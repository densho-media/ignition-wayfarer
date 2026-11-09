# T06 convergence analysis

Status: **GATHERING draft**, 2026-11-09. Inputs: the Atlas, T06's own FDP-1 solves, and the EARLY findings of T01
(`claude/project-thread-93sqqi` 57fe625) and T04 (`claude/project-thread-9hxayw` 1b85941). T02 and T03 had published nothing yet. The
final synthesis replaces this after the T01-T04 handoffs.

All tables come from `futures.py` (generated detail in `results/CHAINS.md`, data in `results/futures.json`). The FDP-1 calculator, the
four-burn engine and `convergence.py` are imported read-only. V0 through this adapter reproduces 20,760 t, and the energy ledger closes
in every combined solve. Every step value is a TARGET, never a result.

## 0. The headline: gain and compression are one lever, and the Atlas pair is not energy-consistent

T04 EARLY shows that compressing fuel to density ρ costs at least its Fermi-degenerate energy. Target gain is therefore bounded:
**G ≤ 1,787 × (η_c/α) × (ρ / 3,000 g/cm³)^(-2/3)**. Here η_c is the share of driver energy that ends up as fuel internal energy, and α is
the adiabat, so η_c/α ≤ 1 by definition. Present implosions are far below 1.

| Case | ρ g/cm³ | Gain | η_c/α needed | Energy-consistent |
| --- | --- | --- | --- | --- |
| Atlas V0, V1, V2 (FDP-1 optimistic tier) | 3,000 | 3,000 | 1.68 | **NO** |
| T06 chains K1-K5 and the grand endpoint (draft 1) | 3,000-6,000 | 3,000-6,000 | 1.68-5.33 | **NO** |
| T06 V3 proposal | 2,000 | 702 | 0.30 | yes |
| T06 V4 proposal | 3,000 | 894 | 0.50 | yes |

So the steepest-looking convergence step in T06's first draft (K4, denser compression, which halved every loop radius) is not available.
Denser fuel lowers the gain the driver can reach. The two numbers must be chosen together, and the quantity that IGNITION would have to
declare is the **compression coupling η_c/α**, not the gain. This changes D-T06-1 (registry_proposal.toml).

**Frontier**: the gain is set to its bound at each density, and the lightest closing ship is kept (results/CHAINS.md, "Frontier").

| Lever set | η_c/α 0.1 | 0.2 | 0.3 | 0.5 | 1.0 (ideal) |
| --- | --- | --- | --- | --- | --- |
| V1c (Atlas V1 at driver 0.30) | none closes | none closes | 160.8 kt (500 g/cm³) | 50.3 kt (1,000) | 18.9 kt (2,000) |
| All T06 engineering levers, Atlas thermal | 30.5 kt (1,000) | 13.3 kt (1,500) | 10.3 kt (2,000) | 8.3 kt (3,000) | 7.0 kt (3,000) |
| The same, with T01 EARLY thermal (628 K equivalent, house 0.005 %) | 51.8 kt (500) | 18.3 kt (1,500) | 12.4 kt (1,500) | 9.3 kt (2,000) | 7.4 kt (3,000) |

What this means:

- On its own, the Atlas V1 engineering package does not survive the bound at a believable coupling. Only the full T06 engineering
  package does, and then only at η_c/α of about 0.2 or more.
- **Engineering convergence now earns more than it did.** With the bound in force, the thermal, driver and structure levers decide
  whether a ship exists at all (V1c at 0.3: 161 kt; the full package at 0.3: 10.3 kt). Before the bound they only made a closing ship
  smaller. This is the one place the analysis finds a real convergence effect: the improvements do not multiply, but together they
  move the ship across the closure boundary.
- The convergent ship is not small and dense. At η_c/α 0.3 the lightest density is 1,500-2,000 g/cm³, with 44 t TNT pulses at
  57-93 Hz and the outer loop at r 128-171 m. That is larger than FDP-1, not half its size.

## 1. What is real, what is hopeful

These are the single-lever chains on V1c (12,978 t). They keep the Atlas gain and density, so they show sensitivity only (section 0).

| Chain | Mechanism | Link status | Alone on V1c | Combined | Verdict |
| --- | --- | --- | --- | --- | --- |
| **K1 recirculating power** | gain ×2 (VTX-01A), driver 0.30→0.45 and half its mass (VTX-01B), house ÷2 (VTX-01C) | modelled | -24 %, -20 %, -15 %, -8 % | 8,204 t (-37 %) | the driver steps are real; the gain step is excluded by the bound |
| **K2 thermal** | 800 K warm loop (VTX-07A), liquid-sheet warm radiators (VTX-07B), thin hot heat pipes (T06-NEW-1) | modelled | -14 %, -15 %, -4 % | 9,904 t (-24 %) | real mechanism, but T01 EARLY finds the split loop is 628 K, not 800 K |
| **K3 nozzle** | nozzle 0.86 (VTX-03), plume strike ÷2 (VTX-03B), recovery 0.98 (VTX-02C) | unmodelled / speculative / modelled | -18 %, -5 %, -0.1 % | 10,410 t (-20 %) | hopeful; the sign of the helical effect is unresolved (D-09); an upper bound, because the ledger is shared |
| **K4 compression** | 6,000 g/cm³ (VTX-01A), half-mass armour (VTX-06B) | modelled, but **inconsistent** | -14 %, -2 % | 10,971 t | **withdrawn**: 6,000 g/cm³ at gain 3,000 needs η_c/α 2.66 |
| **K5 structure** | 3 GPa laminate for hoops, spars and trusses (T06-NEW-2) | modelled | -3 % each | 11,810 t (-9 %) | real but small |

The prompt's example chain (*better ignition → less fusion power → less recirculating power → smaller thermal system → lower dry mass →
lower propulsion demand*) holds in sign but is in the wrong order. At fixed exhaust velocity and acceleration, gain does not lower the
fusion power that a given thrust needs. It lowers the recirculating power (driver loss and driver mass). Fusion power then falls only
because the lighter ship needs less thrust (K1: 10.8 to 6.8 TW). Booking it the other way round would credit the same saving twice.

## 2. Combined against summed: no super-additive synergy in mass

| Chain | Combined t | Additive expectation t | Multiplicative expectation t | Interaction vs product |
| --- | --- | --- | --- | --- |
| K1 | 8,204 | 4,313 | 6,188 | +32.6 % |
| K2 | 9,904 | 8,694 | 9,106 | +8.8 % |
| K3 | 10,410 | 10,083 | 10,190 | +2.2 % |
| K5 | 11,810 | 11,784 | 11,820 | -0.1 % |

Each combination saves less than its single effects multiplied together, and much less than their sum. The additive column is what double
counting would claim: 4,313 t for K1. The cause is a floor that the drive cannot shrink: payload 990 t, plus propellant at the rocket
equation's four-burn mass ratio of 2.72 at 19,201 km/s, plus its tanks. With every specific mass at 1e-4 of today's value, the ship
still departs at **4,228 t** (payload 990, propellant 2,671, tanks 251, shield 206, drive 209). That is the convergence floor at the
mission exhaust velocity. Only a higher ve or a lighter payload moves it.

## 3. Steepest parameters

Elasticity of departure mass at V1c (d ln m / d ln x, from ±10 % solves):

| Parameter | Elasticity |
| --- | --- |
| Nozzle efficiency | **-2.87** |
| Warm-loop temperature | **-1.74** |
| Driver efficiency | -0.74 |
| Gain | -0.63 |
| Driver mass | +0.37 |
| Warm areal mass | +0.34 |
| Compression | -0.34 (at fixed gain, which section 0 rules out) |
| House load | +0.17 |

Plume strike, hot areal mass, structure, armour and recovery are all below 0.1. **Recovery efficiency barely matters**: 0.90 to 0.98
moves the ship 0.4 %, because at high gain the recirculating power is about 0.1 % of fusion.

The downside is steeper than the upside, and these negative results are kept:

| Change on V1c | Departure t | Factor |
| --- | --- | --- |
| Gain 1,500 | 34,385 | ×2.65 |
| Nozzle efficiency 0.72 | 17,891 | ×1.38 |
| Warm loop 600 K | 19,865 | ×1.53 |
| House load 0.1 % | 15,585 | ×1.20 |

**The nozzle-efficiency cliff near 0.53 is the exhaust-velocity gate**, η_jet × b ≥ ve²/(2ε) = 0.524 (S-FIJI-V4), not the mass
feedback. No thermal or mass improvement moves it (F-T06-1).

## 4. Mission ambitions

| Ambition | V1c | V3 (η_c/α 0.3) | V3c | V4 (0.5 + nozzle) | V4c | Verdict |
| --- | --- | --- | --- | --- | --- | --- |
| Departure t | 12,978* | 12,655 | 21,069 | 8,295 | 10,757 | |
| Four 0.016 c burns | closes* | closes | closes | closes | closes | **MET** at TARGET values (*V1c only with the inconsistent gain 3,000) |
| LOCKED 6.0 y round trip | 0.0073 g | 0.0073 g (13,499 t) | 0.0073 g (24,510 t) | 0.0073 g (8,622 t) | 0.0073 g (11,517 t) | **MET ONLY ABOVE 0.0073 g** departure acceleration; 0.0069 g gives 6.35 y |
| 1 g | 81× short | 74× short | 102× short | 57× short | 77× short | **NOT MET** |
| 1.5 g | — | — | — | — | — | **NOT MET** (no closing solution found) |

- **6.0 years is a kinematic question, not a mass one.** The minimum round trip is 6.35 y at 0.0069 g in every case, because it depends
  on acceleration and ve only. Meeting the lock costs 4-16 % more mass and needs an owner choice of departure acceleration, not a new
  technology.
- **1 g needs a specific-mass breakthrough that no record provides.** Even on the first-draft grand endpoint, which is inconsistent in
  the optimistic direction, every drive, power, radiator, nozzle and light-structure specific mass must fall about **64-fold** together
  (40 kt, about 4,400 TW of fusion). 1.5 g found no closing solution. T06 does not propose a breakthrough of that size.
- The canon First Ignition ramp (0 to 1.5 g, BASELINE `[mission.first_ignition]`) is inconsistent with every Vertex ship. That conflict
  is already open on the canon side; T06 records it and does not resolve it.

## 5. Which breakthroughs IGNITION would have to declare

| Breakthrough | Why it cannot be derived | Decision |
| --- | --- | --- |
| D-³He ignition with compression coupling η_c/α of about 0.3-0.5 (gain about 700-900 at 2,000-3,000 g/cm³) | demonstrated gain 4.1 (D-T); D-³He has never ignited; present couplings are far lower | D-T06-1 |
| A pulsed magnetic nozzle at 0.79-0.86 | theory gives 0.79-0.86 (unverified source); simulations give 0.34-0.70 | D-T06-2 (after T03 and D-09) |
| Survival of engine-first braking through dust at 0.016 c | no shield physics validated above about 15 km/s | D-06 (T02 leads) |
| Anything for 1 g | a 64-fold specific-mass gap | not proposed |

Fiji is not on this list. Canon defines it as a premise, not a missing breakthrough, and T06 adds no property to it (D-07).

## 6. Open for the final synthesis

- **T04:** confirm the bound and its ρ^(-2/3) scaling. Say whether magnetisation, shock or fast ignition change α or the coupling
  (T04 EARLY says magnetisation removes the hot-spot requirement but not the compression ceiling), and give a credible η_c/α band
  for heavy-ion direct drive.
- **T01:** sourced driver and house numbers at 1,500-2,000 g/cm³ (larger, slower pulses: about 44 t TNT at 57-94 Hz in V3), and the
  launcher speed T01 and T04 both flag.
- **T03:** the joint nozzle and recovery ledger, and whether 0.79 is defensible for 44 t TNT pulses.
- **T02:** protection mass and orientation constraints for loops at r 128-171 m.
- Check every cross-thread chain for energy booked twice (especially VTX-02C recovery between T01 and T03).
- Re-run `futures.py` against any calculator change that T00 integrates.
