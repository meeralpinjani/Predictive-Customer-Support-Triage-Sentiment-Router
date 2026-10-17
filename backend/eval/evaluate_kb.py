"""Knowledge-base threshold tuning (VALIDATION split) and accuracy (TEST split) - playbook 7.5, 13.1.

    python -m eval.evaluate_kb

Auto threshold: the lowest similarity at which every validation auto-answer is the right
article (precision matters more than recall). Suggest threshold: best F1 for "the right
article is shown to the agent".
"""
import numpy as np
import pandas as pd

from eval.common import DATA, kb_for, set_mode


def _scores(df: pd.DataFrame, mode: str) -> pd.DataFrame:
    set_mode(mode)
    kb = kb_for(mode)
    rows = []
    for text, expected in zip(df["text"], df["expected_article"]):
        m = kb.match(text)
        rows.append({"conf": m.confidence, "correct": m.article_id == expected, "in_scope": expected != "none"})
    return pd.DataFrame(rows)


def tune(val: pd.DataFrame) -> tuple[float, float]:
    grid = np.round(np.arange(0.20, 0.96, 0.01), 2)
    auto = next((t for t in grid if val.loc[val.conf >= t, "correct"].all() and (val.conf >= t).any()), 0.95)
    best_f1, suggest = -1.0, 0.5
    for t in grid:
        shown = val.conf >= t
        tp = (shown & val.correct).sum()
        p = tp / shown.sum() if shown.sum() else 0.0
        r = tp / val.in_scope.sum() if val.in_scope.sum() else 0.0
        f1 = 2 * p * r / (p + r) if p + r else 0.0
        if f1 > best_f1:
            best_f1, suggest = f1, float(t)
    # Margin over the tightest passing value guards against a handful of validation rows.
    return round(min(suggest, auto), 2), round(min(float(auto) + 0.02, 0.95), 2)


def metrics(df: pd.DataFrame, suggest: float, auto: float) -> dict:
    a = df.conf >= auto
    s = df.conf >= suggest
    return {
        "auto_answers": int(a.sum()),
        "auto_accuracy": round(float(df.loc[a, "correct"].mean()), 3) if a.any() else None,
        "auto_coverage": round(float((a & df.correct).sum() / df.in_scope.sum()), 3),
        "out_of_scope_auto": int((a & ~df.in_scope).sum()),
        "suggest_precision": round(float(df.loc[s, "correct"].mean()), 3) if s.any() else None,
        "suggest_recall": round(float((s & df.correct).sum() / df.in_scope.sum()), 3),
        "top1_accuracy_in_scope": round(float(df.loc[df.in_scope, "correct"].mean()), 3),
    }


def evaluate(mode: str) -> dict:
    data = pd.read_csv(DATA / "kb_eval.csv")
    val = _scores(data[data.split == "val"], mode)
    test = _scores(data[data.split == "test"], mode)
    suggest, auto = tune(val)
    return {
        "matcher": "minilm" if mode == "hf" else "tfidf",
        "suggest_threshold": suggest,
        "auto_threshold": auto,
        "validation": metrics(val, suggest, auto),
        "test": metrics(test, suggest, auto),
        "n_val": int(len(val)),
        "n_test": int(len(test)),
    }


if __name__ == "__main__":
    import json
    for mode in ("rules", "hf"):
        print(json.dumps(evaluate(mode), indent=2))
