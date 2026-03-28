"""
Mean-Shift Super Resolution (MSSR) — single-frame super-resolution.

MSSR achieves super-resolution from a SINGLE frame by analyzing the
local intensity distribution around each pixel using mean-shift
analysis. It identifies sub-pixel emitter positions from the local
gradient structure.

The algorithm:
1. For each pixel, compute the local mean shift vector:
   m(x) = (Σ K(x-xi) * xi * I(xi)) / (Σ K(x-xi) * I(xi)) - x
   where K is a Gaussian kernel and I is the intensity.

2. The mean shift magnitude |m(x)| indicates proximity to an emitter:
   - Near an emitter center: |m| ≈ 0 (convergence point)
   - On the slope of a PSF: |m| points toward the center

3. The MSSR image is constructed as:
   MSSR(x) = I(x) / (|m(x)| + epsilon)
   This sharpens peaks (small |m|) and suppresses slopes (large |m|).

Resolution improvement: ~1.5-2x from a SINGLE frame.
Temporal resolution: same as camera frame rate (no stacking needed).

References:
    - Torres-García et al. (2022), Extending resolution within a
      single imaging frame, Nature Communications 13:7452
"""
import numpy as np
from scipy.ndimage import uniform_filter, gaussian_filter


def compute_mssr(image: np.ndarray, order: int = 1,
                  kernel_sigma: float = 1.0) -> np.ndarray:
    """Compute MSSR super-resolution image from a single frame.

    Args:
        image: 2D array (H, W) — single fluorescence frame.
        order: MSSR order (1 or 2). Higher order = more sharpening.
        kernel_sigma: Gaussian kernel sigma for mean-shift computation.

    Returns:
        2D array (H, W) — MSSR enhanced image, normalized to [0, 1].
    """
    image = image.astype(np.float64)
    H, W = image.shape

    # Compute intensity-weighted mean shift
    # Numerator: Σ K(x-xi) * xi * I(xi) for each coordinate
    Ix = image * np.arange(W)[np.newaxis, :]  # intensity * x-coord
    Iy = image * np.arange(H)[:, np.newaxis]  # intensity * y-coord

    # Smooth with Gaussian kernel
    smooth_I = gaussian_filter(image, sigma=kernel_sigma) + 1e-10
    smooth_Ix = gaussian_filter(Ix, sigma=kernel_sigma)
    smooth_Iy = gaussian_filter(Iy, sigma=kernel_sigma)

    # Mean position (intensity-weighted centroid in local neighborhood)
    mean_x = smooth_Ix / smooth_I
    mean_y = smooth_Iy / smooth_I

    # Current pixel positions
    x_grid = np.arange(W)[np.newaxis, :] * np.ones((H, 1))
    y_grid = np.arange(H)[:, np.newaxis] * np.ones((1, W))

    # Mean shift vector
    shift_x = mean_x - x_grid
    shift_y = mean_y - y_grid

    # Mean shift magnitude
    shift_mag = np.sqrt(shift_x**2 + shift_y**2)

    # MSSR image: sharpen peaks, suppress slopes
    epsilon = np.percentile(shift_mag[shift_mag > 0], 5) if np.any(shift_mag > 0) else 0.1

    if order == 1:
        mssr = image / (shift_mag + epsilon)
    else:
        # Order 2: use gradient of shift magnitude for extra sharpening
        grad_x = np.gradient(shift_mag, axis=1)
        grad_y = np.gradient(shift_mag, axis=0)
        grad_mag = np.sqrt(grad_x**2 + grad_y**2)
        mssr = image / ((shift_mag + epsilon) * (grad_mag + epsilon))

    # Normalize to [0, 1]
    mssr = np.maximum(mssr, 0)
    vmax = np.percentile(mssr, 99.5)
    if vmax > 0:
        mssr = np.clip(mssr / vmax, 0, 1)

    return mssr


def compute_temporal_mssr(images: np.ndarray, order: int = 1,
                           kernel_sigma: float = 1.0) -> np.ndarray:
    """Compute temporal MSSR by averaging MSSR across frames.

    Combines the single-frame resolution of MSSR with temporal
    averaging for improved SNR.

    Args:
        images: 3D array (T, H, W).
        order: MSSR order (1 or 2).
        kernel_sigma: Gaussian kernel sigma.

    Returns:
        2D array (H, W) — temporally averaged MSSR image.
    """
    T = images.shape[0]
    accumulated = np.zeros(images.shape[1:], dtype=np.float64)

    for t in range(T):
        accumulated += compute_mssr(images[t], order=order, kernel_sigma=kernel_sigma)

    result = accumulated / T
    vmax = result.max()
    if vmax > 0:
        result /= vmax
    return result
