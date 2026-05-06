"""
一次性初始化腳本：抓取全市場 5 年歷史資料。
執行方式：python scripts/bootstrap.py
"""
import logging
import sys
import time
from datetime import date, timedelta
from pathlib import Path

from tqdm import tqdm

# 確保 src 可被 import
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.collect import institutional, margin, ohlcv
from src.collect.stock_list import get_all_stocks

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs/bootstrap.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)

Path("logs").mkdir(exist_ok=True)

YEARS = 5
ERROR_LOG = Path("logs/bootstrap_errors.log")


def trading_dates(start: date, end: date) -> list[date]:
    """回傳 start~end 之間的所有工作日（週一到週五）。"""
    days = []
    cur = start
    while cur <= end:
        if cur.weekday() < 5:
            days.append(cur)
        cur += timedelta(days=1)
    return days


def bootstrap_ohlcv(tickers: list[str]) -> None:
    logger.info("=== Phase 1: 抓取 OHLCV 歷史資料（%d 支）===", len(tickers))
    errors = []

    for ticker in tqdm(tickers, desc="OHLCV"):
        try:
            import yfinance as yf
            from pathlib import Path as P
            import pandas as pd

            out_path = Path(f"data/ohlcv/{ticker}.parquet")
            out_path.parent.mkdir(parents=True, exist_ok=True)

            if out_path.exists():
                existing = pd.read_parquet(out_path)
                if len(existing) > 200:
                    continue  # 已有足夠資料，跳過

            end_date = date.today()
            start_date = end_date - timedelta(days=365 * YEARS + 30)

            raw = yf.download(ticker, start=str(start_date), end=str(end_date),
                              progress=False, auto_adjust=True)
            if raw.empty:
                errors.append(f"OHLCV no data: {ticker}")
                continue

            raw.index = pd.to_datetime(raw.index).normalize()
            if isinstance(raw.columns, pd.MultiIndex):
                raw.columns = raw.columns.get_level_values(0)
            raw.columns = [c.lower() for c in raw.columns]
            raw.to_parquet(out_path)

        except Exception as e:
            errors.append(f"OHLCV error {ticker}: {e}")
            logger.debug("OHLCV 失敗 %s: %s", ticker, e)

        time.sleep(0.05)

    logger.info("OHLCV 完成，失敗 %d 支", len(errors))
    if errors:
        ERROR_LOG.write_text("\n".join(errors), encoding="utf-8")


def bootstrap_institutional(dates: list[date]) -> None:
    logger.info("=== Phase 2: 抓取三大法人歷史資料（%d 個交易日）===", len(dates))

    for d in tqdm(dates, desc="三大法人"):
        try:
            twse_df = institutional.fetch_history(d, market="TWSE")
            if not twse_df.empty:
                for _, row in twse_df.iterrows():
                    code = str(row["code"]).strip()
                    institutional._append_to_parquet(code, row)
            time.sleep(0.5)

            tpex_df = institutional.fetch_history(d, market="TPEX")
            if not tpex_df.empty:
                for _, row in tpex_df.iterrows():
                    code = str(row["code"]).strip()
                    institutional._append_to_parquet(code, row)
            time.sleep(0.5)

        except Exception as e:
            logger.warning("三大法人 %s 失敗: %s", d, e)


def bootstrap_margin(dates: list[date]) -> None:
    logger.info("=== Phase 3: 抓取融資融券歷史資料（%d 個交易日）===", len(dates))

    for d in tqdm(dates, desc="融資融券"):
        try:
            twse_df = margin.fetch_history(d, market="TWSE")
            if not twse_df.empty:
                for _, row in twse_df.iterrows():
                    code = str(row["code"]).strip()
                    margin._append_to_parquet(code, row)
            time.sleep(0.5)

            tpex_df = margin.fetch_history(d, market="TPEX")
            if not tpex_df.empty:
                for _, row in tpex_df.iterrows():
                    code = str(row["code"]).strip()
                    margin._append_to_parquet(code, row)
            time.sleep(0.5)

        except Exception as e:
            logger.warning("融資融券 %s 失敗: %s", d, e)


def main() -> None:
    logger.info("Bootstrap 開始，抓取近 %d 年歷史資料", YEARS)

    # 取得股票清單
    logger.info("取得全市場股票清單...")
    stocks = get_all_stocks()
    tickers = stocks["ticker"].tolist()
    logger.info("共 %d 支股票", len(tickers))

    # Phase 1: OHLCV
    bootstrap_ohlcv(tickers)

    # Phase 2 & 3: 籌碼與融資券（按日爬取，有 rate limit）
    end_date = date.today()
    start_date = end_date - timedelta(days=365 * YEARS + 30)
    dates = trading_dates(start_date, end_date)

    bootstrap_institutional(dates)
    bootstrap_margin(dates)

    logger.info("Bootstrap 完成！接下來執行 python scripts/train.py 訓練模型。")


if __name__ == "__main__":
    main()
