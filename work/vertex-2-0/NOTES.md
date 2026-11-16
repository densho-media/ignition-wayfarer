# Vertex 2.0: integrated propulsion closure (work, not canon)

| | |
| --- | --- |
| Kind | study (research and engineering analysis) |
| Status | ACTIVE, awaiting owner decisions Q1-Q4 |
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
