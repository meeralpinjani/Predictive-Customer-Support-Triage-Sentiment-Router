import asyncio
from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.misc import router as misc_router
from app.api.tickets import router as tickets_router
from app.config import settings
from app.db import Base, SessionLocal, engine
from app.services.rescore import rescore_open

log = logging.getLogger("app.main")


async def background_rescore_worker() -> None:
    while True:
        try:
            await asyncio.sleep(settings.rescore_interval_sec)
            db = SessionLocal()
            try:
                rescore_open(db)
            finally:
                db.close()
        except asyncio.CancelledError:
            break
        except Exception as exc:
            log.warning("Background rescore error: %s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    Base.metadata.create_all(bind=engine)
    worker_task = asyncio.create_task(background_rescore_worker())
    try:
        yield
    finally:
        worker_task.cancel()
        try:
            await worker_task
        except asyncio.CancelledError:
            pass


app = FastAPI(
    title="Predictive Customer Support Triage & Sentiment Router",
    description="Context-aware ticket triage and sentiment router API (AlgoAmigos)",
    version="1.0.0",
    lifespan=lifespan,
)

# Configure CORS
origins = [origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(misc_router)
app.include_router(tickets_router)


@app.get("/", tags=["system"])
def root() -> dict[str, str]:
    return {
        "name": "Predictive Customer Support Triage API",
        "docs": "/docs",
        "health": "/api/health",
        "mode": settings.nlp_mode,
    }
