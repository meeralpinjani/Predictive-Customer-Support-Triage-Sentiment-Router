import { useEffect, useRef, useState } from "react";
import { FlaskConical, RotateCcw } from "lucide-react";
import { api } from "../../api.js";
import { COMPONENT_LABEL, COMPONENT_ORDER } from "../../lib/meta.js";
import { ErrorNote, Tile } from "../ui.jsx";

function Slider({ label, value, min, max, step, onChange, display }) {
  return (
    <label className="block">
      <span className="flex justify-between text-xs mb-1">
        <span className="font-medium text-ink-2">{label}</span>
        <span className="font-semibold num">{display ?? value}</span>
      </span>
      <input type="range" min={min} max={max} step={step} value={value} onChange={(e) => onChange(Number(e.target.value))}
             className="w-full accent-[rgb(var(--glacier))]" />
    </label>
  );
}

/** Preview how the open queue would re-rank under other weights/thresholds. Saves nothing. */
export default function WhatIfTile({ config, onPreview, ticketsVersion }) {
  const defaults = config && {
    weights: config.weights,
    level3_score: config.level3_score,
    frustration_senior: Number(config.frustration_senior.toFixed(2)),
  };
  const [state, setState] = useState(null);
  const [summary, setSummary] = useState(null);
  const [error, setError] = useState("");
  const timer = useRef();

  useEffect(() => {
    if (defaults && !state) setState(defaults);
  }, [config]); // eslint-disable-line react-hooks/exhaustive-deps

  const dirty = state && defaults && JSON.stringify(state) !== JSON.stringify(defaults);

  useEffect(() => {
    if (!state) return;
    if (!dirty) {
      onPreview(null);
      setSummary(null);
      return;
    }
    clearTimeout(timer.current);
    timer.current = setTimeout(async () => {
      try {
        const res = await api.whatIf(state);
        onPreview(new Map(res.tickets.map((t) => [t.id, t])));
        setSummary(res);
        setError("");
      } catch (err) {
        setError(err.message);
      }
    }, 250);
    return () => clearTimeout(timer.current);
  }, [state, ticketsVersion]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!state) {
    return <Tile eyebrow="Try other settings" title="Tune the router" icon={FlaskConical} className="lg:col-span-4"><p className="text-sm text-ink-3">Loading…</p></Tile>;
  }

  const total = COMPONENT_ORDER.reduce((s, k) => s + state.weights[k], 0) || 1;
  const setWeight = (k, v) => setState((s) => ({ ...s, weights: { ...s.weights, [k]: v } }));

  return (
    <Tile
      eyebrow="Try other settings · preview only"
      title="Tune the router live"
      icon={FlaskConical}
      className="lg:col-span-4"
      action={dirty && (
        <button className="btn-ghost !py-1 !px-2.5 !text-xs" onClick={() => setState(defaults)}>
          <RotateCcw className="w-3.5 h-3.5" /> Reset
        </button>
      )}
    >
      <p className="text-xs text-ink-3 mb-3">Move a slider and the queue re-ranks instantly. Nothing is saved.</p>
      <div className="space-y-3">
        {COMPONENT_ORDER.map((k) => (
          <Slider key={k} label={`${COMPONENT_LABEL[k]} weight`} value={state.weights[k]} min={0} max={1} step={0.05}
                  display={`${Math.round((state.weights[k] / total) * 100)}%`} onChange={(v) => setWeight(k, v)} />
        ))}
        <div className="border-t border-line pt-3 space-y-3">
          <Slider label="Level 3 from score" value={state.level3_score} min={30} max={95} step={1}
                  onChange={(v) => setState((s) => ({ ...s, level3_score: v }))} />
          <Slider label="Frustration → Level 3" value={state.frustration_senior} min={0.2} max={0.95} step={0.01}
                  onChange={(v) => setState((s) => ({ ...s, frustration_senior: v }))} />
        </div>
      </div>
      <div className="mt-4 rounded-2xl bg-sunken p-3 text-xs" aria-live="polite">
        {summary ? (
          <p><span className="font-bold num">{summary.moved}</span> tickets change position ·{" "}
            <span className="font-bold num">{summary.route_changes}</span> would change route</p>
        ) : (
          <p className="text-ink-3">Showing the live configuration.</p>
        )}
      </div>
      {error && <div className="mt-2"><ErrorNote>{error}</ErrorNote></div>}
    </Tile>
  );
}
