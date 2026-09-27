"""Plain-language text and colour scales for the atlas pages, stills and clips.

Presentation only: nothing here reads, changes or selects recorded values. File,
record, stage and seed codes stay in receipts; pictures get these plain labels.
"""
from __future__ import annotations

import math

MODEL = "Simulated activity in a male fly brain model. Input injected at TuBu; the fly does not see."
SIGNATURE = "Candidate neural signature, not ADHD or behaviour."
CALIBRATION = "Calibration runs, not the experiment's result."
FLASHES = ("Glow shows recorded model spiking; flash paths are illustrative. "
           "Simulated activity; input injected at TuBu; the fly does not see.")
ATTRIBUTION = ("MaleCNS v1.0 connectome · Janelia Research Campus, Google Research and University of Cambridge · "
               "Berg et al., Cell (2026) · CC BY 4.0 · geometry simplified and recoloured")
AUTHOR = "Hasan “Rolf” Yildirim"
PROJECT = "Flyonenomics"

# Okabe-Ito colours: the same condition has the same colour in every figure.
CONDITION_COLOURS = {"wt": "#0072B2", "fumin": "#D55E00"}
GENOTYPES = {"wt": ("Normal brain", "wild type"), "fumin": ("Broken dopamine cleanup", "fumin mutant")}
TREATMENTS = {"vehicle": "untreated", "release": "reduced dopamine release"}
INPUTS = {"A": "input A", "B": "input B", "AB": "A + B together", "A+B": "A + B together",
          "off": "no input", "blank": "no input"}
ANATOMY_ONLY = {"color": "#5d6b78", "opacity": 0.12}  # on the dark value stage

# The paper's anatomy figure: the atlas's two views with print-size text and no page controls.
PAPER_ANATOMY = dict(
    order=["TuBu", "ER", "CX_DAN", "MB_DAN", "KC"],
    key_title="Cell groups drawn · anatomy only, no activity is shown",
    key_heads=["Group", "Cells drawn", ""],
    notes={"TuBu": "The model's artificial input is injected into these cells.",
           "ER": "All drawn. The 245 with a direct TuBu connection are the analysed readout.",
           "KC": "A sample of up to 8 per cell type and side, for shape, not density."},
    views={"main": dict(letter="a", title="Brain, front view", note="Top of head up; the fly's left is on the right.",
                        bar_um=100),
           "context": dict(letter="b", title="Whole CNS",
                           note="Brain, neck connective and ventral nerve cord at one scale.", bar_um=200)},
    method=("Lines are simplified neuron centrelines; surfaces are simplified brain-region meshes. "
            "Every group is drawn in full except Kenyon cells."),
    attribution=ATTRIBUTION)


def signed(value: float) -> str:
    return f"{value:+g}".replace("-", "−")


def phase_label(label: str) -> str:
    """Rewrite a recorded phase label in plain words; timing is unchanged."""
    head, _, rest = label.partition(": ")
    code = rest.split(" ·")[0]
    if label.startswith("Settling"):
        return "Settling, no input"
    if label.startswith("Gap"):
        return "Pause, no input"
    if head == "TuBu input":
        return "No input" if code == "off" else "Input on"
    if head == "History":
        return "First input: " + INPUTS.get(code, code)
    if head == "Test":
        return "Test input: " + INPUTS.get(code, code)
    return label


def condition_text(entry: dict, stage: str | None) -> dict:
    phases = [dict(p, label=phase_label(p["label"])) for p in entry.get("phases", [])]
    if "condition" not in entry:
        return dict(title=entry["label"], detail="", science="", colour="#8394a2", phases=phases)
    genotype, treatment = entry["condition"].split("-")
    head, science = GENOTYPES[genotype]
    protocol = entry["protocol"]
    science = f"{science}, {TREATMENTS[treatment]}"
    if stage == "5a":
        title = "No input" if protocol == "off" else f"TuBu input pattern {signed(float(protocol))}°"
        return dict(title=title, detail=head, science=science, colour=CONDITION_COLOURS[genotype], phases=phases)
    history, test = protocol
    first = "No input first" if history in ("off", "blank") else f"Input {history} first"
    return dict(title=head, detail=f"{first}, then {INPUTS[test]}", science=science,
                colour=CONDITION_COLOURS[genotype], phases=phases)


def value_scale(series: dict, *, runs: int | None) -> dict:
    """Colour-scale labels. Whole spike counts per bin get one colour step per spike."""
    low, high, unit = series["minimum"], series["maximum"], series["unit"]
    edges = series.get("bin_edges_s")
    widths = {round(b - a, 9) for a, b in zip(edges, edges[1:])} if edges else set()
    width = widths.pop() if len(widths) == 1 else None
    counts = width and [v * width for c in series["conditions"] for row in c["values"] for v in row]
    discrete = bool(counts) and low == 0 and all(abs(c - round(c)) < 1e-9 for c in counts)
    if unit == "Hz change from control":
        return dict(title="Change from control (Hz)", low=f"{low:+g} Hz", high=f"{high:+g} Hz", levels=None,
                    ticks=[[low, f"{low:+g}"], [0, "0"], [high, f"{high:+g}"]],
                    note="Red: rate rise; blue: rate fall; grey: little change. One symmetric asinh scale across conditions and times.")
    if unit != "Hz":
        return dict(title=f"Value ({unit})", low="", high="", levels=None,
                    ticks=[[low, f"{low:g}"], [(low + high) / 2, f"{(low + high) / 2:g}"], [high, f"{high:g}"]],
                    note="Made-up display values. One fixed range for every time.")
    if discrete:
        spikes = round(high * width)
        return dict(title="Spike rate of each recorded cell (Hz)", low="silent",
                    high=f"{spikes} spikes in {width * 1000:g} ms", levels=[k / width for k in range(spikes + 1)],
                    ticks=None, note=(f"Each step is one more spike in the {width * 1000:g} ms bin. "
                                      "One fixed scale for every condition and time."))
    step = 10 ** math.floor(math.log10(high / 2)) if high > 0 else 1
    ticks = [t * step for t in range(0, int(high / step) + 1)]
    ticks = ticks[::math.ceil(len(ticks) / 4)]
    average = f"Average of {runs} simulated flies. " if runs else ""
    return dict(title="Spike rate of each recorded cell (Hz)", low="", high="",
                levels=None, ticks=[[t, f"{t:g}"] for t in ticks],
                note=average + "One fixed scale for every condition and time.")


def display_block(series: dict, mode: str, *, stage: str | None = None, runs: int | None = None,
                  fly: tuple[int, int] | None = None, pair: list[float] | None = None) -> dict:
    """mode: anatomy (dummy playback), study (5a/5b means), primary (one 5b run) or custom."""
    synthetic = series.get("kind") == "synthetic"
    conditions = {c["id"]: condition_text(c, stage) for c in series["conditions"]}
    base = dict(badge="MaleCNS v1.0 · adult male", figure_zoom=1.0, anatomy_only=ANATOMY_ONLY,
                figure_attribution=ATTRIBUTION, conditions=conditions, scale=value_scale(series, runs=runs),
                view_brain="Brain · front view", time_axis="time (s)", time_suffix="",
                aggregate=dict(title="Central-complex dopamine neurons: group total",
                               note="Summed spikes of the whole group per second, recorded as one number. "
                                    "It is never spread over the grey cells. Same scale for every condition."),
                value_honest=[], author=AUTHOR, project=PROJECT, flashes=FLASHES, model=MODEL, signature=SIGNATURE)
    explain = ("Lines are neuron centrelines, not surfaces or synapses. Ring, TuBu and both dopamine groups are "
               "shown in full; Kenyon cells are a sample by cell type and side. Brain-region surfaces are "
               "simplified; the outer outline joins the main published brain regions.")
    if mode == "anatomy":
        return dict(base, page_title="Male fly brain atlas", kicker=f"{PROJECT} · male fly brain atlas",
                    title="A male fly brain, mapped",
                    subtitle="Real MaleCNS anatomy and the five cell groups this model studies.",
                    honest=[], value_honest=[series["label"]], explain=explain,
                    conditions={c["id"]: dict(title="Demo values", detail="made-up sine waves, not a model run",
                                              science="", colour="#8394a2", phases=[]) for c in series["conditions"]},
                    method="Demo values only: made-up sine waves that show how playback works.",
                    series_label=series["label"])
    recorded = (explain + " Colour shows each recorded cell's spike rate in the current time bin; grey cells "
                "were not recorded one by one. The central-complex dopamine group total is plotted "
                "separately and never spread over cells.")
    if mode == "custom":
        delta = series["unit"] == "Hz change from control"
        return dict(base, page_title="Male fly brain · activity", kicker=f"{PROJECT} · activity playback",
                    title="Activity playback", subtitle=series["label"], honest=[series["label"]],
                    explain=(explain + " Colour shows each cell's change in firing rate versus control." if delta else recorded),
                    method=series.get("summary", ""), series_label=series["label"])
    a, b = pair or (None, None)
    patterns = (f" A and B are two injected TuBu input patterns, labelled {signed(a)}° and {signed(b)}°; "
                "they are not something the fly sees." if pair else "")
    if mode == "primary":
        number, total = fly
        who = f"Simulated fly {number} of {total}, the most typical run by the study's history measure, picked before viewing."
        block = dict(base, page_title="Male fly brain · four input histories",
                     kicker=f"{PROJECT} · experiment playback",
                     title="One simulated fly, four input histories",
                     subtitle="Normal brain versus broken dopamine cleanup, after input A or input B first. " + who,
                     honest=[MODEL, SIGNATURE], explain=recorded,
                     method="100 ms bins with no smoothing; time counts from the start of A + B input." + patterns,
                     series_label=f"Simulated fly {number} of {total}", figure_zoom=1.7,
                     view_brain="Brain · front view, central region", time_axis="time since A + B began (s)",
                     time_suffix="after A + B began", fly=who)
    else:
        runs_text = f"Average of {runs} simulated flies" if runs else "Recorded runs"
        title = "How the model answers input" if stage == "5a" else "Recorded model activity"
        honest = [MODEL, CALIBRATION] if stage == "5a" else [MODEL, SIGNATURE]
        block = dict(base, page_title="Male fly brain · " + title.lower(),
                     kicker=f"{PROJECT} · {'calibration' if stage == '5a' else 'experiment'} playback",
                     title=title, subtitle=f"{runs_text}, 100 ms bins, whole runs including settling.",
                     honest=honest, explain=recorded,
                     method=f"{runs_text}. 100 ms bins with no smoothing; time counts from the start of each run, "
                            "including 2 s of settling with no input." + patterns,
                     series_label=runs_text, figure_zoom=1.7, view_brain="Brain · front view, central region",
                     time_axis="time from run start (s)", time_suffix="from run start")
    if synthetic:
        block["honest"] = [series["label"]]
        block["title"] = "SYNTHETIC TEST DATA · " + block["title"]
    return block
