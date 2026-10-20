"""M7 production reference section: the L4 presentation layer of one contiguous path (PROTOTYPE, standard library only).

S&E 48!A23 (WF-022) defines L4 PRODUCTION as linked models, rigs, materials, lighting and stable exports; this module adds the generated
production detail of the boarding path, primary port -> entry chamber -> stationary trunk -> ring-A spin transfer -> ring-A crew tube ->
ring-A sector 1, on top of the unchanged engineering geometry. It follows route_fitout (the ARCHITECTURE layer): every element has a job the
route already needs (panel mounting and service access, frames that carry the panels, handhold brackets, fixture housings, identification)
and the culture decides how it looks. Only the engineering-flexible and artistic surface classes are detailed (15!I120); physics-locked
parts keep REP_PROXY grey with no hero finish (15!H120). Nothing here carries load or changes a pressure boundary, an interface, a volume or
the clear route: check() keeps every element outside the clearances the route already has.

An element is a closed mesh in the frame of the asset it is built in (vehicle frame for SERVICE and CREW_TRANSFER, the rotor or drum frame
for parented parts, the sector frame for the interior), with its assembly, family (the generator joins one family of an assembly into one
object, so the runtime gets a few batched meshes, not one object per stud), production material, surface class and function. `[production]`
holds the switch, the assemblies built and every dimension; the materials are `[production.materials]`.
`python3 src/wayfarer/production_detail.py` prints the element counts and the check.
"""
import json
import math

# Stable assembly IDs of the section (plan M7). host: the build target whose asset carries the assembly.
ASSEMBLIES = {
    'M7.EXT.PORT': dict(host='SERVICE', zone='primary boarding port, exterior', classes=('ENGINEERING_FLEXIBLE',)),
    'M7.ENT': dict(host='SERVICE', zone='entry chamber and trunk node (HUM-001 zones 1-2)', classes=('ENGINEERING_FLEXIBLE', 'ARTISTIC')),
    'M7.TRK': dict(host='CREW_TRANSFER', zone='stationary crew trunk (zone 2)', classes=('ENGINEERING_FLEXIBLE', 'ARTISTIC')),
    'M7.XFR': dict(host='HABITAT', zone='ring-A spin transfer surroundings (zone 3); closures physics-locked', classes=('ENGINEERING_FLEXIBLE',)),
    'M7.SPK': dict(host='HABITAT', zone='ring-A crew tube to sector 1 (zone 4)', classes=('ENGINEERING_FLEXIBLE',)),
    'M7.RA1': dict(host='HABITAT', zone='ring-A sector 1 HABITATION (zone 5; placed on that sector only, shared definitions)',
                   classes=('ENGINEERING_FLEXIBLE', 'ARTISTIC')),
    # M8.1 exterior production identity ([production.m8], its own switch and maturity; same layer, same generator).
    'M8.BROW.AFT': dict(host='FORWARD_SHIELD', zone='Brow aft face: panel modules between the existing joints, inside the truss envelope',
                        classes=('ENGINEERING_FLEXIBLE', 'ARTISTIC')),
    'M8.CROWN.RIM': dict(host='FORWARD_SHIELD', zone='Aegis Crown rim: the sector module on the housing aft plate and the rim girder '
                                                     '(mechanisms, shutters and optics unchanged)', classes=('ENGINEERING_FLEXIBLE', 'ARTISTIC')),
}
BOX_FACES = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
BUILDERS = {}


def builder(assembly):
    def wrap(fn):
        BUILDERS[assembly] = fn
        return fn
    return wrap


def RA1_SECTOR(s):
    """(ring, sector) of M7.RA1: the induction ring's sector 1, the arrival sector of the boarding route."""
    return (s['induction']['ring'], 1)


def scope(s, assembly):
    """The table that switches and labels an assembly: [production] for M7, [production.m8] for M8 (independently switchable)."""
    return s['production']['m8'] if assembly.startswith('M8.') else s['production']


def built(s):
    """Assemblies the build makes, M7 then M8, each scope by its own switch."""
    p = s['production']; m8 = p.get('m8', {})
    return (list(p['assemblies']) if p['enabled'] else [])+(list(m8['assemblies']) if m8.get('enabled') else [])


def listed(s):
    p = s['production']
    return list(p['assemblies'])+list(p.get('m8', {}).get('assemblies', []))


def enabled(s, assembly=None):
    if assembly is None:
        return bool(built(s))
    q = scope(s, assembly)
    return bool(q['enabled']) and assembly in q['assemblies']


def material_value(s, key):
    """[r, g, b, roughness, metallic] of a production material: [production.materials] or the exterior [production.m8.materials]."""
    p = s['production']
    return p['materials'][key] if key in p['materials'] else p['m8']['materials'][key]


def element(assembly, family, name, material, cls, function, vs, fs, bevel=0.0):
    if assembly not in ASSEMBLIES:
        raise ValueError(f'Unknown assembly {assembly}')
    return dict(assembly=assembly, family=family, name=name, material=material, surface_class=cls, function=function,
                vs=[tuple(map(float, v)) for v in vs], fs=[tuple(q) for q in fs], bevel=bevel)


def lettering(assembly, family, name, material, function, text, centre, right, up, height):
    """Stencilled text (the generator converts it to a mesh): centred at centre on the plane right x up, letters height tall, read facing
    the plane's normal (right x up). Restrained identification only: hatch, port and panel IDs, never livery."""
    q = element(assembly, family, name, material, 'ARTISTIC', function, [], [])
    q.update(text=text, centre=tuple(centre), right=tuple(right), up=tuple(up), height=height)
    return q


# Pure mesh helpers (closed solids).
def box(centre, axes, size):
    """Corners and faces of a box: centre, three unit axes and the size along them."""
    vs = [tuple(centre[i]+sx*size[0]/2*axes[0][i]+sy*size[1]/2*axes[1][i]+sz*size[2]/2*axes[2][i] for i in range(3))
          for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)]
    return vs, BOX_FACES


CURVE_STEP_DEG = 6.0     # M7 performance pass: 6 deg chords sag at most R(1-cos 3 deg) = 1.1 mm at r 0.8 m and 2.6 mm at r 1.925 m


def bent(at, s0, s1, r0, r1, p0, p1, step_deg=None, n=2):
    """A box bent round an axis: at(s, rho, phi_rad) gives the point; s along the axis, rho across it, phi in degrees."""
    k = max(n, int(abs(p1-p0)/(step_deg or CURVE_STEP_DEG))+1)
    vs = [at(a, r, math.radians(p0+(p1-p0)*j/k)) for j in range(k+1) for a, r in ((s0, r0), (s1, r0), (s1, r1), (s0, r1))]
    fs = [(4*j+i, 4*j+(i+1) % 4, 4*(j+1)+(i+1) % 4, 4*(j+1)+i) for j in range(k) for i in range(4)]+[(3, 2, 1, 0), (4*k, 4*k+1, 4*k+2, 4*k+3)]
    return vs, fs


def rod(a, b, r, n=8):
    """A closed n-gon prism of radius r from a to b."""
    d = [b[i]-a[i] for i in range(3)]; L = math.sqrt(sum(x*x for x in d)); d = [x/L for x in d]
    t = (1.0, 0.0, 0.0) if abs(d[0]) < .9 else (0.0, 1.0, 0.0)
    u = cross(d, t); m = math.sqrt(sum(x*x for x in u)); u = [x/m for x in u]; w = cross(d, u)
    ring = lambda c: [tuple(c[i]+r*(math.cos(2*math.pi*j/n)*u[i]+math.sin(2*math.pi*j/n)*w[i]) for i in range(3)) for j in range(n)]
    vs = ring(a)+ring(b)
    fs = [(j, (j+1) % n, n+(j+1) % n, n+j) for j in range(n)]+[tuple(range(n-1, -1, -1)), tuple(range(n, 2*n))]
    return vs, fs


def cross(a, b):
    return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])


def windows_free(windows, lo, hi, gap):
    """Sub-intervals of [lo, hi] (degrees, lo < hi, unwrapped) clear of the given windows (any wrap) widened by gap."""
    cuts = sorted((a-gap+shift, b+gap+shift) for a, b in windows for shift in (-720.0, -360.0, 0.0, 360.0, 720.0))
    out, at = [], lo
    for a, b in cuts:
        if b <= at or a >= hi:
            continue
        if a > at:
            out.append((at, a))
        at = max(at, b)
    if at < hi:
        out.append((at, hi))
    return [(a, b) for a, b in out if b-a > 1e-6]


def elements(s, assembly=None):
    """Production elements of one assembly, or of every assembly [production] builds."""
    if assembly is not None:
        return BUILDERS[assembly](s) if assembly in BUILDERS else []
    return [q for a in built(s) for q in elements(s, a)]


def families(els):
    """{(assembly, family): [elements]}: what the generator joins into one object."""
    out = {}
    for q in els:
        out.setdefault((q['assembly'], q['family']), []).append(q)
    return out


def object_name(assembly, family):
    return 'Prod_'+assembly.replace('M7.', '').replace('M8.', '').replace('.', '_')+'_'+family


def check(s, assembly=None):
    """Failures of the built assemblies (or one): each assembly's own clearance screen (CHECKS) plus degenerate meshes."""
    fails = []
    for a in ([assembly] if assembly else listed(s)):
        els = elements(s, a)
        for q in els:
            if 'text' in q:
                continue
            if len(q['vs']) < 4 or not q['fs'] or any(max(f) >= len(q['vs']) for f in q['fs']):
                fails.append(f"{q['name']}: degenerate mesh")
        if a in CHECKS:
            fails += CHECKS[a](s, els)
    return fails


CHECKS = {}


# M7.ENT: the entry chamber and the trunk node (dock-local frame of human_entry: a along the port's outward radial, rho and phi across it).
def entry_keepouts(s, f):
    """(zone, a0, a1, phi0, phi1) wall windows the production layer must leave: route_fitout's taken windows (parked leaves, light strips,
    panels), every fit-out wall element (bands, stringers, grilles, chase, locker; the frames bound the bays instead) and the angular
    footprint of every wall-mounted rod (handrail brackets, handholds, handles, foot restraint, chase lines) widened by its radius."""
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


@builder('M7.ENT')
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
            for k, (p0, p1) in enumerate(windows_free(wins, -180.0, 180.0, gap), 1):
                n = max(1, math.ceil((p1-p0)/q['panel_max_deg']))
                if (p1-p0)/n < q['panel_min_deg']:
                    continue
                # The carrier tray: a dark rail under the panel run the fasteners lock into; it is what the seams show.
                vs, fs = bent(at, a0+seam/2, a1-seam/2, t1, R-.0003, p0+gap/4, p1-gap/4)
                out.append(element('M7.ENT', 'Trays', f"ENT_{zone.title()}_B{b}_T{k}", 'gasket', 'ENGINEERING_FLEXIBLE',
                                   'panel carrier tray and seam gasket', vs, fs))
                for i in range(n):
                    lo = p0+(p1-p0)*i/n+gap/2; hi = p0+(p1-p0)*(i+1)/n-gap/2; s0, s1 = a0+seam, a1-seam
                    name = f"ENT_{zone.title()}_B{b}_P{k}_{i+1}"; deck = 135.0 <= (lo+hi)/2 % 360.0 <= 225.0
                    vs, fs = bent(at, s0, s1, t0, t1, lo, hi)
                    out.append(element('M7.ENT', 'Panels', name, 'panel_service' if deck else 'panel_inhabited', 'ENGINEERING_FLEXIBLE',
                                       'replaceable wall panel module (service access to the shell and lines behind)', vs, fs, bevel=q['panel_bevel_m']))
                    st = q['fastener_m']; inset = q['fastener_inset_m']; dphi = math.degrees(inset/R)
                    for sa in (s0+inset, s1-inset):
                        for sp in (lo+dphi, hi-dphi):
                            vs, fs = bent(at, sa-st/2, sa+st/2, t0-q['fastener_proud_m'], t0, sp-math.degrees(st/2/R), sp+math.degrees(st/2/R), n=1)
                            out.append(element('M7.ENT', 'Fasteners', name+f'_F{len(out)}', 'fastener', 'ENGINEERING_FLEXIBLE',
                                               'quarter-turn panel fastener', vs, fs))
    # Bulkhead faces: an annulus of radial panel segments between the hatch-frame mark and the wall, off the hinge and leaf, the
    # placards and the equalization valves; they face the chamber (outer bulkhead) or the chamber and the node (inner bulkhead).
    st = he.stations(s, f); bh = q['bulkhead']
    faces = [('Outer', st['a_out'], -1.0, s['human_entry']['outer_hinge_deg']), ('Inner', st['a_in'], 1.0, None),
             ('Node', st['node_in'], 1.0, s['human_entry']['inner_hinge_deg'])]
    valves = [math.degrees(he.local(f, v['points'][0])[2]) for v in he.fixtures(s, f) if 'valve' in v['role']]
    for tagname, a, side, hinge in faces:
        wins = [(d-bh['valve_keep_deg'], d+bh['valve_keep_deg']) for d in valves]+[(d-bh['placard_keep_deg'], d+bh['placard_keep_deg']) for d in (0.0, 180.0)]
        if hinge is not None:
            wins.append((hinge-bh['hinge_keep_deg'], hinge+bh['hinge_keep_deg']))
        r0, r1 = bh['inner_m'], R-.004; d0, d1 = (a+side*.0015, a+side*(.0015+q['panel_thickness_m']))
        for k, (p0, p1) in enumerate(windows_free(wins, -180.0, 180.0, gap), 1):
            n = max(1, math.ceil((p1-p0)/bh['segment_max_deg']))
            for i in range(n):
                lo = p0+(p1-p0)*i/n+gap/2; hi = p0+(p1-p0)*(i+1)/n-gap/2
                vs, fs = bent(lambda u, r, ph: at(u, r, ph), min(d0, d1), max(d0, d1), r0, r1, lo, hi)
                out.append(element('M7.ENT', 'Bulkhead', f'ENT_Bulkhead_{tagname}_{k}_{i+1}', 'panel_inhabited', 'ENGINEERING_FLEXIBLE',
                                   'bulkhead face panel (access to the hatch-frame seal land bolts)', vs, fs, bevel=q['panel_bevel_m']))
    # Housings: two lips along each light strip's long edges and two end caps, so the emitter reads as a recessed, serviceable fixture.
    for fx in (x for x in he.fixtures(s, f) if x['role'] == 'light strip'):
        a, rho, phi = fx['centre']; la, lt, lr = fx['size']; lip, h = q['housing_lip_m'], q['housing_depth_m']; dp = math.degrees((lt/2+lip)/R)
        for side, (lo, hi) in enumerate(((math.degrees(phi)-dp, math.degrees(phi)-dp+math.degrees(lip/R)),
                                         (math.degrees(phi)+dp-math.degrees(lip/R), math.degrees(phi)+dp)), 1):
            vs, fs = bent(at, a-la/2-lip, a+la/2+lip, R-h, R-.001, lo, hi, n=1)
            out.append(element('M7.ENT', 'Housings', f"{fx['name']}_Lip_{side}", 'housing', 'ENGINEERING_FLEXIBLE', 'light-strip housing lip', vs, fs, bevel=.002))
        for end, (s0, s1) in enumerate(((a-la/2-lip, a-la/2), (a+la/2, a+la/2+lip)), 1):
            vs, fs = bent(at, s0, s1, R-h, R-.001, math.degrees(phi)-dp, math.degrees(phi)+dp, n=1)
            out.append(element('M7.ENT', 'Housings', f"{fx['name']}_Cap_{end}", 'housing', 'ENGINEERING_FLEXIBLE', 'light-strip housing end cap', vs, fs, bevel=.002))
    return out


def entry_check(s, els):
    """Every element inside its zone, outside the passage (no closer to the axis than the valves already stand) and, for panels and
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


CHECKS['M7.ENT'] = entry_check


# M7.EXT.PORT: the primary port from outside (vehicle frame). The capture ring, the port fitting, the hull and the docking aids are
# physics-locked or already built; the layer adds only flush service covers in the accepted M4 grammar (15!A202: ochre covers) and the
# port's identification, outside the visiting vehicle's ~3 m keep-out corridor (Q33) and clear of the approach aids (exterior_hardware).
@builder('M7.EXT.PORT')
def port_elements(s):
    import exterior_hardware as eh
    import human_entry as he
    q = s['production']['port']; f = he.ports(s)[0]; out = []
    for k, cov in enumerate(q['covers'], 1):
        dx, dt = cov['at_m']; L, W, D = cov['size_m']
        c, a, r = eh.on_hull(s, f['x'], f['theta'], dx, dt, D/2+q['standoff_m'])
        ax = eh.frame(a); vs, fs = box(c, ax, (L, W, D))
        out.append(element('M7.EXT.PORT', 'Covers', f'EXT_Cover_{k}', 'service_ochre', 'ENGINEERING_FLEXIBLE', cov['function'], vs, fs, bevel=.006))
        ins = q['fastener_inset_m']; st = q['fastener_m']
        for i, (sx, sy) in enumerate([(-1, -1), (-1, 1), (1, -1), (1, 1), (0, -1), (0, 1)]):
            fc = tuple(c[j]+sx*(L/2-ins)*ax[0][j]+sy*(W/2-ins)*ax[1][j]+(D/2+st/4)*ax[2][j] for j in range(3))
            vs, fs = box(fc, ax, (st, st, st/2))
            out.append(element('M7.EXT.PORT', 'Fasteners', f'EXT_Cover_{k}_F{i+1}', 'fastener', 'ENGINEERING_FLEXIBLE', 'quarter-turn cover fastener', vs, fs))
        top = tuple(c[j]+(D/2+.0015)*ax[2][j] for j in range(3)); right = tuple(-x for x in ax[1])     # faces outward, fore (+X) up
        out.append(lettering('M7.EXT.PORT', 'Lettering', f'EXT_Cover_{k}_Label', 'wayfinding_blue', 'cover identification stencil', cov['label'],
                             top, right, ax[0], cov['label_m']))
    dx, dt = q['port_id_at_m']; c, a, r = eh.on_hull(s, f['x'], f['theta'], dx, dt, q['standoff_m']+.0015); ax = eh.frame(a)
    out.append(lettering('M7.EXT.PORT', 'Lettering', 'EXT_Port_ID', 'placard', 'port identification for the visiting vehicle and EVA crew',
                         q['port_id'], c, tuple(-x for x in ax[1]), ax[0], q['port_id_m']))
    return out


def port_check(s, els):
    """Covers off the hull opening round the port, inside the window the collar straps already leave round the port's aids (so no
    strap or seam crosses them, casing_panels.collar_keepouts) and clear of every approach aid (exterior_hardware.docking) by a margin."""
    import casing_panels as cp
    import exterior_hardware as eh
    import hull_geometry as hg
    import human_entry as he
    q = s['production']['port']; f = he.ports(s)[0]; R = hg.radius_at(s, f['x']); fails = []
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


CHECKS['M7.EXT.PORT'] = port_check


# Shared wall-cladding component (ENT, TRK, SPK use the same module): a panel run in one bay of a cylindrical wall, its carrier tray and
# its fasteners. at(s, rho, phi_rad) maps the bay's axial coordinate, radius and angle to the asset frame.
def clad_bay(assembly, prefix, at, R, s0, s1, p0, p1, q, material, n_min=1):
    out = []; seam = q['seam_m']; gap = math.degrees(seam/R); t0, t1 = R-q['panel_back_gap_m']-q['panel_thickness_m'], R-q['panel_back_gap_m']
    n = max(n_min, math.ceil((p1-p0)/q['panel_max_deg']))
    if (p1-p0)/n < q['panel_min_deg'] or s1-s0 < 3*seam:
        return out
    vs, fs = bent(at, s0+seam/2, s1-seam/2, t1, R-.0003, p0+gap/4, p1-gap/4)
    out.append(element(assembly, 'Trays', f'{prefix}_T', 'gasket', 'ENGINEERING_FLEXIBLE', 'panel carrier tray and seam gasket', vs, fs))
    st, inset = q['fastener_m'], q['fastener_inset_m']; dphi = math.degrees(inset/R)
    for i in range(n):
        lo = p0+(p1-p0)*i/n+gap/2; hi = p0+(p1-p0)*(i+1)/n-gap/2; a0, a1 = s0+seam, s1-seam
        vs, fs = bent(at, a0, a1, t0, t1, lo, hi)
        out.append(element(assembly, 'Panels', f'{prefix}_{i+1}', material, 'ENGINEERING_FLEXIBLE',
                           'replaceable wall panel module (service access to the shell and lines behind)', vs, fs, bevel=q['panel_bevel_m']))
        for sa in (a0+inset, a1-inset):
            for sp in (lo+dphi, hi-dphi):
                vs, fs = bent(at, sa-st/2, sa+st/2, t0-q['fastener_proud_m'], t0, sp-math.degrees(st/2/R), sp+math.degrees(st/2/R), n=1)
                out.append(element(assembly, 'Fasteners', f'{prefix}_{i+1}_F{len(out)}', 'fastener', 'ENGINEERING_FLEXIBLE', 'quarter-turn panel fastener', vs, fs))
    return out


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
    store ports' rails, the route stripe, every non-frame fit-out element (placards, chevrons, diffuser) widened by a margin."""
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
            pts = q['points'] if q['shape'] == 'rod' else wbox_pts(q)
            xs = [v[0] for v in pts]; ph = [math.degrees(math.atan2(v[2], v[1])) for v in pts]; lo, hi = min(ph), max(ph)
            if hi-lo > 180.0:
                ph = [x+360.0 if x < 0 else x for x in ph]; lo, hi = min(ph), max(ph)
            out.append((min(xs)-.05, max(xs)+.05, lo-3.0, hi+3.0))
    return out


def wbox_pts(q):
    c, ax, size = q['centre'], q['axes'], q['size']
    return [tuple(c[i]+sx*size[0]/2*ax[0][i]+sy*size[1]/2*ax[1][i]+sz*size[2]/2*ax[2][i] for i in range(3)) for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)]


def opening_clear(s, R, x0, x1, lo, hi):
    """True when the patch x0..x1, lo..hi (degrees) of the trunk wall stays opening_margin_m clear of every branch opening."""
    import human_entry as he
    for d in (lo, (lo+hi)/2, hi):
        if not any(a <= x0 and x1 <= b for a, b in he.clear_spans(s, R, math.radians(d), x0, x1)):
            return False
    return True


@builder('M7.TRK')
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
        for k, (p0, p1) in enumerate(windows_free(wins, -180.0, 180.0, gap), 1):
            # split the window at the openings: sub-patches whose three sample angles stay clear of every branch opening
            n = max(1, math.ceil((p1-p0)/q['panel_max_deg']))
            for i in range(n):
                lo, hi = p0+(p1-p0)*i/n, p0+(p1-p0)*(i+1)/n
                if not opening_clear(s, R, a0, a1, lo, hi):
                    continue
                deck = 160.0 <= (lo+hi)/2 % 360.0 <= 200.0
                out += clad_bay('M7.TRK', f'TRK_B{b}_P{k}_{i+1}', at, R, a0, a1, lo, hi, q, 'panel_service' if deck else 'panel_inhabited')
    for fx in (x for x in he.trunk_fixtures(s) if x['role'] == 'light strip'):
        c, ax = he.box_frame(None, fx); la, lt, lr = fx['size']; lip, h = q['housing_lip_m'], q['housing_depth_m']
        x = c[0]; phi = math.degrees(math.atan2(c[2], c[1])); dp = math.degrees((lt/2+lip)/R)
        for side, (lo, hi) in enumerate(((phi-dp, phi-dp+math.degrees(lip/R)), (phi+dp-math.degrees(lip/R), phi+dp)), 1):
            vs, fs = bent(at, x-la/2-lip, x+la/2+lip, R-h, R-.001, lo, hi, n=1)
            out.append(element('M7.TRK', 'Housings', f"{fx['name']}_Lip_{side}", 'housing', 'ENGINEERING_FLEXIBLE', 'light-strip housing lip', vs, fs, bevel=.002))
        for end, (s0, s1) in enumerate(((x-la/2-lip, x-la/2), (x+la/2, x+la/2+lip)), 1):
            vs, fs = bent(at, s0, s1, R-h, R-.001, phi-dp, phi+dp, n=1)
            out.append(element('M7.TRK', 'Housings', f"{fx['name']}_Cap_{end}", 'housing', 'ENGINEERING_FLEXIBLE', 'light-strip housing end cap', vs, fs, bevel=.002))
    return out


def trunk_check(s, els):
    """Every element on the trunk wall (no closer to the axis than the housings' depth), inside the trunk's length, its cladding off the
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


CHECKS['M7.TRK'] = trunk_check


def fixture_points(q):
    """Points of a fixture or fit-out element in its own frame (rods, segment lists, boxes, tubes), for keep-out windows."""
    import human_entry as he
    if q['shape'] == 'rod':
        return q['points']
    if q['shape'] == 'rods':
        return [p for seg in q['segments'] for p in seg]
    if q['shape'] in ('tube', 'cyl'):
        return [q['a'], q['b']]
    if q['shape'] == 'wbox' or 'axes' in q and 'centre' in q:
        return wbox_pts(q)
    if q['shape'] == 'box' and 'world_centre' in q:
        return he.box_corners(None, q)
    return []


def windows_of(points, coord, pad_s, pad_deg):
    """(s0, s1, phi0, phi1) of points under coord(p) -> (s, phi_deg), padded; wraps resolved toward the smaller span."""
    sp = [coord(p) for p in points]
    if not sp:
        return None
    ss = [a for a, _ in sp]; ph = [b % 360.0 for _, b in sp]; lo, hi = min(ph), max(ph)
    if hi-lo > 180.0:
        ph = [x-360.0 if x > 180.0 else x for x in ph]; lo, hi = min(ph), max(ph)
    return (min(ss)-pad_s, max(ss)+pad_s, lo-pad_deg, hi+pad_deg)


def patch_free(keep, s0, s1, lo, hi):
    import route_fitout as rf
    return not any(w0 < s1 and s0 < w1 and rf.overlaps((lo, hi), (wlo, whi)) for w0, w1, wlo, whi in keep)


# M7.XFR: ring A's despun drum (drum frame, parented to Drum_j): a lining of replaceable panels on the drum's outer wall above the crawl
# rail, between and around the route frames, off the tube openings (their frames and door seal lands are physics-locked closures), the
# handrails, lights, transfer panel and placards; housings round the drum lights. No closure, seal, bearing or interface is touched.
def drum_keepouts(s, j):
    import crew_transfer as ct
    import human_entry as he
    import route_fitout as rf
    rot, v, la = he.vestibule_station(s, j); R = v['clear']; h = s['human_entry']
    coord = lambda p: (p[0], math.degrees(math.atan2(p[2], p[1])))
    out = []
    edge = v['port_clear']+h['hatch_frame_width_m']+s['production']['drum']['opening_margin_m']
    for a in la.values():
        half = math.degrees(math.asin(min(1.0, edge/R)))
        out.append((-1e3, 1e3, math.degrees(a)-half, math.degrees(a)+half))
    for q in he.vestibule_fixtures(s, j)+[e for e in rf.drum_elements(s, j) if e['shape'] != 'ring']:
        if '_Frame_' in q['name'] and q['shape'] == 'xarc':
            out.append((q['x'][0], q['x'][1], q['phi'][0]-.5, q['phi'][1]+.5)); continue
        w = windows_of(fixture_points(q), coord, .04, 2.5)
        if w:
            out.append(w)
    return out


@builder('M7.XFR')
def drum_elements(s):
    import crew_transfer as ct
    import human_entry as he
    j = s['induction']['ring']; q = dict(s['production']['entry'], **{k: v for k, v in s['production']['drum'].items() if k in s['production']['entry']})
    rot, v, la = he.vestibule_station(s, j); R = v['clear']; h = s['human_entry']; w = h['chamber_wall_m']
    a0 = v['cu0']+w+h['crawl_rail_height_m']+h['handrail_radius_m']+.06; a1 = v['cu1']-w-.02
    at = lambda x, r, a: ct.radial(x, r, a); keep = drum_keepouts(s, j); gap = math.degrees(q['seam_m']/R); out = []
    wins = [(lo, hi) for w0, w1, lo, hi in keep if w0 < a1 and a0 < w1]
    for k, (p0, p1) in enumerate(windows_free(wins, -180.0, 180.0, gap), 1):
        out += clad_bay('M7.XFR', f'XFR_P{k}', at, R, a0, a1, p0, p1, q, 'panel_machinery', n_min=1)
    for fx in (x for x in he.vestibule_fixtures(s, j) if x['role'] == 'light strip'):
        c, ax = he.box_frame(None, fx); la_, lt, lr = fx['size']; lip, hd = q['housing_lip_m'], q['housing_depth_m']
        x = c[0]; phi = math.degrees(math.atan2(c[2], c[1])); dp = math.degrees((lt/2+lip)/R)
        for side, (lo, hi) in enumerate(((phi-dp, phi-dp+math.degrees(lip/R)), (phi+dp-math.degrees(lip/R), phi+dp)), 1):
            vs, fs = bent(at, x-la_/2-lip, x+la_/2+lip, R-hd, R-.001, lo, hi, n=1)
            out.append(element('M7.XFR', 'Housings', f"{fx['name']}_Lip_{side}", 'housing', 'ENGINEERING_FLEXIBLE', 'light-strip housing lip', vs, fs, bevel=.002))
    return out


def drum_check(s, els):
    import human_entry as he
    j = s['induction']['ring']; rot, v, la = he.vestibule_station(s, j); R = v['clear']; keep = drum_keepouts(s, j); fails = []
    depth = s['production']['entry']['housing_depth_m']; h = s['human_entry']
    for q in els:
        rs = [math.hypot(p[1], p[2]) for p in q['vs']]; xs = [p[0] for p in q['vs']]
        if min(rs) < R-depth-1e-6:
            fails.append(f"{q['name']}: {R-min(rs):.3f} m off the drum wall (the suited annulus keeps {v['clear']-v['r0']:.2f} m)")
        if min(xs) < v['cu0']-1e-6 or max(xs) > v['cu1']+1e-6:
            fails.append(f"{q['name']}: beyond the drum chamber")
        if q['family'] in ('Panels', 'Trays', 'Fasteners'):
            w = windows_of(q['vs'], lambda p: (p[0], math.degrees(math.atan2(p[2], p[1]))), 0.0, 0.0)
            if not patch_free(keep, w[0]+1e-6, w[1]-1e-6, w[2]+1e-6, w[3]-1e-6):
                fails.append(f"{q['name']}: on a keep-out window")
    return fails


CHECKS['M7.XFR'] = drum_check


# M7.SPK: ring A's crew tube to sector 1, its radial run (rotor frame, parented to Rotor_j): ring frames every frame_pitch_m and the
# cladding between them, off the ladder, its arrest rail and brackets, the light strips, the hatch panel and the fit-out (deck band,
# placards, bezel, handles). The tube's collar, elbows and the sector hatch stay as they are.
def tube_frame(s):
    import human_entry as he
    j = s['induction']['ring']; rot, v, la, frames = he.spoke_station(s, j); fr = frames[1]; R_ = he.RUN
    o, d, n1, n2 = fr['points'][R_], fr['d'][R_], fr['n1'][R_], fr['n2'][R_]
    def at(t, r, a):
        return tuple(o[i]+d[i]*t+r*(math.cos(a)*n1[i]+math.sin(a)*n2[i]) for i in range(3))
    def coord(p):
        q = [p[i]-o[i] for i in range(3)]
        return (sum(q[i]*d[i] for i in range(3)), math.degrees(math.atan2(sum(q[i]*n2[i] for i in range(3)), sum(q[i]*n1[i] for i in range(3)))))
    return j, fr, at, coord


def tube_keepouts(s):
    import human_entry as he
    import route_fitout as rf
    j, fr, at, coord = tube_frame(s); t0, t1 = he.run_span(s, fr); out = []
    for q in he.spoke_fixtures(s, j)+rf.tube_end_elements(s, j):
        if q['shape'] == 'tarc':
            out.append((q['t'][0]-.03, q['t'][1]+.03, q['phi'][0]-2.0, q['phi'][1]+2.0)); continue
        pts = [p for p in fixture_points(q) if t0-.5 <= coord(p)[0] <= t1+.5]
        w = windows_of(pts, coord, .05, 3.0)
        if w:
            out.append(w)
    return out


@builder('M7.SPK')
def tube_elements(s):
    import crew_transfer as ct
    import human_entry as he
    q = s['production']['entry']; t_ = s['production']['tube']; j, fr, at, coord = tube_frame(s); rc = ct.tube_radii(s, j)[1]
    t0, t1 = he.run_span(s, fr); t0 += t_['end_inset_m']; t1 -= t_['end_inset_m']; keep = tube_keepouts(s); out = []
    gap = math.degrees(q['seam_m']/rc); n = max(1, round((t1-t0)/t_['frame_pitch_m'])); edges = [t0+(t1-t0)*i/n for i in range(n+1)]
    fw, fd = t_['frame_width_m'], t_['frame_depth_m']
    for i, tc in enumerate(edges):
        a, b = tc-fw/2, tc+fw/2
        wins = [(lo, hi) for w0, w1, lo, hi in keep if w0 < b and a < w1]
        for k, (p0, p1) in enumerate(windows_free(wins, -180.0, 180.0, 1.0), 1):
            vs, fs = bent(at, max(a, t0-fw/2), min(b, t1+fw/2), rc-fd, rc-.0003, p0, p1)
            out.append(element('M7.SPK', 'Frames', f'SPK_Frame_{i}_{k}', 'frame_structural', 'ENGINEERING_FLEXIBLE',
                               'tube ring frame carrying the lining panels', vs, fs, bevel=.004))
    for i, (a, b) in enumerate(zip(edges, edges[1:]), 1):
        s0, s1 = a+fw/2, b-fw/2
        wins = [(lo, hi) for w0, w1, lo, hi in keep if w0 < s1 and s0 < w1]
        for k, (p0, p1) in enumerate(windows_free(wins, -180.0, 180.0, gap), 1):
            out += clad_bay('M7.SPK', f'SPK_B{i}_P{k}', at, rc, s0, s1, p0, p1, q, 'panel_inhabited')
    return out


def tube_check(s, els):
    import crew_transfer as ct
    import human_entry as he
    j, fr, at, coord = tube_frame(s); rc = ct.tube_radii(s, j)[1]; keep = tube_keepouts(s); fails = []
    lim = s['production']['tube']['frame_depth_m']; t0, t1 = he.run_span(s, fr)
    for q in els:
        loc = [coord(p) for p in q['vs']]
        rr = [math.dist(p, at(c[0], 0.0, 0.0)) for p, c in zip(q['vs'], loc)]
        if min(rr) < rc-lim-1e-6:
            fails.append(f"{q['name']}: {rc-min(rr):.3f} m off the tube wall")
        if min(c[0] for c in loc) < t0-.05 or max(c[0] for c in loc) > t1+.05:
            fails.append(f"{q['name']}: beyond the run")
        if q['family'] in ('Panels', 'Trays', 'Fasteners', 'Frames'):
            w = windows_of(q['vs'], coord, 0.0, 0.0)
            if not patch_free(keep, w[0]+1e-6, w[1]-1e-6, w[2]+1e-6, w[3]-1e-6):
                fails.append(f"{q['name']}: on a keep-out window")
    return fails


CHECKS['M7.SPK'] = tube_check


# M7.RA1: ring A sector 1 (HABITATION), sector frame (+X axial, +Y radially outward = down in spin, +Z tangential; deck at y 0),
# parented to that sector's instance only. The overhead is the zone the layer details: removable service panels on trays in the bays of
# the route fit-out's overhead frame grid, off the aisle lights, route bands and chevrons, diffuser, landing chase, thrust step, hatch frame
# and its rails, and the hatch opening plus the landing well's column the route descends through; housings round the aisle lights.
# Nothing comes below overhead_floor_y_m, so the aisle, the berths' access strips and every route body stay as they were.
def sector_overhead_items(s):
    import human_entry as he
    import route_fitout as rf
    els = rf.sector_elements(s, 'HABITATION')+rf.sector_sign(s, 'HABITATION')+rf.seraph_elements(s, 'HABITATION')[0]+rf.landing_elements(s)+he.landing_fixtures(s)
    out = []
    for q in els:
        pts = [q['min'], q['max']] if q['shape'] == 'box' and 'min' in q else fixture_points(q)
        if pts and min(p[1] for p in pts) < s['production']['sector']['item_floor_y_m']:
            out.append((q['name'], [min(p[k] for p in pts) for k in range(3)], [max(p[k] for p in pts) for k in range(3)], q))
    return out


def sector_keepouts(s, x0, x1):
    """z intervals of the overhead a bay x0..x1 leaves: overhead items (frames excluded: they bound the bays), the hatch opening and the
    landing well, each widened by the margin."""
    import habitat_interior as hi
    import human_entry as he
    q = s['production']['sector']; m = q['margin_m']; out = []
    for name, lo, hi_, el in sector_overhead_items(s):
        if '_Frame_' in name or lo[1] > q['touch_y_m']:
            continue                                     # frames bound the bays; items hanging clear below the panels pass under them
        if el['shape'] == 'tube':
            r = el.get('r1', .9); c = el['a']; lo, hi_ = [c[0]-r, lo[1], c[2]-r], [c[0]+r, hi_[1], c[2]+r]
        if lo[0]-m < x1 and x0 < hi_[0]+m:
            out.append((lo[2]-m, hi_[2]+m))
    hx, hz, hr = hi.hatch_opening(s); hr += q['hatch_margin_m']
    if abs((x0+x1)/2-hx) < hr or (x0 < hx < x1):
        dx = max(0.0, min(abs(x0-hx), abs(x1-hx))) if not (x0 < hx < x1) else 0.0
        half = math.sqrt(max(0.0, hr*hr-dx*dx)); out.append((hz-half, hz+half))
    L = he.landing(s)
    if L['well_x'][0]-m < x1 and x0 < L['well_x'][1]+m:
        out.append((L['well_z'][0]-m, L['well_z'][1]+m))
    return out


def sector_bays(s):
    xs = sorted({(round(lo[0], 4), round(hi_[0], 4)) for name, lo, hi_, _ in sector_overhead_items(s) if '_Frame_' in name})
    edges = [x for c in xs for x in c]
    return [(edges[2*i+1], edges[2*i+2]) for i in range(len(edges)//2-1) if edges[2*i+2]-edges[2*i+1] > .2]


@builder('M7.RA1')
def sector_elements(s):
    import habitat_interior as hi
    q = s['production']['entry']; sq = s['production']['sector']; out = []
    oh = next(b for b in hi.plates(s) if b['name'] == 'Interior_Overhead'); Y = oh['max'][1]; Z0, Z1 = -sq['span_z_m'], sq['span_z_m']
    seam, th, st, ins = q['seam_m'], q['panel_thickness_m'], q['fastener_m'], q['fastener_inset_m']
    down = (0.0, 1.0, 0.0); X, Zv = (1.0, 0.0, 0.0), (0.0, 0.0, 1.0)
    for b, (x0, x1) in enumerate(sector_bays(s), 1):
        free = windows_free(sector_keepouts(s, x0, x1), Z0, Z1, 0.0)
        for k, (z0, z1) in enumerate(free, 1):
            if z1-z0 < sq['panel_min_m']:
                continue
            vs, fs = box(((x0+x1)/2, Y+.0015, (z0+z1)/2), (X, down, Zv), (x1-x0-seam, .003, z1-z0-seam/2))
            out.append(element('M7.RA1', 'Trays', f'RA1_B{b}_T{k}', 'gasket', 'ENGINEERING_FLEXIBLE', 'overhead panel carrier and seam gasket', vs, fs))
            n = max(1, math.ceil((z1-z0)/sq['panel_max_m']))
            for i in range(n):
                a, c = z0+(z1-z0)*i/n+seam/2, z0+(z1-z0)*(i+1)/n-seam/2
                vs, fs = box(((x0+x1)/2, Y+.003+th/2, (a+c)/2), (X, down, Zv), (x1-x0-2*seam, th, c-a))
                out.append(element('M7.RA1', 'Panels', f'RA1_B{b}_P{k}_{i+1}', 'panel_inhabited', 'ENGINEERING_FLEXIBLE',
                                   'removable overhead service panel (ducts, power and data above)', vs, fs, bevel=q['panel_bevel_m']))
                for sx in (x0+seam+ins, x1-seam-ins):
                    for sz in (a+ins, c-ins):
                        vs, fs = box((sx, Y+.003+th+q['fastener_proud_m']/2, sz), (X, down, Zv), (st, q['fastener_proud_m'], st))
                        out.append(element('M7.RA1', 'Fasteners', f'RA1_B{b}_P{k}_{i+1}_F{len(out)}', 'fastener', 'ENGINEERING_FLEXIBLE', 'quarter-turn panel fastener', vs, fs))
    lip, hd = q['housing_lip_m'], sq['housing_depth_m']
    for name, lo, hi_, el in sector_overhead_items(s):
        if 'Aisle_Light' not in name:
            continue
        for side, z in enumerate((lo[2]-lip/2, hi_[2]+lip/2), 1):
            vs, fs = box(((lo[0]+hi_[0])/2, Y+hd/2, z), (X, down, Zv), (hi_[0]-lo[0]+2*lip, hd, lip))
        for side, x in enumerate((lo[0]-lip/2, hi_[0]+lip/2), 1):
            vs, fs = box((x, Y+hd/2, (lo[2]+hi_[2])/2), (X, down, Zv), (lip, hd, hi_[2]-lo[2]+2*lip))
            out.append(element('M7.RA1', 'Housings', f'{name}_Housing_{side}', 'housing', 'ENGINEERING_FLEXIBLE', 'aisle light housing (long sides)', vs, fs, bevel=.002))
        for side, z in enumerate((lo[2]-lip/2, hi_[2]+lip/2), 1):
            vs, fs = box(((lo[0]+hi_[0])/2, Y+hd/2, z), (X, down, Zv), (hi_[0]-lo[0], hd, lip))
            out.append(element('M7.RA1', 'Housings', f'{name}_Cap_{side}', 'housing', 'ENGINEERING_FLEXIBLE', 'aisle light housing (end caps)', vs, fs, bevel=.002))
    return out


def sector_check(s, els):
    import habitat_interior as hi
    import human_entry as he
    sq = s['production']['sector']; hx, hz, hr = hi.hatch_opening(s); L = he.landing(s); fails = []
    for q in els:
        ys = [p[1] for p in q['vs']]
        if max(ys) > sq['overhead_floor_y_m']:
            fails.append(f"{q['name']}: reaches {max(ys):.3f} m, below the overhead zone ({sq['overhead_floor_y_m']} m)")
        for p in q['vs']:
            if math.hypot(p[0]-hx, p[2]-hz) < hr-1e-6 or (L['well_x'][0] < p[0] < L['well_x'][1] and L['well_z'][0] < p[2] < L['well_z'][1]):
                fails.append(f"{q['name']}: inside the hatch opening or the landing well's column"); break
    return fails


CHECKS['M7.RA1'] = sector_check



# M8.1: the exterior production identity (ship frame, built in the FORWARD_SHIELD asset). Everything sits aft of the skin's aft face
# inside the truss envelope, on the Crown housing's aft plate, or as a marking film on the rim girder's outer face; nothing reaches the
# sunward face, the EYE wells, the Crown windows, shutters, covers, carriages or their travel, the Lance, the truss chords or the rim hardware.
def outward(vs, fs):
    """Faces wound outward (positive signed volume), so the runtime's back-face culling keeps the visible side of each solid."""
    vol = 0.0
    for f in fs:
        a = vs[f[0]]
        for i in range(1, len(f)-1):
            b, c = vs[f[i]], vs[f[i+1]]
            vol += a[0]*(b[1]*c[2]-b[2]*c[1])-a[1]*(b[0]*c[2]-b[2]*c[0])+a[2]*(b[0]*c[1]-b[1]*c[0])
    return fs if vol >= 0 else [tuple(reversed(f)) for f in fs]


def m8_element(assembly, family, name, material, cls, function, vs, fs, bevel=0.0, **meta):
    q = element(assembly, family, name, material, cls, function, vs, outward(vs, fs), bevel)
    q.update(meta)
    return q


def crown_sectors(s):
    """Crown bays (1-based) that carry the M8 sector module: the representative bay first, all twelve once it passed its gates."""
    import forward_shield as fsh
    n = len(fsh.crown(s)['bays'])
    out = [int(j) for j in s['production']['m8']['crown_sectors']]
    if any(j < 1 or j > n for j in out) or len(set(out)) != len(out):
        raise ValueError(f'crown_sectors must be distinct bays 1..{n}: {out}')
    return out


def brow_frame(s):
    """The aft face's fixed geometry: the cone (skin_aft_at), its slope, the forward-chord keep-outs and the existing joint lines."""
    import forward_shield as fsh
    c = s['forward_shield']['rear_construction']; t = fsh.truss(s)
    keep = t['member_radius']+fsh.clearance(s)
    rings = sorted({r['radius'] for k, r in enumerate(t['rings']) if f"Truss_Ring_{k+1:02}" not in t['removed']})
    return dict(skin=lambda r: fsh.skin_aft_at(s, r), truss=lambda r: fsh.truss_aft_at(s, r), slope=fsh.skin_aft_at(s, 10.0)-fsh.skin_aft_at(s, 11.0),
                keep=keep, rings=rings, hoops=list(c['joint_hoop_r_m']), joint_w=c['joint_width_m'], joint_deg=list(c['joint_deg_offsets']),
                spokes=[sp['azimuth'] for sp in t['spokes']], member=t['member_radius'])


def brow_bands(s, f):
    """Radial bands of the aft face between the joints and the forward ring chords: [(r0, r1)] before splitting into panels."""
    q = s['production']['m8']['brow']; seam = q['seam_m']; r0, r1 = q['r_m']
    cuts = [(h-f['joint_w']/2-seam/2, h+f['joint_w']/2+seam/2) for h in f['hoops']]+[(R-f['keep']-seam/2, R+f['keep']+seam/2) for R in f['rings']]
    cuts.append((q['protected_r_m']-f['joint_w']/2-seam/2, q['protected_r_m']+f['joint_w']/2+seam/2))
    out, at = [], r0
    for a, b in sorted(set(cuts)):
        if a > at:
            out.append((at, min(a, r1)))
        at = max(at, b)
    if at < r1:
        out.append((at, r1))
    return [(a, b) for a, b in out if b-a > .3]


def brow_columns(s, f, b):
    """Angular columns (degrees, unwrapped) of the Brow module of Crown bay azimuth b (degrees): the service lane on the bay azimuth between
    the joints, and the structural columns either side up to the spoke chords. Returned as functions of r (the gaps are lengths)."""
    q = s['production']['m8']['brow']; h = q['lane_half_deg']; seam = q['seam_m']
    jg = lambda r: math.degrees((f['joint_w']/2+seam/2)/r); kg = lambda r: math.degrees((f['keep']+seam/2)/r)
    return [('lane', lambda r: b-h+jg(r), lambda r: b+h-jg(r)),
            ('structure', lambda r: b+h+jg(r), lambda r: b+15.0-kg(r)),
            ('structure', lambda r: b-15.0+kg(r), lambda r: b-h-jg(r))]


def brow_point(f, r, off, phi):
    """Point off metres aft of the skin's aft face (along -X) at radius r and azimuth phi (radians)."""
    return (f['skin'](r)-off, r*math.cos(phi), r*math.sin(phi))


def brow_axes(f, r, phi):
    """(tangential, along-cone radial, aft normal) unit vectors on the aft face."""
    k = f['slope']; n = math.sqrt(1+k*k)
    return ((0.0, -math.sin(phi), math.cos(phi)), (-k/n, math.cos(phi)/n, math.sin(phi)/n), (-1/n, -k*math.cos(phi)/n, -k*math.sin(phi)/n))


def brow_aft_elements(s):
    import forward_shield as fsh
    q = s['production']['m8']['brow']; f = brow_frame(s); A = 'M8.BROW.AFT'; out = []
    off0, off1 = q['standoff_m'], q['standoff_m']+q['thickness_m']; seam = q['seam_m']; prot = q['protected_r_m']
    at = lambda r, off, phi: brow_point(f, r, off, phi)
    fn = {'lane': 'service-lane panel module in line with the Crown bay and its carriage-service hatch (crawler side, 50!AG-A02)',
          'structure': 'structural cladding module over the truss bay (replaceable panel, 14 regenerative_brow)',
          'protected': 'protected-equipment cladding over the hub, the EYE mounts and the Lance root'}
    mats = {'lane': 'ext_service', 'structure': 'ext_cladding', 'protected': 'ext_protected'}
    bands = brow_bands(s, f)
    for bay in fsh.crown(s)['bays']:
        j = bay['index']; b = math.degrees(bay['azimuth'])
        for col, (kind, lo, hi) in enumerate(brow_columns(s, f, b)):
            for r0, r1 in bands:
                n = max(1, math.ceil((r1-r0)/q['panel_max_m']))
                for i in range(n):
                    a0 = r0+(r1-r0)*i/n+(seam/2 if i else 0.0); a1 = r0+(r1-r0)*(i+1)/n-(seam/2 if i < n-1 else 0.0)
                    zone = 'protected' if a1 <= prot+1e-6 else kind
                    p0, p1 = max(lo(a0), lo(a1)), min(hi(a0), hi(a1))
                    m = max(1, math.ceil(math.radians(p1-p0)*a1/q['panel_max_width_m']))
                    for k in range(m):
                        g = math.degrees(seam/2/a0)
                        q0 = p0+(p1-p0)*k/m+(g if k else 0.0); q1 = p0+(p1-p0)*(k+1)/m-(g if k < m-1 else 0.0)
                        name = f'Prod_BrowPanel_{j:02}_{col}_{a0:.1f}_{k}'
                        lim = a1
                        if zone == 'protected':
                            lim = a1-q['boundary_line_m']-.02
                            vs, fs = bent(at, a1-q['boundary_line_m'], a1, off0, off1, q0, q1, step_deg=2.5)
                            out.append(m8_element(A, 'boundary', name+'_Line', 'ext_amber', 'ARTISTIC',
                                                  'amber boundary line of the protected-equipment zone (hub, EYE mounts, Lance root)', vs, fs, span=(a1-q['boundary_line_m'], a1, q0, q1)))
                        vs, fs = bent(at, a0, lim, off0, off1, q0, q1, step_deg=2.5)
                        out.append(m8_element(A, 'panels', name, mats[zone], 'ENGINEERING_FLEXIBLE', fn[zone], vs, fs, q['bevel_m'],
                                              span=(a0, lim, q0, q1)))
                        # quarter-turn fasteners at the panel corners, on the panel's aft face
                        for rr, pp in ((a0, q0), (a0, q1), (lim, q0), (lim, q1)):
                            rr2 = rr+(q['fastener_inset_m'] if rr == a0 else -q['fastener_inset_m'])
                            pp2 = math.radians(pp)+(q['fastener_inset_m']/rr2 if pp == q0 else -q['fastener_inset_m']/rr2)
                            t_, s_, n_ = brow_axes(f, rr2, pp2); c0 = at(rr2, off1, pp2)
                            c = tuple(c0[i]+n_[i]*q['fastener_proud_m']/2 for i in range(3))
                            vs, fs = box(c, (t_, s_, n_), (q['fastener_m'], q['fastener_m'], q['fastener_proud_m']))
                            out.append(m8_element(A, 'fasteners', name+f'_F{len(out)}', 'ext_fastener', 'ENGINEERING_FLEXIBLE',
                                                  'quarter-turn panel fastener (panel replacement interface)', vs, fs))
        # inspection caps at the forward-chord nodes of the spoke on this module's +15 deg side (one cap per node)
        sp = math.radians(b+15.0)
        for R in f['rings']:
            r = R+q['cap_offset_m']; phi = sp-(f['keep']+q['cap_radius_m']+.15)/r
            t_, s_, n_ = brow_axes(f, r, phi); c0 = at(r, off1, phi)
            vs, fs = rod(tuple(c0[i]-n_[i]*.004 for i in range(3)), tuple(c0[i]+n_[i]*q['cap_thickness_m'] for i in range(3)), q['cap_radius_m'], n=16)
            out.append(m8_element(A, 'caps', f'Prod_BrowCap_{j:02}_{R:g}', 'ext_cap', 'ENGINEERING_FLEXIBLE',
                                  'node inspection cap: view port onto the truss node attachment behind the panels (ochre maintenance cover)', vs, fs))
        # lane stencils: the sector number on the protected band and the service-lane label at the lane's outer end
        for text, r, h, mat in ((f'S{j:02}', q['stencil_r_m'], q['stencil_m'], 'ext_stencil_light'),
                                (f'C{j:02} SERVICE LANE', bands[-1][1]-.55, .26, 'ext_stencil')):
            phi = math.radians(b); t_, s_, n_ = brow_axes(f, r, phi); c0 = at(r, off1+.002, phi)
            out.append(lettering(A, 'markings', f'Prod_BrowStencil_{j:02}_{h:g}', mat,
                                 'restrained stencil: sector number and service-lane identification (ASB Spacecraft 17)', text, c0, t_, s_, h))
    return out


def brow_aft_check(s, els):
    f = brow_frame(s); fails = []
    for q in els:
        pts = [q['centre']] if 'text' in q else q['vs']
        for x, y, z in pts:
            r = math.hypot(y, z)
            if not 7.4 <= r <= 41.0:
                fails.append(f"{q['name']}: r {r:.2f} outside the aft-face panel zone"); break
            if x > f['skin'](r)-.005 or x < f['truss'](r):
                fails.append(f"{q['name']}: x {x:.3f} at r {r:.2f} leaves the space between the skin's aft face and the truss"); break
            if any(abs(r-R) < f['keep'] for R in f['rings']):
                fails.append(f"{q['name']}: inside a forward ring chord's keep-out at r {r:.2f}"); break
            phi = math.atan2(z, y)
            if any(abs(r*math.sin(phi-a)) < f['keep'] and math.cos(phi-a) > 0 for a in f['spokes']):
                fails.append(f"{q['name']}: inside a spoke chord's keep-out"); break
    return fails


def crown_frame(s):
    import exterior_hardware as eh
    import forward_shield as fsh
    cr = fsh.crown(s); rc = s['forward_shield']['rear_construction']; st = fsh.stations(s); hw = eh.table(s)
    return dict(x0=cr['x0'], r_in=cr['inner_r'], r_out=cr['outer_r'], R=st['shield_r'], rim=st['rim'], rib_half=rc['rib_width_m']/2,
                hatch_r=tuple(rc['hatch_r_m']), hatch_half=rc['hatch_tangential_m']/2, hatch_depth=rc['hatch_depth_m'], n=len(cr['bays']),
                bays={b['index']: b['azimuth'] for b in cr['bays']},
                beacons=[(sum(st['rim'])/2, math.radians(d), hw['beacon_radius_m']) for d in hw['rim_beacon_deg']])


def crown_rim_elements(s):
    q = s['production']['m8']['crown']; f = crown_frame(s); A = 'M8.CROWN.RIM'; out = []; x0 = f['x0']; half = 180.0/f['n']
    plate = lambda r, off, phi: (x0-off, r*math.cos(phi), r*math.sin(phi))          # aft of the housing's aft plate
    film = lambda x, rr, phi: (x, rr*math.cos(phi), rr*math.sin(phi))               # on the rim girder's outer face
    for j in crown_sectors(s):
        b = f['bays'][j]; B = math.degrees(b); cs, sn = math.cos(b), math.sin(b)
        local = lambda r, u, off: (x0-off, r*cs-u*sn, r*sn+u*cs)
        # graphite doubler frame round the existing ochre carriage-service hatch
        h0, h1 = f['hatch_r']; hu = f['hatch_half']; g = q['frame_gap_m']; w = q['frame_width_m']; o0 = q['standoff_m']; o1 = o0+q['frame_thickness_m']
        R0, R1, U = h0-g-w, h1+g+w, hu+g+w
        bars = [((R0, -U), (h0-g, U)), ((h1+g, -U), (R1, U)), ((h0-g, -U), (h1+g, -hu-g)), ((h0-g, hu+g), (h1+g, U))]
        for i, ((ra, ua), (rb, ub)) in enumerate(bars):
            vs = [local(r, u, o) for r in (ra, rb) for u in (ua, ub) for o in (o0, o1)]
            out.append(m8_element(A, 'frames', f'Prod_CrownDoubler_{j:02}_{i}', 'ext_doubler', 'ENGINEERING_FLEXIBLE',
                                  'doubler frame round the carriage-service hatch (hatch and mechanism unchanged; service path OPEN)', vs, BOX_FACES, .01))
        for (ra, ua) in ((R0+.08, -U+.08), (R0+.08, U-.08), (R1-.08, -U+.08), (R1-.08, U-.08), (R0+.08, 0.0), (R1-.08, 0.0)):
            vs, fs = box(local(ra, ua, o1+.006), ((1.0, 0, 0), (0, cs, sn), (0, -sn, cs)), (.012, .06, .06))
            out.append(m8_element(A, 'fasteners', f'Prod_CrownDoublerBolt_{j:02}_{len(out)}', 'ext_fastener', 'ENGINEERING_FLEXIBLE',
                                  'doubler fastener', vs, fs))
        # replaceable access panels either side of the hatch, off the partition ribs
        p0, p1 = q['panel_r_m']; seam = q['panel_seam_m']; po0, po1 = q['standoff_m'], q['standoff_m']+q['panel_thickness_m']
        for side in (-1, 1):
            a = math.degrees((U+seam)/p0); e = half-math.degrees((f['rib_half']+q['rib_keep_m'])/p0); n = q['panels_per_side']
            for k in range(n):
                lo = a+(e-a)*k/n+(math.degrees(seam/2/p0) if k else 0.0); hi = a+(e-a)*(k+1)/n-(math.degrees(seam/2/p0) if k < n-1 else 0.0)
                q0, q1 = (B+lo, B+hi) if side > 0 else (B-hi, B-lo)
                vs, fs = bent(plate, p0, p1, po0, po1, q0, q1, step_deg=1.0)
                out.append(m8_element(A, 'panels', f'Prod_CrownPanel_{j:02}_{side:+d}_{k}', 'ext_service', 'ENGINEERING_FLEXIBLE',
                                      'replaceable access panel on the housing aft plate (carriage bay equipment behind; access OPEN)', vs, fs, .008,
                                      span=(p0, p1, q0, q1)))
                for rr, pp in ((p0+.12, q0), (p0+.12, q1), (p1-.12, q0), (p1-.12, q1)):
                    ph = math.radians(pp)+(.12/rr if pp == q0 else -.12/rr)
                    vs, fs = box(plate(rr, po1+.006, ph), ((1.0, 0, 0), (0, math.cos(ph), math.sin(ph)), (0, -math.sin(ph), math.cos(ph))), (.012, .06, .06))
                    out.append(m8_element(A, 'fasteners', f'Prod_CrownPanelBolt_{j:02}_{len(out)}', 'ext_fastener', 'ENGINEERING_FLEXIBLE',
                                          'panel fastener', vs, fs))
        # thermal-break closeouts where the plate meets the rim girder and the inner wall
        e = half-math.degrees((f['rib_half']+q['rib_keep_m'])/f['r_in'])
        for i, (ra, rb) in enumerate(((f['r_in']+.02, f['r_in']+.02+q['closeout_m']), (f['r_out']-.05-q['closeout_m'], f['r_out']-.05))):
            vs, fs = bent(plate, ra, rb, q['standoff_m'], q['standoff_m']+q['closeout_thickness_m'], B-e, B+e, step_deg=1.0)
            out.append(m8_element(A, 'closeouts', f'Prod_CrownCloseout_{j:02}_{i}', 'ext_gasket', 'ENGINEERING_FLEXIBLE',
                                  'thermal-break closeout at the housing joint (insulating seal; material and seal design OPEN)', vs, fs, span=(ra, rb, B-e, B+e)))
        # rim girder outer face: the sector boundary half-stripes (two neighbouring modules make one stripe) and the sector number
        R = f['R']; fm = q['film_m']; dh = math.degrees(q['stripe_half_m']/R); xa, xb = f['rim'][0]+.05, f['rim'][1]-.05
        for side in (-1, 1):
            edge = B+side*half; q0, q1 = (edge-dh, edge) if side > 0 else (edge, edge+dh)
            pieces = [(xa, xb)]
            for xc, ab, br in f['beacons']:
                if abs(math.remainder(math.radians(edge)-ab, 2*math.pi)) < 1e-6:
                    pieces = [(xa, xc-br-q['beacon_keep_m']), (xc+br+q['beacon_keep_m'], xb)]
            for i, (u0, u1) in enumerate(pieces):
                vs, fs = bent(film, u0, u1, R+.0005, R+.0005+fm, q0, q1, step_deg=.5)
                out.append(m8_element(A, 'markings', f'Prod_CrownBoundary_{j:02}_{side:+d}_{i}', 'ext_stencil', 'ARTISTIC',
                                      'sector boundary half-stripe on the rim girder (identification only)', vs, fs, film=True))
        tan = (0.0, -sn, cs)
        out.append(lettering(A, 'markings', f'Prod_CrownNumeral_{j:02}', 'ext_stencil', 'Crown sector number on the rim girder (restrained stencil)',
                             f'C{j:02}', film(sum(f['rim'])/2, R+.0005+fm, b), tan, (1.0, 0.0, 0.0), q['numeral_m']))
        out[-1]['wrap_r'] = R+.0005+fm          # wrapped onto the rim cylinder (a flat plane would stand proud at its ends)
        out.append(lettering(A, 'markings', f'Prod_CrownHatchStencil_{j:02}', 'ext_stencil',
                             'carriage-service hatch identification (restrained stencil)', f'C{j:02} CARRIAGE SERVICE',
                             local((R1+f['r_out']-.05-q['closeout_m'])/2, 0.0, q['standoff_m']+.002), tan, (0.0, cs, sn), q['hatch_stencil_m']))
    return out


def crown_rim_check(s, els):
    f = crown_frame(s); q = s['production']['m8']['crown']; fails = []
    h0, h1 = f['hatch_r']; g = q['frame_gap_m']/2
    for e in els:
        pts = [e['centre']] if 'text' in e else e['vs']
        for x, y, z in pts:
            r = math.hypot(y, z); phi = math.atan2(z, y)
            if r > f['R']+.005:
                fails.append(f"{e['name']}: r {r:.4f} leaves the 90 m silhouette"); break
            if r >= f['R']-1e-6:                                     # rim marking film
                if not f['rim'][0] <= x <= f['rim'][1]:
                    fails.append(f"{e['name']}: marking off the rim girder"); break
                if any(math.hypot(x-xc, r*math.remainder(phi-ab, 2*math.pi)) < br+.1 for xc, ab, br in f['beacons']):
                    fails.append(f"{e['name']}: over a rim beacon"); break
                continue
            if not (f['r_in'] <= r <= f['r_out'] and f['x0']-.2 <= x <= f['x0']-.001):
                fails.append(f"{e['name']}: x {x:.3f} r {r:.2f} off the housing's aft plate (inside the housing or ahead of it)"); break
            for k in range(f['n']):                                  # partitions and ribs at the bay azimuths + half a bay
                a = 2*math.pi*(k+.5)/f['n']
                if abs(r*math.sin(phi-a)) < f['rib_half']+.1 and math.cos(phi-a) > 0:
                    fails.append(f"{e['name']}: on a partition rib"); break
            j = min(f['bays'], key=lambda i: abs(math.remainder(phi-f['bays'][i], 2*math.pi)))
            d = phi-f['bays'][j]; u = r*math.sin(d); rr = r*math.cos(d)
            if h0-g < rr < h1+g and abs(u) < f['hatch_half']+g and 'text' not in e:
                fails.append(f"{e['name']}: over the carriage-service hatch"); break
    return fails


BUILDERS['M8.BROW.AFT'] = brow_aft_elements
BUILDERS['M8.CROWN.RIM'] = crown_rim_elements
CHECKS['M8.BROW.AFT'] = brow_aft_check
CHECKS['M8.CROWN.RIM'] = crown_rim_check


def standard(s):
    """The production asset standard carried in the runtime manifest (manifest v2 `production`). The top-level maturity is M7's (the
    accepted standard); every assembly carries its own scope and maturity, so M8 candidates never borrow M7's acceptance."""
    p = s['production']; m8 = p['m8']
    out = {'status': p['status'], 'source_ref': p['evidence_ref'], 'enabled': bool(p['enabled']), 'maturity': p['maturity'],
           'representation': p['representation'],
           'assemblies': {a: dict(zone=ASSEMBLIES[a]['zone'], host=ASSEMBLIES[a]['host'], classes=list(ASSEMBLIES[a]['classes']),
                                  scope='M8' if a.startswith('M8.') else 'M7', maturity=scope(s, a)['maturity'])
                          for a in built(s)},
           'rule': 'M7 L4 visual layer (S&E 48!A23 WF-022): generated detail over unchanged engineering geometry; nodes with '
                   'layer PRODUCTION carry their assembly and maturity. Not engineering GO: no pressure, rescue, load or flight '
                   'qualification is claimed (15!A120, 15!A221).'}
    out['m8'] = {'status': m8['status'], 'source_ref': m8['evidence_ref'], 'enabled': bool(m8['enabled']), 'maturity': m8['maturity'],
                 'crown_sectors': crown_sectors(s), 'detail_range_m': m8['detail_range_m'], 'fine_range_m': m8['fine_range_m'],
                 'rule': 'M8.1 exterior identity (Brow aft face, Crown rim): L4_VISUAL_CANDIDATE until owner art review; repeating the Crown '
                         'module does not qualify any sector mechanism; shield thickness, protection and mass unqualified.'}
    return out


if __name__ == '__main__':
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from spec import load
    s = load()[0]
    print(json.dumps({'enabled': s['production']['enabled'],
                      'assemblies': {a: dict(elements=len(elements(s, a)), objects=len(families(elements(s, a))), failures=check(s, a))
                                     for a in listed(s)}}, indent=1))
