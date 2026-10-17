import csv
from pathlib import Path
import pandas as pd
from app.nlp.analyzer import analyse


def evaluate_nlp(csv_path: Path | None = None) -> dict:
    if csv_path is None:
        csv_path = Path(__file__).resolve().parent.parent / "data" / "tickets_labelled.csv"

    df = pd.read_csv(csv_path)

    # Ground truth
    df["true_urgent"] = (df["urgency_label"] == "high") | (df["critical"] == 1)
    df["true_frustrated"] = (df["frustration_label"] == "high")

    # Run predictions
    pred_urgent = []
    pred_frustrated = []
    analyses = []

    for text in df["text"]:
        a = analyse(str(text))
        analyses.append(a)
        is_urg = bool(a.critical_flags) or (a.urgency >= 0.65)
        is_frust = a.frustration >= 0.75
        pred_urgent.append(is_urg)
        pred_frustrated.append(is_frust)

    df["pred_urgent"] = pred_urgent
    df["pred_frustrated"] = pred_frustrated

    # Metrics computation function
    def compute_prf(tp, fp, fn, tn):
        prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * prec * rec) / (prec + rec) if (prec + rec) > 0 else 0.0
        return round(prec, 4), round(rec, 4), round(f1, 4)

    # 1. Urgency evaluation
    tp_u = int(((df["pred_urgent"] == True) & (df["true_urgent"] == True)).sum())
    fp_u = int(((df["pred_urgent"] == True) & (df["true_urgent"] == False)).sum())
    fn_u = int(((df["pred_urgent"] == False) & (df["true_urgent"] == True)).sum())
    tn_u = int(((df["pred_urgent"] == False) & (df["true_urgent"] == False)).sum())
    prec_u, rec_u, f1_u = compute_prf(tp_u, fp_u, fn_u, tn_u)

    # 2. Frustration evaluation (at 0.75 threshold)
    tp_f = int(((df["pred_frustrated"] == True) & (df["true_frustrated"] == True)).sum())
    fp_f = int(((df["pred_frustrated"] == True) & (df["true_frustrated"] == False)).sum())
    fn_f = int(((df["pred_frustrated"] == False) & (df["true_frustrated"] == True)).sum())
    tn_f = int(((df["pred_frustrated"] == False) & (df["true_frustrated"] == False)).sum())
    prec_f, rec_f, f1_f = compute_prf(tp_f, fp_f, fn_f, tn_f)

    # Save false negatives / mistakes
    mistakes = df[(df["pred_urgent"] != df["true_urgent"]) | (df["pred_frustrated"] != df["true_frustrated"])].copy()
    mistakes_path = Path(__file__).resolve().parent / "nlp_mistakes.csv"
    mistakes.to_csv(mistakes_path, index=False)

    return {
        "total_evaluated": len(df),
        "urgency": {
            "precision": prec_u,
            "recall": rec_u,
            "f1": f1_u,
            "confusion_matrix": {"TP": tp_u, "FP": fp_u, "FN": fn_u, "TN": tn_u},
            "missed_urgent_count": fn_u,
        },
        "frustration": {
            "precision": prec_f,
            "recall": rec_f,
            "f1": f1_f,
            "confusion_matrix": {"TP": tp_f, "FP": fp_f, "FN": fn_f, "TN": tn_f},
        },
        "mistakes_file": str(mistakes_path),
        "false_negatives": df[df["pred_urgent"] == False & (df["true_urgent"] == True)][["text"]].to_dict(orient="records"),
    }


if __name__ == "__main__":
    results = evaluate_nlp()
    print("=" * 60)
    print("NLP EVALUATION METRICS (Rule-Based Triage Baseline)")
    print("=" * 60)
    print(f"Total labelled tickets evaluated: {results['total_evaluated']}")
    print("\n[URGENCY & CRITICAL DETECTION]")
    u = results["urgency"]
    print(f"  - Precision: {u['precision']:.3f}")
    print(f"  - Recall:    {u['recall']:.3f} (Target: >= 0.85)")
    print(f"  - F1 Score:  {u['f1']:.3f}")
    print(f"  - Confusion Matrix: TP={u['confusion_matrix']['TP']}, FP={u['confusion_matrix']['FP']}, FN={u['confusion_matrix']['FN']}, TN={u['confusion_matrix']['TN']}")
    print(f"  - Missed urgent tickets (False Negatives): {u['missed_urgent_count']}")

    print("\n[FRUSTRATION DETECTION (Threshold >= 0.75)]")
    f = results["frustration"]
    print(f"  - Precision: {f['precision']:.3f}")
    print(f"  - Recall:    {f['recall']:.3f}")
    print(f"  - F1 Score:  {f['f1']:.3f}")
    print(f"  - Confusion Matrix: TP={f['confusion_matrix']['TP']}, FP={f['confusion_matrix']['FP']}, FN={f['confusion_matrix']['FN']}, TN={f['confusion_matrix']['TN']}")

    print(f"\nMistakes exported for review: {results['mistakes_file']}")
    print("=" * 60)
