## 1. 專案基礎建設

- [x] 1.1 建立專案目錄結構（src/collect, src/features, src/model, src/report, src/notify, scripts, data, models, reports）
- [x] 1.2 建立 `pyproject.toml`（uv），加入 yfinance, pandas, ta-lib, lightgbm, shap, anthropic, line-bot-sdk, fastapi, uvicorn, requests
- [x] 1.3 建立 `.env.example`，列出所需環境變數：ANTHROPIC_API_KEY, LINE_CHANNEL_ACCESS_TOKEN, LINE_GROUP_ID
- [x] 1.4 建立 `.gitignore`，排除 `.env`, `data/`, `models/`, `logs/`

## 2. 資料收集模組

- [x] 2.1 實作 `src/collect/ohlcv.py`：透過 yfinance 抓取指定股票清單的當日 OHLCV，append 至 `data/ohlcv/<ticker>.parquet`
- [x] 2.2 實作 `src/collect/stock_list.py`：從 TWSE/TPEX 抓取台股全市場股票清單（代號+名稱）
- [x] 2.3 實作 `src/collect/institutional.py`：爬取 TWSE 三大法人當日買賣超資料，append 至 `data/institutional/<ticker>.parquet`
- [x] 2.4 實作 `src/collect/margin.py`：爬取 TWSE 融資融券當日資料，append 至 `data/margin/<ticker>.parquet`
- [x] 2.5 加入資料完整性檢查：缺漏超過 5% 時記錄警告，缺值股票以 NaN 填入

## 3. 特徵工程模組

- [x] 3.1 實作 `src/features/technical.py`：計算 MA5/20/60、RSI(14)、MACD、KD、布林通道、成交量 MA5
- [x] 3.2 實作 `src/features/institutional_features.py`：計算外資/投信連買連賣天數、近 5 日累計買賣超、融資融券增減幅
- [x] 3.3 實作 `src/features/pipeline.py`：合併所有特徵，過濾歷史不足 60 日的股票，輸出 `data/features/<YYYY-MM-DD>.parquet`

## 4. Bootstrap 與模型訓練

- [x] 4.1 實作 `scripts/bootstrap.py`：批次抓取全市場 5 年歷史 OHLCV（yfinance），含錯誤跳過與進度顯示
- [x] 4.2 實作 TWSE 歷史籌碼爬蟲，整合進 bootstrap 流程
- [x] 4.3 實作 TWSE 歷史融資融券爬蟲，整合進 bootstrap 流程
- [x] 4.4 實作 `scripts/train.py`：計算歷史特徵、建立訓練/驗證集、訓練 LightGBM 二元分類模型（目標：超額報酬 > 0）
- [x] 4.5 訓練完成後輸出 `models/lgbm_model.pkl`，並印出驗證集 AUC

## 5. 推理與 SHAP 解釋

- [x] 5.1 實作 `src/model/predict.py`：載入 `models/lgbm_model.pkl`，對當日特徵快照執行推理，輸出各股看漲機率
- [x] 5.2 實作 SHAP 計算：對進入報告門檻的股票計算 SHAP 值，抽取前 3 大貢獻特徵（方向+名稱）
- [x] 5.3 實作信心度門檻篩選邏輯：看好 >70% 最多 10 支、看淡 >70% 最多 5 支，含 fallback Top N 與警示標記

## 6. 報告生成

- [x] 6.1 設計 Claude API prompt 模板：輸入為結構化 JSON（股票清單+信心度+SHAP 因子），輸出為中文報告
- [x] 6.2 實作 `src/report/generator.py`：批次呼叫 Claude API，解析回傳報告
- [x] 6.3 實作 fallback 報告生成：Claude API 失敗時，以 SHAP 特徵名稱拼接簡易文字理由
- [x] 6.4 實作 `src/report/markdown_writer.py`：將報告寫入 `reports/<YYYY-MM-DD>.md`

## 7. LINE 推播

- [x] 7.1 實作 `src/notify/line_bot.py`：呼叫 LINE Messaging API 發送訊息
- [x] 7.2 設計 Flex Message JSON 模板：包含股票名稱、信心度進度條、理由文字
- [x] 7.3 實作 fallback 警示標示：信心度低於門檻時在卡片頂部加入警示文字
- [x] 7.4 實作錯誤處理：LINE API 失敗時記錄 log，不中斷主流程

## 7b. LINE Webhook Server

- [x] 7b.1 實作 `src/notify/webhook.py`：FastAPI webhook handler，處理 follow / memberJoined / join 事件
- [x] 7b.2 實作 `scripts/webhook_server.py`：uvicorn 啟動入口，搭配 Cloudflare Tunnel 使用
- [x] 7b.3 `data/users.json` 儲存使用者 userId、displayName、來源與加入時間

## 8. 主流程整合

- [x] 8.1 實作 `scripts/daily_run.py`：依序呼叫 collect → features → predict → report → notify，含各步驟錯誤處理
- [x] 8.2 加入非交易日偵測：無新資料時優雅結束，不執行後續步驟
- [x] 8.3 加入全流程 log 輸出至 `logs/daily_<YYYY-MM-DD>.log`

## 8b. 預測快照儲存

- [x] 8b.1 實作 `src/report/prediction_store.py`：每日儲存預測快照至 `data/predictions/<YYYY-MM-DD>.json`
- [x] 8b.2 `daily_run.py` Phase 5 呼叫 `prediction_store.save()`，確保每日預測可供比對

## 8c. 前後端分離重構

- [x] 8c.1 後端移至 `api/`，前端移至 `web/`，獨立專案結構
- [x] 8c.2 實作 `api/src/web/app.py`：FastAPI JSON API（`/api/users`、`/api/performance`）
- [x] 8c.3 建立 Vue 3 + Vite 前端專案（`web/package.json`、`vite.config.js`、proxy 設定）
- [x] 8c.4 實作 `web/src/views/Users.vue`：LINE 成員列表頁
- [x] 8c.5 實作 `web/src/views/Performance.vue`：預測比對頁（日期篩選、統計數字、折線/長條/甜甜圈圖、可排序表格）
- [x] 8c.6 更新 GitHub Actions `working-directory: api`，Python 版本固定 3.12

## 9. GitHub Actions 設定

- [x] 9.1 建立 `.github/workflows/daily.yml`：cron 設定為每日 09:30 UTC（=17:30 TST），執行 `scripts/daily_run.py`
- [x] 9.2 在 workflow 中設定 Secrets 讀取：ANTHROPIC_API_KEY, LINE_CHANNEL_ACCESS_TOKEN, LINE_GROUP_ID
- [x] 9.3 建立 `.github/workflows/bootstrap.yml`：手動觸發（workflow_dispatch），執行 bootstrap + train
- [ ] 9.4 驗證 Actions 執行時間在限制內（目標 < 30 分鐘）【需實際觸發 Actions 後確認】

## 10. 驗證與測試

- [ ] 10.1 手動執行 bootstrap，確認全市場資料正確寫入 Parquet
- [ ] 10.2 執行 train.py，確認模型輸出 AUC > 0.52（優於隨機）
- [ ] 10.3 手動執行 daily_run.py，確認完整流程從資料到 LINE 推播無誤
- [ ] 10.4 測試 fallback 機制：模擬信心度全低於門檻，確認警示訊息正確顯示
- [ ] 10.5 觸發 GitHub Actions 一次，確認雲端執行正常
