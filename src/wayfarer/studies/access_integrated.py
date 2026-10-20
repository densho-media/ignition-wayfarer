"""ACCESS-005 / SIM-025 / OD-040 (owner 2026-10-11 16:45, S&E 15!A164): the integrated rescue + pressure + stationary-access study.
Pure, writes JSON and Markdown, never edits canon or geometry.

The owner asked for one architecture study across ring B -> trunk -> refuge, SP-11/12/13 and L1-A instead of widening ports one at a time.
This module does not measure anything itself. It composes the measured segment results of the disposable studies (each writes
references/p1_access_seg_*.json with one schema) into:
  1. route chains per architecture and ship state, each the WORST segment on it (RINGB-006: minimum over pose families, body sizes,
     injury classes, rescuers, kit, doors and seeds, as each study reports it);
  2. the sector coverage matrix (RINGB-007: medically appropriate care and refuge access in 0 g, spin, stopped and locked 1.5 g; no ring
     re-index at 1.5 g, CALC-R05);
  3. the closure family matrix (CLOSURE-005): every closure of the ECLSS-REC2 survey sorted into reversible seated/dogged, a pair in
     series, or a dual (independent second) closure, with the ideal 80 kPa load in both directions (CALC-R02 method). Nothing is qualified.

Architectures (ACCESS-005):
  A  dedicated rescue-capable transfer interface: ring B port (G1 1.10 m comparison / 0.20 m reference guards), trunk ladder 300 deg,
     refuge entry +20 deg with the 1.00 x 2.30 m slot, SP-11 1.20 m -> SP-12 -> trunk, SP-13 independent exit, L1-A protected route.
  B  equivalent distributed protection: a protected care/stabilisation point in every occupied sector, used whenever a transfer chain of
     A does not pass in that state; the EVA district chains stay as in A.

Status bands: PASS >= 0.05 m, MARGINAL 0..0.05, FAIL < 0; a chain is FAIL if any segment fails, else OPEN if any is unmeasured, else
MARGINAL if any is marginal. Targets are never widened.

    python3 src/wayfarer/studies/access_integrated.py
"""
from pathlib import Path
import json
import sys
ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT/'src/wayfarer')]
from spec import load

STATES = ('0g', 'spin', 'stopped', 'locked_1.5g')
RANK = {'FAIL': 0, 'OPEN': 1, 'MARGINAL': 2, 'PASS': 3}
OUT_JSON = ROOT/'references/p1_access_integrated.json'
OUT_MD = ROOT/'references/ACCESS_INTEGRATED_2026-10-11.md'

# Route chains of architecture A. Each chain is a list of design elements; an element filters segments (route key, case-insensitive substring)
# and names the design candidate a segment belongs to (cand). A candidate is one coherent option (a ring B port variant, an SP-11 keeper
# variant, a hoist line/rail option); a segment whose cand is None applies to every candidate of that element. Per element and state the
# best candidate is chosen (its worst segment); the chain is the worst element. Options of different elements are assumed independent.
def _r(*keys):
    return lambda g: any(k in g['route'].lower() for k in keys)


def _pre(*codes):
    return lambda g: g['variant'] if g['variant'].split('_')[0].startswith(codes) else None


def _closure(g):
    i = g['id']
    if i.startswith('A170-SP13-CLOSURE-'):
        return i.split('-OP-')[0][len('A170-SP13-CLOSURE-'):]
    if i.startswith('A178-SP13-LEAF-'):
        return 'A178:' + i[len('A178-SP13-LEAF-'):].replace('-OUTER-ACCESS', '')
    return None


def _hoist_option(g):
    return '|'.join(g['id'].split('|')[:-1])          # line angle, offset and rail; the last token is the casualty class


CHAINS = {
    'A': [
        ('ringB_to_refuge', 'ring B sector -> port -> trunk -> hoist -> refuge slot 1.00 x 2.30 m', [
            ('ring B port variant', _r('ringb_b2->trunk', 'ringb_spin_port_turn', 'trunk->refuge'), lambda g: g['variant']),
            ('hoist line / rail', _r('hoist'), _hoist_option)]),
        ('ringB_care', 'ring B sector -> B2 medical couch', [
            ('ring B port variant', _r('b1->b2', 'b3->b2', 'ringb_b2->couch'), lambda g: g['variant'])]),
        # owner 2026-10-13 (15!A169): ring A is the comparator; the worst-case re-run (RINGB-006) replaces the single-seed built_A quote
        ('ringA', 'ring A sector -> A2 couch / trunk (stop/index, worst case 2026-10-13)', [
            ('ring A as built, worst case', _r('ringa-wc:'), lambda g: None)]),
        ('eva_sp11_sp12', 'SP-11 1.20 m plug -> SP-12 -> trunk (casualty)', [
            ('SP-11 keeper', lambda g: g['id'].startswith('SP11.keeper') or g['id'].startswith('SP11.plug'), _pre('KP')),
            ('SP-11 aperture', lambda g: g['id'].startswith('SP11.aperture') and '1.35' not in g['id'], lambda g: None),
            ('SP-11 chamber controls', lambda g: g['id'].startswith('SP11.controls'), lambda g: None),
            ('SP-12 control cluster', lambda g: g['id'].startswith(('SP12.control', 'SP12.operator')), _pre('CT')),
            # owner 2026-10-13 (15!A170): N1 rejected; the SP-12 exit is one of the N2 / N0 / N3 studies (A170-SP12-*)
            ('SP-12 exit (N1 rejected)', lambda g: g['id'].startswith('A170-SP12-') and not g['id'].endswith('-VS-SP13'), lambda g: g['variant']),
            # owner 2026-10-13 (15!A176): N2 fwd45 is the next reversible comparison; complete litter route, opposite side, single fault
            ('N2 fwd45 complete route and opposite side', lambda g: g['id'].startswith(('A176-SP12-N2FWD45-E2E-', 'A176-SP12-N2FWD45-OP-')), lambda g: None),
            ('N2 fwd45 single fault', lambda g: g['id'].startswith('A176-SP12-N2FWD45-SF-'), lambda g: None)]),
        ('eva_sp13', 'SP-13 independent second exit (fit-out kept; the 1.20 m and bare-room rows are comparisons)', [
            ('SP-13 exit and fit-out', lambda g: g['id'].split('-')[0] == 'SP13' and g['id'].rsplit('-', 1)[-1] in ('A', 'S', 'K', 'U')
             and g['id'].split('-')[1] in ('CTRL', 'RADREARR', 'SEL'), lambda g: g['id'].split('-')[1]),
            ('service capability kept', lambda g: g['id'].startswith('SP13-SERVICE'), lambda g: None),
            # owner 2026-10-13 (15!A170): hinged positively dogged leaf or dual isolation, not the sliding leaf (SP13-POCKET); 80 kPa OPEN
            # owner 15!A178: the aft hinged dogged leaf is preferred; the A178 rows add small partition / mount / side-wall moves and outer-leaf access
            ('exit closure (hinged dogged / dual)', lambda g: g['id'].startswith(('A170-SP13-CLOSURE-', 'A170-SP13-DP80-', 'A178-SP13-')), _closure),
            ('independent of SP-12 (N1 rejected)', lambda g: g['id'].endswith('-VS-SP13') or g['id'] in ('SP13-INDEP-PARTITION', 'SP13-VEHICLE'),
             lambda g: None),                         # every SP-12 variant at once: conservative, the chains are not linked
            # owner 15!A177: one SP-12 fault must not obstruct SP-13; failure tree of the shared extension and the SP-12 hoist anchors
            ('SP-12 faults in the shared extension', lambda g: g['id'].startswith(('A177-SP13-N2_fwd45_', 'A177-SP13-no_fault_N2_fwd45-'))
             or g['id'] in ('A177-SP13-OUTER-LEAF-ACCESS', 'A177-ISOLATION') or g['id'].startswith('A176-SP12-N2FWD45-HOIST-'), lambda g: None)]),
        ('district_l1a', 'L1-A district / Dock_Primary protected 1.5 g route', [
            # owner 2026-10-13 (15!A171): the district port moves to 205-215 deg (reversible WHITEBOX); tether fall load OPEN
            # owner 15!A179: the stile / bracket at Crew_Port_2_2 may be repositioned (PROTOTYPE, no cut); candidates cover their port range
            ('district port 205-215 deg + stile', lambda g: g['id'].startswith('A179-L1A-STILE-') or g['id'] == 'A171-L1A-TETHER-FALL',
             lambda g: g['id'].split('-')[3] if g['id'].startswith('A179-') else None),
            ('dock bridge', lambda g: g['id'] == 'DOCK-BRIDGE', lambda g: None),
            ('SP-52 containment (heat transfer OPEN)', lambda g: g['id'].startswith('SP52-'), lambda g: g['id'] if g['id'].startswith('SP52-CONT') else None)]),
        # owner 2026-10-13 (15!A171, A180): B3H2 (tsh2.*: dog-legged recessed rail, deck-side grip brackets, link <= 0.206 m); B3S (tsb.*) and
        # B3H (tsh.*) stay as history
        ('thrust_hatch_step', 'thrust hatch step B3H2 (tube -> sector under thrust)', [
            ('B3H2 rigs, both hands (grip always taken / released where it costs clearance)', lambda g: g['id'].startswith('tsh2.') and '.body.' in g['id'],
             lambda g: g['id'].split('.')[-1]),
            ('B3H2 parts', lambda g: g['id'].startswith('tsh2.') and '.part.' in g['id'], lambda g: None),
            ('single-hand sequence', lambda g: g['id'].startswith('tsh2.') and '.sequence.' in g['id'], lambda g: None),
            # the rail carries the arrest link, so only 'all hardware' or 'without the handgrip' are coherent options
            ('carriers past the handgrip', lambda g: g['id'].startswith('tsh2.carrier.') and g['id'].split('.')[-1] in ('all_study_hardware', 'without_handgrip'),
             lambda g: g['id'].split('.')[-1]),
            ('leaf sweep and guide', lambda g: g['id'].startswith('tsh2.leaf'), lambda g: None),
            ('arrest link, 0 g feet-free', lambda g: g['id'].startswith('tsh2.') and ('arrest_link' in g['id'] or 'feet_free' in g['id']), lambda g: None)]),
    ],
}


def seg_files():
    return sorted(ROOT.glob('references/p1_access_seg_*.json'))


def segments():
    out, src = [], []
    for f in seg_files():
        d = json.loads(f.read_text()); src.append(f.name)
        for s in d.get('segments', []):
            s = dict(s); s['file'] = f.name
            if s.get('status') not in RANK:
                s['status'] = 'OPEN'
            out.append(s)
    return out, src


def worst(statuses):
    return min(statuses, key=lambda s: RANK[s]) if statuses else 'OPEN'


def _key(g):
    return (RANK[g['status']], g['least_m'] if g.get('least_m') is not None else 9.0)


def element(flt, cand, segs, state):
    hit = [g for g in segs if flt(g) and state in (g.get('states') or STATES)]
    if not hit:
        return dict(status='OPEN', candidate=None, worst=None, candidates={})
    fixed = [g for g in hit if cand(g) is None]; opts = {}
    for g in hit:
        c = cand(g)
        if c is not None:
            opts.setdefault(c, []).append(g)
    if not opts:
        opts = {'(single)': []}
    res = {}
    for c, gs in opts.items():
        w = min(gs+fixed, key=_key); ms = [g['least_m'] for g in gs+fixed if g.get('least_m') is not None]
        res[c] = dict(status=w['status'], least_m=w.get('least_m'), worst_id=w['id'], file=w['file'], least_measured_m=min(ms) if ms else None)
    best = max(res, key=lambda c: (RANK[res[c]['status']], next((v for v in (res[c]['least_m'], res[c]['least_measured_m']) if v is not None), -9.0)))
    return dict(status=res[best]['status'], candidate=best, worst=res[best], candidates=res)


def chain(elements, segs, state):
    els = {name: element(flt, cand, segs, state) for name, flt, cand in elements}
    return dict(status=worst([e['status'] for e in els.values()]), elements=els)


def closures(s):
    d = json.loads((ROOT/'references/p1_eclss_rec2.json').read_text()); kpa = d['cabin_pressure_kpa']
    comp = {c['closure']: c['compliant_today'] for c in d['owner_disposition']['closures']}
    rows = []
    for c in d['survey']:
        n, f = c['name'], c['family']
        if 'Refuge' in n or 'SP-12 branch' in n:
            cls, why = 'DUAL', 'owner 12:34a / CLOSURE-005: an independent second closure where the fault layout needs it (refuge, SP-12 branch)'
        elif f.startswith(('F2', 'F4')):
            cls, why = 'PAIR_IN_SERIES', 'two closures already in series (drum door + tube hatch, dock outer + inner); each still needs a positive reverse path'
        else:
            cls, why = 'REVERSIBLE_SEATED_DOGGED', 'one closure: seated by its normal side, positive dogs/keepers for the reverse polarity'
        load_kn = c.get('reverse_load_kN')
        rows.append(dict(closure=n, family=f, sides=[c['a'], c['b']], seats_from=c['seats_from'], architecture=cls, why=why,
                         load_each_direction_kN=load_kn, compliant_today=comp.get(n), held_today=c['held_today'], status=c['status'],
                         qualification='NOT QUALIFIED (OD-034, 45 I-24 OPEN)'))
    od = s['owner_diagnostics']
    proposed = [dict(closure='Refuge axial slot 1.00 x 2.30 m (STUDY)', architecture='DUAL', load_each_direction_kN=od['refuge_slot_1_00x2_30_force_N']/1e3, source='45 I-12'),
                dict(closure='SP-12 N1 axial slot 1.10 x 2.50 m (STUDY comparator)', architecture='DUAL', load_each_direction_kN=od['n1_slot_1_10x2_50_force_N']/1e3, source='45 I-13'),
                dict(closure='Ring B port 1.10 m (STUDY comparison)', architecture='PAIR_IN_SERIES', load_each_direction_kN=round(od['ringb_port_d1_10_force_N']/1e3, 1), source='45 I-11'),
                dict(closure='SP-11 inner plug 1.20 m (STUDY lead)', architecture='REVERSIBLE_SEATED_DOGGED', load_each_direction_kN=round(od['sp11_leaf_d1_30_force_N']/1e3, 2), source='45 I-08')]
    fam = {}
    for r in rows:
        fam.setdefault(r['architecture'], dict(count=0, non_compliant=0, max_load_kN=0.0, closures=[]))
        e = fam[r['architecture']]; e['count'] += 1; e['non_compliant'] += r['compliant_today'] is False; e['closures'].append(r['closure'])
        e['max_load_kN'] = max(e['max_load_kN'], r['load_each_direction_kN'] or 0.0)
    return dict(cabin_pressure_kpa=kpa, method='ideal clear/leaf area x 80 kPa, the same in both directions (CALC-R02); DIAGNOSTIC, no rating',
                survey=rows, proposed=proposed, families=fam, non_compliant=sum(r['compliant_today'] is False for r in rows), total=len(rows))


def coverage(segfiles):
    for f in segfiles:
        d = json.loads((ROOT/'references'/f).read_text())
        if 'sector_coverage' in d:
            return d['sector_coverage'], d.get('distributed_alternative'), f
    return {}, None, None


def run():
    s, *_ = load(ROOT)
    segs, src = segments()
    arch_a = {cid: dict(title=t, states={st: chain(els, segs, st) for st in STATES}) for cid, t, els in CHAINS['A']}
    cov, dist, cov_src = coverage(src)
    # ring A sectors: the stored matrix predates the worst-case re-run; their transfer access is the ringA chain (owner 2026-10-13)
    cov = {sec: {st: (worst([v, arch_a['ringA']['states'][st]['status']]) if sec.startswith('Sector_1_') and st in STATES else v)
                 for st, v in row.items()} for sec, row in cov.items()}
    # B: care at the in-sector protected point where the A chain is not PASS (deck frame for 0 g / spin / stopped, aft frame under thrust);
    # refuge access is unchanged (the ringB_to_refuge chain), so B is a care-only alternative (RINGB-007).
    care = {g['id']: g for g in segs if g['id'].startswith('care|')}      # owner 2026-10-13 (15!A169) in-sector care, worst case
    arch_b = {}
    for sec, row in cov.items():
        d = ((dist or {}).get('by_sector') or {}).get(sec, {})
        arch_b[sec] = {}
        r_, k_ = sec.split('_')[1:3] if sec.count('_') >= 2 else (None, None)
        tag = f"{'AB'[int(r_)-1]}{k_}" if r_ in ('1', '2') else None
        for st in STATES:
            a = row.get(st, 'OPEN'); frame = 'aft' if st == 'locked_1.5g' else 'deck'
            # owner 15!A173:A174: the 1.5 g aids (o13-V1..V3) and the local care-point changes are options; the best one counts
            # Garden (A3/B3): the earlier results needed Garden_Rack_1 removed, which A174 / H174 do not allow; only the canon rack and the
            # emergency rack stowage variants (o13c-*) count (2026-10-13c)
            garden = tag in ('A3', 'B3')
            opts = [g for k, g in care.items() if (not garden and (k == f'care|{tag}|{frame}' or k.startswith(f'care|{tag}|{frame}|o13-')))
                    or (garden and k.startswith(f'care|{tag}|{frame}|o13c-'))]
            g = max(opts, key=lambda g: (RANK[g['status']], g['least_m'] if g['least_m'] is not None else -9.0)) if opts else None
            if g is not None:
                local = g['status']
            else:
                f_ = d.get(frame, {}); local = f_.get('status', 'OPEN') if f_.get('reachable_by_0_60_path', True) else 'FAIL'
            arch_b[sec][st] = a if RANK.get(a, 1) >= RANK.get(local, 1) else local
    tally = lambda m: {k: sum(1 for r in m.values() for st in STATES if r.get(st) == k) for k in RANK}
    # owner 2026-10-17 (15!A197 OWN-RES, 98!A109): under locked 1.5 g no planned nonambulant transfer; the casualty is restrained and stabilized
    # at the rated burn couch and moved only after a safe thrust reduction/termination. A disposition, never a clearance: no status is raised.
    rule = {sec: {st: ('STABILIZE_AT_BURN_COUCH (no transfer; thrust reduction first; hold time, trigger and clinical capacity HOLD)'
                       if st == 'locked_1.5g' else ('TRANSFER_STUDY' if RANK.get(row.get(st), 1) < RANK['PASS'] else 'TRANSFER'))
                  for st in STATES} for sec, row in cov.items()}
    return dict(
        study='ACCESS-005 integrated rescue + pressure + stationary access (S&E 15!A164, OD-040, 47 SIM-025)',
        status='NONCANON DISPOSABLE STUDY; PRIORITY DESIGN STUDY / NO HULL CUTOUT; no closure, port, guard, pin, rail or room released',
        owner_rules=['worst case over pose families, body sizes, injury classes, two rescuers, kit, doors, seeds (RINGB-006)',
                     'every occupied sector: care + refuge access in 0 g / spin / stopped / locked 1.5 g; no 1.5 g re-index (RINGB-007, CALC-R05)',
                     'positive bidirectional closures, dual closure only where the fault layout needs it (CLOSURE-005, PRESS-004)',
                     'study target >= 0.05 m, never widened',
                     'locked 1.5 g: restrain and stabilize at the rated burn couch, no routine transfer (15!A197 OWN-RES-2026-10-17, 98!A109); Garden_Rack_1 stays',
                     'ring A is not a passing comparator; B3H2 arrest links <= 0.206 m, 0.207-0.213 m only as unapproved sensitivity (15!A198)'],
        segment_sources=src, segments=len(segs),
        architecture_A=arch_a,
        sector_coverage=dict(source=cov_src, A=cov, B=arch_b, tally_A=tally(cov) if cov else None, tally_B=tally(arch_b) if arch_b else None),
        operating_rule_1_5g=dict(source='S&E 15!A197 OWN-RES-2026-10-17, 98!A109', status='SELECTED WORKING RULE / CLINICAL + FLIGHT PROCEDURE HOLD', by_sector=rule),
        distributed_alternative=dist,
        closures=closures(s))


REVIEW_17 = """## Owner resolution 2026-10-17 (S&E 15!A197:A199, 98!A109:A110)

- (r1-A) Locked 1.5 g: no routine transfer of a nonambulant casualty; local burn-couch stabilization, transfer after a safe thrust reduction.
  The coverage tables keep their measured status; the rule is shown as a disposition (operating_rule_1_5g), never as a PASS.
- (r2-A) Ring A stays FAIL as a comparator (A1 -0.103 / -0.171 m, spin turn -0.140 / -0.455 m); its port and spin-port turn are the subject of
  a reversible L2 whitebox with the same worst-case swept-casualty method (references/RINGA_PORT_WHITEBOX_2026-10-17.md).
- (r3) B3H2 links stay <= 0.206 m (current study limit); 0.207-0.213 m are unapproved sensitivity cases. Stop distance and angle, dynamic peak
  force, injury thresholds and anchor/tether ratings stay OPEN.
- (g1-g3) SP-13: the side gallery to the refuge is the preferred L2 topology study (no cutout, no installed pressure facility); the suited
  casualty +0.021 m stays MARGINAL, not PASS.
"""


REVIEW_13B = """## Review after the owner's second 2026-10-13 answers (S&E 15!A173:A180; Claude, numbers from the tables above)

The chains add the A176-A180 studies: the SP-12 N2 fwd45 complete route, opposite side and single faults; the SP-13 leaf moves and the
failure tree of the shared extension; the L1-A stile candidates; the thrust step as B3H2; the 1.5 g aids and local care-point changes as
options of architecture B.

1. **Still no chain passes in any state**; architecture B stays 6 of 24. The best 1.5 g aid (V3 wall jib) reaches Garden -0.066 m (and only
   with the PROTOTYPE rack swap), Medical -0.140 m, Habitation -0.220 m; the medical couch with a folded foot plate passes unsuited (+0.066 m)
   but not suited (-0.031 m).
2. **SP-13 is not independent of SP-12**: an SP-12 carrier jammed on the shared extension axis blocks the SP-13 route (-0.373 m), and the
   outer SP-13 leaf access fails with an SP-12 carrier in the extension (-0.021 m). The one separating layout studied (N2 aft30) fails its own
   carriers (-0.134 m). The 1.5 g SP-12 lift is 2.63 m, not 1.1 m.
3. **L1-A clears**: stile candidate CB2J6 (0.02 m outward + 6 deg, both windows, no cut) +0.064 m over the full route at ports 205/210 deg
   (CB2J6DP adds 215 deg); the chain stays OPEN on loads (tether fall, S-bends, brackets).
4. **B3H2** lifts the instructor and test_a thigh margins with links <= 0.206 m; the newcomer K0 arm stays MARGINAL +0.049 m (top landing
   rung), the always-held grip MARGINAL +0.030 m at K4; arrest loads and the leaf guide OPEN.
"""


REVIEW_13 = """## Review after the owner's 2026-10-13 answers (S&E 15!A169:A172; Claude, numbers from the tables above)

The chains now follow the answers: ring A at the worst-case re-run, SP-12 without N1, the SP-13 hinged dogged leaf or dual isolation, the
L1-A port at 205-215 deg, the thrust step as B3H, and architecture B from the in-sector care study.

1. **No chain passes in any state.** Ring A, the comparator, now fails as well: -0.171 m (suited, 0 g) to -0.455 m (spin port turn).
2. **Distributed care (architecture B) covers 6 of 24 sector states**: only the Garden sectors at 0 g / spin / stopped (fold-down
   couch, +0.075 m). Every locked 1.5 g state and the medical / habitation care points fail.
3. **EVA district.** SP-12 is MARGINAL at best (N2 forward 45 deg, +0.044 m over six seeds), but the chain still fails on the limp
   casualty through SP-11 (-0.099 m). SP-13: the exit route itself is MARGINAL 0.000 m for the suited casualty (2026-10-11), the aft-hinged
   leaf MARGINAL (+0.016 m); the 80 kPa rating is OPEN, so the chain is OPEN.
4. **L1-A** is MARGINAL +0.018 m at every port angle (the built stile at Crew_Port_2_2), OPEN for the tether fall load.
5. **B3H** clears both carriers; the rigs stay MARGINAL (+0.035 m when the right hand lets go where the grip costs clearance, +0.014 m
   for the parts when the grip is always held); the 0 g feet-free pose and arrest loads are OPEN.

The owner reply is drafted in references/RESCUE_REPLY_2026-10-13.md.
"""

REVIEW = """## Review of the 2026-10-11 run (Claude; numbers from the tables above)

1. **No transfer chain of architecture A passes in any state.** Ring B fails for every port variant: the best, G1, is -0.135 m for the
   suited casualty to the trunk and -0.245 m on the annulus to the B2 couch. The spin port turn is -0.42 m. The unsuited classes fail
   too (-0.014 to -0.116 m). Widening the ring B port to 1.10 m does not close the route; this supports ACCESS-005's premise.
2. **Ring A stop/index is the only nearly working transfer.** It PASSes in 0 g and is MARGINAL (+0.031 m, the kit attendant) when
   stopped or locked; it FAILs while spinning. These are the existing single-seed built_A numbers, not the new worst-case method.
3. **The distributed care point (architecture B) covers care in 16 of 24 sector-states.** It fails in the garden sectors (B3 FAIL; A3
   MARGINAL or FAIL), where no couch fits (-0.20 m). It gives care only: refuge from ring B still needs the failing transfer.
4. **EVA district.**
   - The SP-11 keeper (0.10 m stroke, thin recessed lugs, +0.088 m) and the SP-12 control row (+0.070 m) pass as studies.
   - The casualty geometry does not pass: the limp unrestrained casualty is -0.099 m at 1.20 m, and the best SP-12 suited turn is
     -0.091 m.
   - The SP-13 exit route reaches 0.000 m for S, but its sliding closure does not fit the room (-0.877 m).
   - SP-13 overlaps the SP-12 N1 slot (-0.400 m). N1 and the only workable SP-13 exit are mutually exclusive.
5. **L1-A.** Moving the district port to 205-215 deg keeps one continuous protected ladder, at the built ladder's own +0.018 m margin.
   Moving the ladder to 305-330 deg fails: it crosses the refuge port.
6. **B3S.** Boot and hand clearances pass for every rig; the thighs (+0.035 / +0.039 m) and the newcomer's arm (+0.049 m) stay
   MARGINAL. The grab post blocks the suited carrier (-0.009 m), which clears by +0.19 m without it.
7. **Closures.** 31 of 32 have no qualified two-way load path: 14 are pairs in series, 16 single reversible closures, 2 dual. All
   are unqualified.

**Decisions this needs (owner):**
- (a) ring B: a rescue-capable transfer interface beyond the studied envelopes, or distributed care plus refuge protection with a
  garden-sector care point;
- (b) the SP-12 exit: N1 (it blocks SP-13) or N0/N2/N3;
- (c) the SP-13 closure type;
- (d) L1-A port at 205-215 deg;
- (e) drop the B3S grab post;
- (f) SP-52 thermal inputs for the heat-transfer model.
"""


def md(r):
    L = [f"# Integrated rescue, pressure and access study (ACCESS-005, 2026-10-11; chains updated to the owner's 2026-10-13 answers)", '',
         f"{r['status']}. Owner: S&E 15!A164 ACCESS-005, 15!A159:A162, 09 OD-034/OD-040, 47 SIM-025. Code `src/wayfarer/studies/access_integrated.py`,",
         f"result `references/p1_access_integrated.json`. It composes {r['segments']} measured segments from: "+', '.join(f'`{x}`' for x in r['segment_sources'])+'.', '',
         'Rules: '+'; '.join(r['owner_rules'])+'.', '', '## Architecture A (dedicated rescue-capable transfer interface): worst segment per chain and state', '',
         '| Chain | '+' | '.join(STATES)+' | Chosen candidates |', '| --- |'+' --- |'*(len(STATES)+1)]
    for cid, c in r['architecture_A'].items():
        cells = []
        for st in STATES:
            x = c['states'][st]
            ms = [e['worst']['least_measured_m'] for e in x['elements'].values() if e['worst'] and e['worst'].get('least_measured_m') is not None]
            cells.append(x['status'] + (f" {min(ms):+.3f}" if ms else ''))
        pick = {}
        for st in STATES:                     # label from the first state with a measured choice (0 g first)
            for n, e in c['states'][st]['elements'].items():
                if e['candidate'] and n not in pick:
                    pick[n] = e['candidate']
        L.append(f"| {c['title']} | "+' | '.join(cells)+' | '+('; '.join(f'{n}: {v}' for n, v in pick.items()) or 'no measured segment')+' |')
    L += ['', 'Cells: chain status (OPEN when any element is unmeasured, e.g. a load) and the least measured clearance on the chain (m). Chosen: the best candidate of each element in the first state that measures it; \"(single)\" = no alternatives studied.']
    L += ['', '### Elements (0 g and locked 1.5 g)', '', '| Chain | Element | Chosen | 0 g | locked 1.5 g | Governing segment |', '| --- | --- | --- | --- | --- | --- |']
    for cid, c in r['architecture_A'].items():
        for n in c['states']['0g']['elements']:
            e0, e1 = c['states']['0g']['elements'][n], c['states']['locked_1.5g']['elements'][n]
            f = lambda e: e['status'] + (f" {e['worst']['least_m']:+.3f}" if e['worst'] and e['worst'].get('least_m') is not None else '')
            w = (e0['worst'] or e1['worst'] or {}).get('worst_id', '')
            L.append(f"| {cid} | {n} | {e0['candidate'] or e1['candidate'] or ''} | {f(e0)} | {f(e1)} | `{w}` |")
    cov = r['sector_coverage']
    if cov['A']:
        L += ['', '## Sector coverage (care + refuge access)', '', f"Source `{cov['source']}`. A: care and refuge access through the transfer chain (the study's worst of both). B: A, else care at the "
              f"in-sector protected point (deck frame in 0 g / spin / stopped, aft frame under thrust); B does not add refuge access.", '',
              '| Sector | '+' | '.join(f'A {s}' for s in STATES)+' | '+' | '.join(f'B {s}' for s in STATES)+' |', '| --- |'+' --- |'*(2*len(STATES))]
        for sec in cov['A']:
            L.append(f"| {sec} | "+' | '.join(cov['A'][sec].get(s, 'OPEN') for s in STATES)+' | '+' | '.join(cov['B'][sec][s] for s in STATES)+' |')
        L += ['', f"Tally A {cov['tally_A']}; B {cov['tally_B']}."]
        L += ['', "Owner 2026-10-17 (15!A197): in every sector the locked 1.5 g state is handled by the operating rule, not by a transfer: restrain and "
              "stabilize at the rated burn couch, reduce or end thrust when safe, then transfer. The rule raises no cell above; hold time, reduction "
              "trigger, burn interruption and local clinical capacity stay owner/medical HOLD. Ring B in-sector care stays 0/24 with the canonical Garden rack."]
    c = r['closures']
    L += ['', '## Closure families (CLOSURE-005)', '', f"{c['method']}. Non-compliant today: {c['non_compliant']} of {c['total']} (no qualified two-way load path).", '',
          '| Architecture | Closures | Non-compliant | Max ideal load each way (kN) |', '| --- | --- | --- | --- |']
    for k, e in c['families'].items():
        L.append(f"| {k} | {e['count']} | {e['non_compliant']} | {e['max_load_kN']:.1f} |")
    L += ['', 'Proposed study openings (owner 45 I-08/I-11..I-13): '+'; '.join(f"{p['closure']} {p['load_each_direction_kN']:.1f} kN ({p['architecture']})" for p in c['proposed'])+'.',
          '', 'Every closure stays unqualified (OD-034, 45 I-24 OPEN); no hatch is moved or retrofitted (CLOSURE-005).', '', REVIEW_17, REVIEW_13B, REVIEW_13, REVIEW]
    return '\n'.join(L)


if __name__ == '__main__':
    r = run()
    OUT_JSON.write_text(json.dumps(r, indent=1)+'\n')
    OUT_MD.write_text(md(r))
    for cid, c in r['architecture_A'].items():
        print(f"{cid:20s}", ' '.join(f"{st}:{c['states'][st]['status']}" for st in STATES))
    print('closures', {k: (e['count'], e['non_compliant']) for k, e in r['closures']['families'].items()})
    print(OUT_JSON, OUT_MD)
