# Male fly virtual pharmacology bench — paper

Preprint by Hasan "Rolf" Yildirim; not peer reviewed. It covers the dopamine study and follow-up, transmitter knockout tour, courtship pathway, GABA dose curve and rescue, virtual body playback and GPU engine replication. The PDF is generated, not committed. Numerical source lines are in `paper/fact-check.md`.

## One-command paper build

From the repository root, with `uv`, Tectonic and system Cairo installed:

```sh
uv run --locked --script paper/build.py
```

The default build reads the reviewed pilot and confirmation records already on main. It does not run the simulator. A test-only synthetic confirmation option exists for the inherited paper fixtures; its visibly labelled output is not publishable.

Output: `paper/build/manuscript.pdf` and `paper/build/supplement.pdf`. The build fills dopamine fields from the committed records, converts the existing GABA curves to PDF, and includes the existing static anatomy, knockout and courtship panels. It emits a source-hash receipt (including the supplement source) in the ignored build folder. The pilot record is SHA-256 bound; the filler checks the frozen result shapes, but cannot certify biological validity or human review. `paper/figure-fields.md` maps current figure sources. CairoSVG is locked in `build.py.lock`; TeX bundles/fonts can change PDF bytes on different machines.

## Provenance and one command per result

Frozen design first committed at `892cf6f`; selected pair frozen before the
5b outcome run. Male substrate `rest:ed9b0a469d7a6b77`; master seed
`20260912`, bootstrap seed `14620260922`. Calibration seeds **101–110**;
experimental seeds **201–210**. Execution source
`f28779b2099018f7188de8c7f73234c0c53b828f`, 5b plan SHA-256
`dc1fb1df32b795303a16a931673cabdbf570d7ef0b446542808e8c5e37835b29`,
pair SHA-256
`b941a440714244811e9ce305a45e678d5f9e5ea25a4a8f2ed638c0f630eff4dc`,
calibration plan SHA-256
`c40623ac8b8e099f55acd2b0a8899e65a089dfb795bdc2c5ecbdb29b8207d944`.
The primary JSON SHA-256 is
`47c6fc6e9ef83b13bdacc3af1b89b96f6b3b8d6f25c0bd1dd577d42326c0657e`;
per-file raw hashes are in the committed results and audit records, not inferred
from the paper. For all commands below use the recorded analysis environment,
bound model tables/cache and retained raw files. Output paths can be changed
without changing analysis; none of these commands is needed to build the PDF.

One command to recompute **both primaries and the affine control** from raw
arrays (recorded in `adhd-study-analysis-execution.json`):

```sh
.venv/bin/python scripts/adhd_study.py analyse --raw camber-runs/adhd-study/5b-02 --calibration camber-runs/adhd-study/5a-01 --pair validation/records/p2/adhd-study-pair.json --out camber-runs/adhd-study/5b-02-results.json
```

One command for **5a calibration description**:

```sh
.venv/bin/python scripts/adhd_describe.py 5a --raw camber-runs/adhd-study/5a-01 --plan validation/records/p2/adhd-study-calibration-plan.json --pair validation/records/p2/adhd-study-pair.json --out camber-runs/adhd-study/5b-02-figures --record camber-runs/adhd-study/5a-01-descriptive.json
```

One command for **5b whole-test curves, chemical/input audits and other
secondaries**:

```sh
.venv/bin/python scripts/adhd_describe.py 5b --raw camber-runs/adhd-study/5b-02 --calibration camber-runs/adhd-study/5a-01 --pair validation/records/p2/adhd-study-pair.json --result camber-runs/adhd-study/5b-02-results.json --out camber-runs/adhd-study/5b-02-figures --record camber-runs/adhd-study/5b-02-descriptive.json
```

The result JSON, `adhd-study-secondaries.json`, `adhd-study-5a-descriptive.json`,
`adhd-study-5b-descriptive.json`, `adhd-study-per-seed.csv`,
`adhd-study-5b-audit.json`, `adhd-study-input-repair.json` and
`adhd-study-analysis-execution.json` are under `validation/records/p2/`.
Raw `5a-01` and `5b-02` archives are ignored under local
`camber-runs/adhd-study/` and kept on the project's compute machine.
Raw run arrays are not in this repository and are available from the author on request. The exact 5b-02
run passed remote/local audits. d-0023's 101/102 calibration NPZ replay was
byte-identical but failed its RNG audit; d-0025 retained the old calibration
with unchanged per-arm law and repaired 5b input plumbing before outcomes.
Seeds 103–110 were not replayed. All 60 5b-01 partial arms were void.

Agents assisted design, implementation, independent computational review and
writing, not independent human replication. No unsupported manual
citation/code/raw audit is claimed.
