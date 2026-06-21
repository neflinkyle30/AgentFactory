"""Agent Factory OSS — FastAPI application entry point."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.runs import router as runs_router
from app.auth.routes import router as auth_router
from app.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan — runs startup and shutdown logic."""
    # Startup
    if settings.dev_mode:
        print("[DEV] Agent Factory running in development mode (SQLite)")
    if settings.mock_mode:
        print("[MOCK] AI provider running in mock mode — no API calls will be made")
    print("[ORCH] Orchestrator initialized — pipeline ready")
    yield
    # Shutdown
    # Future: close DB connection pool, etc.


app = FastAPI(
    title="Agent Factory",
    description="AI-powered ticket-to-PR pipeline",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS — allow frontend dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ─────────────────────────────────────────────────────────

app.include_router(runs_router)
app.include_router(auth_router)


@app.get("/health", tags=["system"])
async def health_check() -> JSONResponse:
    """Health check endpoint — returns 200 when the service is running."""
    return JSONResponse(
        content={
            "status": "ok",
            "version": "0.1.0",
            "mock_mode": settings.mock_mode,
        }
    )
