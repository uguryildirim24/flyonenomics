# Dopamine cleanup and release reduction in the male brain model

**Completed; unreviewed first numbers:** ΔH_gen **−0.085156**, 95% interval **[−0.153954, −0.020968]**, exact p **0.03515625**, Holm p **0.0703125**—nominal only, not Holm significant. ΔΔH **+0.045877**, interval **[−0.059833, +0.158040]**, exact/Holm p **0.439453125**—**no detected difference**, not Holm significant. Neither primary survives Holm. See the [full results, affine-conditioning warning and exact audits](adhd-study-results.md).

5b-02 completed **320/320 arms and ten audited seeds**, exit 0 at **2026-09-24 04:43:34 UTC**. d-0025 exact RNG/event checks passed on the box and after transfer. The 60 old 5b-01 arms remain **void, never analysed**. Original 5a-01 and the committed −50°/+50° pair were retained: **5a used pre-d-0025 plumbing with the same input statistics**, not a retroactively passed old RNG audit. Replay 103–110 was skipped by the coordinator. No code, frozen analysis or tolerance changed during collection; no full-suite rerun. [Part A](adhd-study-part-a.md) preserves the qualification and repair history.

## Question

Does removing modelled dopamine-transporter uptake change the ER population's response to competing artificial TuBu inputs, depending on which input came first? Does reducing release change that genotype difference?

The intervention is **synthesis-inhibitor-like release reduction**, not methylphenidate and not a drug dose. With transporter uptake already zero in fumin, a transporter-only drug's null effect would be built into this model rather than discovered. The biological motivation and its limits are in [the research review](adhd-model-research.md).

## What was fixed before the experiment

The [design](adhd-study-design.md) was first committed at `892cf6f`, before neural outcomes. [Part A](adhd-study-part-a.md) documents the frozen analysis, synthetic confounds and one-arm cost probe. The coordinator authorised progression after Part A was committed at `f774c3b` and rebound to the reviewed male substrate.

- **One fixed male model:** MaleCNS v1.0, 162,517 neurons and 25,120,209 edges; adopted substrate `rest:ed9b0a469d7a6b77`. Explicit male transmitter, edge-sign, pre/post and KC arrays, never the generic worker's FlyWire defaults. Every arm restores the same verified male starting snapshot.
- **Inputs:** 156 TuBu cells, with imposed body-ID/side-based position labels. These are not measured receptive fields and the fly does not see. Single-input rate totals are matched by the encoder, and pairs retain its cap. There is no added targeted CX_DAN stimulation; the adopted background remains unchanged.
- **Readout:** all 245 ER cells directly reached by TuBu, selected from anatomy before any response. No cell is selected because it responds strongly. All-ER recurrent edges are audited separately, including cells outside this trace set.
- **Conditions:** WT vehicle, fumin vehicle, WT release reduction, fumin release reduction. Fumin sets transporter uptake to zero while preserving first-order non-transporter clearance.
- **Release factor:** `0.37499999999999994`, calculated from chemistry alone before outcomes and applied in both genotypes. At the fixed reference release rates, it returns fumin's analytical resting pool to `DA_ref`.

| Condition | Starting pool in innervated compartments (µM) |
|---|---:|
| WT vehicle | 0.0200000 |
| fumin vehicle | 0.0533333 |
| WT release reduction | 0.0074553 |
| fumin release reduction | approximately 0.0200000 |

These starting values are **encoded assumptions, not a neural rescue finding**. The model's PB mapping has no release sources and holds that pool at 0.02 µM in every condition. All other initial pools, parameters and subsequent drift are retained. A two-second settle is not a claim of equilibrium: the cost probe's EB pool moved by +0.0028112 µM during it.

## Prerequisite: can the readout distinguish the inputs?

Stage 5a uses seeds 101–110, each with off and four single positions, after a two-second blank settle. Each response lasts 20 brain-seconds. The decoder holds out entire seeds and fits its scale only on the training seeds.

The chosen pair is the **first eligible pair** in the committed order, not the most widely separated response. Each member must be represented against off, the two members distinguishable, and their off-subtracted templates independent. The raw files, all candidate margins, source-cell responses and final pair are retained. A failed prerequisite ends the experiment; it does not trigger a new threshold, cell selection or input-strength search.

**Selected pair: −50°/+50°**, the first eligible frozen-order pair from all ten original calibration seeds, committed at `e34ca13`. Original runtime seed manifests were absent after the failed old audit; explicitly labelled post-hoc selection-only receipts preserve that provenance. d-0025 retains the calibration and pair under the unchanged per-arm model law, not by relabelling the old audit as passed.

## Genotype × release experiment

Only after the pair record is committed, stage 5b uses fresh seeds 201–210. Every seed runs all four conditions and eight protocols:

`off→off`, `off→A`, `off→B`, `off→AB`, `A→off`, `A→AB`, `B→off`, `B→AB`.

Each trial has a two-second blank settle, five-second prefix, one-second blank gap and fourteen-second test. Nothing is reset between prefix, gap and test. The first two test seconds are primary; full-test and time-resolved responses are descriptive. Initial states and random streams are paired within seed, with injected-event and RNG audits in the raw manifests.

For each condition, H is the A-prefix pair-minus-off response minus the B-prefix pair-minus-off response, projected onto the independent calibration A-minus-B axis. Positive and negative signs describe this coordinate; neither is defined as healthy, impaired or behaviourally correct.

The two primary contrasts are:

1. fumin minus WT **vehicle** H;
2. the treated genotype gap minus the vehicle genotype gap.

The frozen analysis resamples whole experimental seeds and independently resamples calibration seeds/refits the axis, holding the selected pair fixed (10,000 replicates). It reports 95% bootstrap intervals and exact paired sign-randomisation p values with Holm adjustment over the two primaries. The exact test is conditional on the fitted axis and requires paired sign-exchangeability; the bootstrap additionally propagates calibration uncertainty. No equivalence bound was supplied or invented.

A cross-fitted nonnegative per-cell affine control, trained on held-seed single/off controls rather than pair/history outcomes, is an interpretation check. Mixture coefficients and residuals remain unconstrained rather than being forced into a winner score. The raw, unsubtracted responses are retained alongside H.

**Mean H in all four conditions:** WT vehicle **+0.081309**, fumin vehicle **−0.003847**, WT release reduction **+0.079897**, fumin release reduction **+0.040618**. The point-estimate gap shrinks from −0.085156 to −0.039279, but the interaction interval includes zero: no detected difference. Neither primary survives Holm. A smaller point-estimate gap is not rescue; WT can also move. The key affine residual is numerically unstable (mean −1.576518×10¹², interval [−4.675593×10¹³,+1.814819×10¹³], no detected difference), so it cannot exclude an affine explanation. Full seed ranges, all frozen secondaries and limitations are in the [results](adhd-study-results.md).

## What this can and cannot establish

- The strongest possible conclusion is a candidate history-dependent neural representation under an ADHD-relevant dopamine perturbation **in this fixed model**. It is not ADHD, attention, behaviour, a treatment recommendation or a dose.
- Seeds are stochastic repetitions of one model, not biological animals. Uniform ER receptor assignments, compartment mixing and transferred biophysical assumptions are not validated here.
- Failure to detect a difference is not equivalence or preservation of shape. H is one coordinate; the full vectors and mixture residuals matter.
- Synthetic validation recovers the known injected shift and reversal and exposes simple confounds. It is not a power or false-positive-rate guarantee. One noisy affine-only null has a nominal secondary interval excluding zero; this result was retained, not tuned away. Unidentifiable affine slopes use a reported intercept-only convention, which cannot rule out all affine explanations.
- Signed recurrent-edge inventory and firing presynaptic cells do not by themselves establish delivered inhibition or a causal competition mechanism.

## Anatomy and reproducibility

The [3D male atlas](3d-model.md) provides the anatomical context. Its included playback is explicitly **dummy data**, not this experiment's activity. Unrecorded cells must not be given invented zero firing rates to populate a viewer.

Committed input, source, plan and cost hashes are in `validation/records/p2/adhd-study-{plan,cost}.json`. The runner and frozen inference are `scripts/adhd_study.py` and `scripts/adhd_analysis.py`; descriptive tables and SVGs use `scripts/adhd_describe.py`. Part A gives the run commands and separates the original cost-run provenance from the adopted substrate. The lane report records current job locations and progress; raw files remain separate from inference records.

Qualification history is in `validation/records/p2/adhd-study-gate.json`. In particular, the adaptation helper's special 300-second deadline was removed in favour of its existing shared 2,400-second budget; the outer full-suite budget remains 5,400 seconds. This changed deadline is disclosed, not presented as a pass under the original limit. No numerical assertion, tolerance, fixture or model setting was relaxed.
