"""PSA Phase II damage tolerance: member, joint and shared-node loss, redistribution and progressive collapse (owner D03).

For a sized build, each damage case switches elements off and re-solves the free-free ship under steady thrust x DLF with inertia
relief, then:
  u_nom  = ultimate utilisation (1.4 x limit, design allowables) at full thrust  -> NOMINAL after damage if <= 1
  f_emer = thrust fraction at which the damaged structure carries the accidental load at factor 1.0 on design allowables
           (emergency reduced thrust, not nominal operation)
  progressive collapse: members above 1.0 at the emergency check are removed and the solve repeated until no member exceeds
           1.0 (arrested) or the stiffness matrix turns singular / a member chain fails through (collapse)
Classification: NOMINAL (u_nom <= 1), REDUCED THRUST (f_emer >= 0.30), COAST-ONLY (f_emer < 0.30 but stable at coast loads),
IMMEDIATE REPAIR (collapse or no load path). Spine ties are excluded: they carry a shear-pin release (PROTOTYPE), so an overloaded tie\nreleases the spine laterally instead of failing the cage.
"""
import math

import numpy as np

import analysis as an
import model as mdl

F_MIN_REDUCED = 0.30


def utils(b, fs, scale, factor):
    out = np.zeros(len(b.m.el))
    for i, (e, md, f) in enumerate(zip(b.m.el, b.meta, fs)):
        if f is None or e['kind'] == 'spring' or not e['on'] or md['fam'] in ('iface', 'tie'):
            continue
        s = b.sec[md['group']]; mat = mdl.mat(s['mat'])
        A, I, S = an.tube_props(np.array(s['r']), np.array(s['t']))
        N = scale*f['N']; M = abs(scale)*math.hypot(f['My'], f['Mz'])
        u, _ = an.check(mat, A, I, S, np.array(s['r']), np.array(s['t']), np.array(f['L']), max(-N, 0)*factor/an.LF_ULT,
                        max(N, 0)*factor/an.LF_ULT, M*factor/an.LF_ULT)
        out[i] = float(u)
    return out


def damaged(b, off, dlf, max_rounds=8):
    for i in off:
        b.m.el[i]['on'] = False
    # equipment on a node that lost every member is carried by the neighbouring nodes (its mounts fail over to the next frame)
    moved = {}
    active = {}
    for e in b.m.el:
        if e['on']:
            active[e['a']] = active.get(e['a'], 0)+1; active[e['b']] = active.get(e['b'], 0)+1
    for i in off:
        e = b.m.el[i]
        for n, o in ((e['a'], e['b']), (e['b'], e['a'])):
            if not active.get(n) and b.m.pm.get(n, 0.0) > 0 and active.get(o):
                moved[(n, o)] = b.m.pm[n]
    for (n, o), mval in moved.items():
        share = mval/sum(1 for (n2, _) in moved if n2 == n)
        b.m.pm[o] = b.m.pm.get(o, 0.0)+share
    saved = {n: b.m.pm[n] for (n, _) in moved}
    for n in saved:
        b.m.pm[n] = 0.0
    rec = dict(off=list(off), isolated_nodes=len(saved))
    try:
        r, fs = an.solve(b)
        if not np.isfinite(r['u']).all() or np.abs(r['u']).max() > 50.0:
            raise np.linalg.LinAlgError('mechanism')
        u_ult = utils(b, fs, dlf, an.LF_ULT); u_acc = utils(b, fs, dlf, 1.0)
        rec['u_nom'] = float(u_ult.max()); rec['f_emer'] = float(min(1.0, 1.0/u_acc.max())) if u_acc.max() > 0 else 1.0
        rec['worst'] = int(np.argmax(u_ult)); rec['worst_group'] = b.meta[rec['worst']]['group']
        rec['tip_dx_mm'] = float(np.abs(r['u'][0::6]).max()*1e3)
        # progressive collapse at full thrust, accidental factor 1.0 (a damaged ship whose crew does not reduce thrust)
        chain = []; removed = []
        for _ in range(max_rounds):
            r2, f2 = an.solve(b)
            if not np.isfinite(r2['u']).all() or np.abs(r2['u']).max() > 50.0:
                chain.append('mechanism'); break
            ua = utils(b, f2, dlf, 1.0)
            over = [i for i in np.where(ua > 1.0)[0]]
            if not over:
                break
            k = max(over, key=lambda i: ua[i]); b.m.el[k]['on'] = False; removed.append(int(k)); chain.append(b.meta[k]['group'])
        rec['collapse_chain'] = chain; rec['progressive'] = ('mechanism' in chain) or len(chain) >= max_rounds
        for k in removed:
            b.m.el[k]['on'] = True
        rec['class'] = ('NOMINAL' if rec['u_nom'] <= 1.0 else 'REDUCED THRUST' if rec['f_emer'] >= F_MIN_REDUCED and not rec['progressive']
                        else 'COAST-ONLY' if not rec['progressive'] or rec['f_emer'] > 0.05 else 'IMMEDIATE REPAIR')
        if rec['progressive'] and rec['class'] == 'NOMINAL':
            rec['class'] = 'REDUCED THRUST'
    except Exception as ex:                                   # singular: the damage removed the only load path
        rec.update(u_nom=float('inf'), f_emer=0.0, progressive=True, collapse_chain=['no load path: '+type(ex).__name__], cls='')
        rec['class'] = 'IMMEDIATE REPAIR'
    for i in off:
        b.m.el[i]['on'] = True
    for (n, o), mval in moved.items():
        b.m.pm[o] -= mval/sum(1 for (n2, _) in moved if n2 == n)
    for n, v in saved.items():
        b.m.pm[n] = v
    return rec


def rail_members_at(b, x0, az):
    """The rail element of the bay starting at station x0 on the rail at azimuth az."""
    xs = b.xs; k = min(range(len(xs)), key=lambda i: abs(xs[i]-x0)); na = b.station_nodes[xs[k]][az]; nb = b.station_nodes[xs[k+1]][az]
    return [i for i, e in enumerate(b.m.el) if {e['a'], e['b']} == {na, nb}]


def node_members(b, n):
    return [i for i, e in enumerate(b.m.el) if e['kind'] != 'spring' and n in (e['a'], e['b'])]


def scenarios(b):
    """Damage set per D03: rail bay, rail joint (node), shared node (paired-sector frame node or sector node for 3 rails), whole
    pickup strut, collar chord, keel bay, spine-tie set, double rail bay (both rails of one sector at one station)."""
    rails = b.rail_az(); sc = []
    xs = [-111.25, -55.25, 0.75, 56.75, 84.75]
    for x in xs:
        sc.append((f'rail bay lost at X {x:+.0f}, az {rails[0]:.0f}', rail_members_at(b, x, rails[0])))
    for x in (-55.25, 56.75):
        k = min(range(len(b.xs)), key=lambda i: abs(b.xs[i]-x)); n = b.station_nodes[b.xs[k]][rails[0]]
        sc.append((f'rail joint (node) lost at X {b.xs[k]:+.0f}, az {rails[0]:.0f}', node_members(b, n)))
        # shared node: the sector node between paired rails (6 rails) or the frame node next to the single rail (3 rails)
        if b.rails == 6:
            sec_az = 30.0 if 30.0 in b.station_nodes[b.xs[k]] else min(b.station_nodes[b.xs[k]], key=lambda a: abs(a-30.0))
            pair = [a for a in rails if abs(((a-30.0+180) % 360)-180) < 20]
            mem = sum((node_members(b, b.station_nodes[b.xs[k]][a]) for a in pair), [])
            sc.append((f'shared sector node: both paired-rail joints at X {b.xs[k]:+.0f} (common-mode)', sorted(set(mem))))
        else:
            n2 = b.station_nodes[b.xs[k]][rails[0]]
            sc.append((f'shared sector node at X {b.xs[k]:+.0f} (the single rail joint, common-mode)', node_members(b, n2)))
    if b.rails == 6:
        pair = [a for a in rails if abs(((a-30.0+180) % 360)-180) < 20]
        mem = sum((rail_members_at(b, 0.75, a) for a in pair), [])
        sc.append(('both rails of one sector lost at X +1 (one sector)', mem))
    sc.append(('pickup strut lost (nozzle 0, one of three)', [i for i, md in enumerate(b.meta) if md['fam'] == 'pickup'][:1]))
    ci = [i for i, (e, md) in enumerate(zip(b.m.el, b.meta)) if md['fam'] == 'collar']
    sc.append(('collar chord member lost (sector 30, aft spoke)', [i for i in ci if {b.m.el[i]['a'], b.m.el[i]['b']} & {b.chord[30.0][0][0]}][:1]))
    ki = [i for i, md in enumerate(b.meta) if md['fam'] == 'keel']
    sc.append(('keel bay lost (first keel bay)', ki[:1]))
    return sc


def run(b, dlf):
    return [dict(name=n, **damaged(b, off, dlf)) for n, off in scenarios(b) if off]


def redundancy_penalty(b3_mass, b6_mass):
    return (b6_mass-b3_mass)/1e3
