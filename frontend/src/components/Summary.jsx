import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import clsx from "clsx";
import { ArrowRightLeft, FileText, History, Loader2, RefreshCw, ScrollText, X } from "lucide-react";
import { api } from "../api.js";
import { useLiveData } from "../lib/events.jsx";
import { levelTitle, timeAgo } from "../lib/meta.js";
import { ErrorNote, SkeletonLines, Tile, useToast } from "./ui.jsx";

const STATE = {
  ready: { label: "Up to date", cls: "bg-tier1-soft text-tier1-text" },
  stale: { label: "Out of date", cls: "bg-tier2-soft text-tier2-text" },
  pending: { label: "Updating…", cls: "bg-sunken text-ink-2" },
  failed: { label: "Last update failed", cls: "bg-senior-soft text-senior-text" },
  unavailable: { label: "Not available", cls: "bg-sunken text-ink-3" },
};
const METHOD = { extractive: "built from the saved messages", llm: "rewritten by a local AI model", llm_partial: "partly rewritten by a local AI model", unavailable: "—" };

const ref = (src) => (src === "ticket" ? "original description" : typeof src === "number" ? `message #${src}` : src);

/** One labelled list of quoted items, each showing where it came from. */
function Quoted({ title, items, hint }) {
  if (!items?.length) return null;
  return (
    <section>
      <p className="eyebrow mb-1">{title}{hint && <span className="normal-case tracking-normal font-normal"> · {hint}</span>}</p>
      <ul className="space-y-1">
        {items.map((it, i) => (
          <li key={i} className="text-sm">
            “{it.text}”
            <span className="text-[11px] text-ink-3"> · {ref(it.source)}{it.by ? `, ${it.by}` : ""}{it.owner ? ` · to do: ${it.owner}` : ""}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}

export function SummaryBody({ s, staff }) {
  return (
    <div className="space-y-3">
      {s.problem_statement && <section><p className="eyebrow mb-1">Problem</p><p className="text-sm">{s.problem_statement}</p></section>}
      {s.customer_goal && <Quoted title="What the customer wants" items={[s.customer_goal]} />}
      {s.conversation_summary && <section><p className="eyebrow mb-1">So far</p><p className="text-sm">{s.conversation_summary}</p></section>}
      <section><p className="eyebrow mb-1">Status</p><p className="text-sm">{s.current_status?.replaceAll("_", " ")}</p></section>
      {staff && <Quoted title="Customer says" hint="claims, not verified" items={s.customer_claims} />}
      {staff && <Quoted title="Confirmed" hint="from records or an agent's explicit confirmation" items={s.confirmed_facts} />}
      <Quoted title="Already tried" items={s.troubleshooting_attempted} />
      {staff && <Quoted title="Worked" items={s.successful_actions} />}
      {staff && <Quoted title="Didn't work" items={s.failed_attempts} />}
      <Quoted title="Promised by support" items={s.promises_made} />
      <Quoted title="Still to do" items={s.pending_actions} />
      <Quoted title="Open questions" items={s.unresolved_questions} />
      {staff && s.escalation_reason && <Quoted title="Why it was escalated" items={[s.escalation_reason]} />}
      {staff && s.critical_flags?.length > 0 && (
        <section><p className="eyebrow mb-1">Emergency flags (from the ticket)</p>
          <div className="flex gap-1">{s.critical_flags.map((f) => <span key={f} className="chip bg-senior-soft text-senior-text">{f}</span>)}</div></section>
      )}
      {staff && s.next_recommended_step && (
        <section className="rounded-2xl bg-sunken p-3"><p className="eyebrow mb-1">Suggested next step · a rule, not a fact</p><p className="text-sm">{s.next_recommended_step.text}</p></section>
      )}
    </div>
  );
}

/** "View summary" button + accessible dialog. Always shows a summary or an explicit unavailable state. */
export function SummaryButton({ ticketId, staff = false, compact = false, className }) {
  const [open, setOpen] = useState(false);
  const btn = useRef();
  return (
    <>
      <button ref={btn} type="button" className={clsx("btn-ghost", compact && "!py-1 !px-2 !text-xs", className)}
              onClick={(e) => { e.preventDefault(); e.stopPropagation(); setOpen(true); }} aria-haspopup="dialog"
              aria-label={compact ? `View summary of ticket ${ticketId}` : undefined} title="View summary">
        <ScrollText className={compact ? "w-3.5 h-3.5" : "w-4 h-4"} aria-hidden />{!compact && " View summary"}
      </button>
      {open && <SummaryDialog ticketId={ticketId} staff={staff} onClose={() => { setOpen(false); btn.current?.focus({ preventScroll: true }); }} />}
    </>
  );
}

function SummaryDialog({ ticketId, staff, onClose }) {
  const toast = useToast();
  const close = useRef();
  const [busy, setBusy] = useState(false);
  const { data, error, reload } = useLiveData(() => api.summary(ticketId), {
    match: (ev) => ev.ticket_id === ticketId && (ev.type.startsWith("summary.") || ev.type === "message.created"),
    deps: [ticketId], intervalMs: 30000,
  });
  useEffect(() => { close.current?.focus(); }, []);
  const s = data?.summary;
  const st = STATE[data?.status] ?? STATE.unavailable;

  const refresh = async () => {
    setBusy(true);
    try {
      await api.summaryRefresh(ticketId);
      await reload();
    } catch (err) {
      toast(err.message, "error");
    } finally {
      setBusy(false);
    }
  };
  const navigate = useNavigate();
  const goToConversation = () => {
    onClose();
    const here = document.getElementById("conversation");
    if (here) {
      setTimeout(() => here.scrollIntoView({ block: "center" }), 50);
    } else {
      // Opened from a ticket list: open the ticket itself, scrolled to the conversation.
      navigate(`${staff ? "/tickets" : "/support/tickets"}/${ticketId}#conversation`);
    }
  };

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/40 p-4" role="dialog" aria-modal="true" aria-labelledby="sum-title"
         onKeyDown={(e) => e.key === "Escape" && onClose()} onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="w-full max-w-lg max-h-[85vh] overflow-y-auto scroll-thin rounded-3xl bg-card border border-line p-5 shadow-xl">
        <div className="flex items-start gap-3">
          <FileText className="w-5 h-5 mt-0.5 text-glacier-text" aria-hidden />
          <div className="flex-1">
            <h2 id="sum-title" className="text-lg font-bold">Ticket #{ticketId} summary</h2>
            <p className="text-xs text-ink-3">A quick read. The full conversation is always the source of truth.</p>
          </div>
          <button ref={close} className="btn-ghost !p-1.5" onClick={onClose} aria-label="Close summary"><X className="w-4 h-4" /></button>
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-2 text-xs">
          {data && <span className={clsx("chip", st.cls)}>{st.label}</span>}
          {s && <span className="text-ink-3">{METHOD[s.method] ?? s.method} · updated {timeAgo(s.updated_at)}</span>}
        </div>
        <div className="mt-4">
          {error && <ErrorNote>{error}</ErrorNote>}
          {!data && !error && <SkeletonLines rows={6} />}
          {data && data.status === "stale" && <p className="mb-3 text-xs text-ink-2">The conversation has changed since this summary was made.</p>}
          {data && data.status === "failed" && <p className="mb-3 text-xs text-ink-2">The last update failed{data.reason ? ` (${data.reason})` : ""}. {s ? "Showing the last good summary." : ""}</p>}
          {data && !s && <p className="text-sm text-ink-2">No summary is available{data.reason ? `: ${data.reason}` : ""}. Read the full conversation instead.</p>}
          {s && <SummaryBody s={s} staff={staff} />}
        </div>
        <div className="mt-5 flex flex-wrap gap-2 justify-end">
          {staff && <button className="btn-ghost" onClick={refresh} disabled={busy}>{busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />} Refresh summary</button>}
          <button className="btn-primary" onClick={goToConversation}>View full conversation</button>
        </div>
      </div>
    </div>
  );
}

/** Shown to agents above the reply box on transferred tickets: what the previous person knew. */
export function HandoverPanel({ ticketId, className }) {
  const { data, error } = useLiveData(() => api.handovers(ticketId), {
    match: (ev) => ev.ticket_id === ticketId && ev.type === "handover.created", deps: [ticketId], intervalMs: 60000,
  });
  const [showHistory, setShowHistory] = useState(false);
  if (error) return <Tile className={className} eyebrow="Handover"><ErrorNote>{error}</ErrorNote></Tile>;
  if (!data) return null;
  if (!data.length) return null;               // never transferred: nothing to hand over
  const h = data[0];
  const s = h.snapshot;
  const fromTo = `${h.from_level ? levelTitle(h.from_level) : "—"}${h.from_agent ? ` (${h.from_agent})` : ""} → ${h.to_level ? levelTitle(h.to_level) : "queue"}${h.to_agent ? ` (${h.to_agent})` : ""}`;
  return (
    <Tile className={className} eyebrow={`Handover · ${h.trigger.replace("_", " ")} · ${timeAgo(h.created_at)}`} icon={ArrowRightLeft}
          title={fromTo}
          action={data.length > 1 && (
            <button className="btn-ghost !py-1 !px-2.5 !text-xs" onClick={() => setShowHistory((v) => !v)} aria-expanded={showHistory}>
              <History className="w-3.5 h-3.5" /> History ({data.length})
            </button>
          )}>
      <div className="space-y-3 text-sm">
        {h.snapshot_method === "fallback_raw" && (
          <p className="rounded-2xl bg-tier2-soft text-tier2-text px-3 py-2 text-xs">
            Built from the raw recent messages ({h.error === "summaries_disabled" ? "summaries are turned off" : "the summary wasn't available"}): read the conversation below for details.
          </p>
        )}
        <p><b>Why:</b> {h.reason || "—"} <span className="text-ink-3 text-xs">· by {h.actor}</span></p>
        <p className="text-xs text-ink-3">At transfer: priority {s.at_transfer?.priority}{s.at_transfer?.critical_flags?.length ? ` · emergency: ${s.at_transfer.critical_flags.join(", ")}` : ""}</p>
        <Quoted title="Already tried" items={s.troubleshooting_attempted} />
        <Quoted title="Confirmed" items={s.confirmed_facts} />
        <Quoted title="Open questions" items={s.unresolved_questions} />
        <Quoted title="Still to do" items={s.pending_actions} />
        <Quoted title="Promised by support" items={s.promises_made} />
        {s.next_recommended_step && <p className="rounded-2xl bg-sunken p-3"><span className="eyebrow block mb-1">Suggested next step · a rule</span>{s.next_recommended_step.text}</p>}
        {showHistory && (
          <ol className="border-t border-line pt-2 space-y-1 text-xs text-ink-2">
            {data.map((x) => (
              <li key={x.id}>#{x.sequence} · {x.trigger.replace("_", " ")} · {x.from_level ?? "—"} → {x.to_level ?? "queue"} · {x.reason} · {new Date(x.created_at).toLocaleString()} · {x.snapshot_method}</li>
            ))}
          </ol>
        )}
      </div>
    </Tile>
  );
}
