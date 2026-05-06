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

    # 取融資融券餘額表（通常在 data[1]）
    tables = data.get("tables", [])
    target = None
    for t in tables:
        if "融資" in t.get("title", ""):
            target = t
            break

    if not target or not target.get("data"):
        return pd.DataFrame()

    cols = ["code", "name",
            "margin_buy", "margin_sell", "margin_redeem", "margin_balance", "margin_limit",
            "short_buy", "short_sell", "short_redeem", "short_balance", "short_limit",
            "offset"]
    rows = [[c.replace(",", "").strip() for c in row] for row in target["data"]]
    df = pd.DataFrame(rows, columns=cols[:len(rows[0])] if rows else cols)
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

    rows = data.get("aaData", [])
    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    df = df.iloc[:, :13]
    df.columns = ["code", "name",
                  "margin_prev", "margin_buy", "margin_sell", "margin_redeem", "margin_balance",
                  "short_prev", "short_buy", "short_sell", "short_redeem", "short_balance",
                  "offset"]
    df["date"] = pd.Timestamp(target_date)

    numeric_cols = [c for c in df.columns if c not in ("code", "name", "date")]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col].astype(str).str.replace(",", ""), errors="coerce")

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
