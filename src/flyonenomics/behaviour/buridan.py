"""Buridan probe analysis and bare-substrate sign and K3 calibration."""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import time
import hashlib
import datetime as dt
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

from flyonenomics.behaviour.metrics import (
    Geometry,
    bootstrap_mean_interval,
    interval_excludes_zero,
    score,
    steer_gain,
)
from flyonenomics.behaviour.visual_calibration import (
    declared_drive_present,
    declared_substrate,
    declared_substrate_id,
    declared_substrate_present,
)
from flyonenomics.io import hash_file, read_json, read_parquet, read_text, read_yaml
from flyonenomics.types import load_params

ROOT = Path(__file__).resolve().parents[3]
OPEN_LOOP_AZIMUTHS = tuple(range(-150, 151, 30))  # SPEC section 3.5.
SIGN_SEEDS = (1, 2, 3)  # Calibration sign search; real post-freeze 4.1 uses ten seeds.
FLAT_OMEGA_DEG_S = 5  # SPEC section 7 test 4.1.
CONTROL_MIN_FI_DIFFERENCE = .2  # SPEC section 7 test 4.2.
PROVISIONAL_K_STEER = (2, 8)  # WP6 brief provisional sub-grid.
PROVISIONAL_R_VIS_MAX = (70, 150)  # WP6 brief provisional sub-grid.
PROVISIONAL_SIGMA_VIS = (15, 30)  # WP6 brief provisional sub-grid.
PROVISIONAL_SEEDS = (1, 2)  # WP6 brief provisional sub-grid.
PROVISIONAL_DURATION_S = 10  # WP6 brief provisional sub-grid.


def _read_development() -> dict[str, Any]:
    path = ROOT / "data/behaviour-dev.yaml"
    return (read_yaml(path) or {}) if path.exists() else {}


def _write_development(record: dict[str, Any]) -> None:
    path = ROOT / "data/behaviour-dev.yaml"
    path.write_text(yaml.safe_dump(record, sort_keys=False, allow_unicode=True))


def steering_curve(run_dir: Path) -> list[dict[str, Any]]:
    """Aggregate dwell-only open-loop rates (Hz) and omega (degrees/s) by azimuth (11,)."""
    params = load_params()
    transition = params.get("openloop.transition_s")
    period = transition + params.get("openloop.dwell_s")
    groups: dict[int, list[pd.DataFrame]] = {az: [] for az in OPEN_LOOP_AZIMUTHS}
    for path in sorted(run_dir.glob("arm-*/seed-*/probe-*-arena.parquet")):
        frame = read_parquet(path).to_pandas()
        t = frame.t_ms.to_numpy(dtype=float) / 1000
        for index, azimuth in enumerate(OPEN_LOOP_AZIMUTHS):
            mask = (t >= index * period + transition) & (t < (index + 1) * period)
            groups[azimuth].append(frame.loc[mask, ["r_L", "r_R", "omega"]])
    if not all(groups.values()):
        raise ValueError("open-loop run has no complete azimuth schedule")
    output = []
    for azimuth, parts in groups.items():
        values = pd.concat(parts, ignore_index=True)
        if values.empty:
            raise ValueError(f"no dwell data at {azimuth} degrees")
        output.append({"azimuth_deg": azimuth, "rate_difference_hz": float((values.r_R - values.r_L).mean()),
                       "omega_deg_s": float(values.omega.mean()), "chunks": len(values)})
    return output


def choose_sign(curve: list[dict[str, Any]], current_sign: int = 1) -> dict[str, Any]:
    """Choose +/- steering sign by 4.1, or flat below 5 degrees/s at every azimuth."""
    if all(abs(row["omega_deg_s"]) < FLAT_OMEGA_DEG_S for row in curve):
        return {"status": "flat (provisional)", "sign_steer": current_sign,
                "acceptance_4_1": False}
    positive = [row["omega_deg_s"] for row in curve if 0 < row["azimuth_deg"] < 90]
    negative = [row["omega_deg_s"] for row in curve if -90 < row["azimuth_deg"] < 0]
    if len(positive) != 2 or len(negative) != 2:
        raise ValueError("missing +/-30 or +/-60 degree sign-check points")
    direction = np.mean(positive) - np.mean(negative)
    sign = current_sign if direction >= 0 else -current_sign
    corrected = {row["azimuth_deg"]: row["omega_deg_s"] * sign / current_sign for row in curve}
    accepted = all(corrected[az] > 0 for az in (30, 60)) and all(corrected[az] < 0 for az in (-30, -60))
    return {"status": "provisional", "sign_steer": sign, "acceptance_4_1": accepted}


def _run_experiment(experiment: Any, workers: int = 1) -> Path:
    """Run one development experiment; this lane passes one whole-brain worker process."""
    from flyonenomics.orchestrator import run
    from flyonenomics.store import ResultsStore
    store = ResultsStore(ROOT / "runs")
    run_id = run(experiment, store, workers)
    errors = store.validate_run(run_id)
    if errors:
        raise RuntimeError("validate_run failed: " + "; ".join(errors))
    return store.run_path(run_id)


def _p2_run_facts(run_dir: Path) -> dict[str, Any]:
    """Read identity and actual settle durations from an orchestrator manifest."""
    manifest = read_json(run_dir / "manifest.json")
    identity = manifest.get("identity") or {}
    facts = {
        "substrate_id": manifest.get("substrate_id"),
        "engine_model": manifest.get("engine_model"),
        "platform": identity.get("platform"),
        "settle_s": [float(row["settle_s"]) for row in manifest.get("probe_offsets", [])],
    }
    missing = [key for key in ("substrate_id", "engine_model", "platform") if not facts[key]]
    if missing:
        raise ValueError(f"run manifest lacks {', '.join(missing)}: {run_dir}")
    if facts["substrate_id"] != declared_substrate_id():
        raise ValueError("run substrate differs from item 122's declared drive")
    return facts


def _platform_context(values: list[str]) -> dict[str, Any]:
    """Summarize execution platforms without using them as a validity condition."""
    platforms = sorted(set(values))
    return {
        **({"platform": platforms[0]} if len(platforms) == 1 else {}),
        "platforms": platforms,
    }


def _p2_run_context(run_dirs: list[Path]) -> dict[str, Any]:
    """Require one substrate and engine across stage runs; record platform provenance and settles."""
    if not run_dirs:
        raise ValueError("P2 stage has no run directories")
    facts = [_p2_run_facts(path) for path in run_dirs]
    for key in ("substrate_id", "engine_model"):
        if len({row[key] for row in facts}) != 1:
            raise ValueError(f"P2 stage mixed run {key} values")
    return {
        "substrate_id": facts[0]["substrate_id"],
        "engine_model": facts[0]["engine_model"],
        **_platform_context([str(row["platform"]) for row in facts]),
        "settle_s_by_run": [
            {"run_dir": str(path), "platform": row["platform"], "settle_s": row["settle_s"]}
            for path, row in zip(run_dirs, facts, strict=True)
        ],
    }


def _p2_evidence_context(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Require parent stage records to have one complete, current run identity."""
    if not records:
        raise ValueError("P2 evidence context is empty")
    for index, record in enumerate(records):
        missing = [key for key in ("substrate_id", "engine_model") if not record.get(key)]
        if not (record.get("platform") or record.get("platforms")):
            missing.append("platform provenance")
        if missing:
            raise ValueError(f"P2 parent record {index} lacks {', '.join(missing)}")
    for key in ("substrate_id", "engine_model"):
        if len({record[key] for record in records}) != 1:
            raise ValueError(f"P2 parent records mix {key} values")
    if records[0]["substrate_id"] != declared_substrate_id():
        raise ValueError("P2 parent records differ from item 122's declared drive")
    platforms = [
        str(value)
        for record in records
        for value in (record.get("platforms") or [record["platform"]])
    ]
    return {
        "substrate_id": records[0]["substrate_id"],
        "engine_model": records[0]["engine_model"],
        **_platform_context(platforms),
    }


def sign_check(run_dir: Path | None = None) -> dict[str, Any]:
    """Run/read 3-seed 33-s open-loop development probe and set provisional steering sign."""
    if run_dir is None:
        from flyonenomics.schema import load_experiment
        run_dir = _run_experiment(load_experiment(ROOT / "data/experiments/open-loop-steering.json"))
    status = read_json(run_dir / "status.json")
    if status.get("state") != "done":
        raise ValueError(f"open-loop run is not complete: {status.get('state')}")
    seeds = {int(path.name.removeprefix("seed-")) for path in run_dir.glob("arm-*/seed-*") if path.is_dir()}
    if seeds != set(SIGN_SEEDS):
        raise ValueError(f"sign check needs seeds {SIGN_SEEDS}; found {sorted(seeds)}")
    curve = steering_curve(run_dir)
    manifest = read_json(run_dir / "manifest.json")
    settings = manifest.get("behaviour_settings")
    if settings is None:
        raise ValueError("sign-check run must record the steering sign actually used")
    decision = choose_sign(curve, current_sign=int(settings["sign_steer"]))
    result = {"class": "development", "provisional": True, "stub": "IdentityNeuromod",
              "run_dir": str(run_dir), "curve": curve, **decision}
    record = _read_development()
    record["sign_steer"] = decision["sign_steer"]
    record["sign_check"] = result
    _write_development(record)
    return result


def behaviour_step_min_mm(experiment: Any, record: dict[str, Any] | None = None) -> float:
    """Read step_min_mm from the pinned behaviour file, not from Params. Units: mm."""
    if record is None:
        version = experiment.substrate.behaviour_version
        path = ROOT / "data" / f"behaviour-{version}.yaml"
        record = read_yaml(path) if path.exists() else {}
    value = (record or {}).get("step_min_mm")
    if value is None or not np.isfinite(float(value)):
        raise ValueError("pinned behaviour file must carry finite step_min_mm")
    return float(value)


def model_probe_metrics(run_dir: Path) -> list[dict[str, Any]]:
    """Score each Buridan seed's arena parquet in 20-s window mode; mm/degree trajectory (n,)."""
    params = load_params()
    geometry = Geometry.from_params(params)
    from flyonenomics.schema import load_experiment
    from flyonenomics.schema.experiment import BuridanParams
    experiment = load_experiment(run_dir / "experiment.json")
    arms = {arm.label: arm for arm in experiment.arms}
    step_min_mm = behaviour_step_min_mm(experiment)
    rows = []
    for path in sorted(run_dir.glob("arm-*/seed-*/probe-*-arena.parquet")):
        arm = path.parents[1].name.removeprefix("arm-")
        probe = arms[arm].expanded()[int(path.name.split("-")[1])]
        if not isinstance(probe.params, BuridanParams):
            continue
        episodes = None
        if probe.params.distractor is not None:
            distractor = probe.params.distractor
            episodes = pd.DataFrame([{"onset_s": distractor.onset_s, "azimuth_deg": distractor.azimuth}])
        arena = read_parquet(path).to_pandas()
        frame = pd.DataFrame({"t_s": arena.t_ms.to_numpy(dtype=float) / 1000,
                              "x_mm": arena.x.to_numpy(dtype=float), "y_mm": arena.y.to_numpy(dtype=float),
                              "segment": np.zeros(len(arena), dtype=int)})
        result = score(frame, geometry, params, mode="window",
                       step_min_mm=step_min_mm, episodes=episodes)
        rows.append({"arm": arm,
                     "seed": int(path.parent.name.removeprefix("seed-")), "probe": path.stem,
                     "metrics": result})
    return rows


def calibration_target() -> dict[str, float | int]:
    """Read calibration-half FI and stripe deviation medians/IQRs; fractions/degrees, 64 flies."""
    split = read_json(ROOT / "data/brembs-split.json")
    values = split["calibration_metrics"]
    for key in ("fixation_index", "stripe_deviation_deg"):
        if values[f"{key}_defined_flies"] <= 0:
            raise ValueError(f"calibration half has no defined {key} values")
        if values[f"{key}_iqr"] <= 0:
            raise ValueError(f"calibration IQR is zero: {key}")
    return values


def _buridan_experiment(name: str, duration_s: float, seeds: tuple[int, ...],
                        candidate: dict[str, Any] | None = None) -> Any:
    """Construct one layers-off, wild-type development Buridan probe; duration seconds, seeds (n,)."""
    from flyonenomics.schema import load_experiment
    source = load_experiment(ROOT / "data/experiments/controls-encoder-off.json")
    data = source.model_dump(mode="json")
    data["name"] = name
    data["seeds"] = list(seeds)
    data["arms"][0]["protocol"][0]["duration_s"] = duration_s
    data["arms"][0]["protocol"][0]["params"]["encoder"] = "on"
    data["arms"][0]["protocol"][0]["label"] = "stripes-on"
    if candidate is not None:
        data["meta"]["behaviour_override"] = candidate
    return type(source).model_validate(data)


def calibrate() -> dict[str, Any]:
    """Run provisional 2x2x2 K3 grid, two 10-s seeds/candidate; FI fractions and deviations degrees."""
    sign = _read_development().get("sign_check", {})
    if sign.get("status") not in ("provisional", "flat (provisional)"):
        raise ValueError("provisional sign check must complete before K3")
    target = calibration_target()
    sub_grid = {"K_steer": list(PROVISIONAL_K_STEER), "r_vis_max": list(PROVISIONAL_R_VIS_MAX),
                "sigma_vis": list(PROVISIONAL_SIGMA_VIS), "seeds": list(PROVISIONAL_SEEDS),
                "duration_s": PROVISIONAL_DURATION_S}
    record = _read_development()
    previous = record.get("K3", {})
    table = (list(previous["table"]) if previous.get("status") == "in_progress"
             and previous.get("reference_calibration") == target
             and previous.get("sub_grid") == sub_grid
             and previous.get("sign_steer") == record.get("sign_steer") else [])
    prior = os.environ.get("FLYONENOMICS_BEHAVIOUR_OVERRIDE")
    try:
        for gain in PROVISIONAL_K_STEER:
            for rate in PROVISIONAL_R_VIS_MAX:
                for sigma in PROVISIONAL_SIGMA_VIS:
                    candidate = {"K_steer": gain, "r_vis_max": rate, "sigma_vis": sigma}
                    if any(all(row[key] == value for key, value in candidate.items()) for row in table):
                        continue
                    os.environ["FLYONENOMICS_BEHAVIOUR_OVERRIDE"] = json.dumps(candidate)
                    name = f"wp6-k3-k{gain}-r{rate}-s{sigma}"
                    experiment = _buridan_experiment(name, PROVISIONAL_DURATION_S, PROVISIONAL_SEEDS, candidate)
                    run_dir = _run_experiment(experiment)
                    seeds = model_probe_metrics(run_dir)
                    fi = [row["metrics"]["fixation_index"] for row in seeds]
                    dev = [row["metrics"]["stripe_deviation_deg"] for row in seeds]
                    if any(value is None for value in fi + dev):
                        objective = 1e12
                        median_fi = median_dev = None
                    else:
                        median_fi = float(np.median(fi))
                        median_dev = float(np.median(dev))
                        objective = ((median_fi - target["fixation_index_median"]) / target["fixation_index_iqr"]) ** 2
                        objective += ((median_dev - target["stripe_deviation_deg_median"]) / target["stripe_deviation_deg_iqr"]) ** 2
                    table.append({**candidate, "objective": float(objective), "model_fi": median_fi,
                                  "model_stripe_deviation_deg": median_dev, "run_dir": str(run_dir),
                                  "seeds": list(PROVISIONAL_SEEDS)})
                    record["K3"] = {"class": "development", "provisional": True,
                                    "stub": "IdentityNeuromod", "status": "in_progress",
                                    "sub_grid": sub_grid, "reference_calibration": target,
                                    "sign_steer": record.get("sign_steer"), "table": table}
                    _write_development(record)
    finally:
        if prior is None:
            os.environ.pop("FLYONENOMICS_BEHAVIOUR_OVERRIDE", None)
        else:
            os.environ["FLYONENOMICS_BEHAVIOUR_OVERRIDE"] = prior
    winner = min(table, key=lambda row: row["objective"])
    record["selected"] = {key: winner[key] for key in ("K_steer", "r_vis_max", "sigma_vis")}
    result = {"class": "development", "provisional": True, "stub": "IdentityNeuromod",
              "status": "provisional", "sign_steer": record.get("sign_steer"),
              "layers": {"background": False, "dopamine_A": False, "transporter_C": False,
                         "dan_fast_synapses": "retain"},
              "sub_grid": sub_grid,
              "reference_calibration": target, "winner": winner, "table": table}
    record["K3"] = result
    _write_development(record)
    return result


def controls_4_2() -> dict[str, Any]:
    """Run 3-seed, 20-s stripes-on and two controls; report FI and deviation medians."""
    if not _read_development().get("selected"):
        raise ValueError("provisional K3 must complete before 4.2 controls")
    from flyonenomics.schema import load_experiment
    paths = {"stripes_on": _run_experiment(_buridan_experiment(
        "wp6-stripes-on-development", load_params().get("buridan.duration_s"), SIGN_SEEDS))}
    for key, filename in (("stripes_off", "controls-stripes-off.json"),
                          ("encoder_off", "controls-encoder-off.json")):
        paths[key] = _run_experiment(load_experiment(ROOT / "data/experiments" / filename))
    measurements: dict[str, Any] = {}
    for key, path in paths.items():
        rows = model_probe_metrics(path)
        measurements[key] = {"run_dir": str(path), "seeds": [row["seed"] for row in rows],
                             "median_fi": float(np.median([row["metrics"]["fixation_index"] for row in rows])),
                             "median_stripe_deviation_deg": float(np.median([row["metrics"]["stripe_deviation_deg"] for row in rows]))}
    on = measurements["stripes_on"]
    comparisons = {key: {"fi_difference": on["median_fi"] - measurements[key]["median_fi"],
                         "deviation_difference_deg": on["median_stripe_deviation_deg"] - measurements[key]["median_stripe_deviation_deg"]}
                   for key in ("stripes_off", "encoder_off")}
    result = {"class": "development", "provisional": True, "stub": "IdentityNeuromod",
              "measurements": measurements, "comparisons": comparisons,
              "passes_4_2_threshold_provisionally": all(row["fi_difference"] >= CONTROL_MIN_FI_DIFFERENCE and row["deviation_difference_deg"] < 0
                                                    for row in comparisons.values())}
    record = _read_development()
    record["control_4_2"] = result
    _write_development(record)
    return result


FINAL_LAYERS = {"background": False, "dopamine_A": True, "transporter_C": True,
                "dan_fast_synapses": "retain", "receptor_kinetics_B": False, "learning_D": False}
FINAL_K_STEER = (1, 2, 4, 8)
FINAL_R_VIS_MAX = (40, 70, 100, 150)
FINAL_SIGMA_VIS = (15, 20, 30)
FINAL_SEEDS = (1, 2, 3, 4, 5)
PROGRESS = ROOT / ".cache/wp9-behaviour-progress.json"


def _progress() -> dict[str, Any]:
    """Read resumable calibration measurements; one JSON mapping, no frozen input edits."""
    return read_json(PROGRESS) if PROGRESS.exists() else {}


def _save_progress(value: dict[str, Any]) -> None:
    """Atomically retain measured candidate rows; one JSON mapping."""
    PROGRESS.parent.mkdir(parents=True, exist_ok=True)
    temporary = PROGRESS.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n")
    temporary.replace(PROGRESS)


def _available_memory() -> float:
    """Read macOS PhysMem unused memory, in MiB."""
    output = subprocess.check_output(["top", "-l", "1", "-n", "0"], text=True)
    match = re.search(r"PhysMem:.*?([0-9]+(?:\.[0-9]+)?)([MG]) unused", output)
    if not match:
        raise RuntimeError("top did not report PhysMem unused")
    return float(match.group(1)) * (1024 if match.group(2) == "G" else 1)


def _wait_for_memory() -> None:
    """Apply WP9's 4000 MiB start threshold, waiting at most 30 minutes."""
    for attempt in range(16):
        free = _available_memory()
        if free > 4000:
            print(f"WP9 PhysMem: {free:.0f} MiB unused", flush=True)
            return
        if attempt == 15:
            print(f"WP9 PhysMem: {free:.0f} MiB after 30 minutes; proceeding", flush=True)
            return
        print(f"WP9 PhysMem: {free:.0f} MiB; waiting two minutes", flush=True)
        time.sleep(120)


def _final_experiment(source: str, name: str, seeds: tuple[int, ...],
                      override: dict[str, float | int]) -> Any:
    """Build a matching-layers candidate with isolated behaviour overrides."""
    from flyonenomics.schema import load_experiment
    original = load_experiment(ROOT / "data/experiments" / source)
    data = original.model_dump(mode="json")
    data["name"] = name
    data["seeds"] = list(seeds)
    data["layers"] = FINAL_LAYERS
    data["substrate"]["behaviour_version"] = "dev"
    data["meta"] = {"behaviour_override": override, "calibration": "WP9 final bare substrate"}
    if source == "controls-encoder-off.json":
        data["arms"][0]["protocol"][0]["params"]["encoder"] = "on"
        data["arms"][0]["protocol"][0]["label"] = "stripes-on"
        data["arms"][0]["protocol"][0]["duration_s"] = 20
    return type(original).model_validate(data)


def _run_final(experiment: Any) -> Path:
    """Start one whole-brain worker after WP9's memory check."""
    _wait_for_memory()
    return _run_experiment(experiment, workers=1)


def _frozen_sign_check() -> dict[str, Any] | None:
    """Return the sign check frozen in `behaviour-v0.1.yaml`, if that record exists."""
    path = ROOT / "data/behaviour-v0.1.yaml"
    return read_yaml(path).get("sign_check") if path.exists() else None


def final_sign_check() -> dict[str, Any]:
    """Measure the bare A/C-on steering curve at 100, then 140/280 Hz if flat.

    Once `behaviour-v0.1.yaml` is frozen and no local progress exists, replay its
    recorded curve after checking the grid and cap against Params, as K2 replays
    the dopamine record; the freeze allows no later remeasurement.
    """
    import yaml
    dopamine = read_yaml(ROOT / "data/dopamine-v0.1.yaml")
    if not dopamine.get("qualified"):
        return {"status": "blocked", "reason": "K2/Q is not qualified"}
    params = load_params()
    cap = float(params.get("vis.r_max"))
    rates = (int(params.get("vis.r_vis_max")), 140, 280)
    if any(rate > cap for rate in rates):
        raise ValueError("sign-check rate exceeds vis.r_max")
    progress = _progress()
    frozen = _frozen_sign_check()
    if frozen is not None and not progress.get("sign_attempts"):
        tried = tuple(row["r_vis_max_hz"] for row in frozen["attempts"])
        if float(frozen["r_max_hz"]) != cap or tried != rates[:len(tried)]:
            raise ValueError("frozen sign check differs from the Params grid")
        return {**frozen, "reason": "sign check already measured; frozen behaviour record retained"}
    attempts = progress.setdefault("sign_attempts", [])
    for rate in rates:
        if any(row["r_vis_max_hz"] == rate for row in attempts):
            continue
        candidate = {"K_steer": int(params.get("steer.K_steer")),
                     "r_vis_max": rate, "sigma_vis": int(params.get("vis.sigma_vis")),
                     "sign_steer": 1}
        run_dir = _run_final(_final_experiment("open-loop-steering.json", f"wp9-sign-r{rate}",
                                                SIGN_SEEDS, candidate))
        curve = steering_curve(run_dir)
        decision = choose_sign(curve, current_sign=1)
        attempts.append({"r_vis_max_hz": rate, "run_dir": str(run_dir),
                         "seeds": list(SIGN_SEEDS), "curve": curve, "decision": decision})
        _save_progress(progress)
        print(f"WP9 sign rate {rate} Hz: {json.dumps(decision)}", flush=True)
        if not decision["status"].startswith("flat"):
            break
    for row in attempts:
        row["decision"]["status"] = ("flat" if row["decision"]["status"].startswith("flat")
                                      else "measured")
    selected = next((row for row in attempts if row["decision"]["status"] != "flat"), None)
    result = {"status": "recorded", "configuration_class": "matching-layers",
              "layers": FINAL_LAYERS, "r_max_hz": cap, "attempts": attempts,
              "flat": selected is None, "selected_r_vis_max_hz": selected["r_vis_max_hz"] if selected else 280,
              "sign_steer": selected["decision"]["sign_steer"] if selected else 1,
              "acceptance_4_1": bool(selected and selected["decision"]["acceptance_4_1"])}
    progress["sign_result"] = result
    _save_progress(progress)
    return result


def _freeze_final(sign: dict[str, Any], selected: dict[str, Any] | None,
                  table: list[dict[str, Any]]) -> dict[str, Any]:
    """Freeze K3 inputs and measured grid, with qualification deferred to 4.1/4.2."""
    development = _read_development()
    existing_path = ROOT / "data/behaviour-v0.1.yaml"
    existing = read_yaml(existing_path) if existing_path.exists() else {}
    split = ROOT / "data/brembs-split.json"
    split_data = read_json(split)
    record = {"version": "v0.1", "date": dt.date.today().isoformat(),
              "qualified": False, "qualification_pending": ["4.1", "4.2"] if selected else [],
              "validation_4_1": "unavailable" if selected else "failed",
              "qualification_reason": "pending final controls" if selected else
                                      "sign curve flat at 280 Hz, section 9.1 fallback",
              "configuration_class": "matching-layers", "layers": FINAL_LAYERS,
              "params_version": load_params().version, "dopamine_version": "v0.1",
              "receptor_map_version": "v0.1", "connectome_version": "783",
              "brembs_split_sha256": hash_file(split),
              "calibration_half_sha256": hashlib.sha256(json.dumps(
                  split_data["calibration"], sort_keys=True).encode()).hexdigest(),
              "holdout_half_sha256": hashlib.sha256(json.dumps(
                  split_data["holdout"], sort_keys=True).encode()).hexdigest(),
              "seed_master": 20260912, "seeds": list(FINAL_SEEDS),
              "v_fwd_mm_s": development.get("v_fwd_mm_s", existing.get("v_fwd_mm_s")),
              "step_min_mm": development.get("step_min_mm", existing.get("step_min_mm")),
              "r_max_hz": sign["r_max_hz"], "sign_steer": sign["sign_steer"],
              "selected": {key: selected[key] for key in ("K_steer", "r_vis_max", "sigma_vis")}
                          if selected else {"K_steer": int(load_params().get("steer.K_steer")),
                                            "r_vis_max": 280, "sigma_vis": int(load_params().get("vis.sigma_vis"))},
              "sign_check": sign,
              "K3": {"status": "recorded" if selected else "unavailable",
                     "reason": None if selected else "flat at 280 Hz; section 9.1 fallback",
                     "reference_calibration": calibration_target(), "winner": selected,
                     "table": table}}
    path = ROOT / "data/behaviour-v0.1.yaml"
    path.write_text(yaml.safe_dump(record, sort_keys=False, allow_unicode=True))
    return record


def final_k3() -> dict[str, Any]:
    """Run the fixed 48-candidate five-seed grid, or record the flat-curve fallback."""
    progress = _progress()
    sign = progress.get("sign_result") or _frozen_sign_check()
    if not sign:
        return {"status": "blocked", "reason": "final sign check is missing"}
    if sign["flat"]:
        frozen_path = ROOT / "data/behaviour-v0.1.yaml"
        if frozen_path.exists():
            frozen = read_yaml(frozen_path)
            if frozen.get("sign_check") != sign or frozen.get("K3", {}).get("status") != "unavailable":
                raise ValueError("frozen behaviour record differs from the flat sign result")
        else:
            _freeze_final(sign, None, [])
        return {"status": "recorded", "outcome": "unavailable",
                "reason": "flat at 280 Hz; section 9.1 fallback", "candidates": 0}
    target = calibration_target()
    rates = list(FINAL_R_VIS_MAX)
    if sign["selected_r_vis_max_hz"] not in rates:
        rates.append(sign["selected_r_vis_max_hz"])
    table = progress.setdefault("k3_table", [])
    for gain in FINAL_K_STEER:
        for rate in rates:
            for sigma in FINAL_SIGMA_VIS:
                candidate = {"K_steer": gain, "r_vis_max": rate, "sigma_vis": sigma}
                if any(all(row[key] == value for key, value in candidate.items()) for row in table):
                    continue
                override = {**candidate, "sign_steer": sign["sign_steer"]}
                run_dir = _run_final(_final_experiment("controls-encoder-off.json",
                    f"wp9-k3-k{gain}-r{rate}-s{sigma}", FINAL_SEEDS, override))
                rows = model_probe_metrics(run_dir)
                fi = [row["metrics"]["fixation_index"] for row in rows]
                dev = [row["metrics"]["stripe_deviation_deg"] for row in rows]
                if any(value is None for value in fi + dev):
                    median_fi = median_dev = None
                    objective = float("inf")
                else:
                    median_fi = float(np.median(fi))
                    median_dev = float(np.median(dev))
                    objective = float(((median_fi - target["fixation_index_median"]) /
                                       target["fixation_index_iqr"]) ** 2 +
                                      ((median_dev - target["stripe_deviation_deg_median"]) /
                                       target["stripe_deviation_deg_iqr"]) ** 2)
                table.append({**candidate, "objective": objective, "model_fi": median_fi,
                              "model_stripe_deviation_deg": median_dev,
                              "run_dir": str(run_dir), "seeds": list(FINAL_SEEDS)})
                _save_progress(progress)
                print(f"WP9 K3 {len(table)}/{len(FINAL_K_STEER)*len(rates)*len(FINAL_SIGMA_VIS)}: {objective}", flush=True)
    winner = min(table, key=lambda row: row["objective"])
    _freeze_final(sign, winner, table)
    return {"status": "recorded", "winner": winner, "candidates": len(table),
            "qualified": False, "reason": "4.1 and 4.2 qualification pending"}


STAGE = {"sign": final_sign_check, "K3": final_k3}
DEV_STAGE = {"sign": sign_check, "K3": calibrate, "4.2": controls_4_2}

# --- Phase 2 (SPEC-P2 sections 3.5, 3.6, 3.7). No engine until coordinator. ---
SIGN_CHECK_AZIMUTHS = (-150, -120, -90, -60, -45, -30, 0, 30, 45, 60, 90, 120, 150)
K3R_K_STEER = (1.0, 2.0, 4.0, 8.0, 16.0)
K3R_PROPOSAL_SEEDS = (1, 2, 3, 4, 5)
K3R_FINAL_SEEDS = tuple(range(1, 11))
VT_CAL_RATES_HZ = (40.0, 70.0, 100.0, 150.0, 280.0)
VT_CAL_SIGMA_VIS = 20.0
CENTRAL_INPUT_POPULATIONS: tuple[str, ...] = ("TuBu", "visual_projection", "LAL_neurons")
P2_MIN_DELTA_HZ = 0.5
P2_CONTROL_FI = 0.2
PLAN_SETTLE_S = 2.0
BURIDAN_S = 20.0
VISUAL_PATH = ROOT / "data/visual-v0.2.yaml"
DOPAMINE_PATH = ROOT / "data/dopamine-v0.2.yaml"


def p2_missing_dependencies(stage: str | None = None) -> list[str]:
    """Name missing inputs; visual producers require the recorded fallback trigger.

    VT-cal and step 3 create the visual configuration, so cannot require it
    beforehand. Consumers (including the default query) still require it.
    Every stage requires item 122's substrate and canonical drive/dopamine.
    Units: none.
    """
    missing: list[str] = []
    if not declared_substrate_present():
        missing.append("item 122 declared substrate")
    elif not declared_drive_present():
        missing.append("data/drive-v0.2.yaml")
    if stage in ("VT-cal", "open-loop"):
        from flyonenomics.behaviour.visual_status import photoreceptor_failures

        outcomes = {}
        for key, name in (("vcal", "visual-vcal"), ("v1", "V1"), ("v3", "V3"),
                          ("sign", "signcheck"), ("4.1r", "4.1r"), ("4.2r", "4.2r")):
            record = _read_p2_record(name)
            if record and (record.get("status") or record.get("outcome")) in (
                    "passed", "failed", "recorded", "flat"):
                outcomes[key] = {**record, "present": True}
        if not photoreceptor_failures(outcomes):
            missing.append("recorded photoreceptor failure (SPEC-P2 3.7)")
        if stage == "open-loop":
            tubu_records = tuple(filter(None, (_read_p2_record(name) for name in (
                "vtcal", "4.1r-T-sign", "k3r-tubu", "4.1r-T", "4.2r-T"))))
            if not any((record.get("status") or record.get("outcome")) in
                       ("failed", "flat", "unavailable") or record.get("flat") is True
                       for record in tubu_records):
                missing.append("recorded TuBu failure (SPEC-P2 3.7)")
    elif not VISUAL_PATH.is_file():
        missing.append("data/visual-v0.2.yaml")
    if not DOPAMINE_PATH.is_file():
        missing.append("data/dopamine-v0.2.yaml")
    return missing


def k3r_objective(model_fi: float | None, model_dev_deg: float | None,
                  target: dict[str, float | int]) -> float:
    """SPEC section 3.5 K3r objective. FI is a fraction; deviation is degrees."""
    if model_fi is None or model_dev_deg is None:
        return float("inf")
    fi_term = ((float(model_fi) - float(target["fixation_index_median"])) /
               float(target["fixation_index_iqr"])) ** 2
    dev_term = ((float(model_dev_deg) - float(target["stripe_deviation_deg_median"])) /
                float(target["stripe_deviation_deg_iqr"])) ** 2
    return float(fi_term + dev_term)


def choose_k3r(table: list[dict[str, Any]]) -> dict[str, Any]:
    """Pick the lowest-objective K_steer, ties to the lower gain. Units: deg/s per Hz."""
    if not table:
        raise ValueError("K3r table is empty")
    return min(table, key=lambda row: (float(row["objective"]), float(row["K_steer"])))


def k3r_finalists(table: list[dict[str, Any]], n: int = 3) -> list[dict[str, Any]]:
    """Return the n lowest-objective Camber rows for the Mac ten-seed rerun."""
    ranked = sorted(table, key=lambda row: (float(row["objective"]), float(row["K_steer"])))
    return ranked[:n]


def choose_sign_from_gains(gains: list[float], rng: np.random.Generator, n_boot: int) -> dict[str, Any]:
    """Set sign_steer from the three-seed steer_gain interval (section 3.5). Units: Hz/deg."""
    from flyonenomics.behaviour.metrics import bootstrap_mean_interval, interval_excludes_zero

    interval = bootstrap_mean_interval(gains, rng, n_boot)
    lo, hi = interval["ci95"]
    if lo > 0:
        sign, flat, status = 1, False, "measured"
    elif hi < 0:
        sign, flat, status = -1, False, "measured"
    else:
        sign, flat, status = 1, True, "flat"
    return {"sign_steer": sign, "flat": flat, "status": status,
            "acceptance_4_1r_sign": interval_excludes_zero(interval["ci95"]) and not flat,
            **interval}


def measure_bias_from_rates(deltas_hz: list[float]) -> dict[str, Any]:
    """Ten-seed mean of r_R − r_L on an ambient probe. Units: Hz. Shapes: (n_seed,)."""
    values = np.asarray(deltas_hz, dtype=float)
    if len(values) < 1:
        raise ValueError("bias needs at least one seed")
    return {"bias_hz": float(values.mean()), "n": int(len(values)), "per_seed_hz": values.tolist()}


def evaluate_4_1r(gains: list[float], plus45_delta_hz: list[float], minus45_delta_hz: list[float],
                  sign_steer: int, rng: np.random.Generator, n_boot: int,
                  min_delta_hz: float = P2_MIN_DELTA_HZ) -> dict[str, Any]:
    """Matching-layers 4.1r on constructed per-seed values. Units: Hz/deg and Hz."""
    from flyonenomics.behaviour.metrics import bootstrap_mean_interval, interval_excludes_zero

    gain = bootstrap_mean_interval(gains, rng, n_boot)
    contrast = np.asarray(plus45_delta_hz, dtype=float) - np.asarray(minus45_delta_hz, dtype=float)
    delta = bootstrap_mean_interval(contrast, rng, n_boot)
    gain_ok = interval_excludes_zero(gain["ci95"]) and (
        (sign_steer > 0 and gain["mean"] > 0) or (sign_steer < 0 and gain["mean"] < 0))
    delta_ok = abs(delta["mean"]) >= float(min_delta_hz) and interval_excludes_zero(delta["ci95"])
    passed = bool(gain_ok and delta_ok)
    return {"outcome": "passed" if passed else "failed", "steer_gain": gain,
            "plus45_minus_minus45_hz": delta, "sign_steer": int(sign_steer),
            "gain_ok": gain_ok, "delta_ok": delta_ok}


def evaluate_4_2r(stripes_on: dict[str, list[float]], stripes_off: dict[str, list[float]],
                  encoder_off: dict[str, list[float]], min_fi: float = P2_CONTROL_FI) -> dict[str, Any]:
    """Matching-layers 4.2r on constructed per-seed FI and deviation. Fractions and degrees."""
    def median(key: str, arm: dict[str, list[float]]) -> float:
        return float(np.median(arm[key]))

    on_fi, off_fi, enc_fi = median("fixation_index", stripes_on), median("fixation_index", stripes_off), median("fixation_index", encoder_off)
    on_dev, off_dev, enc_dev = (median("stripe_deviation_deg", arm)
                                for arm in (stripes_on, stripes_off, encoder_off))
    fi_ok = (on_fi - off_fi) >= float(min_fi) and (on_fi - enc_fi) >= float(min_fi)
    dev_ok = on_dev < off_dev and on_dev < enc_dev
    return {"outcome": "passed" if fi_ok and dev_ok else "failed",
            "median_fi": {"stripes_on": on_fi, "stripes_off": off_fi, "encoder_off": enc_fi},
            "median_stripe_deviation_deg": {"stripes_on": on_dev, "stripes_off": off_dev, "encoder_off": enc_dev},
            "fi_ok": fi_ok, "deviation_ok": dev_ok}


def evaluate_vtcal(table: list[dict[str, Any]], min_delta_hz: float = P2_MIN_DELTA_HZ) -> dict[str, Any]:
    """Select the lowest r_vis_max whose constructed V1-T three-seed row passes. Units: Hz."""
    passing = [row for row in table if row.get("central_input_carried") and row.get("steering_carried")
               and abs(float(row.get("mean_delta_steer_hz") or 0.0)) >= float(min_delta_hz)
               and row.get("delta_interval_excludes_zero")]
    passing.sort(key=lambda row: float(row["r_vis_max_hz"]))
    selected = passing[0] if passing else None
    return {"status": "passed" if selected else "failed",
            "selected_r_vis_max_hz": None if selected is None else float(selected["r_vis_max_hz"]),
            "sigma_vis": VT_CAL_SIGMA_VIS, "table": table, "n_passing": len(passing)}


def _blocked(stage: str, missing: list[str] | None = None) -> dict[str, Any]:
    """Return a blocked P2 stage record bound to the declared substrate. Units: none."""
    missing = p2_missing_dependencies(stage) if missing is None else missing
    reason = "Waiting for: " + (", ".join(missing) if missing else "the coordinator's engine slot")
    return {"status": "blocked", "stage": stage, "reason": reason, "missing": missing,
            "substrate_id": declared_substrate_id(), "declared_substrate": declared_substrate()}


# --- Phase 2 engine runners (SPEC-P2 sections 3.5 to 3.7). Engine work is explicit. ---
P2_FIXTURES = ROOT / "data/experiments/p2"
P2_RECORDS = ROOT / "validation/records/p2"
BEHAVIOUR_P2 = ROOT / "data/behaviour-v0.2.yaml"
VISUAL_P2 = ROOT / "data/visual-v0.2.yaml"
P2_ANALYSIS_SEED = 20260912


def _p2_experiment(name: str, *, seeds: tuple[int, ...] | list[int] | None = None,
                   behaviour_version: str | None = None, visual_version: str | None = None,
                   meta: dict[str, Any] | None = None,
                   record_rates: list[str] | None = None) -> Any:
    """Load one WP20 fixture with seed, pin, metadata and rate overrides. Units per file."""
    from flyonenomics.schema import load_experiment

    source = load_experiment(P2_FIXTURES / name)
    data = source.model_dump(mode="json")
    if seeds is not None:
        data["seeds"] = [int(seed) for seed in seeds]
    if behaviour_version is not None:
        data["substrate"]["behaviour_version"] = behaviour_version
    if visual_version is not None:
        data["substrate"]["visual_version"] = visual_version
    if meta:
        data["meta"] = {**data.get("meta", {}), **meta}
    if record_rates is not None:
        data["record"] = {**data.get("record", {}), "rates": list(record_rates)}
    return type(source).model_validate(data)


def _p2_open_loop_probe(experiment: Any, label: str | None = None) -> tuple[int, list[dict[str, Any]]]:
    """One open-loop probe's expanded index and block schedule. Units: seconds, degrees."""
    from flyonenomics.schema.experiment import Probe

    for index, phase in enumerate(experiment.arms[0].expanded()):
        if not isinstance(phase, Probe) or phase.assay != "open_loop_steering":
            continue
        if label is not None and phase.label != label:
            continue
        blocks = getattr(phase.params, "blocks", None)
        if not blocks:
            raise ValueError("WP20 open-loop fixture needs explicit schema 1.3 blocks")
        return index, [{"stimulus": block.stimulus, "azimuth_deg": block.azimuth_deg,
                        "transition_s": float(block.transition_s), "dwell_s": float(block.dwell_s)}
                       for block in blocks]
    raise ValueError(f"no open_loop_steering probe{'' if label is None else f' labelled {label}'}")


def _p2_arena(run_dir: Path, arm: str, seed: int, probe: int) -> pd.DataFrame:
    """Arena table (t_ms, r_L, r_R, omega) for one seed/probe. Units: s, Hz, degrees/s."""
    path = run_dir / f"arm-{arm}" / f"seed-{seed}" / f"probe-{probe}-arena.parquet"
    if not path.is_file():
        raise ValueError(f"missing arena table: {path}")
    return read_parquet(path).to_pandas()


def open_loop_blocks(run_dir: Path, *, label: str | None = None,
                     arm: str | None = None) -> list[dict[str, Any]]:
    """Per-seed open-loop block means of r_R − r_L and omega. Units: Hz, degrees/s.

    Reads the run's resolved experiment and each seed's arena table. Block
    dwell excludes the block transition, as SPEC-P2 section 3.5 requires.
    Shapes: one row per seed, each with one row per block. `arm` names one
    arm of a multi-arm run; it defaults to the first arm.
    """
    from flyonenomics.schema import load_experiment

    experiment = load_experiment(run_dir / "experiment.json")
    probe, schedule = _p2_open_loop_probe(experiment, label)
    arm = experiment.arms[0].label if arm is None else arm
    rows: list[dict[str, Any]] = []
    for seed in experiment.seeds:
        frame = _p2_arena(run_dir, arm, int(seed), probe)
        t = frame.t_ms.to_numpy(dtype=float) / 1000.0
        start = 0.0
        blocks: list[dict[str, Any]] = []
        for block in schedule:
            period = block["transition_s"] + block["dwell_s"]
            mask = (t >= start + block["transition_s"]) & (t < start + period)
            if not mask.any():
                raise ValueError(f"no dwell samples for block {block['stimulus']} at {block['azimuth_deg']}")
            blocks.append({"stimulus": block["stimulus"], "azimuth_deg": block["azimuth_deg"],
                           "delta_hz": float((frame.loc[mask, "r_R"] - frame.loc[mask, "r_L"]).mean()),
                           "omega_deg_s": float(frame.loc[mask, "omega"].mean()),
                           "n_samples": int(mask.sum())})
            start += period
        rows.append({"seed": int(seed), "blocks": blocks})
    return rows


def open_loop_population_blocks(run_dir: Path, populations: tuple[str, ...], *,
                                label: str | None = None) -> list[dict[str, Any]]:
    """Per-seed block means of named populations from one open-loop run. Units: Hz.

    Reads the run's rates table (one column per population) and the probe's
    block schedule. Shapes: one row per seed, one row per block.
    """
    from flyonenomics.schema import load_experiment

    experiment = load_experiment(run_dir / "experiment.json")
    probe, schedule = _p2_open_loop_probe(experiment, label)
    arm = experiment.arms[0].label
    rows: list[dict[str, Any]] = []
    for seed in experiment.seeds:
        path = run_dir / f"arm-{arm}" / f"seed-{seed}" / f"probe-{probe}-rates.parquet"
        if not path.is_file():
            raise ValueError(f"missing rates table: {path}")
        frame = read_parquet(path).to_pandas()
        t = frame.t_ms.to_numpy(dtype=float) / 1000.0
        start = 0.0
        blocks: list[dict[str, Any]] = []
        for block in schedule:
            period = block["transition_s"] + block["dwell_s"]
            mask = (t >= start + block["transition_s"]) & (t < start + period)
            if not mask.any():
                raise ValueError(f"no dwell samples for block {block['stimulus']} at {block['azimuth_deg']}")
            means = {name: float(frame.loc[mask, name].mean()) for name in populations}
            blocks.append({"stimulus": block["stimulus"], "azimuth_deg": block["azimuth_deg"], **means})
            start += period
        rows.append({"seed": int(seed), "blocks": blocks})
    return rows


def v1t_row(run_dir: Path, *, r_vis_max: float, rng: np.random.Generator,
            n_boot: int, label: str = "v1-three-seed") -> dict[str, Any]:
    """One VT-cal row: measured central input and steering on the V1-T probe. Units: Hz.

    Follows SPEC-P2 section 3.7: V1 with the depth requirement restricted to
    central input and steering. Each central-input population is measured; the
    depth is carried when any of its intervals excludes zero.
    """
    populations = ("steering_L", "steering_R", *CENTRAL_INPUT_POPULATIONS)
    rows = open_loop_population_blocks(run_dir, populations, label=label)
    central: dict[str, list[float]] = {name: [] for name in CENTRAL_INPUT_POPULATIONS}
    steer: list[float] = []
    for row in rows:
        per_seed = {name: [] for name in CENTRAL_INPUT_POPULATIONS}
        plus = minus = None
        for index, block in enumerate(row["blocks"]):
            if block["azimuth_deg"] is None:
                continue
            ambient = row["blocks"][index - 1]
            for name in CENTRAL_INPUT_POPULATIONS:
                per_seed[name].append(block[name] - ambient[name])
            value = block["steering_R"] - block["steering_L"]
            if block["azimuth_deg"] == 45.0:
                plus = value
            elif block["azimuth_deg"] == -45.0:
                minus = value
        if plus is None or minus is None:
            raise ValueError("V1-T probe needs +45 and -45 stripe blocks")
        for name in CENTRAL_INPUT_POPULATIONS:
            central[name].append(float(np.mean(per_seed[name])))
        steer.append(float(plus - minus))
    steer_interval = bootstrap_mean_interval(steer, rng, n_boot)
    central_intervals = {name: bootstrap_mean_interval(values, rng, n_boot)
                         for name, values in central.items()}
    carried = [name for name, interval in central_intervals.items()
               if interval_excludes_zero(interval["ci95"])]
    return {"r_vis_max_hz": float(r_vis_max), "run_dir": str(run_dir),
            "mean_delta_steer_hz": steer_interval["mean"], "ci95": steer_interval["ci95"],
            "delta_interval_excludes_zero": interval_excludes_zero(steer_interval["ci95"]),
            "steering_carried": interval_excludes_zero(steer_interval["ci95"]),
            "central_input_carried": bool(carried), "central_input_populations": carried,
            "central_ci95": {name: interval["ci95"] for name, interval in central_intervals.items()}}


def bias_from_run(run_dir: Path) -> dict[str, Any]:
    """Ten-seed ambient bias from one bias run. Units: Hz."""
    rows = open_loop_blocks(run_dir)
    return measure_bias_from_rates([row["blocks"][0]["delta_hz"] for row in rows])


def steer_gains_from_run(run_dir: Path) -> list[float]:
    """Per-seed steer_gain from one sign-check run. Units: Hz per degree."""
    gains = []
    for row in open_loop_blocks(run_dir):
        azimuths = [block["azimuth_deg"] for block in row["blocks"] if block["azimuth_deg"] is not None]
        deltas = [block["delta_hz"] for block in row["blocks"] if block["azimuth_deg"] is not None]
        gains.append(steer_gain(azimuths, deltas))
    return gains


def sign_from_run(run_dir: Path) -> dict[str, Any]:
    """Choose the steering sign from one sign-check run. Units: Hz per degree."""
    from flyonenomics.orchestrator.seeds import ANALYSIS, stream

    gains = steer_gains_from_run(run_dir)
    n_boot = int(_p2_params().get("pred.bootstrap_n"))
    return choose_sign_from_gains(gains, stream(P2_ANALYSIS_SEED, 0, 0, ANALYSIS), n_boot)


def k3r_row(k_steer: float, run_dir: Path, target: dict[str, float | int]) -> dict[str, Any]:
    """One K3r candidate row from a scored Buridan run. FI is a fraction, deviation degrees."""
    rows = model_probe_metrics(run_dir)
    fi = [row["metrics"]["fixation_index"] for row in rows]
    dev = [row["metrics"]["stripe_deviation_deg"] for row in rows]
    if not rows or any(value is None for value in fi + dev):
        return {"K_steer": float(k_steer), "run_dir": str(run_dir), "model_fi": None,
                "model_stripe_deviation_deg": None, "objective": float("inf"), "n": len(rows)}
    median_fi, median_dev = float(np.median(fi)), float(np.median(dev))
    return {"K_steer": float(k_steer), "run_dir": str(run_dir), "model_fi": median_fi,
            "model_stripe_deviation_deg": median_dev,
            "objective": k3r_objective(median_fi, median_dev, target), "n": len(rows)}


def _p2_record_path(name: str) -> Path:
    """Path of one WP20 stage record under validation/records/p2. Units: none."""
    return P2_RECORDS / f"{name}.json"


def _write_p2_record(name: str, record: dict[str, Any]) -> str:
    """Write one WP20 stage record and return its SHA-256. Units: none, scalar hash."""
    P2_RECORDS.mkdir(parents=True, exist_ok=True)
    path = _p2_record_path(name)
    path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    return hash_file(path)


def _read_p2_record(name: str) -> dict[str, Any] | None:
    """Read one committed WP20 stage record, or None when absent. Units per record."""
    path = _p2_record_path(name)
    return read_json(path) if path.is_file() else None


def _p2_params() -> Any:
    """v0.2 Params for WP20 stages. Units: per Params rows."""
    return load_params(ROOT / "data/params-v0.2.yaml")


def _p2_encoder() -> str:
    """Encoder in force from the pinned visual file, or the Params default. Units: none."""
    from flyonenomics.drive.rest import load_visual_v02

    visual = load_visual_v02(VISUAL_PATH if VISUAL_PATH.is_file() else None, _p2_params())
    return str(visual.inject_at)


def _encoder_records() -> dict[str, str]:
    """WP20 record names for the encoder in force, so TuBu never overwrites the photoreceptor evidence."""
    tubu = _p2_encoder() == "TuBu"
    return {"bias": "bias-T" if tubu else "bias",
            "sign": "4.1r-T-sign" if tubu else "signcheck",
            "k3r": "k3r-tubu" if tubu else "k3r",
            "4.1r": "4.1r-T" if tubu else "4.1r",
            "4.2r": "4.2r-T" if tubu else "4.2r"}


def _p2_workers() -> int:
    """WP20 worker count from FLYONENOMICS_P2_WORKERS, default one. Units: workers."""
    return max(1, int(os.environ.get("FLYONENOMICS_P2_WORKERS", "1")))


def _k3r_meta(sign_steer: int, bias_hz: float, visual: str, k_steer: float) -> dict[str, Any]:
    """K-grid fixture metadata for one controller. Units: Hz, deg/s per Hz."""
    return {"sign_steer": int(sign_steer), "bias_hz": float(bias_hz), "visual": visual,
            "grid": {"K_steer": float(k_steer)}}


def _k3r_wave(fixture: str, sign_steer: int, bias_hz: float, visual: str,
              target: dict[str, float | int]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    """Five-seed proposal then the three lowest-objective ten-seed finalists. Units: Hz, degrees."""
    proposal = []
    for k_steer in K3R_K_STEER:
        experiment = _p2_experiment(fixture, seeds=K3R_PROPOSAL_SEEDS,
                                    meta=_k3r_meta(sign_steer, bias_hz, visual, k_steer))
        proposal.append(k3r_row(k_steer, _run_experiment(experiment, workers=_p2_workers()), target))
    finalists = []
    for row in k3r_finalists(proposal, 3):
        k_steer = float(row["K_steer"])
        experiment = _p2_experiment(fixture, seeds=K3R_FINAL_SEEDS,
                                    meta=_k3r_meta(sign_steer, bias_hz, visual, k_steer))
        finalists.append(k3r_row(k_steer, _run_experiment(experiment, workers=_p2_workers()), target))
    return proposal, finalists, choose_k3r(finalists)


def _behaviour_document(controller: str, *, sign_steer: int | None, bias_hz: float,
                        k_steer: float | None, visual: str,
                        records: dict[str, str]) -> dict[str, Any]:
    """Build data/behaviour-v0.2.yaml; SPEC-P2 section 3.5. Units: mm/s, Hz, deg/s per Hz."""
    from flyonenomics.drive.rest import blob_id

    base = read_yaml(ROOT / "data/behaviour-base-v0.2.yaml")
    return {
        "version": "v0.2", "controller": controller,
        "v_fwd_mm_s": float(base["v_fwd_mm_s"]), "step_min_mm": float(base["step_min_mm"]),
        "r_max_hz": float(base["r_max_hz"]), "sign_steer": sign_steer,
        "bias_hz": float(bias_hz), "K_steer": k_steer, "visual": visual,
        "provenance": {"behaviour-base-v0.2.yaml": blob_id(ROOT / "data/behaviour-base-v0.2.yaml"),
                       **records},
    }


def _write_behaviour(document: dict[str, Any]) -> str:
    """Write data/behaviour-v0.2.yaml and return its SHA-256. Units: none, scalar hash."""
    BEHAVIOUR_P2.write_text(yaml.safe_dump(document, sort_keys=False, width=120))
    return hash_file(BEHAVIOUR_P2)


def _visual_document(encoder: str, *, vcal_record: str, vcal_sha256: str,
                     r_light: float | None = None, r_vis_max: float | None = None,
                     sigma_vis: float | None = None) -> dict[str, Any]:
    """Build a WP20 section 3.7 commit of data/visual-v0.2.yaml. Units: Hz, degrees."""
    params = _p2_params()
    document: dict[str, Any] = {
        "version": "v0.2", "inject_at": encoder,
        "r_dark": float(params.get("vis.pr_rate_dark_hz")),
        "pr_acceptance_deg": float(params.get("vis.pr_acceptance_deg")),
        "provenance": {"item": 122, "vcal_record": vcal_record, "vcal_sha256": vcal_sha256},
    }
    if r_light is not None:
        document["r_light"] = float(r_light)
    if r_vis_max is not None:
        document["r_vis_max"] = float(r_vis_max)
    if sigma_vis is not None:
        document["sigma_vis"] = float(sigma_vis)
    return document


def measure_bias(*, record_name: str | None = None) -> dict[str, Any]:
    """Bias stage: ten-seed ambient mean of r_R − r_L on item 122's substrate. Units: Hz."""
    missing = p2_missing_dependencies()
    if missing:
        return _blocked("bias")
    record = record_name or _encoder_records()["bias"]
    run_dir = _run_experiment(_p2_experiment("bias.json"), workers=_p2_workers())
    result = {"status": "recorded", "stage": "bias", "record": record, "encoder": _p2_encoder(),
              "declared_substrate": declared_substrate(), "run_dir": str(run_dir),
              **_p2_run_context([run_dir]), **bias_from_run(run_dir)}
    result["record_sha256"] = _write_p2_record(record, result)
    return result


def sign_check_p2() -> dict[str, Any]:
    """4.1r-sign stage: three-seed steer_gain interval on item 122's substrate. Hz/degree."""
    missing = p2_missing_dependencies()
    if missing:
        return _blocked("4.1r-sign")
    record = _encoder_records()["sign"]
    run_dir = _run_experiment(_p2_experiment("signcheck.json"), workers=_p2_workers())
    decision = sign_from_run(run_dir)
    result = {"status": "recorded" if not decision["flat"] else "failed", "stage": "4.1r-sign",
              "record": record, "encoder": _p2_encoder(),
              "declared_substrate": declared_substrate(), "run_dir": str(run_dir),
              **_p2_run_context([run_dir]),
              "gains_hz_per_deg": steer_gains_from_run(run_dir), **decision}
    result["record_sha256"] = _write_p2_record(record, result)
    return result


def _run_k3r(fixture: str, stage: str, record_name: str) -> dict[str, Any]:
    """K3r and K3r-T: propose, rerun finalists, commit the controller. Units: Hz, degrees."""
    missing = p2_missing_dependencies()
    if missing:
        return _blocked(stage)
    records = _encoder_records()
    bias, sign = _read_p2_record(records["bias"]), _read_p2_record(records["sign"])
    if not bias:
        return _blocked(stage, [f"validation/records/p2/{records['bias']}.json"])
    if not sign:
        return _blocked(stage, [f"validation/records/p2/{records['sign']}.json"])
    if sign.get("flat") is True:
        return {"status": "failed", "stage": stage, "substrate_id": declared_substrate_id(),
                "declared_substrate": declared_substrate(),
                "reason": "flat sign check; section 3.7 step 1 applies"}
    parent_context = _p2_evidence_context([bias, sign])
    from flyonenomics.drive.rest import blob_id

    visual = blob_id(VISUAL_PATH)
    proposal, finalists, winner = _k3r_wave(fixture, int(sign["sign_steer"]),
                                            float(bias["bias_hz"]), visual, calibration_target())
    finite = np.isfinite(float(winner["objective"]))
    context = _p2_run_context([Path(row["run_dir"]) for row in [*proposal, *finalists]])
    if any(context[key] != parent_context[key] for key in ("substrate_id", "engine_model")):
        raise ValueError("K3r runs differ from their bias/sign evidence identity")
    result = {"status": "recorded" if finite else "failed", "stage": stage,
              "declared_substrate": declared_substrate(), **context, "visual_blob": visual,
              "proposal": proposal, "finalists": finalists, "winner": winner}
    if not finite:
        result["reason"] = "all K_steer finalists had undefined Buridan metrics"
    record_sha = _write_p2_record(record_name, result)
    if not finite:
        return {**result, "record": record_name, "record_sha256": record_sha}
    document = _behaviour_document("closed_loop", sign_steer=int(sign["sign_steer"]),
                                   bias_hz=float(bias["bias_hz"]), k_steer=float(winner["K_steer"]),
                                   visual=visual,
                                   records={f"{records['bias']}.json": hash_file(_p2_record_path(records["bias"])),
                                            f"{records['sign']}.json": hash_file(_p2_record_path(records["sign"])),
                                            f"{record_name}.json": record_sha})
    return {**result, "record": record_name, "record_sha256": record_sha,
            "behaviour_sha256": _write_behaviour(document)}


def run_k3r() -> dict[str, Any]:
    """K3r stage on the photoreceptor encoder; commits the closed-loop controller. Hz/degree."""
    return _run_k3r("k3r.json", "K3r", "k3r")


def run_k3r_tubu() -> dict[str, Any]:
    """K3r-T stage on the TuBu encoder; commits the closed-loop controller. Hz/degree."""
    return _run_k3r("k3r-tubu.json", "K3r-T", "k3r-tubu")


def run_vtcal() -> dict[str, Any]:
    """VT-cal: TuBu encoder grid, V1 depths restricted to central input and steering. Hz.

    Uses `vpath-vtcal.json`, explicitly targeting TuBu with no visual pin and
    `r_vis_max` metadata; the `v1-three-seed` probe measures the central-input
    populations and the ±45° Δsteer. Three seeds per rate, then ten seeds at
    the lowest passing value; a ten-seed pass commits `visual-v0.2.yaml`.
    """
    from flyonenomics.orchestrator.seeds import ANALYSIS, stream

    missing = p2_missing_dependencies("VT-cal")
    if missing:
        return _blocked("VT-cal", missing)
    n_boot = int(_p2_params().get("pred.bootstrap_n"))
    rates = ("steering_L", "steering_R", *CENTRAL_INPUT_POPULATIONS)
    table: list[dict[str, Any]] = []
    for rate in VT_CAL_RATES_HZ:
        experiment = _p2_experiment("vpath-vtcal.json", meta={"r_vis_max": float(rate)},
                                    record_rates=list(rates))
        run_dir = _run_experiment(experiment, workers=_p2_workers())
        table.append(v1t_row(run_dir, r_vis_max=rate,
                             rng=stream(P2_ANALYSIS_SEED, 0, 0, ANALYSIS), n_boot=n_boot))
    selection = evaluate_vtcal(table)
    ten_seed = None
    if selection["selected_r_vis_max_hz"] is not None:
        experiment = _p2_experiment("vpath-vtcal.json", seeds=K3R_FINAL_SEEDS,
                                    meta={"r_vis_max": selection["selected_r_vis_max_hz"]},
                                    record_rates=list(rates))
        ten_seed = v1t_row(_run_experiment(experiment, workers=_p2_workers()),
                           r_vis_max=selection["selected_r_vis_max_hz"],
                           rng=stream(P2_ANALYSIS_SEED, 0, 0, ANALYSIS), n_boot=n_boot)
    passed = bool(ten_seed and ten_seed["central_input_carried"] and ten_seed["steering_carried"]
                  and abs(ten_seed["mean_delta_steer_hz"]) >= P2_MIN_DELTA_HZ)
    run_rows = [*table, *([ten_seed] if ten_seed is not None else [])]
    result = {"stage": "VT-cal", "status": "passed" if passed else "failed",
              "declared_substrate": declared_substrate(),
              **_p2_run_context([Path(row["run_dir"]) for row in run_rows]),
              "table": table, "selected_r_vis_max_hz": selection["selected_r_vis_max_hz"],
              "sigma_vis": VT_CAL_SIGMA_VIS, "n_passing": selection["n_passing"],
              "ten_seed": ten_seed}
    record_sha = _write_p2_record("vtcal", result)
    if passed:
        document = _visual_document("TuBu", vcal_record="validation/records/p2/vtcal.json",
                                    vcal_sha256=record_sha,
                                    r_vis_max=result["selected_r_vis_max_hz"],
                                    sigma_vis=result["sigma_vis"])
        VISUAL_P2.write_text(yaml.safe_dump(document, sort_keys=False, width=120))
        result["visual_sha256"] = hash_file(VISUAL_P2)
    return {**result, "record_sha256": record_sha}


def run_4_1r() -> dict[str, Any]:
    """4.1r: the sign-check protocol at seeds 1 to 10 on the committed controller. Hz, Hz/degree."""
    from flyonenomics.orchestrator.seeds import ANALYSIS, stream

    missing = p2_missing_dependencies()
    if missing:
        return _blocked("4.1r")
    if not BEHAVIOUR_P2.is_file():
        return _blocked("4.1r", ["data/behaviour-v0.2.yaml"])
    behaviour = read_yaml(BEHAVIOUR_P2)
    run_dir = _run_experiment(_p2_experiment("signcheck.json", seeds=K3R_FINAL_SEEDS,
                                             behaviour_version="v0.2"), workers=_p2_workers())
    rows = open_loop_blocks(run_dir)
    gains, plus45, minus45 = [], [], []
    for row in rows:
        azimuths = [block["azimuth_deg"] for block in row["blocks"] if block["azimuth_deg"] is not None]
        deltas = [block["delta_hz"] for block in row["blocks"] if block["azimuth_deg"] is not None]
        by_azimuth = dict(zip(azimuths, deltas))
        gains.append(steer_gain(azimuths, deltas))
        plus45.append(by_azimuth[45.0])
        minus45.append(by_azimuth[-45.0])
    result = {"stage": "4.1r", "record": _encoder_records()["4.1r"],
              "declared_substrate": declared_substrate(), "run_dir": str(run_dir),
              **_p2_run_context([run_dir]), "gains_hz_per_deg": gains,
              **evaluate_4_1r(gains, plus45, minus45, int(behaviour["sign_steer"]),
                              stream(P2_ANALYSIS_SEED, 0, 0, ANALYSIS),
                              int(_p2_params().get("pred.bootstrap_n")))}
    result["record_sha256"] = _write_p2_record(_encoder_records()["4.1r"], result)
    return result


def run_4_2r() -> dict[str, Any]:
    """4.2r: stripes-on beats both controls at seeds 1 to 10. Fractions, degrees."""
    missing = p2_missing_dependencies()
    if missing:
        return _blocked("4.2r")
    if not BEHAVIOUR_P2.is_file():
        return _blocked("4.2r", ["data/behaviour-v0.2.yaml"])
    arms: dict[str, list[float]] = {}
    run_dirs: list[Path] = []
    for name, experiment in load_buridan_controls().items():
        run_dir = _run_experiment(experiment, workers=_p2_workers())
        run_dirs.append(run_dir)
        metrics = model_probe_metrics(run_dir)
        arms[name] = {"fixation_index": [row["metrics"]["fixation_index"] for row in metrics],
                      "stripe_deviation_deg": [row["metrics"]["stripe_deviation_deg"] for row in metrics]}
    result = {"stage": "4.2r", "record": _encoder_records()["4.2r"],
              "declared_substrate": declared_substrate(), **_p2_run_context(run_dirs),
              **evaluate_4_2r(arms["stripes_on"], arms["stripes_off"], arms["encoder_off"])}
    result["record_sha256"] = _write_p2_record(_encoder_records()["4.2r"], result)
    return result


WAVE = ("bias", "4.1r-sign", "K3r", "4.1r", "4.2r")


def _vcal_stage_rows(record: dict[str, Any] | None) -> list[dict[str, Any]]:
    """V-cal V3 passers with their Δsteer means. Units: Hz, degrees."""
    rows = []
    for outcome in (record or {}).get("outcomes", []):
        v3 = outcome.get("v3") or {}
        v1 = outcome.get("v1") or {}
        if not v3.get("passed"):
            continue
        rows.append({"r_light_hz": outcome.get("rate_hz"), "v3_passed": True,
                     "mean_delta_steer_hz": (v1.get("delta_steer") or {}).get("mean")})
    return rows


def _open_loop_encoder(vcal: dict[str, Any] | None, vtcal: dict[str, Any] | None) -> dict[str, Any]:
    """SPEC-P2 section 3.7 step 3 encoder: V3 passer first, else the VT-cal value. Units: Hz."""
    passed = _vcal_stage_rows(vcal)
    if passed:
        best = max(passed, key=lambda row: abs(float(row.get("mean_delta_steer_hz") or 0.0)))
        return {"inject_at": "photoreceptors", "r_light": float(best["r_light_hz"]),
                "source": "visual-vcal", "mean_delta_steer_hz": best.get("mean_delta_steer_hz")}
    table = (vtcal or {}).get("table") or []
    if table:
        best = max(table, key=lambda row: abs(float(row.get("mean_delta_steer_hz") or 0.0)))
        return {"inject_at": "TuBu", "r_vis_max": float(best["r_vis_max_hz"]),
                "sigma_vis": float((vtcal or {}).get("sigma_vis") or VT_CAL_SIGMA_VIS),
                "source": "vtcal", "mean_delta_steer_hz": best.get("mean_delta_steer_hz")}
    return {}


def _commit_visual(encoder: dict[str, Any], record_name: str, record_sha: str) -> str | None:
    """Commit data/visual-v0.2.yaml for the step-3 encoder unless the bytes match. Units: none."""
    if encoder["inject_at"] == "photoreceptors":
        document = _visual_document("photoreceptors",
                                    vcal_record=f"validation/records/p2/{record_name}.json",
                                    vcal_sha256=record_sha, r_light=encoder["r_light"])
    else:
        document = _visual_document("TuBu", vcal_record=f"validation/records/p2/{record_name}.json",
                                    vcal_sha256=record_sha, r_vis_max=encoder["r_vis_max"],
                                    sigma_vis=encoder["sigma_vis"])
    encoded = yaml.safe_dump(document, sort_keys=False, width=120)
    if VISUAL_P2.is_file() and read_text(VISUAL_P2) == encoded:
        return None
    VISUAL_P2.write_text(encoded)
    return hash_file(VISUAL_P2)


def _photoreceptor_record(run_dir: Path, protocol: str, r_light: float) -> dict[str, Any]:
    """Read WP18's side-resolved V1 or full V3 observer on the final visual bytes. Hz."""
    from flyonenomics.behaviour.visual_run import record_v1, record_v3
    from flyonenomics.schema import load_experiment

    experiment = load_experiment(run_dir / "experiment.json")
    rows = [read_json(run_dir / f"arm-{experiment.arms[0].label}" / f"seed-{seed}" /
                      "metrics.json")["probes"]["0"]["visual_path"] for seed in experiment.seeds]
    identity = read_json(run_dir / "manifest.json")["identity"]
    record = (record_v1(rows, r_light=r_light, screen="ten_seed", identity=identity)
              if protocol == "v1" else record_v3(rows, r_light=r_light, identity=identity))
    return {**record, "kind": record["test_id"], "run_dir": str(run_dir)}


def run_open_loop() -> dict[str, Any]:
    """Section 3.7 step 3: open-loop encoder, V1/V3 on those bytes, bias, open-loop behaviour. Hz."""
    from flyonenomics.diagnostics.visual_path import V1_DEPTHS
    from flyonenomics.drive.rest import blob_id
    from flyonenomics.orchestrator.seeds import ANALYSIS, stream

    missing = p2_missing_dependencies("open-loop")
    if missing:
        return _blocked("open-loop", missing)
    encoder = _open_loop_encoder(_read_p2_record("visual-vcal"), _read_p2_record("vtcal"))
    if not encoder:
        return _blocked("open-loop", ["a V-cal V3 passer or a VT-cal table"])
    visual_sha = _commit_visual(encoder, encoder["source"],
                                hash_file(_p2_record_path(encoder["source"])))
    n_boot = int(_p2_params().get("pred.bootstrap_n"))
    full_populations = tuple(dict.fromkeys(name for names in V1_DEPTHS.values() for name in names))
    populations = (CENTRAL_INPUT_POPULATIONS if encoder["inject_at"] == "TuBu"
                   else full_populations)
    rates = list(dict.fromkeys((*populations, "steering_L", "steering_R")))
    photo = encoder["inject_at"] == "photoreceptors"
    v1_exp = _p2_experiment("vpath-v1.json", visual_version="v0.2", record_rates=rates,
                            meta={"visual_path_protocol": "v1"} if photo else None)
    v1_run = _run_experiment(v1_exp, workers=_p2_workers())
    run_dirs = [v1_run]
    if encoder["inject_at"] == "TuBu":
        v1 = {"kind": "V1-T", **v1t_row(
            v1_run, r_vis_max=float(encoder["r_vis_max"]), label="v1-propagation",
            rng=stream(P2_ANALYSIS_SEED, 0, 0, ANALYSIS), n_boot=n_boot)}
    else:
        v1 = _photoreceptor_record(v1_run, "v1", float(encoder["r_light"]))
    _write_p2_record(f"{v1['kind']}-open-loop", v1)
    v3 = None
    if photo:
        v3_run = _run_experiment(
            _p2_experiment("vpath-v3.json", visual_version="v0.2",
                            meta={"visual_path_protocol": "v3"}), workers=_p2_workers())
        run_dirs.append(v3_run)
        v3 = _photoreceptor_record(v3_run, "v3", float(encoder["r_light"]))
        _write_p2_record("V3-open-loop", v3)
    bias = measure_bias(record_name="bias-open-loop")
    document = _behaviour_document("open_loop", sign_steer=None, bias_hz=float(bias["bias_hz"]),
                                   k_steer=None, visual=blob_id(VISUAL_PATH),
                                   records={f"{bias['record']}.json":
                                            hash_file(_p2_record_path(bias["record"]))})
    bias_run = Path(bias["run_dir"])
    result = {"stage": "open-loop", "status": "recorded", "encoder": encoder,
              "visual_sha256": hash_file(VISUAL_P2), "visual_changed": visual_sha is not None,
              "v1": v1, "v3": v3, "bias": bias,
              "declared_substrate": declared_substrate(),
              **_p2_run_context([*run_dirs, bias_run]),
              "behaviour_sha256": _write_behaviour(document)}
    result["record_sha256"] = _write_p2_record("open-loop", result)
    return result


WP20_VARIANTS: tuple[str, ...] = tuple(
    [f"perm-{k}" for k in range(3)] + [f"jitter-{k}" for k in range(5)]
    + ["sigma_h-0", "sigma_h-20", "v_fwd-half", "v_fwd-double", "histamine-off"]
)
R48_ARMS: tuple[tuple[str, bool, str], ...] = (
    ("stripes_on", True, "on"), ("stripes_off", False, "on"), ("encoder_off", True, "off"))


def variant_settings(name: str) -> dict[str, Any]:
    """One 4.8r variant's engine settings; SPEC-P2 section 3.5. Units: per field."""
    prefix, _, suffix = name.partition("-")
    if prefix == "perm":
        return {"perm": int(suffix) + 1}
    if prefix == "jitter":
        return {"jitter": int(suffix)}
    if prefix == "sigma_h":
        return {"sigma_h": float(suffix)}
    if name == "v_fwd-half":
        return {"v_fwd_scale": 0.5}
    if name == "v_fwd-double":
        return {"v_fwd_scale": 2.0}
    if name == "histamine-off":
        return {"histamine_off": True}
    raise ValueError(f"unknown 4.8r variant: {name}")


def _p2_visual() -> Any:
    """Committed visual settings for the encoder in force. Units: Hz, degrees."""
    from flyonenomics.drive.rest import load_visual_v02

    return load_visual_v02(VISUAL_PATH, _p2_params())


def _p2_jitter(stream_id: int, n_syn: int, params: Any) -> np.ndarray:
    """One 4.8r JITTER stream scale; log-normal sigma from Params. (n_syn,) float32."""
    from flyonenomics.orchestrator.seeds import stream
    from flyonenomics.types import JITTER

    sigma = float(params.get("artefact.jitter_sigma"))
    return stream(P2_ANALYSIS_SEED, 0, stream_id, JITTER).lognormal(
        -sigma * sigma / 2, sigma, n_syn).astype(np.float32)


def _connection_sign_scale(base_scale: np.ndarray, i_pre: np.ndarray,
                           photoreceptor: np.ndarray) -> np.ndarray:
    """Put only photoreceptor connection rows back at file sign. (n_syn,) dimensionless."""
    scale = np.asarray(base_scale, dtype=np.float32).copy()
    pre = np.asarray(i_pre, dtype=np.int32)
    mask = np.asarray(photoreceptor, dtype=bool)
    if pre.shape != scale.shape or (len(pre) and (int(pre.min()) < 0 or int(pre.max()) >= len(mask))):
        raise ValueError("4.8r connection arrays do not match the substrate scale")
    scale[mask[pre]] = 1.0
    return scale


def _buridan_variant_scale(context: dict[str, Any], settings: dict[str, Any]) -> np.ndarray:
    """Weight scale for one 4.8r variant; (n_syn,) float32. Units: dimensionless."""
    if "histamine_off" not in settings:
        return np.asarray(context["scale"], dtype=np.float32)
    from flyonenomics.connectome_arrays import connectome_source_paths, load_connectome_arrays
    from flyonenomics.substrate.transmitters import PHOTORECEPTOR_TYPES, annotations_in_engine

    frame, _order = annotations_in_engine()
    photoreceptor = frame["cell_type"].fillna("").isin(PHOTORECEPTOR_TYPES).to_numpy()
    completeness, connectivity = connectome_source_paths("783")
    _roots, i_pre, _j_post, _weights = load_connectome_arrays(completeness, connectivity)
    # The rest scale already contains scope, optic-exemption and GABA-to-KC
    # factors. Preserve every non-photoreceptor byte and put only connection
    # rows from photoreceptors back at their connection-file sign (scale 1).
    return _connection_sign_scale(context["scale"], i_pre, photoreceptor)


def _buridan_probe(context: dict[str, Any], settings: dict[str, Any], *,
                   stripes: bool, encoder: str,
                   seeds: tuple[int, ...]) -> dict[str, list[Any]]:
    """Run one 4.8r arm directly; per-seed FI and deviation. Fractions, degrees."""
    from types import SimpleNamespace

    from flyonenomics.drive.rest import rest_background_weights
    from flyonenomics.neuromod.state import Neuromod
    from flyonenomics.orchestrator.seeds import BEHAVIOUR, ENCODER, brian_seed, stream
    from flyonenomics.schema.experiment import Probe
    from flyonenomics.types import LayerFlags

    params, registry, drive = context["params"], context["registry"], context["drive"]
    visual = _p2_visual()
    behaviour = read_yaml(BEHAVIOUR_P2)
    v_fwd = float(behaviour["v_fwd_mm_s"]) * float(settings.get("v_fwd_scale", 1.0))
    r_vis = float(visual.r_light) if visual.inject_at == "photoreceptors" else float(visual.r_vis_max)
    probe = Probe.model_validate({
        "type": "probe", "assay": "buridan", "duration_s": BURIDAN_S, "label": "4.8r",
        "params": {"stripes": stripes, "encoder": encoder, "inject_at": visual.inject_at,
                   "initial_heading": "random"}})
    arena = Behaviour(SimpleNamespace(topology=context["topology"]), registry, params, probe,
                      v_fwd=v_fwd, sign_steer=int(behaviour["sign_steer"]),
                      K_steer=float(behaviour["K_steer"]), r_vis_max=r_vis,
                      sigma_vis=float(visual.sigma_vis or VT_CAL_SIGMA_VIS),
                      bias_hz=float(behaviour["bias_hz"]))
    scale = _buridan_variant_scale(context, settings)
    records: list[dict[str, Any]] = []
    for seed in seeds:
        engine = context["engine"]
        engine.restore("initial")
        engine.set_weight_scale(scale)
        engine.seed(brian_seed(P2_ANALYSIS_SEED, seed, 0))
        arena.reset(stream(P2_ANALYSIS_SEED, seed, 0, BEHAVIOUR))
        arena.encoder_stream = stream(P2_ANALYSIS_SEED, seed, 0, ENCODER)
        if settings.get("perm"):
            arena.permutation(int(settings["perm"]))
        if settings.get("jitter") is not None:
            jitter = _p2_jitter(int(settings["jitter"]), engine.n_syn, params)
            engine.set_weight_scale(np.asarray(scale * jitter, dtype=np.float32))
        mod = Neuromod(registry, params, LayerFlags(background=True, dopamine_A=True, transporter_C=True),
                       read_yaml(ROOT / "data/dopamine-v0.2.yaml"), base_v_th=context["base"],
                       schema_version="1.3", drive_groups=context["groups"])
        mod.clamp_pools(True)
        mod.reset_fast()
        composed = mod.compose()
        engine.set_threshold(composed.v_th)
        engine.set_gain(composed.gain)
        engine.compose_refractory()
        engine.set_background(rest_background_weights(registry, drive, params))

        def stimulus(engine: Any = engine, arena: Any = arena) -> None:
            engine.set_input_rates(arena.rates(arena.view(), 0))

        settle = mod.settle(engine, stimulus,
                            [registry.population("steering_L"), registry.population("steering_R")])
        chunk_ms = int(params.get("engine.chunk_ms"))
        remaining = int(round(BURIDAN_S * 1000))
        elapsed = 0.0
        while remaining > 0:
            chunk = min(chunk_ms, remaining)
            engine.set_input_rates(arena.rates(arena.view(), elapsed))
            result = engine.run_chunk(chunk)
            mod.on_chunk(result.counts, chunk / 1000.0)
            composed = mod.compose()
            engine.set_threshold(composed.v_th)
            engine.set_gain(composed.gain)
            arena.step(result.counts, chunk / 1000.0)
            elapsed += chunk / 1000.0
            remaining -= chunk
        records.append({"metrics": arena.metrics(), "settle_s": float(settle.settle_s),
                        "settled": bool(settle.converged)})
    return {"seeds": list(seeds),
            "fixation_index": [row["metrics"]["fixation_index"] for row in records],
            "stripe_deviation_deg": [row["metrics"]["stripe_deviation_deg"] for row in records],
            "settle_s": [row["settle_s"] for row in records],
            "settled": [row["settled"] for row in records]}


def run_4_8r() -> dict[str, Any]:
    """4.8r sensitivity: the 4.2r conclusion under the 13 section 3.5 variants. Fractions, degrees.

    Class development. A direct driver applies the within-eye permutations,
    jitter streams, `sigma_h`, `v_fwd` and photoreceptor-sign variants to one
    built engine; histamine-off recomposes the weight scale at the
    connection-file sign.
    """
    if p2_missing_dependencies():
        return _blocked("4.8r")
    if not BEHAVIOUR_P2.is_file():
        return _blocked("4.8r", ["data/behaviour-v0.2.yaml"])
    behaviour = read_yaml(BEHAVIOUR_P2)
    if behaviour.get("controller") != "closed_loop":
        return _blocked("4.8r", ["a closed-loop data/behaviour-v0.2.yaml"])
    base_record_name = _encoder_records()["4.2r"]
    base_record = _read_p2_record(base_record_name)
    if not base_record or base_record.get("outcome") not in ("passed", "failed"):
        return _blocked("4.8r", [f"validation/records/p2/{base_record_name}.json"])
    from flyonenomics.drive.background import group_indices
    from flyonenomics.drive.rest import apply_rest_substrate, load_drive_rest
    from flyonenomics.engine import BrianEngine, InputTopology
    from flyonenomics.orchestrator.workers import connectome_files
    from flyonenomics.registry import build_registry
    from flyonenomics.validation.artefacts import photoreceptor_sign_detector
    from flyonenomics.validation.binding import platform_id

    params = _p2_params()
    base_sigma_h = float(params.get("arena.sigma_h"))
    registry = build_registry("783", populations_path=ROOT / "data/populations-v0.2.yaml")
    drive = load_drive_rest(ROOT / "data/drive-v0.2.yaml")
    visual = _p2_visual()
    injection = "R1_6" if visual.inject_at == "photoreceptors" else visual.inject_at
    extended = np.sort(np.asarray(registry.population(injection).idx, dtype=np.int32))
    topology = InputTopology(background=True, extended_idx=extended,
                             trace_idx=np.zeros(0, dtype=np.int32))
    engine = BrianEngine()
    engine.seed(P2_ANALYSIS_SEED)
    engine.build(connectome_files("783"), params, topology, mechanisms=None)
    base, scale = apply_rest_substrate(engine, params, drive)
    engine.store("initial")
    context = {"engine": engine, "registry": registry, "drive": drive, "base": base,
               "scale": scale, "topology": topology, "groups": group_indices(registry),
               "params": params}
    table: list[dict[str, Any]] = []
    for name in WP20_VARIANTS:
        settings = variant_settings(name)
        params.data["arena"]["sigma_h"]["value"] = float(settings.get("sigma_h", base_sigma_h))
        arms = {arm[0]: _buridan_probe(context, settings, stripes=arm[1], encoder=arm[2],
                                       seeds=K3R_FINAL_SEEDS) for arm in R48_ARMS}
        evaluation = evaluate_4_2r(arms["stripes_on"], arms["stripes_off"], arms["encoder_off"])
        table.append({"variant": name, "settings": settings,
                      "4_2r_holds": evaluation["outcome"] == "passed", **evaluation})
    survived = all(row["4_2r_holds"] for row in table if row["variant"] != "histamine-off")
    histamine = next(row["outcome"] for row in table if row["variant"] == "histamine-off")
    result = {"stage": "4.8r", "status": "recorded", "class": "development",
              "substrate_id": declared_substrate_id(), "declared_substrate": declared_substrate(),
              "engine_model": engine.engine_model(), "platform": platform_id(),
              "input_population": injection, "base_4_2r_record": base_record_name,
              "base_4_2r_sha256": hash_file(_p2_record_path(base_record_name)),
              "variants": list(WP20_VARIANTS), "table": table,
              "4_2r_survives_retinotopy_and_jitter": survived,
              "photoreceptor_sign": photoreceptor_sign_detector(base_record["outcome"], histamine)}
    result["record_sha256"] = _write_p2_record("4.8r", result)
    return result


def run_wave(stages: tuple[str, ...] = WAVE) -> dict[str, Any]:
    """Run named WP20 stages in order and stop at a failure or configuration checkpoint."""
    runners = {"bias": measure_bias, "4.1r-sign": sign_check_p2, "K3r": run_k3r,
               "K3r-T": run_k3r_tubu, "VT-cal": run_vtcal, "4.1r": run_4_1r, "4.2r": run_4_2r,
               "4.8r": run_4_8r, "open-loop": run_open_loop}
    if any(stage not in runners for stage in stages):
        raise ValueError(f"unknown stage: {stages}")
    results: dict[str, dict[str, Any]] = {}
    checkpoint = None
    for index, stage in enumerate(stages):
        row = runners[stage]()
        results[stage] = row
        if row.get("status") in ("blocked", "failed") or row.get("outcome") == "failed":
            break
        visual_written = bool(row.get("visual_sha256")) and (
            stage != "open-loop" or bool(row.get("visual_changed")))
        configuration = ("data/visual-v0.2.yaml" if visual_written else
                         "data/behaviour-v0.2.yaml" if row.get("behaviour_sha256") else None)
        if configuration is not None and index + 1 < len(stages):
            checkpoint = {"after": stage, "configuration": configuration,
                          "remaining": list(stages[index + 1:])}
            break
    return {"wave": list(stages), "results": results, "checkpoint": checkpoint}


def load_buridan_controls(path: Path | None = None) -> dict[str, Any]:
    """Load the three 4.2r control experiments. Paired arms cannot differ in stripes."""
    from flyonenomics.schema import Experiment
    from flyonenomics.io import read_json
    document = read_json(path or ROOT / "data/experiments/p2/buridan-controls.json")
    required = ("stripes_on", "stripes_off", "encoder_off")
    if any(key not in document for key in required):
        raise ValueError("buridan-controls.json must hold stripes_on, stripes_off and encoder_off")
    return {key: Experiment.model_validate(document[key]) for key in required}


P2_STAGE: dict[str, Any] = {
    "bias": measure_bias,
    "4.1r-sign": sign_check_p2,
    "K3r": run_k3r,
    "K3r-T": run_k3r_tubu,
    "VT-cal": run_vtcal,
    "4.1r": run_4_1r,
    "4.2r": run_4_2r,
    "4.8r": run_4_8r,
    "open-loop": run_open_loop,
}


def main() -> None:
    """Run provisional development stages; seconds/Hz/degrees from named experiments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dev", action="store_true")
    parser.add_argument("--sign-run", type=Path)
    parser.add_argument("--skip-sign", action="store_true")
    parser.add_argument("--skip-k3", action="store_true")
    parser.add_argument("--skip-controls", action="store_true")
    args = parser.parse_args()
    if not args.dev:
        parser.error("provisional stages require --dev")
    if not args.skip_sign:
        print(json.dumps({"sign": sign_check(args.sign_run)}, default=str), flush=True)
    if not args.skip_k3:
        print(json.dumps({"K3": calibrate()}, default=str), flush=True)
    if not args.skip_controls:
        print(json.dumps({"4.2": controls_4_2()}, default=str), flush=True)


if __name__ == "__main__":
    main()
