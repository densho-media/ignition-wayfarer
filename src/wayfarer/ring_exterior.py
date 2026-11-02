"""Habitat ring exterior production module (Phase 4 S4, PROTOTYPE, standard library only): the 15 deg segment module of the selected
exterior grammar (VC+ moderated, owner S1 art gate 2026-10-24; Art Style Bible Spacecraft row 19), shared by the detail packs
ring_a_exterior (WF-RING-A) and ring_b_exterior (WF-RING-B). Each pack calls elements() with its own parameters and its ring; the pure
geometry is in the rotor frame (habitat_ring's ring-local frame: u along the ship axis, then r cos t, r sin t), so the detail turns with
the ring.

Function: make each ring read as an assembled, maintained, inhabited pressure structure from the whole-ship to the human scale by value
and rhythm, never by size (owner 2026-10-24: no enlargement, no move, no unsupported mechanism). Per 15 deg assembly segment, on both
flanks of the frame: light replaceable shell cassettes (calm fields), a mid-value joint cap either side of every joint over a dark joint
gap (the frame rhythm), a graphite node housing with an ochre service cover where a structural spoke meets the frame, a calm shell
panel over each pressure face in its recess, a muted amber occupancy band over the pressurized segments, the text-only sector ID
(A1..A3, B1..B3) with a short GU deep-blue identifier bar under it (functional wayfinding for EVA and drone approach). Each ring's
detail is two assemblies, the +u (forward) and -u (aft) flank, so each claims only the space between the frame flank and the sweep.
Fixed (read, never changed): the frame (r 24.5-30.0 m, |u| <= 2.0 m), the 2.15 m sweep half-depth, the sector pressure envelopes, the
spokes, crew tubes and hub, the M4 construction inside the frame (joints, webs, cassettes, covers, nodes, rim band). Unknown and not
modelled: frame section and load path (OD-016), shielding or mass credit, cassette withdrawal, utility routing (all OPEN).
"""
import math
import habitat_ring as hr
import production_detail as pd


def frame(s):
    r = s['habitat_ring']
    return dict(R0=r['frame_inner_radius_m'], RS0=r['sector_inner_radius_m'], RS1=r['sector_outer_radius_m'], RO=hr.outer(s),
                H=r['frame_axial_m']/2, HS=r['sector_axial_m']/2, half=hr.sector_arc(s)/2, sweep=hr.sweep_half(s),
                seg=math.radians(r['construction']['segment_deg']))


def solid(assembly, family, name, material, cls, function, u0, u1, r0, r1, t0, t1, n=None):
    k = n or max(2, math.ceil(abs(t1-t0)/math.radians(1.5)))
    vs, fs = hr.ring_solid(u0, u1, r0, r1, t0, t1, k)
    return pd.element(assembly, family, name, material, cls, function, vs, fs)


def elements(s, q, ring, assembly, sgn):
    """Every element on one flank (sgn +1: +u, forward; -1: -u, aft) of ring `ring` (1 or 2) for the pack parameters q."""
    g = frame(s); out = []; letter = 'AB'[ring-1]
    sectors = [x['angle'] for x in hr.sectors(s) if x['ring'] == ring]
    spokes = sorted({x['angle'] for x in hr.spokes(s) if x['ring'] == ring and not x['crew']})
    R0, RS0, RS1, RO, H, HS = g['R0'], g['RS0'], g['RS1'], g['RO'], g['H'], g['HS']
    gap = lambda m, r: m/2/r
    flank = lambda sgn, d0, d1: tuple(sorted((sgn*(H+d0), sgn*(H+d1))))
    hs = pd.marking_height(s, 'sector_id')
    for k in range(round(math.tau/g['seg'])):
        c = g['seg']*k; a, b = c-g['seg']/2, c+g['seg']/2; tag = f'Prod_Ring{letter}_S{k:02}'
        pressure = any(abs(math.remainder(c-x, math.tau)) < 1e-6 for x in sectors)
        node = next((x for x in spokes if abs(math.remainder(c-x, math.tau)) < 1e-6), None)
        sid = next((i+1 for i, x in enumerate(sectors) if abs(math.remainder(c-x, math.tau)) < 1e-6), None)
        for _ in (sgn,):
            side = 'F' if sgn > 0 else 'A'
            # light replaceable shell cassettes on the flank, between the joint caps, split round a spoke node and the pressure recess
            u0, u1 = flank(sgn, *q['cassette_u_m'])
            spans = [(R0+.05, RS0-.02), (RS1+.02, RO-.05)] if pressure else \
                [(R0+.05, RS0+q['node_height_m']+.02), (RS0+q['node_height_m']+.06, RO-.05)] if node is not None else [(R0+.05, RO-.05)]
            for r0, r1 in spans:
                lo, hi = a+gap(q['cassette_joint_gap_m'], r1), b-gap(q['cassette_joint_gap_m'], r1)
                nh = math.radians(q['node_half_deg']+.1)
                pieces = [(lo, node-nh), (node+nh, hi)] if node is not None and r0 < RS0+q['node_height_m'] else [(lo, hi)]
                for i, (p0, p1) in enumerate(pieces):
                    out.append(solid(assembly, 'cassettes', f'{tag}_{side}_Cassette_{r0:.0f}_{i}', 'xf_shell', 'ENGINEERING_FLEXIBLE',
                                     'flank shell cassette (replaceable module; withdrawal OPEN)', u0, u1, r0, r1, p0, p1))
            if pressure:
                # the pressure face in its recess: one calm shell panel per side, off the sector skin
                d = H-HS; u0, u1 = flank(sgn, -d+q['pressure_panel_gap_m'], -d+q['pressure_panel_gap_m']+q['pressure_panel_m'])
                out.append(solid(assembly, 'cassettes', f'{tag}_{side}_PressureFace', 'xf_shell', 'ENGINEERING_FLEXIBLE',
                                 'pressure-sector face cladding (no shielding claim)', u0, u1, RS0+.15, RS1-.15,
                                 c-g['half']+gap(.3, RS0), c+g['half']-gap(.3, RS0)))
                u0, u1 = flank(sgn, q['cassette_u_m'][1], q['cassette_u_m'][1]+q['film_m'])
                r0, r1 = RO-q['band_r_m'][1], RO-q['band_r_m'][0]
                out.append(solid(assembly, 'occupancy', f'{tag}_{side}_Band', 'xf_amber', 'ARTISTIC', 'occupancy band over the pressurized segment',
                                 u0, u1, r0, r1, a+gap(q['cassette_joint_gap_m'], RO), b-gap(q['cassette_joint_gap_m'], RO)))
            if 'index_r_m' in q and not pressure:
                out += spin_index(s, q, g, assembly, tag, side, sgn, a, b)
            if pressure and 'viewport_count' in q:
                out += viewports(s, q, g, assembly, tag, side, sgn, c, k)
            # the frame rhythm: a mid-value joint cap either side of each joint over a dark joint gap (each segment owns the joint at its
            # start angle, so every joint is built once)
            for t in (a,):
                u0, u1 = flank(sgn, 0, q['joint_cap_u_m'])
                w0, w1 = q['joint_gap_m']/2, q['joint_gap_m']/2+q['joint_cap_m']
                for i, (p0, p1) in enumerate(((t-gap(2*w1, RS0), t-gap(2*w0, RS0)), (t+gap(2*w0, RS0), t+gap(2*w1, RS0)))):
                    out.append(solid(assembly, 'joints', f'{tag}_{side}_JointCap_{t:.3f}_{i}', 'xf_structure', 'ENGINEERING_FLEXIBLE',
                                     'segment joint cap over the web frame (exposed structure)', u0, u1, R0, RO-.02, p0, p1, n=1))
                u0, u1 = flank(sgn, 0, q['film_m']*8)
                out.append(solid(assembly, 'joints', f'{tag}_{side}_JointGap_{t:.3f}', 'xf_joint', 'ARTISTIC', 'joint gap',
                                 u0, u1, R0, RO-.02, t-gap(2*w0, RS0), t+gap(2*w0, RS0), n=1))
            if node is not None:
                # where a structural spoke meets the frame: a graphite node housing with an ochre service cover
                nh = math.radians(q['node_half_deg']); u0, u1 = flank(sgn, 0, q['node_u_m'])
                out.append(solid(assembly, 'nodes', f'{tag}_{side}_Node', 'xf_machinery', 'ENGINEERING_FLEXIBLE',
                                 'spoke node housing (exposed machinery; contents OPEN)', u0, u1, R0, RS0+q['node_height_m'], node-nh, node+nh))
                ch = math.radians(q['node_cover_half_deg']); u0, u1 = flank(sgn, q['node_u_m'], q['node_u_m']+q['film_m']*5)
                out.append(solid(assembly, 'nodes', f'{tag}_{side}_NodeCover', 'xf_service', 'ENGINEERING_FLEXIBLE', 'node service cover (ochre)',
                                 u0, u1, R0+.3, RS0+q['node_height_m']-.3, node-ch, node+ch))
            if sid is not None:
                # the text-only sector ID over the outer hoop, read from outside each flank (tangent x radial = -u)
                u = sgn*(H+q['cassette_u_m'][1]+.0025); r = (RS1+RO)/2-.05
                pos = (u, r*math.cos(c), r*math.sin(c)); tang = (0.0, -math.sin(c), math.cos(c)); rad = (0.0, math.cos(c), math.sin(c))
                right = tang if sgn < 0 else tuple(-x for x in tang)
                out.append(pd.lettering(assembly, 'markings', f'{tag}_{side}_ID', 'xf_mark', 'ring sector ID (text only)',
                                        f'{letter}{sid}', pos, right, rad, hs))
                # GU deep-blue identifier bar under the ID (pressure-segment identifier, functional wayfinding)
                bw = q['id_bar_width_m']/2/r; u0, u1 = flank(sgn, q['cassette_u_m'][1], q['cassette_u_m'][1]+q['film_m'])
                rb = r-hs*.7-q['id_bar_gap_m']
                out.append(solid(assembly, 'wayfinding', f'{tag}_{side}_IDBar', 'xf_wayfinding', 'ARTISTIC',
                                 'GU deep-blue pressure-segment identifier (functional wayfinding)', u0, u1, rb-q['id_bar_m'], rb, c-bw, c+bw))
    return out


def local(u, r, w, a):
    """Rotor-frame point at axial u, radius r and tangential offset w (m) from the radial line at angle a."""
    return (u, r*math.cos(a)-w*math.sin(a), r*math.sin(a)+w*math.cos(a))


def lbox(assembly, family, name, material, cls, function, u0, u1, r0, r1, w0, w1, a):
    """A box in the local frame of the radial line at angle a: axial u0..u1, radial r0..r1, tangential w0..w1 (m)."""
    ax = ((1.0, 0.0, 0.0), (0.0, math.cos(a), math.sin(a)), (0.0, -math.sin(a), math.cos(a)))
    vs, fs = pd.box(local((u0+u1)/2, (r0+r1)/2, (w0+w1)/2, a), ax, (u1-u0, r1-r0, w1-w0))
    return pd.element(assembly, family, name, material, cls, function, vs, fs)


def disc(assembly, family, name, material, cls, function, u0, u1, r, w, a, ro, ri=0.0, n=20):
    """A round plate (ri = 0) or annulus whose axis is the ship axis, centred at radius r, tangential offset w from angle a."""
    ring = lambda u, rad: [local(u, r+rad*math.cos(math.tau*j/n), w+rad*math.sin(math.tau*j/n), a) for j in range(n)]
    if ri <= 0:
        vs = ring(u0, ro)+ring(u1, ro)
        fs = [(j, (j+1) % n, n+(j+1) % n, n+j) for j in range(n)]+[tuple(range(n-1, -1, -1)), tuple(range(n, 2*n))]
    else:
        vs = ring(u0, ri)+ring(u0, ro)+ring(u1, ro)+ring(u1, ri)
        fs = [(b*n+j, b*n+(j+1) % n, ((b+1) % 4)*n+(j+1) % n, ((b+1) % 4)*n+j) for b in range(4) for j in range(n)]
    return pd.element(assembly, family, name, material, cls, function, vs, fs)


def spin_index(s, q, g, assembly, tag, side, sgn, a, b):
    """Rotor spin index on the flank's outer edge: the first half of every 15 deg segment outside the pressure segments (those carry
    the amber band, the sector ID and the viewports) carries a charcoal block on the light cassettes, so the ring reads as a turning wheel (and its phase and rate can be read by eye, by drones and by camera) against the
    stationary collar and frame, which never carry it. Paint on the cassette face (film), no structure."""
    RO = g['RO']; u0 = sgn*(g['H']+q['cassette_u_m'][1]); u1 = u0+sgn*q['film_m']; u0, u1 = sorted((u0, u1))
    r0, r1 = RO-q['index_r_m'][1], RO-q['index_r_m'][0]; gp = q['cassette_joint_gap_m']/2/RO
    return [solid(assembly, 'spin_index', f'{tag}_{side}_SpinIndex', 'xf_mark', 'ARTISTIC',
                  'rotor spin index: half-segment charcoal block on the flank edge (rotating parts only)', u0, u1, r0, r1, a+gp, (a+b)/2)]


def viewports(s, q, g, assembly, tag, side, sgn, c, k):
    """Crew viewports in a pressure sector's flank face (in its recess), at standing eye height above the deck. Each is a framed pane
    behind an armoured external shutter that slides toward the hub on two guides; the pane shows the cabin's warm light. PROTOTYPE: the
    pressure-skin penetration, pane stack and shutter drive are OPEN; the flank face has no axial shielding claim to lose."""
    out = []; deck = s['habitat']['floor_radius']['value']; r = deck-q['viewport_eye_m']
    face = sgn*(g['HS']+q['pressure_panel_gap_m']+q['pressure_panel_m'])
    n = q['viewport_count']; pitch = q['viewport_pitch_m']; rc = q['viewport_clear_m']/2; rf = rc+q['viewport_frame_m']
    closed = q['viewport_closed']      # shutter pattern per sector index (crew choice; stable)
    for i in range(n):
        w = (i-(n-1)/2)*pitch; nm = f'{tag}_{side}_Viewport{i}'
        f0, f1 = sorted((face, face+sgn*q['viewport_frame_proud_m']))
        out.append(disc(assembly, 'viewports', nm+'_Frame', 'xf_machinery', 'ENGINEERING_FLEXIBLE', 'viewport frame (pane stack OPEN)',
                        f0, f1, r, w, c, rf, rc))
        p0, p1 = sorted((face, face+sgn*q['viewport_pane_proud_m']))
        out.append(disc(assembly, 'viewports', nm+'_Pane', 'xf_viewport', 'ARTISTIC', 'viewport pane showing the lit cabin', p0, p1, r, w, c, rc))
        shut = closed[(k+i) % len(closed)]
        sr = r if shut else r-q['viewport_shutter_travel_m']
        s0, s1 = sorted((face+sgn*q['viewport_frame_proud_m'], face+sgn*(q['viewport_frame_proud_m']+q['viewport_shutter_m'])))
        hs = q['viewport_shutter_half_m']
        out.append(lbox(assembly, 'viewports', nm+'_Shutter', 'xf_structure', 'ENGINEERING_FLEXIBLE',
                        'armoured external shutter (slides toward the hub; drive OPEN)', s0, s1, sr-hs, sr+hs, w-hs, w+hs, c))
        for gside in (-1, 1):      # the two shutter guides, from the closed to the open position
            gw = w+gside*(hs+.03)
            out.append(lbox(assembly, 'viewports', nm+f'_Guide{gside:+d}', 'xf_structure', 'ENGINEERING_FLEXIBLE', 'shutter guide rail',
                            f0, s1, r-q['viewport_shutter_travel_m']-hs, r+hs, gw-.025, gw+.025, c))
    return out


def spoke_trays(s, q, ring, assembly, deg, part):
    """Rotating service runs from the rotary fluid coupling to the ring: on each structural spoke a graphite tray between the twin rails
    (u = 0) carrying three insulated lines (water, coolant, power/data), clamped every clamp_pitch_m and tied to both rails, with a short
    run along the drum from the coupling face. Routing, line count and sizes are PROTOTYPE (utility routing OPEN); no load path."""
    hr_ = s['habitat_ring']; ri_ = s['rotor_interface']; out = []; t = q['tray']
    r0, r1 = ri_['drum_outer_radius_m']+t['root_gap_m'], hr_['frame_inner_radius_m']-t['end_gap_m']
    rail = hr_['spoke_rail_u_m']-hr_['spoke_rail_radius_m']; split = t['split_r_m']
    lo, hi = (r0, split) if part == 'IN' else (split, r1)      # two assemblies per spoke (inner, outer), so each claims a tight box
    for a in [x for x in sorted({x['angle'] for x in hr.spokes(s) if x['ring'] == ring and not x['crew']}) if round(math.degrees(x)) == deg]:
        nm = f"Prod_Ring{'AB'[ring-1]}_Spoke{round(math.degrees(a)):03d}"; hw = t['width_m']/2; w0 = -t['depth_m']
        out.append(lbox(assembly, 'trays', nm+'_Tray', 'xf_machinery', 'ENGINEERING_FLEXIBLE', 'spoke service tray (rotating side)',
                        -hw, hw, lo, hi, w0, w0+t['wall_m'], a))
        for j, du in enumerate((-hw*.6, 0.0, hw*.6)):
            out.append(lbox(assembly, 'trays', nm+f'_Line{j}', 'xf_insul_line', 'ENGINEERING_FLEXIBLE',
                            'insulated service line (water / coolant / power-data; media OPEN)', du-t['line_m']/2, du+t['line_m']/2, lo, hi,
                            w0+t['wall_m'], w0+t['wall_m']+t['line_m'], a))
        k = 1
        while r0+k*t['clamp_pitch_m'] < r1-.5:
            rc = r0+k*t['clamp_pitch_m']
            if not lo+.1 < rc < hi-.1:
                k += 1; continue
            out.append(lbox(assembly, 'trays', nm+f'_Clamp{k:02d}', 'xf_structure', 'ENGINEERING_FLEXIBLE', 'tray clamp band',
                            -hw-.02, hw+.02, rc-.05, rc+.05, w0-.02, w0+t['wall_m']+t['line_m']+.02, a))
            if k % 2 == 0:
                for sd in (-1, 1):
                    u0_, u1_ = sorted((sd*(hw+.02), sd*(rail+.03)))
                    out.append(lbox(assembly, 'trays', nm+f'_Tie{k:02d}{sd:+d}', 'xf_structure', 'ENGINEERING_FLEXIBLE',
                                    'tray tie to the spoke rail', u0_, u1_, rc-.04, rc+.04, w0, w0+.06, a))
            k += 1
        # the run along the drum from the rotating half of the fluid coupling to the spoke root
        cu = ri_['fluid_coupling']['rotor_u_m'][0]
        if part != 'IN':
            continue
        out.append(lbox(assembly, 'trays', nm+'_DrumRun', 'xf_insul_line', 'ENGINEERING_FLEXIBLE', 'line run along the drum from the rotary coupling',
                        -hw, cu, ri_['drum_outer_radius_m']+.005, r0+t['line_m'], w0+t['wall_m'], w0+t['wall_m']+t['line_m'], a))
    return out


def blankets(s, q, ring, assembly, sgn):
    """Thermal blankets on the frame's inner face (it looks at the axis, the cold tank farm and space): one off-white beta-cloth blanket
    per 15 deg segment, cut back round every spoke root and crew-tube opening. Lay-up and thermal credit OPEN; depiction only."""
    g = frame(s); b = q['blanket']; out = []
    keep = [x['angle'] for x in hr.spokes(s) if x['ring'] == ring]
    for k in range(round(math.tau/g['seg'])):
        a0, a1 = g['seg']*k-g['seg']/2, g['seg']*k+g['seg']/2
        pieces = [(a0+b['gap_m']/2/g['R0'], a1-b['gap_m']/2/g['R0'])]
        for x in keep:
            cut = b['spoke_clear_m']/g['R0']
            pieces = [pp for p0, p1 in pieces for pp in ((p0, min(p1, x-cut)), (max(p0, x+cut), p1)) if pp[1]-pp[0] > 1e-4] \
                if any(p0 < x+cut and x-cut < p1 for p0, p1 in pieces) else pieces
        for i, (p0, p1) in enumerate(pieces):
            u0, u1 = sorted((sgn*b['u_m'][0], sgn*b['u_m'][1]))
            out.append(solid(assembly, 'blankets', f"Prod_Ring{'AB'[ring-1]}_S{k:02}_{'F' if sgn > 0 else 'A'}_Blanket{i}", 'xf_root',
                             'ENGINEERING_FLEXIBLE', 'inner-face thermal blanket (lay-up OPEN)', u0, u1, g['R0']-b['thickness_m'], g['R0'], p0, p1))
    return out


def check_hub(s, els, ring):
    """Trays and blankets stay inside the ring's own rotating envelope: |u| <= the sweep, r <= the frame inner radius, and off the crew
    spokes' tube keep-out (no element within the spoke rail half-angle of a crew spoke)."""
    g = frame(s); eps = 1e-6; fails = []
    crew = [x['angle'] for x in hr.spokes(s) if x['ring'] == ring and x['crew']]
    for q in els:
        for u, y, z in q['vs']:
            rr = math.hypot(y, z)
            if abs(u) > g['sweep']+eps or rr > g['R0']+eps or rr < s['rotor_interface']['drum_outer_radius_m']-eps:
                fails.append(f"{q['name']}: outside the rotating hub/spoke envelope at u {u:.3f}, r {rr:.3f}"); break
        if 'Blanket' in q['name']:
            continue
        ts = [math.atan2(z, y) for _, y, z in q['vs']]
        if any(abs(math.remainder(t-c, math.tau)) < math.radians(10) for t in ts for c in crew):
            fails.append(f"{q['name']}: on a crew spoke")
    return fails


def check(s, els, ring):
    """Every element inside the frame envelope widened to the sweep (r 24.5 m .. the outer radius, |u| <= the sweep half-depth), off the
    sector pressure envelopes and outside the frame body (|u| >= the frame half-depth) except the panels in the pressure recess."""
    g = frame(s); eps = 1e-6; fails = []
    secs = [q['angle'] for q in hr.sectors(s) if q['ring'] == ring]
    for q in els:
        pts = [q['centre']] if 'text' in q else q['vs']
        for u, y, z in pts:
            rr = math.hypot(y, z)
            if abs(u) > g['sweep']+eps or rr < g['R0']-eps or rr > g['RO']+eps:
                fails.append(f"{q['name']}: outside the frame/sweep envelope at u {u:.3f}, r {rr:.3f}"); break
        if 'text' in q:
            continue
        us = [p[0] for p in pts]; rs = [math.hypot(p[1], p[2]) for p in pts]; ts = [math.atan2(p[2], p[1]) for p in pts]
        for c in secs:
            d = [math.remainder(t-c, math.tau) for t in ts]
            if min(d) < g['half']-eps and max(d) > -g['half']+eps and min(us) < g['HS']-eps and max(us) > -g['HS']+eps \
                    and min(rs) < g['RS1']-eps and max(rs) > g['RS0']+eps:
                fails.append(f"{q['name']}: enters a sector pressure envelope"); break
        if not q['name'].endswith('_PressureFace') and '_Viewport' not in q['name'] and min(abs(u) for u in us) < g['H']-eps:
            fails.append(f"{q['name']}: inside the frame body (|u| < {g['H']:g} m)")
    return fails
