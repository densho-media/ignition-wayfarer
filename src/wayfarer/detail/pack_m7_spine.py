"""Detail pack m7_spine (docs/MODULES.md): the boarding path through the stationary body, module WF-SPINE. M7.EXT.PORT (the primary port's
service covers and identification on the hull) and M7.ENT (the entry chamber and trunk node's wall panels, bulkhead faces and light
housings) on the anchor WF-SPINE.SERVICE.ORIGIN; M7.TRK (the stationary crew trunk's panels, trays and light housings) on
WF-SPINE.CREW_TRANSFER.ORIGIN. Both anchors are their host collection's origin, so each detail asset is built in the vehicle frame, exactly
where the host built it before.

Owned with data/detail/m7_spine.toml (manifest, [params.port] and [params.bulkhead]) and the generated assets
assets/wayfarer/detail/WF_DETAIL_M7_EXT_PORT.blend, WF_DETAIL_M7_ENT.blend and WF_DETAIL_M7_TRK.blend. Accepted by the owner on 2026-10-20
with the M7 section (L4_VISUAL_ACCEPTED, scope M7); migrated unchanged from production_detail.py (MOD phase 2). Reads human_entry,
route_fitout, crew_transfer and hull_geometry and the shared M7 panel grammar [production.entry]; changes none of them. The clear route, the
hatches, the valves' floor, the docking aids, the capture ring and every pressure boundary stay as they are.
"""
import math
import production_detail as pd

PACK = 'm7_spine'


# M7.ENT: the entry chamber and the trunk node (dock-local frame of human_entry: a along the port's outward radial, rho and phi across it).
def entry_keepouts(s, f):
    """(zone, a0, a1, phi0, phi1) wall windows the production layer must leave: route_fitout's taken windows (parked leaves, light strips,
    panels), every fit-out wall pd.element (bands, stringers, grilles, chase, locker; the frames bound the bays instead) and the angular
    footprint of every wall-mounted pd.rod (handrail brackets, handholds, handles, foot restraint, chase lines) widened by its radius."""
    import human_entry as he
    import route_fitout as rf
    out = list(rf.blocked(s, f)); R = he.stations(s, f)['chamber_r']
    for q in rf.elements(s, f):
        fp = rf.footprint(s, f, q)
        if fp and '_Frame_' not in q['name']:
            out.append(fp[:5])
    rods = [q for q in he.fixtures(s, f) if q['shape'] == 'rod']+[q for q in rf.elements(s, f) if q['shape'] == 'rod']
    ext = rf.extents(s, f)
    for q in rods:
        loc = [he.local(f, v) for v in q['points']]
        if min(r for _, r, _ in loc) < R-.12:
            continue                                     # valves stand off the wall: no wall footprint
        pad = math.degrees((q['radius']+.02)/R); a0 = min(a for a, _, _ in loc)-q['radius']-.02; a1 = max(a for a, _, _ in loc)+q['radius']+.02
        ph = [math.degrees(p) % 360.0 for _, _, p in loc]; lo, hi = min(ph), max(ph)
        if hi-lo > 180.0:
            ph = [x-360.0 if x > 180.0 else x for x in ph]; lo, hi = min(ph), max(ph)
        for zone, (r, b0, b1) in ext.items():
            if a0 < b1 and b0 < a1:
                out.append((zone, a0, a1, lo-pad, hi+pad))
    return out


def entry_bays(s, f, zone):
    """Axial bays of a zone between the route_fitout frame stations."""
    import route_fitout as rf
    r, a0, a1 = rf.extents(s, f)[zone]
    cuts = sorted({(q['a'][0], q['a'][1]) for q in rf.elements(s, f) if q['shape'] == 'arc' and f"_{zone.title()}_Frame_" in q['name']})
    edges = [a0]+[x for c in cuts for x in c]+[a1]
    return [(edges[2*i], edges[2*i+1]) for i in range(len(edges)//2)]


@pd.builder('M7.ENT')
def entry_elements(s):
    """Replaceable wall-panel modules in every free bay of the chamber and node walls (seams, four quarter-turn fasteners each), and housings
    round the light strips. Panels are thin skins on the shell's inner face, inside the frames' depth, so the clear route is unchanged."""
    import human_entry as he
    import route_fitout as rf
    q = s['production']['entry']; f = he.ports(s)[0]; R = he.stations(s, f)['chamber_r']; out = []
    at = lambda a, r, ph: he.world(f, a, r, ph)
    keep = entry_keepouts(s, f); seam = q['seam_m']; t0, t1 = R-q['panel_back_gap_m']-q['panel_thickness_m'], R-q['panel_back_gap_m']
    gap = math.degrees(seam/R)
    for zone in rf.ZONES:
        for b, (a0, a1) in enumerate(entry_bays(s, f, zone), 1):
            wins = [(lo, hi) for z, w0, w1, lo, hi in keep if z == zone and w0 < a1-seam and a0+seam < w1]
            for k, (p0, p1) in enumerate(pd.windows_free(wins, -180.0, 180.0, gap), 1):
                n = max(1, math.ceil((p1-p0)/q['panel_max_deg']))
                if (p1-p0)/n < q['panel_min_deg']:
                    continue
                # The carrier tray: a dark rail under the panel run the fasteners lock into; it is what the seams show.
                vs, fs = pd.bent(at, a0+seam/2, a1-seam/2, t1, R-.0003, p0+gap/4, p1-gap/4)
                out.append(pd.element('M7.ENT', 'Trays', f"ENT_{zone.title()}_B{b}_T{k}", 'gasket', 'ENGINEERING_FLEXIBLE',
                                   'panel carrier tray and seam gasket', vs, fs))
                for i in range(n):
                    lo = p0+(p1-p0)*i/n+gap/2; hi = p0+(p1-p0)*(i+1)/n-gap/2; s0, s1 = a0+seam, a1-seam
                    name = f"ENT_{zone.title()}_B{b}_P{k}_{i+1}"; deck = 135.0 <= (lo+hi)/2 % 360.0 <= 225.0
                    vs, fs = pd.bent(at, s0, s1, t0, t1, lo, hi)
                    out.append(pd.element('M7.ENT', 'Panels', name, 'panel_service' if deck else 'panel_inhabited', 'ENGINEERING_FLEXIBLE',
                                       'replaceable wall panel module (service access to the shell and lines behind)', vs, fs, bevel=q['panel_bevel_m']))
                    st = q['fastener_m']; inset = q['fastener_inset_m']; dphi = math.degrees(inset/R)
                    for sa in (s0+inset, s1-inset):
                        for sp in (lo+dphi, hi-dphi):
                            vs, fs = pd.bent(at, sa-st/2, sa+st/2, t0-q['fastener_proud_m'], t0, sp-math.degrees(st/2/R), sp+math.degrees(st/2/R), n=1)
                            out.append(pd.element('M7.ENT', 'Fasteners', name+f'_F{len(out)}', 'fastener', 'ENGINEERING_FLEXIBLE',
                                               'quarter-turn panel fastener', vs, fs))
    # Bulkhead faces: an annulus of radial panel segments between the hatch-frame mark and the wall, off the hinge and leaf, the
    # placards and the equalization valves; they face the chamber (outer bulkhead) or the chamber and the node (inner bulkhead).
    st = he.stations(s, f); bh = pd.params(s, PACK)['bulkhead']
    faces = [('Outer', st['a_out'], -1.0, s['human_entry']['outer_hinge_deg']), ('Inner', st['a_in'], 1.0, None),
             ('Node', st['node_in'], 1.0, s['human_entry']['inner_hinge_deg'])]
    valves = [math.degrees(he.local(f, v['points'][0])[2]) for v in he.fixtures(s, f) if 'valve' in v['role']]
    for tagname, a, side, hinge in faces:
        wins = [(d-bh['valve_keep_deg'], d+bh['valve_keep_deg']) for d in valves]+[(d-bh['placard_keep_deg'], d+bh['placard_keep_deg']) for d in (0.0, 180.0)]
        if hinge is not None:
            wins.append((hinge-bh['hinge_keep_deg'], hinge+bh['hinge_keep_deg']))
        r0, r1 = bh['inner_m'], R-.004; d0, d1 = (a+side*.0015, a+side*(.0015+q['panel_thickness_m']))
        for k, (p0, p1) in enumerate(pd.windows_free(wins, -180.0, 180.0, gap), 1):
            n = max(1, math.ceil((p1-p0)/bh['segment_max_deg']))
            for i in range(n):
                lo = p0+(p1-p0)*i/n+gap/2; hi = p0+(p1-p0)*(i+1)/n-gap/2
                vs, fs = pd.bent(lambda u, r, ph: at(u, r, ph), min(d0, d1), max(d0, d1), r0, r1, lo, hi)
                out.append(pd.element('M7.ENT', 'Bulkhead', f'ENT_Bulkhead_{tagname}_{k}_{i+1}', 'panel_inhabited', 'ENGINEERING_FLEXIBLE',
                                   'bulkhead face panel (access to the hatch-frame seal land bolts)', vs, fs, bevel=q['panel_bevel_m']))
    # Housings: two lips along each light strip's long edges and two end caps, so the emitter reads as a recessed, serviceable fixture.
    for fx in (x for x in he.fixtures(s, f) if x['role'] == 'light strip'):
        a, rho, phi = fx['centre']; la, lt, lr = fx['size']; lip, h = q['housing_lip_m'], q['housing_depth_m']; dp = math.degrees((lt/2+lip)/R)
        for side, (lo, hi) in enumerate(((math.degrees(phi)-dp, math.degrees(phi)-dp+math.degrees(lip/R)),
                                         (math.degrees(phi)+dp-math.degrees(lip/R), math.degrees(phi)+dp)), 1):
            vs, fs = pd.bent(at, a-la/2-lip, a+la/2+lip, R-h, R-.001, lo, hi, n=1)
            out.append(pd.element('M7.ENT', 'Housings', f"{fx['name']}_Lip_{side}", 'housing', 'ENGINEERING_FLEXIBLE', 'light-strip housing lip', vs, fs, bevel=.002))
        for end, (s0, s1) in enumerate(((a-la/2-lip, a-la/2), (a+la/2, a+la/2+lip)), 1):
            vs, fs = pd.bent(at, s0, s1, R-h, R-.001, math.degrees(phi)-dp, math.degrees(phi)+dp, n=1)
            out.append(pd.element('M7.ENT', 'Housings', f"{fx['name']}_Cap_{end}", 'housing', 'ENGINEERING_FLEXIBLE', 'light-strip housing end cap', vs, fs, bevel=.002))
    return out


def entry_check(s, els):
    """Every pd.element inside its zone, outside the passage (no closer to the axis than the valves already stand) and, for panels and
    fasteners, off every keep-out window."""
    import human_entry as he
    import route_fitout as rf
    f = he.ports(s)[0]; floor = s['human_entry']['valve_rho_m']; ext = rf.extents(s, f); keep = entry_keepouts(s, f); fails = []
    for q in els:
        loc = [he.local(f, v) for v in q['vs']]
        if min(r for _, r, _ in loc) < floor and q['family'] != 'Bulkhead':
            fails.append(f"{q['name']}: inside the valves' {floor:.2f} m")
        a0, a1 = min(a for a, _, _ in loc), max(a for a, _, _ in loc)
        zone = next((z for z, (r, b0, b1) in ext.items() if b0-1e-6 <= a0 and a1 <= b1+1e-6), None)
        if zone is None:
            fails.append(f"{q['name']}: outside the chamber and node walls"); continue
        if q['family'] == 'Bulkhead':
            st = he.stations(s, f)
            if min(r for _, r, _ in loc) < st['r_hinge']+.02 or max(r for _, r, _ in loc) > st['chamber_r']:
                fails.append(f"{q['name']}: not between the hatch frame and the wall")
            continue
        if q['family'] in ('Panels', 'Fasteners', 'Trays'):
            ph = [math.degrees(p) for _, _, p in loc]; lo, hi = min(ph), max(ph)
            if hi-lo > 180.0:
                ph = [x+360.0 if x < 0 else x for x in ph]; lo, hi = min(ph), max(ph)
            for z, w0, w1, wlo, whi in keep:
                import route_fitout as rf2
                if z == zone and a0 < w1 and w0 < a1 and rf2.overlaps((lo+1e-6, hi-1e-6), (wlo, whi)):
                    fails.append(f"{q['name']}: on a keep-out window ({z} a {w0:.2f}-{w1:.2f}, phi {wlo:.0f}-{whi:.0f})"); break
    return fails


pd.CHECKS['M7.ENT'] = entry_check


# M7.EXT.PORT: the primary port from outside (vehicle frame). The capture ring, the port fitting, the hull and the docking aids are
# physics-locked or already built; the layer adds only flush service covers in the accepted M4 grammar (15!A202: ochre covers) and the
# port's identification, outside the visiting vehicle's ~3 m keep-out corridor (Q33) and clear of the approach aids (exterior_hardware).
@pd.builder('M7.EXT.PORT')
def port_elements(s):
    import exterior_hardware as eh
    import human_entry as he
    q = pd.params(s, PACK)['port']; f = he.ports(s)[0]; out = []
    for k, cov in enumerate(q['covers'], 1):
        dx, dt = cov['at_m']; L, W, D = cov['size_m']
        c, a, r = eh.on_hull(s, f['x'], f['theta'], dx, dt, D/2+q['standoff_m'])
        ax = eh.frame(a); vs, fs = pd.box(c, ax, (L, W, D))
        out.append(pd.element('M7.EXT.PORT', 'Covers', f'EXT_Cover_{k}', 'service_ochre', 'ENGINEERING_FLEXIBLE', cov['function'], vs, fs, bevel=.006))
        ins = q['fastener_inset_m']; st = q['fastener_m']
        for i, (sx, sy) in enumerate([(-1, -1), (-1, 1), (1, -1), (1, 1), (0, -1), (0, 1)]):
            fc = tuple(c[j]+sx*(L/2-ins)*ax[0][j]+sy*(W/2-ins)*ax[1][j]+(D/2+st/4)*ax[2][j] for j in range(3))
            vs, fs = pd.box(fc, ax, (st, st, st/2))
            out.append(pd.element('M7.EXT.PORT', 'Fasteners', f'EXT_Cover_{k}_F{i+1}', 'fastener', 'ENGINEERING_FLEXIBLE', 'quarter-turn cover fastener', vs, fs))
        top = tuple(c[j]+(D/2+.0015)*ax[2][j] for j in range(3)); right = tuple(-x for x in ax[1])     # faces outward, fore (+X) up
        out.append(pd.lettering('M7.EXT.PORT', 'Lettering', f'EXT_Cover_{k}_Label', 'wayfinding_blue', 'cover identification stencil', cov['label'],
                             top, right, ax[0], cov['label_m']))
    dx, dt = q['port_id_at_m']; c, a, r = eh.on_hull(s, f['x'], f['theta'], dx, dt, q['standoff_m']+.0015); ax = eh.frame(a)
    out.append(pd.lettering('M7.EXT.PORT', 'Lettering', 'EXT_Port_ID', 'placard', 'port identification for the visiting vehicle and EVA crew',
                         q['port_id'], c, tuple(-x for x in ax[1]), ax[0], q['port_id_m']))
    return out


def port_check(s, els):
    """Covers off the hull opening round the port, inside the window the collar straps already leave round the port's aids (so no
    strap or seam crosses them, casing_panels.collar_keepouts) and clear of every approach aid (exterior_hardware.docking) by a margin."""
    import casing_panels as cp
    import exterior_hardware as eh
    import hull_geometry as hg
    import human_entry as he
    q = pd.params(s, PACK)['port']; f = he.ports(s)[0]; R = hg.radius_at(s, f['x']); fails = []
    wins = sorted(((k[0]-f['x'], k[1]-f['x'], (k[2]-f['theta'])*R, (k[3]-f['theta'])*R) for k in cp.collar_keepouts(s)
                   if k[0] < f['x'] < k[1] and cp.adiff((k[2]+k[3])/2, f['theta']) < .5), key=lambda w: (w[1]-w[0])*(w[3]-w[2]))
    opening, window = wins[0], wins[-1]
    aids = [x for x in eh.docking(s) if x.get('fitting') == f['name']]
    for el in els:
        if el['family'] != 'Covers':
            continue
        cov = q['covers'][int(el['name'].rsplit('_', 1)[1])-1]; dx, dt = cov['at_m']; L, W, _ = cov['size_m']
        lo, hi = (dx-L/2, dt-W/2), (dx+L/2, dt+W/2)
        if lo[0] < opening[1] and opening[0] < hi[0] and lo[1] < opening[3] and opening[2] < hi[1]:
            fails.append(f"{el['name']}: over the port's hull opening")
        if not (window[0] <= lo[0] and hi[0] <= window[1] and window[2] <= lo[1] and hi[1] <= window[3]):
            fails.append(f"{el['name']}: outside the strap-free window round the port")
        for x in aids:
            ox, ot = x['off']; gap = max(abs(ox-dx)-L/2, abs(ot-dt)-W/2)-x.get('half', .1)
            if gap < q['aid_margin_m']:
                fails.append(f"{el['name']}: {gap:.2f} m from {x['name']}")
    return fails


pd.CHECKS['M7.EXT.PORT'] = port_check


# M7.TRK: the stationary trunk (vehicle frame; x along the ship axis, angles as crew_transfer.radial).
def trunk_bays(s):
    """Axial bays between the route_fitout trunk frames (their x extents), over the trunk's length."""
    import route_fitout as rf
    tr, x0, x1 = rf.trunk_extent(s)
    cuts = sorted({tuple(q['x']) for q in rf.trunk_elements(s) if q['shape'] == 'xarc' and '_Frame_' in q['name']})
    edges = [x0]+[x for c in cuts for x in c]+[x1]
    return [(edges[2*i], edges[2*i+1]) for i in range(len(edges)//2) if edges[2*i+1]-edges[2*i] > .1]


def trunk_keepouts(s):
    """(x0, x1, phi0, phi1) windows (degrees) the trunk cladding leaves: the whole-length windows (handrails, lights, ladder), the refuge and
    store ports' rails, the route stripe, every non-frame fit-out pd.element (placards, chevrons, diffuser) widened by a margin."""
    import route_fitout as rf
    tr, x0, x1 = rf.trunk_extent(s); full, local = rf.trunk_windows(s); p = s['route_fitout']; out = [(x0, x1, a, b) for a, b in full]+list(local)
    S, half = p['route_stripe_deg'], p['route_stripe_width_deg']/2
    out.append((x0, x1, S-half-1.0, S+half+1.0))
    for q in rf.trunk_elements(s):
        if '_Frame_' in q['name'] or 'Route_Stripe' in q['name']:
            continue
        if q['shape'] == 'xarc':
            out.append((q['x'][0]-.03, q['x'][1]+.03, q['phi'][0]-2.0, q['phi'][1]+2.0))
        else:
            pts = q['points'] if q['shape'] == 'rod' else pd.wbox_pts(q)
            xs = [v[0] for v in pts]; ph = [math.degrees(math.atan2(v[2], v[1])) for v in pts]; lo, hi = min(ph), max(ph)
            if hi-lo > 180.0:
                ph = [x+360.0 if x < 0 else x for x in ph]; lo, hi = min(ph), max(ph)
            out.append((min(xs)-.05, max(xs)+.05, lo-3.0, hi+3.0))
    return out


def opening_clear(s, R, x0, x1, lo, hi):
    """True when the patch x0..x1, lo..hi (degrees) of the trunk wall stays opening_margin_m clear of every branch opening."""
    import human_entry as he
    for d in (lo, (lo+hi)/2, hi):
        if not any(a <= x0 and x1 <= b for a, b in he.clear_spans(s, R, math.radians(d), x0, x1)):
            return False
    return True


@pd.builder('M7.TRK')
def trunk_elements(s):
    """Replaceable wall-panel modules with trays and fasteners in every free patch of every bay of the trunk wall (off the openings, rails,
    lights, ladder, stripe, placards and chevrons), and housings round the trunk light strips."""
    import crew_transfer as ct
    import human_entry as he
    import route_fitout as rf
    q = s['production']['entry']; R, X0, X1 = rf.trunk_extent(s); at = lambda x, r, a: ct.radial(x, r, a); out = []
    keep = trunk_keepouts(s); gap = math.degrees(q['seam_m']/R)
    for b, (a0, a1) in enumerate(trunk_bays(s), 1):
        wins = [(lo, hi) for w0, w1, lo, hi in keep if w0 < a1 and a0 < w1]
        for k, (p0, p1) in enumerate(pd.windows_free(wins, -180.0, 180.0, gap), 1):
            # split the window at the openings: sub-patches whose three sample angles stay clear of every branch opening
            n = max(1, math.ceil((p1-p0)/q['panel_max_deg']))
            for i in range(n):
                lo, hi = p0+(p1-p0)*i/n, p0+(p1-p0)*(i+1)/n
                if not opening_clear(s, R, a0, a1, lo, hi):
                    continue
                deck = 160.0 <= (lo+hi)/2 % 360.0 <= 200.0
                out += pd.clad_bay('M7.TRK', f'TRK_B{b}_P{k}_{i+1}', at, R, a0, a1, lo, hi, q, 'panel_service' if deck else 'panel_inhabited')
    for fx in (x for x in he.trunk_fixtures(s) if x['role'] == 'light strip'):
        c, ax = he.box_frame(None, fx); la, lt, lr = fx['size']; lip, h = q['housing_lip_m'], q['housing_depth_m']
        x = c[0]; phi = math.degrees(math.atan2(c[2], c[1])); dp = math.degrees((lt/2+lip)/R)
        for side, (lo, hi) in enumerate(((phi-dp, phi-dp+math.degrees(lip/R)), (phi+dp-math.degrees(lip/R), phi+dp)), 1):
            vs, fs = pd.bent(at, x-la/2-lip, x+la/2+lip, R-h, R-.001, lo, hi, n=1)
            out.append(pd.element('M7.TRK', 'Housings', f"{fx['name']}_Lip_{side}", 'housing', 'ENGINEERING_FLEXIBLE', 'light-strip housing lip', vs, fs, bevel=.002))
        for end, (s0, s1) in enumerate(((x-la/2-lip, x-la/2), (x+la/2, x+la/2+lip)), 1):
            vs, fs = pd.bent(at, s0, s1, R-h, R-.001, phi-dp, phi+dp, n=1)
            out.append(pd.element('M7.TRK', 'Housings', f"{fx['name']}_Cap_{end}", 'housing', 'ENGINEERING_FLEXIBLE', 'light-strip housing end cap', vs, fs, bevel=.002))
    return out


def trunk_check(s, els):
    """Every pd.element on the trunk wall (no closer to the axis than the housings' depth), inside the trunk's length, its cladding off the
    keep-out windows and clear of every branch opening."""
    import route_fitout as rf
    R, X0, X1 = rf.trunk_extent(s); depth = s['production']['entry']['housing_depth_m']; keep = trunk_keepouts(s); fails = []
    for q in els:
        rs = [math.hypot(v[1], v[2]) for v in q['vs']]; xs = [v[0] for v in q['vs']]
        if min(rs) < R-depth-1e-6:
            fails.append(f"{q['name']}: {R-min(rs):.3f} m off the wall")
        if min(xs) < X0-1e-6 or max(xs) > X1+1e-6:
            fails.append(f"{q['name']}: beyond the trunk")
        if q['family'] in ('Panels', 'Fasteners', 'Trays'):
            ph = [math.degrees(math.atan2(v[2], v[1])) for v in q['vs']]; lo, hi = min(ph), max(ph)
            if hi-lo > 180.0:
                ph = [x+360.0 if x < 0 else x for x in ph]; lo, hi = min(ph), max(ph)
            import route_fitout as rf2
            for w0, w1, wlo, whi in keep:
                if min(xs) < w1 and w0 < max(xs) and rf2.overlaps((lo+1e-6, hi-1e-6), (wlo, whi)):
                    fails.append(f"{q['name']}: on a keep-out window (x {w0:.2f}-{w1:.2f}, phi {wlo:.0f}-{whi:.0f})"); break
            if not opening_clear(s, R, min(xs), max(xs), lo+1e-6, hi-1e-6):
                fails.append(f"{q['name']}: near a branch opening")
    return fails


pd.CHECKS['M7.TRK'] = trunk_check
