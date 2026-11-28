"""PSA Phase III closure runs (owner 3.5, WSI closure request a-c): strength sizing (full Phase III check) then stability-driven
stiffening by modal sensitivity, not uniform thickening.

Sensitivity rule (Rayleigh, fixed mode shape): for the critical mode phi at lambda, raising the stiffness of group g by a relative
amount d_g raises lambda by about lambda x d_g x U_g / U, where U_g is the strain energy of phi in g. Its cost is m_g x (mass per unit
stiffness change): EI ~ r^3 t and m ~ r t, so a radius increase buys 3x the bending stiffness per kg that a thickness increase does
(until rmax or the shell limit). Each pass stiffens the groups with the highest energy share per tonne, until the share they cover
reaches COVER, by the factor the Rayleigh estimate needs (capped at x1.6 per pass), then re-checks strength (larger sections pass;
a shell-limited group gets thickness back) and recomputes every state and case. Passive targets: static (fixed-direction) and full
follower lambda >= LAM_TARGET x operating thrust at every depletion state.

  python3 closure3.py <tag> <concept> <deck> <rotor> [--ring] [--mats fam=MAT,...] [--target 1.95] [--passes 10]
"""
import argparse
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
import model as mdl  # noqa: E402
import model3 as m3  # noqa: E402
import run3  # noqa: E402

OUT = H.parent / 'results' / 'p3_closure'; OUT.mkdir(parents=True, exist_ok=True)
LAM_TARGET = 1.95
F1_MIN = 0.0       # WSI I-08: 0.095 Hz first elastic mode at every state when requested (--f1)
COVER = 0.6
CASES = (('static', 0.0), ('follower', 1.0))
SIZED_FAMS = None   # every sized family may be stiffened


THRUST_AT = 'noz'   # Phase III audit: thrust enters at the four nozzle pickups (actual points); 'ring' = the 12 thrust-ring nodes (Phase II)


def crit(b, partial):
    """global_stability with the critical mode kept (thrust at the actual thrust points, inertia-relief axial field)."""
    T = b.cfg['thrust']; ring = list(b.noz) if THRUST_AT == 'noz' else list(b.station_nodes[b.xs[0]].values())
    b.m.loads = {}; b.m.follow = {}
    for n in ring:
        b.m.thrust(n, (T/len(ring), 0.0, 0.0), follower=True)
    r = b.m.solve_static(inertia_relief=True); fs = b.m.element_forces(r['u'])
    N = [f['N'] if f else 0.0 for f in fs]
    out = an.reduced_stability(b, N, lam_hi=12.0, nbasis=60, partial=partial)
    b.apply_thrust(T)
    return out


def energies(b, u):
    """Strain energy of mode u per design group (sized groups) and in the unsized remainder (springs, interfaces, vessel walls)."""
    U = {}; rest = 0.0
    for e, md in zip(b.m.el, b.meta):
        if not e['on']:
            continue
        d = b.m._dofs(e); ue = u[d]
        if e['kind'] == 'spring':
            k = np.zeros((12, 12))
            for j, kk in enumerate(e['k6']):
                k[j, j] = k[j+6, j+6] = kk; k[j, j+6] = k[j+6, j] = -kk
            rest += 0.5*float(ue @ k @ ue); continue
        L, R, T = b.m.frame(e); ul = T @ ue; en = 0.5*float(ul @ b.m.k_local(L, e['sec'], e['mat'], e['kind']) @ ul)
        if md['fam'] in ('iface', 'mount') or md['group'] not in b.sec:
            rest += en
        else:
            U[md['group']] = U.get(md['group'], 0.0)+en
    return U, rest


def group_mass(b):
    m = {}
    for e, md in zip(b.m.el, b.meta):
        if e['kind'] == 'spring' or not e['on'] or md['fam'] in ('iface', 'mount'):
            continue
        L = b.m.frame(e)[0]; m[md['group']] = m.get(md['group'], 0.0)+e['mat']['rho']*e['sec']['A']*L
    return m


def first_mode(b):
    import scipy.sparse.linalg as spla
    K = b.m.assemble('K'); M = b.m.assemble('M'); free = b.m.free_mask(); Kf = K[free][:, free].tocsc(); Mf = M[free][:, free].tocsc()
    w2, V = spla.eigsh(Kf, M=Mf, k=12, sigma=-0.5, which='LM'); o = np.argsort(w2); w2, V = w2[o], V[:, o]
    j = int(np.argmax(w2 > 1e-4*w2.max())); u = np.zeros(b.m.ndof); u[free] = V[:, j]
    return float(np.sqrt(w2[j])/(2*math.pi)), u


def sweep(b, hs, log):
    res = []
    for s in hs:
        b.attach(s['cfg']['bodies'])
        for nm, part in CASES:
            g = crit(b, part); lam = g.get('lam') or 12.0
            res.append(dict(left=s['left'], case=nm, partial=part, lam=lam, kind=g.get('kind'), f1=g.get('f1'), mode=g.get('mode')))
    log('    ' + '  '.join(f"{r['left']:.1f}{r['case'][0]} {r['lam']:.2f}" for r in res))
    return res


def strength_fix(b, env, K=a3.K_EFF):
    """After stiffening: every member must still pass the full check; a failing group gets thickness (never less section)."""
    fixed = []
    for _ in range(6):
        u, mode = a3.utilisation(b, env, K)
        worst = {}
        for i, (e, md) in enumerate(zip(b.m.el, b.meta)):
            if u[i] > 1.0:
                worst[md['group']] = max(worst.get(md['group'], 0.0), u[i])
        if not worst:
            break
        for g, v in worst.items():
            s = b.sec[g]; s['t'] = min(s['t']*min(2.0, v*1.1), s['r']/4); fixed.append(g)
        b.update_sections()
    return sorted(set(fixed))


def run(tag, concept, deck, rotor, ring=False, mats=None, target=LAM_TARGET, passes=10, n_states=3, src='wsi', log=print, f1_min=F1_MIN,
        start=None):
    t0 = time.time(); hs = run3.hist(n_states, src)
    b = m3.Build3(concept, hs[0]['cfg'], deck=deck, rotor=rotor, guide_ring=ring, mats=mats or {})
    b.attach(hs[0]['cfg']['bodies']); mc = b.mass_check(hs[0]['cfg']['bodies'])
    if start:
        sd = json.loads(Path(start).read_text())
        for g, q in sd['sections'].items():
            if g in b.sec:
                b.sec[g].update(q)
        b.update_sections(); res = dict(joints_t=sd['strength_joints_t'], sizing={})
        failing0 = sd.get('strength_failing', [])
    else:
        res = a3.run3(b, hs, iters=4, log=log); failing0 = None
    strength_members = b.structure_mass()[0]/1e3; m0 = group_mass(b)
    failing = failing0 if failing0 is not None else [g for g, s in res['sizing'].items() if not s['passes']]
    log(f'  strength: members {strength_members:.1f} t, joints {res["joints_t"]:.1f} t, failing {failing}')
    hist = []
    st = sweep(b, hs, log)
    for k in range(passes):
        worst = min(st, key=lambda r: r['lam'])
        hist.append(dict(pass_=k, members_t=b.structure_mass()[0]/1e3, lam={f"{r['left']:.1f}:{r['case']}": r['lam'] for r in st},
                         worst=f"{worst['left']:.1f}:{worst['case']}"))
        f1s = []
        if f1_min:
            for s_ in hs:
                b.attach(s_['cfg']['bodies']); f1s.append((first_mode(b), s_['left']))
            hist[-1]['f1'] = {f"{l:.1f}": f for (f, _), l in f1s}
            log('    f1 ' + '  '.join(f"{l:.1f} {f:.3f}" for (f, _), l in f1s))
        lam_ok = worst['lam'] >= target-2e-3 or worst['mode'] is None
        f1_low = [x for x in f1s if x[0][0] < f1_min]
        if lam_ok and not f1_low:
            break
        if not lam_ok:
            mode = worst['mode']; need = target/worst['lam'] - 1.0; why = f"{worst['left']:.1f}:{worst['case']} lambda {worst['lam']:.2f}"
        else:
            (f1, mode), l = min(f1_low, key=lambda x: x[0][0]); need = (f1_min/f1)**2 - 1.0; why = f'{l:.1f}: f1 {f1:.3f} Hz'
        U, rest = energies(b, mode); tot = sum(U.values())+rest; gm = group_mass(b)
        eff = sorted(((U[g]/tot)/max(gm.get(g, 1.0)/1e3, 1e-3), g) for g in U if U[g] > 0)[::-1]
        pick, cov = [], 0.0
        for e_, g in eff:
            pick.append(g); cov += U[g]/tot
            if cov >= COVER or len(pick) >= 12:
                break
        d = min(0.6, 1.1*need/max(cov, 1e-3))
        for g in pick:
            s = b.sec[g]; fr = (1+d)**(1/3)
            if s['fam'] not in ('spine', 'hub', 'tankwall') and s['r']*fr <= s['rmax']:
                s['r'] *= fr
            else:
                s['t'] = min(s['t']*(1+d), s['r']/4)
        b.update_sections()
        hist[-1].update(picked={g: round(U[g]/tot, 3) for g in pick}, cover=cov, d=d, unsized_share=rest/tot)
        log(f"  pass {k+1}: worst {why}; stiffen {len(pick)} groups "
            f"(cover {cov:.2f}, unsized share {rest/tot:.2f}) by EI x{1+d:.2f}: {', '.join(pick[:6])}")
        cs = an.cases(b, hs); env = a3.envelope3(b, cs); fixed = strength_fix(b, env)
        if fixed:
            log(f'    strength re-fix: {fixed}')
        st = sweep(b, hs, log)
    f1_end = {}
    for s_ in hs:
        b.attach(s_['cfg']['bodies']); f1_end[f"{s_['left']:.1f}"] = first_mode(b)[0]
    cs = an.cases(b, hs); env = a3.envelope3(b, cs); jt, per = an.joints(b, env)
    sm, by = b.structure_mass(); m1 = group_mass(b)
    added = {g: (m1.get(g, 0)-m0.get(g, 0))/1e3 for g in m1 if abs(m1.get(g, 0)-m0.get(g, 0)) > 50.0}
    out = dict(tag=tag, thrust_at=THRUST_AT, concept=concept, deck=deck, rotor=rotor, guide_ring=ring, mats=mats or {}, source=hs[0]['cfg']['id'], target=target,
               mass_check=mc, strength_members_t=strength_members, strength_joints_t=res['joints_t'], strength_failing=failing,
               members_t=sm/1e3, joints_t=jt/1e3, structure_t=sm/1e3+jt/1e3, stiffening_t=sm/1e3-strength_members,
               added_by_group_t=dict(sorted(added.items(), key=lambda kv: -kv[1])), by_family_t={k: v/1e3 for k, v in by.items()},
               tankwall_credit_t=b.tank_credit_t(), psa_increment_t=sm/1e3+jt/1e3-b.tank_credit_t(),
               stability=[{k: v for k, v in r.items() if k != 'mode'} for r in st], passes=hist,
               f1_Hz=f1_end, f1_min=f1_min,
               closed=bool(min(r['lam'] for r in st) >= target-2e-3 and min(f1_end.values()) >= (f1_min or 0)), seconds=time.time()-t0,
               sections={g: dict(r=s['r'], t=s['t'], mat=s['mat']) for g, s in b.sec.items()})
    (OUT / f'{tag}.json').write_text(json.dumps(out, indent=1, default=float))
    log(f"{tag}: structure {out['structure_t']:.1f} t (strength {strength_members+res['joints_t']:.1f}, stiffening +{out['stiffening_t']:.1f}), "
        f"closed {out['closed']}, min lambda {min(r['lam'] for r in st):.2f}, {out['seconds']:.0f} s")
    return out, b


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('tag'); p.add_argument('concept'); p.add_argument('deck'); p.add_argument('rotor')
    p.add_argument('--ring', action='store_true'); p.add_argument('--mats', default='')
    p.add_argument('--target', type=float, default=LAM_TARGET); p.add_argument('--passes', type=int, default=10)
    p.add_argument('--thrust', default='noz'); p.add_argument('--src', default='wsi'); p.add_argument('--f1', type=float, default=0.0); p.add_argument('--start', default=None)
    a = p.parse_args()
    mats = dict(kv.split('=') for kv in a.mats.split(',') if kv); THRUST_AT = a.thrust
    run(a.tag, a.concept, a.deck, a.rotor, ring=a.ring, mats=mats, target=a.target, passes=a.passes, src=a.src, f1_min=a.f1, start=a.start)
