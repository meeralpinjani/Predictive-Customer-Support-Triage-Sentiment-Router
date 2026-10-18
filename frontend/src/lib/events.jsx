import { createContext, useContext, useEffect, useRef, useState } from "react";
import { eventsUrl } from "../api.js";

const EventsCtx = createContext({ subscribe: () => () => {}, connected: false, status: "connecting", reconnect: () => {} });
export const useEvents = () => useContext(EventsCtx);

const TYPES = [
  "ticket.created", "ticket.updated", "ticket.escalated", "ticket.resolved", "message.created", "typing",
  "callback.requested", "callback.updated", "queue.rescored", "integrity.assessed", "integrity.review_updated",
  "summary.updated", "summary.failed", "handover.created",
];
const MAX_BACKOFF_MS = 30000;

/**
 * One server-sent-events stream per signed-in user, with its own reconnect and back-off.
 * status: connecting | connected | reconnecting | offline | recovering.
 * Events may be missed while disconnected (the server bus is in memory), so after reconnecting we
 * send a local "connection.restored" event: pages re-fetch from the API (useLiveData does this
 * automatically) before the status goes back to "connected".
 */
export function EventsProvider({ user, children }) {
  const listeners = useRef(new Set());
  const [status, setStatus] = useState("connecting");
  const [attempt, setAttempt] = useState(0);
  const failures = useRef(0);
  const hadError = useRef(false);

  useEffect(() => {
    if (!user) return undefined;
    let timer;
    const es = new EventSource(eventsUrl, { withCredentials: true });
    const emit = (data) => listeners.current.forEach((fn) => fn(data));
    const dispatch = (e) => {
      try {
        emit(JSON.parse(e.data));
      } catch {
        /* ignore malformed */
      }
    };
    TYPES.forEach((t) => es.addEventListener(t, dispatch));
    es.onopen = () => {
      failures.current = 0;
      if (hadError.current) {
        hadError.current = false;
        setStatus("recovering");
        emit({ type: "connection.restored" });          // pages refetch what they may have missed
        timer = setTimeout(() => setStatus("connected"), 1200);
      } else {
        setStatus("connected");
      }
    };
    es.onerror = () => {
      es.close();                                        // we manage retries ourselves, with back-off
      hadError.current = true;
      failures.current += 1;
      setStatus(navigator.onLine === false ? "offline" : "reconnecting");
      const wait = Math.min(1000 * 2 ** (failures.current - 1), MAX_BACKOFF_MS);
      timer = setTimeout(() => setAttempt((a) => a + 1), wait);
    };
    const online = () => setAttempt((a) => a + 1);
    const offline = () => setStatus("offline");
    window.addEventListener("online", online);
    window.addEventListener("offline", offline);
    return () => {
      clearTimeout(timer);
      es.close();
      window.removeEventListener("online", online);
      window.removeEventListener("offline", offline);
    };
  }, [user?.id, attempt]); // eslint-disable-line react-hooks/exhaustive-deps

  const reconnect = () => { hadError.current = true; failures.current = 0; setAttempt((a) => a + 1); };
  const subscribe = (fn) => {
    listeners.current.add(fn);
    return () => listeners.current.delete(fn);
  };
  return <EventsCtx.Provider value={{ subscribe, connected: status === "connected", status, reconnect }}>{children}</EventsCtx.Provider>;
}

/** Subscribe to live events with a handler that always sees fresh props/state. */
export function useEventListener(handler) {
  const { subscribe } = useEvents();
  const ref = useRef(handler);
  ref.current = handler;
  useEffect(() => subscribe((ev) => ref.current(ev)), [subscribe]);
}

/**
 * Load data, then reload when a matching live event arrives (debounced) and every
 * `intervalMs` as a safety net. Returns { data, error, loading, reload }.
 */
export function useLiveData(loader, { match = () => true, intervalMs = 20000, deps = [] } = {}) {
  const [state, setState] = useState({ data: null, error: "", loading: true });
  const timer = useRef();
  const loaderRef = useRef(loader);
  loaderRef.current = loader;

  const reload = async () => {
    try {
      const data = await loaderRef.current();
      setState({ data, error: "", loading: false });
    } catch (err) {
      setState((s) => ({ ...s, error: err.message, loading: false }));
    }
  };

  useEffect(() => {
    setState((s) => ({ ...s, loading: true }));
    reload();
    const id = setInterval(reload, intervalMs);
    return () => clearInterval(id);
  }, deps); // eslint-disable-line react-hooks/exhaustive-deps

  useEventListener((ev) => {
    if (ev.type === "typing" || (ev.type !== "connection.restored" && !match(ev))) return;
    clearTimeout(timer.current);
    timer.current = setTimeout(reload, 250);
  });

  return { ...state, reload };
}

/** A short two-tone chime for escalations (WebAudio, no asset needed). */
export function chime() {
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    [880, 1320].forEach((f, i) => {
      const o = ctx.createOscillator();
      const g = ctx.createGain();
      o.frequency.value = f;
      o.type = "sine";
      g.gain.setValueAtTime(0.0001, ctx.currentTime + i * 0.15);
      g.gain.exponentialRampToValueAtTime(0.15, ctx.currentTime + i * 0.15 + 0.02);
      g.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + i * 0.15 + 0.25);
      o.connect(g).connect(ctx.destination);
      o.start(ctx.currentTime + i * 0.15);
      o.stop(ctx.currentTime + i * 0.15 + 0.3);
    });
    setTimeout(() => ctx.close(), 800);
  } catch {
    /* audio unavailable */
  }
}
