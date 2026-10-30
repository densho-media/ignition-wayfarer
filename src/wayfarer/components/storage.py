"""S01/F01 STORAGE recipe (fuel_storage): the helium-3 body stations, the hydrogen/deuterium torus behind the Brow with its struts, the
transfer lines and the four feed run tanks the drive feed lines start from. Geometry PROTOTYPE; the split is WORKING (FUEL-SPLIT)."""
import math

from common import cylinder, cylinder_mesh, empty, line, material, mesh
import fuel_storage as fst

SPECIES_COLOR = {'helium-3': (.62, .66, .72), 'deuterium': (.50, .60, .74), 'hydrogen': (.70, .74, .78)}


def sector_solid(x0, x1, r0, r1, a0, a1, n=16):
    """Closed annular-sector solid about +X."""
    ring = [(r0, a0+(a1-a0)*k/n) for k in range(n+1)]+[(r1, a1-(a1-a0)*k/n) for k in range(n+1)]
    m = len(ring); vs = [(x, r*math.cos(a), r*math.sin(a)) for x in (x0, x1) for r, a in ring]
    fs = [(k, (k+1) % m, m+(k+1) % m, m+k) for k in range(m)]
    fs += [tuple(reversed(range(m))), tuple(m+k for k in range(m))]
    return vs, fs


def torus_cell(tor, c, n_arc=48, n_sec=24):
    """One torus vessel cell: the tube swept from a0 to a1 at major radius R about +X through x, closed by 2:1 ellipsoidal heads where
    heads[i] is set and by a flat bulkhead otherwise."""
    R, a, xc = tor['R'], tor['a'], tor['x']; h = tor['head']
    def tube_point(phi, th, r=a, along=0.0):
        rr = R+r*math.cos(th); x = xc+r*math.sin(th)
        t = (-math.sin(phi), math.cos(phi))          # tangent of the major circle
        return (x, rr*math.cos(phi)+along*t[0], rr*math.sin(phi)+along*t[1])
    na = max(4, int(n_arc*(c['a1']-c['a0'])/math.pi))
    rows = [[tube_point(c['a0']+(c['a1']-c['a0'])*i/na, math.tau*k/n_sec) for k in range(n_sec)] for i in range(na+1)]
    for end, sign in ((0, -1), (1, 1)):
        phi = c['a0'] if end == 0 else c['a1']
        if c['heads'][end]:
            caps = [[tube_point(phi, math.tau*k/n_sec, a*math.cos(u), sign*h*math.sin(u)) for k in range(n_sec)] for u in (math.pi/6, math.pi/3)]
            tip = tube_point(phi, 0.0, 0.0, sign*h)
        else:
            caps, tip = [], tube_point(phi, 0.0, 0.0)
        if end == 0:
            rows = caps[::-1]+rows; first_tip = tip
        else:
            rows = rows+caps; last_tip = tip
    vs = [p for row in rows for p in row]+[first_tip, last_tip]
    nr = len(rows); fs = [(i*n_sec+k, i*n_sec+(k+1) % n_sec, (i+1)*n_sec+(k+1) % n_sec, (i+1)*n_sec+k) for i in range(nr-1) for k in range(n_sec)]
    t0, t1 = len(vs)-2, len(vs)-1
    fs += [(t0, (k+1) % n_sec, k) for k in range(n_sec)]+[(t1, (nr-1)*n_sec+k, (nr-1)*n_sec+(k+1) % n_sec) for k in range(n_sec)]
    return vs, fs


def stamp(obj, s, species, role):
    f = s['fuel_storage']
    obj['canon_status'] = f['canon_status']; obj['source_ref'] = f['source_ref']; obj['species'] = species; obj['storage_role'] = role
    obj['engineering_status'] = 'PROTOTYPE geometry (FUEL-SPLIT WORKING); OPEN: '+f['open']
    return obj


def build(c, s):
    lobe_mat = material('Fuel_He3_Station', SPECIES_COLOR['helium-3'])
    for lb in fst.body_lobes(s):
        obj = mesh(c, lb['name'], *sector_solid(lb['x0'], lb['x1'], lb['r_in'], lb['r_out'], lb['a0'], lb['a1']), lobe_mat, kind='fuel_tank')
        stamp(obj, s, lb['species'], 'body station (BODY-C3)'); obj['liquid_m3'] = round(lb['liquid_m3'], 1); obj['module'] = lb['module']
    tor = fst.torus(s)
    for cell in tor['cells']:
        obj = mesh(c, cell['name'], *torus_cell(tor, cell), material(f"Fuel_Torus_{'D2' if cell['species'] == 'deuterium' else 'H2'}", SPECIES_COLOR[cell['species']]), kind='fuel_tank')
        stamp(obj, s, cell['species'], 'forward torus vessel'); obj['liquid_m3'] = round(cell['liquid_m3'], 1); obj['vessel'] = cell['vessel']
    strut_mat = material('Fuel_Torus_Strut', (.30, .40, .48))
    for st in fst.torus_struts(s):
        obj = mesh(c, st['name'], *cylinder_mesh(st['a'], st['b'], st['radius'], 16), strut_mat, kind='fuel_support')
        stamp(obj, s, 'none', 'torus strut on the forward hull collar')
    line_mat = material('CryoFeed', (.55, .74, .86))
    for ln in fst.transfer_lines(s):
        obj = line(c, ln['name'], ln['points'], ln['radius'], line_mat, kind='fuel_transfer_line')
        stamp(obj, s, ln['species'], f"transfer {ln['source']} -> {ln['tank']} ({ln['leg']} leg)"); obj['tank'] = ln['tank']
        if ln.get('hull_penetration'):
            iface = empty(c, f"IF_FUEL_HULL_{ln['name'].split('_', 2)[2].upper()}", ln['hull_penetration'])
            iface['engineering_status'] = 'OPEN: cryogenic hull penetration (sleeve, thermal break, seal and isolation valve not designed)'
        iface = empty(c, f"IF_FUEL_RUN_TANK_{ln['name'].split('_', 2)[2].upper()}", ln['points'][-1]) if ln['leg'] == 'interior' else None
        if iface:
            iface['engineering_status'] = 'OPEN: run-tank inlet (valve, transfer pump and flow control not designed)'
    metal = material('Fuel_Mount', (.30, .40, .48))
    for hg in fst.lobe_hangers(s):
        vs, fs = [], []
        for a, b in hg['struts']:
            v, f = cylinder_mesh(a, b, hg['radius'], 8); n = len(vs); vs += v; fs += [tuple(i+n for i in q) for q in f]
        obj = mesh(c, hg['name'], vs, fs, metal, kind='fuel_support'); stamp(obj, s, 'none', 'lobe hangers to the keel rails (S04)')
    cold = material('Fuel_Cryocooler', (.80, .78, .72))
    for q in fst.cryocoolers(s):
        ca, sa = math.cos(q['azimuth']), math.sin(q['azimuth']); vs = []
        for x in (q['x']-q['length']/2, q['x']+q['length']/2):
            for r in (q['r0'], q['r1']):
                for w in (-q['width']/2, q['width']/2):
                    vs.append((x, r*ca-w*sa, r*sa+w*ca))
        obj = mesh(c, q['name'], vs, [(0, 2, 3, 1), (4, 5, 7, 6), (0, 1, 5, 4), (2, 6, 7, 3), (0, 4, 6, 2), (1, 3, 7, 5)], cold, kind='fuel_equipment')
        stamp(obj, s, 'helium-3 / 20 K', 'cryocooler cold-box on a utility frame (S04 equipment mount; lift, power and heat rejection OPEN)')
    tank_mat = material('Tank', (.39, .48, .56))
    ft = s['physics']['fuel_tanks']
    for t in fst.run_tanks(s):
        obj = cylinder(c, t['name'], (t['x0']+t['x1'])/2, t['x1']-t['x0'], t['radius'], tank_mat, t['y'], t['z'])
        obj['representation'] = ft['representation']; obj['dimensions_status'] = ft['dimensions_status']; obj['fuel_mass_known'] = False
        obj['storage_role'] = 'feed run tank: transfer buffer and feed conditioning ahead of the shadow shield (volume OPEN)'
