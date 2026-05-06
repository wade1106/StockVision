## ADDED Requirements

### Requirement: 計算技術指標特徵
系統 SHALL 基於歷史 OHLCV Parquet 資料，使用 ta-lib 計算技術指標，作為模型輸入特徵。

#### Scenario: 正常計算技術指標
- **WHEN** 某支股票有足夠歷史資料（至少 60 個交易日）
- **THEN** 系統計算以下指標並寫入特徵欄位：MA5、MA20、MA60、RSI(14)、MACD、MACD Signal、KD(K值、D值)、布林通道上下軌、成交量 MA5

#### Scenario: 歷史資料不足
- **WHEN** 某支股票歷史資料少於 60 個交易日（如新上市股）
- **THEN** 該股票從當日特徵快照中排除，不進入模型推理

### Requirement: 整合籌碼特徵
系統 SHALL 將三大法人與融資融券資料轉換為模型可用的數值特徵。

#### Scenario: 計算籌碼衍生特徵
- **WHEN** 特徵工程 Pipeline 執行
- **THEN** 系統計算：外資連買/連賣天數、外資近 5 日累計買賣超、投信近 5 日累計買賣超、融資增減幅、融券增減幅

### Requirement: 輸出每日特徵快照
系統 SHALL 將當日全市場特徵組合成一個 Parquet 快照檔案，供模型推理使用。

#### Scenario: 產出特徵快照
- **WHEN** 特徵工程完成
- **THEN** 系統將所有股票當日特徵寫入 `data/features/<YYYY-MM-DD>.parquet`，每列一支股票

#### Scenario: 特徵欄位缺值處理
- **WHEN** 某股票部分特徵欄位為 NaN（如籌碼資料缺漏）
- **THEN** 系統以 LightGBM 可接受的 NaN 保留，不做插補，由模型自行處理缺值