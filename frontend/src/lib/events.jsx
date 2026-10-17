import { createContext, useContext, useEffect, useRef, useState } from "react";
import { eventsUrl } from "../api.js";

const EventsCtx = createContext({ subscribe: () => () => {}, connected: false });
export const useEvents = () => useContext(EventsCtx);

const TYPES = [
  "ticket.created", "ticket.updated", "ticket.escalated", "ticket.resolved", "message.created", "typing",
  "callback.requested", "callback.updated", "queue.rescored",
];

/** One server-sent-events stream per signed-in user. The browser reconnects automatically. */
export function EventsProvider({ user, children }) {
  const listeners = useRef(new Set());
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    if (!user) return undefined;
    const es = new EventSource(eventsUrl, { withCredentials: true });
    const dispatch = (e) => {
      try {
        const data = JSON.parse(e.data);
        listeners.current.forEach((fn) => fn(data));
      } catch {
        /* ignore malformed */
      }
    };
    TYPES.forEach((t) => es.addEventListener(t, dispatch));
    es.onopen = () => setConnected(true);
    es.onerror = () => setConnected(false);
    return () => {
      es.close();
      setConnected(false);
    };
  }, [user?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  const subscribe = (fn) => {
    listeners.current.add(fn);
    return () => listeners.current.delete(fn);
  };
  return <EventsCtx.Provider value={{ subscribe, connected }}>{children}</EventsCtx.Provider>;
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
    if (ev.type === "typing" || !match(ev)) return;
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
