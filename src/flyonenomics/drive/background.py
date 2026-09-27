"""Provisional per-super-class background drive and fixed-array K1 descent."""

from __future__ import annotations

import argparse
import datetime
import json
import time
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Literal

import numpy as np
import yaml
from pydantic import Field, model_validator

from flyonenomics.orchestrator.seeds import brian_seed as _brian_seed
from flyonenomics.registry import Registry, build_registry
from flyonenomics.types import StrictModel, load_params
from flyonenomics.validation.artefacts import FanoAccumulator

if TYPE_CHECKING:
    from flyonenomics.engine.base import Engine

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_SEED = 20260912
INITIAL_WEIGHT_MV = 0.5
BRACKET_UPPER_MV = 0.95
BRACKET_POINTS = 8
TRANSITION_BISECTIONS = 4
GROUP_STEP_MV = 0.05
K1B_MIN_STEP_MV = 0.001  # WP3b attempt-3 coordinate-search resolution
HOT_MULTIPLIER = 2.0
MIN_OBSERVED_RATE_HZ = 1.0  # one observed spike, divided by group-neuron seconds
K1_MEASURE_S = 5.0  # SPEC 3.3 window, not a fitted model constant
CALIBRATION_STATE = "base arrays (v_th everywhere, gain 1), layer A off"
_BG_MIN_MV, _BG_MAX_MV = (float(part.strip()) for part in
                            load_params().row("bg.w_bg")["range"].split("to"))

MALE_DRIVE_GROUPS: dict[str, str] = {
    "ascending_neuron": "ascending",
    "efferent_ascending": "ascending",
    "descending_neuron": "descending",
    "efferent_descending": "descending",
    "cb_intrinsic": "central",
    "vnc_intrinsic": "central",
    "ol_intrinsic": "optic",
    "cb_endocrine": "endocrine",
    "vnc_endocrine": "endocrine",
    "cb_motor": "motor",
    "vnc_motor": "motor",
    "cb_efferent": "motor",
    "vnc_efferent": "motor",
    "cb_sensory": "sensory",
    "ol_sensory": "sensory",
    "vnc_sensory": "sensory",
    "sensory_ascending": "sensory",
    "sensory_ascending_tbc": "sensory",
    "sensory_descending": "sensory",
    "visual_centrifugal": "visual_centrifugal",
    "visual_projection": "visual_projection",
    "visual_projection_tbc": "visual_projection",
}


class DriveGroup(StrictModel):
    """One drive group. Units: w_bg mV, rates Hz; shape: scalar fields."""

    size: int = Field(ge=1)
    w_bg: float
    target_hz: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    measured_hz: float = Field(ge=0, allow_inf_nan=False)

    @model_validator(mode="after")
    def check_weight(self) -> DriveGroup:
        """Apply the parameter-file mV bounds; shape one scalar."""
        if not _BG_MIN_MV <= self.w_bg <= _BG_MAX_MV:
            raise ValueError("w_bg outside parameter-file range")
        return self


class DriveTable(StrictModel):
    """K1 drive record. Units: per group; shape: one mapping over groups."""

    drive_version: Literal["dev"]
    configuration_class: Literal["development"]
    g_inh: float = Field(default=1.0, ge=1, allow_inf_nan=False)
    groups: dict[str, DriveGroup]
    objective: float = Field(ge=0, allow_inf_nan=False)
    evaluation_count: int = Field(ge=0)
    seed: int
    date: str
    params_version: str
    receptor_map_version: str
    arrays_note: str
    calibration_state: str
    qualified: Literal[False]
    synchrony: dict[str, float | str | None]
    misses: list[str]
    wall_s: float = Field(ge=0, allow_inf_nan=False)

    @model_validator(mode="after")
    def check_groups(self) -> DriveTable:
        """Require an undriven sensory group; units mV/Hz, shape one group."""
        sensory = self.groups.get("sensory")
        if sensory is None or sensory.w_bg != 0 or sensory.target_hz is not None:
            raise ValueError("sensory group must have zero weight and no target")
        if any(group.target_hz is None for name, group in self.groups.items() if name != "sensory"):
            raise ValueError("each nonsensory group needs a target")
        return self


@lru_cache(maxsize=4)
def group_indices(registry: Registry) -> dict[str, np.ndarray]:
    """Map groups to engine indices. Units: indices; shapes: each (group size,)."""
    from flyonenomics.registry.annotations import load_dataset_annotations

    frame = load_dataset_annotations(registry.connectome_version).set_index("root_id").reindex(registry.root_ids)
    if frame["super_class"].isna().any():
        raise ValueError("missing super_class for a model neuron")
    names = frame["super_class"].to_numpy(dtype=str)
    if registry.connectome_version == "male-cns:v1.0":
        # Vocabulary translation fixed from release anatomy before calibration.
        # The FlyWire drive's broad groups remain the conceptual groups; the
        # MaleCNS release subdivides them by CNS region and direction.
        unknown = sorted(set(names) - set(MALE_DRIVE_GROUPS))
        if unknown:
            raise ValueError(f"unmapped MaleCNS drive super_class values: {unknown}")
        names = np.asarray([MALE_DRIVE_GROUPS[name] for name in names], dtype=str)
    for population, group in (("DAN", "DAN"), ("CX_DAN", "DAN"), ("KC", "KC"), ("ER", "ER")):
        names[registry.population(population).idx] = group
    return {name: np.flatnonzero(names == name).astype(np.int32) for name in sorted(set(names))}


def background_weights(registry: Registry, drive: DriveTable | dict[str, object]) -> np.ndarray:
    """Expand per-group background weights in mV; shape: (registry.n,)."""
    if isinstance(drive, dict):
        drive = DriveTable.model_validate(drive)
    indices = group_indices(registry)
    if set(indices) != set(drive.groups):
        raise ValueError("drive groups do not match registry")
    weights = np.zeros(registry.n, dtype=np.float64)
    for name, idx in indices.items():
        group = drive.groups[name]
        if group.size != idx.size:
            raise ValueError(f"drive group size mismatch: {name}")
        weights[idx] = group.w_bg
    return weights


def weight_scale(signs_or_engine: np.ndarray, g_inh: float) -> np.ndarray:
    """Scale inhibitory connection magnitudes; input signs (n_syn,), output float32 (n_syn,)."""
    signs = np.asarray(signs_or_engine)
    if signs.ndim != 1 or not np.issubdtype(signs.dtype, np.number) or not np.all(np.isfinite(signs)):
        raise ValueError("connection signs must be a finite numeric vector")
    if not np.isfinite(g_inh) or g_inh < 1:
        raise ValueError("g_inh must be finite and at least one")
    return np.where(signs < 0, g_inh, 1.0).astype(np.float32)


def _connection_signs(connectivity: Path) -> np.ndarray:
    """Read signed connection counts in parquet order; shape (n_syn,), no units."""
    from flyonenomics.engine.brian_engine import resolve_connectome_path
    from flyonenomics.io import read_parquet

    path = resolve_connectome_path(connectivity)

    return read_parquet(path, columns=["Excitatory x Connectivity"]).to_pandas()["Excitatory x Connectivity"].to_numpy()


def load_drive(path: str | Path = ROOT / "data/drive-dev.yaml") -> DriveTable:
    """Read a drive YAML record. Units: mV and Hz; shape: one table."""
    from flyonenomics.io import read_yaml

    return DriveTable.model_validate(read_yaml(path))


def calibrate(engine: Engine, registry: Registry, targets: dict[str, float], seed: int, max_evals: int,
              v_th_mv: np.ndarray, gain: np.ndarray) -> DriveTable:
    """Run capped K1 on fixed (n,) threshold mV and gain arrays; return drive table."""
    params = load_params()
    indices = group_indices(registry)
    if engine.n != registry.n or v_th_mv.shape != (engine.n,) or gain.shape != (engine.n,):
        raise ValueError("engine, registry, threshold, and gain shapes differ")
    if set(targets) != set(indices) - {"sensory"} or any(x <= 0 for x in targets.values()):
        raise ValueError("targets must cover every nonsensory group")
    if not np.all(np.isfinite(v_th_mv)) or not np.all(np.isfinite(gain)):
        raise ValueError("fixed threshold and gain arrays must be finite")
    if max_evals < 1:
        raise ValueError("max_evals must be positive")
    settle_ms = float(params.get("settle.min_s")) * 1000
    measure_ms = K1_MEASURE_S * 1000
    chunk_ms = float(params.get("engine.chunk_ms"))
    weights = {name: (0.0 if name == "sensory" else INITIAL_WEIGHT_MV) for name in indices}
    best_weights = dict(weights)
    best_score = float("inf")
    best_rates: dict[str, float] = {}
    best_sync: dict[str, float | str | None] = {"status": "unknown", "F": None, "max_bin_fraction": None}
    eval_count = 0
    began = time.perf_counter()

    def evaluate(candidate: dict[str, float], phase: str) -> tuple[float, dict[str, float]]:
        nonlocal eval_count, best_score, best_weights, best_rates, best_sync
        started = time.perf_counter()
        engine.restore("initial")
        engine.seed(_brian_seed(seed, 0, 0))
        engine.set_threshold(v_th_mv.copy())
        engine.set_gain(gain.copy())
        vector = np.zeros(engine.n, dtype=np.float64)
        for name, idx in indices.items():
            vector[idx] = candidate[name]
        engine.set_background(vector)
        for _ in range(round(settle_ms / chunk_ms)):
            engine.run_chunk(chunk_ms)
        counts = np.zeros(engine.n, dtype=np.int64)
        fano = FanoAccumulator(engine.n, params)
        for _ in range(round(measure_ms / chunk_ms)):
            result = engine.run_chunk(chunk_ms)
            counts += result.counts
            fano.add(result.hist_1ms)
        rates = {name: float(counts[idx].mean() / (measure_ms / 1000)) for name, idx in indices.items()}
        sync = fano.report()
        ignited = any(rates[name] > HOT_MULTIPLIER * targets[name]
                      for name in ("central", "DAN", "KC") if name in targets)
        score = sum(float(np.log(max(rates[name], MIN_OBSERVED_RATE_HZ / (idx.size * (measure_ms / 1000))) / targets[name]) ** 2)
                    for name, idx in indices.items() if name != "sensory")
        if sync["status"] == "tripped" or ignited:
            score = float("inf")
        if score < best_score:
            best_score, best_weights, best_rates, best_sync = score, dict(candidate), rates, sync
        eval_count += 1
        print(json.dumps({"evaluation": eval_count, "phase": phase, "weights_mv": candidate, "rates_hz": rates,
                          "objective": score if np.isfinite(score) else None, "synchrony": sync,
                          "ignited": ignited,
                          "wall_s": round(time.perf_counter() - started, 3)}), flush=True)
        return score, rates

    low: list[tuple[float, float, dict[str, float]]] = []
    rejected_scales: list[float] = []
    for scale in np.geomspace(INITIAL_WEIGHT_MV, BRACKET_UPPER_MV, min(max_evals, BRACKET_POINTS)):
        candidate = {name: (0.0 if name == "sensory" else float(scale)) for name in indices}
        score, rates = evaluate(candidate, "common-scale bracket")
        if np.isfinite(score):
            low.append((float(scale), score, rates))
        else:
            rejected_scales.append(float(scale))
    if not low:
        raise RuntimeError("K1 found no synchrony-feasible low-rate evaluation")
    lower = max(point[0] for point in low)
    higher = [scale for scale in rejected_scales if scale > lower]
    if higher:
        upper = min(higher)
        for _ in range(min(TRANSITION_BISECTIONS, max_evals - eval_count)):
            scale = float(np.sqrt(lower * upper))
            candidate = {name: (0.0 if name == "sensory" else scale) for name in indices}
            score, rates = evaluate(candidate, "transition bisection")
            if np.isfinite(score):
                low.append((scale, score, rates))
                lower = scale
            else:
                upper = scale
    central_target = targets.get("central")
    near = [point for point in low if central_target is not None and
            0.5 * central_target <= point[2]["central"] <= 2.0 * central_target]
    selected_scale, current_score, current_rates = max(near or low, key=lambda point: point[0])
    weights = {name: (0.0 if name == "sensory" else selected_scale) for name in indices}
    priority = [name for name in ("DAN", "KC", "central") if name in targets]
    priority.extend(name for name in targets if name not in priority)
    for name in priority:
        if eval_count >= max_evals:
            break
        chosen = dict(weights)
        chosen_rates = current_rates
        local_score = current_score
        for direction in (-1, 1):
            if eval_count >= max_evals:
                break
            candidate = dict(weights)
            candidate[name] = min(_BG_MAX_MV, max(_BG_MIN_MV, weights[name] + direction * GROUP_STEP_MV))
            score, rates = evaluate(candidate, "bidirectional coordinate")
            if score <= local_score:
                chosen, chosen_rates, local_score = candidate, rates, score
        weights, current_rates, current_score = chosen, chosen_rates, local_score
    steps = {name: GROUP_STEP_MV for name in priority}
    focus = priority[:3] or priority
    focus_index = 0
    while eval_count < max_evals:
        name = focus[focus_index % len(focus)]
        focus_index += 1
        direction = 1 if current_rates[name] < targets[name] else -1
        candidate = dict(weights)
        candidate[name] = min(_BG_MAX_MV, max(_BG_MIN_MV, weights[name] + direction * steps[name]))
        if candidate == weights:
            break
        score, rates = evaluate(candidate, "focused refinement")
        if score < current_score:
            weights, current_rates, current_score = candidate, rates, score
        else:
            steps[name] *= 0.5
    if not best_rates:
        raise RuntimeError("K1 found no synchrony-feasible evaluation")
    misses = [name for name in targets if not 0.5 * targets[name] <= best_rates[name] <= 2 * targets[name]]
    groups = {name: DriveGroup(size=int(idx.size), w_bg=best_weights[name],
        target_hz=targets.get(name), measured_hz=best_rates[name]) for name, idx in indices.items()}
    return DriveTable(drive_version="dev", configuration_class="development", groups=groups,
        objective=best_score, evaluation_count=eval_count, seed=seed,
        date=datetime.date.today().isoformat(), params_version="v0.1", receptor_map_version="v0.1",
        arrays_note="caller-supplied fixed threshold and gain arrays",
        calibration_state="fixed arrays supplied by caller; no tonic-state qualification",
        qualified=False, synchrony=best_sync, misses=misses, wall_s=time.perf_counter() - began)


def _calibrate_k1b(engine: Engine, registry: Registry, targets: dict[str, float], seed: int,
                   max_evals: int, v_th_mv: np.ndarray, gain: np.ndarray,
                   start_weight_mv: float, g_inh: float) -> DriveTable:
    """Run WP3b K1 from a mapped common mV weight; fixed arrays shape (n,), rates Hz."""
    params = load_params()
    indices = group_indices(registry)
    if engine.n != registry.n or v_th_mv.shape != (engine.n,) or gain.shape != (engine.n,):
        raise ValueError("engine, registry, threshold, and gain shapes differ")
    if set(targets) != set(indices) - {"sensory"} or any(x <= 0 for x in targets.values()):
        raise ValueError("targets must cover every nonsensory group")
    if max_evals < 1 or not np.isfinite(start_weight_mv) or not _BG_MIN_MV <= start_weight_mv <= _BG_MAX_MV \
            or not np.isfinite(g_inh) or g_inh < 1:
        raise ValueError("invalid evaluation cap, start weight, or inhibitory ratio")
    settle_ms = float(params.get("settle.min_s")) * 1000
    measure_ms = K1_MEASURE_S * 1000
    chunk_ms = float(params.get("engine.chunk_ms"))
    current = {name: (0.0 if name == "sensory" else start_weight_mv) for name in indices}
    current_score = float("inf")
    current_rates: dict[str, float] = {}
    best_score = float("inf")
    best_weights = dict(current)
    best_rates: dict[str, float] = {}
    best_sync: dict[str, float | str | None] = {"status": "unknown", "F": None, "max_bin_fraction": None}
    evaluation_count = 0
    began = time.perf_counter()

    def evaluate(candidate: dict[str, float], phase: str) -> tuple[float, dict[str, float]]:
        """Score one restored candidate; mV group weights and Hz group rates."""
        nonlocal evaluation_count, best_score, best_weights, best_rates, best_sync
        started = time.perf_counter()
        engine.restore("initial")
        engine.seed(_brian_seed(seed, 0, 0))
        engine.set_threshold(v_th_mv.copy())
        engine.set_gain(gain.copy())
        vector = np.zeros(engine.n, dtype=np.float64)
        for name, idx in indices.items():
            vector[idx] = candidate[name]
        engine.set_background(vector)
        for _ in range(round(settle_ms / chunk_ms)):
            engine.run_chunk(chunk_ms)
        counts = np.zeros(engine.n, dtype=np.int64)
        fano = FanoAccumulator(engine.n, params)
        for _ in range(round(measure_ms / chunk_ms)):
            result = engine.run_chunk(chunk_ms)
            counts += result.counts
            fano.add(result.hist_1ms)
        rates = {name: float(counts[idx].mean() / (measure_ms / 1000)) for name, idx in indices.items()}
        sync = fano.report()
        score = sum(float(np.log(max(rates[name], MIN_OBSERVED_RATE_HZ / (idx.size * (measure_ms / 1000)))
                                 / targets[name]) ** 2)
                    for name, idx in indices.items() if name != "sensory")
        if sync["status"] != "clear":
            score = float("inf")
        if score < best_score:
            best_score, best_weights, best_rates, best_sync = score, dict(candidate), rates, sync
        evaluation_count += 1
        print(json.dumps({"evaluation": evaluation_count, "phase": phase, "g_inh": g_inh,
                          "weights_mv": candidate, "rates_hz": rates,
                          "objective": score if np.isfinite(score) else None,
                          "synchrony": sync, "wall_s": round(time.perf_counter() - started, 3)}),
              flush=True)
        return score, rates

    current_score, current_rates = evaluate(current, "mapped common start")
    priority = [name for name in ("DAN", "KC", "central") if name in targets]
    priority.extend(name for name in targets if name not in priority)
    for name in priority:
        if evaluation_count >= max_evals:
            break
        chosen, chosen_score, chosen_rates = current, current_score, current_rates
        for direction in (-1, 1):
            if evaluation_count >= max_evals:
                break
            candidate = dict(current)
            candidate[name] = min(_BG_MAX_MV, max(_BG_MIN_MV, current[name] + direction * GROUP_STEP_MV))
            score, rates = evaluate(candidate, "bidirectional coordinate")
            if score < chosen_score:
                chosen, chosen_score, chosen_rates = candidate, score, rates
        current, current_score, current_rates = chosen, chosen_score, chosen_rates
    steps = {name: GROUP_STEP_MV for name in priority}
    while evaluation_count < max_evals:
        if np.isfinite(best_score):
            current, current_score, current_rates = dict(best_weights), best_score, best_rates
        ranked = sorted(priority, key=lambda name: abs(np.log(max(current_rates.get(name, 0),
            MIN_OBSERVED_RATE_HZ / (indices[name].size * K1_MEASURE_S)) / targets[name])), reverse=True)
        name = ranked[(evaluation_count - 1) % min(len(ranked), 3)]
        direction = 1 if current_rates.get(name, 0) < targets[name] else -1
        candidate = dict(current)
        candidate[name] = min(_BG_MAX_MV, max(_BG_MIN_MV, current[name] + direction * steps[name]))
        if candidate == current or steps[name] < K1B_MIN_STEP_MV:
            break
        score, rates = evaluate(candidate, "targeted refinement")
        if score < current_score:
            current, current_score, current_rates = candidate, score, rates
        else:
            steps[name] *= 0.5
    if not best_rates:
        raise RuntimeError("K1b found no synchrony-clear evaluation")
    misses = [name for name in targets if not 0.5 * targets[name] <= best_rates[name] <= 2 * targets[name]]
    groups = {name: DriveGroup(size=int(idx.size), w_bg=best_weights[name],
        target_hz=targets.get(name), measured_hz=best_rates[name]) for name, idx in indices.items()}
    return DriveTable(drive_version="dev", configuration_class="development", g_inh=g_inh,
        groups=groups, objective=best_score, evaluation_count=evaluation_count, seed=seed,
        date=datetime.date.today().isoformat(), params_version="v0.1", receptor_map_version="v0.1",
        arrays_note="base arrays, layer A off", calibration_state=f"{CALIBRATION_STATE}; g_inh={g_inh:g}",
        qualified=False, synchrony=best_sync, misses=misses, wall_s=time.perf_counter() - began)


def _k1_unavailable() -> dict[str, str]:
    """Report missing tonic arrays. Units: none; shapes: scalar mapping."""
    return {"status": "unavailable", "reason": "the calibration state needs the tonic arrays of WP5's Neuromod"}


def run_dev(g_inh: float = 1.0, start_weight_mv: float | None = None) -> dict[str, str]:
    """Calibrate v783 base arrays at inhibitory ratio; mV/Hz, arrays shape (n,)."""
    from flyonenomics.engine import BrianEngine, InputTopology
    from flyonenomics.validation.level0 import connectome

    if not np.isfinite(g_inh) or g_inh < 1:
        raise ValueError("g_inh must be finite and at least one")
    if start_weight_mv is not None and (not np.isfinite(start_weight_mv)
                                         or not _BG_MIN_MV <= start_weight_mv <= _BG_MAX_MV):
        raise ValueError("start weight outside the background mV range")
    params = load_params()
    registry = build_registry("783")
    groups = group_indices(registry)
    targets = {name: float(params.get(f"bg.target.{name if name in ('central', 'DAN', 'KC', 'ER', 'descending', 'motor') else 'other'}"))
               for name in groups if name != "sensory"}
    engine = BrianEngine()
    engine.seed(_brian_seed(DEFAULT_SEED, 0, 0))
    engine.build(connectome("783"), params, InputTopology(background=True))
    if g_inh > 1:
        engine.set_weight_scale(weight_scale(_connection_signs(connectome("783").connectivity), g_inh))
    threshold = np.full(engine.n, float(params.get("lif.v_th")))
    gain = np.ones(engine.n)
    engine.set_threshold(threshold)
    engine.set_gain(gain)
    initial_weight = INITIAL_WEIGHT_MV if start_weight_mv is None else start_weight_mv
    initial_background = np.full(engine.n, initial_weight)
    initial_background[groups["sensory"]] = 0.0
    engine.set_background(initial_background)
    engine.store("initial")
    if g_inh == 1:
        drive = calibrate(engine, registry, targets, DEFAULT_SEED, int(params.get("bg.k1_max_evals")),
                          threshold, gain)
    else:
        drive = _calibrate_k1b(engine, registry, targets, DEFAULT_SEED,
                              int(params.get("bg.k1_max_evals")), threshold, gain,
                              initial_weight, g_inh)
    if g_inh == 1:
        drive = drive.model_copy(update={"arrays_note": "base arrays, layer A off",
                                         "calibration_state": CALIBRATION_STATE})
    destination = ROOT / "data/drive-dev.yaml"
    destination.write_text(yaml.safe_dump(drive.model_dump(), sort_keys=False))
    return {"status": "recorded", "path": str(destination), "evaluations": str(drive.evaluation_count)}


STAGE: dict[str, object] = {}  # WP5 registers item-47 skipped K1; development K1 remains below.
DEV_STAGE = {"K1-dev": run_dev}


def main() -> None:
    """Run provisional K1 via --dev. Units: mV/Hz; shapes: one drive table."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--dev", action="store_true", required=True)
    parser.add_argument("--g-inh", type=float, default=1.0)
    parser.add_argument("--start-mv", type=float)
    args = parser.parse_args()
    print(json.dumps(run_dev(args.g_inh, args.start_mv)), flush=True)


if __name__ == "__main__":
    main()
