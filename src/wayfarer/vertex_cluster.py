"""Wayfarer Propulsion Cluster (owner brief 2026-11-14, Asset C). Pure, standard library only.

Four instances of the one Compact Vertex Engine (vertex_engine.parts, Blender asset WF_VERTEX_ENGINE) around the aft axis in the owner
nozzle order N1..N4 = +Y+Z, -Y+Z, +Y-Z, -Y-Z, plus the frame, distribution, cross-fire baffle, interfaces and per-engine display effects
built in WF_PROPULSION_CLUSTER. An engine instance is a placement (origin and rotation) of the engine asset; nothing here copies engine
geometry, so an engine change reaches all four instances through the linked asset.

The cluster is a SPECULATIVE working representation ([propulsion_representation]); it replaces the Fiji four-nozzle representation in the
active ship and never renders with it. It changes no canon value: thrust, power and mission numbers stay those of the canon drive.

Control: the cluster carries its own DRIVE_MANIFOLD_CTRL with the drive_manifold properties and actions, so the flight timeline, the
configurations and the runtime display tracks drive it unchanged; flux share n becomes engine Nn's level.

`python3 src/wayfarer/vertex_cluster.py` prints the fit screen: placement, clearances, candidate study, magnetics and radiation screens.
"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import vertex_engine as ve
import drive_manifold as dm
import layout

MU0 = ve.MU0
# Owner nozzle order (propulsion.manifold.nozzle_map): N1 +Y+Z, N2 -Y+Z, N3 +Y-Z, N4 -Y-Z; azimuth from +Y toward +Z.
AZIMUTH = {1: 45.0, 2: 135.0, 3: -45.0, 4: -135.0}
ADJACENT = [(1, 2), (2, 4), (4, 3), (3, 1)]


def arrangement(n=4):
    """(azimuths, neighbour pairs) for n engines. Four engines take the owner nozzle order; any other even count (six is the parametric
    alternative the brief keeps open) is evenly spaced counter-clockwise from +Y+Z, with alternating polarity around the ring."""
    if n == 4:
        return AZIMUTH, ADJACENT
    if n < 2 or n % 2:
        raise ValueError(f'engine count {n}: an even count keeps the alternating polarity (zero net torque)')
    az = {k: (90 - 180/n - 360*(k-1)/n + 180) % 360 - 180 for k in range(1, n+1)}
    return az, [(k, k % n + 1) for k in range(1, n+1)]


def polarities(s, n=None):
    c = config(s); n = n or c['engine_count']
    return list(c['polarity']) if n == len(c['polarity']) else [1 if k % 2 else -1 for k in range(n)]
FIJI, VERTEX = 'FIJI_FOUR_NOZZLE', 'VERTEX_CLUSTER'
SERVICES = [('TARGET_FEED', 'FUEL', 'fuel'), ('LITHIUM_SUPPLY', 'HOT_THERMAL', 'hot'), ('LITHIUM_RETURN', 'HOT_THERMAL', 'hot'),
            ('CRYOGEN', 'CRYOGENIC', 'cryo'), ('POWER', 'ELECTRICAL', 'power'), ('DATA', 'INSTRUMENTATION', 'sensor')]


def active(s):
    """The active propulsion representation: 'VERTEX_CLUSTER' or 'FIJI_FOUR_NOZZLE'."""
    r = s.get('propulsion_representation', {}).get('active', FIJI)
    assert r in (FIJI, VERTEX), r
    return r


def propulsion_asset(s):
    """The propulsion subsystem file the vehicle links (sim rig, ride-through and inspection references follow it)."""
    return 'WF_PROPULSION_CLUSTER' if active(s) == VERTEX else 'WF_PROPULSION'


def config(s):
    return s['propulsion_cluster']


# ---------- vectors ------------------------------------------------------------------------------------------------------------------

def add(a, b): return tuple(x+y for x, y in zip(a, b))
def sub(a, b): return tuple(x-y for x, y in zip(a, b))
def mul(a, k): return tuple(x*k for x in a)
def dot(a, b): return sum(x*y for x, y in zip(a, b))
def norm(a):
    L = math.sqrt(dot(a, a)) or 1.0
    return mul(a, 1/L)


# ---------- placements -----------------------------------------------------------------------------------------------------------------

def placement(j, pitch, cant_deg, front_x, polarity=1, n=4):
    """Engine Nj: origin (the cartridge's forward face, ship frame) and rotation (columns: engine +X, +Y, +Z in the ship frame). Engine +Y
    points radially outward, so the engine's service panel (azimuth 180) faces the hub; the cant tips the exhaust (-X) outward."""
    azd = arrangement(n)[0][j]; az = math.radians(azd); c = math.radians(cant_deg)
    u = (0.0, math.cos(az), math.sin(az)); t = (0.0, -math.sin(az), math.cos(az))
    X = (math.cos(c), -math.sin(c)*u[1], -math.sin(c)*u[2])
    Y = (math.sin(c), math.cos(c)*u[1], math.cos(c)*u[2])
    Z = t
    return dict(n=j, name=f'ENGINE_N{j}', ident=f'WF.VTX.CL4.ENGINE.N{j}', label=f'N{j}', azimuth_deg=azd, origin=(front_x, pitch*u[1], pitch*u[2]),
                axes=(X, Y, Z), polarity=polarity)


def placements(s, pitch=None, cant=None, front_x=None, n=None):
    c = config(s); n = n or c['engine_count']; pol = polarities(s, n)
    return [placement(j, c['pitch_radius_m'] if pitch is None else pitch, c['cant_deg'] if cant is None else cant,
                      c['front_x_m'] if front_x is None else front_x, pol[j-1], n) for j in range(1, n+1)]


def to_ship(pl, v):
    X, Y, Z = pl['axes']
    return tuple(pl['origin'][i]+v[0]*X[i]+v[1]*Y[i]+v[2]*Z[i] for i in range(3))


def matrix(pl):
    """4x4 world matrix rows (Blender Matrix order) of a placement."""
    X, Y, Z = pl['axes']; o = pl['origin']
    return [[X[0], Y[0], Z[0], o[0]], [X[1], Y[1], Z[1], o[1]], [X[2], Y[2], Z[2], o[2]], [0.0, 0.0, 0.0, 1.0]]


# ---------- frame and distribution -----------------------------------------------------------------------------------------------------

def ring_nodes(s):
    """The twelve aft thrust-ring nodes (structure.thrust_ring): ship-frame points the thrust struts land on."""
    p, st = s['prototype'], s['structure']
    x = layout.at(s, p['thrust_ring_x'])-st['ring_depth_m']/2
    return [dm.radial(x, st['ring_node_radius_m'], math.radians(p['ring_phase_deg'])+k*math.tau/st['ring_nodes']) for k in range(st['ring_nodes'])]


def stations(s):
    """Ship-frame stations of the cluster."""
    c = config(s); est = ve.stations(s); pl = placements(s)[0]
    collar = to_ship(pl, ((est['collar_fwd']+est['collar_aft'])/2, 0, 0))[0]
    burn = to_ship(pl, (est['burn'], 0, 0))[0]
    p = s['prototype']
    return dict(collar=collar, hub_fwd=collar+c['hub_length_m']/2, hub_aft=collar-c['hub_length_m']/2, burn=burn,
                baffle_fwd=collar-c['hub_length_m']/2, baffle_aft=burn-7.0, bay=layout.at(s, p['reactor_center_x']), bay_length=8.0, bay_radius=4.2,
                engine_aft=min(v[0] for pl_ in placements(s) for v in (to_ship(pl_, (est['exit']-1.0, 0, 0)),)))


def keepouts(s):
    """Spheres the cluster frame must clear: each comms appendage's gimbal sweep (exterior_hardware.comms) plus the member clearance."""
    import exterior_hardware as eh
    out = {}
    for p in eh.comms(s):
        if p.get('antenna') and p['antenna'] not in out:
            out[p['antenna']] = (tuple(p['gimbal']), p['sweep']+s['prototype']['radiator_member_clearance_m'])
    return out


def segment_point(a, b, q):
    d = sub(b, a); L2 = dot(d, d) or 1e-12; t = max(0.0, min(1.0, dot(sub(q, a), d)/L2))
    return math.dist(add(a, mul(d, t)), q)


def clear_of_keepouts(s, a, b, radius):
    return all(segment_point(a, b, c)-radius > r for c, r in keepouts(s).values())


def cradle_point(s, pl, az_deg, r=None):
    c = config(s); est = ve.stations(s)
    return to_ship(pl, ve.pol((est['collar_fwd']+est['collar_aft'])/2, c['cradle_radius_m'] if r is None else r, az_deg))


def frame(s):
    """Cluster frame members (ship frame): hub, thrust struts, cradles, trunnion pins, spokes, chords, cross-fire baffle. Each carries its
    load-path role; sizes are ENGINEERING_PROTOTYPE (unsized: joint and member design OPEN)."""
    c = config(s); st = stations(s); pls = placements(s); est = ve.stations(s); nodes = ring_nodes(s); out = []
    P = lambda name, cat, shape, mat, note, **g: out.append(ve.part(name, cat, shape, mat, note=note, **g))
    rh = c['hub_radius_m']
    P('CL_Reaction_Hub', 'STRUCTURE', 'revolve', 'structure', 'Central reaction hub: engine spokes meet here; carries the net magnetic and thrust loads to the thrust struts',
      profile=[(st['hub_fwd'], rh-2.2), (st['hub_fwd'], rh), (st['hub_aft'], rh), (st['hub_aft'], rh-2.2)], closed=True, n=48)
    # thrust struts: every thrust-ring node to the hub's forward rim, triangulated (+-15 deg)
    for k, node in enumerate(nodes):
        a = math.atan2(node[2], node[1])
        for side, d in (('A', -15), ('B', 15)):
            P(f'CL_Hub_Thrust_Strut_{k:02}{side}', 'STRUCTURE', 'tube', 'structure', f'Thrust strut: hub forward rim to thrust-ring node {k}',
              points=[node, dm.radial(st['hub_fwd'], rh-0.5, a+math.radians(d))], radius=c['thrust_strut_radius_m'])
    used = set()
    for pl in pls:
        j = pl['n']
        # cradle ring around the engine at the collar station, and four trunnion pins
        X = pl['axes'][0]; ctr = to_ship(pl, ((est['collar_fwd']+est['collar_aft'])/2, 0, 0))
        P(f'CL_N{j}_Cradle', 'STRUCTURE', 'torus', 'structure', f'N{j} cradle ring: trunnion seats, spokes and thrust struts meet here',
          x=(est['collar_fwd']+est['collar_aft'])/2, R=c['cradle_radius_m'], a=c['member_radius_m'], nu=48, nv=8, placement=j)
        for k, az in enumerate(ve.config(s)['geometry']['trunnion_azimuths_deg'], 1):
            P(f'CL_N{j}_Trunnion_Pin_{k}', 'SERVICE', 'tube', 'service', f'N{j} trunnion pin {k}: released for engine exchange (load: thrust and field)',
              points=[ve.pol((est['collar_fwd']+est['collar_aft'])/2, ve.config(s)['geometry']['collar_outer_radius_m']+0.55, az),
                      ve.pol((est['collar_fwd']+est['collar_aft'])/2, c['cradle_radius_m']+c['member_radius_m'], az)], radius=0.22, placement=j)
        # spokes: hub outer rim to the cradle's hub-facing side
        az_e = math.radians(pl['azimuth_deg'])
        for side, (loc, d) in (('A', (140, -14)), ('B', (220, 14))):
            P(f'CL_N{j}_Spoke_{side}', 'STRUCTURE', 'tube', 'structure', f'N{j} radial spoke {side}: field and lateral loads into the hub',
              points=[dm.radial(st['collar'], rh, az_e+math.radians(d)), cradle_point(s, pl, loc)], radius=c['member_radius_m'])
        # thrust struts: the two nearest thrust-ring nodes, from the cradle's forward quarter
        # the two nearest thrust-ring nodes whose strut clears every comms appendage's gimbal sweep (HGA booms stand on ring nodes)
        cand = sorted((k for k in range(len(nodes)) if k in c['thrust_ring_nodes']), key=lambda k: math.dist(nodes[k], ctr))
        pick = []
        for k in cand:
            loc = min((150, 210), key=lambda a: math.dist(cradle_point(s, pl, a), nodes[k]))
            if clear_of_keepouts(s, cradle_point(s, pl, loc), nodes[k], c['thrust_strut_radius_m']*1.2) and len(pick) < 2:
                pick.append((k, loc))
        for k, loc in pick:
            used.add(k)
            P(f'CL_N{j}_Thrust_Strut_{k:02}', 'STRUCTURE', 'tube', 'structure', f'N{j} thrust strut: cradle to thrust-ring node {k} (primary thrust path)',
              points=[cradle_point(s, pl, loc), nodes[k]], radius=c['thrust_strut_radius_m']*1.2)
        P(f'CL_N{j}_Strut_Ring_Tie', 'STRUCTURE', 'tube', 'structure', f'N{j} outboard thrust tie: cradle outer side to the hub rim (closes the triangle)',
          points=[cradle_point(s, pl, 0), dm.radial(st['hub_fwd'], rh, az_e)], radius=c['member_radius_m']*0.8)
    # chords between adjacent cradles
    for a, b in ADJACENT:
        pa, pb = pls[a-1], pls[b-1]
        ca = to_ship(pb, ((est['collar_fwd']+est['collar_aft'])/2, 0, 0))
        cb = to_ship(pa, ((est['collar_fwd']+est['collar_aft'])/2, 0, 0))
        qa = min((cradle_point(s, pa, k*10) for k in range(36)), key=lambda q: math.dist(q, ca))
        qb = min((cradle_point(s, pb, k*10) for k in range(36)), key=lambda q: math.dist(q, cb))
        P(f'CL_Chord_N{a}_N{b}', 'STRUCTURE', 'tube', 'structure', f'Chord N{a}-N{b}: ties neighbouring cradles (repulsion between opposite-polarity neighbours)',
          points=[qa, qb], radius=c['member_radius_m'])
    # cross-fire baffle: cruciform vanes in the four planes between neighbouring engines, and a core post on the axis
    r0, r1 = 6.0, c['pitch_radius_m']+4.0
    for k, az in enumerate((0, 90, 180, 270)):
        a = math.radians(az); u = (0.0, math.cos(a), math.sin(a))
        cen = (0.5*(st['baffle_fwd']+st['baffle_aft']), 0.5*(r0+r1)*u[1], 0.5*(r0+r1)*u[2])
        P(f'CL_Crossfire_Vane_{az:03d}', 'SHIELDING', 'box', 'armour', 'Cross-fire baffle vane: blocks each burn point\'s line of sight to the neighbouring engines\' loops',
          center=cen, size=(st['baffle_fwd']-st['baffle_aft'], r1-r0, 0.35), az=az)
    P('CL_Crossfire_Core', 'SHIELDING', 'revolve', 'shield', 'Cross-fire baffle core: blocks the diagonal line of sight across the axis',
      profile=[(st['baffle_fwd'], 0.0), (st['baffle_fwd'], r0), (st['baffle_aft'], r0*0.8), (st['baffle_aft'], 0.0)], closed=True, n=32)
    return out


def distribution(s):
    """Service distribution: the power and conditioning bay on the old reactor mount, the axial trunk through the thrust ring and hub, and
    six lines per engine along its spokes to the quick-disconnect panel (category, material and service per line)."""
    c = config(s); st = stations(s); pls = placements(s); est = ve.stations(s); g = ve.config(s)['geometry']; out = []
    x0, x1 = st['bay']+st['bay_length']/2, st['bay']-st['bay_length']/2
    out.append(ve.part('CL_Power_Conditioning_Bay', 'ELECTRICAL', 'revolve', 'power',
                       note='Cluster power and conditioning bay (on the old reactor mount): pulsed-power primary, cryoplant, lithium heat exchanger to the hot radiator loop',
                       profile=[(x0, 0.0), (x0, st['bay_radius']), (x1, st['bay_radius']), (x1, 0.0)], closed=True, n=32))
    sp = c['service_line_spacing_m']; rl = c['service_line_radius_m']
    for i, (svc, cat, mat) in enumerate(SERVICES):
        a = math.radians(60*i+30); rr = 1.0
        out.append(ve.part(f'CL_Trunk_{svc}', cat, 'tube', mat, note=f'Axial {svc.replace("_", " ").lower()} trunk from the bay through the thrust ring to the hub',
                           points=[dm.radial(x1, rr, a), dm.radial(st['hub_aft']+0.4, rr, a)], radius=rl*1.6))
    for pl in pls:
        j = pl['n']; az_e = math.radians(pl['azimuth_deg']); mid = (est['collar_fwd']+est['collar_aft'])/2
        for i, (svc, cat, mat) in enumerate(SERVICES):
            off = (i-2.5)*sp
            t = (0.0, -math.sin(az_e), math.cos(az_e))
            start = add(dm.radial(st['collar'], 1.0, az_e), mul(t, off))
            elbow = add(dm.radial(st['collar'], c['hub_radius_m']+0.6, az_e), mul(t, off))
            panel = to_ship(pl, (mid, -(g['collar_outer_radius_m']+0.5), off))
            near = to_ship(pl, (mid, -(c['cradle_radius_m']+1.0), off))
            out.append(ve.part(f'CL_N{j}_Line_{svc}', cat, 'tube', mat, note=f'N{j} {svc.replace("_", " ").lower()} line from the hub to the engine panel',
                               points=[start, elbow, near, panel], radius=rl))
    return out


def interfaces(s):
    """Ship-frame interfaces: per engine (mount, thrust, exit/nozzle, service panel, removal axis) and cluster level (power bay = the old
    IF_REACTOR_MOUNT, heat rejection, hub, thrust-ring seats)."""
    st = stations(s); est = ve.stations(s); out = []; g = ve.config(s)['geometry']
    for pl in placements(s):
        j = pl['n']; mid = (est['collar_fwd']+est['collar_aft'])/2
        out += [dict(name=f'IF_VTX_ENGINE_{j:02}_MOUNT', at=to_ship(pl, (mid, 0, 0)), axis=pl['axes'][0], note=f'N{j} trunnion plane: engine to cradle'),
                dict(name=f'IF_VTX_ENGINE_{j:02}_THRUST', at=to_ship(pl, (est['burn'], 0, 0)), axis=pl['axes'][0], note=f'N{j} thrust line (force on the ship along the engine +X)'),
                dict(name=f'IF_NOZZLE_{j:02}', at=to_ship(pl, (est['exit'], 0, 0)), axis=pl['axes'][0], note=f'N{j} exit plane (L4): the simulation nozzle vector anchor'),
                dict(name=f'IF_VTX_ENGINE_{j:02}_SERVICE', at=to_ship(pl, (mid, -(g['collar_outer_radius_m']+0.5), 0)), axis=pl['axes'][1], note=f'N{j} quick-disconnect panel'),
                dict(name=f'IF_VTX_ENGINE_{j:02}_REMOVAL', at=to_ship(pl, (est['exit']-2, 0, 0)), axis=mul(pl['axes'][0], -1), note=f'N{j} removal axis: aft along the engine axis')]
    out += [dict(name='IF_REACTOR_MOUNT', at=(st['bay'], 0.0, 0.0), axis=(1.0, 0.0, 0.0), note='Cluster power and conditioning bay centre (same station as the Fiji reactor mount)'),
            dict(name='IF_CLUSTER_POWER_BAY', at=(st['bay'], 0.0, 0.0), axis=(1.0, 0.0, 0.0), note='Main bus and pulsed-power primary feed into the cluster'),
            dict(name='IF_CLUSTER_HEAT_REJECTION', at=(st['bay']+st['bay_length']/2, 0.0, st['bay_radius']), axis=(1.0, 0.0, 0.0), note='Lithium heat exchanger to the hot radiator circuit'),
            dict(name='IF_CLUSTER_HUB', at=(st['collar'], 0.0, 0.0), axis=(1.0, 0.0, 0.0), note='Reaction hub centre')]
    out += [dict(name=f'IF_CLUSTER_RING_SEAT_{k:02}', at=n, axis=(1.0, 0.0, 0.0), note=f'Thrust strut seat on thrust-ring node {k}') for k, n in enumerate(ring_nodes(s))]
    return out


# ---------- display: shared effects, per-engine channels ----------------------------------------------------------------------------

def level(j):
    return f'min(1,4*s{j}/max(s1+s2+s3+s4,1e-06))'


def effect_objects(s):
    """One record per engine and effect of vertex_engine.effects: the shared definition, placed per engine, named N<j>_<effect>."""
    out = []
    for pl in placements(s):
        for e in ve.effects(s):
            out.append(dict(e, object=f'N{pl["n"]}_{e["name"]}', engine=pl['n'], placement=pl))
    return out


CHANNELS = {
    'ready': 'f',
    'burn': 'min(1,a*v*{e})',
    'flash': 'min(1,4*a*(1-a)*v*{e})',
    'plume': 'min(1,a*v*n*{e})',
    'hot': 'min(1,max(a,0.6*l)*{e})',
    'driver': 'min(1,min(1,A+B)*a*v*{e})',
}


def drivers(s):
    """(object, data path, index, expression) for every per-engine display object; Blender builds exactly these, display() evaluates them.
    Variables are drive_manifold.VARIABLES on the cluster's DRIVE_MANIFOLD_CTRL."""
    k = s['drive_manifold']['thrust_display_exponent']; out = []
    for o in effect_objects(s):
        e = level(o['engine']); alpha = CHANNELS[o['channel']].format(e=e)
        out.append((o['object'], 'color', 3, alpha))
        # Scale collapses an unlit effect (as PLASMA_COMMON does), so solid previews and the static export never show it; the plume's
        # length along the engine axis follows the display throttle.
        shown = f'min(1,{alpha}*1000)'
        out += [(o['object'], 'scale', i, f'(0.25+0.75*pow(max(t,0),{k!r}))*{shown}' if (o['channel'] == 'plume' and i == 0) else shown) for i in range(3)]
    for pl in placements(s):
        out += [(f'N{pl["n"]}_FX_FIELD_ENVELOPE', path, -1, 'dbm<0.5') for path in ('hide_viewport', 'hide_render')]
    return out


def display(s, values):
    env = {'min': min, 'max': max, 'sqrt': math.sqrt, 'pow': math.pow, '__builtins__': {}}
    env.update({var: float(values.get(prop, dm.SAVED_SETTINGS[prop]) if prop in dm.SAVED_SETTINGS else values[prop]) for var, prop in dm.VARIABLES.items()})
    return {(obj, path, index): float(eval(expr, env)) for obj, path, index, expr in drivers(s)}


def field_envelope(s):
    """Magnetic-nozzle field envelope (debug layer, hidden unless magnetic_field_debug): the loop-guided surface from the shield rim through
    each loop's bore. A display of the loop positions, not a field solution."""
    st = ve.stations(s); g = ve.config(s)['geometry']
    prof = [(st['shield_aft'], g['shield_aft_radius_m']*0.9)]+[(l['x'], l['r']*0.86) for l in st['loops']]+[(st['exit']-12.0, st['loops'][-1]['r']*1.25)]
    return ve.part('FX_FIELD_ENVELOPE', 'VISUAL_EFFECTS', 'revolve', 'field', note='Magnetic nozzle envelope (debug display; fields are invisible in normal views)', profile=prof, closed=False, n=48)


# Web viewer drive states (owner brief 11): named control poses on the first-ignition order; the viewer shows the matching opacities.
STATES = {
    'OFF': dict(description='Drive off: fields down, no plasma', values=dict()),
    'PRE_IGNITION': dict(description='Coils energised (ready indicators), no burn yet', values=dict(manifold_field_strength=1.0)),
    'IGNITION_PULSE': dict(description='First pulses: drivers firing, ignition flash, burn starting', values=dict(manifold_field_strength=1.0, drive_active=0.5, laser_A_power=0.5, laser_B_power=0.5,
                                                                                                               lattice_activation=0.5, nozzle_field_strength=0.3)),
    'SUSTAINED': dict(description='Sustained burn at the display operating point', values=dict(manifold_field_strength=1.0, drive_active=1.0, laser_A_power=0.5, laser_B_power=0.5,
                                                                                               lattice_activation=1.0, nozzle_field_strength=1.0)),
    'SHUTDOWN': dict(description='Burn stopped; hardware still hot, fields holding', values=dict(manifold_field_strength=0.5, lattice_activation=0.5)),
}


def state_values(s, name, shares=None):
    v = {**dm.neutral(s), 'plasma_visibility': 1.0, **STATES[name]['values']}
    for j, x in enumerate(shares or [0.25]*4, 1):
        v[f'flux_share_{j}'] = x
    return v


def effect_states(s):
    """{state: {object: opacity}} plus per-engine overrides, for the web viewer (web_export writes it next to the GLB)."""
    out = {}
    for name, st in STATES.items():
        d = display(s, state_values(s, name))
        out[name] = dict(description=st['description'], opacity={o: round(v, 4) for (o, p, i), v in d.items() if p == 'color'},
                         scale_x={o: round(v, 4) for (o, p, i), v in d.items() if p == 'scale' and i == 0})
    return dict(states=out, engines={f'N{pl["n"]}': [o['object'] for o in effect_objects(s) if o['engine'] == pl['n']] for pl in placements(s)},
                layers={o['name']: o['layer'] for o in ve.effects(s)},
                colors={o['name']: [round(c, 3) for c in o['color']] for o in ve.effects(s)}, rule='Per-engine level = 4 x flux_share_n / sum(shares); colours are a display, not a spectrum',
                evidence='SPECULATIVE display')


# ---------- engineering screens ---------------------------------------------------------------------------------------------------------

_ENV = {}


def gaps(s, pitch=None, cant=None, front_x=None, scale=1.0, n=None):
    """Clearances of one layout from the drawn engine envelope: adjacent engines (closest approach of the two envelope cones), central
    opening, outer radius and the radiators' aft edge."""
    key = (id(s), scale)
    if key not in _ENV:
        _ENV[key] = ve.envelope(s, scale)
    env = _ENV[key]; est = ve.stations(s, scale); c = config(s)
    pls = placements(s, pitch, cant, front_x, n)
    adjacent = arrangement(len(pls))[1]
    # envelope samples along each engine: (local x, radius) at the collar and at every loop
    prof = [(est['collar_fwd'], ve.config(s)['geometry']['collar_outer_radius_m']*scale+0.8), (est['shield_aft'], ve.config(s)['geometry']['shield_aft_radius_m']*scale)]
    prof += [(x, r) for x, r in ve.cage_points(s, scale)[1:]]
    prof = [(x, min(r+0.45, env['max_radius'])) for x, r in prof]
    def axis_pts(pl): return [(to_ship(pl, (x, 0, 0)), r) for x, r in prof]
    adj = min(math.dist(pa, pb)-ra-rb for a, b in adjacent for (pa, ra), (pb, rb) in zip(axis_pts(pls[a-1]), axis_pts(pls[b-1])))
    central = min(math.hypot(p[1], p[2])-r for pl in pls for p, r in axis_pts(pl))
    outer = max(math.hypot(p[1], p[2])+r for pl in pls for p, r in axis_pts(pl))
    aft = min(p[0] for pl in pls for p, _ in axis_pts(pl))-0.7
    return dict(adjacent_gap_m=adj, central_opening_m=central, outer_radius_m=outer, aft_x_m=aft)


def magnetics(s, pitch=None):
    """Inter-engine magnetic loads, dipole approximation of the four loops (CALCULATED, order of magnitude): each engine's loops carry
    I = 2 B R / mu0 at the C-07 stopping field; neighbours with opposite polarity repel, the diagonal pair (same polarity) attracts."""
    c = config(s); pitch = c['pitch_radius_m'] if pitch is None else pitch
    calc = {r['id']: r for r in ve.calculations(s)}; B = calc['C-07']['compact']; st = ve.stations(s)
    m = sum(2*B*l['r']/MU0*math.pi*l['r']**2 for l in st['loops'])          # A m^2
    d_adj, d_diag = pitch*math.sqrt(2), 2*pitch
    # two parallel coaxial-normal dipoles side by side (broadside): F = 3 mu0 m^2 / (4 pi d^4)
    F = lambda d: 3*MU0*m*m/(4*math.pi*d**4)
    pol = c['polarity']
    return dict(evidence='CALCULATED', field_T=B, dipole_moment_Am2=m, adjacent_distance_m=d_adj, diagonal_distance_m=d_diag,
                adjacent_force_MN=F(d_adj)/1e6, diagonal_force_MN=F(d_diag)/1e6, polarity=pol,
                net_torque='zero by symmetry (quadrupole arrangement)', note='Broadside dipole approximation at the stopping field; a pulse transient, not a steady load. Chords and the hub carry it.',
                thrust_per_engine_MN=calc['C-10']['compact'])


def _sphere_dirs(n=4000):
    g = math.pi*(3-math.sqrt(5))
    for i in range(n):
        y = 1-2*(i+0.5)/n; r = math.sqrt(1-y*y); a = g*i
        yield (y, r*math.cos(a), r*math.sin(a))


def radiation(s, n=6000):
    """Line of sight from each burn point (CALCULATED geometric screen, point source): the fraction of its emission that would reach the
    radiator blades, the hull and the neighbouring engines' loops, with and without the cross-fire baffle and the own shield."""
    pls = placements(s); est = ve.stations(s); g = ve.config(s)['geometry']; st = stations(s); c = config(s)
    th = s['thermal_radiators'] if 'thermal_radiators' in s else None
    shield_r, shield_x = g['shield_aft_radius_m'], est['shield_aft']
    burn = to_ship(pls[0], (est['burn'], 0, 0))
    r0, r1 = 6.0, c['pitch_radius_m']+4.0
    def blocked_by_own_shield(d):
        # direction in engine-local frame
        X, Y, Z = pls[0]['axes']; dl = (dot(d, X), dot(d, Y), dot(d, Z))
        if dl[0] <= 0: return False
        t = (shield_x-est['burn'])/dl[0]
        return math.hypot(dl[1]*t, dl[2]*t) <= shield_r
    def hits_baffle(d):
        for az in (0, 90, 180, 270):
            a = math.radians(az); nrm = (0.0, -math.sin(a), math.cos(a)); u = (0.0, math.cos(a), math.sin(a))
            den = dot(d, nrm)
            if abs(den) < 1e-9: continue
            t = -dot(burn, nrm)/den
            if t <= 0: continue
            p = add(burn, mul(d, t)); rr = dot(p, u)
            if st['baffle_aft'] <= p[0] <= st['baffle_fwd'] and r0 <= rr <= r1:
                return True
        # core post (cylinder r0 between the baffle stations)
        return False
    def hits_radiator(d):
        # blades: planes containing the axis at the blade azimuths, r 6.5-37, x from -133.25 forward 20 m (the aft cells)
        for k in range(3):
            a = math.radians(30+120*k); nrm = (0.0, -math.sin(a), math.cos(a)); u = (0.0, math.cos(a), math.sin(a))
            den = dot(d, nrm)
            if abs(den) < 1e-9: continue
            t = -dot(burn, nrm)/den
            if t <= 0: continue
            p = add(burn, mul(d, t)); rr = dot(p, u)
            if -133.25 <= p[0] <= -40.0 and 6.5 <= rr <= 37.0:
                return True
        return False
    def hits_neighbour(d):
        for pl in pls[1:]:
            for l in est['loops']:
                q = to_ship(pl, (l['x'], 0, 0)); w = sub(q, burn); t = dot(w, d)
                if t <= 0: continue
                closest = math.dist(add(burn, mul(d, t)), q)
                # a ray grazing the loop's plane near radius r: crude disc annulus test in the loop plane
                X = pl['axes'][0]; den = dot(d, X)
                if abs(den) < 1e-9: continue
                tt = dot(w, X)/den
                if tt <= 0: continue
                p = add(burn, mul(d, tt)); rr = math.dist(p, q)
                if abs(rr-l['r']) <= l['cryostat_minor_m']+0.4:
                    return True
        return False
    tot = rad = rad_b = nb = nb_b = 0
    for d in _sphere_dirs(n):
        if blocked_by_own_shield(d):
            continue
        tot += 1
        b = hits_baffle(d)
        if hits_radiator(d):
            rad += 1; rad_b += (not b)
        if hits_neighbour(d):
            nb += 1; nb_b += (not b)
    return dict(evidence='CALCULATED', method=f'{n} directions from engine N1 burn point; point source; own shield shadow removed',
                shadow_half_angle_deg=math.degrees(math.atan2(shield_r, est['shield_aft']-est['burn'])),
                radiator_fraction_unbaffled=rad/n, radiator_fraction=rad_b/n, neighbour_loop_fraction_unbaffled=nb/n, neighbour_loop_fraction=nb_b/n,
                note='The radiator blades lie forward of the engines and outside most of the open hemisphere; the baffle removes the direct path to the neighbours. Shine and scatter not modelled.')


def study(s):
    """Owner brief 6.1: screen the candidate grid (pitch radius, cant, module scale, front station) against the clearances and the visual
    ratio to the forward shield, and confirm the selection is a passing candidate. ENGINEERING_PROTOTYPE selection rule: the engine as
    defined (scale 1), the smallest pitch that passes, the front station nearest the hull."""
    c = config(s); shield_d = s['forward_shield']['diameter']['value'] if 'forward_shield' in s and isinstance(s['forward_shield'].get('diameter'), dict) else 90.0
    rows = []
    for pitch in c['candidate_pitch_radii_m']:
        for cant in c['candidate_cant_deg']:
            for scale in c['candidate_module_scales']:
                for fx in c['candidate_front_x_m']:
                    gp = gaps(s, pitch, cant, fx, scale); ratio = 2*gp['outer_radius_m']/shield_d
                    ok = dict(adjacent=gp['adjacent_gap_m'] >= c['min_engine_gap_m'], central=gp['central_opening_m'] >= c['min_central_opening_m'],
                              visual=c['visual_ratio_target'][0] <= ratio <= c['visual_ratio_target'][1], cant_loss=1-math.cos(math.radians(cant)) <= 0.005)
                    rows.append(dict(pitch=pitch, cant=cant, scale=scale, front_x=fx, ratio=round(ratio, 3), **{k: round(v, 2) for k, v in gp.items()},
                                     axial_loss=round(1-math.cos(math.radians(cant)), 5), passes=all(ok.values()), failed=[k for k, v in ok.items() if not v]))
    passing = [r for r in rows if r['passes']]
    rule = sorted([r for r in passing if r['scale'] == 1.0], key=lambda r: (r['pitch'], -r['front_x'], abs(r['cant']-2.0)))
    sel = next((r for r in rows if (r['pitch'], r['cant'], r['scale'], r['front_x']) == (c['pitch_radius_m'], c['cant_deg'], 1.0, c['front_x_m'])), None)
    return dict(evidence='ENGINEERING_PROTOTYPE', candidates=len(rows), passing=len(passing), selection=sel, rule_choice=rule[0] if rule else None,
                rule='scale 1 (the engine as defined), the smallest pitch that passes, the front station nearest the hull, cant nearest 2 deg (exhaust spreads outward)',
                rows=rows, shield_diameter_m=shield_d)


def six_engine(s):
    """The parametric six-engine alternative at the selected pitch, cant and front: the gap screen only (no frame, effects or build)."""
    c = config(s); g = gaps(s, n=6)
    ok = lambda g_: g_['adjacent_gap_m'] >= c['min_engine_gap_m'] and g_['central_opening_m'] >= c['min_central_opening_m']
    need = next((p for p in (c['pitch_radius_m']+0.5*k for k in range(61)) if ok(gaps(s, pitch=p, n=6))), None)
    gn = gaps(s, pitch=need, n=6) if need else None
    return dict(evidence='ENGINEERING_PROTOTYPE', engines=6,
                passing_pitch_m=need, passing_outer_radius_m=round(gn['outer_radius_m'], 3) if gn else None, azimuth_deg=arrangement(6)[0], polarity=polarities(s, 6),
                gaps={k: round(v, 3) for k, v in g.items()},
                passes=ok(g),
                note='Screen only: six engines at the four-engine pitch. Building it needs the frame, the shares (dm has four) and an owner decision.')


def check(s):
    """Fit screen of the selected cluster: raises on a failed rule; returns the report."""
    c = config(s); gp = gaps(s); st = study(s); mg = magnetics(s); env = ve.envelope(s)
    problems = []
    need = lambda ok, msg: ok or problems.append(msg)
    need(st['selection'] is not None and st['selection']['passes'], f'selected layout is not a passing candidate: {st["selection"]}')
    need(gp['adjacent_gap_m'] >= c['min_engine_gap_m'], f'adjacent gap {gp["adjacent_gap_m"]:.2f} < {c["min_engine_gap_m"]}')
    need(gp['central_opening_m'] >= c['min_central_opening_m'], f'central opening {gp["central_opening_m"]:.2f} < {c["min_central_opening_m"]}')
    need(env['max_radius'] <= ve.config(s)['geometry']['max_radius_m']+1e-9, f'engine envelope {env["max_radius"]:.2f} exceeds its limit')
    need(c['front_x_m'] < -133.25, 'engine fronts must sit aft of the radiator blades (X -133.25)')
    need(c['engine_count'] == len(c['polarity']) == 4, 'four engines, four polarities')
    need(sum(c['polarity']) == 0 and all(c['polarity'][a-1] != c['polarity'][b-1] for a, b in ADJACENT), 'neighbours must have opposite polarity')
    for p in frame(s)+distribution(s):
        if p['shape'] == 'tube' and not p.get('placement'):
            pts = p['points']
            need(all(clear_of_keepouts(s, u, w, p['radius']) for u, w in zip(pts, pts[1:])), f'{p["name"]} enters a comms appendage sweep')
    L = s['ship']['length']; overall = (L['value']/2+s['forward_defense']['dust_lance']['length']['value'])-gp['aft_x_m']
    need(overall <= L['max'], f'overall hardware length {overall:.1f} exceeds the {L["max"]} m envelope')
    if problems:
        raise ValueError('; '.join(problems))
    return dict(gaps={k: round(v, 3) for k, v in gp.items()}, overall_hardware_length_m=round(overall, 2), visual_ratio=round(2*gp['outer_radius_m']/st['shield_diameter_m'], 3),
                study={k: v for k, v in st.items() if k != 'rows'}, magnetics=mg, six_engine=six_engine(s))


def report(s):
    return dict(cluster=config(s)['id'], engine=ve.config(s)['id'], active=active(s), placements=[{k: v for k, v in pl.items()} for pl in placements(s)],
                check=check(s), radiation=radiation(s), engine_fit=ve.fit_screen(s), stations={k: round(v, 3) for k, v in stations(s).items()})


if __name__ == '__main__':
    import json
    from spec import load
    print(json.dumps(report(load(Path(__file__).resolve().parents[2])[0]), indent=1, default=str))
