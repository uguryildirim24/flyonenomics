"""MCP tool server: typed experiment tools over the results store (WP7).

Units and shapes: all tools take and return JSON-serialisable dicts;
rates are in Hz, thresholds in mV, concentrations in uM, ticks are
integer recording ticks, tables are (rows, columns) mappings.
 Mechanism claims must cite a run id."""
from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import json
import os
import subprocess
import sys
from contextvars import ContextVar
from functools import lru_cache, wraps
from pathlib import Path
from typing import Any, Callable, get_args

from mcp.server.fastmcp import FastMCP
from pydantic import ValidationError

from flyonenomics.io import parquet_file, read_json, read_text, read_yaml

REPO = Path(__file__).resolve().parents[3]

# Implementation-mechanics constants (WP7 brief). No scientific values here.
PREVIEW_ROWS = 50  # WP7 brief: rows in large-table previews
LIVE_TAIL_LINES = 20  # WP7 brief: lines in live-file tails
MAX_STRING_CHARS = 400  # WP7 brief: prose bound enforced by tests/test_server.py
SUBPROCESS_TIMEOUT_S = 10  # WP7 brief: spawn grace advised to clients before first run_status poll
POLL_INTERVAL_S = 2.0  # WP7 brief: client poll interval suggested in run_status output

# WP7 mechanics: bounded products, per-call identity snapshot.
# Absolute worker ceiling; a launch is also capped by the engine budget's core
# cap (18 − 2 on this Mac) and refused above its swap start gate (item 69(d), item 76).
MAX_WORKERS = 16
RESULT_WHATS = ("summary", "metrics", "provenance", "slow_state", "dopamine",
                "receptors", "drug", "arena", "rates", "spikes", "popcount", "index", "live")
SLOW_STATE_APPROXIMATION = "phase1-drug-only"
_CONTEXT: ContextVar[dict[str, Any] | None] = ContextVar("tool_context", default=None)

mcp = FastMCP("flyonenomics")


def _runs_dir() -> Path:
    """Resolve the store root; units none, one path from env or repo. Mechanism claims must cite a run id."""
    override = os.environ.get("FLYONENOMICS_RUNS_DIR")
    root = Path(override) if override else REPO / "runs"
    root.mkdir(parents=True, exist_ok=True)
    return root.resolve()


def _cache_dir() -> Path:
    """Resolve the configured cache or repository default; one absolute path. Mechanism claims must cite a run id."""
    return Path(os.environ.get("FLYONENOMICS_CACHE_DIR") or REPO / ".cache").resolve()


def _free_parameters() -> dict[str, Any]:
    """Read free parameters from the manifest writer's source; units per key, scalar mapping. Mechanism claims must cite a run id."""
    from flyonenomics.orchestrator.runner import FREE_PARAMETER_KEYS
    from flyonenomics.types import load_params

    params = load_params()
    return {key: params.get(key) for key in FREE_PARAMETER_KEYS}


def _data_versions() -> dict[str, str]:
    """Read data-file versions in force; units none, name-to-version mapping. Mechanism claims must cite a run id."""
    versions: dict[str, str] = {}
    from flyonenomics.validation.binding import versioned_data_files

    for path in versioned_data_files(REPO):
        try:
            header = read_yaml(path) or {}
            versions[path.name] = str(header.get("version", "absent"))
        except OSError:
            versions[path.name] = "absent"
    return versions


def _provenance(run_id: str | None = None) -> dict[str, Any]:
    """Build the provenance block; units none, commit hashes plus optional run id. Mechanism claims must cite a run id."""
    from flyonenomics.validation.binding import repo_commit, sha256_file

    context = _CONTEXT.get()
    if context is not None and context["provenance"] is not None:
        return {**context["provenance"], "run_id": run_id}
    try:
        uv_hash = sha256_file(REPO / "uv.lock")
    except OSError:
        uv_hash = "absent"
    try:
        prov_hash = sha256_file(REPO / "data/provenance.json")
    except OSError:
        prov_hash = "absent"
    result = {"code_commit": repo_commit(REPO), "uv_lock_hash": uv_hash,
            "provenance_hash": prov_hash, "data_versions": _data_versions(),
            "run_id": run_id}
    if context is not None:
        context["provenance"] = result
    return result


def _code_hash() -> str:
    """Item 78 content hash of this checkout, cached per tool call; units none, one string."""
    from flyonenomics.validation import binding

    context = _CONTEXT.get()
    if context is not None and context.get("code_hash") is not None:
        return context["code_hash"]
    try:
        value = binding.code_content_hash(REPO)
    except (OSError, RuntimeError, subprocess.SubprocessError):
        value = ""
    if context is not None:
        context["code_hash"] = value
    return value


def _validation_entries(flags: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Rebind stored identities with the validation package; units none, entry list. Mechanism claims must cite a run id."""
    from flyonenomics.validation.binding import IdentityBlock, ValidationEntry, is_compatible
    context = _CONTEXT.get()
    cache_key = json.dumps(flags, sort_keys=True)
    if context is not None and cache_key in context["entries"]:
        return context["entries"][cache_key]
    provenance = _provenance()
    code_hash = _code_hash()
    raw = read_json(REPO / "validation/status.json")
    entries = []
    for item in raw.get("results", []):
        entry = ValidationEntry.model_validate(item)
        current = IdentityBlock(
            code_commit=provenance["code_commit"], code_hash=code_hash, uv_lock_hash=provenance["uv_lock_hash"],
            provenance_hash=provenance["provenance_hash"], data_versions=provenance["data_versions"],
            connectome_version=entry.identity.connectome_version,
            layer_flags=flags if flags is not None else entry.identity.layer_flags,
            protocol_hash=entry.identity.protocol_hash, assay=entry.identity.assay)
        valid, reason = is_compatible(entry, current, repo=REPO)
        entries.append({"test_id": entry.test_id, "class": entry.compatibility,
                        "outcome": entry.outcome, "binding": "valid" if valid else "stale",
                        "reason": reason, "identity_flags": entry.identity.layer_flags})
    if context is not None:
        context["entries"][cache_key] = entries
    return entries


def _layers(flags: Any = None) -> dict[str, Any]:
    """Derive per-flag evidence from executed identities (SPEC 11.29); flag mapping. Mechanism claims must cite a run id."""
    from flyonenomics.types import LayerFlags
    from flyonenomics.orchestrator.stubs import STUB_NAMES

    resolved = flags if flags is not None else LayerFlags()
    items = dict(resolved) if isinstance(resolved, dict) else dataclasses.asdict(resolved)
    try:
        entries = _validation_entries(items)
    except (OSError, ValueError, KeyError, TypeError):
        entries = []
    out = {}
    for key, value in items.items():
        def belongs(test_id: str) -> bool:
            if key in ("dopamine_A", "transporter_C"):
                return test_id in ("0.5", "0.7") or test_id.startswith("3.")
            if key == "background":
                return test_id.startswith(("1.", "2."))
            return False

        evidence = [e for e in entries if e["class"] in ("canonical", "matching-layers")
                    and belongs(e["test_id"])
                    and e["identity_flags"].get(key) == ("retain" if key == "dan_fast_synapses" else True)]
        stub = key in ("receptor_kinetics_B", "learning_D") or (
            key in ("dopamine_A", "transporter_C") and "IdentityNeuromod" in STUB_NAMES)
        status = "absent" if stub or not evidence else (
            "valid" if all(e["binding"] == "valid" and e["outcome"] in ("passed", "recorded")
                           for e in evidence) else "stale")
        out[key] = {"value": value, "validation": status}
    return out


def _behaviour_component(flags: Any = None) -> str:
    """Report the measured behaviour qualification separately from layer flags."""
    try:
        entries = _validation_entries(flags)
    except (OSError, ValueError, KeyError, TypeError):
        return "unavailable"
    by_id = {e["test_id"]: e for e in entries}
    flat = by_id.get("4.1")
    if flat and flat["class"] == "matching-layers" and flat["binding"] == "valid" and flat["outcome"] == "failed":
        return "level 4 open-loop only"
    return "unavailable"


def validation_summary(flags: Any = None) -> tuple[dict[str, Any], str]:
    """Derive dashboard validation fields from one per-request identity snapshot."""
    context = {"provenance": None, "entries": {}}
    token = _CONTEXT.set(context)
    try:
        return _layers(flags), _behaviour_component(flags)
    finally:
        _CONTEXT.reset(token)


def _bounded(node: Any, path: tuple[str, ...] = ()) -> Any:
    """Bound all strings structurally except the two root subtrees; units characters. Mechanism claims must cite a run id."""
    if path in (("schema",), ("what_the_map_leaves_out",)):
        return node
    if isinstance(node, str):
        return node[:MAX_STRING_CHARS]
    if isinstance(node, dict):
        return {str(k)[:MAX_STRING_CHARS]: _bounded(v, (*path, str(k))) for k, v in node.items()}
    if isinstance(node, (list, tuple)):
        return [_bounded(v, (*path, str(i))) for i, v in enumerate(node)]
    return node


def _tool_payload(function: Callable[..., dict[str, Any]]) -> Callable[..., dict[str, Any]]:
    """Give each tool one identity snapshot and envelope errors; ordered JSON mapping. Mechanism claims must cite a run id."""
    @wraps(function)
    def invoke(*args: Any, **kwargs: Any) -> dict[str, Any]:
        token = _CONTEXT.set({"provenance": None, "entries": {}})
        try:
            try:
                return function(*args, **kwargs)
            except (OSError, ValueError, KeyError, TypeError) as exc:
                from flyonenomics.types import LayerFlags
                try:
                    layers = _layers()
                except (OSError, ValueError, KeyError, TypeError):
                    layers = {k: {"value": v, "validation": "absent"}
                              for k, v in dataclasses.asdict(LayerFlags()).items()}
                return _envelope(layers, _provenance(), ok=False, errors=[str(exc)])
        finally:
            _CONTEXT.reset(token)
    return invoke


def _envelope(layers: dict[str, Any], provenance: dict[str, Any], **data: Any) -> dict[str, Any]:
    """Wrap a payload with the structural leading keys; units per payload, ordered mapping. Mechanism claims must cite a run id."""
    parameters = _free_parameters()
    run_id = provenance.get("run_id")
    if run_id:
        from flyonenomics.store import ResultsStore
        try:
            run_path = _run_path(ResultsStore(_runs_dir()), run_id)
            manifest_path = _inside(run_path, "manifest.json")
            if manifest_path.is_file():
                manifest = read_json(manifest_path)
                provenance = {**provenance, "server_code_commit": provenance.get("code_commit"),
                              **{k: manifest[k] for k in ("code_commit", "uv_lock_hash", "provenance_hash") if k in manifest},
                              "data_versions": manifest.get("identity", {}).get("data_versions", {}),
                              "substrate_versions": manifest.get("versions", {})}
                parameters = manifest.get("free_parameters", {})
        except (OSError, ValueError, KeyError, TypeError):
            pass
    return _bounded({"layers": layers, "free_parameters": parameters,
                     "provenance": provenance, **data})



@lru_cache(maxsize=3)
def _registry_cached(connectome_version: str = "783") -> Any:
    """Build each version's registry once per server process. Mechanism claims require a run id."""
    from flyonenomics.registry import build_registry

    return build_registry(connectome_version)


def _validate_dict(experiment: dict[str, Any]) -> tuple[Any | None, list[str], dict[str, Any], dict[str, int]]:
    """Validate an experiment dict; units per schema, experiment plus errors plus resolution.

    Returns (experiment_or_None, errors, resolved_roots, counts). Never raises on
    bad input: schema, v630, behaviour-stub, and resolution failures all come
    back as error strings.
     Mechanism claims must cite a run id."""
    from flyonenomics.schema.experiment import Experiment, Probe, Substrate
    from flyonenomics.types import load_params

    if not isinstance(experiment, dict):
        return None, ["experiment must be a JSON object"], {}, {}
    try:
        validated = Experiment.model_validate(experiment)
    except ValidationError as exc:
        errors = [f"{'.'.join(str(p) for p in err['loc'])}: {err['msg']}" for err in exc.errors()]
        return None, errors or ["schema validation failed"], {}, {}
    errors: list[str] = []
    defaults = Substrate()
    for key, expected in (("annotation_version", defaults.annotation_version),
                          ("receptor_map_version", defaults.receptor_map_version),
                          ("params_version", load_params().version)):
        if getattr(validated.substrate, key) != expected:
            errors.append(f"unavailable {key}: {getattr(validated.substrate, key)}")
    if validated.substrate.connectome_version == "630":
        errors.append("connectome_version 630 refused: orchestrator v630 support deferred (SPEC 11 item 22)")
    from flyonenomics.orchestrator.stubs import STUB_NAMES
    if "IdentityBehaviour" in STUB_NAMES and any(isinstance(p, Probe) and p.assay in ("buridan", "open_loop_steering")
           for arm in validated.arms for p in arm.expanded()):
        errors.append("behaviour stub: assay arrives in WP6")
    if errors:
        return validated, errors, {}, {}
    try:
        resolved = validated.resolve(_registry_cached(validated.substrate.connectome_version))
    except (ValueError, KeyError) as exc:
        return validated, [str(exc)], {}, {}
    counts = {name: len(idx) for name, idx in resolved.items()}
    return validated, [], resolved, counts


def _map_leaves_out() -> str:
    """Quote feasibility section 4 verbatim; units none, one markdown string. Mechanism claims must cite a run id."""
    try:
        text = read_text(REPO / "docs/feasibility.md")
        start = text.index("## 4. What the map leaves out")
        end = text.index("## 5.", start)
        return text[start:end].strip()
    except (OSError, ValueError):
        return "unavailable"


def _preview_table(path: Path) -> dict[str, Any]:
    """Preview a parquet table; units per schema, path plus first PREVIEW_ROWS records. Mechanism claims must cite a run id."""
    with parquet_file(path) as parquet:
        batch = next(parquet.iter_batches(batch_size=PREVIEW_ROWS), None)
        return {"path": str(path), "rows": parquet.metadata.num_rows,
                "columns": parquet.schema_arrow.names,
                "preview": batch.to_pylist() if batch is not None else []}


def _inside(root: Path, *parts: str) -> Path:
    """Resolve a file strictly beneath its trusted root, including symlinks; one path. Mechanism claims must cite a run id."""
    target = root.joinpath(*parts).resolve()
    if target == root.resolve() or not target.is_relative_to(root.resolve()):
        raise ValueError("path must resolve strictly inside the run directory")
    return target


def _run_path(store: Any, run_id: str) -> Path:
    """Reject encoded separators and non-identifiers before resolving a run; one path. Mechanism claims must cite a run id."""
    if not isinstance(run_id, str) or not run_id or any(c in run_id for c in ("/", "\\", "%")):
        raise ValueError("invalid run_id")
    store.run_path(run_id)  # Store's plain-name contract applies too.
    return _inside(store.root, run_id)


def _selection(experiment: Any, arm: str | None, seed: int | None,
               probe: int | None) -> tuple[Any, int, int]:
    """Validate selectors against the experiment and choose its first probe; scalar ids. Mechanism claims must cite a run id."""
    from flyonenomics.schema.experiment import Probe
    chosen = next((a for a in experiment.arms if a.label == arm), None) if arm is not None else experiment.arms[0]
    if chosen is None:
        raise ValueError("unknown arm")
    seed = experiment.seeds[0] if seed is None else seed
    if type(seed) is not int or seed not in experiment.seeds:
        raise ValueError("unknown seed")
    probes = [i for i, p in enumerate(chosen.expanded()) if isinstance(p, Probe)]
    probe = probes[0] if probe is None else probe
    if type(probe) is not int or probe not in probes:
        raise ValueError("unknown probe")
    return chosen, seed, probe


@mcp.tool()
@_tool_payload
def describe_lab() -> dict[str, Any]:
    """Report substrate, layers, assays, drugs, genotypes, and map limits; units per field, nested mapping. Mechanism claims must cite a run id."""
    from flyonenomics.schema.named import named_manipulations
    from flyonenomics.types import LayerFlags, load_params

    params = load_params()
    from flyonenomics.schema.experiment import Substrate, Probe, Genotype, Drug, DEFERRED_DRUGS
    defaults = Substrate()
    records = read_json(REPO / "data/provenance.json")["records"]
    substrate = {"connectome_version": "absent", "annotation_version": "absent",
                 "params_version": params.version, "drive_version": "absent",
                 "dopamine_version": "absent", "behaviour_version": "absent"}
    sources = {}
    for record in records:
        path = record.get("path") or ""
        if record.get("status") != "fetched":
            continue
        if Path(path).name == f"Connectivity_{defaults.connectome_version}.parquet":
            substrate["connectome_version"] = defaults.connectome_version
            sources["connectome"] = {k: record.get(k) for k in ("path", "version", "sha256")}
        if Path(path).name == f"annotations-{defaults.annotation_version}.tsv":
            substrate["annotation_version"] = Path(path).stem.removeprefix("annotations-")
            sources["annotations"] = {k: record.get(k) for k in ("path", "version", "sha256")}
    for key in ("drive", "dopamine", "behaviour"):
        path = REPO / "data" / f"{key}-v0.1.yaml"
        if path.is_file():
            try:
                substrate[f"{key}_version"] = str(read_yaml(path).get("version", "absent"))
            except OSError:
                pass
    genotypes = {
        name: [m.model_dump(mode="json") for m in named_manipulations(name)]
        for name in get_args(Genotype.model_fields["named"].annotation)
    }
    return _envelope(_layers(LayerFlags()), _provenance(),
                     substrate=substrate, substrate_sources=sources,
                     directories={"runs": str(_runs_dir()), "cache": str(_cache_dir())},
                     assays=list(get_args(Probe.model_fields["assay"].annotation)),
                     drugs={"supported": list(get_args(Drug)), "deferred": sorted(DEFERRED_DRUGS)},
                     named_genotypes=genotypes,
                     slow_state=SLOW_STATE_APPROXIMATION,
                     what_the_map_leaves_out=_map_leaves_out())


@mcp.tool()
@_tool_payload
def list_populations() -> dict[str, Any]:
    """List registry populations with counts; units neurons, name-to-count mapping. Mechanism claims must cite a run id."""
    registry = _registry_cached()
    populations = [{"name": name, "count": int(registry.population(name).count)} for name in registry.populations()]
    return _envelope(_layers(), _provenance(), populations=populations, n=len(populations))


@mcp.tool()
@_tool_payload
def describe_population(name: str) -> dict[str, Any]:
    """Describe one population; units neurons, scalar fields plus small mappings. Mechanism claims must cite a run id."""
    from flyonenomics.registry import annotations as ann

    try:
        registry = _registry_cached()
        pop = registry.population(name)
    except KeyError:
        return _envelope(_layers(), _provenance(), ok=False, errors=[f"unknown population: {name}"])
    _, (low, high) = registry.inventory(name)
    frame = ann.load_annotations("v2.1.0")
    subset = frame[frame["root_id"].isin([int(r) for r in pop.root_ids])]
    super_classes = {str(k): int(v) for k, v in subset["super_class"].fillna("na").value_counts().items()}
    known = subset["known_nt"].fillna("na").value_counts()
    top_nt = subset["top_nt"].fillna("na").value_counts()
    completeness: Any = "unknown"
    try:
        results = read_json(REPO / "validation/status.json").get("results", [])
        for item in results:
            if item.get("test_id") == "registry.completeness":
                completeness = item.get("measured", {}).get("populations", {}).get(name, "unknown")
                break
    except OSError:
        pass
    return _envelope(_layers(), _provenance(), ok=True, name=pop.name,
                     count=int(pop.count), inventory_range=[low, high],
                     source=str(pop.selector),
                     super_class=dict(list(super_classes.items())[:PREVIEW_ROWS]),
                     top_known_nt={"value": str(known.index[0]), "n": int(known.iloc[0])} if len(known) else {"value": "na", "n": 0},
                     top_predicted_nt={"value": str(top_nt.index[0]), "n": int(top_nt.iloc[0])} if len(top_nt) else {"value": "na", "n": 0},
                     completeness=completeness)


@mcp.tool()
@_tool_payload
def list_compartments() -> dict[str, Any]:
    """List the 37 compartments with sides and ids; units none, row list. Mechanism claims must cite a run id."""
    registry = _registry_cached()
    compartments = [{"name": c.name, "side": c.side, "id": int(c.id)} for c in registry.compartments()]
    return _envelope(_layers(), _provenance(), compartments=compartments, n=len(compartments))


@mcp.tool()
@_tool_payload
def resolve_population(spec: dict[str, Any]) -> dict[str, Any]:
    """Resolve a population spec to roots and indices; units int64 roots/int32 indices, arrays (m,). Mechanism claims must cite a run id."""
    from flyonenomics.registry import PopulationSpec

    if not isinstance(spec, dict):
        return _envelope(_layers(), _provenance(), ok=False, errors=["spec must be a JSON object"])
    try:
        parsed = PopulationSpec.model_validate(spec)
    except ValidationError as exc:
        return _envelope(_layers(), _provenance(), ok=False,
                         errors=[f"{'.'.join(str(p) for p in err['loc'])}: {err['msg']}" for err in exc.errors()])
    try:
        pop = _registry_cached().resolve(parsed)
    except KeyError as exc:
        return _envelope(_layers(), _provenance(), ok=False, errors=[str(exc.args[0])])
    except ValueError as exc:
        return _envelope(_layers(), _provenance(), ok=False, errors=[str(exc)])
    return _envelope(_layers(), _provenance(), ok=True, name=pop.name,
                     count=int(pop.count), root_ids=[int(r) for r in pop.root_ids],
                     idx=[int(i) for i in pop.idx])


@mcp.tool()
@_tool_payload
def get_schema() -> dict[str, Any]:
    """Return the Experiment JSON schema; units per field, schema mapping. Mechanism claims must cite a run id."""
    from flyonenomics.schema.experiment import Experiment

    return _envelope(_layers(), _provenance(), schema=Experiment.model_json_schema())


@mcp.tool()
@_tool_payload
def example_experiments() -> dict[str, Any]:
    """Return runnable examples each with its validation result; units per schema, list. Mechanism claims must cite a run id."""
    from flyonenomics.store.results import read_json

    entries = []
    for label in ("sugar-reflex", "spontaneous", "acceptance-6.3"):
        try:
            if label == "acceptance-6.3":
                text = read_text(REPO / "docs/SPEC.md").split("### 6.3 ", 1)[1]
                doc = json.loads(text.split("```json", 1)[1].split("```", 1)[0])
            else:
                doc = read_json(REPO / "data/experiments" / f"{label}.json")
            _, errors, _, counts = _validate_dict(doc)
            entries.append({"label": label, "experiment": doc,
                            "validation": {"ok": not errors, "errors": errors, "counts": counts}})
        except (OSError, ValueError, IndexError) as exc:
            entries.append({"label": label, "status": "unavailable",
                            "validation": {"ok": False, "errors": [str(exc)]}})
    return _envelope(_layers(), _provenance(), examples=entries)


@mcp.tool()
@_tool_payload
def validate_experiment(experiment: dict[str, Any]) -> dict[str, Any]:
    """Validate schema, populations, drugs, and arm matching; resolved indices/root_ids (n,), experiment mapping. Mechanism claims must cite a run id."""
    validated, errors, resolved, counts = _validate_dict(experiment)
    if errors:
        layers = _layers()
        if validated is not None:
            layers = _layers(validated.layers)
        return _envelope(layers, _provenance(), ok=False, errors=errors)
    return _envelope(_layers(validated.layers), _provenance(), ok=True,
                     experiment=validated.model_dump(mode="json"),
                     resolved={k: [int(i) for i in v] for k, v in resolved.items()},
                     root_ids={k: [int(_registry_cached().root_ids[i]) for i in v]
                               for k, v in resolved.items()},
                     counts=counts)


@mcp.tool()
@_tool_payload
def run_experiment(experiment: dict[str, Any], n_workers: int = 4) -> dict[str, Any]:
    """Validate, queue, and detach a run, returning its id at once; units none/ids, mapping. Mechanism claims must cite a run id."""
    from flyonenomics.orchestrator.runner import make_run_id
    from flyonenomics.store import ResultsStore
    from flyonenomics.store.results import atomic_json

    import shutil

    from flyonenomics.orchestrator import budget

    ceiling = min(MAX_WORKERS, budget.core_cap())
    if type(n_workers) is not int or not 1 <= n_workers <= ceiling:
        return _envelope(_layers(), _provenance(), ok=False,
                         errors=[f"n_workers must be an integer from 1 to {ceiling}"])
    validated, errors, _, _ = _validate_dict(experiment)
    if errors:
        return _envelope(_layers(validated.layers if validated is not None else None),
                         _provenance(), ok=False, errors=errors)
    swap_mib = budget.swap_used_mib()
    if swap_mib > budget.SWAP_HARD_MIB:
        return _envelope(_layers(validated.layers), _provenance(), ok=False,
                         errors=[f"swap used {swap_mib:.0f} MiB is above the {budget.SWAP_HARD_MIB:.0f} MiB engine start gate"])
    # Item 71: the runner's default keys on an acceptance-* filename, and this
    # launch passes runs/<id>/input.json, so the sleep assertion is explicit.
    caffeinate = ["--caffeinate"] if shutil.which("caffeinate") else []
    store = ResultsStore(_runs_dir())
    while True:
        run_id = make_run_id(validated)
        run_dir = store.run_path(run_id)
        try:
            run_dir.mkdir()
            break
        except FileExistsError:
            continue
    document = validated.model_dump(mode="json")
    input_path = run_dir / "input.json"
    atomic_json(input_path, document)
    atomic_json(run_dir / "experiment.json", document)
    status = {"state": "queued", "created": run_id.rsplit("-", 1)[0], "run_id": run_id}
    atomic_json(run_dir / "status.json", status)
    store.index.upsert(run_id, document, status)
    try:
        with (run_dir / "log.txt").open("ab") as log_handle:
            subprocess.Popen([sys.executable, str(REPO / "scripts/run_experiment.py"), str(input_path),
                              "--workers", str(n_workers), *caffeinate, "--runs-dir", str(store.root), "--run-id", run_id],
                             cwd=str(REPO), start_new_session=True, stdin=subprocess.DEVNULL,
                             stdout=log_handle, stderr=subprocess.STDOUT,
                             env={**os.environ, "FLYONENOMICS_CACHE_DIR": str(_cache_dir())})
    except OSError as exc:
        status.update(state="failed", traceback=str(exc))
        atomic_json(run_dir / "status.json", status)
        store.index.upsert(run_id, document, status)
        return _envelope(_layers(validated.layers), _provenance(run_id), ok=False,
                         run_id=run_id, errors=[str(exc)])
    return _envelope(_layers(validated.layers), _provenance(run_id), ok=True, run_id=run_id,
                     poll_interval_s=POLL_INTERVAL_S, spawn_grace_s=SUBPROCESS_TIMEOUT_S)


@mcp.tool()
@_tool_payload
def run_status(run_id: str) -> dict[str, Any]:
    """Report a run's lifecycle state; units seconds, scalar status fields. Mechanism claims must cite a run id."""
    from flyonenomics.store import ResultsStore
    from flyonenomics.store.results import read_json

    store = ResultsStore(_runs_dir())
    try:
        path = _run_path(store, run_id)
    except ValueError:
        return _envelope(_layers(), _provenance(run_id), ok=False, errors=[f"unknown run_id: {run_id}"])
    if not path.is_dir() or not (path / "status.json").is_file():
        return _envelope(_layers(), _provenance(run_id), ok=False, errors=[f"unknown run_id: {run_id}"])
    status = read_json(_inside(path, "status.json"))
    layers: Any = _layers()
    try:
        from flyonenomics.schema.experiment import Experiment

        layers = _layers(Experiment.model_validate(read_json(_inside(path, "experiment.json"))).layers)
    except (OSError, ValueError):
        pass
    kept = {k: status.get(k) for k in ("state", "created", "wall_time_s", "arm", "seed",
                                       "phase_index", "brain_time_s", "estimated_remaining_s", "n_workers") if k in status}
    data: dict[str, Any] = {"ok": True, "run_id": run_id, "status": kept,
                            "poll_interval_s": POLL_INTERVAL_S}
    if status.get("state") == "failed":
        data["errors"] = [str(status.get("traceback", "failed"))[-MAX_STRING_CHARS:]]
    return _envelope(layers, _provenance(run_id), **data)


@mcp.tool()
@_tool_payload
def cancel_run(run_id: str) -> dict[str, Any]:
    """Request cooperative cancellation; units none, verdict mapping. Mechanism claims must cite a run id."""
    from flyonenomics.store import ResultsStore
    from flyonenomics.schema import Experiment
    from flyonenomics.store.results import read_json

    store = ResultsStore(_runs_dir())
    try:
        path = _run_path(store, run_id)
        experiment = Experiment.model_validate(read_json(_inside(path, "experiment.json")))
        _inside(path, "CANCEL")
        store.cancel(run_id)
    except (FileNotFoundError, ValueError, OSError):
        return _envelope(_layers(), _provenance(run_id), ok=False, errors=[f"unknown run_id: {run_id}"])
    return _envelope(_layers(experiment.layers), _provenance(run_id), ok=True, run_id=run_id)


@mcp.tool()
@_tool_payload
def get_results(run_id: str, what: str, arm: str | None = None, seed: int | None = None,
                probe: int | None = None) -> dict[str, Any]:
    """Fetch one result product with named selectors; units per product, mapping. Mechanism claims must cite a run id."""
    from flyonenomics.store import ResultsStore
    from flyonenomics.store.results import read_json

    store = ResultsStore(_runs_dir())
    try:
        path = _run_path(store, run_id)
    except ValueError:
        return _envelope(_layers(), _provenance(run_id), ok=False, errors=[f"unknown run_id: {run_id}"])
    if what not in RESULT_WHATS:
        return _envelope(_layers(), _provenance(run_id), ok=False,
                         errors=[f"unknown what: {what}; expected one of {', '.join(RESULT_WHATS)}"])
    if not path.is_dir() or not (path / "experiment.json").is_file():
        return _envelope(_layers(), _provenance(run_id), ok=False, errors=[f"unknown run_id: {run_id}"])
    from flyonenomics.schema.experiment import Experiment
    experiment = Experiment.model_validate(read_json(_inside(path, "experiment.json")))
    chosen, seed, probe = _selection(experiment, arm, seed, probe)
    arm = chosen.label
    selected = {"arm": arm, "seed": seed, "probe": probe}
    layers = _layers(experiment.arm_layers(chosen))
    seed_dir = _inside(path, f"arm-{arm}", f"seed-{seed}")
    try:
        if what == "summary":
            metrics = read_json(_inside(path, "metrics.json"))
            return _envelope(layers, _provenance(run_id), ok=True, selected=selected,
                             summary={"arms": metrics.get("arms", {}),
                                      "paired_differences": metrics.get("paired_differences", {}),
                                      **{key: metrics[key] for key in ("slow_state", "repeat_note", "layer_note", "calibration_limits") if key in metrics}})
        if what == "metrics":
            return _envelope(layers, _provenance(run_id), ok=True, selected=selected,
                             metrics=read_json(_inside(path, "metrics.json")))
        if what == "provenance":
            manifest = read_json(_inside(path, "manifest.json"))
            return _envelope(layers, _provenance(run_id), ok=True, selected=selected,
                             provenance_detail={k: manifest.get(k) for k in
                                                ("versions", "code_commit", "uv_lock_hash",
                                                 "protocol_hash", "layers", "free_parameters",
                                                 "formulation", "slow_state")})
        if what == "live":
            live_path = _inside(path, str(seed_dir.relative_to(path)), "live", f"probe-{probe}.ndjson")
            if not live_path.is_file():
                return _envelope(layers, _provenance(run_id), ok=False, selected=selected,
                                 live={"status": "not_started", "n_lines": 0, "events": []},
                                 errors=[f"probe has not started or live recording is unavailable: {arm}/{seed}/probe-{probe}"])
            # A writer may be in the middle of its final line; only complete events count.
            from collections import deque
            events: Any = deque(maxlen=LIVE_TAIL_LINES)
            count = 0
            with live_path.open() as handle:
                for line in handle:
                    try:
                        event = json.loads(line)
                    except ValueError:
                        if not line.endswith("\n"):
                            continue
                        raise
                    events.append(event)
                    count += 1
            return _envelope(layers, _provenance(run_id), ok=True, selected=selected,
                             live={"status": "started", "n_lines": count, "events": list(events)})
        names = {"slow_state": seed_dir / "slow-state.parquet",
                 "index": seed_dir / "index.parquet",
                 "receptors": seed_dir / f"probe-{probe}-receptors.parquet",
                 "drug": seed_dir / f"probe-{probe}-drug.parquet",
                 "dopamine": seed_dir / f"probe-{probe}-dopamine.parquet",
                 "arena": seed_dir / f"probe-{probe}-arena.parquet",
                 "rates": seed_dir / f"probe-{probe}-rates.parquet",
                 "spikes": seed_dir / f"probe-{probe}-spikes.parquet",
                 "popcount": seed_dir / f"probe-{probe}-popcount-1ms.parquet"}
        table_path = _inside(path, str(names[what].relative_to(path)))
        if not table_path.is_file():
            return _envelope(layers, _provenance(run_id), ok=False, selected=selected,
                             errors=[f"missing table for {arm}/{seed}/probe-{probe}: {table_path.name}"])
        return _envelope(layers, _provenance(run_id), ok=True, selected=selected,
                         table=_preview_table(table_path))
    except (OSError, ValueError) as exc:
        return _envelope(layers, _provenance(run_id), ok=False, selected=selected, errors=[str(exc)])


def _utc_timestamp(value: str) -> dt.datetime:
    """Parse compact or extended ISO timestamps; naive inputs use UTC. Mechanism claims must cite a run id."""
    stamp = dt.datetime.fromisoformat(value)
    return stamp.replace(tzinfo=dt.timezone.utc) if stamp.tzinfo is None else stamp.astimezone(dt.timezone.utc)


@mcp.tool()
@_tool_payload
def list_runs(filter: dict[str, Any] | None = None) -> dict[str, Any]:
    """List indexed runs with optional filters; units per metrics, row list. Mechanism claims must cite a run id."""
    from flyonenomics.store import ResultsStore

    store = ResultsStore(_runs_dir())
    filt = {} if filter is None else filter
    if not isinstance(filt, dict):
        return _envelope(_layers(), _provenance(), ok=False, errors=["filter must be a JSON object"])
    allowed = {"state", "name", "assay", "created_after"}
    if set(filt) - allowed or any(not isinstance(v, str) for v in filt.values()):
        return _envelope(_layers(), _provenance(), ok=False, errors=["unknown filter or non-string value"])
    cutoff = _utc_timestamp(filt["created_after"]) if filt.get("created_after") else None
    rows = []
    for row in store.index.rows():
        try:
            parsed = {"run_id": row["run_id"], "name": row["name"], "created": row["created"],
                      "state": row["state"], "arms": json.loads(row["arms"]),
                      "seeds": json.loads(row["seeds"]), "assay": json.loads(row["assay"]),
                      "headline_metrics": json.loads(row["headline_metrics"] or "{}"),
                      "artefact_flags": json.loads(row["artefact_flags"] or "[]")}
        except (ValueError, KeyError, TypeError):
            continue
        if filt.get("state") and parsed["state"] != filt["state"]:
            continue
        if filt.get("name") and filt["name"] not in parsed["name"]:
            continue
        if filt.get("assay") and filt["assay"] not in parsed["assay"]:
            continue
        if cutoff is not None:
            try:
                created = _utc_timestamp(parsed["created"])
            except ValueError:
                continue
            if created <= cutoff:
                continue
        rows.append(parsed)
    return _envelope(_layers(), _provenance(), ok=True, runs=rows, n=len(rows))


@mcp.tool()
@_tool_payload
def compare_runs(run_ids: list[str], metric: str) -> dict[str, Any]:
    """Compare one metric across runs with pairing where valid; units Hz/counts, tables. Mechanism claims must cite a run id."""
    import numpy as np

    from flyonenomics.store import ResultsStore
    from flyonenomics.store.results import read_json

    store = ResultsStore(_runs_dir())
    if not isinstance(run_ids, list) or len(run_ids) < 2:
        return _envelope(_layers(), _provenance(), ok=False, errors=["run_ids must list at least two runs"])
    tables: dict[str, Any] = {}
    seeds_of: dict[str, list[int]] = {}
    s_of: dict[str, int] = {}
    for run_id in run_ids:
        try:
            path = _run_path(store, run_id)
        except ValueError:
            return _envelope(_layers(), _provenance(), ok=False, errors=[f"unknown run_id: {run_id}"])
        if not path.is_dir() or not (path / "metrics.json").is_file():
            return _envelope(_layers(), _provenance(), ok=False, errors=[f"unknown run_id: {run_id}"])
        experiment = read_json(_inside(path, "experiment.json"))
        metrics = read_json(_inside(path, "metrics.json"))
        s_of[run_id] = int(experiment["seed"])
        seeds_of[run_id] = [int(s) for s in experiment["seeds"]]
        per_arm: dict[str, Any] = {}
        for label, block in metrics.get("arms", {}).items():
            values = []
            for row in block.get("per_seed", []):
                if metric in row:
                    values.append({"seed": int(row["seed"]), "value": float(row[metric])})
            if values:
                numbers = np.array([row["value"] for row in values])
                per_arm[str(label)] = {"per_seed": values, "mean": float(numbers.mean()),
                    "sd": float(numbers.std(ddof=1)) if len(numbers) > 1 else 0.0, "n": len(numbers)}
        if not per_arm:
            return _envelope(_layers(), _provenance(), ok=False,
                             errors=[f"metric {metric} not recorded in {run_id}"])
        tables[run_id] = {"S": s_of[run_id], "seeds": seeds_of[run_id], "arms": per_arm}
    first, second = run_ids[0], run_ids[1]
    paired: dict[str, Any] | None = None
    reason = ""
    if s_of[first] != s_of[second]:
        reason = "pairing impossible: different S"
    elif seeds_of[first] != seeds_of[second]:
        reason = "pairing impossible: different seed lists"
    elif set(tables[first]["arms"]) != set(tables[second]["arms"]):
        reason = "pairing impossible: different arms"
    else:
        paired = {}
        for label in sorted(tables[first]["arms"]):
            left = {r["seed"]: r["value"] for r in tables[first]["arms"][label]["per_seed"]}
            right = {r["seed"]: r["value"] for r in tables[second]["arms"][label]["per_seed"]}
            if set(left) != set(seeds_of[first]) or set(right) != set(seeds_of[second]):
                paired = None
                reason = "pairing impossible: metric missing for a requested seed"
                break
            ids = seeds_of[first]
            diffs = np.array([right[seed] - left[seed] for seed in ids])
            paired[label] = {"seeds": ids, "per_seed": [float(v) for v in diffs],
                             "mean": float(diffs.mean()), "n": len(diffs),
                             "sd": float(diffs.std(ddof=1)) if len(diffs) > 1 else 0.0}
    data: dict[str, Any] = {"ok": True, "metric": metric, "tables": tables,
                           "paired_run_ids": [first, second]}
    if paired is None:
        data["paired"] = False
        data["reason"] = reason
    else:
        data["paired"] = {f"{second}-minus-{first}": paired}
    return _envelope(_layers(), _provenance(), **data)


@mcp.tool()
@_tool_payload
def validation_status() -> dict[str, Any]:
    """Report each validation entry with its binding; units per entry, list. Mechanism claims must cite a run id."""
    entries = [{k: v for k, v in entry.items() if k != "identity_flags"}
               for entry in _validation_entries()]
    return _envelope(_layers(), _provenance(), ok=True, entries=entries, n=len(entries),
                     behaviour_component=_behaviour_component())


def tool_names() -> list[str]:
    """Return registered tool names in registration order; units none, name list. Mechanism claims must cite a run id."""
    tools = mcp._tool_manager.list_tools()
    import asyncio

    if asyncio.iscoroutine(tools):
        tools = asyncio.run(tools)
    return [t.name for t in tools]


def main() -> None:
    """Serve stdio or answer --list-tools; units none, no arrays. Mechanism claims must cite a run id."""
    parser = argparse.ArgumentParser(description="flyonenomics MCP tool server (stdio)")
    parser.add_argument("--list-tools", action="store_true", help="print tool names and exit")
    args = parser.parse_args()
    if args.list_tools:
        print("\n".join(tool_names()))
        return
    mcp.run()


if __name__ == "__main__":
    main()
