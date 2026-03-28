"""
Quantum Dot Blinking Emitter Simulator.

Generates synthetic fluorescence image sequences with stochastic
blinking behavior for testing and validating SOFI algorithms.

===== BLINKING MODEL =====

Quantum dots (QDots) exhibit fluorescence intermittency (blinking)
characterized by power-law distributed on/off dwell times:

    P(t_on)  ~ t^(-alpha_on)     with alpha_on  ~ 1.5
    P(t_off) ~ t^(-alpha_off)    with alpha_off ~ 1.5

The blinking is modeled as a telegraph process that switches between
a bright state (intensity = brightness) and a dark state (intensity = 0).

The power-law distribution is sampled using the inverse CDF method:

    t = t_min * (1 - u)^(-1/(alpha-1))

where u ~ Uniform(0, 1). This produces heavy-tailed dwell times
characteristic of QDot blinking (Kuno et al., 2001, JCP 115:1028).

The exponent alpha ~ 1.5 is experimentally observed for CdSe/ZnS
QDots and arises from a distributed tunneling model where the QDot
ionizes by electron tunneling to trap states at varying distances.

===== NOISE MODEL =====

The simulated images include:
1. Poisson shot noise: inherent photon counting statistics
2. Gaussian read noise: detector electronics noise
3. Uniform background: autofluorescence / scattered light

The noise model is:
    I_measured(r, t) = Poisson(I_signal(r, t) + background) + N(0, sigma_read^2)

===== IMAGE FORMATION =====

Each emitter is convolved with a 2D Gaussian PSF:

    U(r) = (1/2*pi*sigma^2) * exp(-|r|^2 / (2*sigma^2))

This is a good approximation for the Airy disk when sigma ~ 0.45*lambda/NA.

References:
    - Kuno et al. (2001), J. Chem. Phys. 115:1028
    - Shimizu et al. (2001), Phys. Rev. B 63:205316
    - Dertinger et al. (2009), PNAS 106(52):22287-22292
    - Dahan et al. (2003), Science 302(5651):442-445
"""

import numpy as np
from typing import Tuple, Optional, List


class BlinkingEmitter:
    """Single fluorescent emitter with stochastic two-state blinking.

    Models a quantum dot that switches between an emissive (bright)
    state and a non-emissive (dark) state with power-law distributed
    dwell times.

    The power-law exponents (alpha_on, alpha_off) control the blinking
    statistics:
        - alpha < 2: infinite mean dwell time (Levy statistics)
        - alpha = 1.5: typical QDot behavior
        - alpha > 2: finite mean, converges to exponential-like behavior

    Attributes:
        x: Horizontal position in pixels (sub-pixel float).
        y: Vertical position in pixels (sub-pixel float).
        brightness: Peak emission intensity (photons/frame).
        alpha_on: Power-law exponent for on-state dwell times.
        alpha_off: Power-law exponent for off-state dwell times.
        t_min: Minimum dwell time in frames (truncation parameter).
        t_max: Maximum dwell time in frames (truncation parameter).
        is_on: Current state (True = emitting).
    """

    def __init__(
        self,
        x: float,
        y: float,
        brightness: float = 1000.0,
        alpha_on: float = 1.5,
        alpha_off: float = 1.5,
        t_min: int = 1,
        t_max: int = 100,
    ):
        """Initialize emitter at position (x, y).

        Args:
            x: Horizontal position in pixels.
            y: Vertical position in pixels.
            brightness: Peak fluorescence intensity.
            alpha_on: On-time power-law exponent.
            alpha_off: Off-time power-law exponent.
            t_min: Minimum dwell time (frames).
            t_max: Maximum dwell time (frames).
        """
        self.x = x
        self.y = y
        self.brightness = brightness
        self.alpha_on = alpha_on
        self.alpha_off = alpha_off
        self.t_min = t_min
        self.t_max = t_max
        self.is_on = np.random.random() > 0.5
        self._time_in_state = 0
        self._state_duration = self._draw_duration()

    def _draw_duration(self) -> int:
        """Draw a state duration from the truncated power-law distribution.

        Uses the inverse CDF method for the Pareto distribution:
            t = t_min * (1 - u)^(-1/(alpha-1))

        The result is clamped to [t_min, t_max] to prevent
        unrealistically long dwell times.

        Returns:
            Integer duration in frames.
        """
        alpha = self.alpha_on if self.is_on else self.alpha_off
        u = np.random.random()
        # Avoid division by zero when u = 1
        u = min(u, 1.0 - 1e-10)
        duration = int(self.t_min * (1 - u) ** (-1.0 / (alpha - 1)))
        return min(max(duration, self.t_min), self.t_max)

    def step(self) -> float:
        """Advance one time step and return current intensity.

        Checks if the current state duration has been exceeded,
        and if so, switches state and draws a new duration.

        Returns:
            Fluorescence intensity: brightness if on, 0.0 if off.
        """
        self._time_in_state += 1
        if self._time_in_state >= self._state_duration:
            self.is_on = not self.is_on
            self._time_in_state = 0
            self._state_duration = self._draw_duration()
        return self.brightness if self.is_on else 0.0

    def generate_trace(self, num_frames: int) -> np.ndarray:
        """Generate a complete intensity time trace.

        Args:
            num_frames: Number of time frames to simulate.

        Returns:
            1D array of intensity values over time.
        """
        trace = np.zeros(num_frames)
        for t in range(num_frames):
            trace[t] = self.step()
        return trace


def generate_gaussian_psf(size: int, sigma: float) -> np.ndarray:
    """Generate a normalized 2D Gaussian Point Spread Function.

    The Gaussian PSF models the diffraction-limited spot:

        U(x, y) = (1/(2*pi*sigma^2)) * exp(-(x^2+y^2)/(2*sigma^2))

    This is a good approximation for a microscope's Airy disk pattern
    when sigma ~ 0.45 * lambda / NA, where lambda is the emission
    wavelength and NA is the numerical aperture.

    Args:
        size: Side length of the PSF array (should be odd).
        sigma: Standard deviation in pixels.

    Returns:
        2D array of shape (size, size), normalized to sum to 1.
    """
    x = np.arange(size) - size // 2
    xx, yy = np.meshgrid(x, x)
    psf = np.exp(-(xx**2 + yy**2) / (2 * sigma**2))
    return psf / psf.sum()


def simulate_blinking_sequence(
    num_frames: int = 500,
    image_size: Tuple[int, int] = (64, 64),
    num_emitters: int = 20,
    psf_sigma: float = 2.0,
    brightness: float = 1000.0,
    background: float = 100.0,
    noise_std: float = 20.0,
    seed: Optional[int] = None,
) -> Tuple[np.ndarray, np.ndarray]:
    """Generate a synthetic blinking fluorescence image sequence.

    Creates a time-lapse image stack simulating a widefield fluorescence
    microscope observing a field of blinking quantum dots. Each emitter
    is convolved with a Gaussian PSF and the images include realistic
    Poisson shot noise and Gaussian read noise.

    The pipeline for each frame:
        1. For each emitter, query current on/off state and intensity.
        2. Place a PSF-convolved spot at the emitter's position.
        3. Add uniform background fluorescence.
        4. Apply Poisson shot noise (photon counting).
        5. Add Gaussian read noise (detector electronics).

    Args:
        num_frames: Number of time frames to simulate.
        image_size: (height, width) of each frame in pixels.
        num_emitters: Number of blinking QDot emitters.
        psf_sigma: PSF standard deviation in pixels.
            Typical values: 1.5-3.0 for diffraction-limited imaging.
        brightness: Mean peak emitter brightness (photons/frame).
            Individual emitters get brightness * Uniform(0.5, 1.5).
        background: Uniform background intensity (photons/pixel/frame).
        noise_std: Standard deviation of Gaussian read noise.
        seed: Random seed for reproducibility. None for random.

    Returns:
        Tuple of (images, emitter_positions):
            images: (T, H, W) float64 array of simulated frames.
            emitter_positions: (N, 2) array of [y, x] emitter positions.
    """
    if seed is not None:
        np.random.seed(seed)

    H, W = image_size
    psf_size = int(6 * psf_sigma) | 1  # ensure odd
    psf = generate_gaussian_psf(psf_size, psf_sigma)
    half = psf_size // 2

    # Random emitter positions with margin to avoid edge artifacts
    margin = half + 2
    positions = np.column_stack(
        [
            np.random.uniform(margin, H - margin, num_emitters),
            np.random.uniform(margin, W - margin, num_emitters),
        ]
    )

    # Create emitters with random brightness variation
    emitters: List[BlinkingEmitter] = [
        BlinkingEmitter(
            x=positions[i, 1],
            y=positions[i, 0],
            brightness=brightness * (0.5 + np.random.random()),
        )
        for i in range(num_emitters)
    ]

    # Generate frames
    images = np.zeros((num_frames, H, W), dtype=np.float64)

    for t in range(num_frames):
        frame = np.full((H, W), background, dtype=np.float64)

        for emitter in emitters:
            intensity = emitter.step()
            if intensity > 0:
                iy = int(round(emitter.y))
                ix = int(round(emitter.x))

                # Compute valid region considering image boundaries
                y_start = max(0, iy - half)
                y_end = min(H, iy + half + 1)
                x_start = max(0, ix - half)
                x_end = min(W, ix + half + 1)

                # Corresponding PSF region
                py_start = y_start - (iy - half)
                py_end = psf_size - ((iy + half + 1) - y_end)
                px_start = x_start - (ix - half)
                px_end = psf_size - ((ix + half + 1) - x_end)

                frame[y_start:y_end, x_start:x_end] += (
                    intensity * psf[py_start:py_end, px_start:px_end]
                )

        # Poisson shot noise (photon counting statistics)
        frame = np.maximum(frame, 0)
        frame = np.random.poisson(frame.astype(np.int64)).astype(np.float64)

        # Gaussian read noise (detector electronics)
        frame += noise_std * np.random.randn(H, W)

        images[t] = frame

    return images, positions


def generate_ground_truth(positions, image_size, psf_sigma, brightness=1000.0):
    """Generate the ideal diffraction-limited image.

    Places delta functions at each emitter position and convolves
    with the PSF. This is the 'ground truth' that SOFI aims to recover.

    Args:
        positions: (N, 2) array of [y, x] emitter positions.
        image_size: (H, W) tuple.
        psf_sigma: PSF standard deviation in pixels.
        brightness: Peak emitter brightness.

    Returns:
        2D array (H, W) normalized to [0, 1].
    """
    H, W = image_size
    psf_size = int(6 * psf_sigma) | 1
    psf = generate_gaussian_psf(psf_size, psf_sigma)
    half = psf_size // 2

    image = np.zeros((H, W), dtype=np.float64)
    for i in range(len(positions)):
        iy, ix = int(round(positions[i, 0])), int(round(positions[i, 1]))
        y_start = max(0, iy - half); y_end = min(H, iy + half + 1)
        x_start = max(0, ix - half); x_end = min(W, ix + half + 1)
        py_start = y_start - (iy - half); py_end = psf_size - ((iy + half + 1) - y_end)
        px_start = x_start - (ix - half); px_end = psf_size - ((ix + half + 1) - x_end)
        image[y_start:y_end, x_start:x_end] += brightness * psf[py_start:py_end, px_start:px_end]

    vmax = image.max()
    return image / vmax if vmax > 0 else image
