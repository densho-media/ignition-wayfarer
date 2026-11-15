"""Deadship Phase 2C gate G1 (owner brief 2026-11-15): does a finite trace-contaminant-control (TCC) bed create a real NH3 decision?
Task study (work/), not part of the build. It reruns the Shared Air reference strategies (shared_air.cases) with the TCC's capture
efficiency computed from a finite, partly loaded bed instead of the fixed 0.95, and scores them on the gate's own metrics
(ds2b_reconcile.play_run).

    python3 work/project-thread-dfyyv7/ds2c_tcc_gate.py      # about 3 min; prints the tables, writes ds2c_tcc_gate.json

The bed (sources: NASA/TM-2006-214234-class TCCS process-economics assessment, NTRS 20060005220; ICES-2018-253, NTRS 20180004945):
- 22.7 kg of phosphoric-acid-treated activated carbon (Barnebey-Sutcliffe 3032), 15.29 m3/h process flow, expendable (not regenerated).
- NH3 is chemisorbed: one mole of the acid's first H reacts with one mole of NH3, so capacity is stoichiometric. Measured available acid
  0.56 mmol/g gives 12.7 mol = 215.9 g NH3 per bed; the report's conservative case (0.26 mmol/g reacting) gives 100 g.
- The flight bed's profile after 2,595 h: segment 1 (of 5) held 3.6-5.7 mg/g (46 % of its acid), segments 2-5 held 0.004-0.009 mg/g.
  The reaction front is sharp: a fresh section captures NH3 almost completely within about a fifth of the bed.
- Moist-gas capacities at 5 ppm: B-S 3032 12.9 mg/g, Ammonasorb II 21.1, Chemsorb 1425 21.8 (ICES-2018-253); the post-flight bed 11.9
  mg/g at about 0.2 ppm. Water occupies pores; co-adsorbed water raised capacity 25-74 % at 50 ppm in Luna et al. 2010 (cited there).
  Humidity therefore changes capacity in either direction by tens of percent; it is carried as the capacity range, not a separate law.

Model (PROTOTYPE): the Bohart-Adams irreversible-reaction model by the method of lines. The bed is K equal segments; segment k with
capacity q_k and loading l_k passes air with single-segment capture 1 - exp(-a (1 - l_k / q_k)) (reaction rate proportional to the
free acid sites). a = NTU / K with NTU = 30 for the whole bed (the flight profile above needs at least ln 600 = 6.4 per fifth of the bed).
The 0.95 single-pass efficiency of SYS-002 v2 is kept as a flow factor (bypass and channelling), so a fresh bed reproduces v2's 0.95.
An initial loading is laid down by running the same model at a low constant inlet concentration until the bed holds the given fraction,
so its front has the model's own constant-pattern shape, not an assumed one.
"""
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / 'src/wayfarer'))
sys.path.insert(0, str(HERE))
import ring_air  # noqa: E402
import shared_air as sa  # noqa: E402
import ds2b_reconcile as rc  # noqa: E402

K = 20
NTU = 30.0
FLOW_FACTOR = 0.95
CAPACITY_G = {'theoretical 216 g (0.56 mmol/g)': 215.9, 'conservative 100 g (0.26 mmol/g)': 100.0}
QUANTUM = 0.001            # the efficiency is recomputed when it moves by this much (the propagator is rebuilt then)


def bed(capacity_kg, loaded_fraction):
    """A bed of K segments with `loaded_fraction` of its capacity already taken, laid down by the model itself."""
    q = capacity_kg / K
    b = dict(q=q, l=[0.0] * K)
    target = loaded_fraction * capacity_kg
    while sum(b['l']) < target - 1e-12:
        load(b, min(target - sum(b['l']), capacity_kg * 1e-4))
    return b


def capture(b):
    """Each segment's capture fraction of what reaches it, and the bed's single-pass efficiency (without the flow factor)."""
    a = NTU / K
    r = [1.0 - math.exp(-a * (1.0 - min(lk / b['q'], 1.0))) for lk in b['l']]
    through = 1.0
    for rk in r:
        through *= 1.0 - rk
    return r, 1.0 - through


def load(b, m):
    """Lay m kg captured by the bed into its segments, in proportion to what each one takes from the passing air."""
    r, eta = capture(b)
    if eta <= 0.0:
        return
    inlet = 1.0
    for k, rk in enumerate(r):
        b['l'][k] += m * inlet * rk / eta
        inlet *= 1.0 - rk


def efficiency(b):
    return FLOW_FACTOR * capture(b)[1]


_step = ring_air.step


def step_with_bed(st, p, dt):
    """ring_air.step, then the captured NH3 goes into the bed and the TCC's flow is re-weighted by the bed's efficiency."""
    before = st['nh3_removed']
    _step(st, p, dt)
    b = st.get('_bed')
    if b is None:
        return st
    load(b, st['nh3_removed'] - before)
    eta = round(efficiency(b) / QUANTUM) * QUANTUM
    if abs(eta * p['tcc_flow'] - p['tcc_k_m3_s']) > 1e-15:
        p['tcc_k_m3_s'] = eta * p['tcc_flow']
        st['_tcache'] = {}
    return st


def run(actions, capacity_kg, loaded):
    """A Shared Air script with the given bed, scored as ds2b_reconcile does."""
    sc = sa.load()
    p = dict(sa.params())
    p['tcc_flow'] = ring_air.TRACE['tcc_flow_m3_s']['value']
    b = bed(capacity_kg, loaded)
    p['tcc_k_m3_s'] = round(efficiency(b) / QUANTUM) * QUANTUM * p['tcc_flow']
    init = sa.Run.__init__

    def init_with_bed(self, sc_, p_):
        init(self, sc_, p_)
        self.st['_bed'] = b
    sa.Run.__init__ = init_with_bed
    ring_air.step = step_with_bed
    try:
        sa_load, sa_params = sa.load, sa.params
        sa.load, sa.params = (lambda *a, **k: sc), (lambda *a, **k: p)
        out = rc.play_run(actions)
    finally:
        sa.Run.__init__ = init
        ring_air.step = _step
        sa.load, sa.params = sa_load, sa_params
    out['bed_eta_start'] = FLOW_FACTOR * capture(bed(capacity_kg, loaded))[1]
    out['bed_eta_end'] = efficiency(b)
    out['bed_loaded_end'] = sum(b['l']) / capacity_kg
    out['bed_took_g'] = (sum(b['l']) - loaded * capacity_kg) * 1000.0
    return out


def main():
    cases = {n: a for n, _, a in sa.cases()}
    strategies = {'isolate, restore at 24 h': cases['watch_restore'], 'purge': cases['purge'],
                  'separate, reconnect 4 h': cases['separate_reconnect'], 'isolate, no plan': cases['isolate']}
    out = dict(K=K, NTU=NTU, flow_factor=FLOW_FACTOR, rows={})
    for cap_name, cap_g in CAPACITY_G.items():
        for loaded in (0.0, 0.9, 0.98, 0.995):
            key = f'{cap_name}, loaded {loaded:.3f}'
            rows = {s: run(a, cap_g / 1000.0, loaded) for s, a in strategies.items()}
            out['rows'][key] = dict(rows=rows, front=rc.front(rows))
            print(f'--- {key}: fresh-bed efficiency at start {rows["purge"]["bed_eta_start"]:.3f}')
            for s, r in rows.items():
                dom = out['rows'][key]['front'].get(s)
                print(f"  {s:28s} {r['verdict']:14s} 1h {r['r1']*30:5.1f} 24h {r['r24']*20:4.1f} dose24 {r['dose']:6.1f} 7d {r['r7d']*3:4.2f} "
                      f"restore {r['restore_h']:6.1f} h | bed took {r['bed_took_g']:5.2f} g, eta {r['bed_eta_start']:.3f} -> {r['bed_eta_end']:.3f}"
                      f" | {'NON-DOMINATED' if dom == [] else ('not viable' if dom is None else 'dominated by ' + ', '.join(dom))}")
    (HERE / 'ds2c_tcc_gate.json').write_text(json.dumps(out, indent=1) + '\n')


if __name__ == '__main__':
    main()
