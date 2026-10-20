"""P1F optically gated Fiji/Lattice manifold: PROTOTYPE geometry, normalized rig state and clearance checks.

Canon (drive_capture_2026-09-27c): 1 core -> common plasma -> 1 finite convergence throat -> 1 magnetic manifold ->
4 flux channels -> 4 magnetic nozzles (LOCKED topology). Two A/B optical sources send light aft (-X) to four lattice
gates L1-L4 (WORKING). Light conditions the lattice; the magnetic field splits and steers the charged plasma. Fields
never bend the beam, so every optical segment here is a straight line routed by mirrors.

AFT-007 (drive_capture_2026-10-03b): the Structural_Spine ends on a terminated hub at the shadow-shield bulkhead (06!A47, 15!A72), so
the common and throat plasma are solid columns and three outer sectors of the primary cage carry the drive load around the core.
Each optical source has its own dog-leg bore through the hub and shield beside the spine end, a splitter in the shield-to-core gap, two
corridor legs outside the cage and one distributor-head cartridge per leg in a lattice gap (06!A55, 15!A73, 15!A83). The nozzles carry
warm yoke rings and straps, and the pickups bear on the inlet yoke (15!A67). All of this is PROTOTYPE geometry.

Every dimension comes from the PROTOTYPE [drive_manifold] and [prototype] tables. Controls are normalized 0-1 display
values; optical power, wavelength, response time and the optical-to-lattice coupling stay OPEN, so no formula here maps
gate light to flux share. Flux shares are the commanded manifold-control input.

Standard library and the pure layout module only; imported by spec, the Blender recipes, the rig, inspect, presentation and tests.
"""
from pathlib import Path
import json
import math
import sys
import layout

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT/'references/p1_drive_manifold.json'
CONTROL = 'DRIVE_MANIFOLD_CTRL'
# Driven X of the last point of each PLASMA_EXHAUST_j curve (its single spline: 4 nozzle points, then the run end).
EXHAUST_END = 'data.splines[0].points[4].co'

# Keyed, normalized 0-1 controls on DRIVE_MANIFOLD_CTRL. None of them carries a physical unit.
PROPS = {
    'drive_active': 'Drive output display level: 0 off, 1 the configuration operating point. Not a throttle percentage.',
    'manifold_field_strength': 'Seed-coil base field level (slow control; establishes base topology).',
    'lattice_activation': 'Fiji lattice activity display level (heat-dependent field enhancement).',
    'laser_A_power': 'Master optical source A output (normalized; rating OPEN).',
    'laser_B_power': 'Master optical source B output (normalized; rating OPEN).',
    'optical_gate_1': 'Lattice optical gate L1 command (fast trim; coupling OPEN).',
    'optical_gate_2': 'Lattice optical gate L2 command.',
    'optical_gate_3': 'Lattice optical gate L3 command.',
    'optical_gate_4': 'Lattice optical gate L4 command.',
    'flux_share_1': 'Commanded flow share of flux channel F1 -> N1 (renormalized to sum 1).',
    'flux_share_2': 'Commanded flow share of F2 -> N2.',
    'flux_share_3': 'Commanded flow share of F3 -> N3.',
    'flux_share_4': 'Commanded flow share of F4 -> N4.',
    'nozzle_field_strength': 'Magnetic nozzle field level (expansion/detachment control).',
    'manifold_balance': 'Label only: 1 - sum|share - 0.25|/1.5. Nothing is driven by it.',
    'plasma_visibility': 'Display request: 0 hides plasma layers.',
}
# Debug-layer display requests (>= 0.5 shows the layer); never keyed by the actions, saved at 0.
DEBUG_TOGGLES = {
    'magnetic_field_debug': 'Show WF_DEBUG_MAGNETICS (flux lines, throat deformation, nozzle vectors).',
    'optical_debug': 'Show WF_DEBUG_OPTICS (beam axis, focus, gate paths, illuminated areas, clearance volumes).',
    'separatrix_debug': 'Show WF_DEBUG_SEPARATRICES (the SEP_* magnetic separatrices).',
}
# Debug subsystem -> its toggle. WF_PROPULSION links each as a DRIVE_<subsystem> instance whose hide flags are driven by
# the toggle, so a library override of the propulsion assembly carries the switches with the control.
DEBUG_LAYERS = {'DEBUG_MAGNETICS': 'magnetic_field_debug', 'DEBUG_SEPARATRICES': 'separatrix_debug', 'DEBUG_OPTICS': 'optical_debug'}
# Configuration display settings (P1-006): posed per configuration, never keyed by the actions, saved at SAVED_SETTINGS.
CONFIGURATION_SETTINGS = {
    'thrust_level': 'Display-only throttle: the configuration max_accel_g / the highest drive-ACTIVE max_accel_g. '
                    'Sets only the length of the exhaust run past each nozzle exit; exhaust velocity and mass flow OPEN (S3).',
}
SAVED_SETTINGS = {**{k: 0.0 for k in DEBUG_TOGGLES}, 'thrust_level': 1.0}
# Driver variable -> control property.
VARIABLES = {'t': 'thrust_level', 'dbm': 'magnetic_field_debug', 'dbs': 'separatrix_debug', 'dbo': 'optical_debug', 'a': 'drive_active', 'v': 'plasma_visibility', 'n': 'nozzle_field_strength', 'f': 'manifold_field_strength',
             'l': 'lattice_activation', 'A': 'laser_A_power', 'B': 'laser_B_power',
             **{f'g{j}': f'optical_gate_{j}' for j in range(1, 5)}, **{f's{j}': f'flux_share_{j}' for j in range(1, 5)}}


def smooth(t):
    return 3*t*t-2*t*t*t


def radial(x, r, a):
    return (x, r*math.cos(a), r*math.sin(a))


def sub(a, b):
    return tuple(p-q for p, q in zip(a, b))


def dot(a, b):
    return sum(p*q for p, q in zip(a, b))


def norm(a):
    return math.sqrt(dot(a, a))


def point_segment(p, a, b):
    """Distance from a point to a segment (unrolled: this is the hot loop of every clearance screen)."""
    ux, uy, uz = b[0]-a[0], b[1]-a[1], b[2]-a[2]; wx, wy, wz = p[0]-a[0], p[1]-a[1], p[2]-a[2]
    uu = ux*ux+uy*uy+uz*uz
    t = 0.0 if uu == 0 else max(0.0, min(1.0, (wx*ux+wy*uy+wz*uz)/uu))
    return math.sqrt((wx-t*ux)**2+(wy-t*uy)**2+(wz-t*uz)**2)


def segment_segment(a, b, c, d, samples=64):
    """Sampled minimum distance between two segments (adequate at the centimetre scale used here)."""
    return min(point_segment(tuple(p+k/samples*(q-p) for p, q in zip(a, b)), c, d) for k in range(samples+1))


def optics_x(s):
    """Ship-frame X of the optical stations (layout datums); splitter_x is per route."""
    m = s['drive_manifold']
    out = {k: layout.at(s, m[k]) for k in ('laser_x', 'turn_x', 'hub_forward_x', 'route_jog_x', 'head_x')}
    out['splitter_x'] = {key: layout.at(s, v) for key, v in m['splitter_x'].items()}
    return out


def spine_span(s):
    """(aft, forward) X of Structural_Spine: it ends on the terminated hub (hub_forward_x) and runs to the forward inset.
    Single source for the recipe, the storage obstacles and stations()['spine_aft']."""
    return layout.at(s, s['drive_manifold']['hub_forward_x']), s['ship']['length']['value']/2-s['prototype']['spine_forward_inset_m']


def quadrants(s):
    """(sign Y, sign Z) of Nozzle_01..04 = owner N1-N4 (06!A48, 15!C71): the single source of the nozzle order, equal to the EYE F1-F4 order."""
    return [tuple(q) for q in s['propulsion']['manifold']['nozzle_map']['quadrants']]


def opposite(s, k):
    """1-based nozzle at the negated quadrant of nozzle k (diametric opposite), found by sign and never by index."""
    qs = quadrants(s); target = tuple(-c for c in qs[k-1])
    return qs.index(target)+1


def neighbours(s, k):
    """1-based nozzles sharing exactly one quadrant sign with nozzle k, in nozzle order."""
    qs = quadrants(s); q = qs[k-1]
    return [j for j, o in enumerate(qs, 1) if j != k and (o[0] == q[0]) != (o[1] == q[1])]


def channel_loss_shares(s, failed):
    """Flux shares after the owner recovery (06!A51, 15!C76): the failed channel and its diametric opposite get 0, each survivor 1/2.
    The survivors are the other diagonal at propulsion.manifold.channel_loss_recovery.surviving_thrust_fraction of nominal."""
    out = {failed, opposite(s, failed)}
    return [0.0 if j in out else 1/(len(quadrants(s))-len(out)) for j in range(1, len(quadrants(s))+1)]


def throat_geometry(s):
    """(length, waist radius) of the throat from the WORKING owner source (Q25); the field profile stays OPEN."""
    t = s['propulsion']['manifold']['throat_geometry']
    return t['length_m'], t['waist_radius_m']


def stations(s):
    """Axial stations of the existing envelopes plus the PROTOTYPE throat and optics."""
    p, m = s['prototype'], s['drive_manifold']; L = s['ship']['length']['value']
    x = lambda key: layout.at(s, p[key])
    entry = x('manifold_center_x')+p['manifold_length_m']/2
    shield = x('shadow_center_x')
    return dict(core_fwd=x('reactor_center_x')+p['reactor_length_m']/2, core_aft=x('reactor_center_x')-p['reactor_length_m']/2,
                common_fwd=x('common_center_x')+p['common_length_m']/2, common_aft=x('common_center_x')-p['common_length_m']/2,
                throat_entry=entry, throat_exit=entry-throat_geometry(s)[0], manifold_aft=entry-p['manifold_length_m'],
                lattice_fwd=entry-m['lattice_forward_offset_m'], lattice_aft=entry-m['lattice_forward_offset_m']-m['lattice_length_m'],
                inlet=-L/2+p['nozzle_length_m'], exit=-L/2, shield_fwd=shield+p['shadow_thickness_m']/2, shield_aft=shield-p['shadow_thickness_m']/2,
                ring=x('thrust_ring_x'), spine_aft=spine_span(s)[0])


def geometry(s):
    p, m = s['prototype'], s['drive_manifold']; st = stations(s)
    R1 = p['nozzle_offset_m']*math.sqrt(2); r0 = m['branch_start_radius_m']; n = m['branch_samples']
    angles = [math.atan2(zz, yy) for yy, zz in quadrants(s)]
    x1, xi = st['throat_exit'], st['inlet']

    def branch_radius(x):
        return r0+(R1-r0)*smooth(max(0.0, min(1.0, (x-x1)/(xi-x1))))
    branches = [[radial(x1+(xi-x1)*k/(n-1), branch_radius(x1+(xi-x1)*k/(n-1)), a) for k in range(n)] for a in angles]
    # Exhaust continues along the nozzle axis through the nozzle and a short visual run past the exit. Point radii
    # follow the nozzle field envelope (throat -> exit); no divergence is drawn past the exit (plume boundary OPEN, R2).
    L_n, exit_r, throat_r = p['nozzle_length_m'], p['nozzle_exit_radius_m'], p['nozzle_throat_radius_m']
    def envelope(local):
        return throat_r if local >= .65*L_n else exit_r+(throat_r-exit_r)*local/(.65*L_n)
    ex_local = [L_n, .65*L_n, .325*L_n, 0.0]
    exhausts = []
    for a in angles:
        pts = [radial(st['exit']+u, R1, a) for u in ex_local]+[radial(st['exit']-m['exhaust_length_m'], R1, a)]
        exhausts.append(dict(points=pts, factors=[envelope(u)/throat_r for u in ex_local]+[exit_r/throat_r]))
    # Solid common and throat columns (06!A47, 15!A70): no spine passes through the plasma, so every inner radius is 0. The
    # throat waists, then hands over to the four branches.
    common = dict(x0=st['common_fwd'], x1=st['common_aft'], inner=0.0, outer=m['common_stream_outer_radius_m'])
    throat_rings = [(st['throat_entry'], 0.0, m['common_stream_outer_radius_m']),
                    ((st['throat_entry']+x1)/2, 0.0, throat_geometry(s)[1]),
                    (x1, 0.0, r0+p['flow_radius_m'])]
    lat_x = (st['lattice_fwd']+st['lattice_aft'])/2; half = math.radians(m['lattice_half_angle_deg'])
    lattice = [dict(x0=st['lattice_fwd'], x1=st['lattice_aft'], r_in=m['lattice_inner_radius_m'], r_out=m['lattice_outer_radius_m'],
                    a0=a-half, a1=a+half, angle=a, target=radial(lat_x, m['lattice_inner_radius_m'], a)) for a in angles]
    coils = [dict(x=st['throat_entry']-o, radius=m['seed_coil_radius_m'], tube=m['seed_coil_tube_m']) for o in m['seed_coil_offsets_m']]
    routes = optical_routes(s, st, lattice)
    lasers = {key: dict(center=r['laser_center'], size=(m['laser_length_m'], m['laser_width_m'], m['laser_width_m']), path=r['trunk']) for key, r in routes.items()}
    mirrors = {name: pt for r in routes.values() for name, pt in r['mirrors'].items()}
    gates = {(key, j): chord for key, r in routes.items() for (kk, j), chord in r['chords'].items() if kk == key}
    windows = {(key, j): pt for key, r in routes.items() for (kk, j), pt in r['windows'].items() if kk == key}
    # Illuminated lattice area around each gate target (pad on the lattice inner face).
    pad_half_x, pad_half_a = .45, math.radians(10)
    pads = [dict(x0=lat['target'][0]+pad_half_x, x1=lat['target'][0]-pad_half_x, r=lat['r_in']-.02, a0=lat['angle']-pad_half_a, a1=lat['angle']+pad_half_a) for lat in lattice]
    hub = dict(x0=st['shield_fwd'], x1=optics_x(s)['hub_forward_x'], radius=m['hub_radius_m'])
    return dict(stations=st, angles=angles, nozzle_radius=R1, branches=branches, exhausts=exhausts, common=common,
                throat_rings=throat_rings, lattice=lattice, coils=coils, lasers=lasers, routes=routes, mirrors=mirrors, hub=hub,
                gate_beams=gates, windows=windows, pads=pads,
                separatrices=separatrices(s, st), field_lines=field_lines(s, st, branches, angles),
                nozzle_vectors=[(radial(st['exit'], R1, a), radial(st['exit']-3.0, R1, a)) for a in angles])


def nearest_sectors(angle_rad, lattice, count=2):
    """Lattice sector numbers (1-based) nearest in azimuth to a head, as (j, |delta| rad), nearest first."""
    def delta(lat):
        d = (angle_rad-lat['angle']) % math.tau
        return min(d, math.tau-d)
    return sorted(((j, delta(lat)) for j, lat in enumerate(lattice, 1)), key=lambda t: t[1])[:count]


def optical_routes(s, st, lattice):
    """Independent A/B optical routes (06!A55, 15!A73, 15!A83); every position is a PROTOTYPE selection.

    Cold side: laser -> turn mirror -> entry mirror -> a dog-leg bore through the hub and shield beside the spine end (one jog of
    route_jog_m, away from the other route's side) -> splitter in the shield-to-core gap. Hot side: two legs from the splitter run out
    to the corridor between the cage and the hull skin, aft along it, and turn inward to a distributor-head cartridge in a lattice
    gap; each head fires one chord to each of its two neighbouring sectors. A uses -Y (bus A) and a -Z jog, B uses +Y and +Z."""
    m = s['drive_manifold']; ox = optics_x(s)
    yb0, jog, rc, lx, hl = m['route_offset_m'], m['route_jog_m'], m['route_corridor_radius_m'], ox['laser_x'], m['laser_length_m']/2
    routes = {}
    for key, sign in (('A', -1), ('B', 1)):
        yb, zj, sx = sign*yb0, sign*jog, ox['splitter_x'][key]
        turn, entry = (ox['turn_x'], sign*m['laser_offset_m'], 0.0), (ox['turn_x'], yb, 0.0)
        jog1, jog2, split = (ox['route_jog_x'], yb, 0.0), (ox['route_jog_x'], yb, zj), (sx, yb, zj)
        trunk = [(lx-hl, sign*m['laser_offset_m'], 0.0), turn, entry, jog1, jog2, split]
        bore = [(ox['hub_forward_x'], yb, 0.0), jog1, jog2, (st['shield_aft'], yb, zj)]
        mirrors = {f'OPTICAL_TURN_MIRROR_{key}': turn, f'OPTICAL_ENTRY_MIRROR_{key}': entry, f'OPTICAL_JOG_MIRROR_{key}_1': jog1,
                   f'OPTICAL_JOG_MIRROR_{key}_2': jog2, f'OPTICAL_SPLITTER_{key}': split}
        legs, heads, chords, windows = [], {}, {}, {}
        for i, (run_deg, head_deg) in enumerate(zip(m['route_run_angles_deg'][key], m['route_heads_deg'][key]), 1):
            ar, ah = math.radians(run_deg), math.radians(head_deg)
            c1, c2, head = radial(sx, rc, ar), radial(ox['head_x'], rc, ar), radial(ox['head_x'], m['head_radius_m'], ah)
            legs.append(dict(index=i, run_deg=run_deg, head_deg=head_deg, points=[split, c1, c2, head], head=head))
            mirrors[f'OPTICAL_CORRIDOR_MIRROR_{key}_{i}_1'] = c1; mirrors[f'OPTICAL_CORRIDOR_MIRROR_{key}_{i}_2'] = c2
            heads[f'OPTICAL_HEAD_{key}_{i}'] = head
            for j, _ in nearest_sectors(ah, lattice):
                d = sub(lattice[j-1]['target'], head); n_d = norm(d)
                chords[(key, j)] = [head, lattice[j-1]['target']]
                windows[(key, j)] = tuple(q+m['head_size_m']*c/n_d for q, c in zip(head, d))
        routes[key] = dict(laser_center=(lx, sign*m['laser_offset_m'], 0.0), trunk=trunk, bore=bore, legs=legs, mirrors=mirrors, heads=heads,
                           chords=chords, windows=windows, jog=(yb, zj))
    return routes


def route_beams(g):
    """Every straight optical segment, by drawn object name: the trunk (OPTICAL_BEAM_K), two corridor legs and the chord of each gate."""
    out = {}
    for key, r in g['routes'].items():
        out[f'OPTICAL_BEAM_{key}'] = r['trunk']
        for leg in r['legs']:
            out[f'OPTICAL_LEG_{key}_{leg["index"]}'] = leg['points']
    for (key, j), chord in g['gate_beams'].items():
        out[f'GATE_BEAM_{key}_L{j}'] = chord
    return out


def separatrices(s, st):
    """Flux-domain boundaries midway between neighbouring branches: field boundaries, never material walls. They start on the
    axis because the plasma is solid."""
    m = s['drive_manifold']; out = []
    outer_end = s['prototype']['nozzle_offset_m']*math.sqrt(2)+m['domain_radius_m']+.1
    for k in range(4):
        a = math.radians(90+90*k); axis = (round(math.cos(a)), round(math.sin(a)))
        # The two nozzles on the side of the separatrix direction (the sign of its non-zero Y or Z component).
        pair = [j for j, q in enumerate(quadrants(s), 1) if q[0 if axis[0] else 1] == (axis[0] or axis[1])]
        name = 'SEP_'+''.join(str(j) for j in sorted(pair))
        rows = []
        for i in range(17):
            x = st['throat_entry']+(st['inlet']-st['throat_entry'])*i/16
            w = smooth(i/16); rows.append((x, 0.0, m['common_stream_outer_radius_m']+(outer_end-m['common_stream_outer_radius_m'])*w))
        out.append(dict(name=name, angle=a, rows=rows))
    return out


def field_lines(s, st, branches, angles):
    """Debug magnetic topology: lines start in the common annulus and bend into their own branch without crossing a separatrix."""
    m = s['drive_manifold']; lines = []; n = len(branches[0])
    x_fwd = st['common_fwd']
    for j, a in enumerate(angles):
        for rho, da in [(2.2, -.45), (2.2, 0.0), (2.2, .45), (1.45, 0.0)]:
            th = a+da; pts = []
            off = .35*m['domain_radius_m']*(rho-1.8)/.4
            for i in range(9):
                x = x_fwd+(st['throat_entry']-x_fwd)*i/8; pts.append(radial(x, rho, th))
            for k in range(0, n, 3):
                c = branches[j][k]; t = smooth(min(1.0, k/(n*.35)))
                target = (c[0], c[1]+off*math.cos(th), c[2]+off*math.sin(th))
                pts.append(tuple((1-t)*q+t*r for q, r in zip(radial(c[0], rho, th), target)))
            c = branches[j][-1]
            pts.append((st['exit'], c[1]+off*math.cos(th), c[2]+off*math.sin(th)))
            lines.append(dict(branch=j+1, points=pts))
    return lines


# ---------- normalized state -------------------------------------------------------------------------------------

def neutral(s):
    """Saved state: drive off, shares at the LOCKED nominal, optics off. Never save a posed vehicle."""
    share = s['propulsion']['manifold']['nominal_share']
    return {**{k: 0.0 for k in PROPS}, **{f'flux_share_{j}': share for j in range(1, 5)}, 'manifold_balance': 1.0, 'plasma_visibility': 1.0}


def nominal(s):
    m = s['drive_manifold']
    return {**neutral(s), 'drive_active': 1.0, 'manifold_field_strength': 1.0, 'lattice_activation': 1.0, 'nozzle_field_strength': 1.0,
            'laser_A_power': m['nominal_laser_share'], 'laser_B_power': m['nominal_laser_share'],
            **{f'optical_gate_{j}': m['nominal_gate_command'] for j in range(1, 5)}}


def thrust_level(s, name):
    """P1-006 display throttle from the sourced acceleration limits (11_OPERATING_CONFIGS); the saved value when the drive is OFF."""
    cfg = s['configuration'][name]
    if cfg.get('drive') != 'ACTIVE':
        return SAVED_SETTINGS['thrust_level']
    full = max(c['max_accel_g'] for c in s['configuration'].values() if c.get('buildable') and c.get('drive') == 'ACTIVE')
    return cfg['max_accel_g']/full


def configuration_state(s, name):
    """Drive state per operating configuration (11_OPERATING_CONFIGS): ACTIVE -> nominal balanced, OFF -> neutral,
    plus the configuration's display throttle."""
    cfg = s['configuration'][name]
    return {**(nominal(s) if cfg.get('drive') == 'ACTIVE' else neutral(s)), 'thrust_level': thrust_level(s, name)}


def normalize(shares):
    total = sum(shares)
    if total <= 0:
        raise ValueError('Flux shares must have a positive sum')
    return [x/total for x in shares]


def balance(shares):
    return 1-sum(abs(x-.25) for x in normalize(shares))/1.5


def couple_arm(s, shares):
    """Moment arm per unit total thrust from branch allocation, assuming equal exhaust velocity (Fiji 25!E23).

    Axial thrust at the nozzle offsets gives pitch (about +Y) = sum s*z and yaw (about +Z) = -sum s*y. Because shares
    sum to 1, the change from the balanced state is a pure couple: independent of the (unknown) centre of mass.
    Parallel axial thrust can never produce roll (Fiji 25!A36)."""
    q = s['prototype']['nozzle_offset_m']; sh = normalize(shares)
    pitch = sum(x*zz*q for x, (yy, zz) in zip(sh, quadrants(s))); yaw = -sum(x*yy*q for x, (yy, zz) in zip(sh, quadrants(s)))
    return dict(pitch_arm_m=round(pitch, 12)+0.0, yaw_arm_m=round(yaw, 12)+0.0, roll_arm_m=0.0, couple_arm_m=round(math.hypot(pitch, yaw), 12))


# ---------- drivers: one expression source for Blender and for display() ----------------------------------------

def drivers(s):
    """(object, data path, index, expression). Blender builds exactly these; display() evaluates them."""
    m = s['drive_manifold']; R = s['prototype']['flow_radius_m']; rb = m['beam_radius_m']
    total = 'max(s1+s2+s3+s4,1e-06)'; supply = 'min(1,A+B)'; out = []
    exit_x = stations(s)['exit']; run = m['exhaust_length_m']; k = m['thrust_display_exponent']
    for j in range(1, 5):
        out += [(f'PLASMA_BRANCH_{j}', 'data.bevel_depth', -1, f'{R!r}*sqrt(max(4*a*v*s{j}/{total},0))'),
                (f'PLASMA_BRANCH_{j}', 'color', 3, 'min(1,a*v)'),
                (f'PLASMA_EXHAUST_{j}', 'data.bevel_depth', -1, f'{R!r}*sqrt(max(4*a*v*n*s{j}/{total},0))'),
                (f'PLASMA_EXHAUST_{j}', 'color', 3, 'min(1,a*v*n)'),
                (f'PLASMA_EXHAUST_{j}', EXHAUST_END, 0, f'{exit_x!r}-{run!r}*pow(max(t,0),{k!r})'),
                (f'GATE_L{j}', 'color', 3, f'{supply}*g{j}'),
                (f'LATTICE_SECTOR_{j}', 'color', 3, 'l')]
    for name in ['PLASMA_COMMON', 'PLASMA_THROAT']:
        out += [(name, 'scale', k, 'min(1,a*v*1000)') for k in range(3)]+[(name, 'color', 3, 'min(1,a*v)')]
    for key in 'AB':
        out += [(f'LASER_{key}', 'color', 3, key), (f'OPTICAL_BEAM_{key}', 'data.bevel_depth', -1, f'{rb!r}*min(1,{key}*1000)'), (f'OPTICAL_BEAM_{key}', 'color', 3, key)]
    # Routes are independent: every segment of route K reads only its own source K, and a chord reads its own source and gate.
    for key in 'AB':
        for leg in (1, 2):
            out += [(f'OPTICAL_LEG_{key}_{leg}', 'data.bevel_depth', -1, f'{rb!r}*min(1,{key}*1000)'), (f'OPTICAL_LEG_{key}_{leg}', 'color', 3, key)]
        for j in range(1, 5):
            out += [(f'GATE_BEAM_{key}_L{j}', 'data.bevel_depth', -1, f'{rb!r}*min(1,{key}*g{j}*1000)'), (f'GATE_BEAM_{key}_L{j}', 'color', 3, f'{key}*g{j}')]
    for k in range(len(m['seed_coil_offsets_m'])):
        out.append((f'SEED_COIL_{k+1}', 'color', 3, 'f'))
    var = {prop: name for name, prop in VARIABLES.items()}
    for layer, toggle in DEBUG_LAYERS.items():
        out += [(f'DRIVE_{layer}', path, -1, f'{var[toggle]}<0.5') for path in ('hide_viewport', 'hide_render')]
    return out


def vector_limit_cones(s):
    """Preview-only steering-limit cones (15!G76): per nozzle an apex at the exit centre, axis -X, the WORKING normal and the
    DIAGNOSTIC emergency half-angle, and the display exhaust length. Limits only; the vector authority is OPEN (06!E52)."""
    study = s['propulsion']['nozzle_vector_study']; R1 = s['prototype']['nozzle_offset_m']*math.sqrt(2); st = stations(s)
    return [dict(nozzle=k, apex=radial(st['exit'], R1, math.atan2(zz, yy)), axis=(-1.0, 0.0, 0.0), length=s['drive_manifold']['exhaust_length_m'],
                 normal_deg=study['normal_deg'], normal_status=study['canon_status'],
                 emergency_deg=study['emergency']['limit_deg'], emergency_status=study['emergency']['canon_status'])
            for k, (yy, zz) in enumerate(quadrants(s), 1)]


def exhaust_end_x(s, level):
    """X of the exhaust run's aft end at a display throttle (the saved curve holds level 1)."""
    m = s['drive_manifold']
    return stations(s)['exit']-m['exhaust_length_m']*max(level, 0)**m['thrust_display_exponent']


def expression_variables(expression):
    names = set()
    token = ''
    for ch in expression+' ':
        if ch.isalnum() or ch == '_':
            token += ch
        else:
            if token in VARIABLES:
                names.add(token)
            token = ''
    return sorted(names)


def display(s, values):
    """Evaluate every driver for a control state: the exact values Blender should show."""
    env = {'min': min, 'max': max, 'sqrt': math.sqrt, 'pow': math.pow, '__builtins__': {}}
    env.update({var: float(values.get(prop, SAVED_SETTINGS[prop]) if prop in SAVED_SETTINGS else values[prop]) for var, prop in VARIABLES.items()})
    return {(obj, path, index): float(eval(expr, env)) for obj, path, index, expr in drivers(s)}


# ---------- reusable actions --------------------------------------------------------------------------------------

def _sequence(start, events):
    keys = [(1, dict(start))]; state = dict(start)
    for frame, changes in events:
        state = {**state, **changes}; keys.append((frame, dict(state)))
    for _, key in keys:
        key['manifold_balance'] = balance([key[f'flux_share_{j}'] for j in range(1, 5)])
    return keys


def _gates(values):
    return {f'optical_gate_{j}': v for j, v in enumerate(values, 1)}


def _shares(values):
    return {f'flux_share_{j}': v for j, v in enumerate(values, 1)}


def actions(s):
    """Reusable PROTOTYPE sequences on DRIVE_MANIFOLD_CTRL (frames at [drive_manifold].fps). LINEAR keys only;
    a repeated value is a hold. Timings are editable placeholders until engineering sets real ones."""
    m = s['drive_manifold']; N = nominal(s); Z = neutral(s); L = m['nominal_laser_share']; G = m['nominal_gate_command']
    ex = s['propulsion']['manifold']['example_maneuver']['shares']; rec = s['propulsion']['manifold']['channel_loss_recovery']
    trim = lambda up: _gates([G+.1 if u else G-.1 for u in up])
    spec = {
        # P1-007: steps 3-8 of the owner black start (17_POWER_STORAGE A12:A17) on the frames of WF_BLACK_START: seed coils,
        # plasma breakdown, pulse heating, first fusion, then the thermomagnetic lattice (activation 650 K, Fiji 02!E11) and
        # field lock; optics, gates, split, streams and nozzle fields follow. Replaces the P1F brief's lattice-before-plasma order.
        'WF_DRIVE_STARTUP': ('Black-start order (17_POWER_STORAGE steps 3-8): seed coils, plasma breakdown, pulse heating, first fusion, lattice activation, field lock; then optics, gates, split, streams, nozzle fields, 25/25/25/25.', Z, [
            (24, {}), (48, {'manifold_field_strength': .6}), (72, {'drive_active': .1}), (84, {}),
            (96, {'drive_active': .3}), (120, {'lattice_activation': .5}), (144, {'lattice_activation': 1.0, 'manifold_field_strength': 1.0}),
            (156, {'laser_A_power': L, 'laser_B_power': L}), (168, _gates([G]*4)),
            (192, {'drive_active': 1.0}), (216, {'nozzle_field_strength': 1.0}), (240, {})]),
        'WF_DRIVE_IDLE': ('Hot standby: seed field, lattice and optics held; drive at a low display level.', {**N, 'drive_active': .2}, [(48, {})]),
        'WF_MANIFOLD_BALANCED': ('Nominal straight acceleration, 25/25/25/25 (LOCKED).', N, [(48, {})]),
        'WF_MANIFOLD_PITCH': ('Pitch demo: +Z pair N1/N2 0.30, -Z pair N3/N4 0.20. Gates trim first, shares follow.', N, [
            (24, {}), (36, trim([1, 1, 0, 0])), (60, _shares([.3, .3, .2, .2])), (108, {}), (120, _gates([G]*4)), (144, _shares([.25]*4))]),
        'WF_MANIFOLD_YAW': ('Yaw demo: +Y pair N1/N3 0.30, -Y pair N2/N4 0.20.', N, [
            (24, {}), (36, trim([1, 0, 1, 0])), (60, _shares([.3, .2, .3, .2])), (108, {}), (120, _gates([G]*4)), (144, _shares([.25]*4))]),
        'WF_MANIFOLD_IMBALANCE': ('Owner example 20/30/20/30 (Fiji 25!C26:C29): a yaw couple under the owner N1-N4 map, the -Y pair N2/N4 at 0.30 and the +Y pair N1/N3 at 0.20, no pitch (06!E48, 15!C71).', N, [
            (24, {}), (36, trim([s_ > .25 for s_ in ex])), (60, _shares(ex)), (108, {}), (120, _gates([G]*4)), (144, _shares([.25]*4))]),
        'WF_LASER_A_FAIL': ('Laser A fails; B assumes all four gate channels; gate balance restored (Fiji 25!A69).', N, [
            (24, {}), (26, {'laser_A_power': 0.0}), (36, {}), (60, {'laser_B_power': 1.0}), (144, {})]),
        'WF_LASER_B_FAIL': ('Laser B fails; A assumes all four gate channels.', N, [
            (24, {}), (26, {'laser_B_power': 0.0}), (36, {}), (60, {'laser_A_power': 1.0}), (144, {})]),
        'WF_LASER_AB_FAIL': ('Both sources lost: fast optical trim lost; hold the seed-coil base manifold and derate (Fiji 25!A70).', N, [
            (24, {}), (26, {'laser_A_power': 0.0, 'laser_B_power': 0.0}), (36, {}), (84, {'drive_active': .5}), (144, {})]),
        'WF_GATE_1_FAIL': ('Gate L1 response drops; branch 1 weakens; seed coils and the quadrant-neighbour gates L2/L3 compensate; precautionary derate (Fiji 25!A71).', N, [
            (24, {}), (26, {'optical_gate_1': 0.0}), (48, _shares([.22, .26, .26, .26])), (60, {}),
            (96, {**_shares([.25]*4), **{f'optical_gate_{j}': G+.05 for j in neighbours(s, 1)}}), (120, {'drive_active': .8}), (144, {})]),
        'WF_FLUX_CHANNEL_FAIL': ('Flux channel F3 field collapse (Fiji 25!A40): the branch weakens, F3 is isolated and its diametric opposite F2 is derated at once, and N1/N4 stabilize at drive 0.5 with zero couple (owner recovery 06!A51, 15!C76). Transition torque: RCS/Momentum control (15!I76), not modelled. No hull strike is implied.', N, [
            (24, {}), (30, _shares([.88/3, .88/3, .12, .88/3])),
            (36, {**_shares(channel_loss_shares(s, 3)), **{f'optical_gate_{j}': 0.0 for j in (3, opposite(s, 3))}, 'drive_active': rec['surviving_thrust_fraction']}), (144, {})]),
        'WF_DRIVE_SHUTDOWN': ('Stepped hysteretic descent (05_DRIVE_INTERFACE A12, LOCKED): output, feed, rebalance, gates, lattice, exhaust clears while fields still confine, seed-field steps, optics off.', N, [
            (24, {}), (48, {'drive_active': .5}), (72, {}), (96, {'drive_active': .15}), (108, _shares([.25]*4)), (120, {}),
            (144, _gates([0.0]*4)), (168, {'lattice_activation': .5}), (180, {'drive_active': 0.0}), (192, {'nozzle_field_strength': 0.0}),
            (204, {'lattice_activation': 0.0}), (216, {'manifold_field_strength': .5}), (240, {}), (252, {'manifold_field_strength': 0.0}),
            (264, {'laser_A_power': 0.0, 'laser_B_power': 0.0}), (276, {})]),
    }
    out = {}
    for name, (description, start, events) in spec.items():
        keys = _sequence(start, events)
        out[name] = dict(description=description, keys=keys, frame_range=[keys[0][0], keys[-1][0]])
    return out


def action_state(s, name, frame):
    keys = actions(s)[name]['keys']
    if frame <= keys[0][0]:
        return dict(keys[0][1])
    for (f0, a), (f1, b) in zip(keys, keys[1:]):
        if frame <= f1:
            t = (frame-f0)/(f1-f0)
            return {k: a[k]+(b[k]-a[k])*t for k in a}
    return dict(keys[-1][1])


# ---------- clearance screen --------------------------------------------------------------------------------------

def nozzle_coils(s):
    """The four Nozzle_Coil stations in the nozzle frame (local x from the exit plane, along the nozzle axis).

    Single source for recipes.NOZZLE, the exhaust-clearance screen, the strike modules and the pickup attachment.
    ring_radius is the centreline radius of the coil tube; outer is the tube's outer face; inner the coil inner face."""
    p, h = s['prototype'], s['drive_hot_section']
    L_n, exit_r, throat_r, tube = p['nozzle_length_m'], p['nozzle_exit_radius_m'], p['nozzle_throat_radius_m'], h['nozzle_coil_tube_m']
    out = []
    for j, (x, outer) in enumerate([(0, exit_r), (L_n*.35, exit_r*h['nozzle_coil_mid_radius_factor']), (L_n*.65, throat_r), (L_n, throat_r)]):
        out.append(dict(index=j, name=f'Nozzle_Coil_{j:02}', x=min(L_n-tube, max(tube, x)), outer=outer, ring_radius=outer-tube, tube=tube, inner=outer-2*tube))
    return out


def exhaust_factor(ex, st, u):
    """Plasma radius factor of an exhaust curve at local nozzle x u (piecewise linear between its saved points)."""
    local = [q[0]-st['exit'] for q in ex['points']]; pairs = list(zip(local, ex['factors']))
    for (u0, f0), (u1, f1) in zip(pairs, pairs[1:]):
        if u1 <= u <= u0:
            return f0+(f1-f0)*(u-u0)/(u1-u0)
    return ex['factors'][-1]


def nozzle_yokes(s):
    """Warm structural yoke of each nozzle (15!A67, G67): one ring per Nozzle_Coil station, yoke_standoff_m outside the coil's outer face,
    joined by yoke_strap_count straps on the ring mid radii. Straps start at the pickup direction, so the pickup load enters a strap.
    Ship frame; PROTOTYPE sections, the cold-mass supports behind the standoff are OPEN (OD-024)."""
    p, st, h = s['prototype'], s['structure'], s['drive_hot_section']; L = s['ship']['length']['value']
    xring = layout.at(s, p['thrust_ring_x']); phase = math.radians(p['ring_phase_deg']); half = st['ring_depth_m']/2
    coils = nozzle_coils(s); w = h['yoke_width_m']; out = []
    for j, n in enumerate(st['nozzle_pickup_nodes']):
        yy, zz = quadrants(s)[j]; axis = (yy*p['nozzle_offset_m'], zz*p['nozzle_offset_m'])
        node = radial(xring-half, st['ring_node_radius_m'], phase+n*math.tau/st['ring_nodes'])
        a0 = math.atan2(node[2]-axis[1], node[1]-axis[0])
        rings = []
        for c in coils:
            r_in = c['outer']+h['yoke_standoff_m']
            rings.append(dict(name=f'Nozzle_Yoke_{j}_{c["index"]}', nozzle=j, coil=c['index'], axis=axis, x=-L/2+c['x'],
                              x0=-L/2+max(0.0, c['x']-w/2), x1=-L/2+min(p['nozzle_length_m'], c['x']+w/2), r_in=r_in, r_out=r_in+h['yoke_thickness_m'],
                              coil_gap=r_in-c['outer']))
        straps = []
        for k in range(h['yoke_strap_count']):
            a = a0+k*math.tau/h['yoke_strap_count']
            straps.append(dict(name=f'Nozzle_Yoke_Strap_{j}_{k}', nozzle=j, angle=a, radius=h['yoke_strap_radius_m'],
                               points=[(r['x'], axis[0]+(r['r_in']+r['r_out'])/2*math.cos(a), axis[1]+(r['r_in']+r['r_out'])/2*math.sin(a)) for r in rings]))
        out.append(dict(nozzle=j, axis=axis, rings=rings, straps=straps, pickup_angle=a0))
    return out


def nozzle_pickups(s):
    """Nozzle pickups: from the outer face of the inlet yoke (pickup_attach_yoke) to the thrust-ring node, never on the axis or the coil
    windings (15!A67). The start is offset from the nozzle axis in YZ toward the ring node."""
    p, st, h = s['prototype'], s['structure'], s['drive_hot_section']
    xring = layout.at(s, p['thrust_ring_x']); half = st['ring_depth_m']/2; out = []
    for y in nozzle_yokes(s):
        j = y['nozzle']; ring_ = y['rings'][h['pickup_attach_yoke']]
        node = st['nozzle_pickup_nodes'][j]; a = math.radians(p['ring_phase_deg'])+node*math.tau/st['ring_nodes']
        end = radial(xring-half, st['ring_node_radius_m'], a)
        start = (ring_['x'], y['axis'][0]+ring_['r_out']*math.cos(y['pickup_angle']), y['axis'][1]+ring_['r_out']*math.sin(y['pickup_angle']))
        out.append(dict(name=f'Nozzle_Pickup_{j}', a=start, b=end, radius=.16, nozzle=j, yoke=ring_['coil'], axis=y['axis'],
                        geometry_basis='PROTOTYPE: starts on the outer face of the inlet warm yoke (drive_hot_section.pickup_attach_yoke), off the nozzle axis and clear of the coil windings (15!G67); yoke and strut sections PROTOTYPE, cold-mass supports OPEN (OD-024)'))
    return out


def structure_members(s):
    """Aft-ring members near the branches (components/revision.structure): hub webs, nozzle pickups, and the yoke rings (as 16-sided
    polylines whose radius bounds the section) and straps of each nozzle."""
    p, st, h = s['prototype'], s['structure'], s['drive_hot_section']
    xring = layout.at(s, p['thrust_ring_x']); phase = math.radians(p['ring_phase_deg'])
    out = []
    for j, n in enumerate(st['nozzle_pickup_nodes']):
        a = phase+n*math.tau/st['ring_nodes']
        out.append(dict(name=f'Hub_Web_{j}', a=radial(xring, st['hub_diameter_m']/2, a), b=radial(xring, st['ring_node_radius_m'], a), radius=.15))
    for y in nozzle_yokes(s):
        for ring_ in y['rings']:
            mid = (ring_['r_in']+ring_['r_out'])/2; bound = math.hypot((ring_['x1']-ring_['x0'])/2, (ring_['r_out']-ring_['r_in'])/2)
            pts = [(ring_['x'], y['axis'][0]+mid*math.cos(k*math.tau/16), y['axis'][1]+mid*math.sin(k*math.tau/16)) for k in range(17)]
            out += [dict(name=ring_['name'], a=a_, b=b_, radius=bound) for a_, b_ in zip(pts, pts[1:])]
        for strap in y['straps']:
            out += [dict(name=strap['name'], a=a_, b=b_, radius=strap['radius']) for a_, b_ in zip(strap['points'], strap['points'][1:])]
    return out+nozzle_pickups(s)


def crosses(a, b, x0, x1, radius):
    """Does segment a->b pass the full shield slab x0..x1 inside the given radius? (studies/shadow_screen.py)"""
    if (a[0]-x0)*(b[0]-x0) > 0 or (a[0]-x1)*(b[0]-x1) > 0:
        return False
    for x in (x0, x1):
        t = (x-a[0])/(b[0]-a[0]); y = a[1]+t*(b[1]-a[1]); z = a[2]+t*(b[2]-a[2])
        if math.hypot(y, z) > radius:
            return False
    return True


def box_corners(center, size):
    return [(center[0]+i*size[0]/2, center[1]+j*size[1]/2, center[2]+k*size[2]/2) for i in (-1, 1) for j in (-1, 1) for k in (-1, 1)]


def cold_optics(g):
    """Cold-side optics (forward of the shield): name -> points that must never see the core through a shield opening. The second jog
    mirror ends the aft leg of the bore, so the core sees it by construction: it is hot-side (hot_optics)."""
    out = {f'LASER_{k}': box_corners(l['center'], l['size']) for k, l in g['lasers'].items()}
    out.update({n: [pt] for n, pt in g['mirrors'].items() if n.startswith(('OPTICAL_TURN_MIRROR_', 'OPTICAL_ENTRY_MIRROR_')) or (n.startswith('OPTICAL_JOG_MIRROR_') and n.endswith('_1'))})
    return out


def hot_optics(g):
    """Hot-side elements aft of the shield or ending the bore, the replaceable cartridges (15!A83): name list."""
    names = [n for n in g['mirrors'] if n.startswith(('OPTICAL_SPLITTER_', 'OPTICAL_CORRIDOR_MIRROR_')) or (n.startswith('OPTICAL_JOG_MIRROR_') and n.endswith('_2'))]
    return names+[n for r in g['routes'].values() for n in r['heads']]+[f'OPTICAL_WINDOW_{k}_L{j}' for k, j in g['windows']]


def cylinder_gap(q, x0, x1, radius):
    """Distance from a point to a solid cylinder about the ship axis spanning x1..x0 (any order); 0 inside."""
    lo, hi = min(x0, x1), max(x0, x1)
    return math.hypot(max(lo-q[0], 0.0, q[0]-hi), max(math.hypot(q[1], q[2])-radius, 0.0))


def segment_cylinder_gap(a, b, x0, x1, radius, samples=48):
    return min(cylinder_gap(tuple(p+k/samples*(q-p) for p, q in zip(a, b)), x0, x1, radius) for k in range(samples+1))


def bore_open_rays(bore, radius, x_aft, x_fwd, q, x_target, r_target, rings=(0.0, 0.5, 1.0), n=12, samples=48):
    """Does any straight line from point q pass the whole dog-leg bore (polyline, bore radius) between x_fwd and x_aft and then reach
    the disc of radius r_target at x_target? Lines are fixed by q and a point on the bore's aft end disc, so only that disc is sampled."""
    end = bore[-1]; eps = 1e-9
    for rr in rings:
        for k in range(1 if rr == 0 else n):
            a = k*math.tau/n
            t = (end[0], end[1]+rr*radius*math.cos(a), end[2]+rr*radius*math.sin(a))
            if t[0] >= q[0]:
                continue
            if all(min(point_segment(tuple(u+(v-u)*i/samples for u, v in zip(q, t)), c, d) for c, d in zip(bore, bore[1:])) <= radius+eps
                   for i in range(samples+1) if x_aft <= q[0]+(t[0]-q[0])*i/samples <= x_fwd):
                u = (x_target-q[0])/(t[0]-q[0])
                if math.hypot(q[1]+u*(t[1]-q[1]), q[2]+u*(t[2]-q[2])) <= r_target:
                    return True
    return False


def sector_body_gap(q, lat):
    """Distance from a point to a lattice sector body (annular sector, axial span lat x1..x0)."""
    lo, hi = min(lat['x0'], lat['x1']), max(lat['x0'], lat['x1']); dx = max(lo-q[0], 0.0, q[0]-hi)
    r, th = math.hypot(q[1], q[2]), math.atan2(q[2], q[1]); half = (lat['a1']-lat['a0'])/2
    d = abs((th-lat['angle']+math.pi) % math.tau-math.pi)
    if d <= half:
        return math.hypot(dx, max(lat['r_in']-r, 0.0, r-lat['r_out']))
    plane = min(point_segment((0.0, q[1], q[2]), (0.0, lat['r_in']*math.cos(a), lat['r_in']*math.sin(a)), (0.0, lat['r_out']*math.cos(a), lat['r_out']*math.sin(a)))
                for a in (lat['a0'], lat['a1']))
    return math.hypot(dx, plane)


def bypass_gaps(s, g):
    """Smallest gap from the primary-cage members between the thrust ring and the shield face (the three outer sectors that bypass the
    core, 07!A16) to everything they go around, by class. Member radius is subtracted; plasma classes carry a plasma radius."""
    import hull_geometry
    p, m, st = s['prototype'], s['drive_manifold'], g['stations']; rmax = m['plasma_branch_max_radius_m']
    cage = [q for q in hull_geometry.cage_points(s) if st['ring'] <= q[0] <= st['shield_fwd']]
    out = {}
    def put(name, values):
        v = min(values, default=None)
        if v is not None:
            out[name] = v
    def cyl(name, x0, x1, radius):
        put(name, (cylinder_gap(q[:3], x0, x1, radius)-q[3] for q in cage))
    cyl('Fusion_Core', st['core_aft'], st['core_fwd'], p['reactor_radius_m'])
    cyl('Common_Plasma_Region', st['common_aft'], st['common_fwd'], p['common_radius_m'])
    cyl('Magnetic_Manifold', st['manifold_aft'], st['throat_entry'], p['manifold_radius_m'])
    cyl('Lattice', st['lattice_aft'], st['lattice_fwd'], m['lattice_outer_radius_m'])
    put('Seed_coils', (math.hypot(q[0]-c['x'], math.hypot(q[1], q[2])-c['radius'])-c['tube']-q[3] for c in g['coils'] for q in cage))
    def along(name, polylines, radius):
        put(name, (point_segment(q[:3], a, b)-radius-q[3] for pts in polylines for a, b in zip(pts, pts[1:]) for q in cage
                   if min(a[0], b[0])-1.5 <= q[0] <= max(a[0], b[0])+1.5))
    along('Branch_plasma', g['branches'], rmax)
    along('Exhaust_plasma', [e['points'] for e in g['exhausts']], rmax*p['nozzle_exit_radius_m']/p['nozzle_throat_radius_m'])
    hot = {n: pts for n, pts in route_beams(g).items() if not n.startswith('GATE_BEAM_')}
    put('Route_beams', (point_segment(q[:3], a, b)-m['beam_radius_m']-q[3] for pts in hot.values() for a, b in zip(pts, pts[1:]) for q in cage
                        if min(a[0], b[0])-1.5 <= q[0] <= max(a[0], b[0])+1.5))
    put('Route_mirrors', (math.dist(q[:3], pt)-m['mirror_radius_m']-q[3] for pt in g['mirrors'].values() for q in cage))
    put('Yokes', (point_segment(q[:3], mem['a'], mem['b'])-mem['radius']-q[3] for mem in structure_members(s) if mem['name'].startswith('Nozzle_Yoke') for q in cage
                  if min(mem['a'][0], mem['b'][0])-1.5 <= q[0] <= max(mem['a'][0], mem['b'][0])+1.5))
    return out


def rail_span(s):
    """Sector rails of the cage at the sector_pickup_nodes angles: {angle_deg: (x_min, x_max)} over the thrust ring to the cage end."""
    import hull_geometry
    p, st = s['prototype'], s['structure']; out = {}
    for n in st['sector_pickup_nodes']:
        a = math.radians(p['ring_phase_deg'])+n*math.tau/st['ring_nodes']
        xs = [q[0] for q in hull_geometry.cage_points(s) if abs(q[3]-p['structural_rail_radius_m']) < 1e-12 and math.hypot(q[1]-math.hypot(q[1], q[2])*math.cos(a), q[2]-math.hypot(q[1], q[2])*math.sin(a)) < 1e-6]
        out[round(math.degrees(a) % 360, 6)] = (min(xs), max(xs))
    return out


def check(s, d=None, members=None):
    """Clearances and routing rules. Failures block validation; findings are real conflicts reported, not hidden.
    members replaces structure_members(s) (tests force a pickup back onto the nozzle axis)."""
    import hull_geometry
    p, m = s['prototype'], s['drive_manifold']; g = geometry(s); st = g['stations']
    spine = p['spine_radius_m']; rmax = m['plasma_branch_max_radius_m']; gap = m['plasma_hardware_clearance_m']; clr = p['mechanical_clearance_m']
    rb, beam_clr, rm = m['beam_radius_m'], m['beam_clearance_m'], m['mirror_radius_m']
    ox = optics_x(s); sp0, sp1 = spine_span(s); hub = g['hub']
    failures, findings, meas = [], [], {}
    def need(ok, message):
        if not ok:
            failures.append(message)
    # Station order: core -> common -> throat inside the manifold envelope -> lattice -> nozzles; optics around the shield and hub.
    need(st['core_aft'] >= st['common_fwd'] and math.isclose(st['common_aft'], st['throat_entry']), 'Throat must start at the common/manifold interface (IF_MANIFOLD_INPUT)')
    need(st['throat_entry'] > st['throat_exit'] > st['lattice_fwd'] > st['lattice_aft'] > st['manifold_aft'] >= st['inlet'], 'Throat and lattice must sit inside the manifold envelope, ahead of the nozzles')
    need(st['core_fwd'] < min(ox['splitter_x'].values()) and max(ox['splitter_x'].values()) < st['shield_aft'] < st['shield_fwd'] < ox['route_jog_x'] < ox['hub_forward_x'] < ox['turn_x'] < ox['laser_x']-m['laser_length_m']/2,
         'Optical stations: core < splitters < shield slab < jog planes (inside the hub) < hub face < turn mirrors < lasers')
    lat_mid = (st['lattice_fwd']+st['lattice_aft'])/2
    need(st['throat_exit'] > ox['head_x'] and st['lattice_fwd'] >= ox['head_x'] > lat_mid, 'Distributor heads: aft of the throat exit, inside the lattice span and forward of the gate targets')
    need(m['head_radius_m']+m['head_size_m'] < p['manifold_radius_m'], 'Distributor heads inside the Magnetic_Manifold envelope')
    need(math.isclose(rmax, 2*p['flow_radius_m']), 'Largest plasma radius is the share-1 branch (2 x flow_radius)')
    need(g['common']['outer'] < p['common_radius_m'] and throat_geometry(s)[1] < m['common_stream_outer_radius_m'], 'Common stream and throat waist stay inside the common envelope')
    # Solid plasma and the terminated spine (06!A47, 15!A70, 15!A72): the plasma column has no bore and no structure passes through it.
    need(g['common']['inner'] == 0 and all(r[1] == 0 for r in g['throat_rings']) and all(r[1] == 0 for sp in g['separatrices'] for r in sp['rows']), 'Plasma must be solid: inner radius 0')
    meas['spine_x'] = [sp0, sp1]; meas['spine_core_axial_gap_m'] = sp0-st['core_fwd']
    need(sp0 >= st['shield_fwd'], 'Spine must end forward of the shield slab: no on-axis shield penetration')
    need(meas['spine_core_axial_gap_m'] >= p['shadow_thickness_m'], 'Spine end must stand off the core by at least the shield thickness')
    spans = [(st['core_aft'], st['core_fwd']), (st['common_aft'], st['common_fwd']), (st['manifold_aft'], st['throat_entry'])]
    need(not any(lo <= sp0+(sp1-sp0)*k/200 <= hi for lo, hi in spans for k in range(201)), 'Spine reaches the core, common region or manifold')
    # Branch paths: axial at both ends, smooth, separated.
    R1, r0 = g['nozzle_radius'], m['branch_start_radius_m']; dx = st['throat_exit']-st['inlet']
    slope = [(R1-r0)*6*t*(1-t)/dx for t in [k/400 for k in range(401)]]
    curv = [abs((R1-r0)*(6-12*t)/dx**2)/(1+sl*sl)**1.5 for t, sl in zip([k/400 for k in range(401)], slope)]
    meas['branch_max_off_axis_deg'] = math.degrees(math.atan(max(slope)))
    meas['branch_min_bend_radius_m'] = 1/max(curv)
    meas['branch_end_angles_deg'] = [math.degrees(math.atan(slope[0])), math.degrees(math.atan(slope[-1]))]
    need(max(abs(x) for x in meas['branch_end_angles_deg']) < 1e-9, 'Branches must be axial where they leave the throat and enter the nozzles')
    need(meas['branch_min_bend_radius_m'] > 2*rmax, 'Branch bend tighter than its own diameter')
    sep = min(norm(sub(g['branches'][0][k], g['branches'][1][k])) for k in range(len(g['branches'][0])))
    meas['branch_centreline_separation_min_m'] = sep; meas['branch_gap_at_max_radius_m'] = sep-2*rmax
    need(sep-2*rmax >= gap, 'Neighbouring branches touch at the largest plasma radius')
    need(all(q[0] >= st['inlet']-1e-9 for q in g['branches'][0]), 'Branch overruns the nozzle inlet')
    # Aft ring: hub annulus, hub webs, nozzle pickups and the nozzle yokes (pickups start on the inlet yoke's outer face, off the nozzle axis).
    hub_x0, hub_x1 = st['ring']-.8, st['ring']+.8
    thrust_hub = min(math.hypot(q[1], q[2])-rmax-s['structure']['hub_diameter_m']/2 for b in g['branches'] for q in b if hub_x0 <= q[0] <= hub_x1)
    meas['branch_hub_gap_m'] = thrust_hub; need(thrust_hub >= gap, 'Branch plasma reaches the central thrust hub')
    ring_inner = s['structure']['ring_od_m']/2-s['structure']['ring_radial_depth_m']  # inner truss ring face
    meas['branch_ring_gap_m'] = ring_inner-max(math.hypot(q[1], q[2])+rmax for b in g['branches'] for q in b if abs(q[0]-st['ring']) <= s['structure']['ring_depth_m']/2)
    need(meas['branch_ring_gap_m'] >= gap, 'Branch plasma reaches the thrust ring')
    web, pickup_overlap, exhaust_web = [], [], []
    for mem in (structure_members(s) if members is None else members):
        for j, b in enumerate(g['branches']):
            if mem.get('nozzle') == j and mem['name'].startswith('Nozzle_Pickup_'):
                # The member's own branch: report how far it runs inside the plasma path; every sample is still checked.
                inside = [q for q in b if point_segment(q, mem['a'], mem['b']) < rmax+mem['radius']]
                pickup_overlap.append(dict(member=mem['name'], branch=j+1, samples_inside=len(inside), length_inside_m=round(norm(sub(inside[0], inside[-1])) if len(inside) > 1 else 0.0, 3)))
            web.append(dict(member=mem['name'], branch=j+1, gap_m=min(point_segment(q, mem['a'], mem['b']) for q in b)-rmax-mem['radius']))
        # Exhaust plasma (radius follows the nozzle field envelope) against the same member, over a fine sample of each exhaust run.
        for j, ex in enumerate(g['exhausts']):
            for (q0, f0), (q1, f1) in zip(zip(ex['points'], ex['factors']), list(zip(ex['points'], ex['factors']))[1:]):
                for k in range(21):
                    q = tuple(a_+(b_-a_)*k/20 for a_, b_ in zip(q0, q1))
                    exhaust_web.append(point_segment(q, mem['a'], mem['b'])-rmax*(f0+(f1-f0)*k/20)-mem['radius'])
    meas['branch_ring_member_min_gap_m'] = min(w['gap_m'] for w in web)
    need(meas['branch_ring_member_min_gap_m'] >= gap, 'Branch plasma reaches a hub web, nozzle pickup or nozzle yoke')
    meas['exhaust_ring_member_min_gap_m'] = min(exhaust_web)
    need(meas['exhaust_ring_member_min_gap_m'] >= gap, 'Exhaust plasma reaches a hub web, nozzle pickup or nozzle yoke')
    if any(o['samples_inside'] for o in pickup_overlap):
        findings.append(dict(id='PICKUP_IN_PLASMA', detail='A nozzle pickup starts on the nozzle axis, so its first segment lies inside the plasma path. The pickup should attach to the nozzle yoke, not the axis.', overlap=pickup_overlap))
    yokes = nozzle_yokes(s)
    meas['yoke_coil_gap_m'] = min(r['coil_gap'] for y in yokes for r in y['rings'])
    need(meas['yoke_coil_gap_m'] > 0 and math.isclose(meas['yoke_coil_gap_m'], s['drive_hot_section']['yoke_standoff_m']), 'Nozzle yokes must stand off the coils by yoke_standoff_m')
    meas['yoke_outer_axis_radius_m'] = max(math.hypot(*y['axis'])+r['r_out'] for y in yokes for r in y['rings'])
    meas['yoke_skin_gap_m'] = min(hull_geometry.inner_radius_at(s, x)-math.hypot(*y['axis'])-r['r_out'] for y in yokes for r in y['rings'] for x in (r['x0'], r['x1']))
    meas['yoke_neighbour_gap_m'] = min(math.dist(a['axis'], b['axis'])-ra['r_out']-rb_['r_out'] for i, a in enumerate(yokes) for b in yokes[i+1:] for ra, rb_ in zip(a['rings'], b['rings']))
    need(meas['yoke_skin_gap_m'] >= clr, 'Nozzle yoke reaches the hull inner skin')
    need(meas['yoke_neighbour_gap_m'] >= clr, 'Neighbouring nozzle yokes touch')
    # Lattice and seed coils around the branches.
    lat_gap = min(g['lattice'][0]['r_in']-math.hypot(q[1], q[2])-rmax for b in g['branches'] for q in b if st['lattice_aft'] <= q[0] <= st['lattice_fwd'])
    meas['branch_lattice_gap_m'] = lat_gap; need(lat_gap >= gap, 'Branch plasma reaches a lattice sector')
    need(m['lattice_outer_radius_m'] < p['manifold_radius_m'] and m['lattice_inner_radius_m'] < m['lattice_outer_radius_m'], 'Lattice sectors inside the manifold envelope')
    need(4*2*m['lattice_half_angle_deg'] < 360, 'Lattice sectors overlap')
    coil_gaps = []
    for c in g['coils']:
        near = [math.hypot(q[1], q[2]) for b in g['branches'] for q in b if abs(q[0]-c['x']) <= c['tube']+rmax] or [m['common_stream_outer_radius_m']]
        coil_gaps.append(c['radius']-c['tube']-max(near)-rmax)
        need(c['x']-c['tube'] > st['lattice_fwd'] or c['x']+c['tube'] < st['lattice_aft'], 'Seed coil runs through a lattice sector')
        need(c['radius']+c['tube'] <= p['manifold_radius_m'], 'Seed coil outside the manifold envelope')
    meas['branch_seed_coil_gap_m'] = min(coil_gaps); need(min(coil_gaps) >= gap, 'Branch plasma reaches a seed coil')
    # Exhaust inside the nozzle field envelope: coil inner faces at the four NOZZLE_Coil stations.
    coil_inner = [(c['x'], c['inner']) for c in nozzle_coils(s)]
    ex = g['exhausts'][0]
    meas['exhaust_nozzle_coil_gap_m'] = min(r-rmax*exhaust_factor(ex, st, u) for u, r in coil_inner)
    need(meas['exhaust_nozzle_coil_gap_m'] >= gap, 'Exhaust plasma reaches a nozzle coil')
    # Bypass: the three outer sectors of the cage clear everything they go around between the thrust ring and the shield face.
    bp = bypass_gaps(s, g); plasma = {'Branch_plasma', 'Exhaust_plasma'}
    meas['bypass_gaps_m'] = bp; meas['bypass_member_min_gap_m'] = min(v for k, v in bp.items() if k not in plasma)
    meas['bypass_plasma_min_gap_m'] = min(v for k, v in bp.items() if k in plasma)
    need(meas['bypass_member_min_gap_m'] >= clr and meas['bypass_plasma_min_gap_m'] >= gap, f'Bypass sector members too close to {min(bp, key=bp.get)}')
    rails = rail_span(s); meas['bypass_rails'] = {str(k): list(v) for k, v in rails.items()}
    need(len(rails) == len(s['structure']['sector_pickup_nodes']) == 3 and all(lo <= st['ring']+1e-9 and hi >= st['shield_fwd'] for lo, hi in rails.values()),
         'Three sector rails must run from the thrust ring to past the shield face')
    # Optics: straight segments that never propagate forward, a dog-leg bore per route beside the spine end, independent routes.
    beams = route_beams(g)
    forward = [name for name, pts in beams.items() for a, b in zip(pts, pts[1:]) if b[0] > a[0]+1e-9]
    need(not forward, f'Optical segments propagate forward: {forward}')
    bore_r = m['optical_channel_radius_m']
    meas['bore_spine_gap_m'] = min(math.hypot(q[1], q[2])-bore_r-spine for r in g['routes'].values() for q in r['bore'])
    meas['bore_hub_wall_m'] = hub['radius']-max(math.hypot(q[1], q[2])+bore_r for r in g['routes'].values() for q in r['bore'])
    need(meas['bore_spine_gap_m'] >= clr, 'Optical bore reaches the spine footprint')
    need(meas['bore_hub_wall_m'] >= clr, 'Optical bore leaves too little hub wall')
    need(hub['radius'] <= p['shadow_radius_m']-clr and hub['x0'] < ox['route_jog_x'] < hub['x1'], 'Terminated hub: inside the shield radius, jog planes inside the hub')
    cold = cold_optics(g)
    core_pts = [(x, r*math.cos(a), r*math.sin(a)) for x in (st['core_fwd'], (st['core_fwd']+st['core_aft'])/2) for r in (0.0, p['reactor_radius_m']/2, p['reactor_radius_m']) for a in [k*math.pi/6 for k in range(12)]]
    exposed = {k: any(bore_open_rays(r['bore'], bore_r, st['shield_aft'], ox['hub_forward_x'], q, st['core_fwd'], p['reactor_radius_m']) for r in g['routes'].values() for q in pts) for k, pts in cold.items()}
    need(not any(exposed.values()), f'Cold-side optics see the core through a shield bore: {[k for k, v in exposed.items() if v]}')
    shadow = {k: all(crosses(c, q, st['shield_aft'], st['shield_fwd'], p['shadow_radius_m']) for c in core_pts for q in pts) for k, pts in cold.items() if k.startswith('LASER')}
    need(all(shadow.values()), 'Lasers must sit inside the shadow-shield cone of the core envelope')
    # Route independence: nothing shared, and the two routes keep their clearance.
    ra, rb_ = g['routes']['A'], g['routes']['B']
    shared = set(ra['mirrors'])&set(rb_['mirrors']) | set(ra['heads'])&set(rb_['heads'])
    own = lambda r: [pts for n, pts in beams.items() if n.startswith(('OPTICAL_BEAM_'+('A' if r is ra else 'B'), 'OPTICAL_LEG_'+('A' if r is ra else 'B')))]
    sep = min(segment_segment(a, b, c, e, 32)-2*rb for pa in own(ra) for pb in own(rb_) for a, b in zip(pa, pa[1:]) for c, e in zip(pb, pb[1:]))
    msep = min(math.dist(u, v)-2*rm for u in ra['mirrors'].values() for v in rb_['mirrors'].values())
    mbeam = min(min(point_segment(u, c, e) for pb in own(rb_) for c, e in zip(pb, pb[1:]))-rm-rb for u in ra['mirrors'].values())
    mbeam = min(mbeam, min(min(point_segment(u, c, e) for pa in own(ra) for c, e in zip(pa, pa[1:]))-rm-rb for u in rb_['mirrors'].values()))
    meas['route_separation_m'] = min(sep, msep, mbeam)
    need(not shared and meas['route_separation_m'] >= beam_clr, 'Optical routes A and B must share no element and keep the beam clearance')
    # Gate coverage: each lattice sector receives exactly one chord from each route, from a head that sits in a lattice gap.
    half = math.radians(m['lattice_half_angle_deg']); head_ang = m['head_size_m']/m['head_radius_m']
    cover = {j: sorted(k for k, jj in g['gate_beams'] if jj == j) for j in range(1, 5)}
    need(all(c == ['A', 'B'] for c in cover.values()), f'Each lattice gate needs exactly one A and one B beam: {cover}')
    gaps_deg = [math.degrees(min(abs((math.radians(leg['head_deg'])-lat['angle']+math.pi) % math.tau-math.pi) for lat in g['lattice'])-half-head_ang) for r in g['routes'].values() for leg in r['legs']]
    meas['head_gap_angle_min_deg'] = min(gaps_deg); need(min(gaps_deg) > 0, 'A distributor head sits over a lattice sector')
    # Gate chords clear the branch plasma, the seed coils and every non-target lattice sector.
    chord_branch = min(segment_segment(c[0], c[1], a, b, 64)-rmax-rb for c in g['gate_beams'].values() for br in g['branches'] for a, b in zip(br, br[1:]))
    meas['gate_beam_branch_gap_m'] = chord_branch; need(chord_branch >= gap, 'Gate beam reaches branch plasma')
    beam_coil = min(point_segment(radial(c['x'], c['radius'], a), *b)-c['tube']-rb for c in g['coils'] for b in g['gate_beams'].values() for a in [k*math.pi/36 for k in range(72)])
    meas['gate_beam_seed_coil_gap_m'] = beam_coil; need(beam_coil >= beam_clr, 'Gate beam clips a seed coil')
    other = min(sector_body_gap(tuple(u+(v-u)*i/60 for u, v in zip(*b)), lat)-rb for (k, j), b in g['gate_beams'].items() for jj, lat in enumerate(g['lattice'], 1) if jj != j for i in range(61))
    meas['gate_beam_other_sector_min_m'] = other; need(other >= beam_clr, 'Gate beam reaches another lattice sector')
    # Corridor: the hot-side route clears the cage, the hull skin and the three envelopes.
    cage = hull_geometry.cage_points(s)
    hot_segs = [(a, b) for n, pts in beams.items() if n.startswith(('OPTICAL_LEG_', 'OPTICAL_BEAM_')) for a, b in zip(pts, pts[1:]) if min(a[0], b[0]) <= st['shield_aft']]
    meas['route_cage_min_gap_m'] = min(min(point_segment(q[:3], a, b) for a, b in hot_segs if min(a[0], b[0])-1.5 <= q[0] <= max(a[0], b[0])+1.5)-rb-q[3]
                                       for q in cage if any(min(a[0], b[0])-1.5 <= q[0] <= max(a[0], b[0])+1.5 for a, b in hot_segs))
    meas['route_mirror_cage_min_gap_m'] = min(math.dist(q[:3], pt)-rm-q[3] for n, pt in g['mirrors'].items() if pt[0] <= st['shield_aft'] for q in cage if abs(q[0]-pt[0]) < 1.5)
    skin = lambda a, b: min(hull_geometry.inner_radius_at(s, a[0]+(b[0]-a[0])*k/20)-math.hypot(a[1]+(b[1]-a[1])*k/20, a[2]+(b[2]-a[2])*k/20) for k in range(21))
    meas['route_skin_min_gap_m'] = min(min(skin(a, b)-rb for a, b in hot_segs), min(hull_geometry.inner_radius_at(s, pt[0])-math.hypot(pt[1], pt[2])-rm for pt in g['mirrors'].values() if pt[0] <= st['shield_aft']))
    need(min(meas['route_cage_min_gap_m'], meas['route_mirror_cage_min_gap_m'], meas['route_skin_min_gap_m']) >= clr, 'Optical corridor route too close to the cage or the hull skin')
    envs = [('Fusion_Core', st['core_aft'], st['core_fwd'], p['reactor_radius_m']), ('Common_Plasma_Region', st['common_aft'], st['common_fwd'], p['common_radius_m']),
            ('Magnetic_Manifold', st['manifold_aft'], st['throat_entry'], p['manifold_radius_m'])]
    env_gap = []
    for n, pts in beams.items():
        if n.startswith('GATE_BEAM_'):
            continue
        for k, (a, b) in enumerate(zip(pts, pts[1:])):
            last_leg = n.startswith('OPTICAL_LEG_') and k == len(pts)-2     # the final inward segment ends in the manifold: the window crossing
            env_gap += [segment_cylinder_gap(a, b, x0, x1, r)-rb for name, x0, x1, r in envs if not (last_leg and name == 'Magnetic_Manifold')]
    meas['route_envelope_min_gap_m'] = min(env_gap); need(meas['route_envelope_min_gap_m'] >= beam_clr, 'Optical route too close to the core, common region or manifold envelope')
    face = min(abs(a[0]-st['shield_aft'])-rb for n, pts in beams.items() if n.startswith(('OPTICAL_LEG_', 'OPTICAL_BEAM_')) for a in pts if a[0] < st['shield_aft'])
    meas['route_shield_face_gap_m'] = face; need(face >= beam_clr, 'Optical route too close to the shield face')
    meas['route_core_face_gap_m'] = min(a[0]-st['core_fwd'] for n, pts in beams.items() if n.startswith('OPTICAL_BEAM_') for a in pts if a[0] < st['shield_aft'])-rb
    need(meas['route_core_face_gap_m'] >= beam_clr, 'Optical route too close to the core face')
    meas['cold_optics_core_sight'] = exposed; meas['lasers_in_shadow'] = shadow
    findings.append(dict(id='SPINE_TERMINATION', detail='Structural_Spine (r %.3f m) ends on the PROTOTYPE terminated hub (r %.2f m) on the forward face of the shadow shield; no structure crosses the core, common region or manifold, and the plasma is solid. Drive thrust reaches the forward ship through the 12-node thrust ring and the three outer sector rails around the core. The bulkhead structure, hub shielding and load shares are OPEN (07!H16, 15!G70).' % (spine, hub['radius']),
                         spine_x=[sp0, sp1], hub_x=[hub['x0'], hub['x1']], core_x=[st['core_aft'], st['core_fwd']], bypass_rails_deg=sorted(rails)))
    findings.append(dict(id='HOT_SIDE_OPTICS', detail='The replaceable cartridges are hot-side: the second jog mirror ends the aft leg of each bore and so sees the core, the splitter sits in the shield-to-core gap, and the corridor mirrors, distributor heads and gate windows sit aft of the shield. They must be sacrificial or robotically replaceable; humans enter only after shutdown and cooldown (15!C83). Cartridge geometry and protection are OPEN (14!G31).',
                         elements=hot_optics(g)))
    findings.append(dict(id='SEPARATRIX_THROUGH_HUB_WEBS', detail='Separatrices sit midway between branches (0/90/180/270 deg), the same angles as the hub webs at the thrust ring. They are field boundaries, not material, so this only shows in the debug layer.'))
    rec_arm = {k: couple_arm(s, channel_loss_shares(s, k)) for k in range(1, 5)}
    rejected = couple_arm(s, [1/3, 1/3, 0.0, 1/3])
    need(all(a['couple_arm_m'] == 0 for a in rec_arm.values()), 'Channel-loss recovery must leave no couple for any failed channel (06!A51)')
    findings.append(dict(id='CHANNEL_ISOLATION_COUPLE', detail='Owner recovery (06!A51, 15!C76): isolating a flux channel and derating its diametric opposite leaves the surviving diagonal at %.0f%% thrust with couple %.3f m for every failed channel. The rejected default, a three-channel asymmetric state with the failed channel simply dropped, leaves %.2f m. The transition torque falls to RCS/Momentum control (15!I76), not modelled; vector authority is OPEN.' % (100*s['propulsion']['manifold']['channel_loss_recovery']['surviving_thrust_fraction'], max(a['couple_arm_m'] for a in rec_arm.values()), rejected['couple_arm_m']),
                         recovery_couple=rec_arm[3], rejected_three_channel_couple=rejected))
    # Radiator members: closest thermal support to the exhaust run (plume boundary itself is OPEN, R2).
    if d is not None:
        import thermal_geometry
        rad_members = thermal_geometry.supports(s, d)
        meas['exhaust_radiator_member_min_m'] = min(segment_segment(e['points'][0], e['points'][-1], a, b, 32)-mem['radius'] for e in g['exhausts'] for mem in rad_members for a, b in thermal_geometry.legs(mem))
        need(meas['exhaust_radiator_member_min_m'] > p['radiator_member_clearance_m'], 'Exhaust run reaches a radiator support')
    # Nozzle placement (Q26): the screen reproduces the owner's rounded figures.
    npl = s['propulsion']['manifold']['nozzle_placement']
    need(meas['exhaust_nozzle_coil_gap_m'] >= npl['accepted_coil_clearance_m']-0.005, 'nozzle_placement: coil clearance below the accepted 0.09 m')
    need(meas['branch_max_off_axis_deg'] <= npl['accepted_max_off_axis_deg']+0.05, 'nozzle_placement: off-axis routing above the accepted 21.6 deg')
    need(meas['branch_min_bend_radius_m'] >= npl['accepted_min_bend_radius_m']-0.005, 'nozzle_placement: bend radius below the accepted 4.74 m')
    import drive_hot_section
    hot_section = drive_hot_section.check(s, g, d)
    failures += hot_section['failures']; findings += hot_section['findings']; meas.update(hot_section['measurements'])
    return dict(passed=not failures, failures=failures, measurements=meas, findings=findings)


def report(s, d=None):
    c = check(s, d)
    return dict(generated_by='drive_manifold.py', status='PROTOTYPE geometry screen; not an engineering validation',
                pass_=c['passed'], failures=c['failures'], measurements=c['measurements'], findings=c['findings'],
                couples={name: couple_arm(s, shares) for name, shares in [('balanced', [.25]*4), ('pitch', [.3, .3, .2, .2]), ('yaw', [.3, .2, .3, .2]),
                                                                              ('owner_example_yaw', s['propulsion']['manifold']['example_maneuver']['shares']),
                                                                              ('channel_loss_recovery_F3', channel_loss_shares(s, 3)), ('rejected_three_channel_F3', [1/3, 1/3, 0, 1/3])]},
                actions={k: dict(frame_range=v['frame_range'], description=v['description']) for k, v in actions(s).items()},
                open=[k for k in ['optical_power', 'optical_wavelength', 'gate_response_time', 'optical_to_lattice_coupling', 'throat_field_profile'] if s['propulsion']['manifold'][k].get('known') is False])


if __name__ == '__main__':
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from spec import load, derived
    data, *_ = load()
    out = report(data, derived(data))
    OUTPUT.write_text(json.dumps(out, indent=2)+'\n')
    print(json.dumps({'pass': out['pass_'], 'failures': out['failures'], **{k: v for k, v in out['measurements'].items() if not isinstance(v, dict)}}, indent=2))
