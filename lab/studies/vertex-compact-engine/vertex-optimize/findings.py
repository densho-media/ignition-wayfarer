#!/usr/bin/env python3
"""Findings of vertex-optimize and the page import (research, not canon).

Reads results/optimize.json (the scan) and results/coils.json (coils.py), recomputes the combination and hydrogen blocks for the research
geometry (optimize.RESEARCH), ranks the refinement scan with its sampling error, writes the findings into results/optimize.json and a slim
copy for the Fusion Engineering page to lab/studies/fusion-ignition/imports/optimize.json.

    python3 lab/studies/vertex-compact-engine/vertex-optimize/findings.py
"""
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE))
import optimize as O  # noqa: E402

AMU = O.AMU
WD, WH = 2 / 5, 3 / 5


def main():
    P = HERE / 'results' / 'optimize.json'
    R = json.loads(P.read_text()); CO = json.loads((HERE / 'results' / 'coils.json').read_text())
    src = json.loads(O.X.SRC.read_text()); fi = json.loads(O.X.FI.read_text())
    nz = fi['ledger']['nozzle']['C1|1']
    key = O.RESEARCH; R['best'] = key
    G = {g['key']: g for g in R['geometries']}
    g0, gb = G['drawn|0'], G[key]
    base = next(r for r in src['levers'] if r['lever'] == 'base')['label']
    ext80 = next(r for r in src['levers'] if r['label'].startswith('Early extraction: 80'))['label']

    def row(geo, pic, lab):
        return next(rw for rw in R['rows'] if rw['geo'] == geo and rw['picture'] == pic and rw['label'] == lab)
    d_b, d_e, b_b, b_e = row('drawn|0', 'vacuum', base), row('drawn|0', 'vacuum', ext80), row(key, 'vacuum', base), row(key, 'vacuum', ext80)
    R['combination'] = dict(drawn=dict(base=d_b, ext80=d_e), best=dict(base=b_b, ext80=b_e),
                            naive=dict(thrust_N=b_b['thrust_N'], heat_over=d_e['heat_over'] * b_b['heat_over'] / d_b['heat_over'],
                                       note='topology thrust gain and extraction heat gain applied together, as if independent'),
                            computed=dict(thrust_N=b_e['thrust_N'], heat_over=b_e['heat_over'], exhaust_m_s=b_e['exhaust_m_s']),
                            cavity=dict(base=row(key, 'cavity', base), ext80=row(key, 'cavity', ext80)))
    m_d = 2.01410 * AMU                        # hydrogen bounds in debris-mass units of the base pulse
    lev = next(r for r in src['levers'] if r['lever'] == 'base'); md = lev['mass_kg'] - lev['fusion_J'] / O.C ** 2
    R['hydrogen'] = [dict(case=c, x=f, I0=rw['impulse_Ns'], **O.h2_bounds(rw, f * md)) for c, rw in (('base', b_b), ('ext80', b_e)) for f in (1.0, 3.0, 10.0)]
    R.pop('coils', None)                       # coils.py is the coil source (round windings of the 3D engine)
    # ranking of the scan (design target, both pictures), sampling error from the debris hit share
    rank = []
    for k, g in G.items():
        v, c = row(k, 'vacuum', base), row(k, 'cavity', base)
        err = math.sqrt(WD ** 2 * g['species']['D']['err'] ** 2 + WH ** 2 * g['species']['He3']['err'] ** 2)
        rank.append(dict(key=k, label=g['label'], thrust_vac_N=v['thrust_N'], thrust_cav_N=c['thrust_N'], heat_vac=v['heat_over'], heat_cav=c['heat_over'],
                         hit_vac=v['hit_share_plasma'], err=err, stored_J=g['stored_J'], coil_t=g['coil_t']))
    rank.sort(key=lambda r: -(r['thrust_vac_N'] + r['thrust_cav_N']))
    moved = [r for r in rank if r['key'] != 'drawn|0']
    T4 = sorted(4 * r['thrust_vac_N'] / 1e6 for r in moved if G[r['key']]['dz'] >= 4); tmed = T4[len(T4) // 2]
    tmin, tmax = T4[0], T4[-1]
    hmin = min(f['heat_over'] for f in R['frontier']['vacuum'] + R['frontier']['cavity'])
    cc = {c['id']: c for c in CO['cases']}
    bal0, balb = g0['species']['D']['balance'], gb['species']['D']['balance']
    F = dict(
        burn=(f'Moving the burn aft is the lever: every geometry with the burn 4 m or more aft gives {tmin:.2f}-{tmax:.2f} MN, median {tmed:.2f} MN (four '
              f'engines), against {4 * d_b["thrust_N"] / 1e6:.2f} MN as drawn. The closure factor (x3 to x6), grading and aft spacing mostly stay within the '
              f'sampling error (+-{100 * rank[0]["err"]:.0f} points of debris hit share at {R["n_dir"]} directions, about +-0.1 MN); none is a clear win over x4 at 4 m.'),
        closure=(f'Stronger closure coils matter mainly through the capture current: with the burn 4 m aft the field that stops the pulse needs '
                 f'{gb["stored_J"] / 1e9:.0f} GJ per engine instead of {g0["stored_J"] / 1e9:.0f} GJ as drawn, still {cc["opt_capture"]["stored_J"] / cc["built"]["stored_J"]:.0f}x '
                 f'the {cc["built"]["stored_J"] / 1e9:.0f} GJ the drawn coils carry.'),
        cavity=(f'Plasma picture: letting the debris expand as an unmagnetised bubble to R_b = {gb["cavity_R_m"]:.1f} m before the field acts changes the '
                f'research result by {100 * (row(key, "cavity", base)["thrust_N"] / b_b["thrust_N"] - 1):+.0f} % in thrust; as drawn the bubble ({g0["cavity_R_m"]:.1f} m) '
                f'reaches nothing. Both pictures bracket a coupled plasma (still not modelled).'),
        pickup=(f'Re-tracing the X-ray and neutron pickup for the moved burn: the hardware covers {100 * gb["sky"]:.0f} % of the sky instead of '
                f'{100 * g0["sky"]:.0f} %, so the design-target heat falls from {d_b["heat_over"]:,.0f}x to {b_b["heat_over"]:,.0f}x the radiator share '
                f'(ENG-065 had kept the old pickup and reported 1,967x).'),
        balance=(f'Momentum balance (D debris, units of one particle momentum): as drawn the ship gets {bal0["ship"]:.2f}, made of {bal0["via_hardware"]:+.2f} from '
                 f'particles striking the shield and closure hardware and {bal0["via_field"]:+.2f} through the field: a pusher plate, not a nozzle. With the burn 4 m '
                 f'aft the ship gets {balb["ship"]:.2f}, {balb["via_field"]:+.2f} through the field and {balb["via_hardware"]:+.2f} by impact. Closure '
                 f'{max(bal0["closure"], balb["closure"]):.0e}.'),
        combination=(f'Combined, not multiplied: research geometry plus 80 % early extraction gives {4 * b_e["thrust_N"] / 1e6:.2f} MN at {b_e["heat_over"]:,.0f}x; '
                     f'multiplying the separate gains would claim {4 * b_b["thrust_N"] / 1e6:.2f} MN at {R["combination"]["naive"]["heat_over"]:,.0f}x. Extraction moves '
                     f'energy into fast products that carry almost no momentum, so it removes the thrust the topology won; the two levers compete.'),
        hydrogen=('Hydrogen reaction mass: inelastic mixing keeps the impulse and lowers the exhaust speed; only ideal elastic transfer (no physics yet) '
                  f'raises thrust, x{R["hydrogen"][2]["elastic"]["impulse_Ns"] / R["hydrogen"][2]["I0"]:.2f} with ten times the debris mass. Coupling OPEN.'),
        coils=(f'Coils at the capture current, burn 4 m aft: {cc["opt_capture"]["stored_J"] / 1e9:.0f} GJ per engine, {cc["opt_capture"]["B_peak_max_T"]:.0f} T at the '
               f'windings (above the 20-25 T REBCO practice), {cc["opt_capture"]["Fx_max_MN"] / 1e3:.1f} GN axial on one coil, a {cc["opt_capture"]["quench_dump_s"] / 60:.0f} '
               f'min dump at 50 kA and 10 kV, or {cc["opt_capture"]["quench_copper_t"]:,.0f} t of copper to absorb it. The drawn research geometry (closure x4 at the '
               f'as-built current) carries {cc["opt_built"]["stored_J"] / 1e9:.0f} GJ, {cc["opt_built"]["B_peak_max_T"]:.1f} T, {cc["opt_built"]["structure_t"]:.0f} t of hoop '
               f'structure; it does not capture the pulse.'),
        frontier='Lowest heat anywhere: ' + ', '.join(f'{f["label"]} ({f["geo"]}) {4 * f["thrust_N"] / 1e6:.2f} MN at {f["heat_over"]:,.0f}x' for f in R['frontier']['vacuum'][:2]),
        none=f'No geometry, lever or combination closes: the lowest heat found is {hmin:,.0f}x the radiator share, and thrust stays near a twentieth of the 21.8 MN need.')
    R['findings'] = F; R['ranking'] = rank
    P.write_text(json.dumps(R, indent=1))
    # ---- slim page import ----
    def gv(g):
        return dict(key=g['key'], label=g['label'], dz=g['dz'], fc=g['fc'], k=g['k'], B_burn_T=g['B_burn_T'], cavity_R_m=g['cavity_R_m'],
                    coil_t=g['coil_t'], stored_J=g['stored_J'], sky=g['sky'],
                    sp={s: dict(hit=v['hit'], cos=v['cos'], err=v['err']) for s, v in {'p': g['species']['p14.7'], 'a': g['species']['a3.6'], 'D': g['species']['D'],
                                                                                         'He3': g['species']['He3'], 'D_cav': g['species']['D_cav'], 'He3_cav': g['species']['He3_cav']}.items()},
                    bal=g['species']['D']['balance'])
    keep = ('thrust_N', 'exhaust_m_s', 'heat_over', 'hit_share_plasma', 'deposited_kg_s', 'impulse_Ns', 'xray_share')
    S = lambda r: {k: r[k] for k in keep}
    baseT = {k: dict(vacuum=S(row(k, 'vacuum', base)), cavity=S(row(k, 'cavity', base))) for k in G}
    Sb = gb['species']
    research = dict(key=key, label=gb['label'], dz=gb['dz'], burn_x_drawn=CO['burn_x_drawn'], burn_x_moved=CO['burn_x_moved'], rings=CO['research_geometry'],
                    clearances=CO['clearances'], blades=CO['blades'],
                    nozzle=dict(eta=WD * Sb['D']['cos'] + WH * Sb['He3']['cos'], hit=WD * Sb['D']['hit'] + WH * Sb['He3']['hit'], pickup=nz['pickup'] * gb['pickup_scale'],
                                budget_W=nz['budget_W'], source='vertex-optimize research geometry, vacuum picture'))
    K = R['combination']
    comb = {k: ({kk: S(vv) for kk, vv in v.items()} if k in ('drawn', 'best', 'cavity') else v) for k, v in K.items()}
    coils = [{k: v for k, v in c.items() if k != 'coils'} for c in CO['cases']]
    asm = [dict(title='Burn moved 4 m aft (target flight extended)', why='Forward field lines from the drawn burn end on the shield and closure coils, so most plasma struck them.',
                effect=f'struck plasma {pct(d_b["hit_share_plasma"])} to {pct(b_b["hit_share_plasma"])}, thrust {4 * d_b["thrust_N"] / 1e6:.2f} to {4 * b_b["thrust_N"] / 1e6:.2f} MN',
                problem='ENG-066', closes=False),
           dict(title='Closure coils C1, C2, L1 rewound at four times the ampere-turns', why='A stronger closing mirror turns the forward-going field lines aft.',
                effect=f'capture energy {g0["stored_J"] / 1e9:,.0f} to {gb["stored_J"] / 1e9:.0f} GJ; still {cc["opt_capture"]["B_peak_max_T"]:.0f} T at the windings', problem='ENG-067', closes=False),
           dict(title='Hoop bands with embedded 20 K channels', why='One part carries the hoop load, supports the cold mass and cools it instead of three attached parts.',
                effect=f'{cc["opt_built"]["structure_t"]:.0f} t of bands; C2 to L1 clearance {next(c for c in CO["clearances"] if c["pair"] == "C2-L1")["gap_m"]:.2f} m', problem='ENG-068', closes=False),
           dict(title='Quench dump busbars and resistor', why='The stored field energy must leave the coils safely when a winding quenches.',
                effect=f'{cc["opt_built"]["stored_J"] / 1e9:.0f} GJ to dump at the drawn current, {cc["opt_capture"]["stored_J"] / 1e9:.0f} GJ at capture', problem='ENG-069', closes=False),
           dict(title='Thermal blades re-aimed at the moved burn', why='Edge-on blades only work when they point at the burn.',
                effect=f'turned up to {CO["blades"]["max_turn_deg"]:.0f} deg; the alignment budget is a fraction of a milliradian', problem='ENG-070', closes=False),
           dict(title='Early extraction at the source (no hardware)', why='Fast products leaving the target early take energy out of the X-rays.',
                effect=f'heat {b_b["heat_over"]:,.0f}x to {b_e["heat_over"]:,.0f}x, thrust {4 * b_b["thrust_N"] / 1e6:.2f} to {4 * b_e["thrust_N"] / 1e6:.2f} MN', problem='ENG-072', closes=False)]
    imp = dict(cls='SAMPLED', study='vertex-optimize', source='lab/studies/vertex-compact-engine/vertex-optimize (optimize.py, coils.py, findings.py)', n_dir=R['n_dir'],
               research=research, geos=[gv(g) for g in R['geometries']], base=baseT, combination=comb, hydrogen=R['hydrogen'], coils=coils, findings=F,
               ranking=[{k: v for k, v in r.items()} for r in rank], frontier=R['frontier'], assembly=asm)
    out = ROOT / 'lab/studies/fusion-ignition/imports/optimize.json'
    out.write_text(json.dumps(imp, indent=1))
    for k, v in F.items():
        print(f'{k}: {v}')
    print('wrote', out.relative_to(ROOT), out.stat().st_size, 'bytes')


def pct(x):
    return f'{100 * x:.0f} %'


if __name__ == '__main__':
    main()
