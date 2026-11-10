"""Vertex feasibility gate 2, Task C (T05): shield-envelope geometry, dust limit and the twin-nozzle comparison. NON-CANON.

Run from the project root: python3 work/vertex-blender/gate2.py  ->  work/vertex-blender/gate2.json  (standard library, seconds)

What it does (tilt-plane and axisymmetric geometry only; mass convergence is T00's coupled.py, which these variants feed):
  farms     tank-farm radius, stretch length at the coupled propellant, aft-shield rim by FDP-1's rule
            rim = atan(R_farm / d_far + 1 m / d_shield) (T00, 2026-11-10), dust clearance to the canon r 45 forward shield,
            A1 leak clearance (leak inner edge minus rim), shield radius and area against the V4 shield
  standoff  the burn point moved aft so a wider farm keeps the 7.5 deg rim
  twin      parallel outrigger and splayed twin nozzles: loop interference, channel clearance against the planar radiator wings,
            the ship's angular size from each burn point, cosine loss, force and torque balance; conceptual only (brief: "a small
            conceptual comparison ... without adopting or fully detailing it")
Numbers it reads: t00_gate_handoff.json (9rsgog 43fac75), rev3.json (stretch), checks.json (wing aft edge).
"""
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
GATE = json.loads((HERE/'t00_gate_handoff.json').read_text())
ST3 = json.loads((HERE/'rev3.json').read_text())['stretch']
CHK = json.loads((HERE/'checks.json').read_text())
A1 = GATE['lanes']['A1_tilted_closure_RETAINED']; CS = GATE['coupled_ship']
XB = GATE['x_burn_m']
FARM_X_NEAR = 109.25                       # FDP-1 shield envelope 'existing_tank_farm' near end (ship X)
V4_FARM_R = 34.5
DUST_R = 45.0; DUST_CLEAR = 1.0            # canon forward shield r 45 (data/wayfarer_3d.toml forward_shield rationale), 1 m clearance
D_SHIELD = 65.0                            # shield plane for the rim rule, as T00 uses it (V4 W face 64.7-66 m; coupled 68.6 m gives r 42.0)
D_SHIELD_V4 = 65.0
LIMIT = A1['shadow_cone_limit_deg']
LEAK_C, LEAK_R = A1['leak_cone']['centre_polar_deg'], A1['leak_cone']['radius_deg']
LAM = (CS['spine']['shield']['farm_radius_m']/V4_FARM_R)**2       # coupled / Rev 4 propellant ratio used by T00 (2.73)
STRETCH_X0 = ST3['x_m'][0]; STRETCH_L_V4 = ST3['length_m']


def rim_deg(R_farm, d_far, d_shield=D_SHIELD):
    return math.degrees(math.atan(R_farm/d_far+1.0/d_shield))


# T00 A1 tilt rows (note 2026-11-10T07:27Z; gate2/cone.json on 9rsgog when pushed). beta: field set turned back so the net thrust is axial.
TILTS = [
    {'tilt_deg': 14, 'beta_deg': 2.68, 'leak_centre_deg': 10.83, 'leak_radius_deg': 2.99, 'rim_limit_deg': 7.50, 'C1_near_polar_deg': 8.68,
     'C1_near_z_m': 63.96, 'C1_near_r_m': 9.77, 'C1_envelope_polar_deg': 7.30, 'static_torque_GN_m': 52.6, 'shield_face_m': 65.0, 'valid': True},
    {'tilt_deg': 15, 'beta_deg': 2.88, 'leak_centre_deg': 11.65, 'leak_radius_deg': 2.97, 'rim_limit_deg': 8.35, 'C1_near_polar_deg': 7.88,
     'C1_near_z_m': 64.09, 'C1_near_r_m': 8.87, 'C1_envelope_polar_deg': 6.49, 'static_torque_GN_m': 60.1, 'shield_face_m': 68.2, 'valid': True},
    {'tilt_deg': 16, 'beta_deg': 3.08, 'leak_centre_deg': 12.42, 'leak_radius_deg': 2.98, 'rim_limit_deg': 9.09, 'C1_near_polar_deg': 7.08,
     'C1_near_z_m': None, 'C1_near_r_m': 7.98, 'C1_envelope_polar_deg': 5.69, 'static_torque_GN_m': 69.7, 'shield_face_m': 68.2, 'valid': True},
    {'tilt_deg': 18, 'beta_deg': 3.51, 'leak_centre_deg': 13.92, 'leak_radius_deg': 2.98, 'rim_limit_deg': 10.60, 'C1_near_r_m': 6.22,
     'static_torque_GN_m': 104.0, 'valid': False, 'note': 'C1 inside the module (r 6.5 m)'},
    {'tilt_deg': 20, 'valid': False, 'note': 'C1 through the module and the bore'}, {'tilt_deg': 22, 'valid': False, 'note': 'C1 through the module and the bore'}]


def farm_row(name, R, burn_shift_m=0.0, note='', lam=None):
    d_far = FARM_X_NEAR-(XB-burn_shift_m)
    L = STRETCH_L_V4*(LAM if lam is None else lam)/((R/V4_FARM_R)**2)
    rim = rim_deg(R, d_far)
    rs = D_SHIELD*math.tan(math.radians(rim)); rs_v4 = D_SHIELD_V4*math.tan(math.radians(A1['shield_rim_polar_deg']))
    return {'variant': name, 'farm_radius_m': R, 'stretch_length_m': L, 'stretch_x_m': [STRETCH_X0, STRETCH_X0+L],
            'burn_point_moved_aft_m': burn_shift_m, 'd_farm_near_m': d_far, 'shield_rim_deg': rim,
            'shield_radius_m_at_%.1f_m' % D_SHIELD: rs, 'shield_area_vs_V4': (rs/rs_v4)**2,
            'meets_7p5_rim': rim <= LIMIT+1e-9, 'leak_inner_edge_deg': LEAK_C-LEAK_R, 'leak_clearance_to_rim_deg': LEAK_C-LEAK_R-rim,
            'dust_clearance_m': DUST_R-R, 'inside_dust_shield': R <= DUST_R-DUST_CLEAR+1e-9,
            'pass_geometry': (rim <= LIMIT+1e-9) and (R <= DUST_R-DUST_CLEAR+1e-9), 'note': note}


def max_R_for_rim(d_far, rim=LIMIT, d_shield=D_SHIELD):
    return d_far*(math.tan(math.radians(rim))-1.0/d_shield)


def burn_shift_for(R, rim=LIMIT, d_shield=D_SHIELD):
    d = R/(math.tan(math.radians(rim))-1.0/d_shield)
    return d-(FARM_X_NEAR-XB)


def farms():
    d0 = FARM_X_NEAR-XB
    R75 = max_R_for_rim(d0)
    rows = [farm_row('F0 V4 farm (reference, V4 mass)', V4_FARM_R, lam=1.0, note='V4 stretch 275 m carries 25 kt; at the coupled propellant it becomes F3'),
            farm_row('F1 wide (T00 coupled converged)', CS['spine']['shield']['farm_radius_m'], note='T00 gate preferred case'),
            farm_row('F2 cone-limited r %.1f' % R75, math.floor(R75*100)/100, note='largest farm meeting the 7.5 deg rim with the farm end at X 109.25'),
            farm_row('F2x dust-limited r 44', DUST_R-DUST_CLEAR, note='rim 7.9 deg: needs the burn point aft (F4)'),
            farm_row('F3 long (V4 section)', V4_FARM_R, note='T00 long farm'),
            farm_row('F4 r 44 with the burn point %.1f m aft' % burn_shift_for(DUST_R-DUST_CLEAR), DUST_R-DUST_CLEAR,
                     burn_shift_m=burn_shift_for(DUST_R-DUST_CLEAR), note='drive, coils and aft spine move aft; longer aft spine'),
            farm_row('F4w wide r 57 with the burn point %.0f m aft' % burn_shift_for(57.0), 57.0, burn_shift_m=burn_shift_for(57.0),
                     note='meets the rim but not the dust shield')]
    # A1 at a larger tilt (T00 gate2/cone.json): the leak moves out, the rim limit rises, C1's near side comes inward, so the shield
    # face moves forward out of C1's z band (62.4-65.7 m) to 68.2 m; the dust shield then governs (r 44)
    for t in TILTS:
        if t['valid'] and t['tilt_deg'] > 14:
            r = farm_row('F6 r 44, A1 tilt %d deg, shield face at %.1f m' % (t['tilt_deg'], t['shield_face_m']), DUST_R-DUST_CLEAR,
                         note='T00 lane T%d: the rim limit is %.2f deg' % (t['tilt_deg'], t['rim_limit_deg']))
            r['shield_rim_deg'] = rim_deg(DUST_R-DUST_CLEAR, d0, t['shield_face_m'])
            r['tilt_deg'] = t['tilt_deg']; r['rim_limit_deg'] = t['rim_limit_deg']
            r['meets_7p5_rim'] = None; r['meets_tilt_rim'] = r['shield_rim_deg'] <= t['rim_limit_deg']
            r['leak_inner_edge_deg'] = t['leak_centre_deg']-t['leak_radius_deg']; r['leak_clearance_to_rim_deg'] = r['leak_inner_edge_deg']-r['shield_rim_deg']
            r['pass_geometry'] = r['meets_tilt_rim'] and r['inside_dust_shield']
            r['variant'] = r['variant'].replace('F6', 'F6_%d' % t['tilt_deg']); rows.append(r)
    # ellipse: narrow (b) along the tilt plane, wide (a) across it; the rim rule applies per azimuth, the dust shield to both
    b = R75; a = CS['spine']['shield']['farm_radius_m']**2/b
    rows.append({'variant': 'F5 elliptical %.1f x %.1f (narrow in the tilt plane)' % (a, b), 'farm_radius_m': [a, b],
                 'shield_rim_deg_tilt_plane': rim_deg(b, d0), 'shield_rim_deg_across': rim_deg(a, d0),
                 'stretch_length_m': STRETCH_L_V4, 'dust_clearance_m': DUST_R-a, 'inside_dust_shield': a <= DUST_R-DUST_CLEAR,
                 'meets_7p5_rim': rim_deg(b, d0) <= LIMIT, 'pass_geometry': False,
                 'note': 'leak side passes, but the wide axis (%.0f m) is far outside the r 45 dust shield: REJECTED' % a})
    return rows


def twin():
    """Twin-nozzle concept, conceptual geometry. FDP-1 loops (T00 A1 handoff): L1 R 56 m, L2 R 97 m, L3 R 168 m at z -97 m."""
    loops = {L['name']: L for L in A1['loops'] if L['name'].startswith('L')}
    RL3 = loops['L3']['radius_m']; RL1 = loops['L1']['radius_m']
    wing_aft_x = CHK['generations']['V4']['wing_aft_x_m']; d_wing = wing_aft_x-XB
    keep = GATE['axis_channel']['keep_out_recommendation_deg']; band = GATE['axis_channel']['half_angle_band_deg'][1]
    rows = []
    for k_scale, label in ((1.0, 'FDP-1 nozzle (each at full pulse energy, half rate)'), (0.5**(1/3), 'each nozzle at half pulse energy (loops x0.79)')):
        s_min = 2*RL3*k_scale/2+5.0                   # loop L3 radius + 5 m: two nozzles side by side, axes parallel
        rings = (30.0, 346.0)                         # habitat rings r 30 at X ~ 97 (d 346 from the V4 burn plane)
        farm = (41.7, FARM_X_NEAR-XB)
        ang = lambda r, d: (math.degrees(math.atan((s_min-r)/d)), math.degrees(math.atan((s_min+r)/d)))
        a_r, a_f = ang(*rings), ang(*farm)
        span = (min(a_r[0], a_f[0]), max(a_r[1], a_f[1]))
        rows.append({'case': 'parallel outriggers, '+label, 'loop_scale': k_scale, 'nozzle_separation_from_axis_m': s_min,
                     'ship_angular_span_from_each_burn_deg': span, 'shield_half_angle_deg': (span[1]-span[0])/2,
                     'channel_to_ship_clearance_deg': span[0]-keep,
                     'wing_conflict': 'in the wing plane the forward channel runs along the wing from its aft edge %.0f m ahead of the burn; '
                                      'out of the plane the radiators see each burn face-on' % d_wing,
                     'structure': 'outrigger diagonals on the burn rays (edge-on, shadowable); root bending F x s if not triangulated',
                     'force_torque': 'axial thrust; differential thrust 1 %% gives %.0f MN m yaw' % (0.01*CS['summary']['departure_t']*1e3*CS['summary']['a0_g']*9.80665/2*s_min/1e6),
                     'launcher': 'rate per nozzle halves (%.0f Hz each), muzzle speed and barrel fall with it' % (CS['summary']['pellet_rate_Hz']/2)})
    # splayed: axes tilted outward by beta so a nozzle near the axis sends its channel past the ship
    for beta in (8.0, 12.0, 16.0):
        loop_overlap_s = RL3*math.cos(math.radians(beta))-abs(loops['L3']['centre_m'][2])*math.sin(math.radians(beta))
        rows.append({'case': 'splayed %.0f deg (out of the wing plane, mirrored pair)' % beta, 'splay_deg': beta,
                     'cosine_thrust_loss': 1-math.cos(math.radians(beta)),
                     'min_separation_for_L3_clear_m': loop_overlap_s+5.0,
                     'channel_clearance_vs_farm_deg': beta-keep-math.degrees(math.atan(41.7/(FARM_X_NEAR-XB))),
                     'channel_clearance_band_edge_deg': beta-band-math.degrees(math.atan(41.7/(FARM_X_NEAR-XB))),
                     'force_torque': 'a mirrored pair out of the wing plane cancels the lateral force; two nozzles side by side in Y '
                                     'splayed in +/-Z also leave a roll couple unless four nozzles are used',
                     'note': 'splaying outward at the bow moves the aft loops (L3 at z -97 m) inward: it does not ease loop interference'})
    return {'loops_m': {n: L['radius_m'] for n, L in loops.items()}, 'L1_radius_m': RL1, 'rows': rows,
            'verdict': 'BLOCKED with FDP-1-sized nozzles: L3 (R 168 m) forces about 170 m between the nozzle axes, the planar radiator '
                       'wings either sit in the forward channel (in-plane) or face each burn (out of plane), and a mirrored splay needs '
                       'four nozzles to cancel force and torque. A twin architecture needs a nozzle several times smaller (a different '
                       'nozzle, T00) and a radiator layout that is edge-on to two burn points.'}


def main():
    out = {'study': 'Vertex feasibility gate 2, Task C geometry (T05)', 'status': 'MODEL, research only, NON-CANON',
           'inputs': {'t00': '9rsgog 43fac75 t05_handoff_gate.json', 'rim_rule': 'FDP-1: atan(R/d_far + 1 m/d_shield) (T00 2026-11-10)',
                      'x_burn_m': XB, 'farm_x_near_m': FARM_X_NEAR, 'd_shield_m': D_SHIELD, 'limit_deg': LIMIT,
                      'leak_cone_deg': [LEAK_C, LEAK_R], 'lambda_propellant': LAM, 'dust_shield_r_m': DUST_R},
           'farms': farms(), 'a1_tilts_T00': TILTS, 'twin_nozzles': twin()}
    (HERE/'gate2.json').write_text(json.dumps(out, indent=1))
    for r in out['farms']:
        print('%-50s R %-14s L %6.0f rim %s dust %5.1f pass %s' % (r['variant'], r['farm_radius_m'], r['stretch_length_m'],
              round(r.get('shield_rim_deg', r.get('shield_rim_deg_tilt_plane')), 2), r['dust_clearance_m'], r['pass_geometry']))
    for r in out['twin_nozzles']['rows']:
        print(r['case'], {k: (round(v, 2) if isinstance(v, float) else v) for k, v in r.items() if k not in ('case', 'wing_conflict', 'structure', 'note', 'force_torque', 'launcher')})


if __name__ == '__main__':
    main()
