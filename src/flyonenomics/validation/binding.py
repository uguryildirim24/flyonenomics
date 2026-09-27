"""Compatibility binding of SPEC section 7 and SPEC-P2 section 5.1 (WP16).

Computes the identity block of a validation entry and compares a
stored entry against a run context under the compatibility rule.
Phase 1 test 0.9 still holds. Phase 2 adds per-entry inputs, code_scope
without data/, run_code_scope, overrides_hash, platform, substrate_id,
and qualification_of.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import os
import platform
import re
import subprocess
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any, Literal, Self

from pydantic import Field, model_validator

from flyonenomics.types import StrictModel, LayerFlags

GRID_ENTRY_IDS = frozenset({"V-cal", "VT-cal", "K3r", "K3r-T", "3.9r", "4.8r"})
SIGN_DISAGREE_MAX = 0.10
COMMON_IDENTITY_PATHS = frozenset({"data/provenance.json"})

COMPONENT_PASSED: dict[str, tuple[str, ...]] = {
    "engine": (
        "0.1", "0.2", "0.3", "0.4", "0.7", "0.8", "0.9r", "0.10", "0.10-engine",
        "0.12", "0.13", "0.14", "0.15", "1.0", "1.1",
    ),
    "registry": ("registry.inventory", "registry.labels", "registry.precedence"),
    "rest substrate": (
        "3.1r-alg", "3.1br", "2.3r", "2.7r", "2.6r", "2.2r", "1.4r", "1.4r-ff", "2.4r",
    ),
    "neuromodulation": ("0.5", "3.1br", "3.2r", "3.3r", "3.4r", "3.5r", "3.7"),
}

VISUAL_PASSED: dict[str, tuple[str, ...]] = {
    "photoreceptor closed loop": ("V0", "V1", "V3"),
    "TuBu closed loop": ("V0", "V1-T"),
    "open loop": ("V0",),
}

BEHAVIOUR_PASSED: dict[str, tuple[str, ...]] = {
    "photoreceptor closed loop": ("4.0", "4.0b", "4.0c", "4.1r", "4.2r"),
    "TuBu closed loop": ("4.0", "4.0b", "4.0c", "4.1r-T", "4.2r-T"),
    "open loop": ("4.0", "4.0b", "4.0c"),
}


class CompatibilityClass:
    """Configuration classes of the section 7 compatibility rule."""

    CANONICAL: str = "canonical"
    MATCHING_LAYERS: str = "matching-layers"
    RUN_BOUND: str = "run-bound"
    DEVELOPMENT: str = "development"

    @classmethod
    def values(cls) -> list[str]:
        """Return the four class names.

        Units: none. Shapes: a list of four strings.
        """
        return [cls.CANONICAL, cls.MATCHING_LAYERS, cls.RUN_BOUND, cls.DEVELOPMENT]


class IdentityBlock(StrictModel):
    """Identity block of one validation entry (SPEC section 7, SPEC-P2 5.1).

    Units: none. Shapes: scalars only. fixture_hash is the SHA-256
    of the canonical fixture the test ran; protocol_hash is the
    SHA-256 of the validated experiment for run-bound entries.
    code_hash is the Phase 1 content hash of src/, data/, scripts/, uv.lock
    (item 69(b)). code_scope is the same hash with data/ removed (item 78).
    run_code_hash / run_code_scope are those hashes at launch (item 73);
    run_code_hash is recorded only and never stales (item 77).
    Empty code_hash or run_code_hash keeps the Phase 1 commit rule.
    """

    code_commit: str = Field(min_length=1)
    code_hash: str = ""
    run_code_hash: str = ""
    code_scope: str = ""
    run_code_scope: str = ""
    uv_lock_hash: str = Field(min_length=1)
    provenance_hash: str = Field(min_length=1)
    data_versions: dict[str, str] = Field(default_factory=dict)
    connectome_version: str = "783"
    layer_flags: dict[str, Any] = Field(default_factory=dict)
    fixture_hash: str = ""
    protocol_hash: str | None = None
    assay: str = ""
    machine: str = ""
    date: str = ""
    inputs: dict[str, str] = Field(default_factory=dict)
    overrides_hash: str = ""
    platform: str = ""
    substrate_id: str = "bare"
    engine_model: str = "lif"
    mechanisms: dict[str, Any] | None = None


class ValidationEntry(StrictModel):
    """One stored validation result with its identity block.

    Units: measured values carry their own units in the measured
    mapping. Shapes: scalars only unless measured says otherwise.
    """

    test_id: str
    category: str = Field(min_length=1)
    outcome: Literal["passed", "failed", "recorded", "unavailable", "stale", "not run"] = "passed"
    compatibility: Literal["canonical", "matching-layers", "run-bound", "development"] = "canonical"
    identity: IdentityBlock
    measured: dict[str, Any] = Field(default_factory=dict)
    data_dependencies: list[str] = Field(default_factory=list)
    fixture_path: str | None = None
    stub: str | None = None
    one_use: bool = False
    declared_inputs: list[str] = Field(default_factory=list)
    grid: bool = False
    grid_points: list[Any] = Field(default_factory=list)
    conservative_binding: bool = False

    @model_validator(mode="after")
    def check_evidence(self) -> Self:
        """Require protocol or stub evidence. Units: none. Shapes: scalar fields."""
        if self.compatibility == "run-bound" and not self.identity.protocol_hash:
            raise ValueError("run-bound entries require a validated protocol hash")
        if self.compatibility == "development" and not self.stub:
            raise ValueError("development entries must name the stub or provisional component")
        return self


def sha256_text(text: str) -> str:
    """Return the SHA-256 hex of one text string.

    Units: none. Shapes: one string in, one hex string out.
    """
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: str | Path) -> str:
    """Return the SHA-256 hex of one file's bytes.

    Units: none. Shapes: one path in, one hex string out.
    """
    from flyonenomics.io import hash_file

    return hash_file(path)


def platform_id() -> str:
    """Return platform.system().lower()-platform.machine(). Units: none."""
    return f"{platform.system().lower()}-{platform.machine()}"


def overrides_hash_from_env(encoded: str | None = None) -> str:
    """SHA-256 of canonical FLYONENOMICS_PARAM_OVERRIDES_JSON, or empty.

    Units: none. Shapes: one hex string.
    """
    raw = encoded if encoded is not None else os.environ.get("FLYONENOMICS_PARAM_OVERRIDES_JSON")
    if not raw:
        return ""
    document = json.loads(raw)
    if not isinstance(document, dict) or not document:
        return ""
    return sha256_text(json.dumps(document, sort_keys=True, separators=(",", ":")))


def canonical_override_hash(point: Mapping[str, Any]) -> str:
    """SHA-256 of one declared grid point. Units: none. Shapes: one hex."""
    return sha256_text(json.dumps(dict(point), sort_keys=True, separators=(",", ":")))


def _git(root: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    """Run one git command in root. Units: none. Shapes: argument list."""
    return subprocess.run(["git", *args], cwd=str(root), capture_output=True, text=True, timeout=30)


def _is_git_repo(root: Path) -> bool:
    """Return whether root is a git work tree. Units: none. Shapes: scalar."""
    try:
        out = _git(root, ["rev-parse", "--is-inside-work-tree"])
    except (OSError, subprocess.SubprocessError):
        return False
    return out.returncode == 0 and out.stdout.strip() == "true"


def _code_paths() -> list[str]:
    """Return the tracked trees that enter code_hash. Units: none. Shapes: path list.

    Fixtures are not part of code_hash: canonical and matching-layers entries
    bind their fixture through fixture_hash, and run manifests (which read no
    entry fixture) must hash the same trees as the entries they quote.
    """
    return ["src", "data", "scripts", "uv.lock"]


def _code_scope_paths() -> list[str]:
    """Return the trees that enter code_scope (item 78, no data/). Units: none."""
    return ["src", "scripts", "uv.lock"]


def _blob_lines_hash(pairs: list[tuple[str, str]]) -> str:
    """Hash (path, git blob id) pairs in path order. Units: none. Shapes: one hex."""
    return sha256_text("".join(f"{blob} {path}\n" for path, blob in sorted(pairs)))


def _head_blobs(root: Path, paths: list[str]) -> list[tuple[str, str]]:
    """Return (path, blob id) of HEAD files under paths. Units: none. Shapes: pair list."""
    out = _git(root, ["ls-tree", "-r", "-z", "HEAD", "--", *paths])
    if out.returncode != 0:
        raise RuntimeError(out.stderr.strip() or "git ls-tree failed")
    pairs = []
    for record in out.stdout.split("\0"):
        if not record:
            continue
        meta, path = record.split("\t", 1)
        _mode, kind, blob = meta.split()
        if kind == "blob":
            pairs.append((path, blob))
    return pairs


def _worktree_blobs(root: Path, paths: list[str]) -> list[tuple[str, str]]:
    """Return (path, git blob id) of working-tree files git would track. Units: none. Shapes: pair list."""
    out = _git(root, ["ls-files", "-z", "-c", "-o", "--exclude-standard", "--", *paths])
    if out.returncode != 0:
        raise RuntimeError(out.stderr.strip() or "git ls-files failed")
    files = sorted({item for item in out.stdout.split("\0") if item and (root / item).is_file()})
    if not files:
        return []
    hashed = subprocess.run(["git", "hash-object", "--stdin-paths"], cwd=str(root), input="\n".join(files) + "\n",
                            capture_output=True, text=True, timeout=120)
    if hashed.returncode != 0:
        raise RuntimeError(hashed.stderr.strip() or "git hash-object failed")
    blobs = hashed.stdout.split()
    if len(blobs) != len(files):
        raise RuntimeError("git hash-object returned a different number of ids")
    return list(zip(files, blobs))


def _filesystem_hash(root: Path, paths: list[str]) -> str:
    """Hash files under paths when git is absent. Units: none. Shapes: one hex with fs: prefix."""
    digest = hashlib.sha256()
    files: list[str] = []
    for rel in paths:
        candidate = root / rel
        if candidate.is_file():
            files.append(rel)
        elif candidate.is_dir():
            files.extend(str(child.relative_to(root)) for child in candidate.rglob("*") if child.is_file())
    for rel in sorted(files):
        digest.update(f"{sha256_file(root / rel)} {rel}\n".encode())
    return "fs:" + digest.hexdigest()


def _content_hash(root: Path, paths: list[str]) -> str:
    """Hash git blobs or filesystem bytes under paths. Units: none. Shapes: one hex."""
    if not _is_git_repo(root):
        return _filesystem_hash(root, paths)
    status = _git(root, ["status", "--porcelain", "--untracked-files=all", "--", *paths])
    if status.returncode != 0:
        raise RuntimeError(status.stderr.strip() or "git status failed")
    pairs = _head_blobs(root, paths) if not status.stdout.strip() else _worktree_blobs(root, paths)
    return "git:" + _blob_lines_hash(pairs)


def code_content_hash(repo: str | Path) -> str:
    """Hash the content of src/, data/, scripts/ and uv.lock (item 69(b)).

    Units: none. Shapes: one string. In a git work tree the hash covers
    (path, git blob id) of every file git tracks or would track there (`git:`).
    A clean tree reads the ids from HEAD's tree; a dirty tree hashes the
    working-tree bytes into the same blob ids, so identical content gives the
    same hash whether or not it is committed. A non-git directory hashes file
    bytes (`fs:`).
    """
    return _content_hash(Path(repo), _code_paths())


def code_scope_hash(repo: str | Path) -> str:
    """Hash git blob ids of src/, scripts/ and uv.lock (SPEC-P2 item 78).

    Units: none. Shapes: one string with git: or fs: prefix.
    """
    return _content_hash(Path(repo), _code_scope_paths())


def blob_id(root: str | Path, relative: str) -> str:
    """Return the git blob id of one file's current bytes. Units: none."""
    base = Path(root)
    path = base / relative
    if not path.is_file():
        raise FileNotFoundError(relative)
    hashed = subprocess.run(
        ["git", "hash-object", "--", str(path)],
        cwd=str(base), capture_output=True, text=True, timeout=30,
    )
    if hashed.returncode != 0:
        raise RuntimeError(hashed.stderr.strip() or "git hash-object failed")
    return hashed.stdout.strip()


def input_blobs(root: str | Path, paths: Iterable[str]) -> dict[str, str]:
    """Map repository-relative paths to blob ids, first-seen order. Units: none."""
    mapping: dict[str, str] = {}
    for rel in paths:
        if rel in mapping:
            continue
        mapping[rel] = blob_id(root, rel)
    return mapping


def repo_commit(repo: str | Path | None = None) -> str:
    """Return the git HEAD commit of the repo, or "unknown".

    Units: none. Shapes: one string.
    """
    try:
        root = Path(repo) if repo is not None else Path(__file__).resolve().parents[3]
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=15,
        )
        if out.returncode == 0:
            return out.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return "unknown"


def machine_id() -> str:
    """Return the machine identifier (model and chip).

    Units: none. Shapes: one string.
    """
    if platform.system() == "Darwin":
        values = []
        for key in ("hw.model", "machdep.cpu.brand_string"):
            result = subprocess.run(["sysctl", "-n", key], check=True, capture_output=True, text=True)
            values.append(result.stdout.strip())
        return " / ".join(values)
    return f"{platform.machine()} {platform.processor()}".strip()


def identity_hash(identity: IdentityBlock) -> str:
    """Return the SHA-256 of the canonical identity JSON.

    Units: none. Shapes: one block in, one hex string out.
    """
    text = json.dumps(identity.model_dump(), sort_keys=True)
    return sha256_text(text)


def _override_allowed(entry: ValidationEntry) -> bool:
    """Return whether a nonempty overrides_hash is one declared grid point."""
    if not entry.identity.overrides_hash:
        return True
    if not entry.grid and entry.test_id not in GRID_ENTRY_IDS:
        return False
    allowed = {canonical_override_hash(point) for point in entry.grid_points if isinstance(point, Mapping)}
    return entry.identity.overrides_hash in allowed


def apply_logged_inputs(
    entry: ValidationEntry, logged: Sequence[str], root: str | Path, *,
    log_present: bool = True,
) -> ValidationEntry:
    """Union declared paths with the merged log and attach blob ids.

    Units: none. Shapes: one entry. A logged path the entry did not declare
    demotes it to development with reason undeclared input. data/provenance.json
    is a common identity dependency (provenance_hash) and is not charged as an
    undeclared input. A missing log falls back to every data/ and
    tests/fixtures/ path and flags conservative binding. Phase 1 entries with
    no declared_inputs are left unchanged.
    """
    if not entry.declared_inputs:
        return entry
    from flyonenomics.io import conservative_inputs

    base = Path(root)
    if not log_present:
        paths = conservative_inputs(base)
        blobs = input_blobs(base, paths)
        measured = {**entry.measured, "conservative binding": True, "binding_reason": "missing dependency log"}
        return entry.model_copy(update={
            "conservative_binding": True,
            "identity": entry.identity.model_copy(update={"inputs": blobs}),
            "measured": measured,
        })
    declared = list(dict.fromkeys(entry.declared_inputs))
    charged = [path for path in logged if path not in COMMON_IDENTITY_PATHS]
    undeclared = [path for path in charged if path not in declared]
    union = list(dict.fromkeys([*declared, *charged]))
    blobs = input_blobs(base, union)
    identity = entry.identity.model_copy(update={"inputs": blobs})
    if undeclared:
        stub = entry.stub or "undeclared input"
        measured = {**entry.measured, "binding_reason": "undeclared input", "undeclared_inputs": undeclared}
        return entry.model_copy(update={
            "compatibility": CompatibilityClass.DEVELOPMENT,
            "stub": stub,
            "identity": identity,
            "measured": measured,
        })
    return entry.model_copy(update={"identity": identity})


def is_compatible(
    entry: ValidationEntry, run: IdentityBlock, *,
    current_fixture_hash: str | None = None, repo: str | Path | None = None,
) -> tuple[bool, str]:
    """Compare a stored entry against a run context.

    Units: none. Shapes: one entry and one block in; one
    (valid, reason) pair out. Implements the section 7 rule:
    canonical entries match on code, environment, data, and
    fixture; matching-layers entries also match on layer flags;
    run-bound entries match on the protocol hash; development
    entries are never valid. SPEC-P2 section 5.1 adds code_scope,
    input blobs, run_code_scope, overrides, and substrate.
    """
    ident = entry.identity
    if entry.outcome == "not run":
        return True, "terminal not-run entry"
    if entry.compatibility == CompatibilityClass.DEVELOPMENT:
        return False, "development entries are never valid"
    if run.uv_lock_hash != ident.uv_lock_hash:
        return False, "uv.lock hash differs"
    if entry.compatibility in (CompatibilityClass.CANONICAL, CompatibilityClass.MATCHING_LAYERS):
        if current_fixture_hash is None and entry.fixture_path:
            root = Path(repo) if repo is not None else Path(__file__).resolve().parents[3]
            path = root / entry.fixture_path
            if path.is_file():
                current_fixture_hash = sha256_file(path)
        if not current_fixture_hash or current_fixture_hash != ident.fixture_hash:
            return False, "canonical fixture missing or hash differs"
    if ident.code_scope:
        if run.code_scope != ident.code_scope:
            return False, "code scope differs"
        if ident.run_code_scope and ident.run_code_scope != ident.code_scope:
            return False, "run scope mismatch"
        if ident.run_code_scope and run.run_code_scope and ident.run_code_scope != run.run_code_scope:
            return False, "run scope mismatch"
        # code_scope leaves data/ out only because inputs bind the data an
        # entry reads. An entry with no recorded inputs keeps code_hash.
        if not ident.inputs and ident.code_hash and run.code_hash != ident.code_hash:
            return False, "code hash differs (entry records no inputs)"
    elif ident.code_hash:
        # Item 77: run_code_hash is recorded but does not stale while code_hash matches.
        if run.code_hash != ident.code_hash:
            return False, "code hash differs"
    elif run.code_commit != ident.code_commit:
        return False, "code commit differs"
    if ident.inputs:
        live_root = Path(repo) if repo is not None else Path(__file__).resolve().parents[3]
        for rel, stored in ident.inputs.items():
            path = live_root / rel
            if not path.is_file():
                return False, f"input blob differs: {rel}"
            if blob_id(live_root, rel) != stored:
                return False, f"input blob differs: {rel}"
    if ident.overrides_hash != run.overrides_hash:
        return False, "overrides hash differs"
    if ident.overrides_hash and not _override_allowed(entry):
        return False, "override outside declared grid"
    ident_model = ident.engine_model or "lif"
    from flyonenomics.drive.mechanisms import substrate_engine_agree

    if not substrate_engine_agree(ident.substrate_id, ident_model):
        return False, "substrate_id and engine_model disagree"
    if entry.compatibility in (CompatibilityClass.MATCHING_LAYERS, CompatibilityClass.RUN_BOUND):
        if ident.substrate_id != run.substrate_id:
            return False, "substrate mismatch"
        run_model = run.engine_model or "lif"
        if ident_model != run_model:
            return False, "engine_model mismatch"
    if run.provenance_hash != ident.provenance_hash:
        return False, "provenance hash differs"
    declared = {Path(path).as_posix() for path in entry.declared_inputs}
    for name in entry.data_dependencies:
        if entry.declared_inputs:
            # A P2 identity records versions of declared files only, so an
            # undeclared (or mistyped) dependency could never be compared.
            if f"data/{name}" not in declared:
                return False, f"data dependency not declared: {name}"
            if name not in ident.data_versions and name not in run.data_versions:
                # A declared file without -vX.Y is bound by its input blob.
                continue
        if (not run.data_versions.get(name) or not ident.data_versions.get(name)
                or run.data_versions[name] != ident.data_versions[name]):
            return False, f"data version differs: {name}"
    if entry.compatibility == CompatibilityClass.MATCHING_LAYERS:
        fields = ("background", "dopamine_A", "transporter_C", "dan_fast_synapses")
        if any(name not in run.layer_flags or name not in ident.layer_flags
               or run.layer_flags[name] != ident.layer_flags[name] for name in fields):
            return False, "layer flags differ"
    if entry.compatibility == CompatibilityClass.RUN_BOUND:
        if run.protocol_hash != ident.protocol_hash:
            return False, "protocol hash differs"
    return True, "valid"


def binding_of(
    entry: ValidationEntry, run: IdentityBlock, *,
    current_fixture_hash: str | None = None, repo: str | Path | None = None,
) -> str:
    """Return "valid" or "stale" for one entry against one run.

    Units: none. Shapes: one entry and one block in, one word out.
    """
    valid, _ = is_compatible(entry, run, current_fixture_hash=current_fixture_hash, repo=repo)
    return "valid" if valid else "stale"


def required_passed_ids(
    component: str, *, visual_status: str = "photoreceptor closed loop",
    include_sigma_th: bool = False, required_passed: Sequence[str] | None = None,
) -> tuple[str, ...]:
    """Return the section 5.2 required-passed ids for one component. Units: none."""
    if required_passed is not None:
        return tuple(required_passed)
    if component == "visual path":
        return VISUAL_PASSED.get(visual_status, ())
    if component == "behaviour":
        return BEHAVIOUR_PASSED.get(visual_status, ())
    ids = COMPONENT_PASSED.get(component)
    if ids is None:
        raise KeyError(f"unknown component: {component}")
    if component == "engine" and include_sigma_th:
        return (*ids[:9], "0.11", *ids[9:])
    return ids


def qualification_of(
    component: str, run: IdentityBlock, *,
    results: Sequence[ValidationEntry], repo: str | Path | None = None,
    visual_status: str = "photoreceptor closed loop",
    include_sigma_th: bool = False, required_passed: Sequence[str] | None = None,
    current_fixture_hash: str | None = None,
) -> tuple[bool, dict[str, str]]:
    """Answer qualification from the section 5.1 rules and the 5.2 map.

    Units: none. Shapes: one (qualified, reasons) pair. A required-passed
    entry must be present, passed, and valid for run. v0.1 file flags are
    not read here.
    """
    wanted = required_passed_ids(
        component, visual_status=visual_status, include_sigma_th=include_sigma_th,
        required_passed=required_passed,
    )
    if required_passed is None and component == "engine":
        model = run.engine_model or "lif"
        extra: tuple[str, ...] = ()
        if model == "lif+sfa":
            extra = ("0.16",)
        elif model == "lif+std":
            extra = ("0.17",)
        elif model == "lif+cbi":
            extra = ("0.18",)
        wanted = (*wanted, *extra)
    by_id = {entry.test_id: entry for entry in results}
    reasons: dict[str, str] = {}
    qualified = True
    for test_id in wanted:
        entry = by_id.get(test_id)
        if entry is None:
            reasons[test_id] = "missing"
            qualified = False
            continue
        if entry.outcome != "passed":
            reasons[test_id] = f"outcome {entry.outcome}"
            qualified = False
            continue
        valid, reason = is_compatible(
            entry, run, repo=repo, current_fixture_hash=current_fixture_hash,
        )
        if not valid:
            reasons[test_id] = reason
            qualified = False
            continue
        reasons[test_id] = "valid"
    return qualified, reasons


def versioned_data_files(root: str | Path) -> list[Path]:
    """Released data files, data/*-vX.Y.yaml, sorted by name. Units: none. Shapes: paths.

    A v0.2 dependency must be recorded too, or its entry is stale on the run
    that wrote it.
    """
    return sorted(path for path in (Path(root) / "data").glob("*-v*.yaml")
                  if re.search(r"-v\d+\.\d+\.yaml$", path.name))


def identity_version_files(
    root: str | Path, declared_inputs: Sequence[str] | None = None,
) -> list[Path]:
    """Versioned data files recorded on one identity. Units: none.

    Phase 1 identities (no declared_inputs) keep every released file.
    Phase 2 identities record only declared numeric `data/*-vX.Y.yaml` paths.
    """
    released = versioned_data_files(root)
    if not declared_inputs:
        return released
    base = Path(root)
    allowed = {Path(item).as_posix() for item in declared_inputs}
    return [path for path in released if path.relative_to(base).as_posix() in allowed]


def build_identity(
    repo: str | Path, *, connectome_version: str, layers: LayerFlags,
    assay: str, fixture: str | Path | None = None, protocol_hash: str | None = None,
    run_code_hash: str | None = None, declared_inputs: Sequence[str] | None = None,
    logged_paths: Sequence[str] | None = None, substrate_id: str | None = None,
    run_code_scope: str | None = None, overrides_hash: str | None = None,
    platform: str | None = None, engine_model: str | None = None,
    mechanisms: dict[str, Any] | None = None,
) -> IdentityBlock:
    """Hash current execution inputs, failing on absent inputs.

    Units: none. Shapes: scalar hashes and a filename-to-version mapping.
    Protocol hash is supplied by the validated experiment serializer (WP4).
    Phase 1 identities record every released data file (*-vX.Y.yaml).
    Phase 2 identities with declared_inputs record only those versioned
    numeric paths. Version strings and provenance_hash are read through
    io inside unlogged(), so they do not charge the dependency log.
    run_code_hash None copies code_hash (this process executed). An empty
    string leaves the Phase 1 gap: the analysed run has no content hash.
    code_scope omits data/. run_code_scope None copies code_scope.
    """
    from flyonenomics.io import read_yaml, unlogged

    root = Path(repo)
    with unlogged():
        versions = {}
        for path in identity_version_files(root, declared_inputs):
            data = read_yaml(path)
            if not isinstance(data, dict) or not isinstance(data.get("version"), str) or not data["version"]:
                raise ValueError(f"missing data version: {path}")
            versions[path.name] = data["version"]
        provenance_hash = sha256_file(root / "data/provenance.json")
    commit = repo_commit(root)
    if commit == "unknown":
        raise ValueError("cannot identify code commit")
    code_hash = code_content_hash(root)
    executed = code_hash if run_code_hash is None else run_code_hash
    scope = code_scope_hash(root)
    executed_scope = scope if run_code_scope is None else run_code_scope
    union: list[str] = []
    if declared_inputs:
        union.extend(declared_inputs)
    if logged_paths:
        union.extend(path for path in logged_paths if path not in COMMON_IDENTITY_PATHS)
    inputs = input_blobs(root, union) if union else {}
    return IdentityBlock(
        code_commit=commit, code_hash=code_hash, run_code_hash=executed,
        code_scope=scope, run_code_scope=executed_scope,
        uv_lock_hash=sha256_file(root / "uv.lock"),
        provenance_hash=provenance_hash,
        data_versions=versions, connectome_version=connectome_version,
        layer_flags={name: getattr(layers, name) for name in layers.__dataclass_fields__},
        fixture_hash=sha256_file(root / fixture) if fixture is not None else "",
        protocol_hash=protocol_hash, assay=assay, machine=machine_id(),
        date=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        inputs=inputs,
        overrides_hash=overrides_hash_from_env() if overrides_hash is None else overrides_hash,
        platform=platform_id() if platform is None else platform,
        substrate_id="bare" if substrate_id is None else substrate_id,
        engine_model="lif" if engine_model is None else engine_model,
        mechanisms=mechanisms,
    )


def logged_suite(test_id: str) -> dict[str, Any]:
    """Run one execute suite with a per-entry dependency log directory.

    Units: none. Shapes: a result or error mapping. Spawned workers import
    this helper so they are not __main__.
    """
    from flyonenomics.io import flush, set_log_dir
    from flyonenomics.validation.execute import run_one_suite

    from flyonenomics.io import clear_log

    root = Path(os.environ.get("FLYONENOMICS_DEPS_ROOT", "."))
    dest = root / test_id
    dest.mkdir(parents=True, exist_ok=True)
    # Pool workers are reused; start each entry with an empty log.
    clear_log()
    set_log_dir(dest)
    os.environ["FLYONENOMICS_DEPS_DIR"] = str(dest)
    row = run_one_suite(test_id)
    flush(dest)
    return row
