"""Watari API application entry point."""

from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.error_handlers import register_error_handlers
from src.api.middleware import RequestIDMiddleware
from src.api.routers import alerts as alerts_router
from src.api.routers import assets as assets_router
from src.api.routers import attack as attack_router
from src.api.routers import audit as audit_router
from src.api.routers import auth as auth_router
from src.api.routers import cases as cases_router
from src.api.routers import dashboard as dashboard_router
from src.api.routers import enrichment as enrichment_router
from src.api.routers import evidence as evidence_router
from src.api.routers import modules as modules_router
from src.api.routers import notes as notes_router
from src.api.routers import observables as observables_router
from src.api.routers import realtime as realtime_router
from src.api.routers import reports as reports_router
from src.api.routers import search as search_router
from src.api.routers import tasks as tasks_router
from src.api.routers import templates as templates_router
from src.api.routers import tenants as tenants_router
from src.api.routers import timeline as timeline_router
from src.api.routers import users as users_router
from src.db.engine import admin_engine, engine
from src.realtime import get_hub
from src.utils import get_settings

settings = get_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Manage application startup and shutdown.

    The async engine creates connections lazily, so startup is a no-op
    aside from holding a reference. On shutdown we dispose the pool so
    pending connections are closed cleanly. We also start / stop the
    realtime WebSocket hub's Redis pub/sub listener.
    """
    hub = get_hub()
    await hub.start_listener()
    try:
        yield
    finally:
        await hub.stop()
        await engine.dispose()
        await admin_engine.dispose()


app = FastAPI(
    title="Watari API",
    version="0.1.0",
    description="Collaborative Case Management Platform for cybersecurity teams",
    docs_url="/docs",
    redoc_url="/redoc",
    debug=settings.app_debug,
    lifespan=lifespan,
)

# Request ID middleware runs first so every subsequent middleware and
# handler can access `request.state.request_id` for logging/tracing.
app.add_middleware(RequestIDMiddleware)

# CORS middleware configured for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global exception handlers that wrap all errors in the ApiError envelope
register_error_handlers(app)

# Route registration
app.include_router(auth_router.router)
app.include_router(tenants_router.router)
app.include_router(users_router.router)
app.include_router(cases_router.router)
app.include_router(tasks_router.router)
app.include_router(templates_router.router)
app.include_router(observables_router.router)
app.include_router(assets_router.router)
app.include_router(evidence_router.router)
app.include_router(timeline_router.router)
app.include_router(alerts_router.router)
app.include_router(notes_router.router)
app.include_router(search_router.router)
app.include_router(audit_router.router)
app.include_router(enrichment_router.sources_router)
app.include_router(enrichment_router.trigger_router)
app.include_router(enrichment_router.results_router)
app.include_router(attack_router.mappings_router)
app.include_router(attack_router.reference_router)
app.include_router(reports_router.templates_router)
app.include_router(reports_router.reports_router)
app.include_router(modules_router.router)
app.include_router(dashboard_router.router)
app.include_router(realtime_router.router)


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}
