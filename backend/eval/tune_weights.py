"""Tune the hand-set numbers on data instead of copying them:

    python -m eval.tune_weights

1. Urgency base value per problem type: coordinate search for the best urgency macro-F1 on the
   TRAIN split (both analysis modes). Emergencies (security, safety, legal, outage) stay fixed.
2. (see 4)
3. Priority weights (frustration, urgency, value, waiting): grid search (steps of 0.05) in the queue
   simulation on five simulated days built only from TRAIN tickets (seeds 11, 23, 31, 47, 59).
   Objective = late replies + (urgent + highly frustrated average wait) / 30 + high-value average wait / 60
   (lower is better). Waits are in minutes, so 30 minutes of average delay counts like one late reply.
4. Level 3 score cut-off: best escalation F1 on the TRAIN split, using the tuned weights.

Nothing here touches the TEST split; eval.run_all reports the held-out results afterwards.
Prints the proposal; the chosen values are copied into app/nlp/rules.py and app/config.py.
"""
import itertools
import random
import statistics as st

from sklearn.metrics import f1_score

from app.config import DEFAULT_SLA_MIN, SLA_RISK_FULL, SLA_RISK_POINTS, SLA_RISK_START, WEIGHTS, settings
from app.nlp import frustration_model
from app.nlp.rules import INTENT_META, INTENTS, analyse_rules, urgency_boost
from app.services.priority import compute_priority
from app.services.router import decide
from app.services.value import customer_value
from eval.common import customers, labelled, set_mode
from eval.evaluate_nlp import MID_VALUE, to_level

TUNABLE = [i[0] for i in INTENTS] + ["other"]
CANDIDATES = [round(x * 0.05, 2) for x in range(1, 20)]
SIM_SEEDS = (11, 23, 31, 47, 59)
AGENTS, N, WINDOW_MIN, SERVICE_MIN = 3, 120, 480, (5, 25)


# ---------------------------------------------------------------- per-ticket components
def components(texts: list[str], mode: str) -> list[dict]:
    """Everything urgency depends on, so new base values can be tried without re-running the models."""
    from app.nlp.analyzer import analyse
    out = []
    for text in texts:
        base = analyse_rules(text)
        full = analyse(text) if mode == "hf" else base
        row = {"intent": base.intent, "flags": base.critical_flags, "boost": urgency_boost(text),
               "frustration": full.frustration, "confidence": full.confidence, "final_intent": full.intent,
               "urgency_now": full.urgency, "model_base": None, "p_top": None}
        if mode == "hf" and not base.critical_flags:
            from app.nlp import hf
            _, p_top, model_base = hf.issue_scores(text)
            row.update(model_base=model_base, p_top=p_top)
        out.append(row)
    return out


def urgency(row: dict, bases: dict, mode: str) -> float:
    """Mirror of rules.urgency_from_base / analyzer._hf_analysis (checked against the real values below)."""
    if row["flags"]:
        return row["urgency_now"]
    if mode == "hf":
        mixed = row["model_base"] if row["intent"] == "other" else 0.5 * bases[row["intent"]] + 0.5 * row["model_base"]
    else:
        mixed = bases[row["intent"]]
    return round(min(mixed + row["boost"], 1.0), 3)


def macro_f1(rows, labels, bases, mode) -> float:
    return f1_score(labels, [to_level(urgency(r, bases, mode)) for r in rows], average="macro")


def tune_bases(data: dict, labels) -> dict:
    bases = {k: INTENT_META[k]["base"] for k in TUNABLE}
    score = lambda b: sum(macro_f1(rows, labels, b, m) for m, rows in data.items())
    best = score(bases)
    for _ in range(3):                                  # a few passes of coordinate search
        for k in TUNABLE:
            for v in CANDIDATES:
                trial = {**bases, k: v}
                s = score(trial)
                if s > best + 1e-9:
                    best, bases = s, trial
    return bases


# ---------------------------------------------------------------- escalation cut-off
def tune_level3(rows, df, bases, mode, weights=None) -> tuple[int, float, float]:
    should = ((df["urgency_label"] == "high") | (df["critical"] == 1) | (df["frustration_label"] == "high")).tolist()

    def f1_for(cut):
        sent = []
        for r in rows:
            u = urgency(r, bases, mode)
            pr = compute_priority(u, r["frustration"], MID_VALUE, 0, 240, weights=weights)
            d = decide(pr.route_score, r["frustration"], r["final_intent"], r["flags"], 0.0, value=MID_VALUE,
                       confidence=r["confidence"], allow_auto=False, level3_score=cut, mode=mode)
            sent.append(d.route == "level3")
        return f1_score(should, sent)
    current = f1_for(settings.level3_score)
    best = max(range(50, 86, 5), key=lambda c: (round(f1_for(c), 4), c == settings.level3_score))
    return best, current, f1_for(best)


# ---------------------------------------------------------------- simulation (train tickets only)
def build_day(rows, df, seed, bases, mode) -> list[dict]:
    rng = random.Random(seed)
    idx = df.sample(N, replace=True, random_state=seed).index
    pos = {i: p for p, i in enumerate(df.index)}
    custs = customers()
    day = []
    for i in idx:
        r, lab = rows[pos[i]], df.loc[i]
        c = rng.choice(custs)
        v = customer_value(c["segment"], c["ltv"], c["churn_risk"], c["renewal_days"]).value
        day.append({"arrival": rng.uniform(0, WINDOW_MIN), "service": rng.uniform(*SERVICE_MIN),
                    "urgency": urgency(r, bases, mode), "frustration": r["frustration"], "value": v,
                    "sla": c["sla_minutes"] or DEFAULT_SLA_MIN,
                    "urgent": lab["urgency_label"] == "high" or lab["critical"] == 1, "high_value": v >= 0.7,
                    "frustrated": lab["frustration_label"] == "high"})
    return day


def fast_score(t, now, w) -> float:
    """Same number as compute_priority(...).score (checked below), without building explanations."""
    sla, wait = max(t["sla"], 1.0), max(now - t["arrival"], 0.0)
    base = 100 * (w["frustration"] * t["frustration"] + w["urgency"] * t["urgency"] + w["value"] * t["value"]
                  + w["age"] * min(wait / sla, 1.0))
    ramp = (wait - SLA_RISK_START * sla) / ((SLA_RISK_FULL - SLA_RISK_START) * sla)
    return int(min(base + SLA_RISK_POINTS * min(max(ramp, 0.0), 1.0), 100.0) + 0.5)


def run_day(day, w) -> dict:
    import heapq
    queue = sorted(day, key=lambda t: t["arrival"])
    free = [0.0] * AGENTS
    pending, i, waits = [], 0, []
    while i < len(queue) or pending:
        now = heapq.heappop(free)
        if not pending and i < len(queue) and queue[i]["arrival"] > now:
            now = queue[i]["arrival"]
        while i < len(queue) and queue[i]["arrival"] <= now:
            pending.append(queue[i]); i += 1
        t = max(pending, key=lambda x: (fast_score(x, now, w), -x["arrival"]))
        pending.remove(t)
        waits.append((t, max(now - t["arrival"], 0.0)))
        heapq.heappush(free, now + t["service"])
    avg = lambda sel: st.mean([w_ for t, w_ in waits if sel(t)] or [0.0])
    return {"breaches": sum(1 for t, w_ in waits if w_ > t["sla"]), "urgent": avg(lambda t: t["urgent"]),
            "frustrated": avg(lambda t: t["frustrated"]), "high_value": avg(lambda t: t["high_value"])}


def objective(days, w) -> float:
    res = [run_day(d, w) for d in days]
    return st.mean(r["breaches"] + (r["urgent"] + r["frustrated"]) / 30 + r["high_value"] / 60 for r in res)


def tune_weights(days) -> tuple[dict, float, float]:
    current = objective(days, WEIGHTS)
    best_w, best = dict(WEIGHTS), current
    for f, u, v in itertools.product(range(1, 18), repeat=3):
        a = 20 - f - u - v
        if a < 1:
            continue
        w = {"frustration": f / 20, "urgency": u / 20, "value": v / 20, "age": a / 20}
        s = objective(days, w)
        if s < best - 1e-9:
            best_w, best = w, s
    return best_w, current, best


def main() -> dict:
    df = labelled("train").reset_index(drop=True)
    labels = df["urgency_label"].tolist()
    modes = ["rules", "hf"] if set_mode("hf") else ["rules"]
    data = {}
    for m in modes:
        set_mode(m)
        data[m] = components(df["text"].tolist(), m)
        cur = {k: INTENT_META[k]["base"] for k in TUNABLE}
        mism = sum(abs(urgency(r, cur, m) - r["urgency_now"]) > 1e-6 for r in data[m])
        assert mism == 0, f"urgency mirror differs from the analyser on {mism} tickets ({m})"
    before = {m: round(macro_f1(data[m], labels, {k: INTENT_META[k]["base"] for k in TUNABLE}, m), 3) for m in modes}
    bases = tune_bases(data, labels)
    after = {m: round(macro_f1(data[m], labels, bases, m), 3) for m in modes}
    primary = modes[-1]
    set_mode(primary)
    days = [build_day(data[primary], df, s, bases, primary) for s in SIM_SEEDS]
    probe = days[0][0]
    assert fast_score(probe, 200.0, WEIGHTS) == compute_priority(probe["urgency"], probe["frustration"], probe["value"],
                                                                  200.0 - probe["arrival"], probe["sla"]).score
    weights, obj_before, obj_after = tune_weights(days)
    l3, l3_before, l3_after = tune_level3(data[primary], df, bases, primary, weights)
    result = {
        "urgency_bases": {k: bases[k] for k in TUNABLE},
        "urgency_macro_f1_train": {"before": before, "after": after},
        "level3_score": {"chosen": l3, "escalation_f1_train_before": round(l3_before, 3), "after": round(l3_after, 3)},
        "weights": weights,
        "simulation_objective_train_days": {"before": round(obj_before, 3), "after": round(obj_after, 3)},
    }
    return result


if __name__ == "__main__":
    import json
    print(json.dumps(main(), indent=2))
