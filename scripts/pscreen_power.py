#!/usr/bin/env python3
"""P-screen power pilot (SPEC-P2 sections 3.6 and 4.4).

Runs the section 3.6 open-loop probe for wild type and fumin, vehicle arm only,
seeds 1 to 10, on item 122's declared substrate, and writes
`validation/records/p2/pscreen-power.json`. It does not run the full P-screen
and applies no pass floor: it reports the measured per-seed values, their
seed-bootstrap intervals and the paired genotype difference.

`steer_gain` uses the probe's 13 sign-check blocks (the 4.1r protocol);
`distractor_capture_hz` uses the two 4 s capture blocks. The constant bias
cancels in both, so the behaviour file's bias is not required, but it is read
and recorded for traceability.

Usage on the box, from the repository root:

    FLYONENOMICS_CACHE_DIR=~/flyo-cache \
      .venv/bin/python scripts/pscreen_power.py --workers 8
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np

from flyonenomics.behaviour.buridan import open_loop_blocks
from flyonenomics.behaviour.metrics import (
    bootstrap_mean_interval,
    distractor_capture_hz,
    interval_excludes_zero,
    steer_gain,
)
from flyonenomics.behaviour.visual_calibration import declared_substrate
from flyonenomics.io import hash_file, read_json, read_yaml
from flyonenomics.orchestrator import run as orchestrate
from flyonenomics.orchestrator.seeds import ANALYSIS, stream
from flyonenomics.schema import load_experiment
from flyonenomics.store import ResultsStore

ROOT = Path(__file__).resolve().parents[1]
P2_FIXTURES = ROOT / "data/experiments/p2"
SOURCE_FIXTURE = "pharm-411-openloop.json"
PILOT_NAME = "pscreen-power-openloop"
RECORD_NAME = "pscreen-power"
BEHAVIOUR = ROOT / "data/behaviour-v0.2.yaml"
GENOTYPES = ("wild_type", "fumin")
SEEDS = tuple(range(1, 11))
SIGN_BLOCKS = 13
ANALYSIS_SEED = 20260912
N_BOOT = 10_000


def pilot_experiment() -> Any:
    """The source 4.11 fixture restricted to the wild-type and fumin vehicle arms."""
    source = load_experiment(P2_FIXTURES / SOURCE_FIXTURE)
    data = source.model_dump(mode="json")
    arms = [arm for arm in data["arms"]
            if (arm.get("genotype") or {}).get("named") in GENOTYPES]
    if sorted((arm["genotype"]["named"] for arm in arms)) != sorted(GENOTYPES):
        raise ValueError("source fixture is missing the wild-type or fumin vehicle arm")
    data["arms"] = arms
    data["seeds"] = list(SEEDS)
    data["name"] = PILOT_NAME
    data["description"] = (
        "P-screen power pilot: section 3.6 open-loop probe, vehicle only, "
        "wild type and fumin, seeds 1-10")
    data["meta"] = {**data.get("meta", {}), "stage": "P-screen power pilot"}
    return type(source).model_validate(data)


def bias_hz() -> float:
    """Bias in force from the committed open-loop behaviour file. Units: Hz."""
    document = read_yaml(BEHAVIOUR)
    return float(document["bias_hz"])


def per_seed_readouts(run_dir: Path, arm: str, bias: float) -> tuple[list[float], list[float]]:
    """One arm's per-seed steer_gain and distractor_capture_hz. Units: Hz/deg and Hz."""
    gains: list[float] = []
    captures: list[float] = []
    for row in open_loop_blocks(run_dir, arm=arm):
        blocks = row["blocks"]
        if len(blocks) != SIGN_BLOCKS + 2:
            raise ValueError(f"{arm} seed {row['seed']}: expected 15 blocks, got {len(blocks)}")
        sign = blocks[:SIGN_BLOCKS]
        azimuths = [block["azimuth_deg"] for block in sign]
        deltas = [block["delta_hz"] for block in sign]
        if any(azimuth is None for azimuth in azimuths):
            raise ValueError(f"{arm} seed {row['seed']}: sign block lacks an azimuth")
        gains.append(steer_gain(azimuths, deltas, bias_hz=bias))
        off, on = blocks[-2], blocks[-1]
        if off["azimuth_deg"] != -45.0 or on["azimuth_deg"] != -45.0:
            raise ValueError(f"{arm} seed {row['seed']}: capture blocks must sit at -45 degrees")
        captures.append(distractor_capture_hz(on["delta_hz"], off["delta_hz"], bias_hz=bias))
    if len(gains) != len(SEEDS):
        raise ValueError(f"{arm}: expected {len(SEEDS)} seeds, got {len(gains)}")
    return gains, captures


def summarize(values: list[float], rng: np.random.Generator) -> dict[str, Any]:
    """Mean and seed-bootstrap interval of one vector, with its excludes-zero flag."""
    interval = bootstrap_mean_interval(values, rng, N_BOOT)
    return {"per_seed": [float(value) for value in values], **interval,
            "excludes_zero": bool(interval_excludes_zero(interval["ci95"]))}


def _run_facts(run_dir: Path) -> dict[str, Any]:
    """Identity, platform and actual settle/brain/wall facts from one manifest. Mixed units."""
    manifest = read_json(run_dir / "manifest.json")
    identity = manifest.get("identity") or {}
    offsets = manifest.get("probe_offsets") or []
    if not offsets:
        raise ValueError(f"run manifest carries no probe offsets: {run_dir}")
    if not identity.get("platform"):
        raise ValueError(f"run manifest identity lacks a platform: {run_dir}")
    settle = [float(row["settle_s"]) for row in offsets]
    duration = [float(row["duration_s"]) for row in offsets]
    wall = manifest.get("wall_times") or {}
    return {
        "run_id": run_dir.name,
        "run_dir": str(run_dir),
        "platform": identity["platform"],
        "substrate_id": manifest.get("substrate_id"),
        "engine_model": manifest.get("engine_model"),
        "identity": identity,
        "settle_s": settle,
        "brain_s": float(np.sum(duration) + np.sum(settle)),
        "wall_s": float(wall.get("total_s") or 0.0),
    }


def collect(run_dir: Path) -> dict[str, Any]:
    """Build the pilot record from one completed run. Units per stored readout field."""
    experiment = load_experiment(run_dir / "experiment.json")
    labels = {arm.label: (arm.genotype.named if arm.genotype else None) for arm in experiment.arms}
    by_genotype = {name: label for label, name in labels.items()
                   if name in GENOTYPES}
    if set(by_genotype) != set(GENOTYPES):
        raise ValueError(f"pilot run does not carry both genotypes: {sorted(by_genotype)}")
    bias = bias_hz()
    rng = stream(ANALYSIS_SEED, 0, 0, ANALYSIS)
    readouts: dict[str, Any] = {}
    for metric in ("steer_gain_hz_per_deg", "distractor_capture_hz"):
        readouts[metric] = {}
    for genotype, label in by_genotype.items():
        gains, captures = per_seed_readouts(run_dir, label, bias)
        readouts["steer_gain_hz_per_deg"][genotype] = summarize(gains, rng)
        readouts["distractor_capture_hz"][genotype] = summarize(captures, rng)
    for metric, key in (("steer_gain_hz_per_deg", "steer_gain"),
                        ("distractor_capture_hz", "capture")):
        wild = np.asarray(readouts[metric]["wild_type"]["per_seed"], dtype=float)
        mutant = np.asarray(readouts[metric]["fumin"]["per_seed"], dtype=float)
        paired = (mutant - wild).tolist()
        readouts[metric]["fumin_minus_wild_type"] = summarize(paired, rng)
        readouts[metric]["plain_sentence"] = _sentence(key, readouts[metric])
    facts = _run_facts(run_dir)
    return {
        "name": RECORD_NAME,
        "class": "development",
        "compatibility": "development",
        "stage": "P-screen power pilot",
        "fixture": f"data/experiments/p2/{SOURCE_FIXTURE}",
        "seeds": list(SEEDS),
        "probe_s": 47.0,
        "bias_hz": bias,
        "genotypes": list(GENOTYPES),
        "readouts": readouts,
        "declared_substrate": declared_substrate(),
        **facts,
    }


def _sentence(key: str, metric: dict[str, Any]) -> str:
    """One plain sentence per readout and genotype on whether the interval excludes zero."""
    parts = []
    for genotype in GENOTYPES:
        row = metric[genotype]
        phrase = "excludes zero" if row["excludes_zero"] else "includes zero"
        parts.append(f"{genotype} mean {row['mean']:.6g} [{row['ci95'][0]:.6g}, "
                     f"{row['ci95'][1]:.6g}] {phrase}")
    paired = metric["fumin_minus_wild_type"]
    phrase = "excludes zero" if paired["excludes_zero"] else "includes zero"
    parts.append(f"paired fumin-minus-wild-type {paired['mean']:.6g} "
                 f"[{paired['ci95'][0]:.6g}, {paired['ci95'][1]:.6g}] {phrase}")
    return f"{key}: " + "; ".join(parts) + "."


def write_record(record: dict[str, Any]) -> Path:
    """Write the pilot record and return its path. Units per stored fields."""
    path = ROOT / "validation/records/p2" / f"{RECORD_NAME}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    record["record_sha256"] = hash_file(path)
    return path


def main(argv: list[str] | None = None) -> int:
    """Run the pilot (unless --run-dir is given), collect it and write the record."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--runs-dir", type=Path, default=ROOT / "runs")
    parser.add_argument("--run-dir", type=Path, default=None,
                        help="collect an existing run instead of starting one")
    args = parser.parse_args(argv)
    if args.run_dir is not None:
        run_dir = args.run_dir
    else:
        store = ResultsStore(args.runs_dir)
        run_id = orchestrate(pilot_experiment(), store, args.workers)
        errors = store.validate_run(run_id)
        if errors:
            raise RuntimeError("validate_run failed: " + "; ".join(errors))
        run_dir = store.run_path(run_id)
    record = collect(run_dir)
    path = write_record(record)
    print(json.dumps({"record": str(path), "run_dir": str(run_dir),
                      "readouts": record["readouts"]["steer_gain_hz_per_deg"]["plain_sentence"],
                      "capture": record["readouts"]["distractor_capture_hz"]["plain_sentence"]},
                     indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
