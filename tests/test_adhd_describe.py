"""Figure edge cases only; neural and inferential checks live in test_adhd_study."""
from importlib import import_module
from pathlib import Path
import xml.etree.ElementTree as ET

import numpy as np


def test_figures_handle_flat_curves_and_failed_prerequisite(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "scripts"))
    describe = import_module("adhd_describe")
    times = np.arange(220) * .1 - 7.95
    line = tmp_path / "flat.svg"
    describe.line_plot(line, "Flat & labelled", times, np.zeros((4, 220)), describe.LABELS,
                       "template units", zero=True)
    root = ET.fromstring(line.read_text())
    assert root.tag.endswith("svg")
    assert "nan" not in line.read_text() and "Flat &amp; labelled" in line.read_text()
    pair = describe.analysis.choose_pair(np.zeros((10, 5, 245)))
    heat = tmp_path / "failed.svg"
    describe.calibration_plot(heat, np.zeros((10, 5, 245)), pair)
    ET.fromstring(heat.read_text())
    assert "prerequisite failure" in heat.read_text()
