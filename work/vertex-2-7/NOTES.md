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

## Results

- Ideal 0.0885 c; 2.7 point (thermal velocity spread, traced kappa 0.883, b 0.95) caps at 0.074 c, 6,224 t; all levers 0.084 c, 4,766 t.
- Velocity spread is a new correction (thermal 0.905, ambipolar 0.978 of jet energy); 2.6's 6,271 t becomes 6,436 t at 0.072 c.
- He-3 ~flat in ve: 2,250 t (2.7 point), 1,460-1,510 t (levers); no feed ratio or fuel cycle helps.
- Full channelling leaves a 9.5 % photon floor (11.6 % isotropic); SR-26A (0.39 %) is independent of VBC.
- Spine floor is dust, not heat: >= ~130 m (NOMINAL bumper 82 m), ~475 m in JUSTIFIED (420 m stand-off).
- HIGH = 1 g Kuiper grains (unmeasured, 5.3 kt alone) + 15 deg debris spread (untested, 1.8 kt alone). JUSTIFIED: 3.2 kt armour at 200 m or
  406 t at ~475 m (6,535 t; levers 5,153 t). Blades 226-603 punctures; flips 1.2; rings 0.2; Brow needs 133 m bumper.
- 4.6 kt: no. Smallest gap +166 t (64 t system) with every lever; +37 t with a perfect nozzle; +553 t in JUSTIFIED.

## Open owner questions

1. JUSTIFIED as the dust design envelope? 2. Spine ~475 m or revised stern perforation rule? 3. He-3 requirement 1.4-2.3 kt as logistics?
4. Next: traced high-cosine nozzle with forward-stream closure?
