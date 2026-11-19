"""FPS aft feed train (WF_STORAGE, fuel_system.py; owner brief 2026-11-18): run tanks -> outlet valves -> metering/conditioning -> isolation
-> shadow-shield sleeves -> the cluster bay (fuel) and the four engine panels (hydrogen), with relief vents, purge, sensors, supports, the
refuelling receptacle and the IF_FPS_* interfaces. Built in place of drive.cryo_feed while the Vertex cluster is shown.

Every object carries kind, species, function, fps_id (docs/FUEL_SYSTEM.md inventory id), engineering_status and confidence; species set
the functional colour (D teal, He-3 violet, H2 blue). Geometry PROTOTYPE."""
import math

import bpy

from common import cylinder_mesh, empty, line, material, mesh
import fuel_system as fs
from storage import LINE_COLOR, box_mesh, hoop_mesh, merge

COLOR = {'deuterium': (.20, .62, .60), 'helium-3': (.55, .38, .80), 'hydrogen': (.28, .52, .82), 'helium': (.70, .70, .66), 'none': (.80, .78, .70)}
EQUIP = (.74, .72, .66)
OPEN = 'PROTOTYPE geometry (FPS V0); OPEN: '


def stamp(obj, s, species, function, fps_id, confidence='PLAUSIBLE', open_=''):
    obj['species'] = species; obj['function'] = function; obj['fps_id'] = fps_id; obj['fps_version'] = s['fuel_system']['version']
    obj['storage_group'] = 'FPS_AFT_FEED'; obj['confidence'] = confidence
    obj['engineering_status'] = OPEN+(open_ or s['fuel_system']['open'])
    return obj


def _oriented_box(at, size, axis_y, axis_z):
    """Box centred at `at`, X along the ship axis, its Y/Z edges along the given radial and tangential unit vectors."""
    sx, sy, sz = size; vs = []
    for dx in (-1, 1):
        for dy in (-1, 1):
            for dz in (-1, 1):
                vs.append(tuple(at[i]+(dx*sx/2 if i == 0 else 0)+dy*sy/2*axis_y[i]+dz*sz/2*axis_z[i] for i in range(3)))
    return vs, [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]


def _axes(y, z):
    r = math.hypot(y, z) or 1.0; ry = (0.0, y/r, z/r); rt = (0.0, -z/r, y/r)
    return ry, rt


def build(c, s):
    # Species lines take the farm's PMDS-bound line materials (APP-FEED-CRYO jacket); the purge lines take the bound CryoFeed jacket.
    mat = {sp: material(f'Fuel_Line_{fs.TAG[sp]}', LINE_COLOR[sp]) for sp in fs.SPECIES}
    mat['helium'] = material('CryoFeed', (.55, .74, .86)); mat['none'] = material('FPS_Service', COLOR['none'])
    equip = material('FPS_Equipment', EQUIP); bracket = material('FPS_Support', (.36, .38, .42))
    for ln in fs.feed_lines(s):
        sp = ln['species']; tag = ln['name'].split('_', 2)[2]
        obj = line(c, ln['name'], ln['points'], ln['radius'], mat[sp], kind='fps_feed_line')
        fn = ('fuel feed: run tank -> metering unit -> isolation -> stepped shield sleeve -> cluster bay (target fabrication inlet)' if sp != 'hydrogen'
              else 'reaction-mass feed: run tank -> boost pump -> conditioning skid -> isolation -> shield sleeve -> corridor -> inside the thrust ring -> H2 header')
        stamp(obj, s, sp, fn, f"FPS-DL-{tag}", 'ESTABLISHED', 'jacket and bore sizing, thermal intercepts, line supports past the corridor')
        obj['tank'] = ln['tank']; obj['role'] = fs.ROLE[sp]; obj['liquid_bore_mm_first_order'] = round(fs.bore_m(fs.flows(s)[sp]['kg_s'], fs.fst.cfg(s)['density_kg_m3'][fs.fst.INV_KEY[sp]])*1e3, 1)
        i = empty(c, f"IF_FPS_SHIELD_{tag.upper()}", ln['shield_point'])
        i['engineering_status'] = 'OPEN: stepped (dog-leg) shadow-shield sleeve; thermal intercepts, labyrinth shielding and streaming dose not designed (OD-026)'
        i['species'] = sp; i['feed_line'] = ln['name']
        tank = bpy.data.objects.get(ln['tank'])
        if tank is not None:
            tank['fuel_family'] = sp; tank['feed_line'] = ln['name']; tank['family_assignment'] = 'PROTOTYPE (15!G69)'; tank['role'] = fs.ROLE[sp]
    for e in fs.equipment(s):
        sp = e['species']; y, z = e['at'][1:]; ry, rt = _axes(y, z)
        if e['shape'] == 'box':
            vs, fc = _oriented_box(e['at'], e['size'], ry, rt)
        else:
            x = e['at'][0]; vs, fc = cylinder_mesh((x+e['length']/2, y, z), (x-e['length']/2, y, z), e['radius'], 24)
        obj = mesh(c, e['name'], vs, fc, equip if e['kind'] != 'fps_valve' else mat[sp], kind=e['kind'])
        conf = 'ESTABLISHED' if e['kind'] in ('fps_valve', 'fps_pump') else 'PLAUSIBLE'
        stamp(obj, s, sp, e['function'], 'FPS-'+{'fps_valve': 'VL', 'fps_pump': 'PU', 'fps_conditioner': 'CU'}[e['kind']]+'-'+e['name'].split('_')[-2]+'-'+e['name'].split('_')[-1],
              conf, 'hardware selection, mass, power and mounting')
        obj['feed_line'] = e['line']
    h = fs.header(s)
    obj = mesh(c, h['name'], *hoop_mesh(h['x'], 0.0, 0.0, h['r'], h['tube'], 96, 8), mat['hydrogen'], kind='fps_feed_line')
    stamp(obj, s, 'hydrogen', 'H2 header ring forward of the cluster hub: two trunks in (A at 225 deg, B at 315 deg), one branch out per engine; either trunk feeds all four',
          'FPS-HD-H2', 'ESTABLISHED')
    for b in fs.branches(s):
        obj = line(c, b['name'], b['points'], b['radius'], mat['hydrogen'], kind='fps_feed_line')
        stamp(obj, s, 'hydrogen', f"H2 branch to engine N{b['engine']}'s collar inlet (header -> between the cluster's thrust struts -> along the engine axis)",
              f"FPS-BR-N{b['engine']}", 'PLAUSIBLE', 'branch flow control at the panel, flexible section across the engine trunnion')
    for q in fs.sensors(s):
        f = s['fuel_system']['feed']['sensor']; r = f['extra_m']+s['fuel_system']['feed']['line_radius_m']; parts = []
        line_pts = {l['name']: l['points'] for l in fs.feed_lines(s)} | {b['name']: b['points'] for b in fs.branches(s)}
        pts = line_pts[q['line']]
        for p in q['points']:
            seg = min(zip(pts, pts[1:]), key=lambda ab: fs._seg_d(p, *ab)); d = [seg[1][i]-seg[0][i] for i in range(3)]; L = math.sqrt(sum(x*x for x in d))
            u = [x/L*f['length_m']/2 for x in d]
            parts.append(cylinder_mesh(tuple(p[i]-u[i] for i in range(3)), tuple(p[i]+u[i] for i in range(3)), r, 16))
        obj = mesh(c, q['name'], *merge(parts), equip, kind='fps_sensor')
        stamp(obj, s, q['species'], f"pressure, temperature and flow sensor sleeves on {q['line']} ({len(parts)} stations); leak detection by pressure decay and the jacket vacuum",
              'FPS-IN-'+q['name'].split('_')[-1], 'ESTABLISHED', 'sensor selection and redundancy')
    sup = fs.supports(s)
    for name in sorted({u['line'] for u in sup}):
        own = [u for u in sup if u['line'] == name]
        obj = mesh(c, f"FPS_Supports_{name.split('_')[-1]}", *merge([cylinder_mesh(u['a'], u['b'], u['radius'], 8) for u in own]), bracket, kind='fps_support')
        stamp(obj, s, 'none', f'{len(own)} sliding line clamps from {name} to the primary frames (axial slide for cold contraction)', 'FPS-SS-'+name.split('_')[-1], 'ESTABLISHED')
    for r in fs.relief(s):
        sp = r['species']; t = r['tank'][-2:]; y, z = r['valve'][1:]; ry, rt = _axes(y, z)
        obj = mesh(c, f'FPS_Relief_Valve_{t}', *_oriented_box(r['valve'], (r['size'],)*3, ry, rt), mat[sp], kind='fps_valve')
        stamp(obj, s, sp, f"relief valve on {r['tank']}'s forward head (boil-off and overpressure)", f'FPS-RV-{t}', 'ESTABLISHED', 'set pressure and flow capacity')
        obj = line(c, f'FPS_Vent_{t}', r['vent'], r['radius'], mat[sp], kind='fps_vent_line')
        stamp(obj, s, sp, f"vent line from {r['tank']}'s relief valve through the hull", f'FPS-VT-{t}', 'ESTABLISHED', 'hull penetration and vent sizing')
        obj = mesh(c, f'FPS_Vent_Tee_{t}', *cylinder_mesh(r['tee'][0], r['tee'][1], r['radius']*1.6, 12), equip, kind='fps_vent_line')
        stamp(obj, s, sp, 'non-propulsive tee outlet: two opposite nozzles along X, so venting adds no net thrust', f'FPS-VT-{t}-TEE', 'ESTABLISHED')
    for p in fs.purge(s):
        x, y, z = p['at']
        obj = mesh(c, p['name'], *cylinder_mesh((x+p['length']/2, y, z), (x-p['length']/2, y, z), p['radius'], 20), mat['helium'], kind='fps_purge')
        stamp(obj, s, 'helium', 'helium purge bottle: inerts the H2 line before maintenance and after a trip (He does not freeze at 20 K)', 'FPS-PG-'+p['name'][-1], 'ESTABLISHED',
              'bottle volume and pressure')
        obj = line(c, p['name']+'_Line', p['line'], p['line_radius'], mat['helium'], kind='fps_purge')
        stamp(obj, s, 'helium', 'purge line to the H2 isolation valve', 'FPS-PG-'+p['name'][-1]+'-L', 'ESTABLISHED')
    rf = fs.refuel(s); pn = rf['panel']; a = pn['azimuth']; ry = (0.0, math.cos(a), math.sin(a)); rt = (0.0, -math.sin(a), math.cos(a))
    obj = mesh(c, pn['name'], *_oriented_box(pn['at'], (pn['size'][1], pn['size'][2], pn['size'][0]), ry, rt), equip, kind='fps_refuel')
    stamp(obj, s, 'none', 'refuelling receptacle on the farm deck rim: the tanker umbilical mates here (one dry-break coupling per species, bonding, data)', 'FPS-RF-PANEL',
          'ESTABLISHED', 'coupling standard, approach corridor and umbilical loads')
    for l in rf['lines']:
        sp = l['species']; tg = fs.TAG[sp]
        obj = line(c, l['name'], l['points'], l['radius'], mat[sp], kind='fps_refuel')
        stamp(obj, s, sp, f"fill line from the {tg} coupling to {l['main']}", f'FPS-RF-{tg}', 'ESTABLISHED')
        cp = l['coupling']; obj = mesh(c, f'FPS_Refuel_Coupling_{tg}', *cylinder_mesh(cp, tuple(cp[i]+ry[i]*0.35 for i in range(3)), rf['coupling_radius'], 20), mat[sp], kind='fps_refuel')
        stamp(obj, s, sp, f'{tg} dry-break refuelling coupling', f'FPS-RF-{tg}-C', 'ESTABLISHED')
        v = l['valve']; obj = mesh(c, f'FPS_Refuel_Valve_{tg}', *_oriented_box(v, (0.30, 0.30, 0.30), ry, rt), mat[sp], kind='fps_valve')
        stamp(obj, s, sp, f'{tg} fill isolation valve', f'FPS-RF-{tg}-V', 'ESTABLISHED')
    for i in fs.interfaces(s):
        e = empty(c, i['name'], i['at']); e['engineering_status'] = 'OPEN: '+i['note']; e['species'] = i['species']; e['fps_interface'] = True
