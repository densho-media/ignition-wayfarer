"""HR-001 / TODO E01: packaging comparison for the hybrid heat-recovery preheater (NONCANON study, PROTOTYPE envelopes, nothing saved).

Function: hot drive coolant -> isolated exchanger / intermediate loop -> conditioned H2 reaction mass downstream of cryogenic storage and
upstream of the existing injection ring -> common mixing region -> N1-N4 (S&E 15!A193 HR-001, 06!A58:A64, 40!A97:A109, OD-041). Brayton A/B
stay as they are; no core return, no cryotank heating, no manifold, nozzle, radiator, hull or mass change (15!H193, H196).
Fixed: the built H2 feed lines (CRYO_FEED_LINE_03/04, drive_hot_section.cryo_feed), the injection ring, the shadow-shield slab and its
dog-leg rule, reactor / common / tank / Brayton envelopes, hull inner wall. Unknown (all OPEN): source heat and temperature, H2 flow, phase
and enthalpy, HX duty, pinch, pressure drop, materials, masses, the interior hot-loop route to the radiator chases, plasma / seed-field /
magnetic / radiation keepouts. Design freedom (PROTOTYPE judgment, this file): the cassette, valve and pipe sizes and positions.

Each candidate is a parallel branch on each hydrogen line: the built line stays the BYPASS (the normal state, HR-002), two isolation valves
take H2 through the preheater cassette, a bypass valve on the built line closes only in PREHEAT; the intermediate loop separates drive
coolant from hydrogen (hot -> intermediate HX -> intermediate fluid -> H2 preheater). Removing every HR_ part restores the baseline.

  A  shielded engineering bay: preheater forward of the shadow shield in the Engineering_Envelope (X -80..-72 m), intermediate loop
     through two new stepped sleeves per line to an intermediate HX in the annulus beside the reactor.
  B  aft drive annulus: preheater and intermediate HX in the annulus aft of the reactor, beside the injection ring; no shield penetration.

    python3 src/wayfarer/studies/hr001_packaging.py                       # screen only (JSON to stdout)
    /snap/bin/blender -b --python src/wayfarer/studies/hr001_packaging.py -- --out runs/<stamp>-hr001
"""
from pathlib import Path
import argparse
import json
import math
import sys
ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT/'src/wayfarer'), str(ROOT/'src/wayfarer/build'), str(ROOT/'src/wayfarer/presentation')]
from spec import load
import drive_manifold as dm
import drive_hot_section as hs
import power_storage as ps
import hull_geometry

# PROTOTYPE study choices (judgment, no source): proxy sizes only, never a duty, mass or rating.
CASSETTE = dict(length=1.6, radial=0.6, width=0.7)       # H2 preheater cassette (HX_CORE) per hydrogen line
INTER_HX = dict(length=1.4, radial=0.7, width=0.7)       # hot-loop / intermediate exchanger per line
H2_PIPE_R = 0.08                                         # branch pipe = the built feed line radius
INTER_PIPE_R = 0.06                                      # intermediate loop feed / return
HOT_PIPE_R = 0.06                                        # hot-loop branch stubs to the OPEN tap
VALVE_R = 0.14                                           # valve body proxy (sphere)
SENSOR_R = 0.05
SLEEVE_STEP = 0.5                                        # dog-leg step inside the slab, the feed-line convention (cryo_feed_sleeve_step_m)
H2_LINES = (3, 4)                                        # CRYO_FEED_LINE_03/04 (terminus injection_ring)
PALETTE = dict(hx_core=(.85, .45, .15), inter_hx=(.75, .2, .15), h2_branch=(.35, .7, .95), intermediate=(.95, .75, .25),
               hot=(.9, .15, .1), valve=(.9, .9, .9), sensor=(.3, .95, .45), tap=(1.0, 0.0, 1.0), sleeve=(.6, .6, .65), debug=(.7, .3, 1.0))
note = 'STUDY HR-001 packaging (ART_HR, NONCANON, PROTOTYPE envelopes; every duty, mass, rating and keepout OPEN)'


def radial(x, r, deg):
    a = math.radians(deg)
    return (x, r*math.cos(a), r*math.sin(a))


def azimuth(p):
    return math.degrees(math.atan2(p[2], p[1])) % 360


def line_of(s, j):
    return next(l for l in hs.cryo_feed(s) if l['index'] == j)


def box(name, kind, x0, x1, r0, r1, deg, width, role):
    """Radial box: axial x0..x1, radial r0..r1 along azimuth deg, tangential width; corners for clearance sampling."""
    a = math.radians(deg); u = (0.0, math.cos(a), math.sin(a)); t = (0.0, -math.sin(a), math.cos(a))
    corners = [tuple(x*(i == 0)+r*u[i]+w*t[i] for i in range(3)) for x in (x0, x1) for r in (r0, r1) for w in (-width/2, width/2)]
    corners = [(x, c[1], c[2]) for x, c in zip([x0]*4+[x1]*4, corners)]
    return dict(name=name, kind=kind, shape='box', x0=min(x0, x1), x1=max(x0, x1), r0=r0, r1=r1, deg=deg, width=width, role=role, corners=corners)


def pipe(name, kind, points, radius, role):
    return dict(name=name, kind=kind, shape='pipe', points=points, radius=radius, role=role)


def node(name, kind, point, radius, role):
    return dict(name=name, kind=kind, shape='node', point=point, radius=radius, role=role)


def arc(x, r, d0, d1, step=3.0):
    n = max(1, math.ceil(abs(d1-d0)/step))
    return [radial(x, r, d0+(d1-d0)*k/n) for k in range(n+1)]


def sleeve_path(x_before, x_after, st, r, deg, inset, step=SLEEVE_STEP):
    """Stepped dog-leg through the shadow-shield slab at azimuth deg (the feed-line rule): radially by step at the forward inset plane,
    back at the aft inset plane, so no straight line crosses the sleeve. A negative step jogs inward (keeps the sleeve inside the slab rim)."""
    xf, xa = st['shield_fwd']-inset, st['shield_aft']+inset
    return [radial(x_before, r, deg), radial(xf, r, deg), radial(xf, r+step, deg), radial(xa, r+step, deg), radial(xa, r, deg), radial(x_after, r, deg)]


def candidate_a(s):
    """Shielded engineering bay (forward of the shadow shield)."""
    st = dm.stations(s); h = s['drive_hot_section']; parts = []
    for j in H2_LINES:
        L = line_of(s, j); th = azimuth(L['a']); r_line = math.hypot(L['a'][1], L['a'][2]); tag = f'L{j}'
        rc = r_line+0.85; c0, c1 = -74.0, -74.0-CASSETTE['length']                       # cassette 0.85 m outboard of the line
        x_in, x_out = -73.6, c1-0.4
        parts.append(box(f'HR_A_{tag}_HX_Core', 'hx_core', c0, c1, rc-CASSETTE['radial']/2, rc+CASSETTE['radial']/2, th, CASSETTE['width'], 'H2 preheater cassette'))
        parts.append(pipe(f'HR_A_{tag}_H2_Preheat_Feed', 'h2_branch', [radial(x_in, r_line, th), radial(x_in, rc, th), radial(c0, rc, th)], H2_PIPE_R, 'conditioned H2 to preheater'))
        parts.append(pipe(f'HR_A_{tag}_H2_Preheat_Return', 'h2_branch', [radial(c1, rc, th), radial(x_out, rc, th), radial(x_out, r_line, th)], H2_PIPE_R, 'preheated H2 back to the built line'))
        parts += [node(f'HR_A_{tag}_Valve_H2_In', 'valve', radial(x_in, r_line+0.3, th), VALVE_R, 'H2 branch isolation (closed in BYPASS)'),
                  node(f'HR_A_{tag}_Valve_H2_Out', 'valve', radial(x_out, r_line+0.3, th), VALVE_R, 'H2 branch isolation (closed in BYPASS)'),
                  node(f'HR_A_{tag}_Valve_H2_Bypass', 'valve', radial((x_in+x_out)/2, r_line, th), VALVE_R, 'built line = bypass (open in BYPASS)'),
                  node(f'HR_A_{tag}_Sensor_H2_In', 'sensor', radial(c0+0.15, rc+CASSETTE['radial']/2+0.08, th), SENSOR_R, 'H2 T/p/flow in'),
                  node(f'HR_A_{tag}_Sensor_H2_Out', 'sensor', radial(c1-0.15, rc+CASSETTE['radial']/2+0.08, th), SENSOR_R, 'H2 T/p out')]
        # Intermediate loop: leaves the cassette aft face, swings 15 deg off the H2 line, crosses the slab in its own dog-leg sleeve
        # The pipes run outboard of the reactor envelope (r 4.6) and jog inward through the slab so the sleeve stays inside its 5.7 m rim.
        d = th+(-15 if j == 3 else 15); xi0, xi1 = st['core_fwd']-0.4, st['core_fwd']-0.4-INTER_HX['length']; ri = 5.2
        for k, (r0, rr, nm) in enumerate(((rc-0.15, 4.95, 'Feed'), (rc+0.15, 5.25, 'Return'))):
            run = [radial(c1, r0, th), radial(c1-0.3, r0, th)]+arc(c1-0.3, r0, th, d)[1:]+[radial(c1-0.3, rr, d)]
            run += sleeve_path(st['shield_fwd']+0.3, st['shield_aft']-0.3, st, rr, d, h['cryo_feed_sleeve_jog_inset_m'], -SLEEVE_STEP)
            run += [radial(xi0, rr, d)]
            parts.append(pipe(f'HR_A_{tag}_Intermediate_{nm}', 'intermediate', run, INTER_PIPE_R, f'intermediate loop {nm.lower()} through a new stepped slab sleeve'))
        parts.append(box(f'HR_A_{tag}_Intermediate_HX', 'inter_hx', xi0, xi1, ri-INTER_HX['radial']/2, ri+INTER_HX['radial']/2-0.05, d, INTER_HX['width'], 'hot-loop / intermediate exchanger'))
        tap = radial((xi0+xi1)/2, 4.68, d)
        parts += [pipe(f'HR_A_{tag}_Hot_Feed', 'hot', [radial(xi0-0.3, ri-INTER_HX['radial']/2, d), radial(xi0-0.3, 4.68, d)], HOT_PIPE_R, 'hot-loop branch feed'),
                  pipe(f'HR_A_{tag}_Hot_Return', 'hot', [radial(xi1+0.3, ri-INTER_HX['radial']/2, d), radial(xi1+0.3, 4.68, d)], HOT_PIPE_R, 'hot-loop branch return'),
                  node(f'HR_A_{tag}_Hot_Loop_Tap', 'tap', tap, 0.1, 'OPEN: interior hot-loop route not modelled'),
                  node(f'HR_A_{tag}_Valve_Hot_Isolation', 'valve', radial(xi0-0.3, 4.95, d), VALVE_R, 'hot branch isolation (HX_FAULT_ISOLATED)')]
    return parts


def candidate_b(s):
    """Aft drive annulus beside the injection ring (aft of the reactor, no shield penetration)."""
    st = dm.stations(s); inj = hs.injection_ring(s); parts = []
    for j in H2_LINES:
        L = line_of(s, j); th = azimuth(L['b']); rcor = s['drive_hot_section']['h2_corridor_radius_m']; tag = f'L{j}'
        sgn = 1 if j == 3 else -1; d = th+sgn*14; dh = th+sgn*32; rc = 4.75
        c0 = st['core_aft']-0.4; c1 = c0-1.3                                                    # -89.9 .. -91.2
        x_tap = st['core_aft']+0.9
        parts.append(box(f'HR_B_{tag}_HX_Core', 'hx_core', c0, c1, rc-CASSETTE['radial']/2, rc+CASSETTE['radial']/2, d, CASSETTE['width'], 'H2 preheater cassette'))
        parts.append(pipe(f'HR_B_{tag}_H2_Preheat_Feed', 'h2_branch', arc(x_tap, rcor, th, d)+[radial(c0+0.15, rcor, d), radial(c0+0.15, rc, d), radial(c0, rc, d)], H2_PIPE_R, 'conditioned H2 to preheater'))
        x_r = inj['x']+inj['tube']+0.15
        parts.append(pipe(f'HR_B_{tag}_H2_Preheat_Return', 'h2_branch', [radial(c1, rc, d)]+arc(x_r, rc, d, th)+[radial(inj['x'], rc, th)], H2_PIPE_R, 'preheated H2 into the built turn-in leg'))
        parts += [node(f'HR_B_{tag}_Valve_H2_In', 'valve', radial(x_tap, rcor, th+sgn*4), VALVE_R, 'H2 branch isolation (closed in BYPASS)'),
                  node(f'HR_B_{tag}_Valve_H2_Out', 'valve', radial(inj['x'], rc, th), VALVE_R, 'H2 branch isolation (closed in BYPASS)'),
                  node(f'HR_B_{tag}_Valve_H2_Bypass', 'valve', radial(c0-0.6, rcor, th), VALVE_R, 'built line = bypass (open in BYPASS)'),
                  node(f'HR_B_{tag}_Sensor_H2_In', 'sensor', radial(c0-0.15, rc+CASSETTE['radial']/2+0.08, d), SENSOR_R, 'H2 T/p/flow in'),
                  node(f'HR_B_{tag}_Sensor_H2_Out', 'sensor', radial(c1+0.15, rc+CASSETTE['radial']/2+0.08, d), SENSOR_R, 'H2 T/p out')]
        parts.append(box(f'HR_B_{tag}_Intermediate_HX', 'inter_hx', c0, c1+0.1, rc-INTER_HX['radial']/2, rc+INTER_HX['radial']/2, dh, INTER_HX['width'], 'hot-loop / intermediate exchanger'))
        xm = (c0+c1)/2
        for rr, nm in ((rc-0.2, 'Feed'), (rc+0.2, 'Return')):
            parts.append(pipe(f'HR_B_{tag}_Intermediate_{nm}', 'intermediate', arc(xm, rr, d+sgn*5, dh-sgn*5), INTER_PIPE_R, f'intermediate loop {nm.lower()}'))
        tap = radial(st['core_aft']+0.05, 4.3, dh)
        parts += [pipe(f'HR_B_{tag}_Hot_Feed', 'hot', [radial(c0, 4.5, dh), radial(st['core_aft']+0.05, 4.5, dh)], HOT_PIPE_R, 'hot-loop branch feed'),
                  pipe(f'HR_B_{tag}_Hot_Return', 'hot', [radial(c0, 4.15, dh), radial(st['core_aft']+0.05, 4.15, dh)], HOT_PIPE_R, 'hot-loop branch return'),
                  node(f'HR_B_{tag}_Hot_Loop_Tap', 'tap', tap, 0.1, 'OPEN: hot-loop tap on the reactor aft face, route not modelled'),
                  node(f'HR_B_{tag}_Valve_Hot_Isolation', 'valve', radial(c0+0.12, 4.9, dh), VALVE_R, 'hot branch isolation (HX_FAULT_ISOLATED)')]
    return parts


CANDIDATES = {'A': candidate_a, 'B': candidate_b}
SELECTED = 'B'                                           # E01 selection (references/HR001_PACKAGING_2026-10-16.md); A kept as the alternative

# HR-002 state labels -> valve positions per hydrogen line (O open, C closed). BRAYTON_BASELINE and NO_DATA leave the HR branch closed:
# Brayton A/B run from the existing hot loop as built, and missing data never opens a valve. HYBRID splits the bypass by a modulating
# position whose value is OPEN, so it is 'M' (neither a number nor a claim).
MODES = {
    'BYPASS':            dict(H2_In='C', H2_Out='C', H2_Bypass='O', Hot_Isolation='C'),
    'PREHEAT_STUDY':     dict(H2_In='O', H2_Out='O', H2_Bypass='C', Hot_Isolation='O'),
    'BRAYTON_BASELINE':  dict(H2_In='C', H2_Out='C', H2_Bypass='O', Hot_Isolation='C'),
    'HYBRID_STUDY':      dict(H2_In='O', H2_Out='O', H2_Bypass='M', Hot_Isolation='O'),
    'HX_FAULT_ISOLATED': dict(H2_In='C', H2_Out='C', H2_Bypass='O', Hot_Isolation='C'),
    'NO_DATA':           dict(H2_In='C', H2_Out='C', H2_Bypass='O', Hot_Isolation='C'),
}


def debug_links(s, key):
    """Non-physical energy-path links (HR-P06, HR-P09): each hot-loop tap to a Brayton train (the existing closed-Brayton A/B take heat
    from the same hot loop; route OPEN) and a conditioning node at each hydrogen tank's aft cap (conditioning point OPEN). Never screened."""
    out = []; trains = {n: (a, b) for n, a, b, r in ps.obstacles(s) if n.startswith('Brayton_Train')}
    for j, train in zip(H2_LINES, sorted(trains)):
        tap = next(p for p in CANDIDATES[key](s) if p['name'] == f'HR_{key}_L{j}_Hot_Loop_Tap')['point']
        a, b = trains[train]; mid = tuple((u+v)/2 for u, v in zip(a, b))
        out.append(pipe(f'HR_{key}_L{j}_Debug_Hot_To_{train}', 'debug', [tap, (tap[0], tap[1]*0.4, tap[2]*0.4), (mid[0], tap[1]*0.4, tap[2]*0.4), mid],
                        0.025, f'DEBUG: existing hot loop -> {train} (route OPEN, not a pipe)'))
        L = line_of(s, j)
        out.append(node(f'HR_{key}_L{j}_H2_Conditioning', 'debug', L['a'], 0.12, 'OPEN: H2 conditioning point assumed at the tank aft cap'))
    return out


def h2_paths(s, key, j):
    """Hydrogen flow path of line j from the tank cap to the injection ring in each mode, as the ordered list of segments it uses:
    'built' (the existing CRYO_FEED_LINE polyline between the branch points) or the branch parts. A closed valve removes its segment."""
    parts = {p['name'].split(f'_L{j}_')[1]: p for p in CANDIDATES[key](s) if f'_L{j}_' in p['name']}
    out = {}
    for mode, v in MODES.items():
        path = ['built:tank_cap..branch_in']
        if v['H2_In'] == 'O' and v['H2_Out'] == 'O':
            path += ['H2_Preheat_Feed', 'HX_Core', 'H2_Preheat_Return']
        if v['H2_Bypass'] in ('O', 'M'):
            path += ['built:branch_in..branch_out']
        path += ['built:branch_out..injection_ring']
        missing = [n for n in path if not n.startswith('built:') and n not in parts]
        out[mode] = dict(path=path, missing=missing)
    return out


def topology(s):
    """E02 checks per candidate: BYPASS (and every non-study mode) is exactly the built line; PREHEAT goes through the cassette; HX
    fault isolation closes the hot branch and both H2 branch valves; no HR part ends inside a tank or the plasma; every part is tagged."""
    res = {}
    for key, build in CANDIDATES.items():
        parts = build(s); fails = []
        for j in H2_LINES:
            paths = h2_paths(s, key, j)
            for mode in ('BYPASS', 'BRAYTON_BASELINE', 'NO_DATA', 'HX_FAULT_ISOLATED'):
                if paths[mode]['path'] != ['built:tank_cap..branch_in', 'built:branch_in..branch_out', 'built:branch_out..injection_ring']:
                    fails.append(f'L{j} {mode} is not the built line')
            if 'HX_Core' not in paths['PREHEAT_STUDY']['path'] or 'built:branch_in..branch_out' in paths['PREHEAT_STUDY']['path']:
                fails.append(f'L{j} PREHEAT does not pass the cassette alone')
            fails += [f'L{j} {m} missing {paths[m]["missing"]}' for m in paths if paths[m]['missing']]
            for nm in ('H2_Preheat_Feed', 'H2_Preheat_Return'):
                pt = next(p for p in parts if p['name'] == f'HR_{key}_L{j}_{nm}')
                ends = (pt['points'][0], pt['points'][-1]); L = line_of(s, j)['points']
                on_line = [min(dm.point_segment(q, a, b) for a, b in zip(L, L[1:])) for q in ends]
                if min(on_line) > 1e-6:
                    fails.append(f'L{j} {nm} does not join the built line')
        g = dm.geometry(s); inner = [(n, f) for n, f in obstacles(s, 0) if n.startswith('Tank_Volume') or n in ('Fusion_Core', 'Common_Plasma_Region')]
        for p in parts:
            if p['kind'] in ('hot', 'tap'):
                continue
            pts, rad = samples(p)
            for n, f in inner:
                if min(f(q) for q in pts)-rad < 0:
                    fails.append(f'{p["name"]} enters {n}')
            if not p['name'].startswith(f'HR_{key}_') or not p.get('role'):
                fails.append(f'{p["name"]} untagged')
        res[key] = dict(result='PASS' if not fails else 'FAIL', failures=fails, modes=MODES,
                        removable='every part is an HR_ overlay object; the built feed lines, ring and envelopes are never edited')
    return res




# ---------- clearance screen ------------------------------------------------------------------------------------------------------------

def samples(part, step=0.1):
    """Points on a part and the radius to subtract (surface points for boxes, axis points for pipes and nodes)."""
    if part['shape'] == 'node':
        return [part['point']], part['radius']
    if part['shape'] == 'pipe':
        pts = []
        for a, b in zip(part['points'], part['points'][1:]):
            n = max(1, math.ceil(dm.norm(dm.sub(b, a))/step))
            pts += [tuple(u+(v-u)*k/n for u, v in zip(a, b)) for k in range(n+1)]
        return pts, part['radius']
    a = math.radians(part['deg']); out = []
    nx, nr, nw = (max(2, math.ceil(v/step)+1) for v in (part['x1']-part['x0'], part['r1']-part['r0'], part['width']))
    for i in range(nx):
        x = part['x0']+(part['x1']-part['x0'])*i/(nx-1)
        for k in range(nr):
            r = part['r0']+(part['r1']-part['r0'])*k/(nr-1)
            for m in range(nw):
                w = -part['width']/2+part['width']*m/(nw-1)
                if i in (0, nx-1) or k in (0, nr-1) or m in (0, nw-1):
                    out.append((x, r*math.cos(a)-w*math.sin(a), r*math.sin(a)+w*math.cos(a)))
    return out, 0.0


def cyl_sdf(q, a, b, radius):
    """Signed distance from q to a flat-ended cylinder a->b (negative inside)."""
    d = dm.sub(b, a); L = dm.norm(d); e = tuple(c/L for c in d); v = dm.sub(q, a); t = dm.dot(v, e)
    radial_d = dm.norm(dm.sub(v, tuple(c*t for c in e)))-radius; axial = max(-t, t-L)
    return min(max(radial_d, axial), 0.0)+math.hypot(max(radial_d, 0.0), max(axial, 0.0))


def box_sdf(q, center, size):
    d = [abs(a-c)-h/2 for a, c, h in zip(q, center, size)]
    return min(max(d), 0.0)+math.sqrt(sum(max(v, 0.0)**2 for v in d))


def obstacles(s, j_line):
    """Fixed built members the branch must clear, as (name, signed-distance function): every member a cryogenic feed line must clear
    (drive_hot_section.feed_members: tanks, Brayton, packs, spine hub, optical bores, lasers, beams, mirrors, heads, injection ring,
    reactor / common / manifold envelopes), the other feed lines and the hull inner wall. The H2 line the branch joins is excluded on
    purpose; the slab is reported separately (only declared dog-leg sleeves may cross it). Members of one name keep their minimum."""
    g = dm.geometry(s); out = []
    for name, kind, pay in hs.feed_members(s, g):
        name = name.split('[')[0]
        if kind == 'cylinder':
            a, b, r = pay; f = (lambda q, a=a, b=b, r=r: cyl_sdf(q, a, b, r)) if dm.norm(dm.sub(b, a)) > 1e-9 else (lambda q, a=a, r=r: dm.norm(dm.sub(q, a))-r)
        elif kind == 'box':
            f = lambda q, c=pay[0], sz=pay[1]: box_sdf(q, c, sz)
        elif kind == 'envelope':
            x0, x1, r = pay; f = lambda q, x0=x0, x1=x1, r=r: cyl_sdf(q, (x1, 0, 0), (x0, 0, 0), r)
        else:
            f = lambda q, pk=pay: ps.point_box(q, pk)
        out.append((name, f))
    out.append(('Hull_Inner_Wall', lambda q: hull_geometry.inner_radius_at(s, q[0])-math.hypot(q[1], q[2])))
    for L in hs.cryo_feed(s):
        if L['index'] == j_line:
            continue
        pts = L['points']
        out.append((L['name'], lambda q, pts=pts, r=L['radius']: min(dm.point_segment(q, a, b) for a, b in zip(pts, pts[1:]))-r))
    return out


def slab_crossings(s, part):
    """Pipe legs crossing the shadow-shield slab: (count, open sight lines through the sleeve bore by the drive_hot_section rule)."""
    if part['shape'] != 'pipe':
        return None
    st = dm.stations(s); xs = [q[0] for q in part['points']]
    if not (min(xs) < st['shield_aft'] and max(xs) > st['shield_fwd']):
        return None
    line = dict(points=part['points'], sleeve_radius=part['radius']+s['drive_hot_section']['cryo_feed_sleeve_gap_m'])
    return hs.sleeve_sight_lines(line, st['shield_aft'], st['shield_fwd'], n=12, samples=40)


def shadowed(s, q):
    """True when every straight line from the reactor envelope's forward rim to q passes the shadow-shield disc (q forward of it)."""
    st = dm.stations(s); p = s['prototype']; R = p['shadow_radius_m']
    if q[0] <= st['shield_fwd']:
        return False
    for k in range(24):
        a = 2*math.pi*k/24; c = (st['core_fwd'], p['reactor_radius_m']*math.cos(a), p['reactor_radius_m']*math.sin(a))
        for x in (st['shield_aft'], st['shield_fwd']):
            t = (x-c[0])/(q[0]-c[0]); y, z = c[1]+t*(q[1]-c[1]), c[2]+t*(q[2]-c[2])
            if math.hypot(y, z) > R:
                return False
    return True


def path_length(points):
    return sum(dm.norm(dm.sub(b, a)) for a, b in zip(points, points[1:]))


def screen(s):
    st = dm.stations(s); lat = dict(fwd=st['lattice_fwd'], aft=st['lattice_aft']); result = {}
    for key, build in CANDIDATES.items():
        parts = build(s); per_obstacle = {}; worst = []; crossings = []; shadow = []
        for part in parts:
            j = int(part['name'].split('_L')[1][0])
            pts, rad = samples(part)
            for name, f in obstacles(s, j):
                if part['kind'] in ('hot', 'tap') and name == 'Fusion_Core':
                    continue                                                     # the hot branch connects to the drive by intent
                gap = min(f(q) for q in pts)-rad
                if name not in per_obstacle or gap < per_obstacle[name]['gap_m']:
                    per_obstacle[name] = dict(gap_m=round(gap, 3), part=part['name'])
            c = slab_crossings(s, part)
            if c is not None:
                crossings.append(dict(part=part['name'], open_sight_lines=c))
            else:
                xs = [q[0] for q in pts]
                if not (min(xs) < st['shield_aft'] and max(xs) > st['shield_fwd']) and min(xs) <= st['shield_fwd'] and max(xs) >= st['shield_aft']:
                    crossings.append(dict(part=part['name'], open_sight_lines=None, error='part inside the slab without a sleeve'))
            if part['kind'] == 'hx_core' or (part['kind'] in ('valve', 'sensor') and '_H2_' in part['name']):
                shadow.append(all(shadowed(s, q) for q in pts))
        hx = [p for p in parts if p['kind'] == 'hx_core']; inj = hs.injection_ring(s)
        h2_out = [p for p in parts if p['name'].endswith('H2_Preheat_Return')]
        hot_h2_run = []
        for p in h2_out:
            j = int(p['name'].split('_L')[1][0]); L = line_of(s, j); end = p['points'][-1]
            rest = [q for q in L['points'] if q[0] < end[0]-1e-6] if key == 'A' else []
            hot_h2_run.append(round(path_length(p['points'])+path_length([end]+rest), 2))
        inter = [p for p in parts if p['kind'] == 'intermediate']
        result[key] = dict(
            parts=len(parts), worst_gap_m=round(min(v['gap_m'] for v in per_obstacle.values()), 3),
            gaps=dict(sorted(per_obstacle.items(), key=lambda kv: kv[1]['gap_m'])),
            new_slab_sleeves=len(crossings), slab_crossings=crossings,
            preheater_shadowed=all(shadow) if shadow else False,
            preheated_h2_run_m=hot_h2_run, intermediate_loop_run_m=[round(path_length(p['points']), 2) for p in inter],
            preheater_to_lattice_m=round(min(p['x1'] for p in hx)-lat['fwd'], 2),
            preheater_to_common_region_axial_m=round(min(p['x1'] for p in hx)-st['common_fwd'], 2) if key == 'A' else 0.0,
        )
    result['topology'] = topology(s); result['selected'] = SELECTED
    result['hold'] = ['plasma / seed-field / magnetic exclusion envelopes (R2, OD-022..028): not defined, so no mesh margin counts as clearance',
                      'neutron and gamma dose at each location, H2 and hot-fluid activation: OPEN (shadow screen is geometric only)',
                      'interior hot-loop route from the drive to the radiator chases (X -18.5 m): not modelled; the tap is a labelled node',
                      'H2 conditioning point and inlet T/p/phase: OPEN; the branch assumes conditioning at the tank aft cap',
                      'duty, pinch, pressure drop, mass, materials, H2 embrittlement and leak class: OPEN (HR-P12, HR-P15)',
                      'crew and drone access into the engineering bay or the drive annulus: no route or hatch is built (SP-49 / DS-14 unrelated)']
    return result


# ---------- Blender overlay -------------------------------------------------------------------------------------------------------------

def spec(s):
    return s


def apply(s, state=None, which=('A', 'B')):
    import bpy
    from mathutils import Vector
    from common import material
    mats = {k: material(f'ART_HR_{k}', v) for k, v in PALETTE.items()}
    for key in which:
        for part in CANDIDATES[key](s)+debug_links(s, key):
            if part['shape'] == 'box':
                c = part['corners']; faces = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
                me = bpy.data.meshes.new(part['name']); me.from_pydata(c, [], faces); me.update(); me.materials.append(mats[part['kind']])
                ob = bpy.data.objects.new(part['name'], me)
            elif part['shape'] == 'pipe':
                cu = bpy.data.curves.new(part['name'], 'CURVE'); cu.dimensions = '3D'; cu.bevel_depth = part['radius']; cu.bevel_resolution = 2
                sp = cu.splines.new('POLY'); sp.points.add(len(part['points'])-1)
                for pt, q in zip(sp.points, part['points']):
                    pt.co = (*q, 1.0)
                cu.materials.append(mats[part['kind']]); ob = bpy.data.objects.new(part['name'], cu)
            else:
                bpy.ops.mesh.primitive_uv_sphere_add(radius=part['radius'], location=part['point'], segments=12, ring_count=8)
                ob = bpy.context.active_object; ob.name = part['name']; ob.data.materials.append(mats[part['kind']])
                bpy.context.scene.collection.objects.unlink(ob) if ob.name in bpy.context.scene.collection.objects else None
            bpy.context.scene.collection.objects.link(ob) if ob.name not in bpy.context.scene.collection.objects else None
            ob['geometry_status'] = 'PROTOTYPE'; ob['study'] = 'hr001_packaging'; ob['candidate'] = key; ob['role'] = part['role']


SUBSYSTEMS = ('WF_PROPULSION', 'WF_POWER_STORAGE', 'WF_STORAGE', 'WF_SHIELDING', 'WF_STRUCTURE', 'WF_HULL', 'WF_DEBUG_MAGNETICS')


def renders(s, out, size):
    """Cutaway of the aft bay: the subsystem assets' objects inside X -100..-55 m and r < 5.95 m (the hull skin and everything outboard
    left out), with the study parts."""
    import bpy
    from mathutils import Vector, Matrix
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene; shown = []
    for name in SUBSYSTEMS:
        path = ROOT/'assets/wayfarer/subsystems'/f'{name}.blend'
        with bpy.data.libraries.load(str(path), link=False) as (src, dst):
            dst.objects = list(src.objects)
        for ob in dst.objects:
            if ob is None or ob.type not in ('MESH', 'CURVE'):
                continue
            pts = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
            lo, hi = min(p.x for p in pts), max(p.x for p in pts); rad = max(max(abs(p.y), abs(p.z)) for p in pts)   # box half-width, not corner radius
            if hi > -100 and lo < -55 and rad < 5.95 and not any(k in ob.name for k in ('Hull', 'Skin', 'Shell', 'Engineering_Envelope')):
                sc.collection.objects.link(ob); shown.append(ob.name)
    apply(s)
    sc.render.engine = 'BLENDER_WORKBENCH'; sh = sc.display.shading; sh.light = 'STUDIO'; sh.color_type = 'MATERIAL'; sh.show_cavity = True
    sh.show_backface_culling = False
    if sc.world is None:
        sc.world = bpy.data.worlds.new('ART_HR_World')
    sc.world.color = (.055, .075, .10)
    sc.render.resolution_x, sc.render.resolution_y = size, round(size*.75); sc.render.image_settings.file_format = 'PNG'
    cam = bpy.data.objects.new('ART_HR_Camera', bpy.data.cameras.new('ART_HR_Camera')); sc.collection.objects.link(cam); sc.camera = cam
    cam.data.clip_start = 0.05; cam.data.clip_end = 500
    P = lambda x, r, deg: Vector(radial(x, r, deg))
    views = {   # name: (camera, target, lens); both hydrogen lines are on the -Z side (225 and 315 deg)
        'overview': (P(-60, 26, 270), P(-82, 0, 270), 32),
        'candidate_a': (P(-66, 13, 300), P(-77.5, 4.0, 280), 30),
        'candidate_b': (P(-80, 13, 300), P(-90.5, 4.0, 280), 30),
        'side': (P(-80, 45, 270), P(-80, 0, 270), 40),
    }
    paths = []
    for name, (loc, look, lens) in views.items():
        z = (loc-look).normalized(); up = Vector((1, 0, 0)) if abs(z.x) < .9 else Vector((0, 0, 1))
        x = up.cross(z).normalized(); y = z.cross(x)
        cam.location = loc; cam.rotation_euler = Matrix((x, y, z)).transposed().to_euler(); cam.data.lens = lens
        p = out/f'hr001_{name}.png'; sc.render.filepath = str(p); bpy.ops.render.render(write_still=True); paths.append(p.name)
        print('WF_HR001', name, flush=True)
    print('WF_HR001 shown', len(shown), sorted(shown)[:80], flush=True)
    return paths


def main(out=None, size=1280):
    s = load(ROOT)[0]; result = dict(study='HR-001 packaging A/B (TODO E01; NONCANON, PROTOTYPE, nothing saved)', screen=screen(s))
    if out is None:
        print(json.dumps(result, indent=1)); return result
    out.mkdir(parents=True, exist_ok=True)
    result['renders'] = renders(s, out, size)
    (out/'hr001_packaging.json').write_text(json.dumps(result, indent=1)+'\n')
    print('WF_HR001 done', out, flush=True)
    return result


if __name__ == '__main__':
    argv = sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
    ap = argparse.ArgumentParser(); ap.add_argument('--out', type=Path); ap.add_argument('--size', type=int, default=1280)
    a = ap.parse_args(argv)
    main(None if a.out is None else (a.out if a.out.is_absolute() else ROOT/a.out), a.size)
