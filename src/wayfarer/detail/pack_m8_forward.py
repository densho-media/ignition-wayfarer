"""Detail pack m8_forward (docs/MODULES.md): the M8.1 exterior production identity on the forward structure, module WF-FWD. M8.BROW.AFT (panel
modules, caps, fasteners and stencils on the Brow's aft face between the existing joints) and M8.CROWN.RIM (the sector module on the Aegis
Crown housing's aft plate and the rim girder's markings), both on the anchor WF-FWD.FORWARD_SHIELD.ORIGIN, the forward-shield asset's
origin (ship frame). Both stay static: the Crown's carriages, shutters, covers and heads move, the housing plate and the rim girder the
detail sits on do not, and no element is parented to anything that moves.

Owned with data/detail/m8_forward.toml (manifest, [params.brow] and [params.crown]) and the generated assets
assets/wayfarer/detail/WF_DETAIL_M8_BROW_AFT.blend and WF_DETAIL_M8_CROWN_RIM.blend, which WF_FORWARD_SHIELD links. Scope M8 ([production.m8]:
its own switch, L4_VISUAL_CANDIDATE until the owner's art review, the Crown bays in crown_sectors, the exterior materials and the Godot draw
ranges); migrated unchanged from production_detail.py (MOD phase 2). Reads forward_shield; changes nothing in it: the sunward face, the EYE
wells, the Crown windows, shutters, covers, carriages and their travel, the Lance, the truss chords and the rim hardware stay as they are.
"""
import math
import production_detail as pd

PACK = 'm8_forward'


# M8.1: the exterior production identity (ship frame). Everything sits aft of the skin's aft face inside the truss envelope, on the Crown
# housing's aft plate, or as a marking film on the rim girder's outer face; nothing reaches the sunward face, the EYE wells, the Crown
# windows, shutters, covers, carriages or their travel, the Lance, the truss chords or the rim hardware.
def m8_element(assembly, family, name, material, cls, function, vs, fs, bevel=0.0, **meta):
    q = pd.element(assembly, family, name, material, cls, function, vs, pd.outward(vs, fs), bevel)
    q.update(meta)
    return q


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
    q = pd.params(s, PACK)['brow']; seam = q['seam_m']; r0, r1 = q['r_m']
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
    q = pd.params(s, PACK)['brow']; h = q['lane_half_deg']; seam = q['seam_m']
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
    q = pd.params(s, PACK)['brow']; f = brow_frame(s); A = 'M8.BROW.AFT'; out = []
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
                            vs, fs = pd.bent(at, a1-q['boundary_line_m'], a1, off0, off1, q0, q1, step_deg=2.5)
                            out.append(m8_element(A, 'boundary', name+'_Line', 'ext_amber', 'ARTISTIC',
                                                  'amber boundary line of the protected-equipment zone (hub, EYE mounts, Lance root)', vs, fs, span=(a1-q['boundary_line_m'], a1, q0, q1)))
                        vs, fs = pd.bent(at, a0, lim, off0, off1, q0, q1, step_deg=2.5)
                        out.append(m8_element(A, 'panels', name, mats[zone], 'ENGINEERING_FLEXIBLE', fn[zone], vs, fs, q['bevel_m'],
                                              span=(a0, lim, q0, q1)))
                        # quarter-turn fasteners at the panel corners, on the panel's aft face
                        for rr, pp in ((a0, q0), (a0, q1), (lim, q0), (lim, q1)):
                            rr2 = rr+(q['fastener_inset_m'] if rr == a0 else -q['fastener_inset_m'])
                            pp2 = math.radians(pp)+(q['fastener_inset_m']/rr2 if pp == q0 else -q['fastener_inset_m']/rr2)
                            t_, s_, n_ = brow_axes(f, rr2, pp2); c0 = at(rr2, off1, pp2)
                            c = tuple(c0[i]+n_[i]*q['fastener_proud_m']/2 for i in range(3))
                            vs, fs = pd.box(c, (t_, s_, n_), (q['fastener_m'], q['fastener_m'], q['fastener_proud_m']))
                            out.append(m8_element(A, 'fasteners', name+f'_F{len(out)}', 'ext_fastener', 'ENGINEERING_FLEXIBLE',
                                                  'quarter-turn panel fastener (panel replacement interface)', vs, fs))
        # inspection caps at the forward-chord nodes of the spoke on this module's +15 deg side (one cap per node)
        sp = math.radians(b+15.0)
        for R in f['rings']:
            r = R+q['cap_offset_m']; phi = sp-(f['keep']+q['cap_radius_m']+.15)/r
            t_, s_, n_ = brow_axes(f, r, phi); c0 = at(r, off1, phi)
            vs, fs = pd.rod(tuple(c0[i]-n_[i]*.004 for i in range(3)), tuple(c0[i]+n_[i]*q['cap_thickness_m'] for i in range(3)), q['cap_radius_m'], n=16)
            out.append(m8_element(A, 'caps', f'Prod_BrowCap_{j:02}_{R:g}', 'ext_cap', 'ENGINEERING_FLEXIBLE',
                                  'node inspection cap: view port onto the truss node attachment behind the panels (ochre maintenance cover)', vs, fs))
        # lane stencils: the sector number on the protected band and the service-lane label at the lane's outer end
        for text, r, h, mat in ((f'S{j:02}', q['stencil_r_m'], q['stencil_m'], 'ext_stencil_light'),
                                (f'C{j:02} SERVICE LANE', bands[-1][1]-.55, .26, 'ext_stencil')):
            phi = math.radians(b); t_, s_, n_ = brow_axes(f, r, phi); c0 = at(r, off1+.002, phi)
            out.append(pd.lettering(A, 'markings', f'Prod_BrowStencil_{j:02}_{h:g}', mat,
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
    q = pd.params(s, PACK)['crown']; f = crown_frame(s); A = 'M8.CROWN.RIM'; out = []; x0 = f['x0']; half = 180.0/f['n']
    plate = lambda r, off, phi: (x0-off, r*math.cos(phi), r*math.sin(phi))          # aft of the housing's aft plate
    film = lambda x, rr, phi: (x, rr*math.cos(phi), rr*math.sin(phi))               # on the rim girder's outer face
    for j in pd.crown_sectors(s):
        b = f['bays'][j]; B = math.degrees(b); cs, sn = math.cos(b), math.sin(b)
        local = lambda r, u, off: (x0-off, r*cs-u*sn, r*sn+u*cs)
        # graphite doubler frame round the existing ochre carriage-service hatch
        h0, h1 = f['hatch_r']; hu = f['hatch_half']; g = q['frame_gap_m']; w = q['frame_width_m']; o0 = q['standoff_m']; o1 = o0+q['frame_thickness_m']
        R0, R1, U = h0-g-w, h1+g+w, hu+g+w
        bars = [((R0, -U), (h0-g, U)), ((h1+g, -U), (R1, U)), ((h0-g, -U), (h1+g, -hu-g)), ((h0-g, hu+g), (h1+g, U))]
        for i, ((ra, ua), (rb, ub)) in enumerate(bars):
            vs = [local(r, u, o) for r in (ra, rb) for u in (ua, ub) for o in (o0, o1)]
            out.append(m8_element(A, 'frames', f'Prod_CrownDoubler_{j:02}_{i}', 'ext_doubler', 'ENGINEERING_FLEXIBLE',
                                  'doubler frame round the carriage-service hatch (hatch and mechanism unchanged; service path OPEN)', vs, pd.BOX_FACES, .01))
        for (ra, ua) in ((R0+.08, -U+.08), (R0+.08, U-.08), (R1-.08, -U+.08), (R1-.08, U-.08), (R0+.08, 0.0), (R1-.08, 0.0)):
            vs, fs = pd.box(local(ra, ua, o1+.006), ((1.0, 0, 0), (0, cs, sn), (0, -sn, cs)), (.012, .06, .06))
            out.append(m8_element(A, 'fasteners', f'Prod_CrownDoublerBolt_{j:02}_{len(out)}', 'ext_fastener', 'ENGINEERING_FLEXIBLE',
                                  'doubler fastener', vs, fs))
        # replaceable access panels either side of the hatch, off the partition ribs
        p0, p1 = q['panel_r_m']; seam = q['panel_seam_m']; po0, po1 = q['standoff_m'], q['standoff_m']+q['panel_thickness_m']
        for side in (-1, 1):
            a = math.degrees((U+seam)/p0); e = half-math.degrees((f['rib_half']+q['rib_keep_m'])/p0); n = q['panels_per_side']
            for k in range(n):
                lo = a+(e-a)*k/n+(math.degrees(seam/2/p0) if k else 0.0); hi = a+(e-a)*(k+1)/n-(math.degrees(seam/2/p0) if k < n-1 else 0.0)
                q0, q1 = (B+lo, B+hi) if side > 0 else (B-hi, B-lo)
                vs, fs = pd.bent(plate, p0, p1, po0, po1, q0, q1, step_deg=1.0)
                out.append(m8_element(A, 'panels', f'Prod_CrownPanel_{j:02}_{side:+d}_{k}', 'ext_service', 'ENGINEERING_FLEXIBLE',
                                      'replaceable access panel on the housing aft plate (carriage bay equipment behind; access OPEN)', vs, fs, .008,
                                      span=(p0, p1, q0, q1)))
                for rr, pp in ((p0+.12, q0), (p0+.12, q1), (p1-.12, q0), (p1-.12, q1)):
                    ph = math.radians(pp)+(.12/rr if pp == q0 else -.12/rr)
                    vs, fs = pd.box(plate(rr, po1+.006, ph), ((1.0, 0, 0), (0, math.cos(ph), math.sin(ph)), (0, -math.sin(ph), math.cos(ph))), (.012, .06, .06))
                    out.append(m8_element(A, 'fasteners', f'Prod_CrownPanelBolt_{j:02}_{len(out)}', 'ext_fastener', 'ENGINEERING_FLEXIBLE',
                                          'panel fastener', vs, fs))
        # thermal-break closeouts where the plate meets the rim girder and the inner wall
        e = half-math.degrees((f['rib_half']+q['rib_keep_m'])/f['r_in'])
        for i, (ra, rb) in enumerate(((f['r_in']+.02, f['r_in']+.02+q['closeout_m']), (f['r_out']-.05-q['closeout_m'], f['r_out']-.05))):
            vs, fs = pd.bent(plate, ra, rb, q['standoff_m'], q['standoff_m']+q['closeout_thickness_m'], B-e, B+e, step_deg=1.0)
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
                vs, fs = pd.bent(film, u0, u1, R+.0005, R+.0005+fm, q0, q1, step_deg=.5)
                out.append(m8_element(A, 'markings', f'Prod_CrownBoundary_{j:02}_{side:+d}_{i}', 'ext_stencil', 'ARTISTIC',
                                      'sector boundary half-stripe on the rim girder (identification only)', vs, fs, film=True))
        tan = (0.0, -sn, cs)
        out.append(pd.lettering(A, 'markings', f'Prod_CrownNumeral_{j:02}', 'ext_stencil', 'Crown sector number on the rim girder (restrained stencil)',
                             f'C{j:02}', film(sum(f['rim'])/2, R+.0005+fm, b), tan, (1.0, 0.0, 0.0), q['numeral_m']))
        out[-1]['wrap_r'] = R+.0005+fm          # wrapped onto the rim cylinder (a flat plane would stand proud at its ends)
        out.append(pd.lettering(A, 'markings', f'Prod_CrownHatchStencil_{j:02}', 'ext_stencil',
                             'carriage-service hatch identification (restrained stencil)', f'C{j:02} CARRIAGE SERVICE',
                             local((R1+f['r_out']-.05-q['closeout_m'])/2, 0.0, q['standoff_m']+.002), tan, (0.0, cs, sn), q['hatch_stencil_m']))
    return out


def crown_rim_check(s, els):
    f = crown_frame(s); q = pd.params(s, PACK)['crown']; fails = []
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


pd.BUILDERS['M8.BROW.AFT'] = brow_aft_elements
pd.BUILDERS['M8.CROWN.RIM'] = crown_rim_elements
pd.CHECKS['M8.BROW.AFT'] = brow_aft_check
pd.CHECKS['M8.CROWN.RIM'] = crown_rim_check
