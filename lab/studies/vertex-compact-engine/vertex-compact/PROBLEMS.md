# Engineering Problems Register: compact Wayfarer direction

Research, not canon. Part 1 is the compact cluster (the main direction from 2026-11-23); part 2 is the remote-engine research branch
(lab/studies/vertex-compact-engine/vertex-hims/PROBLEMS.md, kept as reference). An OPEN problem blocks a claim of validation, not the development of the model.

## Part 1: compact cluster (variants C1-C4)

| ID | Problem | Variants | Required | Achieved | Severity | Status |
| --- | --- | --- | --- | --- | --- | --- |
| ENG-030 | Compact engine hardware absorbs most of the burn | C1, C2, C3, C4 | Piped heat <= 10.8 GW (four engines, the canon drive radiators) | C1 176,004 GW (16,295 x); C3/C4 116,627 GW (10,798 x) | CRITICAL: 4 orders of magnitude | OPEN |
| ENG-031 | Compact axial efficiency 0.31-0.51 inflates the mass ratio | C1, C2, C3, C4 | eta about 0.95 (canon ve) | C1 0.31, C3 0.51; departure 48,744 t even if the heat closed | HIGH | OPEN |
| ENG-032 | Burns light the radiator blades and the aft ship | C1, C2, C3, C4 | <= 0.1 GW direct burn on the ship | C1 1,255 GW; C2 76 GW (cluster 30 m aft); C4 13.9 GW, all on the blade aft ends | HIGH (C1), MEDIUM (C4) | MITIGATED |
| ENG-033 | Loop windings take 7,000 x their neutron fluence limit | C1, C2, C3, C4 | 3e22 n/m2 | 2.2e+26 n/m2 (7,260 x) | HIGH | OPEN |
| ENG-034 | Engine faces lead in braking: armour only | C1, C2, C3, C4 | 0.1 breaches per face | Armour 8-10 cm W/C: 444 t NOMINAL, 780 t JUSTIFIED (whole aft end) | MEDIUM | MITIGATED |
| ENG-035 | Compact stern screens close for the tank dome (NOMINAL) | C4 | 0.1 events | 0.086 events NOMINAL with 5.5 t; JUSTIFIED needs more stand-off | LOW (NOMINAL), MEDIUM (JUSTIFIED) | MITIGATED |
| ENG-036 | Hull-shadowing shields grow and add engine heat | C3, C4 | Shadow the ship without extra heat | C3 shield r 7.9 m (375 t/engine); C4 r 9.5 m (533 t/engine) | MEDIUM | OPEN |
| ENG-037 | Longer thrust truss and feeds (30-36 m) | C2, C3, C4 | Carries 21.8 MN and the field loads | Drawn, not sized (30 t per engine allotted) | LOW | OPEN |
| ENG-038 | Ripple heating of the compact eddy shields | C1, C2, C3, C4 | Radiated by the shield at <= 2,300 K | 41 MW per engine, dB/B 0.001 | LOW next to ENG-030 | WATCH |

### ENG-030: Compact engine hardware absorbs most of the burn

- Works / does not: C1 176,004 GW (16,295 x); C3/C4 116,627 GW (10,798 x) against Piped heat <= 10.8 GW (four engines, the canon drive radiators)
- Mechanism: Loops, shield and closure coils within 2-12 m of a 65 TW burn see most of its sky and take 46-69 % of the charged products
- Evidence: `lab/studies/vertex-compact-engine/vertex-compact/results/compact.json`
- Assumptions: V2 optimistic fuel (1.6B S5), vacuum test particles, ron.py sky ledger
- Possible solutions: Stronger closure field (x4 already used in C3), ribbon loops, larger loop radii within the cluster envelope, lower-loss fuel cycle
- Future technology or redesign: Absorbed fraction 4e-5 of fusion power (today about 0.45); a field that keeps charged products off hardware at 2-10 m
- Next: Hybrid PIC of the compact burn with C1-C2 closure coils at x4 field

### ENG-031: Compact axial efficiency 0.31-0.51 inflates the mass ratio

- Works / does not: C1 0.31, C3 0.51; departure 48,744 t even if the heat closed against eta about 0.95 (canon ve)
- Mechanism: Products hitting the shield and leaving radially do not make thrust; ve falls with eta
- Evidence: `lab/studies/vertex-compact-engine/vertex-compact/results/compact.json`
- Assumptions: Test particles, 48 directions x 4 species (quick run)
- Possible solutions: Field x4 and burn 12 m aft of the shield (C3) raise eta 0.31 to 0.51
- Future technology or redesign: Plasma detachment model; collective effects
- Next: Full 160-direction run; scan field x2-x8

### ENG-032: Burns light the radiator blades and the aft ship

- Works / does not: C1 1,255 GW; C2 76 GW (cluster 30 m aft); C4 13.9 GW, all on the blade aft ends against <= 0.1 GW direct burn on the ship
- Mechanism: Shadow cones of the drawn shields (28 deg) do not cover the spine, the tank dome or the blade roots beside the cluster
- Evidence: `lab/studies/vertex-compact-engine/vertex-compact/results/compact.json (ship_lit)`
- Assumptions: No ship self-occlusion; photons + neutrons; four canted burns
- Possible solutions: Cluster 30 m aft (16x less), tank-shadowing shields (C3/C4), move the blade aft station forward or cant the blade aft ends edge-on
- Future technology or redesign: None for C4: a geometry change of the blade aft station (PROTOTYPE) closes most of the remainder
- Next: Blade aft-station trade (area kept)

### ENG-033: Loop windings take 7,000 x their neutron fluence limit

- Works / does not: 2.2e+26 n/m2 (7,260 x) against 3e22 n/m2
- Mechanism: Windings 7.6 m from the burn behind 0.22 m of armour (drawn)
- Evidence: `lab/studies/vertex-compact-engine/vertex-compact/results/compact.json`
- Assumptions: W-B4C attenuation 0.08 m, scattered floor 1e-4 (MPN rule)
- Possible solutions: No armour thickness closes: the scattered floor alone is 11 x the limit. Replaceable loop cassettes (one set per burn, about 11 exchanges per mission), or a winding farther from the burn
- Future technology or redesign: Radiation-tolerant conductor at 34e22 n/m2 with thicker armour; or neutron-lean fuel
- Next: Neutron transport for the compact loop armour

### ENG-034: Engine faces lead in braking: armour only

- Works / does not: Armour 8-10 cm W/C: 444 t NOMINAL, 780 t JUSTIFIED (whole aft end) against 0.1 breaches per face
- Mechanism: Loops, shield faces and the hub lead into the dust in braking; nothing can stand ahead of them in the burn view
- Evidence: `lab/studies/vertex-compact-engine/vertex-compact/results/compact.json (dust)`
- Assumptions: Dust-impacts rules, extrapolated above 100 km/s
- Possible solutions: Replaceable armour tiles on the loop aft faces and the hub cap (C4)
- Future technology or redesign: Armour areal density /2
- Next: Tile layout on the loop cryostats

### ENG-035: Compact stern screens close for the tank dome (NOMINAL)

- Works / does not: 0.086 events NOMINAL with 5.5 t; JUSTIFIED needs more stand-off against 0.1 events
- Mechanism: Three screens in a 15 m zone ahead of the tank dome, inside the enlarged shields' shadow
- Evidence: `lab/studies/vertex-compact-engine/vertex-compact/results/compact.json`
- Assumptions: HIMS-B pass-through 0.5 per screen (NOMINAL)
- Possible solutions: Screens become roll-fed spares; armour remains the JUSTIFIED answer
- Future technology or redesign: None
- Next: JUSTIFIED screen count vs shield size

### ENG-036: Hull-shadowing shields grow and add engine heat

- Works / does not: C3 shield r 7.9 m (375 t/engine); C4 r 9.5 m (533 t/engine) against Shadow the ship without extra heat
- Mechanism: Shadowing the tank dome from a burn 24 m off axis needs a 40-46 deg shield; it adds sky (heat) and mass
- Evidence: `lab/studies/vertex-compact-engine/vertex-compact/results/compact.json`
- Assumptions: LiH body, 5 cm W/B4C face
- Possible solutions: One cluster-wide shadow disc on the hub instead of four large cones (to study)
- Future technology or redesign: None
- Next: Cluster shadow-disc variant

### ENG-037: Longer thrust truss and feeds (30-36 m)

- Works / does not: Drawn, not sized (30 t per engine allotted) against Carries 21.8 MN and the field loads
- Mechanism: Cluster moved aft on twelve truss members; feeds, trunks and the Li/cold loops lengthen
- Evidence: `lab/studies/vertex-compact-engine/vertex-compact/blender_compact.py`
- Assumptions: PROTOTYPE
- Possible solutions: Size with vertex_structure loads
- Future technology or redesign: None
- Next: Truss FE with the cluster load cases

### ENG-038: Ripple heating of the compact eddy shields

- Works / does not: 41 MW per engine, dB/B 0.001 against Radiated by the shield at <= 2,300 K
- Mechanism: 5.7 kHz pulses (AMPN rule, eps_c 0.3)
- Evidence: `lab/studies/vertex-compact-engine/vertex-compact/results/compact.json`
- Assumptions: Coupling 0.3 (0.1-1) not measured
- Possible solutions: Booked in the piped heat
- Future technology or redesign: Measured coupling
- Next: With ENG-002

## Part 2: remote-engine research branch (reference, not the main direction)

| ID | Problem | Status |
| --- | --- | --- |
| ENG-001 | Whole-ship mass does not reach the 4,426 t benchmark | OPEN |
| ENG-002 | Field-ripple heating of the winding and eddy shield | OPEN |
| ENG-003 | Plasma-coupled detachment not modelled | OPEN |
| ENG-004 | Rare high-energy strikes on hardware unbounded | OPEN |
| ENG-005 | Winding neutron fluence sets a 15 m ring floor | MITIGATED |
| ENG-006 | Neutrons reach the ship through the plug | MITIGATED |
| ENG-007 | Forward escape needs cant; E cannot clear its forward stream | OPEN |
| ENG-010 | Exhaust plume cannot stop dust (Mode B) | REJECTED |
| ENG-011 | HIMS: deflection limited by plasma beta and the ionised share, not by the field integral | OPEN |
| ENG-012 | Vertex ring fields cannot reach the dust path at the ship | REJECTED |
| ENG-013 | Laser pre-ionisation of dust | REJECTED |
| ENG-014 | Engine faces cannot have a screen ahead of them | MITIGATED |
| ENG-015 | Boom service ducts dominate JUSTIFIED dust mass | OPEN |
| ENG-016 | Stern screen erosion and replacement | WATCH |
| ENG-017 | Impact physics above 100 km/s is extrapolated | OPEN |
| ENG-018 | Engine-to-engine magnetic forces on the boom frame | WATCH |
| ENG-019 | Giga-cycle fatigue from the 20 kHz ripple | WATCH |
| ENG-020 | Quench protection of thin tapes | MITIGATED |
| ENG-021 | Adaptive geometry adds mass without protection | REJECTED |
