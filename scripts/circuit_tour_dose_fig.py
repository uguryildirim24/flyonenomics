#!/usr/bin/env python3
"""Simple static concentration-response figure from the recorded paired intervals."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from xml.sax.saxutils import escape

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--data', type=Path, default=ROOT/'camber-runs/circuit-tour/dose-summary/analysis.json')
parser.add_argument('--overlay', type=Path, help='CUDA analysis with its own matched controls')
parser.add_argument('--out', type=Path, default=ROOT/'figures/3d/gaba-dose/curves.svg')
args=parser.parse_args()
data=json.loads(args.data.read_text())
overlay=json.loads(args.overlay.read_text()) if args.overlay else None
parts=['<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="590" viewBox="0 0 1280 590">',
       '<rect width="1280" height="590" fill="#f4f8fa"/>',
       '<style>text{font-family:system-ui,sans-serif;fill:#193548} .title{font-size:27px;font-weight:700} .axis{font-size:17px} .tick{font-size:15px} .hint{font-size:14px;fill:#526d7a}</style>',
       '<text x="56" y="52" class="title">GABA receptor scaling changes model brain activity</text>',
       '<text x="56" y="80" class="hint">Outside sensory neurons · rate difference from matched rest · brackets show 95% whole-seed intervals</text>']

def panel(left, title, prefix, values, xmax, ymin, ymax, color, xlabel):
    top,bottom=135,465
    x0,x1=left+75,left+535
    def px(x):return x0+x/xmax*(x1-x0)
    def py(y):return bottom-(y-ymin)/(ymax-ymin)*(bottom-top)
    parts.append(f'<text x="{left+22}" y="120" class="axis">{escape(title)}</text>')
    parts.append(f'<path d="M{x0} {top} V{bottom} H{x1}" stroke="#516b79" stroke-width="2" fill="none"/>')
    for i in range(5):
        v=ymin+(ymax-ymin)*i/4; yy=py(v)
        parts.append(f'<line x1="{x0}" y1="{yy}" x2="{x1}" y2="{yy}" stroke="#dce6eb"/>')
        parts.append(f'<text x="{x0-8}" y="{yy+5}" text-anchor="end" class="tick">{v:g}</text>')
    for i in range(5):
        v=xmax*i/4; xx=px(v)
        parts.append(f'<text x="{xx}" y="{bottom+23}" text-anchor="middle" class="tick">{v:g}</text>')
    datasets=[(data,color,False)] if overlay is None else [(data,'#b6464a',False),(overlay,'#2878a3',True)]
    for dataset,stroke,dashed in datasets:
        xy=[]
        for v in values:
            a,lo,hi=dataset['conditions'][f'{prefix}-{v}']['paired_delta']['outside_sensory'];xx=px(float(v));yy=py(a)
            xy.append((xx,yy))
            parts.append(f'<line x1="{xx}" x2="{xx}" y1="{py(lo)}" y2="{py(hi)}" stroke="{stroke}" stroke-width="3"/>')
            for e in (lo,hi):parts.append(f'<line x1="{xx-6}" x2="{xx+6}" y1="{py(e)}" y2="{py(e)}" stroke="{stroke}" stroke-width="2"/>')
        points=' '.join(f'{x},{y}' for x,y in [(px(0),py(0)),*xy])
        dash=' stroke-dasharray="8 5"' if dashed else ''
        parts.append(f'<polyline points="{points}" fill="none" stroke="{stroke}" stroke-width="3"{dash}/>')
        for x,y in xy:
            if dashed:
                parts.append(f'<rect x="{x-4}" y="{y-4}" width="8" height="8" fill="{stroke}"/>')
            else:
                parts.append(f'<circle cx="{x}" cy="{y}" r="5" fill="{stroke}"/>')
    parts.append(f'<text x="{(x0+x1)/2}" y="{bottom+62}" text-anchor="middle" class="axis">{escape(xlabel)}</text>')

panel(15,'GABA blocked','block',('0.10','0.25','0.50','0.75','0.90','1.00'),1.,0,14,'#b6464a','Fraction of GABA receptors blocked')
panel(655,'GABA strengthened','boost',('0.25','0.50','1.00','2.00'),2.,-1,0.1,'#2878a3','Extra GABA conductance (φ)')
if overlay is not None:
    parts.append('<text x="56" y="561" class="hint">Red circles: Brian2 · blue squares, dashed: GPU · ΔHz from each engine’s control · injected input; the fly does not see.</text>')
else:
    parts.append('<text x="56" y="561" class="hint">Block concentration: picrotoxin brain-equivalent on recombinant Rdl homomers; potentiation has no calibrated drug concentration.</text>')
parts.append('</svg>')
path=args.out
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text('\n'.join(parts)+'\n')
print(path)
