import { useEffect, useState } from "react";
import {
  AlertTriangle, BookOpen, Brain, CheckCircle2, Gavel, Loader2, Lock, MousePointerClick, ScanSearch, ThumbsDown, ThumbsUp, UserRound,
} from "lucide-react";
import { api } from "../../api.js";
import {
  BOOST_LABEL, COMPONENT_LABEL, COMPONENT_ORDER, INTENT_LABEL, SEGMENT_LABEL, SIGNAL_LABEL, STATUS_LABEL, VALUE_LABEL, fmtWait, isOpen, pct,
} from "../../lib/meta.js";
import { Empty, ErrorNote, MeterRow, RouteBadge, Tile, useToast } from "../ui.jsx";

function Card({ title, icon: Icon, children, className = "" }) {
  return (
    <div className={`rounded-2xl border border-line p-4 ${className}`}>
      <p className="eyebrow flex items-center gap-1.5 mb-2.5">
        {Icon && <Icon className="w-3.5 h-3.5" aria-hidden />} {title}
      </p>
      {children}
    </div>
  );
}

export default function DetailTile({ ticket, onChanged }) {
  const toast = useToast();
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

  const run = async (key, fn, okMessage) => {
    setBusy(key);
    setError("");
    try {
      await fn();
      toast(okMessage, "success");
      await onChanged?.();
    } catch (err) {
      setError(err.message);
      toast(err.message, "error");
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
  const open = isOpen(t);
  const overrideValid = reason.trim().length >= 3 && (route || priority !== "");
  const boosts = Object.entries(t.boosts || {}).filter(([, v]) => v > 0);
  const slaRatio = t.wait_minutes / t.sla_minutes;
  const signals = t.analysis.signals || {};

  return (
    <Tile
      eyebrow={`Ticket #${t.id} · ${STATUS_LABEL[t.status] ?? t.status}`}
      title={t.subject || (INTENT_LABEL[t.analysis.intent] ?? "Ticket")}
      icon={ScanSearch}
      className="lg:col-span-8"
      action={
        <div className="text-right">
          <p className="text-4xl font-extrabold num leading-none">{t.priority}</p>
          <p className="text-[10px] uppercase tracking-wider text-ink-3 mt-1">
            {t.priority_locked ? "priority set by agent" : "priority / 100"}
          </p>
        </div>
      }
    >
      <div className="grid gap-4 md:grid-cols-2">
        {/* ---------------- left: message + score breakdown */}
        <div className="space-y-4 min-w-0">
          <div className="rounded-2xl bg-sunken p-4">
            <p className="text-xs text-ink-3 mb-1.5 flex flex-wrap gap-x-2">
              <span>{t.customer ? `${t.customer.name} · ${SEGMENT_LABEL[t.customer.segment] ?? t.customer.segment}` : "Unknown customer"}</span>
              <span>· {t.channel}</span>
              {t.analysis.language === "hi-en" && <span>· Hinglish</span>}
            </p>
            <p className="text-sm text-ink whitespace-pre-wrap break-words">{t.body}</p>
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
                  title={`${COMPONENT_LABEL[k]} ${pct(t.components[k] ?? 0)} adds ${t.contributions[k] ?? 0} points`}
                />
              ))}
            </div>
            {boosts.length > 0 && (
              <ul className="mt-3 flex flex-wrap gap-1.5">
                {boosts.map(([k, v]) => (
                  <li key={k} className="chip bg-tier2-soft text-tier2-text">+{Math.round(v)} {BOOST_LABEL[k] ?? k}</li>
                ))}
              </ul>
            )}
          </div>

          {open && (
            <div>
              <div className="flex justify-between text-xs mb-1">
                <span className="font-medium text-ink-2">Waiting vs SLA</span>
                <span className="font-semibold num">{fmtWait(t.wait_minutes)} / {fmtWait(t.sla_minutes)}</span>
              </div>
              <div className="h-2 rounded-full bg-sunken overflow-hidden">
                <div className="h-full rounded-full transition-[width] duration-500"
                     style={{ width: `${Math.min(slaRatio, 1) * 100}%`,
                              background: slaRatio >= 1 ? "rgb(var(--senior))" : slaRatio >= 0.75 ? "rgb(var(--tier2))" : "rgb(var(--tier1))" }} />
              </div>
              <p className="mt-1 text-[11px] text-ink-3">From 75% of the SLA the ticket gains up to +50 points so it is served before it breaches.</p>
            </div>
          )}
        </div>

        {/* ---------------- right: routing, AI read, KB, actions */}
        <div className="space-y-4 min-w-0">
          <Card title="Routed to" icon={UserRound}>
            <div className="flex items-center justify-between gap-2 flex-wrap">
              <RouteBadge route={t.route} />
              <div className="flex gap-1.5">
                {t.route_locked && <span className="chip bg-sunken text-ink-2" title="Agent override; ageing will not move it"><Lock className="w-3 h-3" aria-hidden /> locked</span>}
                {t.manager_flag && <span className="chip bg-senior-soft text-senior-text"><Gavel className="w-3 h-3" aria-hidden /> manager notified</span>}
              </div>
            </div>
            <p className="mt-2 text-sm font-medium">{t.route_reason}</p>
            {t.reasons.length > 0 && (
              <ul className="mt-2 space-y-1">
                {t.reasons.map((r) => (
                  <li key={r} className="text-xs text-ink-2 flex gap-2"><span className="text-glacier" aria-hidden>●</span>{r}</li>
                ))}
              </ul>
            )}
            {t.assigned_agent && (
              <p className="mt-2 text-xs text-ink-3">Assigned to <span className="font-semibold text-ink-2">{t.assigned_agent.name}</span> ({t.assigned_agent.level})</p>
            )}
          </Card>

          <Card title={`How the ${t.analysis.mode === "hf" ? "AI models" : "rules"} read it`} icon={Brain}>
            <div className="flex flex-wrap gap-1.5 mb-3">
              <span className="chip bg-sunken text-ink-2">{INTENT_LABEL[t.analysis.intent] ?? t.analysis.intent}</span>
              <span className="chip bg-sunken text-ink-2">confidence {pct(t.analysis.confidence)}</span>
              {t.analysis.critical_flags.map((f) => (
                <span key={f} className="chip bg-senior-soft text-senior-text"><AlertTriangle className="w-3 h-3" aria-hidden /> {f}</span>
              ))}
            </div>
            <div className="grid grid-cols-2 gap-x-4 gap-y-2">
              {["neg", "anger", "style", "churn"].map((k) => (
                <MeterRow key={k} compact label={SIGNAL_LABEL[k]} value={signals[k] ?? 0} display={pct(signals[k] ?? 0)}
                          color="rgb(var(--senior))" title={`${SIGNAL_LABEL[k]} signal feeding the frustration score`} />
              ))}
            </div>
            {Object.keys(t.value_parts || {}).length > 0 && (
              <>
                <p className="eyebrow mt-3 mb-2">Customer value {pct(t.components.value)}</p>
                <div className="grid grid-cols-2 gap-x-4 gap-y-2">
                  {Object.entries(t.value_parts).map(([k, v]) => (
                    <MeterRow key={k} compact label={VALUE_LABEL[k] ?? k} value={v} display={pct(v)} color="rgb(var(--auto))" />
                  ))}
                </div>
              </>
            )}
          </Card>

          {(t.kb.action !== "none" || t.status === "kb_handled") && t.kb.title && (
            <div className="rounded-2xl bg-auto-soft/70 border border-auto/20 p-4">
              <div className="flex items-center justify-between gap-2">
                <span className="eyebrow flex items-center gap-1.5 !text-auto-text">
                  <BookOpen className="w-3.5 h-3.5" aria-hidden />
                  {t.kb.action === "auto_reply" ? "Answered automatically" : "Suggested article"}
                </span>
                <span className="text-xs font-semibold num">{pct(t.kb.confidence)} match</span>
              </div>
              <p className="mt-1.5 text-sm font-semibold">{t.kb.title}</p>
              <p className="mt-1 text-xs text-ink-2 whitespace-pre-wrap">{t.kb.answer}</p>
              <p className="mt-1 text-[11px] text-ink-3">{t.kb.source}</p>
              {t.kb.rated ? (
                <p className="mt-3 text-xs text-ink-3">Feedback recorded.</p>
              ) : (
                <div className="mt-3 flex flex-wrap gap-2">
                  <button className="btn-ghost !py-1.5 !text-xs bg-card" disabled={!!busy}
                          onClick={() => run("up", () => api.feedback(t.id, { kind: "kb_helpful" }), "Marked as helpful")}>
                    <ThumbsUp className="w-3.5 h-3.5" /> Helped
                  </button>
                  <button className="btn-ghost !py-1.5 !text-xs bg-card" disabled={!!busy}
                          onClick={() => run("down", () => api.feedback(t.id, { kind: "kb_not_helpful" }),
                                             t.status === "kb_handled" ? "Escalated to a human agent" : "Feedback recorded")}>
                    <ThumbsDown className="w-3.5 h-3.5" /> Didn't help
                  </button>
                </div>
              )}
            </div>
          )}

          {open && (
            <form
              className="rounded-2xl border border-line p-4 space-y-2.5"
              onSubmit={(e) => {
                e.preventDefault();
                if (!overrideValid) return;
                run("override", () => api.override(t.id, {
                  route: route || null,
                  priority: priority === "" ? null : Number(priority),
                  reason: reason.trim(),
                }), "Override saved and logged as feedback");
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
                <input className="field" type="number" min={0} max={100} value={priority}
                       onChange={(e) => setPriority(e.target.value)} placeholder="Priority 0-100" aria-label="New priority" />
              </div>
              <input className="field" value={reason} onChange={(e) => setReason(e.target.value)}
                     placeholder="Reason (required, becomes training feedback)" aria-label="Reason" />
              <div className="flex gap-2">
                <button type="submit" className="btn-primary flex-1" disabled={!overrideValid || !!busy}>
                  {busy === "override" && <Loader2 className="w-4 h-4 animate-spin" />}
                  Override
                </button>
                <button type="button" className="btn-ghost" disabled={!!busy}
                        onClick={() => run("resolve", () => api.resolve(t.id), `Ticket #${t.id} resolved`)}>
                  {busy === "resolve" ? <Loader2 className="w-4 h-4 animate-spin" /> : <CheckCircle2 className="w-4 h-4" />}
                  Resolve
                </button>
              </div>
            </form>
          )}
          {error && <ErrorNote>{error}</ErrorNote>}
        </div>
      </div>
    </Tile>
  );
}
