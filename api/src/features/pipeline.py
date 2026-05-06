import logging
from datetime import date
from pathlib import Path

import pandas as pd

from src.features import institutional_features, technical

logger = logging.getLogger(__name__)

OHLCV_DIR = Path("data/ohlcv")
FEATURES_DIR = Path("data/features")
MIN_HISTORY_DAYS = 60


def build(stock_df: pd.DataFrame, target_date: date | None = None) -> pd.DataFrame:
    """
    stock_df: 欄位含 code, name, ticker 的全市場股票清單
    target_date: 要計算特徵的日期，預設今日

    回傳每列一支股票的特徵 DataFrame，並存至 data/features/<YYYY-MM-DD>.parquet
    """
    if target_date is None:
        target_date = date.today()

    ts = pd.Timestamp(target_date)
    FEATURES_DIR.mkdir(parents=True, exist_ok=True)
    out_path = FEATURES_DIR / f"{target_date}.parquet"

    rows = []
    skipped = 0

    for _, stock in stock_df.iterrows():
        code = str(stock["code"])
        ticker = str(stock["ticker"])
        name = str(stock["name"])

        ohlcv_path = OHLCV_DIR / f"{ticker}.parquet"
        if not ohlcv_path.exists():
            skipped += 1
            continue

        ohlcv = pd.read_parquet(ohlcv_path)
        ohlcv.index = pd.to_datetime(ohlcv.index)
        ohlcv = ohlcv[ohlcv.index <= ts].sort_index()

        if len(ohlcv) < MIN_HISTORY_DAYS:
            skipped += 1
            continue

        try:
            tech = technical.compute(ohlcv)
            latest_tech = tech.iloc[-1].to_dict()
        except Exception as e:
            logger.warning("%s 技術指標計算失敗: %s", ticker, e)
            skipped += 1
            continue

        inst = institutional_features.compute(code, ts)

        row = {"code": code, "name": name, "ticker": ticker, "date": ts}
        row.update(latest_tech)
        row.update(inst)
        rows.append(row)

    if not rows:
        logger.error("無任何股票通過特徵工程篩選")
        return pd.DataFrame()

    result = pd.DataFrame(rows).set_index("code")

    # 移除 OHLCV 原始欄位，只保留特徵
    drop_cols = [c for c in ["open", "high", "low", "close", "volume"] if c in result.columns]
    result.drop(columns=drop_cols, inplace=True)

    result.to_parquet(out_path)
    logger.info("特徵快照已存至 %s，共 %d 支（跳過 %d 支）", out_path, len(result), skipped)
    return result
