"""Compartment dopamine balance in µM, with one explicit Euler step per chunk."""
from __future__ import annotations

import numpy as np
from numpy.typing import NDArray
from scipy.sparse import csr_matrix


def innervated_mask(innervation: csr_matrix) -> NDArray[np.bool_]:
    """Return nonempty M rows as a boolean vector (n_comp,)."""
    return np.asarray(innervation.getnnz(axis=1) > 0, dtype=np.bool_)


def tonic_source(da_ref_um: float, vmax_um_s: NDArray[np.float64], km_um: NDArray[np.float64],
                 k_ns_s: float, mask: NDArray[np.bool_]) -> NDArray[np.float64]:
    """Return item-51 standing release, µM/s vector (n_comp,); absent M rows are zero."""
    source = da_ref_um * (np.asarray(vmax_um_s) / (np.asarray(km_um) + da_ref_um) + k_ns_s)
    return np.where(mask, source, 0.0).astype(np.float64)


def fixed_point(source_um_s: NDArray[np.float64], vmax_um_s: NDArray[np.float64],
                km_um: NDArray[np.float64], k_ns_s: float) -> NDArray[np.float64]:
    """Solve transporter plus first-order clearance balance; input/output (n_comp,) µM or µM/s."""
    source = np.asarray(source_um_s, dtype=np.float64)
    vmax = np.asarray(vmax_um_s, dtype=np.float64)
    km = np.asarray(km_um, dtype=np.float64)
    b = vmax + k_ns_s * km - source
    discriminant = np.sqrt(b * b + 4 * k_ns_s * source * km)
    # Rationalize only for b >= 0; for b < 0 the rationalized denominator
    # subtracts nearly equal numbers at large release and loses precision.
    answer = np.empty_like(b)
    positive = b >= 0
    answer[positive] = 2 * source[positive] * km[positive] / (b[positive] + discriminant[positive])
    answer[~positive] = (discriminant[~positive] - b[~positive]) / (2 * k_ns_s)
    # With DAT absent the exact balance is independent of methylphenidate/Km.
    return np.where(vmax == 0, source / k_ns_s, answer)


def euler_step(da_um: NDArray[np.float64], counts: NDArray[np.int32], dt_s: float,
               innervation: csr_matrix, mask: NDArray[np.bool_], alpha_um: NDArray[np.float64],
               rel: float, vmax_um_s: NDArray[np.float64], km_um: NDArray[np.float64],
               k_ns_s: float, da_ref_um: float,
               tonic_source_um_s: NDArray[np.float64] | None = None) -> NDArray[np.float64]:
    """Advance pools once; DA/alpha (n_comp,) µM, source (n_comp,) µM/s, counts (n,), duration s."""
    da = np.asarray(da_um, dtype=np.float64)
    tonic = np.zeros_like(da) if tonic_source_um_s is None else np.asarray(tonic_source_um_s, dtype=np.float64)
    if tonic.shape != da.shape:
        raise ValueError("tonic source must have shape (n_comp,)")
    release = rel * (alpha_um * np.asarray(innervation @ counts).ravel() + tonic * dt_s)
    clear = vmax_um_s * da / (km_um + da) + k_ns_s * da
    next_da = np.maximum(0.0, da + release - clear * dt_s)
    next_da[~mask] = da_ref_um
    return next_da
