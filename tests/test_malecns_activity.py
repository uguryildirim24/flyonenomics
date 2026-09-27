"""Playback-only gates: ID joins, count binning, honest aggregates, synthetic 5b."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import sys

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from malecns_3d.activity import (  # noqa: E402
    CALIBRATION, array_sha, binned_rates, extract_study, load_values, read, save, sha,
)


def synthetic_study(folder, stage="5b", *, roots=None, cells=None):
    """Small made-up study files, including intentionally shuffled count columns."""
    folder.mkdir()
    raw = folder / "raw"
    raw.mkdir()
    params = folder / "params.yaml"
    params.write_text("engine:\n  chunk_ms: {value: 10}\n")
    if roots is None:
        roots = np.arange(101, 108, dtype=np.int64)
    if cells is None:
        cells = [dict(body_id=str(body), group=group) for body, group in zip(
            roots, ["ER", "ER", "TuBu", "TuBu", "CX_DAN", "MB_DAN", "KC"])]
    indices = {str(body): i for i, body in enumerate(roots)}
    er_ids = [c["body_id"] for c in cells if c["group"] == "ER"]
    tubu_ids = [c["body_id"] for c in cells if c["group"] == "TuBu"]
    er_idx = np.array([indices[body] for body in er_ids[::-1]])
    identity = dict(sha256={"data/params-v0.2.yaml": sha(params)}, commit="synthetic-not-a-run")
    binding = dict(connectome_version="male-cns:v1.0", engine_arrays_sha256={"roots_i64le": array_sha(roots)})
    plan = dict(synthetic=True, identity=identity, substrate_id="synthetic-not-a-substrate",
                engine_arrays_sha256=binding["engine_arrays_sha256"], male_array_binding=binding,
                cells=[dict(engine_index=indices[er_ids[0]], body_id=int(er_ids[0]))],
                source_indices=[indices[body] for body in tubu_ids[::-1]], source_body_ids=list(map(int, tubu_ids[::-1])),
                seeds={"5a": [101, 102], "5b": [201, 202]},
                timing=dict(settle_s=.1, prefix_s=.2, gap_s=.1, test_s=.2, **{"5a_s": .5}))
    plan_path = folder / "plan.json"
    save(plan_path, plan)
    pair_path = folder / "pair.json" if stage == "5b" else None
    if pair_path:
        save(pair_path, dict(plan_sha256=sha(plan_path), pair=[-50, 50]))
    protocols = [["A", "AB"], ["B", "off"]] if stage == "5b" else ["off", "-150.0", "-50.0", "50.0", "150.0"]
    for s, seed in enumerate(plan["seeds"][stage]):
        rows = []
        for a, protocol in enumerate(protocols):
            t = np.arange(60)[:, None]
            # Deliberately reverse columns relative to displayed body IDs.
            er = (t % 3 + np.arange(len(er_ids), 0, -1)[None, :] + s + a).astype(np.int32)
            tubu = (t % 2 + len(er_ids) + np.arange(len(tubu_ids), 0, -1)[None, :] + s + a).astype(np.int32)
            total = (np.arange(60) % 4 + 7 + s + a).astype(np.int64)
            path = raw / f"seed-{seed}-arm-{a:02}.npz"
            np.savez_compressed(path, er_counts=er[:, -1:], tubu_counts=tubu,
                                er_edge_presynaptic_counts=er, er_edge_presynaptic_indices=er_idx,
                                CX_DAN_counts=total)
            row = dict(condition="wt-vehicle", protocol=protocol, file=path.name, sha256=sha(path),
                       male_array_binding=binding)
            if stage == "5b":
                row["chunk_s"] = .01
            rows.append(row)
        save(raw / f"seed-{seed}.json", dict(seed=seed, stage=stage, rows=rows, synthetic=True,
             identity=identity, plan_sha256=sha(plan_path), pair_sha256=sha(pair_path) if pair_path else None,
             receipt_kind="SYNTHETIC test fixture"))
    return dict(raw=raw, plan_path=plan_path, params_path=params, roots=roots, cells=cells,
                destination=folder / "display", source="SYNTHETIC test fixture, not a neural run", pair_path=pair_path)


def test_bin_counts_are_rates_not_spike_counts_or_per_cell_aggregate():
    counts = np.arange(40, dtype=np.int32).reshape(20, 2)
    np.testing.assert_array_equal(binned_rates(counts, .01, .1), counts.reshape(2, 10, 2).sum(axis=1) / .1)
    np.testing.assert_array_equal(binned_rates(counts.sum(axis=1), .01, .1),
                                  counts.reshape(2, 10, 2).sum(axis=(1, 2)) / .1)
    for invalid in (.005, .015, .3):
        with pytest.raises(ValueError):
            binned_rates(counts, .01, invalid)
    with pytest.raises(ValueError, match="nonnegative integers"):
        binned_rates(-counts, .01, .1)


@pytest.mark.parametrize("stage", ["5a", "5b"])
def test_synthetic_raw_to_same_value_loader(tmp_path, stage):
    args = synthetic_study(tmp_path / stage, stage)
    path = extract_study(**args)
    data = read(path)
    viewer = load_values(args["cells"], data)
    assert data["kind"] == "synthetic" and data["label"].startswith("SYNTHETIC")
    assert "Artificial input injected at TuBu; the fly does not see." in data["label"]
    assert viewer["body_ids"] == ["101", "102", "103", "104"]
    assert viewer["anatomy_only_groups"] == ["CX_DAN", "MB_DAN", "KC"]
    assert viewer["aggregate_specs"][0]["label"].endswith("population total, not per-cell")
    assert viewer["aggregate_specs"][0]["unit"] == "spikes/s"
    if stage == "5b":
        assert "A = -50°" in viewer["summary"]
        assert [p["label"] for p in viewer["conditions"][0]["phases"]] == [
            "Settling · input off", "History: A", "Gap · input off", "Test: AB"]
    else:
        assert CALIBRATION in viewer["label"]
        assert len(viewer["conditions"]) == 5
    with np.load(path.parent / "per-seed.npz", allow_pickle=False) as kept:
        assert kept["rates_hz"].shape == (2, len(viewer["conditions"]), 6, 4)
        np.testing.assert_allclose(kept["bin_edges_s"], np.arange(7) * .1)
        assert "SYNTHETIC" in str(kept["label"])
        for i, condition in enumerate(viewer["conditions"]):
            np.testing.assert_array_equal(condition["values"], kept["rates_hz"][:, i].mean(axis=0))
            np.testing.assert_array_equal(condition["aggregates"]["CX_DAN"], kept["cx_dan_total_spikes_s"][:, i].mean(axis=0))
        # Direct numerical oracle from raw chunks: join 102,101 and 104,103 to IDs 101..104.
        seed = int(kept["seeds"][0])
        with np.load(args["raw"] / f"seed-{seed}-arm-00.npz") as raw:
            np.testing.assert_array_equal(kept["rates_hz"][0, 0, 0],
                np.r_[raw["er_edge_presynaptic_counts"][:10].sum(axis=0)[::-1],
                      raw["tubu_counts"][:10].sum(axis=0)[::-1]] / .1)
            assert kept["cx_dan_total_spikes_s"][0, 0, 0] == raw["CX_DAN_counts"][:10].sum() / .1
    manifest = read(path.parent / "manifest.json")
    assert manifest["source_sha256"]["plan"] == sha(args["plan_path"])
    assert all(entry["receipt_kind"] == "SYNTHETIC test fixture" for entry in manifest["seed_receipts"])
    assert manifest["outputs"]["values.json"]["sha256"] == sha(path)


def test_historical_plan_validation_results_are_not_a_synthetic_run(tmp_path):
    args = synthetic_study(tmp_path / "historical", "5a")
    plan = read(args["plan_path"])
    plan["synthetic"] = {"analysis_validation": "made-up validation results, not the recording"}
    save(args["plan_path"], plan)
    for path in args["raw"].glob("seed-*.json"):
        record = read(path)
        del record["synthetic"]
        record["plan_sha256"] = sha(args["plan_path"])
        record["identity_evidence"] = "Reconstructed identity, not a runtime receipt"
        save(path, record)
    path = extract_study(**args)
    assert read(path)["kind"] == "model"
    assert read(path)["label"] == CALIBRATION
    assert "Reconstructed" in read(path.parent / "manifest.json")["seed_receipts"][0]["identity_evidence"]


@pytest.mark.parametrize("defect", ["checksum", "missing_seed", "root_order", "chunk", "synthetic_label", "er_mapping"])
def test_raw_defects_fail_not_silently_relabel_or_fill(tmp_path, defect):
    args = synthetic_study(tmp_path / defect)
    seed_path = args["raw"] / "seed-201.json"
    record = read(seed_path)
    if defect == "checksum":
        record["rows"][0]["sha256"] = "0" * 64
    elif defect == "missing_seed":
        (args["raw"] / "seed-202.json").unlink()
    elif defect == "root_order":
        args["roots"] = args["roots"][::-1]
    elif defect == "chunk":
        record["rows"][0]["chunk_s"] = .02
    elif defect == "synthetic_label":
        record["synthetic"] = False
    elif defect == "er_mapping":
        path = args["raw"] / record["rows"][0]["file"]
        with np.load(path) as arrays:
            changed = dict(arrays)
        changed["er_edge_presynaptic_indices"] = np.array([0, 1])
        np.savez_compressed(path, **changed)
        record["rows"][0]["sha256"] = sha(path)
    save(seed_path, record)
    with pytest.raises(ValueError):
        extract_study(**args)


def test_dummy_and_partial_recordings_are_explicit(tmp_path):
    args = synthetic_study(tmp_path / "partial")
    data = read(extract_study(**args))
    shuffled = copy.deepcopy(data)
    shuffled["body_ids"] = data["body_ids"][::-1]
    for condition in shuffled["conditions"]:
        condition["values"] = np.asarray(condition["values"])[:, ::-1].tolist()
    assert load_values(args["cells"], shuffled)["conditions"] == load_values(args["cells"], data)["conditions"]
    # Absent per-cell data cannot be painted as zero or as a population mean.
    data["anatomy_only_groups"] = []
    with pytest.raises(ValueError, match="Missing per-cell"):
        load_values(args["cells"], data)
    data["anatomy_only_groups"] = ["CX_DAN", "MB_DAN", "KC", "ER"]
    with pytest.raises(ValueError, match="must not have"):
        load_values(args["cells"], data)
    dummy = dict(dataset="male-cns:v1.0", label="DUMMY DATA · synthetic", unit="arbitrary units",
                 body_ids=["101", "102"], times_s=[0, 1], values=[[.1, .2], [.3, .4]])
    result = load_values(args["cells"][:2], dummy)
    assert result["conditions"][0]["values"] == dummy["values"]
    assert result["minimum"] == .1 and result["maximum"] == .4
    dummy["values"][0][0] = float("nan")
    with pytest.raises(ValueError, match="finite"):
        load_values(args["cells"][:2], dummy)
