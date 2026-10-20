"""Owner 2026-10-17 (S&E 15!A198 OWN-RES-RA, r2-A): ring A port and spin-port turn as a reversible L2 WHITEBOX (NONCANON PROTOTYPE, disposable).

Ring A is not a passing rescue comparator: on the worst-case method (ringb_unified.survey, RINGB-006) every ring A leg fails, A1 -0.103 m
unsuited / -0.171 m suited, the spin route -0.140 / -0.455 m, the locked annulus legs -0.065 / -0.243 m (references/p1_ringb_insector_care.json).
This study measures the same eight routes with the same sweep (injury classes A/C/K/S, body x1.00/x1.08, doors 1.00/0.90, seeds, six pose
families with wobbles, two rescuers) in disposable workspaces whose ring A vestibule is changed with the existing study knobs of
crew_transfer.vestibule ([human_entry.study], never set in the spec):
  port_clear_radius_m {"1"}   ring A's spine port clear radius (built 0.80 m = the 1.6 m docking passage; ring A has no hub window limit)
  chamber_depth_extra_m {"1"} extra radial depth of ring A's annular transit chamber (built: suited envelope + handrails)
Function: a casualty carrier with two rescuers from a ring A sector through the hatch, the rotary chamber and the spine port into the trunk.
Fixed: the 1.6 m trunk, the spine core, the trunk arrest rail, hub/rotor structure and every other built mesh. Unknown: loads, seals, masses,
ratings. Design freedom (PROTOTYPE, VARIANTS below): port size and chamber depth; second pass: the trunk ladder and arrest rail at the port
(joggled or cut, in-memory scene edits) and a couch-side transfer space at A2 (Lab_Bench relocated, litter alongside the couch).
A geometric PASS is not a rescue release (15!A198 H).

    python3 src/wayfarer/studies/ringa_port_whitebox.py build              # workspaces under RUN/<variant>/work (full builds)
    python3 src/wayfarer/studies/ringa_port_whitebox.py run --workers 14   # 8 routes x 4 carriers per variant + a geometry job, Blender each (pass-2 variants reuse the pass-1 builds)
    python3 src/wayfarer/studies/ringa_port_whitebox.py collect            # references/p1_ringa_whitebox.json, RINGA_PORT_WHITEBOX_2026-10-17.md
"""
from pathlib import Path
import argparse
import json
import re
import shutil
import subprocess
import sys
import time
ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT/'src/wayfarer'), str(ROOT/'src/wayfarer/build'), str(ROOT/'src/wayfarer/studies'), str(ROOT/'tools')]
import ringb_unified as ru
BLENDER = ru.BLENDER
RUN = ROOT/'runs/20261017T0900Z-ringa-whitebox'
OUT_JSON = ROOT/'references/p1_ringa_whitebox.json'
OUT_MD = ROOT/'references/RINGA_PORT_WHITEBOX_2026-10-17.md'
BUILT = ROOT/'runs/20261013T1515Z-ringb-insector-care/ringA'      # the 2026-10-13 worst-case re-run of the built model (variant 'built')
ROUTES = ('A1', 'A2', 'A3', 'A1-A2', 'A3-A2', 'A2-M', 'A1-A2-M', 'A3-A2-M')
STATES = {'A1': ['0g', 'stopped', 'locked_1.5g'], 'A2': ['spin'], 'A3': ['spin'], 'A2-M': ['spin'],
          'A1-A2': ['stopped', 'locked_1.5g'], 'A3-A2': ['stopped', 'locked_1.5g'], 'A1-A2-M': ['stopped', 'locked_1.5g'], 'A3-A2-M': ['stopped', 'locked_1.5g']}
# PROTOTYPE variants: (port clear radius m or None = built 0.80, extra chamber depth m); 'base' = the workspace whose build a variant reuses,
# 'lad' / 'cs' = in-memory edits of the survey scene and routes (ladder_edit, couch_side), never saved to the workspace asset
VARIANTS = {
    'RA_D20': dict(pc=None, depth=0.20, note='chamber 0.20 m deeper, port as built (1.60 m)'),
    'RA_D40': dict(pc=None, depth=0.40, note='chamber 0.40 m deeper, port as built (1.60 m)'),
}
# Second pass (2026-10-17, the two next bounded comparisons of pass 1): the trunk ladder (both stiles, rungs, brackets) and the trunk arrest
# rail with its brackets moved clear of the ring A spine-port bend, the L1-A stile style (studies/l1a_stile.py: a window over the port's X
# extent +- WIN_PAD_M blended to the built ladder over RAMP_M), and a couch-side transfer space at A2. Rail, stile, bracket and couch
# ratings stay OPEN; grip / arrest continuity over a moved or removed section is OPEN (no fall-arrest number is assumed).
JOG = dict(kind='jog', dth=30.0, drl=0.04)     # PROTOTYPE: section rotated 30 deg away from the swing side (285 -> 315 deg) + 0.04 m outward
CUT = dict(kind='cut', pad=0.25)               # PROTOTYPE: ladder and rail start above the port window (port X + port r + pad); fold-away lower section
for _d in (20, 40):
    _b = f'RA_D{_d}'
    VARIANTS[f'{_b}_JG'] = dict(pc=None, depth=_d/100, base=_b, lad=JOG, note=f'{_b} + trunk ladder and arrest rail joggled 30 deg away from '
                                'the swing side and 0.04 m outward in the port window (L1-A JG/OR style)')
    VARIANTS[f'{_b}_CL'] = dict(pc=None, depth=_d/100, base=_b, lad=CUT, note=f'{_b} + trunk ladder and arrest rail start above the port window '
                                '(the bend free of members; the lower section folds away, PROTOTYPE)')
    VARIANTS[f'{_b}_CL_CS'] = dict(pc=None, depth=_d/100, base=_b, lad=CUT, cs=True, note=f'{_b}_CL + couch-side transfer space at A2: '
                                   'the litter parks alongside the Medical_Couch at carry height, the Lab_Bench is relocated (location OPEN)')
# Third pass (2026-10-17, the next steps of pass 2): the pass-2 cut left the trunk arrest rail (A1 -0.046) and trunk handrail 2 (JG -0.033) as the
# unsuited limits and the ring-side tube floor-ladder arrest rails as the suited annulus limit (-0.114 / -0.122). CF<pad>: the cut extended to
# the bend's full reach (pad above the port window) and applied to trunk handrail 2 as well; TR: the floor-ladder-2 arrest rails of both crew
# tubes fold away (stowable sections, PROTOTYPE) for a casualty transfer. Fall-arrest continuity over a cut or folded section stays OPEN.
HANDRAIL2 = ('Crew_Trunk_Handrail_2',)
TUBE_RAILS = ('Crew_Tube_1_1_Floor_Ladder_2_Arrest_Rail', 'Crew_Tube_1_2_Floor_Ladder_2_Arrest_Rail')
for _pad in (60, 100):
    VARIANTS[f'RA_D40_CF{_pad}_TR_CS'] = dict(pc=None, depth=0.40, base='RA_D40', cs=True,
                                              lad=dict(kind='cut', pad=_pad/100, extra=HANDRAIL2, fold=TUBE_RAILS),
                                              note=f'RA_D40_CL_CS with the cut {_pad/100:.2f} m above the port window, trunk handrail 2 cut too, and the '
                                              'tube floor-ladder-2 arrest rails folded away (PROTOTYPE stowable sections)')
PASS1 = ('built', 'RA_D20', 'RA_D40')
WIN_PAD_M = 0.25                               # L1-A window pad and blend (studies/l1a_stile.py)
RAMP_M = 0.90
LADDER = ('Crew_Trunk_Ladder_Stile_1', 'Crew_Trunk_Ladder_Stile_2', 'Crew_Trunk_Ladder_Rungs', 'Crew_Trunk_Ladder_Brackets',
          'Crew_Trunk_Arrest_Rail', 'Crew_Trunk_Arrest_Rail_Brackets')
CS_GAP_M = 0.10                # PROTOTYPE couch-side transfer gap (bridged by a transfer board / slide sheet, OPEN) for the widest carrier
CS_HALF_M = 0.857/2            # widest carrier half-width: the suited capsule S (hum003_routes.CARRIERS)
# Not buildable with the existing knobs: a spine port larger than the 1.6 m trunk (port clear radius 0.90 m) fails human_entry.check
# (asin(clear / trunk radius) > 1): the port cannot be wider than the bore it opens into, so a larger spin-port turn needs a trunk-side
# flare / junction, which has no study hook (run 20261017T0900Z-ringa-whitebox, RA_P090 build.log).
NOT_BUILDABLE = {'RA_P090': 'spine port 1.80 m clear > 1.60 m trunk bore: human_entry.check math domain error (asin(clear/trunk radius) > 1)'}
CARRIERS = 'ACKS'
STUDY_MARGIN_M = 0.05                          # owner study target (RINGB-006), never widened


def edit(text, v):
    t = '\n# ring A port whitebox workspace only (studies/ringa_port_whitebox.py)\n[human_entry.study]\n'
    if v['pc'] is not None:
        t += f'port_clear_radius_m = {{ "1" = {v["pc"]} }}\n'
    if v['depth']:
        t += f'chamber_depth_extra_m = {{ "1" = {v["depth"]} }}\n'
    assert '[human_entry.study]' not in text
    return text+t


def work_of(name):
    return RUN/VARIANTS.get(name, {}).get('base', name)/'work'


def port_window(s):
    import human_entry as he
    return next((x, r) for n, x, _, r in he.openings(s) if n == 'Crew_Port_1_1')


def _resample(q, xs):
    """An axis-parallel prism record (two end rings) as rings at xs (same section), so an X-dependent edit can bend it."""
    import math
    vs = [tuple(v) for v in q['vs']]; x0 = min(v[0] for v in vs); x1 = max(v[0] for v in vs)
    ring = [v for v in vs if abs(v[0]-x0) < 1e-4]
    assert all(abs(v[0]-x0) < 1e-4 or abs(v[0]-x1) < 1e-4 for v in vs) and 2*len(ring) == len(vs), q['name']
    cy = sum(v[1] for v in ring)/len(ring); cz = sum(v[2] for v in ring)/len(ring)
    ring.sort(key=lambda v: math.atan2(v[2]-cz, v[1]-cy)); n = len(ring); xs = [x for x in xs if x0 <= x <= x1]
    xs = sorted(set([x0, x1]+xs)) if xs and xs[0] > x0 else sorted(set(xs+[x1]))
    nv = [(x, v[1], v[2]) for x in xs for v in ring]
    fs = [(i*n+k, i*n+(k+1) % n, (i+1)*n+(k+1) % n, (i+1)*n+k) for i in range(len(xs)-1) for k in range(n)]
    fs += [tuple(range(n))[::-1], tuple(range((len(xs)-1)*n, len(xs)*n))]
    return nv, fs


def ladder_edit(s, records, lad):
    """PROTOTYPE: the trunk ladder + arrest rail records near ring A's spine port joggled (rotation about the trunk axis + radial offset, full over
    the window, blended over RAMP_M) or cut below the window top. In memory only (the workspace asset is never saved)."""
    import math
    xp, rp = port_window(s); a = rp+WIN_PAD_M
    w = lambda x: max(0.0, min(1.0, 1.0-(abs(x-xp)-a)/RAMP_M))
    out = []
    extra = lad.get('extra', ()); fold = lad.get('fold', ())
    for q in records:
        if q['name'] in fold:
            continue                                   # folded away for the transfer (PROTOTYPE)
        if q['name'] not in LADDER and not q['name'].startswith(extra or ('\0',)):
            out.append(q); continue
        prism = q['name'] in ('Crew_Trunk_Ladder_Stile_1', 'Crew_Trunk_Ladder_Stile_2', 'Crew_Trunk_Arrest_Rail')
        if lad['kind'] == 'cut':
            xc = xp+rp+lad['pad']
            if prism:
                vs, fs = _resample(q, [xc]); keep = {i for i, v in enumerate(vs) if v[0] >= xc-1e-6}
            else:
                vs, fs = [tuple(v) for v in q['vs']], [tuple(f) for f in q['fs']]; keep = {i for i, v in enumerate(vs) if v[0] >= xc}
            fs = [f for f in fs if all(i in keep for i in f)]
            if not fs:
                continue
        else:
            if prism:
                vs, fs = _resample(q, [xp-a-RAMP_M+k*0.05 for k in range(int((2*(a+RAMP_M))/0.05)+1)])
            else:
                vs, fs = [tuple(v) for v in q['vs']], [tuple(f) for f in q['fs']]
            nv = []
            for x, y, z in vs:
                k = w(x); rho = math.hypot(y, z)+lad['drl']*k; th = math.atan2(z, y)+math.radians(lad['dth'])*k
                nv.append((x, rho*math.cos(th), rho*math.sin(th)))
            vs = nv
        used = sorted({i for f in fs for i in f}); lo = [min(vs[i][k] for i in used) for k in range(3)]; hi = [max(vs[i][k] for i in used) for k in range(3)]
        out.append(dict(q, vs=vs, fs=fs, lo=lo, hi=hi))
    return out


def _medical(s):
    import crew_transfer as ct
    import habitat_interior as hi
    import human_entry as he
    k = s['habitat']['layout']['functions'].index('WORK_MEDICAL_OPS')+1; rot, v, la = he.vestibule_station(s, 1)
    zones = {q['name']: q for q in hi.zones(s, 'WORK_MEDICAL_OPS')}
    return (lambda p: he.at_index(rot, ct.sector_point(s, la[k], p))), zones


def couch_edit(s, records):
    """PROTOTYPE transfer space: ring A's Lab_Bench (opposite the couch across the aisle) relocated out of the medical sector (location OPEN)."""
    import numpy as np
    point, zones = _medical(s); b = zones['Lab_Bench']; c = np.asarray(point(tuple((b['min'][i]+b['max'][i])/2 for i in range(3))))
    hit = lambda q: q['name'] in ('Lab_Bench', 'Sector_Fit_Room_Lab_Bench', 'Sector_Fit_Room_Lab_Bench_Text') and \
        all(q['lo'][i]-1.5 <= c[i] <= q['hi'][i]+1.5 for i in range(3))
    gone = [q for q in records if hit(q)]
    assert any(q['name'] == 'Lab_Bench' for q in gone), 'ring A Lab_Bench not found'
    return [q for q in records if not hit(q)]


def couch_side(s, routes):
    """PROTOTYPE couch-side transfer at A2: the M leg ends with the litter alongside the Medical_Couch in the aisle at carry height (its centre
    CS_GAP_M + the widest carrier half-width off the couch edge, head at the couch's head end), instead of sideways over the couch; the slide across
    is a staff action (OPEN). As on the built couch leg (couch = True) the rescuers are not swept inline on the last leg: they stand on the
    attendant strip beside the litter (its width in geom), since an inline head-end rescuer would stand in the sector end wall."""
    import casualty_sweep as cs
    import human_entry as he
    point, zones = _medical(s); c = zones['Medical_Couch']; L = he.landing(s); y = cs.CARRY_Y_M
    zc = c['min'][2]-CS_GAP_M-CS_HALF_M; xe = c['max'][0]
    leg = [('M', point((L['x'], y, L['z']))), ('M', point((L['x'], y, zc))), ('M', point((xe, y, zc)))]
    for k in [k for k in routes if k.startswith('A') and k.endswith('-M')]:
        p = routes[k]['path']; cut = next(i for i, q in enumerate(p) if q[0] == 'M')
        routes[k] = dict(path=p[:cut]+leg, couch=True)
    return routes


def build(names):
    for name in names:
        vd = RUN/name; work = work_of(name)
        if work.exists():
            shutil.rmtree(work)
        vd.mkdir(parents=True, exist_ok=True)
        shutil.copytree(ROOT/'data', work/'data')
        p = work/'data/wayfarer_3d.toml'; p.write_text(edit(p.read_text(), VARIANTS[name]))
        with open(vd/'build.log', 'w') as log:
            code = subprocess.call([BLENDER, '-b', '--factory-startup', '--python', str(ROOT/'src/wayfarer/studies/ringb_unified.py'), '--', 'buildwrap', '--root', str(work)],
                                   stdout=log, stderr=subprocess.STDOUT, cwd=ROOT)
        print(name, 'build exit', code, flush=True)


def survey(args):
    import casualty_sweep as cs
    import hum003_routes as hr
    ru.UNI = RUN; ru.work_of = work_of; v = VARIANTS[args.variant]
    scene0, routes0 = cs.scene, hr.trunk_routes

    def scene(s, ins, open_=1.0):
        r = scene0(s, ins, open_)
        if v.get('lad'):
            r = ladder_edit(s, r, v['lad'])
        if v.get('cs'):
            r = couch_edit(s, r)
        return r
    cs.scene = scene
    if v.get('cs'):
        hr.trunk_routes = lambda s: couch_side(s, routes0(s))
    ru.survey(argparse.Namespace(variant=args.variant, route=args.route, carrier=args.carrier))


def geom(args):
    """Ring A vestibule stations of the variant and mesh overlaps of its vestibule family with every other built mesh (Blender)."""
    import bpy
    import casualty_sweep as cs
    import crew_transfer as ct
    from mathutils.bvhtree import BVHTree
    from spec import load
    root = work_of(args.variant); s = load(root)[0]; v = ct.vestibule(s, 1)
    bpy.ops.wm.open_mainfile(filepath=str(root/'assets/wayfarer/WF_WAYFARER_001.blend')); records = cs.scene(s, cs.load_inspect(), 1.0)
    fam = lambda n: re.match(r'(Crew_Vestibule_1|Crew_Port_1_)', n)
    skip = lambda n: bool(fam(n)) or n.startswith(('Crew_Tube_1_', 'Crew_Trunk', 'Structural_Spine', 'Crew_Connector', 'Crew_Port'))
    hits = {}
    for q in [q for q in records if fam(q['name'])]:
        tq = BVHTree.FromPolygons([tuple(x) for x in q['vs']], [tuple(f) for f in q['fs']])
        for o in records:
            if skip(o['name']) or any(o['lo'][i] > q['hi'][i] or o['hi'][i] < q['lo'][i] for i in range(3)):
                continue
            if tq.overlap(BVHTree.FromPolygons([tuple(x) for x in o['vs']], [tuple(f) for f in o['fs']])):
                hits.setdefault(q['name'], set()).add(o['name'])
    out = dict(variant=args.variant, port_clear_m=round(2*v['port_clear'], 3), vestibule_u_m=[round(v['u0'], 3), round(v['u1'], 3)],
               chamber_clear_radius_m=round(v['clear'], 3), chamber_outer_radius_m=round(v['r1'], 3),
               mesh_overlaps={k: sorted(x)[:8] for k, x in hits.items()}, done=True)
    vv = VARIANTS.get(args.variant, {})
    if vv.get('lad'):                          # the edited members: angles, radii and X start in the port window (trunk clear radius 0.80 m)
        import math
        xp, rp = port_window(s); win = (xp-rp-WIN_PAD_M, xp+rp+WIN_PAD_M); lad = {}
        for q in ladder_edit(s, records, vv['lad']):
            if q['name'] in LADDER and q['name'] not in lad:
                ps = [p for p in q['vs'] if win[0] <= p[0] <= win[1]]
                lad[q['name']] = dict(x_start_m=round(q['lo'][0], 3), in_window=bool(ps),
                                      deg=[round(math.degrees(math.atan2(p[2], p[1])) % 360, 1) for p in (min(ps, key=lambda p: math.atan2(p[2], p[1]) % (2*math.pi)),
                                           max(ps, key=lambda p: math.atan2(p[2], p[1]) % (2*math.pi)))] if ps else None,
                                      max_radius_m=round(max(math.hypot(p[1], p[2]) for p in ps), 3) if ps else None)
        out['ladder'] = dict(port_x_m=round(xp, 3), window_x_m=[round(win[0], 3), round(win[1], 3)], members=lad)
    if vv.get('cs'):
        point, zones = _medical(s); c = zones['Medical_Couch']; zc = c['min'][2]-CS_GAP_M-CS_HALF_M
        nxt = max(q['max'][2] for n, q in zones.items() if n != 'Lab_Bench' and q['max'][2] <= c['min'][2] and q['max'][0] > c['min'][0] and q['min'][0] < c['max'][0])
        out['couch_side'] = dict(litter_centre_z_m=round(zc, 3), couch_edge_z_m=c['min'][2], strip_to_next_block_m=round(c['min'][2]-nxt, 3),
                                 attendant_strip_m=round(zc-CS_HALF_M-nxt, 3), relocated='Lab_Bench')
    (RUN/args.variant).mkdir(parents=True, exist_ok=True); (RUN/args.variant/'geom.json').write_text(json.dumps(out, indent=1)+'\n')
    print('WF_RA_GEOM', json.dumps(out), flush=True)


def run(args):
    from concurrent.futures import ThreadPoolExecutor
    jobs = [(f'geom {v}', ['geom', '--variant', v], RUN/v/'geom.json') for v in VARIANTS]
    jobs += [(f'survey {v} {r} {c}', ['survey', '--variant', v, '--route', r, '--carrier', c], RUN/v/'survey'/f'{r}_{c}.json')
             for v in VARIANTS for r in ROUTES for c in CARRIERS]
    jobs = [j for j in jobs if args.only in j[0]]
    jobs.sort(key=lambda j: 0 if '-' in j[0].split()[-2] else 1)        # the long annulus legs first
    (RUN/'logs').mkdir(parents=True, exist_ok=True)

    def go(j):
        label, argv, done = j
        if done.exists() and json.loads(done.read_text()).get('done'):
            return 0
        log = RUN/'logs'/(re.sub(r'[^A-Za-z0-9_.-]+', '_', label)+'.log'); t = time.time()
        for _ in range(3):                    # Blender occasionally crashes while evaluating the assembly; retry
            with open(log, 'w') as f:
                code = subprocess.call(['timeout', '-s', 'KILL', '5400', BLENDER, '-b', '--factory-startup', '--python-exit-code', '1',
                                        '--python', str(Path(__file__).resolve()), '--']+argv, stdout=f, stderr=subprocess.STDOUT, cwd=ROOT)
            if code == 0:
                break
        print('done', label, code, f'{time.time()-t:.0f}s', flush=True); return code
    with ThreadPoolExecutor(args.workers) as ex:
        list(ex.map(go, jobs))


def _st(m):
    return 'OPEN' if m is None else ('FAIL' if m < 0 else ('MARGINAL' if m < STUDY_MARGIN_M else 'PASS'))


def collect():
    out = dict(study='Ring A port and spin-port turn L2 WHITEBOX (owner 2026-10-17, S&E 15!A198 OWN-RES-RA; r2-A)',
               status='NONCANON PROTOTYPE DISPOSABLE STUDY; L2 COMPARATIVE / ALL HIGH-G SAFETY HOLD; no port, chamber, cutout or rating released',
               method='ringb_unified.survey worst case (RINGB-006) in disposable workspaces; [human_entry.study] knobs of crew_transfer.vestibule; '
                      'U = worst of A/C/K, S = suited; PASS >= 0.05 m, MARGINAL 0..0.05, FAIL < 0',
               worst_case_over=ru.WORST_OVER, variants={})
    for name, uni, v in [('built', BUILT, dict(pc=None, depth=0.0, note='ring A as built (2026-10-13 worst-case re-run)'))] + \
                        [(k, RUN, VARIANTS[k]) for k in VARIANTS]:
        ru.UNI = uni; rows = {}
        for r in ROUTES:
            row = {}
            for grp, classes in (('U', 'ACK'), ('S', 'S')):
                stt = ru.seg_stats(name, r, classes)
                if stt:
                    row[grp] = dict(least_m=stt['least_m'], status=_st(stt['least_m']), nearest=stt['nearest'], case=stt['case'],
                                    per_class={c: x['least_m'] for c, x in stt['per_class'].items()})
            rows[r] = dict(states=STATES[r], **row)
        g = RUN/name/'geom.json'
        out['variants'][name] = dict(spec=v, geom=json.loads(g.read_text()) if g.exists() else None, routes=rows)
    out['not_buildable'] = NOT_BUILDABLE
    OUT_JSON.write_text(json.dumps(out, indent=1)+'\n'); OUT_MD.write_text(md(out)); print('wrote', OUT_JSON, OUT_MD)


FINDINGS = """## Findings (Claude, numbers from the tables)

1. **No ring A leg passes in any variant.** Ring A stays a FAIL comparator (15!A198); nothing here is a release, and rail, stile, bracket,
   couch and fall-arrest ratings stay OPEN.
2. **The chamber depth is the annulus-leg knob.** 0.20 m deeper turns the unsuited locked / stopped annulus legs (A1-A2, A3-A2 and their
   couch legs) from FAIL (-0.065 / -0.073 m) to MARGINAL +0.012 m; 0.40 m gives +0.033 m, still below the 0.05 m target. The ladder
   variants do not change these legs (the trunk ladder is not on them); their limit is Structural_Spine (D20) or the ring-side tube
   Crew_Tube_1_2 / its floor-ladder arrest rails (D40).
3. **Moving the trunk ladder and arrest rail out of the bend helps only with the 0.40 m chamber.** With D20 the spin-port turn
   (A2, A3, A2-M) stays at -0.106 / -0.114 m, set by the port rim Crew_Port_1_1. With D40 the joggle (JG, 30 deg + 0.04 m) lifts A2 / A2-M
   from -0.106 to -0.039 m and A3 from -0.104 to -0.033 m; the cut (CL, members start at X 83.70) gives -0.050 / -0.046 m, now limited by the
   cut rail end. A1 (0 g / stopped / 1.5 g) moves from -0.103 to -0.033 m (JG, next limit trunk handrail 2 at 255 deg) or -0.046 m (CL,
   the cut rail end), in both depths. All stay FAIL.
4. **The suited casualty still fails every leg** (-0.113 to -0.344 m). The ladder variants move the suited trunk limit from the arrest rail
   (-0.171 m) to the port rim (A2 / A3 -0.165 / -0.169 m with D40) and the ring-side tube floor-ladder arrest rails (A1 -0.113 / -0.117 m); with
   D20 the port rim keeps A2 / A3 at -0.337 / -0.344 m.
5. **The couch-side transfer space removes the Medical_Couch limit.** With the litter parked alongside the couch (0.10 m transfer gap for
   the widest carrier, a 1.14 m attendant strip where the Lab_Bench stood, rescuers not swept inline on the last leg as on the built couch
   leg) the medical leg reaches the sweep cap (+0.100 m, all classes incl. S); A1-A2-M / A3-A2-M then equal their annulus legs: +0.012 /
   -0.159 m (D20) and +0.033 / -0.122 m (D40). Lab_Bench relocation, transfer board and the slide across are OPEN.
6. **Best combination (RA_D40_CL_CS): unsuited MARGINAL +0.033 m on the four annulus legs, FAIL -0.046 to -0.050 m on A1 / A2 / A3 / A2-M;
   suited FAIL everywhere.** The remaining limits are the port rim Crew_Port_1_1 (suited spin-port turn), the cut end of the trunk arrest rail
   and trunk handrail 2 (unsuited trunk legs) and the ring-side tube floor-ladder arrest rails (suited annulus legs).
7. **Member notes (geometry screen, no load).** The joggle carries the stile and arrest-rail bracket feet 0.04 m into the trunk wall line
   (r <= 0.84 m against the 0.80 m clear radius: re-anchoring OPEN). The cut leaves the arrest rail without a bracket below X 98.54 (the built
   rail is held at its ends) and the climber without grip or arrest over the bottom 2.0 m (X 81.67-83.70) unless a fold-away section is
   rated; both OPEN. The D20_JG A3 unsuited -0.132 m is a K x1.08 seed-202 rescuer search value at the port rim, not a ladder effect.
8. **A port wider than the trunk is not buildable** with the existing knobs; a larger spin-port turn needs a trunk-side flare or junction
   (a new geometry hook, an owner-level pressure-architecture change).

9. **Third pass (CF60 / CF100 _TR_CS: the cut 0.60 / 1.00 m above the port window incl. trunk handrail 2, both tubes' floor-ladder-2
   arrest rails folded away, on RA_D40 with the couch-side space).** CF100 gives the **first non-failing trunk leg: A1 unsuited MARGINAL
   +0.012 m** (next limit the trunk fit frame); CF60 leaves A1 at -0.008 m (the supply diffuser). The spin-port turn (A2, A3, A2-M) rises to
   -0.013 / -0.014 m in both and is now set by the **port rim Crew_Port_1_1**, as are the suited A2 / A3 legs (-0.169 / -0.165 m, unchanged).
   Folding the tube rails lifts suited A1-A2 from -0.122 to -0.067 m (next: the rail brackets) but not A3-A2 (-0.113 m, tube 3's rail is
   not on that leg's limiting section; it stays the nearest). Unsuited annulus legs stay +0.033 m (Crew_Tube_1_2).
10. **What is left is the port.** With every member moved that the knobs allow, the 1.60 m spine port (= the trunk bore) limits the
   unsuited spin-port turn by 0.013 m short of zero (0.063 m short of the 0.05 m target) and the suited casualty by 0.165-0.169 m. A
   suited pass needs a port wider than the trunk, i.e. a trunk-side flare or junction: a pressure-architecture change that is the owner's.
   The cut / folded sections leave the climber without grip or arrest from the trunk ladder foot to X 84.45 m (about 3.7 m) and in the tube floor-ladder legs
   during a transfer (stowage, re-deployment and fall-arrest continuity OPEN).
"""


def md(d):
    L = ['# Ring A port and spin-port turn whitebox (owner 2026-10-17, S&E 15!A198)', '', d['status']+'.', '',
         'Code `src/wayfarer/studies/ringa_port_whitebox.py`, result `references/p1_ringa_whitebox.json`, runs `'+str(RUN.relative_to(ROOT))+'`.',
         'Method: '+d['method']+'.', '',
         '## First pass: chamber depth', '', '| Route (states) | '+' | '.join(PASS1)+' |', '| --- |'+' --- |'*len(PASS1)]
    for r in ROUTES:
        cells = []
        for name, v in [(k, d['variants'][k]) for k in PASS1]:
            x = v['routes'][r]
            cells.append(' / '.join(f"{x[g]['least_m']:+.3f} {x[g]['nearest']}" if g in x else 'OPEN' for g in ('U', 'S')))
        L.append(f"| {r} ({', '.join(STATES[r])}) | "+' | '.join(cells)+' |')
    L += ['', 'Cells: unsuited worst (A/C/K) / suited S, metres, with the nearest object.', '']
    L += ['## Second pass: ladder / arrest rail clear of the bend and the couch-side transfer space', '',
          'Least clearance per route and variant (m; unsuited U = worst of A/C/K, suited S), then the nearest object of each.', '',
          '| Variant | '+' | '.join(ROUTES)+' |', '| --- |'+' --- |'*len(ROUTES)]
    for name, v in d['variants'].items():
        L.append(f'| {name} | '+' | '.join(' / '.join(f"{v['routes'][r][g]['least_m']:+.3f}" if g in v['routes'][r] else 'OPEN' for g in ('U', 'S'))
                                         for r in ROUTES)+' |')
    L += ['', '| Route | Variant | U least m | U nearest | S least m | S nearest |', '| --- | --- | --- | --- | --- | --- |']
    for r in ROUTES:
        for name, v in d['variants'].items():
            x = v['routes'][r]; c = lambda g: (f"{x[g]['least_m']:+.3f} {x[g]['status']}", x[g]['nearest'] or '-') if g in x else ('OPEN', '-')
            L.append(f'| {r} | {name} | {c("U")[0]} | {c("U")[1]} | {c("S")[0]} | {c("S")[1]} |')
    L += ['', '## Variants', '']
    for name, v in d['variants'].items():
        g = v['geom'] or {}
        L.append(f"- **{name}**: {v['spec']['note']}" + (f"; port {g['port_clear_m']} m, chamber clear radius {g['chamber_clear_radius_m']} m, "
                 f"overlaps {g['mesh_overlaps'] or 'none'}" if g else ''))
        if g.get('ladder'):
            m = g['ladder']['members']
            L.append(f"  - port window X {g['ladder']['window_x_m'][0]}-{g['ladder']['window_x_m'][1]} m: "+'; '.join(
                f"{k.replace('Crew_Trunk_', '')} from X {q['x_start_m']}" + (f" at {q['deg'][0]}-{q['deg'][1]} deg, r <= {q['max_radius_m']} m" if q['deg'] else '')
                for k, q in m.items()))
        if g.get('couch_side'):
            c = g['couch_side']
            L.append(f"  - couch side: litter centre {c['litter_centre_z_m']} m across (couch edge {c['couch_edge_z_m']} m), attendant strip "
                     f"{c['attendant_strip_m']} m beside the litter, {c['relocated']} relocated")
    L += ['', FINDINGS, '## Not buildable with the existing study knobs', ''] + [f'- **{k}**: {v}' for k, v in d.get('not_buildable', {}).items()]
    return '\n'.join(L)+'\n'


if __name__ == '__main__':
    argv = sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else sys.argv[1:]
    ap = argparse.ArgumentParser(); sp = ap.add_subparsers(dest='cmd')
    b = sp.add_parser('build'); b.add_argument('names', nargs='?', default=','.join(VARIANTS))
    q = sp.add_parser('survey'); q.add_argument('--variant'); q.add_argument('--route'); q.add_argument('--carrier')
    q = sp.add_parser('geom'); q.add_argument('--variant')
    q = sp.add_parser('run'); q.add_argument('--workers', type=int, default=12); q.add_argument('--only', default='')
    sp.add_parser('collect')
    a = ap.parse_args(argv)
    if a.cmd == 'build':
        build(a.names.split(','))
    elif a.cmd == 'survey':
        survey(a)
    elif a.cmd == 'geom':
        geom(a)
    elif a.cmd == 'run':
        run(a)
    elif a.cmd == 'collect':
        collect()
