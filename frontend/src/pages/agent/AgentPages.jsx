import { useEffect, useMemo, useState } from "react";
import { HandoverPanel, SummaryButton } from "../../components/Summary.jsx";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  Activity, ArrowLeft, ArrowUpCircle, Boxes, CheckCircle2, ChevronDown, Compass, Hand, Loader2, Lock, Paperclip, Radio, UserRound,
} from "lucide-react";
import { api } from "../../api.js";
import { useAuth } from "../../lib/auth.jsx";
import { useEventListener, useLiveData } from "../../lib/events.jsx";
import { OPEN_STATUSES, SEGMENT_LABEL, STATUS_LABEL, isOpen, levelTitle, routeMeta, timeAgo } from "../../lib/meta.js";
import QueueTile from "../../components/live/QueueTile.jsx";
import TicketExplain from "../../components/TicketExplain.jsx";
import { CallbackPanel, Conversation } from "../../components/Conversation.jsx";
import { ErrorNote, PageHeader, RouteBadge, Skeleton, SkeletonLines, Tile, useToast } from "../../components/ui.jsx";
import { AttachmentList } from "../../components/Attachments.jsx";

const NEXT = { level1: "level2", level2: "level3" };

async function loadAgentTickets() {
  const [queue, mine, resolved] = await Promise.all([
    api.tickets({ view: "queue" }), api.tickets({ view: "mine" }), api.tickets({ view: "resolved" }),
  ]);
  const byId = new Map();
  [...queue, ...mine, ...resolved].forEach((t) => byId.set(t.id, t));
  return [...byId.values()].sort((a, b) => b.priority - a.priority || new Date(a.created_at) - new Date(b.created_at));
}

export function AgentQueuePage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const { data: tickets, error } = useLiveData(loadAgentTickets, {
    match: (ev) => ev.ticket_id != null || ev.type === "queue.rescored",
  });
  const [feed, setFeed] = useState([]);

  useEventListener((ev) => {
    if (!ev.ticket_id || ev.type === "typing") return;
    const text = {
      "ticket.created": `New ticket #${ev.ticket_id}`,
      "ticket.escalated": ev.route === user.role ? `#${ev.ticket_id} escalated in from ${routeMeta(ev.old_route).label}`
        : `#${ev.ticket_id} moved up to ${routeMeta(ev.route).label}`,
      "message.created": ev.author_role === "customer" ? `Customer replied on #${ev.ticket_id}` : null,
      "callback.requested": `Call requested on #${ev.ticket_id}`,
      "ticket.resolved": `#${ev.ticket_id} resolved`,
    }[ev.type];
    if (text) setFeed((f) => [{ id: `${Date.now()}-${Math.random()}`, text, at: new Date().toISOString(), tid: ev.ticket_id }, ...f].slice(0, 12));
  });

  const tabs = useMemo(() => [
    { value: "queue", label: "Level queue", match: (t) => t.route === user.role && OPEN_STATUSES.includes(t.status) },
    { value: "mine", label: "Assigned to me", match: (t) => t.assigned_agent?.id === user.id && OPEN_STATUSES.includes(t.status) },
    { value: "resolved", label: "Resolved by me", match: (t) => t.status === "resolved" },
  ], [user]);

  const list = tickets ?? [];
  const queue = list.filter((t) => t.route === user.role && isOpen(t));
  const waiting = queue.filter((t) => t.status === "queued").length;
  const mine = list.filter((t) => t.assigned_agent?.id === user.id && t.status === "in_progress").length;
  const atRisk = queue.filter((t) => t.wait_minutes >= 0.75 * t.sla_minutes).length;
  const m = routeMeta(user.role);

  return (
    <div className="grid gap-4 lg:grid-cols-12 pt-2">
      <Tile dark className="lg:col-span-8" eyebrow="Your queue" icon={Radio}>
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="text-sm text-slate-400">{levelTitle(user.role)}</p>
            {tickets ? <p className="text-6xl font-extrabold text-white num leading-none mt-1">{queue.length}</p>
              : <Skeleton className="h-14 w-24 !bg-fjord-surface mt-1" />}
            <p className="mt-2 text-sm text-slate-400">open tickets at your level</p>
          </div>
          <dl className="flex gap-6 text-right">
            {[["waiting", waiting, "text-sky-300"], ["yours", mine, "text-teal-300"], ["near reply-by", atRisk, "text-amber-300"]].map(([k, v, c]) => (
              <div key={k}><dt className="text-xs text-slate-400">{k}</dt><dd className={`text-2xl font-bold num ${c}`}>{tickets ? v : "–"}</dd></div>
            ))}
          </dl>
        </div>
        <div className="mt-5 h-1.5 rounded-full" style={{ background: m.bar }} aria-hidden />
      </Tile>
      <Tile className="lg:col-span-4" eyebrow="Live activity" icon={Activity}>
        {feed.length === 0 ? <p className="text-sm text-ink-3">Escalations, new tickets and replies appear here as they happen.</p> : (
          <ul className="space-y-2 max-h-40 overflow-y-auto scroll-thin">
            {feed.map((f) => (
              <li key={f.id}><Link to={`/tickets/${f.tid}`} className="flex justify-between gap-2 text-sm hover:text-glacier-text">
                <span>{f.text}</span><span className="text-[11px] text-ink-3 shrink-0">{timeAgo(f.at)}</span></Link></li>
            ))}
          </ul>
        )}
      </Tile>
      {error && <div className="lg:col-span-12"><ErrorNote>{error}</ErrorNote></div>}
      <QueueTile tickets={list} loading={!tickets} onSelect={(id) => navigate(`/tickets/${id}`)} tabs={tabs}
                 title="Tickets" eyebrow={levelTitle(user.role)} className="lg:col-span-12" showRoute={false} />
    </div>
  );
}

function GuidesTile({ ticketId }) {
  const [guides, setGuides] = useState(null);
  const [open, setOpen] = useState(0);
  useEffect(() => { api.guides(ticketId).then(setGuides).catch(() => setGuides([])); }, [ticketId]);
  return (
    <Tile eyebrow="Guides for this ticket" icon={Compass}>
      {!guides ? <SkeletonLines rows={3} /> : guides.length === 0 ? (
        <p className="text-sm text-ink-3">No specific guide. Check the knowledge base if you're unsure.</p>
      ) : (
        <ul className="space-y-2">
          {guides.map((g, i) => (
            <li key={g.id} className="rounded-2xl border border-line">
              <button className="w-full text-left px-3.5 py-2.5 flex items-center gap-2" aria-expanded={open === i} onClick={() => setOpen(open === i ? -1 : i)}>
                <Lock className="w-3.5 h-3.5 text-ink-3 shrink-0" aria-hidden />
                <span className="text-sm font-semibold flex-1">{g.title}</span>
                <ChevronDown className={`w-4 h-4 text-ink-3 transition ${open === i ? "rotate-180" : ""}`} aria-hidden />
              </button>
              {open === i && <p className="px-3.5 pb-3 text-xs text-ink-2 whitespace-pre-wrap leading-relaxed">{g.answer}</p>}
            </li>
          ))}
        </ul>
      )}
    </Tile>
  );
}

export function StaffTicketPage() {
  const { id } = useParams();
  const ticketId = Number(id);
  const { user } = useAuth();
  const navigate = useNavigate();
  const toast = useToast();
  const { data: t, error, reload } = useLiveData(() => api.ticket(ticketId), {
    match: (ev) => ev.ticket_id === ticketId, deps: [ticketId],
  });
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState("");
  const admin = user.role === "admin";
  const backTo = admin ? "/admin" : "/queue";

  const act = async (key, fn, msg, after) => {
    setBusy(key);
    try {
      await fn();
      toast(msg, "success");
      if (after) after();
      else await reload();
    } catch (err) {
      toast(err.message, "error");
    } finally {
      setBusy("");
    }
  };

  if (error) {
    return (
      <div className="pt-6 space-y-3">
        <ErrorNote>{error.includes("not found") ? "This ticket is no longer at your level (it may have been escalated)." : error}</ErrorNote>
        <Link to={backTo} className="btn-ghost">Back to queue</Link>
      </div>
    );
  }
  if (!t) return <div className="pt-6"><SkeletonLines rows={8} /></div>;

  const atMyLevel = admin || t.route === user.role;
  const open = isOpen(t);
  const next = NEXT[t.route];

  return (
    <div className="grid gap-4 lg:grid-cols-12 pt-2">
      <PageHeader
        title={t.subject || `Ticket #${t.id}`}
        badges={<>
          <RouteBadge route={t.route} />
          <span className="chip bg-sunken text-ink-2">{STATUS_LABEL[t.status] ?? t.status}</span>
          {t.incident && <Link to="/incidents" className="chip bg-tier2-soft text-tier2-text"><Boxes className="w-3 h-3" aria-hidden />Incident #{t.incident.id}</Link>}
          {t.integrity?.ai_like && <span className="chip bg-sunken text-ink-2" title="The writing looks AI-generated. Not evidence on its own.">AI-like writing</span>}
          {t.integrity?.review_suggested && <span className="chip bg-glacier-soft text-glacier-text" title="The integrity check suggests a manual review by an admin.">Integrity review suggested</span>}
        </>}
        subtitle={`#${t.id} · ${t.category_label} · ${t.customer ? `${t.customer.name} (${SEGMENT_LABEL[t.customer.segment] ?? t.customer.segment})` : "Unknown customer"} · opened ${timeAgo(t.created_at)} · priority ${t.priority}`}
        back={<Link to={backTo} className="text-sm text-ink-3 hover:text-ink inline-flex items-center gap-1"><ArrowLeft className="w-4 h-4" /> Back to queue</Link>}
        actions={<SummaryButton ticketId={t.id} staff />}
      />

      <div className="lg:col-span-8 grid gap-4 content-start">
        <HandoverPanel ticketId={t.id} />
        <Conversation ticketId={t.id} live={t.route === "level3" && open} suggest tall
                      canReply={atMyLevel || t.assigned_agent?.id === user.id}
                      placeholder={t.route === "level3" ? "Chat live with the customer…" : "Reply to the customer…"} />
        {t.attachments?.length > 0 && (
          <Tile eyebrow="Files from the customer" icon={Paperclip}><AttachmentList items={t.attachments} /></Tile>
        )}
      </div>

      <div className="lg:col-span-4 grid gap-4 content-start">
        <Tile eyebrow="Actions" icon={Hand}>
          <p className="text-sm text-ink-2 flex items-center gap-1.5">
            <UserRound className="w-4 h-4" aria-hidden />
            {t.assigned_agent ? <>Assigned to <b>{t.assigned_agent.id === user.id ? "you" : t.assigned_agent.name}</b></> : "Unassigned (no agent free yet)"}
          </p>
          {!atMyLevel && <p className="mt-2 text-xs text-ink-3">This ticket has moved to {t.level_name}.</p>}
          {atMyLevel && open && (
            <div className="mt-3 space-y-3">
              {!admin && t.status === "queued" && (
                <button className="btn-primary w-full" disabled={!!busy} onClick={() => act("claim", () => api.claim(t.id), "You're on it")}>
                  {busy === "claim" && <Loader2 className="w-4 h-4 animate-spin" />}<Hand className="w-4 h-4" />Claim ticket
                </button>
              )}
              {next && (
                <form className="space-y-2" onSubmit={(e) => {
                  e.preventDefault();
                  act("esc", () => api.escalate(t.id, reason.trim()), `Escalated to ${levelTitle(next)}`,
                      admin ? () => { setReason(""); reload(); } : () => navigate("/queue"));
                }}>
                  <textarea className="field min-h-[64px]" placeholder={`Why does this need ${routeMeta(next).name}?`} value={reason}
                            onChange={(e) => setReason(e.target.value)} aria-label="Escalation reason" />
                  <button className="btn-ghost w-full" disabled={!!busy || reason.trim().length < 3}>
                    {busy === "esc" ? <Loader2 className="w-4 h-4 animate-spin" /> : <ArrowUpCircle className="w-4 h-4" />}
                    Escalate to {routeMeta(next).label}
                  </button>
                </form>
              )}
              <button className="btn-ghost w-full" disabled={!!busy} onClick={() => act("resolve", () => api.resolve(t.id), `Ticket #${t.id} resolved`)}>
                {busy === "resolve" ? <Loader2 className="w-4 h-4 animate-spin" /> : <CheckCircle2 className="w-4 h-4" />}Resolve
              </button>
            </div>
          )}
          {!open && <p className="mt-2 text-xs text-ink-3">{STATUS_LABEL[t.status]}.</p>}
        </Tile>
        {t.route === "level3" && <CallbackPanel ticketId={t.id} mode="agent" />}
        <GuidesTile ticketId={t.id} />
      </div>

      <TicketExplain ticket={t} onChanged={reload} admin={admin} className="lg:col-span-12" />
    </div>
  );
}
