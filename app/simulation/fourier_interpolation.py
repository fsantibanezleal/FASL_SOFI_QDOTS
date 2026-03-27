"""
Fourier Interpolation for Sub-pixel Resolution Enhancement.

===== THEORY =====

Fourier interpolation (also called sinc interpolation or zero-padding
interpolation) increases the spatial sampling of an image without
adding information beyond the original bandwidth. It is the
information-theoretically optimal interpolation for band-limited signals.

The method works by:
1. Computing the 2D FFT of the image
2. Embedding the spectrum in a larger array (zero-padding)
3. Computing the inverse FFT of the padded spectrum

This is equivalent to sinc interpolation in the spatial domain:

    f_interp(x) = Sum_n f[n] * sinc((x - n*dx) / dx)

where dx is the original pixel spacing.

===== APPLICATION IN SOFI =====

In standard SOFI, the nth-order cumulant narrows the PSF by sqrt(n),
but the pixel grid remains the same. The resolution improvement is
limited by the Nyquist sampling of the original pixels.

Fourier interpolation upsamples the cumulant image by factor n,
creating n*n sub-pixels for each original pixel. Combined with
the PSF narrowing from cumulants, this achieves true n-fold
resolution improvement (SOFIX approach).

The upsampling factor should match the cumulant order:
    Order 2: 2x upsampling -> 2x resolution (with deconvolution)
    Order 3: 3x upsampling -> 3x resolution
    Order n: nx upsampling -> nx resolution

===== IMPLEMENTATION NOTES =====

For even-sized arrays, the zero-padding must handle the Nyquist
frequency component correctly to avoid artifacts. The Nyquist
component is split equally between positive and negative frequencies.

For real-valued images, the spectrum has Hermitian symmetry:
    F(-k) = F*(k)

This symmetry is preserved by proper zero-padding.

References:
    - Dertinger et al. (2010), Opt. Express 18(18):18875
    - Geissbuehler et al. (2011), Biomed. Opt. Express 2(3):408-420
    - Oppenheim & Schafer (2009), Discrete-Time Signal Processing
"""

import numpy as np
from typing import Tuple, Optional


def fourier_interpolate(
    image: np.ndarray,
    factor: int = 2,
) -> np.ndarray:
    """Upsample an image by Fourier zero-padding interpolation.

    Increases the spatial sampling of the image by the given factor
    without adding frequency content beyond the original bandwidth.
    This is optimal for band-limited signals (which microscopy
    images are, due to the optical transfer function cutoff).

    The procedure:
    1. Compute 2D FFT of the input image.
    2. Create a larger frequency array (factor*H x factor*W).
    3. Place the original spectrum in the center.
    4. Compute the inverse FFT.
    5. Scale by factor^2 to preserve total energy.

    Edge effects are minimized by the implicit periodic boundary
    assumption of the DFT. For non-periodic images, consider
    applying a window function or mirroring before interpolation.

    Args:
        image: 2D input image of shape (H, W).
        factor: Integer upsampling factor (>= 1).
            factor=1 returns the original image.
            factor=2 doubles the resolution (4x pixels).
            factor=n creates n^2 times more pixels.

    Returns:
        2D interpolated image of shape (factor*H, factor*W).

    Raises:
        ValueError: If factor < 1.
    """
    if factor < 1:
        raise ValueError(f"Upsampling factor must be >= 1, got {factor}")

    if factor == 1:
        return image.copy()

    H, W = image.shape
    new_H, new_W = H * factor, W * factor

    # Forward FFT
    spectrum = np.fft.fft2(image)

    # Shift zero-frequency to center for easier manipulation
    spectrum = np.fft.fftshift(spectrum)

    # Create padded spectrum
    padded = np.zeros((new_H, new_W), dtype=complex)

    # Place original spectrum in center of padded array
    y_offset = (new_H - H) // 2
    x_offset = (new_W - W) // 2
    padded[y_offset : y_offset + H, x_offset : x_offset + W] = spectrum

    # Handle Nyquist frequency for even-sized arrays
    # Split Nyquist component to preserve Hermitian symmetry
    if H % 2 == 0:
        # The first row of the shifted spectrum is the Nyquist row
        padded[y_offset, x_offset : x_offset + W] *= 0.5
        padded[y_offset + H - 1, x_offset : x_offset + W] *= 0.5
        # Duplicate at symmetric position
        padded[y_offset - 1, x_offset : x_offset + W] = padded[
            y_offset, x_offset : x_offset + W
        ]

    if W % 2 == 0:
        padded[y_offset : y_offset + H, x_offset] *= 0.5
        padded[y_offset : y_offset + H, x_offset + W - 1] *= 0.5
        padded[y_offset : y_offset + H, x_offset - 1] = padded[
            y_offset : y_offset + H, x_offset
        ]

    # Shift back and inverse FFT
    padded = np.fft.ifftshift(padded)
    result = np.real(np.fft.ifft2(padded))

    # Scale to preserve energy/intensity levels
    result *= factor * factor

    return result


def fourier_interpolate_stack(
    images: np.ndarray,
    factor: int = 2,
) -> np.ndarray:
    """Upsample an image stack by Fourier interpolation.

    Applies Fourier interpolation to each frame independently.
    Useful for upsampling the raw image stack before cumulant
    computation (alternative approach to post-cumulant interpolation).

    Note: For SOFI, it is generally better to compute cumulants
    on the original grid and then interpolate, as this avoids
    amplifying noise in the upsampled stack.

    Args:
        images: 3D array (T, H, W) of image frames.
        factor: Integer upsampling factor.

    Returns:
        3D array (T, factor*H, factor*W) of interpolated frames.
    """
    T, H, W = images.shape
    new_H, new_W = H * factor, W * factor
    result = np.zeros((T, new_H, new_W), dtype=images.dtype)

    for t in range(T):
        result[t] = fourier_interpolate(images[t], factor)

    return result


def compute_resolution_gain(
    original_psf_sigma: float,
    order: int,
    with_interpolation: bool = True,
) -> dict:
    """Compute the theoretical resolution improvement for SOFI.

    Calculates the effective PSF width and resolution gain for
    different SOFI processing strategies.

    Three scenarios:
    1. Cumulant only: PSF narrows by sqrt(n), no pixel improvement.
       Effective resolution gain: sqrt(n) (if well-sampled).

    2. Cumulant + Fourier interpolation: PSF narrows by sqrt(n),
       pixel grid refined by n. Effective gain: sqrt(n) to n
       depending on deconvolution.

    3. Cumulant + interpolation + deconvolution (SOFIX):
       Full n-fold resolution improvement.

    Args:
        original_psf_sigma: PSF sigma in pixels.
        order: SOFI cumulant order.
        with_interpolation: Include Fourier interpolation.

    Returns:
        Dictionary with resolution metrics:
            - original_sigma: original PSF sigma
            - effective_sigma: SOFI effective sigma
            - psf_narrowing: sqrt(n) factor
            - pixel_factor: interpolation factor (1 or n)
            - max_theoretical_gain: maximum achievable gain
    """
    psf_narrowing = np.sqrt(order)
    effective_sigma = original_psf_sigma / psf_narrowing
    pixel_factor = order if with_interpolation else 1

    return {
        "original_sigma": original_psf_sigma,
        "effective_sigma": effective_sigma,
        "psf_narrowing": psf_narrowing,
        "pixel_factor": pixel_factor,
        "max_theoretical_gain": float(order) if with_interpolation else psf_narrowing,
        "original_fwhm": original_psf_sigma * 2.355,
        "effective_fwhm": effective_sigma * 2.355,
    }
