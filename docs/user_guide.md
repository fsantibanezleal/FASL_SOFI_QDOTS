# User Guide — FASL SOFI QDOTS

Operator-focused guide for running synthetic SOFI simulations, processing TIFF
stacks, and interpreting the super-resolution output. For the mathematical
foundation see `docs/sofi_theory.md`; for system design see
`docs/architecture.md`.

---

## 1. Launching the Application

### Local development
```bash
cd FASL_SOFI_QDOTS
python -m venv .venv
source .venv/Scripts/activate        # Windows (Git Bash / bash)
pip install -r requirements.txt
python -m uvicorn app.main:app --port 8007
```

Then open **http://localhost:8007** in your browser.

- Swagger UI: `http://localhost:8007/docs`
- ReDoc: `http://localhost:8007/redoc`
- WebSocket progress endpoint: `ws://localhost:8007/ws`

### One-click launcher
`python run_app.py` starts the Uvicorn server and auto-opens the browser.

---

## 2. The Frontend at a Glance

The single-page UI is divided into three sections:

1. **Simulation controls** — parameters for the synthetic QDot dataset
   (number of frames, emitters, PSF sigma, brightness, noise).
2. **Processing controls** — cumulant orders, window size, optional Fourier
   interpolation, deconvolution selector, linearization toggle.
3. **Output canvas** — renders the widefield mean image and each SOFI order
   side-by-side with selectable colormap (gray, hot, viridis, inferno).

A bottom progress bar is driven live by the `/ws` WebSocket.

---

## 3. Running a Synthetic Experiment

### 3.1 Quick recipe — "first working SOFI"

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| `num_frames` | 500 | Enough statistics for orders 2–4 |
| `image_size` | 64 | Fast, fits typical screens at 4x |
| `num_emitters` | 20 | Dense enough to show clustering |
| `psf_sigma` | 2.0 px | ~diffraction-limited (FWHM ≈ 4.7 px) |
| `brightness` | 1000 | Good SNR against background |
| `background` | 100 | Realistic widefield baseline |
| `noise_std` | 20 | Typical sCMOS read noise |
| `seed` | 42 | Reproducible for screenshots |

### 3.2 Processing recipe

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| `orders` | `[2, 3, 4]` | Cover √2, √3, 2× resolution gain |
| `window_size` | 100 | Robust to drift / bleaching |
| `use_fourier` | `true` | Sub-pixel detail for order ≥ 3 |
| `deconvolution` | `"wiener"` | Reach full n-fold (SOFIX) gain |
| `linearize` | `true` | Correct the εⁿ brightness bias |

---

## 4. Interpreting the Output

Each order `n` produces three images in the canvas:

- **Raw cumulant** `|C_n(r)|` — shows blob narrowing but brightness scales as εⁿ.
- **Linearized SOFI** `|C_n|^(1/n)` — restores physical brightness scaling.
- **SOFIX** (if Fourier + deconvolution enabled) — full n-fold resolution image.

Expected qualitative changes as `n` grows:

| Order | Visible effect on clustered emitters |
|-------|--------------------------------------|
| 1 (mean) | Everything blurred into a single blob |
| 2 | Blob narrows √2 → clusters start to separate |
| 3 | Asymmetric shapes appear; signed (can go negative) |
| 4 | Two nearby emitters cleanly resolved |
| 5–6 | High-order artifacts unless SNR and frame count are generous |

### Signed cumulants
Odd orders (3, 5) carry a sign; the UI plots `|C_n|` for display.
The sign encodes the skewness of the intensity trace and is used internally
by bSOFI flattening — it is **not** a rendering bug.

---

## 5. Loading Experimental TIFF Stacks

`app/simulation/tiff_loader.py` accepts multi-frame TIFF stacks (tifffile +
Pillow fallback). Typical usage from Python:

```python
from app.simulation.tiff_loader import load_tiff_stack
from app.simulation.sofi_pipeline import SOFIPipeline

stack = load_tiff_stack("data/qdots_session01.tif")   # shape (T, H, W)
pipeline = SOFIPipeline(orders=[2, 3, 4], psf_sigma=2.0,
                        use_fourier=True, deconvolution="wiener")
result = pipeline.process(stack)
```

**Data hygiene checklist before processing:**

- [ ] At least 500 frames (1000+ preferred for orders ≥ 4).
- [ ] No global bleaching over the window; if present, shorten `window_size`.
- [ ] Sample drift corrected (SOFI is not translation-invariant inside a window).
- [ ] Background subtracted or uniform across FOV.
- [ ] `psf_sigma` matches your microscope (set from the Airy radius in pixels).

---

## 6. Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| Cumulants look identical to mean image | Emitters do not blink | Increase `num_frames`, verify simulation noise, or check TIFF content |
| Order-4 image is noisy speckle | Insufficient frames for higher statistics | Raise `num_frames` ≥ 1000 or lower order |
| SOFIX image has ringing | Over-deconvolved | Switch `deconvolution` from `wiener` to `none`, or lower iterations |
| Output canvas blank | WebSocket not connected | Reload page, check browser console for `/ws` errors |
| `psf_sigma` mismatch warning | Deconvolution kernel inconsistent with PSF used in simulation | Use the same `psf_sigma` in both `simulate` and `process` |
| High-memory error on large stacks | Entire stack held in RAM | Lower `window_size`, crop ROI, or process in batches |

---

## 7. Tests & Validation

```bash
python -m pytest tests/ -v
```

- `test_cumulants.py` — validates C₂…C₆ against analytic distributions.
- `test_emitter.py` — power-law exponent fit from simulated on/off times.
- `test_mssr.py` — Mean-Shift super-resolution unit tests.
- `test_pipeline.py` — end-to-end resolution gain check.

A passing suite is the minimum pre-commit gate.

---

## 8. API Quick Reference

- `POST /api/simulate` → `{ "frames": [...], "mean_image": [...], "shape": [T,H,W] }`
- `POST /api/process`  → `{ "cumulant_images": {...}, "sofi_images": {...} }`
- `GET  /api/state`    → current simulation + processing parameters
- `WS   /ws`           → `{ "type": "progress", "step": "...", "progress": 0.0–1.0 }`

See `docs/architecture.md` for the full module map and `README.md` for the
parameter tables.
