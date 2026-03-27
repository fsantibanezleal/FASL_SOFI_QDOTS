"""
Tests for SOFI cumulant computation.

Validates cumulant formulas using synthetic data with known
statistical properties.
"""

import sys
import os
import numpy as np

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.simulation.cumulants import compute_cumulant, compute_sofi_image, compute_cross_cumulant


def test_cumulant_2_constant_signal():
    """C2 of a constant signal should be zero (no fluctuations)."""
    images = np.ones((100, 8, 8)) * 50.0
    result = compute_cumulant(images, 2)
    assert np.allclose(result, 0, atol=1e-10), f"C2 of constant signal should be 0, got max={result.max()}"
    print("  PASS: C2 of constant signal is zero")


def test_cumulant_2_known_variance():
    """C2 of a known signal should match expected auto-covariance."""
    np.random.seed(42)
    T, H, W = 10000, 4, 4
    # Create independent Gaussian noise at each pixel
    images = np.random.randn(T, H, W) * 5.0 + 100.0

    result = compute_cumulant(images, 2)
    # For IID Gaussian noise, C2(lag=1) should be ~0
    assert np.all(np.abs(result) < 0.5), f"C2 of IID noise at lag 1 should be ~0, got max={np.abs(result).max()}"
    print("  PASS: C2 of IID noise is near zero (no auto-correlation)")


def test_cumulant_2_correlated_signal():
    """C2 of a correlated signal should be positive."""
    np.random.seed(42)
    T, H, W = 5000, 4, 4
    # AR(1) process: x(t) = 0.9*x(t-1) + noise
    images = np.zeros((T, H, W))
    images[0] = np.random.randn(H, W)
    for t in range(1, T):
        images[t] = 0.9 * images[t-1] + 0.1 * np.random.randn(H, W)

    result = compute_cumulant(images, 2)
    # Auto-covariance at lag 1 should be positive for AR(1) with positive coefficient
    assert np.all(result > 0), f"C2 of positively correlated signal should be positive"
    print("  PASS: C2 of correlated signal is positive")


def test_cumulant_3_symmetric_signal():
    """C3 of a symmetric distribution should be near zero."""
    np.random.seed(42)
    T, H, W = 50000, 4, 4
    images = np.random.randn(T, H, W) * 5.0 + 100.0

    result = compute_cumulant(images, 3)
    assert np.all(np.abs(result) < 3.0), f"C3 of symmetric noise should be ~0, got max={np.abs(result).max()}"
    print(f"  PASS: C3 of symmetric signal is near zero (max={np.abs(result).max():.3f})")


def test_cumulant_4_gaussian():
    """C4 of a Gaussian signal should be near zero (excess kurtosis = 0)."""
    np.random.seed(42)
    T, H, W = 50000, 4, 4
    images = np.random.randn(T, H, W) * 5.0 + 100.0

    result = compute_cumulant(images, 4)
    # C4 with time lags for IID Gaussian should be ~0
    assert np.all(np.abs(result) < 15.0), f"C4 of Gaussian should be ~0, got max={np.abs(result).max()}"
    print(f"  PASS: C4 of Gaussian signal is near zero (max={np.abs(result).max():.3f})")


def test_cumulant_order_validation():
    """Invalid orders should raise ValueError."""
    images = np.ones((10, 4, 4))

    for order in [0, 1, 7, -1]:
        try:
            compute_cumulant(images, order)
            assert False, f"Should have raised ValueError for order {order}"
        except ValueError:
            pass
    print("  PASS: Invalid orders correctly rejected")


def test_insufficient_frames():
    """Too few frames should raise ValueError."""
    images = np.ones((3, 4, 4))
    try:
        compute_cumulant(images, 4)  # Need at least 5 frames
        assert False, "Should have raised ValueError"
    except ValueError:
        pass
    print("  PASS: Insufficient frames correctly rejected")


def test_compute_sofi_image():
    """compute_sofi_image should return normalized [0,1] image."""
    np.random.seed(42)
    T, H, W = 200, 8, 8
    # Create signal with blinking-like behavior
    images = np.random.exponential(100, (T, H, W))

    result = compute_sofi_image(images, 2, window_size=50, linearize=True)
    assert result.shape == (H, W), f"Wrong shape: {result.shape}"
    assert result.min() >= 0.0, f"Min should be >= 0, got {result.min()}"
    assert result.max() <= 1.0, f"Max should be <= 1, got {result.max()}"
    print("  PASS: compute_sofi_image returns normalized image")


def test_cumulant_5_iid():
    """C5 of IID noise should be near zero."""
    np.random.seed(42)
    T, H, W = 50000, 2, 2
    images = np.random.randn(T, H, W) * 5.0 + 100.0
    result = compute_cumulant(images, 5)
    assert np.all(np.abs(result) < 50.0), f"C5 of IID noise should be ~0, got max={np.abs(result).max()}"
    print(f"  PASS: C5 of IID noise is near zero (max={np.abs(result).max():.3f})")


def test_cumulant_6_iid():
    """C6 of IID noise should be near zero."""
    np.random.seed(42)
    T, H, W = 50000, 2, 2
    images = np.random.randn(T, H, W) * 5.0 + 100.0
    result = compute_cumulant(images, 6)
    assert np.all(np.abs(result) < 500.0), f"C6 of IID noise should be ~0, got max={np.abs(result).max()}"
    print(f"  PASS: C6 of IID noise is near zero (max={np.abs(result).max():.3f})")


def test_cross_cumulant_2():
    """Cross-cumulant order 2 should produce wider image."""
    images = np.random.randn(200, 16, 16).astype(np.float64) * 10 + 100
    xc = compute_cross_cumulant(images, 2)
    assert xc.shape[1] == 16 * 2 - 1, f"Expected width {16*2-1}, got {xc.shape[1]}"
    print("  PASS: Cross-cumulant order 2 produces upsampled image")


def test_cross_cumulant_3():
    """Cross-cumulant order 3 should produce (H-1, W-1) image."""
    images = np.random.randn(200, 16, 16).astype(np.float64) * 10 + 100
    xc = compute_cross_cumulant(images, 3)
    assert xc.shape == (15, 15), f"Expected (15, 15), got {xc.shape}"
    print("  PASS: Cross-cumulant order 3 produces correct shape")


def test_cross_cumulant_4():
    """Cross-cumulant order 4 should produce (H-1, W-1) image."""
    images = np.random.randn(200, 16, 16).astype(np.float64) * 10 + 100
    xc = compute_cross_cumulant(images, 4)
    assert xc.shape == (15, 15), f"Expected (15, 15), got {xc.shape}"
    print("  PASS: Cross-cumulant order 4 produces correct shape")


if __name__ == "__main__":
    print("=== SOFI Cumulant Tests ===")
    test_cumulant_2_constant_signal()
    test_cumulant_2_known_variance()
    test_cumulant_2_correlated_signal()
    test_cumulant_3_symmetric_signal()
    test_cumulant_4_gaussian()
    test_cumulant_order_validation()
    test_insufficient_frames()
    test_compute_sofi_image()
    test_cumulant_5_iid()
    test_cumulant_6_iid()
    test_cross_cumulant_2()
    test_cross_cumulant_3()
    test_cross_cumulant_4()
    print("=== All cumulant tests passed ===")
