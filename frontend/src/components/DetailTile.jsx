import { useEffect, useState } from "react";
import { AlertTriangle, BookOpen, CheckCircle2, Loader2, Lock, MousePointerClick, ScanSearch, ThumbsDown, ThumbsUp } from "lucide-react";
import { api } from "../api.js";
import { COMPONENT_LABEL, SEGMENT_LABEL, STATUS_LABEL, fmtWait, pct } from "../lib/meta.js";
import { Empty, MeterRow, RouteBadge, Tile } from "./ui.jsx";

const COMPONENT_ORDER = ["urgency", "frustration", "value", "age"];

export default function DetailTile({ ticket, onChanged }) {
  const [route, setRoute] = useState("");
  const [priority, setPriority] = useState("");
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    setRoute("");
    setPriority("");
    setReason("");
    setError("");
  }, [ticket?.id]);

  const run = async (key, fn) => {
    setBusy(key);
    setError("");
    try {
      await fn();
      await onChanged?.();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy("");
    }
  };

  if (!ticket) {
    return (
      <Tile eyebrow="Ticket detail" title="Why this score?" icon={ScanSearch} className="lg:col-span-8">
        <Empty icon={MousePointerClick}>Select a ticket in the queue to see its signals, reasons and actions.</Empty>
      </Tile>
    );
  }

  const t = ticket;
  const isOpen = ["queued", "in_progress"].includes(t.status);
  const overrideValid = reason.trim().length >= 3 && (route || priority !== "");

  return (
    <Tile
      eyebrow={`Ticket #${t.id} · ${STATUS_LABEL[t.status] ?? t.status}`}
      title={t.subject || "No subject"}
      icon={ScanSearch}
      className="lg:col-span-8"
      action={
        <div className="text-right">
          <p className="text-4xl font-extrabold tabular-nums leading-none">{t.priority}</p>
          <p className="text-[10px] uppercase tracking-wider text-nordic-muted mt-1">priority / 100</p>
        </div>
      }
    >
      <div className="grid gap-5 md:grid-cols-2">
        {/* Left: message + signals */}
        <div className="space-y-4 min-w-0">
          <div className="rounded-2xl bg-nordic-frost p-4">
            <p className="text-xs text-nordic-muted mb-1.5">
              {t.customer ? `${t.customer.name} · ${SEGMENT_LABEL[t.customer.segment] ?? t.customer.segment}` : "Unknown customer"}
              {" · "}waiting {fmtWait(t.wait_minutes)}
            </p>
            <p className="text-sm text-nordic-dark whitespace-pre-wrap break-words">{t.body}</p>
          </div>

          <div>
            <p className="eyebrow mb-2">Signals → score points</p>
            <div className="space-y-3">
              {COMPONENT_ORDER.map((k) => (
                <MeterRow
                  key={k}
                  label={COMPONENT_LABEL[k]}
                  value={t.components[k] ?? 0}
                  display={pct(t.components[k] ?? 0)}
                  sub={t.contributions[k] != null ? `+${t.contributions[k]} pts` : undefined}
                  title={`${COMPONENT_LABEL[k]}: ${pct(t.components[k] ?? 0)} contributes ${t.contributions[k] ?? 0} points`}
                />
              ))}
            </div>
          </div>

          <div className="flex flex-wrap gap-1.5 text-xs">
            <span className="chip bg-slate-100 text-nordic-slate">intent: {t.analysis.intent}</span>
            <span className="chip bg-slate-100 text-nordic-slate">nlp: {t.analysis.mode}</span>
            {t.analysis.critical_flags.map((f) => (
              <span key={f} className="chip bg-nordic-lingonberryLight text-nordic-lingonberry">
                <AlertTriangle className="w-3 h-3" aria-hidden /> {f}
              </span>
            ))}
          </div>
        </div>

        {/* Right: routing, KB, actions */}
        <div className="space-y-4 min-w-0">
          <div className="rounded-2xl border border-nordic-border p-4">
            <div className="flex items-center justify-between gap-2">
              <span className="eyebrow">Routed to</span>
              <div className="flex items-center gap-1.5">
                {t.route_locked && (
                  <span className="chip bg-slate-100 text-nordic-slate" title="Agent override; ageing will not change the route">
                    <Lock className="w-3 h-3" aria-hidden /> locked
                  </span>
                )}
                <RouteBadge route={t.route} />
              </div>
            </div>
            <p className="mt-2 text-sm font-medium">{t.route_reason}</p>
            {t.reasons.length > 0 && (
              <ul className="mt-2 space-y-1">
                {t.reasons.map((r) => (
                  <li key={r} className="text-xs text-nordic-slate flex gap-2">
                    <span className="text-nordic-glacier" aria-hidden>●</span>
                    {r}
                  </li>
                ))}
              </ul>
            )}
            {t.assigned_agent_id && <p className="mt-2 text-xs text-nordic-muted">Assigned agent #{t.assigned_agent_id}</p>}
          </div>

          {t.kb.action !== "none" && (
            <div className="rounded-2xl bg-nordic-auroraLight/60 border border-indigo-100 p-4">
              <div className="flex items-center justify-between">
                <span className="eyebrow flex items-center gap-1.5 !text-nordic-aurora">
                  <BookOpen className="w-3.5 h-3.5" aria-hidden />
                  {t.kb.action === "auto_reply" ? "Auto-answered" : "Suggested article"}
                </span>
                <span className="text-xs font-semibold tabular-nums">{pct(t.kb.confidence)} match</span>
              </div>
              <p className="mt-1.5 text-sm font-semibold">{t.kb.title}</p>
              {t.auto_reply && <p className="mt-1.5 text-xs text-nordic-slate whitespace-pre-wrap">{t.auto_reply}</p>}
              <div className="mt-3 flex gap-2">
                <button className="btn-ghost !py-1.5 !text-xs bg-white" disabled={!!busy} onClick={() => run("up", () => api.feedback(t.id, { kind: "kb_helpful" }))}>
                  <ThumbsUp className="w-3.5 h-3.5" /> Helped
                </button>
                <button className="btn-ghost !py-1.5 !text-xs bg-white" disabled={!!busy} onClick={() => run("down", () => api.feedback(t.id, { kind: "kb_not_helpful" }))}>
                  <ThumbsDown className="w-3.5 h-3.5" /> Didn't help
                </button>
              </div>
            </div>
          )}

          {isOpen && (
            <form
              className="rounded-2xl border border-nordic-border p-4 space-y-2.5"
              onSubmit={(e) => {
                e.preventDefault();
                if (!overrideValid) return;
                run("override", () =>
                  api.override(t.id, {
                    route: route || null,
                    priority: priority === "" ? null : Number(priority),
                    reason: reason.trim(),
                  }),
                );
              }}
            >
              <p className="eyebrow">Agent override</p>
              <div className="grid grid-cols-2 gap-2">
                <select className="field" value={route} onChange={(e) => setRoute(e.target.value)} aria-label="New route">
                  <option value="">Keep route</option>
                  <option value="tier1">Tier 1</option>
                  <option value="tier2">Tier 2</option>
                  <option value="senior">Senior</option>
                </select>
                <input
                  className="field"
                  type="number"
                  min={0}
                  max={100}
                  value={priority}
                  onChange={(e) => setPriority(e.target.value)}
                  placeholder="Priority"
                  aria-label="New priority"
                />
              </div>
              <input className="field" value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Reason (required, logged as feedback)" />
              <div className="flex gap-2">
                <button type="submit" className="btn-primary flex-1" disabled={!overrideValid || !!busy}>
                  {busy === "override" && <Loader2 className="w-4 h-4 animate-spin" />}
                  Override
                </button>
                <button type="button" className="btn-ghost" disabled={!!busy} onClick={() => run("resolve", () => api.resolve(t.id))}>
                  {busy === "resolve" ? <Loader2 className="w-4 h-4 animate-spin" /> : <CheckCircle2 className="w-4 h-4" />}
                  Resolve
                </button>
              </div>
            </form>
          )}
          {error && <p className="text-xs text-nordic-lingonberry">{error}</p>}
        </div>
      </div>
    </Tile>
  );
}
