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

from .api.routes import router

# Application metadata
app = FastAPI(
    title="FASL SOFI QDOTS",
    description=(
        "Super-resolution Optical Fluctuation Imaging (SOFI) web application. "
        "Simulates quantum dot blinking and computes cumulant-based "
        "super-resolution images (orders 2-6)."
    ),
    version="2.0.0",
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
    """Health check endpoint."""
    return {"status": "ok", "service": "FASL SOFI QDOTS", "version": "2.0.0"}
