"""S02 recipe (exterior_hardware): docking guidance, airlock floodlights, position beacons (slice 1), high-gain dishes, the optical terminal
and RCS pods (slice 2) as PROTOTYPE boxes, discs and dishes. The service-side parts build with WF_SERVICE, the rim beacons and rim RCS pods
with WF_FORWARD_SHIELD (forward structure)."""
import math

from common import cylinder_mesh, material, mesh
import exterior_hardware as eh
import human_entry as he

FACES = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
LIGHT = {'white': (.95, .95, .90), 'amber': (1.0, .62, .12)}


def dish_mesh(q, n=48, rings=8, thick=0.04):
    """Closed paraboloid shell: front surface from the vertex along the axis to the rim, back surface thick behind it."""
    v, ax, R, h = q['vertex'], q['axis'], q['radius'], q['depth']
    hlp = (0.0, 0.0, 1.0) if abs(ax[2]) < 0.9 else (1.0, 0.0, 0.0)
    e1 = (ax[1]*hlp[2]-ax[2]*hlp[1], ax[2]*hlp[0]-ax[0]*hlp[2], ax[0]*hlp[1]-ax[1]*hlp[0]); m = math.sqrt(sum(c*c for c in e1)); e1 = tuple(c/m for c in e1)
    e2 = (ax[1]*e1[2]-ax[2]*e1[1], ax[2]*e1[0]-ax[0]*e1[2], ax[0]*e1[1]-ax[1]*e1[0])
    vs = []
    for off in (0.0, -thick):
        vs.append(tuple(v[i]+ax[i]*off for i in range(3)))
        for j in range(1, rings+1):
            rr = R*j/rings; z = h*(rr/R)**2+off
            for k in range(n):
                a = 2*math.pi*k/n; vs.append(tuple(v[i]+ax[i]*z+(e1[i]*math.cos(a)+e2[i]*math.sin(a))*rr for i in range(3)))
    B = len(vs)//2; idx = lambda base, j, k: base+1+(j-1)*n+k % n; fs = []
    for base, flip in ((0, False), (B, True)):
        for k in range(n):
            f = (base, idx(base, 1, k), idx(base, 1, k+1)); fs.append(f[::-1] if flip else f)
        for j in range(1, rings):
            for k in range(n):
                f = (idx(base, j, k), idx(base, j+1, k), idx(base, j+1, k+1), idx(base, j, k+1)); fs.append(f[::-1] if flip else f)
    for k in range(n):
        fs.append((idx(0, rings, k), idx(B, rings, k), idx(B, rings, k+1), idx(0, rings, k+1)))
    return vs, fs


def build(c, items):
    made = []
    for q in items:
        if q['shape'] == 'dish':
            mat = material('Ext_Antenna_Dish', (.80, .78, .72))           # M4 off-white (as the root boots): the dish's thermal finish
        elif q['kind'] == 'comms_antenna':
            mat = material('Ext_Antenna_Boom', (.55, .56, .58))
        elif q.get('jet'):
            mat = material('Ext_RCS_Nozzle', (.16, .19, .22))            # M4 dark (as the joints): refractory nozzle
        elif q.get('rcs'):
            mat = material('Ext_RCS_Pod', (.55, .56, .58))
        elif q.get('light'):
            mat = material(f"Ext_Light_{q['light'].title()}", LIGHT[q['light']], emission=2.0)
        elif q.get('emissive') is False:
            mat = material('Ext_Dock_Target', (.90, .90, .88))
        else:
            mat = material('Ext_Sensor', (.24, .26, .29))
        if q['shape'] == 'dish':
            obj = mesh(c, q['name'], *dish_mesh(q), mat, kind=q['kind'])
        elif q['shape'] == 'tube':
            obj = mesh(c, q['name'], *cylinder_mesh(q['a'], q['b'], q['r1']), mat, kind=q['kind'])
        else:
            obj = mesh(c, q['name'], he.box_corners(None, q), FACES, mat, kind=q['kind'])
        obj['role'] = q['role']; obj['geometry_status'] = 'PROTOTYPE'; obj['evidence_ref'] = 'dock_ports' if 'fitting' in q else ''
        obj['owner_status'] = ('OPEN: S&E 37 F14 / F16 name the function; band, rate, aperture, thrust and placement are unsized (S02 slice 2, PROTOTYPE bounding case)'
                               if q['kind'] in ('comms_antenna', 'rcs_thruster') or q.get('rcs') or q.get('jet') else
                               'OPEN: no owner row sizes or places docking aids, floodlights or beacons (S02 slice 1, PROTOTYPE judgment)')
        if q.get('antenna'):
            obj['antenna'] = q['antenna']; obj['boresight'] = (-1.0, 0.0, 0.0); obj['sweep_radius_m'] = q['sweep']
        if q.get('jet'):
            obj['jet_direction'] = q['jet']
        if q.get('fitting'):
            obj['fitting'] = q['fitting']
        made.append(obj)
    return made


def service(c, s):
    return build(c, eh.service_parts(s))+casing(c, s)


def casing(c, s):
    """S04 slice 1 (casing_panels): longitudinal and hoop joint straps as two meshes, one plate per access panel. Faces wound outward
    (Phase 4 S9: the runtime lit their inward faces from the back and self-shadowed them)."""
    import casing_panels as cp
    from production_detail import outward
    import hull_geometry as hg
    q = cp.table(s); R = hg.radius_at(s, 0.0); r0, r1 = R-.005, R+q['seam_height_m']; w = q['seam_width_m']; x0, x1 = q['x_range_m']
    mat = material('Casing_Strap', (.16, .19, .22)); made = []     # M4 dark joints
    rad = lambda x, r, a: (x, r*math.cos(a), r*math.sin(a))
    vs, fs = [], []
    for a in cp.long_lines(s):
        dt = w/2/R; b = len(vs)
        for x in (x0, x1):
            vs += [rad(x, r0, a-dt), rad(x, r0, a+dt), rad(x, r1, a+dt), rad(x, r1, a-dt)]
        fs += [(b, b+1, b+2, b+3)[::-1], (b+4, b+5, b+6, b+7)]+[(b+i, b+(i+1) % 4, b+4+(i+1) % 4, b+4+i) for i in range(4)]
    made.append(mesh(c, 'Casing_Seams_Long', vs, outward(vs, fs), mat, kind='casing_detail'))
    vs, fs = [], []
    for x in cp.stations(s):
        for a0, a1 in cp.hoop_arcs(s):
            n = max(2, int((a1-a0)/math.radians(3))); b = len(vs)
            for k in range(n+1):
                a = a0+(a1-a0)*k/n; vs += [rad(x-w/2, r0, a), rad(x+w/2, r0, a), rad(x+w/2, r1, a), rad(x-w/2, r1, a)]
            for k in range(n):
                i, j = b+4*k, b+4*(k+1)
                fs += [(i+m, j+m, j+(m+1) % 4, i+(m+1) % 4) for m in range(4)]
            fs += [(b, b+1, b+2, b+3), tuple(reversed(range(b+4*n, b+4*n+4)))]
    made.append(mesh(c, 'Casing_Seams_Hoop', vs, outward(vs, fs), mat, kind='casing_detail'))
    # S04 slice 3: the forward collar's straps, broken round its openings and fitting aids (casing_panels.collar_straps).
    _, _, Rc = cp.collar(s); c0, c1 = Rc-.005, Rc+q['seam_height_m']
    for kind_, name in (('long', 'Casing_Collar_Seams_Long'), ('hoop', 'Casing_Collar_Seams_Hoop')):
        vs, fs = [], []
        for k, v, lo, hi in cp.collar_straps(s):
            if k != kind_:
                continue
            n = 1 if k == 'long' else max(2, int((hi-lo)/math.radians(3))); b = len(vs)
            for i in range(n+1):
                u = lo+(hi-lo)*i/n
                if k == 'long':
                    dt = w/2/Rc; vs += [rad(u, c0, v-dt), rad(u, c0, v+dt), rad(u, c1, v+dt), rad(u, c1, v-dt)]
                else:
                    vs += [rad(v-w/2, c0, u), rad(v+w/2, c0, u), rad(v+w/2, c1, u), rad(v-w/2, c1, u)]
            for i in range(n):
                i0, j0 = b+4*i, b+4*(i+1)
                fs += [(i0+m, j0+m, j0+(m+1) % 4, i0+(m+1) % 4) for m in range(4)]
            fs += [(b, b+1, b+2, b+3), tuple(reversed(range(b+4*n, b+4*n+4)))]
        made.append(mesh(c, name, vs, outward(vs, fs), mat, kind='casing_detail'))
    pmat = material('Casing_Access_Panel', (.78, .60, .24))     # M4 ochre service covers (15!A202)
    for p in cp.access_panels(s):
        L, W, D = p['size']; a = p['theta']; dt = W/2/R; vs = []
        for x in (p['x']-L/2, p['x']+L/2):
            vs += [rad(x, r0, a-dt), rad(x, r0, a+dt), rad(x, R+D, a+dt), rad(x, R+D, a-dt)]
        obj = mesh(c, p['name'], vs, outward(vs, [(0, 1, 2, 3)[::-1], (4, 5, 6, 7)]+[(i, (i+1) % 4, 4+(i+1) % 4, 4+i) for i in range(4)]), pmat,
                   kind='casing_detail')
        obj['role'] = 'casing access panel over the cage-to-skin corridor (feed lines, root chases, drone rails) beside the keel lane'
        made.append(obj)
    for obj in made:
        obj['geometry_status'] = 'PROTOTYPE'; obj['owner_status'] = 'OPEN: no owner row sizes casing joints or access panels (S04 slice 1, PROTOTYPE judgment)'
    return made


def forward(c, s):
    import forward_shield as fsh
    made = build(c, eh.forward_parts(s)); cls = fsh.design_classes(s)
    for obj in made:                     # HSFP (98!A58): every forward-structure kind carries its design class
        obj['design_class'] = cls[obj['kind']]
    return made
