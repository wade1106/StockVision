import logging
import os
import pickle
from pathlib import Path

import numpy as np
import pandas as pd
import shap

logger = logging.getLogger(__name__)

MODEL_PATH = Path("models/lgbm_model.pkl")

CONFIDENCE_THRESHOLD = float(os.environ.get("CONFIDENCE_THRESHOLD", "0.70"))
BULLISH_MAX = 10
BEARISH_MAX = 5
FALLBACK_BULLISH_N = 5
FALLBACK_BEARISH_N = 3


def _load_model() -> tuple:
    if not MODEL_PATH.exists():
        raise FileNotFoundError(
            f"模型檔案不存在：{MODEL_PATH}，請先執行 scripts/train.py"
        )
    with open(MODEL_PATH, "rb") as f:
        payload = pickle.load(f)
    return payload["model"], payload["feature_cols"]


def run(features: pd.DataFrame) -> pd.DataFrame:
    """
    features: index=code，欄位包含特徵與 name/ticker 等資訊
    回傳含 prob、shap_top3 欄位的 DataFrame
    """
    model, feature_cols = _load_model()

    available_cols = [c for c in feature_cols if c in features.columns]
    missing = set(feature_cols) - set(available_cols)
    if missing:
        logger.warning("特徵缺漏 %d 欄：%s", len(missing), list(missing)[:5])

    X = features[available_cols].astype(float)

    # 推理
    proba = model.predict_proba(X)[:, 1]
    result = features[["name", "ticker"]].copy() if "name" in features.columns else features.copy()
    result["prob"] = proba

    # SHAP 只對進入門檻的股票計算（節省時間）
    candidate_mask = (result["prob"] >= CONFIDENCE_THRESHOLD) | \
                     (result["prob"] <= (1 - CONFIDENCE_THRESHOLD))
    if candidate_mask.sum() == 0:
        candidate_mask = pd.Series(True, index=result.index)

    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(X[candidate_mask])

    # shap_values 可能是 list（二元分類取正類）
    if isinstance(shap_values, list):
        sv = shap_values[1]
    else:
        sv = shap_values

    shap_df = pd.DataFrame(sv, index=X[candidate_mask].index, columns=available_cols)

    def top3_features(row: pd.Series) -> list[dict]:
        abs_vals = row.abs().nlargest(3)
        return [
            {"feature": feat, "direction": "positive" if row[feat] > 0 else "negative"}
            for feat in abs_vals.index
        ]

    result.loc[candidate_mask, "shap_top3"] = shap_df.apply(top3_features, axis=1)
    result["shap_top3"] = result["shap_top3"].where(result["shap_top3"].notna(), None)

    return result


def select(result: pd.DataFrame) -> dict:
    """
    根據信心度門檻篩選看好/看淡清單，含 fallback 邏輯。
    回傳 {"bullish": [...], "bearish": [...], "fallback": bool, "max_prob": float}
    """
    threshold = CONFIDENCE_THRESHOLD
    sorted_desc = result.sort_values("prob", ascending=False)
    sorted_asc = result.sort_values("prob", ascending=True)

    bullish = sorted_desc[sorted_desc["prob"] >= threshold].head(BULLISH_MAX)
    bearish = sorted_asc[sorted_asc["prob"] <= (1 - threshold)].head(BEARISH_MAX)

    fallback = False
    max_bullish_prob = float(sorted_desc["prob"].iloc[0]) if len(sorted_desc) > 0 else 0.0
    max_bearish_conf = float(1 - sorted_asc["prob"].iloc[0]) if len(sorted_asc) > 0 else 0.0

    if len(bullish) == 0:
        bullish = sorted_desc.head(FALLBACK_BULLISH_N)
        fallback = True
        logger.warning("看好清單為空，fallback Top %d（最高信心度 %.1f%%）",
                       FALLBACK_BULLISH_N, max_bullish_prob * 100)

    if len(bearish) == 0:
        bearish = sorted_asc.head(FALLBACK_BEARISH_N)
        fallback = True
        logger.warning("看淡清單為空，fallback Top %d（最高看淡信心度 %.1f%%）",
                       FALLBACK_BEARISH_N, max_bearish_conf * 100)

    return {
        "bullish": bullish.to_dict("records"),
        "bearish": bearish.to_dict("records"),
        "fallback": fallback,
        "max_bullish_prob": max_bullish_prob,
        "max_bearish_conf": max_bearish_conf,
        "threshold": threshold,
    }