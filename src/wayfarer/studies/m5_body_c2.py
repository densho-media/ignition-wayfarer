"""M5 BODY-C2: the separate D / He-3 / H2 layout of the BODY-C keel-lane train, its corrected free volume and interfaces, and the tankage
dry-mass ledger (owner 2026-10-18, S&E 15!A207 OWN-BODY-Q1 G "alternative separate D/He3/H2 layout; measure corrected free volume and
interfaces", 15!A208 G "separate source-tagged envelopes, no more than measured installation area; propagate null for certified
capacity", 15!A209 G "accounting ledger with mutually exclusive category IDs, conservative unsized masses as UNKNOWN and measured
component volumes", 98!A115). WORKING STUDY CHOICE / FUEL QUANTITY OPEN / NO REBUDGET RELEASE: BODY-C (WF_STUDY_BODY_C) stays as the
module-rule comparator; nothing enters the vehicle; no inventory is trimmed and the hull is not resized to hide a deficit.

Function: house all three species at once, each in its own jacketed vessel, so the first-ignition shortfall is shared instead of
leaving one species (H2 in BODY-C) entirely unhoused, and show what that costs in feed lines, species boundaries and dry mass. Fixed:
the BODY-C installation (27 lobe slots between the keels, 9 modules X -57.5..53.5, walls 0.30 m He-3 / 0.15 m D2 and H2, lanes,
manifolds, utility frames, equipment bay, workshop, spine tunnel), the measured bay X -57.5..81.25 r 1.025-4.721 (tank_bay_survey),
the S&E 62 needs (He-3 164.8 t, D 110.1 t IDEAL lower bounds; H2 145.1 t first burn + 180 t reserve, HYPOTHESIS; 600 t PROVISIONAL
aggregate, 15!A207), the 10_WAYFARER_MASS buckets (main structure 150 t, radiator / thermal 100 t, power / comms 50 t, design margin
30 t untouched; 15!A209). Unknown (OPEN): inventory, recycle and return; tank, insulation, support and plant masses; heat leak and cooler
power; feed-system design. Design freedom (PROTOTYPE, this file): the balanced lobe assignment, the screening areal densities.

    python3 src/wayfarer/studies/m5_body_c2.py                    # layout, volumes, interfaces, ledger -> references/m5_body_c2.json
    /snap/bin/blender -b --factory-startup --python-exit-code 1 --python src/wayfarer/studies/m5_body_c2.py -- --asset   # + study asset
        assets/wayfarer/studies/WF_STUDY_BODY_C2.blend and its overlap screen against the saved vehicle
"""
from pathlib import Path
import argparse
import json
import math
import sys
ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT/'src/wayfarer'), str(ROOT/'src/wayfarer/build'), str(ROOT/'src/wayfarer/studies'), str(ROOT/'src/wayfarer/shots')]
import body_architecture as ba
import m5_cutaway as mc

OUT_JSON = ROOT/'references/m5_body_c2.json'
ASSET = ROOT/'assets/wayfarer/studies/WF_STUDY_BODY_C2.blend'
COLLECTION = 'WF_STUDY_BODY_C2'
FAMILIES = ('HE3', 'D2', 'H2')
AGGREGATE_T = 600.0          # 15!A207: PROVISIONAL aggregate (D + He-3 + H2), not LH2
BUCKETS_T = {'main_structure': 150.0, 'drive_package': 250.0, 'radiator_thermal': 100.0, 'power_comms': 50.0,
             'design_margin': 30.0}   # 10_WAYFARER_MASS 2:13 (G2/G9/G10 owner notes 2026-10-18), 15!A209, 15!A219

# SCREENING ONLY (never entered in the ledger, 15!A209 H): order-of-magnitude areal densities to show whether the buckets could plausibly
# absorb the tankage. PROTOTYPE judgment.
SCREEN = dict(shell_kg_m2=10.8,          # Al-Li 2195, 4 mm minimum gauge, inner vessel (flat lobe faces need stiffening: more)
              skin_kg_m2=2.7,            # 1 mm Al outer skin / debris barrier (in space no vacuum shell is needed)
              mli_kg_m2=0.75,            # ~30 layers MLI with spacers
              he3_shield_kg_m2=2.7)      # He-3: one 1 mm Al 20 K intercept shield inside its jacket


def need_first():
    n = mc.liquid_need(); return dict(HE3=n['HE3'], D2=n['D2'], H2=n['H2_FIRST'])


def slot_capacity():
    o = ba.option('C'); span = 120-ba.LANE_DEG
    return {f: mc.lobe(0, ba.MODULE-ba.GAP, o['r_in'], o['r_out'], 0, span, mc.WALL[f])['net_m3'] for f in FAMILIES}


def balanced_assign():
    """Greedy, forward to aft (He-3 then lands farthest from the core where it ties): each lobe slot goes to the species with the lowest
    housed fraction of its first-ignition need, so every species is housed at about the same fraction."""
    o = ba.option('C'); cap = slot_capacity(); need = need_first(); housed = {f: 0.0 for f in FAMILIES}; out = {}
    for m in reversed(range(len(o['modules']))):
        for k in ba.KEELS:
            f = min(FAMILIES, key=lambda q: (housed[q]/need[q], FAMILIES.index(q)))
            out[(m, k)] = f; housed[f] += cap[f]
    return out


def coverage(res):
    a = res['allocation']; cap = a['capacity_m3']; need = mc.liquid_need(); nf = need_first()
    mass = {f: cap[f]*mc.DENSITY[f]/1000 for f in FAMILIES}
    fi = {f: round(min(cap[f], nf[f])/nf[f], 3) for f in FAMILIES}
    return dict(capacity_m3=cap, first_ignition_fraction=fi,
                housed_first_ignition_m3=round(sum(min(cap[f], nf[f]) for f in FAMILIES)),
                first_ignition_deficit_m3=round(sum(min(cap[f], nf[f]) for f in FAMILIES)-need['first_ignition']),
                full_load_deficit_m3=round(sum(cap.values())-need['total']),
                housed_mass_t={f: round(v, 1) for f, v in mass.items()}, housed_mass_total_t=round(sum(mass.values()), 1),
                aggregate_t=AGGREGATE_T, aggregate_fraction=round(sum(mass.values())/AGGREGATE_T, 3),
                certified_capacity=None, note='certified capacity propagates null (15!A208 G); every figure is a PROTOTYPE envelope')


# ---------------------------------------------------------------- free volume

def clip_volume(p, r0, r1, x0, x1):
    a, b = max(p['ri'], r0), min(p['ro'], r1); u, v = max(p['x0'], x0), min(p['x1'], x1)
    return 0.0 if a >= b or u >= v else math.radians(p['a1']-p['a0'])/2*(b*b-a*a)*(v-u)


def free_volume(res):
    """The measured bay (tank_bay_survey) less every BODY-C2 envelope, by category; lanes are counted without the support bulkheads cut
    out of them. The remainder is space no envelope claims."""
    b = ba.bay(); gross = math.pi*(b['r_out']**2-b['r_in']**2)*(b['x1']-b['x0']); cats = {}
    for p in res['parts']:
        v = clip_volume(p, b['r_in'], b['r_out'], b['x0'], b['x1'])
        if p['kind'] in ('he3_cryostat', 'd2_cryostat', 'h2_tank'):
            cats['liquid_net'] = cats.get('liquid_net', 0.0)+v*(1-ba.ULLAGE); cats['ullage'] = cats.get('ullage', 0.0)+v*ba.ULLAGE
        else:
            cats[p['kind']] = cats.get(p['kind'], 0.0)+v
    sup = sum(clip_volume(p, b['r_in'], b['r_out'], b['x0'], b['x1']) for p in res['parts'] if p['kind'] == 'tank_support')
    cats['service_lane'] -= sup
    used = sum(cats.values())
    return dict(bay=dict(b, gross_m3=round(gross)), by_category_m3={k: round(v) for k, v in sorted(cats.items())}, claimed_m3=round(used),
                free_m3=round(gross-used), free_fraction=round((gross-used)/gross, 3),
                where_free='r 1.025-1.10 m round the spine tunnel, the 1 m module gaps outside lanes and utility frames, and the equipment-bay unallocated slice is counted as claimed')


# ---------------------------------------------------------------- interfaces

def interfaces(res, assign):
    o = ba.option('C'); mods = o['modules']; span = 120-ba.LANE_DEG; out = {}
    lanes = {}
    for (m, k), f in assign.items():                     # a lobe at sector mid k+60 borders the lanes at k and k+120
        for lane in (k, (k+120) % 360):
            lanes.setdefault(lane, set()).add(f)
    bounds = {}
    for (m, k), f in assign.items():
        for (m2, k2) in ((m+1, k), (m, (k+120) % 360)):
            if (m2, k2) in assign and assign[(m2, k2)] != f:
                key = '-'.join(sorted((f, assign[(m2, k2)]))); bounds[key] = bounds.get(key, 0)+1
    frames = sorted({p['x0'] for p in res['parts'] if p['kind'] == 'refrigeration_frame'})
    for f in FAMILIES:
        ms = [m for (m, k), g in assign.items() if g == f]
        far = max(mods[m]['x1'] for m in ms) if ms else None
        he = [min(abs((mods[m]['x0']+mods[m]['x1'])/2-x) for x in frames) for m in ms] if frames else []
        out[f] = dict(vessels=len(ms), modules=sorted({m for m in ms}), feed_run_in_bay_m=None if far is None else round(far-ba.bay()['x0'], 1),
                      lanes=sorted(l for l, fs in lanes.items() if f in fs), max_distance_to_refrigeration_frame_m=round(max(he), 1) if he else None)
    return dict(per_family=out, lines_per_lane={str(int(l)): sorted(fs) for l, fs in sorted(lanes.items())}, species_boundaries=bounds,
                refrigeration_frames_x=frames, aft_run_to_drive_m=round(ba.bay()['x0']-(-100.5), 1),
                note='each lane carries a separate line set per species bordering it (no shared lines between He-3, D2 and H2); a species boundary '
                     'is a jacket-to-jacket face across a lane or a module gap (thermal break, separate relief); aft run from the bay end to the '
                     'manifold aft face X -100.5')


# ---------------------------------------------------------------- dry-mass ledger

def lobe_area(p):
    th = math.radians(p['a1']-p['a0']); L = p['x1']-p['x0']
    return 2*(p['ro']-p['ri'])*L+(p['ri']+p['ro'])*th*L+2*th/2*(p['ro']**2-p['ri']**2)


def ledger(res):
    """Mutually exclusive category IDs, each in exactly one existing bucket; mass UNKNOWN (null) for every unsized item; measured volumes
    and areas from the envelopes. A separate SCREEN column (never summed into a bucket) gives an order of magnitude."""
    parts = res['parts']; vessels = [p for p in parts if p['kind'] in ('he3_cryostat', 'd2_cryostat', 'h2_tank')]
    area = {f: sum(lobe_area(p) for p in vessels if p.get('family') == f) for f in FAMILIES}; A = sum(area.values())
    vol = lambda kind: round(sum(p['gross_m3'] for p in parts if p['kind'] == kind), 1)
    n = lambda kind: sum(1 for p in parts if p['kind'] == kind)
    S = SCREEN
    rows = [
        dict(id='TK-MS-01', item='inner vessel pressure shells (He-3 / D2 / H2)', bucket='main_structure', count=len(vessels),
             area_m2={f: round(v) for f, v in area.items()}, volume_m3=None, screen_t=round(A*S['shell_kg_m2']/1000, 1)),
        dict(id='TK-MS-02', item='outer skin / debris barrier of each jacket (no vacuum shell needed in space)', bucket='main_structure',
             count=len(vessels), area_m2=round(A), volume_m3=None, screen_t=round(A*S['skin_kg_m2']/1000, 1)),
        dict(id='TK-MS-03', item='mounting frames: support bulkheads to the keel rails (lobe saddles)', bucket='main_structure',
             count=n('tank_support'), volume_m3=vol('tank_support'), screen_t=None),
        dict(id='TK-MS-04', item='MLI / aerogel in the jacket allowance', bucket='main_structure', count=len(vessels),
             area_m2=round(A), volume_m3=vol('insulation_envelope'), screen_t=round(A*S['mli_kg_m2']/1000, 1)),
        dict(id='TK-MS-05', item='structural heat barrier (thermal standoffs in supports and saddles)', bucket='main_structure', count=None,
             volume_m3=None, screen_t=None),
        dict(id='TK-TH-01', item='active refrigeration: cryocooler cold heads, He-3 and H2 refrigeration', bucket='radiator_thermal',
             count=n('refrigeration_frame'), volume_m3=vol('refrigeration_frame'), screen_t=None),
        dict(id='TK-TH-02', item='heat intercept: He-3 20 K shields', bucket='radiator_thermal', count=sum(1 for p in vessels if p.get('family') == 'HE3'),
             area_m2=round(area['HE3']), volume_m3=None, screen_t=round(area['HE3']*S['he3_shield_kg_m2']/1000, 1)),
        dict(id='TK-TH-03', item='cryogenic exchangers (inside the refrigeration frames: volume counted in TK-TH-01)', bucket='radiator_thermal',
             count=None, volume_m3=None, screen_t=None),
        dict(id='TK-TH-04', item='relief vents, boil-off recovery, purge', bucket='radiator_thermal', count=n('vent_frame'), volume_m3=vol('vent_frame'),
             screen_t=None, function='boil-off and pressure management (thermal)'),
        dict(id='TK-PW-01', item='electrical converters and cables for the cryo plant, pumps and valves', bucket='power_comms', count=None,
             volume_m3=None, screen_t=None, note='no geometry: the 34 power-conversion envelope is the ship\'s, not tankage'),
        dict(id='TK-MS-06', item='structural line supports and manifold brackets in the keel lanes', bucket='main_structure', count=None,
             volume_m3=None, screen_t=None, note='15!A219 C: structural line supports stay main structure; no separate geometry'),
        dict(id='TK-FN-01', item='main-engine D / He-3 / H2 feed pumps, metering / regulating / isolation valves, filters', bucket='drive_package',
             count=n('transfer_pump_frame'), volume_m3=vol('transfer_pump_frame'), screen_t=None,
             function='owner 2026-10-18 (15!A219, 98!A120, 10_WAYFARER_MASS G9): inside the 250 t drive package once, unsized'),
        dict(id='TK-FN-02', item='powered propulsion feed lines (one set per species per lane) and injector / manifold feed interfaces',
             bucket='drive_package', count=n('transfer_manifold'), volume_m3=vol('transfer_manifold'), screen_t=None,
             function='as TK-FN-01; the lane manifold envelope also routes vent (TK-TH-04) and cold-head (TK-TH-01) lines: its volume is '
                      'reported here once, mass is booked by function'),
        dict(id='TK-MARGIN', item='design margin', bucket='design_margin', count=None, volume_m3=None, screen_t=0.0, note='untouched (15!A209)'),
    ]
    for r in rows:
        r['mass_t'] = None; r['status'] = 'UNKNOWN' if r['id'] != 'TK-MARGIN' else 'UNTOUCHED'
    per_bucket = {}
    for r in rows:
        b = per_bucket.setdefault(r['bucket'], dict(bucket_t=BUCKETS_T[r['bucket']], ledger_t=None, ids=[], screen_known_t=0.0))
        b['ids'].append(r['id']); b['screen_known_t'] = round(b['screen_known_t']+(r['screen_t'] or 0.0), 1)
    return dict(rows=rows, per_bucket=per_bucket, screen=SCREEN,
                rule='mass_t null = UNKNOWN (15!A209 G). screen_t is an order-of-magnitude orientation from measured areas and the SCREEN '
                     'densities only: it is not a ledger value, not a PASS and not a budget claim; each bucket already carries the rest of the '
                     'ship, so even a partial screen near a bucket total means the owner must rebalance wet mass before CAD release.')


def screen_all():
    assign = balanced_assign(); c2 = mc.body_c(assign); c1 = mc.body_c()
    return dict(status='WORKING STUDY CHOICE / FUEL QUANTITY OPEN / NO REBUDGET RELEASE (S&E 15!A207:A209, 98!A115)',
                need_m3=mc.liquid_need(), slot_capacity_m3={f: round(v, 1) for f, v in slot_capacity().items()},
                c1=dict(layout='BODY-C module rule (He-3 first, then D2; H2 none)', **coverage(c1)),
                c2=dict(layout='BODY-C2 balanced lobes (separate jacketed vessels, every species housed at about the same fraction)', **coverage(c2),
                        assignment={f'{m}_{int(k)}': f for (m, k), f in sorted(assign.items())}),
                free_volume=dict(c2=free_volume(c2)), interfaces=interfaces(c2, assign), ledger=ledger(c2),
                shortfall_bars=c2['shortfall_bars']), c2


def main(asset=False):
    res, c2 = screen_all()
    if asset:
        res['asset_objects'] = len(mc.build_asset(dict(body_c=c2), ASSET, COLLECTION, 'm5_body_c2',
                                                  'WORKING STUDY CHOICE / FUEL QUANTITY OPEN (15!A207:A209): balanced separate-species layout'))
        res['overlap'] = mc.overlap_screen(None, 'studies/WF_STUDY_BODY_C2.blend', COLLECTION)
    elif OUT_JSON.exists():
        old = json.loads(OUT_JSON.read_text()); res.update({k: old[k] for k in ('asset_objects', 'overlap') if k in old})
    OUT_JSON.write_text(json.dumps(res, indent=1)+'\n')
    for k in ('c1', 'c2'):
        print(k, {q: res[k][q] for q in ('capacity_m3', 'first_ignition_fraction', 'housed_first_ignition_m3', 'first_ignition_deficit_m3',
                                         'full_load_deficit_m3', 'housed_mass_t', 'housed_mass_total_t', 'aggregate_fraction')})
    print('assignment', res['c2']['assignment'])
    print('free', json.dumps(res['free_volume']['c2']))
    print('interfaces', json.dumps(res['interfaces']))
    for r in res['ledger']['rows']:
        print(' ', r['id'], r['bucket'], r.get('count'), r.get('volume_m3'), r.get('area_m2'), r['screen_t'])
    print('buckets', res['ledger']['per_bucket'])
    if 'overlap' in res:
        print('overlap', res['overlap']['study_parts'], len(res['overlap']['conflicts']), [ (c['study'], c['other']) for c in res['overlap']['conflicts'][:6]])
    return res


if __name__ == '__main__':
    argv = sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else sys.argv[1:]
    ap = argparse.ArgumentParser(); ap.add_argument('--asset', action='store_true')
    main(ap.parse_args(argv).asset)
