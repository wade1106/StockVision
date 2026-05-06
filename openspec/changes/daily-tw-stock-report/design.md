## Context

台股全市場約 1800 支股票，每交易日收盤後需在有限時間內完成資料收集、特徵工程、模型推理、報告生成與推播。GitHub Actions 免費版限制 7GB RAM、2 core、6 小時上限。TWSE 三大法人與融資融券資料約於 17:00 公布，因此 Pipeline 排定於 17:30 TST 一次觸發，確保資料完整性。

## Goals / Non-Goals

**Goals:**
- 每日 17:30 TST 自動完成全流程，從資料收集到 LINE 推播
- 支援 Bootstrap 一次性初始化（抓 5 年歷史資料 + 訓練初始模型）
- 增量更新，每日只抓當日新資料，不重跑全量
- 模型可解釋：SHAP 值作為報告理由的素材
- 報告信心度門檻 70%，為零時 fallback Top N 並警示

**Non-Goals:**
- 盤中即時訊號（非即時系統）
- 自動下單交易
- 美股或其他市場
- 付費資料來源（全部使用公開資料）

## Decisions

### D1: 排程單次觸發 vs 多次觸發

**決定**：單次觸發，17:30 TST
**理由**：OHLCV、籌碼、融資券全部到齊後一次跑，避免兩次觸發帶來的狀態同步複雜度。17:30 離收盤 4 小時，LINE 用戶仍有足夠時間參考隔日操作。
**捨棄**：14:30 + 17:30 兩段式，複雜度高且好處有限。

### D2: 資料存儲格式

**決定**：Parquet，按股票代號分檔（`data/ohlcv/2330.TW.parquet`）
**理由**：Parquet 壓縮率高，pandas 讀取快，columnar 格式適合按指標查詢。每支股票獨立檔案，增量更新只需 append 當日一筆，不影響其他股票。
**捨棄**：SQLite 增量更新方便但檔案單點、Git 不友好；CSV 無壓縮效率低。

### D3: 模型訓練頻率

**決定**：模型不每日重新訓練，定期（每月或每季）手動觸發 retrain
**理由**：每日重訓 1800 支股票資料在 Actions 上耗時過長且不必要，模型週期性 drift 不大。每日 Pipeline 只做 inference。
**捨棄**：每日重訓，Actions 資源不足且穩定性差。

### D4: 目標變數定義

**決定**：個股隔日報酬相對大盤超額報酬（個股漲幅 - 加權指數漲幅），以 0 為閾值做二元分類
**理由**：純漲跌二分法受大盤整體方向干擾，超額報酬能過濾市場系統性影響，更能反映個股強弱。
**捨棄**：純隔日漲跌二分（受大盤影響太大）、多日後報酬（時間感模糊）。

### D5: SHAP 整合 Claude API 的方式

**決定**：每支股票取 SHAP 值前 3 大特徵，組成結構化 JSON，一次批次送入 Claude API 生成全報告
**理由**：避免對每支股票單獨呼叫 API（1800 次請求），批次處理只需 1~2 次呼叫，成本與延遲均大幅降低。
**捨棄**：逐股呼叫 Claude，API 成本與延遲不可接受。

### D6: LINE 推播方式

**決定**：LINE Messaging API + Flex Message 卡片格式，推播至 LINE 群組（Group ID）

### D8: Python 套件管理

**決定**：使用 `uv` 管理虛擬環境與依賴，以 `pyproject.toml` 取代 `requirements.txt`
**理由**：uv 安裝速度極快（比 pip 快 10~100x），lock file 確保環境可重現，GitHub Actions 有官方 `astral-sh/setup-uv` action 支援。
**捨棄**：pip + requirements.txt（無 lock file，環境重現性較差）。

### D9: LINE Webhook Server

**決定**：FastAPI webhook server，本機執行，透過 Cloudflare Tunnel 對外暴露 HTTPS 端點
**理由**：不需要付費雲端主機，Cloudflare Tunnel 提供穩定的公開 HTTPS URL。FastAPI 輕量且型別安全。
**捨棄**：部署至 Render/Railway（需額外帳號與 CI 設定）、Flask（功能足夠但 FastAPI 更現代）。
**用途**：接收 LINE Platform 的 `follow`（追蹤官方帳號）與 `memberJoined`（加入群組）事件，記錄使用者 userId + displayName 至 `data/users.json`。
**理由**：LINE Notify 已於 2025/3/31 停止服務。Flex Message 支援結構化卡片，視覺清晰。推播至群組而非個人，方便多人共同接收報告，且日後新增成員只需加入群組，無需異動程式碼或 Secrets。
**捨棄**：LINE Notify（已停服）、推播給個人 User ID（擴展性差）、Broadcast（需付費方案）。

### D7: 模型檔案存放

**決定**：`models/lgbm_model.pkl` 納入 Git 版控（檔案通常 < 50MB）
**理由**：簡單，Actions 可直接 checkout 後 inference，無需額外下載步驟。
**捨棄**：GitHub Releases，需額外 download step，複雜度增加。

## Risks / Trade-offs

- **TWSE 網站結構變動** → 爬蟲失效：爬蟲模組獨立封裝，失效時只影響籌碼資料，OHLCV 仍可跑；加入 schema 驗證，異常時 Slack/LINE 告警。
- **yfinance 資料延遲或缺漏** → 當日資料不完整：加入資料完整性檢查，缺漏超過閾值時 skip 推播並告警。
- **LightGBM 模型 drift** → 預測品質下降：定期回測評估，metrics 低於門檻時觸發 retrain。
- **Actions 執行時間超出預期** → Pipeline 失敗：分拆 collect / predict / report 為獨立 job，失敗時各自重試，減少全量重跑。
- **Claude API 費用** → 批次設計控制在每日 1~2 次呼叫，估計 token 數可控。

## Migration Plan

1. 本機執行 `scripts/bootstrap.py` 抓取 5 年歷史資料（約 30~60 分鐘）
2. 執行 `scripts/train.py` 訓練初始模型，產出 `models/lgbm_model.pkl`
3. 設定 GitHub Secrets：`ANTHROPIC_API_KEY`、`LINE_CHANNEL_ACCESS_TOKEN`、`LINE_GROUP_ID`
4. Push 至 GitHub，啟用 `.github/workflows/daily.yml`
5. 手動觸發一次驗證全流程
6. 觀察首週報告品質，視情況調整信心度門檻或特徵

**Rollback**：停用 Actions workflow 即可停止推播，資料與模型不受影響。

## Open Questions

- TWSE 爬蟲的 rate limit 策略？全市場 1800 支籌碼資料是否可以一次性 bulk 下載，還是需要逐頁爬取？
- 首次 Bootstrap 的 5 年歷史籌碼資料，TWSE 是否有完整的歷史查詢介面？
- LINE 群組的 Group ID 取得：需先將 Official Account 加入群組，並透過 Webhook 事件取得 `groupId`（`Cxxxxxxxxxxxxxxxxx`）。
