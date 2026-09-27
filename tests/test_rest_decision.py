"""Constructed SPEC-P2 2.6 decisions; no Brian2 engine imports or runs."""
from copy import deepcopy
import json
import math
from pathlib import Path
import pytest
from flyonenomics.drive.rest_map import (
    Setting, TARGETS, attach_reflex, calibration_next, candidate_id, capped_candidates,
    decide, long_decision, objective, order_key, reflex_decision, screen_candidate,
    select_map_pairs, select_r3, tier2_settings, violation,
)


def rows():
    return [{"w_bg": w, "seed": seed, "F": 2., "b": .002, "stability_ratio": 1.,
             "rates_hz": {**TARGETS, "central": 1., "DAN": 1., "KC": 1.}}
            for w in Setting(3, 4).weights for seed in (1, 2, 3)]


def candidate(**updates):
    row = screen_candidate(Setting(3, 4), 1.2, rows())
    return {**row, **updates}


def test_missing_silent_and_finite_objective():
    empty = screen_candidate(Setting(3, 4), 1.2, [])
    assert empty["S"] == 70 and not empty["screen_passed"]
    data = rows()
    for r in data:
        r.update(F=None, stability_ratio=None, rates_hz={g: 0. for g in TARGETS})
    silent = screen_candidate(Setting(3, 4), 1.2, data)
    assert not silent["screen_passed"] and math.isfinite(silent["J"])
    assert silent["violations"]["central"] == pytest.approx(math.log(50))
    assert violation(float('nan')) == 10
    assert violation(None) == 10
    assert violation(1e200, upper=1) == 10
    assert objective(TARGETS) == 0


@pytest.mark.parametrize('field,value', [('F', 3.), ('b', .05), ('stability_ratio', 2.01)])
def test_every_seed_both_weights(field, value):
    data = rows()
    next(r for r in data if r['w_bg'] == 1.25 and r['seed'] == 3)[field] = value
    result = screen_candidate(Setting(3, 4), 1.2, data)
    assert not result['screen_passed']
    if field != 'stability_ratio':
        assert result['S'] == 0  # Strict predicates do not follow from score == 0.


def test_seed_mean_rates_and_grade_compares_both_pair_members():
    data = rows()
    for r in data:
        if r['w_bg'] == 1.2:
            r['rates_hz']['DAN'] = {1: 0., 2: .75, 3: .75}[r['seed']]
        if r['w_bg'] == 1.25:
            r['rates_hz']['central'] = 2.
        if r['w_bg'] == 1.3:
            r['rates_hz']['central'] = 3.
    result = screen_candidate(Setting(3, 4), 1.2, data)
    assert result['screen_checks']['DAN']
    assert not result['screen_checks']['gradedness']
    with pytest.raises(ValueError, match='duplicate'):
        screen_candidate(Setting(3, 4), 1.2, data + [data[0]])


def test_order_exact_ties_j_bins_and_all_parameter_tiebreakers():
    a = candidate(J=1.01, g_gaba=2, g_glu=6)
    b = candidate(J=1.24, g_gaba=3, g_glu=4)
    assert order_key(a) < order_key(b)  # same J bin and same product, gaba decides
    assert order_key(candidate(J=1.25)) > order_key(candidate(J=1.24))
    base = candidate()
    for key, val in [('sigma_th', 1.), ('optic_exemption', True), ('n_bg', 400), ('w_bg', 1.25)]:
        assert order_key(base) < order_key({**base, key: val})
    assert order_key(base) == order_key(deepcopy(base))
    with pytest.raises(ValueError):
        order_key(candidate(S=float('inf')))


def test_order_key_is_the_spec_p2_2_6_tuple():
    """Lock the SPEC-P2 2.6 field order, not only pairwise inequalities."""
    row = candidate(S=8.866750667586105, J=16.10126160395004, g_gaba=3.0, g_glu=6.0,
                    sigma_th=1.0, optic_exemption=False, n_bg=25, w_bg=3.4)
    assert order_key(row) == (
        8.866750667586105, math.floor(16.10126160395004 / 0.25),
        abs(math.log(3.0)) + abs(math.log(6.0)),
        3.0, 6.0, 1.0, False, 25, 3.4,
    )


def test_development_substrate_uses_complete_s_not_a_screen_lower_bound():
    """SPEC-P2 2.6 step 5 ranks complete S (R-reflex measured). Incomplete S is a lower bound."""
    measured = candidate(S=8.87, J=16.1, g_gaba=3.0, g_glu=6.0, sigma_th=1.0,
                         n_bg=25, w_bg=3.4, screen_passed=True, reflex_passed=False)
    screen_fail = candidate(S=0.0, J=16.1, g_gaba=4.0, g_glu=2.0, screen_passed=False)
    assert order_key(screen_fail) < order_key(measured)
    complete = [measured]
    assert candidate_id(min(complete, key=order_key)) == candidate_id(measured)
    record = json.loads((Path(__file__).resolve().parents[1] / "validation/records/p2/rest-escalation.json").read_text())
    col = {name: i for i, name in enumerate(record["columns"])}
    rows = [r for r in record["rows"] if r[col["state"]] == "measured"]
    def as_row(r):
        return {k: r[col[k]] for k in ("g_gaba", "g_glu", "sigma_th", "optic_exemption", "n_bg", "w_bg", "S", "J")}
    closest = min(rows, key=lambda r: order_key(as_row(r)))
    assert closest[col["candidate_id"]] == "3.0-6.0-1.0-False-25-3.4"
    assert record["development_substrate"]["candidate_id"] == closest[col["candidate_id"]]
    assert decide([{**as_row(r), "screen_passed": True, "reflex_passed": False, "long_passed": None}
                   for r in rows], tier=2)["status"] == "P2-partial-B"


def test_twenty_cap_and_shortlist():
    data = [candidate(w_bg=i / 100 + .7) for i in range(25)]
    selected, excluded = capped_candidates(list(reversed(data)))
    assert len(selected) == 20 and len(excluded) == 5
    assert all(r['status'] == 'not tested (cap)' for r in excluded)
    result = decide([{**r, 'reflex_passed': True, 'long_passed': True} for r in selected])
    assert len(result['ranked']) == 20 and len(result['shortlist']) == 3
    assert decide(data, complete=False)['status'] == 'pending'


def test_reflex_full_rule_retention_and_boundary():
    ff = {'upstream': [60.] * 10, 'extended': [60.] * 10}
    ref = {'upstream': [100.] * 10, 'extended': [100.] * 10}
    result = reflex_decision([40.] * 6, [51.] * 10, ff, ref)
    assert result['reflex_passed'] and result['retention']['extended'] == .6
    assert not reflex_decision([40.] * 6, [50.] * 10, ff, ref)['reflex_passed']
    assert not reflex_decision([40.] * 6, [39.] + [80.] * 9, ff, ref)['reflex_passed']
    assert not reflex_decision([40.] * 5, [60.] * 10, ff, ref)['reflex_passed']
    assert not reflex_decision([40.] * 6, [60.] * 10, ff, {})['reflex_passed']
    row = attach_reflex(candidate(), result)
    assert attach_reflex(row, result)['S'] == row['S']
    ref['upstream'] = [0.] * 10
    assert reflex_decision([40.] * 6, [60.] * 10, ff, ref)['reflex_passed']
    ff['extended'] = [49.] * 10
    assert not reflex_decision([40.] * 6, [60.] * 10, ff, ref)['reflex_passed']


def test_long_requires_all_ten_seeds_and_explicit_no_ignition():
    data = [{'seed': i, 'F': 2., 'stability_ratio': 1., 'ignited': False} for i in range(1, 11)]
    assert long_decision(data)['long_passed']
    assert not long_decision(data[:-1])['long_passed']
    data[0]['ignited'] = True
    assert not long_decision(data)['long_passed']
    data[0]['ignited'] = None
    assert not long_decision(data)['long_passed']


@pytest.mark.parametrize('screen,reflex,trigger', [(False, False, 'R-screen'), (True, False, 'R-reflex'), (True, True, 'R-long')])
def test_each_tier_two_trigger_and_unique_pairs(screen, reflex, trigger):
    data = [candidate(g_gaba=g, screen_passed=screen, reflex_passed=reflex,
                      long_passed=False, reflex_violation=6-g) for g in (1, 2, 3, 4)]
    data += [candidate(g_gaba=1, w_bg=1.25, screen_passed=screen, reflex_passed=reflex, long_passed=False, reflex_violation=5)]
    result = decide(data)
    assert result['status'] == 'tier2' and result['trigger'] == trigger
    assert len(result['tier2_pairs']) == 3
    if trigger == 'R-reflex':
        assert result['tier2_pairs'][0] == [4, 4]
    variants = tier2_settings(result['tier2_pairs'])
    assert len(variants) == 51
    for s in variants:
        assert s.weights[0] * s.n_bg == pytest.approx(70)
    assert decide(data, tier=2)['status'] == 'P2-partial-B'


def test_r3_all_fail_six_cap_timeout_and_rank_order():
    ranked = [candidate(w_bg=.7 + i / 100) for i in range(8)]
    assert select_r3(ranked, {}, 11.9)['status'] == 'waiting'
    assert select_r3(ranked, {}, 12)['candidate'] == ranked[0]
    fail = {candidate_id(r): False for r in ranked[:6]}
    assert select_r3(ranked, fail, 1)['reason'] == 'R3 exhausted'
    assert select_r3(ranked, {candidate_id(ranked[1]): True}, 1)['candidate'] == ranked[1]
    fail[candidate_id(ranked[1])] = True
    assert select_r3(ranked, fail, 1)['candidate'] == ranked[1]


def test_t_to_c_fallthrough_one_candidate_and_three_exhausted():
    ranked = [candidate(w_bg=.7 + i / 100) for i in range(5)]
    assert calibration_next(ranked, [], ranked[0], 'T', False)['table'] == 'C'
    assert calibration_next(ranked, [], ranked[0], 'C', False)['candidate'] == ranked[1]
    assert calibration_next(ranked[:1], [], ranked[0], 'C', False)['status'] == 'P2-partial-B'
    ids = [candidate_id(r) for r in ranked[:2]]
    assert calibration_next(ranked, ids, ranked[2], 'C', False)['status'] == 'P2-partial-B'
    assert calibration_next(ranked, [], ranked[0], 'T', True)['status'] == 'passed'


def test_map_selection_capped_and_deterministic():
    data = [candidate(g_gaba=a, g_glu=b, screen_passed=(a == 3 and b >= 3), S=abs(3-a))
            for a in (1, 2, 3, 4, 6, 8) for b in (1, 2, 3, 4, 6, 8)]
    assert len(select_map_pairs(data)) == 12
    assert select_map_pairs(data) == select_map_pairs(list(reversed(data)))
