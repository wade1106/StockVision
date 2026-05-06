## Why

散戶難以在收盤後快速整合技術面與籌碼面訊號來決定隔日佈局。本系統每天收盤後自動抓取台股全市場資料、以 LightGBM 預測隔日漲跌機率、並透過 Claude API 生成含信心度與理由的看好/看淡報告，再推播至 LINE。

## What Changes

- 新增每日自動化 Pipeline，GitHub Actions 於 17:30 TST 觸發
- 新增 Bootstrap 腳本，一次性抓取 5 年歷史資料並訓練初始模型
- 新增 Phase 1 資料收集模組：OHLCV (yfinance)、三大法人籌碼、融資融券 (TWSE 爬蟲)
- 新增 Phase 2 分析模組：特徵工程 (ta-lib)、LightGBM 推理、SHAP 解釋、Claude API 報告生成
- 新增 LINE Messaging API 推播，每日發送 Flex Message 卡片報告
- 新增歷史資料存儲，以 Parquet 格式按股票/日期分檔管理

## Capabilities

### New Capabilities

- `data-collection`: 每日增量抓取台股全市場 OHLCV、三大法人籌碼、融資融券，存入 Parquet
- `feature-engineering`: 基於歷史 Parquet 計算技術指標與籌碼特徵，組合成模型輸入
- `ml-prediction`: LightGBM 模型推理全市場個股隔日看漲機率，並以 SHAP 抽取關鍵因子
- `report-generation`: 將 ML 預測結果與 SHAP 因子送入 Claude API，生成含信心度與理由的看好/看淡報告
- `line-notification`: 透過 LINE Messaging API 推播 Flex Message，看好 Top 5~10 / 看淡 Top 3~5，信心度門檻 70%，為零時 fallback Top N 並標示警示
- `bootstrap`: 一次性腳本，抓取 5 年歷史資料並訓練初始 LightGBM 模型

### Modified Capabilities

## Impact

- 新增 Python 依賴：yfinance, pandas, ta-lib, lightgbm, shap, anthropic, line-bot-sdk
- GitHub Actions 需設定 Secrets：ANTHROPIC_API_KEY、LINE_CHANNEL_ACCESS_TOKEN
- 資料存儲：`data/` 目錄下 Parquet 檔案，首次 bootstrap 後約數 GB
- 模型存儲：`models/lgbm_model.pkl`，需納入版控或 GitHub Releases
