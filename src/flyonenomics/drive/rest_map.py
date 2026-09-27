"""WP17 development rest screen and SPEC-P2 2.6 decision rule.

Pure decisions import no engine. Rates are Hz, weights/thresholds mV and
windows seconds. Evaluation rows retain their execution provenance.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Iterable

from flyonenomics.io import read_bytes, read_text, read_json, read_parquet

ROOT = Path(__file__).resolve().parents[3]
SCALES = (1, 2, 3, 4, 6, 8)
WEIGHTS = tuple(round(0.70 + 0.05 * i, 2) for i in range(19))
SEEDS = (1, 2, 3)
LONG_SEEDS = tuple(range(1, 11))
CAP = 10.0
TARGETS = {"DAN": 5.0, "ER": 2.0, "KC": 0.1, "ascending": 1.0,
           "central": 1.0, "descending": 1.0, "endocrine": 1.0,
           "motor": 0.5, "optic": 1.0, "visual_centrifugal": 1.0,
           "visual_projection": 1.0}


@dataclass(frozen=True)
class Setting:
    """One scale/variance setting, before weight selection. Units: ratios, mV, inputs."""
    g_gaba: float
    g_glu: float
    sigma_th: float = 0.0
    optic_exemption: bool = False
    n_bg: int = 100
    g_gaba_kc: float = 1.0

    def __post_init__(self) -> None:
        if (not all(math.isfinite(x) for x in (self.g_gaba, self.g_glu, self.sigma_th, self.g_gaba_kc))
                or min(self.g_gaba, self.g_glu) <= 0 or self.g_gaba_kc < 1 or self.sigma_th < 0
                or self.n_bg not in (25, 100, 400)):
            raise ValueError("invalid rest setting")

    @property
    def weights(self) -> tuple[float, ...]:
        return tuple(round(w * 100 / self.n_bg, 8) for w in WEIGHTS)


def number(value: Any) -> float | None:
    """Return finite nonnegative metric or None; units inherited."""
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) and result >= 0 else None


def violation(value: Any, lower: float | None = None, upper: float | None = None,
              *, floor: float | None = None) -> float:
    """Capped logarithmic violation; missing/undefined metric contributes ten."""
    x = number(value)
    if x is None:
        return CAP
    if floor is not None:
        x = max(floor, x)
    low = 0.0 if lower is None else (CAP if x == 0 else math.log(lower / x))
    high = 0.0 if upper is None or x == 0 else math.log(x / upper)
    return min(CAP, max(0.0, low, high))


def objective(rates: dict[str, Any], targets: dict[str, float] = TARGETS) -> float:
    """J on seed-mean clamped candidate-weight group rates; missing rates floor at .01 Hz."""
    return sum(math.log(max(number(rates.get(g)) or 0.0, .01) / target) ** 2
               for g, target in targets.items())


def order_key(candidate: dict[str, Any]) -> tuple:
    """SPEC-P2 total order on finite candidate summaries; units as in section 2.6."""
    setting = Setting(**{k: candidate.get(k, v) for k, v in
                        asdict(Setting(candidate["g_gaba"], candidate["g_glu"])).items()})
    s, j, w = (number(candidate.get(k)) for k in ("S", "J", "w_bg"))
    if s is None or j is None or w is None:
        raise ValueError("order key needs finite S, J and w_bg")
    return (s, math.floor(j / .25), abs(math.log(setting.g_gaba)) + abs(math.log(setting.g_glu)),
            setting.g_gaba, setting.g_glu, setting.sigma_th, setting.optic_exemption, setting.n_bg, w)


def _mean(values: Iterable[Any]) -> float | None:
    values = [number(v) for v in values]
    return sum(values) / len(values) if values and None not in values else None


def _max_h_max(*values: Any) -> float | None:
    """Largest recorded h_max, or None when every probe is not lif+cbi."""
    present = [float(v) for v in values if v is not None]
    return max(present) if present else None


def _cbi_row_computable(row: dict, *, dt_ms: float | None = None) -> bool:
    """False when this evaluation is cbi-stiff (SPEC-P2 2.2.4). Missing h_max is computable."""
    h = row.get("h_max")
    if h is None:
        return True
    from flyonenomics.drive.rest_tier3 import cbi_stiff
    return not cbi_stiff(float(h), dt_ms=dt_ms)


def screen_candidate(setting: Setting, w_bg: float, rows: list[dict], *, dt_ms: float | None = None) -> dict:
    """Evaluate an adjacent pair and the next point; three distinct seeds each.

    Rows carry w_bg, seed, F, b, stability_ratio, rates_hz. Missing rows fail,
    duplicate rows raise (silently pooling a repeated seed would bias the screen).
    A cbi-stiff row's metrics count as not computable (score CAP), not as a rest failure.
    """
    index = setting.weights.index(w_bg)
    if index + 2 >= len(setting.weights):
        raise ValueError("candidate needs two adjacent weights and a next-grid point")
    weights = setting.weights[index:index + 3]
    lookup = {}
    for row in rows:
        key = (round(float(row["w_bg"]), 8), int(row["seed"]))
        if key in lookup:
            raise ValueError(f"duplicate evaluation {key}")
        lookup[key] = row
    points = [[lookup.get((w, seed), {}) for seed in SEEDS] for w in weights]

    def field_of(row: dict, field: str) -> float | None:
        return None if not _cbi_row_computable(row, dt_ms=dt_ms) else number(row.get(field))

    def rate_of(row: dict, group: str) -> float | None:
        return None if not _cbi_row_computable(row, dt_ms=dt_ms) else number(row.get("rates_hz", {}).get(group))

    means = [{g: _mean(rate_of(r, g) for r in point) for g in TARGETS}
             for point in points]
    violations: dict[str, float] = {}
    checks: dict[str, bool] = {}
    for field, lo, hi, strict in (("F", None, 3, True), ("b", None, .05, True),
                                   ("stability_ratio", .5, 2, False)):
        vals = [field_of(r, field) for p in points[:2] for r in p]
        violations[field] = max(violation(v, lo, hi) for v in vals)
        checks[field] = all(v is not None and (lo is None or v >= lo)
                            and (v < hi if strict else v <= hi) for v in vals)
    for g, lo, hi in (("central", .5, 8), ("DAN", .5, 10), ("KC", None, 2)):
        vals = [p[g] for p in means[:2]]
        violations[g] = max(violation(v, lo, hi, floor=.01) for v in vals)
        checks[g] = all(v is not None and (lo is None or v >= lo) and v <= hi for v in vals)
    grades = []
    grade_ok = []
    for i in range(3):
        nxt = rate_of(points[2][i], "central")
        for p in points[:2]:
            c = rate_of(p[i], "central")
            grades.append(CAP if nxt is None or c is None else
                          violation(max(nxt, .01) / max(c, .01), upper=3))
            grade_ok.append(nxt is not None and c is not None and nxt < 3 * c)
    violations["gradedness"] = max(grades)
    checks["gradedness"] = all(grade_ok)
    stiff = any(not _cbi_row_computable(r, dt_ms=dt_ms) for p in points for r in p)
    flags = ["cbi-stiff"] if stiff else []
    return {**asdict(setting), "w_bg": w_bg, "pair_weights": list(weights[:2]),
            "rates_hz": means[0], "pair_rates_hz": means[:2],
            "violations": violations, "S": sum(violations.values()),
            "J": objective(means[0]), "screen_passed": all(checks.values()),
            "screen_checks": checks, "reflex_passed": None, "long_passed": None,
            "flags": flags}


def reflex_decision(a: list[Any], b: list[Any], candidate: dict[str, list[Any]],
                    bare: dict[str, list[Any]]) -> dict:
    """Reflex (a) six, (b) ten, (c) ten paired sugar-minus-silent values, Hz."""
    def complete(values: list[Any], size: int) -> bool:
        # Reflex differences can be negative; those fail floors, not provenance.
        return len(values) == size and all(isinstance(v, (int, float)) and math.isfinite(v) for v in values)
    a_ok, b_ok = complete(a, 6), complete(b, 10)
    ret = {}
    for mode in ("upstream", "extended"):
        c, r = candidate.get(mode, []), bare.get(mode, [])
        denominator = sum(r) / 10 if complete(r, 10) else 0
        ret[mode] = (sum(c) / 10 / denominator if complete(c, 10) and denominator > 0 else None)
    va = violation(max(1, min(a)), lower=40) if a_ok else CAP
    vb = violation(max(1, sum(b) / 10), lower=50) if b_ok else CAP
    vc = violation(max(.01, ret["extended"]), lower=.5) if ret["extended"] is not None else CAP
    passed = (a_ok and b_ok and min(a) >= 40 and min(b) >= 40 and sum(b) / 10 > 50
              and ret["extended"] is not None and ret["extended"] >= .5
              and complete(candidate.get('upstream', []), 10) and complete(bare.get('upstream', []), 10))
    return {"reflex_passed": bool(passed), "reflex_violations": {"a": va, "b": vb, "c": vc},
            "reflex_violation": va + vb + vc, "retention": ret,
            "a_hz": a, "b_hz": b, "candidate_ff_hz": candidate, "bare_ff_hz": bare}


def long_decision(rows: list[dict], *, dt_ms: float | None = None) -> dict:
    """Ten-seed 30 s check; ignition is explicitly measured, never inferred absent."""
    if len({r["seed"] for r in rows}) != len(rows):
        raise ValueError("duplicate R-long seed")
    stiff = any(not _cbi_row_computable(r, dt_ms=dt_ms) for r in rows)
    passed = (not stiff
              and set(r["seed"] for r in rows) == set(LONG_SEEDS)
              and all(number(r.get("F")) is not None and r["F"] < 3
                      and r.get("ignited") is False
                      and number(r.get("stability_ratio")) is not None
                      and .5 <= r["stability_ratio"] <= 2 for r in rows))
    return {"long_passed": passed, "long_rows": rows,
            "flags": ["cbi-stiff"] if stiff else []}


def attach_reflex(candidate: dict, result: dict) -> dict:
    """Combine screen score with measured reflex violations without double counting."""
    return {**candidate, **result, "S": sum(candidate["violations"].values()) + result["reflex_violation"]}


def capped_candidates(candidates: list[dict], cap: int = 20) -> tuple[list[dict], list[dict]]:
    """Select R2 admissions on the pre-reflex order; preserve all cap exclusions."""
    ordered = sorted((r for r in candidates if r["screen_passed"]), key=order_key)
    return ordered[:cap], [{**r, "status": "not tested (cap)"} for r in ordered[cap:]]


def _best_pairs(candidates: list[dict], key=order_key) -> list[dict]:
    out, seen = [], set()
    for row in sorted(candidates, key=key):
        pair = row["g_gaba"], row["g_glu"]
        if pair not in seen:
            seen.add(pair)
            out.append(row)
    return out


def decide(candidates: list[dict], *, tier: int = 1, complete: bool = True) -> dict:
    """Rank completed stages or select tier 2 / escalation; pending work is not failure."""
    ranked = sorted((r for r in candidates if r["screen_passed"]
                     and r.get("reflex_passed") is True and r.get("long_passed") is True), key=order_key)
    result = {"ranked": ranked, "shortlist": ranked[:3], "closest": sorted(candidates, key=order_key)}
    if not complete:
        return {**result, "status": "pending"}
    if ranked:
        return {**result, "status": "ranked"}
    if tier == 2:
        return {**result, "status": "P2-partial-B", "reason": "tier 2 exhausted"}
    reflex = [r for r in candidates if r.get("reflex_passed") is True]
    screen = [r for r in candidates if r["screen_passed"]]
    if reflex:
        selected, reason = _best_pairs(reflex)[:3], "R-long"
    elif screen:
        selected = _best_pairs(screen, key=lambda r: (r.get("reflex_violation", 3 * CAP), order_key(r)))[:3]
        reason = "R-reflex"
    else:
        selected, reason = _best_pairs(candidates)[:3], "R-screen"
    return {**result, "status": "tier2", "trigger": reason,
            "tier2_pairs": [[r["g_gaba"], r["g_glu"]] for r in selected]}


def tier2_settings(pairs: list[list[float]]) -> list[Setting]:
    """Seventeen variants per selected pair, with mean-preserving weight grids."""
    return [Setting(a, b, sigma, optic, n) for a, b in pairs
            for sigma in (0., 1., 2.) for optic in (False, True) for n in (25, 100, 400)
            if (sigma, optic, n) != (0., False, 100)]


def select_r3(ranked: list[dict], results: dict[str, bool], elapsed_hours: float) -> dict:
    """R4: first R3 passer among at most six, or first rank at exhaustion/12 h."""
    if not ranked:
        return {"status": "P2-partial-B", "reason": "ranked list exhausted"}
    screened = ranked[:6]
    for row in screened:
        state = results.get(candidate_id(row))
        if state is True:
            return {"status": "selected", "candidate": row, "reason": "R3 passed"}
    if elapsed_hours >= 12 or all(candidate_id(r) in results for r in screened):
        return {"status": "selected", "candidate": ranked[0], "reason": "R3 timeout" if elapsed_hours >= 12 else "R3 exhausted"}
    return {"status": "waiting", "reason": "R3 pending"}


def calibration_next(ranked: list[dict], failed_ids: list[str], current: dict,
                     table: str, q_passed: bool) -> dict:
    """T -> C -> next rank, at most three failed candidates; section 2.5."""
    if q_passed:
        return {"status": "passed", "candidate": current, "table": table}
    if table == "T":
        return {"status": "retry", "candidate": current, "table": "C"}
    failed = set(failed_ids) | {candidate_id(current)}
    remaining = [r for r in ranked if candidate_id(r) not in failed]
    if len(failed) >= 3 or not remaining:
        return {"status": "P2-partial-B", "reason": "K1r/Q-rest fall-through exhausted"}
    return {"status": "next", "candidate": remaining[0]}


def candidate_id(row: dict) -> str:
    """Stable parameter identity, independent of measured rank."""
    return '-'.join(str(row[k]) for k in ("g_gaba", "g_glu", "sigma_th", "optic_exemption", "n_bg", "w_bg"))


def select_map_pairs(candidates: list[dict], pass_pairs: list[tuple] | None = None) -> list[list[float]]:
    """Map passers plus six closest nonpassing pairs and their axial grid neighbours."""
    best = _best_pairs(candidates)
    passed = set(pass_pairs if pass_pairs is not None else
                 [(r["g_gaba"], r["g_glu"]) for r in candidates if r["screen_passed"]])
    misses = [r for r in best if (r["g_gaba"], r["g_glu"]) not in passed][:6]
    allowed = passed | {(r["g_gaba"], r["g_glu"]) for r in misses}
    for a, b in list(allowed):
        for axis, value in enumerate((a, b)):
            i = SCALES.index(value)
            for j in (i - 1, i + 1):
                if 0 <= j < len(SCALES):
                    allowed.add((SCALES[j], b) if axis == 0 else (a, SCALES[j]))
    return [[r["g_gaba"], r["g_glu"]] for r in best
            if (r["g_gaba"], r["g_glu"]) in allowed][:12]


def execution_identity(job_id: str) -> dict:
    """Capture clean launch commit and content scope, plus platform and data digests."""
    import subprocess
    from flyonenomics.validation.binding import code_scope_hash, platform_id
    dirty = subprocess.check_output(['git', 'status', '--porcelain', '--untracked-files=no'], cwd=ROOT, text=True)
    if dirty.strip():
        raise RuntimeError('commit tracked changes before engine execution')
    return {'job_id': str(job_id), 'commit': subprocess.check_output(
        ['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'code_scope': code_scope_hash(ROOT), 'platform': platform_id(), 'class': 'development',
        'inputs': {p: hashlib.sha256(read_bytes(ROOT / p)).hexdigest() for p in
                   ('data/params-v0.2.yaml', 'data/transmitters-v0.2.yaml',
                    'data/dopamine-v0.1.yaml', 'data/populations-v0.1.yaml')}}


def _write_json(path: Path, value: Any) -> None:
    from flyonenomics.store.results import atomic_json
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_json(path, value)


def map_plan(path: Path) -> dict:
    """Import model-sign map once; fix old last/first ratio to the specified first/last.

    Map-only absent target rates floor to .01 for J, explicitly enumerated in output.
    The historical item-43 passers seed the set; all new ranking uses section 2.6.
    """
    frame = read_parquet(path).to_pandas()
    if 'sign' in frame:
        frame = frame[frame['sign'] == 'model']
    candidates = []
    for (a, b), block in frame.groupby(['g_gaba', 'g_glu']):
        setting = Setting(float(a), float(b))
        converted = []
        for r in block.to_dict('records'):
            last = number(r['last_central_hz'])
            first = number(r['first_central_hz'])
            converted.append({'w_bg': round(r['weight_mv'], 8), 'seed': r['seed'],
                              'F': number(r['F']), 'b': number(r['max_bin_fraction']),
                              'stability_ratio': first / last if first is not None and last else None,
                              'rates_hz': {g: number(r.get(g + '_hz')) for g in TARGETS}})
        candidates.extend(screen_candidate(setting, w, converted) for w in setting.weights[:-2])
    historical_passers = [(3., 3.), (3., 4.), (3., 6.), (3., 8.)]
    pairs = select_map_pairs(candidates, historical_passers)
    return {'class': 'development', 'tier': 1, 'map_sha256': hashlib.sha256(read_bytes(path)).hexdigest(),
            'source_jobs': sorted(set(str(v) for v in frame.job_id)),
            'source_commit': sorted(set(str(v) for v in frame.commit)),
            'source_code_scope': sorted(set(str(v) for v in frame.code_scope)),
            'source_platform': sorted(set(str(v) for v in frame.platform)),
            'map_missing_J_groups': [g for g in TARGETS if g + '_hz' not in frame],
            'historical_pass_pairs': historical_passers, 'pairs': pairs,
            'settings': [asdict(Setting(*p)) for p in pairs],
            'map_best_candidates': _best_pairs(candidates), 'seeds': list(SEEDS),
            'evaluations': len(pairs) * 19 * 3, 'brain_s': len(pairs) * 19 * 3 * 12}


def _build_engine(setting: Setting, *, mode: str = 'dark', bare: bool = False,
                  feedforward: bool = False, mechanisms=None,
                  mechanisms_section=None, dt_ms: float | None = None,
                  clamp: bool | None = None, trace_idx=None) -> dict:
    """One engine per spawned child, all immutable substrate arrays before store.

    clamp None keeps the historic rule (clamped when background is on).
    trace_idx None keeps the historic MN9-on-lif+sfa monitor.
    dt_ms None keeps params-v0.2 ``lif.dt``; a float overrides it for WP28.
    """
    import numpy as np
    from flyonenomics.drive.background import group_indices
    from flyonenomics.drive.rest import apply_rest_substrate
    from flyonenomics.engine import BrianEngine, InputTopology, UpstreamBank
    from flyonenomics.engine.models import resolve_engine_model
    from flyonenomics.io import read_yaml
    from flyonenomics.neuromod.state import Neuromod
    from flyonenomics.orchestrator.seeds import brian_seed
    from flyonenomics.registry import build_registry
    from flyonenomics.types import LayerFlags, load_params
    from flyonenomics.validation.level0 import connectome
    params = load_params(ROOT / 'data/params-v0.2.yaml')
    params.data['bg']['n_bg']['value'] = setting.n_bg
    if dt_ms is not None:
        params.data['lif']['dt']['value'] = float(dt_ms)
    registry = build_registry('783')
    sugar = registry.population('sugar_GRN_R').idx
    if trace_idx is not None:
        trace = np.asarray(trace_idx, dtype=np.int32)
    elif resolve_engine_model(mechanisms) == 'lif+sfa':
        trace = np.asarray(registry.population('MN9').idx, dtype=np.int32)
    else:
        trace = np.zeros(0, dtype=np.int32)
    topology = InputTopology(background=not feedforward,
        upstream_banks=[UpstreamBank(sugar, 150.)] if mode == 'upstream' else [],
        extended_idx=np.sort(sugar) if mode == 'extended' else np.zeros(0, dtype=np.int32),
        trace_idx=trace)
    engine = BrianEngine()
    engine.seed(brian_seed(20260912, 0, 0))
    engine.build(connectome('783'), params, topology, mechanisms=mechanisms)
    if bare:
        scale = np.ones(engine.n_syn, dtype=np.float32)
        engine.set_weight_scale(scale)
        base = np.full(engine.n, float(params.get('lif.v_th')))
    else:
        base, scale = apply_rest_substrate(engine, params, {**asdict(setting), 'seed': 20260912,
                                                            'scope': 'brain',
                                                            'mechanisms': mechanisms_section},
                                           thresholds=not feedforward)
    groups = group_indices(registry)
    mod = Neuromod(registry, params, LayerFlags(background=not feedforward),
                   read_yaml(ROOT / 'data/dopamine-v0.1.yaml'), base_v_th=base,
                   schema_version='1.3', drive_groups=groups)
    hold = (not feedforward) if clamp is None else bool(clamp)
    mod.clamp_pools(hold)
    mod.reset_fast()
    composed = mod.compose()
    engine.set_threshold(composed.v_th)
    engine.set_gain(composed.gain)
    engine.compose_refractory()
    if not feedforward:
        engine.set_background(np.zeros(engine.n))
    engine.store('initial')
    return {'engine': engine, 'mod': mod, 'groups': groups, 'registry': registry,
            'params': params, 'sugar': sugar, 'mode': mode, 'feedforward': feedforward,
            'weight_scale': scale}


def _probe(built: dict, weight: float, seed: int, *, seconds: float, edge_s: float = 1.,
           active: bool = False, deadline: float | None = None) -> dict:
    """Restore/seed, settle 2 s, measure; streaming all-neuron 1ms synchrony and rolling ignition."""
    import time
    from collections import deque
    import numpy as np
    from flyonenomics.orchestrator.seeds import brian_seed
    from flyonenomics.validation.artefacts import FanoAccumulator, ignition_detector
    e, mod, groups, params = (built[k] for k in ('engine', 'mod', 'groups', 'params'))
    began = time.monotonic()
    e.restore('initial')
    e.seed(brian_seed(20260912, seed, 0))
    mod.reset_fast()
    comp = mod.compose()
    offset = built.get('v_th_offset')
    if offset is None:
        e.set_threshold(comp.v_th)
    else:
        e.set_threshold(np.asarray(comp.v_th, dtype=np.float64) + np.asarray(offset, dtype=np.float64))
    e.set_gain(comp.gain)
    if not built['feedforward']:
        policy = built.get('bg_policy')
        if policy is None or policy == 'default':
            w = np.full(e.n, weight)
            w[groups['sensory']] = 0.
        else:
            from flyonenomics.drive.rest_nonuniform import background_vector
            w = background_vector(e.n, weight, groups, policy)
        e.set_background(w)
    if built['mode'] == 'upstream':
        e.set_upstream_active(0, active)
    elif built['mode'] == 'extended':
        e.set_input_rates(np.full(len(built['sugar']), 150. if active else 0.))
    chunk_ms = float(params.get('engine.chunk_ms'))
    chunks_second = round(1000 / chunk_ms)
    lab = built.get('lab_sample')
    fano_chunks = pair_chunks = None
    h_max = None
    def step():
        nonlocal h_max
        if deadline is not None and time.monotonic() >= deadline:
            raise TimeoutError('rest task wall cap reached')
        result = e.run_chunk(chunk_ms)
        h_max = _max_h_max(h_max, result.h_max)
        if not mod.clamped:
            mod.on_chunk(result.counts, chunk_ms / 1000)
            c = mod.compose()
            if offset is None:
                e.set_threshold(c.v_th)
            else:
                e.set_threshold(np.asarray(c.v_th, dtype=np.float64) + np.asarray(offset, dtype=np.float64))
            e.set_gain(c.gain)
        return result
    settled_central = 0
    for pos in range(2 * chunks_second):
        r = step()
        if pos >= chunks_second:
            settled_central += int(r.counts[groups['central']].sum())
    settled_hz = settled_central / len(groups['central'])
    counts = np.zeros(e.n, dtype=np.int64)
    fano = FanoAccumulator(e.n, params)
    first = last = 0
    n_chunks, edge_chunks = round(seconds * chunks_second), round(edge_s * chunks_second)
    if lab is not None:
        fano_chunks = np.zeros((len(lab['fano_idx']), n_chunks), dtype=np.int32)
        pair_chunks = np.zeros((len(lab['pair_idx']), n_chunks), dtype=np.int32)
    central_windows = deque()
    rolling = 0
    max_central = 0.
    for pos in range(n_chunks):
        r = step()
        counts += r.counts
        fano.add(r.hist_1ms)
        if fano_chunks is not None:
            fano_chunks[:, pos] = r.counts[lab['fano_idx']]
            pair_chunks[:, pos] = r.counts[lab['pair_idx']]
        c = int(r.counts[groups['central']].sum())
        if pos < edge_chunks:
            first += c
        if pos >= n_chunks - edge_chunks:
            last += c
        central_windows.append(c)
        rolling += c
        if len(central_windows) > chunks_second:
            rolling -= central_windows.popleft()
        if len(central_windows) == chunks_second:
            max_central = max(max_central, rolling / len(groups['central']))
    rates = {g: float(counts[idx].mean() / seconds) for g, idx in groups.items()}
    sync = fano.report()
    row = {'seed': seed, 'w_bg': weight, 'settle_s': 2., 'measure_s': seconds,
            'edge_s': edge_s, 'rates_hz': rates, 'F': sync['F'], 'b': sync['max_bin_fraction'],
            'stability_ratio': first / last if last else None,
            'first_central_hz': first / (len(groups['central']) * edge_s),
            'last_central_hz': last / (len(groups['central']) * edge_s),
            'settled_central_hz': settled_hz, 'max_rolling_central_hz': max_central,
            'ignited': bool(ignition_detector(
                np.asarray([max_central], dtype=float), settled_hz, params)['tripped']),
            'mn9_hz': float(counts[built['registry'].population('MN9').idx].mean() / seconds),
            'pools': 'clamped' if mod.clamped else 'free', 'wall_s': time.monotonic() - began,
            'h_max': h_max}
    if fano_chunks is not None:
        from flyonenomics.drive.rest_nonuniform import lab_measures
        row['lab'] = lab_measures(fano_chunks, pair_chunks, chunk_ms=chunk_ms)
    return row


DIAG_BLOCK_ORDER = ("MN9", "APL", "DAN", "KC", "optic", "central", "rest")
FANO_BINS_MS = (1, 5, 10, 50, 100)
DIAG_WINDOWS = (("early", 2.0, 12.0), ("late", 12.0, 32.0))
DIAG_SECONDS = 32.0
DIAG_SHUFFLE_BLOCK_MS = 100
THRESHOLD_SEED = 20260912
Q_22R_MEDIAN_MIN_HZ = 0.2
Q_22R_MEDIAN_MAX_HZ = 5.0
Q_22R_HIGH_HZ = 50.0
Q_22R_HIGH_FRACTION = 0.01


def _json_safe(value: Any) -> Any:
    """JSON-safe scalars and nested maps. Units: unchanged."""
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if hasattr(value, "item") and getattr(value, "ndim", 1) == 0:
        return _json_safe(value.item())
    return value


def fano_from_counts(counts_1ms) -> float | None:
    """Population Fano of a bin-count series. Units: dimensionless."""
    import numpy as np
    counts = np.asarray(counts_1ms, dtype=np.float64)
    if counts.size == 0:
        return None
    total = float(counts.sum())
    if total <= 0:
        return None
    mean = total / counts.size
    var = float(np.mean(np.square(counts))) - mean * mean
    return max(0.0, var / mean)


def fano_at_bins(counts_1ms, bin_ms: Iterable[int] = FANO_BINS_MS) -> dict[str, float | None]:
    """F at several bin widths. Units: ms in, dimensionless out."""
    import numpy as np
    counts = np.asarray(counts_1ms, dtype=np.int64).ravel()
    out: dict[str, float | None] = {}
    for width in bin_ms:
        w = int(width)
        n = (counts.size // w) * w
        if n == 0 or w < 1:
            out[str(w)] = None
            continue
        coarse = counts[:n].reshape(-1, w).sum(axis=1)
        out[str(w)] = fano_from_counts(coarse)
    return out


def median_rate_22r(rates_hz) -> dict[str, Any]:
    """2.2r all-neuron median rule. Units: Hz. Input shape (n,)."""
    import numpy as np
    rates = np.asarray(rates_hz, dtype=np.float64).ravel()
    if rates.size == 0 or not np.all(np.isfinite(rates)):
        raise ValueError("2.2r needs a finite per-neuron rate vector")
    median = float(np.median(rates))
    high = float(np.mean(rates > Q_22R_HIGH_HZ))
    return {
        "median_hz": median,
        "fraction_above_50_hz": high,
        "passed": bool(Q_22R_MEDIAN_MIN_HZ <= median <= Q_22R_MEDIAN_MAX_HZ and high < Q_22R_HIGH_FRACTION),
        "rule": "2.2r: all-neuron median in [0.2, 5] Hz and <1 percent above 50 Hz",
    }


def covariance_decomposition(
    population_1ms,
    block_1ms: dict[str, Any],
    neuron_counts,
    block_neuron_counts: dict[str, Any],
    n_bins: int,
) -> dict[str, Any]:
    """F = [Σ p_i(1-p_i) + 2 Σ_{i<j} Cov] / Σ p_i split by disjoint blocks."""
    import numpy as np
    pop = np.asarray(population_1ms, dtype=np.float64).ravel()
    totals = np.asarray(neuron_counts, dtype=np.float64).ravel()
    if n_bins <= 0 or pop.size != n_bins:
        raise ValueError("covariance decomposition needs matching 1 ms bins")
    p = totals / n_bins
    independent = float(np.sum(p * (1.0 - p)))
    mean_pop = float(pop.mean())
    var_pop = float(np.mean(np.square(pop))) - mean_pop * mean_pop
    cov_term = var_pop - independent
    fano = (var_pop / mean_pop) if mean_pop > 0 else None
    blocks = {}
    for name, series in block_1ms.items():
        n_b = np.asarray(series, dtype=np.float64).ravel()
        if n_b.size != n_bins:
            raise ValueError(f"block {name} bin count differs from the population series")
        mean_b = float(n_b.mean())
        var_b = float(np.mean(np.square(n_b))) - mean_b * mean_b
        neuron_b = np.asarray(block_neuron_counts[name], dtype=np.float64).ravel()
        p_b = neuron_b / n_bins
        indep_b = float(np.sum(p_b * (1.0 - p_b)))
        blocks[name] = {
            "mean": mean_b,
            "var": var_b,
            "independent": indep_b,
            "within_cov": var_b - indep_b,
        }
    pairs = {}
    names = [name for name in DIAG_BLOCK_ORDER if name in block_1ms]
    names.extend(name for name in block_1ms if name not in names)
    stacked = {name: np.asarray(block_1ms[name], dtype=np.float64).ravel() for name in names}
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            cov = float(np.mean(stacked[a] * stacked[b]) - stacked[a].mean() * stacked[b].mean())
            pairs[f"{a}:{b}"] = cov
    denom = independent + cov_term
    return {
        "F": fano,
        "independent": independent,
        "covariance_term": cov_term,
        "covariance_fraction": (cov_term / denom) if denom else None,
        "blocks": blocks,
        "pairs": pairs,
        "dominant_pair": max(pairs, key=lambda k: abs(pairs[k])) if pairs else None,
    }


def shuffle_block_fano(idx, ms, n_ms: int, *, block_ms: int = DIAG_SHUFFLE_BLOCK_MS,
                       rng=None) -> float | None:
    """F after permuting each neuron's 1 ms bins inside block_ms windows."""
    import numpy as np
    generator = np.random.default_rng(rng)
    idx = np.asarray(idx, dtype=np.int32)
    ms = np.asarray(ms, dtype=np.int64)
    if n_ms <= 0 or block_ms < 1:
        return None
    n_blocks = n_ms // block_ms
    if n_blocks <= 0 or idx.size == 0:
        return fano_from_counts(np.zeros(n_ms, dtype=np.int32))
    keep = (ms >= 0) & (ms < n_blocks * block_ms)
    idx = idx[keep]
    ms = ms[keep]
    shuffled = np.zeros(n_ms, dtype=np.int32)
    block_id = ms // block_ms
    for block in range(n_blocks):
        sel = block_id == block
        neurons = idx[sel]
        local = ms[sel] - block * block_ms
        if neurons.size == 0:
            continue
        order = np.argsort(neurons, kind="mergesort")
        neurons = neurons[order]
        local = local[order]
        starts = np.flatnonzero(np.concatenate(([True], neurons[1:] != neurons[:-1])))
        ends = np.append(starts[1:], neurons.size)
        base = block * block_ms
        for start, stop in zip(starts, ends):
            k = int(stop - start)
            if k <= block_ms:
                new_t = generator.choice(block_ms, size=k, replace=False)
            else:
                new_t = generator.integers(0, block_ms, size=k)
            shuffled[base + new_t] += 1
    remainder = n_ms - n_blocks * block_ms
    if remainder:
        extra = (ms >= n_blocks * block_ms) & (ms < n_ms)
        if extra.any():
            shuffled[ms[extra]] += 1
    return fano_from_counts(shuffled)


def disjoint_diag_blocks(registry) -> dict[str, Any]:
    """Exclusive diagnostic populations. Units: engine indices. Shapes: (size,)."""
    import numpy as np
    from flyonenomics.drive.background import group_indices
    from flyonenomics.substrate.transmitters import annotations_in_engine
    n = int(registry.n)
    assigned = np.zeros(n, dtype=np.uint8)
    blocks: dict[str, Any] = {}
    groups = group_indices(registry)
    frame, _order = annotations_in_engine()
    hemibrain = frame["hemibrain_type"].fillna("").to_numpy(dtype=str)
    apl = np.flatnonzero(hemibrain == "APL").astype(np.int32)

    def take(name: str, idx) -> None:
        idx = np.asarray(idx, dtype=np.int32)
        idx = idx[(idx >= 0) & (idx < n) & (assigned[idx] == 0)]
        assigned[idx] = 1
        blocks[name] = np.ascontiguousarray(idx)

    take("MN9", registry.population("MN9").idx)
    take("APL", apl)
    take("DAN", groups["DAN"])
    take("KC", groups["KC"])
    take("optic", groups["optic"])
    take("central", groups["central"])
    take("rest", np.flatnonzero(assigned == 0))
    if sum(int(v.size) for v in blocks.values()) != n:
        raise ValueError("diagnostic blocks do not partition the engine")
    return blocks


def diag_sample_indices(blocks: dict[str, Any], n: int, *, seed: int = THRESHOLD_SEED) -> dict[str, Any]:
    """Fixed raster sample of 2000 central neurons and 20 voltage neurons."""
    import numpy as np
    from flyonenomics.orchestrator.seeds import stream
    from flyonenomics.types import ANALYSIS
    rng = stream(int(seed), 0, 0, ANALYSIS)
    central = np.asarray(blocks["central"], dtype=np.int32)
    n_sample = min(2000, int(central.size))
    central_sample = np.sort(rng.choice(central, size=n_sample, replace=False).astype(np.int32))
    raster = np.unique(np.concatenate([
        np.asarray(blocks["KC"], dtype=np.int32),
        np.asarray(blocks["APL"], dtype=np.int32),
        np.asarray(blocks["DAN"], dtype=np.int32),
        np.asarray(blocks["MN9"], dtype=np.int32),
        central_sample,
    ]))
    parts = []
    for name, count in (("MN9", 1), ("APL", 2), ("KC", 4), ("DAN", 2), ("central", 11)):
        idx = np.asarray(blocks[name], dtype=np.int32)
        if idx.size == 0:
            continue
        take = min(int(count), int(idx.size))
        parts.append(rng.choice(idx, size=take, replace=False))
    trace = np.unique(np.concatenate(parts)) if parts else np.zeros(0, dtype=np.int32)
    if trace.size < 20:
        remaining = np.setdiff1d(np.arange(int(n), dtype=np.int32), trace)
        need = min(20 - int(trace.size), int(remaining.size))
        if need > 0:
            extra = rng.choice(remaining, size=need, replace=False)
            trace = np.unique(np.concatenate([trace, extra]))
    return {
        "raster_idx": np.ascontiguousarray(raster, dtype=np.int32),
        "central_sample": np.ascontiguousarray(central_sample, dtype=np.int32),
        "trace_idx": np.ascontiguousarray(np.sort(trace[:20]), dtype=np.int32),
    }


def analyse_spike_windows(idx, ms, n: int, *, windows=DIAG_WINDOWS, blocks=None,
                          shuffle_seed: int = 0) -> dict[str, Any]:
    """F, covariance and 2.2r median on named windows. Units: ms, Hz."""
    import numpy as np
    idx = np.asarray(idx, dtype=np.int32)
    ms = np.asarray(ms, dtype=np.int64)
    block_id = np.full(n, -1, dtype=np.int8)
    order = list(blocks or {})
    for i, name in enumerate(order):
        block_id[np.asarray(blocks[name], dtype=np.int32)] = i
    out: dict[str, Any] = {}
    for i_window, (name, start_s, stop_s) in enumerate(windows):
        start = int(round(start_s * 1000))
        stop = int(round(stop_s * 1000))
        n_bins = stop - start
        seconds = n_bins / 1000.0
        sel = (ms >= start) & (ms < stop)
        w_idx = idx[sel]
        w_ms = ms[sel] - start
        pop = np.bincount(w_ms, minlength=n_bins).astype(np.int32) if w_ms.size else np.zeros(n_bins, dtype=np.int32)
        totals = np.bincount(w_idx, minlength=n).astype(np.int64) if w_idx.size else np.zeros(n, dtype=np.int64)
        block_1ms = {}
        block_neuron = {}
        spike_block = block_id[w_idx] if w_idx.size else np.zeros(0, dtype=np.int8)
        for i, bname in enumerate(order):
            bsel = spike_block == i
            b_ms = w_ms[bsel] if w_idx.size else np.zeros(0, dtype=np.int64)
            block_1ms[bname] = (
                np.bincount(b_ms, minlength=n_bins).astype(np.int32) if b_ms.size
                else np.zeros(n_bins, dtype=np.int32)
            )
            members = np.asarray(blocks[bname], dtype=np.int32)
            block_neuron[bname] = totals[members]
        rng = np.random.default_rng(
            np.random.SeedSequence(int(shuffle_seed), spawn_key=(i_window,)),
        )
        out[name] = {
            "start_s": start_s,
            "stop_s": stop_s,
            "F_bins": fano_at_bins(pop),
            "covariance": covariance_decomposition(
                pop, block_1ms, totals, block_neuron, n_bins,
            ),
            "shuffle_F_1ms": shuffle_block_fano(w_idx, w_ms, n_bins, rng=rng),
            "median_22r": median_rate_22r(totals / seconds),
            "mn9_hz": float(totals[np.asarray(blocks["MN9"], dtype=np.int32)].mean() / seconds) if blocks else None,
            "block_means_hz": {
                bname: float(np.asarray(block_neuron[bname], dtype=np.float64).mean() / seconds)
                if np.asarray(blocks[bname]).size else 0.0
                for bname in order
            },
        }
    return out


def _instrumented_probe(built: dict, weight: float, seed: int, *, seconds: float = DIAG_SECONDS,
                        deadline: float | None = None, dest=None,
                        raster_idx=None, blocks=None) -> dict:
    """32 s from startup with diagnostic arrays.

    Scoring fields match `_probe`: 2 s settle, then 10 s, the interval [2, 12).
    """
    import time
    from collections import deque
    import numpy as np
    from flyonenomics.orchestrator.seeds import brian_seed
    from flyonenomics.validation.artefacts import FanoAccumulator
    e, mod, groups, params = (built[k] for k in ('engine', 'mod', 'groups', 'params'))
    began = time.monotonic()
    e.restore('initial')
    e.seed(brian_seed(20260912, seed, 0))
    mod.reset_fast()
    comp = mod.compose()
    offset = built.get('v_th_offset')
    if offset is None:
        e.set_threshold(comp.v_th)
    else:
        e.set_threshold(np.asarray(comp.v_th, dtype=np.float64) + np.asarray(offset, dtype=np.float64))
    e.set_gain(comp.gain)
    if not built['feedforward']:
        policy = built.get('bg_policy')
        if policy is None or policy == 'default':
            w = np.full(e.n, weight)
            w[groups['sensory']] = 0.
        else:
            from flyonenomics.drive.rest_nonuniform import background_vector
            w = background_vector(e.n, weight, groups, policy)
        e.set_background(w)
    if built['mode'] == 'upstream':
        e.set_upstream_active(0, False)
    elif built['mode'] == 'extended':
        e.set_input_rates(np.zeros(len(built['sugar'])))
    chunk_ms = float(params.get('engine.chunk_ms'))
    chunks_second = round(1000 / chunk_ms)
    tick0 = e.tick()
    h_max = None
    def step():
        nonlocal h_max
        if deadline is not None and time.monotonic() >= deadline:
            raise TimeoutError('rest task wall cap reached')
        result = e.run_chunk(chunk_ms)
        h_max = _max_h_max(h_max, result.h_max)
        if not mod.clamped:
            mod.on_chunk(result.counts, chunk_ms / 1000)
            c = mod.compose()
            if offset is None:
                e.set_threshold(c.v_th)
            else:
                e.set_threshold(np.asarray(c.v_th, dtype=np.float64) + np.asarray(offset, dtype=np.float64))
            e.set_gain(c.gain)
        return result
    n_chunks = round(seconds * chunks_second)
    settled_central = 0
    measure_counts = np.zeros(e.n, dtype=np.int64)
    fano = FanoAccumulator(e.n, params)
    first = last = 0
    edge_chunks = chunks_second
    central_windows = deque()
    rolling = 0
    max_central = 0.
    t1_chunks = 10 * chunks_second
    settle_chunks = 2 * chunks_second
    lab = built.get('lab_sample')
    fano_chunks = pair_chunks = None
    if lab is not None:
        fano_chunks = np.zeros((len(lab['fano_idx']), t1_chunks), dtype=np.int32)
        pair_chunks = np.zeros((len(lab['pair_idx']), t1_chunks), dtype=np.int32)
    for pos in range(n_chunks):
        r = step()
        if pos >= chunks_second:
            settled_central += int(r.counts[groups['central']].sum()) if pos < settle_chunks else 0
        if settle_chunks <= pos < settle_chunks + t1_chunks:
            measure_counts += r.counts
            fano.add(r.hist_1ms)
            t1_pos = pos - settle_chunks
            if fano_chunks is not None:
                fano_chunks[:, t1_pos] = r.counts[lab['fano_idx']]
                pair_chunks[:, t1_pos] = r.counts[lab['pair_idx']]
            c = int(r.counts[groups['central']].sum())
            if t1_pos < edge_chunks:
                first += c
            if t1_pos >= t1_chunks - edge_chunks:
                last += c
            central_windows.append(c)
            rolling += c
            if len(central_windows) > chunks_second:
                rolling -= central_windows.popleft()
            if len(central_windows) == chunks_second:
                max_central = max(max_central, rolling / len(groups['central']))
    settled_hz = settled_central / len(groups['central'])
    t1_seconds = 10.0
    rates = {g: float(measure_counts[idx].mean() / t1_seconds) for g, idx in groups.items()}
    sync = fano.report()
    spikes = e.spikes(tick0)
    ticks_per_ms = int(e.ticks_per_ms)
    ms = (np.asarray(spikes.tick, dtype=np.int64) // ticks_per_ms)
    idx = np.asarray(spikes.idx, dtype=np.int32)
    n_ms = int(round(seconds * 1000))
    keep = (ms >= 0) & (ms < n_ms)
    idx, ms = idx[keep], ms[keep]
    used_blocks = blocks or disjoint_diag_blocks(built['registry'])
    analysis = analyse_spike_windows(
        idx, ms, e.n, blocks=used_blocks, shuffle_seed=seed,
    )
    raster = np.asarray(raster_idx if raster_idx is not None else idx[:0], dtype=np.int32)
    raster_keep = np.isin(idx, raster) if raster.size else np.zeros(idx.shape, dtype=bool)
    traces = e.traces(tick0)
    v = np.asarray(traces.v_mv, dtype=np.float64)
    if v.size:
        v_1ms = v[:, ::ticks_per_ms][:, :n_ms]
    else:
        v_1ms = np.zeros((0, n_ms), dtype=np.float64)
    mn9 = np.asarray(used_blocks["MN9"], dtype=np.int32)
    mn9_1ms = np.bincount(ms[np.isin(idx, mn9)], minlength=n_ms).astype(np.int32) if mn9.size else np.zeros(n_ms, dtype=np.int32)
    totals = np.bincount(idx, minlength=e.n).astype(np.int64) if idx.size else np.zeros(e.n, dtype=np.int64)
    block_1ms = {}
    block_ids = np.full(e.n, -1, dtype=np.int8)
    for i, name in enumerate(DIAG_BLOCK_ORDER):
        block_ids[np.asarray(used_blocks[name], dtype=np.int32)] = i
    spike_block = block_ids[idx] if idx.size else np.zeros(0, dtype=np.int8)
    stacked = []
    for i, name in enumerate(DIAG_BLOCK_ORDER):
        series = (
            np.bincount(ms[spike_block == i], minlength=n_ms).astype(np.int32)
            if idx.size else np.zeros(n_ms, dtype=np.int32)
        )
        block_1ms[name] = series
        stacked.append(series)
    if dest is not None:
        path = Path(dest)
        path.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(
            path,
            block_names=np.array(DIAG_BLOCK_ORDER),
            block_1ms=np.stack(stacked, axis=0),
            neuron_totals=totals,
            raster_idx=idx[raster_keep],
            raster_ms=ms[raster_keep],
            mn9_1ms=mn9_1ms,
            v_idx=np.asarray(traces.idx, dtype=np.int32),
            v_1ms=v_1ms,
        )
    result = {
        'seed': seed, 'w_bg': weight, 'settle_s': 2., 'measure_s': t1_seconds,
        'edge_s': 1., 'rates_hz': rates, 'F': sync['F'], 'b': sync['max_bin_fraction'],
        'stability_ratio': first / last if last else None,
        'first_central_hz': first / (len(groups['central']) * 1.0),
        'last_central_hz': last / (len(groups['central']) * 1.0),
        'settled_central_hz': settled_hz, 'max_rolling_central_hz': max_central,
        'ignited': probe_ignited(settled_hz, max_central, params),
        'mn9_hz': float(measure_counts[built['registry'].population('MN9').idx].mean() / t1_seconds),
        'pools': 'clamped' if mod.clamped else 'free', 'wall_s': time.monotonic() - began,
        'h_max': h_max,
        'from_startup_s': seconds,
        'windows': analysis,
        'npz': None if dest is None else str(dest),
        'n_spikes': int(idx.size),
        'block_sizes': {name: int(np.asarray(used_blocks[name]).size) for name in DIAG_BLOCK_ORDER},
    }
    if fano_chunks is not None:
        from flyonenomics.drive.rest_nonuniform import lab_measures
        result['lab'] = lab_measures(fano_chunks, pair_chunks, chunk_ms=chunk_ms)
    return _json_safe(result)


def _task(payload: dict) -> str:
    """Worker owns one scale setting and one NDJSON file; never builds another network."""
    import time
    setting = Setting(**payload['setting'])
    path = Path(payload['path'])
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError(f'refusing to overwrite evaluation evidence: {path}')
    deadline = time.monotonic() + payload['wall_cap_s']
    stage = payload['stage']
    meta = {**payload['identity'], **asdict(setting), 'stage': stage,
            'plan_sha256': payload['plan_sha256'], 'task_id': path.stem}
    with path.open('x') as handle:
        def emit(row):
            handle.write(json.dumps({**meta, **row}, allow_nan=False) + '\n')
            handle.flush()
        try:
            built = _build_engine(setting, mode=payload.get('mode', 'dark'),
                                  bare=payload.get('bare', False), feedforward=payload.get('feedforward', False))
            for weight, seed in payload['probes']:
                if stage == 'R-screen' or stage == 'R-long':
                    emit({'kind': 'evaluation', **_probe(built, weight, seed,
                         seconds=30. if stage == 'R-long' else 10.,
                         edge_s=5. if stage == 'R-long' else 1., deadline=deadline)})
                else:
                    silent = _probe(built, weight, seed, seconds=1., deadline=deadline)
                    sugar = _probe(built, weight, seed, seconds=1., active=True, deadline=deadline)
                    emit({'kind': 'evaluation', 'seed': seed, 'w_bg': weight,
                          'mode': payload['mode'], 'feedforward': payload.get('feedforward', False),
                          'bare': payload.get('bare', False), 'silent': silent, 'sugar': sugar,
                          'difference_hz': sugar['mn9_hz'] - silent['mn9_hz'],
                          'h_max': _max_h_max(silent.get('h_max'), sugar.get('h_max'))})
            emit({'kind': 'task-complete', 'evaluations': len(payload['probes'])})
        except Exception as exc:
            emit({'kind': 'task-error', 'error': f'{type(exc).__name__}: {exc}'})
            raise
    return str(path)


def execute_tasks(tasks: list[dict], workers: str | int) -> None:
    """Spawn isolation and the shared Mac slot lease; Linux workers explicitly bounded."""
    import multiprocessing as mp
    import platform
    from concurrent.futures import ProcessPoolExecutor, as_completed
    from contextlib import nullcontext
    from flyonenomics.orchestrator.budget import lease_workers, swap_used_mib
    if not tasks:
        return
    if platform.system() == 'Darwin':
        if workers != 'auto':
            raise ValueError('Mac rest runs require --workers auto')
        if swap_used_mib() > 4000:
            raise RuntimeError('Mac swap exceeds 4000 MiB')
        lease = lease_workers('auto', len(tasks))
    else:
        import os
        ceiling = max(62, os.cpu_count() or 0)
        if workers == 'auto' or not 1 <= int(workers) <= ceiling:
            raise ValueError(f'Camber needs an explicit worker count in 1..{ceiling}')
        lease = nullcontext(None)
    with lease as held:
        count = held.count if held is not None else min(int(workers), len(tasks))
        with ProcessPoolExecutor(max_workers=count, mp_context=mp.get_context('spawn'),
                                 max_tasks_per_child=1) as pool:
            futures = [pool.submit(_task, payload) for payload in tasks]
            for f in as_completed(futures):
                print(json.dumps({'completed': f.result()}), flush=True)


def screen_tasks(plan: dict, out: Path, identity: dict, q: float = 42.5) -> list[dict]:
    """One setting/seed per child amortizes builds over 19 weights (36 tasks for R1).

    Optional plan 'slices' ([start, stop) weight indices, contiguous from 0 to 19) split
    each setting/seed into shorter children; every probe restores and reseeds, so the
    evaluations are the same probes under shorter wall per child.
    """
    plan_sha = hashlib.sha256(json.dumps(plan, sort_keys=True).encode()).hexdigest()
    slices = plan.get('slices')
    if slices is not None:
        bounds = [tuple(s) for s in slices]
        if not bounds or bounds[0][0] != 0 or bounds[-1][1] != len(WEIGHTS) or any(
                a >= b for a, b in bounds) or any(x[1] != y[0] for x, y in zip(bounds, bounds[1:])):
            raise ValueError('slices must be contiguous nonempty ranges covering every weight')
    tasks = []
    for index, record in enumerate(plan['settings']):
        setting = Setting(**record)
        for seed in SEEDS:
            for start, stop in (bounds if slices is not None else [(0, len(WEIGHTS))]):
                suffix = f'-w{start:02d}-{stop:02d}' if slices is not None else ''
                probes = [(w, seed) for w in setting.weights[start:stop]]
                tasks.append({'setting': record, 'stage': 'R-screen', 'identity': identity,
                              'path': str(out / f'setting-{index:03d}-seed-{seed}{suffix}.ndjson'),
                              'probes': probes, 'plan_sha256': plan_sha,
                              'wall_cap_s': 1.25 * q * len(probes) * 12 + 60})
    return tasks


def read_evaluations(out: Path, expected: list[dict]) -> list[dict]:
    """Fail closed on incomplete/error tasks, mixed execution identities or duplicate probes."""
    rows = []
    for task in expected:
        path = out / Path(task['path']).name
        if not path.is_file():
            raise ValueError(f'missing task {path.name}')
        records = [json.loads(line) for line in read_text(path).splitlines()]
        if (not records or records[-1].get('kind') != 'task-complete'
                or any(r.get('kind') == 'task-error' for r in records)):
            raise ValueError(f'incomplete task {path.name}')
        evals = [r for r in records if r['kind'] == 'evaluation']
        keys = [(r['w_bg'], r['seed']) for r in evals]
        if sorted(keys) != sorted(tuple(p) for p in task['probes']):
            raise ValueError(f'wrong probes in {path.name}')
        for r in records:
            for k in ('job_id', 'commit', 'code_scope', 'platform'):
                if not r.get(k) or r[k] != task['identity'][k]:
                    raise ValueError(f'provenance mismatch: {path.name} {k}')
            if r.get('stage') != task['stage']:
                raise ValueError(f'stage mismatch: {path.name}')
            if r.get('task_id') != path.stem:
                raise ValueError(f'task mismatch: {path.name}')
            if r.get('plan_sha256') != task['plan_sha256']:
                raise ValueError(f'plan mismatch: {path.name}')
            if any(r.get(k) != v for k, v in task['setting'].items()):
                raise ValueError(f'setting mismatch: {path.name}')
        rows.extend(evals)
    return rows


def aggregate_screen(plan: dict, rows: list[dict]) -> list[dict]:
    """Score all candidate pairs while preserving their raw source task references."""
    candidates = []
    for config in plan['settings']:
        setting = Setting(**config)
        subset = [r for r in rows if all(r[k] == v for k, v in config.items())]
        for weight in setting.weights[:-2]:
            c = screen_candidate(setting, weight, subset)
            c['provenance'] = [{k: r[k] for k in ('job_id', 'commit', 'code_scope', 'platform', 'task_id')}
                               for r in subset if r['w_bg'] == weight]
            candidates.append(c)
    return sorted(candidates, key=order_key)


def _stage_record(name: str) -> dict:
    """Import explicit development stage summary; never launch a paid job implicitly.

    The producer job's code_scope is recorded as evidence. Resume binds to the
    summary's declared inputs and artifacts, not the whole-repo code_scope
    (decision 46 / declared-inputs). A later src/ change must not block R1.
    """
    import os
    root = Path(os.environ.get('FLYONENOMICS_REST_RESULTS', ROOT / 'camber-runs/wp17'))
    path = root / name / 'summary.json'
    if not path.is_file():
        return {'status': 'blocked', 'reason': f'missing {path}; run rest_screen.py explicitly'}
    record = read_json(path)
    execution = record.get('execution', {})
    declared = execution.get('inputs')
    if not isinstance(declared, dict) or not declared:
        return {'status': 'blocked', 'reason': 'rest evidence declared inputs are absent'}
    for relative, digest in declared.items():
        if hashlib.sha256(read_bytes(ROOT / relative)).hexdigest() != digest:
            return {'status': 'blocked', 'reason': f'rest evidence input changed: {relative}'}
    artifacts = record.get('artifact_sha256', {})
    if not artifacts or any(not (path.parent / p).is_file() or
            hashlib.sha256(read_bytes(path.parent / p)).hexdigest() != digest
            for p, digest in artifacts.items()):
        return {'status': 'blocked', 'reason': 'rest evidence missing or changed'}
    return {**record, 'outputs': str(path), 'input_identity': _stage_identity(name)}


def _stage_identity(name: str) -> dict:
    import os
    from flyonenomics.validation.binding import code_scope_hash
    root = Path(os.environ.get('FLYONENOMICS_REST_RESULTS', ROOT / 'camber-runs/wp17')) / name
    return {'code_scope': code_scope_hash(ROOT), 'artifacts': {
        str(p.relative_to(root)): hashlib.sha256(read_bytes(p)).hexdigest()
        for p in sorted(root.rglob('*')) if p.suffix in ('.json', '.ndjson') and p.is_file()}}


def run_r1() -> dict:
    return _stage_record('R1')


def run_r2() -> dict:
    return _stage_record('R2')


run_r1.input_identity = lambda: _stage_identity('R1')
run_r2.input_identity = lambda: _stage_identity('R2')
STAGE = {'R1': run_r1, 'R2': run_r2}


def probe_ignited(settled_hz: float, max_rolling_hz: float, params: Any = None) -> bool:
    """Item 87 ignition flag from a stored probe's settled mean and rolling maximum."""
    from flyonenomics.validation.artefacts import ignition_detector
    import numpy as np
    return bool(ignition_detector(
        np.asarray([max_rolling_hz], dtype=float), float(settled_hz), params)["tripped"])


def _ignition_fields(obj: dict[str, Any]) -> bool:
    return {"ignited", "settled_central_hz", "max_rolling_central_hz"} <= obj.keys()


def iter_ignition_probes(obj: Any) -> Iterable[dict[str, Any]]:
    """Yield every mapping that carries the three stored ignition fields."""
    if isinstance(obj, dict):
        if _ignition_fields(obj):
            yield obj
        for child in obj.values():
            yield from iter_ignition_probes(child)
    elif isinstance(obj, list):
        for child in obj:
            yield from iter_ignition_probes(child)


def ignition_flag_change(probe: dict[str, Any], params: Any = None) -> dict[str, Any] | None:
    """Return the change record when the stored flag disagrees with item 87."""
    recorded = probe.get("ignited")
    if recorded is None:
        return None
    settled = float(probe["settled_central_hz"])
    peak = float(probe["max_rolling_central_hz"])
    now = probe_ignited(settled, peak, params)
    if bool(recorded) == now:
        return None
    return {
        "settled_central_hz": settled,
        "max_rolling_central_hz": peak,
        "ignited_recorded": bool(recorded),
        "ignited_item87": now,
    }


def _compact_unit(row: dict[str, Any]) -> dict[str, Any]:
    unit = row.get("unit") if isinstance(row.get("unit"), dict) else {}
    setting = row.get("setting") if row.get("setting") is not None else unit.get("setting")
    compact = {}
    for key in ("sub_tier", "engine_model", "g_gaba", "g_glu", "g_gaba_kc",
                "sigma_th", "optic_exemption", "n_bg"):
        if row.get(key) is not None:
            compact[key] = row[key]
        elif unit.get(key) is not None:
            compact[key] = unit[key]
    if setting is not None:
        compact["setting"] = setting
    return compact


def _change_row(probe: dict[str, Any], *, source: str, parent: dict[str, Any] | None,
                role: str | None, params: Any = None) -> dict[str, Any] | None:
    change = ignition_flag_change(probe, params)
    if change is None:
        return None
    context = parent or probe
    return {
        **change,
        "source": source,
        "stage": context.get("stage") or probe.get("stage"),
        "kind": role or context.get("kind") or probe.get("kind"),
        "task_id": context.get("task_id") or probe.get("task_id"),
        "seed": probe.get("seed", context.get("seed")),
        "w_bg": probe.get("w_bg", context.get("w_bg")),
        "unit": _compact_unit(context) or _compact_unit(probe),
    }


def scan_ignition_document(obj: Any, *, source: str, params: Any = None) -> tuple[int, list[dict[str, Any]]]:
    """Scan a loaded JSON document. Returns (n_probes, changes)."""
    n = 0
    changes: list[dict[str, Any]] = []
    if isinstance(obj, dict) and obj.get("kind") == "evaluation":
        for role in ("silent", "sugar"):
            child = obj.get(role)
            if isinstance(child, dict) and _ignition_fields(child):
                n += 1
                row = _change_row(child, source=source, parent=obj, role=role, params=params)
                if row is not None:
                    changes.append(row)
        if _ignition_fields(obj):
            n += 1
            row = _change_row(obj, source=source, parent=obj, role=None, params=params)
            if row is not None:
                changes.append(row)
        return n, changes
    for probe in iter_ignition_probes(obj):
        n += 1
        row = _change_row(probe, source=source, parent=None, role=None, params=params)
        if row is not None:
            changes.append(row)
    return n, changes


def _source_label(path: Path, root: Path = ROOT) -> str:
    """Path relative to the flyonenomics repo when the file lives under it."""
    repo = root.parent.parent
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(repo))
    except ValueError:
        return str(resolved)


def scan_ignition_path(path: Path, *, params: Any = None) -> tuple[int, list[dict[str, Any]]]:
    """Scan one JSON or NDJSON file. Returns (n_probes, changes)."""
    text = read_text(path)
    source = _source_label(path)
    if path.suffix == ".ndjson":
        n = 0
        changes: list[dict[str, Any]] = []
        for line in text.splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            count, found = scan_ignition_document(row, source=source, params=params)
            n += count
            changes.extend(found)
        return n, changes
    return scan_ignition_document(json.loads(text), source=source, params=params)


def default_ignition_recheck_paths(root: Path = ROOT) -> list[Path]:
    """T3a/b/c T0+T1 records here, 3d records here or under wp26, plus raw ndjson."""
    records = root / "validation" / "records" / "p2"
    named = [
        records / "rest-T3a-T0.json",
        records / "rest-T3a-T1.json",
        records / "rest-T3b-T0.json",
        records / "rest-T3b-T1.json",
        records / "rest-T3c-T0.json",
        records / "rest-T3d-T0.json",
        records / "rest-T3d-T1.json",
    ]
    siblings = root.parent
    raw_roots = [
        siblings / "wp24" / "camber-runs" / "wp24",
        siblings / "wp26" / "camber-runs" / "wp26",
        siblings / "wp26" / "validation" / "records" / "p2",
    ]
    paths: list[Path] = [p for p in named if p.is_file()]
    seen = {p.resolve() for p in paths}
    for base in raw_roots:
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if path.suffix not in {".json", ".ndjson"} or not path.is_file():
                continue
            resolved = path.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            paths.append(path)
    return paths


def build_ignition_recheck(paths: Iterable[Path] | None = None, *, params: Any = None) -> dict[str, Any]:
    """Side file body: every stored ignition flag that item 87 would change."""
    scanned = list(paths) if paths is not None else default_ignition_recheck_paths()
    n_probes = 0
    changes: list[dict[str, Any]] = []
    missing = []
    for path in scanned:
        if not path.is_file():
            missing.append(_source_label(path))
            continue
        count, found = scan_ignition_path(path, params=params)
        n_probes += count
        changes.extend(found)
    by_tier: dict[str, int] = {}
    for row in changes:
        key = str((row.get("unit") or {}).get("sub_tier") or "unknown")
        by_tier[key] = by_tier.get(key, 0) + 1
    return {
        "class": "development",
        "rule": "item 87: relative ignition only when settled_central_hz >= ign.min_baseline_hz 0.5; absolute 8 Hz unconditional",
        "n_files": len(scanned) - len(missing),
        "n_probes": n_probes,
        "n_changed": len(changes),
        "n_changed_by_sub_tier": by_tier,
        "missing_files": missing,
        "note": "Collected T0/T1 JSON summaries have no per-probe ignition fields. Changes come from the raw NDJSON those records collected. No stored record is rewritten.",
        "changes": changes,
    }
