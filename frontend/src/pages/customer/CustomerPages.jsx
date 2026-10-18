import { useEffect, useMemo, useState } from "react";
import { SummaryButton } from "../../components/Summary.jsx";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import clsx from "clsx";
import {
  ArrowLeft, BookOpen, CheckCircle2, ChevronDown, ChevronRight, Clock3, HelpCircle, LifeBuoy, Lightbulb, Loader2,
  Paperclip, PlusCircle, Search, Send, ShieldAlert, Sparkles, ThumbsDown, ThumbsUp, Wrench,
} from "lucide-react";
import { api } from "../../api.js";
import { useAuth } from "../../lib/auth.jsx";
import { useLiveData } from "../../lib/events.jsx";
import { STATUS_LABEL, routeMeta, timeAgo } from "../../lib/meta.js";
import { CallbackPanel, Conversation } from "../../components/Conversation.jsx";
import { AttachmentList, DropZone } from "../../components/Attachments.jsx";
import { Empty, ErrorNote, PageHeader, Skeleton, SkeletonLines, Tile, useToast } from "../../components/ui.jsx";

const LEVEL_ICON = { level1: LifeBuoy, level2: Wrench, level3: ShieldAlert, auto_kb: BookOpen };

function StatusPill({ t }) {
  const done = t.status === "resolved";
  return (
    <span className={clsx("chip", done ? "bg-tier1-soft text-tier1-text" : routeMeta(t.route).badge)}>
      {done ? "Resolved" : t.route === "auto_kb" ? "Answered" : t.level_name}
    </span>
  );
}

function Stat({ label, value, icon: Icon, tone }) {
  return (
    <div className="tile !p-5 lg:col-span-3">
      <div className="flex items-center justify-between">
        <p className="text-xs font-semibold text-ink-3">{label}</p>
        <span className={clsx("w-8 h-8 rounded-xl grid place-items-center", tone)}><Icon className="w-4 h-4" aria-hidden /></span>
      </div>
      <p className="mt-2 text-3xl font-extrabold num">{value}</p>
    </div>
  );
}

/** A short list of article cards (help centre preview, ticket sidebars). */
function ArticleLinks({ articles, emptyText }) {
  if (!articles?.length) return <p className="text-sm text-ink-3">{emptyText}</p>;
  return (
    <ul className="space-y-1">
      {articles.map((a) => (
        <li key={a.id}>
          <Link to={`/help?article=${a.id}`} className="flex items-center gap-3 rounded-xl px-2 py-2 -mx-2 hover:bg-sunken">
            <BookOpen className="w-4 h-4 text-auto shrink-0" aria-hidden />
            <span className="text-sm font-medium flex-1 min-w-0 truncate">{a.title}</span>
            <ChevronRight className="w-4 h-4 text-ink-3 shrink-0" aria-hidden />
          </Link>
        </li>
      ))}
    </ul>
  );
}

// ------------------------------------------------------------------ home
export function SupportHome() {
  const { user } = useAuth();
  const { data: tickets, error } = useLiveData(() => api.myTickets(), { match: (ev) => !!ev.ticket_id });
  const [articles, setArticles] = useState(null);
  useEffect(() => { api.kbArticles().then((a) => setArticles(a.slice(0, 5))).catch(() => setArticles([])); }, []);

  const list = tickets ?? [];
  const count = (fn) => (tickets ? list.filter(fn).length : "–");

  return (
    <div className="grid gap-4 lg:grid-cols-12 pt-2">
      <PageHeader title={`Welcome back, ${user.name.split(" ")[0]}`} subtitle="Track your tickets, open new requests and find quick answers."
                  actions={<Link to="/support/new" className="btn-primary"><PlusCircle className="w-4 h-4" />New ticket</Link>} />

      <Stat label="Open" value={count((t) => t.status === "queued")} icon={Clock3} tone="bg-tier2-soft text-tier2-text" />
      <Stat label="In progress" value={count((t) => t.status === "in_progress")} icon={LifeBuoy} tone="bg-glacier-soft text-glacier-text" />
      <Stat label="Resolved" value={count((t) => t.status === "resolved")} icon={CheckCircle2} tone="bg-tier1-soft text-tier1-text" />
      <Stat label="Answered instantly" value={count((t) => t.route === "auto_kb")} icon={Sparkles} tone="bg-auto-soft text-auto-text" />

      <Tile className="lg:col-span-8" eyebrow="Your tickets" title="Recent requests"
            action={tickets?.length > 0 && <span className="text-xs text-ink-3">{tickets.length} total</span>}>
        {error && <ErrorNote>{error}</ErrorNote>}
        {!tickets ? <SkeletonLines rows={4} /> : tickets.length === 0 ? (
          <Empty icon={LifeBuoy}>No tickets yet. <Link to="/support/new" className="text-glacier-text font-semibold">Create your first one</Link>.</Empty>
        ) : (
          <ul className="divide-y divide-line">
            {tickets.map((t) => {
              const Icon = LEVEL_ICON[t.route] ?? LifeBuoy;
              return (
                <li key={t.id} className="flex items-center gap-1">
                  <Link to={`/support/tickets/${t.id}`} className="flex-1 min-w-0 flex items-center gap-4 py-3 px-2 -mx-2 rounded-xl hover:bg-sunken">
                    <span className={clsx("w-10 h-10 rounded-2xl grid place-items-center shrink-0", routeMeta(t.route).badge)}><Icon className="w-4 h-4" aria-hidden /></span>
                    <span className="min-w-0 flex-1">
                      <span className="block font-semibold text-sm truncate">{t.subject || t.body}</span>
                      <span className="block text-xs text-ink-3">#{t.id} · {t.category_label} · updated {timeAgo(t.updated_at)}</span>
                    </span>
                    <StatusPill t={t} />
                    <ChevronRight className="w-4 h-4 text-ink-3 shrink-0" aria-hidden />
                  </Link>
                  <SummaryButton ticketId={t.id} compact />
                </li>
              );
            })}
          </ul>
        )}
      </Tile>

      <Tile className="lg:col-span-4" eyebrow="Help centre" title="Quick answers" icon={HelpCircle}
            action={<Link to="/help" className="text-xs font-semibold text-glacier-text hover:underline">Browse all</Link>}>
        {!articles ? <SkeletonLines rows={4} /> : <ArticleLinks articles={articles} emptyText="No articles yet." />}
        <div className="mt-auto pt-4">
          <div className="rounded-2xl bg-glacier-soft/60 p-4 text-sm">
            <p className="font-semibold">Need help right now?</p>
            <p className="text-ink-2 text-xs mt-1">Urgent, security or safety problems go straight to an expert, whatever category you pick.</p>
          </div>
        </div>
      </Tile>
    </div>
  );
}

// ------------------------------------------------------------------ new ticket
export function NewTicketPage() {
  const navigate = useNavigate();
  const toast = useToast();
  const [cats, setCats] = useState(null);
  const [category, setCategory] = useState("");
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [files, setFiles] = useState([]);
  const [suggestions, setSuggestions] = useState([]);
  const [openArticle, setOpenArticle] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    api.categories().then((c) => setCats(c.categories)).catch((e) => setError(e.message));
  }, []);

  // "These articles might help" while typing.
  useEffect(() => {
    const text = `${subject} ${body}`.trim();
    if (text.length < 12) {
      setSuggestions([]);
      return undefined;
    }
    const t = setTimeout(() => api.kbSuggest(text).then(setSuggestions).catch(() => {}), 350);
    return () => clearTimeout(t);
  }, [subject, body]);

  const submit = async (e) => {
    e.preventDefault();
    if (!category) return setError("Please choose a category.");
    setBusy(true);
    setError("");
    try {
      const t = await api.submitTicket({ category, subject: subject.trim(), body: body.trim() });
      if (files.length) {
        try {
          await api.uploadTicketFiles(t.id, files);
        } catch (err) {
          toast(`Ticket created, but files failed: ${err.message}`, "error");
        }
      }
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
      <PageHeader title="New ticket" subtitle="Pick a category, describe the problem, and add screenshots if you have them."
                  back={<Link to="/support" className="text-sm text-ink-3 hover:text-ink inline-flex items-center gap-1"><ArrowLeft className="w-4 h-4" />My tickets</Link>} />

      <div className="lg:col-span-8 grid gap-4 content-start">
        <Tile eyebrow="1 · Category" title="What is it about?">
          {!cats ? <Skeleton className="h-32" /> : (
            <div className="grid sm:grid-cols-2 gap-5">
              {groups.map((g) => (
                <div key={g.level} role="radiogroup" aria-label={g.title}>
                  <p className="flex items-center gap-2 text-sm font-semibold"><g.icon className="w-4 h-4 text-ink-3" aria-hidden />{g.title}</p>
                  <p className="text-xs text-ink-3 mb-2">{g.note}</p>
                  <div className="grid gap-2">
                    {cats.filter((c) => c.level === g.level).map((c) => (
                      <button type="button" key={c.id} role="radio" aria-checked={category === c.id} onClick={() => setCategory(c.id)}
                              className={clsx("text-left rounded-xl border px-3.5 py-2.5 text-sm font-semibold transition flex items-center justify-between",
                                category === c.id ? "border-glacier bg-glacier-soft/60 ring-2 ring-glacier/15" : "border-line hover:border-ink-3/40")}>
                        {c.label}
                        {category === c.id && <CheckCircle2 className="w-4 h-4 text-glacier" aria-hidden />}
                      </button>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </Tile>
        <Tile eyebrow="2 · Details" title="Describe the issue" icon={Send}>
          <div className="grid gap-3">
            <input className="field" placeholder="Subject (optional)" value={subject} maxLength={200} onChange={(e) => setSubject(e.target.value)} aria-label="Subject" />
            <textarea className="field min-h-[150px]" placeholder="What happened? Include anything that helps us act fast (deadlines, error messages…)."
                      value={body} maxLength={5000} onChange={(e) => setBody(e.target.value)} required aria-label="Message" />
            <DropZone files={files} setFiles={setFiles} onError={(m) => m && toast(m, "error")} />
            <div className="flex flex-wrap items-center gap-3 justify-between pt-1">
              <p className="text-xs text-ink-3 max-w-md">Urgent, security or safety problems are escalated to an expert automatically, whatever the category.</p>
              <button className="btn-primary" disabled={busy || !body.trim()}>{busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}Submit ticket</button>
            </div>
            {error && <ErrorNote>{error}</ErrorNote>}
          </div>
        </Tile>
      </div>

      <div className="lg:col-span-4 grid gap-4 content-start lg:sticky lg:top-20">
        <Tile eyebrow="These articles might help" icon={Lightbulb}>
          {suggestions.length === 0 ? (
            <p className="text-sm text-ink-3">Start describing your problem and we'll suggest answers from the help centre. You might not need a ticket at all.</p>
          ) : (
            <ul className="space-y-2">
              {suggestions.map((a) => (
                <li key={a.id} className="rounded-2xl border border-line">
                  <button type="button" className="w-full text-left px-3.5 py-3 flex items-center gap-2" aria-expanded={openArticle === a.id}
                          onClick={() => setOpenArticle(openArticle === a.id ? null : a.id)}>
                    <BookOpen className="w-4 h-4 text-auto shrink-0" aria-hidden />
                    <span className="text-sm font-semibold flex-1">{a.title}</span>
                    <ChevronDown className={clsx("w-4 h-4 text-ink-3 transition", openArticle === a.id && "rotate-180")} aria-hidden />
                  </button>
                  {openArticle === a.id && (
                    <div className="px-3.5 pb-3 text-sm text-ink-2">
                      <p>{a.answer}</p>
                      <button type="button" className="btn-ghost !py-1 !text-xs mt-2" onClick={() => navigate("/support")}>
                        <ThumbsUp className="w-3.5 h-3.5" /> That solved it
                      </button>
                    </div>
                  )}
                </li>
              ))}
            </ul>
          )}
        </Tile>
        <Tile eyebrow="Tip" icon={Paperclip}>
          <p className="text-sm text-ink-2">A screenshot of the error and the time it happened usually gets you an answer much faster.</p>
        </Tile>
      </div>
    </form>
  );
}

// ------------------------------------------------------------------ ticket
const STEPS = ["level1", "level2", "level3"];

export function CustomerTicketPage() {
  const { id } = useParams();
  const ticketId = Number(id);
  const toast = useToast();
  const { data: t, error, reload } = useLiveData(() => api.myTicket(ticketId), {
    match: (ev) => ev.ticket_id === ticketId, deps: [ticketId],
  });
  const [related, setRelated] = useState(null);
  const [busy, setBusy] = useState("");

  useEffect(() => {
    if (t && related === null) api.kbSuggest(`${t.subject} ${t.body}`).then(setRelated).catch(() => setRelated([]));
  }, [t]); // eslint-disable-line react-hooks/exhaustive-deps

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
      <PageHeader title={t.subject || `Ticket #${t.id}`} badges={<StatusPill t={t} />}
                  subtitle={`#${t.id} · ${t.category_label} · opened ${timeAgo(t.created_at)}`}
                  back={<Link to="/support" className="text-sm text-ink-3 hover:text-ink inline-flex items-center gap-1"><ArrowLeft className="w-4 h-4" />My tickets</Link>}
                  actions={<>
                    <SummaryButton ticketId={t.id} />
                    {!resolved && (
                      <button className="btn-ghost" disabled={!!busy} onClick={() => act("resolve", () => api.resolve(t.id), "Ticket closed")}>
                        <CheckCircle2 className="w-4 h-4" /> My problem is solved
                      </button>
                    )}
                  </>} />

      <div className="lg:col-span-8 grid gap-4 content-start">
        {t.route === "auto_kb" && t.auto_reply && (
          <Tile eyebrow="Instant answer" title={t.kb.title} icon={BookOpen}>
            <p className="text-sm whitespace-pre-wrap">{t.kb.answer}</p>
            <p className="mt-1 text-[11px] text-ink-3">{t.kb.source}</p>
            {!t.kb.rated && !resolved ? (
              <div className="mt-4 flex flex-wrap gap-2 items-center rounded-2xl bg-sunken p-3">
                <span className="text-sm font-semibold mr-1">Did this help?</span>
                <button className="btn-ghost bg-card" disabled={!!busy} onClick={() => act("up", () => api.feedback(t.id, "kb_helpful"), "Great, ticket closed")}>
                  <ThumbsUp className="w-4 h-4" /> Yes, solved
                </button>
                <button className="btn-ghost bg-card" disabled={!!busy} onClick={() => act("down", () => api.feedback(t.id, "kb_not_helpful"), "Passed to a support agent")}>
                  <ThumbsDown className="w-4 h-4" /> No, I need a person
                </button>
              </div>
            ) : <p className="mt-3 text-xs text-ink-3">Thanks for the feedback.</p>}
          </Tile>
        )}
        <Conversation ticketId={t.id} live={t.live_chat && !resolved} canReply tall
                      placeholder={resolved ? "Reply to reopen this ticket…" : t.live_chat ? "Chat live with the expert…" : "Add details, reply, or attach a screenshot…"} />
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
                      {state === "now" && <span className="block text-xs text-ink-3">{resolved ? "Resolved here" : t.agent_name ? `${t.agent_name} is on it` : "Waiting for the next free agent"}</span>}
                    </span>
                  </li>
                );
              })}
            </ol>
          )}
          <p className="mt-4 text-xs text-ink-3">Status: {STATUS_LABEL[t.status] ?? t.status} · updated {timeAgo(t.updated_at)}</p>
        </Tile>
        {t.route === "level3" && <CallbackPanel ticketId={t.id} mode="customer" open={!resolved} />}
        <Tile eyebrow="Your original message">
          <p className="text-sm whitespace-pre-wrap break-words text-ink-2">{t.body}</p>
          <AttachmentList items={t.attachments} />
        </Tile>
        <Tile eyebrow="Related help articles" icon={HelpCircle}>
          {related === null ? <SkeletonLines rows={2} /> : <ArticleLinks articles={related} emptyText="No matching articles. Our team will answer you here." />}
        </Tile>
      </div>
    </div>
  );
}

// ------------------------------------------------------------------ help centre
export function HelpCentrePage() {
  const [params, setParams] = useSearchParams();
  const [articles, setArticles] = useState(null);
  const [q, setQ] = useState("");
  const [error, setError] = useState("");
  const openId = params.get("article");

  useEffect(() => { api.kbArticles().then(setArticles).catch((e) => setError(e.message)); }, []);
  useEffect(() => {
    if (openId) document.getElementById(`article-${openId}`)?.scrollIntoView({ block: "center", behavior: "smooth" });
  }, [openId, articles]);

  const groups = useMemo(() => {
    const term = q.toLowerCase().trim();
    const rows = (articles ?? []).filter((a) => !term || `${a.title} ${a.answer} ${a.questions.join(" ")}`.toLowerCase().includes(term));
    const by = {};
    rows.forEach((a) => {
      const g = (a.source || "Help Center").replace(/^Help Center\s*-\s*/, "") || "General";
      (by[g] ||= []).push(a);
    });
    return Object.entries(by).sort(([a], [b]) => a.localeCompare(b));
  }, [articles, q]);

  return (
    <div className="grid gap-4 lg:grid-cols-12 pt-2">
      <Tile dark className="lg:col-span-12" eyebrow="Help centre" icon={HelpCircle}>
        <h1 className="text-3xl font-extrabold tracking-tight text-white">How can we help?</h1>
        <p className="mt-1 text-slate-400 text-sm">Answers to the most common questions. Can't find yours? <Link to="/support/new" className="text-sky-300 font-semibold hover:underline">Open a ticket</Link>.</p>
        <div className="mt-5 max-w-2xl flex items-center gap-2 rounded-2xl bg-white/95 dark:bg-card px-4 h-12">
          <Search className="w-4 h-4 text-ink-3" aria-hidden />
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search for answers (e.g. invoice, password, 2FA)…"
                 className="flex-1 bg-transparent outline-none text-sm text-ink placeholder:text-ink-3" aria-label="Search help articles" />
        </div>
      </Tile>
      {error && <div className="lg:col-span-12"><ErrorNote>{error}</ErrorNote></div>}
      {!articles ? <div className="lg:col-span-12"><SkeletonLines rows={6} /></div> : groups.length === 0 ? (
        <div className="lg:col-span-12 tile"><Empty icon={Search}>No articles match “{q}”. <Link to="/support/new" className="text-glacier-text font-semibold">Ask our team</Link>.</Empty></div>
      ) : groups.map(([group, items]) => (
        <Tile key={group} className="lg:col-span-6" eyebrow={group} title={`${items.length} article${items.length === 1 ? "" : "s"}`} icon={BookOpen}>
          <ul className="divide-y divide-line">
            {items.map((a) => {
              const open = openId === a.id;
              return (
                <li key={a.id} id={`article-${a.id}`}>
                  <button className="w-full text-left py-3 flex items-center gap-2" aria-expanded={open}
                          onClick={() => setParams(open ? {} : { article: a.id })}>
                    <span className="text-sm font-semibold flex-1">{a.title}</span>
                    <ChevronDown className={clsx("w-4 h-4 text-ink-3 transition", open && "rotate-180")} aria-hidden />
                  </button>
                  {open && <p className="pb-3 text-sm text-ink-2 whitespace-pre-wrap">{a.answer}</p>}
                </li>
              );
            })}
          </ul>
        </Tile>
      ))}
    </div>
  );
}
