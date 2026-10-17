import { useCallback, useEffect, useState } from "react";
import { Snowflake, WifiOff } from "lucide-react";
import { api } from "./api.js";
import { DeflectionTile, LiveQueueHero, WaitTile } from "./components/Overview.jsx";
import SubmitTile from "./components/SubmitTile.jsx";
import QueueTile from "./components/QueueTile.jsx";
import DetailTile from "./components/DetailTile.jsx";
import { FormulaTile, KbTesterTile, RouteMixTile, SegmentWaitTile, SimulationTile, TrustTile } from "./components/Insights.jsx";

const POLL_MS = 3000;

export default function App() {
  const [tickets, setTickets] = useState([]);
  const [stats, setStats] = useState(null);
  const [customers, setCustomers] = useState([]);
  const [config, setConfig] = useState(null);
  const [health, setHealth] = useState(null);
  const [sim, setSim] = useState(null);
  const [simError, setSimError] = useState("");
  const [selectedId, setSelectedId] = useState(null);
  const [online, setOnline] = useState(true);
  const [updatedAt, setUpdatedAt] = useState(null);

  const refresh = useCallback(async () => {
    try {
      const [t, s, h] = await Promise.all([api.tickets(), api.stats(), api.health()]);
      setTickets(t);
      setStats(s);
      setHealth(h);
      setOnline(true);
      setUpdatedAt(new Date());
    } catch {
      setOnline(false);
      setHealth(null);
    }
  }, []);

  useEffect(() => {
    api.customers().then(setCustomers).catch(() => {});
    api.config().then(setConfig).catch(() => {});
    api.simulation().then(setSim).catch((e) => setSimError(e.message));
    refresh();
    const id = setInterval(refresh, POLL_MS);
    return () => clearInterval(id);
  }, [refresh]);

  const selected = tickets.find((t) => t.id === selectedId) ?? null;

  const onSubmitted = async (t) => {
    setSelectedId(t.id);
    await refresh();
  };

  return (
    <div className="min-h-screen">
      <div className="mx-auto max-w-[1440px] px-4 sm:px-6 lg:px-8 py-6 lg:py-8">
        <header className="flex flex-wrap items-center justify-between gap-4 mb-6">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-2xl bg-nordic-fjord grid place-items-center">
              <Snowflake className="w-5 h-5 text-sky-300" aria-hidden />
            </div>
            <div>
              <h1 className="text-lg sm:text-xl font-extrabold tracking-tight">Support Triage Router</h1>
              <p className="text-xs text-nordic-muted">Sentiment · urgency · customer value → one explainable priority</p>
            </div>
          </div>
          <div className="flex items-center gap-2 text-xs">
            {online ? (
              <span className="chip bg-nordic-pineLight text-teal-800">
                <span className="relative flex w-2 h-2">
                  <span className="absolute inline-flex h-full w-full rounded-full bg-nordic-pine opacity-60 animate-ping" />
                  <span className="relative inline-flex w-2 h-2 rounded-full bg-nordic-pine" />
                </span>
                Live{updatedAt && ` · ${updatedAt.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })}`}
              </span>
            ) : (
              <span className="chip bg-nordic-lingonberryLight text-nordic-lingonberry">
                <WifiOff className="w-3 h-3" aria-hidden /> API offline — start the backend on :8000
              </span>
            )}
            <span className="chip bg-white border border-nordic-border text-nordic-slate">AlgoAmigos</span>
          </div>
        </header>

        <main className="grid grid-cols-1 lg:grid-cols-12 gap-4">
          <LiveQueueHero tickets={tickets} loading={!updatedAt} />
          <DeflectionTile tickets={tickets} />
          <WaitTile stats={stats} />

          <SubmitTile customers={customers} onSubmitted={onSubmitted} onOpen={setSelectedId} />
          <QueueTile tickets={tickets} selectedId={selectedId} onSelect={setSelectedId} />

          <DetailTile ticket={selected} onChanged={refresh} />
          <div className="lg:col-span-4 grid gap-4 content-start">
            <RouteMixTile stats={stats} />
            <SegmentWaitTile stats={stats} />
          </div>

          <SimulationTile sim={sim} error={simError} />
          <KbTesterTile config={config} />

          <FormulaTile config={config} />
          <TrustTile
            stats={stats}
            health={health}
            onRescore={async () => {
              await api.rescore();
              await refresh();
            }}
          />
        </main>

        <footer className="mt-8 text-center text-[11px] text-nordic-muted">
          Predictive Customer Support Triage &amp; Sentiment Router · HelloWorld KIT ’26
        </footer>
      </div>
    </div>
  );
}
