"""FPS V1.1 release readiness, item 1: what the cluster frame's +83 t (V1 1,353 t -> V1.1 1,436 t) does to mass, centre of mass,
acceleration, structural loads and the mission, against the same numbers at V1 (dd4a64c).

Study code (work/, not read by the build). The ship's canonical mass budget (physics.mass_budget, B02 mass_model, operating_point) does not
read the Vertex cluster at all: the drive is the 250 t 'drive_package' allowance. So this script answers two questions and keeps them apart:
  canon      the canonical numbers, which V1.1 cannot change (nothing in them reads vertex_*); shown to prove they are unchanged;
  as-modeled the same calculations with the modeled Vertex mass placed on the ship (a copy of the spec, never written back):
             (a) the V1.1 frame delta alone (+83 t at the frame's own centroid), and (b) the whole modeled cluster replacing the 250 t
             allowance, the context the delta sits in.
Mission targets (0.016 c, delta-v, the drive's power cap, the owner's case E) are held; only the consequences move.

    python3 lab/studies/fuel-propellant/readiness.py [repo_root [v1_frame_t]] > out.json
"""
import copy
import json
import math
import sys
from pathlib import Path

ROOT = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT/'src/wayfarer'))
from spec import load                                     # noqa: E402
import mass_model as mm                                   # noqa: E402
import operating_point as op                              # noqa: E402
import vertex_cluster as vc                               # noqa: E402
import vertex_engine as ve                                # noqa: E402
import vertex_structure as vs                             # noqa: E402

G0 = 9.80665


def frame_centroid(s):
    """Mass and centroid of the cluster frame's structure parts (the same volumes vertex_structure.frame_mass sums)."""
    mt = ve.config(s)['materials']; rho = mt['density_kg_m3']['structure']*mt['solid_fraction']['structure']; M = 0.0; c = [0.0]*3
    for p in vc.frame(s):
        if p['material'] != 'structure':
            continue
        m = ve._volume(p)*rho; pts = ve.mesh_of(p)[0]
        if p.get('placement'):
            pl = vc.placements(s)[p['placement']-1]; pts = [vc.to_ship(pl, q) for q in pts]
        mid = [sum(q[k] for q in pts)/len(pts) for k in range(3)]
        M += m; c = [a+m*b for a, b in zip(c, mid)]
    return M, [a/M for a in c]


def engines_centroid(s):
    """The four engines as point masses at their collar centres (ship frame)."""
    est = ve.stations(s); mid = (est['collar_fwd']+est['collar_aft'])/2; m = ve.mass_estimate(s)['total_kg']
    return [(m, vc.to_ship(pl, (mid, 0.0, 0.0))) for pl in vc.placements(s)]


def with_extra(s, extra_kg, parts):
    """A spec copy whose end-of-mission ship carries extra_kg more (the cluster mass is dry, so it stays to burnout)."""
    t = copy.deepcopy(s); t['physics']['operating_point']['protected_and_operational_kg'] += extra_kg
    return t, parts


def account(s, extra_parts, label):
    """Mission, burn and placed-mass numbers with extra point masses (kg, (x, y, z)) added to the dry ship."""
    extra = sum(m for m, _ in extra_parts)
    t = copy.deepcopy(s); t['physics']['operating_point']['protected_and_operational_kg'] += extra
    mi = op.mission(t); b = op.burn(t)
    dry = mm.dry_parts(t)
    # the copy's protected+operational grew, so dry_parts put `extra` into the unallocated operating inventory: take it back out and
    # place the extra where it really is
    for p in dry:
        if p['name'] == 'operating_inventory':
            p['m'] -= extra
            break
    dry += [mm._part(f'{label}_{k}', m, c[0]-0.5, c[0]+0.5, ['point'], (c[1], c[2])) for k, (m, c) in enumerate(extra_parts)]
    d = mm.totals(dry)
    P = mi['propellant_kg']; k = P/op.mission(s)['propellant_kg']    # stores scale with the mission propellant (the vessels' fill grows)
    cap = {}
    for c in mm.tank_capacity(s):
        cap[c['species']] = cap.get(c['species'], 0.0)+c['cap_kg']
    import fuel_storage as fst
    inv = fst.inventory(s); fill = {sp: inv[fst.INV_KEY[sp]]*k/cap[sp] for sp in cap}
    # departure and burnout: propellant in the vessels (balanced), drained to the burnout reserve as mass_model.burn_states does
    states = []
    for left in (1.0, 1.0-(b['departure_mass_kg']-b['burnout_mass_kg'])/P):
        st = mm.stores_at(t, left*k)
        states.append(mm.totals(dry+mm.propellant_parts(t, st['he3'], st['d2'], st['h2'], True)))
    return dict(extra_t=extra/1e3, propellant_t=P/1e3, departure_t=mi['departure_mass_kg']/1e3, end_t=mi['end_mass_kg']/1e3,
                added_tank_t=mi['added_tank_kg']/1e3, burn_days=b['duration_d'], accel_g=b['accel_g'], thrust_MN=b['peak_thrust_N']/1e6,
                distance_AU=b['distance_AU'], fusion_PJ=b['fusion_energy_J']/1e15, peak_fusion_TW=b['peak_fusion_power_W']/1e12,
                dry_cg_x=d['cg_m'][0], dry_lateral_mm=d['lateral_m']*1e3,
                departure_cg_x=states[0]['cg_m'][0], burnout_cg_x=states[1]['cg_m'][0], departure_lateral_mm=states[0]['lateral_m']*1e3,
                I_pitch_departure=states[0]['I_pitch'], I_roll_departure=states[0]['I_roll'], vessel_fill=fill,
                fits_vessels=all(f <= 1.0 for f in fill.values()))


def structure(s):
    R = vs.cluster_members(s); cases = {}
    for c, d in R['cases'].items():
        cases[c] = {g: dict(u=round(v['u'], 3), member=v['row']['name'] if v['row'] else None) for g, v in d['groups'].items()}
    sets, _ = vs.cluster_load_sets(s); f = vs.fe_cluster(s, sets['LC01_THRUST_ALL'])
    rings = vc.ring_nodes(s); est = ve.stations(s)
    ties = []
    for p in vc.frame(s):
        if 'Tie' not in p['name']:
            continue
        a, b = p['points'][0], p['points'][-1]
        k = min(range(len(rings)), key=lambda i: math.dist(b, rings[i]))
        ties.append(dict(name=p['name'], length_m=round(math.dist(a, b), 2), radius_m=p['radius'], ring_node=k,
                         foot_to_node_m=round(math.dist(b, rings[k]), 3),
                         angle_to_axis_deg=round(math.degrees(math.acos(abs(b[0]-a[0])/math.dist(a, b))), 1)))
    tie_rows = {r['name']: r for r in f['rows'] if 'Tie' in r['name']}
    for t in ties:
        r = tie_rows.get(t['name'], {}); t['lc01_axial_MN'] = round(r.get('N', 0.0)/1e6, 3); t['lc01_u'] = round(r.get('u', 0.0), 3)
    return dict(cases=cases, stiffness_N_m=R['stiffness_N_m'], rocking_Hz=R['frequency_Hz'], magnetic_margin=R['magnetic_margin'],
                thrust_per_engine_MN=sets and vs.cluster_load_sets(s)[1]['thrust_N']/1e6, ties=ties, elements=f['elements'])


def main():
    s = load(ROOT)[0]
    m_frame, c_frame = frame_centroid(s); eng = engines_centroid(s); m_eng = sum(m for m, _ in eng)
    canon = account(s, [], 'none')
    budget = {i['id']: i['mass_kg'] for i in s['physics']['mass_budget']['items']}['drive_package']
    out = dict(root=str(ROOT), frame_t=m_frame/1e3, frame_centroid_m=c_frame, engines_t=m_eng/1e3, engine_each_t=m_eng/4e3,
               cluster_t=(m_frame+m_eng)/1e3, drive_allowance_t=budget/1e3, canon=canon,
               whole_cluster=account(s, [(m_frame-budget*m_frame/(m_frame+m_eng), c_frame)] +
                                     [(m-budget*m/(m_frame+m_eng), c) for m, c in eng], 'cluster'),
               structure=structure(s), pulse_Hz=None)
    if len(sys.argv) > 2:                                   # the V1 frame mass (t): the V1.1 delta alone, at the frame's centroid
        d = m_frame-float(sys.argv[2])*1e3
        out['frame_delta'] = account(s, [(d, c_frame)], 'frame_delta')
    if 'flank_tie' in str(out['structure']['cases']):         # V1.1 only (the V1 frame has the ring ties)
        out['ship_thrust'] = {f'{a:.3f} g': ship_thrust_cases(s, a) for a in (out['whole_cluster']['accel_g'][1], canon['accel_g'][1])}
    try:
        import vertex_magnet as vm
        out['pulse_Hz'] = vm.plasma(s)['pulse_Hz']
    except Exception as e:                                  # noqa: BLE001
        out['pulse_Hz'] = str(e)
    print(json.dumps(out, indent=1, default=float))



def ship_thrust_cases(s, accel_g):
    """Extra load sets (not in vertex_structure's 1.2 sets, which carry the engine's own C-10 thrust): each engine pushing its share of
    the ship operating point's thrust (operating_point.burn peak), alone, against its own inertia at the given ship acceleration, and with
    the NOMINAL inter-engine field. Governing utilisation per member group."""
    sets, mags = vs.cluster_load_sets(s); pls = vc.placements(s); n = len(pls)
    T = op.burn(s)['peak_thrust_N']/n; m_e = ve.mass_estimate(s)['total_kg']
    add = lambda a, b: tuple(x+y for x, y in zip(a, b))
    out = {}
    for name, inertia, field in (('SHIP_THRUST', False, False), ('SHIP_THRUST+INERTIA', True, False), ('SHIP_THRUST+INERTIA+FIELD_NOMINAL', True, True)):
        loads = {}
        for pl in pls:
            F = vc.mul(pl['axes'][0], T)
            if inertia:
                F = add(F, (-m_e*accel_g*G0, 0.0, 0.0))
            M = (0.0, 0.0, 0.0)
            if field:
                F = add(F, mags['nominal'][pl['n']][0]); M = mags['nominal'][pl['n']][1]
            loads[pl['n']] = (F, M)
        r = vs.fe_cluster(s, loads); g = {}
        for row in r['rows']:
            if row['u'] > g.get(row['group'], (0.0, ''))[0]:
                g[row['group']] = (round(row['u'], 3), row['name'])
        out[name] = g
    return dict(thrust_per_engine_MN=T/1e6, engine_thrust_C10_MN=mags['thrust_N']/1e6, accel_g=accel_g, cases=out)



if __name__ == '__main__':
    main()
