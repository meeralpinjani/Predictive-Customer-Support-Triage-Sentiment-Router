import { useState } from "react";
import clsx from "clsx";
import { BarChart3, Check, Gauge, Layers, Sigma, Table2, X } from "lucide-react";
import { fmtWait, pct } from "../../lib/meta.js";
import { Empty, Segmented, SkeletonLines, Tile } from "../ui.jsx";

const FCFS = "rgb(var(--tier2))";
const ROUTER = "rgb(var(--tier1))";

const SIM_METRICS = [
  { key: "urgent_avg", label: "Urgent · avg wait" },
  { key: "urgent_p95", label: "Urgent · 95th pct" },
  { key: "high_value_avg", label: "High-value · avg wait" },
  { key: "non_urgent_avg", label: "Low-priority · avg wait" },
  { key: "max_wait_overall", label: "Longest wait" },
];

function change(a, b) {
  if (!a) return "–";
  const d = (b - a) / a;
  return `${d > 0 ? "+" : "−"}${Math.abs(Math.round(d * 100))}%`;
}

/** Playbook 13.3-13.4: FCFS vs the router on the same simulated day. */
export function ResultsTile({ report, error }) {
  const [view, setView] = useState("chart");
  const sim = report?.simulation;
  const f = sim?.policies?.fcfs;
  const r = sim?.policies?.router;
  const max = f && r ? Math.max(...SIM_METRICS.flatMap((m) => [f[m.key], r[m.key]]), 1) : 1;
  const deflection = report?.nlp?.[report.primary_mode]?.auto_answer?.deflection_rate;

  return (
    <Tile
      eyebrow="Proof of impact · playbook 13.4"
      title="A busy day: first-come-first-served vs the router"
      icon={BarChart3}
      className="lg:col-span-8"
      action={<Segmented label="View" value={view} onChange={setView}
                         options={[{ value: "chart", label: "Chart", icon: BarChart3 }, { value: "table", label: "Table", icon: Table2 }]} />}
    >
      {!sim ? (error ? <Empty icon={BarChart3}>{error}</Empty> : <SkeletonLines rows={6} />) : (
        <>
          <div className="grid grid-cols-3 gap-2 mb-5">
            {[
              ["Urgent wait", change(f.urgent_avg, r.urgent_avg)],
              ["High-value wait", change(f.high_value_avg, r.high_value_avg)],
              ["SLA breaches", `${f.sla_breaches} → ${r.sla_breaches}`],
            ].map(([k, v]) => (
              <div key={k} className="rounded-2xl bg-sunken px-3 py-2.5">
                <p className="text-[11px] text-ink-3">{k}</p>
                <p className="text-2xl font-extrabold num text-tier1-text">{v}</p>
              </div>
            ))}
          </div>

          {view === "chart" ? (
            <>
              <div className="flex flex-wrap gap-4 mb-3 text-xs" aria-hidden>
                <span className="flex items-center gap-1.5 text-ink-2 font-medium"><span className="w-3 h-3 rounded-sm" style={{ background: FCFS }} />FCFS (before)</span>
                <span className="flex items-center gap-1.5 text-ink-2 font-medium"><span className="w-3 h-3 rounded-sm" style={{ background: ROUTER }} />Router (after)</span>
              </div>
              <div className="space-y-3.5" role="img" aria-label="Average waits in minutes, FCFS versus router; see the table view for values">
                {SIM_METRICS.map((m) => (
                  <div key={m.key} className="grid grid-cols-[minmax(0,8.5rem)_1fr] sm:grid-cols-[10.5rem_1fr] items-center gap-3">
                    <span className="text-xs font-medium text-ink-2">{m.label}</span>
                    <div className="space-y-[2px]">
                      {[["FCFS", f, FCFS], ["Router", r, ROUTER]].map(([name, d, color]) => (
                        <div key={name} className="flex items-center gap-2 group" title={`${name} · ${m.label}: ${d[m.key]} min`}>
                          <div className="flex-1 h-3.5">
                            <div className="h-full rounded-r transition-[width] duration-700 group-hover:brightness-110"
                                 style={{ width: `${(d[m.key] / max) * 100}%`, background: color, minWidth: 2 }} />
                          </div>
                          <span className="w-14 text-right text-xs font-semibold num">{fmtWait(d[m.key])}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-[11px] uppercase tracking-wider text-ink-3">
                    <th className="py-2 font-semibold">Metric</th><th className="py-2 font-semibold text-right">FCFS</th>
                    <th className="py-2 font-semibold text-right">Router</th><th className="py-2 font-semibold text-right">Change</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {SIM_METRICS.map((m) => (
                    <tr key={m.key}>
                      <td className="py-2 text-ink-2">{m.label}</td>
                      <td className="py-2 text-right num">{f[m.key]} min</td>
                      <td className="py-2 text-right num font-semibold">{r[m.key]} min</td>
                      <td className="py-2 text-right num">{change(f[m.key], r[m.key])}</td>
                    </tr>
                  ))}
                  <tr><td className="py-2 text-ink-2">SLA breaches</td><td className="py-2 text-right num">{f.sla_breaches}</td>
                    <td className="py-2 text-right num font-semibold">{r.sla_breaches}</td><td className="py-2 text-right num">{change(f.sla_breaches, r.sla_breaches)}</td></tr>
                  <tr><td className="py-2 text-ink-2">Tickets needing a human</td><td className="py-2 text-right num">100%</td>
                    <td className="py-2 text-right num font-semibold">{pct(1 - (deflection ?? 0))}</td><td className="py-2 text-right num">−{pct(deflection ?? 0)}</td></tr>
                </tbody>
              </table>
            </div>
          )}
          <p className="mt-4 text-[11px] text-ink-3 leading-relaxed">
            {sim.setup.tickets} labelled tickets, {sim.setup.agents} agents, {sim.setup.window_min / 60}h window, handling {sim.setup.service_min.join("–")} min,
            demand ≈ {Math.round(sim.setup.load * 100)}% of capacity, SLA per customer ({sim.setup.sla}), seed {sim.setup.seed}.
            Trade-off: urgent tickets from free-tier customers (8h SLA) can wait longer than under FCFS, but within their SLA.
            Source <code className="font-mono">eval/simulate.py</code>.
          </p>
        </>
      )}
    </Tile>
  );
}

const TARGETS = [
  { key: "urgency", label: "Urgency F1 (3 classes)", get: (n) => n.urgency.macro_f1, target: 0.75 },
  { key: "fr_r", label: "Frustration recall", get: (n) => n.frustration.recall, target: 0.80 },
  { key: "fr_p", label: "Frustration precision", get: (n) => n.frustration.precision, target: 0.80 },
  { key: "esc", label: "Escalation precision", get: (n) => n.escalation.precision, target: 0.80 },
  { key: "crit", label: "Critical-issue recall", get: (n) => n.critical.recall, target: 0.90 },
  { key: "safe", label: "Safe auto-answers", get: (n) => n.auto_answer.safe_precision, target: 0.90 },
];

/** Classifier metrics on held-out tickets, against the playbook's targets (13.1). */
export function ScorecardTile({ report, error }) {
  const [mode, setMode] = useState(null);
  const active = mode ?? report?.primary_mode ?? "hf";
  const n = report?.nlp?.[active];
  const kb = report?.kb?.[active];
  const modes = Object.keys(report?.nlp ?? {});

  return (
    <Tile
      eyebrow="Scorecard · unseen tickets"
      icon={Gauge}
      className="lg:col-span-4"
      action={modes.length > 1 && (
        <Segmented label="NLP engine" value={active} onChange={setMode}
                   options={modes.map((m) => ({ value: m, label: m === "hf" ? "AI models" : "Rules" }))} />
      )}
    >
      {!n ? (error ? <Empty icon={Gauge}>{error}</Empty> : <SkeletonLines rows={7} />) : (
        <>
          <ul className="divide-y divide-line">
            {[...TARGETS.map((t) => ({ label: t.label, v: t.get(n), target: t.target })),
              { label: "KB auto-answer accuracy", v: kb?.test?.auto_accuracy, target: 0.90 },
            ].map((row) => {
              const ok = row.v != null && row.v >= row.target;
              return (
                <li key={row.label} className="flex items-center gap-3 py-2">
                  <span className={clsx("w-5 h-5 rounded-full grid place-items-center shrink-0", ok ? "bg-tier1-soft text-tier1-text" : "bg-tier2-soft text-tier2-text")}
                        aria-label={ok ? "meets target" : "below target"}>
                    {ok ? <Check className="w-3 h-3" /> : <X className="w-3 h-3" />}
                  </span>
                  <span className="text-sm flex-1 min-w-0">{row.label}</span>
                  <span className="text-sm font-bold num">{pct(row.v)}</span>
                  <span className="text-[11px] text-ink-3 w-12 text-right num">≥{pct(row.target)}</span>
                </li>
              );
            })}
            <li className="flex items-center gap-3 py-2">
              <span className="w-5 h-5 rounded-full grid place-items-center shrink-0 bg-tier1-soft text-tier1-text"><Check className="w-3 h-3" /></span>
              <span className="text-sm flex-1">Latency per ticket</span>
              <span className="text-sm font-bold num">{Math.round(n.latency_ms.mean)} ms</span>
              <span className="text-[11px] text-ink-3 w-12 text-right">&lt;2 s</span>
            </li>
          </ul>
          <p className="mt-auto pt-3 text-[11px] text-ink-3">
            {n.n} unseen tickets ({report.dataset.hinglish} Hinglish in the full set). Thresholds were fitted on train/validation only.
          </p>
        </>
      )}
    </Tile>
  );
}

/** Playbook 13.5: what each signal adds. */
export function AblationTile({ report }) {
  const sim = report?.simulation;
  const order = ["fcfs", "sentiment_only", "plus_urgency", "plus_value", "router"];
  const metrics = [
    { key: "urgent_avg", label: "Urgent avg wait", fmt: fmtWait },
    { key: "high_value_avg", label: "High-value avg wait", fmt: fmtWait },
    { key: "sla_breaches", label: "SLA breaches", fmt: (v) => v },
  ];
  return (
    <Tile eyebrow="Ablation · playbook 13.5" title="Why every signal is needed" icon={Layers} className="lg:col-span-8">
      {!sim ? <SkeletonLines rows={5} /> : (
        <>
          <div className="grid gap-5 sm:grid-cols-3">
            {metrics.map((m) => {
              const max = Math.max(...order.map((p) => sim.policies[p][m.key]), 1);
              return (
                <div key={m.key}>
                  <p className="text-xs font-semibold text-ink-2 mb-2">{m.label} <span className="font-normal text-ink-3">(lower is better)</span></p>
                  <ul className="space-y-1.5">
                    {order.map((p) => {
                      const v = sim.policies[p][m.key];
                      const best = v === Math.min(...order.map((q) => sim.policies[q][m.key]));
                      return (
                        <li key={p} title={`${sim.labels[p]}: ${m.fmt(v)}`}>
                          <div className="flex justify-between text-[11px] mb-0.5">
                            <span className={clsx("truncate", p === "router" ? "font-bold text-ink" : "text-ink-3")}>{sim.labels[p]}</span>
                            <span className={clsx("num", best && "font-bold text-tier1-text")}>{m.fmt(v)}</span>
                          </div>
                          <div className="h-1.5 rounded-full bg-sunken overflow-hidden">
                            <div className="h-full rounded-full" style={{ width: `${(v / max) * 100}%`, background: p === "router" ? ROUTER : "rgb(var(--ink-3))" }} />
                          </div>
                        </li>
                      );
                    })}
                  </ul>
                </div>
              );
            })}
          </div>
          <p className="mt-4 text-xs text-ink-2 leading-relaxed">
            Sentiment alone barely speeds up urgent tickets and multiplies SLA breaches. Adding urgency makes urgent tickets
            fastest, but valuable accounts then wait longer than under FCFS and SLAs break. Adding customer value helps those
            accounts. The full router with SLA ageing gives up a little urgent speed to get the fewest SLA breaches and the
            fastest high-value service.
          </p>
        </>
      )}
    </Tile>
  );
}

const SIGNAL_NAMES = {
  neg: "Negative tone", anger: "Anger / sarcasm", style: "Shouting", churn: "Churn threat",
  neg_model: "Negative tone (RoBERTa)", anger_model: "Anger (emotion model)", neg_rules: "Negative words",
  anger_rules: "Anger & sarcasm cues",
};

/** The fitted frustration model: transparent logistic weights. */
export function ModelTile({ report }) {
  const mode = report?.primary_mode;
  const fm = report?.frustration_model?.[mode];
  const coef = fm?.coef ?? {};
  const entries = Object.entries(coef).sort((a, b) => b[1] - a[1]);
  const max = Math.max(...entries.map(([, v]) => Math.abs(v)), 1);
  return (
    <Tile eyebrow="Frustration model" title="What makes a customer 'highly frustrated'" icon={Sigma} className="lg:col-span-4">
      {!fm ? <SkeletonLines rows={6} /> : (
        <>
          <ul className="space-y-2">
            {entries.map(([k, v]) => (
              <li key={k} title={`weight ${v}`}>
                <div className="flex justify-between text-xs mb-0.5">
                  <span className="text-ink-2">{SIGNAL_NAMES[k] ?? k}</span>
                  <span className="font-semibold num">{v > 0 ? "+" : ""}{v.toFixed(2)}</span>
                </div>
                <div className="h-1.5 rounded-full bg-sunken overflow-hidden">
                  <div className="h-full rounded-full" style={{ width: `${(Math.abs(v) / max) * 100}%`, background: v >= 0 ? "rgb(var(--senior))" : "rgb(var(--ink-3))" }} />
                </div>
              </li>
            ))}
          </ul>
          <p className="mt-auto pt-3 text-[11px] text-ink-3 leading-relaxed">
            Logistic regression fitted on {fm.train_size} training tickets (playbook 9.5). "High frustration" from probability{" "}
            {fm.threshold}, chosen by cross-validation to favour recall: missing an angry customer costs more than a false alarm.
          </p>
        </>
      )}
    </Tile>
  );
}
