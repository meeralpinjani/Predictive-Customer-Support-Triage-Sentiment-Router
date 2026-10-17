import { useMemo, useState } from "react";
import clsx from "clsx";
import { AlertTriangle, Inbox, ListOrdered } from "lucide-react";
import { OPEN_STATUSES, SEGMENT_LABEL, fmtWait, routeMeta } from "../lib/meta.js";
import { Empty, RouteBadge, Segmented, Tile } from "./ui.jsx";

const TABS = [
  { value: "open", label: "All open", match: (t) => OPEN_STATUSES.includes(t.status) },
  { value: "senior", label: "Senior", match: (t) => OPEN_STATUSES.includes(t.status) && t.route === "senior" },
  { value: "tier2", label: "Tier 2", match: (t) => OPEN_STATUSES.includes(t.status) && t.route === "tier2" },
  { value: "tier1", label: "Tier 1", match: (t) => OPEN_STATUSES.includes(t.status) && t.route === "tier1" },
  { value: "auto", label: "Auto", match: (t) => t.status === "kb_handled" },
  { value: "resolved", label: "Resolved", match: (t) => t.status === "resolved" },
];

const byArrival = (a, b) => new Date(a.created_at) - new Date(b.created_at);

export default function QueueTile({ tickets, selectedId, onSelect }) {
  const [tab, setTab] = useState("open");
  const [order, setOrder] = useState("priority");

  const { rows, arrival } = useMemo(() => {
    const match = TABS.find((t) => t.value === tab).match;
    const filtered = tickets.filter(match);
    const arrivalOrder = [...filtered].sort(byArrival);
    const arrival = new Map(arrivalOrder.map((t, i) => [t.id, i + 1]));
    // API already returns priority desc, oldest first on ties.
    return { rows: order === "fcfs" ? arrivalOrder : filtered, arrival };
  }, [tickets, tab, order]);

  const tabOptions = TABS.map((t) => ({ value: t.value, label: t.label, count: tickets.filter(t.match).length }));

  return (
    <Tile
      eyebrow="Agent view"
      title="Live queue"
      icon={ListOrdered}
      className="lg:col-span-8"
      action={
        <Segmented
          value={order}
          onChange={setOrder}
          options={[
            { value: "fcfs", label: "Before · FCFS" },
            { value: "priority", label: "After · Priority" },
          ]}
        />
      }
    >
      <div className="overflow-x-auto scroll-thin -mx-1 px-1 pb-1">
        <Segmented value={tab} onChange={setTab} options={tabOptions} />
      </div>

      <ol className="mt-4 flex-1 min-h-[280px] max-h-[480px] lg:max-h-[560px] overflow-y-auto scroll-thin space-y-2 pr-1">
        {rows.length === 0 && <Empty icon={Inbox}>Nothing here right now.</Empty>}
        {rows.map((t, i) => {
          const m = routeMeta(t.route);
          const moved = arrival.get(t.id) - (i + 1);
          return (
            <li key={t.id}>
              <button
                onClick={() => onSelect(t.id)}
                className={clsx(
                  "w-full text-left flex items-stretch gap-4 rounded-2xl border p-3 pr-4 transition",
                  selectedId === t.id
                    ? "border-nordic-glacier bg-nordic-glacierLight/50 ring-2 ring-nordic-glacier/15"
                    : "border-nordic-border hover:border-slate-300 hover:bg-nordic-frost/60",
                )}
              >
                <span className={clsx("w-1 rounded-full shrink-0", m.dot)} aria-hidden />
                <div className="w-12 shrink-0 text-center">
                  <p className="text-2xl font-extrabold tabular-nums leading-tight">{t.priority}</p>
                  <p className="text-[10px] uppercase tracking-wider text-nordic-muted">score</p>
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-semibold text-sm truncate">{t.customer?.name ?? "Unknown customer"}</span>
                    {t.customer && (
                      <span className="text-[11px] text-nordic-muted">{SEGMENT_LABEL[t.customer.segment] ?? t.customer.segment}</span>
                    )}
                    <RouteBadge route={t.route} />
                    {t.analysis.critical_flags.map((f) => (
                      <span key={f} className="chip bg-nordic-lingonberryLight text-nordic-lingonberry">
                        <AlertTriangle className="w-3 h-3" aria-hidden />
                        {f}
                      </span>
                    ))}
                  </div>
                  <p className="mt-0.5 text-sm text-nordic-slate truncate">{t.subject || t.body}</p>
                  {t.reasons.length > 0 && (
                    <p className="mt-0.5 text-xs text-nordic-muted truncate">Why: {t.reasons.join(" · ")}</p>
                  )}
                </div>
                <div className="shrink-0 text-right flex flex-col justify-between">
                  <span className="text-xs font-semibold tabular-nums text-nordic-slate">{fmtWait(t.wait_minutes)}</span>
                  <span className="text-[10px] text-nordic-muted whitespace-nowrap" title="Arrival position vs position shown">
                    Arrived #{arrival.get(t.id)} · #{i + 1}
                    {order === "priority" && moved > 0 && <span className="ml-1 text-nordic-pine font-semibold">↑{moved}</span>}
                  </span>
                </div>
              </button>
            </li>
          );
        })}
      </ol>
    </Tile>
  );
}
