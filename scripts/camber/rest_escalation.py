#!/usr/bin/env python3
"""SPEC-P2 section 2.6 step 5: closest-miss tables and the development substrate choice.

Reads tier-1 R1/R2 and tier-2 screen/stage-2 records, recomputes each candidate's worst-case
criterion values from its rows, and writes a record plus the generated escalation sections of
docs/resting-candidates.md (between escalation and closest-miss markers). No engine runs.
"""
from __future__ import annotations
import argparse
import glob
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
from flyonenomics.drive import rest_map as rest
from flyonenomics.io import read_bytes, read_json, read_text

SETTING_KEYS = ('g_gaba', 'g_glu', 'sigma_th', 'optic_exemption', 'n_bg')
MARKERS = {'escalation': ('<!-- escalation:begin -->', '<!-- escalation:end -->'),
           'closest': ('<!-- closest-miss:begin -->', '<!-- closest-miss:end -->')}


def sha256(path):
    return hashlib.sha256(read_bytes(path)).hexdigest()


def evaluation_rows(paths):
    rows = []
    for p in paths:
        for line in read_text(p).splitlines():
            r = json.loads(line)
            if r.get('kind') == 'evaluation':
                rows.append(r)
    return rows


def worst_values(c, rows):
    """Worst-case section 2.3 values over seeds and both pair members, as screen_candidate reads them."""
    setting = rest.Setting(**{k: c[k] for k in SETTING_KEYS})
    index = setting.weights.index(c['w_bg'])
    weights = setting.weights[index:index + 3]
    lookup = {(round(float(r['w_bg']), 8), int(r['seed'])): r for r in rows}
    points = [[lookup.get((w, s), {}) for s in rest.SEEDS] for w in weights]
    pair = [r for p in points[:2] for r in p]
    def worst(field, fn):
        vals = [rest.number(r.get(field)) for r in pair]
        return None if any(v is None for v in vals) else fn(vals)
    grades = []
    for i in range(3):
        nxt = rest.number(points[2][i].get('rates_hz', {}).get('central'))
        for p in points[:2]:
            cur = rest.number(p[i].get('rates_hz', {}).get('central'))
            grades.append(None if nxt is None or cur is None else max(nxt, .01) / max(cur, .01))
    means = c['pair_rates_hz']
    span = lambda g: [min(m[g] for m in means), max(m[g] for m in means)] if all(m.get(g) is not None for m in means) else None
    return {'F_max': worst('F', max), 'b_max': worst('b', max),
            'stability_min': worst('stability_ratio', min), 'stability_max': worst('stability_ratio', max),
            'central_hz': span('central'), 'DAN_hz': span('DAN'), 'KC_hz': span('KC'),
            'gradedness_max': None if None in grades else max(grades)}


def failed_step(c, state):
    if state in ('pending', 'cap', 'beyond'):
        return {'pending': 'R-reflex pending', 'cap': 'not tested (cap)',
                'beyond': 'measured beyond cap (not in decision)'}[state]
    if not c['screen_passed']:
        return 'R-screen (' + ', '.join(k for k, ok in c['screen_checks'].items() if not ok) + ')'
    if c.get('reflex_passed') is False:
        return 'R-reflex (' + ', '.join(k for k, v in c['reflex_violations'].items() if v > 0) + ')'
    if c.get('long_passed') is False:
        return 'R-long'
    return 'passed'


def row(tier, c, rows, state):
    out = {'tier': tier, 'candidate_id': rest.candidate_id(c), **{k: c[k] for k in SETTING_KEYS},
           'w_bg': c['w_bg'], **worst_values(c, rows), 'S': c['S'], 'J': c['J'],
           'screen_passed': c['screen_passed'], 'reflex_passed': c.get('reflex_passed'),
           'long_passed': c.get('long_passed'), 'state': state, 'failed_step': failed_step(c, state)}
    if 'reflex_violations' in c:
        out.update({'reflex_a_min_hz': min(c['a_hz']) if c['a_hz'] else None,
                    'reflex_b_mean_hz': sum(c['b_hz']) / len(c['b_hz']) if c['b_hz'] else None,
                    'retention_extended': c['retention']['extended'],
                    'retention_upstream': c['retention']['upstream']})
    return out


def tier1(r1_summary, r2_decision):
    summary, decision = read_json(r1_summary), read_json(r2_decision)
    rows = evaluation_rows(sorted(glob.glob(str(Path(r1_summary).parent / 'setting-*.ndjson'))))
    measured = {rest.candidate_id(c): c for c in decision['candidates']}
    admitted = {rest.candidate_id(c) for c in summary['admitted']}
    out = []
    for c in summary['candidates']:
        cid = rest.candidate_id(c)
        subset = [r for r in rows if all(r[k] == c[k] for k in SETTING_KEYS)]
        if cid in measured:
            out.append(row(1, measured[cid], subset, 'measured'))
        else:
            out.append(row(1, c, subset, 'cap' if cid in admitted else 'screen'))
    return out


def tier2(screen_path, stage2_path):
    screen, stage2 = read_json(screen_path), read_json(stage2_path)
    files = {}
    for index, source in screen['sources'].items():
        files[int(index)] = [str(Path(source['dir']) / name) for name in source['artifact_sha256']]
    parent = read_json(ROOT / 'validation/records/p2/rest-tier2-plan.json')
    by_setting = {}
    for index, paths in files.items():
        config = parent['settings'][index]
        by_setting[tuple(config[k] for k in SETTING_KEYS)] = evaluation_rows(paths)
    measured = {rest.candidate_id(c): c for c in stage2['admitted']}
    beyond = {rest.candidate_id(c): c for c in stage2.get('beyond_cap_results', [])}
    admitted = {rest.candidate_id(c) for c in screen['admitted']}
    out = []
    for c in screen['candidates']:
        cid = rest.candidate_id(c)
        subset = by_setting[tuple(c[k] for k in SETTING_KEYS)]
        if cid in measured:
            out.append(row(2, measured[cid], subset, 'measured'))
        elif cid in beyond:
            out.append(row(2, beyond[cid], subset, 'beyond'))
        elif cid in admitted:
            out.append(row(2, c, subset, 'pending'))
        elif c['screen_passed']:
            out.append(row(2, c, subset, 'cap'))
        else:
            out.append(row(2, c, subset, 'screen'))
    return out, screen, stage2


def fmt(v, digits=3):
    if v is None:
        return 'n/a'
    if isinstance(v, list):
        return '–'.join(fmt(x, digits) for x in v)
    if isinstance(v, bool):
        return 'on' if v else 'off'
    return f'{v:.{digits}f}'


def table(rows, reflex):
    head = ['Tier', 'g_gaba', 'g_glu', 'σ_th mV', 'optic exempt', 'n_bg', 'w_bg mV', 'F max', 'b max',
            'stability min–max', 'central Hz', 'DAN Hz', 'KC Hz', 'gradedness max']
    if reflex:
        head += ['(a) min Δ Hz', '(b) mean Δ Hz', '(c) ext. retention']
    head += ['S', 'J', 'Failed step']
    lines = ['| ' + ' | '.join(head) + ' |', '|' + '|'.join('---:' if h not in ('Failed step',) else '---' for h in head) + '|']
    for r in rows:
        cells = [str(r['tier']), fmt(r['g_gaba'], 1), fmt(r['g_glu'], 1), fmt(r['sigma_th'], 1), fmt(r['optic_exemption']),
                 str(r['n_bg']), fmt(r['w_bg'], 4), fmt(r['F_max']), fmt(r['b_max'], 4),
                 fmt([r['stability_min'], r['stability_max']]), fmt(r['central_hz'], 2), fmt(r['DAN_hz'], 2),
                 fmt(r['KC_hz'], 2), fmt(r['gradedness_max'], 2)]
        if reflex:
            cells += [fmt(r.get('reflex_a_min_hz'), 0), fmt(r.get('reflex_b_mean_hz'), 1), fmt(r.get('retention_extended'), 4)]
        cells += [fmt(r['S'], 4), fmt(r['J'], 3), r['failed_step']]
        lines.append('| ' + ' | '.join(cells) + ' |')
    return '\n'.join(lines)


def replace_block(text, name, body):
    begin, end = MARKERS[name]
    if text.count(begin) != 1 or text.count(end) != 1:
        raise ValueError(f'{name} markers must appear exactly once')
    head, rest_ = text.split(begin)
    _, tail = rest_.split(end)
    return head + begin + '\n' + body.strip() + '\n' + end + tail


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--r1-summary', type=Path, required=True)
    parser.add_argument('--r2-decision', type=Path, required=True)
    parser.add_argument('--tier2-screen', type=Path, required=True)
    parser.add_argument('--tier2-stage2', type=Path, required=True)
    parser.add_argument('--record', type=Path, required=True)
    parser.add_argument('--doc', type=Path, required=True)
    parser.add_argument('--outcome-note', default='', help='governance follow-up for the final section (who decided what)')
    args = parser.parse_args()
    rows1 = tier1(args.r1_summary, args.r2_decision)
    rows2, screen, stage2 = tier2(args.tier2_screen, args.tier2_stage2)
    rows = rows1 + rows2
    interim = bool(screen.get('settings_missing') or stage2.get('pending_stage2') or stage2['decision_status'] == 'pending')
    depth = {'measured': 0, 'beyond': 1, 'pending': 2, 'cap': 3, 'screen': 4}
    rows.sort(key=lambda r: (depth[r['state']], rest.order_key(r)))
    complete = [r for r in rows if r['state'] == 'measured']
    ranked = [r for r in complete if r['reflex_passed'] and r['long_passed']]
    chosen = complete[0] if complete else None
    count = lambda tier, *states: sum(1 for r in rows if r['tier'] == tier and r['state'] in states)
    counts = {t: {'candidates': count(t, *depth), 'screen_passers': sum(1 for r in rows if r['tier'] == t and r['screen_passed']),
                  'measured_reflex': count(t, 'measured'), 'reflex_passed': sum(1 for r in rows if r['tier'] == t and r['state'] == 'measured' and r['reflex_passed']),
                  'long_passed': sum(1 for r in rows if r['tier'] == t and r['state'] == 'measured' and r['long_passed']),
                  'pending_reflex': count(t, 'pending'), 'not_tested_cap': count(t, 'cap'), 'measured_beyond_cap': count(t, 'beyond')}
              for t in (1, 2)}
    inputs = {str(p): sha256(p) for p in (args.r1_summary, args.r2_decision, args.tier2_screen, args.tier2_stage2)}
    record = {'status': 'interim' if interim else 'final', 'class': 'development', 'section': 'SPEC-P2 2.6 step 5',
              'decision_status': 'pending' if interim else ('ranked' if ranked else 'P2-partial-B'),
              'ranked': [r['candidate_id'] for r in ranked], 'counts': counts,
              'tier2_settings_missing': screen.get('settings_missing', []),
              'tier2_pending_stage2': stage2.get('pending_stage2', []),
              'development_substrate': chosen and {k: chosen[k] for k in ('tier', 'candidate_id', 'S', 'J', 'failed_step')},
              'eligibility': 'lowest order key among candidates measured through R-reflex (S complete)',
              'inputs_sha256': inputs, 'columns': list(rows[0]), 'rows': [list(r.values()) for r in rows]}
    args.record.write_text(json.dumps(record, indent=None, separators=(',', ':')) + '\n')
    mark = 'INTERIM' if interim else 'FINAL'
    missing = screen.get('settings_missing', [])
    pending = stage2.get('pending_stage2', [])
    c1, c2 = counts[1], counts[2]
    body = f"""## Escalation — SPEC-P2 2.6 step 5 ({mark})

"""
    if interim:
        screen_state = (f"{len(missing)} of 51 tier-2 settings await the screen ({', '.join(map(str, missing))})"
                        if missing else "the R-screen over all 51 tier-2 settings is final")
        body += (f"**Interim, not the decision.** Tier-2 stage 2 is still running: {len(pending)} of the "
                 f"{'current ' if missing else ''}top-20 admissions await R-reflex, and {screen_state}. This section and "
                 f"the closest-miss appendix are regenerated by `scripts/camber/rest_escalation.py` when the last "
                 f"stage-2 job lands.\n\n")
    measured = c1['measured_reflex'] + c2['measured_reflex']
    passed = c1['reflex_passed'] + c2['reflex_passed']
    if interim:
        body += f"""Tier 1 left the ranked list empty at R-reflex, which triggered tier 2 on (3,6), (3,8) and (4,2).
So far {measured} candidates have been measured through R-reflex ({c1['measured_reflex']} tier 1,
{c2['measured_reflex']} tier 2 admitted, plus {c2['measured_beyond_cap']} tier 2 measured beyond the
{'current ' if missing else ''}cap). {passed} passed R-reflex, so none reached R-long.
**Ranked list so far: `{record['ranked']}`.** Expected outcome: **P2-partial-B, "no rest substrate"**. The
coordinator asks Rolf whether to authorise tier 3, relax a named criterion, or stop.

The rest of tier 2 cannot rescue R-reflex (c). """
    else:
        outcome = 'P2-partial-B, "no rest substrate"' if not ranked else 'ranked'
        body += f"""**Decision: {outcome}.** Tier 1 left the ranked list empty at R-reflex, which triggered tier 2 on
(3,6), (3,8) and (4,2) (section 2.6 step 4). Tier 2 screened all 51 settings, and all 20 tier-wide
admissions were measured through R-reflex. Across both tiers {measured} candidates in the decision sets
were measured through R-reflex ({c1['measured_reflex']} tier 1, {c2['measured_reflex']} tier 2); {passed}
passed, so none reached R-long. **Ranked list `{record['ranked']}`, shortlist `[]`.** No candidate is released
to R3, no `drive-v0.2.yaml` is written, and the bare substrate stays canonical.
{(chr(10) + args.outcome_note + chr(10)) if args.outcome_note else ''}
Why tier 2 could not rescue R-reflex (c): """
    body += f"""the feed-forward probe runs with background off and base thresholds, so
σ_th and n_bg cannot change it, and optic exemption left the rows identical where measured ((3,6), (3,8)).
Extended retention is therefore a property of the scale pair: 0.0018 for (3,6) and (3,8), 0.0 for (4,2),
against a 0.5 floor. Every tier-2 admission sits on one of those pairs. Why the scaling abolishes the
reflex is in `.reports/WP17-report.md`, section "Why inhibitory scaling abolishes the reflex".

| Stage | Tier 1 | Tier 2 |
|---|---:|---:|
| candidates scored by R-screen | {c1['candidates']} | {c2['candidates']} |
| R-screen passers | {c1['screen_passers']} | {c2['screen_passers']} |
| measured through R-reflex (admitted) | {c1['measured_reflex']} | {c2['measured_reflex']} |
| R-reflex passed | {c1['reflex_passed']} | {c2['reflex_passed']} |
| R-long passed | {c1['long_passed']} | {c2['long_passed']} |
| admitted, R-reflex pending | {c1['pending_reflex']} | {c2['pending_reflex']} |
| not tested (cap) | {c1['not_tested_cap']} | {c2['not_tested_cap']} |
| measured beyond the cap (not in decision) | {c1['measured_beyond_cap']} | {c2['measured_beyond_cap']} |

**Closest-miss score.** S sums the section 2.6 violations. It is complete only for candidates measured
through R-reflex. For R-screen failures and for passers not yet measured it omits the reflex terms, so it is
a lower bound and does not compare with a complete S. The tables therefore group candidates by the deepest
stage reached and sort by the order key within each group. Values are worst case over seeds and both pair
members: F, b and the stability ratio over the six pair rows; central, DAN and KC as the range of the two
pair means; gradedness as the largest next-point/pair central ratio; reflex (a) the lowest seed
difference, (b) the mean difference, (c) the extended retention.

**Development substrate.** Step 5 allows the lowest candidate by order key to be written as
`data/drive-dev-p2.yaml`. I apply it to candidates with complete S (measured through R-reflex, tier 1 and
tier 2 pooled, the decision set only): **{chosen['candidate_id'] if chosen else 'none'}** (tier {chosen['tier'] if chosen else '–'},
S {fmt(chosen['S'], 4) if chosen else '–'}, J {fmt(chosen['J'], 3) if chosen else '–'}, failed {chosen['failed_step'] if chosen else '–'}).
It is class development and qualifies nothing.{' It may change while stage 2 is interim.' if interim else ''}
{'' if interim else 'Its configuration commit is separate from this evidence, per the section 2.5 freeze protocol.'}

### Candidates measured through R-reflex

{table([r for r in rows if r['state'] in ('measured', 'beyond')], True)}

Record: `{args.record}` (inputs by SHA-256; every candidate row). The full closest-miss table of all
{len(rows)} candidates is the appendix at the end of this document.
"""
    closest = f"""## Appendix: closest-miss table, all candidates ({mark})

Grouped by deepest stage reached (measured through R-reflex, measured beyond cap, R-reflex pending, not
tested (cap), R-screen failure), order key within each group. {len(rows)} candidates.

{table(rows, True)}
"""
    text = read_text(args.doc)
    text = replace_block(text, 'escalation', body)
    text = replace_block(text, 'closest', closest)
    args.doc.write_text(text)
    print(json.dumps({'status': record['status'], 'rows': len(rows), 'chosen': record['development_substrate'],
                      'counts': counts}))


if __name__ == '__main__':
    main()
