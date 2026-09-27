"""Paired seed contrasts retained by the measured Phase 2 neural entries."""
from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from flyonenomics.orchestrator.seeds import ANALYSIS, stream

BOOTSTRAP_QUANTILES = (0.025, 0.975)


def analysis_rng(seed: int) -> np.random.Generator:
    """Return the ANALYSIS stream at s=0, k=0; experiment seed, scalar."""
    return stream(int(seed), 0, 0, ANALYSIS)


def paired_difference(left: NDArray[np.float64], right: NDArray[np.float64]) -> NDArray[np.float64]:
    """Return left minus right per seed; metric units, shape (n_seed,)."""
    if left.shape != right.shape or not left.size:
        raise ValueError("paired difference needs nonempty aligned seed vectors")
    return left - right


def bootstrap_mean_interval(values: NDArray[np.float64], rng: np.random.Generator,
                            n_boot: int) -> tuple[float, list[float], NDArray[np.float64]]:
    """Mean and bootstrap 95 percent interval of the seed mean; metric units."""
    if not values.size or n_boot < 1:
        raise ValueError("bootstrap requires seeds and resamples")
    indices = rng.integers(0, len(values), size=(n_boot, len(values)))
    draws = values[indices].mean(axis=1)
    mean = float(values.mean())
    interval = np.quantile(draws, BOOTSTRAP_QUANTILES).tolist()
    return mean, interval, draws
