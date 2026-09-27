# flyonenomics Phase 2 build specification

Final, 2026-09-14, by p2author. Revised through `tasks/p2/turns/review-1.md` to `review-3.md` in the P2 spec round (`tasks/p2/protocol.md`), and signed off by p2critic in `review-4.md` at f36b4f1. Every finding's disposition is in `tasks/p2/decisions.md`. Revised for WP24 (tier 3 structural rest mechanisms) on `spec/wp24` in the WP24 spec round (`tasks/WP24-spec.md`, turns under `tasks/wp24/turns/`), after Rolf authorised tier 3 on 2026-09-16.

Sources for the WP24 revision: lane w17's `.reports/WP17-report.md`, `.reports/camber-ledger.md`, `docs/resting-candidates.md` and `validation/records/p2/rest-reflex-path.json` on `lane/w17` at dac30d4 (cited below as "WP17 report" and "the ledger"); `docs/resting-map.md`; `src/flyonenomics/engine/brian_engine.py` at dbe0597; a Brian2 2.10.1 feasibility check of the three variant equation sets (section 2.2.4).

Sources: `docs/brief.md`; `docs/SPEC.md` (Phase 1, revision S3, section 11 items 1 to 74); `docs/phase1-results.md`; `docs/visual-path-diagnostic.md`; `docs/calibration.md`; `docs/bench.md`; `docs/feasibility.md`; `docs/research/`; code reviews r5, r8, r9 and r11; the WP11 report through cf1a6d4; the WP13 report and code at 58a99ec; the lane briefs `tasks/camber-map.md`, `tasks/camber-proof.md`, `tasks/WP12.md` and `tasks/WP13.md`; `src/flyonenomics/drive/k1b_study.py`. The Camber resting-state map report had not landed when this draft was written, so every decision that depends on it is written as a rule with a fallback (section 2.6).

Goal. Rolf, 2026-09-12: "turn it into a virtual brain I can actually experiment on … simulate ADHD-relevant attention problems: change dopamine signaling, receptor activity, or particular circuits, see whether impaired attention emerges, and then test interventions". Rolf, 2026-09-14: Phase 2 pursues the resting substrate, not an encoder move (items 65 and 68 confirmed), and has to go fast. Phase 1 built the instrument, but the brain it runs on is silent at rest. Nothing that dopamine does to thresholds and gains reaches a spike, and the visual relay needs a baseline the substrate lacks. Phase 2 gives the brain a resting state, then redoes the visual path, the closed loop and the pharmacology on it.

Relation to Phase 1. `docs/SPEC.md` stays normative for everything this document does not change. "SPEC section 3.4" points there, "section 2.4" without a prefix points here, and "item N" is SPEC section 11 item N. For a Phase 2 run (schema 1.3 with `background: true`), this document wins where the two disagree. A Phase 1 file keeps its Phase 1 meaning bit for bit. Phase 1's conventions carry over: brain time, wall time, index, population, compartment, engine and recording ticks, the category words (verification, consistency, calibration, empirical validation, prediction), and the configuration classes. Python module paths such as `drive/rest.py` or `validation/binding.py` are relative to `src/flyonenomics/`, except files under `scripts/` and `tests/`. Every other path, including `validation/status.json` and `validation/records/`, is relative to the repository root.

Added terms:

- Bare substrate: keeps its Phase 1 meaning (`lif.g_inh` 1, `background: false`).
- Rest substrate: the v783 network with a `data/drive-v0.2.yaml` configuration in force (transmitter rule, inhibitory scales, background drive, any tier-2 settings and any tier-3 mechanism of section 2.2).
- Mechanism: one of the tier-3 changes to the neuron or synapse model (section 2.2.4), set by a block of the drive file's `mechanisms` section and off when that block is null or absent.
- Engine model: the key of the model variant an engine was built with, `lif` for the Phase 1 model (section 2.2.4).
- Candidate: one point of the section 2.2 search space.
- Configuration file: a numeric input under `data/` whose identity is its bytes (section 2.5).
- Evidence: what is measured about configuration files, held in `validation/status.json`, `validation/records/` and results documents under `docs/`. Evidence is never an input to an entry or a run.
- `q_plan`: 27 wall s per brain s per engine, the warm bare B1 figure of 18 times a 1.5 allowance for the busier substrate. It plans work until measured values replace it (section 6.4).
- Engine-hour: `q_plan` × brain s / 3600, so one brain second costs 0.0075 engine-hours.

## 1. Scope and acceptance

### 1.1 What Phase 2 delivers

- A rest substrate: a network that fires sparsely, asynchronously and stably without stimulation and keeps a stated minimum of the sugar reflex, configured in `data/drive-v0.2.yaml`. Section 2 gives the search space, criterion, calibration chain, freeze protocol and decision rule.
- A dopamine configuration `data/dopamine-v0.2.yaml` calibrated on that substrate. Where DANs fire, measured phasic DAN input holds dopamine at its reference level, and a bounded tonic source fills the rest.
- A photoreceptor visual encoder with histamine-signed photoreceptor output, `data/visual-v0.2.yaml`, and a verified propagation record from R1-6 to the steering descending neurons (section 3).
- Closed-loop Buridan steering on the rest substrate: bias, sign check, K3r, 4.1r and 4.2r, `data/behaviour-v0.2.yaml`, and one holdout comparison after integration (section 3.8).
- An ADHD manipulation set. It covers dopamine synthesis and release, transporter, receptor and circuit manipulations, each with vehicle and intervention arms and behavioural and neural readouts. Every contrast is reported as a prediction with a status word (section 4).
- Validation deltas: re-run entries with an `r` suffix, new entries, per-entry input binding with a dependency log, and platform and substrate fields (section 5).
- A compute plan: scheduled sweeps on Camber `large` nodes and a shared slot budget for local runs (section 6). The live view gets a corrected count contract and small additions (section 7).

### 1.2 What Phase 2 does not deliver

These go to Phase 3 unless Rolf pulls them forward (open question 1):

- layer B (receptor kinetics and chronic adaptation), so the slow state between probes stays drug pharmacokinetics only;
- layer D (learning);
- an atlas-derived receptor map;
- a field-potential proxy and the competing-flicker assay;
- forward-speed coupling: walking speed stays constant, so hyperactivity is not a readout;
- a body, a nerve cord, or an image-based eye (the encoder is one-dimensional in azimuth);
- octopamine, serotonin, glia and gap junctions;
- a custom engine or Brian2CUDA;
- a physical arena.

Structural mechanisms for rest are tier 3 of section 2.2 (WP24), authorised by Rolf on 2026-09-16 at section 2.6 step 5: spike-frequency adaptation (3a), short-term synaptic depression (3b) and conductance-based inhibition (3c). Each is a configuration switch, off by default, tried one at a time. Combinations of mechanisms, per-population mechanism constants and other model changes stay out (open questions 32 and 33).

### 1.3 What carries over unchanged

The bare substrate stays the canonical reproduction baseline. Its entries stay in `validation/status.json` under `substrate_id: bare` and are never relabelled: 0.3, 1.0 to 1.3, `1.4-bare`, `2.2-bare`, 3.1, 3.1b, 3.2 to 3.5, and 3.7.

The qualified neuromodulation half carries over:

- `data/dopamine-v0.1.yaml`: R_c 0 in all 37 compartments, `alpha_c` equal to `alpha_max`, `da.tonic_source` 0.00266667 µM/s;
- the transporter, drug and pharmacokinetic models and their equations;
- `receptors-v0.1.yaml` and `compartments-v0.1.yaml`;
- the Phase 1 dose-series numbers.

Phase 2 re-qualifies layers A and C on the rest substrate (section 2.5) and does not change their equations.

These files stay byte-identical: `params-v0.1.yaml`, `populations-v0.1.yaml`, `compartments-v0.1.yaml`, `receptors-v0.1.yaml`, `drive-dev.yaml`, `dopamine-v0.1.yaml`, `behaviour-v0.1.yaml` (the section 9.1 fallback, `qualified: false`), and the sealed 4.3 holdout half in `data/brembs-split.json`. New values go into new `-v0.2` files. Test 0.12 checks each frozen file against its SHA-256 at the pre-closure baseline commit 835da84.

### 1.4 Phase 1 closure prerequisite

Acceptance evaluation for Phase 2 (WP22) requires the first line of `docs/phase1-results.md` to state that the Phase 1 partial-delivery predicate holds at a named commit. Item 70's second acceptance pair produces that statement after WP12 and review r12, run under `caffeinate -ims` with real and awake wall time recorded (item 71). WP14 to WP21 and WP23 do not wait for it. WP22 checks that the section 1.3 files at the closure commit still have their 835da84 SHA-256s. If the closure pair fails or a file differs, WP22 stops and Rolf decides.

### 1.5 Acceptance and outcomes

Input. Rolf types, in Claude Code with the tool server attached: "on the resting fly brain, compare wild-type and fumin flies on Buridan fixation with a flashing distractor: give each 0.5 mM methylphenidate or vehicle, wait two hours, then test again". Claude Code writes `data/experiments/p2/acceptance-p2.json`, or an equivalent that validates against schema 1.3:

- Arms: `wt-vehicle`, `wt-mph`, `fumin-vehicle` and `fumin-mph`, identical in every resolved field except genotype and drug.
- Seeds: 1 to 10, shared by all arms.
- Phases: the SPEC section 6.3 list, namely a 20 s Buridan baseline probe with the distractor, the dose, a two-hour wait, and a 20 s Buridan test probe with the distractor.
- Configuration: `background: true`, layers A and C on, `inject_at: "photoreceptors"`, `initial_heading: "random"`.
- Pins: `drive-v0.2`, `dopamine-v0.2`, `visual-v0.2`, `behaviour-v0.2`, `params-v0.2`, `populations-v0.2` and `transmitters-v0.2`.
- Recording: the `record` block keeps the SPEC section 6.3 populations and adds rates for the stage populations of section 3.3, plus `DA_exposed`, PAM, PPL1, KC, MBON and dFB.

Claude Code then calls `run_experiment` on available project compute.

Outputs. Everything SPEC section 1.3 lists, for four arms, plus:

- the substrate identity (`substrate_id` and the blob id of every configuration file);
- the steering bias used in omega;
- per-probe settle flags, which mean convergence of the resolved population set of section 2.4, shown with the unresolved populations and the per-compartment dopamine fixed-point gaps;
- recorded stage-population rates;
- a contrast table (clause 7).

Main acceptance predicate P2. Every clause is required.

1. The run completes without intervention. Its awake wall time is within the section 6.4 budget computed from benchmark B2-P2, and real and awake wall times agree within 1 percent (item 71).
2. Every output listed above exists, and `validate_run` reports no missing field.
3. Every entry the manifest quotes is valid for this run under section 5.1, and none is stale. The section 5.2 component map holds for visual status "photoreceptor closed loop", with 3.10r and 4.3r passed. Every probe is settled under section 2.4.
4. The two-hour wait advances the pharmacokinetic state analytically in under 1 s of wall time, and the manifest records the slow-state approximation.
5. Two conditions hold.
   - (a) Transporter action: in the wild-type arms, the paired drug-minus-vehicle difference in mean compartment dopamine over the test probe, averaged over innervated compartments, has a bootstrap 95 percent interval above zero. The methylphenidate brain concentration at the start of the test probe is positive and recorded.
   - (b) Neural coupling: the paired fumin-minus-wild-type difference, vehicle arms, in mean `DA_exposed` rate (section 4.2) over the test probe has a bootstrap 95 percent interval that excludes zero.
6. A second execution of the same file with the same seeds in the pinned environment reproduces every recording tick and every metric bit for bit.
7. The contrast table reports four headline contrasts on fixation index, stripe deviation, distractor switch rate and fixation retention over the test probe. Each has a paired bootstrap 95 percent interval. The first three also carry their section 4.6 status word; the interaction carries only its interval. The contrasts are:
   - genotype: fumin minus wild type, vehicle arms;
   - drug in wild type;
   - drug in fumin;
   - interaction: the drug effect in fumin minus the drug effect in wild type.

   The clause requires computation and reporting, not an outcome.

Outcomes. Phase 2 ends in exactly one of the outcomes below, chosen by rule. The first line of `docs/phase2-results.md`, the run summary and the dashboard state the outcome, the commit, and the status tuple (substrate, visual status, coupling, holdout). Coupling is "passed" or "failed" by 3.10r. Holdout is "passed", "failed", "not run" or "spent-invalidated" (section 3.8).

- P2-partial-B, "no rest substrate". It holds when section 2.6 step 6 ends with tier 3d empty, or when Rolf stops tier 3. No acceptance file runs. `docs/transmitter-census.md` and `docs/resting-candidates.md` exist, the latter with every evaluated candidate's and tier-3 unit's criterion values, closest-miss score, failed step and the escalation record. The bare substrate stays canonical.
- With a qualified rest substrate (Q-rest passed), the section 3.7 chain sets the visual status, which selects the acceptance file:
  - "photoreceptor closed loop": `acceptance-p2.json`;
  - "TuBu closed loop": `acceptance-p2-tubu.json`, identical except for `inject_at: "TuBu"` and the TuBu settings of `visual-v0.2.yaml`;
  - "open loop": `acceptance-p2-openloop.json`, with the same arms, seeds and phases, each Buridan probe replaced by the section 3.6 open-loop probe under the encoder the visual configuration names.

  For the selected file, clauses 1, 2, 4, 5(a) and 6 are required, and clause 3 is required with the section 5.2 rows for that visual status. Clauses 5(b) and 7 are always computed. For the open-loop file, clause 7 uses `steer_gain`, `distractor_capture_hz` and the `DA_exposed` rate.
  - P2 holds when the visual status is "photoreceptor closed loop", coupling and holdout are "passed", and clauses 1 to 7 hold.
  - P2-delivered holds when every clause required for the selected file holds but P2 does not. The first line names the tuple, for example "P2-delivered (visual: TuBu closed loop; coupling: passed; holdout: failed)".
  - P2-not-delivered holds when a required clause fails for the selected file. The first line names the failing clause. WP22 records it and stops.

## 2. The rest substrate

### 2.1 Starting point

The bare substrate is silent at rest. With uniform background drive, Phase 1 found only silent or ignited states at ratio 1, and changing input variance did not help there (item 24). A global inhibitory ratio of 4 met the screening criterion at 1.148 and 1.268 mV (item 35), and a settled 10 s seed-0 window at 1.1485 mV gave Fano 2.59. The same ratio missed five placeholder targets in K1-dev: DAN 0.77 Hz, KC 1.45 Hz, central 4.94 Hz, motor 1.61 Hz, visual_centrifugal 2.44 Hz. It also abolished the reflex: background-off MN9 went from 86/53 Hz at ratio 1 to 0/0 Hz in upstream/extended mode, and to 3/8 Hz with background on and synchrony tripped (item 47).

The WP10 diagnostic found two problems in the visual relay (item 68):

- The photoreceptor-to-lamina and lamina-to-medulla stages are sign-inverting, and the relay needs a tonic baseline the silent substrate lacks.
- The transmitter predictor has no histamine class, so photoreceptors are mostly treated as cholinergic.

Phase 2 changes five things:

1. Transmitter classes come from curated annotations first, with a histamine class for photoreceptors.
2. GABA and glutamate get separate inhibitory scales (item 45).
3. The background weight is searched jointly with the scales.
4. If tier 1 has no passing candidate, tier 2 adds threshold heterogeneity, an optic exemption and a different input count.
5. If tier 2 has no passing candidate, tier 3 changes the neuron or synapse model, one mechanism at a time (section 2.2.4).

Scales go through `Engine.set_weight_scale` and background through `set_background`. Threshold offsets go into the per-neuron base threshold that `Neuromod.compose` starts from (section 8.4, WP15). All of them are applied once per worker process before `store("initial")`, and each scale combination is built in a fresh process (SPEC section 3.3; `docs/calibration.md` records the carry-over and exit-134 abort an in-process ratio change caused). A tier-3 mechanism is chosen earlier, at `build` (section 2.2.4). Generalising item 44, drive-v0.2 content is in force only when an experiment pins `drive-v0.2` with `background: true`. The one exception is the declared feed-forward fixture of section 8.1. The `mechanisms` section is drive content: it is in force exactly when the rest of the file is, including in that fixture.

### 2.2 Search space

#### 2.2.1 Transmitter rule (fixed by biology, not tuned)

WP14 builds `data/transmitters-v0.2.yaml` from the pinned annotation v2.1.0. Each neuron i gets a class c(i) from {ACh, Glu, GABA, His, mod, unk}, decided in this order:

1. Photoreceptors. Cell types R1-6, R7 and R8 get His, from the provenance table below.
2. Curated transmitter. If `known_nt` lists acetylcholine, glutamate, GABA or histamine, the first one listed decides. If it lists only modulatory transmitters (dopamine, serotonin, octopamine, tyramine), the class is mod.
3. No curated label. The neuron keeps the connection file's sign, and `top_nt` only names the class within that sign.
   - An inhibitory neuron is Glu when `top_nt` is glutamate, GABA when it is gaba, and unk otherwise.
   - An excitatory neuron is ACh when `top_nt` is acetylcholine, mod when it is dopamine, serotonin or octopamine, and unk otherwise.

The curated sign s_cur(i) is −1 for Glu, GABA and His and +1 for ACh and mod. For unk it is the connection file's sign. Modulatory transmitters count as excitatory, the Shiu 2024 convention.

The connection file's sign s_pq(k) of row k is its `Excitatory` column. WP14 verifies that s_pq is a function of the presynaptic neuron; test 0.10 fails if it is not. The census also reports every neuron whose s_pq differs from the Shiu rule applied to `top_nt`. Step 3 never changes such a neuron's sign, so only curated labels and the photoreceptor table change signs.

Row scale. For row k with presynaptic neuron j = pre(k):

```
scale_k = (s_cur(j) / s_pq(k)) × g(c(j))
g(Glu) = g_glu      g(GABA) = g_gaba      g(His) = g_his = 1
g(ACh) = g(mod) = 1
g(unk) = 1 if s_pq(k) > 0, else g_gaba
```

`scale_array()` returns float32 of shape (n_syn,) in connection-file order, the order `set_weight_scale` takes. Engine weights become `_base_w_mv × scale`, and the engine already accepts negative factors. `g_his` stays 1, and the photoreceptor input rate calibrated in section 3.4 acts as the gain.

Scope. `transmitters.scope` defaults to `brain`, which applies curated corrections to every presynaptic neuron. `optic_sensory` applies them only to presynaptic super_class optic and sensory, and leaves other neurons on step 3 (open question 4).

The table below counts neurons whose curated `known_nt` sign disagrees with their `top_nt` sign, by super_class. The census recomputes the counts against the connection file's sign.

| Change | sensory | optic | central | visual_projection | descending | total |
|---|---:|---:|---:|---:|---:|---:|
| predicted excitatory, curated inhibitory | 809 | 533 | 8 | 0 | 0 | 1,350 |
| predicted inhibitory, curated excitatory | 5 | 492 | 41 | 2 | 2 | 542 |

| Cell type | Annotation count | In engine | `top_nt` counts | `known_nt` | Class under the rule |
|---|---:|---:|---|---|---|
| R1-6 | 8,452 | 7,932 | ACh 5,343; Glu 1,675; GABA 530; serotonin 397; empty 393; octopamine 89; dopamine 25 | none | His |
| R7 | 1,343 | 1,337 | Glu 731; ACh 319; GABA 269; others small | none | His |
| R8 | 1,324 | 1,314 | mostly excitatory classes | histamine | His |
| L1 | 1,579 | — | Glu 1,043; GABA 512; ACh 24 | glutamate | Glu |
| L2, Mi1, Tm3 | 1,554; 1,580; 1,746 | — | — | acetylcholine | ACh |

| Claim | Source | Checked |
|---|---|---|
| Photoreceptors release histamine onto a histamine-gated chloride channel; LMCs hyperpolarise to light | Hardie RC 1989, Nature 339:704–706 | yes |
| hclA and hclB form the photoreceptor-synapse histamine channel in Drosophila | Pantazis A et al. 2008, J Neurosci 28(29):7250 | yes |
| R7 and R8 signal through Ort, the histamine-gated channel, onto Dm8 and Tm5c | Gao S et al. 2008, Neuron 60(2):328 | yes |
| ON selectivity needs sign inversion from glutamatergic L1 through GluClα and GABAergic inhibition onto Mi1 and Tm3 | Molina-Obando S et al. 2019, eLife 8:e49373 | yes |

The L1 relay. All 1,579 L1 neurons become Glu and take `g_glu`, including the 512 predicted GABA and 24 predicted ACh. The L1 → Mi1 (121,693 synapses) and L1 → Tm3 (80,600 synapses) rows are inhibitory. R1-6 → L1 (63,344 synapses) and R1-6 → L2 (62,051 synapses) become fully inhibitory, where the predicted signed sums were +35,316 and +33,833.

#### 2.2.2 Tier 1 (tuned)

| Parameter | Grid | Unit | Note |
|---|---|---|---|
| `drive.g_gaba` | 1, 2, 3, 4, 6, 8 | ratio | scale of GABA-class rows |
| `drive.g_glu` | 1, 2, 3, 4, 6, 8 | ratio | scale of Glu-class rows |
| `drive.w_bg` | 0.70 to 1.60 in steps of 0.05 (19 values) | mV | one common weight for every non-sensory drive group |
| `bg.n_bg` | 100 | inputs per neuron | fixed in tier 1 |
| `bg.r_bg` | 10 | Hz per input | fixed |

Groups are those of `drive-dev.yaml`. Sensory neurons get no background, so photoreceptors are silent at rest in the dark, and their class changes the rest point only under light (V3, section 3.4). The diagonal g_gaba = g_glu is Phase 1's `g_inh` grid except for the roughly 1,900 corrected neurons.

#### 2.2.3 Tier 2 (only when section 2.6 calls for it)

| Parameter | Values | Unit | Definition |
|---|---|---|---|
| `drive.sigma_th` | 0, 1, 2 | mV | per-neuron base threshold `lif.v_th + sigma_th × z_i`, with z_i from N(0, 1) truncated to ±2 |
| `drive.optic_exemption` | off, on | flag | when on, g_gaba and g_glu do not apply to presynaptic super_class optic rows; curated signs still apply |
| `bg.n_bg` | 25, 100, 400 | inputs | the weight grid is multiplied by 100/n_bg, so mean drive stays the same and input variance scales by 100/n_bg |

z_i is drawn once from `np.random.SeedSequence(drive.seed, spawn_key=(0, 0, DRIVE))`, with the new component identifier `DRIVE = 7`, and the SHA-256 of its float32 array is recorded. The grid is 3 × 2 × 3 = 18 settings minus the tier-1 setting, so 17 variants. They run for the three scale pairs named by section 2.6 step 4, at all 19 scaled weights, three seeds and 12 s each: 17 × 3 × 19 × 3 × 12 = 34,884 brain s.

Why these three. Heterogeneous thresholds are the standard way to break the all-or-none ignition of a homogeneous LIF network. The optic lobe holds 77,536 of the 138,639 neurons, and its columnar inhibition may need a different scale from the central brain's. Item 24 tested input variance at ratio 1 only.

#### 2.2.4 Tier 3 (section 2.6 step 6)

Rolf authorised tier 3 on 2026-09-16 (open question 6). Tiers 1 and 2 ended on one conflict: every scale that quiets the network abolishes the sugar reflex.

- Extended-mode retention was 0.00178571 at (3, 6) and (3, 8) and 0 at (4, 2), against a bare ten-seed mean of 56.0 Hz. Upstream, MN9 fell from 85.3 Hz to 0 at every tested scale (WP17 report).
- MN9 has 5,579 input synapses; 3,128 are GABA or Glu (2,777 + 351) and 2,411 are ACh. A structural proxy of recruited inhibitory over excitatory flow from sugar GRNs to MN9 is 0.83 at scale 1, 1.0 near g 1.2 on the diagonal, 1.66 at (2, 2) and 2.9 to 3.3 at the tested pairs (WP17 report). No feed-forward measurement exists between scale 1 and g_gaba 3.
- At ratio 1 the network does not rest. The map (connection-file signs) measured central 17.7 to 19.2 Hz and F 3.61 to 3.67 at 1.15 to 1.25 mV (`docs/resting-map.md`), and item 24 found only silent or ignited states.

Tier 3 keeps the scales at or near 1 and quiets the network by changing the neuron or synapse model.

Rules for every mechanism:

- A mechanism is a block of the drive file's `mechanisms` section. An absent section, or every block null, means no mechanism.
- At most one block is non-null (open question 33).
- The engine has one model variant per mechanism, held as literal strings in `engine/models.py`. `build` chooses the variant once, before any Brian2 object exists. No variant is a runtime flag or a zero-valued term inside another variant's equations.
- Variant `lif` is the Phase 1 model byte for byte: the same model, threshold, reset and `on_pre` strings, method, objects, object names, namespace keys, construction order and random draws as `brian_engine.py` at the WP24 branch point. `build` with `mechanisms` not passed, `None`, or a `Mechanisms` whose blocks are all null builds `lif`, and it is the only path tests 0.3, 0.8 and 0.14 take. On that path `build` makes the same Brian2 constructor calls, with the same arguments and in the same order, as at the branch point. It creates no extra object, namespace key, state variable or monitored variable. So every existing test stays bitwise (test 0.15).
- Mechanism parameters are set in `build` before `store("initial")` and never written afterwards. No mechanism draws random numbers, so a seed produces the same input streams with a mechanism on or off.
- Each unit of the search uses one global value per mechanism parameter. A scope says which neurons carry it (open question 32). Sensory neurons are always outside it: super_class `sensory` from `annotations_in_engine`, the same column the optic exemption reads. They carry the stimulus encoders (sugar GRNs, photoreceptors), so they neither adapt nor depress (open question 29).
- The evidence is thin. No adaptation, depression or reversal constant has been measured for this network, and the engine's volt-scaled currents have no direct biological magnitude. The grids are therefore wide: a factor of 300 in adaptation strength, 40 in depression strength, and reversals from 5 to 20 mV below v_0.

| Engine model | Mechanism | Method | Closed-form test |
|---|---|---|---|
| `lif` | none | `linear` | 0.15 (switch neutrality) |
| `lif+sfa` | 3a, spike-frequency adaptation | `linear` | 0.16 |
| `lif+std` | 3b, short-term synaptic depression | `linear` | 0.17 |
| `lif+cbi` | 3c, conductance-based inhibition | `rk4` | 0.18 |

Every variant keeps `threshold` `v > v_th_i`, `refractory` `rfc`, the synapse model `w : volt` with delay `lif.t_dly`, and every external input as built today: upstream `PoissonInput` on v, background `PoissonInput` on g with `w_bg_i`, and extended and spike-list synapses `g += w_in`.

Strings. The `lif` strings are defined by bytes, not by the listing below. WP24's first commit records the model, threshold, reset and `on_pre` strings that `brian_engine.py` passes to Brian2 at the branch point in `tests/fixtures/wp24-off-reference.json`, as `lif_model`, `lif_threshold`, `lif_reset` and `lif_on_pre` with the SHA-256 of each. Test 0.15 (a) compares `model_strings()` with those four strings. The `lif` listing documents them and takes no part in any test. For the other variants the listings are normative. A model string is its listed lines joined by a newline, with a final newline, as `lif_model` is. A reset or `on_pre` string is its one listed line with no final newline. `engine/models.py` holds the strings verbatim, and review r18a, r18b or r18c compares them with the listings (open question 34). The `initial` and `namespace adds` lines are not strings; they state initial values and namespace entries.

`lif`:

```
model:   dv/dt = (v_0 - v + g) / t_mbr : volt (unless refractory)
         dg/dt = -g / tau : volt (unless refractory)
         rfc : second
         v_th_i : volt
         gain_i : 1
         w_bg_i : volt
reset:   v = v_rst; w = 0; g = 0 * mV
on_pre:  g += w * gain_i_post
```

Engine interface. These extend the SPEC section 3.1 `Engine` protocol. Tests 0.15 to 0.18 and the tier-3 stages read mechanism state only through them, never through Brian2 objects (item 57):

- `build(connectome, params, topology, mechanisms: Mechanisms | None = None)`. The variant is chosen from `mechanisms` before any Brian2 object exists.
- `engine_model() -> str`: `lif`, `lif+sfa`, `lif+std` or `lif+cbi`.
- `model_strings() -> tuple[str, str, str, str]`: the model, threshold, reset and `on_pre` strings passed to Brian2. `method() -> str`: `linear` or `rk4`.
- `mechanism_traces(since_tick: int) -> MechanismTraceTable`: on `trace_idx` only, on the tick grid of `traces(since_tick)`. Its columns are `a_sfa_mv` under `lif+sfa`, `x_std` and `xr_std` under `lif+std`, and `h_inh` under `lif+cbi`, each of shape (len(`trace_idx`), n_ticks). Under `lif` it has no columns, and no monitor exists for it.
- `ChunkResult.h_max: float | None`: under `lif+cbi`, the largest h_inh over all neurons at the end of that chunk, read from the state after `run_chunk`; otherwise None. An evaluation's h_max is the largest over its chunks. A peak between chunk ends is not seen (open question 38).
- `set_refractory` and `compose_refractory` raise `ValueError("depression latch: refractory period below lif.t_dly")` when they would give a neuron with U_std_i > 0 a refractory period below `lif.t_dly`.

**3a, spike-frequency adaptation (`lif+sfa`).**

```
model:   dv/dt = (v_0 - v + g - a_sfa) / t_mbr : volt (unless refractory)
         dg/dt = -g / tau : volt (unless refractory)
         da_sfa/dt = -a_sfa / tau_sfa_i : volt (unless refractory)
         rfc : second
         v_th_i : volt
         gain_i : 1
         w_bg_i : volt
         b_sfa_i : volt (constant)
         tau_sfa_i : second (constant)
reset:   v = v_rst; w = 0; g = 0 * mV; a_sfa += b_sfa_i
on_pre:  g += w * gain_i_post
initial: a_sfa = 0 mV
```

- State and units. a_sfa is an adaptation current in volts, the unit of g, because the engine writes currents with the membrane resistance folded in. Each spike raises it by b_sfa_i, and it decays with tau_sfa_i. A neuron firing steadily at rate f carries a mean a_sfa of b_sfa × tau_sfa × f.
- Integration. The system stays linear with per-neuron constant coefficients, so `linear` applies. Brian2 2.10.1's exact update divides by t_mbr − tau_sfa_i, so the loader rejects tau_sfa below 2 × max(`lif.t_mbr`, `lif.tau`), which is 40 ms.
- Reset and refractory. The reset adds b_sfa_i and does not clear a_sfa. a_sfa is frozen during refractory, like g (open question 30).
- Scope `non_sensory`. b_sfa_i is b inside the scope and 0 mV outside; tau_sfa_i is tau everywhere, so the update never divides by zero. Neurons outside the scope follow the `lif` dynamics to 1e-9 (test 0.16 (e)), not bitwise, because the generated update expression differs. MN9, the neuron R-reflex scores, is inside the scope, as is every motor neuron. T0 records MN9's a_sfa, so a T0 failure can be split into cost at the readout and cost along the path (open question 42).
- Why it can separate rest from the reflex. Adaptation lowers a neuron's sustained rate in proportion to that rate, and changes no weight. From the LIF rate formula f = 1 / (t_rfc + t_mbr × ln((D + 7 mV) / D)), with D the steady drive above threshold, a neuron at 56 Hz has D = 5.89 mV and a slope k of 5.8 Hz per mV. To first order it keeps 1 / (1 + k × b × tau) of its rate: 97 percent at b × tau = 0.005 mV·s, 78 percent at 0.05 and 26 percent at 0.5. In the recurrent network that loss feeds back around every excitatory loop, so the network rate can fall much further than one feed-forward stage does. Tier 3a looks for pairs near 1, where the path to MN9 keeps its balance of excitation and inhibition, quieted by adaptation. The R-reflex window is sustained: the stimulus is on for the whole 3 s probe and scored over its last second. So the reflex pays the steady-state cost at every non-sensory stage, not a transient cost (open question 26). T0 and T1 measure whether the recurrent gain outweighs that cost.
- Grid: `b_mv` {0.1, 0.3, 1, 3} × `tau_ms` {50, 150, 500}, 12 settings, b × tau from 0.005 to 1.5 mV·s.

**3b, short-term synaptic depression (`lif+std`).**

```
model:   dv/dt = (v_0 - v + g) / t_mbr : volt (unless refractory)
         dg/dt = -g / tau : volt (unless refractory)
         dx_std/dt = (1 - x_std) / tau_std_i : 1
         rfc : second
         v_th_i : volt
         gain_i : 1
         w_bg_i : volt
         xr_std : 1
         U_std_i : 1 (constant)
         tau_std_i : second (constant)
reset:   v = v_rst; w = 0; g = 0 * mV; xr_std = x_std; x_std = xr_std * (1 - U_std_i)
on_pre:  g += w * gain_i_post * xr_std_pre
initial: x_std = 1, xr_std = 1
```

- State. x_std is neuron j's available resource fraction. At a spike, xr_std latches the fraction before the spike, and x_std loses the fraction U_std_i of it. The last reset statement reads xr_std, not x_std. Brian2 2.10.1's numpy target aliases the two after `xr_std = x_std` and updates `x_std = x_std * (1 - U_std_i)` in place, so the latch would carry the depleted value. The listed form matches test 0.17's closed form on both the Cython and numpy targets. Every synapse of j transmits w × xr_std, so at full resources a synapse transmits exactly today's weight and the calibrated resting PSP does not change. At a steady presynaptic rate r the mean-field resource is 1 / (1 + U × tau × r).
- Exactness. The per-synapse Tsodyks–Markram depression model with one U and tau per presynaptic neuron gives every outgoing synapse of that neuron the same resource trajectory, so one variable per neuron is exact. Delivery reads xr_std after `lif.t_dly` 1.8 ms, and a second spike inside that delay would overwrite it. `lif.t_rfc` 2.2 ms rules that out. `set_refractory` and `compose_refractory` raise when they would give a neuron with U_std_i > 0 a refractory period below `lif.t_dly` (engine interface above). That includes an active upstream bank target (refractory 0) inside the scope. Sensory bank targets such as the sugar GRNs are outside every scope.
- Integration and refractory. x_std is decoupled from v and g, so `linear` applies. It recovers during refractory: depletion is a synaptic state, not a membrane state (open question 30).
- Scope. `non_sensory_excitatory` covers presynaptic neurons with s_cur = +1 (section 2.2.1) that are not sensory. `non_sensory` covers every non-sensory presynaptic neuron. U_std_i is U inside the scope and 0 outside; tau_std_i is tau everywhere. Both scopes are in the grid. Depressing only excitation tilts an active path towards inhibition, as scaling did at MN9. Depressing both keeps the path's ratio but also weakens the inhibition that quiets the network.
- Why it can separate rest from the reflex. Depression weakens the output of neurons that fire fast and leaves rest-rate transmission nearly whole: at U × tau = 0.02 s the resource is 0.91 at 5 Hz and 0.5 at 50 Hz. Ignition needs sustained high rates, so depression caps it without scaling any weight. The reflex path fires at tens of hertz for the whole sustained window, so it pays depression at every non-sensory stage (open question 26).
- Grid: `scope` {non_sensory_excitatory, non_sensory} × `U` {0.05, 0.2, 0.5} × `tau_ms` {100, 400}, 12 settings, U × tau from 0.005 to 0.2 s.

**3c, conductance-based inhibition (`lif+cbi`).**

```
model:   dv/dt = (v_0 - v + g + h_inh * (E_inh - v)) / t_mbr : volt (unless refractory)
         dg/dt = -g / tau : volt (unless refractory)
         dh_inh/dt = -h_inh / tau : 1 (unless refractory)
         rfc : second
         v_th_i : volt
         gain_i : 1
         w_bg_i : volt
reset:   v = v_rst; w = 0; g = 0 * mV; h_inh = 0
on_pre:  g += w * gain_i_post * int(w > 0 * mV); h_inh += -w * gain_i_post * int(w < 0 * mV) / dV_inh
initial: h_inh = 0
namespace adds: E_inh (mV), dV_inh = v_0 - E_inh
```

- State. h_inh is an inhibitory conductance relative to the leak, with the same decay constant as g. A recurrent event with w < 0 adds −w × gain / (v_0 − E_inh). At v = v_0 that event injects exactly the current today's weight does. The sign test reads w at delivery, so a row whose sign the transmitter rule or `set_weight_scale` flipped routes to the right variable, and a disconnected row (w = 0) adds nothing. External inputs are excitatory and stay current-based.
- Effect. Inhibition now grows with depolarisation and cannot drive v below E_inh. A neuron pushed towards threshold by recurrent excitation receives stronger inhibition, which works against ignition without scaling any weight. At E_inh −57 mV an inhibitory event at threshold (−45 mV) is 2.4 times its size at v_0; at −72 mV it is 1.35 times. MN9 near threshold pays the same factor, and T0 measures whether the path survives.
- Integration. The product h_inh × v makes the system bilinear. Brian2 2.10.1 rejects `linear` for it, so the variant uses `rk4` at `lif.dt`. The membrane's effective time constant is t_mbr / (1 + h_inh), and rk4's error grows with the step taken over it. An evaluation whose h_max (engine interface above) gives `lif.dt` × (1 + h_max) / `lif.t_mbr` above `tier3.cbi_stiff_limit` 0.1 is flagged `cbi-stiff`, and its metrics count as not computable (section 2.6). The limit keeps about ten steps per effective time constant; at `lif.dt` 0.1 ms and `lif.t_mbr` 20 ms it is h_max above 19 (open question 38).
- Reset and refractory. h_inh is frozen during refractory and cleared at a spike, like g.
- Scope `all`: every recurrent row whose weight is negative at delivery.
- Grid: `E_inh_mv` {−72, −62, −57}, which is 20, 10 and 5 mV below v_0: 3 settings (open question 31).

**3d, KC-targeted APL inhibition (no new variant).** One factor `g_gaba_kc` multiplies GABA rows whose postsynaptic neuron is a KC. It is applied through `set_weight_scale` on the same `scale_array` path as `g_gaba`. There is no equation change and no new engine variant. `gain_i` is untouched: it is layer A/C's pharmacology channel. The KC mask is `cell_class` `Kenyon_Cell` from `annotations_in_engine`, the same selector as population `KC`. Item 32 allows this one per-population constant (KC). Item 39 lets an empty 3c start 3d. When `g_gaba_kc` is 1, the scale array is byte-identical to the same call without the factor. Only GABA→KC rows change when the factor is not 1; unk inhibitory rows and GABA rows onto non-KCs do not.

- Grid: pairs (1, 1), (1, 2), (1, 4) × {no mechanism, 3a at b 1 mV and τ 50 ms} × `g_gaba_kc` {2, 3, 4, 6}: 24 units. T0 and T1 run in one wave: KCs are silent in the T0 probe, so T0 cannot fail on KC, but T0 is still recorded.

**Pair set P3 and fixed settings.** Every sub-tier searches the same 15 scale pairs (g_gaba, g_glu):

- g_gaba {1, 1.5, 2} × g_glu {1, 2, 4, 8}. This is where the proxy sits near parity and where no feed-forward retention has been measured. g_gaba 1.5 is a new point between parity and (2, 2). At g_gaba 2, F missed narrowly at (2, 6) and (2, 8), 3.12 to 3.13 (WP17 report). g_glu is spread wide because MN9's direct inhibitory inputs are mostly GABA.
- The three pairs tier 2 ran on: (3, 6), (3, 8), (4, 2). They test whether a mechanism restores the reflex where rest is already close.

Every unit uses `sigma_th` 0, optic exemption off, `n_bg` 100 and the 19 tier-1 weights. σ_th and n_bg do not enter R-reflex (c), and optic exemption left it unchanged where measured (WP17 report). Grids, pairs and search constants live in `data/rest-tier3-v0.2.yaml` (section 8.2).

**The `mechanisms` section.** Key names:

```
mechanisms:
  adaptation:             {b_mv, tau_ms, scope: non_sensory, mask_sha256} or null
  depression:             {U, tau_ms, scope: non_sensory_excitatory | non_sensory, mask_sha256} or null
  conductance_inhibition: {E_inh_mv, scope: all} or null
```

Scope masks. A mask is a uint8 array of length `engine.n` whose element i is 1 when neuron `root_ids[i]` is in the scope and 0 otherwise. `root_ids` order is engine order and the registry's order, not connection-file order. `mask_sha256` is the SHA-256 of the mask's bytes. Sensory means super_class `sensory` in `annotations_in_engine`, the column the optic exemption reads. `non_sensory` is every neuron that is not sensory. `non_sensory_excitatory` is every neuron that is not sensory and has s_cur = +1 (section 2.2.1); an unk neuron's s_cur is its connection-file sign, so it is in the scope exactly when that sign is +1. Scope `all` (3c) has no mask, because the delivery-time sign of w selects the route.

`drive/mechanisms.py` loads the section and resolves it against the registry and the transmitter file into a `Mechanisms` object of per-neuron arrays (`engine/models.py`), which is passed to `build`. `engine_model_of(section)` names the variant: a non-null `adaptation` gives `lif+sfa`, `depression` gives `lif+std`, `conductance_inhibition` gives `lif+cbi`, and an absent section or all-null blocks give `lif`. The loader rejects:

- an unknown key in the section or in a block;
- more than one non-null block;
- a block at zero strength (`b_mv` 0 or `U` 0), since off is written as null;
- a non-finite value;
- adaptation `tau_ms` below 40, `U` outside (0, 1], depression `tau_ms` below 10, or `E_inh_mv` above `lif.v_0` − 1 mV;
- a scope outside its list;
- a `mask_sha256` that differs from the resolved mask.

`load_drive_rest` accepts exactly these top-level keys, and rejects any other, so a misspelt section cannot be ignored silently:

- the six section 2.5 sections and `mechanisms`;
- `version`, whose value must be `v0.2` (WP19's drive documents write it);
- `configuration_class`, whose value must be `development`, and, only beside it, `candidate_id`, `selection` and `note`.

The development keys are legal on class-development files such as `data/drive-dev-p2.yaml`. Identity stays the file's bytes, so they add no identity rule. The committed `data/drive-v0.2.yaml` carries none of them. The drive mapping `load_drive_rest` returns always has a `mechanisms` field: the validated section, or null when the file has none (test 0.15 (b)(ii)).

`apply_rest_substrate` requires the mapping it applies to state `mechanisms`, a section or null, and raises when the key is missing. When its target has `engine_model()`, it raises unless that equals `engine_model_of` of the mapping's section. A build that omits the mechanism therefore fails on its first application instead of running `lif` (section 2.5).

### 2.3 Resting criterion

Item 43's structure is kept and tightened in three ways:

- A central floor and a DAN floor of 0.5 Hz each. A near-silent network passes the synchrony tests while no modulation reaches a spike, and the derived-rate dopamine form needs DAN input.
- A KC cap of 2 Hz. Kenyon cells are sparse; ratio 4 gave 1.45 to 1.51 Hz against a placeholder target of 0.1 Hz.
- A reflex requirement inside the screen, because item 47 shows that rest and the reflex can conflict.

Screening windows use the Phase 1 K1 calibration state (SPEC section 3.3): wild type, background on, layer A on with pools clamped at `DA_ref` and tonic arrays held, layer C on without drug.

Metrics:

- F is the population Fano factor of all-neuron counts in 1 ms bins.
- b is the largest 1 ms bin fraction of neurons.
- The stability ratio is the central rate over the first second divided by the rate over the last second.
- Rates are group means in Hz.

A metric that cannot be computed counts as a failure with the capped violation of section 2.6. Examples are F for a window with no spikes, and the stability ratio when the last second has no central spikes.

R-screen covers one scale setting at two adjacent grid weights; the lower weight becomes the candidate weight. Each weight gets three seeds of 2 s settle plus 10 s measurement.

| Quantity | Rule | Parameter |
|---|---|---|
| F | < 3 in every seed at both weights | `rest.fano_max` 3 |
| b | < 0.05 in every seed at both weights | `rest.bin_fraction_max` 0.05 |
| stability ratio | in [0.5, 2] in every seed at both weights | `rest.stability_ratio` |
| central rate, seed mean | in [0.5, 8] Hz at both weights | `rest.central_hz` |
| DAN group rate, seed mean | in [0.5, 10] Hz at both weights | `rest.dan_hz` |
| KC group rate, seed mean | ≤ 2 Hz at both weights | `rest.kc_max_hz` |
| gradedness | central rate at the next grid weight above the pair < 3 × central rate at each pair member | `rest.grade_factor` 3 |

R-reflex runs only on R-screen passers, in extended mode, with sugar GRNs at 150 Hz and 1 s per condition after settle. It has three parts:

- (a) Background on, both weights, three seeds: the MN9 sugar-minus-silent difference is at least 40 Hz in every seed.
- (b) Background on, candidate weight, ten seeds: the ten-seed mean difference exceeds 50 Hz and no seed falls below 40 Hz (item 61).
- (c) Minimum retained feed-forward response. Background off, A and C on with `dopamine-v0.1`, ten seeds, upstream and extended modes. The same seeds, windows, layers and modes run twice: with every scale 1 (the matched bare reference) and with the candidate's scales. Retention per mode is the candidate's ten-seed mean MN9 difference divided by the bare reference's. Extended-mode retention must be at least `rest.ff_retention_min` 0.5, so at most half the feed-forward response may be lost. Upstream retention and both arms' per-seed values are recorded. The bare reference is measured once per R-reflex batch and shared by every candidate in the batch.

R-long. Candidate weight, ten seeds, 2 s settle plus 30 s. In every seed:

- F < 3 over the window;
- no ignition (section 9.2);
- central mean of the first 5 s over the last 5 s in [0.5, 2].

A candidate passes the criterion when it passes all three stages. The allowed feed-forward loss is open question 11.

### 2.4 Settle rule for schema 1.3 runs

Schema 1.2 files keep the Phase 1 rule. The rule below applies to every schema 1.3 probe.

Windows. Settle compares consecutive windows of `settle.window_s_13` 1.0 s. Each window is split into `settle.blocks` 5 equal blocks. Comparisons start at `settle.min_s` 2 and repeat at each window boundary.

Decision set. The candidates are every recorded population and every drive group. At the first comparison, a candidate g with N_g neurons, spike count n_g and mean rate m_g = n_g / (N_g × W) in the window just completed is resolved when:

```
n_g ≥ 2 × settle.fano_ref × (settle.k_resolve × m_g / δ_g)²
δ_g = max(settle.tol_abs_rate_13, settle.tol_rate × m_g)
```

The parameters are `settle.fano_ref` 3, `settle.k_resolve` 5, `settle.tol_abs_rate_13` 0.02 Hz and `settle.tol_rate` 0.10. With these values a candidate above 0.2 Hz needs 15,000 spikes per window. The condition uses counts only, so a drifting population cannot exclude itself by its own variance. Resolved candidates form the decision set D, which is fixed for the probe. The others are recorded as `unresolved` and never block settle. A two-neuron steering population, or the 361-neuron DAN group at a few hertz, cannot show a 10 percent drift bound in 10 s, and the record says so.

Equivalence test. For g in D, with m the window-mean rate, s the standard deviation of the 5 block-mean rates within a window, and Δ = m_last − m_prev:

```
SE_Δ = sqrt(s_last² / 5 + s_prev² / 5)
pass = |Δ| + t × SE_Δ ≤ δ_g(m_prev)
t = settle.t_quantile 1.860 (one-sided 95 percent, 8 degrees of freedom)
```

Drift must be shown to lie inside ±δ_g, so sampling noise makes passing harder, not easier. Block means absorb super-Poisson fluctuation at the block scale.

Convergence. A probe converges at the first comparison where every population in D passes. If it has not converged by `settle.max_s` 10, it is unsettled, which fails acceptance clause 3 as in Phase 1.

Meaning. For schema 1.3, "settled" means that the resolved population set has converged. That is narrower than the Phase 1 meaning, which covered every recorded population and every compartment. Every manifest, summary and results table that shows a settle flag shows the unresolved populations and the dopamine fixed-point gaps next to it. Whether Rolf accepts this meaning or wants an extra gate is open question 13.

Dopamine. Compartment dopamine is not a convergence criterion for schema 1.3. `reset_fast()` starts every innervated compartment at its analytic fixed point for the composed parameters (SPEC section 3.4). The wild-type clearance time constant `DA_ref / Q_c` is 7.5 s, and longer with a blocked transporter, so a window-to-window test within 10 s cannot separate drift from phasic fluctuation. Instead each probe records, per compartment, the fixed-point gap: the recording-window mean dopamine minus the analytic fixed point at the recording's measured weighted DAN input rate. The DA steady-state detector (section 9.2) flags gaps above `detector.da_gap_fraction` 0.25 of that fixed point. Wild-type resting dopamine is qualified separately by 3.1br(ii).

Test 0.13 runs this rule's own code path on synthetic block counts, 1,000 trials per case:

- (a) Stationary: a 26,568-neuron population at 1 Hz and a 77,529-neuron population at 0.5 Hz with block-scale Fano 2.6, both resolved; a 5,177-neuron population at 1.5 Hz and a 2-neuron population at 5 Hz, both unresolved. The probe converges by `settle.max_s` in at least 99 percent of trials, and the unresolved labels are correct.
- (b) Drift: the 26,568-neuron population's rate rises 20 percent per second throughout. Settle is declared converged in at most 1 percent of trials.
- (c) Slow drift: the same at 5 percent per second. The acceptance rate is recorded, with no target.

### 2.5 Calibration chain, freeze protocol and configuration files

Freeze protocol, for the `drive`, `dopamine`, `visual`, `behaviour-base` and `behaviour` v0.2 files and the calibration fixtures that carry candidate values (section 3.5):

1. Configuration commit. The WP writes the configuration file and commits it with nothing else. The file holds numeric configuration plus a `provenance` block: the SHA-256 of each evidence record the values came from, the Camber job ids, and the blob ids of upstream configuration files. It holds no qualification flag and no field a later execution fills in.
2. Executions. The entries that test the configuration run on a clean tree at that commit. Each identity block stores the entry's inputs with their blob ids (section 5.1).
3. Evidence commit. Results go to `validation/status.json`, `validation/records/p2/<stage>.json` and the WP's documents. None of these is an input, so the evidence commit changes no identity.
4. Qualification. A configuration is qualified for a run exactly when the section 5.2 entries that test it are passed and valid for that run. No configuration file carries a `qualified` field. The runner asks `qualification_of` in `validation/binding.py` (WP16) instead of reading a file flag.
5. Failure. A failed qualification leads to new configuration bytes, a new configuration commit and new executions. A configuration's identity is its bytes: evidence for earlier bytes stays attached to those bytes and is never relabelled.

`substrate_id` is `rest:` followed by the first 16 hex characters of the drive configuration file's SHA-256 when the file has no mechanism on. With a mechanism on it is `rest-<tag>:` followed by the same 16 hex characters, with tag `sfa`, `std` or `cbi` (section 2.2.4). Every writer computes it with `substrate_id_for` in `drive/mechanisms.py`, and none builds the string itself. It goes into every manifest and identity block, beside `engine_model` (section 5.1). Test 0.9r(c) runs the whole protocol on a constructed repository.

Stage chain. `scripts/calibrate.py --phase 2` dispatches these stages in order. WP15 owns the dispatcher, and each WP registers its stages through `STAGE`. Every stage writes a resumable record `validation/records/p2/<stage>.json` with its status, input identity and outputs. A rerun skips a stage whose record is passed with an unchanged input identity.

1. C0 census (WP14, no engine): `transmitters-v0.2.yaml`, `populations-v0.2.yaml`, the retinotopy tables, `docs/transmitter-census.md`.
2. R1 screen (WP17, development, Camber): R-screen over the pairs chosen by section 2.6 step 1.
3. R2 shortlist (WP17, development): R-reflex, R-long and the ranking of section 2.6.
4. R3 visual screen (WP18, development). It applies V3 and three-seed V1 at the four V-cal rates to candidates in rank order, starting with the shortlist. A candidate passes R3 when some rate passes both. When no shortlisted candidate passes, R3 continues down the ranked list until one passes or `rest.r3_max` 6 candidates have been screened.
5. R4 selection (WP19): the first candidate in rank order that passed R3. If no screened candidate passed, or none had passed 12 wall hours after the shortlist commit, the first candidate by rank. The reason is recorded, and R3 keeps running and recording. Vision on the chosen substrate then follows section 3.7.
6. K1r (WP19, Mac; speculative parallel coordinate descent whose rounds reproduce the serial descent bitwise, review r14c decision 48; serial K1r at the measured q1 needs 1.55 h, over the one-hour rule).
7. Drive configuration commit (WP19).
8. K2r and the dopamine configuration commit (WP19, Mac).
9. Q-rest (WP19, Mac).

Tier 3. When R2 ends empty after tier 2, WP24's stages T3a, T3b and T3c (section 2.6 step 6; development, Camber) run between R2 and R3, each only when the one before ends empty. A tier-3 ranked list takes R2's place as the input of R3 and R4. Every later stage runs on it unchanged, with the candidate's mechanism in force. K1r tunes group weights with the mechanism fixed. The mechanism reaches every engine by one path:

1. Row. Before the drive commit, a candidate's mechanism exists only in its ranked-list row (section 2.6 step 6, Records). `drive/mechanisms.py` gives `mechanisms_section(row)` (the drive-file section) and `mechanisms_from_unit(row, registry)` (the resolved `Mechanisms`), and it rejects a row whose `engine_model` is not `engine_model_of` its section. A row without `engine_model` or `mechanisms`, which is every tier-1 and tier-2 row, reads as `lif` with a null section. WP19's `ranked_candidates` keeps the row's `engine_model` and `mechanisms`, and its candidate identifier includes them (section 2.6 step 6).
2. Document. Every drive document built from a row carries `mechanisms_section(row)` as its `mechanisms` section. For WP19 that is `make_drive`, so K1r's in-memory documents, the drive commit and `data/drive-v0.2.yaml` carry it. For WP18, R3 builds each candidate's engine from such a document.
3. Build. Every engine that applies a rest drive document, from a file or from memory, passes `mechanisms_from_drive(drive, registry)` to `build`. The call sites are the drive block of `orchestrator/workers.py` (Q-rest's schema 1.3 fixtures, V-cal and every later run, from the pin); `_worker` in `drive/rest_calibration.py` (the K1r, Q-rest and B1-rest jobs, and the K2r jobs that `neuromod/calibration.py` submits through `run_jobs`, as on `lane/w19` at 957f8b1); `_build_engine` in `drive/rest_map.py` (T0 to T2); and R3's engine screen in `behaviour/visual_calibration.py`. A bare reference builds `lif`.
4. Guard. `apply_rest_substrate` raises when the mapping it applies does not state `mechanisms`, or when the engine's `engine_model()` differs from the mapping's (section 2.2.4). A call site that builds without the mechanism fails on its first application.
5. Records. Every R3, K1r and K2r record line that names a candidate stores the row's `engine_model` beside the `engine_model()` its engine reported. R4 and the drive commit refuse a record in which the two differ, with reason `mechanism not in force`. Entries from Q-rest on are covered by the section 5.1 validity clause on `substrate_id` and `engine_model`.

K1r. The calibration state is that of section 2.3, with scales, transmitter rule and tier-2 settings fixed. K1r starts from the common weight and runs coordinate descent over group weights, each bounded to the common weight ± `k1r.bound_mv` 0.10 mV, for at most 40 evaluations. Each evaluation is seed 1 with 2 s settle plus 5 s measurement, and the objective is J (section 2.6). Evaluations with F ≥ 3, b ≥ 0.05 or central above 8 Hz are rejected. The configuration to commit is:

- the tuned table T, when K1r lowers J by at least `k1r.min_improvement` 20 percent;
- otherwise the common-weight table C.

If Q-rest fails on T, C gets its own configuration commit, K2r and Q-rest; evidence from T never qualifies C. If Q-rest fails on C, or C was committed first and failed, R4 selects again among the remaining ranked candidates. When `rest.qrest_max_candidates` 3 candidates have failed Q-rest, or the ranked list runs out first, section 2.6 step 5 applies to a tier-1 or tier-2 list. A tier-3 list's sub-tier ends empty with failed stage `Q-rest` (section 2.6 step 6).

K2r. Pools are clamped at `DA_ref`, background is on, A and C are on, and there is no drug. Three seeds (indices 1 to 3 from `seed_master` 20260912) each get 2 s settle plus 5 s measurement, giving R_c, the weighted DAN spike rate into compartment c. With `Q_c = DA_ref × (Vmax0_c / (Km0_c + DA_ref) + k_ns0)` in µM/s:

```
alpha_c = Q_c / max(R_c, da.R_min)      µM per weighted spike
S_c     = Q_c − alpha_c × R_c           µM/s, ≥ 0 by construction
mode    = derived when R_c ≥ da.R_min (S_c = 0), source otherwise
```

With `da.R_min` at 0.5 weighted spikes/s, alpha_c is continuous across the mode boundary and never exceeds Q_c / R_min = 0.00533 µM, below `alpha_max`. At R_c = 0, S_c = Q_c, the v0.1 tonic source.

Integration uses the per-compartment arrays from `dopamine-v0.2.yaml`, with `rel` the release scale from genotype and drug and `f_retained,c` the SPEC section 3.4 retained-DAN fraction:

- reset release: `rel × (alpha_c × R_c + S_c) × f_retained,c`;
- per chunk of duration Δ: `rel × (alpha_c × weighted counts_c + S_c × Δ × f_retained,c)`.

Silenced DANs produce no counts, so `f_retained` multiplies only the source term within chunks, as the current `neuromod/state.py` does. `neuromod/pools.py` already accepts per-compartment `alpha` and source arrays. Test 3.1r-alg checks the algebra before any free-pool run. At `rel` 1, `f_retained` 1 and no drug, the fixed point equals `DA_ref` to 1e-9 at R_c in {0, 0.01, 0.1, R_min − 1e-9, R_min, R_min + 1e-9, 10}, and S_c ≥ 0 everywhere.

Q-rest runs on free pools with A and C on, in this order: 3.1br, 2.3r, 2.7r, 2.6r, 2.2r, 1.4r, 1.4r-ff, 2.4r, with 2.1r recorded (section 5.3). If 3.1br(ii) fails, R_c is measured again on free pools with the current arrays, alpha_c and S_c are recomputed, and a new dopamine configuration commit and 3.1br follow. At most `k2r.max_iterations` 3 iterations run, each recorded. Failure after the last iteration fails Q-rest for that drive configuration.

`data/drive-v0.2.yaml` contains:

- `transmitter_rule`: file blob id and scope;
- `scales`: `g_gaba`, `g_glu`, `g_his`, the unk rule, and the scale-array SHA-256;
- `background`: `n_bg`, `r_bg`, and per group its size and `w_bg` (sensory 0);
- `threshold`: `sigma_th`, `drive.seed` and the z-array SHA-256, or null;
- `optic_exemption`;
- `mechanisms`, optional: the section 2.2.4 blocks, absent or all null for no mechanism;
- `provenance`: the R1, R2, R3, R4 and K1r record SHA-256s, the tier-3 plan, T0, T1, T2 and decision record SHA-256s of the candidate's sub-tier when it came from tier 3, the Camber map report path and SHA-256 if used, and the Camber job ids.

`data/dopamine-v0.2.yaml` contains:

- the v0.1 constants;
- `compartments`, the compartment names in registry order, which the loader checks as it does today;
- per compartment, in that order: `R_c` (the rate that `alpha_c` and `S_c` were computed from, and that reset uses), `alpha_c`, `S_c` and mode;
- the drive file's blob id;
- `provenance`: the K2r record SHA-256 and the iteration number.

Every runtime value comes from configuration files. Test `tests/test_p2_config_loaders.py` (WP15, no engine) builds settings through the real loaders and factories with no `validation/` directory present. It covers the configuration sets of section 8.1.

### 2.6 Decision rule

Closest-miss score. Each section 2.3 criterion contributes a log-scale violation, taken as the worst over seeds and over both pair members, and zero when the criterion is met. Rates are floored at 0.01 Hz before logarithms. Each violation is capped at `rest.violation_cap` 10, and a metric that is missing or cannot be computed scores 10.

| Criterion | Violation |
|---|---|
| F | max(0, ln(F / 3)) |
| b | max(0, ln(b / 0.05)) |
| stability ratio | max(0, ln(0.5 / ratio), ln(ratio / 2)) |
| central rate | max(0, ln(0.5 / c), ln(c / 8)) |
| DAN rate | max(0, ln(0.5 / d), ln(d / 10)) |
| KC rate | max(0, ln(k / 2)) |
| gradedness | max(0, ln(c_next / (3 c))) |
| reflex (a), when measured | max(0, ln(40 / max(1, lowest seed difference))) |
| reflex (b), when measured | max(0, ln(50 / max(1, mean difference))) |
| reflex (c), when measured | max(0, ln(0.5 / max(0.01, extended retention))) |

S is the sum of the violations.

Objective. `J = Σ_g (ln(max(r_g, 0.01) / target_g))²` over drive groups with placeholder targets (SPEC section 5 `bg.target.*`), from clamped R-screen rates. The targets are placeholders, so J only orders candidates.

Order key. Every cap, selection and ranking uses one total order, ascending in each field in turn: S; floor(J / `rest.j_bin` 0.25); parsimony |ln g_gaba| + |ln g_glu|; g_gaba; g_glu; sigma_th; optic_exemption; n_bg; w_bg. Every field is finite after flooring and capping, so the order is total. A scale pair is ordered by its best candidate.

1. Screen set. If the Camber map report has landed, take its R-screen passers and its six lowest non-passers by order key, add the (g_gaba, g_glu) grid neighbours of all of these, and keep the first 12 scale pairs by order key on the map's values. The map used the connection file's classes and layer A off, so it chooses where to look and qualifies nothing. If the report is absent when WP14 and WP17's driver are ready, take all 36 scale pairs. Each chosen pair runs at all 19 weights and three seeds under R-screen.
2. Reflex and long window. R-screen passers go through R-reflex and then R-long in order-key order, up to `rest.max_candidates` 20. Passers beyond the cap are recorded as `not tested (cap)`.
3. Rank. Candidates passing all three stages form the ranked list in order-key order. Its first three, or fewer if fewer exist, are the shortlist.
4. Tier 2. If the ranked list is empty, tier 2 runs automatically within `rest.tier2_cap_engine_hours` 265, on three scale pairs:
   - no pair passes R-screen: the three lowest pairs by order key;
   - pairs pass R-screen but none passes R-reflex: the three R-screen passers with the lowest total reflex violation, ties by order key;
   - pairs pass R-reflex but none passes R-long: the three lowest R-reflex passers by order key.

   Tier-2 passers go through steps 2 and 3.
5. Escalation. Step 5 is reached when tier 2 leaves the ranked list empty, or when the K1r and Q-rest fall-through of section 2.5 runs out on a tier-1 or tier-2 list. Then:
   - `docs/resting-candidates.md` records an escalation section with the closest-miss table and each candidate's failed step;
   - the coordinator asks Rolf whether to authorise tier 3, relax a named criterion, or stop;
   - the lowest candidate by order key may be written as `data/drive-dev-p2.yaml`, class development, so lanes can keep developing. It never qualifies anything.

   Rolf authorised tier 3 on 2026-09-16 (open question 6), so step 6 follows step 5. P2-partial-B does not hold while tier 3 runs; step 6 decides it (section 1.5). `data/drive-dev-p2.yaml` stays the development substrate for lanes during tier 3 (open question 35).
6. Tier 3 (WP24, then WP26). Sub-tiers 3a, 3b, 3c and 3d run in that order under the tier-3 rules below, each only when the one before ends empty.

`tests/test_rest_decision.py` (WP17, no engine) runs the decision code on constructed metric tables. It covers:

- silent and missing metrics;
- exact ties broken by the order key;
- J-bin ties;
- the 20-candidate cap;
- R3 all failing within `rest.r3_max`;
- R3 late at 12 hours;
- the T-to-C fall-through;
- a one-candidate shortlist exhausted;
- each tier-2 trigger;
- both escalation routes.

**Tier 3 (step 6).** A unit is one pair of P3 with one mechanism setting from the sub-tier's grid (section 2.2.4). The section 2.3 criteria, their parameters and the closest-miss score are unchanged. The unit's mechanism is in force in every candidate arm: R-screen, R-reflex (a), (b) and (c), and R-long. The matched bare reference of R-reflex (c) stays as section 2.3 defines it, with engine model `lif` and every scale 1 (open question 27).

- T0, feed-forward retention. Every unit runs the extended-mode candidate arm of R-reflex (c): background off, A and C on with `dopamine-v0.1`, ten seeds, sugar GRNs at 150 Hz, 2 s settle and 1 s per condition. (c) does not depend on the weight, so one run covers all 19 weights of the unit. The unit passes T0 when extended retention is at least `rest.ff_retention_min` 0.5.
  - Denominator. Extended retention is the unit's ten-seed mean MN9 difference divided by that of the extended bare-reference task in the same Camber job (section 6.5), so a lost job affects only its own units. Each T0 line stores the job id, that same-job bare mean and the global bare mean, which is the bare mean of the sub-tier's first T0 job in launch order. Retention values from different jobs are never compared as if they shared a denominator. Bare references build `lif` at scale 1 from one commit and are expected to agree bitwise across jobs, as the bare reference did across the Mac and Camber (WP17 report). When a job's per-seed bare differences are not equal to the first job's, every unit of that job is flagged `bare-mismatch`.
  - Recorded beside retention: the ten-seed mean background-off MN9 difference in Hz, and under 3a MN9's mean a_sfa over the scored second of the sugar condition, per seed, from `mechanism_traces` with MN9 in `trace_idx`. A unit whose background-off difference is below 50 Hz is flagged `t2-b-unreachable`. The flag is not a criterion, and admission ignores it (open question 41).
  - In 3a only, the 12 pairs of P3 with g_gaba ≤ 2 also run once with no mechanism. These baseline rows measure where scaling alone loses the reflex. They are recorded and are never units or candidates.
  - T0 comes before R-screen because (c) failed every measured candidate of tiers 1 and 2 and costs 60 brain s per unit, against R-screen's 684. Without caps the ranked list is the same in either order (open question 28).
- T1, R-screen. T0 passers are admitted in rounds.
  - Pairs are taken in order of parsimony |ln g_gaba| + |ln g_glu|, then g_gaba, then g_glu. Within a pair, passers are ordered by mechanism strength M descending, then by the sub-tier's parameter order. Round r admits the r-th passer of every pair that has one.
  - Admission stops at `tier3.t1_max_units` 40, or before the first unit that would lift the projected sub-tier cost above `tier3.cap_engine_hours` 400. The projection in engine-hours is (T0 brain s + admitted T1 brain s + 9,760) × `q_plan` 27 × ρ_mech / 3600. T0 brain s is the completed T0, with baseline rows and bare-reference tasks; it is already spent and still counts. 9,760 brain s is the T2 maximum: 20 candidates of 476 and four upstream bare references of 60 (section 6.5), counted whatever the number of candidates. ρ_mech is the B-mech value in the plan record. If T0 alone lifts the projection above 400, T1 admits no unit and the sub-tier ends with failed stage `R-screen`, reason `cap`.
  - Admitted units run R-screen at all 19 weights and three seeds. Units not admitted are recorded `not tested (cap)`.
  - As in section 2.3, two adjacent passing weights form a candidate at the lower weight, so one unit can give several candidates.
- T2, reflex and long window. Candidates in tier-3 order-key order, up to `rest.max_candidates` 20, run in one round: R-reflex (a) and (b), the upstream-mode arm of (c) against an upstream bare reference in the same job, and R-long. Upstream retention is recorded, as in section 2.3. Candidates beyond the cap are recorded `not tested (cap)`.
- Rank. Candidates that pass T0, R-screen, R-reflex (a) and (b), and R-long form the sub-tier's ranked list in tier-3 order-key order. Its first three, or fewer if fewer exist, are the shortlist. List and shortlist go to section 2.5 stages R3 onwards unchanged. R-reflex (a) and (b) are absolute rates with background on, and T0 is a ratio with background off, so passing T0 does not imply passing T2.

Tier-3 order key, ascending in each field in turn: S; floor(J / `rest.j_bin`); parsimony; M; g_gaba; g_glu; the sub-tier's parameters in order; w_bg.

- M is b_mv × tau_ms / 1000 in mV·s for 3a, U × tau_ms / 1000 in s for 3b, 1 / (`lif.v_0` − E_inh_mv) in 1/mV for 3c, and `g_gaba_kc` (dimensionless) for 3d. The key prefers the weaker mechanism; T1 admission tries the stronger one first.
- Parameter order: tau_ms then b_mv for 3a; scope (`non_sensory_excitatory` first), U, tau_ms for 3b; E_inh_mv for 3c; `g_gaba_kc`, then whether 3a is on (none first), then tau_ms and b_mv when 3a is on, for 3d.
- A unit without R-screen rates has no J and takes 0 in that field.
- Pair, parameters and weight identify a candidate, so the order is total.

Closest miss. Units and candidates are ordered by the deepest stage reached (T2, then T1, then T0), then by the tier-3 order key, with S summed over the criteria measured. A criterion the unit's deepest stage did not measure is left out of that S, while a measured metric that is missing or not computable still scores 10. The ranked list's order key keeps the S of section 2.6. The first is the sub-tier's closest miss.

Sub-tier end. A sub-tier ends empty, with its failed stage recorded, when:

- no unit passes T0 (`T0`);
- no admitted unit passes R-screen (`R-screen`);
- no candidate passes R-reflex (a) and (b) (`R-reflex`);
- candidates pass R-reflex (a) and (b) but none passes R-long (`R-long`);
- the section 2.5 K1r and Q-rest fall-through runs out on its ranked list (`Q-rest`).

An empty 3a starts 3b, an empty 3b starts 3c, and an empty 3c starts 3d; nothing else starts a sub-tier (open question 39, item 73). An empty 3d makes P2-partial-B hold. `docs/resting-candidates.md` then gains a tier-3 escalation section with each sub-tier's failed stage and closest-miss table, and the coordinator goes to Rolf. When a sub-tier ends empty and the coordinator asks, its closest miss may be written as `data/drive-dev-t3.yaml`, class development. Tier 3 never rewrites `data/drive-dev-p2.yaml`.

Flags, recorded per unit:

- `grid edge`: a T1 unit with no R-screen passer whose lowest-S adjacent weight pair is (1.55, 1.60) mV, with central seed-mean rate below the `rest.central_hz` floor at 1.60 mV. Recorded only; the weight grid is not extended (open question 36).
- `cbi-stiff` (section 2.2.4): the flagged evaluation's metrics count as not computable.
- `t2-b-unreachable` and `bare-mismatch` (T0): recorded only.

Records. Every tier-3 evaluation is development. Sub-tier X writes, under `validation/records/p2/`:

- `rest-T3X-plan.json`, committed before launch: units, pairs, grid, ρ_mech, job shapes and the cap projection. A plan whose ρ_mech is not the recorded B-mech value for its engine model is invalid, and no job launches from it, except 3d, which has no B-mech and stores ρ_mech 1.0 for the scale path.
- `rest-T3X-T0.json`, `rest-T3X-T1.json` and `rest-T3X-T2.json`;
- `rest-T3X-decision.json`: the ranked list and shortlist, or the failed stage, with the closest-miss table.

Each evaluation line carries the job id, commit, `code_scope`, platform, `engine_model` and mechanism setting.

A ranked-list row, the only input R3 and R4 read for a candidate (section 2.5), holds:

- `candidate_id`: WP19's tier-1 identifier (g_gaba, g_glu, sigma_th, optic_exemption, n_bg and w_bg joined by `-`), then `-`, the tag (`sfa`, `std` or `cbi`) and the block's values in key order without `mask_sha256`, for example `1.5-2.0-0.0-False-100-1.15-sfa-1.0-150.0-non_sensory`. A 3d identifier appends `-kc-<s>` with `s` = `str(float(g_gaba_kc))`, for example `1.0-4.0-0.0-False-100-1.15-kc-6.0` with no mechanism and `1.0-4.0-0.0-False-100-1.15-sfa-1.0-50.0-non_sensory-kc-6.0` with 3a. Each numeric value is written as `str(float(x))` except `n_bg`, which is `str(int(n_bg))`; a boolean is `True` or `False` and a scope its name, so a value read as `1` or `1.0` gives one identifier;
- `sub_tier`, `engine_model`, and `mechanisms`, the drive-file section with the unit's values and resolved `mask_sha256`;
- `g_gaba`, `g_glu`, `w_bg` (the candidate weight), `sigma_th`, `optic_exemption`, `n_bg` and the transmitter-rule `scope`;
- the T0 line: extended retention, same-job and global bare means, background-off difference, MN9 a_sfa under 3a, flags and job id;
- the T1 metrics of both pair weights per seed, and the T2 metrics: R-reflex (a) and (b) per seed, upstream retention and R-long per seed;
- S, J, the tier-3 order-key fields and the job ids.

`tests/test_rest_tier3_decision.py` (WP24, no engine) runs the tier-3 decision code on constructed tables. It covers:

- T0 at retention exactly 0.5 and just below;
- two T0 jobs whose bare means differ by 1 Hz, with a unit at the 0.5 edge in each, decided on its own job's denominator and flagged `bare-mismatch`;
- `t2-b-unreachable` recorded without changing admission;
- baseline rows, never admitted or ranked;
- admission rounds, the 40-unit cap, and the engine-hour projection with `q_plan` 27 at ρ_mech 1 and 1.5, and at a ρ_mech where T0 alone exceeds 400 (failed stage `R-screen`, reason `cap`);
- one ranked-list row per sub-tier, for which `engine_model_of`, `mechanisms_section` and `mechanisms_from_unit` round-trip the row, WP19's `ranked_candidates` and `make_drive` keep the section, and two rows that differ only in mechanism values get different identifiers;
- several candidates from one unit;
- the T2 cap of 20;
- ties on every field of the tier-3 order key;
- closest-miss depth ordering;
- each failed stage, including `Q-rest`;
- the 3a to 3b to 3c to 3d chain and P2-partial-B after 3d;
- a `cbi-stiff` evaluation scored as not computable, and a `grid edge` flag.

## 3. Visual path and closed-loop steering

### 3.1 Starting point

WP10 drove R1-6 with 300 Hz Poisson input on the bare substrate:

- R1-6 fired at 128 Hz full-field and at 26 to 32 Hz under a stripe. L1 followed at 10.5 Hz full-field and at 1.7 to 2.9 Hz under a stripe.
- Mi1 stayed at or below 0.03 Hz and Tm3 at 0.0 Hz. T4, T5, LC, MeTu, visual projection, TuBu, ER and LAL stayed essentially at zero.
- The steering difference was 0.0 Hz in all 18 corrected stripe conditions.
- Direct 500 Hz LAL drive moved the steering cells by 26.3, 16.5 and 15.3 Hz, so the output end works.
- One leak: whole-lamina full-field drive fired DNa02_L at 5.5, 4.0 and 3.0 Hz, left side only.

Item 68 reads this as a substrate problem, not a question of where the encoder injects.

On a rest substrate with histamine-signed photoreceptors, Phase 2 presents what Buridan presents: dark vertical bars on a bright wall. The expected mechanism:

- In the dark at rest, optic neurons fire near their group rate and photoreceptors are silent.
- Ambient light drives R1-6, which through histamine inhibit L1, L2 and L3.
- A dark bar lifts that inhibition in the columns it covers, so L1 and L2 there return towards their resting rate.
- L2 is cholinergic, so the OFF signal continues with positive sign into Tm1, Tm2, Tm4 and Tm9 and on to T5 and the lobula.
- L1 is glutamatergic, so a dark bar raises L1 and suppresses Mi1 and Tm3 in those columns, the correct ON-pathway sign for darkness.

V1 measures whether this reaches LAL and DNa02. The LIF network has no temporal filtering, so T4 and T5 integrate contrast rather than compute motion, and the model steers on bar position (section 9.1, risk 3).

### 3.2 Photoreceptor encoder (`behaviour/encoder.py`, mode `photoreceptors`)

Injection site. The `R1_6` population of `populations-v0.2.yaml` (7,932 neurons in the engine), in extended mode, with per-neuron rates written each chunk through `set_input_rates`. R7 and R8 get no drive in v0.2: the arena is achromatic, and R1-6 carry luminance (open question 10). R1_6 enters the engine's extended set only under the section 8.1 topology rule.

Retinotopy, the WP10 rule, implemented by WP14 in `substrate/retinotopy.py`:

- Within each eye (annotation `side`), R1-6 neurons are ranked by the z coordinate of their lamina terminal (`pos_z`; anterior is smaller z).
- Rank r of n maps to fly-relative azimuth φ = (r + 0.5) / n × 150° in the right eye and −(r + 0.5) / n × 150° in the left eye, with 0° straight ahead.
- The table of root id and azimuth goes into `populations-v0.2.yaml` with its SHA-256.

Luminance. The wall is bright (L = 1) except where a bar covers it. Bar k (stripe A, stripe B, and the distractor while on) has fly-relative centre a_k, angular width w_k computed exactly from its edge points (SPEC section 3.5), and contrast c_k in [0, 1]. Each photoreceptor sees through a Gaussian acceptance of standard deviation σ = `vis.pr_acceptance_deg`:

```
u_k(φ) = ½ [ erf((d(φ, a_k) + w_k/2) / (√2 σ)) − erf((d(φ, a_k) − w_k/2) / (√2 σ)) ]
L(φ)   = max(0, 1 − Σ_k c_k u_k(φ))
rate_i = min(vis.r_max, r_dark + (r_light − r_dark) × L(φ_i))
```

- d is the wrapped angular difference.
- `r_light` comes from `visual-v0.2.yaml`, set by V-cal.
- `r_dark` is `vis.pr_rate_dark_hz` 0.
- Rates are Poisson input rates in extended mode, not photoreceptor firing rates. WP10 measured 128 Hz firing at 300 Hz input.

Distractor. The Phase 1 definition is unchanged: a bar at a fixed arena azimuth, width `arena.stripe_width`, contrast switching between 0 and `distractor.contrast` at `flicker_hz` with 50 percent duty. On the bright wall it is a flickering dark bar.

Controls. `stripes: false` and `encoder: "off"` both give uniform ambient light (L = 1 at every photoreceptor). The rest point is the same in all three Buridan arms, and the controls differ only in stimulus content. Darkness exists only as `stimulus: "dark"` in open-loop blocks and spontaneous probes (section 8.1).

TuBu mode stays as the section 3.7 fallback. Buridan and `open_loop_steering` probes take `inject_at` from the pinned `visual-v0.2.yaml` unless the file sets it.

### 3.3 Stage populations and propagated retinotopy

`populations-v0.2.yaml` holds everything in v0.1 plus the WP10 overlay types, each split by side where the annotation has side labels:

- R1_6, L1, L2, L3, L4, L5;
- Mi1, Mi4, Mi9, Tm1, Tm2, Tm3, Tm4, Tm9;
- T4 (a to d union), T5 (a to d union);
- LC10 (a to f union), LC_all, LPLC, MeTu, visual_projection.

`DA_exposed` is a derived population computed when the registry is built (section 4.2).

Column subsets. A dark 5° bar covers about 3 percent of an eye's columns, so a side-wide mean would dilute a real lamina signal about 30-fold. WP14 propagates azimuth by connectivity. For a neuron n, az(n) is the synapse-weighted circular mean of the azimuths of its presynaptic partners that already have one, and its spread is their circular standard deviation. Types are assigned in this order:

1. R1-6 (the rank rule);
2. L1 to L5;
3. Mi1, Mi4, Mi9, Tm1, Tm2, Tm3, Tm4, Tm9;
4. T4, T5;
5. LC10.

A type gets column subsets only when its median spread is at most `vis.max_column_spread_deg` 20°. The column subset for a bar at azimuth a is the type's neurons on the bar's side with |d(az, a)| ≤ `vis.column_halfwidth_deg` 10°, computed at probe start and recorded. Types that fail the spread test use side-wide populations. The census reports each type's median spread and the L2 → Tm1, Tm2, Tm4 and Tm9 synapse counts.

### 3.4 Visual-path entries and the visual configuration

V fixtures live in `data/experiments/p2/vpath-*.json` and run on the configured rest substrate, wild type, vehicle, A and C on. They pin `behaviour_version: "base-v0.2"` (section 3.5), because no steering configuration exists yet. V-cal passes each candidate rate as a declared grid point. V0 is class canonical; V1, V2, V3 and V-cal are matching-layers.

V0 (verification, no engine) has three parts:

- (a) Per eye, R1-6 azimuth is strictly monotone in z rank and covers (0°, 150°) or (−150°, 0°).
- (b) Per eye, propagated L2 azimuth has Spearman ρ ≥ 0.9 against the rank rule applied to L2's own z positions.
- (c) On a constructed heading and bar set, encoder rates equal the section 3.2 formula to relative error 1e-12.

V1 (consistency) measures propagation:

- Probes: ten seeds, one `open_loop_steering` probe with blocks in the order ambient, stripe at +45°, ambient, stripe at −45°, each `transition_s` 1 plus `dwell_s` 3.
- Differences: for each stage population (column subset where available), the mean rate in each stripe block minus that in the preceding ambient block, ipsilateral and contralateral.
- Steering: `Δsteer = (r_R − r_L)(+45°) − (r_R − r_L)(−45°)`.
- Intervals: bootstrap 95 percent over seeds from the ANALYSIS stream. A stage is carried when its interval excludes zero.

V1 passes when both of these hold:

- the Δsteer interval excludes zero and |mean Δsteer| ≥ `vpath.min_delta_hz` 0.5 Hz;
- a carried population exists at each depth: retina (R1_6), lamina (L1 or L2), medulla (any of Mi1, Tm1, Tm2, Tm3, Tm4, Tm9), lobula or lobula plate (T5, LC10, LC_all, LPLC or MeTu), central input (TuBu, visual_projection or LAL_neurons), and steering.

The table of carried stages is always recorded, and a failing V1 shows where the chain breaks.

V2 (consistency, recorded): in the stripe blocks, the L1 column subset rises and the Mi1 column subset does not.

V3 (consistency): ambient stability. Three seeds, `stimulus: ambient`, 2 s settle plus 10 s. The R-screen rows of section 2.3 hold except gradedness, with no ignition. The raw ambient `r_R − r_L` is recorded.

V-cal (calibration):

- Stage 1: for `r_light` in {50, 100, 150, 300} Hz, run V3, then three-seed V1 wherever V3 passed.
- Stage 2: if no rate passes V3, run the same at {25, 10} Hz.
- Selection: the lowest rate that passes V3 and three-seed V1, and then passes V1 at ten seeds.
- No selection with a V3 pass: V1 is recorded as failed at the V3-passing rate with the largest |mean Δsteer|, and section 3.7 applies.
- No V3 pass at any rate: V3 is recorded as failed, and section 3.7 applies.

On selection, WP18 commits `data/visual-v0.2.yaml` with `inject_at: photoreceptors`, `r_light`, `r_dark`, the acceptance angle, and `provenance` holding the V-cal record SHA-256. Under the freeze protocol, V1 and V3 then execute against that configuration and must pass.

`diagnostics/visual_path.py` v2 is the WP10 driver reused for R3 (development). It adds the dark and ambient conditions, histamine scales, the rest substrate, stage populations, column subsets and V1 statistics. The V entries themselves run through the orchestrator's `open_loop_steering` assay, so they get a class and a binding.

### 3.5 Steering: bias, initial heading, sign check, K3r, 4.1r and 4.2r

Order. Every step here runs on the configured drive, dopamine and visual files. Bias and sign are measured before any gain is chosen, and K3r varies only `K_steer`, so the configuration committed afterwards is exactly the controller K3r scored. `r_light` is not a K3r variable: it sets the photoreceptor gain and the ambient rest point, and V-cal has already chosen the lowest rate that keeps rest and carries the signal.

Steering configuration. Three files hold every runtime steering value, all under the section 2.5 freeze protocol:

- `data/behaviour-base-v0.2.yaml` (WP15) holds the values that exist before any steering calibration. These are `v_fwd_mm_s` 15.251167474671366 (the calibration half's median walking speed from ingestion), `step_min_mm` 0.8, `r_max_hz` 300 and the three split SHA-256s, all copied from `behaviour-v0.1.yaml`. Its `provenance` names that file's blob id. A file pinning `behaviour_version: "base-v0.2"` may contain only open-loop and spontaneous probes, except the K3r fixtures below.
- `data/experiments/p2/k3r.json` and `k3r-tubu.json` (WP20) are calibration fixtures committed after the bias and sign check. They are the only files that may run Buridan probes on the `base-v0.2` pin. Each one pins the committed visual file (photoreceptor for `k3r.json`, TuBu for `k3r-tubu.json`). It carries `sign_steer`, `bias_hz` and that visual file's blob id as calibration metadata, and declares `K_steer` as its only grid. The controller each probe runs is then fully determined: sign and bias from the metadata, K from the grid point, and runtime values from the base file.
- `data/behaviour-v0.2.yaml` (WP20) holds the base values, `controller`, `sign_steer`, `bias_hz`, `K_steer` and the visual file's blob id. Its `provenance` holds the base file's blob id, the bias, sign-check and K3r record SHA-256s, and Camber job ids. `controller` is `closed_loop` after K3r or K3r-T, with every field set, and `open_loop` in section 3.7 step 3, with `sign_steer` and `K_steer` null.

Section 8.1 gives the loader rules that stop a steering file from being used with the wrong visual file or probe type.

Bias (calibration). `bias_hz` is the ten-seed mean of `r_R − r_L` over a 10 s `stimulus: ambient` open-loop probe pinning `base-v0.2`. Phase 2 arenas compute:

```
omega = sign_steer × K_steer × ((r_R − r_L) − bias_hz)
```

This removes a constant turn from the WP10 left-side DNa02 leak or any rest-substrate asymmetry. The bias-dominated detector (section 9.2) watches it. A constant offset changes neither the `steer_gain` slope nor any difference between two blocks, so the sign check, 4.1r and `distractor_capture_hz` do not depend on the bias; it enters omega and the detector only.

Initial heading. `arena.initial_heading` is `random` for schema 1.3 files: h₀ is uniform on (−180°, 180°], the first draw of the probe's BEHAVIOUR stream at `arena.reset`, and position stays (0, 0). Arms are not in the stream key, so paired arms start from the same heading. This removes the item 42 artefact that review r8 traced to the start facing stripe A plus the edge reversal (open question 3).

Metrics (`behaviour/metrics.py`):

- `steer_gain` (Hz per degree): per seed, the least-squares slope of bias-corrected block-mean `r_R − r_L` against fly-relative azimuth over stripe blocks with |azimuth| ≤ 60°.
- `fixation_retention`: per seed, the window-mode fixation index over the distractor episode [onset, onset + duration) minus that over [0, onset). With the default 5 s onset the pre-episode window is short, and the interval shows it.
- `distractor_capture_hz`: per seed, bias-corrected `r_R − r_L` in a 4 s block with the stripe at −45° and the distractor flickering at +90°, minus the same block with the distractor off.

Sign check (4.1r-sign, calibration). Seeds 1 to 3, dark-stripe blocks at the 13 azimuths {−150, −120, −90, −60, −45, −30, 0, 30, 45, 60, 90, 120, 150}°, each `transition_s` 1 plus `dwell_s` 2 (39 s), pinning `base-v0.2`. `sign_steer` is +1 when the three-seed `steer_gain` interval lies above zero and −1 when it lies below. A stripe on the right must produce a turn towards it, because Buridan flies approach dark bars. An interval that includes zero is a flat sign check, and section 3.7 applies.

K3r (calibration, fixture `k3r.json`). Calibration half of `brembs-split.json`, window mode, wild type, vehicle, stripes, no distractor, 20 s Buridan probes, with the sign and bias the fixture carries:

- Grid: `K_steer` {1, 2, 4, 8, 16}.
- Objective: the SPEC section 3.5 objective `((FI_m − FI_c) / IQR_FI_c)² + ((dev_m − dev_c) / IQR_dev_c)²`.
- Camber proposes: all five values at five seeds, as development.
- The Mac disposes: the three lowest-objective values rerun at seeds 1 to 10, and the Mac objective chooses, ties to the lower `K_steer`.

WP20 then commits `data/behaviour-v0.2.yaml` with `controller: closed_loop` and the chosen `K_steer`.

4.1r (matching-layers consistency). The sign-check protocol at seeds 1 to 10 on the committed behaviour configuration. It passes when the `steer_gain` interval excludes zero with the committed sign, and the bias-corrected difference between the +45° and −45° blocks is at least 0.5 Hz in magnitude with an interval that excludes zero.

4.2r (matching-layers consistency). Seeds 1 to 10, random initial heading. Wild-type median fixation index with stripes and encoder on exceeds both controls by at least 0.2, and median stripe deviation is lower than both.

4.4r to 4.8r carry the Phase 1 definitions onto the rest substrate:

- 4.4r to 4.7r are predictions, computed from the P-screen (development) and from the canonical prediction files where a genotype is selected (section 4.4).
- 4.8r is a sensitivity entry on Camber, class development. It tests the 4.2r conclusion under three within-eye permutations of the azimuth table, five jitter streams, `sigma_h` at 0 and 20, `v_fwd` at half and double, and histamine off (photoreceptor rows at their connection-file sign).

### 3.6 Attention assays

The closed-loop attention readouts are fixation index, stripe deviation, walk count, distractor switch rate (SPEC section 3.5) and fixation retention, all from 20 s Buridan probes with the distractor.

The open-loop readouts are `steer_gain` and `distractor_capture_hz`. The open-loop probe used by `acceptance-p2-openloop.json` and 4.11 has three parts, 47 s in total:

1. the 13 sign-check blocks (39 s);
2. a 4 s capture block with the distractor off;
3. a 4 s capture block with the distractor on.

### 3.7 Fallback chain and visual status

1. Photoreceptor failure. Any of these counts: a V-cal outcome without a selected rate, V1 or V3 failing on the committed visual bytes, a flat sign check, a 4.1r failure, or a 4.2r failure. The chain then moves once to the next candidate in rank order that passes R3, screening further ranked candidates within `rest.r3_max` if needed. That candidate goes through the WP19 chain (K1r, drive commit, K2r, Q-rest) and then V-cal and section 3.5 again. If no such candidate exists, or step 1 has already been used, go to step 2.
2. TuBu path, on the drive configuration in force:
   - VT-cal (calibration, pinning `base-v0.2`): V1 with the depth requirement restricted to central input and steering, under the TuBu encoder at `r_vis_max` in {40, 70, 100, 150, 280} Hz and `sigma_vis` 20. Three seeds per value, then ten at the lowest passing value. On a pass, WP20 commits `visual-v0.2.yaml` with `inject_at: TuBu`, `r_vis_max` and `sigma_vis`, and V1-T executes on it.
   - Then bias-T, 4.1r-T-sign, the `k3r-tubu.json` commit, K3r-T over `K_steer` {1, 2, 4, 8, 16}, the behaviour commit (`controller: closed_loop`), 4.1r-T and 4.2r-T, with the section 3.5 definitions.

   If all pass, the visual status is "TuBu closed loop" (open question 12).
3. Open loop. If the TuBu path fails at any step, the visual status is "open loop". Step 3 can be reached straight after V-cal and VT-cal have both failed, before any K3r has run. The encoder is photoreceptors when V3 passed at any rate, at the V3-passing rate with the largest |mean Δsteer|. Otherwise it is TuBu at the VT-cal value with the largest |mean Δsteer|. WP20 then does these in order:
   1. commits `visual-v0.2.yaml` for that encoder, unless those exact bytes are already committed;
   2. executes and records V1 and V3 (or V1-T) on those bytes, pinning `base-v0.2`;
   3. measures the bias under that encoder;
   4. commits `behaviour-v0.2.yaml` with `controller: open_loop`, that bias, null `sign_steer` and `K_steer`, and the visual blob id, replacing any earlier bytes.

   The open-loop acceptance file and the pharmacology fixtures pin both files. The 500 Hz LAL drive stays a diagnostic.

If step 1 is never triggered, the visual status is "photoreceptor closed loop". `validation/records/p2/visual-status.json` records the status, the step reached and each failure. Every change of encoder is a new configuration commit, so earlier evidence stays with earlier bytes. WP18 owns the V-cal commit of the visual file, and WP20 owns every visual and behaviour commit made under steps 2 and 3.

### 3.8 Holdout comparison

4.3r (empirical, holdout) runs once, in WP22, after integration:

1. Every WP is merged at an integration commit, and reviews r13 to r16 have no open blocker or major finding.
2. Status is regenerated at that commit.
3. `scripts/holdout_ready.py` (WP22) verifies three things: every required-passed entry of section 5.2 for the recorded visual status, except the holdout, is passed and valid at HEAD; the tree is clean; `holdout_half_sha256` matches `brembs-split.json`.
4. 4.3r executes: ten fresh seeds 11 to 20, with the model's wild-type median fixation index and stripe deviation compared against the interquartile range of the 64 holdout flies' window-mode values. Under "TuBu closed loop" the same entry is 4.3r-T. Under "open loop" no holdout runs.
5. B2-P2 and the acceptance pair run on a commit whose code scope and configuration blob ids equal the integration commit's.

Ownership and one-use handling. WP22 owns `validation/level4_holdout.py` (4.3r, 4.3r-T and 4.3r-replay), the fixtures `data/experiments/p2/holdout-p2.json` and `holdout-p2-tubu.json`, and `scripts/holdout_ready.py`. These entries are registered with `one_use: true`. `scripts/run_validation.py` (WP16) never executes a one-use entry during ordinary regeneration: it carries the existing record forward and recomputes only its validity. It executes one only under `--holdout <entry>`, and only when both of these hold:

- `holdout_ready.py` passes at HEAD in the same invocation;
- `validation/status.json` holds no earlier execution of 4.3r or 4.3r-T.

`--holdout 4.3r-replay` instead requires an existing 4.3r or 4.3r-T execution, a clean tree, configuration blob ids equal to that execution's, and no earlier replay.

That execution spends the holdout. After it:

- A code-only fix (changes to `src/`, `scripts/` or `uv.lock`, no configuration byte) allows one exact replay at the new code with the same configuration and seeds, recorded as `4.3r-replay`. The holdout keeps its outcome only if the replay's per-seed metrics are bitwise identical to the original's. Otherwise the holdout becomes `spent-invalidated`, and P2 is unreachable.
- Any configuration change is a scientific correction. The holdout becomes `spent-invalidated`, any new comparison is `4.3r-dev` (development, never passing), and P2 is unreachable.
- Old executions never receive new identity hashes.

## 4. Pharmacology and ADHD manipulations

### 4.1 What changes

On the bare substrate, dopamine moved thresholds and gains but almost nothing fired to express it: the 3.8 ablation gave a `DN_all` difference of exactly 0 in every cell, and 3.6 gave 0 for fumin. On the rest substrate, exposed neurons fire at rest, so a tonic dopamine change should change rates and, through the visual path, steering. Phase 2 keeps the layer A and C equations, the drugs and the pharmacokinetics. It changes the dopamine configuration (section 2.5), the manipulation set and the readouts. 3.10r shows whether modulation reaches spikes.

### 4.2 Manipulations and named genotypes

Every manipulation is an existing schema manipulation (SPEC section 6.1). Schema 1.3 adds seven named expansions to `schema/named.py`, and the Phase 1 four keep their definitions.

| Named genotype | Expansion | Family | Reading |
|---|---|---|---|
| `wild_type` | none | reference | |
| `fumin` | `scale_dat all 0` | transporter | DAT loss (Phase 1) |
| `dat_half` | `scale_dat all 0.5` | transporter | partial DAT loss, model state |
| `dopamine_depleted` | `scale_release 0.5` | synthesis and release | halved release (Phase 1) |
| `dop1r1_null` | `scale_receptor D1 all 0` | receptor | Dop1R1 null (Phase 1) |
| `dop2r_null` | `scale_receptor D2 all 0` | receptor | D2-like receptor null |
| `dan_autoreceptor_null` | `scale_receptor D2 DAN 0`, `scale_receptor D2 CX_DAN 0` | receptor, signalling | removes D2 autoreceptor terms on dopamine neurons (receptor map PAM, PPL1, PPL2 r2 1.0; CX_DAN r2 1) |
| `er_dop1r1_kd` | `scale_receptor D1 ER 0` | receptor, circuit | ring-neuron Dop1R1 loss |
| `pam_silenced` | `silence PAM` | circuit | |
| `cx_dan_silenced` | `silence CX_DAN` | circuit | |
| `dfb_silenced` | `silence dFB` | circuit | |

Interventions are the two supported drugs: methylphenidate (transporter block) and 3-iodotyrosine (release reduction, `drug.3iy.EC50` 10 µM brain, a placeholder). Methylphenidate is the intervention for genotypes with low dopamine or low dopamine signalling. 3-iodotyrosine is the intervention for excess extracellular dopamine (`fumin`, `dat_half`). Circuit interventions (`activate`, `scale_gain`, `shift_threshold`) stay available through the schema, but Phase 2 runs none as named arms.

`DA_exposed` (`registry/derived.py`, WP15) contains every neuron with a nonzero exposure weight in at least one compartment and a nonzero receptor weight (r1, r2 or rq) in `receptors-v0.1.yaml`. Its size and root-id SHA-256 go into the manifest.

### 4.3 Matched arms

Within a file, arms share seeds, phase list, assay parameters and substrate. Only genotype and drug names differ, plus the overridable flags in ablation files (SPEC section 6.1). Food concentration is matched phase by phase, so methylphenidate arms and 3-iodotyrosine arms live in separate files, each with its own vehicle arm at the same `c_food_mm`.

Every screen and prediction file uses this protocol:

1. a 20 s Buridan baseline probe with the distractor;
2. `dose` (drug or vehicle);
3. a two-hour `wait`;
4. a 20 s Buridan test probe with the distractor.

Genotypes apply before the first probe and persist. Contrasts are paired by seed. Arms are not in the stream key, so paired arms share Brian2 seeds, initial heading and arena noise.

WP21 writes every screen, prediction and ablation file in two forms, `-buridan` with the 20 s Buridan probes above and `-openloop` with each Buridan probe replaced by the section 3.6 open-loop probe. The form matching the visual status runs; "closed loop" in section 6 means either closed-loop status.

### 4.4 Stages

P-screen (development, Camber, WP21). It runs after the behaviour configuration is committed and 4.2r (or 4.2r-T) has executed, or after the open-loop status is recorded.

- `pharm-screen-mph.json`: all eleven genotypes × {vehicle, methylphenidate 0.5 mM}, seeds 1 to 10.
- `pharm-screen-3iy.json`: wild type, `fumin` and `dat_half` × {vehicle, 3-iodotyrosine 3 mM}, seeds 1 to 10.

All section 4.5 readouts are recorded. The P-screen is development, so it supplies 4.4r to 4.7r and 4.9 as recorded predictions only.

Selection. Genotypes other than wild type and fumin qualify when at least one impairment contrast on fixation index, switch rate or fixation retention has status "emerged" (section 4.6). Under open loop, `steer_gain` and `distractor_capture_hz` take that role. Qualifying genotypes are ranked by their largest `|mean| / interval half-width`, ties by name, and up to three are selected. Fumin is always included because the acceptance file needs it.

Canonical predictions (matching-layers, WP21):

- `pharm-mph.json`: wild type, fumin and the selected genotypes × {vehicle, methylphenidate 0.5 mM}, seeds 1 to 10.
- `pharm-3iy.json`: wild type, fumin, and `dat_half` when selected × {vehicle, 3-iodotyrosine 3 mM}, seeds 1 to 10.

These give 4.10 per genotype.

4.11 (Camber, development): the section 3.6 open-loop probe for wild type, fumin and the selected genotypes, vehicle arm only, seeds 1 to 10. It runs only under a closed-loop status; under open loop, the P-screen's vehicle arms already carry these readouts, and 4.11 is read from them.

Neural entries (section 5.3): 3.2r (fumin), 3.3r (dose series), 3.4r (methylphenidate on fumin), 3.5r (3-iodotyrosine), 3.6r, 3.8r and 3.10r (coupling). 3.9r (receptor-constant sensitivity) runs on Camber as development. The fixtures of 3.2r to 3.6r, 3.10r and 3.9r use dark `spontaneous` probes. They measure dopamine and rates without visual input, so they run before the visual status is known. 3.8r runs after the behaviour commit in the form matching the visual status.

### 4.5 Readouts

Behavioural, per seed and probe: fixation index, stripe deviation, walk count, distractor switch rate with its invalid-window count, and `fixation_retention`. Open-loop files add `steer_gain` and `distractor_capture_hz`.

Neural, per seed and probe: mean compartment dopamine over innervated compartments; the mean per-neuron rate of `DA_exposed`, PAM, PPL1, CX_DAN, KC, MBON, ER, EPG, dFB, TuBu, `steering_L`, `steering_R` and `DN_all`; transporter occupancy and brain drug concentration.

"Impaired attention" means, against wild-type vehicle on the test probe: a lower fixation index, a higher stripe deviation, a higher distractor switch rate, or a lower fixation retention. In open loop it means a smaller `steer_gain` magnitude or a larger `distractor_capture_hz` towards the distractor.

### 4.6 Contrasts and status words

Every contrast is a paired difference over seeds. Its bootstrap 95 percent interval uses `pred.bootstrap_n` 10,000 resamples of seeds from the ANALYSIS stream, with seeds resampled jointly across arms.

| Metric | Minimum effect | Parameter |
|---|---|---|
| fixation index, fixation retention | 0.05 | `pred.fi_min_effect` |
| stripe deviation | 5 deg | `pred.dev_min_effect` |
| distractor switch rate | 0.1 | `pred.switch_min_effect` |
| `DA_exposed` and other per-neuron rates | 0.1 Hz | `pred.rate_min_effect` |
| `steer_gain` | 0.002 Hz/deg | `pred.steer_gain_min_effect` |
| `distractor_capture_hz` | 0.2 Hz | `pred.capture_min_effect` |

Impairment contrasts compare a genotype with wild type, vehicle arms, on the test probe:

- "emerged": the interval excludes zero in the impairing direction and |mean| ≥ the minimum effect;
- "opposite": the same, in the other direction;
- "none": the interval lies inside ± the minimum effect;
- "inconclusive": otherwise.

Intervention contrasts compare drug with vehicle within a genotype whose impairment emerged. The rescue index is `RI = (g_drug − g_vehicle) / (wt_vehicle − g_vehicle)`, from arm means, with its interval from the same joint bootstrap:

- "rescued": the drug interval excludes zero in the restoring direction and the RI interval lies above 0.5;
- "partial": the drug interval excludes zero in the restoring direction, and "rescued" does not hold;
- "worsened": the drug interval excludes zero in the impairing direction;
- "none": otherwise.

In wild type and in genotypes without emerged impairment, the drug contrast uses the impairment words against that genotype's vehicle arm. Interactions carry only their interval.

Multiple comparisons. No correction is applied. Every contrast computed is reported, and each table states its contrast count and how many "emerged" or "opposite" statuses 5 percent of that count would give by chance. The clause 7 contrasts are the pre-registered headline; everything else is exploratory, and the results say so.

### 4.7 If modulation does not reach spikes

If 3.10r fails, coupling is "failed", P2 is unreachable, and section 1.5 still sets the outcome. WP21 reports 3.9r's smallest change within the SPEC section 5 ranges of `gamma_*`, `dV_*`, `Kd_D1` and `Kd_D2` that makes the 3.10r interval exclude zero. No constant changes without Rolf.

## 5. Validation deltas

### 5.1 Binding rule

Declared inputs. Every Phase 2 entry and calibration stage declares, in its definition, the data files and fixtures it reads. Its identity block (`validation/binding.py`, `IdentityBlock`) stores:

- `code_scope`: one hash of git blob ids of `src/`, `scripts/` and `uv.lock` (HEAD blobs when clean, working blobs of tracked and untracked non-ignored files when dirty, prefix `git:`). This is the reviewed `code_hash` of SPEC item 78 with `data/` removed.
- `inputs`: a map from each declared or logged path to its blob id.
- `provenance_hash` (Phase 1), which covers `.cache/`.
- `run_code_scope`: `code_scope` computed at launch (item 73). This closes the r11 finding that the commit was recorded at aggregation.
- `overrides_hash`: SHA-256 of the canonical JSON of `FLYONENOMICS_PARAM_OVERRIDES_JSON`, or empty. This closes the r11 finding that overrides were missing.
- `platform`: `platform.system().lower()` and `platform.machine()` joined by a hyphen.
- `substrate_id`: `bare`, `rest:<16 hex>` or `rest-<tag>:<16 hex>` (section 2.5).
- `engine_model`: `lif`, `lif+sfa`, `lif+std` or `lif+cbi`, read back from the built engine with `engine_model()`, never copied from a configuration file.
- `mechanisms`: the resolved mechanism block (its values and `mask_sha256`), or null.
- The Phase 1 layer flags, protocol hash and machine identifier.

`drive_version` is null when `background: false`, which closes the r11 finding that background-off manifests wrote v0.1.

Dependency log. Every read of a file under `data/` or `tests/fixtures/` goes through `io.py` (WP16): `read_text`, `read_bytes`, `read_yaml`, `read_json`, `read_parquet` (pyarrow), `load_npy`. Each call appends the repository-relative path to the process's dependency log. Worker processes write `deps-<pid>.json` into their run or entry directory at each flush and at exit, and the parent merges them. The entry's `inputs` is the union of its declarations and its merged log:

- A logged path the entry did not declare demotes it to development with reason `undeclared input`.
- If a process the entry started leaves no log, `inputs` falls back to the tree ids of all of `data/` and `tests/fixtures/`, and the entry is flagged `conservative binding`.

Static check. 0.9r scans `src/` and `scripts/` with `ast` for direct file reads outside `io.py`. It looks for builtin `open` or `Path.open` in a read mode, `Path.read_text`, `Path.read_bytes`, `pandas.read_parquet`, `pyarrow.parquet.read_table`, `pyarrow.parquet.ParquetFile`, `numpy.load`, and `yaml` or `json` loads from file objects. Each hit fails unless `tests/fixtures/io-allowlist.json` lists it with a reason. The allowlist is only for reads under `runs/`, `.cache/` and temporary paths.

Validity. A run does not compare one run-wide hash. For each entry it quotes, it computes its own `code_scope` once and the blob id, in its own tree, of every path in that entry's `inputs`. The entry is valid for the run when all of these hold:

- the Phase 1 class rule of SPEC section 7 holds;
- `code_scope` is equal, or both sides lack it and the Phase 1 `code_commit` rule holds;
- every input blob id is equal;
- the entry's `run_code_scope` equals its `code_scope`;
- `overrides_hash` is empty, or the entry declares `grid: true` and the override is one of its declared grid points (V-cal, VT-cal, K3r, K3r-T, 3.9r, 4.8r);
- for matching-layers and run-bound entries, `substrate_id`, `engine_model` and the layer flags are equal;
- the entry's own `substrate_id` and `engine_model` agree: `bare` and `rest:` with `lif`, and `rest-sfa:`, `rest-std:` and `rest-cbi:` with `lif+sfa`, `lif+std` and `lif+cbi`. Sub-tier 3d does not add a substrate tag: a 3d unit with no mechanism stays `rest:` / `lif`, and a 3d unit with 3a stays `rest-sfa:` / `lif+sfa`. The ranked-list `candidate_id` gains `-kc-<s>` (section 2.6).

Older identity blocks and schemas (the rule of open question 22, extended to mechanisms):

- An identity block or manifest without `engine_model`, which is every one written before WP24, reads as `lif` with `mechanisms` null. It stays valid for a `lif` run under the rules above and is never valid for a run with a mechanism.
- Schema 1.2 rejects a drive pin whose file has a mechanism on. Schema 1.3 with `background: false` rejects one too, except in the section 8.1 feed-forward fixture.
- A checkout from before WP24 does not know the `mechanisms` section and would run `lif` with such a file. Its `substrate_id` would be `rest:<16 hex>`, which never equals a WP24 run's `rest-<tag>:<16 hex>`, and its `code_scope` differs, so none of its records binds to a mechanism run (open question 40).

Consequences:

- Commits that touch only documents, evidence or data the entry does not read leave it valid.
- A change to `src/`, `scripts/` or `uv.lock` stales every entry, which is re-executed, never relabelled.
- Phase 1 entries without `code_scope` keep the commit rule (WP11).
- `qualification_of(component, run)` in `validation/binding.py` answers qualification from these rules. The runner uses it where Phase 1 read a record's `qualified` flag, and v0.1 files keep their flags.

### 5.2 Component map

Rows for every visual status:

| Component | Required passed | Required recorded |
|---|---|---|
| engine | 0.1, 0.2, 0.3, 0.4, 0.7, 0.8, 0.9r, 0.10, 0.11 (when `sigma_th` > 0), 0.12, 0.13, 0.14, 0.15, 0.16 (when `lif+sfa` is in force), 0.17 (when `lif+std` is in force), 0.18 (when `lif+cbi` is in force), 1.0, 1.1 | 1.2 if the archive is present; B-mech for the engine model in force (section 6.5) |
| registry | inventory, label and precedence checks on `populations-v0.2`; the census check inside 0.10 | completeness; sign-disagreement list |
| rest substrate | 3.1r-alg, 3.1br, 2.3r, 2.7r, 2.6r, 2.2r, 1.4r, 1.4r-ff, 2.4r | 2.1r, 1.3r, 2.5r, R1 to R4 and K1r records; the tier-3 records of the candidate's sub-tier when it came from tier 3 |
| neuromodulation, A and C on | 0.5, 3.1br, 3.2r, 3.3r, 3.4r, 3.5r, 3.7 | 3.1r (K2r record), 3.6r, 3.8r, 3.10r (passed for P2) |

Rows by visual status:

| Visual status | Visual path, passed | Visual path, recorded | Behaviour, passed | Behaviour, recorded |
|---|---|---|---|---|
| photoreceptor closed loop | V0, V1, V3 | V2, V-cal | 4.0, 4.0b, 4.0c, 4.1r, 4.2r | bias, 4.1r-sign, K3r, 4.3r (passed for P2) |
| TuBu closed loop | V0, V1-T | V-cal, V1 and V3 as executed, VT-cal, visual-status record | 4.0, 4.0b, 4.0c, 4.1r-T, 4.2r-T | bias-T, 4.1r-T-sign, K3r-T, 4.3r-T |
| open loop | V0 | V-cal, VT-cal and V1, V1-T or V3 as executed on the final bytes, visual-status record | 4.0, 4.0b, 4.0c | bias under the open-loop encoder; 4.1r or 4.1r-T as executed; `steer_gain` and `distractor_capture_hz` per arm |

Not required under any status, and reported in the results: 3.9r, 4.4r to 4.8r, 4.9, 4.10 and 4.11. Development screens (R1 to R3, T3a to T3c, the Camber half of K3r) never count.

Calibration and freezing order on the rest substrate:

1. C0, then R1 and R2, then T3a to T3c when section 2.6 step 6 runs, then R3 and R4;
2. K1r, then the drive commit;
3. K2r, then the dopamine commit;
4. Q-rest;
5. V-cal, then the visual commit, then V1 and V3;
6. bias, sign check and K3r, then the behaviour commit;
7. 4.1r and 4.2r;
8. integration, then 4.3r, then acceptance.

A change to an earlier configuration stales the later entries that read it, through the binding rule.

### 5.3 Tests

All Phase 1 entries not listed here carry over unchanged in definition and class and stay bound to their own substrate: 0.1 to 0.8, 1.0 to 1.3, `1.4-bare`, `2.2-bare`, 3.1 to 3.9 on the bare record, 4.0, 4.0b and `4.1-procedure`. Entries with an `r` suffix are separate Phase 2 entries on the rest substrate; they do not replace their Phase 1 counterparts.

Level 0:

- 0.9r (verification) has four parts.
  - (a) The Phase 1 0.9 cases.
  - (b) Constructed cases for each section 5.1 clause: a code-scope change, a run-scope mismatch, an input blob change, an undeclared logged input, an override inside and outside a declared grid, and a substrate mismatch.
  - (c) The freeze protocol on a constructed git repository. A configuration commit and an execution produce a valid entry. An evidence commit leaves it valid, and so does a commit to an unrelated data file. A configuration byte change stales it, and so does a `src/` change. `qualification_of` follows each step.
  - (d) Dependency negatives. A `pyarrow.parquet.read_table` of `data/reference/l5-baseline-spikes.parquet` through `io.py` is logged. The same read made directly in a scanned module fails the static check. A spawned process reading through `io.py` has its log merged. A spawned process whose log is missing triggers conservative binding. A plain Python read through `io.py` is logged.
- 0.10 (verification): transmitter rule and scale composition, in two legs.
  - Pure leg: on a constructed annotation table, classes follow section 2.2.1 and the scale array equals the formula row by row. On the real files: every photoreceptor row is inhibitory; every L1 row has class Glu; s_pq is a function of the presynaptic neuron; no neuron outside the curated labels and photoreceptor types changes sign; census counts match `transmitters-v0.2.yaml`.
  - Engine leg: after `set_weight_scale`, `store("initial")` and `restore`, weights on 1,000 rows sampled from every class and every corrected-sign class equal `_base_w_mv × scale` bitwise.
- 0.11 (verification, required when `sigma_th` > 0): over 100 chunks with modulation active, each engine threshold equals `lif.v_th + sigma_th × z_i`, plus the composed dopamine shift, plus manipulation shifts, bitwise.
- 0.12 (verification): each section 1.3 file has the SHA-256 listed in `tests/fixtures/frozen-v0.1.json`, which WP16 writes from 835da84. Every v0.1 row value is unchanged in `params-v0.2.yaml` unless marked "changed".
- 0.13 (verification): the section 2.4 settle rule, as specified there. It also checks that schema 1.2 probes use the Phase 1 rule.
- 0.14 (verification): bare compatibility. `tests/fixtures/experiments/bare-twin-1.2.json` and `bare-twin-1.3.json` resolve to identical experiments apart from `schema_version` and give bitwise identical spike tables and metrics. A schema 1.3 file with `background: false` that sets any 1.3-only feature is rejected (section 8.1).
- 0.15 (verification): switch neutrality for tier 3, in four parts.
  - (a) Strings. `build` with `mechanisms` not passed, `None`, or a `Mechanisms` whose blocks are all null gives `engine_model()` `lif` and `method()` `linear`. `model_strings()` equals (`lif_model`, `lif_threshold`, `lif_reset`, `lif_on_pre`) from `tests/fixtures/wp24-off-reference.json`, byte for byte. The namespace keys and state variable names equal those the fixture records. The Brian2 object names do too, compared on the first `build` in a fresh process, as the fixture was recorded, because each build's names carry its build tag (`neurons_e0`). `mechanism_traces(0)` has no columns. No part of (a) reads this document.
  - (b) Bitwise off path. WP24's first commit (section 8.4, G-3a step 1) writes `tests/fixtures/wp24-off-reference.json` before any engine edit. It records the commit and its `code_scope`, and the four `lif` strings as `brian_engine.py` passes them to Brian2, with the SHA-256 of each. It also records the object names, namespace keys and state variable names of the tiny engine of run (i), and, for each of four runs, its recipe and the SHA-256s named below.
    - Encodings, named in the fixture. A spike-table hash is the SHA-256 of `idx` as little-endian int32 bytes followed by `tick` as little-endian int64 bytes, in the order `spikes(0)` returns them. A trace hash is the SHA-256 of `tick` as little-endian int64 bytes followed by `v_mv` as little-endian float64 bytes in C order.
    - (i) The 0.16 fixture on `lif`: the spike-table hash of `spikes(0)` and the trace hash of `traces(0)`. This is the only run that traces.
    - (ii) A 2 s probe without stimulus, seed 1, background on, with `data/drive-dev-p2.yaml` applied through `load_drive_rest` and `apply_rest_substrate` and `bg.n_bg` set to that file's `n_bg`: the spike-table hash of `spikes(0)` after the probe. The file has no `mechanisms` section, so the loader's result states `mechanisms` as null, and that result is what `apply_rest_substrate` receives. At commit 1, whose loader does not return the key yet, the result is passed as that loader returns it.
    - (iii) The same probe on a constructed copy of that file with a `mechanisms` section whose three blocks are null: the same hash as (ii).
    - (iv) The extended-mode candidate arm of R-reflex (c) at pair (3, 6), seed 1, both conditions. The recording code calls `_build_engine` in `drive/rest_map.py` with `Setting(g_gaba=3, g_glu=6)`, `mode` extended and `feedforward` true, with no mechanism. It then calls `_probe` on the result with weight 1.15 mV, seed 1 and `seconds` 1, first silent and then with `active` true, and takes the spike-table hash of `spikes(0)` after each call. It does not call `_task`, which writes metrics rather than tables. At the branch point that is v783, `params-v0.2.yaml`, background off, A and C on with `dopamine-v0.1` and free pools, sugar GRNs as extended inputs at 150 Hz, `sigma_th` 0, optic exemption off, `n_bg` 100, weight 1.15 mV (unused with background off), and scales applied through `apply_rest_substrate` with `thresholds=False`. Each `_probe` call restores, reseeds with `brian_seed(20260912, 1, 0)`, settles 2 s and measures 1 s.

    The recording code of runs (i) to (iv) in `validation/level0_mech.py` is committed at commit 1 and checks every later commit unchanged. On every later G-3a commit, each run gives its recorded SHA-256s, and (iii) gives those of (ii). Each identity records its execution platform; runs (ii) to (iv) build the full engine and are slow tests.
  - (c) Existing tests. 0.3, 0.4, 0.8, 0.10-engine, 0.11, 0.13 and 0.14 pass against their recorded references, unchanged, on every WP24 commit.
  - (d) Identity and loading, on constructed files (`tests/test_mechanisms_loader.py`):
    - `substrate_id_for` gives `rest:<16 hex>` for (ii) and (iii), and `rest-sfa:`, `rest-std:` and `rest-cbi:` for files with one block on. `engine_model_of` follows section 2.2.4 for each block and for an absent section.
    - Every loader rejection of section 2.2.4 fires. `load_drive_rest` accepts `data/drive-dev-p2.yaml` as committed and a document with `version` v0.2. It rejects an unknown top-level key, a `version` other than v0.2, `candidate_id`, `selection` or `note` without `configuration_class` development, and a `configuration_class` other than development.
    - Masks: a constructed four-neuron registry with neurons 1 and 3 in scope hashes to the SHA-256 of the bytes 00 01 00 01. The `non_sensory` and `non_sensory_excitatory` masks built from the real annotations have length `engine.n`, follow `root_ids` order, exclude every sensory neuron, and place each unk neuron by its connection-file sign.
    - `apply_rest_substrate` raises on a mapping without `mechanisms`, and on a model mismatch in both directions.
    - Schema 1.2 and schema 1.3 background-off files that pin a file with a mechanism are rejected outside the section 8.1 fixture.
    - An identity block without `engine_model` binds to a `lif` run and not to a `lif+sfa` run. An identity block whose `substrate_id` tag and `engine_model` disagree is invalid.
- 0.16 (verification, required when `lif+sfa` is in force): adaptation of one neuron against its exact solution, in the style of test 0.1.
  - Fixture `tests/fixtures/engine/fixture-0-16.json` on the tiny engine files of test 0.1. Neuron 0 is the spike-list driver and is traced (`spikelist_idx` and `trace_idx` [0]). Neurons 1 to 3 are silenced at `engine.silence_vth`, and none of them projects to neuron 0, so neuron 0 receives only the spike list. The list holds ticks 100 + 100k for k = 0 to 49 (100 Hz from 10 to 500 ms) and ticks 6,000 + 10k for k = 0 to 49 (1 kHz from 600 to 650 ms). The run is 8,000 ticks at `lif.dt` 0.1 ms. v of neuron 0 comes from `traces(0).v_mv` in mV, as in test 0.1, and a_sfa from `mechanism_traces(0).a_sfa_mv` in mV. The reference keeps v, g and a in mV. The engine's g is not recorded, and no clause compares it.
  - Exact one-tick solution. With E_m = exp(−dt / t_mbr), E_g = exp(−dt / tau), E_a = exp(−dt / tau_sfa), c_g = tau / (tau − t_mbr) and c_a = tau_sfa / (tau_sfa − t_mbr), the section 2.2.4 equations over one tick give

    ```
    v' = v_0 + (v − v_0) × E_m + g × c_g × (E_g − E_m) − a × c_a × (E_a − E_m)
    g' = g × E_g
    a' = a × E_a
    ```

    Under `lif`, a is 0 throughout and its term is dropped.
  - Reference procedure. The reference starts from v = v_0, g = 0, a = 0 and no spike, and runs each tick k in this order:
    1. Record v, g and a as the state at time k × dt.
    2. The neuron is refractory at tick k when it has spiked and k − s_last < round(rfc / dt), where s_last is its last spike tick.
    3. If it is not refractory, apply the one-tick solution. If it is refractory, v, g and a keep their values.
    4. It spikes at tick k when it is not refractory and v > v_th.
    5. A spike-list event at tick k adds `input.w_in` to g only when the neuron was not refractory at step 2 and did not spike at step 4. Otherwise the event is lost.
    6. At a spike: s_last = k, v = v_rst, g = 0 and a = a + b. a is not cleared.

    An event at tick k therefore acts from time (k + 1) × dt, test 0.1's convention. The order is Brian2 2.10.1's for this model: state update, threshold, synaptic delivery, then reset, with writes to `unless refractory` variables dropped while the neuron is refractory and on its spike tick. In the WP24 round this procedure matched Brian2 on this fixture in all eight runs of (a) to (c): equal spike ticks, states within 1.3e-14 relative.
  - Validity. At every tick where step 4 is evaluated, |v − v_th| ≥ 1e-6 mV in the reference, so no threshold decision rests on rounding. Under each setting of (b) the reference loses at least one event during refractory and at least one on a spike tick, and under (c) at least one on a spike tick, so step 5 is exercised. A fixture that fails either condition is changed, never the tolerance.
  - (a) `lif`: spike ticks equal to the reference's, and |v − v_ref| ≤ 1e-9 × max(|v_ref|, 1 mV) at every tick. This checks the procedure against the Phase 1 model; (b) to (e) check adaptation.
  - (b) `lif+sfa` with neuron 0 in scope, at (b_mv, tau_ms) = (1, 150), (3, 50) and (0.3, 500): spike ticks equal, and v and a_sfa within 1e-9 × max(|x_ref|, 1 mV) at every tick. At each setting neuron 0 fires fewer spikes than under (a).
  - (c) As (a) and (b), with neuron 0's refractory period set to 0 through `set_refractory`.
  - (d) Decay. From tick j = s_last + round(`lif.t_rfc` / dt) + 1 after neuron 0's last spike in (b) to the last tick k, with no event in between, a_sfa(k) / a_sfa(j) equals exp(−(k − j) × dt / tau_sfa) within 1e-9. This clause does not depend on the reference procedure.
  - (e) Scope. With the mask on neurons 1 to 3 only, neuron 0 matches the `lif` reference within (a)'s tolerance, and its a_sfa is exactly 0 mV throughout.
- 0.17 (verification, required when `lif+std` is in force): depression of one connection against its closed form.
  - Fixture `tests/fixtures/engine/fixture-0-17.json` with `tiny_std_completeness.csv` and `tiny_std_connectivity.parquet`: two neurons and one excitatory connection 0 → 1 of 20 synapses (weight 20 × `lif.w_syn`). Neuron 0 is the spike-list driver, and both neurons are traced. The list holds ticks 100 + 200k for k = 0 to 49 (50 Hz from 10 to 990 ms) and ticks 12,100 + 200k for k = 0 to 4 (50 Hz from 1,210 ms). The run is 14,000 ticks. Neuron 1 must stay at least 1 mV below `lif.v_th` in every reference run.
  - Driver. In every run, neuron 0's recorded spike ticks s_1, s_2, … equal the spike ticks of the 0.16 reference procedure for a `lif` neuron under the same list, one spike per event. Depression acts only on neuron 0's outputs, so its own dynamics are `lif`. The closed form below is therefore a function of the list and the parameters, not of the engine's record.
  - Closed form. xr_1 = 1, and x_k⁺ = xr_k × (1 − U) is neuron 0's x_std from time (s_k + 1) × dt. For k ≥ 2, xr_k = 1 − (1 − x_(k−1)⁺) × exp(−(s_k − s_(k−1)) × dt / tau_std). The recorded x_std is 1 up to tick s_1, and 1 − (1 − x_k⁺) × exp(−(j − s_k − 1) × dt / tau_std) at tick j with s_k < j ≤ s_(k+1). x_std recovers during refractory. Spike k is delivered at tick s_k + round(`lif.t_dly` / dt) and acts from the next tick. Neuron 1's v is v_0 plus, for each k, 20 × `lif.w_syn` × xr_k times test 0.1's kernel from that acting time.
  - (a) `lif` (xr_k = 1): v of neuron 1 within 1e-9 × max(|v_ref|, 1 mV) at every tick.
  - (b) `lif+std` with neuron 0 in scope, at (U, tau_ms) = (0.2, 100), (0.5, 400) and (0.05, 400): v of neuron 1 within (a)'s tolerance, and x_std of neuron 0 within 1e-9 absolute, at every tick. At each setting the mean of v − v_0 over [810, 1010) ms is below 0.9 times its value in (a).
  - (c) `lif+std` with neuron 0 outside the scope (U_std 0): spike ticks equal to (a), v within (a)'s tolerance, and x_std and xr_std exactly 1 throughout.
  - (d) Guard: `set_refractory` to 1 ms on a neuron with U_std > 0 raises the section 2.2.4 `ValueError`, and so does `compose_refractory` with an active bank targeting such a neuron.
- 0.18 (verification, required when `lif+cbi` is in force): conductance-based inhibition against a high-accuracy reference.
  - Fixture `tests/fixtures/engine/fixture-0-18.json` with `tiny_cbi_completeness.csv` and `tiny_cbi_connectivity.parquet`: three neurons, with 0 → 2 inhibitory and 1 → 2 excitatory, 20 synapses each (weights −20 and +20 × `lif.w_syn`). Neurons 0 and 1 are spike-list drivers, and neuron 2 is traced. Neuron 0's list is 10 + 20k ms for k = 0 to 49 (50 Hz), and neuron 1's is 10 + 12.5k ms for k = 0 to 79 (80 Hz). An event at t ms is tick round(t / dt), which is exact for every event at both 0.1 and 0.05 ms. The run is 1,100 ms. Neuron 2 must stay at least 1 mV below `lif.v_th` in every reference run.
  - Drivers. In every run, each driver's recorded spike ticks equal the spike ticks of the 0.16 reference procedure for a `lif` neuron under its list at the run's dt, one spike per event. The drivers receive only spike-list input, which acts on g, so their h_inh stays 0.
  - Reference. Neuron 2's section 2.2.4 equations in u = v − v_0 (mV), g (mV) and h_inh (dimensionless), integrated by `scipy.integrate.solve_ivp` with method DOP853, rtol 1e-13 and atol 1e-13, and sampled at every tick. Driver spike s is delivered at tick s + round(`lif.t_dly` / dt) and acts from the next tick. The integration stops there, applies g += w for w > 0 or h_inh += −w / (v_0 − E_inh) for w < 0, and restarts.
  - Tolerance. `rk4` is not exact, so the tolerance is 1e-6, not 1e-9. In a WP24-round scratch check on this fixture, against RK4 with 40 substeps per tick rather than DOP853, its error was about 2e-11 relative in v and 6e-10 in h_inh at 0.1 ms. An error in the equations, the normalisation or the routing moves v by more than 0.02 mV, above 3e-4 relative. (c) checks the method's order.
  - (a) `lif` on this fixture against test 0.1's closed form, summed over signed events: 1e-9 × max(|v_ref|, 1 mV).
  - (b) `lif+cbi` at `E_inh_mv` −72, −62 and −57: v of neuron 2 within 1e-6 × max(|v_ref|, 1 mV) and h_inh within 1e-6 × max(|h_ref|, 1) at every tick. At each setting the largest |v − v_lif| over the run exceeds 0.02 mV, so the test is not vacuous.
  - (c) Convergence. At `E_inh_mv` −57, the same run at `lif.dt` 0.05 ms has a largest |v − v_ref| no more than 1/8 of that at 0.1 ms, unless the error at 0.1 ms is below 1e-10 mV. rk4's order predicts 1/16, and a WP24-round scratch check against RK4 with 40 substeps per tick, not DOP853, measured 0.062. If (c) fails because the reference's own error or the event grid dominates, the fixture's rates or run length change, never the 1/8 rule.
  - (d) Normalisation and routing. With neuron 1 silent and one event from neuron 0, h_inh from the acting tick equals 20 × `lif.w_syn` / (v_0 − E_inh) × exp(−t / tau) within 1e-6, and v of neuron 2 matches the reference, in which g stays 0 mV, within (b)'s tolerance. g is not recorded; an event routed to g as well, or to g alone, moves v away from that reference by more than 1e-3 relative. After `set_weight_scale` with factor −1 on both rows, the 0 → 2 row acts on g and the 1 → 2 row on h_inh: h_inh and v match the reference with the roles swapped.
  - (e) Constructed evaluations (no engine): h_max 19.1 at `lif.dt` 0.1 ms flags `cbi-stiff`, and h_max 18.9 does not.

Level 1:

- 1.3r (consistency, recorded): on the rest substrate with background on, bitter GRN co-activation reduces MN9 below half its sugar-only rate.
- 1.4r (consistency): rest substrate, background on, A and C on with free pools, extended mode, ten seeds, 1 s per condition after settle. The ten-seed mean MN9 sugar-minus-silent difference exceeds 50 Hz, and no seed falls below 40 Hz (item 61). On a drive configuration with a mechanism, the mechanism is in force and the rule is unchanged: absolute rates with background on, not a retention.
- 1.4r-ff (consistency): R-reflex (c) on the committed drive configuration, through the fixtures `ff-bare.json` and `ff-candidate.json`. A mechanism in the committed drive file is in force in `ff-candidate.json`; `ff-bare.json` always builds `lif`. They use identical seeds, windows, layers (A and C on, `dopamine-v0.1`) and modes. Extended-mode retention must be at least 0.5. Upstream retention and both arms' per-seed values are recorded.

Level 2 (rest substrate, free pools, A and C on, wild type, no drug):

- 2.1r (background calibration, recorded): clamped and free group rates against placeholder targets, and J.
- 2.2r (consistency): over a settled 10 s spontaneous window, the all-neuron median rate is in [0.2, 5] Hz and fewer than 1 percent of neurons exceed 50 Hz, the pre-specified Phase 1 background-on criterion of test 2.2. The stimulated seed-0 1.4r window is also recorded under the bare rule.
- 2.3r (consistency): three seeds, 10 s after settle. The R-screen rows of section 2.3 hold except gradedness, and every probe settles under section 2.4. Block-scale Fano per resolved population is recorded.
- 2.4r (consistency): five JITTER streams of log-normal σ 0.3. Under each, the 1.4r MN9 difference changes by under 25 percent, group rates change by under a factor of 1.5, and F stays below 3.
- 2.5r (benchmark, recorded): B1-rest `q1` and B2-rest, and at WP22 B2-P2 on the selected acceptance file, each with `q2` at its worker count, `t_build`, `t_agg`, mean settle per probe and peak memory (section 6.4).
- B-mech (benchmark, recorded, WP24): section 6.5, once per engine model with a mechanism, before that sub-tier's plan record, run by `scripts/bench.py --mech sfa|std|cbi`.
- 2.6r (consistency): all group weights shifted by +0.05 and by −0.05 mV, three seeds, 10 s each. At +0.05, central rate stays under 3 × its configured value and F stays below 3. At −0.05, central rate stays above one third of its configured value.
- 2.7r (consistency): ten seeds, 30 s after settle. In every seed F is below 3, there is no ignition, and the central ratio of the first to the last 5 s is in [0.5, 2].

Level 3 (rest substrate):

- 3.1r (calibration, recorded): the K2r record.
- 3.1r-alg (verification, no engine): the section 2.5 fixed-point checks.
- 3.1br (consistency): 3.1b (i) to (iii) with background on, three seeds, each settled and then recorded for 10 s, every seed required.
- 3.2r to 3.5r (consistency): the Phase 1 definitions of 3.2 to 3.5 on the rest substrate, with dark `spontaneous` probes in place of the Phase 1 Buridan probes. `dose-p2.json` (3.3r) has four arms (wild type and fumin, each with vehicle and methylphenidate) and doses 0.1, 0.5 and 1.0 mM with 100 h washouts. Each dose level gets one 5 s probe, seeds 1 to 3.
- 3.6r (prediction, recorded): the Phase 1 3.6 contrasts plus the fumin-minus-wild-type `DA_exposed` rate.
- 3.7 (verification): unchanged.
- 3.8r (consistency, recorded, matching-layers): the Phase 1 2×2 factorial on `ablation-p2.json`, in the form matching the visual status, after the behaviour commit, with `DA_exposed` mean rate added beside `DN_all` and mean compartment dopamine.
- 3.9r (sensitivity, recorded, development on Camber): the Phase 1 3.9 settings (nine parameters or pairs at low, default and high, 27 before seeds) in two parts.
  - Dose part: `dose-p2.json` at all 27 settings, seeds 1 to 3, recording the dose-effect sign and the wild-type, drug and fumin ordering as in Phase 1.
  - Coupling part: `coupling-sweep.json`, which is the 3.10r fixture without the dop1r1_null arm (wild type and fumin, vehicle, seeds 1 to 10, one 20 s dark `spontaneous` probe). It runs at the 15 distinct settings of the seven parameters that act without drug: `Kd_D1`, `Kd_D2`, the `gamma_*` pair, the `dV_*` pair, `Vmax`, `Km` and `k_ns`, with the default once. `Ki_mph` and `kappa` act only through the drug, so their coupling contrast is the default's. Each setting records the 3.10r contrast and interval.
- 3.10r (consistency, canonical fixture `data/experiments/p2/coupling.json`): arms `wild_type`, `fumin` and `dop1r1_null`, vehicle, ten seeds, one 20 s `spontaneous` probe in the dark.
  - Required: the paired fumin-minus-wild-type `DA_exposed` mean-rate interval excludes zero.
  - Recorded: the dop1r1_null contrast and the per-population differences for KC, MBON, ER, EPG, dFB, steering and `DN_all`.

Level V: V0, V1, V2, V3 and V-cal (section 3.4); VT-cal and V1-T (section 3.7).

Level 4:

- 4.0c (verification): `steer_gain`, `fixation_retention` and `distractor_capture_hz` on constructed data with known values; the random initial heading equals the first BEHAVIOUR draw and is identical across arms; the bias is subtracted exactly once in omega.
- Bias, 4.1r-sign, K3r, 4.1r, 4.2r and 4.4r to 4.8r (section 3.5), 4.3r (section 3.8), and their -T counterparts (section 3.7).
- 4.9 (prediction, development): the P-screen contrast tables.
- 4.10 (prediction, matching-layers): the canonical prediction tables per selected genotype, with status words.
- 4.11 (prediction, development): `steer_gain` and `distractor_capture_hz` per genotype (section 4.4).

## 6. Compute plan

### 6.1 Local budget and Mac timing basis

Rolf's MacBook (Apple M5 Pro, 18 cores, 24 GB) runs under item 69 (d): one engine budget per machine, shared by every lane through the slot file of WP11's `orchestrator/budget.py`. No lane owns the machine. Auto slots are min(physical CPUs − 2 − held slots, floor(available / footprint)), where available is `hw.memsize × kern.memorystatus_level / 100` less an 8 GiB reserve on macOS (review r12: running workers are already absent from available memory, so held slots reduce only the core term), and swap use above 4,000 MiB gives zero slots. WP11's latest probe measured a 790 MB footprint, which fits the 12-worker target in memory. Its scaling qualification is still pending, and fitting in memory does not prove throughput.

Rule: a lane plans with the worker count its budget query grants. Until WP11's scaling results or B2-rest give a measured per-engine cost at that concurrency, it uses `q_plan`. If the scaling results show a per-engine slowdown at the granted concurrency, the lane multiplies by it.

The Mac timing plan includes:

- K1r, K2r and Q-rest;
- V-cal, V1 and V3;
- bias, sign check, the K3r finalists, 4.1r and 4.2r;
- the neural level-3 entries and the canonical prediction files;
- B1-rest, B2-rest and B2-P2;
- status regeneration, 4.3r, and the acceptance pair and its replay;
- the Phase 1 closure pair (item 70).

Acceptance and closure runs hold `caffeinate -ims`.

### 6.2 Camber

`large` nodes have 64 cores and 256 GB, cost 2.56 credits per node-hour, are CPU only, and draw on a free trial with no balance command. Account `roller`, team `hasanugurteam03920735`, CLI `~/.camber/bin/camber`.

Planning figures:

- 62 engines per node: 64 cores less 2. At 790 MB to 2.9 GB per engine, memory fits.
- ρ, the per-engine cost of a Camber engine relative to `q_plan`, is 1.0 until the proof lane (`tasks/camber-proof.md`) measures it. If measured ρ exceeds 1.5, every Camber row scales by ρ, and each WP re-checks its cap before launching.
- Two nodes run concurrently. If the account limit is one node, Camber wall times double.

Staging, running and pulling back use lane cam's scripts at commit 983c141 (`scripts/camber/stage.sh`, `job.sh`, `grid.py`):

1. `stage.sh` puts a git archive of the lane's commit and the needed `.cache` subset at `stash://roller/projects/flyonenomics/<commit>/`.
2. The job runs `uv sync --frozen` and a shard driver over 62 processes. Each scale combination gets its own process, with the scale applied before `store("initial")`. Every evaluation writes one NDJSON line with job id, commit, `code_scope`, platform, parameters, seed and metrics.
3. Results go to `stash://roller/projects/flyonenomics/<commit>/results/<label>/`.
4. The lane pulls them back to `.worktrees/<lane>/camber-runs/<label>/`, which git ignores.
5. The lane appends each job to `.reports/camber-ledger.md`: job id, label, node type, start, end, node-hours, credits.

A lane checks job state with one `camber job get <id>` at most every ten minutes. Camber experiment files set `record.live: false`.

Credit caps at ρ = 1:

| WP | Cap (credits) | Covers |
|---|---:|---|
| WP17 | 11 | R1 including the full tier-1 fallback, R-reflex and R-long |
| WP17, tier 2 | 11 | tier 2 when section 2.6 step 4 triggers it |
| WP18 | 1 | R3 |
| WP20 | 4 | K3r, 4.8r, K3r-T |
| WP21 | 10 closed loop, 14 open loop | P-screen, 3.9r, 4.11 |
| WP24, per tier-3 sub-tier | 62 | T0, T1 and T2 at ρ_mech 1 and the measured Camber rate (section 6.5) |

The caps total 26 credits under closed loop and 30 under open loop, 11 more with tier 2, on top of lane cam's map. Exceeding a cap by up to 25 percent needs coordinator approval; beyond that, Rolf decides (open question 5). If Camber is unavailable, the Mac runs the work at the wall times of section 6.3. WP24's row uses the measured Camber rate of section 6.5, not the 62-engine planning figures above. It is recorded for the ledger: Rolf ruled on 2026-09-16 that credits are not a gate and wall time is (`HANDOFF.md`, Open item 3). Tier 3 has no Mac fallback within the schedule. Without Camber, only T0 runs on the Mac (88 engine-hours for 3a, about 18 hours at 5 workers), and the coordinator asks Rolf.

### 6.3 Estimates

Engine-hours use `q_plan`. Brain s count each probe's duration plus `budget.plan_settle_s` 2 s of settle; wall budgets use measured settle instead (section 6.4). Mac wall is engine-hours divided by 5 granted workers, and parallel rows halve at 10 workers if scaling holds. Camber wall assumes two nodes, and node-hours are engine-hours / 62. "Closed loop" rows apply to both closed-loop statuses; "open loop" rows replace them under that status.

| Work | WP | Brain s | Where | Engine-hours | Wall | Credits |
|---|---|---:|---|---:|---|---:|
| Camber map stage 1 (running, lane cam) | cam | 49,248 | Camber | 369 | ~3 h | 15.3 |
| R1 re-screen, 12 pairs × 19 × 3 × 12 s | WP17 | 8,208 | Camber | 62 | ~30 min | 2.5 |
| R1 full tier 1 instead, 36 pairs | WP17 | 24,624 | Camber (Mac ~37 h) | 185 | ~1.5 h | 7.6 |
| R-reflex and R-long, ≤ 20 × 540 s plus bare references | WP17 | 10,920 | Camber | 82 | ~40 min | 3.4 |
| Tier 2, if triggered | WP17 | 34,884 | Camber | 262 | ~2 h | 10.8 |
| B-mech, per engine model: W1 and W2, off, weakest and strongest, three warm repeats | WP24 | 162 | Mac, one engine | 1.2 | ~1.5 h with builds | |
| Tests 0.15 (b) (full-engine runs, before and after the engine edit), 0.16 to 0.18 (tiny engines) | WP24 | 14 | Mac, one engine | 0.1 | ~30 min with builds | |
| Tier 3a, if triggered (section 6.5) | WP24 | 48,880 | Camber, 16 jobs | 366.6 | ~6 h at 5 slots, ~8 h with collection | 61.6 |
| Tier 3b, if 3a ends empty | WP24 | 48,160 | Camber, 16 jobs | 361.2 | ~6 h at 5 slots, ~8 h with collection | 60.8 |
| Tier 3c, if 3b ends empty | WP24 | 39,880 | Camber, 13 jobs | 299.1 | ~6 h at 5 slots, ~8 h with collection | 50.7 |
| R3, ≤ 6 candidates × 4 rates × 90 s | WP18 | 2,160 | Camber (Mac ~3.2 h) | 16 | ~10 min | 0.7 |
| B1-rest | WP19 | 20 | Mac, one engine | 0.15 | 9 min | |
| K1r | WP19 | 280 | Mac, one engine | 2.1 | 2.1 h | |
| K2r with free-pool iterations | WP19 | 130 | Mac, 3 workers | 1.0 | 20 min | |
| Q-rest (also B2-rest) | WP19 | 700 | Mac | 5.3 | 1.1 h | |
| Second K1r-to-Q-rest chain, if needed | WP19 | 830 | Mac | 6.2 | 1.3 h plus K1r serial | |
| V-cal, visual commit, V1 and V3 | WP18 | 540 | Mac | 4.1 | 50 min | |
| Bias, sign check, 4.1r (41 s probes) | WP20 | 653 | Mac | 4.9 | 1 h | |
| K3r proposal, 5 values × 5 seeds × 22 s | WP20 | 550 | Camber | 4.1 | ~5 min | 0.2 |
| K3r finalists and 4.2r | WP20 | 1,320 | Mac | 9.9 | 2 h | |
| 4.8r, 13 variants × 3 arms × 10 × 22 s | WP20 | 8,580 | Camber | 64 | ~35 min | 2.7 |
| TuBu path, if needed | WP20 | 2,600 Mac, 550 Camber | Mac and Camber | 19.5 + 4.1 | 3.9 h | 0.2 |
| Neural level 3 (3.2r to 3.6r, 3.8r, 3.10r), allowance | WP21 | 4,200 | Mac | 31.5 | 6.3 h | |
| P-screen, closed loop, 28 arms × 10 × 2 × 22 s | WP21 | 12,320 | Camber | 92 | ~45 min | 3.8 |
| P-screen, open loop, 28 arms × 10 × 2 × 49 s | WP21 | 27,440 | Camber | 206 | ~1.7 h | 8.5 |
| 3.9r dose part, 27 settings × 3 seeds × 12 probes × 7 s | WP21 | 6,804 | Camber | 51 | ~25 min | 2.1 |
| 3.9r coupling part, 15 settings × 2 arms × 10 × 22 s | WP21 | 6,600 | Camber | 50 | ~25 min | 2.0 |
| 4.11, closed loop, ≤ 5 arms × 10 × 49 s | WP21 | 2,450 | Camber | 18 | ~10 min | 0.8 |
| Canonical predictions, closed loop, ≤ 16 arms × 10 × 2 × 22 s | WP21 | 7,040 | Mac timing basis | 52.8 | 10.6 h | |
| Canonical predictions, open loop, ≤ 16 arms × 10 × 2 × 49 s | WP21 | 15,680 | Mac timing basis | 117.6 | 23.5 h | |
| Status regeneration at integration | WP22 | — | Mac | — | 6,150 s serial measured; ~1.5 h | |
| Closed loop: 4.3r (10 × 22 s), B2-P2 (4 seeds × 4 arms × 2 × 22 s), acceptance pair (2 × 10 × 4 × 2 × 22 s) | WP22 | 4,444 | Mac | 33.3 | 6.7 h | |
| Open loop: B2-P2 (4 × 4 × 2 × 49 s), acceptance pair (2 × 10 × 4 × 2 × 49 s) | WP22 | 9,408 | Mac | 70.6 | 14.1 h | |

The neural level-3 row is an allowance; the plan check below replaces it with the expanded files' brain s, including 3.8r's longer open-loop form.

Totals without conditional rows and without the running map:

- Closed loop. Mac: about 19,300 brain s, 145 engine-hours, about 29 wall hours at 5 workers (about 15 at 10), plus regeneration. Camber: about 58,600 brain s, 439 engine-hours, 7.1 node-hours, 18.1 credits.
- Open loop. Mac: about 32,900 brain s, 247 engine-hours, about 49 wall hours at 5 workers, plus regeneration. Camber: about 71,300 brain s, 535 engine-hours, 8.6 node-hours, 22.1 credits. Steps not reached on the way to open loop (K3r, 4.2r, 4.8r) lower both.

Conditional rows add 5.1 credits for the full tier 1, 10.8 for tier 2 and 0.2 for the TuBu path, and 61.6, 60.8 and 50.7 for tiers 3a, 3b and 3c at the measured Camber rate. Tier-3 Camber rows use section 6.5's node-hours, not engine-hours / 62. At a measured ρ of 2, Camber credits double.

Plan check. `scripts/bench.py --plan <file>` (WP19, no engine) expands an experiment file. It prints arms, seeds, probes, per-probe durations, and brain s at the planning settle. Two tests run it on every Phase 2 file behind a row above, in both probe forms:

- `tests/test_p2_plan_pharm.py` (WP21) covers the P-screen, prediction and ablation files (canonical files at the maximum selection), `dose-p2.json`, `coupling.json`, `coupling-sweep.json` with the 3.9r setting lists, and 4.11.
- `tests/test_p2_plan_acceptance.py` (WP22) covers the three acceptance files, the holdout fixtures, and each branch's B2-P2 derivation.

Each file must match its row's factors and brain s, and each B2-P2 derivation must equal its source file in everything except seeds. A WP whose files change a row updates the row and re-checks its cap before launching.

### 6.4 Wall budgets

A stage of T brain s over n runs gets this budget:

```
serial or dependent stage: 1.25 × q1_s × T + n × (t_build + t_agg)
parallel stage:            1.25 × q2_s(w) × T + n × (t_build + t_agg)
```

- q1_s is the measured single-engine cost per simulated brain s on the stage's substrate: B1 for bare, B1-rest for rest.
- q2_s(w) is the measured aggregate cost per simulated brain s on that substrate at the stage's granted concurrency w.
- Before a measurement exists, q1_s is `q_plan` and q2_s(w) is `q_plan` / w.
- T sums, over the stage's expanded files, each probe's duration plus its settle. The settle is the mean measured by the latest benchmark of that probe type on the substrate, or `settle.max_s` before one exists.

WP19 runs B1-rest (B1 with the rest substrate pinned and background on) before K1r. Q-rest's own execution, at its granted w, is recorded as B2-rest and gives later rest stages q2_s at that w. A stage granted a different w uses `q_plan` / w, scaled by any WP11 slowdown, until measured at that w.

B2-P2 (WP22) derives from the acceptance file the visual status selects. `scripts/bench.py --b2p2 <file>` restricts that file to seeds 1 to 4 and changes nothing else: arms, pins, encoder, phases and recording stay as they are. It runs at the acceptance run's granted w and records mean settle per probe type. Clause 1's budget is `1.25 × q2 × T_acc + n × (t_build + t_agg)`. Here q2 is B2-P2's wall per simulated brain s, T_acc sums the acceptance file's probe durations plus B2-P2's measured mean settle per probe, and n is the acceptance file's run count. At the planning settle, B2-P2 is 704 brain s for either closed-loop file and 1,568 for the open-loop file.

If B1-rest `q1` exceeds `budget.q1_escalation` 30 wall s per brain s, WP19 reports to the coordinator, and every rest estimate is rescaled. A Camber job's wall cap is `1.25 × ρ × q_plan × brain s per shard + 60 s`. Every WP report records measured wall against budget.

### 6.5 Tier 3: benchmark and Camber shaping

B-mech (WP24, Mac, one engine). It runs once per engine model with a mechanism, as `scripts/bench.py --mech sfa|std|cbi`, and is recorded in `validation/records/p2/bench-mech-<tag>.json` and `docs/bench.md`. No tier-3 Camber job is sized before it.

- W1, rest probe: pair (3, 6), every group weight 1.15 mV, `n_bg` 100, `sigma_th` 0, optic exemption off, background on, the section 2.3 calibration state, seed 1, 2 s settle plus 10 s.
- W2, feed-forward probe: the T0 candidate arm at pair (1, 1), seed 1, both conditions of 3 s each.
- Each workload runs with no mechanism, at the grid's weakest setting (lowest M) and at its strongest (highest M), with ties in M broken by the section 2.6 parameter order, first for the weakest and last for the strongest. Each setting gets one cold build, then three warm repeats.
- Recorded per run: wall per brain s, cold build time, peak `phys_footprint`, and spike count, since the cost follows activity.
- ρ_mech is the largest ratio, over W1 and W2 and both settings, of the median wall per brain s with the mechanism on to the median with it off, and at least 1.0. It scales every tier-3 Camber figure below and the cap projection of section 2.6 step 6. A ρ_mech above 1.5 is a line in the WP24 report, not a stop.

Camber constants, all in `data/rest-tier3-v0.2.yaml`, from the ledger unless the row says otherwise:

| Name | Value | Source |
|---|---:|---|
| `camber.workers` | 36 per large node | throughput plateau of ~29.5 engine-equivalents on 32 physical cores |
| `camber.worker_s_per_brain_s` | 50 | job 27299: 11,327 s × 36 workers / 684 evaluations of 12 brain s (rate basis in the WP17 report) |
| `camber.build_s` | 250 per task | stage-2 pack sizing |
| `camber.setup_s` | 600 per job | tier-2 completion and stage-2 estimates |
| `camber.running_max_s` | 7,200 | Rolf's rule: jobs under 2 running hours |
| `camber.timeout_s` | 9,000 | command timeout of every tier-2 job |
| `camber.margin` | 1.25 | section 6.4 |
| `camber.slots` | 5 | concurrent jobs per account, GPU nodes included (probe 27470) |

Job shaping. A task is what one worker runs: one engine build, then its probes. One rule fixes every task, and both `scripts/camber/rest_tier3.py` and the table below follow it.

- A task costs `build_s` + `worker_s_per_brain_s` × ρ_mech × its brain s in worker-seconds.
- The makespan limit is (`running_max_s` − `setup_s`) / `margin` = 5,280 s, and every task fits it. A task therefore holds at most B = floor((5,280 − `build_s`) / (`worker_s_per_brain_s` × ρ_mech)) brain s, which is 100 at ρ_mech 1.
- T0: one task per unit or baseline row, holding its ten seeds and both conditions, 60 brain s. Every T0 job holds one extended bare-reference task of the same shape. When B is below 60, each such task is split into tasks of floor(B / 6) whole seeds.
- T1: one task per slice of one unit's seed. A slice is a run of at most floor(B / 12) adjacent weights, 8 at ρ_mech 1, as WP17's completion jobs were.
- T2: one task per candidate, arm, weight and seed. A seed of R-reflex (a) or (b), or of the upstream arm of (c), is a task of 6 brain s, its two 3 s conditions. A seed of R-long is a task of 32 brain s. Every T2 job holds ten upstream bare-reference tasks of 6 brain s, one per seed.
- A plan in which a one-seed task exceeds B is not launched. Its plan record says so, and the coordinator asks Rolf.
- A job's tasks sum to at most `workers` × 5,280 = 190,080 worker-seconds. Jobs are filled in admission order.
- The command timeout is `timeout_s`, and a task's wall cap is twice its planned worker-seconds. For tier 3 these replace section 6.4's Camber cap, which uses `q_plan`.
- Node-hours are worker-seconds / 36 / 3600 plus `setup_s` per job.
- Measured rate. Each T0 task records its wall seconds per brain second after the build. When the median over a sub-tier's T0 tasks exceeds `worker_s_per_brain_s` × ρ_mech × `margin`, that sub-tier's T1 and T2 tasks and jobs are shaped with the median in its place, and the T1 record says so. The cap projection of section 2.6 step 6 keeps `q_plan` × ρ_mech. ρ_mech is a Mac ratio. For `lif+cbi` its `rk4` update may scale differently on Camber's x86 build, so 3c's planned T0 figures carry that known bias until its first T0 job reports (open question 43).

Sizes at ρ_mech 1:

| Stage | Tasks | Brain s | Worker-s | Jobs | Node-hours | Wall at 5 free slots |
|---|---:|---:|---:|---:|---:|---|
| T0, 3a (180 units, 12 baseline rows, 4 bare) | 196 | 11,760 | 637,000 | 4 | 5.58 | 1.4 h |
| T0, 3b (180 units, 4 bare) | 184 | 11,040 | 598,000 | 4 | 5.28 | 1.4 h |
| T0, 3c (45 units, 1 bare) | 46 | 2,760 | 149,500 | 1 | 1.32 | 1.3 h |
| T1, ≤ 40 units × 3 seeds × slices of 8, 8 and 3 weights | 360 | 27,360 | 1,458,000 | 8 | 12.58 | 3.1 h (5 jobs, then 3) |
| T2, ≤ 20 candidates × 36 tasks, 4 jobs × 10 bare tasks | 760 | 9,760 | 678,000 | 4 | 5.90 | 1.5 h |

Brain s per item: a T0 unit or bare reference is 10 seeds × 2 conditions × 3 s = 60. An R-screen unit is 19 weights × 3 seeds × 12 s = 684. A T2 candidate is 476 brain s in 36 tasks: R-reflex (a) at both weights and three seeds (36), (b) at ten seeds (60) and the upstream arm of (c) at ten seeds (60), all in 6 brain-s tasks, and R-long at ten seeds of 32 brain s (320). A 6 brain-s task costs 550 worker-seconds and a 32 brain-s task 1,850. So a T2 job's worker-seconds are 32,800 per candidate plus 5,500 for its bare tasks.

Per sub-tier, at most: 3a 48,880 brain s, 366.6 engine-hours, 16 jobs, 24.06 node-hours, 61.6 credits; 3b 48,160, 361.2, 16, 23.76, 60.8; 3c 39,880, 299.1, 13, 19.80, 50.7. Each sub-tier's Camber wall is about 6 hours at five free slots, plus collection and the decision between stages. Slots shared with other lanes lengthen it.

Sub-tier 3d (WP26, IBM). No new B-mech and no new engine variant. The search is 24 units: (1, 1), (1, 2), (1, 4) × {none, 3a at b 1 mV τ 50 ms} × `g_gaba_kc` {2, 3, 4, 6}. T0 and T1 pack into one wave. Shaping uses the IBM measured rate 45.75 worker-s per brain s, 36 workers, 600 s setup, three boxes at most. At the caps: **27,736 brain s, 353 engine-h, $24.5, about 4.2 h wall**. The section 2.6 cap projection is **259** against 400, using the blend of ρ 1 and the recorded sfa ρ_mech. A 3d plan record stores ρ_mech 1.0 for the scale path; it is not a B-mech value, because 3d has none.

## 7. Live activity view

WP13 built the view (lane lv, final commit 58a99ec, `docs/dashboard.md`). A panel on the dashboard charts, per flushed live window:

- a "whole-network" spike count;
- up to two population rates;
- a raster of up to 64 sampled neurons when windows carry spikes.

The additive route `GET /api/runs/{run_id}/live/{arm}/{seed}/{probe}` returns the NDJSON windows, and the websocket replays them.

The current contract is wrong for Phase 2. `orchestrator/live.py` accumulates counts only for recorded populations, which need not cover the brain and may overlap, so their sum omits some spikes and double-counts others. The displayed rate is a count per window second, not per-neuron Hz.

Phase 2 changes (WP23):

1. Producer (`orchestrator/live.py`), as additive fields under `live_version: 2`:
   - `all_count`, accumulated from the full per-neuron count array, independent of recorded populations;
   - `window_ms`, the actual window duration, including a short final window;
   - `sizes`, the neuron count of each recorded population;
   - `block` and `stimulus`, the open-loop block index and label, or null.

   The runner passes the block through the existing `maybe_emit` call. WP23 edits only that call site in `orchestrator/workers.py`, after WP15 merges.
2. Dashboard:
   - the whole-network series uses `all_count`;
   - population rates are per-neuron Hz, `count / (size × window_ms / 1000)`;
   - a stream without `live_version: 2` keeps its chart, labelled "sum over recorded populations (may overlap, not whole-network)" and "spikes per second, aggregate", never "whole-network" or per-neuron Hz.
3. Additions:
   - a population picker among the probe's recorded populations, so Rolf can watch lamina, medulla, lobula, central complex and steering during a run;
   - a stage strip for open-loop probes that carry `block`: per stage population, the current block's per-neuron rate minus the preceding ambient block's;
   - the substrate label (`bare`, `rest:<id>` or `rest-<tag>:<id>`) in the run header.
4. Tests: overlapping populations, neurons in no recorded population, unequal sizes, an incomplete final window, and a version 1 stream shown with the partial labels.

Phase 2 files never record `spikes: "all"`. Live sampling stays on the LIVE stream (SPEC section 3.6), so recording options never touch experiment randomness.

## 8. Interfaces and work packages

### 8.1 Schema 1.3

`schema/experiment.py` accepts `schema_version` "1.2" or "1.3". A 1.2 file resolves exactly as in Phase 1, and test 0.8 on the Phase 1 invariance fixture must stay canonical and unchanged.

Schema 1.3 with `background: true` differs in these fields:

- `substrate` gains `populations_version`, `transmitters_version` and `visual_version`. The defaults for params, populations, transmitters, drive, dopamine, visual and behaviour are all v0.2.
- `buridan` params: `inject_at` accepts "TuBu", "ER" or "photoreceptors" and defaults from `visual-v0.2.yaml`. `initial_heading` accepts "random" (default) or "stripe_A".
- `open_loop_steering` params: either `azimuths`, which expands to stripe blocks with `transition_s` 1 and `dwell_s` 2, or `blocks`. `blocks` is a list of `{stimulus: "stripe" | "ambient" | "dark", azimuth_deg: float | null, distractor: {azimuth, flicker_hz, contrast} | null, transition_s, dwell_s}`. `azimuth_deg` is required for "stripe"; for the held fly the distractor azimuth is fly-relative. `duration_s` must equal the sum of `transition_s + dwell_s` over blocks.
- `spontaneous` params: `stimulus` "dark" (default) or "ambient".
- `genotype.named`: the eleven names of section 4.2.
- Settle follows section 2.4.

Schema 1.3 with `background: false` is bare-compatible:

- Every defaulted field resolves to its schema 1.2 value: params, populations, dopamine and behaviour v0.1; drive, transmitters and visual null; `inject_at` "TuBu"; `initial_heading` "stripe_A"; the Phase 1 settle rule; `substrate_id` `bare`.
- A file that sets a 1.3-only feature is rejected: photoreceptor injection, `blocks`, random heading, a `stimulus` other than "dark", a v0.2 pin, or a named genotype new in 1.3.
- Test 0.14 checks the named twin fixtures bitwise.

The single exception is `apply_scales_without_background: true` together with a `drive-v0.2` pin. It is valid only in a fixture a validation entry declares (`ff-candidate.json`), and it makes any other file development. Such a fixture resolves exactly like its bare twin (`ff-bare.json`), except that the drive configuration's transmitter rule, scales and mechanism are applied. The mechanism sets the engine model at build (section 2.2.4); the bare twin always builds `lif`.

Topology (`orchestrator/phases.py`). `R1_6` enters `extended_idx` when any resolved probe of the experiment needs photoreceptor input:

- a Buridan probe whose resolved `inject_at` is "photoreceptors", with the encoder on or off;
- an open-loop probe under a photoreceptor visual configuration;
- a `spontaneous` probe with `stimulus: ambient`.

Otherwise the Phase 1 topology rule applies unchanged. `build_topology` receives the resolved params and visual configuration of the run instead of loading default params.

Configuration loaders (WP15). The v0.2 behaviour loader reads encoder settings (`r_light`, or `r_vis_max` and `sigma_vis`) only from the pinned visual file, and runtime steering values (`v_fwd_mm_s`, `step_min_mm`, `r_max_hz`, `sign_steer`, `bias_hz`, `K_steer`) only from the pinned behaviour file, `base-v0.2` or `v0.2`. Two kinds of calibration fixture are the only exceptions:

- Encoder-grid fixtures (R3, V-cal, VT-cal) pin no visual file. They supply the grid value (`r_light` or `r_vis_max`) as explicit metadata, and the other encoder settings come from `params-v0.2.yaml`. They may contain only open-loop and spontaneous probes.
- K-grid fixtures (`k3r.json`, `k3r-tubu.json`) pin `base-v0.2` and the committed visual file. They take `sign_steer` and `bias_hz` from their committed metadata and `K_steer` from their declared grid. They may run Buridan probes.

The loader rejects:

- a `behaviour-v0.2.yaml` or K-grid fixture whose `visual` blob id differs from the git blob id of the pinned visual file's bytes;
- a Buridan probe in any file pinning `base-v0.2` other than a K-grid fixture, or pinning a behaviour file with `controller: open_loop`;
- a K-grid fixture with no visual pin, missing or non-finite `sign_steer` or `bias_hz`, a `sign_steer` other than ±1, or a grid on anything other than `K_steer`;
- an encoder-grid fixture that pins a visual file or contains a Buridan probe;
- a grid value outside its fixture's declared grid;
- a missing or non-finite runtime value.

The dopamine loader takes `R_c`, `alpha_c` and `S_c` from `dopamine-v0.2.yaml` and checks `compartments` against the registry order.

`tests/test_p2_config_loaders.py` runs the real loaders and factories with no `validation/` directory present, on constructed configuration sets:

- photoreceptor closed loop;
- TuBu closed loop;
- open loop straight after V-cal and VT-cal failure, where only the base, visual and `open_loop` behaviour files exist;
- the pre-steering stages pinning `base-v0.2`, including V-cal and VT-cal with no visual file;
- successful K3r and K3r-T fixtures, where each declared `K_steer` value builds a Buridan behaviour whose sign, bias, K, runtime values and encoder settings equal the metadata, grid point, base file and visual file;
- each rejection above, including a K-grid fixture with incomplete metadata, an undeclared `K_steer` value, a missing visual pin and a mismatched visual blob id.

### 8.2 Parameters v0.2

`data/params-v0.2.yaml` contains every v0.1 row with the item 63 authority notes folded in, plus the rows below. A v0.1 value differs in v0.2 only where the table says "changed" (test 0.12).

| Name | Value | Unit | Source | Range | Level |
|---|---|---|---|---|---|
| transmitters.scope | brain | — | design choice (open question 4) | brain, optic_sensory | 2 |
| drive.g_gaba, drive.g_glu | section 2.6 | ratio | `drive-v0.2.yaml` | 1 to 8 | 2 |
| drive.g_his | 1 | ratio | design choice; `r_light` carries the gain | fixed | 2, V |
| drive.w_bg[group] | section 2.6, then K1r | mV | `drive-v0.2.yaml` | 0.70 to 1.60 | 2 |
| drive.sigma_th | 0 unless tier 2 | mV | design choice | 0, 1, 2 | 2 |
| drive.optic_exemption | false unless tier 2 | flag | design choice | false, true | 2 |
| drive.seed | the seed the evaluations used, recorded in each drive file (20260912 for tier 2 and `data/drive-dev-p2.yaml`; review r14c, decision 45) | — | design choice | per file | 2 |
| rest.fano_max, rest.bin_fraction_max | 3, 0.05 | 1, fraction | items 43 and 46 | fixed | 2 |
| rest.stability_ratio | [0.5, 2] | ratio | item 43 | fixed | 2 |
| rest.central_hz | [0.5, 8] | Hz | item 35 cap; floor is a design choice | fixed | 2 |
| rest.dan_hz | [0.5, 10] | Hz | placeholder band; tonic DAN firing reported at 1 to 10 Hz | fixed | 2, 3 |
| rest.kc_max_hz | 2 | Hz | design choice; KCs are sparse | fixed | 2 |
| rest.grade_factor | 3 | ratio | item 43 | fixed | 2 |
| rest.screen_seeds, rest.settle_s, rest.measure_s | 3, 2, 10 | 1, s, s | item 43 | fixed | 2 |
| rest.long_seeds, rest.long_measure_s, rest.long_edge_s | 10, 30, 5 | 1, s, s | design choice | fixed | 2 |
| rest.reflex_mean_hz, rest.reflex_seed_min_hz | 50, 40 | Hz | item 61 | fixed | 1, 2 |
| rest.ff_retention_min | 0.5 | fraction of the matched bare response | design choice (open question 11) | fixed | 1, 2 |
| rest.weight_step_mv | 0.05 | mV | item 35 grid | fixed | 2 |
| rest.max_candidates, rest.r3_max, rest.qrest_max_candidates | 20, 6, 3 | 1 | design choice | fixed | 2 |
| rest.violation_cap, rest.j_bin | 10, 0.25 | 1 | design choice | fixed | 2 |
| rest.tier2_cap_engine_hours | 265 | engine-hours | section 6.3 | fixed | 2 |
| k1r.bound_mv, k1r.min_improvement | 0.10, 0.20 | mV, fraction of J | design choice | fixed | 2 |
| k2r.max_iterations | 3 | 1 | design choice | fixed | 3 |
| settle.window_s_13, settle.blocks | 1.0, 5 | s, 1 | design choice (section 2.4) | fixed | 2, 3 |
| settle.tol_abs_rate_13 | 0.02 | Hz | design choice (section 2.4) | fixed | 2, 3 |
| settle.fano_ref, settle.k_resolve | 3, 5 | 1, 1 | design choice (section 2.4) | fixed | 2, 3 |
| settle.t_quantile | 1.860 | 1 | one-sided 95 percent, 8 degrees of freedom | fixed | 2, 3 |
| detector.da_gap_fraction | 0.25 | fraction of fixed point | design choice | fixed | 3 |
| vis.inject_at | photoreceptors (changed; `visual-v0.2.yaml` is authoritative) | population | section 3.2 | TuBu fallback | 4 |
| vis.pr_rate_light_hz | V-cal | Hz input rate | V-cal grid {50, 100, 150, 300}, extension {25, 10} | 10 to 300 | V, 4 |
| vis.pr_rate_dark_hz | 0 | Hz | design choice | fixed | V, 4 |
| vis.pr_acceptance_deg | 5 | deg | placeholder, near the interommatidial angle | 3 to 8 | V, 4 |
| vis.column_halfwidth_deg, vis.max_column_spread_deg | 10, 20 | deg | design choice (section 3.3) | fixed | V |
| vpath.min_delta_hz | 0.5 | Hz | design choice | fixed | V |
| steer.K_steer grid | {1, 2, 4, 8, 16} | deg/s per Hz | K3r | 1 to 16 | 4 |
| arena.initial_heading | random | — | design choice (item 42 artefact) | random, stripe_A | 4 |
| pred.fi_min_effect, pred.dev_min_effect, pred.switch_min_effect, pred.rate_min_effect | 0.05, 5, 0.1, 0.1 | 1, deg, 1, Hz | design choice | fixed | 3, 4 |
| pred.steer_gain_min_effect, pred.capture_min_effect | 0.002, 0.2 | Hz/deg, Hz | design choice | fixed | 4 |
| pred.bootstrap_n | 10,000 | resamples | design choice | fixed | all |
| ign.window_s, ign.factor, ign.max_central_hz, ign.min_baseline_hz | 1, 3, 8, 0.5 | s, ratio, Hz, Hz | design choice (section 9.2); floor is item 87 | fixed | 2 |
| offrest.factor | 2 | ratio | design choice | fixed | 2 |
| bias.max_fraction | 0.5 | fraction of tuning range | design choice | fixed | 4 |
| q_plan | 27 | wall s per brain s per engine | B1 18 × 1.5 allowance | replaced by measurement | none |
| camber.engines_per_node, camber.rho | 62, 1.0 | 1, ratio | planning figures until the proof lane reports | — | none |
| budget.q1_escalation | 30 | wall s per brain s | design choice | fixed | all |
| budget.plan_settle_s | 2 | s per probe | `settle.min_s`, for estimates only | fixed | none |

`data/rest-tier3-v0.2.yaml` (WP24) holds the tier-3 search rows below and the `camber.*` rows of section 6.5. Only tier-3 stages read it. `params-v0.2.yaml` does not change, so no entry that reads it goes stale. The loader bounds of section 2.2.4 (adaptation tau at least 2 × max(`lif.t_mbr`, `lif.tau`), E_inh at most `lif.v_0` − 1 mV) are computed in code from the pinned params, not configured.

| Name | Value | Unit | Source |
|---|---|---|---|
| tier3.pairs | the 15 pairs of P3 | ratio | section 2.2.4 |
| tier3.baseline_pairs | the 12 pairs of P3 with g_gaba ≤ 2 | ratio | section 2.6 step 6 |
| tier3.weights_mv | 0.70 to 1.60 in steps of 0.05 | mV | tier-1 grid |
| tier3.fixed | `sigma_th` 0, `optic_exemption` false, `n_bg` 100 | mV, flag, inputs | section 2.2.4 |
| tier3.sfa | `b_mv` {0.1, 0.3, 1, 3} × `tau_ms` {50, 150, 500}, scope `non_sensory` | mV, ms | design choice; no measured constant |
| tier3.std | scope {`non_sensory_excitatory`, `non_sensory`} × `U` {0.05, 0.2, 0.5} × `tau_ms` {100, 400} | 1, ms | design choice; no measured constant |
| tier3.cbi | `E_inh_mv` {−72, −62, −57}, scope `all` | mV | design choice; no measured constant |
| tier3.t1_max_units | 40 | units per sub-tier | design choice (section 6.5 wall) |
| tier3.cap_engine_hours | 400 | engine-hours per sub-tier, at `q_plan` 27 × ρ_mech | section 6.5 |
| tier3.cbi_stiff_limit | 0.1 | `lif.dt` × (1 + h_max) / `lif.t_mbr` | about ten `rk4` steps per effective membrane time constant (section 2.2.4) |
| tier3.gaba_kc | pairs (1, 1), (1, 2), (1, 4); `g_gaba_kc` {2, 3, 4, 6}; sfa {null, b 1 mV τ 50 ms} | ratio, 1, mV·ms | WP26 option C; KC-targeted GABA scale (section 2.2.4 3d) |
| ibm.workers | 36 | workers per `cx2-64x128` | WP25 port proof |
| ibm.worker_s_per_brain_s | 45.75 | worker-s per brain s | WP25 smoke2, after build |
| ibm.setup_s | 600 | s per box | section 6.5 `camber.setup_s` |

### 8.3 Configuration, fixture and evidence files

| File | Kind | Writer | Committed |
|---|---|---|---|
| `data/transmitters-v0.2.yaml` | configuration | WP14 | WP14 gate |
| `data/populations-v0.2.yaml` (v0.1 plus stage populations and retinotopy tables) | configuration | WP14 | WP14 gate |
| `data/params-v0.2.yaml` | configuration | WP15 | WP15 gate |
| `data/drive-v0.2.yaml` | configuration | WP19 | after K1r, per section 2.5 |
| `data/dopamine-v0.2.yaml` | configuration | WP19 | after K2r and each K2r iteration |
| `data/rest-tier3-v0.2.yaml` | configuration (tier-3 search constants) | WP24 | G-3a |
| `data/drive-dev-t3.yaml` | development configuration | WP24 | when a sub-tier ends empty and the coordinator asks |
| `data/visual-v0.2.yaml` | configuration | WP18 (V-cal commit), WP20 (section 3.7 steps 2 and 3) | after V-cal or VT-cal, and at each section 3.7 encoder change |
| `data/behaviour-base-v0.2.yaml` | configuration | WP15 | WP15 gate |
| `data/experiments/p2/k3r.json`, `k3r-tubu.json` | calibration fixture | WP20 | after bias and sign check |
| `data/behaviour-v0.2.yaml` | configuration | WP20 | after K3r or K3r-T (`closed_loop`), or after the open-loop bias (`open_loop`) |
| `data/experiments/p2/holdout-p2.json`, `holdout-p2-tubu.json` | fixture | WP22 | WP22 gate, before integration |
| `data/experiments/p2/*.json`, `tests/fixtures/experiments/*.json` | fixture | the WP owning the entry | its gate |
| `tests/fixtures/frozen-v0.1.json`, `tests/fixtures/io-allowlist.json` | fixture | WP16 | WP16 gate |
| `tests/fixtures/wp24-off-reference.json` | fixture | WP24 | WP24's first commit, before any engine edit |
| `tests/fixtures/engine/fixture-0-16.json` | fixture | WP24 | G-3a |
| `tests/fixtures/engine/fixture-0-17.json`, `fixture-0-18.json`, `tiny_std_*`, `tiny_cbi_*` | fixture | WP24 | G-3b, G-3c |
| `validation/status.json`, `validation/records/p2/*.json` | evidence | the stage or entry owner | evidence commits |
| `validation/records/p2/rest-T3{a,b,c,d}-{plan,T0,T1,T2,decision}.json`, `bench-mech-{sfa,std,cbi}.json` | evidence | WP24, WP26 (3d) | the plan record before launch; the rest in evidence commits |
| `docs/transmitter-census.md`, `docs/resting-candidates.md`, `docs/*-p2.md`, `docs/phase2-results.md`, `docs/tier3-mechanisms.md` | evidence | the owning WP | evidence commits |

### 8.4 Work packages

Every lane works in its own worktree from `main` after the r12 merge, commits only its owned files, never pushes, and reports at `.reports/WP<N>-report.md` with `Final commit: <sha>`, gates with timings, measured wall against budget, and deviations. Mac engine work follows section 6.1. Camber lanes keep `.reports/camber-ledger.md`.

| WP | Content | Owner files | Depends on | Gate |
|---|---|---|---|---|
| WP14 | Transmitter census, scale composition, retinotopy, stage populations (no engine) | `substrate/__init__.py`, `substrate/transmitters.py`, `substrate/scales.py`, `substrate/retinotopy.py`, `data/transmitters-v0.2.yaml`, `data/populations-v0.2.yaml`, `docs/transmitter-census.md`, `validation/level0_substrate.py` (0.10 pure leg), their tests | main | 0.10 pure leg passed; section 2.2.1 tables reproduced from the files; median column spread per type reported |
| WP16 | Binding, dependency log, platform, detectors | `io.py`; the read-call conversion to `io.py` in existing modules, as a first mechanical commit merged before WP15 starts; `validation/binding.py` (per-entry inputs, `qualification_of`); `validation/artefacts.py`; `scripts/run_validation.py` (log merge, `--only`, one-use entries and `--holdout`); `tests/fixtures/frozen-v0.1.json`; `tests/fixtures/io-allowlist.json`; `validation/level0_binding.py` (0.9r, 0.12); their tests | r12 merged | conversion commit merged; 0.9r (a) to (d) and 0.12 passed; static check clean; a constructed one-use entry is carried forward by regeneration and executes only under `--holdout` with a passing readiness check |
| WP15 | Rest-substrate plumbing and integration seams | `drive/rest.py` (v0.2 loaders, `apply_rest_substrate`); `orchestrator/workers.py` (drive block); `orchestrator/runner.py` (identity, manifest, `qualification_of` in place of record flags); `orchestrator/phases.py` (topology rule, resolved params and visual configuration, blocks and ambient stimuli); `orchestrator/components.py` and `behaviour/__init__.py` (factories take resolved configuration objects, encoder dispatch by `inject_at`, v0.2 settings); `behaviour/arena.py` (initial heading, bias in omega); `schema/experiment.py` (1.3, bare compatibility); `types.py` (Params v0.2); `data/params-v0.2.yaml`; `data/behaviour-base-v0.2.yaml`; the v0.2 behaviour and dopamine loaders with the section 8.1 checks; `tests/test_p2_config_loaders.py`; `neuromod/state.py` (settle rule, per-neuron base threshold in `compose`, per-compartment `alpha_c` and `S_c` in reset and chunks); `registry/__init__.py` (version pass-through, derived-population hook in `build_registry`); `registry/derived.py` (`DA_exposed`); `scripts/calibrate.py` (`--phase 2` order, resumable records); `validation/level0_rest.py` (0.10 engine leg, 0.11, 0.13, 0.14); `tests/fixtures/experiments/bare-twin-1.2.json`, `bare-twin-1.3.json`; their tests | WP16 conversion commit; WP14 `scale_array` signature | 0.10 engine leg, 0.11, 0.13 and 0.14 passed; loader test passed for every section 8.1 configuration set; 0.8 canonical and unchanged; integration tests pass for Phase 2 stage dispatch and resume, resolved-stimulus topology, derived populations, persistent threshold composition and per-compartment source integration |
| WP17 | Rest map round 2 and decision rule | `drive/rest_map.py` (driver, R-screen, R-reflex, R-long, S, J, order key, `STAGE` R1 and R2); `scripts/camber/rest_screen.py`; `scripts/camber/rest_screen.sh`; `docs/resting-candidates.md`; `tests/test_rest_decision.py`; their tests | WP14; lane cam's staging scripts (Mac fallback otherwise); the cam map report if landed | ranked list and shortlist, or escalation, recorded under section 2.6; decision tests pass; every evaluation line carries job id, commit, `code_scope`, platform |
| WP18 | Photoreceptor encoder and visual path v2 | `behaviour/encoder.py` (photoreceptor class behind WP15's dispatch); `behaviour/visual_calibration.py` (`STAGE` R3 and V-cal); `diagnostics/visual_path.py` v2; `scripts/diagnose_visual_path.py`; `validation/levelv.py` (V0 to V3, V-cal); `data/experiments/p2/vpath-*.json`; `data/visual-v0.2.yaml` (V-cal commit); `docs/visual-path-p2.md`; their tests | code: WP14, WP15; R3: WP17 shortlist; V-cal: WP19 Q-rest | V0 passed; R3 table recorded; V-cal outcome recorded, and on selection the visual commit made and V1 and V3 passed |
| WP19 | Rest calibration chain and Q-rest | `scripts/bench.py` (first owner: B1-rest and B2-rest modes, `--plan`); `drive/rest_calibration.py` (`STAGE` R4, K1r, Q-rest, drive commit); `neuromod/calibration.py` (K2r, `STAGE` K2r, dopamine commit); `data/drive-v0.2.yaml`; `data/dopamine-v0.2.yaml`; `validation/levelrest.py` (1.3r, 1.4r, 1.4r-ff, 2.1r to 2.7r, 3.1r, 3.1r-alg, 3.1br); `data/experiments/p2/rest-*.json`, `ff-bare.json`, `ff-candidate.json`; `docs/calibration-p2.md`; their tests | WP15, WP16, WP17 ranked list, r13 | B1-rest and B2-rest recorded; `--plan` prints the section 6.3 factors for a constructed file; Q-rest passed on committed configurations, or the fall-through or escalation recorded |
| WP20 | Steering, closed loop and TuBu fallback | `behaviour/buridan.py` (bias, sign check, K3r and -T stages, VT-cal); `behaviour/metrics.py`; `data/behaviour-v0.2.yaml`; `data/visual-v0.2.yaml` (commits under section 3.7 steps 2 and 3); `validation/level4_p2.py` (4.0c, bias, 4.1r-sign, K3r, 4.1r, 4.2r, 4.4r to 4.8r, -T variants, VT-cal, V1-T); `data/experiments/p2/{bias,signcheck,k3r,k3r-tubu,buridan-controls}.json`; `scripts/camber/k3r.py`; `validation/records/p2/visual-status.json`; `docs/behaviour-p2.md`; their tests | WP18 V-cal outcome, WP19 Q-rest | visual status set under section 3.7 with its required records, and `behaviour-v0.2.yaml` committed in the form that status needs |
| WP21 | Pharmacology and ADHD manipulations | `schema/named.py`; `analysis/__init__.py`; `analysis/contrasts.py` (status words, rescue index, contrast tables); `validation/level3_p2.py` (3.2r to 3.10r, 4.9 to 4.11); `data/experiments/p2/{coupling,coupling-sweep,dose-p2}.json` and `{ablation-p2,pharm-*}` in both probe forms; `tests/test_p2_plan_pharm.py`; `scripts/camber/pharm.py`; `docs/pharmacology-p2.md`; their tests | code: WP15; neural half: WP19; behaviour half: WP20 | 3.10r executed; 3.2r to 3.5r passed; P-screen and canonical tables written with every contrast and the contrast count |
| WP22 | Integration, holdout and acceptance | `data/experiments/p2/acceptance-p2.json`, `acceptance-p2-tubu.json`, `acceptance-p2-openloop.json`; `scripts/holdout_ready.py`; `validation/level4_holdout.py` (4.3r, 4.3r-T, 4.3r-replay); `data/experiments/p2/holdout-p2.json`, `holdout-p2-tubu.json`; `scripts/bench.py` (B2-P2 mode, after WP19); `tests/test_p2_plan_acceptance.py`; `docs/bench.md` (P2 rows); `orchestrator/runner.py` (summary block only); `validation/status.json` (regeneration); `server/mcp_server.py` and `dashboard/app.py` (additive substrate fields, after WP23); `docs/phase2-results.md` | WP20, WP21, WP23, Phase 1 closure, r13 to r16 | readiness check passed or its failure recorded; 4.3r executed at most once; outcome set under section 1.5 |
| WP23 | Live view contract and additions | `orchestrator/live.py`; the `maybe_emit` call site in `orchestrator/workers.py`, after WP15; `dashboard/static/*`; `dashboard/app.py` (additive routes); `tests/test_live_producer.py`; `tests/test_dashboard_live*.py`; `docs/dashboard.md` | WP13 merged, WP15 | section 7 tests pass; version 1 streams carry the partial labels |
| WP24 | Tier 3 structural rest mechanisms (section 2.2.4, section 2.6 step 6) | `engine/base.py` (`build` signature, `Mechanisms`, `MechanismTraceTable`, `ChunkResult.h_max`); `engine/models.py` (new: variant strings, `Mechanisms`); `engine/brian_engine.py` (variant choice in `build`, `engine_model`, `model_strings`, `method`, `mechanism_traces`, h_max, the depression refractory guard); `drive/mechanisms.py` (new: section loader, scope masks, `engine_model_of`, `mechanisms_section`, `mechanisms_from_unit`, `mechanisms_from_drive`, `substrate_id_for`); `drive/rest.py` (top-level key list, `mechanisms` in the loader's result, the `mechanisms` requirement and engine-model guard in `apply_rest_substrate`); `drive/rest_tier3.py` (new: T0 to T2, admission, tier-3 order key, closest miss, flags, ranked-list rows, decision, `STAGE` T3a to T3c); `drive/rest_map.py` (in `_build_engine` only: the mechanism passed to `build` and stated to `apply_rest_substrate`, and MN9 added to `trace_idx` under `lif+sfa`); `drive/rest_calibration.py` (only the section 2.5 path: `substrate_id_for` in place of its substrate-id literal; `r2_path` reading the sub-tier decision record that holds a tier-3 ranked list; `ranked_candidates` keeping `engine_model` and `mechanisms` in the row and the identifier; `make_drive` writing the section; `_candidate_drive` stating it; `_worker` passing `mechanisms_from_drive` to its `engine.build(` call; R4 and the drive commit refusing a record with `mechanism not in force`); `orchestrator/workers.py` (drive file loaded before build, `mechanisms_from_drive` passed to its `engine.build(` call); `orchestrator/runner.py` (`substrate_id_of` through `substrate_id_for`, `engine_model` and `mechanisms` manifest fields); `validation/binding.py` (`engine_model` identity field and the two section 5.1 validity clauses); `validation/level0_rest.py` and `tests/test_p2_rest.py` (the `mechanisms` key at their `apply_rest_substrate` calls, only); `behaviour/visual_calibration.py` (only under the shared-file rule below); `schema/experiment.py` (mechanism-pin rejections of section 5.1); `scripts/camber/rest_tier3.py` and `rest_tier3.sh` (new); `scripts/bench.py` (`--mech sfa|std|cbi` mode only); `validation/level0_mech.py` (new: 0.15 to 0.18); `data/rest-tier3-v0.2.yaml`; `data/drive-dev-t3.yaml`; `tests/fixtures/wp24-off-reference.json`; `tests/fixtures/engine/fixture-0-16.json`, `fixture-0-17.json`, `fixture-0-18.json`, `tiny_std_*` and `tiny_cbi_*`; `tests/test_mechanisms_loader.py`; `tests/test_rest_tier3_decision.py`; `docs/tier3-mechanisms.md` (new, sections listed below); the tier-3 sections of `docs/resting-candidates.md`; the B-mech rows of `docs/bench.md`; the tier-3 and B-mech records; their tests | Rolf's authorisation (2026-09-16); this revision signed off; r14b merged (`lane/w17`, `lane/w19`) | G-3a, G-3b and G-3c, below |

Shared files, each with a fixed order:

- `orchestrator/runner.py`: WP15 owns identity and manifest; WP22 later owns only the summary block; WP24 later changes only `substrate_id_of` and adds the `engine_model` and `mechanisms` manifest fields.
- `orchestrator/workers.py`: WP15 owns the drive block; WP23 later owns only the `maybe_emit` call site; WP24 later edits only the drive block and the `engine.build(` call beside it.
- `data/visual-v0.2.yaml`: WP18 makes the V-cal commit; WP20 makes every commit under section 3.7 steps 2 and 3.
- `scripts/bench.py`: WP19 adds B1-rest, B2-rest and `--plan`; WP22 later adds only the B2-P2 mode; WP24 adds only `--mech`.
- `engine/base.py`, `engine/models.py`, `engine/brian_engine.py`: WP24 only, in Phase 2.
- `drive/rest.py`: WP15 owns the v0.2 loaders; WP24 later adds only the top-level key list and the engine-model guard.
- `drive/rest_map.py` (WP17) and `drive/rest_calibration.py` (WP19): WP24 edits them only after r14b merges, and only as its row says.
- `behaviour/visual_calibration.py`: WP18 owns it. R3's engine screen builds each candidate from a drive document that carries the row's mechanism (section 2.5). If that screen already exists without it when WP24 lands, WP24 changes only its `engine.build(` calls and the documents they apply, and its report lists the change.
- `validation/level0_rest.py` and `tests/test_p2_rest.py`: WP15; WP24 later adds only the `mechanisms` key at their `apply_rest_substrate` calls.
- `validation/binding.py`: WP16; WP24 later adds only the `engine_model` field and its validity clause.
- `schema/experiment.py`: WP15; WP24 later adds only the mechanism-pin rejections.
- `docs/resting-candidates.md`: WP17; WP24 appends only tier-3 sections. `docs/bench.md`: WP22 owns the P2 rows; WP24 adds only B-mech rows.
- `scripts/run_validation.py`: WP16 only; WP22 calls `--holdout` without editing it.
- WP16's read-call conversion touches modules other WPs later own. It lands first and changes no behaviour.

Reviews:

- r13 covers WP14, WP15 and WP16, before WP19's first configuration commit.
- r14 covers WP17 and WP19. A change it forces stales later entries through the binding rule, and they rerun.
- r15 covers WP18 and WP20.
- r16 covers WP21 and WP23.
- r17 covers WP22.
- r18a, r18b and r18c cover WP24 at G-3a, G-3b and G-3c. Each starts at its gate and runs beside that sub-tier's development search. It must pass before the first configuration commit of a drive file with that mechanism. A review change to a variant's model strings, method or `on_pre` reruns that sub-tier's search (open question 34).

The holdout waits for r16 (section 3.8).

WP24 gates, each timed in the report:

- G-3a, before the 3a search, in commits whose order the history shows, none squashed into another:
  1. `tests/fixtures/wp24-off-reference.json`, `tests/fixtures/engine/fixture-0-16.json` and the recording code in `validation/level0_mech.py`, with no change under `engine/`, `drive/` or `orchestrator/`, recorded with the execution platform in their identities under test 0.15 (b).
  2. `engine/models.py` with the `lif` strings, `build`'s `mechanisms=None` default and the engine interface, with no variant other than `lif`. 0.15 (a) to (c) and the full suite pass against commit 1.
  3. `lif+sfa` and test 0.16. 0.15 and the full suite still pass.

  Later commits add the rest of the row, and each passes 0.15 and the full suite. At the gate: `uv sync --frozen` succeeds; the not-slow suite, 0.15 (d), 0.16 and `tests/test_rest_tier3_decision.py` pass; B-mech for `lif+sfa` is recorded; and `rest-T3a-plan.json` is committed with ρ_mech, units and job shapes under section 6.5.
- G-3b, before the 3b search: 0.17 passes, B-mech for `lif+std` is recorded, `rest-T3b-plan.json` is committed, and 0.15 and the full suite still pass on the G-3b commit.
- G-3c, before the 3c search: the same with 0.18, `lif+cbi` and `rest-T3c-plan.json`.

The full suite in these gates is the not-slow suite plus 0.3, 0.4, 0.8, 0.10-engine, 0.11, 0.13, 0.14 and 0.15 (a) to (c). It does not include 1.4 or any Camber run.

G-3b and G-3c code is written on the Mac while 3a runs, so each next sub-tier can launch as soon as the one before ends empty. Every tier-3 Camber job follows section 6.2's staging, ledger and polling rules.

The WP24 report (`.reports/WP24-report.md`) contains:

- the final commit;
- each gate with timings;
- every `engine.build(` and `apply_rest_substrate(` call site in `src/`, `scripts/` and `tests/`, and whether it passes or states a drive document's mechanisms;
- the B-mech table and ρ_mech per engine model;
- per sub-tier, the T0, T1 and T2 tables: units, passers, candidates, closest misses, flags and the failed stage;
- the Camber ledger rows;
- measured wall and node-hours against section 6.5;
- deviations.

`docs/tier3-mechanisms.md` has these sections: the variant strings and methods as built, with the `lif` fixture hashes; the engine interface as built; tests 0.15 to 0.18 with the largest errors reached; the B-mech table per engine model; per sub-tier, the plan, the T0, T1 and T2 summaries with flags, and the decision; the call-site table of the report.

### 8.5 Schedule

Day 0 is spec sign-off plus Rolf's answers to the open questions that change work (1 to 5, 11, 12 and 13). Wall figures come from section 6.3.

- Day 0: WP14, WP16 (conversion commit first) and WP23 start. WP18 and WP21 start code against sections 8.1 and 4.
- Day 0.5: WP14 and the WP16 conversion land, and WP15 starts. WP17 launches R1 on Camber, and the first resting numbers come back within about two hours of launch.
- Day 1: WP17 finishes R-reflex and R-long and commits the ranked list, the first resting-substrate result. WP18 starts R3.
- Day 1.5: WP15 and WP16 land, then r13.
- Day 2: WP19 runs B1-rest, K1r (about 2 h on one engine), the drive commit, K2r, the dopamine commit and Q-rest (about 1 h): the first configured rest substrate.
- Day 2.5: WP18 runs V-cal and commits the visual configuration. WP21 starts its neural half, and r14 starts.
- Day 3: WP20 runs bias, sign check, K3r (Camber, then the Mac finalists), the behaviour commit, 4.1r and 4.2r, with 4.8r on Camber.
- Days 3.5 to 5: WP21 runs the P-screen, 3.9r, 4.11 and the canonical predictions (about 11 h at 5 workers on the Mac timing basis). r15 follows WP20.
- Days 5 to 6.5: r16, then WP22 runs integration, status regeneration, the readiness check, 4.3r, B2-P2 and the acceptance pair, and writes the results. r17 follows.

Tier 2 adds about one day before day 2. A section 3.7 step-1 fall-through adds about a day, the TuBu path about half a day, and the open-loop branch about a day of Mac time for its longer probes. Mac slots shared by WP19, WP20 and WP21 set the pace on days 2.5 to 5; more granted workers shorten them.

Tier 3 (WP24). Rolf authorised it on 2026-09-16, after tier 2 ended empty. Its time comes before day 2 above, since every later day needs a rest substrate:

- Start: this revision is signed off, r14b merges, and the WP24 implementation lane starts from main.
- About one day after the start: G-3a (engine variant, tests 0.15 and 0.16, B-mech, plan record) is reached, and 3a goes to Camber. T0 takes about 1.5 h, T1 about 3 h and T2 about 1.5 h, so about 8 h with collection and decisions. r18a runs beside it, and G-3b and G-3c code proceeds on the Mac.
- A 3a ranked list feeds R3 (WP18) and R4, K1r, K2r and Q-rest (WP19), after r18a; day 2 above starts then.
- An empty 3a adds about 8 h for 3b, and an empty 3b about 8 h more for 3c.

Lanes keep developing on `data/drive-dev-p2.yaml` meanwhile.

## 9. Risks and artefact detectors

### 9.1 Risks

1. No candidate qualifies after tier 2. This happened, and Rolf authorised tier 3 (section 2.6 step 6). P2-partial-B holds if tier 3d ends empty.
2. Rest and the reflex conflict again (item 47). The reflex sits inside the screen, tier 2 targets the best reflex candidates, and the allowed feed-forward loss is Rolf's call (open question 11).
3. The visual path blocks somewhere other than the lamina. The LIF network cannot compute motion, so the model steers on bar position. V1 locates the break, and section 3.7 bounds the outcome.
4. The WP10 left-only DNa02_L leak, or another asymmetry, becomes a constant turn. Bias subtraction handles it, and the bias detector watches it.
5. Platforms disagree near the ignition edge. Brian2 Cython builds on different CPUs and compilers do not match bit for bit, and small differences can flip a criterion near the edge. Test 2.6r demands margin, and the platform-agreement detector reports flips.
6. Camber credits run out on a free trial with no balance command. The ledger, the caps and the Mac fallbacks cover it.
7. The receptor constants are placeholders, and modulation may be too weak to change rates. 3.10r sets the coupling status, and 3.9r locates the lever (section 4.7).
8. The busier substrate runs slower. B1-rest escalates above 30 wall s per brain s.
9. A correction after the holdout makes P2 unreachable. The holdout waits for integration and review (section 3.8).
10. Many contrasts make chance findings likely. Every contrast is counted and reported, and the headline is pre-registered.
11. Glutamate is excitatory at some real synapses, while the transmitter rule makes every glutamatergic output inhibitory. This is a model assumption; the census lists the glutamate-heavy central populations the rule touches.
12. Curated annotations cover a minority of neurons and can be wrong. The scope option (open question 4) limits the correction if the census shows surprises.
13. Block-scale fluctuation on the rest substrate may exceed `settle.fano_ref`, leaving probes unsettled. 2.3r records block Fano and requires every Q-rest probe to settle, so this shows up in WP19, not at acceptance.
14. The model is a female brain without a nerve cord. Behaviour goes through the descending-neuron steering proxy, as in Phase 1.
15. A mechanism strong enough to quiet the network also costs the sustained reflex window at every non-sensory stage. T0 measures that cost on every unit before anything else runs, and the 3a baseline rows show how much of the loss comes from scaling alone.
16. Conductance-based inhibition under `rk4` loses accuracy where inhibitory conductance is large. Probes record h_max, and flagged evaluations count as not computable.
17. A checkout from before WP24 ignores a drive file's `mechanisms` section and runs `lif`. Identity keeps its records apart (section 5.1).
18. Tier 3 costs Camber wall time: about 8 hours per sub-tier at five free slots, about a day if 3c is reached, with no Mac fallback in the schedule. Slots shared with other lanes lengthen it.

### 9.2 Artefact detectors (`validation/artefacts.py`)

Carried from SPEC section 9.2:

- completeness;
- synchrony (F and b);
- weight jitter;
- the encoder permutation, now three within-eye shuffles of the R1-6 azimuth table. A 4.2r conclusion that survives every shuffle is reported "not retinotopic".
- the label check, now also reporting per recorded population the fraction of neurons whose curated and predicted signs disagree, flagging any population above 10 percent.

Added:

- Ignition. During any recorded probe on the rest substrate, a 1 s window with central rate above `ign.factor` × the settled central mean flags the run `ignited` only when the settled central mean is at or above `ign.min_baseline_hz`; a 1 s window above `ign.max_central_hz` flags it unconditionally (item 87). An ignited canonical run fails acceptance clause 3.
- Off-rest. At the end of settle, a wild-type vehicle probe with central, DAN, KC or optic per-neuron rate outside a factor of `offrest.factor` of the Q-rest free-pool rate for the same stimulus condition (dark or ambient) is flagged. Manipulated arms are compared only on groups their manipulation does not target. The flag is reported and does not fail a run.
- DA steady state. A probe whose recorded fixed-point gap (section 2.4) exceeds `detector.da_gap_fraction` of the fixed point in an innervated compartment is flagged for that compartment. Reported, not failing.
- Bias-dominated steering. `|bias_hz|` above `bias.max_fraction` × (maximum − minimum) of the ten-seed 4.1r tuning curve is flagged, and 4.2r reports it.
- Photoreceptor-sign dependence. In 4.8r, if the 4.2r conclusion disappears or reverses with histamine off, the result is reported "depends on photoreceptor sign". This is expected and recorded, not a failure.
- Platform agreement. For the configured candidate's R-screen metrics and for every K3r finalist, Camber and Mac values are compared. A central-rate difference above 25 percent, or a criterion that passes on one platform and fails on the other, is flagged "platform-sensitive" in `docs/resting-candidates.md` or `docs/behaviour-p2.md`.

## 10. Open questions

These are every "For Rolf" item from reviews 1 to 4, each with my reading. Sign-off does not answer them. Questions 1 to 5, 11, 12 and 13 change work and are needed by day 0 (section 8.5); the rest can wait for the step that raises them. The one editorial "For Rolf" item, the clause 7 interaction status, is already fixed in section 1.5. Items 26 to 43 come from the WP24 spec round. Items 27 to 33, 38 and 42 fix what WP24 builds and are needed before it starts; the rest can wait for the step that raises them. Coordinator, 2026-09-16 18:12: items 27 to 33, 38 and 42 were adopted at the readings written here as WP24's working defaults so the implementation lane could start (brief `tasks/WP24.md`). Rolf answered all of them, and item 41, on 2026-09-16 at 18:18: every reading accepted as written. Item 41 is still reported at the end of each T0 as the `t2-b-unreachable` count. Item 73 is the WP26 3d pre-stage.

1. Phase 3 deferrals. My reading: section 1.2's list is right for speed. Forward-speed coupling (hyperactivity as a readout) and learning are the two that bear on the ADHD goal; both stay out unless Rolf wants them in the Phase 2 headline. ANSWERED by Rolf 2026-09-14 ~19:55: accept the reading.
2. The acceptance sentence. In the model, methylphenidate has no transporter to block in fumin, so the drug contrast in fumin is expected to be small. My reading: keep fumin for the machinery and the coupling clause, and let the P-screen's most impaired genotype lead `docs/phase2-results.md` without changing the predicate. ANSWERED by Rolf 2026-09-14 ~19:55: accept the reading.
3. Random initial heading as the 1.3 default. It removes the item 42 artefact, but Phase 2 fixation indices are not directly comparable with Phase 1 bare runs. My reading: accept. ANSWERED by Rolf 2026-09-14 ~19:55: accept the reading.
4. Scope of the curated sign correction: whole brain (`brain`) or optic and sensory only (`optic_sensory`). My reading: whole brain, since about 1,900 neurons are affected and curated labels are the better evidence. Switch to `optic_sensory` if the census shows central corrections concentrated in a few types with doubtful labels. ANSWERED by Rolf 2026-09-14 ~19:55: accept the reading.
5. The Camber envelope. The caps total 26 credits under closed loop and 30 under open loop (11 more with tier 2) beyond the running map, at `q_plan` and ρ = 1. The proof lane's speed measurement rescales them, and WP11's final scaling measurements set the Mac worker counts that decide how much work Camber must take. Is that inside the free trial? My reading: plan on it, and have the coordinator re-check the envelope once ρ and WP11 scaling are measured, before WP17 launches R1. ANSWERED by Rolf 2026-09-14 ~19:55: accept the reading.
6. Authorising tier 3 (engine equation changes) if tiers 1 and 2 fail. My reading: decide only when section 2.6 step 5 is reached. ANSWERED by Rolf 2026-09-16 15:10 ("tier 3"), at section 2.6 step 5 with tier 2 ending empty (every measured candidate at extended-mode retention 0.000–0.002): tier 3 is authorised. WP24 is written as a spec revision on `spec/wp24` (brief `tasks/WP24-spec.md`, turns under `tasks/wp24/turns/`), starting with spike-frequency adaptation; the bare substrate stays canonical and every mechanism is a switch that is off by default and bitwise-neutral when off.
7. K1r bounded group tuning. My reading: keep it; it costs about 2 hours and falls back to the common weight with its own qualification.
8. The holdout policy of section 3.8. The holdout runs once after integration and review, and a later configuration change leaves P2 unreachable. My reading: accept; a new holdout split is not something Phase 2 can create.
9. Narrowing entry binding to declared and logged data inputs (section 5.1), at the cost of WP16's read-call conversion. My reading: accept; otherwise every configuration commit stales every entry, and each regeneration costs about 6,150 s of serial validation.
10. R7 and R8 get no drive in v0.2. My reading: fine for an achromatic arena; revisit only if V1 fails at the lamina.
11. The allowed feed-forward loss: extended-mode retention of at least 0.5 of the matched bare response, with upstream retention only recorded. My reading: accept, since background drive supplies part of the reflex's depolarisation at rest. Rolf can instead ask for a higher floor or an upstream requirement before WP17 launches R-reflex. ANSWERED by Rolf 2026-09-14 ~19:55: accept the reading.
12. A TuBu closed loop is "P2-delivered", not P2, because P2 promises a photoreceptor-driven brain. My reading: keep that. Rolf can instead accept TuBu closed loop as P2. ANSWERED by Rolf 2026-09-14 ~19:55: accept the reading.
13. The meaning of "settled" for schema 1.3 (section 2.4). It covers the resolved population set only. Small populations such as DAN and the steering neurons are shown as unresolved, and dopamine fixed-point gaps are reported without failing a probe. My reading: accept, because 10 s of settle cannot resolve those populations and an unconditional gate would fail every probe. If Rolf wants a stricter gate, the cheapest one fails a probe whose wild-type vehicle dopamine gap exceeds `detector.da_gap_fraction` in a compartment that a clause 5 contrast averages. ANSWERED by Rolf 2026-09-14 ~19:55: accept the reading.
14. Census central count (WP14 report). Curated-inhibitory corrections in the central class measure 11, not 8 (total 1,353, not 1,350): two PPL203 (`dopamine, gaba`) and one DN1a (`CCHa1, Dh44, glutamate`) are classified by their first classical transmitter token. Coordinator reading 2026-09-14: keep the first-classical-token rule; the section 2.2.1 table takes the measured 11 and 1,353 at review r13. Every other cell matched.
15. V0(b) against L2 geometry (WP14 report). Propagated L2 azimuth has Spearman ρ 0.673 (left) and 0.676 (right) against the rank rule on L2's own z, below the 0.9 floor, while the median L2 column spread is 3.0° and every stage type is under 20°. Coordinator reading 2026-09-14: the failure is L2's z as a proxy for the retinal axis, not propagation. WP18 records ρ under the z rank and under the rank along each eye's first principal axis of L2 positions (signed to agree with R1-6's z order). If the principal-axis ρ is at least 0.9, V0(b) uses that axis; otherwise V0(b) is recorded, not gating, and review r15 decides with WP18's measurements. The Phase 1 rule stays: nothing is claimed as passed that was not run.
16. Test 0.10 has two legs in two owned files (`validation/level0_substrate.py`, WP14; `validation/level0_rest.py`, WP15). Coordinator reading 2026-09-14: WP14's entry keeps id `0.10` (pure leg); WP15 registers the engine leg as `0.10-engine`; every place this document requires 0.10 requires both ids passed.
17. LC10 propagated coverage (WP14 report). 397 of 816 in-engine LC10 neurons receive an azimuth; the covered subset passes the 20° spread test. Coordinator reading 2026-09-14: accept; LC10 column subsets use the covered neurons and every table that uses them states the coverage.
18. R1-6 rank ties (review r13, decision 18). `pos_z` has ties within each eye. Coordinator reading 2026-09-15: tied neurons share the mean rank; azimuths are rounded to 6 decimals; the committed SHA-256 covers that rounded table (as committed on `review/r13`).
19. Within-stage type order in propagation (review r13, decision 19). Coordinator reading 2026-09-15: types within one section 3.3 stage are assigned in the listed type order, each seeing the types before it (as built); whole-stage assignment would leave L5 at 37 of 1,258 neurons covered.
20. drive-v0.2 key names (review r13, decision 20). Coordinator reading 2026-09-15: the loader's names are the file format WP19 writes — `transmitter_rule.{blob_id, scope}`, `scales.{g_gaba, g_glu, g_his, unk, sha256}`, `background.{n_bg, r_bg, groups.<name>.{size, w_bg}}`, `threshold.{sigma_th, seed, z_sha256}` or null, `optic_exemption`, `provenance`; a tier 2 `n_bg` of 25 or 400 also sets the matching params override, since the engine reads `bg.n_bg` from params and the loader refuses a mismatch. WP24 adds the optional top-level section `mechanisms.{adaptation.{b_mv, tau_ms, scope, mask_sha256}, depression.{U, tau_ms, scope, mask_sha256}, conductance_inhibition.{E_inh_mv, scope}}`, each block or null (section 2.2.4). The drive file stays `drive-v0.2.yaml`, with no successor version: every schema 1.3 pin, the section 8.1 fixture rule and the WP19 loaders already key on v0.2, and a file's identity is its bytes. The top-level keys become a closed list.
21. Scales-only fixture substrate id (review r13, decision 21). Coordinator reading 2026-09-15: `ff-candidate.json` carries `rest:<16 hex>` (as built), because its weights are the candidate's and a bare entry must not bind to it. WP24: when the committed drive file has a mechanism, the fixture's `substrate_id` is `rest-<tag>:<16 hex>` from `substrate_id_for`, and its `engine_model` agrees (section 5.1).
22. Schema 1.2 files with v0.2 pins (review r13, decision 22). Coordinator reading 2026-09-15: reject `params_version` or `drive_version` v0.2 pins in schema 1.2, so the rest substrate is reachable only through 1.3; test 0.14 asserts the rejection. The change lands in the next review round (r14), whose reviewer owns it.
23. `drive_version` null (review r13, decision 23; SPEC item 84). Coordinator reading 2026-09-15: section 5.1's null and item 84's omission are schema 1.3 rules; schema 1.2 manifests keep writing v0.1 so Phase 1 manifests and protocol hashes stay as recorded.
24. P2 data dependencies must be declared inputs (review r14a, decision 24). Coordinator reading 2026-09-16: accepted as built in `12adab6`. For an entry with `declared_inputs`, every `data_dependencies` name must appear as `data/<name>` in `declared_inputs`, else the entry is stale with `data dependency not declared: <name>`; a declared file without `-vX.Y` is bound by its blob alone. WP19's rest entries declare no `data_dependencies` and are unaffected; any later P2 entry that names a data dependency declares it.
25. Status evidence regenerated after the move (review r14a, decision 25; SPEC item 83). Coordinator reading 2026-09-16: accepted. Lane ev2 (brief `tasks/evidence-p1b.md`) moves `.worktrees/rg/runs/validation-0.6-lite` and `validation-0.8` into `evidence/phase1/runs/` by run-id subdirectory, keeps rg's derived `index.sqlite` beside the others as `index.sqlite.from-rg`, and also moves the `wp9-*` files under `.worktrees/w9/.cache` and the `closure-p1-*` files under `.worktrees/cl/.cache` that `tasks/reviews/code-p1c.md` cites into `evidence/phase1/cache/`; it extends `docs/phase1-evidence.sha256`, re-runs the check and restores read-only. `.worktrees/rg`, `w9` and `cl` stay until that lane merges. Standing rule: every later status regeneration moves its run trees the same way in the same round, or its report states that they are lane-local.
26. The sustained reflex window. R-reflex scores the last second of a 3 s probe with the stimulus on throughout, so adaptation and depression pay their steady-state cost; the usual argument that a transient feed-forward volley passes adaptation does not apply to the criterion as written. My reading: keep the criterion, which this round is not authorised to change. If tier 3 fails at T0 with retention clustered just under 0.5 at the weakest settings, Rolf may want an onset-window variant of R-reflex, which would be a criterion change.
27. Mechanisms in the feed-forward measurement. R-reflex (c) and `ff-candidate.json` apply the candidate's mechanism, and the bare reference stays `lif`. My reading: accept. Leaving the mechanism out of (c) would hide exactly the feed-forward cost the floor exists to bound. ANSWERED by Rolf, 2026-09-16 18:18: accepted at the reading above.
28. T0 before R-screen, extended mode only. Tier 3 runs R-reflex (c)'s extended arm first and its upstream arm only for T2 candidates. Every candidate must pass (c) anyway, (c) does not depend on the weight, and upstream retention is recorded, not required. Without caps the ranked list is therefore the same as section 2.6's order would give. My reading: accept. ANSWERED by Rolf, 2026-09-16 18:18: accepted at the reading above.
29. Sensory exemption. Sensory neurons neither adapt nor depress, so the sugar GRNs and photoreceptors keep their calibrated encoders. My reading: accept. The alternative, scope `all`, would also change the V-cal and R3 input gains, and it can be a later grid dimension if a sub-tier fails on a margin. The scored neuron is the opposite question: item 42. ANSWERED by Rolf, 2026-09-16 18:18: accepted at the reading above.
30. Refractory semantics. a_sfa and h_inh are frozen during refractory like g, and x_std recovers during it. a_sfa is not cleared at a spike, and h_inh is. My reading: accept. The freeze stretches adaptation's effective time constant by the refractory fraction, about 12 percent at 56 Hz, well inside the grid's factor of 10 in tau. ANSWERED by Rolf, 2026-09-16 18:18: accepted at the reading above.
31. Conductance-based inhibition's normalisation and reversal. Events match today's current at v = v_0, and E_inh takes the placeholders −72, −62 and −57 mV. This model has no measured reversal on its volt scale. My reading: accept. Normalising at v_0 keeps every calibrated resting PSP; normalising at threshold would weaken resting inhibition everywhere. ANSWERED by Rolf, 2026-09-16 18:18: accepted at the reading above.
32. Global mechanism constants. One value per parameter applies within a scope, with no per-population constants. My reading: accept for tier 3. Per-population constants multiply the grid by the population count and would need a new authorisation. ANSWERED by Rolf, 2026-09-16 18:18: accepted at the reading above.
33. One mechanism at a time. No sub-tier combines mechanisms, so 3b does not carry 3a's closest miss. My reading: accept. Rerunning 3b's 12 settings with 3a's closest-miss adaptation on costs about 11,000 brain s at T0, and about 360 engine-hours with T1 and T2. Rolf can add it after 3c. ANSWERED by Rolf, 2026-09-16 18:18: accepted at the reading above.
34. Search before review. Each sub-tier's development search starts at its gate, beside r18a, r18b or r18c. A review change to that variant's model strings, method or `on_pre` reruns the sub-tier. Other code changes leave its records standing as development evidence, as tier 1's did across r14. My reading: accept for speed. Nothing development qualifies anything, and K1r and Q-rest re-execute on the Mac after the review.
35. P2-partial-B during tier 3. It does not hold while tier 3 runs, and `data/drive-dev-p2.yaml` stays the development substrate for lanes. A sub-tier's closest miss becomes `data/drive-dev-t3.yaml` only when the coordinator asks. My reading: accept. Switching lanes to a tier-3 development file mid-search would restart their development runs for a substrate that also failed.
36. The weight grid edge. Mechanisms lower rates, so the resting weight may sit above 1.60 mV. Tier 3 flags `grid edge` and does not extend the grid. My reading: accept for the first pass. If most R-screen failures of a sub-tier carry the flag, extending the weights to 2.00 mV costs 8 × 3 × 12 = 288 brain s per unit, and Rolf decides.
37. DONE in review r18a (`20eb8de`, item 60). Lane w19's own substrate id. `drive/rest_calibration.py` on `lane/w19` (line 793 at 758f145) builds `"rest:"+_sha(_drive())[:16]` itself, which would label a mechanism file `rest:`. WP24 replaces that literal with `substrate_id_for` after r14b. My reading: accept, and r14b checks every other writer of `substrate_id` for the same pattern.
38. The `cbi-stiff` rule. An evaluation whose h_max gives `lif.dt` × (1 + h_max) / `lif.t_mbr` above 0.1, which is h_max above 19, counts as not computable. This adds a validity condition for a numerical method, not a relaxation. My reading: accept the cut at 0.1, about ten `rk4` steps per effective membrane time constant. Round 1 proposed 0.5 (h_max above 99), which lets `rk4` run where it is no longer accurate; Rolf can ask for the looser cut, since it is a validity rule and not a rest criterion. h_max is sampled at chunk ends and can miss a peak. If a 3c candidate ranks, a dt 0.05 ms rerun of its R-screen seed 1 on the Mac is the direct check. ANSWERED by Rolf, 2026-09-16 18:18: accepted at the reading above.
39. Sequential sub-tiers. 3b starts only when 3a ends empty, including after a Q-rest fall-through that can take a day. My reading: accept. Starting 3b's T0 as soon as slots free up during 3a would save about 1.4 hours of wall, cost 5.3 node-hours whenever 3a succeeds, and needs both variants' gates at once. Rolf can ask for it. ADDENDUM, coordinator 2026-09-17 02:05 under Rolf's autonomy grant ("i sleep autonomous. i trust your decisions and agency don't wait for my input"): 3b's T0 was submitted during 3a's T1 because 3a's T0 (`rest-T3a-T0.json`, lane commit `ce1e102`) admitted 17 of 180 units, all at g_gaba 1.0 and g_glu 1.0, with `t2-b-unreachable` on 189 of 192 rows and 15 of the 17 passers, so 3a is likely to end empty at T2 (b); both gates were reviewed and merged (r18a `5d6be00`, r18b `09bc4d6`); the 5.3 node-hours are moot if 3a succeeds. 3b's T1 still waits for 3a's decision.
40. Checkouts before WP24 and the `mechanisms` section. Their loader ignores unknown keys, so they would run a mechanism file as `lif` under a `rest:` id. My reading: accept the identity separation of section 5.1 as the guard. Tier-3 files are read only by WP24's loader, and every lane merges main after WP24 lands before it reads a tier-3 file.
41. T0 passers that cannot pass T2. T0 is a retention ratio with background off, while R-reflex (a) and (b) in T2, and 1.4r after K1r, require absolute MN9 differences of 40 and 50 Hz with background on. A unit can pass T0 at 0.5 of the bare 56.0 Hz, a 28 Hz difference, and still have no route to 50 Hz. T0 records the background-off difference and flags a unit below 50 Hz `t2-b-unreachable`, without changing admission. My reading: run T1 and T2 as written, since the flag is a heuristic (background drive adds depolarisation) and changing admission would be a criterion change. The coordinator reports the flag count when T0 ends. If every T0 passer of a sub-tier carries the flag, Rolf can stop the sub-tier there for a criterion change instead of spending T1's roughly 3 hours. ANSWERED by Rolf, 2026-09-16 18:18: accepted at the reading above. REPORTED, 3a T0 (2026-09-17 02:00): 189 of 192 rows and 15 of 17 passers carry `t2-b-unreachable`; every passer sits at g_gaba 1.0 and g_glu 1.0 (retention median over all units 0.043, maximum 0.979); the two unflagged passers are the weakest adaptation settings (b 0.1 mV, tau 50 and 150 ms). T1 and T2 run as written; T2 (b) measures the flag directly.
42. The scored neuron inside the scope. MN9 is motor, not sensory, so 3a adapts it and 3b depresses its non-sensory inputs; T0 therefore mixes readout cost with path cost. By the first-order estimate of section 2.2.4, a neuron at 56 Hz keeps 97 percent of its rate at b × tau 0.005 mV·s and 26 percent at 0.5. T0 records MN9's a_sfa under 3a so the two can be told apart. My reading: keep MN9 in scope. Exempting the readout, or all motor neurons, would give the scored cell a model no other neuron has and bias the criterion towards passing. Rolf can ask for the exemption before WP24 starts; it changes the masks and so the substrate. ANSWERED by Rolf, 2026-09-16 18:18: accepted at the reading above.
43. Camber rate of the mechanism variants. B-mech measures ρ_mech on the Mac, and every Camber figure of section 6.5 scales the ledger's 50 worker-s per brain s by it. `lif+cbi`'s `rk4` update may scale differently on Camber's x86 Cython build. My reading: accept the Mac ratio as a stated bias for planning, and let each sub-tier's T0 tasks measure the Camber rate; T1 and T2 are shaped from the measurement when it exceeds the plan by more than `camber.margin` (section 6.5). This is a measurement, not a decision for Rolf.
44. Camber receipts reachable from main (review r14b, decision 26). Coordinator reading 2026-09-16: accepted as implemented in `b870b2c`. A citation of Camber receipts must resolve from main: a tracked path, the default for small text and JSON (WP17's 251 receipts live under `validation/records/p2/camber-receipts/wp17/`), or an explicit lane-local mark in the citing document; evaluation trees (parquet, `tasks.json`) may stay lane-local when a committed record binds them by SHA-256. WP24's ledger section follows the same rule.
45. Drive threshold seed (review r14c, decision 45; lane w19 finding F1). Coordinator reading 2026-09-16: accepted as built in `fbf840b`. The committed drive file, or the ranked candidate row it came from, is the source of truth for the threshold seed; `make_drive` and `_candidate_drive` re-materialise z from that recorded seed and never from a constant, and a candidate with `sigma_th > 0` and no seed raises. Section 8.2's `drive.seed` row now says so; WP17's tier-2 evaluations and `data/drive-dev-p2.yaml` used 20260912.
46. R1/R2 stage-record binding (review r14c, decision 46; finding F3). Coordinator reading 2026-09-16: accepted as built in `bf83dcd`. R1 and R2 resume against the producer summary's declared inputs and artifact SHA-256s (decision 24), not the whole-repo `code_scope`, so a later `src/` change no longer blocks the dispatcher with "rest evidence code scope is stale"; `code_scope` stays recorded as evidence.
47. `bg.n_bg` binding (review r14c, decision 47; finding F5). Coordinator reading 2026-09-16: accepted. `n_bg` is a drive-file field bound through the drive blob; rest Q-rest entries keep `overrides_hash` empty, the process-local overlay that satisfies the loader's `drive.background.n_bg == params bg.n_bg` equality is not an identity override, and rest ids are not added to `GRID_ENTRY_IDS`.
48. K1r method (review r14c, decision 48; finding F7, deviation `DEV-W19-K1R-PAR`). Coordinator reading 2026-09-16: accepted. Speculative parallel coordinate descent is the K1r method on the condition, locked by `tests/test_wp19_stages.py::test_k1r_speculative_replay_equals_serial_descent`, that its rounds reproduce the serial descent's full evaluation dicts bitwise for batch sizes 1, 3, 8 and 40. Section 2.5 step 6 now says so. The development run took 1,750 s against 5,580 s serial.
49. 3.1br per-seed dopamine bound on sparse compartments (review r14c, finding F10; for Rolf). On the development substrate, with DAN rates near 0.8 Hz, seed 1 passes 3.1br(ii) each time (0.0033 to 0.0037 µM against 0.004) while seeds 2 and 3 fail from sparse-compartment spike noise, which re-estimating R_c from the seed mean cannot remove. Options: a seed-mean criterion, a sparse-compartment bound, or a longer window. Coordinator reading: change nothing until a tier-3 candidate reaches K2r; if it fails 3.1br the same way, Rolf picks one of the three.
50. 2.2r all-neuron median against a group-mean screen (review r14c, finding F11; for Rolf). WP17's R-screen checks group means; 2.2r then requires an all-neuron median of 0.2 Hz or more over 10 s. The development substrate has median 0.0 Hz with more than half the neurons silent while the group means sit on target, so a ranked candidate can pass R1 to K2r and still fail 2.2r at the end of Q-rest. Options: add the 2.2r median to the screen, or revisit the criterion. Coordinator reading: tier 3's T1 R-screen records the all-neuron median as a flag so the coordinator can report it before T2; no criterion changes now.
51. B2-rest q2 by batch kind (review r14c, finding F16). Coordinator reading 2026-09-16: accepted; on the canonical run `q2_by_workers` is keyed by batch kind (rest against bare feed-forward, which loads params v0.1 with no background) before later stages consume it. WP19 owns the change.
52. 2.4r jitter band inside window noise (review r14c, finding F17; for Rolf). 2.4r's 25 percent band around one 1 s MN9 difference sits inside window noise when MN9 already fires 20 to 36 Hz at rest (the ten 1.4r per-seed differences have SD about 22 Hz). Options: compare against the ten-seed 1.4r mean, or rerun several seeds per stream. Coordinator reading: wait for a tier-3 candidate's 1.4r numbers; a resting MN9 near 0 Hz, which every rest criterion wants, makes the band usable as written.
53. WP19-dev records measure the interim development candidate (review r14c). The chain's R4, K1r and Q-rest bytes are the interim candidate `3.0-6.0-2.0-False-25-3.0`; main's `data/drive-dev-p2.yaml` is the final closest miss `3.0-6.0-1.0-False-25-3.4` (`3aac713`). Those records are not a measurement of the closest miss, and `validation/records/p2/dev/B2-rest.json` stays frozen without class fields; the canonical run writes them.
54. IdentityBlock key-set test carries WP24's two fields (review r18a, decision 54; WP24 deviation 1). Coordinator reading 2026-09-16: accepted. `tests/test_binding.py` (WP16) names `engine_model` and `mechanisms` as companions to the WP24-owned fields on the same class; not a WP16 behaviour change.
55. `ChunkResult.h_max` lives on `types.ChunkResult` (review r18a, decision 55; deviation 2). Coordinator reading: accepted; the field stays where `brian_engine.run_chunk` returns it, and `types.py` counts as allowed for that field although 8.4 names `engine/base.py`.
56. `engine/__init__.py` re-exports `Mechanisms`, `Adaptation` and `MechanismTraceTable` (review r18a, decision 56). Coordinator reading: accepted; public names of WP24-owned types, no Brian2 load at collection.
57. Worker `engine.build` keeps `inspect.signature` so a `*args` stub still builds (review r18a, decision 57; deviation 4). Coordinator reading: accepted as built in `6ff84d4`; the rest-path test stub takes `*args, mechanisms=None`, a rest drive passes `mechanisms_from_drive`, a non-rest stub omits the keyword.
58. Renamed WP24 tests (review r18a, decision 58; deviation 5). Coordinator reading: accepted; `tests/test_wp24_loader.py` and `tests/test_wp24_rest_tier3_decision.py` must not import `flyonenomics.engine` at collection, and `test_registry.py::test_root_ids_follow_completeness_order` asserts what it did before.
59. Schema mechanism-pin checks read the drive YAML under `io.unlogged()` (review r18a, decision 59; deviation 6). Coordinator reading: accepted; schema validation is not an entry's declared read, `unlogged` is thread-local since r14a, same pattern as `build_identity`'s version reads.
60. Every writer of `substrate_id` for a rest drive goes through `substrate_id_for` (review r18a, decision 60; item 37 done). Coordinator reading: accepted as built in `20eb8de`: WP19's literal is gone, ranked rows and documents keep `engine_model` and `mechanisms`, later stages pass `mechanisms_from_drive` to `engine.build`, and R4 and the drive commit refuse when the named and observed models disagree.
61. 3b unit count (review r18b, decision 61). Coordinator reading 2026-09-17: accepted. Only 3a runs the 12 baseline pairs (P3 with g_gaba at most 2, no mechanism); they are recorded and never units or candidates, so 3b and 3c have 15 P3 pairs × 12 settings = 180 units where 3a had 192.
62. `engine/__init__.py` re-exports `Depression` (review r18b, decision 62). Coordinator reading: accepted, companion to item 56.
63. 0.17 codegen targets (review r18b, decision 63). Coordinator reading: accepted. Production runs Brian2 on Cython; the listed alias-free reset passes on both Cython and a scratch numpy target (err_v at most 9.4e-15, err_x at most 4.6e-14), while the naive reset passes on Cython and fails on numpy. Production codegen and the listed reset do not change.
64. Packed T0 `bare-mismatch` (review r18b, decision 64). Coordinator reading: accepted as built in `6dcb2fd`. Each T0 line stores the same-job bare mean and the global bare mean from the first T0 job in launch order; a job whose per-seed bare differences differ from the first job's flags every unit `bare-mismatch`. `collect_t0` is the per-job pass, `collect_packed_t0` (CLI `collect-t0-packed`) the launch-order collect that sets the flag. Every tier-3 T0 collection uses the packed collect.
65. `rest_map` probe carries `h_max` (review r18c, decision 65). Coordinator reading 2026-09-17: accepted as built in `9ec62b1`. `_probe`, `screen_candidate` and `long_decision` carry `ChunkResult.h_max` (max across chunks) and score stiff metrics as CAP / not computable, so T0, T1 and R-long flag `cbi-stiff`; companion to item 55; no wider edit of `rest_map.py`.
66. 0.18 (d) sign-flip drives both rows (review r18c, decision 66). Coordinator reading: accepted as built in `6a8c379`. After `set_weight_scale` −1 on both rows the flip clause drives one event from neuron 0 and one from neuron 1, requires a non-zero reference `h_inh` and matching driver spikes (N197).
67. `engine/__init__.py` re-exports `ConductanceInhibition` (review r18c, decision 67). Coordinator reading: accepted, companion to items 56 and 62.
68. 3c unit count (review r18c, decision 68). Coordinator reading: accepted, companion to item 61: 15 P3 pairs × 3 E_inh values = 45 units, one job.
69. T2 R-reflex stiffness (review r18c, decision 69). Coordinator reading: accepted. `reflex_decision` scores raw Hz lists without `h_max`; T0, T1 and R-long already block a stiff pass, but a unit not stiff at T0 (background off, 1 s) can become stiff under background-on R-reflex. Before the first 3c T2, WP24 makes a T2 probe with `h_max` above 19 not computable (flag `cbi-stiff`, no pass); 3a and 3b have no `h_inh`, so their T2 is unaffected.
70. 3b T1 does not wait for 3a's T2 decision (coordinator, 2026-09-17 10:50, under the autonomy grant of 2026-09-17 00:05: "i sleep autonomous. i trust your decisions and agency don't wait for my input"). Rolf's item 41 answer (run T1 and T2 as written whatever the T0 flags say) applies to every sub-tier, credits are not a gate, and the 3b T1 measurement of criterion (b) is independent of 3a's. So when 3b T0 has any passer, WP24 submits 3b T1 at once; an empty 3b T0 is pushed as `RANKED WP24-3b` empty at T0. The Camber recovery of the night (two silent cancellation waves, large probe, staged resubmits 27566 and 27569 to 27572, all COMPLETED by 10:47) is recorded in HANDOFF.md.


71. (Coordinator decision under the 2026-09-17 00:05 autonomy grant, 18:30.) Camber is closed for this project (usage quota, three cancellation waves), Vultr is blocked and Kamatera capped; the remaining tier-3 jobs (3b T1, 3c T0, and whatever follows) run on IBM Cloud VPC in us-east under WP25 (`tasks/WP25.md`): the Camber lifecycle is ported to `scripts/ibm/`, plans, commits and commands are replayed unchanged, results are pulled into the same `camber-runs/wp24/` layout, and the science collectors and decisions stay with WP24. Provider rule: one instance at a time until the first job completes end to end; every instance is torn down by the lane that created it, floating IP included. Section 6.5's Camber constants (36 workers, 2 h jobs) carry over to the `cx2-64x128` profile, which is the Camber large equal.

72. (Coordinator decision under the autonomy grant, 2026-09-17 20:05, on Rolf's "this has been going on for more than a week i really need us to accelerate".) The one-instance rule of item 71 ends: the port proved up, run, pull and teardown end to end on the smoke instance and job 0 ran cleanly for 50 minutes, so up to three cx2-64x128 run at once across all lanes (the account quota is 200 vCPU). Camber's standing order carries over to IBM: no submission waits for the coordinator or Rolf; wp24 collects each batch as soon as it is complete, decides admission, and submits every later tier-3 stage itself; every instance is torn down by the lane that created it. A second runner lane (wp25b) replays 3b T1 job 1 and 3c T0 beside wp25's job 0, and an Opus lane drafts `tasks/WP26-options.md`, three costed options for the case where tier 3 ends empty, so the next decision waits on nothing.

73. (Coordinator decision under Rolf's 2026-09-17 21:50 grant "autonomous i sleep take this until the end".) Sub-tier 3d, KC-targeted APL inhibition on `lif` as `tasks/WP26-options.md` option C and `tasks/WP26.md`, is authorised and starts now rather than after 3b and 3c: every tier so far ended at the R-screen on KC rate and F, the credit has room (about 185 dollars of 200), and running the 3d wave beside the last 3b and 3c stages saves about four hours if they end empty; if they do not, the wave costs about 25 dollars and yields a second candidate class. Box rule: the cap stays three cx2-64x128 across all lanes; wp24's stages have priority, so wp26 holds at most two boxes at any time and checks `ibmcloud is instances` before every create.

74. (Coordinator ruling under the same grant, provisional until Rolf confirms.) The R-reflex (a)/(b) harmonisation of option A applies to every tier-3 candidate that fails only R-reflex (a) or (b): `rest.reflex_mean_hz` 28 Hz and `seed_min_hz` 22 Hz, 0.5 and 0.4 of the same-job bare difference, matching the (c) floor of item 11; 1.4r takes the same reading. Both verdicts are recorded for such a candidate, the original thresholds' and the harmonised, and the candidate is flagged `reflex-harmonised` in its record, in `docs/resting-candidates.md` and in the RANKED line, so Rolf can strike it on waking. A candidate that fails anything else is not rescued by this ruling.

76. (Reviewer r18d, leftover verify; 2026-09-18 00:18, `tasks/reviews/code-r18d.md`, merged into main at `07c7c0d`.) Rule: `down.sh` leftover verify is per named instance when `IBM_LEFTOVER_NAME` is set. It fails only if that instance, its floating IP, or its live boot volume remains. Own boot `pending_deletion` / `deleting` is allowed. Other `flyo-*` boxes print as `other` and do not fail. Default `IBM_MAX_INSTANCES` is 1; the coordinator may raise it to 3. The empty-set check from the one-instance port made every concurrent teardown fail after a good delete (flyo-02 and flyo-03 down receipts).

77. (Reviewer r18d, `IBM_MAX_INSTANCES` before SSH; 2026-09-18 00:18, `tasks/reviews/code-r18d.md`, merged into main at `07c7c0d`.) Rule: `up.sh` counts `flyo-*` instances after the budget read and before `ibm_ensure_ssh_rule`. A cap of 0 must refuse without adding an SSH rule.

78. (Reviewer r18d, item 74 named floors; 2026-09-18 00:18, `tasks/reviews/code-r18d.md`, merged into main at `07c7c0d`.) Rule: 0.5 and 0.4 of the same-job bare difference are the live floors (28.0 and 22.4 Hz at 56 Hz). Named 28 Hz and 22 Hz apply only when the bare mean is missing. `docs/resting-candidates.md` now says that. SPEC-P2 item 74 still says "22 Hz … against a 56 Hz bare"; that is the named-floor wording, not a code defect.

79. (Reviewer r18d, `collect_t2`; 2026-09-18 00:18, `tasks/reviews/code-r18d.md`, merged into main at `07c7c0d`.) Rule: item 74 lives on `t2_reflex_probe`. No `collect_t2` exists. No T2 job ran on 3a, 3b or 3c. A later T2 collector must call `t2_reflex_probe` with `sub_tier` and `job_bare_mean`. This is not a close blocker.

80. (Reviewer r18d, flyo-04 receipts; 2026-09-18 00:18, `tasks/reviews/code-r18d.md`, merged into main at `07c7c0d`.) Rule: create, run and down for flyo-04 live under `validation/records/p2/ibm-receipts/wp26/` on `lane/wp26`. This review does not merge wp26. Sub-tier 3d is out of scope.

81. (Coordinator ruling under Rolf's 2026-09-17 21:50 grant, 2026-09-18 07:50.) Tier 3 ends empty: 3a and 3b at the T1 R-screen on KC rate and F, 3c at T0 with the reflex lost, and 3d (item 73) at the T1 R-screen on F alone; 3d's closest miss `1.0-4.0-0.0-False-100-0.85-kc-6.0` (pair (1, 4), no adaptation, `g_gaba_kc` 6, w_bg 0.85) passes central (5.74 Hz), KC (0.25 Hz), b, stability, DAN and gradedness and fails F at 3.02 (mean at w_bg 0.85) and 3.22 (worst pair) against the cap of 3; T2 did not run and item 74 rescued nothing. No further mechanism is added and no further box is created under the grant. P2-partial-B, recorded at the tier-2 close, stands as Phase 2's resting-state outcome and `data/drive-dev-p2.yaml` stays the development substrate for WP18 to WP22. What remains is Rolf's: the criterion question of items 41, 49, 50 and 52 now has a unit that fails F alone by 0.02 at the mean, so relaxing the F cap (or scoring F at the mean rather than the worst pair) would admit it to T2; that is a criterion change after the data and is recorded only if Rolf rules it. Items 73 and 74 stand as records of the grant.

82. (Reviewer r18e, leftover verify; 2026-09-18 08:47, `tasks/reviews/code-r18e.md`, merged into main.) Rule: keep main's `IBM_LEFTOVER_NAME` per-name leftover check (decision 76). The lane's `IBM_DOWN_ALLOW_SIBLINGS=1` is not in the merged scripts. flyo-05 and flyo-06 down receipts needed a sibling to remain; main's rule prints other `flyo-*` as `other` and does not fail. Three boxes work.

83. (Reviewer r18e, wave packing; 2026-09-18 08:47, `tasks/reviews/code-r18e.md`, merged into main.) Rule: the 3d wave packer fills three boxes by cost. Every T0 unit sat on job 0; most units' T1 sat on job 1 or 2. That is a one-wave launch, not per-unit co-location of T0 and T1. Evaluation `src/` is identical across the three job commits. Collectors remain fail-closed on launch-order and `plan_sha256`. Not a record rewrite.

84. (Reviewer r18e, `collect_t2` and item 74; 2026-09-18 08:47, `tasks/reviews/code-r18e.md`, merged into main.) Rule: item 74 lives on `t2_reflex_probe`. `collect_t2` calls it with `sub_tier` and `job_bare_mean`. Decision 79's missing production caller is closed on this branch. No T2 job ran.

85. Free (reserved for r18e, unused).

86. (Rolf, 2026-09-18 08:40, after the GPT Pro consultation `tasks/gpt-pro/rest-consult-1.md` on the whole rest record.) Items 73, 74 and 81 are confirmed as written. The consultation's diagnosis is adopted as the working reading: tier 3 shows that no searched setting passes the combined contract, not that the connectome cannot rest; the 3d closest miss's F failure (five of six rows over 3, worst 3.22) is shared network-wide fluctuation, whose location the records do not resolve. Its ranked plan runs on IBM (Rolf: "on ibm"), not on the Mac first: experiment 1 (instrumented replay of `1.0-4.0-0.0-False-100-0.85-kc-6.0` with a background-on reflex probe and the free-pool median-rate check) and experiment 2 (threshold spread `sigma_th` {0, 0.5, 1, 2} mV on that substrate over w_bg 0.75 to 0.95) as one wave under lane WP27 (`tasks/WP27.md`), cap 15 dollars list; experiments 3 (input variance, `n_bg`) and 4 (freeze and falsify) follow only on the conditions the consultation states, each under its own cap, the sequence capped at 22 dollars of engine time plus box overhead. No criterion changes: `rest.fano_max` 3, the KC cap and the two-weight worst-seed scoring stand; the diagnostic runs are not T1 or T2 admissions.

87. (Rolf, same ruling; detector change, recorded with the old verdicts kept.) The ignition detector of section 9.2 applies its relative test (a 1 s window above `ign.factor` times the settled central mean) only when the settled central mean is at or above a floor `ign.min_baseline_hz`, proposed 0.5 Hz (the `rest.central_hz` floor); the absolute `ign.max_central_hz` 8 Hz test stays unconditional. Reason: two 3d rows at w_bg 0.75 are flagged `ignited` with a settled central rate of zero and a rolling maximum of 0.000188 Hz. No stored record is rewritten; a side file lists every existing row whose flag changes under the new rule. Lane WP28 (`tasks/WP28.md`).

88. (Rolf, same ruling.) Sub-tier 3c is not biologically closed: all 45 units carry `cbi-stiff` and the one that kept the reflex (retention 0.609, h_max 19.65 against the cut of 19) failed only that numerical gate. A timestep-convergence diagnostic runs on five 3c units spanning the h_max range, T0 with background off at dt, dt/2 and dt/4, recording h_max, retention and the MN9 difference at each step. If the results converge and retention holds, the stiffness cut is numerical and Rolf decides whether 3c reruns at the converged step; if retention collapses regardless, 3c stays closed. No readmission to T0 comes from the diagnostic itself. Lane WP28.

89. (Rolf, 2026-09-18 11:58, on the item 88 diagnostic `validation/records/p2/rest-T3c-convergence.json`.) The convergence check found the four stiffer 3c units physically closed (reflex lost at dt 0.1, 0.05 and 0.025 ms) and the closest miss `1.0-1.0-cbi--72.0-all` closed only numerically (retention 0.60, 0.70 and 0.64 across the steps; h_max 18.8, 17.9 and 16.1, under the cut of 19 at the finer steps). That one unit gets the T1 R-screen it never had, run at dt 0.05 ms on the rk4 path with the ordinary tier-3 T1 protocol (two adjacent weights, three seeds, the 2.3 rows, gradedness), the stiffness cut evaluated at that step, and T2 with item 74 if it passes; plain `lif+cbi`, no second mechanism. This completes sub-tier 3c rather than reopening it; the other 44 units stay closed. Cost about 5 dollars on one box; lane WP28 runs it as its deliverable 4.

90. (Coordinator decision under item 86, 2026-09-18 13:35, on `RANKED WP27-sigma 03b3f1e`.) Threshold spread produced the first R-screen passers of the whole search: `1.0-4.0-1.0-False-100-0.75-kc-6.0` (sigma_th 1 mV, pair 0.75/0.80), `1.0-4.0-2.0-False-100-0.75-kc-6.0` and `1.0-4.0-2.0-False-100-0.9-kc-6.0` (sigma_th 2 mV), every 2.3 row passing with F under 3 on the worst pair, KC 0.24 to 0.34 Hz and central 5.6 to 7.4 Hz. Their background-on reflex probes fail: at sigma_th 2 the sugar response at rest is gone (differences near 0 Hz), at sigma_th 1 it is about 36 Hz mean against a 56 Hz bare with one seed at 3 Hz and one at 83 Hz, failing the original (a)/(b) thresholds and, as the lane's collector scores it, item 74's harmonised (a) while passing harmonised (b). The T0 rows of that wave used base thresholds with background off and are not evidence about the spread network. Rulings: (i) the consultation's experiment 3 (`n_bg`) is not triggered, because F is no longer the remaining failure; (ii) experiment 4 runs now on the sigma_th 1 contender alone as lane WP27's deliverable 5: fresh seeds 11 to 20 at both pair weights, clamped and free pools, 32 s each; the paired sugar probes at both weights with the same-job bare reference; and the configured-weight perturbations w minus 0.05, w, w plus 0.05 on seeds 11 to 13; one box, cap 10 dollars list; both reflex verdicts recorded, nothing admitted by the lane; (iii) review r18f starts on `lane/wp27` at `03b3f1e` and must recompute the harmonised (a) verdict of the sigma_th 1 candidate from the rows, because a candidate that passes item 74's floors at rest would be the first ranked candidate of Phase 2 and goes to Rolf before anything else runs on it. No criterion changes.

91. (Reviewer r18f, sigma-1 item 74; 2026-09-18 14:17, `tasks/reviews/code-r18f.md`, merged into main at `3aa9413`.) Rule: `1.0-4.0-1.0-False-100-0.75-kc-6.0` fails item 74 as written. `(a)` is the six pair-weight MN9 differences; the floor is `min(a)` against 0.4 of the same-job bare mean (22.4 Hz at 56 Hz). min(a) = 3 Hz. Harmonised `(b)` would pass. The candidate is not ranked. No WAITING line.

92. (Reviewer r18f, 3 Hz and 83 Hz; 2026-09-18 14:17, `tasks/reviews/code-r18f.md`, merged into main at `3aa9413`.) Rule: both seeds are real dark-MN9, not a probe defect. Seed 2 at 0.80 is quiet then 84 Hz on sugar. Seed 3 at 0.80 is already 78 Hz in the dark. Settle holds. `_ab_pass` does not check mean(a).

93. (Reviewer r18f, T0 31.3 Hz; 2026-09-18 14:17, `tasks/reviews/code-r18f.md`, merged into main at `3aa9413`.) Rule: the sigma-wave T0 rows used base thresholds (`feedforward=True`, `thresholds=False`). The 31.3 Hz difference is background-off. It is not evidence about the spread network.

94. (Reviewer r18f, diagnostic admission; 2026-09-18 14:17, `tasks/reviews/code-r18f.md`, merged into main at `3aa9413`.) Rule: experiments 1 and 2 admit nothing to T1 or T2. The F cap is not relaxed. P2-partial-B stands. `collect_sigma` may reuse T0 diffs for both `(c)` streams; that does not admit a unit.

95. (Reviewer r18f, instrumented window; 2026-09-18 14:17, `tasks/reviews/code-r18f.md`, merged into main at `3aa9413`.) Rule: `_instrumented_probe` scores T1-comparable F and MN9 on `[2, 12)`, matching `_probe`. The committed JSON keeps the `[1, 11)` `mn9_hz` of 47.5 Hz. Docs state the `[2, 12)` rate 54.1 Hz. No record rewrite. flyo-11 was staged from `lane/wp27` before `92704fa`; its live probe still uses `[1, 11)`. The settle fix lands when this branch merges to main. This review does not touch the box.

96. (Reviewer r18f, freeze rematch; 2026-09-18 14:17, `tasks/reviews/code-r18f.md`, merged into main at `3aa9413`.) Rule: experiment 4 packing of `FREEZE_ID` (the sigma-1 R-screen passer) is diagnostic. `collect_freeze` sets `admitted_t1` and `admitted_t2` false. Item 74 still fails on the 3 Hz seed, so freeze does not rank the unit. One box, list cap $10, seeds 11–20. The freeze pair screen has no 0.85 mV gradedness point (item 90). Results are not in this review.

97. (Reviewer r18g, 2026-09-18, dt/2 versus dt/4.) Rule: the 38 Hz versus 36 Hz MN9 difference is within one-seed noise. Seed 1 at recorded dt 0.1 ms is 30 Hz against the 10-seed T0 mean 34.1 Hz. The same-job bare moves 54 Hz to 56 Hz. Retention stays ≥ 0.5 at every step. Mixed is the 0.05 retention-ratio tolerance (delta 0.061), not a lost reflex and not a T0 readmission. Sub-tier 3c stays closed at the item 89 R-screen.

98. (Reviewer r18g, 2026-09-18, T1 screen flags.) Rule: `collect_t1` unions unit flags with `screen_candidate` flags. The committed T1 record is not rewritten: S, `ranked` empty, and closest miss `1.0-1.0-0.0-False-100-0.7-cbi--72.0-all-kc-1.0` are unchanged. Raw rows remain 51 of 57 `cbi-stiff` at dt 0.05 ms (cut h_max > 39).

99. (Reviewer r18g, 2026-09-18, `t0_closest_miss`.) Rule: `decide_t3c_item89` keeps `t0_closest_miss` when the live decision is already the item-89 output. The T0 record stays byte-identical.

100. (Coordinator record under item 86, 2026-09-18 15:40, on `RANKED WP27-freeze f4ac736`.) The consultation's experiment 4 falsified the sigma_th 1 contender `1.0-4.0-1.0-False-100-0.75-kc-6.0`: on fresh seeds 11 to 20 the R-screen does not hold (F up to 3.10 at 0.80 mV, and two clamped seeds at 0.75 mV burst to F 9.2 and 8.3), the reflex at rest fails both the original thresholds and item 74's floors (mean(b) 29.2 Hz, min(a) minus 53.3 Hz, because MN9 was already firing before sugar), and the weight perturbation ignites at 0.70 mV. Its three-seed pass was seed luck at the edge of the cap. The consultation's sequence is complete (experiments 1, 2 and 4 run, 3 not triggered) for about 12 dollars of engine time against the 22 dollar cap; nothing is ranked; P2-partial-B stands. The one new fact worth carrying forward is the dark motor neuron: at rest MN9 fires 40 to 87 Hz in about half the seeds at 0.80 mV (both pools) and in a few at 0.75 mV, without sugar, so any reflex-at-rest criterion on this substrate is dominated by which seeds happen to have MN9 already on. What happens next is Rolf's call.

101. (Reviewer r18h, 2026-09-18, F max and the 9.2/8.3 bursts.) Rule: the record's F max 3.100 covers the twenty clamped `[2, 12)` pair rows. It is 0.80 mV seed 14. Clamped 0.75 mV seeds 11 and 18 are in the record. Their live `[1, 11)` F is 9.205 and 8.304 (`F_recorded`). Their scored F is 2.786 and 2.805. The collector is not wrong. The RANKED wording now names those rows. No record rewrite.

102. (Reviewer r18h, 2026-09-18, min(a) −53.3 Hz.) Rule: min(a) is 0.80 mV seed 13. Silent MN9 is 87.0 Hz. Sugar is 33.7 Hz. It is dark MN9 already on, not a collector bug. Bare mean 57.0 Hz. Item 74 floors 28.5/22.8 Hz. Original 50/40 fail. Harmonised (b) would pass the mean alone. `reflex-harmonised` is false.

103. (Reviewer r18h, 2026-09-18, dark MN9 in the record.) Rule: each freeze long row carries `mn9_hz` on `[2, 12)` and `mn9_hz_recorded` on `[1, 11)`. Item 100's carry-forward fact is reproducible from the record. Free-pool 0.80 mV has 7 of 10 seeds at 48.0 to 84.6 Hz. Both pools at 0.80 mV: 12 of 20 ≥ 40 Hz.

104. (Reviewer r18h, 2026-09-18, perturbation F 3.000 and item 87.) Rule: `freeze_perturbation` uses spec F < 3. 3.000406 at 0.80 mV seed 11 is a fail. 0.70 mV fails on F 42.8 at seed 12. Live `ignited` on 0.70 is the `0fd2aed` detector. Item 87 does not trip. The collector does not read the ignited flag. Perturbation F is already `_probe` `[2, 12)`.

105. (Reviewer r18h, 2026-09-18, diagnostic admission.) Rule: experiment 4 admits nothing to T1 or T2. Flags `diagnostic`. The F cap is not relaxed. P2-partial-B stands. Experiment 3 was not run. Overlay leaves `rates_hz` on the live `[1, 11)` window; `[2, 12)` group means also pass, so the screen verdict does not change.

110. (Coordinator record, 2026-09-18 16:38, Rolf's ruling on the research round; numbers 101 to 109 are left to review r18h.) Rolf asked for three research lanes instead of a ruling (16:25); their reports `docs/research/R1-rest-biology.md`, `R2-model-users.md` and `R3-dark-mn9.md` (merged, citations checked) agree on a cause the search never addressed: the connectome is heavy-tailed in in-degree and synapse count, so uniform brain-wide scaling cannot balance it (Landau 2016, Roxin 2011): the hubs cross threshold first and ignite, and inhibition strong enough to hold them kills the peripheral reflex; the dark MN9 of item 100 is that same pathology seen from the motor end; the 1 ms population Fano cap has no in vivo counterpart; and a 2026 preprint (Li, Ping, Zhang and Wang, bioRxiv 10.64898/2026.08.21.745055) reaches a resting state on FlyWire by regulating a small inhibitory hub set. Rolf's ruling (about 16:30): the non-uniform round, all runs on IBM (no Mac pilots). This item authorises WP29 (`tasks/WP29.md`), sub-tier 3e, on the 3d substrate (inhibitory ratio 4, GABA-to-KC factor 6, n_bg 100) with five arms, each a per-neuron vector through the existing `set_weight_scale` (postsynaptic gain) and `set_threshold` paths and the background-weight vector, no engine equation change: (A) background into sensory neurons only; (B) motor neurons exempt from the background; (C) incoming gain 1/sqrt(K_i/K_median) by in-degree; (D) deterministic thresholds rising with in-degree; (E) outgoing factor on the inhibitory hubs MBON06, LPi13, LPi15 and their reciprocal partners, only if the registry resolves those types. For this round only, item 42 (MN9 untouched) is relaxed to allow arm B (MN9 receives no direct background; nothing else about MN9 changes) and item 32 (one population factor) is relaxed to allow arm E. Every row records, beside the R-screen, the lab-standard measures from R1 (single-unit Fano at 100 ms on a fixed central sample, mean pairwise correlation at 50 ms, PCA participation ratio) as recorded-only diagnostics; the R-screen and items 74 and 87 are unchanged. Any R-screen passer goes through the reflex at rest and a fresh-seed freeze (the experiment 4 protocol) before it is ranked. Caps: two boxes, 20 dollars of engine time for the round, credit floor 30 dollars, the safe wait-pull-down pattern. Stop rule: if no arm yields an R-screen passer that keeps the reflex (item 74 floors) with dark MN9 under 5 Hz in every seed, the rest search closes for good at P2-partial-B and no further round starts without a new ruling from Rolf.
110.1 Arm A `sens`. Invert the background exemption: `w_bg` is `weight` on `groups['sensory']` and 0 elsewhere. The central brain receives only network-filtered input. Ladder 0.80, 1.00, 1.20, 1.40 mV (four points, 0.20 mV step: sensory-only drive is expected to need a higher range than the non-sensory 0.75–0.90 window). Adjacent pairs (0.80, 1.00) and (1.00, 1.20); gradedness uses the next ladder point.
110.2 Arm B `nomotor`. Keep the sensory exemption. Set `w_bg` to 0 on `groups['motor']` (MN9 included). Common ladder 0.75, 0.80, 0.85, 0.90 mV. Item 42 is relaxed for this arm only: MN9 gets no direct Poisson background; MN9 threshold, gain, and incoming weights are unchanged.
110.3 Arm C `indeg`. Incoming gain `1/sqrt(K_i / K_median)` through `set_weight_scale` on the postsynaptic side, composed with the 3d scale (g_gaba 1, g_glu 4, g_gaba_kc 6). `K_i` is the incoming synapse count (sum of `|Excitatory x Connectivity|` onto i). `K_median` is the median of `K_i > 0`. Values `K_i < 1` use 1 in the gain. Common ladder. Each record stores the K distribution (min, max, median of positive, p99, n_zero).
110.4 Arm D `thdeg`. `v_th_i = v_th0 + beta * K_i / 1000` mV through `set_threshold` after `Neuromod.compose`. `beta` in {0.5, 1.0, 2.0}. `K_i` as in 110.3. Common ladder. No random threshold draw (`sigma_th` 0).
110.5 Arm E `hubs`. Outgoing factor {2, 3, 4} on MBON06, LPi13, LPi15 and their reciprocal excitatory partners (neurons with excitatory edges both ways with a hub). Applied through `set_weight_scale` on presynaptic rows, composed with the 3d scale. Item 32 is relaxed for this arm only. If any named type does not resolve in engine-order `cell_type` or `hemibrain_type`, skip the arm, record why, and continue. Common ladder.
110.6 Wave. Plan `validation/records/p2/rest-T3e-plan.json`. Per arm setting: 12 s R-screen on `[2, 12)` at three seeds on the four-point ladder; T0 10-seed feed-forward (background off) because C, D and E can change the path; 10-seed paired sugar at each ladder weight; one same-job 10-seed bare per box. Lab measures from R1 are recorded-only on the 12 s probes (2000 central neurons, Fano at 100 ms; 500-neuron sample, pairwise correlation at 50 ms and PCA participation ratio). Packing: two `cx2-64x128` boxes, 75 worker-s per brain-s, list dollars include 600 s setup per box. No `up.sh` before `GO wp29`. An R-screen passer then gets 10-seed reflex at rest (seeds 1–10) and the experiment-4 freeze (seeds 11–20) before RANKED. Item 74 and item 87 stay as written.

111. (Coordinator record under item 110, 2026-09-18 18:24, on `RANKED WP29-3e b866fab () closest 1.0-4.0-0.0-False-100-1.0-kc-6.0-sens S=0 F=2.680 KC=0.0875 MN9dark=2.9` and `DONE WP29 .reports/WP29-report.md 6650d36`.) The non-uniform round ran as one wave of 50 tasks on two boxes for about 4.5 dollars. Outcome: arms B (motor exempt), C (in-degree gain) and D (in-degree thresholds) admit nothing (D's T0 reflex collapses to 10.8, 0.4 and 0 Hz at beta 0.5, 1.0, 2.0); arm E (inhibitory hubs) was skipped because the registry has no LPi13 or LPi15 and only two MBON06 cells; arm A (background into sensory neurons only) at 1.0 mV is the first unit in the whole search to pass the R-screen with the motor neuron dark: S 0, F 2.680, KC 0.0875 Hz, central 4.83 Hz, DAN 0.81 Hz, stability 1.001, dark MN9 at most 2.9 Hz in every seed, and healthy lab-standard measures (single-unit Fano 0.35 at 100 ms, mean pairwise correlation 1.6e-5 at 50 ms, participation ratio 20). It fails item 74 by a hair: the reflex at rest is present in every seed and pair weight, (a) 33, 34, 22, 19, 22, 21 Hz against the 22.4 Hz floor (min 19), (b) mean 27.4 Hz against the 28.0 Hz floor, (c) passes; T0 retention 0.559 passes. By the letter of item 110's stop rule (a passer must keep the reflex at item 74's floors) the rest search closes at P2-partial-B, and the lane recorded it so. The coordinator's reading for Rolf: this miss differs in kind from every earlier one (quiet, irregular, motor dark, reflex present but 0.6 Hz under a provisional floor on three seeds), the floors of item 74 are themselves provisional until Rolf confirms them, and the two cheap tests that would settle it are a fresh-seed freeze on seeds 11 to 20 (the experiment 4 protocol, about 4 dollars) and a finer ladder around 1.0 mV (0.9, 1.1, three seeds, about 1 dollar). Whether the search stays closed or takes one of those tests is Rolf's ruling; no box is created until he rules. Review r18i covers the WP29 code and records (decisions from 112).

112. (Reviewer r18i, 2026-09-18, passer.) Rule: `1.0-4.0-0.0-False-100-1.0-kc-6.0-sens` passes the R-screen from the raw rows. S 0. F 2.680. KC 0.0875 Hz. central 4.83 Hz. Item 87 does not trip. Dark MN9 max 2.9 Hz on the 12 s pair; sugar-silent max 4.0 Hz is 1.20 mV seed 4. `screen_passed` true. No failed checks.

113. (Reviewer r18i, 2026-09-18, item 74, including min(b).) Rule: differences are sugar minus dark on the same seed and pair weight. `(a)` is the six values from seeds 1–3 at both pair weights. That is the item 74 `(a)` test as written (decision 91). min(a) 19 Hz (1.20 mV seed 1: dark 3 Hz, sugar 22 Hz) vs 22.4. mean(b) 27.4 vs 28.0. min(b) 22 Hz (1.00 mV seed 3) vs 22.4. `_ab_pass` requires all three. Bare mean 56.0 Hz from the arm's 10-seed job. Original 50/40 fail. `reflex-harmonised` is false. A freeze on seeds 11–20 must clear those three floors and still hold the R-screen with dark MN9 under 5 Hz.

114. (Reviewer r18i, 2026-09-18, lab sample.) Rule: Fano 0.350 excludes 1,809 silent of 2,000, so it is the mean over 191 active units. 703 pairs are 38 of the fixed 500-neuron sample. PCA PR 20.01 is on that 500. Measures are recorded only. No verdict depends on them. No record rewrite.

115. (Reviewer r18i, 2026-09-18, arms.) Rule: arm A drives sensory only, and the 21 sugar GRNs are inside that group, so 150 Hz sugar is on top of 1.0 mV Poisson. Arm C used K median 200. Arm D T0 dies on high-K path cells (il3LN6, DNg35, MN9), not on the GRNs. Arm E skipped: LPi13 and LPi15 are absent; LPi12 n=4 and LPi21 n=2 exist; MBON06 n=2. A hub arm on those resolving types is still possible under a new ruling.

116. (Reviewer r18i, 2026-09-18, collector, IBM, admission.) Rule: the committed JSON is the corrected collect (screen pair, same-job 10-seed bare). Nothing under `rest-T3*.json` other than the new 3e files changed. Experiment 3e admits nothing to T1 or T2. P2-partial-B stands. IBM receipts are create/run/wait/pull/down; nothing left; `scripts/ibm/` unchanged.

120. (Coordinator record, 2026-09-18 18:33, Rolf's ruling on item 111; numbers 112 to 119 are left to review r18i.) Rolf chose the deciding wave: ten fresh seeds at three weights around the passing point, same protocol as experiment 4. This item authorises WP30 (`tasks/WP30.md`) on the sensory-only arm of sub-tier 3e (`1.0-4.0-0.0-False-100-<w>-kc-6.0-sens`, item 110 arm A) at 0.9, 1.0 and 1.1 mV, seeds 11 to 20: long dark rows (the R-screen on `[2, 12)` with the later windows recorded), paired sugar, the same-job bare on the same ten seeds, both item 74 verdicts, dark MN9 per row, the lab-standard measures recorded, and the weight perturbation on seeds 11 to 13. Ranking rule: a weight ranks if the R-screen holds on every one of the ten seeds at both pair weights, dark MN9 stays under 5 Hz in every seed, and item 74's floors (mean(b) at 0.5 of the same-job bare mean, and min(a) and min(b) at 0.4 of it, decisions 91 and 113) are met on the ten seeds; a ranked unit goes to WP19 on the parked w19 lane as the resting substrate, and the item 74 floors used are the ones Rolf then confirms. If no weight ranks, the rest search closes for good at P2-partial-B (items 81, 111) and no further round starts without a new ruling. Caps: one box, 8 dollars, credit floor 30, the safe pattern, plan and projected cost pushed as WAITING before the first box.
120.1 Wave. Plan `validation/records/p2/rest-T3e-freeze-plan.json`. Arm A `sens` on the 3d substrate. Candidate weights 0.9, 1.0, 1.1 mV. Pair at each candidate is the 3e arm A step of 0.20 mV: (0.9, 1.1), (1.0, 1.2), (1.1, 1.3). Run weights 0.9, 1.0, 1.1, 1.2, 1.3 mV. Seeds 11 to 20. One clamped 32 s long dark row per seed and run weight (R-screen on `[2, 12)`, later windows recorded; no free pool). Paired sugar 3 s at each run weight. One same-job 10-seed bare. T0 feed-forward on the same ten seeds. Perturbation ±0.05 mV on seeds 11 to 13 at each candidate weight (unique probes 0.85 to 1.15 mV). Lab measures recorded-only on the long-row `[2, 12)` window. No gradedness point (experiment 4). Item 74 (a) is the six pair-weight differences on seeds 11 to 13, (b) the ten-seed mean at the candidate weight and min(b) at or above 0.4 of the same-job bare (decision 113); original 50/40 recorded too. One `cx2-64x128`, 75 worker-s per brain-s, list dollars include 600 s setup. No `up.sh` before `GO wp30`.
120.2 Civo scaffolding (WP30, 2026-09-18, Rolf: coding only, no compute). IBM login rejected (`BXNIM0434E`, account blocked). `scripts/civo/` mirrors `scripts/ibm/` on the Civo REST API (`https://api.civo.com/v2`), with `CIVO_DRY_RUN=1`, detached wait, pull before down, `CIVO_DOWN_OK=1`, `CIVO_LEFTOVER_NAME`, receipts under `validation/records/p2/civo-receipts/`. Default size `g4p.xlarge` (Performance Extra Large: 32 cores / 128 GB / 250 GB NVMe, **$0.952384/h** on the public list 2026-09-18). Key path `~/.config/civo/api_key`, never printed. No instance created under this record. The freeze plan in 120.1 stays ready; repack workers and dollars before the first live Civo `up.sh`.
120.3 Modal scaffolding (WP30, 2026-09-18, Rolf: Civo gave nothing; coding only, no compute). Target is Modal Functions. `scripts/modal/` runs one freeze task per `run_task` (cpu 1.0 physical core, timeout 14400 s with margin), fans the plan with `.map`, writes `camber-runs/wp30/<label>/`, cache on Volume `flyo-cache` via `upload.sh`. Image: Debian 3.12 + `uv sync --frozen`. Token `~/.modal.toml`, never printed. CPU dollars at the public price $0.0000131 / physical-core / s for 2472 brain-s × 75 worker-s/brain-s = **$2.4287**. No function run, no image build, no volume upload under this record.
120.4 Modal runner (WP30, 2026-09-18, Rolf: the rolfyildirim workspace has about 8 dollars left; the wave must survive a credit stop). Coding only until a GO that names Modal. `run_task` returns the ndjson body. The driver writes each file to `camber-runs/wp30/<label>/` as that result arrives (`order_outputs=False`), not after the map. Task order: weight 1.0, then 0.9, then 1.1; bare rows first within each (shared bare with 1.0, then dark longs, then sugar). `MODAL_MAX_DOLLARS` default 6, from the public per-core-second and per-GiB-second prices; the driver stops submitting when the next task's projection would cross that ceiling. Cost projection uses cpu=0.5 physical core per single-thread worker unless measured otherwise. CPU dollars 2472 × 75 × 0.5 × $0.0000131 = **$1.2144**. No function run, no image build, no volume upload under this record.



121. (Coordinator record, 2026-09-18 23:01, Rolf's stop.) R4 (`docs/research/R4-mn9-facts.md`, lane fact1) finds that MN9's firing rate has never been recorded electrically in a living fly, at rest or during the sugar reflex; what exists is calcium imaging (flat at rest, about 50 percent brighter at 100 mM sucrose, about 90 percent at 1 M) and video of the extension. Shiu 2024 assumed a basal rate of 0 Hz, tuned the synaptic weight against the model's own MN9 output, and validated by whether the rostrum extends (106 cell types, 91 percent agreement), never by a rate. So Phase 1 test 1.1's "above 50 Hz", test 1.4r's reflex band, R-reflex (a) and (b), and item 74's 0.5 and 0.4 floors are numbers fitted to the model with no measured counterpart. Rolf: "we wrote down an imaginary number as a rule and kept chasing it as a real number"; the coordinator confirms it set the number. Standing: those floors are recorded measures, not pass or fail lines, and item 120's ranking rule is void where it leans on them, so WP30's stop is not a close of the rest search under item 120's last sentence. Facts of record: on the sensory-only arm at 1.0 mV (item 110 arm A), ten fresh seeds 11 to 20 hold the R-screen (F max 2.619, KC 0.089 Hz, central 4.83 Hz), dark MN9 stays at or under 4.7 Hz, and the sugar reflex fires on every seed at mean 26.6 Hz and minimum 19.3 Hz against the same-job bare 57.0 Hz (retention 0.956; `validation/records/p2/rest-T3e-freeze-partial.json` on `lane/score30`). Weight 0.9 has seeds 11, 12, 15, 16, 19, 20 home and unscored; 1.1 has seeds 12, 13; the rest never ran. Rolf stopped Modal and closed every lane at 23:01 ("stop modal", "close all panes"). What the reflex at rest is judged by, and whether the rest search continues, is his to say; no compute and no lane starts until he does. Repo cleanup and consolidation are authorised (`tasks/cleanup-c1.md`, lane clean1).

122. (Rolf's ruling, 2026-09-19 13:29, answer 1 to the coordinator's ask a-1.) Rolf: "Take this calm brain as our starting point and begin the attention tests on it." Reading: the sensory-only arm at 1.0 mV (item 110 arm A; facts of record in item 121) is the declared Phase 2 resting substrate, and the rest search closes on it. WP18, WP20, WP21 and WP22 move onto it; their parked branches (lane/w18, lane/w20, lane/w21, lane/w22) resume from main. Item 74's 0.5 and 0.4 floors, test 1.4r's reflex band and R-reflex (a) and (b) stay recorded measures, never pass or fail lines (item 121): the reflex at rest is reported as its measured value beside the same-job bare. The 0.9 and 1.1 mV partial seeds stay recorded and unscored.

123. (Coordinator decision, 2026-09-19 14:22, t-0001 open questions 1 and 2.) Item 122 bypasses WP19's K1r and Q-rest chain, and WP19 is closed, so `data/drive-v0.2.yaml` for item 122's unit (`1.0-4.0-0.0-False-100-1.0-kc-6.0-sens`) is committed once, by lane t-0001 in round r19, and every other lane merges it rather than writing its own. It is a canonical configuration, not development class: item 122 makes it the resting substrate. Its `provenance` block names item 122 and the two rest records `validation/records/p2/rest-T3e-decision.json` and `rest-T3e-freeze-partial.json` with their SHA-256s.

124. (Rolf's GO, 2026-09-19 14:29.) Rolf: "anything thats ready to run run it rn". Compute is Rolf's Oracle box `compute host` (16 cores arm64, Ubuntu 24.04; facts in the herdr-ade PROJECT.md), reached over SSH from a lane's pane; results come back into this repo on the Mac. First wave: WP18's V-cal, V1 and V3 at item 122's unit (lane t-0001, plan of about 860 brain-seconds). WP21's neural half follows when its plan is ready (lane t-0002). The engine's platform record reads linux-aarch64 there, a deviation from the Mac and x86 records, recorded with the first run.

125. (Coordinator decision, 2026-09-19 15:06, t-0002 WAITING.) The neural wave also needs `data/dopamine-v0.2.yaml`, which no branch has: item 122 skipped WP19's chain, and K2r never ran on the declared unit. Lane t-0002 runs K2r as section 5 defines it (`neuromod/calibration.py`, three seeds, about 130 brain-seconds with its free-pool iterations) on the declared drive `rest:379cc4cc9030cdd1` on the Oracle box, and commits the one canonical `data/dopamine-v0.2.yaml` with the K2r record SHA-256 in `provenance`. Every other lane merges that commit. Q-rest is not rerun as a gate: item 122 already declared the unit on the ten-seed freeze facts. Where code needs a Q-rest record, the lane records its measures without pass or fail (item 121).

126. (Coordinator record, 2026-09-19 16:27, r21 review f4addb4.) With the rest search closed (items 122, 123), section 3.7's photoreceptor-failure step 1 (move to the next ranked candidate that passes R3 and rerun the WP19 chain) no longer applies: there is one declared substrate and no ranked list to fall back on. A photoreceptor failure goes straight to step 2, the TuBu path. The visual-status machine carries that since r21.

127. (Coordinator record, 2026-09-20 21:01, lane t-0014, `docs/optic-lobe-silence.md`.) Why the visual path is silent on item 122's substrate, measured on the Oracle box in four arms: the declared model gives its inhibitory visual relays no depolarizing operating point. The sensory background reaches R1-6 (ambient 91.347 Hz) but not L1/L2, which sit at about -57.0 mV against an unchanged -45 mV threshold. The stripe does reach the lamina: releasing photoreceptor inhibition raises ipsilateral lamina voltage by 0.599 to 0.808 mV, far short of threshold, so every downstream population emits zero spikes in all twelve conditions, darkness included. The connections are intact and correctly composed: R1-6 to L1 is 5,867 pairs and 63,344 synapses, to L2 5,727 and 62,051, every composed pair negative and non-zero. Counterfactuals, recorded and not adopted: 1 mV of optic background gives sparse lamina activity with no consistent narrow-stripe contrast; 2 mV wakes L1 and L2 with a local narrow-stripe response on both sides (L1 +1.284/+1.217 Hz, L2 +0.236/+0.104 Hz) but does not restore the visual path; restoring the connection-file photoreceptor signs activates L1/L2 but reverses their stripe response and leaves Mi1 and Tm3 silent. LPLC, MeTu and TuBu stay completely silent in every condition of every arm. Reading: this is a property of the model as specified, not an engine, sign or index defect, and no firing floor or histamine sign flip repairs it (item 121 stands). Consequence for Phase 2: the TuBu path (section 3.7 step 2, running under lane t-0013) tests the central and steering circuitry under injected visual input; it is a downstream-input substitution and cannot demonstrate retina-to-brain vision. Whether Phase 2 accepts that or opens a visual-model revision is Rolf's to say once the TuBu wave reports.

128. (Coordinator record, 2026-09-20 11:22, r30 merged `bac1b08`, lane t-0019, `docs/signal-transfer-audit.md`, `validation/records/p2/signal-transfer-audit.json`.) Where the signal goes on item 122's substrate, from a zero-time graph audit on `darwin-arm64` plus a 48 brain-second paired voltage probe on the Oracle box. Eye path: the stripe reaches the lamina and moves it in the right direction. All 64 condition-selected strongest immediate targets of R1-6 receive a positive release-from-inhibition event change and depolarize by 1.012 to 4.154 mV in three-seed means (seed means of the pooled change span 0.063 mV), with stripe mean threshold gaps of 11.073 to 62.519 mV and nearest sampled gaps of 8.919 to 52.574 mV. None spikes. This does **not** supersede item 127: that item reports whole-population ambient means (L1 -57.038, L2 -57.015 mV) and ipsilateral stripe deltas (0.599 to 0.808 mV), while this audit reports a condition-selected subset pooling to -71.024 mV (selected L1 -65.5, L2 -66.7, Am -81.6, L3 -58.5). Different target sets; both stand, and -71 mV is never the population mean. TuBu path: TuBu has 656 immediate targets through 1,859 all-positive composed rows and 21,349 anatomical synapses; 37 of 64 strongest children raise their spike count when TuBu fires, so the TuBu signal survives its first relay and item 127's silence does not extend to it. Coverage, which is the ruling that changes what we may claim: TuBu directly reaches 244 of 8,053 `visual_projection` cells and 5 of 547 `LAL_neurons`, and reaches no `DNa02` or steering cell at all — those lie two hops out. The r25 readouts that produced the open-loop fall-through (`visual_projection` +9.52e-05 Hz, `LAL_neurons` +3.81e-03 Hz) were whole-population means over those observers, taken from the same populations this audit measured. A spiking response confined to the directly reached cells would appear in those means reduced by size factors of about 33 and 109. **The audit measures coverage, not a division: whether those reached cells respond is unmeasured.** Consequence: the r25 null is not evidence that steering does not respond, and equally is not evidence that it does. The open-loop visual status stands as the recorded status, but the measurement that justified it cannot carry that weight. Lane t-0029 measures the reached subset per cell, with unreached cells as a control and every two-hop endpoint reported individually; the status is Rolf's to revisit on that result.

129. (Coordinator record, 2026-09-20 11:22, r31 merged `73c11d1`, lane t-0024, `docs/dopamine-activity-dependence.md`, `validation/records/p2/dopamine-activity-dependence.json`.) A retraction of what the merged pharmacology results are evidence for. `neuromod/calibration.py::rest_release_constants` sets `alpha_c = q / max(R_c, R_min)` and `S_c = max(0, q - alpha_c * R_c)`, so `alpha_c * R_c + S_c = q` in both branches for non-negative `R_c`; the committed `data/dopamine-v0.2.yaml` has `R_c = 0` for all 37 compartments, mode `source`, so the branch taken is exact and the sustained release the fixed point sees is `q = 0.0026667` µM/s whatever the measured firing rate. The fixed points follow in closed form: `da* = DA_ref = 0.02` µM for wild type and `da* = q / k_ns = 0.0533` µM when `Vmax = 0` (fumin). Every merged value reproduces from that closed form to the last bit — methylphenidate 0.037989169674944576, 0.0484631907095745 and 0.050704812545102375 µM, 3-iodotyrosine 0.006862099486803409 µM wild type and 0.01841390658021888 µM fumin — and the recorded fumin 0.05333333333333334 differs from the fixed point by 6.94e-18, one unit in the last place of `q / k_ns`. Across all 98 arm, seed and probe rows of the four committed runs, no innervated dopamine neuron fires in any spontaneous or drug arm except a single spike from CX_DAN `PPM1205` (engine index 107102, root 720575940632126860) at t = 2436.2 ms in the dose-p2 vehicle arm, seed 2, probe 12; the only spatial variance anywhere in the dopamine record is that cell's four target compartments (EB, FB, NO_L, LAL_L) in its innervation-weight ratios, plus two settle transients of the same cell with the same four-compartment signature. It is the only one of 138,639 columns with exactly those four non-zeros. **Ruling: the 3.2r to 3.5r results are correctness controls on the dopamine kinetics and genotype module, not circuit-level evidence.** Fumin carrying over twice wild-type dopamine, methylphenidate raising dopamine dose by dose in wild type and doing nothing in fumin, and 3-IY lowering it in both are the encoded assumptions returning themselves. Two limits on how far this retraction reaches. The dopamine layer is not inert: the `descending-pam` PAM arm carries 549,582 innervated dopamine spikes at 31.77 Hz and a spatially structured field spanning 0.02 to about 30 µM, so the coupling works and is dormant rather than broken, and that arm is the separate activity-driven positive control. And 3.6r and 3.10r record firing rates downstream of the dopamine field; they are not dopamine measurements and must never be reported as such. The control of running the fixtures with recurrent activity removed was not run and is not needed: those arms already have no innervated firing and the `source` branch fixes the pool at `q`, so it would return the same fixed points by construction.

130. (Coordinator record, 2026-09-20 11:40, r32 merged, lane t-0028, `docs/eye-path-audit.md`, `validation/records/p2/eye-path-audit.json`, `scripts/eye_path_audit.py`.) Three reconciliation checks on the eye path, raised by an outside consultation on the r30 probe and answered by arithmetic against committed evidence with no engine run. (i) Thresholds: the declared substrate carries no threshold spread. `data/drive-v0.2.yaml` has `threshold: null`, so `sigma_th` is 0.0 and `apply_rest_substrate` returns a flat -45.0 mV over all 138,639 cells; `rest_tier3.py::candidate_id` orders the id as `g_gaba-g_glu-sigma_th-optic_exemption-n_bg-w_bg`, so in `1.0-4.0-0.0-False-100-1.0-kc-6.0-sens` the `0.0` is `sigma_th` and the `False` is `optic_exemption`. The variation seen in the r30 rows is the dopamine layer's `d_v` composed on top by `Neuromod.compose`: 30 distinct composed values spanning -45.014706 to -44.428571 mV, carried by 6,138 of 8,725 dopamine-exposed cells. All 64 eye targets sit at exactly -45.0 because they are sensory and unexposed; 57 of 64 TuBu targets sit at -44.743697 because they are exposed. **Ruling: where the signal-transfer probe reports a gap or distance to threshold, it is a gap to the composed threshold, not to the declared -45 mV, and must be stated that way.** The recorded 7.2355 mV TuBu gap is internally consistent and sits 0.22 mV above the declared-threshold gap of 7.0072 mV. Only three committed records report a distance to threshold and none mixes the two conventions. (ii) Drive: the photoreceptor contribution reconstructs from the instantiated weights and recorded events to within 0.17 mV over 384 target, condition and seed rows (mean residual -0.0003 mV, standard deviation 0.0445 mV, five rows above 1 percent, largest 1.5 percent on an 11 mV drive). Recomputing every traced target's effective weight sum and synapse total from the raw connectome arrays reproduces the committed static rows exactly, so the synapse count, `w_syn` and the transmitter multiplier each enter once; a doubled count or multiplier would put the deepest target at about -168 mV at the membrane rather than -110. The predictor is not circular: the event sum comes from engine spike counts and raw-derived weights, independent of the sampled voltage. This establishes that the implementation delivers the current it specifies; it does not establish that the current is right. (iii) The -110 mV tail is a recorded limitation of the declared current-based substrate, which has no reversal potential and so cannot self-limit. Under SPEC-P2 3c's conductance steady state with the project's own reversal placeholders, the deepest traced target would settle at -66.86, -60.53 or -56.60 mV for a chloride reversal of -72, -62 or -57 mV, shifts of 43.00, 49.34 and 53.26 mV; across all 64 targets the deepest mean sits 37.9 to 52.9 mV below the reversal range and the deepest sample 49.5 to 64.5 mV below it. In biology the photoreceptor-to-lamina synapse is histaminergic and gates chloride, so its hyperpolarizing force weakens as the cell approaches reversal. **No engine change is proposed or adopted and no conductance model is recommended; this is a written, quantified limitation only, and whether Phase 2 revisits the synapse formulation is Rolf's to say.** Noted and deliberately not claimed: at a -57 mV reversal the conductance steady state is -56.60 mV, close to item 127's L1/L2 population means of about -57.0 mV. That may be coincidence and is not presented as a finding.

131. (Coordinator record, 2026-09-20 12:24, r34 merged, lane t-0029, reviewer t-0032, `docs/tubu-reached-subset.md`, `validation/records/p2/tubu-reached-subset.json`, `scripts/audit_reached_subset.py`.) The steering measurement item 128 said was missing, now made: TuBu off versus on at 70 Hz on item 122's declared substrate, ten seeds, 20 s paired probes, 400 brain-seconds on the Oracle box, 774 cells traced individually and never as a population mean. Anatomy first, because it explains the earlier observer choice: TuBu's dominant projection is the ellipsoid body, reaching 228 of 278 `ER` cells through 479 pairs and 15,213 synapses at +4,183.575 mV composed, against 244 of 8,053 `visual_projection` cells at +83.875 mV and 5 of 547 `LAL_neurons` at +1.925 mV — a fiftyfold difference in composed weight, and no direct reach to any steering or `DNa02` cell. **Ruling, superseding item 128 narrowly:** for this injection and rate, the directly reached `visual_projection` cells (0 of 244 firing) and `LAL_neurons` (0 of 5 firing) are a *measured* null on all ten seeds, not an unmeasured one; the best-fed LAL cell takes +14.4 mV/s and reaches -49.843 mV, still 4.843 mV below threshold. TuBu is not silent at its main projection: 55 of 228 directly reached `ER` ring neurons fire with input on and 0 with input off, emitting 4,157 to 4,290 extra spikes over 18 s on every seed, across ER2, ER3w, ER3d, ER5, ER3p, ER4m, ER4d and ER3m, while the 173 weakly-fed ER cells stay silent (class median input 5.164 mV/s). The four steering endpoints receive no direct TuBu event and show no consistent paired direction: `steering_L` exactly 0 on every seed, `steering_R` mean -0.2, `DNa02_L` +3.7, `DNa02_R` -6.6, all straddling zero; of eleven positive two-hop intermediates only CL053 gains anything, +1.6 spikes. Controls were selected from anatomy and metadata rather than response: 244 matched unreached `visual_projection` cells and 5 matched LAL cells fire on no seed and carry exactly zero TuBu event. **These findings concern this injection at this rate, not every possible input**, and item 128's warning about the r25 population averages remains historically correct. Consequence: the open-loop visual status now rests on a measured null at the steering output rather than on a diluted population mean. The signal enters the central complex and stops there.

132. (Coordinator record, 2026-09-20 12:24, r34, reviewer t-0032, `src/flyonenomics/engine/brian_engine.py`, `docs/SPEC.md` §3.1.) The engine trace cap. Lane t-0029 raised it from 64 to 4,096 to trace its census in one build; review measured the cost and reduced it to the 774 actually executed. The facts, recorded so the next enlargement is not guessed: the old 64 **rejected** excess traces rather than truncating them, so no previously merged result was silently cut short; the executed census traced 774 cells, not the 656 the lane reported; its raw 20 s voltage monitor is about 1.238 GB per worker with about 1.115 GB more for extraction; and a 4,096-cell plain-`lif` run would take about 6.55 GB raw plus about 5.90 GB extraction **per worker**, enough to exhaust either machine under plausible concurrency. **Ruling: the cap stands at 774, the measured census, and is not a licence for more.** Any later enlargement needs a duration-, model-, worker- and machine-aware memory budget first, not a number chosen to fit a run. Trading a loud rejection for an out-of-memory failure is a worse contract, not a better one.

133. (Coordinator record, 2026-09-20 12:35, outside consultation on items 130 and 131, no lane, no run.) Two corrections and one limitation, recorded before they are forgotten. **(i) A conductance synapse at the visual periphery would not restore vision, and would weaken the signal.** With leak and histamine alone, every reversal potential in item 130's table leaves the equilibrium at or below -52 mV, so releasing inhibition still cannot cross the -45 mV threshold and the spike-only output bottleneck survives unchanged. Worse, the same reference-current-matched mapping that lifts the baseline also shunts the response: for illustrative inhibitory drives of 19 mV ambient and 17 mV stripe at `E = -62 mV`, the baseline improves from about -71 to about -58.55 mV while the stripe response falls from 2 mV to about 0.26 mV. Conductance brings saturation and shunting, not merely a voltage floor. A counterexample against reading item 130 as an indictment of current-based modelling: Lappalainen's successful graded early-visual model uses additive synaptic inputs rather than chloride-reversal conductances, so the missing ingredient there is graded release, not conductance. Item 130's 43 to 53 mV shifts stand as differences between formulations under assumed reversals; they are not measured biological errors, and they are a constant-drive counterfactual rather than the mean voltage of a dynamically simulated conductance network. **(ii) The -57 mV near-coincidence in item 130 is construction, not evidence, and is withdrawn even as a curiosity.** At the chosen `E = -57 mV` and `h = 11.575`, `V - E = (v0 - E)/(1 + h) = 10/12.575 ≈ 0.398 mV`: the mapping forces a strongly inhibited cell close to whatever reversal is chosen, so matching it to an earlier current-based population average supplies no independent support. **(iii) A limitation on item 131.** That measurement traced *positive* two-hop paths from TuBu and asked whether firing increased. Positive paths alone cannot establish where all transmission stops: an inhibitory or disinhibitory route to the steering endpoints would not appear in that census, and is not excluded by it. Item 131's null is a null for increased firing along positive paths at one injection and one rate.

134. (Coordinator record, 2026-09-20 13:05, r35 merged, lane t-0033, reviewer t-0034, `docs/ring-dopamine-design.md`, `docs/ring-dopamine-stage1.md`, `validation/records/p2/ring-dopamine-stage1.json`.) Stage 1 of the ring-neuron dopamine experiment, the direction Rolf approved in chat on 2026-09-20 after items 128 to 133 closed the visual route. **Census, recomputed by review from the committed `M` matrix:** exactly nine neurons have a non-zero ellipsoid-body column, all `CX_DAN`, with EB weight sum 2.40025241 of which the four largest carry 2.38680. All 331 mushroom-body `DAN` members have zero EB columns, so `PAM` — the population `descending-pam.json` drives — puts nothing into EB, and item 129's `PPM1205` is only the seventh of the nine (EB 0.00308642 against FB 0.97530866). The population to drive is `CX_DAN`, of whose 30 members 9 carry EB innervation; no existing population name selects only the nine, so a named subset or explicit root list is needed to drive them alone. All 228 traced `ER` cells read their exposure from EB alone at weight 1.0 with `r1 = 1.0`, `r2 = 0.5`. **Probe, ten seeds, paired, 20 s, 400 brain-seconds on the box, both arms with the TuBu stripe on and the driven arm adding `activate CX_DAN 50 Hz`:** ellipsoid-body dopamine rises from the 0.02 µM fixed point to 3.388–3.568 µM (paired difference +3.4586 µM [+3.4253, +3.4919]), peaking at 5.3 µM against the 5.013 µM the closed form gives at 20 s. Ring responders rise from 55 to 61 per seed (+8.5 [+6.19, +10.81]) and ring spikes by +1550.4 per seed [+1515.0, +1585.8]; the composed threshold shifts -0.4035 mV [-0.4064, -0.4006]. The TuBu input is unchanged between arms (-0.0190 Hz [-0.0574, +0.0194], including zero), so the ring change is not an input change. The dark arm independently reproduces item 131's 55 of 228 responders — review confirmed it is a fresh run, with per-seed counts and one marginal cell differing — and nine of ten dark seeds hold EB at exactly 0.02 µM. **Limitation, at the same standing as the result: this probe cannot separate the dopamine field from fast synaptic transmission.** `CX_DAN` has 231 direct edges onto `ER` (410 synapses, 230 excitatory), the dark arm has zero `CX_DAN` spikes, and the record carries no `CX_DAN`-to-`ER` event amplitude. The threshold shift is field-mediated by construction, being exactly the `d_v` term, but the spike and voltage changes are only consistent with it. A `dan_fast_synapses: "disconnect"` arm isolates the field and stage 2 carries one. Stage 2 may proceed.

135. (Coordinator record, 2026-09-20 13:05, r35 review t-0034, `neuromod/receptors.py`.) A property of the receptor model that any dose series must be designed around, recorded before stage 3 walks into it. The ring-neuron threshold term is `d_v = -1.5*occ1 + 1.0*occ2` and is **non-monotonic in dopamine**: it peaks at +0.555029 mV at `da = 0.16219` µM and crosses zero at `da = 1.849999` µM. So a small dopamine rise *raises* the ring threshold, making those cells harder to fire, and a large rise *lowers* it. At stage 1's measured 3.46 µM the field is past the crossover. **A dose series that straddles 1.85 µM will produce a U-shaped response that is a property of this receptor equation, not a finding about flies**, and must be reported as such or designed to avoid the crossover. This is recorded as a modelling fact, not a defect; whether the two-receptor weighting is right is a separate question nobody has asked.

136. (Coordinator record, 2026-09-21 04:20, r36 merged, lane t-0035, reviewer t-0036, `docs/ring-dopamine-stage2.md`, `validation/records/p2/ring-dopamine-stage2.json`, `scripts/ring_dopamine_stage2.py`.) Stage 2 of the ring-neuron dopamine experiment, which exists to settle the limitation item 134 recorded at the same standing as its result. Five paired arms, ten seeds, 20 s probes, 1,000 brain-seconds on the Oracle box, 228 traced `ER` cells, the TuBu stripe on throughout, reported per cell and never as a population mean. **The measurement:** of item 134's +1550.4 ring spikes per seed, **+1465.7 survive with `CX_DAN`'s fast synapses disconnected** [+1428.2964, +1503.1036], and retain minus disconnect is +84.7 [+34.4638, +134.9362]; both exclude zero. The survival fraction 0.94650198 [0.91472, 0.97828] is a **mean of per-seed ratios**; the ratio of the paired means is 0.94536894, and the two are different statistics that the record must not conflate. The `CX_DAN`-to-`ER` event amplitude item 134 lacked is +77,177.9 mV composed with the synapses retained and exactly 0 with them disconnected. **Ruling: item 134's effect is attributed to the dopamine field rather than to `CX_DAN`'s ordinary transmission, but as a lower bound and not a partition.** Two reasons, both established by review and both pointing the same way. (i) The `disconnect` layer zeroes all 70,134 `DAN` and `CX_DAN` outgoing edges — 7,919 `CX_DAN`, 62,215 other `DAN`, 213 onto a traced `ER` — not only the 231 edges the confound concerns, and the raw files record `CX_DAN` spikes alone (dark 0 to 1 per seed, driven about 19,700 to 20,400) with no count for the other `DAN` cells. If any removed non-`CX_DAN` edge is active in the dark, the disconnect arm loses that input too, so +1465.7 is conservative; the direction is established and the magnitude is not. Stage 3 records dark `DAN` spikes. (ii) The two driven arms are **not matched on the field**: disconnecting `CX_DAN`'s recurrent input moves its own rate from 36.743 to 37.436 Hz and EB dopamine from 3.4786 to 3.4303 µM, a paired +0.0483 µM [+0.00647, +0.09014] excluding zero, and on the descending branch the retain arm's higher field lowers its threshold by 0.00359 mV — the same direction as the fast route, so **+84.7 is an upper bound on the fast route**. Separately, the split into +1465.7 and +84.7 sums to +1550.4 but is a partition only if the field and the fast route add linearly, which was not tested; the clean design is a two-by-two of fast edges present or absent crossed with ring modulation dynamic or clamped to its vehicle trajectory, and stage 2 ran three of its four cells. **Disconnect audit, verified by review against a copy of `engine._syn.w` taken before and after an in-place write:** the 15,021,849 other synapses unchanged at 23,131,243.575 mV, presynaptic and postsynaptic index arrays unchanged, the EB innervation row unchanged at weight sum 2.40025241, the EB fixed point 0.02 µM on both sides. The layer removes the fast route and nothing else, so item 129's warning about deleting cells together with their tonic sources is answered. **Genotype:** `fumin` is `ScaleDat factor 0` with the connectome and TuBu protocol held fixed. Concentrations are reported before any ring difference, as item 135 requires: wild type 3.4786 µM retained and 3.4303 disconnected, `fumin` 4.0281 and 3.9645, both genotypes on the same descending branch of `d_v`. `fumin` minus wild type is +62.7 spikes [+23.50, +101.90] retained and +91.0 [+50.93, +131.07] disconnected, both excluding zero; the active-cell count (+0.9) and the TuBu source rate both include zero. That is 4 to 6 percent of the field's own spike effect, carried by 43 of 228 cells. **The genotype difference is real, paired and small; it is not a switch.** Stage 3 may proceed, carrying the disconnect layer.

137. (Coordinator record, 2026-09-21 04:25, outside consultation on items 134 and 135, no lane, no run. The wording fixes it caused are in r36's review commits; the corrections themselves are mine.) **(i) Item 135 names the wrong number and is corrected here.** It says a dose series straddling 1.85 µM will produce a U-shaped response belonging to the receptor equation. That is wrong. 1.85 µM is where `d_v` crosses **zero**, which is only where the offset changes sign relative to the unmodulated threshold; the **turning point** of `d_v` is 0.16219 µM, and above it the curve descends monotonically. From stage 1's 3.46 µM vehicle a dopamine-raising series moves monotonically down that branch and produces no U. What survives, and is the sharper point, is that **a 20-second mean concentration does not place a whole trial on one branch**: every driven trial climbs through 0.16219 µM on its way up, so the trajectory visits the turning point even when the mean does not. A dose series must be designed against `d_v(D(t))`, not against a mean. Item 135's other numbers — the +0.555029 mV peak, the 0.16219 µM turning point, the 1.849999 µM zero crossing, and the instruction that a curve belonging to the equation must never be reported as a finding about flies — stand unchanged. **(ii) An interval that includes zero is not equivalence, and item 134 states one as if it were.** Item 134 reports the TuBu input as "unchanged between arms" on the strength of -0.0190 Hz [-0.0574, +0.0194]. The correct reading is no detected mean-rate difference, and this project already carries that ruling from r28. A pooled mean rate can also hide changed effective input, since spike timing and connection-weighted rate are not the mean; r36 computed the connection-weighted TuBu-to-`ER` event for stage 2 at -2,131 mV [-7,464, +3,202], which likewise includes zero and likewise is not equivalence. **(iii) "Responder" was the wrong word throughout stages 1 and 2 and is now "active cell".** Both arms carry the stripe and neither stage ran a stripe-off condition, so a cell counted as responding is an active cell, not a demonstrated stripe responder, and increased firing could be non-specific activation. Demonstrating visual modulation requires stripe-on minus stripe-off compared across dopamine conditions, which no stage so far has run. Related and now fixed in the records: the 173 quiet cells are silent across the baseline seeds rather than never-firing, per-cell delta units are stated explicitly, and those cells carry about 1.5 of the +1550.4 spikes, so stage 1 is **amplification of an already-active subset, not recruitment**. **(iv) Every interval in this project uses `mean ± 1.96 SE`; the paired-t multiplier at n = 10 is 2.262.** Recomputed at 2.262, stage 2's marginal intervals are +84.7 [+26.72, +142.68], +62.7 [+17.46, +107.94] and +91.0 [+44.76, +137.24], all still excluding zero. **Ruling: published intervals stay at 1.96 so the records remain comparable, and any move to 2.262 moves every record together or none.** Either way these intervals describe precision conditional on this model and carry no receptor or kinetic uncertainty. **(v) Item 134's PAM census is a statement about the instantiated exposure matrix**, namely that all 331 mushroom-body `DAN` members have zero EB columns in `M`. It is not evidence about biological PAM influence and does not exclude indirect circuit effects. **(vi) Recorded against stage 3 and not yet acted on:** all 228 `ER` cells are given the identical receptor parameterisation, while experimental work reports dopamine increasing evoked responses in R2 ring neurons and decreasing them in R5. Those calcium measurements do not supply our threshold coefficients and cannot be used to fit them, but a universal ring response rule is a stronger assumption than the data supports. Until that is examined, **a methylphenidate series is sensitivity to modelled transporter inhibition and must be labelled as such, never as therapeutic rescue**, and it must report the whole chain — drug parameter, uptake, EB dopamine, threshold modulation, ring activity — with a vehicle-clamped modulation control.

138. (Coordinator record, 2026-09-21 04:45, outside consultation on item 136, no lane, no run. Recorded before stage 3 is designed against a claim item 136 does not make.) **What stage 2's survival result identifies, and what it does not.** (i) The decomposition is sound as arithmetic and needs no linearity assumption: with `B` dark, `R` driven-retain and `D` driven-disconnect, `R − B = (D − B) + (R − D)` is an identity however non-linear the model, so item 136's +1465.7 and +84.7 are two valid successive intervention contrasts. Item 136's caution against reading them as a partition into independent contributions stands, and so does the observation that a small `R − D` does not bound the interaction — fast transmission could matter much more when ring modulation is clamped. (ii) **Survival does not establish that the surviving effect acts through the ring cells' own dopamine receptors.** Driving `CX_DAN` raises dopamine in several compartments, not EB alone, and dopamine-modulated neurons elsewhere can feed `ER`. The measured claim is that about 95 percent of the excess ring spikes survive the audited 70,134-edge ablation. **"About 95 percent is ring threshold modulation" is not measured and must not be written**, which matters because it is the claim a dose-response stage would lean on. (iii) The identifying design is a two-by-two with `CX_DAN` driven in **all four** cells — fast synapses retained or disconnected, crossed with the applied ring `d_v` dynamic or clamped to its dark reference — and stage 2 measured two of them. **The dark arm is not a third cell of that design**: it removes source activation, whereas driven-disconnected-clamped keeps dopamine elevated everywhere outside the ring, and the unchanged innervation matrix and tonic fixed point do not make those equivalent. The interaction contrast is `I = (R1 − R0) − (D1 − D0)` in the obvious notation. (iv) **The clamp, when it is run, overrides the final applied `ER` `d_v` with its paired dark-reference trajectory** at the same seed, genotype, stripe and timing, leaving production, uptake, innervation, source activity and the `occ1`/`occ2` calculation live. Setting `d_v` to zero or resetting the threshold to −45 mV would strip the baseline dopamine offset as well and is a different intervention; clamping the occupancies instead reaches further upstream than the question needs and would disable anything else they feed. The result is a **threshold-modulation test, not an all-dopamine test**, and any other dopamine-dependent `ER` parameter stays live and outside its scope. (v) **An interval containing zero will not establish additivity**, so an interaction contrast must be reported with the smallest effect the design could resolve, and neither number may become a pass line (item 121). (vi) Stage 2b, lane t-0037, runs the two missing cells under the same audited 70,134-edge mask, and also records the dark arm's non-`CX_DAN` `DAN` spike count that item 136 left unmeasured.

139. (Coordinator record, 2026-09-21 07:10, r37 merged, lane t-0037, reviewer t-0038, `docs/ring-dopamine-stage2b.md`, `validation/records/p2/ring-dopamine-stage2b.json`, `scripts/ring_dopamine_stage2b.py`.) Stage 2b closes the two-by-two item 138 specified and **corrects item 136's attribution**. Five paired arms, ten seeds, 20 s, 1,000 brain-seconds, wild type, 228 traced `ER`, the TuBu stripe on throughout and `CX_DAN` driven at 50 Hz in all four intervention cells. The clamp replaces the final applied `d_v` on the traced `ER` cells with the constant dark reference +0.256302521 mV, recomputed by review from `receptor_effect` at `da_c = DA_ref` (`r1 = 1.0`, `r2 = 0.5`, `occ1 = 0.0196078431372549`, `occ2 = 0.2857142857142857`), leaving the pool, source term, innervation, occupancies and input gain live; it is neither zero nor a reset to the base −45 mV. Review verified the audit is not vacuous — it compares two neuromods at the same pool value rather than reading back its own write — that `compose` never writes through the returned vectors so the subclass's copy is behaviour-neutral, and that the clamped threshold survives a pool step. The `dark`, `driven-retain` and `driven-disconnect` arms reproduce stage 2 with a maximum absolute per-seed difference of exactly 0, as fresh runs under this round's plan. **Ruling: the surviving disconnect effect is not mostly ring threshold modulation, and no stage may present it as such.** Of stage 1's +1550.4 ring spikes per seed, +561.3 [+514.84, +607.76] — 0.3619 [0.3335, 0.3904], the mean of the ten per-seed ratios, against 0.362036 for the ratio of paired means — is removed by clamping `d_v` with the fast synapses retained, and +551.2 [+516.19, +586.21], 0.3759 [0.3542, 0.3977], with them disconnected. The remaining +989.1 [+940.95, +1037.25] persists with the ring threshold pinned; the ring's own input gain is live and unclamped at ×1.1256 (`ER` gain 1.0840 driven against 0.9630 dark), and indirect dopamine effects elsewhere are equally consistent. **That disjunction is not resolved by this design and must not be resolved in prose.** The interaction `I = (R1 − R0) − (D1 − D0)` is +10.1 spikes [−47.37, +67.57], which includes zero: **no detected interaction, which is not additivity**. The smallest effect resolvable from the design's own standard error of 29.322 spikes is 57.47 at 1.96 SE and 66.33 at the paired-t 2.262. Per cell the interaction is 34 positive, 27 negative and 167 zero, so cancellation is worth examining and the signs alone establish nothing cellwise. **Item 136's open control-mismatch count is measured:** in the `dark` arm the 331 non-`CX_DAN` `DAN` cells carry 5,308 spikes per seed (5,272 to 5,335, 0.891 Hz) while `CX_DAN` carries 0 to 1, so the 70,134-edge ablation does remove an active dark input. Review established those edges are net excitatory in the composed weights (all 62,215 raw signs excitatory; the curated scale makes 1,313 inhibitory; net +26,915.625 mV, and +105.05 mV for the 213 edges onto a traced `ER`), which supports item 136's direction **anatomically only** — see item 140, which records why that is not sufficient.

140. (Coordinator record, 2026-09-21 07:15, outside consultation on item 139, no lane, no run.) Four corrections to how stage 2b's result may be read, recorded before stage 2c is designed against the wrong one. **(i) "A third runs through the threshold term" assigns a share that the design cannot assign, and the wording is replaced.** The defensible statement is: *clamping the applied `ER` threshold term eliminates about 36 percent of the retained arm's excess while the input gain and network feedback remain live.* Interaction makes a mechanistic share dependent on the intervention and the decomposition chosen, so an eliminated fraction is not an anatomical partition and no stage may write it as one. **(ii) The possibility item 139 collapses is joint dependence, not merely local against indirect.** If a combined clamp removed nearly all the excess, `ER`-local modulation would be *required* for that aggregate excess under these conditions; it would not establish exclusive local generation or sufficiency, because increased upstream input can produce extra ring spikes only when the ring gain is elevated, and recurrent feedback and cancellation between populations give further reasons an eliminated aggregate is not a unique partition. Conversely, a large combined-clamp residual would establish an effect independent of the clamped `ER` terms and **not automatically an indirect dopamine effect** — with the fast synapses retained, ordinary `CX_DAN` transmission is still a candidate. **(iii) Item 139's anatomical sign check is necessary and not sufficient, so item 136's "conservative" is downgraded to unestablished.** Signed composed weights alone cannot settle whether `D1 − B` is conservative, because event rates, recipients and network feedback also decide the net effect of removing an input that is active in the dark. The disconnected arm's fraction-of-effect currently uses a denominator mixing source activation with the removal of an active baseline input; the correct reference is a **matched dark-disconnected arm `BD`**, giving `D1 − BD`. Until that arm exists, only the retained-network comparisons are free of this problem, and the disconnected fraction is reported with the mixed denominator named. **(iv) The resolution figure in item 139 is a confidence-interval half-width, not a powered minimum detectable effect**, and must be written that way. It does not guarantee detection of every true interaction above 66 spikes; it is uncertainty in an estimated mean under its own assumptions, computed from ten paired interaction contrasts and not from 228 cells as independent replicates. In proportion it is about 12 percent of the 561.3-spike threshold-clamp effect and about 4.3 percent of the 1,550.4-spike total excess, so it constrains large interactions relative to the total far more strongly than it constrains interaction comparable to the 84.7-spike retain-minus-disconnect contrast — which it still permits. It concerns net population-total interaction at this intervention level and time window, for fast-edge ablation crossed with threshold modulation only, and says nothing about threshold against gain, local modulation against upstream change, other dopamine exposures, or biological parameter uncertainty. **(v) Two smaller points carried forward.** The dark threshold reference is constant to 1.44e-4 mV, not mathematically exact, and records must state the approximation rather than promote it to equality. And whatever any clamp establishes, it supports a model-internal transporter-inhibition sensitivity study only: it establishes neither the biological validity of the receptor parameters (item 137 (vi)) nor stripe-specific enhancement, since TuBu stimulation is present throughout and no stage has yet run a stripe-off condition.

141. (Coordinator record, 2026-09-21 09:05, r38 merged, lane t-0039, reviewer t-0040, `docs/ring-dopamine-stage2c.md`, `validation/records/p2/ring-dopamine-stage2c.json`, `scripts/ring_dopamine_stage2c.py`.) Stage 2c closes the isolation sequence. Five paired arms, ten seeds, 20 s, 1,000 brain-seconds, wild type, 228 traced `ER`, TuBu stripe on throughout: `dark`, `dark-disconnect`, `driven-retain`, `driven-retain-clamped` and `driven-retain-both-clamped`. **The application-site census, verified independently by review against the merged code, is the finding the rest rests on:** `receptor_effect` is the only path from a compartment pool to per-cell quantities and returns exactly `d_v`, `gain`, `occ1` and `occ2`; `Neuromod.compose` applies only `d_v` as the spike threshold and `gain` as a postsynaptic input multiplier, and records the occupancies without applying them; the engine's only dopamine-dependent per-neuron write points are `set_threshold` and `set_gain`; no dopamine term reaches `tau`, `v_rst`, the refractory period, the background or any outgoing weight; and `rq` (Dop1R2) is read only by `registry/derived.py::da_exposed` and the `ScaleReceptor` `Dq` manipulation, neither used by wild type, never by `receptor_effect` or `compose`. **Two sites, so a clamp on both is a complete `ER`-local clamp, and there is no modulation of `ER` output.** Clamp constants recomputed by review from the code at `da_c = DA_ref`: `d_v` +0.25630252100840334 mV and gain 0.9630252086147875 (1.5e-9 from the float64 closed form because the receptor arrays are float32; the code's value is the recorded one). **Measured, paired, spikes per seed:** `R1 − B` +1550.4 [+1514.96, +1585.84]; `R1 − R0` +561.3 [+514.84, +607.76]; `R0 − Rb` +905.9 [+868.79, +943.01]; `R1 − Rb` +1467.2 [+1426.45, +1507.95]; `Rb − B` +83.2 [+41.75, +124.65]; all exclude zero. Combined fraction 0.9469219961 [0.920918, 0.972926] as the mean of per-seed ratios, against 0.9463364293 as the ratio of paired means, both named. **Ruling: clamping the applied `ER` threshold term and input gain together eliminates about 95 percent of the retained arm's excess while network feedback remains live, so `ER`-local modulation is required for that aggregate excess under these conditions — not exclusive generation and not sufficiency.** `R0 − Rb` is the additional effect of removing gain modulation with the threshold already clamped, is not an independent gain share, and no gain-only arm was run. **The matched dark-disconnected reference:** `BD − B` = +37.7 [−5.89, +81.29], **including zero**, with `D1 − B = (D1 − BD) + (BD − B)` = 1428.0 + 37.7 = 1465.7 holding seed by seed. The point estimate is positive — removing the `DAN` input *raises* dark firing, opposite to item 136's assumed direction — but the interval includes zero, so **item 136's "conservative" is withdrawn and stays withdrawn: unresolved, neither confirmed nor reversed, and a point estimate is not a direction.** Two things review established that the lane had not. The near-equality of the +83.2 residual and stage 2's +84.7 fast route is a **coincidence at this resolution**: the paired difference `(R1 − D1) − (Rb − B)` is +1.5 [−66.60, +69.60], including zero, with correlation −0.095, and neither may be written as identifying the other. And the ablation's raising of non-`CX_DAN` `DAN` firing (0.8908 to 0.9374 Hz, +0.04661 Hz [+0.04191, +0.05131]) is **not** net-inhibitory direct recurrence: the removed edges onto those 331 cells are net excitatory in the composed weights (+579.43 mV over 1,513 edges, 1,508 `mod` and 5 `GABA`), so the direct sign points the other way and the rise is polysynaptic through the ablation's other targets. That is item 140 (iii) made concrete.

142. (Coordinator record, 2026-09-21 09:15, outside consultation on item 141, no lane, no run. **This item closes the isolation sequence and sets the contract for stage 3.**) **(i) Three corrections to item 141's reading.** First, a wording error of mine that propagated: the two `ER`-local sites are not both received-input modulation. `d_v` changes the **spike threshold**; `gain` scales **received synaptic events**. They are both `ER`-local and both on the input side of the cell, and that is all that may be said. Second, and materially: under `g += w * gain_i_post` a positive gain increase scales **negative as well as positive weights** wherever the rule applies, so a gain change is **not automatically an increase in net excitation** and must never be narrated as an excitatory mechanism without signed evidence. Stage 3 keeps separate signed input accounting. Third, `Rb − B` = +83.2 is [+35.4, +131.0] under the paired-t multiplier 2.262 and so is **not compatible with zero**: "nearly all eliminated" is supported, "entirely `ER`-local" is not, and about 5.4 percent of the excess persists under the joint clamp. **(ii) A better contrast than the one item 141 chased.** With the matched baseline, the difference between the two stimulation-induced excesses is `(R1 − B) − (D1 − BD)` = 1550.4 − 1428.0 = **122.4 spikes per seed**, equivalently 84.7 + 37.7. The +84.7 remains a valid retain-minus-disconnect contrast under stimulation but it is not the baseline-adjusted effect of the ablation on the stimulation response. Neither contrast uniquely identifies ordinary synaptic transmission, because the ablation changes network activity and chemical exposure together, and **even exact seedwise agreement would establish numerical agreement, not pathway identity**. No further compute is to be spent chasing it. **(iii) The isolation stops here.** No gain-only arm, no complete explanation of the residual and no further factorial is needed before a bounded transporter-inhibition study. What stage 2 established is stronger than the earlier chemical checks: changing the implemented `ER`-local modulation changes neuronal output substantially with network feedback live. But that 95 percent belongs to `CX_DAN` activation against its unstimulated reference, and **does not transfer to transporter inhibition against vehicle while `CX_DAN` is already activated** — stage 3 asks a different question at a different operating point, and carries its own clamp control rather than inheriting stage 2's. **(iv) The minimum stage 3 that is worth running.** No receptor refit: the parameterisation is frozen and is not to be "corrected" until a drug curve looks plausible. The question is whether changing modelled uptake produces a measurable neuronal consequence beyond the chemical and receptor changes the equations already prescribe. Vehicle plus **two separated transporter-inhibition levels, chosen from inexpensive kinetic and receptor calculations and never from `ER` spike outcomes**, with the exact altered uptake parameter and its mapping reported; absent an independently justified concentration-to-inhibition mapping, the primary axis is **fractional transporter inhibition, not a methylphenidate dose**. `CX_DAN` drive, TuBu drive, the fast-synapse mask, initial conditions and external event realisations all matched; the comparator is **driven vehicle, not the dark reference**; actual source firing recorded, since fixing external drive does not fix emitted spikes. Report the whole chain — intervention, uptake flux, EB dopamine over time, applied `ER` threshold and gain, `ER` spikes — with the analysis window declared beforehand and the **transient shown rather than a 20-second mean treated as equilibrium or as placing a trial on one receptor branch**. Primary endpoint is the paired total `ER` spike change, with absolute counts and per-cell or subtype changes beside it, so a flat result can be told apart into insufficient dopamine separation, near-saturated modulation terms, or little neuronal response despite appreciable parameter change. **If the cheap calculations show all proposed interventions produce virtually identical applied `ER` terms, that saturation is reported and the large neural series is not bought** — and `CX_DAN` drive is not quietly lowered afterwards to manufacture a slope. **(v) Two controls stage 3 must carry.** One drug-specific clamp at a preselected active inhibition level, replaying **the paired driven-vehicle trajectories** of both applied `ER` terms — **not the dark constants**, which would remove the existing `CX_DAN`-driven modulation along with the drug effect and answer the wrong question — with vehicle replay verified to reproduce vehicle behaviour and chemistry, occupancies and non-`ER` modulation left live. And a vehicle-against-drug specificity check in the transporter-disabled model, whose purpose is to detect unintended drug effects in the implementation and **not** to count the encoded absence of a target as independent biological validation. **(vi) The limits stage 3 publishes with its result.** The receptor equations, the uniform assignment across all 228 `ER` cells, the clipping rules, and that `rq` is census-only. Experimental work reporting opposite dopamine modulation of evoked calcium responses in R2 and R5 ring neurons supports **retaining a biological-validity warning, not refitting threshold coefficients from those measurements**. With TuBu stimulation present throughout, the outcome is **drug-dependent ring activity under fixed stimulation** — not improved visual coding, not rescue, and not selection. A stripe-off comparison becomes necessary only if the claim is broadened to stimulus-specific modulation. What makes stage 3 worth running is locating the neural sensitivity or its absence, not obtaining a smooth curve.

143. (Coordinator record, 2026-09-21 18:15, r39 merged, lane t-0041, reviewer t-0043 carrying forward the unbound hand-started review t-0042, `docs/ring-dopamine-stage3.md`, `validation/records/p2/ring-dopamine-stage3.json`, `scripts/ring_dopamine_stage3.py`.) Stage 3 of the ring-neuron dopamine experiment, run under item 142's contract: a **model-internal fractional-transporter-inhibition sensitivity study at the driven operating point, not a methylphenidate dose study**. Input is injected at TuBu, downstream of a visual pathway that does not conduct; the fly does not see, and the outcome is drug-dependent ring activity under fixed stimulation. **Part A, closed form, no engine run.** The altered parameter is `da.Vmax` (0.11 µM/s) through `ScaleDat` → `dat_geno` → `_kinetics`, so fractional inhibition `i` is `ScaleDat factor = 1 − i`. Across the whole range the window-mean applied `ER` terms move 0.0238 mV in `d_v` and 0.00482 in gain at the nominal drive, about 6 and 4 percent of stage 2c's clamp range: the receptor terms are near-saturated at this operating point, which is a property of the equations and not a finding about flies. The levels 0.2 and 0.8 were chosen by a rule on applied-term separation that is in executed-runner commit `8b73fbe`, before any neural result; the expanded "near-saturated but not virtually identical" judgement first appears in result commit `254a38d`, drafted after launch and before summarization, and is not claimed to predate launch. Part B was still informative because `EB` saturation does not exclude an indirect effect: transporter inhibition acts outside `EB`, so stopping at part A would have been an allocation decision, not a demonstrated neural null. **Part B:** seven paired arms, wild type, ten seeds, 20 s, 1,400 brain-seconds on the box, 228 traced `ER`, TuBu stripe on and `CX_DAN` driven at 50 Hz in every arm, comparator **driven vehicle**, analysis window the 18 s after the 2 s transition, declared beforehand. The chain: realised window-mean uptake flux 0.08007 µM/s at vehicle, 0.06458 low, 0.01653 high; EB window mean 3.4786, 3.5846 and 3.9291 µM (4.0281 transporter-disabled); `inhibit-high − vehicle` applied `d_v` −0.02652 mV [−0.03204, −0.02101] and gain +0.00538 [+0.00426, +0.00651]; the trajectory is still climbing at 20 s, and the transient is shown in the record, not averaged into an equilibrium. **Measured, spikes per seed.** `inhibit-low − vehicle` −4.6 [−49.69, +40.49]: no detected difference. `inhibit-high − vehicle` +64.8 [+13.41, +116.19], t9 2.47, nominal p 0.036, **Holm-adjusted p 0.071 across the two inhibition-versus-vehicle tests: a small increase with nominal evidence, not a multiplicity-controlled effect**, about 1.1 percent of vehicle firing, 45 cells up against 17 down, eight of ten seeds positive, and +39.125 with the two largest seeds dropped (the +35.8 carried in the lane's record and in the review brief was an arithmetic error). `inhibit-high − inhibit-low` +69.4 [+27.19, +111.61]. `inhibit-high` against the transporter-disabled model +2.1, paired-t [−57.9, +62.1]: no detected difference, whose interval allows a difference nearly as large as the whole effect, so it establishes neither a plateau nor a reproduction of knockout. **The clearest result is the drug clamp.** Replaying the paired driven-vehicle trajectories of both applied `ER` terms, one value per native 10 ms chunk with no offset, while EB stays elevated (+0.4562 µM [+0.3938, +0.5186] over vehicle), gives `inhibit-high − inhibit-high-clamped` +93.4, paired-t [+40.2, +146.6], p 0.0033, and `inhibit-high-clamped − vehicle` −28.6, paired-t [−85.6, +28.4]. **Ruling: pinning both applied `ER` terms to the paired driven-vehicle trajectory removes the detected effect, and nothing detectable remains. The clamp cannot separate the threshold term from gain; 64.8 = 93.4 + (−28.6) is an identity and licenses no mediated share; the residual is unresolved, not zero.** Controls: the vehicle replay reproduces vehicle spike for spike and chunk for chunk; the drug applied in the transporter-disabled model changes nothing, 0.0 seed for seed; the transporter-disabled arm reproduces stage 2's +62.7. These are implementation checks and reproducibility under reused conditions, not biological validation. **A reported quantity changed after the run, and review caught it.** The raw field `gain_weighted_signed_input_mV` sums `w·gain` once per incoming edge per chunk without presynaptic event counts, so it is an edge inventory, not delivered input, and gave −230,526.85 high and −51,606.71 low. The event-weighted `signed_input_event_mV` gives −10,097 [−18,314, −1,881] high and +1,245 [−4,543, +7,033] low. Both stay in the record under distinct names, the first under `superseded_edge_inventory`. Only the event-weighted quantity supports a claim about delivered input; its high-level decrease sits almost entirely in cells silent at vehicle (−10,530 of it); and **why spikes rise while event-weighted signed input falls is unresolved**, so no arm may be narrated as an excitatory gain effect. **Provenance:** the raw `identity.runner_sha256` is stage 2c's hash because the probe called stage 2c's `identity()`; the executed runner is `c2bb16eb…` at `8b73fbe`, the raw files are untouched, the fix is confined to stage 3, and `run_seed` is AST-identical between execution and merge. The box was unreachable for about two hours through a Tailscale outage; there was no reboot and no memory event, and the run completed unaffected. **Limits published with the result:** the receptor equations, their uniform assignment to all 228 `ER` cells, the clipping rules, `rq` census-only, and the R2/R5 biological-validity warning of item 137 (vi); two levels establish no EC50, optimal dose or monotonicity; fractional parameter inhibition is not fractional flux reduction; no clamp was run at the low level. **Stage 4 has ground to stand on only as a separate stimulus-specific experiment**: stage 3 establishes bounded neuronal sensitivity under fixed artificial TuBu input and leaves the selectivity question untested.

144. (Coordinator record, 2026-09-21 18:20, Rolf's answer to a-11 on 2026-09-21, no lane, no run.) **The full open-loop P-screen is not run.** Rolf chose to skip it. The measured basis is the power pilot (r33, main 655f38b, `validation/records/p2/pscreen-power.json`): the section 3.6 open-loop probe, wild type and `fumin`, vehicle arm only, ten seeds, 1,000 brain-seconds, 2 h 38 min on the box. Wild-type `steer_gain` 0.003934 [−0.003164, +0.011389] and paired `fumin` minus wild type 0.003883 [−0.004735, +0.012050] both include zero, and both `distractor_capture_hz` intervals and their paired difference include zero: no detected steering gain and no detected genotype difference. `fumin`'s own `steer_gain` interval excludes zero at a lower bound of 0.0014732; that is one of six intervals, which is what chance produces, and the record's `reading_note` says so. **Why the full screen was not worth running:** 28 arms at this resolution would take about four days on the box, and its readout sits downstream of item 131's measured steering null, where TuBu input reaches the ring but the reached steering populations stay silent. A screen whose vehicle endpoint cannot be told apart from zero would fill the drug table with intervals including zero rather than answer a question, and the compute goes to the ring-neuron dopamine stages instead. **Consequence for what Phase 2 ships:** 4.4r to 4.7r, 4.9 and 4.10, the entries the P-screen supplies as recorded predictions (section 4.4), and the 4.11 reader that takes the P-screen's vehicle arms, are not produced. They are to be marked not run with this item as the reason, never filled from the pilot, and the pilot stays recorded as the measured open-loop result.

145. (Coordinator record, 2026-09-21 18:40, outside consultation on item 143 and the stage 4 design, no lane, no run. **This item sets the stage 4 contract.**) **(i) Corrections to item 143's reading.** "Removes the detected effect" leans on a high-versus-vehicle contrast that is nominal only (p 0.036) and does not survive the Holm adjustment item 143 itself states (0.071). The clamp statement carries the explicit contrasts: the joint clamp reduces the high-inhibition arm by 93.4 spikes per seed [+40.2, +146.6], and the residual against vehicle is unresolved. "Nothing detectable remains" describes that residual interval and is not evidence of mechanism; comparing which intervals include zero is not the mechanistic evidence, the direct clamp contrast is. The event-weighted signed-input result supports a descriptive aggregation reading — the negative change sits in cells silent at vehicle while cells active at vehicle receive a small positive change, so the population total is a poor guide to the firing subset — and establishes nothing about which change caused the extra spikes. AST identity of `run_seed` does not establish identity of imported code, initialisation, configuration or analysis; those are preserved beside the corrected runner hash as a provenance requirement, not a reason for another run. Item 144's skip is an allocation decision and adds no biological null. **(ii) Stage 4 measures stimulus selectivity, not stimulus selection, and establishes nothing about attention whichever way it comes out.** Moving one stripe asks whether ring responses distinguish its position. Experiments on attention-like processing in flies present competing stimuli together, or manipulate a selection state independently, and measure differential representation or suppression; this design has neither. Sharper tuning or better decoding can occur without selection, and a rate change alone establishes neither arousal nor gain. Stage 4 is therefore a **position-coding** experiment, and `docs/ring-dopamine-design.md`'s "the only stage that earns the word attention" is withdrawn: attention stays the motivation, and no stage 4 result may carry the word. A competition design is a separate question, decided after stage 4 shows whether the ring carries a position code at all. **(iii) Part A, no neural outcome.** Compare the complete cell-resolved injection patterns across azimuths — which TuBu cells, their relative rates, amplitudes and timing — not only which cells receive nonzero drive, since the same cells can encode position through relative drive; and report where the azimuth-to-TuBu assignment comes from, because an imposed geometric mapping means the experiment decodes injected position labels, not validated visual coordinates. Stop only if every azimuth produces an identical input distribution across the instantiated stimulus interface (**encoder collapse**, a stimulus-interface limitation, not a dopamine null); identical direct TuBu-to-`ER` projections alone support only a narrower conclusion, since different TuBu activation can reach `ER` by other paths. Match total injected drive across positions by a rule fixed from the encoder. Choose four azimuths from the encoder and anatomy only. **(iv) Part B design.** Stripe off plus four azimuths, crossed with `CX_DAN` dark, `CX_DAN` driven at 50 Hz, and `CX_DAN` driven with both applied `ER` terms replayed from the paired `CX_DAN`-dark trajectory **for the same stimulus condition**, the clamped stripe-off arm included: fifteen arms, ten seeds, 20 s, about 3,000 brain-seconds. The intervention is named **`CX_DAN` activation**, which changes dopamine and fast transmission together; stage 2c's 95 percent clamp elimination was measured at 45° with the stripe on and does not transfer to other positions, to stripe off, or to a shape endpoint. Actual TuBu spike patterns are recorded per arm as the input-side positive control, and EB dopamine and the applied `ER` terms are recorded over the window; the primary result is an 18-second, transient-inclusive spike-count representation, not an equilibrium. **(v) One primary endpoint, frozen before launch.** A seed-held-out comparison of the per-cell affine model `μ_driven(θ) = a_i·μ_dark(θ) + b_i`, `a_i ≥ 0`, against condition-specific tuning, fitted on training seeds and scored on held-out seeds, with noise in both conditions accounted for rather than treating dark means as exact. All 228 cells enter; no cell is selected as a stripe responder from the same observations (the 61 active cells were identified at one position and are not a census of position-responsive cells). Stripe responses stay signed; raw on and off counts are fitted jointly rather than treating subtracted counts as counts; an intercept means an azimuth-independent evoked component. A rejected affine null means **a change not explained by per-cell additive and multiplicative transformations of mean firing** — not sharpening, not selection, and not a mechanism beyond the implemented receptor equations. With four positions it is coarse position discrimination or a tuning-pattern change, since four samples cannot separate narrowing from a shifted or unsampled peak. The joint clamp is the prespecified mechanistic follow-up and asks only whether a measured change depends on the implemented `ER`-local coupling with feedback live. Decoding (a fixed nearest-centroid or regularised linear classifier, whole seeds held out, scaling inside the folds) and cellwise or subtype indices are secondary, and decoding is compared against a spike-count-matched or affine-rate null, because more spikes alone improve a classifier. Uncertainty comes from seed-block resampling with the whole analysis refitted; the ten seed blocks are the independent replicates, not 228 cells or 40 trials. **(vi) The pipeline is validated and committed before launch.** On synthetic data with realistic count variability — affine-only modulation including sparse cells and changed variability, and known non-affine changes of stated sizes — the frozen pipeline must not report shape changes it was not given. The sizes it resolves under those planning assumptions are planning figures, not power guarantees, and never pass lines (item 121). **(vii) The outcomes, named in advance.** Encoder collapse; **transmission collapse** (TuBu distinguishes positions, `ER` does not, so there is no ring tuning to change); a detected non-affine change; **unresolved**, when the intervals stay broad; and the strongest flat outcome, which needs distinct injected patterns, distinguishable TuBu responses, a reproducible `ER` position code, clear activation-related rate modulation, and no non-affine change beyond a bound fixed before the run from stated scientific relevance, never from a number this model produced. Without such a bound a nonsignificant result is unresolved, not preserved shape. Conclusions apply to the declared spike-count window only. The uniform `ER` receptor assignment stays unvalidated, and item 137 (vi)'s R2/R5 calcium results cannot calibrate the threshold and gain coefficients. Genotype and transporter inhibition on position coding follow only if resources allow, as prioritisation, not as proof that a flat large contrast forbids a drug effect at another operating point. An optional benchmark, replaying recorded incoming events into isolated `ER` model cells under both modulation settings, would test whether local input-to-spike conversion suffices for any detected change.

146. (Coordinator record, 2026-09-21 19:25, outside consultation on the competition stage Rolf chose on 2026-09-21 (a-12), no lane, no run. **This item sets the stage 5 contract.** Stage 5 runs only if stage 4 shows a reproducible `ER` position code.) **(i) The anchor.** Sun et al., "Neural signatures of dynamic stimulus selection in Drosophila", *Nature Neuroscience* 20, 1104–1113 (2017): two-colour calcium imaging showed contralateral suppression of ipsilateral responses in both tuberculo-bulbar inputs and ring neurons, stronger and history-dependent in the ring neurons, captured by biphasic temporal filters. That makes this pathway the appropriate one, but it does not make every one of the 228 traced `ER` cells a counterpart of the recorded population: subtype and hemisphere correspondence are checked, not assumed. Direct TuBu injection bypasses part of the transformation the experiment studied, so actual TuBu responses are recorded beside `ER` and no suppression is attributed to `ER` without them. **(ii) Three claims kept apart.** Subadditivity is not competition, and competition is not selection. The per-cell joint-stimulus interaction `J_i = μ_i(A+B) − μ_i(A) − μ_i(B) + μ_i(off)` is named as that and nothing more: a cell can be suppressed by adding B with `J_i = 0`, and a strongly negative `J_i` can be symmetric suppression that selects neither. Differential representation needs population evidence for A and B separately: pair responses are projected onto single-stimulus templates calibrated from independent data, with an unexplained residual kept, and the coefficients are **not** constrained to sum to one, which would manufacture a trade-off. The templates must be distinguishable rather than nearly collinear. A pair pattern poorly fitted by either template is reported as a mixture-specific pattern, not as suppression of whichever fits worse, and a classifier calling A+B "A" does not establish that B disappeared. **(iii) The design: one pair, with controlled history.** A static simultaneous pair cannot separate a persistent input or anatomical preference from history-dependent selection. Eight protocols, each a prefix, the same fixed gap, then a test: blank prefix before off, A, B and A+B; A prefix before off and A+B; B prefix before off and A+B. The final injected pair is identical across histories, with matched external event realisations; `CX_DAN` stimulation follows the same absolute schedule; neuronal state is **not** reset between prefix and test. Crossed with `CX_DAN` dark, `CX_DAN` driven at 50 Hz (named **`CX_DAN` activation**, since fast transmission stays live), and `CX_DAN` driven with both applied `ER` terms replayed from the paired dark trajectory **for the entire stimulus history**, prefix, gap and test: 24 arms, ten **fresh** seeds, about 4,800 brain-seconds. The response window starts when the final pair appears and is declared before the run; time-resolved responses are retained and sustained activity is secondary, because long averages can hide transient suppression or alternating dominance. **(iv) Choosing the pair.** From stage 4's dark data only: both members must individually produce reliable, distinguishable `ER` patterns at comparable injected drive, in opposite hemifields where the instantiated representation supports it, to correspond to the experiment. Not the pair with the largest decoding distance, which can pair a strong response with an absent one and manufacture a winner. Stage 5's fresh seeds keep the noise that selected the pair from also validating it, and template fitting and feature selection stay independent of the tested outcomes. A second pair is added only to test a stated generalisation, never as a second chance at significance. **(v) One frozen primary contrast.** `H = [μ(A prefix, A+B) − μ(A prefix, off)] − [μ(B prefix, A+B) − μ(B prefix, off)]`, projected onto the independently calibrated A-versus-B readout. The driven result is compared with the affine prediction from dark: the per-cell affine transform is fitted on single-stimulus controls, excluding pair outcomes, using stage 4's tuning data with its uncertainty carried forward, and under that transform `J_driven = a_i·J_dark`. The joint clamp is the mechanistic follow-up and remains an intervention with network feedback live, not proof that `ER` alone generates anything. Unsubtracted traces are kept, since subtraction removes additive carry-over that is itself part of the history effect. A nonzero `H` can arise because history changes responses to the individual components; isolating competition-specific memory needs history-matched single-stimulus arms, which are not authorised before this bounded result exists. **(vi) Audits before interpretation.** That A+B delivers what is presumed, from cell-resolved injected rates and actual TuBu spikes, since shared recipients, rate caps or normalisation can prevent a sum. Which `ER`→`ER` connections exist in the instantiated model, their composed signs, and whether their presynaptic cells fire: "`ER` is GABAergic" does not establish effective mutual inhibition between the two stimulus channels, and the connectomic literature offers winner-take-all or gain normalisation for that motif without settling which. No `ER`-inhibition ablation now. **(vii) The pipeline is validated and committed before launch** on synthetic responses with symmetric saturation, fixed spatial bias, affine modulation and known asymmetric suppression, and must not report asymmetry or history effects it was not given. Ten seeds are a bounded pilot; the seed is the replication unit, not cells or time bins. **(viii) The outcomes, named in advance.** Prerequisite failure: one member is not represented alone, or the encoder suppresses an input before it reaches the circuit, a localised limitation and not a competition null. No additional preferential representation: the pair is adequately described by the declared mixture model with no asymmetry beyond a bound fixed before the run, in interpretable units of the calibrated response, never from the observed interval width or from a number this model produced (item 121). Competition without detectable modulation: a reproducible asymmetric or history-dependent representation exists, and `CX_DAN` activation does not change the primary contrast beyond that bound. A detected modulation. Unresolved. Zero average balance is not balance: A can dominate some seeds or intervals and B others, so per-seed and time-resolved distributions are kept, and an inability to tell balanced representation from alternating dominance is reported as a limitation. **(ix) The ceiling on the claim.** The defensible target is **history-dependent differential representation under TuBu injection: a candidate neural signature relevant to stimulus selection, not a demonstration of fly attention**. Finding a nontrivial consequence of fixed wiring is legitimate model science; calling it a computation the real fly performs needs independent validation. If the eye front-end check (lane t-0048) finds the trained flyvis eye feasible for the ring path and it is integrated before stage 5 runs, stage 5 takes seen stimuli and the framing becomes "the fly sees through a trained eye model", with that model's limits; otherwise input stays at TuBu, downstream of a visual pathway that does not conduct, and the fly does not see.

147. (Coordinator record, 2026-09-21 19:50, Rolf's ruling given 2026-09-20 and repeated 2026-09-21, r40 merged (main 7275378), lane t-0044, reviewer t-0047, repair reviewer t-0050.) **The Mac-only results rule is deleted.** A result's validity no longer depends on the platform it ran on. `platform.canonical` is gone from `data/params-v0.2.yaml`; binding no longer rejects or stales an entry for platform; validation no longer demotes a class for platform; tier-3 reference checks, WP19 startup, rest-screen reference matching and behaviour-stage aggregation run on either platform; the dashboard no longer blocks live view for platform alone. Platform stays in every identity block and record as **provenance only**. The clauses that stated the rule were removed from this document, `docs/SPEC.md` was unchanged, and no record or `validation/status.json` byte changed. Numbered items above that state or apply the rule are history, superseded by this item. The rule had been reported deleted on 2026-09-20 when it was not; ask a-6 was withdrawn, and the question is closed: it is not to be reopened as an ask. **Records held back only by platform:** `validation/records/p2/wp21-neural.json` (class `development`, assigned because the neural wave ran on the box; it supplies 3.2r to 3.6r and 3.10r), and the two byte-equivalent K2r records `validation/records/p2/entry-3.1r.json` and `wp19-entry-3.1r-c8e958eb36bbaa7b.json` (`identity.platform = linux-aarch64`). Under this ruling they count. Their stored class stands until a lane re-classes them with this item as the reason; no record is edited by hand.

148. (Coordinator record, 2026-09-21 20:45, Rolf's answer to a-13, r42 merged (main fb62410), lane t-0048, reviewer t-0053, `docs/eye-frontend-feasibility.md`, `validation/records/p2/eye-frontend-feasibility.json`, `scripts/eye_feasibility/`.) **Can a trained eye feed this brain? The motion seam is feasible to attempt; it is not built or tested. The ring seam is not justified yet.** flyvis 1.2.0 (TuragaLab, Lappalainen et al. 2024, pretrained `flow/0000/000`) runs on this Mac in a separate environment, about 6 s of wall time per 20 s stimulus at 100 frames/s and 2.21 GiB peak; neither flyvis nor PyTorch entered the project's dependencies. The pinned v783 annotation table in this repository has no retinal column field, so a direct type-and-column join matched **0 of flyvis's 45,669 cells**. That is a limit of the local table, not of v783: Matsliah, Yu et al. 2024 (Nature 634:166-180) publish a v783 right-eye grid of 796 columns with FlyWire root assignments that include every T4a-d and T5a-d type (Codex `column_assignment.csv.gz`, OpticLobe.jl). The lane missed it; the review corrected the verdict. **Motion route:** in our substrate 12,238 T4/T5 cells feed 144 named lobula-plate tangentials, which reach bilateral DNa02 and DNae001, the four endpoints item 131 found silent under TuBu drive. That is anatomy, not function. Remaining work before any dynamic probe: pin the published table and check it against the substrate's T4/T5 roots, freeze the right-eye orientation and the flyvis 721-to-796 column transform, freeze the graded-to-spiking conversion on upstream data only (item 121), add a seam runner outside `src/`, and validate on synthetic spatial patterns. The lane's five-to-eight-day estimate assumed the table had to be derived, so there is no sound time estimate for the corrected scope. Only the right eye is covered. **Ring route:** among optic inputs to the 886 MeTu cells presynaptic to the relevant TuBu set (244 MeTu1, 100 MeTu2, 273 MeTu3, 269 MeTu4), flyvis-modelled types carry 20.28% of synapses and 14.74% of absolute composed weight; untyped optic cells, Dm2, Dm21 and several CB types carry most of the rest. A seam there needs a justified model of that missing input, or evidence that the covered subset suffices chosen without reference to the `ER` outcome, estimated at one to two weeks of model and physiology work. **Consequences:** stage 4 runs on the imposed TuBu label (item 145 (iii)), and stage 5 takes TuBu input unless a ring seam is validated first (item 146, last sentence). flyvis is a trained optic-lobe model, not a biological eye; nothing here shows visual function in the spiking brain, and in every result so far the fly does not see. Whether to build the motion seam is Rolf's call (ask a-15).

149. (Coordinator record, 2026-09-21 23:30, Rolf's ruling, feasibility lane t-0055 at 374ff42, its review pending.) **The model moves to MaleCNS v1.0.** Rolf, 2026-09-21: "just download it i want to use that model irregardless". MaleCNS v1.0 (Berg et al. 2026, *Cell*, DOI 10.1016/j.cell.2026.08.015; HHMI Janelia, Google Research, MRC LMB/Cambridge; CC BY 4.0) is an adult male central nervous system of about 166,000 neurons: brain, both optic lobes and ventral nerve cord. It becomes a new, separately versioned substrate, `male-cns:v1.0`, and never masquerades as FlyWire `783`. **Nothing measured on FlyWire v783 transfers.** Every Phase 2 record stays as recorded, bound to `rest:379cc4cc9030cdd1`, and remains the reference for what was found on the female brain. Port order, from t-0055's plan: (1) a dataset adapter and first-class version; (2) canonical annotation, engine-order and edge schemas with source checksums and attribution; (3) a population registry after review of the audit rows, with explicit laterality and an ROI-based `CX_DAN` filter; (4) a versioned eye-assignment artifact carrying method and confidence per cell; (5) compartment targets, W/M matrices, receptor exposures and every dopamine and drive parameter rebuilt on the male graph; (6) new parameter, drive, dopamine, visual and behaviour versions and a new substrate id; (7) structural checks, resting calibration, the reflex, visual transfer, steering and behaviour re-run before anything is claimed. No parameter is fitted to a downstream outcome (item 121). What MaleCNS adds: a brain-to-nerve-cord graph that reaches leg and wing motor neurons, and optic-lobe column fields. What it does not settle, pending review: its direct column fields cover 15 of flyvis's 65 types and not T4/T5, a wiring-inferred method gives unique assignments to 11,994 of flyvis's 45,669 cells across both eyes, and R1-R6 share one identity. Stage 4 (item 145) finishes on FlyWire and is reported as a FlyWire result; no further FlyWire stage starts, and stage 5 (item 146) is redesigned on the male substrate after calibration.

150. (Coordinator record, 2026-09-22 02:40, decision d-0002 under Rolf's ruling a-16 / item 149, r45 merged (main f2cc4af), lane t-0056, reviewer t-0058, `docs/malecns-port.md`, `data/malecns-v1.0-manifest.json`, `src/flyonenomics/datasets.py`.) **Port step 1 is in, and the male brain is built by the FlyWire substrate's rules.** `male-cns:v1.0` is a distinct connectome version loaded through one dataset adapter; FlyWire 630 and 783 engine arrays hash identically before and after it. The seven MaleCNS v1.0 flat tables (24,377,419,334 bytes, CC BY 4.0) sit in the ignored cache with a committed manifest; meshes and skeletons are inventoried, not downloaded (native meshes alone 756 GB), for later figures. Kept nodes: 162,517 traced and typed of 211,577 annotation rows; every typed result-critical candidate is kept; nine traced but untyped broad-class motor rows (eight leg, one wing) are left for the population ruling. The review found two build differences from FlyWire, and **this item removes both, so that differences between the brains come from anatomy rather than from preprocessing:** (a) FlyWire keeps every globally aggregated directed pair with no weight cut (15,091,983), while step 1 cut the male graph at aggregate weight 5 (6,138,378 edges); the male graph instead keeps every pair, 25,120,209 edges on the same nodes. (b) FlyWire stores an unknown-transmitter neuron's sign on each connection row, but Shiu's predictions classify the neuron once from all its presynaptic sites (1,617 neurons, 73,881 edges), while step 1 zeroed the outgoing edges of 1,991 unknown-consensus male neurons (88,463 edges); the male graph instead signs each unknown-consensus neuron once from all its per-T-bar transmitter predictions and applies that sign to every outgoing connection, by FlyWire's per-neuron rule. Of 560,785 affected MaleCNS pairs, 89,519 change sign from the superseded per-pair interpretation; 2,022 of 2,435 output-bearing unknown-consensus neurons would otherwise have mixed signs. Tyramine is recognised as in FlyWire's curated set. The seven named transmitter polarities already agree. Nothing here is calibrated, and the fly does not see.

151. (Coordinator record, 2026-09-22 05:15, r47 merged (main 3f87110), lane t-0046, reviewer t-0063, `docs/ring-dopamine-stage4.md`, `validation/records/p2/ring-dopamine-stage4.json`, raw output `camber-runs/ring-dopamine-stage4/run-20260921T-partb-01/`.) **Stage 4 (item 145) is measured on FlyWire: `CX_DAN` activation changes the `ER` tuning pattern over the imposed positions in a way that per-cell rate scaling and offset do not explain.** Position is an imposed TuBu label assigned by ascending root ID, not seen and not validated visual coordinates; the fly does not see. Ten paired seeds ran all fifteen arms on the declared substrate `rest:379cc4cc9030cdd1` (3,000 brain-seconds). The analysis froze at Part A (`1cb0d6a`) before launch; the executed runner is exactly the committed `64e225e` file, and the reviewer recomputed every reported score from the raw seed files with the frozen code. **The one confirmatory result:** dark versus activated scores 43.4667, centred 95% whole-seed bootstrap interval [22.5803, 82.4022], lower endpoint above zero. This is a change over four coarse positions and does not say whether a peak narrowed, shifted or moved outside the sampled positions. **Joint clamp, post hoc:** the clamp arms were frozen, but the two comparisons below and their bootstrap seeds were chosen after the run. The replayed `ER` threshold and gain terms match the paired dark trajectories exactly (all 11,400 per-target window means, maximum difference 0). Dark versus activated-and-clamped scores 2.6209 [−3.0315, 7.2560], which includes zero: unresolved, no detected difference, not sameness. Activated-and-clamped versus activated scores 39.7314 [19.9364, 76.6919]. Read together, and only as post hoc, the measured change depends on the model's implemented `ER`-local threshold-and-gain coupling with feedback live; it does not separate threshold from gain and is not evidence of a biological mechanism. Every decoder is saturated at 40/40 (TuBu in all three conditions, `ER` dark and activated, the affine-rate null), so decoding separates no condition and no model. **Stage 5:** on FlyWire this meets the reproducible `ER` position-code prerequisite of items 145 and 146 (dark patterns decode 40/40 with whole seeds held out). Item 149 still stops further FlyWire stages; stage 5 is redesigned on `male-cns:v1.0` after calibration, and this female-brain result does not establish a position code there. The disk-full window on the shared box (148 logging errors) lost no result: each seed file was written whole after all fifteen arms.

152. (Coordinator record, 2026-09-22 07:45, under Rolf's ruling a-16 / item 149, r48 merged (main 1d9660b), lanes t-0060 and t-0061, reviewer t-0064, `data/populations-male-cns-v1.0.yaml`, `scripts/build_malecns_populations.py`, `validation/records/p2/malecns-populations.json`, `data/eye-assignment-male-cns-v1.0.parquet`, `scripts/malecns_eye_assignment.py`, `validation/records/p2/malecns-eye-assignment.json`, `docs/malecns-port.md`.) **Port steps 3 and 4 are in: the male brain has its own population registry and eye-column assignment, both chosen from anatomy and labels before any model outcome.** Both rebuild byte-for-byte on the box from the checksummed release tables on item 150's graph (adapter v3); neither reads connection signs. **(i) Populations.** All 142 FlyWire population names have a male row with explicit laterality, and `male-cns:v1.0` resolves only the male registry; FlyWire registry selection and engine arrays are unchanged. The `ER` trace set uses FlyWire's rule, at least one direct TuBu aggregate pair: 245 of 282 male cells (FlyWire 228 of 278); both brains drop all their ER1 cells by that rule. `CX_DAN` uses the FlyWire threshold, output onto the seven central-complex compartments (EB, PB, FB, NO, both LAL) of at least 0.2 of all output, and keeps 27 of 36 dopamine candidates (FlyWire 30 of 40). The review corrected the lane's EB-only count (4 of 36). The male rule assigns each partner synapse by its own released ROI, while FlyWire weights each partner by its compartment-targeting row, so the two filters are analogues, not identical. **There is no sugar-reflex source on the male brain yet:** 161 typed labellar gustatory cells exist, but none carries a sugar modality or receptor label, and `flywireType` is a type label, not a cell-level match. `sugar_GRN_R` stays empty rather than being filled by count or by firing, so port step 7's reflex check has no input until a source is established. Right MN9 is body 16949; 373 typed leg and 66 typed wing motor neurons are kept, and nine untyped broad-motor rows are excluded by the frozen typed-node rule. **(ii) Eye columns.** One row per kept cell, with method, confidence, ties and collisions. The review found 1,867 wiring inferences tied for the greatest-weight column that had been counted as unique; they are now unresolved. Unique type-position slots: 17,807 left, 18,999 right, 12,089 in both eyes, of 45,669. T4/T5 have no direct column labels; wiring-inferred unique coverage is 407 to 460 of 721 slots per type and eye. R1–R6 and CT1 shared identities stay unresolved. **Tests:** the full suite takes about 75 minutes single-process on the box. Seven tests fail on main's box checkout too (a macOS memory test, four dashboard tests, one Linux arm64 trace hash, one missing `uv` on the box PATH), so they are Linux-box differences, not these changes. The 149 registry tests pass. Nothing here is calibrated, and the fly does not see.

153. (Coordinator record, 2026-09-22 12:30, under Rolf's ruling a-16 / item 149, r49 merged (main a07ffe0), lane t-0066, reviewer t-0068, `data/{compartments,receptors,transmitters,dopamine,drive}-male-cns-v1.0.yaml`, `scripts/malecns_dopamine_tables.py`, `validation/records/p2/malecns-dopamine-classification.json`, `validation/records/p2/malecns-dopamine-tables.json`, `docs/malecns-port.md`.) **Port step 5 is in: the dopamine layer's compartments and tables exist for the male brain, and nothing in them is calibrated.** Before building, the lane classified all 1,445 values in the six FlyWire source tables as **anatomy** (rebuilt on the male brain by the FlyWire rule), **declared** (a literature or design constant carried with its source) or **calibrated** (chosen on the FlyWire resting brain). The classification froze at `f1f723f`, and no value changed class after any output. Every calibrated value is null in the male files: all 37 `R_c`, `alpha_c`, `S_c` and `mode` values, and the drive scales, weights, threshold, optic exemption and mechanisms. The loaders refuse the male dopamine and drive tables as uncalibrated rather than defaulting or falling back to FlyWire numbers; step 7 calibrates them. `build_registry` now builds the male brain end to end through the dataset adapter. MaleCNS's unsided `NO` goes to `NO_L` or `NO_R` by the postsynaptic cell's side, split equally when the cell has no lateral side, which is FlyWire's own target-side rule; `CX_DAN` still keeps 27 of 36. Mushroom-body DAN, MBON and Kenyon-cell memberships follow the same Aso et al. 2014 type rules. Three `MBON25-like` cells are placed by their exact released FlyWire type; eight male types stay unplaced (six two-cell DAN types, one `MBON25-like` cell and a two-cell broad `KC` type). **Measured beside FlyWire:** W 162,517 × 37 with 24,454 non-zeros (FlyWire 138,639 × 37, 29,588); M 452 non-zeros (465); 8,074 exposed cells (8,725). The male brain has more neurons but fewer exposed cells. The release has 1,113 fewer Kenyon cells than FlyWire, which is larger than the 651-cell gap; the unplaced broad `KC` type accounts for at most two exposed cells. How much of the gap each cell class explains was not measured. The male transmitter class `unknown` (4,400 cells) is a label, not a silenced edge: all 25,120,209 engine edges carry a non-zero signed weight, as item 150 requires. FlyWire's registries, matrices, receptor and drive arrays, engine arrays and transmitter map are byte-identical to before. Nothing here is calibrated, no engine ran, and the fly does not see.

154. (Coordinator record, 2026-09-22 14:30, decision d-0003, r50 merged (main 875cd35), lane t-0067, reviewer t-0070, `tests/fixtures/wp24-off-reference.json`, `src/flyonenomics/validation/level0_mech.py`, `src/flyonenomics/dashboard/app.py`, `src/flyonenomics/server/mcp_server.py`.) **The full suite passes on the Linux box, so lanes and reviewers are gated there.** The Mac cannot give a clean suite while another project's runs hold its swap above the engine-start gate; on the box, one process runs 912 passed, 30 skipped, in about 78 minutes. Seven tests had failed only on Linux. Six were environment assumptions in the tests: a macOS branch the test did not select, `node` and `uv` missing from the box's non-login PATH, and a dashboard load time that computed the validation identity twice per request. The engine-start gate itself already reads Linux `MemAvailable` and swap, so it means the same on both machines. **Test 0.15 (b)(i), switch neutrality, now has one exact reference per platform (d-0003).** On Linux arm64 the voltage trace differs from the Darwin reference by at most 2.84e-14 mV (floating-point rounding; ticks and spikes identical), so no single byte reference can serve both machines. The Linux reference was recorded the way the Darwin one was: by the recorder commit `7f070b7` running the engine from before the WP24 edit (`983541d`). The reviewer reproduced it, and it equals the current Linux trace exactly, so switch neutrality holds on Linux as it does on the Mac. The check picks the reference for the running platform and compares exact hashes; an unknown platform fails. A numerical tolerance was refused as an invented pass line (item 121). Review found one defect: the lane's dashboard cached the validation identity for the whole process, which would show stale status once code, data or records changed. It is now computed once per request, and the load criterion is unchanged. The 0.16 adaptation helper can exceed its 300 s child timeout on a cold, loaded box; it passes alone and is recorded, not changed.

155. (Rolf's ruling, 2026-09-22 16:50 UTC, under item 149, on lane t-0069's unreviewed result, branch commit `5166fc0`, `docs/malecns-rest.md`.) Rolf: "claude i have no rules we have an experiment to run". Reading: item 122's ruled configuration, applied unchanged (sensory-only background 1.0 mV, `g_gaba=1`, `g_glu=4`, `g_his=1`, `g_gaba_kc=6`, no optic exemption), is the male resting substrate for `male-cns:v1.0`, as the same configuration was for FlyWire in item 122, and the port moves to the experiment. The §2.3 rules on the male brain are recorded measures, not gates (items 110, 121, 122). **Measured by the lane, before review:** at 1.0 mV over ten seeds, R-screen F is 3.28, 3.28 and 3.07 on seeds 1, 5 and 9 and below 3 on the other seven; R-long (30 s) F is 3.09, 3.17 and 3.02 on the same seeds. No seed ignites. The ten-seed means are central 4.79 Hz (FlyWire 4.83), DAN 1.51 Hz (0.81) and KC 0.010 Hz (0.089). At 1.2 mV every seed has F below 3 (maximum 2.53), and every seed's central rate at 1.4 mV is below three times its rate at 1.0 and 1.2 mV. R-reflex is not measured: there is no male sugar source (item 152). The §2.5 dopamine chain on seeds 1 to 3 is computed and not adopted by the lane; port step 6 adopts it by FlyWire's procedure, mints the male drive file at these settings and mints a new substrate identifier with `substrate_id_for`; `rest:379cc4cc9030cdd1` names the FlyWire brain only. The review of t-0069 checks these numbers and whether seeds 1 and 5, which agree to four figures, draw distinct random streams; any correction it makes replaces the numbers here. Stage 5 (item 146) runs on this male substrate. Nothing here is a biological claim, and the fly does not see.

156. (Coordinator decision d-0009, 2026-09-22, under Rolf's restated goal (note n-0001: "i just want to see if we can replicate adhd in a fly and see what happens"; proper methodology, reproducibility, clear findings, a 3D model; no prior rules) and his delegation of the science choices ("i trust in claude you got this"). r51 merged (main ce0ff18), lane t-0073, reviewer t-0075, `docs/adhd-model-research.md`.) **The first experiment: an ADHD-relevant dopamine perturbation and an attention-relevant neural readout on the male brain.** The research, checked against 21 primary sources by the lane and independently by the reviewer, finds that flies model parts of ADHD, not the condition. The fumin dopamine-transporter mutant is the best-supported model (daily activity two to three times control, less sleep, slower adult dopamine clearance), with no attention phenotype shown. It corrects several claims in `docs/research/L2-biology.md`, including the atomoxetine direction, the candidate-gene screens and the scope of methylphenidate rescue in radish flies; the corrected record replaces L2 for this experiment. **Choices.** Change: modelled transporter loss (named `fumin`, uptake Vmax 0 in every compartment, non-transporter clearance kept). Readout: item 146's history contrast `H` on the male `ER` trace set, with the per-cell affine control as the interpretation check. Intervention: a global release reduction named synthesis-inhibitor-like, never a dose, at the fraction fixed from chemistry alone that returns fumin's resting pool to `DA_ref` (0.375 with the current male constants), applied to both genotypes. Methylphenidate is not the intervention: in this model it acts only through the transporter that fumin removes, so its null would be encoded, not found. Design: 2 × 2 (genotype × vehicle or release reduction), `CX_DAN` undriven, pools initialised at each condition's chemical steady state; stage 5a finds the male position code and fixes the pair by item 146 (iv) on seeds 101 to 110; stage 5b runs item 146's eight history protocols in all four conditions on fresh seeds 201 to 210. Two primary contrasts, paired over whole seeds with Holm: the genotype effect on `H`, and the genotype-by-intervention interaction. Lane t-0077 commits the design and the analysis, validated on synthetic data, before any run. **Claim ceiling:** a candidate neural signature relevant to stimulus selection under an ADHD-relevant dopamine perturbation in one fixed model; not ADHD, not attention, not behaviour, not a drug dose. The fly does not see.

157. (Coordinator record, 2026-09-22 20:55 UTC, under item 155, round r1 of the new round numbering (the harness reused the id; 2026-09-12's r1 brief and findings remain in git at 633ad16 and cf5868e), main 2ba4512, lane t-0076, reviewer t-0080, `data/drive-male-cns-v1.0.yaml`, `data/dopamine-male-cns-v1.0.yaml`, `scripts/malecns_substrate.py`, `validation/records/p2/malecns-substrate*.json`, `validation/records/p2/malecns-seed-check.json`, `docs/malecns-port.md`.) **Port step 6 is in: the male brain has its own resting substrate, `rest:ed9b0a469d7a6b77`.** The drive file carries item 155's configuration unchanged. The dopamine table holds the §2.5 chain computed by WP19's `rest_release_constants` from the recorded K2r rows of seeds 1 to 3, after checking the raw seed files against t-0069's hashes (8 derived, 29 source), the same procedure FlyWire used (items 123, 125). `scripts/malecns_substrate.py --regenerate` rebuilds both tables and the identifier byte-for-byte from pinned inputs. The male loaders accept the filled tables and refuse null calibrated values and incomplete bindings. FlyWire data, registries and engine arrays are unchanged. **Seeds:** the ten derived engine seeds all differ. Seeds 1 and 5 (2194859040 and 941284824) produce 5,059 and 3,595 spikes in the first 100 ms, and replaying a seed reproduces its spike train exactly, so their near-equal long-window means are not duplicate streams. **Review fix:** the lane's substrate had pinned the whole MaleCNS manifest, which the 3D model's visual rows (r52) then changed. The pin now covers only the five manifest rows that build model arrays, which renamed the substrate from the lane's `rest:5836215ca8694178` (not adopted) to `rest:ed9b0a469d7a6b77`; every number, the float32 scale hash and the one-second spike count (205,749) are unchanged. One male brain-second takes about 80 s of wall time on one box worker at 7.1 GB peak memory. `rest:379cc4cc9030cdd1` remains the FlyWire substrate only. The fly does not see.

158. (Coordinator design freeze, 2026-09-25, before outcome runs.) **Chemical knockout tour.**

**Pre-freeze facts (2026-09-25).** Seeds 501–510 are unused in earlier validation JSON records and archived seed records checked before the freeze. The sensory drive group contains 15,016 cells, of which 10,436 (69.499%) are cholinergic by consensus `top_nt`. The directly driven sensory group includes 1,394 R1–R6, 1,299 R7 and 1,329 R8 photoreceptors. The fly still does not see: rest input is injected Poisson noise, not light. A 0.2 brain-second control-only engine check ran locally and on Modal; no knockout outcome ran before this freeze.


Status: frozen on 2026-09-25, before any outcome run. Rolf gave the go; execution waits for this freeze.

Source facts: `docs/knockout-tour-scoping.md` on t-0111 (e1957e5), `docs/malecns-rest.md` (item 155).

## Question

When one chemical system is switched off, does the simulated male brain change the way a real fly brain would? This is a sanity check of the model. It isn't a new finding about flies.

## Brain and starting state

- `male-cns:v1.0`, the reviewed male rest state (item 155, `rest:ed9b0a469d7a6b77`), with no model or parameter change.
- Dark rest: background Poisson drive into the sensory group only, as in item 155. No stimulus. The fly doesn't see.
- Healthy rest has ongoing activity: central brain about 5 Hz, DAN about 1 Hz, KC about 0.01-0.09 Hz (item 155 records). So both loss and release of activity can show.
- 2 s settle, then a 10 s measurement window per seed.

## How a chemical is switched off

One mechanism for every class: disconnect every outgoing synapse of every neuron whose consensus transmitter label is that chemical (`engine.disconnect`, available today, no model change). This is the model version of blocking the chemical's receptors everywhere. It works like picrotoxin for GABA.

Dopamine: fast outputs disconnected and the dopamine modulatory layer switched off as well, so all dopamine signalling is gone.

Groups use consensus labels, not engine classes. So the histamine group includes the 1,777 T1 cells that the engine currently classes as unknown.

## Conditions (same 10 fresh seeds in every condition, paired)

| # | Switched off | Neurons | Expected in the model | Real-fly anchor |
|---|---|---:|---|---|
| 0 | nothing (control) | 0 | the item 155 rest | n/a |
| 1 | acetylcholine | 102,576 | Activity beyond the sensory neurons collapses toward silence. Most sensory neurons are cholinergic, so the background input can't get in. Sensory neurons keep firing because they're driven directly. | Nicotinic block: paralysis |
| 2 | GABA | 21,868 | Activity rises across central brain and optic lobes. Possibly runaway, synchronous firing. | Picrotoxin: seizures |
| 3 | glutamate | 29,104 | Activity rises. Glutamate inhibits in the central brain, in real flies (GluCl) and in this model. | GluCl block: disinhibition |
| 4 | histamine | 5,899 | Changes, if any, stay in the optic lobes. The fly isn't seeing. The rest drive reaches the photoreceptors (R1–R8); this row expects optic-lobe changes, with no signed direction. | Hdc/ort null: blind |
| 5 | dopamine | 392 | Small or no detected difference in whole-brain activity; any change local (mushroom body, central complex). | Hypoactivity, more sleep (slow, behavioural) |
| 6 | octopamine | 101 | Small or no detected difference. | Lethargy, flight failure (slow) |
| 7 | serotonin | 48 | Small or no detected difference. | Sleep fragmentation (slow) |
| 8 | unlabelled | 2,529 | Small. Shows how much the neurons without a clear label matter. | none |

Tyramine has no consensus neurons in this map. It is not run.

Rows 5-7 are written down now on purpose. Real modulator effects are slow and behavioural. In this model the modulators are a few hundred neurons with placeholder receptor densities and fast signed synapses. A small result there shows a limit of the model. It says nothing about flies.

Ordering prediction for whole-brain activity outside the sensory group: GABA-off and glutamate-off above control, acetylcholine-off far below, rows 4-8 near control.

## Readouts (measured facts, no pass lines)

Per seed and condition:
- mean rate for each of the 12 drive groups, and for the whole brain outside the sensory group;
- the rate distribution: fraction of silent neurons (no spike in 10 s), median, 99th percentile, maximum;
- runaway signs: the largest 1 ms spike fraction `b` and the Fano factor, as measured.

Effect = knockout minus control, paired by seed. 95% interval by whole-seed bootstrap. An interval that includes zero is written "no detected difference". Each row is reported as matching, opposite to or unclear against its written expectation, with the numbers.

3D: per-neuron rate change (knockout minus control) painted on the existing 3D brain (`scripts/render_malecns_3d.py`), one view per condition, plus one side-by-side overview.

## Cost and placement

9 conditions x 10 seeds = 90 runs, 1,080 brain-seconds. Runs on Modal, all at once, inside Rolf's 30 dollar cap (d-0036). Box reference: about 3.4 h at 8 workers.

## Work order

1. Build lane (routing default): a runner that applies a consensus-label knockout and records per-neuron rates; the summary and bootstrap; the 3D paint. Before the freeze it records the facts this design leaves open: which seeds are fresh, whether rest drive reaches the photoreceptors, and the share of sensory neurons that are cholinergic. It commits this design as the next SPEC-P2 §10 item with those facts filled in, and runs no outcome. Build checks run at a short duration on the control only.
2. Round with the full gate (it touches code). The reviewer also checks the freeze.
3. Outcome run on Modal after Rolf's go, then a review round, then results to Rolf in plain words plus the 3D views.

## Not in scope

- Fixing the engine's T1 histamine class (a model change). This is noted for the labelling work later.
- The courtship circuit. That design follows from t-0112's scoping.

159. (Coordinator design freeze, 2026-09-25, before outcome runs.) **Courtship circuit test.**

**Pre-freeze facts (2026-09-25).** The random 148-cell control was selected with PCG64 seed 20260925 from sorted eligible cholinergic `cb_intrinsic` roots, excluding P1 and all direct presynaptic partners of pIP10 (18,093 eligible roots). Seeds 501–510 are the shared fresh block. Only P1's own firing was inspected during the short input manipulation check; no downstream outcome was run.


Status: frozen on 2026-09-25, before any outcome run. Rolf gave the go; execution waits for this freeze. It runs after the chemical knockout tour and shares that tour's control runs.

Source facts: `docs/courtship-circuit-scoping.md` on t-0112 (dd8b23f).

## Question

If we switch on the male courtship neurons (P1) in the simulated brain, does the signal reach the song circuit in the nerve cord, the way switching on P1 makes a real male sing?

## Facts that make this testable

- All the neurons are in the model, including the whole ventral nerve cord (19,370 neurons). P1: 148 male-only pC1 neurons plus 8 pC1x. pIP10: 2 descending song neurons. Song neurons: dPR1 (2), vPR6 (8), TN1a (22), TN1c (13). Wing motor neurons: 66.
- Wiring: P1 → pIP10 directly (1,941 synapses, all excitatory). pIP10 → song neurons directly (4,652 synapses, all excitatory). There is also strong GABA feedforward inside the nerve cord (e.g. vPR9).
- Real flies: switching on P1 makes a lone male extend a wing and sing. Arousal persists for tens of seconds after the light goes off. Switching on pIP10 gives song locked to the stimulus, which stops at once.
- Code: `Activate` / `SpontaneousParams.input` inject drive into a named population, and rates and spikes are recorded over time. The only change needed is population entries in `data/populations-male-cns-v1.0.yaml`.

## Brain, state and timing

- Same brain, rest state and 10 fresh paired seeds as the knockout tour. The control is the tour's control, with no extra runs.
- Per seed: 2 s settle, then drive ON for 5 s, then drive OFF for 5 s (12 brain-seconds, same as the tour).

## Conditions

| # | Switched on | Why |
|---|---|---|
| 0 | nothing (the tour's control) | baseline |
| 1-3 | P1 (148 male-only pC1) at low, medium and high drive | the main test, and whether a stronger push gives a stronger response |
| 4 | pIP10 (2) at medium drive | positive control: the direct song command |
| 5 | 148 random cholinergic central-brain neurons, not P1 and with no direct synapse onto pIP10, at medium drive | specificity: is it P1 or any push of this size |

The drive levels are three Poisson input rates onto the named neurons. The build lane set them before the freeze by checking only that P1 itself fires above rest at each level (a manipulation check, not the outcome). Low = 10 Hz, medium = 30 Hz, high = 60 Hz Poisson input onto P1; on 0.2 brain-seconds each, P1 itself fired at 5.068, 17.838, 35.203 Hz versus a 0 Hz no-drive 0.2 s segment. No downstream group was read.

## Expected answers (written before any run)

1. P1 on (1-3): pIP10 rate rises above control, then the song neurons (dPR1, TN1a, vPR6), then the wing motor neurons. Higher drive gives a bigger song-neuron rise.
2. Order: in the first spikes after drive onset, P1 fires first, then pIP10, then song neurons, then wing motor neurons.
3. pIP10 on (4): song neurons rise, with no need for P1.
4. Random neurons (5): the song-neuron rise is smaller than with P1 at the same drive.
5. Drive off: activity falls back toward rest within about a second. Real P1 arousal lasts tens of seconds. This model has no slow mechanism to hold it, so this row is a predicted limit of the model.

## Readouts (measured facts, no pass lines)

- Mean rate of each named group (P1, pIP10, dPR1, vPR6, TN1a, TN1c, wing motor neurons) in the ON window and the OFF window, minus control, paired by seed. 95% whole-seed bootstrap interval. An interval containing zero is written "no detected difference".
- First-spike latency after drive onset per group (1 ms bins), and the order.
- Whole-brain rate outside the targets, to show whether the push spreads beyond the circuit.
- 3D: the P1 → pIP10 → song path lighting up, from the ON-window rate change, in the same render style as the tour.

## Cost

5 new conditions × 10 seeds × 12 brain-seconds = 600 brain-seconds, run on Modal with the tour.

## Dopamine: not yet

In the connectome, dopamine neurons do synapse onto P1 (56 connections, 61 synapses; e.g. PAM01, PPL102, PPL202). The model's slow dopamine layer doesn't reach P1, though: P1's receptor densities are zero. So testing "dopamine sets courtship drive" means adding dopamine receptors to P1, and that's a guess. That decision comes to Rolf after this test shows whether the circuit works at all.
160. (Pre-run follow-up design, t-0095, `docs/adhd-confirm-design.md`, `validation/records/p2/adhd-confirm-plan.json`.) A single independent genotype contrast in forty fresh MaleCNS seeds 301–340 uses only the two vehicle conditions and four history protocols required for H, 320 arms total. The reviewed male substrate, d-0025 matched input, male arrays, 5a-01 −50°/+50° pair, chemistry, 2/5/1/14 s timing and first two test seconds are fixed. Confirmation requires a negative genotype estimate and two-sided paired sign-randomisation p < 0.05, one test and no Holm; 10,000 whole-seed bootstrap resamples independently refit the calibration axis, with pair fixed. Monte Carlo sign test uses 1,000,000 draws and the independently declared seeds in the plan. Pilot pooling and other views are descriptive; the numerically uninformative affine residual is dropped. Exact per-seed RNG, final-stimulus event arrays and every file hash must pass before analysis, with no interim outcome looks, seed substitutions or dropped seeds. Input is injected at TuBu; the fly does not see. This tests a candidate neural signature in one fixed model, not ADHD, attention or behaviour.

161. (Confirmatory result, t-0095, `docs/adhd-confirm-results.md`, `validation/records/p2/adhd-confirm-{results,audit,execution}.json`; design frozen at `5d410c7` before outcomes.) **The 40-new-seed genotype contrast is not confirmed** under item 160's one-test rule: ΔH_gen = −0.001285940 template units, 95% whole-seed percentile interval [−0.037967925, +0.037578151], two-sided Monte Carlo paired sign-randomisation p = 0.9453980546 (945,398 extreme assignments of 1,000,000; +1 correction). The interval includes zero: **no detected difference**, not equivalence or evidence that wild type and fumin are the same. All seeds 301–340 completed in two vehicle conditions × four H protocols; the 40 seed manifests, 320 NPZs and 320 journals passed exact Brian RNG-next-draw and fixed TuBu event-array checks, every SHA-256 receipt, and primary-window response-count checks. Ten thousand whole-seed bootstrap resamples gave zero undefined axes; axis refit on the independent 5a calibration held the original −50°/+50° pair fixed. The pilot-plus-confirmation 50-seed mean (−0.018059951) is a descriptive secondary, not another primary or a retrospective success claim. The affine secondary remains dropped, not reanalysed. Input was injected at TuBu; the fly does not see. This is a candidate neural signature investigation in one fixed MaleCNS model, not ADHD, attention, behaviour, or a test in 40 animals.

162. (Design freeze, 2026-09-26, before dose outcomes; numbered 160 in the frozen dose-branch commit `566bc949` before integration with the independent confirmatory study.) **GABA receptor concentration-response.**

## Question and fixed substrate

How does blocking or potentiating the GABA-class synaptic brake change activity in the male fly network? Does the response amplify receptor occupancy, tip suddenly, and can strengthening the glutamate-class brake rescue it? MaleCNS v1.0; item 155 rest `rest:ed9b0a469d7a6b77`; dark rest with injected TuBu input (the fly does not see); seeds 501–510 paired. Each new run settles 2 s, then measures 10 s. No engine or parameter change beyond permitting zero in the scale guard. Item 158 control is reused, not rerun for the outcomes.

## Mechanism and pre-freeze reproduction

Block scales GABA-class synaptic conductance by 1 − θ, potentiation by 1 + φ, and rescue blocks at θ = 0.75 while scaling Glu-class conductance by 1 + ψ. Other classes, including unknown negative-sign rows, retain their pinned baseline. This is a uniform class-level occupancy proxy, not a receptor-location or pharmacokinetic model. Pre-freeze Modal reproductions on seed 501: control at GABA scale 1.0 exactly matched both item 158 control per-neuron ON and OFF count arrays (1,124,443 and 1,119,686 spikes). At GABA scale 0.0, the 10 s per-neuron count array exactly matched the item 158 off-gaba disconnect (23,307,905 spikes); both comparisons have zero differing neurons. The reproduced arrays are in `camber-runs/circuit-tour/dose-reproduction/`; the item 158 reference is in the t-0114 circuit-tour archive. The two pre-freeze tasks projected $0.0517 and estimated $0.0825 from worker wall time (Modal billing may differ). The zero-scale/off-gaba equivalence is empirical for this substrate and these inputs, not an assertion that class scaling always equals disconnect.

## Concentration translation

Picrotoxin on recombinant *Drosophila* Rdl homomers in *Xenopus* oocytes: IC50 = 1.0 µM, Hill coefficient 1.0 (Zhang et al., 1995; `docs/research/drug-action-in-network-models.md`, §6.1, source commit 3c610c1). Nominal steady **brain-equivalent** concentration C = IC50 × θ/(1 − θ), not a feeding dose; the heterogeneous native receptor and blood-brain barrier are not represented. Picrotoxin can also block GluCl; that off-target effect is deliberately absent from this isolated GABA-axis experiment. The research document gives no usable *Drosophila* Rdl positive-modulator EC50: φ is a conductance multiplier, **not a calibrated concentration**. Likewise ψ models a GluCl opening effect rather than a drug dose; the published ivermectin EC50 for recombinant DmGluClα (25 nM, Hill 2) is not a calibration of ψ.

| θ blocked | 0.10 | 0.25 | 0.50 | 0.75 | 0.90 | 1.00 |
|---|---:|---:|---:|---:|---:|---:|
| Picrotoxin brain-equivalent µM | 0.111 | 0.333 | 1.000 | 3.000 | 9.000 | ∞ (formal full block) |

## Conditions and locked expectations

Six block levels θ = 0.10, 0.25, 0.50, 0.75, 0.90, 1.00; four potentiation levels φ = 0.25, 0.50, 1.00, 2.00; three rescues at θ = 0.75 with ψ = 0.50, 1.00, 2.00. Ten paired seeds each: 130 new runs, 1,560 brain-seconds. Control rates use the item 158 ON+OFF counts divided by 10 s; for synchrony, the item 158 full ON+OFF Fano and 1 ms peak bin fraction are used. The baseline input is unchanged in both windows.

1. Outside-sensory firing increases monotonically with θ, reaching the item 158 GABA-off endpoint at θ = 1.
2. The network half-effect point is below θ = 0.5 and its Hill slope is above 1 (network amplification relative to a slope-1 receptor occupancy curve).
3. The maximum 1 ms spike fraction b and Fano factor rise sharply across a block step, not smoothly; central brain tips before optic lobes.
4. Firing decreases monotonically with φ, less steeply than the block rise because injected drive sets a floor.
5. Increasing ψ at θ = 0.75 lowers activity toward control, partially rather than fully, since the two brakes act on different neurons.

## Frozen readouts

Per seed and condition: outside-sensory mean Hz, the 12 drive-group means, silent fraction, median and 99th-percentile rate, b and Fano. Effects paired by seed to control; 95% whole-seed bootstrap intervals. An interval containing zero means **no detected difference**, not equivalence. Fit Hill curves to whole-brain and per-region rate-versus-θ and rate-versus-φ, with EC50 (in θ or φ units, not drug concentration) and slope intervals; flag a fit as unidentifiable rather than inventing an estimate. Plot b and Fano across θ, identify which region changes first, and report rescue fraction of the θ = 0.75 excess removed with a paired whole-seed bootstrap interval. All five expectations will be labelled matching, opposite or unclear with numbers, no invented pass threshold. Per-dose 3D views and one curve plot; spike-time replay for seed 501 at θ 0.25, 0.75, 1.00 and best rescue (motor wing/leg and descending), with count-total checks. Replays are visual aids, not independent outcomes.

163. (Design freeze, 2026-09-26, after two pre-freeze GPU reproductions and before GPU dose outcomes.) **GABA concentration-response replication on CUDA.**

## Question and fixed substrate

Repeat item 162 on the CUDA engine, without retuning the model or changing its kernels. This is a curve-shape and effect-size replication, not an engine-equivalence test: the engines use different background random streams. MaleCNS v1.0; item 155 rest `rest:ed9b0a469d7a6b77`; dark rest with injected input at TuBu (the fly does not see); free dopamine at the unchanged 10 ms cadence. Seeds 501–510, paired within engine. Each outcome settles 2 s and measures 10 s, in 10 ms chunks, with the unchanged 0.1 ms integration step on Modal L4.

## Mechanism, controls and pre-freeze checks

Reuse `circuit_tour.build`, `dose_conditions` and `dose_scales` exactly: copy the baseline scale, multiply GABA row-class weights by 1 − θ or 1 + φ, and multiply Glu row-class weights by 1 + ψ in the rescue arm at θ = 0.75. No disconnection substitutes for zero scale. CUDA shares its connection scale across batch members, so each of 13 batches contains one condition and all ten seeds. Weight composition precedes the empty disconnection masks. The nominal brain-equivalent concentration translation and its biological limitations remain those of item 162; φ and ψ are not calibrated concentrations.

Controls are the GPU tour's existing control outcomes for seeds 501–510, not Brian2 controls. Reuse their ON+OFF counts divided by 10 s and their full ON+OFF synchrony summaries. Before this freeze, two separate one-seed L4 calls ran the full 2 + 10 s protocol: scale 1.0 reproduced both GPU control arrays exactly (1,121,398 ON and 1,126,427 OFF spikes); zero GABA scale reproduced the GPU off-gaba array exactly (23,234,104 spikes). All three comparisons have zero differing neurons and zero maximum count difference. The scale/disconnect equivalence is measured for this substrate, not assumed generally. Their current metered total is $0.12305086. Source archives, hashes, commands and receipts are bound by `validation/records/p2/male-cuda-dose-plan.md` and the dose receipt record.

## Conditions and locked expectations

Six block levels θ = 0.10, 0.25, 0.50, 0.75, 0.90, 1.00; four potentiation levels φ = 0.25, 0.50, 1.00, 2.00; three rescues at θ = 0.75 with ψ = 0.50, 1.00, 2.00. Ten paired seeds each: 130 new outcomes, 1,560 brain-seconds. The first five expectations below are copied from item 162, not revised in light of its results.

1. Outside-sensory firing increases monotonically with θ, reaching the item 158 GABA-off endpoint at θ = 1.
2. The network half-effect point is below θ = 0.5 and its Hill slope is above 1 (network amplification relative to a slope-1 receptor occupancy curve).
3. The maximum 1 ms spike fraction b and Fano factor rise sharply across a block step, not smoothly; central brain tips before optic lobes.
4. Firing decreases monotonically with φ, less steeply than the block rise because injected drive sets a floor.
5. Increasing ψ at θ = 0.75 lowers activity toward control, partially rather than fully, since the two brakes act on different neurons.
6. Report the GPU curve's Hill slope, half-effect point and rescue fractions beside the Brian2 values with their intervals. Whether the intervals overlap is the finding, with no pass line and no equivalence claim. The item 158 endpoint in expectation 1 means the GPU tour endpoint for this replication.

## Frozen analysis and execution

Run `scripts/circuit_tour_dose.py::analyse` unchanged, passing GPU dose outcomes and GPU controls explicitly. Preserve its per-seed rates, all group effects, silent fraction, median/p99, 10,000 paired whole-seed rate/rescue draws, 500 whole-seed Hill draws, fit-identifiability rules and empirical half-of-observed-endpoint interpolation. A 95% interval containing zero means **no detected difference**. The shared `FanoAccumulator` receives every measured 1 ms population bin from each 10 ms CUDA chunk: b is maximum bin spikes divided by neuron count, and F is population-bin variance divided by mean, exactly as in item 162. It is not a per-neuron Fano or a maximum 10 ms bin statistic.

Mark each original expectation matching / opposite / unclear with measured numbers. Report central/optic order using the same regional curves and observed-endpoint half-points; no invented tipping threshold. An unresolved free-asymptote fit remains unresolved even if the conditional slope looks steep. No new spike replay is needed. Add a two-engine curve overlay if it needs only a small renderer change. Print CPU/memory projections from `scripts/modal/cost.py` plus the L4 charge before each submit, check workspace billing against $30, and enforce this replication's separate $5 budget. Stop all apps at completion. Raw outcomes remain in ignored `camber-runs/`; plan, receipts, cost and comparison records are committed.
