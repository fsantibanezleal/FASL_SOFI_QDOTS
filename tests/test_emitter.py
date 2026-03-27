"""
Tests for the quantum dot blinking emitter simulator.

Validates blinking statistics and image generation.
"""

import sys
import os
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.simulation.emitter_simulator import (
    BlinkingEmitter,
    generate_gaussian_psf,
    simulate_blinking_sequence,
)


def test_emitter_creation():
    """Emitter should initialize with correct attributes."""
    e = BlinkingEmitter(x=10.5, y=20.3, brightness=500.0)
    assert e.x == 10.5
    assert e.y == 20.3
    assert e.brightness == 500.0
    assert e.alpha_on == 1.5
    assert e.alpha_off == 1.5
    print("  PASS: Emitter creation with correct attributes")


def test_emitter_blinking():
    """Emitter should switch between on and off states."""
    np.random.seed(42)
    e = BlinkingEmitter(x=0, y=0, brightness=100.0, t_min=1, t_max=10)

    trace = e.generate_trace(1000)

    # Should have both on and off values
    unique_vals = set(trace)
    assert 0.0 in unique_vals, "Emitter should have off periods"
    assert any(v > 0 for v in unique_vals), "Emitter should have on periods"

    # Count transitions
    transitions = np.sum(np.diff(trace) != 0)
    assert transitions > 10, f"Expected many transitions, got {transitions}"
    print(f"  PASS: Emitter blinking with {transitions} transitions in 1000 frames")


def test_emitter_intensity():
    """On-state intensity should equal brightness."""
    np.random.seed(42)
    e = BlinkingEmitter(x=0, y=0, brightness=1234.0)
    trace = e.generate_trace(500)

    on_values = trace[trace > 0]
    if len(on_values) > 0:
        assert np.all(on_values == 1234.0), "On intensity should equal brightness"
    print("  PASS: On-state intensity matches brightness")


def test_gaussian_psf_normalized():
    """Gaussian PSF should sum to 1."""
    psf = generate_gaussian_psf(21, 3.0)
    assert abs(psf.sum() - 1.0) < 1e-10, f"PSF sum = {psf.sum()}"
    assert psf.shape == (21, 21)
    print("  PASS: Gaussian PSF is normalized")


def test_gaussian_psf_symmetry():
    """Gaussian PSF should be radially symmetric."""
    psf = generate_gaussian_psf(21, 3.0)
    center = 10
    # Check horizontal/vertical symmetry
    assert np.allclose(psf[center, :], psf[center, ::-1]), "Not symmetric horizontally"
    assert np.allclose(psf[:, center], psf[::-1, center]), "Not symmetric vertically"
    # Check diagonal symmetry
    assert np.allclose(psf, psf.T), "Not symmetric about diagonal"
    print("  PASS: Gaussian PSF is symmetric")


def test_simulate_sequence_shape():
    """Simulated sequence should have correct shape."""
    images, positions = simulate_blinking_sequence(
        num_frames=50, image_size=(32, 32),
        num_emitters=5, seed=42
    )
    assert images.shape == (50, 32, 32), f"Wrong shape: {images.shape}"
    assert positions.shape == (5, 2), f"Wrong positions shape: {positions.shape}"
    print("  PASS: Simulated sequence has correct shape")


def test_simulate_sequence_reproducible():
    """Same seed should produce identical results."""
    img1, pos1 = simulate_blinking_sequence(num_frames=20, image_size=(16, 16), seed=123)
    img2, pos2 = simulate_blinking_sequence(num_frames=20, image_size=(16, 16), seed=123)

    assert np.allclose(img1, img2), "Same seed should produce identical images"
    assert np.allclose(pos1, pos2), "Same seed should produce identical positions"
    print("  PASS: Simulation is reproducible with same seed")


def test_simulate_has_fluctuations():
    """Simulated data should have temporal fluctuations (for SOFI)."""
    images, _ = simulate_blinking_sequence(
        num_frames=200, image_size=(32, 32),
        num_emitters=10, seed=42
    )

    # Check temporal variance at central pixels
    center = images[:, 14:18, 14:18]
    temporal_std = np.std(center, axis=0)
    assert temporal_std.max() > 0, "Should have temporal fluctuations"
    print(f"  PASS: Temporal fluctuations present (max std = {temporal_std.max():.1f})")


def test_simulate_background():
    """Background should be approximately the specified value."""
    images, positions = simulate_blinking_sequence(
        num_frames=100, image_size=(64, 64),
        num_emitters=3, background=200.0,
        brightness=500, noise_std=5, seed=42
    )

    # Corners should be mostly background
    corner = images[:, 0:3, 0:3]
    mean_corner = np.mean(corner)
    # With Poisson noise, should be approximately background
    assert abs(mean_corner - 200) < 50, f"Corner mean should be ~200, got {mean_corner:.1f}"
    print(f"  PASS: Background level correct (corner mean = {mean_corner:.1f})")


def test_emitter_trace_length():
    """generate_trace should return correct length."""
    e = BlinkingEmitter(x=0, y=0)
    trace = e.generate_trace(300)
    assert len(trace) == 300, f"Expected 300, got {len(trace)}"
    print("  PASS: Trace length is correct")


if __name__ == "__main__":
    print("=== Emitter Simulator Tests ===")
    test_emitter_creation()
    test_emitter_blinking()
    test_emitter_intensity()
    test_gaussian_psf_normalized()
    test_gaussian_psf_symmetry()
    test_simulate_sequence_shape()
    test_simulate_sequence_reproducible()
    test_simulate_has_fluctuations()
    test_simulate_background()
    test_emitter_trace_length()
    print("=== All emitter tests passed ===")
