"""T05 Stage A screening (study code, NON-CANON). Pure Python, no Blender.

  python3 work/vertex-blender/screen.py        # about 5 s; writes work/vertex-blender/screen.json

Reads the generation overrides through lab/variants/vertex-drive/convergence.py (registry/generations.toml), solves each drawn generation
with the FDP-1 calculator (the same call convergence.py makes), and the canonical datums through src/wayfarer/layout.py. It computes only
what the Stage A plan needs to fix the geometry requirements:
  1. per-generation envelopes and extents (what Stage B will draw),
  2. closure-coil positions at each generation's stand-off (T03 design C_W15: polar 20/40 deg on the stand-off sphere),
  3. radiator-architecture alternatives for V4 (planform, tip radius, frontal edge, mass deltas),
  4. irradiance from the 1800 K hot band and the warm field on habitat ring A and on closure coil C1,
  5. in-plane root loads on a V4 wing at peak acceleration.
Nothing here feeds back into the calculator; every number is a screening estimate (label MODEL or EXTRAPOLATION in the output).
"""
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [str(ROOT/'lab/variants/vertex-drive'), str(ROOT/'src/wayfarer'), str(ROOT/'src')]
import convergence as cv               # noqa: E402  (imports lab/variants/fdp1/run.py as cv.fdp1)
import spec, layout, habitat_ring       # noqa: E402

SIGMA = 5.670374419e-8
EPS = 0.9
DRAWN = ('V0', 'V4', 'V5')
T03 = json.loads((ROOT/'lab/variants/vertex-drive/studies/nozzle/results/nozzle_results.json').read_text())['designs']['C_W15']


def canon():
    s = spec.load()[0]
    o = layout.origins(s)
    half = habitat_ring.sweep_half(s)
    fs = s['prototype']; fm = s['fuel_storage']['farm']
    hab = s['habitat']
    r_out = hab['outer_radius']['value'] if isinstance(hab['outer_radius'], dict) else hab['outer_radius']
    return {'datums_x_m': o, 'body_x_m': [o['AFT'], o['FWD']], 'ring_a_x_m': o['RING_A'], 'ring_b_x_m': o['RING_A']+6.0,
            'ring_sweep_half_m': half, 'ring_outer_r_m': r_out, 'ring_a_aft_face_x_m': o['RING_A']-half,
            'hot_blades': {'x_m': [o['RADIATOR_AFT'], o['RADIATOR_FRONT']], 'r_m': [6.5, 37.0], 'az_deg': [30.0, 150.0, 270.0], 'T_K': 1800.0},
            'dock_primary': {'x_m': layout.at(s, fs['dock_x']), 'az_deg': fs['dock_primary_angle_deg']},
            'dock_service': {'x_m': layout.at(s, fs['dock_x']), 'az_deg': fs['dock_service_angle_deg']},
            'airlock': {'x_m': layout.at(s, fs['airlock_x']), 'az_deg': fs['airlock_angle_deg']},
            'tank_farm_x_m': [layout.at(s, fm['x_aft_apex']), layout.at(s, fm['x_fwd_apex'])],
            'forward_shield': {'r_m': 45.0, 'note': 'bow assembly ahead of the farm; position from the built asset in Stage B'},
            'source': 'data/wayfarer_3d.toml through src/wayfarer/layout.py (datums, fuel_storage.farm, docks); docs/MODEL.md (blade radii, '
                      'shield radius). The X 99.40 m dock figure in lab/variants/fdp1/NOTES.md and planning/T05-BLENDER.md is stale (pass 7).'}


def solve(gen):
    ov = cv.generations()[gen]['overrides']
    return cv.fdp1.solve('baseline', {k: v for k, v in ov.items() if k != 'vertex'})


def envelope(R):
    lay = R['layout']; th = R['thermal']; w = th['layouts'][th['selected_layout']]; sh = R['shield']
    xB = lay['x_burn']; Rs = lay['R_s']
    coils = []
    for L in T03['loops'][:2]:                      # C1, C2 on the stand-off sphere at their polar angles (scaled with R_s)
        p = math.radians(L['polar_deg'])
        scale = Rs/L['distance_m']
        coils.append({'name': L['name'].split('@')[0], 'x_m': xB+Rs*math.cos(p), 'r_m': Rs*math.sin(p),
                      'winding_minor_m': L['winding_minor_m']*scale, 'envelope_r_m': [2.0*scale, 3.2*scale]})
    loops = [{'name': L['name'], 'x_m': L['x'], 'r_m': L['r'], 'envelope_r_m': L['envelope_radius_m']} for L in R['nozzle']['loops']]
    tb = R['tanks']['options']['T-B']
    return {'x_burn_m': xB, 'stand_off_m': Rs, 'x_shield_aft_m': lay['x_shield_aft'], 'x_shield_fwd_m': lay['x_shield_fwd'],
            'x_module_fwd_m': lay['x_module_fwd'], 'module_r_m': lay['module_radius'], 'shield_r_hw_m': sh['radius_hw_aft_m'],
            'hardware_cone_deg': sh['hardware_half_angle_deg'], 'crew_cone_deg': sh['crew_half_angle_deg'], 'loops': loops,
            'closure_coils': coils,
            'wing': {'layout': th['selected_layout'], 'az_deg': w['azimuths_deg'], 'x_m': [lay['wing_aft_x'], lay['wing_forward_x']],
                     'chord_m': lay['wing_length'], 'hot_band_r_m': [w['warm_root_radius_m']-w['hot_band_m'], w['warm_root_radius_m']],
                     'warm_r_m': [w['warm_root_radius_m'], w['tip_radius_m']], 'tip_r_m': w['tip_radius_m'],
                     'warm_T_K': th['radiators']['warm']['T_K'], 'hot_T_K': th['radiators']['hot']['T_K'],
                     'warm_planform_m2': w['total_planform_m2'], 'all_layouts': {k: {q: v[q] for q in ('wings', 'tip_radius_m', 'area_penalty')
                                                                                  if q in v} for k, v in th['layouts'].items() if k != 'ENVELOPE'}},
            'drivers': {'galleries': R['drivers']['galleries'], 'r_m': R['drivers']['radius_m'], 'x_m': [R['drivers']['x_aft'], R['drivers']['x_fwd']],
                        'linac_m': R['drivers']['linac_length_m']},
            'injection_path_m': R['injection']['path_m'], 'pulse_Hz': R['fusion']['pellet_rate_Hz'],
            'launcher_one_in_flight_m_s': R['injection']['path_m']*R['fusion']['pellet_rate_Hz'],
            'tanks_TB': {'vessels': len(tb['vessels']), 'added_length_m': tb['added_length_m'], 'bow_shift_m': tb['added_length_m']},
            'low_loop_m2': th['low_loop']['area_m2'], 'departure_t': cv.fdp1.summary(R)['departure_t']}


def irradiance(rect, T, recv, normal, n=160):
    """W/m2 on a differential receiver from one face of a planar rectangle in z=0 (x0..x1, y0..y1) at temperature T, emissivity EPS.
    Grid is geometric toward the receiver's nearest corner so the near edge is resolved."""
    x0, x1, y0, y1 = rect; xr, yr, zr = recv; nx, ny, nz = normal
    if abs(zr) < 1e-9:
        return 0.0
    def g(a, b, near, k):                        # k points from a to b, dense near `near`
        if near <= a:
            return [a+(b-a)*((i+0.5)/k)**3 for i in range(k)], None
        if near >= b:
            return [b-(b-a)*((i+0.5)/k)**3 for i in range(k)], None
        return [a+(b-a)*(i+0.5)/k for i in range(k)], None
    xs, _ = g(x0, x1, xr, n); ys, _ = g(y0, y1, yr, n)
    # cell widths from sorted points
    def widths(p):
        q = sorted(p); e = [q[0]-(q[1]-q[0])/2]+[(q[i]+q[i+1])/2 for i in range(len(q)-1)]+[q[-1]+(q[-1]-q[-2])/2]
        lo, hi = min(x0, y0), 0
        return q, [e[i+1]-e[i] for i in range(len(q))]
    xs, dx = widths(xs); ys, dy = widths(ys)
    tot = 0.0
    for xe, wx in zip(xs, dx):
        for ye, wy in zip(ys, dy):
            vx, vy, vz = xe-xr, ye-yr, -zr          # receiver -> emitter
            s2 = vx*vx+vy*vy+vz*vz; s = math.sqrt(s2)
            c1 = abs(zr)/s                          # emitter face normal is +-z, facing the receiver
            c2 = (vx*nx+vy*ny+vz*nz)/s
            if c2 > 0:
                tot += c1*c2/(math.pi*s2)*wx*wy
    return EPS*SIGMA*T**4*tot, tot


def ring_load(env, C):
    """Worst irradiance on ring A's aft sweep face (normal -x) and outer rim (radial normal), az 5..85 deg off the wing plane."""
    w = env['wing']; xa = C['ring_a_aft_face_x_m']; xr_rim = C['ring_a_x_m']; R = C['ring_outer_r_m']
    out = {}
    for band, (r0, r1), T in (('hot_band', w['hot_band_r_m'], w['hot_T_K']), ('warm_field', (w['warm_r_m'][0], min(w['warm_r_m'][1], w['warm_r_m'][0]+3000)), w['warm_T_K'])):
        best = {'aft_face': (0, None), 'rim': (0, None)}
        for azd in (5, 15, 30, 45, 60, 75, 85):
            a = math.radians(azd)
            for rr in (R-2.0, R):
                p = (xa, rr*math.cos(a), rr*math.sin(a))
                E, F = irradiance((w['x_m'][0], w['x_m'][1], r0, r1), T, p, (-1, 0, 0), n=90)
                if E > best['aft_face'][0]:
                    best['aft_face'] = (E, {'az_deg': azd, 'r_m': rr, 'view_factor': F})
            p = (xr_rim, R*math.cos(a), R*math.sin(a))
            E, F = irradiance((w['x_m'][0], w['x_m'][1], r0, r1), T, p, (0, math.cos(a), math.sin(a)), n=90)
            if E > best['rim'][0]:
                best['rim'] = (E, {'az_deg': azd, 'view_factor': F})
        out[band] = {k: {'W_m2': v[0], **(v[1] or {})} for k, v in best.items()}
    return out


def blade_ring_load(C):
    """Reference: the canonical 1800 K blades on ring A's aft face (blade rotated into z=0 frame: worst point 30-60 deg off a blade)."""
    b = C['hot_blades']; xa = C['ring_a_aft_face_x_m']; R = C['ring_outer_r_m']
    best = 0.0
    for azd in (5, 15, 30, 45, 60):
        a = math.radians(azd)
        E, _ = irradiance((b['x_m'][0], b['x_m'][1], b['r_m'][0], b['r_m'][1]), b['T_K'], (xa, R*math.cos(a), R*math.sin(a)), (-1, 0, 0), n=90)
        best = max(best, E)
    return best*3                                  # three blades, upper bound (each counted at its own worst angle)


def coil_load(env):
    """Irradiance on closure coil C1 where it crosses the wing plane (y = r_C1), from the hot band face, receiver normal +z/-x mix."""
    w = env['wing']; c = env['closure_coils'][0]
    out = {}
    for lift in (c['envelope_r_m'][1], 2*c['envelope_r_m'][1]):
        for nm, n in (('facing_fwd', (1, 0, 0)), ('facing_wing_plane', (0, 0, -1))):
            p = (c['x_m'], c['r_m'], lift)
            if nm == 'facing_fwd':
                # emitter at x > receiver: receiver normal +x
                E, F = irradiance((w['x_m'][0], w['x_m'][1], w['hot_band_r_m'][0], w['hot_band_r_m'][1]), w['hot_T_K'], p, n, n=90)
            else:
                E, F = irradiance((w['x_m'][0], w['x_m'][1], w['hot_band_r_m'][0], w['hot_band_r_m'][1]), w['hot_T_K'], p, n, n=90)
            out[f'{nm}_z{lift:.1f}m'] = {'W_m2': E, 'view_factor': F}
    out['gap_coil_centre_to_wing_aft_edge_m'] = w['x_m'][0]-c['x_m']
    return out


def radiator_alternatives(env, R, gens):
    """V4 warm load on alternative architectures. Area never shrinks for view factor (AGENTS.md); calculator-closed rows say so."""
    w = env['wing']; A = w['warm_planform_m2']; L = w['chord_m']; root = w['warm_r_m'][0]; Tw = w['warm_T_K']
    Q = R['thermal']['circuits']['warm_total_W']
    rows = []
    def tip(area, n, chord, root_r=root):
        return root_r+area/(n*chord)
    rows.append({'id': 'R0', 'name': 'W2 flat wings, droplet sheet 0.5 kg/m2 (V4 as calculated)', 'planform_m2': A, 'tip_r_m': w['tip_r_m'],
                 'closed_by_calculator': True, 'label': 'MODEL'})
    for k, v in w['all_layouts'].items():
        if k == 'W2':
            continue
        rows.append({'id': f'R1-{k}', 'name': f'{k}: {v["wings"]} wings, view-factor penalty x{v["area_penalty"]:.2f}', 'planform_m2': A*v['area_penalty'],
                     'tip_r_m': v['tip_radius_m'], 'closed_by_calculator': False, 'label': 'MODEL (layout only; mass not re-closed)'})
    # tandem wing: second W2 pair on the T-B stretch only (5 m ahead of the existing farm front, clear of the docks and airlock, to the
    # stretched farm front), so it never meets the rings, docks or airlock
    farm = gens['canon']['tank_farm_x_m']
    xf0 = farm[1]+5.0; xf1 = farm[1]+env['tanks_TB']['added_length_m']
    L2 = xf1-xf0
    rows.append({'id': 'R2', 'name': f'Tandem W2: aft wing {L:.0f} m chord + forward wing {L2:.0f} m chord (x {xf0:.0f} to {xf1:.0f})',
                 'planform_m2': A, 'tip_r_m': root+A/(2*(L+L2)), 'closed_by_calculator': False, 'label': 'EXTRAPOLATION (geometry only)',
                 'note': 'only exists with the T-B stretch; forward wing lies in the forward shield dust shadow only inside r 45 m; edge-on to the burn'})
    # warm-band split already in V4 (VTX-07E): show the temperature lever from the convergence cases
    rows.append({'id': 'R3', 'name': 'Equivalent warm temperature 670 K (V4_warm_band)', 'tip_r_m': 6.7e3, 'closed_by_calculator': True,
                 'label': 'MODEL (convergence.json V4_warm_band; tip from T05_HANDOFF)'})
    rows.append({'id': 'R4', 'name': 'Driver efficiency 0.45 (V4_driver_band)', 'tip_r_m': 3.4e3, 'closed_by_calculator': True,
                 'label': 'MODEL (convergence.json V4_driver_band; tip from T05_HANDOFF)'})
    # heat pump to 1000 K: ideal Carnot work
    Th = 1000.0; W = Q*(Th/Tw-1); Aq = (Q+W)/(2*EPS*SIGMA*Th**4)
    rows.append({'id': 'R5', 'name': 'Heat pump lifting the warm loop to 1000 K (ideal Carnot)', 'planform_m2': Aq, 'tip_r_m': tip(Aq, 2, L),
                 'extra_electric_W': W, 'closed_by_calculator': False, 'label': 'EXTRAPOLATION',
                 'note': f'needs {W/1e9:.0f} GW extra electric at the Carnot limit (x2 at a real COP), against about 110 GW driver input: rejected'})
    # cone radiator with apex at the burn point (edge-on), outer face only
    for th_deg in (15.0, 30.0):
        t = math.radians(th_deg); need = 2*A                       # one-sided against the wing's two-sided planform
        l1 = env['stand_off_m']+40.0; l2 = math.sqrt(need/(math.pi*math.sin(t))+l1*l1)
        frontal = math.pi*((l2*math.sin(t))**2-(l1*math.sin(t))**2)
        rows.append({'id': f'R6-{int(th_deg)}', 'name': f'Coaxial cone radiator, apex at the burn, half-angle {th_deg:.0f} deg', 'slant_m': [l1, l2],
                     'mouth_r_m': l2*math.sin(t), 'frontal_m2': frontal, 'closed_by_calculator': False, 'label': 'EXTRAPOLATION',
                     'note': 'edge-on to the burn, but its frontal area to the dust stream is the whole annulus: rejected on dust'})
    # propellant as a heat sink
    mdot = R['closure'].get('mdot_kg_s') or (R['closure']['thrust_MN']*1e6/(R['closure']['ve_km_s']*1e3))
    rows.append({'id': 'R7', 'name': 'Propellant as heat sink (regenerative)', 'sink_W': mdot*14e3*600, 'closed_by_calculator': False,
                 'label': 'EXTRAPOLATION', 'note': f'{mdot:.3f} kg/s of propellant absorbs about {mdot*14e3*600/1e6:.1f} MW against {Q/1e9:.1f} GW: rejected'})
    # frontal edge (dust): per cm of leading-edge thickness, both wings
    for r in rows:
        if 'tip_r_m' in r and r['id'].startswith(('R0', 'R1', 'R2', 'R3', 'R4', 'R5')):
            n = 2 if not r['id'].startswith('R1') else int(r['name'].split(':')[1].split()[0])
            r['leading_edge_m2_per_cm'] = n*(r['tip_r_m']-10.0)*0.01*(2 if r['id'] == 'R2' else 1)
    return rows, Q


def mitigations(env, C):
    """Chordwise grading (Stage B requirement candidates): keep the same hot-band area but end it at the canon hot-blade front
    (RADIATOR_FRONT), and/or start it forward of closure coil C1. Returns the ring A and C1 irradiance for each."""
    w = env['wing']; x0, x1 = w['x_m']; r0, r1 = w['hot_band_r_m']; A = (x1-x0)*(r1-r0)
    xa = C['ring_a_aft_face_x_m']; R = C['ring_outer_r_m']; c = env['closure_coils'][0]
    out = {}
    for nm, (h0, h1) in (('as_calculated', (x0, x1)), ('hot_aft_of_RADIATOR_FRONT', (x0, C['datums_x_m']['RADIATOR_FRONT'])),
                         ('hot_aft_of_RADIATOR_FRONT_and_20m_clear_of_C1', (c['x_m']+c['envelope_r_m'][1]+20.0, C['datums_x_m']['RADIATOR_FRONT']))):
        rr1 = r0+A/(h1-h0)
        ring = max(irradiance((h0, h1, r0, rr1), w['hot_T_K'], (xa, R*math.cos(math.radians(a)), R*math.sin(math.radians(a))), (-1, 0, 0), n=90)[0]
                   for a in (5, 15, 30, 45, 60, 75))
        coil = irradiance((h0, h1, r0, rr1), w['hot_T_K'], (c['x_m'], c['r_m'], c['envelope_r_m'][1]), (1, 0, 0), n=90)[0]
        out[nm] = {'hot_x_m': [h0, h1], 'hot_r_m': [r0, rr1], 'ring_A_aft_face_W_m2': ring, 'C1_W_m2': coil}
    return out


def wing_loads(env, R):
    w = env['wing']; a = 0.018730006731935773*9.80665
    span = w['tip_r_m']-w['hot_band_r_m'][0]
    m_sheet = w['warm_planform_m2']/2*0.5; m_hot = (w['hot_band_r_m'][1]-w['hot_band_r_m'][0])*w['chord_m']*1.5
    m_spar = 2*span*12.5
    m = m_sheet+m_hot+m_spar
    F = m*a; M = F*span/2
    return {'wing_mass_t': m/1e3, 'peak_accel_m_s2': a, 'in_plane_force_MN': F/1e6, 'root_moment_N_m': M,
            'chord_couple_MN': M/w['chord_m']/1e6, 'label': 'EXTRAPOLATION (uniform mass along span; in-plane cantilever; no dynamics)'}


def main():
    C = canon()
    out = {'canon': C, 'generations': {}}
    Rs = {}
    for g in DRAWN:
        R = solve(g); Rs[g] = R
        env = envelope(R)
        aft = min(L['x_m'] for L in env['loops']) - max(L['r_m'] for L in env['loops'])*math.tan(math.radians(20.0))*0
        env['extent_x_m'] = [min(L['x_m'] for L in env['loops']), C['body_x_m'][1]+env['tanks_TB']['bow_shift_m']]
        env['extent_span_m'] = 2*env['wing']['tip_r_m']
        env['ring_A_irradiance'] = ring_load(env, C)
        env['closure_coil_C1_irradiance'] = coil_load(env)
        out['generations'][g] = env
    out['canon_blades_on_ring_A_W_m2'] = blade_ring_load(C)
    out['V4_hot_band_mitigations'] = mitigations(out['generations']['V4'], C)
    out['V4_radiator_alternatives'], out['V4_warm_W'] = radiator_alternatives(out['generations']['V4'], Rs['V4'], {'canon': C})
    out['V4_wing_loads'] = wing_loads(out['generations']['V4'], Rs['V4'])
    out['solar_constant_1AU_W_m2'] = 1361.0
    (HERE/'screen.json').write_text(json.dumps(out, indent=1, default=float))
    g4 = out['generations']['V4']
    print('V4 extent x', [round(v, 1) for v in g4['extent_x_m']], 'span', round(g4['extent_span_m']))
    for g in DRAWN:
        e = out['generations'][g]
        print(g, 'ringA', {b: {k: round(v['W_m2']) for k, v in d.items()} for b, d in e['ring_A_irradiance'].items()},
              'C1', {k: (round(v['W_m2']) if isinstance(v, dict) else round(v, 1)) for k, v in e['closure_coil_C1_irradiance'].items()},
              'coils', [(c['name'], round(c['x_m'], 1), round(c['r_m'], 1)) for c in e['closure_coils']])
    print('canon blades on ring A', round(out['canon_blades_on_ring_A_W_m2']))
    for r in out['V4_radiator_alternatives']:
        print(r['id'], r['name'], {k: (round(v) if isinstance(v, float) else v) for k, v in r.items() if k not in ('id', 'name', 'note', 'label')})
    for k, v in out['V4_hot_band_mitigations'].items():
        print('mitigation', k, {q: ([round(t, 1) for t in u] if isinstance(u, list) else round(u)) for q, u in v.items()})
    print('wing loads', {k: (round(v, 3) if isinstance(v, float) else v) for k, v in out['V4_wing_loads'].items()})


if __name__ == '__main__':
    main()
