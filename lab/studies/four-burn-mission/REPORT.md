# Wayfarer four-burn mission: propulsion and fuel study

Owner brief 2026-11-03 13:14Z. Research only. Canon, `data/`, generators, tank geometry, the locked Fiji Drive specs and the
Blender files are unchanged. Every number below comes from `python3 lab/studies/four-burn-mission/run.py`. Inputs are in
`scenarios/v1.toml`, each marked CANON, RESEARCH, ASSUMPTION, PROTOTYPE or FICTION. The full tables are in `results/MATRICES.md`,
the machine-readable output is in `results/results.json`, and the figures are in `figures/`.

## Summary

- **The round trip closes, but only with a pulsed D-³He drive and only far below 1 g.** No physical drive in this model reaches
  1 g. The gap is a factor of about 100 in drive-plus-radiator mass per watt in the speculative tier and about 3,500 in the credible
  tier (figure F).
- **Best-supported direction: a pulsed D-³He drive** (IFD-P/IFD-PH): fuel pellets burned aft of the ship, one Fiji-amplified
  magnetic nozzle, the open aft geometry the owner accepted in v4.
  - Speculative engineering tier (target gain 3,000): departure 9.7 kt, 0.007 to 0.019 g, four burns of 726, 566, 441 and 343 days
    (5.7 years under thrust).
  - Credible extrapolation tier (gain 300): departure 30 kt, 0.0001 g, 325 years under thrust.
- **Continuous direct-fusion drives fail.** At central assumptions an open-cage core reaches an exhaust velocity of only 10,130 km/s.
  That is below the roughly 11,000 km/s at which the tank and drive mass feedback makes the four-burn mass diverge.
- **Optimistic continuous drives close at 0.0003 to 0.0009 g,** which means 64 to 144 years under thrust. That is far worse than
  pulsed.
- **Hydrogen reaction mass drops out.** At the optimum the exhaust is the unburned and fused fuel itself. Adding hydrogen lowers the
  exhaust velocity, and that costs more tank and propellant mass than it saves in power.
- **Helium-3 demand rises 3.4 to 12 times over canon:** 3,690 t at 9.7 kt, or 13,400 t at 30 kt, against 1,094 t today.
  The canon split depends on 80 % burnup and 95 % recovery, and no mechanism supports those numbers.
- **The existing 13-vessel farm is too small for every physical configuration.** He-3 and D need about 3.1 to 3.3 times their present
  volume, and the hydrogen vessels go unused. The farm needs a complete storage redesign.
- **The canon working point (261 TW, 1 g) is not physical.** It needs a jet efficiency of 0.80, but the charged-particle share of
  100 keV 1:1 D-³He is 0.737, which is the upper bound for a magnetic nozzle. It also assumes only 4 × 10⁻⁵ of the fusion power is
  absorbed, against the 0.26 neutral share.

## 1. What is new, what is canon, what is proposed

| Kind | Items |
|---|---|
| **Existing canon, reproduced** | 4,426 → 1,629 t four-burn ledger at ve 19,201 km/s; tank capacities 20,271 / 4,886 / 15,022 m³; tankage 458 t |
| **New findings (this study)** | canon He-3 understated by about 14 t because lost unburned D and He-3 are booked as hydrogen; the "147 t short" text is stale (section 2); as-built tanks are 38 t over the 0.15 × propellant law; the 1 g working point breaks the energy partition; tank feedback diverges below about 11,000 km/s; continuous D-³He cannot reach the mission's exhaust velocity at credible confinement; pulsed drives close; hydrogen is not needed at the optimum; He-3 demand is 3,700 to 13,400 t |
| **Proposed future changes (owner decision, nothing applied)** | choose the design tier and the story timescale; switch the drive to pulsed D-³He with one nozzle; drop the hydrogen inventory; redesign the tank farm for about 3.3 times the He-3/D volume; grow the ship to about 10 kt (speculative) or 30 kt (credible); size the radiators at about 1 kt |
| **Fiji lattice** | used only as canon allows: field amplification and stabilisation (continuous confinement up to 20 T, nozzle loop fields). No new properties proposed. |

## 2. Reconciliation with the operating point and the tank documents

- **Ledger.** The model reproduces canon exactly: departure 4,426 t, end mass 1,629 t, propellant 2,797 t
  (`results/MATRICES.md`, "Canon audit").
- **Species.** He-3 / D / H come out at 1,108 / 740 / 949 t here, against canon's 1,094 / 731 / 972 t. Canon books the 23 t of lost
  unburned D and He-3 feed as hydrogen. The total is right, but the He-3 and D tanks are understated by about 14 t and 9 t.
- **The 147 t shortfall** belongs to the pass-5 one-way ship. Braking from cruise at its 1,480 t burnout mass needed 327 t against a
  180 t reserve, a 147 t gap. Pass 7 replaced that ship with one carrying four-burn propellant, so the gap is closed.
  - The text "return braking short by 147 t (S&E 69)" in `data/wayfarer_3d.toml` `[fuel_storage].open` is stale. I have not edited
    it, because this study changes no canon.
- **Tank law.** The operating point books 419 t of tanks (0.15 × propellant); the as-built farm is 458 t. Closing the four burns with
  the as-built mass needs 66 t more propellant, for a departure mass of 4,530 t.
- **Fit.** Both the canon split and the as-built closure fit the existing vessels: He-3 at 94.9 % and 98.3 % of capacity, D at 88 %
  and 91 %, H at 94 %. This holds only if canon's efficiencies hold, and they do not (section 5).

## 3. Kinematics (Matrix A, figure A)

- **Reaching 0.016 c** takes 5.66 days at 1 g. Distance covered is 7.84 AU per burn.
- **Four burns** at 1 g total 22.6 days. At 0.01 g they total 6.2 years; at 0.001 g, 62 years.
- **Minimum destination distance** for a stop is two burn distances: 15.7 AU at 1 g, 1,569 AU at 0.01 g.
- **Relativity.** The relativistic correction is 1.3 × 10⁻⁴ (γ = 1.000128), so Newtonian kinematics are sufficient. The code keeps
  the relativistic form.
- **Constant thrust versus constant acceleration.** At constant thrust the acceleration rises as mass drops. The run is throttled at
  1.5 g. At 1 g departure the first burn takes 5.0 days against 5.66 days at constant 1 g.
- **Burn time is not journey time.** Coast time depends on the destination distance, which stays a free variable.

## 4. Rocket equation (Matrix B, figure B)

- **Total Δv** is 4 × 0.016 c = 19,187 km/s.
- **Mass ratio.** With the end mass fixed at 1,629 t, the four-burn mass ratio is 2.72 at the canon 19,201 km/s, 3.59 at
  15,000 km/s, 6.81 at 10,000 km/s and 599 at 3,000 km/s.
- **Tank feedback.** Tanks at 11.4 kg per m³ add a loop gain of k(R⁴ − 1).
  - Tanks alone reach a loop gain of 1 near 9,500 km/s. Below that there is no solution at any size.
  - At 10,000 km/s a 1,629 t ship already departs at 86.6 kt.
  - Once drive and radiator mass are added, the practical floor is about 11,000 km/s. The IFD-C central loop gain is 1.15 to 1.5 at
    9,000 to 10,000 km/s.
- **Exhaust velocity versus energy.** Higher exhaust velocity needs more energy per kilogram: ½ve² is 184 TJ/kg at 19,201 km/s.
  D-³He holds 352 TJ/kg if fully fused. The upper limit is ve_max = √(2 η ε x), where x is the fused share of the exhaust.
  This is the link between Matrix B and the drive physics.

## 5. Fusion fuel versus reaction mass, and the energy budget (Matrix C, figure D)

- **Energy partition.** Plasma at 100 keV with 1:1 molar D-³He (canon's 0.600 He-3 mass share) loses 0.230 of fusion power to
  bremsstrahlung and 0.033 to neutrons, counting D-D tritium burned in place. That leaves 0.737 as charged particles.
  This agrees with the v4 figures (0.237 and 0.010) within the difference in tritium-burn assumption.
  - He-3-rich mixes are worse: 2:1 gives 0.30 to 0.37 bremsstrahlung.
  - Lean mixes (0.25:1) cut bremsstrahlung but triple the neutron share.
  - **1:1 stays the best compromise** (fuel-ratio table in MATRICES.md).
- **Burn fraction.**
  - Continuous: b = τp / (τp + τ_burn). At the central τp of 3 s this gives b = 0.26 and ve_max = 10,130 km/s.
  - Pulsed: b = ρR / (ρR + H_B), with H_B ≈ 44 g/cm² for D-³He at 100 keV, calibrated on 7 g/cm² for DT. The optimistic design
    burns 0.67 of its fuel at ρR 90 g/cm²; the central design burns 0.45 at 36 g/cm².
  - No 80 % burnup and no 95 % recovery are assumed. Unburned fuel leaves in the exhaust and counts as reaction mass.
- **Ledger per architecture, for the four burns.** Fusion-fuel feed is D plus He-3; "lost unburned" means it leaves as exhaust.

  | Design | Feed (t) | Fused (t) | Lost unburned (t) | H added (t) | Expelled (t) | ve (km/s) |
  |---|---|---|---|---|---|---|
  | IFD-PH optimistic, 10 kt | 6,149 | 4,130 | 2,019 | 0 | 6,149 | 19,201 |
  | IFD-PH central, 30 kt | 22,369 | 10,099 | 12,270 | 0 | 22,369 | 14,000 |
  | IFD-CH optimistic, 10 kt | 5,720 | 5,250 | 470 | 259 | 5,979 | 21,000 |
  | CANON 1 g (unsupported) | 3,736 | 3,690 | 46 | 1,919 | 5,655 | 19,201 |

- **Mass defect.** Fused mass converts into product kinetic energy; the bookkeeping counts it inside "expelled". Every closure
  asserts momentum (rocket equation), mass (the burn sum equals propellant drawn, the ledger ends at the end mass) and energy
  (each ledger sums to 1 of fusion power).
- **Where the power goes** (10 TW design point; figure D):
  - Continuous central: 0.57 directed jet, 0.28 plume and radiation to space, 0.15 hot-loop heat.
  - Pulsed central: 0.61 to 0.63 jet, about 0.36 to space, 0.017 heat (hot plus driver).
  - Pulsed optimistic: 0.78 jet and 0.006 heat.
  - Exhaust energy is never booked as radiator heat. Radiation is booked onto hardware only by the solid angle that hardware subtends.
- **Driver power** recirculates: 1/(G·η_d) of fusion power, which is 0.011 at central and 0.0007 at optimistic. The driver's waste
  heat goes to warm radiators at 400 to 600 K.

## 6. Architectures (Matrix E, figures C and E)

| Name | What it is | Class |
|---|---|---|
| CANON | today's 250 t drive at 261 TW, η 0.80, 4 × 10⁻⁵ absorbed | unsupported (breaks the partition) |
| IFD-C | v3/v4 open-cage continuous D-³He core, Fiji fields to 20 T, W armour on Li heat pipes, one nozzle | credible extrapolation at central; τp above 1 s needs Fiji stabilisation |
| IFD-CH | IFD-C with flowing Li armour (30 to 50 MW/m²) and a liquid wall | highly speculative engineering |
| IFD-P | v4 pulsed D-³He pellets, stand-off heavy-ion driver, Fiji-amplified magnetic nozzle loops | highly speculative engineering (D-³He ignition) |
| IFD-PH | IFD-P with an optional hydrogen tamper and a free pulse rate | highly speculative engineering |

Closures at a 10 kt departure-mass cap (860 t payload):

| Design | ve (km/s) | Fusion (TW) | a0 (g) | Burn time (y) | Drive / radiators / tanks (t) |
|---|---|---|---|---|---|
| IFD-PH optimistic | 19,201 | 8.1 | 0.0069 | 5.7 | 901 / 999 / 577 |
| IFD-P optimistic | 19,201 | 8.4 | 0.0072 | 5.6 | 931 / 1,041 / 592 |
| IFD-CH optimistic | 21,000 | 0.91 | 0.00063 | 64 | 1,791 / 550 / 564 |
| IFD-C optimistic | 21,000 | 0.41 | 0.00028 | 144 | 2,087 / 244 / 561 |
| any drive, central tier | — | — | — | no closure under 14 kt | — |

At a 30 kt cap the central tier closes for pulsed drives: IFD-PH at 325 years, IFD-P at 278 years.

- **Continuous drives are mass-bound.** The wall-flux limit forces about 300 m of core per 0.2 TW (IFD-CH: 4 cores × 306 m at
  0.91 TW). Armour and coil mass come to 3.5 to 8 × 10⁻⁶ kg per W of jet power.
- **Pulsed drives keep the hardware away from the burn.**
  - The nozzle stands 43 m (optimistic) to 101 m (central) from the burn point.
  - The loops intercept only a small solid angle.
  - The fuel's own ρR absorbs most X-rays: 1.2 % escape at optimistic, 4 % at central.
- **The hydrogen tamper is not used at the optimum.** The search picked a tamper ratio of about 10⁻⁹ every time, so IFD-PH equals
  IFD-P. Tamper-captured X-rays would matter only if the dense-plasma bremsstrahlung were much higher than modelled.
- **Highest departure acceleration that closes, as the ship grows without limit:**

  | Drive | Highest a0 (g) | At ve (km/s) |
  |---|---|---|
  | IFD-P optimistic | 0.012 | 23,000 |
  | IFD-PH optimistic | 0.010 | 18,000 |
  | IFD-CH optimistic | 0.00086 | 21,000 |
  | IFD-P central | 0.00029 | 21,000 |
  | IFD-PH central | 0.00019 | 15,000 |
  | CANON (unsupported) | 1.5 | 18,000 |

## 7. Sustaining 1 g (figure F)

- **Required specific mass.** To hold 1 g at ve 16,000 to 19,200 km/s, drive plus radiators must weigh 2.0 to 3.0 × 10⁻⁹ kg per W
  of jet power, and that is with zero payload.

  | Drive | Specific mass (kg/W of jet) | Gap to 1 g |
  |---|---|---|
  | Canon allowance | 1.55 × 10⁻⁹ | meets it, which is why canon closes at 1 g |
  | IFD-P/IFD-PH optimistic | 2.7 × 10⁻⁷ | ×90 to ×100 |
  | IFD-P/IFD-PH central | 9.3 × 10⁻⁶ | ×3,500 |
  | IFD-CH optimistic | 3.5 × 10⁻⁶ | ×1,200 |
  | IFD-C optimistic | 7.9 × 10⁻⁶ | ×2,600 |

- **Power at 1 g:**
  - Today's 4,426 t departure needs 417 TW of jet power, 650 to 730 TW of fusion, and 11 to 110 TW of heat (Matrix C).
  - The 9.7 kt optimistic ship would need 1,430 TW of fusion.
- **Dominant barriers**, in order (sensitivity, figure H):
  1. target gain;
  2. driver mass and waste heat (the warm radiators);
  3. nozzle efficiency and mass;
  4. compressed fuel density (ρR);
  5. tank mass per m³.

  Radiator temperature for the hot loop matters little; the warm driver-heat radiators matter a great deal.

## 8. Mass cases (brief section 5; MATRICES.md "Mass cases")

| Case | Departure (t) | End (t) | Propellant (t) | Burns 1 to 4 (days) | Thrust (MN) | Fusion (TW) |
|---|---|---|---|---|---|---|
| 1. Existing 1,629 t final, ve 19,201, flown at 1 g | 4,426 | 1,629 | 2,797 (978 / 762 / 594 / 462) | 5.0 / 4.0 / 3.8 / 3.8 | 43.4 | 417 jet; not physical |
| 2. Illustrative 1,000 t dry, ve 19,201, at 1 g | 2,716 | 1,000 | 1,716 | 5.0 / 4.0 / 3.8 / 3.8 | 26.6 | 256 jet; not physical |
| 3. Reduced (560 t payload), IFD-PH optimistic | 9,944 | 3,661 | 6,283 | 613 / 477 / 372 / 290 | 0.80 | 9.8 |
| 3b. Reduced, IFD-PH central (30 kt) | 29,998 | 6,857 | 23,141 | 55,618 / 38,457 / 26,591 / 18,386 | 0.025 | 0.27 |
| 4. Enlarged, IFD-PH optimistic (30 kt) | 29,877 | 10,999 | 18,878 | 512 / 399 / 311 / 242 | 2.86 | 35.3 |
| 5. Fully iterated, IFD-PH optimistic (10 kt) | 9,732 | 3,583 | 6,149 | 726 / 566 / 441 / 343 | 0.66 | 8.1 |
| 5b. Fully iterated, IFD-PH central (30 kt) | 29,985 | 7,616 | 22,369 | 46,161 / 32,770 / 23,264 / 16,515 | 0.031 | 0.35 |

- **Cases 1 and 2** fix the end mass, as the brief asks. Their tanks, at 0.15 × propellant (419 t and 257 t), sit inside that mass.
  Cases 3 to 5 iterate payload, drive, radiators, tanks and the 2 % reserve until the departure mass reproduces itself; each mass
  history is asserted to end at its end mass.
- **Why cutting payload barely helps.** Cutting payload from 860 t to 560 t shortens the optimistic burns by only 15 %, because the
  drive, radiators and tanks dominate the dry mass.

## 9. Radiation and heat (figures D and I; MATRICES.md "Crew dose")

**IFD-PH optimistic (10 kt, 8.1 TW):**

- Hot heat at 1,800 K is 34.5 GW over 0.032 km² of two-sided heat-pipe panels.
- Warm driver heat at 400 to 600 K is 11.4 GW over 0.86 km².
- Radiators total 999 t, against canon's 10.8 GW allocation.
- **The warm radiators are the size driver.** 0.86 km² is about a 930 m square, or a 30 m-wide blade 29 km long, which is far larger
  than the ship. The pessimistic warm-radiator tier alone stretches the mission to 75 years.

**IFD-PH central (30 kt, 0.35 TW):**

- Hot heat is 2.8 GW over 0.003 km²; warm heat is 3.0 GW over 0.48 km²; radiators total 1,228 t.

**Neutrons and crew dose:**

- The fuel's ρR stops almost all neutrons from the pulsed burn: 5.5 × 10⁻⁶ escape at optimistic, 1.2 × 10⁻³ at central.
- Even so, 45 to 430 MW of neutrons leave the burn point.
- At 150 m and unshielded, that is 1.6 × 10⁴ to 1.6 × 10⁵ Sv/h.
- Holding 20 mSv per year needs 10 to 13 decades of attenuation in the shadow shield. That is roughly 3 to 4 m of LiH-class
  material, a first-order estimate. The 100 t shield in the drive mass is a placeholder until a transport calculation sizes it.
- Continuous cores leak 14 to 31 GW of neutrons and need 15 decades.

## 10. Tanks (Matrix D, figure G)

| Configuration | He-3 / D / H (t) | Need / existing (He-3, D) | Outcome |
|---|---|---|---|
| IFD-PH optimistic, 10 kt | 3,687 / 2,462 / 0 | 3.3× / 3.1× | complete storage redesign |
| IFD-P optimistic, 10 kt | 3,783 / 2,526 / 0 | 3.4× / 3.2× | complete storage redesign |
| IFD-CH optimistic, 10 kt | 3,429 / 2,290 / 259 | 3.1× / 2.9× | complete storage redesign |
| IFD-C optimistic, 10 kt | 3,472 / 2,319 / 169 | 3.1× / 2.9× | additional tanks |
| IFD-PH central, 30 kt | 13,412 / 8,957 / 0 | 12× / 11× | complete storage redesign |
| CANON at 1 g (unsupported) | 2,240 / 1,496 / 1,919 | 2.0× / 1.9× | additional tanks |

**For the 10 kt pulsed ship:**

- The farm needs about 82,000 m³, equal to 24 L-class vessels. At 11.4 kg/m³ it weighs 577 t.
- It occupies about 59 m of bay length, against 28.6 m today, at the existing 13-vessel cross-section.
- Cryocooling is 0.8 MW.
- The 15,022 m³ of hydrogen vessels are idle. Converting them to He-3 or D needs engineering changes (insulation, cooler lift,
  PMDs), so the model does not count them.
- The axial load at the brief's 1.5 g would be 103 MN, 4.4 times the Q45 collar limit. At the real 0.019 g peak it is about 1.3 MN.

Nothing in the existing tank geometry was changed.

## 11. Recommendation (the brief's 12 questions)

1. **Can Wayfarer do 0.016 c, unrefuelled, round trip?** Yes, with a pulsed D-³He drive. Every physical case closes only far below
   1 g. With credible extrapolation it takes centuries under thrust; with speculative engineering, about 5 years. Continuous
   D-³He does not close at credible assumptions.
2. **Minimum inventories.**
   - 10 kt optimistic: He-3 3,690 t, D 2,460 t, no hydrogen; 6,150 t of propellant including a 2 % reserve.
   - Smallest closure, 4.5 kt (20 years under thrust): He-3 1,705 t, 2,843 t of propellant.
   - Credible tier, 30 kt: He-3 13,400 t, D 9,000 t.
3. **Most credible exhaust velocity.** 14,000 to 15,000 km/s at the central tier (b about 0.45, gain 300). 19,200 km/s needs about
   ρR 90 g/cm² and gain 3,000.
4. **Can it sustain 1 g?** No. Every physical drive is 90 to 3,500 times too heavy per watt.
5. **Achievable acceleration.**
   - Optimistic pulsed: 0.007 g at departure, rising to 0.019 g; at most about 0.012 g at any ship size.
   - Central: about 10⁻⁴ g.
6. **Burn durations.**
   - Optimistic, 10 kt: 726, 566, 441 and 343 days.
   - Central, 30 kt: 126, 90, 64 and 45 years.
7. **Departure mass.** 9.7 kt optimistic (2.2 times today) or 30 kt central (6.8 times).
8. **Architecture.** Pulsed D-³He in the open aft geometry (IFD-P, with the tamper option of IFD-PH kept):
   - a stand-off driver and the burn point aft of the ship;
   - one Fiji-amplified magnetic nozzle at 43 to 100 m;
   - a 1,800 K hot loop plus large warm driver radiators;
   - a layered shadow shield.
9. **Cores and nozzles.** One burn point and one magnetic nozzle (three Fiji loops as in v4, with four trim sectors).
   - More chambers multiply driver and nozzle mass without lowering mass per watt.
   - The continuous alternative needs four cores of about 306 m.
10. **Tanks.** Redesign. The farm needs about 3.3 times the He-3 and D volume, the hydrogen vessels go, and the farm runs to about
    59 m.
11. **Radiators.** About 1,000 t:
    - 0.03 km² of hot panels for about 35 GW;
    - 0.86 km² of warm panels for about 11 GW of driver heat (optimistic);
    - central: 0.48 km² warm.
12. **Breakthroughs still required:**
    - D-³He ignition and burn in a compressed pellet at ρR 36 to 90 g/cm²;
    - target gain of 300 (central) to 3,000 (optimistic);
    - a driver of 0.3 to 0.45 efficiency at 0.05 to 0.2 kg/kW, firing 10 to 100 Hz for years;
    - a magnetic nozzle efficiency of 0.65 to 0.79, with Fiji loops surviving the X-ray and debris fluence;
    - thousands of tonnes of He-3;
    - light warm radiators.

    The Fiji lattice needs no new properties for this direction.

**Closest defensible alternative if centuries are unacceptable.** Keep the pulsed drive and accept 5 to 20 years under thrust. That
needs the speculative-tier gain (about 3,000) to hold.

**Remaining gap to the 1 g story.** About 100 times in drive specific mass, even then.

## 12. Unresolved physics and speculative assumptions

| Item | Status | Effect |
|---|---|---|
| D-³He ignition in an inertial or magneto-inertial pellet | not demonstrated; DT ignition only (NIF, 2022 to 2025) | everything pulsed |
| Target gain 300 to 3,000 | extrapolation; NIF gain about 4 (DT) | strongest lever: optimistic gain swings burn time from 325 y to 54 y; pessimistic from 5.7 y to 120 y |
| ρR 36 to 90 g/cm² for D-³He | beyond any compression demonstrated | sets burn fraction and ve |
| H_B burn parameter about 44 g/cm² | calibrated scaling, not a burn simulation | burn fraction |
| Dense-plasma bremsstrahlung share 0.25 to 0.45 | estimate | X-ray load |
| Driver efficiency and mass (heavy ion, 0.15 to 0.45, 0.05 to 1 kg/kW) | projected | warm radiators |
| Magnetic nozzle efficiency 0.5 to 0.79 for pulsed plasma | modelled, not flown | ve and heat |
| Loop survival at 4 × 10⁴ J/m² per pulse at 100 Hz | unknown | stand-off and mass |
| Continuous confinement τp of 3 to 30 s for D-³He at 100 keV | needs Fiji stabilisation (fiction, canon) | the continuous ve ceiling |
| Wall flux 10 to 50 MW/m² (W on Li heat pipes, flowing Li) | above today's 10 MW/m² designs | continuous core size |
| Radiator areal mass (heat pipes, droplets, warm panels) | projected | radiator mass |
| Tank mass at 11.4 kg/m³ at 4 to 12 times the volume | scaled from the as-built farm | tank feedback |
| He-3 supply of 2 to 13 kt | outside the ship model | mission logistics |
| Shadow-shield mass (100 t placeholder), neutron transport | first-order | crew dose |
| Mission exclusions | gravity, capture, launch, landing and trajectory corrections are not modelled | Δv is exactly 4 × 0.016 c |

## Deliverables

| # | Deliverable | Where |
|---|---|---|
| 1 | Calculator | `fourburn/` (plasma, kinematics, rocket, architectures, thermal, tanks, closure, study), `run.py`, `scenarios/v1.toml`, 18 tests in `tests/test_fourburn.py` |
| 2 | Four-burn ledger | MATRICES.md "Canon audit", "Mass cases"; results.json `designs.*.burn_propellant_t` |
| 3 | Acceleration matrix | Matrix A, figure A |
| 4 | Exhaust-velocity matrix | Matrix B, figure B |
| 5 | Energy and radiation budget | Matrix C, section 5, figure D, crew-dose table |
| 6 | Iterated mass model | `fourburn/closure.py`, mass cases 3 to 5, figure E |
| 7 | Tank comparison | Matrix D, figure G |
| 8 | Continuous, pulsed and hybrid comparison | Matrix E, "Sustaining 1 g", figure F |
| 9 | Pareto analysis | MATRICES.md "Pareto fronts", figure C (no weighted score) |
| 10 | Recommendation | section 11; concept sketch, figure I |
| 11 | Unresolved physics | section 12 |

**Reproduce:** `python3 lab/studies/four-burn-mission/run.py --fresh`; the optimisation takes about 80 minutes. Without `--fresh` it
reuses `results/pareto.json`. Then run `python3 lab/studies/four-burn-mission/figures.py`. The tests run with
`python3 -m unittest discover -s lab/studies/four-burn-mission/tests`.

## Owner decisions (nothing applied)

1. **Design tier.** Choose between the speculative tier (about 10 kt, 5.7 years under thrust, gain 3,000) and the credible tier
   (30 kt, centuries). The story timescale follows from this choice.
2. **Drive.** Adopt pulsed D-³He with one nozzle as the Fiji Drive direction (this would change the locked specs, so only on
   approval).
3. **Inventory and tanks.** Drop the hydrogen inventory and redesign the tank farm for He-3 and D.
4. **Stale text.** Correct the stale 147 t text in `[fuel_storage].open`.
5. **He-3 sourcing.** Decide where thousands of tonnes of He-3 come from.

## Sources

The research sources are the v4 report's list (`/mnt/project-files/review/fiji_drive_v4_2026-11-03/REPORT.md`, "Sources"):

- **Experiments:** NIF FY2025; MagLIF PRL 125, 155002; General Fusion LM26.
- **Design studies:** FDR NIAC; the UAH and MSFC pulsed magnetic nozzle work; Daedalus and Icarus; DFD (Cohen 2019, Thomas 2017).
- **D-³He inertial burn:** OSTI 7107437.
- **Materials:** W under pulsed X-rays (OSTI 20849929); ARC/REBCO (arXiv 1409.3540); liquid-lithium PFCs (NSTX-U).
- **Plasma physics:** Bosch & Hale, Nucl. Fusion 32 (1992) 611; Rider, Phys. Plasmas 2 (1995) 1853.

The arXiv, OSTI and NTRS hosts are blocked from this cloud session, so those IDs are carried over from v4 without being re-fetched.
