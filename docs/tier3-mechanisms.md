# Tier 3 structural rest mechanisms (WP24)

Development record of SPEC-P2 sections 2.2.4, 2.5, 2.6 step 6, 5.3 and 6.5.
Nothing here qualifies a rest substrate.

## Variant strings and methods

The `lif` strings are the bytes in `tests/fixtures/wp24-off-reference.json`.
The SPEC-P2 listing of `lif` documents them and takes no part in any test.

| `engine_model` | method | In force at G-3a |
|---|---|---|
| `lif` | `linear` | yes |
| `lif+sfa` | `linear` | yes |
| `lif+std` | `linear` | yes |
| `lif+cbi` | `rk4` | yes |

`lif` fixture hashes stay the 0.15 (b) values. A later commit that changes those bytes has failed the off-path contract.

## Engine interface

`Engine.build(..., mechanisms=None)` chooses the variant before any Brian2 object exists.
`None`, an omitted argument, or all-null `Mechanisms` blocks build `lif`.
`engine_model()`, `model_strings()`, `method()` and `mechanism_traces(since_tick)` are on the interface.
Under `lif` the trace table has no mechanism columns.

## Tests 0.15 to 0.18

| Test | Status | Largest error |
|---|---|---|
| 0.15 (a)–(c) | pass on the G-3a engine commits | recorded in the WP24 report |
| 0.15 (d) | loader, masks, `substrate_id_for`, identity | no engine |
| 0.16 | pass (`lif+sfa` closed form) | recorded in the WP24 report |
| 0.17 | pass (`lif+std` closed form) | err_v and err_x at most 1e-9 |
| 0.18 | pass (`lif+cbi` vs DOP853) | (b) err_v 2.1e-11, err_h 6.0e-10 |

## B-mech

B-mech runs once per engine model with a mechanism, as `scripts/bench.py --mech sfa|std|cbi`.
The record is `validation/records/p2/bench-mech-<tag>.json`.
ρ_mech is the largest ratio, over W1 and W2 and both on-settings, of median warm wall per brain s with the mechanism on to the median with it off, and at least 1.0.

| Tag | engine_model | ρ_mech | Record |
|---|---|---:|---|
| sfa | `lif+sfa` | 1.486 | `validation/records/p2/bench-mech-sfa.json` |
| std | `lif+std` | 1.346 | `validation/records/p2/bench-mech-std.json` |
| cbi | `lif+cbi` | 1.234 | `validation/records/p2/bench-mech-cbi.json` |

ρ_mech 1.486 (sfa), 1.346 (std) and 1.234 (cbi) are below 1.5. They are not a stop.

## Sub-tier 3a (`lif+sfa`)

Plan: `validation/records/p2/rest-T3a-plan.json`.
ρ_mech 1.4863463034318214 (the B-mech value). B = 67 brain s. T0: 192 units (180 + 12 baseline), 5 jobs, 197 tasks, 11,820 brain s. Cap projection at T0 with no T1 units: 240.6 engine-hours, under 400.
T0, T1 and T2 summaries land after Camber returns.

## Sub-tier 3b (`lif+std`)

Plan: `validation/records/p2/rest-T3b-plan.json`.
ρ_mech 1.3459778442507917 (the B-mech value). B = 74 brain s. T0: 180 units, 5 jobs, 185 tasks, 11,100 brain s. Cap projection at T0 with no T1 units: 210.6 engine-hours, under 400. `launch` is true.
The 3b search starts only when 3a ends empty.

## Sub-tier 3c (`lif+cbi`)

Plan: `validation/records/p2/rest-T3c-plan.json`.
ρ_mech 1.2336139268858282 (the B-mech value). B = 81 brain s. T0: 45 units, 1 job, 46 tasks, 2,760 brain s. Cap projection at T0 with no T1 units: 115.8 engine-hours, under 400. `launch` is true.
The 3c search starts only when 3b ends empty.

## Sub-tier 3d (KC-targeted APL inhibition)

No new engine variant. `g_gaba_kc` multiplies GABA→KC rows on the `scale_array` / `set_weight_scale` path. `gain_i` is untouched. `g_gaba_kc` 1 is byte-identical to omitting the factor.
Plan: `validation/records/p2/rest-T3d-plan.json`. ρ_mech 1.0 (no B-mech). 24 units. T0 and T1 pack into one IBM wave at 45.75 worker-s per brain s, 36 workers, 600 s setup, three boxes at most. T1 slice width uses 75 worker-s per brain s (IBM t3b-t1-00 10 s probes) so one task fits the 9000 s timeout. Cap projection 259 of 400. Status: GO WP26. Item 74 rejudges T2 (a)/(b) at 0.5/0.4 of the same-job bare difference without changing the written 40/50 Hz floors.
The 3d search starts only when 3c ends empty.

## Call-site table

Writers of `substrate_id` go through `drive/mechanisms.substrate_id_for`.
The WP24 report lists every call site.
`drive/rest_calibration.py` landed on main with WP19 and is on this tree after `fac5664`.
