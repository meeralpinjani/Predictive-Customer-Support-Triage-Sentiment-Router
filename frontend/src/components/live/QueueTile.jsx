import { useMemo, useRef, useState } from "react";
import clsx from "clsx";
import { AlertTriangle, ArrowDown, ArrowUp, Inbox, ListOrdered } from "lucide-react";
import { OPEN_STATUSES, SEGMENT_LABEL, fmtWait, routeMeta } from "../../lib/meta.js";
import { Empty, RouteBadge, Segmented, Skeleton, Tile } from "../ui.jsx";

const TABS = [
  { value: "open", label: "All open", match: (t) => OPEN_STATUSES.includes(t.status) },
  { value: "senior", label: "Senior", match: (t) => OPEN_STATUSES.includes(t.status) && t.route === "senior" },
  { value: "tier2", label: "Tier 2", match: (t) => OPEN_STATUSES.includes(t.status) && t.route === "tier2" },
  { value: "tier1", label: "Tier 1", match: (t) => OPEN_STATUSES.includes(t.status) && t.route === "tier1" },
  { value: "auto", label: "Auto-answered", match: (t) => t.route === "auto_kb" },
  { value: "resolved", label: "Resolved", match: (t) => t.status === "resolved" },
];

const byArrival = (a, b) => new Date(a.created_at) - new Date(b.created_at);

function SlaBar({ wait, sla }) {
  const r = Math.min(wait / sla, 1.25) / 1.25;
  const color = wait >= sla ? "rgb(var(--senior))" : wait >= 0.75 * sla ? "rgb(var(--tier2))" : "rgb(var(--tier1))";
  return (
    <div className="w-16 h-1 rounded-full bg-sunken overflow-hidden" title={`Waited ${fmtWait(wait)} of a ${fmtWait(sla)} SLA`}>
      <div className="h-full rounded-full" style={{ width: `${r * 100}%`, background: color }} />
    </div>
  );
}

export default function QueueTile({ tickets, loading, selectedId, onSelect, preview }) {
  const [tab, setTab] = useState("open");
  const [order, setOrder] = useState("priority");
  const refs = useRef(new Map());

  const { rows, arrival } = useMemo(() => {
    const match = TABS.find((t) => t.value === tab).match;
    const filtered = tickets.filter(match);
    const arrivalOrder = [...filtered].sort(byArrival);
    const arrival = new Map(arrivalOrder.map((t, i) => [t.id, i + 1]));
    let rows = order === "fcfs" ? arrivalOrder : filtered; // API returns priority order
    if (preview && order === "priority") {
      rows = [...filtered].sort((a, b) => (preview.get(a.id)?.position ?? 1e9) - (preview.get(b.id)?.position ?? 1e9));
    }
    return { rows, arrival };
  }, [tickets, tab, order, preview]);

  const counts = TABS.map((t) => ({ value: t.value, label: t.label, count: tickets.filter(t.match).length }));

  const onKeyDown = (e) => {
    if (!["ArrowDown", "ArrowUp", "Home", "End"].includes(e.key) || rows.length === 0) return;
    e.preventDefault();
    const i = rows.findIndex((t) => t.id === selectedId);
    const next = e.key === "Home" ? 0 : e.key === "End" ? rows.length - 1
      : Math.min(Math.max((i < 0 ? -1 : i) + (e.key === "ArrowDown" ? 1 : -1), 0), rows.length - 1);
    onSelect(rows[next].id);
    refs.current.get(rows[next].id)?.focus();
  };

  return (
    <Tile
      eyebrow="Agent view"
      title={preview ? "Live queue · what-if preview" : "Live queue"}
      icon={ListOrdered}
      className="lg:col-span-8"
      action={
        <Segmented
          label="Queue order"
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
        <Segmented label="Queue filter" value={tab} onChange={setTab} options={counts} />
      </div>

      <ol
        className="mt-4 flex-1 min-h-[280px] max-h-[480px] lg:max-h-[600px] overflow-y-auto scroll-thin space-y-2 pr-1"
        aria-label="Tickets"
        onKeyDown={onKeyDown}
      >
        {loading && Array.from({ length: 5 }, (_, i) => <li key={i}><Skeleton className="h-[74px] w-full rounded-2xl" /></li>)}
        {!loading && rows.length === 0 && <li><Empty icon={Inbox}>Nothing here right now.</Empty></li>}
        {rows.map((t, i) => {
          const m = routeMeta(t.route);
          const moved = arrival.get(t.id) - (i + 1);
          const p = preview?.get(t.id);
          const previewRoute = p && p.route !== t.route ? p.route : null;
          return (
            <li key={t.id}>
              <button
                ref={(el) => (el ? refs.current.set(t.id, el) : refs.current.delete(t.id))}
                onClick={() => onSelect(t.id)}
                aria-current={selectedId === t.id}
                className={clsx(
                  "w-full text-left flex items-stretch gap-3 sm:gap-4 rounded-2xl border p-3 pr-4 transition",
                  selectedId === t.id
                    ? "border-glacier bg-glacier-soft/60 ring-2 ring-glacier/15"
                    : "border-line hover:border-ink-3/40 hover:bg-sunken",
                )}
              >
                <span className={clsx("w-1 rounded-full shrink-0", m.dot)} aria-hidden />
                <div className="w-12 shrink-0 text-center">
                  <p className="text-2xl font-extrabold num leading-tight">{p ? p.score : t.priority}</p>
                  <p className="text-[10px] uppercase tracking-wider text-ink-3">
                    {p && p.score !== t.priority ? <span className="line-through">{t.priority}</span> : "score"}
                  </p>
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-x-2 gap-y-1 flex-wrap">
                    <span className="font-semibold text-sm">{t.customer?.name ?? "Unknown customer"}</span>
                    {t.customer && <span className="text-[11px] text-ink-3">{SEGMENT_LABEL[t.customer.segment] ?? t.customer.segment}</span>}
                    <RouteBadge route={t.route} />
                    {previewRoute && (
                      <span className="chip bg-sunken text-ink-2">→ <RouteBadge route={previewRoute} className="!px-1.5" /></span>
                    )}
                    {t.analysis.critical_flags.map((f) => (
                      <span key={f} className="chip bg-senior-soft text-senior-text">
                        <AlertTriangle className="w-3 h-3" aria-hidden />
                        {f}
                      </span>
                    ))}
                    {t.analysis.language === "hi-en" && <span className="chip bg-sunken text-ink-2">Hinglish</span>}
                  </div>
                  <p className="mt-0.5 text-sm text-ink-2 line-clamp-2 break-words">{t.subject ? `${t.subject} · ${t.body}` : t.body}</p>
                  {t.reasons.length > 0 && <p className="mt-0.5 text-xs text-ink-3 line-clamp-1">Why: {t.reasons.join(" · ")}</p>}
                  <p className="sm:hidden mt-1 text-[11px] text-ink-3 num">
                    Waiting {fmtWait(t.wait_minutes)} · arrived #{arrival.get(t.id)}, shown #{i + 1}
                  </p>
                </div>
                <div className="hidden sm:flex shrink-0 text-right flex-col items-end justify-between gap-1">
                  <span className="text-xs font-semibold num text-ink-2">{fmtWait(t.wait_minutes)}</span>
                  {OPEN_STATUSES.includes(t.status) && <SlaBar wait={t.wait_minutes} sla={t.sla_minutes} />}
                  <span className="text-[10px] text-ink-3 whitespace-nowrap" title="Arrival position vs position shown">
                    Arrived #{arrival.get(t.id)} · #{i + 1}
                    {order === "priority" && moved > 0 && (
                      <span className="ml-1 text-tier1-text font-semibold"><ArrowUp className="inline w-3 h-3 -mt-0.5" aria-label="moved up" />{moved}</span>
                    )}
                    {order === "priority" && moved < 0 && (
                      <span className="ml-1 text-ink-3"><ArrowDown className="inline w-3 h-3 -mt-0.5" aria-label="moved down" />{-moved}</span>
                    )}
                  </span>
                </div>
              </button>
            </li>
          );
        })}
      </ol>
      <p className="mt-2 text-[11px] text-ink-3">Tip: click a ticket, then use ↑ ↓ to move through the queue.</p>
    </Tile>
  );
}
