"""Phase 2 level-0 binding suites: 0.9r and 0.12 (WP16).

0.9r covers the Phase 1 0.9 cases, constructed section 5.1 clauses, the
freeze protocol on a constructed git repository, and dependency-log
negatives including the static read-call scan. 0.12 checks frozen
section 1.3 files against tests/fixtures/frozen-v0.1.json and, when
params-v0.2.yaml exists, unchanged v0.1 rows.
"""

from __future__ import annotations

import ast
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable

from flyonenomics.io import (
    clear_log,
    conservative_inputs,
    logged_paths,
    merge_logs,
    read_bytes,
    read_json,
    read_parquet,
    read_text,
    read_yaml,
    set_log_dir,
    set_repo_root,
)
from flyonenomics.types import LayerFlags
from flyonenomics.validation.binding import (
    IdentityBlock,
    ValidationEntry,
    apply_logged_inputs,
    build_identity,
    is_compatible,
    qualification_of,
    sha256_text,
)

REPO = Path(__file__).resolve().parents[3]
FROZEN_FIXTURE = "tests/fixtures/frozen-v0.1.json"
ALLOWLIST_FIXTURE = "tests/fixtures/io-allowlist.json"
CHANGED_PARAM_ROWS = frozenset({"vis.inject_at"})
FROZEN_FILES = (
    "data/params-v0.1.yaml",
    "data/populations-v0.1.yaml",
    "data/compartments-v0.1.yaml",
    "data/receptors-v0.1.yaml",
    "data/drive-dev.yaml",
    "data/dopamine-v0.1.yaml",
    "data/behaviour-v0.1.yaml",
    "data/brembs-split.json",
)


def _call_name(node: ast.AST) -> str:
    """Return a dotted call name, or empty. Units: none."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _call_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    return ""


def _const_str(node: ast.AST | None) -> str | None:
    """Return a string constant, or None. Units: none."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _open_mode(node: ast.Call, *, is_method: bool) -> str:
    """Return the mode of an open() or Path.open() call. Units: none."""
    idx = 0 if is_method else 1
    if len(node.args) > idx:
        mode = _const_str(node.args[idx])
        if mode is not None:
            return mode
    for keyword in node.keywords:
        if keyword.arg == "mode":
            mode = _const_str(keyword.value)
            if mode is not None:
                return mode
    return "r"


def _is_read_mode(mode: str) -> bool:
    """Return whether a file mode can read. Units: none."""
    return "r" in mode or "+" in mode


class _ReadVisitor(ast.NodeVisitor):
    """Collect direct file reads that must go through io.py."""

    def __init__(self, aliases: dict[str, str], function: str) -> None:
        self.aliases = aliases
        self.function = function
        self.hits: list[dict[str, Any]] = []

    def _kind(self, node: ast.Call) -> str | None:
        name = _call_name(node.func)
        mapped = name
        # A method on an unnamed receiver, such as (root / "x").read_text() or
        # Path(p).read_bytes(), is never an imported name, whatever the module imports.
        unnamed_receiver = isinstance(node.func, ast.Attribute) and not _call_name(node.func.value)
        if unnamed_receiver:
            pass
        elif name in self.aliases:
            mapped = self.aliases[name]
        else:
            head = name.split(".", 1)[0]
            if head in self.aliases:
                mapped = self.aliases[head] + name[len(head):]
        if "flyonenomics.io" in mapped:
            return None
        func = node.func
        is_builtin_open = isinstance(func, ast.Name) and func.id == "open"
        is_path_open = (
            isinstance(func, ast.Attribute)
            and func.attr == "open"
            and _call_name(func.value) not in {"os", "posix"}
        )
        if is_builtin_open or is_path_open:
            if _is_read_mode(_open_mode(node, is_method=is_path_open)):
                return "open"
            return None
        if mapped.endswith("read_text") or name.endswith("read_text"):
            return "Path.read_text"
        if mapped.endswith("read_bytes") or name.endswith("read_bytes"):
            return "Path.read_bytes"
        if mapped in {"pandas.read_parquet", "pd.read_parquet"} or mapped.endswith("pandas.read_parquet"):
            return "pandas.read_parquet"
        if mapped.endswith("ParquetFile"):
            return "pyarrow.parquet.ParquetFile"
        if mapped.endswith("read_table") and ("parquet" in mapped or mapped.endswith("pq.read_table")):
            return "pyarrow.parquet.read_table"
        if mapped in {"numpy.load", "np.load"} or mapped in {"numpy.load"} or mapped.endswith("numpy.load"):
            return "numpy.load"
        if mapped.endswith(".load") and mapped.split(".", 1)[0] in {"np", "numpy"}:
            return "numpy.load"
        if mapped == "json.load" or mapped.endswith(".json.load") or mapped.endswith("json.load") and not mapped.endswith("json.loads"):
            if mapped.endswith("json.loads"):
                return None
            if mapped == "json.load" or mapped.endswith(".load") and "json" in mapped and not mapped.endswith("loads"):
                return "json.load"
        if mapped in {"yaml.safe_load", "yaml.load"} or mapped.endswith("yaml.safe_load") or mapped.endswith("yaml.load"):
            arg = node.args[0] if node.args else None
            if isinstance(arg, ast.Name):
                return "yaml.load"
        return None

    def visit_Call(self, node: ast.Call) -> None:
        kind = self._kind(node)
        if kind is not None:
            self.hits.append({
                "line": node.lineno,
                "kind": kind,
                "name": self.function,
            })
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        inner = _ReadVisitor(self.aliases, node.name)
        for child in node.body:
            inner.visit(child)
        self.hits.extend(inner.hits)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        inner = _ReadVisitor(self.aliases, node.name)
        for child in node.body:
            inner.visit(child)
        self.hits.extend(inner.hits)


def _aliases(tree: ast.AST) -> dict[str, str]:
    """Map imported names to modules. Units: none. Shapes: small mapping."""
    aliases: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                aliases[alias.asname or alias.name] = alias.name
        elif isinstance(node, ast.ImportFrom) and node.module:
            for alias in node.names:
                local = alias.asname or alias.name
                aliases[local] = f"{node.module}.{alias.name}"
    return aliases


def scan_read_calls(root: str | Path, *, allowlist: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """Scan src/ and scripts/ for direct file reads outside io.py.

    Units: none. Shapes: a list of hit mappings. Hits listed in the
    allowlist with file, kind, and name are omitted.
    """
    base = Path(root)
    allowed = {(item.get("file"), item.get("kind"), item.get("name")) for item in (allowlist or [])}
    hits: list[dict[str, Any]] = []
    for folder in (base / "src", base / "scripts"):
        if not folder.is_dir():
            continue
        for path in sorted(folder.rglob("*.py")):
            rel = path.relative_to(base).as_posix()
            if rel.endswith("/io.py") or rel == "src/flyonenomics/io.py":
                continue
            tree = ast.parse(read_text(path), filename=rel)
            visitor = _ReadVisitor(_aliases(tree), "<module>")
            visitor.visit(tree)
            for hit in visitor.hits:
                key = (rel, hit["kind"], hit["name"])
                generic = (rel, hit["kind"], None)
                if key in allowed or generic in allowed:
                    continue
                hits.append({"file": rel, **hit})
    return hits


def load_allowlist(root: str | Path | None = None) -> list[dict[str, Any]]:
    """Load tests/fixtures/io-allowlist.json. Units: none. Shapes: a list."""
    base = REPO if root is None else Path(root)
    payload = read_json(base / ALLOWLIST_FIXTURE)
    if isinstance(payload, dict):
        return list(payload.get("allow", []))
    if isinstance(payload, list):
        return payload
    raise ValueError("io-allowlist.json must be a list or a mapping with allow")


def _git(root: Path, args: list[str]) -> None:
    """Run one git command. Units: none."""
    subprocess.run(["git", *args], cwd=str(root), check=True, capture_output=True, text=True)


def _commit(root: Path, message: str) -> None:
    """Stage every change and commit. Units: none."""
    _git(root, ["add", "-A"])
    _git(root, ["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", message])


def _freeze_repo(root: Path) -> None:
    """Create a constructed repository for 0.9r(c). Units: none."""
    files = {
        "src/pkg/a.py": "x = 1\n",
        "scripts/run.py": "print(1)\n",
        "uv.lock": "lock\n",
        "data/config.yaml": "value: 1\n",
        "data/unrelated.yaml": "other: 1\n",
        "data/params-v0.1.yaml": "version: v0.1\n",
        "data/provenance.json": "{}\n",
        "docs/evidence.md": "notes\n",
        "tests/fixtures/f.json": "{}\n",
        ".gitignore": "__pycache__/\n",
    }
    for rel, text in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    _git(root, ["init", "-q"])
    _commit(root, "configuration")


def _part_a() -> dict[str, Any]:
    """Reuse the Phase 1 0.9 cases. Units: none."""
    from flyonenomics.validation.level0 import test_0_9

    entry = test_0_9()
    return {"passed": entry.outcome == "passed", "measured": entry.measured}


def _part_b(tmp: Path) -> dict[str, Any]:
    """Constructed cases for each section 5.1 clause. Units: none."""
    _freeze_repo(tmp)
    set_repo_root(tmp)
    layers = LayerFlags()
    identity = build_identity(
        tmp, connectome_version="783", layers=layers, assay="binding",
        declared_inputs=["data/config.yaml"], fixture="tests/fixtures/f.json",
    )
    entry = ValidationEntry(
        test_id="0.9r-b", category="verification", identity=identity,
        declared_inputs=["data/config.yaml"], data_dependencies=["config.yaml"],
        fixture_path="tests/fixtures/f.json",
    )
    run = identity.model_copy()
    ok_base, _ = is_compatible(entry, run, repo=tmp)
    scope_run = run.model_copy(update={"code_scope": run.code_scope + "x"})
    ok_scope, reason_scope = is_compatible(entry, scope_run, repo=tmp)
    mismatch = entry.model_copy(update={
        "identity": identity.model_copy(update={"run_code_scope": identity.code_scope + "y"}),
    })
    ok_run, reason_run = is_compatible(mismatch, run, repo=tmp)
    (tmp / "data/config.yaml").write_text("value: 2\n")
    _commit(tmp, "config byte")
    later = build_identity(
        tmp, connectome_version="783", layers=layers, assay="binding",
        declared_inputs=["data/config.yaml"], fixture="tests/fixtures/f.json",
    )
    ok_blob, reason_blob = is_compatible(entry, later, repo=tmp)
    (tmp / "data/config.yaml").write_text("value: 1\n")
    _commit(tmp, "restore config")
    restored = build_identity(
        tmp, connectome_version="783", layers=layers, assay="binding",
        declared_inputs=["data/config.yaml"], fixture="tests/fixtures/f.json",
    )
    extra = apply_logged_inputs(entry, ["data/config.yaml", "data/unrelated.yaml"], tmp)
    undeclared = extra.compatibility == "development" and extra.measured.get("binding_reason") == "undeclared input"
    grid_entry = entry.model_copy(update={
        "grid": True,
        "grid_points": [{"vis.pr_rate_light_hz": 100}],
        "identity": identity.model_copy(update={
            "overrides_hash": sha256_text(json.dumps({"vis.pr_rate_light_hz": 100}, sort_keys=True, separators=(",", ":"))),
        }),
    })
    grid_run = restored.model_copy(update={"overrides_hash": grid_entry.identity.overrides_hash})
    ok_grid, _ = is_compatible(grid_entry, grid_run, repo=tmp)
    outside = grid_entry.model_copy(update={"grid_points": [{"vis.pr_rate_light_hz": 50}]})
    ok_outside, reason_outside = is_compatible(outside, grid_run, repo=tmp)
    match_entry = ValidationEntry(
        test_id="0.9r-sub", category="verification", compatibility="matching-layers",
        identity=identity.model_copy(update={"substrate_id": "rest:0123456789abcdef"}),
        declared_inputs=["data/config.yaml"], data_dependencies=["config.yaml"],
        fixture_path="tests/fixtures/f.json",
    )
    ok_sub, reason_sub = is_compatible(match_entry, restored, repo=tmp)
    passed = (
        ok_base and not ok_scope and "code scope" in reason_scope
        and not ok_run and "run scope" in reason_run
        and not ok_blob and "input blob" in reason_blob
        and undeclared and ok_grid and not ok_outside and "grid" in reason_outside
        and not ok_sub and "substrate" in reason_sub
    )
    return {
        "passed": passed,
        "base": ok_base, "code_scope": reason_scope, "run_scope": reason_run,
        "input_blob": reason_blob, "undeclared": undeclared,
        "grid_inside": ok_grid, "grid_outside": reason_outside,
        "substrate": reason_sub,
    }


def _part_c(tmp: Path) -> dict[str, Any]:
    """Freeze protocol on a constructed git repository. Units: none."""
    _freeze_repo(tmp)
    set_repo_root(tmp)
    layers = LayerFlags()
    identity = build_identity(
        tmp, connectome_version="783", layers=layers, assay="freeze",
        declared_inputs=["data/config.yaml"], fixture="tests/fixtures/f.json",
    )
    entry = ValidationEntry(
        test_id="freeze", category="verification", identity=identity,
        declared_inputs=["data/config.yaml"], data_dependencies=["config.yaml"],
        fixture_path="tests/fixtures/f.json",
    )
    steps: list[dict[str, Any]] = []

    def check(label: str, expect: bool) -> None:
        run = build_identity(
            tmp, connectome_version="783", layers=layers, assay="freeze",
            declared_inputs=["data/config.yaml"], fixture="tests/fixtures/f.json",
        )
        valid, reason = is_compatible(entry, run, repo=tmp)
        qualified, reasons = qualification_of(
            "freeze", run, results=[entry], repo=tmp, required_passed=["freeze"],
        )
        steps.append({
            "label": label, "valid": valid, "reason": reason,
            "qualified": qualified, "qualification": reasons, "expect": expect,
        })

    check("execution", True)
    (tmp / "docs/evidence.md").write_text("evidence commit\n")
    _commit(tmp, "evidence")
    check("evidence", True)
    (tmp / "data/unrelated.yaml").write_text("other: 2\n")
    _commit(tmp, "unrelated data")
    check("unrelated", True)
    (tmp / "data/config.yaml").write_text("value: 9\n")
    _commit(tmp, "configuration byte")
    check("config", False)
    (tmp / "data/config.yaml").write_text("value: 1\n")
    _commit(tmp, "restore configuration")
    (tmp / "src/pkg/a.py").write_text("x = 2\n")
    _commit(tmp, "src change")
    check("src", False)
    passed = all(step["valid"] is step["expect"] and step["qualified"] is step["expect"] for step in steps)
    return {"passed": passed, "steps": steps, "code_scope": identity.code_scope}


def _write_parquet(path: Path) -> None:
    """Write one tiny parquet file. Units: none. Shapes: one row."""
    import pyarrow as pa
    import pyarrow.parquet as parquet

    path.parent.mkdir(parents=True, exist_ok=True)
    table = pa.table({"n": [1]})
    parquet.write_table(table, path)


def _part_d(tmp: Path) -> dict[str, Any]:
    """Dependency-log negatives. Units: none."""
    parquet_path = tmp / "data" / "reference" / "l5-baseline-spikes.parquet"
    _write_parquet(parquet_path)
    set_repo_root(tmp)
    clear_log()
    read_parquet(parquet_path)
    logged = logged_paths()
    io_logged = "data/reference/l5-baseline-spikes.parquet" in logged
    (tmp / "src").mkdir(parents=True, exist_ok=True)
    (tmp / "scripts").mkdir(parents=True, exist_ok=True)
    bad = tmp / "src" / "direct_parquet.py"
    bad.write_text(
        "import pyarrow.parquet as pq\n"
        "def load():\n"
        "    return pq.read_table('data/reference/l5-baseline-spikes.parquet')\n"
    )
    direct_hits = scan_read_calls(tmp, allowlist=[])
    direct_failed = any(hit["kind"] == "pyarrow.parquet.read_table" for hit in direct_hits)
    log_dir = tmp / "deps-spawn"
    log_dir.mkdir()
    data_file = tmp / "data" / "params-v0.1.yaml"
    data_file.parent.mkdir(parents=True, exist_ok=True)
    data_file.write_text("version: v0.1\n")
    code = (
        "from flyonenomics.io import set_log_dir, set_repo_root, read_text, flush\n"
        f"set_repo_root({str(tmp)!r})\n"
        f"set_log_dir({str(log_dir)!r})\n"
        f"read_text({str(data_file)!r})\n"
        "flush()\n"
    )
    proc = subprocess.run([sys.executable, "-c", code], cwd=str(tmp), capture_output=True, text=True)
    merged = merge_logs(log_dir) if proc.returncode == 0 else []
    spawned = "data/params-v0.1.yaml" in merged
    # Env-only child: the log directory arrives through FLYONENOMICS_DEPS_DIR
    # and the file is written by the atexit flush, as in a spawned worker.
    env_dir = tmp / "deps-env"
    env_code = (
        "from flyonenomics.io import set_repo_root, read_text\n"
        f"set_repo_root({str(tmp)!r})\n"
        f"read_text({str(data_file)!r})\n"
    )
    env_proc = subprocess.run(
        [sys.executable, "-c", env_code], cwd=str(tmp), capture_output=True, text=True,
        env={**os.environ, "FLYONENOMICS_DEPS_DIR": str(env_dir)},
    )
    env_logged = env_proc.returncode == 0 and "data/params-v0.1.yaml" in (merge_logs(env_dir) if env_dir.is_dir() else [])
    missing_dir = tmp / "deps-missing"
    missing_dir.mkdir()
    # A process that leaves no log: the entry binds conservatively on every data/ and fixture path.
    probe = ValidationEntry(
        test_id="probe", category="verification", outcome="passed", compatibility="canonical",
        identity=IdentityBlock(code_commit="constructed", uv_lock_hash="constructed", provenance_hash="constructed"),
        declared_inputs=["data/params-v0.1.yaml"],
    )
    bound = apply_logged_inputs(probe, merge_logs(missing_dir), tmp, log_present=bool(list(missing_dir.glob("deps-*.json"))))
    missing_triggers = bool(
        bound.conservative_binding
        and set(bound.identity.inputs) == set(conservative_inputs(tmp))
        and "data/reference/l5-baseline-spikes.parquet" in bound.identity.inputs
    )
    clear_log()
    set_repo_root(tmp)
    read_text(data_file)
    plain = "data/params-v0.1.yaml" in logged_paths()
    evasion = tmp / "src" / "unnamed_receiver.py"
    evasion.write_text(
        "from pathlib import Path\n"
        "from flyonenomics.io import read_text, read_bytes\n"
        "def load(root):\n"
        "    return (root / 'data/x.yaml').read_text(), Path(root).read_bytes()\n"
    )
    evasion_kinds = {hit["kind"] for hit in scan_read_calls(tmp, allowlist=[])
                     if hit.get("file", "").endswith("unnamed_receiver.py")}
    evasion_caught = evasion_kinds == {"Path.read_text", "Path.read_bytes"}
    passed = (io_logged and direct_failed and spawned and env_logged and missing_triggers and plain
              and evasion_caught and proc.returncode == 0)
    return {
        "passed": passed, "io_logged": io_logged, "direct_failed": direct_failed,
        "spawned": spawned, "spawned_env_only": env_logged, "conservative": missing_triggers,
        "plain": plain, "unnamed_receiver_caught": evasion_caught,
        "direct_hits": direct_hits,
    }


def _param_values(node: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    """Flatten params YAML rows to dotted keys. Units: per row."""
    values: dict[str, Any] = {}
    for name, child in node.items():
        if name == "version" or not isinstance(child, dict):
            continue
        key = f"{prefix}.{name}" if prefix else name
        if "value" in child:
            values[key] = child["value"]
        else:
            values.update(_param_values(child, key))
    return values


def static_read_call_check(root: str | Path | None = None) -> dict[str, Any]:
    """Run the 0.9r static scan against root. Units: none."""
    base = REPO if root is None else Path(root)
    allow = load_allowlist(base) if (base / ALLOWLIST_FIXTURE).is_file() else []
    hits = scan_read_calls(base, allowlist=allow)
    return {"passed": not hits, "hits": hits, "allowlist": len(allow)}


def test_0_9r() -> ValidationEntry:
    """Verification 0.9r: binding clauses, freeze protocol, and dependency log."""
    part_a = _part_a()
    try:
        with tempfile.TemporaryDirectory() as first:
            part_b = _part_b(Path(first))
        with tempfile.TemporaryDirectory() as second:
            part_c = _part_c(Path(second))
        with tempfile.TemporaryDirectory() as third:
            part_d = _part_d(Path(third))
    finally:
        # The parts point io at temporary repositories; restore the real root
        # and an empty log even when a part raises.
        set_repo_root(REPO)
        clear_log()
    static = static_read_call_check(REPO)
    part_d_ok = bool(part_d["passed"] and static["passed"])
    passed = bool(part_a["passed"] and part_b["passed"] and part_c["passed"] and part_d_ok)
    identity = build_identity(
        REPO, connectome_version="783", layers=LayerFlags(), assay="binding",
        fixture=FROZEN_FIXTURE,
    )
    return ValidationEntry(
        test_id="0.9r", category="verification",
        outcome="passed" if passed else "failed", compatibility="canonical",
        identity=identity, fixture_path=FROZEN_FIXTURE,
        measured={
            "a": part_a, "b": part_b, "c": part_c, "d": part_d, "static": static,
        },
    )


def test_0_12() -> ValidationEntry:
    """Verification 0.12: frozen v0.1 SHA-256s and unchanged params rows."""
    listed = read_json(REPO / FROZEN_FIXTURE)
    if not isinstance(listed, dict):
        raise ValueError("frozen-v0.1.json must map paths to SHA-256 hex")
    files: dict[str, dict[str, Any]] = {}
    frozen_ok = True
    for rel in FROZEN_FILES:
        digest = hashlib.sha256(read_bytes(REPO / rel)).hexdigest()
        expected = listed.get(rel)
        match = expected == digest
        files[rel] = {"sha256": digest, "expected": expected, "match": match}
        frozen_ok = frozen_ok and bool(match)
    v2_path = REPO / "data" / "params-v0.2.yaml"
    params_report: dict[str, Any]
    params_ok = True
    if not v2_path.is_file():
        # WP15 has landed params-v0.2.yaml; its absence is a failure, not a pending half.
        params_ok = False
        params_report = {"status": "missing params-v0.2.yaml", "changed_allowed": sorted(CHANGED_PARAM_ROWS)}
    else:
        v1 = _param_values(read_yaml(REPO / "data" / "params-v0.1.yaml"))
        v2 = _param_values(read_yaml(v2_path))
        drifted = []
        for key, value in v1.items():
            if key in CHANGED_PARAM_ROWS:
                continue
            if key not in v2 or v2[key] != value:
                drifted.append(key)
        params_ok = not drifted
        params_report = {"status": "compared", "drifted": drifted, "v0_1_rows": len(v1)}
    passed = frozen_ok and params_ok
    identity = build_identity(
        REPO, connectome_version="783", layers=LayerFlags(), assay="binding",
        fixture=FROZEN_FIXTURE,
    )
    return ValidationEntry(
        test_id="0.12", category="verification",
        outcome="passed" if passed else "failed", compatibility="canonical",
        identity=identity, fixture_path=FROZEN_FIXTURE,
        measured={"files": files, "params_v0_2": params_report, "frozen_ok": frozen_ok},
    )


SUITE: dict[str, Callable[[], ValidationEntry]] = {
    "0.9r": test_0_9r,
    "0.12": test_0_12,
}
