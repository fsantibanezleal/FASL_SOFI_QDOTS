# Architecture

## Overview

FASL SOFI QDOTS is a client-server web application for Super-resolution Optical Fluctuation Imaging (SOFI) analysis of quantum dot fluorescence data.

## System Architecture

```
+---------------------------+      +---------------------------+
|       Frontend            |      |       Backend             |
|  (HTML5 / CSS / JS)       | HTTP |  (FastAPI / Python)       |
|                           |<---->|                           |
|  - Canvas rendering       |  WS  |  - REST API               |
|  - Colormap support       |      |  - WebSocket progress     |
|  - Parameter controls     |      |  - Simulation engine      |
|  - Progress display       |      |  - SOFI pipeline          |
+---------------------------+      +---------------------------+
                                            |
                                            v
                              +---------------------------+
                              |   Simulation Engine       |
                              |                           |
                              |  cumulants.py             |
                              |  emitter_simulator.py     |
                              |  psf.py                   |
                              |  deconvolution.py         |
                              |  fourier_interpolation.py |
                              |  sofi_pipeline.py         |
                              +---------------------------+
```

## Module Responsibilities

### app/main.py
- FastAPI application factory
- Static file serving
- Route registration
- Health check endpoint

### app/api/routes.py
- POST /api/simulate: Generate synthetic blinking data
- POST /api/process: Run SOFI cumulant pipeline
- GET /api/state: Query current application state
- WS /ws: Real-time progress WebSocket

### app/simulation/cumulants.py
- Core cumulant computation engine
- Orders 2-6 with correct moment-cumulant relations
- Windowed processing with accumulation
- Optional linearization (nth root)

### app/simulation/emitter_simulator.py
- Quantum dot blinking model (power-law on/off times)
- Gaussian PSF convolution
- Poisson shot noise + Gaussian read noise
- Configurable emitter positions and brightness

### app/simulation/psf.py
- Gaussian PSF model
- Airy disk PSF model (Bessel function)
- Effective SOFI PSF computation
- FWHM measurement utility

### app/simulation/deconvolution.py
- Wiener deconvolution (frequency domain)
- Richardson-Lucy iterative deconvolution
- SOFI-specific deconvolution with effective PSF

### app/simulation/fourier_interpolation.py
- Zero-padding Fourier interpolation
- Stack interpolation
- Resolution gain calculation

### app/simulation/sofi_pipeline.py
- Pipeline orchestration (SOFIPipeline class)
- Result container (SOFIResult dataclass)
- Progress callback support
- Configurable processing modes

## Data Flow

1. **Simulation**: User sets parameters -> API generates blinking stack -> Mean image displayed
2. **Processing**: User selects orders -> API computes cumulants -> SOFI images displayed
3. **Progress**: Backend sends WebSocket messages -> Frontend updates progress bar

## Image Data Transfer

Images are transferred as base64-encoded float32 arrays with shape metadata. The frontend decodes the binary data and applies colormaps via Canvas ImageData.

## Port Configuration

The application runs on port **8007** by default.

## Related Documents

- `docs/user_guide.md` — end-user walkthrough, recipes, troubleshooting
- `docs/sofi_theory.md` — mathematical foundation (cumulants, moments, bSOFI)
- `docs/references.md` — primary literature (Dertinger, Geissbuehler, Basak, ...)
- `docs/svg/optical_setup.svg` — widefield microscope diagram with physical scales
- `docs/svg/fluctuation_analysis.svg` — trace → lagged products → cumulant map
