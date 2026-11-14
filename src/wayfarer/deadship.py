"""Deadship scenarios (DS-1 "Scrubber", Phase 1): load and check a training scenario from data/deadship/, compute its model-level
reference replay and package it for the walk. Standard library only.

The scenario layer sits on top of an engineering model and only calls the model's public operations (cabin_air.start, operate, step,
readout). The model knows nothing of scenarios; the scenario owns its training values (time scale, fault lead, watch length, texts),
never an engineering value: `load` refuses a scenario that sets one. Godot runs the scenario (godot/scripts/deadship/scrubber.gd) and
must reproduce `reference()` within the model's tolerance before it offers the training.

    python3 src/wayfarer/deadship.py      # check the scenario and print its reference replay
"""
import json
import math
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import cabin_air

SCENARIO = 'data/deadship/ds1_scrubber.toml'
FILE = 'wf_deadship_ds1.json'
SCHEMA = 'WF_DEADSHIP_SCENARIO'
VERSION = 1
# Engineering values a scenario must never set (they belong to the model and its canon sources).
ENGINEERING_KEYS = {'co2_target', 'co2_max', 'pressure', 'pressure_kpa', 'volume', 'V_m3', 'occupants', 'per_person_kg_s', 'k_m3_s',
                    'temperature_K', 'rate', 'bands', 'kpa'}
CONDITIONS = ('at', 'flag', 'mode', 'fan', 'spare')
FLAGS = ('inspected', 'diagnosed', 'watch_passed')
POINTS = ('bay', 'bench')


def _keys(d, path=''):
    if isinstance(d, dict):
        for k, v in d.items():
            yield f'{path}{k}', k
            yield from _keys(v, f'{path}{k}.')
    elif isinstance(d, list):
        for i, v in enumerate(d):
            yield from _keys(v, f'{path}{i}.')


def load(root=ROOT, path=SCENARIO):
    """The scenario, checked: it names only model operations and fields, sets no engineering value and has the eight DS-1 steps."""
    sc = tomllib.loads((Path(root) / path).read_text())
    bad = sorted(p for p, k in _keys(sc) if k in ENGINEERING_KEYS)
    if bad:
        raise ValueError(f'{path}: a scenario must not set engineering values: {bad}')
    ini = sc['initial']
    for f in cabin_air.FIELDS:
        if ini[f] not in cabin_air.FIELDS[f]:
            raise ValueError(f'{path}: initial {f} {ini[f]!r} is not a state of the model')
    ops = [ini['fault']] + [op for _, op in sc['reference']['events']]
    for op in ops:
        if op not in cabin_air.OPERATIONS:
            raise ValueError(f'{path}: {op!r} is not an operation of the model')
    for st in sc['steps']:
        for c in st['done']:
            kind, _, value = c.partition(':')
            ok = (kind == 'at' and value in POINTS) or (kind == 'flag' and value in FLAGS) or \
                 (kind in cabin_air.FIELDS and value in cabin_air.FIELDS[kind])
            if not ok:
                raise ValueError(f"{path}: step {st['id']}: unknown condition {c!r}")
    ids = [st['id'] for st in sc['steps']]
    if ids != ['recognize', 'inspect', 'diagnose', 'isolate', 'retrieve', 'repair', 'restore', 'verify']:
        raise ValueError(f'{path}: DS-1 has the eight tutorial steps in order, got {ids}')
    if sc['scenario'].get('scored'):
        raise ValueError(f'{path}: Phase 1 is unscored')
    return sc


def begin(sc, p):
    """The model state the trainee meets: the initial state, the fault, then fault_lead_h ship hours with no input."""
    ini = sc['initial']
    st = cabin_air.start(p, mode=ini['mode'], fan=ini['fan'], spare=ini['spare'])
    reason = cabin_air.operate(st, ini['fault'])
    assert not reason, reason
    cabin_air.step(st, p, float(ini['fault_lead_h'])*3600.0)
    # the trainee's clock starts here; the model's own clock and ledger keep running from the steady state
    return st


def watch(st, p, ship_h, dt=60.0):
    """The projected stability watch: the same model advanced ship_h hours with no input. Returns the verdict and its evidence."""
    x_max = 0.0; reached = False
    n = int(round(ship_h*3600.0/dt))
    for _ in range(n):
        cabin_air.step(st, p, dt)
        x = cabin_air.readout(st, p)['x']
        x_max = max(x_max, x)
        reached = reached or x > p['co2_max']
    r = cabin_air.readout(st, p)
    x_ss = cabin_air.steady_x(p) if r['removing'] else None
    ok = r['removing'] and not reached and r['x'] <= p['co2_target'] and x_ss is not None and x_ss <= p['co2_target']
    return dict(passed=bool(ok), x_end=r['x'], x_max=x_max, steady_x=x_ss, removing=r['removing'], dxdt_per_h=r['dxdt_per_h'])


def reference(sc, p, dt=1.0):
    """The ideal run at model level: begin, the reference events at their ship times (1 s steps), then the watch at 60 s steps.
    Godot replays the same and must agree within cabin_air.TOLERANCE."""
    st = begin(sc, p)
    t0 = st['t_s']
    events = [(t0+float(t), op, '') for t, op in sc['reference']['events']]
    out = []
    end = events[-1][0]
    while True:
        while events and st['t_s'] >= events[0][0]-1e-9:
            t, op, _ = events.pop(0)
            reason = cabin_air.operate(st, op)
            assert not reason, (op, reason)
            out.append(dict(t_s=st['t_s']-t0, op=op, m_kg=st['m_kg'], mode=st['mode'], fan=st['fan'], spare=st['spare']))
        if st['t_s'] >= end-1e-9:
            break
        cabin_air.step(st, p, dt)
    w = watch(st, p, float(sc['watch']['ship_h']))
    return dict(start_m_kg=begin(sc, p)['m_kg'], events=out, watch=w, end_m_kg=st['m_kg'], ledger_kg=cabin_air.ledger_error(st))


def contract(root=ROOT):
    import life_support
    import spec
    sc = load(root)
    p = cabin_air.params(spec.load(Path(root))[0], life_support.load(Path(root)))
    return dict(schema=SCHEMA, version=VERSION, notice='SIMULATION: a Deadship training scenario (PROTOTYPE, unscored). It sets no '
                'engineering value; the CO2 model (wf_cabin_air.json) owns them.', source=SCENARIO, scenario=sc,
                model=dict(file=cabin_air.FILE, schema=cabin_air.SCHEMA, version=cabin_air.VERSION), reference=reference(sc, p),
                reference_dt_s=dict(events=1.0, watch=60.0))


def write(root, out):
    Path(out).write_text(json.dumps(contract(root), separators=(',', ':'))+'\n')    # compact: the play download has a byte budget


def main(argv):
    c = contract(); ref = c['reference']; sc = c['scenario']
    p = cabin_air.params()
    x0 = ref['start_m_kg']/cabin_air.M_CO2/p['n_mol']
    print(f"{sc['scenario']['id']} {sc['scenario']['name']}: {len(sc['steps'])} steps, time x{sc['time']['scale']:g}, watch {sc['watch']['ship_h']:g} h "
          f"at x{sc['time']['watch_scale']:g}")
    print(f"start: fan failed {sc['initial']['fault_lead_h']:g} h ago, CO2 {100*x0:.3f} %; control limit in "
          f"{cabin_air.hours_between(p, x0, p['co2_max']):.2f} h ship time ({cabin_air.hours_between(p, x0, p['co2_max'])*3600/sc['time']['scale']/60:.1f} min real)")
    for e in ref['events']:
        print(f"  +{e['t_s']/3600:.2f} h {e['op']:14s} CO2 {100*e['m_kg']/cabin_air.M_CO2/p['n_mol']:.3f} %  {e['mode']}/{e['fan']}/{e['spare']}")
    w = ref['watch']
    print(f"watch: {'PASS' if w['passed'] else 'FAIL'}, end {100*w['x_end']:.3f} %, max {100*w['x_max']:.3f} %, steady {100*(w['steady_x'] or 0):.3f} %")
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
