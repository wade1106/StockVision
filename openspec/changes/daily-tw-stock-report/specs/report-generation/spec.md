## ADDED Requirements

### Requirement: 批次呼叫 Claude API 生成報告
系統 SHALL 將篩選後的看好/看淡股票清單（含 SHAP 因子）一次批次送入 Claude API，生成完整的中文報告。

#### Scenario: 正常生成報告
- **WHEN** ML 預測完成，看好/看淡清單已確定
- **THEN** 系統組裝結構化 prompt，呼叫 Claude API 一次，取得包含每股信心度與文字理由的完整報告

#### Scenario: Claude API 呼叫失敗
- **WHEN** Claude API 回傳錯誤或逾時
- **THEN** 系統 fallback 為純 SHAP 特徵名稱拼接的簡易報告（不中斷推播），並記錄錯誤 log

### Requirement: 信心度門檻篩選
系統 SHALL 以 70% 為信心度門檻篩選報告股票，門檻下無股票時自動 fallback。

#### Scenario: 正常門檻篩選
- **WHEN** ML 推理完成
- **THEN** 看好清單取信心度 > 70% 的股票，最多 10 支；看淡清單取信心度 > 70% 的股票，最多 5 支

#### Scenario: 看好清單為零時 fallback
- **WHEN** 信心度 > 70% 的看好股票數為 0
- **THEN** 強制取信心度最高的前 5 支，並在報告中標註「今日最高信心度僅 XX%，訊號偏弱」

#### Scenario: 看淡清單為零時 fallback
- **WHEN** 信心度 > 70% 的看淡股票數為 0
- **THEN** 強制取信心度最低的前 3 支（看漲機率最低），並標註「今日最高看淡信心度僅 XX%，訊號偏弱」

### Requirement: 輸出 Markdown 報告存檔
系統 SHALL 將每日完整報告存為 Markdown 檔案。

#### Scenario: 報告存檔
- **WHEN** 報告生成完成
- **THEN** 系統將報告寫入 `reports/<YYYY-MM-DD>.md`，格式包含：大盤總覽、看好股票表格（股票、信心度、理由）、看淡股票表格、方法說明