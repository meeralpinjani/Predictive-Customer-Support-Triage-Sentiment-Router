import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import clsx from "clsx";
import {
  AlertTriangle, ChevronLeft, ChevronRight, Copy, FileText, History, Info, Loader2, RefreshCw, Scale, ShieldCheck, Sparkles,
} from "lucide-react";
import { api } from "../../api.js";
import { useLiveData } from "../../lib/events.jsx";
import { RouteBadge, Empty, ErrorNote, PageHeader, SkeletonLines, Tile, useToast } from "../../components/ui.jsx";
import { timeAgo } from "../../lib/meta.js";

// Neutral wording throughout: this is a review aid, never a verdict.
const REVIEW = {
  clear: { label: "Clear", cls: "bg-sunken text-ink-2" },
  review_recommended: { label: "Review suggested", cls: "bg-glacier-soft text-glacier-text" },
  under_review: { label: "Under review", cls: "bg-tier2-soft text-tier2-text" },
  confirmed_integrity_concern: { label: "Concern confirmed by a reviewer", cls: "bg-senior-soft text-senior-text" },
  dismissed: { label: "Dismissed", cls: "bg-sunken text-ink-3" },
};
const REVIEW_ORDER = ["review_recommended", "under_review", "confirmed_integrity_concern", "dismissed", "clear"];
const AI_TEXT = {
  not_assessed: "Not assessed yet",
  insufficient_text: "Too short to assess",
  unsupported_language: "Language not supported (English only)",
  model_unavailable: "Detector unavailable",
};
const SLA_TEXT = { ok: "On time", near: "Near reply-by time", late: "Past reply-by time", closed: "Closed" };
const CONSISTENCY = {
  verified_conflict: "Conflicts with our records",
  possible_inconsistency: "Possible inconsistency",
  insufficient_evidence: "Can't be checked here",
  no_conflict_detected: "No conflict found",
};
const REASON = {
  verified_conflict: "Conflicts with ticket history",
  possible_inconsistency: "Possible inconsistency with our records",
  cross_customer_near_identical: "Near-identical text from another customer",
  ai_pattern: "AI-like writing patterns",
};
const reasonText = (r) => REASON[r] ?? (r.startsWith("manipulation:") ? `Indicator: ${r.split(":")[1].replaceAll("_", " ")}` : r);

function aiText(status, score, threshold) {
  if (status !== "assessed") return AI_TEXT[status] ?? status;
  return score != null && score >= threshold
    ? "AI-like writing patterns detected (not evidence on its own)"
    : "No strong AI-like patterns";
}

function StateChip({ state }) {
  const m = REVIEW[state] ?? { label: state, cls: "bg-sunken text-ink-2" };
  return <span className={clsx("chip", m.cls)}>{m.label}</span>;
}

/** Small accessible confirmation dialog with an optional / required reason. */
function ConfirmDialog({ open, title, body, confirmLabel, reasonMode, onCancel, onConfirm, busy }) {
  const [reason, setReason] = useState("");
  const ref = useRef();
  useEffect(() => { if (open) { setReason(""); setTimeout(() => ref.current?.focus(), 0); } }, [open]);
  if (!open) return null;
  const needs = reasonMode === "required";
  const valid = !needs || reason.trim().length >= 10;
  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/40 p-4" role="dialog" aria-modal="true" aria-labelledby="dlg-title"
         onKeyDown={(e) => e.key === "Escape" && onCancel()}>
      <form className="w-full max-w-md rounded-3xl bg-card border border-line p-5 shadow-xl"
            onSubmit={(e) => { e.preventDefault(); if (valid && !busy) onConfirm(reason.trim()); }}>
        <h2 id="dlg-title" className="text-lg font-bold">{title}</h2>
        <p className="mt-1 text-sm text-ink-2">{body}</p>
        {reasonMode && (
          <label className="block mt-4 text-sm font-semibold">
            Reason {needs ? <span className="text-ink-3 font-normal">(required, at least 10 characters)</span> : <span className="text-ink-3 font-normal">(optional)</span>}
            <textarea ref={ref} className="field mt-1.5 min-h-[90px]" maxLength={1000} value={reason}
                      onChange={(e) => setReason(e.target.value)} />
          </label>
        )}
        <div className="mt-4 flex justify-end gap-2">
          <button type="button" className="btn-ghost" onClick={onCancel} disabled={busy}>Cancel</button>
          <button type="submit" className="btn-primary" disabled={!valid || busy} ref={reasonMode ? undefined : ref}>
            {busy && <Loader2 className="w-4 h-4 animate-spin" />} {confirmLabel}
          </button>
        </div>
      </form>
    </div>
  );
}

function Detail({ id, threshold, onChanged }) {
  const toast = useToast();
  const { data: a, error, reload } = useLiveData(() => api.integrityDetail(id), {
    match: (ev) => ev.type?.startsWith("integrity.") && ev.ticket_id != null, intervalMs: 30000, deps: [id],
  });
  const [related, setRelated] = useState(null);
  const [history, setHistory] = useState(null);
  const [dialog, setDialog] = useState(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => { setRelated(null); setHistory(null); }, [id]);

  const act = async (action, reason = "") => {
    setBusy(true);
    try {
      await api.integrityReview(id, action, reason);
      toast("Review saved", "success");
      setDialog(null);
      await reload();
      if (history) setHistory(await api.integrityHistory(id));
      onChanged();
    } catch (err) {
      toast(err.message, "error");
    } finally {
      setBusy(false);
    }
  };
  const reassess = async () => {
    setBusy(true);
    try {
      await api.integrityReassess(a.ticket_id);
      toast("Reassessment queued", "success");
      setDialog(null);
      onChanged();
    } catch (err) {
      toast(err.message, "error");
    } finally {
      setBusy(false);
    }
  };

  if (error) return <Tile className="lg:col-span-5" eyebrow="Assessment"><ErrorNote>{error}</ErrorNote></Tile>;
  if (!a) return <Tile className="lg:col-span-5" eyebrow="Assessment"><SkeletonLines rows={8} /></Tile>;
  const t = a.ticket;
  const done = a.status === "complete";

  return (
    <Tile className="lg:col-span-5 self-start lg:sticky lg:top-4" eyebrow={`Assessment #${a.id} · ${a.trigger.replaceAll("_", " ")}`}
          title={t ? <Link to={`/tickets/${t.id}`} className="hover:underline">#{t.id} {t.subject || "(no subject)"}</Link> : `Ticket #${a.ticket_id}`}
          icon={ShieldCheck}>
      <div className="space-y-4 text-sm">
        {/* Ticket handling, shown separately: integrity never changes it */}
        {t && (
          <section aria-label="Ticket handling" className="rounded-2xl bg-sunken p-3">
            <p className="eyebrow mb-1.5">Ticket handling (unchanged by this review)</p>
            <div className="flex flex-wrap items-center gap-1.5">
              <RouteBadge route={t.route} />
              <span className="chip bg-card text-ink-2 border border-line num">priority {t.priority}</span>
              <span className="chip bg-card text-ink-2 border border-line">{SLA_TEXT[t.sla_status]}</span>
              {t.critical_flags.map((f) => <span key={f} className="chip bg-senior-soft text-senior-text"><AlertTriangle className="w-3 h-3" aria-hidden /> {f}</span>)}
            </div>
          </section>
        )}

        <section aria-label="Review state" className="flex flex-wrap items-center gap-2">
          <StateChip state={a.review_state} />
          {a.status !== "complete" && <span className="chip bg-sunken text-ink-3">{a.status === "pending" ? "Assessment running…" : `Assessment failed (${a.error})`}</span>}
          {a.policy_reasons.map((r) => <span key={r} className="chip bg-sunken text-ink-2">{reasonText(r)}</span>)}
        </section>

        <section aria-label="Writing patterns">
          <p className="eyebrow mb-1">Writing patterns</p>
          <p className="font-semibold">{aiText(a.ai_status, a.ai_score, threshold)}</p>
          {a.ai_status === "assessed" && (
            <p className="text-xs text-ink-3 mt-0.5 num">
              Detector score (not a probability): average {a.ai_score?.toFixed(2)}, highest {a.ai_score_max?.toFixed(2)} ·
              {" "}{a.ai_chunk_count} window{a.ai_chunk_count === 1 ? "" : "s"} · {a.ai_word_count} words
            </p>
          )}
          {a.ai_reason && a.ai_status !== "assessed" && <p className="text-xs text-ink-3 mt-0.5">Reason: {a.ai_reason.replaceAll("_", " ")}</p>}
          <p className="text-xs text-ink-3 mt-0.5 break-all">Model: {a.model_name ?? "—"}{a.model_version ? ` (${a.model_version})` : ""}</p>
          <details className="mt-1">
            <summary className="text-xs font-semibold text-glacier-text cursor-pointer">Limitations</summary>
            <ul className="mt-1 list-disc pl-5 text-xs text-ink-2 space-y-0.5">{a.ai_limitations.map((l) => <li key={l}>{l}</li>)}</ul>
          </details>
        </section>

        <section aria-label="Similar tickets">
          <p className="eyebrow mb-1">Near-identical tickets</p>
          {a.related.length === 0 ? (
            <p className="text-ink-2">None found{a.duplicate_max_similarity != null ? ` (closest similarity ${a.duplicate_max_similarity.toFixed(2)}, ${a.duplicate_method})` : ""}.</p>
          ) : (
            <>
              <p className="text-ink-2">{a.related.length} found ({a.duplicate_method}).</p>
              {!related ? (
                <button className="btn-ghost !py-1 !px-2.5 !text-xs mt-1" onClick={async () => setRelated(await api.integrityRelated(id))}>
                  <Copy className="w-3.5 h-3.5" aria-hidden /> View related tickets
                </button>
              ) : (
                <ul className="mt-1.5 space-y-1.5">
                  {related.map((r) => (
                    <li key={r.ticket_id} className="rounded-xl border border-line p-2">
                      <div className="flex flex-wrap items-center gap-1.5 text-xs">
                        <Link to={`/tickets/${r.ticket_id}`} className="font-semibold hover:underline">#{r.ticket_id} {r.subject}</Link>
                        <span className="chip bg-sunken text-ink-2 num">similarity {r.similarity.toFixed(2)}</span>
                        <span className="chip bg-sunken text-ink-2">{r.same_customer ? "same customer" : "other customer"}</span>
                        {r.shared_issue && <span className="chip bg-sunken text-ink-2">shared issue</span>}
                      </div>
                      <p className="text-xs text-ink-3 mt-1 line-clamp-2">{r.excerpt}</p>
                    </li>
                  ))}
                </ul>
              )}
            </>
          )}
        </section>

        <section aria-label="Consistency with records">
          <p className="eyebrow mb-1">Consistency with our records</p>
          <p className="font-semibold">{CONSISTENCY[a.consistency_status] ?? a.consistency_status}</p>
          {a.consistency_findings.length > 0 && (
            <ul className="mt-1 space-y-0.5 text-xs text-ink-2">{a.consistency_findings.map((f, i) => <li key={i}>• {CONSISTENCY[f.status]}: {f.detail}</li>)}</ul>
          )}
        </section>

        <section aria-label="Indicators">
          <p className="eyebrow mb-1">Indicators</p>
          {a.manipulation_indicators.length === 0 ? <p className="text-ink-2">None.</p> : (
            <ul className="space-y-0.5 text-xs text-ink-2">{a.manipulation_indicators.map((m) => <li key={m.code}>• <b>{m.code.replaceAll("_", " ")}</b>: {m.detail}</li>)}</ul>
          )}
        </section>

        {a.document_findings.length > 0 && (
          <section aria-label="Documents">
            <p className="eyebrow mb-1">Customer documents</p>
            <ul className="space-y-1 text-xs text-ink-2">
              {a.document_findings.map((d) => (
                <li key={d.attachment_id} className="flex flex-wrap items-center gap-1.5">
                  <FileText className="w-3.5 h-3.5" aria-hidden /> <span className="font-semibold">{d.filename}</span>
                  <span className="chip bg-sunken text-ink-2">{d.status === "extracted" ? "read" : d.status === "needs_ocr" ? "could not be fully analysed" : d.status.replaceAll("_", " ")}</span>
                  {d.status === "extracted" && <span>{aiText(d.ai_status, d.ai_score, threshold)}{d.ai_score != null ? ` · detector score ${d.ai_score.toFixed(2)}` : ""}</span>}
                </li>
              ))}
            </ul>
          </section>
        )}

        <section aria-label="Actions" className="flex flex-wrap gap-2 pt-1 border-t border-line">
          <button className="btn-ghost !text-xs" disabled={!done || busy || a.review_state === "under_review"} onClick={() => act("start_review")}>
            <Scale className="w-3.5 h-3.5" aria-hidden /> Start review
          </button>
          <button className="btn-ghost !text-xs" disabled={!done || busy} onClick={() => setDialog("dismiss")}>Dismiss</button>
          <button className="btn-ghost !text-xs" disabled={!done || busy} onClick={() => setDialog("confirm")}>Confirm concern</button>
          <button className="btn-ghost !text-xs" disabled={busy} onClick={() => setDialog("reassess")}>
            <RefreshCw className="w-3.5 h-3.5" aria-hidden /> Reassess
          </button>
          <button className="btn-ghost !text-xs" disabled={busy} onClick={async () => setHistory(await api.integrityHistory(id))}>
            <History className="w-3.5 h-3.5" aria-hidden /> History
          </button>
        </section>

        {history && (
          <section aria-label="Review history">
            <p className="eyebrow mb-1">Review history</p>
            {history.length === 0 ? <p className="text-ink-2">No review actions yet.</p> : (
              <ol className="space-y-1 text-xs">
                {history.map((h) => (
                  <li key={h.id} className="text-ink-2">
                    <b>{h.action.replaceAll("_", " ")}</b> by {h.actor_name} · {new Date(h.created_at).toLocaleString()} · assessment #{h.assessment_id}
                    {h.reason && <span className="block text-ink-3">“{h.reason}”</span>}
                  </li>
                ))}
              </ol>
            )}
          </section>
        )}
        <p className="text-[11px] text-ink-3">Policy {a.policy_version} · assessment v{a.assessment_version} · created {timeAgo(a.created_at)}</p>
      </div>

      <ConfirmDialog open={dialog === "dismiss"} title="Dismiss this assessment?" busy={busy} reasonMode="optional" confirmLabel="Dismiss"
                     body="Nothing about the ticket changes. You can add a note for the record." onCancel={() => setDialog(null)}
                     onConfirm={(r) => act("dismiss", r)} />
      <ConfirmDialog open={dialog === "confirm"} title="Confirm an integrity concern?" busy={busy} reasonMode="required" confirmLabel="Confirm concern"
                     body="Only confirm after checking the evidence yourself. Writing patterns alone are never enough. Your name, the time and your reason are recorded."
                     onCancel={() => setDialog(null)} onConfirm={(r) => act("confirm", r)} />
      <ConfirmDialog open={dialog === "reassess"} title="Reassess this ticket?" busy={busy} confirmLabel="Reassess"
                     body="A new assessment is added; earlier ones and their history are kept." onCancel={() => setDialog(null)} onConfirm={reassess} />
    </Tile>
  );
}

export function AdminIntegrity() {
  const [params, setParams] = useSearchParams();
  const selected = params.get("a") ? Number(params.get("a")) : null;
  const [filters, setFilters] = useState({ review_state: "", ai_status: "", has_duplicates: "", date_from: "", date_to: "", q: "", sort: "newest" });
  const [page, setPage] = useState(1);
  const [qInput, setQInput] = useState("");
  const { data: status } = useLiveData(() => api.integrityStatus(), { intervalMs: 60000 });
  const { data, error, loading, reload } = useLiveData(
    () => api.integrityList({ ...filters, page, page_size: 20 }),
    { match: (ev) => ev.type?.startsWith("integrity."), intervalMs: 20000, deps: [JSON.stringify(filters), page] },
  );
  useEffect(() => { const id = setTimeout(() => { setPage(1); setFilters((f) => ({ ...f, q: qInput.trim() })); }, 300); return () => clearTimeout(id); }, [qInput]);

  const setFilter = (k, v) => { setPage(1); setFilters((f) => ({ ...f, [k]: v })); };
  const select = (id) => setParams(id ? { a: String(id) } : {});
  const threshold = status?.review_threshold ?? 0.8;
  const stats = data?.stats;
  const pages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1;

  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 pt-2">
      <PageHeader title="Integrity"
                  subtitle="A review aid for admins: it points out things worth a human look. It never changes priority, routing or what customers see, and it never decides anything on its own."
                  badges={status && (
                    <span className={clsx("chip", status.enabled ? "bg-tier1-soft text-tier1-text" : "bg-sunken text-ink-3")}>
                      {status.enabled ? "On" : "Off"} · detector {status.model_check === "ok" ? "ready" : status.model_check.replaceAll("_", " ")}
                    </span>
                  )} />

      {status && !status.enabled && (
        <div className="lg:col-span-12 rounded-2xl bg-sunken p-3 text-sm text-ink-2 flex gap-2">
          <Info className="w-4 h-4 mt-0.5 shrink-0" aria-hidden />
          The analyzer is switched off, so new tickets aren't assessed. Set <code className="font-mono">AI_INTEGRITY_ENABLED=true</code> in <code className="font-mono">backend/.env</code> and restart the backend.
        </div>
      )}

      <section className="lg:col-span-12 grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3" aria-label="Summary">
        {!stats ? Array.from({ length: 6 }).map((_, i) => <div key={i} className="h-20 rounded-3xl bg-card border border-line animate-pulse" />) : (
          [["Assessed tickets", stats.total], ...REVIEW_ORDER.map((s) => [REVIEW[s].label, stats.by_review_state[s] ?? 0, s])].map(([label, n, s]) => (
            <button key={label} type="button" onClick={() => s && setFilter("review_state", filters.review_state === s ? "" : s)}
                    className={clsx("rounded-3xl bg-card border p-3 text-left transition", filters.review_state === s && s ? "border-glacier" : "border-line hover:border-ink-3")}>
              <p className="text-2xl font-extrabold num">{n}</p>
              <p className="text-xs text-ink-3">{label}</p>
            </button>
          ))
        )}
      </section>

      <Tile className={selected ? "lg:col-span-7" : "lg:col-span-12"} eyebrow="Latest assessment per ticket" title="Review queue" icon={Sparkles}
            action={<button className="btn-ghost !py-1 !px-2.5 !text-xs" onClick={reload} disabled={loading}>{loading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : "Refresh"}</button>}>
        <div className="flex flex-wrap gap-2 mb-3">
          <input className="field !py-1.5 w-48" placeholder="Search subject or #id" value={qInput} onChange={(e) => setQInput(e.target.value)} aria-label="Search" />
          <select className="field !py-1.5 w-44" value={filters.review_state} onChange={(e) => setFilter("review_state", e.target.value)} aria-label="Review state">
            <option value="">All review states</option>
            {REVIEW_ORDER.map((s) => <option key={s} value={s}>{REVIEW[s].label}</option>)}
          </select>
          <select className="field !py-1.5 w-44" value={filters.ai_status} onChange={(e) => setFilter("ai_status", e.target.value)} aria-label="Writing-pattern check">
            <option value="">All writing checks</option>
            <option value="assessed">Assessed</option>
            {Object.entries(AI_TEXT).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
          <select className="field !py-1.5 w-40" value={filters.has_duplicates} onChange={(e) => setFilter("has_duplicates", e.target.value)} aria-label="Near-identical tickets">
            <option value="">Any duplicates</option>
            <option value="true">Has near-identical</option>
            <option value="false">None</option>
          </select>
          <input type="date" className="field !py-1.5 w-40" value={filters.date_from} onChange={(e) => setFilter("date_from", e.target.value)} aria-label="From date" />
          <input type="date" className="field !py-1.5 w-40" value={filters.date_to} onChange={(e) => setFilter("date_to", e.target.value)} aria-label="To date" />
          <select className="field !py-1.5 w-36" value={filters.sort} onChange={(e) => setFilter("sort", e.target.value)} aria-label="Sort">
            <option value="newest">Newest first</option>
            <option value="oldest">Oldest first</option>
            <option value="priority">Highest priority</option>
          </select>
        </div>

        {error && <ErrorNote>{error}</ErrorNote>}
        {!data ? <SkeletonLines rows={8} /> : data.items.length === 0 ? (
          <Empty icon={ShieldCheck}>{stats?.total ? "No assessments match these filters." : "No assessments yet. They appear here once the analyzer is on and customers create tickets or reply."}</Empty>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead><tr className="text-left text-[11px] uppercase tracking-wider text-ink-3">
                  {["Ticket", "Level · priority", "Emergency", "Reply-by", "Review", "Writing check", "Near-identical", "When"].map((h) => <th key={h} className="py-2 pr-3 font-semibold whitespace-nowrap">{h}</th>)}
                </tr></thead>
                <tbody className="divide-y divide-line">
                  {data.items.map((a) => (
                    <tr key={a.id} onClick={() => select(a.id)} tabIndex={0} onKeyDown={(e) => e.key === "Enter" && select(a.id)}
                        className={clsx("cursor-pointer hover:bg-sunken focus:outline-none focus:bg-sunken", selected === a.id && "bg-sunken")}
                        aria-selected={selected === a.id}>
                      <td className="py-2.5 pr-3 max-w-[220px]">
                        <p className="font-semibold truncate">#{a.ticket_id} {a.ticket?.subject || "(no subject)"}</p>
                        <p className="text-xs text-ink-3">{a.ticket?.category}</p>
                      </td>
                      <td className="py-2.5 pr-3 whitespace-nowrap">{a.ticket && <><RouteBadge route={a.ticket.route} /> <span className="num text-ink-2">{a.ticket.priority}</span></>}</td>
                      <td className="py-2.5 pr-3">{a.ticket?.critical_flags.length ? a.ticket.critical_flags.map((f) => <span key={f} className="chip bg-senior-soft text-senior-text mr-1">{f}</span>) : <span className="text-ink-3">—</span>}</td>
                      <td className="py-2.5 pr-3 text-xs text-ink-2 whitespace-nowrap">{a.ticket ? SLA_TEXT[a.ticket.sla_status] : "—"}</td>
                      <td className="py-2.5 pr-3">{a.status === "pending" ? <span className="chip bg-sunken text-ink-3">running…</span> : <StateChip state={a.review_state} />}</td>
                      <td className="py-2.5 pr-3 text-xs text-ink-2 max-w-[180px]">{a.status === "pending" ? "—" : aiText(a.ai_status, a.ai_score, threshold)}</td>
                      <td className="py-2.5 pr-3 num">{a.duplicate_count || <span className="text-ink-3">0</span>}</td>
                      <td className="py-2.5 text-xs text-ink-3 whitespace-nowrap">{timeAgo(a.created_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="flex items-center justify-between mt-3 text-xs text-ink-3">
              <span className="num">{data.total} result{data.total === 1 ? "" : "s"}</span>
              <div className="flex items-center gap-1">
                <button className="btn-ghost !p-1.5" disabled={page <= 1} onClick={() => setPage((p) => p - 1)} aria-label="Previous page"><ChevronLeft className="w-4 h-4" /></button>
                <span className="num">Page {page} of {pages}</span>
                <button className="btn-ghost !p-1.5" disabled={page >= pages} onClick={() => setPage((p) => p + 1)} aria-label="Next page"><ChevronRight className="w-4 h-4" /></button>
              </div>
            </div>
          </>
        )}
      </Tile>

      {selected && <Detail id={selected} threshold={threshold} onChanged={reload} />}
    </div>
  );
}
