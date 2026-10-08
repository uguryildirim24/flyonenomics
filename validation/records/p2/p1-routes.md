# P1 descending-route re-analysis (SPEC-P2 item 159)

This is an exploratory re-analysis of the existing complete circuit-tour outcomes, **not a new outcome run**. Machine-readable tables: [all 1,310 typed descending cells](p1-routes-cells.csv), [all 480 types](p1-routes-types.csv), and [provenance and all input checksums](p1-routes-manifest.json). The cell table has one row per root; the type table first averages cells of a type **within each seed**, then resamples whole seeds (never cells). The typed descending count follows `super_class == descending_neuron` and a non-null `type` in the cached annotation table; the run's broader `descending` group count is 1,314, not the definition used here. No group is inferred from a name alone.

Reproduce with this worktree's frozen environment (no simulation):

```sh
FLYONENOMICS_CACHE_DIR=<local-project-root>/.cache .venv/bin/python scripts/p1_routes_analysis.py <local-project-root>/<reference-checkout>/camber-runs/circuit-tour/outcomes
```

Each row is the seed-mean difference in ON spikes / 5 seconds against that seed's control ON spikes / 5 seconds, in Hz. Seeds 501–510; control plus P1-low (10 Hz), P1-medium (30 Hz), P1-high (60 Hz) Poisson input and `courtship_random` (30 Hz, 148 preselected cholinergic cells). Identical whole-seed bootstrap convention to `scripts/circuit_tour_analysis.py`: PCG64 seed 20260925, 10,000 resamples of ten matched seeds, percentile 95% intervals. `medium_minus_low`, `high_minus_medium`, `high_minus_low` and `medium_minus_random` are *paired within seed* before bootstrap. Source counts SHA-256 and model provenance are in the JSON manifest, verified before computing each row. CSV figures round to four decimal places; an interval touching or crossing zero is **no detected difference**, not equality. These are descriptive, unadjusted intervals over an exploratory scan of 480 types; selected large effects risk winner's curse. Classification is descriptive, not a pre-registered decision test.

## Named descending cells and types

All entries: Δ Hz [95% whole-seed interval]. Random means random-input minus control, not P1 minus random. Asterisks are not used; read intervals directly.

| Type/cell | Low | Medium | High | Random | Shape |
|---|---:|---:|---:|---:|---|
| pIP10, type mean (2) | +5.04 [4.03, 6.03] | +18.77 [16.71, 20.40] | +35.94 [32.37, 38.42] | +0.08 [-0.57, 0.83] | Graded rise; both successive contrasts positive |
| pIP10 R 11116 | +8.12 [6.84, 9.34] | +22.60 [21.10, 24.04] | +35.50 [33.34, 37.46] | -0.14 [-1.02, 0.86] | Graded rise |
| pIP10 L 523998 | +1.96 [0.98, 2.88] | +14.94 [12.22, 17.00] | +36.38 [31.26, 39.70] | +0.30 [-0.22, 0.88] | Graded rise |
| pIP1, type mean (2) | +4.63 [-6.29, 15.42] | +3.79 [-3.06, 12.57] | +1.01 [-8.22, 10.82] | +6.37 [0.02, 13.49] | No detected P1 difference; not a proven plateau |
| pIP1 L 10030 | +14.82 [-5.14, 34.90] | +13.32 [-0.52, 30.42] | +10.64 [-7.10, 28.90] | +16.82 [4.08, 30.78] | No detected P1 difference |
| pIP1 R 10038 | -5.56 [-8.00, -3.30] | -5.74 [-7.78, -3.60] | -8.62 [-11.16, -5.74] | -4.08 [-6.48, -1.62] | Decrease, not recruitment |
| DNp68, type mean (2) | -0.08 [-0.49, 0.35] | +0.63 [0.29, 0.97] | +14.94 [10.81, 18.16] | -0.06 [-0.57, 0.41] | Medium rise, much stronger at high |
| DNp68 R 11259 | 0.00 [0.00, 0.00] | +0.04 [0.00, 0.10] | +7.22 [5.20, 8.86] | 0.00 [0.00, 0.00] | High-only detected |
| DNp68 L 11674 | -0.16 [-0.98, 0.70] | +1.22 [0.54, 1.90] | +22.66 [16.44, 27.48] | -0.12 [-1.14, 0.82] | Medium rise, stronger at high |
| aSP22, type mean (2) | -0.03 [-0.16, 0.10] | -0.25 [-0.38, -0.14] | -0.32 [-0.45, -0.20] | +0.12 [-0.06, 0.32] | Not a low-rise route |

The type-level pIP10 medium-minus-low is +13.73 [12.39, 14.90] and high-minus-medium +17.17 [15.33, 18.63] Hz; a graded increase, though these intervals do not establish exact proportionality. DNp68 high-minus-medium is +14.31 [10.18, 17.56] Hz. pIP1 high-minus-low is -3.62 [-12.08, 6.42] Hz; failure to distinguish its levels cannot establish a plateau, especially with the opposite-signed cells and positive random-input mean. For a smaller low-rise/non-detected-further-change example, DNge068's type mean is +0.47 Hz at low; inspect its full intervals in the type table before interpreting it as a plateau, much less as aggression.

For every CSV row, `shape` uses the same intervals: “low rise; further change not detected” means positive low and both medium-minus-low and high-minus-low contain zero; “high-only detected” means low and medium contain zero, high and high-minus-medium are positive; “rises at each step” means low, medium-minus-low and high-minus-medium are positive; “no detected difference” means all three P1-versus-control intervals contain zero. Everything else is “other/mixed”. The descriptions are not exhaustive biological states: decreases and medium-first increases can land in mixed. No non-detection proves a true flat response. The CSV retains all eight intervals and the row-level shape rather than hiding mixed responses.

The largest type-mean detected early response is pIP10 (+5.04 Hz); the largest high-minus-low is also pIP10 (+30.90 [28.08, 32.90] Hz). Other late high-minus-low examples are DNge151 (+18.40 [12.42, 23.34]), DNge138 (+17.47 [11.35, 22.27]) and DNpe034 (+17.41 [12.15, 21.65]) Hz; their functional roles are not assigned by this assay. No specific early aggression route is demonstrated. See `docs/p1-routes.md` for the biological comparison and limits. This model has one injected input site, no body, does not see, and Poisson drive frequencies are not optogenetic light intensities.
