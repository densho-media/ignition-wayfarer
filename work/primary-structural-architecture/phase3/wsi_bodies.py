"""WSI working configuration (WSI-0.1, work/wayfarer-systems-integration/results/wsi_config.json + the ledger rows of wsi_cp1.json on
the WSI branch, read only) as PSA rigid bodies, in the same body format as c11.config, so model3 / run3 / stab3 run on it unchanged.

  vessels   wsi tanks.vessels (x range, R, az, a, loaded_t, fill); tankage category shared by a(L+a); mission = loaded x mission/loaded
  rows      wsi ledger rows NEW / REPLACEMENT / HISTORICAL (moved) / PAYLOAD, placed with c11.ROWS; SSI items from wsi equipment + mounts
  historical production dry parts (mass_model, the 150 t line and production tankage removed), forward parts moved by the WSI stretch
  excluded  STRUCTURE (provisional) rows: PSA builds the structure in the FE model
Gaps found in WSI-0.1 (reported to WSI): equipment cg of the farm vessels, cryocoolers and the Brow translation are still at the C1.1
positions (x 136.3 / 164.3 / 168.7) although the farm is stretched to x 186.66; PSA places the cryo stations at the farm forward
end + 1.0 m (the C1.1 rule) and takes vessels and Brow from the tanks / dimensions blocks.
"""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

H = Path(__file__).resolve().parent
sys.path.insert(0, str(H)); sys.path.insert(0, str(H.parent / 'phase2'))
import c11  # noqa: E402

WSI_BRANCH = 'origin/claude/cloud/wayfarer-systems-integration'
WSI_DIR = 'work/wayfarer-systems-integration/results'
_W = {}


def wsi(ref=None):
    ref = ref or WSI_BRANCH
    if ref not in _W:
        get = lambda n: json.loads(subprocess.check_output(['git', 'show', f'{ref}:{WSI_DIR}/{n}'], cwd=c11.ROOT))
        sha = subprocess.check_output(['git', 'rev-parse', '--short', ref], cwd=c11.ROOT, text=True).strip()
        _W[ref] = (get('wsi_config.json'), get('wsi_cp1.json'), sha)
    return _W[ref]


def vessels(W, left, carried=True):
    T = W['tanks']; P = W['propellant']; tk = W['mass']['by_category_t']['TANKAGE']*1e3
    frac_m = P['mission_t']/P['loaded_t']
    sh = {v['id']: v['a']*(v['x'][1]-v['x'][0]+v['a']) for v in T['vessels']}; tot = sum(sh.values()); out = []
    for v in T['vessels']:
        x0, x1 = v['x']; L = x1-x0; a = v['a']; mt = tk*sh[v['id']]/tot
        mp = v['loaded_t']*1e3*(frac_m*left + ((1-frac_m) if carried else 0.0))
        Lq = L*v['fill']*mp/(v['loaded_t']*1e3) if mp > 0 else 0.0
        kw = dict(vid=v['id'], a=a, R=v['R'], az=v['az'], x0=x0, x1=x1, species=v['species'])
        out.append(c11.body(f'vessel {v["id"]} shell', mt, c11.p3(0.5*(x0+x1), v['R'], v['az']), c11.cyl_I(mt, a, L, shell=True), 'vessel', 'tankage', 'WSI', **kw))
        if mp > 0:
            out.append(c11.body(f'vessel {v["id"]} {v["species"]}', mp, c11.p3(x0+Lq/2, v['R'], v['az']), c11.cyl_I(mp, a, Lq), 'vessel', 'propellant',
                                'PROPELLANT', level_m=Lq, **kw))
    return out


def config(left=1.0, carried=True, ref=None):
    W, CP, sha = wsi(ref); shift = W['tanks']['added_length_m']; farm = tuple(W['dimensions']['farm_x']); brow = tuple(W['dimensions']['brow_x'])
    items = {i['id']: dict(i, mounts=[m for m in W['mounts'] if m['item'] == i['id']]) for i in W['equipment']}
    out = []
    for p in c11.mm.dry_parts(c11.cf2.S()):
        if p['name'] in c11.STRUCT_KEY or p['name'].startswith('tankage_'):
            continue
        x0, x1 = p['x']; c = np.array(p['c'], float)
        if x0 >= c11.FARM_P1-8.0:
            x0, x1 = x0+shift, x1+shift; c[0] += shift
        n = p['name']; I = p['I']
        if '@ring_' in n:
            out.append(c11.body(n, p['m'], c, I, 'rotor', n.split('@')[0], 'PRODUCTION', ring=n[-1]))
        elif n in ('forward_impact_shielding', 'eye_sensors'):
            out.append(c11.body(n, p['m'], c, I, 'brow', n, 'PRODUCTION', x=(x0, x1)))
        elif n == 'drive_package':
            out.append(c11.body(n, p['m'], c, I, 'drive', n, 'PRODUCTION', x=(x0, x1)))
        elif n in c11.PROD_BLADE:
            out.append(c11.body(n, p['m'], c, I, 'blade', n, 'PRODUCTION', x=(x0, x1), r=c11.PROD_BLADE[n]['r'], az=c11.PROD_BLADE[n]['az']))
        else:
            out.append(c11.body(n, p['m'], c, I, 'line', n, 'PRODUCTION', x=(x0, x1), r=3.0))
    for row in CP['ledger']['rows']:
        if row['cat'] not in ('NEW', 'REPLACEMENT', 'HISTORICAL (moved)', 'PAYLOAD') or row['t'] <= 0:
            continue
        m = row['t']*1e3
        if row['cat'] == 'PAYLOAD':
            out.append(c11.body(row['item'], m, (100.3, 0.0, 3.2), (0, 0, 0), 'lump', 'ISSA', 'WSI', x=(100.3, 100.3)))
            continue
        rule = c11.ROWS[row['item']]; k = rule['kind']
        if k == 'cryo':
            cr = [i for i in items.values() if i['id'].startswith('CRYO-')]
            for i in cr:
                cg = np.array(i['cg'], float); cg[0] = farm[1]+1.0
                out.append(c11.body(f'{row["item"]} {i["id"]}', m/len(cr), cg, (0, 0, 0), 'lump', 'ISSA', 'WSI', sid=i['id']))
            continue
        if 'sid' in rule:
            its = [items[s] for s in rule['sid']]; tot = sum(max(i.get('mass_t') or 0, 1e-3) for i in its)
            for i in its:
                mi = m*max(i.get('mass_t') or 0, 1e-3)/tot
                env = i.get('envelope', {}); x = env.get('x', [i['cg'][0]-1, i['cg'][0]+1]); L = x[1]-x[0]
                kind = 'unit' if k == 'unit' else ('lump' if k == 'lump' else 'blade1')
                out.append(c11.body(f'{row["item"]} {i["id"]}', mi, i['cg'], (0.0, mi*L*L/12, mi*L*L/12), kind, 'ISSA', 'WSI', sid=i['id'],
                                    mounts=i['mounts'], x=tuple(x)))
            continue
        x0, x1 = rule['x']; c = ((x0+x1)/2, 0.0, 0.0); L = x1-x0
        if k == 'blade':
            out.append(c11.body(row['item'], m, c, (m*rule['r']**2, m*(rule['r']**2/2+L*L/12), m*(rule['r']**2/2+L*L/12)), 'blade', 'ISSA', 'WSI',
                                x=(x0, x1), r=rule['r'], az=rule['az']))
        else:
            out.append(c11.body(row['item'], m, c, c11.cyl_I(m, rule['r'], L), k, 'ISSA', 'WSI', x=(x0, x1), r=rule['r']))
    out += vessels(W, left, carried)
    return dict(name='WSI-0.1', id=f'{W["id"]} (WSI {sha})', bodies=out, thrust=W['mission']['thrust_N'], farm=farm, brow=brow, left=left,
                ship_length_m=W['dimensions']['ship_length_m'])


def history(n=3, carried=True, ref=None):
    out = []
    for k in range(n):
        left = 1.0-k/(n-1); c = config(left, carried, ref); M = sum(b['m'] for b in c['bodies']); c['parts'] = c['bodies']
        out.append(dict(left=left, M_kg=M, a=c['thrust']/M, cfg=c))
    return out


if __name__ == '__main__':
    W, CP, sha = wsi(); cats = W['mass']['by_category_t']
    want = W['mass']['departure_t']-cats['STRUCTURE (provisional)']
    for left in (1.0, 0.0):
        c = config(left); M, cg, J = c11.totals(c['bodies'])
        print(f'WSI {sha} left {left}: {M/1e3:,.1f} t without structure (WSI departure less structure {want:,.1f}), CG x {cg[0]:.2f} '
              f'y {cg[1]:.3f} z {cg[2]:.3f}, Ixx {J[0,0]:.3e} Iyy {J[1,1]:.3e}')
