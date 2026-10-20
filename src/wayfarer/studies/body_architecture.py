"""BODY-001 whole-body internal architecture study (user brief 2026-10-18, Priority 1; B01 support): NONCANON, PROTOTYPE envelopes, nothing saved.

Function: decide how the stationary hull body between the aft equipment cluster and ring A's vestibule is allocated, so later modeling has
one reversible foundation. Fixed (source or built): 13 m body and the r 5.0 m outer cage with three keel rails at 30/150/270 deg and frames
every 4 m (07_PRIMARY_STRUCTURE, WORKING); the spine (r 0.875 m) and its 1.9 m forward core carrying the crew trunk; the shadow-shield slab,
engineering envelope, Brayton trains, main battery and pulse bank aft (X -81..-57.5 m); the measured free annulus r 1.025-4.721 m over
X -57.5..81.25 m (tank_bay_survey, references/p1_tank_bays.json); hydrogen feed lines in the cage-to-skin corridor; separated D-3He and
hydrogen tank families, no direct core-to-tank sight line (15!A69, 14 cryogenic_storage_stack). Unknown (OPEN, never chosen here): wet mass,
reaction mass, fusion fuel and its He-3 load, tank pressure, temperatures, boil-off, refrigeration power, tank and insulation mass, dose,
field keep-outs (15!A200 OWN-SCI: measure and propose, do not choose). Owner proxy for comparison: a 60 m storage allowance, 3,732 m3
envelope, "not CAD-verified" (30_PROPELLANT_VOLUME, 34_HARDWARE_PACKING); 15!A114: the free 139 m corridor is not qualified volume.
Design freedom (PROTOTYPE judgment, this file): tank pattern, module pitch, wall/insulation allowance, ullage, zone order, the service routes.

Three materially different packagings of the same bay:
  A  compact aft block: the owner's 60 m allowance as five 12 m modules of four cylinders; the forward 79 m stays equipment and reserve.
  B  full-length annulus: nine 12 m modules of one annular tank each plus two utility frames; maximum volume, no interior access.
  C  keel-lane tank train (recommended): the same stations as B, each module three lobe tanks between the keels, leaving a lane on every
     keel for supports, feed manifolds and crawler inspection, and the crew trunk continued aft in a 1.9 m spine core to the engineering bay.

    python3 src/wayfarer/studies/body_architecture.py                      # numbers + elevation/section SVGs (references/, runs/)
    /snap/bin/blender -b --python src/wayfarer/studies/body_architecture.py -- --out runs/<stamp>-body-arch   # + whitebox cutaway renders
    python3 src/wayfarer/studies/body_architecture.py --out runs/<stamp>-body-arch                           # then: captions (PIL)
"""
from pathlib import Path
import argparse
import json
import math
import sys
ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT/'src/wayfarer'), str(ROOT/'src/wayfarer/build')]

SURVEY = ROOT/'references/p1_tank_bays.json'
OUT_JSON = ROOT/'references/p1_body_architecture.json'

# REFERENCE PHYSICS (saturated liquids at their normal boiling points; scale only, no storage state is chosen).
DENSITY = dict(LH2=70.85, LD2=163.0, LHE3=58.9, SLUSH_H2_50=81.5, WATER=1000.0)
# Owner bounds (S&E 02, PROVISIONAL): propulsion inventory 300-600 t; 30_PROPELLANT_VOLUME study case 600 t with 274.9 t reacted D-3He.
INVENTORY_T = (300.0, 600.0)

# PROTOTYPE judgment (this study).
WALL = 0.15            # tank wall + aerogel/MLI allowance, envelope -> liquid, every face
ULLAGE = 0.05
MODULE = 12.0          # module pitch: three 4 m cage frame bays
GAP = 1.0              # support / inter-module valve gap inside each pitch
UTIL = 2.0             # utility frame (refrigeration cold heads, pumps, valves; owner tank-bay overhead 250 m3, 34)
END_ALLOW = 0.5        # per end: bulkhead knuckle of an annular or lobe tank
LANE_DEG = 20.0        # C: clear lane centred on each keel
KEELS = (30.0, 150.0, 270.0)
SPINE_TUNNEL_R = 0.95  # C: forward spine core radius (1.9 m, inside the WORKING 1.5-2.0 m envelope) continued aft
CLR = 0.15             # mechanical_clearance_m


def bay():
    b = max(json.loads(SURVEY.read_text())['bays'], key=lambda q: q['length_m'])
    return dict(x0=b['x0_m'], x1=b['x1_m'], r_in=b['narrowest']['r_in_m'], r_out=b['narrowest']['r_out_m'])


def cyl_volume(R, L):
    """Liquid volume of a cylinder tank of envelope radius R and length L with 2:1 ellipsoidal heads."""
    r = R-WALL; Ll = L-2*WALL; h = r/2
    return math.pi*r*r*(Ll-2*h)+2*(2/3)*math.pi*r*r*h


def sector_volume(ri, ro, span_deg, L):
    """Liquid volume of an annular sector tank (span_deg; 360 = full annulus) between envelope radii ri..ro."""
    a, b = ri+WALL, ro-WALL; L = L-2*END_ALLOW
    span = math.radians(span_deg) - (0 if span_deg >= 360 else 2*WALL/((a+b)/2))
    return span/2*(b*b-a*a)*L


def stations(x0, n, util_every):
    """Module [x0, x1) list from x0, a utility frame after every util_every modules (none after the last)."""
    out = []; x = x0
    for i in range(n):
        out.append((x, x+MODULE-GAP)); x += MODULE
        if util_every and (i+1) % util_every == 0 and i+1 < n:
            x += UTIL
    return out, x


def option(key, s=None):
    b = bay(); x0 = b['x0']
    if key == 'A':
        mods, x_end = stations(x0, 5, 0)
        R = 1.848                     # tank_bay_survey FOUR pattern at the narrowest section
        tanks = [dict(m=i, shape='cyl', R=R, deg=45+90*k, rc=b['r_in']+R) for i in range(len(mods)) for k in range(4)]
        per = cyl_volume(R, MODULE-GAP); r_in = b['r_in']
    else:
        mods, x_end = stations(x0, 9, 3)
        if key == 'B':
            tanks = [dict(m=i, shape='sector', span=360.0, mid=0.0) for i in range(len(mods))]
            r_in = b['r_in']; per = sector_volume(r_in, b['r_out'], 360.0, MODULE-GAP)
        else:
            r_in = SPINE_TUNNEL_R+CLR; span = 120-LANE_DEG
            tanks = [dict(m=i, shape='sector', span=span, mid=k+60) for i in range(len(mods)) for k in KEELS]
            per = sector_volume(r_in, b['r_out'], span, MODULE-GAP)
    vol = per*len(tanks)*(1-ULLAGE)
    xs = [(m[0]+m[1])/2 for m in mods]
    zones = zones_for(key, b, mods, x_end)
    return dict(key=key, modules=[dict(x0=round(a, 2), x1=round(c, 2)) for a, c in mods], tanks=tanks, r_in=r_in, r_out=b['r_out'],
                tank_count=len(tanks), per_tank_m3=round(per, 1), usable_m3=round(vol), tank_x0=round(mods[0][0], 2), tank_x1=round(mods[-1][1], 2),
                tank_length_m=round(mods[-1][1]-mods[0][0], 2), centroid_x=round(sum(xs)/len(xs), 2), zones=zones,
                lh2_t=round(vol*DENSITY['LH2']/1000), slush_t=round(vol*DENSITY['SLUSH_H2_50']/1000),
                he3_t_per_lobe=None if key != 'C' else round(per*(1-ULLAGE)*DENSITY['LHE3']/1000, 1))


def zones_for(key, b, mods, x_end):
    """Axial allocation of the bay beyond the tanks (X ranges, gross annulus volume, function, status)."""
    area = math.pi*(b['r_out']**2-b['r_in']**2)
    z = [dict(id='aft_equipment', x0=-72.0, x1=b['x0'], use='existing: engineering bay face, Brayton A/B, main battery, pulse bank, 4 schematic feed tanks',
              status='BUILT (PROTOTYPE)')]
    z.append(dict(id='tank_train', x0=mods[0][0], x1=mods[-1][1], use='hydrogen reaction mass (C: forward two modules = separated D and He-3 cryostats)',
                  status='PROTOTYPE envelope'))
    if key == 'A':
        z += [dict(id='equipment_bay', x0=x_end, x1=x_end+12, use='34 fore envelopes: power conversion 70, nav/radio/lasercom 40, RCS prop 45, coolant HX 75, trunks 50 m3'),
              dict(id='unallocated', x0=x_end+12, x1=70.0, use='reserve; no qualified use (15!A114)'),
              dict(id='workshop_fallback', x0=70.0, x1=b['x1'], use='SERV-002 aft fallback X 70-81.2 (forward X 100.4-108.9 preferred)')]
    else:
        z += [dict(id='equipment_bay', x0=x_end, x1=70.0, use='34 fore envelopes (280 m3) + tank-bay overhead not in the utility frames'),
              dict(id='workshop_fallback', x0=70.0, x1=b['x1'], use='SERV-002 aft fallback X 70-81.2 (forward X 100.4-108.9 preferred)')]
    for q in z:
        q['x0'], q['x1'] = round(q['x0'], 2), round(q['x1'], 2); q['gross_m3'] = round(area*(q['x1']-q['x0']))
        q.setdefault('status', 'PROTOTYPE')
    return z


def requirement():
    """What the owner's PROVISIONAL inventory bounds need as liquids (scale only; split and storage state OPEN)."""
    out = dict(per_100t_m3={k: round(1e5/v) for k, v in DENSITY.items()})
    out['inventory_all_LH2_m3'] = {f'{int(t)}t': round(t*1000/DENSITY['LH2']/(1-ULLAGE)) for t in INVENTORY_T}
    out['inventory_all_slush_m3'] = {f'{int(t)}t': round(t*1000/DENSITY['SLUSH_H2_50']/(1-ULLAGE)) for t in INVENTORY_T}
    return out


def assess(o, req):
    need = req['inventory_all_LH2_m3']
    fits = {k: o['usable_m3'] >= v for k, v in need.items()}
    return dict(fits_all_LH2=fits, share_of_600t_LH2=round(o['usable_m3']/need['600t'], 2))


QUALITATIVE = {
    'A': dict(service='tanks open to the cage on four sides; forward 79 m free for equipment and access; no aft crew route (OPEN)',
              thermal='short H2 feed (aft); tanks far from the radiator-root band only in their aft 60 m (same as all)',
              radiation='first module 23.5 m forward of the shadow-shield slab; He-3 placement OPEN',
              structure='propellant centroid aft (X -27.5): shortest load path to the thrust ring',
              reversibility='high: forward half untouched',
              conflicts='none with built assemblies; capacity below every owner inventory bound'),
    'B': dict(service='no interior access past the spine; inspection only from the cage-to-skin corridor or externally (DS-13 casing rail)',
              thermal='feed lines run 126 m in the corridor; one tank skin faces the hot-facing casing over the whole body',
              radiation='as A for the aft module; He-3 placement OPEN',
              structure='annular tanks carry pressure in a poor shape: heavy end bulkheads and inner walls (mass OPEN)',
              reversibility='low: fills the only axial path aft of the crew trunk; HR-001 and any internal route must cross it',
              conflicts='blocks an internal service route (aft corridor OPEN, 15!A114); SERV-002 aft fallback kept forward'),
    'C': dict(service='spine tunnel = continuous 0.80 m crew/robot route from the trunk to the engineering bay; three keel lanes reach every module',
              thermal='lobes stand off the keel rails; lanes carry feed manifolds and cold-head lines; cage-to-skin corridor reserved for a thermal barrier',
              radiation='H2 modules aft shield the forward fuel cryostats from core neutrons (He-3 absorbs thermal neutrons); dose OPEN',
              structure='lobes hang from the three keels at frame stations (the load path 07 already builds); multi-cell lobes need tie-rods (mass OPEN)',
              reversibility='high: module pattern and fuel/H2 split are per-module parameters; zones and stations stay',
              conflicts='spine radius 0.875 -> 0.95 m over the bay (inside the WORKING envelope); trunk aft hatch at X 81.3'),
}


def screen():
    req = requirement(); opts = {k: option(k) for k in 'ABC'}
    for k, o in opts.items():
        o.update(assess(o, req)); o['assessment'] = QUALITATIVE[k]
    return dict(study='BODY-001 whole-body internal architecture (NONCANON; PROTOTYPE envelopes; nothing saved)',
                bay=bay(), assumptions=dict(wall_insulation_m=WALL, ullage=ULLAGE, module_pitch_m=MODULE, gap_m=GAP, utility_frame_m=UTIL,
                                            lane_deg=LANE_DEG, density_kg_m3=DENSITY, status='PROTOTYPE / REFERENCE PHYSICS'),
                owner_proxy=dict(length_m=60, envelope_m3=3732.2, status='NOT CAD-verified (30, 34)'),
                requirement=req, options=opts, recommended='C')


# ---------------------------------------------------------------- SVG elevation and sections (pure)

COL = dict(tank='#7fb8e6', fuel='#a98ad8', equipment_bay='#e0a54a', unallocated='#d9d9d9', workshop_fallback='#7cc58a',
           aft_equipment='#9a9a9a', util='#f07c3a', spine='#555', tunnel='#ffffff', cage='#333')


def svg(res):
    W, H, X0, X1 = 1500, 760, -80.0, 90.0
    sx = lambda x: 60+(x-X0)/(X1-X0)*(W-120)
    g = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" font-family="sans-serif" font-size="12">',
         f'<rect width="{W}" height="{H}" fill="#fafafa"/>',
         '<text x="20" y="24" font-size="15">BODY-001 internal allocation: three packagings of the measured bay (half-section above the axis, r 0..6.5 m). '
         'PROTOTYPE envelopes, NONCANON; volumes are liquid at 5% ullage.</text>']
    for row, k in enumerate('ABC'):
        o = res['options'][k]; y0 = 70+row*220; sy = lambda r: y0+150-r*22
        g.append(f'<text x="20" y="{y0}" font-size="14" font-weight="bold">{k} - {dict(A="compact aft block (owner 60 m proxy)", B="full-length annulus", C="keel-lane tank train + spine tunnel (recommended)")[k]}: '
                 f'{o["usable_m3"]:,} m3 ~ {o["lh2_t"]} t LH2 ({o["share_of_600t_LH2"]:.0%} of 600 t), centroid X {o["centroid_x"]}</text>')
        g.append(f'<line x1="{sx(X0)}" y1="{sy(6.5)}" x2="{sx(X1)}" y2="{sy(6.5)}" stroke="#bbb"/>')
        g.append(f'<line x1="{sx(X0)}" y1="{sy(5.0)}" x2="{sx(81.35)}" y2="{sy(5.0)}" stroke="{COL["cage"]}" stroke-dasharray="6 3"/>')
        for z in o['zones']:
            if z['id'] == 'tank_train':
                continue
            g.append(f'<rect x="{sx(z["x0"])}" y="{sy(o["r_out"])}" width="{sx(z["x1"])-sx(z["x0"])}" height="{sy(o["r_in"])-sy(o["r_out"])}" '
                     f'fill="{COL.get(z["id"], "#ccc")}" opacity=".75"/>')
            g.append(f'<text x="{sx(z["x0"])+3}" y="{sy(o["r_out"])-4}" font-size="10">{z["id"].replace("_", " ")}</text>')
        for i, m in enumerate(o['modules']):
            fuel = k == 'C' and i >= len(o['modules'])-2
            g.append(f'<rect x="{sx(m["x0"])}" y="{sy(o["r_out"])}" width="{sx(m["x1"])-sx(m["x0"])}" height="{sy(o["r_in"])-sy(o["r_out"])}" '
                     f'fill="{COL["fuel" if fuel else "tank"]}" stroke="#2b5d85" rx="{10 if k == "A" else 3}"/>')
        for a, c in zip(o['modules'], o['modules'][1:]):
            if c['x0']-a['x1'] > GAP+.1:
                g.append(f'<rect x="{sx(a["x1"]+GAP/2)}" y="{sy(o["r_out"])}" width="{sx(c["x0"])-sx(a["x1"]+GAP/2)}" height="{sy(o["r_in"])-sy(o["r_out"])}" fill="{COL["util"]}"/>')
        rs = SPINE_TUNNEL_R if k == 'C' else .875
        g.append(f'<rect x="{sx(-72)}" y="{sy(rs)}" width="{sx(81.35)-sx(-72)}" height="{sy(0)-sy(rs)}" fill="{COL["tunnel" if k == "C" else "spine"]}" stroke="#555"/>')
        if k == 'C':
            g.append(f'<text x="{sx(0)}" y="{sy(.3)}" font-size="10">crew/robot tunnel in spine core (0.80 m clear), trunk -> engineering bay</text>')
        for x in range(-70, 90, 10):
            g.append(f'<text x="{sx(x)-8}" y="{sy(0)+14}" font-size="9" fill="#666">{x}</text>')
    g.append('</svg>')
    return '\n'.join(g)


def section_svg(res):
    """Cross-sections (looking aft) of one module per option, with the cage, keels and hull."""
    W, H, S = 1050, 400, 26
    g = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" font-family="sans-serif" font-size="12">', f'<rect width="{W}" height="{H}" fill="#fafafa"/>']
    for j, k in enumerate('ABC'):
        o = res['options'][k]; cx, cy = 175+j*350, 210
        P = lambda r, d: (cx+r*S*math.cos(math.radians(d)), cy-r*S*math.sin(math.radians(d)))
        g.append(f'<text x="{cx-150}" y="30" font-size="13" font-weight="bold">{k}: {o["tank_count"]//len(o["modules"])} tank(s) per module</text>')
        g.append(f'<circle cx="{cx}" cy="{cy}" r="{6.5*S}" fill="none" stroke="#bbb" stroke-width="3"/>')
        g.append(f'<circle cx="{cx}" cy="{cy}" r="{5.0*S}" fill="none" stroke="#333" stroke-dasharray="5 3"/>')
        for d in KEELS:
            x, y = P(5.0, d); g.append(f'<circle cx="{x}" cy="{y}" r="5" fill="#333"/>')
        for t in (q for q in o['tanks'] if q['m'] == 0):
            if t['shape'] == 'cyl':
                x, y = P(t['rc'], t['deg']); g.append(f'<circle cx="{x}" cy="{y}" r="{t["R"]*S}" fill="{COL["tank"]}" stroke="#2b5d85"/>')
            elif t['span'] >= 360:
                g.append(f'<circle cx="{cx}" cy="{cy}" r="{o["r_out"]*S}" fill="{COL["tank"]}" stroke="#2b5d85"/><circle cx="{cx}" cy="{cy}" r="{o["r_in"]*S}" fill="#fafafa" stroke="#2b5d85"/>')
            else:
                a0, a1 = t['mid']-t['span']/2, t['mid']+t['span']/2
                p0, p1, p2, p3 = P(o['r_out'], a0), P(o['r_out'], a1), P(o['r_in'], a1), P(o['r_in'], a0)
                g.append(f'<path d="M{p0[0]},{p0[1]} A{o["r_out"]*S},{o["r_out"]*S} 0 0 0 {p1[0]},{p1[1]} L{p2[0]},{p2[1]} '
                         f'A{o["r_in"]*S},{o["r_in"]*S} 0 0 1 {p3[0]},{p3[1]} Z" fill="{COL["tank"]}" stroke="#2b5d85"/>')
        rs = SPINE_TUNNEL_R if k == 'C' else .875
        g.append(f'<circle cx="{cx}" cy="{cy}" r="{rs*S}" fill="{"#fff" if k == "C" else "#555"}" stroke="#555"/>')
        if k == 'C':
            g.append(f'<circle cx="{cx}" cy="{cy}" r="{.8*S}" fill="none" stroke="#555" stroke-dasharray="2 2"/>')
            for d in KEELS:
                x, y = P(3.3, d); g.append(f'<text x="{x-14}" y="{y}" font-size="9">lane</text>')
        g.append(f'<text x="{cx-150}" y="{H-20}" font-size="11">{o["per_tank_m3"]} m3 liquid per tank</text>')
    g.append(f'<text x="20" y="{H-4}" font-size="10" fill="#555">Looking aft. Grey ring: hull r 6.5 m; dashed: cage r 5.0 m; dots: keel rails 30/150/270 deg.</text>')
    g.append('</svg>')
    return '\n'.join(g)


# ---------------------------------------------------------------- Blender whitebox (recommended option C) and cutaway renders

PALETTE = dict(h2=(.50, .72, .90, 1.0), fuel=(.66, .54, .85, 1.0), util=(.94, .49, .23, 1.0), equip=(.88, .65, .29, .55),
               shop=(.49, .77, .54, .45), tunnel=(.95, .95, .95, .35), strut=(.30, .30, .32, 1.0), barrier=(.85, .82, .55, .18))


def lobe_mesh(name, x0, x1, ri, ro, a0, a1, seg=10):
    import bpy
    vs = []; n = seg+1
    for x in (x0, x1):
        for r in (ri, ro):
            for i in range(n):
                a = math.radians(a0+(a1-a0)*i/seg); vs.append((x, r*math.cos(a), r*math.sin(a)))
    idx = lambda e, rr, i: e*2*n+rr*n+i
    f = []
    for i in range(seg):
        f += [(idx(0, 0, i), idx(0, 0, i+1), idx(1, 0, i+1), idx(1, 0, i)), (idx(0, 1, i), idx(1, 1, i), idx(1, 1, i+1), idx(0, 1, i+1)),
              (idx(0, 0, i), idx(0, 1, i), idx(0, 1, i+1), idx(0, 0, i+1)), (idx(1, 0, i), idx(1, 0, i+1), idx(1, 1, i+1), idx(1, 1, i))]
    if a1-a0 < 359:
        f += [(idx(0, 0, 0), idx(1, 0, 0), idx(1, 1, 0), idx(0, 1, 0)), (idx(0, 0, seg), idx(0, 1, seg), idx(1, 1, seg), idx(1, 0, seg))]
    me = bpy.data.meshes.new(name); me.from_pydata(vs, [], f); me.update()
    return bpy.data.objects.new(name, me)


def tube(name, x0, x1, r, seg=32):
    return lobe_mesh(name, x0, x1, r*.98, r, 0, 360, seg)


def apply(s, o):
    """Study parts (ART_BODY_*): lobes, utility frames, equipment and workshop-fallback zones, the spine tunnel, keel support struts."""
    import bpy
    from common import material
    mats = {k: material(f'ART_BODY_{k}', v[:3], alpha=v[3]) for k, v in PALETTE.items()}
    col = bpy.data.collections.new('ART_BODY_ARCH'); bpy.context.scene.collection.children.link(col)
    parts = []
    def add(ob, kind, role):
        col.objects.link(ob); ob.data.materials.append(mats[kind]); ob['geometry_status'] = 'PROTOTYPE'; ob['study'] = 'body_architecture'
        ob['option'] = o['key']; ob['role'] = role; parts.append(ob.name)
    nm = len(o['modules'])
    for t in o['tanks']:
        m = o['modules'][t['m']]; fuel = t['m'] >= nm-2
        add(lobe_mesh(f'ART_BODY_Tank_{t["m"]:02}_{int(t["mid"])}', m['x0'], m['x1'], o['r_in'], o['r_out'], t['mid']-t['span']/2, t['mid']+t['span']/2),
            'fuel' if fuel else 'h2', 'separated D / He-3 cryostat (split OPEN)' if fuel else 'hydrogen reaction-mass lobe')
        for d in (t['mid']-t['span']/2, t['mid']+t['span']/2):          # support struts from the lobe flank to the keel rail at each frame
            for x in (m['x0']+1.5, m['x1']-1.5):
                a = math.radians(d); b = math.radians(min(KEELS, key=lambda k: abs((k-d+180) % 360-180)))
                cu = bpy.data.curves.new('ART_BODY_Strut', 'CURVE'); cu.dimensions = '3D'; cu.bevel_depth = .06
                sp = cu.splines.new('POLY'); sp.points.add(1)
                sp.points[0].co = (x, 3.6*math.cos(a), 3.6*math.sin(a), 1); sp.points[1].co = (x, 4.85*math.cos(b), 4.85*math.sin(b), 1)
                add(bpy.data.objects.new('ART_BODY_Strut', cu), 'strut', 'lobe support to keel (PROTOTYPE)')
    for a, c in zip(o['modules'], o['modules'][1:]):
        if c['x0']-a['x1'] > GAP+.1:
            add(lobe_mesh(f'ART_BODY_Utility_{a["x1"]:.0f}', a['x1']+GAP/2, c['x0']-GAP/2, o['r_in'], o['r_out'], 0, 360, 36), 'util',
                'utility frame: refrigeration cold heads, pumps, valves (tank-bay overhead)')
    for z in o['zones']:
        if z['id'] in ('equipment_bay', 'workshop_fallback'):
            add(lobe_mesh(f'ART_BODY_{z["id"]}', z['x0'], z['x1']-.2, o['r_in'], o['r_out'], 0, 360, 36), 'equip' if z['id'] == 'equipment_bay' else 'shop', z['use'])
    add(tube('ART_BODY_Spine_Tunnel', -72.0, 81.35, SPINE_TUNNEL_R), 'tunnel', 'trunk continued aft in a 1.9 m spine core (0.80 m clear)')
    return parts


HIDE = ('Tank_Volume', 'Engineering_Envelope', 'Body_Envelope', 'FieldEnvelope', 'Magnetic_Flow', 'PLASMA', 'OPTICAL_BEAM', 'Human_', 'Preview_')
HIDE_KINDS = ('scale_reference', 'entry_camera', 'sim_proxy', 'magnetic_field', 'plasma', 'optical_beam', 'hull_envelope')
CAPTION = ('WAYFARER 001 / BODY-001 option C: keel-lane tank train + spine tunnel / {view} | STUDY, NONCANON: PROTOTYPE envelopes, hull hidden',
           'blue: H2 reaction-mass lobes | violet: separated D / He-3 cryostats (split OPEN) | orange: utility frames | amber: equipment bay | '
           'green: SERV-002 aft workshop fallback | white: spine tunnel', 'inventory, tank mass, pressure, boil-off, dose and keep-outs OPEN (15!A200)')


def caption(path, view):
    from PIL import Image, ImageDraw
    im = Image.open(path).convert('RGB'); d = ImageDraw.Draw(im); h = 24
    d.rectangle((0, im.height-3*h-14, im.width, im.height), fill=(12, 14, 18))
    for i, line in enumerate(CAPTION):
        d.text((16, im.height-3*h-6+i*h), line.format(view=view.upper()), fill=(235, 235, 235) if i == 0 else (190, 190, 190))
    im.save(path)


def renders(s, o, out, size):
    """The saved COAST vehicle with the hull assembly and display layers hidden in memory (nothing saved), plus the study parts."""
    import bpy
    from mathutils import Vector, Matrix
    bpy.ops.wm.open_mainfile(filepath=str(ROOT/'assets/wayfarer'/(s['vehicle']['asset']+'.blend')))
    sc = bpy.context.scene
    for ob in bpy.data.objects:
        if ob.name == 'Assembly_HULL' or ob.name.startswith(HIDE) or ob.get('kind', '') in HIDE_KINDS:
            ob.hide_render = ob.hide_viewport = True
    apply(s, o)
    sc.render.engine = 'BLENDER_WORKBENCH'; sh = sc.display.shading; sh.light = 'STUDIO'; sh.color_type = 'MATERIAL'; sh.show_cavity = True
    sh.show_backface_culling = False
    sc.world = sc.world or bpy.data.worlds.new('ART_BODY_World'); sc.world.color = (.055, .075, .10)
    sc.render.resolution_x, sc.render.resolution_y = size, round(size*9/16); sc.render.image_settings.file_format = 'PNG'
    cam = bpy.data.objects.new('ART_BODY_Camera', bpy.data.cameras.new('ART_BODY_Camera')); sc.collection.objects.link(cam); sc.camera = cam
    cam.data.clip_end = 3000
    P = lambda x, r, deg: Vector((x, r*math.cos(math.radians(deg)), r*math.sin(math.radians(deg))))
    views = {   # camera, target, up, lens or None, ortho scale, clip start; from +Z the body is open between the 30 and 150 deg blades
        'whole_cutaway': (Vector((10, -95, 175)), P(5, 0, 0), (0, 1, 0), 30, None, .5),
        'side_elevation': (P(5, 400, 90), P(5, 0, 90), (0, -1, 0), None, 175, .5),
        'module_close': (P(14, 26, 55), P(-8, 1.5, 36), (1, 0, 0), 32, None, .3),
        'section_aft': (P(26, 0, 0), P(-50, 0, 0), (0, 0, 1), None, 15, 1.8),
    }
    paths = []
    for name, (loc, look, up, lens, ortho, clip) in views.items():
        z = (loc-look).normalized(); x = Vector(up).cross(z).normalized(); y = z.cross(x)
        cam.location = loc; cam.rotation_euler = Matrix((x, y, z)).transposed().to_euler(); cam.data.clip_start = clip
        cam.data.type = 'ORTHO' if ortho else 'PERSP'
        if ortho:
            cam.data.ortho_scale = ortho
        else:
            cam.data.lens = lens
        p = out/f'body_{name}.png'; sc.render.filepath = str(p); bpy.ops.render.render(write_still=True); paths.append(p.name)
        print('WF_BODY', name, flush=True)
    return paths


def _blender():
    try:
        import bpy  # noqa: F401
        return True
    except ImportError:
        return False


def main(out=None, size=1600):
    from spec import load
    s = load(ROOT)[0]; res = screen()
    if out is not None:
        out.mkdir(parents=True, exist_ok=True)
        (out/'body_elevation.svg').write_text(svg(res)); (out/'body_sections.svg').write_text(section_svg(res))
        if 'bpy' in sys.modules or _blender():
            res['renders'] = renders(s, res['options']['C'], out, size)
        else:                                       # system Python: caption the renders a Blender run left (PIL is not in Blender)
            for q in sorted(out.glob('body_*.png')):
                caption(q, q.stem[5:])
        (out/'body_architecture.json').write_text(json.dumps(res, indent=1)+'\n')
    OUT_JSON.write_text(json.dumps({k: v for k, v in res.items() if k != 'renders'}, indent=1)+'\n')
    for k, o in res['options'].items():
        print(k, o['tank_count'], 'tanks', o['usable_m3'], 'm3', o['lh2_t'], 't LH2', 'x', o['tank_x0'], o['tank_x1'], 'centroid', o['centroid_x'], o['fits_all_LH2'])
    print(json.dumps(res['requirement']))
    return res


if __name__ == '__main__':
    argv = sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else sys.argv[1:]
    ap = argparse.ArgumentParser(); ap.add_argument('--out', type=Path); ap.add_argument('--size', type=int, default=1600)
    a = ap.parse_args(argv)
    main(None if a.out is None else (a.out if a.out.is_absolute() else ROOT/a.out), a.size)
