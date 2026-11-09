# T06 early findings: convergence and futures

| | |
| --- | --- |
| Thread | T06, technology convergence and IGNITION technology history |
| Date | 2026-11-09 |
| Base | `8de3ffa` on `claude/project-thread-pv2pie` |
| Status | EARLY / GATHERING. The final synthesis waits for the T01-T04 handoffs |
| Inputs | Atlas at 8de3ffa; T01 EARLY `57fe625`; T04 EARLY `1b85941`; T02 and T03 had nothing published yet |

Research only, not canon. Every number comes from `futures.py` (FDP-1 solves through `convergence.py`, read-only) and is listed in
`results/CHAINS.md`. Rerun the whole set with `python3 lab/variants/vertex-drive/studies/futures/futures.py` (about 6-7 min on 4 cores),
then `deps.py`.

## For every thread

1. **Gain and compression are one lever (from T04's bound).** Under G ≤ 1,787 × η_c/α × (ρ/3,000 g/cm³)^(-2/3), the Atlas V0-V2
   (3,000 g/cm³ at gain 3,000) need η_c/α = 1.68, which is impossible. Treat every Atlas mass as conditional. With gain held at its
   bound, the lightest ships at coupling 0.3 are:
   - **161 kt** with the Atlas V1 package at driver efficiency 0.30;
   - **10.3 kt** with the full T06 engineering package;
   - **12.4 kt** with T01 EARLY thermal numbers.

   At coupling 0.2 the Atlas package does not close at all. The quantity to declare is the coupling, not the gain.
2. **The engineering package decides closure, not just size.** In mass the levers combine sub-multiplicatively: no chain is
   super-additive, because payload, propellant and tanks form a floor of 4,228 t at ve 19,201 km/s. Under the bound, though, the same
   levers together turn "no ship" into a ship.
3. **The nozzle-efficiency cliff near 0.53 is the exhaust-velocity gate** η_jet·b ≥ ve²/(2ε) = 0.524, not mass. No other lever moves it.
4. **Elasticities at V1c:** nozzle efficiency -2.87, warm temperature -1.74, driver efficiency -0.74, gain -0.63, driver mass +0.37,
   warm areal mass +0.34. **Recovery efficiency is -0.04** (0.90 to 0.98 is worth 0.4 %).
5. **The 6.0 y lock is kinematic.** The minimum round trip is 6.35 y at 0.0069 g everywhere. The lock is met above 0.0073 g in every
   closing case, at 4-16 % more mass. **1 g is not met**: every specific mass would have to fall about 64-fold. 1.5 g found no
   solution.

## Proposed generations (generations_proposal.toml; gain at the bound)

| Gen | Coupling η_c/α | ρ g/cm³ | Gain | Nozzle | Departure t | At driver 0.30 | Loop 3 r m | Rate Hz | Wing tip m |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| V3 | 0.3 | 2,000 | 702 | 0.79 | 12,655 | 21,069 | 169 | 57 | 1,006 |
| V4 | 0.5 | 3,000 | 894 | 0.86 (declared) | 8,295 | 10,757 | 86 | 169 | 473 |

## For T05 (physical manifestation)

- The consistent ships have **larger, slower pulses** than FDP-1: V3 carries 44 t TNT at 57 Hz with a 65 m stand-off and loops at
  r 56 / 97 / 169 m. Do not draw the half-size nozzle from T06's first-draft chain K4; it has been withdrawn.
- V4 is close to the FDP-1 size: loops at r 28.5 / 49.4 / 85.6 m and wings to 473 m (1,071 m at driver efficiency 0.30).

## Questions

- **T04:** Is the ρ^(-2/3) scaling of your bound right at fixed b = 0.672? Do magnetisation, shock or fast ignition change α? What is a
  credible η_c/α band for heavy-ion direct drive? T06 uses 0.1-1.0 and proposes 0.3 (V3) and 0.5 (V4).
- **T01:** At 1,500-2,000 g/cm³ (44-78 t TNT pulses, 27-94 Hz), what are the house load, the launcher speed and the warm-loop
  equivalent temperature? Should the 628 K equivalent be the planning value for all generations?
- **T03:** Is a joint nozzle and recovery ledger possible? Is 0.79 defensible for 44 t TNT pulses at a 65 m stand-off?
- **T02:** What is the protection mass for loops at r 128-171 m in both orientations, and does V4's r 86 m change anything?
