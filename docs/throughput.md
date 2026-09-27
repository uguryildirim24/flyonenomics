# Throughput (WP11, SPEC item 69)

Lane w11 measured one v783 worker after `build()`/`store("initial")` on 2026-09-14, then cut copies that do not change results, added a machine-wide engine budget, bound new validation entries on a content hash, and ran independent validation entries in parallel.

## What changed

- Build-time pandas frames are deleted as soon as Brian2 holds `i`, `j`, and `w`. Connectome arrays are cached as memmaps under `$FLYONENOMICS_CACHE_DIR/connectome-arrays/` so every worker maps one copy. `engine._base_w_mv` is that memmap (read-only float64, 121 MB) instead of a private numpy copy. A cache miss reads `Connectivity_783.parquet` only in a short-lived child (`python -m flyonenomics.connectome_arrays`). That child maps about 1.9 GB of IOAccelerator (Metal) memory; it exits before the worker builds. Workers never call `pandas.read_parquet` on the connectome.
- Synapse index dtypes stay int32; synapse weights stay float64. Narrower weight dtypes would change results.
- The parent spills the registry snapshot (roots, populations, W, M, receptors) to `$FLYONENOMICS_CACHE_DIR/registry-share/<version>-<content hash>/` and workers memory-map it. The key hashes every array and record written (roots, populations, compartments, provenance, W, M, receptors), so a changed population, compartment, receptor or annotation input gets a new directory (review r12). Spawn no longer pickles a private copy of those arrays into each child.
- `Network.store("initial")` no longer keeps a second RAM copy of synapse state. Snapshots live under `$FLYONENOMICS_CACHE_DIR/engine-store/<pid>/`. Static synapse indices (`i`, `j`, `_synaptic_pre`, `_synaptic_post`) are omitted. Synapse weights go to a sidecar npy, not the pickle. Restore reads both files. An engine deletes its files when it is collected, a process removes its directory at exit, and the first store in a process removes directories of pids that no longer exist (review r12; 15 GB in 73 directories had built up). Fork-after-build stays off.
- Engine workers do not import pandas or pyarrow until the first `write_table`. They load the registry share with local types so they never import the registry package. The 16 KB IOAccelerator line on the one-process probe is the probe script scanning for pandas frames.
- `orchestrator/budget.py` holds a lock file under the cache dir. `run_experiment.py --workers auto` and an omitted `--workers` ask the budget. An explicit integer still wins, capped by physical cores minus two. `orchestrator.n_workers` in Params is unchanged (item 63).
- New identity blocks carry `code_hash` (analysis tree) and `run_code_hash` (the engine execution the entry analyses, item 73). Live runs set them equal. Level-3 copies `identity.code_hash` from the analysed manifest. Empty `run_code_hash` keeps the Phase 1 gap. An identity without `code_hash` keeps the Phase 1 `code_commit` rule.
- `scripts/run_validation.py --workers N|auto` runs independent entries concurrently. Default remains serial.

## One-worker footprint after `build()`

v783, 138,639 neurons, 15,091,983 synapses. Command: `uv run python scripts/bench.py --footprint-probe`.

| Item | Before (bytes) | After (bytes) | Notes |
|---|---:|---:|---|
| `syn.i` | 60,367,932 int32 | same | already the narrowest Brian2 index dtype |
| `syn.j` | 60,367,932 int32 | same | |
| `syn.w` | 120,735,864 float64 | same | must stay float64 for bit-identical weights |
| `engine._base_w_mv` | 120,735,864 owned float64 | 120,735,864 memmap | `owndata` false, shared file |
| pandas `df_comp`/`df_con` after build | 0 (already gone) | 0 | peak during first parquet load is now a one-time cache fill |
| tracemalloc current / peak | 472 / 634 MiB | 13 / 414 MiB | stored copy is a file, not RAM |
| `footprint` phys_footprint | 3,050 MB (peak 3,464 MB) | 789 MB (peak 789 MB) | parquet isolated; store file-backed |
| RSS (`ps`) | 891 MiB | 943 MiB | footprint is the comparable figure |
| mapped file (connectome cache) | 80 KB | 115 MB | shared across workers |
| IOAccelerator | 1,937 MB | 16 KB | probe process only; workers stay clear until parquet write |

The 12-worker memory target (12 × per-worker plus 8 GB left in 24 GB) is met on the 789 MB probe: 12 × 789 MB + 8 GiB is 17.3 GB. Remaining per-worker mass is live Brian2 synapse arrays (MALLOC_LARGE 633 MB). The budget records 790 MB from this probe. Auto size during the scaling run was 2 because the vm_stat free plus reclaimable sum, minus the 8 GiB reserve, only covered two footprints; explicit 4, 8, and 12 still ran. Review r12 changed the memory term (below). In a real 12-worker run, `footprint` phys_footprint peaked at 841 MiB per worker (sum 8,644 MiB); in a 4-worker two-arm run one worker peaked at 953 MiB, so live workers sit 7 to 20 percent above the one-process probe. Live workers also map 132 MB of IOAccelerator (about 38 MB dirty) once pyarrow writes a table, against 1,937 MB before the parquet cut.

## Budget rule

Slots live in `$FLYONENOMICS_CACHE_DIR/engine-budget/slots.json` behind `slots.lock`. Holders are keyed `pid:token`; dead pids are pruned. Available memory is `hw.memsize × kern.memorystatus_level / 100`, the kernel figure `memory_pressure` prints as free percentage; it counts file cache and compressible pages that vm_stat's free, speculative, inactive and purgeable pages leave out (idle Mac at 72 percent: 17.3 GiB against 8.7 GiB by vm_stat). Auto count = min(physical CPUs − 2 − slots already held, floor((available − 8 GiB) / measured footprint)). Held slots are not subtracted from the memory term, because running workers' pages are already missing from available memory. `lease_workers` sizes and registers a lease under one lock hold, so two auto commands cannot take the same slots. Swap used above 4,000 MiB yields zero auto slots. Explicit `--workers N` still starts N workers (capped by cores − 2 and the job count) and registers them so other auto commands see the load.

## Binding

`code_hash` is `git:` plus a sha256 over the git blob ids of `src/`, `data/`, `scripts/` and `uv.lock`: the HEAD blobs on a clean tree, the working-tree blobs (tracked and untracked, ignores honoured) on a dirty one, so committing the same bytes keeps the hash. Fixtures are bound by `fixture_hash`, not by `code_hash`, so the runner and every entry compute the same value (review r12). New entries bind on `code_hash`. A docs-only commit leaves a new entry valid. A one-byte `src/` change stales it. A Phase 1 identity block with empty `code_hash` still stales on a different `code_commit`. Canonical fixture bytes are still compared; a fixture-only change reports the fixture reason first.

## Parallel validation

Subset that runs in minutes: `0.9,registry.inventory,registry.labels,registry.precedence` (no whole-brain engine). Serial and `--workers 2` wrote identical `status.json` after stripping `date` and `identity.date`/`identity.machine`. All four passed, class canonical, zero infrastructure errors. The r9 exit rule is unchanged: development failures print and do not fail the command.

## Scaling and invariance

Sugar-reflex at 1091114 versus 71f4c6b, two workers each, same seeds: 64 parquet tables Arrow-equal, five `metrics.json` files byte-equal, `validate_run` empty on both.

Four workers versus eight, same sugar-reflex protocol with seeds 1–4 (eight jobs so eight workers actually spawn): 128 parquet tables Arrow-equal, metrics byte-equal, `validate_run` empty. Four workers 275 s; eight workers 150 s. Files `.reports/WP11-invariance.json` and `.reports/WP11-invariance-4vs8.json`.

`scripts/bench.py --footprint` on a 1-arm 12-seed sugar-reflex derivative. Swap used stayed 1,624.75 MiB. Budget maximum at the start of the run was 2.

| Workers | Wall s | Peak worker RSS MiB | Per-worker RSS MiB |
|---:|---:|---:|---:|
| 2 (budget max) | 646 | 2,081 | 1,041 |
| 4 | 379 | 4,117 | 1,029 |
| 8 | 268 | 7,477 | 935 |
| 12 | 172 | 7,622 | 635 |

RSS is `ps` sum over live worker PIDs. The 12-worker per-worker RSS is lower because not every PID is in the sample at the RSS peak; `footprint` phys_footprint of 789 MB is the comparable one-worker figure. File `.reports/WP11-footprint-scaling.json`.

## Cost

One 12-seed one-arm sugar-reflex wall is 172 s at 12 workers versus 379 s at 4 workers (2.2×). WP9's serial validation pass was 6,150 s; independent entries can now overlap under `--workers N`. WP9's 27-setting grid was 22,372 s at four workers, one setting at a time. The same 12-seed one-arm shape at 12 workers is 172 s, so 27 settings one after another would be about 4,640 s. The full 49-entry validation pass was not rerun here.
