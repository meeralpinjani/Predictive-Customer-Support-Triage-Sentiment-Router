import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import clsx from "clsx";
import {
  ArrowLeft, BookOpen, CheckCircle2, ChevronRight, Cpu, LifeBuoy, Loader2, PlusCircle, Send, ShieldAlert, ThumbsDown,
  ThumbsUp, Wrench,
} from "lucide-react";
import { api } from "../../api.js";
import { useAuth } from "../../lib/auth.jsx";
import { useLiveData } from "../../lib/events.jsx";
import { STATUS_LABEL, routeMeta, timeAgo } from "../../lib/meta.js";
import { CallbackPanel, Conversation } from "../../components/Conversation.jsx";
import { Empty, ErrorNote, Skeleton, SkeletonLines, Tile, useToast } from "../../components/ui.jsx";

const LEVEL_ICON = { level1: LifeBuoy, level2: Wrench, level3: ShieldAlert, auto_kb: BookOpen };

function StatusPill({ t }) {
  const done = t.status === "resolved";
  return (
    <span className={clsx("chip", done ? "bg-tier1-soft text-tier1-text" : routeMeta(t.route).badge)}>
      {done ? "Resolved" : t.route === "auto_kb" ? "Answered" : t.level_name}
    </span>
  );
}

export function SupportHome() {
  const { user } = useAuth();
  const { data: tickets, error } = useLiveData(() => api.myTickets(), { match: (ev) => !!ev.ticket_id });
  const open = tickets?.filter((t) => t.status !== "resolved") ?? [];
  const closed = tickets?.filter((t) => t.status === "resolved") ?? [];

  return (
    <div className="grid gap-4 lg:grid-cols-12 pt-2">
      <Tile dark className="lg:col-span-8" eyebrow="Customer support" icon={LifeBuoy}>
        <h1 className="text-3xl font-extrabold tracking-tight text-white">Hi {user.name.split(" ")[0]}, how can we help?</h1>
        <p className="mt-2 text-slate-400 text-sm max-w-xl">
          Pick a category and describe the issue. Simple questions are answered instantly; everything else goes
          straight to the right team, and urgent problems reach an expert live.
        </p>
        <Link to="/support/new" className="mt-6 self-start btn bg-white text-fjord hover:bg-slate-100">
          <PlusCircle className="w-4 h-4" /> New ticket
        </Link>
      </Tile>
      <Tile className="lg:col-span-4" eyebrow="Your plan" icon={Cpu}>
        <p className="text-3xl font-extrabold">{user.customer?.plan || "–"}</p>
        <p className="mt-1 text-sm text-ink-3">{open.length} open · {closed.length} resolved</p>
      </Tile>

      <Tile className="lg:col-span-12" eyebrow="Your tickets" title="Recent requests">
        {error && <ErrorNote>{error}</ErrorNote>}
        {!tickets ? <SkeletonLines rows={4} /> : tickets.length === 0 ? (
          <Empty icon={LifeBuoy}>No tickets yet. <Link to="/support/new" className="text-glacier-text font-semibold">Create your first one</Link>.</Empty>
        ) : (
          <ul className="divide-y divide-line">
            {tickets.map((t) => {
              const Icon = LEVEL_ICON[t.route] ?? LifeBuoy;
              return (
                <li key={t.id}>
                  <Link to={`/support/tickets/${t.id}`} className="flex items-center gap-4 py-3 px-2 -mx-2 rounded-xl hover:bg-sunken">
                    <span className={clsx("w-10 h-10 rounded-2xl grid place-items-center shrink-0", routeMeta(t.route).badge)}><Icon className="w-4 h-4" aria-hidden /></span>
                    <span className="min-w-0 flex-1">
                      <span className="block font-semibold text-sm truncate">{t.subject || t.body}</span>
                      <span className="block text-xs text-ink-3">#{t.id} · {t.category_label} · updated {timeAgo(t.updated_at)}</span>
                    </span>
                    <StatusPill t={t} />
                    <ChevronRight className="w-4 h-4 text-ink-3 shrink-0" aria-hidden />
                  </Link>
                </li>
              );
            })}
          </ul>
        )}
      </Tile>
    </div>
  );
}

export function NewTicketPage() {
  const navigate = useNavigate();
  const toast = useToast();
  const [cats, setCats] = useState(null);
  const [category, setCategory] = useState("");
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    api.categories().then((c) => setCats(c.categories)).catch((e) => setError(e.message));
  }, []);

  const submit = async (e) => {
    e.preventDefault();
    if (!category) return setError("Please choose a category.");
    setBusy(true);
    setError("");
    try {
      const t = await api.submitTicket({ category, subject: subject.trim(), body: body.trim() });
      toast(t.route === "auto_kb" ? "We found an answer for you right away" : `Sent to ${t.level_name}`, "success");
      navigate(`/support/tickets/${t.id}`);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const groups = [
    { level: "level1", title: "General Support", icon: LifeBuoy, note: "Accounts, billing, plans and how-to questions" },
    { level: "level2", title: "Technical Support", icon: Wrench, note: "Something broken, slow, down or not connecting" },
  ];

  return (
    <form onSubmit={submit} className="grid gap-4 lg:grid-cols-12 pt-2">
      <div className="lg:col-span-12">
        <Link to="/support" className="text-sm text-ink-3 hover:text-ink inline-flex items-center gap-1"><ArrowLeft className="w-4 h-4" /> My tickets</Link>
        <h1 className="mt-2 text-2xl font-extrabold tracking-tight">New ticket</h1>
      </div>
      {groups.map((g) => (
        <Tile key={g.level} className="lg:col-span-6" eyebrow={g.note} title={g.title} icon={g.icon}>
          {!cats ? <Skeleton className="h-32" /> : (
            <div className="grid sm:grid-cols-2 gap-2" role="radiogroup" aria-label={g.title}>
              {cats.filter((c) => c.level === g.level).map((c) => (
                <button type="button" key={c.id} role="radio" aria-checked={category === c.id} onClick={() => setCategory(c.id)}
                        className={clsx("text-left rounded-2xl border px-3.5 py-3 text-sm font-semibold transition",
                          category === c.id ? "border-glacier bg-glacier-soft/60 ring-2 ring-glacier/15" : "border-line hover:border-ink-3/40")}>
                  {c.label}
                </button>
              ))}
            </div>
          )}
        </Tile>
      ))}
      <Tile className="lg:col-span-12" eyebrow="Describe the issue" icon={Send}>
        <div className="grid gap-3">
          <input className="field" placeholder="Subject (optional)" value={subject} maxLength={200} onChange={(e) => setSubject(e.target.value)} aria-label="Subject" />
          <textarea className="field min-h-[140px]" placeholder="What happened? Include anything that helps us act fast (deadlines, error messages…)."
                    value={body} maxLength={5000} onChange={(e) => setBody(e.target.value)} required aria-label="Message" />
          <div className="flex flex-wrap items-center gap-3 justify-between">
            <p className="text-xs text-ink-3">Urgent, security or safety problems are escalated to an expert automatically, whatever the category.</p>
            <button className="btn-primary" disabled={busy || !body.trim()}>{busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}Submit ticket</button>
          </div>
          {error && <ErrorNote>{error}</ErrorNote>}
        </div>
      </Tile>
    </form>
  );
}

const STEPS = ["level1", "level2", "level3"];

export function CustomerTicketPage() {
  const { id } = useParams();
  const ticketId = Number(id);
  const toast = useToast();
  const { data: t, error, reload } = useLiveData(() => api.myTicket(ticketId), {
    match: (ev) => ev.ticket_id === ticketId, deps: [ticketId],
  });
  const [busy, setBusy] = useState("");

  const act = async (key, fn, msg) => {
    setBusy(key);
    try {
      await fn();
      toast(msg, "success");
      await reload();
    } catch (err) {
      toast(err.message, "error");
    } finally {
      setBusy("");
    }
  };

  if (error) return <div className="pt-6"><ErrorNote>{error}</ErrorNote></div>;
  if (!t) return <div className="pt-6"><SkeletonLines rows={6} /></div>;
  const resolved = t.status === "resolved";
  const current = STEPS.indexOf(t.route);

  return (
    <div className="grid gap-4 lg:grid-cols-12 pt-2">
      <div className="lg:col-span-12">
        <Link to="/support" className="text-sm text-ink-3 hover:text-ink inline-flex items-center gap-1"><ArrowLeft className="w-4 h-4" /> My tickets</Link>
        <div className="mt-2 flex flex-wrap items-center gap-3 justify-between">
          <h1 className="text-2xl font-extrabold tracking-tight">{t.subject || `Ticket #${t.id}`}</h1>
          <StatusPill t={t} />
        </div>
        <p className="text-sm text-ink-3">#{t.id} · {t.category_label} · opened {timeAgo(t.created_at)}</p>
      </div>

      <div className="lg:col-span-8 grid gap-4 content-start">
        {t.route === "auto_kb" && t.auto_reply && (
          <Tile eyebrow="Instant answer" title={t.kb.title} icon={BookOpen}>
            <p className="text-sm whitespace-pre-wrap">{t.kb.answer}</p>
            <p className="mt-1 text-[11px] text-ink-3">{t.kb.source}</p>
            {!t.kb.rated && !resolved ? (
              <div className="mt-4 flex flex-wrap gap-2 items-center">
                <span className="text-sm font-semibold mr-1">Did this help?</span>
                <button className="btn-ghost" disabled={!!busy} onClick={() => act("up", () => api.feedback(t.id, "kb_helpful"), "Great — ticket closed")}>
                  <ThumbsUp className="w-4 h-4" /> Yes, solved
                </button>
                <button className="btn-ghost" disabled={!!busy} onClick={() => act("down", () => api.feedback(t.id, "kb_not_helpful"), "Passed to a support agent")}>
                  <ThumbsDown className="w-4 h-4" /> No, I need a person
                </button>
              </div>
            ) : <p className="mt-3 text-xs text-ink-3">Thanks for the feedback.</p>}
          </Tile>
        )}
        <Conversation ticketId={t.id} live={t.live_chat && !resolved} canReply
                      placeholder={resolved ? "Reply to reopen this ticket…" : t.live_chat ? "Chat live with the expert…" : "Add details or reply…"} />
      </div>

      <div className="lg:col-span-4 grid gap-4 content-start">
        <Tile eyebrow="Where your ticket is">
          {t.route === "auto_kb" ? <p className="text-sm text-ink-2">Answered automatically from our help centre.</p> : (
            <ol className="space-y-3">
              {STEPS.map((lvl, i) => {
                const m = routeMeta(lvl);
                const state = i < current ? "past" : i === current ? "now" : "next";
                return (
                  <li key={lvl} className={clsx("flex items-center gap-3", state === "next" && "opacity-40")}>
                    <span className={clsx("w-8 h-8 rounded-full grid place-items-center text-xs font-bold", state === "now" ? `${m.dot} text-white` : "bg-sunken text-ink-3")}>{i + 1}</span>
                    <span>
                      <span className="block text-sm font-semibold">{m.name}</span>
                      {state === "now" && <span className="block text-xs text-ink-3">{resolved ? "Resolved here" : t.agent_name ? `${t.agent_name} is on it` : "Waiting for the next agent"}</span>}
                    </span>
                  </li>
                );
              })}
            </ol>
          )}
          <p className="mt-4 text-xs text-ink-3">Status: {STATUS_LABEL[t.status] ?? t.status}</p>
          {!resolved && (
            <button className="btn-ghost mt-3" disabled={!!busy} onClick={() => act("resolve", () => api.resolve(t.id), "Ticket closed")}>
              <CheckCircle2 className="w-4 h-4" /> My problem is solved
            </button>
          )}
        </Tile>
        {t.route === "level3" && <CallbackPanel ticketId={t.id} mode="customer" open={!resolved} />}
        <Tile eyebrow="Your original message">
          <p className="text-sm whitespace-pre-wrap break-words text-ink-2">{t.body}</p>
        </Tile>
      </div>
    </div>
  );
}
