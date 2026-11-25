#!/usr/bin/env python3
"""ENG-067/068/069 on the approved research geometry: the lowest practical stored energy, conductor mass and stress for capture, without
treating a stronger field as the answer (owner brief 2026-11-25 08:55Z, item 3). WORK, not canon.

  1. Topology: field energy per joule captured (W/E) for every geometry the vertex-optimize scan built (the ratio does not depend on E,
     so it is the figure of merit of a topology), and the floor W/E >= 1 (the field could at best hold exactly the energy it stops).
  2. Current distribution: per-ring current multipliers on the research geometry, coordinate descent on W at constant capture
     (vertex-ron capture; the binding direction is re-found at every step).
  3. Conductor and structure scenarios: the capture case under today's and assumed future current density Je and allowable stress;
     the property each scenario assumes is stated, nothing is credited unless its number is named.
  4. Load path: axial force per coil (GN, self-balanced inside the coil set) against the net thrust the ship sees (MN).
  5. Quench: modules that each dump in a safe time; dump resistor mass; why pulsed or distributed field storage does not apply.

Two capture cases are carried, never mixed: BURN (the design pulse's charged energy at the mission rate, vertex-pulse) and OPERATING
(the mission operating point at the design rate, the 286 GJ of vertex-optimize). The coils as drawn (k = 1, 27 GJ) stay separate.

    python3 lab/studies/vertex-compact-engine/vertex-pulse/magnets.py        # about 3 minutes; writes results/magnets.json
"""
import copy
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT / 'lab/studies/vertex-compact-engine/vertex-optimize'))
import optimize as O  # noqa: E402

ron = O.ron
P = dict(
    Je=(('today: REBCO tape stack at 20 K, ~20 T (engineering current density)', 1.53e8),
        ('assumed: 2x engineering current density at the same field', 3.06e8),
        ('assumed: 4x (thin-substrate tape, higher fill)', 6.12e8)),
    sigma=(('today: high-strength steel / Hastelloy reinforcement', 1.5e9),
           ('assumed: carbon-fibre / nanotube composite at 4 K', 3.0e9),
           ('assumed: 6 GPa structural fibre at 4 K', 6.0e9)),
    B_conductor_limit_T=(('today: REBCO critical field margin at 20 K', 30.0), ('assumed: 45 T class', 45.0), ('assumed: 60 T class', 60.0)),
    t_dump_safe_s=10.0,        # P[a REBCO coil must be discharged within seconds after a quench is detected]
    I_op=50e3, V_dump=10e3,    # A, V per module dump circuit (vertex-optimize defaults)
    steel_c=500.0, steel_dT=400.0,   # dump resistor: steel, J/kg/K and allowed rise
)


def scaled(v, mult):
    w = copy.deepcopy(v)
    for c in w['coils']:
        c['I'] *= mult.get(c['name'], 1.0)
    return w


def descend(v, E, names, steps=(0.7, 0.85, 1.15, 1.4), rounds=4):
    mult = {n: 1.0 for n in names}
    best = ron.capture(v, E)['W_J']; hist = [best]
    for _ in range(rounds):
        moved = False
        for n in names:
            for s in steps:
                m = dict(mult, **{n: mult[n] * s})
                W = ron.capture(scaled(v, m), E)['W_J']
                if W < best * 0.995:
                    best, mult, moved = W, m, True
        hist.append(best)
        if not moved:
            break
    return mult, best, hist


def main():
    R = json.loads((ROOT / 'lab/studies/vertex-compact-engine/vertex-optimize/results/optimize.json').read_text())
    PU = json.loads((HERE / 'results' / 'pulse.json').read_text())
    k = ron.canon()
    v, src, E_op, cap_op = ron.configure(O.geometry(O.RESEARCH, 4.0, 4.0), k)
    base = next(r for r in PU['rows'] if r['label'] == 'Target mass x1')
    E_burn = base['capture']['burn']['E_charged_J']
    # 1. topology
    topo = [dict(key=g['key'], label=g['label'], W_over_E=g['stored_J'] / E_op, B_burn_T=g['B_burn_T'], binding=g['binding'],
                 coil_t=g['coil_t']) for g in R['geometries']]
    topo.sort(key=lambda t: t['W_over_E'])
    # 2. current distribution
    names = [c['name'] for c in v['coils']]
    W0 = cap_op['W_J']
    mult, Wopt, hist = descend(v, E_op, names)
    vo = scaled(v, mult); capo = ron.capture(vo, E_op)
    # 3. scenarios at both capture cases, distribution as optimised
    cases = []
    for basis, E in (('burn', E_burn), ('operating', E_op)):
        for nm, vv in (('research as drawn', v), ('research, optimised current distribution', vo)):
            c = ron.capture(vv, E); kk = c['k']
            ce = O.coil_engineering(vv, kk, f'{basis}: {nm}')
            I_tot = sum(abs(cc['I']) * kk * 2 * math.pi * O.ron.hoop_r(cc) for cc in vv['coils'])      # A*m of conductor
            scen = []
            for jl, Je in P['Je']:
                for sl, sg in P['sigma']:
                    cond = I_tot / Je * 6000 / 1e3
                    struct = ce['structure_t'] * 1.5e9 / sg
                    scen.append(dict(Je_label=jl, Je=Je, sigma_label=sl, sigma=sg, conductor_t=cond, structure_t=struct, total_t=cond + struct))
            # peak field at the windings: B_self ~ mu0 I / (2 pi a), a ~ sqrt(I / (pi Je)), so B_self ~ sqrt(I Je): denser conductor, higher field
            Bw = ce['B_peak_max_T']
            Bw_by_Je = [dict(Je=Je, B_peak_T=Bw * math.sqrt(Je / P['Je'][0][1])) for _, Je in P['Je']]
            N = max(1, math.ceil(2 * c['W_J'] / (P['I_op'] * P['V_dump'] * P['t_dump_safe_s'])))
            cases.append(dict(basis=basis, distribution=nm, E_J=E, k=kk, W_J=c['W_J'], W_over_E=c['W_J'] / E, binding=c['binding_part'],
                              B_burn_T=ce['B_burn_T'], B_wind_T=Bw, B_wind_by_Je=Bw_by_Je, hoop_GN=ce['hoop_total_MN'] / 1e3,
                              Fx_max_GN=ce['Fx_max_MN'] / 1e3, Fx_net_MN=ce['Fx_net_MN'], coils=ce['coils'], scenarios=scen,
                              quench_modules=N, module_energy_GJ=c['W_J'] / N / 1e9,
                              dump_steel_t=c['W_J'] / (P['steel_c'] * P['steel_dT']) / 1e3,
                              conductor_limit_ok={lbl: Bw <= lim for lbl, lim in P['B_conductor_limit_T']}))
    built = O.coil_engineering(v, 1.0, 'research coils as drawn (k = 1)')
    fl = dict(W_floor_over_E=1.0, best_topology=topo[0]['key'], best_topology_W_over_E=topo[0]['W_over_E'],
              research_W_over_E=W0 / E_op, optimised_W_over_E=Wopt / E_op, gain=W0 / Wopt)
    # 5. pulsed storage: the field is persistent; a pulse only dents it by E/W. Recharging the whole field every pulse would cost W f.
    pulsed = dict(persistent_ripple=1.0 / (Wopt / E_op), recharge_every_pulse_W=Wopt * PU['Hz_design'],
                  recharge_at_mission_rate_W=(Wopt / E_op) * E_burn * base['Hz'])
    out = dict(cls='CALCULATED', source='lab/studies/vertex-compact-engine/vertex-pulse/magnets.py', P={k_: v_ for k_, v_ in P.items()},
               E_op_J=E_op, E_burn_J=E_burn, topology=topo, distribution=dict(mult=mult, W0_J=W0, W_J=Wopt, history=hist,
               binding=capo['binding_part']), floor=fl, cases=cases, built=dict(W_J=built['stored_J'], B_burn_T=built['B_burn_T'],
               B_wind_T=built['B_peak_max_T'], hoop_GN=built['hoop_total_MN'] / 1e3, Fx_max_GN=built['Fx_max_MN'] / 1e3,
               Fx_net_MN=built['Fx_net_MN']), pulsed=pulsed)
    (HERE / 'results' / 'magnets.json').write_text(json.dumps(out, indent=1))
    print('topology W/E best', [(t['key'], round(t['W_over_E'], 1)) for t in topo[:6]], 'worst', topo[-1]['key'], round(topo[-1]['W_over_E'], 1))
    print('distribution', {n: round(m, 2) for n, m in mult.items()}, f'W {W0 / 1e9:.0f} -> {Wopt / 1e9:.0f} GJ', [round(h / 1e9) for h in hist])
    for c in cases:
        best = min(c['scenarios'], key=lambda q: q['total_t']); today = c['scenarios'][0]
        print(f"{c['basis']:9s} {c['distribution'][:40]:40s} W {c['W_J'] / 1e9:7.1f} GJ Bw {c['B_wind_T']:5.1f} T hoop {c['hoop_GN']:6.1f} GN "
              f"Fx {c['Fx_max_GN']:6.2f} GN net {c['Fx_net_MN']:8.1f} MN mass today {today['total_t']:6.0f} t best {best['total_t']:5.0f} t quench N {c['quench_modules']}")
    print(out['built']); print(pulsed)


if __name__ == '__main__':
    main()
