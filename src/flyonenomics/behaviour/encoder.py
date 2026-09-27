"""Visual stripe geometry and extended-input rates."""
from __future__ import annotations

from typing import Any, Literal

import numpy as np
from numpy.typing import NDArray
from scipy.special import erf

from flyonenomics.behaviour.metrics import wrap
from flyonenomics.types import Params

# SPEC-P2 section 3.2 / 8.2 defaults used when params-v0.2.yaml is not pinned.
PR_RATE_DARK_HZ = 0.0
PR_ACCEPTANCE_DEG = 5.0
EYE_SPAN_DEG = 150.0


def preferred_azimuths(root_ids: NDArray[np.int64], sides: NDArray[np.str_], pref_range: tuple[float, float]) -> NDArray[np.float64]:
    """Assign preferred fly-relative azimuths (degrees, n neurons) on an even ipsilateral grid by ascending root ID."""
    result = np.full(len(root_ids), np.nan)
    for side in ("left", "right", "center", "na"):
        idx = np.flatnonzero(sides == side)
        if not len(idx):
            continue
        ordered = idx[np.argsort(root_ids[idx])]
        if side == "left":
            values = -np.linspace(pref_range[0], pref_range[1], len(idx))
        elif side == "right":
            values = np.linspace(pref_range[0], pref_range[1], len(idx))
        else:
            values = np.linspace(-pref_range[1], pref_range[1], len(idx))
        result[ordered] = values
    if np.isnan(result).any():
        raise ValueError("unknown side in injection population")
    return result


def retinotopy_azimuths_for(root_ids: NDArray[np.int64]) -> NDArray[np.float64]:
    """Look up WP14 R1-6 azimuths by root_id. Units: degrees. Shapes: (n,)."""
    from flyonenomics.substrate.retinotopy import load_retinotopy

    table = load_retinotopy()
    payload = table["types"]["R1_6"]
    by_root = {
        int(root): (np.nan if az is None else float(az))
        for root, az in zip(payload["root_ids"], payload["azimuth_deg"])
    }
    missing = [int(root) for root in root_ids if int(root) not in by_root]
    if missing:
        raise ValueError(f"R1-6 retinotopy missing {len(missing)} root_ids")
    return np.array([by_root[int(root)] for root in root_ids], dtype=np.float64)


def apply_within_eye_permutation(encoder: Any, k: int) -> None:
    """Apply WP16 within-eye R1-6 azimuth shuffles. Units: degrees. Shapes: (n,)."""
    from flyonenomics.validation.artefacts import within_eye_azimuth_shuffles

    count = int(encoder.params.get("artefact.encoder_perms"))
    if not 0 <= k <= count:
        raise ValueError("permutation index out of range")
    if k == 0:
        encoder.preferred = encoder.base_preferred.copy()
        return
    if encoder.stream is None and getattr(encoder, "encoder_seed", None) is None:
        raise ValueError("ENCODER stream not set")
    if encoder._permutations is None:
        seed = encoder.encoder_seed
        if seed is None:
            seed = 0
        encoder._permutations = [
            np.asarray(row, dtype=np.float64)
            for row in within_eye_azimuth_shuffles(
                encoder.base_preferred, encoder.sides, int(seed), params=encoder.params,
            )
        ]
    encoder.preferred = encoder._permutations[k - 1].copy()


class VisualEncoder:
    """Gaussian stripe encoder, rates Hz (n_extended,) from fly-relative stimuli."""

    def __init__(self, registry: Any, extended_idx: NDArray[np.int32], params: Params, population: str) -> None:
        """Map one population's engine indices to sorted extended-input positions; arrays (n_neurons,)."""
        pop = registry.population(population)
        if not len(pop.idx):
            raise ValueError(f"{population} injection population is empty")
        self.params = params
        self.population = population
        self.extended_idx = extended_idx
        self.positions = np.searchsorted(extended_idx, pop.idx)
        if np.any(self.positions >= len(extended_idx)) or not np.array_equal(extended_idx[self.positions], pop.idx):
            raise ValueError(f"{population} absent from extended input union")
        if population == "TuBu":
            self.preferred = preferred_azimuths(pop.root_ids, pop.side, tuple(params.get("vis.pref_range")))
        else:
            order = np.argsort(pop.root_ids)
            self.preferred = np.empty(len(pop.idx), dtype=float)
            self.preferred[order] = np.linspace(-180, 180, len(pop.idx), endpoint=False)
        self.sides = np.asarray(pop.side)
        self.base_preferred = self.preferred.copy()
        self.stream: np.random.Generator | None = None
        self.encoder_seed: int | None = None
        self._permutations: list[NDArray[np.float64]] | None = None

    def permutation(self, k: int) -> None:
        """Select within-eye reassignment k (0 is original); degrees array (n_neurons,)."""
        apply_within_eye_permutation(self, k)

    def rates(self, stimuli: list[dict[str, float]], enabled: bool = True, *,
              maximum_hz: float | None = None, sigma_deg: float | None = None) -> NDArray[np.float64]:
        """Return capped visual input in Hz (n_extended,) from stimuli az_fly degrees and contrast unitless."""
        output = np.zeros(len(self.extended_idx), dtype=float)
        if not enabled or not stimuli:
            return output
        maximum = self.params.get("vis.r_vis_max") if maximum_hz is None else maximum_hz
        sigma = self.params.get("vis.sigma_vis") if sigma_deg is None else sigma_deg
        if not np.isfinite(maximum) or maximum < 0 or not np.isfinite(sigma) or sigma <= 0:
            raise ValueError("encoder maximum must be nonnegative Hz and sigma positive degrees")
        value = np.zeros(len(self.preferred), dtype=float)
        for stimulus in stimuli:
            contrast = stimulus["contrast"]
            if contrast <= 0:
                continue
            difference = wrap(stimulus["az_fly"] - self.preferred)
            value += contrast * np.exp(-np.square(difference) / (2 * sigma * sigma))
        output[self.positions] = np.minimum(maximum, maximum * value)
        return output


def midpoint_rank_azimuths(
    sides: NDArray[np.str_],
    anterior_coord: NDArray[np.floating],
    span_deg: float = EYE_SPAN_DEG,
) -> NDArray[np.float64]:
    """Map per-eye z rank to fly-relative azimuth in degrees (n,).

    SPEC-P2 section 3.2: rank r of n maps to (r + 0.5) / n × span in the
    right eye and the negative of that in the left eye. Smaller z is
    anterior (rank 0). Units: anterior_coord is the z section index;
    output is degrees. Shapes: (n,).
    """
    if len(sides) != len(anterior_coord):
        raise ValueError("sides and anterior_coord must have the same length")
    if not np.isfinite(span_deg) or span_deg <= 0:
        raise ValueError("eye span must be positive degrees")
    result = np.full(len(sides), np.nan, dtype=np.float64)
    z = np.asarray(anterior_coord, dtype=np.float64)
    for side in ("left", "right", "center", "na"):
        idx = np.flatnonzero(np.asarray(sides) == side)
        if not len(idx):
            continue
        order_local = np.argsort(z[idx], kind="stable")
        ordered = idx[order_local]
        count = len(idx)
        ranks = (np.arange(count, dtype=np.float64) + 0.5) / count * span_deg
        if side == "left":
            result[ordered] = -ranks
        elif side == "right":
            result[ordered] = ranks
        else:
            result[ordered] = np.linspace(-span_deg, span_deg, count, endpoint=False) + span_deg / count
    if np.isnan(result).any():
        raise ValueError("unknown side in retinotopic assignment")
    return result


def bar_occupancy(
    preferred_deg: NDArray[np.floating],
    az_fly_deg: float,
    width_deg: float,
    acceptance_deg: float,
) -> NDArray[np.float64]:
    """Return Gaussian-acceptance occupancy u(φ) in [0, 1] (n,).

    SPEC-P2 section 3.2. Units: degrees. Shapes: preferred (n,); output (n,).
    """
    if not np.isfinite(width_deg) or width_deg < 0:
        raise ValueError("bar width must be nonnegative degrees")
    if not np.isfinite(acceptance_deg) or acceptance_deg <= 0:
        raise ValueError("acceptance angle must be positive degrees")
    difference = np.asarray(wrap(np.asarray(preferred_deg, dtype=np.float64) - float(az_fly_deg)), dtype=np.float64)
    scale = np.sqrt(2.0) * float(acceptance_deg)
    half = float(width_deg) / 2.0
    occupancy = 0.5 * (erf((difference + half) / scale) - erf((difference - half) / scale))
    return np.clip(occupancy, 0.0, 1.0)


def luminance(
    preferred_deg: NDArray[np.floating],
    stimuli: list[dict[str, float]],
    acceptance_deg: float,
) -> NDArray[np.float64]:
    """Return wall luminance L(φ) in [0, 1] (n,) for dark bars on a bright wall.

    SPEC-P2 section 3.2. Contrast is unitless in [0, 1]. Width and azimuth
    are degrees. Empty stimuli give L = 1.
    """
    value = np.ones(len(preferred_deg), dtype=np.float64)
    azimuths = np.asarray(preferred_deg, dtype=np.float64)
    for stimulus in stimuli:
        contrast = float(stimulus["contrast"])
        if contrast <= 0:
            continue
        if contrast > 1 or not np.isfinite(contrast):
            raise ValueError("bar contrast must be in [0, 1]")
        width = float(stimulus["width"])
        occupancy = bar_occupancy(azimuths, float(stimulus["az_fly"]), width, acceptance_deg)
        value -= contrast * occupancy
    return np.maximum(0.0, value)


def photoreceptor_input_rates(
    preferred_deg: NDArray[np.floating],
    stimuli: list[dict[str, float]],
    *,
    r_light: float,
    r_dark: float = PR_RATE_DARK_HZ,
    acceptance_deg: float = PR_ACCEPTANCE_DEG,
    r_max: float,
    kind: Literal["stripe", "ambient", "dark"] = "stripe",
) -> NDArray[np.float64]:
    """Return Poisson input rates in Hz (n,) from SPEC-P2 section 3.2.

    kind ambient (and empty stripe stimuli) give L = 1. kind dark gives
    r_dark at every photoreceptor. r_light, r_dark and r_max are Hz;
    acceptance_deg is degrees.
    """
    if not np.isfinite(r_light) or r_light < 0 or not np.isfinite(r_dark) or r_dark < 0:
        raise ValueError("photoreceptor rates must be nonnegative Hz")
    if not np.isfinite(r_max) or r_max < 0:
        raise ValueError("encoder maximum must be nonnegative Hz")
    n = len(preferred_deg)
    if kind == "dark":
        values = np.full(n, r_dark, dtype=np.float64)
    elif kind == "ambient" or not stimuli:
        values = np.full(n, r_dark + (r_light - r_dark) * 1.0, dtype=np.float64)
    elif kind == "stripe":
        wall = luminance(preferred_deg, stimuli, acceptance_deg)
        values = r_dark + (r_light - r_dark) * wall
    else:
        raise ValueError("stimulus kind must be stripe, ambient or dark")
    return np.minimum(r_max, values)


class PhotoreceptorEncoder:
    """Dark-bar photoreceptor encoder, rates Hz (n_extended,) from fly-relative stimuli.

    WP15 dispatches this class when inject_at is photoreceptors. Preferred
    azimuths come from the WP14 retinotopy table or an explicit array.
    encoder off and stripes false both give ambient light (L = 1).
    """

    mode = "photoreceptors"
    population_name = "R1_6"

    def __init__(
        self,
        registry: Any,
        extended_idx: NDArray[np.int32],
        params: Params,
        population: str = "R1_6",
        *,
        preferred: NDArray[np.floating] | None = None,
        r_light: float | None = None,
        r_dark: float = PR_RATE_DARK_HZ,
        acceptance_deg: float = PR_ACCEPTANCE_DEG,
    ) -> None:
        """Map R1-6 engine indices onto extended input; azimuths degrees (n,)."""
        pop = registry.population(population)
        if not len(pop.idx):
            raise ValueError(f"{population} injection population is empty")
        self.params = params
        self.population = population
        self.extended_idx = extended_idx
        self.r_light = r_light
        self.r_dark = r_dark
        self.acceptance_deg = acceptance_deg
        self.positions = np.searchsorted(extended_idx, pop.idx)
        if np.any(self.positions >= len(extended_idx)) or not np.array_equal(extended_idx[self.positions], pop.idx):
            raise ValueError(f"{population} absent from extended input union")
        self.sides = np.asarray(pop.side)
        if preferred is not None:
            azimuths = np.asarray(preferred, dtype=np.float64)
            if azimuths.shape != (len(pop.idx),):
                raise ValueError("preferred azimuths must match the injection population")
            self.preferred = azimuths
        elif getattr(pop, "azimuth_deg", None) is not None:
            self.preferred = np.asarray(pop.azimuth_deg, dtype=np.float64)
            if self.preferred.shape != (len(pop.idx),):
                raise ValueError("population azimuth_deg must match the injection population")
        else:
            self.preferred = retinotopy_azimuths_for(np.asarray(pop.root_ids, dtype=np.int64))
        self.base_preferred = self.preferred.copy()
        self.stream: np.random.Generator | None = None
        self.encoder_seed: int | None = None
        self._permutations: list[NDArray[np.float64]] | None = None

    def permutation(self, k: int) -> None:
        """Select within-eye reassignment k (0 is original); degrees array (n_neurons,)."""
        apply_within_eye_permutation(self, k)

    def rates(
        self,
        stimuli: list[dict[str, float]],
        enabled: bool = True,
        *,
        maximum_hz: float | None = None,
        sigma_deg: float | None = None,
        r_light: float | None = None,
        r_dark: float | None = None,
        kind: Literal["stripe", "ambient", "dark"] = "stripe",
        lit: bool | None = None,
    ) -> NDArray[np.float64]:
        """Return capped photoreceptor input in Hz (n_extended,).

        enabled False is ambient light, not zeros (SPEC-P2 section 3.2 controls).
        lit False selects a dark open-loop block. maximum_hz is vis.r_max;
        sigma_deg is the acceptance angle.
        """
        output = np.zeros(len(self.extended_idx), dtype=np.float64)
        light = self.r_light if r_light is None else r_light
        if light is None:
            if maximum_hz is None:
                raise ValueError("r_light must be supplied until visual-v0.2.yaml is pinned")
            light = float(maximum_hz)
        dark = self.r_dark if r_dark is None else r_dark
        sigma = self.acceptance_deg
        if sigma_deg is not None:
            try:
                tubu_sigma = float(self.params.get("vis.sigma_vis"))
            except (KeyError, TypeError, ValueError):
                tubu_sigma = None
            if tubu_sigma is None or abs(float(sigma_deg) - tubu_sigma) > 1e-12:
                sigma = float(sigma_deg)
        maximum = float(self.params.get("vis.r_max") if maximum_hz is None else maximum_hz)
        names = [str(row.get("name", "")) for row in stimuli]
        stimulus_kind: Literal["stripe", "ambient", "dark"]
        if lit is False or kind == "dark" or (names and all(name == "dark" for name in names)):
            stimulus_kind = "dark"
        elif not enabled or kind == "ambient" or not stimuli or all(name == "ambient" for name in names):
            stimulus_kind = "ambient"
        else:
            stimulus_kind = "stripe"
        values = photoreceptor_input_rates(
            self.preferred, stimuli, r_light=light, r_dark=dark,
            acceptance_deg=sigma, r_max=float(maximum), kind=stimulus_kind,
        )
        output[self.positions] = values
        return output
