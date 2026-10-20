"""RAD-003-2026-10-11 (S&E 15!A128, follow-up of RAD-002 15!A122; 40!A74:A85): front-datum radiator growth study. Pure, writes JSON, never
edits canon or geometry. STUDY / NONCANON: the as-built 9 x 0.125 m seams, the aft-root datum and every station stay unchanged (15!E128).

Owner: no forward growth may reduce ring A's current 1.5 m clearance; lead study a front-fixed/compliant front cassette with joint 9 ~0.25 m,
the other eight joints at 0.175/0.20/0.25 m, C/C, SiC, W, Mo, Nb; the truss insulated and independently compliant, NOT assumed cool.

Method: the RAD-002 DIAGNOSTIC 1-D free-strain screen (radiator_expansion geometry and temperature fields, radiator_rad002 alpha(T) and the
0.025 m PROTOTYPE margin), with per-joint seam widths, a front-edge datum on cassette 10 and three truss (carrier) datum schemes:
- AFT    the built global datum at the aft root boom (X -15.925); the truss grows forward and carries the front cassette's datum with it.
- FRONT  the truss's axial datum moved to a new front post at the blade front frame (X 81.149, hull side at T_install); the truss grows
         aft; the aft root boom and the stays become axial slides.
- SPLIT  the built aft-datum truss plus a truss expansion joint at frame 9; the front segment (cassette 10 and the spar) on the front post.
Joint numbering: joint j sits on frame j between cassettes j and j+1, counted from aft; joint 9 (frame 9, X 62.934) is the front-most seam.
No stiffness, friction, creep, bond, pressure or load: closures are kinematic. Temperatures, posts, datums and the truss states are PROTOTYPE.

    python3 src/wayfarer/studies/radiator_rad003.py [--out references/p1_rad003.json]
"""
from pathlib import Path
import argparse
import json
import sys
ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT/'src/wayfarer'), str(ROOT/'src/wayfarer/studies')]
from spec import load
import radiator_expansion as rx
import radiator_rad002 as r2

T0 = rx.T_INSTALL_K
MARGIN = r2.MARGIN_M                      # 0.025 m PROTOTYPE least open gap
JOINT9_M = 0.25
OTHERS_M = (0.175, 0.20, 0.25)
TRUSS_STATES = {                          # PROTOTYPE truss (carrier) temperatures; the owner: do not assume a cool truss
    'COLD_START_100K': 100.0,             # truss still cold-soaked while the sheet is already hot (start-up transient)
    'INSTALL_293K': 293.0,
    'WARM_450K': 450.0,                   # warm-loop level (thermal.loops), insulated truss picking up heat
    'HOT_600K': 600.0,                    # insulation degraded
    'POOR_900K': 900.0,                   # poor insulation
    'UNINSULATED_1800K': 1800.0,          # truss at the sheet temperature
}
SHEET_HOT = ('HOT_UNIFORM', 'ROOT_BAND_COOLER', 'AXIAL_GRADIENT', 'BAY_ISOLATED_COLD')
SCHEMES = ('AFT', 'FRONT', 'SPLIT')
# Source shapes behind radiator_rad002.ALPHA_T (endpoints unchanged; literature-shaped from general references, not re-looked-up here).
ALPHA_SOURCES = {
    'CC_composite': 'in-plane C/C, axial fibres, layup dependent (~0-1e-6 /K near RT rising to ~2-3e-6 /K hot; e.g. Savage, Carbon-Carbon '
                    'Composites, 1993); through-thickness several times higher',
    'SiC': 'sintered/CVD SiC (Munro 1997, J. Phys. Chem. Ref. Data 26:1195; ~3.3-3.6e-6 /K near RT, ~5.5-6e-6 /K near 1800 K)',
    'W': 'tungsten (Touloukian TPRC vol. 12; White & Minges 1997, Int. J. Thermophys. 18:1269; ~4.4e-6 /K RT, ~5.5-6e-6 /K hot)',
    'Mo_TZM': 'Mo/TZM (Touloukian TPRC vol. 12; ~5e-6 /K RT, ~7-7.5e-6 /K near 1800 K)',
    'Nb_C103': 'Nb C-103 (Touloukian TPRC vol. 12 for Nb; C-103 producer data ~7e-6 /K RT, ~9e-6 /K near 1800 K)',
    'owner_equivalent': 'secant 5.46e-6 /K = the owner ~1.5 m aggregate over 182.149 m (40!A64), not a material (15!H122)',
}


def geometry(s, seams):
    """The built blade cut at the built frames with per-joint seam widths (len 9), seams centred on the frames."""
    g = rx.geometry(s); fr = g['frames']; n = len(fr)-1; h = [w/2 for w in seams]
    g['cassettes'] = [dict(bay=i+1, x0=fr[i]+(h[i-1] if i > 0 else 0.0), x1=fr[i+1]-(h[i] if i < n-1 else 0.0), mid=(fr[i]+fr[i+1])/2)
                      for i in range(n)]
    g['seams'] = list(seams); g['front_post_x'] = fr[-1]
    return g


def carrier(g, scheme, eps_c, Tc):
    """Carrier axial displacement vs the hull for cassette index i at x."""
    e = eps_c(Tc); xg, xf, x9 = g['datum_x'], g['front_post_x'], g['frames'][-2]; last = len(g['cassettes'])-1
    if scheme == 'AFT':
        return lambda i, x: e*(x-xg)
    if scheme == 'FRONT':
        return lambda i, x: e*(x-xf)
    return lambda i, x: e*(x-xf) if (i == last or x > x9) else e*(x-xg)          # SPLIT


def kin(g, eps, T, eps_c, Tc, scheme, front_edge=True):
    cs = g['cassettes']; last = len(cs)-1; br = g['frames']; C = carrier(g, scheme, eps_c, Tc)
    dat = [c['mid'] for c in cs]
    if front_edge:
        dat[-1] = cs[-1]['x1']
    edge = lambda i, x, v: C(i, dat[i])+rx.integrate(lambda q: eps(T(q, v)), dat[i], x, br)
    vs = {'root_edge': 0.0, 'trunk': g['trunk_v'], 'outer_edge': g['width']}
    joints = []
    for i in range(last):
        a, b, xj, w = cs[i], cs[i+1], br[i+1], g['seams'][i]
        cl = {k: edge(i, a['x1'], v)-edge(i+1, b['x0'], v) for k, v in vs.items()}
        slip = max(abs(edge(k, x, v)-C(k, xj)) for k, x in ((i, a['x1']), (i+1, b['x0'])) for v in vs.values())
        joints.append(dict(joint=i+1, x=xj, seam_m=w, closure_m=cl, gap_m=w-max(cl.values()), max_open_m=w-min(cl.values()),
                           bellows_m=cl['trunk'], shoe_slip_m=slip))
    front_sheet = max(edge(last, cs[-1]['x1'], v) for v in vs.values()); front_truss = C(last, g['front_post_x'])
    front = max(front_sheet, front_truss)
    aft = min(min(edge(0, cs[0]['x0'], v) for v in vs.values()), C(0, br[0]))
    slides = [dict(name=m['name'], x=m['x'], slip_m=C(0, m['x'])) for m in g['slides']]
    if scheme in ('FRONT',):
        slides.append(dict(name='Aft_Root_Boom (datum -> slide)', x=g['datum_x'], slip_m=C(0, g['datum_x'])))
    xg = g['datum_x']; k5 = next(k for k, c in enumerate(cs) if c['x0'] <= xg <= c['x1'])
    loop = edge(k5, xg, g['trunk_v'])                                              # sheet at the aft-root hull exit vs the hull
    truss_joint = C(last-1, br[-2])-C(last, br[-2]) if scheme == 'SPLIT' else 0.0  # closure of the truss expansion joint at frame 9
    e = g['ends']
    return dict(joints=joints, min_gap_m=min(j['gap_m']-0 for j in joints),
                min_margin_m=min(j['gap_m'] for j in joints), joint9_gap_m=joints[-1]['gap_m'],
                others_min_gap_m=min(j['gap_m'] for j in joints[:-1]), max_open_m=max(j['max_open_m'] for j in joints),
                max_shoe_slip_m=max(j['shoe_slip_m'] for j in joints), bellows_max_m=max(abs(j['bellows_m']) for j in joints),
                bellows_joint9_m=joints[-1]['bellows_m'], front_motion_m=front, aft_motion_m=aft,
                ring_A_sweep_to_spar_m=e['ring_A_sweep_to_spar_front']-front, collar_hoop_to_spar_m=e['collar_hoop_to_spar_front']-front,
                thrust_ring_face_to_aft_frame_m=e['thrust_ring_face_to_aft_frame']+aft,
                max_global_slide_m=max(abs(m['slip_m']) for m in slides), global_slides=slides,
                root_loop_m=loop, truss_joint_closure_m=truss_joint)


def area(g, seams):
    """READBACK ONLY: non-emitting seam planform per blade face over the emitting width (ribbon minus root band, as 40!F76); Sheets owns area."""
    w = g['width']-g['band']; built = 9*0.125*w; new = sum(seams)*w
    return dict(nonemitting_per_face_m2=new, delta_vs_built_per_face_m2=new-built, net_per_face_m2_readback=4978.16-(new-built),
                fraction_of_built_net=(new-built)/4978.16, delta_three_blades_both_faces_m2=6*(new-built))


def combo(s, m, mc, seams, scheme, Tc_name, front_edge=True):
    """All sheet states at one truss state (cold soak pairs with the truss at 100 K and 293 K)."""
    g = geometry(s, seams); tc = rx.cases(g); Tc = TRUSS_STATES[Tc_name]; out = {}
    for st in SHEET_HOT:
        out[st] = kin(g, m['eps'], tc[st]['T'], mc['eps'], Tc, scheme, front_edge)
    for name, t in (('COLD_SOAK/truss100', 100.0), ('COLD_SOAK/truss293', 293.0)):
        out[name] = kin(g, m['eps'], tc['COLD_SOAK']['T'], mc['eps'], t, scheme, front_edge)
    w = lambda k: min(r[k] for r in out.values()); W = lambda k: max(r[k] for r in out.values())
    hot = out['HOT_UNIFORM']; cold = out['COLD_SOAK/truss100']
    stroke = max(max(r['joints'][j]['bellows_m'] for r in out.values())-min(r['joints'][j]['bellows_m'] for r in out.values()) for j in range(9))
    s_ = dict(min_gap_m=w('min_gap_m'), joint9_min_gap_m=w('joint9_gap_m'), others_min_gap_m=w('others_min_gap_m'),
              ring_A_min_m=w('ring_A_sweep_to_spar_m'), collar_min_m=w('collar_hoop_to_spar_m'), thrust_ring_min_m=w('thrust_ring_face_to_aft_frame_m'),
              max_shoe_slip_m=W('max_shoe_slip_m'), max_global_slide_m=W('max_global_slide_m'), bellows_max_m=W('bellows_max_m'),
              bellows_hot_m=hot['bellows_max_m'], bellows_joint9_hot_m=hot['bellows_joint9_m'], bellows_stroke_range_m=stroke,
              bellows_strain=W('bellows_max_m')/g['bellows_length'], root_loop_hot_m=hot['root_loop_m'], root_loop_cold_m=cold['root_loop_m'],
              truss_joint_closure_m=W('truss_joint_closure_m'), max_open_m=W('max_open_m'), front_motion_max_m=W('front_motion_m'))
    fails = []
    if s_['min_gap_m'] < MARGIN-1e-9:
        fails.append(f"seam margin {s_['min_gap_m']:+.3f} < {MARGIN}")
    if s_['ring_A_min_m'] < g['ends']['ring_A_min']-1e-9:
        fails.append(f"ring A {s_['ring_A_min_m']:.3f} < 1.5")
    if s_['collar_min_m'] <= 0:
        fails.append('collar')
    if s_['thrust_ring_min_m'] <= 0:
        fails.append('thrust ring')
    if s_['max_shoe_slip_m'] > g['travel']+1e-9:
        fails.append(f"shoe slip {s_['max_shoe_slip_m']:.3f} > {g['travel']}")
    if s_['max_global_slide_m'] > g['travel']+1e-9:
        fails.append(f"global slide {s_['max_global_slide_m']:.3f} > {g['travel']}")
    s_['fails'] = fails; s_['pass'] = not fails
    return s_, out


def truss_limits(g, mc):
    """FRONT scheme: truss temperatures (same hull at T_install) at which the aft-most stay slide uses the 0.20 m travel and at which the
    truss aft end reaches the thrust-ring face (sheet aft growth ignored here; it is reported per combination)."""
    xf = g['frames'][-1]; arm = max(xf-m['x'] for m in g['slides']); aft_arm = xf-g['frames'][0]
    def solve(target):
        lo, hi = T0, 3000.0
        if mc['eps'](hi)*1 <= 0:
            return None
        for _ in range(60):
            mid = (lo+hi)/2
            lo, hi = (mid, hi) if mc['eps'](mid) < target else (lo, mid)
        return round(lo, 1)
    return dict(slide_travel_K=solve(g['travel']/arm), slide_arm_m=arm, thrust_ring_K=solve(g['ends']['thrust_ring_face_to_aft_frame']/aft_arm))


def run():
    s, *_ = load(ROOT); g0 = rx.geometry(s); mats = r2.materials(g0)
    order = ('owner_equivalent', 'CC_composite', 'SiC', 'W', 'Mo_TZM', 'Nb_C103')
    sets = {'built_9x0.125': [0.125]*9, **{f'8x{w:.3f}+j9_0.25': [w]*8+[JOINT9_M] for w in OTHERS_M}}
    res = {}
    for name in order:
        m = mats[name]; rm = dict(source=ALPHA_SOURCES[name], kind=m['kind'], secant_alpha=m['secant'],
                                  free_growth_hot_m=m['eps'](rx.T_HOT_K)*g0['d']['blade_length_m'], combos={})
        for tm_name in ('same', 'CC_composite'):
            if tm_name == 'CC_composite' and name == 'CC_composite':
                continue
            mc = m if tm_name == 'same' else mats['CC_composite']
            for sname, seams in sets.items():
                for scheme in SCHEMES:
                    if sname == 'built_9x0.125' and scheme != 'AFT':
                        continue
                    for tn in TRUSS_STATES:
                        fe = sname != 'built_9x0.125'
                        key = f'{sname}|{scheme}|truss_{tm_name}|{tn}'
                        rm['combos'][key] = combo(s, m, mc, seams, scheme, tn, front_edge=fe)[0]
        # joint-9 and other seams needed (closure + margin) for the lead FRONT scheme with a same-material truss, by truss state
        need = {}
        for tn in TRUSS_STATES:
            _, out = combo(s, m, m, [0.25]*9, 'FRONT', tn)
            j9 = max(max(r['joints'][-1]['closure_m'].values()) for r in out.values())
            oth = max(max(max(j['closure_m'].values()) for j in r['joints'][:-1]) for r in out.values())
            need[tn] = dict(joint9_seam_needed_m=j9+MARGIN, other_seam_needed_m=oth+MARGIN)
        rm['seams_needed_FRONT_same_truss'] = need
        rm['FRONT_truss_limits_K'] = {tm: truss_limits(g0, mats[tm] if tm != 'same' else m) for tm in ('same', 'CC_composite')}
        res[name] = rm
    # truss temperature where the FRONT scheme's slides use the 0.20 m travel (truss same material), and the SPLIT truss-joint stroke
    detail_key = '8x0.200+j9_0.25'
    _, detail = combo(s, mats['owner_equivalent'], mats['owner_equivalent'], sets[detail_key], 'FRONT', 'WARM_450K')
    return dict(
        status='DIAGNOSTIC_STUDY_NONCANON (RAD-003-2026-10-11, 15!A128; STUDY / CURRENT 9x0.125 m UNCHANGED)',
        method='RAD-002 1-D free-strain screen on the RAD-DATUM rig: integrated alpha(T), per-joint seams, front-edge datum on cassette 10, '
               'truss datum schemes AFT/FRONT/SPLIT, truss temperature swept; no stiffness, friction, creep, bond, pressure or load.',
        joint_numbering='joint j on frame j between cassettes j and j+1 from aft; joint 9 = frame 9 at X 62.934, the front-most seam',
        margin_m=MARGIN, alpha_T=r2.ALPHA_T, alpha_sources=ALPHA_SOURCES, truss_states_K=TRUSS_STATES,
        sheet_states=list(SHEET_HOT)+['COLD_SOAK/truss100', 'COLD_SOAK/truss293'],
        built_end_clearances_m=g0['ends'], front_post_x_m=g0['frames'][-1], global_datum_x_m=g0['datum_x'],
        area_readback={k: area(g0, v) for k, v in sets.items()},
        materials=res,
        detail_owner_equivalent_FRONT_WARM450_8x0p20=dict((k, {kk: vv for kk, vv in v.items() if kk != 'joints'} | dict(
            joints=[dict(joint=j['joint'], seam_m=j['seam_m'], gap_m=j['gap_m'], bellows_m=j['bellows_m'], shoe_slip_m=j['shoe_slip_m'])
                    for j in v['joints']])) for k, v in detail.items()))


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('--out', type=Path, default=ROOT/'references/p1_rad003.json'); a = ap.parse_args()
    r = run()
    a.out.write_text(json.dumps(r, indent=1, default=float)+'\n')
    for name, m in r['materials'].items():
        for k, c in m['combos'].items():
            if '|truss_same|' in k or 'built' in k:
                print(f"{name:16s} {k:52s} gap {c['min_gap_m']:+.3f} j9 {c['joint9_min_gap_m']:+.3f} ringA {c['ring_A_min_m']:.3f} "
                      f"slide {c['max_global_slide_m']:.3f} slip {c['max_shoe_slip_m']:.3f} bel {c['bellows_max_m']:.3f} {'PASS' if c['pass'] else 'FAIL '+'; '.join(c['fails'])}")
    print(a.out)
