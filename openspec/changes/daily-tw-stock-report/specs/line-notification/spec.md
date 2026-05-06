## ADDED Requirements

### Requirement: 透過 LINE Messaging API 推播 Flex Message 至群組
系統 SHALL 使用 LINE Messaging API 將當日報告以 Flex Message 卡片格式推播至指定 LINE 群組（Group ID）。

#### Scenario: 正常推播
- **WHEN** 報告生成完成
- **THEN** 系統以環境變數 `LINE_GROUP_ID`（格式 `Cxxxxxxxxxxxxxxxxx`）為收件對象，呼叫 LINE Messaging API push 端點，發送一則包含看好 Top N 與看淡 Top N 的 Flex Message 卡片至群組

#### Scenario: LINE API 呼叫失敗
- **WHEN** LINE Messaging API 回傳錯誤
- **THEN** 系統記錄錯誤 log，不重試，Markdown 報告仍正常存檔

### Requirement: Flex Message 卡片格式
系統 SHALL 以結構化卡片呈現報告，包含股票名稱、信心度進度條、主要理由。

#### Scenario: 正常信心度門檻下的卡片內容
- **WHEN** 看好股票信心度 >= 70%
- **THEN** 卡片顯示：股票代號+名稱、信心度百分比與視覺進度條、Claude 生成的文字理由（1~2句）

#### Scenario: Fallback 警示標示
- **WHEN** 報告為 fallback 模式（信心度低於門檻）
- **THEN** 卡片頂部顯示警示文字：「⚠️ 今日訊號偏弱，最高信心度僅 XX%」

### Requirement: 推播數量限制
系統 SHALL 在 LINE 推播中限制看好最多 10 支、看淡最多 5 支，避免訊息過長。

#### Scenario: 股票數超出上限
- **WHEN** 符合門檻的股票數超過上限
- **THEN** 依信心度排序，取前 N 支，其餘不顯示於 LINE（完整清單仍在 Markdown 報告中）