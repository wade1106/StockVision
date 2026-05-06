import logging
import time
from datetime import date
from io import StringIO
from pathlib import Path

import pandas as pd
import requests

logger = logging.getLogger(__name__)

DATA_DIR = Path("data/institutional")
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://www.twse.com.tw/",
}

# TWSE 三大法人 bulk API，回傳當日全市場
TWSE_INST_URL = "https://www.twse.com.tw/rwd/zh/fund/T86"
TPEX_INST_URL = "https://www.tpex.org.tw/web/stock/3insti/daily_trade/3itrade_hedge_result.php"


def _fetch_twse_institutional(target_date: date) -> pd.DataFrame:
    date_str = target_date.strftime("%Y%m%d")
    params = {"date": date_str, "selectType": "ALLBUT0999", "response": "json"}
    resp = requests.get(TWSE_INST_URL, params=params, headers=HEADERS, timeout=30)
    data = resp.json()

    if data.get("stat") != "OK" or not data.get("data"):
        return pd.DataFrame()

    # 欄位依位置抓取，相容 12 欄與 19 欄格式
    # 12 欄: code,name, 外資(3), 投信(3), 自營(3), total_net
    # 19 欄: code,name, 外資(3), 投信(3), 自營自行(3), 自營避險(3), dealer_net, 合計(3), extra
    COL_MAP = {
        "code": 0, "name": 1,
        "foreign_buy": 2, "foreign_sell": 3, "foreign_net": 4,
        "investment_trust_buy": 5, "investment_trust_sell": 6, "investment_trust_net": 7,
    }

    rows = []
    for row in data["data"]:
        clean = [str(c).replace(",", "").strip() if c is not None else "0" for c in row]
        n = len(clean)
        record = {k: clean[i] for k, i in COL_MAP.items() if i < n}
        # dealer_net 和 total_net 依欄位數選對應位置
        record["dealer_net"] = clean[14] if n >= 15 else (clean[8] if n >= 9 else "0")
        record["total_net"]  = clean[17] if n >= 18 else (clean[11] if n >= 12 else "0")
        rows.append(record)

    df = pd.DataFrame(rows)
    df["date"] = pd.Timestamp(target_date)

    numeric_cols = [c for c in df.columns if c not in ("code", "name", "date")]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    return df


def _fetch_tpex_institutional(target_date: date) -> pd.DataFrame:
    date_str = f"{target_date.year - 1911}/{target_date.month:02d}/{target_date.day:02d}"
    params = {"l": "zh-tw", "se": "EW", "t": "D", "d": date_str, "s": "0,asc"}
    resp = requests.get(TPEX_INST_URL, params=params, headers=HEADERS, timeout=30)
    data = resp.json()

    # 新格式：tables[0]["data"]；舊格式：aaData
    if "tables" in data:
        tables = data.get("tables", [])
        if not tables or not tables[0].get("data"):
            return pd.DataFrame()
        rows = tables[0]["data"]
    else:
        if not data.get("iTotalRecords"):
            return pd.DataFrame()
        rows = data.get("aaData", [])

    if not rows:
        return pd.DataFrame()

    records = []
    for row in rows:
        clean = [str(c).replace(",", "").strip() if c is not None else "0" for c in row]
        n = len(clean)
        record = {
            "code": clean[0],
            "name": clean[1],
            "foreign_buy":            clean[2]  if n > 2  else "0",
            "foreign_sell":           clean[3]  if n > 3  else "0",
            "foreign_net":            clean[4]  if n > 4  else "0",
            "investment_trust_buy":   clean[5]  if n > 5  else "0",
            "investment_trust_sell":  clean[6]  if n > 6  else "0",
            "investment_trust_net":   clean[7]  if n > 7  else "0",
            "dealer_net":             clean[16] if n > 16 else (clean[8] if n > 8 else "0"),
            "total_net":              clean[23] if n > 23 else (clean[11] if n > 11 else "0"),
        }
        records.append(record)

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
    抓取全市場三大法人資料並寫入各股 Parquet。
    回傳 {stock_code: success}。
    """
    if target_date is None:
        target_date = date.today()

    results: dict[str, bool] = {}

    try:
        twse_df = _fetch_twse_institutional(target_date)
        logger.info("TWSE 三大法人: %d 支", len(twse_df))
        time.sleep(1)
    except Exception as e:
        logger.error("TWSE 三大法人抓取失敗: %s", e)
        twse_df = pd.DataFrame()

    try:
        tpex_df = _fetch_tpex_institutional(target_date)
        logger.info("TPEX 三大法人: %d 支", len(tpex_df))
    except Exception as e:
        logger.error("TPEX 三大法人抓取失敗: %s", e)
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
                logger.error("寫入 %s 三大法人失敗: %s", code, e)
                results[code] = False

    return results


def fetch_history(target_date: date, market: str = "TWSE") -> pd.DataFrame:
    """Bootstrap 用：抓取單日歷史三大法人資料，回傳 DataFrame。"""
    if market == "TWSE":
        return _fetch_twse_institutional(target_date)
    return _fetch_tpex_institutional(target_date)
