"""EVA-003 / SERV-003 integrated forward district (S&E 43 EVA-059, 44 EVA3-004, 15!A129 SERV-003, 98!A96; docs/EVA.md "EVA-003"):
SP-11 / SP-12 / SP-13 and the SERV-002 service district on ONE overlay, screened in memory against the saved vehicle (nothing saved, no
generator reads this). NONCANON packaging study: no port, pressure wall, room volume, gas budget or mass is approved by it (EVA-059 E60).

The owner asks for one spatial allocation instead of two independent surveys that share X ~103.6-106.1 m (98!D96 "double booking
stationary volume"), with EVA access and protected rescue first when they compete (EVA-059 H60). Layouts:

- L0 as proposed: SP-12/13 (az 5-75 deg) and SERV-002 option A (workshop + cell at 60 deg, warm module at 240 deg) together: the
  double-booked volumes are measured;
- L1-A EVA first, service turned: SP-12/13 and SP-11 stay; the workshop and the sealed cell take the clear angle found by a scan with the
  EVA rooms as obstacles (trunk extension A), the SP-52 warm module its own clear angle (shortest straight feed to a candidate warm panel);
- L1-B the same with the external corridor B (the fallback).

Each element: vehicle clash (every stationary mesh and rotating sweep at the mechanical clearance, inside the hull), mutual overlap volume
(0.1 m sample grid), shell area and PROTOTYPE shell mass (SERV-002's 20 kg/m2, inside the 60 t service/cargo category, never the root
budget), the pressure topology (compartments, hatches, which side each seats from), egress in 0 g and under 1.5 g aft-down, the
trunk-branch shirt-sleeve access (the existing 0.90 m Crew_Connector_Airlock_EVA opened up in a disposable copy) and the people,
casualty and robot envelopes through each opening.

    /snap/bin/blender -b --python src/wayfarer/studies/eva3_district.py -- --out runs/<stamp>-eva3-district
"""
from pathlib import Path
import argparse
import json
import math
import sys
import bpy
from mathutils import Matrix, Vector
ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT/'src/wayfarer'), str(ROOT/'src/wayfarer/build'), str(ROOT/'src/wayfarer/studies'), str(ROOT/'src/wayfarer/validation')]
from spec import load
import crew_transfer as ct
import eva_suit as es
import human_entry as he
import hull_geometry
import layout
import storeroom_survey as sv
import serv002_district as sd

STEP = 0.10                       # overlap sample grid (m)
PHI_SCAN = range(0, 360, 10)
SUITED_SUPPORTED = 'supported_frame'


# ---------------------------------------------------------------------------------------------------------------------------------
# elements (vehicle frame): sector rooms, boxes (storeroom_survey.box), cylinders along a radial

def sector(name, x, az, r):
    return dict(name=name, kind='sector', x=tuple(x), az=tuple(az), r=tuple(r))


def cylinder(name, x, th_deg, r0, r1, radius):
    return dict(name=name, kind='cyl', x=x, th=math.radians(th_deg), a=(r0, r1), radius=radius)


def inside(e, p):
    x, y, z = p
    if e['kind'] == 'sector':
        r = math.hypot(y, z); az = math.degrees(math.atan2(z, y)) % 360
        return e['x'][0] <= x <= e['x'][1] and e['r'][0] <= r <= e['r'][1] and e['az'][0] <= az <= e['az'][1]
    if e['kind'] == 'box':
        b = e['box']; c, s = math.cos(b['phi']), math.sin(b['phi']); u = y*c+z*s; t = -y*s+z*c
        return b['x'][0] <= x <= b['x'][1] and b['u'][0] <= u <= b['u'][1] and b['t'][0] <= t <= b['t'][1]
    c, s = math.cos(e['th']), math.sin(e['th']); a = y*c+z*s; q = -y*s+z*c
    return e['a'][0] <= a <= e['a'][1] and math.hypot(x-e['x'], q) <= e['radius']


def samples(e):
    """Grid points inside an element (its bounding box, filtered)."""
    if e['kind'] == 'sector':
        R = e['r'][1]; lo = (e['x'][0], -R, -R); hi = (e['x'][1], R, R)
    elif e['kind'] == 'box':
        cs = e['box']['corners']; lo = tuple(min(v[i] for v in cs) for i in range(3)); hi = tuple(max(v[i] for v in cs) for i in range(3))
    else:
        R = e['a'][1]+e['radius']; lo = (e['x']-e['radius'], -R, -R); hi = (e['x']+e['radius'], R, R)
    n = [max(1, int((hi[i]-lo[i])/STEP)) for i in range(3)]; out = []
    for i in range(n[0]):
        for j in range(n[1]):
            for k in range(n[2]):
                p = (lo[0]+(i+.5)*STEP, lo[1]+(j+.5)*STEP, lo[2]+(k+.5)*STEP)
                if inside(e, p):
                    out.append(p)
    return out


def overlaps(elements, allowed=()):
    """Shared volume (m3) of every pair, except the pairs a layout means to nest (the chamber rises through SP-12, the branch mouth
    opens into its floor)."""
    pts = {e['name']: samples(e) for e in elements}; out = {}
    for i, a in enumerate(elements):
        for b in elements[i+1:]:
            if {a['name'], b['name']} in [set(x) for x in allowed]:
                continue
            v = sum(1 for p in pts[a['name']] if inside(b, p))*STEP**3
            if v > 0:
                out[f"{a['name']} x {b['name']}"] = round(v, 2)
    return out, {k: round(len(v)*STEP**3, 1) for k, v in pts.items()}


def extent(e):
    """X, azimuth (deg) and radius extents of an element, for the X-azimuth map."""
    if e['kind'] == 'sector':
        return dict(name=e['name'], x=list(e['x']), az=list(e['az']), r=list(e['r']))
    if e['kind'] == 'box':
        cs = e['box']['corners']; az = [math.degrees(math.atan2(v.z, v.y)) % 360 for v in cs]; c = math.degrees(e['box']['phi']) % 360
        az = [c+((a-c+180) % 360-180) for a in az]; rr = [math.hypot(v.y, v.z) for v in cs]
        return dict(name=e['name'], x=[round(min(v.x for v in cs), 3), round(max(v.x for v in cs), 3)], az=[round(min(az), 1), round(max(az), 1)],
                    r=[round(e['box']['u'][0], 3), round(max(rr), 3)])
    half = math.degrees(math.asin(min(1.0, e['radius']/max(e['a'][0], e['radius'])))); c = math.degrees(e['th'])
    return dict(name=e['name'], x=[round(e['x']-e['radius'], 3), round(e['x']+e['radius'], 3)], az=[round(c-half, 1), round(c+half, 1)], r=list(e['a']))


def svg(result, path):
    """The X-azimuth development of L0 and L1-A: each element as its X and azimuth extent (radius in the label), the double-booked pairs
    of L0 named. A diagram for the owner, not geometry."""
    cols = dict(SP12='#4aa3df', SP13='#6c7fe0', SP11_chamber='#e8c547', SP12_branch='#dddddd', workshop='#46c07a', cell='#e8574a',
                warm_SP52='#f39c27', passage_0='#9fd89f', passage_1='#9fd89f')
    W, H, m = 760, 560, 60; x0, x1 = 99.5, 109.0
    X = lambda x: m+(x-x0)/(x1-x0)*(W-2*m); A = lambda a: 40+a/360*(H-80)
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{2*W}" height="{H+80}" font-family="sans-serif" font-size="11">',
           '<rect width="100%" height="100%" fill="#1b1e24"/>']
    for k, (lay, title) in enumerate((('L0', 'L0 as proposed: SP-12/13 + SERV-002 A independently'), ('L1-A', 'L1-A EVA first: service district turned'))):
        L = result['layouts'].get(lay, {}); ox = k*W
        out.append(f'<text x="{ox+m}" y="22" fill="#eee" font-size="14">{title}  ({L.get("status", "")})</text>')
        for xv in range(100, 110):
            out.append(f'<line x1="{ox+X(xv)}" y1="40" x2="{ox+X(xv)}" y2="{H-40}" stroke="#333"/><text x="{ox+X(xv)-8}" y="{H-24}" fill="#aaa">{xv}</text>')
        for av in range(0, 361, 45):
            out.append(f'<line x1="{ox+m}" y1="{A(av)}" x2="{ox+W-m}" y2="{A(av)}" stroke="#333"/><text x="{ox+16}" y="{A(av)+4}" fill="#aaa">{av}°</text>')
        out.append(f'<text x="{ox+W/2-40}" y="{H-6}" fill="#aaa">ship X (m)</text>')
        for e in L.get('map', []):
            a0, a1 = e['az']
            for lo, hi in ((a0, a1),) if 0 <= a0 and a1 <= 360 else ((a0 % 360, 360), (0, a1 % 360)):
                out.append(f'<rect x="{ox+X(e["x"][0])}" y="{A(lo)}" width="{X(e["x"][1])-X(e["x"][0])}" height="{A(hi)-A(lo)}" '
                           f'fill="{cols.get(e["name"], "#999")}" fill-opacity="0.55" stroke="{cols.get(e["name"], "#999")}"/>')
            if e['name'].startswith('passage'):
                continue
            ty = {'SP11_chamber': A(a0)+14, 'SP12_branch': A(a1)-6, 'cell': A(a1)+12}.get(e['name'], A((a0+a1)/2)+4)
            out.append(f'<text x="{ox+X(e["x"][0])+3}" y="{ty}" fill="#fff">{e["name"]} r {e["r"][0]:.2f}–{e["r"][1]:.2f}</text>')
        y = H+12
        for pair, v in (L.get('double_booked_m3') or {}).items():
            out.append(f'<text x="{ox+m}" y="{y}" fill="#ff8a80">double-booked: {pair} {v} m³</text>'); y += 14
    out.append('</svg>'); Path(path).write_text('\n'.join(out)+'\n')


def box_el(name, b):
    return dict(name=name, kind='box', box=b)


# ---------------------------------------------------------------------------------------------------------------------------------
# vehicle screen of a sector / cylinder: as boxes covering it (each 10 deg slice of a sector; a cylinder by its bounding box)

def as_boxes(e):
    if e['kind'] == 'box':
        return [e['box']]
    if e['kind'] == 'cyl':
        return [sv.box(e['x']-e['radius'], e['x']+e['radius'], e['th'], e['a'][0], e['a'][1], e['radius'])]
    out = []; a0, a1 = e['az']; n = max(1, int(math.ceil((a1-a0)/10.0)))
    for k in range(n):
        lo = a0+(a1-a0)*k/n; hi = a0+(a1-a0)*(k+1)/n; ph = math.radians((lo+hi)/2); half = math.radians((hi-lo)/2)
        out.append(sv.box(e['x'][0], e['x'][1], ph, e['r'][0]*math.cos(half), e['r'][1], e['r'][1]*math.sin(half)))
    return out


def screen(s, obs, e, ignore=()):
    c = s['prototype']['mechanical_clearance_m']; hits = set(); inside_hull = True
    for b in as_boxes(e):
        g = sv.box(b['x'][0], b['x'][1], b['phi'], b['u'][0], b['u'][1], b['t'][1], c)
        hits |= obs.hits(g, ignore=ignore); inside_hull &= sv.inside_hull(s, g)
    return dict(hits=sorted(hits), inside_hull=inside_hull)


def shell_area(e):
    if e['kind'] == 'sector':
        (x0, x1), (a0, a1), (r0, r1) = e['x'], e['az'], e['r']; th = math.radians(a1-a0); L = x1-x0
        return L*th*(r0+r1)+2*L*(r1-r0)+2*th*(r1*r1-r0*r0)/2
    if e['kind'] == 'box':
        b = e['box']; dx, du, dt = b['x'][1]-b['x'][0], b['u'][1]-b['u'][0], b['t'][1]-b['t'][0]; return 2*(dx*du+dx*dt+du*dt)
    L = e['a'][1]-e['a'][0]; return 2*math.pi*e['radius']*L+2*math.pi*e['radius']**2


# ---------------------------------------------------------------------------------------------------------------------------------

def eva_elements(s, data, lead):
    """SP-12, SP-13, the SP-11 lead chamber (from eva_sp11), the branch neck (Crew_Connector_Airlock_EVA, opened as a shirt-sleeve
    passage) and the parallel plug's parking pocket (the lead's chosen direction)."""
    ch = lead['chamber']; fit = lead['fitting']; w = fit['wall_m']
    br = next(q for q in ct.stationary(s) if q['name'] == 'Crew_Connector_Airlock_EVA')
    out = [sector('SP12', data['sp12']['x_m'], data['sp12']['az_deg'], data['sp12']['r_m']),
           sector('SP13', data['sp13']['x_m'], data['sp13']['az_deg'], data['sp13']['r_m']),
           cylinder('SP11_chamber', fit['x'], fit['theta_deg'], ch['inner_bulkhead_a_m'], ch['outer_bulkhead_a_m'], ch['clear_radius_m']+w),
           cylinder('SP12_branch', fit['x'], fit['theta_deg'], math.hypot(*br['points'][0][1:]), data['sp12']['r_m'][0], br['radius']+w)]
    return out, br


WARM_X0 = (104.0, 106.3)          # warm module aft face: SERV-002's station, or forward of the workshop (clear of the shield column at 108.5 m)


def serv_elements(s, obs, phi, option, warm_phi=None, warm_x0=None):
    fn = sd.option_a if option == 'A' else sd.option_b
    o, R, extra, ext = fn(s, obs, phi)
    if warm_phi is not None:
        w = s['human_entry']['chamber_wall_m']; M = R['warm']; x0 = M['x'][0] if warm_x0 is None else warm_x0
        d = layout.spine_radius_at(s, x0)+s['prototype']['mechanical_clearance_m']
        R['warm'] = sd.envelope(x0, x0+sd.WARM[2]+2*w, warm_phi, d, d+sd.WARM[1]+2*w, sd.WARM[0]/2+w)
    els = [box_el('workshop', R['workshop']), box_el('cell', R['cell']), box_el('warm_SP52', R['warm'])]
    els += [box_el(f'passage_{i}', b) for i, b in enumerate(extra)]
    if ext:
        els.append(dict(name='trunk_extension', kind='cyl', x=None, ext=ext))
    return o, R, els, ext


def ext_inside(ext, p):
    return ext['x'][0] <= p[0] <= ext['x'][1] and math.hypot(p[1], p[2]) <= ext['radius']


def clean(s, obs, els, eva):
    """Vehicle screen of the service elements and their overlap with the EVA elements."""
    res = {}
    for e in els:
        if e['name'] == 'trunk_extension':
            continue
        ign = ('Structural_Spine', 'Crew_Trunk') if e['name'].startswith('passage') else ()
        sc = screen(s, obs, e, ign); ov = []
        pts = samples(e)
        for x in eva:
            v = sum(1 for p in pts if inside(x, p))*STEP**3
            if v > 0:
                ov.append((x['name'], round(v, 2)))
        res[e['name']] = dict(**sc, eva_overlap=ov)
    ok = all(not r['hits'] and r['inside_hull'] and not r['eva_overlap'] for r in res.values())
    return ok, res


def main(out):
    s = load(ROOT)[0]; out.mkdir(parents=True, exist_ok=True); data = es.load(ROOT)
    sp = json.loads((ROOT/'references/p1_eva_sp11.json').read_text()); lead = next(r for r in sp['rows'] if abs(r['aperture_m']-data['sp11_eva3']['lead_m']) < 1e-9)
    env = json.loads((ROOT/'references/p1_eva_envelopes.json').read_text())
    bpy.ops.wm.open_mainfile(filepath=str(ROOT/'assets/wayfarer'/(s['vehicle']['asset']+'.blend'))); bpy.context.scene.frame_set(1); obs = sv.Obstacles()
    eva, br = eva_elements(s, data, lead); nest = [('SP12', 'SP11_chamber'), ('SP12', 'SP12_branch'), ('SP11_chamber', 'SP12_branch'), ('passage_0', 'passage_1')]
    result = dict(study='EVA-003 / SERV-003 integrated forward district (NONCANON packaging study)', step_m=STEP, layouts={})
    # EVA elements in the vehicle
    result['eva_elements'] = {e['name']: dict(**screen(s, obs, e, ('Structural_Spine', 'Crew_Trunk', 'Airlock_EVA', 'Crew_Connector_Airlock_EVA')),
                                             shell_m2=round(shell_area(e), 1)) for e in eva if e['name'] != 'SP11_chamber'}
    result['eva_elements']['SP11_chamber'] = dict(screen='exact mesh check in references/p1_eva_sp11_vehicle.json (a box round a cylinder is too coarse here)',
                                                  shell_m2=round(shell_area(next(e for e in eva if e['name'] == 'SP11_chamber')), 1))
    # L0: as proposed (SERV-002 option A at its chosen 60 deg, warm module opposite)
    o0, R0, els0, ext0 = serv_elements(s, obs, math.radians(60), 'A')
    ov0, vols0 = overlaps(eva+[e for e in els0 if e['name'] != 'trunk_extension'], nest)
    result['layouts']['L0'] = dict(title='as proposed: SP-12/13 and SERV-002 A (workshop + cell 60 deg, warm 240 deg) independently', status='FAIL' if ov0 else 'PASS',
                                   double_booked_m3=ov0, volumes_m3=vols0, map=[extent(e) for e in eva+[e for e in els0 if e['name'] != 'trunk_extension']])
    # L1: EVA first; scan the service district around the spine with the EVA elements as obstacles
    for option in ('A', 'B'):
        found = []
        for deg in PHI_SCAN:
            o, R, els, ext = serv_elements(s, obs, math.radians(deg), option)
            core = [e for e in els if e['name'] in ('workshop', 'cell') or e['name'].startswith('passage')]
            ok, res = clean(s, obs, core, eva)
            runs = [o.get('port', {}).get('run'), o.get('trunk_port', {}).get('run'), o.get('corridor', {}).get('screen')]
            ok = ok and all(not r['hits'] for r in runs if r) and not o.get('trunk_port', {}).get('opening_conflicts')
            if ok:
                found.append((deg, o, R, els, ext, res))
        if not found:
            result['layouts'][f'L1-{option}'] = dict(status='FAIL', reason='no clear angle for the workshop and cell with the EVA rooms in place'); continue
        warm_ok = []
        for deg, o, R, els, ext, res in found:
            for wx in WARM_X0:
                for wd in PHI_SCAN:
                    _, R2, els2, _ = serv_elements(s, obs, math.radians(deg), option, math.radians(wd), wx)
                    wm = next(e for e in els2 if e['name'] == 'warm_SP52'); others = eva+[e for e in els2 if e['name'] in ('workshop', 'cell')]
                    ok, wres = clean(s, obs, [wm], others)
                    if ok:
                        warm_ok.append((sd.warm_feed(s, R2['warm'])['length_m'], deg, wd, wx, R2, els2, wres))
        if not warm_ok:
            result['layouts'][f'L1-{option}'] = dict(status='FAIL', reason='no clear angle for the SP-52 warm module', service_angles=[f[0] for f in found]); continue
        feed, deg, wd, wx, R, els, wres = min(warm_ok, key=lambda f: f[0])
        o, _, _, ext = serv_elements(s, obs, math.radians(deg), option, math.radians(wd), wx)
        allel = eva+[e for e in els if e['name'] != 'trunk_extension']; ov, vols = overlaps(allel, nest)
        _, res = clean(s, obs, [e for e in els if e['name'] != 'trunk_extension'], eva)
        shells = {e['name']: round(shell_area(e), 1) for e in allel}
        ext_m2 = 2*math.pi*ext['radius']*(ext['x'][1]-ext['x'][0]) if ext else 0.0
        if ext:
            shells['trunk_extension'] = round(ext_m2, 1)
        total = sum(shells.values())-shells.get('SP12_branch', 0.0)            # the branch neck exists already (hollowed, not new shell)
        result['layouts'][f'L1-{option}'] = dict(
            title=f'EVA first: SP-11/12/13 kept; workshop + cell at {deg} deg ({o["option"]}), SP-52 warm module at {wd} deg from X {wx} m',
            status='PASS' if not ov else 'CONFLICT', service_angles_deg=[f[0] for f in found], workshop_deg=deg, warm_deg=wd, warm_x0=wx,
            warm_options=sorted({(f[1], f[2], f[3]) for f in warm_ok}),
            warm_feed=sd.warm_feed(s, R['warm']), elements=res, double_booked_m3=ov, volumes_m3=vols, shell_m2=shells,
            new_shell_m2=round(total, 1), new_shell_mass_t=round(total*sd.SHELL_KG_M2/1e3, 2), access=o, map=[extent(e) for e in allel])
    result['sp13_second_egress'] = sp13_egress(s, obs, data, eva)
    result['ladder_extension'] = ladder_extension(s, result)
    result['topology'] = topology(s, data, lead, br, env, result)
    (out/'eva3_district.json').write_text(json.dumps(result, indent=1, default=str)+'\n')
    (ROOT/'references/p1_eva_district.json').write_text(json.dumps(result, indent=1, default=str)+'\n'); svg(result, ROOT/'references/EVA3_DISTRICT_MAP.svg')
    print('WF_EVA3_DISTRICT', json.dumps({k: (v['status'], v.get('double_booked_m3'), v.get('workshop_deg'), v.get('warm_deg')) for k, v in result['layouts'].items()}), flush=True)
    render(s, eva, result, out, obs)
    print('WF_EVA3_DISTRICT done', out, flush=True)


def sp13_egress(s, obs, data, eva):
    """SP-13's second way out (L1 gives it only the door to SP-12): the A trunk extension carried on to the shield column side of SP-13
    and a 0.90 m radial port from it up into SP-13's floor. Tried at SP-13's mid station across its azimuths; reported, not chosen."""
    c = s['crew_transfer']; clr = s['prototype']['mechanical_clearance_m']; x = sum(data['sp13']['x_m'])/2; out = []
    ro = sd.PORT_CLEAR/2+c['passage_wall_m']; ext_end = x+ro+c['passage_wall_m']+.3
    for az in range(int(data['sp13']['az_deg'][0])+10, int(data['sp13']['az_deg'][1]), 10):
        port = cylinder('SP13_port', x, az, c['trunk_clear_radius_m'], data['sp13']['r_m'][0], ro)
        sc = screen(s, obs, port, ('Structural_Spine', 'Crew_Trunk')); ov = [e['name'] for e in eva if e['name'] not in ('SP13',) and any(inside(e, p_) for p_ in samples(port))]
        out.append(dict(az_deg=az, **sc, overlaps=ov))
    ok = [o for o in out if not o['hits'] and not o['overlaps']]
    return dict(station_x=round(x, 3), extension_to_x=round(ext_end, 3), extension_spine_clear=ext_end < 108.5-clr, candidates=out,
                status='CANDIDATE' if ok else 'BLOCKED', note='needs the spine bore hollow to X %.2f m (the bore contents and the structural cut are OPEN)' % ext_end)


def ladder_extension(s, result, x_top=104.9):
    """SERV-003's 5 m thrust-ladder extension (15!A129): the trunk ladder's stile lines (its 285 deg station, as built) checked from the
    present ladder top to the district passage's end against every trunk opening (human_entry.clear_spans), and the angles where a stile
    pair runs clear above the openings."""
    h = s['human_entry']; rl = s['crew_transfer']['trunk_clear_radius_m']-h['spoke_ladder_standoff_m']; phi = math.asin(h['spoke_ladder_width_m']/2/rl)
    L = he.trunk_ladder(s); th = math.radians(h['trunk_ladder_deg'])
    spans = [he.clear_spans(s, rl, th+sd*phi, L['floor'], x_top) for sd in (-1, 1)]
    gaps = []
    for sp in spans:
        for (a0, a1), (b0, b1) in zip(sp, sp[1:]):
            if b0 > L['top']-1e-6 or a1 > L['top']-.3:
                gaps.append((round(a1, 2), round(b0, 2)))
    clear = [d for d in range(0, 360, 5) if all(any(a <= 100.6 and b >= x_top for a, b in he.clear_spans(s, rl, math.radians(d)+sd*phi, 96.0, x_top)) for sd in (-1, 1))]
    blockers = [dict(name=n, x=round(x, 2), deg=round(math.degrees(t_) % 360, 1), r=r) for n, x, t_, r in he.openings(s) if L['top']-1 < x < x_top]
    return dict(ladder_deg=h['trunk_ladder_deg'], present_top_x=round(L['top'], 3), to_x=x_top, extension_m=round(x_top-L['top'], 2),
                stile_gaps=gaps, openings_on_the_way=blockers, clear_angles_above_dock_deg=clear,
                status='NOT CONTINUOUS',
                note='Crew_Connector_Dock_Primary (r 0.85 m, wider than the 0.80 m trunk) opens the whole trunk circumference at X ~98.4-100.4 m, '
                     'so no stile line runs past it at any angle: the extension needs a folding/removable section across the dock mouth (it '
                     'must not block the docking passage) or the trunk hoist; above it the 285 deg station runs clear to the district passage.')


def topology(s, data, lead, br, env, result):
    """Pressure topology, egress in 0 g and under 1.5 g aft-down, and what passes each opening (people, casualty, robot)."""
    import eva_access as ea
    V = env['variants']; tilts = data['airlock_study']['casualty_tilt_deg']; L = he.trunk_ladder(s); trunk = ct.stationary(s)[0]
    port = 2*br['radius']; robot = sd.ROBOT*math.sqrt(2)
    need = {f'{k}.{p}': ea.passage_circle(V[k][p], tilts if p != 'chamber' else (0.0,))['diameter_m'] for k in V for p in ('chamber', SUITED_SUPPORTED, 'casualty', 'unsuited')}
    sill = data['sp12']['x_m'][0]; branch_lo = br['points'][0][0]-br['radius']
    return dict(
        compartments=[
            dict(id='TRUNK', role='crew passage (existing)', isolation='existing'),
            dict(id='SP12', role='EVA prep / donning / buddy check (49 m3 gross)', hatches=['branch hatch to the trunk (seats from the trunk side, so a SP-12 leak holds it shut)',
                 'SP-11 inner hatch (parallel plug, seats from SP-12)', 'SP-12/13 door (seats from SP-12)']),
            dict(id='SP11', role='two-person airlock', hatches=['inner (parallel plug into SP-12)', 'outer (plug, seats from the chamber)'],
                 note='manual depress/equalization valves at both bulkheads; the cycle gas budget is a Sheets item'),
            dict(id='SP13', role='suit service: drying, charging, inspection, spares (26 m3 gross)', hatches=['door to SP-12 (only access in L1)']),
            dict(id='DISTRICT', role='service passage (A: trunk extension in the spine bore; B: corridor)', hatches=['district hatch at the trunk end (seats from the trunk side)']),
            dict(id='WORKSHOP', role='clean crewed workshop', hatches=['port hatch to the district passage']),
            dict(id='CELL', role='sealed hot/dirty cell, no crew entry while running', hatches=['pass-through and glove ports from the workshop; own vent to space']),
            dict(id='SP52', role='~450 K warm module, non-habitable', hatches=['own service hatch, robot first (crew only after cooldown)'])],
        openings=dict(
            branch_port=dict(clear_m=port, unsuited={k: round(port-v, 3) for k, v in need.items() if k.endswith('unsuited')},
                             supported_casualty={k: round(port-v, 3) for k, v in need.items() if k.endswith(SUITED_SUPPORTED)},
                             free_limp={k: round(port-v, 3) for k, v in need.items() if k.endswith('.casualty')}, robot_cube_diag=round(port-robot, 3),
                             note='the 0.90 m branch is the shirt-sleeve way in; a suited casualty on its frame goes this way to the trunk and the rescue routes'),
            sp11=dict(clear_m=lead['aperture_m'], note='see p1_eva_sp11.json')),
        egress=dict(
            zero_g=['SP-12 -> branch -> trunk (primary)', 'SP-12 -> SP-11 -> exterior (EVA only, not a cabin egress)', 'SP-13 -> SP-12 -> branch (single way out of SP-13 in L1: OPEN)'],
            thrust_1_5g=dict(trunk_ladder_top_x=round(L['top'], 3), branch_sill_x=round(branch_lo, 3), ladder_extension_to_branch_m=round(branch_lo-L['top'], 2),
                             sp12_floor_x=sill, sp13_floor_x=data['sp13']['x_m'][0], sp12_to_sp13_climb_m=round(data['sp13']['x_m'][0]-sill, 2),
                             trunk_end_x=round(trunk['points'][1][0], 3),
                             note='under 1.5 g aft-down X is vertical: the branch is a horizontal crawl 0.65 m above the SP-12 floor; SP-13 is a 4.2 m climb '
                                  'up an internal ladder through a door in SP-12\'s forward wall; EVA itself is drive-off (drive gate), so the chamber is not used under thrust')),
        service_connections=dict(
            SP12=['power and data', 'ventilation loop (own, isolatable)', 'O2 preparation interface (no flow budget)', 'suit umbilical/pressure-check panel',
                  'depress/repress lines to SP-11 (manual valves)', 'fire detection and suppression'],
            SP13=['power (battery charging)', 'water/coolant for suit loop service and drying air', 'spares stowage', 'ventilation (own)'],
            SP11=['vent line to space (depress), repress from SP-12 or the cabin loop', 'manual valves at both bulkheads', 'mechanical door interlock', 'lights, comms'],
            district='as SERV-002: workshop loop, cell exhaust to space, SP-52 warm loop to a candidate warm panel (routing OPEN, OD-022)'))


def render(s, eva, result, out, obs):
    """Overlay renders (Workbench): L0 (double booking, red) and the L1-A layout, side and section."""
    cols = dict(SP12=(.25, .65, .95, 1), SP13=(.35, .45, .95, 1), SP11_chamber=(.95, .85, .25, 1), SP12_branch=(.95, .95, .95, 1),
                workshop=(.25, .85, .45, 1), cell=(1.0, .2, .15, 1), warm_SP52=(1.0, .6, .05, 1), passage=(.6, .9, .6, 1))
    import bmesh
    def mk(e, name):
        me = bpy.data.meshes.new(name)
        if e['kind'] == 'box':
            me.from_pydata([tuple(v) for v in e['box']['corners']], [], sv.FACES)
        elif e['kind'] == 'sector':
            bm = bmesh.new(); vs = []
            n = 16; (x0, x1), (a0, a1), (r0, r1) = e['x'], e['az'], e['r']
            ring = lambda x, r: [bm.verts.new((x, r*math.cos(math.radians(a0+(a1-a0)*k/n)), r*math.sin(math.radians(a0+(a1-a0)*k/n)))) for k in range(n+1)]
            A = [ring(x0, r0), ring(x0, r1), ring(x1, r1), ring(x1, r0)]
            for i in range(4):
                P, Q = A[i], A[(i+1) % 4]
                for k in range(n):
                    bm.faces.new((P[k], P[k+1], Q[k+1], Q[k]))
            bm.to_mesh(me); bm.free()
        else:
            bm = bmesh.new(); ax = Vector((0, math.cos(e['th']), math.sin(e['th'])))
            bmesh.ops.create_cone(bm, cap_ends=True, segments=24, radius1=e['radius'], radius2=e['radius'], depth=e['a'][1]-e['a'][0])
            bm.to_mesh(me); bm.free()
        ob = bpy.data.objects.new(name, me); bpy.context.scene.collection.objects.link(ob)
        if e['kind'] == 'cyl':
            ax = Vector((0, math.cos(e['th']), math.sin(e['th']))); ob.matrix_world = Matrix.Translation(Vector((e['x'], 0, 0))+ax*(e['a'][0]+e['a'][1])/2) @ \
                ax.to_track_quat('Z', 'X').to_matrix().to_4x4()
        key = name.split('__')[0]; mat = bpy.data.materials.new(name); mat.diffuse_color = cols.get(key, cols['passage'] if key.startswith('passage') else (.7, .7, .7, 1))
        me.materials.append(mat); return ob
    keep = ('Structural_Spine', 'Crew_Trunk', 'Survival_Reserve_1', 'Survival_Reserve_2', 'Storeroom_Shell')
    hidden = [o for o in bpy.data.objects if not o.hide_render and o.name not in keep]
    for o in hidden:
        o.hide_render = True
    sc = bpy.context.scene; cam = bpy.data.objects.new('CAM_EVA3D', bpy.data.cameras.new('CAM_EVA3D')); sc.collection.objects.link(cam); sc.camera = cam
    sc.render.engine = 'BLENDER_WORKBENCH'; sc.display.shading.light = 'STUDIO'; sc.display.shading.color_type = 'MATERIAL'; sc.display.shading.show_cavity = True
    sc.render.resolution_x, sc.render.resolution_y = 1400, 900; paths = []
    for tag, lay in (('L0', 'L0'), ('L1A', 'L1-A')):
        L = result['layouts'].get(lay)
        if not L or (tag == 'L1A' and 'workshop_deg' not in L):
            continue
        if tag == 'L0':
            _, _, els, ext = serv_elements(s, obs, math.radians(60), 'A')
        else:
            _, _, els, ext = serv_elements(s, obs, math.radians(L['workshop_deg']), 'A', math.radians(L['warm_deg']), L['warm_x0'])
        made = [mk(e, f"{e['name']}__{tag}") for e in eva+[e for e in els if e['name'] != 'trunk_extension']]
        tv = Vector((0, -math.sin(math.radians(145)), math.cos(math.radians(145)))); uv = Vector((0, math.cos(math.radians(145)), math.sin(math.radians(145))))
        for view, loc, look, up, scale in (('side', Vector((104.0, 0, 0))+tv*30, None, uv, 13.0),
                                           ('section', Vector((112.0, 0, 0)), Vector((-1, 0, 0)), Vector((0, 0, 1)), 13.0)):
            look = look or (Vector((104.0, 0, 0))-loc).normalized(); z = -look.normalized(); x = up.cross(z).normalized(); y = z.cross(x)
            cam.location = loc; cam.rotation_euler = Matrix((x, y, z)).transposed().to_euler(); cam.data.type = 'ORTHO'; cam.data.ortho_scale = scale
            cam.data.clip_start = .1; cam.data.clip_end = 80.0 if view == 'side' else 11.5
            p = out/f'eva3_district_{tag}_{view}.png'; sc.render.filepath = str(p); bpy.ops.render.render(write_still=True); paths.append(p.name)
        for o in made:
            bpy.data.objects.remove(o)
    for o in hidden:
        o.hide_render = False
    return paths


if __name__ == '__main__':
    argv = sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
    ap = argparse.ArgumentParser(); ap.add_argument('--out', type=Path, required=True); a = ap.parse_args(argv)
    main(a.out if a.out.is_absolute() else ROOT/a.out)
