"""Does CAPS really signal frustration? Train the frustration model three ways on the TRAIN split
and compare on the held-out TEST split:

    python -m eval.shouting_ablation

A: shouting = CAPS + exclamation marks (the original signal)
B: shouting = exclamation marks only (no CAPS)
C: no shouting signal at all
Also scores calm messages typed in capitals, which should NOT count as frustrated.
"""
import re

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupKFold, cross_val_predict

from eval.common import analyse_all, labelled, set_mode

CALM_CAPS = ["HELLO, I CANNOT FIND THE INVOICE FOR MARCH. COULD YOU SEND IT PLEASE? THANK YOU.",
             "HI TEAM, HOW DO I ADD A NEW USER TO OUR ACCOUNT? THANKS IN ADVANCE.",
             "GOOD MORNING. MY PASSWORD RESET EMAIL HAS NOT ARRIVED YET. KINDLY CHECK."]


def exclaim(text: str) -> float:
    return round(min(1.0, 0.4 * min(text.count("!"), 5) / 5 / 0.4 * 0.4 + (0.2 if "??" in text else 0.0)), 3)


def feats(a, text, variant, mode):
    base = ["neg_model", "anger_model", "neg_rules", "anger_rules"] if mode == "hf" else ["neg", "anger"]
    row = [a.signals.get(k, 0.0) for k in base] + [a.signals.get("churn", 0.0)]
    if variant == "A":
        row.append(a.signals.get("style", 0.0))
    elif variant == "B":
        row.append(min(1.0, min(text.count("!"), 5) / 5 + (0.2 if "??" in text else 0.0)))
    return row


def threshold(oof, y):
    best_t, best = 0.5, -1.0
    for t in np.round(np.arange(0.20, 0.81, 0.01), 2):
        pred = oof >= t
        tp = int((pred & (y == 1)).sum())
        p = tp / pred.sum() if pred.sum() else 0.0
        r = tp / (y == 1).sum()
        f2 = 5 * p * r / (4 * p + r) if p + r else 0.0
        if f2 > best:
            best_t, best = float(t), f2
    return best_t


def run(mode: str) -> None:
    set_mode(mode)
    tr, te = labelled("train"), labelled("test")
    a_tr, _ = analyse_all(tr["text"].tolist(), mode)
    a_te, _ = analyse_all(te["text"].tolist(), mode)
    a_calm, _ = analyse_all(CALM_CAPS, mode)
    ytr = (tr["frustration_label"] == "high").astype(int).to_numpy()
    yte = (te["frustration_label"] == "high").astype(int).to_numpy()
    for v in "ABC":
        Xtr = np.array([feats(a, t, v, mode) for a, t in zip(a_tr, tr["text"])])
        Xte = np.array([feats(a, t, v, mode) for a, t in zip(a_te, te["text"])])
        lr = LogisticRegression(C=1.0, class_weight="balanced", max_iter=1000)
        oof = cross_val_predict(lr, Xtr, ytr, cv=GroupKFold(n_splits=5), groups=tr["template_id"], method="predict_proba")[:, 1]
        th = threshold(oof, ytr)
        lr.fit(Xtr, ytr)
        pred = lr.predict_proba(Xte)[:, 1] >= th
        tp = int((pred & (yte == 1)).sum())
        p, r = (tp / pred.sum() if pred.sum() else 0.0), tp / (yte == 1).sum()
        calm = lr.predict_proba(np.array([feats(a, t, v, mode) for a, t in zip(a_calm, CALM_CAPS)]))[:, 1]
        print(f"[{mode}] {v}: test recall {r:.3f} precision {p:.3f} | threshold {th} | "
              f"calm CAPS messages scored {[round(float(x), 2) for x in calm]} -> flagged {int((calm >= th).sum())}/3")


if __name__ == "__main__":
    for m in ("rules", "hf"):
        run(m)
