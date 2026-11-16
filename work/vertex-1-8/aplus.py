"""Vertex 1.8 Phase F: the Adaptive Vertex A+ review prototype (owner go 2026-11-16 11:49Z). Work in progress, not canon: nothing in
src/, tests/, tools/, godot/, web/ or CI reads this folder.

Pure (standard library + the pure modules). It turns today's engine parts (vertex_engine.parts) into the A+ prototype and defines its
motion as a function of the control state, so the Blender review file and the browser review read the same numbers:

  parts_aplus(s)      today's 264 parts, reshaped where A+ needs it (L3 hoop at the rail radius, cylindrical rail segment), each tagged
                      with its moving group (STATIC, L4, PETAL_L1_j, PETAL_L2_j), plus the new A+ parts (PROTOTYPE)
  timeline(s)         the nine states: physical durations, compressed playback durations, control values and the diagnostics derived
                      from the shared evidence (vertex_adaptive, vertex_dynamic, vertex_magnet field), sampled for playback
  pose(s, v)          rigid transform of every moving group for control values v (engine frame)

  python3 work/vertex-1-8/aplus.py            # writes work/vertex-1-8/aplus_timeline.json and prints the summary

Decisions applied (owner, 2026-11-16): SP-18A parked (no joints in any winding: petals move only shells and armour); the ignition flywheel
is OPTIONAL (built in its own collection, off by default; first ignition names the bootstrap source as OPEN); the physics problems stay OPEN.
"""
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT/'src'/'wayfarer'))
import spec  # noqa: E402
import vertex_engine as ve  # noqa: E402
import vertex_cluster as vc  # noqa: E402
import vertex_adaptive as vad  # noqa: E402
import drive_manifold as dm  # noqa: E402

OUT = HERE/'aplus_timeline.json'

# PROTOTYPE choices (unsourced, review only)
PROTO = dict(
    flywheel=False,                     # owner: optional until its mass and energy requirements are resolved
    petal_lift_m=1.45,                  # shell segment withdraws radially outward by more than its own section (clears the winding)
    armour_withdraw_m=0.9,              # armour shoe withdraws along the burn direction (exchange path)
    rotor_display_rev=6.0,              # display revolutions of a dynamo rotor per playback second at full charging speed
    alignment_display_gain=40.0,        # the 10 mm survey error is invisible at ship scale; the alignment view may magnify it
    fps=24,
)

# Compressed playback per state (seconds). The physical duration is shown beside it; nothing pretends field formation takes seconds.
PLAY_S = dict(DORMANT=7.0, MECHANICAL_PREPARATION=9.0, DIGITAL_ALIGNMENT=7.0, FIELD_FORMATION=10.0, PLASMA_CALIBRATION=8.0,
              FIRST_IGNITION=6.0, VERTEX_LOCK=5.0, SUSTAINED_MODULATION=8.0, SHUTDOWN_OR_FAILURE=8.0)
DORMANT_SHOW_S = 7.0 * 24              # the dormant state is indefinite; the review shows a service inspection of the petals inside it

LOOPS = ['L1', 'L2', 'L3', 'L4']


def load():
    s = spec.load(ROOT)[0]
    R = json.loads(vad.EVIDENCE_PATH.read_text())
    return s, R


# ---------- geometry ------------------------------------------------------------------------------------------------------------------

def _r(p):
    return math.hypot(p[1], p[2])


def _scale_r(p, r_new):
    r = _r(p)
    return (p[0], p[1]*r_new/r, p[2]*r_new/r) if r > 1e-9 else p


def _petal_of(name):
    for L in ('L1', 'L2'):
        for stem in (f'VTX_{L}_Segment_', f'VTX_{L}_Armour_'):
            if name.startswith(stem) and name[len(stem):].isdigit():
                return f'PETAL_{L}_{int(name[len(stem):])}'
    return None


def parts_aplus(s, R):
    """Today's parts with the A+ reshaping and the moving-group tag, plus the new parts."""
    g = ve.config(s)['geometry']; st = ve.stations(s); loops = {l['name']: l for l in st['loops']}
    CA = R['carriages']; rail_R = CA['rail']['radius_m']
    l3 = loops['L3']; hx3 = ve.hoop_x(l3); old3 = l3['r']+l3['cryostat_minor_m']+g['cage_clearance_m']; d3 = rail_R-old3
    in_l4 = vad.ring_members('L4')
    out = []
    for p in ve.parts(s):
        p = dict(p)
        n = p['name']
        if n == 'VTX_Cage_Hoop_L3':
            p['R'] = rail_R; p['note'] += ' (A+: grown to the rail radius; the aft longeron segments become cylindrical rails)'
        elif n.startswith('VTX_Loop_Seat_L3_'):
            p['points'] = [p['points'][0], _scale_r(p['points'][1], rail_R)]
        elif p['shape'] == 'tube' and 'points' in p and n.startswith(('VTX_Cage_Longeron_', 'VTX_Exchange_Rail_', 'VTX_Lithium_Supply', 'VTX_Lithium_Return',
                                                                      'VTX_Cryo_Feed_', 'VTX_Coil_Current_Leads')) and not n.startswith('VTX_Cryo_Feed_C'):
            p['points'] = [_scale_r(q, _r(q)+d3) if abs(q[0]-hx3) < 1e-6 else q for q in p['points']]
        elif n.startswith(('VTX_L3_Lead_Branch', 'VTX_L3_Cryo_Branch', 'VTX_L3_Lithium_')):
            q = p['points'][0]; p['points'] = [_scale_r(q, _r(q)+d3)]+p['points'][1:]
        p['group'] = 'L4' if in_l4(n) else (_petal_of(n) or 'STATIC')
        if n.startswith('VTX_Cage_Longeron_'):
            p['note'] += ' (A+: the segment between the L3 and L4 hoops is a cylindrical rail for the L4 carriage)'
        out.append(p)
    out += new_parts(s, R)
    return out


def new_parts(s, R):
    """A+ machinery (all PROTOTYPE in position and size; masses from [vertex_adaptive])."""
    g = ve.config(s)['geometry']; st = ve.stations(s); out = []; P = ve.part; pol = ve.pol
    loops = {l['name']: l for l in st['loops']}; coils = st['coils']
    rail_R = R['carriages']['rail']['radius_m']
    # HTS dynamos and persistent switches: one per coil, beside its lead turret (C1/C2 at 270 deg, loops at 90 deg)
    for c in coils+st['loops']:
        az = 270.0 if c in coils else 90.0
        rt = c['r']+c['cryostat_minor_m']; grp = 'L4' if c['name'] == 'L4' else 'STATIC'
        dx = 1.05 if c in coils else -1.15
        hc = pol(c['x']+dx, rt+0.35, az)
        out.append(P(f'VTX_{c["name"]}_Dynamo_Housing', 'MAGNETIC_COILS' if c in coils else 'MAGNETIC_NOZZLE', 'disc', 'cryostat',
                     note=f'{c["name"]} HTS flux-pump dynamo housing (charges the coil without current leads; still once persistent). PROTOTYPE size',
                     center=hc, radius=0.42, depth=0.36, n=20))
        out[-1]['group'] = grp
        rc = (hc[0]+(0.24 if dx > 0 else -0.24), hc[1], hc[2])
        out.append(P(f'VTX_{c["name"]}_Dynamo_Rotor', 'MAGNETIC_COILS' if c in coils else 'MAGNETIC_NOZZLE', 'disc', 'coil',
                     note=f'{c["name"]} dynamo rotor (HTS magnets on the rim; spins only while the field forms)', center=rc, radius=0.34, depth=0.06, n=20))
        out[-1].update(group=f'ROTOR_{c["name"]}', parent=grp, origin=rc)
        out.append(P(f'VTX_{c["name"]}_Dynamo_Index', 'MAGNETIC_COILS' if c in coils else 'MAGNETIC_NOZZLE', 'box', 'lamp',
                     note='Rotor index mark (makes the spin readable)', center=(rc[0]+(0.04 if dx > 0 else -0.04), rc[1]+0.2*math.cos(math.radians(az)),
                                                                             rc[2]+0.2*math.sin(math.radians(az))), size=(0.03, 0.22, 0.06), az=az))
        out[-1].update(group=f'ROTOR_{c["name"]}', parent=grp, origin=rc)
        sw = pol(c['x']+dx*0.45, rt+0.75, az+(8 if c in coils else -8))
        out.append(P(f'VTX_{c["name"]}_Persistent_Switch', 'ELECTRICAL', 'box', 'cryostat', note=f'{c["name"]} persistent switch (closes when the field is formed)',
                     center=sw, size=(0.45, 0.35, 0.35), az=az))
        out[-1]['group'] = grp
    # L4 carriage drive and lock blocks on the rails, with lock lamps
    l4 = loops['L4']; hx4 = ve.hoop_x(l4)
    for j in range(g['cage_longerons']):
        az = 22.5+j*360/g['cage_longerons']
        out.append(P(f'VTX_L4_Carriage_Block_{j+1}', 'STRUCTURE', 'box', 'structure', note='L4 carriage drive and lock block (rack drive on the rail; lock pins engage at the two stations)',
                     center=pol(hx4+0.25, rail_R+0.05, az), size=(0.9, 0.55, 0.6), az=az))
        out[-1]['group'] = 'L4'
        out.append(P(f'VTX_L4_Lock_Lamp_{j+1}', 'INSTRUMENTATION', 'sphere', 'lamp', note='Lock state lamp (amber travelling, green locked)',
                     center=pol(hx4+0.25, rail_R+0.42, az), radius=0.12, n=6))
        out[-1].update(group='L4', lamp='lock')
    # station stops on the rails (fixed): stowed and operating
    stow = R['carriages']['stow_stroke_m']['L4']
    for j in range(g['cage_longerons']):
        az = 22.5+j*360/g['cage_longerons']
        for tag, x in (('Operating', hx4-0.35), ('Stowed', hx4+stow+0.85)):
            out.append(P(f'VTX_Rail_Stop_{tag}_{j+1}', 'STRUCTURE', 'box', 'structure', note=f'{tag} station lock seat on the rail',
                         center=pol(x, rail_R, az), size=(0.25, 0.4, 0.45), az=az))
            out[-1]['group'] = 'STATIC'
    # trim coils at L3 and L4 (normal-conducting, warm): four saddle arcs each, forward of the loop
    for name in ('L3', 'L4'):
        l = loops[name]
        for j in range(4):
            a0 = 45.0+90*j-14; a1 = a0+28
            out.append(P(f'VTX_{name}_Trim_Coil_{j+1}', 'MAGNETIC_NOZZLE', 'torus', 'power', note=f'{name} trim coil {j+1}/4 (fast field shaping and steering; ohmic)',
                         x=l['x']+l['cryostat_minor_m']+0.3, R=l['r']+0.2, a=0.13, arc=(a0, a1), nu=8, nv=6))
            out[-1]['group'] = 'L4' if name == 'L4' else 'STATIC'
    # metrology heads (alignment): on each hoop, aimed across the engine; beams are an effect object shown during alignment
    for l in st['loops']:
        R0 = rail_R if l['name'] in ('L3', 'L4') else l['r']+l['cryostat_minor_m']+g['cage_clearance_m']
        for j in range(3):
            az = 120*j+7.5
            out.append(P(f'VTX_{l["name"]}_Metrology_Head_{j+1}', 'INSTRUMENTATION', 'box', 'sensor', note='Laser-tracker metrology head (loop position and tilt)',
                         center=pol(ve.hoop_x(l)+0.05, R0+0.42, az), size=(0.3, 0.3, 0.3), az=az))
            out[-1]['group'] = 'L4' if l['name'] == 'L4' else 'STATIC'
    # service-petal hinge blocks on the L1/L2 joint flanges (fixed)
    for name in ('L1', 'L2'):
        l = loops[name]; clock = 22.5*LOOPS.index(name)
        for j in range(g['segments_per_loop']):
            az = clock+360*j/g['segments_per_loop']
            out.append(P(f'VTX_{name}_Petal_Guide_{j+1}', 'MAGNETIC_NOZZLE', 'box', 'structure', note=f'{name} service-petal guide on joint flange {j+1} (shell withdraws outward on it)',
                         center=pol(l['x'], l['r']+l['cryostat_minor_m']+0.32, az), size=(0.22, 0.5, 0.3), az=az))
            out[-1]['group'] = 'STATIC'
    return out


def metrology_beams(s, R):
    """Effect: laser lines from every metrology head to the next loop's head on the same azimuth (shown in state 3 only)."""
    g = ve.config(s)['geometry']; st = ve.stations(s); rail_R = R['carriages']['rail']['radius_m']; pol = ve.pol
    pts = []
    for l in st['loops']:
        R0 = rail_R if l['name'] in ('L3', 'L4') else l['r']+l['cryostat_minor_m']+g['cage_clearance_m']
        pts.append([pol(ve.hoop_x(l)+0.05, R0+0.42, 120*j+7.5) for j in range(3)])
    beams = [(pts[i][j], pts[i+1][j]) for i in range(len(pts)-1) for j in range(3)]
    return ve.part('FX_METROLOGY', 'VISUAL_EFFECTS', 'beams', 'field', note='Metrology laser lines (alignment state only)', beams=beams, radius=0.025)


def flywheel(s):
    """Optional shared ignition flywheel at the cluster hub (ship frame). 58 t nominal for the cluster (1.7); OPTIONAL (owner 2026-11-16)."""
    k = vc.stations(s); x = (k['hub_fwd']+k['hub_aft'])/2
    return [ve.part('CL_Ignition_Flywheel_Housing', 'STRUCTURE', 'revolve', 'structure', note='OPTIONAL ignition flywheel containment (58 t class for the cluster; mass and energy OPEN)',
                    profile=[(x+1.0, 0.6), (x+1.0, 2.6), (x-1.0, 2.6), (x-1.0, 0.6)], closed=True, n=40),
            dict(ve.part('CL_Ignition_Flywheel_Rotor', 'STRUCTURE', 'disc', 'coil', note='OPTIONAL flywheel rotor (spins up in state 2, discharges in state 6)',
                         center=(x+1.08, 0.0, 0.0), radius=2.3, depth=0.1, n=40), origin=(x+1.08, 0.0, 0.0), group='FLYWHEEL')]


def petal_motion(s, group):
    """Withdrawal vectors (engine frame) of a petal's shell (radially out) and armour (toward the burn point)."""
    _, L, j = group.split('_'); j = int(j); g = ve.config(s)['geometry']; st = ve.stations(s)
    l = next(x for x in st['loops'] if x['name'] == L); clock = 22.5*LOOPS.index(L)
    m = math.radians(clock+360*(j-1)/g['segments_per_loop']+180/g['segments_per_loop'])
    phi = math.atan2(l['r'], l['x']-st['burn'])
    shell = (0.0, PROTO['petal_lift_m']*math.cos(m), PROTO['petal_lift_m']*math.sin(m))
    w = PROTO['armour_withdraw_m']
    armour = (-w*math.cos(phi), -w*math.sin(phi)*math.cos(m), -w*math.sin(phi)*math.sin(m))
    return shell, armour



SHOTS = {   # state: ((camera from, target) at the start, (camera from, target) at the end), engine frame of N1 (+Y radial out) unless 'C'
    'DORMANT': (((0.0, 36.0, 14.0), (-18.0, 4.0, 0.0)), ((-3.0, 33.0, 10.0), (-18.0, 4.0, 0.0))),
    'MECHANICAL_PREPARATION': (((-22.0, 48.0, 8.0), (-23.0, 0.0, 0.0)), ((-24.0, 47.0, 4.0), (-24.0, 0.0, 0.0))),
    'DIGITAL_ALIGNMENT': (((-14.0, 30.0, 16.0), (-26.0, 5.0, 2.0)), ((-16.0, 31.0, 12.0), (-27.0, 5.0, 2.0))),
    'FIELD_FORMATION': (((-25.5, 7.0, 18.5), (-32.4, 0.0, 10.8)), ((-26.5, 8.0, 17.0), (-32.4, 0.0, 10.8))),
    'PLASMA_CALIBRATION': (('C', (-190.0, -100.0, 42.0), (-170.0, 0.0, 0.0)), ('C', (-186.0, -92.0, 36.0), (-170.0, 0.0, 0.0))),
    'FIRST_IGNITION': (('C', (-205.0, -85.0, 24.0), (-175.0, 0.0, 0.0)), ('C', (-200.0, -80.0, 22.0), (-175.0, 0.0, 0.0))),
    'VERTEX_LOCK': (('C', (-150.0, -75.0, 62.0), (-160.0, 0.0, 0.0)), ('C', (-152.0, -70.0, 58.0), (-160.0, 0.0, 0.0))),
    'SUSTAINED_MODULATION': (('C', (-330.0, -230.0, 60.0), (-205.0, 0.0, 0.0)), ('C', (-300.0, -210.0, 95.0), (-205.0, 0.0, 0.0))),
    'SHUTDOWN_OR_FAILURE': (((-22.0, 48.0, 8.0), (-23.0, 0.0, 0.0)), ((-24.0, 47.0, 4.0), (-24.0, 0.0, 0.0))),
}

# ---------- the nine states -------------------------------------------------------------------------------------------------------------

def timeline(s, R):
    """Nine states with physical and playback durations, control values at the start and end of each, and derived diagnostics."""
    SEQ = R['sequence']['states']; DY = json.loads(vad.vd.EVIDENCE_PATH.read_text())
    AL = R['alignment']; CA = R['carriages']; F = R['audit']['field']
    worst = next(r for r in AL['rows'] if r['name'] == AL['worst'])
    slope = worst['tilt_rad'][0]/AL['offsets_m'][0]                      # rad per metre of offset (first order, 1.8)
    thrust = AL['thrust_N']; stored = F['stored_J']; charge_h = DY['dynamo']['dynamo_charge'][0]['hours']
    lead_W = DY['dynamo']['leads'][1]['radiator_W']
    neutral = {**dm.neutral(s), 'plasma_visibility': 1.0, **{f'flux_share_{j}': 0.25 for j in range(1, 5)}}
    proposed = dict(nozzle_deployment=0.0, field_ring_trim=0.0, induction_rotor_speed=0.0, service_petals=0.0, ai_optimization_state=0.0,
                    plasma_stability=0.0, thermal_load=0.0, vertex_lock=0.0, fault_code=0.0)
    # end-of-state control values (start = previous end); keys from 1.8 sequence plus the review's explicit poses
    ends = {
        'DORMANT': dict(),
        'MECHANICAL_PREPARATION': dict(nozzle_deployment=1.0, induction_rotor_speed=1.0),
        'DIGITAL_ALIGNMENT': dict(field_ring_trim=1.0, ai_optimization_state=0.4),
        'FIELD_FORMATION': dict(manifold_field_strength=1.0, induction_rotor_speed=0.0, lattice_activation=0.6),
        'PLASMA_CALIBRATION': dict(drive_active=0.2, laser_A_power=0.3, laser_B_power=0.3, nozzle_field_strength=0.3, plasma_stability=0.5, ai_optimization_state=0.7),
        'FIRST_IGNITION': dict(drive_active=0.5, laser_A_power=0.5, laser_B_power=0.5, lattice_activation=1.0, nozzle_field_strength=0.6, plasma_stability=0.8),
        'VERTEX_LOCK': dict(vertex_lock=1.0, plasma_stability=1.0, ai_optimization_state=1.0, drive_active=1.0, nozzle_field_strength=1.0),
        'SUSTAINED_MODULATION': dict(thrust_level=1.0, thermal_load=1.0),
        'SHUTDOWN_OR_FAILURE': dict(drive_active=0.0, laser_A_power=0.0, laser_B_power=0.0, nozzle_field_strength=0.0, manifold_field_strength=0.0,
                                    lattice_activation=0.0, induction_rotor_speed=0.0, nozzle_deployment=0.0, field_ring_trim=0.0, vertex_lock=0.0,
                                    plasma_stability=0.0, ai_optimization_state=0.0, thermal_load=0.0, thrust_level=0.0),
    }
    v = {**neutral, **proposed}; t_play = 0.0; t_phys = 0.0; states = []
    for st in SEQ:
        name = st['state']; start = dict(v); v = {**v, **ends[name]}
        phys = st['duration_s'] if st['duration_s'] else DORMANT_SHOW_S
        states.append(dict(n=st['n'], state=name, maps_to=st['maps_to'], description=st['description'], physical_s=phys,
                           physical_label=_dur(st['duration_s'])+(' at 1 V (307 h at 0.1 V)' if name == 'FIELD_FORMATION' else ''), play_s=PLAY_S[name], play_t0=t_play, phys_t0=t_phys, start=start, end=dict(v)))
        t_play += PLAY_S[name]; t_phys += phys
    # keyframe curves inside a state: (fraction of state -> fraction of the start->end change); default linear
    shapes = dict(MECHANICAL_PREPARATION=dict(induction_rotor_speed=(0.6, 1.0)), DIGITAL_ALIGNMENT=dict(field_ring_trim='exp'),
                  FIELD_FORMATION=dict(induction_rotor_speed=(0.92, 1.0)), SHUTDOWN_OR_FAILURE=dict(nozzle_deployment=(0.55, 1.0), induction_rotor_speed=(0.0, 0.0)))
    # dormant service inspection: petals open then close inside the dormant state; the rotors run backwards to discharge in shutdown
    events = [dict(state='DORMANT', prop='service_petals', keys=[(0.15, 0.0), (0.4, 1.0), (0.65, 1.0), (0.9, 0.0)]),
              dict(state='SHUTDOWN_OR_FAILURE', prop='induction_rotor_speed', keys=[(0.0, 0.0), (0.08, -1.0), (0.45, -1.0), (0.55, 0.0)]),
              dict(state='FIELD_FORMATION', prop='induction_rotor_speed', keys=[(0.0, 1.0), (0.9, 1.0), (0.97, 0.0)])]
    diag = dict(stored_J=stored, charge_h_1V=charge_h, lead_heat_avoided_W=lead_W, thrust_engine_N=thrust/4 if thrust > 6e6 else thrust,
                alignment=dict(loop=AL['worst'], survey_m=AL['offsets_m'][0], fine_m=AL['offsets_m'][-1], tilt_per_m=slope),
                stroke_m=CA['stow_stroke_m']['L4'], stop_field_T=F['stop_field_T'])
    return dict(states=states, shapes=shapes, events=events, diagnostics=diag, play_total_s=t_play, physical_total_s=t_phys,
                flywheel=PROTO['flywheel'], proto=PROTO)


def _dur(sec):
    if not sec:
        return 'indefinite'
    if sec >= 100*3600:
        return f'{sec/86400:.0f} days'
    if sec >= 3600:
        return f'{sec/3600:.1f} h'
    if sec >= 60:
        return f'{sec/60:.0f} min'
    return f'{sec:.0f} s'


def value_at(T, state, prop, u):
    """Control value of prop at fraction u in [0,1] of state."""
    for e in T['events']:
        if e['state'] == state['state'] and e['prop'] == prop:
            ks = e['keys']
            if u <= ks[0][0]:
                return ks[0][1]
            for (u0, a), (u1, b) in zip(ks, ks[1:]):
                if u <= u1:
                    return a+(b-a)*(u-u0)/(u1-u0)
            return ks[-1][1]
    a = state['start'].get(prop, 0.0); b = state['end'].get(prop, 0.0)
    sh = T['shapes'].get(state['state'], {}).get(prop)
    if sh == 'exp':
        f = 1.0-math.exp(-5*u)/1.0 if u < 1 else 1.0
        f = (1-math.exp(-5*u))/(1-math.exp(-5))
    elif isinstance(sh, tuple):
        u0, u1 = sh
        f = 0.0 if u <= u0 else (1.0 if u >= u1 or u1 == u0 else (u-u0)/(u1-u0))
    else:
        f = u
    f = 0.5-0.5*math.cos(math.pi*f) if sh != 'exp' else f
    return a+(b-a)*f


def diagnostics_at(T, state, u, v):
    """Readouts derived from the shared engineering parameters at fraction u of the state (physical clock, not playback)."""
    D = T['diagnostics']; name = state['state']; phys = state['phys_t0']+u*state['physical_s']
    al = D['alignment']
    if name == 'DIGITAL_ALIGNMENT':
        off = al['fine_m']+(al['survey_m']-al['fine_m'])*math.exp(-5*u*1.0)*(1-u)+0.0
    elif state['n'] < 3:
        off = al['survey_m']
    elif name == 'SHUTDOWN_OR_FAILURE' and u > 0.55:
        off = al['survey_m']
    else:
        off = al['fine_m']
    field = v.get('manifold_field_strength', 0.0)
    return dict(clock_s=phys, l4_position_m=-(1-v['nozzle_deployment'])*D['stroke_m'], alignment_offset_mm=off*1e3,
                field_tilt_mrad=off*al['tilt_per_m']*1e3, side_force_kN=off*al['tilt_per_m']*D['thrust_engine_N']/1e3,
                field_fraction=field, stop_field_T=field*D['stop_field_T'], stored_energy_GJ=field**2*D['stored_J']/1e9,
                thrust_MN=v.get('drive_active', 0.0)*min(1.0, v.get('nozzle_field_strength', 0.0))*D['thrust_engine_N']/1e6,
                lead_heat_avoided_MW=D['lead_heat_avoided_W']/1e6, rotor=v.get('induction_rotor_speed', 0.0))


def pose(T, v, gain=1.0):
    """Rigid transforms (engine frame) of the moving groups for control values v: translation (dx, dy, dz) and rotation about the group's
    own axis. L4 translates along +X (forward) when stowed; trim residual is a small lateral offset (x gain for the alignment view)."""
    D = T['diagnostics']; al = D['alignment']
    stow = D['stroke_m']*(1-v['nozzle_deployment'])
    resid = al['fine_m']+(al['survey_m']-al['fine_m'])*(1-v['field_ring_trim'])
    out = {'L4': dict(t=(stow, resid*gain*0.7071, resid*gain*0.7071), r=0.0)}
    p = v['service_petals']
    for L in ('L1', 'L2'):
        for j in range(1, 9):
            out[f'PETAL_{L}_{j}'] = dict(open=p)
    return out


def sample(s, R, T, fps=None):
    """Playback samples: per frame the state, control values and diagnostics (the browser review interpolates these)."""
    fps = fps or PROTO['fps']; rows = []
    keys = list(T['states'][0]['start'])
    for st in T['states']:
        n = int(round(st['play_s']*fps))
        for i in range(n):
            u = i/n; v = {k: value_at(T, st, k, u) for k in keys}
            rows.append(dict(state=st['n'], u=round(u, 4), v={k: round(x, 4) for k, x in v.items()}, d={k: round(x, 6) for k, x in diagnostics_at(T, st, u, v).items()}))
    return rows


def effects_at(s, v):
    """Effect opacities and plume scale from the existing display rig (vertex_cluster.display) for control values v."""
    d = vc.display(s, {k: v[k] for k in v if k in dm.PROPS or k in dm.SAVED_SETTINGS})
    return {o: round(x, 4) for (o, path, i), x in d.items() if path == 'color'}, {o: round(x, 4) for (o, path, i), x in d.items() if path == 'scale' and i == 0}


def write(s, R):
    T = timeline(s, R); rows = sample(s, R, T, fps=6)
    fx = []
    for r in rows:
        op, sc = effects_at(s, r['v'])
        fx.append(dict(o={k.split('_', 1)[1]: x for k, x in op.items() if k.startswith('N1_')}, s={k.split('_', 1)[1]: x for k, x in sc.items() if k.startswith('N1_')}))
    FL = R['field_lines']
    doc = dict(version='1.8F-proto', status='PROTOTYPE review (not canon)', timeline={k: v for k, v in T.items() if k not in ('shapes',)},
               fps=6, samples=rows, effects=fx, field_lines=FL, flywheel_optional=True,
               open=['capture and detachment (the plume response to the field)', 'source radiation (neutrons, X-rays, charged leakage)',
                     'driver power and target gain', 'coil survival under the burn', 'mass closure', 'thermal closure'])
    OUT.write_text(json.dumps(doc, separators=(',', ':')))
    return doc


if __name__ == '__main__':
    s, R = load()
    P = parts_aplus(s, R)
    from collections import Counter
    print('parts', len(P), Counter(p['group'].split('_')[0] for p in P))
    doc = write(s, R)
    T = doc['timeline']
    for st in T['states']:
        print(f"{st['n']} {st['state']:<24} phys {st['physical_label']:>10}  play {st['play_s']:4.1f} s")
    print('play total', T['play_total_s'], 's; samples', len(doc['samples']), '; bytes', OUT.stat().st_size)
