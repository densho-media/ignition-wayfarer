"""F01 torus load path and drawdown (pass 6, WORKING, Claude under the owner's delegation of 2026-10-31; S&E 15 OWN-F01-TORUS-LOADS-2026-10-31).

Uses the B02 placed propellant (mass_model, balanced per species) along the B01 burn. Standard library only.

- draw(s): each torus cell's load along the burn. Every cell only drains, so the balanced loading needs metered outlets per cell (a draw
  ratio), not transfers between cells.
- supports(s): each vessel's propellant plus a dry tank allowance at the burn's instantaneous acceleration, shared by its two bipods
  (fuel_storage.torus_struts); the leg forces from statics in the support's X-r plane, against yield (ultimate factor) and Euler
  buckling (knockdown) of the titanium leg tube. For comparison, the bending stress a radial strut of the same tube would carry.
- spine(s): the axial load the structure carries at a few stations, the mass forward of each station times the acceleration.

    python3 src/wayfarer/fuel_loads.py      # prints the result and writes references/p1_fuel_loads.json
"""
import json
import math
from pathlib import Path

import fuel_storage
import mass_model

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT/'references/p1_fuel_loads.json'


def q(s):
    return s['physics']['fuel_loads']


def _cells_at(s, frac):
    """Balanced cell loads (kg) with frac of the burn's deuterium and first-ignition hydrogen left."""
    inv = fuel_storage.cfg(s)['inventory_kg']
    d, _ = mass_model.balance(s, 'deuterium', inv['deuterium']*frac)
    h, _ = mass_model.balance(s, 'hydrogen', inv['hydrogen_reserve']+inv['hydrogen_first_ignition']*frac)
    return {r['name']: r['kg'] for r in d+h}


def schedule(s, steps=10):
    """Burn states: time, acceleration, and each cell's load. The burn fraction left follows mass_model.burn_states."""
    inv = fuel_storage.cfg(s)['inventory_kg']; out = []
    for st in mass_model.burn_states(s, steps):
        frac = (st['propellant_kg']-inv['hydrogen_reserve'])/(inv['helium_3']+inv['deuterium']+inv['hydrogen_first_ignition'])
        out.append(dict(t_s=st['t_s'], accel_m_s2=st['thrust_N']/st['mass_kg'], mass_kg=st['mass_kg'], cells=_cells_at(s, frac), parts_frac=frac))
    return out


def legs(s):
    """Unit vectors (x, r) from the apex to each foot, per support, from fuel_storage.torus_struts."""
    out = {}
    for st in fuel_storage.torus_struts(s):
        a, b = st['a'], st['b']; key = st['name'].rsplit('_', 1)[0]
        dx = a[0]-b[0]; dr = math.hypot(a[1], a[2])-math.hypot(b[1], b[2]); L = math.hypot(dx, dr)
        out.setdefault(key, dict(vessel=st['vessel'], radius=st['radius']))[st['side']] = dict(u=(dx/L, dr/L), L=L)
    return out


def supports(s, steps=10):
    p = q(s); t = fuel_storage.cfg(s)['torus']; cap, tor = mass_model.torus_capacity(s)
    dry = {}
    for c in cap:
        dry[c['vessel']] = dry.get(c['vessel'], 0.0)+p['tank_dry_fraction']*c['cap_kg']
    vessel_of = {c['name']: c['vessel'] for c in cap}
    r, w = t['strut_radius_m'], t['strut_wall_m']; A = 2*math.pi*r*w; I = math.pi*r**3*w; FS = p['ultimate_factor']
    worst = None
    for st in schedule(s, steps):
        if st['accel_m_s2'] <= 0:
            continue
        mv = {v: dry[v] for v in dry}
        for name, kg in st['cells'].items():
            mv[vessel_of[name]] += kg
        for key, sp in legs(s).items():
            P = mv[sp['vessel']]*st['accel_m_s2']/2                     # inertial load on this support, toward -X
            ua, uf = sp['Aft']['u'], sp['Fwd']['u']
            # apex equilibrium: Ta ua + Tf uf + (-P, 0) = 0 (T > 0 tension)
            D = ua[0]*uf[1]-ua[1]*uf[0]; Ta = (P*uf[1])/D; Tf = (-P*ua[1])/D
            for side, T in (('Aft', Ta), ('Fwd', Tf)):
                L = sp[side]['L']; Pcr = math.pi**2*p['strut_E_Pa']*I/L**2/p['buckling_knockdown']
                row = dict(support=key, side=side, t_s=st['t_s'], vessel_kg=mv[sp['vessel']], load_N=P, force_N=T, length_m=L,
                           stress_margin=p['strut_yield_Pa']/(abs(T)*FS/A)-1,
                           buckling_margin=(Pcr/(-T*FS)-1) if T < 0 else None)
                key2 = min(row['stress_margin'], row['buckling_margin'] if row['buckling_margin'] is not None else 1e9)
                if worst is None or key2 < worst[0]:
                    worst = (key2, row)
    # the old radial strut of the same tube, as a cantilever from the collar carrying the worst support load in bending
    Lr = tor['R']-tor['a']-6.5; Z = I/r
    radial = dict(length_m=Lr, bending_stress_Pa=worst[1]['load_N']*Lr/Z, yield_Pa=p['strut_yield_Pa'])
    return dict(tube=dict(radius_m=r, wall_m=w, area_m2=A, I_m4=I), dry_kg=dry, worst=worst[1], worst_margin=worst[0], radial_strut=radial)


def spine(s, stations=(-81.0, 0.0, 82.9, 96.1)):
    """Axial load at stations: the mass forward of each station times the acceleration, at burnout (peak) and at departure."""
    out = []
    for st in (mass_model.burn_states(s, 10)[i] for i in (1, -1)):
        parts = mass_model.dry_parts(s)
        a = st['thrust_N']/st['mass_kg']
        inv = fuel_storage.cfg(s)['inventory_kg']
        frac = (st['propellant_kg']-inv['hydrogen_reserve'])/(inv['helium_3']+inv['deuterium']+inv['hydrogen_first_ignition'])
        parts += mass_model.propellant_parts(s, inv['helium_3']*frac, inv['deuterium']*frac, inv['hydrogen_reserve']+inv['hydrogen_first_ignition']*frac)
        row = dict(t_s=st['t_s'], accel_m_s2=a, thrust_N=st['thrust_N'], stations={})
        for xs in stations:
            m = sum(pt['m']*min(1.0, max(0.0, (pt['x'][1]-xs)/(pt['x'][1]-pt['x'][0]))) if pt['x'][1] > pt['x'][0] else (pt['m'] if pt['x'][0] > xs else 0.0)
                    for pt in parts)
            row['stations'][str(xs)] = dict(mass_forward_kg=m, axial_N=m*a)
        out.append(row)
    return out


def report(s):
    sch = schedule(s); names = sorted(sch[0]['cells'])
    drains = {n: all(b['cells'][n] <= a['cells'][n]+1e-6 for a, b in zip(sch, sch[1:])) for n in names}
    sp = supports(s); fails = []
    if not all(drains.values()):
        fails.append('a torus cell must be refilled during the burn (crossfeed needed): ' + ', '.join(n for n, ok in drains.items() if not ok))
    if sp['worst_margin'] < 0:
        fails.append(f"torus bipod leg margin {sp['worst_margin']:.2f} < 0")
    return dict(status=q(s)['canon_status'], draw=dict(cells_drain_only=drains, departure={n: sch[0]['cells'][n] for n in names},
                burnout={n: sch[-1]['cells'][n] for n in names}), supports=sp, spine=spine(s), failures=fails)


def check(s):
    return report(s)['failures']


if __name__ == '__main__':
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from spec import load
    s = load()[0]; r = report(s)
    OUTPUT.write_text(json.dumps(r, indent=1, default=float)+'\n')
    print(json.dumps(r, indent=1, default=lambda x: round(x, 3)))
