# T06 roadmap: how the Vertex Drive could become possible

These are developmental hypotheses, not a timeline. The eras are ordered by prerequisite, not by date. No canon date is used, because the
IGNITION timeline could not be read in this session (ASSUMPTIONS.md A-27). Nothing here is canon. Every ship number is an FDP-1 solve
from `futures.py` (results in `results/CHAINS.md`), and every step value is a TARGET, never a demonstrated result.

Status: **GATHERING draft** (2026-11-09). It is built on the Atlas, T06's chains, and the T01 and T04 EARLY findings. The final
handoffs will revise it.

## The story in one paragraph

Four things must happen, roughly in this order, and none of them is a Fiji property:

1. Fusion targets must be made and fired at machine cadence (the rep-rated era).
2. Machinery must learn to run hot.
3. Drivers must compress D-³He fuel with a coupling η_c/α of about 0.3-0.5. Gain follows from that coupling: about 700-900 at
   2,000-3,000 g/cm³, where the demonstrated gain is 4.1. This is the one breakthrough IGNITION would have to declare.
4. A pulsed magnetic nozzle must be validated near its theoretical efficiency.

Fiji, as canon defines it, makes ring-scale nozzle loops practical but closes none of these gaps. With all four, the whole engineering
package is what decides whether a ship exists: a T06 V4-class ship of about 8.3 kt, or 10.3-12.7 kt at coupling 0.3. Dust at 0.016 c
stays unsolved in every era.

## Eras

| Era | What becomes possible | Records | Credibility | Prerequisites | What it buys the ship (FDP-1 solve) |
| --- | --- | --- | --- | --- | --- |
| **E0 Foundation** (today) | D-T ignition at target gain 4.1; compressed D-T fuel at about 600 g/cm³; REBCO at 45.5 T in small coils; SiC logic for a year at 773 K; CNT fibres at 8 GPa; Whipple shields to about 15 km/s | VTX-01, 02B, 07A, T06-NEW-2, 08A | A | none | nothing flies |
| **E1 Rep-rated fusion** | target factories at power-plant cadence; heavy-ion drivers at 0.25-0.35 wall-plug and 10-100 Hz; target engagement to 20 µm; launchers at several km/s (T01 and T04: the next target must survive the last pulse) | VTX-01B, 01C, 05A, 05B, 01D | B | E0 | the industrial base |
| **E2 Hot machinery** | power conversion at 600-800 K (T01 EARLY: the component mix gives an equivalent 628 K); a bottom-up house load of 0.003-0.014 % | VTX-07A, 07C | B | E1 | the largest engineering saving (warm-loop elasticity -1.7) |
| **E3 Efficient compression** | D-T-sparked D-³He burn, then fuel-only D-³He at compression coupling η_c/α 0.3-0.5, which gives gain 700-900 at 2,000-3,000 g/cm³; He-³ at the kilotonne scale | VTX-01D, 01A, 01 | B in physics, **declared** in degree (D-T06-1) | E1, plus a He-³ economy (not modelled) | the ship closes at all: at η_c/α 0.2 the Atlas V1 package does not close, and at 0.3 it is 161 kt |
| **E4 Fiji-cored nozzles** | the canon Fiji lattice (×30 amplification, slow, stabilising) on large segmented no-insulation REBCO loops; a pulsed nozzle validated on test stands | VTX-02A (canon), 02B, 03, 03A, 03C | C (Fiji, canon) and B; nozzle **declared** in degree (D-T06-2) | E0 magnets; a D-09-class study | holds the nozzle at 0.79-0.86 (elasticity -2.9); at 0.72 the ship grows 38 % |
| **E5 Convergence** | light drivers, liquid-sheet warm radiators, thin refractory heat pipes, 3 GPa laminates, lighter armour | VTX-01B, 07B, T06-NEW-1, T06-NEW-2, 06B | B | E2-E4 | at η_c/α 0.3: 10.3 kt (Atlas thermal) or 12.4 kt (T01 EARLY thermal) instead of 161 kt; V3 12,655 t, V4 8,295 t |
| **Unconverged** | survival of engine-first braking through interstellar dust at 0.016 c | VTX-08, 08A, 08B, 08D | B / UNRESOLVED | validated shield physics at thousands of km/s | no mass credit; a precondition for any Vertex ship (D-06) |

## Critical breakthroughs, in order of consequence

1. **Compression coupling** (VTX-01A, E3). Gain and density are one lever under the energy bound (T04 EARLY). The Atlas gain of 3,000
   at 3,000 g/cm³ would need η_c/α 1.68, which is impossible. The declared quantity should be the coupling. → D-T06-1.
2. **Pulsed nozzle efficiency** (VTX-03, E4). This is the steepest mass lever. Below about 0.53, no ship reaches the mission exhaust
   velocity at any size (the ve gate, F-T06-1). → D-T06-2, which needs T03 and D-09.
3. **Hot machinery** (VTX-07A, E2). A 600 K warm loop costs +53 % against 700 K. T01 finds that the split loop is 628 K, not 700-800 K.
4. **Driver efficiency and mass** (VTX-01B, E1). The published 0.30 against the assumed 0.45 costs +25 % on V1, and +66 % on V3 (V3c).
   Driver loss is 75-95 % of the warm heat once the house load is booked (T01).
5. **The engineering package as a whole** (E5). Under the bound it is the difference between a ship and no ship.
6. **Dust** (VTX-08, unconverged). No era above solves it.

## What is deliberately absent

- No new Fiji property in any era (D-07). In this story Fiji's role is what its canon card says: it lets ring-scale nozzle loops run
  with fewer ampere-turns and holds a stable flux geometry between pulses.
- No 1 g ship. Every specific mass would have to be about 64 times lower, and 1.5 g found no closing solution (CONVERGENCE.md section 4).
- No dense, small-pulse ship. The first-draft compression chain (6,000 g/cm³, loops at half radius) was withdrawn under the bound.
- No replacement of the canon four-nozzle drive (D-08 is not approved).
