"""
Point Spread Function (PSF) Models.

===== OPTICAL BACKGROUND =====

The Point Spread Function describes the response of an imaging system
to a point source. In fluorescence microscopy, the PSF determines the
spatial extent of each emitter's image and thus the diffraction limit.

For an ideal circular aperture, the PSF is the Airy pattern:

    I(r) = I_0 * [2 * J_1(k*NA*r) / (k*NA*r)]^2

where:
    J_1   = Bessel function of the first kind, order 1
    k     = 2*pi / lambda (wavenumber)
    NA    = numerical aperture of the objective
    r     = radial distance from the optical axis

The first zero of the Airy pattern defines the Rayleigh resolution:

    r_Rayleigh = 0.61 * lambda / NA

===== GAUSSIAN APPROXIMATION =====

The Airy pattern is commonly approximated by a 2D Gaussian:

    U(x, y) = exp(-(x^2 + y^2) / (2*sigma^2))

with sigma chosen to match the Airy pattern:

    sigma ~ 0.21 * lambda / NA    (matching the FWHM)

    or equivalently:

    FWHM = 2 * sqrt(2*ln(2)) * sigma ~ 2.355 * sigma

This approximation is valid within the central lobe and simplifies
analytical calculations, especially for SOFI where U^n is needed.

===== SOFI PSF NARROWING =====

When computing the nth-order cumulant, the effective PSF becomes:

    U_eff(r) = U^n(r) = exp(-n * r^2 / (2*sigma^2))

This is a Gaussian with effective sigma:

    sigma_eff = sigma / sqrt(n)

giving a resolution improvement of sqrt(n) in each dimension.

References:
    - Born & Wolf (2019), Principles of Optics, 7th ed.
    - Zhang et al. (2007), Appl. Opt. 46(10):1819-1829
    - Dertinger et al. (2009), PNAS 106(52):22287-22292
"""

import numpy as np
from scipy.special import j1
from typing import Optional, Tuple


def gaussian_psf(
    size: int,
    sigma: float,
    normalize: bool = True,
) -> np.ndarray:
    """Generate a 2D Gaussian Point Spread Function.

    Creates a symmetric 2D Gaussian kernel centered in the array.
    This is the standard PSF model for SOFI analysis.

    The Gaussian PSF:
        U(x, y) = A * exp(-(x^2 + y^2) / (2*sigma^2))

    where A is chosen so that the PSF sums to 1 (if normalized)
    or has peak value 1 (if not normalized).

    Args:
        size: Side length of the output array. Should be odd for
            symmetric centering. If even, it will be used as-is.
        sigma: Standard deviation of the Gaussian in pixels.
            Typical values for microscopy:
                - 1.0-2.0 pixels: well-sampled (Nyquist)
                - 2.0-4.0 pixels: oversampled
                - < 1.0 pixels: undersampled (aliasing risk)
        normalize: If True, PSF sums to 1 (energy conservation).
            If False, peak value is 1.

    Returns:
        2D array of shape (size, size) containing the PSF.
    """
    x = np.arange(size, dtype=np.float64) - size // 2
    xx, yy = np.meshgrid(x, x)
    psf = np.exp(-(xx**2 + yy**2) / (2 * sigma**2))

    if normalize:
        psf /= psf.sum()
    else:
        psf /= psf.max()

    return psf


def airy_psf(
    size: int,
    wavelength: float = 0.532,
    na: float = 1.4,
    pixel_size: float = 0.1,
    normalize: bool = True,
) -> np.ndarray:
    """Generate a 2D Airy disk Point Spread Function.

    The Airy pattern is the exact PSF for a circular aperture:

        I(r) = [2 * J_1(v) / v]^2

    where v = (2*pi/lambda) * NA * r is the reduced optical coordinate.

    At v=0 we use the limit: J_1(v)/v -> 1/2, so I(0) = 1.

    The Rayleigh criterion places the first zero at:
        r_Rayleigh = 0.61 * lambda / NA

    Args:
        size: Side length of the output array in pixels.
        wavelength: Emission wavelength in micrometers.
            Typical values: 0.488 (GFP), 0.532 (QDot 525),
            0.585 (QDot 585), 0.620 (QDot 625).
        na: Numerical aperture of the objective lens.
            Typical values: 0.4-0.9 (air), 1.0-1.45 (oil).
        pixel_size: Physical pixel size in micrometers.
            Determines the spatial sampling of the PSF.
        normalize: If True, PSF sums to 1.

    Returns:
        2D array of shape (size, size) containing the Airy PSF.
    """
    x = (np.arange(size, dtype=np.float64) - size // 2) * pixel_size
    xx, yy = np.meshgrid(x, x)
    r = np.sqrt(xx**2 + yy**2)

    # Reduced optical coordinate
    k = 2.0 * np.pi / wavelength
    v = k * na * r

    # Compute Airy pattern with limit handling at v=0
    # J_1(v)/v -> 1/2 as v -> 0, so [2*J_1(v)/v]^2 -> 1
    with np.errstate(divide="ignore", invalid="ignore"):
        airy = np.where(v == 0, 1.0, (2.0 * j1(v) / v) ** 2)

    if normalize:
        airy /= airy.sum()
    else:
        airy /= airy.max()

    return airy


def sofi_effective_psf(
    psf: np.ndarray,
    order: int,
    normalize: bool = True,
) -> np.ndarray:
    """Compute the effective PSF for nth-order SOFI.

    The nth-order cumulant effectively raises the PSF to the nth power:

        U_eff(r) = U(r)^n

    For a Gaussian PSF with width sigma, this produces a Gaussian
    with width sigma/sqrt(n), giving sqrt(n) resolution improvement.

    For an Airy PSF, the sidelobes are suppressed even more strongly
    than the main lobe narrows, which is beneficial for imaging.

    Args:
        psf: 2D array containing the original PSF.
        order: SOFI cumulant order (typically 2-6).
        normalize: If True, normalize the result to sum to 1.

    Returns:
        2D array of the effective SOFI PSF (same shape as input).
    """
    eff_psf = np.power(np.maximum(psf, 0), order)

    if normalize and eff_psf.sum() > 0:
        eff_psf /= eff_psf.sum()

    return eff_psf


def psf_fwhm(psf: np.ndarray) -> float:
    """Estimate the Full Width at Half Maximum of a PSF.

    Takes a radial profile through the center and finds the width
    at half the peak value using linear interpolation.

    Args:
        psf: 2D PSF array (assumed centered).

    Returns:
        FWHM in pixels. Returns 0.0 if the PSF is too narrow
        to measure (subpixel).
    """
    center = psf.shape[0] // 2
    profile = psf[center, :]
    peak = profile.max()
    half_max = peak / 2.0

    # Find indices where profile crosses half-maximum
    above = profile >= half_max
    if not np.any(above):
        return 0.0

    indices = np.where(above)[0]
    left = indices[0]
    right = indices[-1]

    # Linear interpolation for sub-pixel accuracy
    if left > 0:
        frac_left = (half_max - profile[left - 1]) / (
            profile[left] - profile[left - 1]
        )
        left_pos = left - 1 + frac_left
    else:
        left_pos = float(left)

    if right < len(profile) - 1:
        frac_right = (half_max - profile[right + 1]) / (
            profile[right] - profile[right + 1]
        )
        right_pos = right + frac_right
    else:
        right_pos = float(right)

    return right_pos - left_pos


def sigma_from_optics(wavelength: float, na: float) -> float:
    """Convert optical parameters to Gaussian PSF sigma.

    Uses the approximation:
        sigma = 0.21 * lambda / NA

    which matches the FWHM of the Airy pattern.

    Args:
        wavelength: Emission wavelength in micrometers.
        na: Numerical aperture.

    Returns:
        Gaussian sigma in micrometers.
    """
    return 0.21 * wavelength / na
