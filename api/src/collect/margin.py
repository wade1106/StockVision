import logging
import time
from datetime import date
from pathlib import Path

import pandas as pd
import requests

logger = logging.getLogger(__name__)

DATA_DIR = Path("data/margin")
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://www.twse.com.tw/",
}

TWSE_MARGIN_URL = "https://www.twse.com.tw/rwd/zh/marginTrading/MI_MARGN"
TPEX_MARGIN_URL = "https://www.tpex.org.tw/web/stock/margin_trading/margin_balance/margin_bal_result.php"


def _fetch_twse_margin(target_date: date) -> pd.DataFrame:
    date_str = target_date.strftime("%Y%m%d")
    params = {"date": date_str, "selectType": "ALL", "response": "json"}
    resp = requests.get(TWSE_MARGIN_URL, params=params, headers=HEADERS, timeout=30)
    data = resp.json()

    if data.get("stat") != "OK":
        return pd.DataFrame()

    # 找列數最多的 table（股票明細表）
    tables = data.get("tables", [])
    target = max(tables, key=lambda t: len(t.get("data", [])), default=None)

    if not target or not target.get("data"):
        return pd.DataFrame()

    # 欄位位置固定：margin_balance=5, short_balance=10，相容 13 或 16 欄
    records = []
    for row in target["data"]:
        clean = [str(c).replace(",", "").strip() if c is not None else "0" for c in row]
        n = len(clean)
        if n < 6:
            continue
        records.append({
            "code":           clean[0],
            "name":           clean[1],
            "margin_buy":     clean[2] if n > 2 else "0",
            "margin_sell":    clean[3] if n > 3 else "0",
            "margin_balance": clean[5] if n > 5 else "0",
            "short_sell":     clean[7] if n > 7 else "0",
            "short_buy":      clean[8] if n > 8 else "0",
            "short_balance":  clean[10] if n > 10 else "0",
        })

    if not records:
        return pd.DataFrame()

    df = pd.DataFrame(records)
    df["date"] = pd.Timestamp(target_date)

    numeric_cols = [c for c in df.columns if c not in ("code", "name", "date")]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    return df


def _fetch_tpex_margin(target_date: date) -> pd.DataFrame:
    date_str = f"{target_date.year - 1911}/{target_date.month:02d}/{target_date.day:02d}"
    params = {"l": "zh-tw", "d": date_str, "s": "0,asc"}
    resp = requests.get(TPEX_MARGIN_URL, params=params, headers=HEADERS, timeout=30)
    data = resp.json()

    # 新格式：tables[0]["data"]；舊格式：aaData
    if "tables" in data:
        tables = data.get("tables", [])
        rows = tables[0].get("data", []) if tables else []
    else:
        rows = data.get("aaData", [])

    if not rows:
        return pd.DataFrame()

    # 舊格式(13欄): margin_balance=col6, short_balance=col11
    # 新格式(20欄): margin_balance=col6, short_balance=col14
    records = []
    for row in rows:
        clean = [str(c).replace(",", "").strip() if c is not None else "0" for c in row]
        n = len(clean)
        if n < 7:
            continue
        short_balance_idx = 14 if n >= 15 else 11
        records.append({
            "code":           clean[0],
            "name":           clean[1],
            "margin_buy":     clean[3] if n > 3 else "0",
            "margin_sell":    clean[4] if n > 4 else "0",
            "margin_balance": clean[6] if n > 6 else "0",
            "short_balance":  clean[short_balance_idx] if n > short_balance_idx else "0",
        })

    if not records:
        return pd.DataFrame()

    df = pd.DataFrame(records)
    df["date"] = pd.Timestamp(target_date)

    numeric_cols = [c for c in df.columns if c not in ("code", "name", "date")]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    return df


def _append_to_parquet(ticker_code: str, row: pd.Series) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = DATA_DIR / f"{ticker_code}.parquet"
    new_df = row.to_frame().T.set_index("date")

    if path.exists():
        existing = pd.read_parquet(path)
        combined = pd.concat([existing, new_df])
        combined = combined[~combined.index.duplicated(keep="last")]
        combined.sort_index(inplace=True)
        combined.to_parquet(path)
    else:
        new_df.to_parquet(path)


def fetch_today(target_date: date | None = None) -> dict[str, bool]:
    """
    抓取全市場融資融券資料並寫入各股 Parquet。
    全額交割股無融資融券，margin_balance / short_balance 以 0 填入。
    """
    if target_date is None:
        target_date = date.today()

    results: dict[str, bool] = {}

    try:
        twse_df = _fetch_twse_margin(target_date)
        logger.info("TWSE 融資融券: %d 支", len(twse_df))
        time.sleep(1)
    except Exception as e:
        logger.error("TWSE 融資融券抓取失敗: %s", e)
        twse_df = pd.DataFrame()

    try:
        tpex_df = _fetch_tpex_margin(target_date)
        logger.info("TPEX 融資融券: %d 支", len(tpex_df))
    except Exception as e:
        logger.error("TPEX 融資融券抓取失敗: %s", e)
        tpex_df = pd.DataFrame()

    for df in [twse_df, tpex_df]:
        if df.empty:
            continue
        for _, row in df.iterrows():
            code = str(row["code"]).strip()
            try:
                _append_to_parquet(code, row)
                results[code] = True
            except Exception as e:
                logger.error("寫入 %s 融資融券失敗: %s", code, e)
                results[code] = False

    return results


def fetch_history(target_date: date, market: str = "TWSE") -> pd.DataFrame:
    """Bootstrap 用：抓取單日歷史融資融券資料，回傳 DataFrame。"""
    if market == "TWSE":
        return _fetch_twse_margin(target_date)
    return _fetch_tpex_margin(target_date)
