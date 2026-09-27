"""Tier-3 engine tests 0.15 to 0.18 (SPEC-P2 5.3, WP24).

Commit 1 records the 0.15 (b) off-path hashes before any engine edit.
Later commits check those hashes unchanged. Engine imports stay inside
measure helpers so pytest collection does not build a network.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

_UNSET = object()

import numpy as np
import yaml

from flyonenomics.io import read_json, read_yaml
from flyonenomics.types import LayerFlags, load_params, params_path_for_version
from flyonenomics.validation.binding import (
    ValidationEntry,
    build_identity,
    code_scope_hash,
    platform_id,
    repo_commit,
)

REPO = Path(__file__).resolve().parents[3]
FIX = REPO / "tests" / "fixtures" / "engine"
OFF_REFERENCE = REPO / "tests" / "fixtures" / "wp24-off-reference.json"
FIXTURE_0_16 = "tests/fixtures/engine/fixture-0-16.json"
FIXTURE_0_17 = "tests/fixtures/engine/fixture-0-17.json"
FIXTURE_0_18 = "tests/fixtures/engine/fixture-0-18.json"
DRIVE_DEV = REPO / "data" / "drive-dev-p2.yaml"
def spike_table_hash(idx: np.ndarray, tick: np.ndarray) -> str:
    """SHA-256 of idx little-endian int32 then tick little-endian int64.

    Units: none. Shapes: idx (n_spikes,) int32, tick (n_spikes,) int64.
    """
    return hashlib.sha256(
        np.ascontiguousarray(idx, dtype=np.int32).tobytes()
        + np.ascontiguousarray(tick, dtype=np.int64).tobytes()
    ).hexdigest()


def trace_hash(tick: np.ndarray, v_mv: np.ndarray) -> str:
    """SHA-256 of tick little-endian int64 then v_mv little-endian float64 C-order.

    Units: mV. Shapes: tick (n_time,) int64, v_mv (m, n_time) float64.
    """
    return hashlib.sha256(
        np.ascontiguousarray(tick, dtype=np.int64).tobytes()
        + np.ascontiguousarray(v_mv, dtype=np.float64).tobytes()
    ).hexdigest()


def string_sha256(text: str) -> str:
    """SHA-256 of one UTF-8 string. Units: none. Shapes: one hex."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def run_isolated(measure: str, timeout_s: int = 2400) -> dict[str, Any]:
    """Run one measure helper in a fresh interpreter. Units: seconds. Shapes: mapping."""
    code = (
        "import json; "
        f"from flyonenomics.validation.level0_mech import {measure} as m; "
        'print("ENTRY-BEGIN"); print(json.dumps(m()))'
    )
    proc = subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout_s,
        env=os.environ.copy(),
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"isolated {measure} failed: {proc.stderr[-4000:]}\n{proc.stdout[-2000:]}"
        )
    marker = "ENTRY-BEGIN\n"
    if marker not in proc.stdout:
        raise RuntimeError(
            f"isolated {measure} printed no entry: {proc.stdout[-1000:]} {proc.stderr[-2000:]}"
        )
    return json.loads(proc.stdout.rsplit(marker, 1)[1])


def _capture_brian_constructors() -> dict[str, Any]:
    """Wrap NeuronGroup and Synapses to record strings as passed to Brian2."""
    import brian2 as b

    captured: dict[str, Any] = {"neuron": [], "synapse": []}
    orig_ng = b.NeuronGroup
    orig_syn = b.Synapses

    def wrapped_ng(*args: Any, **kwargs: Any) -> Any:
        model = kwargs.get("model", args[1] if len(args) > 1 else None)
        captured["neuron"].append(
            {
                "model": model if isinstance(model, str) else str(model),
                "threshold": kwargs.get("threshold"),
                "reset": kwargs.get("reset"),
                "method": kwargs.get("method"),
                "name": kwargs.get("name"),
                "namespace_keys": sorted(str(k) for k in (kwargs.get("namespace") or {}).keys()),
            }
        )
        return orig_ng(*args, **kwargs)

    def wrapped_syn(*args: Any, **kwargs: Any) -> Any:
        captured["synapse"].append(
            {
                "on_pre": kwargs.get("on_pre"),
                "name": kwargs.get("name"),
            }
        )
        return orig_syn(*args, **kwargs)

    b.NeuronGroup = wrapped_ng  # type: ignore[assignment]
    b.Synapses = wrapped_syn  # type: ignore[assignment]
    return captured


def _tiny_016_engine(*, capture: bool = False, mechanisms: Any = _UNSET) -> Any:
    """Build the 0.16 tiny engine. Units: none. Shapes: n == 4.

    The recording path omits mechanisms so build receives its default.
    """
    import numpy as np

    from flyonenomics.engine import BrianEngine, InputTopology
    from flyonenomics.types import ConnectomeFiles

    fix = read_json(REPO / FIXTURE_0_16)
    captured = _capture_brian_constructors() if capture else None
    engine = BrianEngine()
    engine.seed(int(fix["seed"]))
    build_kwargs: dict[str, Any] = {}
    if mechanisms is not _UNSET:
        build_kwargs["mechanisms"] = mechanisms
    engine.build(
        ConnectomeFiles(
            completeness=FIX / "tiny_completeness.csv",
            connectivity=FIX / "tiny_connectivity.parquet",
            version="630",
        ),
        load_params(),
        InputTopology(
            spikelist_idx=np.array(fix["spikelist_idx"], dtype=np.int32),
            trace_idx=np.array(fix["trace_idx"], dtype=np.int32),
        ),
        **build_kwargs,
    )
    engine._wp24_capture = captured
    return engine


def _run_016_lif(engine: Any) -> tuple[Any, Any]:
    """Drive the 0.16 spike list on lif and return spikes and traces."""
    import numpy as np

    from flyonenomics.validation.level0 import prepare, run_chunks

    fix = read_json(REPO / FIXTURE_0_16)
    params = load_params()
    prepare(engine)
    silence = float(params.get("engine.silence_vth"))
    v_th = float(params.get("lif.v_th"))
    thresholds = np.full(engine.n, v_th, dtype=np.float64)
    thresholds[1:] = silence
    engine.set_threshold(thresholds)
    ticks = np.array(fix["spike_tick"], dtype=np.int64)
    engine.set_spike_list(
        np.full(ticks.shape, int(fix["driver"]), dtype=np.int32),
        ticks,
    )
    engine.seed(int(fix["seed"]))
    duration_ms = float(fix["duration_ticks"]) * float(fix["dt_ms"])
    run_chunks(engine, duration_ms)
    return engine.spikes(0), engine.traces(0)


def measure_0_15_b_i() -> dict[str, Any]:
    """0.15 (b)(i): 0.16 fixture on lif, plus constructor strings and names."""
    engine = _tiny_016_engine(capture=True)
    spikes, traces = _run_016_lif(engine)
    captured = engine._wp24_capture
    neuron = captured["neuron"][0]
    recurrent = next(item for item in captured["synapse"] if item["name"] and "spikelist" not in item["name"])
    neu = engine._neu
    net = engine._net
    state_names = sorted(str(name) for name in neu.variables.keys() if not str(name).startswith("_"))
    object_names = sorted(str(obj.name) for obj in net.objects)
    model = neuron["model"]
    threshold = neuron["threshold"]
    reset = neuron["reset"]
    on_pre = recurrent["on_pre"]
    return {
        "lif_model": model,
        "lif_threshold": threshold,
        "lif_reset": reset,
        "lif_on_pre": on_pre,
        "lif_model_sha256": string_sha256(model),
        "lif_threshold_sha256": string_sha256(threshold),
        "lif_reset_sha256": string_sha256(reset),
        "lif_on_pre_sha256": string_sha256(on_pre),
        "method": neuron["method"],
        "object_names": object_names,
        "namespace_keys": neuron["namespace_keys"],
        "state_variable_names": state_names,
        "spike_table_sha256": spike_table_hash(spikes.idx, spikes.tick),
        "trace_sha256": trace_hash(traces.tick, traces.v_mv),
        "recipe": "0.16 fixture on lif; spike-table hash of spikes(0) and trace hash of traces(0)",
    }


def _snapshot_0_15_a(engine: Any, *, include_capture: bool = False) -> dict[str, Any]:
    """Read 0.15 (a) fields from one built tiny engine."""
    traces = engine.mechanism_traces(0)
    row: dict[str, Any] = {
        "engine_model": engine.engine_model(),
        "method": engine.method(),
        "model_strings": list(engine.model_strings()),
        "mechanism_columns": list(traces.columns()),
        "state_variable_names": sorted(
            str(name) for name in engine._neu.variables.keys() if not str(name).startswith("_")
        ),
        "object_names": sorted(str(obj.name) for obj in engine._net.objects),
    }
    if include_capture:
        captured = engine._wp24_capture
        neuron = captured["neuron"][0]
        recurrent = next(
            item for item in captured["synapse"] if item["name"] and "spikelist" not in item["name"]
        )
        row["passed_model"] = neuron["model"]
        row["passed_threshold"] = neuron["threshold"]
        row["passed_reset"] = neuron["reset"]
        row["passed_on_pre"] = recurrent["on_pre"]
        row["passed_method"] = neuron["method"]
        row["namespace_keys"] = neuron["namespace_keys"]
    return row


def measure_0_15_a() -> dict[str, Any]:
    """0.15 (a): lif strings, names, and empty mechanism traces on three build paths."""
    from flyonenomics.engine.models import Mechanisms

    fixture = read_json(OFF_REFERENCE)
    omitted = _snapshot_0_15_a(_tiny_016_engine(capture=True), include_capture=True)
    none = _snapshot_0_15_a(_tiny_016_engine(mechanisms=None))
    all_null = _snapshot_0_15_a(_tiny_016_engine(mechanisms=Mechanisms()))
    return {
        "omitted": omitted,
        "none": none,
        "all_null": all_null,
        "expected": {
            "engine_model": "lif",
            "method": "linear",
            "model_strings": [
                fixture["lif_model"],
                fixture["lif_threshold"],
                fixture["lif_reset"],
                fixture["lif_on_pre"],
            ],
            "object_names": fixture["object_names"],
            "namespace_keys": fixture["namespace_keys"],
            "state_variable_names": fixture["state_variable_names"],
        },
    }


def check_0_15_a() -> dict[str, Any]:
    """Compare 0.15 (a) on three lif build paths against the off-path fixture."""
    got = run_isolated("measure_0_15_a", timeout_s=300)
    expected = got["expected"]
    mismatches: list[str] = []
    for path in ("omitted", "none", "all_null"):
        row = got[path]
        if row["engine_model"] != expected["engine_model"]:
            mismatches.append(f"{path}.engine_model")
        if row["method"] != expected["method"]:
            mismatches.append(f"{path}.method")
        if row["model_strings"] != expected["model_strings"]:
            mismatches.append(f"{path}.model_strings")
        if row["mechanism_columns"]:
            mismatches.append(f"{path}.mechanism_columns")
        if row["state_variable_names"] != expected["state_variable_names"]:
            mismatches.append(f"{path}.state_variable_names")
    omitted = got["omitted"]
    if omitted["object_names"] != expected["object_names"]:
        mismatches.append("omitted.object_names")
    if omitted["namespace_keys"] != expected["namespace_keys"]:
        mismatches.append("omitted.namespace_keys")
    strings = expected["model_strings"]
    if omitted["passed_model"] != strings[0]:
        mismatches.append("omitted.passed_model")
    if omitted["passed_threshold"] != strings[1]:
        mismatches.append("omitted.passed_threshold")
    if omitted["passed_reset"] != strings[2]:
        mismatches.append("omitted.passed_reset")
    if omitted["passed_on_pre"] != strings[3]:
        mismatches.append("omitted.passed_on_pre")
    if omitted["passed_method"] != "linear":
        mismatches.append("omitted.passed_method")
    return {"passed": not mismatches, "mismatches": mismatches, "measured": got}


def _apply_drive_dev(engine: Any, drive: dict[str, Any], params: Any) -> None:
    """Apply load_drive_rest output: scales, thresholds, background weights."""
    from flyonenomics.drive.rest import apply_rest_substrate, rest_background_weights
    from flyonenomics.registry import build_registry

    params.data["bg"]["n_bg"]["value"] = int(drive["n_bg"])
    base, _scale = apply_rest_substrate(engine, params, drive)
    engine.set_threshold(base)
    registry = build_registry("783")
    engine.set_background(rest_background_weights(registry, drive, params))


def _probe_drive_dev(path: Path) -> str:
    """2 s background-on probe, seed 1, no stimulus. Units: none. Shapes: one hex."""
    import numpy as np

    from flyonenomics.drive.rest import load_drive_rest
    from flyonenomics.engine import BrianEngine, InputTopology
    from flyonenomics.validation.level0 import connectome, run_chunks

    params = load_params(params_path_for_version("v0.2"))
    drive = load_drive_rest(path)
    params.data["bg"]["n_bg"]["value"] = int(drive["n_bg"])
    engine = BrianEngine()
    engine.seed(1)
    engine.build(connectome("783"), params, InputTopology(background=True))
    _apply_drive_dev(engine, drive, params)
    engine.seed(1)
    run_chunks(engine, 2000.0)
    spikes = engine.spikes(0)
    return spike_table_hash(spikes.idx, spikes.tick)


def measure_0_15_b_ii() -> dict[str, Any]:
    """0.15 (b)(ii): drive-dev-p2.yaml, 2 s, seed 1, background on, no stimulus."""
    digest = _probe_drive_dev(DRIVE_DEV)
    return {
        "spike_table_sha256": digest,
        "recipe": (
            "2 s probe without stimulus, seed 1, background on, data/drive-dev-p2.yaml "
            "through load_drive_rest and apply_rest_substrate, bg.n_bg from the file"
        ),
    }


def measure_0_15_b_iii() -> dict[str, Any]:
    """0.15 (b)(iii): constructed copy with three null mechanism blocks."""
    raw = read_yaml(DRIVE_DEV)
    if not isinstance(raw, dict):
        raise ValueError("drive-dev-p2.yaml must be a mapping")
    raw = dict(raw)
    raw["mechanisms"] = {
        "adaptation": None,
        "depression": None,
        "conductance_inhibition": None,
    }
    handle = tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False)
    try:
        yaml.safe_dump(raw, handle, sort_keys=False)
        handle.close()
        digest = _probe_drive_dev(Path(handle.name))
    finally:
        Path(handle.name).unlink(missing_ok=True)
    return {
        "spike_table_sha256": digest,
        "recipe": (
            "same probe as (ii) on a constructed copy with mechanisms blocks all null"
        ),
    }


def measure_0_15_b_iv() -> dict[str, Any]:
    """0.15 (b)(iv): R-reflex (c) extended candidate arm at (3, 6), seed 1."""
    from flyonenomics.drive.rest_map import Setting, _build_engine, _probe

    built = _build_engine(Setting(g_gaba=3, g_glu=6), mode="extended", feedforward=True)
    engine = built["engine"]
    _probe(built, 1.15, 1, seconds=1, active=False)
    silent = engine.spikes(0)
    silent_hash = spike_table_hash(silent.idx, silent.tick)
    _probe(built, 1.15, 1, seconds=1, active=True)
    sugar = engine.spikes(0)
    sugar_hash = spike_table_hash(sugar.idx, sugar.tick)
    return {
        "spike_table_sha256_silent": silent_hash,
        "spike_table_sha256_sugar": sugar_hash,
        "recipe": (
            "_build_engine Setting(g_gaba=3, g_glu=6) mode extended feedforward true; "
            "_probe weight 1.15 seed 1 seconds 1 silent then active; spikes(0) after each"
        ),
    }


def assemble_off_reference(parts: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Build the 0.15 (b) fixture mapping from isolated measure results."""
    one = parts["i"]
    return {
        "commit": repo_commit(REPO),
        "code_scope": code_scope_hash(REPO),
        "platform": platform_id(),
        "python": sys.version.split()[0],
        "platform_system": platform.system().lower(),
        "platform_machine": platform.machine(),
        "lif_model": one["lif_model"],
        "lif_threshold": one["lif_threshold"],
        "lif_reset": one["lif_reset"],
        "lif_on_pre": one["lif_on_pre"],
        "lif_model_sha256": one["lif_model_sha256"],
        "lif_threshold_sha256": one["lif_threshold_sha256"],
        "lif_reset_sha256": one["lif_reset_sha256"],
        "lif_on_pre_sha256": one["lif_on_pre_sha256"],
        "object_names": one["object_names"],
        "namespace_keys": one["namespace_keys"],
        "state_variable_names": one["state_variable_names"],
        "runs": {
            "i": {
                "recipe": one["recipe"],
                "spike_table_sha256": one["spike_table_sha256"],
                "trace_sha256": one["trace_sha256"],
            },
            "ii": {
                "recipe": parts["ii"]["recipe"],
                "spike_table_sha256": parts["ii"]["spike_table_sha256"],
            },
            "iii": {
                "recipe": parts["iii"]["recipe"],
                "spike_table_sha256": parts["iii"]["spike_table_sha256"],
            },
            "iv": {
                "recipe": parts["iv"]["recipe"],
                "spike_table_sha256_silent": parts["iv"]["spike_table_sha256_silent"],
                "spike_table_sha256_sugar": parts["iv"]["spike_table_sha256_sugar"],
            },
        },
    }


def record_off_reference(*, include_full: bool = True) -> dict[str, Any]:
    """Run 0.15 (b) recipes and write tests/fixtures/wp24-off-reference.json."""
    parts = {"i": run_isolated("measure_0_15_b_i", timeout_s=300)}
    if include_full:
        from flyonenomics.orchestrator.budget import acquire_engine_slots

        with acquire_engine_slots(1):
            parts["ii"] = run_isolated("measure_0_15_b_ii")
            parts["iii"] = run_isolated("measure_0_15_b_iii")
            parts["iv"] = run_isolated("measure_0_15_b_iv")
    payload = assemble_off_reference(parts) if include_full else {
        **assemble_off_reference({
            "i": parts["i"],
            "ii": {"recipe": "", "spike_table_sha256": ""},
            "iii": {"recipe": "", "spike_table_sha256": ""},
            "iv": {
                "recipe": "",
                "spike_table_sha256_silent": "",
                "spike_table_sha256_sugar": "",
            },
        }),
        "runs": {"i": {
            "recipe": parts["i"]["recipe"],
            "spike_table_sha256": parts["i"]["spike_table_sha256"],
            "trace_sha256": parts["i"]["trace_sha256"],
        }},
        "partial": True,
    }
    OFF_REFERENCE.write_text(json.dumps(payload, indent=2) + "\n")
    return payload


def check_0_15_b(*, parts: tuple[str, ...] = ("i", "ii", "iii", "iv")) -> dict[str, Any]:
    """Re-run named 0.15 (b) recipes and compare to the committed fixture."""
    fixture = read_json(OFF_REFERENCE)
    measured: dict[str, Any] = {}
    mismatches: list[str] = []
    if "i" in parts:
        ident = platform_id()
        reference = fixture["platform_references"].get(ident)
        if reference is None:
            mismatches.append(f"i.reference: no off-path reference for platform {ident}")
        else:
            got = run_isolated("measure_0_15_b_i", timeout_s=300)
            measured["i"] = got
            ref = reference["runs"]["i"]
            if got["spike_table_sha256"] != ref["spike_table_sha256"]:
                mismatches.append("i.spike_table_sha256")
            if got["trace_sha256"] != ref["trace_sha256"]:
                mismatches.append("i.trace_sha256")
            for key in (
                "lif_model",
                "lif_threshold",
                "lif_reset",
                "lif_on_pre",
                "object_names",
                "namespace_keys",
                "state_variable_names",
            ):
                if got[key] != fixture[key]:
                    mismatches.append(key)
    if "ii" in parts:
        got = run_isolated("measure_0_15_b_ii")
        measured["ii"] = got
        if got["spike_table_sha256"] != fixture["runs"]["ii"]["spike_table_sha256"]:
            mismatches.append("ii.spike_table_sha256")
    if "iii" in parts:
        got = run_isolated("measure_0_15_b_iii")
        measured["iii"] = got
        if got["spike_table_sha256"] != fixture["runs"]["ii"]["spike_table_sha256"]:
            mismatches.append("iii.spike_table_sha256 (must equal ii)")
        if got["spike_table_sha256"] != fixture["runs"]["iii"]["spike_table_sha256"]:
            mismatches.append("iii.spike_table_sha256")
    if "iv" in parts:
        got = run_isolated("measure_0_15_b_iv")
        measured["iv"] = got
        ref = fixture["runs"]["iv"]
        if got["spike_table_sha256_silent"] != ref["spike_table_sha256_silent"]:
            mismatches.append("iv.spike_table_sha256_silent")
        if got["spike_table_sha256_sugar"] != ref["spike_table_sha256_sugar"]:
            mismatches.append("iv.spike_table_sha256_sugar")
    return {
        "passed": not mismatches,
        "mismatches": mismatches,
        "measured": {key: {k: v for k, v in row.items() if "sha256" in k or k == "recipe"} for key, row in measured.items()},
    }


def test_0_15() -> ValidationEntry:
    """Switch neutrality: 0.15 (a) and 0.15 (b)(i) on the tiny engine."""
    result_a = check_0_15_a()
    result_b = check_0_15_b(parts=("i",))
    outcome = "passed" if result_a["passed"] and result_b["passed"] else "failed"
    identity = build_identity(
        REPO,
        connectome_version="630",
        layers=LayerFlags(),
        assay="switch-neutrality",
        fixture="tests/fixtures/wp24-off-reference.json",
        declared_inputs=[
            FIXTURE_0_16,
            "tests/fixtures/engine/tiny_completeness.csv",
            "tests/fixtures/engine/tiny_connectivity.parquet",
            "tests/fixtures/wp24-off-reference.json",
            "data/params-v0.1.yaml",
        ],
    )
    return ValidationEntry(
        test_id="0.15",
        category="verification",
        outcome=outcome,
        compatibility="canonical",
        identity=identity,
        measured={"0.15_a": result_a, "0.15_b_i": result_b},
        fixture_path="tests/fixtures/wp24-off-reference.json",
        declared_inputs=list(identity.inputs),
    )


def _sfa_mechanisms(n: int, *, scope: np.ndarray, b_mv: float, tau_ms: float) -> Any:
    """Build a Mechanisms object with adaptation on the named indices."""
    from flyonenomics.engine.models import Adaptation, Mechanisms

    b = np.zeros(n, dtype=np.float64)
    b[np.asarray(scope, dtype=np.int32)] = float(b_mv)
    tau = np.full(n, float(tau_ms), dtype=np.float64)
    return Mechanisms(adaptation=Adaptation(b_mv=b, tau_ms=tau))


def sfa_reference_procedure(
    *,
    n_ticks: int,
    dt_ms: float,
    v_0: float,
    v_rst: float,
    v_th: float,
    t_mbr: float,
    tau: float,
    rfc_ms: float,
    w_in: float,
    events: np.ndarray,
    b_mv: float,
    tau_sfa_ms: float,
    use_sfa: bool,
) -> dict[str, Any]:
    """Exact one-tick 0.16 reference (SPEC-P2 5.3). Units: mV, ms, ticks."""
    event_set = {int(k) for k in np.asarray(events, dtype=np.int64)}
    e_m = float(np.exp(-dt_ms / t_mbr))
    e_g = float(np.exp(-dt_ms / tau))
    e_a = float(np.exp(-dt_ms / tau_sfa_ms)) if use_sfa else 1.0
    c_g = tau / (tau - t_mbr)
    c_a = tau_sfa_ms / (tau_sfa_ms - t_mbr) if use_sfa else 0.0
    rfc_ticks = int(round(rfc_ms / dt_ms))
    v = float(v_0)
    g = 0.0
    a = 0.0
    s_last = -10**18
    has_spiked = False
    v_rec: list[float] = []
    a_rec: list[float] = []
    spike_ticks: list[int] = []
    lost_refractory = 0
    lost_spike_tick = 0
    min_gap = float("inf")
    for k in range(n_ticks + 1):
        v_rec.append(v)
        a_rec.append(a)
        if k == n_ticks:
            break
        is_ref = bool(has_spiked and (k - s_last) < rfc_ticks)
        if not is_ref:
            if use_sfa:
                v = v_0 + (v - v_0) * e_m + g * c_g * (e_g - e_m) - a * c_a * (e_a - e_m)
                g = g * e_g
                a = a * e_a
            else:
                v = v_0 + (v - v_0) * e_m + g * c_g * (e_g - e_m)
                g = g * e_g
            gap = abs(v - v_th)
            if gap < min_gap:
                min_gap = gap
            did_spike = v > v_th
        else:
            did_spike = False
        if did_spike:
            spike_ticks.append(k)
        if k in event_set:
            if is_ref:
                lost_refractory += 1
            elif did_spike:
                lost_spike_tick += 1
            else:
                g += w_in
        if did_spike:
            s_last = k
            has_spiked = True
            v = v_rst
            g = 0.0
            if use_sfa:
                a = a + b_mv
    return {
        "v_mv": np.asarray(v_rec, dtype=np.float64),
        "a_sfa_mv": np.asarray(a_rec, dtype=np.float64),
        "spike_ticks": np.asarray(spike_ticks, dtype=np.int64),
        "lost_refractory": lost_refractory,
        "lost_spike_tick": lost_spike_tick,
        "min_gap_to_threshold_mv": float(min_gap),
    }


def _compare_016_trace(engine_v: np.ndarray, ref_v: np.ndarray) -> float:
    """Largest |x - x_ref| / max(|x_ref|, 1 mV). Units: mV. Shapes: (n_time,)."""
    scale = np.maximum(np.abs(ref_v), 1.0)
    return float(np.max(np.abs(engine_v - ref_v) / scale))


def _run_016(
    *,
    mechanisms: Any = _UNSET,
    rfc_ms: float | None = None,
) -> dict[str, Any]:
    """Drive the 0.16 fixture and return neuron-0 spikes, v, and a_sfa."""
    from flyonenomics.validation.level0 import prepare, run_chunks

    kwargs: dict[str, Any] = {}
    if mechanisms is not _UNSET:
        kwargs["mechanisms"] = mechanisms
    engine = _tiny_016_engine(**kwargs)
    fix = read_json(REPO / FIXTURE_0_16)
    params = load_params()
    prepare(engine)
    silence = float(params.get("engine.silence_vth"))
    v_th = float(params.get("lif.v_th"))
    thresholds = np.full(engine.n, v_th, dtype=np.float64)
    thresholds[1:] = silence
    engine.set_threshold(thresholds)
    ticks = np.array(fix["spike_tick"], dtype=np.int64)
    engine.set_spike_list(
        np.full(ticks.shape, int(fix["driver"]), dtype=np.int32),
        ticks,
    )
    if rfc_ms is not None:
        engine.set_refractory(
            np.array([int(fix["driver"])], dtype=np.int32),
            np.array([rfc_ms], dtype=np.float64),
        )
    engine.seed(int(fix["seed"]))
    duration_ms = float(fix["duration_ticks"]) * float(fix["dt_ms"])
    run_chunks(engine, duration_ms)
    spikes = engine.spikes(0)
    traces = engine.traces(0)
    mech = engine.mechanism_traces(0)
    keep = spikes.idx == int(fix["driver"])
    return {
        "n": int(engine.n),
        "engine_model": engine.engine_model(),
        "spike_ticks": np.asarray(spikes.tick[keep], dtype=np.int64),
        "tick": np.asarray(traces.tick, dtype=np.int64),
        "v_mv": np.asarray(traces.v_mv[0], dtype=np.float64),
        "a_sfa_mv": None if mech.a_sfa_mv is None else np.asarray(mech.a_sfa_mv[0], dtype=np.float64),
        "columns": list(mech.columns()),
    }


def _016_params() -> dict[str, Any]:
    """LIF and input constants for the 0.16 reference. Units: mV and ms."""
    params = load_params()
    return {
        "v_0": float(params.get("lif.v_0")),
        "v_rst": float(params.get("lif.v_rst")),
        "v_th": float(params.get("lif.v_th")),
        "t_mbr": float(params.get("lif.t_mbr")),
        "tau": float(params.get("lif.tau")),
        "t_rfc": float(params.get("lif.t_rfc")),
        "dt_ms": float(params.get("lif.dt")),
        "w_in": float(params.get("input.w_in")),
    }


def _016_align(ref: dict[str, Any], tick: np.ndarray) -> dict[str, Any]:
    """Take reference samples at the engine trace ticks."""
    v = np.asarray(ref["v_mv"], dtype=np.float64)
    a = np.asarray(ref["a_sfa_mv"], dtype=np.float64)
    if int(tick.max()) >= v.shape[0] or int(tick.min()) < 0:
        raise ValueError("trace ticks fall outside the 0.16 reference")
    return {
        **ref,
        "v_mv": v[tick],
        "a_sfa_mv": a[tick],
    }


def _016_clause(
    *,
    engine_sfa: bool,
    ref_sfa: bool,
    b_mv: float,
    tau_ms: float,
    scope: np.ndarray,
    rfc_ms: float | None,
    lif_spikes: np.ndarray | None,
) -> dict[str, Any]:
    """Run one 0.16 engine setting against the reference procedure."""
    fix = read_json(REPO / FIXTURE_0_16)
    constants = _016_params()
    n_ticks = int(fix["duration_ticks"])
    events = np.array(fix["spike_tick"], dtype=np.int64)
    rfc = constants["t_rfc"] if rfc_ms is None else float(rfc_ms)
    ref = sfa_reference_procedure(
        n_ticks=n_ticks,
        dt_ms=constants["dt_ms"],
        v_0=constants["v_0"],
        v_rst=constants["v_rst"],
        v_th=constants["v_th"],
        t_mbr=constants["t_mbr"],
        tau=constants["tau"],
        rfc_ms=rfc,
        w_in=constants["w_in"],
        events=events,
        b_mv=b_mv,
        tau_sfa_ms=tau_ms,
        use_sfa=ref_sfa,
    )
    mechanisms: Any = _UNSET
    if engine_sfa:
        mechanisms = _sfa_mechanisms(4, scope=scope, b_mv=b_mv, tau_ms=tau_ms)
    got = _run_016(mechanisms=mechanisms, rfc_ms=rfc_ms)
    aligned = _016_align(ref, got["tick"])
    err_v = _compare_016_trace(got["v_mv"], aligned["v_mv"])
    err_a = 0.0
    if engine_sfa and ref_sfa and 0 in {int(i) for i in scope}:
        if got["a_sfa_mv"] is None:
            raise RuntimeError("lif+sfa traces have no a_sfa_mv")
        err_a = _compare_016_trace(got["a_sfa_mv"], aligned["a_sfa_mv"])
    spikes_equal = np.array_equal(got["spike_ticks"], aligned["spike_ticks"])
    fewer = True
    if lif_spikes is not None:
        fewer = int(got["spike_ticks"].shape[0]) < int(lif_spikes.shape[0])
    a_zero = True
    if got["a_sfa_mv"] is not None and 0 not in {int(i) for i in scope}:
        a_zero = bool(np.all(got["a_sfa_mv"] == 0.0))
    passed = bool(
        spikes_equal
        and err_v <= 1e-9
        and err_a <= 1e-9
        and aligned["min_gap_to_threshold_mv"] >= 1e-6
        and fewer
        and a_zero
    )
    return {
        "passed": passed,
        "spikes_equal": spikes_equal,
        "err_v": err_v,
        "err_a": err_a,
        "n_spikes": int(got["spike_ticks"].shape[0]),
        "n_ref_spikes": int(aligned["spike_ticks"].shape[0]),
        "fewer_than_lif": fewer,
        "a_sfa_zero": a_zero,
        "lost_refractory": aligned["lost_refractory"],
        "lost_spike_tick": aligned["lost_spike_tick"],
        "min_gap_to_threshold_mv": aligned["min_gap_to_threshold_mv"],
        "engine_model": got["engine_model"],
        "columns": got["columns"],
        "spike_ticks": got["spike_ticks"].tolist(),
        "last_spike": int(got["spike_ticks"][-1]) if got["spike_ticks"].shape[0] else None,
        "tick0": int(got["tick"][0]),
        "tick1": int(got["tick"][-1]),
        "a_sfa_mv": None if got["a_sfa_mv"] is None else got["a_sfa_mv"].tolist(),
        "v_mv_tail": got["v_mv"][-1],
        "got_tick": got["tick"].tolist(),
        "dt_ms": constants["dt_ms"],
        "t_rfc": constants["t_rfc"],
        "tau_ms": tau_ms,
    }


def _016_decay(clause: dict[str, Any]) -> dict[str, Any]:
    """0.16 (d): a_sfa decay after the last spike, with no event in between."""
    if clause["a_sfa_mv"] is None or clause["last_spike"] is None:
        return {"passed": False, "reason": "no a_sfa or no spike"}
    a = np.asarray(clause["a_sfa_mv"], dtype=np.float64)
    tick = np.asarray(clause["got_tick"], dtype=np.int64)
    dt_ms = float(clause["dt_ms"])
    rfc_ticks = int(round(float(clause["t_rfc"]) / dt_ms))
    j_tick = int(clause["last_spike"]) + rfc_ticks + 1
    if j_tick not in set(int(t) for t in tick):
        return {"passed": False, "reason": f"decay start tick {j_tick} missing"}
    j = int(np.where(tick == j_tick)[0][0])
    k = int(a.shape[0] - 1)
    if a[j] == 0.0:
        return {"passed": False, "reason": "a_sfa at decay start is 0"}
    ratio = float(a[k] / a[j])
    expected = float(np.exp(-(int(tick[k]) - int(tick[j])) * dt_ms / float(clause["tau_ms"])))
    err = abs(ratio - expected) / max(abs(expected), 1e-30)
    return {
        "passed": bool(err <= 1e-9),
        "ratio": ratio,
        "expected": expected,
        "err": err,
        "j_tick": j_tick,
        "k_tick": int(tick[k]),
    }


def measure_0_16() -> dict[str, Any]:
    """0.16: adaptation of one neuron against its exact solution."""
    settings = [(1.0, 150.0), (3.0, 50.0), (0.3, 500.0)]
    scope0 = np.array([0], dtype=np.int32)
    lif_a = _016_clause(
        engine_sfa=False, ref_sfa=False, b_mv=0.0, tau_ms=150.0, scope=scope0, rfc_ms=None, lif_spikes=None
    )
    sfa_b = [
        _016_clause(
            engine_sfa=True, ref_sfa=True, b_mv=b, tau_ms=tau, scope=scope0, rfc_ms=None, lif_spikes=np.array(lif_a["spike_ticks"])
        )
        for b, tau in settings
    ]
    lif_c = _016_clause(
        engine_sfa=False, ref_sfa=False, b_mv=0.0, tau_ms=150.0, scope=scope0, rfc_ms=0.0, lif_spikes=None
    )
    sfa_c = [
        _016_clause(
            engine_sfa=True, ref_sfa=True, b_mv=b, tau_ms=tau, scope=scope0, rfc_ms=0.0, lif_spikes=np.array(lif_c["spike_ticks"])
        )
        for b, tau in settings
    ]
    decay = [_016_decay(row) for row in sfa_b]
    scope_out = np.array([1, 2, 3], dtype=np.int32)
    sfa_e = _016_clause(
        engine_sfa=True, ref_sfa=False, b_mv=1.0, tau_ms=150.0, scope=scope_out, rfc_ms=None, lif_spikes=None
    )
    # (e) compares to the lif reference, not fewer-than-lif.
    e_ok = bool(
        sfa_e["spikes_equal"]
        and sfa_e["err_v"] <= 1e-9
        and sfa_e["a_sfa_zero"]
        and sfa_e["engine_model"] == "lif+sfa"
    )
    b_events = all(row["lost_refractory"] >= 1 and row["lost_spike_tick"] >= 1 for row in sfa_b)
    c_events = all(row["lost_spike_tick"] >= 1 for row in sfa_c)
    passed = bool(
        lif_a["passed"]
        and lif_a["engine_model"] == "lif"
        and all(row["passed"] for row in sfa_b)
        and all(row["engine_model"] == "lif+sfa" for row in sfa_b)
        and lif_c["passed"]
        and all(row["passed"] for row in sfa_c)
        and all(row["passed"] for row in decay)
        and e_ok
        and b_events
        and c_events
        and lif_a["min_gap_to_threshold_mv"] >= 1e-6
    )
    def slim(row: dict[str, Any]) -> dict[str, Any]:
        return {key: row[key] for key in (
            "passed", "spikes_equal", "err_v", "err_a", "n_spikes", "n_ref_spikes",
            "fewer_than_lif", "lost_refractory", "lost_spike_tick",
            "min_gap_to_threshold_mv", "engine_model", "columns",
        ) if key in row}

    return {
        "passed": passed,
        "a": slim(lif_a),
        "b": [slim(row) for row in sfa_b],
        "c_lif": slim(lif_c),
        "c_sfa": [slim(row) for row in sfa_c],
        "d": decay,
        "e": {
            "passed": e_ok,
            "err_v": sfa_e["err_v"],
            "a_sfa_zero": sfa_e["a_sfa_zero"],
            "spikes_equal": sfa_e["spikes_equal"],
            "engine_model": sfa_e["engine_model"],
        },
        "b_events_ok": b_events,
        "c_events_ok": c_events,
    }


def check_0_16() -> dict[str, Any]:
    """Run 0.16 in a fresh process."""
    return run_isolated("measure_0_16")


def test_0_16() -> ValidationEntry:
    """Adaptation of one neuron against its exact solution (SPEC-P2 5.3)."""
    result = check_0_16()
    identity = build_identity(
        REPO,
        connectome_version="630",
        layers=LayerFlags(),
        assay="adaptation",
        fixture=FIXTURE_0_16,
        declared_inputs=[
            FIXTURE_0_16,
            "tests/fixtures/engine/tiny_completeness.csv",
            "tests/fixtures/engine/tiny_connectivity.parquet",
            "data/params-v0.1.yaml",
        ],
    )
    return ValidationEntry(
        test_id="0.16",
        category="verification",
        outcome="passed" if result["passed"] else "failed",
        compatibility="canonical",
        identity=identity,
        measured={"0.16": result},
        fixture_path=FIXTURE_0_16,
        declared_inputs=list(identity.inputs),
    )


def _std_mechanisms(n: int, *, scope: np.ndarray, U: float, tau_ms: float) -> Any:
    """Build a Mechanisms object with depression on the named indices."""
    from flyonenomics.engine.models import Depression, Mechanisms

    u = np.zeros(n, dtype=np.float64)
    u[np.asarray(scope, dtype=np.int32)] = float(U)
    tau = np.full(n, float(tau_ms), dtype=np.float64)
    return Mechanisms(depression=Depression(U=u, tau_ms=tau))


def _tiny_017_engine(*, mechanisms: Any = _UNSET, with_bank: bool = False) -> Any:
    """Build the 0.17 two-neuron engine. Units: none. Shapes: n == 2."""
    import numpy as np

    from flyonenomics.engine import BrianEngine, InputTopology, UpstreamBank
    from flyonenomics.types import ConnectomeFiles

    fix = read_json(REPO / FIXTURE_0_17)
    engine = BrianEngine()
    engine.seed(int(fix["seed"]))
    banks = []
    if with_bank:
        banks = [UpstreamBank(idx=np.array([0], dtype=np.int32), rate_hz=1.0)]
    build_kwargs: dict[str, Any] = {}
    if mechanisms is not _UNSET:
        build_kwargs["mechanisms"] = mechanisms
    engine.build(
        ConnectomeFiles(
            completeness=FIX / "tiny_std_completeness.csv",
            connectivity=FIX / "tiny_std_connectivity.parquet",
            version="630",
        ),
        load_params(),
        InputTopology(
            upstream_banks=banks,
            spikelist_idx=np.array(fix["spikelist_idx"], dtype=np.int32),
            trace_idx=np.array(fix["trace_idx"], dtype=np.int32),
        ),
        **build_kwargs,
    )
    return engine


def _017_params() -> dict[str, Any]:
    """LIF, delay and input constants for the 0.17 closed form. Units: mV and ms."""
    params = load_params()
    return {
        "v_0": float(params.get("lif.v_0")),
        "v_rst": float(params.get("lif.v_rst")),
        "v_th": float(params.get("lif.v_th")),
        "t_mbr": float(params.get("lif.t_mbr")),
        "tau": float(params.get("lif.tau")),
        "t_rfc": float(params.get("lif.t_rfc")),
        "t_dly": float(params.get("lif.t_dly")),
        "dt_ms": float(params.get("lif.dt")),
        "w_in": float(params.get("input.w_in")),
        "w_syn": float(params.get("lif.w_syn")),
    }


def std_closed_form(
    *,
    spike_ticks: np.ndarray,
    n_ticks: int,
    dt_ms: float,
    U: float,
    tau_std_ms: float,
    t_dly_ms: float,
    t_mbr: float,
    tau: float,
    v_0: float,
    w_syn: float,
    tick: np.ndarray,
) -> dict[str, Any]:
    """0.17 closed form for x_std of neuron 0 and v of neuron 1. Units: mV, ms, ticks."""
    s = [int(x) for x in np.asarray(spike_ticks, dtype=np.int64)]
    x = np.ones(n_ticks + 1, dtype=np.float64)
    xr_list: list[float] = []
    x_plus: list[float] = []
    for k, sk in enumerate(s):
        if k == 0:
            xr_k = 1.0
        else:
            xr_k = 1.0 - (1.0 - x_plus[k - 1]) * float(
                np.exp(-(sk - s[k - 1]) * dt_ms / tau_std_ms)
            )
        xr_list.append(xr_k)
        xp = xr_k * (1.0 - U)
        x_plus.append(xp)
        end = s[k + 1] if k + 1 < len(s) else n_ticks
        for j in range(sk + 1, end + 1):
            if 0 <= j <= n_ticks:
                x[j] = 1.0 - (1.0 - xp) * float(
                    np.exp(-(j - sk - 1) * dt_ms / tau_std_ms)
                )
    delay_ticks = int(round(t_dly_ms / dt_ms))
    time_ms = np.asarray(tick, dtype=np.float64) * dt_ms
    v = np.full(time_ms.shape, v_0, dtype=np.float64)
    weight = 20.0 * w_syn
    denom = 1.0 - t_mbr / tau
    for k, sk in enumerate(s):
        acting = sk + delay_ticks + 1
        arrival = acting * dt_ms
        mask = time_ms >= arrival - 1e-12
        tp = time_ms[mask] - arrival
        kernel = (np.exp(-tp / tau) - np.exp(-tp / t_mbr)) / denom
        v[mask] += weight * xr_list[k] * kernel
    tick_i = np.asarray(tick, dtype=np.int64)
    if int(tick_i.max()) >= x.shape[0] or int(tick_i.min()) < 0:
        raise ValueError("trace ticks fall outside the 0.17 closed form")
    return {
        "x_std": x[tick_i],
        "xr": np.asarray(xr_list, dtype=np.float64),
        "v_mv": v,
        "min_gap_to_threshold_mv": 0.0,
    }


def _run_017(*, mechanisms: Any = _UNSET) -> dict[str, Any]:
    """Drive the 0.17 fixture and return neuron-0 spikes and both traces."""
    from flyonenomics.validation.level0 import prepare, run_chunks

    kwargs: dict[str, Any] = {}
    if mechanisms is not _UNSET:
        kwargs["mechanisms"] = mechanisms
    engine = _tiny_017_engine(**kwargs)
    fix = read_json(REPO / FIXTURE_0_17)
    params = load_params()
    prepare(engine)
    ticks = np.array(fix["spike_tick"], dtype=np.int64)
    engine.set_spike_list(
        np.full(ticks.shape, int(fix["driver"]), dtype=np.int32),
        ticks,
    )
    engine.seed(int(fix["seed"]))
    duration_ms = float(fix["duration_ticks"]) * float(fix["dt_ms"])
    run_chunks(engine, duration_ms)
    spikes = engine.spikes(0)
    traces = engine.traces(0)
    mech = engine.mechanism_traces(0)
    keep = spikes.idx == int(fix["driver"])
    rec = int(fix["recorded"])
    rec_row = int(np.where(traces.idx == rec)[0][0])
    drv_row = int(np.where(traces.idx == int(fix["driver"]))[0][0])
    return {
        "n": int(engine.n),
        "engine_model": engine.engine_model(),
        "method": engine.method(),
        "spike_ticks": np.asarray(spikes.tick[keep], dtype=np.int64),
        "tick": np.asarray(traces.tick, dtype=np.int64),
        "v_mv": np.asarray(traces.v_mv[rec_row], dtype=np.float64),
        "x_std": None if mech.x_std is None else np.asarray(mech.x_std[drv_row], dtype=np.float64),
        "xr_std": None if mech.xr_std is None else np.asarray(mech.xr_std[drv_row], dtype=np.float64),
        "columns": list(mech.columns()),
        "v_th": float(params.get("lif.v_th")),
    }


def _017_clause(*, engine_std: bool, U: float, tau_ms: float, scope: np.ndarray) -> dict[str, Any]:
    """Run one 0.17 engine setting against the closed form."""
    fix = read_json(REPO / FIXTURE_0_17)
    constants = _017_params()
    n_ticks = int(fix["duration_ticks"])
    events = np.array(fix["spike_tick"], dtype=np.int64)
    driver = sfa_reference_procedure(
        n_ticks=n_ticks,
        dt_ms=constants["dt_ms"],
        v_0=constants["v_0"],
        v_rst=constants["v_rst"],
        v_th=constants["v_th"],
        t_mbr=constants["t_mbr"],
        tau=constants["tau"],
        rfc_ms=constants["t_rfc"],
        w_in=constants["w_in"],
        events=events,
        b_mv=0.0,
        tau_sfa_ms=150.0,
        use_sfa=False,
    )
    mechanisms: Any = _UNSET
    if engine_std:
        mechanisms = _std_mechanisms(2, scope=scope, U=U, tau_ms=tau_ms)
    got = _run_017(mechanisms=mechanisms)
    form = std_closed_form(
        spike_ticks=driver["spike_ticks"],
        n_ticks=n_ticks,
        dt_ms=constants["dt_ms"],
        U=U if engine_std and 0 in {int(i) for i in scope} else 0.0,
        tau_std_ms=tau_ms,
        t_dly_ms=constants["t_dly"],
        t_mbr=constants["t_mbr"],
        tau=constants["tau"],
        v_0=constants["v_0"],
        w_syn=constants["w_syn"],
        tick=got["tick"],
    )
    err_v = _compare_016_trace(got["v_mv"], form["v_mv"])
    err_x = 0.0
    if engine_std and got["x_std"] is not None:
        err_x = float(np.max(np.abs(got["x_std"] - form["x_std"])))
    spikes_equal = np.array_equal(got["spike_ticks"], driver["spike_ticks"])
    one_per_event = int(got["spike_ticks"].shape[0]) == int(events.shape[0])
    min_gap = float(np.min(constants["v_th"] - form["v_mv"]))
    x_one = True
    xr_one = True
    if engine_std and 0 not in {int(i) for i in scope}:
        x_one = bool(got["x_std"] is not None and np.all(got["x_std"] == 1.0))
        xr_one = bool(got["xr_std"] is not None and np.all(got["xr_std"] == 1.0))
    passed = bool(
        spikes_equal
        and one_per_event
        and err_v <= 1e-9
        and err_x <= 1e-9
        and min_gap >= 1.0
        and x_one
        and xr_one
    )
    window = (got["tick"] * constants["dt_ms"] >= 810.0) & (got["tick"] * constants["dt_ms"] < 1010.0)
    mean_dev = float(np.mean(got["v_mv"][window] - constants["v_0"])) if np.any(window) else float("nan")
    return {
        "passed": passed,
        "spikes_equal": spikes_equal,
        "one_per_event": one_per_event,
        "err_v": err_v,
        "err_x": err_x,
        "min_gap_to_threshold_mv": min_gap,
        "mean_dev_810_1010": mean_dev,
        "engine_model": got["engine_model"],
        "method": got["method"],
        "columns": got["columns"],
        "x_one": x_one,
        "xr_one": xr_one,
        "n_spikes": int(got["spike_ticks"].shape[0]),
    }


def _017_guard() -> dict[str, Any]:
    """0.17 (d): set_refractory and compose_refractory raise the latch error."""
    mechanisms = _std_mechanisms(2, scope=np.array([0], dtype=np.int32), U=0.2, tau_ms=100.0)
    engine = _tiny_017_engine(mechanisms=mechanisms)
    raised_set = False
    try:
        engine.set_refractory(
            np.array([0], dtype=np.int32),
            np.array([1.0], dtype=np.float64),
        )
    except ValueError as exc:
        raised_set = str(exc) == "depression latch: refractory period below lif.t_dly"
    engine_bank = _tiny_017_engine(mechanisms=mechanisms, with_bank=True)
    raised_compose = False
    try:
        engine_bank.compose_refractory()
    except ValueError as exc:
        raised_compose = str(exc) == "depression latch: refractory period below lif.t_dly"
    return {"passed": bool(raised_set and raised_compose), "set": raised_set, "compose": raised_compose}


def measure_0_17() -> dict[str, Any]:
    """0.17: depression of one connection against its closed form."""
    settings = [(0.2, 100.0), (0.5, 400.0), (0.05, 400.0)]
    scope0 = np.array([0], dtype=np.int32)
    lif_a = _017_clause(engine_std=False, U=0.0, tau_ms=100.0, scope=scope0)
    std_b = [
        _017_clause(engine_std=True, U=u, tau_ms=tau, scope=scope0)
        for u, tau in settings
    ]
    mean_ok = all(
        row["mean_dev_810_1010"] < 0.9 * lif_a["mean_dev_810_1010"]
        for row in std_b
    )
    scope_out = np.array([1], dtype=np.int32)
    std_c = _017_clause(engine_std=True, U=0.2, tau_ms=100.0, scope=scope_out)
    guard = _017_guard()
    passed = bool(
        lif_a["passed"]
        and lif_a["engine_model"] == "lif"
        and all(row["passed"] for row in std_b)
        and all(row["engine_model"] == "lif+std" for row in std_b)
        and mean_ok
        and std_c["passed"]
        and std_c["engine_model"] == "lif+std"
        and std_c["x_one"]
        and std_c["xr_one"]
        and guard["passed"]
    )
    def slim(row: dict[str, Any]) -> dict[str, Any]:
        return {key: row[key] for key in (
            "passed", "spikes_equal", "one_per_event", "err_v", "err_x",
            "min_gap_to_threshold_mv", "mean_dev_810_1010", "engine_model",
            "method", "columns", "x_one", "xr_one", "n_spikes",
        ) if key in row}

    return {
        "passed": passed,
        "a": slim(lif_a),
        "b": [slim(row) for row in std_b],
        "mean_ok": mean_ok,
        "c": slim(std_c),
        "d": guard,
    }


def check_0_17() -> dict[str, Any]:
    """Run 0.17 in a fresh process."""
    return run_isolated("measure_0_17", timeout_s=300)


def test_0_17() -> ValidationEntry:
    """Depression of one connection against its closed form (SPEC-P2 5.3)."""
    result = check_0_17()
    identity = build_identity(
        REPO,
        connectome_version="630",
        layers=LayerFlags(),
        assay="depression",
        fixture=FIXTURE_0_17,
        declared_inputs=[
            FIXTURE_0_17,
            "tests/fixtures/engine/tiny_std_completeness.csv",
            "tests/fixtures/engine/tiny_std_connectivity.parquet",
            "data/params-v0.1.yaml",
        ],
    )
    return ValidationEntry(
        test_id="0.17",
        category="verification",
        outcome="passed" if result["passed"] else "failed",
        compatibility="canonical",
        identity=identity,
        measured={"0.17": result},
        fixture_path=FIXTURE_0_17,
        declared_inputs=list(identity.inputs),
    )


def _018_params() -> dict[str, Any]:
    """LIF constants for 0.18. Units: mV and ms."""
    params = load_params()
    return {
        "v_0": float(params.get("lif.v_0")),
        "v_rst": float(params.get("lif.v_rst")),
        "v_th": float(params.get("lif.v_th")),
        "t_mbr": float(params.get("lif.t_mbr")),
        "tau": float(params.get("lif.tau")),
        "t_rfc": float(params.get("lif.t_rfc")),
        "t_dly": float(params.get("lif.t_dly")),
        "dt_ms": float(params.get("lif.dt")),
        "w_in": float(params.get("input.w_in")),
        "w_syn": float(params.get("lif.w_syn")),
    }


def _018_event_ms() -> tuple[np.ndarray, np.ndarray]:
    """Event times in ms from the 0.18 fixture lists recorded at 0.1 ms."""
    fix = read_json(REPO / FIXTURE_0_18)
    t0 = np.asarray(fix["spike_tick_0"], dtype=np.float64) * 0.1
    t1 = np.asarray(fix["spike_tick_1"], dtype=np.float64) * 0.1
    return t0, t1


def _018_ticks(dt_ms: float) -> tuple[np.ndarray, np.ndarray]:
    """Event ticks at one dt. Units: ms. Shapes: (50,) and (80,)."""
    t0, t1 = _018_event_ms()
    return (
        np.rint(t0 / dt_ms).astype(np.int64),
        np.rint(t1 / dt_ms).astype(np.int64),
    )


def _018_driver_spikes(events: np.ndarray, dt_ms: float, n_ticks: int) -> np.ndarray:
    """0.16 lif reference spike ticks for one 0.18 driver list."""
    constants = _018_params()
    ref = sfa_reference_procedure(
        n_ticks=n_ticks,
        dt_ms=dt_ms,
        v_0=constants["v_0"],
        v_rst=constants["v_rst"],
        v_th=constants["v_th"],
        t_mbr=constants["t_mbr"],
        tau=constants["tau"],
        rfc_ms=constants["t_rfc"],
        w_in=constants["w_in"],
        events=events,
        b_mv=0.0,
        tau_sfa_ms=150.0,
        use_sfa=False,
    )
    return np.asarray(ref["spike_ticks"], dtype=np.int64)


def _018_acting(spike_ticks: np.ndarray, dt_ms: float, t_dly_ms: float) -> np.ndarray:
    """Acting ticks of delayed recurrent delivery. Units: ticks."""
    delay = int(round(t_dly_ms / dt_ms))
    return np.asarray(spike_ticks, dtype=np.int64) + delay + 1


def _018_lif_v(tick: np.ndarray, acting_w: list[tuple[int, float]], *, v_0: float, t_mbr: float, tau: float, dt_ms: float) -> np.ndarray:
    """0.1 kernel summed over signed recurrent events. Units: mV."""
    time_ms = np.asarray(tick, dtype=np.float64) * dt_ms
    v = np.full(time_ms.shape, v_0, dtype=np.float64)
    denom = 1.0 - t_mbr / tau
    for acting, weight in acting_w:
        arrival = acting * dt_ms
        mask = time_ms >= arrival - 1e-12
        tp = time_ms[mask] - arrival
        v[mask] += weight * (np.exp(-tp / tau) - np.exp(-tp / t_mbr)) / denom
    return v


def _018_dop853(
    *,
    E_inh: float,
    v_0: float,
    t_mbr: float,
    tau: float,
    dt_ms: float,
    n_ticks: int,
    jumps: list[tuple[int, float, float]],
    sample: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Integrate neuron 2's cbi equations with DOP853. Units: mV, ticks."""
    from collections import defaultdict

    from scipy.integrate import solve_ivp

    def rhs(_t: float, y: np.ndarray) -> list[float]:
        u, g, h = float(y[0]), float(y[1]), float(y[2])
        return [
            (-(1.0 + h) * u + g + h * (E_inh - v_0)) / t_mbr,
            -g / tau,
            -h / tau,
        ]

    grouped: dict[int, list[tuple[float, float]]] = defaultdict(list)
    for acting, dg, dh in jumps:
        grouped[int(acting)].append((float(dg), float(dh)))
    acting_ticks = sorted(grouped)
    t_end = n_ticks * dt_ms
    sample = np.asarray(sample, dtype=np.int64)
    t_sample = sample.astype(np.float64) * dt_ms
    u_out = np.zeros(sample.shape, dtype=np.float64)
    h_out = np.zeros(sample.shape, dtype=np.float64)
    y = np.array([0.0, 0.0, 0.0], dtype=np.float64)
    t_cur = 0.0
    filled = 0

    def record_until(t_stop: float) -> None:
        nonlocal filled, y, t_cur
        mask = (t_sample >= t_cur - 1e-15) & (t_sample < t_stop - 1e-15)
        idx = np.where(mask)[0]
        if idx.size:
            sol = solve_ivp(
                rhs, (t_cur, t_stop), y, method="DOP853",
                rtol=1e-13, atol=1e-13, t_eval=t_sample[idx], dense_output=False,
            )
            if not sol.success:
                raise RuntimeError(f"DOP853 failed: {sol.message}")
            u_out[idx] = sol.y[0]
            h_out[idx] = sol.y[2]
            filled += int(idx.size)
        if t_stop > t_cur:
            sol = solve_ivp(
                rhs, (t_cur, t_stop), y, method="DOP853",
                rtol=1e-13, atol=1e-13, t_eval=np.array([t_stop], dtype=np.float64),
            )
            if not sol.success:
                raise RuntimeError(f"DOP853 failed: {sol.message}")
            y = np.array(sol.y[:, -1], dtype=np.float64)
        t_cur = t_stop

    for acting in acting_ticks:
        t_act = acting * dt_ms
        if t_act > t_cur:
            record_until(t_act)
        for dg, dh in grouped[acting]:
            y[1] += dg
            y[2] += dh
        exact = np.where(np.isclose(t_sample, t_act, rtol=0.0, atol=1e-12))[0]
        u_out[exact] = y[0]
        h_out[exact] = y[2]
        filled += int(exact.size)
    if t_cur < t_end:
        record_until(t_end)
    leftover = np.where(np.isclose(t_sample, t_end, rtol=0.0, atol=1e-12) & (u_out == 0.0) & (sample == n_ticks))[0]
    if leftover.size:
        u_out[leftover] = y[0]
        h_out[leftover] = y[2]
    return u_out + v_0, h_out


def _tiny_018_engine(*, mechanisms: Any = _UNSET, dt_ms: float | None = None) -> Any:
    """Build the 0.18 three-neuron engine."""
    from flyonenomics.engine import BrianEngine, InputTopology
    from flyonenomics.types import ConnectomeFiles

    fix = read_json(REPO / FIXTURE_0_18)
    params = load_params()
    if dt_ms is not None:
        params.data["lif"]["dt"]["value"] = float(dt_ms)
    engine = BrianEngine()
    engine.seed(int(fix["seed"]))
    build_kwargs: dict[str, Any] = {}
    if mechanisms is not _UNSET:
        build_kwargs["mechanisms"] = mechanisms
    engine.build(
        ConnectomeFiles(
            completeness=FIX / "tiny_cbi_completeness.csv",
            connectivity=FIX / "tiny_cbi_connectivity.parquet",
            version="630",
        ),
        params,
        InputTopology(
            spikelist_idx=np.array(fix["spikelist_idx"], dtype=np.int32),
            trace_idx=np.array(fix["trace_idx"], dtype=np.int32),
        ),
        **build_kwargs,
    )
    return engine


def _cbi_mechanisms(E_inh_mv: float) -> Any:
    """Build a Mechanisms object for lif+cbi."""
    from flyonenomics.engine.models import ConductanceInhibition, Mechanisms

    return Mechanisms(conductance_inhibition=ConductanceInhibition(E_inh_mv=float(E_inh_mv)))


def _run_018(
    *,
    mechanisms: Any = _UNSET,
    dt_ms: float = 0.1,
    events0: np.ndarray | None = None,
    events1: np.ndarray | None = None,
    scale: np.ndarray | None = None,
) -> dict[str, Any]:
    """Drive the 0.18 fixture and return neuron-2 traces and driver spikes."""
    from flyonenomics.validation.level0 import prepare, run_chunks

    fix = read_json(REPO / FIXTURE_0_18)
    kwargs: dict[str, Any] = {}
    if mechanisms is not _UNSET:
        kwargs["mechanisms"] = mechanisms
    engine = _tiny_018_engine(dt_ms=dt_ms, **kwargs)
    prepare(engine)
    t0, t1 = _018_ticks(dt_ms)
    if events0 is not None:
        t0 = np.asarray(events0, dtype=np.int64)
    if events1 is not None:
        t1 = np.asarray(events1, dtype=np.int64)
    idx = np.concatenate([
        np.full(t0.shape, 0, dtype=np.int32),
        np.full(t1.shape, 1, dtype=np.int32),
    ])
    ticks = np.concatenate([t0, t1]).astype(np.int64)
    engine.set_spike_list(idx, ticks)
    if scale is not None:
        engine.set_weight_scale(np.asarray(scale, dtype=np.float32))
    engine.seed(int(fix["seed"]))
    run_chunks(engine, float(fix["duration_ms"]))
    spikes = engine.spikes(0)
    traces = engine.traces(0)
    mech = engine.mechanism_traces(0)
    rec = int(fix["recorded"])
    rec_row = int(np.where(traces.idx == rec)[0][0])
    return {
        "engine_model": engine.engine_model(),
        "method": engine.method(),
        "spike_0": np.asarray(spikes.tick[spikes.idx == 0], dtype=np.int64),
        "spike_1": np.asarray(spikes.tick[spikes.idx == 1], dtype=np.int64),
        "tick": np.asarray(traces.tick, dtype=np.int64),
        "v_mv": np.asarray(traces.v_mv[rec_row], dtype=np.float64),
        "h_inh": None if mech.h_inh is None else np.asarray(mech.h_inh[rec_row], dtype=np.float64),
        "columns": list(mech.columns()),
        "n_syn": int(engine.n_syn),
        "h_max_last": None,
    }


def _018_jumps(s0: np.ndarray, s1: np.ndarray, *, dt_ms: float, t_dly: float, w_syn: float, E_inh: float | None, v_0: float, flipped: bool = False) -> list[tuple[int, float, float]]:
    """Recurrent jumps (acting_tick, dg, dh) for neuron 2."""
    w0 = -20.0 * w_syn
    w1 = 20.0 * w_syn
    if flipped:
        w0, w1 = -w0, -w1
    a0 = _018_acting(s0, dt_ms, t_dly)
    a1 = _018_acting(s1, dt_ms, t_dly)
    jumps: list[tuple[int, float, float]] = []
    for acting, w in list(zip(a0, [w0] * len(a0))) + list(zip(a1, [w1] * len(a1))):
        if E_inh is None:
            jumps.append((int(acting), float(w), 0.0))
        elif w > 0:
            jumps.append((int(acting), float(w), 0.0))
        elif w < 0:
            jumps.append((int(acting), 0.0, float(-w / (v_0 - E_inh))))
    return jumps


def measure_0_18() -> dict[str, Any]:
    """0.18: conductance-based inhibition against DOP853 and the 0.1 kernel."""
    from flyonenomics.drive.rest_tier3 import cbi_stiff

    constants = _018_params()
    dt = 0.1
    n_ticks = int(round(1100.0 / dt))
    t0, t1 = _018_ticks(dt)
    s0 = _018_driver_spikes(t0, dt, n_ticks)
    s1 = _018_driver_spikes(t1, dt, n_ticks)
    one_each = int(s0.shape[0]) == int(t0.shape[0]) and int(s1.shape[0]) == int(t1.shape[0])
    got_a = _run_018()
    spikes_a = np.array_equal(got_a["spike_0"], s0) and np.array_equal(got_a["spike_1"], s1)
    jumps_lif = _018_jumps(s0, s1, dt_ms=dt, t_dly=constants["t_dly"], w_syn=constants["w_syn"], E_inh=None, v_0=constants["v_0"])
    v_lif = _018_lif_v(
        got_a["tick"], [(a, dg) for a, dg, _dh in jumps_lif],
        v_0=constants["v_0"], t_mbr=constants["t_mbr"], tau=constants["tau"], dt_ms=dt,
    )
    err_a = _compare_016_trace(got_a["v_mv"], v_lif)
    min_gap_a = float(np.min(constants["v_th"] - v_lif))
    a_ok = bool(
        got_a["engine_model"] == "lif"
        and spikes_a
        and one_each
        and err_a <= 1e-9
        and min_gap_a >= 1.0
    )
    settings = [-72.0, -62.0, -57.0]
    b_rows: list[dict[str, Any]] = []
    for e_inh in settings:
        got = _run_018(mechanisms=_cbi_mechanisms(e_inh))
        v_ref, h_ref = _018_dop853(
            E_inh=e_inh, v_0=constants["v_0"], t_mbr=constants["t_mbr"], tau=constants["tau"],
            dt_ms=dt, n_ticks=n_ticks,
            jumps=_018_jumps(s0, s1, dt_ms=dt, t_dly=constants["t_dly"], w_syn=constants["w_syn"], E_inh=e_inh, v_0=constants["v_0"]),
            sample=got["tick"],
        )
        err_v = _compare_016_trace(got["v_mv"], v_ref)
        err_v_abs = float(np.max(np.abs(got["v_mv"] - v_ref)))
        scale_h = np.maximum(np.abs(h_ref), 1.0)
        err_h = float(np.max(np.abs(got["h_inh"] - h_ref) / scale_h)) if got["h_inh"] is not None else 1.0
        max_dv = float(np.max(np.abs(got["v_mv"] - v_lif)))
        min_gap = float(np.min(constants["v_th"] - v_ref))
        drivers_ok = np.array_equal(got["spike_0"], s0) and np.array_equal(got["spike_1"], s1)
        passed = bool(
            got["engine_model"] == "lif+cbi"
            and got["method"] == "rk4"
            and drivers_ok
            and err_v <= 1e-6
            and err_h <= 1e-6
            and max_dv > 0.02
            and min_gap >= 1.0
        )
        b_rows.append({
            "passed": passed, "E_inh_mv": e_inh, "err_v": err_v, "err_v_abs": err_v_abs, "err_h": err_h,
            "max_dv_vs_lif": max_dv, "min_gap_to_threshold_mv": min_gap,
            "engine_model": got["engine_model"], "method": got["method"],
            "drivers_ok": drivers_ok,
        })
    dt_fine = 0.05
    n_fine = int(round(1100.0 / dt_fine))
    t0f, t1f = _018_ticks(dt_fine)
    s0f = _018_driver_spikes(t0f, dt_fine, n_fine)
    s1f = _018_driver_spikes(t1f, dt_fine, n_fine)
    got_c = _run_018(mechanisms=_cbi_mechanisms(-57.0), dt_ms=dt_fine)
    v_ref_c, _h_c = _018_dop853(
        E_inh=-57.0, v_0=constants["v_0"], t_mbr=constants["t_mbr"], tau=constants["tau"],
        dt_ms=dt_fine, n_ticks=n_fine,
        jumps=_018_jumps(s0f, s1f, dt_ms=dt_fine, t_dly=constants["t_dly"], w_syn=constants["w_syn"], E_inh=-57.0, v_0=constants["v_0"]),
        sample=got_c["tick"],
    )
    err_c = float(np.max(np.abs(got_c["v_mv"] - v_ref_c)))
    err_b_abs = next(row["err_v_abs"] for row in b_rows if row["E_inh_mv"] == -57.0)
    c_ok = bool(err_b_abs < 1e-10 or err_c <= err_b_abs / 8.0)
    # (d) one event from neuron 0, neuron 1 silent, E_inh -62.
    e_d = -62.0
    one0 = t0[:1]
    empty1 = np.zeros(0, dtype=np.int64)
    s0_one = _018_driver_spikes(one0, dt, n_ticks)
    got_d = _run_018(mechanisms=_cbi_mechanisms(e_d), events0=one0, events1=empty1)
    acting = int(_018_acting(s0_one, dt, constants["t_dly"])[0])
    h0 = 20.0 * constants["w_syn"] / (constants["v_0"] - e_d)
    time_ms = got_d["tick"].astype(np.float64) * dt
    t_act = acting * dt
    mask = time_ms >= t_act - 1e-12
    h_exp = np.zeros_like(time_ms)
    h_exp[mask] = h0 * np.exp(-(time_ms[mask] - t_act) / constants["tau"])
    err_h_d = float(np.max(np.abs(got_d["h_inh"][mask] - h_exp[mask]))) if got_d["h_inh"] is not None else 1.0
    v_ref_d, h_ref_d = _018_dop853(
        E_inh=e_d, v_0=constants["v_0"], t_mbr=constants["t_mbr"], tau=constants["tau"],
        dt_ms=dt, n_ticks=n_ticks,
        jumps=_018_jumps(s0_one, empty1, dt_ms=dt, t_dly=constants["t_dly"], w_syn=constants["w_syn"], E_inh=e_d, v_0=constants["v_0"]),
        sample=got_d["tick"],
    )
    err_v_d = _compare_016_trace(got_d["v_mv"], v_ref_d)
    d_ok = bool(err_h_d <= 1e-6 and err_v_d <= 1e-6)
    one1 = t1[:1]
    s1_one = _018_driver_spikes(one1, dt, n_ticks)
    got_d_flip = _run_018(
        mechanisms=_cbi_mechanisms(e_d), events0=one0, events1=one1,
        scale=np.array([-1.0, -1.0], dtype=np.float32),
    )
    v_flip, h_flip = _018_dop853(
        E_inh=e_d, v_0=constants["v_0"], t_mbr=constants["t_mbr"], tau=constants["tau"],
        dt_ms=dt, n_ticks=n_ticks,
        jumps=_018_jumps(s0_one, s1_one, dt_ms=dt, t_dly=constants["t_dly"], w_syn=constants["w_syn"], E_inh=e_d, v_0=constants["v_0"], flipped=True),
        sample=got_d_flip["tick"],
    )
    err_flip_v = _compare_016_trace(got_d_flip["v_mv"], v_flip)
    scale_hf = np.maximum(np.abs(h_flip), 1.0)
    err_flip_h = float(np.max(np.abs(got_d_flip["h_inh"] - h_flip) / scale_hf)) if got_d_flip["h_inh"] is not None else 1.0
    flip_drivers = np.array_equal(got_d_flip["spike_0"], s0_one) and np.array_equal(got_d_flip["spike_1"], s1_one)
    d_flip_ok = bool(
        err_flip_v <= 1e-6
        and err_flip_h <= 1e-6
        and float(np.max(np.abs(h_flip))) > 1e-6
        and flip_drivers
    )
    e_ok = bool(cbi_stiff(19.1) and not cbi_stiff(18.9) and not cbi_stiff(19.0))
    passed = bool(
        a_ok
        and all(row["passed"] for row in b_rows)
        and c_ok
        and d_ok
        and d_flip_ok
        and e_ok
    )
    return {
        "passed": passed,
        "a": {"passed": a_ok, "err_v": err_a, "min_gap_to_threshold_mv": min_gap_a, "spikes_ok": spikes_a, "one_per_event": one_each, "engine_model": got_a["engine_model"]},
        "b": b_rows,
        "c": {"passed": c_ok, "err_0.05": err_c, "err_0.1": err_b_abs},
        "d": {"passed": d_ok and d_flip_ok, "err_h": err_h_d, "err_v": err_v_d, "err_flip_v": err_flip_v, "err_flip_h": err_flip_h},
        "e": {"passed": e_ok},
    }


def check_0_18() -> dict[str, Any]:
    """Run 0.18 in a fresh process."""
    return run_isolated("measure_0_18", timeout_s=600)


def test_0_18() -> ValidationEntry:
    """Conductance-based inhibition against a high-accuracy reference (SPEC-P2 5.3)."""
    result = check_0_18()
    identity = build_identity(
        REPO,
        connectome_version="630",
        layers=LayerFlags(),
        assay="conductance_inhibition",
        fixture=FIXTURE_0_18,
        declared_inputs=[
            FIXTURE_0_18,
            "tests/fixtures/engine/tiny_cbi_completeness.csv",
            "tests/fixtures/engine/tiny_cbi_connectivity.parquet",
            "data/params-v0.1.yaml",
        ],
    )
    return ValidationEntry(
        test_id="0.18",
        category="verification",
        outcome="passed" if result["passed"] else "failed",
        compatibility="canonical",
        identity=identity,
        measured={"0.18": result},
        fixture_path=FIXTURE_0_18,
        declared_inputs=list(identity.inputs),
    )


SUITE = {"0.15": test_0_15, "0.16": test_0_16, "0.17": test_0_17, "0.18": test_0_18}


if __name__ == "__main__":
    include_full = "--tiny" not in sys.argv
    payload = record_off_reference(include_full=include_full)
    print(json.dumps({"wrote": str(OFF_REFERENCE), "keys": list(payload.keys())}, indent=2))
