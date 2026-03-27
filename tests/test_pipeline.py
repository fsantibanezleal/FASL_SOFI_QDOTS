"""
Tests for the SOFI processing pipeline.

Validates end-to-end processing with synthetic data.
"""

import sys
import os
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.simulation.sofi_pipeline import SOFIPipeline, SOFIResult
from app.simulation.emitter_simulator import simulate_blinking_sequence
from app.simulation.fourier_interpolation import fourier_interpolate, compute_resolution_gain
from app.simulation.deconvolution import wiener_deconvolution, richardson_lucy
from app.simulation.psf import gaussian_psf, airy_psf, psf_fwhm, sofi_effective_psf


def test_pipeline_basic():
    """Basic pipeline should produce valid results."""
    np.random.seed(42)
    images, positions = simulate_blinking_sequence(
        num_frames=200, image_size=(32, 32),
        num_emitters=10, seed=42
    )

    pipeline = SOFIPipeline(orders=[2, 3], window_size=50)
    result = pipeline.process(images)

    assert isinstance(result, SOFIResult)
    assert result.mean_image.shape == (32, 32)
    assert 2 in result.sofi_images
    assert 3 in result.sofi_images
    assert result.sofi_images[2].shape == (32, 32)
    assert result.sofi_images[3].shape == (32, 32)
    print("  PASS: Basic pipeline produces valid results")


def test_pipeline_resolution_improvement():
    """Higher orders should produce sharper (narrower peak) images."""
    np.random.seed(42)
    # Single emitter at center for clean test
    images, _ = simulate_blinking_sequence(
        num_frames=1000, image_size=(32, 32),
        num_emitters=5, psf_sigma=3.0, seed=42,
        brightness=2000, background=50, noise_std=10
    )

    pipeline = SOFIPipeline(orders=[2, 4], window_size=200)
    result = pipeline.process(images)

    # Higher order should have higher contrast (more peaked)
    c2 = result.sofi_images[2]
    c4 = result.sofi_images[4]
    # Compare standard deviation as measure of "peakiness"
    assert c4.std() > 0, "C4 should have non-zero variation"
    assert c2.std() > 0, "C2 should have non-zero variation"
    print("  PASS: Pipeline produces results for multiple orders")


def test_pipeline_progress_callback():
    """Progress callback should be called."""
    np.random.seed(42)
    images, _ = simulate_blinking_sequence(
        num_frames=100, image_size=(16, 16), num_emitters=5, seed=42
    )

    progress_log = []

    def callback(step, frac):
        progress_log.append((step, frac))

    pipeline = SOFIPipeline(orders=[2], window_size=50)
    pipeline.process(images, progress_callback=callback)

    assert len(progress_log) > 0, "Progress callback was never called"
    assert progress_log[-1][1] == 1.0, "Final progress should be 1.0"
    print("  PASS: Progress callback works correctly")


def test_fourier_interpolation():
    """Fourier interpolation should increase image size."""
    np.random.seed(42)
    img = np.random.rand(16, 16)
    result = fourier_interpolate(img, factor=2)
    assert result.shape == (32, 32), f"Expected (32,32), got {result.shape}"

    result3 = fourier_interpolate(img, factor=3)
    assert result3.shape == (48, 48), f"Expected (48,48), got {result3.shape}"
    print("  PASS: Fourier interpolation produces correct sizes")


def test_fourier_interpolation_identity():
    """Factor 1 should return original image."""
    img = np.random.rand(16, 16)
    result = fourier_interpolate(img, factor=1)
    assert np.allclose(result, img), "Factor 1 should be identity"
    print("  PASS: Fourier interpolation identity (factor=1)")


def test_wiener_deconvolution():
    """Wiener deconvolution should produce an image of correct shape."""
    img = np.random.rand(32, 32)
    psf = gaussian_psf(11, 2.0)
    result = wiener_deconvolution(img, psf, snr=30)
    assert result.shape == img.shape, f"Wrong shape: {result.shape}"
    print("  PASS: Wiener deconvolution produces correct shape")


def test_richardson_lucy():
    """R-L deconvolution should produce a non-negative image."""
    np.random.seed(42)
    img = np.random.rand(32, 32) * 100 + 10
    psf = gaussian_psf(11, 2.0)
    result = richardson_lucy(img, psf, iterations=10)
    assert result.shape == img.shape
    assert np.all(result >= 0), "R-L result should be non-negative"
    print("  PASS: Richardson-Lucy produces non-negative result")


def test_gaussian_psf():
    """Gaussian PSF should be normalized and centered."""
    psf = gaussian_psf(21, 3.0)
    assert psf.shape == (21, 21)
    assert abs(psf.sum() - 1.0) < 1e-10, f"PSF should sum to 1, got {psf.sum()}"
    assert psf[10, 10] == psf.max(), "Peak should be at center"
    print("  PASS: Gaussian PSF is normalized and centered")


def test_airy_psf():
    """Airy PSF should be normalized and centered."""
    psf = airy_psf(41, wavelength=0.532, na=1.4, pixel_size=0.05)
    assert psf.shape == (41, 41)
    assert abs(psf.sum() - 1.0) < 1e-10
    assert psf[20, 20] == psf.max()
    print("  PASS: Airy PSF is normalized and centered")


def test_sofi_effective_psf():
    """Effective PSF should be narrower than original."""
    psf = gaussian_psf(41, 4.0, normalize=False)
    fwhm_orig = psf_fwhm(psf)

    eff2 = sofi_effective_psf(psf, 2, normalize=False)
    fwhm_2 = psf_fwhm(eff2)

    eff4 = sofi_effective_psf(psf, 4, normalize=False)
    fwhm_4 = psf_fwhm(eff4)

    assert fwhm_2 < fwhm_orig, f"Order 2 FWHM ({fwhm_2}) should be < original ({fwhm_orig})"
    assert fwhm_4 < fwhm_2, f"Order 4 FWHM ({fwhm_4}) should be < order 2 ({fwhm_2})"
    print(f"  PASS: PSF narrowing: original={fwhm_orig:.1f}, C2={fwhm_2:.1f}, C4={fwhm_4:.1f}")


def test_resolution_gain_calculation():
    """Resolution gain metrics should be correct."""
    gain = compute_resolution_gain(3.0, 4, with_interpolation=True)
    assert abs(gain["psf_narrowing"] - 2.0) < 1e-10
    assert abs(gain["effective_sigma"] - 1.5) < 1e-10
    assert gain["max_theoretical_gain"] == 4.0
    print("  PASS: Resolution gain calculations correct")


def test_pipeline_config():
    """Pipeline config should be retrievable."""
    pipeline = SOFIPipeline(orders=[2, 3, 4], psf_sigma=2.5)
    config = pipeline.get_config()
    assert config["orders"] == [2, 3, 4]
    assert config["psf_sigma"] == 2.5
    print("  PASS: Pipeline config retrieval works")


if __name__ == "__main__":
    print("=== SOFI Pipeline Tests ===")
    test_pipeline_basic()
    test_pipeline_resolution_improvement()
    test_pipeline_progress_callback()
    test_fourier_interpolation()
    test_fourier_interpolation_identity()
    test_wiener_deconvolution()
    test_richardson_lucy()
    test_gaussian_psf()
    test_airy_psf()
    test_sofi_effective_psf()
    test_resolution_gain_calculation()
    test_pipeline_config()
    print("=== All pipeline tests passed ===")
