import { Activity, Clock, Sparkles } from "lucide-react";
import { Skeleton, Tile } from "../ui.jsx";
import { ROUTE_ORDER, fmtWait, isOpen, pct, routeMeta } from "../../lib/meta.js";

export function LiveQueueHero({ tickets, loading }) {
  const open = tickets.filter(isOpen);
  const counts = Object.fromEntries(ROUTE_ORDER.map((r) => [r, 0]));
  open.forEach((t) => (counts[t.route] = (counts[t.route] ?? 0) + 1));
  counts.auto_kb = tickets.filter((t) => t.route === "auto_kb").length;
  const total = ROUTE_ORDER.reduce((s, r) => s + counts[r], 0);
  const critical = open.filter((t) => t.analysis.critical_flags.length).length;
  const atRisk = open.filter((t) => t.wait_minutes >= 0.75 * t.sla_minutes).length;

  return (
    <Tile dark eyebrow="Live triage" icon={Activity} className="lg:col-span-6">
      <div className="flex items-end justify-between gap-4">
        <div>
          {loading ? <Skeleton className="h-14 w-24 !bg-fjord-surface" /> : (
            <p className="text-6xl font-extrabold text-white num leading-none">{open.length}</p>
          )}
          <p className="mt-2 text-sm text-slate-400">tickets waiting for a human</p>
        </div>
        <dl className="flex gap-6 text-right">
          <div>
            <dt className="text-xs text-slate-400">critical open</dt>
            <dd className="text-2xl font-bold text-rose-300 num">{loading ? "–" : critical}</dd>
          </div>
          <div>
            <dt className="text-xs text-slate-400">near / past SLA</dt>
            <dd className="text-2xl font-bold text-amber-300 num">{loading ? "–" : atRisk}</dd>
          </div>
        </dl>
      </div>

      <div className="mt-6 flex h-3 w-full gap-[2px] rounded-full overflow-hidden bg-fjord-surface" aria-hidden>
        {total > 0 &&
          ROUTE_ORDER.filter((r) => counts[r]).map((r) => (
            <div key={r} title={`${routeMeta(r).label}: ${counts[r]}`}
                 style={{ width: `${(counts[r] / total) * 100}%`, background: routeMeta(r).bar }} className="h-full" />
          ))}
      </div>
      <ul className="mt-3 grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
        {ROUTE_ORDER.map((r) => (
          <li key={r} className="flex items-center gap-2 text-slate-300">
            <span className="w-2 h-2 rounded-full shrink-0" style={{ background: routeMeta(r).bar }} aria-hidden />
            {r === "auto_kb" ? "Auto-answered" : routeMeta(r).label}
            <span className="ml-auto font-semibold text-white num">{counts[r]}</span>
          </li>
        ))}
      </ul>
    </Tile>
  );
}

export function DeflectionTile({ stats }) {
  const rate = stats?.deflection_rate ?? 0;
  const auto = stats?.counts_by_route?.auto_kb ?? 0;
  return (
    <Tile eyebrow="Deflection" icon={Sparkles} className="lg:col-span-3">
      {stats ? <p className="text-5xl font-extrabold num">{pct(rate)}</p> : <Skeleton className="h-12 w-24" />}
      <p className="mt-2 text-sm text-ink-3">
        {stats ? `${auto} of ${stats.total_tickets}` : "–"} tickets answered by the knowledge base, no agent needed
      </p>
      <div className="mt-auto pt-4">
        <div className="h-2 rounded-full bg-auto-soft overflow-hidden">
          <div className="h-full rounded-full bg-auto transition-[width] duration-500" style={{ width: pct(rate) }} />
        </div>
      </div>
    </Tile>
  );
}

export function WaitTile({ stats }) {
  return (
    <Tile eyebrow="Wait time · open tickets" icon={Clock} className="lg:col-span-3">
      <div className="flex items-baseline gap-2">
        {stats ? (
          <p className="text-4xl xl:text-5xl font-extrabold num whitespace-nowrap">{fmtWait(stats.avg_wait_minutes)}</p>
        ) : <Skeleton className="h-12 w-24" />}
        <span className="text-sm text-ink-3">avg</span>
      </div>
      <dl className="mt-auto pt-4 grid grid-cols-2 gap-2">
        <div className="rounded-2xl bg-sunken px-3 py-2">
          <dt className="text-[11px] text-ink-3">95th percentile</dt>
          <dd className="text-sm font-bold num">{fmtWait(stats?.p95_wait_minutes)}</dd>
        </div>
        <div className="rounded-2xl bg-sunken px-3 py-2">
          <dt className="text-[11px] text-ink-3">past SLA</dt>
          <dd className="text-sm font-bold num">{stats?.sla_breached_open ?? "–"}</dd>
        </div>
      </dl>
    </Tile>
  );
}
