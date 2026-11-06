<!-- lab entry -->
| Lab entry | |
| --- | --- |
| Kind | Study |
| Status | PROMOTED into main 1f9eba1; kept as a reusable radiator tool |
| Question | Radiator view-factor Monte Carlo (radmc.py) and the blade concepts behind the Graded Thermal Blade. |
| Model base | main 90df1a9 |
| Salvaged from | claude/project-thread-qlrsa7 @ b320e9d, 2026-11-06 |
| Open owner questions | None. Kept numbers: references/evidence/graded_thermal_blade.json. |
| Review | project files review/graded_thermal_blade_2026-11-01/ |

# Graded Thermal Blade (owner brief 2026-11-01, thread "Replace radiator baffles with graded thermal blade")

Branch `claude/project-thread-qlrsa7` from main 90df1a9. Study code here: `radmc.py` (band-spectral Monte Carlo), `ship.py`
(scene from the spec), `concepts.py` (A-D builders), `study.py` / `run_concept.py` (driver), `gill_run.py`, `hot_loss.py`;
results in `results/*.json`. Run: `python3 study.py <config>` from this folder (numpy, 4 processes, 2-4 min per config).

## Function

Reject three heat grades aft of the rings without the 1800 K blades heating the cooler sections, the habitat rings or the tank farm,
with fewer and smaller separating structures than the RAD-ZONE baffles.

## Fixed constraints

- Three fixed blade planes at 30/150/270 deg, root r 6.5 m, outer r 37 m (shield shadow, 8 m margin), no fold, hinge or cant.
- Hot blade 182.149 x 30.5 m at 1800 K, eps 0.90, unchanged; its front X 48.9 m. WARM 440 K / 5 MW, LOW 300 K / 1 MW (PROTOTYPE loads).
- The district stays 44.5 m (X 48.9-93.4): ring A, the bypass collar, the tank farm and everything forward keep their stations.
- Kirchhoff per wavelength: a coating's absorptance for a source equals its band-weighted emissivity at that source's spectrum.

## Model (what the numbers include)

- Planar triangles, two-sided groups, 8 wavelength bands (0-2.5-4.5-6-8-9.5-12-20-inf um) with Planck fractions per temperature.
- Rays from each receiver; reciprocity gives absorbed power from every hotter group, including multiple diffuse and specular bounces.
- Reflector sheets are adiabatic with their own spectral emissivity; their temperatures are solved (bisection, fixed point).
- Casing and root bands are adiabatic re-radiators (MLI-wrapped, gray); rings (aft face and rims) and the tank farm (a black disc
  r 6-34.5 m at its aft face, X 109.25 m, an upper bound) are cold receivers.
- Limits: 20,000 rays per band per group (about +-1-2 % on section nets); no conduction through supports (sheets are thermally
  floating; supports are short spokes, see below); the casing temperature is not solved; no sunlight in the Monte Carlo (docking is
  analytic below); metals as gray specular (real polished metals absorb more at short wavelength: covered by the end-of-life case).
- Check: the gray WARM-to-hot coupling of the open layout agrees with the existing `mutual_screen` (11.4 vs 12.0 kW/m2).

## Findings

1. **The existing baffles do not work as built.** The 0.10 back-load was an assumption. Solved: hot-side layer 1245 K, its forward
   layer 917 K at eps 0.08 (3.2 kW/m2), right next to the WARM sheet: WARM absorbs 3.7 MW from it, net 2.36 MW for a 5 MW load
   (-53 %). LOW passes (+25 %) behind its own baffle pair.
2. **The baffles also do a job nobody listed:** without any blocker the hot blades put 30 MW on ring A and 34 MW on the tank-farm
   aft face in a burn (gray cool sections net-heated 6-10 x). A full-diameter shield at the hot front is required for the forward
   ship regardless of the cool sections. Wedge reflectors that only fill the blade-to-blade hull (B) leave 7 / 5 MW on rings / tanks.
3. **WARM and LOW do not need a shield between them.** Same plane: zero view; across the wedge the 440 K sheet puts < 0.11 MW on LOW.
4. **A V-groove bulkhead fixes the leak.** Three sheets (0 / 5 / 10 deg, forward-leaning) vent the heat between them radially to
   space: layers 1204 / 805 / 493 K instead of 1265 / 1033 / 760 K for three flat layers. WARM interference falls from 62 % to ~8 %.
5. **Spectral selectivity is real but not the lever here.** OSR (silvered fused silica) absorbs 0.18 of an 1800 K spectrum while
   emitting 0.81 at 300 K / 0.74 at 440 K: 5x less hot pick-up than gray, still net-heated without a blocker (WARM -3.1 MW). With
   the bulkhead the hot view is gone, so the higher-emissivity white ceramic (AZ-93 family, ISS radiators) wins; its 0.15 solar
   absorptance is what matters (docking near the Sun).
6. **Directional gills (A) fail**: beta 70 deg: WARM -13.3 MW, LOW -4.1 MW; beta 50: -3.1 / -0.36 MW; rings and tanks 26-29 MW. The
   fins near the break must be almost transverse to hide from the blades, so their polished backs become hot-facing baffles that
   are cooled by the warm loop, and they look forward onto the rings.
7. **Separate arrays (D)**: Q38 found 746 m2 of usable shadowed area forward; the sections need about 3,570 m2 of planform, and the
   forward ship still needs the bulkhead. No credible site.
8. **Directional hot emission** (suppressing the blades' grazing emission, which is what reaches the forward ship at 60-85 deg) would
   cost about 20 % of the hot blades' hemispherical emission; rejected (the hot blade is deliberately undersized).

## Selected design (C*, "Graded Thermal Blade")

HOT blade (unchanged) | one V-groove thermal bulkhead (offsets 0.5/0.8/1.1 m from the blade front, slopes 0/5/10 deg, eps 0.12 / 0.08
/ 0.05: polished Mo or Nb-alloy, polished Ti or superalloy, gold or silver on Ti) | 0.4 m clearance | WARM 22.5 m (root line; aft edge
on the diagonal of the last layer, 17.0 m at the rim, 19.7 m mean) | 0.5 m expansion joint | LOW 20.0 m | ring A slot. White ceramic
on both sides of every zone sheet; zone root strip 0.5 m (no 1800 K root transition is needed at 440/300 K), sheets r 7.0-37 m.

| Scenario | WARM net / margin | LOW net / margin | Bulkhead layers (K) |
| --- | --- | --- | --- |
| 1 Maximum drive (hot 1800 K), beginning of life | 6.17 MW / +23 % | 1.26 MW / +26 % | 1204 / 805 / 493 |
| 2 Cruise, drive off (blades 440 K drain-back) | 6.38 / +28 % | 1.30 / +30 % | 296 / 212 / 270 |
| 3 Post-burn cooling (blades 1300 K) | 6.34 / +27 % | 1.29 / +29 % | 871 / 583 / 377 |
| 4 Docking, Sun at 1 AU on the sheets (analytic, BOL / EOL) | capacity -4 % / -7 % | capacity -16 % / -33 %; 1.09 / 0.78 MW for the 0.7 MW docking load | cold |
| 5 Degraded: end-of-life coatings and layers | 5.73 / +15 % | 1.12 / +12 % | 1217 / 874 / 571 |
| 5 Degraded: end of life and 10 % of cells isolated | 5.16 / +3 % | 1.01 / +1 % | |
| 5 Degraded: one blade plane's circuit lost (2 of 3) | ~4.1 / -18 % | ~0.84 / -16 % | |

Docking (scenario 4, analytic): the three planes present about 2 one-face areas to a Sun perpendicular to X, so the fraction of a
section's capacity lost is alpha_s x 1361 x 2 / (6 x eps sigma T^4): LOW 16 % (beginning of life) / 33 % (end of life), WARM 4 % / 7 %.
In docking the LOW load is the cryocoolers and avionics, 0.7 MW: coast capacity 1.30 MW x 0.84 = 1.09 MW (BOL), 1.16 x 0.67 = 0.78 MW
(EOL) still covers it. The current gray 0.9 sheets would lose about 98 % of LOW in full sun.

One lost circuit: the shortfall goes into the hot loop by heat pump (the F02 burn mode): WARM 0.9 MW needs about 5 MW of work
(half Carnot, 440 to 1800 K), 6 MW more in the hot loop against its 3.6 GW other-loads allowance; LOW 0.16 MW into WARM by 0.15 MW of
work. In the coast the hot blades' drain-back warm channels (51 MW) cover WARM.

Forward ship (maximum drive): ring A 0.33 MW (WARM 0.21, LOW 0.10, bulkhead 0.03) against 0.12 MW today; tank-farm aft disc 0.38 MW
(0.13 today), an upper bound for a black disc. Both come from the 300-440 K sheets (no hot view): ring A's aft face, already excluded
as a cold radiator in HIGH_POWER (thermal_loops), stays roughly neutral; the tank aft caps see about 100 W/m2 of 300-500 K
radiation, a normal MLI outer boundary. Hot blades: 0.4 % of their emission comes back from the bulkhead, the same as the current
baffles; the hot face of the bulkhead absorbs 0.6 % (eps 0.12 vs 0.08), net -0.2 % +- 0.15 % to space versus today (hot_loss.json).

## Mass, area (first order, PROTOTYPE areal masses)

| | Current (2 stations x 2 flat discs) | Selected (1 V-groove station, 3 sheets) |
| --- | --- | --- |
| Shield sheets | 4 x 4,184 m2 = 16,736 m2 | 4,184 + 4,200 + 4,249 = 12,633 m2 (-25 %) |
| Shield mass (sheets 0.60 / 0.35 kg/m2, frames 1.16 t per layer) | ~11.5 t | 8.95 t (-2.6 t) |
| Zone sheets, planform | 3,706 m2 (incl. 3 m root bands) | 3,573 m2 + 64 m2 root strips |
| Two-face emitting area | 6,682 m2 | 7,145 m2 (+7 %) |
| Zone sheet mass at 5 kg/m2 planform | 18.5 t | 18.2 t |
| District total | ~30 t | ~27 t (about -3 t, -10 %) |
| Crawler/EVA gates | 2 stations x 2 layers | 1 station x 3 layers |
| Net WARM / LOW at maximum drive | 2.36 / 1.25 MW (-53 % / +25 %) | 6.17 / 1.26 MW (+23 % / +26 %) |

## Structure, expansion, maintenance (judgment)

- Layer growth from 300 K: layer 1 (Mo, 5.5e-6/K, 1204 K) 0.15 m on its 31 m radius; layer 2 (Ti, 805 K) 0.15 m; layer 3 0.06 m.
  Each layer is 36 overlapping gores (labyrinth overlap >= 0.2 m, no straight gap) on sliding clips; the rim ring is segmented.
  The cone layers grow mostly in their own surface, so the V gaps (0.3 m at the casing) change by under 0.03 m.
- The bulkhead hangs from the casing and the WARM root booms (cool side), never from the 1800 K blade spar; spokes run along the
  three blade planes where the blades already cast an edge-on shadow. The gores carry no load but their own tension.
- Penetrations: none for coolant (no circuit crosses). One crawler/EVA gate per layer at the casing, opened only in the coast.
- Vibration, gore flutter during ignition transients, MMOD perforation (a hole in layer 1 is a local hot spot on layer 2): OPEN.

## Unknowns / OPEN

Coating qualification at the 440 K section (AZ-93 is flown near 300 K), polished-refractory emissivity at 1200 K over years, gore
seams and their leak, layer support conduction, the sheets' structure and mass (B01), bulkhead dynamics. All PROTOTYPE.

## Decisions

- Selected C* in the existing 44.5 m. WARM/LOW baffle pair removed; HOT/WARM baffle pair replaced by the V-groove bulkhead.
- Kept a full-diameter shield: required for the rings and the tank farm (finding 2), not only for the cool sections.
- Coating white ceramic (not OSR): higher emissivity once the hot view is blocked; OSR stays the option if the WARM/LOW sections must
  ever face the blades.
