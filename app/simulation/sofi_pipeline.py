"""
SOFI Processing Pipeline Orchestrator.

===== PIPELINE OVERVIEW =====

The complete SOFI processing pipeline transforms a fluorescence
time-lapse image stack into super-resolution images through the
following stages:

    1. Input Validation & Preprocessing
       - Validate image stack dimensions
       - Optional background subtraction
       - Optional photobleaching correction

    2. Cumulant Computation (orders 2-6)
       - Temporal mean subtraction
       - Windowed cumulant accumulation
       - Multiple orders computed in parallel

    3. Fourier Interpolation (optional)
       - Zero-padding upsampling by factor n for order n
       - Achieves sub-pixel resolution

    4. Deconvolution (optional)
       - Wiener or Richardson-Lucy
       - Uses effective PSF U^n(r)
       - Achieves n-fold resolution (SOFIX)

    5. Linearization
       - nth root to correct brightness nonlinearity
       - |C_n|^(1/n) gives linear brightness

    6. Normalization & Output
       - Normalize to [0, 1] or [0, 255]
       - Generate comparison images

===== PROCESSING MODES =====

Mode 1 - Basic SOFI:
    Cumulant -> Linearize -> Normalize
    Resolution: sqrt(n)-fold

Mode 2 - bSOFI (balanced SOFI):
    Cumulant -> Linearize -> Cross-cumulant corrections
    Resolution: sqrt(n)-fold, better SNR

Mode 3 - SOFIX (extended SOFI):
    Cumulant -> Fourier Interpolate -> Deconvolve -> Linearize
    Resolution: n-fold

References:
    - Dertinger et al. (2009), PNAS 106(52):22287-22292
    - Geissbuehler et al. (2012), Optical Nanoscopy 1:4
    - Dertinger et al. (2010), Opt. Express 18(18):18875
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Any

from .cumulants import compute_cumulant, compute_sofi_image
from .psf import gaussian_psf, sofi_effective_psf
from .deconvolution import wiener_deconvolution, richardson_lucy, deconvolve_sofi
from .fourier_interpolation import fourier_interpolate


@dataclass
class SOFIResult:
    """Container for SOFI processing results.

    Stores the output images and metadata from a SOFI pipeline run.

    Attributes:
        mean_image: Temporal mean of the input stack (widefield equivalent).
        cumulant_images: Dict mapping order -> raw cumulant image.
        sofi_images: Dict mapping order -> processed SOFI image.
        interpolated_images: Dict mapping order -> Fourier-interpolated image.
        deconvolved_images: Dict mapping order -> deconvolved image.
        metadata: Processing parameters and statistics.
    """

    mean_image: np.ndarray = field(default_factory=lambda: np.array([]))
    cumulant_images: Dict[int, np.ndarray] = field(default_factory=dict)
    sofi_images: Dict[int, np.ndarray] = field(default_factory=dict)
    interpolated_images: Dict[int, np.ndarray] = field(default_factory=dict)
    deconvolved_images: Dict[int, np.ndarray] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


class SOFIPipeline:
    """Complete SOFI processing pipeline.

    Orchestrates all processing steps from raw image stack to
    super-resolution output images. Supports multiple cumulant
    orders, optional Fourier interpolation, and deconvolution.

    Usage:
        pipeline = SOFIPipeline(
            orders=[2, 3, 4],
            psf_sigma=2.0,
            use_fourier=True,
            deconvolution="wiener",
        )
        result = pipeline.process(image_stack)

    The pipeline reports progress via an optional callback function,
    which receives (step_name, progress_fraction) tuples.

    Attributes:
        orders: List of cumulant orders to compute.
        window_size: Temporal window for cumulant computation.
        psf_sigma: PSF sigma for deconvolution.
        use_fourier: Whether to apply Fourier interpolation.
        deconvolution: Deconvolution method ("none", "wiener", "richardson_lucy").
        linearize: Whether to apply nth-root linearization.
        deconv_params: Additional parameters for deconvolution.
    """

    def __init__(
        self,
        orders: Optional[List[int]] = None,
        window_size: int = 100,
        psf_sigma: float = 2.0,
        use_fourier: bool = False,
        deconvolution: str = "none",
        linearize: bool = True,
        deconv_params: Optional[Dict[str, Any]] = None,
    ):
        """Initialize the SOFI pipeline.

        Args:
            orders: Cumulant orders to compute. Default [2, 3, 4].
            window_size: Frames per temporal window for cumulant
                accumulation. Larger = better SNR, more drift sensitivity.
            psf_sigma: Gaussian PSF sigma in pixels. Used for
                deconvolution effective PSF computation.
            use_fourier: Enable Fourier interpolation upsampling.
            deconvolution: Method - "none", "wiener", or "richardson_lucy".
            linearize: Apply nth-root brightness linearization.
            deconv_params: Extra params for deconvolution (e.g., snr, iterations).
        """
        self.orders = orders or [2, 3, 4]
        self.window_size = window_size
        self.psf_sigma = psf_sigma
        self.use_fourier = use_fourier
        self.deconvolution = deconvolution
        self.linearize = linearize
        self.deconv_params = deconv_params or {}

        # Validate orders
        for order in self.orders:
            if order < 2 or order > 6:
                raise ValueError(f"Cumulant order must be 2-6, got {order}")

    def process(
        self,
        images: np.ndarray,
        progress_callback: Optional[Callable[[str, float], None]] = None,
    ) -> SOFIResult:
        """Run the complete SOFI pipeline on an image stack.

        Processes the image stack through all pipeline stages and
        returns a SOFIResult containing all intermediate and final
        images.

        Args:
            images: 3D array (T, H, W) of fluorescence frames.
            progress_callback: Optional function called with
                (step_description, fraction_complete) for progress reporting.
                fraction_complete ranges from 0.0 to 1.0.

        Returns:
            SOFIResult with all computed images and metadata.

        Raises:
            ValueError: If images have wrong shape or too few frames.
        """
        if images.ndim != 3:
            raise ValueError(f"Expected 3D image stack, got {images.ndim}D")

        T, H, W = images.shape
        min_frames = max(self.orders) + 1
        if T < min_frames:
            raise ValueError(
                f"Need at least {min_frames} frames for orders {self.orders}, got {T}"
            )

        result = SOFIResult()
        result.metadata = {
            "num_frames": T,
            "image_size": (H, W),
            "orders": list(self.orders),
            "window_size": self.window_size,
            "psf_sigma": self.psf_sigma,
            "use_fourier": self.use_fourier,
            "deconvolution": self.deconvolution,
            "linearize": self.linearize,
        }

        total_steps = len(self.orders) * (
            1 + int(self.use_fourier) + int(self.deconvolution != "none")
        ) + 1  # +1 for mean image
        current_step = 0

        def _report(msg: str):
            nonlocal current_step
            current_step += 1
            if progress_callback:
                progress_callback(msg, current_step / total_steps)

        # Step 1: Mean image (widefield equivalent)
        images_f64 = images.astype(np.float64)
        result.mean_image = np.mean(images_f64, axis=0)
        _report("Computed mean image")

        # Precompute PSF for deconvolution
        psf_size = int(6 * self.psf_sigma) | 1
        psf = gaussian_psf(psf_size, self.psf_sigma)

        # Step 2-4: Process each order
        for order in self.orders:
            # Cumulant computation
            cum = compute_sofi_image(
                images_f64, order,
                window_size=self.window_size,
                linearize=False,  # We'll linearize later if needed
            )
            result.cumulant_images[order] = cum
            _report(f"Computed order-{order} cumulant")

            # Working image for further processing
            working = cum.copy()

            # Fourier interpolation
            if self.use_fourier:
                working = fourier_interpolate(working, factor=order)
                result.interpolated_images[order] = working.copy()
                _report(f"Fourier interpolated order-{order}")

            # Deconvolution
            if self.deconvolution != "none":
                # Resize PSF if interpolated
                if self.use_fourier:
                    interp_psf_size = int(6 * self.psf_sigma * order) | 1
                    interp_psf = gaussian_psf(
                        interp_psf_size, self.psf_sigma * order
                    )
                    eff_psf = sofi_effective_psf(interp_psf, order)
                else:
                    eff_psf = sofi_effective_psf(psf, order)

                if self.deconvolution == "wiener":
                    snr = self.deconv_params.get("snr", 30.0)
                    working = wiener_deconvolution(working, eff_psf, snr=snr)
                elif self.deconvolution == "richardson_lucy":
                    iters = self.deconv_params.get("iterations", 20)
                    working = richardson_lucy(working, eff_psf, iterations=iters)

                result.deconvolved_images[order] = working.copy()
                _report(f"Deconvolved order-{order}")

            # Linearization and normalization
            if self.linearize and order > 1:
                working = np.abs(working)
                working = np.power(np.maximum(working, 0), 1.0 / order)

            # Normalize to [0, 1]
            vmin, vmax = working.min(), working.max()
            if vmax > vmin:
                working = (working - vmin) / (vmax - vmin)

            result.sofi_images[order] = working

        if progress_callback:
            progress_callback("Pipeline complete", 1.0)

        return result

    def get_config(self) -> Dict[str, Any]:
        """Return the pipeline configuration as a dictionary.

        Returns:
            Dictionary of all pipeline parameters.
        """
        return {
            "orders": list(self.orders),
            "window_size": self.window_size,
            "psf_sigma": self.psf_sigma,
            "use_fourier": self.use_fourier,
            "deconvolution": self.deconvolution,
            "linearize": self.linearize,
            "deconv_params": dict(self.deconv_params),
        }
