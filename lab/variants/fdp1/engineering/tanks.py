"""Fuel storage: the existing 13-vessel farm (canon geometry, unchanged) against the FDP-1 requirement, and three candidate layouts for
the added He-3 and D2 volume, drawn as ghosts. The required volumes, tank mass law, cooling and axial load are the four-burn calculator's
(tanks.compare); this module turns the deficit into vessels and positions. Nothing replaces the existing vessels; the hydrogen vessels
stay (idle in this scenario) and their dry mass is carried when keep_idle_hydrogen_vessels is set.

  T-A  aft stack: whole 13-slot bays between the hull and the equipment module (short feed lines; widens the shadow cone)
  T-B  forward stretch: whole bays ahead of the existing farm; the forward shield, Crown and EYE move forward by the added length
  T-C  outer ring: a third ring of L-class vessels around the existing farm, no stretch (outer radius exceeds the forward shield)
"""
import math

from .config import v

SPEC_KEY = {'helium-3': 'helium_3', 'deuterium': 'deuterium', 'hydrogen': 'hydrogen'}


def existing(s, mods):
    fs = mods['fuel_storage']; ts = fs.tanks(s)
    return [dict(t, liquid_m3=t['liquid_m3'], key=SPEC_KEY[t['species']]) for t in ts]


def deficit(r, ex):
    tk = r['tanks']; req = tk['required_m3']
    cap = {k: sum(t['liquid_m3'] for t in ex if t['key'] == k) for k in ('helium_3', 'deuterium', 'hydrogen')}
    return {k: max(0.0, req[k]-cap[k]) for k in req}, cap


def _bay_slots(ex):
    """The 13 cross-section slots of the existing farm (class, R, azimuth, envelope radius, liquid volume)."""
    return [{'cls': t['tank_class'], 'R': t['R'], 'az': t['azimuth_deg'], 'a_env': t['a_env'], 'a': t['a'], 'm3': t['liquid_m3']} for t in ex]


def _fill(slots_per_bay, need, n_max=20):
    """Fill bays: He-3 into L slots, D2 into M slots, then D2 overflow into free L slots. Returns [(bay, slot, species)]."""
    out = []; left = dict(need); bay = 0
    while (left['helium_3'] > 1e-6 or left['deuterium'] > 1e-6) and bay < n_max:
        for sl in [x for x in slots_per_bay if x['cls'] == 'L']:
            if left['helium_3'] > 1e-6:
                out.append((bay, sl, 'helium_3')); left['helium_3'] -= sl['m3']
            elif left['deuterium'] > 1e-6:
                out.append((bay, sl, 'deuterium')); left['deuterium'] -= sl['m3']
        for sl in [x for x in slots_per_bay if x['cls'] == 'M']:
            if left['deuterium'] > 1e-6:
                out.append((bay, sl, 'deuterium')); left['deuterium'] -= sl['m3']
            elif left['helium_3'] > 1e-6:
                out.append((bay, sl, 'helium_3')); left['helium_3'] -= sl['m3']
        bay += 1
    return out, bay


def _vessel(name, key, x0, x1, R, az, a_env, a, m3):
    c, sn = math.cos(math.radians(az)), math.sin(math.radians(az))
    return {'name': name, 'key': key, 'species': key, 'x0': x0, 'x1': x1, 'R': R, 'azimuth_deg': az, 'y': R*c, 'z': R*sn,
            'a_env': a_env, 'a': a, 'liquid_m3': m3}


def options(cfg, s, mods, r, lay):
    ex = existing(s, mods); need, cap = deficit(r, ex)
    x0e, x1e = min(t['x0'] for t in ex), max(t['x1'] for t in ex); Lb = x1e-x0e; gap = v(cfg['tanks']['bay_gap_m'])
    slots = _bay_slots(ex)
    out = {}
    fill, nb = _fill(slots, need)
    # T-A: bays aft of the hull attach (positions follow the layout's bay block)
    va = []
    for i, (bay, sl, key) in enumerate(fill):
        xa1 = lay['x_attach']-gap-bay*(Lb+gap); xa0 = xa1-Lb
        va.append(_vessel(f'FDP1_TA_Tank_B{bay+1}_{i:02d}_{key}', key, xa0, xa1, sl['R'], sl['az'], sl['a_env'], sl['a'], sl['m3']))
    out['T-A'] = {'vessels': va, 'bays': nb, 'added_length_m': nb*(Lb+gap), 'where': 'aft of the hull, ahead of the equipment module'}
    vb = []
    for i, (bay, sl, key) in enumerate(fill):
        xb0 = x1e+gap+bay*(Lb+gap); xb1 = xb0+Lb
        vb.append(_vessel(f'FDP1_TB_Tank_B{bay+1}_{i:02d}_{key}', key, xb0, xb1, sl['R'], sl['az'], sl['a_env'], sl['a'], sl['m3']))
    out['T-B'] = {'vessels': vb, 'bays': nb, 'added_length_m': nb*(Lb+gap), 'where': 'ahead of the existing farm; bow assembly moves forward'}
    # T-C: a third ring of L-class vessels on the existing bay length
    L0 = next(x for x in slots if x['cls'] == 'L'); Ro = v(cfg['tanks']['outer_ring_radius_m'])
    n_ring = int(2*math.pi*Ro/(2*L0['a_env']+1.0))
    vc = []; left = dict(need); k = 0
    for ring in range(4):
        R = Ro+ring*(2*L0['a_env']+1.0); n_ring = int(2*math.pi*R/(2*L0['a_env']+1.0))
        for j in range(n_ring):
            key = 'helium_3' if left['helium_3'] > 1e-6 else ('deuterium' if left['deuterium'] > 1e-6 else None)
            if key is None:
                break
            vc.append(_vessel(f'FDP1_TC_Tank_R{ring+1}_{j:02d}_{key}', key, x0e, x1e, R, 360.0*j/n_ring+(180.0/n_ring)*ring, L0['a_env'], L0['a'], L0['m3']))
            left[key] -= L0['m3']; k += 1
        if left['helium_3'] <= 1e-6 and left['deuterium'] <= 1e-6:
            break
    out['T-C'] = {'vessels': vc, 'bays': 0, 'added_length_m': 0.0, 'rings': ring+1, 'where': 'third vessel ring around the existing farm'}
    for k2, o in out.items():
        added = {sp: sum(t['liquid_m3'] for t in o['vessels'] if t['key'] == sp) for sp in ('helium_3', 'deuterium')}
        o['added_m3'] = added; o['count'] = len(o['vessels'])
        o['max_radius_m'] = max((t['R']+t['a_env'] for t in o['vessels']), default=0.0)
        o['spare_m3'] = {sp: added[sp]-need[sp] for sp in added}
    return {'existing': ex, 'existing_capacity_m3': cap, 'deficit_m3': need, 'options': out, 'bay_length_m': Lb}


def summary(cfg, r, opt, s):
    tk = r['tanks']; rho = s['fuel_storage']['density_kg_m3']
    idle = sum(t['liquid_m3'] for t in opt['existing'] if t['key'] == 'hydrogen')
    return {'required_m3': tk['required_m3'], 'existing_m3': tk['existing_m3'], 'ratio': tk['ratio'], 'outcome': tk['outcome'],
            'vessels_L_equivalent': tk['vessels_L_equivalent'], 'farm_length_m_same_section': tk['farm_length_m'],
            'tank_mass_kg': tk['tank_mass_kg'], 'cooling_W': tk['cooling_W'], 'axial_load_1p5g_N': tk['axial_load_N'],
            'axial_load_ratio_1p5g': tk['axial_load_ratio'], 'idle_hydrogen_m3': idle, 'deficit_m3': opt['deficit_m3'],
            'loaded_t': r['species_t'], 'density_kg_m3': rho}
