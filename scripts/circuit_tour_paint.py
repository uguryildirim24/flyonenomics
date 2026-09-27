#!/usr/bin/env python3
"""Render labelled, identifier-free condition and overview images on the MaleCNS 3D model."""
from __future__ import annotations

import base64
from html import escape
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def uri(png: bytes) -> str:
    return 'data:image/png;base64,' + base64.b64encode(png).decode('ascii')


def paint(summary: Path, out: Path) -> None:
    from playwright.sync_api import sync_playwright
    summary, out = summary.resolve(), out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    subprocess.run([sys.executable, str(ROOT/'scripts/render_malecns_3d.py'),
                    '--circuit', '--values', str(summary/'paint-values.json'), '--out', str(out)], check=True)
    labels = [(c['id'], c['label']) for c in json.loads((summary/'paint-values.json').read_text())['conditions']]
    dose = all(k.startswith(('block-', 'boost-', 'rescue-')) for k, _ in labels)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel='chrome', headless=True,
                                     args=['--use-angle=swiftshader', '--enable-unsafe-swiftshader'])
        source = browser.new_page(viewport={'width':1600, 'height':1050}, device_scale_factor=1)
        source.route('http://**/*', lambda route: route.abort())
        source.route('https://**/*', lambda route: route.abort())
        source.goto((out/'male-cns-atlas.html').as_uri())
        source.wait_for_function('window.atlasReady === true', timeout=120000)
        card = browser.new_page(viewport={'width':1560, 'height':850}, device_scale_factor=1)
        for key, label in labels:
            source.locator('#condition').select_option(key)
            circuit = not (key.startswith('off-') or dose)
            source.locator('#brain').click()
            source.evaluate('new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))')
            brain = source.locator('#viewport').screenshot()
            if circuit:
                source.locator('#cns').click()
                source.evaluate('new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))')
                cns = source.locator('#viewport').screenshot()
            else:
                cns = source.locator('#context').screenshot()
            title = escape(label.replace('_',' '))
            html = f'''<!doctype html><html><head><style>
            body{{margin:0;background:#edf3f5;color:#1a3445;font-family:system-ui,sans-serif}}
            header{{padding:24px 40px 8px}}h1{{margin:0;font-size:38px;font-weight:700;letter-spacing:-.04em}}
            p{{margin:9px 0;color:#496577;font-size:17px}}
            main{{display:grid;grid-template-columns:1fr 1fr;gap:18px;margin:16px 40px}}
            figure{{background:white;margin:0;border:1px solid #d9e3e8;border-radius:8px;overflow:hidden}}
            figure img{{width:100%;height:560px;object-fit:contain;display:block}}
            figcaption{{font-weight:600;padding:12px 18px;border-top:1px solid #edf0f2}}
            footer{{padding:5px 40px;font-size:17px;color:#344e60}}
            </style></head><body><header><h1>{title}</h1>
            <p>Change in model neuron firing · matched healthy rest ·{'receptor conductance scaling' if dose else 'injected courtship drive' if circuit else 'one chemical switched off'}</p></header>
            <main><figure><img src="{uri(brain)}"><figcaption>Brain · anterior view</figcaption></figure>
            <figure><img src="{uri(cns)}"><figcaption>{'Brain to song circuit in the nerve cord' if circuit else 'Brain and nerve cord · whole CNS'}</figcaption></figure></main>
            <footer>Red = more spikes · blue = fewer spikes · grey = little change. Model input is injected; the fly does not see.<br>
            Skeletons are anatomical representatives; colour intensity uses one shared scale for all conditions.</footer></body></html>'''
            card.set_content(html)
            card.screenshot(path=str(out/f'{key}.png'), full_page=True)
        browser.close()
        overview = pw.chromium.launch(channel='chrome', headless=True)
        page = overview.new_page(viewport={'width':2400, 'height':1100}, device_scale_factor=1)
        heading = 'GABA receptor occupancy · model firing' if dose else 'Changes in model firing · chemical blocks and courtship drive'
        html = '<html><head><style>body{background:#e8eef2;color:#152c3e;font:20px system-ui;margin:24px}h1{text-align:center}main{display:grid;grid-template-columns:repeat(3,1fr);gap:18px}figure{margin:0;background:white;padding:8px;border-radius:8px}figcaption{padding:8px;font-weight:600}img{width:100%}</style></head><body><h1>'+heading+'</h1><p>Injected input; the fly does not see. Red = more spikes; blue = fewer; one shared colour scale.</p><main>'
        for key, label in labels:
            png = uri((out/f'{key}.png').read_bytes())
            html += f'<figure><img src="{png}"><figcaption>{escape(label.replace("_"," "))}</figcaption></figure>'
        page.set_content(html+'</main></body></html>')
        page.screenshot(path=str(out/'overview.png'), full_page=True)
        overview.close()


if __name__ == '__main__':
    if len(sys.argv) != 3:
        raise SystemExit('usage: circuit_tour_paint.py <summary> <figure-output>')
    paint(Path(sys.argv[1]),Path(sys.argv[2]))
