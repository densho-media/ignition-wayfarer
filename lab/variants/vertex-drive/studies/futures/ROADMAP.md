# T06 roadmap: how the Vertex Drive could become possible

These are developmental hypotheses, not a timeline. Eras are ordered by prerequisite, not by date; no canon date is used because the
IGNITION timeline could not be read in this session (ASSUMPTIONS.md A-27). Nothing here is canon. Every ship number is an FDP-1 solve
from `futures.py` (results/CHAINS.md), and every step value is a TARGET, never a demonstrated result.

Status: **FINAL synthesis**, 2026-11-09, after the T01-T04 handoffs (CONVERGENCE.md).

## The story in one paragraph

Five things must happen, roughly in this order, and none of them is a Fiji property: targets fired at machine cadence; machinery that
runs hot; drivers that compress D-³He with a coupling η_c/α of at least 0.5; a closure-coil pulsed nozzle that reaches its ideal model;
and protection that survives engine-first braking through dust. With all five the ship is about 38 kt (V3), and at the physical limit of
compression about 18 kt (V4, FDP-1's size). Without the coupling it is 110-360 kt; without the nozzle, over 100 kt even at ideal
compression; without the dust answer there is no ship at all.

## Eras

| Era | What becomes possible | Records | Cred. | Prerequisites | What it buys the ship |
| --- | --- | --- | --- | --- | --- |
| **E0 Foundation** (today) | D-T ignition at gain 4.1; compressed D-T at about 600 g/cm³; REBCO at 45.5 T in small coils; SiC logic at 773 K; CNT fibres at 8 GPa; Whipple shields to about 15 km/s | VTX-01, 02B, 07A, T06-NEW-2, 08A | A | none | nothing flies; at 489 K present-component warm loops no T06 ship closes (T01) |
| **E1 Rep-rated fusion** | target factories at plant cadence (0.6 MJ per pellet, T01); heavy-ion drivers 0.25-0.35 wall-plug; engagement to 20 µm; launchers at 2.5-9 km/s (T01, T04 injection 4.6-9.2 km/s) | VTX-01B, 01C, 05A, 05B, 01D | B | E0 | the industrial base; house load falls to 2.6e-5 of fusion |
| **E2 Hot machinery** | fourteen component types each at its own TARGET temperature: equivalent warm loop 628 K | VTX-07A, 07C | B | E1 | the largest single correction: at 700 K the T06 ship would be 13 kt, at 628 K 25 kt (coupling 0.5, alone) |
| **E3 Efficient compression** — **declared** | D-T-sparked D-³He (43-144 kg tritium per mission), then coupling η_c/α ≥ 0.5; He-³ at kilotonne scale (not modelled) | VTX-01D, 01A, 01 | B in physics, declared in degree (D-T06-1) | E1 | 110 kt → 38 kt (0.3 → 0.5); 18 kt at the ideal limit |
| **E4 Fiji-cored closure-coil nozzles** — **declared** | canon Fiji lattice (×30, slow, stabilising) on segmented REBCO loops; closure coils; stored field 15 E_p; η_T 0.79 validated | VTX-02A (canon), 02B, 03, 03C, T03-NEW-1 | C (Fiji) and B; nozzle declared (D-T06-2) | E0 magnets; a D-09-class study | 58 kt → 38 kt (10 → 15 E_p); at literature 0.64 ≥110 kt |
| **E5 Convergence** | light drivers, liquid-sheet warm radiators, thin refractory heat pipes, 3 GPa laminates, lighter armour | VTX-01B, 07B, T06-NEW-1, T06-NEW-2, 06B | B | E2-E4 | closure itself: the Atlas package never closes at coupling 0.2; the T06 package does |
| **Unconverged** | engine-first braking through dust at 0.016 c; loop neutron fluence 3-62× REBCO tolerance | VTX-08, 08A, 08B, 08D | B / UNRESOLVED | validated shield physics at thousands of km/s | +250 t of skirt and shoes buys survival odds, not survival (D-06) |

## Critical breakthroughs, in order of consequence

1. **Compression coupling** (E3, D-T06-1 = D-T04-1). 0.3 → 0.5 takes the ship from 110 to 38 kt.
2. **Pulsed nozzle at its ideal model** (E4, D-T06-2 = D-T03-2). The steepest lever (elasticity -2.9); below about 0.53 no ship reaches
   the mission exhaust velocity at any size (F-T06-1).
3. **Dust** (unconverged, D-06). A precondition, not a mass term.
4. **Hot machinery** (E2). T01's 628 K is the largest single correction to the Atlas.
5. **Driver efficiency and mass** (E1). 0.30 → 0.45 takes V3 from 37.9 to 24.1 kt and V4 from 17.9 to 14.3 kt. T01 calls driver kg/W
   fragile (volt-second scaling).
6. **The engineering package as a whole** (E5). It decides closure, not just size.

## What is deliberately absent

- No new Fiji property (D-07). Fiji lets ring-scale loops run with fewer ampere-turns and holds the flux geometry between pulses.
- No 1 g ship: a 5,084-fold specific-mass gap; 1.5 g does not close.
- No dense, small-pulse ship: the 6,000 g/cm³ chain was withdrawn under T04's bound.
- No replacement of the canon four-nozzle drive (D-08 is not approved).
