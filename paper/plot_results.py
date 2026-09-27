#!/usr/bin/env python3
"""Render frozen per-seed H and primary contrasts as a dependency-free SVG.

No refitting, testing or recomputing intervals: the dots, means and interval
endpoints come directly from the committed result record.
"""
from __future__ import annotations

import argparse
import hashlib
from html import escape
from pathlib import Path

from fill_results import load_json, validate_record

HERE = Path(__file__).resolve().parent
DEFAULT = HERE.parent / 'validation/records/p2/adhd-study-results.json'
RESULTS_SHA256 = '47c6fc6e9ef83b13bdacc3af1b89b96f6b3b8d6f25c0bd1dd577d42326c0657e'


def render(record: dict) -> str:
    if validate_record(record):
        raise ValueError('synthetic fixture cannot be used for the results figure')
    rows, primary = record['H_per_seed_condition'], record['primary']
    # Reject mismatched paired contrasts; never fabricate a plot from unrelated arrays.
    for i, row in enumerate(rows):
        genotype = row[1] - row[0]
        interaction = row[3] - row[2] - genotype
        if abs(primary[0]['per_seed'][i] - genotype) > 1e-10 or abs(primary[1]['per_seed'][i] - interaction) > 1e-10:
            raise ValueError('per-seed contrasts do not match condition H')
    out = ['<svg xmlns="http://www.w3.org/2000/svg" width="1100" height="680" viewBox="0 0 1100 680">',
           '<rect width="1100" height="680" fill="#fffdf9"/>',
           '<style>text{font-family:Arial,sans-serif;fill:#283443} .title{font-size:24px;font-weight:bold} .heading{font-size:18px;font-weight:bold} .small{font-size:13px} .axis{stroke:#8d99a5;stroke-width:1} .zero{stroke:#ac665d;stroke-width:1.5;stroke-dasharray:5 5}</style>']

    def line(x1, y1, x2, y2, css, width=1):
        out.append(f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" class="{css}" stroke-width="{width}"/>')

    def text(x, y, value, cls='small', anchor='start'):
        out.append(f'<text x="{x}" y="{y}" class="{cls}" text-anchor="{anchor}">{escape(str(value))}</text>')

    def dot(x, y, colour, radius=4):
        out.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{radius}" fill="{colour}"/>')

    top, bottom = 148, 515
    scale = lambda v: bottom - (v + .35) / .7 * (bottom - top)
    text(50, 42, 'History contrast in the male connectome model', 'title')
    text(50, 70, '10 paired simulation seeds 201–210  ·  H in calibration A−B template units')
    text(52, 110, 'A  Ring-neuron H by condition', 'heading')
    text(590, 110, 'B  Paired primary contrasts', 'heading')
    for v in (-.3, -.2, -.1, 0, .1, .2, .3):
        y = scale(v)
        line(95, y, 1050, y, 'zero' if v == 0 else 'axis')
        text(83, y + 5, f'{v:+.1f}' if v else '0', anchor='end')
    xvals = [140, 260, 380, 500]
    labels = ['WT vehicle', 'fumin vehicle', 'WT release', 'fumin release']
    colours = ['#3b7394', '#c26b49', '#3b7394', '#c26b49']
    for row in rows:
        for j in range(3):
            line(xvals[j], scale(row[j]), xvals[j+1], scale(row[j+1]), 'axis')
        for j, value in enumerate(row):
            dot(xvals[j], scale(value), colours[j], 3.7)
    for x, label in zip(xvals, labels):
        text(x, 540, label, anchor='middle')
    text(298, 567, 'Lines connect the same seed; ranges are not intervals.', anchor='middle')
    for j, item in enumerate(primary):
        x = 705 + j * 230
        for seed, value in enumerate(item['per_seed']):
            dot(x + (seed - 4.5) * 3.3, scale(value), '#567e97', 3.5)
        lo, hi = item['ci95']
        line(x, scale(lo), x, scale(hi), 'axis', 4)
        line(x-9, scale(lo), x+9, scale(lo), 'axis', 2)
        line(x-9, scale(hi), x+9, scale(hi), 'axis', 2)
        dot(x, scale(item['mean']), '#be523d', 6)
        label = 'fumin − WT (vehicle)' if j == 0 else 'difference in gaps'
        text(x, 540, label, anchor='middle')
        text(x, 568, f"mean {item['mean']:+.4f}  [{lo:+.4f}, {hi:+.4f}]", anchor='middle')
        text(x, 592, f"exact p={item['p_exact']:.4f}  Holm p={item['p_holm']:.4f}", anchor='middle')
    text(50, 635, 'Bars are recorded unadjusted 95% whole-seed bootstrap intervals, not simultaneous bands.')
    text(50, 658, 'Vehicle gap nominal only, not Holm significant; interaction: no detected difference. No rescue established.')
    out.append('</svg>')
    return '\n'.join(out) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if hashlib.sha256(DEFAULT.read_bytes()).hexdigest() != RESULTS_SHA256:
        raise ValueError('reviewed result record differs from the frozen findings in the plot')
    args.out.write_text(render(load_json(DEFAULT)))


if __name__ == '__main__':
    main()
