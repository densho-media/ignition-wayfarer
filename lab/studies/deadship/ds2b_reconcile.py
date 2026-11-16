"""Deadship Phase 2B finalization (owner brief 2026-11-15): why the gate's crew separation (report section 30.5) became CO2_LIMIT in the
playable reference (section 34.10), and which strategies stay viable and non-dominated in play. Task study (work/), not part of the build:
it runs the gate's own simulator (ds2b_gate.simulate) and the playable machine (shared_air.Run) and scores both on the gate's definitions.

    python3 lab/studies/deadship/ds2b_reconcile.py      # about 2 min; prints the tables, writes ds2b_reconcile.json

Metrics (the gate's, section 30.3): peak CO2 where people are and crew-hours above the 0.3 % target over 24 h; the worst person's largest
1 h and 24 h mean NH3 against 30 and 20 ppm; the crew's mean 24 h NH3 dose; the worst 7 d mean against 3 ppm; the time until every
compartment stays under 3 ppm (168 = not within the 7 d projection); viability = no occupied compartment over 0.5 % CO2 within 24 h.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / 'src/wayfarer'))
sys.path.insert(0, str(HERE))
import air_exposure as ax   # noqa: E402
import ds2b_gate as g   # noqa: E402
import shared_air as sa   # noqa: E402

H = 3600.0
SMAC = g.SMAC
EPS = g.EPS
KEYS = ('r1', 'r24', 'dose', 'co2_ch', 'r7d', 'restore_h')


def gate_run(strat, **over):
    sc = dict(g.BASE, **over)
    st, p, tracks, samples, ex = g.simulate(strat, sc)
    o = g.score(st, p, tracks, samples, ex)
    b = o['obj'][24]
    return dict(viable=o['viable'][24], peak_pct=o['co2_peak_pct'], co2_ch=b['co2_ch'], r1=b['r1'], r24=b['r24'], dose=b['dose'],
                r7d=b['r7d'], restore_h=min(b['restore_h'], 168.0), contain_min=o['contain_t_min'])


def play_run(actions):
    """A playable script on shared_air.Run (as shared_air.play), scored on the gate's definitions."""
    sc, p = sa.load(), sa.params()
    r, _, _ = sa.play(sc, p, actions)
    d = r.debrief()
    ch24 = 0.0
    r1 = r24 = 0.0
    doses = []
    for q in r.people:
        k = max(j for j in range(len(q['t'])) if q['t'][j] <= 24*H + 1e-6) + 1
        r1 = max(r1, ax.window_max(q['t'][:k], q['Es'][:k], H)[0]/SMAC['1h'])
        r24 = max(r24, ax.window_max(q['t'][:k], q['Es'][:k], 24*H)[0]/SMAC['24h'])
        doses.append(q['Es'][k - 1]/H)
    over = [t for t, mx, _ in r.samples if mx > SMAC['7d']]
    restore = 0.0 if not over else (168.0 if over[-1] >= r.samples[-1][0] - 1e-6 else over[-1]/H)
    v = d['watch']['verdict']
    return dict(viable=v['co2_limit_crossed_at_h'] is None or v['co2_limit_crossed_at_h'] > 24.0, verdict=v['result'], family=d['watch']['family'],
                peak_pct=d['co2_peak_pct'], co2_ch=v['co2_above_target_crew_h'], r1=r1, r24=r24, dose=sum(doses)/len(doses),
                r7d=max(q['mean_7d_ppm'] for q in d['people'])/SMAC['7d'], restore_h=restore, a1_h=d['clear_h']['A1'],
                contain_min=(d['contained_at_h'] or 0.0)*60.0, released_g=d['released_g'])


def dominated(a, b):
    """b dominates a beyond the gate's epsilons: no worse on every objective, better by more than epsilon on one."""
    eps = dict(EPS, co2_ch=EPS['co2_ch'], restore_h=EPS['restore_h'])
    no_worse = all(b[k] <= a[k] + eps[k] for k in KEYS)
    better = any(b[k] < a[k] - eps[k] for k in KEYS)
    return no_worse and better


def front(rows):
    viable = {n: r for n, r in rows.items() if r['viable']}
    return {n: [m for m, o in viable.items() if m != n and dominated(r, o)] for n, r in viable.items()}


def playable_fast():
    """The same strategies with the trainee containing at the alert (10 min) instead of 15 min: the fastest a single trainee can be."""
    C0 = 600.0; D = C0 + 610.0
    w = sa.walk
    iso = [[C0, 'contain_start'], [D, 'order', 'A', 'A2']] + w(sa.A1_TO_A3, D) + sa.seal(D + 150.0, 'A1P', 'A1N') + [[D + 1200.0, 'watch', 'RESTORE']]
    pur = [[C0, 'contain_start'], [D, 'order', 'A', 'A3'], [D, 'order', 'B', 'A3']] + w(sa.A1_A2_A3, D, leave_open=True) + [[D + 1200.0, 'watch', 'NONE']]
    sep = ([[C0, 'contain_start'], [D, 'order', 'A', 'A2'], [D, 'order', 'C', 'A2']] + w(sa.A1_TO_A3, D, leave_open=True)
           + sa.seal(D + 300.0, 'A1P', 'A3N') + [[D + 305.0, 'schedule', 4*H]] + w(sa.A3_TO_A2, D + 310.0) + [[D + 1200.0, 'watch', 'RESTORE']])
    return {'fast: isolate, restore at 24 h': iso, 'fast: purge': pur, 'fast: separate, reconnect 4 h': sep}


def main():
    out = {}
    rep_sep = dict(arcs=('Hb', 'Ha', 'B'), dest=('A2', 'A2', 'A2'), contain=1, t2=1)
    gate = {
        'gate: separate, reconnect 4 h (section 30.5)': gate_run(rep_sep),
        'gate: separate, no reconnect': gate_run(dict(rep_sep, t2=0)),
        'gate: separate, reconnect 4 h, crew act at 15 min': gate_run(rep_sep, delay_s=900.0),
        'gate: separate, reconnect 4 h, crew act at 30 min': gate_run(rep_sep, delay_s=1800.0),
        'gate: purge to the TCC, all to A3': gate_run(dict(arcs=('O', 'O', 'Hb'), dest=('A3', 'A3', 'A3'), contain=1, t2=0)),
        'gate: isolate A1, all to A3': gate_run(dict(arcs=('Ha', 'Ha', 'Hb'), dest=('A3', 'A3', 'A3'), contain=1, t2=0)),
    }
    cases = {n: a for n, _, a in sa.cases()}
    play = {
        'play 3 separate (no reconnection)': play_run(cases['separate']),
        'play 17 separate_reconnect (4 h)': play_run(cases['separate_reconnect']),
        'play 18 separate_late (6 h)': play_run(cases['separate_late']),
        'play 1 isolate (no plan)': play_run(cases['isolate']),
        'play 15 watch_restore (isolate, restore at 24 h)': play_run(cases['watch_restore']),
        'play 2 purge': play_run(cases['purge']),
    }
    fast = {n: play_run(a) for n, a in playable_fast().items()}
    out = dict(gate=gate, play=play, fast=fast,
               front_play=front({k: play[k] for k in ('play 1 isolate (no plan)', 'play 15 watch_restore (isolate, restore at 24 h)', 'play 2 purge',
                                                     'play 17 separate_reconnect (4 h)', 'play 18 separate_late (6 h)', 'play 3 separate (no reconnection)')}),
               front_fast=front(fast), eps=EPS)
    for block in ('gate', 'play', 'fast'):
        print(f'--- {block}')
        for n, r in out[block].items():
            print(f"{n:52s} viable {str(r['viable']):5s} {r.get('verdict', ''):14s} peak {r['peak_pct']:.3f} % co2 {r['co2_ch']:6.1f} crew-h | "
                  f"1h {r['r1']*30:5.1f} 24h {r['r24']*20:4.1f} dose24 {r['dose']:6.1f} 7d {r['r7d']*3:4.2f} | restore {r['restore_h']:6.2f} h"
                  f"{'' if 'a1_h' not in r else f' A1 {r[chr(97)+chr(49)+chr(95)+chr(104)]}'} | contained {r['contain_min']:.1f} min")
    for f in ('front_play', 'front_fast'):
        print(f'--- {f}: viable strategies and who dominates them')
        for n, by in out[f].items():
            print(f'  {n:52s} {"NON-DOMINATED" if not by else "dominated by " + ", ".join(by)}')
    (HERE / 'ds2b_reconcile.json').write_text(json.dumps(out, indent=1) + '\n')


if __name__ == '__main__':
    main()
