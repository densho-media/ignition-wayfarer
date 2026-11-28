"""PSA Phase III.4 fail-safe joints (owner P2-D5): joint and local-damage cases on a closed variant, classified on the owner's
hierarchy, with stability (not only strength) after damage, and the split-fitting mitigation for the shared nodes.

Hierarchy (best last): CATASTROPHIC < SHUTDOWN-ONLY < COAST < REPAIR < REDUCED < NOMINAL
  CATASTROPHIC   no load path, or the damaged ship buckles at operating thrust (static lambda < 1.0), or progressive collapse at
                 full thrust before shutdown (accidental factor 1.0)
  SHUTDOWN-ONLY  survives full thrust until detection and shutdown (lambda >= 1.0, no progressive collapse) but not a shutdown margin
                 (lambda < 1.2 PROTO) - the shutdown itself must be fast and clean
  COAST          survives shutdown with margin; carries coast loads (spin, RCS) - thrust needs repair first
  REPAIR         a repair restores thrust (classification of COAST when the damaged member is replaceable in flight: all are)
  REDUCED        thrust fraction f >= 0.30 with lambda >= 1.95 f... i.e. lambda_damaged/1.95 >= 0.30, and strength at f (factor 1.0)
  NOMINAL        lambda_damaged >= 1.95 and ultimate utilisation <= 1 at full thrust
REPAIR is reported as COAST + repairable (every PSA member is a replaceable cassette, hierarchy.py), so the classes printed are
CATASTROPHIC, SHUTDOWN-ONLY, COAST, REDUCED, NOMINAL with f_reduced.

Damage sets (one at a time): a whole joint (every member at the node) at the most loaded joints of each kind; a local damage sphere
(radius R_LOCAL, PROTO: debris strike, fire, fitting burst) at the paired-rail stations, which is the shared-node common mode; and the
split fitting (each node fitting is two independent half-lugs, so a fitting failure removes the members on one side of the node only).

  python3 failsafe3.py <closure json> [n_states]
"""
import json
import math
import sys
import time
from pathlib import Path

import numpy as np

H = Path(__file__).resolve().parent
sys.path.insert(0, str(H)); sys.path.insert(0, str(H.parent / 'phase2'))
import analysis as an  # noqa: E402
import analysis3 as a3  # noqa: E402
import closure3 as c3  # noqa: E402
import model as mdl  # noqa: E402
import model3 as m3  # noqa: E402
import run3  # noqa: E402

OUT = H.parent / 'results' / 'p3_failsafe'; OUT.mkdir(parents=True, exist_ok=True)
R_LOCAL = 2.5          # m, local damage sphere (PROTO)
LAM_SHUT = 1.2         # lambda margin needed to ride through detection and shutdown (PROTO)
F_RED = 0.30
SKIP = ('iface', 'mount', 'tie', 'slide')


def load(path, n):
    d = json.loads(Path(path).read_text()); hs = run3.hist(n, 'wsi')
    c3.THRUST_AT = d.get('thrust_at', 'noz')
    b = m3.Build3(d['concept'], hs[0]['cfg'], deck=d['deck'], rotor=d['rotor'], guide_ring=d['guide_ring'], mats=d['mats'])
    for g, s in d['sections'].items():
        if g in b.sec:
            b.sec[g].update(s)
    b.update_sections()
    return d, b, hs


def utils(b, fs, factor):
    """Member utilisation under one solve (full Phase III check) at load factor `factor` (1.4 ultimate, 1.0 accidental)."""
    u = np.zeros(len(b.m.el))
    for i, (e, md, f) in enumerate(zip(b.m.el, b.meta, fs)):
        if f is None or e['kind'] == 'spring' or not e['on'] or md['fam'] in SKIP or md['group'] not in b.sec:
            continue
        s = b.sec[md['group']]; mat = mdl.mat(s['mat']); A, I, S = an.tube_props(np.array(s['r']), np.array(s['t'])); L = b.m.frame(e)[0]
        k = factor/a3.LF
        v, _ = a3.check3(mat, A, I, S, s['r'], s['t'], L, k*max(-f['N'], 0), k*max(f['N'], 0), k*math.hypot(f['My'], f['Mz']),
                         k*abs(f.get('T', 0.0)), k*math.hypot(f['Vy'], f['Vz']))
        u[i] = float(v)
    return u


def members_at(b, nodes):
    s = set(nodes)
    return [i for i, (e, md) in enumerate(zip(b.m.el, b.meta)) if e['kind'] != 'spring' and md['fam'] not in ('iface',)
            and (e['a'] in s or e['b'] in s)]


def xyz(b, n):
    return np.array(b.m.X[n])


def sphere(b, c, r):
    P = np.array(b.m.X); return list(np.where(np.linalg.norm(P-c, axis=1) <= r)[0])


def split_half(b, n):
    """Members of node n on one side of the fitting's split plane (the plane through n normal to the member set's mean direction
    in the frame plane): a split fitting loses one half-lug, not the node."""
    idx = members_at(b, [n]); p = xyz(b, n); d = []
    for i in idx:
        e = b.m.el[i]; o = e['b'] if e['a'] == n else e['a']; v = xyz(b, o)-p; d.append(v/max(np.linalg.norm(v), 1e-9))
    d = np.array(d); radial = p.copy(); radial[0] = 0.0
    nrm = np.cross([1.0, 0, 0], radial) if np.linalg.norm(radial) > 1e-6 else np.array([0, 0, 1.0])
    nrm /= max(np.linalg.norm(nrm), 1e-9)
    side = d @ nrm
    a = [i for i, s in zip(idx, side) if s > 1e-6]; c = [i for i, s in zip(idx, side) if s <= 1e-6]
    return max((a, c), key=len) if a and c else idx[:max(1, len(idx)//2)]


def joint_rank(b, hs):
    cs = an.cases(b, hs); env = a3.envelope3(b, cs)
    F = {}
    for i, (e, md) in enumerate(zip(b.m.el, b.meta)):
        if e['kind'] == 'spring' or md['fam'] in SKIP or md['group'] not in b.sec:
            continue
        f = max(env['Nc'][i], env['Nt'][i])
        for n in (e['a'], e['b']):
            F.setdefault(n, []).append((f, md['fam']))
    return F


def scenarios(b, hs):
    F = joint_rank(b, hs); sc = []
    fam_of = {}
    for n, lst in F.items():
        fams = {f for _, f in lst}; key = 'deck' if 'deck' in fams else 'guide' if 'guide' in fams else 'pickup' if 'pickup' in fams else \
            'rail' if 'rail' in fams else 'collar' if 'collar' in fams else 'keel' if 'keel' in fams else None
        if key and len(lst) >= 2:
            fam_of.setdefault(key, []).append((sum(f for f, _ in lst), n))
    for key, lst in fam_of.items():
        for _, n in sorted(lst)[::-1][:2]:
            p = xyz(b, n); tag = f'{key} joint n{n} X {p[0]:+.0f} az {math.degrees(math.atan2(p[2], p[1])) % 360:.0f}'
            sc.append(('joint', tag+' (whole node)', members_at(b, [n]), n))
            sc.append(('split', tag+' (split fitting, one half-lug)', split_half(b, n), n))
    rails = b.rail_az()
    for x in (-111.25, -55.25, 0.75, 56.75):
        k = min(range(len(b.xs)), key=lambda i: abs(b.xs[i]-x)); xs = b.xs[k]
        na, nb = b.station_nodes[xs][rails[0]], b.station_nodes[xs][rails[1]]
        c = 0.5*(xyz(b, na)+xyz(b, nb)); gap = float(np.linalg.norm(xyz(b, na)-xyz(b, nb)))
        sc.append(('local', f'local damage r {R_LOCAL} m between paired rails X {xs:+.0f} (gap {gap:.1f} m, common mode)',
                   members_at(b, sphere(b, c, R_LOCAL)), na))
    sc.append(('member', 'one nozzle pickup strut', [i for i, md in enumerate(b.meta) if md['fam'] == 'pickup'][:1], None))
    return sc


def lam_at(b, partial=0.0):
    g = c3.crit(b, partial); return g.get('lam') or 12.0, g.get('kind')


def intact_util(b, hs):
    """Accidental (factor 1.0) utilisation of the intact ship per state: members already above 1 intact (strength-failing groups
    of the closure) are not counted as damage overloads."""
    out = {}
    for s in hs:
        b.attach(s['cfg']['bodies']); r, fs = an.solve(b); out[s['left']] = utils(b, fs, 1.0)
    return out


def evaluate(b, off, hs, u0):
    """Damage `off`, then per state: lambda (static and follower), ultimate utilisation, the strength-limited thrust fraction, and
    the progressive chain at full thrust (factor 1.0, members newly above max(1, intact) removed one at a time, up to 6). The chain
    is catastrophic only if the residual structure is a mechanism or buckles below operating thrust (residual static lambda < 1);
    a chain of local secondary members that leaves the ship stable is local damage (repair)."""
    for i in off:
        b.m.el[i]['on'] = False
    rec = dict(n_off=len(off), groups=sorted({b.meta[i]['group'] for i in off})[:12], states=[])
    try:
        for s in hs:
            b.attach(s['cfg']['bodies']); base = np.maximum(1.0, 1.02*u0[s['left']])
            ls, _ = lam_at(b, 0.0); lf, _ = lam_at(b, 1.0); lam = min(ls, lf)
            r, fs = an.solve(b)
            if not np.isfinite(r['u']).all() or np.abs(r['u']).max() > 50.0:
                raise np.linalg.LinAlgError('mechanism')
            uu = utils(b, fs, a3.LF); ua = utils(b, fs, 1.0)
            f_str = float(min(1.0, np.min(base/np.maximum(ua, 1e-9))))
            chain, removed, mech = [], [], False
            for _ in range(6):
                over = np.where(ua > base)[0]
                if not len(over):
                    break
                k = int(max(over, key=lambda i: ua[i]/base[i])); b.m.el[k]['on'] = False; removed.append(k); chain.append(b.meta[k]['group'])
                r2, f2 = an.solve(b)
                if not np.isfinite(r2['u']).all() or np.abs(r2['u']).max() > 50.0:
                    mech = True; break
                ua = utils(b, f2, 1.0)
            lam_res = lam if not removed else (0.0 if mech else lam_at(b, 0.0)[0])
            arrested = not mech and not len(np.where(ua > base)[0])
            for k in removed:
                b.m.el[k]['on'] = True
            prim = [g for g in chain if g.split(':')[0] in ('rail', 'pickup', 'ring', 'cone', 'deck', 'keel', 'collar', 'spine', 'guide')]
            rec['states'].append(dict(left=s['left'], lam=lam, lam_static=ls, lam_follower=lf, u_ult=float(uu.max()), f_strength=f_str,
                                      chain=chain, primary_in_chain=prim, arrested=arrested, mechanism=mech, lam_residual=lam_res))
        st = rec['states']; w = min(st, key=lambda r: r['lam'])
        cat = any(r['mechanism'] or r['lam_residual'] < 1.0 for r in st)
        f_red = min(min(r['lam'] for r in st)/c3.LAM_TARGET, min(r['f_strength'] for r in st))
        if w['lam'] < 1.0 or cat:
            cls = 'CATASTROPHIC'
        elif w['lam'] < LAM_SHUT or min(r['lam_residual'] for r in st) < LAM_SHUT:
            cls = 'SHUTDOWN-ONLY'
        elif w['lam'] >= c3.LAM_TARGET-2e-3 and all(r['f_strength'] >= 1.0 for r in st):
            cls = 'NOMINAL'
        elif f_red >= F_RED:
            cls = 'REDUCED'
        else:
            cls = 'COAST'
        rec.update(lam_min=w['lam'], lam_residual_min=min(r['lam_residual'] for r in st), f_reduced=float(min(f_red, 1.0)),
                   chain=max((r['chain'] for r in st), key=len), cls=cls)
    except Exception as ex:
        rec.update(lam_min=0.0, lam_residual_min=0.0, f_reduced=0.0, cls='CATASTROPHIC', note='no load path: '+type(ex).__name__)
    for i in off:
        b.m.el[i]['on'] = True
    return rec


def main(path, n=3):
    t0 = time.time(); d, b, hs = load(path, n); b.attach(hs[0]['cfg']['bodies'])
    rows = []; u0 = intact_util(b, hs)
    for kind, name, off, node in scenarios(b, hs):
        if not off:
            continue
        r = evaluate(b, off, hs, u0); r.update(kind=kind, name=name, node=node); rows.append(r)
        print(f"{r['cls']:14s} lam {r['lam_min']:.2f} res {r['lam_residual_min']:.2f} f_red {r['f_reduced']:.2f}  {name}  ({r['n_off']} members)", flush=True)
    out = dict(source=path, tag=d['tag'], r_local=R_LOCAL, lam_shut=LAM_SHUT, rows=rows, seconds=time.time()-t0)
    (OUT / f"{d['tag']}.json").write_text(json.dumps(out, indent=1, default=float))
    return out


if __name__ == '__main__':
    main(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 3)
