#!/usr/bin/env python3
"""Descriptive SVGs from an already audited, frozen confirmation result; no inference."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def frame(title: str, subtitle: str) -> list[str]:
    return ['<svg xmlns="http://www.w3.org/2000/svg" width="960" height="470" viewBox="0 0 960 470">',
            '<rect width="960" height="470" fill="#fcfaf6"/>',
            '<style>text{font-family:Arial,sans-serif;fill:#273542}.small{font-size:12px}</style>',
            f'<text x="55" y="40" font-size="22" font-weight="bold">{title}</text>',
            f'<text x="55" y="62" class="small">{subtitle}</text>']


def save(path: Path, drawing: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('\n'.join([*drawing, '</svg>']) + '\n')


def per_seed(result: dict, path: Path) -> None:
    primary = result['primary']
    values = primary['per_seed']
    if len(values) != 40:
        raise ValueError('complete 40-seed result required')
    lo, hi = min(0, *values, *primary['ci95']), max(0, *values, *primary['ci95'])
    pad = max((hi - lo) * .1, .01)
    lo, hi = lo - pad, hi + pad
    x = lambda i: 85 + 815 * i / 39
    y = lambda v: 390 - 280 * (v - lo) / (hi - lo)
    drawing = frame('Confirmatory genotype difference by seed',
                    'Fumin minus wild type · first 2 test seconds · 40 paired stochastic seeds · descriptive points')
    for v in (lo, 0, hi):
        drawing += [f'<line x1="85" x2="900" y1="{y(v):.2f}" y2="{y(v):.2f}" stroke="#a9b2b9" stroke-dasharray="4 4"/>',
                    f'<text x="79" y="{y(v)+4:.2f}" text-anchor="end" class="small">{v:.3f}</text>']
    for i in range(0, 40, 5):
        drawing.append(f'<text x="{x(i):.2f}" y="412" text-anchor="middle" class="small">{301+i}</text>')
    for i, v in enumerate(values):
        drawing.append(f'<circle cx="{x(i):.2f}" cy="{y(v):.2f}" r="4" fill="#27658e"/>')
    a, b = primary['ci95']
    drawing += [f'<line x1="85" x2="900" y1="{y(primary["mean"]):.2f}" y2="{y(primary["mean"]):.2f}" stroke="#b34538" stroke-width="2"/>',
                f'<text x="95" y="94" class="small">Mean {primary["mean"]:+.5f}; 95% whole-seed interval [{a:+.5f}, {b:+.5f}]</text>',
                '<text x="490" y="446" text-anchor="middle" class="small">Seed ID · model replicates, not flies</text>']
    save(path, drawing)


def time_course(result: dict, path: Path) -> None:
    series = result['secondaries']['time_course_100ms_H_per_seed']
    if len(series) != 40 or any(len(s) != 2 or any(len(v) != 140 for v in s) for s in series):
        raise ValueError('full 100 ms course required')
    mean = [[sum(seed[c][i] for seed in series) / 40 for i in range(140)] for c in (0, 1)]
    lo, hi = min(0, *mean[0], *mean[1]), max(0, *mean[0], *mean[1])
    pad = max((hi - lo) * .1, .05)
    lo, hi = lo - pad, hi + pad
    x = lambda i: 90 + 805 * i / 139
    y = lambda v: 385 - 275 * (v - lo) / (hi - lo)
    drawing = frame('History signal across the full test',
                    '100 ms bins · average of 40 complete seeds · both vehicle genotypes · descriptive, no binwise tests')
    drawing.append(f'<rect x="90" y="110" width="{x(19.5)-90:.2f}" height="275" fill="#e5e9ec"/>')
    drawing.append('<text x="95" y="101" class="small">Primary [0, 2) s</text>')
    for value in (lo, 0, hi):
        drawing += [f'<line x1="90" x2="895" y1="{y(value):.2f}" y2="{y(value):.2f}" stroke="#c7cfd3" stroke-dasharray="4 4"/>',
                    f'<text x="84" y="{y(value)+4:.2f}" text-anchor="end" class="small">{value:.2f}</text>']
    for second in (0, 2, 4, 6, 8, 10, 12, 14):
        xx = 90 + 805 * second / 14
        drawing.append(f'<text x="{xx:.2f}" y="411" text-anchor="middle" class="small">{second}</text>')
    for c, (label, color) in enumerate((('Wild type', '#27658e'), ('Fumin', '#b34538'))):
        points = ' '.join(f'{x(i):.2f},{y(v):.2f}' for i, v in enumerate(mean[c]))
        drawing += [f'<polyline points="{points}" fill="none" stroke="{color}" stroke-width="2"/>',
                    f'<line x1="{660+c*116}" x2="{675+c*116}" y1="83" y2="83" stroke="{color}" stroke-width="3"/>',
                    f'<text x="{679+c*116}" y="87" class="small">{label}</text>']
    drawing.append('<text x="490" y="446" text-anchor="middle" class="small">Seconds since test onset · projected history H (template units)</text>')
    save(path, drawing)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--result', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    result = json.loads(args.result.read_text())
    per_seed(result, args.out / 'per-seed.svg')
    time_course(result, args.out / 'time-course.svg')


if __name__ == '__main__':
    main()
