"""M5 BODY-C3: the grouped optimization of the BODY-C2 separate D / He-3 / H2 layout (owner 2026-10-19, S&E 15!A218 "use BODY-C2 as the
reference for the next reversible fuel-packaging iteration; keep BODY-C as the comparison baseline; optimize the grouping of He-3, D and
H2 vessels to reduce cryogenic interfaces, refrigeration distances, plumbing complexity and maintenance constraints", 98!A120).
WORKING STUDY CHOICE / FUEL QUANTITY OPEN / NO REBUDGET RELEASE: nothing is installed in WF_STORAGE, the hull is not resized, no smaller
inventory is selected and no feasibility is claimed; the calculated shortfalls stay visible.

Function: keep C2's vessel count per species (15 He-3, 3 D2, 9 H2: the same capacity and the same deficits) and regroup them so each
species fills whole ring modules. Fixed: everything C2 fixes (the BODY-C installation, utility frames at X -22 / +16, the measured bay,
the S&E 62 needs). Unknown (OPEN): heat leak, cooler power, feed design, line sizes. Design freedom (PROTOTYPE, this file): the
module-homogeneous rule and the selection order below.

Selection, over all 504 module-homogeneous orders of 5 He-3 + 1 D2 + 3 H2 modules (lexicographic, PROTOTYPE judgment):
  1. shortest longest He-3 cold line to a refrigeration frame (3.2 K service is the costliest line; C2 has 31-32 m, 15!G218);
  2. fewest He-3 (3.2 K) to 20 K jacket faces: each is a permanent 17 K thermal break with separate relief (C2 has 33);
  3. shortest summed He-3 cold line (all 15 vessels);
  4. shortest total feed-line length in the keel lanes;
  5. fewest D2 / H2 faces (same 20 K class, separate relief).
The best order with the faces criterion first is kept as the alternative (C3-alt): fewer faces, but C2's long He-3 lines.

    python3 src/wayfarer/studies/m5_body_c3.py            # search, comparison C / C2 / C3 -> references/m5_body_c3.json
    /snap/bin/blender -b --factory-startup --python-exit-code 1 --python src/wayfarer/studies/m5_body_c3.py -- --asset   # + study asset
        assets/wayfarer/studies/WF_STUDY_BODY_C3.blend and its overlap screen against the saved vehicle
"""
from pathlib import Path
import argparse
import itertools
import json
import sys
ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT/'src/wayfarer'), str(ROOT/'src/wayfarer/build'), str(ROOT/'src/wayfarer/studies'), str(ROOT/'src/wayfarer/shots')]
import body_architecture as ba
import m5_cutaway as mc
import m5_body_c2 as c2m

OUT_JSON = ROOT/'references/m5_body_c3.json'
ASSET = ROOT/'assets/wayfarer/studies/WF_STUDY_BODY_C3.blend'
COLLECTION = 'WF_STUDY_BODY_C3'
FAMILIES = c2m.FAMILIES
CODE = {'HE3': '3', 'D2': 'D', 'H2': 'H'}   # order strings, aft to forward


def module_rule_assign():
    """BODY-C's module rule as a lobe map (fore -> aft He-3, D2; H2 none), for like-for-like metrics."""
    res = mc.body_c(); out = {}
    for p in res['parts']:
        if p.get('family'):
            m = int(p['name'].split('_')[3]); mid = float(p['name'].split('_')[4])
            out[(m, (mid-60) % 360)] = p['family']
    return out


def metrics(res, assign):
    """Like-for-like comparison: capacity, cryogenic boundaries, line lengths, refrigeration distance, isolation zones, screened mass."""
    mods = ba.option('C')['modules']; x_aft = mods[0]['x0']
    frames = sorted({p['x0'] for p in res['parts'] if p['kind'] == 'refrigeration_frame'})
    fc = sorted({(p['x0']+p['x1'])/2 for p in res['parts'] if p['kind'] == 'refrigeration_frame'})
    faces = {}
    for (m, k), f in assign.items():
        for nb in ((m+1, k), (m, (k+120) % 360)):
            g = assign.get(nb)
            if g and g != f:
                key = '-'.join(sorted((f, g))); faces[key] = faces.get(key, 0)+1
    thermal_break = sum(v for k, v in faces.items() if 'HE3' in k)
    lane_runs = {}                                       # lane -> species -> forwardmost bordering lobe x1
    for (m, k), f in assign.items():
        for lane in (k, (k+120) % 360):
            d = lane_runs.setdefault(lane, {}); d[f] = max(d.get(f, x_aft), mods[m]['x1'])
    line_m = round(sum(x-x_aft for d in lane_runs.values() for x in d.values()), 1)
    dist = {f: [min(abs((mods[m]['x0']+mods[m]['x1'])/2-x) for x in fc) for (m, k), g in assign.items() if g == f] for f in FAMILIES}
    # isolation zones: connected same-species groups over the face graph (a zone is warmed, purged or isolated as one unit)
    seen, zones = set(), {f: 0 for f in FAMILIES}
    for s in assign:
        if s in seen:
            continue
        zones[assign[s]] += 1; stack = [s]
        while stack:
            m, k = stack.pop()
            if (m, k) in seen:
                continue
            seen.add((m, k))
            for nb in ((m+1, k), (m-1, k), (m, (k+120) % 360), (m, (k-120) % 360)):
                if nb in assign and assign[nb] == assign[(m, k)]:
                    stack.append(nb)
    mixed = sum(1 for m in range(len(mods)) if len({assign[(m, k)] for k in ba.KEELS if (m, k) in assign}) > 1)
    led = c2m.ledger(res); ms = led['per_bucket']['main_structure']['screen_known_t']; th = led['per_bucket']['radiator_thermal']['screen_known_t']
    cov = c2m.coverage(res)
    return dict(capacity_m3={f: round(v, 1) for f, v in cov['capacity_m3'].items()}, first_ignition_fraction=cov['first_ignition_fraction'],
                first_ignition_deficit_m3=cov['first_ignition_deficit_m3'], full_load_deficit_m3=cov['full_load_deficit_m3'],
                housed_mass_total_t=cov['housed_mass_total_t'], certified_capacity=None,
                jacket_faces=faces, he3_thermal_break_faces=thermal_break,
                line_sets=sum(len(d) for d in lane_runs.values()), lane_line_length_m=line_m,
                lines_per_lane={str(int(l)): sorted(d) for l, d in sorted(lane_runs.items())},
                he3_cold_line_max_m=round(max(dist['HE3']), 1) if dist['HE3'] else None,
                he3_cold_line_sum_m=round(sum(dist['HE3']), 1),
                h2_cold_line_max_m=round(max(dist['H2']), 1) if dist['H2'] else None,
                isolation_zones=zones, mixed_species_modules=mixed,
                screen_main_structure_t=ms, screen_thermal_t=th, refrigeration_frames_x=frames)


def candidates():
    for order in sorted(set(itertools.permutations(['HE3']*5+['D2']+['H2']*3))):
        yield {(m, k): f for m, f in enumerate(order) for k in ba.KEELS}, ''.join(CODE[f] for f in order)


def key(m):
    return (m['he3_cold_line_max_m'], m['he3_thermal_break_faces'], m['he3_cold_line_sum_m'], m['lane_line_length_m'],
            m['jacket_faces'].get('D2-H2', 0))


def search():
    rows = [(key(m), code, a, m) for a, code in candidates() for m in (metrics(mc.body_c(a), a),)]
    return sorted(rows, key=lambda t: t[0])


def screen_all():
    rows = search(); best = rows[0]; a3 = best[2]; c3 = mc.body_c(a3)
    a2 = c2m.balanced_assign(); c2 = mc.body_c(a2); c1 = mc.body_c(); a1 = module_rule_assign()
    front = [dict(order_aft_to_fwd=code, key=list(k)) for k, code, _, _ in rows[:8]]
    alt = min(rows, key=lambda t: (t[3]['he3_thermal_break_faces'], t[3]['he3_cold_line_max_m'], t[3]['lane_line_length_m']))
    out = dict(status='WORKING STUDY CHOICE / FUEL QUANTITY OPEN / NO REBUDGET RELEASE (S&E 15!A218, 98!A120)',
               rule='module-homogeneous; lexicographic: longest He-3 cold line, He-3/20 K faces, summed He-3 cold line, lane line length, '
                    'D2/H2 faces (PROTOTYPE)',
               candidates=len(rows), selected=best[1], best_eight=front,
               alternative_faces_first=dict(order_aft_to_fwd=alt[1], **{k: alt[3][k] for k in (
                   'he3_thermal_break_faces', 'he3_cold_line_max_m', 'he3_cold_line_sum_m', 'lane_line_length_m', 'jacket_faces',
                   'isolation_zones')}),
               compare=dict(body_c=dict(layout='BODY-C module rule (comparison baseline)', **metrics(c1, a1)),
                            body_c2=dict(layout='BODY-C2 balanced lobes (reference, 15!A218)', **metrics(c2, a2)),
                            body_c3=dict(layout=f'BODY-C3 grouped modules, aft to fwd {best[1]}', **metrics(c3, a3))),
               assignment={f'{m}_{int(k)}': f for (m, k), f in sorted(a3.items())},
               free_volume=c2m.free_volume(c3), ledger=c2m.ledger(c3), shortfall_bars=c3['shortfall_bars'])
    return out, c3


def main(asset=False):
    res, c3 = screen_all()
    for name, f in (('body_c', 'm5_body_c.json'), ('body_c2', 'm5_body_c2.json')):
        old = json.loads((ROOT/'references'/f).read_text()).get('overlap')
        res['compare'][name]['overlap_conflicts'] = None if old is None else [(c['study'], c['other']) for c in old['conflicts']]
    if asset:
        res['asset_objects'] = len(mc.build_asset(dict(body_c=c3), ASSET, COLLECTION, 'm5_body_c3',
                                                  'WORKING STUDY CHOICE / FUEL QUANTITY OPEN (15!A218): grouped separate-species layout'))
        res['overlap'] = mc.overlap_screen(None, 'studies/WF_STUDY_BODY_C3.blend', COLLECTION)
    elif OUT_JSON.exists():
        old = json.loads(OUT_JSON.read_text()); res.update({k: old[k] for k in ('asset_objects', 'overlap') if k in old})
    if 'overlap' in res:
        res['compare']['body_c3']['overlap_conflicts'] = [(c['study'], c['other']) for c in res['overlap']['conflicts']]
    OUT_JSON.write_text(json.dumps(res, indent=1)+'\n')
    print('selected', res['selected'], 'of', res['candidates']); print('front', res['best_eight'])
    print('alt', res['alternative_faces_first'])
    for k, v in res['compare'].items():
        print(k, json.dumps({q: v[q] for q in v if q not in ('layout', 'refrigeration_frames_x')}))
    print('free', res['free_volume']['free_m3'], res['free_volume']['claimed_m3'])
    return res


if __name__ == '__main__':
    argv = sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else sys.argv[1:]
    ap = argparse.ArgumentParser(); ap.add_argument('--asset', action='store_true')
    main(ap.parse_args(argv).asset)
