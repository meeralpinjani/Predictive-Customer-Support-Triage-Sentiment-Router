"""Real-time events (server-sent events) for live queues, escalations and chat.

Each browser holds one /api/events stream. Endpoints run in worker threads, so publishing
hands events to the event loop thread-safely. Delivery is filtered per user: customers see
their own tickets, agents see their level (and tickets assigned to them), admins see all.
"""
import asyncio
import json
import logging
from dataclasses import dataclass, field

log = logging.getLogger("triage.events")


@dataclass(eq=False)  # identity-hashed so subscribers can live in a set
class Subscriber:
    user_id: int
    role: str
    customer_id: str | None
    queue: asyncio.Queue = field(default_factory=lambda: asyncio.Queue(maxsize=200))


_subscribers: set[Subscriber] = set()
_loop: asyncio.AbstractEventLoop | None = None


def bind_loop(loop: asyncio.AbstractEventLoop) -> None:
    global _loop
    _loop = loop


def subscribe(user_id: int, role: str, customer_id: str | None) -> Subscriber:
    sub = Subscriber(user_id, role, customer_id)
    _subscribers.add(sub)
    return sub


def unsubscribe(sub: Subscriber) -> None:
    _subscribers.discard(sub)


def _wants(sub: Subscriber, ev: dict) -> bool:
    if sub.user_id == ev.get("actor_id") and ev["type"] == "typing":
        return False
    if sub.role == "admin":
        return True
    if sub.role == "customer":
        return ev.get("customer_id") is not None and ev.get("customer_id") == sub.customer_id
    # agents: their level now, the level a ticket just left, or tickets assigned to them
    return (
        sub.role in (ev.get("route"), ev.get("old_route"))
        or (ev.get("assigned_agent_id") is not None and ev.get("assigned_agent_id") == sub.user_id)
    )


def _deliver(ev: dict) -> None:
    for sub in list(_subscribers):
        if _wants(sub, ev):
            try:
                sub.queue.put_nowait(ev)
            except asyncio.QueueFull:
                log.warning("Dropping event for slow subscriber %s", sub.user_id)


def publish(ev: dict) -> None:
    """Thread-safe: callable from sync endpoints and the background re-scorer."""
    if _loop is None or _loop.is_closed():
        return
    try:
        running = asyncio.get_running_loop()
    except RuntimeError:
        running = None
    if running is _loop:
        _deliver(ev)
    else:
        _loop.call_soon_threadsafe(_deliver, ev)


def ticket_event(kind: str, t, old_route: str | None = None, **extra) -> dict:
    return {
        "type": kind,
        "ticket_id": t.id,
        "customer_id": t.customer_id,
        "route": t.route,
        "old_route": old_route,
        "assigned_agent_id": t.assigned_agent_id,
        "status": t.status,
        **extra,
    }


def encode(ev: dict) -> str:
    return f"event: {ev['type']}\ndata: {json.dumps(ev, default=str)}\n\n"
