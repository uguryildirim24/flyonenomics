"""WP18 measurements inside the orchestrator's open_loop_steering assay.

The orchestrator owns engine construction, pinned configurations, seeds and
neuromodulation. VisualProbe only observes chunks and supplies the prescribed
2 s ambient settle. No second engine implementation or clamped dopamine pools.
Units: seconds, degrees, Hz, mV.
"""
from __future__ import annotations

from collections import deque
from pathlib import Path
from typing import Any

import numpy as np

from flyonenomics.diagnostics.visual_path import (
    V1_DEPTHS, bootstrap_mean_interval, evaluate_v1,
)
from flyonenomics.types import SettleRecord, load_params
from flyonenomics.validation.artefacts import FanoAccumulator, ignition_detector

REPO = Path(__file__).resolve().parents[3]
DRIVE_PATH = REPO / "data/drive-v0.2.yaml"
DOPAMINE_PATH = REPO / "data/dopamine-v0.2.yaml"
PARAMS_PATH = REPO / "data/params-v0.2.yaml"
DECLARED_INPUTS = (
    "data/drive-v0.2.yaml", "data/dopamine-v0.2.yaml", "data/params-v0.2.yaml",
    "data/populations-v0.2.yaml", "data/transmitters-v0.2.yaml",
    "data/receptors-v0.1.yaml", "data/compartments-v0.1.yaml",
    "data/behaviour-base-v0.2.yaml", "data/provenance.json",
)
V1_FIXTURE = "data/experiments/p2/vpath-v1.json"
V3_FIXTURE = "data/experiments/p2/vpath-v3.json"
VCAL_FIXTURE = "data/experiments/p2/vpath-vcal.json"
MASTER_SEED = 20260912
V_CAL_STAGE1_HZ = (50.0, 100.0, 150.0, 300.0)
V_CAL_STAGE2_HZ = (25.0, 10.0)
V3_SEEDS = V1_THREE_SEEDS = (1, 2, 3)
V1_SEEDS = tuple(range(1, 11))
SETTLE_S = 2.0
V1_POPULATIONS = tuple(dict.fromkeys(name for names in V1_DEPTHS.values() for name in names))
V3_RECORD = REPO / "validation/records/p2/V3.json"
V1_RECORD = REPO / "validation/records/p2/V1.json"
VCAL_RECORD = REPO / "validation/records/p2/visual-vcal.json"
VISUAL_PATH = REPO / "data/visual-v0.2.yaml"


def stage_subsets(registry: Any, params: Any, table: dict) -> dict:
    """Resolve ipsi/contra engine indices at probe start, separately for each bar.

    Only types passing the propagated-spread test get columns. Otherwise use
    annotation-side populations. Empty sides stay empty, never bilateral.
    """
    from flyonenomics.diagnostics.visual_path import column_subset_indices

    subsets = {}
    for name in V1_POPULATIONS:
        pop = registry.population(name)
        block = table["types"].get(name, {})
        columns = bool(block.get("column_subsets"))
        az = None
        if columns:
            by_root = dict(zip(block["root_ids"], block["azimuth_deg"], strict=True))
            az = np.array([by_root.get(int(root)) for root in pop.root_ids], dtype=float)
        subsets[name] = {}
        for bar in (45.0, -45.0):
            subsets[name][str(bar)] = {}
            for side, target in (("ipsilateral", bar), ("contralateral", -bar)):
                if columns:
                    positions = column_subset_indices(
                        az, pop.side, target,
                        halfwidth_deg=float(params.get("vis.column_halfwidth_deg")),
                    )
                else:
                    positions = np.flatnonzero(pop.side == ("right" if target > 0 else "left"))
                subsets[name][str(bar)][side] = np.asarray(pop.idx[positions], dtype=np.int32)
        subsets[name]["mode"] = "column" if columns else "side-wide"
    return subsets


def _rate(counts: np.ndarray, idx: np.ndarray, seconds: float) -> float:
    """Mean per-neuron Hz. Empty subset has no measured rate."""
    return float(counts[idx].sum() / (len(idx) * seconds)) if len(idx) else 0.0


class VisualProbe:
    """Chunk observer attached to an actual orchestrator probe, not a new runner."""

    def __init__(self, protocol: str, registry: Any, params: Any, phase: Any, groups: dict) -> None:
        from flyonenomics.substrate.retinotopy import load_retinotopy

        if protocol not in ("v1", "v3") or phase.assay != "open_loop_steering":
            raise ValueError("visual measurement requires a V1/V3 open-loop probe")
        blocks = phase.params.blocks
        expected = [("ambient", None, 1, 9)] if protocol == "v3" else [
            ("ambient", None, 1, 3), ("stripe", 45, 1, 3),
            ("ambient", None, 1, 3), ("stripe", -45, 1, 3),
        ]
        actual = [(b.stimulus, b.azimuth_deg, b.transition_s, b.dwell_s) for b in blocks]
        if actual != expected or phase.params.inject_at != "photoreceptors":
            raise ValueError("visual measurement requires the SPEC-P2 3.4 blocks and encoder")
        self.protocol, self.registry, self.params = protocol, registry, params
        self.groups = groups
        self.counts = np.zeros(registry.n, dtype=np.int64)
        self.blocks = np.zeros((4, registry.n), dtype=np.int64) if protocol == "v1" else None
        self.subsets = stage_subsets(registry, params, load_retinotopy()) if protocol == "v1" else {}
        self.fano = FanoAccumulator(registry.n, params)
        self.central_windows: deque[int] = deque()
        self.rolling = 0
        self.max_rolling = 0.0
        self.first_central = self.last_central = 0
        self.chunks_per_s = round(1000 / params.get("engine.chunk_ms"))
        self.settled_central_hz = 0.0

    def settle(self, engine: Any, mod: Any, stimulus: Any, recorded: list) -> SettleRecord:
        """SPEC-P2 3.4 fixed 2 s, with normal A/C pool updates (not a test seam)."""
        chunk_ms = self.params.get("engine.chunk_ms")
        counts = np.zeros(engine.n, dtype=np.int64)
        final_second = np.zeros(engine.n, dtype=np.int64)
        for pos in range(2 * self.chunks_per_s):
            mod.check_cancel()
            stimulus()
            result = engine.run_chunk(chunk_ms)
            mod.on_chunk(result.counts, chunk_ms / 1000)
            composed = mod.compose()
            engine.set_threshold(composed.v_th)
            engine.set_gain(composed.gain)
            counts += result.counts
            if pos >= self.chunks_per_s:
                final_second += result.counts
        self.settled_central_hz = _rate(final_second, self.groups["central"], 1.0)
        return SettleRecord(
            True, SETTLE_S, mod.fixed_point(), mod.da_c.copy(),
            np.array([_rate(counts, p.idx, SETTLE_S) for p in recorded]), engine.tick(),
            upstream_extended_overlap_idx=mod.overlap.copy(), unresolved=[], da_gap_um=[],
        )

    def chunk(self, result: Any, recording_time: float) -> None:
        """Observe the same chunks sent to ProbeRecorder; seconds, counts."""
        self.counts += result.counts
        if self.protocol == "v1":
            # Integer chunk index avoids floating boundary drift at 1/4/5/... s.
            step = round(recording_time * self.chunks_per_s)
            block, offset = divmod(step, 4 * self.chunks_per_s)
            if offset >= self.chunks_per_s:
                self.blocks[block] += result.counts
            return
        self.fano.add(result.hist_1ms)
        central = int(result.counts[self.groups["central"]].sum())
        self.central_windows.append(central)
        self.rolling += central
        if len(self.central_windows) > self.chunks_per_s:
            self.rolling -= self.central_windows.popleft()
        if len(self.central_windows) == self.chunks_per_s:
            self.max_rolling = max(self.max_rolling, self.rolling / len(self.groups["central"]))
        if recording_time < 1.0:
            self.first_central += central
        if recording_time >= 9.0:
            self.last_central += central

    def result(self, seed: int) -> dict:
        """Small per-seed measurements plus exact column membership (engine indices)."""
        if self.protocol == "v3":
            sync = self.fano.report()
            ignition = ignition_detector(np.array([self.max_rolling]), self.settled_central_hz, self.params)
            return {
                "seed": seed, "F": sync["F"], "b": sync["max_bin_fraction"],
                "stability_ratio": self.first_central / self.last_central if self.last_central else None,
                "central_hz": _rate(self.counts, self.groups["central"], 10),
                "DAN_hz": _rate(self.counts, self.groups["DAN"], 10),
                "KC_hz": _rate(self.counts, self.groups["KC"], 10),
                "settled_central_hz": self.settled_central_hz,
                "max_rolling_central_hz": self.max_rolling, "ignited": bool(ignition["tripped"]),
                "steering_diff_hz": self.steer(self.counts, 10),
            }
        deltas, blocks, memberships = {}, {}, {}
        for name, subset in self.subsets.items():
            blocks[name], memberships[name] = {}, {"mode": subset["mode"]}
            for pos, bar in enumerate((45.0, -45.0)):
                key = str(bar)
                blocks[name][key] = {}
                memberships[name][key] = {}
                for side, idx in subset[key].items():
                    delta = _rate(self.blocks[2 * pos + 1] - self.blocks[2 * pos], idx, 3)
                    blocks[name][key][side] = delta
                    memberships[name][key][side] = idx.tolist()
            deltas[name] = {
                side: float(np.mean([blocks[name][str(bar)][side] for bar in (45.0, -45.0)]))
                for side in ("ipsilateral", "contralateral")
            }
        steering = [self.steer(self.blocks[pos], 3) for pos in (1, 3)]
        return {"seed": seed, "stage_delta_hz": deltas, "block_stage_delta_hz": blocks,
                "subsets": memberships, "delta_steer_hz": steering[0] - steering[1],
                "block_steering_diff_hz": steering}

    def steer(self, counts: np.ndarray, seconds: float) -> float:
        return (_rate(counts, self.registry.population("steering_R").idx, seconds)
                - _rate(counts, self.registry.population("steering_L").idx, seconds))


def v3_passed(rows: list[dict]) -> dict:
    """SPEC-P2 R-screen without gradedness; report all measured Hz alongside it."""
    if not rows:
        return {"passed": False, "reason": "no V3 rows"}
    per_seed = all(r["F"] is not None and r["F"] < 3 and r["b"] < .05
                   and r["stability_ratio"] is not None and .5 <= r["stability_ratio"] <= 2
                   and not r["ignited"] for r in rows)
    central, dan, kc = (float(np.mean([r[k] for r in rows])) for k in ("central_hz", "DAN_hz", "KC_hz"))
    means = .5 <= central <= 8 and .5 <= dan <= 10 and kc <= 2
    return {"passed": bool(per_seed and means), "checks": {
        "per_seed": per_seed, "central": central, "DAN": dan, "KC": kc, "means": means,
        "ignition": [r["ignited"] for r in rows], "steering_diff_hz": [r["steering_diff_hz"] for r in rows],
    }}


def v1_passed(rows: list[dict], *, min_delta_hz: float | None = None) -> dict:
    """Bootstrap over seeds; keep ipsilateral and contralateral measurements separate."""
    from flyonenomics.orchestrator.seeds import ANALYSIS, stream

    if not rows:
        return {"passed": False, "reason": "no V1 rows"}
    rows = sorted(rows, key=lambda r: r["seed"])
    threshold = float(load_params(PARAMS_PATH).get("vpath.min_delta_hz")) if min_delta_hz is None else min_delta_hz
    rng = stream(MASTER_SEED, 0, 0, ANALYSIS)
    result = evaluate_v1(
        {n: np.array([r["stage_delta_hz"][n]["ipsilateral"] for r in rows]) for n in V1_POPULATIONS},
        np.array([r["delta_steer_hz"] for r in rows]), rng, min_delta_hz=threshold, bootstrap_n=10_000,
    )
    result["contralateral"] = {
        n: bootstrap_mean_interval(np.array([r["stage_delta_hz"][n]["contralateral"] for r in rows]), rng)
        for n in V1_POPULATIONS
    }
    return result


def record_v3(rows: list[dict], *, r_light: float, identity: dict | None = None) -> dict:
    result = v3_passed(rows)
    return {"status": "passed" if result["passed"] else "failed", "test_id": "V3",
            "r_light_hz": r_light, **result, "rows": rows, **({"identity": identity} if identity else {})}


def record_v1(rows: list[dict], *, r_light: float, screen: str, identity: dict | None = None) -> dict:
    result = v1_passed(rows)
    return {"status": "passed" if result["passed"] else "failed", "test_id": "V1",
            "screen": screen, "seed_count": len(rows), "r_light_hz": r_light,
            "passed": result["passed"], "evaluation": result, "rows": rows,
            **({"identity": identity} if identity else {})}


def record_vcal(summary: dict, *, identity: dict | None = None) -> dict:
    return {**{k: v for k, v in summary.items() if k != "rows"},
            "status": "passed" if summary.get("selected_r_light_hz") is not None else "failed",
            "visual_commit": "data/visual-v0.2.yaml" if summary.get("selected_r_light_hz") is not None else None,
            **({"identity": identity} if identity else {})}


def visual_document(r_light: float, params: Any, vcal_sha256: str) -> dict:
    return {"version": "v0.2", "inject_at": "photoreceptors", "r_light": r_light,
            "r_dark": float(params.get("vis.pr_rate_dark_hz")),
            "pr_acceptance_deg": float(params.get("vis.pr_acceptance_deg")),
            "provenance": {"item": 122, "vcal_record": VCAL_RECORD.relative_to(REPO).as_posix(),
                           "vcal_sha256": vcal_sha256}}


def write_record(path: Path, payload: dict) -> str:
    from flyonenomics.store.results import atomic_json
    from flyonenomics.validation.binding import sha256_file

    atomic_json(path, payload)
    return sha256_file(path)


def vcal_stage2_needed(stage1_pass: dict, rates: tuple) -> bool:
    return not any(stage1_pass.get(float(rate), False) for rate in rates)


def vcal_candidate(all_rates: list, v3_pass: dict, v1_screen: dict) -> float | None:
    return next((float(r) for r in sorted(all_rates)
                 if v3_pass.get(r, {}).get("passed") and v1_screen.get(r, {}).get("passed")), None)


def vcal_v1_failed_rate(outcomes: list[dict]) -> float | None:
    passing = [o for o in outcomes if o["v3"].get("passed")]
    if not passing:
        return None
    # Stable tie: the lower light rate, not process completion order.
    return float(max(sorted(passing, key=lambda o: o["rate_hz"]),
                     key=lambda o: abs(o.get("v1", {}).get("delta_steer", {}).get("mean", 0)))["rate_hz"])
