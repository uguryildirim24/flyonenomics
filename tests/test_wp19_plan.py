"""Section 6.3 expansion is independent of engine/configuration availability."""
import importlib.util
import json
from pathlib import Path


def bench():
    spec = importlib.util.spec_from_file_location("bench_wp19", Path(__file__).resolve().parents[1] / "scripts/bench.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_plan_counts_heterogeneous_probes_and_ignores_wait(tmp_path):
    document = json.loads((Path(__file__).resolve().parents[1] / "data/experiments/sugar-reflex.json").read_text())
    document["seeds"] = [1, 2, 3]
    for arm in document["arms"]:
        arm["protocol"][0]["duration_s"] = 5
        arm["protocol"].append({"type": "wait", "hours": 2})
    path = tmp_path / "constructed.json"
    path.write_text(json.dumps(document))
    plan = bench().plan_experiment(path)
    assert (plan["arms"], plan["seeds"], plan["probes"], plan["expanded_probes"]) == (2, 3, 4, 12)
    assert plan["brain_s"] == 60
    assert plan["per_arm"][0]["per_probe"][0]["duration_s"] == 5


def test_plan_expands_repeats(tmp_path):
    document = json.loads((Path(__file__).resolve().parents[1] / 'data/experiments/sugar-reflex.json').read_text())
    for arm in document['arms']:
        arm['protocol']=[{'type':'repeat','n':3,'spacing_hours':100,'body':arm['protocol']}]
    path=tmp_path/'repeat.json';path.write_text(json.dumps(document))
    plan=bench().plan_experiment(path)
    assert plan['expanded_probes']==24
    assert plan['brain_s']==72
