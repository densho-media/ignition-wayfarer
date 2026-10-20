"""RAD-002-2026-10-10 (S&E 15!A122, 40!A74:A85, 98!A88, OD-007): material-led comparison of the radiator expansion options, built on the
RAD-DATUM free-strain rig (radiator_expansion.py). Pure, writes JSON, never edits canon or geometry. The as-built 182.149 m blade, nine
0.125 m seams and the aft-root datum stay the WORKING geometry; candidate seams are not for the production mesh (15!G122).

What it adds to the rig (15!G122: discrete expansion states, gradients, materials, seam closure margin, tip/collar/stay displacement, bow,
stress, feed routes, non-emitting area, ring A clearance):
- alpha(T): each material's CTE rises linearly with temperature (DIAGNOSTIC literature-shaped endpoints whose mean over 293-1800 K is the
  rig's secant value), integrated, so cooler parts (root band, a cooler front, a warm truss, a cold soak) grow less than the secant says;
  15!I122, 40!A77: delta L = L0 x integral alpha(T) dT. The owner's ~1.5 m equivalent stays a secant (not tied to a material, 15!H122).
- Options: nine seams of 0.125-0.25 m, and 10-13 cassettes at 0.125 m, per material and temperature state; closure margin, shoe slip, the
  front's motion against the collar, spar and ring A sweep, the bellows stroke and the seams' non-emitting planform per blade face (the
  emitting width, ribbon minus root band, as 40!F76; Sheets owns area, view factor and heat, 40!A78).
- Truss: the carrier (same material as the sheet unless named) at 293-600 K, and the truss temperature that uses up each end clearance.
- Stress indicator: the strain needed to absorb a closed seam's overrun inside one cassette, times a hot elastic modulus: a magnitude that
  says a closed seam is not acceptable, not a stress analysis (bonds, creep and loads are OPEN, 40!F77).

    python3 src/wayfarer/studies/radiator_rad002.py [--out runs/<stamp>-rad002]
"""
from pathlib import Path
import argparse
import datetime
import json
import sys
ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT/'src/wayfarer'), str(ROOT/'src/wayfarer/studies')]
from spec import load
import radiator_expansion as rx

T0, TH = rx.T_INSTALL_K, rx.T_HOT_K
# DIAGNOSTIC: alpha at T0 and at TH (1/K), linear between; mean equals the rig's secant. E: rough elastic modulus near 1500-1800 K (GPa).
ALPHA_T = {
    'CC_composite': dict(a0=0.3e-6, a1=2.7e-6, E_GPa=70, note='in-plane, axial fibres; through-thickness CTE several times higher'),
    'SiC': dict(a0=3.6e-6, a1=6.0e-6, E_GPa=380, note='monolithic'),
    'W': dict(a0=4.4e-6, a1=5.6e-6, E_GPa=350, note=''),
    'Mo_TZM': dict(a0=5.1e-6, a1=7.3e-6, E_GPa=280, note=''),
    'Nb_C103': dict(a0=7.0e-6, a1=9.0e-6, E_GPa=85, note=''),
}
SEAMS = (0.125, 0.15, 0.175, 0.20, 0.25)
CASSETTES = (10, 11, 12, 13)
TRUSS_K = (293.0, 350.0, 400.0, 450.0, 600.0)
MARGIN_M = 0.025     # PROTOTYPE: least open gap a seam must keep in every state (tolerance, creep, assembly); the owner calls 1 mm none (98!D88)
STATES = ('HOT_UNIFORM', 'ROOT_BAND_COOLER', 'AXIAL_GRADIENT', 'BAY_ISOLATED_COLD', 'COLD_SOAK')


def strain_T(a0, a1):
    """Free strain from T0 to T with alpha linear in T: integral of a0 + (a1-a0)(t-T0)/(TH-T0) dt."""
    k = (a1-a0)/(TH-T0)
    return lambda T: a0*(T-T0)+k*(T-T0)**2/2


def materials(g):
    L = g['d']['blade_length_m']; dT = TH-T0; out = {}
    for name, m in ALPHA_T.items():
        out[name] = dict(eps=strain_T(m['a0'], m['a1']), secant=(m['a0']+m['a1'])/2, E_GPa=m['E_GPa'], note=m['note'], kind='alpha(T)')
    a = g['aggregate']/(L*dT)
    out['owner_equivalent'] = dict(eps=lambda T, a=a: a*(T-T0), secant=a, E_GPa=None, note='the owner ~1.5 m aggregate as a secant (40!A64)', kind='secant')
    return out


def area(g, seam, bays):
    """Non-emitting seam planform per blade face (m2): the joints times the seam over the emitting width (ribbon minus the root band)."""
    return (bays-1)*seam*(g['width']-g['band'])


def option(s, m, seam, bays):
    g = rx.geometry(s, seam, bays); tc = rx.cases(g); out = {}
    for st in STATES:
        r = rx.run_case(g, None, tc[st]['T'], 'a_carrier_install', 'MID_BAY', eps=m['eps'])
        over = max(0.0, -r['min_gap_m']); cl = r['clearances_m']
        out[st] = dict(min_gap_m=r['min_gap_m'], max_open_gap_m=r['max_open_gap_m'], max_shoe_slip_m=r['max_shoe_slip_m'],
                       front_m=r['front_motion_m'], aft_m=r['aft_motion_m'], spar_to_collar_m=cl['collar_hoop_to_spar_front'],
                       ring_A_sweep_to_spar_m=cl['ring_A_sweep_to_spar_front'], bellows_m=r['feed']['max_bellows_takeup_m'],
                       bellows_strain=r['feed']['bellows_axial_strain'], flags=r['flags'],
                       overrun_stress_MPa=None if not (over and m['E_GPa']) else round(m['E_GPa']*1e3*over/g['bay_length'], 1))
    return dict(seam_m=seam, cassettes=bays, joints=bays-1, cassette_length_m=g['bay_length'], nonemitting_per_face_m2=area(g, seam, bays),
                delta_vs_built_m2=area(g, seam, bays)-area(g, 0.125, 10), states=out)


def front_fixed(s, m):
    """The front cassette held at its front edge (the rest at mid-bay): the front stays at the collar and ring A clearances while the
    carrier is cool, and joint 9 takes the front cassette's whole growth on top of its neighbour's half."""
    g = rx.geometry(s); tc = rx.cases(g); out = {}
    for st in ('HOT_UNIFORM', 'COLD_SOAK'):
        r = rx.run_case(g, None, tc[st]['T'], 'a_carrier_install', 'FRONT_FIXED', eps=m['eps'])
        j9 = r['joints'][-1]
        out[st] = dict(joint9_closure_m=max(j9['closure_m'].values()), joint9_gap_m=j9['gap_m'], other_min_gap_m=min(j['gap_m'] for j in r['joints'][:-1]),
                       front_m=r['front_motion_m'], ring_A_sweep_to_spar_m=r['clearances_m']['ring_A_sweep_to_spar_front'],
                       joint9_seam_for_margin_m=max(j9['closure_m'].values())+MARGIN_M, max_shoe_slip_m=r['max_shoe_slip_m'])
    return out


def truss(s, m):
    g = rx.geometry(s); tc = rx.cases(g); out = []
    for Tc in TRUSS_K:
        r = rx.run_case(g, None, tc['HOT_UNIFORM']['T'], 'a_carrier_T', 'MID_BAY', eps=m['eps'], Tc=Tc)
        out.append(dict(truss_K=Tc, front_m=r['front_motion_m'], aft_m=r['aft_motion_m'], max_global_slide_m=r['max_global_slide_m'],
                        max_shoe_slip_m=r['max_shoe_slip_m'], min_gap_m=r['min_gap_m'], clearances_m=r['clearances_m'], flags=r['flags']))
    return out


def run(out_dir):
    s, *_ = load(ROOT); g = rx.geometry(s); mats = materials(g)
    check = {w: round(4978.16-(area(g, w, 10)-area(g, 0.125, 10)), 4) for w in SEAMS}     # vs 40!C81:C85 (net hot area per blade face)
    res = {}
    for name, m in mats.items():
        res[name] = dict(kind=m['kind'], secant_alpha=m['secant'], E_GPa=m['E_GPa'], note=m['note'],
                         free_growth_hot_m=m['eps'](TH)*g['d']['blade_length_m'],
                         seams={f'{w:.3f}': option(s, m, w, 10) for w in SEAMS},
                         cassettes={str(n): option(s, m, 0.125, n) for n in CASSETTES if n != 10},
                         truss=truss(s, m), front_fixed=front_fixed(s, m))
        ok = lambda o: all(q['min_gap_m'] >= MARGIN_M for q in o['states'].values())
        need = next((w for w in SEAMS if ok(res[name]['seams'][f'{w:.3f}'])), None)
        nneed = next((n for n in CASSETTES if n != 10 and ok(res[name]['cassettes'][str(n)])), None)
        res[name]['smallest_passing_seam_m'] = need; res[name]['fewest_passing_cassettes_at_0.125'] = nneed
    out = dict(status='DIAGNOSTIC_STUDY_NOT_A_QUALIFICATION (RAD-002-2026-10-10, 15!A122)', alpha_T=ALPHA_T, margin_m=MARGIN_M,
               scope='1-D free strain on the built blade and its options; no stiffness, friction, creep, bond or load; the carrier at the '
                     'installation temperature unless swept; MID_BAY local datums (proposed); temperatures PROTOTYPE (radiator_expansion).',
               area_check_vs_40_C81_C85=check, built_end_clearances_m=g['ends'], materials=res)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir/'rad002.json').write_text(json.dumps(out, indent=1)+'\n')
    return out


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('--out', type=Path, default=None); args = ap.parse_args()
    out = args.out or ROOT/'runs'/(datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-rad002')
    r = run(out)
    print('area check vs 40!C81:C85:', r['area_check_vs_40_C81_C85'])
    for name, m in r['materials'].items():
        row = {w: round(q['states']['HOT_UNIFORM']['min_gap_m'], 3) for w, q in m['seams'].items()}
        cas = {n: round(min(x['min_gap_m'] for x in q['states'].values()), 3) for n, q in m['cassettes'].items()}
        print(name, 'growth', round(m['free_growth_hot_m'], 3), 'hot gap by seam', row, 'worst gap by cassettes', cas,
              'passing seam', m['smallest_passing_seam_m'], 'cassettes', m['fewest_passing_cassettes_at_0.125'])
    print(out/'rad002.json')
