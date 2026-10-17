import { useState } from "react";
import { BarChart3, BookOpen, Loader2, RefreshCw, Search, ShieldCheck, Sigma, Users } from "lucide-react";
import { api } from "../api.js";
import { COMPONENT_LABEL, ROUTE_ORDER, SEGMENT_LABEL, fmtWait, pct, routeMeta } from "../lib/meta.js";
import { Empty, MeterRow, RouteBadge, Tile } from "./ui.jsx";

export function RouteMixTile({ stats }) {
  const counts = stats?.counts_by_route ?? {};
  const max = Math.max(1, ...Object.values(counts));
  return (
    <Tile eyebrow="All tickets by route" icon={BarChart3}>
      <div className="space-y-3">
        {ROUTE_ORDER.map((r) => (
          <MeterRow
            key={r}
            label={routeMeta(r).label}
            value={counts[r] ?? 0}
            max={max}
            display={counts[r] ?? 0}
            color={routeMeta(r).bar}
            title={`${routeMeta(r).label}: ${counts[r] ?? 0} tickets`}
          />
        ))}
      </div>
    </Tile>
  );
}

const SEGMENTS = ["enterprise", "pro", "basic", "free", "unknown"];

export function SegmentWaitTile({ stats }) {
  const waits = stats?.avg_wait_by_segment ?? {};
  const present = SEGMENTS.filter((s) => waits[s] != null);
  const max = Math.max(1, ...present.map((s) => waits[s]));
  return (
    <Tile eyebrow="Avg wait by plan · open" icon={Users}>
      {present.length === 0 ? (
        <p className="text-sm text-nordic-muted">No open tickets.</p>
      ) : (
        <div className="space-y-3">
          {present.map((s) => (
            <MeterRow key={s} label={SEGMENT_LABEL[s]} value={waits[s]} max={max} display={fmtWait(waits[s])} title={`${SEGMENT_LABEL[s]}: ${waits[s]} min`} />
          ))}
        </div>
      )}
    </Tile>
  );
}

const SIM_METRICS = [
  { key: "urgent_avg", label: "Urgent · avg wait" },
  { key: "urgent_p95", label: "Urgent · p95 wait" },
  { key: "non_urgent_avg", label: "Non-urgent · avg wait" },
  { key: "max_wait_overall", label: "Longest wait (any ticket)" },
];
const SIM_SERIES = [
  { key: "fcfs", label: "FCFS (before)", color: "#D97706" },
  { key: "priority", label: "Priority router (after)", color: "#0D9488" },
];

export function SimulationTile({ sim, error }) {
  const r = sim?.results;
  const max = r ? Math.max(1, ...SIM_METRICS.flatMap((m) => SIM_SERIES.map((s) => r[s.key][m.key]))) : 1;
  const cut = r && r.fcfs.urgent_avg > 0 ? (r.fcfs.urgent_avg - r.priority.urgent_avg) / r.fcfs.urgent_avg : null;

  return (
    <Tile
      eyebrow="Proof of impact"
      title="FCFS vs priority router — simulated day"
      icon={BarChart3}
      className="lg:col-span-8"
      action={
        cut != null && (
          <div className="text-right">
            <p className="text-3xl font-extrabold tabular-nums text-nordic-pine leading-none">−{pct(cut)}</p>
            <p className="text-[10px] uppercase tracking-wider text-nordic-muted mt-1">urgent avg wait</p>
          </div>
        )
      }
    >
      {!r ? (
        <Empty icon={BarChart3}>{error ? `Simulation unavailable: ${error}` : "Running simulation…"}</Empty>
      ) : (
        <>
          <div className="flex flex-wrap gap-4 mb-4 text-xs">
            {SIM_SERIES.map((s) => (
              <span key={s.key} className="flex items-center gap-1.5 text-nordic-slate font-medium">
                <span className="w-3 h-3 rounded-sm" style={{ background: s.color }} aria-hidden />
                {s.label}
              </span>
            ))}
          </div>
          <div className="space-y-4">
            {SIM_METRICS.map((m) => (
              <div key={m.key} className="grid grid-cols-[minmax(0,9rem)_1fr] sm:grid-cols-[11rem_1fr] items-center gap-3">
                <span className="text-xs font-medium text-nordic-slate">{m.label}</span>
                <div className="space-y-[2px]">
                  {SIM_SERIES.map((s) => {
                    const v = r[s.key][m.key];
                    return (
                      <div key={s.key} className="flex items-center gap-2 group" title={`${s.label} · ${m.label}: ${v} min`}>
                        <div className="flex-1 h-3.5">
                          <div
                            className="h-full rounded-r transition-[width] duration-700 group-hover:brightness-110"
                            style={{ width: `${(v / max) * 100}%`, background: s.color, minWidth: 2 }}
                          />
                        </div>
                        <span className="w-14 text-right text-xs font-semibold tabular-nums text-nordic-dark">{fmtWait(v)}</span>
                      </div>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>
          <p className="mt-5 text-[11px] text-nordic-muted">
            {sim.setup.tickets} tickets · {sim.setup.agents} agents · {sim.setup.window_min / 60}h window · SLA {sim.setup.sla_min}m · seed{" "}
            {sim.setup.seed} · urgent = {r.priority.urgent_count}, non-urgent = {r.priority.non_urgent_count} · source{" "}
            <code className="mono">eval/simulate.py</code>
          </p>
        </>
      )}
    </Tile>
  );
}

export function KbTesterTile({ config }) {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [res, setRes] = useState(null);
  const [error, setError] = useState("");

  const run = async (e) => {
    e.preventDefault();
    if (!text.trim()) return;
    setBusy(true);
    setError("");
    try {
      setRes(await api.kbMatch(text.trim()));
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const suggest = res?.suggest_threshold ?? config?.kb_suggest_threshold ?? 0.55;
  const auto = res?.auto_threshold ?? config?.kb_auto_threshold ?? 0.75;
  const actionLabel = { auto_reply: "Would auto-answer", suggest: "Would suggest to agent", none: "Abstains → human" };

  return (
    <Tile eyebrow="Knowledge base" title="Match tester" icon={BookOpen} className="lg:col-span-4">
      <form onSubmit={run} className="flex gap-2">
        <input className="field" value={text} onChange={(e) => setText(e.target.value)} placeholder="e.g. how do I enable 2FA?" />
        <button className="btn-primary shrink-0 !px-3" disabled={busy || !text.trim()} aria-label="Match">
          {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
        </button>
      </form>
      {error && <p className="mt-2 text-xs text-nordic-lingonberry">{error}</p>}

      {res && (
        <div className="mt-4 space-y-3">
          <div>
            <div className="flex items-baseline justify-between">
              <span className="eyebrow">Confidence</span>
              <span className="text-sm font-bold tabular-nums">{pct(res.confidence)}</span>
            </div>
            <div className="relative mt-1.5 h-2.5 rounded-full bg-slate-100">
              <div className="h-full rounded-full bg-nordic-aurora transition-[width] duration-500" style={{ width: pct(Math.min(res.confidence, 1)) }} />
              {[suggest, auto].map((th, i) => (
                <span key={i} className="absolute -top-1 -bottom-1 w-0.5 bg-nordic-dark/60" style={{ left: pct(th) }} aria-hidden />
              ))}
            </div>
            <div className="relative mt-1 h-4 text-[10px] text-nordic-muted">
              <span className="absolute -translate-x-1/2" style={{ left: pct(suggest) }}>suggest {suggest}</span>
              <span className="absolute -translate-x-1/2" style={{ left: pct(auto) }}>auto {auto}</span>
            </div>
          </div>
          <span className="chip bg-nordic-auroraLight text-nordic-aurora">{actionLabel[res.action] ?? res.action}</span>
          {res.matched && (
            <div className="rounded-2xl bg-nordic-frost p-3">
              <p className="text-sm font-semibold">{res.title}</p>
              <p className="text-[11px] text-nordic-muted">{res.source}</p>
              <p className="mt-1.5 text-xs text-nordic-slate line-clamp-4">{res.answer}</p>
            </div>
          )}
        </div>
      )}
      {!res && !error && <p className="mt-4 text-xs text-nordic-muted">Type a question to see which article matches and whether the bot would answer on its own.</p>}
    </Tile>
  );
}

const W_ORDER = ["urgency", "frustration", "value", "age"];

export function FormulaTile({ config }) {
  if (!config) return <Tile eyebrow="How scoring works" icon={Sigma} className="lg:col-span-8"><Empty>Loading…</Empty></Tile>;
  const w = config.weights;
  const ladder = [
    { cond: "Critical flag (security, legal, safety, outage)", route: "senior" },
    { cond: `Frustration ≥ ${config.frustration_senior}`, route: "senior" },
    { cond: `KB match ≥ ${config.kb_auto_threshold}, routine intent, calm, score < ${config.tier2_score}`, route: "auto_kb" },
    { cond: `Score ≥ ${config.senior_score}`, route: "senior" },
    { cond: `Score ≥ ${config.tier2_score}`, route: "tier2" },
    { cond: "Everything else", route: "tier1" },
  ];
  return (
    <Tile eyebrow="How scoring works" title="One transparent score, one routing ladder" icon={Sigma} className="lg:col-span-8">
      <div className="grid gap-5 md:grid-cols-2">
        <div>
          <p className="mono text-sm rounded-2xl bg-nordic-fjord text-slate-100 p-4 leading-relaxed">
            priority = 100 × (
            {W_ORDER.map((k, i) => (
              <span key={k}>
                <br />
                &nbsp;&nbsp;<span className="text-sky-300">{w[k]}</span> × {k}
                {i < W_ORDER.length - 1 ? " +" : ""}
              </span>
            ))}
            <br />)
          </p>
          <div className="mt-3 flex gap-[2px] h-2.5 rounded-full overflow-hidden" aria-hidden>
            {W_ORDER.map((k, i) => (
              <div key={k} style={{ width: `${w[k] * 100}%` }} className={["bg-sky-700", "bg-sky-500", "bg-sky-300", "bg-sky-200"][i]} />
            ))}
          </div>
          <ul className="mt-2 grid grid-cols-2 gap-1 text-[11px] text-nordic-slate">
            {W_ORDER.map((k, i) => (
              <li key={k} className="flex items-center gap-1.5">
                <span className={`w-2 h-2 rounded-sm ${["bg-sky-700", "bg-sky-500", "bg-sky-300", "bg-sky-200"][i]}`} aria-hidden />
                {COMPONENT_LABEL[k]} {pct(w[k])}
              </li>
            ))}
          </ul>
          <p className="mt-3 text-xs text-nordic-muted">
            Open tickets are re-scored every {config.rescore_interval_sec}s, so waiting raises priority and routes only move up.
          </p>
        </div>
        <ol className="space-y-1.5">
          {ladder.map((s, i) => (
            <li key={i} className="flex items-center gap-3 rounded-xl border border-nordic-border px-3 py-2">
              <span className="mono text-[11px] text-nordic-muted w-4">{i + 1}</span>
              <span className="text-xs text-nordic-slate flex-1">{s.cond}</span>
              <RouteBadge route={s.route} />
            </li>
          ))}
        </ol>
      </div>
    </Tile>
  );
}

export function TrustTile({ stats, health, onRescore }) {
  const [busy, setBusy] = useState(false);
  const rows = [
    { label: "Agent override rate", value: stats?.override_rate, hint: "Lower means agents agree with routing" },
    { label: "KB suggestion acceptance", value: stats?.suggestion_acceptance_rate, hint: "Helpful votes ÷ all KB votes" },
    { label: "KB abstention rate", value: stats?.abstention_rate, hint: "Tickets where the bot stayed quiet" },
  ];
  return (
    <Tile
      eyebrow="Trust & health"
      icon={ShieldCheck}
      className="lg:col-span-4"
      action={
        <button
          className="btn-ghost !py-1 !px-2.5 !text-xs"
          disabled={busy}
          onClick={async () => {
            setBusy(true);
            try {
              await onRescore();
            } finally {
              setBusy(false);
            }
          }}
        >
          <RefreshCw className={`w-3.5 h-3.5 ${busy ? "animate-spin" : ""}`} /> Rescore
        </button>
      }
    >
      <ul className="space-y-3">
        {rows.map((r) => (
          <li key={r.label} className="flex items-center justify-between gap-3" title={r.hint}>
            <div>
              <p className="text-sm font-medium">{r.label}</p>
              <p className="text-[11px] text-nordic-muted">{r.hint}</p>
            </div>
            <span className="text-lg font-bold tabular-nums">{r.value == null ? "–" : pct(r.value, 1)}</span>
          </li>
        ))}
      </ul>
      <div className="mt-auto pt-4 grid grid-cols-3 gap-2 text-center">
        {[
          ["API", health?.status ?? "offline"],
          ["NLP", health?.nlp_mode ?? "–"],
          ["KB", health ? `${health.kb_size} articles` : "–"],
        ].map(([k, v]) => (
          <div key={k} className="rounded-xl bg-nordic-frost py-2">
            <p className="text-[10px] uppercase tracking-wider text-nordic-muted">{k}</p>
            <p className="text-xs font-semibold mt-0.5">{v}</p>
          </div>
        ))}
      </div>
    </Tile>
  );
}
