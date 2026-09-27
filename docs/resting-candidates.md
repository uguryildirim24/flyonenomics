# Resting candidates — WP17

Tier-1 development search complete: R1 admitted nine candidates; all nine failed
Mac R-reflex. **Ranked list: empty. Shortlist: empty.** R-long was correctly not
run. SPEC-P2 section 2.6 step 4 triggered tier 2 on **(3,6), (3,8), (4,2)**, which
ran on Camber on 2026-09-16. Tier 2 also left the ranked list empty: **P2-partial-B**
(escalation below, final).

<!-- escalation:begin -->
## Escalation — SPEC-P2 2.6 step 5 (FINAL)

**Decision: P2-partial-B, "no rest substrate".** Tier 1 left the ranked list empty at R-reflex, which triggered tier 2 on
(3,6), (3,8) and (4,2) (section 2.6 step 4). Tier 2 screened all 51 settings, and all 20 tier-wide
admissions were measured through R-reflex. Across both tiers 29 candidates in the decision sets
were measured through R-reflex (9 tier 1, 20 tier 2); 0
passed, so none reached R-long. **Ranked list `[]`, shortlist `[]`.** No candidate is released
to R3, no `drive-v0.2.yaml` is written, and the bare substrate stays canonical.

The coordinator put the section 2.6 step 5 question (tier 3, relax a named criterion, or stop) to Rolf. **Rolf authorised tier 3** (section 2.2.4). **WP24 is complete.** Ranked list empty. Shortlist empty. The bare substrate stays canonical. **P2-partial-B holds.**

Why tier 2 could not rescue R-reflex (c): the feed-forward probe runs with background off and base thresholds, so
σ_th and n_bg cannot change it, and optic exemption left the rows identical where measured ((3,6), (3,8)).
Extended retention is therefore a property of the scale pair: 0.0018 for (3,6) and (3,8), 0.0 for (4,2),
against a 0.5 floor. Every tier-2 admission sits on one of those pairs. Why the scaling abolishes the
reflex is in `.reports/WP17-report.md`, section "Why inhibitory scaling abolishes the reflex".

| Stage | Tier 1 | Tier 2 |
|---|---:|---:|
| candidates scored by R-screen | 204 | 867 |
| R-screen passers | 9 | 153 |
| measured through R-reflex (admitted) | 9 | 20 |
| R-reflex passed | 0 | 0 |
| R-long passed | 0 | 0 |
| admitted, R-reflex pending | 0 | 0 |
| not tested (cap) | 0 | 125 |
| measured beyond the cap (not in decision) | 0 | 8 |

**Closest-miss score.** S sums the section 2.6 violations. It is complete only for candidates measured
through R-reflex. For R-screen failures and for passers not yet measured it omits the reflex terms, so it is
a lower bound and does not compare with a complete S. The tables therefore group candidates by the deepest
stage reached and sort by the order key within each group. Values are worst case over seeds and both pair
members: F, b and the stability ratio over the six pair rows; central, DAN and KC as the range of the two
pair means; gradedness as the largest next-point/pair central ratio; reflex (a) the lowest seed
difference, (b) the mean difference, (c) the extended retention.

**Development substrate.** Step 5 allows the lowest candidate by order key to be written as
`data/drive-dev-p2.yaml`. I apply it to candidates with complete S (measured through R-reflex, tier 1 and
tier 2 pooled, the decision set only): **3.0-6.0-1.0-False-25-3.4** (tier 2,
S 8.8668, J 16.101, failed R-reflex (a, b, c)).
It is class development and qualifies nothing.
Its configuration commit is separate from this evidence, per the section 2.5 freeze protocol.

### Candidates measured through R-reflex

| Tier | g_gaba | g_glu | σ_th mV | optic exempt | n_bg | w_bg mV | F max | b max | stability min–max | central Hz | DAN Hz | KC Hz | gradedness max | (a) min Δ Hz | (b) mean Δ Hz | (c) ext. retention | S | J | Failed step |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 2 | 3.0 | 6.0 | 1.0 | off | 25 | 3.4000 | 2.135 | 0.0026 | 0.987–1.010 | 3.93–4.24 | 0.67–0.85 | 1.42–1.52 | 1.16 | 0 | 14.1 | 0.0018 | 8.8668 | 16.101 | R-reflex (a, b, c) |
| 2 | 3.0 | 8.0 | 2.0 | on | 25 | 3.0000 | 1.995 | 0.0032 | 0.985–1.024 | 3.82–4.07 | 0.77–0.95 | 1.35–1.43 | 1.14 | -28 | 12.7 | 0.0018 | 8.9713 | 15.554 | R-reflex (a, b, c) |
| 2 | 3.0 | 6.0 | 2.0 | off | 25 | 3.0000 | 2.048 | 0.0027 | 0.993–1.005 | 4.09–4.36 | 0.80–0.98 | 1.42–1.49 | 1.14 | -53 | 12.5 | 0.0018 | 8.9872 | 15.706 | R-reflex (a, b, c) |
| 2 | 3.0 | 8.0 | 2.0 | off | 25 | 3.0000 | 2.081 | 0.0027 | 0.988–0.997 | 3.81–4.07 | 0.78–0.96 | 1.33–1.41 | 1.14 | -3 | 11.0 | 0.0018 | 9.1150 | 14.914 | R-reflex (a, b, c) |
| 2 | 3.0 | 8.0 | 2.0 | off | 400 | 0.2125 | 2.788 | 0.0026 | 0.982–1.013 | 3.64–3.85 | 0.58–0.70 | 1.38–1.46 | 1.12 | -49 | 7.3 | 0.0018 | 9.5251 | 15.605 | R-reflex (a, b, c) |
| 2 | 3.0 | 6.0 | 2.0 | on | 25 | 2.8000 | 2.060 | 0.0028 | 0.985–1.012 | 3.85–4.08 | 0.64–0.78 | 1.34–1.40 | 1.13 | -49 | 6.9 | 0.0018 | 9.5814 | 15.948 | R-reflex (a, b, c) |
| 2 | 3.0 | 8.0 | 2.0 | on | 25 | 2.8000 | 2.141 | 0.0029 | 0.985–1.009 | 3.60–3.82 | 0.63–0.77 | 1.28–1.35 | 1.14 | 6 | -9.0 | 0.0018 | 9.7212 | 15.258 | R-reflex (a, b, c) |
| 2 | 3.0 | 8.0 | 2.0 | off | 100 | 0.8500 | 2.384 | 0.0027 | 0.985–1.011 | 3.80–4.04 | 0.70–0.84 | 1.42–1.49 | 1.13 | -16 | 5.6 | 0.0018 | 9.7902 | 15.440 | R-reflex (a, b, c) |
| 2 | 3.0 | 6.0 | 2.0 | off | 100 | 0.8000 | 2.450 | 0.0025 | 0.996–1.012 | 3.87–4.09 | 0.61–0.72 | 1.43–1.50 | 1.13 | -44 | 4.8 | 0.0018 | 9.9443 | 15.884 | R-reflex (a, b, c) |
| 2 | 3.0 | 8.0 | 2.0 | off | 100 | 0.8000 | 2.487 | 0.0024 | 0.985–1.015 | 3.60–3.80 | 0.59–0.70 | 1.36–1.42 | 1.13 | -40 | 4.0 | 0.0018 | 10.1266 | 15.734 | R-reflex (a, b, c) |
| 1 | 3.0 | 6.0 | 0.0 | off | 100 | 1.1500 | 2.652 | 0.0033 | 0.985–1.017 | 4.39–4.79 | 0.76–0.97 | 1.78–1.87 | 1.19 | 0 | 3.7 | 0.0018 | 10.2046 | 18.903 | R-reflex (a, b, c) |
| 2 | 3.0 | 8.0 | 2.0 | off | 25 | 2.8000 | 2.193 | 0.0024 | 0.992–1.016 | 3.58–3.81 | 0.63–0.78 | 1.26–1.33 | 1.14 | -16 | 2.5 | 0.0018 | 10.5966 | 14.899 | R-reflex (a, b, c) |
| 2 | 3.0 | 8.0 | 0.0 | off | 25 | 3.6000 | 2.089 | 0.0027 | 0.983–1.012 | 3.70–4.00 | 0.66–0.83 | 1.41–1.50 | 1.18 | -16 | 2.4 | 0.0018 | 10.6375 | 15.779 | R-reflex (a, b, c) |
| 1 | 3.0 | 8.0 | 0.0 | off | 100 | 1.2000 | 2.554 | 0.0035 | 0.991–1.011 | 4.46–4.84 | 0.93–1.22 | 1.78–1.88 | 1.18 | 1 | 2.4 | 0.0018 | 10.6375 | 20.196 | R-reflex (a, b, c) |
| 2 | 3.0 | 8.0 | 1.0 | off | 25 | 3.4000 | 2.154 | 0.0026 | 0.988–1.014 | 3.66–3.94 | 0.65–0.82 | 1.33–1.41 | 1.17 | -28 | 1.9 | 0.0018 | 10.8711 | 15.492 | R-reflex (a, b, c) |
| 1 | 3.0 | 8.0 | 0.0 | off | 100 | 1.2500 | 2.591 | 0.0040 | 0.991–1.004 | 4.84–5.24 | 1.22–1.58 | 1.88–1.94 | 1.17 | -3 | 1.8 | 0.0018 | 10.9251 | 22.456 | R-reflex (a, b, c) |
| 2 | 3.0 | 6.0 | 2.0 | off | 400 | 0.2125 | 2.811 | 0.0026 | 0.997–1.008 | 3.92–4.14 | 0.59–0.70 | 1.47–1.54 | 1.12 | -52 | 1.4 | 0.0018 | 11.1765 | 15.830 | R-reflex (a, b, c) |
| 1 | 3.0 | 6.0 | 0.0 | off | 100 | 1.2000 | 2.393 | 0.0037 | 0.984–1.017 | 4.79–5.22 | 0.97–1.26 | 1.87–1.96 | 1.19 | 0 | 1.4 | 0.0018 | 11.1765 | 21.029 | R-reflex (a, b, c) |
| 2 | 3.0 | 6.0 | 2.0 | off | 25 | 2.8000 | 2.141 | 0.0026 | 0.994–1.006 | 3.85–4.09 | 0.64–0.80 | 1.33–1.42 | 1.14 | -53 | -6.0 | 0.0018 | 11.5129 | 15.672 | R-reflex (a, b, c) |
| 2 | 3.0 | 8.0 | 2.0 | on | 100 | 0.8000 | 2.668 | 0.0029 | 0.967–1.046 | 3.61–3.82 | 0.58–0.68 | 1.36–1.43 | 1.13 | -59 | -10.8 | 0.0018 | 11.5129 | 15.723 | R-reflex (a, b, c) |
| 2 | 3.0 | 8.0 | 0.0 | on | 25 | 3.4000 | 2.420 | 0.0027 | 0.987–1.021 | 3.41–3.70 | 0.52–0.65 | 1.32–1.40 | 1.19 | -16 | -3.4 | 0.0018 | 11.5129 | 15.935 | R-reflex (a, b, c) |
| 2 | 3.0 | 8.0 | 1.0 | on | 25 | 3.4000 | 2.160 | 0.0031 | 0.993–1.022 | 3.67–3.98 | 0.64–0.84 | 1.34–1.45 | 1.17 | -29 | -5.2 | 0.0018 | 11.5129 | 15.831 | R-reflex (a, b, c) |
| 2 | 3.0 | 8.0 | 2.0 | off | 400 | 0.2250 | 2.766 | 0.0028 | 0.988–1.013 | 3.85–4.07 | 0.70–0.81 | 1.46–1.53 | 1.12 | -49 | -12.4 | 0.0018 | 11.5129 | 15.792 | R-reflex (a, b, c) |
| 2 | 3.0 | 6.0 | 1.0 | on | 25 | 3.4000 | 2.237 | 0.0032 | 0.988–1.009 | 3.94–4.24 | 0.67–0.85 | 1.42–1.50 | 1.16 | -25 | -2.4 | 0.0018 | 11.5129 | 16.214 | R-reflex (a, b, c) |
| 1 | 3.0 | 8.0 | 0.0 | off | 100 | 1.1000 | 2.995 | 0.0029 | 0.995–1.022 | 3.75–4.09 | 0.57–0.72 | 1.60–1.69 | 1.19 | -36 | -7.0 | 0.0018 | 11.5129 | 17.984 | R-reflex (a, b, c) |
| 1 | 3.0 | 8.0 | 0.0 | off | 100 | 1.1500 | 2.516 | 0.0032 | 0.995–1.011 | 4.09–4.46 | 0.72–0.93 | 1.69–1.78 | 1.19 | -10 | 0.1 | 0.0018 | 11.5129 | 18.214 | R-reflex (a, b, c) |
| 1 | 4.0 | 2.0 | 0.0 | off | 100 | 1.4000 | 2.244 | 0.0058 | 0.994–1.003 | 7.12–7.63 | 2.62–3.13 | 1.24–1.28 | 1.15 | -1 | 0.6 | 0.0000 | 11.5129 | 33.109 | R-reflex (a, b, c) |
| 1 | 4.0 | 3.0 | 0.0 | off | 100 | 1.4500 | 2.282 | 0.0059 | 0.995–1.007 | 7.09–7.56 | 2.88–3.46 | 1.34–1.39 | 1.14 | 0 | 1.0 | 0.0000 | 11.5129 | 33.799 | R-reflex (a, b, c) |
| 1 | 4.0 | 4.0 | 0.0 | off | 100 | 1.5000 | 2.698 | 0.0067 | 0.995–1.008 | 7.19–7.63 | 3.36–4.01 | 1.43–1.51 | 1.13 | 0 | 1.0 | 0.0000 | 11.5129 | 35.238 | R-reflex (a, b, c) |
| 2 | 3.0 | 6.0 | 1.0 | on | 25 | 3.2000 | 2.263 | 0.0026 | 0.988–1.009 | 3.67–3.94 | 0.53–0.67 | 1.33–1.42 | 1.16 | -21 | 12.3 | 0.0018 | 9.0033 | 16.389 | measured beyond cap (not in decision) |
| 2 | 3.0 | 8.0 | 1.0 | on | 25 | 3.2000 | 2.350 | 0.0027 | 0.992–1.014 | 3.42–3.67 | 0.52–0.64 | 1.27–1.34 | 1.17 | -29 | -6.2 | 0.0018 | 11.5129 | 16.230 | measured beyond cap (not in decision) |
| 2 | 3.0 | 8.0 | 2.0 | off | 25 | 3.2000 | 2.034 | 0.0030 | 0.988–1.019 | 4.07–4.33 | 0.96–1.17 | 1.41–1.50 | 1.14 | -36 | -5.3 | 0.0018 | 11.5129 | 16.173 | measured beyond cap (not in decision) |
| 2 | 3.0 | 8.0 | 2.0 | on | 400 | 0.2250 | 2.981 | 0.0033 | 0.988–1.011 | 3.86–4.09 | 0.69–0.82 | 1.49–1.57 | 1.13 | -45 | -2.7 | 0.0018 | 11.5129 | 16.012 | measured beyond cap (not in decision) |
| 2 | 3.0 | 6.0 | 0.0 | off | 25 | 3.4000 | 2.227 | 0.0023 | 0.990–1.016 | 3.66–3.95 | 0.54–0.68 | 1.38–1.48 | 1.17 | -46 | -5.3 | 0.0018 | 11.5129 | 16.278 | measured beyond cap (not in decision) |
| 2 | 3.0 | 6.0 | 0.0 | off | 25 | 3.6000 | 2.099 | 0.0027 | 0.995–1.002 | 3.95–4.29 | 0.68–0.86 | 1.48–1.56 | 1.18 | -46 | -6.8 | 0.0018 | 11.5129 | 16.266 | measured beyond cap (not in decision) |
| 2 | 3.0 | 8.0 | 2.0 | on | 100 | 0.8500 | 2.482 | 0.0032 | 0.967–1.002 | 3.82–4.07 | 0.68–0.85 | 1.43–1.51 | 1.14 | -59 | -6.7 | 0.0018 | 11.5129 | 16.411 | measured beyond cap (not in decision) |
| 2 | 3.0 | 6.0 | 0.0 | on | 25 | 3.4000 | 2.448 | 0.0028 | 0.985–1.012 | 3.67–3.97 | 0.55–0.69 | 1.39–1.47 | 1.17 | -30 | -8.3 | 0.0018 | 11.5129 | 16.525 | measured beyond cap (not in decision) |

Record: `validation/records/p2/rest-escalation.json` (inputs by SHA-256; every candidate row). The full closest-miss table of all
1071 candidates is the appendix at the end of this document.
<!-- escalation:end -->

## R1 starting set (SPEC-P2 2.6)

The map at `270ea43` used connection-file transmitter classes and layer A off.
Its eight sign-labelled passers represent four scale pairs. Histamine and model
signs have identical dark metrics; only the model copy is imported. The raw map
source is job **27163**, commit **4e0220f81a08bd50e78dcc686aa5d51c6bba4558**,
code_scope **4e0220f**, platform **camber-large**, class **development**.

The reproducible selection plan is `validation/records/p2/rest-map-plan.json`.
For every pair it scores all 17 possible adjacent candidate weights using
section 2.6 S and J, then selects the historical map passers plus the six lowest
unique nonpassers and their axial grid neighbours, capped at 12 by the new
order key. The historical pass flag only selects where to look.

| R1 search order | g_gaba | g_glu |
|---:|---:|---:|
| 1 | 4 | 2 |
| 2 | 3 | 8 |
| 3 | 3 | 6 |
| 4 | 4 | 1 |
| 5 | 3 | 4 |
| 6 | 3 | 3 |
| 7 | 3 | 2 |
| 8 | 3 | 1 |
| 9 | 4 | 8 |
| 10 | 4 | 3 |
| 11 | 4 | 6 |
| 12 | 4 | 4 |

Each runs all 19 weights (0.70–1.60 mV), seeds 1–3, 2 s settle and 10 s
measurement: **684 evaluations / 8,208 brain seconds**. R1 uses the curated
whole-brain transmitter rule, fixed histamine scale 1, and layers A/C on with
clamped dopamine pools and held tonic arrays. Sensory background remains zero.

Map limitations: five J groups (ascending, endocrine, motor,
visual_centrifugal, visual_projection) were not recorded. For map-only ordering,
their rates are floored to 0.01 Hz, adding the same constant J contribution to
every row before binning. This is an explicit missing-data convention, not a
measurement; R1 records every target group. The map's stored stability ratio was
last/first; the importer computes first/last from the original rates. Candidate
pair gradedness compares the point above the pair against both members.

## Decision and confirmation

Constructed tests exercise section 2.6 before engine execution, including silent
and missing metrics, strict boundaries, J bins, total ordering, the 20-candidate
cap, all tier-2 triggers, six-candidate R3 exhaustion, the 12-hour fallback,
T-to-C retry, one-candidate exhaustion and both escalation routes.

The first 20 R-screen passers enter R-reflex. Extended background-on responses
must pass the six-value and ten-seed rules. The matched bare background-off
reference is shared once per batch, with ten seeds in upstream and extended
modes. Extended retention must reach 0.5. R-long runs only after reflex passes:
ten seeds, 2 s settle + 30 s measurement, F <3, no ignition and first/last 5 s
ratio in [0.5, 2]. All-neuron 1 ms bins define F and maximum bin fraction.

## Compute and evidence

Camber job 27297 failed before engine construction (101 running seconds,
0.0718222 credits). The full Stash round-trip proved seven executable-mode
changes with all 408 tracked blobs unchanged. Retry 27299 retained the whole-tree
guard and set only Git core.fileMode=false. It completed in 11327 running seconds,
3.146388889 node-hours, 8.054755556 credits. Total WP17 Camber spend is
**8.126577778 credits**. Receipt and ledger: `validation/records/p2/camber-receipts/wp17/` and
`.reports/camber-ledger.md`. The CREDITS spent notification was delivered.

R2 ran on the Mac with `--workers auto`, 14 leased slots and prelaunch swap
1335.88M. Every evaluation carries job id, commit, code_scope and platform.
Both stages are development evidence; no configuration has been qualified.

## Tier-2 trigger (not final escalation)

*Historical, from the tier-1 close. Tier 2 has since run in full; the final escalation is above.*

The empty ranking triggers section 2.6 step 4 via **R-reflex**. The three unique
scale pairs with lowest measured reflex violation, ties by order key, are
**(3,6), (3,8), (4,2)**. The prepared but unexecuted plan is
`validation/records/p2/rest-tier2-plan.json`: 51 settings, 2,907 evaluations,
34,884 brain seconds. Any third Camber job needs a new explicit go. No tier-2
engines have been launched, and section 2.6 step 5 / P2-partial-B is not reached.

## Prepared matched bare reference (development)

Both mode tasks completed and their 20 evaluation rows passed the manifest's
seed, setting, plan and execution-identity checks. These are reference responses,
not candidate qualification. They will be reused by R2 via `--bare-dir`.

| Mode | Mean MN9 difference (Hz) | Seeds | Job id | Commit | code_scope | Platform |
|---|---:|---:|---|---|---|---|
| upstream | 85.3 | 10 | mac-w17-bare-20260915 | 48141f11b18b12e2013f36225eff1b1042e29d4a | git:8910ab5b893ac6e3e8482771f58348ea9f6900de31445f533deb9e0e4c744c0f | darwin-arm64 |
| extended | 56.0 | 10 | mac-w17-bare-20260915 | 48141f11b18b12e2013f36225eff1b1042e29d4a | git:8910ab5b893ac6e3e8482771f58348ea9f6900de31445f533deb9e0e4c744c0f | darwin-arm64 |

Raw evidence: `camber-runs/wp17/bare/{bare-upstream,bare-extended}.ndjson` and
`tasks.json`. Upstream task wall was 1570.73 s; extended was 816.93 s, each below
the 3247.5 s task budget. The two tasks ran concurrently under an auto slot lease.

## R1 collected and verified

Job 27299 completed in 11327 s, 3.146388889 node-hours, 8.054755556 credits.
All 684 evaluations and 36 completion rows match their original task manifests:
commit `b3622d0d45283f0df8bb501514edb31aae64a0d8`, code_scope `git:1f24c37fa74ba8d75da9f73693cca240ee87a479487492f400ce11965262f1b1`, platform `linux-x86_64`, job `27299`.
The unchanged clean-tree guard ran after the mode-only Git configuration repair;
all source blobs had already passed the full Stash round-trip audit. Every
downloaded artifact hash and the locally recomputed aggregation match.
Verification: `validation/records/p2/rest-R1-verification.json`. Raw evidence:
`camber-runs/wp17/R1-curated-retry/R1/`.

| Admission | g_gaba | g_glu | w_bg mV | S | J |
|---:|---:|---:|---:|---:|---:|
| 1 | 3 | 8 | 1.10 | 0 | 17.98448124 |
| 2 | 3 | 8 | 1.15 | 0 | 18.21413310 |
| 3 | 3 | 6 | 1.15 | 0 | 18.90330068 |
| 4 | 3 | 8 | 1.20 | 0 | 20.19581240 |
| 5 | 3 | 6 | 1.20 | 0 | 21.02850641 |
| 6 | 3 | 8 | 1.25 | 0 | 22.45620095 |
| 7 | 4 | 2 | 1.40 | 0 | 33.10931246 |
| 8 | 4 | 3 | 1.45 | 0 | 33.79873278 |
| 9 | 4 | 4 | 1.50 | 0 | 35.23790103 |

No cap exclusions. R2 reuses the completed Mac bare reference byte for byte.

## R2 completed and verified (Mac, development)

All 27 candidate tasks completed: 297 evaluations, plus the original 20 bare
reference evaluations reused byte for byte. Every task's provenance, seed and
setting coverage passed. All 32 final artifact hashes matched, independent
reaggregation reproduced the decision, and the R2 stage import accepted the
record. R-long has zero evaluations because no candidate passed R-reflex.

Candidate job: `mac-w17-R2-20260916`; commit
`3b1af0d5ca9f1caa7f630c9187da81805c731a45`; code_scope
`git:8910ab5b893ac6e3e8482771f58348ea9f6900de31445f533deb9e0e4c744c0f`;
platform `darwin-arm64`. The reused reference keeps its original `48141f1`
commit and `mac-w17-bare-20260915` label, with the same code_scope and platform.
R1 keeps its distinct original b3622d0 identity; no evidence was relabelled.

The following is the failed R2 candidate table in order-key order, **not a
qualifying ranked list**. All upstream retentions are zero. Extended mean
responses were 0.1 Hz for the six g_gaba=3 candidates and zero for the three
g_gaba=4 candidates, against the bare 56.0 Hz mean.

| g_gaba | g_glu | w_bg mV | (a) min Δ Hz | (b) mean Δ Hz | (b) min Δ Hz | Extended retention | S | J | Failed step |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 3 | 6 | 1.15 | 0 | 3.7 | -11 | 0.00178571 | 10.20459265 | 18.90330068 | R-reflex (a), (b), (c) |
| 3 | 8 | 1.20 | 1 | 2.4 | -5 | 0.00178571 | 10.63745673 | 20.19581240 | R-reflex (a), (b), (c) |
| 3 | 8 | 1.25 | -3 | 1.8 | -2 | 0.00178571 | 10.92513880 | 22.45620095 | R-reflex (a), (b), (c) |
| 3 | 6 | 1.20 | 0 | 1.4 | -4 | 0.00178571 | 11.17645323 | 21.02850641 | R-reflex (a), (b), (c) |
| 3 | 8 | 1.10 | -36 | -7.0 | -36 | 0.00178571 | 11.51292546 | 17.98448124 | R-reflex (a), (b), (c) |
| 3 | 8 | 1.15 | -10 | 0.1 | -22 | 0.00178571 | 11.51292546 | 18.21413310 | R-reflex (a), (b), (c) |
| 4 | 2 | 1.40 | -1 | 0.6 | -1 | 0.00000000 | 11.51292546 | 33.10931246 | R-reflex (a), (b), (c) |
| 4 | 3 | 1.45 | 0 | 1.0 | -1 | 0.00000000 | 11.51292546 | 33.79873278 | R-reflex (a), (b), (c) |
| 4 | 4 | 1.50 | 0 | 1.0 | -1 | 0.00000000 | 11.51292546 | 35.23790103 | R-reflex (a), (b), (c) |

Committed decision and full per-seed reflex values:
`validation/records/p2/rest-R2-decision.json`. Raw final summary and artifacts:
`camber-runs/wp17/R2/summary.json`, `reflex/`, `bare-reference/`.
Ranked list `[]`; shortlist `[]`. No configuration or R3 candidate is released.

<!-- closest-miss:begin -->
## Appendix: closest-miss table, all candidates (FINAL)

Grouped by deepest stage reached (measured through R-reflex, measured beyond cap, R-reflex pending, not
tested (cap), R-screen failure), order key within each group. 1071 candidates.

| Tier | g_gaba | g_glu | σ_th mV | optic exempt | n_bg | w_bg mV | F max | b max | stability min–max | central Hz | DAN Hz | KC Hz | gradedness max | (a) min Δ Hz | (b) mean Δ Hz | (c) ext. retention | S | J | Failed step |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 2 | 3.0 | 6.0 | 1.0 | off | 25 | 3.4000 | 2.135 | 0.0026 | 0.987–1.010 | 3.93–4.24 | 0.67–0.85 | 1.42–1.52 | 1.16 | 0 | 14.1 | 0.0018 | 8.8668 | 16.101 | R-reflex (a, b, c) |
| 2 | 3.0 | 8.0 | 2.0 | on | 25 | 3.0000 | 1.995 | 0.0032 | 0.985–1.024 | 3.82–4.07 | 0.77–0.95 | 1.35–1.43 | 1.14 | -28 | 12.7 | 0.0018 | 8.9713 | 15.554 | R-reflex (a, b, c) |
| 2 | 3.0 | 6.0 | 2.0 | off | 25 | 3.0000 | 2.048 | 0.0027 | 0.993–1.005 | 4.09–4.36 | 0.80–0.98 | 1.42–1.49 | 1.14 | -53 | 12.5 | 0.0018 | 8.9872 | 15.706 | R-reflex (a, b, c) |
| 2 | 3.0 | 8.0 | 2.0 | off | 25 | 3.0000 | 2.081 | 0.0027 | 0.988–0.997 | 3.81–4.07 | 0.78–0.96 | 1.33–1.41 | 1.14 | -3 | 11.0 | 0.0018 | 9.1150 | 14.914 | R-reflex (a, b, c) |
| 2 | 3.0 | 8.0 | 2.0 | off | 400 | 0.2125 | 2.788 | 0.0026 | 0.982–1.013 | 3.64–3.85 | 0.58–0.70 | 1.38–1.46 | 1.12 | -49 | 7.3 | 0.0018 | 9.5251 | 15.605 | R-reflex (a, b, c) |
| 2 | 3.0 | 6.0 | 2.0 | on | 25 | 2.8000 | 2.060 | 0.0028 | 0.985–1.012 | 3.85–4.08 | 0.64–0.78 | 1.34–1.40 | 1.13 | -49 | 6.9 | 0.0018 | 9.5814 | 15.948 | R-reflex (a, b, c) |
| 2 | 3.0 | 8.0 | 2.0 | on | 25 | 2.8000 | 2.141 | 0.0029 | 0.985–1.009 | 3.60–3.82 | 0.63–0.77 | 1.28–1.35 | 1.14 | 6 | -9.0 | 0.0018 | 9.7212 | 15.258 | R-reflex (a, b, c) |
| 2 | 3.0 | 8.0 | 2.0 | off | 100 | 0.8500 | 2.384 | 0.0027 | 0.985–1.011 | 3.80–4.04 | 0.70–0.84 | 1.42–1.49 | 1.13 | -16 | 5.6 | 0.0018 | 9.7902 | 15.440 | R-reflex (a, b, c) |
| 2 | 3.0 | 6.0 | 2.0 | off | 100 | 0.8000 | 2.450 | 0.0025 | 0.996–1.012 | 3.87–4.09 | 0.61–0.72 | 1.43–1.50 | 1.13 | -44 | 4.8 | 0.0018 | 9.9443 | 15.884 | R-reflex (a, b, c) |
| 2 | 3.0 | 8.0 | 2.0 | off | 100 | 0.8000 | 2.487 | 0.0024 | 0.985–1.015 | 3.60–3.80 | 0.59–0.70 | 1.36–1.42 | 1.13 | -40 | 4.0 | 0.0018 | 10.1266 | 15.734 | R-reflex (a, b, c) |
| 1 | 3.0 | 6.0 | 0.0 | off | 100 | 1.1500 | 2.652 | 0.0033 | 0.985–1.017 | 4.39–4.79 | 0.76–0.97 | 1.78–1.87 | 1.19 | 0 | 3.7 | 0.0018 | 10.2046 | 18.903 | R-reflex (a, b, c) |
| 2 | 3.0 | 8.0 | 2.0 | off | 25 | 2.8000 | 2.193 | 0.0024 | 0.992–1.016 | 3.58–3.81 | 0.63–0.78 | 1.26–1.33 | 1.14 | -16 | 2.5 | 0.0018 | 10.5966 | 14.899 | R-reflex (a, b, c) |
| 2 | 3.0 | 8.0 | 0.0 | off | 25 | 3.6000 | 2.089 | 0.0027 | 0.983–1.012 | 3.70–4.00 | 0.66–0.83 | 1.41–1.50 | 1.18 | -16 | 2.4 | 0.0018 | 10.6375 | 15.779 | R-reflex (a, b, c) |
| 1 | 3.0 | 8.0 | 0.0 | off | 100 | 1.2000 | 2.554 | 0.0035 | 0.991–1.011 | 4.46–4.84 | 0.93–1.22 | 1.78–1.88 | 1.18 | 1 | 2.4 | 0.0018 | 10.6375 | 20.196 | R-reflex (a, b, c) |
| 2 | 3.0 | 8.0 | 1.0 | off | 25 | 3.4000 | 2.154 | 0.0026 | 0.988–1.014 | 3.66–3.94 | 0.65–0.82 | 1.33–1.41 | 1.17 | -28 | 1.9 | 0.0018 | 10.8711 | 15.492 | R-reflex (a, b, c) |
| 1 | 3.0 | 8.0 | 0.0 | off | 100 | 1.2500 | 2.591 | 0.0040 | 0.991–1.004 | 4.84–5.24 | 1.22–1.58 | 1.88–1.94 | 1.17 | -3 | 1.8 | 0.0018 | 10.9251 | 22.456 | R-reflex (a, b, c) |
| 2 | 3.0 | 6.0 | 2.0 | off | 400 | 0.2125 | 2.811 | 0.0026 | 0.997–1.008 | 3.92–4.14 | 0.59–0.70 | 1.47–1.54 | 1.12 | -52 | 1.4 | 0.0018 | 11.1765 | 15.830 | R-reflex (a, b, c) |
| 1 | 3.0 | 6.0 | 0.0 | off | 100 | 1.2000 | 2.393 | 0.0037 | 0.984–1.017 | 4.79–5.22 | 0.97–1.26 | 1.87–1.96 | 1.19 | 0 | 1.4 | 0.0018 | 11.1765 | 21.029 | R-reflex (a, b, c) |
| 2 | 3.0 | 6.0 | 2.0 | off | 25 | 2.8000 | 2.141 | 0.0026 | 0.994–1.006 | 3.85–4.09 | 0.64–0.80 | 1.33–1.42 | 1.14 | -53 | -6.0 | 0.0018 | 11.5129 | 15.672 | R-reflex (a, b, c) |
| 2 | 3.0 | 8.0 | 2.0 | on | 100 | 0.8000 | 2.668 | 0.0029 | 0.967–1.046 | 3.61–3.82 | 0.58–0.68 | 1.36–1.43 | 1.13 | -59 | -10.8 | 0.0018 | 11.5129 | 15.723 | R-reflex (a, b, c) |
| 2 | 3.0 | 8.0 | 0.0 | on | 25 | 3.4000 | 2.420 | 0.0027 | 0.987–1.021 | 3.41–3.70 | 0.52–0.65 | 1.32–1.40 | 1.19 | -16 | -3.4 | 0.0018 | 11.5129 | 15.935 | R-reflex (a, b, c) |
| 2 | 3.0 | 8.0 | 1.0 | on | 25 | 3.4000 | 2.160 | 0.0031 | 0.993–1.022 | 3.67–3.98 | 0.64–0.84 | 1.34–1.45 | 1.17 | -29 | -5.2 | 0.0018 | 11.5129 | 15.831 | R-reflex (a, b, c) |
| 2 | 3.0 | 8.0 | 2.0 | off | 400 | 0.2250 | 2.766 | 0.0028 | 0.988–1.013 | 3.85–4.07 | 0.70–0.81 | 1.46–1.53 | 1.12 | -49 | -12.4 | 0.0018 | 11.5129 | 15.792 | R-reflex (a, b, c) |
| 2 | 3.0 | 6.0 | 1.0 | on | 25 | 3.4000 | 2.237 | 0.0032 | 0.988–1.009 | 3.94–4.24 | 0.67–0.85 | 1.42–1.50 | 1.16 | -25 | -2.4 | 0.0018 | 11.5129 | 16.214 | R-reflex (a, b, c) |
| 1 | 3.0 | 8.0 | 0.0 | off | 100 | 1.1000 | 2.995 | 0.0029 | 0.995–1.022 | 3.75–4.09 | 0.57–0.72 | 1.60–1.69 | 1.19 | -36 | -7.0 | 0.0018 | 11.5129 | 17.984 | R-reflex (a, b, c) |
| 1 | 3.0 | 8.0 | 0.0 | off | 100 | 1.1500 | 2.516 | 0.0032 | 0.995–1.011 | 4.09–4.46 | 0.72–0.93 | 1.69–1.78 | 1.19 | -10 | 0.1 | 0.0018 | 11.5129 | 18.214 | R-reflex (a, b, c) |
| 1 | 4.0 | 2.0 | 0.0 | off | 100 | 1.4000 | 2.244 | 0.0058 | 0.994–1.003 | 7.12–7.63 | 2.62–3.13 | 1.24–1.28 | 1.15 | -1 | 0.6 | 0.0000 | 11.5129 | 33.109 | R-reflex (a, b, c) |
| 1 | 4.0 | 3.0 | 0.0 | off | 100 | 1.4500 | 2.282 | 0.0059 | 0.995–1.007 | 7.09–7.56 | 2.88–3.46 | 1.34–1.39 | 1.14 | 0 | 1.0 | 0.0000 | 11.5129 | 33.799 | R-reflex (a, b, c) |
| 1 | 4.0 | 4.0 | 0.0 | off | 100 | 1.5000 | 2.698 | 0.0067 | 0.995–1.008 | 7.19–7.63 | 3.36–4.01 | 1.43–1.51 | 1.13 | 0 | 1.0 | 0.0000 | 11.5129 | 35.238 | R-reflex (a, b, c) |
| 2 | 3.0 | 6.0 | 1.0 | on | 25 | 3.2000 | 2.263 | 0.0026 | 0.988–1.009 | 3.67–3.94 | 0.53–0.67 | 1.33–1.42 | 1.16 | -21 | 12.3 | 0.0018 | 9.0033 | 16.389 | measured beyond cap (not in decision) |
| 2 | 3.0 | 8.0 | 1.0 | on | 25 | 3.2000 | 2.350 | 0.0027 | 0.992–1.014 | 3.42–3.67 | 0.52–0.64 | 1.27–1.34 | 1.17 | -29 | -6.2 | 0.0018 | 11.5129 | 16.230 | measured beyond cap (not in decision) |
| 2 | 3.0 | 8.0 | 2.0 | off | 25 | 3.2000 | 2.034 | 0.0030 | 0.988–1.019 | 4.07–4.33 | 0.96–1.17 | 1.41–1.50 | 1.14 | -36 | -5.3 | 0.0018 | 11.5129 | 16.173 | measured beyond cap (not in decision) |
| 2 | 3.0 | 8.0 | 2.0 | on | 400 | 0.2250 | 2.981 | 0.0033 | 0.988–1.011 | 3.86–4.09 | 0.69–0.82 | 1.49–1.57 | 1.13 | -45 | -2.7 | 0.0018 | 11.5129 | 16.012 | measured beyond cap (not in decision) |
| 2 | 3.0 | 6.0 | 0.0 | off | 25 | 3.4000 | 2.227 | 0.0023 | 0.990–1.016 | 3.66–3.95 | 0.54–0.68 | 1.38–1.48 | 1.17 | -46 | -5.3 | 0.0018 | 11.5129 | 16.278 | measured beyond cap (not in decision) |
| 2 | 3.0 | 6.0 | 0.0 | off | 25 | 3.6000 | 2.099 | 0.0027 | 0.995–1.002 | 3.95–4.29 | 0.68–0.86 | 1.48–1.56 | 1.18 | -46 | -6.8 | 0.0018 | 11.5129 | 16.266 | measured beyond cap (not in decision) |
| 2 | 3.0 | 8.0 | 2.0 | on | 100 | 0.8500 | 2.482 | 0.0032 | 0.967–1.002 | 3.82–4.07 | 0.68–0.85 | 1.43–1.51 | 1.14 | -59 | -6.7 | 0.0018 | 11.5129 | 16.411 | measured beyond cap (not in decision) |
| 2 | 3.0 | 6.0 | 0.0 | on | 25 | 3.4000 | 2.448 | 0.0028 | 0.985–1.012 | 3.67–3.97 | 0.55–0.69 | 1.39–1.47 | 1.17 | -30 | -8.3 | 0.0018 | 11.5129 | 16.525 | measured beyond cap (not in decision) |
| 2 | 3.0 | 6.0 | 2.0 | on | 25 | 3.0000 | 2.030 | 0.0032 | 0.985–1.007 | 4.08–4.35 | 0.78–0.95 | 1.40–1.49 | 1.14 | n/a | n/a | n/a | 0.0000 | 16.112 | not tested (cap) |
| 2 | 3.0 | 6.0 | 2.0 | on | 100 | 0.8000 | 2.603 | 0.0029 | 0.992–1.017 | 3.87–4.09 | 0.60–0.70 | 1.43–1.48 | 1.12 | n/a | n/a | n/a | 0.0000 | 16.162 | not tested (cap) |
| 2 | 3.0 | 8.0 | 0.0 | on | 25 | 3.6000 | 2.122 | 0.0032 | 0.998–1.010 | 3.70–4.03 | 0.65–0.82 | 1.40–1.49 | 1.19 | n/a | n/a | n/a | 0.0000 | 16.189 | not tested (cap) |
| 2 | 3.0 | 8.0 | 1.0 | off | 25 | 3.6000 | 2.071 | 0.0030 | 0.992–1.014 | 3.94–4.26 | 0.82–1.05 | 1.41–1.51 | 1.17 | n/a | n/a | n/a | 0.0000 | 16.233 | not tested (cap) |
| 2 | 3.0 | 6.0 | 2.0 | off | 100 | 0.8500 | 2.377 | 0.0029 | 0.991–1.012 | 4.09–4.34 | 0.72–0.86 | 1.50–1.55 | 1.12 | n/a | n/a | n/a | 0.0000 | 16.268 | not tested (cap) |
| 2 | 3.0 | 6.0 | 2.0 | off | 400 | 0.2250 | 2.736 | 0.0031 | 0.997–1.020 | 4.14–4.37 | 0.70–0.83 | 1.54–1.59 | 1.13 | n/a | n/a | n/a | 0.0000 | 16.371 | not tested (cap) |
| 2 | 3.0 | 8.0 | 0.0 | off | 25 | 3.8000 | 2.024 | 0.0030 | 0.983–1.012 | 4.00–4.35 | 0.83–1.06 | 1.50–1.59 | 1.17 | n/a | n/a | n/a | 0.0000 | 16.357 | not tested (cap) |
| 2 | 3.0 | 8.0 | 1.0 | off | 25 | 3.2000 | 2.270 | 0.0023 | 0.988–1.003 | 3.40–3.66 | 0.52–0.65 | 1.26–1.33 | 1.16 | n/a | n/a | n/a | 0.0000 | 16.324 | not tested (cap) |
| 2 | 3.0 | 8.0 | 2.0 | off | 400 | 0.2375 | 2.778 | 0.0031 | 0.981–1.011 | 4.07–4.31 | 0.81–0.97 | 1.53–1.64 | 1.13 | n/a | n/a | n/a | 0.0000 | 16.321 | not tested (cap) |
| 2 | 3.0 | 6.0 | 0.0 | on | 25 | 3.6000 | 2.248 | 0.0034 | 0.983–1.012 | 3.97–4.31 | 0.69–0.86 | 1.47–1.57 | 1.18 | n/a | n/a | n/a | 0.0000 | 16.552 | not tested (cap) |
| 2 | 3.0 | 6.0 | 1.0 | off | 25 | 3.2000 | 2.222 | 0.0025 | 0.987–1.010 | 3.67–3.93 | 0.53–0.67 | 1.34–1.42 | 1.16 | n/a | n/a | n/a | 0.0000 | 16.570 | not tested (cap) |
| 2 | 3.0 | 6.0 | 2.0 | on | 100 | 0.8500 | 2.512 | 0.0035 | 0.974–1.013 | 4.09–4.34 | 0.70–0.86 | 1.48–1.57 | 1.13 | n/a | n/a | n/a | 0.0000 | 16.659 | not tested (cap) |
| 2 | 3.0 | 6.0 | 2.0 | on | 400 | 0.2250 | 2.967 | 0.0034 | 0.999–1.016 | 4.13–4.39 | 0.69–0.83 | 1.54–1.62 | 1.13 | n/a | n/a | n/a | 0.0000 | 16.668 | not tested (cap) |
| 2 | 3.0 | 8.0 | 0.0 | off | 25 | 3.4000 | 2.330 | 0.0022 | 0.979–1.006 | 3.41–3.70 | 0.51–0.66 | 1.31–1.41 | 1.18 | n/a | n/a | n/a | 0.0000 | 16.697 | not tested (cap) |
| 2 | 3.0 | 8.0 | 2.0 | off | 100 | 0.9000 | 2.439 | 0.0029 | 0.995–1.011 | 4.04–4.28 | 0.84–1.02 | 1.49–1.57 | 1.13 | n/a | n/a | n/a | 0.0000 | 16.554 | not tested (cap) |
| 2 | 3.0 | 6.0 | 2.0 | off | 25 | 3.2000 | 1.967 | 0.0030 | 0.993–1.008 | 4.36–4.64 | 0.98–1.20 | 1.49–1.56 | 1.14 | n/a | n/a | n/a | 0.0000 | 16.892 | not tested (cap) |
| 2 | 3.0 | 6.0 | 2.0 | off | 100 | 0.7500 | 2.551 | 0.0023 | 0.987–1.009 | 3.67–3.87 | 0.51–0.61 | 1.35–1.43 | 1.12 | n/a | n/a | n/a | 0.0000 | 16.924 | not tested (cap) |
| 2 | 3.0 | 8.0 | 1.0 | on | 25 | 3.6000 | 2.004 | 0.0038 | 0.993–1.022 | 3.98–4.28 | 0.84–1.06 | 1.45–1.52 | 1.16 | n/a | n/a | n/a | 0.0000 | 16.751 | not tested (cap) |
| 2 | 3.0 | 8.0 | 2.0 | on | 25 | 3.2000 | 1.952 | 0.0036 | 0.979–1.024 | 4.07–4.34 | 0.95–1.16 | 1.43–1.51 | 1.14 | n/a | n/a | n/a | 0.0000 | 16.802 | not tested (cap) |
| 2 | 3.0 | 6.0 | 0.0 | off | 25 | 3.8000 | 1.962 | 0.0031 | 0.987–1.002 | 4.29–4.66 | 0.86–1.11 | 1.56–1.66 | 1.18 | n/a | n/a | n/a | 0.0000 | 17.144 | not tested (cap) |
| 2 | 3.0 | 6.0 | 1.0 | off | 25 | 3.6000 | 2.000 | 0.0030 | 0.987–1.007 | 4.24–4.55 | 0.85–1.10 | 1.52–1.59 | 1.16 | n/a | n/a | n/a | 0.0000 | 17.168 | not tested (cap) |
| 2 | 3.0 | 6.0 | 1.0 | on | 25 | 3.6000 | 2.074 | 0.0036 | 0.994–1.013 | 4.24–4.57 | 0.85–1.09 | 1.50–1.59 | 1.17 | n/a | n/a | n/a | 0.0000 | 17.328 | not tested (cap) |
| 2 | 3.0 | 6.0 | 2.0 | off | 100 | 0.9000 | 2.377 | 0.0031 | 0.991–1.005 | 4.34–4.59 | 0.86–1.04 | 1.55–1.62 | 1.13 | n/a | n/a | n/a | 0.0000 | 17.308 | not tested (cap) |
| 2 | 3.0 | 6.0 | 2.0 | off | 400 | 0.2375 | 2.700 | 0.0032 | 0.998–1.020 | 4.37–4.64 | 0.83–0.99 | 1.59–1.69 | 1.13 | n/a | n/a | n/a | 0.0000 | 17.253 | not tested (cap) |
| 2 | 3.0 | 8.0 | 0.0 | on | 25 | 3.8000 | 1.977 | 0.0039 | 0.994–1.006 | 4.03–4.37 | 0.82–1.09 | 1.49–1.60 | 1.18 | n/a | n/a | n/a | 0.0000 | 17.417 | not tested (cap) |
| 2 | 3.0 | 8.0 | 1.0 | off | 25 | 3.8000 | 2.010 | 0.0033 | 0.989–1.009 | 4.26–4.58 | 1.05–1.33 | 1.51–1.61 | 1.16 | n/a | n/a | n/a | 0.0000 | 17.321 | not tested (cap) |
| 2 | 3.0 | 8.0 | 1.0 | off | 100 | 1.0500 | 2.624 | 0.0029 | 0.987–1.011 | 3.90–4.20 | 0.68–0.85 | 1.55–1.63 | 1.16 | n/a | n/a | n/a | 0.0000 | 17.253 | not tested (cap) |
| 2 | 3.0 | 8.0 | 2.0 | on | 100 | 0.9000 | 2.377 | 0.0037 | 0.984–1.026 | 4.07–4.31 | 0.85–1.02 | 1.51–1.57 | 1.13 | n/a | n/a | n/a | 0.0000 | 17.268 | not tested (cap) |
| 2 | 3.0 | 8.0 | 2.0 | on | 400 | 0.2375 | 2.981 | 0.0037 | 0.990–1.008 | 4.09–4.35 | 0.82–0.98 | 1.57–1.64 | 1.13 | n/a | n/a | n/a | 0.0000 | 17.465 | not tested (cap) |
| 2 | 3.0 | 6.0 | 1.0 | off | 100 | 1.0000 | 2.897 | 0.0028 | 0.997–1.008 | 3.89–4.17 | 0.57–0.72 | 1.54–1.61 | 1.16 | n/a | n/a | n/a | 0.0000 | 17.580 | not tested (cap) |
| 2 | 3.0 | 6.0 | 2.0 | on | 25 | 3.2000 | 1.970 | 0.0037 | 0.991–1.012 | 4.35–4.66 | 0.95–1.20 | 1.49–1.58 | 1.14 | n/a | n/a | n/a | 0.0000 | 17.739 | not tested (cap) |
| 2 | 3.0 | 8.0 | 1.0 | off | 100 | 1.0000 | 2.745 | 0.0026 | 0.976–1.010 | 3.63–3.90 | 0.55–0.68 | 1.47–1.55 | 1.16 | n/a | n/a | n/a | 0.0000 | 17.686 | not tested (cap) |
| 2 | 3.0 | 8.0 | 2.0 | off | 25 | 3.4000 | 2.047 | 0.0033 | 0.989–1.019 | 4.33–4.61 | 1.17–1.42 | 1.50–1.59 | 1.14 | n/a | n/a | n/a | 0.0000 | 17.623 | not tested (cap) |
| 2 | 3.0 | 6.0 | 0.0 | on | 25 | 3.8000 | 2.155 | 0.0040 | 0.983–1.009 | 4.31–4.68 | 0.86–1.13 | 1.57–1.66 | 1.17 | n/a | n/a | n/a | 0.0000 | 17.974 | not tested (cap) |
| 2 | 3.0 | 6.0 | 1.0 | off | 100 | 1.0500 | 2.569 | 0.0029 | 0.992–1.002 | 4.17–4.50 | 0.72–0.89 | 1.61–1.70 | 1.16 | n/a | n/a | n/a | 0.0000 | 17.959 | not tested (cap) |
| 2 | 3.0 | 6.0 | 2.0 | on | 100 | 0.9000 | 2.522 | 0.0038 | 0.974–1.007 | 4.34–4.61 | 0.86–1.04 | 1.57–1.65 | 1.13 | n/a | n/a | n/a | 0.0000 | 17.946 | not tested (cap) |
| 2 | 3.0 | 8.0 | 2.0 | off | 100 | 0.9500 | 2.466 | 0.0032 | 0.994–1.007 | 4.28–4.55 | 1.02–1.24 | 1.57–1.64 | 1.13 | n/a | n/a | n/a | 0.0000 | 17.757 | not tested (cap) |
| 2 | 3.0 | 6.0 | 1.0 | off | 25 | 3.8000 | 1.930 | 0.0034 | 0.987–1.023 | 4.55–4.91 | 1.10–1.39 | 1.59–1.68 | 1.16 | n/a | n/a | n/a | 0.0000 | 18.141 | not tested (cap) |
| 2 | 3.0 | 8.0 | 0.0 | off | 25 | 4.0000 | 1.971 | 0.0035 | 0.993–1.003 | 4.35–4.69 | 1.06–1.36 | 1.59–1.67 | 1.16 | n/a | n/a | n/a | 0.0000 | 18.192 | not tested (cap) |
| 2 | 3.0 | 8.0 | 2.0 | off | 400 | 0.2500 | 2.898 | 0.0034 | 0.981–1.012 | 4.31–4.58 | 0.97–1.18 | 1.64–1.69 | 1.13 | n/a | n/a | n/a | 0.0000 | 18.017 | not tested (cap) |
| 2 | 3.0 | 6.0 | 2.0 | off | 25 | 3.4000 | 1.932 | 0.0034 | 0.983–1.019 | 4.64–4.94 | 1.20–1.47 | 1.56–1.65 | 1.14 | n/a | n/a | n/a | 0.0000 | 18.394 | not tested (cap) |
| 2 | 3.0 | 6.0 | 2.0 | on | 400 | 0.2375 | 2.967 | 0.0040 | 0.994–1.016 | 4.39–4.64 | 0.83–1.00 | 1.62–1.68 | 1.13 | n/a | n/a | n/a | 0.0000 | 18.342 | not tested (cap) |
| 2 | 3.0 | 8.0 | 1.0 | on | 25 | 3.8000 | 1.950 | 0.0041 | 0.992–1.014 | 4.28–4.61 | 1.06–1.33 | 1.52–1.62 | 1.16 | n/a | n/a | n/a | 0.0000 | 18.283 | not tested (cap) |
| 2 | 3.0 | 8.0 | 2.0 | on | 25 | 3.4000 | 1.874 | 0.0041 | 0.979–1.011 | 4.34–4.63 | 1.16–1.43 | 1.51–1.60 | 1.14 | n/a | n/a | n/a | 0.0000 | 18.494 | not tested (cap) |
| 2 | 3.0 | 6.0 | 2.0 | off | 100 | 0.9500 | 2.333 | 0.0033 | 0.985–1.005 | 4.59–4.88 | 1.04–1.28 | 1.62–1.69 | 1.13 | n/a | n/a | n/a | 0.0000 | 18.626 | not tested (cap) |
| 2 | 3.0 | 8.0 | 1.0 | off | 100 | 1.1000 | 2.502 | 0.0032 | 0.987–1.011 | 4.20–4.53 | 0.85–1.08 | 1.63–1.73 | 1.16 | n/a | n/a | n/a | 0.0000 | 18.508 | not tested (cap) |
| 2 | 3.0 | 6.0 | 0.0 | off | 25 | 4.0000 | 1.935 | 0.0036 | 0.987–1.000 | 4.66–5.03 | 1.11–1.41 | 1.66–1.75 | 1.16 | n/a | n/a | n/a | 0.0000 | 18.876 | not tested (cap) |
| 2 | 3.0 | 8.0 | 2.0 | on | 100 | 0.9500 | 2.396 | 0.0042 | 0.990–1.026 | 4.31–4.59 | 1.02–1.27 | 1.57–1.70 | 1.13 | n/a | n/a | n/a | 0.0000 | 18.970 | not tested (cap) |
| 2 | 3.0 | 8.0 | 2.0 | on | 400 | 0.2500 | 2.816 | 0.0042 | 0.990–1.015 | 4.35–4.62 | 0.98–1.21 | 1.64–1.74 | 1.13 | n/a | n/a | n/a | 0.0000 | 18.986 | not tested (cap) |
| 2 | 3.0 | 6.0 | 1.0 | off | 100 | 1.1000 | 2.458 | 0.0034 | 0.975–1.002 | 4.50–4.85 | 0.89–1.15 | 1.70–1.81 | 1.16 | n/a | n/a | n/a | 0.0000 | 19.118 | not tested (cap) |
| 2 | 3.0 | 6.0 | 2.0 | off | 400 | 0.2500 | 2.738 | 0.0034 | 0.995–1.013 | 4.64–4.91 | 0.99–1.21 | 1.69–1.76 | 1.12 | n/a | n/a | n/a | 0.0000 | 19.012 | not tested (cap) |
| 2 | 3.0 | 8.0 | 0.0 | on | 25 | 4.0000 | 1.927 | 0.0043 | 0.994–1.014 | 4.37–4.72 | 1.09–1.39 | 1.60–1.70 | 1.17 | n/a | n/a | n/a | 0.0000 | 19.177 | not tested (cap) |
| 2 | 3.0 | 8.0 | 1.0 | off | 25 | 4.0000 | 1.993 | 0.0037 | 0.989–1.009 | 4.58–4.91 | 1.33–1.66 | 1.61–1.70 | 1.15 | n/a | n/a | n/a | 0.0000 | 19.199 | not tested (cap) |
| 2 | 3.0 | 8.0 | 2.0 | off | 25 | 3.6000 | 2.048 | 0.0037 | 0.999–1.007 | 4.61–4.92 | 1.42–1.73 | 1.59–1.67 | 1.13 | n/a | n/a | n/a | 0.0000 | 19.051 | not tested (cap) |
| 2 | 3.0 | 6.0 | 1.0 | on | 25 | 3.8000 | 2.007 | 0.0043 | 0.985–1.013 | 4.57–4.94 | 1.09–1.40 | 1.59–1.70 | 1.16 | n/a | n/a | n/a | 0.0000 | 19.435 | not tested (cap) |
| 2 | 3.0 | 8.0 | 2.0 | off | 100 | 1.0000 | 2.466 | 0.0036 | 0.994–1.017 | 4.55–4.84 | 1.24–1.51 | 1.64–1.72 | 1.13 | n/a | n/a | n/a | 0.0000 | 19.394 | not tested (cap) |
| 2 | 3.0 | 6.0 | 2.0 | on | 25 | 3.4000 | 1.934 | 0.0041 | 0.992–1.012 | 4.66–4.94 | 1.20–1.48 | 1.58–1.64 | 1.13 | n/a | n/a | n/a | 0.0000 | 19.720 | not tested (cap) |
| 2 | 3.0 | 8.0 | 2.0 | off | 400 | 0.2625 | 2.910 | 0.0037 | 0.989–1.012 | 4.58–4.86 | 1.18–1.45 | 1.69–1.76 | 1.12 | n/a | n/a | n/a | 0.0000 | 19.746 | not tested (cap) |
| 2 | 3.0 | 6.0 | 2.0 | on | 100 | 0.9500 | 2.522 | 0.0043 | 0.985–1.027 | 4.61–4.90 | 1.04–1.29 | 1.65–1.72 | 1.14 | n/a | n/a | n/a | 0.0000 | 19.795 | not tested (cap) |
| 2 | 3.0 | 8.0 | 0.0 | off | 25 | 4.2000 | 1.993 | 0.0038 | 0.996–1.014 | 4.69–5.04 | 1.36–1.71 | 1.67–1.76 | 1.15 | n/a | n/a | n/a | 0.0000 | 19.952 | not tested (cap) |
| 2 | 3.0 | 6.0 | 0.0 | on | 25 | 4.0000 | 1.945 | 0.0043 | 0.990–1.009 | 4.68–5.05 | 1.13–1.45 | 1.66–1.78 | 1.17 | n/a | n/a | n/a | 0.0000 | 20.172 | not tested (cap) |
| 2 | 3.0 | 6.0 | 1.0 | off | 25 | 4.0000 | 1.930 | 0.0039 | 1.007–1.023 | 4.91–5.28 | 1.39–1.72 | 1.68–1.79 | 1.16 | n/a | n/a | n/a | 0.0000 | 20.031 | not tested (cap) |
| 2 | 3.0 | 6.0 | 2.0 | off | 25 | 3.6000 | 1.964 | 0.0038 | 0.983–1.019 | 4.94–5.26 | 1.47–1.79 | 1.65–1.74 | 1.14 | n/a | n/a | n/a | 0.0000 | 20.026 | not tested (cap) |
| 2 | 3.0 | 8.0 | 1.0 | off | 100 | 1.1500 | 2.500 | 0.0037 | 0.991–1.010 | 4.53–4.87 | 1.08–1.38 | 1.73–1.81 | 1.16 | n/a | n/a | n/a | 0.0000 | 20.183 | not tested (cap) |
| 2 | 3.0 | 6.0 | 2.0 | off | 100 | 1.0000 | 2.405 | 0.0038 | 0.985–1.003 | 4.88–5.19 | 1.28–1.56 | 1.69–1.79 | 1.13 | n/a | n/a | n/a | 0.0000 | 20.429 | not tested (cap) |
| 2 | 3.0 | 8.0 | 2.0 | on | 25 | 3.6000 | 1.836 | 0.0045 | 0.989–1.011 | 4.63–4.94 | 1.43–1.73 | 1.60–1.69 | 1.14 | n/a | n/a | n/a | 0.0000 | 20.647 | not tested (cap) |
| 2 | 3.0 | 6.0 | 2.0 | off | 400 | 0.2625 | 2.756 | 0.0038 | 0.995–1.013 | 4.91–5.22 | 1.21–1.48 | 1.76–1.84 | 1.13 | n/a | n/a | n/a | 0.0000 | 20.848 | not tested (cap) |
| 2 | 3.0 | 8.0 | 1.0 | on | 25 | 4.0000 | 1.875 | 0.0047 | 0.987–1.001 | 4.61–4.95 | 1.33–1.69 | 1.62–1.72 | 1.15 | n/a | n/a | n/a | 0.0000 | 20.817 | not tested (cap) |
| 2 | 3.0 | 6.0 | 0.0 | off | 25 | 4.2000 | 1.910 | 0.0040 | 0.992–1.007 | 5.03–5.41 | 1.41–1.75 | 1.75–1.86 | 1.16 | n/a | n/a | n/a | 0.0000 | 21.044 | not tested (cap) |
| 2 | 3.0 | 6.0 | 1.0 | off | 100 | 1.1500 | 2.404 | 0.0037 | 0.975–1.015 | 4.85–5.22 | 1.15–1.43 | 1.81–1.89 | 1.16 | n/a | n/a | n/a | 0.0000 | 21.073 | not tested (cap) |
| 2 | 3.0 | 8.0 | 2.0 | off | 25 | 3.8000 | 2.048 | 0.0041 | 0.999–1.018 | 4.92–5.22 | 1.73–2.07 | 1.67–1.75 | 1.13 | n/a | n/a | n/a | 0.0000 | 21.247 | not tested (cap) |
| 2 | 3.0 | 8.0 | 2.0 | on | 100 | 1.0000 | 2.396 | 0.0046 | 0.993–1.020 | 4.59–4.87 | 1.27–1.55 | 1.70–1.77 | 1.13 | n/a | n/a | n/a | 0.0000 | 21.122 | not tested (cap) |
| 2 | 3.0 | 8.0 | 0.0 | on | 100 | 1.2000 | 2.760 | 0.0048 | 0.987–1.010 | 4.51–4.90 | 0.99–1.29 | 1.79–1.86 | 1.18 | n/a | n/a | n/a | 0.0000 | 21.310 | not tested (cap) |
| 2 | 3.0 | 8.0 | 1.0 | off | 25 | 4.2000 | 2.040 | 0.0040 | 0.994–1.004 | 4.91–5.25 | 1.66–2.04 | 1.70–1.79 | 1.14 | n/a | n/a | n/a | 0.0000 | 21.388 | not tested (cap) |
| 2 | 3.0 | 8.0 | 1.0 | on | 100 | 1.1500 | 2.814 | 0.0047 | 0.971–1.009 | 4.59–4.92 | 1.14–1.44 | 1.77–1.83 | 1.15 | n/a | n/a | n/a | 0.0000 | 21.437 | not tested (cap) |
| 2 | 3.0 | 8.0 | 2.0 | off | 100 | 1.0500 | 2.615 | 0.0040 | 0.996–1.017 | 4.84–5.13 | 1.51–1.86 | 1.72–1.82 | 1.13 | n/a | n/a | n/a | 0.0000 | 21.442 | not tested (cap) |
| 2 | 3.0 | 8.0 | 2.0 | on | 400 | 0.2625 | 2.825 | 0.0047 | 0.992–1.015 | 4.62–4.90 | 1.21–1.50 | 1.74–1.83 | 1.13 | n/a | n/a | n/a | 0.0000 | 21.445 | not tested (cap) |
| 2 | 3.0 | 6.0 | 2.0 | on | 25 | 3.6000 | 1.843 | 0.0050 | 0.987–1.005 | 4.94–5.27 | 1.48–1.77 | 1.64–1.74 | 1.14 | n/a | n/a | n/a | 0.0000 | 21.648 | not tested (cap) |
| 2 | 3.0 | 6.0 | 1.0 | on | 25 | 4.0000 | 1.923 | 0.0051 | 0.985–1.012 | 4.94–5.30 | 1.40–1.75 | 1.70–1.81 | 1.15 | n/a | n/a | n/a | 0.0000 | 21.754 | not tested (cap) |
| 2 | 3.0 | 6.0 | 2.0 | on | 100 | 1.0000 | 2.475 | 0.0047 | 0.985–1.027 | 4.90–5.21 | 1.29–1.57 | 1.72–1.80 | 1.13 | n/a | n/a | n/a | 0.0000 | 21.944 | not tested (cap) |
| 2 | 3.0 | 8.0 | 0.0 | on | 25 | 4.2000 | 1.822 | 0.0049 | 0.995–1.014 | 4.72–5.07 | 1.39–1.73 | 1.70–1.79 | 1.15 | n/a | n/a | n/a | 0.0000 | 21.812 | not tested (cap) |
| 2 | 3.0 | 8.0 | 2.0 | off | 400 | 0.2750 | 2.978 | 0.0042 | 0.989–1.007 | 4.86–5.15 | 1.45–1.79 | 1.76–1.86 | 1.13 | n/a | n/a | n/a | 0.0000 | 21.951 | not tested (cap) |
| 2 | 4.0 | 2.0 | 1.0 | off | 100 | 1.2000 | 2.411 | 0.0045 | 0.994–1.004 | 5.60–6.05 | 1.57–1.92 | 1.03–1.12 | 1.18 | n/a | n/a | n/a | 0.0000 | 22.448 | not tested (cap) |
| 2 | 3.0 | 6.0 | 1.0 | on | 100 | 1.1500 | 2.973 | 0.0050 | 0.995–1.014 | 4.90–5.27 | 1.20–1.47 | 1.82–1.92 | 1.16 | n/a | n/a | n/a | 0.0000 | 22.423 | not tested (cap) |
| 2 | 3.0 | 6.0 | 2.0 | off | 25 | 3.8000 | 1.964 | 0.0044 | 0.988–0.998 | 5.26–5.60 | 1.79–2.13 | 1.74–1.83 | 1.13 | n/a | n/a | n/a | 0.0000 | 22.323 | not tested (cap) |
| 2 | 3.0 | 8.0 | 0.0 | off | 25 | 4.4000 | 1.993 | 0.0042 | 1.000–1.014 | 5.04–5.39 | 1.71–2.12 | 1.76–1.85 | 1.14 | n/a | n/a | n/a | 0.0000 | 22.467 | not tested (cap) |
| 2 | 3.0 | 8.0 | 1.0 | off | 100 | 1.2000 | 2.621 | 0.0041 | 0.989–1.007 | 4.87–5.23 | 1.38–1.73 | 1.81–1.90 | 1.15 | n/a | n/a | n/a | 0.0000 | 22.320 | not tested (cap) |
| 2 | 3.0 | 6.0 | 1.0 | off | 25 | 4.2000 | 1.905 | 0.0042 | 0.997–1.022 | 5.28–5.65 | 1.72–2.10 | 1.79–1.88 | 1.14 | n/a | n/a | n/a | 0.0000 | 22.535 | not tested (cap) |
| 2 | 3.0 | 6.0 | 2.0 | off | 100 | 1.0500 | 2.405 | 0.0041 | 0.998–1.005 | 5.19–5.51 | 1.56–1.89 | 1.79–1.88 | 1.13 | n/a | n/a | n/a | 0.0000 | 22.544 | not tested (cap) |
| 2 | 3.0 | 6.0 | 0.0 | on | 25 | 4.2000 | 1.862 | 0.0050 | 0.984–1.009 | 5.05–5.45 | 1.45–1.80 | 1.78–1.88 | 1.16 | n/a | n/a | n/a | 0.0000 | 22.870 | not tested (cap) |
| 2 | 3.0 | 6.0 | 2.0 | off | 400 | 0.2750 | 2.756 | 0.0044 | 0.992–1.012 | 5.22–5.53 | 1.48–1.81 | 1.84–1.89 | 1.13 | n/a | n/a | n/a | 0.0000 | 22.963 | not tested (cap) |
| 2 | 3.0 | 8.0 | 2.0 | on | 25 | 3.8000 | 1.836 | 0.0052 | 0.991–1.005 | 4.94–5.24 | 1.73–2.08 | 1.69–1.78 | 1.13 | n/a | n/a | n/a | 0.0000 | 22.943 | not tested (cap) |
| 2 | 3.0 | 6.0 | 1.0 | off | 100 | 1.2000 | 2.398 | 0.0042 | 0.990–1.015 | 5.22–5.61 | 1.43–1.77 | 1.89–2.00 | 1.16 | n/a | n/a | n/a | 0.0000 | 23.305 | not tested (cap) |
| 2 | 3.0 | 8.0 | 1.0 | on | 25 | 4.2000 | 1.809 | 0.0053 | 0.986–1.001 | 4.95–5.29 | 1.69–2.05 | 1.72–1.81 | 1.14 | n/a | n/a | n/a | 0.0000 | 23.347 | not tested (cap) |
| 2 | 3.0 | 8.0 | 2.0 | off | 25 | 4.0000 | 2.081 | 0.0044 | 0.991–1.018 | 5.22–5.53 | 2.07–2.46 | 1.75–1.84 | 1.12 | n/a | n/a | n/a | 0.0000 | 23.384 | not tested (cap) |
| 2 | 3.0 | 8.0 | 2.0 | on | 100 | 1.0500 | 2.313 | 0.0050 | 0.995–1.013 | 4.87–5.17 | 1.55–1.87 | 1.77–1.84 | 1.13 | n/a | n/a | n/a | 0.0000 | 23.399 | not tested (cap) |
| 2 | 3.0 | 6.0 | 0.0 | off | 25 | 4.4000 | 1.910 | 0.0043 | 0.992–1.007 | 5.41–5.81 | 1.75–2.20 | 1.86–1.97 | 1.14 | n/a | n/a | n/a | 0.0000 | 23.532 | not tested (cap) |
| 2 | 3.0 | 8.0 | 1.0 | off | 25 | 4.4000 | 2.067 | 0.0044 | 0.998–1.003 | 5.25–5.60 | 2.04–2.50 | 1.79–1.88 | 1.13 | n/a | n/a | n/a | 0.0000 | 23.719 | not tested (cap) |
| 2 | 3.0 | 8.0 | 2.0 | off | 100 | 1.1000 | 2.615 | 0.0043 | 0.995–1.003 | 5.13–5.44 | 1.86–2.18 | 1.82–1.90 | 1.12 | n/a | n/a | n/a | 0.0000 | 23.602 | not tested (cap) |
| 2 | 3.0 | 8.0 | 2.0 | on | 400 | 0.2750 | 2.825 | 0.0053 | 0.995–1.012 | 4.90–5.20 | 1.50–1.85 | 1.83–1.91 | 1.13 | n/a | n/a | n/a | 0.0000 | 23.798 | not tested (cap) |
| 2 | 3.0 | 6.0 | 2.0 | on | 25 | 3.8000 | 1.849 | 0.0052 | 0.987–1.006 | 5.27–5.61 | 1.77–2.15 | 1.74–1.86 | 1.13 | n/a | n/a | n/a | 0.0000 | 24.074 | not tested (cap) |
| 2 | 3.0 | 8.0 | 1.0 | on | 100 | 1.2000 | 2.555 | 0.0054 | 0.998–1.016 | 4.92–5.27 | 1.44–1.79 | 1.83–1.91 | 1.15 | n/a | n/a | n/a | 0.0000 | 24.151 | not tested (cap) |
| 2 | 3.0 | 6.0 | 2.0 | off | 25 | 4.0000 | 1.959 | 0.0044 | 0.983–1.001 | 5.60–5.94 | 2.13–2.51 | 1.83–1.92 | 1.12 | n/a | n/a | n/a | 0.0000 | 24.499 | not tested (cap) |
| 2 | 3.0 | 6.0 | 2.0 | on | 100 | 1.0500 | 2.430 | 0.0052 | 0.980–1.007 | 5.21–5.53 | 1.57–1.93 | 1.80–1.89 | 1.13 | n/a | n/a | n/a | 0.0000 | 24.413 | not tested (cap) |
| 2 | 3.0 | 8.0 | 0.0 | on | 100 | 1.2500 | 2.558 | 0.0053 | 0.988–1.012 | 4.90–5.30 | 1.29–1.67 | 1.86–1.98 | 1.16 | n/a | n/a | n/a | 0.0000 | 24.482 | not tested (cap) |
| 2 | 3.0 | 6.0 | 1.0 | on | 25 | 4.2000 | 1.855 | 0.0054 | 0.983–1.013 | 5.30–5.67 | 1.75–2.13 | 1.81–1.90 | 1.14 | n/a | n/a | n/a | 0.0000 | 24.598 | not tested (cap) |
| 2 | 3.0 | 8.0 | 0.0 | off | 25 | 4.6000 | 2.076 | 0.0046 | 1.000–1.009 | 5.39–5.75 | 2.12–2.59 | 1.85–1.94 | 1.13 | n/a | n/a | n/a | 0.0000 | 24.651 | not tested (cap) |
| 2 | 3.0 | 8.0 | 0.0 | on | 25 | 4.4000 | 1.821 | 0.0055 | 0.994–1.010 | 5.07–5.42 | 1.73–2.16 | 1.79–1.86 | 1.14 | n/a | n/a | n/a | 0.0000 | 24.577 | not tested (cap) |
| 2 | 3.0 | 6.0 | 2.0 | off | 100 | 1.1000 | 2.468 | 0.0045 | 0.997–1.009 | 5.51–5.83 | 1.89–2.23 | 1.88–1.94 | 1.13 | n/a | n/a | n/a | 0.0000 | 24.920 | not tested (cap) |
| 2 | 3.0 | 6.0 | 1.0 | off | 25 | 4.4000 | 1.905 | 0.0046 | 0.997–1.022 | 5.65–6.01 | 2.10–2.54 | 1.88–1.98 | 1.13 | n/a | n/a | n/a | 0.0000 | 25.136 | not tested (cap) |
| 2 | 3.0 | 6.0 | 2.0 | off | 400 | 0.2875 | 2.913 | 0.0046 | 0.992–1.012 | 5.53–5.88 | 1.81–2.20 | 1.89–1.99 | 1.13 | n/a | n/a | n/a | 0.0000 | 25.304 | not tested (cap) |
| 2 | 3.0 | 8.0 | 2.0 | off | 25 | 4.2000 | 2.081 | 0.0047 | 0.991–1.002 | 5.53–5.85 | 2.46–2.88 | 1.84–1.94 | 1.12 | n/a | n/a | n/a | 0.0000 | 25.722 | not tested (cap) |
| 2 | 3.0 | 8.0 | 2.0 | on | 25 | 4.0000 | 1.836 | 0.0055 | 0.987–1.011 | 5.24–5.56 | 2.08–2.47 | 1.78–1.87 | 1.12 | n/a | n/a | n/a | 0.0000 | 25.740 | not tested (cap) |
| 2 | 3.0 | 6.0 | 0.0 | on | 25 | 4.4000 | 1.836 | 0.0059 | 0.984–1.009 | 5.45–5.83 | 1.80–2.23 | 1.88–1.99 | 1.15 | n/a | n/a | n/a | 0.0000 | 25.771 | not tested (cap) |
| 2 | 3.0 | 8.0 | 2.0 | on | 100 | 1.1000 | 2.307 | 0.0055 | 0.995–1.012 | 5.17–5.48 | 1.87–2.22 | 1.84–1.92 | 1.12 | n/a | n/a | n/a | 0.0000 | 25.790 | not tested (cap) |
| 2 | 3.0 | 8.0 | 1.0 | off | 25 | 4.6000 | 2.067 | 0.0048 | 0.991–1.003 | 5.60–5.94 | 2.50–2.96 | 1.88–1.97 | 1.12 | n/a | n/a | n/a | 0.0000 | 26.043 | not tested (cap) |
| 2 | 3.0 | 8.0 | 1.0 | on | 25 | 4.4000 | 1.774 | 0.0059 | 0.986–1.003 | 5.29–5.63 | 2.05–2.50 | 1.81–1.90 | 1.13 | n/a | n/a | n/a | 0.0000 | 26.162 | not tested (cap) |
| 2 | 3.0 | 6.0 | 2.0 | on | 25 | 4.0000 | 1.849 | 0.0057 | 0.989–1.022 | 5.61–5.95 | 2.15–2.57 | 1.86–1.95 | 1.12 | n/a | n/a | n/a | 0.0000 | 27.037 | not tested (cap) |
| 2 | 3.0 | 6.0 | 2.0 | on | 100 | 1.1000 | 2.430 | 0.0058 | 0.977–1.007 | 5.53–5.86 | 1.93–2.30 | 1.89–1.98 | 1.12 | n/a | n/a | n/a | 0.0000 | 27.025 | not tested (cap) |
| 2 | 3.0 | 6.0 | 1.0 | on | 25 | 4.4000 | 1.835 | 0.0060 | 0.983–1.013 | 5.67–6.05 | 2.13–2.56 | 1.90–2.00 | 1.13 | n/a | n/a | n/a | 0.0000 | 27.377 | not tested (cap) |
| 2 | 3.0 | 8.0 | 0.0 | on | 25 | 4.6000 | 1.784 | 0.0061 | 0.989–1.010 | 5.42–5.78 | 2.16–2.59 | 1.86–1.98 | 1.13 | n/a | n/a | n/a | 0.0000 | 27.371 | not tested (cap) |
| 2 | 3.0 | 8.0 | 2.0 | on | 25 | 4.2000 | 1.836 | 0.0063 | 0.987–1.011 | 5.56–5.87 | 2.47–2.90 | 1.87–1.97 | 1.11 | n/a | n/a | n/a | 0.0000 | 28.342 | not tested (cap) |
| 2 | 3.0 | 8.0 | 1.0 | on | 25 | 4.6000 | 1.801 | 0.0065 | 0.994–1.006 | 5.63–5.96 | 2.50–2.94 | 1.90–1.99 | 1.12 | n/a | n/a | n/a | 0.0000 | 28.994 | not tested (cap) |
| 2 | 4.0 | 2.0 | 1.0 | off | 100 | 1.4000 | 2.391 | 0.0063 | 0.994–1.009 | 7.45–7.93 | 3.24–3.80 | 1.29–1.36 | 1.13 | n/a | n/a | n/a | 0.0000 | 35.523 | not tested (cap) |
| 2 | 4.0 | 2.0 | 2.0 | on | 100 | 1.3000 | 2.767 | 0.0087 | 0.996–1.007 | 7.57–8.00 | 3.68–4.15 | 1.32–1.36 | 1.12 | n/a | n/a | n/a | 0.0000 | 39.653 | not tested (cap) |
| 2 | 3.0 | 8.0 | 2.0 | on | 400 | 0.2875 | 2.853 | 0.0057 | 0.989–1.011 | 5.20–5.52 | 1.85–2.23 | 1.91–2.00 | 1.12 | n/a | n/a | n/a | 0.0021 | 26.437 | R-screen (KC) |
| 2 | 3.0 | 8.0 | 1.0 | off | 100 | 1.2500 | 2.669 | 0.0044 | 0.989–1.007 | 5.23–5.58 | 1.73–2.16 | 1.90–2.01 | 1.14 | n/a | n/a | n/a | 0.0026 | 24.838 | R-screen (KC) |
| 1 | 3.0 | 4.0 | 0.0 | off | 100 | 1.1500 | 3.011 | 0.0038 | 0.993–1.003 | 4.84–5.27 | 0.88–1.11 | 1.92–2.00 | 1.18 | n/a | n/a | n/a | 0.0043 | 19.889 | R-screen (F, KC) |
| 2 | 3.0 | 6.0 | 2.0 | off | 25 | 4.2000 | 1.959 | 0.0050 | 0.983–1.007 | 5.94–6.28 | 2.51–2.97 | 1.92–2.01 | 1.12 | n/a | n/a | n/a | 0.0045 | 26.983 | R-screen (KC) |
| 2 | 3.0 | 8.0 | 2.0 | off | 400 | 0.2875 | 3.015 | 0.0045 | 0.993–1.008 | 5.15–5.47 | 1.79–2.14 | 1.86–1.94 | 1.12 | n/a | n/a | n/a | 0.0049 | 24.292 | R-screen (F) |
| 1 | 4.0 | 3.0 | 0.0 | off | 100 | 1.5000 | 2.340 | 0.0064 | 0.995–1.007 | 7.56–8.04 | 3.46–4.09 | 1.39–1.46 | 1.13 | n/a | n/a | n/a | 0.0050 | 36.595 | R-screen (central) |
| 2 | 3.0 | 8.0 | 2.0 | off | 100 | 1.1500 | 2.758 | 0.0047 | 0.994–1.004 | 5.44–5.75 | 2.18–2.58 | 1.90–2.01 | 1.12 | n/a | n/a | n/a | 0.0069 | 26.029 | R-screen (KC) |
| 2 | 3.0 | 6.0 | 2.0 | off | 400 | 0.2000 | 3.007 | 0.0025 | 0.985–1.008 | 3.73–3.92 | 0.50–0.59 | 1.40–1.47 | 1.12 | n/a | n/a | n/a | 0.0072 | 16.835 | R-screen (F, DAN) |
| 2 | 3.0 | 6.0 | 2.0 | on | 400 | 0.2750 | 3.025 | 0.0053 | 1.002–1.024 | 5.24–5.57 | 1.54–1.88 | 1.84–1.93 | 1.13 | n/a | n/a | n/a | 0.0083 | 24.846 | R-screen (F) |
| 2 | 3.0 | 8.0 | 1.0 | on | 100 | 1.2500 | 2.357 | 0.0059 | 0.986–1.016 | 5.27–5.63 | 1.79–2.21 | 1.91–2.02 | 1.14 | n/a | n/a | n/a | 0.0086 | 27.166 | R-screen (KC) |
| 2 | 3.0 | 8.0 | 2.0 | on | 100 | 0.7500 | 2.671 | 0.0027 | 0.977–1.046 | 3.42–3.61 | 0.50–0.58 | 1.28–1.36 | 1.12 | n/a | n/a | n/a | 0.0093 | 16.018 | R-screen (DAN) |
| 2 | 3.0 | 6.0 | 2.0 | on | 100 | 0.7500 | 2.658 | 0.0028 | 1.005–1.020 | 3.68–3.87 | 0.50–0.60 | 1.36–1.43 | 1.11 | n/a | n/a | n/a | 0.0093 | 17.150 | R-screen (DAN) |
| 2 | 4.0 | 2.0 | 2.0 | off | 400 | 0.1750 | 2.614 | 0.0021 | 0.987–1.020 | 3.55–3.72 | 0.49–0.55 | 0.72–0.76 | 1.16 | n/a | n/a | n/a | 0.0106 | 19.857 | R-screen (DAN) |
| 2 | 3.0 | 6.0 | 1.0 | on | 100 | 1.2000 | 2.637 | 0.0057 | 0.996–1.009 | 5.27–5.66 | 1.47–1.87 | 1.92–2.02 | 1.15 | n/a | n/a | n/a | 0.0110 | 25.430 | R-screen (KC) |
| 2 | 3.0 | 6.0 | 2.0 | on | 25 | 4.2000 | 1.787 | 0.0062 | 0.989–1.022 | 5.95–6.28 | 2.57–2.98 | 1.95–2.02 | 1.12 | n/a | n/a | n/a | 0.0122 | 29.709 | R-screen (KC) |
| 2 | 3.0 | 8.0 | 1.0 | off | 400 | 0.3125 | 3.038 | 0.0041 | 0.981–1.009 | 4.71–5.07 | 1.14–1.43 | 1.85–1.95 | 1.16 | n/a | n/a | n/a | 0.0127 | 21.948 | R-screen (F) |
| 2 | 3.0 | 8.0 | 0.0 | off | 25 | 4.8000 | 2.094 | 0.0052 | 0.994–1.009 | 5.75–6.10 | 2.59–3.09 | 1.94–2.03 | 1.13 | n/a | n/a | n/a | 0.0155 | 27.126 | R-screen (KC) |
| 1 | 4.0 | 2.0 | 0.0 | off | 100 | 1.4500 | 2.244 | 0.0063 | 0.992–1.000 | 7.63–8.14 | 3.13–3.73 | 1.28–1.36 | 1.13 | n/a | n/a | n/a | 0.0177 | 36.198 | R-screen (central) |
| 1 | 3.0 | 8.0 | 0.0 | off | 100 | 1.3000 | 2.702 | 0.0047 | 0.995–1.004 | 5.24–5.65 | 1.58–2.01 | 1.94–2.04 | 1.15 | n/a | n/a | n/a | 0.0181 | 25.114 | R-screen (KC) |
| 2 | 3.0 | 8.0 | 2.0 | off | 25 | 4.4000 | 2.114 | 0.0051 | 0.994–1.014 | 5.85–6.17 | 2.88–3.35 | 1.94–2.04 | 1.11 | n/a | n/a | n/a | 0.0185 | 28.265 | R-screen (KC) |
| 2 | 3.0 | 8.0 | 2.0 | on | 400 | 0.2125 | 3.056 | 0.0031 | 0.988–1.011 | 3.65–3.86 | 0.58–0.69 | 1.42–1.49 | 1.13 | n/a | n/a | n/a | 0.0186 | 15.796 | R-screen (F) |
| 2 | 3.0 | 8.0 | 0.0 | on | 100 | 1.3000 | 2.245 | 0.0061 | 0.994–1.012 | 5.30–5.68 | 1.67–2.10 | 1.98–2.04 | 1.15 | n/a | n/a | n/a | 0.0205 | 27.692 | R-screen (KC) |
| 2 | 3.0 | 8.0 | 1.0 | on | 100 | 1.1000 | 3.062 | 0.0045 | 0.971–1.004 | 4.26–4.59 | 0.90–1.14 | 1.66–1.77 | 1.16 | n/a | n/a | n/a | 0.0206 | 19.121 | R-screen (F) |
| 2 | 3.0 | 8.0 | 2.0 | on | 100 | 1.1500 | 2.249 | 0.0061 | 0.989–1.012 | 5.48–5.78 | 2.22–2.62 | 1.92–2.04 | 1.12 | n/a | n/a | n/a | 0.0212 | 28.364 | R-screen (KC) |
| 2 | 3.0 | 6.0 | 1.0 | off | 400 | 0.3000 | 3.068 | 0.0036 | 0.987–1.015 | 4.64–5.03 | 0.94–1.17 | 1.84–1.92 | 1.18 | n/a | n/a | n/a | 0.0224 | 20.538 | R-screen (F) |
| 2 | 3.0 | 6.0 | 2.0 | off | 100 | 1.1500 | 2.482 | 0.0049 | 0.995–1.009 | 5.83–6.18 | 2.23–2.63 | 1.94–2.05 | 1.12 | n/a | n/a | n/a | 0.0225 | 27.223 | R-screen (KC) |
| 2 | 3.0 | 6.0 | 2.0 | on | 400 | 0.2875 | 2.865 | 0.0059 | 0.989–1.024 | 5.57–5.92 | 1.88–2.30 | 1.93–2.05 | 1.13 | n/a | n/a | n/a | 0.0230 | 27.681 | R-screen (KC) |
| 2 | 3.0 | 6.0 | 2.0 | on | 400 | 0.2500 | 3.076 | 0.0047 | 0.983–1.002 | 4.64–4.94 | 1.00–1.25 | 1.68–1.78 | 1.14 | n/a | n/a | n/a | 0.0249 | 20.076 | R-screen (F) |
| 2 | 3.0 | 6.0 | 2.0 | on | 400 | 0.2625 | 3.076 | 0.0047 | 0.983–1.014 | 4.94–5.24 | 1.25–1.54 | 1.78–1.84 | 1.13 | n/a | n/a | n/a | 0.0249 | 22.809 | R-screen (F) |
| 2 | 3.0 | 8.0 | 0.0 | on | 25 | 4.8000 | 1.784 | 0.0067 | 0.989–1.005 | 5.78–6.13 | 2.59–3.11 | 1.98–2.05 | 1.12 | n/a | n/a | n/a | 0.0259 | 30.265 | R-screen (KC) |
| 1 | 3.0 | 3.0 | 0.0 | off | 100 | 1.1500 | 3.080 | 0.0041 | 1.000–1.012 | 5.16–5.61 | 1.02–1.26 | 1.93–1.99 | 1.19 | n/a | n/a | n/a | 0.0262 | 20.342 | R-screen (F) |
| 2 | 3.0 | 8.0 | 2.0 | off | 100 | 0.7500 | 2.578 | 0.0023 | 0.992–1.015 | 3.40–3.60 | 0.49–0.59 | 1.29–1.36 | 1.12 | n/a | n/a | n/a | 0.0268 | 16.331 | R-screen (DAN) |
| 2 | 3.0 | 8.0 | 2.0 | on | 25 | 4.4000 | 1.803 | 0.0068 | 0.995–1.004 | 5.87–6.19 | 2.90–3.34 | 1.97–2.06 | 1.11 | n/a | n/a | n/a | 0.0277 | 31.058 | R-screen (KC) |
| 2 | 3.0 | 8.0 | 2.0 | off | 400 | 0.2000 | 2.955 | 0.0024 | 0.957–1.010 | 3.46–3.64 | 0.48–0.58 | 1.33–1.38 | 1.12 | n/a | n/a | n/a | 0.0308 | 16.294 | R-screen (DAN) |
| 2 | 3.0 | 6.0 | 0.0 | on | 25 | 4.6000 | 1.768 | 0.0063 | 0.996–1.016 | 5.83–6.22 | 2.23–2.69 | 1.99–2.06 | 1.13 | n/a | n/a | n/a | 0.0309 | 28.748 | R-screen (KC) |
| 1 | 3.0 | 6.0 | 0.0 | off | 100 | 1.1000 | 3.094 | 0.0032 | 0.977–1.007 | 4.01–4.39 | 0.60–0.76 | 1.68–1.78 | 1.19 | n/a | n/a | n/a | 0.0310 | 17.964 | R-screen (F) |
| 2 | 3.0 | 8.0 | 1.0 | off | 25 | 4.8000 | 2.088 | 0.0052 | 0.991–1.001 | 5.94–6.29 | 2.96–3.46 | 1.97–2.07 | 1.11 | n/a | n/a | n/a | 0.0333 | 28.533 | R-screen (KC) |
| 2 | 3.0 | 6.0 | 0.0 | off | 25 | 4.6000 | 1.914 | 0.0047 | 0.996–1.009 | 5.81–6.19 | 2.20–2.63 | 1.97–2.07 | 1.13 | n/a | n/a | n/a | 0.0338 | 26.141 | R-screen (KC) |
| 2 | 3.0 | 6.0 | 2.0 | on | 100 | 1.1500 | 2.293 | 0.0065 | 0.977–1.016 | 5.86–6.21 | 2.30–2.72 | 1.98–2.07 | 1.12 | n/a | n/a | n/a | 0.0352 | 29.801 | R-screen (KC) |
| 2 | 3.0 | 6.0 | 0.0 | on | 100 | 1.2500 | 2.756 | 0.0058 | 0.996–1.009 | 5.27–5.70 | 1.35–1.73 | 1.98–2.07 | 1.17 | n/a | n/a | n/a | 0.0353 | 25.636 | R-screen (KC) |
| 2 | 3.0 | 8.0 | 2.0 | off | 100 | 1.2000 | 2.821 | 0.0052 | 0.994–1.009 | 5.75–6.06 | 2.58–2.98 | 2.01–2.07 | 1.11 | n/a | n/a | n/a | 0.0356 | 28.441 | R-screen (KC) |
| 2 | 3.0 | 8.0 | 2.0 | on | 400 | 0.3000 | 2.853 | 0.0061 | 0.989–1.008 | 5.52–5.82 | 2.23–2.64 | 2.00–2.08 | 1.12 | n/a | n/a | n/a | 0.0371 | 29.208 | R-screen (KC) |
| 2 | 3.0 | 8.0 | 1.0 | off | 100 | 1.3000 | 2.735 | 0.0050 | 0.994–1.008 | 5.58–5.94 | 2.16–2.63 | 2.01–2.08 | 1.13 | n/a | n/a | n/a | 0.0376 | 27.586 | R-screen (KC) |
| 2 | 4.0 | 2.0 | 2.0 | off | 100 | 1.3500 | 2.272 | 0.0068 | 0.996–1.004 | 7.89–8.32 | 4.12–4.63 | 1.37–1.44 | 1.11 | n/a | n/a | n/a | 0.0392 | 38.291 | R-screen (central) |
| 2 | 3.0 | 6.0 | 1.0 | off | 400 | 0.3125 | 3.068 | 0.0041 | 0.979–1.015 | 5.03–5.45 | 1.17–1.48 | 1.92–2.04 | 1.17 | n/a | n/a | n/a | 0.0402 | 22.761 | R-screen (F, KC) |
| 2 | 3.0 | 8.0 | 1.0 | on | 25 | 4.8000 | 1.801 | 0.0071 | 0.994–1.015 | 5.96–6.30 | 2.94–3.48 | 1.99–2.08 | 1.12 | n/a | n/a | n/a | 0.0409 | 31.765 | R-screen (KC) |
| 1 | 3.0 | 6.0 | 0.0 | off | 100 | 1.2500 | 2.418 | 0.0041 | 0.984–1.004 | 5.22–5.67 | 1.26–1.65 | 1.96–2.08 | 1.17 | n/a | n/a | n/a | 0.0412 | 23.667 | R-screen (KC) |
| 1 | 3.0 | 3.0 | 0.0 | off | 100 | 1.2000 | 2.711 | 0.0042 | 0.989–1.012 | 5.61–6.10 | 1.26–1.58 | 1.99–2.08 | 1.18 | n/a | n/a | n/a | 0.0416 | 22.913 | R-screen (KC) |
| 2 | 3.0 | 6.0 | 1.0 | off | 100 | 1.2500 | 2.450 | 0.0045 | 0.988–1.009 | 5.61–6.01 | 1.77–2.22 | 2.00–2.09 | 1.14 | n/a | n/a | n/a | 0.0421 | 26.074 | R-screen (KC) |
| 2 | 4.0 | 2.0 | 1.0 | on | 25 | 5.2000 | 2.012 | 0.0089 | 0.999–1.012 | 7.90–8.35 | 4.22–4.78 | 1.28–1.35 | 1.11 | n/a | n/a | n/a | 0.0429 | 40.457 | R-screen (central) |
| 2 | 3.0 | 6.0 | 1.0 | off | 25 | 4.6000 | 1.909 | 0.0049 | 0.993–1.011 | 6.01–6.38 | 2.54–3.05 | 1.98–2.09 | 1.13 | n/a | n/a | n/a | 0.0448 | 27.552 | R-screen (KC) |
| 1 | 3.0 | 4.0 | 0.0 | off | 100 | 1.2000 | 2.511 | 0.0042 | 0.995–1.010 | 5.27–5.72 | 1.11–1.41 | 2.00–2.09 | 1.18 | n/a | n/a | n/a | 0.0455 | 22.245 | R-screen (KC) |
| 2 | 3.0 | 6.0 | 1.0 | on | 25 | 4.6000 | 1.835 | 0.0065 | 0.992–1.005 | 6.05–6.41 | 2.56–3.05 | 2.00–2.09 | 1.12 | n/a | n/a | n/a | 0.0462 | 30.390 | R-screen (KC) |
| 2 | 3.0 | 8.0 | 1.0 | on | 100 | 1.3000 | 2.238 | 0.0065 | 0.986–1.009 | 5.63–6.00 | 2.21–2.66 | 2.02–2.10 | 1.13 | n/a | n/a | n/a | 0.0479 | 30.238 | R-screen (KC) |
| 2 | 4.0 | 2.0 | 1.0 | off | 100 | 1.4500 | 2.344 | 0.0072 | 0.997–1.005 | 7.93–8.41 | 3.80–4.41 | 1.36–1.45 | 1.12 | n/a | n/a | n/a | 0.0495 | 38.550 | R-screen (central) |
| 2 | 3.0 | 6.0 | 2.0 | off | 25 | 4.4000 | 1.969 | 0.0053 | 0.992–1.007 | 6.28–6.64 | 2.97–3.43 | 2.01–2.10 | 1.11 | n/a | n/a | n/a | 0.0505 | 29.431 | R-screen (KC) |
| 2 | 3.0 | 6.0 | 1.0 | on | 100 | 1.2500 | 2.468 | 0.0063 | 0.992–1.009 | 5.66–6.06 | 1.87–2.29 | 2.02–2.10 | 1.14 | n/a | n/a | n/a | 0.0505 | 28.439 | R-screen (KC) |
| 2 | 3.0 | 8.0 | 1.0 | off | 400 | 0.3000 | 3.167 | 0.0035 | 0.981–1.005 | 4.35–4.71 | 0.91–1.14 | 1.79–1.85 | 1.17 | n/a | n/a | n/a | 0.0541 | 19.734 | R-screen (F) |
| 2 | 4.0 | 2.0 | 2.0 | on | 100 | 1.3500 | 2.767 | 0.0093 | 0.992–1.004 | 8.00–8.45 | 4.15–4.69 | 1.36–1.44 | 1.11 | n/a | n/a | n/a | 0.0542 | 42.685 | R-screen (central) |
| 2 | 3.0 | 8.0 | 2.0 | on | 100 | 1.2000 | 2.246 | 0.0067 | 0.988–1.004 | 5.78–6.10 | 2.62–3.04 | 2.04–2.12 | 1.11 | n/a | n/a | n/a | 0.0563 | 31.228 | R-screen (KC) |
| 2 | 3.0 | 6.0 | 2.0 | on | 400 | 0.2125 | 3.179 | 0.0031 | 0.986–1.005 | 3.92–4.13 | 0.59–0.69 | 1.47–1.54 | 1.13 | n/a | n/a | n/a | 0.0580 | 16.146 | R-screen (F) |
| 2 | 3.0 | 8.0 | 2.0 | off | 25 | 4.6000 | 2.181 | 0.0055 | 0.998–1.014 | 6.17–6.49 | 3.35–3.80 | 2.04–2.12 | 1.11 | n/a | n/a | n/a | 0.0588 | 30.531 | R-screen (KC) |
| 2 | 3.0 | 6.0 | 1.0 | off | 100 | 0.9500 | 3.040 | 0.0025 | 0.994–1.008 | 3.65–3.89 | 0.48–0.57 | 1.47–1.54 | 1.15 | n/a | n/a | n/a | 0.0594 | 18.858 | R-screen (F, DAN) |
| 2 | 4.0 | 2.0 | 0.0 | off | 25 | 5.4000 | 1.629 | 0.0066 | 0.995–1.005 | 8.05–8.49 | 4.34–4.93 | 1.30–1.36 | 1.11 | n/a | n/a | n/a | 0.0597 | 37.021 | R-screen (central) |
| 2 | 4.0 | 2.0 | 0.0 | on | 100 | 1.4000 | 3.187 | 0.0085 | 0.997–1.010 | 7.23–7.76 | 2.66–3.13 | 1.22–1.27 | 1.14 | n/a | n/a | n/a | 0.0603 | 37.721 | R-screen (F) |
| 2 | 3.0 | 8.0 | 0.0 | off | 25 | 5.0000 | 2.156 | 0.0055 | 0.991–1.013 | 6.10–6.45 | 3.09–3.61 | 2.03–2.13 | 1.12 | n/a | n/a | n/a | 0.0618 | 29.556 | R-screen (KC) |
| 2 | 3.0 | 6.0 | 2.0 | on | 400 | 0.3000 | 2.805 | 0.0066 | 0.989–1.010 | 5.92–6.27 | 2.30–2.73 | 2.05–2.13 | 1.12 | n/a | n/a | n/a | 0.0629 | 30.528 | R-screen (KC) |
| 2 | 4.0 | 2.0 | 1.0 | on | 100 | 1.4500 | 2.994 | 0.0095 | 0.997–1.005 | 8.04–8.53 | 3.84–4.45 | 1.36–1.44 | 1.12 | n/a | n/a | n/a | 0.0643 | 43.559 | R-screen (central) |
| 2 | 3.0 | 6.0 | 2.0 | on | 25 | 4.4000 | 1.777 | 0.0068 | 0.994–1.011 | 6.28–6.65 | 2.98–3.47 | 2.02–2.13 | 1.12 | n/a | n/a | n/a | 0.0648 | 32.327 | R-screen (KC) |
| 2 | 3.0 | 6.0 | 0.0 | on | 100 | 1.2000 | 3.202 | 0.0050 | 0.978–1.009 | 4.83–5.27 | 1.03–1.35 | 1.87–1.98 | 1.18 | n/a | n/a | n/a | 0.0651 | 22.388 | R-screen (F) |
| 2 | 3.0 | 8.0 | 0.0 | on | 100 | 1.3500 | 2.206 | 0.0069 | 0.986–1.011 | 5.68–6.09 | 2.10–2.63 | 2.04–2.14 | 1.14 | n/a | n/a | n/a | 0.0683 | 30.859 | R-screen (KC) |
| 2 | 4.0 | 2.0 | 1.0 | off | 400 | 0.3625 | 3.213 | 0.0063 | 0.995–1.001 | 7.34–7.85 | 2.80–3.37 | 1.35–1.43 | 1.14 | n/a | n/a | n/a | 0.0685 | 36.326 | R-screen (F) |
| 2 | 3.0 | 6.0 | 2.0 | off | 100 | 1.2000 | 2.624 | 0.0052 | 0.995–1.013 | 6.18–6.53 | 2.63–3.09 | 2.05–2.15 | 1.11 | n/a | n/a | n/a | 0.0721 | 29.680 | R-screen (KC) |
| 2 | 3.0 | 6.0 | 0.0 | off | 25 | 4.8000 | 1.914 | 0.0051 | 0.997–1.009 | 6.19–6.56 | 2.63–3.15 | 2.07–2.15 | 1.12 | n/a | n/a | n/a | 0.0730 | 28.749 | R-screen (KC) |
| 2 | 4.0 | 2.0 | 0.0 | off | 400 | 0.3750 | 3.207 | 0.0067 | 0.990–1.001 | 7.48–8.05 | 2.53–3.07 | 1.39–1.40 | 1.15 | n/a | n/a | n/a | 0.0731 | 37.291 | R-screen (F, central) |
| 2 | 3.0 | 8.0 | 0.0 | on | 25 | 5.0000 | 1.757 | 0.0075 | 0.994–1.007 | 6.13–6.48 | 3.11–3.61 | 2.05–2.15 | 1.12 | n/a | n/a | n/a | 0.0731 | 33.059 | R-screen (KC) |
| 2 | 3.0 | 8.0 | 2.0 | on | 25 | 4.6000 | 1.780 | 0.0073 | 0.995–1.003 | 6.19–6.50 | 3.34–3.82 | 2.06–2.15 | 1.10 | n/a | n/a | n/a | 0.0734 | 33.700 | R-screen (KC) |
| 2 | 3.0 | 8.0 | 1.0 | off | 100 | 1.3500 | 2.865 | 0.0054 | 0.996–1.008 | 5.94–6.31 | 2.63–3.16 | 2.08–2.15 | 1.13 | n/a | n/a | n/a | 0.0743 | 29.988 | R-screen (KC) |
| 2 | 3.0 | 8.0 | 1.0 | off | 400 | 0.2875 | 3.239 | 0.0032 | 0.992–1.008 | 4.03–4.35 | 0.70–0.91 | 1.69–1.79 | 1.17 | n/a | n/a | n/a | 0.0767 | 18.744 | R-screen (F) |
| 1 | 4.0 | 2.0 | 0.0 | off | 100 | 1.5000 | 2.289 | 0.0070 | 0.992–1.000 | 8.14–8.64 | 3.73–4.36 | 1.36–1.42 | 1.13 | n/a | n/a | n/a | 0.0767 | 39.280 | R-screen (central) |
| 1 | 3.0 | 8.0 | 0.0 | off | 100 | 1.3500 | 3.016 | 0.0050 | 0.995–1.008 | 5.65–6.03 | 2.01–2.55 | 2.04–2.15 | 1.14 | n/a | n/a | n/a | 0.0768 | 27.695 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 0.0 | on | 100 | 1.4500 | 3.133 | 0.0093 | 0.997–1.004 | 7.76–8.28 | 3.13–3.72 | 1.27–1.34 | 1.13 | n/a | n/a | n/a | 0.0771 | 41.064 | R-screen (F, central) |
| 2 | 3.0 | 8.0 | 2.0 | off | 100 | 1.2500 | 2.938 | 0.0055 | 0.999–1.009 | 6.06–6.39 | 2.98–3.43 | 2.07–2.17 | 1.11 | n/a | n/a | n/a | 0.0794 | 30.709 | R-screen (KC) |
| 2 | 3.0 | 6.0 | 1.0 | off | 25 | 4.8000 | 1.909 | 0.0054 | 0.993–1.010 | 6.38–6.76 | 3.05–3.51 | 2.09–2.17 | 1.12 | n/a | n/a | n/a | 0.0802 | 30.154 | R-screen (KC) |
| 2 | 3.0 | 8.0 | 2.0 | on | 400 | 0.3125 | 2.605 | 0.0068 | 0.995–1.006 | 5.82–6.14 | 2.64–3.06 | 2.08–2.17 | 1.11 | n/a | n/a | n/a | 0.0810 | 31.799 | R-screen (KC) |
| 2 | 3.0 | 8.0 | 1.0 | off | 25 | 5.0000 | 2.183 | 0.0056 | 0.994–1.002 | 6.29–6.62 | 3.46–4.00 | 2.07–2.17 | 1.11 | n/a | n/a | n/a | 0.0814 | 30.974 | R-screen (KC) |
| 2 | 3.0 | 8.0 | 1.0 | on | 400 | 0.3375 | 2.995 | 0.0066 | 0.992–1.015 | 5.52–5.91 | 1.91–2.36 | 2.07–2.17 | 1.15 | n/a | n/a | n/a | 0.0818 | 29.973 | R-screen (KC) |
| 2 | 3.0 | 6.0 | 1.0 | off | 100 | 1.3000 | 2.504 | 0.0050 | 0.988–1.006 | 6.01–6.40 | 2.22–2.68 | 2.09–2.17 | 1.13 | n/a | n/a | n/a | 0.0819 | 28.897 | R-screen (KC) |
| 1 | 3.0 | 6.0 | 0.0 | off | 100 | 1.3000 | 2.491 | 0.0047 | 0.991–1.008 | 5.67–6.08 | 1.65–2.08 | 2.08–2.17 | 1.15 | n/a | n/a | n/a | 0.0825 | 26.580 | R-screen (KC) |
| 2 | 3.0 | 8.0 | 1.0 | off | 100 | 0.9500 | 2.954 | 0.0026 | 0.976–1.015 | 3.39–3.63 | 0.46–0.55 | 1.39–1.47 | 1.15 | n/a | n/a | n/a | 0.0827 | 18.155 | R-screen (DAN) |
| 2 | 3.0 | 6.0 | 0.0 | on | 25 | 4.8000 | 1.767 | 0.0071 | 1.001–1.016 | 6.22–6.60 | 2.69–3.18 | 2.06–2.17 | 1.12 | n/a | n/a | n/a | 0.0830 | 31.717 | R-screen (KC) |
| 2 | 3.0 | 6.0 | 0.0 | on | 100 | 1.3000 | 2.389 | 0.0063 | 0.996–1.009 | 5.70–6.14 | 1.73–2.16 | 2.07–2.17 | 1.15 | n/a | n/a | n/a | 0.0831 | 29.074 | R-screen (KC) |
| 2 | 3.0 | 6.0 | 2.0 | off | 400 | 0.3000 | 3.101 | 0.0050 | 0.992–1.009 | 5.88–6.22 | 2.20–2.64 | 1.99–2.10 | 1.12 | n/a | n/a | n/a | 0.0833 | 27.929 | R-screen (F, KC) |
| 2 | 3.0 | 8.0 | 1.0 | on | 100 | 1.3500 | 2.172 | 0.0072 | 0.996–1.004 | 6.00–6.37 | 2.66–3.24 | 2.10–2.18 | 1.13 | n/a | n/a | n/a | 0.0843 | 33.364 | R-screen (KC) |
| 2 | 3.0 | 8.0 | 1.0 | on | 25 | 5.0000 | 1.787 | 0.0079 | 0.994–1.015 | 6.30–6.64 | 3.48–3.99 | 2.08–2.18 | 1.11 | n/a | n/a | n/a | 0.0864 | 34.467 | R-screen (KC) |
| 2 | 3.0 | 8.0 | 0.0 | off | 400 | 0.3250 | 3.221 | 0.0043 | 0.993–1.012 | 4.43–4.91 | 0.78–1.09 | 1.89–2.03 | 1.22 | n/a | n/a | n/a | 0.0885 | 21.253 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 2.0 | off | 400 | 0.3500 | 3.131 | 0.0072 | 0.994–1.002 | 7.92–8.37 | 4.02–4.58 | 1.41–1.51 | 1.11 | n/a | n/a | n/a | 0.0886 | 39.160 | R-screen (F, central) |
| 2 | 3.0 | 6.0 | 1.0 | on | 25 | 4.8000 | 1.752 | 0.0072 | 0.992–1.004 | 6.41–6.78 | 3.05–3.56 | 2.09–2.19 | 1.12 | n/a | n/a | n/a | 0.0888 | 33.343 | R-screen (KC) |
| 2 | 3.0 | 8.0 | 2.0 | on | 100 | 1.2500 | 2.149 | 0.0073 | 0.988–1.007 | 6.10–6.42 | 3.04–3.50 | 2.12–2.19 | 1.11 | n/a | n/a | n/a | 0.0906 | 34.105 | R-screen (KC) |
| 2 | 4.0 | 2.0 | 2.0 | off | 100 | 1.4000 | 2.405 | 0.0073 | 0.993–1.004 | 8.32–8.76 | 4.63–5.24 | 1.44–1.50 | 1.11 | n/a | n/a | n/a | 0.0907 | 41.034 | R-screen (central) |
| 2 | 3.0 | 6.0 | 1.0 | on | 100 | 1.3000 | 2.335 | 0.0069 | 0.992–1.006 | 6.06–6.45 | 2.29–2.78 | 2.10–2.19 | 1.13 | n/a | n/a | n/a | 0.0916 | 31.633 | R-screen (KC) |
| 1 | 3.0 | 2.0 | 0.0 | off | 100 | 1.2500 | 2.928 | 0.0052 | 1.002–1.005 | 6.63–7.19 | 1.90–2.29 | 2.09–2.19 | 1.17 | n/a | n/a | n/a | 0.0916 | 27.815 | R-screen (KC) |
| 1 | 3.0 | 3.0 | 0.0 | off | 100 | 1.2500 | 2.459 | 0.0046 | 0.989–1.007 | 6.10–6.60 | 1.58–1.96 | 2.08–2.19 | 1.17 | n/a | n/a | n/a | 0.0923 | 26.084 | R-screen (KC) |
| 2 | 3.0 | 6.0 | 1.0 | off | 400 | 0.3250 | 3.082 | 0.0047 | 0.979–1.004 | 5.45–5.87 | 1.48–1.86 | 2.04–2.14 | 1.16 | n/a | n/a | n/a | 0.0925 | 25.573 | R-screen (F, KC) |
| 2 | 3.0 | 6.0 | 2.0 | on | 100 | 1.2000 | 2.293 | 0.0068 | 0.993–1.016 | 6.21–6.56 | 2.72–3.16 | 2.07–2.19 | 1.11 | n/a | n/a | n/a | 0.0930 | 32.555 | R-screen (KC) |
| 2 | 4.0 | 2.0 | 1.0 | on | 25 | 5.4000 | 1.948 | 0.0095 | 0.996–1.012 | 8.35–8.79 | 4.78–5.35 | 1.35–1.41 | 1.11 | n/a | n/a | n/a | 0.0940 | 43.407 | R-screen (central) |
| 2 | 4.0 | 2.0 | 0.0 | on | 100 | 1.5000 | 2.981 | 0.0098 | 0.997–1.004 | 8.28–8.79 | 3.72–4.38 | 1.34–1.41 | 1.12 | n/a | n/a | n/a | 0.0945 | 44.546 | R-screen (central) |
| 2 | 3.0 | 8.0 | 1.0 | on | 100 | 1.0500 | 3.302 | 0.0039 | 0.974–1.008 | 3.94–4.26 | 0.71–0.90 | 1.58–1.66 | 1.17 | n/a | n/a | n/a | 0.0959 | 17.427 | R-screen (F) |
| 2 | 3.0 | 8.0 | 0.0 | on | 400 | 0.3500 | 2.903 | 0.0065 | 0.994–1.018 | 5.45–5.92 | 1.54–2.03 | 2.10–2.21 | 1.17 | n/a | n/a | n/a | 0.0986 | 30.100 | R-screen (KC) |
| 2 | 3.0 | 6.0 | 0.0 | off | 400 | 0.3375 | 3.016 | 0.0045 | 0.994–1.018 | 5.29–5.80 | 1.13–1.50 | 2.11–2.20 | 1.19 | n/a | n/a | n/a | 0.0992 | 25.333 | R-screen (F, KC) |
| 2 | 3.0 | 6.0 | 2.0 | off | 25 | 4.6000 | 1.969 | 0.0056 | 0.997–1.012 | 6.64–6.98 | 3.43–3.88 | 2.10–2.21 | 1.11 | n/a | n/a | n/a | 0.0995 | 31.842 | R-screen (KC) |
| 2 | 3.0 | 6.0 | 2.0 | on | 400 | 0.3125 | 2.756 | 0.0069 | 0.990–1.004 | 6.27–6.62 | 2.73–3.15 | 2.13–2.21 | 1.12 | n/a | n/a | n/a | 0.0997 | 33.120 | R-screen (KC) |
| 2 | 3.0 | 8.0 | 0.0 | off | 25 | 5.2000 | 2.180 | 0.0057 | 0.991–1.013 | 6.45–6.80 | 3.61–4.16 | 2.13–2.21 | 1.11 | n/a | n/a | n/a | 0.1001 | 31.993 | R-screen (KC) |
| 1 | 3.0 | 4.0 | 0.0 | off | 100 | 1.2500 | 2.378 | 0.0044 | 1.002–1.010 | 5.72–6.20 | 1.41–1.80 | 2.09–2.21 | 1.17 | n/a | n/a | n/a | 0.1009 | 25.299 | R-screen (KC) |
| 2 | 3.0 | 6.0 | 2.0 | on | 25 | 4.6000 | 1.777 | 0.0074 | 0.995–1.017 | 6.65–6.99 | 3.47–3.96 | 2.13–2.21 | 1.11 | n/a | n/a | n/a | 0.1012 | 35.074 | R-screen (KC) |
| 2 | 3.0 | 6.0 | 0.0 | off | 25 | 3.2000 | 2.399 | 0.0020 | 0.990–1.016 | 3.41–3.66 | 0.45–0.54 | 1.31–1.38 | 1.16 | n/a | n/a | n/a | 0.1028 | 19.682 | R-screen (DAN) |
| 2 | 3.0 | 8.0 | 2.0 | off | 25 | 4.8000 | 2.217 | 0.0058 | 0.998–1.005 | 6.49–6.82 | 3.80–4.34 | 2.12–2.22 | 1.10 | n/a | n/a | n/a | 0.1041 | 32.719 | R-screen (KC) |
| 2 | 4.0 | 2.0 | 2.0 | on | 100 | 1.4000 | 2.762 | 0.0098 | 0.992–1.002 | 8.45–8.88 | 4.69–5.28 | 1.44–1.51 | 1.10 | n/a | n/a | n/a | 0.1042 | 45.825 | R-screen (central) |
| 2 | 3.0 | 8.0 | 1.0 | on | 400 | 0.3500 | 2.862 | 0.0071 | 0.992–1.015 | 5.91–6.31 | 2.36–2.88 | 2.17–2.22 | 1.14 | n/a | n/a | n/a | 0.1048 | 33.409 | R-screen (KC) |
| 2 | 4.0 | 2.0 | 1.0 | off | 100 | 1.5000 | 2.418 | 0.0072 | 0.996–1.004 | 8.41–8.89 | 4.41–5.04 | 1.45–1.49 | 1.11 | n/a | n/a | n/a | 0.1051 | 41.562 | R-screen (central) |
| 2 | 3.0 | 8.0 | 1.0 | off | 400 | 0.3250 | 3.287 | 0.0043 | 0.990–1.009 | 5.07–5.45 | 1.43–1.79 | 1.95–2.03 | 1.15 | n/a | n/a | n/a | 0.1057 | 24.532 | R-screen (F, KC) |
| 2 | 3.0 | 6.0 | 2.0 | off | 100 | 1.2500 | 2.649 | 0.0057 | 0.996–1.013 | 6.53–6.87 | 3.09–3.52 | 2.15–2.23 | 1.11 | n/a | n/a | n/a | 0.1072 | 32.289 | R-screen (KC) |
| 2 | 3.0 | 8.0 | 0.0 | on | 100 | 1.4000 | 2.206 | 0.0076 | 0.986–1.001 | 6.09–6.49 | 2.63–3.18 | 2.14–2.23 | 1.13 | n/a | n/a | n/a | 0.1085 | 34.125 | R-screen (KC) |
| 2 | 3.0 | 8.0 | 2.0 | on | 25 | 4.8000 | 1.757 | 0.0078 | 0.995–1.005 | 6.50–6.82 | 3.82–4.34 | 2.15–2.23 | 1.10 | n/a | n/a | n/a | 0.1088 | 36.383 | R-screen (KC) |
| 2 | 4.0 | 2.0 | 0.0 | off | 25 | 5.6000 | 1.617 | 0.0070 | 0.995–1.005 | 8.49–8.93 | 4.93–5.53 | 1.36–1.45 | 1.11 | n/a | n/a | n/a | 0.1101 | 39.651 | R-screen (central) |
| 2 | 3.0 | 6.0 | 0.0 | off | 25 | 5.0000 | 1.900 | 0.0054 | 0.990–1.009 | 6.56–6.94 | 3.15–3.67 | 2.15–2.24 | 1.12 | n/a | n/a | n/a | 0.1130 | 31.319 | R-screen (KC) |
| 2 | 3.0 | 6.0 | 1.0 | on | 100 | 1.1000 | 3.359 | 0.0045 | 0.993–1.014 | 4.51–4.90 | 0.91–1.20 | 1.71–1.82 | 1.17 | n/a | n/a | n/a | 0.1130 | 20.037 | R-screen (F) |
| 2 | 3.0 | 8.0 | 0.0 | on | 25 | 5.2000 | 1.757 | 0.0083 | 0.994–1.007 | 6.48–6.82 | 3.61–4.17 | 2.15–2.24 | 1.11 | n/a | n/a | n/a | 0.1145 | 35.851 | R-screen (KC) |
| 2 | 3.0 | 8.0 | 0.0 | on | 25 | 3.2000 | 2.636 | 0.0022 | 0.987–1.021 | 3.17–3.41 | 0.45–0.52 | 1.23–1.32 | 1.18 | n/a | n/a | n/a | 0.1160 | 18.637 | R-screen (DAN) |
| 2 | 3.0 | 8.0 | 2.0 | off | 400 | 0.3000 | 3.270 | 0.0048 | 0.994–1.008 | 5.47–5.77 | 2.14–2.57 | 1.94–2.06 | 1.12 | n/a | n/a | n/a | 0.1161 | 26.802 | R-screen (F, KC) |
| 2 | 3.0 | 6.0 | 2.0 | off | 100 | 0.7000 | 2.731 | 0.0021 | 0.987–1.036 | 3.50–3.67 | 0.44–0.51 | 1.29–1.35 | 1.11 | n/a | n/a | n/a | 0.1189 | 19.190 | R-screen (DAN) |
| 1 | 3.0 | 6.0 | 0.0 | off | 100 | 1.3500 | 2.534 | 0.0052 | 0.991–1.008 | 6.08–6.50 | 2.08–2.63 | 2.17–2.25 | 1.14 | n/a | n/a | n/a | 0.1191 | 29.415 | R-screen (KC) |
| 2 | 3.0 | 6.0 | 2.0 | on | 100 | 1.2500 | 2.274 | 0.0074 | 0.993–1.001 | 6.56–6.91 | 3.16–3.63 | 2.19–2.25 | 1.11 | n/a | n/a | n/a | 0.1192 | 35.453 | R-screen (KC) |
| 2 | 3.0 | 6.0 | 2.0 | off | 400 | 0.3125 | 3.101 | 0.0055 | 0.992–1.009 | 6.22–6.57 | 2.64–3.06 | 2.10–2.18 | 1.11 | n/a | n/a | n/a | 0.1197 | 30.416 | R-screen (F, KC) |
| 2 | 3.0 | 8.0 | 2.0 | on | 400 | 0.3250 | 2.631 | 0.0073 | 0.995–1.006 | 6.14–6.47 | 3.06–3.50 | 2.17–2.26 | 1.11 | n/a | n/a | n/a | 0.1206 | 34.812 | R-screen (KC) |
| 2 | 4.0 | 2.0 | 1.0 | on | 100 | 1.5000 | 2.994 | 0.0102 | 0.998–1.005 | 8.53–9.03 | 4.45–5.15 | 1.44–1.54 | 1.12 | n/a | n/a | n/a | 0.1209 | 46.761 | R-screen (central) |
| 2 | 3.0 | 8.0 | 1.0 | off | 25 | 5.2000 | 2.229 | 0.0062 | 0.990–1.006 | 6.62–6.96 | 4.00–4.59 | 2.17–2.26 | 1.11 | n/a | n/a | n/a | 0.1213 | 33.370 | R-screen (KC) |
| 2 | 3.0 | 6.0 | 0.0 | on | 25 | 3.2000 | 2.608 | 0.0024 | 0.987–1.001 | 3.42–3.67 | 0.44–0.55 | 1.31–1.39 | 1.16 | n/a | n/a | n/a | 0.1214 | 18.797 | R-screen (DAN) |
| 2 | 3.0 | 6.0 | 1.0 | off | 100 | 1.3500 | 2.619 | 0.0055 | 0.992–1.006 | 6.40–6.79 | 2.68–3.21 | 2.17–2.26 | 1.12 | n/a | n/a | n/a | 0.1216 | 31.626 | R-screen (KC) |
| 2 | 3.0 | 6.0 | 0.0 | on | 100 | 1.3500 | 2.255 | 0.0069 | 0.997–1.003 | 6.14–6.58 | 2.16–2.68 | 2.17–2.26 | 1.14 | n/a | n/a | n/a | 0.1230 | 32.466 | R-screen (KC) |
| 2 | 3.0 | 6.0 | 0.0 | on | 25 | 5.0000 | 1.725 | 0.0077 | 0.996–1.019 | 6.60–6.98 | 3.18–3.72 | 2.17–2.27 | 1.11 | n/a | n/a | n/a | 0.1249 | 34.697 | R-screen (KC) |
| 2 | 4.0 | 2.0 | 0.0 | on | 25 | 5.6000 | 1.932 | 0.0099 | 0.995–1.001 | 8.60–9.06 | 4.97–5.55 | 1.37–1.43 | 1.11 | n/a | n/a | n/a | 0.1249 | 44.853 | R-screen (central) |
| 2 | 3.0 | 8.0 | 2.0 | on | 100 | 1.3000 | 2.148 | 0.0079 | 0.991–1.011 | 6.42–6.75 | 3.50–4.00 | 2.19–2.27 | 1.11 | n/a | n/a | n/a | 0.1271 | 36.761 | R-screen (KC) |
| 1 | 3.0 | 2.0 | 0.0 | off | 100 | 1.3000 | 2.614 | 0.0058 | 0.999–1.005 | 7.19–7.73 | 2.29–2.75 | 2.19–2.27 | 1.16 | n/a | n/a | n/a | 0.1276 | 31.638 | R-screen (KC) |
| 1 | 3.0 | 4.0 | 0.0 | off | 100 | 1.1000 | 3.410 | 0.0032 | 0.982–1.005 | 4.43–4.84 | 0.70–0.88 | 1.80–1.92 | 1.19 | n/a | n/a | n/a | 0.1282 | 18.419 | R-screen (F) |
| 2 | 3.0 | 8.0 | 1.0 | on | 25 | 5.2000 | 1.787 | 0.0083 | 0.992–1.010 | 6.64–6.98 | 3.99–4.56 | 2.18–2.28 | 1.10 | n/a | n/a | n/a | 0.1291 | 37.235 | R-screen (KC) |
| 2 | 3.0 | 6.0 | 1.0 | on | 100 | 1.3500 | 2.274 | 0.0073 | 0.993–1.009 | 6.45–6.85 | 2.78–3.32 | 2.19–2.28 | 1.13 | n/a | n/a | n/a | 0.1298 | 34.940 | R-screen (KC) |
| 1 | 3.0 | 2.0 | 0.0 | off | 100 | 0.8500 | 3.416 | 0.0017 | 0.987–1.018 | 3.94–4.08 | 0.53–0.58 | 1.45–1.52 | 1.08 | n/a | n/a | n/a | 0.1300 | 78.331 | R-screen (F) |
| 2 | 3.0 | 6.0 | 1.0 | off | 25 | 5.0000 | 2.034 | 0.0058 | 0.997–1.010 | 6.76–7.12 | 3.51–4.07 | 2.17–2.28 | 1.11 | n/a | n/a | n/a | 0.1301 | 32.691 | R-screen (KC) |
| 2 | 3.0 | 6.0 | 1.0 | on | 25 | 5.0000 | 1.730 | 0.0078 | 1.002–1.007 | 6.78–7.15 | 3.56–4.11 | 2.19–2.28 | 1.11 | n/a | n/a | n/a | 0.1306 | 36.186 | R-screen (KC) |
| 2 | 4.0 | 2.0 | 1.0 | off | 25 | 5.6000 | 1.675 | 0.0073 | 0.990–1.004 | 8.69–9.13 | 5.34–5.94 | 1.41–1.49 | 1.10 | n/a | n/a | n/a | 0.1317 | 41.262 | R-screen (central) |
| 1 | 3.0 | 3.0 | 0.0 | off | 100 | 1.3000 | 2.357 | 0.0052 | 0.994–1.007 | 6.60–7.11 | 1.96–2.43 | 2.19–2.28 | 1.16 | n/a | n/a | n/a | 0.1327 | 29.523 | R-screen (KC) |
| 2 | 3.0 | 6.0 | 1.0 | off | 400 | 0.2875 | 3.427 | 0.0034 | 0.993–1.011 | 4.31–4.64 | 0.73–0.94 | 1.77–1.84 | 1.17 | n/a | n/a | n/a | 0.1330 | 19.168 | R-screen (F) |
| 2 | 3.0 | 8.0 | 1.0 | on | 100 | 1.4000 | 2.172 | 0.0081 | 0.992–1.004 | 6.37–6.74 | 3.24–3.84 | 2.18–2.29 | 1.12 | n/a | n/a | n/a | 0.1357 | 36.290 | R-screen (KC) |
| 2 | 3.0 | 8.0 | 1.0 | off | 25 | 3.0000 | 2.436 | 0.0020 | 0.994–1.012 | 3.18–3.40 | 0.44–0.52 | 1.18–1.26 | 1.15 | n/a | n/a | n/a | 0.1357 | 18.583 | R-screen (DAN) |
| 2 | 3.0 | 6.0 | 2.0 | on | 400 | 0.3250 | 2.755 | 0.0074 | 0.988–1.004 | 6.62–6.97 | 3.15–3.61 | 2.21–2.29 | 1.11 | n/a | n/a | n/a | 0.1358 | 36.077 | R-screen (KC) |
| 1 | 3.0 | 4.0 | 0.0 | off | 100 | 1.3000 | 2.371 | 0.0050 | 1.001–1.008 | 6.20–6.69 | 1.80–2.25 | 2.21–2.29 | 1.16 | n/a | n/a | n/a | 0.1360 | 28.316 | R-screen (KC) |
| 2 | 3.0 | 6.0 | 1.0 | off | 25 | 3.0000 | 2.379 | 0.0020 | 0.993–1.008 | 3.44–3.67 | 0.44–0.53 | 1.26–1.34 | 1.14 | n/a | n/a | n/a | 0.1376 | 19.154 | R-screen (DAN) |
| 2 | 4.0 | 2.0 | 0.0 | off | 400 | 0.3625 | 3.443 | 0.0064 | 0.990–1.006 | 6.88–7.48 | 1.97–2.53 | 1.29–1.39 | 1.17 | n/a | n/a | n/a | 0.1376 | 33.605 | R-screen (F) |
| 2 | 3.0 | 6.0 | 1.0 | off | 400 | 0.3375 | 3.090 | 0.0050 | 0.987–1.000 | 5.87–6.28 | 1.86–2.31 | 2.14–2.23 | 1.14 | n/a | n/a | n/a | 0.1392 | 28.612 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 2.0 | off | 100 | 1.4500 | 2.405 | 0.0075 | 0.993–0.999 | 8.76–9.20 | 5.24–5.88 | 1.50–1.59 | 1.10 | n/a | n/a | n/a | 0.1395 | 43.782 | R-screen (central) |
| 2 | 4.0 | 2.0 | 2.0 | off | 400 | 0.3625 | 3.131 | 0.0073 | 0.990–1.003 | 8.37–8.82 | 4.58–5.11 | 1.51–1.57 | 1.11 | n/a | n/a | n/a | 0.1398 | 42.361 | R-screen (F, central) |
| 2 | 3.0 | 8.0 | 0.0 | on | 400 | 0.3625 | 2.652 | 0.0076 | 0.991–1.018 | 5.92–6.38 | 2.03–2.65 | 2.21–2.30 | 1.15 | n/a | n/a | n/a | 0.1403 | 33.852 | R-screen (KC) |
| 2 | 3.0 | 6.0 | 2.0 | off | 25 | 4.8000 | 1.995 | 0.0059 | 0.996–1.012 | 6.98–7.33 | 3.88–4.45 | 2.21–2.30 | 1.10 | n/a | n/a | n/a | 0.1417 | 34.421 | R-screen (KC) |
| 2 | 4.0 | 2.0 | 1.0 | off | 400 | 0.3750 | 3.308 | 0.0068 | 0.995–1.004 | 7.85–8.36 | 3.37–3.94 | 1.43–1.48 | 1.13 | n/a | n/a | n/a | 0.1424 | 39.680 | R-screen (F, central) |
| 2 | 3.0 | 6.0 | 2.0 | on | 400 | 0.2000 | 3.411 | 0.0029 | 0.986–1.004 | 3.72–3.92 | 0.49–0.59 | 1.40–1.47 | 1.11 | n/a | n/a | n/a | 0.1425 | 16.573 | R-screen (F, DAN) |
| 2 | 4.0 | 2.0 | 1.0 | on | 25 | 5.6000 | 1.948 | 0.0103 | 0.995–1.001 | 8.79–9.23 | 5.35–5.98 | 1.41–1.49 | 1.10 | n/a | n/a | n/a | 0.1431 | 46.341 | R-screen (central) |
| 1 | 3.0 | 2.0 | 0.0 | off | 100 | 1.2000 | 3.318 | 0.0047 | 0.990–1.005 | 6.10–6.63 | 1.55–1.90 | 1.98–2.09 | 1.18 | n/a | n/a | n/a | 0.1436 | 24.226 | R-screen (F, KC) |
| 1 | 4.0 | 1.0 | 0.0 | off | 100 | 1.3500 | 3.413 | 0.0064 | 0.992–1.010 | 7.53–8.12 | 2.91–3.44 | 1.21–1.25 | 1.15 | n/a | n/a | n/a | 0.1442 | 33.755 | R-screen (F, central) |
| 2 | 3.0 | 8.0 | 1.0 | on | 100 | 1.0000 | 3.469 | 0.0032 | 0.974–1.026 | 3.64–3.94 | 0.55–0.71 | 1.46–1.58 | 1.17 | n/a | n/a | n/a | 0.1453 | 16.898 | R-screen (F) |
| 2 | 3.0 | 8.0 | 1.0 | on | 25 | 3.0000 | 2.477 | 0.0023 | 0.992–1.019 | 3.20–3.42 | 0.43–0.52 | 1.19–1.27 | 1.15 | n/a | n/a | n/a | 0.1454 | 18.194 | R-screen (DAN) |
| 2 | 3.0 | 8.0 | 0.0 | off | 25 | 3.2000 | 2.544 | 0.0020 | 0.979–1.029 | 3.17–3.41 | 0.43–0.51 | 1.23–1.31 | 1.17 | n/a | n/a | n/a | 0.1459 | 19.036 | R-screen (DAN) |
| 2 | 3.0 | 8.0 | 2.0 | off | 25 | 5.0000 | 2.217 | 0.0061 | 0.994–1.002 | 6.82–7.14 | 4.34–4.90 | 2.22–2.32 | 1.10 | n/a | n/a | n/a | 0.1466 | 35.074 | R-screen (KC) |
| 2 | 3.0 | 6.0 | 2.0 | off | 100 | 1.3000 | 2.701 | 0.0059 | 0.990–1.004 | 6.87–7.22 | 3.52–4.02 | 2.23–2.32 | 1.10 | n/a | n/a | n/a | 0.1471 | 34.650 | R-screen (KC) |
| 2 | 3.0 | 6.0 | 1.0 | on | 25 | 3.0000 | 2.452 | 0.0024 | 0.995–1.008 | 3.44–3.67 | 0.43–0.53 | 1.25–1.33 | 1.15 | n/a | n/a | n/a | 0.1476 | 18.910 | R-screen (DAN) |
| 2 | 4.0 | 2.0 | 2.0 | off | 25 | 5.4000 | 1.703 | 0.0074 | 0.999–1.006 | 8.85–9.28 | 5.73–6.30 | 1.47–1.54 | 1.10 | n/a | n/a | n/a | 0.1484 | 42.657 | R-screen (central) |
| 2 | 3.0 | 6.0 | 2.0 | on | 25 | 4.8000 | 1.735 | 0.0082 | 0.996–1.017 | 6.99–7.33 | 3.96–4.48 | 2.21–2.32 | 1.10 | n/a | n/a | n/a | 0.1491 | 37.963 | R-screen (KC) |
| 2 | 3.0 | 8.0 | 1.0 | off | 100 | 1.4000 | 3.095 | 0.0057 | 0.993–1.003 | 6.31–6.69 | 3.16–3.75 | 2.15–2.25 | 1.12 | n/a | n/a | n/a | 0.1500 | 32.548 | R-screen (F, KC) |
| 2 | 3.0 | 8.0 | 2.0 | off | 100 | 0.7000 | 2.668 | 0.0021 | 0.990–1.001 | 3.23–3.40 | 0.43–0.49 | 1.21–1.29 | 1.13 | n/a | n/a | n/a | 0.1502 | 18.387 | R-screen (DAN) |
| 2 | 3.0 | 8.0 | 0.0 | off | 25 | 5.4000 | 2.205 | 0.0060 | 0.999–1.008 | 6.80–7.14 | 4.16–4.79 | 2.21–2.32 | 1.10 | n/a | n/a | n/a | 0.1504 | 34.205 | R-screen (KC) |
| 2 | 3.0 | 6.0 | 1.0 | on | 400 | 0.3500 | 2.992 | 0.0072 | 0.993–1.008 | 6.35–6.77 | 2.41–2.93 | 2.24–2.33 | 1.13 | n/a | n/a | n/a | 0.1512 | 34.766 | R-screen (KC) |
| 2 | 4.0 | 2.0 | 2.0 | on | 100 | 1.4500 | 2.762 | 0.0105 | 0.997–1.003 | 8.88–9.32 | 5.28–5.92 | 1.51–1.59 | 1.10 | n/a | n/a | n/a | 0.1527 | 48.754 | R-screen (central) |
| 2 | 3.0 | 8.0 | 0.0 | on | 100 | 1.4500 | 2.207 | 0.0084 | 0.995–1.009 | 6.49–6.88 | 3.18–3.83 | 2.23–2.33 | 1.12 | n/a | n/a | n/a | 0.1529 | 37.179 | R-screen (KC) |
| 2 | 3.0 | 6.0 | 0.0 | on | 100 | 1.4000 | 2.180 | 0.0078 | 0.990–1.003 | 6.58–6.99 | 2.68–3.22 | 2.26–2.33 | 1.13 | n/a | n/a | n/a | 0.1530 | 35.727 | R-screen (KC) |
| 2 | 3.0 | 8.0 | 2.0 | on | 25 | 5.0000 | 1.757 | 0.0085 | 0.994–1.007 | 6.82–7.16 | 4.34–4.88 | 2.23–2.33 | 1.10 | n/a | n/a | n/a | 0.1543 | 38.741 | R-screen (KC) |
| 2 | 3.0 | 8.0 | 2.0 | on | 100 | 0.7000 | 2.865 | 0.0021 | 0.977–1.018 | 3.23–3.42 | 0.43–0.50 | 1.23–1.28 | 1.13 | n/a | n/a | n/a | 0.1545 | 18.722 | R-screen (DAN) |
| 2 | 3.0 | 6.0 | 2.0 | on | 100 | 1.3000 | 2.192 | 0.0080 | 0.994–1.001 | 6.91–7.27 | 3.63–4.15 | 2.25–2.34 | 1.11 | n/a | n/a | n/a | 0.1551 | 38.130 | R-screen (KC) |
| 2 | 3.0 | 8.0 | 2.0 | on | 400 | 0.2000 | 3.337 | 0.0031 | 0.987–1.007 | 3.47–3.65 | 0.48–0.58 | 1.35–1.42 | 1.11 | n/a | n/a | n/a | 0.1554 | 16.496 | R-screen (F, DAN) |
| 2 | 3.0 | 6.0 | 2.0 | on | 100 | 0.7000 | 2.799 | 0.0024 | 0.986–1.020 | 3.48–3.68 | 0.43–0.50 | 1.29–1.36 | 1.12 | n/a | n/a | n/a | 0.1558 | 19.117 | R-screen (DAN) |
| 1 | 3.0 | 8.0 | 0.0 | off | 100 | 1.4000 | 3.147 | 0.0054 | 0.999–1.008 | 6.03–6.44 | 2.55–3.13 | 2.15–2.23 | 1.13 | n/a | n/a | n/a | 0.1568 | 30.384 | R-screen (F, KC) |
| 1 | 3.0 | 6.0 | 0.0 | off | 100 | 1.4000 | 2.668 | 0.0057 | 0.996–1.007 | 6.50–6.93 | 2.63–3.21 | 2.25–2.34 | 1.13 | n/a | n/a | n/a | 0.1570 | 32.082 | R-screen (KC) |
| 2 | 3.0 | 8.0 | 1.0 | on | 400 | 0.3625 | 2.641 | 0.0078 | 0.999–1.014 | 6.31–6.70 | 2.88–3.49 | 2.22–2.34 | 1.13 | n/a | n/a | n/a | 0.1574 | 36.553 | R-screen (KC) |
| 2 | 3.0 | 6.0 | 0.0 | off | 25 | 5.2000 | 1.956 | 0.0059 | 0.990–1.009 | 6.94–7.31 | 3.67–4.27 | 2.24–2.34 | 1.11 | n/a | n/a | n/a | 0.1579 | 33.769 | R-screen (KC) |
| 2 | 3.0 | 8.0 | 2.0 | on | 400 | 0.3375 | 2.631 | 0.0081 | 0.998–1.006 | 6.47–6.80 | 3.50–3.97 | 2.26–2.34 | 1.11 | n/a | n/a | n/a | 0.1582 | 37.629 | R-screen (KC) |
| 2 | 4.0 | 2.0 | 2.0 | on | 25 | 5.4000 | 1.902 | 0.0102 | 0.991–1.004 | 8.95–9.37 | 5.74–6.32 | 1.48–1.54 | 1.10 | n/a | n/a | n/a | 0.1582 | 47.650 | R-screen (central) |
| 2 | 3.0 | 8.0 | 0.0 | off | 400 | 0.3375 | 3.343 | 0.0043 | 0.990–1.003 | 4.91–5.40 | 1.09–1.44 | 2.03–2.10 | 1.19 | n/a | n/a | n/a | 0.1586 | 24.244 | R-screen (F, KC) |
| 2 | 3.0 | 6.0 | 1.0 | on | 100 | 1.0500 | 3.516 | 0.0042 | 0.993–1.019 | 4.20–4.51 | 0.73–0.91 | 1.63–1.71 | 1.17 | n/a | n/a | n/a | 0.1586 | 18.374 | R-screen (F) |
| 2 | 4.0 | 2.0 | 0.0 | off | 25 | 5.8000 | 1.601 | 0.0076 | 0.995–1.004 | 8.93–9.38 | 5.53–6.19 | 1.45–1.52 | 1.10 | n/a | n/a | n/a | 0.1594 | 42.228 | R-screen (central) |
| 2 | 3.0 | 8.0 | 0.0 | on | 25 | 5.4000 | 1.711 | 0.0087 | 0.994–1.003 | 6.82–7.17 | 4.17–4.82 | 2.24–2.35 | 1.10 | n/a | n/a | n/a | 0.1600 | 38.558 | R-screen (KC) |
| 2 | 3.0 | 6.0 | 1.0 | off | 100 | 1.4000 | 2.730 | 0.0059 | 0.991–1.006 | 6.79–7.18 | 3.21–3.80 | 2.26–2.35 | 1.12 | n/a | n/a | n/a | 0.1605 | 34.185 | R-screen (KC) |
| 2 | 3.0 | 6.0 | 1.0 | on | 100 | 1.4000 | 2.183 | 0.0080 | 0.997–1.009 | 6.85–7.25 | 3.32–3.92 | 2.28–2.35 | 1.12 | n/a | n/a | n/a | 0.1631 | 37.856 | R-screen (KC) |
| 2 | 3.0 | 8.0 | 1.0 | off | 400 | 0.2750 | 3.536 | 0.0030 | 0.991–1.010 | 3.72–4.03 | 0.55–0.70 | 1.58–1.69 | 1.17 | n/a | n/a | n/a | 0.1643 | 17.810 | R-screen (F) |
| 2 | 3.0 | 8.0 | 1.0 | off | 25 | 5.4000 | 2.229 | 0.0063 | 0.990–1.009 | 6.96–7.31 | 4.59–5.12 | 2.26–2.36 | 1.10 | n/a | n/a | n/a | 0.1647 | 35.730 | R-screen (KC) |
| 1 | 3.0 | 4.0 | 0.0 | off | 100 | 1.3500 | 2.338 | 0.0054 | 0.995–1.012 | 6.69–7.16 | 2.25–2.75 | 2.29–2.36 | 1.14 | n/a | n/a | n/a | 0.1655 | 31.260 | R-screen (KC) |
| 2 | 3.0 | 8.0 | 1.0 | on | 100 | 1.4500 | 2.165 | 0.0086 | 0.992–1.006 | 6.74–7.11 | 3.84–4.46 | 2.29–2.36 | 1.11 | n/a | n/a | n/a | 0.1661 | 39.369 | R-screen (KC) |
| 2 | 3.0 | 8.0 | 2.0 | off | 400 | 0.3125 | 3.350 | 0.0052 | 0.994–1.004 | 5.77–6.11 | 2.57–2.97 | 2.06–2.12 | 1.11 | n/a | n/a | n/a | 0.1665 | 29.324 | R-screen (F, KC) |
| 2 | 3.0 | 8.0 | 2.0 | on | 100 | 1.3500 | 2.146 | 0.0085 | 0.995–1.011 | 6.75–7.10 | 4.00–4.54 | 2.27–2.37 | 1.10 | n/a | n/a | n/a | 0.1685 | 39.312 | R-screen (KC) |
| 2 | 3.0 | 6.0 | 2.0 | on | 400 | 0.3375 | 2.561 | 0.0081 | 0.988–1.006 | 6.97–7.33 | 3.61–4.10 | 2.29–2.37 | 1.11 | n/a | n/a | n/a | 0.1691 | 38.754 | R-screen (KC) |
| 2 | 3.0 | 8.0 | 1.0 | on | 400 | 0.3250 | 3.431 | 0.0057 | 0.993–1.016 | 5.13–5.52 | 1.52–1.91 | 1.96–2.07 | 1.15 | n/a | n/a | n/a | 0.1700 | 26.707 | R-screen (F, KC) |
| 1 | 3.0 | 2.0 | 0.0 | off | 100 | 1.1500 | 3.559 | 0.0042 | 0.990–1.004 | 5.62–6.10 | 1.28–1.55 | 1.89–1.98 | 1.18 | n/a | n/a | n/a | 0.1710 | 20.807 | R-screen (F) |
| 2 | 3.0 | 6.0 | 0.0 | on | 25 | 5.2000 | 1.725 | 0.0081 | 0.994–1.019 | 6.98–7.35 | 3.72–4.33 | 2.27–2.37 | 1.11 | n/a | n/a | n/a | 0.1714 | 37.543 | R-screen (KC) |
| 2 | 3.0 | 6.0 | 1.0 | on | 25 | 5.2000 | 1.691 | 0.0086 | 1.000–1.007 | 7.15–7.51 | 4.11–4.70 | 2.28–2.37 | 1.10 | n/a | n/a | n/a | 0.1715 | 38.915 | R-screen (KC) |
| 2 | 3.0 | 6.0 | 1.0 | off | 25 | 5.2000 | 2.034 | 0.0063 | 0.997–1.009 | 7.12–7.49 | 4.07–4.66 | 2.28–2.38 | 1.10 | n/a | n/a | n/a | 0.1720 | 35.258 | R-screen (KC) |
| 2 | 3.0 | 6.0 | 2.0 | off | 100 | 1.3500 | 2.759 | 0.0064 | 0.990–1.005 | 7.22–7.57 | 4.02–4.57 | 2.32–2.38 | 1.10 | n/a | n/a | n/a | 0.1731 | 37.255 | R-screen (KC) |
| 2 | 4.0 | 2.0 | 0.0 | on | 25 | 5.8000 | 1.927 | 0.0107 | 0.997–1.003 | 9.06–9.51 | 5.55–6.18 | 1.43–1.50 | 1.10 | n/a | n/a | n/a | 0.1731 | 47.758 | R-screen (central) |
| 2 | 3.0 | 6.0 | 1.0 | on | 100 | 1.0000 | 3.569 | 0.0036 | 1.004–1.019 | 3.90–4.20 | 0.58–0.73 | 1.54–1.63 | 1.16 | n/a | n/a | n/a | 0.1736 | 17.613 | R-screen (F) |
| 1 | 3.0 | 3.0 | 0.0 | off | 100 | 1.3500 | 2.231 | 0.0057 | 0.997–1.006 | 7.11–7.63 | 2.43–2.96 | 2.28–2.38 | 1.15 | n/a | n/a | n/a | 0.1750 | 32.899 | R-screen (KC) |
| 2 | 3.0 | 8.0 | 1.0 | on | 25 | 5.4000 | 1.714 | 0.0091 | 0.992–1.002 | 6.98–7.34 | 4.56–5.14 | 2.28–2.38 | 1.10 | n/a | n/a | n/a | 0.1751 | 40.034 | R-screen (KC) |
| 2 | 3.0 | 6.0 | 2.0 | off | 25 | 5.0000 | 2.029 | 0.0063 | 0.996–1.008 | 7.33–7.67 | 4.45–4.99 | 2.30–2.39 | 1.10 | n/a | n/a | n/a | 0.1765 | 36.798 | R-screen (KC) |
| 2 | 4.0 | 2.0 | 1.0 | off | 25 | 5.8000 | 1.634 | 0.0077 | 0.990–1.001 | 9.13–9.56 | 5.94–6.58 | 1.49–1.54 | 1.10 | n/a | n/a | n/a | 0.1783 | 43.682 | R-screen (central) |
| 2 | 3.0 | 8.0 | 2.0 | off | 25 | 5.2000 | 2.299 | 0.0065 | 0.994–1.004 | 7.14–7.47 | 4.90–5.44 | 2.32–2.40 | 1.10 | n/a | n/a | n/a | 0.1841 | 37.067 | R-screen (KC) |
| 2 | 3.0 | 8.0 | 2.0 | on | 400 | 0.3500 | 2.571 | 0.0085 | 0.998–1.005 | 6.80–7.14 | 3.97–4.48 | 2.34–2.41 | 1.10 | n/a | n/a | n/a | 0.1849 | 40.561 | R-screen (KC) |
| 2 | 3.0 | 6.0 | 0.0 | off | 400 | 0.3500 | 3.168 | 0.0050 | 0.996–1.018 | 5.80–6.31 | 1.50–1.99 | 2.20–2.28 | 1.17 | n/a | n/a | n/a | 0.1850 | 28.921 | R-screen (F, KC) |
| 2 | 3.0 | 6.0 | 1.0 | on | 400 | 0.3625 | 2.838 | 0.0082 | 0.992–1.008 | 6.77–7.19 | 2.93–3.53 | 2.33–2.41 | 1.13 | n/a | n/a | n/a | 0.1856 | 38.242 | R-screen (KC) |
| 2 | 4.0 | 2.0 | 2.0 | off | 100 | 1.5000 | 2.351 | 0.0081 | 0.992–1.003 | 9.20–9.64 | 5.88–6.46 | 1.59–1.63 | 1.10 | n/a | n/a | n/a | 0.1863 | 46.501 | R-screen (central) |
| 2 | 3.0 | 6.0 | 2.0 | off | 400 | 0.1875 | 3.063 | 0.0024 | 0.985–1.005 | 3.55–3.73 | 0.42–0.50 | 1.34–1.40 | 1.11 | n/a | n/a | n/a | 0.1877 | 19.856 | R-screen (F, DAN) |
| 2 | 3.0 | 8.0 | 2.0 | off | 400 | 0.1875 | 3.048 | 0.0022 | 0.957–1.021 | 3.27–3.46 | 0.42–0.48 | 1.27–1.33 | 1.11 | n/a | n/a | n/a | 0.1889 | 18.909 | R-screen (F, DAN) |
| 2 | 3.0 | 6.0 | 0.0 | on | 400 | 0.3625 | 2.788 | 0.0075 | 0.991–1.007 | 6.38–6.86 | 2.06–2.69 | 2.31–2.42 | 1.15 | n/a | n/a | n/a | 0.1892 | 35.471 | R-screen (KC) |
| 2 | 3.0 | 6.0 | 2.0 | on | 100 | 1.3500 | 2.129 | 0.0086 | 0.994–1.001 | 7.27–7.62 | 4.15–4.70 | 2.34–2.42 | 1.10 | n/a | n/a | n/a | 0.1910 | 40.855 | R-screen (KC) |
| 2 | 3.0 | 8.0 | 0.0 | on | 100 | 1.5000 | 2.207 | 0.0088 | 0.993–1.009 | 6.88–7.26 | 3.83–4.50 | 2.33–2.42 | 1.11 | n/a | n/a | n/a | 0.1912 | 40.300 | R-screen (KC) |
| 2 | 4.0 | 2.0 | 2.0 | off | 25 | 5.6000 | 1.703 | 0.0080 | 1.000–1.006 | 9.28–9.69 | 6.30–6.88 | 1.54–1.60 | 1.09 | n/a | n/a | n/a | 0.1915 | 45.067 | R-screen (central) |
| 2 | 4.0 | 2.0 | 1.0 | on | 25 | 5.8000 | 1.933 | 0.0108 | 0.995–1.005 | 9.23–9.69 | 5.98–6.58 | 1.49–1.57 | 1.10 | n/a | n/a | n/a | 0.1919 | 49.103 | R-screen (central) |
| 2 | 3.0 | 6.0 | 2.0 | on | 25 | 5.0000 | 1.723 | 0.0086 | 0.996–1.013 | 7.33–7.70 | 4.48–5.05 | 2.32–2.42 | 1.10 | n/a | n/a | n/a | 0.1920 | 40.528 | R-screen (KC) |
| 2 | 3.0 | 8.0 | 0.0 | on | 25 | 5.6000 | 1.712 | 0.0093 | 0.993–1.003 | 7.17–7.51 | 4.82–5.34 | 2.35–2.43 | 1.10 | n/a | n/a | n/a | 0.1930 | 41.179 | R-screen (KC) |
| 2 | 3.0 | 8.0 | 2.0 | on | 25 | 5.2000 | 1.737 | 0.0093 | 0.994–1.007 | 7.16–7.48 | 4.88–5.43 | 2.33–2.43 | 1.09 | n/a | n/a | n/a | 0.1932 | 41.418 | R-screen (KC) |
| 2 | 3.0 | 8.0 | 0.0 | off | 25 | 5.6000 | 2.276 | 0.0065 | 0.999–1.006 | 7.14–7.49 | 4.79–5.38 | 2.32–2.43 | 1.10 | n/a | n/a | n/a | 0.1934 | 36.675 | R-screen (KC) |
| 2 | 3.0 | 6.0 | 1.0 | off | 100 | 1.4500 | 2.875 | 0.0065 | 0.991–0.999 | 7.18–7.57 | 3.80–4.42 | 2.35–2.43 | 1.11 | n/a | n/a | n/a | 0.1937 | 36.867 | R-screen (KC) |
| 1 | 3.0 | 6.0 | 0.0 | off | 100 | 1.4500 | 2.946 | 0.0064 | 0.996–1.002 | 6.93–7.34 | 3.21–3.81 | 2.34–2.43 | 1.12 | n/a | n/a | n/a | 0.1943 | 34.772 | R-screen (KC) |
| 1 | 4.0 | 1.0 | 0.0 | off | 100 | 1.4000 | 3.355 | 0.0070 | 0.989–1.012 | 8.12–8.69 | 3.44–4.07 | 1.25–1.35 | 1.14 | n/a | n/a | n/a | 0.1949 | 37.218 | R-screen (F, central) |
| 1 | 3.0 | 6.0 | 0.0 | off | 100 | 1.0500 | 3.624 | 0.0028 | 0.977–1.007 | 3.69–4.01 | 0.50–0.60 | 1.58–1.68 | 1.19 | n/a | n/a | n/a | 0.1949 | 19.106 | R-screen (F, DAN) |
| 2 | 3.0 | 8.0 | 2.0 | on | 100 | 1.4000 | 2.130 | 0.0091 | 0.991–1.009 | 7.10–7.44 | 4.54–5.10 | 2.37–2.44 | 1.10 | n/a | n/a | n/a | 0.1972 | 42.189 | R-screen (KC) |
| 1 | 3.0 | 3.0 | 0.0 | off | 100 | 1.1000 | 3.661 | 0.0037 | 0.993–1.016 | 4.75–5.16 | 0.83–1.02 | 1.83–1.93 | 1.18 | n/a | n/a | n/a | 0.1990 | 18.344 | R-screen (F) |
| 2 | 4.0 | 2.0 | 2.0 | on | 100 | 1.5000 | 2.678 | 0.0112 | 0.993–1.003 | 9.32–9.77 | 5.92–6.51 | 1.59–1.64 | 1.10 | n/a | n/a | n/a | 0.1998 | 51.752 | R-screen (central) |
| 2 | 3.0 | 8.0 | 1.0 | off | 25 | 5.6000 | 2.317 | 0.0067 | 0.992–1.012 | 7.31–7.65 | 5.12–5.73 | 2.36–2.44 | 1.09 | n/a | n/a | n/a | 0.2009 | 37.895 | R-screen (KC) |
| 2 | 3.0 | 6.0 | 0.0 | on | 100 | 1.4500 | 2.152 | 0.0085 | 0.990–1.006 | 6.99–7.41 | 3.22–3.91 | 2.33–2.45 | 1.12 | n/a | n/a | n/a | 0.2009 | 38.722 | R-screen (KC) |
| 2 | 3.0 | 6.0 | 0.0 | off | 25 | 5.4000 | 1.974 | 0.0065 | 0.995–1.002 | 7.31–7.69 | 4.27–4.87 | 2.34–2.45 | 1.10 | n/a | n/a | n/a | 0.2027 | 36.200 | R-screen (KC) |
| 2 | 3.0 | 8.0 | 2.0 | off | 100 | 1.3000 | 3.270 | 0.0059 | 0.995–1.008 | 6.39–6.71 | 3.43–3.93 | 2.17–2.25 | 1.10 | n/a | n/a | n/a | 0.2029 | 33.279 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 2.0 | on | 25 | 5.6000 | 1.902 | 0.0109 | 0.996–1.005 | 9.37–9.80 | 6.32–6.92 | 1.54–1.61 | 1.09 | n/a | n/a | n/a | 0.2034 | 50.362 | R-screen (central) |
| 2 | 4.0 | 2.0 | 0.0 | off | 25 | 6.0000 | 1.601 | 0.0078 | 0.998–1.008 | 9.38–9.83 | 6.19–6.80 | 1.52–1.59 | 1.09 | n/a | n/a | n/a | 0.2060 | 44.747 | R-screen (central) |
| 2 | 4.0 | 2.0 | 2.0 | off | 400 | 0.3750 | 3.180 | 0.0086 | 0.990–1.003 | 8.82–9.28 | 5.11–5.82 | 1.57–1.73 | 1.11 | n/a | n/a | n/a | 0.2068 | 45.112 | R-screen (F, central) |
| 2 | 3.0 | 6.0 | 0.0 | off | 400 | 0.3250 | 3.504 | 0.0038 | 0.989–1.001 | 4.78–5.29 | 0.85–1.13 | 2.01–2.11 | 1.22 | n/a | n/a | n/a | 0.2072 | 22.082 | R-screen (F, KC) |
| 2 | 3.0 | 8.0 | 0.0 | on | 100 | 1.1500 | 3.692 | 0.0046 | 0.987–1.003 | 4.13–4.51 | 0.75–0.99 | 1.71–1.79 | 1.20 | n/a | n/a | n/a | 0.2076 | 18.905 | R-screen (F) |
| 2 | 3.0 | 6.0 | 1.0 | on | 100 | 1.4500 | 2.139 | 0.0088 | 0.997–1.005 | 7.25–7.65 | 3.92–4.53 | 2.35–2.46 | 1.11 | n/a | n/a | n/a | 0.2081 | 40.932 | R-screen (KC) |
| 2 | 3.0 | 6.0 | 1.0 | on | 25 | 5.4000 | 1.711 | 0.0089 | 0.995–1.006 | 7.51–7.89 | 4.70–5.34 | 2.37–2.46 | 1.10 | n/a | n/a | n/a | 0.2082 | 41.708 | R-screen (KC) |
| 1 | 3.0 | 4.0 | 0.0 | off | 100 | 1.4000 | 2.355 | 0.0058 | 0.995–1.012 | 7.16–7.63 | 2.75–3.32 | 2.36–2.46 | 1.14 | n/a | n/a | n/a | 0.2086 | 34.304 | R-screen (KC) |
| 2 | 3.0 | 6.0 | 0.0 | on | 25 | 5.4000 | 1.748 | 0.0089 | 0.994–1.002 | 7.35–7.74 | 4.33–4.91 | 2.37–2.47 | 1.10 | n/a | n/a | n/a | 0.2091 | 40.353 | R-screen (KC) |
| 2 | 3.0 | 8.0 | 1.0 | on | 25 | 5.6000 | 1.714 | 0.0095 | 0.991–1.002 | 7.34–7.67 | 5.14–5.77 | 2.38–2.47 | 1.09 | n/a | n/a | n/a | 0.2100 | 42.554 | R-screen (KC) |
| 2 | 3.0 | 6.0 | 1.0 | off | 25 | 5.4000 | 1.974 | 0.0066 | 0.994–1.003 | 7.49–7.85 | 4.66–5.28 | 2.38–2.47 | 1.10 | n/a | n/a | n/a | 0.2107 | 37.632 | R-screen (KC) |
| 2 | 3.0 | 6.0 | 0.0 | on | 25 | 3.0000 | 2.699 | 0.0021 | 0.987–1.016 | 3.21–3.42 | 0.40–0.44 | 1.23–1.31 | 1.14 | n/a | n/a | n/a | 0.2114 | 25.136 | R-screen (DAN) |
| 2 | 3.0 | 8.0 | 0.0 | on | 400 | 0.3750 | 2.638 | 0.0085 | 0.991–1.008 | 6.38–6.81 | 2.65–3.38 | 2.30–2.47 | 1.14 | n/a | n/a | n/a | 0.2126 | 37.382 | R-screen (KC) |
| 2 | 4.0 | 2.0 | 2.0 | off | 400 | 0.3375 | 3.720 | 0.0068 | 0.994–1.007 | 7.50–7.92 | 4.02–4.03 | 1.41–2.00 | 1.12 | n/a | n/a | n/a | 0.2172 | 38.375 | R-screen (F, KC) |
| 1 | 3.0 | 2.0 | 0.0 | off | 100 | 1.3500 | 2.480 | 0.0060 | 0.995–1.011 | 7.73–8.30 | 2.75–3.31 | 2.27–2.40 | 1.15 | n/a | n/a | n/a | 0.2180 | 35.211 | R-screen (central, KC) |
| 1 | 3.0 | 8.0 | 0.0 | off | 100 | 1.4500 | 3.229 | 0.0061 | 0.999–1.004 | 6.44–6.82 | 3.13–3.74 | 2.23–2.31 | 1.12 | n/a | n/a | n/a | 0.2189 | 33.145 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 0.0 | on | 25 | 6.0000 | 1.961 | 0.0113 | 0.997–1.003 | 9.51–9.96 | 6.18–6.80 | 1.50–1.59 | 1.10 | n/a | n/a | n/a | 0.2190 | 50.451 | R-screen (central) |
| 2 | 4.0 | 2.0 | 1.0 | off | 25 | 6.0000 | 1.649 | 0.0082 | 0.996–1.002 | 9.56–9.99 | 6.58–7.23 | 1.54–1.64 | 1.09 | n/a | n/a | n/a | 0.2224 | 46.188 | R-screen (central) |
| 2 | 3.0 | 6.0 | 2.0 | on | 100 | 1.4000 | 2.121 | 0.0092 | 0.996–1.006 | 7.62–7.99 | 4.70–5.28 | 2.42–2.50 | 1.10 | n/a | n/a | n/a | 0.2229 | 43.587 | R-screen (KC) |
| 2 | 3.0 | 8.0 | 1.0 | off | 400 | 0.3375 | 3.502 | 0.0050 | 0.990–1.002 | 5.45–5.84 | 1.79–2.22 | 2.03–2.14 | 1.15 | n/a | n/a | n/a | 0.2232 | 27.591 | R-screen (F, KC) |
| 2 | 3.0 | 6.0 | 2.0 | off | 25 | 5.2000 | 2.029 | 0.0068 | 0.993–1.008 | 7.67–8.03 | 4.99–5.59 | 2.39–2.50 | 1.09 | n/a | n/a | n/a | 0.2252 | 39.023 | R-screen (central, KC) |
| 2 | 3.0 | 8.0 | 1.0 | on | 100 | 1.5000 | 2.178 | 0.0097 | 0.999–1.006 | 7.11–7.48 | 4.46–5.12 | 2.36–2.51 | 1.11 | n/a | n/a | n/a | 0.2252 | 42.193 | R-screen (KC) |
| 2 | 4.0 | 2.0 | 2.0 | on | 400 | 0.3500 | 3.547 | 0.0094 | 0.995–1.004 | 8.05–8.50 | 4.10–4.60 | 1.44–1.49 | 1.11 | n/a | n/a | n/a | 0.2282 | 43.871 | R-screen (F, central) |
| 2 | 3.0 | 8.0 | 0.0 | on | 400 | 0.3375 | 3.591 | 0.0064 | 0.993–1.011 | 4.97–5.45 | 1.15–1.54 | 2.03–2.10 | 1.19 | n/a | n/a | n/a | 0.2282 | 26.110 | R-screen (F, KC) |
| 2 | 3.0 | 6.0 | 0.0 | on | 400 | 0.3500 | 3.268 | 0.0070 | 0.992–1.000 | 5.87–6.38 | 1.58–2.06 | 2.20–2.31 | 1.17 | n/a | n/a | n/a | 0.2283 | 31.577 | R-screen (F, KC) |
| 2 | 3.0 | 6.0 | 1.0 | off | 400 | 0.3500 | 3.257 | 0.0054 | 0.987–1.001 | 6.28–6.71 | 2.31–2.81 | 2.23–2.31 | 1.14 | n/a | n/a | n/a | 0.2283 | 31.717 | R-screen (F, KC) |
| 2 | 3.0 | 8.0 | 0.0 | off | 25 | 5.8000 | 2.276 | 0.0069 | 0.994–1.006 | 7.49–7.84 | 5.38–6.00 | 2.43–2.52 | 1.09 | n/a | n/a | n/a | 0.2292 | 38.898 | R-screen (KC) |
| 2 | 3.0 | 8.0 | 1.0 | off | 100 | 1.4500 | 3.231 | 0.0061 | 0.993–1.009 | 6.69–7.06 | 3.75–4.34 | 2.25–2.34 | 1.11 | n/a | n/a | n/a | 0.2296 | 35.016 | R-screen (F, KC) |
| 2 | 3.0 | 8.0 | 1.0 | on | 400 | 0.3750 | 2.652 | 0.0093 | 0.992–1.005 | 6.70–7.10 | 3.49–4.18 | 2.34–2.52 | 1.12 | n/a | n/a | n/a | 0.2296 | 39.865 | R-screen (KC) |
| 2 | 3.0 | 6.0 | 2.0 | on | 25 | 5.2000 | 1.723 | 0.0092 | 0.996–1.006 | 7.70–8.04 | 5.05–5.65 | 2.42–2.50 | 1.09 | n/a | n/a | n/a | 0.2302 | 43.130 | R-screen (central, KC) |
| 1 | 3.0 | 8.0 | 0.0 | off | 100 | 1.0500 | 3.531 | 0.0026 | 0.997–1.022 | 3.42–3.75 | 0.47–0.57 | 1.52–1.60 | 1.20 | n/a | n/a | n/a | 0.2302 | 18.728 | R-screen (F, DAN) |
| 2 | 3.0 | 6.0 | 2.0 | off | 400 | 0.3250 | 3.320 | 0.0057 | 0.999–1.011 | 6.57–6.93 | 3.06–3.50 | 2.18–2.28 | 1.11 | n/a | n/a | n/a | 0.2313 | 32.871 | R-screen (F, KC) |
| 2 | 3.0 | 6.0 | 1.0 | off | 100 | 1.5000 | 2.975 | 0.0067 | 0.993–1.005 | 7.57–7.98 | 4.42–5.09 | 2.43–2.52 | 1.11 | n/a | n/a | n/a | 0.2315 | 39.339 | R-screen (KC) |
| 1 | 3.0 | 6.0 | 0.0 | off | 100 | 1.5000 | 2.977 | 0.0066 | 0.996–1.002 | 7.34–7.75 | 3.81–4.49 | 2.43–2.52 | 1.11 | n/a | n/a | n/a | 0.2315 | 37.409 | R-screen (KC) |
| 2 | 3.0 | 8.0 | 0.0 | off | 25 | 3.0000 | 2.701 | 0.0019 | 0.974–1.029 | 2.97–3.17 | 0.40–0.43 | 1.15–1.23 | 1.15 | n/a | n/a | n/a | 0.2317 | 26.086 | R-screen (DAN) |
| 1 | 3.0 | 3.0 | 0.0 | off | 100 | 1.4000 | 2.213 | 0.0060 | 0.998–1.006 | 7.63–8.14 | 2.96–3.55 | 2.38–2.48 | 1.13 | n/a | n/a | n/a | 0.2330 | 36.034 | R-screen (central, KC) |
| 2 | 3.0 | 6.0 | 0.0 | off | 25 | 3.0000 | 2.688 | 0.0018 | 0.990–1.017 | 3.22–3.41 | 0.40–0.45 | 1.24–1.31 | 1.14 | n/a | n/a | n/a | 0.2331 | 26.762 | R-screen (DAN) |
| 2 | 4.0 | 2.0 | 2.0 | off | 25 | 5.8000 | 1.674 | 0.0081 | 1.001–1.002 | 9.69–10.11 | 6.88–7.50 | 1.60–1.67 | 1.09 | n/a | n/a | n/a | 0.2338 | 47.425 | R-screen (central) |
| 2 | 3.0 | 8.0 | 2.0 | on | 25 | 5.4000 | 1.708 | 0.0096 | 0.998–1.006 | 7.48–7.82 | 5.43–6.06 | 2.43–2.53 | 1.09 | n/a | n/a | n/a | 0.2348 | 43.868 | R-screen (KC) |
| 2 | 3.0 | 8.0 | 2.0 | off | 25 | 5.4000 | 2.432 | 0.0069 | 0.996–1.004 | 7.47–7.80 | 5.44–6.03 | 2.40–2.53 | 1.09 | n/a | n/a | n/a | 0.2352 | 39.418 | R-screen (KC) |
| 2 | 4.0 | 2.0 | 1.0 | on | 25 | 6.0000 | 1.905 | 0.0116 | 0.996–1.005 | 9.69–10.13 | 6.58–7.28 | 1.57–1.65 | 1.09 | n/a | n/a | n/a | 0.2365 | 51.910 | R-screen (central) |
| 2 | 3.0 | 6.0 | 1.0 | on | 400 | 0.3750 | 2.709 | 0.0087 | 0.992–1.010 | 7.19–7.63 | 3.53–4.23 | 2.41–2.53 | 1.12 | n/a | n/a | n/a | 0.2368 | 41.343 | R-screen (KC) |
| 2 | 3.0 | 6.0 | 2.0 | on | 400 | 0.3500 | 2.581 | 0.0093 | 0.990–1.006 | 7.33–7.70 | 4.10–4.69 | 2.37–2.54 | 1.10 | n/a | n/a | n/a | 0.2380 | 41.601 | R-screen (KC) |
| 2 | 3.0 | 6.0 | 0.0 | on | 100 | 1.5000 | 2.125 | 0.0090 | 1.001–1.006 | 7.41–7.83 | 3.91–4.58 | 2.45–2.54 | 1.11 | n/a | n/a | n/a | 0.2385 | 41.903 | R-screen (KC) |
| 2 | 3.0 | 8.0 | 2.0 | on | 400 | 0.3625 | 2.508 | 0.0091 | 0.995–1.005 | 7.14–7.49 | 4.48–5.08 | 2.41–2.54 | 1.10 | n/a | n/a | n/a | 0.2402 | 43.257 | R-screen (KC) |
| 2 | 4.0 | 2.0 | 1.0 | off | 25 | 5.4000 | 2.805 | 0.0070 | 0.996–1.004 | 8.25–8.69 | 5.34–5.37 | 1.41–2.34 | 1.11 | n/a | n/a | n/a | 0.2407 | 41.649 | R-screen (central, KC) |
| 2 | 3.0 | 8.0 | 2.0 | on | 100 | 1.4500 | 2.136 | 0.0097 | 0.991–1.007 | 7.44–7.77 | 5.10–5.70 | 2.44–2.54 | 1.09 | n/a | n/a | n/a | 0.2407 | 44.714 | R-screen (KC) |
| 2 | 3.0 | 6.0 | 2.0 | off | 100 | 1.4000 | 3.092 | 0.0069 | 0.997–1.007 | 7.57–7.92 | 4.57–5.16 | 2.38–2.48 | 1.09 | n/a | n/a | n/a | 0.2434 | 39.496 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 2.0 | on | 25 | 5.8000 | 1.859 | 0.0115 | 0.996–1.005 | 9.80–10.24 | 6.92–7.58 | 1.61–1.71 | 1.09 | n/a | n/a | n/a | 0.2467 | 53.034 | R-screen (central) |
| 2 | 3.0 | 6.0 | 2.0 | on | 400 | 0.3625 | 2.581 | 0.0093 | 0.993–1.013 | 7.70–8.07 | 4.69–5.20 | 2.54–2.54 | 1.10 | n/a | n/a | n/a | 0.2472 | 44.700 | R-screen (central, KC) |
| 2 | 3.0 | 8.0 | 1.0 | off | 25 | 5.8000 | 2.317 | 0.0069 | 0.992–1.012 | 7.65–7.98 | 5.73–6.32 | 2.44–2.56 | 1.09 | n/a | n/a | n/a | 0.2482 | 40.011 | R-screen (KC) |
| 2 | 3.0 | 6.0 | 1.0 | on | 400 | 0.3375 | 3.431 | 0.0069 | 0.993–1.004 | 5.92–6.35 | 1.96–2.41 | 2.15–2.24 | 1.15 | n/a | n/a | n/a | 0.2484 | 31.320 | R-screen (F, KC) |
| 2 | 3.0 | 8.0 | 0.0 | on | 25 | 5.8000 | 1.715 | 0.0100 | 0.993–1.005 | 7.51–7.86 | 5.34–6.05 | 2.43–2.57 | 1.09 | n/a | n/a | n/a | 0.2496 | 43.653 | R-screen (KC) |
| 2 | 3.0 | 8.0 | 2.0 | off | 100 | 1.3500 | 3.288 | 0.0062 | 0.995–1.008 | 6.71–7.04 | 3.93–4.48 | 2.25–2.34 | 1.10 | n/a | n/a | n/a | 0.2499 | 35.654 | R-screen (F, KC) |
| 2 | 3.0 | 8.0 | 1.0 | on | 25 | 5.8000 | 1.688 | 0.0101 | 0.991–1.002 | 7.67–8.02 | 5.77–6.34 | 2.47–2.56 | 1.09 | n/a | n/a | n/a | 0.2508 | 45.016 | R-screen (central, KC) |
| 2 | 3.0 | 6.0 | 1.0 | on | 100 | 1.5000 | 2.138 | 0.0094 | 0.997–1.010 | 7.65–8.05 | 4.53–5.22 | 2.46–2.55 | 1.11 | n/a | n/a | n/a | 0.2510 | 43.866 | R-screen (central, KC) |
| 2 | 3.0 | 8.0 | 0.0 | off | 400 | 0.3500 | 3.601 | 0.0048 | 0.990–1.010 | 5.40–5.85 | 1.44–1.93 | 2.10–2.14 | 1.17 | n/a | n/a | n/a | 0.2518 | 27.390 | R-screen (F, KC) |
| 2 | 3.0 | 6.0 | 0.0 | off | 25 | 5.6000 | 1.974 | 0.0068 | 0.989–1.002 | 7.69–8.06 | 4.87–5.53 | 2.45–2.56 | 1.10 | n/a | n/a | n/a | 0.2531 | 38.685 | R-screen (central, KC) |
| 1 | 3.0 | 4.0 | 0.0 | off | 100 | 1.4500 | 2.368 | 0.0063 | 0.994–1.011 | 7.63–8.11 | 3.32–3.95 | 2.46–2.56 | 1.12 | n/a | n/a | n/a | 0.2612 | 37.350 | R-screen (central, KC) |
| 1 | 3.0 | 2.0 | 0.0 | off | 100 | 0.9000 | 3.897 | 0.0019 | 0.990–1.015 | 4.08–4.25 | 0.58–0.65 | 1.52–1.59 | 1.10 | n/a | n/a | n/a | 0.2615 | 53.999 | R-screen (F) |
| 2 | 3.0 | 6.0 | 0.0 | on | 25 | 5.6000 | 1.748 | 0.0096 | 0.995–1.010 | 7.74–8.10 | 4.91–5.52 | 2.47–2.57 | 1.10 | n/a | n/a | n/a | 0.2617 | 42.985 | R-screen (central, KC) |
| 2 | 4.0 | 2.0 | 0.0 | off | 400 | 0.3500 | 3.904 | 0.0058 | 0.993–1.006 | 6.29–6.88 | 1.55–1.97 | 1.18–1.29 | 1.19 | n/a | n/a | n/a | 0.2634 | 29.561 | R-screen (F) |
| 2 | 3.0 | 8.0 | 0.0 | on | 25 | 3.0000 | 2.825 | 0.0022 | 0.997–1.012 | 2.97–3.17 | 0.38–0.45 | 1.16–1.23 | 1.15 | n/a | n/a | n/a | 0.2644 | 25.700 | R-screen (DAN) |
| 2 | 3.0 | 6.0 | 0.0 | on | 400 | 0.3750 | 2.802 | 0.0089 | 0.991–1.007 | 6.86–7.34 | 2.69–3.46 | 2.42–2.62 | 1.14 | n/a | n/a | n/a | 0.2685 | 39.031 | R-screen (KC) |
| 2 | 3.0 | 6.0 | 1.0 | off | 25 | 5.6000 | 2.028 | 0.0070 | 0.994–1.003 | 7.85–8.22 | 5.28–5.86 | 2.47–2.55 | 1.09 | n/a | n/a | n/a | 0.2715 | 39.905 | R-screen (central, KC) |
| 2 | 3.0 | 8.0 | 1.0 | on | 100 | 0.9500 | 3.659 | 0.0028 | 0.991–1.026 | 3.40–3.64 | 0.46–0.55 | 1.39–1.46 | 1.17 | n/a | n/a | n/a | 0.2728 | 18.192 | R-screen (F, DAN) |
| 2 | 4.0 | 2.0 | 2.0 | off | 25 | 6.0000 | 1.686 | 0.0085 | 0.998–1.002 | 10.11–10.53 | 7.50–8.13 | 1.67–1.77 | 1.08 | n/a | n/a | n/a | 0.2748 | 49.826 | R-screen (central) |
| 2 | 3.0 | 8.0 | 2.0 | off | 25 | 5.6000 | 2.432 | 0.0071 | 0.997–1.001 | 7.80–8.12 | 6.03–6.61 | 2.53–2.60 | 1.08 | n/a | n/a | n/a | 0.2760 | 41.602 | R-screen (central, KC) |
| 2 | 3.0 | 6.0 | 0.0 | on | 100 | 1.1500 | 3.964 | 0.0047 | 0.978–1.009 | 4.43–4.83 | 0.79–1.03 | 1.78–1.87 | 1.20 | n/a | n/a | n/a | 0.2788 | 19.562 | R-screen (F) |
| 2 | 3.0 | 8.0 | 2.0 | off | 400 | 0.3250 | 3.587 | 0.0057 | 0.995–1.006 | 6.11–6.42 | 2.97–3.41 | 2.12–2.21 | 1.11 | n/a | n/a | n/a | 0.2792 | 31.757 | R-screen (F, KC) |
| 2 | 3.0 | 6.0 | 1.0 | off | 400 | 0.2750 | 3.970 | 0.0033 | 0.993–1.011 | 4.00–4.31 | 0.57–0.73 | 1.65–1.77 | 1.17 | n/a | n/a | n/a | 0.2800 | 18.634 | R-screen (F) |
| 1 | 3.0 | 3.0 | 0.0 | off | 100 | 0.9000 | 3.794 | 0.0021 | 0.990–1.020 | 3.72–3.89 | 0.48–0.52 | 1.51–1.59 | 1.11 | n/a | n/a | n/a | 0.2821 | 59.704 | R-screen (F, DAN) |
| 2 | 3.0 | 6.0 | 1.0 | on | 25 | 5.6000 | 1.711 | 0.0096 | 0.995–1.003 | 7.89–8.25 | 5.34–5.92 | 2.46–2.57 | 1.09 | n/a | n/a | n/a | 0.2830 | 44.287 | R-screen (central, KC) |
| 2 | 3.0 | 8.0 | 2.0 | on | 25 | 5.6000 | 1.695 | 0.0103 | 0.996–1.006 | 7.82–8.14 | 6.06–6.66 | 2.53–2.62 | 1.09 | n/a | n/a | n/a | 0.2854 | 46.295 | R-screen (central, KC) |
| 2 | 4.0 | 2.0 | 2.0 | on | 25 | 6.0000 | 1.859 | 0.0120 | 0.993–1.003 | 10.24–10.66 | 7.58–8.20 | 1.71–1.77 | 1.08 | n/a | n/a | n/a | 0.2872 | 55.797 | R-screen (central) |
| 2 | 3.0 | 8.0 | 2.0 | on | 400 | 0.3750 | 2.592 | 0.0101 | 0.995–1.006 | 7.49–7.84 | 5.08–5.70 | 2.54–2.67 | 1.10 | n/a | n/a | n/a | 0.2879 | 45.824 | R-screen (KC) |
| 2 | 3.0 | 8.0 | 1.0 | off | 25 | 2.8000 | 2.577 | 0.0017 | 0.980–1.015 | 3.00–3.18 | 0.37–0.44 | 1.10–1.18 | 1.13 | n/a | n/a | n/a | 0.2895 | 24.572 | R-screen (DAN) |
| 2 | 3.0 | 8.0 | 2.0 | on | 100 | 1.5000 | 2.136 | 0.0102 | 0.998–1.007 | 7.77–8.12 | 5.70–6.36 | 2.54–2.64 | 1.09 | n/a | n/a | n/a | 0.2913 | 47.186 | R-screen (central, KC) |
| 2 | 3.0 | 6.0 | 1.0 | on | 400 | 0.3250 | 3.729 | 0.0061 | 0.995–1.007 | 5.50–5.92 | 1.58–1.96 | 2.06–2.15 | 1.16 | n/a | n/a | n/a | 0.2915 | 27.678 | R-screen (F, KC) |
| 2 | 3.0 | 8.0 | 2.0 | on | 400 | 0.1875 | 3.337 | 0.0024 | 0.981–1.002 | 3.29–3.47 | 0.41–0.48 | 1.27–1.35 | 1.12 | n/a | n/a | n/a | 0.2928 | 18.604 | R-screen (F, DAN) |
| 1 | 3.0 | 4.0 | 0.0 | off | 100 | 1.0500 | 4.023 | 0.0030 | 0.982–1.009 | 4.11–4.43 | 0.57–0.70 | 1.73–1.80 | 1.18 | n/a | n/a | n/a | 0.2934 | 19.274 | R-screen (F) |
| 2 | 4.0 | 2.0 | 2.0 | on | 400 | 0.3625 | 3.601 | 0.0102 | 0.998–1.003 | 8.50–8.95 | 4.60–5.16 | 1.49–1.55 | 1.11 | n/a | n/a | n/a | 0.2944 | 46.939 | R-screen (F, central) |
| 2 | 3.0 | 8.0 | 1.0 | on | 400 | 0.3125 | 4.029 | 0.0054 | 0.995–1.016 | 4.76–5.13 | 1.21–1.52 | 1.88–1.96 | 1.16 | n/a | n/a | n/a | 0.2948 | 23.379 | R-screen (F) |
| 2 | 3.0 | 8.0 | 1.0 | on | 25 | 2.8000 | 2.550 | 0.0018 | 0.997–1.019 | 3.01–3.20 | 0.37–0.43 | 1.11–1.19 | 1.14 | n/a | n/a | n/a | 0.2957 | 23.873 | R-screen (DAN) |
| 2 | 3.0 | 8.0 | 0.0 | off | 25 | 6.0000 | 2.293 | 0.0071 | 0.994–1.005 | 7.84–8.18 | 6.00–6.59 | 2.52–2.64 | 1.09 | n/a | n/a | n/a | 0.2993 | 41.089 | R-screen (central, KC) |
| 2 | 3.0 | 6.0 | 0.0 | on | 25 | 2.8000 | 2.797 | 0.0016 | 0.985–1.016 | 3.05–3.21 | 0.37–0.40 | 1.17–1.23 | 1.12 | n/a | n/a | n/a | 0.3024 | 40.165 | R-screen (DAN) |
| 2 | 3.0 | 6.0 | 2.0 | on | 100 | 1.4500 | 2.096 | 0.0099 | 0.994–1.006 | 7.99–8.36 | 5.28–5.88 | 2.50–2.59 | 1.09 | n/a | n/a | n/a | 0.3030 | 46.134 | R-screen (central, KC) |
| 2 | 3.0 | 8.0 | 2.0 | off | 100 | 1.4000 | 3.336 | 0.0065 | 1.000–1.009 | 7.04–7.38 | 4.48–5.08 | 2.34–2.44 | 1.10 | n/a | n/a | n/a | 0.3041 | 37.951 | R-screen (F, KC) |
| 2 | 3.0 | 8.0 | 1.0 | off | 100 | 0.9000 | 3.284 | 0.0020 | 0.990–1.015 | 3.19–3.39 | 0.40–0.46 | 1.30–1.39 | 1.14 | n/a | n/a | n/a | 0.3046 | 22.875 | R-screen (F, DAN) |
| 2 | 3.0 | 6.0 | 1.0 | off | 100 | 0.9000 | 3.316 | 0.0021 | 0.988–0.996 | 3.45–3.65 | 0.41–0.48 | 1.38–1.47 | 1.13 | n/a | n/a | n/a | 0.3051 | 23.374 | R-screen (F, DAN) |
| 2 | 3.0 | 6.0 | 1.0 | off | 25 | 2.8000 | 2.549 | 0.0019 | 0.990–1.007 | 3.25–3.44 | 0.37–0.44 | 1.19–1.26 | 1.13 | n/a | n/a | n/a | 0.3051 | 24.847 | R-screen (DAN) |
| 2 | 3.0 | 6.0 | 1.0 | on | 25 | 2.8000 | 2.601 | 0.0021 | 0.998–1.019 | 3.26–3.44 | 0.37–0.43 | 1.19–1.25 | 1.13 | n/a | n/a | n/a | 0.3054 | 24.214 | R-screen (DAN) |
| 2 | 3.0 | 6.0 | 2.0 | off | 25 | 5.4000 | 2.021 | 0.0070 | 0.993–1.008 | 8.03–8.37 | 5.59–6.18 | 2.50–2.60 | 1.09 | n/a | n/a | n/a | 0.3065 | 41.319 | R-screen (central, KC) |
| 2 | 3.0 | 8.0 | 0.0 | on | 25 | 6.0000 | 1.715 | 0.0105 | 0.995–1.005 | 7.86–8.21 | 6.05–6.64 | 2.57–2.65 | 1.09 | n/a | n/a | n/a | 0.3071 | 46.276 | R-screen (central, KC) |
| 2 | 3.0 | 6.0 | 2.0 | off | 400 | 0.1750 | 3.168 | 0.0021 | 0.987–1.005 | 3.37–3.55 | 0.39–0.42 | 1.27–1.34 | 1.11 | n/a | n/a | n/a | 0.3087 | 25.246 | R-screen (F, DAN) |
| 2 | 3.0 | 6.0 | 2.0 | on | 25 | 5.4000 | 1.717 | 0.0099 | 0.996–1.008 | 8.04–8.40 | 5.65–6.24 | 2.50–2.60 | 1.09 | n/a | n/a | n/a | 0.3125 | 45.576 | R-screen (central, KC) |
| 1 | 4.0 | 1.0 | 0.0 | off | 100 | 1.4500 | 3.544 | 0.0078 | 0.989–1.012 | 8.69–9.27 | 4.07–4.83 | 1.35–1.55 | 1.13 | n/a | n/a | n/a | 0.3139 | 41.160 | R-screen (F, central) |
| 2 | 3.0 | 8.0 | 0.0 | off | 25 | 2.8000 | 2.812 | 0.0014 | 0.974–1.011 | 2.82–2.97 | 0.37–0.40 | 1.09–1.15 | 1.13 | n/a | n/a | n/a | 0.3139 | 42.684 | R-screen (DAN) |
| 1 | 3.0 | 8.0 | 0.0 | off | 100 | 1.5000 | 3.441 | 0.0064 | 0.999–1.008 | 6.82–7.21 | 3.74–4.36 | 2.31–2.39 | 1.11 | n/a | n/a | n/a | 0.3142 | 35.669 | R-screen (F, KC) |
| 2 | 3.0 | 6.0 | 2.0 | off | 100 | 1.4500 | 3.092 | 0.0074 | 0.997–1.007 | 7.92–8.28 | 5.16–5.78 | 2.48–2.57 | 1.09 | n/a | n/a | n/a | 0.3147 | 41.861 | R-screen (F, central, KC) |
| 2 | 3.0 | 6.0 | 2.0 | off | 400 | 0.3375 | 3.475 | 0.0061 | 0.995–1.011 | 6.93–7.26 | 3.50–4.00 | 2.28–2.37 | 1.10 | n/a | n/a | n/a | 0.3152 | 35.565 | R-screen (F, KC) |
| 2 | 3.0 | 8.0 | 0.0 | on | 25 | 2.8000 | 2.870 | 0.0018 | 0.982–1.012 | 2.83–2.97 | 0.36–0.38 | 1.09–1.16 | 1.13 | n/a | n/a | n/a | 0.3231 | 41.195 | R-screen (DAN) |
| 1 | 3.0 | 2.0 | 0.0 | off | 100 | 1.4000 | 2.415 | 0.0067 | 0.995–1.011 | 8.30–8.88 | 3.31–3.90 | 2.40–2.49 | 1.14 | n/a | n/a | n/a | 0.3247 | 38.834 | R-screen (central, KC) |
| 2 | 3.0 | 8.0 | 1.0 | off | 25 | 6.0000 | 2.309 | 0.0075 | 0.993–1.002 | 7.98–8.31 | 6.32–6.97 | 2.56–2.66 | 1.09 | n/a | n/a | n/a | 0.3248 | 42.311 | R-screen (central, KC) |
| 2 | 3.0 | 6.0 | 2.0 | on | 400 | 0.1875 | 3.510 | 0.0025 | 0.987–1.011 | 3.54–3.72 | 0.42–0.49 | 1.34–1.40 | 1.12 | n/a | n/a | n/a | 0.3255 | 19.049 | R-screen (F, DAN) |
| 1 | 3.0 | 3.0 | 0.0 | off | 100 | 0.9500 | 4.164 | 0.0023 | 0.990–0.996 | 3.89–4.11 | 0.52–0.58 | 1.59–1.66 | 1.13 | n/a | n/a | n/a | 0.3279 | 36.044 | R-screen (F) |
| 2 | 3.0 | 8.0 | 1.0 | on | 25 | 6.0000 | 1.688 | 0.0108 | 1.000–1.009 | 8.02–8.35 | 6.34–7.00 | 2.56–2.67 | 1.08 | n/a | n/a | n/a | 0.3322 | 47.402 | R-screen (central, KC) |
| 1 | 3.0 | 3.0 | 0.0 | off | 100 | 1.0500 | 4.183 | 0.0031 | 0.989–1.016 | 4.39–4.75 | 0.67–0.83 | 1.73–1.83 | 1.18 | n/a | n/a | n/a | 0.3324 | 18.718 | R-screen (F) |
| 1 | 3.0 | 3.0 | 0.0 | off | 100 | 1.0000 | 4.183 | 0.0027 | 0.989–1.005 | 4.11–4.39 | 0.58–0.67 | 1.66–1.73 | 1.16 | n/a | n/a | n/a | 0.3324 | 22.906 | R-screen (F) |
| 2 | 3.0 | 6.0 | 2.0 | on | 400 | 0.3750 | 2.466 | 0.0099 | 0.991–1.013 | 8.07–8.44 | 5.20–5.83 | 2.54–2.64 | 1.09 | n/a | n/a | n/a | 0.3328 | 47.114 | R-screen (central, KC) |
| 2 | 3.0 | 6.0 | 0.0 | off | 25 | 2.8000 | 2.725 | 0.0015 | 0.991–1.017 | 3.05–3.22 | 0.36–0.40 | 1.17–1.24 | 1.12 | n/a | n/a | n/a | 0.3346 | 43.597 | R-screen (DAN) |
| 2 | 3.0 | 6.0 | 0.0 | off | 25 | 5.8000 | 2.008 | 0.0075 | 0.989–1.003 | 8.06–8.43 | 5.53–6.12 | 2.56–2.65 | 1.09 | n/a | n/a | n/a | 0.3350 | 41.127 | R-screen (central, KC) |
| 2 | 3.0 | 8.0 | 2.0 | off | 400 | 0.1750 | 3.206 | 0.0020 | 0.978–1.022 | 3.12–3.27 | 0.38–0.42 | 1.20–1.27 | 1.12 | n/a | n/a | n/a | 0.3384 | 24.035 | R-screen (F, DAN) |
| 1 | 3.0 | 3.0 | 0.0 | off | 100 | 1.4500 | 2.213 | 0.0066 | 0.998–1.008 | 8.14–8.64 | 3.55–4.18 | 2.48–2.60 | 1.13 | n/a | n/a | n/a | 0.3385 | 39.151 | R-screen (central, KC) |
| 1 | 3.0 | 4.0 | 0.0 | off | 100 | 1.0000 | 4.182 | 0.0025 | 0.994–1.009 | 3.85–4.11 | 0.50–0.57 | 1.63–1.73 | 1.15 | n/a | n/a | n/a | 0.3389 | 23.845 | R-screen (F, DAN) |
| 2 | 4.0 | 2.0 | 2.0 | on | 400 | 0.3750 | 3.601 | 0.0108 | 0.996–1.001 | 8.95–9.41 | 5.16–5.77 | 1.55–1.64 | 1.10 | n/a | n/a | n/a | 0.3451 | 50.161 | R-screen (F, central) |
| 2 | 3.0 | 6.0 | 0.0 | on | 25 | 5.8000 | 1.706 | 0.0101 | 0.998–1.010 | 8.10–8.47 | 5.52–6.19 | 2.57–2.69 | 1.09 | n/a | n/a | n/a | 0.3536 | 45.606 | R-screen (central, KC) |
| 2 | 3.0 | 6.0 | 1.0 | on | 100 | 0.9500 | 3.955 | 0.0030 | 0.997–1.009 | 3.65–3.90 | 0.46–0.58 | 1.45–1.54 | 1.15 | n/a | n/a | n/a | 0.3589 | 18.844 | R-screen (F, DAN) |
| 2 | 3.0 | 8.0 | 2.0 | off | 25 | 5.8000 | 2.370 | 0.0075 | 0.997–1.004 | 8.12–8.45 | 6.61–7.21 | 2.60–2.71 | 1.08 | n/a | n/a | n/a | 0.3593 | 43.572 | R-screen (central, KC) |
| 1 | 3.0 | 4.0 | 0.0 | off | 100 | 1.5000 | 2.426 | 0.0070 | 0.994–1.007 | 8.11–8.57 | 3.95–4.65 | 2.56–2.67 | 1.11 | n/a | n/a | n/a | 0.3593 | 40.114 | R-screen (central, KC) |
| 2 | 3.0 | 6.0 | 1.0 | off | 25 | 5.8000 | 2.028 | 0.0072 | 0.991–1.006 | 8.22–8.58 | 5.86–6.48 | 2.55–2.67 | 1.09 | n/a | n/a | n/a | 0.3595 | 42.099 | R-screen (central, KC) |
| 2 | 3.0 | 6.0 | 1.0 | on | 25 | 5.8000 | 1.663 | 0.0103 | 0.989–1.003 | 8.25–8.62 | 5.92–6.59 | 2.57–2.68 | 1.09 | n/a | n/a | n/a | 0.3671 | 46.806 | R-screen (central, KC) |
| 2 | 3.0 | 6.0 | 0.0 | off | 400 | 0.3625 | 3.663 | 0.0054 | 0.996–1.014 | 6.31–6.79 | 1.99–2.56 | 2.28–2.37 | 1.15 | n/a | n/a | n/a | 0.3675 | 32.095 | R-screen (F, KC) |
| 2 | 3.0 | 8.0 | 2.0 | on | 25 | 5.8000 | 1.672 | 0.0108 | 0.996–1.004 | 8.14–8.47 | 6.66–7.25 | 2.62–2.74 | 1.08 | n/a | n/a | n/a | 0.3714 | 48.575 | R-screen (central, KC) |
| 1 | 4.0 | 1.0 | 0.0 | off | 100 | 1.5000 | 3.544 | 0.0080 | 0.994–1.002 | 9.27–9.83 | 4.83–5.43 | 1.51–1.55 | 1.12 | n/a | n/a | n/a | 0.3728 | 44.837 | R-screen (F, central) |
| 2 | 4.0 | 2.0 | 0.0 | on | 100 | 1.2000 | 4.359 | 0.0057 | 0.985–1.000 | 5.17–5.66 | 1.13–1.40 | 0.98–1.04 | 1.22 | n/a | n/a | n/a | 0.3736 | 21.693 | R-screen (F) |
| 2 | 4.0 | 2.0 | 2.0 | on | 400 | 0.3375 | 4.332 | 0.0090 | 0.995–1.012 | 7.62–8.05 | 4.04–4.10 | 1.44–1.94 | 1.12 | n/a | n/a | n/a | 0.3743 | 42.581 | R-screen (F, central) |
| 1 | 3.0 | 2.0 | 0.0 | off | 100 | 1.1000 | 4.371 | 0.0036 | 0.992–1.007 | 5.17–5.62 | 1.06–1.28 | 1.81–1.89 | 1.18 | n/a | n/a | n/a | 0.3765 | 18.414 | R-screen (F) |
| 2 | 3.0 | 6.0 | 1.0 | off | 400 | 0.3625 | 3.628 | 0.0058 | 0.992–1.010 | 6.71–7.12 | 2.81–3.45 | 2.31–2.42 | 1.12 | n/a | n/a | n/a | 0.3806 | 34.666 | R-screen (F, KC) |
| 2 | 3.0 | 8.0 | 1.0 | off | 100 | 1.5000 | 3.628 | 0.0069 | 0.998–1.009 | 7.06–7.43 | 4.34–5.01 | 2.34–2.42 | 1.11 | n/a | n/a | n/a | 0.3809 | 37.451 | R-screen (F, KC) |
| 2 | 3.0 | 6.0 | 1.0 | on | 400 | 0.3125 | 4.286 | 0.0058 | 0.995–1.018 | 5.09–5.50 | 1.26–1.58 | 1.96–2.06 | 1.17 | n/a | n/a | n/a | 0.3838 | 24.292 | R-screen (F, KC) |
| 2 | 3.0 | 6.0 | 2.0 | on | 100 | 1.5000 | 2.095 | 0.0105 | 0.994–1.003 | 8.36–8.73 | 5.88–6.56 | 2.59–2.69 | 1.09 | n/a | n/a | n/a | 0.3841 | 48.792 | R-screen (central, KC) |
| 2 | 3.0 | 6.0 | 2.0 | off | 25 | 5.6000 | 2.031 | 0.0076 | 0.999–1.002 | 8.37–8.72 | 6.18–6.80 | 2.60–2.70 | 1.09 | n/a | n/a | n/a | 0.3883 | 43.522 | R-screen (central, KC) |
| 2 | 3.0 | 8.0 | 1.0 | off | 100 | 0.8500 | 3.284 | 0.0020 | 0.987–1.012 | 3.02–3.19 | 0.37–0.40 | 1.23–1.30 | 1.13 | n/a | n/a | n/a | 0.3903 | 32.482 | R-screen (F, DAN) |
| 2 | 3.0 | 8.0 | 0.0 | on | 100 | 1.1000 | 4.440 | 0.0036 | 0.988–1.009 | 3.76–4.13 | 0.59–0.75 | 1.60–1.71 | 1.20 | n/a | n/a | n/a | 0.3920 | 17.366 | R-screen (F) |
| 2 | 3.0 | 6.0 | 2.0 | on | 25 | 5.6000 | 1.703 | 0.0104 | 0.997–1.008 | 8.40–8.75 | 6.24–6.85 | 2.60–2.71 | 1.09 | n/a | n/a | n/a | 0.3920 | 48.053 | R-screen (central, KC) |
| 2 | 3.0 | 8.0 | 1.0 | off | 400 | 0.3500 | 3.971 | 0.0057 | 0.989–1.004 | 5.84–6.24 | 2.22–2.78 | 2.14–2.24 | 1.14 | n/a | n/a | n/a | 0.3929 | 30.492 | R-screen (F, KC) |
| 1 | 3.0 | 2.0 | 0.0 | off | 100 | 0.9500 | 4.452 | 0.0025 | 0.987–1.012 | 4.25–4.49 | 0.65–0.74 | 1.59–1.65 | 1.13 | n/a | n/a | n/a | 0.3947 | 32.725 | R-screen (F) |
| 2 | 3.0 | 6.0 | 1.0 | off | 100 | 0.8500 | 3.316 | 0.0020 | 0.988–1.016 | 3.28–3.45 | 0.37–0.41 | 1.32–1.38 | 1.12 | n/a | n/a | n/a | 0.3947 | 32.689 | R-screen (F, DAN) |
| 2 | 3.0 | 8.0 | 2.0 | off | 100 | 1.4500 | 3.545 | 0.0068 | 0.998–1.009 | 7.38–7.71 | 5.08–5.66 | 2.44–2.53 | 1.09 | n/a | n/a | n/a | 0.4009 | 40.090 | R-screen (F, KC) |
| 2 | 3.0 | 8.0 | 1.0 | on | 400 | 0.3000 | 4.510 | 0.0050 | 0.995–1.005 | 4.40–4.76 | 0.97–1.21 | 1.79–1.88 | 1.17 | n/a | n/a | n/a | 0.4077 | 20.676 | R-screen (F) |
| 2 | 3.0 | 8.0 | 2.0 | on | 400 | 0.1750 | 3.434 | 0.0021 | 0.981–1.002 | 3.12–3.29 | 0.38–0.41 | 1.21–1.27 | 1.12 | n/a | n/a | n/a | 0.4106 | 23.239 | R-screen (F, DAN) |
| 2 | 3.0 | 6.0 | 0.0 | off | 400 | 0.3750 | 3.684 | 0.0061 | 0.995–1.014 | 6.79–7.26 | 2.56–3.21 | 2.37–2.46 | 1.14 | n/a | n/a | n/a | 0.4106 | 35.140 | R-screen (F, KC) |
| 2 | 3.0 | 6.0 | 0.0 | off | 25 | 6.0000 | 2.008 | 0.0075 | 0.994–1.004 | 8.43–8.80 | 6.12–6.77 | 2.65–2.77 | 1.09 | n/a | n/a | n/a | 0.4219 | 43.261 | R-screen (central, KC) |
| 1 | 3.0 | 3.0 | 0.0 | off | 100 | 1.5000 | 2.163 | 0.0069 | 0.991–1.008 | 8.64–9.14 | 4.18–4.85 | 2.60–2.67 | 1.12 | n/a | n/a | n/a | 0.4231 | 42.058 | R-screen (central, KC) |
| 2 | 3.0 | 6.0 | 0.0 | on | 25 | 6.0000 | 1.706 | 0.0107 | 0.993–1.004 | 8.47–8.83 | 6.19–6.79 | 2.69–2.78 | 1.09 | n/a | n/a | n/a | 0.4269 | 48.293 | R-screen (central, KC) |
| 2 | 3.0 | 6.0 | 2.0 | off | 100 | 1.5000 | 3.203 | 0.0076 | 0.994–1.005 | 8.28–8.65 | 5.78–6.43 | 2.57–2.66 | 1.09 | n/a | n/a | n/a | 0.4272 | 44.093 | R-screen (F, central, KC) |
| 1 | 3.0 | 2.0 | 0.0 | off | 100 | 1.4500 | 2.373 | 0.0069 | 0.994–1.009 | 8.88–9.43 | 3.90–4.53 | 2.49–2.60 | 1.13 | n/a | n/a | n/a | 0.4272 | 42.256 | R-screen (central, KC) |
| 2 | 3.0 | 6.0 | 1.0 | off | 400 | 0.3750 | 3.705 | 0.0066 | 0.995–1.010 | 7.12–7.53 | 3.45–4.03 | 2.42–2.48 | 1.12 | n/a | n/a | n/a | 0.4273 | 37.446 | R-screen (F, KC) |
| 1 | 3.0 | 4.0 | 0.0 | off | 100 | 0.9500 | 4.182 | 0.0023 | 0.978–1.010 | 3.64–3.85 | 0.45–0.50 | 1.56–1.63 | 1.13 | n/a | n/a | n/a | 0.4273 | 35.765 | R-screen (F, DAN) |
| 2 | 3.0 | 8.0 | 2.0 | off | 25 | 6.0000 | 2.479 | 0.0079 | 0.996–1.004 | 8.45–8.77 | 7.21–7.82 | 2.71–2.80 | 1.08 | n/a | n/a | n/a | 0.4286 | 45.514 | R-screen (central, KC) |
| 2 | 3.0 | 6.0 | 2.0 | on | 400 | 0.1750 | 3.510 | 0.0024 | 0.992–1.035 | 3.37–3.54 | 0.38–0.42 | 1.28–1.34 | 1.11 | n/a | n/a | n/a | 0.4290 | 25.402 | R-screen (F, DAN) |
| 2 | 4.0 | 2.0 | 1.0 | on | 400 | 0.3750 | 4.332 | 0.0096 | 0.995–1.006 | 7.99–8.51 | 3.40–4.07 | 1.39–1.55 | 1.13 | n/a | n/a | n/a | 0.4290 | 44.338 | R-screen (F, central) |
| 2 | 3.0 | 6.0 | 2.0 | off | 400 | 0.3500 | 3.781 | 0.0065 | 0.993–1.003 | 7.26–7.62 | 4.00–4.52 | 2.37–2.44 | 1.10 | n/a | n/a | n/a | 0.4294 | 37.952 | R-screen (F, KC) |
| 1 | 3.0 | 4.0 | 0.0 | off | 100 | 0.9000 | 3.912 | 0.0019 | 0.978–1.014 | 3.49–3.64 | 0.42–0.45 | 1.49–1.56 | 1.10 | n/a | n/a | n/a | 0.4370 | 61.359 | R-screen (F, DAN) |
| 1 | 3.0 | 1.0 | 0.0 | off | 100 | 0.9000 | 4.665 | 0.0025 | 0.993–1.021 | 4.64–4.85 | 0.86–0.98 | 1.54–1.61 | 1.11 | n/a | n/a | n/a | 0.4416 | 46.850 | R-screen (F) |
| 2 | 3.0 | 8.0 | 2.0 | on | 25 | 6.0000 | 1.682 | 0.0115 | 0.998–1.009 | 8.47–8.80 | 7.25–7.87 | 2.74–2.83 | 1.08 | n/a | n/a | n/a | 0.4417 | 50.808 | R-screen (central, KC) |
| 2 | 3.0 | 6.0 | 1.0 | off | 25 | 6.0000 | 1.990 | 0.0077 | 0.991–1.007 | 8.58–8.94 | 6.48–7.14 | 2.67–2.79 | 1.08 | n/a | n/a | n/a | 0.4439 | 44.448 | R-screen (central, KC) |
| 2 | 3.0 | 8.0 | 2.0 | off | 100 | 1.5000 | 3.545 | 0.0075 | 0.993–1.009 | 7.71–8.05 | 5.66–6.31 | 2.53–2.62 | 1.09 | n/a | n/a | n/a | 0.4447 | 42.251 | R-screen (F, central, KC) |
| 2 | 3.0 | 6.0 | 1.0 | on | 25 | 6.0000 | 1.690 | 0.0111 | 0.989–1.002 | 8.62–8.98 | 6.59–7.23 | 2.68–2.78 | 1.09 | n/a | n/a | n/a | 0.4467 | 49.396 | R-screen (central, KC) |
| 2 | 3.0 | 6.0 | 0.0 | on | 100 | 1.1000 | 4.703 | 0.0038 | 0.984–1.011 | 4.04–4.43 | 0.60–0.79 | 1.68–1.78 | 1.20 | n/a | n/a | n/a | 0.4495 | 18.243 | R-screen (F) |
| 2 | 3.0 | 8.0 | 2.0 | off | 400 | 0.3375 | 3.931 | 0.0061 | 0.995–1.006 | 6.42–6.76 | 3.41–3.95 | 2.21–2.40 | 1.11 | n/a | n/a | n/a | 0.4517 | 34.281 | R-screen (F, KC) |
| 1 | 3.0 | 2.0 | 0.0 | off | 100 | 1.0500 | 4.725 | 0.0033 | 0.992–1.020 | 4.80–5.17 | 0.87–1.06 | 1.74–1.81 | 1.17 | n/a | n/a | n/a | 0.4542 | 17.978 | R-screen (F) |
| 1 | 3.0 | 2.0 | 0.0 | off | 100 | 1.0000 | 4.725 | 0.0029 | 0.987–1.020 | 4.49–4.80 | 0.74–0.87 | 1.65–1.74 | 1.15 | n/a | n/a | n/a | 0.4542 | 21.460 | R-screen (F) |
| 1 | 3.0 | 1.0 | 0.0 | off | 100 | 1.2000 | 4.507 | 0.0052 | 0.988–1.010 | 7.05–7.67 | 2.30–2.72 | 2.00–2.10 | 1.18 | n/a | n/a | n/a | 0.4546 | 26.891 | R-screen (F, KC) |
| 1 | 3.0 | 8.0 | 0.0 | off | 100 | 1.0000 | 3.902 | 0.0022 | 0.997–1.020 | 3.20–3.42 | 0.41–0.47 | 1.44–1.52 | 1.18 | n/a | n/a | n/a | 0.4552 | 24.950 | R-screen (F, DAN) |
| 2 | 4.0 | 2.0 | 1.0 | on | 400 | 0.3625 | 4.749 | 0.0090 | 0.995–1.006 | 7.46–7.99 | 2.85–3.40 | 1.32–1.39 | 1.14 | n/a | n/a | n/a | 0.4593 | 40.654 | R-screen (F) |
| 2 | 3.0 | 8.0 | 1.0 | on | 100 | 0.9000 | 3.805 | 0.0026 | 0.991–1.015 | 3.20–3.40 | 0.40–0.46 | 1.30–1.39 | 1.15 | n/a | n/a | n/a | 0.4608 | 21.718 | R-screen (F, DAN) |
| 1 | 3.0 | 1.0 | 0.0 | off | 100 | 1.2500 | 4.218 | 0.0061 | 0.991–1.007 | 7.67–8.29 | 2.72–3.21 | 2.10–2.19 | 1.17 | n/a | n/a | n/a | 0.4650 | 31.360 | R-screen (F, central, KC) |
| 2 | 3.0 | 6.0 | 2.0 | off | 25 | 5.8000 | 2.031 | 0.0077 | 0.998–1.004 | 8.72–9.08 | 6.80–7.45 | 2.70–2.81 | 1.08 | n/a | n/a | n/a | 0.4678 | 45.682 | R-screen (central, KC) |
| 2 | 3.0 | 6.0 | 2.0 | on | 25 | 5.8000 | 1.715 | 0.0110 | 0.997–1.009 | 8.75–9.10 | 6.85–7.49 | 2.71–2.81 | 1.08 | n/a | n/a | n/a | 0.4682 | 50.441 | R-screen (central, KC) |
| 2 | 3.0 | 8.0 | 0.0 | off | 400 | 0.3625 | 4.139 | 0.0056 | 0.993–1.010 | 5.85–6.31 | 1.93–2.55 | 2.14–2.32 | 1.15 | n/a | n/a | n/a | 0.4707 | 30.406 | R-screen (F, KC) |
| 2 | 3.0 | 6.0 | 1.0 | on | 400 | 0.3000 | 4.836 | 0.0051 | 0.999–1.025 | 4.70–5.09 | 0.99–1.26 | 1.83–1.96 | 1.18 | n/a | n/a | n/a | 0.4774 | 21.538 | R-screen (F) |
| 1 | 3.0 | 1.0 | 0.0 | off | 100 | 1.1500 | 4.849 | 0.0048 | 0.984–1.010 | 6.49–7.05 | 1.95–2.30 | 1.91–2.00 | 1.18 | n/a | n/a | n/a | 0.4813 | 22.422 | R-screen (F, KC) |
| 2 | 3.0 | 6.0 | 1.0 | off | 100 | 0.8000 | 3.257 | 0.0019 | 0.980–1.016 | 3.13–3.28 | 0.33–0.37 | 1.26–1.32 | 1.11 | n/a | n/a | n/a | 0.4845 | 54.139 | R-screen (F, DAN) |
| 2 | 3.0 | 8.0 | 1.0 | off | 100 | 0.8000 | 3.302 | 0.0016 | 0.987–1.030 | 2.89–3.02 | 0.34–0.37 | 1.18–1.23 | 1.11 | n/a | n/a | n/a | 0.4846 | 51.900 | R-screen (F, DAN) |
| 2 | 4.0 | 2.0 | 0.0 | on | 400 | 0.3750 | 4.767 | 0.0097 | 0.998–1.006 | 7.61–8.21 | 2.49–3.12 | 1.33–1.43 | 1.15 | n/a | n/a | n/a | 0.4885 | 41.975 | R-screen (F, central) |
| 2 | 3.0 | 8.0 | 1.0 | off | 400 | 0.3625 | 4.108 | 0.0060 | 0.989–1.004 | 6.24–6.64 | 2.78–3.39 | 2.24–2.39 | 1.13 | n/a | n/a | n/a | 0.4911 | 33.134 | R-screen (F, KC) |
| 2 | 3.0 | 6.0 | 0.0 | on | 400 | 0.3375 | 4.461 | 0.0062 | 0.992–1.003 | 5.37–5.87 | 1.19–1.58 | 2.11–2.20 | 1.19 | n/a | n/a | n/a | 0.4928 | 27.464 | R-screen (F, KC) |
| 2 | 3.0 | 6.0 | 2.0 | off | 400 | 0.3625 | 3.905 | 0.0070 | 0.993–1.007 | 7.62–7.98 | 4.52–5.03 | 2.44–2.52 | 1.09 | n/a | n/a | n/a | 0.4954 | 40.417 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 2.0 | off | 100 | 1.3000 | 3.851 | 0.0064 | 0.996–1.004 | 7.47–7.89 | 4.12–4.44 | 1.37–2.56 | 1.11 | n/a | n/a | n/a | 0.4964 | 39.128 | R-screen (F, KC) |
| 2 | 3.0 | 6.0 | 1.0 | on | 100 | 0.9000 | 3.955 | 0.0026 | 0.984–1.011 | 3.44–3.65 | 0.40–0.46 | 1.40–1.45 | 1.13 | n/a | n/a | n/a | 0.5002 | 22.882 | R-screen (F, DAN) |
| 1 | 3.0 | 6.0 | 0.0 | off | 100 | 1.0000 | 4.235 | 0.0025 | 0.990–1.005 | 3.45–3.69 | 0.43–0.50 | 1.50–1.58 | 1.17 | n/a | n/a | n/a | 0.5017 | 23.961 | R-screen (F, DAN) |
| 2 | 3.0 | 8.0 | 0.0 | off | 400 | 0.3125 | 4.962 | 0.0033 | 0.983–1.012 | 3.99–4.43 | 0.64–0.78 | 1.84–1.89 | 1.23 | n/a | n/a | n/a | 0.5031 | 18.668 | R-screen (F) |
| 2 | 3.0 | 6.0 | 1.0 | off | 400 | 0.2625 | 4.528 | 0.0028 | 0.982–1.005 | 3.76–4.00 | 0.46–0.57 | 1.58–1.65 | 1.15 | n/a | n/a | n/a | 0.5052 | 20.293 | R-screen (F, DAN) |
| 2 | 3.0 | 8.0 | 1.0 | on | 400 | 0.2875 | 4.990 | 0.0044 | 0.990–1.010 | 4.07–4.40 | 0.74–0.97 | 1.70–1.79 | 1.17 | n/a | n/a | n/a | 0.5089 | 18.866 | R-screen (F) |
| 1 | 3.0 | 8.0 | 0.0 | off | 100 | 0.9500 | 3.916 | 0.0021 | 1.006–1.031 | 3.02–3.20 | 0.39–0.41 | 1.36–1.44 | 1.14 | n/a | n/a | n/a | 0.5143 | 38.694 | R-screen (F, DAN) |
| 2 | 3.0 | 8.0 | 2.0 | off | 400 | 0.3500 | 4.156 | 0.0066 | 0.995–0.999 | 6.76–7.09 | 3.95–4.41 | 2.40–2.42 | 1.10 | n/a | n/a | n/a | 0.5165 | 36.856 | R-screen (F, KC) |
| 2 | 3.0 | 6.0 | 1.0 | off | 100 | 0.7500 | 3.143 | 0.0016 | 0.980–1.014 | 3.03–3.13 | 0.31–0.33 | 1.20–1.26 | 1.08 | n/a | n/a | n/a | 0.5210 | 84.812 | R-screen (F, DAN) |
| 2 | 4.0 | 2.0 | 1.0 | on | 400 | 0.3500 | 5.052 | 0.0081 | 0.992–1.007 | 6.94–7.46 | 2.47–2.85 | 1.32–1.37 | 1.15 | n/a | n/a | n/a | 0.5211 | 36.910 | R-screen (F) |
| 1 | 4.0 | 3.0 | 0.0 | off | 100 | 1.3500 | 4.297 | 0.0059 | 0.991–1.022 | 6.13–6.63 | 1.91–3.08 | 1.20–2.36 | 1.16 | n/a | n/a | n/a | 0.5237 | 27.940 | R-screen (F, KC) |
| 1 | 4.0 | 3.0 | 0.0 | off | 100 | 1.4000 | 4.297 | 0.0059 | 0.996–1.022 | 6.63–7.09 | 2.88–3.08 | 1.34–2.36 | 1.14 | n/a | n/a | n/a | 0.5237 | 34.257 | R-screen (F, KC) |
| 1 | 3.0 | 2.0 | 0.0 | off | 100 | 1.5000 | 2.316 | 0.0075 | 0.994–1.009 | 9.43–9.97 | 4.53–5.24 | 2.60–2.72 | 1.12 | n/a | n/a | n/a | 0.5261 | 45.395 | R-screen (central, KC) |
| 2 | 3.0 | 6.0 | 0.0 | on | 100 | 1.0500 | 5.078 | 0.0034 | 0.982–1.011 | 3.71–4.04 | 0.50–0.60 | 1.58–1.68 | 1.20 | n/a | n/a | n/a | 0.5263 | 18.136 | R-screen (F) |
| 2 | 3.0 | 8.0 | 1.0 | off | 400 | 0.2625 | 4.533 | 0.0028 | 0.991–1.010 | 3.49–3.72 | 0.45–0.55 | 1.50–1.58 | 1.16 | n/a | n/a | n/a | 0.5268 | 19.365 | R-screen (F, DAN) |
| 1 | 3.0 | 1.0 | 0.0 | off | 100 | 0.9500 | 5.092 | 0.0027 | 0.983–1.017 | 4.85–5.13 | 0.98–1.13 | 1.61–1.68 | 1.15 | n/a | n/a | n/a | 0.5290 | 29.966 | R-screen (F) |
| 2 | 3.0 | 8.0 | 0.0 | on | 100 | 1.0500 | 4.868 | 0.0032 | 0.994–1.009 | 3.44–3.76 | 0.48–0.59 | 1.53–1.60 | 1.20 | n/a | n/a | n/a | 0.5293 | 18.211 | R-screen (F, DAN) |
| 2 | 3.0 | 6.0 | 1.0 | on | 100 | 0.8500 | 3.686 | 0.0022 | 0.984–1.011 | 3.29–3.44 | 0.36–0.40 | 1.32–1.40 | 1.11 | n/a | n/a | n/a | 0.5376 | 33.362 | R-screen (F, DAN) |
| 2 | 3.0 | 8.0 | 1.0 | off | 100 | 0.7500 | 3.302 | 0.0015 | 0.983–1.030 | 2.78–2.89 | 0.32–0.34 | 1.10–1.18 | 1.09 | n/a | n/a | n/a | 0.5400 | 85.795 | R-screen (F, DAN) |
| 1 | 3.0 | 1.0 | 0.0 | off | 100 | 1.3000 | 3.961 | 0.0068 | 0.993–1.005 | 8.29–8.93 | 3.21–3.78 | 2.19–2.33 | 1.15 | n/a | n/a | n/a | 0.5406 | 35.916 | R-screen (F, central, KC) |
| 2 | 3.0 | 6.0 | 2.0 | off | 25 | 6.0000 | 2.028 | 0.0082 | 0.995–1.005 | 9.08–9.44 | 7.45–8.08 | 2.81–2.91 | 1.08 | n/a | n/a | n/a | 0.5408 | 47.752 | R-screen (central, KC) |
| 2 | 3.0 | 6.0 | 0.0 | off | 400 | 0.3125 | 5.141 | 0.0037 | 0.989–1.006 | 4.30–4.78 | 0.68–0.85 | 1.93–2.01 | 1.24 | n/a | n/a | n/a | 0.5415 | 19.394 | R-screen (F, KC) |
| 2 | 3.0 | 8.0 | 0.0 | off | 400 | 0.3750 | 4.293 | 0.0061 | 0.993–1.004 | 6.31–6.74 | 2.55–3.20 | 2.32–2.41 | 1.14 | n/a | n/a | n/a | 0.5432 | 33.496 | R-screen (F, KC) |
| 2 | 3.0 | 6.0 | 2.0 | on | 25 | 6.0000 | 1.715 | 0.0116 | 0.997–1.009 | 9.10–9.46 | 7.49–8.11 | 2.81–2.92 | 1.08 | n/a | n/a | n/a | 0.5459 | 52.613 | R-screen (central, KC) |
| 2 | 3.0 | 8.0 | 1.0 | on | 100 | 0.8000 | 3.574 | 0.0018 | 0.978–1.018 | 2.88–3.02 | 0.34–0.36 | 1.17–1.23 | 1.11 | n/a | n/a | n/a | 0.5481 | 49.604 | R-screen (F, DAN) |
| 1 | 3.0 | 1.0 | 0.0 | off | 100 | 1.0000 | 5.210 | 0.0032 | 0.983–1.017 | 5.13–5.54 | 1.13–1.39 | 1.68–1.77 | 1.16 | n/a | n/a | n/a | 0.5520 | 19.579 | R-screen (F) |
| 2 | 4.0 | 2.0 | 1.0 | on | 100 | 1.4000 | 4.575 | 0.0088 | 0.997–1.012 | 7.57–8.04 | 3.84–3.98 | 1.36–2.28 | 1.13 | n/a | n/a | n/a | 0.5571 | 43.094 | R-screen (F, central, KC) |
| 2 | 3.0 | 8.0 | 1.0 | on | 100 | 0.8500 | 3.805 | 0.0020 | 0.978–1.015 | 3.02–3.20 | 0.36–0.40 | 1.23–1.30 | 1.13 | n/a | n/a | n/a | 0.5599 | 31.200 | R-screen (F, DAN) |
| 2 | 3.0 | 6.0 | 2.0 | off | 400 | 0.3750 | 3.944 | 0.0074 | 0.994–1.007 | 7.98–8.33 | 5.03–5.67 | 2.52–2.60 | 1.09 | n/a | n/a | n/a | 0.5754 | 42.671 | R-screen (F, central, KC) |
| 2 | 3.0 | 6.0 | 1.0 | on | 100 | 0.7500 | 3.318 | 0.0014 | 0.987–1.003 | 3.03–3.13 | 0.31–0.33 | 1.20–1.24 | 1.09 | n/a | n/a | n/a | 0.5768 | 83.362 | R-screen (F, DAN) |
| 2 | 3.0 | 6.0 | 1.0 | on | 100 | 0.8000 | 3.532 | 0.0017 | 0.987–1.006 | 3.13–3.29 | 0.33–0.36 | 1.24–1.32 | 1.10 | n/a | n/a | n/a | 0.5777 | 49.944 | R-screen (F, DAN) |
| 2 | 3.0 | 8.0 | 2.0 | off | 400 | 0.3625 | 4.219 | 0.0074 | 0.993–1.006 | 7.09–7.43 | 4.41–5.01 | 2.42–2.54 | 1.10 | n/a | n/a | n/a | 0.5798 | 39.073 | R-screen (F, KC) |
| 1 | 3.0 | 8.0 | 0.0 | off | 100 | 0.9000 | 3.916 | 0.0017 | 0.996–1.031 | 2.86–3.02 | 0.36–0.39 | 1.27–1.36 | 1.13 | n/a | n/a | n/a | 0.5831 | 69.288 | R-screen (F, DAN) |
| 1 | 3.0 | 1.0 | 0.0 | off | 100 | 1.0500 | 5.381 | 0.0035 | 0.993–1.010 | 5.54–5.97 | 1.39–1.63 | 1.77–1.85 | 1.17 | n/a | n/a | n/a | 0.5843 | 17.192 | R-screen (F) |
| 1 | 3.0 | 1.0 | 0.0 | off | 100 | 1.1000 | 5.381 | 0.0041 | 0.984–1.010 | 5.97–6.49 | 1.63–1.95 | 1.85–1.91 | 1.18 | n/a | n/a | n/a | 0.5843 | 18.744 | R-screen (F) |
| 2 | 3.0 | 6.0 | 1.0 | on | 400 | 0.2875 | 5.409 | 0.0047 | 0.993–1.025 | 4.33–4.70 | 0.74–0.99 | 1.73–1.83 | 1.18 | n/a | n/a | n/a | 0.5895 | 19.522 | R-screen (F) |
| 2 | 3.0 | 8.0 | 1.0 | off | 400 | 0.3750 | 4.451 | 0.0064 | 0.991–1.004 | 6.64–7.04 | 3.39–4.03 | 2.39–2.43 | 1.12 | n/a | n/a | n/a | 0.5901 | 35.961 | R-screen (F, KC) |
| 1 | 3.0 | 6.0 | 0.0 | off | 100 | 0.9000 | 3.961 | 0.0018 | 0.975–1.006 | 3.11–3.26 | 0.36–0.39 | 1.35–1.43 | 1.11 | n/a | n/a | n/a | 0.5953 | 66.036 | R-screen (F, DAN) |
| 1 | 3.0 | 6.0 | 0.0 | off | 100 | 0.9500 | 4.235 | 0.0022 | 0.975–1.005 | 3.26–3.45 | 0.39–0.43 | 1.43–1.50 | 1.14 | n/a | n/a | n/a | 0.6004 | 38.934 | R-screen (F, DAN) |
| 2 | 3.0 | 8.0 | 1.0 | on | 100 | 0.7500 | 3.536 | 0.0015 | 0.986–1.018 | 2.79–2.88 | 0.32–0.34 | 1.10–1.17 | 1.08 | n/a | n/a | n/a | 0.6231 | 85.346 | R-screen (F, DAN) |
| 1 | 3.0 | 1.0 | 0.0 | off | 100 | 1.3500 | 3.961 | 0.0071 | 0.993–1.007 | 8.93–9.54 | 3.78–4.34 | 2.33–2.39 | 1.14 | n/a | n/a | n/a | 0.6334 | 40.305 | R-screen (F, central, KC) |
| 2 | 3.0 | 8.0 | 1.0 | on | 400 | 0.2750 | 5.797 | 0.0039 | 0.987–1.010 | 3.77–4.07 | 0.58–0.74 | 1.62–1.70 | 1.17 | n/a | n/a | n/a | 0.6588 | 17.885 | R-screen (F) |
| 2 | 4.0 | 2.0 | 0.0 | on | 400 | 0.3625 | 5.811 | 0.0085 | 0.998–1.006 | 7.01–7.61 | 1.99–2.49 | 1.26–1.33 | 1.17 | n/a | n/a | n/a | 0.6611 | 37.790 | R-screen (F) |
| 2 | 3.0 | 8.0 | 0.0 | on | 400 | 0.3250 | 5.767 | 0.0053 | 0.979–1.010 | 4.49–4.97 | 0.87–1.15 | 1.94–2.03 | 1.22 | n/a | n/a | n/a | 0.6681 | 22.009 | R-screen (F, KC) |
| 2 | 3.0 | 6.0 | 1.0 | off | 400 | 0.2500 | 4.732 | 0.0027 | 0.982–1.025 | 3.55–3.76 | 0.40–0.46 | 1.49–1.58 | 1.13 | n/a | n/a | n/a | 0.6687 | 24.841 | R-screen (F, DAN) |
| 1 | 3.0 | 1.0 | 0.0 | off | 100 | 1.4500 | 3.382 | 0.0083 | 0.995–1.001 | 10.18–10.81 | 5.02–5.69 | 2.50–2.57 | 1.12 | n/a | n/a | n/a | 0.6732 | 47.981 | R-screen (F, central, KC) |
| 2 | 3.0 | 6.0 | 0.0 | on | 100 | 1.0000 | 5.078 | 0.0031 | 0.982–1.006 | 3.46–3.71 | 0.43–0.50 | 1.50–1.58 | 1.17 | n/a | n/a | n/a | 0.6788 | 23.374 | R-screen (F, DAN) |
| 1 | 3.0 | 1.0 | 0.0 | off | 100 | 1.4000 | 3.794 | 0.0076 | 0.995–1.007 | 9.54–10.18 | 4.34–5.02 | 2.39–2.50 | 1.13 | n/a | n/a | n/a | 0.7008 | 44.139 | R-screen (F, central, KC) |
| 2 | 4.0 | 2.0 | 1.0 | off | 400 | 0.3500 | 5.326 | 0.0063 | 0.999–1.021 | 6.83–7.34 | 2.80–3.04 | 1.35–2.28 | 1.15 | n/a | n/a | n/a | 0.7028 | 35.621 | R-screen (F, KC) |
| 2 | 3.0 | 6.0 | 1.0 | off | 400 | 0.2250 | 4.510 | 0.0019 | 0.989–1.018 | 3.22–3.37 | 0.37–0.38 | 1.36–1.43 | 1.11 | n/a | n/a | n/a | 0.7059 | 61.968 | R-screen (F, DAN) |
| 2 | 3.0 | 6.0 | 1.0 | on | 400 | 0.2750 | 6.083 | 0.0041 | 0.984–1.019 | 4.02–4.33 | 0.59–0.74 | 1.66–1.73 | 1.17 | n/a | n/a | n/a | 0.7069 | 18.459 | R-screen (F) |
| 2 | 3.0 | 8.0 | 2.0 | off | 400 | 0.3750 | 4.616 | 0.0074 | 0.993–1.006 | 7.43–7.78 | 5.01–5.64 | 2.54–2.65 | 1.09 | n/a | n/a | n/a | 0.7118 | 41.410 | R-screen (F, KC) |
| 2 | 3.0 | 6.0 | 1.0 | off | 400 | 0.2125 | 4.093 | 0.0019 | 0.989–1.018 | 3.11–3.22 | 0.33–0.37 | 1.31–1.36 | 1.09 | n/a | n/a | n/a | 0.7170 | 89.525 | R-screen (F, DAN) |
| 2 | 3.0 | 8.0 | 1.0 | off | 400 | 0.2500 | 4.874 | 0.0025 | 0.998–1.024 | 3.30–3.49 | 0.40–0.45 | 1.44–1.50 | 1.14 | n/a | n/a | n/a | 0.7176 | 24.330 | R-screen (F, DAN) |
| 2 | 3.0 | 8.0 | 0.0 | on | 100 | 0.9000 | 4.466 | 0.0018 | 0.979–1.024 | 2.87–3.00 | 0.36–0.38 | 1.27–1.34 | 1.12 | n/a | n/a | n/a | 0.7187 | 69.210 | R-screen (F, DAN) |
| 2 | 4.0 | 2.0 | 2.0 | off | 25 | 5.2000 | 3.295 | 0.0075 | 0.999–1.011 | 8.44–8.85 | 5.73–6.34 | 1.47–3.40 | 1.10 | n/a | n/a | n/a | 0.7252 | 45.553 | R-screen (F, central, KC) |
| 2 | 3.0 | 6.0 | 1.0 | off | 400 | 0.2375 | 4.732 | 0.0026 | 0.992–1.025 | 3.37–3.55 | 0.38–0.40 | 1.43–1.49 | 1.12 | n/a | n/a | n/a | 0.7256 | 37.385 | R-screen (F, DAN) |
| 1 | 3.0 | 4.0 | 0.0 | off | 100 | 0.8500 | 4.937 | 0.0021 | 0.829–1.014 | 3.35–3.49 | 0.39–0.42 | 1.41–1.49 | 1.10 | n/a | n/a | n/a | 0.7355 | 92.223 | R-screen (F, DAN) |
| 2 | 3.0 | 8.0 | 0.0 | on | 100 | 1.0000 | 5.191 | 0.0030 | 0.994–1.032 | 3.20–3.44 | 0.41–0.48 | 1.43–1.53 | 1.18 | n/a | n/a | n/a | 0.7381 | 23.043 | R-screen (F, DAN) |
| 2 | 3.0 | 8.0 | 1.0 | off | 400 | 0.2125 | 4.296 | 0.0018 | 0.984–1.064 | 2.88–2.96 | 0.34–0.36 | 1.23–1.27 | 1.09 | n/a | n/a | n/a | 0.7382 | 89.436 | R-screen (F, DAN) |
| 1 | 3.0 | 1.0 | 0.0 | off | 100 | 1.5000 | 3.307 | 0.0088 | 0.996–1.009 | 10.81–11.42 | 5.69–6.47 | 2.57–2.67 | 1.12 | n/a | n/a | n/a | 0.7443 | 51.428 | R-screen (F, central, KC) |
| 2 | 3.0 | 6.0 | 0.0 | on | 100 | 0.9500 | 5.008 | 0.0024 | 0.979–1.010 | 3.27–3.46 | 0.39–0.43 | 1.42–1.50 | 1.14 | n/a | n/a | n/a | 0.7525 | 36.469 | R-screen (F, DAN) |
| 2 | 4.0 | 2.0 | 2.0 | on | 25 | 3.8000 | 2.391 | 0.0061 | 0.998–1.010 | 5.67–6.07 | 1.97–3.92 | 0.98–4.25 | 1.14 | n/a | n/a | n/a | 0.7545 | 23.918 | R-screen (KC) |
| 2 | 3.0 | 8.0 | 1.0 | off | 400 | 0.2375 | 4.874 | 0.0022 | 0.988–1.024 | 3.11–3.30 | 0.38–0.40 | 1.34–1.44 | 1.12 | n/a | n/a | n/a | 0.7654 | 35.939 | R-screen (F, DAN) |
| 2 | 4.0 | 2.0 | 0.0 | on | 25 | 4.2000 | 2.602 | 0.0060 | 0.985–1.009 | 5.44–5.89 | 3.13–3.66 | 4.13–4.34 | 1.18 | n/a | n/a | n/a | 0.7737 | 30.021 | R-screen (KC) |
| 2 | 3.0 | 8.0 | 1.0 | off | 400 | 0.2250 | 4.715 | 0.0019 | 0.984–1.015 | 2.96–3.11 | 0.36–0.38 | 1.27–1.34 | 1.11 | n/a | n/a | n/a | 0.7762 | 60.477 | R-screen (F, DAN) |
| 2 | 4.0 | 2.0 | 2.0 | on | 25 | 4.0000 | 2.391 | 0.0065 | 0.996–1.010 | 6.07–6.46 | 3.92–4.46 | 4.25–4.42 | 1.13 | n/a | n/a | n/a | 0.7930 | 34.837 | R-screen (KC) |
| 2 | 4.0 | 2.0 | 2.0 | on | 25 | 4.2000 | 2.326 | 0.0067 | 0.996–1.010 | 6.46–6.85 | 3.16–4.46 | 1.17–4.42 | 1.14 | n/a | n/a | n/a | 0.7930 | 38.144 | R-screen (KC) |
| 2 | 4.0 | 2.0 | 2.0 | off | 25 | 3.2000 | 2.966 | 0.0038 | 0.995–1.009 | 4.62–4.96 | 1.14–3.09 | 0.84–4.42 | 1.15 | n/a | n/a | n/a | 0.7941 | 14.646 | R-screen (KC) |
| 2 | 3.0 | 8.0 | 1.0 | on | 400 | 0.2125 | 4.460 | 0.0018 | 0.976–1.007 | 2.87–2.97 | 0.34–0.36 | 1.21–1.26 | 1.09 | n/a | n/a | n/a | 0.7947 | 87.810 | R-screen (F, DAN) |
| 2 | 3.0 | 6.0 | 0.0 | on | 100 | 0.9000 | 4.867 | 0.0021 | 0.979–1.016 | 3.11–3.27 | 0.36–0.39 | 1.34–1.42 | 1.11 | n/a | n/a | n/a | 0.8087 | 64.431 | R-screen (F, DAN) |
| 2 | 3.0 | 8.0 | 0.0 | on | 100 | 0.9500 | 5.191 | 0.0026 | 0.998–1.032 | 3.00–3.20 | 0.38–0.41 | 1.34–1.43 | 1.15 | n/a | n/a | n/a | 0.8149 | 36.385 | R-screen (F, DAN) |
| 2 | 4.0 | 2.0 | 0.0 | on | 25 | 5.4000 | 3.341 | 0.0092 | 0.995–1.009 | 8.17–8.60 | 4.97–5.91 | 1.37–3.91 | 1.11 | n/a | n/a | n/a | 0.8499 | 48.862 | R-screen (F, central, KC) |
| 2 | 3.0 | 8.0 | 1.0 | on | 400 | 0.2625 | 6.412 | 0.0034 | 0.984–1.023 | 3.50–3.77 | 0.46–0.58 | 1.51–1.62 | 1.17 | n/a | n/a | n/a | 0.8524 | 18.736 | R-screen (F, DAN) |
| 2 | 3.0 | 6.0 | 1.0 | on | 400 | 0.2125 | 4.642 | 0.0019 | 0.992–1.008 | 3.10–3.21 | 0.33–0.35 | 1.30–1.36 | 1.09 | n/a | n/a | n/a | 0.8642 | 87.291 | R-screen (F, DAN) |
| 2 | 4.0 | 2.0 | 1.0 | on | 25 | 4.6000 | 2.332 | 0.0075 | 0.992–1.004 | 6.58–7.03 | 4.60–5.23 | 4.57–4.77 | 1.15 | n/a | n/a | n/a | 0.8694 | 39.458 | R-screen (KC) |
| 2 | 4.0 | 2.0 | 1.0 | off | 100 | 0.9500 | 3.759 | 0.0031 | 0.994–1.006 | 3.87–4.16 | 0.63–2.06 | 0.79–3.82 | 1.17 | n/a | n/a | n/a | 0.8718 | 14.587 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 2.0 | on | 25 | 3.2000 | 3.253 | 0.0040 | 0.974–1.007 | 4.67–4.96 | 1.39–2.73 | 0.90–4.43 | 1.16 | n/a | n/a | n/a | 0.8765 | 23.924 | R-screen (F, KC) |
| 1 | 4.0 | 4.0 | 0.0 | off | 100 | 1.3500 | 5.355 | 0.0057 | 0.996–1.016 | 5.82–6.29 | 1.80–3.11 | 1.20–2.74 | 1.17 | n/a | n/a | n/a | 0.8943 | 26.872 | R-screen (F, KC) |
| 2 | 3.0 | 6.0 | 1.0 | on | 400 | 0.2625 | 7.004 | 0.0039 | 0.984–1.022 | 3.75–4.02 | 0.48–0.59 | 1.56–1.66 | 1.16 | n/a | n/a | n/a | 0.8969 | 19.359 | R-screen (F, DAN) |
| 2 | 3.0 | 6.0 | 0.0 | on | 400 | 0.3250 | 6.965 | 0.0061 | 0.999–1.029 | 4.85–5.37 | 0.92–1.19 | 2.01–2.11 | 1.21 | n/a | n/a | n/a | 0.8981 | 23.096 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 1.0 | off | 100 | 0.7500 | 3.999 | 0.0018 | 0.989–1.014 | 3.17–3.31 | 0.41–1.13 | 0.63–3.08 | 1.15 | n/a | n/a | n/a | 0.9181 | 80.012 | R-screen (F, DAN, KC) |
| 2 | 3.0 | 8.0 | 0.0 | off | 400 | 0.3000 | 7.521 | 0.0033 | 0.983–1.008 | 3.63–3.99 | 0.52–0.64 | 1.72–1.84 | 1.23 | n/a | n/a | n/a | 0.9191 | 19.146 | R-screen (F) |
| 2 | 3.0 | 6.0 | 0.0 | off | 400 | 0.2625 | 6.174 | 0.0038 | 0.992–1.023 | 3.28–3.41 | 0.41–0.44 | 1.57–1.62 | 1.10 | n/a | n/a | n/a | 0.9301 | 64.761 | R-screen (F, DAN) |
| 2 | 4.0 | 2.0 | 0.0 | off | 25 | 5.0000 | 2.071 | 0.0065 | 0.996–1.004 | 7.17–7.62 | 5.47–6.12 | 5.02–5.21 | 1.13 | n/a | n/a | n/a | 0.9574 | 40.632 | R-screen (KC) |
| 2 | 3.0 | 8.0 | 1.0 | on | 400 | 0.2250 | 5.590 | 0.0021 | 0.964–1.009 | 2.97–3.12 | 0.36–0.37 | 1.26–1.34 | 1.11 | n/a | n/a | n/a | 0.9616 | 61.985 | R-screen (F, DAN) |
| 2 | 4.0 | 2.0 | 1.0 | off | 100 | 1.1500 | 3.513 | 0.0044 | 0.992–1.006 | 5.22–5.60 | 1.57–3.31 | 1.03–4.47 | 1.16 | n/a | n/a | n/a | 0.9618 | 26.993 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 0.0 | off | 25 | 5.2000 | 2.002 | 0.0065 | 0.996–1.003 | 7.62–8.05 | 4.34–6.12 | 1.30–5.21 | 1.12 | n/a | n/a | n/a | 0.9635 | 43.422 | R-screen (central, KC) |
| 2 | 3.0 | 6.0 | 0.0 | off | 400 | 0.3000 | 8.066 | 0.0037 | 0.989–1.016 | 3.92–4.30 | 0.55–0.68 | 1.82–1.93 | 1.23 | n/a | n/a | n/a | 0.9891 | 19.875 | R-screen (F) |
| 2 | 4.0 | 2.0 | 2.0 | off | 100 | 1.2500 | 4.299 | 0.0064 | 0.999–1.009 | 7.07–7.47 | 4.44–4.81 | 2.56–3.76 | 1.12 | n/a | n/a | n/a | 0.9922 | 38.956 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 1.0 | off | 25 | 5.2000 | 2.805 | 0.0070 | 0.991–1.001 | 7.82–8.25 | 5.37–6.50 | 2.34–5.25 | 1.11 | n/a | n/a | n/a | 0.9955 | 45.074 | R-screen (central, KC) |
| 1 | 4.0 | 1.0 | 0.0 | off | 100 | 0.9000 | 4.555 | 0.0022 | 0.991–1.019 | 3.58–3.77 | 1.53–1.78 | 3.39–3.58 | 1.13 | n/a | n/a | n/a | 0.9988 | 60.347 | R-screen (F, KC) |
| 2 | 3.0 | 6.0 | 1.0 | on | 400 | 0.2250 | 5.853 | 0.0023 | 0.992–1.010 | 3.21–3.37 | 0.35–0.38 | 1.36–1.42 | 1.11 | n/a | n/a | n/a | 1.0123 | 63.757 | R-screen (F, DAN) |
| 2 | 4.0 | 2.0 | 1.0 | off | 100 | 1.1000 | 3.723 | 0.0044 | 0.990–1.006 | 4.83–5.22 | 2.90–3.31 | 4.39–4.47 | 1.17 | n/a | n/a | n/a | 1.0200 | 24.212 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 1.0 | on | 400 | 0.2125 | 4.919 | 0.0022 | 0.995–1.024 | 3.28–3.42 | 1.23–1.37 | 3.25–3.39 | 1.15 | n/a | n/a | n/a | 1.0219 | 89.097 | R-screen (F, KC) |
| 2 | 3.0 | 8.0 | 1.0 | on | 400 | 0.2500 | 6.655 | 0.0031 | 0.984–1.023 | 3.28–3.50 | 0.40–0.46 | 1.43–1.51 | 1.15 | n/a | n/a | n/a | 1.0255 | 22.795 | R-screen (F, DAN) |
| 2 | 3.0 | 6.0 | 1.0 | on | 400 | 0.2500 | 7.004 | 0.0033 | 0.993–1.022 | 3.55–3.75 | 0.42–0.48 | 1.50–1.56 | 1.14 | n/a | n/a | n/a | 1.0316 | 23.797 | R-screen (F, DAN) |
| 2 | 4.0 | 2.0 | 0.0 | on | 400 | 0.3500 | 8.368 | 0.0081 | 0.991–1.017 | 6.40–7.01 | 1.99–2.19 | 1.26–2.04 | 1.19 | n/a | n/a | n/a | 1.0443 | 35.528 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 1.0 | off | 100 | 1.2500 | 3.227 | 0.0055 | 0.994–1.004 | 6.05–6.52 | 1.92–5.05 | 1.12–5.32 | 1.16 | n/a | n/a | n/a | 1.0514 | 25.841 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 2.0 | off | 25 | 2.8000 | 2.462 | 0.0029 | 0.991–1.018 | 4.06–4.37 | 0.78–2.65 | 0.76–5.75 | 1.14 | n/a | n/a | n/a | 1.0556 | 12.935 | R-screen (KC) |
| 2 | 4.0 | 2.0 | 2.0 | off | 25 | 3.0000 | 2.462 | 0.0029 | 0.993–1.009 | 4.37–4.62 | 1.14–2.65 | 0.84–5.75 | 1.14 | n/a | n/a | n/a | 1.0556 | 22.991 | R-screen (KC) |
| 2 | 4.0 | 2.0 | 0.0 | off | 25 | 2.8000 | 3.380 | 0.0018 | 0.986–1.015 | 3.20–3.34 | 0.49–1.49 | 0.61–5.04 | 1.13 | n/a | n/a | n/a | 1.0722 | 44.545 | R-screen (F, DAN, KC) |
| 2 | 4.0 | 2.0 | 1.0 | off | 100 | 1.3500 | 4.778 | 0.0060 | 0.994–1.009 | 6.98–7.45 | 3.24–4.50 | 1.29–3.75 | 1.14 | n/a | n/a | n/a | 1.0930 | 38.868 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 1.0 | on | 100 | 1.0000 | 4.712 | 0.0036 | 0.998–1.019 | 4.18–4.48 | 0.92–2.08 | 0.89–3.82 | 1.18 | n/a | n/a | n/a | 1.0983 | 19.805 | R-screen (F, KC) |
| 2 | 3.0 | 8.0 | 1.0 | on | 400 | 0.2375 | 6.655 | 0.0027 | 0.964–1.009 | 3.12–3.28 | 0.37–0.40 | 1.34–1.43 | 1.13 | n/a | n/a | n/a | 1.1024 | 35.604 | R-screen (F, DAN) |
| 2 | 3.0 | 6.0 | 1.0 | on | 400 | 0.2375 | 6.860 | 0.0027 | 0.993–1.010 | 3.37–3.55 | 0.38–0.42 | 1.42–1.50 | 1.11 | n/a | n/a | n/a | 1.1074 | 35.957 | R-screen (F, DAN) |
| 1 | 4.0 | 2.0 | 0.0 | off | 100 | 1.3500 | 3.279 | 0.0058 | 0.994–1.005 | 6.65–7.12 | 2.62–5.12 | 1.24–5.58 | 1.15 | n/a | n/a | n/a | 1.1141 | 39.268 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 0.0 | on | 25 | 2.8000 | 4.424 | 0.0023 | 0.975–1.006 | 3.21–3.38 | 1.57–1.60 | 3.91–4.24 | 1.19 | n/a | n/a | n/a | 1.1387 | 41.848 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 0.0 | off | 400 | 0.3000 | 9.405 | 0.0038 | 0.997–1.017 | 4.15–4.58 | 0.65–0.79 | 0.93–1.00 | 1.27 | n/a | n/a | n/a | 1.1426 | 15.408 | R-screen (F) |
| 2 | 3.0 | 6.0 | 0.0 | off | 400 | 0.2875 | 9.016 | 0.0035 | 0.989–1.035 | 3.61–3.92 | 0.48–0.55 | 1.70–1.82 | 1.19 | n/a | n/a | n/a | 1.1457 | 26.700 | R-screen (F, DAN) |
| 2 | 4.0 | 2.0 | 2.0 | off | 100 | 0.8500 | 3.020 | 0.0033 | 0.992–1.012 | 4.37–4.62 | 2.31–3.15 | 3.72–6.32 | 1.14 | n/a | n/a | n/a | 1.1571 | 23.190 | R-screen (F, KC) |
| 1 | 4.0 | 2.0 | 0.0 | off | 100 | 1.2000 | 3.697 | 0.0048 | 0.997–1.011 | 5.11–5.63 | 1.11–3.98 | 0.97–5.16 | 1.22 | n/a | n/a | n/a | 1.1576 | 19.601 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 1.0 | on | 100 | 0.8500 | 3.792 | 0.0025 | 0.995–1.005 | 3.52–3.65 | 0.55–2.25 | 0.74–5.17 | 1.18 | n/a | n/a | n/a | 1.1845 | 33.089 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 2.0 | off | 25 | 3.4000 | 2.966 | 0.0039 | 0.992–1.005 | 4.96–5.31 | 3.09–4.21 | 4.42–6.69 | 1.15 | n/a | n/a | n/a | 1.2081 | 24.713 | R-screen (KC) |
| 2 | 3.0 | 8.0 | 0.0 | off | 400 | 0.2875 | 9.177 | 0.0033 | 0.974–1.008 | 3.33–3.63 | 0.45–0.52 | 1.65–1.72 | 1.20 | n/a | n/a | n/a | 1.2264 | 27.483 | R-screen (F, DAN) |
| 2 | 3.0 | 6.0 | 0.0 | off | 400 | 0.2750 | 9.016 | 0.0030 | 0.994–1.035 | 3.41–3.61 | 0.44–0.48 | 1.62–1.70 | 1.15 | n/a | n/a | n/a | 1.2305 | 44.778 | R-screen (F, DAN) |
| 2 | 4.0 | 2.0 | 0.0 | off | 25 | 3.8000 | 3.111 | 0.0040 | 0.992–1.039 | 4.58–5.02 | 2.26–4.11 | 3.73–6.69 | 1.20 | n/a | n/a | n/a | 1.2437 | 21.434 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 1.0 | on | 100 | 1.2000 | 4.156 | 0.0065 | 0.996–1.007 | 5.69–6.15 | 1.62–4.48 | 1.04–5.05 | 1.16 | n/a | n/a | n/a | 1.2527 | 25.072 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 1.0 | on | 100 | 1.2500 | 4.156 | 0.0065 | 0.991–1.003 | 6.15–6.59 | 2.33–4.48 | 1.17–5.05 | 1.17 | n/a | n/a | n/a | 1.2527 | 37.760 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 2.0 | off | 25 | 3.6000 | 2.268 | 0.0044 | 0.992–1.004 | 5.31–5.66 | 4.21–4.82 | 6.69–7.05 | 1.15 | n/a | n/a | n/a | 1.2599 | 30.234 | R-screen (KC) |
| 1 | 4.0 | 1.0 | 0.0 | off | 100 | 0.9500 | 5.928 | 0.0025 | 0.987–1.027 | 3.77–4.04 | 0.91–1.78 | 1.02–3.58 | 1.16 | n/a | n/a | n/a | 1.2622 | 36.538 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 0.0 | on | 100 | 0.8500 | 4.049 | 0.0021 | 0.990–1.018 | 3.22–3.32 | 2.01–2.25 | 4.95–5.25 | 1.14 | n/a | n/a | n/a | 1.2656 | 95.370 | R-screen (F, KC) |
| 1 | 4.0 | 3.0 | 0.0 | off | 100 | 1.1500 | 4.148 | 0.0040 | 0.987–1.009 | 4.32–4.79 | 0.71–3.20 | 0.96–5.15 | 1.23 | n/a | n/a | n/a | 1.2693 | 16.661 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 2.0 | on | 400 | 0.1750 | 3.984 | 0.0032 | 0.984–1.005 | 3.59–3.78 | 1.82–2.30 | 5.11–5.38 | 1.14 | n/a | n/a | n/a | 1.2724 | 27.194 | R-screen (F, KC) |
| 2 | 3.0 | 6.0 | 1.0 | off | 100 | 0.7000 | 6.087 | 0.0017 | 0.648–1.014 | 2.92–3.03 | 0.28–0.31 | 1.14–1.20 | 1.09 | n/a | n/a | n/a | 1.2796 | 116.904 | R-screen (F, DAN) |
| 2 | 4.0 | 2.0 | 1.0 | off | 25 | 3.0000 | 3.803 | 0.0026 | 0.992–0.998 | 3.65–3.93 | 2.09–2.35 | 5.03–5.69 | 1.18 | n/a | n/a | n/a | 1.2826 | 23.638 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 1.0 | off | 25 | 2.8000 | 3.803 | 0.0023 | 0.992–1.000 | 3.45–3.65 | 1.74–2.09 | 4.44–5.69 | 1.19 | n/a | n/a | n/a | 1.2826 | 27.024 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 2.0 | off | 100 | 1.0000 | 2.848 | 0.0043 | 0.990–1.004 | 5.24–5.55 | 3.54–4.71 | 4.34–7.27 | 1.14 | n/a | n/a | n/a | 1.2904 | 30.529 | R-screen (KC) |
| 2 | 3.0 | 8.0 | 0.0 | off | 400 | 0.2750 | 9.177 | 0.0029 | 0.974–1.032 | 3.14–3.33 | 0.42–0.45 | 1.55–1.65 | 1.16 | n/a | n/a | n/a | 1.2921 | 47.661 | R-screen (F, DAN) |
| 2 | 3.0 | 6.0 | 0.0 | on | 400 | 0.3125 | 10.946 | 0.0054 | 0.976–1.029 | 4.36–4.85 | 0.72–0.92 | 1.93–2.01 | 1.24 | n/a | n/a | n/a | 1.2977 | 19.548 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 0.0 | off | 400 | 0.3375 | 8.111 | 0.0055 | 0.994–1.020 | 5.71–6.29 | 1.55–2.37 | 1.18–2.72 | 1.21 | n/a | n/a | n/a | 1.3036 | 29.051 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 2.0 | off | 25 | 3.8000 | 2.236 | 0.0048 | 0.996–1.004 | 5.66–6.04 | 4.82–5.51 | 7.05–7.39 | 1.14 | n/a | n/a | n/a | 1.3067 | 33.335 | R-screen (KC) |
| 1 | 4.0 | 2.0 | 0.0 | off | 100 | 1.1500 | 4.606 | 0.0038 | 0.984–1.011 | 4.70–5.11 | 1.11–3.07 | 0.97–4.82 | 1.22 | n/a | n/a | n/a | 1.3074 | 23.907 | R-screen (F, KC) |
| 2 | 3.0 | 6.0 | 0.0 | on | 400 | 0.2625 | 8.742 | 0.0027 | 0.989–1.012 | 3.27–3.41 | 0.39–0.43 | 1.53–1.63 | 1.11 | n/a | n/a | n/a | 1.3111 | 62.885 | R-screen (F, DAN) |
| 1 | 4.0 | 2.0 | 0.0 | off | 100 | 0.9500 | 4.013 | 0.0022 | 0.983–1.007 | 3.48–3.62 | 0.52–2.54 | 0.76–5.56 | 1.19 | n/a | n/a | n/a | 1.3135 | 40.469 | R-screen (F, KC) |
| 1 | 4.0 | 3.0 | 0.0 | off | 100 | 1.2000 | 4.148 | 0.0046 | 0.987–1.000 | 4.79–5.24 | 3.20–3.71 | 5.15–5.40 | 1.22 | n/a | n/a | n/a | 1.3178 | 26.669 | R-screen (F, KC) |
| 2 | 3.0 | 8.0 | 0.0 | on | 400 | 0.3125 | 11.284 | 0.0053 | 0.979–1.010 | 4.04–4.49 | 0.68–0.87 | 1.83–1.94 | 1.24 | n/a | n/a | n/a | 1.3247 | 18.982 | R-screen (F) |
| 2 | 4.0 | 2.0 | 0.0 | off | 25 | 4.0000 | 3.111 | 0.0042 | 0.992–1.039 | 5.02–5.42 | 4.11–4.70 | 6.69–7.35 | 1.19 | n/a | n/a | n/a | 1.3379 | 28.331 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 0.0 | off | 25 | 4.2000 | 2.280 | 0.0046 | 0.994–1.005 | 5.42–5.84 | 4.70–5.35 | 7.35–7.66 | 1.16 | n/a | n/a | n/a | 1.3429 | 32.017 | R-screen (KC) |
| 2 | 4.0 | 2.0 | 0.0 | off | 25 | 4.4000 | 2.149 | 0.0046 | 0.990–1.007 | 5.84–6.23 | 2.29–5.35 | 1.02–7.66 | 1.17 | n/a | n/a | n/a | 1.3429 | 35.373 | R-screen (KC) |
| 2 | 4.0 | 2.0 | 1.0 | on | 25 | 4.2000 | 2.509 | 0.0060 | 0.990–1.001 | 5.72–6.17 | 3.46–5.77 | 4.13–7.66 | 1.16 | n/a | n/a | n/a | 1.3434 | 31.926 | R-screen (KC) |
| 2 | 4.0 | 2.0 | 1.0 | on | 25 | 4.4000 | 2.409 | 0.0068 | 0.995–1.004 | 6.17–6.58 | 4.60–5.77 | 4.57–7.66 | 1.14 | n/a | n/a | n/a | 1.3434 | 40.305 | R-screen (KC) |
| 2 | 4.0 | 2.0 | 0.0 | off | 25 | 3.6000 | 3.479 | 0.0032 | 0.997–1.010 | 4.24–4.58 | 2.26–3.22 | 3.73–6.62 | 1.24 | n/a | n/a | n/a | 1.3444 | 23.796 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 2.0 | on | 100 | 0.9000 | 3.337 | 0.0045 | 0.994–1.011 | 4.62–4.96 | 1.18–4.12 | 1.11–6.94 | 1.15 | n/a | n/a | n/a | 1.3507 | 16.636 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 2.0 | off | 25 | 4.0000 | 2.203 | 0.0051 | 0.996–1.004 | 6.04–6.42 | 5.51–6.21 | 7.39–7.75 | 1.13 | n/a | n/a | n/a | 1.3545 | 36.311 | R-screen (KC) |
| 2 | 4.0 | 2.0 | 2.0 | off | 25 | 4.2000 | 2.109 | 0.0051 | 0.996–1.004 | 6.42–6.78 | 3.11–6.21 | 1.15–7.75 | 1.13 | n/a | n/a | n/a | 1.3545 | 39.370 | R-screen (KC) |
| 2 | 4.0 | 2.0 | 2.0 | off | 25 | 4.8000 | 3.096 | 0.0069 | 0.992–1.005 | 7.61–8.03 | 6.28–8.32 | 5.05–7.50 | 1.11 | n/a | n/a | n/a | 1.3560 | 43.734 | R-screen (F, central, KC) |
| 1 | 4.0 | 1.0 | 0.0 | off | 100 | 1.0000 | 5.928 | 0.0031 | 0.987–1.027 | 4.04–4.39 | 0.91–2.49 | 1.02–3.96 | 1.23 | n/a | n/a | n/a | 1.3630 | 18.184 | R-screen (F, KC) |
| 1 | 4.0 | 4.0 | 0.0 | off | 100 | 1.3000 | 4.051 | 0.0049 | 0.990–1.007 | 5.41–5.82 | 1.80–4.00 | 1.20–5.81 | 1.18 | n/a | n/a | n/a | 1.3677 | 33.243 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 1.0 | off | 25 | 3.2000 | 2.677 | 0.0030 | 0.992–1.005 | 3.93–4.25 | 2.35–3.68 | 5.03–7.96 | 1.21 | n/a | n/a | n/a | 1.3814 | 21.267 | R-screen (KC) |
| 2 | 4.0 | 2.0 | 1.0 | off | 25 | 3.4000 | 2.598 | 0.0034 | 0.996–1.014 | 4.25–4.56 | 3.18–3.68 | 5.67–7.96 | 1.17 | n/a | n/a | n/a | 1.3814 | 25.027 | R-screen (KC) |
| 2 | 4.0 | 2.0 | 0.0 | on | 100 | 1.2500 | 4.426 | 0.0069 | 0.985–1.001 | 5.66–6.22 | 1.40–4.58 | 1.04–5.40 | 1.20 | n/a | n/a | n/a | 1.3821 | 25.787 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 1.0 | off | 25 | 4.4000 | 2.102 | 0.0054 | 0.997–1.005 | 6.08–6.53 | 3.96–6.49 | 4.31–8.03 | 1.14 | n/a | n/a | n/a | 1.3895 | 32.597 | R-screen (KC) |
| 2 | 4.0 | 2.0 | 1.0 | off | 25 | 4.6000 | 2.102 | 0.0058 | 0.996–1.002 | 6.53–6.95 | 5.21–6.49 | 4.77–8.03 | 1.14 | n/a | n/a | n/a | 1.3895 | 40.462 | R-screen (KC) |
| 2 | 4.0 | 2.0 | 0.0 | on | 25 | 4.4000 | 2.602 | 0.0064 | 0.994–1.010 | 5.89–6.37 | 3.66–6.11 | 4.34–8.06 | 1.17 | n/a | n/a | n/a | 1.3933 | 33.704 | R-screen (KC) |
| 1 | 4.0 | 4.0 | 0.0 | off | 100 | 1.2500 | 4.160 | 0.0049 | 0.990–1.002 | 4.96–5.41 | 3.37–4.00 | 5.37–5.81 | 1.18 | n/a | n/a | n/a | 1.3941 | 29.396 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 2.0 | off | 100 | 1.0500 | 2.976 | 0.0049 | 0.990–1.004 | 5.55–5.93 | 3.54–6.10 | 4.34–8.13 | 1.14 | n/a | n/a | n/a | 1.4027 | 29.091 | R-screen (KC) |
| 2 | 4.0 | 2.0 | 2.0 | off | 100 | 1.1000 | 2.976 | 0.0053 | 0.990–1.002 | 5.93–6.28 | 4.59–6.10 | 4.79–8.13 | 1.13 | n/a | n/a | n/a | 1.4027 | 36.808 | R-screen (KC) |
| 2 | 4.0 | 2.0 | 0.0 | off | 25 | 3.0000 | 4.083 | 0.0024 | 0.990–1.015 | 3.34–3.62 | 0.49–2.21 | 0.61–5.82 | 1.21 | n/a | n/a | n/a | 1.4046 | 21.538 | R-screen (F, DAN, KC) |
| 2 | 4.0 | 2.0 | 1.0 | off | 400 | 0.2750 | 5.692 | 0.0034 | 0.992–1.016 | 4.32–4.62 | 0.93–2.56 | 0.95–4.36 | 1.18 | n/a | n/a | n/a | 1.4197 | 20.796 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 2.0 | on | 25 | 2.8000 | 2.504 | 0.0033 | 0.995–1.014 | 4.12–4.41 | 2.41–3.56 | 5.01–8.27 | 1.17 | n/a | n/a | n/a | 1.4199 | 20.786 | R-screen (KC) |
| 1 | 4.0 | 4.0 | 0.0 | off | 100 | 1.2000 | 4.613 | 0.0043 | 0.992–1.002 | 4.54–4.96 | 3.06–3.37 | 5.37–5.40 | 1.22 | n/a | n/a | n/a | 1.4226 | 26.236 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 2.0 | on | 25 | 5.2000 | 2.929 | 0.0098 | 0.991–1.006 | 8.54–8.95 | 5.74–8.90 | 1.48–7.48 | 1.10 | n/a | n/a | n/a | 1.4317 | 56.784 | R-screen (central, KC) |
| 2 | 4.0 | 2.0 | 0.0 | on | 25 | 4.6000 | 2.400 | 0.0071 | 0.997–1.010 | 6.37–6.82 | 6.11–6.83 | 8.06–8.40 | 1.16 | n/a | n/a | n/a | 1.4354 | 42.380 | R-screen (KC) |
| 2 | 4.0 | 2.0 | 0.0 | on | 25 | 4.8000 | 2.331 | 0.0081 | 0.999–1.006 | 6.82–7.26 | 5.48–6.83 | 4.98–8.40 | 1.15 | n/a | n/a | n/a | 1.4354 | 46.126 | R-screen (KC) |
| 2 | 4.0 | 2.0 | 0.0 | off | 25 | 4.6000 | 2.047 | 0.0056 | 0.990–1.007 | 6.23–6.74 | 2.29–6.84 | 1.02–8.41 | 1.16 | n/a | n/a | n/a | 1.4361 | 25.478 | R-screen (KC) |
| 2 | 4.0 | 2.0 | 0.0 | off | 25 | 4.8000 | 2.071 | 0.0058 | 0.997–1.005 | 6.74–7.17 | 5.47–6.84 | 5.02–8.41 | 1.14 | n/a | n/a | n/a | 1.4361 | 42.316 | R-screen (KC) |
| 2 | 4.0 | 2.0 | 2.0 | off | 400 | 0.3250 | 5.191 | 0.0068 | 0.998–1.015 | 7.09–7.50 | 4.03–5.57 | 2.00–4.87 | 1.12 | n/a | n/a | n/a | 1.4391 | 41.623 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 2.0 | off | 25 | 4.4000 | 2.042 | 0.0061 | 0.996–1.004 | 6.78–7.21 | 3.11–7.69 | 1.15–8.46 | 1.13 | n/a | n/a | n/a | 1.4422 | 29.247 | R-screen (KC) |
| 2 | 4.0 | 2.0 | 2.0 | off | 25 | 4.6000 | 2.042 | 0.0064 | 0.992–1.004 | 7.21–7.61 | 6.28–7.69 | 5.05–8.46 | 1.12 | n/a | n/a | n/a | 1.4422 | 45.700 | R-screen (KC) |
| 1 | 4.0 | 1.0 | 0.0 | off | 100 | 1.2500 | 5.047 | 0.0061 | 0.994–1.013 | 6.39–6.97 | 4.72–5.29 | 4.94–5.03 | 1.18 | n/a | n/a | n/a | 1.4427 | 34.264 | R-screen (F, KC) |
| 1 | 4.0 | 1.0 | 0.0 | off | 100 | 1.3000 | 5.047 | 0.0061 | 0.992–1.007 | 6.97–7.53 | 2.91–5.29 | 1.21–5.03 | 1.17 | n/a | n/a | n/a | 1.4427 | 38.702 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 1.0 | off | 100 | 1.3000 | 4.778 | 0.0060 | 0.997–1.008 | 6.52–6.98 | 4.50–5.05 | 3.75–5.32 | 1.15 | n/a | n/a | n/a | 1.4437 | 38.230 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 2.0 | on | 25 | 4.4000 | 2.295 | 0.0078 | 0.996–1.010 | 6.85–7.29 | 3.16–7.78 | 1.17–8.51 | 1.12 | n/a | n/a | n/a | 1.4482 | 33.003 | R-screen (KC) |
| 2 | 4.0 | 2.0 | 2.0 | on | 25 | 4.6000 | 2.295 | 0.0080 | 0.998–1.006 | 7.29–7.68 | 4.11–7.78 | 1.29–8.51 | 1.12 | n/a | n/a | n/a | 1.4482 | 49.721 | R-screen (KC) |
| 2 | 4.0 | 2.0 | 2.0 | on | 100 | 0.7500 | 3.346 | 0.0034 | 0.996–1.008 | 3.95–4.16 | 2.80–3.28 | 5.51–7.67 | 1.14 | n/a | n/a | n/a | 1.4533 | 23.605 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 0.0 | on | 25 | 5.0000 | 2.922 | 0.0087 | 0.995–1.019 | 7.26–7.75 | 5.48–8.12 | 4.98–8.62 | 1.13 | n/a | n/a | n/a | 1.4614 | 44.723 | R-screen (KC) |
| 2 | 4.0 | 2.0 | 0.0 | on | 100 | 0.9000 | 4.839 | 0.0026 | 0.977–1.011 | 3.32–3.48 | 2.25–2.45 | 5.25–5.36 | 1.18 | n/a | n/a | n/a | 1.4632 | 65.250 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 2.0 | on | 100 | 0.7000 | 3.392 | 0.0030 | 0.995–1.002 | 3.71–3.95 | 1.91–3.28 | 5.39–7.67 | 1.15 | n/a | n/a | n/a | 1.4668 | 22.545 | R-screen (F, KC) |
| 1 | 4.0 | 2.0 | 0.0 | off | 100 | 0.9000 | 4.013 | 0.0022 | 0.983–1.014 | 3.25–3.48 | 0.43–2.54 | 0.69–5.56 | 1.12 | n/a | n/a | n/a | 1.4673 | 62.265 | R-screen (F, DAN, KC) |
| 2 | 4.0 | 2.0 | 2.0 | off | 25 | 5.0000 | 3.295 | 0.0075 | 0.994–1.011 | 8.03–8.44 | 6.34–8.32 | 3.40–7.50 | 1.10 | n/a | n/a | n/a | 1.4682 | 49.535 | R-screen (F, central, KC) |
| 2 | 4.0 | 2.0 | 1.0 | on | 25 | 4.8000 | 2.326 | 0.0083 | 0.992–0.999 | 7.03–7.49 | 5.23–8.07 | 4.77–8.78 | 1.13 | n/a | n/a | n/a | 1.4798 | 42.925 | R-screen (KC) |
| 2 | 4.0 | 2.0 | 1.0 | on | 25 | 5.0000 | 2.290 | 0.0083 | 0.994–1.003 | 7.49–7.90 | 4.22–8.07 | 1.28–8.78 | 1.12 | n/a | n/a | n/a | 1.4798 | 51.250 | R-screen (KC) |
| 2 | 4.0 | 2.0 | 2.0 | on | 100 | 0.9500 | 3.513 | 0.0051 | 0.996–1.008 | 4.96–5.29 | 4.12–4.83 | 6.94–7.50 | 1.14 | n/a | n/a | n/a | 1.4799 | 29.634 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 1.0 | off | 25 | 4.8000 | 2.084 | 0.0062 | 0.993–1.002 | 6.95–7.41 | 5.21–8.08 | 4.77–8.79 | 1.13 | n/a | n/a | n/a | 1.4807 | 38.879 | R-screen (KC) |
| 2 | 4.0 | 2.0 | 1.0 | off | 25 | 5.0000 | 2.005 | 0.0068 | 0.991–1.001 | 7.41–7.82 | 6.50–8.08 | 5.25–8.79 | 1.12 | n/a | n/a | n/a | 1.4807 | 47.114 | R-screen (KC) |
| 2 | 4.0 | 2.0 | 1.0 | on | 25 | 3.6000 | 2.725 | 0.0045 | 0.997–1.005 | 4.61–4.99 | 4.29–4.97 | 8.45–8.95 | 1.19 | n/a | n/a | n/a | 1.4982 | 28.195 | R-screen (KC) |
| 2 | 4.0 | 2.0 | 2.0 | off | 100 | 1.1500 | 2.997 | 0.0057 | 0.991–1.008 | 6.28–6.69 | 4.59–7.66 | 4.79–8.95 | 1.13 | n/a | n/a | n/a | 1.4987 | 35.362 | R-screen (KC) |
| 2 | 4.0 | 2.0 | 1.0 | off | 25 | 3.6000 | 2.395 | 0.0038 | 0.996–1.014 | 4.56–4.95 | 3.18–4.98 | 5.67–8.97 | 1.18 | n/a | n/a | n/a | 1.5007 | 24.188 | R-screen (KC) |
| 2 | 4.0 | 2.0 | 2.0 | on | 25 | 3.0000 | 3.253 | 0.0040 | 0.974–1.014 | 4.41–4.67 | 2.73–3.56 | 4.43–8.27 | 1.13 | n/a | n/a | n/a | 1.5009 | 26.456 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 1.0 | on | 100 | 0.8000 | 5.226 | 0.0025 | 0.957–1.004 | 3.33–3.52 | 1.68–2.25 | 4.18–5.17 | 1.11 | n/a | n/a | n/a | 1.5052 | 50.503 | R-screen (F, KC) |
| 1 | 4.0 | 4.0 | 0.0 | off | 100 | 0.8500 | 4.985 | 0.0021 | 0.975–1.016 | 2.82–2.94 | 1.10–2.05 | 3.35–5.44 | 1.11 | n/a | n/a | n/a | 1.5083 | 104.582 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 2.0 | on | 100 | 1.0000 | 3.513 | 0.0055 | 0.996–1.008 | 5.29–5.63 | 4.83–5.43 | 7.50–7.74 | 1.15 | n/a | n/a | n/a | 1.5109 | 33.290 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 2.0 | on | 100 | 1.0500 | 3.399 | 0.0061 | 0.995–1.002 | 5.63–6.00 | 5.43–6.07 | 7.74–8.04 | 1.13 | n/a | n/a | n/a | 1.5163 | 36.518 | R-screen (F, KC) |
| 1 | 4.0 | 6.0 | 0.0 | off | 100 | 1.1500 | 5.211 | 0.0041 | 0.987–1.005 | 3.80–4.22 | 0.53–2.66 | 0.94–5.34 | 1.23 | n/a | n/a | n/a | 1.5343 | 16.659 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 1.0 | off | 400 | 0.3250 | 6.621 | 0.0061 | 0.993–1.027 | 5.86–6.35 | 2.51–4.12 | 2.45–4.26 | 1.17 | n/a | n/a | n/a | 1.5480 | 28.547 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 1.0 | off | 400 | 0.3375 | 6.621 | 0.0063 | 0.998–1.027 | 6.35–6.83 | 3.04–4.12 | 2.28–4.26 | 1.16 | n/a | n/a | n/a | 1.5480 | 36.015 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 2.0 | on | 100 | 0.8000 | 4.201 | 0.0035 | 0.968–1.011 | 4.16–4.39 | 2.80–3.32 | 5.51–6.73 | 1.13 | n/a | n/a | n/a | 1.5496 | 21.239 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 2.0 | on | 100 | 0.8500 | 4.201 | 0.0040 | 0.968–1.011 | 4.39–4.62 | 1.18–3.32 | 1.11–6.73 | 1.15 | n/a | n/a | n/a | 1.5496 | 24.357 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 2.0 | on | 25 | 4.8000 | 2.119 | 0.0090 | 0.990–1.006 | 7.68–8.12 | 4.11–9.41 | 1.29–9.29 | 1.11 | n/a | n/a | n/a | 1.5506 | 39.116 | R-screen (central, KC) |
| 2 | 4.0 | 2.0 | 0.0 | on | 100 | 0.9500 | 4.839 | 0.0029 | 0.977–1.012 | 3.48–3.71 | 2.45–2.91 | 5.36–5.92 | 1.15 | n/a | n/a | n/a | 1.5633 | 37.702 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 2.0 | off | 400 | 0.2500 | 3.678 | 0.0044 | 0.988–1.012 | 4.96–5.27 | 4.50–5.18 | 7.34–7.82 | 1.15 | n/a | n/a | n/a | 1.5675 | 28.193 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 2.0 | on | 25 | 3.4000 | 2.458 | 0.0049 | 0.995–1.003 | 4.96–5.38 | 1.39–5.54 | 0.90–9.60 | 1.14 | n/a | n/a | n/a | 1.5691 | 18.223 | R-screen (KC) |
| 2 | 4.0 | 2.0 | 2.0 | on | 25 | 3.6000 | 2.458 | 0.0050 | 0.995–1.001 | 5.38–5.67 | 1.97–5.54 | 0.98–9.60 | 1.14 | n/a | n/a | n/a | 1.5691 | 35.724 | R-screen (KC) |
| 1 | 4.0 | 6.0 | 0.0 | off | 100 | 1.3500 | 4.761 | 0.0055 | 0.991–1.010 | 5.42–5.81 | 2.17–4.07 | 1.25–6.08 | 1.16 | n/a | n/a | n/a | 1.5733 | 35.136 | R-screen (F, KC) |
| 1 | 4.0 | 4.0 | 0.0 | off | 100 | 0.9000 | 4.985 | 0.0022 | 0.975–1.025 | 2.94–3.09 | 2.05–2.29 | 5.44–5.81 | 1.18 | n/a | n/a | n/a | 1.5735 | 72.938 | R-screen (F, KC) |
| 1 | 4.0 | 6.0 | 0.0 | off | 100 | 1.2000 | 5.211 | 0.0044 | 0.993–1.003 | 4.22–4.61 | 2.66–3.07 | 5.34–5.59 | 1.21 | n/a | n/a | n/a | 1.5806 | 25.417 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 0.0 | on | 25 | 3.4000 | 3.543 | 0.0036 | 0.972–1.003 | 3.92–4.29 | 2.32–3.94 | 4.83–8.26 | 1.25 | n/a | n/a | n/a | 1.5849 | 20.173 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 0.0 | on | 25 | 5.2000 | 3.341 | 0.0091 | 0.995–1.019 | 7.75–8.17 | 5.91–8.12 | 3.91–8.62 | 1.12 | n/a | n/a | n/a | 1.5899 | 52.703 | R-screen (F, central, KC) |
| 2 | 4.0 | 2.0 | 0.0 | on | 100 | 1.1500 | 6.117 | 0.0050 | 0.988–1.011 | 4.75–5.17 | 1.13–3.07 | 0.98–4.82 | 1.20 | n/a | n/a | n/a | 1.5912 | 25.168 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 2.0 | on | 25 | 5.0000 | 2.929 | 0.0096 | 0.990–1.006 | 8.12–8.54 | 8.90–9.41 | 7.48–9.29 | 1.11 | n/a | n/a | n/a | 1.6014 | 56.110 | R-screen (central, KC) |
| 2 | 4.0 | 2.0 | 1.0 | on | 25 | 3.0000 | 3.510 | 0.0027 | 0.962–1.007 | 3.72–3.90 | 1.47–3.34 | 3.17–8.49 | 1.21 | n/a | n/a | n/a | 1.6031 | 25.777 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 1.0 | on | 25 | 2.8000 | 3.510 | 0.0026 | 0.962–1.004 | 3.51–3.72 | 3.02–3.34 | 8.28–8.49 | 1.14 | n/a | n/a | n/a | 1.6031 | 30.487 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 1.0 | off | 25 | 3.8000 | 2.330 | 0.0040 | 0.994–1.008 | 4.95–5.30 | 4.98–5.76 | 8.97–9.97 | 1.18 | n/a | n/a | n/a | 1.6063 | 30.132 | R-screen (KC) |
| 2 | 4.0 | 2.0 | 1.0 | on | 25 | 3.8000 | 2.580 | 0.0050 | 0.997–1.009 | 4.99–5.36 | 4.97–5.81 | 8.95–10.01 | 1.16 | n/a | n/a | n/a | 1.6106 | 31.706 | R-screen (KC) |
| 2 | 4.0 | 2.0 | 1.0 | on | 25 | 4.0000 | 2.574 | 0.0056 | 0.990–1.009 | 5.36–5.72 | 3.46–5.81 | 4.13–10.01 | 1.16 | n/a | n/a | n/a | 1.6106 | 35.989 | R-screen (KC) |
| 1 | 4.0 | 4.0 | 0.0 | off | 100 | 1.4500 | 5.092 | 0.0066 | 0.995–1.017 | 6.77–7.19 | 3.36–5.46 | 1.43–5.90 | 1.13 | n/a | n/a | n/a | 1.6118 | 42.150 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 2.0 | on | 100 | 1.1000 | 3.528 | 0.0067 | 0.995–1.007 | 6.00–6.37 | 6.07–6.96 | 8.04–8.62 | 1.13 | n/a | n/a | n/a | 1.6233 | 40.018 | R-screen (F, KC) |
| 1 | 4.0 | 3.0 | 0.0 | off | 100 | 1.0000 | 5.614 | 0.0031 | 0.989–1.041 | 3.38–3.67 | 0.41–2.10 | 0.80–4.50 | 1.23 | n/a | n/a | n/a | 1.6257 | 20.832 | R-screen (F, DAN, KC) |
| 1 | 4.0 | 4.0 | 0.0 | off | 100 | 1.0500 | 5.241 | 0.0032 | 0.990–1.010 | 3.44–3.78 | 0.41–2.21 | 0.87–4.72 | 1.24 | n/a | n/a | n/a | 1.6263 | 16.603 | R-screen (F, DAN, KC) |
| 2 | 4.0 | 2.0 | 2.0 | off | 100 | 0.9000 | 3.059 | 0.0039 | 0.992–1.012 | 4.62–4.95 | 2.31–5.61 | 3.72–10.05 | 1.15 | n/a | n/a | n/a | 1.6339 | 21.167 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 2.0 | off | 100 | 0.9500 | 3.059 | 0.0041 | 0.995–1.006 | 4.95–5.24 | 4.71–5.61 | 7.27–10.05 | 1.13 | n/a | n/a | n/a | 1.6339 | 31.004 | R-screen (F, KC) |
| 1 | 4.0 | 6.0 | 0.0 | off | 100 | 1.5000 | 4.706 | 0.0069 | 0.997–1.006 | 6.65–7.04 | 3.86–5.79 | 1.44–6.55 | 1.12 | n/a | n/a | n/a | 1.6361 | 43.620 | R-screen (F, KC) |
| 2 | 3.0 | 8.0 | 0.0 | on | 400 | 0.3000 | 15.420 | 0.0049 | 0.984–1.005 | 3.64–4.04 | 0.54–0.68 | 1.73–1.83 | 1.24 | n/a | n/a | n/a | 1.6371 | 18.005 | R-screen (F) |
| 1 | 4.0 | 6.0 | 0.0 | off | 100 | 1.4000 | 4.864 | 0.0063 | 0.999–1.011 | 5.81–6.24 | 2.17–5.20 | 1.25–6.40 | 1.15 | n/a | n/a | n/a | 1.6469 | 28.064 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 2.0 | off | 100 | 0.7500 | 3.091 | 0.0032 | 0.981–1.007 | 3.88–4.20 | 1.44–4.78 | 3.19–10.10 | 1.14 | n/a | n/a | n/a | 1.6497 | 18.397 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 2.0 | off | 100 | 0.8000 | 3.091 | 0.0032 | 0.981–1.006 | 4.20–4.37 | 3.15–4.78 | 6.32–10.10 | 1.13 | n/a | n/a | n/a | 1.6497 | 26.007 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 1.0 | on | 400 | 0.2750 | 7.443 | 0.0043 | 0.998–1.017 | 4.34–4.67 | 0.97–2.50 | 0.96–4.21 | 1.19 | n/a | n/a | n/a | 1.6526 | 20.793 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 1.0 | off | 25 | 4.0000 | 2.235 | 0.0045 | 0.984–1.008 | 5.30–5.71 | 5.76–6.61 | 9.97–10.48 | 1.15 | n/a | n/a | n/a | 1.6561 | 33.691 | R-screen (KC) |
| 2 | 4.0 | 2.0 | 1.0 | off | 25 | 4.2000 | 2.157 | 0.0047 | 0.984–1.005 | 5.71–6.08 | 3.96–6.61 | 4.31–10.48 | 1.15 | n/a | n/a | n/a | 1.6561 | 37.139 | R-screen (KC) |
| 1 | 4.0 | 4.0 | 0.0 | off | 100 | 1.4000 | 5.355 | 0.0066 | 0.996–1.017 | 6.29–6.77 | 3.11–5.46 | 2.74–5.90 | 1.15 | n/a | n/a | n/a | 1.6620 | 33.753 | R-screen (F, KC) |
| 1 | 4.0 | 6.0 | 0.0 | off | 100 | 1.4500 | 4.864 | 0.0069 | 0.997–1.011 | 6.24–6.65 | 5.20–5.79 | 6.40–6.55 | 1.13 | n/a | n/a | n/a | 1.6692 | 40.822 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 2.0 | on | 100 | 1.1500 | 3.528 | 0.0076 | 0.994–1.007 | 6.37–6.77 | 6.96–7.82 | 8.62–9.14 | 1.13 | n/a | n/a | n/a | 1.6819 | 43.688 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 2.0 | on | 100 | 1.2500 | 3.431 | 0.0081 | 0.996–1.007 | 7.19–7.57 | 3.68–8.62 | 1.32–9.53 | 1.12 | n/a | n/a | n/a | 1.6959 | 50.991 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 0.0 | on | 25 | 3.6000 | 2.926 | 0.0042 | 0.990–1.002 | 4.29–4.73 | 3.94–5.70 | 8.26–10.93 | 1.25 | n/a | n/a | n/a | 1.6986 | 25.783 | R-screen (KC) |
| 2 | 4.0 | 2.0 | 2.0 | on | 100 | 1.2000 | 3.484 | 0.0081 | 0.994–1.003 | 6.77–7.19 | 7.82–8.62 | 9.14–9.53 | 1.12 | n/a | n/a | n/a | 1.7114 | 47.455 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 0.0 | on | 100 | 1.0000 | 5.614 | 0.0032 | 0.994–1.014 | 3.71–3.92 | 0.61–2.91 | 0.80–5.92 | 1.21 | n/a | n/a | n/a | 1.7118 | 25.373 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 1.0 | on | 100 | 1.0500 | 4.441 | 0.0049 | 0.988–1.019 | 4.48–4.89 | 0.92–4.58 | 0.89–7.53 | 1.19 | n/a | n/a | n/a | 1.7179 | 15.491 | R-screen (F, KC) |
| 1 | 4.0 | 1.0 | 0.0 | off | 100 | 1.0500 | 6.020 | 0.0037 | 0.987–1.006 | 4.39–4.86 | 2.49–3.80 | 3.96–5.57 | 1.21 | n/a | n/a | n/a | 1.7205 | 20.148 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 1.0 | on | 400 | 0.3375 | 5.946 | 0.0078 | 0.992–1.007 | 6.47–6.94 | 2.47–5.23 | 1.37–5.71 | 1.16 | n/a | n/a | n/a | 1.7333 | 41.726 | R-screen (F, KC) |
| 2 | 3.0 | 8.0 | 0.0 | on | 400 | 0.2875 | 15.420 | 0.0042 | 0.984–1.016 | 3.35–3.64 | 0.45–0.54 | 1.65–1.73 | 1.21 | n/a | n/a | n/a | 1.7354 | 25.122 | R-screen (F, DAN) |
| 2 | 4.0 | 2.0 | 2.0 | off | 400 | 0.2250 | 3.456 | 0.0036 | 0.989–1.005 | 4.41–4.70 | 3.43–5.33 | 6.55–9.88 | 1.13 | n/a | n/a | n/a | 1.7392 | 23.037 | R-screen (F, KC) |
| 1 | 4.0 | 2.0 | 0.0 | off | 100 | 1.3000 | 3.610 | 0.0058 | 0.994–1.005 | 6.17–6.65 | 5.12–7.27 | 5.58–9.53 | 1.17 | n/a | n/a | n/a | 1.7468 | 40.530 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 1.0 | on | 400 | 0.2875 | 7.151 | 0.0056 | 0.991–1.006 | 4.67–5.08 | 0.97–3.46 | 0.96–4.83 | 1.19 | n/a | n/a | n/a | 1.7496 | 16.785 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 0.0 | on | 100 | 1.3000 | 5.532 | 0.0076 | 0.992–1.024 | 6.22–6.75 | 4.58–5.60 | 5.40–6.27 | 1.17 | n/a | n/a | n/a | 1.7538 | 39.035 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 0.0 | on | 100 | 1.3500 | 5.532 | 0.0078 | 0.998–1.024 | 6.75–7.23 | 2.66–5.60 | 1.22–6.27 | 1.16 | n/a | n/a | n/a | 1.7538 | 44.337 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 0.0 | on | 25 | 3.8000 | 2.704 | 0.0051 | 0.990–1.004 | 4.73–5.15 | 5.70–6.56 | 10.93–11.60 | 1.18 | n/a | n/a | n/a | 1.7583 | 31.117 | R-screen (KC) |
| 2 | 4.0 | 2.0 | 0.0 | on | 25 | 4.0000 | 2.649 | 0.0054 | 0.985–1.007 | 5.15–5.44 | 3.13–6.56 | 4.13–11.60 | 1.17 | n/a | n/a | n/a | 1.7583 | 35.306 | R-screen (KC) |
| 1 | 4.0 | 8.0 | 0.0 | off | 100 | 1.2000 | 5.662 | 0.0045 | 0.992–1.007 | 4.00–4.37 | 2.73–3.01 | 6.13–6.18 | 1.21 | n/a | n/a | n/a | 1.7638 | 25.876 | R-screen (F, KC) |
| 2 | 3.0 | 8.0 | 0.0 | on | 400 | 0.2750 | 14.382 | 0.0036 | 0.999–1.016 | 3.15–3.35 | 0.41–0.45 | 1.55–1.65 | 1.16 | n/a | n/a | n/a | 1.7643 | 45.354 | R-screen (F, DAN) |
| 1 | 4.0 | 2.0 | 0.0 | off | 100 | 1.2500 | 3.697 | 0.0052 | 0.994–1.000 | 5.63–6.17 | 3.98–7.27 | 5.16–9.53 | 1.21 | n/a | n/a | n/a | 1.7706 | 31.561 | R-screen (F, KC) |
| 2 | 3.0 | 6.0 | 0.0 | on | 400 | 0.3000 | 17.739 | 0.0051 | 0.976–1.013 | 3.93–4.36 | 0.56–0.72 | 1.81–1.93 | 1.24 | n/a | n/a | n/a | 1.7772 | 18.399 | R-screen (F) |
| 1 | 4.0 | 8.0 | 0.0 | off | 100 | 1.5000 | 5.214 | 0.0072 | 0.989–1.011 | 6.25–6.62 | 5.34–6.01 | 6.54–6.81 | 1.12 | n/a | n/a | n/a | 1.7774 | 42.081 | R-screen (F, KC) |
| 2 | 3.0 | 6.0 | 0.0 | on | 400 | 0.2750 | 15.550 | 0.0044 | 0.989–1.012 | 3.41–3.62 | 0.43–0.47 | 1.63–1.71 | 1.16 | n/a | n/a | n/a | 1.7888 | 41.802 | R-screen (F, DAN) |
| 1 | 4.0 | 8.0 | 0.0 | off | 100 | 1.1500 | 5.662 | 0.0039 | 0.976–1.005 | 3.64–4.00 | 2.56–2.73 | 6.13–6.38 | 1.21 | n/a | n/a | n/a | 1.7953 | 23.666 | R-screen (F, KC) |
| 1 | 4.0 | 3.0 | 0.0 | off | 100 | 1.3000 | 3.616 | 0.0050 | 0.990–1.010 | 5.74–6.13 | 1.91–6.87 | 1.20–10.00 | 1.17 | n/a | n/a | n/a | 1.7965 | 39.062 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 2.0 | off | 400 | 0.2375 | 3.678 | 0.0039 | 0.989–1.004 | 4.70–4.96 | 4.50–5.33 | 7.34–9.88 | 1.13 | n/a | n/a | n/a | 1.8017 | 28.577 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 1.0 | on | 400 | 0.3000 | 7.163 | 0.0060 | 0.991–1.006 | 5.08–5.51 | 3.46–4.04 | 4.83–5.13 | 1.20 | n/a | n/a | n/a | 1.8122 | 27.551 | R-screen (F, KC) |
| 1 | 4.0 | 8.0 | 0.0 | off | 100 | 1.1000 | 5.784 | 0.0038 | 0.976–1.001 | 3.32–3.64 | 2.32–2.56 | 6.18–6.38 | 1.24 | n/a | n/a | n/a | 1.8166 | 22.449 | R-screen (F, KC) |
| 2 | 3.0 | 6.0 | 0.0 | on | 400 | 0.2875 | 17.739 | 0.0049 | 0.989–1.013 | 3.62–3.93 | 0.47–0.56 | 1.71–1.81 | 1.21 | n/a | n/a | n/a | 1.8381 | 24.866 | R-screen (F, DAN) |
| 1 | 4.0 | 3.0 | 0.0 | off | 100 | 1.2500 | 3.806 | 0.0050 | 0.990–1.010 | 5.24–5.74 | 3.71–6.87 | 5.40–10.00 | 1.18 | n/a | n/a | n/a | 1.8478 | 30.268 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 1.0 | off | 100 | 1.0500 | 3.723 | 0.0038 | 0.990–1.009 | 4.51–4.83 | 2.90–5.43 | 4.39–10.24 | 1.17 | n/a | n/a | n/a | 1.8493 | 28.296 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 2.0 | off | 100 | 0.7000 | 4.258 | 0.0025 | 0.962–1.007 | 3.75–3.88 | 1.44–3.23 | 3.19–8.99 | 1.14 | n/a | n/a | n/a | 1.8530 | 27.003 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 2.0 | off | 100 | 1.2000 | 4.299 | 0.0062 | 0.998–1.009 | 6.69–7.07 | 4.81–7.66 | 3.76–8.95 | 1.12 | n/a | n/a | n/a | 1.8584 | 43.363 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 1.0 | off | 100 | 1.0000 | 3.759 | 0.0036 | 0.994–1.009 | 4.16–4.51 | 2.06–5.43 | 3.82–10.24 | 1.18 | n/a | n/a | n/a | 1.8589 | 19.620 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 2.0 | off | 400 | 0.3000 | 3.880 | 0.0061 | 0.994–1.003 | 6.30–6.72 | 4.98–8.51 | 5.32–9.97 | 1.13 | n/a | n/a | n/a | 1.8638 | 36.556 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 1.0 | off | 100 | 0.9000 | 5.230 | 0.0026 | 0.972–1.009 | 3.70–3.87 | 0.63–3.20 | 0.79–7.40 | 1.14 | n/a | n/a | n/a | 1.8642 | 28.235 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 0.0 | off | 25 | 3.4000 | 3.662 | 0.0030 | 0.997–1.006 | 3.97–4.24 | 3.22–4.50 | 6.62–10.68 | 1.18 | n/a | n/a | n/a | 1.8748 | 27.013 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 0.0 | off | 400 | 0.2750 | 8.490 | 0.0033 | 0.982–1.013 | 3.62–3.83 | 2.37–2.37 | 4.39–4.67 | 1.16 | n/a | n/a | n/a | 1.8878 | 46.100 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 0.0 | on | 25 | 3.2000 | 3.543 | 0.0031 | 0.972–1.003 | 3.72–3.92 | 2.32–4.45 | 4.83–11.53 | 1.21 | n/a | n/a | n/a | 1.9184 | 28.685 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 1.0 | on | 100 | 1.3000 | 4.025 | 0.0081 | 0.991–1.005 | 6.59–7.14 | 2.33–8.89 | 1.17–10.17 | 1.15 | n/a | n/a | n/a | 1.9198 | 32.730 | R-screen (F, KC) |
| 1 | 4.0 | 1.0 | 0.0 | off | 100 | 1.2000 | 4.809 | 0.0058 | 0.994–1.013 | 5.84–6.39 | 4.72–6.60 | 4.94–8.54 | 1.20 | n/a | n/a | n/a | 1.9237 | 34.604 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 0.0 | off | 400 | 0.2875 | 9.405 | 0.0035 | 0.982–1.017 | 3.83–4.15 | 0.65–2.37 | 0.93–4.39 | 1.20 | n/a | n/a | n/a | 1.9292 | 27.279 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 2.0 | on | 400 | 0.2250 | 4.194 | 0.0041 | 0.994–1.005 | 4.48–4.73 | 4.66–5.35 | 8.94–9.93 | 1.15 | n/a | n/a | n/a | 1.9378 | 26.427 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 2.0 | on | 400 | 0.1875 | 3.951 | 0.0032 | 0.984–1.010 | 3.78–4.04 | 2.30–4.58 | 5.11–10.61 | 1.17 | n/a | n/a | n/a | 1.9442 | 21.789 | R-screen (F, KC) |
| 1 | 4.0 | 6.0 | 0.0 | off | 100 | 0.9500 | 7.493 | 0.0025 | 0.992–1.045 | 2.81–2.96 | 1.60–1.98 | 4.47–5.63 | 1.22 | n/a | n/a | n/a | 1.9498 | 44.276 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 0.0 | off | 25 | 3.2000 | 4.083 | 0.0027 | 0.990–1.009 | 3.62–3.97 | 2.21–4.50 | 5.82–10.68 | 1.19 | n/a | n/a | n/a | 1.9836 | 24.103 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 2.0 | off | 400 | 0.1875 | 3.499 | 0.0030 | 0.987–1.006 | 3.72–4.06 | 0.55–5.62 | 0.76–12.68 | 1.16 | n/a | n/a | n/a | 2.0008 | 14.984 | R-screen (F, KC) |
| 1 | 4.0 | 1.0 | 0.0 | off | 100 | 1.1500 | 5.326 | 0.0048 | 0.979–1.010 | 5.30–5.84 | 5.72–6.60 | 8.18–8.54 | 1.21 | n/a | n/a | n/a | 2.0257 | 29.982 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 1.0 | on | 100 | 0.9000 | 4.197 | 0.0034 | 0.991–1.005 | 3.65–4.01 | 0.55–5.18 | 0.74–10.85 | 1.16 | n/a | n/a | n/a | 2.0267 | 16.956 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 2.0 | off | 400 | 0.2125 | 3.456 | 0.0033 | 0.989–1.010 | 4.28–4.41 | 3.43–6.35 | 6.55–13.40 | 1.12 | n/a | n/a | n/a | 2.0434 | 28.530 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 1.0 | on | 100 | 1.3500 | 4.575 | 0.0086 | 0.999–1.012 | 7.14–7.57 | 3.98–8.89 | 2.28–10.17 | 1.14 | n/a | n/a | n/a | 2.0479 | 51.548 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 2.0 | off | 400 | 0.2000 | 3.499 | 0.0032 | 0.991–1.010 | 4.06–4.28 | 5.62–6.35 | 12.68–13.40 | 1.11 | n/a | n/a | n/a | 2.0559 | 28.017 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 2.0 | off | 400 | 0.2875 | 3.771 | 0.0054 | 0.994–1.004 | 5.98–6.30 | 4.98–8.92 | 5.32–12.46 | 1.13 | n/a | n/a | n/a | 2.0578 | 41.534 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 2.0 | on | 400 | 0.2375 | 4.359 | 0.0048 | 0.993–1.005 | 4.73–5.04 | 5.35–6.30 | 9.93–10.79 | 1.13 | n/a | n/a | n/a | 2.0594 | 29.882 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 1.0 | on | 25 | 3.2000 | 3.363 | 0.0038 | 0.964–1.007 | 3.90–4.36 | 1.47–6.38 | 3.17–14.07 | 1.22 | n/a | n/a | n/a | 2.0653 | 18.179 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 1.0 | on | 25 | 3.4000 | 3.363 | 0.0041 | 0.964–1.007 | 4.36–4.61 | 4.29–6.38 | 8.45–14.07 | 1.17 | n/a | n/a | n/a | 2.0653 | 31.023 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 2.0 | off | 400 | 0.2625 | 3.910 | 0.0049 | 0.988–1.012 | 5.27–5.64 | 5.18–8.14 | 7.82–12.14 | 1.15 | n/a | n/a | n/a | 2.0686 | 31.424 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 1.0 | on | 100 | 0.7500 | 5.226 | 0.0020 | 0.957–1.005 | 3.25–3.33 | 1.68–2.88 | 4.18–9.12 | 1.09 | n/a | n/a | n/a | 2.0725 | 91.323 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 2.0 | on | 400 | 0.2500 | 4.441 | 0.0055 | 0.988–1.005 | 5.04–5.30 | 3.42–6.30 | 4.58–10.79 | 1.13 | n/a | n/a | n/a | 2.0780 | 33.635 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 1.0 | off | 100 | 0.8500 | 5.597 | 0.0026 | 0.971–1.009 | 3.54–3.70 | 3.20–3.58 | 7.40–8.58 | 1.12 | n/a | n/a | n/a | 2.0797 | 38.635 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 1.0 | off | 100 | 0.8000 | 5.597 | 0.0024 | 0.971–1.014 | 3.31–3.54 | 1.13–3.58 | 3.08–8.58 | 1.14 | n/a | n/a | n/a | 2.0797 | 50.527 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 1.0 | off | 400 | 0.2125 | 4.939 | 0.0024 | 0.978–1.012 | 3.35–3.52 | 2.94–4.26 | 7.66–9.85 | 1.11 | n/a | n/a | n/a | 2.0928 | 94.384 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 2.0 | off | 400 | 0.2750 | 3.910 | 0.0052 | 0.996–1.008 | 5.64–5.98 | 8.14–8.92 | 12.14–12.46 | 1.13 | n/a | n/a | n/a | 2.0940 | 38.501 | R-screen (F, KC) |
| 1 | 4.0 | 6.0 | 0.0 | off | 100 | 1.3000 | 4.761 | 0.0055 | 0.991–1.014 | 5.04–5.42 | 4.07–5.66 | 6.08–10.25 | 1.16 | n/a | n/a | n/a | 2.0962 | 36.869 | R-screen (F, KC) |
| 1 | 4.0 | 3.0 | 0.0 | off | 100 | 0.8500 | 4.829 | 0.0021 | 0.975–1.008 | 3.04–3.05 | 0.37–2.66 | 0.70–7.52 | 1.14 | n/a | n/a | n/a | 2.1034 | 108.216 | R-screen (F, DAN, KC) |
| 1 | 4.0 | 1.0 | 0.0 | off | 100 | 1.1000 | 6.020 | 0.0043 | 0.979–1.010 | 4.86–5.30 | 3.80–5.72 | 5.57–8.18 | 1.22 | n/a | n/a | n/a | 2.1056 | 23.541 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 1.0 | off | 400 | 0.2250 | 5.101 | 0.0024 | 0.978–1.023 | 3.52–3.59 | 1.57–4.26 | 3.57–9.85 | 1.17 | n/a | n/a | n/a | 2.1251 | 72.012 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 0.0 | on | 25 | 3.0000 | 4.424 | 0.0026 | 0.975–1.006 | 3.38–3.72 | 1.57–4.45 | 3.91–11.53 | 1.17 | n/a | n/a | n/a | 2.1405 | 26.533 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 1.0 | on | 100 | 0.9500 | 4.712 | 0.0036 | 0.991–1.002 | 4.01–4.18 | 2.08–5.18 | 3.82–10.85 | 1.16 | n/a | n/a | n/a | 2.1425 | 27.200 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 0.0 | on | 100 | 1.0500 | 6.210 | 0.0042 | 0.998–1.014 | 3.92–4.35 | 0.61–4.52 | 0.80–8.26 | 1.23 | n/a | n/a | n/a | 2.1463 | 14.138 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 0.0 | on | 100 | 1.1000 | 6.210 | 0.0050 | 0.989–1.011 | 4.35–4.75 | 3.07–4.52 | 4.82–8.26 | 1.21 | n/a | n/a | n/a | 2.1463 | 25.764 | R-screen (F, KC) |
| 1 | 4.0 | 4.0 | 0.0 | off | 100 | 1.1000 | 5.271 | 0.0038 | 0.996–1.011 | 3.78–4.19 | 2.21–4.89 | 4.72–9.75 | 1.20 | n/a | n/a | n/a | 2.1478 | 21.105 | R-screen (F, KC) |
| 1 | 4.0 | 4.0 | 0.0 | off | 100 | 1.1500 | 5.271 | 0.0040 | 0.993–1.011 | 4.19–4.54 | 3.06–4.89 | 5.40–9.75 | 1.21 | n/a | n/a | n/a | 2.1478 | 28.133 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 1.0 | on | 100 | 1.1500 | 4.395 | 0.0054 | 0.997–1.010 | 5.32–5.69 | 1.62–7.47 | 1.04–11.74 | 1.16 | n/a | n/a | n/a | 2.1514 | 37.417 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 2.0 | off | 400 | 0.3125 | 5.191 | 0.0066 | 0.996–1.015 | 6.72–7.09 | 5.57–8.51 | 4.87–9.97 | 1.12 | n/a | n/a | n/a | 2.1549 | 45.025 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 1.0 | on | 100 | 1.1000 | 4.441 | 0.0053 | 0.988–1.010 | 4.89–5.32 | 4.58–7.47 | 7.53–11.74 | 1.17 | n/a | n/a | n/a | 2.1617 | 29.769 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 1.0 | off | 400 | 0.2625 | 6.839 | 0.0034 | 0.991–1.030 | 4.06–4.32 | 2.56–3.87 | 4.36–7.67 | 1.15 | n/a | n/a | n/a | 2.1676 | 25.135 | R-screen (F, KC) |
| 1 | 4.0 | 3.0 | 0.0 | off | 100 | 1.1000 | 5.310 | 0.0038 | 0.975–1.026 | 4.06–4.32 | 0.71–4.94 | 0.96–9.88 | 1.20 | n/a | n/a | n/a | 2.1686 | 26.930 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 2.0 | on | 400 | 0.2125 | 3.909 | 0.0042 | 0.996–1.008 | 4.31–4.48 | 4.66–6.39 | 8.94–13.43 | 1.12 | n/a | n/a | n/a | 2.1694 | 28.631 | R-screen (F, KC) |
| 1 | 4.0 | 6.0 | 0.0 | off | 100 | 1.2500 | 5.124 | 0.0050 | 0.993–1.014 | 4.61–5.04 | 3.07–5.66 | 5.59–10.25 | 1.20 | n/a | n/a | n/a | 2.1696 | 28.641 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 2.0 | on | 400 | 0.2000 | 3.951 | 0.0042 | 0.996–1.010 | 4.04–4.31 | 4.58–6.39 | 10.61–13.43 | 1.15 | n/a | n/a | n/a | 2.1799 | 26.113 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 1.0 | off | 400 | 0.3125 | 5.968 | 0.0049 | 0.993–1.022 | 5.46–5.86 | 2.51–6.56 | 2.45–9.11 | 1.17 | n/a | n/a | n/a | 2.2045 | 34.629 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 2.0 | on | 400 | 0.2625 | 4.602 | 0.0060 | 0.988–1.005 | 5.30–5.69 | 3.42–8.01 | 4.58–11.85 | 1.15 | n/a | n/a | n/a | 2.2074 | 29.703 | R-screen (F, KC) |
| 1 | 4.0 | 3.0 | 0.0 | off | 100 | 1.0500 | 5.614 | 0.0038 | 0.975–1.041 | 3.67–4.06 | 2.10–4.94 | 4.50–9.88 | 1.20 | n/a | n/a | n/a | 2.2244 | 20.843 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 1.0 | off | 400 | 0.2375 | 5.101 | 0.0029 | 0.988–1.023 | 3.59–3.90 | 1.57–5.50 | 3.57–11.30 | 1.14 | n/a | n/a | n/a | 2.2625 | 35.991 | R-screen (F, KC) |
| 2 | 3.0 | 8.0 | 1.0 | off | 100 | 0.7000 | 9.316 | 0.0018 | 0.268–1.014 | 2.65–2.78 | 0.30–0.32 | 1.05–1.10 | 1.15 | n/a | n/a | n/a | 2.2625 | 115.285 | R-screen (F, stability_ratio, DAN) |
| 2 | 4.0 | 2.0 | 2.0 | on | 400 | 0.2750 | 4.602 | 0.0068 | 0.995–1.009 | 5.69–6.06 | 8.01–9.13 | 11.85–12.68 | 1.13 | n/a | n/a | n/a | 2.2746 | 41.258 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 1.0 | on | 400 | 0.3250 | 6.258 | 0.0073 | 0.993–1.004 | 6.01–6.47 | 5.23–7.56 | 5.71–9.70 | 1.17 | n/a | n/a | n/a | 2.3142 | 41.982 | R-screen (F, KC) |
| 1 | 4.0 | 2.0 | 0.0 | off | 100 | 1.1000 | 5.317 | 0.0038 | 0.984–1.023 | 4.35–4.70 | 3.07–6.25 | 4.82–11.70 | 1.18 | n/a | n/a | n/a | 2.3387 | 29.121 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 2.0 | on | 400 | 0.2875 | 4.609 | 0.0073 | 0.991–1.009 | 6.06–6.43 | 9.13–10.18 | 12.68–13.37 | 1.13 | n/a | n/a | n/a | 2.3472 | 45.153 | R-screen (F, DAN, KC) |
| 2 | 4.0 | 2.0 | 2.0 | on | 400 | 0.3000 | 4.609 | 0.0080 | 0.991–1.001 | 6.43–6.81 | 8.44–10.18 | 9.80–13.37 | 1.13 | n/a | n/a | n/a | 2.3472 | 48.837 | R-screen (F, DAN, KC) |
| 1 | 4.0 | 8.0 | 0.0 | off | 100 | 1.4500 | 5.444 | 0.0069 | 0.998–1.011 | 5.87–6.25 | 5.34–6.95 | 6.54–11.58 | 1.13 | n/a | n/a | n/a | 2.3519 | 44.860 | R-screen (F, KC) |
| 1 | 4.0 | 8.0 | 0.0 | off | 100 | 1.2500 | 5.779 | 0.0050 | 0.986–1.007 | 4.37–4.76 | 3.01–5.34 | 6.18–10.93 | 1.18 | n/a | n/a | n/a | 2.3536 | 28.724 | R-screen (F, KC) |
| 1 | 4.0 | 4.0 | 0.0 | off | 100 | 0.9500 | 5.830 | 0.0030 | 0.973–1.025 | 3.09–3.33 | 2.29–4.50 | 5.81–10.96 | 1.14 | n/a | n/a | n/a | 2.3657 | 41.888 | R-screen (F, KC) |
| 1 | 4.0 | 8.0 | 0.0 | off | 100 | 1.3000 | 5.779 | 0.0053 | 0.986–1.001 | 4.76–5.13 | 5.34–5.85 | 10.93–11.11 | 1.16 | n/a | n/a | n/a | 2.3707 | 36.361 | R-screen (F, KC) |
| 2 | 3.0 | 8.0 | 0.0 | off | 400 | 0.2625 | 12.380 | 0.0035 | 0.243–1.032 | 2.93–3.14 | 0.38–0.42 | 1.44–1.55 | 1.19 | n/a | n/a | n/a | 2.4012 | 76.466 | R-screen (F, stability_ratio, DAN) |
| 2 | 4.0 | 2.0 | 1.0 | off | 400 | 0.2875 | 5.345 | 0.0045 | 0.992–1.003 | 4.62–5.07 | 0.93–8.03 | 0.95–12.50 | 1.19 | n/a | n/a | n/a | 2.4104 | 15.818 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 1.0 | off | 400 | 0.3000 | 5.345 | 0.0048 | 0.997–1.008 | 5.07–5.46 | 6.56–8.03 | 9.11–12.50 | 1.16 | n/a | n/a | n/a | 2.4104 | 34.264 | R-screen (F, KC) |
| 1 | 4.0 | 3.0 | 0.0 | off | 100 | 0.9500 | 4.956 | 0.0023 | 0.989–1.000 | 3.30–3.38 | 0.41–4.57 | 0.80–11.59 | 1.11 | n/a | n/a | n/a | 2.4479 | 47.137 | R-screen (F, DAN, KC) |
| 2 | 4.0 | 2.0 | 1.0 | on | 400 | 0.3125 | 7.163 | 0.0072 | 0.993–1.001 | 5.51–6.01 | 4.04–7.56 | 5.13–9.70 | 1.19 | n/a | n/a | n/a | 2.4493 | 32.112 | R-screen (F, KC) |
| 1 | 4.0 | 8.0 | 0.0 | off | 100 | 1.0500 | 6.494 | 0.0033 | 0.997–1.009 | 3.08–3.32 | 2.32–3.83 | 6.18–10.86 | 1.20 | n/a | n/a | n/a | 2.4639 | 27.892 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 0.0 | off | 400 | 0.3125 | 7.550 | 0.0050 | 0.994–1.007 | 4.58–5.21 | 0.79–6.88 | 1.00–9.83 | 1.25 | n/a | n/a | n/a | 2.5153 | 16.660 | R-screen (F, KC) |
| 1 | 4.0 | 6.0 | 0.0 | off | 100 | 0.9000 | 5.917 | 0.0023 | 1.000–1.018 | 2.78–2.81 | 1.98–4.11 | 5.63–12.68 | 1.11 | n/a | n/a | n/a | 2.5263 | 85.130 | R-screen (F, KC) |
| 1 | 4.0 | 8.0 | 0.0 | off | 100 | 0.8500 | 8.280 | 0.0026 | 0.958–1.022 | 2.46–2.55 | 1.89–2.75 | 6.93–9.09 | 1.12 | n/a | n/a | n/a | 2.5291 | 122.191 | R-screen (F, KC) |
| 1 | 4.0 | 8.0 | 0.0 | off | 100 | 0.9000 | 7.808 | 0.0026 | 0.977–1.022 | 2.55–2.69 | 2.75–3.05 | 9.09–9.66 | 1.16 | n/a | n/a | n/a | 2.5317 | 84.299 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 1.0 | off | 400 | 0.2500 | 6.839 | 0.0032 | 0.988–1.030 | 3.90–4.06 | 3.87–5.50 | 7.67–11.30 | 1.16 | n/a | n/a | n/a | 2.5556 | 32.516 | R-screen (F, KC) |
| 1 | 4.0 | 3.0 | 0.0 | off | 100 | 0.9000 | 4.956 | 0.0023 | 0.983–1.008 | 3.05–3.30 | 0.37–4.57 | 0.70–11.59 | 1.11 | n/a | n/a | n/a | 2.5616 | 64.930 | R-screen (F, DAN, KC) |
| 1 | 4.0 | 4.0 | 0.0 | off | 100 | 1.0000 | 5.830 | 0.0030 | 0.973–1.010 | 3.33–3.44 | 0.41–4.50 | 0.87–10.96 | 1.17 | n/a | n/a | n/a | 2.5749 | 32.856 | R-screen (F, DAN, KC) |
| 2 | 4.0 | 2.0 | 0.0 | on | 400 | 0.2625 | 9.090 | 0.0035 | 0.994–1.045 | 3.50–3.66 | 2.60–4.34 | 5.37–8.67 | 1.10 | n/a | n/a | n/a | 2.5757 | 59.253 | R-screen (F, KC) |
| 1 | 4.0 | 6.0 | 0.0 | off | 100 | 1.0000 | 7.493 | 0.0028 | 0.985–1.045 | 2.96–3.28 | 1.60–4.08 | 4.47–10.57 | 1.23 | n/a | n/a | n/a | 2.5801 | 26.621 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 0.0 | off | 400 | 0.3250 | 8.111 | 0.0055 | 0.994–1.020 | 5.21–5.71 | 2.37–6.88 | 2.72–9.83 | 1.23 | n/a | n/a | n/a | 2.5870 | 33.772 | R-screen (F, KC) |
| 1 | 4.0 | 8.0 | 0.0 | off | 100 | 1.0000 | 7.358 | 0.0030 | 0.992–1.017 | 2.85–3.08 | 3.41–3.83 | 10.24–10.86 | 1.22 | n/a | n/a | n/a | 2.5889 | 32.812 | R-screen (F, KC) |
| 1 | 4.0 | 8.0 | 0.0 | off | 100 | 0.9500 | 7.808 | 0.0027 | 0.977–1.017 | 2.69–2.85 | 3.05–3.41 | 9.66–10.24 | 1.19 | n/a | n/a | n/a | 2.5894 | 48.534 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 1.0 | on | 400 | 0.2250 | 5.974 | 0.0030 | 0.991–1.024 | 3.42–3.73 | 1.37–5.97 | 3.39–13.52 | 1.15 | n/a | n/a | n/a | 2.5995 | 63.318 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 0.0 | on | 400 | 0.2875 | 17.702 | 0.0057 | 0.986–1.047 | 3.85–4.21 | 2.61–2.92 | 4.80–4.89 | 1.25 | n/a | n/a | n/a | 2.6687 | 25.215 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 2.0 | on | 400 | 0.3125 | 4.619 | 0.0083 | 0.993–1.001 | 6.81–7.26 | 8.44–12.53 | 9.80–15.00 | 1.13 | n/a | n/a | n/a | 2.6722 | 48.742 | R-screen (F, DAN, KC) |
| 2 | 4.0 | 2.0 | 2.0 | on | 400 | 0.3250 | 4.619 | 0.0083 | 0.993–1.012 | 7.26–7.62 | 4.04–12.53 | 1.94–15.00 | 1.11 | n/a | n/a | n/a | 2.6722 | 56.484 | R-screen (F, DAN, KC) |
| 1 | 4.0 | 2.0 | 0.0 | off | 100 | 1.0000 | 5.890 | 0.0035 | 1.000–1.051 | 3.62–4.10 | 0.52–7.68 | 0.76–15.25 | 1.21 | n/a | n/a | n/a | 2.7063 | 19.204 | R-screen (F, KC) |
| 1 | 4.0 | 2.0 | 0.0 | off | 100 | 1.0500 | 5.890 | 0.0035 | 0.988–1.051 | 4.10–4.35 | 6.25–7.68 | 11.70–15.25 | 1.17 | n/a | n/a | n/a | 2.7063 | 31.163 | R-screen (F, KC) |
| 1 | 4.0 | 8.0 | 0.0 | off | 100 | 1.4000 | 5.543 | 0.0060 | 0.992–1.012 | 5.50–5.87 | 6.95–8.42 | 11.58–16.21 | 1.14 | n/a | n/a | n/a | 2.7064 | 45.799 | R-screen (F, KC) |
| 1 | 4.0 | 8.0 | 0.0 | off | 100 | 1.3500 | 5.723 | 0.0057 | 0.992–1.012 | 5.13–5.50 | 5.85–8.42 | 11.11–16.21 | 1.15 | n/a | n/a | n/a | 2.7384 | 39.293 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 0.0 | on | 400 | 0.3250 | 11.632 | 0.0072 | 0.989–1.046 | 5.23–5.86 | 3.91–6.18 | 5.39–8.12 | 1.24 | n/a | n/a | n/a | 2.7568 | 30.501 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 0.0 | on | 400 | 0.3375 | 11.632 | 0.0074 | 0.991–1.046 | 5.86–6.40 | 2.19–6.18 | 2.04–8.12 | 1.21 | n/a | n/a | n/a | 2.7568 | 39.847 | R-screen (F, KC) |
| 1 | 4.0 | 6.0 | 0.0 | off | 100 | 1.1000 | 6.518 | 0.0033 | 0.979–1.045 | 3.60–3.80 | 0.53–5.89 | 0.94–14.53 | 1.19 | n/a | n/a | n/a | 2.7591 | 29.785 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 1.0 | on | 400 | 0.2625 | 8.597 | 0.0041 | 0.995–1.043 | 4.10–4.34 | 2.50–5.53 | 4.21–11.11 | 1.14 | n/a | n/a | n/a | 2.7676 | 27.559 | R-screen (F, KC) |
| 1 | 4.0 | 6.0 | 0.0 | off | 100 | 1.0500 | 6.890 | 0.0033 | 0.979–1.045 | 3.28–3.60 | 4.08–5.89 | 10.57–14.53 | 1.20 | n/a | n/a | n/a | 2.8147 | 27.370 | R-screen (F, KC) |
| 1 | 4.0 | 2.0 | 0.0 | off | 100 | 0.8500 | 8.774 | 0.0026 | 0.342–1.014 | 3.15–3.25 | 0.43–2.65 | 0.69–7.03 | 1.16 | n/a | n/a | n/a | 2.8644 | 103.597 | R-screen (F, stability_ratio, DAN, KC) |
| 2 | 3.0 | 6.0 | 0.0 | on | 100 | 0.8500 | 11.113 | 0.0019 | 0.155–1.016 | 2.94–3.11 | 0.32–0.36 | 1.26–1.34 | 1.18 | n/a | n/a | n/a | 2.9172 | 100.583 | R-screen (F, stability_ratio, DAN) |
| 2 | 4.0 | 2.0 | 1.0 | on | 400 | 0.2500 | 10.249 | 0.0037 | 0.995–1.043 | 3.84–4.10 | 3.26–5.53 | 6.50–11.11 | 1.15 | n/a | n/a | n/a | 2.9434 | 25.925 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 0.0 | on | 400 | 0.2750 | 14.340 | 0.0038 | 0.986–1.047 | 3.66–3.85 | 2.61–4.34 | 4.80–8.67 | 1.16 | n/a | n/a | n/a | 3.0316 | 46.615 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 1.0 | on | 400 | 0.2375 | 10.249 | 0.0032 | 0.991–1.025 | 3.73–3.84 | 3.26–5.97 | 6.50–13.52 | 1.13 | n/a | n/a | n/a | 3.1393 | 44.928 | R-screen (F, KC) |
| 2 | 4.0 | 2.0 | 0.0 | on | 400 | 0.3125 | 15.016 | 0.0071 | 0.989–1.031 | 4.71–5.23 | 3.91–6.04 | 5.39–9.42 | 1.28 | n/a | n/a | n/a | 3.1606 | 29.311 | R-screen (F, KC) |
| 1 | 3.0 | 1.0 | 0.0 | off | 100 | 0.8500 | 17.860 | 0.0031 | 0.116–1.021 | 4.33–4.64 | 0.78–0.86 | 1.44–1.54 | 1.22 | n/a | n/a | n/a | 3.2426 | 67.001 | R-screen (F, stability_ratio) |
| 2 | 4.0 | 2.0 | 0.0 | on | 400 | 0.3000 | 17.702 | 0.0071 | 0.989–1.031 | 4.21–4.71 | 2.92–6.04 | 4.89–9.42 | 1.28 | n/a | n/a | n/a | 3.3252 | 20.701 | R-screen (F, KC) |
| 1 | 4.0 | 1.0 | 0.0 | off | 100 | 0.8500 | 29.621 | 0.0022 | 0.117–1.019 | 3.28–3.58 | 1.53–2.06 | 3.39–5.35 | 1.28 | n/a | n/a | n/a | 4.7269 | 91.204 | R-screen (F, stability_ratio, KC) |
| 1 | 3.0 | 8.0 | 0.0 | off | 100 | 0.8500 | 25.217 | 0.0025 | 0.031–1.017 | 2.53–2.86 | 0.31–0.36 | 1.11–1.27 | 1.45 | n/a | n/a | n/a | 5.3649 | 104.996 | R-screen (F, stability_ratio, DAN) |
| 2 | 3.0 | 8.0 | 0.0 | on | 100 | 0.8500 | 16.055 | 0.0027 | 0.019–1.024 | 2.62–2.87 | 0.32–0.36 | 1.14–1.27 | 1.26 | n/a | n/a | n/a | 5.3929 | 102.966 | R-screen (F, stability_ratio, DAN) |
| 1 | 3.0 | 3.0 | 0.0 | off | 100 | 0.8500 | 33.036 | 0.0016 | 0.015–1.020 | 3.28–3.72 | 0.41–0.48 | 1.31–1.51 | 1.48 | n/a | n/a | n/a | 6.0814 | 90.740 | R-screen (F, stability_ratio, DAN) |
| 2 | 3.0 | 8.0 | 0.0 | on | 400 | 0.2625 | 46.733 | 0.0040 | 0.023–1.009 | 2.60–3.15 | 0.35–0.41 | 1.28–1.55 | 1.91 | n/a | n/a | n/a | 6.1988 | 72.509 | R-screen (F, stability_ratio, DAN) |
| 2 | 4.0 | 2.0 | 1.0 | off | 100 | 0.7000 | 22.899 | 0.0017 | 0.012–1.010 | 2.86–3.17 | 0.41–0.85 | 0.63–2.73 | 1.41 | n/a | n/a | n/a | 6.2991 | 116.028 | R-screen (F, stability_ratio, DAN, KC) |
| 2 | 3.0 | 6.0 | 1.0 | on | 100 | 0.7000 | 27.155 | 0.0014 | 0.006–1.005 | 2.70–3.03 | 0.26–0.31 | 1.03–1.20 | 1.44 | n/a | n/a | n/a | 7.3069 | 115.107 | R-screen (F, stability_ratio, DAN) |
| 2 | 4.0 | 2.0 | 0.0 | off | 400 | 0.2625 | 68.210 | 0.0056 | 0.027–1.049 | 3.07–3.62 | 2.37–3.40 | 4.67–7.21 | 1.80 | n/a | n/a | n/a | 7.3107 | 70.217 | R-screen (F, stability_ratio, KC) |
| 1 | 3.0 | 6.0 | 0.0 | off | 100 | 0.8500 | 37.642 | 0.0015 | 0.006–1.006 | 2.64–3.11 | 0.30–0.36 | 1.12–1.35 | 1.70 | n/a | n/a | n/a | 7.4473 | 101.020 | R-screen (F, stability_ratio, DAN) |
| 1 | 4.0 | 3.0 | 0.0 | off | 100 | 0.8000 | 13.098 | 0.0021 | 0.483–2.167 | 1.96–3.04 | 2.03–2.66 | 6.33–7.52 | 305.10 | n/a | n/a | n/a | 7.5006 | 131.806 | R-screen (F, stability_ratio, KC, gradedness) |
| 1 | 4.0 | 6.0 | 0.0 | off | 100 | 0.8500 | 48.434 | 0.0022 | 0.019–1.007 | 1.80–2.78 | 1.53–4.11 | 4.77–12.68 | 2.84 | n/a | n/a | n/a | 7.9036 | 119.245 | R-screen (F, stability_ratio, KC) |
| 2 | 3.0 | 8.0 | 1.0 | on | 100 | 0.7000 | 63.360 | 0.0020 | 0.008–0.992 | 1.80–2.79 | 0.31–0.32 | 1.07–1.10 | 4.06 | n/a | n/a | n/a | 7.9455 | 121.970 | R-screen (F, stability_ratio, DAN, gradedness) |
| 2 | 4.0 | 2.0 | 1.0 | on | 100 | 0.7000 | 23.558 | 0.0020 | 0.007–1.005 | 2.65–3.25 | 0.35–2.88 | 0.52–9.12 | 1.40 | n/a | n/a | n/a | 8.2394 | 108.957 | R-screen (F, stability_ratio, DAN, KC) |
| 2 | 3.0 | 8.0 | 1.0 | on | 400 | 0.2000 | 14.534 | 0.0015 | 0.581–8.116 | 0.95–2.87 | 0.11–0.34 | 0.39–1.21 | 297.43 | n/a | n/a | n/a | 9.1168 | 129.319 | R-screen (F, stability_ratio, DAN, gradedness) |
| 2 | 3.0 | 6.0 | 0.0 | on | 100 | 0.8000 | 13.278 | 0.0019 | 0.155–38.000 | 0.98–2.94 | 0.11–0.32 | 0.40–1.26 | 311.21 | n/a | n/a | n/a | 10.5731 | 141.173 | R-screen (F, stability_ratio, DAN, gradedness) |
| 1 | 3.0 | 1.0 | 0.0 | off | 100 | 0.8000 | 49.697 | 0.0031 | 0.006–80.429 | 2.05–4.33 | 0.35–0.78 | 0.68–1.44 | 412.99 | n/a | n/a | n/a | 12.5022 | 96.114 | R-screen (F, stability_ratio, DAN, gradedness) |
| 1 | 4.0 | 6.0 | 0.0 | off | 100 | 0.8000 | 48.434 | 0.0022 | 0.019–22.875 | 0.83–1.80 | 0.08–1.53 | 0.19–4.77 | 281.30 | n/a | n/a | n/a | 13.3144 | 150.570 | R-screen (F, stability_ratio, DAN, KC, gradedness) |
| 1 | 4.0 | 1.0 | 0.0 | off | 100 | 0.8000 | 67.963 | 0.0022 | 0.001–198.667 | 0.64–3.28 | 0.49–2.06 | 1.43–5.35 | 121.61 | n/a | n/a | n/a | 14.1934 | 139.866 | R-screen (F, stability_ratio, DAN, KC, gradedness) |
| 1 | 4.0 | 4.0 | 0.0 | off | 100 | 0.8000 | 43.671 | 0.0019 | 0.002–110.800 | 0.46–2.82 | 0.05–1.10 | 0.11–3.35 | 288.29 | n/a | n/a | n/a | 15.5058 | 157.608 | R-screen (F, stability_ratio, central, DAN, KC, gradedness) |
| 2 | 4.0 | 2.0 | 1.0 | on | 400 | 0.2000 | 84.916 | 0.0020 | 0.000–29.524 | 1.19–3.28 | 0.85–1.23 | 2.71–3.25 | 301.16 | n/a | n/a | n/a | 15.7798 | 124.233 | R-screen (F, stability_ratio, KC, gradedness) |
| 2 | 3.0 | 8.0 | 1.0 | off | 400 | 0.2000 | 11.678 | 0.0014 | 0.103–30.750 | 0.00–2.88 | 0.00–0.34 | 0.00–1.23 | 296.71 | n/a | n/a | n/a | 16.5101 | 220.649 | R-screen (F, stability_ratio, central, DAN, gradedness) |
| 2 | 4.0 | 2.0 | 1.0 | off | 400 | 0.2000 | 68.987 | 0.0021 | 0.000–1.012 | 0.99–3.35 | 0.46–2.94 | 1.43–7.66 | 359.08 | n/a | n/a | n/a | 16.7002 | 128.136 | R-screen (F, stability_ratio, DAN, KC, gradedness) |
| 1 | 3.0 | 8.0 | 0.0 | off | 100 | 0.8000 | 25.217 | 0.0025 | 0.000–9.750 | 0.69–2.53 | 0.09–0.31 | 0.30–1.11 | 286.82 | n/a | n/a | n/a | 16.8947 | 148.615 | R-screen (F, stability_ratio, DAN, gradedness) |
| 2 | 3.0 | 8.0 | 0.0 | on | 100 | 0.8000 | 16.055 | 0.0027 | 0.019–17.875 | 0.00–2.62 | 0.00–0.32 | 0.00–1.14 | 287.86 | n/a | n/a | n/a | 17.3390 | 235.752 | R-screen (F, stability_ratio, central, DAN, gradedness) |
| 2 | 3.0 | 6.0 | 1.0 | on | 400 | 0.2000 | 43.818 | 0.0019 | 0.000–24.714 | 0.58–3.10 | 0.06–0.33 | 0.24–1.30 | 323.12 | n/a | n/a | n/a | 18.0951 | 145.728 | R-screen (F, stability_ratio, DAN, gradedness) |
| 1 | 3.0 | 4.0 | 0.0 | off | 100 | 0.8000 | 74.199 | 0.0021 | 0.000–8.091 | 1.45–3.35 | 0.17–0.39 | 0.59–1.41 | 348.73 | n/a | n/a | n/a | 18.1062 | 132.218 | R-screen (F, stability_ratio, DAN, gradedness) |
| 2 | 3.0 | 6.0 | 1.0 | off | 400 | 0.2000 | 62.231 | 0.0015 | 0.000–1.011 | 1.28–3.11 | 0.12–0.33 | 0.52–1.31 | 321.91 | n/a | n/a | n/a | 18.3260 | 128.234 | R-screen (F, stability_ratio, DAN, gradedness) |
| 1 | 4.0 | 8.0 | 0.0 | off | 100 | 0.8000 | 120.466 | 0.0020 | 0.001–4.143 | 0.11–2.46 | 0.13–1.89 | 0.47–6.93 | 259.49 | n/a | n/a | n/a | 18.4198 | 182.317 | R-screen (F, stability_ratio, central, DAN, KC, gradedness) |
| 1 | 3.0 | 2.0 | 0.0 | off | 100 | 0.8000 | 63.252 | 0.0015 | 0.000–95.875 | 0.64–3.94 | 0.09–0.53 | 0.23–1.45 | 388.19 | n/a | n/a | n/a | 18.7032 | 139.172 | R-screen (F, stability_ratio, DAN, gradedness) |
| 1 | 3.0 | 3.0 | 0.0 | off | 100 | 0.8000 | 33.036 | 0.0016 | 0.015–100.000 | 0.00–3.28 | 0.00–0.41 | 0.00–1.31 | 373.22 | n/a | n/a | n/a | 18.9586 | 234.197 | R-screen (F, stability_ratio, central, DAN, gradedness) |
| 1 | 3.0 | 6.0 | 0.0 | off | 100 | 0.8000 | 37.642 | 0.0015 | 0.006–19.000 | 0.00–2.64 | 0.00–0.30 | 0.00–1.12 | 311.60 | n/a | n/a | n/a | 19.4192 | 228.693 | R-screen (F, stability_ratio, central, DAN, gradedness) |
| 2 | 4.0 | 2.0 | 0.0 | on | 100 | 0.8000 | 18.379 | 0.0021 | 0.556–180.000 | 0.00–3.22 | 0.00–2.01 | 0.00–4.95 | 344.36 | n/a | n/a | n/a | 19.7852 | 224.795 | R-screen (F, stability_ratio, central, DAN, KC, gradedness) |
| 2 | 3.0 | 6.0 | 0.0 | off | 400 | 0.2500 | 5.199 | 0.0038 | n/a–n/a | 0.00–3.28 | 0.00–0.41 | 0.00–1.57 | 342.33 | n/a | n/a | n/a | 23.1111 | 235.752 | R-screen (F, stability_ratio, central, DAN, gradedness) |
| 2 | 3.0 | 8.0 | 0.0 | on | 100 | 0.7500 | 6.753 | 0.0002 | n/a–n/a | 0.00–0.00 | 0.00–0.00 | 0.00–0.00 | 276.40 | n/a | n/a | n/a | 23.1587 | 235.752 | R-screen (F, stability_ratio, central, DAN, gradedness) |
| 2 | 3.0 | 6.0 | 0.0 | on | 400 | 0.2500 | 5.575 | 0.0022 | n/a–n/a | 0.00–3.27 | 0.00–0.39 | 0.00–1.53 | 342.19 | n/a | n/a | n/a | 23.1806 | 235.752 | R-screen (F, stability_ratio, central, DAN, gradedness) |
| 1 | 4.0 | 6.0 | 0.0 | off | 100 | 0.7500 | 8.094 | 0.0009 | n/a–n/a | 0.00–0.83 | 0.00–0.08 | 0.00–0.19 | 273.84 | n/a | n/a | n/a | 23.3305 | 235.752 | R-screen (F, stability_ratio, central, DAN, gradedness) |
| 1 | 3.0 | 6.0 | 0.0 | off | 100 | 0.7500 | 9.574 | 0.0003 | n/a–n/a | 0.00–0.00 | 0.00–0.00 | 0.00–0.00 | 302.58 | n/a | n/a | n/a | 23.5982 | 235.752 | R-screen (F, stability_ratio, central, DAN, gradedness) |
| 2 | 3.0 | 8.0 | 1.0 | off | 400 | 0.1875 | 11.678 | 0.0003 | n/a–n/a | 0.00–0.00 | 0.00–0.00 | 0.00–0.00 | 289.10 | n/a | n/a | n/a | 23.7513 | 235.752 | R-screen (F, stability_ratio, central, DAN, gradedness) |
| 2 | 3.0 | 8.0 | 0.0 | off | 400 | 0.2500 | 12.380 | 0.0035 | n/a–n/a | 0.00–2.93 | 0.00–0.38 | 0.00–1.44 | 314.59 | n/a | n/a | n/a | 23.8942 | 235.752 | R-screen (F, stability_ratio, central, DAN, gradedness) |
| 1 | 4.0 | 2.0 | 0.0 | off | 100 | 0.7500 | 12.076 | 0.0003 | n/a–n/a | 0.00–0.00 | 0.00–0.00 | 0.00–0.00 | 329.65 | n/a | n/a | n/a | 23.9160 | 235.752 | R-screen (F, stability_ratio, central, DAN, gradedness) |
| 2 | 3.0 | 6.0 | 0.0 | on | 100 | 0.7500 | 13.278 | 0.0019 | n/a–n/a | 0.00–0.98 | 0.00–0.11 | 0.00–0.40 | 303.19 | n/a | n/a | n/a | 23.9273 | 235.752 | R-screen (F, stability_ratio, central, DAN, gradedness) |
| 2 | 3.0 | 8.0 | 1.0 | on | 400 | 0.1875 | 14.534 | 0.0013 | n/a–n/a | 0.00–0.95 | 0.00–0.11 | 0.00–0.39 | 288.42 | n/a | n/a | n/a | 23.9677 | 235.752 | R-screen (F, stability_ratio, central, DAN, gradedness) |
| 1 | 3.0 | 3.0 | 0.0 | off | 100 | 0.7500 | 13.201 | 0.0003 | n/a–n/a | 0.00–0.00 | 0.00–0.00 | 0.00–0.00 | 361.86 | n/a | n/a | n/a | 24.0983 | 235.752 | R-screen (F, stability_ratio, central, DAN, gradedness) |
| 2 | 4.0 | 2.0 | 0.0 | on | 100 | 0.7500 | 18.379 | 0.0004 | n/a–n/a | 0.00–0.00 | 0.00–0.00 | 0.00–0.00 | 334.96 | n/a | n/a | n/a | 24.3520 | 235.752 | R-screen (F, stability_ratio, central, DAN, gradedness) |
| 1 | 3.0 | 8.0 | 0.0 | off | 100 | 0.7500 | 25.176 | 0.0024 | n/a–n/a | 0.00–0.69 | 0.00–0.09 | 0.00–0.30 | 277.35 | n/a | n/a | n/a | 24.4780 | 235.752 | R-screen (F, stability_ratio, central, DAN, gradedness) |
| 2 | 4.0 | 2.0 | 0.0 | on | 400 | 0.2500 | 7.782 | 0.0030 | n/a–n/a | 0.00–3.50 | 0.00–2.60 | 0.00–5.37 | 369.17 | n/a | n/a | n/a | 24.5775 | 235.752 | R-screen (F, stability_ratio, central, DAN, KC, gradedness) |
| 1 | 4.0 | 4.0 | 0.0 | off | 100 | 0.7500 | 43.671 | 0.0011 | n/a–n/a | 0.00–0.46 | 0.00–0.05 | 0.00–0.11 | 289.13 | n/a | n/a | n/a | 25.0704 | 235.752 | R-screen (F, stability_ratio, central, DAN, gradedness) |
| 1 | 4.0 | 3.0 | 0.0 | off | 100 | 0.7500 | 13.098 | 0.0020 | n/a–n/a | 0.00–1.96 | 0.00–2.03 | 0.00–6.33 | 313.09 | n/a | n/a | n/a | 25.0974 | 235.752 | R-screen (F, stability_ratio, central, DAN, KC, gradedness) |
| 2 | 3.0 | 6.0 | 1.0 | on | 400 | 0.1875 | 43.818 | 0.0013 | n/a–n/a | 0.00–0.58 | 0.00–0.06 | 0.00–0.24 | 311.14 | n/a | n/a | n/a | 25.1471 | 235.752 | R-screen (F, stability_ratio, central, DAN, gradedness) |
| 1 | 4.0 | 2.0 | 0.0 | off | 100 | 0.8000 | 12.076 | 0.0026 | 0.000–14.000 | 0.00–3.15 | 0.00–2.65 | 0.00–7.03 | 324.87 | n/a | n/a | n/a | 25.1580 | 233.031 | R-screen (F, stability_ratio, central, DAN, KC, gradedness) |
| 2 | 3.0 | 8.0 | 0.0 | on | 400 | 0.2500 | 46.733 | 0.0040 | n/a–n/a | 0.00–2.60 | 0.00–0.35 | 0.00–1.28 | 314.99 | n/a | n/a | n/a | 25.2238 | 235.752 | R-screen (F, stability_ratio, central, DAN, gradedness) |
| 2 | 3.0 | 6.0 | 1.0 | off | 400 | 0.1875 | 62.231 | 0.0015 | n/a–n/a | 0.00–1.28 | 0.00–0.12 | 0.00–0.52 | 311.70 | n/a | n/a | n/a | 25.4997 | 235.752 | R-screen (F, stability_ratio, central, DAN, gradedness) |
| 1 | 3.0 | 1.0 | 0.0 | off | 100 | 0.7500 | 49.697 | 0.0030 | n/a–n/a | 0.00–2.05 | 0.00–0.35 | 0.00–0.68 | 451.17 | n/a | n/a | n/a | 25.6446 | 235.752 | R-screen (F, stability_ratio, central, DAN, gradedness) |
| 1 | 4.0 | 1.0 | 0.0 | off | 100 | 0.7500 | 67.963 | 0.0017 | n/a–n/a | 0.00–0.64 | 0.00–0.49 | 0.00–1.43 | 347.81 | n/a | n/a | n/a | 25.6974 | 235.752 | R-screen (F, stability_ratio, central, DAN, gradedness) |
| 2 | 4.0 | 2.0 | 1.0 | off | 400 | 0.1875 | 68.987 | 0.0018 | n/a–n/a | 0.00–0.99 | 0.00–0.46 | 0.00–1.43 | 346.68 | n/a | n/a | n/a | 25.7091 | 235.752 | R-screen (F, stability_ratio, central, DAN, gradedness) |
| 1 | 3.0 | 2.0 | 0.0 | off | 100 | 0.7500 | 63.252 | 0.0015 | n/a–n/a | 0.00–0.64 | 0.00–0.09 | 0.00–0.23 | 394.56 | n/a | n/a | n/a | 25.7517 | 235.752 | R-screen (F, stability_ratio, central, DAN, gradedness) |
| 1 | 3.0 | 4.0 | 0.0 | off | 100 | 0.7500 | 74.199 | 0.0013 | n/a–n/a | 0.00–1.45 | 0.00–0.17 | 0.00–0.59 | 338.52 | n/a | n/a | n/a | 25.7582 | 235.752 | R-screen (F, stability_ratio, central, DAN, gradedness) |
| 1 | 4.0 | 8.0 | 0.0 | off | 100 | 0.7500 | 120.466 | 0.0019 | n/a–n/a | 0.00–0.11 | 0.00–0.13 | 0.00–0.47 | 251.44 | n/a | n/a | n/a | 25.9454 | 235.752 | R-screen (F, stability_ratio, central, DAN, gradedness) |
| 2 | 4.0 | 2.0 | 1.0 | on | 400 | 0.1875 | 84.916 | 0.0018 | n/a–n/a | 0.00–1.19 | 0.00–0.85 | 0.00–2.71 | 331.48 | n/a | n/a | n/a | 26.1744 | 235.752 | R-screen (F, stability_ratio, central, DAN, KC, gradedness) |
| 2 | 4.0 | 2.0 | 0.0 | off | 400 | 0.2500 | 68.210 | 0.0056 | n/a–n/a | 0.00–3.07 | 0.00–3.40 | 0.00–7.21 | 367.84 | n/a | n/a | n/a | 27.0396 | 235.752 | R-screen (F, stability_ratio, central, DAN, KC, gradedness) |
| 1 | 4.0 | 2.0 | 0.0 | off | 100 | 0.7000 | n/a | 0.0000 | n/a–n/a | 0.00–0.00 | 0.00–0.00 | 0.00–0.00 | 1.00 | n/a | n/a | n/a | 27.8240 | 235.752 | R-screen (F, stability_ratio, central, DAN, gradedness) |
| 2 | 4.0 | 2.0 | 0.0 | off | 400 | 0.1750 | n/a | 0.0000 | n/a–n/a | 0.00–0.00 | 0.00–0.00 | 0.00–0.00 | 1.00 | n/a | n/a | n/a | 27.8240 | 235.752 | R-screen (F, stability_ratio, central, DAN, gradedness) |
| 2 | 4.0 | 2.0 | 0.0 | off | 400 | 0.1875 | n/a | 0.0000 | n/a–n/a | 0.00–0.00 | 0.00–0.00 | 0.00–0.00 | 1.00 | n/a | n/a | n/a | 27.8240 | 235.752 | R-screen (F, stability_ratio, central, DAN, gradedness) |
| 2 | 4.0 | 2.0 | 0.0 | off | 400 | 0.2000 | n/a | 0.0000 | n/a–n/a | 0.00–0.00 | 0.00–0.00 | 0.00–0.00 | 1.00 | n/a | n/a | n/a | 27.8240 | 235.752 | R-screen (F, stability_ratio, central, DAN, gradedness) |
| 2 | 4.0 | 2.0 | 0.0 | off | 400 | 0.2125 | n/a | 0.0000 | n/a–n/a | 0.00–0.00 | 0.00–0.00 | 0.00–0.00 | 1.00 | n/a | n/a | n/a | 27.8240 | 235.752 | R-screen (F, stability_ratio, central, DAN, gradedness) |
| 2 | 4.0 | 2.0 | 0.0 | off | 400 | 0.2250 | n/a | 0.0000 | n/a–n/a | 0.00–0.00 | 0.00–0.00 | 0.00–0.00 | 1.00 | n/a | n/a | n/a | 27.8240 | 235.752 | R-screen (F, stability_ratio, central, DAN, gradedness) |
| 2 | 4.0 | 2.0 | 0.0 | on | 100 | 0.7000 | n/a | 0.0000 | n/a–n/a | 0.00–0.00 | 0.00–0.00 | 0.00–0.00 | 1.00 | n/a | n/a | n/a | 27.8240 | 235.752 | R-screen (F, stability_ratio, central, DAN, gradedness) |
| 2 | 4.0 | 2.0 | 0.0 | on | 400 | 0.1750 | n/a | 0.0000 | n/a–n/a | 0.00–0.00 | 0.00–0.00 | 0.00–0.00 | 1.00 | n/a | n/a | n/a | 27.8240 | 235.752 | R-screen (F, stability_ratio, central, DAN, gradedness) |
| 2 | 4.0 | 2.0 | 0.0 | on | 400 | 0.1875 | n/a | 0.0000 | n/a–n/a | 0.00–0.00 | 0.00–0.00 | 0.00–0.00 | 1.00 | n/a | n/a | n/a | 27.8240 | 235.752 | R-screen (F, stability_ratio, central, DAN, gradedness) |
| 2 | 4.0 | 2.0 | 0.0 | on | 400 | 0.2000 | n/a | 0.0000 | n/a–n/a | 0.00–0.00 | 0.00–0.00 | 0.00–0.00 | 1.00 | n/a | n/a | n/a | 27.8240 | 235.752 | R-screen (F, stability_ratio, central, DAN, gradedness) |
| 2 | 4.0 | 2.0 | 0.0 | on | 400 | 0.2125 | n/a | 0.0000 | n/a–n/a | 0.00–0.00 | 0.00–0.00 | 0.00–0.00 | 1.00 | n/a | n/a | n/a | 27.8240 | 235.752 | R-screen (F, stability_ratio, central, DAN, gradedness) |
| 2 | 4.0 | 2.0 | 0.0 | on | 400 | 0.2250 | n/a | 0.0000 | n/a–n/a | 0.00–0.00 | 0.00–0.00 | 0.00–0.00 | 1.00 | n/a | n/a | n/a | 27.8240 | 235.752 | R-screen (F, stability_ratio, central, DAN, gradedness) |
| 1 | 3.0 | 3.0 | 0.0 | off | 100 | 0.7000 | n/a | 0.0000 | n/a–n/a | 0.00–0.00 | 0.00–0.00 | 0.00–0.00 | 1.00 | n/a | n/a | n/a | 27.8240 | 235.752 | R-screen (F, stability_ratio, central, DAN, gradedness) |
| 1 | 3.0 | 6.0 | 0.0 | off | 100 | 0.7000 | n/a | 0.0000 | n/a–n/a | 0.00–0.00 | 0.00–0.00 | 0.00–0.00 | 1.00 | n/a | n/a | n/a | 27.8240 | 235.752 | R-screen (F, stability_ratio, central, DAN, gradedness) |
| 2 | 3.0 | 6.0 | 0.0 | off | 400 | 0.1750 | n/a | 0.0000 | n/a–n/a | 0.00–0.00 | 0.00–0.00 | 0.00–0.00 | 1.00 | n/a | n/a | n/a | 27.8240 | 235.752 | R-screen (F, stability_ratio, central, DAN, gradedness) |
| 2 | 3.0 | 6.0 | 0.0 | off | 400 | 0.1875 | n/a | 0.0000 | n/a–n/a | 0.00–0.00 | 0.00–0.00 | 0.00–0.00 | 1.00 | n/a | n/a | n/a | 27.8240 | 235.752 | R-screen (F, stability_ratio, central, DAN, gradedness) |
| 2 | 3.0 | 6.0 | 0.0 | off | 400 | 0.2000 | n/a | 0.0000 | n/a–n/a | 0.00–0.00 | 0.00–0.00 | 0.00–0.00 | 1.00 | n/a | n/a | n/a | 27.8240 | 235.752 | R-screen (F, stability_ratio, central, DAN, gradedness) |
| 2 | 3.0 | 6.0 | 0.0 | off | 400 | 0.2125 | n/a | 0.0000 | n/a–n/a | 0.00–0.00 | 0.00–0.00 | 0.00–0.00 | 1.00 | n/a | n/a | n/a | 27.8240 | 235.752 | R-screen (F, stability_ratio, central, DAN, gradedness) |
| 2 | 3.0 | 6.0 | 0.0 | off | 400 | 0.2250 | n/a | 0.0000 | n/a–n/a | 0.00–0.00 | 0.00–0.00 | 0.00–0.00 | 1.00 | n/a | n/a | n/a | 27.8240 | 235.752 | R-screen (F, stability_ratio, central, DAN, gradedness) |
| 2 | 3.0 | 6.0 | 0.0 | on | 400 | 0.1750 | n/a | 0.0000 | n/a–n/a | 0.00–0.00 | 0.00–0.00 | 0.00–0.00 | 1.00 | n/a | n/a | n/a | 27.8240 | 235.752 | R-screen (F, stability_ratio, central, DAN, gradedness) |
| 2 | 3.0 | 6.0 | 0.0 | on | 400 | 0.1875 | n/a | 0.0000 | n/a–n/a | 0.00–0.00 | 0.00–0.00 | 0.00–0.00 | 1.00 | n/a | n/a | n/a | 27.8240 | 235.752 | R-screen (F, stability_ratio, central, DAN, gradedness) |
| 2 | 3.0 | 6.0 | 0.0 | on | 400 | 0.2000 | n/a | 0.0000 | n/a–n/a | 0.00–0.00 | 0.00–0.00 | 0.00–0.00 | 1.00 | n/a | n/a | n/a | 27.8240 | 235.752 | R-screen (F, stability_ratio, central, DAN, gradedness) |
| 2 | 3.0 | 6.0 | 0.0 | on | 400 | 0.2125 | n/a | 0.0000 | n/a–n/a | 0.00–0.00 | 0.00–0.00 | 0.00–0.00 | 1.00 | n/a | n/a | n/a | 27.8240 | 235.752 | R-screen (F, stability_ratio, central, DAN, gradedness) |
| 2 | 3.0 | 6.0 | 0.0 | on | 400 | 0.2250 | n/a | 0.0000 | n/a–n/a | 0.00–0.00 | 0.00–0.00 | 0.00–0.00 | 1.00 | n/a | n/a | n/a | 27.8240 | 235.752 | R-screen (F, stability_ratio, central, DAN, gradedness) |
| 2 | 3.0 | 8.0 | 0.0 | off | 400 | 0.1750 | n/a | 0.0000 | n/a–n/a | 0.00–0.00 | 0.00–0.00 | 0.00–0.00 | 1.00 | n/a | n/a | n/a | 27.8240 | 235.752 | R-screen (F, stability_ratio, central, DAN, gradedness) |
| 2 | 3.0 | 8.0 | 0.0 | off | 400 | 0.1875 | n/a | 0.0000 | n/a–n/a | 0.00–0.00 | 0.00–0.00 | 0.00–0.00 | 1.00 | n/a | n/a | n/a | 27.8240 | 235.752 | R-screen (F, stability_ratio, central, DAN, gradedness) |
| 2 | 3.0 | 8.0 | 0.0 | off | 400 | 0.2000 | n/a | 0.0000 | n/a–n/a | 0.00–0.00 | 0.00–0.00 | 0.00–0.00 | 1.00 | n/a | n/a | n/a | 27.8240 | 235.752 | R-screen (F, stability_ratio, central, DAN, gradedness) |
| 2 | 3.0 | 8.0 | 0.0 | off | 400 | 0.2125 | n/a | 0.0000 | n/a–n/a | 0.00–0.00 | 0.00–0.00 | 0.00–0.00 | 1.00 | n/a | n/a | n/a | 27.8240 | 235.752 | R-screen (F, stability_ratio, central, DAN, gradedness) |
| 2 | 3.0 | 8.0 | 0.0 | off | 400 | 0.2250 | n/a | 0.0000 | n/a–n/a | 0.00–0.00 | 0.00–0.00 | 0.00–0.00 | 1.00 | n/a | n/a | n/a | 27.8240 | 235.752 | R-screen (F, stability_ratio, central, DAN, gradedness) |
| 2 | 3.0 | 8.0 | 0.0 | on | 100 | 0.7000 | n/a | 0.0000 | n/a–n/a | 0.00–0.00 | 0.00–0.00 | 0.00–0.00 | 1.00 | n/a | n/a | n/a | 27.8240 | 235.752 | R-screen (F, stability_ratio, central, DAN, gradedness) |
| 2 | 3.0 | 8.0 | 0.0 | on | 400 | 0.1750 | n/a | 0.0000 | n/a–n/a | 0.00–0.00 | 0.00–0.00 | 0.00–0.00 | 1.00 | n/a | n/a | n/a | 27.8240 | 235.752 | R-screen (F, stability_ratio, central, DAN, gradedness) |
| 2 | 3.0 | 8.0 | 0.0 | on | 400 | 0.1875 | n/a | 0.0000 | n/a–n/a | 0.00–0.00 | 0.00–0.00 | 0.00–0.00 | 1.00 | n/a | n/a | n/a | 27.8240 | 235.752 | R-screen (F, stability_ratio, central, DAN, gradedness) |
| 2 | 3.0 | 8.0 | 0.0 | on | 400 | 0.2000 | n/a | 0.0000 | n/a–n/a | 0.00–0.00 | 0.00–0.00 | 0.00–0.00 | 1.00 | n/a | n/a | n/a | 27.8240 | 235.752 | R-screen (F, stability_ratio, central, DAN, gradedness) |
| 2 | 3.0 | 8.0 | 0.0 | on | 400 | 0.2125 | n/a | 0.0000 | n/a–n/a | 0.00–0.00 | 0.00–0.00 | 0.00–0.00 | 1.00 | n/a | n/a | n/a | 27.8240 | 235.752 | R-screen (F, stability_ratio, central, DAN, gradedness) |
| 2 | 3.0 | 8.0 | 0.0 | on | 400 | 0.2250 | n/a | 0.0000 | n/a–n/a | 0.00–0.00 | 0.00–0.00 | 0.00–0.00 | 1.00 | n/a | n/a | n/a | 27.8240 | 235.752 | R-screen (F, stability_ratio, central, DAN, gradedness) |
| 2 | 3.0 | 8.0 | 1.0 | off | 400 | 0.1750 | n/a | 0.0000 | n/a–n/a | 0.00–0.00 | 0.00–0.00 | 0.00–0.00 | 1.00 | n/a | n/a | n/a | 27.8240 | 235.752 | R-screen (F, stability_ratio, central, DAN, gradedness) |
| 1 | 4.0 | 8.0 | 0.0 | off | 100 | 0.7000 | n/a | 0.0000 | n/a–n/a | 0.00–0.00 | 0.00–0.00 | 0.00–0.00 | 32.48 | n/a | n/a | n/a | 30.2059 | 235.752 | R-screen (F, stability_ratio, central, DAN, gradedness) |
| 1 | 4.0 | 4.0 | 0.0 | off | 100 | 0.7000 | n/a | 0.0000 | n/a–n/a | 0.00–0.00 | 0.00–0.00 | 0.00–0.00 | 137.37 | n/a | n/a | n/a | 31.6481 | 235.752 | R-screen (F, stability_ratio, central, DAN, gradedness) |
| 2 | 4.0 | 2.0 | 1.0 | off | 400 | 0.1750 | n/a | 0.0000 | n/a–n/a | 0.00–0.00 | 0.00–0.00 | 0.00–0.00 | 166.22 | n/a | n/a | n/a | 31.8388 | 235.752 | R-screen (F, stability_ratio, central, DAN, gradedness) |
| 2 | 3.0 | 6.0 | 1.0 | on | 400 | 0.1750 | n/a | 0.0000 | n/a–n/a | 0.00–0.00 | 0.00–0.00 | 0.00–0.00 | 173.47 | n/a | n/a | n/a | 31.8815 | 235.752 | R-screen (F, stability_ratio, central, DAN, gradedness) |
| 1 | 4.0 | 1.0 | 0.0 | off | 100 | 0.7000 | n/a | 0.0000 | n/a–n/a | 0.00–0.00 | 0.00–0.00 | 0.00–0.00 | 185.15 | n/a | n/a | n/a | 31.9466 | 235.752 | R-screen (F, stability_ratio, central, DAN, gradedness) |
| 1 | 3.0 | 2.0 | 0.0 | off | 100 | 0.7000 | n/a | 0.0000 | n/a–n/a | 0.00–0.00 | 0.00–0.00 | 0.00–0.00 | 191.08 | n/a | n/a | n/a | 31.9781 | 235.752 | R-screen (F, stability_ratio, central, DAN, gradedness) |
| 1 | 3.0 | 8.0 | 0.0 | off | 100 | 0.7000 | n/a | 0.0000 | n/a–n/a | 0.00–0.00 | 0.00–0.00 | 0.00–0.00 | 205.22 | n/a | n/a | n/a | 32.0495 | 235.752 | R-screen (F, stability_ratio, central, DAN, gradedness) |
| 1 | 4.0 | 6.0 | 0.0 | off | 100 | 0.7000 | n/a | 0.0000 | n/a–n/a | 0.00–0.00 | 0.00–0.00 | 0.00–0.00 | 247.24 | n/a | n/a | n/a | 32.2358 | 235.752 | R-screen (F, stability_ratio, central, DAN, gradedness) |
| 2 | 3.0 | 6.0 | 1.0 | off | 400 | 0.1750 | n/a | 0.0000 | n/a–n/a | 0.00–0.00 | 0.00–0.00 | 0.00–0.00 | 267.15 | n/a | n/a | n/a | 32.3132 | 235.752 | R-screen (F, stability_ratio, central, DAN, gradedness) |
| 2 | 3.0 | 8.0 | 1.0 | on | 400 | 0.1750 | n/a | 0.0000 | n/a–n/a | 0.00–0.00 | 0.00–0.00 | 0.00–0.00 | 281.97 | n/a | n/a | n/a | 32.3672 | 235.752 | R-screen (F, stability_ratio, central, DAN, gradedness) |
| 2 | 3.0 | 6.0 | 0.0 | on | 100 | 0.7000 | n/a | 0.0000 | n/a–n/a | 0.00–0.00 | 0.00–0.00 | 0.00–0.00 | 292.76 | n/a | n/a | n/a | 32.4048 | 235.752 | R-screen (F, stability_ratio, central, DAN, gradedness) |
| 1 | 4.0 | 3.0 | 0.0 | off | 100 | 0.7000 | n/a | 0.0000 | n/a–n/a | 0.00–0.00 | 0.00–0.00 | 0.00–0.00 | 297.29 | n/a | n/a | n/a | 32.4202 | 235.752 | R-screen (F, stability_ratio, central, DAN, gradedness) |
| 2 | 3.0 | 8.0 | 0.0 | on | 400 | 0.2375 | n/a | 0.0000 | n/a–n/a | 0.00–0.00 | 0.00–0.00 | 0.00–0.00 | 301.69 | n/a | n/a | n/a | 32.4348 | 235.752 | R-screen (F, stability_ratio, central, DAN, gradedness) |
| 2 | 3.0 | 8.0 | 0.0 | off | 400 | 0.2375 | n/a | 0.0000 | n/a–n/a | 0.00–0.00 | 0.00–0.00 | 0.00–0.00 | 302.03 | n/a | n/a | n/a | 32.4360 | 235.752 | R-screen (F, stability_ratio, central, DAN, gradedness) |
| 2 | 4.0 | 2.0 | 1.0 | on | 400 | 0.1750 | n/a | 0.0000 | n/a–n/a | 0.00–0.00 | 0.00–0.00 | 0.00–0.00 | 322.37 | n/a | n/a | n/a | 32.5011 | 235.752 | R-screen (F, stability_ratio, central, DAN, gradedness) |
| 1 | 3.0 | 1.0 | 0.0 | off | 100 | 0.7000 | n/a | 0.0000 | n/a–n/a | 0.00–0.00 | 0.00–0.00 | 0.00–0.00 | 328.32 | n/a | n/a | n/a | 32.5194 | 235.752 | R-screen (F, stability_ratio, central, DAN, gradedness) |
| 2 | 3.0 | 6.0 | 0.0 | on | 400 | 0.2375 | n/a | 0.0000 | n/a–n/a | 0.00–0.00 | 0.00–0.00 | 0.00–0.00 | 328.35 | n/a | n/a | n/a | 32.5195 | 235.752 | R-screen (F, stability_ratio, central, DAN, gradedness) |
| 2 | 3.0 | 6.0 | 0.0 | off | 400 | 0.2375 | n/a | 0.0000 | n/a–n/a | 0.00–0.00 | 0.00–0.00 | 0.00–0.00 | 328.78 | n/a | n/a | n/a | 32.5208 | 235.752 | R-screen (F, stability_ratio, central, DAN, gradedness) |
| 1 | 3.0 | 4.0 | 0.0 | off | 100 | 0.7000 | n/a | 0.0000 | n/a–n/a | 0.00–0.00 | 0.00–0.00 | 0.00–0.00 | 330.46 | n/a | n/a | n/a | 32.5259 | 235.752 | R-screen (F, stability_ratio, central, DAN, gradedness) |
| 2 | 4.0 | 2.0 | 0.0 | on | 400 | 0.2375 | n/a | 0.0000 | n/a–n/a | 0.00–0.00 | 0.00–0.00 | 0.00–0.00 | 357.21 | n/a | n/a | n/a | 32.6037 | 235.752 | R-screen (F, stability_ratio, central, DAN, gradedness) |
| 2 | 4.0 | 2.0 | 0.0 | off | 400 | 0.2375 | n/a | 0.0000 | n/a–n/a | 0.00–0.00 | 0.00–0.00 | 0.00–0.00 | 361.31 | n/a | n/a | n/a | 32.6152 | 235.752 | R-screen (F, stability_ratio, central, DAN, gradedness) |
<!-- closest-miss:end -->

## Tier 3 — WP24 (complete)

Rolf authorised structural rest mechanisms on 2026-09-16. WP24 is complete. WP26 sub-tier 3d is complete. Ranked list: empty. Shortlist: empty. No `drive-v0.2.yaml` is written. The bare substrate stays canonical. **P2-partial-B holds.** Item 81 records this as Phase 2's resting-state outcome. No F cap was relaxed.

Item 87 (WP28, `b3d72fa`) gates the relative ignition test on `ign.min_baseline_hz` 0.5 Hz; the absolute 8 Hz cap stays unconditional. Recheck `validation/records/p2/rest-ignition-recheck.json`: **171** T1 rows change (3a 63, 3b 18, 3d 90; 3c 0). Every settled central mean is under 0.5 Hz, so no R-screen verdict flips. No stored record is rewritten. The changed rows include a rolling maximum of 7.92 Hz (T3d `u11-s3-w00-09`, 7.920 Hz) and a 0.49 Hz settled baseline (T3a `u14-s1-w00-05`, 0.485 Hz). Relative ignition does not apply below the floor; the absolute 8 Hz test alone now judges those rows, and 7.92 Hz stays under the cap.

| Sub-tier | Engine | Ended | Ranked | Closest miss | Failed criteria |
|---|---|---|---|---|---|
| 3a | `lif+sfa` | T1 R-screen (0/17) | empty | `1.0-4.0-0.0-False-100-0.85-sfa-1.0-50.0-non_sensory` | R-screen (see 3a decision) |
| 3b | `lif+std` | T1 R-screen (0/4) | empty | `1.0-8.0-0.0-False-100-1.25-std-0.05-100.0-non_sensory` | KC 15.26 Hz vs ≤ 2 Hz; F 3.012 vs < 3 |
| 3c | `lif+cbi` | T0 (0/45); item 89 T1 at dt 0.05 ms (0/1) | empty | T0 `1.0-1.0-E_inh=-72-all`; T1 `1.0-1.0-0.0-False-100-0.7-cbi--72.0-all-kc-1.0` | T0 `cbi-stiff` (`h_max` 19.65 vs cut > 19); T1 silent then F 4–7 and `cbi-stiff` (cut > 39) |
| 3d | KC-targeted APL (`lif`) | T1 R-screen (0/24) | empty | `1.0-4.0-0.0-False-100-0.85-kc-6.0` | F 3.02 mean / 3.22 pair vs < 3; KC 0.25 Hz and central 5.74 Hz pass |

Sub-tier 3a (`lif+sfa`) ended empty at T1 R-screen. 17 of 180 T0 units passed. T1 scored 17 units and 289 pairs. R-screen passers: 0. T2 did not launch. Closest miss `1.0-4.0-0.0-False-100-0.85-sfa-1.0-50.0-non_sensory`. Decision `validation/records/p2/rest-T3a-decision.json`.

Sub-tier 3b (`lif+std`) ended empty at T1 R-screen. T0 admitted 4 of 180 units. T1 scored 4 units and 68 pairs. R-screen passers: 0. T2 did not launch. Closest miss unit `g_gaba=1.0`, `g_glu=8.0`, `U=0.05`, `tau_ms=100`, scope `non_sensory`, `w_bg=1.25` mV (pair 1.25 / 1.30). Lowest S **2.036**. Violated criteria: KC seed-mean **15.26 Hz** at 1.30 mV and **13.98 Hz** at 1.25 mV against ≤ 2 Hz; F **3.012** on seed 3 at 1.25 mV against < 3. Decision `validation/records/p2/rest-T3b-decision.json`.

3b closest-miss table (lowest S at T1 R-screen):

| g_gaba | g_glu | U | tau_ms | scope | w_bg | S | KC Hz (1.25 / 1.30) | F worst | caps | flags | failed stage |
|---:|---:|---:|---:|---|---:|---:|---|---:|---|---|---|
| 1.0 | 8.0 | 0.05 | 100.0 | non_sensory | 1.25 | 2.036 | 13.98 / 15.26 vs ≤ 2 | 3.012 vs < 3 | KC, F | `t2-b-unreachable` | R-screen |

Sub-tier 3c (`lif+cbi`) ended empty at T0, then empty at T1 for the one unit item 89 reopened. Ranked list: empty. Shortlist: empty. Decision `validation/records/p2/rest-T3c-decision.json`. The T0 record is unchanged.

3c T0 closest-miss table (highest T0 retention; `cbi-stiff` blocked the T0 pass):

| g_gaba | g_glu | E_inh mV | scope | retention | difference Hz | h_max | flags | failed stage |
|---:|---:|---:|---|---:|---:|---:|---|---|
| 1.0 | 1.0 | −72.0 | all | 0.609 | 34.1 | 19.65 | `t2-b-unreachable`, `cbi-stiff` | T0 |

### 3c convergence

Item 88. Five 3c units at recorded `lif.dt` 0.1 ms, 0.05 ms, and 0.025 ms on rk4. T0 background off, seed 1, same-job bare at each step. Plan `validation/records/p2/rest-T3c-convergence-plan.json`. Record `validation/records/p2/rest-T3c-convergence.json`. IBM `flyo-08` `cx2-64x128`, 36 workers, 18 tasks, 108 brain s, exit 0. No unit is readmitted to T0.

Units (log-spaced `h_max` from the T0 record, required closest miss first): `1.0-1.0-cbi--72.0-all` (19.65), `1.5-4.0-cbi--72.0-all` (36.74), `3.0-8.0-cbi--72.0-all` (70.05), `1.5-8.0-cbi--62.0-all` (134.04), `1.0-8.0-cbi--57.0-all` (256.53).

Verdict rule: **numerical** if dt/2 and dt/4 agree (retention within 0.05 and MN9 difference within 2 Hz) and every retention is ≥ 0.5; **physical** if every retention is < 0.5; otherwise **mixed**. Overall **mixed**.

| unit | recorded h_max | recorded ret | dt 0.1 ret / h_max | dt 0.05 | dt 0.025 | stiff at 0.1 / 0.05 / 0.025 | verdict |
|---|---:|---:|---|---|---|---|---|
| `1.0-1.0-cbi--72.0-all` | 19.65 | 0.609 | 0.600 / 18.77 | 0.704 / 17.92 | 0.643 / 16.09 | no / no / no | mixed |
| `1.5-4.0-cbi--72.0-all` | 36.74 | 0.043 | 0.080 / 31.45 | 0.037 / 33.74 | 0.071 / 30.06 | yes / no / no | physical |
| `3.0-8.0-cbi--72.0-all` | 70.05 | 0.000 | 0.000 / 52.86 | 0.000 / 48.38 | 0.000 / 49.88 | yes / yes / no | physical |
| `1.5-8.0-cbi--62.0-all` | 134.04 | 0.027 | 0.000 / 134.04 | 0.074 / 97.43 | 0.071 / 113.70 | yes / yes / yes | physical |
| `1.0-8.0-cbi--57.0-all` | 256.53 | 0.052 | 0.020 / 185.12 | 0.074 / 193.05 | 0.071 / 229.14 | yes / yes / yes | physical |

The closest miss keeps the reflex (retention ≥ 0.5) at every step. dt/2 and dt/4 retention differ by 0.061, so the unit is not numerical. Seed-1 `h_max` at 0.1 ms is 18.77 (below the stiffness cut); the 10-seed T0 maximum was 19.65. The four stiffer units stay below 0.5 at every step, including steps where `cbi-stiff` clears.

Bare MN9 difference: 50 Hz at 0.1 ms, 54 Hz at 0.05 ms, 56 Hz at 0.025 ms.

### 3c T1 at dt 0.05 ms (item 89)

Item 89. Ordinary T1 R-screen for `1.0-1.0-cbi--72.0-all` alone at dt 0.05 ms on rk4 (two adjacent weights, three seeds, the 2.3 rows, gradedness). Stiffness cut at that step (`h_max` > 39). T2 with item 74 if it passed. The other 44 units stay closed. Plan `validation/records/p2/rest-T3c-T1-plan.json`. Record `validation/records/p2/rest-T3c-T1.json`. IBM `flyo-10` `cx2-64x128`, 36 workers, 15 tasks, 684 brain s, exit 0. T2 did not run. Item 74 did not run. No unit is readmitted to T0.

Result: 0 of 1 unit passed the R-screen. Closest miss `1.0-1.0-0.0-False-100-0.7-cbi--72.0-all-kc-1.0` at `w_bg` 0.70, S **37.8**. That pair is silent (central 0 Hz; F and stability not computable). From 0.80 mV the network is active (central 8.7–18 Hz) but F is 4–7 against < 3, and 51 of 57 rows have `h_max` 39.6–49.4, so they are still `cbi-stiff` at dt 0.05 ms. Failed stage: R-screen.

3c T1 closest-miss table:

| g_gaba | g_glu | E_inh mV | scope | w_bg | S | central Hz | F | h_max | flags | failed stage |
|---:|---:|---:|---|---:|---:|---:|---:|---:|---|---|
| 1.0 | 1.0 | −72.0 | all | 0.70 | 37.8 | 0 | not computable | 0 | `t2-b-unreachable` | R-screen |

Sub-tier 3d (KC-targeted APL inhibition on `lif`, WP26) ended empty at T1 R-screen. T0 admitted 24 of 24 units. T1 scored 24 units and 0 R-screen passers. T2 did not run. Item 74 did not run. Closest miss `1.0-4.0-0.0-False-100-0.85-kc-6.0` (pair (1, 4), no adaptation, `g_gaba_kc` 6, `w_bg` 0.85). Lowest S **0.0714**. Violated criterion: F **3.020** mean at 0.85 mV and **3.222** on the 0.85/0.90 pair against < 3. KC **0.251 Hz** and central **5.74 Hz** pass. The F cap was not relaxed. Decision `validation/records/p2/rest-T3d-decision.json`. **P2-partial-B stands.**

3d closest-miss table (lowest S at T1 R-screen):

| g_gaba | g_glu | g_gaba_kc | 3a | w_bg | S | KC Hz | F mean / pair | central Hz | flags | failed stage |
|---:|---:|---:|---|---:|---:|---:|---|---:|---|---|
| 1.0 | 4.0 | 6.0 | none | 0.85 | 0.0714 | 0.251 vs ≤ 2 | 3.020 / 3.222 vs < 3 | 5.74 | none | R-screen |

Item 74: a tier-3 T2 candidate that fails only R-reflex (a) or (b) is judged again at 0.5 and 0.4 of the same-job bare difference (28.0 Hz mean and 22.4 Hz seed minimum against a 56 Hz bare). Named floors are 28 Hz and 22 Hz when the bare mean is missing. Both verdicts are recorded. A pass of that second judgment is flagged `reflex-harmonised` in its record, in this file, and in the RANKED line. A fail of (c), R-long, `cbi-stiff`, or provenance is not rescued. No 3a, 3b, 3c, or 3d candidate reached T2. No candidate carries that flag.

## 3d diagnostic — WP27 (experiments 1 and 2)

Diagnostic only. The 3d closest miss `1.0-4.0-0.0-False-100-0.85-kc-6.0` was replayed on IBM. These runs admit nothing to T1 or T2. The F cap was not relaxed. **P2-partial-B stands.** Records `validation/records/p2/rest-T3d-diag.json` and `validation/records/p2/rest-T3d-sigma.json`. Decision `validation/records/p2/rest-T3d-sigma-decision.json`.

**Where the variance lives.** Disjoint 1 ms counts put most of the covariance inside the central block (`within_cov` ~290–310 versus independent ~135 on settled clamped windows). The largest block-pair term is always `central:rest`, then `KC:central` and `optic:central`. MN9, APL and DAN are near-independent. This is a central shared fluctuation, not a KC or MN9 event.

**Timescale.** Population F at 1 ms is ~3.0–3.2 on settled clamped windows, early `[2, 12)` and late `[12, 32)` alike, so the excess is not a startup artefact. A 100 ms within-neuron shuffle returns F ≈ 0.96–1.05, so the 1 ms excess is synchrony inside 100 ms, not a slow common rate that the shuffle would keep. F still rises at 50 ms and 100 ms bins (clamped 0.85 seed 2: 1 ms 2.91 → 100 ms 5.69 early / 7.24 late). Both fast synchrony and coarser shared structure are present.

**Dark MN9.** Clamped 0.90 mV seed 3 has MN9 **54.1 Hz** in the `[2, 12)` window (the T1 interval). Late `[12, 32)` is 68.45 Hz. The committed row `mn9_hz` of 47.5 Hz was scored on `[1, 11)` by an off-by-one in `_instrumented_probe` (r18f aligned that window with `_probe`; this JSON is not rewritten). The other eleven long `[2, 12)` windows stay at 0.4–2.2 Hz. The run is not ignited on central (max rolling 5.98 Hz).

**Background-on reflex.** Sugar-on versus sugar-off at 0.85/0.90 mV, 3 s. (a) six differences `[25.7, 28.0, 29.0, 24.0, −6.0, 24.7]` Hz. (b) ten seeds at 0.85 mV, mean ~25 Hz. (c) passes (upstream FF retention 1.02; recorded T0 extended 0.559). Original floors 50/40 Hz fail (a) and (b). Item 74 floors 28.0/22.4 Hz against the 56 Hz same-job bare also fail (a) and (b). `reflex-harmonised` is false.

**2.2r median-rate bound.** All twelve free-pool windows have median **0 Hz**. The gate (median in [0.2, 5] Hz and <1% above 50 Hz) fails. Free 0.85 mV seeds 1 and 3 ignite (T1 F 32.4 and 63.0).

**Sigma grid.** `sigma_th` in {0, 0.5, 1, 2} mV, weights 0.75–1.00. T0 difference **31.3 Hz**, retention **0.559**, identical at every sigma: T0 is background-off with base thresholds (`feedforward=True`, `thresholds=False`), so it is not evidence about the spread network. R-screen passers, all S 0, all fail background-on reflex (a)/(b) on both verdicts, (c) passes. r18f recomputed (a) from the raw sugar rows: (a) is the six MN9 differences at both pair weights, seeds 1–3, and item 74 uses the minimum of those six against 0.4 of the same-job bare mean (22.4 Hz at 56 Hz), not the mean of (a).

Sigma_th 1 mV at pair 0.75/0.80: `a_hz` `[31, 35, 30, 36, 83, 3]`. The 83 Hz seed (0.80 mV seed 2) is quiet dark (MN9 1 Hz) then sugar 84 Hz. The 3 Hz seed (0.80 mV seed 3) is dark MN9 already at 78 Hz (sugar 81 Hz). Settle holds (stability 1, central ~5.8 Hz, not ignited). Harmonised (b) passes (min 27 Hz, mean 31.6 Hz). Harmonised (a) fails on the 3 Hz seed. `reflex-harmonised` is false. Sigma_th 2 mV passers have dark MN9 already at 95–116 Hz; the sugar difference is gone.

| sigma_th | w_bg | candidate_id | F max pair | KC Hz | central Hz |
|---:|---:|---|---:|---:|---:|
| 1.0 | 0.75 | `1.0-4.0-1.0-False-100-0.75-kc-6.0` | 2.986 | 0.237 | 5.62 |
| 2.0 | 0.75 | `1.0-4.0-2.0-False-100-0.75-kc-6.0` | 2.999 | 0.284 | 6.50 |
| 2.0 | 0.90 | `1.0-4.0-2.0-False-100-0.9-kc-6.0` | 2.979 | 0.341 | 7.43 |

Closest miss among R-screen failures: `1.0-4.0-2.0-False-100-0.8-kc-6.0`, S **0.0214**, F **3.065** vs < 3, KC **0.305 Hz**, central **6.77 Hz**.

## 3d freeze — WP27 experiment 4

Diagnostic only. Item 90 froze `1.0-4.0-1.0-False-100-0.75-kc-6.0` (sigma_th 1 mV, pair 0.75/0.80) on fresh seeds 11–20. Record `validation/records/p2/rest-T3d-freeze.json`. `admitted_t1` false. `admitted_t2` false. Experiment 3 (`n_bg`) was not run.

**Window (item 95).** flyo-11 staged `0fd2aed` before `92704fa`. Live `F` and `mn9_hz` on the 32 s rows are `[1, 11)`. The collector scores F and dark MN9 from `windows.early` `[2, 12)`. That F matches FanoAccumulator F on the npz population 1 ms counts `[2000, 12000)`. Sugar and T1 perturbation rows already use `_probe` `[2, 12)`.

**R-screen on seeds 11–20.** It does not hold. Pair gates use the ten clamped `[2, 12)` rows at 0.75 and 0.80 mV, no 0.85 mV gradedness point. Record F max **3.100** is that window at 0.80 mV seed 14 (also 3.000, 3.010, 3.023 at 0.80 seeds 11, 15, 16). 0.75 mV `[2, 12)` F stays under 3 (max 2.854). Seeds 11 and 18 at 0.75 mV are in the record: live `[1, 11)` F **9.205** and **8.304** (`F_recorded`); scored F **2.786** and **2.805**. KC **0.236 Hz**, central **5.59 Hz** at 0.75 mV from live rates. S **0.0329**, F only. Overlay rescores F and MN9; `rates_hz`, `b`, and stability stay live `[1, 11)`. `[2, 12)` `block_means_hz` also pass central, DAN, and KC.

**Dark MN9.** Each long row carries `mn9_hz` on `[2, 12)` and `mn9_hz_recorded` on `[1, 11)`, so item 100 is reproducible from the record. Free-pool 0.80 mV: 7 of 10 seeds at **48.0 to 84.6 Hz**. Clamped 0.80 mV: 5 of 10 at 44.4 to 86.1 Hz. Clamped 0.75 mV: 2 of 10 (72.9 Hz seed 19, 88.1 Hz seed 20). Free 0.75 mV: 1 of 10 (87.4 Hz seed 17). Clamped pair rows exceed 10 Hz on 12 of 20.

**Background-on reflex.** (a) six differences seeds 11–13 both weights `[27.7, 85.7, 35.0, 3.0, 83.7, −53.3]` Hz. (b) ten seeds at 0.75 mV, mean **29.2 Hz**, min **−55 Hz** (seed 19 silent 89 Hz, sugar 34 Hz). Same-job bare mean **57.0 Hz**. (c) passes (upstream FF; recorded T0 extended retention 0.559). Original 50/40 Hz fail. Item 74 floors 28.5/22.8 Hz fail (a) on min(a) **−53.3 Hz** (0.80 mV seed 13 already 87 Hz in the dark; sugar 33.7 Hz). Harmonised (b) would pass the mean. `reflex-harmonised` is false. Sugar silent rates live in the raw `sugar-w080.ndjson`; the freeze record stores the differences.

**Perturbation.** Configured weight ±0.05 on seeds 11–13. `_probe` already scores `[2, 12)`. 0.75 mV holds (F max 2.838). 0.70 mV fails (F **42.8** at seed 12). 0.80 mV fails (F **3.000** at seed 11). The collector uses spec F < 3, so 3.000 fails. Live `ignited` is True on 0.70 seeds 11 and 12 because flyo-11 staged `0fd2aed`, which used `peak > 3 × settled or peak > 8` with no 0.5 Hz floor. Item 87 does not trip (settled 0.19 Hz and 0.09 Hz, peak 5.59 Hz and 5.58 Hz). `freeze_perturbation` does not read the ignited flag.

**2.2r.** All 40 free-pool windows have median **0 Hz**. The gate fails.

`data/drive-dev-p2.yaml` stays the development substrate. The bare substrate stays canonical.

## 3e non-uniform — WP29 (item 110)

Non-uniform vectors on the 3d substrate `1.0-4.0-0.0-False-100-<w>-kc-6.0`. No engine equation change. `_probe` scoring unchanged. The R-screen, item 74, and item 87 stay as written. Lab Fano, pairwise correlation, and PCA participation ratio are recorded-only. Records `validation/records/p2/rest-T3e.json`, `validation/records/p2/rest-T3e-rows.json`, and `validation/records/p2/rest-T3e-decision.json`. Plan `validation/records/p2/rest-T3e-plan.json`. IBM two `cx2-64x128` boxes, 50 tasks, 2784 brain-s, list $4.49.

Arm E `hubs` did not run: the registry resolves MBON06 (n=2) and does not resolve LPi13 or LPi15 under any spelling tried (LPi3-4, LPi4-3, LPi2-1, LPi1-2 are also empty). Cell types present are LPi12 (n=4) and LPi21 (n=2). A hub arm on MBON06 plus those two types would need a new ruling. Skip reason recorded in the plan. Sugar `sugar_GRN_R` (n=21) sits inside `groups['sensory']`. Arm A therefore already drives those GRNs with the Poisson background; the paired-sugar 150 Hz is added on top.

`K_i` is incoming synapse count (sum of `|Excitatory x Connectivity|` onto i). On v783: n=138639, n_zero=1549, min 0, max 69948, median of positive 200, p99 3477, mean 393.

Same-job bare mean **56.0 Hz**. Mean wall per brain-s **45.47**.

**T0** (background off, 10 seeds). Arms A–C keep the 3d feed-forward difference **31.3 Hz**, retention **0.559**. Arm D kills the path as beta grows: 10.8 Hz (0.193) at 0.5, 0.4 Hz (0.007) at 1.0, 0.0 Hz at 2.0. The GRNs themselves are not the cause: sugar `K_i` is 79–315 (median 172), so beta 2.0 shifts them by at most 0.63 mV. MN9 (`K_i` 5579) shifts by 2.8 / 5.6 / 11.2 mV. The largest excitatory posts of `sugar_GRN_R` include il3LN6 (`K_i` 17347, +8.7 mV at beta 0.5) and DNg35 (`K_i` 11638, +5.8 mV). Those high-K cells on the path go subthreshold first.

**R-screen** on `[2, 12)`, three seeds, two adjacent ladder weights. One passer: arm A `sens` at pair 1.00/1.20 mV, candidate `1.0-4.0-0.0-False-100-1.0-kc-6.0-sens`. S **0**. F max **2.680** vs < 3. KC **0.0875 Hz**. central **4.83 Hz**. DAN **0.809 Hz**. Dark MN9 on the six pair rows: 0.0, 2.6, 0.0, 2.9, 0.3, 1.8 Hz (all under 5 Hz). Sugar-silent dark MN9 on the pair, seeds 1–10: 0–4 Hz (all under 5 Hz). The 4.0 Hz sugar-silent max is 1.20 mV seed 4. Item 87 does not trip (settled ~4.83 Hz, rolling peak ~4.87 Hz). Lab at 1.00 mV seed 1 is recorded-only: single-unit Fano 100 ms **0.350** on **191** of a fixed 2,000 central neurons (**1,809** silent, excluded because Fano is undefined at mean count 0), mean pairwise corr 50 ms **1.57e-5** on **703** pairs (38 of the fixed 500-neuron sample had positive variance; C(38,2)=703), PCA participation ratio **20.01** on that 500-neuron sample.

**Item 74** on that passer, same-job 10-seed sugar, same seed and pair weight, sugar minus dark. (a) six differences `[33, 34, 22, 19, 22, 21]` Hz, min **19 Hz** (1.20 mV seed 1: dark 3 Hz, sugar 22 Hz). That 3-seed × two-weight (a) is the item 74 (a) test as written (decision 91). (b) ten seeds at 1.00 mV, mean **27.4 Hz**, min **22 Hz** (seed 3: dark 0 Hz, sugar 22 Hz). (c) passes (extended retention 0.559). Original 50/40 Hz floors fail. Harmonised floors 28.0/22.4 Hz against the 56 Hz bare fail min(a) 19 vs 22.4, mean(b) 27.4 vs 28.0 (strict `>`), and min(b) 22 vs 22.4. `_ab_pass` uses all three. The harmonised (b) violation scalar encodes only the mean miss. `reflex-harmonised` is false. No freeze box. The stop rule of item 110 applies: no R-screen passer kept the reflex with dark MN9 under 5 Hz in every seed.

Arms B `nomotor` and C `indeg` fail the R-screen on F (up to 43 and 19) with a silent or near-silent 0.75 mV point. Arm D `thdeg` is silent at rest (central ~0 Hz) and already failed T0 at beta ≥ 0.5. Ranked list: empty. Shortlist: empty. **P2-partial-B stands.** The rest search closes. No further round starts without a new ruling from Rolf.

3e closest-miss table (deepest stage first; the screen passer that failed item 74):

| arm | w_bg | candidate_id | S | F max pair | KC Hz | central Hz | MN9 dark max Hz | item 74 | failed stage |
|---|---:|---|---:|---:|---:|---:|---:|---|---|
| sens | 1.00 | `1.0-4.0-0.0-False-100-1.0-kc-6.0-sens` | 0 | 2.680 | 0.0875 | 4.83 | 2.9 (sugar-silent 4.0 at 1.20 seed 4) | fail min(a) 19 vs 22.4; mean(b) 27.4 vs 28.0; min(b) 22 vs 22.4 | R-reflex |

Per-arm T1 candidates (two per four-point ladder):

| arm | w_bg pair | T0 ret | S | F max | KC Hz | central Hz | MN9 dark max | failed checks |
|---|---|---:|---:|---:|---:|---:|---:|---|
| sens | 0.80 / 1.00 | 0.559 | 22.91 | 2.680 | 0 | 0 | 0.3 | stability, central, DAN, gradedness |
| sens | 1.00 / 1.20 | 0.559 | 0 | 2.680 | 0.0875 | 4.83 | 2.9 | none (item 74 fail) |
| nomotor | 0.75 / 0.80 | 0.559 | 25.74 | 43.07 | 0 | 0 | 1.0 | F, stability, central, DAN, gradedness |
| nomotor | 0.80 / 0.85 | 0.559 | 10.61 | 43.07 | 0.130 | 3.11 | 1.5 | F, stability, DAN, gradedness |
| indeg | 0.75 / 0.80 | 0.559 | 24.92 | 18.96 | 0 | 0 | 0.3 | F, stability, central, DAN, gradedness |
| indeg | 0.80 / 0.85 | 0.559 | 13.77 | 18.96 | 0 | 0.018 | 1.7 | F, stability, central, DAN, gradedness |
| thdeg-0.5 | 0.75 / 0.80 | 0.193 | 17.82 | 1.024 | 0 | 0 | 0.0 | stability, central, DAN, gradedness |
| thdeg-0.5 | 0.80 / 0.85 | 0.193 | 8.52 | 1.767 | 0 | 0 | 0.2 | stability, central, DAN, gradedness |
| thdeg-1.0 | 0.75 / 0.80 | 0.007 | 17.82 | 1.047 | 0 | 0 | 0.0 | stability, central, DAN, gradedness |
| thdeg-1.0 | 0.80 / 0.85 | 0.007 | 17.82 | 1.047 | 0 | 0 | 0.0 | stability, central, DAN, gradedness |
| thdeg-2.0 | 0.75 / 0.80 | 0 | 27.82 | 1.054 | 0 | 0 | 0.0 | F, stability, central, DAN, gradedness |
| thdeg-2.0 | 0.80 / 0.85 | 0 | 17.82 | 1.054 | 0 | 0 | 0.0 | stability, central, DAN, gradedness |
| hubs | skipped | — | — | — | — | — | — | LPi13, LPi15 missing |

`data/drive-dev-p2.yaml` stays the development substrate. The bare substrate stays canonical.

