"""WSI Checkpoint 4: whole-spacecraft review. Reconverges the joint point with the PSA closure structure, adds the WSI-F hardware, and
assembles the deliverables: starting-point vs integrated comparison, convergence history, integrated ledger, load cases and stability,
SSI-1.2 changes, thermal and electrical ledgers, problem register, owner decisions and readiness.

    python3 work/wayfarer-systems-integration/wsi/review.py [closure_tag ...]     # -> results/wsi_cp4.json

STUDY / PROTOTYPE, Track F working configuration (WSI-0.2 candidate); noncanon; production unchanged.
"""
import glob
import json
import sys

import common
from common import G0, PSA, R, THRUST_N, issa_point, J
import coupled

CLOSURE = PSA/'results/p3_closure'
WSI_ADD = [dict(item='dedicated shutdown store (C-01): high-power Li-ion / hybrid capacitor pack, services bus x -92..-80', owner='ISSA electrical', cls='NEW (Track R)'),
           dict(item='LOW tab growth at the joint point (C-14): one-loop-lost nominal, ammonia panels 5 kg/m2', owner='ISSA thermal', cls='NEW (PROTOTYPE)'),
           dict(item='He-3 destratification pumps (C-11), 6 vessels', owner='ISSA cryo', cls='NEW (PROTOTYPE)')]


def closures():
    out = {}
    for f in sorted(glob.glob(str(CLOSURE/'*.json'))):
        d = json.loads(open(f).read()); tag = d['tag']
        st = d['stability']; lam = min((s['lam'] or 99.0) for s in st) if st else None
        f1 = min((s.get('f1_Hz') or s.get('f1') or 0.0) for s in st) if st else None
        out[tag] = dict(tag=tag, rotor=d['rotor'], deck=d['deck'], mats=d.get('mats'), structure_t=d['structure_t'], stiffening_t=d['stiffening_t'],
                        strength_t=d['strength_members_t']+d['strength_joints_t'], lam_min=lam, f1_min_Hz=f1, closed=d['closed'], passes=d.get('passes'),
                        added_by_group_t=d.get('added_by_group_t', {}), stability=st, file=f.split('/')[-1])
    return out


def point(struct_t, extra_t):
    P = issa_point(struct_t+coupled.NONFE_T if False else struct_t-common.STRUCT_LINE_T+extra_t)
    return P


def main(tags):
    rem = J(R/'wsi_remaining.json'); cp1 = J(R/'wsi_cp1.json'); cp2 = J(R/'wsi_cp2.json'); mem = J(R/'wsi_members.json')
    store_t = rem['c01']['dedicated']['mass_t']; low_t = rem['c14']['low_growth']['area_m2']['one_loop_lost']*5.0/1e3; mix_t = 6*0.05
    add = [dict(w, t=t) for w, t in zip(WSI_ADD, (store_t, low_t, mix_t))]; add_t = sum(a['t'] for a in add)
    nonfe = 22.45+24.78                                                                 # PSA casing + rotating ring structure (not in the FE)
    C = closures(); cands = []
    for tag, c in C.items():
        st = c['structure_t']+nonfe
        P = issa_point(st-common.STRUCT_LINE_T+add_t); L = P['L']; T = P['T']
        cands.append(dict(c, structure_total_t=st, departure_t=L['departure_t'], propellant_t=L['propellant_t'], ship_length_m=T['ship_length_m'],
                          a_end_g=THRUST_N/(L['end_t']*1e3)/G0, coupling_t_per_t=(L['departure_t']-cp1['starting_points'][2]['departure_t'])/max(st-1222.9+add_t, 1e-6)))
    pref = None
    for t in tags:
        pref = next((c for c in cands if c['tag'] == t), pref)
    if pref is None and cands:
        pref = min(cands, key=lambda c: (not c['closed'], -min(c['lam_min'] or 0, 1.95), c['departure_t']))
    hist = []
    if pref:
        # convergence: does the PSA closure mass (sized at S-COMB) still hold at the reconverged point? loads ~ T x shares (fixed thrust)
        coupled.REF = coupled.shares(issa_point(1222.9-common.STRUCT_LINE_T))
        st = pref['structure_total_t']
        for k in range(10):
            P = issa_point(st-common.STRUCT_LINE_T+add_t); s = coupled.shares(P)
            k_deck = s['farm']/coupled.REF['farm']; k_cage = s['ahead']/coupled.REF['ahead']
            st_new = pref['structure_total_t']*(0.5*k_deck+0.5*k_cage)
            hist.append(dict(it=k+1, structure_t=st_new, departure_t=P['L']['departure_t'], propellant_t=P['L']['propellant_t'], ship_m=P['T']['ship_length_m'],
                             farm_share=s['farm'], ahead_share=s['ahead']))
            if abs(st_new-st) < 0.5:
                st = st_new; break
            st = st_new
        Pf = issa_point(st-common.STRUCT_LINE_T+add_t)
        pref['reconverged'] = dict(structure_t=st, departure_t=Pf['L']['departure_t'], propellant_t=Pf['L']['propellant_t'], loaded_t=Pf['T']['loaded_t'],
                                   tankage_t=Pf['L']['tankage_t'], end_t=Pf['L']['end_t'], ship_length_m=Pf['T']['ship_length_m'], farm_added_m=Pf['T']['added_length_m'],
                                   a_end_g=THRUST_N/(Pf['L']['end_t']*1e3)/G0, history=hist,
                                   shift_vs_sizing_point_pct=100*(Pf['L']['departure_t']/cp1['starting_points'][2]['departure_t']-1))
        rows = [r for r in cp1['ledger']['rows'] if r['cat'] == 'HISTORICAL']
        rows += [dict(item=r['item'], t=r['t'], owner=r['owner'], cat=r['cat']) for r in Pf['L']['rows']]
        rows += [dict(item='payload: ECLSS CO2 reserve', t=sum(p['t'] for p in Pf['L']['payload']), owner='ISSA ECLSS', cat='PAYLOAD')]
        rows += [dict(item=f'PSA primary structure {pref["tag"]} (strength {pref["strength_t"]:.0f} + stiffening {pref["stiffening_t"]:.0f} + joints, casing, rotating)',
                      t=st, owner='PSA', cat='STRUCTURE')]
        rows += [dict(item=a['item'], t=a['t'], owner=a['owner'], cat='NEW (WSI)') for a in add]
        rows += [dict(item='tankage (re-solved)', t=Pf['L']['tankage_t'], owner='tankage', cat='TANKAGE'),
                 dict(item='propellant residual + boil-off reserve (carried)', t=Pf['L']['carried_t'], owner='propellant', cat='CARRIED'),
                 dict(item='mission propellant', t=Pf['L']['propellant_t'], owner='propellant', cat='PROPELLANT')]
        tot = sum(r['t'] for r in rows); by = {}
        for r in rows:
            by[r['cat']] = by.get(r['cat'], 0.0)+r['t']
        pref['ledger'] = dict(rows=rows, total_t=tot, by_category_t=by, check=f'ledger {tot:,.1f} t vs departure {Pf["L"]["departure_t"]:,.1f} t')
    out = dict(candidates=cands, preferred=pref, wsi_additions=add, closures_read=list(C))
    (R/'wsi_cp4.json').write_text(json.dumps(out, indent=1, default=float))
    for c in cands:
        print(f"{c['tag']:<22} closed {c['closed']!s:<5} lam {c['lam_min']:.2f} f1 {c['f1_min_Hz'] or 0:.3f} structure {c['structure_total_t']:,.0f} t departure "
              f"{c['departure_t']:,.0f} t ship {c['ship_length_m']:.1f} m")
    if pref:
        r = pref['reconverged']; print('preferred', pref['tag'], {k: (round(v, 1) if isinstance(v, float) else v) for k, v in r.items() if k != 'history'}, pref['ledger']['check'])


if __name__ == '__main__':
    main(sys.argv[1:])
