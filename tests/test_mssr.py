"""
Tests for MSSR (Mean-Shift Super Resolution) module.

Validates shape, normalization, peak sharpening, and temporal
averaging behavior.
"""

import sys
import os
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.simulation.mssr import compute_mssr, compute_temporal_mssr


def _make_gaussian_spot(size=32, center=None, sigma=3.0, brightness=1000.0, background=50.0):
    """Create a synthetic image with a single Gaussian emitter."""
    if center is None:
        center = (size // 2, size // 2)
    y, x = np.mgrid[0:size, 0:size]
    spot = brightness * np.exp(-((x - center[1])**2 + (y - center[0])**2) / (2 * sigma**2))
    return spot + background


def test_mssr_shape():
    """MSSR output should have the same shape as input."""
    image = np.random.rand(32, 32) * 100 + 10
    result = compute_mssr(image, order=1, kernel_sigma=1.0)
    assert result.shape == image.shape, f"Expected {image.shape}, got {result.shape}"

    result2 = compute_mssr(image, order=2, kernel_sigma=1.0)
    assert result2.shape == image.shape, f"Expected {image.shape}, got {result2.shape}"
    print("  PASS: MSSR output shape matches input shape")


def test_mssr_normalized():
    """MSSR output should be normalized to [0, 1]."""
    image = _make_gaussian_spot(size=32, sigma=3.0)
    result = compute_mssr(image, order=1, kernel_sigma=1.5)
    assert result.min() >= 0.0, f"Min should be >= 0, got {result.min()}"
    assert result.max() <= 1.0 + 1e-10, f"Max should be <= 1, got {result.max()}"
    print("  PASS: MSSR output is normalized to [0, 1]")


def test_mssr_sharpens_peaks():
    """MSSR should sharpen peaks -- the peak pixel should dominate more.

    We compare the peak pixel value relative to the image maximum in
    a ring around the peak. In the original Gaussian, pixels near the
    center are close to the peak value. In MSSR, the drop-off from the
    peak should be much steeper (sharper).
    """
    image = _make_gaussian_spot(size=64, center=(32, 32), sigma=4.0,
                                 brightness=1000.0, background=50.0)
    result = compute_mssr(image, order=1, kernel_sigma=2.0)

    # Normalize original to [0, 1] for comparison
    img_norm = (image - image.min()) / (image.max() - image.min())

    # Measure the ratio of the peak pixel to its immediate neighbors
    # A sharper peak will have a larger peak-to-neighbor ratio
    def peak_to_neighbor_ratio(img, cy=32, cx=32):
        peak = img[cy, cx]
        neighbors = [img[cy-1, cx], img[cy+1, cx], img[cy, cx-1], img[cy, cx+1]]
        mean_neighbor = np.mean(neighbors) + 1e-15
        return peak / mean_neighbor

    orig_ratio = peak_to_neighbor_ratio(img_norm)
    mssr_ratio = peak_to_neighbor_ratio(result)

    assert mssr_ratio > orig_ratio, \
        f"MSSR should have steeper peak drop-off: MSSR={mssr_ratio:.2f} vs orig={orig_ratio:.2f}"
    print(f"  PASS: MSSR sharpens peaks (peak/neighbor ratio {orig_ratio:.2f} -> {mssr_ratio:.2f})")


def test_mssr_order2_sharper_than_order1():
    """Order 2 MSSR should produce sharper peaks than order 1.

    Measured by comparing the fraction of energy concentrated in
    the peak region (5x5 around center) vs the total image energy.
    """
    image = _make_gaussian_spot(size=64, center=(32, 32), sigma=4.0,
                                 brightness=1000.0, background=50.0)
    r1 = compute_mssr(image, order=1, kernel_sigma=2.0)
    r2 = compute_mssr(image, order=2, kernel_sigma=2.0)

    # Energy concentration: fraction of sum in 5x5 center patch
    def peak_concentration(img, cy=32, cx=32, patch=3):
        total = img.sum() + 1e-10
        peak = img[cy-patch:cy+patch+1, cx-patch:cx+patch+1].sum()
        return peak / total

    conc1 = peak_concentration(r1)
    conc2 = peak_concentration(r2)

    assert conc2 >= conc1, \
        f"Order 2 should concentrate more energy at peak: {conc2:.4f} vs {conc1:.4f}"
    print(f"  PASS: Order 2 sharper than order 1 (concentration {conc1:.4f} -> {conc2:.4f})")


def test_temporal_mssr():
    """Temporal MSSR should produce a valid 2D result from a 3D stack."""
    np.random.seed(42)
    T, H, W = 20, 32, 32
    # Stack of noisy Gaussian spots
    images = np.zeros((T, H, W))
    for t in range(T):
        images[t] = _make_gaussian_spot(size=32, sigma=3.0,
                                         brightness=500 + np.random.randn() * 100,
                                         background=50.0)
        images[t] += np.random.randn(H, W) * 20  # add noise

    result = compute_temporal_mssr(images, order=1, kernel_sigma=1.5)

    assert result.shape == (H, W), f"Expected ({H}, {W}), got {result.shape}"
    assert result.min() >= 0.0, f"Min should be >= 0, got {result.min()}"
    assert result.max() <= 1.0 + 1e-10, f"Max should be <= 1, got {result.max()}"
    print("  PASS: Temporal MSSR produces valid 2D result")


def test_mssr_constant_image():
    """MSSR of a constant image should not crash and produce valid output."""
    image = np.ones((16, 16)) * 100.0
    result = compute_mssr(image, order=1, kernel_sigma=1.0)
    assert result.shape == (16, 16)
    assert np.all(np.isfinite(result)), "MSSR of constant image should be finite"
    print("  PASS: MSSR handles constant image gracefully")


if __name__ == "__main__":
    print("=== MSSR Tests ===")
    test_mssr_shape()
    test_mssr_normalized()
    test_mssr_sharpens_peaks()
    test_mssr_order2_sharper_than_order1()
    test_temporal_mssr()
    test_mssr_constant_image()
    print("=== All MSSR tests passed ===")
