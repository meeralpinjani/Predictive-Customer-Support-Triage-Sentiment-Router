import { useEffect, useRef, useState } from "react";
import clsx from "clsx";
import { AlertCircle, Loader2, MessageSquare, Phone, PhoneCall, RefreshCw, Send, Sparkles, WifiOff } from "lucide-react";
import { api, newClientId } from "../api.js";
import { useEventListener, useEvents, useLiveData } from "../lib/events.jsx";
import { timeAgo } from "../lib/meta.js";
import { ErrorNote, SkeletonLines, Tile, useToast } from "./ui.jsx";
import { AttachButton, AttachmentList, PendingFiles } from "./Attachments.jsx";

// Unsent drafts survive a refresh or a lost connection; cleared only after the server confirms.
const draftKey = (id) => `draft:ticket:${id}`;
function readDraft(id) {
  try { return localStorage.getItem(draftKey(id)) || ""; } catch { return ""; }
}
function writeDraft(id, value) {
  try { value ? localStorage.setItem(draftKey(id), value) : localStorage.removeItem(draftKey(id)); } catch { /* storage off */ }
}
// The client id of an unconfirmed send, so re-sending the same text after a refresh reuses it
// (if the first attempt did reach the server, the retry returns that message instead of a duplicate).
const sendKey = (id) => `draft-send:ticket:${id}`;
function pendingSendId(id, body) {
  try {
    const v = JSON.parse(localStorage.getItem(sendKey(id)) || "null");
    return v && v.body === body ? v.clientId : null;
  } catch { return null; }
}
function rememberSend(id, body, clientId) {
  try { clientId ? localStorage.setItem(sendKey(id), JSON.stringify({ body, clientId })) : localStorage.removeItem(sendKey(id)); } catch { /* storage off */ }
}

/** Live conversation on a ticket: messages, attachments, system notes and typing indicators.
 *  Agents get a "Suggest reply" button that drafts a reply they can edit before sending.
 *  Every send carries a client id: a retry after a network error can't create a duplicate, and a
 *  message is only shown as saved once the server returned it. */
export function Conversation({ ticketId, live = false, canReply = true, placeholder, className, onSent, suggest = false, tall = false }) {
  const toast = useToast();
  const { status: liveStatus, reconnect } = useEvents();
  const { data: messages, error: loadError, reload } = useLiveData(() => api.messages(ticketId), {
    match: (ev) => ev.ticket_id === ticketId, deps: [ticketId], intervalMs: 15000,
  });
  const [text, setText] = useState(() => readDraft(ticketId));
  const [pending, setPending] = useState([]);      // { clientId, body, files, state: "sending" | "failed", error }
  const [resuming, setResuming] = useState(false);
  const [files, setFiles] = useState([]);
  const [busy, setBusy] = useState(false);
  const [drafting, setDrafting] = useState(false);
  const [typing, setTyping] = useState(null);
  const typingTimer = useRef();
  const lastPing = useRef(0);
  const scroller = useRef();

  useEventListener((ev) => {
    if (ev.ticket_id !== ticketId || ev.type !== "typing") return;
    setTyping(ev.name);
    clearTimeout(typingTimer.current);
    typingTimer.current = setTimeout(() => setTyping(null), 3500);
  });

  useEffect(() => {
    const el = scroller.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages?.length, typing]);

  useEffect(() => { setText(readDraft(ticketId)); setPending([]); }, [ticketId]);

  // Opened via "View full conversation" from a list: bring the conversation into view once loaded.
  const jumped = useRef(false);
  useEffect(() => {
    if (!messages || jumped.current || window.location.hash !== "#conversation") return;
    jumped.current = true;
    scroller.current?.scrollIntoView({ block: "center" });
  }, [messages]);

  const onChange = (e) => {
    setText(e.target.value);
    writeDraft(ticketId, e.target.value);
    if (Date.now() - lastPing.current > 2000) {
      lastPing.current = Date.now();
      api.typing(ticketId).catch(() => {});
    }
  };

  const deliver = async (item) => {
    setPending((ps) => ps.map((p) => (p.clientId === item.clientId ? { ...p, state: "sending", error: "" } : p)));
    try {
      if (item.files.length) await api.sendMessageWithFiles(ticketId, item.body, item.files, item.clientId);
      else await api.sendMessage(ticketId, item.body, item.clientId);
      setPending((ps) => ps.filter((p) => p.clientId !== item.clientId));   // confirmed by the server
      if (readDraft(ticketId).trim() === item.body) writeDraft(ticketId, "");
      rememberSend(ticketId, null);
      await reload();
      onSent?.();
      return true;
    } catch (err) {
      setPending((ps) => ps.map((p) => (p.clientId === item.clientId ? { ...p, state: "failed", error: err.message } : p)));
      return false;
    }
  };

  const send = async (e) => {
    e?.preventDefault();
    const body = text.trim();
    if (!body && !files.length) return;
    const clientId = (!files.length && pendingSendId(ticketId, body)) || newClientId();
    if (!files.length) rememberSend(ticketId, body, clientId);
    const item = { clientId, body, files, state: "sending", error: "" };
    setPending((ps) => [...ps, item]);
    setText("");
    setFiles([]);
    setTyping(null);
    setBusy(true);
    await deliver(item);           // the draft is cleared inside deliver() only after the server confirms
    setBusy(false);
  };

  const resume = async () => {
    setResuming(true);
    try {
      await api.resume(ticketId);
      await reload();
      reconnect();
      for (const p of pending.filter((x) => x.state === "failed")) await deliver(p);
      toast("Conversation is up to date", "success");
    } catch (err) {
      toast(`Couldn't resume yet (${err.message}). Your messages are kept here; try again in a moment.`, "error");
    } finally {
      setResuming(false);
    }
  };
  const disconnected = liveStatus === "reconnecting" || liveStatus === "offline";

  const draft = async () => {
    setDrafting(true);
    try {
      const r = await api.suggestedReply(ticketId);
      setText(r.text);
      toast(`Draft ready (${r.tone === "high" ? "extra empathy" : r.tone === "medium" ? "apologetic" : "friendly"} tone) — edit before sending`, "info");
    } catch (err) {
      toast(err.message, "error");
    } finally {
      setDrafting(false);
    }
  };

  const chatMessages = messages?.filter((m) => m.kind !== "system").length ?? 0;

  return (
    <Tile eyebrow={live ? "Live chat · Expert Escalation" : "Conversation"} icon={MessageSquare} className={className}
          bodyClass="min-h-0"
          action={
            <div className="flex items-center gap-2">
              {suggest && canReply && (
                <button className="btn-ghost !py-1 !px-2.5 !text-xs" onClick={draft} disabled={drafting}>
                  {drafting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Sparkles className="w-3.5 h-3.5" />} Suggest reply
                </button>
              )}
              {live && <span className="chip bg-senior-soft text-senior-text"><span className="w-1.5 h-1.5 rounded-full bg-senior animate-pulse" aria-hidden />live</span>}
            </div>
          }>
      {(disconnected || liveStatus === "recovering" || loadError) && (
        <div role="status" className="mb-3 flex flex-wrap items-center gap-2 rounded-2xl bg-sunken px-3 py-2 text-xs text-ink-2">
          {liveStatus === "recovering" ? <Loader2 className="w-3.5 h-3.5 animate-spin" aria-hidden /> : <WifiOff className="w-3.5 h-3.5" aria-hidden />}
          <span className="flex-1">
            {liveStatus === "recovering" ? "Reconnected, fetching anything you missed…"
              : liveStatus === "offline" ? "You're offline. Everything already sent is saved; new messages wait here."
                : "Connection lost, trying to reconnect. Everything already sent is saved."}
          </span>
          {liveStatus !== "recovering" && (
            <button className="btn-ghost !py-1 !px-2.5 !text-xs bg-card" onClick={resume} disabled={resuming}>
              {resuming ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RefreshCw className="w-3.5 h-3.5" />} Resume conversation
            </button>
          )}
        </div>
      )}
      <div id="conversation" ref={scroller} className={clsx("flex-1 overflow-y-auto scroll-thin space-y-3 pr-1", tall ? "min-h-[360px] max-h-[620px]" : "min-h-[260px] max-h-[520px]")} aria-live="polite">
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
              <AttachmentList items={m.attachments} compact light={m.mine} />
              <p className={clsx("text-[10px] mt-1", m.mine ? "opacity-60" : "text-ink-3")}>{timeAgo(m.created_at)}</p>
            </div>
          </div>
        ))}
        {pending.map((p) => (
          <div key={p.clientId} className="flex justify-end">
            <div className={clsx("max-w-[85%] rounded-2xl rounded-br-md px-3.5 py-2.5 border border-dashed",
              p.state === "failed" ? "border-senior/50 bg-senior-soft/40" : "border-line bg-sunken opacity-80")}>
              <p className="text-sm whitespace-pre-wrap break-words">{p.body || `${p.files.length} file(s)`}</p>
              <p className="text-[10px] mt-1 flex items-center gap-1.5 text-ink-3">
                {p.state === "sending" ? <><Loader2 className="w-3 h-3 animate-spin" aria-hidden />Sending…</> : (
                  <>
                    <AlertCircle className="w-3 h-3 text-senior-text" aria-hidden />
                    <span className="text-senior-text">Not sent{p.error ? `: ${p.error}` : ""}</span>
                    <button type="button" className="font-semibold text-glacier-text hover:underline" onClick={() => deliver(p)}>Retry</button>
                  </>
                )}
              </p>
            </div>
          </div>
        ))}
        {messages && chatMessages === 0 && !pending.length && (
          <p className="text-center text-sm text-ink-3 py-6">No messages yet. {canReply ? "Write below to start the conversation." : ""}</p>
        )}
        {typing && <p className="text-xs text-ink-3 italic">{typing} is typing…</p>}
      </div>
      {canReply ? (
        <form onSubmit={send} className="mt-3 pt-3 border-t border-line space-y-2">
          <PendingFiles files={files} onRemove={(i) => setFiles(files.filter((_, j) => j !== i))} />
          <div className="flex gap-2 items-end">
            <AttachButton files={files} setFiles={setFiles} onError={(m) => toast(m, "error")} disabled={busy} />
            <textarea className="field min-h-[44px] max-h-40 resize-y" rows={text.includes("\n") ? 5 : 1} value={text} onChange={onChange}
                      onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && send(e)}
                      placeholder={placeholder || "Write a message… (Enter to send, Shift+Enter for a new line)"} aria-label="Message" maxLength={4000} />
            <button className="btn-primary !px-3 h-[44px]" disabled={busy || (!text.trim() && !files.length)} aria-label="Send">
              {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
            </button>
          </div>
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
