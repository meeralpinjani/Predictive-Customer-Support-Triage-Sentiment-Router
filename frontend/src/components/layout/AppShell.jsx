import { useEffect, useRef, useState } from "react";
import { Link, NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import clsx from "clsx";
import {
  BarChart3, Bell, BookOpen, Inbox, LayoutDashboard, LifeBuoy, LogOut, Moon, PlusCircle, SlidersHorizontal,
  Snowflake, Sun, Users,
} from "lucide-react";
import { useAuth } from "../../lib/auth.jsx";
import { chime, useEvents, useEventListener } from "../../lib/events.jsx";
import { ROLE_LABEL, isAgentRole, levelTitle, routeMeta, timeAgo } from "../../lib/meta.js";
import { useTheme, useToast } from "../ui.jsx";

const NAV = {
  customer: [
    { to: "/support", label: "My tickets", icon: LifeBuoy, end: true },
    { to: "/support/new", label: "New ticket", icon: PlusCircle },
  ],
  agent: [
    { to: "/queue", label: "My queue", icon: Inbox },
    { to: "/knowledge", label: "Knowledge base", icon: BookOpen },
  ],
  admin: [
    { to: "/admin", label: "Overview", icon: LayoutDashboard, end: true },
    { to: "/admin/insights", label: "Insights", icon: BarChart3 },
    { to: "/admin/users", label: "Users & roles", icon: Users },
    { to: "/admin/tuning", label: "Tuning", icon: SlidersHorizontal },
    { to: "/knowledge", label: "Knowledge base", icon: BookOpen },
  ],
};

const navFor = (role) => (role === "customer" ? NAV.customer : role === "admin" ? NAV.admin : NAV.agent);

/** Turn a live event into a notification for this user, or null. */
function describe(ev, user) {
  const id = ev.ticket_id;
  const mine = user.role === "customer";
  const toHref = mine ? `/support/tickets/${id}` : `/tickets/${id}`;
  if (ev.type === "ticket.escalated") {
    if (mine) return { text: `Ticket #${id} is now with ${levelTitle(ev.route)}`, href: toHref, alert: ev.route === "level3", kind: "info" };
    if (ev.route === user.role || user.role === "admin")
      return { text: `Ticket #${id} escalated to ${routeMeta(ev.route).label}${ev.reason ? `: ${ev.reason}` : ""}`, href: toHref, alert: true, kind: "error" };
    if (ev.old_route === user.role) return { text: `Ticket #${id} moved up to ${routeMeta(ev.route).label}`, href: toHref, kind: "info" };
  }
  if (ev.type === "ticket.created" && isAgentRole(user.role) && ev.route === user.role)
    return { text: `New ticket #${id} in your queue`, href: toHref, kind: "info" };
  if (ev.type === "message.created" && ev.actor_id !== user.id) {
    if (mine && ev.author_role !== "customer") return { text: `Support replied on ticket #${id}`, href: toHref, alert: true, kind: "success" };
    if (!mine && ev.author_role === "customer") return { text: `New customer message on #${id}`, href: toHref, kind: "info" };
  }
  if (ev.type === "callback.requested" && (user.role === "level3" || user.role === "admin"))
    return { text: `Callback requested on ticket #${id}`, href: toHref, alert: true, kind: "error" };
  if (ev.type === "callback.updated" && mine) return { text: `Your call on ticket #${id} was updated`, href: toHref, kind: "info" };
  if (ev.type === "ticket.resolved" && mine) return { text: `Ticket #${id} was resolved`, href: toHref, kind: "success" };
  return null;
}

function NotificationBell({ items, unread, onOpen }) {
  const [open, setOpen] = useState(false);
  const ref = useRef();
  useEffect(() => {
    const close = (e) => ref.current && !ref.current.contains(e.target) && setOpen(false);
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, []);
  return (
    <div className="relative" ref={ref}>
      <button className="btn-ghost !p-2 !rounded-full relative" aria-label={`Notifications${unread ? `, ${unread} unread` : ""}`}
              onClick={() => { setOpen((o) => !o); onOpen(); }}>
        <Bell className="w-4 h-4" />
        {unread > 0 && (
          <span className="absolute -top-0.5 -right-0.5 min-w-[18px] h-[18px] px-1 rounded-full bg-senior text-white text-[10px] font-bold grid place-items-center num">
            {unread > 9 ? "9+" : unread}
          </span>
        )}
      </button>
      {open && (
        <div className="absolute right-0 mt-2 w-[min(88vw,340px)] z-40 tile !p-2 max-h-[60vh] overflow-y-auto scroll-thin">
          {items.length === 0 ? <p className="p-3 text-sm text-ink-3">No notifications yet.</p> : items.map((n) => (
            <Link key={n.id} to={n.href} onClick={() => setOpen(false)} className="block rounded-xl px-3 py-2 hover:bg-sunken">
              <p className="text-sm">{n.text}</p>
              <p className="text-[11px] text-ink-3">{timeAgo(n.at)}</p>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

export default function AppShell() {
  const { user, logout } = useAuth();
  const { connected } = useEvents();
  const [theme, toggleTheme] = useTheme();
  const toast = useToast();
  const navigate = useNavigate();
  const location = useLocation();
  const [notes, setNotes] = useState([]);
  const [unread, setUnread] = useState(0);

  useEventListener((ev) => {
    const n = describe(ev, user);
    if (!n) return;
    setNotes((xs) => [{ ...n, id: `${Date.now()}-${Math.random()}`, at: new Date().toISOString() }, ...xs].slice(0, 25));
    setUnread((u) => u + 1);
    toast(n.text, n.kind);
    if (n.alert) chime();
  });

  const nav = navFor(user.role);
  const roleBadge = user.role === "customer" ? `${ROLE_LABEL.customer} · ${user.customer?.plan || ""}` : ROLE_LABEL[user.role];

  return (
    <div className="min-h-screen lg:flex">
      {/* ---------------- desktop sidebar */}
      <aside className="hidden lg:flex lg:flex-col w-64 shrink-0 h-screen sticky top-0 border-r border-line bg-card px-4 py-5">
        <Link to="/" className="flex items-center gap-3 px-2">
          <span className="w-9 h-9 rounded-2xl bg-fjord grid place-items-center"><Snowflake className="w-5 h-5 text-sky-300" aria-hidden /></span>
          <span>
            <span className="block font-extrabold tracking-tight leading-tight">Triage Router</span>
            <span className="block text-[11px] text-ink-3">AlgoAmigos</span>
          </span>
        </Link>
        <nav className="mt-8 space-y-1" aria-label="Main">
          {nav.map((item) => (
            <NavLink key={item.to} to={item.to} end={item.end}
                     className={({ isActive }) => clsx("flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-semibold transition",
                       isActive ? "bg-fjord text-white dark:bg-glacier dark:text-fjord" : "text-ink-2 hover:bg-sunken")}>
              <item.icon className="w-4 h-4" aria-hidden /> {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="mt-auto space-y-3">
          <div className="rounded-2xl bg-sunken p-3">
            <p className="text-sm font-semibold truncate">{user.name}</p>
            <p className="text-[11px] text-ink-3 truncate">{user.email}</p>
            <span className="chip bg-card border border-line text-ink-2 mt-2">{roleBadge}</span>
          </div>
          <div className="flex items-center justify-between px-1 text-xs text-ink-3">
            <span className="flex items-center gap-1.5">
              <span className={clsx("w-2 h-2 rounded-full", connected ? "bg-tier1" : "bg-ink-3")} aria-hidden />
              {connected ? "Live" : "Reconnecting…"}
            </span>
            <div className="flex gap-1">
              <button onClick={toggleTheme} className="btn-ghost !p-2 !rounded-full" aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}>
                {theme === "dark" ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
              </button>
              <button onClick={async () => { await logout(); navigate("/login"); }} className="btn-ghost !p-2 !rounded-full" aria-label="Sign out">
                <LogOut className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>
      </aside>

      <div className="flex-1 min-w-0 pb-20 lg:pb-0">
        {/* ---------------- top bar */}
        <header className="sticky top-0 z-30 bg-canvas/85 backdrop-blur border-b border-line lg:border-none">
          <div className="mx-auto max-w-[1480px] px-4 sm:px-6 lg:px-8 h-14 flex items-center justify-between gap-3">
            <Link to="/" className="lg:hidden flex items-center gap-2 font-extrabold tracking-tight">
              <span className="w-8 h-8 rounded-xl bg-fjord grid place-items-center"><Snowflake className="w-4 h-4 text-sky-300" aria-hidden /></span>
              Triage Router
            </Link>
            <p className="hidden lg:block text-sm text-ink-3">{roleBadge}</p>
            <div className="flex items-center gap-1.5">
              <NotificationBell items={notes} unread={unread} onOpen={() => setUnread(0)} />
              <button onClick={toggleTheme} className="lg:hidden btn-ghost !p-2 !rounded-full" aria-label="Toggle theme">
                {theme === "dark" ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
              </button>
              <button onClick={async () => { await logout(); navigate("/login"); }} className="lg:hidden btn-ghost !p-2 !rounded-full" aria-label="Sign out">
                <LogOut className="w-4 h-4" />
              </button>
            </div>
          </div>
        </header>
        <main className="mx-auto max-w-[1480px] px-4 sm:px-6 lg:px-8 pb-8" key={location.pathname.split("/")[1]}>
          <Outlet />
        </main>
      </div>

      {/* ---------------- mobile bottom bar */}
      <nav className="lg:hidden fixed bottom-0 inset-x-0 z-30 bg-card border-t border-line grid" aria-label="Main"
           style={{ gridTemplateColumns: `repeat(${nav.length}, minmax(0, 1fr))` }}>
        {nav.map((item) => (
          <NavLink key={item.to} to={item.to} end={item.end}
                   className={({ isActive }) => clsx("flex flex-col items-center gap-0.5 py-2 text-[10px] font-semibold",
                     isActive ? "text-glacier-text" : "text-ink-3")}>
            <item.icon className="w-5 h-5" aria-hidden /> {item.label}
          </NavLink>
        ))}
      </nav>
    </div>
  );
}
