import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ExternalLink, Search } from "lucide-react";
import { api } from "../../api.js";
import { useLiveData } from "../../lib/events.jsx";
import { DeflectionTile, LiveQueueHero, WaitTile } from "../../components/live/Overview.jsx";
import SubmitTile from "../../components/live/SubmitTile.jsx";
import QueueTile from "../../components/live/QueueTile.jsx";
import WhatIfTile from "../../components/live/WhatIfTile.jsx";
import TicketExplain from "../../components/TicketExplain.jsx";
import { AblationTile, ModelTile, ResultsTile, ScorecardTile } from "../../components/insights/Evidence.jsx";
import {
  FormulaTile, KbTesterTile, MethodTile, RouteMixTile, SegmentWaitTile, TrustTile,
} from "../../components/insights/Operations.jsx";
import { Empty, PageHeader, Section } from "../../components/ui.jsx";
import { RetrainTile } from "./AdminExtras.jsx";

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
      <PageHeader title="Overview" subtitle="Every queue, live. Click a ticket to see why it got its score and level." />
      <LiveQueueHero tickets={list} loading={!tickets} />
      <DeflectionTile stats={stats} />
      <WaitTile stats={stats} />

      <QueueTile tickets={list} loading={!tickets} selectedId={selectedId} onSelect={setSelectedId} preview={preview}
                 eyebrow="All levels" title="Live queue" />
      <TicketExplain ticket={selected} onChanged={reload} admin
                     action={selected && (
                       <button className="btn-ghost !p-2 !rounded-full" onClick={() => navigate(`/tickets/${selected.id}`)} aria-label="Open full ticket">
                         <ExternalLink className="w-4 h-4" />
                       </button>
                     )} />

      <Section title="Demo & testing tools" hint="send a test ticket as any customer, or preview other settings" defaultOpen={false}>
        <SubmitTile customers={customers ?? []} categories={cats?.categories ?? []}
                    onSubmitted={async (t) => { setSelectedId(t.id); await reload(); }} onOpen={setSelectedId} />
        <WhatIfTile config={config} onPreview={setPreview} ticketsVersion={list.length} />
      </Section>
    </div>
  );
}

export function AdminInsights() {
  const [report, error] = useStatic(api.evaluation);
  const [config] = useStatic(api.config);
  const { data: stats } = useLiveData(() => api.stats(), { intervalMs: 15000 });
  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 pt-2">
      <PageHeader title="Insights & proof" subtitle="How well the AI performs on unseen tickets, and what the router changes on a busy day." />
      <Section title="Results">
        <ResultsTile report={report} error={error} />
        <ScorecardTile report={report} error={error} />
        <div className="lg:col-span-12 grid gap-4 lg:grid-cols-2">
          <RouteMixTile stats={stats} />
          <SegmentWaitTile stats={stats} />
        </div>
      </Section>
      <Section title="Technical details" hint="what each part adds, the trained model, the formula and how it was measured" defaultOpen={false}>
        <AblationTile report={report} />
        <ModelTile report={report} />
        <FormulaTile config={config} />
        <div className="lg:col-span-8"><MethodTile report={report} /></div>
      </Section>
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
      <PageHeader title="Tuning" subtitle="Try other weights safely, check system status, and retrain routing from your agents' decisions." />
      <Section title="Try other settings" hint="preview only, nothing is saved">
        <WhatIfTile config={config} onPreview={setPreview} ticketsVersion={tickets?.length ?? 0} />
        <QueueTile tickets={tickets ?? []} loading={!tickets} onSelect={() => {}} preview={preview}
                   eyebrow="Preview" title="Queue under these settings" />
      </Section>
      <Section title="Status & learning">
        <TrustTile stats={stats} health={health} onRescore={async () => { await api.rescore(); await reload(); }} />
        <RetrainTile className="lg:col-span-8" />
      </Section>
      <Section title="Technical details" hint="the formula and the help-article match tester" defaultOpen={false}>
        <FormulaTile config={config} />
        <KbTesterTile />
      </Section>
    </div>
  );
}

export function NotFound() {
  return (
    <div className="pt-10"><Empty icon={Search}>Page not found. <Link to="/" className="text-glacier-text font-semibold">Go home</Link></Empty></div>
  );
}
