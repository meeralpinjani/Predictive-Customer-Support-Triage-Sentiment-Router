import { useEffect, useState } from "react";
import clsx from "clsx";
import { Activity, AlertTriangle, BrainCircuit, CheckCircle2, Clock3, Inbox, KeyRound, Loader2, Shield, Table2, BarChart3, Users } from "lucide-react";
import { api } from "../../api.js";
import { useAuth } from "../../lib/auth.jsx";
import { useLiveData } from "../../lib/events.jsx";
import { ROLE_LABEL, SEGMENT_LABEL, fmtWait, levelTitle, pct, routeMeta, timeAgo } from "../../lib/meta.js";
import { Empty, ErrorNote, PageHeader, Segmented, SkeletonLines, Tile, useToast } from "../../components/ui.jsx";

// ------------------------------------------------------------------ analytics
function HourlyChart({ hourly }) {
  const max = Math.max(1, ...hourly.map((h) => h.total));
  return (
    <div role="img" aria-label="Tickets per hour over the last 24 hours; see table view for values">
      <div className="flex items-end gap-[3px] h-44">
        {hourly.map((h) => {
          const label = new Date(h.hour).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
          return (
            <div key={h.hour} className="flex-1 h-full flex flex-col justify-end group relative"
                 title={`${label}: ${h.total} tickets, ${h.critical} critical, ${h.auto} auto-answered`}>
              <div className="w-full flex flex-col justify-end rounded-t-md overflow-hidden" style={{ height: `${(h.total / max) * 100}%`, minHeight: h.total ? 3 : 0 }}>
                <div style={{ height: `${(h.critical / Math.max(h.total, 1)) * 100}%`, background: "rgb(var(--senior))" }} />
                <div className="flex-1" style={{ background: "rgb(var(--glacier))" }} />
              </div>
              <span className="absolute -top-5 left-1/2 -translate-x-1/2 text-[10px] font-semibold num opacity-0 group-hover:opacity-100">{h.total}</span>
            </div>
          );
        })}
      </div>
      <div className="flex justify-between text-[10px] text-ink-3 mt-1.5">
        {[0, 6, 12, 18, 23].map((i) => <span key={i}>{new Date(hourly[i].hour).toLocaleTimeString([], { hour: "2-digit" })}</span>)}
      </div>
      <div className="flex gap-4 mt-2 text-xs text-ink-2" aria-hidden>
        <span className="flex items-center gap-1.5"><span className="w-3 h-3 rounded-sm" style={{ background: "rgb(var(--glacier))" }} />All tickets</span>
        <span className="flex items-center gap-1.5"><span className="w-3 h-3 rounded-sm" style={{ background: "rgb(var(--senior))" }} />Critical</span>
      </div>
    </div>
  );
}

/** One small multiple: a daily series as bars with direct value labels. */
function DailyBars({ daily, field, fmt = (v) => v, color = "rgb(var(--glacier))", empty = "No data yet" }) {
  const vals = daily.map((d) => d[field]);
  const known = vals.filter((v) => v != null);
  if (known.length === 0) return <p className="text-sm text-ink-3 py-6 text-center">{empty}</p>;
  const max = Math.max(...known, 1e-9);
  return (
    <div>
      <div className="flex items-end gap-1.5 h-28">
        {daily.map((d) => {
          const v = d[field];
          return (
            <div key={d.day} className="flex-1 h-full flex flex-col justify-end items-center" title={`${d.day}: ${v == null ? "no data" : fmt(v)}`}>
              <span className="text-[10px] font-semibold num mb-0.5">{v == null ? "" : fmt(v)}</span>
              <div className="w-full rounded-t-md" style={{ height: v == null ? 2 : `${Math.max((v / max) * 80, v ? 4 : 2)}%`, background: v == null ? "rgb(var(--line))" : color }} />
            </div>
          );
        })}
      </div>
      <div className="flex gap-1.5 mt-1">
        {daily.map((d) => <span key={d.day} className="flex-1 text-center text-[10px] text-ink-3">{new Date(d.day).toLocaleDateString([], { weekday: "short" })}</span>)}
      </div>
    </div>
  );
}

export function AdminAnalytics() {
  const [days, setDays] = useState(7);
  const [view, setView] = useState("chart");
  const { data, error } = useLiveData(() => api.analytics(days), { match: (ev) => ev.type !== "typing", intervalMs: 30000, deps: [days] });
  const today = data?.daily?.[data.daily.length - 1];
  const sum = (f) => data?.daily.reduce((s, d) => s + (d[f] || 0), 0) ?? 0;
  const created = sum("created");

  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 pt-2">
      <PageHeader title="Analytics" subtitle="Computed live from the database: every number below is a real ticket, reply or escalation."
                  actions={<>
                    <Segmented label="View" value={view} onChange={setView} options={[{ value: "chart", label: "Charts", icon: BarChart3 }, { value: "table", label: "Table", icon: Table2 }]} />
                    <Segmented label="Range" value={days} onChange={setDays} options={[7, 14, 30].map((d) => ({ value: d, label: `${d} days` }))} />
                  </>} />
      {error && <div className="lg:col-span-12"><ErrorNote>{error}</ErrorNote></div>}

      {[
        ["Tickets", created, Inbox, "bg-glacier-soft text-glacier-text", `last ${days} days`],
        ["Answered automatically", created ? pct(sum("auto_answered") / created) : "–", CheckCircle2, "bg-auto-soft text-auto-text", `${sum("auto_answered")} tickets`],
        ["Escalations", sum("escalations"), AlertTriangle, "bg-senior-soft text-senior-text", "moved up a level"],
        ["First response today", today?.avg_first_response_min != null ? fmtWait(today.avg_first_response_min) : "–", Clock3, "bg-tier2-soft text-tier2-text", "average"],
      ].map(([label, value, Icon, tone, sub]) => (
        <div key={label} className="tile !p-5 lg:col-span-3">
          <div className="flex items-center justify-between"><p className="text-xs font-semibold text-ink-3">{label}</p>
            <span className={clsx("w-8 h-8 rounded-xl grid place-items-center", tone)}><Icon className="w-4 h-4" aria-hidden /></span></div>
          <p className="mt-2 text-3xl font-extrabold num">{data ? value : "–"}</p>
          <p className="text-xs text-ink-3">{sub}</p>
        </div>
      ))}

      {!data ? <div className="lg:col-span-12 tile"><SkeletonLines rows={6} /></div> : view === "table" ? (
        <Tile className="lg:col-span-12" eyebrow="Per day" icon={Table2}>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead><tr className="text-left text-[11px] uppercase tracking-wider text-ink-3">
                {["Day", "Created", "Auto-answered", "Deflection", "Escalations", "Resolved", "Avg first response", "Avg resolution"].map((h) => <th key={h} className="py-2 pr-3 font-semibold">{h}</th>)}
              </tr></thead>
              <tbody className="divide-y divide-line">
                {data.daily.map((d) => (
                  <tr key={d.day}>
                    <td className="py-2 pr-3">{d.day}</td><td className="num">{d.created}</td><td className="num">{d.auto_answered}</td>
                    <td className="num">{d.deflection_rate == null ? "–" : pct(d.deflection_rate)}</td><td className="num">{d.escalations}</td>
                    <td className="num">{d.resolved}</td><td className="num">{fmtWait(d.avg_first_response_min)}</td><td className="num">{fmtWait(d.avg_resolution_min)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Tile>
      ) : (
        <>
          <Tile className="lg:col-span-8" eyebrow="Last 24 hours" title="Ticket volume per hour" icon={Activity}><HourlyChart hourly={data.hourly} /></Tile>
          <Tile className="lg:col-span-4" eyebrow="Right now" title="Open tickets by level" icon={Inbox}>
            <div className="space-y-3">
              {["level3", "level2", "level1"].map((l) => {
                const max = Math.max(1, ...Object.values(data.open_by_level));
                return (
                  <div key={l}>
                    <div className="flex justify-between text-xs mb-1"><span className="text-ink-2 font-medium">{levelTitle(l)}</span><span className="font-semibold num">{data.open_by_level[l]}</span></div>
                    <div className="h-2 rounded-full bg-sunken overflow-hidden"><div className="h-full rounded-full" style={{ width: `${(data.open_by_level[l] / max) * 100}%`, background: routeMeta(l).bar }} /></div>
                  </div>
                );
              })}
            </div>
            <p className="mt-auto pt-4 text-[11px] text-ink-3">Data since {new Date(data.data_since).toLocaleString()}. Charts fill in as the app is used.</p>
          </Tile>
          {[
            ["Tickets created", "created", (v) => v],
            ["Deflection (answered automatically)", "deflection_rate", (v) => pct(v), "rgb(var(--auto))"],
            ["Escalations", "escalations", (v) => v, "rgb(var(--senior))"],
            ["Resolved", "resolved", (v) => v, "rgb(var(--tier1))"],
            ["Avg first response", "avg_first_response_min", fmtWait, "rgb(var(--tier2))", "No agent replies yet"],
            ["Avg time to resolve", "avg_resolution_min", fmtWait, "rgb(var(--tier1))", "No resolved tickets yet"],
          ].map(([title, field, fmt, color, empty]) => (
            <Tile key={field} className="lg:col-span-4" eyebrow={`Per day · ${days} days`} title={title}>
              <DailyBars daily={data.daily} field={field} fmt={fmt} color={color} empty={empty} />
            </Tile>
          ))}
        </>
      )}
    </div>
  );
}

// ------------------------------------------------------------------ users & workload
const ROLES = ["customer", "level1", "level2", "level3", "admin"];
const PLANS = ["free", "basic", "pro", "enterprise"];
const AVAIL_DOT = { available: "bg-tier1", busy: "bg-tier2", offline: "bg-ink-3" };

export function AdminUsers() {
  const { user: me } = useAuth();
  const toast = useToast();
  const { data: users, error, reload } = useLiveData(() => api.users(), { intervalMs: 30000 });
  const { data: work, reload: reloadWork } = useLiveData(() => api.workload(), { match: (ev) => ev.type !== "typing", intervalMs: 15000 });
  const [q, setQ] = useState("");
  const [roleFilter, setRoleFilter] = useState("all");

  const update = async (u, patch, msg) => {
    try {
      await api.updateUser(u.id, patch);
      toast(msg, "success");
      await Promise.all([reload(), reloadWork()]);
    } catch (err) {
      toast(err.message, "error");
    }
  };

  const rows = (users ?? []).filter((u) => (roleFilter === "all" || u.role === roleFilter) &&
    (!q || `${u.name} ${u.email}`.toLowerCase().includes(q.toLowerCase())));
  const workBy = Object.fromEntries((work ?? []).filter((w) => w.id).map((w) => [w.id, w]));
  const [link, setLink] = useState(null);
  const requests = (users ?? []).filter((u) => u.reset_requested_at);

  const makeLink = async (u) => {
    try {
      const res = await api.adminResetLink(u.id);
      setLink({ user: u, url: `${window.location.origin}${res.path}`, minutes: res.expires_minutes });
      await reload();
    } catch (err) {
      toast(err.message, "error");
    }
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 pt-2">
      <PageHeader title="Users & workload" subtitle="Promote sign-ups to agents, set each agent's capacity, and see who is carrying what." />
      {["level1", "level2", "level3"].map((lvl) => {
        const agents = (work ?? []).filter((w) => w.level === lvl && w.id);
        const unassigned = (work ?? []).find((w) => w.level === lvl && !w.id)?.open ?? 0;
        return (
          <Tile key={lvl} className="lg:col-span-4" eyebrow={ROLE_LABEL[lvl]} icon={Shield}>
            {!work ? <SkeletonLines rows={2} /> : agents.length === 0 ? <p className="text-sm text-ink-3">No agents at this level yet: tickets wait unassigned.</p> : (
              <ul className="space-y-3">
                {agents.map((a) => (
                  <li key={a.id}>
                    <div className="flex items-center justify-between text-sm">
                      <span className="flex items-center gap-2 font-semibold"><span className={clsx("w-2 h-2 rounded-full", AVAIL_DOT[a.availability])} aria-hidden />{a.name}</span>
                      <span className="num text-ink-2">{a.open}/{a.max_open}</span>
                    </div>
                    <div className="mt-1 h-2 rounded-full bg-sunken overflow-hidden" title={`${a.open} open of ${a.max_open} capacity`}>
                      <div className="h-full rounded-full" style={{ width: `${Math.min(a.open / Math.max(a.max_open, 1), 1) * 100}%`, background: a.open >= a.max_open ? "rgb(var(--senior))" : routeMeta(lvl).bar }} />
                    </div>
                    <p className="text-[11px] text-ink-3 mt-0.5">{a.availability} · {a.in_progress} in progress · {a.resolved_today} resolved today</p>
                  </li>
                ))}
              </ul>
            )}
            {work && <p className={clsx("mt-auto pt-3 text-xs", unassigned ? "text-tier2-text font-semibold" : "text-ink-3")}>{unassigned} ticket{unassigned === 1 ? "" : "s"} waiting unassigned</p>}
          </Tile>
        );
      })}

      {(requests.length > 0 || link) && (
        <Tile className="lg:col-span-12" eyebrow="Password help" title={link ? `Reset link for ${link.user.name}` : `${requests.length} user${requests.length === 1 ? "" : "s"} lost their recovery code`} icon={KeyRound}>
          {link ? (
            <div className="space-y-3">
              <p className="text-sm text-ink-2">Give this link to <b>{link.user.email}</b>. It works once and expires in {link.minutes} minutes.</p>
              <div className="flex gap-2">
                <input className="field font-mono !text-xs" readOnly value={link.url} onFocus={(e) => e.target.select()} aria-label="Reset link" />
                <button className="btn-primary shrink-0" onClick={async () => {
                  try { await navigator.clipboard.writeText(link.url); toast("Link copied", "success"); } catch { /* select manually */ }
                }}>Copy</button>
                <button className="btn-ghost shrink-0" onClick={() => setLink(null)}>Done</button>
              </div>
            </div>
          ) : (
            <ul className="divide-y divide-line">
              {requests.map((u) => (
                <li key={u.id} className="py-2.5 flex items-center gap-3">
                  <span className="flex-1 min-w-0"><span className="block text-sm font-semibold">{u.name}</span>
                    <span className="block text-xs text-ink-3">{u.email} · asked {timeAgo(u.reset_requested_at)}</span></span>
                  <button className="btn-primary !py-1.5" onClick={() => makeLink(u)}>Create reset link</button>
                </li>
              ))}
            </ul>
          )}
        </Tile>
      )}

      <Tile className="lg:col-span-12" eyebrow="Access control" title="All users" icon={Users}
            action={
              <div className="flex flex-wrap gap-2">
                <input className="field !py-1.5 w-48" placeholder="Search" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search users" />
                <select className="field !py-1.5 w-44" value={roleFilter} onChange={(e) => setRoleFilter(e.target.value)} aria-label="Filter by role">
                  <option value="all">All roles</option>
                  {ROLES.map((r) => <option key={r} value={r}>{ROLE_LABEL[r]}</option>)}
                </select>
              </div>
            }>
        {error && <ErrorNote>{error}</ErrorNote>}
        {!users ? <SkeletonLines rows={6} /> : rows.length === 0 ? <Empty icon={Users}>No users match.</Empty> : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead><tr className="text-left text-[11px] uppercase tracking-wider text-ink-3">
                {["User", "Role", "Plan / capacity", "Availability", "Sign-in", "Status"].map((h) => <th key={h} className="py-2 pr-3 font-semibold">{h}</th>)}
              </tr></thead>
              <tbody className="divide-y divide-line">
                {rows.map((u) => {
                  const agent = ["level1", "level2", "level3"].includes(u.role);
                  return (
                    <tr key={u.id} className={clsx(!u.active && "opacity-50")}>
                      <td className="py-2.5 pr-3"><p className="font-semibold">{u.name}{u.id === me.id && " (you)"}</p><p className="text-xs text-ink-3">{u.email}</p></td>
                      <td className="py-2.5 pr-3">
                        <select className="field !py-1 w-52" value={u.role} disabled={u.id === me.id} aria-label={`Role for ${u.name}`}
                                onChange={(e) => update(u, { role: e.target.value }, `${u.name} is now ${ROLE_LABEL[e.target.value]}`)}>
                          {ROLES.map((r) => <option key={r} value={r}>{ROLE_LABEL[r]}</option>)}
                        </select>
                      </td>
                      <td className="py-2.5 pr-3">
                        {u.customer ? (
                          <select className="field !py-1 w-32" value={u.customer.segment} aria-label={`Plan for ${u.name}`}
                                  onChange={(e) => update(u, { plan: e.target.value }, `Plan updated for ${u.name}`)}>
                            {PLANS.map((p) => <option key={p} value={p}>{SEGMENT_LABEL[p]}</option>)}
                          </select>
                        ) : agent ? (
                          <label className="flex items-center gap-2 text-xs text-ink-3">max
                            <input type="number" min={0} max={100} defaultValue={u.max_open} className="field !py-1 w-16"
                                   onBlur={(e) => Number(e.target.value) !== u.max_open && update(u, { max_open: Number(e.target.value) }, `${u.name} can now hold ${e.target.value} tickets`)}
                                   aria-label={`Capacity for ${u.name}`} />
                            {workBy[u.id] && <span className="num">({workBy[u.id].open} open)</span>}
                          </label>
                        ) : <span className="text-ink-3">—</span>}
                      </td>
                      <td className="py-2.5 pr-3">
                        {agent ? (
                          <select className="field !py-1 w-32" value={u.availability} aria-label={`Availability for ${u.name}`}
                                  onChange={(e) => update(u, { availability: e.target.value }, `${u.name} set to ${e.target.value}`)}>
                            {["available", "busy", "offline"].map((a) => <option key={a} value={a}>{a[0].toUpperCase() + a.slice(1)}</option>)}
                          </select>
                        ) : <span className="text-ink-3">—</span>}
                      </td>
                      <td className="py-2.5 pr-3 text-ink-2">{u.auth === "both" ? "Password + Google" : u.auth === "google" ? "Google" : "Password"}</td>
                      <td className="py-2.5 text-right">
                        <div className="flex justify-end gap-1.5">
                          <button className="btn-ghost !py-1 !text-xs" disabled={!u.active} onClick={() => makeLink(u)} title="One-time password reset link">
                            Reset link
                          </button>
                          <button className="btn-ghost !py-1 !text-xs" disabled={u.id === me.id}
                                  onClick={() => update(u, { active: !u.active }, u.active ? `${u.name} disabled` : `${u.name} enabled`)}>
                            {u.active ? "Disable" : "Enable"}
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Tile>
    </div>
  );
}

// ------------------------------------------------------------------ retrain
export function RetrainTile({ className = "lg:col-span-4" }) {
  const toast = useToast();
  const [res, setRes] = useState(null);
  const [busy, setBusy] = useState(false);
  const check = async () => {
    setBusy(true);
    try {
      setRes(await api.retrain());
    } catch (err) {
      toast(err.message, "error");
    } finally {
      setBusy(false);
    }
  };
  useEffect(() => { check(); }, []); // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <Tile className={className} eyebrow="Learn from agents" title="Retrain routing" icon={BrainCircuit}
          action={<button className="btn-ghost !py-1 !px-2.5 !text-xs" onClick={check} disabled={busy}>{busy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : "Re-check"}</button>}>
      <p className="text-xs text-ink-3 mb-3">Every time an agent escalates or an admin re-routes a ticket, that decision is saved. Retraining finds the thresholds that agree with your agents most often.</p>
      {!res ? <SkeletonLines rows={3} /> : res.status === "insufficient" ? (
        <>
          <div className="flex justify-between text-xs mb-1"><span className="text-ink-2 font-medium">Agent decisions collected</span><span className="font-semibold num">{res.decisions}/{res.needed}</span></div>
          <div className="h-2 rounded-full bg-sunken overflow-hidden"><div className="h-full rounded-full bg-glacier" style={{ width: `${(res.decisions / res.needed) * 100}%` }} /></div>
          <p className="mt-3 text-sm text-ink-2">{res.message}</p>
        </>
      ) : (
        <>
          <dl className="grid grid-cols-2 gap-2 text-sm">
            <div className="rounded-xl bg-sunken p-3"><dt className="text-[11px] text-ink-3">Agreement now</dt><dd className="text-xl font-bold num">{pct(res.agreement_before)}</dd></div>
            <div className="rounded-xl bg-sunken p-3"><dt className="text-[11px] text-ink-3">After retraining</dt><dd className="text-xl font-bold num text-tier1-text">{pct(res.agreement_after)}</dd></div>
          </dl>
          <p className="mt-3 text-xs text-ink-2">Level 3 from score {res.current.level3_score} → <b>{res.proposed.level3_score}</b> · frustration threshold {res.current.frustration_senior} → <b>{res.proposed.frustration_senior}</b></p>
          <button className="btn-primary mt-3" disabled={busy || res.agreement_after <= res.agreement_before}
                  onClick={async () => { await api.retrainApply(res.proposed); toast("New thresholds applied", "success"); check(); }}>Apply</button>
        </>
      )}
    </Tile>
  );
}
