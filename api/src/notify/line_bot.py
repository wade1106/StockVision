import logging
import os
from datetime import date

from linebot.v3 import WebhookHandler
from linebot.v3.messaging import (
    ApiClient,
    Configuration,
    MessagingApi,
    PushMessageRequest,
    FlexMessage,
    FlexContainer,
)

logger = logging.getLogger(__name__)


def _build_stock_block(stock: dict, reasons: dict, sentiment: str) -> dict:
    ticker = stock.get("ticker", "")
    name = stock.get("name", ticker)
    prob = stock["prob"]
    conf = prob if sentiment == "bullish" else (1 - prob)
    reason = reasons.get(ticker, "—")
    color = "#27ae60" if sentiment == "bullish" else "#e74c3c"
    label = "看好" if sentiment == "bullish" else "看淡"
    bar_width = f"{int(conf * 100)}%"

    return {
        "type": "box",
        "layout": "vertical",
        "margin": "md",
        "contents": [
            {
                "type": "box",
                "layout": "horizontal",
                "contents": [
                    {
                        "type": "text",
                        "text": f"{name}（{ticker}）",
                        "weight": "bold",
                        "size": "sm",
                        "flex": 3,
                    },
                    {
                        "type": "text",
                        "text": f"{label} {conf:.0%}",
                        "size": "sm",
                        "color": color,
                        "align": "end",
                        "flex": 2,
                    },
                ],
            },
            {
                "type": "box",
                "layout": "vertical",
                "margin": "xs",
                "contents": [
                    {
                        "type": "box",
                        "layout": "vertical",
                        "height": "6px",
                        "backgroundColor": "#eeeeee",
                        "contents": [
                            {
                                "type": "box",
                                "layout": "vertical",
                                "height": "6px",
                                "backgroundColor": color,
                                "width": bar_width,
                                "contents": [],
                            }
                        ],
                    }
                ],
            },
            {
                "type": "text",
                "text": reason,
                "size": "xs",
                "color": "#555555",
                "wrap": True,
                "margin": "xs",
            },
        ],
    }


def _build_flex(selection: dict, reasons: dict, report_date: date) -> dict:
    fallback = selection["fallback"]
    header_text = f"📊 台股每日報告 {report_date}"

    header_contents = [
        {"type": "text", "text": header_text, "weight": "bold", "size": "md", "color": "#ffffff"}
    ]
    if fallback:
        max_b = selection["max_bullish_prob"]
        header_contents.append({
            "type": "text",
            "text": f"⚠️ 今日訊號偏弱，最高信心度 {max_b:.0%}",
            "size": "xs",
            "color": "#ffdddd",
            "margin": "xs",
        })

    bullish_blocks = [_build_stock_block(s, reasons, "bullish") for s in selection["bullish"]]
    bearish_blocks = [_build_stock_block(s, reasons, "bearish") for s in selection["bearish"]]

    body_contents = []
    if bullish_blocks:
        body_contents.append({"type": "text", "text": "🟢 看好", "weight": "bold", "size": "sm"})
        body_contents.extend(bullish_blocks)
    if bearish_blocks:
        body_contents.append({
            "type": "text", "text": "🔴 看淡", "weight": "bold",
            "size": "sm", "margin": "lg",
        })
        body_contents.extend(bearish_blocks)

    return {
        "type": "bubble",
        "size": "giga",
        "header": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": "#1a1a2e",
            "contents": header_contents,
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "spacing": "sm",
            "contents": body_contents,
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "text",
                    "text": "僅供參考，不構成投資建議",
                    "size": "xxs",
                    "color": "#aaaaaa",
                    "align": "center",
                }
            ],
        },
    }


def push(selection: dict, reasons: dict, report_date: date | None = None) -> None:
    """
    推播 Flex Message 至 LINE 群組。
    失敗時記錄 log，不拋出例外。
    """
    if report_date is None:
        report_date = date.today()

    token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")
    group_id = os.environ.get("LINE_GROUP_ID", "")

    if not token or not group_id:
        logger.error("LINE_CHANNEL_ACCESS_TOKEN 或 LINE_GROUP_ID 未設定")
        return

    try:
        flex_body = _build_flex(selection, reasons, report_date)
        config = Configuration(access_token=token)

        with ApiClient(config) as api_client:
            api = MessagingApi(api_client)
            api.push_message(
                PushMessageRequest(
                    to=group_id,
                    messages=[
                        FlexMessage(
                            alt_text=f"台股每日報告 {report_date}",
                            contents=FlexContainer.from_dict(flex_body),
                        )
                    ],
                )
            )

        logger.info("LINE 推播成功：%s", report_date)

    except Exception as e:
        logger.error("LINE 推播失敗: %s", e)