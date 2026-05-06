import logging
from datetime import date
from pathlib import Path

logger = logging.getLogger(__name__)

REPORTS_DIR = Path("reports")


def write(selection: dict, reasons: dict[str, str], report_date: date | None = None) -> Path:
    """
    將報告寫入 reports/<YYYY-MM-DD>.md 並回傳檔案路徑。
    """
    if report_date is None:
        report_date = date.today()

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = REPORTS_DIR / f"{report_date}.md"

    fallback_note = ""
    if selection["fallback"]:
        max_b = selection["max_bullish_prob"]
        max_s = selection["max_bearish_conf"]
        fallback_note = (
            f"\n> ⚠️ 今日訊號偏弱，"
            f"看好最高信心度 {max_b:.1%}、看淡最高信心度 {max_s:.1%}，"
            f"均未達 {selection['threshold']:.0%} 門檻。以下為相對強弱排序。\n"
        )

    bullish_rows = []
    for s in selection["bullish"]:
        ticker = s.get("ticker", "")
        name = s.get("name", "")
        prob = s["prob"]
        reason = reasons.get(ticker, "—")
        bullish_rows.append(f"| {name} | {ticker} | {prob:.1%} | {reason} |")

    bearish_rows = []
    for s in selection["bearish"]:
        ticker = s.get("ticker", "")
        name = s.get("name", "")
        prob = s["prob"]
        conf = 1 - prob
        reason = reasons.get(ticker, "—")
        bearish_rows.append(f"| {name} | {ticker} | {conf:.1%} | {reason} |")

    content = f"""# 台股每日報告 {report_date}
{fallback_note}
## 看好股票

| 股票 | 代號 | 信心度 | 分析 |
|------|------|--------|------|
{chr(10).join(bullish_rows) if bullish_rows else "| — | — | — | 今日無符合條件股票 |"}

## 看淡股票

| 股票 | 代號 | 信心度 | 分析 |
|------|------|--------|------|
{chr(10).join(bearish_rows) if bearish_rows else "| — | — | — | 今日無符合條件股票 |"}

---
*本報告由 LightGBM 模型預測，SHAP 值解釋關鍵因子，Claude API 生成文字說明。僅供參考，不構成投資建議。*
"""

    out_path.write_text(content, encoding="utf-8")
    logger.info("報告已寫入 %s", out_path)
    return out_path