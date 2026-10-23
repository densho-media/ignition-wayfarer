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


def pack_assemblies(s):
    """{assembly: manifest table} of the detail packs loaded with the spec (data/detail/*.toml, modules.py); empty without them."""
    out = {}
    for name, q in s.get('detail_packs', {}).items():
        for a, t in q.get('assembly', {}).items():
            out[a] = dict(t, pack=name)
    return out


def pack_of(s, assembly):
    t = pack_assemblies(s).get(assembly)
    return s['detail_packs'][t['pack']] if t else None


def params(s, pack):
    """A pack's own [params] (its manifest), the parameters that used to live in [production.*]."""
    return s['detail_packs'][pack]['params']


def meta(s, assembly):
    """Zone, host and classes of an assembly: the legacy table, or its pack manifest (host from its anchor)."""
    if assembly in ASSEMBLIES:
        return ASSEMBLIES[assembly]
    import modules
    t = pack_assemblies(s)[assembly]
    return dict(host=modules.anchor_host(t['anchor']), zone=t['zone'], classes=tuple(t['classes']))


def scope(s, assembly):
    """The table that switches and labels an assembly: [production] for M7, [production.m8] for M8 (independently switchable); a pack
    assembly takes the scope its manifest names (M7, M8, or its own [pack] table)."""
    q = pack_of(s, assembly)
    if q is not None:
        sc = q['pack']['scope']
        return s['production'] if sc == 'M7' else s['production']['m8'] if sc == 'M8' else q['pack']
    return s['production']['m8'] if assembly.startswith('M8.') else s['production']


def scope_label(s, assembly):
    q = pack_of(s, assembly)
    return q['pack']['scope'].replace('pack', 'PACK') if q is not None else 'M8' if assembly.startswith('M8.') else 'M7'


def built(s):
    """Assemblies the build makes, M7 then M8, each scope by its own switch, then the enabled detail packs (each also behind its scope's)."""
    p = s['production']; m8 = p.get('m8', {})
    legacy = (list(p['assemblies']) if p['enabled'] else [])+(list(m8['assemblies']) if m8.get('enabled') else [])
    return legacy+[a for a in pack_assemblies(s) if enabled(s, a)]


def listed(s):
    p = s['production']
    return list(p['assemblies'])+list(p.get('m8', {}).get('assemblies', []))+list(pack_assemblies(s))


def enabled(s, assembly=None):
    if assembly is None:
        return bool(built(s))
    q = pack_of(s, assembly)
    if q is not None:
        return bool(q['pack']['enabled']) and bool(scope(s, assembly)['enabled'])
    q = scope(s, assembly)
    return bool(q['enabled']) and assembly in q['assemblies']


def material_value(s, key):
    """[r, g, b, roughness, metallic] of a production material: [production.materials] or the exterior [production.m8.materials]."""
    p = s['production']
    if key in p['materials']:
        return p['materials'][key]
    if key in p['m8']['materials']:
        return p['m8']['materials'][key]
    # A pack's own finishes ([materials] in its manifest); the key must be unique across the shared tables and the packs.
    found = [q['materials'][key] for q in s.get('detail_packs', {}).values() if key in q.get('materials', {})]
    if len(found) != 1:
        raise KeyError(f'production material {key}: {len(found)} definitions')
    return found[0]


def element(assembly, family, name, material, cls, function, vs, fs, bevel=0.0):
    if assembly not in ASSEMBLIES and assembly not in BUILDERS:
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


def wbox_pts(q):
    c, ax, size = q['centre'], q['axes'], q['size']
    return [tuple(c[i]+sx*size[0]/2*ax[0][i]+sy*size[1]/2*ax[1][i]+sz*size[2]/2*ax[2][i] for i in range(3)) for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)]




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
           'assemblies': {a: dict(zone=meta(s, a)['zone'], host=meta(s, a)['host'], classes=list(meta(s, a)['classes']),
                                  scope=scope_label(s, a), maturity=scope(s, a)['maturity'],
                                  **({'pack': pack_assemblies(s)[a]['pack'], 'detail_class': pack_of(s, a)['pack']['detail_class']}
                                     if pack_of(s, a) is not None else {}))
                          for a in built(s)},
           'rule': 'M7 L4 visual layer (S&E 48!A23 WF-022): generated detail over unchanged engineering geometry; nodes with '
                   'layer PRODUCTION carry their assembly and maturity. Not engineering GO: no pressure, rescue, load or flight '
                   'qualification is claimed (15!A120, 15!A221).'}
    out['m8'] = {'status': m8['status'], 'source_ref': m8['evidence_ref'], 'enabled': bool(m8['enabled']), 'maturity': m8['maturity'],
                 'crown_sectors': crown_sectors(s), 'detail_range_m': m8['detail_range_m'], 'fine_range_m': m8['fine_range_m'],
                 'rule': 'M8.1 exterior identity (Brow aft face, Crown rim): L4_VISUAL_CANDIDATE until owner art review; repeating the Crown '
                         'module does not qualify any sector mechanism; shield thickness, protection and mass unqualified.'}
    return out


def load_packs():
    """Import every detail pack's code (src/wayfarer/detail/pack_*.py) once; each registers its builders and screens here."""
    import importlib.util
    import sys
    from pathlib import Path
    for path in sorted((Path(__file__).resolve().parent/'detail').glob('pack_*.py')):
        if path.stem not in sys.modules:
            spec = importlib.util.spec_from_file_location(path.stem, path)
            module = importlib.util.module_from_spec(spec); sys.modules[path.stem] = module
            spec.loader.exec_module(module)


def main():
    from spec import load
    s = load()[0]
    print(json.dumps({'enabled': s['production']['enabled'],
                      'assemblies': {a: dict(elements=len(elements(s, a)), objects=len(families(elements(s, a))), failures=check(s, a))
                                     for a in listed(s)}}, indent=1))


if __name__ == '__main__':
    # Run through the imported module so the packs register into the same tables the build and the tests use.
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import production_detail
    production_detail.main()
else:
    load_packs()
