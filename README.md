# FASL SOFI QDOTS

Super-resolution Optical Fluctuation Imaging (SOFI) web application for quantum dot fluorescence analysis.

## Overview

SOFI extracts sub-diffraction spatial information from temporal fluorescence fluctuations of independently blinking emitters (quantum dots). The nth-order cumulant of intensity time traces narrows the effective PSF by a factor of sqrt(n), achieving super-resolution without single-molecule sparsity requirements.

## Features

- **Cumulant computation** (orders 2-6) with correct moment-cumulant relations
- **Synthetic QDot simulator** with power-law blinking statistics
- **Fourier interpolation** for sub-pixel resolution enhancement
- **Deconvolution** (Wiener and Richardson-Lucy) for SOFIX-level resolution
- **Web-based UI** with canvas rendering, colormaps, and real-time progress
- **Comprehensive test suite** with statistical validation

## Quick Start

```bash
cd FASL_SOFI_QDOTS
python -m venv .venv
source .venv/Scripts/activate  # Windows
pip install -r requirements.txt
python -m uvicorn app.main:app --port 8007
```

Open http://localhost:8007 in your browser.

## Architecture

```
app/
  main.py                     FastAPI application (port 8007)
  api/routes.py               REST + WebSocket endpoints
  simulation/
    cumulants.py              Core SOFI cumulant engine (orders 2-6)
    emitter_simulator.py      QDot blinking simulator
    psf.py                    PSF models (Gaussian, Airy)
    deconvolution.py          Wiener + Richardson-Lucy
    fourier_interpolation.py  Sub-pixel upsampling
    sofi_pipeline.py          Pipeline orchestration
  static/                     Frontend (HTML/CSS/JS)
tests/                        Test suite
docs/                         Theory, architecture, references
```

## Resolution Improvement

| Order | PSF Narrowing | Resolution Gain |
|-------|--------------|-----------------|
| 2     | U^2(r)       | 1.41x           |
| 3     | U^3(r)       | 1.73x           |
| 4     | U^4(r)       | 2.00x           |
| 5     | U^5(r)       | 2.24x           |
| 6     | U^6(r)       | 2.45x           |

## Running Tests

```bash
python tests/test_cumulants.py
python tests/test_pipeline.py
python tests/test_emitter.py
```

## Documentation

- [SOFI Theory](docs/sofi_theory.md) - Exhaustive mathematical foundation
- [Architecture](docs/architecture.md) - System design
- [Development History](docs/development_history.md) - Project evolution
- [References](docs/references.md) - 20+ academic references

## Tech Stack

- Python 3.12+, FastAPI, NumPy, SciPy, Pydantic
- HTML5 Canvas with colormap rendering
- WebSocket for real-time progress
