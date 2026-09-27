"""WP7 tool-server tests: stdio protocol, fixture answers, negatives, structure, e2e.

Units and shapes: rates in Hz, ticks integer recording ticks, tables
(rows, columns) mappings. The fixture run id is discovered, never pinned.
"""
from __future__ import annotations

import asyncio
import copy
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import pytest

REPO = Path(__file__).resolve().parents[1]
FIXTURE_RUNS = REPO / "tests/fixtures/server-run"
_SERVED_RUNS: list[Path] = []
SUGAR_DOC = json.loads((REPO / "tests/fixtures/experiments/server-sugar.json").read_text())
FULL_SUGAR_DOC = json.loads((REPO / "data/experiments/sugar-reflex.json").read_text())

EXPECTED_TOOLS = ["describe_lab", "list_populations", "describe_population",
                  "list_compartments", "resolve_population", "get_schema",
                  "example_experiments", "validate_experiment", "run_experiment",
                  "run_status", "cancel_run", "get_results", "list_runs",
                  "compare_runs", "validation_status"]
RESULT_WHATS = ["summary", "metrics", "provenance", "slow_state", "dopamine",
                "arena", "rates", "spikes", "popcount", "receptors", "drug", "index", "live"]
LONG_EXEMPT = {"what_the_map_leaves_out", "schema"}
E2E_TIMEOUT_S = 600.0
E2E_POLL_S = 10.0


def fixture_run_id() -> str:
    """Return the stored fixture run id; units none, one id string."""
    ids = sorted(p.name for p in FIXTURE_RUNS.iterdir() if p.is_dir())
    assert len(ids) == 1, ids
    return ids[0]


def served_runs() -> Path:
    """Return a session copy of the committed server-run fixture; units none, one path.

    The spawned server opens `index.sqlite` read-write (WAL mode), which creates
    `-shm`/`-wal` sidecars beside it; a killed session leaves them behind. It is
    never pointed at the committed fixture directory itself.
    """
    if not _SERVED_RUNS:
        import atexit
        import shutil
        import tempfile
        root = Path(tempfile.mkdtemp(prefix="flyonenomics-server-run-"))
        atexit.register(shutil.rmtree, root, True)
        shutil.copytree(FIXTURE_RUNS, root / "runs")
        _SERVED_RUNS.append(root / "runs")
    return _SERVED_RUNS[0]


def server_env(runs_dir: Path) -> dict[str, str]:
    """Build the spawned server environment; units none, string mapping."""
    env = {"PATH": os.environ.get("PATH", ""), "HOME": os.environ.get("HOME", ""),
           "FLYONENOMICS_RUNS_DIR": str(runs_dir)}
    if os.environ.get("FLYONENOMICS_CACHE_DIR"):
        env["FLYONENOMICS_CACHE_DIR"] = os.environ["FLYONENOMICS_CACHE_DIR"]
    return env


async def _session(runs_dir: Path, calls: list[tuple[str, dict[str, Any]]]) -> list[dict[str, Any]]:
    """Run tool calls over one stdio session; units per tool, payload list."""
    from mcp.client.stdio import StdioServerParameters, stdio_client
    from mcp import ClientSession

    params = StdioServerParameters(command=sys.executable,
                                   args=["-m", "flyonenomics.server.mcp_server"],
                                   cwd=str(REPO), env=server_env(runs_dir))
    out: list[dict[str, Any]] = []
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            for name, args in calls:
                result = await session.call_tool(name, args)
                payload = result.structuredContent
                if payload is None:
                    payload = json.loads(result.content[0].text)
                out.append(dict(payload))
    return out


def call_all(runs_dir: Path, calls: list[tuple[str, dict[str, Any]]]) -> list[dict[str, Any]]:
    """Drive one stdio session synchronously; units per tool, payload list."""
    return asyncio.run(_session(runs_dir, calls))


def call_one(tool: str, args: dict[str, Any], runs_dir: Path | None = None) -> dict[str, Any]:
    """Call one tool over stdio; units per tool, one payload mapping."""
    return call_all(served_runs() if runs_dir is None else runs_dir, [(tool, args)])[0]


def test_entry_point_lists_tools() -> None:
    """The installed script resolves and names every tool; units none, CLI check."""
    import subprocess

    completed = subprocess.run([sys.executable, "-m", "flyonenomics.server.mcp_server",
                                "--list-tools"], cwd=str(REPO), capture_output=True,
                               text=True, timeout=120)
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.split() == EXPECTED_TOOLS


def test_stdio_tool_list_exact() -> None:
    """The server exposes exactly the section 3.7 tools; units none, name list."""
    from mcp.client.stdio import StdioServerParameters, stdio_client
    from mcp import ClientSession

    async def main() -> list[str]:
        params = StdioServerParameters(command=sys.executable,
                                       args=["-m", "flyonenomics.server.mcp_server"],
                                       cwd=str(REPO), env=server_env(served_runs()))
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = await session.list_tools()
                return [t.name for t in tools.tools]

    assert asyncio.run(main()) == EXPECTED_TOOLS


def test_tools_answer_fixture() -> None:
    """Every read tool answers against the stored run; units per tool, payloads."""
    run_id = fixture_run_id()
    lab = call_one("describe_lab", {})
    assert lab["substrate"]["connectome_version"] == "783"
    assert "volume transmission" in lab["what_the_map_leaves_out"]
    assert lab["slow_state"] == "phase1-drug-only"

    pops = call_one("list_populations", {})
    counts = {p["name"]: p["count"] for p in pops["populations"]}
    assert counts["MN9"] == 1 and counts["sugar_GRN_R"] == 21

    desc = call_one("describe_population", {"name": "MN9"})
    assert desc["ok"] is True and desc["count"] == 1

    comps = call_one("list_compartments", {})
    assert comps["n"] == 37

    res = call_one("resolve_population", {"spec": {"name": "sugar_GRN_R"}})
    assert res["ok"] is True and res["count"] == 21 and len(res["root_ids"]) == 21

    schema = call_one("get_schema", {})
    assert schema["schema"]["title"] == "Experiment"

    examples = call_one("example_experiments", {})
    assert [e["label"] for e in examples["examples"]] == ["sugar-reflex", "spontaneous", "acceptance-6.3"]
    assert examples["examples"][0]["validation"]["ok"] is True

    valid = call_one("validate_experiment", {"experiment": SUGAR_DOC})
    assert valid["ok"] is True and valid["counts"] == {"MN9": 1, "sugar_GRN_R": 21}
    assert valid["experiment"]["meta"]["_resolved_populations"] == valid["resolved"]
    assert valid["root_ids"]["sugar_GRN_R"] == res["root_ids"]

    status = call_one("run_status", {"run_id": run_id})
    assert status["ok"] is True and status["status"]["state"] == "done"
    assert status["layers"]["background"]["value"] is False

    for what in RESULT_WHATS:
        got = call_one("get_results", {"run_id": run_id, "what": what})
        assert got["ok"] is True, (what, got.get("errors"))
        assert got["selected"] == {"arm": "wild-type", "seed": 1, "probe": 0}
        if what in ("dopamine", "arena", "rates", "spikes", "popcount", "slow_state"):
            assert got["table"]["rows"] >= 0 and len(got["table"]["preview"]) <= 50
        if what in ("arena", "rates", "spikes", "popcount", "slow_state"):
            assert got["table"]["rows"] > 0
        if what == "live":
            assert got["live"]["n_lines"] == 10 and len(got["live"]["events"]) <= 20

    runs = call_one("list_runs", {"filter": {"state": "done"}})
    assert runs["ok"] is True and runs["n"] == 1 and runs["runs"][0]["run_id"] == run_id

    cmp_ = call_one("compare_runs", {"run_ids": [run_id, run_id],
                                    "metric": "probe-0.MN9.mean_rate_hz"})
    assert cmp_["ok"] is True and cmp_["paired"] is not None

    vs = call_one("validation_status", {})
    assert vs["ok"] is True and vs["n"] > 0
    assert all(set(e) == {"test_id", "class", "outcome", "binding", "reason"} for e in vs["entries"])


def _buridan_doc() -> dict[str, Any]:
    """Copy the sugar fixture with buridan probes; units per schema, one dict."""
    doc = copy.deepcopy(SUGAR_DOC)
    for arm in doc["arms"]:
        for phase in arm["protocol"]:
            phase["assay"] = "buridan"
            phase["params"] = {"stripes": True, "encoder": "off"}
    return doc


def test_negative_validations() -> None:
    """Unknown fields, drugs, arms, substrates fail as errors; units none, verdicts."""
    bad = copy.deepcopy(SUGAR_DOC)
    bad["bogus"] = 1
    assert call_one("validate_experiment", {"experiment": bad})["ok"] is False

    amp = copy.deepcopy(SUGAR_DOC)
    amp["arms"][0]["protocol"].insert(0, {"type": "dose", "drug": "amphetamine", "c_food_mm": 0.5})
    out = call_one("validate_experiment", {"experiment": amp})
    assert out["ok"] is False and any("amphetamine" in e for e in out["errors"])

    unmatched = copy.deepcopy(SUGAR_DOC)
    unmatched["arms"][1]["protocol"][0]["duration_s"] = 2
    out = call_one("validate_experiment", {"experiment": unmatched})
    assert out["ok"] is False and any("protocol[0].duration_s" in e for e in out["errors"])

    v630 = copy.deepcopy(SUGAR_DOC)
    v630["substrate"]["connectome_version"] = "630"
    out = call_one("validate_experiment", {"experiment": v630})
    assert out["ok"] is False and any("630" in e for e in out["errors"])

    buridan = _buridan_doc()
    # WP6 now accepts valid Buridan. Keep this a negative schema test without
    # launching a whole-brain experiment from the fast test group.
    buridan["arms"][0]["protocol"][0]["params"]["inject_at"] = "NoSuchPopulation"
    out = call_one("validate_experiment", {"experiment": buridan})
    assert out["ok"] is False and any("inject_at" in e for e in out["errors"])
    out = call_one("run_experiment", {"experiment": buridan, "n_workers": 2})
    assert out["ok"] is False and "run_id" not in out

    run_id = fixture_run_id()
    assert call_one("get_results", {"run_id": "no-such-run", "what": "summary"})["ok"] is False
    out = call_one("get_results", {"run_id": run_id, "what": "no-such-what"})
    assert out["ok"] is False and "summary" in out["errors"][0]
    assert call_one("compare_runs", {"run_ids": [run_id, "no-such-run"],
                                    "metric": "probe-0.MN9.mean_rate_hz"})["ok"] is False
    assert call_one("cancel_run", {"run_id": "no-such-run"})["ok"] is False
    assert call_one("describe_population", {"name": "Nope"})["ok"] is False
    assert call_one("resolve_population", {"spec": {"name": "Nope"}})["ok"] is False


def _walk_strings(node: Any, path: str, exempt: set[str], found: list[tuple[str, str]]) -> None:
    """Collect string fields outside exempt subtrees; units chars, path list."""
    if isinstance(node, dict):
        for key, value in node.items():
            if key in exempt and "." not in path and "[" not in path:
                continue
            found.append((f"{path}.<key>", str(key)))
            _walk_strings(value, f"{path}.{key}", exempt, found)
    elif isinstance(node, list):
        for i, value in enumerate(node):
            _walk_strings(value, f"{path}[{i}]", exempt, found)
    elif isinstance(node, str):
        found.append((path, node))


def test_structural_rule() -> None:
    """Payloads lead with the three keys and carry no long prose; units chars, walk."""
    from flyonenomics.server import mcp_server

    run_id = fixture_run_id()
    calls: list[tuple[str, dict[str, Any]]] = [
        ("describe_lab", {}), ("list_populations", {}),
        ("describe_population", {"name": "MN9"}), ("list_compartments", {}),
        ("resolve_population", {"spec": {"name": "MN9"}}), ("get_schema", {}),
        ("example_experiments", {}), ("validate_experiment", {"experiment": SUGAR_DOC}),
        # A format-only test must remain non-executing as new assays land.
        ("run_experiment", {"experiment": {}, "n_workers": 2}),
        ("run_status", {"run_id": run_id}), ("cancel_run", {"run_id": "no-such-run"}),
        ("list_runs", {"filter": {}}),
        ("compare_runs", {"run_ids": [run_id, run_id], "metric": "probe-0.MN9.mean_rate_hz"}),
        ("validation_status", {}),
    ]
    for what in RESULT_WHATS:
        calls.append(("get_results", {"run_id": run_id, "what": what}))
    bound = mcp_server.MAX_STRING_CHARS
    assert bound == 400
    for (name, args), payload in zip(calls, call_all(served_runs(), calls), strict=True):
        assert list(payload)[:3] == ["layers", "free_parameters", "provenance"], name
        found: list[tuple[str, str]] = []
        _walk_strings(payload, name, LONG_EXEMPT, found)
        long = [(p, len(v)) for p, v in found if len(v) > bound]
        assert not long, (name, long[:3])


@pytest.mark.slow
def test_e2e_sugar_reflex_by_tools(tmp_path: Path) -> None:
    """Run sugar-reflex by tool calls alone; units seconds/Hz, run directory.

    Mechanism claims must cite a run id.
    """
    from flyonenomics.store import ResultsStore

    assert os.environ.get("FLYONENOMICS_CACHE_DIR"), "e2e needs the engine cache env var"
    started = asyncio.run(_launch_and_kill_server(tmp_path))
    assert started["ok"] is True, started.get("errors")
    run_id = started["run_id"]
    deadline = time.monotonic() + E2E_TIMEOUT_S
    while True:
        status = call_one("run_status", {"run_id": run_id}, runs_dir=tmp_path)
        if not status["ok"] and status.get("errors") == [f"unknown run_id: {run_id}"]:
            assert time.monotonic() < deadline, "parent never published status.json"
            time.sleep(E2E_POLL_S)
            continue
        assert status["ok"] is True, status.get("errors")
        state = status["status"]["state"]
        if state == "done":
            break
        assert state in ("queued", "building", "running", "aggregating"), status["status"]
        assert time.monotonic() < deadline, f"e2e timed out in {state}"
        time.sleep(E2E_POLL_S)
    summary = call_one("get_results", {"run_id": run_id, "what": "summary"}, runs_dir=tmp_path)
    assert summary["ok"] is True and summary["summary"]["arms"]
    metrics = call_one("get_results", {"run_id": run_id, "what": "metrics"}, runs_dir=tmp_path)
    assert metrics["ok"] is True and metrics["metrics"]["paired_differences"]
    assert ResultsStore(tmp_path).validate_run(run_id) == []
    import shutil

    from flyonenomics.store.index import rebuild

    shutil.copytree(FIXTURE_RUNS / fixture_run_id(), tmp_path / fixture_run_id())
    rebuild(tmp_path)
    cmp_ = call_one("compare_runs", {"run_ids": [fixture_run_id(), run_id],
                                    "metric": "probe-0.MN9.mean_rate_hz"},
                    runs_dir=tmp_path)
    assert cmp_["ok"] is True and cmp_["paired"] is False and "seed" in cmp_["reason"]
    cancelled = call_one("cancel_run", {"run_id": run_id}, runs_dir=tmp_path)
    assert cancelled["ok"] is True


def test_identity_binding_and_layer_evidence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from flyonenomics.server import mcp_server as server
    from flyonenomics.validation import binding
    from flyonenomics.orchestrator import stubs
    from flyonenomics.types import LayerFlags
    import dataclasses
    import shutil

    (tmp_path / 'data').mkdir()
    (tmp_path / 'validation').mkdir()
    for name in ('uv.lock', 'data/provenance.json'):
        shutil.copyfile(REPO / name, tmp_path / name)
    fixture = tmp_path / 'fixture.json'
    fixture.write_text('{}')
    monkeypatch.setattr(server, 'REPO', tmp_path)
    commits = []
    monkeypatch.setattr(binding, 'repo_commit', lambda root: commits.append(root) or 'current')
    monkeypatch.setattr(stubs, 'STUB_NAMES', ())
    flags = dataclasses.asdict(LayerFlags())
    identity = binding.IdentityBlock(code_commit='current', uv_lock_hash=binding.sha256_file(tmp_path/'uv.lock'),
        provenance_hash=binding.sha256_file(tmp_path/'data/provenance.json'),
        fixture_hash=binding.sha256_file(fixture), layer_flags={**flags, 'background': False})
    entry = binding.ValidationEntry(test_id='3.5', category='verification', identity=identity, fixture_path='fixture.json')
    status = tmp_path / 'validation/status.json'
    status.write_text(json.dumps({'results': [entry.model_dump()]}))
    payload = server.validation_status()
    assert len(commits) == 1
    assert payload['entries'][0]['binding'] == 'valid'
    assert payload['layers']['background']['validation'] == 'absent'
    assert payload['layers']['dopamine_A']['validation'] == 'valid'
    stale = entry.model_copy(update={'identity': identity.model_copy(update={'code_commit': 'old'})})
    status.write_text(json.dumps({'results': [entry.model_dump(), stale.model_dump()]}))
    payload = server.validation_status()
    assert [e['binding'] for e in payload['entries']] == ['valid', 'stale']
    assert payload['layers']['dopamine_A']['validation'] == 'stale'
    status.write_text(json.dumps({'results': [entry.model_copy(update={'outcome': 'failed'}).model_dump()]}))
    assert server.validation_status()['layers']['dopamine_A']['validation'] == 'stale'
    status.write_text(json.dumps({'results': [entry.model_dump()]}))
    fixture.write_text('{"drift": true}')
    assert server.validation_status()['entries'][0]['binding'] == 'stale'
    monkeypatch.setattr(stubs, 'STUB_NAMES', ('IdentityNeuromod',))
    assert server.validation_status()['layers']['dopamine_A']['validation'] == 'absent'


def test_rebinding_uses_the_item_78_code_hash(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Entries carrying code_hash bind on the checkout's content hash, not an empty one (review p1c)."""
    from flyonenomics.server import mcp_server as server
    from flyonenomics.validation import binding
    from flyonenomics.orchestrator import stubs
    from flyonenomics.types import LayerFlags
    import dataclasses
    import shutil

    (tmp_path / 'data').mkdir()
    (tmp_path / 'validation').mkdir()
    for name in ('uv.lock', 'data/provenance.json'):
        shutil.copyfile(REPO / name, tmp_path / name)
    fixture = tmp_path / 'fixture.json'
    fixture.write_text('{}')
    monkeypatch.setattr(server, 'REPO', tmp_path)
    # A later commit with the same content: the commit differs, the hash does not.
    monkeypatch.setattr(binding, 'repo_commit', lambda root: 'later-docs-commit')
    content = {'hash': 'git:same-content'}
    calls = []
    monkeypatch.setattr(binding, 'code_content_hash', lambda root: calls.append(root) or content['hash'])
    monkeypatch.setattr(stubs, 'STUB_NAMES', ())
    flags = {**dataclasses.asdict(LayerFlags()), 'dopamine_A': True, 'transporter_C': True, 'background': False}
    identity = binding.IdentityBlock(code_commit='evaluation-commit', code_hash='git:same-content',
        run_code_hash='git:same-content', uv_lock_hash=binding.sha256_file(tmp_path/'uv.lock'),
        provenance_hash=binding.sha256_file(tmp_path/'data/provenance.json'),
        fixture_hash=binding.sha256_file(fixture), layer_flags=flags)
    neuromod = binding.ValidationEntry(test_id='3.5', category='consistency', identity=identity,
                                       fixture_path='fixture.json')
    behaviour = binding.ValidationEntry(test_id='4.1', category='consistency', outcome='failed',
                                        compatibility='matching-layers', identity=identity,
                                        fixture_path='fixture.json')
    (tmp_path / 'validation/status.json').write_text(
        json.dumps({'results': [neuromod.model_dump(mode='json'), behaviour.model_dump(mode='json')]}))
    payload = server.validation_status()
    assert [e['binding'] for e in payload['entries']] == ['valid', 'valid']
    assert len(calls) == 1
    assert server._layers(flags)['dopamine_A']['validation'] == 'valid'
    assert server._behaviour_component(flags) == 'level 4 open-loop only'
    content['hash'] = 'git:changed-src'
    entries = server._validation_entries(flags)
    assert {e['reason'] for e in entries} == {'code hash differs'}
    assert server._behaviour_component(flags) == 'unavailable'


def test_failed_behaviour_does_not_stale_neuromodulation(monkeypatch: pytest.MonkeyPatch) -> None:
    from flyonenomics.server import mcp_server as server
    from flyonenomics.orchestrator import stubs

    flags = {'background': False, 'dopamine_A': True, 'transporter_C': True,
             'dan_fast_synapses': 'retain', 'receptor_kinetics_B': False, 'learning_D': False}
    entries = [
        {'test_id': '3.5', 'class': 'canonical', 'binding': 'valid',
         'outcome': 'passed', 'identity_flags': flags},
        {'test_id': '4.1', 'class': 'matching-layers', 'binding': 'valid',
         'outcome': 'failed', 'identity_flags': flags},
    ]
    monkeypatch.setattr(server, '_validation_entries', lambda ignored=None: entries)
    monkeypatch.setattr(stubs, 'STUB_NAMES', ())
    layers = server._layers(flags)
    assert layers['dopamine_A']['validation'] == 'valid'
    assert layers['transporter_C']['validation'] == 'valid'
    assert server._behaviour_component(flags) == 'level 4 open-loop only'


def test_missing_docs_fail_soft_and_bound_errors(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from flyonenomics.server import mcp_server as server
    monkeypatch.setattr(server, 'REPO', tmp_path)
    assert server._map_leaves_out() == 'unavailable'
    examples = server.example_experiments()
    assert all(e['status'] == 'unavailable' for e in examples['examples'])
    payload = server.describe_population('x' * 1000)
    assert list(payload)[:3] == ['layers', 'free_parameters', 'provenance']
    assert len(payload['errors'][0]) <= 400
    nested = server._bounded({'errors': ['x'*1000], 'meta': {'schema': 'x'*1000}, 'schema': 'x'*1000})
    assert len(nested['errors'][0]) == len(nested['meta']['schema']) == 400
    assert len(nested['schema']) == 1000


def test_launch_queues_before_detached_spawn(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from flyonenomics.server import mcp_server as server
    from flyonenomics.orchestrator import runner
    from flyonenomics.schema import Experiment
    from flyonenomics.store import ResultsStore
    import subprocess

    experiment = Experiment.model_validate(SUGAR_DOC)
    monkeypatch.setenv('FLYONENOMICS_RUNS_DIR', str(tmp_path))
    monkeypatch.setattr(server, '_validate_dict', lambda doc: (experiment, [], {}, {}))
    original = runner.make_run_id
    issued = []
    def identifier(doc: Any) -> Any:
        issued.append(original(doc))
        return issued[-1]
    monkeypatch.setattr(runner, 'make_run_id', identifier)
    launches = []
    def spawn(argv: list[str], **kwargs: Any) -> None:
        run_id = argv[-1]
        store = ResultsStore(tmp_path)
        row = next(r for r in store.index.rows() if r['run_id'] == run_id)
        assert row['state'] == 'queued'
        assert json.loads((store.run_path(run_id)/'status.json').read_text())['state'] == 'queued'
        assert Path(argv[0]).is_absolute() and Path(argv[1]).is_absolute()
        assert argv[1] == str(REPO / 'scripts/run_experiment.py')
        assert kwargs['start_new_session'] is True
        assert kwargs['stdin'] == subprocess.DEVNULL
        assert kwargs['stderr'] == subprocess.STDOUT
        assert Path(kwargs['stdout'].name) == store.run_path(run_id)/'log.txt'
        store.index.upsert(run_id, experiment.model_dump(mode='json'), {'state': 'queued'})
        assert len([r for r in store.index.rows() if r['run_id'] == run_id]) == 1
        launches.append(argv)
    from flyonenomics.orchestrator import budget
    import shutil
    monkeypatch.setattr(server.subprocess, 'Popen', spawn)
    # Avoid replacing the git subprocess used for the envelope's identity.
    monkeypatch.setattr(server, '_provenance', lambda run_id=None: {'run_id': run_id})
    monkeypatch.setattr(server, '_code_hash', lambda: '')
    monkeypatch.setattr(budget, 'core_cap', lambda: 16)
    swap = {'mib': 1600.0}
    monkeypatch.setattr(budget, 'swap_used_mib', lambda: swap['mib'])
    monkeypatch.setattr(shutil, 'which', lambda name: '/usr/bin/caffeinate' if name == 'caffeinate' else None)
    one = server.run_experiment(SUGAR_DOC, 1)
    two = server.run_experiment(SUGAR_DOC, 4)
    twelve = server.run_experiment(SUGAR_DOC, 12)
    assert one['ok'] and two['ok'] and twelve['ok']
    assert len({one['run_id'], two['run_id'], twelve['run_id']}) == 3
    assert issued == [one['run_id'], two['run_id'], twelve['run_id']]
    assert all('--caffeinate' in argv and argv[argv.index('--workers') + 1] in ('1', '4', '12') for argv in launches)
    for workers in (0, -1, 17, True, 1.5):
        assert server.run_experiment(SUGAR_DOC, workers)['ok'] is False
    monkeypatch.setattr(budget, 'core_cap', lambda: 8)
    capped = server.run_experiment(SUGAR_DOC, 12)
    assert capped['ok'] is False and 'from 1 to 8' in capped['errors'][0]
    monkeypatch.setattr(budget, 'core_cap', lambda: 16)
    swap['mib'] = budget.SWAP_HARD_MIB + 1
    gated = server.run_experiment(SUGAR_DOC, 12)
    assert gated['ok'] is False and 'start gate' in gated['errors'][0] and 'run_id' not in gated
    swap['mib'] = 1600.0
    monkeypatch.setattr(shutil, 'which', lambda name: None)
    assert server.run_experiment(SUGAR_DOC, 1)['ok'] and '--caffeinate' not in launches[-1]
    assert len(launches) == 4
    def fail(*args: Any, **kwargs: Any) -> None:
        raise OSError('spawn failed')
    monkeypatch.setattr(server.subprocess, 'Popen', fail)
    failed = server.run_experiment(SUGAR_DOC, 1)
    assert not failed['ok']
    assert server.run_status(failed['run_id'])['status']['state'] == 'failed'


async def _launch_and_kill_server(runs_dir: Path) -> dict[str, Any]:
    """Kill the actual MCP server after its launch reply; run must survive SIGKILL."""
    from mcp.client import stdio
    from mcp import ClientSession
    from unittest.mock import patch
    import signal

    created = []
    original = stdio._create_platform_compatible_process
    async def capture(**kwargs: Any) -> Any:
        process = await original(**kwargs)
        created.append(process)
        return process
    params = stdio.StdioServerParameters(command=sys.executable,
        args=['-m', 'flyonenomics.server.mcp_server'], cwd=str(runs_dir), env=server_env(runs_dir))
    with patch.object(stdio, '_create_platform_compatible_process', capture):
        async with stdio.stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool('run_experiment', {'experiment': FULL_SUGAR_DOC, 'n_workers': 2})
                payload = result.structuredContent or json.loads(result.content[0].text)
                assert payload['ok'], payload
                process = created[0]
                process.kill()
                assert await process.wait() == -signal.SIGKILL
                return payload


@pytest.fixture
def stored_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    import shutil
    from flyonenomics.server import mcp_server as server
    root = tmp_path / 'runs'
    shutil.copytree(FIXTURE_RUNS, root)
    monkeypatch.setenv('FLYONENOMICS_RUNS_DIR', str(root))
    return server, root, root / fixture_run_id()


def test_results_containment_tables_live_and_lifecycle(stored_run: tuple[Any, Path, Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from flyonenomics.store import ResultsStore
    import pandas as pd
    server, root, directory = stored_run
    run_id = directory.name
    for what in server.RESULT_WHATS:
        payload = server.get_results(run_id, what)
        assert payload['ok'], payload
        assert payload['selected'] == {'arm': 'wild-type', 'seed': 1, 'probe': 0}
        if 'table' in payload:
            table = payload['table']
            frame = pd.read_parquet(table['path'])
            assert table['rows'] == len(frame)
            assert table['columns'] == list(frame.columns)
            assert table['preview'] == frame.head(50).to_dict('records')
            if 'tick' in frame and table['preview']:
                assert type(table['preview'][0]['tick']) is int
    for field in ('run_id', 'arm', 'seed', 'probe'):
        for value in ('..', '/tmp', '../../outside', '%2fetc', '%252fetc', 'x\\..\\y'):
            arguments = {'run_id': run_id, 'what': 'rates', field: value}
            assert server.get_results(**arguments)['ok'] is False
    outside = tmp_path / 'outside'
    outside.mkdir()
    (root / 'escape').symlink_to(outside, target_is_directory=True)
    for function in (server.run_status, server.cancel_run):
        assert function('escape')['ok'] is False
        assert function('missing')['ok'] is False
    assert not (outside/'CANCEL').exists()
    assert server.get_results('escape', 'summary')['ok'] is False
    table_path = directory/'arm-wild-type/seed-1/probe-0-rates.parquet'
    table_path.unlink()
    table_path.symlink_to(FIXTURE_RUNS/run_id/'arm-wild-type/seed-1/probe-0-rates.parquet')
    assert server.get_results(run_id, 'rates')['ok'] is False
    live_path = directory/'arm-wild-type/seed-1/live/probe-0.ndjson'
    live_path.write_text(''.join(json.dumps({'tick': n})+'\n' for n in range(25)) + '{"tick":')
    live = server.get_results(run_id, 'live')['live']
    assert live['events'] == [{'tick': n} for n in range(5, 25)]
    live_path.unlink()
    assert server.get_results(run_id, 'live')['live']['status'] == 'not_started'
    status_path = directory/'status.json'
    original = json.loads(status_path.read_text())
    for state in ('queued', 'building', 'running', 'aggregating', 'failed', 'cancelled', 'done'):
        status_path.write_text(json.dumps({**original, 'state': state, 'traceback': 'x'*1000}))
        status = server.run_status(run_id)
        assert status['status']['state'] == state
        assert status['status']['phase_index'] == original['phase_index']
        assert status['status']['estimated_remaining_s'] is None
        assert 'pid' not in status['status'] and 'worker_pids' not in status['status']
    seen = []
    cancel = ResultsStore.cancel
    def tracked(store: Any, run_id: str) -> None:
        seen.append(run_id)
        return cancel(store, run_id)
    monkeypatch.setattr(ResultsStore, 'cancel', tracked)
    assert server.cancel_run(run_id)['ok']
    assert server.cancel_run(run_id)['layers']['background']['value'] is False
    assert seen == [run_id, run_id]
    (root/'not-a-run').mkdir()
    assert server.cancel_run('not-a-run')['ok'] is False
    assert not (root/'not-a-run/CANCEL').exists()
    assert server.run_status(run_id)['status']['state'] == 'done'


def test_compare_and_index_filters(stored_run: tuple[Any, Path, Path]) -> None:
    from flyonenomics.store import ResultsStore
    import shutil
    server, root, directory = stored_run
    store = ResultsStore(root)
    metric = 'probe-0.MN9.mean_rate_hz'
    records = []
    for i, state in enumerate(('queued', 'running', 'done', 'failed', 'cancelled')):
        target = root/f'copy-{i}'
        shutil.copytree(directory, target)
        doc = json.loads((target/'experiment.json').read_text())
        doc['name'] = f'candidate-{i}'
        (target/'experiment.json').write_text(json.dumps(doc))
        store.index.upsert(target.name, doc, {'state': state, 'created': f'20260913T0{i}0000.000000Z'})
        records.append(target)
    for i, state in enumerate(('queued', 'running', 'done', 'failed', 'cancelled')):
        rows = server.list_runs({'state': state, 'name': 'candidate'})['runs']
        assert [r['run_id'] for r in rows] == [f'copy-{i}']
    assert server.list_runs({'assay': 'sugar_reflex'})['n'] == 6
    assert server.list_runs({'assay': 'buridan'})['n'] == 0
    assert server.list_runs({'created_after': '2030-01-01'})['n'] == 0
    assert server.list_runs({'name': 'candidate', 'created_after': '2026-09-13T04:00:00+02:00'})['n'] == 2
    assert server.list_runs({'created_after': 'not-a-date'})['ok'] is False
    assert server.list_runs({'name': 'candidate', 'created_after': '20260913T020000.000000Z'})['n'] == 2
    assert server.list_runs({'unknown': 'value'})['ok'] is False
    assert server.list_runs({'name': 1})['ok'] is False
    left, right, third = [r.name for r in records[:3]]
    paired = server.compare_runs([left, right], metric)
    block = next(iter(paired['paired'].values()))
    assert all(b['mean'] == 0 and b['per_seed'] == [0.0] for b in block.values())
    assert all(b['n'] == 1 and 'mean' in b and 'sd' in b for b in paired['tables'][left]['arms'].values())
    doc_path = records[1]/'experiment.json'
    original = json.loads(doc_path.read_text())
    for change, reason in (({'seed': 42}, 'different S'), ({'seeds': [99]}, 'seed lists')):
        doc_path.write_text(json.dumps({**original, **change}))
        payload = server.compare_runs([left, right], metric)
        assert payload['paired'] is False and reason in payload['reason']
        assert 'ci95' not in json.dumps(payload)
    doc_path.write_text(json.dumps(original))
    third_path = records[2]/'experiment.json'
    third_path.write_text(json.dumps({**original, 'seed': 42}))
    payload = server.compare_runs([left, right, third], metric)
    assert payload['paired'] and payload['paired_run_ids'] == [left, right]
    metrics_path = records[1]/'metrics.json'
    metrics = json.loads(metrics_path.read_text())
    metrics['arms'].pop('mn9-threshold')
    metrics_path.write_text(json.dumps(metrics))
    assert server.compare_runs([left, right], metric)['paired'] is False
    assert server.compare_runs([left, right], 'mean_rate_hz')['ok'] is False
    assert server.compare_runs([left, '../escape'], metric)['ok'] is False


def test_every_registered_tool_success_and_error_envelopes(stored_run: tuple[Any, Path, Path], monkeypatch: pytest.MonkeyPatch) -> None:
    from flyonenomics.store import ResultsStore
    server, root, directory = stored_run
    run_id = directory.name
    monkeypatch.setattr(server.subprocess, 'Popen', lambda *args, **kwargs: None)
    monkeypatch.setattr(server, '_provenance', lambda run_id=None: {'run_id': run_id})
    monkeypatch.setattr(server, '_code_hash', lambda: '')
    from flyonenomics.orchestrator import budget
    monkeypatch.setattr(budget, 'core_cap', lambda: 16)
    monkeypatch.setattr(budget, 'swap_used_mib', lambda: 0.0)
    calls = {
        'describe_lab': {}, 'list_populations': {}, 'describe_population': {'name': 'MN9'},
        'list_compartments': {}, 'resolve_population': {'spec': {'name': 'MN9'}},
        'get_schema': {}, 'example_experiments': {}, 'validate_experiment': {'experiment': SUGAR_DOC},
        'run_experiment': {'experiment': SUGAR_DOC, 'n_workers': 1},
        'run_status': {'run_id': run_id}, 'cancel_run': {'run_id': run_id},
        'get_results': {'run_id': run_id, 'what': 'summary'}, 'list_runs': {'filter': {}},
        'compare_runs': {'run_ids': [run_id, run_id], 'metric': 'probe-0.MN9.mean_rate_hz'},
        'validation_status': {},
    }
    assert list(calls) == server.tool_names()
    # Leave git probing intact without letting the spawn double intercept it.
    from flyonenomics.validation.binding import sha256_file
    monkeypatch.setattr(server, '_provenance', lambda run_id=None: {
        'run_id': run_id, 'code_commit': 'test', 'uv_lock_hash': sha256_file(REPO/'uv.lock'),
        'provenance_hash': sha256_file(REPO/'data/provenance.json'), 'data_versions': {}})
    async def check() -> None:
        for tool in server.mcp._tool_manager.list_tools():
            assert tool.description.endswith('Mechanism claims must cite a run id.')
            payload = await server.mcp._tool_manager.call_tool(tool.name, calls[tool.name])
            assert payload.get('ok', True), (tool.name, payload)
            assert list(payload)[:3] == ['layers', 'free_parameters', 'provenance']
            found = []
            _walk_strings(payload, tool.name, LONG_EXEMPT, found)
            assert all(len(value) <= 400 for _, value in found)
        # A storage/registry input error must go through the same wrapper for all 15 tools.
        def broken(*args: Any, **kwargs: Any) -> None:
            raise OSError('x' * 1000)
        with monkeypatch.context() as fault:
            fault.setattr(server, '_layers', broken)
            # The error handler itself needs an independent envelope fallback.
            for tool in server.mcp._tool_manager.list_tools():
                payload = await server.mcp._tool_manager.call_tool(tool.name, calls[tool.name])
                assert payload['ok'] is False
                assert list(payload)[:3] == ['layers', 'free_parameters', 'provenance']
                assert len(payload['errors'][0]) <= 400
    asyncio.run(check())


def test_fixture_rebuild_and_source_identity(stored_run: tuple[Any, Path, Path]) -> None:
    from flyonenomics.store import ResultsStore
    from flyonenomics.schema import Experiment
    server, root, directory = stored_run
    store = ResultsStore(root)
    before = store.index.rows()
    (root/'index.sqlite').unlink()
    rebuilt = ResultsStore(root).index.rebuild()
    assert before == rebuilt
    assert store.validate_run(directory.name) == []
    source = Experiment.model_validate(SUGAR_DOC)
    source.resolve(server._registry_cached())
    committed = Experiment.model_validate(json.loads((directory/'experiment.json').read_text()))
    assert source.canonical_json() == committed.canonical_json()
    manifest = json.loads((directory/'manifest.json').read_text())
    assert source.protocol_hash() == manifest['protocol_hash']
    assert directory.name.endswith(source.protocol_hash()[:8])
    assert (directory/'log.txt').read_bytes().splitlines() == [b'pinned drive g_inh=1, background=off'] * 2
    payload = server.get_results(directory.name, 'summary')
    assert payload['provenance']['code_commit'] == manifest['code_commit']
    assert payload['free_parameters'] == manifest['free_parameters']


def test_lab_sources_defaults_and_schema(monkeypatch: pytest.MonkeyPatch) -> None:
    from flyonenomics.server import mcp_server as server
    from flyonenomics.schema.experiment import Probe, Genotype, Drug, DEFERRED_DRUGS
    from flyonenomics.schema.named import named_manipulations
    from flyonenomics.orchestrator.runner import FREE_PARAMETER_KEYS
    from flyonenomics.types import load_params
    from typing import get_args
    monkeypatch.delenv('FLYONENOMICS_RUNS_DIR', raising=False)
    monkeypatch.delenv('FLYONENOMICS_CACHE_DIR', raising=False)
    payload = server.describe_lab()
    assert payload['directories'] == {'runs': str(REPO/'runs'), 'cache': str(REPO/'.cache')}
    assert payload['assays'] == list(get_args(Probe.model_fields['assay'].annotation))
    assert payload['drugs'] == {'supported': list(get_args(Drug)), 'deferred': sorted(DEFERRED_DRUGS)}
    assert payload['free_parameters'] == {k: load_params().get(k) for k in FREE_PARAMETER_KEYS}
    expected_genotypes = {
        name: [m.model_dump(mode='json') for m in named_manipulations(name)]
        for name in get_args(Genotype.model_fields['named'].annotation)
    }
    assert payload['named_genotypes'] == expected_genotypes
    records = json.loads((REPO/'data/provenance.json').read_text())['records']
    for name, source in payload['substrate_sources'].items():
        record = next(r for r in records if r['path'] == source['path'])
        assert source == {k: record[k] for k in ('path', 'version', 'sha256')}
    assert payload['substrate']['annotation_version'] == 'v2.1.0'
    text = (REPO/'docs/feasibility.md').read_text()
    assert payload['what_the_map_leaves_out'] == text[text.index('## 4. What the map leaves out'):text.index('## 5.')].strip()


def test_population_inventory_resolution_and_unavailable_pins() -> None:
    from flyonenomics.server import mcp_server as server
    registry = server._registry_cached()
    for name in ('MN9', 'PPL1', 'sugar_GRN_R'):
        description = server.describe_population(name)
        count, limits = registry.inventory(name)
        assert description['count'] == count
        assert description['inventory_range'] == list(limits)
    named = server.resolve_population({'name': 'sugar_GRN_R'})
    explicit = server.resolve_population({'explicit': {'roots': named['root_ids'], 'version': '783'}})
    assert explicit['root_ids'] == named['root_ids'] and explicit['idx'] == named['idx']
    query = server.resolve_population({'query': {'column': 'cell_class', 'values': ['DAN']}})
    assert query['ok'] and query['count'] == registry.population('DAN').count
    for field in ('annotation_version', 'receptor_map_version', 'params_version'):
        doc = copy.deepcopy(SUGAR_DOC)
        doc.setdefault('substrate', {})[field] = 'unavailable'
        for function in (server.validate_experiment, server.run_experiment):
            payload = function(doc)
            assert payload['ok'] is False and any(field in error for error in payload['errors'])
            assert payload['layers']['background']['value'] is False


def test_neuromod_manifest_parameters_and_drug_summary_survive_reader(stored_run):
    server, root, directory = stored_run
    path = directory / 'manifest.json'
    manifest = json.loads(path.read_text())
    manifest['free_parameters'].update({'rec.formulation': 'absolute', 'da.tonic_source': [0.00267],
                                        'receptor_map_version': 'v0.1', 'lif.g_inh': 1})
    path.write_text(json.dumps(manifest))
    metrics_path = directory / 'metrics.json'
    metrics = json.loads(metrics_path.read_text())
    metrics.update(slow_state='phase1-drug-only', calibration_limits={'phasic_release': 'placeholder alpha_max'})
    metrics_path.write_text(json.dumps(metrics))
    response = server.get_results(directory.name, 'summary')
    assert response['free_parameters'] == manifest['free_parameters']
    assert response['summary']['slow_state'] == 'phase1-drug-only'
    assert response['summary']['calibration_limits'] == metrics['calibration_limits']


def test_committed_server_fixture_is_never_opened_by_a_server() -> None:
    """The stdio server writes SQLite sidecars into its runs dir; that dir is a copy."""
    assert served_runs() != FIXTURE_RUNS and not served_runs().is_relative_to(REPO)
    assert call_one("list_runs", {"filter": {}})["ok"] is True
    assert list(served_runs().glob("index.sqlite*")), "the copy is the directory the server opened"
    assert not [p.name for p in FIXTURE_RUNS.glob("index.sqlite-*")]
