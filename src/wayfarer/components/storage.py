"""S01/F01 STORAGE recipe (fuel_storage, TANK-AXIAL): the longitudinal tank farm (thirteen axial vessels on their skirts and thrust deck,
forward guides, ring mains, outlets and valves, cryocoolers, transfer trunks), the four feed run tanks, the dry store in the body bay and the
body frames and CMGs. Geometry PROTOTYPE; the architecture is WORKING (owner brief 2026-11-01).

Every object carries kind, species, storage_group, function and engineering_status; the vessels also their number, liquid volume, capacity
and first-order shell (fuel_loads.vessels). Viewport colours: helium-3 amber, deuterium violet, hydrogen pale blue, dry storage olive."""
import math

from common import cylinder, cylinder_mesh, empty, line, material, mesh
import body_equipment as beq
import fuel_loads
import fuel_storage as fst

SPECIES_COLOR = {'helium-3': (.86, .62, .22), 'deuterium': (.48, .38, .80), 'hydrogen': (.50, .76, .92)}
LINE_COLOR = {'helium-3': (.62, .42, .12), 'deuterium': (.32, .24, .60), 'hydrogen': (.28, .52, .70)}
DRY_COLOR = (.50, .52, .36)
FARM = 'FWD_TANK_FARM'


def stamp(obj, s, species, function, group=FARM):
    f = s['fuel_storage']
    obj['canon_status'] = f['canon_status']; obj['source_ref'] = f['source_ref']; obj['species'] = species; obj['storage_group'] = group
    obj['function'] = function; obj['storage_role'] = function
    obj['engineering_status'] = 'PROTOTYPE geometry (TANK-AXIAL architecture WORKING); OPEN: '+f['open']
    return obj


def merge(parts):
    vs, fs = [], []
    for v, f in parts:
        n = len(vs); vs += v; fs += [tuple(i+n for i in q) for q in f]
    return vs, fs


def vessel_mesh(t, n=48, nh=8):
    """Insulated envelope of an axial vessel: barrel of radius a_env between its Y-rings, 2:1 ellipsoidal heads to the apexes."""
    a = t['a_env']; h = t['head']+(t['a_env']-t['a']); x0, x1 = t['x0'], t['x1']; ya, yf = x0+h, x1-h
    rings = [(ya-h*math.cos(u), a*math.sin(u)) for u in (math.pi/2*k/nh for k in range(1, nh+1))]
    rings += [(yf+h*math.sin(u), a*math.cos(u)) for u in (math.pi/2*k/nh for k in range(0, nh))]
    vs = [(x, t['y']+r*math.cos(math.tau*k/n), t['z']+r*math.sin(math.tau*k/n)) for x, r in rings for k in range(n)]
    m = len(rings); fs = [(j*n+k, (j+1)*n+k, (j+1)*n+(k+1) % n, j*n+(k+1) % n) for j in range(m-1) for k in range(n)]
    vs += [(x0, t['y'], t['z']), (x1, t['y'], t['z'])]; a0, a1 = len(vs)-2, len(vs)-1
    fs += [(a0, k, (k+1) % n) for k in range(n)]+[(a1, (m-1)*n+(k+1) % n, (m-1)*n+k) for k in range(n)]
    return vs, fs


def hoop_mesh(x, cy, cz, r, tube, n=96, m=8):
    """Torus about an X-parallel axis through (cy, cz): major radius r, tube radius `tube`."""
    vs = []
    for i in range(n):
        p = math.tau*i/n
        for j in range(m):
            q = math.tau*j/m; rr = r+tube*math.cos(q)
            vs.append((x+tube*math.sin(q), cy+rr*math.cos(p), cz+rr*math.sin(p)))
    return vs, [(i*m+j, i*m+(j+1) % m, ((i+1) % n)*m+(j+1) % m, ((i+1) % n)*m+j) for i in range(n) for j in range(m)]


def box_mesh(cx, cy, cz, sx, sy, sz):
    vs = [(cx+dx*sx/2, cy+dy*sy/2, cz+dz*sz/2) for dx in (-1, 1) for dy in (-1, 1) for dz in (-1, 1)]
    return vs, [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]


def build(c, s):
    farm(c, s)
    dry_store(c, s)
    body(c, s)
    tank_mat = material('Tank', (.39, .48, .56))
    ft = s['physics']['fuel_tanks']
    for t in fst.run_tanks(s):
        obj = cylinder(c, t['name'], (t['x0']+t['x1'])/2, t['x1']-t['x0'], t['radius'], tank_mat, t['y'], t['z'])
        obj['representation'] = ft['representation']; obj['dimensions_status'] = ft['dimensions_status']; obj['fuel_mass_known'] = False
        obj['storage_role'] = 'feed run tank: transfer buffer and feed conditioning ahead of the shadow shield (volume OPEN)'


def farm(c, s):
    tag = fst.SPECIES_TAG; shell = {r['name']: r for r in fuel_loads.vessels(s)}
    vmat = {sp: material(f'Fuel_{tag[sp]}', col) for sp, col in SPECIES_COLOR.items()}
    lmat = {sp: material(f'Fuel_Line_{tag[sp]}', col) for sp, col in LINE_COLOR.items()}
    skirt_mat = material('Fuel_Skirt_CFRP', (.30, .26, .22)); deck_mat = material('Fuel_Deck', (.42, .44, .47))
    guide_mat = material('Fuel_Guide', (.36, .38, .42)); valve_mat = material('Fuel_Valve', (.75, .72, .66))
    cold = material('Fuel_Cryocooler', (.82, .80, .74))
    for t in fst.tanks(s):
        sp = t['species']; v = shell[t['name']]
        obj = mesh(c, t['name'], *vessel_mesh(t), vmat[sp], kind='fuel_tank')
        stamp(obj, s, sp, f"{t['ring']} ring {tag[sp]} pressure vessel, class {t['tank_class']} (axis parallel to X)")
        obj['tank_number'] = t['id']; obj['tank_class'] = t['tank_class']; obj['azimuth_deg'] = t['azimuth_deg']
        obj['liquid_m3'] = round(t['liquid_m3'], 1); obj['capacity_t'] = round(v['cap_kg']/1e3, 1)
        obj['envelope_d_m'] = 2*t['a_env']; obj['shell_thickness_mm_first_order'] = round(v['thickness_m']*1e3, 1)
        obj['shell_t_first_order'] = round(v['shell_kg']/1e3, 1)
        # aft support: seat ring on the deck and the insulating skirt struts up to the aft Y-ring
        st = fst.seat(s, t)
        parts = [hoop_mesh(st['x'], t['y'], t['z'], st['r'], 0.12, 64, 6)]
        parts += [cylinder_mesh(k['a'], k['b'], k['radius'], 8) for k in fst.skirt_struts(s, t)]
        obj = mesh(c, f"Fuel_Skirt_{t['id']}", *merge(parts), skirt_mat, kind='fuel_support')
        stamp(obj, s, 'none', f"aft fixity of {t['name']}: seat ring and {len(parts)-1} insulating CFRP skirt struts to the aft Y-ring")
        obj['tank_number'] = t['id']
        lk = fst.forward_links(s, t)
        obj = mesh(c, f"Fuel_Fwd_Link_{t['id']}", *merge([cylinder_mesh(k['a'], k['b'], k['radius'], 8) for k in lk]), guide_mat, kind='fuel_support')
        stamp(obj, s, 'none', f"forward lateral guide of {t['name']}: sliding V-link (axial travel for cold contraction)"); obj['tank_number'] = t['id']
    dk = fst.deck(s)
    for tr in dk['trusses']:
        obj = mesh(c, tr['name'], *merge([cylinder_mesh(a, b, tr['radius'] if i < 2 else tr['radius']*0.6, 8) for i, (a, b) in enumerate(tr['members'])]),
                   deck_mat, kind='fuel_support')
        stamp(obj, s, 'none', f"aft thrust deck: radial two-chord truss under {tr['tank']}, cantilevered from the collar frame")
    for hp in dk['hoops']:
        obj = mesh(c, hp['name'], *hoop_mesh(hp['x'], 0.0, 0.0, hp['r'], hp['radius']), deck_mat, kind='fuel_support')
        stamp(obj, s, 'none', 'aft thrust deck hoop tying the radial trusses')
    for ct in fst.collar_ties(s):
        obj = mesh(c, ct['name'], *merge([cylinder_mesh(a, b, ct['radius'], 12) for a, b in ct['members']]), deck_mat, kind='fuel_support')
        stamp(obj, s, 'none', f"tip ties of {ct['truss']} to the bypass collar's forward hoop (the outer truss spans collar -> collar hoop)")
    lac = fst.ring_lacing(s)
    obj = mesh(c, lac['name'], *merge([cylinder_mesh(a, b, lac['radius'], 12) for a, b in lac['members']]), deck_mat, kind='fuel_support')
    stamp(obj, s, 'none', "lacing between the bypass collar's mid and forward hoops: a 5.6 m deep ring girder carrying the deck tips to the bypass girders")
    for r in fst.keel_rails(s):
        obj = mesh(c, r['name'], *cylinder_mesh(r['a'], r['b'], r['radius'], 12), guide_mat, kind='fuel_support')
        stamp(obj, s, 'none', f"keel rail on the inboard side of {r['tank']}: carries its forward link")
    fh = fst.forward_hoop(s)
    obj = mesh(c, fh['name'], *hoop_mesh(fh['x'], 0.0, 0.0, fh['r'], fh['radius']), guide_mat, kind='fuel_support')
    stamp(obj, s, 'none', 'forward hoop tying the keel rails')
    obj = mesh(c, 'Fuel_Forward_Ties', *merge([cylinder_mesh(k['a'], k['b'], k['radius'], 12) for k in fh['ties']]), guide_mat, kind='fuel_support')
    stamp(obj, s, 'none', 'forward hoop ties to the collar')
    for rm in fst.ring_mains(s):
        obj = mesh(c, rm['name'], *hoop_mesh(rm['x'], 0.0, 0.0, rm['r'], rm['radius'], 128, 6), lmat[rm['species']], kind='fuel_transfer_line')
        stamp(obj, s, rm['species'], f"{tag[rm['species']]} ring main on the deck ({rm['ring']} ring): joins the vessel outlets, two-way fed")
    for o in fst.outlets(s):
        obj = line(c, o['name'], o['points'], o['radius'], lmat[o['species']], kind='fuel_transfer_line')
        stamp(obj, s, o['species'], f"outlet from the aft apex (sump under thrust) of {o['tank']} to its ring main")
        vv = o['valve']; obj = mesh(c, vv['name'], *box_mesh(vv['x'], vv['y'], vv['z'], vv['size'], vv['size'], vv['size']), valve_mat, kind='fuel_equipment')
        stamp(obj, s, o['species'], f"isolation and metering valve of {o['tank']} (reachable from the deck)")
    for q in fst.cryocoolers(s):
        ca, sa = math.cos(q['azimuth']), math.sin(q['azimuth']); vs = []
        for x in (q['x']-q['length']/2, q['x']+q['length']/2):
            for r in (q['r0'], q['r1']):
                for w in (-q['width']/2, q['width']/2):
                    vs.append((x, r*ca-w*sa, r*sa+w*ca))
        obj = mesh(c, q['name'], vs, [(0, 2, 3, 1), (4, 5, 7, 6), (0, 1, 5, 4), (2, 6, 7, 3), (0, 4, 6, 2), (1, 3, 7, 5)], cold, kind='fuel_equipment')
        sp = {v: k for k, v in tag.items()}[q['species']]
        stamp(obj, s, sp, f"{q['species']} cryocooler cold box on the deck's aft face (lift, power and heat rejection OPEN)")
    for ln in fst.transfer_lines(s):
        obj = line(c, ln['name'], ln['points'], ln['radius'], lmat[ln['species']], kind='fuel_transfer_line')
        stamp(obj, s, ln['species'], f"transfer {ln['source']} -> {ln['tank']} ({ln['leg']} leg)"); obj['tank'] = ln['tank']
        if ln.get('hull_penetration'):
            iface = empty(c, f"IF_FUEL_HULL_{ln['name'].split('_', 2)[2].upper()}", ln['hull_penetration'])
            iface['engineering_status'] = 'OPEN: cryogenic hull penetration (sleeve, thermal break, seal and isolation valve not designed)'
        if ln['leg'] == 'interior':
            iface = empty(c, f"IF_FUEL_RUN_TANK_{ln['name'].split('_', 2)[2].upper()}", ln['points'][-1])
            iface['engineering_status'] = 'OPEN: run-tank inlet (valve, transfer pump and flow control not designed)'


def dry_store(c, s):
    mat = material('Dry_Store', DRY_COLOR)
    for d in fst.dry_containers(s):
        obj = mesh(c, d['name'], *box_at(d['x0'], d['x1'], d['r0'], d['r1'], math.radians(d['azimuth_deg']), d['width']), mat, kind='dry_storage')
        stamp(obj, s, 'none', 'standard dry-storage container on a rack (workshop, spares, cargo; S&E 13 midship service volume)', 'BODY_DRY_STORE')
        obj['module'] = d['module']; obj['sector'] = d['sector']; obj['volume_m3'] = round(d['volume_m3'], 2)


def box_at(x0, x1, r0, r1, a, w):
    """Box spanning x0..x1 and r0..r1 along azimuth a, w wide tangentially: vertices and faces."""
    ca, sa = math.cos(a), math.sin(a); vs = []
    for x in (x0, x1):
        for r in (r0, r1):
            for t in (-w/2, w/2):
                vs.append((x, r*ca-t*sa, r*sa+t*ca))
    return vs, [(0, 2, 3, 1), (4, 5, 7, 6), (0, 1, 5, 4), (2, 6, 7, 3), (0, 4, 6, 2), (1, 3, 7, 5)]


def body(c, s):
    """S04 internal ring frames and utility-frame beams in the body bay, and the S02 control-moment gyros on the beams
    (body_equipment, PROTOTYPE)."""
    frame_mat = material('Body_Frame', (.36, .30, .24)); cmg_mat = material('Body_CMG', (.72, .72, .70))
    for f in beq.frames(s):
        if 'deg' in f:
            obj = mesh(c, f['name'], *box_at(f['x']-f['depth']/2, f['x']+f['depth']/2, f['r0'], f['r1'], math.radians(f['deg']), f['width']), frame_mat,
                       kind='body_frame')
            obj['function'] = 'utility-frame beam: equipment mount for a CMG (PROTOTYPE; sizing and loads OPEN)'
        else:
            from common import annulus
            obj = annulus(c, f['name'], f['x'], f['width'], f['r1'], f['r0'], frame_mat); obj['kind'] = 'body_frame'
            obj['function'] = 'internal ring frame between body modules, outside the keel rails (PROTOTYPE; sizing OPEN)'
        obj['engineering_status'] = 'PROTOTYPE'
    sz = beq.sizing(s)
    for u in beq.cmgs(s):
        a = u['a']; ra = (0.0, math.cos(a), math.sin(a)); p = lambda x, r: (x, r*ra[1], r*ra[2])
        vs, fs = cylinder_mesh(p(u['x'], u['r']-u['housing']/2), p(u['x'], u['r']+u['housing']/2), u['housing']/2, 32)
        g = u['gimbal']/2; v2, f2 = cylinder_mesh((u['x']-0.04, *p(0, u['r'])[1:]), (u['x']+0.04, *p(0, u['r'])[1:]), g, 32)
        n = len(vs); vs += v2; fs += [tuple(i+n for i in q) for q in f2]
        v3, f3 = box_at(u['cradle'][0], u['cradle'][1]+0.02, u['r']-0.25, u['r']+0.25, a, 0.40)
        n = len(vs); vs += v3; fs += [tuple(i+n for i in q) for q in f3]
        obj = mesh(c, u['name'], vs, fs, cmg_mat, kind='body_equipment')
        obj['function'] = 'double-gimbal control-moment gyro on its cradle (S02 momentum storage, S&E 37 F17)'
        obj['momentum_N_m_s'] = sz['per_unit_N_m_s']; obj['rotor_rpm'] = sz['rotor_rpm']; obj['engineering_status'] = sz['status']+'; mass, power and loads OPEN'
