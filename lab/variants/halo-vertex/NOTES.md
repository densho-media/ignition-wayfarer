<!-- lab entry -->
| Lab entry | |
| --- | --- |
| Kind | Variant |
| Status | PARKED (rejected as the propulsion baseline by the owner, 2026-11-17; kept as noncanonical evidence; successor study: Vertex 2.6 compact protected Vertex) |
| Question | Can a Halo Vertex (four ~40-64 m REBCO halo rings on braced booms about 2 km aft, Vertex Burn Channeling) close the full-return 0.016 c mission ledger? |
| Model base | f1601d4 (Vertex 1.8 Phase F); production geometry and canon unchanged |
| Branch | claude/project-thread-6qwiwi, Vertex 2.0-2.5 (b87a9c1, 39ddb77, 44a59c9), 2026-11-16 |
| Open owner questions | none for the baseline (rejected: 2 km exposed structure, ring dust exposure, compression booms, deployment, silhouette, 6.9 kt vs 4.6 kt); VBC stays a research hypothesis |
| Review | REVIEW_VTX24.blend (local, not in Git) in the project files vertex-2-4/; figures/ here; report Claude Doc "Vertex 2.0 — Integrated Propulsion Closure" |

# halo-vertex (Vertex 2.0-2.5): notes

Archived unchanged from `work/vertex-2-0/` on 2026-11-17. Scripts run from the repository root (`python3 lab/variants/halo-vertex/ledger2.py`);
`make_review_vtx24.py` needs the local Phase F review file. Why the owner rejected it as a baseline: the deployed structure is about 2 km
long and leads into the dust stream during braking, the rings are exposed superconductors, thrust puts the links in compression (booms
in a braced frame, buckling), deployment is complex, the compact silhouette is lost, and even with every mass lever it closes at
6.9 kt, not 4.6 kt.


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

## 2.5 mass levers (owner chose "research the mass levers first", 2026-11-16 17:16Z)

`levers.py` (ledger2 closure; `levers.json`): each lever alone on the 13.8 kt case, then together. Ship dose credit 13.5 kt; burnup 0.95
12.0; channelling 0.95 11.7; REBCO fluence 1e23 11.7; J_e x2 11.0; J_e x3 9.9; all with J_e x2 7.5; all with J_e x3 **6.9 kt** (2.4 kt
He-3, 0.072 c); all at +0.3 yr 10.1 kt. Per engine still about 320 t against 85 t allowed, spread over fin, ship shield, structure,
radiators, conductor, boom and strips. Closure inside 4.6 kt needs a burn with far fewer neutrons and photons per jet watt (a second
speculative step) or an envelope of about 7 kt.

## 2.4 Halo Vertex 3D variant (owner chose the ~7 kt research envelope, 2026-11-16 18:35Z)

`make_review_vtx24.py` (Blender, run on lab/studies/vertex-closure/vertex-1-8/REVIEW_VTX18.blend) builds `REVIEW_VTX24.blend` (packed, not in Git; owner copy
in project files vertex-2-4/) and `figures/` previews. WORK_VTX24 adds, at the 2.5 all-lever closure (6.9 kt, 33 TW, 0.072 c): four
41.6 m REBCO rings (20.4 MA, 0.31 T, armour face and 0.96 m neutron fin), burn points 83 m aft on each ring axis, rings canted 9 degrees
inward, cluster radius 499 m, 2 km triangular compression booms (4 m) from the A+ housings braced at 8 stations, repulsion ties, ship
shadow plugs (2.7 m) with the burn stations in their shadow, neighbour strips, translucent plume (25 degrees) and forward-stream
(15 degrees) envelopes. Timeline 1-360: stowed in the A+ housings (silhouette unchanged), booms extend, rings unfurl, burn. Opens
deployed on CAM_VTX24_DEPLOYED; CAM_VTX24_CLUSTER, CAM_VTX24_RING and CAM_VTX24_STOWED also set. Cables and envelopes drawn thicker than
real. Not yet in lab/: moves to lab/variants/halo-vertex on owner approval.
