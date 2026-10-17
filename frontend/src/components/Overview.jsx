import { Activity, Clock, Sparkles } from "lucide-react";
import { Tile } from "./ui.jsx";
import { OPEN_STATUSES, ROUTE_ORDER, fmtWait, pct, routeMeta } from "../lib/meta.js";

export function LiveQueueHero({ tickets, loading }) {
  const open = tickets.filter((t) => OPEN_STATUSES.includes(t.status));
  const auto = tickets.filter((t) => t.status === "kb_handled").length;
  const counts = Object.fromEntries(ROUTE_ORDER.map((r) => [r, 0]));
  open.forEach((t) => (counts[t.route] = (counts[t.route] ?? 0) + 1));
  counts.auto_kb = auto;
  const total = ROUTE_ORDER.reduce((s, r) => s + counts[r], 0);
  const critical = open.filter((t) => t.analysis.critical_flags.length).length;

  return (
    <Tile dark eyebrow="Live triage" icon={Activity} className="lg:col-span-6">
      <div className="flex items-end justify-between gap-4">
        <div>
          <p className="text-6xl font-extrabold tracking-tight text-white tabular-nums leading-none">{loading ? "–" : open.length}</p>
          <p className="mt-2 text-sm text-slate-400">tickets waiting for a human</p>
        </div>
        <div className="text-right">
          <p className="text-2xl font-bold text-rose-300 tabular-nums">{loading ? "–" : critical}</p>
          <p className="text-xs text-slate-400">critical flags open</p>
        </div>
      </div>

      <div className="mt-6 flex h-3 w-full gap-[2px] rounded-full overflow-hidden bg-nordic-fjordSurface" aria-hidden>
        {total > 0 &&
          ROUTE_ORDER.filter((r) => counts[r]).map((r) => (
            <div
              key={r}
              title={`${routeMeta(r).label}: ${counts[r]}`}
              style={{ width: `${(counts[r] / total) * 100}%`, background: routeMeta(r).bar }}
              className="h-full first:rounded-l-full last:rounded-r-full"
            />
          ))}
      </div>
      <ul className="mt-3 grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
        {ROUTE_ORDER.map((r) => (
          <li key={r} className="flex items-center gap-2 text-slate-300">
            <span className="w-2 h-2 rounded-full" style={{ background: routeMeta(r).bar }} aria-hidden />
            {routeMeta(r).label}
            <span className="ml-auto font-semibold text-white tabular-nums">{counts[r]}</span>
          </li>
        ))}
      </ul>
    </Tile>
  );
}

export function DeflectionTile({ tickets }) {
  const total = tickets.length;
  const auto = tickets.filter((t) => t.status === "kb_handled").length;
  const rate = total ? auto / total : 0;
  return (
    <Tile eyebrow="Deflection" icon={Sparkles} className="lg:col-span-3">
      <p className="text-5xl font-extrabold tracking-tight tabular-nums">{pct(rate)}</p>
      <p className="mt-2 text-sm text-nordic-muted">
        {auto} of {total} tickets answered by the knowledge base, no agent needed
      </p>
      <div className="mt-auto pt-4">
        <div className="h-2 rounded-full bg-nordic-auroraLight overflow-hidden">
          <div className="h-full rounded-full bg-nordic-aurora transition-[width] duration-500" style={{ width: pct(rate) }} />
        </div>
      </div>
    </Tile>
  );
}

export function WaitTile({ stats }) {
  return (
    <Tile eyebrow="Wait time · open" icon={Clock} className="lg:col-span-3">
      <div className="flex items-baseline gap-2">
        <p className="text-4xl xl:text-5xl font-extrabold tracking-tight tabular-nums whitespace-nowrap">{fmtWait(stats?.avg_wait_minutes)}</p>
        <span className="text-sm text-nordic-muted">avg</span>
      </div>
      <div className="mt-auto pt-4 flex items-center justify-between rounded-2xl bg-nordic-frost px-3 py-2.5">
        <span className="text-xs font-medium text-nordic-muted">95th percentile</span>
        <span className="text-sm font-bold tabular-nums">{fmtWait(stats?.p95_wait_minutes)}</span>
      </div>
    </Tile>
  );
}
