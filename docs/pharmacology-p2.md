# Pharmacology and ADHD manipulations (WP21)

This page describes historical FlyWire work, not MaleCNS results. The retained
planner and validators still require their original inputs. Some inputs and
raw archives are absent from the public snapshot. Plans do not establish
completed experiments. See [REPRODUCE.md](../REPRODUCE.md).

Phase 2 keeps the layer A and C equations, the drugs and the pharmacokinetics. It adds seven named genotypes and the retained neural pharmacology fixtures. This document records the files and the rules. It does not change a constant.

## Named genotypes

`schema/named.py` expands eleven names. The Phase 1 four keep their definitions.

| Name | Expansion |
|---|---|
| `wild_type` | none |
| `fumin` | `scale_dat all 0` |
| `dat_half` | `scale_dat all 0.5` |
| `dopamine_depleted` | `scale_release 0.5` |
| `dop1r1_null` | `scale_receptor D1 all 0` |
| `dop2r_null` | `scale_receptor D2 all 0` |
| `dan_autoreceptor_null` | `scale_receptor D2 DAN 0`, `scale_receptor D2 CX_DAN 0` |
| `er_dop1r1_kd` | `scale_receptor D1 ER 0` |
| `pam_silenced` | `silence PAM` |
| `cx_dan_silenced` | `silence CX_DAN` |
| `dfb_silenced` | `silence dFB` |

Schema 1.3 accepts the seven new names; `schema/named.py` expands them and `Genotype.expanded()` returns their hooks. Experiment JSON files use `schema_version` `"1.3"`.

## Contrasts

`analysis/contrasts.py` retains only the paired difference, bootstrap interval and ANALYSIS-stream helpers used by the measured neural entries. The P-screen-only status tables, rescue index and genotype selector were removed with the skipped screen.

## Experiment files

All files live in `data/experiments/p2/`. The retained 3.8r ablation exists in `-buridan` and `-openloop` forms. Neural fixtures use a 20 s or 5 s dark `spontaneous` probe.

| File | Role |
|---|---|
| `pharm-411-openloop.json` | source fixture named by the measured power-pilot record; not a future 4.11 run |
| `ablation-p2-*.json` | 3.8r 2×2 factorial |
| `coupling.json` | 3.10r, wild type, fumin, `dop1r1_null` |
| `coupling-sweep.json` | 3.9r coupling part, wild type and fumin |
| `dose-p2.json` | 3.3r and 3.4r, four arms, 0.1/0.5/1.0 mM |
| `depletion-3iy.json` | 3.5r, dark spontaneous 3-IY |
| `descending-pam.json` | 3.6r PAM 50 Hz arm |

The four P-screen fixtures and four canonical prediction fixtures were removed under item 144. `pharm-411-openloop.json` stays because `validation/records/p2/pscreen-power.json` and its collector name it as the pilot's source fixture.

## Plan check

`tests/test_p2_plan_pharm.py` expands the files without `scripts/bench.py --plan` (WP19). Brain s use `budget.plan_settle_s` 2 s.

| Row | Brain s |
|---|---|
| 3.9r dose (27 settings) | 6,804 |
| 3.9r coupling (15 settings) | 6,600 |

3.9r dose settings are the Phase 1 27. Coupling settings are the 15 distinct no-drug points: `Kd_D1`, `Kd_D2`, `gamma_*`, `dV_*`, `Vmax`, `Km`, `k_ns` at low and high, plus default once. `Ki_mph` and `kappa` do not enter the coupling sweep.

## Entries

`validation/level3_p2.py` holds 3.2r to 3.10r and 4.9 to 4.11. Every entry binds item 122's declared resting substrate (the sensory-only arm at 1.0 mV, `1.0-4.0-0.0-False-100-1.0-kc-6.0-sens`) read from `rest-T3e-decision.json` and `rest-T3e-freeze-partial.json`. Entries 4.9, 4.10 and 4.11 have the terminal outcome `not run`, with SPEC-P2 item 144 as their reason. They are not populated from the power pilot. Every retained experiment file carries the declared unit in `meta.declared_substrate`.

If 3.10r fails, coupling is failed. Section 4.7 then reports 3.9r's smallest in-range change of `gamma_*`, `dV_*`, `Kd_D1` and `Kd_D2` that makes the 3.10r interval exclude zero. No constant changes without Rolf.

## What waits

WP15 owns schema 1.3, `DA_exposed`, loaders and the rest-substrate plumbing, and it is on main. WP19 owns the rest calibration and the dopamine/drive commits; item 123 commits the canonical `data/drive-v0.2.yaml`. WP20 records the visual status and commits `behaviour-v0.2.yaml` with `controller: open_loop` (r27). The retained entries that still wait are the 3.8r factorial and 3.9r sensitivity runs. `scripts/camber/pharm.py --plan` prints only the 3.9r rows and names the declared unit.

Phase 1 items 56, 60, 61 and 62 stay on the bare substrate. The `r` entries here are separate rest-substrate entries.
