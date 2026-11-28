"""PSA Phase III configuration WF-F1-C1.1 as physical rigid bodies (owner brief 2026-11-28, item 3.1).

Every mass item keeps its own mass, centre of mass and rotational inertia about that centre (principal axes along the ship axes),
together with where it is attached to the structure and how (anchor / slide). Nothing is concentrated at an attachment plane.

Sources (read only, never written):
  ISSA  claude/cloud/ship-systems-architecture @ ISSA_REF: i3d_structure_interface.json (SSI-1.1, shared block, mount ids)
        and i3d_consolidated.json (C1.1 ledger rows, per-vessel propellant, tankage, fills, supports)
  PROD  main mass_model dry parts at the PSA base (rings, Brow, drive, inventory); the 150 t primary structure line is removed:
        PSA supplies the structure from its FE model.

Body kinds:
  vessel  one of the 13 farm vessels: shell (tankage share, thin cylinder) + contents (settled liquid aft under thrust); aft skirt
          anchor at the deck plane, forward guide ring radial only (axial slide for cryogenic contraction)            (SSI tanks.supports)
  rotor   one habitat ring assembly (hoop at its COM radius), on the stationary hub bearings, free in roll (spin), gyroscopic
          coupling handled in the dynamics, not in statics
  unit    a lumped machine with SSI mounts (L2 units)
  line    an item spread along X; split into slices at its true radius / blade azimuths, each slice tied to the nearest frame
  drive   drive package and L1 on the nozzle nodes
  brow    Brow and EYE (forward defense) on the Brow interface ring
"""
import json
import math
import subprocess
import sys
from pathlib import Path

import numpy as np

H = Path(__file__).resolve().parent
ROOT = H.parents[2]
sys.path.insert(0, str(ROOT / 'src' / 'wayfarer'))
sys.path.insert(0, str(H.parent / 'phase2'))
import mass_model as mm  # noqa: E402
import configs as cf2  # noqa: E402

ISSA_REF = '8b30b71'
ISSA_DIR = 'work/ship-systems-architecture/results'
THRUST_N = cf2.THRUST_N
STRUCT_KEY = cf2.STRUCT_KEY
FARM_P1 = 137.85                     # production farm forward end; production parts at or ahead of it move with the T-A stretch


def issa(name):
    return json.loads(subprocess.check_output(['git', 'show', f'{ISSA_REF}:{ISSA_DIR}/{name}'], cwd=ROOT))


_SSI = _CON = None


def src():
    global _SSI, _CON
    if _SSI is None:
        _SSI = issa('i3d_structure_interface.json'); _CON = issa('i3d_consolidated.json')
    return _SSI, _CON


def p3(x, r, az):
    return np.array([x, r*math.cos(math.radians(az)), r*math.sin(math.radians(az))])


def body(name, m, c, I, kind, owner, cls, **kw):
    return dict(name=name, m=float(m), c=np.array(c, float), I=np.diag(np.array(I, float)), kind=kind, owner=owner, cls=cls, **kw)


def cyl_I(m, a, L, shell=False):
    """Principal inertia of a cylinder along x (solid or thin shell, open ends) about its centre."""
    if shell:
        ix = m*a*a; it = m*(a*a/2+L*L/12)
    else:
        ix = m*a*a/2; it = m*(a*a/4+L*L/12)
    return (ix, it, it)


def vessels(left, carried=True):
    """The 13 farm vessels at `left` of the mission propellant (1 = departure). Contents settle aft under thrust (level from the aft
    dome); the frozen-liquid inertia is the rigid-body upper bound, slosh is a separate dynamic model (Phase III.3)."""
    S, C = src(); T = C['tanks']; out = []
    sh = {v['id']: v['a']*(v['x1']-v['x0']+v['a']) for v in T['vessels']}; tot_sh = sum(sh.values())
    for v in T['vessels']:
        L = v['x1']-v['x0']; a = v['a']; mt = C['ledger']['tankage_t']*1e3*sh[v['id']]/tot_sh
        keep = (v['residual_t']+v['reserve_t']) if carried else 0.0
        mp = (v['mission_t']*left + keep)*1e3
        rho = mp/max(v['loaded_m3']*(v['mission_t']*left+keep)/v['prop_t'], 1e-9) if mp > 0 else 0.0
        Lq = L*min(1.0, (mp/max(v['prop_t']*1e3, 1e-9))*v['fill']) if mp > 0 else 0.0
        c_sh = p3(0.5*(v['x0']+v['x1']), v['R'], v['az'])
        out.append(body(f'vessel {v["id"]} shell', mt, c_sh, cyl_I(mt, a, L, shell=True), 'vessel', 'tankage', 'ISSA C1.1', vid=v['id'],
                        a=a, R=v['R'], az=v['az'], x0=v['x0'], x1=v['x1'], species=v['species']))
        if mp > 0:
            c_q = p3(v['x0']+Lq/2, v['R'], v['az'])
            out.append(body(f'vessel {v["id"]} {v["species"]}', mp, c_q, cyl_I(mp, a, Lq), 'vessel', 'propellant', 'PROPELLANT', vid=v['id'],
                            a=a, R=v['R'], az=v['az'], x0=v['x0'], x1=v['x1'], species=v['species'], level_m=Lq))
    return out


# ISSA C1.1 ledger rows -> placement. 'sid' names SSI items whose geometry (centre, radius, blade azimuths, x range) carries the row;
# rows without an SSI item take an X range and a radius (PROTOTYPE placement, as Phase II).
ROWS = {
    'L1 (derived)': dict(kind='drive', x=(-140.0, -120.0), r=3.0),
    'L3': dict(kind='line', x=(95.0, 106.0), r=1.5),
    'storage (buffer + restart)': dict(kind='line', x=(-92.0, 40.0), r=4.5),
    'distribution': dict(kind='line', x=(-92.0, 100.0), r=4.6),
    'scatter allowance (OPEN)': dict(kind='line', x=(105.0, 109.0), r=3.0),
    'ECLSS modular increment': dict(kind='line', x=(99.3, 101.3), r=3.2),
    'bulkhead relocation': dict(kind='line', x=(40.8, 41.2), r=6.0),
    'LOG-G1 tare (3 t containers, 12 months)': dict(kind='line', x=(95.0, 106.0), r=2.0),
    'L2 (3 x 3.5 MWe, FT-03 1500 K inlet) (restart packs moved to the storage line)': dict(kind='unit', sid=('PWR-L2U-1', 'PWR-L2U-2', 'PWR-L2U-3')),
    'L2 sections 950 K cross-strapped + dual headers': dict(kind='blade', sid=('RAD-L2-90', 'RAD-L2-210', 'RAD-L2-330')),
    'hot loop H6a': dict(kind='blade', x=(-111.6, 41.02), r=6.52, az=(90.0, 210.0, 330.0)),
    'L2 NaK transport loops + pumps (Stage E)': dict(kind='blade', x=(-81.6, 40.4), r=5.8, az=(10, 50, 130, 170, 250, 290)),
    'L2 section hardware above the Phase VI header line (Stage E)': dict(kind='blade', sid=('RAD-L2-90', 'RAD-L2-210', 'RAD-L2-330')),
    'robots, crawlers, MRU carriage + rail (Stage H)': dict(kind='blade', x=(-92.7, 92.0), r=3.6, az=(270.0,)),
    'body-bay module 10 racks (relocated dry store, Stage H)': dict(kind='line', x=(22.25, 33.25), r=3.0),
    'cryocooler stations (final T-A, increment over the existing coolers)': dict(kind='cryo'),
    'HOT forward-pointing fin manifolds (DR-3D-04)': dict(kind='blade', sid=('RAD-HOT-MAN-90', 'RAD-HOT-MAN-210', 'RAD-HOT-MAN-330')),
    'LOW forward tip extensions (3 blades)': dict(kind='blade', sid=('RAD-LOWTAB-90', 'RAD-LOWTAB-210', 'RAD-LOWTAB-330')),
    'WARM pump upgrade (451 K, +mass flow)': dict(kind='line', x=(50.4, 72.9), r=4.0),
    'MRU fixtures (MIF-A/C)': dict(kind='blade', x=(-92.7, 92.0), r=3.6, az=(270.0,)),
    'MRU second rail (twin rails clear of bus 3)': dict(kind='blade', x=(-92.7, 92.0), r=4.6, az=(255.0, 285.0)),
    'MRU burn restraints (two park stations)': dict(kind='blade', x=(-92.7, 92.0), r=3.6, az=(270.0,)),
    'EXT-TA external transfer arm (H6a EM pumps)': dict(kind='lump', sid=('EXT-TA',)),
}
# production parts placed off-axis (the mass model keeps them axisymmetric): radiator blades on the three planes
PROD_BLADE = {'radiators_thermal': dict(r=21.75, az=(90.0, 210.0, 330.0))}


def config(left=1.0, carried=True, h2_aft=None):
    """Bodies of WF-F1-C1.1 at `left` of the mission propellant. h2_aft: optional joint-study relocation (III.2), a dict
    {fraction, x, r, n, az} moving that fraction of each H2 vessel's contents (and its tankage share) into aft vessels."""
    S, C = src(); items = {i['id']: i for i in S['items']}; shift = C['tanks']['added_length_m']
    out = []
    for p in mm.dry_parts(cf2.S()):
        if p['name'] in STRUCT_KEY or p['name'].startswith('tankage_'):
            continue
        x0, x1 = p['x']; c = np.array(p['c'], float)
        if x0 >= FARM_P1-8.0:
            x0, x1 = x0+shift, x1+shift; c[0] += shift
        n = p['name']; I = p['I']
        if '@ring_' in n:
            out.append(body(n, p['m'], c, I, 'rotor', n.split('@')[0], 'PRODUCTION', ring=n[-1]))
        elif n in ('forward_impact_shielding', 'eye_sensors'):
            out.append(body(n, p['m'], c, I, 'brow', n, 'PRODUCTION', x=(x0, x1)))
        elif n == 'drive_package':
            out.append(body(n, p['m'], c, I, 'drive', n, 'PRODUCTION', x=(x0, x1)))
        elif n in PROD_BLADE:
            out.append(body(n, p['m'], c, I, 'blade', n, 'PRODUCTION', x=(x0, x1), r=PROD_BLADE[n]['r'], az=PROD_BLADE[n]['az']))
        else:
            out.append(body(n, p['m'], c, I, 'line', n, 'PRODUCTION', x=(x0, x1), r=3.0))
    for row in C['ledger']['rows']:
        if row['t'] <= 0:
            continue
        rule = ROWS.get(row['item'])
        if rule is None:
            raise KeyError(f'no placement for C1.1 row {row["item"]}')
        m = row['t']*1e3; k = rule['kind']
        if k == 'cryo':
            cr = [i for i in S['items'] if i['id'].startswith('CRYO-')]
            for i in cr:
                out.append(body(f'{row["item"]} {i["id"]}', m/len(cr), i['cg'], (0, 0, 0), 'lump', 'ISSA', 'ISSA C1.1', sid=i['id']))
            continue
        if 'sid' in rule:
            its = [items[s] for s in rule['sid']]; tot = sum(max(i.get('mass_t') or 0, 1e-3) for i in its)
            for i in its:
                mi = m*max(i.get('mass_t') or 0, 1e-3)/tot
                env = i.get('envelope', {}); x = env.get('x', [i['cg'][0]-1, i['cg'][0]+1]); L = x[1]-x[0]
                kind = 'unit' if k == 'unit' else ('lump' if k == 'lump' else 'blade1')
                out.append(body(f'{row["item"]} {i["id"]}', mi, i['cg'], (0.0, mi*L*L/12, mi*L*L/12), kind, 'ISSA', 'ISSA C1.1', sid=i['id'],
                                mounts=i.get('mounts', []), x=tuple(x)))
            continue
        x0, x1 = rule['x']; c = ((x0+x1)/2, 0.0, 0.0); L = x1-x0
        if k == 'blade':
            out.append(body(row['item'], m, c, (m*rule['r']**2, m*(rule['r']**2/2+L*L/12), m*(rule['r']**2/2+L*L/12)), 'blade', 'ISSA', 'ISSA C1.1',
                            x=(x0, x1), r=rule['r'], az=rule['az']))
        else:
            out.append(body(row['item'], m, c, cyl_I(m, rule['r'], L), k, 'ISSA', 'ISSA C1.1', x=(x0, x1), r=rule['r']))
    out += vessels(left, carried)
    if h2_aft:
        out = relocate_h2(out, **h2_aft)
    return dict(name='C1.1', id=f'WF-F1-C1.1 (ISSA {ISSA_REF}, SSI-1.1)', bodies=out, thrust=THRUST_N, farm=tuple(C['tanks']['farm_x']),
                brow=tuple(C['tanks']['brow_x']), left=left, ship_length_m=C['tanks']['ship_length_m'])


def relocate_h2(bodies, fraction, x, r, n=3, az=(30.0, 150.0, 270.0), a=None):
    """Joint study III.2: move `fraction` of the H2 contents (and the matching tankage share) out of the forward H2 vessels into n
    aft vessels of radius a at (x range, r, az). PROTOTYPE placement; volume, insulation and heating are scored separately."""
    moved = 0.0; moved_sh = 0.0
    for b in bodies:
        if b['kind'] == 'vessel' and b.get('species') == 'hydrogen':
            if b['owner'] == 'propellant':
                dm = b['m']*fraction; b['m'] -= dm; moved += dm
                b['I'] = b['I']*(1-fraction)
            else:
                dm = b['m']*fraction; b['m'] -= dm; moved_sh += dm; b['I'] = b['I']*(1-fraction)
    L = x[1]-x[0]; aa = a or 2.0
    for k in range(n):
        c = p3(0.5*(x[0]+x[1]), r, az[k % len(az)])
        bodies.append(body(f'aft H2 vessel {k+1} shell', moved_sh/n, c, cyl_I(moved_sh/n, aa, L, True), 'aftvessel', 'tankage', 'JOINT STUDY',
                           x=x, r=r, az=az[k % len(az)], a=aa))
        bodies.append(body(f'aft H2 vessel {k+1} hydrogen', moved/n, c, cyl_I(moved/n, aa, L), 'aftvessel', 'propellant', 'JOINT STUDY',
                           x=x, r=r, az=az[k % len(az)], a=aa))
    return bodies


def totals(bodies):
    """Total mass, centre and inertia tensor about the centre (parallel axis), the source truth for the FE representation."""
    M = sum(b['m'] for b in bodies); c = sum(b['m']*b['c'] for b in bodies)/M; J = np.zeros((3, 3))
    for b in bodies:
        d = b['c']-c; J += b['I'] + b['m']*(np.dot(d, d)*np.eye(3)-np.outer(d, d))
    return M, c, J


def history(n=6, carried=True, h2_aft=None):
    out = []
    for k in range(n):
        left = 1.0-k/(n-1); c = config(left, carried, h2_aft); M = sum(b['m'] for b in c['bodies'])
        out.append(dict(left=left, M_kg=M, a=c['thrust']/M, cfg=c))
    return out


if __name__ == '__main__':
    S, C = src()
    for left in (1.0, 0.0):
        c = config(left); M, cg, J = totals(c['bodies'])
        print(f'left {left}: {M/1e3:.1f} t without PSA structure (ISSA C1.1 departure 9078.4 incl. the 150 t line -> {C["ledger"]["departure_t"]-150:.1f}), '
              f'CG x {cg[0]:.2f} y {cg[1]:.3f} z {cg[2]:.3f}, Ixx {J[0,0]:.3e} Iyy {J[1,1]:.3e} Izz {J[2,2]:.3e}')
