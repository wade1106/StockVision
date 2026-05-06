## ADDED Requirements

### Requirement: 每日增量抓取 OHLCV 資料
系統 SHALL 於每日 Pipeline 執行時，透過 yfinance 抓取台股全市場當日 OHLCV（開高低收量），並 append 至對應股票的 Parquet 檔案。

#### Scenario: 正常抓取當日資料
- **WHEN** Pipeline 於 17:30 TST 觸發，且 yfinance 回傳當日資料
- **THEN** 系統將當日一筆記錄 append 至 `data/ohlcv/<ticker>.parquet`，不覆蓋歷史資料

#### Scenario: 當日資料缺漏超過閾值
- **WHEN** yfinance 回傳資料中，缺漏股票數超過全市場 5%
- **THEN** 系統記錄警告 log，跳過後續分析與推播，並透過 LINE 發送錯誤通知

#### Scenario: 非交易日觸發
- **WHEN** Pipeline 於假日或停市日觸發
- **THEN** 系統偵測無新資料後，優雅結束，不寫入任何資料

### Requirement: 每日增量抓取三大法人籌碼
系統 SHALL 透過 TWSE 爬蟲抓取當日三大法人（外資、投信、自營商）買賣超資料，並 append 至對應 Parquet 檔案。

#### Scenario: 正常抓取籌碼資料
- **WHEN** Pipeline 執行且 TWSE 網站已公布當日籌碼資料
- **THEN** 系統解析並將外資、投信、自營商買賣超（張數）寫入 `data/institutional/<ticker>.parquet`

#### Scenario: TWSE 網站無回應或結構異動
- **WHEN** 爬蟲請求失敗或解析結果為空
- **THEN** 系統記錄錯誤，該日籌碼欄位以 NaN 填入，繼續執行後續流程（模型可處理缺值）

### Requirement: 每日增量抓取融資融券
系統 SHALL 透過 TWSE 爬蟲抓取當日融資融券餘額資料，並 append 至對應 Parquet 檔案。

#### Scenario: 正常抓取融資融券資料
- **WHEN** Pipeline 執行且 TWSE 已公布融資融券資料
- **THEN** 系統將融資餘額、融券餘額寫入 `data/margin/<ticker>.parquet`

#### Scenario: 融資融券資料缺漏
- **WHEN** 特定股票無融資融券資料（如全額交割股）
- **THEN** 該股票融資融券欄位以 0 或 NaN 填入，不中斷流程