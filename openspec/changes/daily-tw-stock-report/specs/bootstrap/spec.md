## ADDED Requirements

### Requirement: 一次性歷史資料初始化
系統 SHALL 提供 bootstrap 腳本，一次性抓取台股全市場 5 年歷史 OHLCV、籌碼、融資融券資料，建立完整 Parquet 資料庫。

#### Scenario: 正常執行 bootstrap
- **WHEN** 使用者於本機執行 `python scripts/bootstrap.py`
- **THEN** 系統依序抓取全市場 5 年 OHLCV（yfinance）、三大法人歷史（TWSE）、融資融券歷史（TWSE），全部寫入 `data/` 目錄

#### Scenario: 部分股票抓取失敗
- **WHEN** 特定股票 yfinance 請求失敗（如下市股）
- **THEN** 系統跳過該股票，記錄至 `logs/bootstrap_errors.log`，繼續處理其餘股票

### Requirement: 初始模型訓練
系統 SHALL 提供 train 腳本，基於 bootstrap 產生的歷史資料訓練初始 LightGBM 模型。

#### Scenario: 正常訓練
- **WHEN** 使用者執行 `python scripts/train.py`，且 `data/` 目錄有足夠歷史資料
- **THEN** 系統進行特徵工程、訓練 LightGBM 二元分類模型，輸出 `models/lgbm_model.pkl`，並印出驗證集 AUC 分數

#### Scenario: 訓練資料不足
- **WHEN** 可用歷史資料少於 1 年
- **THEN** 系統警告並中止訓練，提示需先完整執行 bootstrap

### Requirement: Bootstrap 為手動一次性操作
Bootstrap 腳本 SHALL 不納入每日自動排程，僅供初始化或手動 retrain 使用。

#### Scenario: 防止誤觸發
- **WHEN** GitHub Actions daily workflow 執行
- **THEN** bootstrap 腳本不在 daily workflow 中，不會被自動觸發