import { useState } from "react";
import { ArrowRight, Loader2, Send } from "lucide-react";
import { api } from "../../api.js";
import { EXAMPLES, SEGMENT_LABEL } from "../../lib/meta.js";
import { ErrorNote, RouteBadge, Tile, useToast } from "../ui.jsx";

export default function SubmitTile({ customers, onSubmitted, onOpen }) {
  const toast = useToast();
  const [customerId, setCustomerId] = useState("c1");
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);

  const useExample = (ex) => {
    setCustomerId(ex.customer_id);
    setSubject("");
    setBody(ex.body);
    setResult(null);
    setError("");
  };

  const submit = async (e) => {
    e.preventDefault();
    if (!body.trim()) return;
    setBusy(true);
    setError("");
    try {
      const t = await api.submitTicket({ customer_id: customerId || null, subject: subject.trim(), body: body.trim() });
      setResult(t);
      setBody("");
      setSubject("");
      toast(`Ticket #${t.id} scored ${t.priority} → ${t.route === "auto_kb" ? "answered automatically" : t.route}`, "success");
      onSubmitted?.(t);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const selected = customers.find((c) => c.id === customerId);

  return (
    <Tile eyebrow="Customer view" title="Submit a ticket" icon={Send} className="lg:col-span-4">
      <form onSubmit={submit} className="flex flex-col gap-3">
        <label className="block">
          <span className="eyebrow">Customer</span>
          <select className="field mt-1" value={customerId} onChange={(e) => setCustomerId(e.target.value)}>
            {customers.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name} · {SEGMENT_LABEL[c.segment] ?? c.segment}
              </option>
            ))}
            <option value="">Unknown customer</option>
          </select>
          {selected && (
            <span className="mt-1 block text-[11px] text-ink-3">
              SLA {selected.sla_minutes}m · LTV ${Math.round(selected.ltv).toLocaleString()} · churn risk {Math.round(selected.churn_risk * 100)}%
              {selected.renewal_days != null && ` · renews in ${selected.renewal_days}d`}
            </span>
          )}
        </label>
        <label className="block">
          <span className="eyebrow">Subject</span>
          <input className="field mt-1" value={subject} maxLength={200} onChange={(e) => setSubject(e.target.value)} placeholder="Optional" />
        </label>
        <label className="block">
          <span className="eyebrow">Message</span>
          <textarea
            className="field mt-1 min-h-[104px] resize-y"
            value={body}
            maxLength={5000}
            onChange={(e) => setBody(e.target.value)}
            onKeyDown={(e) => (e.ctrlKey || e.metaKey) && e.key === "Enter" && submit(e)}
            placeholder="Describe the issue… (Ctrl+Enter to send)"
            required
          />
        </label>

        <div>
          <span className="eyebrow">Try a playbook example</span>
          <div className="mt-1.5 flex flex-wrap gap-1.5">
            {EXAMPLES.map((ex) => (
              <button
                type="button"
                key={ex.label}
                onClick={() => useExample(ex)}
                className="rounded-full border border-line px-2.5 py-1 text-xs font-medium text-ink-2 hover:border-glacier hover:text-glacier-text transition"
              >
                {ex.label}
              </button>
            ))}
          </div>
        </div>

        <button type="submit" className="btn-primary w-full mt-1" disabled={busy || !body.trim()}>
          {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
          Score & route
        </button>
        {error && <ErrorNote>{error}</ErrorNote>}
      </form>

      {result && (
        <button
          onClick={() => onOpen?.(result.id)}
          className="mt-4 text-left rounded-2xl bg-sunken border border-line p-4 hover:border-glacier transition group"
        >
          <div className="flex items-center justify-between">
            <span className="eyebrow">Ticket #{result.id}</span>
            <RouteBadge route={result.route} />
          </div>
          <div className="mt-2 flex items-end gap-3">
            <span className="text-4xl font-extrabold num">{result.priority}</span>
            <span className="pb-1 text-xs text-ink-3">/ 100 priority · {result.analysis.mode === "hf" ? "AI models" : "rules"}</span>
          </div>
          <p className="mt-1 text-xs text-ink-2">{result.route_reason}</p>
          <p className="mt-2 text-xs font-semibold text-glacier-text flex items-center gap-1">
            Open details <ArrowRight className="w-3 h-3 group-hover:translate-x-0.5 transition" />
          </p>
        </button>
      )}
    </Tile>
  );
}
