import clsx from "clsx";
import { routeMeta } from "../lib/meta.js";

export function Tile({ eyebrow, title, icon: Icon, action, className, children, dark = false }) {
  return (
    <section className={clsx(dark ? "tile-dark" : "tile", "flex flex-col min-w-0", className)}>
      {(eyebrow || title || action) && (
        <header className="flex items-start justify-between gap-3 mb-4">
          <div className="min-w-0">
            {eyebrow && (
              <p className={clsx("eyebrow flex items-center gap-1.5", dark && "!text-slate-400")}>
                {Icon && <Icon className="w-3.5 h-3.5" aria-hidden />}
                {eyebrow}
              </p>
            )}
            {title && (
              <h2 className={clsx("mt-1 text-base font-bold tracking-tight", dark ? "text-white" : "text-nordic-dark")}>
                {title}
              </h2>
            )}
          </div>
          {action && <div className="shrink-0">{action}</div>}
        </header>
      )}
      {children}
    </section>
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

// Horizontal magnitude bar: label + value in ink, the bar carries no text.
export function MeterRow({ label, value, max = 1, display, sub, color = "#0284C7", title }) {
  const w = Math.max(0, Math.min(1, max ? value / max : 0)) * 100;
  return (
    <div className="group" title={title}>
      <div className="flex items-baseline justify-between text-xs mb-1">
        <span className="font-medium text-nordic-slate">{label}</span>
        <span className="text-nordic-dark font-semibold tabular-nums">
          {display}
          {sub && <span className="ml-1.5 font-normal text-nordic-muted">{sub}</span>}
        </span>
      </div>
      <div className="h-2 rounded-full bg-slate-100 overflow-hidden">
        <div
          className="h-full rounded-full transition-[width] duration-500 group-hover:brightness-110"
          style={{ width: `${w}%`, background: color }}
        />
      </div>
    </div>
  );
}

export function Segmented({ value, onChange, options, size = "sm" }) {
  return (
    <div className="inline-flex rounded-xl bg-nordic-frost p-1 border border-nordic-border/70" role="tablist">
      {options.map((o) => (
        <button
          key={o.value}
          role="tab"
          aria-selected={value === o.value}
          onClick={() => onChange(o.value)}
          className={clsx(
            "rounded-lg font-semibold transition whitespace-nowrap",
            size === "sm" ? "px-2.5 py-1 text-xs" : "px-3 py-1.5 text-sm",
            value === o.value ? "bg-white text-nordic-dark shadow-sm" : "text-nordic-muted hover:text-nordic-dark",
          )}
        >
          {o.label}
          {o.count != null && <span className="ml-1 text-nordic-muted font-medium tabular-nums">{o.count}</span>}
        </button>
      ))}
    </div>
  );
}

export function Empty({ icon: Icon, children }) {
  return (
    <div className="flex flex-col items-center justify-center text-center gap-2 py-10 text-sm text-nordic-muted">
      {Icon && <Icon className="w-6 h-6 text-slate-300" aria-hidden />}
      {children}
    </div>
  );
}
