import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import clsx from "clsx";
import {
  BookOpen, Boxes, CheckCircle2, ChevronDown, Lightbulb, Loader2, Lock, Pencil, Plus, Search, Send, Trash2, X,
} from "lucide-react";
import { api } from "../../api.js";
import { useAuth } from "../../lib/auth.jsx";
import { useLiveData } from "../../lib/events.jsx";
import { STATUS_LABEL, routeMeta, timeAgo } from "../../lib/meta.js";
import { flatten } from "../../components/layout/GlobalSearch.jsx";
import { Empty, ErrorNote, PageHeader, RouteBadge, SkeletonLines, Tile, useToast } from "../../components/ui.jsx";

// ------------------------------------------------------------------ search results
export function SearchPage() {
  const { user } = useAuth();
  const [params] = useSearchParams();
  const q = params.get("q") || "";
  const [res, setRes] = useState(null);
  const [error, setError] = useState("");
  useEffect(() => {
    setRes(null);
    if (q.trim().length < 1) return;
    api.search(q).then(setRes).catch((e) => setError(e.message));
  }, [q]);
  const rows = flatten(user, res);
  const groups = rows.reduce((acc, r) => ((acc[r.group] ||= []).push(r), acc), {});
  return (
    <div className="grid gap-4 lg:grid-cols-12 pt-2">
      <PageHeader title={`Results for “${q}”`} subtitle={res ? `${rows.length} result${rows.length === 1 ? "" : "s"}` : "Searching…"} />
      {error && <div className="lg:col-span-12"><ErrorNote>{error}</ErrorNote></div>}
      {!res ? <div className="lg:col-span-12"><SkeletonLines rows={5} /></div> : rows.length === 0 ? (
        <div className="lg:col-span-12 tile"><Empty icon={Search}>Nothing found. Try another word{user.role === "customer" ? <> or <Link to="/support/new" className="text-glacier-text font-semibold">open a ticket</Link></> : ""}.</Empty></div>
      ) : Object.entries(groups).map(([g, items]) => (
        <Tile key={g} className="lg:col-span-6" eyebrow={g} title={`${items.length} found`}>
          <ul className="divide-y divide-line">
            {items.map((r) => (
              <li key={r.key}>
                <Link to={r.href} className="flex items-center gap-3 py-2.5 hover:text-glacier-text">
                  <r.icon className="w-4 h-4 text-ink-3 shrink-0" aria-hidden />
                  <span className="min-w-0"><span className="block text-sm font-semibold truncate">{r.title}</span>
                    <span className="block text-xs text-ink-3 truncate">{r.sub}</span></span>
                </Link>
              </li>
            ))}
          </ul>
        </Tile>
      ))}
    </div>
  );
}

// ------------------------------------------------------------------ incidents
export function IncidentsPage() {
  const toast = useToast();
  const { data: suggestions, reload: reloadSug } = useLiveData(() => api.incidentSuggestions(), { match: (ev) => ev.type.startsWith("ticket") });
  const { data: incidents, reload } = useLiveData(() => api.incidents(), { match: (ev) => ev.type.startsWith("ticket") });
  const [titles, setTitles] = useState({});
  const [drafts, setDrafts] = useState({});
  const [busy, setBusy] = useState("");

  const run = async (key, fn, msg) => {
    setBusy(key);
    try {
      await fn();
      toast(msg, "success");
      await Promise.all([reload(), reloadSug()]);
    } catch (err) {
      toast(err.message, "error");
    } finally {
      setBusy("");
    }
  };

  const active = (incidents ?? []).filter((i) => i.status === "open");
  const done = (incidents ?? []).filter((i) => i.status !== "open");

  return (
    <div className="grid gap-4 lg:grid-cols-12 pt-2">
      <PageHeader title="Incidents" subtitle="When many customers report the same problem, handle it once: group the tickets, reply to everyone, resolve together." />

      <Tile className="lg:col-span-5" eyebrow="Suggested groups" title="Possible duplicates" icon={Lightbulb}
            action={suggestions && <span className="chip bg-sunken text-ink-2">{suggestions.method === "minilm" ? "AI similarity" : "word similarity"}</span>}>
        {!suggestions ? <SkeletonLines rows={4} /> : suggestions.groups.length === 0 ? (
          <Empty icon={Boxes}>No similar open tickets right now.</Empty>
        ) : (
          <ul className="space-y-3">
            {suggestions.groups.map((g, i) => {
              const key = g.ticket_ids.join("-");
              return (
                <li key={key} className="rounded-2xl border border-line p-4">
                  <p className="text-sm font-semibold">{g.ticket_ids.length} similar tickets · {g.customers.length} customer{g.customers.length === 1 ? "" : "s"}</p>
                  <ul className="mt-2 space-y-1">
                    {g.examples.map((e, j) => (
                      <li key={j} className="text-xs text-ink-2 truncate">
                        <Link to={`/tickets/${g.ticket_ids[j]}`} className="hover:text-glacier-text">#{g.ticket_ids[j]} · {e}</Link>
                      </li>
                    ))}
                  </ul>
                  <div className="mt-3 flex gap-2">
                    <input className="field !py-1.5" value={titles[key] ?? g.title} onChange={(e) => setTitles({ ...titles, [key]: e.target.value })}
                           aria-label="Incident title" />
                    <button className="btn-primary !py-1.5 shrink-0" disabled={!!busy}
                            onClick={() => run(`c${i}`, () => api.createIncident(g.ticket_ids, (titles[key] ?? g.title).trim() || "Incident"), "Incident created")}>
                      {busy === `c${i}` ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}Group
                    </button>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </Tile>

      <div className="lg:col-span-7 grid gap-4 content-start">
        {!incidents ? <Tile><SkeletonLines rows={4} /></Tile> : active.length === 0 ? (
          <Tile eyebrow="Active incidents" icon={Boxes}><Empty icon={Boxes}>No active incidents.</Empty></Tile>
        ) : active.map((inc) => (
          <Tile key={inc.id} eyebrow={`Incident #${inc.id} · opened ${timeAgo(inc.created_at)}`} title={inc.title} icon={Boxes}
                action={<span className="chip bg-tier2-soft text-tier2-text">{inc.open} open</span>}>
            <ul className="divide-y divide-line mb-3">
              {inc.tickets.map((t) => (
                <li key={t.id} className="py-2 flex items-center gap-2 text-sm">
                  <Link to={`/tickets/${t.id}`} className="font-semibold hover:text-glacier-text">#{t.id}</Link>
                  <span className="flex-1 truncate text-ink-2">{t.subject}</span>
                  <RouteBadge route={t.route} />
                  <span className="text-xs text-ink-3 w-20 text-right">{STATUS_LABEL[t.status]}</span>
                </li>
              ))}
            </ul>
            <textarea className="field min-h-[72px]" placeholder="Message to every affected customer…" value={drafts[inc.id] || ""}
                      onChange={(e) => setDrafts({ ...drafts, [inc.id]: e.target.value })} aria-label="Message to all" />
            <div className="mt-2 flex flex-wrap gap-2 justify-end">
              <button className="btn-ghost" disabled={!!busy || !(drafts[inc.id] || "").trim()}
                      onClick={() => run(`r${inc.id}`, () => api.incidentReply(inc.id, drafts[inc.id]), `Reply sent to ${inc.open} tickets`).then(() => setDrafts({ ...drafts, [inc.id]: "" }))}>
                <Send className="w-4 h-4" /> Reply to all
              </button>
              <button className="btn-primary" disabled={!!busy}
                      onClick={() => run(`x${inc.id}`, () => api.incidentResolve(inc.id, drafts[inc.id] || ""), "Incident resolved, all tickets closed")}>
                <CheckCircle2 className="w-4 h-4" /> Resolve all
              </button>
            </div>
          </Tile>
        ))}
        {done.length > 0 && (
          <Tile eyebrow="Resolved incidents">
            <ul className="divide-y divide-line">
              {done.map((inc) => (
                <li key={inc.id} className="py-2 text-sm flex justify-between gap-3">
                  <span>#{inc.id} · {inc.title}</span>
                  <span className="text-ink-3 text-xs">{inc.tickets.length} tickets · {timeAgo(inc.resolved_at || inc.created_at)}</span>
                </li>
              ))}
            </ul>
          </Tile>
        )}
      </div>
    </div>
  );
}

// ------------------------------------------------------------------ knowledge base
const EMPTY = { title: "", answer: "", questions: "", source: "Help Center", visibility: "public", tags: "" };

function ArticleEditor({ initial, onCancel, onSaved }) {
  const toast = useToast();
  const [f, setF] = useState(initial);
  const [busy, setBusy] = useState(false);
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });
  const save = async (e) => {
    e.preventDefault();
    setBusy(true);
    const payload = {
      title: f.title, answer: f.answer, source: f.source, visibility: f.visibility,
      questions: f.questions.split("\n").map((s) => s.trim()).filter(Boolean),
      tags: f.tags.split(",").map((s) => s.trim()).filter(Boolean),
    };
    try {
      if (f.id) await api.updateArticle(f.id, payload);
      else await api.createArticle(payload);
      toast(f.id ? "Article updated" : "Article published", "success");
      onSaved();
    } catch (err) {
      toast(err.message, "error");
    } finally {
      setBusy(false);
    }
  };
  return (
    <form onSubmit={save} className="space-y-3">
      <div className="flex gap-2">
        {["public", "internal"].map((v) => (
          <button type="button" key={v} onClick={() => setF({ ...f, visibility: v })}
                  className={clsx("flex-1 rounded-xl border px-3 py-2 text-sm font-semibold", f.visibility === v ? "border-glacier bg-glacier-soft/60" : "border-line")}>
            {v === "public" ? "Public FAQ (customers + auto-answers)" : "Internal guide (agents only)"}
          </button>
        ))}
      </div>
      <input className="field" placeholder="Title" value={f.title} onChange={set("title")} required minLength={3} aria-label="Title" />
      <textarea className="field min-h-[120px]" placeholder="Answer" value={f.answer} onChange={set("answer")} required minLength={10} aria-label="Answer" />
      <textarea className="field min-h-[90px]" placeholder={"Example questions customers ask, one per line\n(these make auto-answers match)"} value={f.questions}
                onChange={set("questions")} aria-label="Example questions" />
      <div className="grid sm:grid-cols-2 gap-2">
        <input className="field" placeholder="Section (e.g. Help Center - Billing)" value={f.source} onChange={set("source")} aria-label="Section" />
        <input className="field" placeholder="Tags for guides: security, legal, frustration…" value={f.tags} onChange={set("tags")} aria-label="Tags" />
      </div>
      <div className="flex gap-2 justify-end">
        <button type="button" className="btn-ghost" onClick={onCancel}><X className="w-4 h-4" />Cancel</button>
        <button className="btn-primary" disabled={busy}>{busy && <Loader2 className="w-4 h-4 animate-spin" />}{f.id ? "Save changes" : "Publish"}</button>
      </div>
    </form>
  );
}

export function KnowledgePage() {
  const { user } = useAuth();
  const toast = useToast();
  const admin = user.role === "admin";
  const [params, setParams] = useSearchParams();
  const openId = params.get("article");
  const [articles, setArticles] = useState(null);
  const [topics, setTopics] = useState(null);
  const [error, setError] = useState("");
  const [q, setQ] = useState("");
  const [filter, setFilter] = useState("all");
  const [editing, setEditing] = useState(null);

  const load = () => api.kbArticles().then(setArticles).catch((e) => setError(e.message));
  useEffect(() => {
    load();
    if (admin) api.kbTopics().then(setTopics).catch(() => setTopics({ topics: [] }));
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (openId) document.getElementById(`kb-${openId}`)?.scrollIntoView({ block: "center", behavior: "smooth" });
  }, [openId, articles]);

  const rows = useMemo(() => (articles ?? []).filter((a) =>
    (filter === "all" || a.visibility === filter) &&
    (!q || `${a.title} ${a.answer} ${a.questions.join(" ")}`.toLowerCase().includes(q.toLowerCase()))), [articles, q, filter]);
  const counts = { all: articles?.length ?? 0, public: articles?.filter((a) => a.visibility === "public").length ?? 0,
    internal: articles?.filter((a) => a.visibility === "internal").length ?? 0 };

  const remove = async (a) => {
    if (!window.confirm(`Delete "${a.title}"? This cannot be undone.`)) return;
    try {
      await api.deleteArticle(a.id);
      toast("Article deleted", "success");
      load();
    } catch (err) {
      toast(err.message, "error");
    }
  };

  return (
    <div className="grid gap-4 lg:grid-cols-12 pt-2">
      <PageHeader title="Knowledge base" subtitle={admin ? "Public articles answer customers automatically; internal guides help agents. Edit both here." : "Help-centre articles and internal guides (how to escalate, security, legal, angry customers…)."}
                  actions={admin && <button className="btn-primary" onClick={() => setEditing({ ...EMPTY })}><Plus className="w-4 h-4" />New article</button>} />

      {editing && (
        <Tile className="lg:col-span-12" eyebrow={editing.id ? "Edit article" : "New article"} icon={Pencil}>
          <ArticleEditor initial={editing} onCancel={() => setEditing(null)} onSaved={() => { setEditing(null); load(); }} />
        </Tile>
      )}

      <Tile className={admin ? "lg:col-span-8" : "lg:col-span-12"} eyebrow={`${rows.length} article${rows.length === 1 ? "" : "s"}`} icon={BookOpen}
            action={
              <div className="flex flex-wrap gap-2">
                <input className="field !py-1.5 w-48" placeholder="Filter…" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Filter articles" />
                <select className="field !py-1.5 w-40" value={filter} onChange={(e) => setFilter(e.target.value)} aria-label="Visibility">
                  <option value="all">All ({counts.all})</option>
                  <option value="public">Public FAQ ({counts.public})</option>
                  <option value="internal">Internal guides ({counts.internal})</option>
                </select>
              </div>
            }>
        {error && <ErrorNote>{error}</ErrorNote>}
        {!articles ? <SkeletonLines rows={6} /> : rows.length === 0 ? <Empty icon={BookOpen}>No articles match.</Empty> : (
          <ul className="divide-y divide-line">
            {rows.map((a) => {
              const open = openId === a.id;
              return (
                <li key={a.id} id={`kb-${a.id}`}>
                  <div className="flex items-center gap-2 py-3">
                    <button className="flex-1 text-left flex items-center gap-2 min-w-0" aria-expanded={open} onClick={() => setParams(open ? {} : { article: a.id })}>
                      {a.visibility === "internal" ? <Lock className="w-4 h-4 text-ink-3 shrink-0" aria-hidden /> : <BookOpen className="w-4 h-4 text-auto shrink-0" aria-hidden />}
                      <span className="text-sm font-semibold truncate">{a.title}</span>
                      <span className={clsx("chip", a.visibility === "internal" ? "bg-sunken text-ink-2" : "bg-auto-soft text-auto-text")}>{a.visibility === "internal" ? "Internal" : "Public"}</span>
                      <ChevronDown className={clsx("w-4 h-4 text-ink-3 ml-auto shrink-0 transition", open && "rotate-180")} aria-hidden />
                    </button>
                    {admin && (
                      <>
                        <button className="btn-ghost !p-1.5" aria-label={`Edit ${a.title}`} onClick={() => setEditing({ ...a, questions: a.questions.join("\n"), tags: a.tags.join(", ") })}><Pencil className="w-4 h-4" /></button>
                        <button className="btn-ghost !p-1.5" aria-label={`Delete ${a.title}`} onClick={() => remove(a)}><Trash2 className="w-4 h-4" /></button>
                      </>
                    )}
                  </div>
                  {open && (
                    <div className="pb-4 pl-6 text-sm space-y-2">
                      <p className="text-ink-2 whitespace-pre-wrap">{a.answer}</p>
                      <p className="text-xs text-ink-3">{a.source}{a.tags.length ? ` · applies to: ${a.tags.join(", ")}` : ""}</p>
                      {a.questions.length > 0 && <p className="text-xs text-ink-3">Matches questions like: {a.questions.slice(0, 4).join(" · ")}</p>}
                    </div>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </Tile>

      {admin && (
        <Tile className="lg:col-span-4" eyebrow="Suggested new topics" title="What customers ask that we can't answer" icon={Lightbulb}>
          {!topics ? <SkeletonLines rows={4} /> : topics.topics.length === 0 ? (
            <p className="text-sm text-ink-3">No recurring unanswered questions yet ({topics.unanswered_tickets ?? 0} tickets had no matching article).</p>
          ) : (
            <ul className="space-y-3">
              {topics.topics.map((t, i) => (
                <li key={i} className="rounded-2xl border border-line p-3">
                  <p className="text-sm font-semibold">{t.count} tickets · {t.keywords.slice(0, 3).join(", ") || "similar questions"}</p>
                  <p className="text-xs text-ink-3 mt-1 line-clamp-2">“{t.examples[0]}”</p>
                  <button className="btn-ghost !py-1 !text-xs mt-2"
                          onClick={() => setEditing({ ...EMPTY, title: t.label, questions: t.examples.join("\n") })}>
                    <Pencil className="w-3.5 h-3.5" /> Draft an article
                  </button>
                </li>
              ))}
            </ul>
          )}
        </Tile>
      )}
    </div>
  );
}
