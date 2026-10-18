import { createContext, useCallback, useContext, useEffect, useState } from "react";
import clsx from "clsx";
import { AlertTriangle, CheckCircle2, Info, X } from "lucide-react";
import { routeMeta } from "../lib/meta.js";

export function Tile({ eyebrow, title, icon: Icon, action, className, bodyClass, children, dark = false, id }) {
  return (
    <section id={id} className={clsx(dark ? "tile-dark" : "tile", "flex flex-col min-w-0", className)} aria-label={title || eyebrow}>
      {(eyebrow || title || action) && (
        <header className="flex items-start justify-between gap-3 mb-4">
          <div className="min-w-0">
            {eyebrow && (
              <p className={clsx("eyebrow flex items-center gap-1.5", dark && "!text-slate-400")}>
                {Icon && <Icon className="w-3.5 h-3.5 shrink-0" aria-hidden />}
                {eyebrow}
              </p>
            )}
            {title && (
              <h2 className={clsx("mt-1 text-base font-bold tracking-tight", dark ? "text-white" : "text-ink")}>{title}</h2>
            )}
          </div>
          {action && <div className="shrink-0">{action}</div>}
        </header>
      )}
      <div className={clsx("flex-1 flex flex-col min-w-0", bodyClass)}>{children}</div>
    </section>
  );
}

export function Skeleton({ className }) {
  return (
    <div className={clsx("relative overflow-hidden rounded-xl bg-sunken", className)} aria-hidden>
      <div className="absolute inset-0 -translate-x-full animate-shimmer bg-gradient-to-r from-transparent via-white/40 dark:via-white/5 to-transparent" />
    </div>
  );
}

export function SkeletonLines({ rows = 3 }) {
  return (
    <div className="space-y-3" role="status" aria-label="Loading">
      {Array.from({ length: rows }, (_, i) => (
        <Skeleton key={i} className={clsx("h-4", i % 2 ? "w-2/3" : "w-full")} />
      ))}
    </div>
  );
}

export function RouteBadge({ route, className }) {
  const m = routeMeta(route);
  return (
    <span className={clsx("chip", m.badge, className)}>
      <span className={clsx("w-1.5 h-1.5 rounded-full", m.dot)} aria-hidden />
      {m.label}
    </span>
  );
}

/** Horizontal magnitude bar. Label and value are text in ink; the bar carries no text. */
export function MeterRow({ label, value, max = 1, display, sub, color = "rgb(var(--glacier))", title, compact = false }) {
  const w = Math.max(0, Math.min(1, max ? value / max : 0)) * 100;
  return (
    <div className="group" title={title}>
      <div className={clsx("flex items-baseline justify-between gap-2", compact ? "text-[11px] mb-0.5" : "text-xs mb-1")}>
        <span className="font-medium text-ink-2 truncate">{label}</span>
        <span className="text-ink font-semibold num whitespace-nowrap">
          {display}
          {sub && <span className="ml-1.5 font-normal text-ink-3">{sub}</span>}
        </span>
      </div>
      <div className={clsx("rounded-full bg-sunken overflow-hidden", compact ? "h-1.5" : "h-2")}>
        <div
          className="h-full rounded-full transition-[width] duration-500 group-hover:brightness-110"
          style={{ width: `${w}%`, background: color }}
        />
      </div>
    </div>
  );
}

export function Segmented({ value, onChange, options, label }) {
  return (
    <div className="inline-flex rounded-xl bg-sunken p-1 border border-line" role="tablist" aria-label={label}>
      {options.map((o) => (
        <button
          key={o.value}
          role="tab"
          aria-selected={value === o.value}
          onClick={() => onChange(o.value)}
          className={clsx(
            "rounded-lg font-semibold transition whitespace-nowrap px-2.5 py-1 text-xs",
            value === o.value ? "bg-card text-ink shadow-sm" : "text-ink-3 hover:text-ink",
          )}
        >
          {o.icon && <o.icon className="inline w-3.5 h-3.5 mr-1 -mt-0.5" aria-hidden />}
          {o.label}
          {o.count != null && <span className="ml-1 text-ink-3 font-medium num">{o.count}</span>}
        </button>
      ))}
    </div>
  );
}

export function Empty({ icon: Icon, children }) {
  return (
    <div className="flex flex-col items-center justify-center text-center gap-2 py-10 text-sm text-ink-3">
      {Icon && <Icon className="w-6 h-6 opacity-50" aria-hidden />}
      {children}
    </div>
  );
}

export function ErrorNote({ children }) {
  return (
    <p role="alert" className="flex items-start gap-1.5 text-xs text-senior-text">
      <AlertTriangle className="w-3.5 h-3.5 mt-px shrink-0" aria-hidden />
      {children}
    </p>
  );
}

// ------------------------------------------------------------------ toasts
const ToastCtx = createContext(() => {});
export const useToast = () => useContext(ToastCtx);

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);
  const push = useCallback((message, kind = "info") => {
    const id = Math.random().toString(36).slice(2);
    setToasts((t) => [...t.slice(-3), { id, message, kind }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), kind === "error" ? 6000 : 3500);
  }, []);
  const Icon = { success: CheckCircle2, error: AlertTriangle, info: Info };
  return (
    <ToastCtx.Provider value={push}>
      {children}
      <div className="fixed top-4 right-4 z-50 flex flex-col gap-2 w-[min(92vw,360px)]" aria-live="polite">
        {toasts.map((t) => {
          const I = Icon[t.kind] ?? Info;
          return (
            <div
              key={t.id}
              className={clsx(
                "animate-toast-in flex items-start gap-2 rounded-2xl border px-3.5 py-3 text-sm shadow-lg bg-card",
                t.kind === "error" ? "border-senior/40" : t.kind === "success" ? "border-tier1/40" : "border-line",
              )}
            >
              <I className={clsx("w-4 h-4 mt-0.5 shrink-0", t.kind === "error" ? "text-senior-text" : t.kind === "success" ? "text-tier1-text" : "text-glacier-text")} aria-hidden />
              <span className="flex-1 text-ink">{t.message}</span>
              <button onClick={() => setToasts((x) => x.filter((y) => y.id !== t.id))} aria-label="Dismiss" className="text-ink-3 hover:text-ink">
                <X className="w-4 h-4" />
              </button>
            </div>
          );
        })}
      </div>
    </ToastCtx.Provider>
  );
}

// ------------------------------------------------------------------ theme
export function useTheme() {
  const [theme, setTheme] = useState(() => {
    try {
      const saved = localStorage.getItem("theme");
      if (saved === "light" || saved === "dark") return saved;
    } catch {
      /* storage unavailable */
    }
    return window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  });
  useEffect(() => {
    document.documentElement.classList.toggle("dark", theme === "dark");
    try {
      localStorage.setItem("theme", theme);
    } catch {
      /* storage unavailable */
    }
  }, [theme]);
  return [theme, () => setTheme((t) => (t === "dark" ? "light" : "dark"))];
}

/** One consistent page header: back link, title with badges right beside it, subtitle, actions on the right. */
/** A titled, collapsible group of tiles on a page (nothing is hidden for good: click to open). */
export function Section({ title, hint, defaultOpen = true, children }) {
  return (
    <details open={defaultOpen} className="lg:col-span-12 group">
      <summary className="flex items-center gap-2 cursor-pointer list-none select-none py-1 [&::-webkit-details-marker]:hidden">
        <span className="text-ink-3 transition group-open:rotate-90" aria-hidden>▸</span>
        <span className="text-sm font-bold">{title}</span>
        {hint && <span className="text-xs text-ink-3">{hint}</span>}
      </summary>
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 mt-3">{children}</div>
    </details>
  );
}

export function PageHeader({ title, subtitle, badges, actions, back }) {
  return (
    <div className="lg:col-span-12 flex flex-wrap items-end justify-between gap-3 pt-1">
      <div className="min-w-0">
        {back}
        <div className="flex flex-wrap items-center gap-2.5 mt-1">
          <h1 className="text-2xl font-extrabold tracking-tight">{title}</h1>
          {badges}
        </div>
        {subtitle && <p className="text-sm text-ink-3 mt-0.5">{subtitle}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}
