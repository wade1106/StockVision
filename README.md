# StockVision 台股每日 AI 選股系統

每個交易日收盤後，自動抓取台灣全市場股票資料，透過機器學習模型預測哪些個股隔日表現可能優於大盤，並將看好 / 看淡清單推播至 LINE 群組。

---

## 用途

- 每日自動收集上市 + 上櫃全市場 OHLCV、三大法人、融資融券資料
- 以 LightGBM 模型預測個股隔日超額報酬方向
- 透過 LINE Flex Message 推播選股結果（含 AI 理由）
- 後台管理介面查看 LINE 成員清單與預測比對結果

---

## 技術架構

```
資料收集層
├── yfinance          → OHLCV 日線資料（38,000+ 支）
├── TWSE / TPEX API   → 三大法人買賣超
└── TWSE / TPEX API   → 融資融券餘額

特徵工程層
├── 技術指標（MA、RSI、MACD、KD、布林通道）
├── 三大法人籌碼特徵（外資連續買超天數、5日淨買超）
└── 融資融券特徵（餘額變化率）

模型層
└── LightGBM 二元分類模型（lgbm_model.pkl）

推播層
├── LINE Messaging API → Flex Message 推播
└── Cloudflare Tunnel  → Webhook 接收 LINE 事件

後台介面
├── FastAPI            → REST API
├── Vue 3 + Vite       → 前端 SPA
└── 登入驗證（Bearer Token）
```

**自動化排程：** Windows 工作排程器，每日 17:30 觸發 `daily_run.py`

---

## 模型訓練

**目標變數：**
```
label = 1  if  個股明日漲幅 − 加權指數明日漲幅 > 0
label = 0  otherwise
```

**訓練流程：**
1. 以近 5 年歷史資料建立特徵快照
2. `TimeSeriesSplit`（5-fold）時序交叉驗證，防止未來資料洩漏
3. AUC 評估預測力，門檻 0.52
4. 全量資料訓練最終模型

**為什麼選 LightGBM：**

| 考量 | 說明 |
|------|------|
| 速度 | 直方圖梯度提升，大量特徵下訓練速度遠快於傳統 GBDT |
| 缺失值容忍 | 三大法人 / 融資券資料並非每支股票都有，原生支援 NaN |
| 特徵重要性 | 內建 feature importance，方便診斷哪類指標真正有預測力 |
| 小樣本穩定 | `min_child_samples` 防止在冷門股小樣本上過擬合 |
| 無需正規化 | 對特徵尺度不敏感，技術指標與籌碼資料單位差異大也不影響 |

---

## 快速開始

### 1. 安裝依賴

```bash
cd api
uv sync
```

### 2. 設定環境變數

複製 `.env.example` 為 `.env` 並填入：

```
ANTHROPIC_API_KEY=
LINE_CHANNEL_ACCESS_TOKEN=
LINE_CHANNEL_SECRET=
LINE_GROUP_ID=
ADMIN_USERNAME=
ADMIN_PASSWORD=
```

### 3. 初始化歷史資料（一次性）

```bash
uv run python scripts/bootstrap.py
uv run python scripts/train.py
```

### 4. 啟動服務

```bash
# 後端（Webhook + API）
uv run python scripts/webhook_server.py

# 前端
cd web && npm run dev
```

### 5. 手動觸發每日 Pipeline

```bash
uv run python scripts/daily_run.py
# 或指定日期
uv run python scripts/daily_run.py --date 2026-05-05
```

---

## 專案結構

```
api/
├── scripts/
│   ├── bootstrap.py      # 一次性歷史資料初始化
│   ├── train.py          # 模型訓練
│   ├── daily_run.py      # 每日 Pipeline
│   └── webhook_server.py # 後端服務入口
├── src/
│   ├── collect/          # 資料收集（OHLCV、三大法人、融資券）
│   ├── features/         # 特徵工程
│   ├── model/            # 模型推理
│   ├── notify/           # LINE 推播 & Webhook
│   ├── report/           # 報告生成
│   └── web/              # FastAPI 後端
web/                      # Vue 3 前端
```

---

> 本系統預測結果僅供參考，不構成投資建議。