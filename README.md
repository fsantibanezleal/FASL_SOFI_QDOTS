# FASL SOFI QDOTS -- Super-Resolution Optical Fluctuation Imaging

![Architecture](docs/svg/architecture.svg)

## Overview

Super-resolution Optical Fluctuation Imaging (SOFI) extracts sub-diffraction spatial information from temporal fluorescence fluctuations of independently blinking quantum dot (QDot) emitters. Unlike single-molecule localization methods (PALM/STORM) that require extreme emitter sparsity, SOFI operates on dense labeling by exploiting higher-order statistical cumulants of intensity time traces.

The nth-order cumulant of the fluorescence signal narrows the effective point spread function (PSF) by a factor of sqrt(n), achieving super-resolution without hardware modifications. This web application provides a complete SOFI processing pipeline -- from synthetic QDot blinking simulation to cumulant computation, Fourier interpolation, and deconvolution -- all accessible through a browser-based interface.

![SOFI Pipeline](docs/svg/sofi_pipeline.svg)

## Frontend

![Frontend Base](docs/png/frontend_base.png)

![Frontend Outputs](docs/png/frontend_outs.png)

## Quick Start

```bash
# Clone and enter the project
cd FASL_SOFI_QDOTS

# Create and activate virtual environment
python -m venv .venv
source .venv/Scripts/activate   # Windows
# source .venv/bin/activate     # Linux / macOS

# Install dependencies
pip install -r requirements.txt

# Launch the server
python -m uvicorn app.main:app --port 8007
```

Open **http://localhost:8007** in your browser. The interactive Swagger docs are at `/docs` and ReDoc at `/redoc`.

## Mathematical Foundation

### Fluorescence Signal Model

The observed fluorescence at pixel position **r** and time *t* is a superposition of all emitters convolved with the microscope PSF:

```
F(r, t) = Sum_k  eps_k * s_k(t) * U(r - r_k)
```

where:
- `eps_k` -- molecular brightness of emitter *k*
- `s_k(t)` -- stochastic on/off switching function (telegraph process)
- `U(r)` -- point spread function (Gaussian or Airy)
- `r_k` -- true position of emitter *k*

### Cumulant Super-Resolution

The nth-order cumulant of the intensity time series yields:

```
C_n(r) = Sum_k  eps_k^n * kappa_n[s_k] * U^n(r - r_k)
```

The key insight: the PSF is raised to the nth power, narrowing the effective PSF:

```
sigma_eff = sigma_PSF / sqrt(n)
```

Cross-terms between different emitters vanish because emitters fluctuate independently -- a fundamental property of cumulants.

![Cumulant Orders](docs/svg/cumulant_orders.svg)

### Cumulant Formulas (Zero-Mean Signals)

For zero-mean fluctuations `dF = F - <F>` with consecutive time lags:

| Order | Formula | Subtraction Terms |
|-------|---------|-------------------|
| 2 | `C2 = <dF(t) * dF(t+1)>` | None (equals auto-covariance) |
| 3 | `C3 = <dF(t) * dF(t+1) * dF(t+2)>` | None (equals 3rd central moment) |
| 4 | `C4 = M4 - M_{03}*M_{12} - M_{02}*M_{13} - M_{01}*M_{23}` | 3 pair-partition terms |
| 5 | `C5 = M5 - Sum_{10 (pair,triple)} M_pair * M_triple` | 10 partition terms |
| 6 | `C6 = M6 - 15*M4*M2 - 10*M3^2 + 30*M2^3` | 40 partition terms |

### Resolution Improvement Table

| Order | PSF Narrowing | Resolution Gain | Effective sigma |
|-------|--------------|-----------------|-----------------|
| 2 | U^2(r) | 1.41x | sigma / sqrt(2) |
| 3 | U^3(r) | 1.73x | sigma / sqrt(3) |
| 4 | U^4(r) | 2.00x | sigma / sqrt(4) |
| 5 | U^5(r) | 2.24x | sigma / sqrt(5) |
| 6 | U^6(r) | 2.45x | sigma / sqrt(6) |

### Processing Modes

| Mode | Pipeline | Resolution |
|------|----------|------------|
| Basic SOFI | Cumulant -> Linearize -> Normalize | sqrt(n)-fold |
| bSOFI | Cumulant -> Linearize -> Cross-cumulant corrections | sqrt(n)-fold, better SNR |
| SOFIX | Cumulant -> Fourier Interpolate -> Deconvolve -> Linearize | n-fold |

### QDot Blinking Model

Quantum dots exhibit fluorescence intermittency with power-law distributed on/off dwell times:

```
P(t_on)  ~ t^(-alpha_on)      alpha_on  ~ 1.5
P(t_off) ~ t^(-alpha_off)     alpha_off ~ 1.5
```

Sampled via the inverse CDF method: `t = t_min * (1 - u)^(-1/(alpha - 1))` where `u ~ Uniform(0, 1)`.

## Features

- **Cumulant computation** (orders 2--6) with correct moment-cumulant partition relations
- **Synthetic QDot simulator** with power-law blinking statistics and configurable noise
- **Fourier interpolation** for sub-pixel resolution enhancement (zero-padding upsampling)
- **Deconvolution** -- Wiener and Richardson-Lucy for SOFIX-level n-fold resolution
- **Linearization** -- nth-root correction for brightness nonlinearity (`|C_n|^(1/n)`)
- **Windowed processing** -- temporal windows for robustness against bleaching and drift
- **Web-based UI** with HTML5 Canvas rendering, colormap support, and real-time progress
- **WebSocket** streaming for live progress updates during computation
- **Swagger/ReDoc** auto-generated API documentation

## Project Structure

```
FASL_SOFI_QDOTS/
├── app/
│   ├── __init__.py
│   ├── main.py                          # FastAPI app entry point (port 8007)
│   ├── api/
│   │   ├── __init__.py
│   │   └── routes.py                    # REST + WebSocket endpoints
│   ├── simulation/
│   │   ├── __init__.py
│   │   ├── cumulants.py                 # Core SOFI cumulant engine (orders 2-6)
│   │   ├── emitter_simulator.py         # QDot blinking simulator (power-law)
│   │   ├── psf.py                       # PSF models (Gaussian, Airy, effective)
│   │   ├── deconvolution.py             # Wiener + Richardson-Lucy deconvolution
│   │   ├── fourier_interpolation.py     # Sub-pixel Fourier upsampling
│   │   └── sofi_pipeline.py             # Pipeline orchestrator (3 processing modes)
│   └── static/
│       ├── index.html                   # Main frontend page
│       ├── css/
│       │   └── style.css                # Application styles
│       └── js/
│           ├── app.js                   # Frontend application logic
│           ├── renderer.js              # Canvas image rendering + colormaps
│           └── websocket.js             # WebSocket client for progress
├── tests/
│   ├── __init__.py
│   ├── test_cumulants.py                # Cumulant computation validation
│   ├── test_emitter.py                  # Blinking simulator tests
│   └── test_pipeline.py                 # End-to-end pipeline tests
├── docs/
│   ├── architecture.md                  # System design documentation
│   ├── sofi_theory.md                   # Exhaustive mathematical foundation
│   ├── development_history.md           # Project evolution log
│   ├── references.md                    # 20+ academic references
│   └── svg/
│       ├── architecture.svg             # System architecture diagram
│       ├── sofi_pipeline.svg            # Processing pipeline flowchart
│       └── cumulant_orders.svg          # Cumulant order comparison
├── requirements.txt                     # Python dependencies
└── __init__.py
```

## API Documentation

### REST Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | Serve the frontend application |
| `GET` | `/health` | Health check (`{"status": "ok", "version": "2.0.0"}`) |
| `GET` | `/docs` | Swagger UI (auto-generated) |
| `GET` | `/redoc` | ReDoc documentation |
| `POST` | `/api/simulate` | Generate synthetic blinking data |
| `POST` | `/api/process` | Run SOFI cumulant pipeline |
| `GET` | `/api/state` | Current application state |

### WebSocket

| Path | Description |
|------|-------------|
| `WS /ws` | Real-time progress updates (`{"type": "progress", "step": "...", "progress": 0.0-1.0}`) |

### Simulation Parameters (`POST /api/simulate`)

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `num_frames` | int | 500 | 50--5000 | Number of time frames |
| `image_size` | int | 64 | 16--256 | Image size (square, pixels) |
| `num_emitters` | int | 20 | 1--200 | Number of QDot emitters |
| `psf_sigma` | float | 2.0 | 0.5--10.0 | PSF sigma (pixels) |
| `brightness` | float | 1000.0 | 100--10000 | Peak emitter brightness |
| `background` | float | 100.0 | 0--1000 | Background intensity |
| `noise_std` | float | 20.0 | 0--200 | Read noise standard deviation |
| `seed` | int | None | -- | Random seed for reproducibility |

### Processing Parameters (`POST /api/process`)

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `orders` | list[int] | [2, 3, 4] | Cumulant orders to compute (2--6) |
| `window_size` | int | 100 | Temporal window for cumulant accumulation |
| `use_fourier` | bool | false | Enable Fourier interpolation upsampling |
| `deconvolution` | str | "none" | Method: "none", "wiener", "richardson_lucy" |
| `linearize` | bool | true | Apply nth-root brightness linearization |
| `psf_sigma` | float | 2.0 | PSF sigma for deconvolution kernel |

### Pipeline Class (`SOFIPipeline`)

```python
from app.simulation.sofi_pipeline import SOFIPipeline

pipeline = SOFIPipeline(
    orders=[2, 3, 4],
    psf_sigma=2.0,
    use_fourier=True,
    deconvolution="wiener",
)
result = pipeline.process(image_stack)

# result.mean_image           -- widefield equivalent
# result.cumulant_images[n]   -- raw cumulant for order n
# result.sofi_images[n]       -- final SOFI super-resolution image
# result.interpolated_images  -- Fourier-interpolated intermediates
# result.deconvolved_images   -- deconvolution intermediates
```

## Running Tests

```bash
# Individual test modules
python tests/test_cumulants.py
python tests/test_pipeline.py
python tests/test_emitter.py

# Or run all tests
python -m pytest tests/ -v
```

Tests include:
- Statistical validation of cumulant formulas against known distributions
- End-to-end pipeline execution with resolution verification
- Emitter blinking statistics (power-law exponent validation)

## Tech Stack

- **Python 3.12+** -- Runtime
- **FastAPI 0.135+** -- ASGI web framework with auto-generated OpenAPI docs
- **NumPy 2.4+** -- Array computation and cumulant math
- **SciPy 1.17+** -- FFT for Fourier interpolation and deconvolution
- **Pydantic 2.12+** -- Request/response validation
- **Uvicorn 0.42+** -- ASGI server
- **tifffile** -- TIFF image I/O for microscopy data
- **HTML5 Canvas** -- Frontend image rendering with colormaps
- **WebSocket** -- Real-time progress streaming

## Documentation

- [SOFI Theory](docs/sofi_theory.md) -- Exhaustive mathematical foundation with derivations
- [System Architecture](docs/architecture.md) -- Component design and data flow
- [Development History](docs/development_history.md) -- Project evolution and decisions
- [References](docs/references.md) -- 20+ academic references (Dertinger, Geissbuehler, Basak, etc.)

## References

1. Dertinger, T. et al. (2009). Fast, background-free, 3D super-resolution optical fluctuation imaging (SOFI). *PNAS*, 106(52):22287-22292.
2. Geissbuehler, S. et al. (2012). Mapping molecular statistics with balanced SOFI (bSOFI). *Optical Nanoscopy*, 1:4.
3. Dertinger, T. et al. (2010). Achieving increased resolution with SOFI. *Optics Express*, 18(18):18875-18885.
4. Basak, R. et al. (2025). Super-resolution imaging of quantum dots. *Nature Photonics*, 19:229-237.
5. Kuno, M. et al. (2001). Fluorescence intermittency in single InP quantum dots. *JCP*, 115:1028.
6. Richardson, W.H. (1972). Bayesian-Based Iterative Method of Image Restoration. *JOSA*, 62(1):55-59.
7. Lucy, L.B. (1974). An iterative technique for the rectification of observed distributions. *AJ*, 79:745-754.

## License

Academic / Research use.
