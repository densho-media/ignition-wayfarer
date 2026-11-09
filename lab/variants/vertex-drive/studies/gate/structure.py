"""Feasibility gate Phase 5: the S5N spine and the J1/J3 joints under the revised coupled mass (T00, research only, NON-CANON).

  python3 lab/variants/vertex-drive/studies/gate/structure.py    # needs results/coupled.json; writes results/structure.json (minute)

BEAM MODEL ONLY: the Rev 4 1D Timoshenko beam (studies/rev4/spine.py) with Guyan-condensed modes, closed-form local checks (longeron
bays, frame ovalling) and joint loads from beam statics. No finite-element model was built or run in this gate; every number here is a
beam-model prediction, and the joints are sized from statics, not from an FE stress field. FE (shells and joints) remains to be done.
Question from the brief: is about 2 kt of spine (Rev 4's N9, tube r 0.61 m on a 31 m ring) still enough on the coupled ship?
"""
import math

import coupled as CP
import gate_common as G
import spine as SP


def joint(sp):
    """J1 splice: per-longeron axial force from the root axial load and moment (n longerons on a ring: I = n A R^2 / 2)."""
    n = 9; Rr = sp['longeron_ring_m']
    out = {}
    for g, lat in sp['lateral'].items():
        M = lat['root_moment_MN_m'] * 1e6
        F = sp['J1']['axial_design_MN'] * 1e6
        N = F / n + 2 * M * SP.SF / (n * Rr)
        A_l, _ = SP.tube(sp['tube_r_m'])
        out[g] = {'root_moment_MN_m': lat['root_moment_MN_m'], 'root_shear_MN': lat['root_shear_MN'],
                  'splice_force_per_longeron_MN': N / 1e6, 'splice_stress_MPa': N / A_l / 1e6, 'allowable_MPa': SP.ALLOW / 1e6,
                  'ok': N / A_l <= SP.ALLOW, 'longeron_stress_MPa_beam': lat['stress_MPa']}
    return out


def summary(sp, label):
    return {'case': label, 'farm': sp['farm'], 'ring_m': sp['longeron_ring_m'], 'tube_r_m': sp['tube_r_m'], 'added_t': sp['added_t'],
            'structure_t': sp['structure_t'], 'length_m': sp['length_m'], 'f1_cantilever_Hz': sp['f1_cantilever_Hz'],
            'f1_free_free_Hz': sp['f1_free_free_Hz'], 'meets_0.2Hz_cantilever': sp['f1_cantilever_Hz'] >= 0.2 - 1e-9,
            'meets_0.2Hz_free_free': sp['f1_free_free_Hz'] >= 0.2 - 1e-9, 'buckling_factor_SF2': sp['buckling_factor_SF2'],
            'J1_axial_design_MN': sp['J1']['axial_design_MN'], 'J1_joint': joint(sp), 'J3': sp['J3'], 'local': sp['local'],
            'pulse_Hz': sp['pulse_Hz']}


def main():
    ov = G.v4_overrides(); R4 = G.solve_full(ov); d0 = SP.t05()
    cp = G.read('coupled.json')
    ships = [('V4 (Rev 4 reference)', R4)]
    for c in cp['cases']:
        if c['status'] == 'CONVERGED' and c.get('summary') and c['label'] in PICK:
            kv = c['final_set']; cap = c['rate_cap_Hz']
            ships.append((c['label'], CP.solve(ov, kv, cap)))
    out = {'study': 'Feasibility gate Phase 5: S5N spine and J1/J3 under the revised mass (T00)',
           'status': 'MODEL, research only, NON-CANON; BEAM MODEL (1D Timoshenko), NOT FE', 'method': __doc__, 'ships': []}
    for lab, R in ships:
        rows = []
        drawn = CP.spine_mass(R, R4, d0, fixed=(31.0, 0.611))                 # Rev 4 N9 as drawn by T05 (S5N): about 2 kt
        rows.append(summary(drawn, 'S5N as drawn (31 m ring, r 0.611 m, about 2 kt) on this ship'))
        for basis in (('cantilever', 0.2), ('free_free', 0.2), ('cantilever', 0.1)):
            try:
                sp = CP.spine_mass(R, R4, d0, basis=basis)
                rows.append(summary(sp, f'N9 wide farm sized for {basis[0]} {basis[1]} Hz'))
            except Exception as e:                     # record, do not hide
                rows.append({'case': f'N9 sized for {basis}', 'error': repr(e)})
        dep = G.C.fdp1.summary(R)['departure_t']
        out['ships'].append({'ship': lab, 'departure_t': dep, 'rate_Hz': R['fusion']['pellet_rate_Hz'], 'rows': rows})
        print(lab, round(dep))
        for r in rows:
            if 'error' in r:
                print('  ', r); continue
            print(f"   {r['case'][:58]:58s} r {r['tube_r_m']:.3f} added {r['added_t']:7.0f} t f_cant {r['f1_cantilever_Hz']:.3f} f_ff {r['f1_free_free_Hz']:.3f} "
                  f"J1 {r['J1_axial_design_MN']:.1f} MN, M0.01g {r['J1_joint']['0.01g']['root_moment_MN_m']:.0f} MN m splice {r['J1_joint']['0.01g']['splice_stress_MPa']:.0f} MPa")
    v = out['ships']
    drawn_ok = [s['rows'][0]['meets_0.2Hz_cantilever'] for s in v]
    out['answer'] = {'two_kt_sufficient_by_ship': {s['ship']: {'cantilever_0.2Hz': s['rows'][0]['meets_0.2Hz_cantilever'],
                                                                 'free_free_0.2Hz': s['rows'][0]['meets_0.2Hz_free_free'],
                                                                 'f1_cantilever_Hz': s['rows'][0]['f1_cantilever_Hz']} for s in v},
                     'note': 'beam model; the cantilever bound is T05 basis, the free-free bound assumes a rigid aft ship'}
    G.write('structure.json', out)
    return drawn_ok


PICK = ('coils + launcher + axis A1, rate free', 'full: + spine free-free 0.2 Hz (upper bound), rate free', 'full: + spine cantilever 0.1 Hz, rate free',
        'full: spine free-free 0.2 Hz, cap 250 Hz', 'full: spine free-free 0.2 Hz, cap 196 Hz')

if __name__ == '__main__':
    main()
