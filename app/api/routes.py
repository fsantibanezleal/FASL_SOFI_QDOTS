"""
FastAPI REST and WebSocket Routes for SOFI Processing.

Provides endpoints for:
    - POST /api/simulate: Generate synthetic blinking data
    - POST /api/process: Run SOFI pipeline on current data
    - GET /api/state: Get current application state
    - WS /ws: WebSocket for real-time progress updates

All image data is transferred as base64-encoded PNG or raw float arrays
depending on the endpoint.
"""

import asyncio
import base64
import io
import json
import os
import tempfile
import time
from typing import Dict, List, Optional, Any

import numpy as np
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, UploadFile, File
from pydantic import BaseModel, Field

from ..simulation.emitter_simulator import simulate_blinking_sequence, generate_ground_truth
from ..simulation.sofi_pipeline import SOFIPipeline
from ..simulation.cumulants import compute_sofi_image
from ..simulation.tiff_loader import load_tiff_stack


# --------------- Pydantic Models ---------------

class SimulationParams(BaseModel):
    """Parameters for generating synthetic blinking data."""

    num_frames: int = Field(500, ge=50, le=5000, description="Number of time frames")
    image_size: int = Field(64, ge=16, le=256, description="Image size (square, pixels)")
    num_emitters: int = Field(20, ge=1, le=200, description="Number of QDot emitters")
    psf_sigma: float = Field(2.0, ge=0.5, le=10.0, description="PSF sigma (pixels)")
    brightness: float = Field(1000.0, ge=100.0, le=10000.0, description="Peak brightness")
    background: float = Field(100.0, ge=0.0, le=1000.0, description="Background intensity")
    noise_std: float = Field(20.0, ge=0.0, le=200.0, description="Read noise std")
    seed: Optional[int] = Field(None, description="Random seed (None for random)")


class ProcessParams(BaseModel):
    """Parameters for SOFI processing."""

    orders: List[int] = Field([2, 3, 4], description="Cumulant orders to compute")
    window_size: int = Field(100, ge=10, le=2000, description="Temporal window size")
    use_fourier: bool = Field(False, description="Apply Fourier interpolation")
    deconvolution: str = Field("none", description="Deconvolution method")
    linearize: bool = Field(True, description="Apply nth-root linearization")
    psf_sigma: float = Field(2.0, ge=0.5, le=10.0, description="PSF sigma for deconvolution")


class StateResponse(BaseModel):
    """Current application state."""

    has_data: bool = False
    num_frames: int = 0
    image_size: List[int] = [0, 0]
    num_emitters: int = 0
    processed_orders: List[int] = []
    simulation_params: Optional[Dict[str, Any]] = None


# --------------- Shared State ---------------

class AppState:
    """Application state shared between routes.

    Stores the current image stack, processing results, and
    connected WebSocket clients.
    """

    def __init__(self):
        self.images: Optional[np.ndarray] = None
        self.positions: Optional[np.ndarray] = None
        self.mean_image: Optional[np.ndarray] = None
        self.sofi_results: Dict[int, np.ndarray] = {}
        self.simulation_params: Optional[Dict[str, Any]] = None
        self.ws_clients: List[WebSocket] = []

    async def broadcast(self, message: dict):
        """Send a message to all connected WebSocket clients."""
        disconnected = []
        for ws in self.ws_clients:
            try:
                await ws.send_json(message)
            except Exception:
                disconnected.append(ws)
        for ws in disconnected:
            self.ws_clients.remove(ws)


app_state = AppState()

# --------------- Router ---------------

router = APIRouter()


def _image_to_base64(image: np.ndarray) -> str:
    """Convert a 2D float image to base64-encoded raw float32 data.

    The image is normalized to [0, 1] and converted to float32.

    Args:
        image: 2D numpy array.

    Returns:
        Base64-encoded string of the float32 data, plus shape info.
    """
    img = image.astype(np.float32)
    vmin, vmax = img.min(), img.max()
    if vmax > vmin:
        img = (img - vmin) / (vmax - vmin)
    return base64.b64encode(img.tobytes()).decode("ascii")


@router.post("/api/simulate")
async def simulate(params: SimulationParams):
    """Generate synthetic blinking fluorescence data.

    Creates a time-lapse image stack with blinking quantum dot
    emitters and stores it in the application state.

    Returns metadata about the generated data and the mean image
    for display.
    """
    start_time = time.time()

    await app_state.broadcast({"type": "progress", "step": "Generating simulation...", "progress": 0.0})

    # Run simulation in thread pool to avoid blocking
    loop = asyncio.get_event_loop()
    images, positions = await loop.run_in_executor(
        None,
        lambda: simulate_blinking_sequence(
            num_frames=params.num_frames,
            image_size=(params.image_size, params.image_size),
            num_emitters=params.num_emitters,
            psf_sigma=params.psf_sigma,
            brightness=params.brightness,
            background=params.background,
            noise_std=params.noise_std,
            seed=params.seed,
        ),
    )

    # Store in state
    app_state.images = images
    app_state.positions = positions
    app_state.mean_image = np.mean(images, axis=0)
    app_state.sofi_results = {}
    app_state.simulation_params = params.model_dump()

    elapsed = time.time() - start_time

    await app_state.broadcast({"type": "progress", "step": "Simulation complete", "progress": 1.0})

    mean_b64 = _image_to_base64(app_state.mean_image)
    H, W = app_state.mean_image.shape

    # Generate ground truth image (emitters convolved with PSF, no noise)
    ground_truth = generate_ground_truth(
        positions, (H, W), params.psf_sigma, params.brightness
    )
    gt_b64 = _image_to_base64(ground_truth)

    return {
        "status": "ok",
        "num_frames": int(images.shape[0]),
        "image_size": [int(images.shape[1]), int(images.shape[2])],
        "num_emitters": int(positions.shape[0]),
        "elapsed_seconds": round(elapsed, 3),
        "mean_image": mean_b64,
        "mean_shape": [H, W],
        "ground_truth": gt_b64,
        "ground_truth_shape": [H, W],
        "positions": positions.tolist(),
    }


@router.post("/api/process")
async def process(params: ProcessParams):
    """Run the SOFI processing pipeline on current data.

    Computes cumulant images for the requested orders and returns
    the results as base64-encoded float arrays.
    """
    if app_state.images is None:
        raise HTTPException(status_code=400, detail="No image data loaded. Run /api/simulate first.")

    start_time = time.time()

    # Progress callback for WebSocket updates
    async def _progress(step: str, frac: float):
        await app_state.broadcast({"type": "progress", "step": step, "progress": frac})

    # Validate orders
    for order in params.orders:
        if order < 2 or order > 6:
            raise HTTPException(status_code=400, detail=f"Invalid order: {order}. Must be 2-6.")

    loop = asyncio.get_event_loop()
    results = {}

    for i, order in enumerate(params.orders):
        await app_state.broadcast({
            "type": "progress",
            "step": f"Computing order-{order} cumulant...",
            "progress": i / len(params.orders),
        })

        sofi_img = await loop.run_in_executor(
            None,
            lambda o=order: compute_sofi_image(
                app_state.images,
                o,
                window_size=params.window_size,
                linearize=params.linearize,
            ),
        )

        app_state.sofi_results[order] = sofi_img
        results[str(order)] = {
            "image": _image_to_base64(sofi_img),
            "shape": list(sofi_img.shape),
            "min": float(sofi_img.min()),
            "max": float(sofi_img.max()),
        }

    elapsed = time.time() - start_time

    await app_state.broadcast({"type": "progress", "step": "Processing complete", "progress": 1.0})

    return {
        "status": "ok",
        "orders": params.orders,
        "elapsed_seconds": round(elapsed, 3),
        "results": results,
    }


@router.get("/api/state")
async def get_state():
    """Get the current application state."""
    return StateResponse(
        has_data=app_state.images is not None,
        num_frames=int(app_state.images.shape[0]) if app_state.images is not None else 0,
        image_size=(
            list(app_state.images.shape[1:]) if app_state.images is not None else [0, 0]
        ),
        num_emitters=(
            int(app_state.positions.shape[0]) if app_state.positions is not None else 0
        ),
        processed_orders=list(app_state.sofi_results.keys()),
        simulation_params=app_state.simulation_params,
    )


@router.post("/api/upload-tiff")
async def upload_tiff(file: UploadFile = File(...)):
    """Upload a TIFF stack for SOFI processing.

    Accepts a .tif or .tiff file, loads it as a 3D image stack, and
    stores it in the application state for subsequent processing via
    the /api/process endpoint.

    Returns metadata about the loaded stack and its mean image.
    """
    if file.filename and not file.filename.lower().endswith((".tif", ".tiff")):
        raise HTTPException(
            status_code=400,
            detail="File must be a TIFF (.tif or .tiff) file.",
        )

    # Save to a temporary file so tifffile/Pillow can read it
    try:
        content = await file.read()
        with tempfile.NamedTemporaryFile(suffix=".tiff", delete=False) as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        images = load_tiff_stack(tmp_path)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to load TIFF: {e}")
    finally:
        # Clean up temp file
        try:
            os.unlink(tmp_path)
        except Exception:
            pass

    # Store in application state
    app_state.images = images
    app_state.positions = None
    app_state.mean_image = np.mean(images, axis=0)
    app_state.sofi_results = {}
    app_state.simulation_params = {
        "source": "tiff_upload",
        "filename": file.filename,
        "num_frames": int(images.shape[0]),
        "image_size": [int(images.shape[1]), int(images.shape[2])],
    }

    mean_b64 = _image_to_base64(app_state.mean_image)
    H, W = app_state.mean_image.shape

    return {
        "status": "ok",
        "source": "tiff_upload",
        "filename": file.filename,
        "num_frames": int(images.shape[0]),
        "image_size": [int(images.shape[1]), int(images.shape[2])],
        "dtype": str(images.dtype),
        "value_range": [float(images.min()), float(images.max())],
        "mean_image": mean_b64,
        "mean_shape": [H, W],
    }


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time progress updates.

    Clients connect here to receive progress messages during
    simulation and processing. Messages are JSON with format:
        {"type": "progress", "step": "...", "progress": 0.0-1.0}
    """
    await websocket.accept()
    app_state.ws_clients.append(websocket)

    try:
        while True:
            # Keep connection alive, handle incoming messages
            data = await websocket.receive_text()
            # Echo back for ping/pong
            if data == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        if websocket in app_state.ws_clients:
            app_state.ws_clients.remove(websocket)
