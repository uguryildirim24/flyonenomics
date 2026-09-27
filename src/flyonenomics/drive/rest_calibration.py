"""Resumable WP19 calibration and fresh-process rest measurements.

Only explicit stage calls execute engines or make configuration commits.
Discovery is read-only. Each child builds one network; changing background
weights restores that network, while different scales use different children.
Units: seconds, per-neuron Hz, mV, compartment µM/weighted spike.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import platform
import subprocess
import time
from concurrent.futures import ProcessPoolExecutor
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable

import numpy as np
import yaml

from flyonenomics.io import read_bytes, read_json, read_yaml
from flyonenomics.store.results import atomic_json
from flyonenomics.validation import levelrest

ROOT = Path(__file__).resolve().parents[3]
RECORDS = ROOT / "validation/records/p2"
DRIVE = ROOT / "data/drive-v0.2.yaml"
DOPAMINE = ROOT / "data/dopamine-v0.2.yaml"
FIXTURES = ROOT / "data/experiments/p2"
# SPEC-P2 2.6 step 5: with no ranked candidate, the chain may run on the
# development substrate. The switch is explicit and inherited by spawned
# workers; development records, configuration files and entries never share
# a path with the qualifying chain, and no development entry binds canonical.
SUBSTRATE_ENV = "FLYONENOMICS_REST_SUBSTRATE"
DEV_SOURCE = ROOT / "data/drive-dev-p2.yaml"
DEV_DRIVE = ROOT / "data/drive-dev-p2-k1r.yaml"
DEV_DOPAMINE = ROOT / "data/dopamine-dev-p2.yaml"
EXERCISE_NOTE = ("development exercise past Q-rest's first failure (the Q-rest outcome is Q-rest.json): "
                 "every worker path on a real engine; no entry published")
DEV_NOTE = ("development substrate (SPEC-P2 2.6 step 5, data/drive-dev-p2.yaml, no ranked candidate): "
            "qualifies nothing; no entry binds canonical")
# Explicit runtime dependencies, including registry defaults (v0.1) and
# schema default params; evidence is deliberately absent from entry inputs.
DATA_INPUTS = [f"data/{name}" for name in (
    "params-v0.1.yaml", "params-v0.2.yaml", "populations-v0.1.yaml", "populations-v0.2.yaml",
    "transmitters-v0.2.yaml", "compartments-v0.1.yaml", "receptors-v0.1.yaml",
    "dopamine-v0.1.yaml", "drugs-v0.1.yaml", "provenance.json")]


def development() -> bool:
    """True when the explicit development-substrate switch is set."""
    value = os.environ.get(SUBSTRATE_ENV, "")
    if value not in ("", "development"):
        raise ValueError(f"{SUBSTRATE_ENV} must be unset or development")
    return value == "development"


def _rec() -> Path:
    return RECORDS / "dev" if development() else RECORDS


def _drive() -> Path:
    return DEV_DRIVE if development() else DRIVE


def _dopamine() -> Path:
    return DEV_DOPAMINE if development() else DOPAMINE


def _class_fields() -> dict:
    return {"configuration_class": "development", "qualifies": "nothing", "note": DEV_NOTE} if development() else {}


def _git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).rstrip()


def _sha(path: Path) -> str:
    return hashlib.sha256(read_bytes(path)).hexdigest()


def stage_identity(*paths: Path) -> dict:
    """Bind a calibration stage to code and exact upstream bytes, including absence."""
    from flyonenomics.validation.binding import code_scope_hash
    return {"code_scope": code_scope_hash(ROOT),
            "inputs": {str(p.relative_to(ROOT)): _sha(p) if p.is_file() else None for p in paths},
            "overrides": os.environ.get("FLYONENOMICS_PARAM_OVERRIDES_JSON", ""),
            **({"substrate": "development"} if development() else {})}


def require_clean() -> None:
    """Qualification executions and configuration commits require a clean tree."""
    if _git("status", "--porcelain"):
        raise RuntimeError("WP19 freeze/execution requires a clean tree; commit the code/evidence checkpoint first")


def save_stage(name: str, record: dict, identity: dict | None = None) -> dict:
    """Write the dispatcher's exact record shape so its subsequent write is idempotent."""
    record = {**record, **_class_fields(),
              "input_identity": identity if identity is not None else STAGE[name].input_identity()}
    path=_rec() / f"{name}.json"
    if path.is_file():
        previous=read_json(path)
        if previous != record:
            atomic_json(_rec() / f"wp19-{name}-{_sha(path)[:16]}.json",previous)
    atomic_json(path, record)
    return record


def freeze_configuration(path: Path, document: dict) -> str:
    """Commit precisely one numeric configuration; return commit SHA, never a flag."""
    if path not in (_drive(), _dopamine()):
        raise ValueError("WP19 can freeze only its drive and dopamine files")
    if "qualified" in document or "provenance" not in document:
        raise ValueError("configuration requires provenance and forbids qualification flags")
    if development() != (document.get("configuration_class") == "development"):
        raise ValueError("a development configuration is written only by the development chain, and always says so")
    require_clean()
    encoded = yaml.safe_dump(document, sort_keys=False)
    if path.is_file() and read_bytes(path) == encoded.encode():
        return _git("rev-parse", "HEAD")
    path.write_text(encoded)
    _git("add", "--", str(path.relative_to(ROOT)))
    _git("commit", "-m", f"calibration(w19{'-dev' if development() else ''}): freeze {path.name}", "--", str(path.relative_to(ROOT)))
    require_clean()
    return _git("rev-parse", "HEAD")


def commit_records(message: str) -> str:
    """Checkpoint only WP19 stage/entry evidence; refuse unrelated dirty files."""
    paths = _git("status", "--porcelain", "--untracked-files=all").splitlines()
    records = _rec().relative_to(ROOT).as_posix()
    allowed = []
    for row in paths:
        rel = row[3:]
        p = Path(rel)
        if (p.parent.as_posix() == records and
                (p.stem in ("C0", "R4", "K1r", "drive", "K2r", "Q-rest", "B1-rest", "B2-rest")
                 or p.stem.startswith(("wp19-", "entry-")))):
            allowed.append(rel)
        else:
            raise RuntimeError(f"uncommitted file outside WP19 evidence: {rel}")
    if allowed:
        _git("add", "--", *allowed)
        _git("commit", "-m", message.replace("calibration(w19)", "calibration(w19-dev)") if development() else message)
    return _git("rev-parse", "HEAD")


def select_candidate(ranked: list[dict], visual: dict, *, elapsed_hours: float,
                     excluded: set[str] | None = None) -> dict:
    """Pure R4 decision on WP17's already-ranked list and WP18 R3 rows."""
    excluded = excluded or set()
    remaining = [c for c in ranked if str(c["id"]) not in excluded]
    if not remaining:
        return {"status": "failed", "outcome": "P2-partial-B", "reason": "ranked candidates exhausted"}
    passing = {str(r["candidate_id"]) for r in visual.get("candidates", []) if r.get("passed") is True}
    selected = next((c for c in remaining if str(c["id"]) in passing), None)
    if selected is not None:
        return {"status": "passed", "candidate": selected, "reason": "first ranked R3 passer"}
    if elapsed_hours >= 12 or visual.get("status") in ("passed", "failed", "recorded"):
        return {"status": "passed", "candidate": remaining[0],
                "reason": "12-hour R3 deadline" if elapsed_hours >= 12 else "no screened R3 passer"}
    return {"status": "blocked", "reason": "R3 has no passer yet; shortlist deadline has not elapsed"}


def fall_through(table: str, candidate_id: str, failed_ids: list[str], ranked_ids: list[str]) -> dict:
    """Bounded T -> C -> remaining ranked candidates -> escalation decision."""
    if table not in ("T","C"):raise ValueError("unknown drive table")
    if table=="T":return {"required":"common table C","failed_candidates":failed_ids,"candidate_id":candidate_id}
    failed=list(dict.fromkeys([*failed_ids,candidate_id]))
    remaining=[c for c in ranked_ids if c not in failed]
    if len(failed)>=3 or not remaining:
        return {"required":"escalation","outcome":"P2-partial-B","failed_candidates":failed,
                "reason":"three candidates failed Q-rest" if len(failed)>=3 else "ranked list exhausted"}
    return {"required":"next ranked candidate","failed_candidates":failed,"remaining":remaining}


def _decision_body(record: dict) -> dict:
    """WP17 nested decision block, or the record itself when ranked sits at the top."""
    inner = record.get("decision")
    return inner if isinstance(inner, dict) else record


def _escalated(record: dict) -> bool:
    """True when WP17 recorded P2-partial-B on this record (nested or top-level)."""
    body = _decision_body(record)
    return (body.get("status") == "P2-partial-B" or record.get("outcome") == "P2-partial-B"
            or record.get("decision_status") == "P2-partial-B")


def _mechanism_not_in_force(record: dict) -> bool:
    """True when a row's engine_model disagrees with the engine's report."""
    lines: list[Any] = []
    if not isinstance(record, dict):
        return False
    for key in ("rows", "candidates", "evaluations"):
        value = record.get(key)
        if isinstance(value, list):
            lines.extend(value)
    for line in lines:
        if not isinstance(line, dict):
            continue
        named = line.get("engine_model")
        reported = line.get("engine_model_observed")
        if named is not None and reported is not None and named != reported:
            return True
    return False


def _ranked_identity(candidate: dict) -> str:
    """WP17 six-tuple id, or the tier-3 identifier when a mechanism is on."""
    keys = ("g_gaba", "g_glu", "sigma_th", "optic_exemption", "n_bg", "w_bg")
    base = "-".join(str(candidate[k]) for k in keys)
    model = candidate.get("engine_model")
    if not model and "mechanisms" in candidate:
        from flyonenomics.drive.mechanisms import engine_model_of
        model = engine_model_of(candidate.get("mechanisms"))
    if model in ("lif+sfa", "lif+std", "lif+cbi"):
        if candidate.get("candidate_id"):
            return str(candidate["candidate_id"])
        from flyonenomics.drive.rest_tier3 import candidate_id
        return candidate_id({**candidate, "engine_model": model})
    return base


def ranked_candidates(record: dict | list) -> list[dict]:
    """Read WP17's committed summary (decision.ranked), preserving its total order.

    IDs use WP17 candidate_id's parameter tuple, not row indices or a new rank.
    A flattened ranked list is also accepted for constructed/imported records.
    engine_model and mechanisms stay on the row; a mechanism id includes them.
    """
    if isinstance(record, list):
        record = {"status": "passed", "decision": {"status": "ranked", "ranked": record}}
    decision=_decision_body(record)
    if record.get("status") not in ("passed","recorded") and not _escalated(record):
        raise ValueError("WP17 R2 is not complete")
    values=decision.get("ranked")
    if not isinstance(values,list):
        values=record.get("ranked")
    if not isinstance(values,list):raise ValueError("WP17 R2 ranked-list interface unavailable")
    if not values and not _escalated(record):
        raise ValueError("empty ranking without WP17 escalation")
    ranked=[]
    for value in values:
        c=dict(value)
        for key,default in (("sigma_th",0.),("optic_exemption",False),("n_bg",100)):
            c.setdefault(key,default)
        for key in ("g_gaba","g_glu","sigma_th","n_bg","w_bg"):
            if key not in c or not np.isfinite(float(c[key])):raise ValueError(f"invalid candidate {key}")
        c.setdefault("id", _ranked_identity(c))
        ranked.append(c)
    if len({c["id"] for c in ranked})!=len(ranked):raise ValueError("duplicate ranked candidate identity")
    return ranked


def jitter_scale(n_syn: int, stream_id: int, params: Any) -> np.ndarray:
    """Phase 1-compatible JITTER streams: master S, seed 0, probe j, float32 scale."""
    from flyonenomics.orchestrator.seeds import stream
    from flyonenomics.types import JITTER
    if stream_id not in range(int(params.get("artefact.jitter_seeds"))):raise ValueError("unknown JITTER stream")
    sigma=float(params.get("artefact.jitter_sigma"))
    return stream(20260912,0,stream_id,JITTER).lognormal(-sigma*sigma/2,sigma,n_syn).astype(np.float32)


def r2_path() -> Path:
    """WP17's committed decision record, or a tier-3 ranked list.

    Prefer a dispatcher-written R2.json. Else a sub-tier decision record
    that holds a nonempty ranked list (3c, then 3b, then 3a). Else prefer
    the tier-2 stage-2 record when it holds P2-partial-B: rest-R2-decision.json
    still says status failed / decision.status tier2 after the empty ranked
    list (F2). Else WP17's own name.
    """
    named = RECORDS / "R2.json"
    if named.is_file():
        return named
    for name in ("rest-T3c-decision.json", "rest-T3b-decision.json", "rest-T3a-decision.json"):
        path = RECORDS / name
        if not path.is_file():
            continue
        record = read_json(path)
        ranked = record.get("ranked")
        if not isinstance(ranked, list):
            ranked = (record.get("decision") or {}).get("ranked")
        if isinstance(ranked, list) and ranked:
            return path
    stage2 = RECORDS / "rest-tier2-stage2.json"
    if stage2.is_file():
        record = read_json(stage2)
        if (record.get("decision_status") == "P2-partial-B"
                or (record.get("decision") or {}).get("status") == "P2-partial-B"):
            return stage2
    return RECORDS / "rest-R2-decision.json"


def ranked_ids() -> list[str]:
    if development():
        return [str(read_json(_rec() / "R4.json")["candidate"]["id"])]
    return [str(c["id"]) for c in ranked_candidates(read_json(r2_path()))]


def development_candidate() -> dict:
    """R4 on the development substrate: SPEC-P2 2.6 step 5, only with no ranked candidate."""
    from flyonenomics.drive.rest import load_drive_rest
    path = r2_path()
    if not path.is_file():
        raise ValueError("no WP17 decision record")
    decision = read_json(path)
    body = _decision_body(decision)
    ranked = body.get("ranked")
    if not isinstance(ranked, list):
        raise ValueError("WP17 decision record has no ranked list")
    if ranked:
        raise ValueError("a ranked candidate exists; the development substrate is not selected")
    rel = DEV_SOURCE.relative_to(ROOT).as_posix()
    if not DEV_SOURCE.is_file() or not _git("log", "-1", "--format=%H", "--", rel):
        raise ValueError(f"{rel} is not committed")
    raw = read_yaml(DEV_SOURCE)
    if raw.get("configuration_class") != "development":
        raise ValueError(f"{rel} is not class development")
    drive = load_drive_rest(DEV_SOURCE)
    weights = {w for g, w in drive["w_bg"].items() if g != "sensory"}
    if len(weights) != 1 or drive["w_bg"].get("sensory") != 0:
        raise ValueError(f"{rel} is not a common-weight table")
    candidate = {"id": str(raw["candidate_id"]), "g_gaba": drive["g_gaba"], "g_glu": drive["g_glu"],
                 "sigma_th": drive["sigma_th"], "optic_exemption": drive["optic_exemption"],
                 "n_bg": int(drive["n_bg"]), "w_bg": weights.pop(), "scope": drive["scope"]}
    if drive.get("sigma_th"):
        candidate["seed"] = int(drive["seed"])
    inner_status = body.get("status", decision.get("decision_status"))
    reason = (f"SPEC-P2 2.6 step 5: no ranked candidate ({path.relative_to(ROOT).as_posix()} "
              f"status {decision.get('status')}, decision.status {inner_status}, ranked []); "
              f"development substrate {rel} chosen")
    return {"candidate": candidate, "reason": reason,
            "decision_record": {"path": path.relative_to(ROOT).as_posix(), "sha256": _sha(path)},
            "source": {"path": rel, "sha256": _sha(DEV_SOURCE), "commit": _git("log", "-1", "--format=%H", "--", rel)},
            "R3": "not run: WP18 has no visual screen on the development substrate"}


def run_r4() -> dict:
    path = r2_path()
    if not path.is_file():
        return {"status": "blocked", "reason": "Waiting for: WP17 ranked list"}
    if not development():
        r2 = read_json(path)
        try:ranked=ranked_candidates(r2)
        except (ValueError,KeyError,TypeError) as exc:return {"status":"blocked","reason":str(exc)}
        stamp = _git("log", "-1", "--format=%ct", "--", path.relative_to(ROOT).as_posix())
        if not stamp:
            return {"status": "blocked", "reason": "WP17 ranked list is not committed"}
    visual = read_json(RECORDS / "R3.json") if (RECORDS / "R3.json").is_file() else {}
    if _mechanism_not_in_force(visual):
        return {"status": "failed", "reason": "mechanism not in force"}
    previous=read_json(_rec()/"Q-rest.json") if (_rec()/"Q-rest.json").is_file() else {}
    transition=previous.get("fall_through",{}) if previous.get("status")=="failed" else {}
    if transition.get("required")=="escalation":
        return save_stage("R4",{"status":"failed",**transition})
    if transition.get("required")=="common table C":
        prior=read_json(_rec()/"R4.json")
        result={**{k:prior[k] for k in ("candidate","source","decision_record") if k in prior},
                "status":"passed","reason":"T failed Q-rest; try C","force_common":True}
    elif development():
        try:result={"status":"passed",**development_candidate()}
        except (ValueError,KeyError,TypeError) as exc:return {"status":"blocked","reason":str(exc)}
    else:
        result = select_candidate(ranked, visual, elapsed_hours=(time.time()-int(stamp))/3600,
                                  excluded=set(transition.get("failed_candidates",[])))
    result["failed_candidates"]=transition.get("failed_candidates",[])
    return save_stage("R4", result)


def coordinate_descent(common: dict[str, float], targets: dict[str, float], evaluate: Callable,
                       *, max_evals: int = 40, bound: float = .10, min_improvement: float = .20) -> dict:
    """Bounded group-weight descent; callback measures a seed-1 2+5 s window.

    The common point counts toward the 40-evaluation cap. Invalid metrics
    cannot win, and the common point remains C when improvement is <20%.
    """
    if max_evals < 1 or max_evals > 40:
        raise ValueError("K1r permits 1 through 40 evaluations")
    history = []
    def score(weights):
        row = evaluate(dict(weights))
        valid = all(row.get(k) is not None and np.isfinite(row[k]) for k in ("F", "b", "central"))
        valid = valid and 0 <= row["F"] < 3 and 0 <= row["b"] < .05 and 0 <= row["central"] <= 8
        j = levelrest.objective(row["groups"], targets) if valid else None
        history.append({"weights": dict(weights), "J": j, "accepted_metrics": bool(valid), "measurement": row})
        return float("inf") if j is None else j
    best = dict(common)
    initial = best_j = score(best)
    step = bound / 2
    while len(history) < max_evals and step >= .00625:
        improved = False
        for group in sorted(targets):
            for direction in (-1, 1):
                if len(history) >= max_evals:
                    break
                candidate = dict(best)
                candidate[group] = float(np.clip(best[group]+direction*step, common[group]-bound, common[group]+bound))
                if candidate == best or any(h["weights"] == candidate for h in history):
                    continue
                j = score(candidate)
                if j < best_j:
                    best, best_j, improved = candidate, j, True
        if not improved:
            step /= 2
    improvement = (initial-best_j)/initial if np.isfinite(initial) and initial > 0 else 0.0
    tuned = improvement >= min_improvement and np.isfinite(best_j)
    return {"status": "passed", "table": "T" if tuned else "C", "weights": best if tuned else common,
            "common": common, "tuned": best, "improvement": improvement,
            "initial_J": initial if np.isfinite(initial) else None,
            "best_J": best_j if np.isfinite(best_j) else None, "evaluations": history}


def _threshold_seed(candidate: dict) -> int:
    """Seed the committed drive file records. Never a module constant (decision 45)."""
    if "seed" not in candidate:
        raise ValueError("a candidate with sigma_th > 0 must record the threshold seed its evaluations used")
    return int(candidate["seed"])


def make_drive(candidate: dict, groups: dict[str, Any] | None = None, weights: dict[str, float] | None = None,
               *, scale_sha: str | None = None, threshold_sha: str | None = None, evidence: dict | None = None) -> dict:
    """Build the loader's versioned numeric document without qualification evidence fields.

    A constructed ranked-list row may be passed alone; that path returns the
    mechanisms section for the WP24 round-trip. Full documents always carry it.
    """
    from flyonenomics.drive.mechanisms import mechanisms_section
    from flyonenomics.validation.binding import blob_id
    section = mechanisms_section(candidate)
    if groups is None:
        return {"mechanisms": section}
    if weights is None or scale_sha is None or evidence is None:
        raise ValueError("make_drive needs groups, weights, scale_sha and evidence")
    sigma = float(candidate.get("sigma_th", 0))
    return {"version": "v0.2", "transmitter_rule": {"blob_id": blob_id(ROOT,"data/transmitters-v0.2.yaml"),
            "scope": candidate.get("scope", "brain")},
            "scales": {"g_gaba": float(candidate["g_gaba"]), "g_glu": float(candidate["g_glu"]),
                       "g_his": 1.0, "unk": "positive:1; negative:g_gaba", "sha256": scale_sha},
            "background": {"n_bg": int(candidate.get("n_bg",100)), "r_bg": 10.,
                           "groups": {g: {"size": len(idx), "w_bg": 0. if g == "sensory" else float(weights[g])}
                                      for g,idx in groups.items()}},
            "threshold": {"sigma_th": sigma,"seed":_threshold_seed(candidate),"z_sha256":threshold_sha} if sigma else None,
            "optic_exemption": bool(candidate.get("optic_exemption",False)), "provenance": evidence,
            "mechanisms": section}


def _candidate_drive(candidate: dict) -> tuple[dict, Any, Any]:
    """Materialize a selected common-weight candidate in memory, without an engine."""
    from flyonenomics.registry import build_registry
    from flyonenomics.drive.background import group_indices
    from flyonenomics.drive.rest import apply_rest_substrate, draw_threshold_z, z_sha256
    from flyonenomics.drive.mechanisms import mechanisms_section
    from flyonenomics.types import load_params
    p = load_params(ROOT / "data/params-v0.2.yaml")
    registry = build_registry("783", populations_path=ROOT / "data/populations-v0.2.yaml")
    groups = group_indices(registry)
    c = dict(candidate)
    c.setdefault("n_bg", int(p.get("bg.n_bg")))
    c.setdefault("scope", "brain")
    # This lightweight target captures only the scale; no Brian2 import/build.
    class ScaleTarget:
        n = registry.n
        def set_weight_scale(self, value): self.scale = value
    target = ScaleTarget()
    sigma = float(c.get("sigma_th", 0))
    settings = {"g_gaba":c["g_gaba"], "g_glu":c["g_glu"], "g_his":1.,
                "sigma_th":sigma, "scope":c["scope"], "optic_exemption":c.get("optic_exemption",False),
                "mechanisms": mechanisms_section(c)}
    if sigma:
        settings["seed"] = _threshold_seed(c)
    apply_rest_substrate(target,p,settings)
    scale_sha = hashlib.sha256(np.ascontiguousarray(target.scale,dtype=np.float32).tobytes()).hexdigest()
    z_sha = z_sha256(draw_threshold_z(settings["seed"],registry.n)) if sigma else None
    common = {g:0. if g == "sensory" else float(c["w_bg"]) for g in groups}
    drive = make_drive(c,groups,common,scale_sha=scale_sha,threshold_sha=z_sha,evidence={})
    drive["background"]["r_bg"] = float(p.get("bg.r_bg"))
    return drive, registry, p


def run_k1r() -> dict:
    commit_records("calibration(w19): checkpoint selection")
    r4 = read_json(_rec() / "R4.json")
    if r4.get("status") != "passed":
        return {"status":"blocked", "reason":"requires passed R4"}
    if r4.get("force_common"):
        previous=read_json(_rec()/"K1r.json")
        previous.update({"weights":previous["common"],"table":"C","reason":"T failed; common-weight fall-through"})
        return save_stage("K1r",previous)
    if development():
        # The development file's own bytes (its threshold seed and z hash), not a re-materialization.
        if _sha(DEV_SOURCE) != r4["source"]["sha256"]:
            raise RuntimeError("development source changed after R4")
        drive = read_yaml(DEV_SOURCE)
    else:
        drive, _, _ = _candidate_drive(r4["candidate"])
    row = k1r_speculative(drive)
    row["drive_template"] = drive
    return save_stage("K1r", row)


K1R_COMPARED = ("groups", "F", "b", "central", "DAN", "KC", "mn9_hz", "R_c", "block_fano", "settled")


def _weights_key(weights: dict) -> str:
    return json.dumps({g: float(w) for g, w in sorted(weights.items())}, sort_keys=True)


def replay_descent(common: dict, targets: dict, cache: dict, params: Any) -> tuple[dict, list[dict]]:
    """Run the serial descent against cached rows; return it and the uncached points it asked for, in order.

    An uncached point scores as invalid (no improvement), so the requested list
    is exactly what the serial algorithm evaluates next unless one of them
    improves. With no request left, the result is the serial result.
    """
    pending: list[dict] = []
    def lookup(weights):
        key = _weights_key(weights)
        if key in cache:
            return cache[key]
        if all(_weights_key(p) != key for p in pending):
            pending.append(dict(weights))
        return {"F": None, "b": None, "central": None, "groups": {}}
    result = coordinate_descent(common, targets, lookup, bound=params.get("k1r.bound_mv"),
                                min_improvement=params.get("k1r.min_improvement"))
    return result, pending


def k1r_speculative(drive_document: dict, *, workers: int | str = "auto") -> dict:
    """K1r with speculative parallel evaluations and the serial algorithm's exact result.

    Deviation for r14b (SPEC-P2 2.5 names one engine): a serial 40-evaluation K1r
    is about 280 brain s at q1, over an hour. Each round evaluates, in fresh
    processes, the next points the serial descent would request; the descent is
    replayed from the cache until it requests nothing. One extra job evaluates the
    first two points in one process, as the serial worker does, and the record
    states whether the second is bitwise equal to its fresh-process evaluation.
    """
    from flyonenomics.orchestrator.budget import core_cap, memory_cap
    params = _params()
    loaded = load_drive_rest_document(drive_document)
    common = loaded["w_bg"]
    targets = {g: float(params.get(f"bg.target.{g if g in ('central','DAN','KC','ER','descending','motor') else 'other'}"))
               for g in common if g != "sensory"}
    batch = max(1, min(core_cap(), memory_cap()) if workers == "auto" else int(workers))
    cache: dict[str, dict] = {}
    rounds = []
    serial_check = None
    start = time.perf_counter()
    while True:
        result, pending = replay_descent(common, targets, cache, params)
        if not pending:
            break
        todo = pending[:batch]
        jobs = [{"kind": "K1r-eval", "drive_document": drive_document, "seed": 1, "weights_list": [w]} for w in todo]
        check = serial_check is None and len(todo) >= 2
        if check:
            jobs.append({"kind": "K1r-eval", "drive_document": drive_document, "seed": 1, "weights_list": todo[:2]})
        out = run_jobs(jobs, workers=workers)
        rows = out["rows"]
        if check:
            pair = rows.pop()["evaluations"]
            fresh = [rows[0]["evaluations"][0], rows[1]["evaluations"][0]]
            serial_check = {"weights": todo[1], "compared": list(K1R_COMPARED),
                            "first_equal": all(pair[0].get(k) == fresh[0].get(k) for k in K1R_COMPARED),
                            "bitwise_equal": all(pair[1].get(k) == fresh[1].get(k) for k in K1R_COMPARED)}
        for weights, row in zip(todo, rows):
            cache[_weights_key(weights)] = row["evaluations"][0]
        rounds.append({"requested": len(pending), "evaluated": len(todo), "benchmark": out["benchmark"]})
    used = {_weights_key(h["weights"]) for h in result["evaluations"]}
    wall = time.perf_counter() - start
    brain = sum(r["benchmark"]["brain_s"] for r in rounds)
    b1 = read_json(_rec()/"B1-rest.json") if (_rec()/"B1-rest.json").is_file() else {}
    q1 = float(b1.get("q1", 27.))
    serial_brain = 7.0 * len(result["evaluations"])
    return {**result, "targets": targets, "serial_equivalence": serial_check,
            "execution": {"mode": "speculative parallel, serial result", "rounds": rounds, "cache_size": len(cache),
                          "evaluations_used": len(used), "speculative_unused": len(cache) - len(used & set(cache)),
                          "total_wall_s": wall, "brain_s_executed": brain, "serial_brain_s": serial_brain,
                          "serial_budget_s": 1.25 * q1 * serial_brain, "q1": q1,
                          "within_serial_budget": wall <= 1.25 * q1 * serial_brain,
                          "deviation": "SPEC-P2 2.5 K1r one engine: speculative parallel rounds, exact serial replay"}}


def load_drive_rest_document(document: dict) -> dict:
    """Validate an in-memory drive document through the file loader."""
    import tempfile
    from flyonenomics.drive.rest import load_drive_rest
    (ROOT / ".cache").mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="wp19-drive-", dir=ROOT / ".cache") as tmp:
        path = Path(tmp) / "drive.yaml"
        path.write_text(yaml.safe_dump(document, sort_keys=False))
        return load_drive_rest(path)


def run_drive() -> dict:
    record = read_json(_rec() / "K1r.json")
    if record.get("status") != "passed":
        return {"status":"blocked", "reason":"requires K1r"}
    if _mechanism_not_in_force(record):
        return {"status": "failed", "reason": "mechanism not in force"}
    commit_records("calibration(w19): checkpoint R4 and K1r evidence")
    document = deepcopy(record["drive_template"])
    for g,w in record["weights"].items(): document["background"]["groups"][g]["w_bg"] = w
    upstream = {"R2": r2_path(), "R3": RECORDS/"R3.json", "R4": _rec()/"R4.json", "K1r": _rec()/"K1r.json"}
    records_sha = {n: _sha(p) if p.is_file() else None for n, p in upstream.items()}
    if development():
        source = document.pop("provenance")
        document = {"configuration_class": "development", "note": DEV_NOTE,
                    **{k: v for k, v in document.items() if k != "configuration_class"}}
        document["provenance"] = {"records_sha256": records_sha, "table": record["table"],
                                  "source": {"path": DEV_SOURCE.relative_to(ROOT).as_posix(), "sha256": _sha(DEV_SOURCE)},
                                  "camber_job_ids": source.get("camber_job_ids", {})}
    else:
        document["provenance"] = {"records_sha256": records_sha,
                                  "camber_job_ids": sorted({str(r["job_id"]) for c in ranked_candidates(read_json(r2_path()))
                                                             for r in c.get("provenance",[]) if r.get("job_id") is not None})}
    sha = freeze_configuration(_drive(),document)
    return save_stage("drive", {"status":"passed", "configuration_commit":sha, "table":record["table"], "sha256":_sha(_drive())})


def _worker(job: dict) -> dict:
    """One spawned process, one built network, compact streaming measurements."""
    import resource
    from types import SimpleNamespace
    from flyonenomics.io import clear_log, flush, logged_paths, set_log_dir, set_repo_root
    from flyonenomics.engine import BrianEngine, InputTopology
    from flyonenomics.engine.base import UpstreamBank
    from flyonenomics.drive.background import group_indices
    from flyonenomics.drive.rest import apply_rest_substrate, load_drive_rest, load_dopamine_v02, rest_background_weights
    from flyonenomics.neuromod.state import Neuromod
    from flyonenomics.neuromod.calibration import ChunkQualification
    from flyonenomics.orchestrator.seeds import brian_seed
    from flyonenomics.orchestrator.workers import connectome_files
    from flyonenomics.registry import build_registry
    from flyonenomics.types import LayerFlags, load_params, JITTER
    from flyonenomics.validation.artefacts import FanoAccumulator

    set_repo_root(ROOT); clear_log(); set_log_dir(job["deps_dir"])
    start = time.perf_counter()
    background = not job.get("bare",False)
    params = load_params(ROOT / f"data/params-{'v0.2' if background else 'v0.1'}.yaml")
    registry = build_registry("783", populations_path=ROOT / f"data/populations-{'v0.2' if background else 'v0.1'}.yaml")
    groups = group_indices(registry)
    drive = None
    if background or job.get("scales_only"):
        path = Path(job.get("drive_path",_drive()))
        if "drive_document" in job:
            path = Path(job["deps_dir"]) / f"drive-{os.getpid()}.yaml"
            path.write_text(yaml.safe_dump(job["drive_document"]))
        drive = load_drive_rest(path)
        # Section 10 reading 20 requires the matching explicit override. Keep
        # it in the job/measurement identity rather than silently substituting.
        if background and drive["n_bg"] != params.get("bg.n_bg"):
            if job.get("overrides",{}).get("bg.n_bg") != drive["n_bg"]:
                raise ValueError("tier-2 input count requires explicit bg.n_bg override")
            params.data["bg"]["n_bg"]["value"] = drive["n_bg"]
    sugar = np.asarray(registry.population("sugar_GRN_R").idx,dtype=np.int32)
    extended = np.sort(sugar) if job["kind"] != "B1-rest" else np.arange(200,dtype=np.int32)
    bitter = np.asarray(registry.population("bitter_GRN_R").idx,dtype=np.int32) if job["kind"]=="bitter" else np.zeros(0,dtype=np.int32)
    if bitter.size: extended=np.union1d(extended,bitter).astype(np.int32)
    upstream = job.get("mode") == "upstream"
    topology = InputTopology(background=background,
        extended_idx=np.zeros(0,dtype=np.int32) if upstream else extended,
        upstream_banks=[UpstreamBank(sugar,150.)] if upstream else [])
    engine = BrianEngine()
    engine.seed(brian_seed(20260912,job["seed"],0))
    from flyonenomics.drive.mechanisms import mechanisms_from_drive
    mechs = mechanisms_from_drive(drive) if drive is not None else None
    engine.build(connectome_files("783"),params,topology,mechanisms=mechs)
    base = None
    scale = np.ones(engine.n_syn,dtype=np.float32)
    if drive is not None:
        base,scale = apply_rest_substrate(engine,params,drive,thresholds=background)
    if base is not None:
        engine.set_threshold(base)
    if background:
        engine.set_background(rest_background_weights(registry,drive,params))
    if job.get("jitter_stream") is not None:
        jitter = jitter_scale(engine.n_syn,job["jitter_stream"],params)
        engine.set_weight_scale(np.asarray(scale*jitter,dtype=np.float32))
    engine.store("initial")
    build_s = time.perf_counter()-start
    chunk_ms = int(params.get("engine.chunk_ms")); step_s=chunk_ms/1000
    dopamine = (load_dopamine_v02(_dopamine(),[c.name for c in registry.compartments()])
                if background and not job.get("clamped") and job["kind"] not in ("K1r","K1r-eval","B1-rest")
                else read_yaml(ROOT / "data/dopamine-v0.1.yaml"))
    recorded = [registry.population(n) for n in ("MN9","DAN","KC","DN_all")]
    recorded.append(SimpleNamespace(name="central",idx=groups["central"]))
    times=[]; durations=[]
    built_at=time.perf_counter()

    def measure(duration: float, active: bool = False, *, weights: dict | None = None,
                fixed_settle: bool = False, clamp: bool = False, coactivate_bitter: bool = False) -> dict:
        engine.restore("initial"); engine.seed(brian_seed(20260912,job["seed"],0))
        if weights is not None:
            d=deepcopy(drive);d["w_bg"]=weights
            engine.set_background(rest_background_weights(registry,d,params))
        elif background and job.get("weight_shift"):
            d=deepcopy(drive);d["w_bg"]={g:w+(job["weight_shift"] if g!="sensory" else 0) for g,w in d["w_bg"].items()}
            engine.set_background(rest_background_weights(registry,d,params))
        mod=Neuromod(registry,params,LayerFlags(background=background),dopamine,
                     base_v_th=base,schema_version="1.3" if background else "1.2",
                     drive_groups=groups if background else None)
        mod.clamp_pools(clamp);mod.reset_fast()
        composed=mod.compose();engine.set_threshold(composed.v_th);engine.set_gain(composed.gain)
        engine.compose_refractory()
        def stimulus():
            if upstream: engine.set_upstream_active(0,active)
            else:
                input_rates=np.zeros(len(extended))
                if active:input_rates[np.isin(extended,sugar)]=150.
                if coactivate_bitter:input_rates[np.isin(extended,bitter)]=150.
                engine.set_input_rates(input_rates)
        stimulus()
        if fixed_settle:
            settle_counts=np.zeros(engine.n,dtype=np.int64)
            for _ in range(round(2/step_s)):
                result=engine.run_chunk(chunk_ms);mod.on_chunk(result.counts,step_s)
                composed=mod.compose();engine.set_threshold(composed.v_th);engine.set_gain(composed.gain)
                settle_counts+=result.counts
            settled=True;settle_s=2.;unresolved=[]
            settled_central=float(settle_counts[groups["central"]].mean()/2)
        else:
            settle=mod.settle(engine,stimulus,recorded)
            settled=settle.converged;settle_s=settle.settle_s;unresolved=settle.unresolved or []
            settled_central=float(settle.final_rates_hz[-1])
        t_record=time.perf_counter()
        counts=np.zeros(engine.n,dtype=np.int64)
        first_second=np.zeros(engine.n,dtype=np.int64)
        dan=np.zeros(len(mod.mask));da_sum=np.zeros(len(mod.mask))
        fano=FanoAccumulator(engine.n,params)
        qual=ChunkQualification(len(mod.mask),engine.n)
        group_chunks={g:[] for g in groups}
        steps=round(duration/step_s)
        if steps<1 or abs(steps*step_s-duration)>1e-9: raise ValueError("record duration must divide into chunks")
        for k in range(steps):
            result=engine.run_chunk(chunk_ms);mod.on_chunk(result.counts,step_s)
            composed=mod.compose();engine.set_threshold(composed.v_th);engine.set_gain(composed.gain)
            counts+=result.counts
            if k<round(1/step_s):first_second+=result.counts
            dan+=np.asarray(mod.m@result.counts).ravel();da_sum+=mod.da_c
            fano.add(result.hist_1ms)
            if job.get("qualify"):qual.observe(mod,engine.thresholds_mv(),engine.gains())
            for g,idx in groups.items():group_chunks[g].append(int(result.counts[idx].sum()))
        rates=counts/duration
        central=np.asarray(group_chunks["central"])/len(groups["central"])/step_s
        def edge(seconds, first):
            n=round(seconds/step_s);return float(np.mean(central[:n] if first else central[-n:]))
        report=fano.report();mn9=int(registry.population("MN9").idx[0])
        one_s=np.convolve(np.asarray(group_chunks["central"]),np.ones(round(1/step_s)),mode="valid")/len(groups["central"])
        group_rates={g:float(rates[idx].mean()) for g,idx in groups.items()}
        block_fano={}
        block_chunks=round(.2/step_s)
        for g,values in group_chunks.items():
            block=np.asarray(values).reshape(-1,block_chunks).sum(axis=1)
            block_fano[g]=float(block.var(ddof=1)/block.mean()) if block.mean()>0 and len(block)>1 else None
        row={"seed":job["seed"],"settled":settled,"settle_s":settle_s,"unresolved":unresolved,
             "duration_s":duration,"groups":group_rates,**{g:group_rates[g] for g in ("central","DAN","KC")},
             "F":report["F"],"b":report["max_bin_fraction"],
             "stability_ratio":edge(1,True)/edge(1,False) if edge(1,False)>0 else None,
             "edge_ratio":edge(5,True)/edge(5,False) if edge(5,False)>0 else None,
             "ignited":window_ignited(one_s,settled_central,params,background),
             "block_fano":block_fano,"mn9_hz":float(rates[mn9]),
             "first_second_mn9_hz":float(first_second[mn9]),"rate_safety":levelrest.rate_safety(rates),
             "stimulated_safety":levelrest.rate_safety(rates,stimulated=True),
             "R_c":(dan/duration).tolist(),"compartments":mod.compartment_names,
             "mean_da_c_um":(da_sum/steps).tolist(),"da_gap_um":mod.da_gap(da_sum/steps,dan/duration).tolist(),
             "record_wall_s":time.perf_counter()-t_record}
        if job.get("qualify"):row["qualification"]=qual.summary(mod)
        times.append(settle_s+duration);durations.append(duration)
        return row

    try:
        kind=job["kind"]
        if kind=="K1r":
            targets={g:float(params.get(f"bg.target.{g if g in ('central','DAN','KC','ER','descending','motor') else 'other'}"))
                     for g in groups if g!="sensory"}
            output=coordinate_descent(drive["w_bg"],targets,
                lambda weights:measure(5,weights=weights,fixed_settle=True,clamp=True),
                bound=params.get("k1r.bound_mv"),min_improvement=params.get("k1r.min_improvement"))
        elif kind=="K1r-eval":
            # One or more K1r evaluations in this process, in order (a list of two is the serial check).
            evaluations=[measure(5,weights=w,fixed_settle=True,clamp=True) for w in job["weights_list"]]
            output={"evaluations":evaluations}
        elif kind=="B1-rest":
            # B1 engine-only contract: no settle or neuromodulation stepping.
            engine.restore("initial");engine.set_input_rates(np.full(200,50.));engine.seed(20260912)
            t=time.perf_counter();spikes=0
            for _ in range(round(20/step_s)):spikes+=int(engine.run_chunk(chunk_ms).counts.sum())
            wall=time.perf_counter()-t;times.append(20.);durations.append(20.)
            output={"q1":wall/20,"run_s":wall,"brain_s":20.,"total_spikes":spikes}
        elif kind=="bitter":
            sugar_row=measure(1,True);both_row=measure(1,True,coactivate_bitter=True)
            output={"seed":job["seed"],"sugar_hz":sugar_row["mn9_hz"],"sugar_bitter_hz":both_row["mn9_hz"],
                    "sugar":sugar_row,"both":both_row}
        elif kind in ("reflex","ff","jitter"):
            silent=measure(1);sugar=measure(1,True)
            output={"seed":job["seed"],"silent":silent,"sugar":sugar,
                    "difference_hz":sugar["mn9_hz"]-silent["mn9_hz"],
                    "settled":silent["settled"] and sugar["settled"]}
            if kind=="jitter":
                rest=measure(10);output.update({"groups":rest["groups"],"F":rest["F"],
                    "stream":job["jitter_stream"],"rest":rest,"settled":output["settled"] and rest["settled"]})
        else:
            output=measure(float(job.get("duration_s",10)),job.get("active",False),
                           fixed_settle=kind=="K2r",clamp=job.get("clamped",False))
        output.update({"build_s":build_s,"total_wall_s":time.perf_counter()-start,
                       "brain_s":sum(times),"probe_count":len(times), "settle_total_s":sum(times)-sum(durations),
                       "built_at":built_at,"finished_at":time.perf_counter(),
                       "engine_model": engine.engine_model(),
                       "engine_model_observed": engine.engine_model(),
                       "peak_rss_mib":resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/(1024**2 if platform.system()=="Darwin" else 1024),
                       "pid":os.getpid(),"logged_inputs":logged_paths()})
        return output
    finally:
        flush()


def engine_precondition() -> dict:
    """Check this lane's engines and the swap ceiling.

    On a shared compute machine this flags only engines launched from this lane's
    own ROOT. Cross-lane concurrency is bounded by each lane's explicit worker cap.
    """
    from flyonenomics.orchestrator.budget import swap_used_mib
    commands=subprocess.check_output(["ps","-eo","pid=,command="],text=True)
    others=[]
    for line in commands.splitlines():
        if any(key in line for key in ("run_experiment.py","run_validation.py","calibrate.py","multiprocessing.spawn")):
            pid=int(line.strip().split(None,1)[0])
            if pid != os.getpid() and str(ROOT) in line:
                others.append(line.strip())
    swap=swap_used_mib()
    if others or swap>4000:
        raise RuntimeError(f"engine start blocked: other engines={others}; swap={swap} MiB")
    return {"swap_used_mib":swap,"other_engines":others,"platform":f"{platform.system().lower()}-{platform.machine()}"}


def window_ignited(one_s: np.ndarray, settled_central: float, params: Any, background: bool) -> bool | None:
    """Section 9.2 ignition on rest windows; bare feed-forward windows (params v0.1, no ign rows) record None."""
    if not background:
        return None
    from flyonenomics.validation.artefacts import ignition_detector
    return ignition_detector(one_s, settled_central, params)["tripped"]


def development_overrides(job: dict) -> dict:
    """drive-dev-p2.yaml carries n_bg 25 against params bg.n_bg 100: add the matching explicit override."""
    if not development() or job.get("bare"):
        return job
    document = job.get("drive_document") or read_yaml(Path(job.get("drive_path", _drive())))
    n_bg = document["background"]["n_bg"]
    if float(n_bg) == float(_params().get("bg.n_bg")):
        return job
    return {**job, "overrides": {**job.get("overrides", {}), "bg.n_bg": n_bg}}


def run_jobs(jobs: list[dict], *, workers: int | str = "auto") -> dict:
    """Lease the shared budget and spawn exactly one network per child/task."""
    import multiprocessing as mp
    from flyonenomics.orchestrator.budget import lease_workers
    import tempfile
    require_clean()
    from flyonenomics.validation.binding import code_scope_hash
    jobs=[development_overrides(j) for j in jobs]
    launch_scope=code_scope_hash(ROOT)
    precondition=engine_precondition()
    start=time.perf_counter()
    (ROOT/".cache").mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="wp19-",dir=ROOT/".cache") as deps:
        with lease_workers(workers,len(jobs)) as lease:
            w=lease.count
            with ProcessPoolExecutor(max_workers=w,mp_context=mp.get_context("spawn"),max_tasks_per_child=1) as pool:
                rows=list(pool.map(_worker,[{**j,"deps_dir":deps} for j in jobs]))
        missing=[r["pid"] for r in rows if not (Path(deps)/f'deps-{r["pid"]}.json').is_file()]
        if missing:raise RuntimeError(f"missing worker dependency logs: {missing}")
    if code_scope_hash(ROOT)!=launch_scope:
        raise RuntimeError("code changed during WP19 engine execution")
    wall=time.perf_counter()-start
    brain=sum(r["brain_s"] for r in rows)
    probes=sum(r["probe_count"] for r in rows)
    b1=read_json(_rec()/"B1-rest.json") if (_rec()/"B1-rest.json").is_file() else {}
    q1=float(b1.get("q1",27.))
    build=max(r["build_s"] for r in rows)
    aggregation=time.perf_counter()-max(r["finished_at"] for r in rows)
    budget=1.25*(q1 if w==1 else 27./w)*brain+len(rows)*(build+aggregation)
    return {"rows":rows,"benchmark":{"wall_budget_s":budget,"within_budget":wall<=budget,
            "budget_basis":"section 6.4: B1 q1 if serial; q_plan/w until concurrency qualified","workers":w,"total_wall_s":wall,"brain_s":brain,
            "q2_total":wall/brain,
            "probe_wall_s":max(r["finished_at"] for r in rows)-min(r["built_at"] for r in rows),
            "q2":(max(r["finished_at"] for r in rows)-min(r["built_at"] for r in rows))/brain,
            "t_build_s":min(r["built_at"] for r in rows)-start,
            "mean_settle_s":sum(r["settle_total_s"] for r in rows)/probes,
            "t_agg_s":time.perf_counter()-max(r["finished_at"] for r in rows),"peak_worker_rss_mib":max(r["peak_rss_mib"] for r in rows),
            "precondition":precondition,"probe_count":probes,
            "overrides":sorted({json.dumps(j.get("overrides",{}),sort_keys=True) for j in jobs}),**_class_fields()}}


def declared_inputs(fixture: str, *, dopamine: bool = True) -> list[str]:
    return [p for p in DATA_INPUTS if (ROOT/p).is_file()] + [
        _drive().relative_to(ROOT).as_posix(), f"data/experiments/p2/{fixture}"] + (
        [_dopamine().relative_to(ROOT).as_posix()] if dopamine else [])


def _entry_identity(fixture: str, *, dopamine: bool = True):
    from flyonenomics.drive.mechanisms import substrate_id_for
    from flyonenomics.types import LayerFlags
    from flyonenomics.validation.binding import build_identity
    return build_identity(ROOT, connectome_version="783",layers=LayerFlags(background=fixture != "ff-candidate.json"),
                          assay="spontaneous",fixture=f"data/experiments/p2/{fixture}",
                          declared_inputs=declared_inputs(fixture,dopamine=dopamine),
                          substrate_id=substrate_id_for(_drive()))


def publish_entry(test_id: str, measured: dict, identity: Any, fixture: str, *, inputs: list[str] | None = None) -> None:
    """Store a result with its launch identity, never an identity made after measurement."""
    from flyonenomics.validation.binding import ValidationEntry
    # A development entry names its provisional component; bind_entry never
    # promotes a development entry, and it is stored only under records/p2/dev.
    dev={"compatibility":"development","stub":DEV_NOTE} if development() else {}
    entry=ValidationEntry(test_id=test_id,category="calibration" if test_id in ("2.1r","3.1r") else
                          "benchmark" if test_id=="2.5r" else "consistency",
                          outcome=measured["outcome"],identity=identity,measured={**measured,**_class_fields()},**dev,
                          declared_inputs=inputs or sorted(identity.inputs),
                          fixture_path=f"data/experiments/p2/{fixture}")
    payload=entry.model_dump(mode="json")
    tag=hashlib.sha256(json.dumps(identity.inputs,sort_keys=True).encode()).hexdigest()[:16]
    atomic_json(_rec()/f"wp19-entry-{test_id}-{tag}.json",payload)
    atomic_json(_rec()/f"entry-{test_id}.json",payload)


def _score(func: Callable, *args) -> dict:
    try:return func(*args)
    except (ValueError,KeyError,TypeError) as exc:
        return {"outcome":"failed","reason":f"uncomputable criterion: {exc}","raw":args}


def run_qrest_once(*, workers: int | str = "auto", exercise: bool = False) -> dict:
    """Execute Q-rest in order on committed bytes, stopping at the first failure.

    The driver handles dopamine iteration and T -> C -> next-ranked-candidate
    fall-through separately so each new configuration has its own commit.
    exercise (development only) runs every batch in order past failures, so
    each worker path meets a real engine; it publishes no entry and writes
    wp19-exercise-<id>.json records, never the Q-rest outcome.
    """
    if exercise and not development():
        raise ValueError("the past-failure exercise exists only on the development substrate")
    require_clean()
    identity=_entry_identity("rest-short.json")
    all_batches=[];results={}
    def batch(jobs):
        out=run_jobs(jobs,workers=workers)
        all_batches.append(out["benchmark"])
        unexpected=set().union(*(set(r["logged_inputs"]) for r in out["rows"]))-allowed
        if unexpected:raise RuntimeError(f"undeclared Q-rest worker inputs: {sorted(unexpected)}")
        return out["rows"]
    def store(test_id,score,fixture="rest-short.json"):
        # One identity per entry: add its actual declared fixture before launch
        # through the same frozen input universe, without reusing other evidence.
        ident=identities[fixture]
        results[test_id]=score
        if exercise:
            atomic_json(_rec()/f"wp19-exercise-{test_id}.json",{**score,**_class_fields(),"exercise":EXERCISE_NOTE,
                        "fixture_path":f"data/experiments/p2/{fixture}","identity":ident.model_dump(mode="json"),
                        "batches":all_batches})
            commit_records(f"calibration(w19): exercise Q-rest {test_id}")
            return True
        publish_entry(test_id,score,ident,fixture)
        commit_records(f"calibration(w19): record Q-rest {test_id}")
        return score["outcome"]=="passed"
    fixture_names=("rest-short.json","rest-long.json","rest-reflex.json","ff-candidate.json","rest-bitter.json")
    identities={f:_entry_identity(f) for f in fixture_names}
    # The feed-forward comparison reads the v0.1 dopamine and both fixtures.
    from flyonenomics.validation.binding import input_blobs
    ff_extra=["data/experiments/p2/ff-bare.json"]
    identities["ff-candidate.json"].inputs.update(input_blobs(ROOT,ff_extra))
    allowed=set().union(*(set(i.inputs) for i in identities.values()))
    start=time.perf_counter()
    rows=batch([{"kind":"short","seed":s,"qualify":True} for s in range(1,4)])
    passed=store("3.1br",_score(levelrest.qualification,rows))
    if passed:
        passed=store("2.3r",_score(levelrest.screen,rows))
    if passed:
        long=batch([{"kind":"long","seed":s,"duration_s":30} for s in range(1,11)])
        passed=store("2.7r",_score(levelrest.long_window,long),"rest-long.json")
    if passed:
        shifted={shift:batch([{"kind":"margin","seed":s,"weight_shift":shift} for s in range(1,4)]) for shift in (.05,-.05)}
        passed=store("2.6r",_score(levelrest.margin,rows,shifted[.05],shifted[-.05]))
    if passed:
        stimulated=batch([{"kind":"safety","seed":0,"active":True,"duration_s":10}])[0]
        safety={"outcome":"passed" if all(r["rate_safety"]["outcome"]=="passed" and r["settled"] for r in rows) else "failed",
                "spontaneous":[r["rate_safety"] for r in rows],"stimulated_seed_0":stimulated["stimulated_safety"]}
        passed=store("2.2r",safety)
    if passed:
        paired=batch([{"kind":"reflex","seed":s} for s in range(1,11)])
        score=_score(levelrest.reflex,[r["difference_hz"] for r in paired]);score["per_seed"]=paired
        if not all(r["settled"] for r in paired):score["outcome"]="failed"
        passed=store("1.4r",score,"rest-reflex.json")
    if passed:
        levelrest.validate_ff_fixtures(FIXTURES/"ff-bare.json",FIXTURES/"ff-candidate.json")
        ff={};ff_rows={}
        for candidate in (False,True):
            tag="candidate" if candidate else "bare";ff[tag]={};ff_rows[tag]={}
            for mode in ("upstream","extended"):
                values=batch([{"kind":"ff","seed":s,"bare":True,"scales_only":candidate,"mode":mode} for s in range(1,11)])
                ff[tag][mode]=[v["difference_hz"] for v in values];ff_rows[tag][mode]=values
        score=_score(levelrest.feedforward,ff["bare"],ff["candidate"]);score["per_seed"]=ff_rows
        if not all(r["settled"] for modes in ff_rows.values() for values in modes.values() for r in values):score["outcome"]="failed"
        passed=store("1.4r-ff",score,"ff-candidate.json")
    if passed:
        baseline={"difference_hz":paired[0]["difference_hz"],"groups":rows[0]["groups"]}
        jit=batch([{"kind":"jitter","seed":1,"jitter_stream":s} for s in range(5)])
        passed=store("2.4r",_score(levelrest.jitter,baseline,jit))
    if passed:
        bitter_rows=batch([{"kind":"bitter","seed":s} for s in range(1,4)])
        bitter_score=levelrest.bitter_suppression([r["sugar_hz"] for r in bitter_rows],[r["sugar_bitter_hz"] for r in bitter_rows])
        bitter_score["per_seed"]=bitter_rows
        store("1.3r",bitter_score,"rest-bitter.json")
    k1=read_json(_rec()/"K1r.json")
    targets={g:float(_params().get(f"bg.target.{g if g in ('central','DAN','KC','ER','descending','motor') else 'other'}"))
             for g in rows[0]["groups"] if g!="sensory"}
    free_rates={g:float(np.mean([r["groups"][g] for r in rows])) for g in rows[0]["groups"]}
    store("2.1r",{"outcome":"recorded","free_group_rates_hz":free_rates,"J_free":levelrest.objective(free_rates,targets),
                   "clamped_K1r":k1})
    total_brain=sum(b["brain_s"] for b in all_batches)
    benchmark={"batches":all_batches,"total_wall_s":time.perf_counter()-start,"brain_s":total_brain,
               "q2_by_workers":{str(w):sum(b["probe_wall_s"] for b in all_batches if b["workers"]==w)/sum(b["brain_s"] for b in all_batches if b["workers"]==w)
                                for w in {b["workers"] for b in all_batches}},
               "scope":"Q-rest execution, includes feed-forward bare twins",
               "completed_all_entries":all(r.get("outcome") in ("passed","recorded") for r in results.values()) if exercise else passed}
    atomic_json(_rec()/("wp19-exercise-B2-rest.json" if exercise else "B2-rest.json"),benchmark)
    store("2.5r",{"outcome":"recorded","B2-rest":benchmark,
                    "B1-rest":read_json(_rec()/"B1-rest.json") if (_rec()/"B1-rest.json").is_file() else None})
    freeze=_git("log","-1","--format=%H","--",_dopamine().relative_to(ROOT).as_posix())
    result={"status":"exercised" if exercise else "passed" if passed else "failed","entries":results,"benchmark":benchmark,
            "configuration_commit":freeze or identity.code_commit,"drive_sha256":_sha(_drive()),"dopamine_sha256":_sha(_dopamine())}
    return result


def run_qrest_exercise() -> dict:
    """Development only: every Q-rest batch past the first failure, then one committed summary."""
    result = run_qrest_once(exercise=True)
    summary = {**result, **_class_fields(), "exercise": EXERCISE_NOTE,
               "outcomes": {k: v.get("outcome") for k, v in result["entries"].items()},
               "qrest_record_sha256": _sha(_rec()/"Q-rest.json") if (_rec()/"Q-rest.json").is_file() else None}
    atomic_json(_rec()/"wp19-exercise-summary.json", summary)
    commit_records("calibration(w19): Q-rest exercise summary")
    return summary


def _params():
    from flyonenomics.types import load_params
    return load_params(ROOT/"data/params-v0.2.yaml")


def binding_preflight() -> dict:
    """Require the no-engine algebra entry to survive actual binding as canonical.

    This also prevents a final qualification on the known metadata-log seam;
    it becomes a passing gate only after the coordinator's fix is merged.
    """
    from flyonenomics.io import clear_log, logged_paths
    from flyonenomics.validation.execute import bind_entry
    from flyonenomics.validation.binding import apply_logged_inputs
    clear_log()
    entry=bind_entry(levelrest.entry("3.1r-alg"),ROOT)
    entry=apply_logged_inputs(entry,logged_paths(),ROOT)
    ready=entry.outcome=="passed" and entry.compatibility=="canonical"
    return {"status":"passed" if ready else "blocked", "entry":entry.model_dump(mode="json"),
            "reason":"binding verified" if ready else "Phase 2 algebra/binding gate does not qualify; merge the coordinator's seam fix"}


def run_qrest() -> dict:
    """Q-rest with at most three dopamine calibrations and explicit fall-through records."""
    commit_records("calibration(w19): checkpoint dopamine freeze evidence")
    preflight=binding_preflight()
    if preflight["status"]!="passed":return preflight
    from flyonenomics.neuromod.calibration import run_k2r
    attempts=[]
    for iteration in range(1,int(_params().get("k2r.max_iterations"))+1):
        result=run_qrest_once();attempts.append(result)
        if result["status"]=="passed":
            return save_stage("Q-rest",{**result,"iterations":attempts})
        q=result["entries"]["3.1br"]
        # Only a DA-window mean failure triggers re-estimation, not a failed
        # settle, bitwise array test or modulation discrepancy alone.
        failed_da=any(r["qualification"]["max_da_error_um"]>r["qualification"]["da_bound_um"] for r in q.get("per_seed",[]))
        if not failed_da or iteration==int(_params().get("k2r.max_iterations")):break
        archive=_rec()/f"wp19-Q-rest-iteration-{iteration}-{_sha(_dopamine())[:16]}.json"
        atomic_json(archive,result);commit_records("calibration(w19): preserve failed dopamine iteration")
        run_k2r(iteration=iteration+1,free_rates=np.mean([r["R_c"] for r in q["per_seed"]],axis=0))
        commit_records("calibration(w19): checkpoint re-estimated dopamine")
    drive_record=read_json(_rec()/"drive.json")
    return save_stage("Q-rest",{**result,"iterations":attempts,
                      "fall_through":fall_through(drive_record["table"],str(read_json(_rec()/"R4.json")["candidate"]["id"]),
                                      read_json(_rec()/"R4.json").get("failed_candidates",[]),
                                      ranked_ids())})


C0_OUTPUTS = (ROOT/"data/transmitters-v0.2.yaml", ROOT/"data/populations-v0.2.yaml", ROOT/"docs/transmitter-census.md")


def run_c0() -> dict:
    """C0 census (section 2.5 stage 1, WP14's outputs, no engine).

    Deviation for r14b: WP14 owns C0 but registered no STAGE, and the
    dispatcher discovers only drive/neuromod/behaviour, so the stage is
    registered here. It builds nothing: it requires WP14's files, the
    retinotopy table in populations v0.2 and a passed 0.10 pure leg.
    """
    from flyonenomics.validation.level0_substrate import test_0_10
    missing=[str(p.relative_to(ROOT)) for p in C0_OUTPUTS if not p.is_file()]
    if missing:
        return {"status":"failed","reason":f"census outputs missing: {missing}"}
    if not isinstance(read_yaml(ROOT/"data/populations-v0.2.yaml").get("retinotopy"),dict):
        return {"status":"failed","reason":"populations-v0.2.yaml has no retinotopy table"}
    entry=test_0_10()
    outputs={str(p.relative_to(ROOT)):_sha(p) for p in C0_OUTPUTS}
    return {"status":"passed" if entry.outcome=="passed" else "failed","owner":"WP14","engine":False,
            "test_0_10":entry.outcome,"outputs":outputs}


STAGE={"C0":run_c0,"R4":run_r4,"K1r":run_k1r,"drive":run_drive,"Q-rest":run_qrest}
def _r4_identity():
    identity=stage_identity(r2_path(),RECORDS/"R3.json",*((DEV_SOURCE,) if development() else ()))
    q=read_json(_rec()/"Q-rest.json") if (_rec()/"Q-rest.json").is_file() else {}
    previous=read_json(_rec()/"R4.json") if (_rec()/"R4.json").is_file() else {}
    identity["failure_transition"] = (_sha(_rec()/"Q-rest.json") if q.get("status")=="failed"
                                      else previous.get("input_identity",{}).get("failure_transition"))
    return identity


run_r4.input_identity=_r4_identity
run_c0.input_identity=lambda:stage_identity(*C0_OUTPUTS)
run_k1r.input_identity=lambda:stage_identity(_rec()/"R4.json",ROOT/"data/params-v0.2.yaml",ROOT/"data/transmitters-v0.2.yaml")
def output_guard(identity: dict, record_name: str, path: Path) -> dict:
    """Invalidate resume if a stage's configuration output was lost or changed."""
    record_path=_rec()/f"{record_name}.json"
    if record_path.is_file():
        record=read_json(record_path)
        actual=_sha(path) if path.is_file() else None
        if record.get("sha256")!=actual:identity["changed_output"]={"path":str(path.relative_to(ROOT)),"sha256":actual}
    return identity


run_drive.input_identity=lambda:output_guard(stage_identity(_rec()/"K1r.json"),"drive",_drive())
run_qrest.input_identity=lambda:stage_identity(_drive(),_dopamine(),*[FIXTURES/f for f in ("rest-short.json","rest-long.json","rest-reflex.json","rest-bitter.json","ff-bare.json","ff-candidate.json")])
