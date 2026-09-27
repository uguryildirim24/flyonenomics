"""Absolute dopamine occupancy and per-neuron receptor effects."""
from __future__ import annotations

import numpy as np
from numpy.typing import NDArray
from scipy.sparse import csr_matrix

from flyonenomics.types import Params


def receptor_effect(da_c: NDArray[np.float64], exposure: csr_matrix, exposed: NDArray[np.bool_],
                    r1: NDArray[np.float64], r2: NDArray[np.float64], params: Params
                    ) -> tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.float64], NDArray[np.float64]]:
    """Return dV (mV), gain, D1 and D2 occupancy (n,) from DA (n_comp,) µM."""
    da_i = np.asarray(exposure @ da_c).ravel()
    occ1 = da_i / (da_i + params.get("rec.Kd_D1")) * exposed
    occ2 = da_i / (da_i + params.get("rec.Kd_D2")) * exposed
    d_v = -params.get("rec.dV_D1") * r1 * occ1 + params.get("rec.dV_D2") * r2 * occ2
    gain = 1 + params.get("rec.gamma_D1") * r1 * occ1 - params.get("rec.gamma_D2") * r2 * occ2
    return d_v, gain, occ1, occ2
