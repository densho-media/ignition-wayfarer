"""P1-008 rotor-interface mechanisms: sourced architecture, PROTOTYPE hub proxies, service paths, states and checks.

Canon (drive_capture_2026-09-29; S&E 16_SPACE_MECHANISMS rows MEC-001..015, 15_MODEL_INTERFACES I5/S6, OD-002/OD-013):
active magnetic primary support with serviceable dry/solid-lubricated touchdown cartridges, a direct electromagnetic hub
motor, contactless inductive power plus data with a low-power emergency path, only essential fluids through a modular
redundant rotary coupling with leak detection and isolation, independent mechanical ring-stop locks that carry the
high-thrust load and bypass the actuators (MEC-011), and continuously monitored health channels. Owner row IDs MEC-0xx are S&E 16_SPACE_MECHANISMS rows.

Nothing here sizes a bearing, a motor, a coupler, a loss or a spin-down: those stay known = false. The one derived number is
the ring-equivalent kinetic energy a full spin-down must remove. Radii, gaps, stack order, segment angles and action timing
come from the PROTOTYPE [rotor_interface] table. Coordinates: x along +X; u = x - rotor centre; angles about +X from +Y.

Standard library only; imported by spec, the Blender recipes, the rig contract, inspect and tests.
"""
from pathlib import Path
import json
import math
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import habitat_ring
import layout
import hull_geometry
import power_storage

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT/'references/p1_rotor_interface.json'
SUBSYSTEM = 'WF_ROTOR_INTERFACE.blend'
FUNCTIONS = {'TOUCHDOWN_BEARING': 2, 'MAGNETIC_BEARING': 2, 'HUB_MOTOR': 1, 'CONTACTLESS_POWER': 1, 'CONTACTLESS_DATA': 1, 'EMERGENCY_POWER_PATH': 1}
ACTIONS = ('WF_RING_STOP_LOCK', 'WF_ROTOR_TOUCHDOWN', 'WF_VESTIBULE_SEAL_FAULT')
# Sourced architecture record behind each proxy function (all WORKING rows of 16_SPACE_MECHANISMS / 15_MODEL_INTERFACES I5).
SOURCES = {'MAGNETIC_BEARING': 'rotor_magnetic_bearings', 'TOUCHDOWN_BEARING': 'rotor_touchdown_bearings', 'HUB_MOTOR': 'rotor_hub_motor',
           'CONTACTLESS_POWER': 'rotor_power_data_transfer', 'CONTACTLESS_DATA': 'rotor_power_data_transfer', 'EMERGENCY_POWER_PATH': 'rotor_power_data_transfer',
           'FLUID_COUPLING': 'rotor_fluid_transfer', 'HUB_DRUM': 'rotor_interface_i5', 'FLUID_MOUNT': 'rotor_fluid_transfer', 'RING_STOP_LOCK': 'ring_stop_lock'}
AROUND = 48  # facets of a full ring; partial segments use proportionally fewer

# Display flags on ROTOR_n_MECH_CTRL (one per rotor; the vehicle saves the preset named by [vehicle].saved_preset and a preset
# poses them in memory). spin_fraction is keyed LINEAR and drives the ring rotation through the Rotor_n driver; the other
# channels are 0/1 states keyed CONSTANT.
PROPS = {
    'levitation_active': 'Active magnetic bearings carry the rotor (normal support, MEC-002).',
    'touchdown_contact': 'Rotor rests or runs on the touchdown cartridges: startup, shutdown, overload or failure only (MEC-003).',
    'motor_driving': 'Hub motor drives or holds speed against the losses, which are OPEN and never zero (MEC-004/010).',
    'motor_braking': 'Hub motor brakes the rotor in a controlled regenerative spin-down.',
    'spin_fraction': 'Ring speed as a fraction of the sourced 4 rpm; the Rotor_n rotation driver multiplies the nominal rate by it in a preset, and integrates it (spin_turned) in the actions and the flight timeline (PROTOTYPE display).',
    'index_lock_engaged': 'Passive/mechanical hub lock engaged at the index angle before high thrust (MEC-004).',
    'ring_locks_engaged': 'Ring-stop locks carry the high-thrust axial load to the spine; actuators are not in the load path (MEC-011).',
    'health_alarm': 'A mechanism health channel reports a fault (MEC-015).',
    'inspection_required': 'A touchdown at speed or a vestibule seal fault occurred: inspect before full-speed or rotating-transfer service (MEC-003, MEC-015).',
    'vestibule_isolated': 'The rotary vestibule is isolated by its hatches after a seal fault (12!A11, habitat.transfer.seal_fault_action); a controlled ring stop follows.',
}
ROTATING = {'levitation_active': 1.0, 'touchdown_contact': 0.0, 'motor_driving': 1.0, 'motor_braking': 0.0, 'spin_fraction': 1.0,
            'index_lock_engaged': 0.0, 'ring_locks_engaged': 0.0, 'health_alarm': 0.0, 'inspection_required': 0.0, 'vestibule_isolated': 0.0}
# Stopped and locked: stopped, set down on the touchdown cartridges at zero speed, index lock and ring-stop locks engaged.
STOPPED_LOCKED = {**ROTATING, 'levitation_active': 0.0, 'touchdown_contact': 1.0, 'motor_driving': 0.0, 'spin_fraction': 0.0,
                  'index_lock_engaged': 1.0, 'ring_locks_engaged': 1.0}
SAVED = {'ROTATING': ROTATING, 'STOPPED_LOCKED': STOPPED_LOCKED}
# FUT-007 integrated rotation, also on ROTOR_n_MECH_CTRL but not display states: the Rotor_n driver turns the ring by spin_turned
# (spin_turned()) while spin_integrated is 1, and by the product spin_fraction x (frame - 1) while it is 0, as every saved preset is.
TURN_PROPS = {'spin_turned': 'Ring turn since the start, in frames at full speed (the integral of spin_fraction, spin_turned()); keyed LINEAR by actions and the flight timeline.',
              'spin_integrated': '1: the Rotor_n driver turns the ring by spin_turned, so a spin ramp slows it to rest at its index angle without reversing; 0 (saved, presets): spin_fraction x (frame - 1).'}
STATES = tuple(SAVED)


def radial(x, r, a):
    return (x, r*math.cos(a), r*math.sin(a))


def buildable_names(s):
    return [name for name, cfg in s['configuration'].items() if cfg['buildable']]


def control(j):
    return f'ROTOR_{j}_MECH_CTRL'


def configuration_state(s, name):
    """Mechanism control values of a buildable preset: its habitat state's saved flags, with the spin and lock channels taken from the
    preset's controls (ring_spin, ring_lock)."""
    cfg = s['configuration'][name]
    return {**SAVED[cfg['habitat']], 'spin_fraction': float(cfg['controls']['ring_spin']), 'ring_locks_engaged': float(cfg['controls']['ring_lock']),
            'index_lock_engaged': float(cfg['controls']['ring_lock'])}


def retracted_lock_outer_radius_max(s):
    """Largest outer radius of a retracted ring-stop lock pin (and the hub index-lock pin) that stays inside the vestibule-strut
    sweep: drum mid radius - strut radius - mechanical clearance."""
    ri = s['rotor_interface']
    return (ri['drum_inner_radius_m']+ri['drum_outer_radius_m'])/2-s['crew_transfer']['strut_radius_m']-s['prototype']['mechanical_clearance_m']


# ---------- PROTOTYPE geometry ------------------------------------------------------------------------------------

def solid(x0, x1, r0, r1, t0, t1):
    """Closed ring or ring segment between radii r0..r1, x0..x1, angles t0..t1. Full rings wrap; segments get end caps."""
    full = math.isclose(t1-t0, math.tau)
    n = AROUND if full else max(2, math.ceil(AROUND*(t1-t0)/math.tau))
    m = n if full else n+1
    ts = [t0+(t1-t0)*k/n for k in range(m)]
    # Vertex blocks: (x0, r0), (x0, r1), (x1, r1), (x1, r0), each with m angles.
    corners = [(x0, r0), (x0, r1), (x1, r1), (x1, r0)]
    vertices = [radial(x, r, t) for x, r in corners for t in ts]
    faces = []
    for b in range(4):
        c = (b+1) % 4
        for k in range(n):
            k1 = (k+1) % m
            faces.append((b*m+k, b*m+k1, c*m+k1, c*m+k))
    if not full:
        for k in (0, m-1):
            faces.append(tuple(b*m+k for b in range(4)) if k else tuple(b*m+k for b in reversed(range(4))))
    return vertices, faces


def rotors(s):
    """Per rotor plane: centre x, phase, the three ring-lock (crew-spoke) angles and the segment centre angles (world frame)."""
    p, ri = s['prototype'], s['rotor_interface']; n = ri['segment_count']; out = []
    for j, x in enumerate(habitat_ring.centers(s), 1):
        phase = math.radians(p['rotor_phase_deg'][j-1])
        locks = habitat_ring.lock_angles(s, j)
        segments = [phase+math.radians(ri['segment_offset_deg'])+k*math.tau/n for k in range(n)]
        out.append(dict(index=j, x=x, phase=phase, lock_angles=locks, segment_angles=segments))
    return out


def stationary(s):
    """Stationary hub modules (segments), the fluid-coupling cartridge and its spokes, in the vehicle frame."""
    ri = s['rotor_interface']; h = math.radians(ri['segment_half_span_deg']); out = []
    for rot in rotors(s):
        j, x = rot['index'], rot['x']
        for m in ri['modules']:
            r1 = ri['touchdown_outer_radius_m'] if m['function'] == 'TOUCHDOWN_BEARING' else ri['stator_outer_radius_m']
            angles = rot['segment_angles'][:m.get('segments', ri['segment_count'])]
            for k, c in enumerate(angles, 1):
                vs, fs = solid(x+m['u0_m'], x+m['u1_m'], ri['stationary_inner_radius_m'], r1, c-h, c+h)
                out.append(dict(name=f"Hub{j}_{m['id']}_S{k}", rotor=j, module=m['id'], function=m['function'], kind='rotor_mechanism',
                                x0=x+m['u0_m'], x1=x+m['u1_m'], r0=ri['stationary_inner_radius_m'], r1=r1, sector=(c-h, c+h),
                                withdraw=m['withdraw'], vertices=vs, faces=fs, ident=f"WF.HUB.{j}.{m['id']}.S{k}"))
        f = ri['fluid_coupling']; u0, u1 = f['stator_u_m']
        vs, fs = solid(x+u0, x+u1, ri['drum_inner_radius_m'], ri['drum_outer_radius_m'], 0.0, math.tau)
        out.append(dict(name=f'Hub{j}_FLUID_COUPLING_Stator', rotor=j, module='FLUID_COUPLING', function='FLUID_COUPLING', kind='rotor_mechanism',
                        x0=x+u0, x1=x+u1, r0=ri['drum_inner_radius_m'], r1=ri['drum_outer_radius_m'], sector=None, withdraw='FWD',
                        vertices=vs, faces=fs, ident=f'WF.HUB.{j}.FLUID_COUPLING'))
    return out


def spokes(s):
    """Fluid-cartridge mounts: radial rods from the spine to the cartridge bore at the lock angles."""
    ri = s['rotor_interface']; f = ri['fluid_coupling']; out = []
    for rot in rotors(s):
        for k, a in enumerate(rot['lock_angles'], 1):
            xx = rot['x']+f['spoke_u_m']
            out.append(dict(name=f"Hub{rot['index']}_FLUID_Spoke_{k}", rotor=rot['index'], angle=a, x=xx, radius=f['spoke_radius_m'],
                            a=radial(xx, ri['stationary_inner_radius_m'], a), b=radial(xx, ri['drum_inner_radius_m'], a)))
    return out


def rotating(s):
    """Rotating hub parts in each rotor's local frame (origin on the rotor centre): drum, one ring per module, fluid face."""
    ri = s['rotor_interface']; out = []
    for rot in rotors(s):
        j = rot['index']
        def ring(name, function, u0, u1, r0, r1, kind='rotor_mechanism'):
            vs, fs = solid(u0, u1, r0, r1, 0.0, math.tau)
            out.append(dict(name=name, rotor=j, function=function, kind=kind, u0=u0, u1=u1, r0=r0, r1=r1, vertices=vs, faces=fs, ident=f'WF.HUB.{j}.{name.split("_", 1)[1]}'))
        ring(f'Hub{j}_Drum', 'HUB_DRUM', *ri['drum_u_m'], ri['drum_inner_radius_m'], ri['drum_outer_radius_m'], kind='rotor_hub_drum')
        for m in ri['modules']:
            ring(f"Hub{j}_{m['id']}_Rotor", m['function'], m['u0_m'], m['u1_m'], ri['rotating_inner_radius_m'], ri['rotating_ring_outer_radius_m'])
        ring(f'Hub{j}_FLUID_COUPLING_Rotor', 'FLUID_COUPLING', *ri['fluid_coupling']['rotor_u_m'], ri['drum_inner_radius_m'], ri['drum_outer_radius_m'])
    return out


def ring_stop_locks(s):
    """Retracted ring-stop lock pins (PROTOTYPE, MEC-011 geometry OPEN): stationary radial rods with flat ends on the spine side at
    each crew-spoke angle, from the stationary inner radius to ring_lock_pin_outer_radius_m. The rotating strike fittings are not modelled."""
    ri = s['rotor_interface']; out = []
    for rot in rotors(s):
        xx = rot['x']+ri['ring_lock_u_m']
        for k, a in enumerate(rot['lock_angles'], 1):
            out.append(dict(name=f"Ring_Stop_Lock_{rot['index']}_{k}", rotor=rot['index'], angle=a, x=xx, radius=ri['ring_lock_radius_m'],
                            a=radial(xx, ri['stationary_inner_radius_m'], a), b=radial(xx, ri['ring_lock_pin_outer_radius_m'], a),
                            drive=f"IF_RING_STOP_LOCK_{rot['index']}_{k}_DRIVE"))
    return out


def interfaces(s):
    """Stationary interfaces (WF_ROTOR_INTERFACE) and rotating ones (habitat files, rotor-local). All engineering is OPEN."""
    ri = s['rotor_interface']; mid = (ri['stationary_inner_radius_m']+ri['stator_outer_radius_m'])/2; out = []
    for rot in rotors(s):
        j, x, a = rot['index'], rot['x'], rot['segment_angles'][0]
        add = lambda name, at, status, **kw: out.append(dict(name=name, rotor=j, at=at, status=status, side=kw.pop('side', 'STATIONARY'), **kw))
        for m in ri['modules']:
            status = {'MAGNETIC_BEARING': 'OPEN OD-013/MEC-010: station count, gap, stiffness, bandwidth, controller power and losses not designed',
                      'TOUCHDOWN_BEARING': 'OPEN OD-013: cartridge rating, clearance, impact/whirl and emergency thermal case not designed; material candidates only (MEC-008)',
                      'HUB_MOTOR': 'OPEN MEC-004: motor topology, torque and gearing not designed; must tolerate loss of one control channel',
                      'CONTACTLESS_POWER': 'OPEN MEC-005/S5: inductive coupler rating, redundancy split and EMI/EMC not designed',
                      'CONTACTLESS_DATA': 'OPEN MEC-005: optical/magnetic/capacitive data link not selected; redundant channels required',
                      'EMERGENCY_POWER_PATH': 'OPEN MEC-005: low-power emergency path; source and rating not sourced; not wired to the survival reserve'}[m['function']]
            add(f"IF_HUB{j}_{m['id']}", radial(x+(m['u0_m']+m['u1_m'])/2, mid, a), status, module=m['id'])
        # The primary feed lands on the rotor-transfer point, where the P1-007 ride-through marker bridges it (checked).
        add(f'IF_HUB{j}_POWER_FEED', (x, 0.0, 0.0), 'OPEN S5: A/B ship-bus feed to the inductive primary via device-level ride-through; route and switching not designed',
            pairs_with=[('WF_POWER_STORAGE.blend', f'IF_RIDE_THROUGH_ROTOR_TRANSFER_{j}'), ('WF_STRUCTURE.blend', f'IF_ROTOR_TRANSFER_{j}')])
        f = ri['fluid_coupling']
        add(f'IF_HUB{j}_FLUID_STATIONARY', radial(x+f['stator_u_m'][1], (ri['drum_inner_radius_m']+ri['drum_outer_radius_m'])/2, a),
            'OPEN OD-002: stationary isolation valve and leak detection; circuit count, media and coupling size not designed')
        add(f'IF_HUB{j}_INDEX_LOCK', radial(x+ri['drum_u_m'][0]-ri['withdraw_margin_m'], (ri['drum_inner_radius_m']+ri['drum_outer_radius_m'])/2, a),
            'OPEN MEC-004: passive/mechanical hub index lock before high thrust; pin, drive and load rating not designed')
        add(f'IF_HUB{j}_HEALTH', radial(x+ri['drum_u_m'][0], mid, a), 'OPEN MEC-015: health channels (gap, vibration, temperature, torque, seal leakage, lubricant, touchdown events); sensors and thresholds not designed',
            channels=list(s['habitat']['transfer']['health_channels']['channels']))
        for end, u in (('AFT', ri['drum_u_m'][0]), ('FWD', f['stator_u_m'][1])):
            add(f'IF_HUB{j}_SERVICE_{end}', radial(x+u, mid if end == 'AFT' else (ri['drum_inner_radius_m']+ri['drum_outer_radius_m'])/2, a),
                'OPEN P1-001/MEC-007: cartridge withdrawal exit; crew access route, tooling and isolation points not designed')
        # Rotating side (rotor-local frame): power/data landing on the rotor bus and the rotating fluid isolation.
        coupler = next(m for m in ri['modules'] if m['function'] == 'CONTACTLESS_POWER')
        add(f'IF_HUB{j}_ROTOR_BUS', radial((coupler['u0_m']+coupler['u1_m'])/2, ri['drum_outer_radius_m'], 0.0),
            'OPEN MEC-005: rotating-side power/data landing on the rotor bus; rotor bus and loads not designed', side='ROTATING')
        add(f'IF_HUB{j}_FLUID_ROTATING', radial(f['rotor_u_m'][0], ri['drum_outer_radius_m'], 0.0),
            'OPEN MEC-006: rotating-side isolation valve, bypass and local reserve; circuits not designed', side='ROTATING')
    return out


# ---------- screens -----------------------------------------------------------------------------------------------

def angular_gap(sector, angle, r, radius):
    """Lateral gap between a segment spanning `sector` (rad) at radius >= r and a radial rod of `radius` at `angle`."""
    if sector is None:
        return -math.inf
    lo, hi = sector; c = (lo+hi)/2; d = abs((angle-c+math.pi) % math.tau-math.pi)-(hi-lo)/2
    return -math.inf if d <= 0 else (r*math.sin(d) if d < math.pi/2 else r)-radius


def withdrawal_span(s, x, x0, x1, direction, coupling=False):
    """Axial withdrawal path (vehicle X) of a cartridge spanning x0..x1 on the rotor centred at x: its own length plus withdraw_margin_m beyond
    the drum end it leaves by; the fluid-coupling cartridge from its own forward face."""
    ri = s['rotor_interface']; length = x1-x0; margin = ri['withdraw_margin_m']; d0, d1 = ri['drum_u_m']
    if coupling:
        return (x1, x1+length+margin)
    return (x+d0-length-margin, x0) if direction == 'AFT' else (x1, x+d1+length+margin)


def withdrawal_extent(s, j):
    """Vehicle-X extent of all of rotor j's withdrawal paths, from the module table (withdrawal() without building the parts)."""
    ri = s['rotor_interface']; x = next(r['x'] for r in rotors(s) if r['index'] == j); u0, u1 = ri['fluid_coupling']['stator_u_m']
    spans = [withdrawal_span(s, x, x+m['u0_m'], x+m['u1_m'], m['withdraw']) for m in ri['modules']]+[withdrawal_span(s, x, x+u0, x+u1, 'FWD', True)]
    return min(a for a, _ in spans), max(b for _, b in spans)


def withdrawal(s):
    """Axial withdrawal path of every stationary cartridge in both habitat states: fixed obstacles (must be none) and the
    removable cartridges that must come out first."""
    p, ri = s['prototype'], s['rotor_interface']; clr = p['mechanical_clearance_m']
    parts = stationary(s); fixed = []
    for sp in spokes(s):
        fixed.append(dict(name=sp['name'], x0=sp['x']-sp['radius'], x1=sp['x']+sp['radius'], r0=ri['stationary_inner_radius_m'], r1=ri['drum_inner_radius_m'], angle=sp['angle'], radius=sp['radius'], states=set(STATES)))
    for lk in ring_stop_locks(s):
        fixed.append(dict(name=lk['name'], x0=lk['x']-lk['radius'], x1=lk['x']+lk['radius'], r0=ri['stationary_inner_radius_m'], r1=ri['ring_lock_pin_outer_radius_m'], angle=lk['angle'], radius=lk['radius'], states=set(STATES)))
    ref = hull_geometry.refuge(s)
    fixed.append(dict(name='Refuge_Storm_Shelter', x0=ref['x0'], x1=ref['x1'], r0=0.0, r1=ref['outer'], angle=None, radius=0.0, states=set(STATES)))
    fixed.append(dict(name='Forward_Mount_Struts', x0=layout.at(s, p['forward_mount_aft_x']), x1=layout.at(s, p['forward_mount_fwd_x']), r0=p['forward_mount_inner_radius_m']-p['structural_strut_radius_m'], r1=p['forward_mount_outer_radius_m'], angle=None, radius=0.0, states=set(STATES)))
    for q in rotating(s):
        x = next(r['x'] for r in rotors(s) if r['index'] == q['rotor'])
        fixed.append(dict(name=q['name'], rotor=q['rotor'], x0=x+q['u0'], x1=x+q['u1'], r0=q['r0'], r1=q['r1'], angle=None, radius=0.0, states=set(STATES)))
    centre = {r['index']: r['x'] for r in rotors(s)}
    rows = {}
    for m in parts:
        span = withdrawal_span(s, centre[m['rotor']], m['x0'], m['x1'], m['withdraw'], m['module'] == 'FLUID_COUPLING')
        def blocks(o):
            if o['x1'] <= span[0] or o['x0'] >= span[1] or o['r1'] <= m['r0'] or o['r0'] >= m['r1']:
                return False
            return o['angle'] is None or angular_gap(m['sector'], o['angle'], m['r0'], o['radius']) < clr
        # Own rotating parts enclose the stationary band without touching it; only other rotors' parts can block.
        hits = {st: sorted(o['name'] for o in fixed if st in o['states'] and o.get('rotor') != m['rotor'] and blocks(o)) for st in STATES}
        prereq = sorted(o['name'] for o in parts if o is not m and o['rotor'] == m['rotor'] and blocks({**o, 'angle': None}) and
                        (o['sector'] is None or m['sector'] is None or angular_gap(m['sector'], (o['sector'][0]+o['sector'][1])/2, m['r0'], 0.0) < 0))
        rows[m['name']] = dict(module=m['module'], direction=m['withdraw'], path_x_m=list(span), fixed_obstacles=hits, prerequisites=prereq,
                               passed=not any(hits.values()))
    return rows


def running(s):
    """Radial and axial clearances between stationary and rotating hub parts, ring-stop locks, arms and neighbours."""
    p, ri = s['prototype'], s['rotor_interface']; clr = p['mechanical_clearance_m']
    magnetic_gap = ri['rotating_inner_radius_m']-ri['stator_outer_radius_m']
    touchdown_gap = ri['rotating_inner_radius_m']-ri['touchdown_outer_radius_m']
    mods = ri['modules']; f = ri['fluid_coupling']; d0, d1 = ri['drum_u_m']
    lock_u, lock_r = ri['ring_lock_u_m'], ri['ring_lock_radius_m']
    hr = s['habitat_ring']; rail_u, rail_r = hr['spoke_rail_u_m'], hr['spoke_rail_radius_m']; sweep = habitat_ring.sweep_half(s)
    pin = ri['ring_lock_pin_outer_radius_m']
    aft = min(lock_u-lock_r, d0); fwd = f['stator_u_m'][1]
    ref = hull_geometry.refuge(s); c = habitat_ring.centers(s)
    # The largest spine radius under any hub (HUM-001: the hubs sit on the spine core, layout.spine_core) sets the seal-to-spine gap.
    spine = max(layout.spine_radius_at(s, x+u) for x in c for u in (aft, fwd))
    mount_aft = layout.at(s, p['forward_mount_aft_x']); cage_end = layout.at(s, p['outer_cage_end_x']); front = layout.origin(s, 'RADIATOR_FRONT')
    rows = {
        'magnetic_display_gap_m': magnetic_gap,
        'touchdown_display_clearance_m': touchdown_gap,
        'spine_to_stationary_m': ri['stationary_inner_radius_m']-spine,
        'ring_to_drum_m': ri['drum_inner_radius_m']-ri['rotating_ring_outer_radius_m'],
        'ring_lock_to_drum_m': d0-(lock_u+lock_r),
        'ring_lock_to_spokes_m': -rail_u-rail_r-(lock_u+lock_r),
        'fluid_face_seal_display_gap_m': f['stator_u_m'][0]-f['rotor_u_m'][1],
        'spoke_to_fluid_face_m': f['spoke_u_m']-f['spoke_radius_m']-f['rotor_u_m'][1],
        'rotor2_fwd_to_refuge_m': ref['x0']-(c[1]+fwd),
        'rotor1_fwd_to_rotor2_aft_m': (c[1]+aft)-(c[0]+fwd),
        'rotor2_fwd_to_forward_mount_m': mount_aft-(c[1]+fwd),
        # Ring sweep (frame plus allowance) against the fixed neighbours: outer cage end, radiator front, the other ring and the forward mount.
        'ring_sweep_aft_to_outer_cage_m': (c[0]-sweep)-cage_end,
        'ring_sweep_to_radiator_front_m': (c[0]-sweep)-(front+p['radiator_leading_spar_radius_m']),
        'ring_planes_gap_m': (c[1]-sweep)-(c[0]+sweep),
        'ring_sweep_fwd_to_forward_mount_m': mount_aft-(c[1]+sweep),
    }
    need = {k: clr for k in rows if k not in ('magnetic_display_gap_m', 'touchdown_display_clearance_m', 'spine_to_stationary_m', 'ring_to_drum_m', 'fluid_face_seal_display_gap_m')}
    failures = [k for k, v in rows.items() if not v >= need.get(k, 1e-9)]
    # Controlled touchdown: a rotor that loses levitation lands on the cartridges, never on a magnetic stator.
    if not 0 < touchdown_gap < magnetic_gap:
        failures.append('touchdown clearance must be positive and smaller than the magnetic gap')
    us = [(m['u0_m'], m['u1_m']) for m in mods]
    if not all(a < b for a, b in us) or not all(b1 < a2 for (_, b1), (a2, _) in zip(us, us[1:])):
        failures.append('module stack must be ordered and non-overlapping')
    if not (d0 <= us[0][0] and us[-1][1] <= d1 < f['rotor_u_m'][0] < f['rotor_u_m'][1] < f['stator_u_m'][0] < f['spoke_u_m'] < f['stator_u_m'][1]):
        failures.append('drum must cover the stack; fluid face, cartridge and spokes follow the forward drum end')
    if not (d0 < -(rail_u+rail_r) and rail_u+rail_r < d1):
        failures.append('ring spokes must attach to the drum')
    if not (spine < ri['stationary_inner_radius_m'] < ri['stator_outer_radius_m'] < ri['touchdown_outer_radius_m'] < ri['rotating_inner_radius_m']
            < ri['rotating_ring_outer_radius_m'] < ri['drum_inner_radius_m'] < ri['drum_outer_radius_m']):
        failures.append('radial bands out of order')
    # The retracted pin stays inside the vestibule-strut sweep and outside the spine-side stationary band's inner radius.
    if not (ri['stationary_inner_radius_m'] < pin and math.hypot(pin, lock_r) <= retracted_lock_outer_radius_max(s)):
        failures.append('ring-stop lock pins must stay inside the vestibule-strut sweep and outside the stationary inner radius')
    return dict(clearances=rows, failures=failures, passed=not failures)


def power_path(s):
    """Hub power chain: A/B ship buses -> device ride-through at the rotor transfer -> inductive primary -> rotor bus."""
    buses = [f'POWER_BUS_{b}' for b in s['power']['bus_names']]
    return {'sources': buses, 'ride_through': [f'IF_RIDE_THROUGH_ROTOR_TRANSFER_{r["index"]}' for r in rotors(s)],
            'transfer': 'INDUCTIVE', 'excludes': ['SURVIVAL_RESERVE'], 'emergency_path_source_known': False,
            'note': 'The survival reserve is fault-isolated and its sourced loads do not name the rotor hub; whether rotating-side life support needs its own reserve is an owner question.'}


# ---------- states and actions ------------------------------------------------------------------------------------

def actions(s):
    """Key tables per action and rotor control. Rotor 1 is the example faulted rotor in WF_ROTOR_TOUCHDOWN; rotor 2 brakes on the
    same spin curve (matched spin-down keeps the counter-rotating momenta cancelled)."""
    st, td = s['rotor_interface']['stop_lock_frames'], s['rotor_interface']['touchdown_frames']
    brake = {**ROTATING, 'motor_driving': 0.0, 'motor_braking': 1.0}
    stopped = {**brake, 'motor_braking': 0.0, 'spin_fraction': 0.0}
    stop_lock = [(1, ROTATING), (st['brake'], brake), (st['stopped'], stopped), (st['index_lock'], {**stopped, 'index_lock_engaged': 1.0}),
            (st['set_down'], {**stopped, 'index_lock_engaged': 1.0, 'levitation_active': 0.0, 'touchdown_contact': 1.0}), (st['ring_locks'], STOPPED_LOCKED), (st['end'], STOPPED_LOCKED)]
    fault = {**brake, 'levitation_active': 0.0, 'touchdown_contact': 1.0, 'health_alarm': 1.0, 'inspection_required': 1.0}
    landed = {**fault, 'motor_braking': 0.0, 'spin_fraction': 0.0}
    faulted = [(1, ROTATING), (td['fault'], fault), (td['stopped'], landed), (td['index_lock'], {**landed, 'index_lock_engaged': 1.0}), (td['end'], {**landed, 'index_lock_engaged': 1.0})]
    matched = [(1, ROTATING), (td['fault'], brake), (td['stopped'], stopped), (td['index_lock'], {**stopped, 'index_lock_engaged': 1.0}), (td['end'], {**stopped, 'index_lock_engaged': 1.0})]
    # Seal fault (Q30): the vestibule is isolated and the rotor stops on the same controlled curve as stop_lock; rotor 1 is the example faulted rotor.
    isolated = {'health_alarm': 1.0, 'inspection_required': 1.0, 'vestibule_isolated': 1.0}
    seal_fault = [(f, {**v, **(isolated if f >= st['brake'] else {})}) for f, v in stop_lock]
    rotors_ = [r['index'] for r in rotors(s)]
    return {
        'WF_RING_STOP_LOCK': dict(description='Stop and lock before high thrust: motor-braked regenerative spin-down while levitated, stop at the index angle, index lock, set down on the touchdown cartridges at zero speed, then the ring-stop locks. The rings stay full size and no room turns.',
                                  slots={control(j): stop_lock for j in rotors_}, frame_range=[1, st['end']]),
        'WF_ROTOR_TOUCHDOWN': dict(description='Loss of levitation on rotor 1 (example): it lands on its touchdown cartridges at speed and brakes to a stop; rotor 2 stays levitated and brakes on the same curve. Inspection required before full-speed service.',
                                   slots={control(rotors_[0]): faulted, **{control(j): matched for j in rotors_[1:]}}, frame_range=[1, td['end']]),
        'WF_VESTIBULE_SEAL_FAULT': dict(description='A leak path across a vestibule seal on rotor 1 (example): the hatches isolate the vestibule, the health alarm and inspection flags are raised and both rotors stop and lock on the stop-lock curve (matched spin-down keeps the counter-rotating momenta cancelled). The second seal plane still holds the pressure boundary.',
                                        slots={control(rotors_[0]): seal_fault, **{control(j): stop_lock for j in rotors_[1:]}}, frame_range=[1, st['end']]),
    }


def frames_per_turn(s):
    """Display frames of one revolution at full speed: the Rotor_n driver turns the ring at the sourced rpm in real time at 24 fps."""
    return 60*24/s['habitat']['rpm']


def spin_turned(s, keys):
    """FUT-007: [(frame, turned)] LINEAR keys of the ring turn, in frames at full speed, for LINEAR spin_fraction keys [(frame, spin)]
    (held constant outside them). The turn is the integral of spin, so it never decreases, and a ring at rest sits at its index angle
    (a whole number of turns):
    - between two rests the integral is scaled to the nearest whole number of turns, at least one: a display-rate choice, since no
      spin-down law or duration is sourced (S6) and the phases around it are not to scale;
    - a run that starts spinning is counted back from its first stop, so it starts at whatever angle brings it to the index;
    - a run that ends spinning keeps the true rate.
    Keys fall on every spin key and on every whole frame of a ramp, where the turn is quadratic."""
    rev = frames_per_turn(s); keys = [(float(f), float(v)) for f, v in keys]
    if any(v < 0 for _, v in keys):
        raise ValueError('spin_fraction below zero would turn the ring backwards')
    frames = sorted({f for f, _ in keys} | {float(f) for (f0, a), (f1, b) in zip(keys, keys[1:]) if a != b for f in range(int(f0)+1, int(f1)+(f1 != int(f1)))})

    def spin(f):
        if f <= keys[0][0]:
            return keys[0][1]
        for (f0, a), (f1, b) in zip(keys, keys[1:]):
            if f <= f1:
                return a+(b-a)*(f-f0)/(f1-f0)
        return keys[-1][1]
    raw = [0.0]
    for f0, f1 in zip(frames, frames[1:]):
        raw.append(raw[-1]+(spin(f0)+spin(f1))/2*(f1-f0))
    rest = [spin(f) == 0 for f in frames]
    # Spinning runs: maximal index spans [i, j] whose interior frames spin; each end is a rest frame or the end of the keys.
    runs, i = [], 0
    while i < len(frames)-1:
        if rest[i] and rest[i+1]:
            i += 1; continue
        j = i+1
        while j < len(frames)-1 and not rest[j]:
            j += 1
        runs.append((i, j)); i = j
    out = [0.0]*len(frames); base = 0.0; done = 0
    for i, j in runs:
        for n in range(done, i+1):
            out[n] = base
        T = raw[j]-raw[i]; starts, stops = rest[i], rest[j]
        if starts and stops:
            k = max(1, round(T/rev))*rev/T
            for n in range(i, j+1):
                out[n] = base+k*(raw[n]-raw[i])
        elif stops:
            whole = math.ceil(T/rev)*rev
            for n in range(i, j+1):
                out[n] = base+whole-(raw[j]-raw[n])
        else:
            for n in range(i, j+1):
                out[n] = base+raw[n]-raw[i]
        base = out[j]; done = j+1
    for n in range(done, len(frames)):
        out[n] = base
    return [(f if f != int(f) else int(f), v) for f, v in zip(frames, out)]


def state_rules(state):
    """Physical-sense rules for one display state; returns the violated rule names."""
    bad = []
    if not (state['levitation_active'] or state['touchdown_contact'] or state['ring_locks_engaged']):
        bad.append('rotor unsupported')
    if state['spin_fraction'] > 0 and (state['index_lock_engaged'] or state['ring_locks_engaged']):
        bad.append('locks engaged while spinning')
    if state['ring_locks_engaged'] and not state['index_lock_engaged']:
        bad.append('ring locks without the index lock')
    if state['motor_driving'] and state['motor_braking']:
        bad.append('motor driving and braking')
    if state['touchdown_contact'] and state['spin_fraction'] > 0 and not state['health_alarm']:
        bad.append('touchdown at speed without a fault')
    if state['health_alarm'] and state['touchdown_contact'] and not state['inspection_required']:
        bad.append('touchdown event without inspection flag')
    if state['vestibule_isolated'] and not (state['health_alarm'] and state['inspection_required']):
        bad.append('vestibule isolated without a fault')
    return bad


def saved_states(s):
    """The vehicle's saved pose: the preset it is saved at and that preset's control state."""
    preset = s['vehicle']['saved_preset']
    return {'preset': preset, 'state': configuration_state(s, preset)}


def kinetic_energy(s):
    rd = s['physics']['rotor_dynamics']
    return 0.5*rd['inertia_each_kg_m2']*rd['omega_rad_s']**2


# ---------- validation --------------------------------------------------------------------------------------------

def open_fields(s):
    t = s['habitat']['transfer']
    return {'ring_stop_locks.rating': t['ring_stop_locks']['rating'], 'magnetic_support.sizing': t['magnetic_support']['sizing'], 'magnetic_support.losses': t['magnetic_support']['losses'],
            'touchdown_bearings.sizing': t['touchdown_bearings']['sizing'], 'touchdown_bearings.material_stack': t['touchdown_bearings']['material_stack'],
            'hub_motor.rating': t['hub_motor']['rating'], 'power_data.rating': t['power_data']['rating'],
            'power_data.emergency_source': t['power_data']['emergency_source'], 'fluids.circuits': t['fluids']['circuits'],
            'health_channels.thresholds': t['health_channels']['thresholds'], 'spin_down': t['spin_down'], 'bearing_seal': t['bearing_seal']}


def check(s):
    """Architecture, OPEN-value, geometry, service, power-path and state checks. Failures are listed, never silenced."""
    failures = []
    def require(condition, message):
        if not condition:
            failures.append(message)
    t = s['habitat']['transfer']; ri = s['rotor_interface']
    mag, td, motor, pd, fl = t['magnetic_support'], t['touchdown_bearings'], t['hub_motor'], t['power_data'], t['fluids']
    require(t['mechanisms']['normal_slip_rings'] is False and pd['normal_slip_rings'] is False, 'No normal-operation slip rings (I5, MEC-005)')
    require(mag['role'] == 'PRIMARY' and mag['technology'] == 'ACTIVE_MAGNETIC_BEARING' and mag['zero_loss'] is False, 'Magnetic primary support, never zero-loss')
    require(mag['failure_response'] == 'CONTROLLED_TOUCHDOWN_AND_SPIN_DOWN', 'Loss of levitation triggers controlled touchdown and spin-down')
    require(td['role'] == 'BACKUP' and td['continuous_duty'] is False and td['inspect_after_touchdown'] is True and td['module'] == 'SERVICEABLE_CARTRIDGE', 'Touchdown cartridges: backup, not continuous duty, serviceable, inspected')
    require(set(td['duty']) == {'STARTUP', 'SHUTDOWN', 'OVERLOAD', 'MAGNETIC_FAILURE'}, 'Touchdown duty cases')
    require(motor['drive'] == 'DIRECT_ELECTROMAGNETIC' and motor['mechanical_reduction'] is False and motor['lock_before_high_thrust'] is True and motor['single_channel_loss_tolerant'] is True, 'Direct hub motor, lockable, single-channel-loss tolerant')
    require(s['power']['habitat_motor_count'] == habitat_ring.ring_count(s), 'One hub motor per ring')
    require(pd['power'] == 'INDUCTIVE' and pd['redundant_channels'] is True and pd['emergency_low_power_path'] is True, 'Contactless power with redundancy and an emergency path')
    require(fl['crossing'] == 'ESSENTIAL_ONLY' and {'LEAK_DETECTION', 'ISOLATION'} <= set(fl['features']), 'Essential fluids only, with leak detection and isolation')
    require(t['serviceability']['spine_dismantle_for_removal'] is False, 'Cartridges removable without dismantling the spine')
    require(t['ring_stop_locks']['actuator_in_load_path'] is False, 'High-thrust loads bypass the actuators')
    require(set(t['health_channels']['channels']) == {'BEARING_GAP', 'VIBRATION', 'TEMPERATURE', 'TORQUE', 'SEAL_LEAKAGE', 'LUBRICANT_STATE', 'TOUCHDOWN_EVENTS'}, 'Seven MEC-015 health channels')
    for path, field in open_fields(s).items():
        require(field.get('known') is False and 'value' not in field, f'{path} stays OPEN')
    # PROTOTYPE layout
    require(ri['status'] == 'PROTOTYPE' and ri['unit'] == 'm', 'Rotor interface layout stays PROTOTYPE')
    counts = {}
    for m in ri['modules']:
        counts[m['function']] = counts.get(m['function'], 0)+1
        require(m['withdraw'] in ('AFT', 'FWD') and 1 <= m.get('segments', ri['segment_count']) <= ri['segment_count'], f"{m['id']}: withdrawal/segments")
    require(counts == FUNCTIONS, f'Module functions per rotor: {counts}')
    require(len({m['id'] for m in ri['modules']}) == len(ri['modules']), 'Module IDs unique')
    require(0 < ri['segment_half_span_deg']*2 < 360/ri['segment_count'], 'Segments leave gaps between them')
    run = running(s)
    require(run['passed'], f"Hub clearances: {run['failures']}")
    service = withdrawal(s)
    for name, row in service.items():
        require(row['passed'], f"{name}: withdrawal blocked by {row['fixed_obstacles']}")
        # Touchdown cartridges (inspected after every touchdown) and the fluid cartridge (life-limited seals) come out first.
        if row['module'].startswith('TOUCHDOWN') or row['module'] == 'FLUID_COUPLING':
            require(not row['prerequisites'], f"{name}: must withdraw without removing {row['prerequisites']}")
    # Power path meets the P1-007 ride-through markers and stays off the survival reserve.
    rt = {r['load'] for r in power_storage.ride_through_points(s)}
    require({f'ROTOR_TRANSFER_{r["index"]}' for r in rotors(s)} <= rt, 'Ride-through bridges each rotor transfer')
    pp = power_path(s)
    # Separate from the survival reserve: not a hub source, and no rotor/hub load on the reserve (its sourced loads name none).
    require('SURVIVAL_RESERVE' not in pp['sources'] and not any(l.startswith(('ROTOR', 'HUB')) for l in s['power']['storage']['survival_reserve']['loads']),
            'Hub power stays separate from the survival reserve')
    feeds = {i['name']: i for i in interfaces(s)}
    points = {r['load']: r['at'] for r in power_storage.ride_through_points(s)}
    for rot in rotors(s):
        j = rot['index']; at = points.get(f'ROTOR_TRANSFER_{j}')
        require(at is not None and math.dist(feeds[f'IF_HUB{j}_POWER_FEED']['at'], at) < 1e-9, f'IF_HUB{j}_POWER_FEED must meet IF_RIDE_THROUGH_ROTOR_TRANSFER_{j}')
    # States: one per buildable preset, sensible at every key, the stop-lock action ends in STOPPED_LOCKED, matched spin-down.
    for name in buildable_names(s):
        state = configuration_state(s, name)
        require(state == SAVED[s['configuration'][name]['habitat']], f'{name}: preset controls must reproduce its habitat state')
    for state in (ROTATING, STOPPED_LOCKED):
        require(set(state) == set(PROPS) and not state_rules(state), f'Saved state rules: {state_rules(state)}')
    require(saved_states(s)['state'] == ROTATING, 'The vehicle is saved at a rotating preset')
    acts = actions(s)
    for aname, a in acts.items():
        for slot, keys in a['slots'].items():
            frames = [f for f, _ in keys]
            require(frames[0] == 1 and all(x < y for x, y in zip(frames, frames[1:])) and frames[-1] == a['frame_range'][1], f'{aname}/{slot}: frames')
            for f, v in keys:
                require(not state_rules(v), f'{aname}/{slot} frame {f}: {state_rules(v)}')
    require(acts['WF_RING_STOP_LOCK']['slots'][control(1)][-1][1] == STOPPED_LOCKED, 'The stop-lock action ends in STOPPED_LOCKED')
    slots = list(acts['WF_ROTOR_TOUCHDOWN']['slots'].values())
    require(all([(f, v['spin_fraction']) for f, v in k] == [(f, v['spin_fraction']) for f, v in slots[0]] for k in slots), 'Matched spin-down: both rotors follow one spin curve')
    require(slots[0][-1][1]['inspection_required'] == 1.0 and slots[1][-1][1]['inspection_required'] == 0.0, 'Only the rotor that touched down needs inspection')
    # Seal fault (Q30, habitat.transfer.seal_fault_action): isolate the vestibule and stop on the stop-lock curve; the end state is STOPPED_LOCKED with the vestibule isolated.
    require(s['habitat']['transfer']['seal_fault_action'] == 'ISOLATE_VESTIBULE_AND_CONTROLLED_RING_STOP', 'Seal-fault rule must isolate the vestibule and stop the ring in a controlled way')
    sf = list(acts['WF_VESTIBULE_SEAL_FAULT']['slots'].values()); sl = acts['WF_RING_STOP_LOCK']['slots']
    require(sf[0][-1][1] == {**STOPPED_LOCKED, 'health_alarm': 1.0, 'inspection_required': 1.0, 'vestibule_isolated': 1.0} and sf[1][-1][1] == STOPPED_LOCKED, 'Seal fault ends STOPPED_LOCKED with the vestibule isolated on the faulted rotor only')
    require(all([(f, v['spin_fraction']) for f, v in k] == [(f, v['spin_fraction']) for f, v in sl[control(1)]] for k in sf), 'Seal fault: both rotors stop on the stop-lock spin curve')
    require(kinetic_energy(s) > 0, 'Rotor kinetic energy')
    return dict(passed=not failures, failures=failures, running=run, withdrawal=service)


def contract(s):
    """Rig-contract section: sourced architecture, OPEN values, the derived spin-down energy, per-rotor layout and states."""
    t = s['habitat']['transfer']; ri = s['rotor_interface']; service = withdrawal(s)
    src = lambda f: {'canon_status': f['canon_status'], 'source_ref': f['source_ref']}
    unknown = lambda f: {'known': False, 'canon_status': f['canon_status'], 'evidence_ref': f['evidence_ref'], 'reason': f['reason'], **({'items': f['items']} if 'items' in f else {})}
    rows = []
    for rot in rotors(s):
        j = rot['index']
        mods = [{'id': m['id'], 'function': m['function'], 'x_m': [rot['x']+m['u0_m'], rot['x']+m['u1_m']], 'segments': m.get('segments', ri['segment_count']),
                 'withdraw': m['withdraw'], 'removal_prerequisites': service[f"Hub{j}_{m['id']}_S1"]['prerequisites']} for m in ri['modules']]
        f = ri['fluid_coupling']
        mods.append({'id': 'FLUID_COUPLING', 'function': 'FLUID_COUPLING', 'x_m': [rot['x']+f['stator_u_m'][0], rot['x']+f['stator_u_m'][1]], 'segments': 1,
                     'withdraw': 'FWD', 'removal_prerequisites': service[f'Hub{j}_FLUID_COUPLING_Stator']['prerequisites']})
        rows.append({'name': f'ROTOR_{j}', 'anchor': f'WF_SIM_ROTOR_{j}_AXIS', 'control': control(j), 'modules': mods,
                     'interfaces': [i['name'] for i in interfaces(s) if i['rotor'] == j],
                     'ring_stop_locks': [b['name'] for b in ring_stop_locks(s) if b['rotor'] == j], 'geometry_status': 'PROTOTYPE'})
    acts = actions(s)
    return {
        'generation': 'P1-008', 'direction': t['mechanisms']['direction'], 'canon': src(t['mechanisms']),
        'architecture': {
            'magnetic_support': {**{k: t['magnetic_support'][k] for k in ('role', 'technology', 'control', 'failure_response', 'zero_loss')}, **src(t['magnetic_support'])},
            'touchdown_bearings': {**{k: t['touchdown_bearings'][k] for k in ('role', 'duty', 'continuous_duty', 'lubrication', 'module', 'inspect_after_touchdown')}, **src(t['touchdown_bearings'])},
            'hub_motor': {**{k: t['hub_motor'][k] for k in ('drive', 'mechanical_reduction', 'reduction_fallback', 'single_channel_loss_tolerant', 'lock_before_high_thrust')}, **src(t['hub_motor'])},
            'power_data': {**{k: t['power_data'][k] for k in ('power', 'data_candidates', 'redundant_channels', 'emergency_low_power_path', 'normal_slip_rings')}, **src(t['power_data'])},
            'fluids': {**{k: t['fluids'][k] for k in ('rotor_autonomy', 'crossing', 'coupling', 'seal_life', 'features')}, **src(t['fluids'])},
            'serviceability': {**{k: t['serviceability'][k] for k in ('modules', 'module_form', 'spine_dismantle_for_removal')}, **src(t['serviceability'])},
            'ring_stop_locks': {'rule': t['ring_stop_locks']['rule'], 'actuator_in_load_path': False, 'axial_load_ref': t['ring_stop_locks']['axial_load_ref'], **src(t['ring_stop_locks'])},
            'health_channels': {'channels': t['health_channels']['channels'], 'feeds': t['health_channels']['feeds'], **src(t['health_channels'])},
        },
        'open': {k: unknown(v) if 'reason' in v else {'known': False, 'canon_status': v['canon_status']} for k, v in open_fields(s).items()},
        'derived': {'kinetic_energy_each_J': {'known': True, 'value': kinetic_energy(s), 'unit': 'J', 'canon_status': 'DERIVED', 'evidence_ref': 'rotor_dynamics',
                                              'basis': 'Ring-equivalent 0.5*I*omega^2 per rotor: the energy a full spin-down removes by motor braking and/or touchdown friction. The split, rate and heat path are OPEN.'}},
        'power_path': power_path(s),
        'rotors': rows,
        'states': {'ROTATING': ROTATING, 'STOPPED_LOCKED': STOPPED_LOCKED, 'saved_preset': saved_states(s)['preset'],
                   'by_configuration': {name: configuration_state(s, name) for name in buildable_names(s)},
                   'status': 'PROTOTYPE display states on ROTOR_n_MECH_CTRL; not a control law'},
        'actions': {k: {'description': a['description'], 'frame_range': a['frame_range'], 'slots': {slot: [{'frame': f, 'state': v} for f, v in keys] for slot, keys in a['slots'].items()}}
                    for k, a in acts.items()},
    }


def report(s):
    result = check(s)
    return {'task': 'P1-008', 'scope': 'Sourced rotor-interface architecture; PROTOTYPE hub proxies, service paths and display states. No bearing, motor, coupler, loss or spin-down sizing.',
            'passed': result['passed'], 'failures': result['failures'], 'running': result['running'], 'withdrawal': result['withdrawal'],
            'contract': contract(s)}


if __name__ == '__main__':
    import spec
    data, _, _, _ = spec.load()
    out = report(data)
    OUTPUT.write_text(json.dumps(out, indent=1)+'\n')
    print('WF_ROTOR_INTERFACE', 'PASS' if out['passed'] else 'FAIL', OUTPUT)
