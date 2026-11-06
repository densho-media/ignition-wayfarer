# FDP-1 Spatial Systems V3: validation

`python3 lab/problems/fdp1-requirements/check_v3.py --regen` — **128/128 checks pass** (88 V2 checks, 40 P11 checks). Written by the script; do not edit.

Geometric coverage is the only protection category computed. Stopping, ejecta, penetration, radiation/shock transmission and survival probability are UNRESOLVED; a covered part is not a safe part.

| group | check | result | detail |
| --- | --- | --- | --- |
| existing | dimensional consistency | PASS | 7 equations; mismatched: none |
| existing | departure = end + propellant | PASS | 20,760.2 t vs 20,760.2 t |
| existing | end = dry + reserve | PASS | 7,643.0 t vs 7,643.0 t |
| existing | departure items sum to departure | PASS | 20,760.2 t vs 20,760.2 t |
| existing | propellant = sum of four burns, burns chain | PASS | 13,117.2 t |
| existing | propellant = fused + unburned = He-3 + D | PASS | 8,809.4 + 4,307.8 t (H tamper 36 g) |
| existing | energy ledger sums to fusion power | PASS | 1.728573e+13 W vs 1.728573e+13 W |
| existing | outflows (jet, plume, radiation, radiators) = fusion | PASS | residual 0.00195 W |
| existing | hot and warm loops = sum of their sources | PASS | hot 77.12 GW, warm 24.39 GW |
| existing | recirculating power balance | PASS | recovered 31.73 GW = load 30.15 + loss 1.59 GW |
| existing | integrated energy E = P x t | PASS | 3.1012e+21 J vs record 3.1012e+21 J |
| existing | fusion power = yield x rate = gain x beam x rate | PASS | 17.286 TW |
| existing | thrust: F = m0 a0 = mdot ve = record | PASS | 1.4039 / 1.4039 / 1.4039 MN |
| existing | P_jet = 0.5 F ve = record | PASS | 13.478 TW |
| existing | each burn dv = 0.016 c (rocket equation) | PASS | 4,796.7, 4,796.7, 4,796.7, 4,796.7 km/s |
| existing | burn times = propellant / mdot = record | PASS | 726, 566, 441, 343 d |
| existing | radiator area = Q / (2 eps sigma T^4) = record | PASS | hot 71,977 m2, warm 1.8439 km2 (eps 0.9) |
| existing | wing planform = warm area | PASS | 1.8439 km2 |
| existing | peak acceleration <= 1.5 g ceiling | PASS | 0.0187 g |
| existing | 1 g deficit = specific mass / required | PASS | x89.1 |
| inputs | closure.departure_t = mass.departure | PASS | 2.07602e+07 vs 2.07602e+07 |
| inputs | closure.ve_km_s = prop.ve | PASS | 1.92012e+07 vs 1.92012e+07 |
| inputs | closure.eta_jet = prop.eta_jet | PASS | 0.77971 vs 0.77971 |
| inputs | closure.hot_T = rad.hot_T | PASS | 1800 vs 1800 |
| inputs | closure.warm_T = rad.warm_T | PASS | 600 vs 600 |
| inputs | closure.emissivity = rad.emissivity | PASS | 0.9 vs 0.9 |
| inputs | closure.hot_areal = rad.hot_areal | PASS | 3 vs 3 |
| inputs | closure.warm_areal = rad.warm_areal | PASS | 1 vs 1 |
| inputs | closure.hot_flux = rad.hot_flux | PASS | 1.07146e+06 vs 1.07146e+06 |
| inputs | closure.warm_flux = rad.warm_flux | PASS | 13227.8 vs 13227.8 |
| inputs | closure.propellant_t = mass.propellant | PASS | 1.31172e+07 vs 1.31172e+07 |
| inputs | closure.a0_g = prop.a0_g | PASS | 0.00689557 vs 0.00689557 |
| inputs | closure.alpha_jet = mass.alpha_jet | PASS | 2.84105e-07 vs 2.84105e-07 |
| inputs | wings.chord_m = rad.wing_chord | PASS | 266.75 vs 266.75 |
| inputs | wings.tip_m = rad.wing_tip_radius | PASS | 3573.06 vs 3573.06 |
| inputs | wings.hot_band_m = rad.hot_band | PASS | 106.921 vs 106.921 |
| inputs | wings.reused_hot_m2 = rad.existing_hot_blades_area | PASS | 14934.5 vs 14934.5 |
| inputs | goal1g.max_a0_g = goal1g.max_a0_any_size_g | PASS | 0.011219 vs 0.011219 |
| inputs | goal1g.alpha_jet = goal1g.specific_mass | PASS | 2.68459e-07 vs 2.68459e-07 |
| inputs | heat fractions x fusion = loop totals | PASS | hot and warm |
| baseline | scenario reproduces the record departure mass | PASS | 2.07602e+07 vs 2.07602e+07 |
| baseline | scenario reproduces the record thrust | PASS | 1.40386e+06 vs 1.40386e+06 |
| baseline | scenario reproduces the record jet power | PASS | 1.34779e+13 vs 1.34779e+13 |
| baseline | scenario reproduces the record fusion power | PASS | 1.72857e+13 vs 1.72857e+13 |
| baseline | scenario reproduces the record hot area | PASS | 71976.8 vs 71976.8 |
| baseline | scenario reproduces the record warm area | PASS | 1.84385e+06 vs 1.84385e+06 |
| baseline | scenario reproduces the record wing tip radius | PASS | 3573.06 vs 3573.06 |
| baseline | scenario reproduces the record hot band | PASS | 106.921 vs 106.921 |
| baseline | scenario reproduces the record end mass | PASS | 7.64301e+06 vs 7.64301e+06 |
| baseline | status BASELINE and feasible | PASS | BASELINE |
| baseline | ceiling 0.0106 g (baseline closure) | PASS | 0.01060 g |
| baseline | goal-1g variant ceiling = record 0.011219 g | PASS | 0.011220 g |
| energy | ledger sums to the fusion power | PASS | 1.72857e+13 W |
| energy | thrust = 2 P_jet / v_e (jet power, not fusion power) | PASS | 1.4039 MN |
| energy | jet + uncollimated + rest = fusion | PASS | jet 13.48 TW, uncollimated 3.51 TW |
| energy | hot deposits sum to the hot loop | PASS | 77.12 GW |
| energy | warm deposits sum to the warm loop | PASS | 24.39 GW |
| mass | 15 budget items sum to departure | PASS | 20,760.2 t |
| mass | every non-zero budget item has a cube on its hardware | PASS | all placed |
| encoding | sphere volume proportional to power | PASS | 8x power -> 8x volume |
| encoding | tube cross-section proportional to power | PASS | 4x power -> 4x area |
| encoding | thin tubes flagged | PASS | min 0.4 m |
| encoding | arrow length proportional to force | PASS | 1.40 MN = 280.8 m |
| encoding | cube volume proportional to mass | PASS | 2x mass -> 2x volume |
| scale | nozzle loop 1 radius and station | PASS | r 37.40 m at x -205.94 m |
| scale | nozzle loop 2 radius and station | PASS | r 64.79 m at x -227.54 m |
| scale | nozzle loop 3 radius and station | PASS | r 112.21 m at x -292.33 m |
| scale | wing tip drawn at the record radius | PASS | 3573.1 m |
| scale | drawn warm planform within 1 % of the record warm area | PASS | 1.8428 vs 1.8439 km2 (the 2 m root gap) |
| scale | Wayfarer hull from the baseline fingerprint (metres) | PASS | hull x -134.0..95.0 m |
| scale | habitat rings at canon radius 30 m | PASS | 29.99, 29.99 |
| radiator | hot: eps sigma (2A) T^4 rejects the loop heat | PASS | 77.120 vs 77.120 GW |
| radiator | warm: eps sigma (2A) T^4 rejects the loop heat | PASS | 24.390 vs 24.390 GW |
| temperature | warm area falls monotonically with T (fixed power) | PASS | 583k > 239k > 115k > 47k > 15k > 6k m2 |
| temperature | area ratio follows T^-4 for the bare plate | PASS | flux(1000)/flux(500) = 16 |
| temperature | ceiling rises with T but saturates (hot loop and hardware fixed) | PASS | 0.0158 < 0.0183 < 0.0193 < 0.0200 < 0.0203 < 0.0204 g |
| temperature | T above record flags P06 transport and P07 materials | PASS | ASSUMPTION, INFEASIBLE, P06, P07 |
| feedback | 0.0069 g, record T: gain, closure and marking consistent | PASS | BASELINE, gain 0.650 |
| feedback | 0.05 g, record T: gain, closure and marking consistent | PASS | INFEASIBLE, gain 4.716 |
| feedback | 0.1 g, 1500 K: gain, closure and marking consistent | PASS | INFEASIBLE, gain 5.007 |
| feedback | 0.25 g, 2000 K: gain, closure and marking consistent | PASS | INFEASIBLE, gain 12.318 |
| feedback | 1 g, 2500 K: gain, closure and marking consistent | PASS | INFEASIBLE, gain 49.053 |
| feedback | 0.009 g, record T: gain, closure and marking consistent | PASS | CLOSES, gain 0.849 |
| feedback | 0.011 g, record T: gain, closure and marking consistent | PASS | CLOSES, gain 0.990 |
| reproducible | evaluate is deterministic | PASS | two runs identical |
| reproducible | export_geometry.py regenerates ship_geometry.json byte for byte | PASS | a5728d26824a |
| baseline files | data files unchanged by the scenario runs | PASS | fdp1_parameters.json 5e00548b26, requirements.json c0ba040441, scenario_inputs.json 15729813f2, ship_geometry.json a5728d2682 |
| baseline files | Wayfarer model, canon data and the phase-1/2 parameters untouched (git) | PASS | no diff |
| P11 geometry | shield read from the shield parts (r 10 m, aft plane x 0) | PASS | r 10.0, x_s 0.0 |
| P11 geometry | aligned stream: clearance independent of distance behind the shield | PASS | 5.000000 vs 5.000000 |
| P11 geometry | cone: clearance shrinks by L·tanθ | PASS | 1.507923 m at L 100 m, θ 2.0° |
| P11 geometry | fully covered component | PASS | min clearance 7.172 m |
| P11 geometry | partially exposed component: status PARTIAL, 0 < exposed < total | PASS | 8.31 of 16.00 m² |
| P11 geometry | partial exposed area matches the analytic value (±3 %) | PASS | 8.310 vs 8.268 m² |
| P11 geometry | fully exposed component | PASS | 16.00 m², protrusion 12.09 m |
| P11 geometry | protrusion = farthest point outside the silhouette | PASS | 12.0907 m |
| P11 geometry | component at the boundary (clearance inside the uncertainty band) | PASS | min clearance 0.500 m |
| P11 geometry | non-axisymmetric component: exposed area of a 30 × 2 m plate (±3 %) | PASS | 20.180 vs 20.067 m² |
| P11 geometry | rolling the plate 90° about X gives the same exposure (circle symmetry) | PASS | 20.180 m² |
| P11 geometry | off-axis rolled plate is worse than the centred one | PASS | 24.58 m² |
| P11 geometry | noncircular shield: polygon area | PASS | 400.0 m² |
| P11 geometry | noncircular shield: a corner point is covered by the square, not by the r 10 circle | PASS | square +0.500 m, circle -3.435 m |
| P11 geometry | noncircular shield: a corner box exposed by the r 10 circle is covered by the 20 m square | PASS | COVERED, min clearance 1.000 m |
| P11 geometry | safety margin lowers every clearance by exactly the margin | PASS | 7.172 → 4.172 m |
| P11 geometry | a large margin turns a covered part into an exposed one | PASS | PARTIAL |
| P11 geometry | required radius covers every sample with zero slack | PASS | R 24.946 m, worst clearance 1.33e-15 m |
| P11 scaling | shield area ∝ R² (r 90 m = 4 × the canon r 45 m area) | PASS | 25,447 m² |
| P11 scaling | added shield mass = areal density × added area | PASS | 247.4 t at 50 kg/m² (test value) |
| P11 scaling | added mass raises the thrust and fusion power needed at the same acceleration | PASS | thrust 1.404 → 1.573 MN |
| P11 scaling | added mass propagates through the power-to-mass feedback (departure grows by more than the added mass) | PASS | departure +2,495.5 t for +247.4 t (×10.09) |
| P11 scaling | engine geometry does not follow power or mass without a packaging law | PASS | r 112.55 m at 1 g |
| P11 scaling | a chosen packaging law scales the engine radially and is listed as an assumption | PASS | ×1.936 → r 217.8 m |
| P11 protection | radiators are not mixed into the critical-part assessment | PASS | 278 assessed parts, 15 radiator panels |
| P11 protection | no areal density: shield-mass effect UNRESOLVED, no mass invented | PASS | UNRESOLVED; Mass UNRESOLVED |
| P11 protection | a supplied areal density is labelled ASSUMPTION | PASS | ASSUMPTION |
| P11 protection | enlarged shield covers every critical part geometrically | PASS | r 112.55 m: 0 exposed |
| P11 protection | covered ≠ safe: Geometry is UNRESOLVED (not PASS) when every part is covered | PASS | every critical part is geometrically covered; stopping, ejecta and penetration unmodelled (P11) |
| P11 protection | six protection categories; only geometric coverage is computed | PASS | geometric coverage, shield stopping capability, secondary ejecta and fragmentation, particle penetration, radiation and shock transmission, mission survival probability |
| P11 protection | no false PASS: Geometry, Radiation, Structures, Thermal never PASS; physically validated never claimed | PASS | PASS only for ['Mass']; statuses valid |
| P11 protection | the ghost shield never modifies the canonical shield | PASS | r 45.0 m |
| P11 protection | a wider arrival cone never protects more | PASS | 50 → 150 parts, 67.5 → 115.9 m |
| P11 regression | baseline shield r 45 m (90 m canon), aft plane x 260.55 m | PASS | r 45.0 m, x 260.55 m |
| P11 regression | engine maximum radius 112.55 m, set by loop 3 | PASS | 112.547 m (FDP1_Loop_3_Sector_Feed_1) |
| P11 regression | baseline violation reported, not hidden: engine clearance −67.5 m, Geometry FAIL | PASS | -67.55 m |
| P11 regression | radiators ~97.9 % of planform outside the envelope | PASS | 97.87 % |
| P11 regression | the V3 scenario at the record reproduces the V2 baseline closure | PASS | 20,760.2 t |
| P11 regression | P11 kept separate and UNRESOLVED; requirements.json still P01–P10 | PASS | P01–P10 + P11 (unresolved) |
| P11 regression | V3 scenario inputs unchanged by the checks | PASS | hashes stable |

## P11 baseline (aligned stream, margin 0, canon 90 m shield)

- shield r 45.0 m, aft plane x 260.55 m
- engine maximum radius 112.55 m (FDP1_Loop_3_Sector_Feed_1); protected radius there 45.0 m; clearance -67.5 m
- shield radius that would cover every critical part: 112.5 m

| system | parts outside | exposed frontal (m²) | max protrusion (m) |
| --- | --- | --- | --- |
| magnetic nozzle loops and Fiji lattice | 24 | 882 | 67.5 |
| shadow shield and loop armour | 2 | 261 | 67.1 |
| FDP-1 thrust structure | 12 | 223 | 67.5 |
| pulsed power and feeds | 8 | 84 | 67.5 |
| thermal lines and wings | 4 | 41 | 67.4 |

## Sensitivity (canon shield)

| arrival cone | margin | critical parts outside | exposed frontal (m²) | max protrusion (m) | shield r needed (m) | radiators outside |
| --- | --- | --- | --- | --- | --- | --- |
| 0° | 0 m | 50 | 1,492 | 67.5 | 112.5 | 97.9 % |
| 0° | 8 m | 79 | 1,782 | 75.5 | 120.5 | 98.2 % |
| 0° | 15 m | 125 | 4,063 | 82.5 | 127.5 | 98.6 % |
| 2.29° | 0 m | 79 | 1,853 | 89.7 | 134.7 | 98.3 % |
| 5° | 0 m | 150 | 2,523 | 115.9 | 160.9 | 99.2 % |

## Radiators (assessed separately)

- planform 1.922 km², inside the envelope 41,012 m², outside 1.881 km² (97.9 %)
- the FDP-1 wings lie in the XY plane: edge-on to an aligned stream, so their frontal area is leading-edge thickness × span; the thickness and the survivability class are UNKNOWN
- retraction under full thermal load is not assumed

## Input hashes (sha256)

- `data/fdp1_parameters.json` 5e00548b264d40e374342292c0e7b16d2e45cf53d38bb87c608f5ee0a4e45a36
- `data/requirements.json` c0ba040441f5a4998000d784241175d01e346a4e4192b65cfb083ead9512f457
- `data/scenario_inputs.json` 15729813f2d990c040367c7b61f2672e0d3cb90eafa967a6550c752bddf19287
- `data/ship_geometry.json` a5728d26824a26a1d83dc2e78eacadb789e19f319a18a22793cd8a52da36ac60
- `data/protection_inputs.json` 3552db4b1d02195279e07d678d978bd874e789f58759119b4adc64fe26682e07
- `data/requirements_p11.json` 5acc4af9671f47622c37bc8e119f88a20a9449df0d9ea1d4173285c7e570805e
