# T06 convergence analysis

Status: **FINAL synthesis**, 2026-11-09. Inputs: the Atlas at `8de3ffa`, T06's own FDP-1 solves, and the final handoffs of
T01 thermal (`claude/project-thread-93sqqi` 1302708), T02 dust (`claude/project-thread-uwi5pl` 3c665ec), T03 nozzle
(`claude/project-thread-ujxhjo` 59244a9) and T04 ignition (`claude/project-thread-9hxayw` fd4ff3d).

All numbers come from `futures.py` (generated tables in `results/CHAINS.md`, data in `results/futures.json`). The FDP-1 calculator, the
four-burn engine and `convergence.py` are imported read-only. V0 through this adapter reproduces 20,760 t, and the energy ledger closes
in every combined solve. Every step value is a TARGET, never a demonstrated result. Research only, not canon.

## 0. The headline

**Once the four threads' corrections are applied together, the Vertex ship is heavier than the Atlas said, and it exists only if
IGNITION declares two breakthroughs.**

| Ship (T06 engineering package, every T01-T04 correction, driver 0.30) | Coupling η_c/α | ρ g/cm³ | Gain | Departure |
| --- | --- | --- | --- | --- |
| Not declared (0.2) | 0.2 | 500 | 1,180 | 362 kt |
| Not declared (0.3) | 0.3 | 1,000 | 1,115 | 110 kt |
| **V3 proposal** (declared 0.5) | 0.5 | 2,000 | 1,171 | **37.9 kt** |
| **V4 proposal** (ideal-compression limit) | 1.0 | 3,000 | 1,787 | **17.9 kt** |
| Atlas V0 (FDP-1 optimistic tier), for comparison | 1.68 needed | 3,000 | 3,000 | 20.8 kt, **not energy-consistent** |

All at the closure-coil nozzle at η_T 0.791 (T03's ideal-model upper bound). FDP-1's 20.8 kt is therefore an ideal-limit ship, not a
planning ship (F-T06-5). Five further penalties have no calculator path and are not booked (section 3); each makes these numbers heavier.

## 1. Gain and compression are one lever

T04 shows that compressing fuel to density ρ costs at least its Fermi-degenerate energy, so target gain is bounded:
**G ≤ 1,787 × (η_c/α) × (ρ / 3,000 g/cm³)^(-2/3)**, with η_c/α ≤ 1 by definition and present implosions in the per-cent range.

| Case | ρ g/cm³ | Gain | η_c/α needed | Energy-consistent |
| --- | --- | --- | --- | --- |
| Atlas V0, V1, V2 | 3,000 | 3,000 | 1.68 | **NO** |
| T06 chains K1-K5, grand endpoint (sensitivity only) | 3,000-6,000 | 3,000-6,000 | 1.68-5.33 | **NO** |
| V3 proposal | 2,000 | 1,171 | 0.50 | yes (declared) |
| V4 proposal | 3,000 | 1,787 | 1.00 | yes (the bound itself) |

Denser fuel lowers the gain the driver can reach, so density and gain must be chosen together. The quantity IGNITION would declare is
the **coupling**, not the gain (D-T06-1, same question as T04 D-T04-1). T06's first-draft compression chain K4 (6,000 g/cm³, half-size
nozzle) is withdrawn.

## 2. What each thread changed

Six corrections from the handoffs, applied to the T06 package at a consistent target (results/CHAINS.md, "Per-thread cost"):

| Thread | Correction | Alone, coupling 0.5 (start 13,144 t) | Alone, ideal coupling (start 8,796 t) |
| --- | --- | --- | --- |
| T01 | equivalent warm loop 628 K, not 700-800 K | **25,141 t** (largest) | 10,661 t |
| T01 | bottom-up house load 2.6e-5 of fusion | 12,800 t (a saving) | 8,640 t |
| T03 | plume strike 0.065 of nozzle loss, not 0.02 | 15,166 t | 9,663 t |
| T03 | stored field 15 E_p for the closure-coil nozzle | **18,865 t** | 12,581 t |
| T03 | η_T = η_mom² = 0.791 (upper bound, nozzle C) | 13,103 t | 8,778 t |
| T02 | +250 t engine skirt and LiH loop shoes | 15,303 t | 10,249 t |
| **All six** | | **45,786 t** | **17,907 t** |

(The cumulative coupling-0.5 value, 45,786 t at 3,000 g/cm³, is above V3's 37,895 t because V3 picks the better density 2,000 g/cm³.)

The thermal correction is the largest. T01 finds that a split warm loop of fourteen component types, each at its own TARGET temperature,
behaves like one loop at 628 K. Only 489 K is supported by present components, and at that value no T06 ship closes.

## 3. Integrated frontier and what is not booked

Lightest closing ship per coupling, gain at the bound, density searched (results/CHAINS.md "Integrated frontier"):

| Lever set | η_c/α | Nozzle C at 15 E_p (η_T 0.791) | Nozzle C at 10 E_p (0.740) | Literature best (0.64) |
| --- | --- | --- | --- | --- |
| Atlas engineering | 0.2 | none closes | none closes | none closes |
| Atlas engineering | 0.3 | 1,747 kt | none closes | none closes |
| Atlas engineering | 0.5 | 368 kt | 1,059 kt | 29,542 kt |
| Atlas engineering | 1.0 | 68.4 kt | 125 kt | 2,817 kt |
| T06 package | 0.2 | 362 kt | 655 kt | 15,552 kt |
| T06 package | 0.3 | 110 kt | 189 kt | 4,191 kt |
| T06 package | 0.5 | **37.9 kt** | 57.8 kt | 605 kt |
| T06 package | 1.0 | **17.9 kt** | 22.7 kt | 110 kt |

Not booked (no calculator path; each adds mass):

- T01: one-target-in-flight launcher at 4.0 / 2.5 km/s: +6.3 % / +17.5 % departure (D-T01-2).
- T03: closure coils and their larger envelope: solid angle 0.040-0.051 against V1's 0.017 (more armour and hot-loop heat).
- T02: LiH loop shoes: +0.0127 of hardware solid angle.
- T03: warm eddy-current screens: about 0.1 % of plasma energy (0.03-1 %) into the hot loop.
- T04: fast ignitor beam line and D-T core: 43-144 kg tritium per mission.

## 4. What is real, what is hopeful

| Chain | Mechanism | After the four threads | Verdict |
| --- | --- | --- | --- |
| **K1 recirculating power** | driver 0.30→0.45 and half its mass (VTX-01B), house load (VTX-01C), gain (VTX-01A) | driver steps hold; T01 house load is a real saving; the gain step is ruled out by the bound | **REAL** (driver, house); gain step **WITHDRAWN** |
| **K2 thermal** | hot machinery (VTX-07A), liquid-sheet warm radiators (VTX-07B), thin refractory heat pipes (T06-NEW-1) | T01: 628 K at TARGET components, 489 K today; T01 calls driver kg/W fragile | **REAL in kind, smaller than hoped**; 800 K withdrawn |
| **K3 nozzle** | η 0.86, plume strike ÷2, recovery 0.98 | T03: η_T 0.791 is the ideal-model ceiling and needs closure coils; plume strike 0.06-0.07 (3× the Atlas); recovery extraction 0.13 % of fusion; clocked sectors give no useful shear; helices trade collimation | **HOPEFUL**; 0.86 and plume ÷2 **WITHDRAWN**; recovery **NEGLIGIBLE** |
| **K4 compression** | 6,000 g/cm³, half-mass armour | inconsistent with T04's bound | **WITHDRAWN** (armour step real, -2 %) |
| **K5 structure** | 3 GPa laminate (T06-NEW-2) | not touched by the threads | **REAL but small** (-3 % per step) |
| **Protection** (new) | engine skirt, LiH shoes (T02) | +250 t mass, +0.0127 solid angle; residual events 540 (3.4-17,300); loop neutron fluence 3-62× REBCO tolerance; plume clearing and deflection fail | **NOT CONVERGED** (D-06) |

The prompt's example chain (*better ignition → less fusion power → less recirculating power → …*) holds in sign but runs in the wrong
order. At fixed exhaust velocity and acceleration, gain lowers the recirculating power (driver loss and driver mass); fusion power then
falls only because the lighter ship needs less thrust. Booking it the other way would credit the same saving twice.

## 5. Combined against summed: no super-additive synergy

On V1c (single-lever sensitivity chains, kept for their structure): K1 combined 8,204 t against a product of single ratios of 6,188 t
(+32.6 %), K2 9,904 against 9,106 (+8.8 %), K3 10,410 against 10,190 (+2.2 %), K5 11,810 against 11,820 (-0.1 %). Every combination
saves less than its single effects multiplied, and far less than their sum (the sum is what double counting would claim). The reason is
a floor the drive cannot shrink: on V4 with every specific mass at 1e-4 the ship still departs at **5,665 t** (payload 1,240,
propellant 3,580, tanks 336, shield 346, drive 366). Only a higher ve or a lighter payload moves it.

Convergence still matters more than these ratios suggest, because it acts on **closure**: at coupling 0.2 the Atlas engineering package
never closes, and the T06 package does (362 kt). At coupling 0.5 the package is the difference between 368 kt and 38 kt.

## 6. Steepest parameters

Elasticities at V1c (d ln m / d ln x, ±10 %): nozzle efficiency **-2.87**, warm temperature **-1.74**, driver efficiency -0.74, gain -0.63,
driver mass +0.37, warm areal mass +0.34, density -0.34 (at fixed gain, which the bound rules out), house load +0.17; everything else
below 0.1. **Recovery efficiency is -0.04**: 0.90 to 0.98 is worth 0.4 %, consistent with T03's 0.13 % extraction.

Negative results kept: on V1c, gain 1,500 ×2.65, nozzle 0.72 ×1.38, warm 600 K ×1.53, house 0.1 % ×1.20. **The nozzle cliff near 0.53
is the exhaust-velocity gate** η_jet × b ≥ ve²/(2ε) = 0.524 (F-T06-1); no mass or thermal improvement moves it. On V3 the cliff rises to
0.607 because V3's heat budget is tighter.

## 7. Mission ambitions

| Ambition | V3 (0.5) | V3o (driver 0.45) | V4 (ideal) | V4o | Verdict |
| --- | --- | --- | --- | --- | --- |
| Departure t | 37,895 | 24,143 | 17,907 | 14,314 | |
| Four 0.016 c burns | closes | closes | closes | closes | **MET** at TARGET values |
| LOCKED 6.0 y round trip | above 0.0073 g: 43,266 t | 25,667 t | 19,154 t | 14,921 t | **MET ONLY ABOVE 0.0073 g**; 0.0069 g gives 6.35 y |
| Ceiling acceleration | 0.0098 g | 0.0132 g | 0.0125 g | 0.0160 g | |
| 1 g | 102× short | 76× short | 80× short | 63× short | **NOT MET** |
| 1.5 g | | | no solution | | **NOT MET** |

- **6.0 years is kinematic**: the minimum round trip is 6.35 y at 0.0069 g everywhere; the lock costs 4-14 % more mass and an owner
  choice of departure acceleration, not a technology (F-T06-3).
- **1 g** on V4 needs every drive, power, radiator, nozzle and light-structure specific mass to fall **5,084-fold** together (30 kt,
  3,605 TW fusion). 1.5 g does not close at all (F-T06-8). T06 proposes no breakthrough of that size. The canon First Ignition ramp
  (0 to 1.5 g) stays inconsistent with every Vertex ship; that conflict is already open on the canon side.

## 8. What IGNITION would have to declare

| Breakthrough | Why it cannot be derived | Without it | Decision |
| --- | --- | --- | --- |
| **Compression coupling η_c/α ≥ 0.5** for D-³He (gain about 1,170 at 2,000 g/cm³) | demonstrated gain 4.1 (D-T); D-³He never ignited; couplings today are per-cent | 110 kt at 0.3, 362 kt at 0.2 | D-T06-1 = D-T04-1 |
| **Closure-coil pulsed nozzle at its ideal model**, η_T 0.79 at 15 E_p | literature η_mom 0.55-0.80 → η_T 0.30-0.64; 0.791 is T03's ideal upper bound | 58 kt at 10 E_p; ≥110 kt at literature 0.64 | D-T06-2 = D-T03-2 |
| **Engine-first dust survival** at 0.016 c | no shield physics above about 15 km/s; T02's clearing and deflection fail | no ship, at any mass | D-06 (T02 D-T02-1..4) |
| Anything for 1 g | 5,084-fold specific-mass gap | | not proposed |

Fiji is not on this list. Canon defines it as a premise (×30 amplification of a slow seed field, flux stabilisation), not a missing
breakthrough; T06 credits it with nothing numeric and adds no property (D-07).
