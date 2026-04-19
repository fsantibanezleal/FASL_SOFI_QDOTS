"""
End-to-end FastAPI route tests.

Covers the HTTP surface that the production frontend and deployment
probes rely on:

    - GET /health
    - GET /api/version
    - POST /api/simulate -> POST /api/process happy path

The simulate -> process flow is exercised with small parameters so the
test stays well under a second on CI. Decoded cumulant arrays are
validated for shape and finiteness.
"""

import base64
import os
import sys

import numpy as np
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import __version__
from app.main import app


client = TestClient(app)


def _decode_float_image(b64: str, shape):
    """Decode a base64 float32 payload produced by routes._image_to_base64.

    The routes helper normalizes to [0, 1] and packs raw float32 bytes;
    we mirror that here so the test can reason about the decoded array.
    """
    raw = base64.b64decode(b64)
    arr = np.frombuffer(raw, dtype=np.float32)
    return arr.reshape(shape)


def test_health_returns_version_from_init():
    """/health must source its version from app.__version__."""
    response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["version"] == __version__


def test_api_version_endpoint():
    """/api/version is a dedicated probe returning the same version."""
    response = client.get("/api/version")
    assert response.status_code == 200
    payload = response.json()
    assert payload["version"] == __version__
    assert payload["service"] == "FASL SOFI QDOTS"


def test_simulate_then_process_happy_path():
    """POST /api/simulate then POST /api/process must return finite cumulants."""
    sim_payload = {
        "num_frames": 60,
        "image_size": 32,
        "num_emitters": 4,
        "psf_sigma": 1.5,
        "brightness": 1000.0,
        "background": 50.0,
        "noise_std": 10.0,
        "seed": 42,
    }
    sim = client.post("/api/simulate", json=sim_payload)
    assert sim.status_code == 200, sim.text
    sim_body = sim.json()
    assert sim_body["status"] == "ok"
    assert sim_body["num_frames"] == 60
    assert sim_body["image_size"] == [32, 32]

    proc_payload = {
        "orders": [2, 3],
        "window_size": 30,
        "use_fourier": False,
        "deconvolution": "none",
        "linearize": True,
        "psf_sigma": 1.5,
    }
    proc = client.post("/api/process", json=proc_payload)
    assert proc.status_code == 200, proc.text
    proc_body = proc.json()
    assert proc_body["status"] == "ok"
    assert proc_body["orders"] == [2, 3]

    for order in ("2", "3"):
        entry = proc_body["results"][order]
        shape = tuple(entry["shape"])
        # Cumulant images are at least as large as the input (n-fold up-sample possible).
        assert len(shape) == 2
        assert shape[0] >= 32 and shape[1] >= 32
        img = _decode_float_image(entry["image"], shape)
        assert np.isfinite(img).all(), f"Non-finite values in order-{order} cumulant"
        assert entry["max"] >= entry["min"]


def test_process_without_data_returns_400():
    """/api/process must 400 when simulate has not been called."""
    # Reset shared state so this test is order-independent.
    from app.api.routes import app_state

    app_state.images = None
    app_state.positions = None
    app_state.mean_image = None
    app_state.sofi_results = {}

    proc_payload = {
        "orders": [2],
        "window_size": 30,
        "use_fourier": False,
        "deconvolution": "none",
        "linearize": True,
        "psf_sigma": 1.5,
    }
    response = client.post("/api/process", json=proc_payload)
    assert response.status_code == 400


if __name__ == "__main__":
    # Allow running as a plain script for parity with the other tests/*.py files.
    test_health_returns_version_from_init()
    test_api_version_endpoint()
    test_process_without_data_returns_400()
    test_simulate_then_process_happy_path()
    print("All API tests passed.")
