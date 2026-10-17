"""Run the whole evaluation and write eval/report.json (served at /api/eval).

    python -m eval.run_all            # retrain frustration weights, tune KB, evaluate both modes
    python -m eval.run_all --no-train

Order matters: frustration weights and KB thresholds are fitted on train/validation data
first; every reported number comes from the held-out test data afterwards.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from app.config import settings
from app.nlp import frustration_model
from eval import evaluate_kb, evaluate_nlp, simulate, train_frustration
from eval.common import labelled, set_mode

REPORT = Path(__file__).resolve().parent / "report.json"


def main(train: bool = True) -> dict:
    hf_ok = set_mode("hf")
    modes = ["rules", "hf"] if hf_ok else ["rules"]
    if train:
        train_frustration.main()

    kb = {m: evaluate_kb.evaluate(m) for m in modes}
    # Apply the tuned KB thresholds before measuring the end-to-end pipeline.
    settings.kb_suggest_threshold = kb["rules"]["suggest_threshold"]
    settings.kb_auto_threshold = kb["rules"]["auto_threshold"]
    if "hf" in kb:
        settings.kb_suggest_threshold_hf = kb["hf"]["suggest_threshold"]
        settings.kb_auto_threshold_hf = kb["hf"]["auto_threshold"]

    nlp = {m: evaluate_nlp.evaluate(m) for m in modes}
    primary = "hf" if hf_ok else "rules"
    df = labelled()
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "primary_mode": primary,
        "dataset": {
            "tickets": int(len(df)),
            "train": int((df.split == "train").sum()),
            "test": int((df.split == "test").sum()),
            "hinglish": int((df.language == "hi-en").sum()),
            "split": "by template (test sentences unseen during tuning)",
        },
        "frustration_model": {m: frustration_model.describe(m) for m in modes},
        "nlp": nlp,
        "kb": kb,
        "simulation": simulate.run_simulation(primary),
        "targets": {
            "urgency_macro_f1": 0.75,
            "frustration_recall": 0.80,
            "escalation_precision": 0.80,
            "kb_auto_accuracy": 0.90,
            "latency_ms": 2000,
        },
    }
    REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-train", action="store_true")
    r = main(train=not ap.parse_args().no_train)
    for m, res in r["nlp"].items():
        print(f"[{m}] urgency F1 {res['urgency']['macro_f1']} | frustration P {res['frustration']['precision']} "
              f"R {res['frustration']['recall']} | escalation P {res['escalation']['precision']} "
              f"R {res['escalation']['recall']} | auto safe {res['auto_answer']['safe_precision']} "
              f"deflect {res['auto_answer']['deflection_rate']} | {res['latency_ms']['mean']} ms")
    for m, k in r["kb"].items():
        print(f"[kb {m}] suggest {k['suggest_threshold']} auto {k['auto_threshold']} test {k['test']}")
    for p, s in r["simulation"]["policies"].items():
        print(f"[sim] {p:15s} urgent {s['urgent_avg']:6.1f} p95 {s['urgent_p95']:6.1f} "
              f"hv {s['high_value_avg']:6.1f} other {s['non_urgent_avg']:6.1f} max {s['max_wait_overall']:6.1f} "
              f"breaches {s['sla_breaches']}")
    print(f"Report written to {REPORT}")
