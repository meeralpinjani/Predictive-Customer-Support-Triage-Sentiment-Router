import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import clsx from "clsx";
import { BookOpen, Building2, Loader2, Lock, Search, Ticket, UserRound } from "lucide-react";
import { api } from "../../api.js";
import { useAuth } from "../../lib/auth.jsx";
import { ROLE_LABEL, routeMeta } from "../../lib/meta.js";

export function articleHref(user, a) {
  return user.role === "customer" ? `/help?article=${a.id}` : `/knowledge?article=${a.id}`;
}

/** Flattened, role-scoped results with hrefs, used by the dropdown and the results page. */
export function flatten(user, res) {
  if (!res) return [];
  const rows = [];
  (res.articles || []).forEach((a) => rows.push({ group: user.role === "customer" ? "Help articles" : "Articles & guides",
    key: `a${a.id}`, icon: a.visibility === "internal" ? Lock : BookOpen, title: a.title,
    sub: a.visibility === "internal" ? "Internal guide" : a.source, href: articleHref(user, a) }));
  (res.tickets || []).forEach((t) => rows.push({ group: "Tickets", key: `t${t.id}`, icon: Ticket,
    title: `#${t.id} · ${t.subject}`, sub: [t.customer, routeMeta(t.route).label, t.status].filter(Boolean).join(" · "), href: t.url }));
  (res.customers || []).forEach((c) => rows.push({ group: "Customers", key: `c${c.id}`, icon: Building2, title: c.name,
    sub: `${c.plan} · ${c.open_tickets} open`, href: `/search?q=${encodeURIComponent(c.name)}` }));
  (res.users || []).forEach((u) => rows.push({ group: "Users", key: `u${u.id}`, icon: UserRound, title: u.name,
    sub: `${u.email} · ${ROLE_LABEL[u.role]}`, href: "/admin/users" }));
  return rows;
}

const PLACEHOLDER = {
  customer: "Search help articles and your tickets…",
  admin: "Search tickets, customers, users or articles…",
};

export default function GlobalSearch() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [q, setQ] = useState("");
  const [res, setRes] = useState(null);
  const [busy, setBusy] = useState(false);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const timer = useRef();
  const box = useRef();
  const input = useRef();

  useEffect(() => {
    const onKey = (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        input.current?.focus();
      }
    };
    const close = (e) => box.current && !box.current.contains(e.target) && setOpen(false);
    window.addEventListener("keydown", onKey);
    document.addEventListener("mousedown", close);
    return () => {
      window.removeEventListener("keydown", onKey);
      document.removeEventListener("mousedown", close);
    };
  }, []);

  useEffect(() => {
    clearTimeout(timer.current);
    if (q.trim().length < 2) {
      setRes(null);
      return undefined;
    }
    timer.current = setTimeout(async () => {
      setBusy(true);
      try {
        setRes(await api.search(q.trim()));
        setActive(0);
      } catch {
        setRes(null);
      } finally {
        setBusy(false);
      }
    }, 220);
    return () => clearTimeout(timer.current);
  }, [q]);

  const rows = flatten(user, res);
  const go = (href) => {
    setOpen(false);
    setQ("");
    navigate(href);
  };
  const onKeyDown = (e) => {
    if (e.key === "ArrowDown") { e.preventDefault(); setActive((a) => Math.min(a + 1, rows.length - 1)); }
    if (e.key === "ArrowUp") { e.preventDefault(); setActive((a) => Math.max(a - 1, 0)); }
    if (e.key === "Escape") setOpen(false);
    if (e.key === "Enter") {
      e.preventDefault();
      if (rows[active]) go(rows[active].href);
      else if (q.trim()) go(`/search?q=${encodeURIComponent(q.trim())}`);
    }
  };

  let lastGroup = null;
  return (
    <div className="relative w-full max-w-xl" ref={box}>
      <div className="flex items-center gap-2 rounded-2xl border border-line bg-card px-3 h-10 focus-within:ring-2 focus-within:ring-glacier/30 focus-within:border-glacier">
        {busy ? <Loader2 className="w-4 h-4 text-ink-3 animate-spin" /> : <Search className="w-4 h-4 text-ink-3" aria-hidden />}
        <input ref={input} value={q} onChange={(e) => { setQ(e.target.value); setOpen(true); }} onFocus={() => setOpen(true)}
               onKeyDown={onKeyDown} placeholder={PLACEHOLDER[user.role] || "Search your tickets, customers and the knowledge base…"}
               className="flex-1 min-w-0 bg-transparent text-sm outline-none placeholder:text-ink-3" aria-label="Search"
               role="combobox" aria-expanded={open && rows.length > 0} aria-controls="search-results" />
        <kbd className="hidden md:inline text-[10px] text-ink-3 border border-line rounded px-1.5 py-0.5">Ctrl K</kbd>
      </div>
      {open && q.trim().length >= 2 && res && (
        <div id="search-results" role="listbox" className="absolute left-0 right-0 mt-2 z-40 tile !p-2 max-h-[65vh] overflow-y-auto scroll-thin">
          {rows.length === 0 ? <p className="p-3 text-sm text-ink-3">No results for “{q}”.</p> : rows.map((r, i) => {
            const header = r.group !== lastGroup ? (lastGroup = r.group) : null;
            return (
              <div key={r.key}>
                {header && <p className="eyebrow px-3 pt-2 pb-1">{header}</p>}
                <button role="option" aria-selected={i === active} onMouseEnter={() => setActive(i)} onClick={() => go(r.href)}
                        className={clsx("w-full text-left flex items-center gap-3 rounded-xl px-3 py-2", i === active ? "bg-sunken" : "")}>
                  <r.icon className="w-4 h-4 text-ink-3 shrink-0" aria-hidden />
                  <span className="min-w-0">
                    <span className="block text-sm font-semibold truncate">{r.title}</span>
                    <span className="block text-[11px] text-ink-3 truncate">{r.sub}</span>
                  </span>
                </button>
              </div>
            );
          })}
          <Link to={`/search?q=${encodeURIComponent(q.trim())}`} onClick={() => setOpen(false)}
                className="block text-center text-xs font-semibold text-glacier-text py-2 mt-1 border-t border-line">
            See all results
          </Link>
        </div>
      )}
    </div>
  );
}
