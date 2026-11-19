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

COLOR = {'target': (.42, .50, .70), 'deuterium': (.20, .62, .60), 'helium-3': (.55, .38, .80), 'hydrogen': (.28, .52, .82), 'helium': (.70, .70, .66), 'none': (.80, .78, .70)}
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
    if fs.v1(s):
        build_v1(c, s, mat, equip, bracket)
    if fs.v11(s):
        build_v11(c, s, mat, equip, bracket)
    for i in fs.interfaces(s):
        e = empty(c, i['name'], i['at']); e['engineering_status'] = 'OPEN: '+i['note']; e['species'] = i['species']; e['fps_interface'] = True


def _dir(a, b):
    d = [b[i]-a[i] for i in range(3)]; L = math.sqrt(sum(x*x for x in d)) or 1.0
    return [x/L for x in d]


def _flanges(pts, r, fl):
    """Flange discs at both ends and every bend of a polyline (bolted joints, drawn as short wider cylinders)."""
    out = []; k = fl['radius_factor']*r; h = fl['length_m']/2
    for i, p in enumerate(pts):
        u = _dir(pts[i-1], p) if i else _dir(p, pts[1])
        out.append(cylinder_mesh(tuple(p[j]-u[j]*h for j in range(3)), tuple(p[j]+u[j]*h for j in range(3)), k, 16))
    return out


def _stamp_v1(obj, s, species, function, fps_id, confidence='PLAUSIBLE', open_='', owner='FPS', pipe_class=''):
    stamp(obj, s, species, function, fps_id, confidence, open_)
    obj['fps_version'] = s['fuel_system']['v1']['version']; obj['fps_milestone'] = 'V1'; obj['owner_workstream'] = owner
    if pipe_class:
        obj['pipe_class'] = pipe_class
    return obj


def build_v1(c, s, mat, equip, bracket):
    """FPS V1 connections (fuel_system.feedthroughs .. h2_injection): the farm transfer chain closed at the hull and the run tanks, the
    H2 ring-main crossover, and on every engine the target feed and the hydrogen injection train (CANDIDATES for the engine workstream)."""
    v = s['fuel_system']['v1']; fl = v['flange']; spec_ = {p['id']: p for p in fs.pipe_spec(s)}
    cls = {'deuterium': 'LD2-TRUNK', 'helium-3': 'LHE3-TRUNK', 'hydrogen': 'LH2-TRUNK'}
    mat['target'] = material('FPS_Target_Feed', COLOR['target'])
    farm_fl = []
    for ft in fs.feedthroughs(s):
        sp = ft['species']; parts = [cylinder_mesh(ft['a'], ft['b'], ft['radius'], 20)]
        parts += [cylinder_mesh(tuple(p[i]-ft['axis'][i]*ft['flange_m']/2 for i in range(3)), tuple(p[i]+ft['axis'][i]*ft['flange_m']/2 for i in range(3)), ft['flange_radius'], 20)
                  for p in ft['flanges']]
        obj = mesh(c, ft['name'], *merge(parts), mat[sp], kind='fps_feedthrough')
        _stamp_v1(obj, s, sp, f"hull feedthrough of {ft['trunk']}: jacketed sleeve with a bellows for the cold line's contraction, flanged inside and outside the aft hull skin",
                  'FPS-FT-'+ft['name'].split('_', 2)[2], 'ESTABLISHED', 'sleeve thermal break and the hull doubler', pipe_class=cls[sp])
        obj['trunk'] = ft['trunk']
        obj = line(c, ft['name']+'_Line', ft['bridge'], ft['line_radius'], mat[sp], kind='fps_feedthrough')
        _stamp_v1(obj, s, sp, f"process line through the feedthrough: joins {ft['trunk']}_Ext to {ft['trunk']}", 'FPS-FT-'+ft['name'].split('_', 2)[2]+'-L', 'ESTABLISHED', pipe_class=cls[sp])
    for ti in fs.tank_inlets(s):
        sp = ti['species']; tk = ti['tank']
        obj = line(c, ti['name'], ti['nozzle'], ti['radius'], mat[sp], kind='fps_tank_inlet')
        _stamp_v1(obj, s, sp, f"fill nozzle of {tk}: from the tee where {' and '.join(ti['trunks'])} meet, axially into the forward cap", 'FPS-TI-'+tk[-2:], 'ESTABLISHED',
                  'nozzle reinforcement and the anti-vortex/PMD inlet inside the tank', pipe_class=cls[sp])
        obj['tank'] = tk
        v = ti['valve']; obj = mesh(c, ti['name']+'_Valve', *_oriented_box(v, (ti['valve_size'],)*3, *_axes(*v[1:])), mat[sp], kind='fps_valve')
        _stamp_v1(obj, s, sp, f'run-tank fill isolation valve on {tk} (closes the run tank off the farm, e.g. while it settles before a burn)', 'FPS-VL-TI-'+tk[-2:], 'ESTABLISHED')
        for ck in ti['checks']:
            obj = mesh(c, f"FPS_Check_Valve_{ck['tag']}", *_oriented_box(ck['at'], (ti['check_size'],)*3, *_axes(*ck['at'][1:])), mat[sp], kind='fps_valve')
            _stamp_v1(obj, s, sp, f"check valve on {ck['trunk']}: either trunk fills {tk}, neither back-feeds the other", 'FPS-VL-CK-'+ck['tag'], 'ESTABLISHED')
        farm_fl += _flanges(ti['nozzle'], ti['radius'], fl)
    x = fs.h2_crossover(s)
    obj = line(c, x['name'], x['points'], x['radius'], mat['hydrogen'], kind='fps_feed_line')
    _stamp_v1(obj, s, 'hydrogen', f"H2 crossover on the farm deck: {x['mains'][0]} (inner vessels I2, I4) to {x['mains'][1]}, from which both H2 trunks leave",
              'FPS-XO-H2', 'ESTABLISHED', pipe_class='LH2-TRUNK')
    y, z = x['valve'][1:]; ry, rt = _axes(y, z)
    obj = mesh(c, 'FPS_H2_Crossover_Valve', *_oriented_box(x['valve'], (x['valve_size'],)*3, ry, rt), mat['hydrogen'], kind='fps_valve')
    _stamp_v1(obj, s, 'hydrogen', 'crossover isolation valve (inner-ring vessels drain into the outer main through it)', 'FPS-VL-XO-H2', 'ESTABLISHED')
    farm_fl += _flanges(x['points'], x['radius'], fl)
    obj = mesh(c, 'FPS_Farm_Flanges', *merge(farm_fl), equip, kind='fps_flange')
    _stamp_v1(obj, s, 'none', f'{len(farm_fl)} bolted flanges and couplings on the farm crossover and the run-tank inlets', 'FPS-FL-FARM', 'ESTABLISHED')
    feeds = {t['engine']: t for t in fs.target_feeds(s)}
    for h in fs.h2_injection(s):
        j = h['engine']; pl = h['placement']; t = feeds[j]; eng_fl = []; inst = []; sup = []
        obj = line(c, t['name'], t['points'], t['radius'], mat['target'], kind='fps_target_feed')
        _stamp_v1(obj, s, 'target', f"N{j} target feed: finished D-3He targets in a cold helium carrier from the service panel's TARGET_FEED slot to the target magazine "
                  '(through the cartridge shell by design)', f'FPS-TF-N{j}', 'PLAUSIBLE', 'target carrier, rate and the panel coupling; magazine side engine-owned',
                  owner='ENGINE (candidate)', pipe_class='TARGET-FEED')
        eng_fl += _flanges([t['points'][0], t['points'][-1]], t['radius'], fl)
        obj = line(c, h['line_name'], h['line'], h['line_radius'], mat['hydrogen'], kind='fps_feed_line')
        _stamp_v1(obj, s, 'hydrogen', f"N{j} H2 injection line: inlet -> fast valve -> aft past the collar (clear of the service panel) -> manifold ring",
                  f'FPS-IJ-N{j}-L', 'PLAUSIBLE', 'line flexibility across the trunnion, thermal shielding near the shield', owner='ENGINE (candidate)', pipe_class='GH2-INJECT')
        X, Y, Z = h['axes']

        def ebox(at, size):
            vs, fc = _oriented_box((0, 0, 0), size, (0, 1, 0), (0, 0, 1))
            return [tuple(at[i]+p[0]*X[i]+p[1]*Y[i]+p[2]*Z[i] for i in range(3)) for p in vs], fc
        obj = mesh(c, h['valve_name'], *ebox(h['valve'], (h['valve_size'], h['valve_size']*1.4, h['valve_size'])), mat['hydrogen'], kind='fps_valve')
        _stamp_v1(obj, s, 'hydrogen', f'N{j} H2 injection control valve: isolation and mass-flow trim of the engine\'s hydrogen (fail-closed on a trip)',
                  f'FPS-VL-IJ-N{j}', 'ESTABLISHED', 'hardware selection', owner='ENGINE (candidate)')
        m = h['manifold']; vs, fc = hoop_mesh(m['x'], 0.0, 0.0, m['R'], m['tube'], 64, 8)
        obj = mesh(c, h['manifold_name'], [vc_to(pl, p) for p in vs], fc, mat['hydrogen'], kind='fps_injector')
        _stamp_v1(obj, s, 'hydrogen', f'N{j} H2 injection manifold ring in the shadow shield\'s shadow, between the collar and the tie rods', f'FPS-IJ-N{j}-M',
                  'PLAUSIBLE', 'distribution and plenum volume', owner='ENGINE (candidate)', pipe_class='GH2-INJECT')
        parts = [cylinder_mesh(a, b, h['port_radius'], 10) for p in h['ports'] for a, b in zip(p, p[1:])]
        parts += [ebox(v, (h['port_valve_m']*1.6, h['port_valve_m'], h['port_valve_m'])) for v in h['port_valves']]
        if fs.v11(s):     # V1.1: the shielding galleries (sleeves where each port crosses the collar and the shadow shield) belong to the ports
            g = next(g for g in fs.shield_galleries(s) if g['engine'] == j)
            parts += [cylinder_mesh(a, b, g['radius'], 12) for a, b in g['segments']]
        obj = mesh(c, h['ports_name'], *merge(parts), mat['hydrogen'], kind='fps_injector')
        _stamp_v1(obj, s, 'hydrogen', f"N{j} {len(h['ports'])} injector ports, each with its fast valve (opens for the gas puff ahead of a pulse, kHz class): aft from the manifold through "
                  'drilled galleries in the thrust collar, across to the shadow shield and dog-legged through it to the burn face (no straight line of sight from '
                  'the burn through a port), between the tie rods and the cage longerons', f'FPS-IJ-N{j}-P', 'SPECULATIVE',
                  'fast-valve rate and life at the pulse frequency, collar galleries, shield streaming, tip heating, the gas-puff coupling itself', owner='ENGINE (candidate)')
        obj['port_count'] = len(h['ports'])
        eng_fl += _flanges([h['line'][0], h['line'][-1]], h['line_radius'], fl)
        q = s['fuel_system']['feed']['sensor']
        for pts, r in ((t['points'], t['radius']), (h['line'], h['line_radius'])):
            a, b = pts[-3], pts[-2]; mid_ = tuple((a[i]+b[i])/2 for i in range(3)); u = _dir(a, b)
            inst.append(cylinder_mesh(tuple(mid_[i]-u[i]*q['length_m']/2 for i in range(3)), tuple(mid_[i]+u[i]*q['length_m']/2 for i in range(3)), r+q['extra_m'], 16))
        obj = mesh(c, f'FPS_N{j}_Instruments', *merge(inst), equip, kind='fps_sensor')
        _stamp_v1(obj, s, 'none', f'N{j} pressure, temperature and flow sleeves on the target feed and the H2 injection line', f'FPS-IN-N{j}-V1', 'ESTABLISHED',
                  owner='ENGINE (candidate)')
        obj = mesh(c, f'FPS_N{j}_Flanges', *merge(eng_fl), equip, kind='fps_flange')
        _stamp_v1(obj, s, 'none', f'N{j} flanged joints: the target feed at the panel and the magazine, the H2 line at the inlet and the manifold (engine removal breaks here)',
                  f'FPS-FL-N{j}', 'ESTABLISHED', owner='ENGINE (candidate)')


def _stamp_v11(obj, s, species, function, fps_id, confidence='PLAUSIBLE', open_='', owner='FPS', pipe_class=''):
    _stamp_v1(obj, s, species, function, fps_id, confidence, open_, owner, pipe_class)
    obj['fps_version'] = s['fuel_system']['v11']['version']; obj['fps_milestone'] = 'V1.1'
    return obj


def _ring_mesh(pts, r):
    return merge([cylinder_mesh(a, b, r, 6) for a, b in zip(pts, pts[1:])])


def build_v11(c, s, mat, equip, bracket):
    """FPS V1.1 blockouts (fuel_system V1.1 section): target fabrication in the cluster bay core and the transfer to the target trunk,
    cryogenic supports and thermal intercepts, PMDs in every tank, pump/regulator/conditioning detail. Merged per function so the
    exported node count stays small (play budget)."""
    tf = fs.target_fabrication(s)
    for e in tf['equipment']:
        sp = e['species']; m = mat.get(sp, equip) if e['name'].startswith('FPS_Fab_Receiver') else equip
        if e['shape'] == 'cyl':
            vs, fc = cylinder_mesh(e['a'], e['b'], e['radius'], 24)
        else:
            vs, fc = _oriented_box(e['at'], e['size'], (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
        obj = mesh(c, e['name'], vs, fc, m, kind='fps_fabrication')
        _stamp_v11(obj, s, sp, e['function'], 'FPS-FAB-'+e['name'].split('_', 2)[2].upper(), 'SPECULATIVE',
                   'target recipe, fill and layering process, throughput and power; the bay layout is PROTOTYPE', owner='FPS (cluster bay core)')
    links = [l for l in tf['lines'] if l['name'].startswith(('FPS_Fab_Link', 'FPS_Fab_Conveyor'))]
    obj = mesh(c, 'FPS_Fab_Links', *merge([cylinder_mesh(a, b, l['radius'], 10) for l in links for a, b in zip(l['points'], l['points'][1:])]), mat['target'], kind='fps_fabrication')
    _stamp_v11(obj, s, 'target', 'fabrication-line links: receivers to the blend unit, and the target conveyor blend -> fill -> inspection -> buffer magazine', 'FPS-FAB-LINKS', 'SPECULATIVE')
    for l in tf['lines']:
        if l in links:
            continue
        sp = l['species']; leg = l['name'].startswith('FPS_Bay_Target')
        obj = line(c, l['name'], l['points'], l['radius'], mat[sp], kind='fps_fabrication' if leg else 'fps_target_feed')
        _stamp_v11(obj, s, sp, (f"{fs.TAG[sp]} leg from the bay fore face (end of its feed line) radially in to its receiver dewar" if leg else
                               'cold-target transfer from the buffer magazine to the cluster target trunk (CL_Trunk_TARGET_FEED) on the bay aft face'),
                   'FPS-FAB-'+('LEG-'+fs.TAG[sp] if leg else 'XFER'), 'PLAUSIBLE', pipe_class='TARGET-FEED' if not leg else {'deuterium': 'LD2-TRUNK', 'helium-3': 'LHE3-TRUNK'}[sp])
    cs = fs.cryo_supports(s); ti = fs.thermal_intercepts(s)
    for pl in fs.vc.placements(s):
        j = pl['n']; parts = []
        for k in cs['clamps']:
            if k['engine'] == j:
                parts += [_ring_mesh(k['ring'], cs['ring_tube']), cylinder_mesh(k['strut'][0], k['strut'][1], cs['strut_radius'], 8)]
        rings = [r for r in ti['rings'] if r.get('engine') == j]
        parts += [_ring_mesh(fs._ring_pts(r['center'], r['axis'], r['R']), ti['tube']) for r in rings]
        obj = mesh(c, f'FPS_N{j}_Supports', *merge(parts), bracket, kind='fps_support')
        _stamp_v11(obj, s, 'none', f'N{j} cryogenic clamps (low-conductance G10 standoffs) holding the target feed to the cartridge shell, and thermal intercepts '
                   'on the target feed and the H2 injection line at the panel side', f'FPS-SS-N{j}', 'PLAUSIBLE', 'clamp spacing against the feed\'s vibration modes at the pulse rate',
                   owner='ENGINE (candidate)')
    rings = [r for r in ti['rings'] if r.get('engine') is None]
    obj = mesh(c, 'FPS_Thermal_Intercepts', *merge([_ring_mesh(fs._ring_pts(r['center'], r['axis'], r['R']), ti['tube']) for r in rings]), equip, kind='fps_intercept')
    _stamp_v11(obj, s, 'none', f"{len(rings)} thermal intercepts (cold-strap collars to the 20 K loop) where cryogenic lines cross a warm/cold boundary: the four feed lines at the "
               'shadow-shield sleeve, the hull feedthroughs\' interior ends and the D2/He-3 legs at the bay fore face', 'FPS-TI-V11', 'PLAUSIBLE', 'strap conductance and the heat-leak budget per crossing')
    pm = fs.pmds(s)
    for grp, sel in (('Run_Tanks', [p for p in pm if p['species'] is None]), ('Farm', [p for p in pm if p['species'] is not None])):
        parts = [_oriented_box(b['center'], b['size'], b['ur'], b['ut']) for p in sel for b in p['vanes']+p['sponge']]
        obj = mesh(c, f'FPS_PMD_{grp}', *merge(parts), bracket, kind='fps_pmd')
        _stamp_v11(obj, s, 'none', f"propellant management devices in {len(sel)} {'run tanks' if grp == 'Run_Tanks' else 'farm vessels'}: four gallery vanes along the barrel and a radial-plate sponge "
                   'at the aft outlet keep liquid at the outlet in coast (no settling thrust)', 'FPS-PMD-'+grp.upper(), 'ESTABLISHED',
                   'vane and sponge sizing against the transfer rate; screen-channel bubble point')
        obj['tanks'] = ','.join(p['tank'] for p in sel)
    for d in fs.equipment_detail(s):
        sp = d['species']; parts = [cylinder_mesh(q['a'], q['b'], q['radius'], 16) for q in d['cyl']]
        parts += [_oriented_box(q['center'], q['size'], q['ur'], q['ut']) for q in d['box']]
        obj = mesh(c, d['name'], *merge(parts), equip, kind='fps_conditioner')
        _stamp_v11(obj, s, sp, f"{d['line']} sub-blockouts: "+', '.join(sorted({q['what'] for q in d['cyl']+d['box']})), 'FPS-EQ-'+d['name'].split('_', 3)[3], 'PLAUSIBLE',
                   'hardware selection, mass and power')


def vc_to(pl, p):
    return fs.vc.to_ship(pl, p)
