"""
SOFI Cumulant Computation Engine.

===== THEORETICAL FOUNDATION =====

Super-resolution Optical Fluctuation Imaging (SOFI) extracts
sub-diffraction spatial information from temporal fluorescence
fluctuations of independent emitters.

The fluorescence signal at pixel position r and time t is:

    F(r, t) = Sum_k  eps_k * s_k(t) * U(r - r_k)

where:
    eps_k  = molecular brightness of emitter k
    s_k(t) = stochastic on/off switching function
    U(r)   = Point Spread Function (PSF)
    r_k    = position of emitter k

The nth-order cumulant of the intensity time series yields:

    C_n(r) = Sum_k  eps_k^n * kappa_n[s_k] * U^n(r - r_k)

The key insight: the PSF is raised to the nth power, narrowing
the effective PSF by factor sqrt(n):

    sigma_eff = sigma_PSF / sqrt(n)

Cross-terms between different emitters vanish because emitters
fluctuate independently (a fundamental property of cumulants).

===== CUMULANT FORMULAS =====

For zero-mean signals dF = F - <F>:

    C2(tau)         = <dF(t) * dF(t+tau)>

    C3(tau1, tau2)  = <dF(t) * dF(t+tau1) * dF(t+tau2)>

    C4(tau1, tau2, tau3) = <dF(t) * dF(t+tau1) * dF(t+tau2) * dF(t+tau3)>
                         - C2(tau1) * C2(tau3-tau2)
                         - C2(tau2) * C2(tau3-tau1)
                         - C2(tau3) * C2(tau2-tau1)

With consecutive-frame time lags (tau=1,2,...):

Order 2: C2 = mean(dF[0:T-1] * dF[1:T])
Order 3: C3 = mean(dF[0:T-2] * dF[1:T-1] * dF[2:T])
Order 4: C4 = mean(dF[0:T-3]*dF[1:T-2]*dF[2:T-1]*dF[3:T])
             - mean(dF[0:T-3]*dF[3:T]) * mean(dF[1:T-2]*dF[2:T-1])
             - mean(dF[0:T-3]*dF[2:T-1]) * mean(dF[1:T-2]*dF[3:T])
             - mean(dF[0:T-3]*dF[1:T-2]) * mean(dF[2:T-1]*dF[3:T])

===== RESOLUTION IMPROVEMENT =====

Order | PSF narrowing | Resolution gain
  2   |  U^2(r)       |  sqrt(2) ~ 1.41x
  3   |  U^3(r)       |  sqrt(3) ~ 1.73x
  4   |  U^4(r)       |  sqrt(4) = 2.00x
  5   |  U^5(r)       |  sqrt(5) ~ 2.24x
  6   |  U^6(r)       |  sqrt(6) ~ 2.45x

References:
    - Dertinger et al. (2009), PNAS 106(52):22287-22292
    - Geissbuehler et al. (2012), Optical Nanoscopy 1:4 (bSOFI)
    - Dertinger et al. (2010), Opt. Express 18(18):18875-18885
    - Basak et al. (2025), Nature Photonics 19:229-237
"""

import numpy as np
from typing import Optional


def compute_cumulant(images: np.ndarray, order: int) -> np.ndarray:
    """Compute the nth-order SOFI cumulant from an image stack.

    Uses zero-mean intensity fluctuations with consecutive time lags
    to compute the auto-cumulant at each pixel.

    The implementation follows the moment-to-cumulant conversion
    for orders 2-6, using the formulas from Dertinger et al. (2009)
    and the general cumulant-moment partition relations.

    For order n, the nth cumulant is expressed as a sum over all
    set partitions of {1, ..., n} using the Mobius function on the
    partition lattice:

        kappa_n = Sum_{pi in P(n)} (-1)^{|pi|-1} (|pi|-1)! Prod_{B in pi} mu_{|B|}

    where mu_k are the kth raw moments of the zero-mean signal.

    Args:
        images: 3D array (T, H, W) of fluorescence frames.
            T = number of time frames (minimum: order + 1)
            H, W = image height and width in pixels
        order: Cumulant order (2, 3, 4, 5, or 6).

    Returns:
        2D array (H, W) of cumulant values at each pixel.

    Raises:
        ValueError: If order < 2 or > 6, or insufficient frames.
    """
    if order < 2 or order > 6:
        raise ValueError(f"Cumulant order must be 2-6, got {order}")

    T, H, W = images.shape
    if T < order + 1:
        raise ValueError(
            f"Need at least {order + 1} frames for order {order}, got {T}"
        )

    # Zero-mean: subtract temporal mean from each pixel
    mean_img = np.mean(images, axis=0)
    delta = images - mean_img[np.newaxis, :, :]

    if order == 2:
        return _cumulant_2(delta)
    elif order == 3:
        return _cumulant_3(delta)
    elif order == 4:
        return _cumulant_4(delta)
    elif order == 5:
        return _cumulant_5(delta)
    elif order == 6:
        return _cumulant_6(delta)


def _cumulant_2(d: np.ndarray) -> np.ndarray:
    """2nd-order cumulant with consecutive time lag.

    C2 = <dF(t) * dF(t+1)>

    This is the auto-covariance at lag 1. For independent
    emitters with identical PSFs, C2 narrows the PSF by sqrt(2).

    Args:
        d: Zero-mean fluctuation stack (T, H, W).

    Returns:
        2D cumulant image (H, W).
    """
    return np.mean(d[:-1] * d[1:], axis=0)


def _cumulant_3(d: np.ndarray) -> np.ndarray:
    """3rd-order cumulant with consecutive time lags.

    C3 = <dF(t) * dF(t+1) * dF(t+2)>

    The 3rd cumulant equals the 3rd central moment for zero-mean
    variables. No subtraction terms needed because:
        kappa_3 = mu_3 (when mu_1 = 0)

    Args:
        d: Zero-mean fluctuation stack (T, H, W).

    Returns:
        2D cumulant image (H, W).
    """
    return np.mean(d[:-2] * d[1:-1] * d[2:], axis=0)


def _cumulant_4(d: np.ndarray) -> np.ndarray:
    """4th-order cumulant with moment subtraction.

    C4 = <dF0*dF1*dF2*dF3>
       - <dF0*dF3>*<dF1*dF2>
       - <dF0*dF2>*<dF1*dF3>
       - <dF0*dF1>*<dF2*dF3>

    The subtraction of all possible pairwise products of 2nd-order
    moments removes Gaussian contributions. This is the defining
    property of the 4th cumulant: it vanishes for Gaussian processes.

    The three subtraction terms correspond to the three ways to
    partition {0,1,2,3} into two pairs:
        {0,3},{1,2}  |  {0,2},{1,3}  |  {0,1},{2,3}

    Args:
        d: Zero-mean fluctuation stack (T, H, W).

    Returns:
        2D cumulant image (H, W).
    """
    T = d.shape[0]
    d0, d1, d2, d3 = d[: T - 3], d[1 : T - 2], d[2 : T - 1], d[3:T]

    m4 = np.mean(d0 * d1 * d2 * d3, axis=0)
    m03 = np.mean(d0 * d3, axis=0)
    m12 = np.mean(d1 * d2, axis=0)
    m02 = np.mean(d0 * d2, axis=0)
    m13 = np.mean(d1 * d3, axis=0)
    m01 = np.mean(d0 * d1, axis=0)
    m23 = np.mean(d2 * d3, axis=0)

    return m4 - m03 * m12 - m02 * m13 - m01 * m23


def _cumulant_5(d: np.ndarray) -> np.ndarray:
    """5th-order cumulant.

    The 5th cumulant is computed via the moment-cumulant relation:

        kappa_5 = mu_5 - 10 * mu_3 * mu_2

    In terms of partitions: we subtract all products of a pair moment
    and a triple moment. There are C(5,2) = 10 ways to choose the pair
    from the 5 indices {0,1,2,3,4}, and each partition is (pair, triple).

    C5 = M5 - Sum_{all 10 (pair,triple) partitions} M_pair * M_triple

    Args:
        d: Zero-mean fluctuation stack (T, H, W).

    Returns:
        2D cumulant image (H, W).
    """
    T = d.shape[0]
    d0, d1, d2, d3, d4 = (
        d[: T - 4],
        d[1 : T - 3],
        d[2 : T - 2],
        d[3 : T - 1],
        d[4:T],
    )

    m5 = np.mean(d0 * d1 * d2 * d3 * d4, axis=0)

    # All 10 partitions of {0,1,2,3,4} into (pair, triple)
    dd = [d0, d1, d2, d3, d4]
    correction = np.zeros_like(m5)

    for i in range(5):
        for j in range(i + 1, 5):
            remaining = [k for k in range(5) if k not in (i, j)]
            pair_val = np.mean(dd[i] * dd[j], axis=0)
            triple_val = np.mean(
                dd[remaining[0]] * dd[remaining[1]] * dd[remaining[2]], axis=0
            )
            correction += pair_val * triple_val

    return m5 - correction


def _cumulant_6(d: np.ndarray) -> np.ndarray:
    """6th-order cumulant.

    The 6th cumulant is the most complex, involving several partition types.
    From the moment-cumulant relation for zero-mean variables:

        kappa_6 = mu_6 - 15*mu_4*mu_2 - 10*mu_3^2 + 30*mu_2^3

    In terms of set partitions of {0,1,2,3,4,5}, we have three types
    of non-trivial partitions to subtract:

    Type A: (pair, quartet) - 15 terms with coefficient -1
        15 ways to choose 2 from 6, remaining 4 form the quartet.

    Type B: (triple, triple) - 10 terms with coefficient -1
        C(6,3)/2 = 10 ways to split into two triples.

    Type C: (pair, pair, pair) - 15 terms with coefficient +2
        15 ways to partition 6 into three pairs.

    C6 = M6 - Sum_A(pair*quartet) - Sum_B(triple*triple) + 2*Sum_C(pair*pair*pair)

    Args:
        d: Zero-mean fluctuation stack (T, H, W).

    Returns:
        2D cumulant image (H, W).
    """
    T = d.shape[0]
    d0 = d[: T - 5]
    d1 = d[1 : T - 4]
    d2 = d[2 : T - 3]
    d3 = d[3 : T - 2]
    d4 = d[4 : T - 1]
    d5 = d[5:T]

    dd = [d0, d1, d2, d3, d4, d5]

    m6 = np.mean(d0 * d1 * d2 * d3 * d4 * d5, axis=0)

    # Type A: (pair, quartet) partitions - 15 terms
    pair_quad = np.zeros_like(m6)
    for i in range(6):
        for j in range(i + 1, 6):
            remaining = [k for k in range(6) if k not in (i, j)]
            pair_val = np.mean(dd[i] * dd[j], axis=0)
            quad_val = np.mean(
                dd[remaining[0]]
                * dd[remaining[1]]
                * dd[remaining[2]]
                * dd[remaining[3]],
                axis=0,
            )
            pair_quad += pair_val * quad_val

    # Type B: (triple, triple) partitions - 10 terms
    # We iterate over all C(6,3)=20 triples, but each partition
    # is counted twice (once for each triple), so divide by 2.
    triple_triple = np.zeros_like(m6)
    for i in range(6):
        for j in range(i + 1, 6):
            for k in range(j + 1, 6):
                remaining = tuple(m for m in range(6) if m not in (i, j, k))
                ta = np.mean(dd[i] * dd[j] * dd[k], axis=0)
                tb = np.mean(
                    dd[remaining[0]] * dd[remaining[1]] * dd[remaining[2]],
                    axis=0,
                )
                triple_triple += ta * tb
    triple_triple /= 2  # Each partition was counted twice

    # Type C: (pair, pair, pair) partitions - 15 terms
    triple_pair = np.zeros_like(m6)
    pair_list = []
    for i in range(6):
        for j in range(i + 1, 6):
            pair_list.append((i, j))

    for idx_a in range(len(pair_list)):
        for idx_b in range(idx_a + 1, len(pair_list)):
            a = pair_list[idx_a]
            b = pair_list[idx_b]
            if set(a) & set(b):
                continue
            remaining = [k for k in range(6) if k not in a and k not in b]
            if len(remaining) == 2:
                c = tuple(remaining)
                pa = np.mean(dd[a[0]] * dd[a[1]], axis=0)
                pb = np.mean(dd[b[0]] * dd[b[1]], axis=0)
                pc = np.mean(dd[c[0]] * dd[c[1]], axis=0)
                triple_pair += pa * pb * pc

    # The nested loop counts each partition 3 times (once per pair
    # chosen as "c").  Divide by 3 to get the correct 15 terms.
    # Bug found by Codex code review on PR #2.
    triple_pair /= 3

    return m6 - pair_quad - triple_triple + 2 * triple_pair


def compute_cross_cumulant(images: np.ndarray, order: int) -> np.ndarray:
    """Cross-cumulant SOFI using neighboring pixel combinations.

    Instead of auto-cumulants at each pixel, combines signals from
    neighboring pixels to achieve sub-pixel sampling:

        C_n(r_virtual) = cumulant(F(r_1, t), ..., F(r_n, t))
        where r_virtual = (r_1 + ... + r_n) / n

    This provides n-fold resolution improvement (not just sqrt(n))
    because the virtual pixel grid is n times finer than the
    physical pixel grid.

    For order 2: combine each pixel with its right neighbor
        r_virtual = (r, r+dx) -> virtual pixel at r + dx/2
    For order 3: combine pixel with right and bottom neighbors
    For order 4: 2x2 neighborhood

    Args:
        images: 3D array (T, H, W) of fluorescence frames.
        order: Cross-cumulant order (2, 3, or 4).

    Returns:
        2D array of cross-cumulant values. Shape depends on order:
        - Order 2: (H, W*2-1) with interleaved auto and cross values
        - Order 3: (H-1, W-1) cross-cumulant map
        - Order 4: (H-1, W-1) cross-cumulant map
        For other orders, falls back to standard auto-cumulant.
    """
    T, H, W = images.shape
    mean_img = np.mean(images, axis=0)
    delta = images - mean_img[np.newaxis, :, :]

    if order == 2:
        # Cross-cumulant between pixel (i,j) and (i,j+1)
        # Virtual pixel at (i, j+0.5) -- doubles horizontal resolution
        d_left = delta[:, :, :-1]   # (T, H, W-1)
        d_right = delta[:, :, 1:]   # (T, H, W-1)
        xc = np.mean(d_left[:-1] * d_right[1:], axis=0)
        # Upscale to 2x width
        result = np.zeros((H, W * 2 - 1))
        result[:, 0::2] = compute_cumulant(images, 2)  # auto at original pixels
        result[:, 1::2] = xc  # cross at virtual pixels
        return result

    elif order == 3:
        # 3-pixel cross: (i,j), (i,j+1), (i+1,j)
        d00 = delta[:, :-1, :-1]
        d01 = delta[:, :-1, 1:]
        d10 = delta[:, 1:, :-1]
        xc = np.mean(d00[:-2] * d01[1:-1] * d10[2:], axis=0)
        return xc

    elif order == 4:
        # 2x2 cross: (i,j), (i,j+1), (i+1,j), (i+1,j+1)
        d00 = delta[:, :-1, :-1]
        d01 = delta[:, :-1, 1:]
        d10 = delta[:, 1:, :-1]
        d11 = delta[:, 1:, 1:]
        # Align time lags: x0=d00, x1=d01(lag1), x2=d10(lag2), x3=d11(lag3)
        T4 = min(d00.shape[0], d01.shape[0], d10.shape[0], d11.shape[0]) - 3
        x0, x1, x2, x3 = d00[:T4], d01[1:T4+1], d10[2:T4+2], d11[3:T4+3]

        m4 = np.mean(x0 * x1 * x2 * x3, axis=0)
        # All three pair-partitions of {0,1,2,3}
        m01 = np.mean(x0 * x1, axis=0)
        m23 = np.mean(x2 * x3, axis=0)
        m02 = np.mean(x0 * x2, axis=0)
        m13 = np.mean(x1 * x3, axis=0)
        m03 = np.mean(x0 * x3, axis=0)
        m12 = np.mean(x1 * x2, axis=0)

        return m4 - m01*m23 - m02*m13 - m03*m12

    return compute_cumulant(images, order)


def compute_sofi_image(
    images: np.ndarray,
    order: int,
    window_size: int = 100,
    linearize: bool = True,
) -> np.ndarray:
    """Compute a complete SOFI super-resolution image.

    Processes the image stack in temporal windows, accumulates
    cumulants across windows, normalizes, and optionally linearizes
    by taking the nth root.

    Windowed processing improves robustness against slow drifts
    (bleaching, focus drift) that would bias the cumulant estimate.
    Each window provides an independent cumulant estimate; averaging
    across windows reduces variance.

    Linearization: The nth-order cumulant scales as brightness^n,
    creating extreme contrast differences between bright and dim
    emitters. Taking the nth root restores linear brightness scaling.

    Args:
        images: 3D array (T, H, W) of fluorescence frames.
        order: Cumulant order (2-6).
        window_size: Number of frames per temporal window.
            Larger windows give better SNR but more sensitivity to drift.
        linearize: If True, take nth root to linearize brightness.

    Returns:
        2D array (H, W) of the SOFI super-resolution image,
        normalized to [0, 1].
    """
    T, H, W = images.shape
    n_windows = max(1, T // window_size)

    accumulated = np.zeros((H, W), dtype=np.float64)

    for k in range(n_windows):
        start = k * window_size
        end = min(start + window_size, T)
        if end - start < order + 1:
            break

        block = images[start:end].astype(np.float64)
        cum = compute_cumulant(block, order)
        accumulated += np.abs(cum)

    accumulated /= max(n_windows, 1)

    if linearize and order > 1:
        # nth root linearization to correct brightness nonlinearity
        # |C_n|^(1/n) gives linear brightness scaling
        accumulated = np.power(np.maximum(accumulated, 0), 1.0 / order)

    # Normalize to [0, 1]
    vmin, vmax = accumulated.min(), accumulated.max()
    if vmax > vmin:
        accumulated = (accumulated - vmin) / (vmax - vmin)

    return accumulated
