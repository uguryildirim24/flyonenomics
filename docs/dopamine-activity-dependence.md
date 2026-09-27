# Dopamine activity dependence

What the Phase 2 dopamine endpoints actually measure. Machine-readable summary:
`validation/records/p2/dopamine-activity-dependence.json`. All numbers below come
from the committed record `validation/records/p2/wp21-neural.json` and from the
run output under `camber-runs/wp21/` (t-0002's worktree, git-ignored). No engine
run was made for this note.

## Answer

The 3.2r to 3.5r dopamine values are the analytic fixed point of the dopamine
kinetics and the genotype. Neural activity contributes nothing to them except
three single-cell transients that are measurable at the 1e-3 µM level. The
merged pharmacology results are therefore correctness controls on the kinetics
module, not evidence about the brain.

This is not because the model cannot carry activity-driven dopamine. The
descending-PAM arm (3.6r) drives the innervated dopamine neurons at about
32 Hz and lifts the pool from 0.02 µM to about 7.4 µM. It is that the
spontaneous, dark conditions in which the drug experiments ran have no
innervated dopamine-neuron firing.

## The observation that started this

`wt_um` for `probe-2` and `probe-7` is bit-identical at `0.02` across all 37
anatomically distinct compartments, and `probe-12` is `0.02` in 33 of 37.
`fumin_um` is identical across all 37 in every probe. A connectome-driven field
cannot look like that unless the input is not a connectome signal.

## 1. The four deviating compartments in probe-12

The four are `EB`, `FB`, `NO_L` and `LAL_L`. They are exactly the complete
target set of one cell: the CX_DAN neuron `PPM1205`, engine index `107102`, root
`720575940632126860`. Its innervation column has weights

| compartment | weight |
|---|---|
| FB | 0.975309 |
| LAL_L | 0.015432 |
| NO_L | 0.006173 |
| EB | 0.003086 |

and no other compartment. It fires **one spike**, at `t = 2436.2 ms`, in the
`vehicle` arm, seed 2, probe 12 of the dose-p2 run. The deviations in that probe
are in exactly the ratios of those weights (FB ÷ 0.9753, EB ÷ 0.00309, and so
on), and only in those four compartments. No other compartment received a
spike from any innervated dopamine neuron in that probe, and no other CX_DAN
neuron fired anywhere in the recorded window of the whole wave.

That is the whole mechanism: `alpha_c` times `M @ counts`, where `M` is the
DAN/CX_DAN innervation matrix. With `alpha_c = 0.005333 µM/spike`, one spike on
a column whose FB weight is 0.975 adds about `0.0052 µM` to FB before clearance.
The other 33 compartments differ from `0.02` by exactly zero because nothing
that innervates them fired.

The four compartments are not distinguished by anything anatomical or dynamic
in themselves. They are distinguished only by being the targets of the one cell
that happened to spike.

## 2. The fixed point, analytically

The release law in `neuromod/calibration.py::rest_release_constants` is built so
that for every compartment

```
alpha_c = q / max(R_c, R_min)
S_c     = max(0, q - alpha_c * R_c)
```

with

```
q = DA_ref * ( Vmax / (Km + DA_ref) + k_ns ).
```

Both branches give the same total release:

- if `R_c >= R_min`: `alpha_c * R_c + S_c = q`;
- if `R_c < R_min`: `alpha_c * R_c + S_c = q/R_min * R_c + q - q/R_min * R_c = q`.

So the release that the fixed point sees is `q` for every compartment, whatever
the measured sustained rate `R_c` is. That is a property of the law, not of the
measurement. The committed file has `R_c = 0` for all 37 compartments (both the
clamped K2r measurement and the free-pool 3.1br measures), so `alpha_c =
q/R_min = 0.005333` and `S_c = q = 0.002667`, mode `source`.

The pool balance is

```
Vmax * da / (Km + da) + k_ns * da = q
```

and it has the closed form (the quadratic used in `neuromod/pools.py::fixed_point`)

```
da* = 2 q Km / (b + sqrt(b^2 + 4 k_ns q Km)),   b = Vmax + k_ns Km - q   (b >= 0)
```

with the `(sqrt(b^2 + 4 k_ns q Km) - b) / (2 k_ns)` branch when `b < 0`, and
`da* = q / k_ns` when `Vmax = 0`.

Constants from `data/params-v0.2.yaml`: `DA_ref = 0.02`, `Vmax = 0.11`,
`Km = 1.3`, `k_ns = 0.05`, `R_min = 0.5`, `Ki_mph = 0.2`, `EC50_3iy = 10`,
`pk.kappa = 0.01`, `pk.k_a = 0.5`. Then `q = 0.02 * (0.11/1.32 + 0.05) =
0.0026666666666666666 µM/s`.

| condition | source | closed form | value (µM) | recorded (µM) |
|---|---|---|---|---|
| wild type, no drug | `q` | root of `Vmax da/(Km+da)+k_ns da = q` | `0.02` | `0.02` |
| fumin, no drug | `q` | `q/k_ns` | `0.05333333333333333` | `0.05333333333333334` |
| wild type, 0.1 mM MPH food | `q` | root, `Km*(1+C_b/0.2)` | `0.037989169674944576` | same |
| wild type, 0.5 mM MPH | `q` | root | `0.0484631907095745` | same |
| wild type, 1.0 mM MPH | `q` | root | `0.050704812545102375` | same |
| wild type, 3 mM 3-IY | `q/(1+C_b/10)` | root | `0.006862099486803409` | same |
| fumin, 3 mM 3-IY | `q/(1+C_b/10)` | `src/k_ns` | `0.01841390658021888` | same |

`C_b = kappa * 1000 * c_food_mm * (1 - exp(-k_a * 2 h))` is the analytical brain
concentration after the two-hour wait of the matched protocol. `C_b` is 0.6321,
3.1606 and 6.3212 µM for 0.1, 0.5 and 1.0 mM MPH, and 18.9636 µM for 3 mM 3-IY.

The recorded methylphenidate and 3-IY values are these closed-form numbers to
the last bit. The one exception is `fumin_um = 0.05333333333333334` against a
fixed point of `0.05333333333333333`, a difference of `6.94e-18`: one unit in
the last place, i.e. floating-point rounding in `q/k_ns`, not a signal.

## 3. Activity-dependent fraction of each recorded endpoint

Because the measured `R_c` are all zero, any activity dependence must show up as
a deviation of the measured window mean from the fixed point. I compared every
recorded probe (98 arm/seed/probe rows across the four runs) with its
condition's fixed point.

| endpoint | recorded value | fixed point | activity-dependent fraction |
|---|---|---|---|
| 3.2r probe-2, all 37 comps | `0.02` (WT), `0.0533` (fumin) | same | `0` |
| 3.2r probe-7, all 37 comps | `0.02` (WT), `0.0533` (fumin) | same | `0` |
| 3.2r probe-12, 33 comps | `0.02` (WT) | `0.02` | `0` |
| 3.2r probe-12, EB | `0.02000239` | `0.02` | `1.20e-4` |
| 3.2r probe-12, NO_L | `0.02000479` | `0.02` | `2.39e-4` |
| 3.2r probe-12, LAL_L | `0.02001196` | `0.02` | `5.98e-4` |
| 3.2r probe-12, FB | `0.02075640` | `0.02` | `3.78e-2` |
| 3.3r vehicle, dose 0.1 / 0.5 | `0.02` | `0.02` | `0` |
| 3.3r vehicle, dose 1.0 | `0.02002096` | `0.02` | `1.05e-3` |
| 3.3r MPH, all doses | `0.0379892 / 0.0484632 / 0.0507048` | same | `0` |
| 3.3r fumin, all doses | `0.0533333` | same | `0` |
| 3.4r fumin MPH minus vehicle | `0.0` per seed | `0.0` | `0` |
| 3.5r wild-type vehicle | `0.02` | `0.02` | `0` |
| 3.5r fumin vehicle | `0.0533333` | same | `0` |
| 3.5r wild-type 3-IY | `0.0068621` | `0.0068621` | `0` |
| 3.5r fumin 3-IY seed 2,3 | `0.0184139` | `0.0184139` | `0` |
| 3.5r fumin 3-IY seed 1 | `0.0184575` | `0.0184139` | `2.37e-3` |
| 3.10r wild-type `DA_exposed` | `0.09553 Hz` | dopamine input `0.02` | `0` (input) |
| 3.10r fumin `DA_exposed` | `0.08333 Hz` | dopamine input `0.0533` | `0` (input) |
| 3.6r PAM minus baseline `DN_all` | `0.00908 Hz` | see below | firing-rate readout |

The three deviations are all the same cell. The `3.2r` probe-12 transient (which
the `3.3r` vehicle dose-1.0 row averages) traces to the one recording-window
spike of `107102`; the `3.5r` fumin 3-IY seed 1 and `descending-pam` baseline
seed 1 transients have **zero** innervated dopamine spikes in the recorded window
and are decaying transients left by a settle-phase spike of the same cell
(FB-dominated, decaying at the fumin `k_ns = 0.05 /s` and at the wild-type DAT
rate respectively). Among the spontaneous and drug arms, the section-2.4
diagnostic `da_gap_um` in the settle files flags exactly those three probes and
exactly the same four compartments; the ten PAM-arm probe settle files also flag
it, from the injected drive and in other compartments (section 4).

Spatial and seed variance:

- Every fixed-point dopamine quantity has **zero spatial variance** (identical
  across all 37 compartments) and **zero seed variance** (identical across
  seeds). The fumin field is also spatially uniform in every one of the 98 rows.
- Among the spontaneous and drug arms, the only spatial variance in a recorded
  dopamine field is the four compartments in the three transient probes above.
  The `3.6r` PAM arm is the exception: the injected drive makes its field
  spatially structured (ranging from `0.02` to about `30` µM across
  compartments), which is why it is the positive control.
- The 3.10r `DA_exposed` **firing rate** does vary by seed (per-seed differences
  from `-0.0148` to `-0.0097 Hz`), but that is a neural readout of a
  genotype-fixed dopamine input, not variation in the dopamine field.

Zero spatial and zero seed variance together are the strong statement: nothing
stochastic and nothing anatomical entered the dopamine values.

## 4. DAN firing rates in the committed runs

The 346 neurons with a nonzero column in the innervation matrix (316 DAN + 30
CX_DAN) are the only ones that can move dopamine. `DAN` fires at about 0.89 Hz
and `PPL1` at about 2.7 Hz in every spontaneous arm, but those firing cells are
among the 15 DANs whose hemibrain types are unplaced in `compartments-v0.1.yaml`,
so their `M` columns are empty. That is why the group rate is nonzero while the
weighted input to every compartment is zero. Counted directly from the spikes
parquet (`innervated_da_mean_rate_hz` = innervated spikes ÷ 346 ÷ recorded
seconds):

| run / arm | innervated DA spikes | innervated DA rate (Hz) | DAN (Hz) | PAM (Hz) | PPL1 (Hz) | CX_DAN (Hz) |
|---|---|---|---|---|---|---|
| coupling wild-type | 0 | 0 | 0.890 | 0.000 | 2.789 | 0.000 |
| coupling fumin | 0 | 0 | 0.887 | 0.000 | 2.749 | 0.000 |
| coupling dop1r1-null | 0 | 0 | 0.888 | 0.000 | 2.758 | 0.000 |
| depletion-3iy vehicle | 0 | 0 | 0.887 | 0.000 | 2.788 | 0.000 |
| depletion-3iy 3iy | 0 | 0 | 0.872 | 0.000 | 2.679 | 0.000 |
| depletion-3iy fumin | 0 | 0 | 0.886 | 0.000 | 2.754 | 0.000 |
| depletion-3iy fumin-3iy | 0 | 0 | 0.894 | 0.000 | 2.779 | 0.000 |
| descending-pam baseline | 0 | 0 | 0.880 | 0.000 | 2.698 | 0.000 |
| descending-pam pam | 549,582 | 31.77 | 34.03 | 36.16 | 0.980 | 0.000 |
| dose-p2 vehicle | 1 | 6.4e-5 | 0.891 | 0.000 | 2.808 | 0.0007 |
| dose-p2 mph | 0 | 0 | 0.891 | 0.000 | 2.740 | 0.000 |
| dose-p2 fumin | 0 | 0 | 0.887 | 0.000 | 2.756 | 0.000 |
| dose-p2 fumin-mph | 0 | 0 | 0.887 | 0.000 | 2.756 | 0.000 |

So the record's note is right at the aggregate level and slightly wrong at the
single-spike level: the innervated dopamine neurons are silent in the recorded
window of every spontaneous arm except for the one spike in dose-p2 vehicle. The
two settle-phase spikes are not in the spike census but are visible in the
dopamine trace and in `da_gap_um`.

## 5. The proposed control: not run

Steps 1 to 4 leave nothing open. The record already separates the two cases at
every endpoint: the drug and genotype conditions sit exactly on the analytic
fixed point, and the only deviations are the three transients from one
identified cell, with the model's own diagnostic confirming them. Removing
recurrent activity while retaining the source masks and kinetics would return
the same fixed points by construction, because the release law makes the
sustained source `q` independent of the measured rate. It would not add
information. No run was made.

For the record, the control would have had this logic: run the same fixtures
with the DAN/CX_DAN spikes removed but the tonic source and kinetics kept. A
result identical to the present endpoints would show the present endpoints carry
no activity; a result that moved would show activity-dependence that the record
missed. The finite, one-cell, 1e-3 µM signal already answers it, so the
ambiguity the consultant worried about does not arise here.

## 6. What this is and is not evidence of

- **It is** a correctness control on the kinetics and genotype module. It shows
  the dopamine kinetic equation, the DAT knockout, methylphenidate's `Km`
  change and 3-IY's release reduction are implemented consistently and produce
  the intended closed-form values.
- **It is not** a prediction the brain made. Fumin carrying over twice
  wild-type dopamine, methylphenidate raising dopamine dose by dose in wild
  type and doing nothing in fumin, and 3-IY lowering it in both are the encoded
  assumptions returning themselves.
- **It is not** evidence that the dopamine layer is inert. The PAM arm moves the
  field to about 7.4 µM. The flatness is a property of the spontaneous dark
  state (no innervated dopamine neuron firing), not of the architecture.
- The 3.6r and 3.10r endpoints are firing-rate readouts. They are downstream of
  the dopamine field and must not be reported as dopamine measurements.

If a ruling is wanted, it should say: the merged pharmacology results (3.2r to
3.5r) are correctness controls on the dopamine kinetics module, are not
circuit-level evidence, and must not be cited as a prediction of the model; the
3.6r PAM arm is a separate activity-driven stimulus and may be cited as the
positive control. I did not write a SPEC-P2 §10 item.

## Plain sentence

Our dopamine drug results only show that the model's dopamine equation and
genotype settings do what they were written to do: the drug experiments never
let the brain move dopamine, so they say nothing about how a fly's brain uses
dopamine.
