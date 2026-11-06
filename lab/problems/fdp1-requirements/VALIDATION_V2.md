# FDP-1 Spatial Systems V2: validation

`python3 lab/problems/fdp1-requirements/check_v2.py` — **88/88 checks pass.** Written by the script; do not edit.

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

## The five test configurations

Scaling: baseline closure (today's FDP-1 alpha). Values for an infeasible target are the lower bound at today's 20,760 t departure mass: no departure mass closes, so the real requirement is larger.

| a (g) | warm loop | status | ceiling (g) | loop gain | basis | fusion (TW) | thrust (MN) | heat (GW) | radiators (km²) | wing tip (km) | engine (t) | flags |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0.0069 | 600 K | BASELINE | 0.0106 | 0.65 | closed design | 17.3 | 1.40 | 102 | 1.92 | 3.57 | 3,829 |  |
| 0.05 | 600 K | INFEASIBLE | 0.0106 | 4.72 | at today's mass (lower bound; no closure) | 125.3 | 10.18 | 736 | 13.89 | 26.02 | 27,765 | INFEASIBLE, P09 |
| 0.1 | 1500 K | INFEASIBLE | 0.0200 | 5.01 | at today's mass (lower bound; no closure) | 250.7 | 20.36 | 1,472 | 1.73 | 3.22 | 29,475 | INFEASIBLE, P06, ASSUMPTION, P07 |
| 0.25 | 2000 K | INFEASIBLE | 0.0203 | 12.32 | at today's mass (lower bound; no closure) | 626.7 | 50.90 | 3,680 | 3.15 | 5.89 | 72,518 | INFEASIBLE, P06, ASSUMPTION, P07, P09 |
| 1 | 2500 K | INFEASIBLE | 0.0204 | 49.05 | at today's mass (lower bound; no closure) | 2,506.8 | 203.59 | 14,721 | 11.33 | 21.21 | 288,793 | INFEASIBLE, P06, ASSUMPTION, P07, P09 |

The ceiling is a property of today's scaling assumptions (drive and radiator mass per W, exhaust velocity, tank fraction), not a physical limit. The record's own goal-1g study uses a slightly lower specific mass and reaches 0.0112 g; the panel offers it as the second scaling option.

## Input hashes (sha256)

- `data/fdp1_parameters.json` 5e00548b264d40e374342292c0e7b16d2e45cf53d38bb87c608f5ee0a4e45a36
- `data/requirements.json` c0ba040441f5a4998000d784241175d01e346a4e4192b65cfb083ead9512f457
- `data/scenario_inputs.json` 15729813f2d990c040367c7b61f2672e0d3cb90eafa967a6550c752bddf19287
- `data/ship_geometry.json` a5728d26824a26a1d83dc2e78eacadb789e19f319a18a22793cd8a52da36ac60
