import asyncio
from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import events
from app.api.auth import admin_router as users_router
from app.api.auth import router as auth_router
from app.api.conversation import router as conversation_router
from app.api.integrity import router as integrity_router
from app.api.knowledge import router as knowledge_router
from app.api.misc import router as misc_router
from app.api.operations import router as operations_router
from app.api.tickets import router as tickets_router
from app.config import settings
from app.schema_upgrade import create_and_upgrade
from app.db import Base, SessionLocal, engine
from app.services import integrity, retrain, summarization
from app.services.rescore import rescore_open

log = logging.getLogger("app.main")


def _rescore_once() -> None:
    db = SessionLocal()
    try:
        rescore_open(db)
    finally:
        db.close()


def _reconcile_summaries() -> None:
    db = SessionLocal()
    try:
        summarization.reconcile(db)
    finally:
        db.close()


async def summary_reconcile_worker() -> None:
    """Start-up and periodic check of summaries against the full history (catches anything missed)."""
    while True:
        try:
            if settings.ticket_summary_enabled:
                await asyncio.to_thread(_reconcile_summaries)
            await asyncio.sleep(max(settings.ticket_summary_reconcile_interval_minutes, 1) * 60)
        except asyncio.CancelledError:
            break
        except Exception as exc:
            log.warning("Summary reconcile error: %s", exc)
            await asyncio.sleep(60)


async def background_rescore_worker() -> None:
    while True:
        try:
            await asyncio.sleep(settings.rescore_interval_sec)
            await asyncio.to_thread(_rescore_once)
        except asyncio.CancelledError:
            break
        except Exception as exc:
            log.warning("Background rescore error: %s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    create_and_upgrade(engine)
    with SessionLocal() as db:
        retrain.load_tuning(db)
    events.bind_loop(asyncio.get_running_loop())
    if settings.nlp_mode == "hf":
        from app.nlp import hf
        hf.warmup(background=True)   # API serves with rules until the models are loaded
    worker_task = asyncio.create_task(background_rescore_worker())
    summary_task = asyncio.create_task(summary_reconcile_worker())
    integrity.startup()   # no-op unless AI_INTEGRITY_ENABLED
    try:
        yield
    finally:
        worker_task.cancel()
        summary_task.cancel()
        try:
            await worker_task
        except asyncio.CancelledError:
            pass
        integrity.shutdown()


app = FastAPI(
    title="Predictive Customer Support Triage & Sentiment Router",
    description="Context-aware ticket triage and sentiment router API (AlgoAmigos)",
    version="3.0.0",
    lifespan=lifespan,
)

origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
# The dashboard normally calls the API through the Vite / nginx proxy (same origin).
# CORS only matters if it is served from another origin; cookies need credentials then.
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins or ["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Content-Type"],
)

app.include_router(auth_router)
app.include_router(users_router)
app.include_router(misc_router)
app.include_router(tickets_router)
app.include_router(knowledge_router)
app.include_router(operations_router)
app.include_router(integrity_router)
app.include_router(conversation_router)

summarization.install(SessionLocal)   # summaries follow every committed change


@app.get("/", tags=["system"])
def root() -> dict[str, str]:
    return {
        "name": "Predictive Customer Support Triage API",
        "docs": "/docs",
        "health": "/api/health",
        "mode": settings.nlp_mode,
    }
