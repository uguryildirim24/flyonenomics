# Provenance errata

## Frozen source descriptions (25 September 2026)

The source descriptions below in the frozen parameter files and engine header are **not reliable provenance**. They remain byte-identical to the executed inputs: the first-study and confirmation plans bind the v0.2 parameters and engine source by SHA-256, and older records also bind v0.1. This page is included with the parameters and engine in the public export; use these corrected descriptions when reading either copy. No numerical value, simulation output or executed result changed: this erratum edits documentation only; the first study directly scales dopamine release rather than using the drug/food pharmacokinetic settings below. The engine correction describes existing snapshot code, not a change in its behaviour.

| Frozen location | Incorrect text | Correct provenance |
|---|---|---|
| `data/params-v0.2.yaml:85`; `data/params-v0.1.yaml:78` (3-IY EC50) | “placeholder; Kume 2005 fed 3-IY at milligrams per millilitre” | “Declared model placeholder; no measured adult-fly concentration–response calibration. Not inferred from Kume 2005 or the single bath concentration in Shin & Venton 2018.” |
| `data/params-v0.2.yaml:88`; `data/params-v0.1.yaml:81` (food-to-brain kappa) | “free parameter with no fly source; L2 report says brain is 10 to 100 times below food; Rolf accepted 0.01 (resolution 9), reported in every drugged summary and swept in 3.9” | “Declared food-to-brain conversion assumption; no verified fly measurement.” |
| `data/params-v0.2.yaml:94`; `data/params-v0.1.yaml:87` (MPH food-dose default) | “Qu 2024, van der Voet 2016 range 0.1 to 1.0 mM” | “Declared model dose setting, not a dose or concentration range established by Qu 2024 or van der Voet 2016.” |
| `src/flyonenomics/engine/brian_engine.py:5` (module header) | “No private Brian2 field is touched.” | “Bank switching uses the public active flag. File-backed snapshots use Brian2 internals and are tied to the pinned Brian2 version.” |

Kume 2005 does not document the claimed 3-IY feeding experiment. Shin & Venton 2018 used one 100 µM bath exposure for 20 minutes, not an EC50 measurement. Van der Voet 2016 used 1 mg/mL food (after comparing 0.5 and 1 mg/mL), not the asserted mM range; Qu 2024 chose 1.5 mg/mL food. The food-to-brain conversion has no verified fly measurement. Snapshotting uses Brian2's `_get_all_objects`, `clock._set_t_update_dt`, `Network._full_state` and `_stored_state`, so the header's blanket claim is false. For the literature assessment, see the [research review](adhd-model-research.md); for the actual outcome and scope, see the [first-study results](adhd-study-results.md).

## Historical substrate input pins

The public snapshot contains two files that differ from the inputs frozen in
`validation/records/p2/malecns-substrate-inputs.json`. The regeneration and
probe commands correctly reject them. This is not a dataset-download error.

| Input | Frozen SHA-256 | Current SHA-256 |
|---|---|---|
| `data/populations-male-cns-v1.0.yaml` | `4b67f2a4d5d54b5bb552bdd54ec350d99842d239a35d5c4cfb48f73daa3bdb63` | `4b72f418e0bc478588a04903393b2df266a3f75b2b5ae0bc75112398d6e1f656` |
| `src/flyonenomics/substrate/scales.py` | `7b8a4b350f19cd678ed60a07db0bb9ff99943588c19045747833e8f0b16dc5cb` | `0d6cb4592b0cf63787a667af376cb5b27e7b68e2a416f189adaf7d141174f4bb` |

Read-only comparison with Rolf's private source history located the frozen
population bytes at `d27d3950dce5e4f5546ba1db19e74f38bc655b96` and frozen
scale bytes at `a64245f7dfe4f9813118b990285df6407bb4717b`. These identify
matching file contents, not the complete executed experiment revisions.
The population change appends courtship selectors and the fixed random control.
The scale change permits zero class strength, where the frozen implementation
required positive strength. Those additions support later experiments. Removing
them to satisfy an earlier pin would break the current tour and block interface.

This comparison did not rerun a model or establish that every output remains
equal. The historical pins and generated runtime tables remain unchanged.
Numerical findings are unchanged. Historical replay needs the full executed source/input archive
and raw evidence. Those archives have no recorded public deposit here. Current
CPU work can load the committed runtime tables after cache provisioning, but
must record its own source identity. Updating the historical pin file to today's
hashes would falsely certify a different input revision.

## Removed duplicate assets

The public tree keeps `figures/3d/calibration-5a/male-cns-arm-00.png` instead of
its byte-identical `male-cns-atlas.png`, and
`figures/3d/experiment-5b/male-cns-wt-a.png` instead of its byte-identical
`male-cns-atlas.png`. Both historical K2r receipt names remain because existing
checks reference them. The unchanged renderer can regenerate the duplicate
PNGs. Original build receipts still identify what was generated. Their
historical hashes are not rewritten.
No unique media or dense scientific record was discarded to reduce clone size.

## Public privacy edits

The three Modal compute-cost summaries and the historical Phase 2
specification redact workspace identifiers and personal account balances.
Run charges, timings and scientific fields remain. Camber account and team
identifiers are placeholders. Private checkout names in paths are placeholders
too. These are privacy edits, not reruns.
`export-manifest.json` hashes the current public bytes. Historical source and
output hashes in experiment receipts still identify the original artifacts.
