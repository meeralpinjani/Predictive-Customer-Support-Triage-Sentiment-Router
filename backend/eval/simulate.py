"""Queue simulation and ablation: FCFS vs the router (playbook 13.3-13.5).

    python -m eval.simulate

One simulated working day. Tickets come from the labelled set and are scored by the real
analyser; each is assigned a customer from customers.json, so value and SLA come from the
real value model. Policies are compared on the exact same arrivals and handling times.
"""
import heapq
import random
import statistics as st

from app.config import DEFAULT_SLA_MIN
from app.services.priority import compute_priority
from app.services.value import customer_value
from eval.common import analyse_all, customers, labelled

# A busy day: demand exceeds capacity by about 30%, so the queue really builds up.
SEED, AGENTS, N, WINDOW_MIN = 7, 3, 120, 480
SERVICE_MIN = (5, 25)     # handling time per ticket, minutes (uniform)

# Ranking key for each policy at time `now`. Higher goes first; ties go to the oldest ticket.
POLICIES = {
    "fcfs": None,
    "sentiment_only": lambda t, now: t["frustration"],
    "plus_urgency": lambda t, now: 0.5 * t["frustration"] + 0.5 * t["urgency"],
    "plus_value": lambda t, now: 0.35 * t["frustration"] + 0.35 * t["urgency"] + 0.30 * t["value"],
    "router": lambda t, now: compute_priority(
        t["urgency"], t["frustration"], t["value"], now - t["arrival"], t["sla"]).score,
}
POLICY_LABEL = {
    "fcfs": "FCFS (arrival order)",
    "sentiment_only": "Sentiment only",
    "plus_urgency": "+ Urgency",
    "plus_value": "+ Customer value",
    "router": "+ SLA ageing (full router)",
}


def build(mode: str) -> list[dict]:
    rng = random.Random(SEED)
    df = labelled().sample(N, replace=True, random_state=SEED).reset_index(drop=True)
    analyses, _ = analyse_all(df["text"].tolist(), mode)
    custs = customers()
    tickets = []
    for (_, r), a in zip(df.iterrows(), analyses):
        c = rng.choice(custs)
        v = customer_value(c["segment"], c["ltv"], c["churn_risk"], c["renewal_days"]).value
        tickets.append({
            "arrival": rng.uniform(0, WINDOW_MIN),
            "service": rng.uniform(*SERVICE_MIN),
            "urgency": a.urgency,
            "frustration": a.frustration,
            "value": v,
            "sla": c["sla_minutes"] or DEFAULT_SLA_MIN,
            "urgent": r["urgency_label"] == "high" or r["critical"] == 1,
            "high_value": v >= 0.7,
        })
    return tickets


def simulate(tickets: list[dict], policy: str) -> list[tuple[dict, float]]:
    rank = POLICIES[policy]
    queue = sorted(tickets, key=lambda t: t["arrival"])
    free = [0.0] * AGENTS
    heapq.heapify(free)
    pending, i, out = [], 0, []
    while i < len(queue) or pending:
        now = heapq.heappop(free)
        if not pending and i < len(queue) and queue[i]["arrival"] > now:
            now = queue[i]["arrival"]
        while i < len(queue) and queue[i]["arrival"] <= now:
            pending.append(queue[i])
            i += 1
        if rank is None:
            t = min(pending, key=lambda x: x["arrival"])
        else:
            t = max(pending, key=lambda x: (rank(x, now), -x["arrival"]))
        pending.remove(t)
        out.append((t, max(now - t["arrival"], 0.0)))
        heapq.heappush(free, now + t["service"])
    return out


def p95(xs: list[float]) -> float:
    xs = sorted(xs)
    return xs[int(0.95 * (len(xs) - 1))] if xs else 0.0


def summarise(res: list[tuple[dict, float]]) -> dict:
    def avg(sel):
        w = [w for t, w in res if sel(t)]
        return round(st.mean(w), 1) if w else 0.0
    urgent = [w for t, w in res if t["urgent"]]
    return {
        "urgent_avg": avg(lambda t: t["urgent"]),
        "urgent_p95": round(p95(urgent), 1),
        "high_value_avg": avg(lambda t: t["high_value"]),
        "non_urgent_avg": avg(lambda t: not t["urgent"]),
        "overall_avg": avg(lambda t: True),
        "max_wait_overall": round(max(w for _, w in res), 1),
        "sla_breaches": sum(1 for t, w in res if w > t["sla"]),
        "total_simulated": len(res),
        "urgent_count": sum(1 for t, _ in res if t["urgent"]),
        "non_urgent_count": sum(1 for t, _ in res if not t["urgent"]),
        "high_value_count": sum(1 for t, _ in res if t["high_value"]),
    }


def run_simulation(mode: str = "rules") -> dict:
    tickets = build(mode)
    policies = {p: summarise(simulate(tickets, p)) for p in POLICIES}
    utilisation = sum(t["service"] for t in tickets) / (AGENTS * WINDOW_MIN)
    return {
        "setup": {"seed": SEED, "agents": AGENTS, "tickets": N, "window_min": WINDOW_MIN,
                  "service_min": list(SERVICE_MIN), "load": round(utilisation, 2), "nlp_mode": mode,
                  "sla": "per customer (60-480 min)"},
        "policies": policies,
        "labels": POLICY_LABEL,
        # Kept for the dashboard's FCFS-vs-router chart.
        "results": {"fcfs": policies["fcfs"], "priority": policies["router"]},
    }


if __name__ == "__main__":
    import json
    print(json.dumps(run_simulation(), indent=2))
