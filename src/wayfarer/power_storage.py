"""P1-007 electrical storage and black start: sourced layers, the nine-step sequence, PROTOTYPE placement and checks.

Canon (drive_capture_2026-09-29, S&E 17_POWER_STORAGE): a WORKING 2 MWh main battery (~800 Wh/kg pack-level
extrapolation), a WORKING 200 kWh / 50 MW supercapacitor pulse bank, a BASELINE fault-isolated survival reserve
(capacity OPEN) and BASELINE device-level ride-through. Survival power does not imply restart power; fusion may shut
down completely. Storage mass stays inside the existing 50 t power/computers/steering/comms allowance.

Nothing here sizes a pack, a generator, a coast load or an endurance: those stay known = false. The only numbers
derived are exact consequences of sourced values (discharge time, charge ratio, energy in joules) plus one labelled
DIAGNOSTIC extrapolated pack mass. Pack volumes and positions come from the PROTOTYPE [power_storage] table.

Standard library only; imported by spec, the Blender recipe, the rig, inspect and tests.
"""
from pathlib import Path
import json
import math
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hull_geometry
import habitat_ring
import layout
import drive_manifold

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT/'references/p1_power_storage.json'
WH = 3600.0
CONTROL = 'POWER_STORAGE_CTRL'
ACTION = 'WF_BLACK_START'
STORES = {'MAIN_BATTERY', 'PULSE_BANK', 'SURVIVAL_RESERVE', 'RIDE_THROUGH'}
SUPPLIES = STORES | {'FUSION_BUS', 'SHIP_BUS'}
REACTOR = ['OFF', 'STARTING', 'FUSION', 'SUSTAINED']

# Black-start display states on POWER_STORAGE_CTRL: 0/1 flags plus the step number, keyed CONSTANT (a state machine,
# not a charge curve). No state of charge is shown: how much energy a start draws is OPEN.
PROPS = {
    'black_start_step': 'Current owner black-start step (0 = cold ship, 1-9 = 17_POWER_STORAGE A10:A18).',
    'ship_services_awake': 'Minimal control, pumps, diagnostics and thermal conditioning available (step 1 on).',
    'main_battery_supplying': 'Main battery supplies ship services and charges the pulse bank (steps 1-8).',
    'pulse_bank_charging': 'Pulse bank charging: from the main battery (step 2) or the fusion bus (step 9).',
    'pulse_bank_armed': 'Pulse bank armed for the startup pulse (after step 2 until its discharge).',
    'pulse_bank_discharging': 'Pulse bank drives startup heating / magnetic transient (step 5).',
    'fusion_bus_supplying': 'Fusion electrical generation carries ship load (step 9).',
    'main_battery_charging': 'Main battery recharging from the fusion bus (step 9).',
    'survival_reserve_standby': 'Survival reserve maintained and fault-isolated; never a restart source.',
}


def radial(x, r, a):
    return (x, r*math.cos(a), r*math.sin(a))


def sub(a, b):
    return tuple(p-q for p, q in zip(a, b))


def dot(a, b):
    return sum(p*q for p, q in zip(a, b))


# ---------- sourced quantities ------------------------------------------------------------------------------------

def quantities(s):
    """Exact consequences of the sourced energy/power values, in SI. Nothing here is a sizing result."""
    st = s['power']['storage']; main, pulse = st['main_battery'], st['pulse_bank']
    main_J = main['usable_energy_Wh']*WH; pulse_J = pulse['energy_Wh']*WH
    return {
        'main_usable_energy_J': main_J,
        'pulse_energy_J': pulse_J,
        'pulse_full_discharge_at_rated_power_s': pulse_J/pulse['power_W'],
        'pulse_charges_per_main_battery': main_J/pulse_J,
        'main_battery_fraction_per_pulse_charge': pulse_J/main_J,
        # DIAGNOSTIC: the owner's extrapolated pack-level specific energy applied to the usable energy. Not installed
        # mass (containment, thermal and switching are unsolved); main_battery.installed_mass stays known = false.
        'main_battery_extrapolated_pack_mass_kg': main['usable_energy_Wh']/main['specific_energy_Wh_kg'],
    }


def mass_allowance(s):
    items = {i['id']: i for i in s['physics']['mass_budget']['items']}
    return items[s['power']['storage']['mass_budget_item']]


# ---------- PROTOTYPE placement -----------------------------------------------------------------------------------

def packs(s):
    """Storage proxies as radial boxes: dict(name, layer, x0, x1, angle, r0, r1, width, corners, center, interface)."""
    ps = s['power_storage']; out = []
    def box(name, layer, b, ident, interface):
        bx0, bx1 = layout.at(s, b['x0']), layout.at(s, b['x1'])
        a = math.radians(b['angle_deg']); u = (0.0, math.cos(a), math.sin(a)); t = (0.0, -math.sin(a), math.cos(a))
        corners = [(x, r*u[1]+w*t[1], r*u[2]+w*t[2]) for x in (bx0, bx1) for r in (b['r0_m'], b['r1_m']) for w in (-b['width_m']/2, b['width_m']/2)]
        rc = (b['r0_m']+b['r1_m'])/2
        out.append(dict(name=name, layer=layer, ident=ident, interface=interface, x0=bx0, x1=bx1, angle=a, r0=b['r0_m'], r1=b['r1_m'],
                        width=b['width_m'], u=u, t=t, corners=corners, center=radial((bx0+bx1)/2, rc, a),
                        volume_m3=(bx1-bx0)*(b['r1_m']-b['r0_m'])*b['width_m']))
    box('Main_Battery', 'MAIN_BATTERY', ps['main_battery'], 'WF.POWER.MAIN_BATTERY', 'IF_MAIN_BATTERY')
    box('Pulse_Bank', 'PULSE_BANK', ps['pulse_bank'], 'WF.POWER.PULSE_BANK', 'IF_PULSE_BANK')
    for j, b in enumerate(ps['survival_packs'], 1):
        box(f'Survival_Reserve_{j}', 'SURVIVAL_RESERVE', b, f'WF.POWER.SURVIVAL.{j}', f'IF_SURVIVAL_RESERVE_{j}')
    return out


def pack_interfaces(s):
    """Connection interfaces on the packs (all OPEN): bus tie, charge path, drive feed and survival isolators."""
    by = {p['name']: p for p in packs(s)}; out = []
    def face(p, x):
        return radial(x, (p['r0']+p['r1'])/2, p['angle'])
    m, q = by['Main_Battery'], by['Pulse_Bank']
    out.append(dict(name='IF_MAIN_BATTERY_BUS_TIE', at=face(m, m['x0']), status='OPEN S5: tie to the A/B buses (fusion-bus charging and discharge); switching and ratings not designed'))
    out.append(dict(name='IF_PULSE_BANK_CHARGE', at=face(q, q['x1']), status='OPEN: charge path from the main battery or fusion bus (17_POWER_STORAGE E5); charger not designed'))
    out.append(dict(name='IF_PULSE_BANK_DRIVE_FEED', at=face(q, q['x0']), status='OPEN: high-power feed to seed coils / startup heating; route, conductor and switching not designed'))
    for p in packs(s):
        if p['layer'] == 'SURVIVAL_RESERVE':
            out.append(dict(name=p['interface']+'_ISOLATOR', at=face(p, p['x0']),
                            status='OPEN: charge path from the ship bus with fault isolation (17_POWER_STORAGE F6); isolation device not designed'))
    return out


def ride_through_points(s):
    """Device-level ride-through markers at the critical loads they bridge, reusing each load's interface position."""
    p = s['prototype']; L = s['ship']['length']['value']; ref = hull_geometry.refuge(s)
    bus = s['power']['bus_names']; ys = [-p['brayton_offset_y_m'], p['brayton_offset_y_m']]
    where = {f'POWER_BUS_{bus[j]}': (('WF_STRUCTURE.blend', f'IF_POWER_BUS_{bus[j]}'), (layout.at(s, p['power_bus_x']), ys[j], 0.0)) for j in range(len(bus))}
    for j, x in enumerate(habitat_ring.centers(s), 1):
        where[f'ROTOR_TRANSFER_{j}'] = (('WF_STRUCTURE.blend', f'IF_ROTOR_TRANSFER_{j}'), (x, 0.0, 0.0))
    where['EYE_MOUNT'] = (('WF_EYE.blend', 'IF_EYE_MOUNT'), (L/2-p['eye_front_inset_m']-p['eye_module_depth_m'], 0.0, 0.0))
    where['REACTOR_MOUNT'] = (('WF_PROPULSION.blend', 'IF_REACTOR_MOUNT'), (layout.at(s, p['reactor_center_x']), 0.0, 0.0))
    where['CREW_REFUGE'] = (('WF_SERVICE.blend', 'IF_CREW_REFUGE'), ((ref['x0']+ref['x1'])/2, 0.0, 0.0))
    return [dict(name=f'IF_RIDE_THROUGH_{k}', load=k, at=where[k][1], pairs_with=where[k][0]) for k in s['power_storage']['ride_through_loads']]


def point_box(v, p):
    """Distance from a point to a radial pack box (0 inside)."""
    local = (v[0]-(p['x0']+p['x1'])/2, dot(v, p['u'])-(p['r0']+p['r1'])/2, dot(v, p['t']))
    half = ((p['x1']-p['x0'])/2, (p['r1']-p['r0'])/2, p['width']/2)
    return math.sqrt(sum(max(0.0, abs(c)-h)**2 for c, h in zip(local, half)))


def bounds_gap(a, b, radius, p):
    """Lower bound on the member/box gap from axis-aligned bounds (used to skip distant members)."""
    lo = [min(a[i], b[i])-radius for i in range(3)]; hi = [max(a[i], b[i])+radius for i in range(3)]
    plo = [min(c[i] for c in p['corners']) for i in range(3)]; phi = [max(c[i] for c in p['corners']) for i in range(3)]
    return math.sqrt(sum(max(0.0, plo[i]-hi[i], lo[i]-phi[i])**2 for i in range(3)))


def cylinder_box(a, b, radius, p, step=0.05, around=64):
    """Gap between a flat-ended cylinder (axis a->b) and a pack box, from points on its side and end caps. The
    half-spacing of the samples is subtracted, so the result never overstates the true gap; 0 or less means contact."""
    d = sub(b, a); length = math.sqrt(dot(d, d)); e = tuple(c/length for c in d)
    # Long members: keep only the part within 1 m (axially) of the box. Any cut face sits >= 1 m from the box, so it
    # cannot create a false minimum below that.
    span = [dot(sub(c, a), e) for c in p['corners']]
    # Box wholly beyond a member end by more than 1 m: the radius-padded bounds can read 0 while the true axial gap is large. The axial separation of
    # the flat end face from the nearest box corner is a true lower bound of the gap (HAB-001 regression).
    if min(span)-1.0 >= length or max(span)+1.0 <= 0:
        return max(bounds_gap(a, b, radius, p), min(span)-length if min(span) > length else -max(span))
    z0, z1 = max(0.0, min(span)-1.0), min(length, max(span)+1.0)
    if z1 <= z0:
        return bounds_gap(a, b, radius, p)
    a = tuple(a[i]+z0*e[i] for i in range(3)); length = z1-z0; b = tuple(a[i]+length*e[i] for i in range(3))
    helper = (1.0, 0.0, 0.0) if abs(e[0]) < .9 else (0.0, 1.0, 0.0)
    e1 = (e[1]*helper[2]-e[2]*helper[1], e[2]*helper[0]-e[0]*helper[2], e[0]*helper[1]-e[1]*helper[0])
    n = math.sqrt(dot(e1, e1)); e1 = tuple(c/n for c in e1)
    e2 = (e[1]*e1[2]-e[2]*e1[1], e[2]*e1[0]-e[0]*e1[2], e[0]*e1[1]-e[1]*e1[0])
    nx = max(1, math.ceil(length/step)); rings = [(k*length/nx, radius) for k in range(nx+1)]
    rings += [(z, radius*f) for z in (0.0, length) for f in (0.0, .2, .4, .6, .8)]
    at = lambda z, r, k: tuple(a[i]+z*e[i]+r*(math.cos(k*math.tau/around)*e1[i]+math.sin(k*math.tau/around)*e2[i]) for i in range(3))
    rel = sub(p['center'], a); along = dot(rel, e)
    if point_box(tuple(a[i]+length/2*e[i] for i in range(3)), p) == 0 or (0 <= along <= length and dot(rel, rel)-along**2 < radius**2):
        return 0.0
    spacing = max(length/nx, radius*math.tau/around, radius*.2)
    return min(point_box(at(z, r, k), p) for z, r in rings for k in range(around))-spacing/2


def obstacles(s):
    """Existing stationary members near the storage volume, as (name, a, b, radius); mirrors the recipes."""
    p = s['prototype']; L = s['ship']['length']['value']; x = lambda k: layout.at(s, p[k]); out = []
    import drive_manifold   # lazy: drive_manifold imports only layout at module level
    aft, fwd = drive_manifold.spine_span(s)
    # One cylinder at the larger radius: the HUM-001 spine core (layout.spine_core) is the radius near the packs and the crew route.
    out.append(('Structural_Spine', (aft, 0, 0), (fwd, 0, 0), max(p['spine_radius_m'], layout.spine_core(s)[2])))
    for j, (yy, zz) in enumerate([(1, 1), (-1, 1), (-1, -1), (1, -1)], 1):
        c = x('tank_center_x'); o = p['tank_offset_m']
        out.append((f'Tank_Volume_{j:02}', (c-p['tank_length_m']/2, yy*o, zz*o), (c+p['tank_length_m']/2, yy*o, zz*o), p['tank_radius_m']))
    for j, yy in enumerate([-p['brayton_offset_y_m'], p['brayton_offset_y_m']], 1):
        c = x('brayton_center_x')
        out.append((f'Brayton_Train_{j}', (c-p['brayton_length_m']/2, yy, 0), (c+p['brayton_length_m']/2, yy, 0), p['brayton_radius_m']))
    c = x('engineering_center_x')
    out.append(('Engineering_Envelope', (c-p['engineering_length_m']/2, 0, 0), (c+p['engineering_length_m']/2, 0, 0), p['engineering_radius_m']))
    for f in hull_geometry.service_fittings(s):
        out.append((f['name'], radial(f['x'], f['r0'], f['theta']), radial(f['x'], f['r1'], f['theta']), f['radius']))
    r = hull_geometry.refuge(s)
    out.append(('Refuge_Storm_Shelter', (r['x0'], 0, 0), (r['x1'], 0, 0), r['outer']))
    # P1-008 rotor hubs: the whole stationary and rotating stack, from the burn locks to the fluid cartridge, as one cylinder.
    ri = s['rotor_interface']
    for j, xx in enumerate(habitat_ring.centers(s), 1):
        out.append((f'Rotor_Hub_{j}', (xx+ri['ring_lock_u_m']-ri['ring_lock_radius_m'], 0, 0), (xx+ri['fluid_coupling']['stator_u_m'][1], 0, 0), ri['drum_outer_radius_m']))
    return out


def clearances(s):
    """Smallest gaps from each pack to existing members, the primary cage, the hull inner skin and the other packs."""
    clr = s['prototype']['mechanical_clearance_m']; ps = packs(s); cage = hull_geometry.cage_points(s); rows = {}
    for p in ps:
        # Members more than 1 m away by their bounds keep that bound (a conservative lower bound on the gap).
        members = {n: (lambda g: g if g > 1.0 else cylinder_box(a, b, r, p))(bounds_gap(a, b, r, p)) for n, a, b, r in obstacles(s)}
        near = min(members, key=members.get)
        cage_gap = min((point_box((x, y, z), p)-rr for x, y, z, rr in cage if p['x0']-6 < x < p['x1']+6), default=math.inf)
        # Hull inner skin: the outermost corner at the hull radius over the pack's axial span.
        skin = min(hull_geometry.radius_at(s, x) for x in (p['x0'], (p['x0']+p['x1'])/2, p['x1']))-s['hull']['shell_thickness_m']
        hull_gap = skin-max(math.hypot(c[1], c[2]) for c in p['corners'])
        others = [q for q in ps if q is not p]
        pack_gap = min(min(point_box(c, q) for c in p['corners']+[p['center']]) for q in others)
        rows[p['name']] = dict(nearest_member=near, member_gap_m=members[near], cage_gap_m=cage_gap, hull_gap_m=hull_gap, pack_gap_m=pack_gap,
                               passed=min(members[near], cage_gap, hull_gap, pack_gap) >= clr)
    return rows


def box_gap(p, q, samples=8):
    """Sampled minimum distance between two pack boxes (grid over each box, both directions)."""
    def grid(b):
        pts = []
        for i in range(samples+1):
            for j in range(samples+1):
                for k in range(samples+1):
                    x = b['x0']+(b['x1']-b['x0'])*i/samples; r = b['r0']+(b['r1']-b['r0'])*j/samples; w = b['width']*(k/samples-.5)
                    pts.append((x, r*b['u'][1]+w*b['t'][1], r*b['u'][2]+w*b['t'][2]))
        return pts
    return min(min(point_box(v, q) for v in grid(p)), min(point_box(v, p) for v in grid(q)))


def isolation(s):
    """Display separation of every survival pack from the main battery and pulse bank (owner rule: no shared failure path)."""
    ps = packs(s); need = s['power_storage']['survival_isolation_min_m']
    main = [p for p in ps if p['layer'] in {'MAIN_BATTERY', 'PULSE_BANK'}]
    rows = {p['name']: min(box_gap(p, q) for q in main) for p in ps if p['layer'] == 'SURVIVAL_RESERVE'}
    return dict(required_m=need, separation_m=rows, passed=all(v >= need for v in rows.values()))


# ---------- black start ------------------------------------------------------------------------------------------

def step_state(step):
    """Display flags after an owner step (0 = cold ship). Pure reading of 17_POWER_STORAGE A10:D18."""
    return {'black_start_step': float(step),
            'ship_services_awake': float(step >= 1),
            'main_battery_supplying': float(1 <= step <= 8),
            'pulse_bank_charging': float(step in (2, 9)),
            'pulse_bank_armed': float(2 <= step <= 4),
            'pulse_bank_discharging': float(step == 5),
            'fusion_bus_supplying': float(step >= 9),
            'main_battery_charging': float(step >= 9),
            'survival_reserve_standby': 1.0}


def action(s):
    """WF_BLACK_START key table on POWER_STORAGE_CTRL: one CONSTANT key per step at the PROTOTYPE frames, then a hold."""
    ps = s['power_storage']; frames = ps['black_start_frames']
    keys = [(f, step_state(k)) for k, f in enumerate(frames)]+[(ps['black_start_end_frame'], step_state(len(frames)-1))]
    return dict(description='Owner nine-step black start (17_POWER_STORAGE A10:D18): services wake, main battery arms the pulse bank, seed coils, '
                            'plasma breakdown, pulse heating, first fusion, lattice activation, field lock, fusion takes load. Plays with WF_DRIVE_STARTUP from frame 1.',
                keys=keys, frame_range=[frames[0], ps['black_start_end_frame']])


def action_state(s, frame):
    keys = action(s)['keys']; state = keys[0][1]
    for f, values in keys:
        if frame >= f:
            state = values
    return dict(state)


def drive_alignment(s):
    """WF_DRIVE_STARTUP at each black-start step frame must show that step's drive state (steps 3-8)."""
    frames = s['power_storage']['black_start_frames']
    at = lambda k: drive_manifold.action_state(s, 'WF_DRIVE_STARTUP', frames[k])
    before = lambda k: drive_manifold.action_state(s, 'WF_DRIVE_STARTUP', frames[k-1])
    rows = {
        3: at(3)['manifold_field_strength'] > 0 and at(3)['drive_active'] == 0 and at(3)['lattice_activation'] == 0,
        4: before(4)['drive_active'] == 0 and at(4)['drive_active'] > 0 and at(4)['lattice_activation'] == 0,
        5: at(5)['lattice_activation'] == 0,
        6: at(6)['drive_active'] > at(4)['drive_active'] and at(6)['lattice_activation'] == 0,
        7: at(7)['lattice_activation'] > 0,
        8: at(8)['lattice_activation'] == 1.0 and at(8)['manifold_field_strength'] == 1.0,
        9: at(9)['drive_active'] > 0,
    }
    return dict(steps={str(k): v for k, v in rows.items()}, passed=all(rows.values()))


# ---------- validation -------------------------------------------------------------------------------------------

def check(s):
    """Unit, energy, state, rule, mass and placement checks. Returns a report; failures are listed, never silenced."""
    failures = []
    def require(condition, message):
        if not condition:
            failures.append(message)
    pw = s['power']; st = pw['storage']; main, pulse, surv, ride = st['main_battery'], st['pulse_bank'], st['survival_reserve'], st['ride_through']
    q = quantities(s)
    require(set(st['layers']) == STORES and len(st['layers']) == 4, 'Four distinct storage layers')
    for key, value in [('main usable energy', main['usable_energy_Wh']), ('main specific energy', main['specific_energy_Wh_kg']),
                       ('pulse energy', pulse['energy_Wh']), ('pulse power', pulse['power_W'])]:
        require(isinstance(value, (int, float)) and math.isfinite(value) and value > 0, f'{key}: positive finite value')
    # 17_POWER_STORAGE D4/D5 quote 2 MWh and 200 kWh / 50 MW; unit mistakes (kWh for Wh, kW for W) fail here.
    require(math.isclose(main['usable_energy_Wh'], 2.0e6) and math.isclose(pulse['energy_Wh'], 2.0e5) and math.isclose(pulse['power_W'], 5.0e7), 'Captured storage values in Wh / W')
    require(pulse['energy_Wh'] <= main['usable_energy_Wh'], 'Step 2: the main battery must hold at least one full pulse-bank charge')
    require(set(pulse['charge_sources']) == {'MAIN_BATTERY', 'FUSION_BUS'}, 'Pulse bank charges only from the main battery or fusion bus')
    require('SURVIVAL_RESERVE' not in pulse['charge_sources'], 'Survival reserve is never a restart source')
    require(set(surv['isolated_from']) >= {'MAIN_BATTERY', 'PULSE_BANK', 'FIJI_LATTICE', 'FUSION_CONTROLS'}, 'Survival reserve isolation list')
    require(ride['scope'] == 'DEVICE_LOCAL' and ride['propulsion_store'] is False, 'Ride-through is device-local and not a propulsion store')
    rules = st['rules']
    require(rules['survival_power_implies_restart'] is False and rules['fusion_must_stay_burning_for_restart'] is False and rules['survival_shares_failure_path'] is False, 'Owner design rules')
    for path, field in [('power.rating', pw['rating']), ('power.hotel_source', pw['hotel_source']), ('power.degraded_modes', pw['degraded_modes']),
                        ('main_battery.installed_mass', main['installed_mass']), ('main_battery.fusion_off_endurance', main['fusion_off_endurance']),
                        ('pulse_bank.ignition_energy', pulse['ignition_energy']), ('survival_reserve.capacity', surv['capacity']),
                        ('survival_reserve.endurance', surv['endurance']), ('survival_reserve.pack_count', surv['pack_count']), ('ride_through.capacity', ride['capacity'])]:
        require(field.get('known') is False and 'value' not in field, f'{path} stays OPEN')
    # Mass: inside the existing stationary allowance; the extrapolated pack is only a DIAGNOSTIC share of it.
    item = mass_allowance(s)
    require(item.get('rotating_allowance_kg', 0) == 0, 'Storage allowance is stationary (no rotating mass added)')
    regions = {i['id']: i for i in s['physics']['mass_regions']['items']}
    require(regions[item['id']]['rotating_kg'] == 0, 'Storage mass region is stationary')
    require(q['main_battery_extrapolated_pack_mass_kg'] < item['mass_kg'], 'Extrapolated main pack exceeds the whole allowance')
    # Sequence: nine contiguous owner steps from reactor OFF / lattice cold to fusion carrying ship load.
    steps = s['power']['black_start']['steps']
    require([x['step'] for x in steps] == list(range(1, 10)), 'Nine contiguous black-start steps')
    require(all(x['reactor'] in REACTOR and set(x['supplied_by']) <= SUPPLIES and set(x['charges']) <= STORES for x in steps), 'Step vocabulary')
    order = [REACTOR.index(x['reactor']) for x in steps]
    require(order == sorted(order) and steps[0]['reactor'] == 'OFF' and steps[-1]['reactor'] == 'SUSTAINED', 'Reactor state only advances, OFF to SUSTAINED')
    require(all('SURVIVAL_RESERVE' not in x['supplied_by'] for x in steps if x['charges'] or x['reactor'] != 'OFF'), 'Survival reserve never charges or starts the drive')
    require(steps[1]['supplied_by'] == ['MAIN_BATTERY'] and steps[1]['charges'] == ['PULSE_BANK'], 'Step 2: main battery charges the pulse bank')
    require(steps[4]['supplied_by'] == ['PULSE_BANK'], 'Step 5: pulse bank drives the startup pulse')
    require(steps[-1]['supplied_by'] == ['FUSION_BUS'] and set(steps[-1]['charges']) == {'MAIN_BATTERY', 'PULSE_BANK'}, 'Step 9: fusion takes load and recharges storage')
    # PROTOTYPE placement and timing.
    ps = s['power_storage']
    require(ps['status'] == 'PROTOTYPE' and ps['unit'] == 'm', 'Storage placement stays PROTOTYPE')
    frames = ps['black_start_frames']
    require(len(frames) == 10 and frames[0] == 1 and all(a < b for a, b in zip(frames, frames[1:])) and frames[-1] < ps['black_start_end_frame'], 'Black-start frames: step 0..9, increasing')
    for p in packs(s):
        require(0 < p['r0'] < p['r1'] and p['x0'] < p['x1'] and p['width'] > 0, f"{p['name']}: box dimensions")
    require(len(ps['survival_packs']) >= 2, 'Survival reserve is distributed (at least two packs)')
    rows = clearances(s)
    for name, row in rows.items():
        require(row['passed'], f"{name}: clearance {min(row['member_gap_m'], row['cage_gap_m'], row['hull_gap_m'], row['pack_gap_m']):.3f} m")
    iso = isolation(s)
    require(iso['passed'], f"Survival packs closer than {iso['required_m']} m to main storage: {iso['separation_m']}")
    loads = {r['load'] for r in ride_through_points(s)}
    require(len(loads) == len(ps['ride_through_loads']), 'Ride-through loads unique')
    align = drive_alignment(s)
    require(align['passed'], f"WF_DRIVE_STARTUP does not follow the black-start steps: {align['steps']}")
    return dict(passed=not failures, failures=failures, quantities=q, clearances=rows, isolation=iso, drive_alignment=align)


def report(s):
    result = check(s); item = mass_allowance(s)
    return {'task': 'P1-007', 'scope': 'Sourced storage layers and black start; PROTOTYPE placement. No pack, generator, load or endurance sizing.',
            'passed': result['passed'], 'failures': result['failures'],
            'sourced': {k: {kk: vv for kk, vv in v.items() if not isinstance(vv, dict)} for k, v in s['power']['storage'].items() if isinstance(v, dict) and k != 'rules'},
            'derived': {k: {'value': v, 'status': 'DIAGNOSTIC' if 'mass' in k else 'DERIVED'} for k, v in result['quantities'].items()},
            'mass_allocation': {'budget_item': item['id'], 'allowance_kg': item['mass_kg'], 'rotating_kg': 0.0,
                                'extrapolated_main_pack_share': result['quantities']['main_battery_extrapolated_pack_mass_kg']/item['mass_kg'],
                                'note': 'Shares the allowance with computers, steering and comms; no new mass line and no installed pack mass.'},
            'open': sorted(k for k, v in {**{f'storage.{a}.{b}': c for a, t in s['power']['storage'].items() if isinstance(t, dict) for b, c in t.items() if isinstance(c, dict)},
                                          'power.rating': s['power']['rating'], 'power.hotel_source': s['power']['hotel_source'],
                                          'power.degraded_modes': s['power']['degraded_modes']}.items() if v.get('known') is False),
            'black_start': [{'step': x['step'], 'path': x['path'], 'reactor': x['reactor'], 'frame': s['power_storage']['black_start_frames'][x['step']], 'state': step_state(x['step'])} for x in s['power']['black_start']['steps']],
            'drive_alignment': result['drive_alignment'],
            'packs': [{'name': p['name'], 'layer': p['layer'], 'x_m': [p['x0'], p['x1']], 'angle_deg': math.degrees(p['angle']), 'radius_m': [p['r0'], p['r1']],
                       'width_m': p['width'], 'display_volume_m3': p['volume_m3'], 'status': 'PROTOTYPE'} for p in packs(s)],
            'clearances': result['clearances'], 'isolation': result['isolation'],
            'ride_through': [{'name': r['name'], 'at': list(r['at']), 'pairs_with': ':'.join(r['pairs_with'])} for r in ride_through_points(s)]}


if __name__ == '__main__':
    import spec
    data, _, _, _ = spec.load()
    OUTPUT.write_text(json.dumps(report(data), indent=1)+'\n')
    print('WF_POWER_STORAGE', 'PASS' if report(data)['passed'] else 'FAIL', OUTPUT)
