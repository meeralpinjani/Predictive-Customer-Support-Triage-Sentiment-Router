import { useEffect, useRef, useState } from "react";
import clsx from "clsx";
import { Loader2, MessageSquare, Phone, PhoneCall, Send } from "lucide-react";
import { api } from "../api.js";
import { useEventListener, useLiveData } from "../lib/events.jsx";
import { timeAgo } from "../lib/meta.js";
import { ErrorNote, SkeletonLines, Tile, useToast } from "./ui.jsx";

/** Live conversation on a ticket: messages, system notes and typing indicators. */
export function Conversation({ ticketId, live = false, canReply = true, placeholder, className, onSent }) {
  const toast = useToast();
  const { data: messages, reload } = useLiveData(() => api.messages(ticketId), {
    match: (ev) => ev.ticket_id === ticketId, deps: [ticketId], intervalMs: 15000,
  });
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [typing, setTyping] = useState(null);
  const typingTimer = useRef();
  const lastPing = useRef(0);
  const bottom = useRef();

  useEventListener((ev) => {
    if (ev.ticket_id !== ticketId || ev.type !== "typing") return;
    setTyping(ev.name);
    clearTimeout(typingTimer.current);
    typingTimer.current = setTimeout(() => setTyping(null), 3500);
  });

  useEffect(() => {
    bottom.current?.scrollIntoView({ block: "nearest" });
  }, [messages?.length, typing]);

  const onChange = (e) => {
    setText(e.target.value);
    if (Date.now() - lastPing.current > 2000) {
      lastPing.current = Date.now();
      api.typing(ticketId).catch(() => {});
    }
  };

  const send = async (e) => {
    e?.preventDefault();
    const body = text.trim();
    if (!body) return;
    setBusy(true);
    try {
      await api.sendMessage(ticketId, body);
      setText("");
      setTyping(null);
      await reload();
      onSent?.();
    } catch (err) {
      toast(err.message, "error");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Tile eyebrow={live ? "Live chat · Expert Escalation" : "Conversation"} icon={MessageSquare} className={className}
          action={live && <span className="chip bg-senior-soft text-senior-text"><span className="w-1.5 h-1.5 rounded-full bg-senior animate-pulse" aria-hidden />live</span>}>
      <div className="flex-1 min-h-[220px] max-h-[460px] overflow-y-auto scroll-thin space-y-3 pr-1" aria-live="polite">
        {!messages ? <SkeletonLines rows={4} /> : messages.map((m) => m.kind === "system" ? (
          <p key={m.id} className="text-center text-[11px] text-ink-3 px-6">{m.body} · {timeAgo(m.created_at)}</p>
        ) : (
          <div key={m.id} className={clsx("flex", m.mine ? "justify-end" : "justify-start")}>
            <div className={clsx("max-w-[85%] rounded-2xl px-3.5 py-2.5",
              m.mine ? "bg-fjord text-white dark:bg-glacier dark:text-fjord rounded-br-md" : "bg-sunken rounded-bl-md")}>
              <p className={clsx("text-[11px] font-semibold mb-0.5", m.mine ? "opacity-70" : "text-ink-3")}>
                {m.mine ? "You" : m.author_name}{m.author_role !== "customer" && !m.mine ? " · Support" : ""}
                {m.frustration != null && <span className="font-normal"> · frustration {Math.round(m.frustration * 100)}%</span>}
              </p>
              <p className="text-sm whitespace-pre-wrap break-words">{m.body}</p>
              <p className={clsx("text-[10px] mt-1", m.mine ? "opacity-60" : "text-ink-3")}>{timeAgo(m.created_at)}</p>
            </div>
          </div>
        ))}
        {typing && <p className="text-xs text-ink-3 italic">{typing} is typing…</p>}
        <div ref={bottom} />
      </div>
      {canReply ? (
        <form onSubmit={send} className="mt-3 flex gap-2 items-end">
          <textarea className="field min-h-[44px] max-h-32 resize-y" rows={1} value={text} onChange={onChange}
                    onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && send(e)}
                    placeholder={placeholder || "Write a message… (Enter to send)"} aria-label="Message" maxLength={4000} />
          <button className="btn-primary !px-3 h-[44px]" disabled={busy || !text.trim()} aria-label="Send">
            {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
          </button>
        </form>
      ) : <p className="mt-3 text-xs text-ink-3">This ticket is closed.</p>}
    </Tile>
  );
}

const CB_STATUS = { requested: "Requested", scheduled: "Scheduled", done: "Completed" };

/** Level 3 callbacks: customers request a call; the expert schedules and completes it. */
export function CallbackPanel({ ticketId, mode, open = true, className }) {
  const toast = useToast();
  const { data: callbacks, reload } = useLiveData(() => api.callbacks(ticketId), {
    match: (ev) => ev.ticket_id === ticketId && ev.type.startsWith("callback"), deps: [ticketId],
  });
  const [form, setForm] = useState({ phone: "", preferred_time: "", note: "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const active = callbacks?.find((c) => c.status !== "done");

  const request = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api.requestCallback(ticketId, form);
      toast("Call requested — an expert will ring you back", "success");
      await reload();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };
  const update = async (cb, status) => {
    try {
      await api.updateCallback(ticketId, cb.id, status);
      await reload();
    } catch (err) {
      toast(err.message, "error");
    }
  };

  return (
    <Tile eyebrow="Talk to an expert" icon={PhoneCall} className={className}>
      {callbacks?.length > 0 && (
        <ul className="space-y-2 mb-3">
          {callbacks.map((c) => (
            <li key={c.id} className="rounded-2xl bg-sunken p-3 text-sm">
              <div className="flex items-center justify-between gap-2">
                <span className="font-semibold flex items-center gap-1.5"><Phone className="w-3.5 h-3.5" aria-hidden />
                  {mode === "agent" ? c.phone : "Callback"}</span>
                <span className={clsx("chip", c.status === "done" ? "bg-tier1-soft text-tier1-text" : "bg-tier2-soft text-tier2-text")}>{CB_STATUS[c.status]}</span>
              </div>
              {c.preferred_time && <p className="text-xs text-ink-3 mt-1">Preferred: {c.preferred_time}</p>}
              {c.note && <p className="text-xs text-ink-2 mt-1">{c.note}</p>}
              {mode === "agent" && c.status !== "done" && (
                <div className="mt-2 flex gap-2">
                  {c.status === "requested" && <button className="btn-ghost !py-1 !text-xs bg-card" onClick={() => update(c, "scheduled")}>Mark scheduled</button>}
                  <button className="btn-ghost !py-1 !text-xs bg-card" onClick={() => update(c, "done")}>Call completed</button>
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
      {mode === "customer" && open && !active && (
        <form onSubmit={request} className="space-y-2">
          <p className="text-xs text-ink-3">Prefer to talk? An expert can call you back.</p>
          <input className="field" type="tel" placeholder="Phone number" value={form.phone} required
                 onChange={(e) => setForm({ ...form, phone: e.target.value })} aria-label="Phone number" />
          <input className="field" placeholder="Best time (e.g. today 15:00)" value={form.preferred_time}
                 onChange={(e) => setForm({ ...form, preferred_time: e.target.value })} aria-label="Preferred time" />
          <button className="btn-primary w-full" disabled={busy}>{busy && <Loader2 className="w-4 h-4 animate-spin" />}<PhoneCall className="w-4 h-4" />Request a call</button>
          {error && <ErrorNote>{error}</ErrorNote>}
        </form>
      )}
      {mode === "agent" && callbacks?.length === 0 && <p className="text-sm text-ink-3">No call requested.</p>}
    </Tile>
  );
}
