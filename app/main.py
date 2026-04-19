"""
FASL SOFI QDOTS - FastAPI Application Entry Point.

Super-resolution Optical Fluctuation Imaging web application.
Provides a REST API and WebSocket interface for simulating quantum dot
blinking data and computing SOFI cumulant super-resolution images.

Usage:
    uvicorn app.main:app --port 8007 --reload

Or:
    python -m uvicorn app.main:app --port 8007

The application serves:
    - Static frontend at /
    - REST API at /api/*
    - WebSocket at /ws
"""

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path

from . import __version__
from .api.routes import router

# Application metadata
app = FastAPI(
    title="FASL SOFI QDOTS",
    description=(
        "Super-resolution Optical Fluctuation Imaging (SOFI) web application. "
        "Simulates quantum dot blinking and computes cumulant-based "
        "super-resolution images (orders 2-6)."
    ),
    version=__version__,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Include API routes
app.include_router(router)

# Serve static files
static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/")
async def root():
    """Serve the main frontend page."""
    return FileResponse(str(static_dir / "index.html"))


@app.get("/health")
async def health():
    """Health check endpoint.

    Returns a small JSON payload suitable for load-balancer / uptime probes.
    Version is sourced from ``app.__version__`` so there is a single source
    of truth for the deployed build.
    """
    return {"status": "ok", "service": "FASL SOFI QDOTS", "version": __version__}


@app.get("/api/version")
async def api_version():
    """Application version endpoint.

    Dedicated version probe for deployment tooling (cPanel Passenger,
    systemd, CI). Returns the same ``__version__`` as ``/health`` so
    smoke tests can pin a specific release.
    """
    return {"version": __version__, "service": "FASL SOFI QDOTS"}
