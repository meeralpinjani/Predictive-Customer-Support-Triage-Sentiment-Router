"""Fit the frustration weights on the TRAIN split (playbook 9.5) and save them.

    python -m eval.train_frustration

A logistic regression over the four interpretable signals (neg, anger, style, churn) predicts
"high frustration". Its coefficients become the runtime formula, one set per NLP mode.
The test split is never touched here.
"""
import json

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupKFold, cross_val_predict

from app.nlp import frustration_model
from app.nlp.frustration_model import WEIGHTS_PATH, features
from eval.common import MODES, analyse_all, labelled


def fit(mode: str) -> dict:
    df = labelled("train")
    analyses, _ = analyse_all(df["text"].tolist(), mode)
    if mode == "hf" and analyses and analyses[0].mode != "hf":
        raise RuntimeError("HF models unavailable; cannot fit hf weights")
    feats = features(mode)
    X = np.array([[a.signals.get(k, 0.0) for k in feats] for a in analyses])
    y = (df["frustration_label"] == "high").astype(int).to_numpy()
    lr = LogisticRegression(C=1.0, class_weight="balanced", max_iter=1000)
    # Threshold from out-of-fold predictions, folds grouped by template (unseen sentences).
    # F2 weights recall double: missing an angry customer costs more than a false alarm.
    oof = cross_val_predict(lr, X, y, cv=GroupKFold(n_splits=5), groups=df["template_id"], method="predict_proba")[:, 1]
    best_t, best_f2 = 0.5, -1.0
    for t in np.round(np.arange(0.20, 0.81, 0.01), 2):
        pred = oof >= t
        tp = int((pred & (y == 1)).sum())
        p = tp / pred.sum() if pred.sum() else 0.0
        r = tp / (y == 1).sum()
        f2 = 5 * p * r / (4 * p + r) if p + r else 0.0
        if f2 > best_f2:
            best_t, best_f2 = float(t), f2
    lr.fit(X, y)
    return {
        "threshold": best_t,
        "cv_f2": round(float(best_f2), 4),
        "intercept": round(float(lr.intercept_[0]), 4),
        "coef": {k: round(float(c), 4) for k, c in zip(feats, lr.coef_[0])},
        "train_size": int(len(y)),
        "train_accuracy": round(float(lr.score(X, y)), 4),
    }


def main() -> dict:
    weights = {}
    # Fit on the raw signals: drop any previous fit so it cannot leak into the features.
    WEIGHTS_PATH.unlink(missing_ok=True)
    frustration_model.reload()
    for mode in MODES:
        try:
            weights[mode] = fit(mode)
            print(f"{mode}: {weights[mode]}")
        except Exception as exc:
            print(f"{mode}: skipped ({exc})")
    WEIGHTS_PATH.write_text(json.dumps(weights, indent=2), encoding="utf-8")
    frustration_model.reload()
    return weights


if __name__ == "__main__":
    main()
