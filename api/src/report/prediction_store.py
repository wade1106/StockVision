import json
import logging
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

PRED_DIR = Path("data/predictions")
OHLCV_DIR = Path("data/ohlcv")


def save(selection: dict, report_date: date | None = None) -> None:
    """每日 Pipeline 結束後儲存預測快照至 data/predictions/<YYYY-MM-DD>.json。"""
    if report_date is None:
        report_date = date.today()

    PRED_DIR.mkdir(parents=True, exist_ok=True)
    path = PRED_DIR / f"{report_date}.json"

    payload = {
        "date": str(report_date),
        "bullish": [
            {
                "ticker": s.get("ticker", ""),
                "name": s.get("name", ""),
                "prob": round(float(s["prob"]), 4),
                "shap_top3": s.get("shap_top3") or [],
            }
            for s in selection["bullish"]
        ],
        "bearish": [
            {
                "ticker": s.get("ticker", ""),
                "name": s.get("name", ""),
                "prob": round(float(s["prob"]), 4),
                "shap_top3": s.get("shap_top3") or [],
            }
            for s in selection["bearish"]
        ],
        "fallback": selection["fallback"],
        "threshold": selection["threshold"],
    }

    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("預測快照已存至 %s", path)


def load(pred_date: date) -> dict | None:
    path = PRED_DIR / f"{pred_date}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def available_dates() -> list[date]:
    """回傳所有已存在預測快照的日期，由新到舊。"""
    if not PRED_DIR.exists():
        return []
    dates = []
    for p in PRED_DIR.glob("*.json"):
        try:
            dates.append(date.fromisoformat(p.stem))
        except ValueError:
            pass
    return sorted(dates, reverse=True)


def _actual_return(ticker: str, pred_date: date) -> float | None:
    """取得 pred_date 隔日的實際漲跌幅。"""
    path = OHLCV_DIR / f"{ticker}.parquet"
    if not path.exists():
        return None
    try:
        df = pd.read_parquet(path)
        df.index = pd.to_datetime(df.index)
        df.sort_index(inplace=True)

        # 找 pred_date 之後的第一個交易日
        future = df[df.index.date > pred_date]
        if future.empty:
            return None
        next_close = future["close"].iloc[0]

        today_rows = df[df.index.date == pred_date]
        if today_rows.empty:
            return None
        today_close = today_rows["close"].iloc[-1]

        return float((next_close - today_close) / today_close)
    except Exception:
        return None


def build_comparison(start: date, end: date) -> list[dict]:
    """
    建立 start~end 日期範圍內的 預測股價 vs 實際股價 清單。
    每筆：date, ticker, name, direction, prob, actual_return, correct
    """
    rows = []
    current = start
    while current <= end:
        pred = load(current)
        if pred:
            for s in pred["bullish"]:
                actual = _actual_return(s["ticker"], current)
                correct = (actual > 0) if actual is not None else None
                rows.append({
                    "date": str(current),
                    "ticker": s["ticker"],
                    "name": s["name"],
                    "direction": "bullish",
                    "prob": round(s["prob"] * 100, 1),
                    "actual_return": round(actual * 100, 2) if actual is not None else None,
                    "correct": correct,
                })
            for s in pred["bearish"]:
                actual = _actual_return(s["ticker"], current)
                correct = (actual < 0) if actual is not None else None
                rows.append({
                    "date": str(current),
                    "ticker": s["ticker"],
                    "name": s["name"],
                    "direction": "bearish",
                    "prob": round((1 - s["prob"]) * 100, 1),
                    "actual_return": round(actual * 100, 2) if actual is not None else None,
                    "correct": correct,
                })
        current += timedelta(days=1)

    return rows
