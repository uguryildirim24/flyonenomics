"""WP5 level-3 checks and typed status for the bare-substrate calibration."""
from __future__ import annotations

from typing import Any, Callable
from pathlib import Path
import json
import re

import numpy as np
from numpy.typing import NDArray

from flyonenomics.io import read_json, read_parquet, read_yaml
from flyonenomics.orchestrator.seeds import ANALYSIS, stream
from flyonenomics.types import LayerFlags, load_params
from flyonenomics.validation.binding import ValidationEntry, build_identity, sha256_file, sha256_text

REPO = Path(__file__).resolve().parents[3]
DOSE_FIXTURE = "data/experiments/dose-series.json"
ABLATION_FIXTURE = "data/experiments/ablation.json"
DEPLETION_FIXTURE = "data/experiments/depletion-3iy.json"
DESCENDING_FUMIN_FIXTURE = "data/experiments/descending-fumin.json"
DESCENDING_PAM_FIXTURE = "data/experiments/descending-pam.json"
# SPEC 7.2 test 3.8-dev: two shared seeds, bootstrap uncertainty over seeds.
ABLATION_SEEDS = (1, 2)
BOOTSTRAP_QUANTILES = (0.025, 0.975)
# SPEC 7.2 test 3.9: nine named parameter groups, each range endpoint and default.
SENSITIVITY_GROUPS: dict[str, tuple[str, ...]] = {
    "Kd_D1": ("rec.Kd_D1",), "Kd_D2": ("rec.Kd_D2",),
    "gamma_*": ("rec.gamma_D1", "rec.gamma_D2"),
    "dV_*": ("rec.dV_D1", "rec.dV_D2"),
    "Ki_mph": ("drug.mph.Ki",), "kappa": ("pk.kappa",),
    "Vmax": ("da.Vmax",), "Km": ("da.Km",), "k_ns": ("da.k_ns",),
}
RANGE_PATTERN = re.compile(r"^([0-9.eE+-]+) to ([0-9.eE+-]+)$")


def ablation_contrasts(cells: dict[tuple[bool, str, str], dict[int, float]],
                       seeds: tuple[int, ...], bootstrap_n: int, rng: np.random.Generator) -> dict[str, Any]:
    """Compute paired fumin-minus-WT 2×2 contrasts; each input is one metric in Hz or µM per seed."""
    diffs: dict[tuple[bool, str], NDArray[np.float64]] = {}
    for pools in (False, True):
        for fast in ("disconnect", "retain"):
            wt = cells[(pools, fast, "wt")]
            fumin = cells[(pools, fast, "fumin")]
            diffs[(pools, fast)] = np.array([fumin[s] - wt[s] for s in seeds], dtype=np.float64)
    def contrasts(d: dict[tuple[bool, str], NDArray[np.float64]]) -> dict[str, NDArray[np.float64]]:
        return {
            "pools-off-fast-disconnect": d[(False, "disconnect")],
            "pools-off-fast-retain": d[(False, "retain")],
            "pools-on-fast-disconnect": d[(True, "disconnect")],
            "pools-on-fast-retain": d[(True, "retain")],
            "pools_main": (d[(True, "disconnect")] + d[(True, "retain")] - d[(False, "disconnect")] - d[(False, "retain")]) / 2,
            "fast_main": (d[(False, "retain")] + d[(True, "retain")] - d[(False, "disconnect")] - d[(True, "disconnect")]) / 2,
            "interaction": d[(True, "retain")] - d[(False, "retain")] - d[(True, "disconnect")] + d[(False, "disconnect")],
        }
    observed = contrasts(diffs)
    if bootstrap_n < 1 or not seeds:
        raise ValueError("bootstrap requires at least one seed and one resample")
    indices = rng.integers(0, len(seeds), size=(bootstrap_n, len(seeds)))
    return {name: {"mean": float(values.mean()), "per_seed": values.tolist(),
                   "ci95": np.quantile(values[indices].mean(axis=1), BOOTSTRAP_QUANTILES).tolist()}
            for name, values in observed.items()}


def depletion_response(vehicle_um: dict[str, NDArray[np.float64]],
                       treated_um: dict[str, NDArray[np.float64]]) -> dict[str, Any]:
    """Check 3.5 settled DA falls after 3-IY in WT and fumin; input vectors (n_seed,) µM."""
    measured = {}
    for genotype in ("wild_type", "fumin"):
        baseline = np.asarray(vehicle_um[genotype], dtype=np.float64)
        drug = np.asarray(treated_um[genotype], dtype=np.float64)
        if baseline.shape != drug.shape or not baseline.size:
            raise ValueError("3.5 requires paired, nonempty seed vectors")
        measured[genotype] = {"vehicle_um": baseline.tolist(), "3iy_um": drug.tolist(),
                              "all_seeds_lower": bool(np.all(drug < baseline))}
    measured["passed"] = all(measured[name]["all_seeds_lower"] for name in ("wild_type", "fumin"))
    return measured


def paired_prediction(difference: NDArray[np.float64], bootstrap_n: int,
                      rng: np.random.Generator) -> dict[str, Any]:
    """Return 3.6 paired difference and seed-bootstrap interval; input Hz (n_seed,), output Hz."""
    values = np.asarray(difference, dtype=np.float64)
    if not values.size or bootstrap_n < 1:
        raise ValueError("prediction requires seeds and resamples")
    draws = rng.choice(values, size=(bootstrap_n, len(values)), replace=True).mean(axis=1)
    return {"mean_hz": float(values.mean()), "per_seed_hz": values.tolist(),
            "ci95_hz": np.quantile(draws, BOOTSTRAP_QUANTILES).tolist()}


def sensitivity_grid(params: Any) -> list[dict[str, Any]]:
    """Build 3.9 endpoint/default settings from parameter rows; 27 group settings, source units per key."""
    settings = []
    for group, keys in SENSITIVITY_GROUPS.items():
        bounds = {}
        for key in keys:
            row = params.row(key)
            match = RANGE_PATTERN.fullmatch(str(row["range"]))
            if match is None:
                raise ValueError(f"3.9 needs numeric range: {key}")
            bounds[key] = (float(match[1]), float(row["value"]), float(match[2]))
        for position, level in enumerate(("low", "default", "high")):
            settings.append({"group": group, "level": level,
                             "overrides": {key: values[position] for key, values in bounds.items()}})
    return settings


def _entry(test_id: str, category: str, outcome: str, measured: dict[str, Any],
           *, fixture: str = DOSE_FIXTURE, development: bool = False,
           provisional_name: str = "IdentityBehaviour", intended_class: str = "canonical",
           matching_layers: bool = False, run_manifest: dict[str, Any] | None = None) -> ValidationEntry:
    """Bind one level-3 result to current code/data and a fixture; measured units per field."""
    flags = LayerFlags(background=False)
    executed: str | None = None
    if run_manifest is not None:
        ident = run_manifest.get("identity") or {}
        executed = str(ident.get("code_hash") or "") if isinstance(ident, dict) else ""
    identity = build_identity(REPO, connectome_version="783", layers=flags,
                              assay="buridan" if matching_layers or fixture in
                              (DOSE_FIXTURE, DEPLETION_FIXTURE, DESCENDING_FUMIN_FIXTURE, DESCENDING_PAM_FIXTURE) else "spontaneous",
                              fixture=fixture, run_code_hash=executed)
    return ValidationEntry(test_id=test_id, category=category, outcome=outcome,
                           compatibility="development" if development else
                                         "matching-layers" if matching_layers else "canonical", identity=identity,
                           measured={"intended_class": intended_class, **measured} if development else measured,
                           data_dependencies=["params-v0.1.yaml", "receptors-v0.1.yaml", "dopamine-v0.1.yaml",
                                              "compartments-v0.1.yaml", "populations-v0.1.yaml"] +
                                             (["behaviour-v0.1.yaml"] if matching_layers or fixture in
                                               (DOSE_FIXTURE, DEPLETION_FIXTURE, DESCENDING_FUMIN_FIXTURE, DESCENDING_PAM_FIXTURE) else []),
                           fixture_path=fixture, stub=provisional_name if development else None)


def _completed_run(fixture: str, *, current_dopamine: bool = True,
                   allow_unsettled: bool = False) -> tuple[Path, dict[str, Any]] | None:
    """Find a complete protocol run; retain nonconverged data only for recorded entries."""
    from flyonenomics.schema import load_experiment
    expected = load_experiment(REPO / fixture).model_dump(mode="json")
    for run in sorted((REPO / "runs").glob("*/"), reverse=True):
        manifest_path = run / "manifest.json"
        experiment_path = run / "experiment.json"
        if not manifest_path.is_file() or not experiment_path.is_file():
            continue
        try:
            manifest = read_json(manifest_path)
            saved = read_json(experiment_path)
        except (OSError, ValueError):
            continue
        dopamine_hash = manifest.get("checksums", {}).get("dopamine-v0.1.yaml")
        if current_dopamine and dopamine_hash != sha256_file(REPO / "data/dopamine-v0.1.yaml"):
            continue
        required = ("params-v0.1.yaml", "receptors-v0.1.yaml", "compartments-v0.1.yaml", "populations-v0.1.yaml")
        if any(manifest.get("checksums", {}).get(name) != sha256_file(REPO / "data" / name)
               for name in required):
            continue
        if manifest.get("unsettled") and not allow_unsettled:
            continue
        saved.setdefault("meta", {}).pop("_resolved_populations", None)
        if manifest.get("state") == "done" and saved == expected:
            return run, manifest
    return None


def _mean_innervated_da(run: Path, manifest: dict[str, Any], arm: str, seed: int, probe: int) -> float:
    """Average recorded DA over chunks and innervated compartments; result µM, table (time,n_comp)."""
    return float(np.mean(list(_compartment_da(run, manifest, arm, seed, probe).values())))


def _compartment_da(run: Path, manifest: dict[str, Any], arm: str, seed: int, probe: int) -> dict[str, float]:
    """Return window-mean DA by innervated compartment; one µM scalar per name."""
    table = read_parquet(run / f"arm-{arm}" / f"seed-{seed}" / f"probe-{probe}-dopamine.parquet").to_pandas()
    uninnervated = set(manifest.get("uninnervated_compartments", []))
    columns = [name for name in manifest["compartments"] if name not in uninnervated]
    if not columns or table.empty:
        raise ValueError("no recorded innervated-compartment DA")
    return {name: float(table[name].mean()) for name in columns}


def _mean_rate(run: Path, arm: str, seed: int, probe: int, population: str) -> float:
    """Read one saved population mean rate; result Hz, scalar."""
    metrics = read_json(run / f"arm-{arm}" / f"seed-{seed}" / "metrics.json")
    return float(metrics["probes"][str(probe)]["populations"][population]["mean_rate_hz"])


def _pending(test_id: str, category: str) -> ValidationEntry:
    """Describe an unexecuted suite; no brain-time or array evidence is asserted."""
    if test_id == "3.1":
        reason = "requires bare-substrate K2"
    elif test_id == "3.1b":
        reason = "requires free-pool Q execution after K2"
    elif test_id == "3.5":
        reason = "paired 3 mM 3-iodotyrosine versus vehicle in WT and fumin was not run"
    elif test_id == "3.6":
        reason = "ten-seed DN_all fumin contrast and 50 Hz PAM activation protocol were not run"
    elif test_id == "3.9":
        reason = "27-setting, three-seed dose-series sensitivity sweep was not run within the WP5 long-run budget"
    else:
        reason = "requires qualified K2/Q and the dedicated bare-substrate protocol"
    builders = {"3.5": "depletion_protocol", "3.6": "prediction_protocols", "3.9": "sensitivity_protocols"}
    details = {"reason": reason}
    if test_id in builders:
        details["protocol_builder"] = "flyonenomics.neuromod.protocols." + builders[test_id]
    return _entry(test_id, category, "unavailable", details)


def test_3_1() -> ValidationEntry:
    """Report the K2 calibration record; rates Hz (n_comp,), alpha µM/spike (n_comp,)."""
    table = read_yaml(REPO / "data/dopamine-v0.1.yaml")
    if not table.get("R_c"):
        return _pending("3.1", "calibration")
    return _entry("3.1", "calibration", "recorded", {key: table[key] for key in ("R_c", "alpha_c", "under_innervated", "seeds", "qualified", "da.tonic_source")})


def test_3_1b() -> ValidationEntry:
    """Report free-pool chunkwise qualification; DA µM (n_comp,), modulation (n,)."""
    table = read_yaml(REPO / "data/dopamine-v0.1.yaml")
    qualification = table.get("qualification", {})
    check = qualification.get("3.1b")
    if not isinstance(check, dict):
        return _pending("3.1b", "consistency")
    return _entry("3.1b", "consistency", "passed" if check.get("passed") else "failed", check)


def test_3_7() -> ValidationEntry:
    """Verify constructed D1-null tonic algebra at 0, DA_ref and 5×DA_ref; mV/gain arrays (4,)."""
    from flyonenomics.neuromod.receptors import receptor_effect
    from flyonenomics.neuromod.state import Neuromod
    from flyonenomics.registry.receptors import ReceptorMap
    from scipy.sparse import csr_matrix
    from types import SimpleNamespace
    params = load_params()
    w = csr_matrix(np.array([[1, 0], [0, 1], [0, 0], [0.5, 0.5]], dtype=np.float32))
    exposed = np.array([True, True, False, True])
    r1 = np.array([1.0, 0.5, 1.0, 1.0])
    r2 = np.array([0.5, 1.0, 1.0, 0.0])
    errors: list[float] = []
    off_registry = SimpleNamespace(n=4, exposure=lambda: w,
                                   innervation=lambda: csr_matrix(np.array([[1, 0, 0, 0], [0, 1, 0, 0]], dtype=np.float32)),
                                   exposed_mask=lambda: exposed,
                                   receptors=lambda: ReceptorMap(r1.astype(np.float32), r2.astype(np.float32),
                                                                  np.zeros(4, dtype=np.float32), "constructed"),
                                   compartments=lambda: [SimpleNamespace(name="a"), SimpleNamespace(name="b")])
    for da in (0, params.get("da.DA_ref"), 5 * params.get("da.DA_ref")):
        dv_wt, g_wt, _, _ = receptor_effect(np.full(2, da), w, exposed, r1, r2, params)
        dv_null, g_null, _, _ = receptor_effect(np.full(2, da), w, exposed, np.zeros(4), r2, params)
        occ = da / (da + params.get("rec.Kd_D1"))
        errors.extend((float(np.max(np.abs(dv_wt - dv_null + params.get("rec.dV_D1") * r1 * occ * exposed))),
                       float(np.max(np.abs(g_wt - g_null - params.get("rec.gamma_D1") * r1 * occ * exposed)))))
        off_wt = Neuromod(off_registry, params, LayerFlags(dopamine_A=False))
        off_null = Neuromod(off_registry, params, LayerFlags(dopamine_A=False))
        off_null.r1.fill(0)
        off_wt.da_c.fill(da)
        off_null.da_c.fill(da)
        errors.extend((float(np.max(np.abs(off_wt.compose().v_th - off_null.compose().v_th))),
                       float(np.max(np.abs(off_wt.compose().gain - off_null.compose().gain))),
                       float(np.max(np.abs(off_wt.compose().v_th - params.get("lif.v_th")))),
                       float(np.max(np.abs(off_wt.compose().gain - 1)))))
    maximum = max(errors)
    return _entry("3.7", "verification", "passed" if maximum < 1e-12 else "failed", {"max_error": maximum, "levels_um": [0, params.get("da.DA_ref"), 5 * params.get("da.DA_ref")]})


def test_3_3() -> ValidationEntry:
    """Check saved paired dose response across 0.1/0.5/1.0 mM; DA means in µM."""
    found = _completed_run(DOSE_FIXTURE)
    if found is None:
        return _pending("3.3", "consistency")
    run, manifest = found
    # The three probe positions are fixed by data/experiments/dose-series.json.
    probe_indices = (2, 7, 12)
    from flyonenomics.schema import load_experiment
    seeds = load_experiment(REPO / DOSE_FIXTURE).seeds
    per_seed = {}
    for seed in seeds:
        vehicle = [_mean_innervated_da(run, manifest, "vehicle", seed, k) for k in probe_indices]
        drug = [_mean_innervated_da(run, manifest, "mph", seed, k) for k in probe_indices]
        fumin = [_mean_innervated_da(run, manifest, "fumin", seed, k) for k in probe_indices]
        per_seed[str(seed)] = {"vehicle_um": vehicle, "mph_um": drug, "fumin_um": fumin}
    # Monotonicity uses the three drug levels; vehicle and fumin bounds are checked per level.
    for row in per_seed.values():
        drug = row["mph_um"]
        row["passed"] = bool(all(a < b for a, b in zip(drug[:-1], drug[1:], strict=True)) and
                             all(v < d < f for v, d, f in zip(row["vehicle_um"], drug, row["fumin_um"], strict=True)))
    development = "IdentityBehaviour" in manifest.get("stubs", []) or not manifest.get("dopamine_qualified", False)
    return _entry("3.3", "consistency", "passed" if all(row["passed"] for row in per_seed.values()) else "failed",
                  {"run_id": run.name, "run_code_commit": manifest.get("code_commit"), "run_identity": manifest.get("identity"),
                   "dose_mm": [0.1, 0.5, 1.0], "per_seed": per_seed,
                   "pk.kappa": load_params().get("pk.kappa"), "slow_state": "phase1-drug-only"}, development=development,
                  provisional_name="IdentityBehaviour" if "IdentityBehaviour" in manifest.get("stubs", []) else "UnqualifiedDopamine",
                  run_manifest=manifest)


def test_3_2() -> ValidationEntry:
    """Check saved fumin-versus-WT free-pool DA; compartment means and fixed points in µM."""
    dose = _completed_run(DOSE_FIXTURE)
    use_dose = dose is not None and bool(dose[1].get("da.tonic_source"))
    fixture = DOSE_FIXTURE if use_dose else ABLATION_FIXTURE
    found = dose if use_dose else _completed_run(ABLATION_FIXTURE)
    if found is None:
        return _pending("3.2", "consistency")
    run, manifest = found
    wt_arm, fumin_arm, probe = (("vehicle", "fumin", 2) if use_dose else
                               ("on-retain-wt", "on-retain-fumin", 0))
    from flyonenomics.schema import load_experiment
    per_seed = {}
    for seed in load_experiment(REPO / fixture).seeds:
        wt = _compartment_da(run, manifest, wt_arm, seed, probe)
        mutant = _compartment_da(run, manifest, fumin_arm, seed, probe)
        settle = read_json(run / f"arm-{fumin_arm}" / f"seed-{seed}" / f"probe-{probe}-settle.json")
        names = manifest["compartments"]
        fp = dict(zip(names, settle["fixed_point_da_c"], strict=True))
        comparisons = {name: {"wt_um": wt[name], "fumin_um": mutant[name], "fixed_point_um": fp[name],
                              "at_least_2x": wt[name] > 0 and mutant[name] >= 2 * wt[name],
                              "within_20pct_fp": abs(mutant[name] - fp[name]) <= 0.2 * fp[name]}
                       for name in wt}
        per_seed[str(seed)] = comparisons
    passed = all(row["at_least_2x"] and row["within_20pct_fp"] for seed in per_seed.values() for row in seed.values())
    development = "IdentityBehaviour" in manifest.get("stubs", []) or not manifest.get("dopamine_qualified", False)
    return _entry("3.2", "consistency", "passed" if passed else "failed",
                  {"run_id": run.name, "run_code_commit": manifest.get("code_commit"), "run_identity": manifest.get("identity"), "per_seed": per_seed},
                  fixture=fixture, development=development,
                  provisional_name="IdentityBehaviour" if "IdentityBehaviour" in manifest.get("stubs", []) else "UnqualifiedDopamine",
                  run_manifest=manifest)


def test_3_4() -> ValidationEntry:
    """Check the 0.5 mM fumin MPH null by paired bootstrap; DA difference/margin µM."""
    found = _completed_run(DOSE_FIXTURE)
    if found is None:
        return _pending("3.4", "consistency")
    run, manifest = found
    from flyonenomics.schema import load_experiment
    experiment = load_experiment(REPO / DOSE_FIXTURE)
    seeds = experiment.seeds
    vehicle = np.array([_mean_innervated_da(run, manifest, "fumin", seed, 7) for seed in seeds])
    drug = np.array([_mean_innervated_da(run, manifest, "fumin-mph", seed, 7) for seed in seeds])
    differences = drug - vehicle
    n_boot = load_params().get("stats.bootstrap_n")
    draws = stream(experiment.seed, 0, 0, ANALYSIS).choice(differences, size=(n_boot, len(seeds)), replace=True).mean(axis=1)
    interval = np.quantile(draws, BOOTSTRAP_QUANTILES)
    margin = load_params().get("stats.equivalence_margin") * vehicle.mean()
    passed = bool(interval[0] > -margin and interval[1] < margin)
    development = "IdentityBehaviour" in manifest.get("stubs", []) or not manifest.get("dopamine_qualified", False)
    return _entry("3.4", "consistency", "passed" if passed else "failed",
                  {"run_id": run.name, "run_code_commit": manifest.get("code_commit"), "run_identity": manifest.get("identity"),
                   "dose_mm": 0.5, "paired_difference_um": differences.tolist(),
                   "ci95_um": interval.tolist(), "equivalence_margin_um": float(margin),
                   "model_note": "Methylphenidate changes Km only, so fumin has no modelled DAT target",
                   "pk.kappa": load_params().get("pk.kappa"), "slow_state": "phase1-drug-only"},
                  development=development,
                  provisional_name="IdentityBehaviour" if "IdentityBehaviour" in manifest.get("stubs", []) else "UnqualifiedDopamine",
                  run_manifest=manifest)


def test_3_8_dev() -> ValidationEntry:
    """Keep the un-copied earlier spontaneous ablation explicitly unavailable."""
    return _entry("3.8-dev", "consistency", "unavailable",
                  {"reason": "earlier spontaneous development run was not copied; final 3.8 is separate"},
                  fixture=ABLATION_FIXTURE, development=True, intended_class="matching-layers")


def test_3_5() -> ValidationEntry:
    """Classify measured 3 mM 3-IY versus vehicle in wild type and fumin."""
    found = _completed_run(DEPLETION_FIXTURE)
    if found is None:
        return _entry("3.5", "consistency", "unavailable",
                      {"reason": "paired 3 mM 3-IY experiment not collected"}, fixture=DEPLETION_FIXTURE)
    run, manifest = found
    from flyonenomics.schema import load_experiment
    experiment = load_experiment(REPO / DEPLETION_FIXTURE)
    seeds = tuple(experiment.seeds)
    vehicle = {"wild_type": np.array([_mean_innervated_da(run, manifest, "vehicle", seed, 2) for seed in seeds]),
               "fumin": np.array([_mean_innervated_da(run, manifest, "fumin", seed, 2) for seed in seeds])}
    treated = {"wild_type": np.array([_mean_innervated_da(run, manifest, "3iy", seed, 2) for seed in seeds]),
               "fumin": np.array([_mean_innervated_da(run, manifest, "fumin-3iy", seed, 2) for seed in seeds])}
    measured = depletion_response(vehicle, treated)
    development = manifest.get("compatibility") == "development"
    return _entry("3.5", "consistency", "passed" if measured["passed"] else "failed",
                  {"run_id": run.name, "run_code_commit": manifest.get("code_commit"),
                   "food_mm": 3.0, "seeds": list(seeds), **measured}, fixture=DEPLETION_FIXTURE,
                  development=development,
                  provisional_name=(manifest.get("stubs") or ["UnqualifiedDopamine"])[0],
                  run_manifest=manifest)


def test_3_6() -> ValidationEntry:
    """Record both ten-seed descending-rate contrasts with paired intervals in Hz."""
    found = {"fumin": _completed_run(DESCENDING_FUMIN_FIXTURE, allow_unsettled=True),
             "pam": _completed_run(DESCENDING_PAM_FIXTURE, allow_unsettled=True)}
    if any(value is None for value in found.values()):
        return _entry("3.6", "prediction", "unavailable",
                      {"reason": "ten-seed fumin or PAM 50 Hz contrast not collected",
                       "available": [name for name, value in found.items() if value is not None]},
                      fixture=DESCENDING_FUMIN_FIXTURE)
    from flyonenomics.schema import load_experiment
    result = {}
    development = False
    stubs = []
    for name, fixture in (("fumin", DESCENDING_FUMIN_FIXTURE), ("pam", DESCENDING_PAM_FIXTURE)):
        run, manifest = found[name]
        experiment = load_experiment(REPO / fixture)
        seeds = tuple(experiment.seeds)
        difference = np.array([_mean_rate(run, name, seed, 0, "DN_all") -
                               _mean_rate(run, "baseline", seed, 0, "DN_all") for seed in seeds])
        result[name] = {"run_id": run.name, "run_code_commit": manifest.get("code_commit"),
                        "seeds": list(seeds), "activation_hz": 50 if name == "pam" else None,
                        "unsettled_probes": len(manifest.get("unsettled", [])),
                        "settled_interpretation": not bool(manifest.get("unsettled")),
                        **paired_prediction(difference, load_params().get("stats.bootstrap_n"),
                                            stream(experiment.seed, 0, 0, ANALYSIS))}
        development = development or manifest.get("compatibility") == "development"
        stubs.extend(manifest.get("stubs", []))
    return _entry("3.6", "prediction", "recorded", {"contrasts": result,
                  "proxy_note": "DN_all rate is not validated locomotion"},
                  fixture=DESCENDING_FUMIN_FIXTURE, development=development,
                  provisional_name=(stubs or ["UnqualifiedDopamine"])[0],
                  run_manifest=found["fumin"][1])


def test_3_8() -> ValidationEntry:
    """Record final matching-layer eight-arm fumin-minus-WT factorial contrasts."""
    found = _completed_run(ABLATION_FIXTURE, allow_unsettled=True)
    if found is None:
        return _entry("3.8", "consistency", "unavailable",
                      {"reason": "final eight-arm ablation not collected"}, fixture=ABLATION_FIXTURE,
                      matching_layers=True)
    run, manifest = found
    from flyonenomics.schema import load_experiment
    experiment = load_experiment(REPO / ABLATION_FIXTURE)
    seeds = tuple(experiment.seeds)
    metrics: dict[str, Any] = {}
    for key, read in (("DN_all_hz", lambda a, s: _mean_rate(run, a, s, 0, "DN_all")),
                      ("innervated_DA_um", lambda a, s: _mean_innervated_da(run, manifest, a, s, 0))):
        cells = {}
        for pools in (False, True):
            for fast in ("disconnect", "retain"):
                for genotype in ("wt", "fumin"):
                    arm = f"{'on' if pools else 'off'}-{fast}-{genotype}"
                    cells[(pools, fast, genotype)] = {seed: read(arm, seed) for seed in seeds}
        metrics[key] = ablation_contrasts(cells, seeds, load_params().get("stats.bootstrap_n"), stream(experiment.seed, 0, 0, ANALYSIS))
    development = manifest.get("compatibility") == "development"
    return _entry("3.8", "consistency", "recorded",
                  {"run_id": run.name, "run_code_commit": manifest.get("code_commit"),
                   "seeds": list(seeds), "contrasts": metrics,
                   "unsettled_probes": len(manifest.get("unsettled", [])),
                   "settled_interpretation": not bool(manifest.get("unsettled"))}, fixture=ABLATION_FIXTURE,
                  matching_layers=not development, development=development,
                  provisional_name=(manifest.get("stubs") or ["UnqualifiedDopamine"])[0],
                  intended_class="matching-layers", run_manifest=manifest)


def test_3_9() -> ValidationEntry:
    """Classify the 27 isolated three-seed dose sweeps and their DA orderings."""
    from flyonenomics.schema import load_experiment

    plan = sensitivity_grid(load_params())
    seeds = tuple(load_experiment(REPO / DOSE_FIXTURE).seeds)
    runs: dict[int, tuple[Path, dict[str, Any]]] = {}
    for run in sorted((REPO / "runs").glob("*/"), reverse=True):
        try:
            saved = read_json(run / "experiment.json")
            manifest = read_json(run / "manifest.json")
        except (OSError, ValueError):
            continue
        name = saved.get("name", "")
        if not name.startswith("dose-series-sensitivity-") or manifest.get("state") != "done":
            continue
        try:
            index = int(name.rsplit("-", 1)[1])
        except ValueError:
            continue
        if index not in range(len(plan)) or index in runs:
            continue
        setting = plan[index]
        meta = saved.get("meta", {})
        overrides = setting["overrides"]
        if (meta.get("sensitivity_group") != setting["group"] or
                meta.get("sensitivity_level") != setting["level"] or
                meta.get("parameter_overrides") != overrides or
                manifest.get("parameter_overrides") != overrides or
                manifest.get("parameter_override_sha256") != sha256_text(json.dumps(overrides, sort_keys=True))):
            continue
        required = ("params-v0.1.yaml", "receptors-v0.1.yaml", "dopamine-v0.1.yaml",
                    "compartments-v0.1.yaml", "populations-v0.1.yaml", "behaviour-v0.1.yaml")
        if any(manifest.get("checksums", {}).get(key) != sha256_file(REPO / "data" / key) for key in required):
            continue
        runs[index] = run, manifest
    if len(runs) != len(plan):
        return _entry("3.9", "sensitivity", "unavailable",
                      {"reason": f"isolated sensitivity grid incomplete: {len(runs)}/27 settings collected",
                       "collected_setting_indices": sorted(runs), "required_settings": len(plan)},
                      fixture=DOSE_FIXTURE)
    measured = []
    development = False
    unsettled = 0
    for index, setting in enumerate(plan):
        run, manifest = runs[index]
        per_seed = {}
        for seed in seeds:
            values = {arm: [_mean_innervated_da(run, manifest, arm, seed, probe)
                            for probe in (2, 7, 12)]
                      for arm in ("vehicle", "mph", "fumin", "fumin-mph")}
            effect = [drug - vehicle for drug, vehicle in zip(values["mph"], values["vehicle"], strict=True)]
            per_seed[str(seed)] = {"compartment_da_um": values, "dose_effect_um": effect,
                                   "dose_effect_sign": ["positive" if value > 0 else "negative" if value < 0 else "zero"
                                                        for value in effect],
                                   "wt_drug_fumin_order": [vehicle < drug < fumin for vehicle, drug, fumin in
                                                           zip(values["vehicle"], values["mph"], values["fumin"], strict=True)],
                                   "fumin_mph_minus_fumin_um": [drug - base for drug, base in
                                                                  zip(values["fumin-mph"], values["fumin"], strict=True)]}
        unsettled += len(manifest.get("unsettled", []))
        development = development or manifest.get("compatibility") == "development" or bool(manifest.get("stubs"))
        measured.append({"index": index, "group": setting["group"], "level": setting["level"],
                         "overrides": setting["overrides"], "run_id": run.name,
                         "run_code_commit": manifest.get("code_commit"),
                         "unsettled_probes": len(manifest.get("unsettled", [])), "per_seed": per_seed})
    return _entry("3.9", "sensitivity", "recorded",
                  {"settings": measured, "n_settings": len(measured), "seeds": list(seeds),
                   "unsettled_probes": unsettled, "settled_interpretation": unsettled == 0},
                  fixture=DOSE_FIXTURE, development=development,
                  provisional_name="StubComponent" if development else "UnqualifiedDopamine",
                  run_manifest=next(iter(runs.values()))[1])


SUITE: dict[str, Callable[[], ValidationEntry]] = {
    "3.1": test_3_1,
    "3.7": test_3_7,
    "3.3": test_3_3,
    "3.2": test_3_2,
    "3.4": test_3_4,
    "3.5": test_3_5,
    "3.6": test_3_6,
    "3.8": test_3_8,
    "3.8-dev": test_3_8_dev,
}
SUITE["3.1b"] = test_3_1b
SUITE["3.9"] = test_3_9
