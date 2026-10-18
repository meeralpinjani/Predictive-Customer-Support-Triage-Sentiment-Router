import { useState } from "react";
import { BarChart3, BookOpen, FileSearch, Loader2, RefreshCw, Search, ShieldCheck, Sigma, Users } from "lucide-react";
import { api } from "../../api.js";
import { COMPONENT_LABEL, COMPONENT_ORDER, ROUTE_ORDER, SEGMENT_LABEL, fmtWait, pct, routeMeta } from "../../lib/meta.js";
import { ErrorNote, MeterRow, RouteBadge, SkeletonLines, Tile, useToast } from "../ui.jsx";

export function RouteMixTile({ stats }) {
  const counts = stats?.counts_by_route ?? {};
  const max = Math.max(1, ...Object.values(counts));
  return (
    <Tile eyebrow="All tickets by route" icon={BarChart3}>
      {!stats ? <SkeletonLines rows={4} /> : (
        <div className="space-y-3">
          {ROUTE_ORDER.map((r) => (
            <MeterRow key={r} label={routeMeta(r).label} value={counts[r] ?? 0} max={max} display={counts[r] ?? 0}
                      color={routeMeta(r).bar} title={`${routeMeta(r).label}: ${counts[r] ?? 0} tickets`} />
          ))}
        </div>
      )}
    </Tile>
  );
}

const SEGMENTS = ["enterprise", "pro", "basic", "free", "unknown"];

export function SegmentWaitTile({ stats }) {
  const waits = stats?.avg_wait_by_segment ?? {};
  const present = SEGMENTS.filter((s) => waits[s] != null);
  const max = Math.max(1, ...present.map((s) => waits[s]));
  return (
    <Tile eyebrow="Avg wait by plan · open tickets" icon={Users}>
      {!stats ? <SkeletonLines rows={4} /> : present.length === 0 ? <p className="text-sm text-ink-3">No open tickets.</p> : (
        <div className="space-y-3">
          {present.map((s) => (
            <MeterRow key={s} label={SEGMENT_LABEL[s]} value={waits[s]} max={max} display={fmtWait(waits[s])} title={`${SEGMENT_LABEL[s]}: ${waits[s]} min`} />
          ))}
        </div>
      )}
    </Tile>
  );
}

export function FormulaTile({ config }) {
  if (!config) return <Tile eyebrow="How scoring works" icon={Sigma} className="lg:col-span-8"><SkeletonLines rows={6} /></Tile>;
  const w = config.weights;
  const shades = ["rgb(var(--glacier))", "rgb(var(--glacier) / .7)", "rgb(var(--glacier) / .45)", "rgb(var(--glacier) / .25)"];
  const ladder = [
    { cond: "Critical flag: security, legal, safety or outage (negation-aware)", route: "level3" },
    { cond: `Confident help-article match ≥ ${config.kb_auto_threshold}, routine question, calm, score < ${config.auto_max_score}`, route: "auto_kb" },
    { cond: `Frustration ≥ ${config.frustration_senior.toFixed(2)}`, route: "level3" },
    { cond: `High-value customer (value ≥ ${config.vip_value}) and score ≥ ${config.vip_score}`, route: "level3" },
    { cond: `Score ≥ ${config.level3_score}`, route: "level3" },
    { cond: "Technical problem detected, or a technical category", route: "level2" },
    { cond: "Everything else (general categories)", route: "level1" },
  ];
  return (
    <Tile eyebrow="How scoring works" title="One transparent score, clear routing rules" icon={Sigma} className="lg:col-span-8">
      <div className="grid gap-5 md:grid-cols-2">
        <div>
          <p className="font-mono text-sm rounded-2xl bg-fjord text-slate-100 p-4 leading-relaxed">
            priority = 100 × (
            {COMPONENT_ORDER.map((k, i) => (
              <span key={k}><br />&nbsp;&nbsp;<span className="text-sky-300">{w[k]}</span> × {k}{i < COMPONENT_ORDER.length - 1 ? " +" : ""}</span>
            ))}
            <br />) + rule boosts
          </p>
          <div className="mt-3 flex gap-[2px] h-2.5 rounded-full overflow-hidden" aria-hidden>
            {COMPONENT_ORDER.map((k, i) => <div key={k} style={{ width: `${w[k] * 100}%`, background: shades[i] }} />)}
          </div>
          <ul className="mt-2 grid grid-cols-2 gap-1 text-[11px] text-ink-2">
            {COMPONENT_ORDER.map((k, i) => (
              <li key={k} className="flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-sm" style={{ background: shades[i] }} aria-hidden />{COMPONENT_LABEL[k]} {pct(w[k])}
              </li>
            ))}
          </ul>
          <ul className="mt-3 space-y-1 text-xs text-ink-2">
            <li><b className="num">+{config.boosts.repeat_contact}</b> third contact in 7 days</li>
            <li><b className="num">+{config.boosts.renewal_risk}</b> renewal in under 14 days and a negative tone</li>
            <li><b className="num">up to +{config.boosts.sla_risk_max}</b> from {pct(config.boosts.sla_risk_start)} of the reply-by time (queue order only)</li>
          </ul>
        </div>
        <ol className="space-y-1.5">
          {ladder.map((s, i) => (
            <li key={i} className="flex items-center gap-3 rounded-xl border border-line px-3 py-2">
              <span className="font-mono text-[11px] text-ink-3 w-4">{i + 1}</span>
              <span className="text-xs text-ink-2 flex-1">{s.cond}</span>
              <RouteBadge route={s.route} />
            </li>
          ))}
        </ol>
      </div>
    </Tile>
  );
}

export function KbTesterTile() {
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

  const actionLabel = { auto_reply: "Would answer automatically", suggest: "Would suggest to the agent", none: "Abstains → human" };

  return (
    <Tile eyebrow="Knowledge base" title="Match tester" icon={BookOpen} className="lg:col-span-4">
      <form onSubmit={run} className="flex gap-2">
        <input className="field" value={text} onChange={(e) => setText(e.target.value)} placeholder="e.g. my card expired" aria-label="Question" />
        <button className="btn-primary shrink-0 !px-3" disabled={busy || !text.trim()} aria-label="Match">
          {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
        </button>
      </form>
      {error && <div className="mt-2"><ErrorNote>{error}</ErrorNote></div>}
      {res ? (
        <div className="mt-4 space-y-3">
          <div>
            <div className="flex items-baseline justify-between">
              <span className="eyebrow">Similarity · {res.matcher === "minilm" ? "MiniLM embeddings" : "TF-IDF"}</span>
              <span className="text-sm font-bold num">{pct(res.confidence)}</span>
            </div>
            <div className="relative mt-1.5 h-2.5 rounded-full bg-sunken">
              <div className="h-full rounded-full bg-auto transition-[width] duration-500" style={{ width: pct(Math.min(res.confidence, 1)) }} />
              {[res.suggest_threshold, res.auto_threshold].map((th, i) => (
                <span key={i} className="absolute -top-1 -bottom-1 w-0.5 bg-ink/60" style={{ left: pct(th) }} aria-hidden />
              ))}
            </div>
            <div className="relative mt-1 h-4 text-[10px] text-ink-3">
              <span className="absolute -translate-x-1/2" style={{ left: pct(res.suggest_threshold) }}>suggest</span>
              <span className="absolute -translate-x-1/2" style={{ left: pct(res.auto_threshold) }}>auto</span>
            </div>
          </div>
          <span className="chip bg-auto-soft text-auto-text">{actionLabel[res.action] ?? res.action}</span>
          {res.matched && (
            <div className="rounded-2xl bg-sunken p-3">
              <p className="text-sm font-semibold">{res.title}</p>
              <p className="text-[11px] text-ink-3">{res.source}</p>
              <p className="mt-1.5 text-xs text-ink-2 line-clamp-4">{res.answer}</p>
            </div>
          )}
        </div>
      ) : !error && (
        <p className="mt-4 text-xs text-ink-3">Type a question to see which of the 26 articles matches and whether the bot would answer on its own.</p>
      )}
    </Tile>
  );
}

export function TrustTile({ stats, health, onRescore }) {
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  const rows = [
    { label: "Manual re-routing rate", value: stats?.override_rate, hint: "Share of human-routed tickets agents re-routed" },
    { label: "KB answer acceptance", value: stats?.suggestion_acceptance_rate, hint: `${stats?.kb_ratings ?? 0} customer ratings so far` },
    { label: "KB abstention", value: stats?.abstention_rate, hint: "Tickets where the bot stayed quiet" },
  ];
  const models = health?.models;
  return (
    <Tile
      eyebrow="System status"
      icon={ShieldCheck}
      className="lg:col-span-4"
      action={
        <button className="btn-ghost !py-1 !px-2.5 !text-xs" disabled={busy}
                onClick={async () => {
                  setBusy(true);
                  try {
                    await onRescore();
                    toast("Open tickets re-scored", "success");
                  } catch (err) {
                    toast(err.message, "error");
                  } finally {
                    setBusy(false);
                  }
                }}>
          <RefreshCw className={`w-3.5 h-3.5 ${busy ? "animate-spin" : ""}`} /> Update priorities now
        </button>
      }
    >
      <ul className="space-y-3">
        {rows.map((r) => (
          <li key={r.label} className="flex items-center justify-between gap-3">
            <div>
              <p className="text-sm font-medium">{r.label}</p>
              <p className="text-[11px] text-ink-3">{r.hint}</p>
            </div>
            <span className="text-lg font-bold num">{r.value == null ? "–" : pct(r.value, 1)}</span>
          </li>
        ))}
      </ul>
      <dl className="mt-auto pt-4 grid grid-cols-3 gap-2 text-center">
        {[
          ["API", health?.status ?? "offline"],
          ["NLP", health ? (health.nlp_mode === "hf" ? "AI models" : models === "loading" ? "loading…" : "rules") : "–"],
          ["KB", health ? `${health.kb_size} · ${health.kb_kind}` : "–"],
        ].map(([k, v]) => (
          <div key={k} className="rounded-xl bg-sunken py-2">
            <dt className="text-[10px] uppercase tracking-wider text-ink-3">{k}</dt>
            <dd className="text-xs font-semibold mt-0.5">{v}</dd>
          </div>
        ))}
      </dl>
    </Tile>
  );
}

export function MethodTile({ report }) {
  const d = report?.dataset;
  return (
    <Tile eyebrow="How we measured" title="Honest numbers" icon={FileSearch} className="lg:col-span-4">
      {!d ? <SkeletonLines rows={5} /> : (
        <ul className="space-y-2 text-xs text-ink-2 leading-relaxed list-disc pl-4">
          <li>{d.tickets} labelled tickets (polite, angry, sarcastic, {d.hinglish} Hinglish) labelled with a written guide.</li>
          <li>Split by template: the {d.test} test tickets use sentences and tone phrases never seen while tuning.</li>
          <li>Frustration weights and help-article cut-offs set on training and validation tickets only.</li>
          <li>Synthetic data written by the team: real tickets would need re-tuning.</li>
          <li>Reproduce: <code className="font-mono">python -m eval.run_all</code>, generated {report.generated_at.slice(0, 10)}.</li>
        </ul>
      )}
    </Tile>
  );
}
