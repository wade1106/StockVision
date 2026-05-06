import logging

import numpy as np
import pandas as pd

try:
    import talib
    _TALIB = True
except ImportError:
    _TALIB = False
    logging.getLogger(__name__).warning("ta-lib 未安裝，改用 pandas 計算技術指標")

logger = logging.getLogger(__name__)


def _ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def compute(df: pd.DataFrame) -> pd.DataFrame:
    """
    輸入單支股票的 OHLCV DataFrame（index=date，欄位含 open/high/low/close/volume）。
    回傳加上技術指標欄位的 DataFrame。
    歷史不足 60 日者，部分指標為 NaN，由 caller 決定是否過濾。
    """
    out = df.copy()
    close = df["close"].astype(float)
    high = df["high"].astype(float)
    low = df["low"].astype(float)
    volume = df["volume"].astype(float)

    if _TALIB:
        out["ma5"] = talib.SMA(close, timeperiod=5)
        out["ma20"] = talib.SMA(close, timeperiod=20)
        out["ma60"] = talib.SMA(close, timeperiod=60)
        out["rsi_14"] = talib.RSI(close, timeperiod=14)
        macd, macd_signal, _ = talib.MACD(close, fastperiod=12, slowperiod=26, signalperiod=9)
        out["macd"] = macd
        out["macd_signal"] = macd_signal
        out["macd_hist"] = macd - macd_signal
        out["slowk"], out["slowd"] = talib.STOCH(high, low, close,
                                                  fastk_period=9, slowk_period=3, slowd_period=3)
        upper, mid, lower = talib.BBANDS(close, timeperiod=20)
        out["bb_upper"] = upper
        out["bb_lower"] = lower
        out["volume_ma5"] = talib.SMA(volume, timeperiod=5)
    else:
        out["ma5"] = close.rolling(5).mean()
        out["ma20"] = close.rolling(20).mean()
        out["ma60"] = close.rolling(60).mean()

        delta = close.diff()
        gain = delta.clip(lower=0).rolling(14).mean()
        loss = (-delta.clip(upper=0)).rolling(14).mean()
        rs = gain / loss.replace(0, np.nan)
        out["rsi_14"] = 100 - (100 / (1 + rs))

        ema12 = _ema(close, 12)
        ema26 = _ema(close, 26)
        out["macd"] = ema12 - ema26
        out["macd_signal"] = _ema(out["macd"], 9)
        out["macd_hist"] = out["macd"] - out["macd_signal"]

        low_min = low.rolling(9).min()
        high_max = high.rolling(9).max()
        raw_k = 100 * (close - low_min) / (high_max - low_min + 1e-9)
        out["slowk"] = raw_k.rolling(3).mean()
        out["slowd"] = out["slowk"].rolling(3).mean()

        ma20 = close.rolling(20).mean()
        std20 = close.rolling(20).std()
        out["bb_upper"] = ma20 + 2 * std20
        out["bb_lower"] = ma20 - 2 * std20

        out["volume_ma5"] = volume.rolling(5).mean()

    # 衍生特徵
    out["price_vs_ma20"] = (close / out["ma20"]) - 1
    out["volume_ratio"] = volume / out["volume_ma5"].replace(0, np.nan)

    return out
