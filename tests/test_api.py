"""
End-to-end FastAPI route tests.

Covers the HTTP surface that the production frontend and deployment
probes rely on:

    - GET /health
    - GET /api/version
    - POST /api/simulate -> POST /api/process happy path
    - POST /api/upload (TIFF upload with size cap + dtype validation)

The simulate -> process flow is exercised with small parameters so the
test stays well under a second on CI. Decoded cumulant arrays are
validated for shape and finiteness.
"""

import base64
import io
import os
import sys

import numpy as np
import pytest
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


# --------------- /api/upload (TIFF upload) ---------------


def _synth_tiff_bytes(frames: int = 3, size: int = 8, dtype: str = "uint16") -> bytes:
    """Build an in-memory multi-frame TIFF with the requested dtype.

    Uses tifffile.imwrite so the authored dtype is preserved and our
    server-side dtype check actually sees what we think it does.
    """
    tifffile = pytest.importorskip("tifffile")
    rng = np.random.default_rng(0)
    if dtype == "uint16":
        stack = rng.integers(0, 1000, size=(frames, size, size), dtype=np.uint16)
    elif dtype == "float32":
        stack = rng.random((frames, size, size), dtype=np.float32)
    elif dtype == "float64":
        stack = rng.random((frames, size, size)).astype(np.float64)
    elif dtype == "uint8":
        stack = rng.integers(0, 255, size=(frames, size, size), dtype=np.uint8)
    else:
        raise ValueError(f"Unsupported test dtype: {dtype}")
    buf = io.BytesIO()
    tifffile.imwrite(buf, stack)
    return buf.getvalue()


def test_upload_accepts_uint16_tiff():
    """POST /api/upload with a small uint16 TIFF must succeed and populate state."""
    pytest.importorskip("tifffile")
    tiff_bytes = _synth_tiff_bytes(frames=3, size=8, dtype="uint16")
    response = client.post(
        "/api/upload",
        files={"file": ("tiny.tiff", tiff_bytes, "image/tiff")},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "ok"
    assert body["source"] == "upload"
    assert body["frames"] == 3
    assert body["height"] == 8
    assert body["width"] == 8
    assert body["dtype"] == "uint16"
    assert body["mean_shape"] == [8, 8]
    # State should reflect the upload so /api/process can consume it.
    from app.api.routes import app_state

    assert app_state.images is not None
    assert app_state.images.shape == (3, 8, 8)


def test_upload_rejects_wrong_extension():
    """Non-TIFF filenames must be rejected with 400 before any read."""
    response = client.post(
        "/api/upload",
        files={"file": ("notes.txt", b"hello", "text/plain")},
    )
    assert response.status_code == 400
    assert "TIFF" in response.json()["detail"]


def test_upload_rejects_uint8_dtype():
    """uint8 is not in the allowed authored-dtype set — must 415."""
    pytest.importorskip("tifffile")
    tiff_bytes = _synth_tiff_bytes(frames=2, size=8, dtype="uint8")
    response = client.post(
        "/api/upload",
        files={"file": ("u8.tiff", tiff_bytes, "image/tiff")},
    )
    assert response.status_code == 415
    assert "uint8" in response.json()["detail"]


def test_upload_enforces_size_cap(monkeypatch):
    """Exceeding SOFI_MAX_UPLOAD_MB must 413 before the stack is loaded."""
    pytest.importorskip("tifffile")
    # A 3x64x64 uint16 TIFF is ~24 KB — well above a 0 MB (forced-1 MB floor) cap
    # once we craft a larger payload. Pad to >1 MB so we cross the cap deterministically.
    big_bytes = _synth_tiff_bytes(frames=5, size=512, dtype="uint16")
    assert len(big_bytes) > 1_048_576, "Crafted TIFF must exceed 1 MB to exercise cap"
    monkeypatch.setenv("SOFI_MAX_UPLOAD_MB", "1")
    response = client.post(
        "/api/upload",
        files={"file": ("big.tiff", big_bytes, "image/tiff")},
    )
    assert response.status_code == 413
    assert "size cap" in response.json()["detail"]


if __name__ == "__main__":
    # Allow running as a plain script for parity with the other tests/*.py files.
    test_health_returns_version_from_init()
    test_api_version_endpoint()
    test_process_without_data_returns_400()
    test_simulate_then_process_happy_path()
    test_upload_accepts_uint16_tiff()
    test_upload_rejects_wrong_extension()
    test_upload_rejects_uint8_dtype()
    print("All API tests passed.")
