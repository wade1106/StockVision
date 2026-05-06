import logging
from pathlib import Path
from datetime import date, timedelta

import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)

DATA_DIR = Path("data/ohlcv")


def _parquet_path(ticker: str) -> Path:
    return DATA_DIR / f"{ticker}.parquet"


def _load_existing(ticker: str) -> pd.DataFrame:
    path = _parquet_path(ticker)
    if path.exists():
        return pd.read_parquet(path)
    return pd.DataFrame()


def _last_stored_date(ticker: str) -> date | None:
    df = _load_existing(ticker)
    if df.empty:
        return None
    return pd.to_datetime(df.index).max().date()


def fetch_recent(tickers: list[str], days: int = 200) -> None:
    """
    批次下載近 days 天的 OHLCV，供 GitHub Actions 無狀態執行使用。
    資料已是最新的股票自動跳過。
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    end = date.today() + timedelta(days=1)
    start = date.today() - timedelta(days=days + 10)
    cutoff = date.today() - timedelta(days=5)

    to_download = []
    for t in tickers:
        last = _last_stored_date(t)
        if last is None or last < cutoff:
            to_download.append(t)

    if not to_download:
        logger.info("所有股票已有近期資料，跳過批次下載")
        return

    logger.info("批次下載 %d 支股票近 %d 天資料...", len(to_download), days)

    BATCH_SIZE = 200
    saved = 0

    for i in range(0, len(to_download), BATCH_SIZE):
        batch = to_download[i:i + BATCH_SIZE]
        try:
            raw = yf.download(batch, start=str(start), end=str(end),
                              progress=False, auto_adjust=True)
            if raw.empty:
                continue

            raw.index = pd.to_datetime(raw.index).normalize()

            for ticker in batch:
                try:
                    if len(batch) == 1:
                        df = raw.copy()
                        if isinstance(df.columns, pd.MultiIndex):
                            df.columns = df.columns.get_level_values(0)
                    elif isinstance(raw.columns, pd.MultiIndex):
                        level1 = raw.columns.get_level_values(1)
                        if ticker not in level1:
                            continue
                        df = raw.xs(ticker, axis=1, level=1).copy()
                    else:
                        continue

                    df.columns = [c.lower() for c in df.columns]
                    df = df.dropna(how="all")

                    if len(df) < 10:
                        continue

                    existing = _load_existing(ticker)
                    if not existing.empty:
                        df = pd.concat([existing, df])
                        df = df[~df.index.duplicated(keep="last")]
                        df.sort_index(inplace=True)

                    df.to_parquet(_parquet_path(ticker))
                    saved += 1
                except Exception as e:
                    logger.debug("儲存 %s 失敗: %s", ticker, e)

        except Exception as e:
            logger.warning("批次下載失敗 [%d:%d]: %s", i, i + BATCH_SIZE, e)

    logger.info("批次下載完成，成功儲存 %d 支", saved)


def fetch_today(tickers: list[str], target_date: date | None = None) -> dict[str, bool]:
    """
    抓取指定日期（預設今日）的 OHLCV，append 至各股 Parquet。
    回傳 {ticker: success} 的字典。
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if target_date is None:
        target_date = date.today()

    results: dict[str, bool] = {}
    failed = 0

    for ticker in tickers:
        try:
            last = _last_stored_date(ticker)
            if last and last >= target_date:
                logger.debug("%s 已有 %s 資料，跳過", ticker, target_date)
                results[ticker] = True
                continue

            start = target_date
            end = target_date + timedelta(days=1)
            raw = yf.download(ticker, start=str(start), end=str(end),
                              progress=False, auto_adjust=True)

            if raw.empty:
                logger.warning("%s 當日無資料", ticker)
                results[ticker] = False
                failed += 1
                continue

            raw.index = pd.to_datetime(raw.index).normalize()
            if isinstance(raw.columns, pd.MultiIndex):
                raw.columns = raw.columns.get_level_values(0)
            raw.columns = [c.lower() for c in raw.columns]

            existing = _load_existing(ticker)
            combined = pd.concat([existing, raw])
            combined = combined[~combined.index.duplicated(keep="last")]
            combined.sort_index(inplace=True)
            combined.to_parquet(_parquet_path(ticker))

            results[ticker] = True
            logger.debug("%s OK", ticker)

        except Exception as e:
            logger.error("%s 抓取失敗: %s", ticker, e)
            results[ticker] = False
            failed += 1

    total = len(tickers)
    fail_rate = failed / total if total > 0 else 0
    if fail_rate > 0.05:
        logger.warning("資料缺漏率 %.1f%% 超過 5%% 門檻（%d/%d 支失敗）",
                       fail_rate * 100, failed, total)

    return results
