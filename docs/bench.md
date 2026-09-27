Partial-delivery predicate met at 119d533; main predicate not met: closed-loop not achieved because the sign curve stayed flat at 280 Hz.

Historical absolute cache paths in this log are shown as portable examples. The 2026 runs used a shared cache, not necessarily the current checkout's `.cache`; commands below were not rerun when paths were normalized.

# Benchmarks B1 and B2 (SPEC 3.1 and 3.10)

## B1

Run `uv run python scripts/bench.py --b1` from the worktree root with
`FLYONENOMICS_CACHE_DIR="$PWD/.cache"` exported (or an absolute shared-cache path).
The command clears only the current worktree's Cython directory:
`$FLYONENOMICS_CACHE_DIR/cython/<worktree-directory-name>`.
It runs the cold and warm legs sequentially in fresh processes, one built
network per process, and prints their JSON measurements.

Workload: v783, 138,639 neurons; a 200-neuron extended input (indices 0–199)
at 50 Hz; 20 brain seconds in 10 ms chunks; seed 20260912. The background
object is present with every `w_bg_i = 0`. These are background-off figures.
Build time is measured by the parent from child-process launch through
`store("initial")`; q1 is run wall time divided by 20 brain seconds.

Measured in review r3 on 2026-09-12 local time (2026-09-13 UTC), Mac17,8,
Apple M5 Pro, 24 GiB RAM, macOS 26.6.2, using the engine implementation
at `7af3d362e47b5ce36dac8710c320f12c1758adfd`. Times below are the printed
JSON values rounded to six decimal places.

| Cache | Process-start build to initial store (s) | Run wall time for 20 brain s | q1 (wall s / brain s) | Spikes |
|---|---:|---:|---:|---:|
| cold | 2.672302 | 419.005957 | 20.950298 | 9,580,635 |
| warm | 1.074464 | 360.282995 | 18.014150 | 9,580,635 |
| drive-dev, cold / warm | 2.719586 / 0.868424 | 413.884840 / 358.589515 | 20.694242 / 17.929476 | 13,301,989 / 13,301,989 |
| drive-dev at `g_inh=4`, cold / warm | 4.508051 / 2.658096 | 416.458368 / 348.388524 | 20.822918 / 17.419426 | 6,091,395 / 6,091,395 |
| review r5 drive-dev `g_inh=4`, cold / warm | 4.561429 / 2.978463 | 404.602622 / 348.580656 | 20.230131 / 17.429033 | 6,091,395 / 6,091,395 |

The added WP3 row is B1 with `--drive data/drive-dev.yaml` on the provisional
low-side weights; paired values are cold / warm. It used the per-neuron-string
background path. Warm `q1 = 17.929476` remains above the 15 target and below
the 30 escalation threshold, so development test 2.5 is recorded failed;
this is not a qualified background benchmark.

The WP3b row reran `uv run python scripts/bench.py --b1 --drive
data/drive-dev.yaml` on the attempt-3 table. It applied `g_inh=4` to all
negative connections before the `initial` snapshot, then the per-group
background weights. Unlike the historical WP3 row, its process-start build
time includes loading the signed parquet column and storing the scaled
network. Warm `q1=17.419426` still exceeds the 15 target but stays below
the 30 escalation line. Development test 2.5 therefore failed; B2 was not yet
measured at that point (see B2 below).

Review r5 repeated the weighted B1 path through the full validation runner
at execution commit `280e7a8efc434829f4026491eb69bb4a63a29861`. Both fresh processes used the
real per-neuron-string background and the ratio-4 table before the initial
snapshot. Warm q1 was 17.429033; development 2.5 was recorded
failed against target 15. This is a development performance
measurement, not a resting-state qualification or a B2 measurement.

The per-neuron weight-string path ran: one whole-group `PoissonInput`,
`N = 100`, rate 10 Hz, weight expression `w_bg_i` (constants read from Params).
The per-group fallback was unnecessary. Both legs produced exactly
9,580,635 spikes. Brian2 compiles lazily at the first run, so cold compilation
is included in the cold run time rather than entirely in build time; the
cold/warm difference is not an isolated compiler timing.

Warm q1 is **18.014150**; cold q1 is **20.950298**. Both exceed the target
of 15 and remain below the escalation threshold of 30. Per SPEC 3.1 and
11.18, work continues, budgets must be recomputed, and test 2.5 is recorded
accordingly when its owning package runs it. WP3 reran B1 with the development
drive table (rows above). This background-off engine benchmark qualifies no
drive, and none is calibrated in Phase 1 (item 47), nor the complete model.

## B2

The four-worker B2 leg completed on 2026-09-13 using a shared cache. A portable rerun command is `FLYONENOMICS_CACHE_DIR="$PWD/.cache" uv run python scripts/bench.py --b2` (after provisioning the cache). The recorded leg used the section 6.3 acceptance experiment with seeds 1–4, bare background off, A/C on, and the frozen fallback behaviour pin. Run `20260913T224205.229595Z-a43cddb6` finished `done` with `validate_run` empty. No second B2 leg was needed.

The orchestrator's amended precondition was met before launch: no other engine process, `vm.swapusage` used 2,016.81 MiB (limit 3,000), and `memory_pressure` 79% free (minimum 50%). The monitor sampled summed live-worker RSS and swap every five seconds, 238 samples from launch through completion. Peak summed worker RSS was **8,917.797 MiB** (8.709 GiB), below the section 3.10 20 GiB three-worker rerun threshold. Swap used stayed at **2,016.81 MiB**, below the 3,800 MiB stop threshold; no worker was killed. The individual sample series is retained in the WP9 report.

| B2 quantity | Measured |
|---|---:|
| Worker count | 4 |
| Total probe brain time including settle, `T_B2` | 352.000 s |
| Mean settle, `s̄` | 2.000 s |
| First probe start to last probe end, `t_probe` | 1,199.619 wall s |
| Aggregate throughput, `q2 = t_probe / T_B2` | 3.408007 wall s / brain s |
| Process start to `store("initial")`, max worker `t_build` | 1.690 wall s |
| Engine-only max worker build (separate diagnostic) | 1.078 wall s |
| Aggregation through final manifest write, `t_agg` | 0.168 wall s |
| Total orchestrator wall time | 1,200.743 s |

The runner timestamps the first probe phase and the start of aggregation on its monotonic clock; `t_probe` is their difference. `t_build` uses each spawned worker's `built_at` timestamp against its parent launch timestamp. The manifest's raw `aggregation_s` field is 0.026730 s through the completed metrics write; the final manifest file appeared 0.141229 s after `status.json` entered `done`. Their sum, 0.167959 s, is the full `t_agg` used below. The budget rule is `1.25 × q2 × T + n_runs × (t_build + t_agg)`; `q2` already includes four-worker throughput and is not divided by four again.

| Section 3.10 workload | Probe brain time `T` (s) | Number of runs | Budget (wall s) |
|---|---:|---:|---:|
| B2 measured file | 352 | 1 | 1,501.381 |
| Ten-seed paired acceptance, one execution | 880 | 1 | 3,750.666 |
| Ten-seed paired acceptance, bitwise replay pair | 1,760 | 2 | 7,501.332 |
| Open-loop fallback acceptance, one execution | 1,400 | 1 | 5,965.871 |
| Open-loop fallback, bitwise replay pair | 2,800 | 2 | 11,931.741 |
| Four paired genotype files, eight arms in total | 3,520 | 4 | 15,002.664 |
| One actual ten-seed, one-arm control file | 220 | 1 | 939.060 |
| Final eight-arm, ten-seed ablation file | 1,760 | 1 | 7,499.474 |
| Three-seed, four-arm dose series | 252 | 1 | 1,075.380 |
| Full 27-setting, three-seed sensitivity grid | 6,804 | 27 | 29,035.266 |

These estimates use the observed 2 s mean settle for each probe. The one-worker level-3 and ablation runs retain the same nominal section 3.10 formula for comparison, but their actual wall times will be reported separately because B2's four-worker `q2` is not a one-worker speed measurement.

The final eight-arm ablation used the then-current three-worker policy and completed in 7,285.557 wall s against its B2-derived 7,499.474 s nominal budget. Its 80 probes all settled, `validate_run` was empty, peak summed worker RSS was 7,512.000 MiB, and peak swap used was 1,928.75 MiB; there was no fallback. Later multi-arm and multi-seed runs use Rolf's amended four-worker policy, with a two-worker fallback only if swap exceeds 3,800 MiB or a worker is killed.

The four-worker, three-seed dose series completed in 832.629 wall s against its 1,075.380 s nominal budget (`validate_run=[]`, no unsettled probes). Peak summed worker RSS was 8,885.188 MiB and peak swap used 1,920.75 MiB. A straight 27-setting forecast from this measured run is 22,480.983 wall s, below the B2-derived 29,035.266 s grid budget; the final grid must still report actual timing and any setting-specific slowdowns.

The first I4 pair, executed at `700a045` and superseded for clause 3 by the pair at `bbb00c2` (item 67), finished its two separate four-worker open-loop acceptance executions in 5,396.072 and 4,613.864 manifest wall seconds, respectively, each below the 5,965.871 s one-run budget; together they used 10,009.936 s below the 11,931.741 s replay-pair budget. Their peak sampled worker RSS values were 8,427.453 and 8,684.266 MiB; peak swap used was 1,920.75 and 1,904.75 MiB. The MCP replay compared 320 Parquet tables and metrics bit for bit, with a separate exact comparison of 40 live-event files. These are integration timings under the frozen open-loop fallback, not a closed-loop behavioural benchmark.

The I4 pair that carries clause 3, executed at `bbb00c2` (runs `20260914T172729.979889Z-0d0a9a8c` and `20260914T193256.822683Z-0d0a9a8c`), reports manifest walls of 5,844.634 and 4,700.647 s. Those manifest walls are `time.monotonic` intervals, which on macOS (`mach_absolute_time`) stop while the machine sleeps. Review r11 measured real elapsed time from each run id's UTC timestamp to its `manifest.json` modification time: 7,524.774 s for the first run and 4,703.448 s for the second. `pmset -g log` records 47 sleep intervals totalling about 1,775 s (clamshell and maintenance sleep, 13:30:34 to 15:08:54 EDT) inside the first run and none inside the second. In real wall time the first run exceeds the 5,965.871 s one-run budget and the pair (12,228.222 s) exceeds the 11,931.741 s pair budget; the awake compute time is inside both. Peak sampled summed worker RSS was 7,282.484 and 7,408.266 MiB and peak swap 1,776.75 and 1,664.75 MiB (WP9 report). None of the other WP9 runs overlapped a sleep interval. Item 70's pair supersedes this pair for the predicate.

The I4 pair that carries the partial-delivery predicate, evaluated at `119d533` and executed at `bc40f25` with the same `code_hash` (runs `20260915T012132.414034Z-0d0a9a8c` and `20260915T020223.783176Z-0d0a9a8c`), used twelve workers on AC power under the I4 client's `caffeinate -ims` assertion; the runner's acceptance-file caffeinate default does not engage through the MCP server. Manifest awake walls are 2444.074 s and 2145.063 s; real walls are 2444.108 s and 2145.038 s. Each is below the 5965.871 s one-run budget. The pair is 4589.137 s awake and 4589.146 s real, below the 11931.741 s replay-pair budget. Awake and real differ by less than 0.002 percent. Peak swap used was 2357.62 MiB and 1535.88 MiB. `cmp` found 423 of 426 files byte-identical; only `log.txt`, `manifest.json` and `status.json` differ.

The 27-setting, three-seed 3.9 sensitivity grid completed sequentially at four workers per setting in **22,372.351 wall s**, below the B2-derived **29,035.266 s** budget and the 22,480.983 s forecast from the three-seed base dose series. Each isolated setting returned `validate_run=[]`; there was no two-worker fallback. Mean setting wall time was 828.606 s (range 816.444–832.889 s). Across the 27 five-second resource logs, peak summed worker RSS was 8,814.188 MiB and peak swap used was 1,896.75 MiB. Every start met the amended precondition: no other engine process, swap used at most 1,896.75 MiB, and at least 76% free by `memory_pressure`.

## B-mech (WP24, SPEC-P2 6.5)

B-mech measures ρ_mech on the Mac, one engine, as `scripts/bench.py --mech sfa|std|cbi`.
Each workload (W1 rest probe and W2 feed-forward probe) runs with the mechanism off, at the grid's weakest setting, and at its strongest setting. Each setting gets one cold build, then three warm repeats.

Measured 2026-09-17 UTC on this Mac, `lif+sfa`, record `validation/records/p2/bench-mech-sfa.json`. Wall 5,074 s. ρ_mech **1.486**. The largest ratio is W2 weak / W2 off.

| Tag | engine_model | ρ_mech | Record |
|---|---|---:|---|
| sfa | `lif+sfa` | 1.486 | `validation/records/p2/bench-mech-sfa.json` |
| std | `lif+std` | 1.346 | `validation/records/p2/bench-mech-std.json` |
| cbi | `lif+cbi` | 1.234 | `validation/records/p2/bench-mech-cbi.json` |

Median warm wall per brain s (`lif+sfa`):

| Workload | off | weak | strong |
|---|---:|---:|---:|
| W1 (12 brain s) | 17.582 | 25.292 | 23.290 |
| W2 (10 brain s) | 11.940 | 17.747 | 16.677 |

Peak `phys_footprint` 2,477 MiB (W1 strong). Spike counts were identical across the four repeats of each setting.

Measured 2026-09-17 UTC on this Mac, `lif+std`, record `validation/records/p2/bench-mech-std.json`. Wall 4,787 s. ρ_mech **1.346**. The largest ratio is W2 weak / W2 off.

Median warm wall per brain s (`lif+std`):

| Workload | off | weak | strong |
|---|---:|---:|---:|
| W1 (12 brain s) | 19.332 | 23.461 | 21.528 |
| W2 (10 brain s) | 11.032 | 14.849 | 14.659 |

Peak `phys_footprint` 2,513 MiB (W1 strong). Spike counts were identical across the four repeats of each setting.

Measured 2026-09-17 UTC on this Mac, `lif+cbi`, record `validation/records/p2/bench-mech-cbi.json`. Wall 4,365 s. ρ_mech **1.234**. The largest ratio is W2 strong / W2 off. Section 6.5 uses this Mac ratio to size Camber jobs; that is a known bias for `rk4`.

Median warm wall per brain s (`lif+cbi`):

| Workload | off | weak | strong |
|---|---:|---:|---:|
| W1 (12 brain s) | 17.809 | 20.960 | 19.726 |
| W2 (10 brain s) | 10.866 | 13.373 | 13.405 |

Peak `phys_footprint` 2,503 MiB (W2 weak). Spike counts were identical across the four repeats of each setting.
