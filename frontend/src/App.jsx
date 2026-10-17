import { useCallback, useEffect, useState } from "react";
import clsx from "clsx";
import { Activity, BarChart3, Cpu, Moon, Snowflake, Sun, WifiOff } from "lucide-react";
import { api } from "./api.js";
import { ToastProvider, useTheme } from "./components/ui.jsx";
import { DeflectionTile, LiveQueueHero, WaitTile } from "./components/live/Overview.jsx";
import SubmitTile from "./components/live/SubmitTile.jsx";
import QueueTile from "./components/live/QueueTile.jsx";
import DetailTile from "./components/live/DetailTile.jsx";
import WhatIfTile from "./components/live/WhatIfTile.jsx";
import { AblationTile, ModelTile, ResultsTile, ScorecardTile } from "./components/insights/Evidence.jsx";
import { FormulaTile, KbTesterTile, MethodTile, RouteMixTile, SegmentWaitTile, TrustTile } from "./components/insights/Operations.jsx";

const POLL_MS = 3000;
const VIEWS = [
  { value: "live", label: "Live triage", icon: Activity },
  { value: "insights", label: "Insights & proof", icon: BarChart3 },
];

function useHashView() {
  const read = () => (window.location.hash === "#insights" ? "insights" : "live");
  const [view, setView] = useState(read);
  useEffect(() => {
    const onHash = () => setView(read());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);
  return [view, (v) => (window.location.hash = v === "insights" ? "insights" : "")];
}

function Dashboard() {
  const [theme, toggleTheme] = useTheme();
  const [view, setView] = useHashView();
  const [tickets, setTickets] = useState([]);
  const [stats, setStats] = useState(null);
  const [customers, setCustomers] = useState([]);
  const [config, setConfig] = useState(null);
  const [health, setHealth] = useState(null);
  const [report, setReport] = useState(null);
  const [reportError, setReportError] = useState("");
  const [selectedId, setSelectedId] = useState(null);
  const [online, setOnline] = useState(true);
  const [loaded, setLoaded] = useState(false);
  const [version, setVersion] = useState(0);
  const [preview, setPreview] = useState(null);

  const refresh = useCallback(async () => {
    try {
      const [t, s, h] = await Promise.all([api.tickets(), api.stats(), api.health()]);
      setTickets(t);
      setStats(s);
      setHealth(h);
      setOnline(true);
      setLoaded(true);
      setVersion((v) => v + 1);
    } catch {
      setOnline(false);
    }
  }, []);

  useEffect(() => {
    api.customers().then(setCustomers).catch(() => {});
    api.config().then(setConfig).catch(() => {});
    api.evaluation().then(setReport).catch((e) => setReportError(e.message));
    refresh();
    const id = setInterval(refresh, POLL_MS);
    return () => clearInterval(id);
  }, [refresh]);

  // Config depends on fitted thresholds; refetch once the backend comes back online.
  useEffect(() => {
    if (online && !config) api.config().then(setConfig).catch(() => {});
    if (online && customers.length === 0) api.customers().then(setCustomers).catch(() => {});
  }, [online]); // eslint-disable-line react-hooks/exhaustive-deps

  const selected = tickets.find((t) => t.id === selectedId) ?? null;
  const onSubmitted = async (t) => {
    setSelectedId(t.id);
    await refresh();
  };

  const nlpLabel = !health ? null : health.nlp_mode === "hf" ? "AI models active" : health.models === "loading" ? "AI models loading…" : "Rules engine";

  return (
    <div className="min-h-screen">
      <div className="mx-auto max-w-[1480px] px-4 sm:px-6 lg:px-8 py-5 lg:py-7">
        <header className="flex flex-wrap items-center justify-between gap-4 mb-5">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-2xl bg-fjord grid place-items-center shrink-0">
              <Snowflake className="w-5 h-5 text-sky-300" aria-hidden />
            </div>
            <div>
              <h1 className="text-lg sm:text-xl font-extrabold tracking-tight">Support Triage Router</h1>
              <p className="text-xs text-ink-3">Sentiment · urgency · customer value → one explainable priority</p>
            </div>
          </div>

          <nav className="order-3 w-full sm:order-none sm:w-auto inline-flex rounded-2xl bg-card border border-line p-1" aria-label="Views">
            {VIEWS.map((v) => (
              <button key={v.value} onClick={() => setView(v.value)} aria-current={view === v.value ? "page" : undefined}
                      className={clsx("flex-1 sm:flex-none inline-flex items-center justify-center gap-1.5 rounded-xl px-3.5 py-2 text-sm font-semibold transition",
                                      view === v.value ? "bg-fjord text-white dark:bg-glacier dark:text-fjord" : "text-ink-3 hover:text-ink")}>
                <v.icon className="w-4 h-4" aria-hidden /> {v.label}
              </button>
            ))}
          </nav>

          <div className="flex items-center gap-2 text-xs flex-wrap">
            {online ? (
              <span className="chip bg-tier1-soft text-tier1-text">
                <span className="relative flex w-2 h-2">
                  <span className="absolute inline-flex h-full w-full rounded-full bg-tier1 opacity-60 animate-ping" />
                  <span className="relative inline-flex w-2 h-2 rounded-full bg-tier1" />
                </span>
                Live
              </span>
            ) : (
              <span className="chip bg-senior-soft text-senior-text"><WifiOff className="w-3 h-3" aria-hidden /> API offline — start the backend</span>
            )}
            {nlpLabel && <span className="chip bg-card border border-line text-ink-2"><Cpu className="w-3 h-3" aria-hidden /> {nlpLabel}</span>}
            <button onClick={toggleTheme} className="btn-ghost !p-2 !rounded-full" aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}>
              {theme === "dark" ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
            </button>
          </div>
        </header>

        {view === "live" ? (
          <main className="grid grid-cols-1 lg:grid-cols-12 gap-4">
            <LiveQueueHero tickets={tickets} loading={!loaded} />
            <DeflectionTile stats={stats} />
            <WaitTile stats={stats} />

            <SubmitTile customers={customers} onSubmitted={onSubmitted} onOpen={setSelectedId} />
            <QueueTile tickets={tickets} loading={!loaded} selectedId={selectedId} onSelect={setSelectedId} preview={preview} />

            <DetailTile ticket={selected} onChanged={refresh} />
            <WhatIfTile config={config} onPreview={setPreview} ticketsVersion={version} />
          </main>
        ) : (
          <main className="grid grid-cols-1 lg:grid-cols-12 gap-4">
            <ResultsTile report={report} error={reportError} />
            <ScorecardTile report={report} error={reportError} />

            <AblationTile report={report} />
            <ModelTile report={report} />

            <FormulaTile config={config} />
            <div className="lg:col-span-4 grid gap-4 content-start">
              <RouteMixTile stats={stats} />
              <SegmentWaitTile stats={stats} />
            </div>

            <KbTesterTile />
            <TrustTile stats={stats} health={health} onRescore={async () => { await api.rescore(); await refresh(); }} />
            <MethodTile report={report} />
          </main>
        )}

        <footer className="mt-8 text-center text-[11px] text-ink-3">
          Predictive Customer Support Triage &amp; Sentiment Router · AlgoAmigos · HelloWorld KIT ’26
        </footer>
      </div>
    </div>
  );
}

export default function App() {
  return (
    <ToastProvider>
      <Dashboard />
    </ToastProvider>
  );
}
