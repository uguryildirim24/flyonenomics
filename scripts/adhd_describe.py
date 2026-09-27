#!/usr/bin/env python3
"""Descriptive tables/SVGs for the frozen ADHD study; no new hypothesis tests.

Reads complete seed files only. Inference remains in adhd_analysis.py.
"""
from __future__ import annotations

import argparse
from html import escape
from pathlib import Path
from typing import Any

import numpy as np

import adhd_analysis as analysis
import adhd_study as study
from flyonenomics.io import load_npy, read_json

COLORS = ("#2463a5", "#c64838", "#42997a", "#8a55a3")
LABELS = ("WT vehicle", "fumin vehicle", "WT release reduction", "fumin release reduction")


def svg_start(title: str, subtitle: str, width: int = 1000, height: int = 470) -> list[str]:
    return [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
            '<rect width="100%" height="100%" fill="#fbfaf7"/>',
            '<style>text{font-family:Arial,sans-serif;fill:#29323b}.small{font-size:12px}</style>',
            f'<text x="35" y="34" font-size="22" font-weight="bold">{escape(title)}</text>',
            f'<text x="35" y="57" font-size="12">{escape(subtitle)}</text>']


def save_svg(path: Path, parts: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join([*parts, "</svg>"]) + "\n")


def line_plot(path: Path, title: str, times: np.ndarray, curves: np.ndarray,
              labels: tuple[str, ...], unit: str, *, zero: bool = False) -> None:
    """Curves are series × time. Display limits are not scientific bounds."""
    parts = svg_start(title, "Artificial TuBu input · MaleCNS model · descriptive seed means, not behavioural measurements")
    left, top, width, height = 90., 95., 650., 285.
    low, high = float(np.min(curves)), float(np.max(curves))
    if zero: low, high = min(low, 0), max(high, 0)
    padding = 0.08 * (high - low) if high != low else max(abs(high) * 0.08, 0.01)
    low -= padding; high += padding
    x = lambda t: left + (float(t) - times[0]) / (times[-1] - times[0]) * width
    y = lambda v: top + height - (float(v) - low) / (high - low) * height
    if times[0] <= 0 <= times[-1]:
        parts.append(f'<rect x="{x(0):.3f}" y="{top}" width="{x(2)-x(0):.3f}" height="{height}" fill="#e7ebee"/>')
        parts.append(f'<text x="{x(0)+3:.2f}" y="{top-8}" class="small">primary 0–2 s</text>')
    for value in np.linspace(low, high, 5):
        parts += [f'<path d="M {left} {y(value):.3f} h {width}" stroke="#dce0e2"/>',
                  f'<text x="{left-10}" y="{y(value)+4:.3f}" text-anchor="end" class="small">{value:.4g}</text>']
    for value in np.linspace(times[0], times[-1], 6):
        parts.append(f'<text x="{x(value):.3f}" y="{top+height+23}" text-anchor="middle" class="small">{value:.3g}</text>')
    if zero and low <= 0 <= high:
        parts.append(f'<path d="M {left} {y(0):.3f} h {width}" stroke="#78818a" stroke-dasharray="4 4"/>')
    for i, (curve, label) in enumerate(zip(curves, labels, strict=True)):
        points = " ".join(f"{x(t):.3f},{y(v):.3f}" for t, v in zip(times, curve, strict=True))
        color = COLORS[i % len(COLORS)]
        parts += [f'<polyline points="{points}" fill="none" stroke="{color}" stroke-width="2.5"/>',
                  f'<path d="M 770 {113+i*30} h 22" stroke="{color}" stroke-width="3"/>',
                  f'<text x="800" y="{117+i*30}" class="small">{escape(label)}</text>']
    parts += [f'<text x="{left}" y="{top-24}" class="small">{escape(unit)}</text>',
              '<text x="410" y="437" text-anchor="middle" font-size="14">Seconds from test onset</text>']
    save_svg(path, parts)


def contrast_plot(path: Path, result: dict[str, Any]) -> None:
    parts = svg_start("Genotype and release-reduction contrasts", "Dots: ten paired seeds · lines: frozen 95% whole-seed bootstrap intervals · Holm over two tests")
    values = [float(v) for row in result["primary"] for v in [*row["per_seed"], *row["ci95"]]]
    lo, hi = min([0., *values]), max([0., *values])
    pad = (hi-lo)*0.1 if hi != lo else 0.01
    lo -= pad; hi += pad
    xp = lambda v: 250 + (float(v)-lo)/(hi-lo)*670
    parts.append(f'<path d="M {xp(0):.3f} 100 v 255" stroke="#92999f" stroke-dasharray="5 5"/>')
    for i, row in enumerate(result["primary"]):
        y = 150 + i*145
        label = "Genotype: fumin − WT" if i == 0 else "Genotype × release reduction"
        parts.append(f'<text x="35" y="{y}" font-size="14">{escape(label)}</text>')
        for seed, v in enumerate(row["per_seed"]):
            dy = ((seed % 5) - 2) * 5
            parts.append(f'<circle cx="{xp(v):.3f}" cy="{y+dy}" r="3.5" fill="{COLORS[i]}" opacity="0.5"/>')
        a, b = row["ci95"]
        parts += [f'<path d="M {xp(a):.3f} {y+27} H {xp(b):.3f}" stroke="{COLORS[i]}" stroke-width="3"/>',
                  f'<circle cx="{xp(row["mean"]):.3f}" cy="{y+27}" r="5" fill="{COLORS[i]}"/>',
                  f'<text x="250" y="{y+55}" class="small">mean {row["mean"]:.5g}; 95% CI [{a:.5g}, {b:.5g}]; Holm p={row["p_holm"]:.5g}</text>']
    for v in np.linspace(lo, hi, 6):
        parts.append(f'<text x="{xp(v):.3f}" y="400" text-anchor="middle" class="small">{v:.4g}</text>')
    parts.append('<text x="580" y="439" text-anchor="middle" font-size="14">Independent A-minus-B template units</text>')
    save_svg(path, parts)


def calibration_plot(path: Path, rates: np.ndarray, pair: dict[str, Any]) -> None:
    mean = rates.mean(axis=0).T
    maximum = float(mean.max())
    parts = svg_start("Male ER response to the four imposed positions", "All 245 anatomy-selected cells in engine order · colour: mean firing rate (Hz) · no outcome-based cell selection", height=840)
    for j, label in enumerate(("off", "−150°", "−50°", "+50°", "+150°")):
        parts.append(f'<text x="{160+j*140}" y="98" text-anchor="middle" font-size="14">{label}</text>')
    for i, row in enumerate(mean):
        for j, value in enumerate(row):
            f = float(value / maximum) if maximum else 0
            color = f"rgb({round(243-207*f)},{round(246-147*f)},{round(247-82*f)})"
            parts.append(f'<rect x="{100+j*140}" y="{112+i*2.6:.3f}" width="125" height="2.7" fill="{color}"/>')
    selected = str(pair["pair"]) if pair["pair"] else "none: prerequisite failure"
    parts += [f'<text x="100" y="785" font-size="14">Range 0–{maximum:.4g} Hz; selected pair {escape(selected)}</text>',
              f'<text x="100" y="811" class="small">Four-way held-seed ER accuracy: {pair["decoder_four_way"]["accuracy"]:.3f}; this is imposed position coding, not attention.</text>']
    save_svg(path, parts)


def describe_5a(raw: Path, plan_path: Path, pair_path: Path, out: Path, record_path: Path) -> None:
    plan, pair = read_json(plan_path), read_json(pair_path)
    rates, hashes = study.load_rates(raw, "5a", plan_hash=study.sha(plan_path))
    if hashes != pair["raw_sha256"]:
        raise ValueError("pair record does not bind these calibration files")
    source, _ = study.load_rates(raw, "5a", field="response_tubu_hz", plan_hash=study.sha(plan_path))
    out.mkdir(parents=True, exist_ok=True)
    calibration_plot(out / "position-code.svg", rates, pair)
    record = {"stage": "5a", "substrate_id": plan["substrate_id"],
              "pair_sha256": study.sha(pair_path), "raw_sha256": hashes,
              "positions": ["off", *analysis.POSITIONS],
              "ER_spikes_per_seed_position": (rates.sum(axis=-1)*20).tolist(),
              "TuBu_spikes_per_seed_position": (source.sum(axis=-1)*20).tolist(),
              "ER_mean_hz_by_position": rates.mean(axis=(0, 2)).tolist(),
              "TuBu_mean_hz_by_position": source.mean(axis=(0, 2)).tolist(),
              "decoder_ER": pair["decoder_four_way"], "decoder_TuBu": pair["tubu_decoder_four_way"],
              "figures_sha256": {"position-code.svg": study.sha(out / "position-code.svg")},
              "reader_sha256": study.sha(Path(__file__))}
    study.dump(record_path, record)


def describe_5b(raw: Path, calibration: Path, plan_path: Path, pair_path: Path,
                result_path: Path, out: Path, record_path: Path) -> None:
    plan, pair, result = read_json(plan_path), read_json(pair_path), read_json(result_path)
    rates, hashes = study.load_rates(raw, "5b", plan_hash=study.sha(plan_path), pair_hash=study.sha(pair_path))
    cal, cal_hashes = study.load_rates(calibration, "5a", plan_hash=plan["calibration_reference"]["plan_sha256"])
    if result["raw_sha256"] != hashes or result["calibration_sha256"] != cal_hashes:
        raise ValueError("frozen inference record does not bind these raw files")
    _, axis = analysis.templates(cal, tuple(pair["pair"]))
    # These summaries add no tests, response windows, fit parameters or cell selection.
    time_h, raw_projection, pool, modulation, tubu, settle, er_active = [], [], [], [], [], [], []
    for seed in range(201, 211):
        manifest = read_json(raw / f"seed-{seed}.json")
        er_rows, tubu_rows, pool_rows, mod_rows, active_rows = [], [], [], [], []
        for row in manifest["rows"]:
            with load_npy(raw / row["file"], allow_pickle=False) as data:
                dt = float(row["chunk_s"])
                chunks = round(0.1 / dt)
                er = data["er_counts"].reshape(-1, chunks, len(plan["cells"])).sum(axis=1) / 0.1
                er_rows.append(er)
                tubu_rows.append(data["tubu_counts"].reshape(-1, chunks, len(plan["source_indices"])).sum(axis=(1, 2)))
                pool_rows.append(data["pool_um"][::chunks])
                mod_rows.append(np.stack([data[key].reshape(-1, chunks, len(plan["cells"])).mean(axis=(1, 2))
                                          for key in ("er_dv_mv", "er_gain", "er_occ1", "er_occ2")]))
                active_rows.append(int(np.sum(data["er_edge_presynaptic_counts"].sum(axis=0) > 0)))
            settle.append({"seed": seed, "condition": row["condition"], "protocol": row["protocol"],
                           "drift_um": row["settle_pool_drift_um"]})
        er = np.asarray(er_rows).reshape(4, 8, -1, len(plan["cells"]))
        time_h.append((er[:, 5] - er[:, 4] - er[:, 7] + er[:, 6]) @ axis)
        raw_projection.append(er @ axis)
        pool.append(np.asarray(pool_rows).reshape(4, 8, -1, len(plan["compartments"])))
        modulation.append(np.asarray(mod_rows).reshape(4, 8, 4, -1))
        tubu.append(np.asarray(tubu_rows).reshape(4, 8, -1))
        er_active.append(np.asarray(active_rows).reshape(4, 8))
    time_h, raw_projection = np.asarray(time_h), np.asarray(raw_projection)
    pool, modulation, tubu = np.asarray(pool), np.asarray(modulation), np.asarray(tubu)
    test_start = plan["timing"]["settle_s"] + plan["timing"]["prefix_s"] + plan["timing"]["gap_s"]
    times = (np.arange(time_h.shape[-1]) + 0.5)*0.1 - test_start
    pool_times = np.arange(pool.shape[-2])*0.1 - test_start
    window = (times >= 0) & (times < 2)
    np.testing.assert_allclose(time_h[..., window].mean(axis=-1), result["H_per_seed_condition"], rtol=1e-12, atol=1e-12)
    out.mkdir(parents=True, exist_ok=True)
    contrast_plot(out / "primary-contrasts.svg", result)
    line_plot(out / "history-time-course.svg", "History contrast over the full test", times,
              time_h.mean(axis=0), LABELS, "A-minus-B template units", zero=True)
    for condition, label in enumerate(LABELS):
        line_plot(out / f"history-seeds-{condition}.svg", f"History contrast by seed: {label}", times,
                  time_h[:, condition], tuple(f"seed {seed}" for seed in range(201, 211)),
                  "A-minus-B template units", zero=True)
        line_plot(out / f"raw-history-{condition}.svg", f"Unsubtracted ER projections: {label}", times,
                  raw_projection[:, condition].mean(axis=0)[[5, 4, 7, 6]],
                  ("A prefix, pair", "A prefix, off", "B prefix, pair", "B prefix, off"),
                  "A-minus-B template units", zero=True)
    eb = plan["compartments"].index("EB")
    line_plot(out / "eb-pool.svg", "EB dopamine: blank prefix, identical final pair", pool_times,
              pool[:, :, 3, :, eb].mean(axis=0), LABELS, "µM")
    for i, (label, unit) in enumerate((("threshold shift", "mV"), ("input gain", "dimensionless"),
                                      ("D1 occupancy", "fraction"), ("D2 occupancy", "fraction"))):
        line_plot(out / f"er-modulation-{i}.svg", f"Applied ER {label}: blank prefix, final pair", times,
                  modulation[:, :, 3, i].mean(axis=0), LABELS, unit)
    for c, name in enumerate(plan["compartments"]):
        line_plot(out / "pools" / f"{name}.svg", f"{name}: blank prefix, final pair", pool_times,
                  pool[:, :, 3, :, c].mean(axis=0), LABELS, "µM")
    signed = np.asarray(plan["er_edges"]["composed_weight_mv"])
    record = {"stage": "5b", "substrate_id": plan["substrate_id"], "raw_sha256": hashes,
              "inference_sha256": study.sha(result_path), "reader_sha256": study.sha(Path(__file__)),
              "conditions": analysis.CONDITIONS, "protocols": analysis.PROTOCOLS,
              "time_from_test_onset_s": times.tolist(), "H_per_seed_condition_time": time_h.tolist(),
              "H_full_test_per_seed_condition": time_h[..., times >= 0].mean(axis=-1).tolist(),
              "raw_projection_per_seed_condition_protocol_time": raw_projection.tolist(),
              "pool_time_from_test_onset_s": pool_times.tolist(), "compartments": plan["compartments"],
              "pool_mean_condition_protocol_time_compartment_um": pool.mean(axis=0).tolist(),
              "ER_spikes_per_seed_condition_protocol_primary": (rates.sum(axis=-1)*2).tolist(),
              "TuBu_primary_spikes_per_seed_condition_protocol": tubu[..., window].sum(axis=-1).tolist(),
              "TuBu_test_spikes_per_seed_condition_protocol": tubu[..., times >= 0].sum(axis=-1).tolist(),
              "settle_pool_drift": settle,
              "ER_edge_audit": {"positive_edges": int(np.sum(signed > 0)), "negative_edges": int(np.sum(signed < 0)),
                                "zero_edges": int(np.sum(signed == 0)),
                                "positive_weight_inventory_mv": float(signed[signed > 0].sum()),
                                "negative_weight_inventory_mv": float(signed[signed < 0].sum()),
                                "active_presynaptic_ER_per_seed_condition_protocol": np.asarray(er_active).tolist(),
                                "claim": "Signed anatomical inventory and firing sources, not delivered current or a causal inhibition test"},
              "figures_sha256": {str(p.relative_to(out)): study.sha(p) for p in sorted(out.rglob("*.svg"))}}
    study.dump(record_path, record)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("5a", "5b"))
    parser.add_argument("--raw", type=Path, required=True)
    parser.add_argument("--plan", type=Path, default=study.PLAN)
    parser.add_argument("--pair", type=Path, required=True)
    parser.add_argument("--calibration", type=Path)
    parser.add_argument("--result", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--record", type=Path, required=True)
    args = parser.parse_args()
    if args.stage == "5a":
        describe_5a(args.raw, args.plan, args.pair, args.out, args.record)
    else:
        if args.calibration is None or args.result is None:
            parser.error("5b requires --calibration and --result")
        describe_5b(args.raw, args.calibration, args.plan, args.pair, args.result, args.out, args.record)


if __name__ == "__main__":
    main()
