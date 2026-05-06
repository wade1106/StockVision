"""
每日自動化 Pipeline 入口。
GitHub Actions 於 17:30 TST (09:30 UTC) 每日觸發。
執行方式：uv run python scripts/daily_run.py [--date YYYY-MM-DD]
"""
import argparse
import logging
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()

import pandas as pd

from src.collect import institutional, margin, ohlcv
from src.collect.stock_list import get_all_stocks
from src.features import pipeline
from src.model import predict
from src.notify import line_bot
from src.report import generator, markdown_writer, prediction_store

parser = argparse.ArgumentParser()
parser.add_argument("--date", type=date.fromisoformat, default=date.today(), help="執行日期 YYYY-MM-DD")
args, _ = parser.parse_known_args()
TODAY = args.date
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_DIR / f"daily_{TODAY}.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


def is_trading_day(stocks_df: pd.DataFrame, tickers: list[str]) -> bool:
    """簡易判斷：今日是否有 OHLCV 新資料（取前 10 支樣本確認）。"""
    sample = tickers[:10]
    has_data = 0
    for ticker in sample:
        path = Path(f"data/ohlcv/{ticker}.parquet")
        if path.exists():
            df = pd.read_parquet(path)
            if not df.empty:
                last_date = pd.to_datetime(df.index).max().date()
                if last_date == TODAY:
                    has_data += 1
    return has_data >= 3


def main() -> None:
    logger.info("===== StockVision 每日 Pipeline 開始：%s =====", TODAY)

    # 取得股票清單
    try:
        stocks = get_all_stocks()
        tickers = stocks["ticker"].tolist()
        logger.info("股票清單：%d 支", len(tickers))
    except Exception as e:
        logger.error("無法取得股票清單: %s", e)
        sys.exit(1)

    # Phase 0: 批次下載近期資料（GitHub Actions 無本機快取時使用）
    logger.info("--- Phase 0: 暖機下載近期資料 ---")
    try:
        ohlcv.fetch_recent(tickers, days=200)
    except Exception as e:
        logger.warning("批次下載失敗（繼續執行）: %s", e)

    # Phase 1: 資料收集
    logger.info("--- Phase 1: 資料收集 ---")
    try:
        ohlcv_results = ohlcv.fetch_today(tickers, TODAY)
        success = sum(v for v in ohlcv_results.values())
        logger.info("OHLCV 完成：%d/%d 支成功", success, len(tickers))
    except Exception as e:
        logger.error("OHLCV 收集失敗: %s", e)
        sys.exit(1)

    # 非交易日偵測
    if not is_trading_day(stocks, tickers):
        logger.info("今日無交易資料，可能為假日或停市，Pipeline 結束。")
        sys.exit(0)

    try:
        institutional.fetch_today(TODAY)
    except Exception as e:
        logger.warning("三大法人收集失敗（繼續執行）: %s", e)

    try:
        margin.fetch_today(TODAY)
    except Exception as e:
        logger.warning("融資融券收集失敗（繼續執行）: %s", e)

    # Phase 2: 特徵工程
    logger.info("--- Phase 2: 特徵工程 ---")
    try:
        features = pipeline.build(stocks, TODAY)
        if features.empty:
            logger.error("特徵快照為空，Pipeline 中止")
            sys.exit(1)
    except Exception as e:
        logger.error("特徵工程失敗: %s", e)
        sys.exit(1)

    # Phase 3: 模型推理
    logger.info("--- Phase 3: 模型推理 ---")
    try:
        result = predict.run(features)
        selection = predict.select(result)
        logger.info(
            "看好 %d 支，看淡 %d 支，fallback=%s",
            len(selection["bullish"]), len(selection["bearish"]), selection["fallback"],
        )
    except FileNotFoundError as e:
        logger.error("%s", e)
        sys.exit(1)
    except Exception as e:
        logger.error("模型推理失敗: %s", e)
        sys.exit(1)

    # Phase 4: 報告生成
    logger.info("--- Phase 4: 報告生成 ---")
    try:
        reasons = generator.generate(selection, TODAY)
        report_path = markdown_writer.write(selection, reasons, TODAY)
        logger.info("報告已存至 %s", report_path)
    except Exception as e:
        logger.error("報告生成失敗: %s", e)
        sys.exit(1)

    # Phase 5: 儲存預測快照（供前端比對用）
    try:
        prediction_store.save(selection, TODAY)
    except Exception as e:
        logger.warning("預測快照儲存失敗（繼續執行）: %s", e)

    # Phase 6: LINE 推播
    logger.info("--- Phase 6: LINE 推播 ---")
    line_bot.push(selection, reasons, TODAY)

    logger.info("===== Pipeline 完成 =====")


if __name__ == "__main__":
    main()