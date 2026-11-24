#!/usr/bin/env python3
"""Engineering Problems Register, compact direction (research, not canon). Continues lab/studies/vertex-compact-engine/vertex-hims/problems.py (ENG-001..021, the
remote-engine research branch) with the compact-cluster entries ENG-030.., each tagged with the compact variants it applies to.
Numbers come from results/compact.json (compact.py). `python3 lab/studies/vertex-compact-engine/vertex-compact/problems.py` writes results/problems_compact.json
(read by blender_compact.py for the overlays) and PROBLEMS.md (both parts). Status as in the HIMS register.
"""
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'vertex-hims'))
import problems as remote  # noqa: E402

R = json.loads((HERE / 'results' / 'compact.json').read_text())['variants']


def f(x):
    return f'{x:,.0f}'


def armour_needed(over, lam=0.08, floor=1e-4, t0=0.22):
    """W-B4C thickness that brings the winding under the fluence limit (MPN rule) from the ratio at t0."""
    flu0 = over * 3e22 / (math.exp(-t0 / lam) + floor)
    room = 3e22 / flu0 - floor
    return lam * math.log(1 / room) if room > 0 else math.inf


C1, C2, C3, C4 = (R[k] for k in ('C1', 'C2', 'C3', 'C4'))
t_arm = armour_needed(C1['winding_over_limit'])
floor_x = C1['winding_over_limit'] * 1e-4 / (math.exp(-0.22 / 0.08) + 1e-4)   # the scattered floor alone, as a multiple of the limit
P = [
    dict(id='ENG-030', title='Compact engine hardware absorbs most of the burn', subsystem='Vertex engine', variants=['C1', 'C2', 'C3', 'C4'],
         mechanism='Loops, shield and closure coils within 2-12 m of a 65 TW burn see most of its sky and take 46-69 % of the charged products',
         evidence='lab/studies/vertex-compact-engine/vertex-compact/results/compact.json', required='Piped heat <= 10.8 GW (four engines, the canon drive radiators)',
         achieved=f"C1 {f(C1['piped_four_W'] / 1e9)} GW ({f(C1['piped_over_budget'])} x); C3/C4 {f(C3['piped_four_W'] / 1e9)} GW ({f(C3['piped_over_budget'])} x)",
         assumptions='V2 optimistic fuel (1.6B S5), vacuum test particles, ron.py sky ledger', severity='CRITICAL: 4 orders of magnitude',
         solutions='Stronger closure field (x4 already used in C3), ribbon loops, larger loop radii within the cluster envelope, lower-loss fuel cycle',
         advances='Absorbed fraction 4e-5 of fusion power (today about 0.45); a field that keeps charged products off hardware at 2-10 m',
         next='Hybrid PIC of the compact burn with C1-C2 closure coils at x4 field', status='OPEN', components=['RING']),
    dict(id='ENG-031', title='Compact axial efficiency 0.31-0.51 inflates the mass ratio', subsystem='Magnetic nozzle', variants=['C1', 'C2', 'C3', 'C4'],
         mechanism='Products hitting the shield and leaving radially do not make thrust; ve falls with eta', evidence='lab/studies/vertex-compact-engine/vertex-compact/results/compact.json',
         required='eta about 0.95 (canon ve)', achieved=f"C1 {C1['eta']:.2f}, C3 {C3['eta']:.2f}; departure {f(C3['departure_if_heat_closed_t'])} t even if the heat closed",
         assumptions='Test particles, 48 directions x 4 species (quick run)', severity='HIGH', solutions='Field x4 and burn 12 m aft of the shield (C3) raise eta 0.31 to 0.51',
         advances='Plasma detachment model; collective effects', next='Full 160-direction run; scan field x2-x8', status='OPEN', components=['RING']),
    dict(id='ENG-032', title='Burns light the radiator blades and the aft ship', subsystem='Ship integration', variants=['C1', 'C2', 'C3', 'C4'],
         mechanism='Shadow cones of the drawn shields (28 deg) do not cover the spine, the tank dome or the blade roots beside the cluster',
         evidence='lab/studies/vertex-compact-engine/vertex-compact/results/compact.json (ship_lit)', required='<= 0.1 GW direct burn on the ship',
         achieved=f"C1 {f(C1['ship_lit_W'] / 1e9)} GW; C2 {f(C2['ship_lit_W'] / 1e9)} GW (cluster 30 m aft); C4 {C4['ship_lit_W'] / 1e9:.1f} GW, all on the blade aft ends",
         assumptions='No ship self-occlusion; photons + neutrons; four canted burns', severity='HIGH (C1), MEDIUM (C4)',
         solutions='Cluster 30 m aft (16x less), tank-shadowing shields (C3/C4), move the blade aft station forward or cant the blade aft ends edge-on',
         advances='None for C4: a geometry change of the blade aft station (PROTOTYPE) closes most of the remainder', next='Blade aft-station trade (area kept)',
         status='MITIGATED', components=['BLADES']),
    dict(id='ENG-033', title='Loop windings take 7,000 x their neutron fluence limit', subsystem='Coil protection', variants=['C1', 'C2', 'C3', 'C4'],
         mechanism='Windings 7.6 m from the burn behind 0.22 m of armour (drawn)', evidence='lab/studies/vertex-compact-engine/vertex-compact/results/compact.json',
         required='3e22 n/m2', achieved=f"{C1['winding_fluence']:.1e} n/m2 ({f(C1['winding_over_limit'])} x)", assumptions='W-B4C attenuation 0.08 m, scattered floor 1e-4 (MPN rule)',
         severity='HIGH', solutions=(f'No armour thickness closes: the scattered floor alone is {floor_x:.0f} x the limit. Replaceable loop cassettes (one set per '
                    f'burn, about {floor_x:.0f} exchanges per mission), or a winding farther from the burn'),
         advances=f'Radiation-tolerant conductor at {floor_x * 3:.0f}e22 n/m2 with thicker armour; or neutron-lean fuel', next='Neutron transport for the compact loop armour', status='OPEN', components=['RING']),
    dict(id='ENG-034', title='Engine faces lead in braking: armour only', subsystem='Dust protection', variants=['C1', 'C2', 'C3', 'C4'],
         mechanism='Loops, shield faces and the hub lead into the dust in braking; nothing can stand ahead of them in the burn view',
         evidence='lab/studies/vertex-compact-engine/vertex-compact/results/compact.json (dust)', required='0.1 breaches per face', achieved=f"Armour 8-10 cm W/C: {f(C1['dust_nominal_t'])} t NOMINAL, {f(C1['dust_justified_t'])} t JUSTIFIED (whole aft end)",
         assumptions='Dust-impacts rules, extrapolated above 100 km/s', severity='MEDIUM', solutions='Replaceable armour tiles on the loop aft faces and the hub cap (C4)',
         advances='Armour areal density /2', next='Tile layout on the loop cryostats', status='MITIGATED', components=['RING', 'HUB']),
    dict(id='ENG-035', title='Compact stern screens close for the tank dome (NOMINAL)', subsystem='Dust protection', variants=['C4'],
         mechanism='Three screens in a 15 m zone ahead of the tank dome, inside the enlarged shields\' shadow', evidence='lab/studies/vertex-compact-engine/vertex-compact/results/compact.json',
         required='0.1 events', achieved=f"{C4['dust_nominal'][-1]['screen_events']:.3f} events NOMINAL with 5.5 t; JUSTIFIED needs more stand-off",
         assumptions='HIMS-B pass-through 0.5 per screen (NOMINAL)', severity='LOW (NOMINAL), MEDIUM (JUSTIFIED)', solutions='Screens become roll-fed spares; armour remains the JUSTIFIED answer',
         advances='None', next='JUSTIFIED screen count vs shield size', status='MITIGATED', components=['SCREEN']),
    dict(id='ENG-036', title='Hull-shadowing shields grow and add engine heat', subsystem='Radiation protection', variants=['C3', 'C4'],
         mechanism='Shadowing the tank dome from a burn 24 m off axis needs a 40-46 deg shield; it adds sky (heat) and mass', evidence='lab/studies/vertex-compact-engine/vertex-compact/results/compact.json',
         required='Shadow the ship without extra heat', achieved=f"C3 shield r {C3['shield']['r_fwd']:.1f} m ({f(C3['shield_t'])} t/engine); C4 r {C4['shield']['r_fwd']:.1f} m ({f(C4['shield_t'])} t/engine)",
         assumptions='LiH body, 5 cm W/B4C face', severity='MEDIUM', solutions='One cluster-wide shadow disc on the hub instead of four large cones (to study)',
         advances='None', next='Cluster shadow-disc variant', status='OPEN', components=['SHIELD']),
    dict(id='ENG-037', title='Longer thrust truss and feeds (30-36 m)', subsystem='Structure', variants=['C2', 'C3', 'C4'],
         mechanism='Cluster moved aft on twelve truss members; feeds, trunks and the Li/cold loops lengthen', evidence='lab/studies/vertex-compact-engine/vertex-compact/blender_compact.py',
         required='Carries 21.8 MN and the field loads', achieved='Drawn, not sized (30 t per engine allotted)', assumptions='PROTOTYPE', severity='LOW',
         solutions='Size with vertex_structure loads', advances='None', next='Truss FE with the cluster load cases', status='OPEN', components=['TRUSS']),
    dict(id='ENG-038', title='Ripple heating of the compact eddy shields', subsystem='Magnetic nozzle', variants=['C1', 'C2', 'C3', 'C4'],
         mechanism='5.7 kHz pulses (AMPN rule, eps_c 0.3)', evidence='lab/studies/vertex-compact-engine/vertex-compact/results/compact.json', required='Radiated by the shield at <= 2,300 K',
         achieved=f"{C1['ripple']['eddy_W'] / 1e6:.0f} MW per engine, dB/B {C1['ripple']['dB_over_B']:.3f}", assumptions='Coupling 0.3 (0.1-1) not measured',
         severity='LOW next to ENG-030', solutions='Booked in the piped heat', advances='Measured coupling', next='With ENG-002', status='WATCH', components=['RING']),
]


def main():
    allp = [dict(p, variants=['REMOTE']) for p in remote.P] + P
    (HERE / 'results' / 'problems_compact.json').write_text(json.dumps(P, indent=1))
    L = ['# Engineering Problems Register: compact Wayfarer direction', '',
         'Research, not canon. Part 1 is the compact cluster (the main direction from 2026-11-23); part 2 is the remote-engine research branch',
         '(lab/studies/vertex-compact-engine/vertex-hims/PROBLEMS.md, kept as reference). An OPEN problem blocks a claim of validation, not the development of the model.', '',
         '## Part 1: compact cluster (variants C1-C4)', '',
         '| ID | Problem | Variants | Required | Achieved | Severity | Status |', '| --- | --- | --- | --- | --- | --- | --- |']
    for p in P:
        L.append(f"| {p['id']} | {p['title']} | {', '.join(p['variants'])} | {p['required']} | {p['achieved']} | {p['severity']} | {p['status']} |")
    for p in P:
        L += ['', f"### {p['id']}: {p['title']}", '', f"- Works / does not: {p['achieved']} against {p['required']}", f"- Mechanism: {p['mechanism']}",
              f"- Evidence: `{p['evidence']}`", f"- Assumptions: {p['assumptions']}", f"- Possible solutions: {p['solutions']}",
              f"- Future technology or redesign: {p['advances']}", f"- Next: {p['next']}"]
    L += ['', '## Part 2: remote-engine research branch (reference, not the main direction)', '',
          '| ID | Problem | Status |', '| --- | --- | --- |']
    for p in remote.P:
        L.append(f"| {p['id']} | {p['title']} | {p['status']} |")
    (HERE / 'PROBLEMS.md').write_text('\n'.join(L) + '\n')
    print(len(P), 'compact problems;', len(allp), 'in all')


if __name__ == '__main__':
    main()
