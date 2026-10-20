"""Local crew and object dynamics (PHYS-001): frames, the apparent-acceleration field, mode transitions, actor profiles and fixtures.

Owner: S&E 46_CREW_DYNAMICS DYN-001..022, 47_SIM_PRODUCTION, Technology 54_SPACE_MOTION_SIM. Sheets own every number: ring radius
and rpm (08), mode limits (11) and the mission state (26 C-001..018). This module only combines them for a local simulation; it never
solves a trajectory, times a transition or releases an EVA gate.

Frames (DYN-001, GEN-001/003), all in ship metres (+X bow, +Z dorsal):
  SHIP  ship-local, non-rotating (attitude rate not released, taken as 0). Field a = -a_ship. Spine, despun vestibule, airlock, EVA.
  RING  turning with ring k about +X through its centre. Field a = -w x (w x r) - 2 w x v - alpha x r - a_ship, with r measured from
        the ring centre. Collision geometry is static in this frame, so the pseudo-forces are the only rotation terms (no double count).
The Godot runtime evaluates the same field from the rig's `dynamics` block; tests compare both to fixtures().
Leaf module: standard library and the pure ring/layout modules only.
"""
import copy
import math
import habitat_ring
import crew_transfer
import human_entry

G0 = habitat_ring.G0
MODES = ('COAST', 'LOW_THRUST', 'HIGH_POWER', 'EVA', 'DOCKED')


# ---------- small vector helpers ----------------------------------------------------------------------------------------

def add(*vs): return tuple(sum(c) for c in zip(*vs))
def sub(a, b): return tuple(x-y for x, y in zip(a, b))
def mul(a, k): return tuple(x*k for x in a)
def dot(a, b): return sum(x*y for x, y in zip(a, b))
def norm(a): return math.sqrt(dot(a, a))
def cross(a, b): return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])


def rot_x(a, angle):
    c, s = math.cos(angle), math.sin(angle)
    return (a[0], c*a[1]-s*a[2], s*a[1]+c*a[2])


# ---------- sourced state -----------------------------------------------------------------------------------------------

def ring_sign(s, ring):
    rs = s['physics']['crew_dynamics']['ring_sign']
    return rs['ring_a'] if ring == 0 else rs['ring_b']


def ring_omega(s, ring, config):
    """Signed spin vector of ring k (0 = A, 1 = B) in a configuration: +-w about +X, zero when stopped and locked (11)."""
    spin = s['configuration'][config]['controls']['ring_spin']
    return (ring_sign(s, ring)*spin*habitat_ring.omega(s), 0.0, 0.0)


def ship_accel(s, config):
    """The ship's axial acceleration for a configuration (11). Drive OFF: zero, known. Drive ACTIVE: the actual value is a released
    channel (26 C-017, FRM-002; still OPEN), so only the mode's upper bound is given, as an envelope case for demonstration."""
    c = s['configuration'][config]
    if c['drive'] == 'OFF':
        return {'known': True, 'value_g': 0.0, 'kind': 'DRIVE_OFF', 'canon_status': c['canon_status'], 'source_ref': c['source_ref']}
    return {'known': False, 'envelope_g': float(c['max_accel_g']), 'kind': 'ENVELOPE_BOUND', 'canon_status': c['canon_status'],
            'source_ref': c['source_ref'], 'reason': 'the actual thrust history is a Sheets channel (26 C-017/C-018); the envelope bound '
            'is a demonstration case, not a flight value'}


def demo_ship_accel_g(s, config):
    """Value the demonstrator uses: zero with the drive off, else the envelope bound (SIMULATION_ONLY)."""
    a = ship_accel(s, config)
    return a['value_g'] if a['known'] else a['envelope_g']


# ---------- frames and field --------------------------------------------------------------------------------------------

def field(w, r, v=(0.0, 0.0, 0.0), alpha=(0.0, 0.0, 0.0), a_ship=(0.0, 0.0, 0.0)):
    """Apparent acceleration (m/s2) on a free body at r (from the frame origin on the spin axis) moving at v in a frame turning at w
    with angular acceleration alpha, aboard a ship accelerating at a_ship: centrifugal + Coriolis + Euler + thrust reaction."""
    centrifugal = mul(cross(w, cross(w, r)), -1.0)
    coriolis = mul(cross(w, v), -2.0)
    euler = mul(cross(alpha, r), -1.0)
    return add(centrifugal, coriolis, euler, mul(a_ship, -1.0))


def to_ring(r, v, centre_x, angle, w):
    """Ship-frame position and velocity -> ring frame of a ring at `angle` turning at w (both position and velocity, DYN-009)."""
    rel = sub(r, (centre_x, 0.0, 0.0))
    return rot_x(rel, -angle), rot_x(sub(v, cross(w, rel)), -angle)


def to_ship(r, v, centre_x, angle, w):
    """Inverse of to_ring."""
    rel = rot_x(r, angle)
    return add(rel, (centre_x, 0.0, 0.0)), add(rot_x(v, angle), cross(w, rel))


def push_dv(impulse_n_s, mass_kg):
    """DYN-010: delta-v = J/m."""
    return mul(impulse_n_s, 1.0/mass_kg)


def tether(p, v, anchor, length, mass_kg=1.0, dt=None):
    """DYN-025 / EVA-065 training tether (2.0 m PROTOTYPE, SIMULATION_ONLY): a unilateral, inextensible constraint. Slack (inside the
    sphere, or moving inward at the limit) it does nothing. Taut and moving outward it applies the impulse that cancels the outward
    radial speed (perfectly inelastic, PROTOTYPE: stiffness, damping and restitution OPEN): J = -m (v . n) n on the body, -J on the
    anchor. The position goes back onto the sphere (a projection, no momentum). Returns position, velocity, taut and the impulse record:
    impulse (N s, on the body), |J|, and the mean reaction force |J|/dt over the step when dt is given (rigid-limit value; the real
    peak depends on the OPEN stiffness, so it scales with the timestep)."""
    d = sub(p, anchor); dist = norm(d)
    rec = {'impulse_n_s': (0.0, 0.0, 0.0), 'impulse_mag_n_s': 0.0, 'anchor_force_n': 0.0, 'dt_s': dt}
    if dist <= length:
        return p, v, False, rec
    n = mul(d, 1.0/dist); out = dot(v, n)
    if out <= 0.0:
        return add(anchor, mul(n, length)), v, True, rec
    j = mul(n, -mass_kg*out)
    rec |= {'impulse_n_s': j, 'impulse_mag_n_s': mass_kg*out, 'anchor_force_n': mass_kg*out/dt if dt else None}
    return add(anchor, mul(n, length)), add(v, mul(j, 1.0/mass_kg)), True, rec


# ---------- spin ramp (DYN-026, WORKING scenario) -----------------------------------------------------------------------

def spin_ramp(s, ring, t, down=True):
    """Signed ring spin (rad/s about +X) and angular acceleration at t seconds into the WORKING constant-alpha ramp:
    w(t) = sign w0 max(0, 1 - t/T) spinning down (DYN-026), sign w0 min(1, t/T) spinning up; T = 08 spin_time (study value, not an
    event time). alpha is zero outside the ramp."""
    T = s['physics']['rotor_operations']['spin_up_time_s']; w0 = ring_sign(s, ring)*habitat_ring.omega(s)
    f = min(max(t/T, 0.0), 1.0); running = 0.0 <= t < T
    w = w0*(1.0-f) if down else w0*f
    a = (-w0/T if down else w0/T) if running else 0.0
    return (w, 0.0, 0.0), (a, 0.0, 0.0)


# ---------- rotary vestibule (DYN-027) ----------------------------------------------------------------------------------

def vestibule_gate(side, drum_w, side_w, restrained, closures, dp_equalized, ramping, tol=None):
    """May the closure on `side` ('STATIONARY' or 'RING') open? DYN-027 / MEC-019: the occupant is restrained while the drum changes
    speed; both independent boundaries stay closed during synchronization and are never open together; only the side whose angular
    speed the drum matches opens, and only with the pressure equalized (the threshold is OPEN, so this is an input flag). `closures`
    maps side -> closed. tol defaults to the rig's rpm match tolerance. Fail closed: any unknown input refuses."""
    other = 'RING' if side == 'STATIONARY' else 'STATIONARY'
    if ramping:
        return {'open': False, 'reason': 'drum changing speed: both boundaries stay closed' + ('' if restrained else '; occupant NOT restrained')}
    if not closures.get(other, False):
        return {'open': False, 'reason': f'{other.lower()} closure is open: never both open'}
    if tol is None or drum_w is None or side_w is None:
        return {'open': False, 'reason': 'angular speeds or tolerance unknown (fail closed)'}
    if abs(drum_w - side_w) > tol:
        return {'open': False, 'reason': f'drum {drum_w:+.5f} rad/s does not match the {side.lower()} side {side_w:+.5f} rad/s'}
    if dp_equalized is not True:
        return {'open': False, 'reason': 'pressure not shown equalized (threshold OPEN, PRESS-004)'}
    return {'open': True, 'reason': f'matched to the {side.lower()} side, pressure equalized, other boundary closed'}


def vestibule_ramp_allowed(restrained, closures):
    """The drum may change speed only with the occupant restrained and both boundaries closed (DYN-027)."""
    if not restrained:
        return {'allowed': False, 'reason': 'occupant not restrained'}
    if not all(closures.get(k, False) for k in ('STATIONARY', 'RING')):
        return {'allowed': False, 'reason': 'a boundary is open'}
    return {'allowed': True, 'reason': 'restrained, both boundaries closed'}


# ---------- operating-mode transitions (SIMULATION_ONLY, untimed) ------------------------------------------------------

RAMP_STEPS = ('RINGS_SPIN_DOWN', 'RINGS_SPIN_UP')


def transition(s, a, b):
    """Ordered steps from configuration a to b. The ring steps follow the owner's simulation sequence (46 DYN-026, 15 CREW-MODE-004,
    WORKING scenario / flight event OPEN): main propulsion OFF -> occupants secured -> both rings decelerate -> rings locked -> HIGH_POWER
    permissible; the reverse unlocks and spins up with the drive off and the occupants secured. A ring ramp with the drive on (the
    <= 0.1 g concurrent case) is unreleased and never generated. Every result is SIMULATION_ONLY; only the ramps carry the WORKING
    study duration, no event time. Refused: unknown or unbuildable states."""
    cfg = s['configuration']
    if a not in MODES or b not in MODES or not cfg[a].get('buildable') or not cfg[b].get('buildable'):
        return {'allowed': False, 'steps': [], 'status': 'REFUSED', 'reason': f'{a} -> {b}: not a buildable operating configuration'}
    if a == b:
        return {'allowed': True, 'steps': [], 'status': 'SIMULATION_ONLY'}
    ca, cb = cfg[a], cfg[b]; steps = []
    ramp = ca['habitat'] != cb['habitat']
    if a == 'DOCKED':
        steps.append('UNDOCK')            # an external event, not modelled
    if ca['drive'] == 'ACTIVE' and (cb['drive'] == 'OFF' or ramp):
        steps.append('DRIVE_OFF')         # no ring ramp under thrust (concurrent low-thrust ramp unreleased, DYN-026)
    if ramp:
        steps.append('OCCUPANTS_SECURED')
    if ca['habitat'] == 'ROTATING' and cb['habitat'] == 'STOPPED_LOCKED':
        steps += ['RINGS_SPIN_DOWN', 'RINGS_LOCKED']
    if ca['habitat'] == 'STOPPED_LOCKED' and cb['habitat'] == 'ROTATING':
        steps += ['RINGS_UNLOCKED', 'RINGS_SPIN_UP']
    if b == 'DOCKED':
        steps.append('DOCK')
    if cb['drive'] == 'ACTIVE':
        steps.append('DRIVE_ON')
    return {'allowed': True, 'steps': steps, 'status': 'SIMULATION_ONLY', 'timed': False, 'sequence_source': '46 DYN-026 / 15 CREW-MODE-004',
            'ramp': {'known': False, 'study_value_s': s['physics']['rotor_operations']['spin_up_time_s'],
                     'reason': '08 spin_time 1800 s WORKING; 46 DYN-026: WORKING scenario, flight event OPEN; no First Ignition timestamp'}}


def ramp_allowed(drive_on, occupants_secured):
    """A ring ramp may run only with the drive off and the occupants secured (DYN-026); the concurrent low-thrust ramp is unreleased."""
    if drive_on:
        return {'allowed': False, 'reason': 'drive on: a ring ramp under thrust (<= 0.1 g concurrent case) is not released (DYN-026)'}
    if not occupants_secured:
        return {'allowed': False, 'reason': 'occupants not secured'}
    return {'allowed': True, 'reason': 'drive off, occupants secured'}


# ---------- actor profiles ----------------------------------------------------------------------------------------------

def profiles(s):
    return {k: dict(v) for k, v in s['physics']['crew_dynamics']['profiles'].items()}


# ---------- state-gated navigation graph (DYN-018, SIM-005) -------------------------------------------------------------

def _technique(mode_cfg, frame):
    """Locomotion an edge needs in a configuration: hand over hand in microgravity, ladders when a gravity field acts along it."""
    spin = mode_cfg['habitat'] == 'ROTATING'; thrust = mode_cfg['drive'] == 'ACTIVE'
    if frame.startswith('RING') and spin:
        return 'LADDER_RADIAL'              # spin gravity along the crew tube
    if thrust:
        return 'LADDER_AFT_DOWN'            # HIGH_POWER / LOW_THRUST on the stationary structure: aft is down (DYN-008)
    return 'HAND_OVER_HAND'


def nav(s):
    """Topological graph over the crew_transfer passages plus the suited EVA path (eva_suit.toml suited_route). Each edge names its
    frame, pressure boundary, rotating interface, allowed actors and modes; the locomotion technique is resolved per mode. Gates are
    PROTOTYPE route logic, not qualification: the casualty query always answers HOLD (DYN-020)."""
    edges_in, _ = crew_transfer.graph(s); edges = []
    everyone, unsuited = ['human_iva', 'seraph'], ['human_iva', 'seraph']
    for a, b in edges_in:
        e = {'from': a, 'to': b, 'frame': 'SHIP', 'pressure_boundary': None, 'rotating_interface': False, 'actors': everyone, 'modes': list(MODES)}
        if b.startswith('VESTIBULE_'):
            e |= {'pressure_boundary': 'PORT_GATE', 'rotating_interface': True,
                  'gate': 'drum synchronized with its ring or both stopped at the index; both closures of the crossing closed behind (DYN-009)'}
        elif b.startswith('SECTOR_'):
            e |= {'frame': f'RING_{"AB"[int(b.split("_")[1])-1]}', 'pressure_boundary': 'SECTOR_LEAF', 'via': 'crew tube'}
        elif b.startswith('DOCK_'):
            e |= {'pressure_boundary': 'DOCK_HATCH', 'modes': ['DOCKED']}
        elif b == 'AIRLOCK_EVA':
            e |= {'pressure_boundary': 'AIRLOCK_INNER'}
        else:
            e |= {'pressure_boundary': 'HATCH'}
        edges.append(e)
    edges += [{'from': 'TRUNK', 'to': 'SP12', 'frame': 'SHIP', 'pressure_boundary': None, 'rotating_interface': False, 'actors': everyone,
               'modes': list(MODES), 'note': 'suit donning room (EVA-002 SP-12, PROTOTYPE placement); human_iva <-> human_suited here'},
              {'from': 'SP12', 'to': 'AIRLOCK_EVA', 'frame': 'SHIP', 'pressure_boundary': 'AIRLOCK_INNER', 'rotating_interface': False,
               'actors': ['human_suited'], 'modes': list(MODES)},
              {'from': 'AIRLOCK_EVA', 'to': 'EVA_EXTERIOR', 'frame': 'SHIP', 'pressure_boundary': 'AIRLOCK_OUTER', 'rotating_interface': False,
               'actors': ['human_suited'], 'modes': ['EVA'], 'status': 'SIMULATION_ONLY; FLIGHT_EVA HOLD (DYN-013)',
               'gate': 'chamber depressurized, inner hatch closed, two tethers clipped (eva.gd phases)'}]
    techniques = {m: [_technique(s['configuration'][m], e['frame']) for e in edges] for m in MODES}
    nodes = sorted({e['from'] for e in edges} | {e['to'] for e in edges})
    return {'nodes': nodes, 'edges': edges, 'technique_by_mode': techniques, 'canon_status': 'PROTOTYPE',
            'basis': 'crew_transfer.graph passages and the suited EVA route; actor envelopes OPEN (DYN-019); suited bodies stay off the '
                     'crew tubes and ring sectors, whose clearances are checked for the unsuited envelope only (EVA-002)',
            'casualty': {'result': 'HOLD', 'source': 'DYN-020 / HUM-002', 'reason': 'no qualified casualty clearance; a route the walking '
                         'mannequin passes is not a rescue route'}}


def route(graph, start, goal, mode, actor, closed=()):
    """Fewest-edge route for an actor in a mode; a closed boundary or a disallowed mode/actor removes the edge (DYN-018 I19)."""
    adj = {}
    for i, e in enumerate(graph['edges']):
        if mode in e['modes'] and actor in e['actors'] and (e['pressure_boundary'] is None or f"{e['from']}-{e['to']}" not in closed):
            adj.setdefault(e['from'], []).append((e['to'], i)); adj.setdefault(e['to'], []).append((e['from'], i))
    prev, todo = {start: None}, [start]
    while todo:
        n = todo.pop(0)
        if n == goal:
            path = [n]
            while prev[path[-1]]:
                path.append(prev[path[-1]][0])
            return path[::-1]
        for m, i in adj.get(n, ()):
            if m not in prev:
                prev[m] = (n, i); todo.append(m)
    return None


# ---------- fixtures (DYN-022) ------------------------------------------------------------------------------------------

def fixtures(s):
    """Expected values every runtime must reproduce, with their owner rows. Ring fixtures use a body on the floor straight 'below'
    the axis in the ring frame, r = (0, 0, -R), and a 1 m/s velocity along +Y (tangential there) or +Z (radial)."""
    R = habitat_ring.floor(s); w = habitat_ring.omega(s); g = G0
    out = []
    for k, name in ((0, 'A'), (1, 'B')):
        wv = ring_omega(s, k, 'COAST')
        floor_a = field(wv, (0.0, 0.0, -R))
        head_a = field(wv, (0.0, 0.0, -(R-2.0)))
        cor_t = field(wv, (0.0, 0.0, 0.0), (0.0, 1.0, 0.0))
        cor_r = field(wv, (0.0, 0.0, 0.0), (0.0, 0.0, 1.0))
        out += [
            {'id': f'RING_{name}_FLOOR', 'ring': k, 'config': 'COAST', 'r': [0.0, 0.0, -R], 'v': [0.0, 0.0, 0.0], 'expect': list(floor_a),
             'expect_g': norm(floor_a)/g, 'source': 'DYN-002 / 08 floor_g', 'status': 'BASELINE'},
            {'id': f'RING_{name}_HEAD', 'ring': k, 'config': 'COAST', 'r': [0.0, 0.0, -(R-2.0)], 'v': [0.0, 0.0, 0.0], 'expect': list(head_a),
             'expect_g': norm(head_a)/g, 'source': 'DYN-004 / 08 head_g', 'status': 'DERIVED'},
            {'id': f'RING_{name}_CORIOLIS_TANGENTIAL', 'ring': k, 'config': 'COAST', 'r': [0.0, 0.0, 0.0], 'v': [0.0, 1.0, 0.0],
             'expect': list(cor_t), 'expect_g': norm(cor_t)/g, 'source': 'DYN-003', 'status': 'REAL PHYSICS'},
            {'id': f'RING_{name}_CORIOLIS_RADIAL', 'ring': k, 'config': 'COAST', 'r': [0.0, 0.0, 0.0], 'v': [0.0, 0.0, 1.0],
             'expect': list(cor_r), 'expect_g': norm(cor_r)/g, 'source': 'DYN-003', 'status': 'REAL PHYSICS'}]
    lt = demo_ship_accel_g(s, 'LOW_THRUST')*g
    tilt = field(ring_omega(s, 0, 'LOW_THRUST'), (0.0, 0.0, -R), a_ship=(lt, 0.0, 0.0))
    out.append({'id': 'LOW_THRUST_TILT', 'ring': 0, 'config': 'LOW_THRUST', 'r': [0.0, 0.0, -R], 'v': [0.0, 0.0, 0.0], 'a_ship_g': lt/g,
                'expect': list(tilt), 'expect_tilt_deg': math.degrees(math.atan2(-tilt[0], -tilt[2])), 'source': 'DYN-005 / 11 LOW_THRUST',
                'status': 'WORKING'})
    hp = demo_ship_accel_g(s, 'HIGH_POWER')*g
    for k in (0, 1):
        locked = field(ring_omega(s, k, 'HIGH_POWER'), (0.0, 0.0, -R), a_ship=(hp, 0.0, 0.0))
        out.append({'id': f'HIGH_POWER_RING_{"AB"[k]}_LOCKED', 'ring': k, 'config': 'HIGH_POWER', 'r': [0.0, 0.0, -R], 'v': [0.0, 0.0, 0.0],
                    'a_ship_g': hp/g, 'expect': list(locked), 'source': 'DYN-006 / DYN-008 / 11 HIGH_POWER', 'status': 'BASELINE'})
    out.append({'id': 'SPINE_COAST_DRIFT', 'zone': 'SHIP', 'config': 'COAST', 'r': [0.0, 0.0, 0.0], 'v': [0.3, 0.0, 0.0],
                'expect': [0.0, 0.0, 0.0], 'source': 'DYN-007', 'status': 'REAL PHYSICS'})
    out.append({'id': 'SPINE_HIGH_POWER_AFT_DOWN', 'zone': 'SHIP', 'config': 'HIGH_POWER', 'r': [0.0, 0.0, 0.0], 'v': [0.0, 0.0, 0.0],
                'a_ship_g': hp/g, 'expect': [-hp, 0.0, 0.0], 'source': 'DYN-008', 'status': 'BASELINE'})
    T = s['physics']['rotor_operations']['spin_up_time_s']
    for k in (0, 1):
        w, a = spin_ramp(s, k, 0.0)
        out.append({'id': f'SPIN_DOWN_RING_{"AB"[k]}_EULER', 'ring': k, 'config': 'COAST', 'r': [0.0, 0.0, -R], 'v': [0.0, 0.0, 0.0],
                    't_s': 0.0, 'alpha': list(a), 'expect_euler': list(mul(cross(a, (0.0, 0.0, -R)), -1.0)),
                    'expect': list(field(w, (0.0, 0.0, -R), alpha=a)), 'ramp_s': T, 'source': 'DYN-026 / 08 alpha', 'status': 'WORKING SCENARIO'})
    m = s['physics']['crew_dynamics']['profiles']
    import eva_suit
    L = eva_suit.load()['route']['tether_reach_m']    # 2.0 m PROTOTYPE training length (DYN-025)
    for name in ('human_iva', 'human_suited'):
        mass = m[name]['mass_kg']; v0 = m[name]['test_push_dv_m_s']
        _, v1, _, rec = tether((L+0.01, 0.0, 0.0), (v0, 0.2, 0.0), (0.0, 0.0, 0.0), L, mass, 1.0/60.0)
        out.append({'id': f'TETHER_{name.upper()}', 'zone': 'SHIP', 'config': 'EVA', 'mass_kg': mass, 'length_m': L, 'p': [L+0.01, 0.0, 0.0],
                    'v': [v0, 0.2, 0.0], 'dt_s': 1.0/60.0, 'expect_v': list(v1), 'expect_impulse_n_s': list(rec['impulse_n_s']),
                    'expect_anchor_force_n': rec['anchor_force_n'], 'source': 'DYN-025 / EVA-065', 'status': 'SIMULATION_ONLY'})
    for name in ('human_iva', 'human_suited'):
        out.append({'id': f'PUSH_{name.upper()}', 'zone': 'SHIP', 'config': 'COAST', 'mass_kg': m[name]['mass_kg'], 'impulse_n_s': [0.0, 30.0, 0.0],
                    'expect_dv': list(push_dv((0.0, 30.0, 0.0), m[name]['mass_kg'])), 'source': 'DYN-010', 'status': 'PROTOTYPE'})
    return out


def tube_stage(s):
    """The induction sector's crew tube on ring A (RING frame, vehicle frame at the index pose = ring-frame coordinates): the radial run's axis
    from the bend to the sector hatch seat, its clear radius, the ladder rungs of the run (human_entry.spoke_fixtures) and of the landing well
    below the hatch (human_entry.landing_fixtures, sector frame mapped by human_entry.sector_frame), all on the one deck-referenced rung grid,
    the direction from the axis toward the ladder and the climber's offset along it (the body axis on the ladder, human_entry mannequin)."""
    h = s['human_entry']; m = h['mannequin']; j = h['tube_rotors'][0]
    rot, k, point, _ = human_entry.sector_frame(s)
    rot_t, _, _, frames = human_entry.spoke_station(s, j)
    fr = frames[k]; R = human_entry.RUN
    p0 = human_entry.at_index(rot_t, fr['points'][R]); d = human_entry.at_index(rot_t, fr['d'][R], False)
    t1 = human_entry.run_span(s, fr)[1]
    end = crew_transfer.add(p0, d, t1)
    name = f"Crew_Tube_{rot_t['index']}_{k}"
    tube = next(q for q in human_entry.spoke_fixtures(s, j) if q['name'] == f'{name}_Ladder_Rungs')
    well = next(q for q in human_entry.landing_fixtures(s) if q['name'] == 'Sector_Ladder_Rungs')
    rungs = [[human_entry.at_index(rot_t, a), human_entry.at_index(rot_t, b)] for a, b in tube['segments']]
    rungs += [[point(a), point(b)] for a, b in well['segments']]
    rungs.sort(key=lambda r: crew_transfer.dot(crew_transfer.sub(r[0], p0), d))
    mid = [tuple((a[i]+b[i])/2 for i in range(3)) for a, b in rungs[:1]][0]
    off = crew_transfer.sub(mid, crew_transfer.add(p0, d, crew_transfer.dot(crew_transfer.sub(mid, p0), d)))
    n = math.sqrt(crew_transfer.dot(off, off))
    return {'frame': 'RING', 'ring': 0, 'zone': 'tube', 'sector': k, 'axis_m': [list(p0), list(end)],
            'clear_radius_m': crew_transfer.tube_radii(s, j)[1], 'toward_ladder': [c/n for c in off], 'ladder_axis_offset_m': n,
            'climber_offset_m': m['spoke_body_offset_m'], 'review_speed_m_s': m['climb_review_speed_m_s'], 'rung_pitch_m': h['spoke_rung_pitch_m'],
            'rungs': [{'anchor_id': f'{name}_Rung_{i+1}' if i < len(tube['segments']) else f'Sector_Ladder_Rung_{i+1-len(tube["segments"])}',
                       'role': 'ladder rung', 'radius_m': tube['radius'], 'rail_start': list(a), 'rail_end': list(b)} for i, (a, b) in enumerate(rungs)],
            'landing_room': 'WF.ROOM.A1.LANDING_WELL',
            'source': 'human_entry.spoke_fixtures / landing_fixtures / sector_frame, crew_transfer.tube_radii', 'status': 'PROTOTYPE geometry',
            'note': 'rungs sorted outward along the run (the tube rungs, then the landing-well rungs); the tube is open into the landing well at the '
                    'hatch seat; the bend and elbows above the run are not a stage (the body enters at the run top)'}


ACCESS_MARGIN_M = 0.10    # PROTOTYPE: least wall clearance of the rigid body proxy on the access line (route checks use the 0.35 m sphere)
ACCESS_START_M = 2.0      # PROTOTYPE stage boundary: the body starts on the trunk axis this far forward of the spine port, head aft
ACCESS_GRID = (0.05, 5)   # IMPLEMENTATION: pose grid of the pivot search (m, deg)
ACCESS_STEP_M = 0.1       # IMPLEMENTATION: waypoint spacing of the body through the elbows
ACCESS_GRIP_ZONE_M = 0.10  # PROTOTYPE technique: before the sync each corner of the line has a grip in reach this far of line either side
                           # (the hands catch and push off there); between corners the body coasts with no hand force (zero field)
cadd = crew_transfer.add   # (a, b, k) -> a + k b
TRUNK_GRIPS = ('trunk handrail', 'refuge port handrail', 'storeroom port handrail')


def _access_world(s):
    """Rotor-local (u, a, b) free-space model of ring A's induction access at the index (the spine port and the sector-1 crew tube both on +a):
    the trunk bore, the spine port's bore (port clear radius about the radial at hatch_u), the drum annulus (r0..clear, cu0..cu1), the drum
    door's bore through the running gap into the crew tube (the same radial and radius) and the mitered tube (crew_transfer.tube_radius_at).
    clear(p, port, door) is a lower bound of the distance from p to the walls with the port gate / drum door open or shut (the largest of the
    region clearances)."""
    rot, v, la, frames = human_entry.spoke_station(s); fr = frames[s['human_entry']['vestibule_port_sectors'][0]]
    trunk = crew_transfer.stationary(s)[0]; tr = trunk['hollow']; u_tr = sorted(q[0]-rot['x'] for q in trunk['points'])
    hu, pc, r0, R, cu0, cu1 = v['hatch_u'], v['port_clear'], v['r0'], v['clear'], v['cu0'], v['cu1']
    rc = crew_transfer.tube_radii(s, rot['index'])[1]; j1 = fr['points'][1]

    def clear(p, port, door):
        u, a, b = p; rho = math.hypot(a, b); lat = math.hypot(u-hu, b); best = -9.0
        if u_tr[0] < u < u_tr[1]:
            best = max(best, tr-rho)
        if port and a >= 0.0:
            best = max(best, min(pc-lat, 9.0 if door else R-rho))
        if cu0 < u < cu1 and r0 < rho < R:
            best = max(best, min(rho-r0, R-rho, u-cu0, cu1-u))
        if door and a >= 0.0:
            beyond = dot(sub(p, j1), fr['miter'][1])
            if beyond <= 0.0:
                best = max(best, min(pc-lat, 9.0 if port else a-r0, rc-beyond))
            best = max(best, rc-crew_transfer.tube_radius_at(fr, p))
        return best
    return dict(rot=rot, v=v, fr=fr, clear=clear, u_tr=u_tr, trunk_r=tr, tube_r=rc)


def _seg_dist(p, a, b):
    # Distance from point p to segment ab (3-D). Written out (the hot loop of the access search), with the operations in the order of
    # norm(sub(p, cadd(a, sub(b, a), f))) so the floats are identical.
    a0, a1, a2 = a; b0, b1, b2 = b; p0, p1, p2 = p
    u0, u1, u2 = b0-a0, b1-a1, b2-a2
    f = max(0.0, min(1.0, ((p0-a0)*u0+(p1-a1)*u1+(p2-a2)*u2)/max(u0*u0+u1*u1+u2*u2, 1e-12)))
    d0, d1, d2 = p0-(a0+f*u0), p1-(a1+f*u1), p2-(a2+f*u2)
    return math.sqrt(d0*d0+d1*d1+d2*d2)


def _capsule_clear(w, c, up, port, door, half, radius, n=16):
    return min(w['clear'](add(c, mul(up, half*(2*k/n-1))), port, door) for k in range(n+1))-radius


def _nlerp(a, b, f):
    v = add(mul(a, 1-f), mul(b, f)); return mul(v, 1/norm(v))


def _segment_clear(w, p, q, port, door, half, radius):
    """Least capsule clearance along the straight move from pose p to pose q (centre lerp, axis nlerp), sampled every 0.02 m and 1 deg."""
    turn = math.degrees(math.acos(max(-1.0, min(1.0, dot(p[1], q[1])))))
    n = max(1, math.ceil(max(norm(sub(q[0], p[0]))/0.02, turn)))
    return min(_capsule_clear(w, add(mul(p[0], 1-k/n), mul(q[0], k/n)), _nlerp(p[1], q[1], k/n), port, door, half, radius) for k in range(n+1))


def _span(p, q, H):
    """Line-parameter length of the straight move p -> q (the larger of the centre travel and the end travel, H the body height)."""
    return max(norm(sub(q[0], p[0])), H/2*math.acos(max(-1.0, min(1.0, dot(p[1], q[1])))))


def _along(p, q, f):
    return add(mul(p[0], 1-f), mul(q[0], f)), _nlerp(p[1], q[1], f)


def _zone(p, q, at_end, held, H):
    """A grip in reach over ACCESS_GRIP_ZONE_M of line from the start (or the end) of the straight move p -> q."""
    f = min(1.0, ACCESS_GRIP_ZONE_M/max(_span(p, q, H), 1e-9))
    return all(held(_along(p, q, 1-f*k/8 if at_end else f*k/8)) for k in range(9))


def _kept(p, q, always, H):
    """always(pose) at every 0.01 m of line along the straight move p -> q."""
    n = max(1, math.ceil(_span(p, q, H)/0.01)); return all(always(_along(p, q, k/n)) for k in range(n+1))


def _pivot(w, base, e1, e2, u0, u1, start, goal, port, door, half, radius, held=None, always=None):
    """Breadth-first search on the pose grid (centre base + i e1 + j e2 on ACCESS_GRID, body axis cos(k) u0 + sin(k) u1) for a move from start
    to goal that keeps ACCESS_MARGIN_M everywhere, then shortcut: the fewest poses whose straight moves keep the margin. With held(pose)
    (a grip in reach), every corner has a grip in reach ACCESS_GRIP_ZONE_M of line either side, so the body can coast between corners; with
    always(pose) (in a field), a grip is in reach at every pose of the move."""
    import collections
    st, dg = ACCESS_GRID
    def pose(n):
        k = math.radians(n[2]*dg); return (cadd(cadd(base, e1, n[0]*st), e2, n[1]*st), add(mul(u0, math.cos(k)), mul(u1, math.sin(k))))
    ok = lambda n: _capsule_clear(w, *pose(n), port, door, half, radius) >= ACCESS_MARGIN_M and (always is None or always(pose(n)))
    prev, q = {start: None}, collections.deque([start])
    while q and goal not in prev:
        n = q.popleft()
        for d in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)):
            m = (n[0]+d[0], n[1]+d[1], n[2]+d[2])
            if m not in prev and abs(m[0]) <= 80 and abs(m[1]) <= 80 and -36 <= m[2] <= 72:
                prev[m] = n
                if ok(m):
                    q.append(m)
    if goal not in prev:
        raise ValueError(f'access: no move {start} -> {goal} keeps {ACCESS_MARGIN_M} m')
    path = [goal]
    while prev[path[-1]] is not None:
        path.append(prev[path[-1]])
    path = [pose(n) for n in reversed(path)]; out = [path[0]]; i = 0; H = 2*(half+radius)
    def good(i, j):
        if held is not None and not (_zone(path[i], path[j], False, held, H) and _zone(path[i], path[j], True, held, H)):
            return False
        if always is not None and not _kept(path[i], path[j], always, H):
            return False
        return _segment_clear(w, path[i], path[j], port, door, half, radius) >= ACCESS_MARGIN_M
    while i < len(path)-1:
        j = len(path)-1
        while j > i+1 and not good(i, j):
            j -= 1
        if held is not None and not good(i, j):
            raise ValueError(f'access: no grip in reach to push off or catch at {tuple(round(x, 3) for x in path[i][0])}')
        out.append(path[j]); i = j
    return out


_ACCESS = {}


def access_stage(s):
    """Cached access_stage_of(s) (the pose search takes seconds; the rig, the tests and the checks ask for it many times)."""
    import hashlib, json
    key = hashlib.sha256(json.dumps(s, sort_keys=True, default=str).encode()).hexdigest()
    if key not in _ACCESS:
        _ACCESS.clear()
        _ACCESS[key] = access_stage_of(s)
    return copy.deepcopy(_ACCESS[key])


def access_stage_of(s):
    """M2 contiguous body path: ring A's induction access from the stationary trunk through the spine port, the despun drum (synchronized while
    the occupant is restrained, DYN-027) and the drum door to the crew tube, through its mitered elbows to the top of the radial run, where
    tube_stage's climber line starts. The body proxy is rigid (the profile's capsule), so the line is derived for it: head aft along the trunk
    axis from ACCESS_START_M forward of the port, a turn head-first to radial at the trunk rails' end, a push-off and a coast out through the
    port's bore (no grip in reach there; the field is zero before the sync) to a catch in the drum, and a pivot onto the vestibule figure's
    chord, a hand on the rail beside the port (human_entry.vestibule_mannequin; both closures shut there: the restraint pose); after the sync (ring A's
    field) a grip in reach at every pose: along the rail aft, a pivot feet-first to radial, forward along the door's bore, the body's ends on the
    tube axis through the elbows (nudged toward a grip where the axis has none in reach), then a step onto the climber line. Each pivot is the fewest straight moves that keep ACCESS_MARGIN_M from the
    walls (a search on the pose grid; a technique choice, PROTOTYPE). Godot gets the collider geometry and the line in the vehicle frame at the
    index (RING frame coordinates; before the sync the drum frame is the SHIP frame at the index)."""
    w = _access_world(s); rot, v, fr = w['rot'], w['v'], w['fr']; h = s['human_entry']
    prof = profiles(s)['human_iva']; half, radius = prof['height_m']/2-prof['radius_m'], prof['radius_m']
    st = ACCESS_GRID[0]; hu = v['hatch_u']; A = (0.0, 1.0, 0.0); B = (0.0, 0.0, 1.0); X = (1.0, 0.0, 0.0); aft = (-1.0, 0.0, 0.0)
    # the restraint pose: the vestibule figure's (human_entry.vestibule_mannequin: on a chord, a hand on the rail beside the port), on the grid
    tor = next(r for r in human_entry.vestibule_mannequin(s)['local'] if r[0].endswith('_Torso')); H = s['prototype']['human_height_m']
    ax = crew_transfer.unit(sub(tor[1][1], tor[1][0])); c = cadd(tor[1][0], ax, 0.12*H)
    hold_pose = (round(c[1]/st), round(c[2]/st), round(math.degrees(math.atan2(ax[2], ax[1]))/ACCESS_GRID[1]))
    # the grips on the way, rotor-local: the trunk's rails and the drum's and tube's rails, stiles and rungs; held(pose): one in reach of the centre
    tube = tube_stage(s); inv = dict(rot, x=-rot['x'], phase=-rot['phase']); fix = []
    for q in human_entry.trunk_fixtures(s):
        if q.get('role') in TRUNK_GRIPS:
            fix.append((q, [tuple(human_entry.at_index(inv, a) for a in q['points'])]))
    for q in human_entry.vestibule_fixtures(s)+human_entry.spoke_fixtures(s):
        if q['name'].startswith(f"Crew_Tube_{rot['index']}_{tube['sector']}_") or q['name'].startswith(f"Crew_Vestibule_{rot['index']}_"):
            if q['shape'] == 'rod' and ('handrail' in q['role'] or 'stile' in q['role'] or 'crawl rail' in q['role']) and 'bracket' not in q['role']:
                fix.append((q, list(zip(q['points'], q['points'][1:]))))
            elif q['shape'] == 'rods' and 'floor ladder rungs' in q['role']:
                fix.append((q, q['segments']))
    gl = [g for _, segs in fix for g in segs]; reach = prof['reach_m']-0.01
    held = lambda p: any(_seg_dist(p[0], a, b) <= reach for a, b in gl)      # min(...) <= reach, stopping at the first grip in reach
    # Before the sync (zero field) the hands act only where a grip is in reach (_pivot held); the spine port's bore has none (its mouth spans
    # the drum's inner wall), so the body crosses it in one coast: from a junction J (radial, head out, at the trunk rails' end on the
    # port's forward side) to a catch pose C in the drum (axis across the port's radial, a grip in reach), the straight move keeping the
    # margin; from C a gripped pivot into the restraint pose shifted to C's station, then along the rail onto the figure's station.
    def free(p):
        return _capsule_clear(w, *p, True, False, half, radius) >= ACCESS_MARGIN_M
    Js = [(k, i) for k in range(round(v['port_clear']/st)) for i in range(round(v['r0']/st)+1)
          if held((cadd((hu+k*st, 0.0, 0.0), A, i*st), A)) and free((cadd((hu+k*st, 0.0, 0.0), A, i*st), A))]
    Cs = [(du, ia, ib, kk) for du in range(-6, 11, 2) for ia in range(round(v['r0']/st)+1, round(v['clear']/st)) for ib in range(-4, 25, 2)
          for kk in range(0, 72, 3)]
    pairs = []
    for du, ia, ib, kk in Cs:
        C = ((hu+du*st, ia*st, ib*st), add(mul(A, math.cos(math.radians(kk*ACCESS_GRID[1]))), mul(B, math.sin(math.radians(kk*ACCESS_GRID[1])))))
        if not held(C) or not free(C):
            continue
        for k, i in Js:
            J = ((hu+k*st, i*st, 0.0), A)
            if not (_zone(J, C, False, held, prof['height_m']) and _zone(J, C, True, held, prof['height_m'])):
                continue
            c_ = _segment_clear(w, J, C, True, False, half, radius)
            if c_ >= ACCESS_MARGIN_M:
                pairs.append((-c_, k, i, du, ia, ib, kk))
    turns = {}
    for _, k, i, du, ia, ib, kk in sorted(pairs):
        try:
            if (k, i) not in turns:
                turns[k, i] = _pivot(w, (hu, 0.0, 0.0), X, A, aft, A, (round(ACCESS_START_M/st), 0, 0), (k, i, 18), True, False, half, radius, held)
            if turns[k, i] is None:
                continue
            into = _pivot(w, (hu+du*st, 0.0, 0.0), A, B, A, B, (ia, ib, kk), hold_pose, True, False, half, radius, held)
            turn = turns[k, i]
            break
        except ValueError:
            turns.setdefault((k, i), None)
    else:
        raise ValueError('access: no coast across the spine port with a grip at both ends')
    shift = []
    if du:
        p0 = into[-1]; shift = [((hu, p0[0][1], p0[0][2]), p0[1])]
        if not held(shift[0]) or _segment_clear(w, p0, shift[0], True, False, half, radius) < ACCESS_MARGIN_M:
            raise ValueError('access: the restraint pose is not reached along the rail')
    # After the sync the drum carries ring A's field, so a grip stays in reach at every pose out through the door (_pivot always): along the
    # handrail from the restraint pose to the nearest station aft where such a pivot exists (the crawl rail then stays in reach to the door's
    # mouth), the pivot feet-first to radial there, then forward along the door's bore to its axis.
    a_out = math.ceil((v['r0']+half+radius+ACCESS_MARGIN_M)/st-1e-9); H = prof['height_m']
    for dk in range(0, -round(v['port_clear']/st), -1):
        try:
            out = _pivot(w, (hu+dk*st, 0.0, 0.0), A, B, A, B, hold_pose, (a_out, 0, 36), False, True, half, radius, always=held)
        except ValueError:
            continue
        if dk:
            out = [((hu, *out[0][0][1:]), out[0][1])]+out+[((hu, *out[-1][0][1:]), out[-1][1])]
        if all(_kept(p, q, held, H) and _segment_clear(w, p, q, False, True, half, radius) >= ACCESS_MARGIN_M for p, q in (out[:2], out[-2:])):
            break
    else:
        raise ValueError('access: no pivot out through the drum door keeps a grip in reach')
    line = [dict(p=p, up=u, phase='trunk') for p, u in turn]+[dict(p=p, up=u, phase='port') for p, u in into+shift]
    hold = len(line)-1; line[hold]['phase'] = 'hold'
    line += [dict(p=p, up=u, phase='door') for p, u in out[1:]]
    # The elbows: the body's ends on the tube axis, feet leading outward; where no grip is in reach of the axis, the centre moves toward the
    # nearest grip by the shortfall.
    def _toward(c):
        d, a, b = min((_seg_dist(c, a, b), a, b) for a, b in gl)
        if d <= reach-0.005:
            return c
        ab = sub(b, a); g = cadd(a, ab, max(0.0, min(1.0, dot(sub(c, a), ab)/max(dot(ab, ab), 1e-12))))
        return cadd(c, crew_transfer.unit(sub(g, c)), d-reach+0.005)
    pts = list(fr['points']); L = [math.dist(a, b) for a, b in zip(pts, pts[1:])]
    def on_axis(t):
        for i in range(len(L)):
            if t <= L[i] or i == len(L)-1:
                return cadd(pts[i], fr['d'][i], t) if t >= 0.0 else cadd(pts[0], fr['d'][0], t)
            t -= L[i]
    t = line[-1]['p'][1]-pts[0][1]+ACCESS_STEP_M; run0 = sum(L[:3])
    top = run0+prof['height_m']/2+0.05
    while t < top+1e-9:
        a, b = on_axis(t-half), on_axis(min(t+half, top+half)); line.append(dict(p=_toward(mul(add(a, b), 0.5)), up=crew_transfer.unit(sub(a, b)), phase='elbow'))
        t = min(t+ACCESS_STEP_M, top) if t < top else top+1.0
    # onto the climber line (tube_stage, vehicle frame): the axis point at its height plus the climber's offset toward the ladder
    world = [dict(q, p=human_entry.at_index(rot, q['p']), up=human_entry.at_index(rot, q['up'], False)) for q in line]
    start = cadd(add(tube['axis_m'][0], mul(crew_transfer.unit(sub(tube['axis_m'][1], tube['axis_m'][0])), prof['height_m']/2+0.05)),
                 tube['toward_ladder'], tube['climber_offset_m'])
    world.append(dict(p=start, up=world[-1]['up'], phase='run'))
    # Check the whole line against the margin (the closures as the phase has them) in the rotor-local model.
    local = [(q['p'], q['up']) for q in line]+[(human_entry.at_index(dict(rot, x=-rot['x'], phase=-rot['phase']), tuple(start)), line[-1]['up'])]
    least = min(_segment_clear(w, p, q, i < hold, i >= hold, half, radius) for i, (p, q) in enumerate(zip(local, local[1:])))
    if least < ACCESS_MARGIN_M-1e-9:
        raise ValueError(f'access line keeps {least:.3f} m < {ACCESS_MARGIN_M} m')
    # Line parameter: the larger of the centre's travel and the travel of the body's ends while it turns, so a pace bounds both; the port
    # is reached where the body first leaves the trunk bore (the gate must be open from there).
    sv = [0.0]
    for p, q in zip(local, local[1:]):
        sv.append(sv[-1]+max(norm(sub(q[0], p[0])), prof['height_m']/2*math.acos(max(-1.0, min(1.0, dot(p[1], q[1]))))))
    port_s = None
    for i, (p, q) in enumerate(zip(local, local[1:])):
        for k in range(41):
            f = k/40; c, u = add(mul(p[0], 1-f), mul(q[0], f)), _nlerp(p[1], q[1], f)
            if port_s is None and any(math.hypot(*add(c, mul(u, half*(2*j/8-1)))[1:])+radius > w['trunk_r'] for j in range(9)):
                port_s = sv[i]+f*(sv[i+1]-sv[i])
    port = human_entry.at_index(rot, (hu, 0.0, 0.0)); radial = human_entry.at_index(rot, A, False)
    grips = [{'anchor_id': f"{q['name']}_{k+1}" if len(segs) > 1 else q['name'], 'role': q['role'], 'radius_m': q['radius'],
              'rail_start': list(human_entry.at_index(rot, a)), 'rail_end': list(human_entry.at_index(rot, b))}
             for q, segs in fix if q['role'] not in TRUNK_GRIPS for k, (a, b) in enumerate(segs)]
    # the coasts: the stretches before the sync with no grip in reach (straight moves between corners; the hands carry no load there)
    coasts = []
    for i, (p, q) in enumerate(zip(local[:hold], local[1:hold+1])):
        n = max(1, math.ceil((sv[i+1]-sv[i])/0.005))
        for k in range(n+1):
            if not held(_along(p, q, k/n)):
                sk = sv[i]+k/n*(sv[i+1]-sv[i])
                if coasts and sk-coasts[-1][1] < (sv[i+1]-sv[i])/n+1e-9:
                    coasts[-1][1] = sk
                else:
                    coasts.append([sk, sk])
    return {'frame': 'RING', 'ring': 0, 'zone': 'access', 'sector': tube['sector'],
            'trunk': {'x_m': [w['u_tr'][0]+rot['x'], port[0]+ACCESS_START_M+prof['height_m']], 'clear_radius_m': w['trunk_r']},
            'port': {'centre_m': list(port), 'radial': list(radial), 'clear_radius_m': v['port_clear']},
            'drum': {'x_m': [v['cu0']+rot['x'], v['cu1']+rot['x']], 'inner_radius_m': v['r0'], 'outer_radius_m': v['clear']},
            'tube': {'points_m': [list(human_entry.at_index(rot, p)) for p in pts[:-1]]+[list(tube['axis_m'][1])],
                     'miters': [list(human_entry.at_index(rot, m, False)) for m in fr['miter'][:-1]], 'clear_radius_m': w['tube_r']},
            'line': [{'p': list(q['p']), 'up': list(q['up']), 'phase': q['phase'], 's_m': d} for q, d in zip(world, sv)], 'hold_index': hold,
            'port_s_m': port_s, 'hold_s_m': sv[hold], 'run_s_m': sv[-1],
            'line_basis': 's_m is the larger of the centre travel and the end travel (height/2 x turn angle); the port is reached where the '
                          'body first leaves the trunk bore',
            'least_clearance_m': least, 'margin_m': ACCESS_MARGIN_M, 'grips': grips, 'reach_m': prof['reach_m'],
            'coasts_s_m': coasts, 'grip_zone_m': ACCESS_GRIP_ZONE_M,
            'source': 'crew_transfer.vestibule / tube_frames_of / stationary, human_entry.vestibule_fixtures / spoke_fixtures, tube_stage',
            'status': 'PROTOTYPE geometry and technique line',
            'note': 'points in the vehicle frame at the index (RING frame coordinates); the port gate is open and the drum door shut before the '
                    'hold, the reverse after it; the walls are the clear surfaces (the stage builds them outside the free space)'}


def stages(s):
    """Collision stages on the real route, from the shared formulas the Blender route uses (never from visual meshes, AGENTS.md):
    the stationary trunk (SHIP frame) as a hollow cylinder of its clear radius with its handrails as grip anchors (human_entry.trunk_fixtures),
    and the sector rooms of ring A's induction aisle (RING frame, the rig's induction_route.rooms, vehicle frame at the index pose), the
    crew tube's run (tube_stage) and the access from the trunk through the drum to the run top (access_stage).
    The trunk wall is closed over its branch openings (PROTOTYPE simplification, listed in `openings`)."""
    trunk = crew_transfer.stationary(s)[0]
    rails = [{'anchor_id': q['name'], 'role': q['role'], 'radius_m': q['radius'], 'rail_start': list(q['points'][0]), 'rail_end': list(q['points'][1])}
             for q in human_entry.trunk_fixtures(s) if q.get('role') in TRUNK_GRIPS]
    openings = [{'name': q['name'], 'role': q['role'], 'x_m': q['points'][0][0], 'theta_deg': math.degrees(math.atan2(q['points'][0][2], q['points'][0][1])),
                 'radius_m': q.get('hollow', q['radius'])}
                for q in crew_transfer.stationary(s)[1:] if q['points'][0][0] and abs(math.hypot(q['points'][0][1], q['points'][0][2])-trunk['hollow']) < 1e-6]
    return {'trunk': {'frame': 'SHIP', 'zone': 'trunk', 'axis_m': [list(trunk['points'][0]), list(trunk['points'][1])], 'clear_radius_m': trunk['hollow'],
                      'handholds': rails, 'openings': openings, 'source': 'crew_transfer.stationary, human_entry.trunk_fixtures', 'status': 'PROTOTYPE geometry'},
            'ring_rooms': {'frame': 'RING', 'ring': 0, 'source': 'induction_route.rooms', 'status': 'PROTOTYPE geometry',
                           'note': 'boxes in the vehicle frame at the index pose = ring-frame coordinates; deck at the floor radius',
                           # J01 (v41): ring B's sector clear volumes on its own rotor (same functions and sector frames as ring A).
                           'rings': {'RING_B': {'ring': 1, 'source': 'human_entry.room_volumes(ring 2)',     # JSON lists, so the saved rig equals the contract
                                                'boxes': [{k: ([list(x) for x in v] if k == 'axes' else list(v) if isinstance(v, tuple) else v) for k, v in b.items()}
                                                          for b in human_entry.room_volumes(s, 2)]}}},
            'tube': tube_stage(s), 'access': access_stage(s),
            'basis': 'colliders from sourced/derived route geometry, not the visual meshes; WAYFARER geometry stays REP_PROXY'}


def contract(s):
    """The rig's `dynamics` block (contract 27): everything a runtime needs to evaluate the field without its own constants."""
    cd = s['physics']['crew_dynamics']; centres = habitat_ring.centers(s)
    rings = [{'ring': k, 'name': f'RING_{"AB"[k]}', 'rotor': f'ROTOR_{k+1}', 'centre_x_m': centres[k], 'floor_radius_m': habitat_ring.floor(s),
              'sign': ring_sign(s, k), 'omega_rad_s': habitat_ring.omega(s)} for k in range(habitat_ring.ring_count(s))]
    modes = {}
    for m in MODES:
        c = s['configuration'][m]
        modes[m] = {'habitat': c['habitat'], 'drive': c['drive'], 'ring_spin': float(c['controls']['ring_spin']),
                    'ship_accel': ship_accel(s, m), 'demo_ship_accel_g': demo_ship_accel_g(s, m),
                    'omega_rad_s': [list(ring_omega(s, k, m)) for k in range(len(rings))],
                    'canon_status': c['canon_status'], 'source_ref': c['source_ref']}
    return {'source_ref': cd['source_ref'], 'canon_status': cd['canon_status'], 'standard_gravity_m_s2': G0,
            'axes': 'ship metres, +X bow, +Z dorsal (Blender); Godot (x, y, z) = (x, z, -y)',
            'frames': cd['frames'], 'ring_sign': cd['ring_sign'], 'spin_ramp': cd['spin_ramp']|{'study_value_s': s['physics']['rotor_operations']['spin_up_time_s']},
            'attitude_rate': cd['attitude_rate'], 'rings': rings, 'modes': modes,
            'transitions': {f'{a}>{b}': transition(s, a, b) for a in MODES for b in MODES if a != b},
            'profiles': profiles(s), 'nav': nav(s),
            'actor_mass': {'known': False, 'reason': cd['actor_mass']['reason']},
            'tether': {'known': False, 'reason': cd['tether']['reason']},
            'vestibule': vestibule(s), 'fixtures': fixtures(s), 'stages': stages(s)}


def vestibule(s):
    """Rotary vestibule handoff data (46 DYN-027, 15 CREW-MODE-004; OPERATIONAL DIRECTION / MECHANISM DETAILS OPEN): the match tolerance
    is the rotor rpm match tolerance (physics.rotor_dynamics); the drum synchronization cycle and the pressure-equalization threshold are
    OPEN (MEC-019, PRESS-004), so a runtime takes the cycle time as a labelled presentation input and the pressure state as a flag."""
    tol_rpm = s['physics']['rotor_dynamics']['rpm_match_tolerance_rpm']
    return {'match_tol_rad_s': tol_rpm*2.0*math.pi/60.0, 'match_tol_rpm': tol_rpm, 'match_tol_source': 'physics.rotor_dynamics.rpm_match_tolerance_rpm',
            'sync_cycle': {'known': False, 'reason': 'drum synchronization cycle time OPEN (MEC-019, 16!I20)'},
            'dp_threshold': {'known': False, 'reason': 'allowable pressure imbalance and equalization flow OPEN (PRESS-004, 45 I-01 is a simulator test point only)'},
            'rules': ['occupant restrained while the drum changes speed', 'both independent boundaries closed during synchronization, never open together',
                      'open only the side whose angular speed the drum matches, with pressure shown equalized',
                      'transform position and velocity (with w x r) at every frame change; no bare reparenting'],
            'status': 'OPERATIONAL DIRECTION / MECHANISM DETAILS OPEN', 'source': '46 DYN-027 / 15 CREW-MODE-004'}
