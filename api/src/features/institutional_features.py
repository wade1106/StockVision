import logging
from pathlib import Path

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

INST_DIR = Path("data/institutional")
MARGIN_DIR = Path("data/margin")


def _consecutive_days(series: pd.Series) -> int:
    """計算最近連續正值或負值天數（正=連買，負=連賣）。"""
    if series.empty:
        return 0
    last = series.iloc[-1]
    if pd.isna(last) or last == 0:
        return 0
    sign = 1 if last > 0 else -1
    count = 0
    for val in reversed(series.tolist()):
        if pd.isna(val) or (val * sign) <= 0:
            break
        count += sign
    return count


def compute(code: str, target_date: pd.Timestamp) -> dict:
    """
    計算單支股票的籌碼衍生特徵，回傳 dict。
    若資料不存在，欄位以 NaN 填入。
    """
    features: dict = {}

    # 三大法人
    inst_path = INST_DIR / f"{code}.parquet"
    if inst_path.exists():
        inst = pd.read_parquet(inst_path)
        inst.index = pd.to_datetime(inst.index)
        inst = inst[inst.index <= target_date].sort_index()

        foreign_net = inst.get("foreign_net", pd.Series(dtype=float))
        it_net = inst.get("investment_trust_net", pd.Series(dtype=float))

        features["foreign_consecutive"] = _consecutive_days(foreign_net)
        features["it_consecutive"] = _consecutive_days(it_net)
        features["foreign_5d_net"] = foreign_net.tail(5).sum() if len(foreign_net) >= 5 else np.nan
        features["it_5d_net"] = it_net.tail(5).sum() if len(it_net) >= 5 else np.nan
        features["foreign_net_today"] = foreign_net.iloc[-1] if not foreign_net.empty else np.nan
        features["it_net_today"] = it_net.iloc[-1] if not it_net.empty else np.nan
    else:
        for col in ["foreign_consecutive", "it_consecutive",
                    "foreign_5d_net", "it_5d_net",
                    "foreign_net_today", "it_net_today"]:
            features[col] = np.nan

    # 融資融券
    margin_path = MARGIN_DIR / f"{code}.parquet"
    if margin_path.exists():
        mar = pd.read_parquet(margin_path)
        mar.index = pd.to_datetime(mar.index)
        mar = mar[mar.index <= target_date].sort_index()

        margin_bal = mar.get("margin_balance", pd.Series(dtype=float))
        short_bal = mar.get("short_balance", pd.Series(dtype=float))

        if len(margin_bal) >= 2:
            prev = margin_bal.iloc[-2]
            curr = margin_bal.iloc[-1]
            features["margin_change_pct"] = (curr - prev) / (abs(prev) + 1e-9)
        else:
            features["margin_change_pct"] = np.nan

        if len(short_bal) >= 2:
            prev = short_bal.iloc[-2]
            curr = short_bal.iloc[-1]
            features["short_change_pct"] = (curr - prev) / (abs(prev) + 1e-9)
        else:
            features["short_change_pct"] = np.nan

        features["margin_balance"] = margin_bal.iloc[-1] if not margin_bal.empty else np.nan
        features["short_balance"] = short_bal.iloc[-1] if not short_bal.empty else np.nan
    else:
        for col in ["margin_change_pct", "short_change_pct", "margin_balance", "short_balance"]:
            features[col] = np.nan

    return features
