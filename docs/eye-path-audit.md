# Eye-path reconciliation audit

Three arithmetic checks on the committed voltage probe in
`validation/records/p2/signal-transfer-audit.json` (merged r30). No engine
run, no new simulation. The evidence is `validation/records/p2/eye-path-audit.json`
and the runner is `scripts/eye_path_audit.py`.

The checks were proposed by an outside consultant against our own probe. Two
come back clean. The third is a real limitation of the declared model and is
quantified, not repaired.

## Check 1: the gap numbers reconcile against the composed threshold, not against -45 mV

The probe records TuBu-path targets at a -52.01 mV baseline with a 7.02 to
7.26 mV gap to threshold, while the declared threshold is -45 mV and the
declared rest is -52 mV (a 7.01 mV gap). The excess is the **runtime composed
threshold**, not a substrate defect.

**The substrate carries no threshold spread.** For `rest:379cc4cc9030cdd1`
(`1.0-4.0-0.0-False-100-1.0-kc-6.0-sens`) the base threshold array the engine
builds is one value, -45.0 mV, over all 138,639 cells. The drive file has
`threshold: null` (`data/drive-v0.2.yaml:52`), so `sigma_th` is 0.0, and
`apply_rest_substrate` returns `np.full(neurons, v_th)` unchanged
(`src/flyonenomics/drive/rest.py:628-630`). The no-spread field in the
substrate string is the `0.0` (`sigma_th`); the `False` is `optic_exemption`.

**The runtime threshold varies, and the dopamine layer causes it.** The engine
runs with `Neuromod.compose`, which adds the receptor term `d_v` to the base
threshold (`src/flyonenomics/neuromod/state.py:303`), and `d_v` comes from the
composed dopamine receptor occupancy (`src/flyonenomics/neuromod/receptors.py:18`).
At the dark fixed point the composed array has 30 distinct values, all between
-45.0148 and -44.4286 mV, confined to dopamine-exposed central cells:

| Composed threshold | Cells | Population |
|---:|---:|---|
| -45.000000 | 132,501 | not exposed / zero receptor effect |
| -44.743697 | 5,177 | Kenyon cells |
| -44.743697 | 368 | CX |
| -44.437395 | 316 | DAN |
| -45.014706 | 153 | CX |
| -44.728992 | 92 | MBON |
| -44.428571 | ~35 | CX and a few unlabelled cells |

6,138 of the 8,725 dopamine-exposed cells carry a nonzero `d_v`. All 64 traced
**eye** targets sit at exactly -45.0 mV; they are optic or sensory cells with no
dopamine exposure. On the **TuBu** path 57 of the 64 targets sit at
-44.743697 mV and 7 at -45.0 mV.

**The recorded gap uses this composed threshold.** The probe computes
`mean_distance_to_threshold_mV` as `threshold_mean - sampled_mean_v`
(`scripts/audit_signal_transfer.py:488-491,507,520`). On the TuBu input-off
condition: baseline mean -52.0072 mV (range -52.1669 to -51.9768), threshold
-44.743697 mV for 171 of 192 target-seed rows and -45.0 mV for 21, recorded gap
mean 7.2355 mV (7.0160 to 7.2563). A gap against exactly -45.0 would be
7.0072 mV. The recorded numbers are internally consistent.

**Verdict.** No defect in the substrate declaration or its construction, and
the substrate id's spread field is not misleading. The audit's "gap" is a gap
to the composed threshold and should be stated that way. No merged result
depends on the answer: the shift is at most 0.57 mV, every traced eye target is
more than 8 mV from threshold, and the TuBu conclusions rest on the presence or
absence of spikes, not on the last fraction of a millivolt.

## Check 2: the photoreceptor drive reconstructs from the instantiated weights

The engine's LIF model relaxes to `v = v_0 + g` with `dv/dt = (v_0 - v + g)/t_mbr`
and `dg/dt = -g/tau` (`src/flyonenomics/engine/models.py:14-20`). For a
stationary presynaptic rate the mean synaptic variable is `sum_i w_ij r_i tau`.
With `tau` = 5 ms and `v_0` = -52 mV, the predicted mean voltage is

```
v_pred = -52 + source_event_sum / 2 s * 0.005 s
```

where `source_event_sum` is `sum_i w_ij n_i`, the **connection-weighted** event
sum recorded per target. It is not the pooled R1-6 population rate.

Over all 64 eye targets, both conditions and three seeds (384 rows):

| Reconstruction residual, measured - predicted | mV |
|---|---:|
| mean | -0.0003 |
| standard deviation | 0.0445 |
| minimum | -0.166 |
| maximum | +0.131 |

The largest residual is 0.166 mV. Relative to each target's own drive, the
largest is 1.5%, on a shallow target whose drive is only about 11 mV; five of
the 384 rows exceed 1%. The residual is the membrane low-pass plus
measurement-window boundary, not a missing term.

**Weights are applied once.** Recomputing every traced target's effective
weight sum and anatomical synapse total straight from the raw connectome
arrays and the composed scale array reproduces the committed static rows
exactly: maximum difference 0.0 mV and 0 synapses over all 64 targets. The path
is `effective = raw_count * lif.w_syn * scale_array(...)` — count, `w_syn` and
the transmitter multiplier each enter once. A doubled count or multiplier would
double the deepest target's -57.9 mV drive to -115.8 mV (about -168 mV at the
membrane), not produce the observed -110 mV.

**The pooled substitution the task warns about is worse.** Using the per-target
weight sum times the unweighted mean rate of the connected source cells gives
residuals with standard deviation 0.284 mV and maximum 0.94 mV, six times the
connection-weighted residual. The record correctly uses the connection-weighted
sum.

**Verdict.** The implementation delivers the current it specifies. This does
not establish that the current is right — only that no count or multiplier is
mis-applied.

## Check 3: the -110 mV tail has no reversal potential

The declared engine adds a fixed signed synaptic current with no reversal. The
deepest traced eye target (engine index 130021) has a connection-weighted drive
of -57.88 mV, a sampled mean of -109.87 mV and a sampled minimum of -121.52 mV
against a -45 mV threshold.

The project's only conductance reversal constants are the tier-3 placeholders
-72, -62 and -57 mV (`data/rest-tier3-v0.2.yaml:47`, SPEC-P2 item 31). Under
the `lif+cbi` formulation (`SPEC-P2` section 3c) the same inhibitory events
produce a conductance `h_ss = |drive| / (v_0 - E)` and steady state
`v = (v_0 + h_ss E) / (1 + h_ss)`, which cannot pass `E`:

| E_Cl | h_ss | steady v | shift from current | deepest min below E |
|---:|---:|---:|---:|---:|
| -72 mV | 2.89 | -66.86 mV | +43.0 mV | 49.5 mV |
| -62 mV | 5.79 | -60.53 mV | +49.3 mV | 59.5 mV |
| -57 mV | 11.58 | -56.60 mV | +53.3 mV | 64.5 mV |

Across all 64 targets the deepest mean (-109.87 mV) is 37.9 to 52.9 mV below
the reversal range and the deepest sample (-121.52 mV) is 49.5 to 64.5 mV
below it. The conductance steady-state shift ranges from 1.4 to 43.0 mV at
E = -72, 2.2 to 49.3 mV at -62 and 3.3 to 53.3 mV at -57. The cost is largest
exactly where the current model looks most dramatic.

This is a written analysis only. No engine, substrate or record was changed.
Whether to adopt a conductance formulation is Rolf's decision and is not
proposed here.

## What the three checks establish, and what they do not

1. **Thresholds: clean, with a caveat.** The substrate has no threshold spread;
   the -44.7437 mV rows are the dopamine A layer's `d_v`. It does not show the
   substrate id is wrong, and no result flips if the shift is removed.
2. **Drive: reproduces.** The implementation delivers the specified current
   with counts and multipliers applied once. It does not show the specified
   current is biologically right.
3. **Tail: real model limitation.** The current formulation drives the deepest
   targets 38 to 65 mV below any plausible chloride reversal; a conductance
   formulation would stop them at the reversal. This is an analysis, not a
   measurement of chloride reversal, and it does not recommend a change.
