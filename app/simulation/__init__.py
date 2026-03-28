"""
SOFI Simulation and Processing Modules.

This package contains the core computational engines for:
- Cumulant computation (orders 2-6)
- Point Spread Function models
- Deconvolution algorithms (Wiener, Richardson-Lucy)
- Fourier interpolation for sub-pixel resolution
- Synthetic blinking emitter generation
- Full SOFI processing pipeline orchestration
"""

from .cumulants import compute_cumulant, compute_sofi_image
from .emitter_simulator import simulate_blinking_sequence, BlinkingEmitter
from .psf import gaussian_psf, airy_psf
from .deconvolution import wiener_deconvolution, richardson_lucy
from .fourier_interpolation import fourier_interpolate
from .sofi_pipeline import SOFIPipeline
from .mssr import compute_mssr, compute_temporal_mssr

__all__ = [
    "compute_cumulant",
    "compute_sofi_image",
    "simulate_blinking_sequence",
    "BlinkingEmitter",
    "gaussian_psf",
    "airy_psf",
    "wiener_deconvolution",
    "richardson_lucy",
    "fourier_interpolate",
    "SOFIPipeline",
    "compute_mssr",
    "compute_temporal_mssr",
]
