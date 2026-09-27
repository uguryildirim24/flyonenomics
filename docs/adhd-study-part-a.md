# Male dopamine/history study: preparation, not experimental results

**Completed under d-0025 — 2026-09-24.** 5b-02 finished **320/320 arms and ten audited seeds**, exit 0 at **04:43:34 UTC**. Exact RNG/event checks passed remotely and after transfer; the frozen analysis ran unchanged. [Unreviewed results and intervals](adhd-study-results.md): neither primary survives Holm; the affine secondary is ill-conditioned and reported without repair. This page preserves preparation/qualification history. The earlier d-0023 failure and its 60 partial 5b-01 arms remain **void evidence, never inference data**.

Part A is complete. The coordinator authorised progression on 2026-09-22 after rebinding to the merged male substrate: stage 5a, then a committed pair choice, then stage 5b. The lane report records launch progress; no genotype or rescue finding is claimed here. No result here establishes ADHD, attention, behaviour or a drug dose. The uniform ER receptor assignment is unvalidated; seeds describe stochastic variation in one fixed anatomical model, not different flies or uncertainty in its biological parameters.

The first design commit is `892cf6f`. The full design from the brief is preserved verbatim in `docs/adhd-study-design.md`, followed by the implementation choices. The adopted substrate is item 157's reviewed **`male-cns:v1.0`, `rest:ed9b0a469d7a6b77`**, merged on main at `2ba4512`. Earlier `rest:5836215ca8694178` is not adopted. The cost probe used its earlier `59064c5` identity, `rest:8aff910a6e7481ad`. The later shared-constant pins, reviewed-rest binding and five-model-source manifest pin changed provenance hashes, not a numerical model setting; the cost record verifies exact equality of the graph, drive/chemistry values, input patterns and timing. Research was read on t-0073 at `082ffda`; its conclusions do not become measured male-brain results.

## Coordinator decision d-0025 — input plumbing repair, not design

The requirement remains: within a seed, identical final stimuli receive **identical actual external event arrays**, regardless of prefix. No audit is relaxed, seed substituted, duration shortened in the experiment or analysis changed.

- **TuBu:** pre-generate fixed tick/cell lists with dedicated PCG64 streams from `SeedSequence(master, spawn_key=(25, seed, segment, stimulus))`. Stream keys do not include genotype, intervention, prefix history, process or wall time. Insert lists through the existing `SpikeGeneratorGroup` path. Preserve Brian2's existing **clocked Poisson convention**, independent Bernoulli(`rate × dt`) per cell/tick, not a new continuous-time/multiple-events-per-tick approximation. Rates, source cells, input weights, delays and scheduling slots stay fixed. Compare actual monitor events to the complete pre-generated list exactly.
- **Background:** opt in only within this study. Retain the original Brian2 `PoissonInput`/`BinomialFunction`, N=100, rate=10 Hz/input, weights, dt check and synapses-slot/order. Write its sampled count for **every target** into an ungated dimensionless scratch variable, then apply it to `g` through the **existing refractory conditional write**. Refractory targets discard the draw rather than skip sampling. This makes the engine stream consumption independent of neuronal activity. No engine default, LIF equation, FlyWire input path or recorded reference is edited; no separate background stream is needed.
- The per-arm transition law is unchanged: the original conditional update is still the same binomial increment when eligible, zero when refractory. Sampling and discarding unused independent draws does not change that conditional law. Only the cross-arm random-number coupling is repaired to the frozen requirement. For TuBu, the per-cell/tick event law is unchanged too. Tests reproduce the old state-dependent RNG defect, verify equal new draw tapes/final states under different refractory histories, check discarded positive draws and the unchanged gating, and show exact original/new background traces when no targets are refractory.
- Retain **5a-01 and the exact committed −50°/+50° pair at e34ca13**, conditional on this unchanged per-arm law. Its data used old random plumbing with the same input statistics; 101/102 already proved byte reproducibility of that old data. Archive its plan byte-for-byte as `adhd-study-calibration-plan.json`; bind that old plan/pair explicitly in the repaired plan instead of rewriting old selection receipts or claiming old execution under new code. The old within-seed RNG audit remains failed, not retroactively passed. **Skip replay seeds 103–110**: d-0025 no longer requires it as a reporting gate.
- Validate before a full run: **two diagnostic seeds 201/202**, WT vehicle, **off→AB, A→AB, B→AB**, with the actual full male engine. Diagnostic timing is 0.02 s settle, 0.04 s prefix, 0.02 s gap, 0.12 s test (0.20 s/arm); this is labelled **diagnostic-only**, never calibration/inference. Require actual/fixed-list event equality, one initial and one final engine-RNG hash per seed across arms, and identical final AB event hashes. Production remains 2/5/1/14 s with the original primary window. Unit tests cover both mechanisms and rejection of mismatched hashes.
- Then the **unchanged full gate**. Commit repair and validation before restarting **5b on the original 201–210 seeds, ten workers**, in a fresh `5b-02` directory. `5b-01`'s 60 partial arms are void and cannot enter analysis. A diagnostic failure, gate failure or change in per-arm model law stops with `ha waiting`; otherwise launch without another approval pause.

Implementation: `src/flyonenomics/drive/paired_inputs.py` plus the study runner, committed **648d2a1**, rebound on Linux at **cb9229a**. All original non-identity plan fields compare exactly equal; the original pair's bytes are unchanged. **15 local checks passed.**

**Full-male diagnostic passed:** 2026-09-23 **06:44:38–06:47:17 UTC**, exit **0**, six arms and two complete diagnostic manifests. For each seed, all three histories have **one initial and one final engine-RNG hash**, and actual injected events equal their fixed lists. Independent raw-array comparisons confirm identical final AB events: **206 events for seed 201, 229 for seed 202**. Prefixes did differ: 0/29/37 events for seed 201 and 0/39/38 for 202 (off/A/B). These are integrity checks, not genotype findings. Records/hashes: `validation/records/p2/adhd-study-input-repair.json`; raw/logs: `camber-runs/adhd-study/paired-input-diagnostic-01*`.

**Full requalification passed** at **cb9229a**, neural workers idle: **2026-09-23 06:49:42–08:16:01 UTC**, **951 passed, 30 skipped, 49 warnings, exit 0**; 5,175.98 s pytest / 5,179 s driver, within the unchanged **5,400-second** outer deadline. JUnit has 981 tests, zero failures/errors. Adaptation took **509.330 s**, under the disclosed **2,400-second** child budget: **not a pass under the former 300-second limit**. FlyWire full-engine reference checks passed without changing defaults/references. Logs/XML/status: `camber-runs/adhd-study/paired-input-full-suite.*`; hashes and timing: repair/gate records. The prior 947-pass gate remains historical. Validation was committed at **f28779b** before **5b-02 launched at 2026-09-23 08:20:40 UTC**, ten workers, unchanged seeds **201–210**. Execution/status is separate in `adhd-study-5b-rerun.json`; `5b-01` remains void. **5b-02 subsequently completed at 2026-09-24 04:43:34 UTC, exit 0.** All ten exact d-0025 audits passed, including full fixed-list regeneration, remote/local hashes and every final-stimulus array. See `adhd-study-5b-audit.json` and the [results](adhd-study-results.md). No code changed during collection/analysis, so the full suite was not rerun; review runs the pinned gate.

```bash
FLYONENOMICS_CACHE_DIR=$HOME/flyo-cache .venv/bin/python scripts/adhd_study.py diagnostic --workers 2 --pair validation/records/p2/adhd-study-pair.json --out camber-runs/adhd-study/paired-input-diagnostic-01
# Only after diagnostic AND unchanged full gate pass, with validation committed:
FLYONENOMICS_CACHE_DIR=$HOME/flyo-cache .venv/bin/python scripts/adhd_study.py 5b --workers 10 --pair validation/records/p2/adhd-study-pair.json --out camber-runs/adhd-study/5b-02
# Only completed, audited 5b-02 seeds enter inference; 5b-01 is void:
.venv/bin/python scripts/adhd_study.py analyse --raw camber-runs/adhd-study/5b-02 --calibration camber-runs/adhd-study/5a-01 --pair validation/records/p2/adhd-study-pair.json --out validation/records/p2/adhd-study-results.json
```

## Chemistry frozen before the cost probe

The source is `validation/records/p2/adhd-study-plan.json`. The release multiplier is **`0.37499999999999994`**, calculated from the adopted kinetic constants, not fitted to neuronal output. It multiplies standing and spike-dependent release equally in both genotypes. Fumin removes transporter uptake only; first-order clearance remains.

| Condition | Initial pool in each innervated compartment (µM) |
|---|---:|
| Wild type, vehicle | 0.020000000000000000 |
| Fumin, vehicle | 0.05333333333333333 |
| Wild type, release reduction | 0.007455292704222517 |
| Fumin, release reduction | approximately 0.020000000000000000 |

The complete 37-element arrays, including floating-point rounding, are in the plan. **PB is uninnervated and is held at 0.02 µM in every condition by the existing chemistry implementation.** These are analytic initialisations at the measured *wild-type* resting source rates, not proof that feedback leaves those rates unchanged in fumin. Settle drift is recorded; no arm is labelled equilibrated on that basis.

The plan was first committed at `c7fdfb9`, before the cost probe. The plan at `4c32070` additionally ran the *complete* frozen inference on noisy synthetic controls. The current plan's `identity.commit` records its generator, incorporating the merged substrate, its five-model-source manifest pin, all adopted upstream pins and bound-reader corrections. Chemistry, anatomy, timing, interventions and inference did not change.

## Inputs and frozen analysis

- **156 TuBu inputs**, **245 directly reached ER readout cells**. All cells remain in the readout, including silent cells. The all-ER structural audit contains **18,437 ER→ER edges**, with composed signs and weights. Presynaptic counts are retained during the runs; a negative anatomical edge alone is not evidence for effective mutual inhibition.
- Single-position input sums are matched to **926.8883135526094 Hz** by the male encoder, before neuronal outcomes. Positions are imposed body-ID-based labels, not validated visual coordinates. Every cell's injected rate is recorded, as are the capped pair rates and actual external and emitted TuBu events.
- Two seconds of blank settle. Stage 5a has 20 further seconds per position. Stage 5b has a 5 s prefix, 1 s gap, 14 s test; the first 2 s of the test are primary. There is no within-trial reset. This preserves item 146's approximate 20 s trial; that item does not specify a numerical split.
- The pair is the first represented pair in the frozen anatomical-label order, **not** the pair with the greatest distance. The off/A, off/B and A/B checks hold out whole seeds. The unchanged rule selected **−50°/+50°**, the first eligible pair, from `5a-01`; committed at **`e34ca13`** before 5b. The encoder retains both members (`equals_a=false`, `equals_b=false`); pair cap loss is 5.33×10⁻¹⁵ Hz (roundoff scale). d-0023's old replay audit failed; d-0025 retains the original calibration under unchanged per-arm law/input statistics, skips replay 103–110, and requires the repaired exact 5b checks (now passed).
- Ten fresh calibration seeds and ten different experiment seeds. The A-versus-B axis comes only from calibration data. All inference resamples whole seeds, including independent calibration seeds, with the selected pair held fixed. Primary p values use exact paired sign randomisation and Holm over the two prescribed comparisons. Template-selection uncertainty is not included.
- The affine secondary uses only off and single-input controls, excludes the evaluated seed (including duplicate bootstrap copies), corrects the fitted moments for sampling noise, and reports unidentifiable cells rather than hiding them. Its residual is against the specified fitted prediction, not every admissible affine transform: an intercept-only convention for an unidentifiable slope cannot establish that a rate-scaling explanation is excluded.

Scripts: `scripts/adhd_study.py` and `scripts/adhd_analysis.py`. Raw output is compressed per arm, with an atomic complete-seed manifest and hashes. The runner records native 10 ms pools, applied ER terms and occupancies, ER/TuBu counts and population counts. It also checks actual injected event hashes across identical final stimuli. Pool-based occupancy arrays were added after the cost runner was launched; the dynamical loop is unchanged.

## Male arrays in every arm — explicit path, not the generic worker

`adhd_study.load_inputs()` calls `malecns_substrate.male_inputs()`. That helper resolves `male-cns:v1.0` engine files and registry, loads `data/transmitters-male-cns-v1.0.yaml`, constructs signs from the male signed weights, and constructs the KC mask from the male registry. It supplies **classes, edge signs, pre, post, KC mask, neuron count and connectome version** explicitly.

Both static preparation and the live engine call:

```python
apply_rest_substrate(engine, params, drive, **ctx['scale_inputs'])
```

Thus the `classes is None or s_pq is None or pre is None` FlyWire-default branch is not taken. The generic orchestrator worker is **not used** by this experiment; its separate default-path issue is not claimed fixed here.

The live construction checks the graph against the frozen plan, and `apply_rest_substrate` checks the float32 scale hash against the male drive file: **`fb6270f518f06cd0adb42748ae10baa360dec752edd237ce7ecdefa70450a84c`**. The plan's `male_array_binding` also records 162,517 neurons, 25,120,209 edges, transmitter-class, edge-sign and KC-mask hashes, and graph-array hashes. Construction compares this binding exactly before storing `study_initial`.

Every off/position arm and every genotype × history arm calls the same `arm()` with this built context, restores **that same male snapshot**, and changes only the defined chemistry and TuBu inputs. `BrianEngine.store()` keeps the immutable pre/post connectivity live and saves the applied synaptic weights in a float64 sidecar; `BrianEngine.restore()` reloads those weights without calling any resting-substrate loader or default-array path. Neither fumin nor release reduction edits weights, edges or the KC mask. Every new arm manifest repeats the verified `male_array_binding` (provenance from the shared snapshot, not a new per-arm scan of all weights). The executed cost arm used this same explicit-array construction; its earlier graph and numeric scale are exactly equal. This combines executed one-arm evidence with a common-path guarantee for all planned arms, **not** a claim that 32 unrun experimental arms have already been measured.

## Execution correction: RNG fingerprint, not model or analysis

The first authorised 5a attempt (`f774c3b`, `5a-01`) produced all 50 arm files but exited 1 at the whole-seed RNG audit, before writing any complete-seed manifests. Its RNG audit has **not passed**. Coordinator decision **d-0019** authorises conditional pair selection from these unchanged neural outputs; **d-0023** below governs the revised replay order and reporting checkpoint. The failed attempt, its exact error and all raw hashes are retained in `validation/records/p2/adhd-study-5a-replay.json`.

The audit had pickled `Brian2.RuntimeDevice.get_random_state()`. In Brian2 2.10.1 its `rand_buffer` and `randn_buffer` fields contain **memory addresses**, not the buffered random numbers. Different allocations therefore fail that checksum despite identical streams; conversely, changed numbers at the same address can evade it. The corrected fingerprint includes NumPy's generator state, buffer indices and the actual unread buffer values. At index zero the Cython implementation refills the buffer before use, so old storage is irrelevant.

Initial/final state equality and the exact final-stimulus event checks remain mandatory. Deterministic regression tests cover both allocation independence and detection of changed unread values, plus actual Cython snapshot replay. Per-arm audit journals are now written atomically before the whole-seed checks, so later failures cannot erase their evidence. The original seeds/five original arms are replayed in two batches under d-0023. Each replayed NPZ must match **byte-for-byte**, not merely approximately or array-wise; the initial two-seed match gates reporting, and the remaining eight are reported separately when completed. No input, timing, model parameter, pair rule, response window or inferential method is changed. Original RNG hashes and timing receipts remain unavailable, not fabricated.

## Coordinator decision d-0019 — historical order, superseded by d-0023

On 2026-09-23 the coordinator changed the order to remove the 5a replay from the critical path. Repair `8b5ad3f` corrects audit bookkeeping only; it changes no model, input, timing, seed or analysis, and leaves `5a-01`'s neural outputs untouched.

1. Let the running full gate finish under the unchanged command/deadlines. On failure, stop with `ha waiting`. The old automatic replay-launch branch is disabled; the running pytest and timeout are untouched.
2. On gate exit zero, run the **unchanged frozen pair rule on `5a-01`**, commit the pair, then launch **5b with ten workers and the corrected RNG audit**, without another approval pause. The position/encoder prerequisites still apply.
3. Only after 5b finishes, run the unchanged ten-seed **`5a-02`** replay while analysing 5b against the original calibration. Every original NPZ must reproduce **byte-for-byte**, and all ten replay seeds must pass the corrected audit. Preserve the exact comparison. Any mismatch or audit failure requires `ha waiting` **before reporting any 5b result**. No array-only fallback, tolerance, seed replacement or pair reselection is authorised.
4. Analysis outputs remain provisional/unreported until that verification succeeds. This decision changes scheduling and defers verification; it does not change the frozen design or relabel the original failed audit as passed.

## Coordinator decision d-0023 — historical order, superseded by d-0025

The coordinator corrected d-0019 on 2026-09-23: deferring the entire replay still left it on the reporting critical path. **d-0023 is the recorded decision label** for this correction.

1. Unchanged: finish the full gate; failure means `ha waiting`. On exit zero, select the frozen-rule pair from `5a-01`, commit it and immediately launch 5b with ten workers and the corrected RNG audit. Position/encoder prerequisites remain mandatory.
2. Once 5b is up and steady, record `free -g`, available CPUs and load. Only with **at least 20 GB available and load leaving at least two cores**, run original seeds **101 and 102**, all five original arms, concurrently under **`nice -n 10` with two workers**. If headroom is insufficient, run those two seeds immediately after 5b instead. Do not change model code, inputs, seeds, timing or analysis.
3. The **two-seed exact-byte match and corrected-audit pass gate the 5b result report**, not completion of the entire replay. On mismatch or audit failure, stop with `ha waiting` before any 5b finding. Preserve all ten NPZ byte comparisons and both actual seed receipts; no array-only fallback or tolerance.
4. Run remaining seeds **103–110 after 5b**, alongside analysis. Report their forty byte comparisons and audit outcomes when done; **flag any mismatch immediately**. If a 5b report precedes those checks, explicitly state that only two seeds have been verified and the other eight are pending; never imply full replay verification.

This changes scheduling and the coordinator's reporting checkpoint, **not the frozen scientific design**. All ten original calibration seeds remain in pair selection and inference; no seed is replaced or omitted from the experiment. Split dispatch invokes the existing `run_seed` jobs unchanged, with source/plan checks retained. The runner, pair rule, estimands, windows and inference remain frozen.

### Selection receipts for the original files

The original failed attempt wrote no complete-seed manifests. The unchanged pair reader needs seed/arm mapping and file hashes, so add explicitly labelled **post-hoc selection receipts**, not successful-run certificates. They retain executed commit `f774c3b` and its original plan hash. Their `plan_sha256` is explicitly an **analysis/continuation binding** to the corrected plan, not a claim that the old run executed that code. All non-identity plan fields must compare exactly equal; only the bound runner's bookkeeping source differs. Male-array evidence comes from the original plan and the executed build's mandatory equality check. Do not invent original RNG hashes, per-arm timings or memory measurements.

Before pair selection, the known d-0019 receipt metadata is updated to reference d-0023's reporting checkpoint (prior receipt hashes remain archived at `5c39f2e`). Once frozen in the pair record, the receipts are immutable. Later replay verification is recorded separately; it must not rewrite them or substitute new calibration files into the frozen pair/inference. Reproduce them, without touching any NPZ or running a neural model:

```bash
.venv/bin/python - <<'PY'
import hashlib, json, subprocess
from pathlib import Path

def at(commit, path):
    return subprocess.check_output(['git', 'show', f'{commit}:{path}'])
def sha(data):
    return hashlib.sha256(data).hexdigest()

executed = 'f774c3bdb3dcac6f0c766c45bfe5fd77122a381a'
plan_path = 'validation/records/p2/adhd-study-plan.json'
old_bytes = at(executed, plan_path)
old = json.loads(old_bytes)
new_bytes = Path(plan_path).read_bytes()
new = json.loads(new_bytes)
assert new_bytes == at('b6b5ccc', plan_path)
assert {k:v for k,v in old.items() if k != 'identity'} == {k:v for k,v in new.items() if k != 'identity'}
changed = [k for k,v in old['identity']['sha256'].items() if new['identity']['sha256'].get(k) != v]
assert changed == ['scripts/adhd_study.py']
archive = json.loads(at('8b5ad3f', 'validation/records/p2/adhd-study-5a-replay.json'))
raw = Path('camber-runs/adhd-study/5a-01')
assert {p.name:sha(p.read_bytes()) for p in raw.glob('*.npz')} == archive['raw_sha256']
positions = ('off', '-150.0', '-50.0', '50.0', '150.0')
for seed in range(101, 111):
    rows = []
    for arm, position in enumerate(positions):
        name = f'seed-{seed}-arm-{arm:02}.npz'
        rows.append(dict(condition='wt-vehicle', protocol=position, file=name,
                         sha256=archive['raw_sha256'][name], male_array_binding=old['male_array_binding']))
    receipt = dict(seed=seed, stage='5a', pair_sha256=None, rows=rows,
        identity={**old['identity'], 'commit':executed},
        identity_evidence='Reconstructed from executed commit and its verified plan pins; not an original runtime receipt.',
        receipt_kind='posthoc-selection-only-d-0019', original_rng_audit='failed; original hashes unavailable',
        plan_sha256=sha(new_bytes), executed_plan_sha256=sha(old_bytes),
        plan_sha256_role='Analysis/continuation binding under d-0019, NOT the executed plan.',
        male_binding_evidence='Original plan; executed build requires exact equality before study_initial.',
        unavailable=['original_rng_initial_sha256', 'original_rng_final_sha256', 'arm_wall_s', 'build_wall_s', 'peak_rss_bytes'],
        verification_order_decision='d-0023',
        verification_required='Seeds 101 and 102: exact NPZ bytes and corrected audit required before 5b findings. Seeds 103-110: replay after 5b alongside analysis, report when done and flag any mismatch immediately.')
    payload = (json.dumps(receipt, indent=2, allow_nan=False)+'\n').encode()
    target = raw/f'seed-{seed}.json'
    if target.exists() and target.read_bytes() != payload:
        assert not Path('validation/records/p2/adhd-study-pair.json').exists(), 'Pair already frozen'
        prior = json.loads(at('5c39f2e', 'validation/records/p2/adhd-study-selection-receipts.json'))
        assert sha(target.read_bytes()) == prior['receipts_sha256'][target.name], target
    if not target.exists() or target.read_bytes() != payload:
        temporary = target.with_suffix('.json.tmp')
        temporary.write_bytes(payload)
        temporary.replace(target)
print('Ten selection-only receipts; original NPZ hashes unchanged; RNG verification still pending.')
PY
```

## d-0023 checkpoint outcome — byte match passes, pairing prerequisite fails

The two-worker, nice-10 replay ran **02:57:50–06:02:32 UTC on 2026-09-23**, after ten-worker 5b reached its first-arm checkpoint. At dispatch, `free -g` reported **78 GB available**; 16 CPUs minus the maximum load average left **5.765 cores**. Both replay workers' nice values were independently confirmed as 10.

All **ten NPZ files for 101/102 match the original archived SHA-256 values exactly**. That demonstrates that the bookkeeping repair did not change those neural outputs. It does **not** demonstrate the required within-seed random-stream pairing. Both replay seeds have one initial RNG hash but **five distinct final hashes**, and the existing whole-seed check raised `ValueError: external random stream consumption differs across arms`. Exit **1**; no complete-seed manifests were written. The two-part reporting checkpoint therefore **failed**.

This is not dismissed as another hash-format issue: independently recomputed hashes of actual recorded injected-event arrays in completed 5b arms differ for **off→AB versus A→AB in all ten seeds**. For example, seed 201's final 14 s test has 25,971 versus 25,829 injected events despite the same final AB rates. These are **protocol-integrity diagnostics, not genotype findings**. The frozen requirement of identical final-stimulus external events is unmet.

5b was explicitly terminated at **06:04:32 UTC**, exit **143** (operator cancellation, not a completed 5b analysis), with **60/320** arm files and zero complete-seed manifests. All completed arms were WT vehicle; no genotype comparison was executed or reported. Remaining replay seeds 103–110 were **not started**. Raw files, arm journals, actual event hashes and the exact comparison are retained locally and on the box, bound by `validation/records/p2/adhd-study-5a-replay.json` and `adhd-study-5b-execution.json`.

The address-hashing defect was real, but correcting it was not sufficient to establish the full experiment's pairing assumption. The passing small Cython regression did not exercise this full setup. A concrete mechanism to investigate is the background `PoissonInput` targeting refractory-gated `g` alongside an extended `PoissonGroup`: state-dependent background draw consumption can couple into a shared generator. This mechanism has not been repaired or isolated by a new neural run. **Do not drop the audit, change the pairing requirement, substitute seeds, report 5b results or restart automatically.** The lane stops with `ha waiting` for a coordinator decision on the unmet prerequisite and any required repair/requalification/recalibration.

Recheck the blocked checkpoint and the example event diagnostic without running a neural model or the genotype inference:

```bash
.venv/bin/python - <<'PY'
import hashlib, json, subprocess
from pathlib import Path
import numpy as np
from flyonenomics.io import load_npy
base = Path('camber-runs/adhd-study')
expected = json.loads(subprocess.check_output(['git','show','8b5ad3f:validation/records/p2/adhd-study-5a-replay.json']))['raw_sha256']
for seed in (101, 102):
    rows = []
    for arm in range(5):
        name = f'seed-{seed}-arm-{arm:02}.npz'
        for run in ('5a-01', '5a-02'):
            assert hashlib.sha256((base/run/name).read_bytes()).hexdigest() == expected[name]
        rows.append(json.loads((base/'5a-02'/Path(name).with_suffix('.json')).read_text())['row'])
    print(seed, 'five byte-identical files; initial/final distinct hashes:',
          len({r['rng_initial_sha256'] for r in rows}), len({r['rng_final_sha256'] for r in rows}))
for arm in (3, 5):
    stem = f'seed-201-arm-{arm:02}'
    row = json.loads((base/'5b-01'/(stem+'.json')).read_text())['row']
    with load_npy(base/'5b-01'/(stem+'.npz'), allow_pickle=False) as d:
        mask = d['injected_ticks'] >= round(8000/row['dt_ms'])
        events = np.column_stack((d['injected_ticks'][mask], d['injected_tubu_positions'][mask]))
        digest = hashlib.sha256(events.tobytes()).hexdigest()
    assert digest == row['injected_test_events_sha256']
    print(row['protocol'], 'final test injected events:', len(events), digest)
PY
```

## Test deadline disclosure

Commit `50e09e9` changed `src/flyonenomics/validation/level0_mech.py::check_0_16` from `run_isolated('measure_0_16', timeout_s=300)` to `run_isolated('measure_0_16')`. The latter uses the pre-existing **2,400 s** shared child-process budget. Two complete-suite attempts had raised `TimeoutExpired` at 300 s before returning numerical results. The unchanged isolated numerical check subsequently passed in **241.36 s**.

This is a **deadline change**, not a pass under the original 300 s deadline. All adaptation settings, exact-solution comparisons, spike equality, error tolerances, fixtures and assertions remain unchanged. The overall suite remains one process under **`timeout 5400`**. Gate attempts and final outcome are disclosed in the lane report; the timeout change needs review as such, and must not be used to imply that any scientific criterion was met by relaxing it.

## Synthetic validation — including the imperfect result

Exact algebraic fixtures return zero history effects for symmetric saturation, a fixed spatial preference and affine modulation without history. Known asymmetric suppression returns **H = 0.25**. An injected genotype shift returns **ΔH = 0.20** and its reversal **ΔΔH = −0.20**. A per-cell affine transform of a pre-existing history effect can change raw H; the exact affine residual is zero, to floating-point precision.

Noisy fixtures use 245 cells, sparse cells and Gamma–Poisson counts (variance `mean + mean²/10`), with 1,000 full-pipeline bootstrap refits per scenario; the experiment uses 10,000. Templates in these fixtures are known, not noisy biological calibrations. These are implementation checks, **not** power guarantees or a false-positive-rate study.

In the noisy known-shift example, the genotype estimate is **0.2175 [0.18672, 0.24617]**, and the difference-in-differences is **−0.22320 [−0.27149, −0.17343]**; both Holm p values are **0.00390625**. None of the other examples has a Holm-significant primary difference.

One noisy *affine-only, no-history* realisation nevertheless gives a nominal genotype interval excluding zero (Holm p **0.14453125**) and an affine-secondary residual **0.04127 [0.00604, 0.07784]** although its true residual is zero. This is retained, not hidden or used to tune the seed. Exact confound removal is not a guarantee against a noisy false positive. The secondary interval is not a new multiplicity-controlled finding, and ten seeds remain a bounded pilot.

Reproduce the chemistry, anatomy and synthetic numbers together, without an engine run, from the frozen code and adopted inputs:

```bash
FLYONENOMICS_CACHE_DIR=$HOME/flyo-cache .venv/bin/python scripts/adhd_study.py freeze --out camber-runs/adhd-study/recomputed-plan.json
```

At the generating commit recorded in the plan's `identity.commit`, on the Linux arm64 box, this reproduces the committed plan. Other commits/platforms change the recorded identity and can change last-bit arithmetic. For just the synthetic validation:

```bash
.venv/bin/python scripts/adhd_study.py synthetic --out camber-runs/adhd-study/synthetic.json
```

## One-arm cost and settle audit

The only new neural run was wild-type vehicle, position −50°, seed index 901: **22 brain-seconds** including settle. It ran on the box from `c7fdfb9`, before the later synthetic/provenance additions, and finished without an error. No ER response from it was used to choose the design.

| Measured quantity | Value |
|---|---:|
| Build | 89.87 s |
| Integration loop | 2,322.59 s |
| Total worker wall time | 2,418.77 s (40.31 min) |
| Peak resident memory | 7,281,872,896 bytes (7.28 GB; 6.78 GiB) |

With one persistent engine per seed, the projection is `build + arms_per_seed × (total − build)`. **At ten workers**, five arms per calibration seed project to **3.260 h**, and 32 arms per experiment seed to **20.726 h**. Totals are 1,100 and 7,040 brain-seconds respectively. Ten times the observed peak is 72.82 GB. This is an extrapolation from **one worker**, not a concurrent-throughput measurement; shared memory bandwidth and different firing under fumin can make the jobs longer. No timing was shortened.

During the 2 s blank settle, EB rose **0.0028112 µM** from its analytic 0.02 µM start. Across compartments, drift ranged from **−0.0007639 to +0.0028112 µM**. This is an audit, not an equilibrium test or a biological criterion. Every compartment's drift is in `validation/records/p2/adhd-study-cost.json`.

Raw files are in the ignored `camber-runs/adhd-study/probe-01/` on the Mac and `<compute-run-root>/camber-runs/adhd-study/probe-01/` on the box. The cost record binds both files by SHA-256, the executed source commit and runner hash, and the exact **probe-time** plan hash (not the later synthetic-validation plan).

Recompute the cost estimates and drift directly from the atomic seed file:

```bash
.venv/bin/python - <<'PY'
import json
from pathlib import Path
r = json.loads(Path('camber-runs/adhd-study/probe-01/seed-901.json').read_text())
b = r['build_wall_s']; t = r['total_wall_s']; a = r['rows'][0]
print('build, integration, total seconds:', b, a['wall_s'], t)
print('peak bytes:', r['peak_rss_bytes'])
print('hours at ten workers:', [(b + n * (t-b))/3600 for n in (5, 32)])
d = a['settle_pool_drift_um']
print('settle drift min, max, EB:', min(d), max(d), d[30])
PY
```

To repeat the *original* cost run, check out `c7fdfb9` on the box and use a new destination:

```bash
FLYONENOMICS_CACHE_DIR=$HOME/flyo-cache .venv/bin/python scripts/adhd_study.py probe --out camber-runs/adhd-study/probe-repeat
```

A repeat is **not** needed for Part A; this command is the reproducibility recipe, not an additional authorised run.

## Historical d-0023 run sequence — superseded by d-0025 above

Under d-0023 (retaining d-0019's original-calibration selection), after the full gate exits zero and the selection-only receipts above are present, on a clean pinned box checkout:

```bash
export FLYONENOMICS_CACHE_DIR=$HOME/flyo-cache
.venv/bin/python scripts/adhd_study.py pair --raw camber-runs/adhd-study/5a-01 --out validation/records/p2/adhd-study-pair.json
```

A prerequisite failure stops here and is reported with `ha waiting`. Otherwise commit the pair record **before**:

```bash
.venv/bin/python scripts/adhd_study.py 5b --workers 10 --pair validation/records/p2/adhd-study-pair.json --out camber-runs/adhd-study/5b-01
```

The unchanged idle full gate passed at `b6b5ccc`: **947 passed, 30 skipped**, exit 0, 4,433.22 s; subsequent pair/docs/records commits changed no bound source. **5b launched with ten workers from pair commit `e34ca13` at 2026-09-23 02:12:36 UTC.**

Once 5b is steady (all ten first-arm journals present), record the d-0023 headroom checks before the two-worker, nice-10 replay of seeds 101–102. Its batch dispatcher submits the same frozen `run_seed` jobs; it changes dispatch only, not `scripts/adhd_study.py` or any scientific parameter. The exact dispatcher source, SHA and commands are retained in `validation/records/p2/adhd-study-replay-dispatch.json`. Resource checks use `free -g`'s printed available value and conservatively require the maximum of 1/5/15-minute load averages to leave two `nproc` cores. The script rechecks these immediately before dispatch and records them; insufficient headroom exits 78 before any neural job.

```bash
# Materialise the recorded dispatcher, without altering the frozen runner:
.venv/bin/python -c "import json; from pathlib import Path; p=Path('camber-runs/adhd-study/replay-batch.py'); p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.loads(Path('validation/records/p2/adhd-study-replay-dispatch.json').read_text())['dispatcher_source'])"
# Only once 5b is steady and headroom permits (otherwise after 5b):
nice -n 10 .venv/bin/python camber-runs/adhd-study/replay-batch.py first-two
# Only after successful 5b completion, alongside analysis:
.venv/bin/python camber-runs/adhd-study/replay-batch.py remaining-eight
```

Both batches write disjoint seed files into `5a-02` and refuse to overwrite prior seed outputs. If headroom is insufficient, defer that batch until immediately after 5b. Seeds 103–110 run after 5b alongside the unchanged analysis:

```bash
.venv/bin/python scripts/adhd_study.py analyse --raw camber-runs/adhd-study/5b-01 --calibration camber-runs/adhd-study/5a-01 --pair validation/records/p2/adhd-study-pair.json --out camber-runs/adhd-study/provisional-5b-results.json
```

Do not report or promote the provisional result until **both seeds 101 and 102 pass the corrected audit and all ten of their NPZ files match byte-for-byte**. The remaining eight seeds are not the reporting gate under d-0023: report their verification when complete and flag any mismatch immediately. Record both batches separately in `validation/records/p2/adhd-study-5a-replay.json`.

Run these inside a detached box job, not a Mac-held SSH pipeline. A changed imported source or adopted input deliberately fails the plan binding: any review changes must be incorporated and re-frozen before stage 5a, without changing the design in response to neural outcomes.
