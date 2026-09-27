#!/usr/bin/env python3
"""Plot recorded 40-seed confirmation contrasts, estimate and interval without inference."""
from __future__ import annotations

from html import escape
from pathlib import Path
import argparse

from fill_results import load_json, validate_confirmation

DEFAULT = Path(__file__).resolve().parents[1] / 'validation/records/p2/adhd-confirm-results.json'


def render(record: dict) -> str:
    validate_confirmation(record)
    primary = record['primary']
    values = primary['per_seed']
    low, high = primary['ci95']
    minimum = min(0, low, *values)
    maximum = max(0, high, *values)
    pad = max((maximum - minimum) * .12, .001)
    minimum -= pad
    maximum += pad
    y = lambda value: 535 - (value - minimum) / (maximum - minimum) * 420
    out = ['<svg xmlns="http://www.w3.org/2000/svg" width="1100" height="650" viewBox="0 0 1100 650">',
           '<rect width="1100" height="650" fill="#fffdf9"/>',
           '<g font-family="Arial,sans-serif" fill="#283443">',
           '<text x="60" y="49" font-size="24" font-weight="bold">Prospectively frozen vehicle genotype contrast</text>',
           '<text x="60" y="78" font-size="16">40 paired seeds 301–340 · fumin − wild type · template units</text>']
    out.append(f'<line x1="60" y1="{y(0):.2f}" x2="1040" y2="{y(0):.2f}" stroke="#a45f55" stroke-dasharray="6 5"/>')
    out.append(f'<text x="64" y="{y(0)-7:.2f}" font-size="14">zero</text>')
    for i, value in enumerate(values):
        x = 75 + i * 19.5
        out.append(f'<circle cx="{x:.2f}" cy="{y(value):.2f}" r="4" fill="#3b7394"/>')
    x = 930
    out.extend([f'<line x1="{x}" y1="{y(low):.2f}" x2="{x}" y2="{y(high):.2f}" stroke="#bd523d" stroke-width="5"/>',
                f'<circle cx="{x}" cy="{y(primary["mean"]):.2f}" r="7" fill="#bd523d"/>',
                '<text x="850" y="565" font-size="14">estimate and 95% interval</text>',
                '<text x="60" y="609" font-size="14">Each dot is one paired seed. Interval and estimate come from the frozen record; no tests are computed here.</text>',
                '</g></svg>'])
    return '\n'.join(out) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--record', type=Path, default=DEFAULT)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    args.out.write_text(render(load_json(args.record)))


if __name__ == '__main__':
    main()
