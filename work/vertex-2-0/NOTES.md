# Vertex 2.0: integrated propulsion closure (work, not canon)

| | |
| --- | --- |
| Kind | study (research and engineering analysis) |
| Status | ACTIVE; owner Q1-Q4 decided 2026-11-16 15:00Z; 2.2/2.3 rerun: the 2.0 closure does not survive |
| Question | Can any propulsion architecture close one unified mass, energy, thrust, fuel, radiation and thermal budget for the full-return 0.016 c mission? |
| Model base | `f1601d4` (Vertex 1.8 Phase F); production geometry and canon unchanged |
| Report | Claude Doc "Vertex 2.0 — Integrated Propulsion Closure" https://claude.ai/artifact/GaqA2TBvxpKpND5SwaPPiN |

## Function

`ledger.py` (pure, about 50 s) applies one set of shared assumptions (`shared()`, each with its basis) to every candidate and closes the
whole mission as a fixed point: end mass -> propellant -> jet power -> fusion power -> engine, shield, radiator, driver and startup mass
-> end mass. Energy, delta-v and impulse are checked automatically; gates G1-G10 report closure, envelopes, trip time, heat flux,
speculative count, conservation, four nozzles and He-3 supply. Writes `ledger.json`.

## Result

- A0 (drawn), A (improved pulsed), B (quasi-continuous magnetized), C (separated open-geometry pulsed): no closure; 2,000-600,000x the
  371 t that the whole propulsion system may weigh inside the 4.6 kt envelope. Geometry solves interception (C: 10 MW/m2, 0.06 % sky);
  driver recirculation at established gain (50) does not.
- D1 fission fragment diverges (2.3 W of heat per jet watt, mass ratio 8.4); D2 beamed + magsail replaces only the departure burn.
- E Halo Vertex (one speculative principle, Vertex Burn Channeling): closes at 6,057 t with the 0.3 yr trip allowance, and at **4,564 t**
  inside the envelope with 0.6 yr (6.6 yr trip): 22.6 TW fusion, pure D-He3 at 0.075 c, 4 x 117 d, one 64 m REBCO halo ring per
  engine about 2 km aft, 666 t propulsion system. He-3 1,546 t (today 1,094 t).

## Owner questions

Q1 trip time 6.6 yr or a heavier envelope; Q2 He-3 load about 1.5 kt; Q3 burns about 2 km aft with deployed rings, housings at the ship;
Q4 VBC as the single IGNITION principle.

## PROTOTYPE choices

Trip allowance 0.3 yr (gate) and 0.6 yr (recommended case); crew-dose geometry (25 m ship radius, habitat 250 m forward, 5 e-folds of
water credit); 2 t/m3 LiH-W shield; 10 t burn station; leakage 1e-4 and nozzle capture 0.8 for E; VBC external drive 5e-6.

## 2.2 / 2.3 rerun (owner decisions 2026-11-16 15:00Z)

Q1 6.6 yr accepted as a research variant (canon stays 6.0 yr); Q2 no He-3 lock until reconciled; Q3 study the 2 km aft rings, all
four together; Q4 VBC the leading speculative principle, not canon. Files: `trace.py` (exact loop field, relativistic Boris pusher;
`trace.json`), `leak.py` (90,000-particle finite-source Monte Carlo; `leak.json`), `vbc.py` (chain-ignition requirements; `vbc.json`),
`halo.py` (four-ring forces, cross-irradiation strips, compression booms, forward stream, stowage), `ledger2.py` (closure with every
correction; `ledger2.json`, about 15 min on 4 cores).

- Driver: 2.0's code used 0.5 kg/kW (28 t per engine at 56 MW); the report text "0.5 kg per W" was wrong. 2.2 uses 1 kg/kW.
- Fuel: the 1:3 feed cannot reach 0.075 c (tank 1.3e14 J/kg at burnup 0.8; ceiling 0.042 c) and does not close. 1:1 at burnup 0.8
  reaches 0.067 c at most. He-3 is the He-3 fed.
- Nozzle: 2.0's 7.5 mT captured 17-48 %. Capture needs B0 R 6.4-12.8 T m (10-20 MA) with the burn 1.5-2 R aft; then zero ring strikes
  in 90,000 particles (below 3.3e-5 at 95 %); forward stream 2.4-4.7 % within 15 degrees, cleared by a 9 degree inward cant.
- Links: thrust pushes the rings toward the ship, so the 2 km links are braced compression booms, not tethers.
- Result: best corrected mission 13.8 kt departure, 2.5 kt system, 5.2 kt He-3, 0.060 c, 60.6 TW (1:1, burnup 0.8, +0.6 yr).
  Levers: REBCO J_e x2 -> 11.0 kt, 95 % channelling -> 11.7 kt. Closure inside 4.6 kt needs about 70 % less.
- VBC: steady self-sustained stream impossible; refined as chain ignition (1.7-20 kHz pellets, transfer 0.4-3.8 %, focusing gain
  0.6-5.5 million, per-pulse error growth 1.3-1.5x needs sub-ms feedback). Vertex Lock = the pulse the chain no longer needs the
  lighting driver.
- 2.4 (3D variant) not started: the geometry is credible, but the dimensions depend on which mass lever the owner chooses.
