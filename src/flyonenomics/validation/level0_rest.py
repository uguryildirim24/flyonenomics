"""Level 0 rest-substrate tests: 0.10-engine, 0.11, 0.13, 0.14 (WP15)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
from scipy.sparse import csr_matrix

from flyonenomics.neuromod.state import Neuromod, settle_13_from_windows
from flyonenomics.registry.receptors import ReceptorMap
from flyonenomics.schema.experiment import Experiment, ShiftThreshold
from flyonenomics.types import LayerFlags, Params, load_params, params_path_for_version
from flyonenomics.validation.binding import ValidationEntry, build_identity

REPO = Path(__file__).resolve().parents[3]
TWIN_12 = "tests/fixtures/experiments/bare-twin-1.2.json"
TWIN_13 = "tests/fixtures/experiments/bare-twin-1.3.json"
_SCHEMA_12_SUBSTRATE = ("populations_version", "transmitters_version", "visual_version")
_SETTLE_POPS = (
    ("A", 26568, 1.0, True),
    ("B", 77529, 0.5, True),
    ("C", 5177, 1.5, False),
    ("D", 2, 5.0, False),
)
_FANO = 2.6
_TRIALS = 1000


@dataclass
class _Pop:
    idx: np.ndarray
    name: str = "p"


class _Registry:
    n = 4

    def __init__(self) -> None:
        self._w = csr_matrix(np.array([[1, 0], [0, 1], [0, 0], [0, 1]], dtype=np.float32))
        self._m = csr_matrix(np.array([[1, 0, 0, 0], [0, 1, 0, 0]], dtype=np.float32))

    def exposure(self) -> csr_matrix:
        return self._w

    def innervation(self) -> csr_matrix:
        return self._m

    def exposed_mask(self) -> np.ndarray:
        return np.asarray(self._w.getnnz(axis=1) > 0)

    def receptors(self) -> ReceptorMap:
        return ReceptorMap(
            np.array([1, 0.5, 1, 1], dtype=np.float32),
            np.array([0.5, 1, 1, 0], dtype=np.float32),
            np.zeros(4, dtype=np.float32),
            "fixture",
        )

    def compartments(self) -> list[Any]:
        return [SimpleNamespace(name="a"), SimpleNamespace(name="b")]

    def population(self, name: str) -> _Pop:
        return _Pop(np.array([0, 1], dtype=np.int32), name)


class _Engine:
    def __init__(self) -> None:
        self.v_th: np.ndarray | None = None
        self.gain: np.ndarray | None = None
        self.ticks = 0
        self.dt_ms = 0.1

    def set_threshold(self, values: np.ndarray) -> None:
        self.v_th = np.asarray(values, dtype=np.float64).copy()

    def set_gain(self, values: np.ndarray) -> None:
        self.gain = np.asarray(values, dtype=np.float64).copy()

    def disconnect(self, idx: np.ndarray) -> None:
        self.disconnected = np.asarray(idx).copy()

    def run_chunk(self, ms: float) -> Any:
        self.ticks += int(round(ms / self.dt_ms))
        return SimpleNamespace(counts=np.array([1, 1, 0, 0], dtype=np.int32))

    def tick(self) -> int:
        return self.ticks


def comparable_experiment(experiment: Experiment) -> dict[str, Any]:
    """Dump two schema versions onto a common 1.2 field set. Units none."""
    data = experiment.model_dump(mode="json")
    data.pop("schema_version", None)
    substrate = data.get("substrate") or {}
    for key in _SCHEMA_12_SUBSTRATE:
        substrate.pop(key, None)
    data["substrate"] = substrate
    data.pop("apply_scales_without_background", None)
    return data


def twin_resolution() -> dict[str, Any]:
    """Load the 0.14 twins and compare resolved dumps. Units none."""
    from flyonenomics.io import read_json

    left = Experiment.model_validate(read_json(REPO / TWIN_12))
    right = Experiment.model_validate(read_json(REPO / TWIN_13))
    same = comparable_experiment(left) == comparable_experiment(right)
    return {
        "passed": bool(same and left.schema_version == "1.2" and right.schema_version == "1.3"),
        "schema_12": left.schema_version,
        "schema_13": right.schema_version,
        "dumps_equal_apart_from_schema": same,
        "background": left.layers.background,
        "params_version": left.substrate.params_version,
    }


# Section 8.1 1.3-only features, each set on the bare 1.3 twin. The probe is
# replaced where the feature belongs to another assay.
_BURIDAN = {"type": "probe", "assay": "buridan", "duration_s": 0.01, "label": "upstream", "params": {}}
_OPEN_LOOP = {"type": "probe", "assay": "open_loop_steering", "duration_s": 0.01, "label": "upstream", "params": {}}
_SPONTANEOUS = {"type": "probe", "assay": "spontaneous", "duration_s": 0.01, "label": "upstream", "params": {}}
_BARE_FEATURES: tuple[tuple[str, dict[str, Any] | None, dict[str, Any]], ...] = (
    ("photoreceptor injection", _BURIDAN, {"inject_at": "photoreceptors"}),
    ("blocks", _OPEN_LOOP, {"blocks": [{"stimulus": "dark", "transition_s": 0.005, "dwell_s": 0.005}]}),
    ("random heading", _BURIDAN, {"initial_heading": "random"}),
    ("ambient stimulus", _SPONTANEOUS, {"stimulus": "ambient"}),
    ("v0.2 params pin", None, {"substrate": {"params_version": "v0.2"}}),
    ("v0.2 drive pin", None, {"substrate": {"drive_version": "v0.2"}}),
    ("v0.2 populations pin", None, {"substrate": {"populations_version": "v0.2"}}),
    ("named genotype new in 1.3", None, {"genotype": {"named": "pam_silenced", "manipulations": []}}),
)
_DECISION_22 = ("v0.2 params pin", "v0.2 drive pin")


def bare_rejections() -> dict[str, Any]:
    """Each 1.3-only feature and v0.2 pin on a background-off 1.3 file, and on a 1.2 file, is rejected. Units none."""
    import copy

    from pydantic import ValidationError

    from flyonenomics.io import read_json

    base = {12: read_json(REPO / TWIN_12), 13: read_json(REPO / TWIN_13)}
    rejected: dict[str, dict[str, bool]] = {}
    routed: dict[str, bool] = {}
    for label, probe, change in _BARE_FEATURES:
        rejected[label] = {}
        for version, raw in base.items():
            data = copy.deepcopy(raw)
            arm = data["arms"][0]
            if probe is not None:
                arm["protocol"] = [{**copy.deepcopy(probe), "params": {**probe["params"], **change}}]
                data["record"] = {"spikes": ["MN9"], "rates": ["MN9"], "popcount": True, "live": False}
            elif "substrate" in change:
                data["substrate"] = {**data["substrate"], **change["substrate"]}
            else:
                arm.update(copy.deepcopy(change))
            try:
                Experiment.model_validate(data)
                rejected[label][f"schema_{version}"] = False
            except ValidationError as exc:
                rejected[label][f"schema_{version}"] = True
                if version == 12 and label in _DECISION_22:
                    routed[label] = "schema 1.3 is the only route to the rest substrate" in str(exc)
    # Section 8.1 lists the pin rejections for 1.3 bare files. Decision 22: a 1.2
    # file rejects v0.2 params and drive pins with an error that names schema 1.3.
    passed = all(row["schema_13"] and row["schema_12"] for row in rejected.values()) and all(
        routed.get(label, False) for label in _DECISION_22)
    return {"passed": passed, "rejected": rejected, "schema_12_routes_to_13": routed}


def run_0_14_engine(root: Path) -> dict[str, Any]:
    """Run both twins through the orchestrator and compare every table and metric bitwise.

    Units: ticks, Hz. Shapes: per recorded table. Runs go under root, not runs/.
    """
    from flyonenomics.io import read_json
    from flyonenomics.orchestrator import run
    from flyonenomics.orchestrator.verification import compare_runs
    from flyonenomics.store.results import ResultsStore

    directories = {}
    for label, fixture in (("1.2", TWIN_12), ("1.3", TWIN_13)):
        store = ResultsStore(root / label.replace(".", "_"))
        run_id = run(Experiment.model_validate(read_json(REPO / fixture)), store, 1)
        directories[label] = store.run_path(run_id)
    tables = compare_runs(directories["1.2"], directories["1.3"])
    settle = {path.relative_to(directories["1.2"]) for path in directories["1.2"].rglob("probe-*-settle.json")}
    settle_equal = settle == {path.relative_to(directories["1.3"]) for path in directories["1.3"].rglob("probe-*-settle.json")} and all(
        read_json(directories["1.2"] / name) == read_json(directories["1.3"] / name) for name in settle)
    manifests = {label: read_json(path / "manifest.json") for label, path in directories.items()}
    return {
        "passed": bool(tables > 0 and settle_equal
                       and manifests["1.2"]["substrate_id"] == manifests["1.3"]["substrate_id"] == "bare"),
        "tables_compared": tables,
        "settle_files_equal": bool(settle_equal),
        "substrate_id": manifests["1.3"]["substrate_id"],
    }


def _params_v02() -> Params:
    return load_params(params_path_for_version("v0.2"))


def _draw_count(rng: np.random.Generator, mean: float, fano: float) -> int:
    """Draw a nonnegative spike count with block-scale Fano. Units: spikes."""
    mean = max(float(mean), 1e-12)
    var = fano * mean
    if var <= mean + 1e-9:
        return int(rng.poisson(mean))
    p = min(max(mean / var, 1e-9), 1.0 - 1e-9)
    n = mean * p / (1.0 - p)
    return int(rng.negative_binomial(max(n, 1e-6), p))


def _windows_for_trial(rng: np.random.Generator, params: Params, drift_per_s: float,
                       n_windows: int | None = None) -> list[dict[str, np.ndarray]]:
    """Build one trial's block-count windows. Units: spikes, s, Hz."""
    window_s = float(params.get("settle.window_s_13"))
    n_blocks = int(params.get("settle.blocks"))
    block_s = window_s / n_blocks
    if n_windows is None:
        n_windows = int(round(float(params.get("settle.max_s")) / window_s))
    windows: list[dict[str, np.ndarray]] = []
    for step in range(n_windows):
        row: dict[str, np.ndarray] = {}
        for name, size, rate0, _resolved in _SETTLE_POPS:
            counts = np.empty(n_blocks, dtype=np.float64)
            for block in range(n_blocks):
                t = step * window_s + (block + 0.5) * block_s
                # Section 2.4 (b) and (c): only the 26,568-neuron population drifts.
                drift = drift_per_s if name == "A" else 0.0
                rate = rate0 * ((1.0 + drift) ** t)
                counts[block] = _draw_count(rng, rate * size * block_s, _FANO)
            row[name] = counts
        windows.append(row)
    return windows


def run_0_13_cases() -> dict[str, Any]:
    """Section 2.4 synthetic cases (a) to (c) plus the schema 1.2 DA rule."""
    params = _params_v02()
    names = [row[0] for row in _SETTLE_POPS]
    sizes = [row[1] for row in _SETTLE_POPS]
    expect_unresolved = [row[0] for row in _SETTLE_POPS if not row[3]]
    rng = np.random.default_rng(20260914)
    stationary = []
    drift20 = []
    drift5 = []
    labels_ok = True
    for _ in range(_TRIALS):
        a = settle_13_from_windows(names, sizes, _windows_for_trial(rng, params, 0.0), params)
        b = settle_13_from_windows(names, sizes, _windows_for_trial(rng, params, 0.20), params)
        c = settle_13_from_windows(names, sizes, _windows_for_trial(rng, params, 0.05), params)
        stationary.append(bool(a["converged"]))
        drift20.append(bool(b["converged"]))
        drift5.append(bool(c["converged"]))
        if list(a["unresolved"]) != expect_unresolved:
            labels_ok = False
    phase1 = Neuromod(_Registry(), load_params(), LayerFlags(), schema_version="1.2")
    engine_12 = _Engine()
    phase1.reset_fast()
    record_12 = phase1.settle(engine_12, lambda: None, [_Pop(np.array([0, 1], dtype=np.int32), "tiny")])
    rest = Neuromod(_Registry(), params, LayerFlags(), schema_version="1.3")
    engine_13 = _Engine()
    rest.reset_fast()
    record_13 = rest.settle(engine_13, lambda: None, [_Pop(np.array([0, 1], dtype=np.int32), "tiny")])
    frac_a = float(np.mean(stationary))
    frac_b = float(np.mean(drift20))
    frac_c = float(np.mean(drift5))
    # The same engine, counts and pools: the Phase 1 rule is held back by
    # dopamine drift, the section 2.4 rule is not.
    ignores_da = bool(record_13.converged and not record_12.converged)
    dispatch = rule_dispatch()
    passed = bool(
        frac_a >= 0.99 and frac_b <= 0.01 and labels_ok and ignores_da and dispatch["passed"]
        and record_12.settle_s == load_params().get("settle.max_s")
    )
    return {
        "passed": passed,
        "stationary_converge": frac_a,
        "drift20_converge": frac_b,
        "drift5_converge": frac_c,
        "unresolved_labels_ok": labels_ok,
        "schema_12_uses_phase1_da": (not record_12.converged),
        "schema_13_ignores_da": ignores_da,
        "schema_13_tiny_unresolved": list(record_13.unresolved or []),
        "rule_dispatch": dispatch,
        "trials": _TRIALS,
    }


def rule_dispatch() -> dict[str, Any]:
    """The worker's settle rule: 1.3 only for schema 1.3 with background on. Units none."""
    import copy

    from flyonenomics.io import read_json
    from flyonenomics.orchestrator.workers import settle_rule

    twin_12 = Experiment.model_validate(read_json(REPO / TWIN_12))
    twin_13 = Experiment.model_validate(read_json(REPO / TWIN_13))
    raw = copy.deepcopy(read_json(REPO / TWIN_13))
    raw["layers"] = {"background": True}
    raw["substrate"] = {"connectome_version": "783"}
    rest = Experiment.model_validate(raw)
    rules = {"1.2": settle_rule(twin_12), "1.3-bare": settle_rule(twin_13), "1.3-background": settle_rule(rest)}
    return {"passed": rules == {"1.2": "1.2", "1.3-bare": "1.2", "1.3-background": "1.3"}, "rules": rules}


def run_0_10_engine(*, workers: int = 1) -> dict[str, Any]:
    """Engine leg: sampled rows equal _base_w_mv × scale after store/restore."""
    del workers
    from flyonenomics.connectome_arrays import connectome_source_paths, load_connectome_arrays
    from flyonenomics.drive.rest import apply_rest_substrate
    from flyonenomics.engine.brian_engine import BrianEngine
    from flyonenomics.engine.base import InputTopology
    from flyonenomics.orchestrator.workers import connectome_files
    from flyonenomics.substrate.scales import CLASS_NAMES, EXCITATORY_CLASSES, INHIBITORY_CLASSES
    from flyonenomics.substrate.transmitters import load_connection_columns, load_transmitters
    from brian2 import mV

    params = load_params()
    transmitters = load_transmitters()
    classes = transmitters["class_array"]
    completeness, connectivity = connectome_source_paths("783")
    _roots, i_pre, _post, _weights = load_connectome_arrays(completeness, connectivity)
    pre = np.asarray(i_pre, dtype=np.int32)
    s_pq = np.sign(np.asarray(load_connection_columns(("Excitatory",)).column("Excitatory").to_numpy(), dtype=np.float64))
    drive = {"g_glu": 4.0, "g_gaba": 2.0, "g_his": 1.0, "optic_exemption": False, "sigma_th": 0.0, "seed": 20260914, "mechanisms": None}
    engine = BrianEngine()
    engine.build(connectome_files("783"), params, InputTopology())
    base, scale = apply_rest_substrate(engine, params, drive, classes=classes, s_pq=s_pq, pre=pre, n=engine.n)
    del base
    raw_scaled = np.array(engine._syn.variables["w"].get_value(), dtype=np.float64, copy=True)
    engine.store("initial")
    engine.restore("initial")
    raw_held = np.array(engine._syn.variables["w"].get_value(), dtype=np.float64, copy=True)
    # Brian holds w in volts, written by set_weight_scale as
    # (_base_w_mv × scale) × mV. Reading back `w / mV` divides again and can
    # move a value by one ULP, so the comparison stays in the stored unit:
    # the restored array must equal the same product bitwise.
    expected_mv = np.asarray(engine._base_w_mv, dtype=np.float64) * np.asarray(scale, dtype=np.float32).astype(np.float64)
    expected = np.asarray(expected_mv * mV, dtype=np.float64)
    labels = np.asarray(classes[pre], dtype=str)
    inhibitory = np.isin(labels, tuple(INHIBITORY_CLASSES))
    excitatory = np.isin(labels, tuple(EXCITATORY_CLASSES))
    s_cur = np.where(inhibitory, -1.0, np.where(excitatory, 1.0, s_pq))
    flipped = s_cur != s_pq
    rng = np.random.default_rng(20260914)
    matched = True
    sampled: dict[str, int] = {}

    def rows_ok(idx: np.ndarray) -> bool:
        if idx.size == 0:
            return True
        return bool(np.array_equal(raw_held[idx], raw_scaled[idx]) and np.array_equal(raw_held[idx], expected[idx]))

    for label in CLASS_NAMES:
        rows = np.flatnonzero(labels == label)
        take = rows if rows.size <= 1000 else rng.choice(rows, 1000, replace=False)
        sampled[str(label)] = int(take.size)
        if not rows_ok(take):
            matched = False
            break
        flip_rows = np.flatnonzero((labels == label) & flipped)
        if flip_rows.size:
            take_flip = flip_rows if flip_rows.size <= 1000 else rng.choice(flip_rows, 1000, replace=False)
            sampled[f"{label}:flipped"] = int(take_flip.size)
            if not rows_ok(take_flip):
                matched = False
                break
    # WP11's memory-mapped base weights are opened read-only, so scales cannot be written through them.
    base_read_only = not bool(np.asarray(engine._base_w_mv).flags.writeable)
    engine.close() if hasattr(engine, "close") else None
    return {"passed": bool(matched and base_read_only), "sampled": sampled, "n_syn": int(engine.n_syn),
            "comparison": "bitwise, volts", "base_weights_read_only": base_read_only}


def test_0_10_engine() -> ValidationEntry:
    """Transmitter scales survive store/restore on the 783 engine. Units: mV."""
    measured = run_0_10_engine()
    identity = build_identity(
        REPO, connectome_version="783", layers=LayerFlags(), assay="spontaneous",
        fixture=TWIN_12,
    )
    return ValidationEntry(
        test_id="0.10-engine",
        category="verification",
        outcome="passed" if measured["passed"] else "failed",
        compatibility="canonical",
        identity=identity,
        measured=measured,
        fixture_path=TWIN_12,
        data_dependencies=["transmitters-v0.2.yaml", "params-v0.1.yaml"],
    )


def run_0_11() -> dict[str, Any]:
    """Bitwise engine thresholds against composed base + dopamine + shift."""
    from flyonenomics.drive.rest import apply_rest_substrate, draw_threshold_z, z_sha256

    params = load_params()
    sigma = 1.0
    seed = 20260914
    n = _Registry.n
    z = draw_threshold_z(seed, n)
    drive = {"g_glu": 1.0, "g_gaba": 1.0, "g_his": 1.0, "optic_exemption": False,
             "sigma_th": sigma, "seed": seed, "z_sha256": z_sha256(z), "mechanisms": None}

    class _ScaleSink:
        def set_weight_scale(self, scale: np.ndarray) -> None:
            self.scale = scale

    # The worker's path: apply_rest_substrate draws the base, Neuromod composes from it.
    base, _scale = apply_rest_substrate(
        _ScaleSink(), params, drive, classes=np.array(["ACh"]), s_pq=np.array([1.0]),
        pre=np.array([0], dtype=np.int32), n=n,
    )
    table = {"alpha_c": [0.01, 0.02], "R_c": [1.0, 2.0]}
    mod = Neuromod(_Registry(), params, LayerFlags(dopamine_A=True), table, base_v_th=base)
    engine = _Engine()
    mod.apply_genotype([ShiftThreshold(type="shift_threshold", population="x", delta_mv=0.3)], engine)
    v_th = float(params.get("lif.v_th"))
    matched = True
    shifts: list[np.ndarray] = []
    for _ in range(100):
        counts = np.array([2, 1, 0, 0], dtype=np.int32)
        mod.on_chunk(counts, 0.01)
        composed = mod.compose()
        engine.set_threshold(composed.v_th)
        d_v, _, _, _ = mod.receptor_terms()
        shifts.append(d_v.copy())
        # Written out term by term, independent of compose().
        expected = np.clip(v_th + sigma * z + mod.shift + d_v, *params.get("rec.vth_clip"))
        expected[mod.silenced] = params.get("engine.silence_vth")
        if engine.v_th is None or not np.array_equal(engine.v_th, expected):
            matched = False
            break
    modulated = bool(len(shifts) == 100 and np.any(shifts[0] != 0) and np.any(shifts[-1] != shifts[0]))
    shifted = bool(np.any(mod.shift != 0))
    truncated = bool(np.all(np.abs(z) <= 2.0))
    return {"passed": bool(matched and modulated and shifted and truncated), "chunks": 100,
            "sigma_th": sigma, "dopamine_shift_active": modulated, "manipulation_shift": shifted,
            "z_truncated": truncated, "z_sha256": drive["z_sha256"]}


def test_0_11() -> ValidationEntry:
    """Persistent threshold composition. Units: mV."""
    measured = run_0_11()
    identity = build_identity(
        REPO, connectome_version="783", layers=LayerFlags(), assay="spontaneous",
        fixture=TWIN_12,
    )
    return ValidationEntry(
        test_id="0.11",
        category="verification",
        outcome="passed" if measured["passed"] else "failed",
        compatibility="canonical",
        identity=identity,
        measured=measured,
        fixture_path=TWIN_12,
        data_dependencies=["params-v0.1.yaml"],
    )


def test_0_13() -> ValidationEntry:
    """Section 2.4 settle rule on synthetic counts. Units: Hz, s."""
    measured = run_0_13_cases()
    identity = build_identity(
        REPO, connectome_version="783", layers=LayerFlags(), assay="spontaneous",
        fixture=TWIN_12,
    )
    return ValidationEntry(
        test_id="0.13",
        category="verification",
        outcome="passed" if measured["passed"] else "failed",
        compatibility="canonical",
        identity=identity,
        measured=measured,
        fixture_path=TWIN_12,
        data_dependencies=["params-v0.2.yaml"],
    )


def test_0_14() -> ValidationEntry:
    """Bare compatibility of schema 1.2 and 1.3 twins. Units none."""
    import tempfile

    resolution = twin_resolution()
    rejections = bare_rejections()
    with tempfile.TemporaryDirectory(prefix="flyonenomics-0.14-") as root:
        engine = run_0_14_engine(Path(root))
    measured = {"passed": bool(resolution["passed"] and rejections["passed"] and engine["passed"]),
                "resolution": resolution, "rejections": rejections, "engine": engine}
    identity = build_identity(
        REPO, connectome_version="783", layers=LayerFlags(), assay="sugar_reflex",
        fixture=TWIN_12,
    )
    return ValidationEntry(
        test_id="0.14",
        category="verification",
        outcome="passed" if measured["passed"] else "failed",
        compatibility="canonical",
        identity=identity,
        measured=measured,
        fixture_path=TWIN_12,
        data_dependencies=["params-v0.1.yaml", "populations-v0.1.yaml", "dopamine-v0.1.yaml",
                           "receptors-v0.1.yaml", "compartments-v0.1.yaml"],
    )


SUITE = {"0.10-engine": test_0_10_engine, "0.11": test_0_11, "0.13": test_0_13, "0.14": test_0_14}
