# T01 report: thermal systems, electrical efficiency and mass

Research only. Nothing here changes the approved ship, `data/`, `src/`, production geometry, the Drive workbooks, FDP-1, the four-burn
engine or the Atlas registry. Every ship number is an FDP-1 calculator result (optimistic tier, four 0.016 c burns, FDP-1 a0 0.0069 g)
run through `split.py`; the generated tables are in `RESULTS.md` and the full record in `ledger.json`. Value labels follow
`planning/HANDOFF.md`.

## Summary

The Atlas halved the ship (V0 20,760 t to V1 10,416 t) mostly through two TARGETs: a 700-800 K warm loop and a house load of 0.05 % of
fusion. Booked component by component:

- **The house-load saving survives and is larger than assumed.** For fuel-only targets near 81 GJ yield, the target factory, injection,
  controls, cryoplants and radiator pumps come to 0.012-0.014 % of fusion with near-term parts and 0.003-0.005 % with advanced ones
  (about 10 MJ and 4-6 MJ per pellet, of which the factory process is 8 MJ and 0.3 MJ). On its own, at FDP-1's 600 K loop, that
  takes the ship from 18,643 t to 10,575 t (the Atlas 0.05 % gave 12,996 t).
- **The 700-800 K warm loop does not survive.** With every component at a TARGET temperature (cores 640 K, power stages 740 K,
  capacitors 550 K, dumps 1,000 K) the equivalent loop is 628 K, not 700 K. With near-term components (cores 470 K, SiC modules 500 K,
  capacitors 440 K) it is 489 K, and the ship does not close at any driver efficiency on 3 kg/m2 radiators.
- **The warm radiator's 1.0 kg/m2 is the real hinge, and it is a TARGET in every generation including V0.** No solid panel technology
  reaches it at 450-800 K (the heat-pipe working-fluid gap; halide and alkali panels are about 5-6 kg/m2). On those panels V1 is
  50,589 t, V2 19,998 t, and FDP-1 itself does not close at 2.5 kg/m2. Only a tin droplet sheet (VTX-07B) reaches about 0.6-1 kg/m2
  above 520 K.
- **Driver efficiency and driver mass now dominate.** Once the house is small, driver-proportional loss is 75-95 % of the warm heat. The
  closure is steep in driver mass per watt: V1 is 12.9 kt at 0.1 kg/kW and 25.1 kt at the calculator's own central 0.2 kg/kW; the
  advanced split ship at efficiency 0.30 does not close at 0.2 kg/kW.
- **Net:** split advanced = **9,702 t at driver efficiency 0.45, 12,654 t at 0.30, 15,473 t at 0.25** (Atlas V1: 10,416 / 12,978 /
  15,219 t). The house gain roughly pays for the lower temperature, so the V1 mass survives in size, for different reasons, and only on
  TARGET hardware: droplet radiators, 640 K cores, 740 K MW power stages.
- **New problem (shared with T04):** FDP-1 flies 12.5 targets at once, 3.7 m apart at 400 m/s; each next target is 3.7 m from an 81 GJ
  pulse and is destroyed. With one target in the open per period the launcher needs 4.7-7.5 km/s; 4 km/s costs +6.3 %, 2.5 km/s +17.5 %,
  1.5 km/s does not close.

Everything above is conditional on FDP-1's gain of 3,000. T04 reports (`studies/ignition/EARLY.md` §1) that this gain needs a
driver-to-fuel coupling of 1.68 and that a consistent gain gives V1 at 59-97 kt; T01 has not folded that in.

## 1. Method

`split.py` imports `convergence.py` read-only and calls `fdp1.solve('baseline', overrides)`, as the Atlas does. V0 reproduces 20,760 t.

The calculator has one warm radiator: one temperature, one areal mass, one transport mass per W. T01 books the warm heat by component,
gives each component a circuit (coolant temperature and radiator technology), and replaces the single radiator with the **equivalent
radiator** that has the same total planform area and the same total mass:

- area per circuit A_i = Q_i / (2 eps_i sigma T_i^4)
- T_eq from 2 x 0.9 x sigma x T_eq^4 = sum Q_i / sum A_i
- areal mass a_eq = sum A_i a_i / sum A_i
- transport t_eq = sum Q_i t_i / sum Q_i

The equivalent radiator (warm T, areal mass, transport) and the bottom-up house load go back into the calculator as overrides, and the
loop repeats until the shares stop moving (2-4 passes). The calculator's warm total equals the component total to below 1e-6 in every
case (`booking_error` in `ledger.json`), and every energy ledger sums to fusion power (`ledger_sum` = 1.000000000).

What the equivalent radiator cannot represent: the number of separate loops (pumps, manifolds, thermal breaks). These are carried as
transport mass per W and as pumping power (booked as house load), never removed. No override path outside the calculator's existing
inputs was needed; the injection-rate case uses the existing `max_rep_Hz` input.

Three component scenarios:

| Scenario | Meaning |
| --- | --- |
| Demonstrated | every part at its rated or demonstrated temperature (cores 420 K, SiC modules 420 K, capacitors 400 K) on Ti-water heat pipes at 3 kg/m2 |
| Conservative | near-term values: 250 C SiC modules (demonstrated continuously at module scale), cores 50 K above their rating, 200 C capacitors, dumps on potassium heat pipes; radiators by temperature band (3 / 5 / 6 kg/m2) |
| Advanced | TARGETs, each tied to a technology: HITPERM-class cores at 673 K, MW SiC/GaN at 773 K, mica/glass capacitors at 573 K, tin droplet sheets (0.6 kg/m2, emissivity 0.5) or 1.5 kg/m2 panels |

FDP-1's optimistic tier (1.0 kg/m2 at 600 K) stays as the comparison point.

## 2. Where the V0 to V1 saving comes from, and what survives

The Atlas V1 change list, applied one step at a time (Atlas single loop, efficiency 0.45):

| Step | Departure t | Change | Survives? |
| --- | --- | --- | --- |
| V0 | 20,760 | | |
| + galleries inside the 7.9 deg cone (VTX-06A) | 19,829 | -931 | yes, it is geometric, not thermal (routing inside the hull unchecked) |
| + idle H2 vessels removed (VTX-04B) | 18,643 | -1,186 | owner decision D-04 |
| + house 0.1 % to 0.05 % (VTX-07C) | 12,996 | -5,647 | **yes, larger**: the bottom-up house gives 10,575 t at this step (-8,068) |
| + warm loop 600 to 700 K (VTX-07A) = V1 | 10,416 | -2,580 | **no** as booked: the split TARGET loop is 628 K, the near-term one 489 K |
| T01 split advanced, efficiency 0.45 | 9,702 | | on TARGET components and droplet radiators |
| T01 split advanced, efficiency 0.30 | 12,654 | | planning value |

D-04 both ways (decision D-04 open): V1 11,083 t with the vessels (+667 t); split advanced at 0.30 13,463 t with them (+809 t, +6.4 %).

## 3. Research questions

### 3.1 Target-factory energy (Q1)

FDP-1 at V1: 0.343 g of fuel per target (0.206 g He-3, 0.137 g D), 18.3 mm diameter, about 81 GJ yield, 95-160 Hz depending on the
case. Per pellet:

| Item | Conservative | Advanced | Basis |
| --- | --- | --- | --- |
| Cold heat at about 1.5 K (fuel conditioning: D2 freezing about 7 J, He-3 subcooling about 1-2 J; plus a 10 kW cold-box leak shared over about 100 targets/s) | 100 J | 100 J | EXTRAPOLATION (property data; cold-box leak ASSUMPTION) |
| Cryoplant input for it | 1,000 W/W at 300 K, scaled by Carnot to 450 K: 0.15 MJ | 600 W/W at 300 K, scaled to 700 K: 0.14 MJ | PUBLISHED (LHC 1.8 K at about 0.15 of Carnot, about 1 kW/W; S-T01-CRYO); 600 W/W is a TARGET |
| Fabrication, layering, inspection, rejected product | 8 MJ | 0.3 MJ | 8 MJ is a ceiling: IFE factories cost about 0.17 USD per target in total, about 0.11 USD of it operation; if all operation were electricity at 0.05 USD/kWh it would buy about 7.6 MJ (S-T01-IFE-TARGET-COST). 0.3 MJ is a TARGET |
| Injection at the one-in-flight speed (4.7-7.5 km/s; 1.34 g with a recovered sabot) | 10 % launcher efficiency: 0.2-0.4 MJ | 30 %: 0.05-0.08 MJ | MODEL (kinetic energy) / ASSUMPTION (efficiency) |
| Magnetisation (VTX-01A) | 0.2 MJ (stand-off pulsed coil, field about 30 T over about 20 cm3 = 7 kJ, at 4 % efficiency) | 0 (seed field from the standing nozzle field) | EXTRAPOLATION |
| Controls, tracking, trim-sector supplies | 30 MW continuous (0.19-0.25 MJ per pellet) | 10 MW | ASSUMPTION |
| Nozzle-coil cryostat static leak (10 kW at 20-40 K) | 0.26 MJ per pellet equivalent | 0.26 MJ | EXTRAPOLATION (about 1 W/m2 on about 1e4 m2) |
| Radiator pumps | 1.5 % of the warm heat | 0.5 % | ASSUMPTION |

**Result.** Conservative about 10 MJ per pellet, or 0.012-0.014 % of fusion; advanced 0.003-0.005 %, mostly the Carnot surcharge of
cryoplants rejecting at 700 K (the factory itself is about 0.6 MJ). Against 0.05 % (Atlas TARGET) and 0.1 % (FDP-1 baseline,
unsourced) the house load is not the problem. It stays small because each target yields about 81 GJ: an IFE plant target (350 MJ) with the same factory
energy would be a 2 % house load. Targets with a hohlraum or a smaller yield (T04) change this result directly, and so do
mass-bearing parts: at about 2e10 targets per mission, every gram per target is 20,000 t.

**Targets in flight (new negative finding, shared with T04).** FDP-1 injects at 400 m/s along the axis over a 46.6 m path at 107 Hz:
12.5 targets are in flight, 3.74 m apart. When pulse n fires, target n+1 is 3.74 m away and receives about 5.3e6 J/m2 of X-rays
(1.15 % of 81 GJ) and about 4.6e8 J/m2 of plasma. On its 2.6 cm2 cross-section that is about 1.4 kJ of X-rays alone, about 35 times
what sublimes its 0.137 g D2 shell (about 40 J). A target must stay behind the shield until the previous pulse has fired and then reach
the burn point before the next one: **v >= path x rate**, 4.7 km/s (advanced, efficiency 0.45) to 7.5 km/s (conservative temperatures,
efficiency 0.45). T04 finds the same constraint independently (4.6 km/s for V1). If the launcher is slower, the pulse rate must fall.
Fewer, larger pulses need a larger stand-off (R_s grows as pulse energy^0.5), so the rate that permits one target in flight is f <= v^2
x 4 pi F / P_x. Run through the existing `max_rep_Hz` input (advanced, efficiency 0.30):

| Launcher speed | Departure t | Rate Hz | Effect |
| --- | --- | --- | --- |
| unlimited (needs 6.1 km/s) | 12,654 | 130 | |
| 4.0 km/s | 13,447 | 72 | +6.3 % |
| 2.5 km/s | 14,866 | 36 | +17.5 % |
| 1.5, 1.0, 0.4 km/s | does not close | | |

Launching a liquid-He-3-in-D2 target at about 6 km/s is about 1.8e5 g in a 10 m barrel (1.8e4 g in 100 m). That is the TARGET,
with a sabot that must be stopped and recovered behind the shield. A shielded flight path (magnetic or material) would also do;
T03 owns whether the nozzle field can shelter a target near the burn point.

### 3.2 Driver power budget (Q2)

Driver loss (wall-plug minus beam) is (1 - eta)/(G eta) of fusion: 0.041 % at 0.45, 0.078 % at 0.30, 0.100 % at 0.25 (gain 3,000).
Split by component (shares of the loss; EXTRAPOLATION from the HIF literature, where core loss is the primary induction-linac loss and
pulser efficiency is 50-75 %, S-T01-HIF-EFF):

| Component | Share | Demonstrated reject T | Conservative circuit | Advanced circuit (TARGET) |
| --- | --- | --- | --- | --- |
| Induction cores (core loss, magnetising current) | 45 % | FINEMET rated 423 K (Curie 823-843 K), Metglas Curie 668 K | 470 K | 640 K (HITPERM-class FeCo, Curie about 1,250 K; core loss at temperature not measured) |
| Modulators (switches, SiC/GaN power stages, gate drives) | 30 % | SiC modules: 523 K junction continuous; MOSFETs fail within 300 h at 573 K | 500 K | 740 K (773 K logic ICs exist; MW power stages do not) |
| Beam loss, dumps, final-focus heating | 8 % | refractory, 900 K+ | 900 K potassium heat pipes | 1,000 K tin sheet |
| Pulse storage (dielectric and ESR loss) | 5 % | capacitors rated 473 K | 440 K | 550 K (mica/glass; no rated part found) |
| Busbars, conversion between recovery, storage and cells | 5 % | insulation class | 500 K | 740 K |
| Ion sources, injector, low-energy front end | 4 % | as modulators | 500 K | 740 K |
| Magnet cryoplant input (SC transport, 10 T arcs, final focus) | 3 % at 300 K | rejects about 300 K | 450 K, input x 1.52 (Carnot) | 700 K, input x 2.38 |

The cryoplant line matters more than its share suggests. Rejecting a 10 K plant's heat at 700 K instead of 300 K multiplies its input
power by 2.4, which adds about 0.003 % of fusion in the advanced case (585 MW at efficiency 0.30). Hot rejection is cheap in radiator
area but not in power. A separate negative: the scenario's optimistic cryo factor (15 W/W for 20-40 K lift) is charged to the warm
loop at 600-800 K, where Carnot alone is 14-39 W/W. It violates Carnot, but it is 0.0003 % of fusion and changes nothing measurable.
T01 books the coil cryoplant at its own Carnot-scaled input instead.

### 3.3 Component thermal circuits (Q3)

Area- and mass-weighted results for the planning case (split advanced, efficiency 0.30, 12,654 t; full tables in `RESULTS.md`):

| Circuit | MW | T K | Radiator | Area m2 | Mass t |
| --- | --- | --- | --- | --- | --- |
| Induction cores | 3,685 | 640 | panel 1.5 kg/m2 | 215,221 | 330 |
| Modulators | 2,457 | 740 | tin sheet | 144,497 | 92 |
| Beam loss and dumps | 655 | 1,000 | tin sheet | 11,555 | 8 |
| Magnet cryoplant | 585 | 700 | tin sheet | 42,938 | 27 |
| Pulse storage | 410 | 550 | tin sheet | 78,920 | 48 |
| Busbars | 410 | 740 | tin sheet | 24,083 | 15 |
| Ion sources | 328 | 740 | tin sheet | 19,266 | 12 |
| Factory, injection, controls, pumps, coil cryo | 155 | 600-740 | tin sheet / panel | 10,039 | 7 |
| **Warm total** | **8,680** | **T_eq 628** | | **546,519** | **540** |

The heat-weighted temperature is 705 K and the area-weighted temperature 675 K. The equivalent temperature that sets the area (628 K)
is lower because the tin sheet's emissivity of 0.5 enters as if the loop were colder. **The induction cores are 39 % of the warm area**,
and the capacitors (5 % of the heat) take 14 %. These two parts, not the power electronics, decide the warm radiator.

Conservative circuits at the same efficiency (equivalent 489 K) do not close on band-specific radiators. They close at 0.45 only when
the radiator is assumed at 1.0 kg/m2 (15,675 t, 1.19 km2, wing tip 2.3 km) or 0.5 kg/m2 (11,602 t). Demonstrated circuits (420 K) do
not close.

### 3.4 Driver-efficiency cases (Q4)

| Case | eta 0.25 | eta 0.30 | eta 0.45 |
| --- | --- | --- | --- |
| Atlas V1: departure t / warm km2 / wing tip m / gain cliff | 15,219 / 0.777 / 1,537 / 1,435 | 12,978 / 0.565 / 1,124 / 1,160 | 10,416 / 0.322 / 653 / 705 |
| Atlas V2: departure t / warm km2 / wing tip m | 12,058 / 0.361 / 737 | 10,838 / 0.276 / 570 | 9,272 / 0.168 / 356 (cliff 581) |
| T01 split advanced (V1 base) | 15,473 / 0.857 / 1,688 / 1,617 | 12,654 / 0.547 / 1,088 / 1,299 | 9,702 / 0.222 / 460 / 769 |
| T01 split advanced (V2 base, half-mass W armour) | 15,102 / 0.836 / 1,647 | 12,351 / 0.533 / 1,061 / 1,290 | 9,470 / 0.217 / 449 |
| T01 split conservative | does not close | does not close | does not close |

Gain cliff = the lowest target gain that still closes, by bisection (9 steps, log scale; circuits re-booked at every step). The split
ledger raises the cliff (769 vs 705 at 0.45) because the driver-proportional warm heat rises as gain falls and the loop is colder than
700 K. At the published efficiency of 0.25-0.30 the cliff is 1,300-1,600. This is the T04 question.

### 3.5 Hot power electronics and core materials (Q5)

| Part | Demonstrated (conditions) | Projected / TARGET | Source |
| --- | --- | --- | --- |
| SiC logic ICs | about 200-transistor JFET ICs, over a year at 773 K, 60 days in Venus conditions | MW conversion at 773 K: TARGET | S-NASA-SIC-500C (SECONDARY_VERIFIED) |
| SiC power modules | 1,200 V, >100 A modules continuous at 523 K junction (sintered-silver and chip-top packaging, >300,000 power cycles) | 573 K: current MOSFETs fail within 300 h of bias stress | S-T01-SIC-250C (SECONDARY_VERIFIED) |
| Pulse capacitors | PEI film and C0G ceramic pulse parts rated to 473 K; breakdown strength falls with temperature | 573 K mica/glass: no rated pulse part found | S-T01-CAP-200C (SECONDARY_VERIFIED) |
| Amorphous cores (Metglas 2605SA1) | Curie 668 K; practical rating about 423 K | | S-CORE-CURIE |
| Nanocrystalline (FINEMET) | Curie 823-843 K; rated 423 K continuous | 470 K near-term (EXTRAPOLATION) | S-CORE-CURIE |
| FeCo nanocrystalline (HITPERM) | magnetisation to about 1,250 K; grains stable at 873 K for 3,072 h; core loss reported only at room temperature | 640-673 K induction cores: TARGET | S-T01-HITPERM (SECONDARY_VERIFIED) |
| GaN, diamond | no MW high-temperature demonstration found in this study | UNKNOWN | none |

### 3.6 Radiator architectures (Q6)

| Type | Band K | kg/m2 (planform, two-sided) | Emissivity | Deployment / retraction | 0.007-0.02 g | Dust (to T02) | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Fixed heat-pipe blades (canon hot) | 1,800 | 3 (optimistic) | 0.9 | fixed | none | edge bumper | canon |
| Ti-water heat-pipe panels | 300-520 | 3 (NASA goal 2-3; flight tube-and-fin 5-10) | 0.9 | fold as panels | none | puncture isolates one pipe | EXTRAPOLATION |
| Halide/ceramic heat pipes | 450-700 | 5 (AlN/AlBr3 estimate 5.2) | 0.9 | as panels | none | as panels | modelling and life tests only |
| Alkali heat pipes | 700-1,400 | 6 | 0.85 | as panels | none | as panels | SP-100-class studies |
| Tin droplet sheet (VTX-07B) | 520-1,000 | 0.6 incl. generator and collector (sheet alone about 0.1) | 0.5 assumed (droplets 0.1-0.2) | stop the flow: no sheet in coast | fly the drops parallel to x: the acceleration only changes their speed; across the sheet the drift is 0.5 a t^2, about 0.9 m over 100 m at 20 m/s | sheet self-heals; collection loss from impacts UNKNOWN | TARGET |
| Deployable wings (VTX-07D, D-05) | any | the panel's, plus spars 25 kg/m (calculator) | | 0.35-1.7 km hinge-root wings | small in-plane loads | 0.5-2 km of edge | experimental only (D-05) |

The view factor stays as the calculator has it: W2 wings in one plane see neither each other nor the hull. The Graded Thermal Blade
Monte Carlo (`lab/studies/graded-thermal-blade/`) is the tool for any layout with more wings. Physical area is never reduced for view
factor.

Sensitivity of the planning case to the sheet's emissivity: 0.3 gives 14,147 t (+11.8 %), 0.5 gives 12,654 t, 0.8 gives 11,945 t
(-5.6 %). With panels at 1.5 kg/m2 instead of the sheet: 13,047 t (+3.1 %, T_eq 679 K, wing tip 838 m). The droplet sheet buys mass
only if its emissivity reaches about 0.5. Its strongest argument is retraction, which T02 needs.

### 3.7 Trade-offs (Q7)

All rows on the planning case (split advanced, efficiency 0.30, 12,654 t), with the change, the result and its label.

| Lever | Change | Departure t | Effect | Maintenance / reliability | Label |
| --- | --- | --- | --- | --- | --- |
| Driver efficiency | 0.30 to 0.45 | 9,702 | -23 % | | TARGET (published 0.20-0.30) |
| Driver efficiency | 0.30 to 0.25 | 15,473 | +22 % | | PUBLISHED range |
| Driver mass | 0.05 to 0.075 / 0.1 / 0.15 kg/kW | 15,389 / 19,623 / 43,679 | +22 / +55 / +245 %; 0.2 kg/kW does not close | heavier cores are more robust | the calculator's central tier is 0.2 |
| Sheet emissivity | 0.5 to 0.3 / 0.8 | 14,147 / 11,945 | +11.8 / -5.6 % | droplet loss, collector cleaning | UNKNOWN |
| Droplets replaced by 1.5 kg/m2 panels | | 13,047 | +3.1 % | no fluid loss; puncture risk | TARGET panels |
| Panels at band-realistic 5-6 kg/m2 (Atlas loop) | V1 700 K / V2 800 K | 50,589 / 19,998 | +386 / +116 % vs Atlas | | EXTRAPOLATION |
| Keep idle H2 vessels (D-04) | | 13,463 | +6.4 % | | decision |
| Launcher 4.0 / 2.5 km/s | | 13,447 / 14,866 | +6.3 / +17.5 % | | MODEL |
| Near-term components | conservative circuits | does not close | | | EXTRAPOLATION |

Driver mass is the steepest lever in the table, and nothing in T01 sources it. Volt-second scaling suggests 0.05 kg/kW is very
optimistic: 1.33 GV per beam set times about 1 µs of pulse at about 2.5 T core swing gives of order 1,000 t of core per gallery.
The record's 3e7 kg for a 5 MJ terrestrial driver points the same way. This is an EXTRAPOLATION and is not modelled.

### 3.8 Reinforcing combinations and double counting (Q8)

- **They compound.** Lower house load means less warm heat, so less fusion power to lift the same ship (the closure feeds back). That
  means a smaller driver and less driver loss, shorter wings and less exposed area for T02. The house step alone is -43 % at 600 K,
  more than its own watts, because of that feedback.
- **They overlap.** Once the house is small, a hotter loop saves less: in the Atlas, 600 to 700 K was worth -2,580 t at 0.05 % house.
  At the bottom-up house, the whole warm loop at 600 K is only 365 t of radiator (step 3b). The Atlas generations count the temperature
  saving against a house load that no longer exists.
- **They conflict.** Hot cryoplant rejection saves area but adds input power (Carnot), and with it recovery and driver load. A faster
  launcher costs little energy but drives the target design (T04). A lower pulse rate (slow launcher) raises the stand-off and the loop
  radii (T03, T05).
- **Booked once.** VTX-02C recovery is held at the Atlas placeholder (recovery efficiency 0.95, its loss in the hot loop); T01 credits
  no additional recovery and changes nothing in the recovery chain. The driver's beam energy is recirculated in the calculator's
  ledger; T01 books only the driver loss, and the cryoplant surcharge enters as house load, so nothing is counted twice. Every ledger
  sums to fusion.

## 4. Required breakthroughs

| What | Demonstrated | Needed (advanced case) | Gap | Record |
| --- | --- | --- | --- | --- |
| Induction-core material in service | 423 K rated (FINEMET) | 673 K with acceptable loss for years | +250 K; loss at temperature unmeasured | VTX-07A |
| MW power stages | 523 K junction, module scale | 773 K, MW, years | +250 K, x1,000 in power | VTX-07A |
| Pulse capacitors | 473 K rated | 573 K | +100 K | VTX-07A |
| Warm radiator above 520 K | about 5 kg/m2 class panels (estimates) | 0.6 kg/m2 droplet sheet at emissivity 0.5, or 1.5 kg/m2 panels | about 8x | VTX-07B |
| Driver | 0.20-0.30 efficiency on paper | 0.30-0.45 at 0.05 kg/kW | mass per W likely >10x | VTX-01B |
| Target launcher | 400 m/s gas guns; fusion pellet injectors about 1 km/s for intact cryogenic pellets | 4.7-7.5 km/s at 100-160 Hz, liquid He-3 inside | about 10x speed | T01-NEW-1 (with T04) |
| Target factory | single-shot cryogenic targets | 0.3-8 MJ per target, about 1e7 per day | rate, not energy | VTX-01C |

## 5. Blender integration recommendations (for T05; D-10 Stage B only)

- **Wings** (D-05, experimental `VAR_` geometry): W2 half-planes port and starboard (azimuth 0 and 180 deg), x -178.75 to +88.0 m
  (266.75 m), root radius 10 m. Tip radius 1,088 m (planning case, warm span 1,024 m from a 63 m warm root), 460 m at efficiency 0.45,
  1,688 m at 0.25. Draw the planning case and show the bracket as a ghost.
- **Circuit bands along the span**, hottest at the root: the 1,800 K hot band (28,337 m2 beyond the canon blades in the planning case),
  then dumps (1,000 K), then power and busbars (740 K), then the cryoplant band (700 K), then cores (640 K), then capacitors (550 K)
  outboard. Each band boundary is a thermal break and a manifold. Areas per band are in `RESULTS.md`.
- **Droplet sheet option** (CONCEPTUAL_ILLUSTRATION): generator bar on the forward edge of each wing frame, collector on the aft edge.
  Drops fly along -x, parallel to the thrust axis. The frame is a perimeter truss without panels, and there is no sheet in coast.
- **Low loop**: about 1,000 m2 of 300 K panels (propellant cryocooling), on the equipment module.
- **Driver galleries** (V1 base): r 4.5 m inside the equipment-module cone. The induction cores and their 640 K manifold are the largest
  heat source; route their manifold to the wing roots. Driver mass in the planning case is the calculator's (`ledger.json` digest
  `driver_t`). Do not draw it as settled: driver mass per W is the steepest unresolved number.
- **Target injection axis**: one target in flight at a time. Draw the muzzle at the shield face and the 46.6 m path, and no pellet train.
- Evidence status: wing envelope and band areas PARAMETRIC_PLACEHOLDER; droplet sheet CONCEPTUAL_ILLUSTRATION.

## 6. Limitations

- Component shares of the driver loss are EXTRAPOLATION. The HIF literature fixes the ranking (cores first), not the numbers.
- The calculator sees one equivalent radiator. Separate manifolds, thermal breaks and redundancy are carried only as transport mass
  per W (2-5e-6 kg/W).
- Radiator areal masses per band are estimates (SECONDARY_VERIFIED at best). The droplet sheet's emissivity is the main unknown.
- No orbit-average or transient thermal analysis. Coast heat loads (no burn) are not sized.
- Gain 3,000 and nozzle efficiency 0.79 are taken as FDP-1 has them. T04's gain-consistency finding is not folded in.
- Sources were read through web search excerpts (SECONDARY_VERIFIED); no full text was read.
