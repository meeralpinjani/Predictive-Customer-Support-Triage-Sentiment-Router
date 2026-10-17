import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import clsx from "clsx";
import { BookOpen, ExternalLink, Search, Shield, Users } from "lucide-react";
import { api } from "../../api.js";
import { useAuth } from "../../lib/auth.jsx";
import { useLiveData } from "../../lib/events.jsx";
import { ROLE_LABEL, SEGMENT_LABEL, timeAgo } from "../../lib/meta.js";
import { DeflectionTile, LiveQueueHero, WaitTile } from "../../components/live/Overview.jsx";
import SubmitTile from "../../components/live/SubmitTile.jsx";
import QueueTile from "../../components/live/QueueTile.jsx";
import WhatIfTile from "../../components/live/WhatIfTile.jsx";
import TicketExplain from "../../components/TicketExplain.jsx";
import { AblationTile, ModelTile, ResultsTile, ScorecardTile } from "../../components/insights/Evidence.jsx";
import {
  FormulaTile, KbTesterTile, MethodTile, RouteMixTile, SegmentWaitTile, TrustTile,
} from "../../components/insights/Operations.jsx";
import { Empty, ErrorNote, SkeletonLines, Tile, useToast } from "../../components/ui.jsx";

function useStatic(loader) {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  useEffect(() => {
    loader().then(setData).catch((e) => setError(e.message));
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
  return [data, error];
}

export function AdminOverview() {
  const navigate = useNavigate();
  const [selectedId, setSelectedId] = useState(null);
  const [preview, setPreview] = useState(null);
  const [customers] = useStatic(api.customers);
  const [cats] = useStatic(api.categories);
  const [config] = useStatic(api.config);
  const { data: tickets, reload } = useLiveData(() => api.tickets(), { match: () => true, intervalMs: 10000 });
  const { data: stats } = useLiveData(() => api.stats(), { match: () => true, intervalMs: 10000 });
  const list = tickets ?? [];
  const selected = list.find((t) => t.id === selectedId) ?? null;

  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 pt-2">
      <LiveQueueHero tickets={list} loading={!tickets} />
      <DeflectionTile stats={stats} />
      <WaitTile stats={stats} />

      <SubmitTile customers={customers ?? []} categories={cats?.categories ?? []}
                  onSubmitted={async (t) => { setSelectedId(t.id); await reload(); }} onOpen={setSelectedId} />
      <QueueTile tickets={list} loading={!tickets} selectedId={selectedId} onSelect={setSelectedId} preview={preview}
                 eyebrow="All levels" title="Live queue" />

      <TicketExplain ticket={selected} onChanged={reload} admin
                     action={selected && (
                       <button className="btn-ghost !p-2 !rounded-full" onClick={() => navigate(`/tickets/${selected.id}`)} aria-label="Open full ticket">
                         <ExternalLink className="w-4 h-4" />
                       </button>
                     )} />
      <WhatIfTile config={config} onPreview={setPreview} ticketsVersion={list.length} />
    </div>
  );
}

export function AdminInsights() {
  const [report, error] = useStatic(api.evaluation);
  const [config] = useStatic(api.config);
  const { data: stats } = useLiveData(() => api.stats(), { intervalMs: 15000 });
  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 pt-2">
      <ResultsTile report={report} error={error} />
      <ScorecardTile report={report} error={error} />
      <AblationTile report={report} />
      <ModelTile report={report} />
      <FormulaTile config={config} />
      <div className="lg:col-span-4 grid gap-4 content-start">
        <RouteMixTile stats={stats} />
        <SegmentWaitTile stats={stats} />
      </div>
      <div className="lg:col-span-8"><MethodTile report={report} /></div>
    </div>
  );
}

export function AdminTuning() {
  const [config] = useStatic(api.config);
  const { data: stats, reload } = useLiveData(() => api.stats(), { intervalMs: 15000 });
  const { data: health } = useLiveData(() => api.health(), { intervalMs: 15000 });
  const [preview, setPreview] = useState(null);
  const { data: tickets } = useLiveData(() => api.tickets(), { match: () => true });
  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 pt-2">
      <WhatIfTile config={config} onPreview={setPreview} ticketsVersion={tickets?.length ?? 0} />
      <QueueTile tickets={tickets ?? []} loading={!tickets} onSelect={() => {}} preview={preview}
                 eyebrow="Preview" title="Queue under these settings" />
      <FormulaTile config={config} />
      <KbTesterTile />
      <TrustTile stats={stats} health={health} onRescore={async () => { await api.rescore(); await reload(); }} />
    </div>
  );
}

const ROLES = ["customer", "level1", "level2", "level3", "admin"];
const PLANS = ["free", "basic", "pro", "enterprise"];

export function AdminUsers() {
  const { user: me } = useAuth();
  const toast = useToast();
  const { data: users, error, reload } = useLiveData(() => api.users(), { intervalMs: 30000 });
  const [q, setQ] = useState("");
  const [roleFilter, setRoleFilter] = useState("all");

  const update = async (u, patch, msg) => {
    try {
      await api.updateUser(u.id, patch);
      toast(msg, "success");
      await reload();
    } catch (err) {
      toast(err.message, "error");
    }
  };

  const rows = (users ?? []).filter((u) =>
    (roleFilter === "all" || u.role === roleFilter) &&
    (!q || `${u.name} ${u.email}`.toLowerCase().includes(q.toLowerCase())));
  const counts = Object.fromEntries(ROLES.map((r) => [r, (users ?? []).filter((u) => u.role === r && u.active).length]));

  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 pt-2">
      {["level1", "level2", "level3"].map((lvl) => (
        <Tile key={lvl} className="lg:col-span-4" eyebrow={ROLE_LABEL[lvl]} icon={Shield}>
          <p className="text-4xl font-extrabold num">{users ? counts[lvl] : "–"}</p>
          <p className="text-sm text-ink-3">active agent{counts[lvl] === 1 ? "" : "s"}{users && counts[lvl] === 0 && " — tickets at this level wait unassigned"}</p>
        </Tile>
      ))}
      <Tile className="lg:col-span-12" eyebrow="Access control" title="Users & roles" icon={Users}
            action={
              <div className="flex gap-2">
                <div className="relative">
                  <Search className="w-4 h-4 absolute left-2.5 top-2.5 text-ink-3" aria-hidden />
                  <input className="field !pl-8 w-48" placeholder="Search" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search users" />
                </div>
                <select className="field w-40" value={roleFilter} onChange={(e) => setRoleFilter(e.target.value)} aria-label="Filter by role">
                  <option value="all">All roles</option>
                  {ROLES.map((r) => <option key={r} value={r}>{ROLE_LABEL[r]}</option>)}
                </select>
              </div>
            }>
        <p className="text-sm text-ink-3 mb-3">New sign-ups start as customers. Promote someone to an agent level here; each level needs at least one active agent.</p>
        {error && <ErrorNote>{error}</ErrorNote>}
        {!users ? <SkeletonLines rows={6} /> : rows.length === 0 ? <Empty icon={Users}>No users match.</Empty> : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-[11px] uppercase tracking-wider text-ink-3">
                  <th className="py-2 font-semibold">User</th><th className="py-2 font-semibold">Role</th>
                  <th className="py-2 font-semibold">Plan</th><th className="py-2 font-semibold">Sign-in</th>
                  <th className="py-2 font-semibold">Joined</th><th className="py-2 font-semibold text-right">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {rows.map((u) => (
                  <tr key={u.id} className={clsx(!u.active && "opacity-50")}>
                    <td className="py-2.5 pr-3"><p className="font-semibold">{u.name}{u.id === me.id && " (you)"}</p><p className="text-xs text-ink-3">{u.email}</p></td>
                    <td className="py-2.5 pr-3">
                      <select className="field !py-1 w-52" value={u.role} disabled={u.id === me.id}
                              onChange={(e) => update(u, { role: e.target.value }, `${u.name} is now ${ROLE_LABEL[e.target.value]}`)} aria-label={`Role for ${u.name}`}>
                        {ROLES.map((r) => <option key={r} value={r}>{ROLE_LABEL[r]}</option>)}
                      </select>
                    </td>
                    <td className="py-2.5 pr-3">
                      {u.customer ? (
                        <select className="field !py-1 w-32" value={u.customer.segment}
                                onChange={(e) => update(u, { plan: e.target.value }, `Plan updated for ${u.name}`)} aria-label={`Plan for ${u.name}`}>
                          {PLANS.map((p) => <option key={p} value={p}>{SEGMENT_LABEL[p]}</option>)}
                        </select>
                      ) : <span className="text-ink-3">—</span>}
                    </td>
                    <td className="py-2.5 pr-3 text-ink-2">{u.auth === "both" ? "Password + Google" : u.auth === "google" ? "Google" : "Password"}</td>
                    <td className="py-2.5 pr-3 text-ink-3">{u.created_at ? timeAgo(u.created_at) : "—"}</td>
                    <td className="py-2.5 text-right">
                      <button className="btn-ghost !py-1 !text-xs" disabled={u.id === me.id}
                              onClick={() => update(u, { active: !u.active }, u.active ? `${u.name} disabled` : `${u.name} enabled`)}>
                        {u.active ? "Disable" : "Enable"}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Tile>
    </div>
  );
}

export function KnowledgePage() {
  const [articles, error] = useStatic(api.kbArticles);
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(null);
  const rows = useMemo(() => (articles ?? []).filter((a) =>
    !q || `${a.title} ${a.answer} ${a.questions.join(" ")}`.toLowerCase().includes(q.toLowerCase())), [articles, q]);
  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 pt-2">
      <Tile className="lg:col-span-12" eyebrow="Help centre" title={`Knowledge base${articles ? ` · ${articles.length} articles` : ""}`} icon={BookOpen}
            action={<input className="field w-56" placeholder="Search articles" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search articles" />}>
        {error && <ErrorNote>{error}</ErrorNote>}
        {!articles ? <SkeletonLines rows={6} /> : (
          <ul className="grid gap-2 md:grid-cols-2">
            {rows.map((a) => (
              <li key={a.id} className="rounded-2xl border border-line">
                <button className="w-full text-left p-4" onClick={() => setOpen(open === a.id ? null : a.id)} aria-expanded={open === a.id}>
                  <p className="font-semibold text-sm">{a.title}</p>
                  <p className="text-[11px] text-ink-3">{a.source} · {a.questions.length} example questions</p>
                </button>
                {open === a.id && (
                  <div className="px-4 pb-4 text-sm space-y-2">
                    <p className="text-ink-2">{a.answer}</p>
                    <p className="text-xs text-ink-3">Matches questions like: {a.questions.slice(0, 4).join(" · ")}</p>
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
      </Tile>
    </div>
  );
}

export function NotFound() {
  return (
    <div className="pt-10"><Empty icon={Search}>Page not found. <Link to="/" className="text-glacier-text font-semibold">Go home</Link></Empty></div>
  );
}
