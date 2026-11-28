"""WSI structural evaluation: the PSA Phase III FE model (phase3/model3.Build3 on phase2 fe/analysis) driven by a WSI coupled point.

The PSA code is imported, never copied or edited. c11 normally reads ISSA C1.1 at 8b30b71; here its source is replaced by the WSI point
(tanks, ledger rows, farm and Brow stations), so the rigid bodies, the farm vessels and the forward translation follow the joint
configuration. Material overlays add the Track F structural materials (data/materials.toml F-* rows) as FE allowables for a run.

STUDY / PROTOTYPE. Passing indicators are not engineering proof.
"""
import copy
import math
import time

import numpy as np

import common  # noqa: F401  (paths)
import c11
import model as mdl
import model3
import analysis as an
import tomllib

from common import PSA, psa_p2

P2 = psa_p2()['variants']['H:hub:F1']['items_t']
NONFE_T = dict(casing=P2.get('protective casing (secondary)', 22.4), rotating=P2.get('rotating ring structure (2 rings)', 24.8))
LAM_REQ_OP = 1.95          # PSA III.0: 1.87 on limit thrust = 1.95 x operating thrust (the lambda basis)


def _f_materials():
    d = tomllib.loads((PSA/'data/materials.toml').read_text()); out = {}
    for m in d['material']:
        if not m['id'].startswith('F-') or 'E' not in m:
            continue
        E = m['E']; out[m['id']] = dict(id=m['id'], name=m['name'], track='F', E=[0.95*E, E, 1.03*E], G=E/2.6, rho=m['rho'], alpha=m['alpha'],
                                         Fty=[0.92*m['Fty'], m['Fty'], 1.05*m['Fty']], Ftu=[0.92*m['Ftu'], m['Ftu'], 1.05*m['Ftu']],
                                         Fcy=[0.92*m['Fcy'], m['Fcy'], 1.05*m['Fcy']], T_max_K=m['T_max'], k_T_350K=1.0,
                                         min_gauge_mm=1.5 if m['family'] != 'AL' else 2.0, **{'class': 'F-PROPOSED'})
    return out


F_MATS = _f_materials()
for k, v in F_MATS.items():
    mdl.MATS.setdefault(k, v)
# compression allowable of the F composites is Fcy (like ALAL2O3F / CFPEEK in model.mat): register it
_orig_mat = mdl.mat


def _mat(mid, which='nom', T=350.0):
    r = _orig_mat(mid, which, T)
    if mid in F_MATS:
        m = F_MATS[mid]; i = {'low': 0, 'nom': 1, 'high': 2}[which]; r['Fc'] = m['Fcy'][i]*1e6
    return r


mdl.mat = _mat


def use_point(P):
    """Point c11 at a WSI coupled point (issa_point output). SSI geometry (items, mounts) stays SSI-1.1. The ledger tankage_t is the
    whole re-solved tankage (production shells included), which c11 spreads over the vessels; c11 drops the production tankage parts."""
    SSI, _ = c11.src()
    c11._SSI, c11._CON = SSI, dict(tanks=P['T'], ledger=P['L'])


def concept(base='H', name=None, **mats):
    """A concept variant with family -> material overrides (registered under `name`)."""
    c = copy.deepcopy(mdl.CONCEPTS[base]); c['mats'].update(mats); name = name or base+'+'+'+'.join(f'{k}:{v}' for k, v in mats.items())
    mdl.CONCEPTS[name] = c
    return name


def evaluate(P, concept_id='H', deck='A', n_states=2, iters=3, h2_aft=None, partials=(0.0, 1.0), stiff_passes=0, log=None, depletion=True,
             radius_scale=None):
    """Size the structure on the point's depletion states and return masses and stability (lambda x operating thrust)."""
    t0 = time.time(); use_point(P)
    hist = c11.history(n_states, h2_aft=h2_aft)
    for h in hist:
        h['cfg']['parts'] = h['cfg']['bodies']
    old_sp = an.STIFF_PASSES; an.STIFF_PASSES = stiff_passes
    try:
        b = model3.Build3(concept_id, hist[0]['cfg'], deck=deck, rotor='hub')
        res = an.run(b, hist, iters=iters, log=log)
    finally:
        an.STIFF_PASSES = old_sp
    sm, by = b.structure_mass()
    stab = []
    states = (hist[0], hist[-1]) if depletion and len(hist) > 1 else (hist[0],)
    for h in states:
        b.attach(h['cfg']['bodies']); an.solve(b)
        for p in partials:
            g = an.global_stability(b, partial=p); g.pop('mode', None)
            stab.append(dict(left=h['left'], partial=p, lam=g.get('lam'), kind=g.get('kind'), f1_Hz=g.get('f1'), mode_groups=g.get('mode_groups', {})))
            if log:
                log(f'  left {h["left"]:.2f} partial {p}: lambda {g.get("lam")} {g.get("kind")} groups {list(g.get("mode_groups", {}))[:4]}')
    members = sm/1e3; joints = res['joints_t']
    total = members+joints+NONFE_T['casing']+NONFE_T['rotating']
    lam_min = {p: min((s['lam'] if s['lam'] is not None else 99.0) for s in stab if s['partial'] == p) for p in partials}
    return dict(concept=concept_id, deck=deck, h2_aft=h2_aft, members_t=members, joints_t=joints, nonfe_t=NONFE_T, structure_t=total,
                by_family_t={k: v/1e3 for k, v in by.items()}, strength_members_t=res['strength_members_t'], stiffness=res['stiffness'],
                stability=stab, lam_static=lam_min.get(0.0), lam_follower=lam_min.get(1.0), lam_req=LAM_REQ_OP,
                farm_x=tuple(P['T']['farm_x']), ship_length_m=P['T']['ship_length_m'], departure_t=P['L']['departure_t'], seconds=time.time()-t0)
