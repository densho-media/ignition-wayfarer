"""Production detail core (PROTOTYPE, standard library only): the shared L4 presentation-layer machinery every detail pack builds with.

S&E 48!A23 (WF-022) defines L4 PRODUCTION as linked models, rigs, materials, lighting and stable exports; this module adds the generated
production detail of the boarding path, primary port -> entry chamber -> stationary trunk -> ring-A spin transfer -> ring-A crew tube ->
ring-A sector 1, on top of the unchanged engineering geometry. It follows route_fitout (the ARCHITECTURE layer): every element has a job the
route already needs (panel mounting and service access, frames that carry the panels, handhold brackets, fixture housings, identification)
and the culture decides how it looks. Only the engineering-flexible and artistic surface classes are detailed (15!I120); physics-locked
parts keep REP_PROXY grey with no hero finish (15!H120). Nothing here carries load or changes a pressure boundary, an interface, a volume or
the clear route: check() keeps every element outside the clearances the route already has.

Every assembly is a detail pack (docs/MODULES.md: data/detail/<pack>.toml, src/wayfarer/detail/pack_<pack>.py), built into its own detail
asset in its anchor's frame. An element is a closed mesh in that frame, with its assembly, family (the generator joins one family of an
assembly into one object, so the runtime gets a few batched meshes, not one object per stud), production material, surface class and
function. This core holds the registration (builder, CHECKS), the scope switches and labels ([production] for M7, [production.m8] for M8,
or a pack's own), the shared materials, the M7 panel grammar helpers and the runtime manifest block; the packs hold their builders and
parameters. `python3 src/wayfarer/production_detail.py` prints the element counts and the check.
"""
import json
import math

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
    """Zone, host and classes of an assembly, from its pack manifest (host from its anchor)."""
    import modules
    t = pack_assemblies(s)[assembly]
    return dict(host=modules.anchor_host(t['anchor']), zone=t['zone'], classes=tuple(t['classes']))


def scope(s, assembly):
    """The table that switches and labels an assembly: the scope its pack names, [production] for M7, [production.m8] for M8
    (independently switchable), or the pack's own [pack] table."""
    q = pack_of(s, assembly); sc = q['pack']['scope']
    return s['production'] if sc == 'M7' else s['production']['m8'] if sc == 'M8' else q['pack']


def scope_label(s, assembly):
    return pack_of(s, assembly)['pack']['scope'].replace('pack', 'PACK')


def built(s):
    """Assemblies the build makes: every enabled pack assembly whose scope is switched on."""
    return [a for a in pack_assemblies(s) if enabled(s, a)]


def listed(s):
    return list(pack_assemblies(s))


def enabled(s, assembly=None):
    if assembly is None:
        return bool(built(s))
    return bool(pack_of(s, assembly)['pack']['enabled']) and bool(scope(s, assembly)['enabled'])


def material_value(s, key):
    """[r, g, b, roughness, metallic] of a production material: [production.materials] (M7 interior standard), the Phase 4 exterior
    families [production.exterior.families] (xf_*) or a pack's own [materials]."""
    p = s['production']
    if key in p['materials']:
        return p['materials'][key]
    if key in p['exterior']['families']:
        return p['exterior']['families'][key]
    # A pack's own finishes ([materials] in its manifest); the key must be unique across the shared tables and the packs.
    found = [q['materials'][key] for q in s.get('detail_packs', {}).values() if key in q.get('materials', {})]
    if len(found) != 1:
        raise KeyError(f'production material {key}: {len(found)} definitions')
    return found[0]


# Phase 4 exterior grammar ([production.exterior], owner S1 selection 2026-10-24): helpers every exterior pack shares.
def marking_height(s, cls):
    """Cap height (m) of a text-only marking of class cls legible at its reading distance: marking_px_min pixels in the reference camera."""
    x = s['production']['exterior']; d = x['marking_read_m'][cls]
    return round(d*2*math.tan(math.radians(x['ref_hfov_deg'])/2)*x['marking_px_min']/x['ref_width_px'], 3)


def tier_of(s, size_m):
    """Scale tier (macro, meso, micro) of a feature by its largest dimension, or None below the micro floor (model it as value or seam)."""
    m = s['production']['exterior']['tier_min_feature_m']
    return next((t for t in ('macro', 'meso', 'micro') if size_m >= m[t]), None)


def area(q):
    """Surface area (m2) of an element's faces (fan triangulation)."""
    vs = q['vs']; total = 0.0
    for f in q['fs']:
        a = vs[f[0]]
        for i in range(1, len(f)-1):
            b, c = vs[f[i]], vs[f[i+1]]
            n = cross([b[k]-a[k] for k in range(3)], [c[k]-a[k] for k in range(3)])
            total += math.sqrt(sum(x*x for x in n))/2
    return total


def accent_report(s, els):
    """{material: share of the elements' area} for the accent families, with the fails against [production.exterior] accent_area_max.
    Lettering counts by its cap-height box. Area is half the closed surface (one visible face of a thin part, roughly)."""
    cap = s['production']['exterior']['accent_area_max']; by = {}
    for q in els:
        a = q['height']**2*len(q['text'])*.6 if 'text' in q else area(q)/2
        by[q['material']] = by.get(q['material'], 0.0)+a
    total = sum(by.values()) or 1.0
    share = {k: by.get(k, 0.0)/total for k in cap}
    return share, [f'{k}: {v:.1%} of the detail area exceeds {cap[k]:.0%}' for k, v in share.items() if v > cap[k]]


def ship_family(s, material_name):
    """Exterior family (xf_* key, or None to keep its own look) of a generated engineering material (WF_MAT_<name> without the prefix)."""
    for rule in s['production']['exterior']['ship_families']:
        if material_name.startswith(tuple(rule['prefixes'])):
            return None if rule['family'] == 'none' else rule['family']
    return None


def element(assembly, family, name, material, cls, function, vs, fs, bevel=0.0):
    if assembly not in BUILDERS:
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




def outward(vs, fs):
    """Faces wound outward (positive signed volume), so the runtime's back-face culling keeps the visible side of each solid."""
    vol = 0.0
    for f in fs:
        a = vs[f[0]]
        for i in range(1, len(f)-1):
            b, c = vs[f[i]], vs[f[i+1]]
            vol += a[0]*(b[1]*c[2]-b[2]*c[1])-a[1]*(b[0]*c[2]-b[2]*c[0])+a[2]*(b[0]*c[1]-b[1]*c[0])
    return fs if vol >= 0 else [tuple(reversed(f)) for f in fs]


def crown_sectors(s):
    """Crown bays (1-based) that carry the M8 sector module: the representative bay first, all twelve once it passed its gates."""
    import forward_shield as fsh
    n = len(fsh.crown(s)['bays'])
    out = [int(j) for j in s['production']['m8']['crown_sectors']]
    if any(j < 1 or j > n for j in out) or len(set(out)) != len(out):
        raise ValueError(f'crown_sectors must be distinct bays 1..{n}: {out}')
    return out




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
