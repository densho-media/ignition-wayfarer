<!-- lab entry -->
| Lab entry | |
| --- | --- |
| Kind | Problem map |
| Status | ACTIVE |
| Question | Where and how badly does FDP-1 fail (why 0.016 c x4 closes but 1 g does not)? Problems only, no solutions. |
| Model base | main e251f7c |
| Salvaged from | claude/project-thread-k6fuel @ a8a1a86, 2026-11-06 |
| Open owner questions | V3 review (modes, P11 protection envelope); P11 UNRESOLVED; shield mass OD-014; the 6.0 vs 6.35 y conflict. |
| Review | project files review/fdp1_requirements_2026-11-04/, fdp1_spatial_2026-11-05/, fdp1_spatial_v2_2026-11-05/, fdp1_spatial_v3_2026-11-05/ |

# NOTES: FDP-1 engineering requirements map (2026-11-04)

**Function.** Show the size of FDP-1's engineering problems and how they connect, as the reference for later
research. Owner brief 2026-11-04 (thread "Visualize FDP-1 engineering limits in Blender").

**Fixed constraints.** FDP-1 record fdp1-v1 (branch `claude/project-thread-8e13aa` @ ec5717d, unchanged) is the
authoritative data; canon from `data/wayfarer_3d.toml`; no Wild Zone or new physics; no number invented to complete a
chart (TBD instead).

**Design freedom.** Layout, colours (owner palette), panel structure, glyphs.

## Findings

- The four burns are a propellant problem: Δv 0.064 c ≈ 0.999 v_e, so mass ratio 2.716 closes regardless of
  acceleration. 1 g is a power-per-mass problem: ×145 fusion power at the same mass (2,507 TW); power-scaled
  hardware at 2.84e-7 kg/W would weigh 26.7× the whole ship. The record's ceiling is 0.0112 g at any size (×89).
- Of the 3.81 TW not in the jet, 3.71 TW leaves the ship (3.51 TW undirected plume, 0.195 TW radiation); 101.5 GW
  becomes onboard heat. Model allocation, not measured.

## Inconsistencies and conflicts found (reported, not fixed)

1. Owner brief "remaining dry mass 7,643 t" is the end mass; dry mass is 7,118 t + 525 t reserve.
2. Canon LOCKED mission duration 6.0 y (02_SHIP_INPUTS A6:H6) vs FDP-1 minimum round trip 6.35 y.
3. FDP-1 structure limits text: "100 Hz for 5.7 years is ~1.8e10 cycles"; the rate is 212 Hz → 3.8e10 cycles.
4. Two specific masses: closure alpha_jet 2.84e-7 kg/W vs 1 g check 2.68e-7 kg/W (6 % apart); the ×89 uses the latter.
5. Energy ledger books outputs as shares of gross fusion; the 5.76 GW beam re-deposited in each target (0.033 %)
   is not booked as an output.
6. Radiator masses include a heat-transport allowance (87 t, 8.6e-7 kg per W of heat) beyond area × areal mass;
   transport hardware itself is not designed.
7. Neutron escape 5.5e-6 of fusion relies on dense-fuel self-absorption at ρR 90 g/cm²; the production share is
   not reported (TBD).
8. Emissivity 0.9 and a 0 K sink are inferred: they reproduce the record's planform fluxes exactly.

## Open questions (no data)

Driver reliability over 3.8e10 pulses; magnetic-nozzle detachment and inter-loop load paths (2.3 GN scale);
hardware radiation dose and shield transport; heat-transport design over 3.5 km wings; material limits at
1,500-2,500 K; fatigue; margin policy for the 4 % reserve; He-3 supply (7,865 t); resolution of the 6.0 y conflict.

## Phase 2 (2026-11-05): spatial refactor

Owner brief 2026-11-05. The representation changed; the data, model and checks did not (20/20 pass, record diff 0).
Encodings are declared in VISUAL_GRAMMAR.md.

Schematic choices, all flagged on the objects:
- The uncollimated plume's spread angle is drawn at 50°; the record has no figure.
- The coast is drawn as one block; the record gives a total only.
- Positions inside the fusion island (drivers, manifolds) are schematic.
- Tubes thinner than 0.12 BU are drawn at that width.

## Phase 3 (2026-11-05): V2, ship-centred and parametric

This phase changed the representation only. FDP-1 physics, canon, the Wayfarer model and the phase-1/2 data are
unchanged; `check_v2.py` checks this with git and file hashes.

Choices and conflicts:
- **Four-nozzle drive.** The brief lists "four primary magnetic nozzles". The FDP-1 record supersedes that drive with
  three nozzle loops at a single burn point, plus Fiji lattice bands on the loops. V2 draws FDP-1 and keeps the
  four-nozzle drive as the hidden collection `V2_99_SUPERSEDED_FOUR_NOZZLE_DRIVE`.
- **Two ceilings.**
  - With today's alpha (2.84e-7 kg/W) the closure law caps at 0.0106 g.
  - The record's goal-1g study uses 2.68e-7 kg/W and gets 0.0112 g.
  - Both are offered as a scaling option. Neither is a physical limit.
- **The temperature slider moves only the warm loop.**
  - Areal mass and transport per W are held at the record's values (flagged ASSUMPTION).
  - Rejecting driver and power heat above 600 K needs heat lift or high-temperature electronics (P06).
  - Material limits at 1,500–2,500 K are unknown (P07).
  - Above 1,800 K the loops would swap roles, which is not modelled.
  - The ceiling saturates near 0.020 g, because the hot loop and the drive hardware do not change.
- **Bow shift.** T-B moves the bow 122.4 m forward. The bay between is drawn as an unresolved translucent cylinder (P08).
- **Schematic positions.** These are flagged on the objects:
  - the heat-manifold nodes;
  - the anchors of the struts deposit;
  - the plume lobe angle;
  - the driver-loop routing;
  - the mission track scale.
- **Still open from earlier phases.** The canon LOCKED 6.0 y conflicts with the computed 6.35 y minimum.

## Phase 4 (2026-11-05): V3, exploration modes and P11

Calculated (geometric coverage only, canon 90 m shield at x 260.55 m, aligned stream, margin 0):
- Engine maximum radius 112.55 m (diameter 225 m), set by `FDP1_Loop_3_Sector_Feed_1` at x −292 m. Protected radius
  there 45 m: clearance −67.5 m. The engine is **not** covered. A shield of r 112.5 m (+33,432 m², ×6.26 area) would
  cover every critical part geometrically.
- 50 of 269 critical parts lie outside, 1,492 m² of frontal area: nozzle loops and Fiji lattice (24 parts, 882 m²),
  thrust structure (12, 223 m²), shadow-shield / loop armour (2, 261 m²), pulsed-power feeds (8, 84 m²), thermal
  lines (4, 41 m²). Tanks, habitat and the Wayfarer spine are covered.
- Sensitivity: 8 m margin → 79 parts; 15 m → 125; 2.29° cone → 79 parts, 89.7 m protrusion; 5° cone → 150 parts,
  r 160.9 m needed, fuel storage and drivers also exposed.
- Radiators: 1.922 km² planform, 41,012 m² (2.1 %) inside the envelope, 97.9 % outside. The FDP-1 wings are edge-on
  to an aligned stream; the Wayfarer blades (r 37.1 m) are covered.

Assumptions and unknowns (not computed, not invented):
- Shield areal density and stack OPEN (OD-014): the mass of a larger shield is UNRESOLVED. With an entered density the
  panel feeds it into the closure as an ASSUMPTION (a test value of 50 kg/m² adds 1,672 t for r 112.5 m; not canon).
- Attitude / arrival-cone envelope OPEN (OD-015). 0° is the idealized stream; 2.29° (DIAGNOSTIC) and 5° (PROTOTYPE)
  are presets only.
- Stopping, ejecta, penetration, radiation/shock transmission and survival probability: UNRESOLVED.
- Radiator survivability class and leading-edge thickness: UNKNOWN. Retraction under full thermal load is not assumed.
- Engine size does not follow power; P^1/3 and P^1/2 are hypothetical packaging laws behind a switch.
- Service hardware counted NON_CRITICAL (ASSUMPTION: replaceable).

No canon changed: P11 lives in `data/requirements_p11.json`, beside the unchanged P01–P10.
