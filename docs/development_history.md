# Development History

## Project History

### Origins (2012-2014)

MATLAB implementation at FASL (Fluorescence and Spectroscopy Laboratory) for analyzing quantum dot fluorescence fluctuations in widefield microscopy. The original codebase implemented:

- **SOFI cumulant analysis** (orders 2-6) with auto-cumulant and cross-cumulant support
- **SOFIX Fourier deconvolution** enhancement for achieving n-fold resolution improvement
- **PSF calculation** via Fresnel propagation and dipole emission models
- **QDot spectral analysis** including Power Spectral Density (PSD) and Lomb-Scargle periodograms
- **Blinking statistics** extraction with power-law fitting for on/off time distributions
- **Monte Carlo emitter simulation** for validating algorithms against ground truth

The MATLAB implementation processed experimental data from CdSe/ZnS quantum dots imaged with a custom widefield fluorescence microscope (100x oil, NA 1.4, 532 nm excitation).

### Key Results

The original MATLAB pipeline demonstrated:
- 2nd-order SOFI achieving 1.4x resolution improvement on QDot clusters
- 4th-order SOFI resolving features separated by ~120 nm (below the 232 nm diffraction limit)
- Power-law blinking exponents of alpha_on ~ 1.5 and alpha_off ~ 1.6 for CdSe/ZnS QDots
- Successful application to biological samples labeled with QDot conjugates

### v2.0.0 (2026-03-27) -- Complete Python Rewrite

Comprehensive rewrite from MATLAB to a modern Python 3.12 / FastAPI web application:

**Architecture:**
- FastAPI backend serving REST API and WebSocket endpoints
- NumPy-vectorized cumulant computation (orders 2-6)
- Modular pipeline: cumulants, PSF, deconvolution, Fourier interpolation
- Pydantic models for API validation
- Canvas-based frontend with colormap rendering

**New Features:**
- Synthetic quantum dot blinking simulator with power-law statistics
- Real-time processing progress via WebSocket
- Interactive parameter adjustment through web UI
- Multiple deconvolution methods (Wiener, Richardson-Lucy)
- Fourier zero-padding interpolation for sub-pixel resolution
- Comprehensive test suite with statistical validation
- Exhaustive mathematical documentation

**Technical Stack:**
- Python 3.12+
- FastAPI + Uvicorn (ASGI server)
- NumPy + SciPy (numerical computation)
- Pydantic (data validation)
- WebSocket (real-time communication)
- HTML5 Canvas (image rendering)

### Mathematical Model

The core SOFI computation follows the cumulant theory:

**Signal Model:**
```
F(r, t) = Sum_k eps_k * s_k(t) * U(r - r_k)
```

**nth-order Cumulant:**
```
C_n(r) = Sum_k eps_k^n * kappa_n[s_k] * U^n(r - r_k)
```

**Effective PSF Width:**
```
sigma_eff = sigma_PSF / sqrt(n)
```

**Implemented Cumulant Formulas (consecutive lags):**

- C2 = mean(dF[t] * dF[t+1])
- C3 = mean(dF[t] * dF[t+1] * dF[t+2])
- C4 = M4 - M(0,3)*M(1,2) - M(0,2)*M(1,3) - M(0,1)*M(2,3)
- C5 = M5 - Sum_{10 terms} M_pair * M_triple
- C6 = M6 - Sum_{15 pair-quartet} - Sum_{10 triple-triple} + 2*Sum_{15 pair-pair-pair}

### Architecture

```
[Frontend (HTML/JS/Canvas)]
        |
        | HTTP / WebSocket
        v
[FastAPI Backend (port 8007)]
        |
        +-- /api/simulate --> EmitterSimulator
        +-- /api/process  --> SOFIPipeline
        +-- /ws           --> ProgressUpdates
        |
        v
[Simulation Engine]
   +-- cumulants.py          (core computation)
   +-- emitter_simulator.py  (synthetic data)
   +-- psf.py                (PSF models)
   +-- deconvolution.py      (Wiener / R-L)
   +-- fourier_interpolation.py  (upsampling)
   +-- sofi_pipeline.py      (orchestration)
```
