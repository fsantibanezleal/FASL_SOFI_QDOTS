"""
Deconvolution Algorithms for SOFI Enhancement.

===== DECONVOLUTION IN SOFI =====

After computing cumulant images, deconvolution can further enhance
resolution by compensating for the residual PSF. Two approaches
are commonly used:

1. Wiener Deconvolution (frequency domain):
   Linear, fast, but requires PSF knowledge and noise estimate.

2. Richardson-Lucy Deconvolution (iterative):
   Non-linear, preserves positivity, based on Bayesian estimation.

===== SOFIX (SOFI WITH DECONVOLUTION) =====

SOFIX combines nth-order cumulant computation with deconvolution
using the known effective PSF U^n(r). This achieves resolution
improvement of n-fold (rather than sqrt(n)-fold from cumulants alone)
when combined with Fourier interpolation.

===== WIENER DECONVOLUTION =====

The Wiener filter minimizes the mean squared error between the
estimated and true object:

    F_hat(k) = H*(k) / (|H(k)|^2 + 1/SNR(k)) * G(k)

where:
    G(k) = Fourier transform of the observed image
    H(k) = Optical Transfer Function (FT of PSF)
    H*(k) = complex conjugate of H(k)
    SNR(k) = signal-to-noise ratio (often assumed constant)

The regularization parameter 1/SNR prevents noise amplification
at frequencies where the OTF is small.

===== RICHARDSON-LUCY DECONVOLUTION =====

The R-L algorithm maximizes the Poisson likelihood iteratively:

    f^(k+1) = f^(k) * [h_flip * (g / (h * f^(k)))]

where:
    f^(k) = current estimate of the true image
    g = observed image
    h = PSF
    h_flip = PSF flipped (for correlation)
    * denotes convolution

This algorithm:
- Preserves non-negativity
- Conserves total flux
- Converges to the maximum likelihood estimate for Poisson noise
- Can be regularized by early stopping to prevent noise amplification

References:
    - Dertinger et al. (2010), Opt. Express 18(18):18875
    - Lucy (1974), Astronomical Journal 79:745
    - Richardson (1972), JOSA 62(1):55-59
    - Wiener (1949), Extrapolation, Interpolation, and Smoothing
"""

import numpy as np
from scipy.signal import fftconvolve
from typing import Optional


def wiener_deconvolution(
    image: np.ndarray,
    psf: np.ndarray,
    snr: float = 30.0,
) -> np.ndarray:
    """Perform Wiener deconvolution on an image.

    Applies the Wiener filter in the Fourier domain to deconvolve
    the image with the given PSF. The SNR parameter controls the
    regularization strength.

    The Wiener filter transfer function is:

        W(k) = H*(k) / (|H(k)|^2 + 1/SNR)

    where H(k) = FT{PSF} is the Optical Transfer Function.

    Higher SNR values give sharper results but may amplify noise.
    Lower SNR values give smoother results with less noise.

    Args:
        image: 2D input image to deconvolve.
        psf: 2D Point Spread Function (should be normalized).
            Does not need to be the same size as the image;
            it will be zero-padded to match.
        snr: Signal-to-noise ratio estimate (linear, not dB).
            Typical values: 10-100 for fluorescence microscopy.
            Default 30.0 is a good starting point.

    Returns:
        2D deconvolved image (same shape as input).
    """
    # Pad PSF to image size and center it
    psf_padded = np.zeros_like(image)
    ph, pw = psf.shape
    cy, cx = image.shape[0] // 2, image.shape[1] // 2
    py, px = ph // 2, pw // 2

    # Place PSF centered in the padded array
    y_start = cy - py
    x_start = cx - px
    psf_padded[y_start : y_start + ph, x_start : x_start + pw] = psf

    # Shift PSF so center is at (0,0) for correct FFT convolution
    psf_padded = np.fft.ifftshift(psf_padded)

    # Compute FFTs
    G = np.fft.fft2(image)
    H = np.fft.fft2(psf_padded)

    # Wiener filter
    H_conj = np.conj(H)
    H_sq = np.abs(H) ** 2
    wiener_filter = H_conj / (H_sq + 1.0 / snr)

    # Apply filter and inverse FFT
    F_hat = wiener_filter * G
    result = np.real(np.fft.ifft2(F_hat))

    return result


def richardson_lucy(
    image: np.ndarray,
    psf: np.ndarray,
    iterations: int = 20,
    clip: bool = True,
) -> np.ndarray:
    """Perform Richardson-Lucy iterative deconvolution.

    The R-L algorithm iteratively refines the image estimate using
    the multiplicative update rule:

        f^(k+1) = f^(k) * conv(h_flip, g / conv(h, f^(k)))

    where conv denotes convolution. This converges to the maximum
    likelihood estimate under Poisson noise statistics.

    The algorithm naturally preserves:
    - Non-negativity of the estimate
    - Total flux conservation
    - Poisson noise characteristics

    Early stopping acts as implicit regularization: too many
    iterations amplify noise (ringing artifacts), while too few
    leave residual blur.

    Typical iteration counts:
        - 5-15: moderate deconvolution, low noise amplification
        - 20-50: stronger deconvolution, some noise amplification
        - 50+: aggressive, requires good SNR

    Args:
        image: 2D input image to deconvolve. Should be non-negative.
        psf: 2D Point Spread Function (normalized to sum to 1).
        iterations: Number of R-L iterations.
            Default 20 is a good balance for SOFI images.
        clip: If True, clip negative values to 0 at each iteration.

    Returns:
        2D deconvolved image (same shape as input).
    """
    # Ensure non-negative input
    image = np.maximum(image, 1e-12)

    # PSF and flipped PSF for correlation
    psf_flip = psf[::-1, ::-1]

    # Initialize estimate with the input image
    estimate = image.copy()

    for _ in range(iterations):
        # Forward model: convolve estimate with PSF
        blurred = fftconvolve(estimate, psf, mode="same")
        blurred = np.maximum(blurred, 1e-12)  # prevent division by zero

        # Ratio of observed to predicted
        ratio = image / blurred

        # Correction factor: correlate ratio with PSF
        correction = fftconvolve(ratio, psf_flip, mode="same")

        # Multiplicative update
        estimate = estimate * correction

        if clip:
            estimate = np.maximum(estimate, 0)

    return estimate


def deconvolve_sofi(
    cumulant_image: np.ndarray,
    psf: np.ndarray,
    order: int,
    method: str = "wiener",
    **kwargs,
) -> np.ndarray:
    """Deconvolve a SOFI cumulant image using the effective PSF.

    For an nth-order SOFI cumulant, the effective PSF is U^n(r).
    This function computes the effective PSF and applies the
    chosen deconvolution method.

    This is the key step in SOFIX (extended SOFI), which achieves
    n-fold resolution improvement by:
    1. Computing the nth-order cumulant (narrows PSF by sqrt(n))
    2. Deconvolving with U^n (removes remaining blur)
    3. The result has resolution limited only by pixel sampling

    Args:
        cumulant_image: 2D cumulant image from compute_cumulant().
        psf: 2D original PSF of the imaging system.
        order: SOFI cumulant order (used to compute U^n).
        method: Deconvolution method - "wiener" or "richardson_lucy".
        **kwargs: Additional keyword arguments passed to the
            deconvolution function (e.g., snr, iterations).

    Returns:
        2D deconvolved cumulant image.

    Raises:
        ValueError: If method is not recognized.
    """
    # Compute effective PSF: U^n
    eff_psf = np.power(np.maximum(psf, 0), order)
    total = eff_psf.sum()
    if total > 0:
        eff_psf /= total

    if method == "wiener":
        return wiener_deconvolution(cumulant_image, eff_psf, **kwargs)
    elif method == "richardson_lucy":
        return richardson_lucy(cumulant_image, eff_psf, **kwargs)
    else:
        raise ValueError(
            f"Unknown deconvolution method: {method}. "
            f"Use 'wiener' or 'richardson_lucy'."
        )
