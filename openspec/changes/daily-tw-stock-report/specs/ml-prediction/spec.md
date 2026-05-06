## ADDED Requirements

### Requirement: LightGBM 推理全市場個股
系統 SHALL 載入預訓練 LightGBM 模型，對當日特徵快照中的所有股票執行推理，輸出各股看漲機率。

#### Scenario: 正常推理
- **WHEN** 當日特徵快照存在且模型檔案 `models/lgbm_model.pkl` 可載入
- **THEN** 系統輸出每支股票的看漲機率（0.0~1.0），代表明日超額報酬為正的信心度

#### Scenario: 模型檔案不存在
- **WHEN** `models/lgbm_model.pkl` 不存在
- **THEN** 系統終止 Pipeline 並發送 LINE 錯誤通知，提示需執行 bootstrap 或 retrain

### Requirement: 目標變數定義
系統 SHALL 以個股隔日報酬相對加權指數的超額報酬作為目標變數（二元分類：超額報酬 > 0 為正類）。

#### Scenario: 訓練時標籤計算
- **WHEN** 訓練資料準備
- **THEN** 標籤 = (個股隔日漲幅 - 加權指數隔日漲幅) > 0，以此作為 LightGBM 的 binary 分類目標

### Requirement: SHAP 值解釋
系統 SHALL 對每支進入報告的股票計算 SHAP 值，抽取貢獻度最高的前 3 個特徵作為理由素材。

#### Scenario: 正常計算 SHAP
- **WHEN** 某股票的看漲機率符合報告門檻
- **THEN** 系統計算該股 SHAP 值，取絕對值最大的前 3 個特徵名稱與方向（正向/負向貢獻）

#### Scenario: SHAP 計算輸出格式
- **WHEN** SHAP 計算完成
- **THEN** 輸出結構為：`{"ticker": "2330", "prob": 0.83, "shap_top3": [{"feature": "institutional_foreign_5d", "direction": "positive"}, ...]}`