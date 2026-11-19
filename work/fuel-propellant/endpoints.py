"""FPS V1.1 pipe-endpoint screen (study code, work/fuel-propellant; pure, no Blender): every end of every FPS, farm-chain and cluster
service line must land on another line, a piece of equipment, a tank, the cluster bay, an engine service panel or a declared interface.
python3 work/fuel-propellant/endpoints.py [out.json]"""
import json, math, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT/'src'/'wayfarer'))
import spec, fuel_system as fs, fuel_storage as fst, vertex_cluster as vc, vertex_engine as ve

s = spec.load()[0]


def seg_d(p, a, b):
    d = [b[i]-a[i] for i in range(3)]; L2 = sum(x*x for x in d) or 1e-12
    t = max(0.0, min(1.0, sum((p[i]-a[i])*d[i] for i in range(3))/L2))
    return math.dist(p, [a[i]+d[i]*t for i in range(3)])


lines = [(n, pts, r) for n, sp, pts, r in fs.polylines(s)]
lines += [(c['name'], c['path'] and c['points'], c['radius']) for c in fs.chain_lines(s)]
lines += [(p['name'], p['points'], p['radius']) for p in vc.distribution(s) if p['shape'] == 'tube']
h = fs.header(s); lines.append((h['name'], [fs.dm.radial(h['x'], h['r'], 2*math.pi*k/96) for k in range(97)], h['tube']))
for g in fs.h2_injection(s):
    m = g['manifold']; pl = g['placement']
    lines.append((g['manifold_name'], [vc.to_ship(pl, ve.pol(m['x'], m['R'], 360*k/64)) for k in range(65)], m['tube']))
anchors = []          # (name, kind, data)
for e in fs.equipment(s):
    anchors.append((e['name'], 'ball', (e['at'], max(e.get('size', (0, 0, 0)))/2+0.3 if e['shape'] == 'box' else e['length']/2+0.2)))
for t in fst.run_tanks(s):
    anchors.append((t['name'], 'xcyl', (t['x0'], t['x1'], t['y'], t['z'], t['radius'])))
for t in fst.tanks(s):
    anchors.append((t['name'], 'xcyl', (t['x0'], t['x1'], t['y'], t['z'], t['a_env'])))
b = fs.bay_frame(s); anchors.append(('CL_Power_Conditioning_Bay', 'xcyl', (b['x1'], b['x0'], 0.0, 0.0, b['r_out'])))
for e in fs.target_fabrication(s)['equipment']:
    if e['shape'] == 'cyl':
        anchors.append((e['name'], 'seg', (e['a'], e['b'], e['radius'])))
    else:
        anchors.append((e['name'], 'ball', (e['at'], max(e['size'])*0.75)))
for pl in vc.placements(s):
    sp = ve.service_panel(s)
    anchors.append((f"VTX_Service_Panel N{pl['n']}", 'ball', (vc.to_ship(pl, ve.pol(sp['x'], sp['r'], sp['azimuth'])), math.hypot(sp['length'], sp['depth'], sp['width'])/2+0.1)))
    anchors.append((f"CL_Reaction_Hub", 'xcyl', (vc.stations(s)['hub_aft'], vc.stations(s)['hub_fwd'], 0.0, 0.0, vc.config(s)['hub_radius_m'])))
ifs = [(i['name'], i['at']) for i in fs.interfaces(s)]+[(i['name'], i['at']) for i in vc.interfaces(s)]
for r in fs.relief(s):
    anchors.append((f"FPS_Relief_Valve_{r['tank'][-2:]}", 'ball', (r['valve'], r['size']+0.1)))
for q in fs.purge(s):
    anchors.append((q['name'], 'ball', (q['at'], q['length']/2+q['radius']+0.1)))
rf = fs.refuel(s); anchors.append((rf['panel']['name'], 'ball', (rf['panel']['at'], max(rf['panel']['size']))))


def anchored(p, r):
    for n, k, d in anchors:
        if k == 'ball' and math.dist(p, d[0]) <= d[1]+r:
            return n
        if k == 'xcyl':
            x0, x1, y, z, R = d
            if x0-r-0.15 <= p[0] <= x1+r+0.15 and math.hypot(p[1]-y, p[2]-z) <= R+r+0.15:
                return n
        if k == 'seg' and seg_d(p, d[0], d[1]) <= d[2]+r+0.1:
            return n
    return None


rows = []
for name, pts, r in lines:
    if not pts or len(pts) < 2 or math.dist(pts[0], pts[-1]) < 1e-6:
        continue            # loops (ring mains, header, manifolds) have no free end
    for end, p in (('start', pts[0]), ('end', pts[-1])):
        hit = None
        for n2, q, r2 in lines:
            if n2 == name or not q:
                continue
            if any(seg_d(p, a, bb) <= r+r2+0.1 for a, bb in zip(q, q[1:])):
                hit = n2; break
        hit = hit or anchored(p, r)
        if not hit and '_H2_Injectors_' in name and end == 'end':
            hit = 'interface '+name.split('_H2')[0].replace('FPS_', 'IF_FPS_H2_INJECT_')+' (burn-face injector tip, SPECULATIVE coupling)'
        if not hit:
            i = min(ifs, key=lambda i: math.dist(i[1], p))
            if math.dist(i[1], p) <= 0.5:
                hit = 'interface '+i[0]
        rows.append(dict(line=name, end=end, at=[round(v, 2) for v in p], joins=hit))
free = [r for r in rows if not r['joins']]
res = dict(ends=len(rows), free=free, interfaces=sorted({r['joins'] for r in rows if r['joins'] and r['joins'].startswith('interface')}))
if len(sys.argv) > 1:
    json.dump(dict(res, rows=rows), open(sys.argv[1], 'w'), indent=1)
print(json.dumps(dict(ends=res['ends'], free=len(free), interfaces=res['interfaces']), indent=1))
for r in free:
    print('FREE', r)
