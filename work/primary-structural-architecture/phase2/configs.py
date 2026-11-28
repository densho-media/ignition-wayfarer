"""PSA Phase II configuration-specific mass distributions (P production, F1 ISSA Track F reference, R ISSA Track R) and their
propellant-depletion histories. Configurations are never mixed: each returns its own placed parts, thrust and datums.

Sources (read only):
  P  - main mass_model (src/wayfarer/mass_model.py) at the PSA base commit.
  F1 - ISSA 3D integration Checkpoint 4 (claude/cloud/ship-systems-architecture 9faee26): i3d_ledger.json (departure, propellant,
       tankage, end mass), i3d_masterplan.json (item X ranges), i3d_remaining.json (T-A farm stretch, cryocoolers), i3d_logistics.json.
       ISSA SSI-1.0 (structure handover file, in preparation) will replace this placement; ISSA_REF names the commit used.
  R  - ISSA Phase VI phase6.json (nominal case); R has no 3D layout yet, so its farm stretch is scaled from F1 by propellant mass
       (PROTOTYPE) and flagged.
Primary structure (main_structure, 150 t) is removed from the placed parts: PSA supplies it from the sized FE model (STRUCT_KEY).
"""
import json
import subprocess
import sys
from pathlib import Path

H = Path(__file__).resolve().parent
ROOT = H.parents[2]
sys.path.insert(0, str(ROOT / 'src' / 'wayfarer'))
import mass_model as mm  # noqa: E402
import spec  # noqa: E402

ISSA_REF = '9faee26'
ISSA_DIR = 'work/ship-systems-architecture/results'
G0 = 9.80665
THRUST_N = 21.770763e6           # power-limited flight thrust of the studied drive (P, F1, R share the drive); not universal (D01)
CANON_DESIGN_THRUST_N = 29.41995e6   # 07!A2 historical reference (D01)
STRUCT_KEY = ('main_structure', 'main_structure@ring_A', 'main_structure@ring_B')
FARM_P = (109.25, 137.85)


def issa(name, ref=ISSA_REF):
    return json.loads(subprocess.check_output(['git', 'show', f'{ref}:{ISSA_DIR}/{name}'], cwd=ROOT))


_S = None


def S():
    global _S
    if _S is None:
        _S = spec.load(ROOT)[0]
    return _S


def part(name, m_kg, x0, x1, r=3.0, cls='', owner=''):
    p = mm._part(name, m_kg, x0, x1, ['cyl', r]); p['cls'] = cls; p['owner'] = owner; p['r'] = r
    return p


def _radius(p):
    return p.get('r', 3.0)


def prod_dry(shift_fwd=0.0, stretch_from=FARM_P[1]):
    """Production dry parts without the primary structure. Parts at or ahead of stretch_from move forward by shift_fwd (T-A)."""
    out = []
    for p in mm.dry_parts(S()):
        if p['name'] in STRUCT_KEY:
            continue
        x0, x1 = p['x']
        if p['name'].startswith('tankage_'):
            continue                                   # tankage is placed per configuration
        if x0 >= stretch_from-8.0 and shift_fwd:
            x0, x1 = x0+shift_fwd, x1+shift_fwd
        q = part(p['name'], p['m'], x0, x1, r=5.0 if 'shield' in p['name'] else 3.0, cls='PRODUCTION', owner=p['name'].split('@')[0])
        out.append(q)
    return out


def prod_tankage():
    return [p for p in mm.dry_parts(S()) if p['name'].startswith('tankage_')]


def prop_pattern(left, farm=FARM_P, scale=1.0):
    """Production propellant parts with `left` of the mission propellant aboard, stretched onto `farm` and scaled."""
    st = mm.stores_at(S(), left); out = []
    f0, f1 = FARM_P; g0, g1 = farm
    for p in mm.propellant_parts(S(), st['he3'], st['d2'], st['h2'], True):
        a, b = p['x']; a2 = g0+(a-f0)*(g1-g0)/(f1-f0); b2 = g0+(b-f0)*(g1-g0)/(f1-f0)
        out.append(part(p['name'], p['m']*scale, a2, b2, r=12.0, cls='PROPELLANT', owner='propellant'))
    return out


def config(name, left=1.0, g_aft=0.0):
    """Placed parts for configuration name at `left` (1 = departure, 0 = all mission propellant used). Returns a dict with parts,
    thrust, datums (farm, Brow) and bookkeeping."""
    if name == 'P':
        st1 = mm.stores_at(S(), 1.0); prop1 = (st1['he3']+st1['d2']+st1['h2'])
        parts = prod_dry() + [part(p['name'], p['m'], *p['x'], r=12.0, cls='TANKAGE', owner='tankage') for p in prod_tankage()] + prop_pattern(left)
        return dict(name='P', id='PRODUCTION main 11f1e94', parts=parts, thrust=THRUST_N, farm=FARM_P, brow=(138.15, 144.75),
                    fwd=144.75, propellant_full_t=prop1/1e3, note='production mass model; primary structure from the FE model')
    if name == 'F1':
        led = issa('i3d_ledger.json'); rem = issa('i3d_remaining.json'); mp = issa('i3d_masterplan.json'); lg = issa('i3d_logistics.json')
        farm = tuple(rem['structure']['farm_x']); shift = rem['structure']['added_m']
        parts = prod_dry(shift_fwd=shift)
        xr = {i['item']: i.get('x') for i in mp['ledger']['items']}
        extra_x = {'L2 NaK transport loops + pumps (Stage E)': (-81.6, 40.4), 'L2 section hardware above the Phase VI header line (Stage E)': (41.0, 50.4),
                   'robots, crawlers, MRU carriage + rail (Stage H)': tuple(lg['carriage']['x']), 'body-bay module 10 racks (relocated dry store, Stage H)': (22.25, 33.25),
                   'cryocooler stations (13, T-A area, Stage I)': (farm[1]-1.0, farm[1]), 'distribution above the Phase VI line (Stage F)': (-92.0, 100.0)}
        for it in led['items']:
            x = xr.get(it['item']) or extra_x.get(it['item'])
            if it['t'] <= 0:
                continue
            if x is None:
                raise KeyError(f'no X range for ISSA item {it["item"]}')
            r = 6.5 if it['item'].startswith('hot loop') else (2.9 if it['item'].startswith('L2 (') else 3.5)
            parts.append(part('ISSA:'+it['item'], it['t']*1e3, x[0], x[1], r=r, cls=it['cls'], owner='ISSA'))
        parts.append(part('ISSA:tankage (T-A)', led['tankage_t']*1e3, farm[0], farm[1], r=12.0, cls='ISSA', owner='tankage'))
        scale = led['propellant_t']*1e3/sum(p['m'] for p in prop_pattern(1.0))
        parts += prop_pattern(left, farm, scale)
        if g_aft:
            # Concept G sensitivity (owner D06): move a share of the H2 reaction mass and its tankage share aft into the midbody
            # (X -70..-20, inside the cage around the spine); He-3 and D2 stay forward behind the shield. PROTOTYPE placement only.
            moved = 0.0
            for p in parts:
                if p['cls'] == 'PROPELLANT' and '_H2' in p['name']:
                    dm = p['m']*g_aft; p['m'] -= dm; moved += dm
            parts.append(part('G:H2 aft share', moved, -70.0, -20.0, r=4.0, cls='PROPELLANT', owner='propellant'))
            h2_full = sum(q['m'] for q in prop_pattern(1.0, farm, scale) if '_H2' in q['name'])
            tank_share = led['tankage_t']*1e3*g_aft*h2_full/(led['propellant_t']*1e3)
            for p in parts:
                if p['name'] == 'ISSA:tankage (T-A)':
                    p['m'] -= tank_share
            parts.append(part('G:H2 aft tankage share', tank_share, -70.0, -20.0, r=4.0, cls='ISSA', owner='tankage'))
        placed_end = sum(p['m'] for p in parts if p['cls'] != 'PROPELLANT')/1e3
        return dict(name='F1', id=f'WF-F1-P6.0 at ISSA {ISSA_REF} (CP4 ledger)', parts=parts, thrust=THRUST_N, farm=farm,
                    brow=(138.15+shift, 144.75+shift), fwd=144.75+shift, propellant_full_t=led['propellant_t'],
                    issa_end_t=led['end_t'], placed_end_t_without_structure=placed_end,
                    note='T-A farm and Brow per CP4; ISSA will resize T-A in SSI-1.0 (owner brief): placement provisional')
    if name == 'R':
        p6 = issa('phase6.json', '5eae701'); c = p6['configs']['R']; i = 1
        led = issa('i3d_ledger.json'); rem = issa('i3d_remaining.json')
        prop = c['mass']['propellant_t'][i]; end = c['mass']['end_t'][i]
        L0 = FARM_P[1]-FARM_P[0]; LF1 = rem['structure']['farm_x'][1]-FARM_P[0]
        LR = L0+(LF1-L0)*(prop-sum(p['m'] for p in prop_pattern(1.0))/1e3)/(led['propellant_t']-sum(p['m'] for p in prop_pattern(1.0))/1e3)
        farm = (FARM_P[0], FARM_P[0]+LR); shift = farm[1]-FARM_P[1]
        parts = prod_dry(shift_fwd=shift)
        xr = {'L2': (-92.0, -80.0), 'L1': (-140.0, -120.0), 'L3': (95.0, 106.0), 'storage': (-92.0, 40.0), 'distribution': (-92.0, 100.0),
              'scatter': (105.0, 140.0), 'ECLSS': (95.0, 106.0), 'L2 sections': (42.96, 50.4), 'bulkhead': (26.0, 27.0), 'LOG': (95.0, 106.0),
              'WARM': (48.9, 93.4), 'hot loop': (-140.0, 26.0)}
        for n, v in c['items_t'].items():
            if v[i] <= 0:
                continue
            key = next(k for k in sorted(xr, key=len, reverse=True) if n.startswith(k))
            x = xr[key]; r = 6.5 if key == 'hot loop' else (2.9 if key == 'L2' else 3.5)
            parts.append(part('ISSA-R:'+n, v[i]*1e3, x[0], x[1], r=r, cls='ISSA R', owner='ISSA'))
        dry_now = sum(p['m'] for p in parts)/1e3
        tank = end-dry_now-150.0                     # balance to the ISSA end mass with the 150 t structure line held as reference
        parts.append(part('ISSA-R:tankage and balance (derived)', tank*1e3, farm[0], farm[1], r=12.0, cls='DERIVED', owner='tankage'))
        scale = prop*1e3/sum(p['m'] for p in prop_pattern(1.0))
        parts += prop_pattern(left, farm, scale)
        return dict(name='R', id='WF-R-P6.0 nominal (ISSA 5eae701 Phase VI)', parts=parts, thrust=THRUST_N, farm=farm,
                    brow=(138.15+shift, 144.75+shift), fwd=144.75+shift, propellant_full_t=prop, issa_end_t=end,
                    tankage_derived_t=tank, note='no ISSA 3D layout: farm length scaled from T-A by propellant mass (PROTOTYPE)')
    raise KeyError(name)


def history(name, n=6, g_aft=0.0):
    """Mass states along the propellant-depletion history (left = 1 .. 0): total mass, acceleration and the placed parts."""
    out = []
    for k in range(n):
        left = 1.0-k/(n-1)
        c = config(name, left, g_aft=g_aft); M = sum(p['m'] for p in c['parts'])
        out.append(dict(left=left, M_kg=M, a=c['thrust']/M, cfg=c))
    return out


if __name__ == '__main__':
    for n in ('P', 'F1', 'R'):
        c = config(n, 1.0); M = sum(p['m'] for p in c['parts'])/1e3
        e = config(n, 0.0); Me = sum(p['m'] for p in e['parts'])/1e3
        print(n, c['id'], f'departure w/o structure {M:.0f} t, end {Me:.0f} t, farm {c["farm"]}, fwd {c["fwd"]:.2f}', {k: round(v, 1) for k, v in c.items() if k.endswith('_t')})
