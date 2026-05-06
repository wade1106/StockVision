"""
模型訓練腳本：基於歷史特徵資料訓練 LightGBM 二元分類模型。
執行方式：uv run python scripts/train.py
目標變數：個股隔日超額報酬 > 0（個股漲幅 - 加權指數漲幅）
"""
import logging
import pickle
import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import TimeSeriesSplit

sys.path.insert(0, str(Path(__file__).parent.parent))

import lightgbm as lgb
from dotenv import load_dotenv

load_dotenv()

from src.collect.stock_list import get_all_stocks
from src.features import institutional_features, technical

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)

OHLCV_DIR = Path("data/ohlcv")
MODEL_PATH = Path("models/lgbm_model.pkl")
TAIEX_TICKER = "^TWII"
MIN_HISTORY_DAYS = 60


def load_taiex_returns() -> pd.Series:
    path = OHLCV_DIR / f"{TAIEX_TICKER}.parquet"
    if not path.exists():
        logger.info("下載加權指數歷史資料...")
        import yfinance as yf
        start = date.today() - timedelta(days=365 * 6)
        raw = yf.download(TAIEX_TICKER, start=str(start), progress=False, auto_adjust=True)
        raw.index = pd.to_datetime(raw.index).normalize()
        if isinstance(raw.columns, pd.MultiIndex):
            raw.columns = raw.columns.get_level_values(0)
        raw.columns = [c.lower() for c in raw.columns]
        path.parent.mkdir(parents=True, exist_ok=True)
        raw.to_parquet(path)

    df = pd.read_parquet(path)
    return df["close"].pct_change()


def build_training_data(stocks: pd.DataFrame, taiex_ret: pd.Series) -> pd.DataFrame:
    all_rows = []

    for _, stock in stocks.iterrows():
        ticker = str(stock["ticker"])
        code = str(stock["code"])

        ohlcv_path = OHLCV_DIR / f"{ticker}.parquet"
        if not ohlcv_path.exists():
            continue

        ohlcv = pd.read_parquet(ohlcv_path)
        ohlcv.index = pd.to_datetime(ohlcv.index)
        ohlcv.sort_index(inplace=True)

        if len(ohlcv) < MIN_HISTORY_DAYS + 5:
            continue

        try:
            tech_df = technical.compute(ohlcv)
        except Exception as e:
            logger.debug("技術指標失敗 %s: %s", ticker, e)
            continue

        stock_ret = ohlcv["close"].pct_change()

        for i in range(MIN_HISTORY_DAYS, len(ohlcv) - 1):
            today = ohlcv.index[i]
            next_day = ohlcv.index[i + 1]

            next_stock_ret = stock_ret.iloc[i + 1]
            next_taiex_ret = taiex_ret.get(next_day, np.nan)

            if pd.isna(next_stock_ret) or pd.isna(next_taiex_ret):
                continue

            label = int((next_stock_ret - next_taiex_ret) > 0)

            tech_row = tech_df.iloc[i].to_dict()
            inst_feats = institutional_features.compute(code, today)

            row = {"code": code, "date": today, "label": label}
            row.update(tech_row)
            row.update(inst_feats)
            all_rows.append(row)

    df = pd.DataFrame(all_rows)
    logger.info("訓練資料：%d 筆，%d 欄", len(df), df.shape[1])
    return df


def train(df: pd.DataFrame) -> tuple[lgb.LGBMClassifier, list[str]]:
    drop_cols = {"code", "date", "label", "open", "high", "low", "close", "volume"}
    feature_cols = [c for c in df.columns if c not in drop_cols]

    X = df[feature_cols].astype(float)
    y = df["label"]

    tscv = TimeSeriesSplit(n_splits=5)
    auc_scores = []

    for fold, (train_idx, val_idx) in enumerate(tscv.split(X)):
        m = lgb.LGBMClassifier(
            n_estimators=500,
            learning_rate=0.05,
            num_leaves=31,
            min_child_samples=50,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=42,
            verbose=-1,
        )
        m.fit(
            X.iloc[train_idx], y.iloc[train_idx],
            eval_set=[(X.iloc[val_idx], y.iloc[val_idx])],
            callbacks=[lgb.early_stopping(50, verbose=False), lgb.log_evaluation(-1)],
        )
        auc = roc_auc_score(y.iloc[val_idx], m.predict_proba(X.iloc[val_idx])[:, 1])
        auc_scores.append(auc)
        logger.info("Fold %d AUC: %.4f", fold + 1, auc)

    mean_auc = float(np.mean(auc_scores))
    logger.info("平均驗證 AUC: %.4f", mean_auc)

    if mean_auc < 0.52:
        logger.warning("AUC %.4f 未達 0.52，預測力偏弱，建議檢查特徵", mean_auc)

    # 全量資料訓練最終模型
    final = lgb.LGBMClassifier(
        n_estimators=500, learning_rate=0.05, num_leaves=31,
        min_child_samples=50, subsample=0.8, colsample_bytree=0.8,
        random_state=42, verbose=-1,
    )
    final.fit(X, y)
    return final, feature_cols


def main() -> None:
    logger.info("開始訓練模型...")

    stocks = get_all_stocks()
    taiex_ret = load_taiex_returns()
    df = build_training_data(stocks, taiex_ret)

    if len(df) < 1000:
        logger.error("訓練資料不足（%d 筆），請先執行 bootstrap.py", len(df))
        sys.exit(1)

    model, feature_cols = train(df)

    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(MODEL_PATH, "wb") as f:
        pickle.dump({"model": model, "feature_cols": feature_cols}, f)

    logger.info("模型已儲存至 %s", MODEL_PATH)


if __name__ == "__main__":
    main()
