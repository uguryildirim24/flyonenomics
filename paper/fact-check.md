# Manuscript numerical fact check

Line references are to `paper/manuscript.tex` in this change. Rendered dopamine numbers are rounded by the manuscript's fixed-three-decimal `siunitx` formatting (with `xfp` for the two-decimal confirmation p) from the frozen result bindings; the source JSON retains full precision. A range lists every value in that phrase, not a new inference. No raw-run identifiers belong in the manuscript.

| Item | Check / provenance |
|---|---|
| Affiliation (manuscript:15; supplement:8) | Rolf reconfirmed Lasell University on 2026-09-30. |
| Title (manuscript:14; supplement:7) | Rolf chose “A whole-nervous-system model of the male fly as a pharmacology bench” on 2026-09-30. |
| Final build switch | `paper/build.py --final` writes `\\finaltrue` to `paper/build/final-mode.tex`; default writes `\\finalfalse`. Only draft status and approval sentence differ in content. |

| Manuscript line | Numbers or check | Source / scope |
|---|---|---|
| 27 | 162,517 neurons; 25,120,209 directed connections | `docs/cuda-methods.md:9`; `docs/adhd-study-results.md:12` |
| 38 | Tables S1–S5 | `paper/supplement.tex`; model and population `docs/cuda-methods.md:19-29,33-55,85-106`; selectors `paper/supplement-fact-check.md` |
| 40 | A/B positions −50°/+50°, 245 direct-TuBu ring readouts; one calibrated A−B template unit | `docs/adhd-study-results.md:12-13,19`; `docs/SPEC-P2.md` item 160 |
| 40 | ten pilot runs, forty new follow-up runs; 2 s settle, 5 s prefix, 1 s gap, 14 s test and first 2 s primary window; two primaries, one follow-up primary | `docs/adhd-study-results.md:11,14,21`; `docs/adhd-confirm-results.md:3,9-11`; `docs/SPEC-P2.md` items 156, 160 |
| 40 | Pilot partial runs voided; retained calibration failed original RNG audit, only part replayed | `docs/adhd-study-results.md:11,14`; `paper/README.md:62-66` |
| 42 | ten repeats; 2 s settle, 10 s knockout measure; courtship 5 s ON, 5 s OFF; P1 at 10/30/60 Hz, pIP10 and random at 30 Hz | `scripts/circuit_tour.py:21,26,149-151`; `docs/SPEC-P2.md` items 158–159 |
| 44 | ten paired dose runs; 2 s settle, 10 s measure; design and Hill readouts frozen before outcomes; observed-endpoint half-point defined at analysis | `docs/SPEC-P2.md` item 162; `scripts/circuit_tour.py:149,164`; `scripts/circuit_tour_dose.py` (analysis definition); review t-0194 S5 commit chronology |
| 46 | 58,655,422 spikes, four 12 s trajectories, 0.1 ms grid, one network per run; L4 8.420 s, 10 ms interface; 0.637029 and 1.268480 s/s at 10 and 1 ms interfaces | `docs/cuda-methods.md:11,79,85,100-101,119-127`; separate short timing observations, not speedup estimates |
| 46 | Independent-stream ladder, within-engine controls, interval overlap not equivalence | `docs/gaba-dose-gpu.md:11-19,121-123`; `validation/records/p2/male-cuda-dose-plan.md:9,46` |
| 53 | pilot −0.085 [−0.154, −0.021], Holm p = 0.070; interaction +0.046 [−0.060, +0.158] | `validation/records/p2/adhd-study-results.json:68,81-110`; three-decimal display from frozen six-significant-digit bindings |
| 55 | confirmation −0.001 [−0.038, +0.038], p = 0.95; not confirmed | `validation/records/p2/adhd-confirm-results.json:5-8,52-59`; two-decimal p display |
| 64 | ACh −1.436 [−1.451, −1.426]; control 1.438 Hz; removal 99.9%; GABA +12.588 [+12.563, +12.613]; glutamate +10.779 [+10.760, +10.799] Hz | `validation/records/p2/circuit-tour-analysis.json` rows off-acetylcholine, off-gaba and off-glutamate; `docs/gaba-dose-results.md:13` control; 1.436/1.438 × 100 rounded to 99.9% |
| 66 | histamine −0.001 [−0.002, +0.001]; dopamine +0.001 [−0.019, +0.025]; octopamine −0.041 [−0.060, −0.023]; serotonin +0.013 [+0.002, +0.029]; unlabelled −0.130 [−0.159, −0.100] Hz | `validation/records/p2/circuit-tour-analysis.json` rows off-histamine, off-dopamine, off-octopamine, off-serotonin, off-unclear; matched whole-repeat intervals |
| 75 | P1 +32.457 [31.928, 32.837]; pIP10 +35.940 [32.370, 38.420]; dPR1 +26.230 [23.390, 29.650]; wing motor +9.159 [8.203, 10.150] Hz; medium dPR1 P1 vs random +17.810 [15.810, 19.820]; direct pIP10 +14.410 [11.360, 17.830]; vPR6 inactive | `validation/records/p2/circuit-tour-analysis.json` courtship rows; `docs/circuit-tour-results.md:13-15` |
| 77 | low-drive route not demonstrated | `docs/p1-routes.md:3,9-16` |
| 88 | control 1.438 Hz; block 10%, 25%, 50%, 75%, 90%, 100% and respective +0.093, +0.295, +0.972, +4.591, +9.591, +12.588 Hz | `validation/records/p2/male-cuda-dose-comparison.json` `brian` dose conditions; `docs/gaba-dose-results.md:13,17` |
| 88 | six paired 95% intervals [0.075, 0.107], [0.276, 0.318], [0.917, 1.022], [4.536, 4.652], [9.407, 9.753], [12.563, 12.613] Hz | `docs/gaba-dose-results.md:17`; Brian2 dose summary committed in `validation/records/p2/male-cuda-dose-comparison.json` |
| 88 | observed full-block half-point 80.1% [79.9%, 80.3%]; fitted slope 5.05 [4.76, 5.34]; extrapolated half-point 99.9% [96.1%, 105.4%] | `validation/records/p2/male-cuda-dose-comparison.json` `brian.fits.block.outside_sensory`; `docs/gaba-dose-results.md:18` (interval extends past full block) |
| 90 | frozen prediction below 50% block, tested against observed 80.1%; frozen fitted-slope prediction above 1, tested against 5.05 [4.76, 5.34]; extra GABA 0.25, 0.50, 1.00, 2.00, decreases 0.260 [0.238, 0.281], 0.442 [0.432, 0.456], 0.611 [0.598, 0.625], 0.835 [0.823, 0.847] Hz | `docs/SPEC-P2.md` item 162 expectations 1–5; `docs/gaba-dose-results.md:18-20` |
| 90 | 75% block; GluCl 0.50, 1.00, 2.00, rescue 23.5% [20.9%, 26.0%], 45.5% [44.7%, 46.5%], 75.0% [73.7%, 76.1%]; residual +1.147 [1.103, 1.205] Hz | `docs/gaba-dose-results.md:21`; `validation/records/p2/male-cuda-dose-comparison.json` `brian` rescue |
| 92 | GPU/Brian2 block slopes 4.99 [4.65, 5.43] / 5.05 [4.76, 5.34]; observed half-points 80.12% [79.95%, 80.30%] / 80.11% [79.90%, 80.33%] | `validation/records/p2/male-cuda-dose-comparison.json`; `docs/gaba-dose-gpu.md:115` |
| 92 | GPU/Brian2 GluCl rescue 23.6% [21.8%, 25.2%] / 23.5% [20.9%, 26.0%]; 45.1% [43.8%, 46.2%] / 45.5% [44.7%, 46.5%]; 75.0% [74.0%, 75.9%] / 75.0% [73.7%, 76.1%] | `validation/records/p2/male-cuda-dose-comparison.json`; `docs/gaba-dose-gpu.md:118` |
| 92 | boost half-effects GPU φ 2.21 [1.50, 4.29], Brian2 φ 1.26 [0.96, 1.80] | `validation/records/p2/male-cuda-dose-comparison.json`; `docs/gaba-dose-gpu.md:117` |
| 99 | NeuroMechFly v2 through FlyGym and MuJoCo | `docs/courtship-body.md:18`; citation metadata in `paper/references-verified.md` |
| 103 | wing angles about 47°, 14°, 8° | `docs/courtship-body.md:14,20-35`; selected mapping, not real motor calibration |
| 119 | visual-projection 0.059 Hz, optic 0.023 Hz, central 4.795 Hz | `validation/records/p2/male-cuda-dose-comparison.json` `brian.conditions`: control = `absolute_mean` − `paired_delta[0]`, consistent across all thirteen conditions; `docs/optic-lobe-silence.md:3-9`; see `docs/cuda-methods.md:33-55` for assumptions, `src/flyonenomics/substrate/transmitters.py:37-44,82-90` for transmitter signs and omitted co-transmission |
| 122 | MaleCNS v1.0, CC BY 4.0 and portal | `docs/research/preprint-availability.md:12-28,51-61`; `paper/references-verified.md:48-66` |
| 122, 128, 131 | Availability, no competing interests, no external funding | `paper/README.md:70-87`; Rolf's declarations retained |
| 125 | Approved AI-use disclosure: Hasan “Rolf” Yildirim conceived, directed and is responsible; Claude (Anthropic), OpenAI Codex and Gemini (Google) roles; tools are not authors or independent human/experimental replication | `paper/manuscript.tex:125`; Rolf's approved wording merged from review-30; draft alone retains the approval sentence |
| 135 | Anatomy version, CC BY 4.0 | `paper/references-verified.md:48-66` |
| 139 | ±200 and ±10 Hz illustration colour caps | `docs/tour-figures.md:29-36`; saturated figure display is not a numerical test |
| 150–165 | Citation years, journals, pages and identifiers | `paper/references-verified.md`; Zhang PubMed 7476913, Wang-Chen/FlyGym and MuJoCo verified via Crossref on 2026-09-30 |

## Figure labels

- Anatomy (manuscript:134–135): scale bars 100 µm and 200 µm, 156 TuBu, 282 ring (245 analysed), 27 central-complex dopamine, 332 mushroom-body dopamine and 155 of 4,064 Kenyon cells, with up-to-8-per-type sampling, from `docs/3d-model.md:118-128`. No physiological measurement overlay.
- Knockout and courtship (manuscript:138–143): ticks ±200 and ±10 Hz and 100 µm scale from `docs/tour-figures.md:15-16,21-41`; visual colour cap `:29-36`, scale geometry `docs/3d-model.md:106-110`.
- Fig. 4 (manuscript:146–147): plotted paired intervals from the local recorded `dose-summary/analysis.json` and the same Brian2 rows committed in `validation/records/p2/male-cuda-dose-comparison.json`. Axes give Hz and conductance units; tick positions are display positions, not additional experimental outcomes. No concentration translation is used.

The dose input at manuscript:44,84 is dark-rest sensory background only, with no TuBu stimulus (`scripts/circuit_tour.py:140-172`). SPEC-P2 item 162's frozen contradictory parenthetical is corrected by the dated note at `docs/SPEC-P2.md:2095`. The body paragraph uses courtship playback only, not the separate GABA body clip.
