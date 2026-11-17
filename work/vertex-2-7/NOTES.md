# Vertex 2.7: exhaust velocity, fuel cycle and protected propulsion

Research only (owner brief 2026-11-17 08:03Z). No canon, geometry, workbook or history changes; no squash.
Report: Claude Doc "Vertex 2.7: Exhaust Velocity, Fuel Cycle and Protected Propulsion" (linked in the thread).

## Function

Bound D-3He exhaust velocity, compare fuel cycles, link He-3 use to the ledger, test whether VBC + SR-26A + SR-26F form one regime,
find the shortest defensible spine, and replace HIGH dust with a justified envelope plus named stress tests, all on the 2.6 C ledger.

## Fixed constraints

- 2.6 ledger and C geometry (work/vertex-2-6/compact.py, protect.py), imported read-only; protected four-engine layout, A+ mechanics.
- Gates: 4.6 kt canon, 7 kt research, +0.6 yr trip, q_max 10 MW/m^2, He-3 1,094 t, dust target 0.1 critical events.

## Code

`fuel.py` (ladder, spread, cycles, isotropic floor), `mission.py` (ve/burnup/nozzle/spread/trip/feed/spine sweeps), `gap.py` (4.6 kt gaps),
`dust.py` (HIGH decomposition, JUSTIFIED envelope, attitude, route), `survive.py` (C inside JUSTIFIED by spine length). Each writes .json/.log.

## Results (corrected braking path, 2026-11-17)

- Path fix (`fixpath.py`, mirrors lab/studies/dust-impacts a62118b): braking legs had reused the accelerating distance, so the home leg ran
  through the Sun (min r -10.96 AU). Corrected: turnaround 324.33 AU, min r 1.0 AU; engine-front events above 5 mm x0.365. 2.6 files unchanged.
- Ideal 0.0885 c; 2.7 point (thermal velocity spread, traced kappa 0.883, b 0.95) caps at 0.074 c, 5,889 t; all levers 0.084 c, 4,523 t.
- Velocity spread is a new correction (thermal 0.905, ambipolar 0.978 of jet energy); 2.6 common-speed 5,928 t becomes 6,084 t at 0.072 c.
- He-3 ~flat in ve: 2,000-2,170 t (2.7 point), 1,388-1,432 t (levers), lowest 1,302 t (perfect nozzle); no feed ratio or fuel cycle helps.
- Full channelling leaves a 9.5 % photon floor (11.6 % isotropic); SR-26A (0.39 %) is independent of VBC.
- Spine floor is dust, not heat: stern bumper stand-off 26 m NOMINAL (spine >= ~76 m), 127 m JUSTIFIED (spine >= ~177 m). 200 m survives JUSTIFIED.
- Dust protection for C: NOMINAL 129 t, JUSTIFIED 216 t (1,451 t below ~177 m), HIGH 9,773 t. HIGH is mostly 1 g Kuiper grains (4,983 t alone);
  debris spread no longer sets stern mass (Brow load x10). Stress: +1 g 8,372 t, +radar tail 1,868 t. Blades 226-603 punctures; flips 1.2;
  rings 0.2; Brow needs a 133 m bumper (77 t).
- JUSTIFIED by spine (2.7 point / levers): 200 m 6,218 / 4,762 t; 475 m 5,863 / 4,636 t; 600 m 5,812 / 4,617 t.
- 4.6 kt: departure met only with every lever (4,523 t, 77 t under; perfect nozzle 4,401 t), but He-3 +258-338 t, four speculative items and
  HIGH dust still fail. In JUSTIFIED the levers miss by 162 t (200 m) and 17 t (600 m). No all-gates closure.

## Open owner questions

1. JUSTIFIED as the dust design envelope? 2. Keep the 200 m research spine (floor ~177 m in JUSTIFIED)? 3. He-3 requirement 1.3-2.2 kt as logistics?
4. Next: traced high-cosine nozzle with forward-stream closure?
