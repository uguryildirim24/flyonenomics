"""Parent-only validation, lifecycle, worker coordination and manifest finalisation."""
from __future__ import annotations
import dataclasses
import datetime as dt
import importlib
import itertools
import json
import queue
import os
from pathlib import Path
import time
import traceback
from typing import Any
import numpy as np
from flyonenomics.orchestrator.budget import lease_workers
from flyonenomics.orchestrator.phases import build_topology
from flyonenomics.orchestrator.seeds import ANALYSIS, stream
from flyonenomics.orchestrator.components import active_stubs
from flyonenomics.neuromod.pools import tonic_source
from flyonenomics.orchestrator.workers import (
    RegistrySnapshot, WorkerContext, load_registry_share, registry_share_key, save_registry_share, settle_rule,
    spawn_context, worker_main,
)
from flyonenomics.schema.experiment import Experiment, Dose, Probe, Repeat, ScaleDat, ScaleReceptor, ScaleRelease
from flyonenomics.io import read_yaml
from flyonenomics.store.results import ResultsStore, atomic_json, read_json
from flyonenomics.types import Params, is_rest_drive, load_params, isolated_param_overrides, params_path_for_version
from flyonenomics.validation.binding import ValidationEntry, binding_of, build_identity, identity_hash, sha256_file, sha256_text

REPO = Path(__file__).resolve().parents[3]
QUEUE_POLL_S = 0.2
WORKER_JOIN_S = 5
BOOTSTRAP_INTERVAL = (0.025, 0.975)
RUN_HASH_LENGTH = 8
MS_PER_SECOND = 1000
TIMESTAMP_FORMAT = "%Y%m%dT%H%M%S.%fZ"
# Params-backed free rows consumed by WP7; the drive ratio is resolved per run.
FREE_PARAMETER_KEYS = ("lif.w_syn", "pk.kappa")


def pinned_drive_ratio(experiment: Experiment, root: Path = REPO) -> float:
    """Return pinned inhibitory magnitude ratio, or bare-model 1; dimensionless scalar."""
    if not experiment.layers.background:
        return 1.0
    version = experiment.substrate.drive_version
    if not version:
        return 1.0
    if is_rest_drive(version):
        return 1.0  # drive-v0.2 carries g_glu and g_gaba, not the v0.1 ratio.
    path = root / "data" / f"drive-{version}.yaml"
    if not path.is_file():
        return 1.0
    from flyonenomics.drive.background import load_drive
    return load_drive(path).g_inh


def _free_parameters(params: Params, experiment: Experiment) -> dict[str, float]:
    """Report free magnitudes and PK ratio; mV/dimensionless scalar mapping."""
    return {**{key: float(params.get(key)) for key in FREE_PARAMETER_KEYS},
            **{key: float(params.get(key)) for key in isolated_param_overrides()},
            "lif.g_inh": pinned_drive_ratio(experiment)}


def background_weights(registry: Any, experiment: Experiment, root: Path = REPO) -> np.ndarray | None:
    """Lazily load optional drive weights; mV array (n,) or no background object."""
    if not experiment.layers.background:
        return None
    module_name = "flyonenomics.drive.background"
    version = experiment.substrate.drive_version
    if not version:
        return None
    path = root / "data" / f"drive-{version}.yaml"
    message = f"background requested: requires {module_name} and {path}"
    try:
        module = importlib.import_module(module_name)
    except ModuleNotFoundError as exc:
        raise RuntimeError(message) from exc
    if not path.is_file():
        raise RuntimeError(message)
    if is_rest_drive(version):
        from flyonenomics.drive.rest import load_drive_rest, rest_background_weights
        params = load_params(params_path_for_version(experiment.substrate.params_version))
        weights = rest_background_weights(registry, load_drive_rest(path), params)
    else:
        weights = np.asarray(module.background_weights(registry, read_yaml(path)), dtype=np.float64)
    if weights.shape != (registry.n,) or not np.all(np.isfinite(weights)):
        raise ValueError("background_weights must return finite (n,) mV weights")
    return weights


def aggregate(experiment: Experiment, results: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate seed metrics and paired bootstrap intervals; Hz/counts, vectors (n_seed,)."""
    params = load_params()
    by_arm: dict[str, dict[int, dict[str, float]]] = {}
    for result in results:
        flat: dict[str, float] = {}
        for probe, values in result["metrics"]["probes"].items():
            for key, value in values.get("behaviour", {}).items():
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    flat[f"probe-{probe}.behaviour.{key}"] = value
            for population, metric in values["populations"].items():
                if metric["mean_rate_hz"] is not None:
                    flat[f"probe-{probe}.{population}.mean_rate_hz"] = metric["mean_rate_hz"]
            if "MN9" in values and values["MN9"]["mean_rate_hz"] is not None:
                flat[f"probe-{probe}.MN9.mean_rate_hz"] = values["MN9"]["mean_rate_hz"]
            for key in ("mean_per_1ms", "max_per_1ms"):
                if values["popcount"][key] is not None:
                    flat[f"probe-{probe}.popcount.{key}"] = values["popcount"][key]
        by_arm.setdefault(result["arm"], {})[result["seed"]] = flat
    output: dict[str, Any] = {"arms": {}, "paired_differences": {},
                              "free_parameters": _free_parameters(params, experiment),
                              "calibration_limits": calibration_limits(params)}
    for label in sorted(by_arm):
        seeds = by_arm[label]
        keys = sorted({key for values in seeds.values() for key in values})
        summary = {}
        for key in keys:
            values = np.array([seeds[s][key] for s in sorted(seeds) if key in seeds[s]])
            summary[key] = {"mean": float(values.mean()), "sd": float(values.std(ddof=1)) if len(values) > 1 else 0.0, "n": len(values)}
        output["arms"][label] = {"per_seed": [{"seed": seed, **seeds[seed]} for seed in sorted(seeds)], "summary": summary}
    # Label and metric sorting makes analysis consumption invariant to arm order.
    for left, right in itertools.combinations(sorted(by_arm), 2):
        pair = {}
        common_seeds = sorted(set(by_arm[left]) & set(by_arm[right]))
        keys = sorted(set(output["arms"][left]["summary"]) & set(output["arms"][right]["summary"]))
        rng = stream(experiment.seed, 0, 0, ANALYSIS)
        for key in keys:
            ids = [s for s in common_seeds if key in by_arm[left][s] and key in by_arm[right][s]]
            values = np.array([by_arm[right][s][key] - by_arm[left][s][key] for s in ids])
            if not len(values):
                continue
            resamples = rng.choice(values, size=(params.get("stats.bootstrap_n"), len(values)), replace=True).mean(axis=1)
            pair[key] = {"mean": float(values.mean()), "sd": float(values.std(ddof=1)) if len(values) > 1 else 0.0,
                         "n": len(values), "seeds": ids, "per_seed": values.tolist(),
                         "ci95": np.quantile(resamples, BOOTSTRAP_INTERVAL).tolist()}
        output["paired_differences"][f"{right}-minus-{left}"] = pair
    if any(isinstance(p, Dose) and p.drug != "vehicle" for arm in experiment.arms for p in arm.expanded()):
        output["slow_state"] = "phase1-drug-only"
    if any(isinstance(p, Repeat) for arm in experiment.arms for p in arm.protocol):
        output["repeat_note"] = "pharmacokinetic differences only; no neural memory across iterations"
    if any(not experiment.arm_layers(arm).dopamine_A for arm in experiment.arms):
        output["layer_note"] = "dopamine_A off: this is not the wild-type calibration state"
    return output


def calibration_limits(params: Params) -> dict[str, Any]:
    """Name Phase 1 placeholder phasic release and deferred targets; alpha in µM/weighted spike."""
    return {"phasic_release": "alpha_max placeholder; bare K2 has zero tonic DAN rate",
            "da.alpha_max": params.get("da.alpha_max"), "alpha_unit": "µM per weighted DAN spike",
            "background_targets": "deferred on the canonical bare substrate (item 47)"}


WALL_MISMATCH_FRACTION = 0.01  # item 71


def _wall_times(awake_s: float, real_s: float, build_s: float, aggregation_s: float,
                process_start_to_initial_store_s: float) -> dict[str, Any]:
    """Record awake and real elapsed wall time; seconds, named clocks, 1 percent flag."""
    return {"total_s": awake_s, "awake_s": awake_s, "real_s": real_s,
            "awake_clock": "time.monotonic", "real_clock": "time.time",
            "mismatch_gt_1pct": _wall_mismatch(awake_s, real_s),
            "max_worker_build_s": build_s, "process_start_to_initial_store_s": process_start_to_initial_store_s,
            "aggregation_s": aggregation_s}


def _wall_mismatch(awake_s: float, real_s: float) -> bool:
    """Item 71: real and awake wall time differ by more than 1 percent of awake time; seconds."""
    return abs(real_s - awake_s) > WALL_MISMATCH_FRACTION * max(awake_s, 1e-9)


def clause_1_wall(manifests: dict[str, dict[str, Any]], budget_one_run_s: float) -> dict[str, Any]:
    """Read section 1.3 clause 1 from run manifests keyed by run id; seconds, one row per run.

    Clause 1 reads awake time (`wall_times.total_s`). A run without a recorded
    real elapsed time, or whose real and awake times differ by more than 1
    percent, is flagged for re-execution (item 71) and clause 1 does not hold.
    """
    rows = []
    for run_id, manifest in manifests.items():
        wall = manifest["wall_times"]
        awake_s = float(wall["total_s"])
        real_s = wall.get("real_s")
        mismatch = True if real_s is None else _wall_mismatch(awake_s, float(real_s))
        rows.append({"run_id": run_id, "awake_s": awake_s, "real_s": real_s,
                     "mismatch_gt_1pct": mismatch, "within_budget": awake_s <= budget_one_run_s})
    rerun = [row["run_id"] for row in rows if row["mismatch_gt_1pct"]]
    holds = bool(rows) and not rerun and all(row["within_budget"] for row in rows)
    return {"budget_one_run_s": budget_one_run_s, "runs": rows, "rerun_for_clause_1": rerun, "holds": holds}


def rest_drive_applied(experiment: Experiment) -> bool:
    """Whether a drive-v0.2 configuration acts on this run (SPEC-P2 sections 2.1, 8.1). Units: none."""
    if not is_rest_drive(experiment.substrate.drive_version):
        return False
    return bool(experiment.layers.background or experiment.apply_scales_without_background)


def substrate_id_of(experiment: Experiment, root: Path = REPO) -> str:
    """Return bare or rest:<16 hex> from the drive file SHA-256. Units: none.

    The section 8.1 scales-only fixture runs a scaled substrate, so it is
    not bare either. With a mechanism on, the tag is rest-<tag>:.
    """
    if not rest_drive_applied(experiment):
        return "bare"
    path = root / "data" / f"drive-{experiment.substrate.drive_version}.yaml"
    if not path.is_file():
        raise RuntimeError(f"rest substrate requested: missing pin {path.name}")
    from flyonenomics.drive.mechanisms import substrate_id_for

    return substrate_id_for(path)


# Section 5.2 rows that qualify each v0.2 configuration file.
QUALIFYING_COMPONENT = {"drive": "rest substrate", "dopamine": "neuromodulation"}


def _qualified(component: str, version: str | None, record: dict[str, Any], identity: Any) -> tuple[bool, dict[str, str] | None]:
    """v0.1 and dev files keep their flag; v0.2 files ask qualification_of (SPEC-P2 5.1)."""
    if not is_rest_drive(version):
        return bool(record.get("qualified", False)), None
    from flyonenomics.validation.binding import qualification_of
    status_path = REPO / "validation/status.json"
    results = ([ValidationEntry.model_validate(raw) for raw in read_json(status_path).get("results", [])]
               if status_path.exists() else [])
    qualified, reasons = qualification_of(QUALIFYING_COMPONENT[component], identity, results=results, repo=REPO)
    return qualified, reasons


def _manifest(experiment: Experiment, registry: RegistrySnapshot, results: list[dict[str, Any]], state: str, wall_s: float, build_s: float, aggregation_s: float, resolved: dict[str, list[int]], *, behaviour_settings: dict[str, float | int] | None = None, process_start_to_initial_store_s: float = 0, wall_real_s: float | None = None, launch: dict[str, str] | None = None) -> dict[str, Any]:
    params = load_params(params_path_for_version(experiment.substrate.params_version))
    parameter_overrides = isolated_param_overrides()
    dopamine_path = REPO / "data" / f"dopamine-{experiment.substrate.dopamine_version}.yaml"
    dopamine_record = read_yaml(dopamine_path) if dopamine_path.is_file() else {}
    assays = sorted({p.assay for arm in experiment.arms for p in arm.expanded() if isinstance(p, Probe)})
    substrate_id = substrate_id_of(experiment)
    launch = launch or {}
    # SPEC-P2 5.1: run_code_scope and run_code_hash are the hashes taken at launch.
    identity = build_identity(REPO, connectome_version=experiment.substrate.connectome_version, layers=experiment.layers,
                              assay=",".join(assays), protocol_hash=experiment.protocol_hash(),
                              run_code_hash=launch.get("code_hash"), run_code_scope=launch.get("code_scope"),
                              substrate_id=substrate_id,
                              engine_model=launch.get("engine_model", "lif"),
                              mechanisms=launch.get("mechanisms"))
    qualification: dict[str, dict[str, str]] = {}
    dopamine_qualified, reasons = _qualified("dopamine", experiment.substrate.dopamine_version, dopamine_record, identity)
    if reasons is not None:
        qualification["dopamine"] = reasons
    refs = []
    artefacts: dict[str, Any] = {"fano": "not run", "jitter": "not run", "permutation": "not run", "completeness": "unknown", "labels": "unknown"}
    status_path = REPO / "validation/status.json"
    if status_path.exists():
        for raw in read_json(status_path).get("results", []):
            entry = ValidationEntry.model_validate(raw)
            if entry.compatibility == "development":
                continue  # Development entries remain in status, but can never bind to a run.
            arm_bindings = {arm.label: binding_of(entry, identity.model_copy(update={
                "layer_flags": dataclasses.asdict(experiment.arm_layers(arm))}), repo=REPO) for arm in experiment.arms}
            refs.append({"test_id": entry.test_id, "identity_hash": identity_hash(entry.identity),
                         "binding": "valid" if all(value == "valid" for value in arm_bindings.values()) else "stale",
                         "arm_bindings": arm_bindings, "outcome": entry.outcome})
            if "completeness" in entry.test_id:
                artefacts["completeness"] = {"outcome": entry.outcome, "measured": entry.measured, "binding": refs[-1]["binding"]}
            if "label" in entry.test_id:
                artefacts["labels"] = {"outcome": entry.outcome, "measured": entry.measured, "binding": refs[-1]["binding"]}
    offsets = sorted([p for result in results for p in result["offsets"]], key=lambda p: (p["arm"], p["seed"], p["probe"]))
    ignored: list[dict[str, Any]] = []
    notes = ["Drug concentrations are held within probes and analytically advanced after settle plus recording; only drug state carries between phases."]
    if not dopamine_qualified:
        notes.append("Dopamine calibration is unqualified; this execution is development evidence only.")
    if any(isinstance(p, Repeat) for arm in experiment.arms for p in arm.protocol):
        notes.append("repeat shows pharmacokinetic differences only; no neural memory carries between iterations")
    if any(not experiment.arm_layers(arm).dopamine_A for arm in experiment.arms):
        notes.append("dopamine_A off: this is not the wild-type calibration state")
    checksum_paths = {p for p in (REPO / "data").glob("*-v0.1.yaml")
                      if not p.name.startswith("drive-")}
    drive_path = None
    if (experiment.layers.background or rest_drive_applied(experiment)) and experiment.substrate.drive_version:
        drive_path = REPO / "data" / f"drive-{experiment.substrate.drive_version}.yaml"
        checksum_paths.add(drive_path)
    if any(assay in ("buridan", "open_loop_steering") for assay in assays):
        behaviour_path = REPO / "data" / f"behaviour-{experiment.substrate.behaviour_version}.yaml"
        if behaviour_path.exists():
            checksum_paths.add(behaviour_path)
    # Preserve the pinned source-file hashes, not only the hash of the
    # provenance index. Loaders verify the files they consume against these.
    checksums = {record["path"] or record["item"]: record["sha256"]
                 for record in read_json(REPO / "data/provenance.json")["records"]
                 if record.get("sha256") is not None}
    checksums.update({p.name: sha256_file(p) for p in sorted(checksum_paths)})
    drive_calibration = {}
    drive_qualified = True
    if rest_drive_applied(experiment):
        from flyonenomics.drive.rest import load_drive_rest
        drive_rest = load_drive_rest(drive_path)
        drive_qualified, reasons = _qualified("drive", experiment.substrate.drive_version, {}, identity)
        qualification["drive"] = reasons or {}
        drive_calibration = {"drive_calibration": {
            "configuration_class": "rest", "qualified": drive_qualified,
            "scales": {key: drive_rest[key] for key in ("g_glu", "g_gaba", "g_his", "optic_exemption", "sigma_th", "scope")},
            "applied": "scales and background" if experiment.layers.background else "scales only (section 8.1 fixture)"}}
    elif experiment.layers.background and drive_path is not None and drive_path.is_file():
        from flyonenomics.drive.background import load_drive
        drive = load_drive(drive_path)
        drive_record = drive.model_dump() if hasattr(drive, "model_dump") else {"qualified": drive.qualified}
        drive_qualified, _reasons = _qualified("drive", experiment.substrate.drive_version, drive_record, identity)
        drive_calibration = {"drive_calibration": {"configuration_class": drive.configuration_class,
            "qualified": drive_qualified, "state": drive.calibration_state}}
    stubs = active_stubs(assays)
    innervation = registry.innervation() if hasattr(registry, "innervation") else None
    uninnervated = ([comp.name for comp, present in zip(registry.compartments(), np.asarray(innervation.getnnz(axis=1) > 0), strict=True) if not present]
                   if innervation is not None else [])
    if innervation is not None:
        innervated = np.asarray(innervation.getnnz(axis=1) > 0, dtype=bool)
        source = tonic_source(float(params.get("da.DA_ref")),
                              np.full(len(innervated), float(params.get("da.Vmax"))),
                              np.full(len(innervated), float(params.get("da.Km"))),
                              float(params.get("da.k_ns")), innervated).tolist()
    else:
        source = dopamine_record.get("da.tonic_source", [])
    identity_dump = identity.model_dump()
    da_exposed = None
    if hasattr(registry, "selected") and "DA_exposed" in registry.selected:
        from flyonenomics.registry.derived import root_ids_sha256
        pop = registry.selected["DA_exposed"]
        da_exposed = {"size": int(pop.count), "root_ids_sha256": root_ids_sha256(pop.root_ids)}
    elif hasattr(registry, "population"):
        try:
            from flyonenomics.registry.derived import root_ids_sha256
            pop = registry.population("DA_exposed")
            da_exposed = {"size": int(pop.count), "root_ids_sha256": root_ids_sha256(pop.root_ids)}
        except (KeyError, ValueError):
            da_exposed = None
    return {"state": state, "identity": identity_dump, "substrate_id": substrate_id,
            "engine_model": identity.engine_model, "mechanisms": identity.mechanisms,
            **({"parameter_overrides": parameter_overrides,
                "parameter_override_sha256": sha256_text(json.dumps(parameter_overrides, sort_keys=True))}
               if parameter_overrides else {}),
            "compatibility": "development" if stubs or not dopamine_qualified or not drive_qualified else "matching-layers", "stubs": stubs,
            **drive_calibration,
            **({"behaviour_settings": behaviour_settings} if behaviour_settings is not None else {}),
            "versions": experiment.substrate.model_dump(), "checksums": checksums,
            "uv_lock_hash": identity.uv_lock_hash, "provenance_hash": identity.provenance_hash, "code_commit": identity.code_commit,
            "protocol_hash": experiment.protocol_hash(), "seed_derivation": "SeedSequence(S, spawn_key=(s,k,component)); arms omitted; ANALYSIS k=0,s=0",
            "slow_state": "phase1-drug-only", "layers": dataclasses.asdict(experiment.layers),
            "arm_layers": {arm.label: dataclasses.asdict(experiment.arm_layers(arm)) for arm in experiment.arms},
            "free_parameters": {**_free_parameters(params, experiment), "rec.formulation": params.get("rec.formulation"),
                                "receptor_map_version": experiment.substrate.receptor_map_version,
                                "dopamine_version": experiment.substrate.dopamine_version, "drive_version": experiment.substrate.drive_version,
                                "da.tonic_source": source},
            "calibration_limits": calibration_limits(params),
            "da.tonic_source": source, "tonic_source_rule": "provisional item 24 / SPEC item 51",
            "formulation": params.get("rec.formulation"),
            "dopamine_qualified": dopamine_qualified, "uninnervated_compartments": uninnervated,
            **({"qualification": qualification} if qualification else {}),
            "validation": refs, "artefacts": artefacts, "artefact_flags": [], "unsettled": [p for p in offsets if not p["converged"]],
            "unmapped": registry.provenance_record, "wall_times": _wall_times(
                wall_s, wall_s if wall_real_s is None else wall_real_s, build_s, aggregation_s,
                process_start_to_initial_store_s),
            "benchmark q2 used": "none (WP9)", "probe_offsets": offsets, "compartments": [c.name for c in registry.compartments()],
            "resolved_populations": resolved, "schema_warnings": experiment._warnings,
            "not_applied": ignored, "notes": notes, "dt_ms": params.get("lif.dt"),
            **({"DA_exposed": da_exposed} if da_exposed is not None else {})}


def make_run_id(experiment: Experiment, created: str | None = None) -> str:
    """Name a resolved experiment using the store clock/hash convention; one run ID."""
    timestamp = created if created is not None else dt.datetime.now(dt.timezone.utc).strftime(TIMESTAMP_FORMAT)
    return f"{timestamp}-{experiment.protocol_hash()[:RUN_HASH_LENGTH]}"


def run(experiment: Experiment, store: ResultsStore, n_workers: int | str | None = None, *, fixture_settle_s: dict[int, float] | None = None, run_id: str | None = None) -> str:
    """Run an experiment using spawned workers; return run ID, times in brain/wall seconds.

    fixture_settle_s is a Python-only stub test seam keyed by expanded phase index;
    it is never accepted as an experiment schema field or command-line option.
    run_id is an optional preassigned run identifier (WP7 tool server); when given,
    the runner reuses it and the queued index insert stays idempotent via upsert.
    """
    from flyonenomics.registry import build_registry
    # Revalidate copies so model_copy cannot bypass matched-arm checks.
    experiment = Experiment.model_validate(experiment.model_dump(mode="json"))
    from flyonenomics.validation.binding import code_content_hash, code_scope_hash
    launch = {"code_hash": code_content_hash(REPO), "code_scope": code_scope_hash(REPO)}
    pins = experiment.substrate
    params = load_params(params_path_for_version(pins.params_version))
    if fixture_settle_s is not None:
        for duration in fixture_settle_s.values():
            if not np.isfinite(duration) or duration < 0 or not np.isclose(duration * MS_PER_SECOND / params.get("engine.chunk_ms"), round(duration * MS_PER_SECOND / params.get("engine.chunk_ms"))):
                raise ValueError("fixture settle duration must be a nonnegative chunk multiple")
    pins = experiment.substrate
    if pins.connectome_version == "630":
        raise ValueError("SPEC section 11 item 22: v630 orchestrator support is deferred; use the bare reproduction suites")
    if any(isinstance(p, Probe) and p.assay in ("buridan", "open_loop_steering")
           for arm in experiment.arms for p in arm.expanded()):
        required = [REPO / "data" / f"behaviour-{pins.behaviour_version}.yaml"]
        if experiment.layers.background and pins.drive_version:
            required.append(REPO / "data" / f"drive-{pins.drive_version}.yaml")
        missing = [path.name for path in required if not path.is_file()]
        if missing:
            raise ValueError("behaviour experiment unavailable: missing pins " + ", ".join(missing))
    if rest_drive_applied(experiment) and not (REPO / "data" / f"drive-{pins.drive_version}.yaml").is_file():
        raise ValueError(f"rest substrate unavailable: missing pin drive-{pins.drive_version}.yaml")
    for name, expected in (("annotation_version", "v2.1.0"), ("receptor_map_version", "v0.1"), ("params_version", params.version)):
        if getattr(pins, name) != expected:
            raise ValueError(f"unavailable {name}: {getattr(pins, name)}")
    from flyonenomics.connectome_arrays import ensure_connectome_for_version
    ensure_connectome_for_version(pins.connectome_version, float(params.get("lif.w_syn")))
    pop_path = None
    if pins.populations_version and pins.populations_version != "v0.1":
        pop_path = REPO / "data" / f"populations-{pins.populations_version}.yaml"
    if pop_path is None:
        registry_full = build_registry(pins.connectome_version)
    else:
        registry_full = build_registry(pins.connectome_version, populations_path=pop_path)
    resolved = experiment.resolve(registry_full)
    visual = None
    if pins.visual_version:
        from flyonenomics.drive.rest import load_visual_v02
        visual_path = REPO / "data" / f"visual-{pins.visual_version}.yaml"
        meta = experiment.meta if isinstance(experiment.meta, dict) and experiment.meta.get("encoder_grid") else None
        visual = load_visual_v02(visual_path if visual_path.is_file() else None, params, meta=meta)
    plan = build_topology(experiment, registry_full, params=params, visual=visual)
    background = background_weights(registry_full, experiment)
    registry = RegistrySnapshot(registry_full.root_ids, {name: registry_full.population(name) for name in registry_full.populations()},
                                registry_full.compartments(), registry_full.provenance(), registry_full.exposure(),
                                registry_full.innervation(), registry_full.receptors())
    cache_override = os.environ.get("FLYONENOMICS_CACHE_DIR", "").strip()
    share_key = pins.connectome_version + "-" + registry_share_key(registry)[:24]
    share_dir = (Path(cache_override) if cache_override else REPO / ".cache") / "registry-share" / share_key
    save_registry_share(registry, share_dir)
    registry = load_registry_share(share_dir)
    dopamine_path = REPO / "data" / f"dopamine-{pins.dopamine_version}.yaml"
    dopamine_table = read_yaml(dopamine_path) if dopamine_path.is_file() else {}
    if pins.dopamine_version not in ("v0.1", "dev"):
        # Section 8.1: R_c, alpha_c and S_c come from dopamine-v0.2.yaml in registry compartment order.
        from flyonenomics.drive.rest import load_dopamine_v02
        if not dopamine_path.is_file():
            raise ValueError(f"dopamine unavailable: missing pin {dopamine_path.name}")
        dopamine_table = load_dopamine_v02(dopamine_path, [c.name for c in registry_full.compartments()])
    drive_groups = None
    if settle_rule(experiment) == "1.3":
        from flyonenomics.drive.background import group_indices
        drive_groups = group_indices(registry_full)  # Section 2.4 decision candidates.
    del registry_full
    created = dt.datetime.now(dt.timezone.utc).strftime(TIMESTAMP_FORMAT)
    preassigned = run_id is not None
    if run_id is None:
        run_id = make_run_id(experiment, created)
    else:
        if Path(run_id).name != run_id or run_id in (".", ".."):
            raise ValueError("invalid run_id")
    directory = store.run_path(run_id)
    directory.mkdir(exist_ok=preassigned)
    atomic_json(directory / "experiment.json", experiment.model_dump(mode="json"))
    (directory / "log.txt").touch()
    started = time.monotonic()
    started_real = time.time()
    current: dict[str, Any] = {"run_id": run_id, "created": created, "pid": os.getpid()}

    def lifecycle(state: str, **fields: Any) -> None:
        """Atomically publish state and index row; seconds, scalar status fields."""
        current.update({"state": state, "wall_time_s": time.monotonic() - started, **fields})
        atomic_json(directory / "status.json", current)
        store.index.upsert(run_id, experiment.model_dump(mode="json"), current)

    lifecycle("queued")
    jobs = [(a, seed) for a in range(len(experiment.arms)) for seed in experiment.seeds]
    lease = lease_workers(n_workers, n_jobs=len(jobs))
    count = lease.count
    ctx = spawn_context()
    messages = ctx.Queue()
    context = WorkerContext(experiment, None, plan, directory, background,
                            fixture_settle_s, dopamine_table=dopamine_table,
                            g_inh=pinned_drive_ratio(experiment),
                            registry_share=str(share_dir), drive_groups=drive_groups)
    processes = [ctx.Process(target=worker_main, args=(context, jobs[i::count], messages)) for i in range(count)]
    results: list[dict[str, Any]] = []
    builds: list[float] = []
    process_builds: list[float] = []
    process_started: dict[int, float] = {}
    finished = 0
    try:
        lifecycle("building", n_workers=count)
        for process in processes:
            launched_at = time.monotonic()
            process.start()
            assert process.pid is not None
            process_started[process.pid] = launched_at
        current["worker_pids"] = [p.pid for p in processes]
        lifecycle("building", n_workers=count, worker_pids=current["worker_pids"])
        while finished < count:
            try:
                message = messages.get(timeout=QUEUE_POLL_S)
            except queue.Empty:
                dead = [p for p in processes if p.exitcode is not None and p.exitcode != 0]
                if dead:
                    raise RuntimeError(f"worker killed: {[(p.pid, p.exitcode) for p in dead]}")
                if all(p.exitcode is not None for p in processes):
                    raise RuntimeError("workers exited without complete result messages")
                continue
            event = message.pop("event")
            if event == "finished":
                finished += 1
            elif event == "built":
                builds.append(message["build_s"])
                process_builds.append(message["built_at"] - process_started[message["pid"]])
                if "engine_model" in message:
                    launch["engine_model"] = message["engine_model"]
                    launch["mechanisms"] = message.get("mechanisms")
            elif event == "phase":
                lifecycle("running", estimated_remaining_s=None, **message)
            elif event == "result":
                results.append(message)
            elif event == "error":
                raise RuntimeError(message["traceback"])
        for process in processes:
            process.join(WORKER_JOIN_S)
            if process.exitcode != 0:
                raise RuntimeError(f"worker failed: {process.pid}: {process.exitcode}")
        lifecycle("aggregating")
        aggregate_start = time.monotonic()
        metrics = aggregate(experiment, results)
        atomic_json(directory / "metrics.json", metrics)
        state = "cancelled" if (directory / "CANCEL").exists() or any(r["cancelled"] for r in results) else "done"
        if state == "done" and len(results) != len(jobs):
            raise RuntimeError("missing worker results")
        lifecycle(state)
        manifest = _manifest(experiment, registry, results, state, time.monotonic() - started,
                             max(builds, default=0), time.monotonic() - aggregate_start, resolved,
                             behaviour_settings=plan.behaviour_settings,
                             process_start_to_initial_store_s=max(process_builds, default=0),
                             wall_real_s=time.time() - started_real, launch=launch)
        if fixture_settle_s is not None:
            manifest["fixture_settle_s"] = fixture_settle_s
        atomic_json(directory / "manifest.json", manifest)  # Last run-file write.
        store.index.upsert(run_id, experiment.model_dump(mode="json"), current, metrics, manifest["artefact_flags"])
        return run_id
    except BaseException:
        lifecycle("failed", traceback=traceback.format_exc())
        raise
    finally:
        for process in processes:
            if process.pid is not None:
                if process.is_alive():
                    process.terminate()
                process.join(WORKER_JOIN_S)
        messages.close()
        messages.join_thread()
        lease.release()
