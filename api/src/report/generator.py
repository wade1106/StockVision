import json
import logging
import os
from datetime import date

import anthropic

logger = logging.getLogger(__name__)

FEATURE_LABELS = {
    "foreign_consecutive": "外資連續買賣天數",
    "foreign_5d_net": "外資近5日累計買賣超",
    "foreign_net_today": "外資今日買賣超",
    "it_consecutive": "投信連續買賣天數",
    "it_5d_net": "投信近5日累計買賣超",
    "it_net_today": "投信今日買賣超",
    "margin_change_pct": "融資增減幅",
    "short_change_pct": "融券增減幅",
    "rsi_14": "RSI(14)",
    "macd_hist": "MACD 柱狀",
    "slowk": "KD 的 K 值",
    "slowd": "KD 的 D 值",
    "price_vs_ma20": "股價與20日均線偏離",
    "volume_ratio": "成交量比值",
    "bb_upper": "布林上軌",
    "bb_lower": "布林下軌",
}


def _feature_to_label(feature: str) -> str:
    return FEATURE_LABELS.get(feature, feature)


def _build_prompt(selection: dict, report_date: date) -> str:
    bullish = selection["bullish"]
    bearish = selection["bearish"]
    fallback = selection["fallback"]
    threshold = selection["threshold"]

    bullish_lines = []
    for s in bullish:
        shap = s.get("shap_top3") or []
        factors = "、".join(
            f"{_feature_to_label(f['feature'])}{'偏高' if f['direction'] == 'positive' else '偏低'}"
            for f in shap
        )
        bullish_lines.append(
            f"- {s.get('name', '')}（{s.get('ticker', '')}）：信心度 {s['prob']:.1%}，關鍵因子：{factors}"
        )

    bearish_lines = []
    for s in bearish:
        shap = s.get("shap_top3") or []
        factors = "、".join(
            f"{_feature_to_label(f['feature'])}{'偏高' if f['direction'] == 'positive' else '偏低'}"
            for f in shap
        )
        bearish_lines.append(
            f"- {s.get('name', '')}（{s.get('ticker', '')}）：看淡信心度 {1 - s['prob']:.1%}，關鍵因子：{factors}"
        )

    fallback_note = (
        f"\n注意：今日整體訊號偏弱，信心度未達 {threshold:.0%} 門檻，以下為相對強弱排序。\n"
        if fallback else ""
    )

    return f"""你是一位台股分析師，請根據以下量化分析結果，為每支股票撰寫簡短的中文投資觀點（每支 1~2 句話），語氣專業但易懂。

報告日期：{report_date}（分析明日走勢）
{fallback_note}
【看好股票】
{chr(10).join(bullish_lines)}

【看淡股票】
{chr(10).join(bearish_lines)}

請依序輸出每支股票的分析，格式如下（嚴格遵守，不要加其他文字）：
```json
{{
  "bullish": [
    {{"ticker": "股票代號", "reason": "分析文字"}}
  ],
  "bearish": [
    {{"ticker": "股票代號", "reason": "分析文字"}}
  ]
}}
```"""


def _fallback_reason(stock: dict, sentiment: str) -> str:
    shap = stock.get("shap_top3") or []
    if not shap:
        return "技術面與籌碼面訊號綜合判斷。"
    parts = [
        f"{_feature_to_label(f['feature'])}{'表現強勢' if f['direction'] == 'positive' else '表現偏弱'}"
        for f in shap
    ]
    return "、".join(parts) + f"，{'看好' if sentiment == 'bullish' else '看淡'}訊號出現。"


def generate(selection: dict, report_date: date | None = None) -> dict:
    """
    呼叫 Claude API 生成報告理由。
    回傳 {ticker: reason} 的字典，包含看好與看淡。
    失敗時 fallback 為 SHAP 特徵拼接的簡易理由。
    """
    if report_date is None:
        report_date = date.today()

    reasons: dict[str, str] = {}

    try:
        client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
        prompt = _build_prompt(selection, report_date)

        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )

        text = message.content[0].text
        # 取出 JSON 區塊
        start = text.find("{")
        end = text.rfind("}") + 1
        parsed = json.loads(text[start:end])

        for item in parsed.get("bullish", []):
            reasons[item["ticker"]] = item["reason"]
        for item in parsed.get("bearish", []):
            reasons[item["ticker"]] = item["reason"]

        logger.info("Claude API 報告生成成功，共 %d 支", len(reasons))

    except Exception as e:
        logger.error("Claude API 失敗，使用 fallback 理由: %s", e)
        for s in selection["bullish"]:
            reasons[s["ticker"]] = _fallback_reason(s, "bullish")
        for s in selection["bearish"]:
            reasons[s["ticker"]] = _fallback_reason(s, "bearish")

    return reasons