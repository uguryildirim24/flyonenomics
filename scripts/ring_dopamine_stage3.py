"""Stage 3 of the ring-neuron dopamine experiment: transporter-inhibition sensitivity.

Item 142 fixes the contract.  Stage 2c showed that the two implemented
``ER``-local dopamine application sites, the spike-threshold term ``d_v`` and
the postsynaptic input gain, together eliminate about 95 percent of the ring
excess that ``CX_DAN`` activation produces against its unstimulated reference.
That number belongs to the dark-to-driven contrast and does not transfer to
transporter inhibition against driven vehicle, so stage 3 asks a different
question at a different operating point.

PART A is a cheap closed-form calculation with no engine run.  It names the
altered uptake parameter (the Michaelis-Menten transporter maximum rate
``da.Vmax``, scaled by ``ScaleDat factor = 1 - inhibition``), computes the
EB dopamine trajectory and the applied ``ER`` threshold and gain for a spread
of fractional transporter inhibitions, chooses two separated levels from the
applied-``ER`` separation and checks for saturation.

PART B is the paired neural probe, run only if part A leaves a usable
separation.  Wild type, ten seeds, 20 s, 228 traced ``ER``, the TuBu stripe on
throughout and ``CX_DAN`` driven at 50 Hz in every arm.  The comparator is
driven vehicle.  The runner reuses ``scripts/ring_dopamine_stage2c.py``
wholesale, including its ``InstrumentedNeuromod`` and both its audits.

Every value is a model measurement, never a pass line.  A null is the result,
and so is saturation found in part A.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
import json
import multiprocessing
import os
from pathlib import Path
import platform
import time
from types import SimpleNamespace
from typing import Any

import numpy as np

import ring_dopamine_stage1 as s1
import ring_dopamine_stage2 as s2
import ring_dopamine_stage2b as s2b
import ring_dopamine_stage2c as s2c
from flyonenomics.neuromod.state import Neuromod

ROOT = Path(__file__).resolve().parents[1]
MASTER = s1.MASTER
SEEDS = s1.SEEDS
SETTLE_S = s1.SETTLE_S
PROBE_S = s1.PROBE_S
TUBU_MAX_HZ = s1.TUBU_MAX_HZ
SIGMA_DEG = s1.SIGMA_DEG
STRIPE_AZ_DEG = s1.STRIPE_AZ_DEG
SOURCE_POPULATION = s1.SOURCE_POPULATION
DOPAMINE_POPULATION = s1.DOPAMINE_POPULATION
DA_DRIVE_HZ = s1.DA_DRIVE_HZ
DEFAULT_FIXTURE = Path("data/experiments/p2/ring-dopamine-stage3.json")
DEFAULT_PLAN = Path("camber-runs/ring-dopamine-stage3/plan.json")
DEFAULT_RAW = Path("camber-runs/ring-dopamine-stage3/raw")
DEFAULT_AUDIT = Path("camber-runs/ring-dopamine-stage3/audit.json")
DEFAULT_DISCONNECT_AUDIT = Path("camber-runs/ring-dopamine-stage3/disconnect-audit.json")
DEFAULT_RECORD = Path("validation/records/p2/ring-dopamine-stage3.json")
STAGE2C_RECORD = Path("validation/records/p2/ring-dopamine-stage2c.json")
SOURCE_COMMIT_ENV = s1.SOURCE_COMMIT_ENV
DECLARED_SUBSTRATE_ID = s1.DECLARED_SUBSTRATE_ID
REACHED_RECORD = s1.REACHED_RECORD

# Fractional transporter inhibition levels.  The two separated levels are
# chosen in ``part_a`` from the applied-ER separation alone; they are fixed
# here as the scale_dat factors (1 - inhibition) the arms apply.  ``None``
# means the wild-type genotype with no transporter manipulation.
INHIBIT_LOW = 0.20      # ScaleDat factor 0.80
INHIBIT_HIGH = 0.80     # ScaleDat factor 0.20
SCALE_LOW = 0.80
SCALE_HIGH = 0.20

# Seven paired arms.  ``vehicle`` is the comparator; ``inhibit-low`` and
# ``inhibit-high`` are part A's levels; ``vehicle-clamped`` replays the paired
# driven-vehicle ER trajectories onto themselves (the replay check);
# ``inhibit-high-clamped`` replays the same paired driven-vehicle ER
# trajectories while chemistry, occupancies and non-ER modulation stay live;
# the two ``dat-disabled`` arms set the target absent.  ``vehicle-clamped`` is
# the extra arm the brief's vehicle-against-vehicle verification needs; the
# seven arms are 7 * 10 * 20 s = 1,400 brain-seconds, the budget ceiling.
ARMS: tuple[dict[str, Any], ...] = (
    {"label": "vehicle", "scale_dat_factors": (), "drive_hz": DA_DRIVE_HZ,
     "dan_fast_synapses": "retain", "replay": None},
    {"label": "inhibit-low", "scale_dat_factors": (SCALE_LOW,), "drive_hz": DA_DRIVE_HZ,
     "dan_fast_synapses": "retain", "replay": None},
    {"label": "inhibit-high", "scale_dat_factors": (SCALE_HIGH,), "drive_hz": DA_DRIVE_HZ,
     "dan_fast_synapses": "retain", "replay": None},
    {"label": "vehicle-clamped", "scale_dat_factors": (), "drive_hz": DA_DRIVE_HZ,
     "dan_fast_synapses": "retain", "replay": "vehicle"},
    {"label": "inhibit-high-clamped", "scale_dat_factors": (SCALE_HIGH,), "drive_hz": DA_DRIVE_HZ,
     "dan_fast_synapses": "retain", "replay": "vehicle"},
    {"label": "vehicle-dat-disabled", "scale_dat_factors": (0.0,), "drive_hz": DA_DRIVE_HZ,
     "dan_fast_synapses": "retain", "replay": None},
    {"label": "inhibit-high-dat-disabled", "scale_dat_factors": (SCALE_HIGH, 0.0),
     "drive_hz": DA_DRIVE_HZ, "dan_fast_synapses": "retain", "replay": None},
)
ARM_LABELS = tuple(arm["label"] for arm in ARMS)

# Primary endpoint contrasts against driven vehicle, in the order the brief
# reports them.  ``signed`` says whether the contrast is a drug contrast.
PRIMARY_CONTRASTS = (
    ("inhibit_low_minus_vehicle", "inhibit-low", "vehicle"),
    ("inhibit_high_minus_vehicle", "inhibit-high", "vehicle"),
    ("inhibit_high_minus_inhibit_low", "inhibit-high", "inhibit-low"),
    ("inhibit_high_clamped_minus_vehicle", "inhibit-high-clamped", "vehicle"),
    ("inhibit_high_minus_inhibit_high_clamped", "inhibit-high", "inhibit-high-clamped"),
    ("vehicle_clamped_minus_vehicle", "vehicle-clamped", "vehicle"),
    ("vehicle_dat_disabled_minus_vehicle", "vehicle-dat-disabled", "vehicle"),
    ("inhibit_high_dat_disabled_minus_vehicle_dat_disabled",
     "inhibit-high-dat-disabled", "vehicle-dat-disabled"),
    ("inhibit_high_minus_vehicle_dat_disabled", "inhibit-high", "vehicle-dat-disabled"),
)

# The operating point stage 2 measured, used for the part A cross-check.
STAGE2_DRIVEN_EB_RANGE_UM = (3.4, 4.0)

# The runner file at the commit the probe executed (source_commit 8b73fbe).
# Recorded so the provenance correction can name the actually executed runner
# even though the raw files' shared identity function hashed stage 2c instead.
EXECUTED_RUNNER_SHA256 = "c2bb16eb6cdca4ed2cc2c8e878e7fc84e0d434c1e8d05d5309a9c2b595a9ef48"


class Stage3Neuromod(s2c.InstrumentedNeuromod):
    """Stage 2c's instrumented neuromod plus a paired ER-term replay.

    The replay replaces ``d_v`` and the input gain on the 228 traced ``ER``
    cells with a recorded per-chunk trajectory (the paired driven-vehicle
    trajectory) while the pool, source term, innervation, occupancies, every
    other cell's terms and the chemistry stay live.  With ``replay is None``
    the returned vectors are the natural ones, so the unclamped arms take the
    base path.
    """

    def __init__(self, *args: Any, replay: dict[str, np.ndarray] | None = None, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.replay = replay
        self.replay_step = 0

    def receptor_terms(self) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        d_v, gain, occ1, occ2 = super().receptor_terms()
        if self.replay is not None:
            d_v = np.array(d_v, dtype=np.float64, copy=True)
            gain = np.array(gain, dtype=np.float64, copy=True)
            d_v[self.er_idx] = self.replay["dv"][self.replay_step]
            gain[self.er_idx] = self.replay["gain"][self.replay_step]
            self.last_applied_dv = d_v
            self.last_applied_gain = gain
        return d_v, gain, occ1, occ2


def dump(path: Path, value: Any) -> None:
    s1.dump(path, value)


def read(path: Path) -> dict[str, Any]:
    return s1.read(path)


def digest(array: np.ndarray, dtype: Any | None = None) -> str:
    return s1.digest(array, dtype)


def _paired_interval(values: list[float]) -> dict[str, Any]:
    return s1._paired_interval(values)


def _distribution(values: list[float]) -> dict[str, Any]:
    return s1._distribution(values)


def probe(label: str) -> Any:
    return s1.probe(label)


def _er_targets() -> np.ndarray:
    return s2._er_targets()


def identity(platform_name: str) -> dict[str, Any]:
    """Stage 3 execution identity: correct the runner hash to this file.

    ``s2c.identity`` records ``Path(__file__)`` as the *stage 2c* runner because
    that is its own file, so its ``runner_sha256`` must be replaced with this
    runner's own hash and the reused stage 2c hash recorded separately.
    """
    from flyonenomics.io import hash_file

    result = s2c.identity(platform_name)
    result["runner_sha256"] = hash_file(Path(__file__))
    result["reused_stage2c_runner_sha256"] = hash_file(Path(s2c.__file__))
    return result


def _prepare_declared(trace_indices: np.ndarray, *, with_traces: bool) -> dict[str, Any]:
    return s2._prepare_declared(trace_indices, with_traces=with_traces)


# ---------------------------------------------------------------------------
# Part A: the cheap calculation, no engine run.
# ---------------------------------------------------------------------------


def _er_receptor_arrays() -> tuple[Any, Any, Any, Any, Any, Any]:
    """Return the registry exposure/receptor arrays and params for the traced ER cells."""
    from flyonenomics.registry import build_registry
    from flyonenomics.types import load_params

    registry = build_registry("783", populations_path=ROOT / "data/populations-v0.2.yaml")
    params = load_params(ROOT / "data/params-v0.2.yaml")
    return registry, registry.exposure().tocsr(), registry.exposed_mask(), \
        np.asarray(registry.receptors().r1, dtype=np.float64), \
        np.asarray(registry.receptors().r2, dtype=np.float64), params


def _eb_dopamine_trajectory(q_um_s: float, vmax_scale: float, *, seconds: float = PROBE_S,
                            dt_s: float = 0.001, start_um: float = 0.02) -> np.ndarray:
    """Closed-form EB pool trajectory: explicit Euler of the on_chunk balance, no engine.

    ``q_um_s`` is the release source into EB (alpha times weighted rate plus
    the tonic standing release), ``vmax_scale`` multiplies ``da.Vmax`` so that
    ``vmax_scale = 1 - inhibition``.  This is the same balance
    ``Neuromod.on_chunk`` integrates, at a finer step.
    """
    from flyonenomics.types import load_params

    params = load_params(ROOT / "data/params-v0.2.yaml")
    vmax = float(params.get("da.Vmax")) * float(vmax_scale)
    km = float(params.get("da.Km"))
    k_ns = float(params.get("da.k_ns"))
    n = int(round(seconds / dt_s))
    out = np.empty(n, dtype=np.float64)
    da = float(start_um)
    for k in range(n):
        da = max(0.0, da + dt_s * (q_um_s - (vmax * da / (km + da) + k_ns * da)))
        out[k] = da
    return out


def _er_terms_for_concentration(da_eb_um: float, registry: Any, exposure: Any, exposed: Any,
                                r1: Any, r2: Any, params: Any, eb_index: int,
                                targets: np.ndarray) -> tuple[float, float]:
    """Applied ER d_v and gain from ``receptor_effect`` at one EB concentration."""
    from flyonenomics.neuromod.receptors import receptor_effect

    da_c = np.full(len(registry.compartments()), float(params.get("da.DA_ref")))
    da_c[eb_index] = float(da_eb_um)
    d_v, gain, occ1, occ2 = receptor_effect(da_c, exposure, exposed, r1, r2, params)
    return float(np.unique(np.asarray(d_v[targets], dtype=np.float64))[0]), \
        float(np.unique(np.asarray(gain[targets], dtype=np.float64))[0])


def part_a() -> dict[str, Any]:
    """The item-142 part A calculation: parameter, mapping, spread, levels, saturation.

    No engine run.  The trajectory uses only the closed-form pool balance and
    ``receptor_effect``.  The two separated levels are chosen from the
    applied-ER separation, never from any ring outcome; the rule is stated
    before any neural result exists.
    """
    from flyonenomics.registry.compartments import compartment_index
    from flyonenomics.types import load_params

    params = load_params(ROOT / "data/params-v0.2.yaml")
    registry, exposure, exposed, r1, r2, _ = _er_receptor_arrays()
    targets = _er_targets()
    eb_index = compartment_index()["EB"]
    da_ref = float(params.get("da.DA_ref"))
    vmax0 = float(params.get("da.Vmax"))
    km = float(params.get("da.Km"))
    k_ns = float(params.get("da.k_ns"))
    alpha = 0.005333333333333333
    s_c = 0.0026666666666666666
    census = s1.eb_innervation()
    eb_weight_sum = float(census["cx_dan"]["eb_weight_sum"])
    weighted_rate = DA_DRIVE_HZ * eb_weight_sum
    q_nominal = alpha * weighted_rate + s_c

    # The parameter and the mapping, stated explicitly.
    parameter = {
        "name": "da.Vmax",
        "meaning": "Michaelis-Menten maximum transporter rate, uM/s, per compartment",
        "implemented_by": (
            "ScaleDat multiplies Neuromod.dat_geno; Neuromod._kinetics computes "
            "vmax = da.Vmax * dat_geno, so the effective transporter rate is "
            "Vmax_eff = da.Vmax * factor"
        ),
        "fumin": "named genotype fumin is ScaleDat factor 0, the encoded absence of the target",
        "mapping": (
            "fractional transporter inhibition i is implemented as ScaleDat factor = 1 - i, "
            "so Vmax_eff = da.Vmax * (1 - i).  No concentration-to-inhibition mapping is used "
            "or assumed, so the primary axis is fractional transporter inhibition, not a "
            "methylphenidate dose."
        ),
        "da_ref_um": da_ref, "vmax0_um_s": vmax0, "km_um": km, "k_ns_s": k_ns,
        "alpha_c_um_per_weighted_spike": alpha, "s_c_um_s": s_c,
        "source_mode": "source",
        "eb_weight_sum": eb_weight_sum,
        "weighted_rate_hz_at_50hz": weighted_rate,
    }
    drive = {
        "nominal": {
            "label": "CX_DAN nominal 50 Hz",
            "weighted_rate_hz": weighted_rate,
            "q_um_s": q_nominal,
            "note": "the brief's declared closed-form drive, all nine EB-innervating CX_DAN at 50 Hz",
        },
        "measured_operating_point": {
            "eb_da_um_range": list(STAGE2_DRIVEN_EB_RANGE_UM),
            "source": "item 137 (i): stage 2's driven field sits near 3.4 to 4.0 uM",
            "note": (
                "the closed-form trajectory at the item 137 operating point is a cross-check; "
                "the nominal 50 Hz closed form over-predicts the realized EB concentration "
                "because the realized CX_DAN rate is below 50 Hz (stage 2 measured 36.6 Hz) "
                "and only nine of the 30 CX_DAN cells carry a nonzero EB column"
            ),
        },
    }

    # The spread of inhibition fractions: trajectory at the nominal 50 Hz drive.
    grid = [round(0.05 * k, 2) for k in range(0, 21)]
    rows = []
    for inhibition in grid:
        trajectory = _eb_dopamine_trajectory(q_nominal, 1.0 - inhibition)
        window = trajectory[int(round(SETTLE_S / 0.001)):]
        dv_win, gain_win = _er_terms_for_concentration(float(window.mean()), registry, exposure,
                                                       exposed, r1, r2, params, eb_index, targets)
        dv20, gain20 = _er_terms_for_concentration(float(trajectory[-1]), registry, exposure,
                                                   exposed, r1, r2, params, eb_index, targets)
        rows.append({
            "inhibition": inhibition, "scale_dat_factor": round(1.0 - inhibition, 2),
            "vmax_eff_um_s": vmax0 * (1.0 - inhibition),
            "eb_da_window_mean_um": float(window.mean()),
            "eb_da_20s_um": float(trajectory[-1]),
            "applied_dv_window_mean_mv": dv_win,
            "applied_gain_window_mean": gain_win,
            "applied_dv_20s_mv": dv20,
            "applied_gain_20s": gain20,
        })

    # Direct operating-point cross-check at the item-137 driven range.
    op_point = []
    for da_eb in STAGE2_DRIVEN_EB_RANGE_UM:
        dv, gain = _er_terms_for_concentration(da_eb, registry, exposure, exposed, r1, r2,
                                               params, eb_index, targets)
        op_point.append({"eb_da_um": da_eb, "applied_dv_mv": dv, "applied_gain": gain})

    # Choose two separated levels from the applied-ER separation alone.  The
    # mapping is monotonic, so the applied-ER separation grows with the
    # inhibition difference.  Rule: over a grid of genuine partial
    # inhibitions (ScaleDat factor in [0.2, 0.8], so neither arm collapses to
    # vehicle or to the target-absent arm), pick the pair with the largest
    # combined applied-d_v and applied-gain window-mean separation.
    candidates = [row for row in rows if 0.2 - 1e-9 <= row["scale_dat_factor"] <= 0.8 + 1e-9]
    best = None
    for a in candidates:
        for b in candidates:
            if b["inhibition"] - a["inhibition"] < 0.4:
                continue
            dv_sep = abs(b["applied_dv_window_mean_mv"] - a["applied_dv_window_mean_mv"])
            gain_sep = abs(b["applied_gain_window_mean"] - a["applied_gain_window_mean"])
            score = dv_sep + gain_sep
            if best is None or score > best["score"]:
                best = {"low": a, "high": b, "dv_sep": dv_sep, "gain_sep": gain_sep, "score": score}
    dv_low = best["low"]["inhibition"]
    dv_high = best["high"]["inhibition"]

    full = rows[0]
    full_inhibit = rows[-1]
    separation = {
        "chosen_low_inhibition": dv_low,
        "chosen_high_inhibition": dv_high,
        "chosen_low_scale_dat_factor": round(1.0 - dv_low, 2),
        "chosen_high_scale_dat_factor": round(1.0 - dv_high, 2),
        "chosen_dv_window_mean_separation_mv": best["dv_sep"],
        "chosen_gain_window_mean_separation": best["gain_sep"],
        "full_range_dv_window_mean_span_mv": abs(full["applied_dv_window_mean_mv"]
                                                 - full_inhibit["applied_dv_window_mean_mv"]),
        "full_range_gain_window_mean_span": abs(full["applied_gain_window_mean"]
                                                - full_inhibit["applied_gain_window_mean"]),
        "full_range_dv_20s_span_mv": abs(full["applied_dv_20s_mv"] - full_inhibit["applied_dv_20s_mv"]),
        "full_range_gain_20s_span": abs(full["applied_gain_20s"] - full_inhibit["applied_gain_20s"]),
        "operating_point_dv_span_mv": abs(op_point[-1]["applied_dv_mv"] - op_point[0]["applied_dv_mv"]),
        "operating_point_gain_span": abs(op_point[-1]["applied_gain"] - op_point[0]["applied_gain"]),
        "rule": (
            "candidate grid of genuine partial inhibitions with ScaleDat factor in [0.2, 0.8]; "
            "choose the pair at least 0.4 apart in inhibition fraction with the largest combined "
            "window-mean applied d_v and applied gain separation; separation in the applied ER "
            "terms is the thing that matters, not separation in the inhibition fraction"
        ),
    }

    # The uptake flux, reported separately from the applied ER terms.  Fractional
    # parameter inhibition is not the same as a fractional reduction in realised
    # uptake flux: at a common dopamine concentration the flux scales with
    # Vmax_eff, but along the trajectory dopamine rises and partly compensates,
    # so the realised flux is not reduced by the inhibition fraction.  Unchanged
    # realised flux is not a failed inhibition.
    def flux(vmax_eff: float, da_um: float) -> float:
        return float(vmax_eff * da_um / (km + da_um))

    scale_low = 1.0 - dv_low
    scale_high = 1.0 - dv_high
    common = []
    for da_um in (0.16219, 1.849999, 3.4, 4.0):
        common.append({
            "da_um": da_um,
            "uptake_flux_vehicle_um_s": flux(vmax0, da_um),
            "uptake_flux_inhibit_low_um_s": flux(vmax0 * scale_low, da_um),
            "uptake_flux_inhibit_high_um_s": flux(vmax0 * scale_high, da_um),
            "uptake_flux_full_inhibition_um_s": flux(0.0, da_um),
        })
    realised = [
        {
            "inhibition": row["inhibition"],
            "vmax_eff_um_s": row["vmax_eff_um_s"],
            "eb_da_window_mean_um": row["eb_da_window_mean_um"],
            "realised_flux_window_mean_um_s": flux(row["vmax_eff_um_s"], row["eb_da_window_mean_um"]),
        }
        for row in rows
        if row["inhibition"] in (0.0, 0.2, 0.4, 0.6, 0.8, 1.0)
    ]
    uptake_flux = {
        "function": "J(da) = Vmax_eff * da / (Km + da), with Km unchanged by the manipulation",
        "common_concentration_check": common,
        "realised_flux": realised,
        "note": (
            "fractional parameter inhibition reduces the transport capacity at a common dopamine "
            "concentration proportionally to Vmax_eff = da.Vmax * (1 - i); the realised flux along "
            "the trajectory is not reduced by the same fraction because dopamine rises and "
            "partly compensates.  Unchanged realised flux is not a failed inhibition."
        ),
    }

    # The saturation check: how far does the whole candidate range move the
    # applied ER terms?  Report the number beside the stage 2c clamp range, the
    # modulation the model already resolves, and the model's own measured
    # d_v-to-spike and gain-to-spike scales.  No project number is used as a
    # pass line (item 121); the decision is documented, not thresholded.
    stage2c = read(ROOT / STAGE2C_RECORD)["probe"] if (ROOT / STAGE2C_RECORD).is_file() else None
    clamp_reference = None
    implied_scale = None
    if stage2c is not None:
        dv_clamp = float(stage2c["threshold_clamp"]["applied_dv_mV"]["mean"])
        gain_clamp = float(stage2c["gain_additional"]["applied_gain"]["mean"])
        dv_spikes = float(stage2c["threshold_clamp"]["er_spikes"]["mean"])
        gain_spikes = float(stage2c["gain_additional"]["er_spikes"]["mean"])
        clamp_reference = {
            "threshold_clamp_applied_dv_mv": dv_clamp,
            "gain_clamp_applied_gain": gain_clamp,
            "threshold_clamp_spikes": dv_spikes,
            "gain_clamp_spikes": gain_spikes,
            "note": "stage 2c's ER-local clamps, the modulation range this model already resolves",
        }
        # A linear scale across conditions, for orientation only; interaction
        # means a mechanistic share cannot be assigned and this is not a
        # prediction or a pass line.
        dv_scale = abs(dv_spikes / dv_clamp) if dv_clamp else 0.0
        gain_scale = abs(gain_spikes / gain_clamp) if gain_clamp else 0.0
        full_dv = separation["full_range_dv_window_mean_span_mv"]
        full_gain = separation["full_range_gain_window_mean_span"]
        implied_scale = {
            "spikes_per_mv_dv": dv_scale,
            "spikes_per_unit_gain": gain_scale,
            "full_range_implied_spikes": dv_scale * full_dv + gain_scale * full_gain,
            "note": (
                "linear orientation scale extrapolated from stage 2c's clamps; interaction and "
                "the different operating point mean it is not a prediction and not a pass line"
            ),
        }
    full_dv_span = separation["full_range_dv_window_mean_span_mv"]
    full_gain_span = separation["full_range_gain_window_mean_span"]
    compressed = None
    if clamp_reference is not None:
        compressed = bool(
            full_dv_span < 0.25 * abs(clamp_reference["threshold_clamp_applied_dv_mv"])
            and full_gain_span < 0.25 * abs(clamp_reference["gain_clamp_applied_gain"])
        )
    saturation = {
        "compressed_relative_to_stage2c_clamp": compressed,
        "reading": (
            "the full candidate inhibition range is compressed relative to the stage 2c clamp "
            "range, so the applied ER terms are near-saturated; the reading is a comparison of "
            "scales, not a pass line (item 121)"
        ),
        "clamp_reference": clamp_reference,
        "implied_spike_scale": implied_scale,
        "indirect_effect_reason": (
            "EB receptor saturation does not exclude an indirect effect.  The transporter "
            "manipulation acts outside EB too, and other dopamine-modulated cells can change the "
            "input reaching ER while ER's own terms barely move; stage 2c left a 5.4 percent "
            "residual under the joint ER clamp.  A small ER-local term change is therefore not "
            "the whole possible route, which is why part B is informative even at a compressed "
            "ER-local separation."
        ),
        "decision": (
            "part B is run: the applied ER terms are near-saturated but not identical, and the "
            "model's own measured d_v-to-spike and gain-to-spike scales put the full-range "
            "implied change at the order of the design's resolution, so whether the compressed "
            "change propagates is the empirical question part B answers.  The implied scale is "
            "not a prediction the neural result is scored against (item 121).  If part B returns "
            "no detected difference, the attenuation is reported where identifiable and "
            "otherwise left unresolved, not forced into one of item 142's three cases: precision "
            "and cancellation across cells or time can prevent a unique diagnosis."
        ),
        "history": (
            "the level-choice rule and the shorter computational saturation decision are in "
            "the executed runner at 8b73fbe.  The expanded write-up wording 'near-saturated but "
            "not virtually identical' first appears in the result commit 254a38d; coordinator "
            "chronology places its drafting after launch and before summarize.  It uses part-A "
            "quantities only, but is not claimed to have been written before launch."
        ),
    }
    return {
        "parameter_and_mapping": parameter,
        "drive": drive,
        "trajectory_grid": rows,
        "operating_point": op_point,
        "separation": separation,
        "saturation": saturation,
        "uptake_flux": uptake_flux,
        "method": (
            "closed-form explicit Euler of the Neuromod.on_chunk pool balance (1 ms step, 20 s "
            "from the 0.02 uM baseline) plus flyonenomics.neuromod.receptors.receptor_effect for "
            "the applied ER terms.  No engine run."
        ),
    }


def build_census(destination: Path) -> None:
    """Write the part A analysis into the record; the probe key stays null."""
    started = time.monotonic()
    census = {
        "eb_innervation": s1.eb_innervation(),
        "ring_receptors": s1.ring_receptors(ROOT / REACHED_RECORD),
        "dan_synapse_census": s2.dan_synapse_census(),
        "er_local_dopamine_sites": s2c.local_dopamine_sites(),
        "part_a": part_a(),
    }
    record = {
        "class": "development",
        "purpose": (
            "ring-neuron dopamine stage 3: a model-internal transporter-inhibition sensitivity "
            "study at the driven operating point"
        ),
        "declared_substrate_id": DECLARED_SUBSTRATE_ID,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "census": census,
        "probe": None,
        "wall_seconds": time.monotonic() - started,
    }
    dump(destination, record)
    pa = census["part_a"]
    print(json.dumps({
        "part_a_parameter": pa["parameter_and_mapping"]["name"],
        "part_a_mapping": pa["parameter_and_mapping"]["mapping"],
        "part_a_grid_rows": len(pa["trajectory_grid"]),
        "part_a_separation": pa["separation"],
        "part_a_saturation": pa["saturation"],
    }, indent=2), flush=True)
    print(f"wrote {destination}", flush=True)


def build_plan(destination: Path) -> None:
    """Fix the trace set (228 ER) and the seven paired arms."""
    from flyonenomics.registry import build_registry
    from flyonenomics.registry.compartments import compartment_index

    reached = read(ROOT / REACHED_RECORD)
    er_cells = [cell for cell in reached["cells"] if "ring_ER" in cell["classes"]]
    trace_indices = sorted(int(cell["engine_index"]) for cell in er_cells)
    registry = build_registry("783", populations_path=ROOT / "data/populations-v0.2.yaml")
    compartment = compartment_index()
    fixture = read(ROOT / DEFAULT_FIXTURE)
    if [arm["label"] for arm in fixture["arms"]] != list(ARM_LABELS):
        raise ValueError("fixture arm labels do not match the runner's arms")
    fixture_factors = [
        tuple(float(hook["factor"]) for hook in arm["genotype"].get("manipulations", [])
              if hook["type"] == "scale_dat")
        for arm in fixture["arms"]
    ]
    runner_factors = [tuple(float(factor) for factor in arm["scale_dat_factors"]) for arm in ARMS]
    if fixture_factors != runner_factors:
        raise ValueError("fixture scale_dat factors do not match the runner's arms")
    output = {
        "class": "development",
        "purpose": "ring-neuron dopamine stage 3 seven-arm paired transporter-inhibition probe plan",
        "declared_substrate_id": DECLARED_SUBSTRATE_ID,
        "protocol": {
            "master_seed": MASTER,
            "seeds": list(SEEDS),
            "arms": list(ARMS),
            "settle_s": SETTLE_S,
            "probe_s": PROBE_S,
            "brain_seconds": PROBE_S * len(ARMS) * len(SEEDS),
            "inject_at": SOURCE_POPULATION,
            "dopamine_population": DOPAMINE_POPULATION,
            "dopamine_drive_hz": float(DA_DRIVE_HZ),
            "stripe_azimuth_deg": STRIPE_AZ_DEG,
            "stripe_width_deg": 5.0,
            "TuBu_max_hz": TUBU_MAX_HZ,
            "TuBu_sigma_deg": SIGMA_DEG,
            "eb_compartment_index": int(compartment["EB"]),
            "inhibit_low": INHIBIT_LOW,
            "inhibit_high": INHIBIT_HIGH,
            "scale_dat_low": SCALE_LOW,
            "scale_dat_high": SCALE_HIGH,
            "replay_definition": (
                "Stage3Neuromod.receptor_terms replaces the applied d_v and input gain on the 228 "
                "traced ER cells with the paired driven-vehicle per-chunk trajectory recorded in "
                "the same seed's vehicle arm; the dopamine pool, innervation, source term, "
                "occupancies and every other cell stay live"
            ),
            "transporter_definition": (
                "ScaleDat factor = 1 - inhibition multiplies dat_geno, so Vmax_eff = da.Vmax * "
                "factor; factor 0 is the encoded absence of the target"
            ),
        },
        "fixture": str(DEFAULT_FIXTURE),
        "trace_indices": trace_indices,
        "trace_n": len(trace_indices),
        "cells": [{"engine_index": int(cell["engine_index"]), "root_id": int(cell["root_id"]),
                   "hemibrain_type": cell["hemibrain_type"], "side": cell["side"]} for cell in er_cells],
    }
    dump(destination, output)
    print(f"wrote {destination} ({len(trace_indices)} traced ER cells, {len(ARMS)} arms)", flush=True)


def _make_manipulations(scale_dat_factors: tuple[float, ...]) -> list[Any]:
    from flyonenomics.schema.experiment import ScaleDat

    return [ScaleDat(type="scale_dat", compartments="all", factor=float(factor))
            for factor in scale_dat_factors]


def build_audit(destination: Path) -> None:
    """Reuse stage 2c's audits and add the paired replay audit.

    The replay audit runs the vehicle arm and a vehicle-clamped arm on one
    declared engine and proves the replayed ER terms equal the vehicle
    trajectory chunk by chunk and are not a constant.
    """
    from flyonenomics.schema.named import named_manipulations
    from flyonenomics.types import LayerFlags

    started = time.monotonic()
    targets = _er_targets()
    ctx = _prepare_declared(targets, with_traces=False)
    reference = s2c.dark_reference()
    # Reuse stage 2c's clamp audits and stage 2's disconnect audit verbatim.
    s2c.build_audit(DEFAULT_DISCONNECT_AUDIT)
    stage2c_audit = read(DEFAULT_DISCONNECT_AUDIT)
    replay = _replay_audit(ctx, reference, named_manipulations, LayerFlags)
    output = {
        "class": "development",
        "purpose": "stage 3 replay audit plus the reused stage 2c clamp and stage 2 disconnect audits",
        "declared_substrate_id": DECLARED_SUBSTRATE_ID,
        "reference": reference,
        "replay": replay,
        "stage2c": stage2c_audit,
        "wall_seconds": time.monotonic() - started,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
    }
    dump(destination, output)
    print(json.dumps({
        "replay_equals_vehicle_per_chunk": replay["replay_equals_vehicle_per_chunk"],
        "replay_not_constant": replay["replay_not_constant"],
        "replay_step_count": replay["step_count"],
        "replay_max_abs_dv_difference_mv": replay["max_abs_dv_difference_mv"],
        "replay_max_abs_gain_difference": replay["max_abs_gain_difference"],
    }, indent=2), flush=True)
    print(f"wrote {destination}", flush=True)



def _replay_audit(ctx: dict[str, Any], reference: dict[str, Any], named_manipulations: Any,
                  LayerFlags: Any) -> dict[str, Any]:
    """Prove the replayed ER terms equal the vehicle trajectory, per chunk, not a constant.

    The vehicle path is run first and its applied ER terms are recorded over a
    handful of synthetic chunks while the pool is moved between them.  The
    replay path then replaces those terms with the recorded trajectory (the
    pool is moved identically) and the applied terms are compared chunk by
    chunk.  The recorded trajectory is also checked to be non-constant.
    """
    from flyonenomics.registry.compartments import compartment_index

    engine = ctx["engine"]
    registry = ctx["registry"]
    params = ctx["params"]
    targets = np.asarray(ctx["targets"], dtype=np.int32)
    base_threshold = np.asarray(ctx["base_threshold"], dtype=np.float64)
    layers = LayerFlags(background=True, dopamine_A=True, transporter_C=True, dan_fast_synapses="retain")
    eb = compartment_index()["EB"]
    steps = 6

    def run_path(replay: dict[str, np.ndarray] | None) -> tuple[list[np.ndarray], list[np.ndarray]]:
        engine.restore("declared")
        mod = Stage3Neuromod(registry, params, layers, ctx["dopamine"], base_v_th=base_threshold,
                             schema_version="1.3", drive_groups=ctx["groups"], er_idx=targets,
                             dv_dark_mv=None, gain_dark=None, replay=replay)
        mod.apply_genotype(named_manipulations("wild_type"), engine)
        mod.reset_fast()
        mod.da_c[eb] = 3.3
        dv_chunks: list[np.ndarray] = []
        gain_chunks: list[np.ndarray] = []
        for step in range(steps):
            mod.replay_step = step
            mod.compose()
            # Move the pool between chunks; the replay must track the recorded
            # trajectory, not the pool.
            mod.da_c[eb] += 0.01 * (step + 1)
            dv_chunks.append(np.asarray(mod.last_applied_dv[targets], dtype=np.float64).copy())
            gain_chunks.append(np.asarray(mod.last_applied_gain[targets], dtype=np.float64).copy())
        return dv_chunks, gain_chunks

    # Natural vehicle trajectory over the synthetic chunks.
    vehicle_dv, vehicle_gain = run_path(replay=None)
    replay_dict = {"dv": np.stack(vehicle_dv), "gain": np.stack(vehicle_gain)}
    replay_dv, replay_gain = run_path(replay=replay_dict)
    dv_diff = max(float(np.max(np.abs(a - b))) for a, b in zip(vehicle_dv, replay_dv, strict=True))
    gain_diff = max(float(np.max(np.abs(a - b))) for a, b in zip(vehicle_gain, replay_gain, strict=True))
    all_dv = np.concatenate([a.ravel() for a in vehicle_dv])
    return {
        "class": "development",
        "purpose": "prove the paired replay reproduces the vehicle ER trajectory per chunk and is not a constant",
        "declared_substrate_id": DECLARED_SUBSTRATE_ID,
        "platform": f"{platform.system().lower()}-{platform.machine()}",
        "er_n": int(targets.size),
        "step_count": len(vehicle_dv),
        "max_abs_dv_difference_mv": dv_diff,
        "max_abs_gain_difference": gain_diff,
        "replay_equals_vehicle_per_chunk": bool(dv_diff < 1e-12 and gain_diff < 1e-12),
        "application_cadence": (
            "one value per engine chunk (10 ms), replaced at the same point in the chunk as the "
            "native Neuromod.compose update; no chunk averaging and no one-chunk delay; only the "
            "applied d_v and input gain on the 228 traced ER cells are replaced and no unrelated "
            "threshold contribution is frozen"
        ),
        "natural_dv_spread_over_steps_mv": float(np.max(all_dv) - np.min(all_dv)),
        "replay_not_constant": bool(np.max(all_dv) - np.min(all_dv) > 1e-6),
        "replay_not_constant_is_informational": (
            "true of the paired vehicle trajectory here, but equality to the paired vehicle values "
            "actually applied is the check; a constant true reference would be equally valid"
        ),
        "vehicle_dv_first_step_mv": float(vehicle_dv[0][0]),
        "vehicle_dv_last_step_mv": float(vehicle_dv[-1][0]),
        "vehicle_gain_first_step": float(vehicle_gain[0][0]),
        "vehicle_gain_last_step": float(vehicle_gain[-1][0]),
    }


def _incoming_signed_input(ctx: dict[str, Any], targets: np.ndarray) -> dict[str, np.ndarray]:
    """Signed incoming weight accounting on the traced ER cells, from the composed weights.

    Under ``g += w * gain_i_post`` a gain increase scales negative weights as
    well as positive ones, so the net signed input per cell is not the unsigned
    input.  These arrays are static per cell; the run multiplies them by the
    applied gain.  Units mV.
    """
    pre, post, effective = ctx["pre"], ctx["post"], ctx["effective"]
    mask = np.isin(post, targets)
    inp_pre = np.asarray(pre[mask], dtype=np.int32)
    inp_tpos = np.searchsorted(targets, np.asarray(post[mask], dtype=np.int32))
    inp_w = np.asarray(effective[mask], dtype=np.float64)
    nt = len(targets)
    signed = np.zeros(nt, dtype=np.float64)
    positive = np.zeros(nt, dtype=np.float64)
    negative = np.zeros(nt, dtype=np.float64)
    np.add.at(signed, inp_tpos, inp_w)
    np.add.at(positive, inp_tpos, np.where(inp_w > 0, inp_w, 0.0))
    np.add.at(negative, inp_tpos, np.where(inp_w < 0, inp_w, 0.0))
    return {"incoming_pre": inp_pre, "incoming_tpos": inp_tpos, "incoming_w": inp_w,
            "signed_weight_sum_mV": signed, "positive_weight_sum_mV": positive,
            "negative_weight_sum_mV": negative}


def run_seed(job: tuple[int, str, str]) -> str:
    """Run all seven arms for one seed in one built engine, paired on the same stream."""
    from flyonenomics.behaviour.arena import Behaviour
    from flyonenomics.orchestrator.seeds import brian_seed
    from flyonenomics.types import LayerFlags

    seed, plan_path, destination = job
    destination_path = Path(destination)
    plan = read(Path(plan_path))
    probe_s = float(plan["protocol"]["probe_s"])
    settle_s = float(plan["protocol"]["settle_s"])
    eb_index = int(plan["protocol"]["eb_compartment_index"])
    targets = np.asarray(plan["trace_indices"], dtype=np.int32)
    if not len(targets) or len(np.unique(targets)) != len(targets):
        raise ValueError("plan supplied an invalid trace target set")
    started = time.monotonic()
    ctx = _prepare_declared(targets, with_traces=True)
    engine, params, registry = ctx["engine"], ctx["params"], ctx["registry"]
    source = ctx["source"]
    dopamine_neurons = ctx["dopamine_neurons"]
    extended = ctx["extended"]
    dopamine = ctx["dopamine"]
    effective = ctx["effective"]
    roots = ctx["roots"]
    pre, post = ctx["pre"], ctx["post"]
    targets = ctx["targets"]
    base_threshold = ctx["base_threshold"]
    groups = ctx["groups"]
    dopamine_positions = np.searchsorted(extended, dopamine_neurons)
    target_position = np.full(registry.n, -1, dtype=np.int32)
    target_position[targets] = np.arange(len(targets), dtype=np.int32)

    def incoming(source_idx: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        mask = np.isin(pre, source_idx) & np.isin(post, targets)
        return (np.asarray(pre[mask], dtype=np.int32), target_position[np.asarray(post[mask], dtype=np.int32)],
                effective[mask])

    tubu_pre, tubu_post, tubu_w = incoming(np.asarray(source, dtype=np.int32))
    da_pre, da_post, da_w = incoming(dopamine_neurons)
    dan_neurons = np.asarray(registry.population("DAN").idx, dtype=np.int32)
    signed_input = _incoming_signed_input(ctx, targets)
    inp_pre = signed_input["incoming_pre"]
    inp_tpos = signed_input["incoming_tpos"]
    inp_w = signed_input["incoming_w"]
    rows = []
    chunk_ms = float(params.get("engine.chunk_ms"))
    settle_chunks = int(round(settle_s * 1000.0 / chunk_ms))
    total_chunks = int(round(probe_s * 1000.0 / chunk_ms))
    n_comp = len(registry.compartments())
    trajectories: dict[str, dict[str, np.ndarray]] = {}

    for arm in plan["protocol"]["arms"]:
        label = arm["label"]
        replay_source = arm.get("replay")
        replay = trajectories.get(str(replay_source)) if replay_source else None
        engine.restore("declared")
        engine.seed(brian_seed(MASTER, seed, 0))
        mod = Stage3Neuromod(
            registry, params,
            LayerFlags(background=True, dopamine_A=True, transporter_C=True,
                       dan_fast_synapses=arm["dan_fast_synapses"]),
            dopamine, base_v_th=base_threshold, schema_version="1.3", drive_groups=groups,
            er_idx=targets, dv_dark_mv=None, gain_dark=None, replay=replay,
        )
        mod.apply_genotype(_make_manipulations(tuple(arm["scale_dat_factors"])), engine)
        mod.reset_fast()
        mod.replay_step = 0
        composed = mod.compose()
        engine.set_threshold(composed.v_th)
        engine.set_gain(composed.gain)
        engine.compose_refractory()
        arena = Behaviour(
            SimpleNamespace(topology=ctx["topology"]), registry, params, probe(label),
            v_fwd=0.0, sign_steer=1, K_steer=0.0, r_vis_max=TUBU_MAX_HZ, sigma_vis=SIGMA_DEG,
        )
        arena.reset(np.random.default_rng(seed))
        count = np.zeros(registry.n, dtype=np.int64)
        source_events = np.zeros(len(targets), dtype=np.float64)
        da_events = np.zeros(len(targets), dtype=np.float64)
        signed_event = np.zeros(len(targets), dtype=np.float64)
        positive_event = np.zeros(len(targets), dtype=np.float64)
        negative_event = np.zeros(len(targets), dtype=np.float64)
        gain_weighted_signed = np.zeros(len(targets), dtype=np.float64)
        threshold_sum = np.zeros(len(targets), dtype=np.float64)
        threshold_min = np.full(len(targets), np.inf)
        threshold_max = np.full(len(targets), -np.inf)
        natural_dv_sum = np.zeros(len(targets), dtype=np.float64)
        applied_dv_sum = np.zeros(len(targets), dtype=np.float64)
        natural_gain_sum = np.zeros(len(targets), dtype=np.float64)
        applied_gain_sum = np.zeros(len(targets), dtype=np.float64)
        natural_dv_chunks: list[float] = []
        applied_dv_chunks: list[float] = []
        natural_gain_chunks: list[float] = []
        applied_gain_chunks: list[float] = []
        full_dv_trajectory = np.empty((total_chunks, len(targets)), dtype=np.float64)
        full_gain_trajectory = np.empty((total_chunks, len(targets)), dtype=np.float64)
        da_sum = np.zeros(n_comp, dtype=np.float64)
        da_min = np.full(n_comp, np.inf)
        da_max = np.full(n_comp, -np.inf)
        measurement_chunks = 0
        measure_tick = None
        input_min = np.inf
        input_max = -np.inf
        drive_hz = float(arm["drive_hz"])
        for step in range(total_chunks):
            rate = arena.rates(arena.view(), step * chunk_ms / 1000.0)
            if drive_hz:
                rate[dopamine_positions] += drive_hz
            input_min = min(input_min, float(rate.min(initial=0.0)))
            input_max = max(input_max, float(rate.max(initial=0.0)))
            engine.set_input_rates(rate)
            if step == settle_chunks:
                measure_tick = engine.tick()
            mod.replay_step = step
            composed = mod.compose()
            engine.set_threshold(composed.v_th)
            engine.set_gain(composed.gain)
            gain_before = np.asarray(composed.gain[targets], dtype=np.float64)
            full_dv_trajectory[step] = np.asarray(mod.last_applied_dv[targets], dtype=np.float64)
            full_gain_trajectory[step] = np.asarray(mod.last_applied_gain[targets], dtype=np.float64)
            result = engine.run_chunk(chunk_ms)
            mod.on_chunk(result.counts, chunk_ms / 1000.0)
            if step >= settle_chunks:
                count += result.counts
                amplitude = result.counts[tubu_pre] * tubu_w * gain_before[tubu_post]
                source_events += np.bincount(tubu_post, weights=amplitude, minlength=len(targets))
                intended = result.counts[da_pre] * da_w * gain_before[da_post]
                if arm["dan_fast_synapses"] == "retain":
                    da_events += np.bincount(da_post, weights=intended, minlength=len(targets))
                # Separate signed input accounting: the full set of incoming
                # edges, split by the sign of the composed weight.
                contrib = result.counts[inp_pre] * inp_w * gain_before[inp_tpos]
                signed_event += np.bincount(inp_tpos, weights=contrib, minlength=len(targets))
                positive_event += np.bincount(inp_tpos, weights=np.where(contrib > 0, contrib, 0.0),
                                              minlength=len(targets))
                negative_event += np.bincount(inp_tpos, weights=np.where(contrib < 0, contrib, 0.0),
                                              minlength=len(targets))
                gain_weighted_signed += np.bincount(
                    inp_tpos, weights=inp_w * gain_before[inp_tpos], minlength=len(targets))
                threshold = np.asarray(composed.v_th[targets], dtype=np.float64)
                threshold_sum += threshold
                np.minimum(threshold_min, threshold, out=threshold_min)
                np.maximum(threshold_max, threshold, out=threshold_max)
                natural = np.asarray(mod.last_natural_dv[targets], dtype=np.float64)
                applied = np.asarray(mod.last_applied_dv[targets], dtype=np.float64)
                natural_dv_sum += natural
                applied_dv_sum += applied
                natural_gain = np.asarray(mod.last_natural_gain[targets], dtype=np.float64)
                applied_gain = np.asarray(mod.last_applied_gain[targets], dtype=np.float64)
                natural_gain_sum += natural_gain
                applied_gain_sum += applied_gain
                natural_dv_chunks.append(float(natural[0]))
                applied_dv_chunks.append(float(applied[0]))
                natural_gain_chunks.append(float(natural_gain[0]))
                applied_gain_chunks.append(float(applied_gain[0]))
                da_sum += mod.da_c
                np.minimum(da_min, mod.da_c, out=da_min)
                np.maximum(da_max, mod.da_c, out=da_max)
                measurement_chunks += 1
        if measure_tick is None:
            raise RuntimeError("measurement tick was not set")
        trajectories[label] = {"dv": full_dv_trajectory, "gain": full_gain_trajectory}
        traces = engine.traces(measure_tick)
        if not np.array_equal(traces.idx, targets) or traces.v_mv.shape[1] == 0:
            raise ValueError("trace target order or measurement window is wrong")
        target_rows = []
        for position, target in enumerate(targets):
            values = traces.v_mv[position]
            target_rows.append({
                "engine_index": int(target),
                "root_id": int(roots[target]),
                "spike_count": int(count[target]),
                "spike_rate_hz": float(count[target] / (probe_s - settle_s)),
                "source_event_amplitude_mV": float(source_events[position]),
                "cx_dan_event_amplitude_mV": float(da_events[position]),
                "signed_input_event_mV": float(signed_event[position]),
                "positive_input_event_mV": float(positive_event[position]),
                "negative_input_event_mV": float(negative_event[position]),
                "gain_weighted_signed_input_mV": float(gain_weighted_signed[position]),
                "signed_weight_sum_mV": float(signed_input["signed_weight_sum_mV"][position]),
                "positive_weight_sum_mV": float(signed_input["positive_weight_sum_mV"][position]),
                "negative_weight_sum_mV": float(signed_input["negative_weight_sum_mV"][position]),
                "sampled_mean_v_mV": float(values.mean()),
                "sampled_min_v_mV": float(values.min()),
                "sampled_max_v_mV": float(values.max()),
                "threshold_mean_mV": float(threshold_sum[position] / measurement_chunks),
                "threshold_min_mV": float(threshold_min[position]),
                "threshold_max_mV": float(threshold_max[position]),
                "mean_distance_to_threshold_mV": float(threshold_sum[position] / measurement_chunks - values.mean()),
                "nearest_sampled_distance_to_threshold_mV": float(threshold_min[position] - values.max()),
                "natural_dv_mean_mV": float(natural_dv_sum[position] / measurement_chunks),
                "applied_dv_mean_mV": float(applied_dv_sum[position] / measurement_chunks),
                "natural_gain_mean": float(natural_gain_sum[position] / measurement_chunks),
                "applied_gain_mean": float(applied_gain_sum[position] / measurement_chunks),
            })
        rows.append({
            "condition": label,
            "scale_dat_factors": list(arm["scale_dat_factors"]),
            "replay": replay_source,
            "dan_fast_synapses": arm["dan_fast_synapses"],
            "dopamine_drive_hz": drive_hz,
            "source_population": SOURCE_POPULATION,
            "source_n": int(len(source)),
            "source_spikes": int(count[source].sum()),
            "source_rate_hz": float(count[source].sum() / (len(source) * (probe_s - settle_s))),
            "dopamine_population": DOPAMINE_POPULATION,
            "dopamine_n": int(len(dopamine_neurons)),
            "dopamine_spikes": int(count[dopamine_neurons].sum()),
            "dopamine_rate_hz": float(count[dopamine_neurons].sum() / (len(dopamine_neurons) * (probe_s - settle_s))),
            "dan_population": "DAN",
            "dan_n": int(len(dan_neurons)),
            "dan_spikes": int(count[dan_neurons].sum()),
            "dan_rate_hz": float(count[dan_neurons].sum() / (len(dan_neurons) * (probe_s - settle_s))),
            "input_rate_min_hz": float(input_min),
            "input_rate_max_hz": float(input_max),
            "targets": target_rows,
            "eb_da_mean_um": float(da_sum[eb_index] / measurement_chunks),
            "eb_da_min_um": float(da_min[eb_index]),
            "eb_da_max_um": float(da_max[eb_index]),
            "da_mean_um": (da_sum / measurement_chunks).tolist(),
            "natural_dv_chunks_mV": natural_dv_chunks,
            "applied_dv_chunks_mV": applied_dv_chunks,
            "natural_gain_chunks": natural_gain_chunks,
            "applied_gain_chunks": applied_gain_chunks,
            "compartments": [compartment.name for compartment in registry.compartments()],
            "trace_samples": int(traces.v_mv.shape[1]),
        })
        print("seed", seed, label, "complete", flush=True)
    dump(destination_path / f"seed-{seed}.json", {
        "identity": {
            **plan["identity"],
            "platform": f"{platform.system().lower()}-{platform.machine()}",
            "scale_sha256": digest(ctx["scale"], np.float32),
            "background_sha256": digest(ctx["background"]),
        },
        "seed": seed,
        "brian_seed": brian_seed(MASTER, seed, 0),
        "settle_s": settle_s,
        "probe_s": probe_s,
        "brain_seconds": probe_s * len(plan["protocol"]["arms"]),
        "rows": rows,
        "wall_seconds": time.monotonic() - started,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
    })
    return f"seed-{seed}.json"


def run_dynamic(plan_path: Path, destination: Path, workers: int, seeds: tuple[int, ...]) -> None:
    plan = read(plan_path)
    plan["identity"] = identity(f"{platform.system().lower()}-{platform.machine()}")
    dump(plan_path, plan)
    destination.mkdir(parents=True, exist_ok=True)
    jobs = [(seed, str(plan_path.resolve()), str(destination.resolve())) for seed in seeds]
    with ProcessPoolExecutor(
        max_workers=workers, mp_context=multiprocessing.get_context("spawn"),
        max_tasks_per_child=1,
    ) as pool:
        print(list(pool.map(run_seed, jobs)), flush=True)


# ---------------------------------------------------------------------------
# Summarize
# ---------------------------------------------------------------------------

AGGREGATE_KEYS = (
    "er_spikes", "active_cells", "mean_v_mV", "max_v_mV", "threshold_mV",
    "mean_distance_mV", "nearest_distance_mV", "cx_dan_event_total_mV",
    "applied_dv_mV", "applied_gain", "source_rate_hz", "dopamine_rate_hz",
    "dopamine_spikes", "dan_spikes", "dan_rate_hz", "eb_da_mean_um", "eb_da_max_um",
    "signed_input_event_mV", "positive_input_event_mV", "negative_input_event_mV",
    "gain_weighted_signed_input_mV",
)


def _seed_aggregate(run: dict[str, Any], label: str) -> dict[str, Any]:
    row = next(item for item in run["rows"] if item["condition"] == label)
    targets = row["targets"]
    spikes = [int(item["spike_count"]) for item in targets]
    return {
        "er_spikes": int(sum(spikes)),
        "active_cells": int(sum(value > 0 for value in spikes)),
        "mean_v_mV": float(np.mean([float(item["sampled_mean_v_mV"]) for item in targets])),
        "max_v_mV": float(np.max([float(item["sampled_max_v_mV"]) for item in targets])),
        "threshold_mV": float(np.mean([float(item["threshold_mean_mV"]) for item in targets])),
        "mean_distance_mV": float(np.mean([float(item["mean_distance_to_threshold_mV"]) for item in targets])),
        "nearest_distance_mV": float(np.mean([float(item["nearest_sampled_distance_to_threshold_mV"]) for item in targets])),
        "cx_dan_event_total_mV": float(np.sum([float(item["cx_dan_event_amplitude_mV"]) for item in targets])),
        "applied_dv_mV": float(np.mean([float(item["applied_dv_mean_mV"]) for item in targets])),
        "applied_gain": float(np.mean([float(item["applied_gain_mean"]) for item in targets])),
        "source_rate_hz": float(row["source_rate_hz"]),
        "dopamine_rate_hz": float(row["dopamine_rate_hz"]),
        "dopamine_spikes": int(row["dopamine_spikes"]),
        "dan_spikes": int(row["dan_spikes"]),
        "dan_rate_hz": float(row["dan_rate_hz"]),
        "eb_da_mean_um": float(row["eb_da_mean_um"]),
        "eb_da_max_um": float(row["eb_da_max_um"]),
        "signed_input_event_mV": float(np.sum([float(item["signed_input_event_mV"]) for item in targets])),
        "positive_input_event_mV": float(np.sum([float(item["positive_input_event_mV"]) for item in targets])),
        "negative_input_event_mV": float(np.sum([float(item["negative_input_event_mV"]) for item in targets])),
        "gain_weighted_signed_input_mV": float(np.sum([float(item["gain_weighted_signed_input_mV"]) for item in targets])),
    }


def _contrast(paired_runs: list[dict[str, Any]], left: str, right: str) -> dict[str, Any]:
    values: dict[str, list[float]] = {key: [] for key in AGGREGATE_KEYS}
    for run in paired_runs:
        a = _seed_aggregate(run, left)
        b = _seed_aggregate(run, right)
        for key in AGGREGATE_KEYS:
            values[key].append(float(a[key]) - float(b[key]))
    output = {
        "left": left,
        "right": right,
        "unit": "paired difference is left minus right over the ten seeds; interval is mean +/- 1.96 SE",
    }
    for key in AGGREGATE_KEYS:
        output[key] = _paired_interval(values[key])
    output["seed_values"] = values
    output["resolution"] = {
        "unit": (
            "confidence-interval half-width from the measured standard error over ten paired "
            "contrasts; 1.96 SE is the project convention and 2.262 SE is the paired-t multiplier "
            "at n=10. This is not a powered minimum detectable effect and is not computed from 228 "
            "cells as independent replicates. Neither is a pass line."
        ),
        "spikes_se": float(output["er_spikes"]["se"]),
        "spikes_1.96_se": float(1.96 * output["er_spikes"]["se"]),
        "spikes_2.262_se": float(2.262 * output["er_spikes"]["se"]),
    }
    from scipy import stats

    spikes = np.asarray(values["er_spikes"], dtype=np.float64)
    n = len(spikes)
    if n > 1 and spikes.std(ddof=1) > 0:
        t = float(spikes.mean() / (spikes.std(ddof=1) / np.sqrt(n)))
        p_value = float(2.0 * stats.t.sf(abs(t), n - 1))
    else:
        t = 0.0
        p_value = 1.0
    output["tests"] = {
        "n": n, "t": t, "df": n - 1, "p_two_sided_nominal": p_value,
        "note": "nominal paired-t test, no multiplicity adjustment; not a pass line (item 121)",
    }
    return output


def _arm_hits(runs: list[dict[str, Any]]) -> dict[str, int]:
    labels = {label: 0 for label in ARM_LABELS}
    fire = {label: set() for label in ARM_LABELS}
    for run in runs:
        for label in ARM_LABELS:
            row = next(item for item in run["rows"] if item["condition"] == label)
            for target in row["targets"]:
                if int(target["spike_count"]) > 0:
                    fire[label].add(int(target["engine_index"]))
    for label in ARM_LABELS:
        labels[label] = len(fire[label])
    return labels


def summarize(raw: Path, plan_path: Path, destination: Path, seeds: tuple[int, ...]) -> None:
    from flyonenomics.io import hash_file

    plan = read(plan_path)
    record = read(destination)
    runs = [read(raw / f"seed-{seed}.json") for seed in seeds]
    probe_s = float(plan["protocol"]["probe_s"])
    n_arms = len(plan["protocol"]["arms"])
    if sum(float(run["brain_seconds"]) for run in runs) != probe_s * n_arms * len(seeds):
        raise ValueError("paired probe brain-second total differs from the plan")
    identities = [run["identity"] for run in runs]
    if any(value != identities[0] for value in identities[1:]):
        raise ValueError("seed execution identities differ")
    cells = plan["cells"]

    per_cell = []
    for cell in cells:
        index = int(cell["engine_index"])
        arm_values: dict[str, dict[str, list[float]]] = {}
        for run in runs:
            for label in ARM_LABELS:
                row = next(item for item in run["rows"] if item["condition"] == label)
                target = next(item for item in row["targets"] if int(item["engine_index"]) == index)
                bucket = arm_values.setdefault(label, {
                    "spike": [], "mean_v_mV": [], "threshold_mV": [], "applied_dv_mV": [],
                    "applied_gain": [], "signed_input_event_mV": [], "positive_input_event_mV": [],
                    "negative_input_event_mV": [], "gain_weighted_signed_input_mV": [],
                    "signed_weight_sum_mV": [], "positive_weight_sum_mV": [], "negative_weight_sum_mV": [],
                    "source_event_mV": [], "cx_dan_event_mV": [],
                })
                bucket["spike"].append(int(target["spike_count"]))
                bucket["mean_v_mV"].append(float(target["sampled_mean_v_mV"]))
                bucket["threshold_mV"].append(float(target["threshold_mean_mV"]))
                bucket["applied_dv_mV"].append(float(target["applied_dv_mean_mV"]))
                bucket["applied_gain"].append(float(target["applied_gain_mean"]))
                bucket["signed_input_event_mV"].append(float(target["signed_input_event_mV"]))
                bucket["positive_input_event_mV"].append(float(target["positive_input_event_mV"]))
                bucket["negative_input_event_mV"].append(float(target["negative_input_event_mV"]))
                bucket["gain_weighted_signed_input_mV"].append(float(target["gain_weighted_signed_input_mV"]))
                bucket["signed_weight_sum_mV"].append(float(target["signed_weight_sum_mV"]))
                bucket["positive_weight_sum_mV"].append(float(target["positive_weight_sum_mV"]))
                bucket["negative_weight_sum_mV"].append(float(target["negative_weight_sum_mV"]))
                bucket["source_event_mV"].append(float(target["source_event_amplitude_mV"]))
                bucket["cx_dan_event_mV"].append(float(target["cx_dan_event_amplitude_mV"]))
        arms_out: dict[str, Any] = {}
        for label in ARM_LABELS:
            bucket = arm_values[label]
            arms_out[label] = {
                "spike_values": bucket["spike"],
                "mean_spike": float(np.mean(bucket["spike"])),
                "active_seeds": int(sum(value > 0 for value in bucket["spike"])),
                "mean_v_values_mV": bucket["mean_v_mV"],
                "threshold_values_mV": bucket["threshold_mV"],
                "applied_dv_values_mV": bucket["applied_dv_mV"],
                "applied_gain_values": bucket["applied_gain"],
                "signed_input_event_values_mV": bucket["signed_input_event_mV"],
                "positive_input_event_values_mV": bucket["positive_input_event_mV"],
                "negative_input_event_values_mV": bucket["negative_input_event_mV"],
                "gain_weighted_signed_input_values_mV": bucket["gain_weighted_signed_input_mV"],
                "signed_weight_sum_mV": bucket["signed_weight_sum_mV"][0],
                "positive_weight_sum_mV": bucket["positive_weight_sum_mV"][0],
                "negative_weight_sum_mV": bucket["negative_weight_sum_mV"][0],
                "source_event_values_mV": bucket["source_event_mV"],
                "cx_dan_event_values_mV": bucket["cx_dan_event_mV"],
            }
        per_cell.append({**cell, "arms": arms_out})

    seed_spikes = {label: [_seed_aggregate(run, label)["er_spikes"] for run in runs]
                   for label in ARM_LABELS}

    summary = {
        "n_cells": len(per_cell),
        "n_arms": n_arms,
        "n_seeds": len(runs),
        "arms": {label: {"seed_er_spikes": seed_spikes[label]} for label in ARM_LABELS},
        "active_cells_any_seed": _arm_hits(runs),
    }

    contrasts = {name: _contrast(runs, left, right) for name, left, right in PRIMARY_CONTRASTS}

    # Multiplicity: the plan did not prespecify one primary among the two
    # inhibition-vs-vehicle tests, so report the nominal p-values and a Holm
    # adjustment across those two; no primary is invented retrospectively.
    holm_members = ("inhibit_low_minus_vehicle", "inhibit_high_minus_vehicle")
    ordered = sorted(((name, contrasts[name]["tests"]["p_two_sided_nominal"])
                      for name in holm_members), key=lambda item: item[1])
    adjusted: dict[str, float] = {}
    running = 0.0
    for rank, (name, p_value) in enumerate(ordered):
        value = min(1.0, p_value * (len(ordered) - rank))
        running = max(running, value)
        adjusted[name] = running
    high_vehicle_values = contrasts["inhibit_high_minus_vehicle"]["seed_values"]["er_spikes"]
    high_vehicle_sorted = sorted(high_vehicle_values, reverse=True)
    multiplicity = {
        "unit": (
            "nominal paired-t p-values over ten paired contrasts for every primary contrast, and "
            "a Holm adjustment across the two inhibition-vs-vehicle tests only.  No contrast was "
            "prespecified as the sole primary, so none is promoted retrospectively."
        ),
        "nominal_p": {name: contrasts[name]["tests"]["p_two_sided_nominal"] for name in contrasts},
        "holm_family": list(holm_members),
        "holm_adjusted_p": adjusted,
        "high_minus_vehicle_seed_sensitivity": {
            "seed_values": high_vehicle_values,
            "mean_after_dropping_largest": float(np.mean(high_vehicle_sorted[1:])),
            "mean_after_dropping_two_largest": float(np.mean(high_vehicle_sorted[2:])),
            "note": "the earlier +35.8 claim was an arithmetic error; the recomputed two-drop mean is +39.125",
        },
        "note": (
            "the high-level increase is nominal evidence that weakens under the two-test Holm "
            "adjustment; it is a small increase, not an established multiplicity-controlled effect"
        ),
    }

    # The clamp's chemistry: the applied ER terms are pinned exactly, but the
    # EB trajectory is not held fixed.  Report both EB differences and the
    # transient range so '% including zero' is read as no detected difference in
    # mean EB, not as unchanged chemistry.
    clamp_equivalence = {
        "applied_terms_pinned": (
            "inhibit-high-clamped replays the vehicle applied d_v and gain exactly, so "
            "applied_dv_delta and applied_gain_delta versus vehicle are exactly 0 by construction"
        ),
        "eb_da_high_clamped_minus_vehicle": contrasts["inhibit_high_clamped_minus_vehicle"]["eb_da_mean_um"],
        "eb_da_high_clamped_minus_high": contrasts["inhibit_high_minus_inhibit_high_clamped"]["eb_da_mean_um"],
        "note": (
            "EB dopamine stays elevated relative to vehicle under the clamp; the clamp's own "
            "effect on mean EB is the high-minus-high-clamped interval.  An interval including "
            "zero is no detected difference in mean EB, not unchanged chemistry, and a transient "
            "EB discrepancy is not excluded."
        ),
    }
    clamp_interpretation = {
        "strongest_permitted_reading": (
            "pinning both applied ER terms to the paired driven-vehicle trajectory removes the "
            "detected effect, and nothing detectable remains"
        ),
        "limits": (
            "d_v and gain are pinned together, so the clamp cannot single out the threshold term "
            "or rule out gain.  The -28.6 spike residual interval includes zero and remains "
            "unresolved; it is not equivalence or proof that no indirect effect remains.  Why "
            "spikes rise while event-weighted signed input falls is also unresolved."
        ),
    }

    # Vehicle replay check: per-chunk equality of the replayed applied terms.
    def chunk_sequence(label: str, key: str) -> dict[int, list[float]]:
        return {int(run["seed"]): [float(v) for v in
                next(item for item in run["rows"] if item["condition"] == label)[key]]
                for run in runs}

    veh_dv = chunk_sequence("vehicle", "applied_dv_chunks_mV")
    veh_clamped_dv = chunk_sequence("vehicle-clamped", "applied_dv_chunks_mV")
    veh_gain = chunk_sequence("vehicle", "applied_gain_chunks")
    veh_clamped_gain = chunk_sequence("vehicle-clamped", "applied_gain_chunks")
    dv_max = max(abs(a - b) for seed in veh_dv for a, b in zip(veh_dv[seed], veh_clamped_dv[seed], strict=True))
    gain_max = max(abs(a - b) for seed in veh_gain for a, b in zip(veh_gain[seed], veh_clamped_gain[seed], strict=True))
    all_veh_dv = [v for seed in veh_dv for v in veh_dv[seed]]
    replay_audit = {
        "vehicle_vs_vehicle_clamped_max_abs_dv_difference_mv": float(dv_max),
        "vehicle_vs_vehicle_clamped_max_abs_gain_difference": float(gain_max),
        "replay_equals_vehicle_per_chunk": bool(dv_max < 1e-12 and gain_max < 1e-12),
        "vehicle_dv_sequence_spread_mv": float(max(all_veh_dv) - min(all_veh_dv)),
        "replay_not_constant": bool(max(all_veh_dv) - min(all_veh_dv) > 1e-6),
        "replay_not_constant_is_informational": (
            "true of the paired vehicle trajectory here, but equality to the paired vehicle values "
            "actually applied is the check; a constant true reference would be equally valid"
        ),
        "application_cadence": (
            "one value per engine chunk (10 ms), replaced at the same point in the chunk as the "
            "native Neuromod.compose update; no chunk averaging and no one-chunk delay; only the "
            "applied d_v and input gain on the 228 traced ER cells are replaced and no unrelated "
            "threshold contribution is frozen"
        ),
        "unit": "per measurement chunk, targets[0], over the ten seeds",
    }

    # Per-cell and per-subtype changes for the primary contrasts.
    def per_cell_distribution(left: str, right: str) -> dict[str, Any]:
        deltas = np.asarray([np.mean(cell["arms"][left]["spike_values"])
                             - np.mean(cell["arms"][right]["spike_values"]) for cell in per_cell],
                            dtype=np.float64)
        out = _distribution([float(value) for value in deltas])
        out["positive"] = int(np.sum(deltas > 1e-9))
        out["negative"] = int(np.sum(deltas < -1e-9))
        out["zero"] = int(np.sum(np.abs(deltas) <= 1e-9))
        return out

    def per_subtype(left: str, right: str) -> dict[str, Any]:
        subtypes: dict[str, list[float]] = {}
        for cell in per_cell:
            delta = float(np.mean(cell["arms"][left]["spike_values"]) - np.mean(cell["arms"][right]["spike_values"]))
            subtypes.setdefault(str(cell["hemibrain_type"]), []).append(delta)
        return {name: {"n": len(values), "mean_spike_delta": float(np.mean(values)),
                       "total_spike_delta": float(np.sum(values))}
                for name, values in sorted(subtypes.items())}

    per_cell_changes = {}
    for name, left, right in PRIMARY_CONTRASTS:
        per_cell_changes[name] = {
            "per_cell_spike_delta_distribution": per_cell_distribution(left, right),
            "per_subtype_spike_delta": per_subtype(left, right),
        }

    # Cumulative signed, gain-weighted synaptic-state increment over the 228
    # traced ER cells and the 18 s window, in voltage-equivalent event units.
    # The gain is the gain applied at each chunk (per event), not an arm-average
    # gain.  This is an input increment, not a membrane hyperpolarisation.
    def arm_input_totals(label: str) -> dict[str, float]:
        def total(key: str) -> float:
            return float(sum(np.mean(cell["arms"][label][key]) for cell in per_cell))
        signed = total("signed_input_event_values_mV")
        source = total("source_event_values_mV")
        cx_dan = total("cx_dan_event_values_mV")
        return {
            "signed_input_event_mV": signed,
            "positive_input_event_mV": total("positive_input_event_values_mV"),
            "negative_input_event_mV": total("negative_input_event_values_mV"),
            "tu_bu_event_mV": source,
            "cx_dan_event_mV": cx_dan,
            "other_sources_event_mV": signed - source - cx_dan,
        }

    def seed_total_signed(label: str) -> list[float]:
        return [float(sum(cell["arms"][label]["signed_input_event_values_mV"][i]
                          for cell in per_cell)) for i in range(len(seeds))]

    def seed_total_edge_inventory(label: str) -> list[float]:
        return [float(sum(cell["arms"][label]["gain_weighted_signed_input_values_mV"][i]
                          for cell in per_cell)) for i in range(len(seeds))]

    active_from_vehicle = {int(cell["engine_index"]): bool(np.mean(cell["arms"]["vehicle"]["spike_values"]) > 0)
                           for cell in per_cell}

    signed_input = {
        "quantity": (
            "cumulative signed, gain-weighted synaptic-state increment over the 228 traced ER "
            "cells and the 18 s window, in voltage-equivalent event units.  Positive means "
            "depolarising input.  It is an input increment, not a membrane hyperpolarisation, "
            "and a more negative value means less net depolarising input, not a hyperpolarising "
            "current."
        ),
        "raw_field": "signed_input_event_mV",
        "gain_used": (
            "the gain applied at each chunk (per event), not an arm-average gain; run_seed "
            "accumulates counts[pre] * w * gain_before[post] with the chunk's applied gain"
        ),
        "absolute_totals_mV": {label: arm_input_totals(label) for label in ARM_LABELS},
        "contrasts": {},
        "superseded_edge_inventory": {
            "raw_field": "gain_weighted_signed_input_mV",
            "quantity": (
                "cumulative per-chunk signed incoming-edge inventory over the 228 traced ER "
                "cells and 18 s window: sum w * applied_gain once per incoming edge per chunk, "
                "without presynaptic event counts"
            ),
            "why_superseded": (
                "the raw field name is misleading: this is not delivered synaptic input because "
                "it omits counts[pre].  It was the source of the earlier -230526.85 mV report.  "
                "The event-weighted signed_input_event_mV quantity above is the correct measure "
                "for claims about delivered cumulative synaptic-state increments.  Both are kept "
                "so the post-run definition change is visible."
            ),
            "contrasts": {},
        },
    }
    for name in ("inhibit_low_minus_vehicle", "inhibit_high_minus_vehicle",
                 "inhibit_high_minus_inhibit_high_clamped", "inhibit_high_minus_vehicle_dat_disabled"):
        left, right = next((l, r) for n, l, r in PRIMARY_CONTRASTS if n == name)
        lt, rt = arm_input_totals(left), arm_input_totals(right)
        delta = {key: lt[key] - rt[key] for key in lt}
        seed_delta = [a - b for a, b in zip(seed_total_signed(left), seed_total_signed(right), strict=True)]
        active_deltas = [float(np.mean(cell["arms"][left]["signed_input_event_values_mV"])
                               - np.mean(cell["arms"][right]["signed_input_event_values_mV"]))
                         for cell in per_cell if active_from_vehicle[int(cell["engine_index"])]]
        silent_deltas = [float(np.mean(cell["arms"][left]["signed_input_event_values_mV"])
                               - np.mean(cell["arms"][right]["signed_input_event_values_mV"]))
                         for cell in per_cell if not active_from_vehicle[int(cell["engine_index"])]]
        signed_input["contrasts"][name] = {
            "delta": delta,
            "signed_interval_mV": _paired_interval(seed_delta),
            "positive_input_event_delta_mV": delta["positive_input_event_mV"],
            "negative_input_event_delta_mV": delta["negative_input_event_mV"],
            "signed_net_input_event_delta_mV": delta["signed_input_event_mV"],
            "tu_bu_event_delta_mV": delta["tu_bu_event_mV"],
            "cx_dan_event_delta_mV": delta["cx_dan_event_mV"],
            "other_sources_event_delta_mV": delta["other_sources_event_mV"],
            "active_from_vehicle": {
                "n": len(active_deltas), "mean_signed_input_delta_mV": float(np.mean(active_deltas)),
                "total_signed_input_delta_mV": float(np.sum(active_deltas)),
            },
            "silent_from_vehicle": {
                "n": len(silent_deltas), "mean_signed_input_delta_mV": float(np.mean(silent_deltas)),
                "total_signed_input_delta_mV": float(np.sum(silent_deltas)),
            },
            "gain_times_signed_weight_sum_delta_mV": sum(
                float(np.mean(cell["arms"][left]["applied_gain_values"]))
                * float(cell["arms"][left]["signed_weight_sum_mV"])
                - float(np.mean(cell["arms"][right]["applied_gain_values"]))
                * float(cell["arms"][right]["signed_weight_sum_mV"]) for cell in per_cell),
        }

    for name in ("inhibit_low_minus_vehicle", "inhibit_high_minus_vehicle"):
        left, right = next((l, r) for n, l, r in PRIMARY_CONTRASTS if n == name)
        inventory_delta = [a - b for a, b in zip(
            seed_total_edge_inventory(left), seed_total_edge_inventory(right), strict=True)]
        signed_input["superseded_edge_inventory"]["contrasts"][name] = {
            "seed_values_mV": inventory_delta,
            "interval_mV": _paired_interval(inventory_delta),
        }

    # The measured operating point, for the saturation reading.  The realised
    # uptake flux at the measured EB mean is reported separately from the
    # fractional parameter inhibition.
    vmax0 = 0.11
    km = 1.3
    scale_of = {arm["label"]: (1.0 if not arm["scale_dat_factors"]
                               else float(np.prod([factor for factor in arm["scale_dat_factors"]])))
                for arm in ARMS}
    operating_point = {}
    for label in ARM_LABELS:
        eb_mean = float(np.mean([_seed_aggregate(run, label)["eb_da_mean_um"] for run in runs]))
        vmax_eff = vmax0 * scale_of[label]
        realised_flux = float(vmax_eff * eb_mean / (km + eb_mean)) if vmax_eff > 0 else 0.0
        operating_point[label] = {
            "eb_da_mean_um": eb_mean,
            "vmax_eff_um_s": vmax_eff,
            "realised_flux_window_mean_um_s": realised_flux,
            "eb_da_max_um": float(np.mean([_seed_aggregate(run, label)["eb_da_max_um"] for run in runs])),
            "applied_dv_window_mean_mv": float(np.mean([_seed_aggregate(run, label)["applied_dv_mV"] for run in runs])),
            "applied_gain_window_mean": float(np.mean([_seed_aggregate(run, label)["applied_gain"] for run in runs])),
        }

    fresh_part_a = part_a()
    output = {
        "class": "development",
        "purpose": (
            "ring-neuron dopamine stage 3: paired transporter-inhibition sensitivity at the driven "
            "operating point, wild type, ten seeds, 228 traced ER, TuBu stripe on throughout and "
            "CX_DAN driven at 50 Hz in every arm.  The comparator is driven vehicle.  Per cell, "
            "never a population mean.  A null is a result."
        ),
        "declared_substrate_id": plan["declared_substrate_id"],
        "protocol": plan["protocol"],
        "identity": identities[0],
        "plan_sha256": hash_file(plan_path),
        "fixture": plan["fixture"],
        "fixture_sha256": hash_file(ROOT / plan["fixture"]),
        "trace_n": plan["trace_n"],
        "part_a": fresh_part_a,
        "box_incident": {
            "what_happened": (
                "a Tailscale reachability outage of roughly two hours (about 14:00 to 15:30 UTC) "
                "during which ssh to compute host timed out; the compute continued and the run completed "
                "unaffected at 15:11:46 UTC"
            ),
            "reboot": False,
            "uptime_at_recovery": "up 1 day, 21:24 (booted 2026-09-19 18:06 UTC)",
            "memory_event": False,
            "oom_kills": "none: dmesg -T and journalctl -k -b 0 show no oom or killed-process lines",
            "memory_at_recovery": "2 GB of 94 GB used, no swap",
            "action": "no relaunch and no fresh output directory; the raw seeds and the record are the run of record",
        },
        "summary": summary,
        "operating_point": operating_point,
        "contrasts": contrasts,
        "multiplicity": multiplicity,
        "clamp_equivalence": clamp_equivalence,
        "clamp_interpretation": clamp_interpretation,
        "per_cell_changes": per_cell_changes,
        "signed_input": signed_input,
        "replay_audit": replay_audit,
        "paired_runs": [{"seed": run["seed"], "arms": {label: _seed_aggregate(run, label)
                                                       for label in ARM_LABELS}} for run in runs],
        "cells": per_cell,
        "raw_directory": str(raw),
        "raw_sha256": {f"seed-{seed}.json": hash_file(raw / f"seed-{seed}.json") for seed in seeds},
        "generated_utc": datetime.now(timezone.utc).isoformat(),
    }
    record["probe"] = output
    record["census"]["part_a"] = fresh_part_a
    record["replay_audit"] = read(DEFAULT_AUDIT).get("replay") if DEFAULT_AUDIT.is_file() else None
    record["provenance_note"] = {
        "executed_runner_sha256": EXECUTED_RUNNER_SHA256,
        "summarizing_runner_sha256": hash_file(Path(__file__)),
        "reused_stage2c_runner_sha256": hash_file(Path(s2c.__file__)),
        "correction": {
            "issue": (
                "the raw files' identity.runner_sha256 is the hash of "
                "scripts/ring_dopamine_stage2c.py (16ee7ad73e...), not of this runner, because the "
                "probe used the shared stage 2c identity function whose Path(__file__) is stage "
                "2c's own file.  The executed runner was scripts/ring_dopamine_stage3.py at "
                "source_commit 8b73fbe, SHA-256 " + EXECUTED_RUNNER_SHA256 + "."
            ),
            "recorded_runner_sha256": output["identity"]["runner_sha256"],
            "true_executed_runner_sha256": EXECUTED_RUNNER_SHA256,
        },
        "note": (
            "The probe ran under scripts/ring_dopamine_stage3.py at source_commit 8b73fbe.  The "
            "raw seed files are the run evidence and record the same source commit and input "
            "hashes; only the runner hash key is corrected above.  No run_seed dynamics changed "
            "afterwards: the committed runner's changes are summarization and part-A additions, "
            "audit wording, the added high-minus-low summary contrast, and the identity fix for "
            "future stage-3 runs.  The summarizing runner hash therefore differs."
        ),
    }
    record["limitation"] = (
        "This is a model-internal fractional-transporter-inhibition sensitivity study, not a "
        "methylphenidate dose study: no concentration-to-inhibition mapping is used or assumed, "
        "so the axis is fractional transporter inhibition.  All 228 ER cells carry the identical "
        "receptor parameters; experimental work reports dopamine increasing evoked calcium "
        "responses in R2 ring neurons and decreasing them in R5, which supports retaining a "
        "biological-validity warning and not refitting the threshold coefficients from those "
        "measurements.  The probe injects at TuBu, downstream of a visual pathway that does not "
        "conduct: the fly does not see.  With TuBu stimulation present throughout, the outcome is "
        "drug-dependent ring activity under fixed stimulation, not improved visual coding or "
        "rescue.  The clamp arm replays the paired driven-vehicle ER terms, not "
        "the dark constants, so it removes the drug effect on those terms while leaving the "
        "CX_DAN-driven modulation that vehicle already carries; ordinary fast CX_DAN transmission "
        "and every non-ER dopamine effect stay live.  The transporter-disabled pair is a "
        "specificity check on the implementation: with the target absent, a drug effect that "
        "persists would be an unintended effect in our code; it is not independent biological "
        "validation of the encoded target.  Two inhibition levels identify no EC50, no optimal "
        "dose and no monotonicity; fractional inhibition is the primary axis and the constant "
        "Vmax multiplier cannot be relabelled as one methylphenidate concentration across a "
        "changing dopamine trajectory, because no fly DAT calibration maps concentration to "
        "inhibition.  The clamp's conditional effect holds at the high level only and is not "
        "generalised to the low level.  Fractional parameter inhibition is not a fractional "
        "reduction in realised uptake flux: at a common dopamine concentration the flux scales "
        "with Vmax_eff, but rising dopamine partly compensates along the trajectory, and "
        "unchanged realised flux is not a failed inhibition."
    )
    record["reading_note"] = (
        "An interval that includes zero is no detected difference, not equivalence.  Every "
        "interval uses mean +/- 1.96 SE; the paired-t multiplier at n = 10 is 2.262 and is given "
        "alongside.  A fraction is named as the mean of per-seed ratios or the ratio of paired "
        "means.  The resolution figures are confidence-interval half-widths from ten paired "
        "contrasts, not powered minimum detectable effects, and not computed from 228 cells as "
        "independent replicates.  Both arms carry the stripe, so a firing cell is an active cell, "
        "not a demonstrated stripe response."
    )
    record["generated_utc"] = datetime.now(timezone.utc).isoformat()
    dump(destination, record)
    print(json.dumps({
        "vehicle_seed_spikes": seed_spikes["vehicle"],
        "inhibit_low_minus_vehicle": contrasts["inhibit_low_minus_vehicle"]["er_spikes"],
        "inhibit_high_minus_vehicle": contrasts["inhibit_high_minus_vehicle"]["er_spikes"],
        "inhibit_high_clamped_minus_vehicle": contrasts["inhibit_high_clamped_minus_vehicle"]["er_spikes"],
        "vehicle_clamped_minus_vehicle": contrasts["vehicle_clamped_minus_vehicle"]["er_spikes"],
        "inhibit_high_dat_disabled_minus_vehicle_dat_disabled":
            contrasts["inhibit_high_dat_disabled_minus_vehicle_dat_disabled"]["er_spikes"],
        "replay_audit": replay_audit,
    }, indent=2), flush=True)
    print(f"wrote {destination}", flush=True)


def _parse_seeds(text: str) -> tuple[int, ...]:
    if "-" in text:
        lo, hi = text.split("-")
        return tuple(range(int(lo), int(hi) + 1))
    return tuple(int(value) for value in text.split(","))


def main() -> None:
    parser = argparse.ArgumentParser(__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    census_parser = sub.add_parser("census")
    census_parser.add_argument("--out", type=Path, default=DEFAULT_RECORD)
    audit_parser = sub.add_parser("audit")
    audit_parser.add_argument("--out", type=Path, default=DEFAULT_AUDIT)
    plan_parser = sub.add_parser("plan")
    plan_parser.add_argument("--out", type=Path, default=DEFAULT_PLAN)
    run_parser = sub.add_parser("run")
    run_parser.add_argument("--plan", type=Path, default=DEFAULT_PLAN)
    run_parser.add_argument("--out", type=Path, default=DEFAULT_RAW)
    run_parser.add_argument("--workers", type=int, choices=range(1, 17), default=10)
    run_parser.add_argument("--seeds", default="1-10")
    run_parser.add_argument("--identity-only", action="store_true")
    summary_parser = sub.add_parser("summarize")
    summary_parser.add_argument("--raw", type=Path, default=DEFAULT_RAW)
    summary_parser.add_argument("--plan", type=Path, default=DEFAULT_PLAN)
    summary_parser.add_argument("--out", type=Path, default=DEFAULT_RECORD)
    summary_parser.add_argument("--seeds", default="1-10")
    args = parser.parse_args()

    if args.command == "census":
        build_census(args.out)
        return
    if args.command == "audit":
        build_audit(args.out)
        return
    if args.command == "plan":
        build_plan(args.out)
        return
    if args.command == "run":
        seeds = _parse_seeds(args.seeds)
        plan = read(args.plan)
        plan["identity"] = identity(f"{platform.system().lower()}-{platform.machine()}")
        dump(args.plan, plan)
        if args.identity_only:
            print(json.dumps(plan["identity"], indent=2), flush=True)
            return
        run_dynamic(args.plan, args.out, args.workers, seeds)
        return
    summarize(args.raw, args.plan, args.out, _parse_seeds(args.seeds))


if __name__ == "__main__":
    main()
