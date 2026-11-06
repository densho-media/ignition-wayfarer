# Fiji Drive v4: continuous vs pulsed fusion, an independent comparison

Research study only. Canon, `data/`, the generators, the production Blender model and the LOCKED propulsion topology are unchanged.
All numbers come from `fiji_v4.py`, which writes `results/v4.json` and `results/v4_summary.txt`. That script was written from scratch and
reads the v3 results only to compare against them. Statuses: canon values keep their workbook status; everything new here is PROTOTYPE.

## Summary

1. **The v3 IFD-1 numbers were too favourable.** An independent recheck lowers its power from 0.154 TW to **0.082 TW**. Three errors caused this:
   - v3 left out electron–electron bremsstrahlung (neutral share 0.247, not 0.195);
   - v3 modelled the coils as thin bands, but a 1.8 m deep coil also catches rays on its sides (hardware share 0.53, not 0.28);
   - v3 sized the coil structure with no safety factor.

   With the complete ship mass (departure 21,800 t), the four-burn mission takes **~1,600 years of burning**.
2. **A second limit applies to every D–³He drive:** the exhaust speed.
   - To reach ve 19,201 km/s, at least 52 % of the fusion energy per kg of exhaust must end up as jet energy:
     directed efficiency × burn fraction ≥ 0.52, with no added inert mass.
   - Continuous drive: either particles stay confined ~124 s (open/FRC systems hold them for milliseconds to seconds), or canon's
     "hypothetical" 95 % recovery of unburned fuel from the exhaust must hold. Without recovery and with τ_p ≈ 1 s, ve ≈ 4,300 km/s.
   - Pulsed drive: the fuel must burn at areal density ρR ≈ 111 g/cm². NIF reaches ~1 g/cm², so that is about 100 times beyond any
     demonstration. It also needs a magnetic nozzle at its theoretical best efficiency (0.79). At the 0.55 seen in simulations, the
     mission ve needs 0.4 Mt pulses.
3. **Pulsed is the better physics, but it does not close.** A point burn far from all hardware cuts radiation interception from 0.53 to
   ~0.003. Dense fuel traps its own neutrons and most X-rays.
   - The heat-limited power rises 60–120× to 5–10 TW. Mission burn time falls to **55 years (optimistic) or ~330 years (central)**.
   - The new bottleneck is the driver. Its waste heat leaves at 350–400 K and needs 1.5–30 km² of extra radiator. The pulses also force
     the nozzle loops 170–1,000 m from the burn point.
4. **Fundamental incompatibility after optimisation.** Today's mission (261 TW, ~10-day first burn at 0.5 g, 4.4 kt ship) needs ship
   heat ≤ 3.7 × 10⁻⁵ of fusion power. No continuous or pulsed D–³He drive found here gets within a factor of ~10 of that on radiation
   alone. With the driver included, it falls short by 100–1,000×. **The heat problem is not solved.**

## 1. Independent verification of IFD-1

| Check | v3 | v4 recheck | Effect |
|---|---|---|---|
| Neutral share (100 keV, 1:1) | 0.195 | **0.247**: brems 0.237 + neutrons 0.010 (Bosch–Hale reactivities, Rider/Wesson bremsstrahlung with the e–e term) | v3 dropped e–e bremsstrahlung (+26 % at 100 keV). Canon 2.5:1 → 0.42; hot-ion 0.5:1 → 0.13 |
| Energy ledger | sums to 1.000 | sums to 1.000 | Closes in energy |
| Mass closure | 0.52 g/s labelled "H2 mass loading" | 0.438 g/s of it is reacted fuel (ash); only 0.081 g/s is left for H2 + unburned fuel | Label error. It also exposes the burn-fraction limit (section 3) |
| Wall flux | 10 MW/m² peak (MC) | analytic line source 12.2 MW/m² at mid-plane; thick-coil MC peak 0.000327 W/m² per W of neutral power | The wall limit falls to 0.124 TW |
| Interception | own 0.251, shield 0.029 | **face 0.220 + coil sides 0.278 = 0.498**, shield 0.036, escape 0.466 | The slots between 1.8 m deep coils are deep relative to their width; v3 counted only the faces |
| Binding limit | wall flux, 0.154 TW | **hot loop, 0.082 TW** (0.53 × 0.247 × P ≤ 10.8 GW) | −47 % |
| Sparse coils | — | ripple 0.3 % at the plasma edge; 23 MA·turn per coil; 41 MA/m² winding; 24 MPa magnetic pressure; β ≈ 0.85 | Confinement geometry is plausible; field quality is not the problem |
| Coil structure (virial, W = 3.6 × 10¹¹ J) | 346 t (composite at ultimate strength) | 940 t composite at safety factor 2.5; 4,300 t steel | Fiji amplification does not reduce the stored field energy the structure must carry |
| Particle confinement | not checked | n = 5.1 × 10²⁰ m⁻³, burn time 23 s; burn fraction 0.84 needs τ_p ≈ 124 s | See section 3 |
| Complete ship mass | not done | drive 5,003 t (canon allowance 250 t) → protected and operational ship 6,053 t → departure **21,811 t**, propellant 13,781 t | — |
| Mission | 0.23 mg, ~240 y | **0.025 mg, 1,587 years of burning** | 20,000× today's 29 days |

**Sources.** The cloud session could not open arxiv.org, osti.gov or ntrs.nasa.gov, so I checked each source by search:
- **REBCO fluence 3 × 10¹⁸ n/cm²:** v3 cited arXiv 1809.10555, which I could not confirm. The correct source is Sorbom et al., ARC,
  arXiv:1409.3540. That figure is Nb₃Sn data used as a lower bound for REBCO, not a measured REBCO limit.
- **Liquid lithium:** v3 said "~10 MW/m² demonstrated, 20–60 projected". PPPL (Maingi 2020) shows 10 MW/m² as a *modelled design target*.
  I found no demonstration. The 50 MW/m² case is unsupported, and the v3 OSTI 1756723 citation is unverified.
- **DFD radiation split:** the cited arXiv 2002.12686 is unconfirmed. Use Cohen et al., JBIS 72 (2019) and Thomas et al., AIAA 2017.
- **Confirmed:** Mattick & Hertzberg (NTRS 19810062992) and Thibeault & Fay (NTRS 20160010096, a hydrogen/boron/nitrogen shielding study).

## 2. Pulsed fusion research: demonstrated vs projected

| Item | Demonstrated | Projected (concept studies) |
|---|---|---|
| ICF ignition, D–T (NIF) | 8.6 MJ from 2.08 MJ laser, target gain 4.13 (April 2025) [LLNL] | gain 30–100+ |
| MagLIF, D–T equivalent (Sandia Z) | 1.1 × 10¹³ neutrons ≈ 2 kJ D–T equivalent; seed field 10–15 T (2020, PRL 125, 155002) | ~100 kJ on Z |
| MTF (General Fusion LM26) | solid Li liner compressing a spherical-tokamak D plasma: ~3× electron temperature (2025–26) | 1 keV, then 10 keV phases |
| FRC compression (Helion) | Polaris operating 2025; no published compression yield | net electricity |
| Fusion Driven Rocket (MSNW/NASA NIAC) | subscale liner and FRC tests only | gain 20–500, liner 0.28–0.41 kg (secondary source), Isp 1,600–5,700 s (≈16–56 km/s) |
| D–³He inertial burn | none | simulations: ρR 8.5 g/cm², 70 keV, gain ~480; most need a D–T igniter |
| Pulsed magnetic nozzle efficiency | — | theoretical 0.79–0.86 (MSFC); simulated 0.34–0.55 (UAH Z-pinch nozzle) |
| Daedalus (BIS 1978) | — | D–³He pellets at 250 Hz, ve ≈ 10,600 km/s, electron-beam drivers |
| W first wall under pulsed X-rays | ~1 J/cm² melts W in one shot; ~1 J/cm² multi-pulse roughening (Sandia/LLNL) | — |

Nothing in the pulsed column has been demonstrated with D–³He, at the needed ρR, or at a repetition rate above a few shots per day.

## 3. The exhaust-velocity limit applies to both drives

The jet's kinetic energy is η × (reacted mass) × 3.53 × 10¹⁴ J/kg. The exhaust mass is the reacted fuel, plus unburned fuel that is not
recovered, plus any inert mass (H₂, liner, ablator). So:

ve = √(2 η ε b / (1 + μ)) when unburned fuel is not recovered (b = burn fraction, μ = inert mass per kg of fuel fed).

- **Continuous:** b = τ_p / (τ_p + τ_burn), with τ_burn = 23 s at IFD-1 density.
  - τ_p 1 s → b 0.04 → ve 4,277 km/s. τ_p 10 s → 11,526 km/s. τ_p 100 s → 18,849 km/s.
  - Canon (b 0.8, recovery 0.95, both marked "hypothetical") reaches 20,764 km/s at η 0.62.
  - No mechanism is known for pulling unburned fuel back out of a 19,000 km/s plasma exhaust.
- **Pulsed:** b = ρR / (ρR + H_B). I calibrated H_B against D–T at 20 keV (6.7 g/cm², textbook 6–7). For D–³He it is 42 g/cm² at
  100 keV and 56 at 70 keV.
  - At the theoretical nozzle efficiency 0.79, the mission ve needs **ρR 111 g/cm², b 0.73**.
  - At the simulated nozzle efficiency 0.55 it needs ρR 1,049 g/cm². That is not credible.
- **Inert mass:** any liner or ablator lowers ve fast. 5 % inert mass → 18,738 km/s; 100 % → 13,577 km/s.
  An FDR-class 0.35 kg liner on a 5.8 g fuel pellet gives **2,445 km/s**. That rules out coil-driven liners (FDR, MagLIF-type
  transmission lines) for this mission.

## 4. Fiji lattice in a pulsed engine (canon properties only)

| Role | How | Limit |
|---|---|---|
| Nozzle field | Lattice-cored superconducting loops; amplification A (canon up to 30) cuts conductor ampere-turns by A | The stored field energy and the structure it needs (virial) do not change. The lattice is not a heat sink (LOCKED), so loops sit behind the X-ray stand-off and their heating goes into the hot loop |
| Target magnetisation | A ≤ 150 T seed in the target-formation region (MIF). It traps 14.7 MeV protons (Larmor radius 3.7 mm at 150 T, ~55 µm after 10× compression) and suppresses electron heat loss | Raises target gain and lowers driver energy. It does **not** lower the ρR needed for burn fraction, because the fuel at β ≫ 1 is held by inertia, not by the field |
| Flux stabilisation | The lattice holds the nozzle flux geometry steady between pulses; amplification is set by temperature, so it is slow and steady | Cannot be the fast compression driver; that would be a new property |
| Energy recovery | The expanding plasma compresses nozzle flux, and pickup loops recharge the driver (FDR, Daedalus) | 5 % recovery loss goes into the 1800 K loop |

## 5. Pulsed model (IFD-P) and budgets

- **Pulse:** 5.8 g of D–³He (1:1) at 1,000 g/cm³, ρR 111 g/cm², 100 keV. Burn fraction 0.73, yield 1.5 TJ (352 t TNT).
  X-ray escape 0.086 after self-absorption; neutron escape ~2 × 10⁻⁵, because the dense fuel thermalises them. Bred tritium burns in place.
  Jet efficiency 0.72 at nozzle efficiency 0.79.
- **Density sets pulse size:**

  | Fuel density | Pulse yield | Rate at mission power | Stand-off (1 J/cm²) |
  |---|---|---|---|
  | 300 g/cm³ | 3.9 kt | 18 Hz | 3.3 km |
  | 1,000 g/cm³ | 352 t | 196 Hz | 1.0 km |
  | 3,000 g/cm³ | 39 t | 1.8 kHz | 335 m |
  | 10,000 g/cm³ | 3.5 t | 20 kHz | 100 m |

- **Nozzle:** three Fiji-amplified superconducting loops at the stand-off radius. Field at the stopping sphere 0.04 T (central)
  to ~0.5 T (optimistic). Hardware solid angle 0.003.
- **Drivers:** must reach the target from the stand-off.
  - Heavy-ion beam: 30 % efficient.
  - Laser: 15 %.
  - Magnetic liner: fails the ve limit (section 3).
- **Heat:** hot-loop heat = escaping radiation × hardware solid angle, plus recovery loss, held ≤ 10.8 GW. Driver loss heat goes to its
  own 350–400 K radiators at 5 kg/m², counted in the mass. The chosen power minimises total burn time with the complete ship mass.

| Design (heavy-ion driver) | Fusion power | Rate | Stand-off | Hot loop | Driver heat | Driver radiator | Drive mass | Departure | Start acceleration | Burn time |
|---|---|---|---|---|---|---|---|---|---|---|
| optimistic (gain 3000, 3,000 g/cm³, 4 J/cm², A 30) | 5.0 TW | 31 Hz | 167 m | 9.5 GW | 3.9 GW | 1.5 km² | 13.6 kt | 53 kt | 0.72 mg | **54 y** |
| central (gain 300, 1,000 g/cm³, 1 J/cm², A 10) | 10 TW | 6.8 Hz | 1,004 m | 8.6 GW | 78 GW | 30 km² | 174 kt | 640 kt | 0.12 mg | **327 y** |
| pessimistic (gain 50, 300 g/cm³, A 3) | 2.5 TW | 0.15 Hz | 3,348 m | 9.0 GW | 117 GW | 45 km² | 358 kt | 1,312 kt | ~0 | 2,671 y |

Laser drivers are 2.5–4× worse on the same assumptions (optimistic 142 y, central 1,206 y). At the full mission power (289 TW), the
central heavy-ion case would put 250 GW into the hot loop and 2,250 GW into driver radiators.

## 6. Same mission, both drives

Requirements held fixed: four 0.016 c burns at ve 19,201 km/s, the 10.8 GW 1800 K drive share, and complete ship mass. Results are in
`diagrams/mission_comparison.png`.

| Drive | Fusion power | Departure mass | Burn time | ve basis |
|---|---|---|---|---|
| Today (canon WORKING) | 261 TW | 4,426 t | 29 days | η 0.8, b 0.8, recovery 0.95 (hypothetical) |
| IFD-1 continuous (v4 recheck) | 0.082 TW | 21,811 t | 1,587 y | needs τ_p ≥ 124 s or canon recovery |
| IFD-P pulsed, optimistic | 5.0 TW | 53,398 t | 54 y | ρR 111 g/cm², ideal nozzle |
| IFD-P pulsed, central | 10 TW | 640,034 t | 327 y | same |

Lowering ve is a possible trade, but it is not adopted here. At today's thrust, jet power falls in proportion to ve, but propellant grows:
- 15,000 km/s → departure 7,117 t;
- 10,000 km/s → 64,286 t;
- 6,000 km/s → tank mass diverges.

A lower ve does not fix the heat ratio.

## 7. Number of chambers and nozzles

The pulse size is set by the ρR that the mission ve needs, not by the chamber count. So every chamber needs a full-size nozzle around its
own burn point.

| Chambers × nozzles | Rate per chamber | Cluster span | Hardware solid angle | Nozzle mass | One out |
|---|---|---|---|---|---|
| 1 × 1 | 6.8 Hz | — | 0.0032 | 9.3 kt | thrust 0 |
| 2 × 2 | 3.4 Hz | 2.2 km | 0.0039 | 18.7 kt | 50 % |
| 4 × 4 | 1.7 Hz | 3.1 km | 0.0051 | 37.3 kt | 75 % |
| 1 × 4 | — | — | — | — | infeasible: a point burn expands in microseconds and cannot be ducted into four nozzles |

**Recommendation: one chamber and one nozzle.** The nozzle's loops are split into four current sectors, which keep the four-way vectoring
role of today's four nozzles. Four separate nozzles would each have to be km-scale, so this is a justified reason to depart from the four
nozzles, and it needs your approval. Redundancy is better bought with spare beamlines, injectors and loop sectors than with extra chambers.

## 8. Recommended integrated Fiji Drive architecture (direction, not a closed design)

**IFD-P: an aft point-burn pulsed drive, built on the accepted aft radiation-escape geometry.**
- Magnetised D–³He targets made of fuel only: no liner, no high-Z ablator.
- Compressed to ρR ≥ 110 g/cm² by stand-off heavy-ion beams.
- Burned 170–1,000 m aft of the ship inside three Fiji-amplified superconducting nozzle loops, with inductive energy recovery.
- A small shadow shield; four loop sectors for vectoring.

It beats continuous IFD-1 on every coupled measure:
- radiation interception 0.003 vs 0.53;
- power ceiling 60–120× higher;
- mission burn time 5–30× shorter.

It keeps D–³He and does not change ve, the mission or the radiator temperatures. **It still does not meet the mission.**

**Remaining scientific limits (blockers):**
1. **ρR 111 g/cm².** Roughly 100× NIF, with D–³He at 100 keV, which nobody has ignited. A D–T igniter, as most studies use, adds 14 MeV
   neutrons.
2. **Nozzle efficiency 0.79.** That is the theoretical bound. At the simulated 0.34–0.55 the mission ve cannot be reached.
3. **Target gain 300–3,000** with a stand-off driver at 30 % efficiency and 0.2 kg/kW. Best demonstrated gain is 4.1, with a 1 % wall-plug laser.
4. **Driver waste heat at 350–400 K:** 1.5–30 km² of radiator. This is now the largest mass item.
5. **Pulse X-ray fluence.** The kilometre stand-off is set by ~1 J/cm² on tungsten; renewable armour is CONDITIONAL.
6. **Heat ratio.** The mission needs ≤ 3.7 × 10⁻⁵ of fusion power as ship heat. Radiation × solid angle alone is ~3 × 10⁻⁴, and the
   driver adds 10⁻³–10⁻².
7. **Repetition rate:** 7–200 Hz at the needed yields, against a few shots per day demonstrated.

## 9. Owner decisions (nothing applied)

- Adopt **IFD-P** (pulsed point-burn) as the research direction in place of continuous IFD-1.
- Allow the change from four nozzles to **one nozzle with four vectoring sectors**.
- Choose how to reconcile the mission:
  - accept decades-to-centuries of burn at the existing radiators;
  - fund km²-scale radiators;
  - lower ve with more propellant;
  - or re-baseline the Fiji canon (P1, burn fraction and recovery are "hypothetical" and OPEN).
- Correct the canon flags in a later authorised Drive pass:
  - η 0.8 exceeds the charged share;
  - burn fraction 0.8 plus recovery 0.95 carries the ve;
  - the B01 absorbed fraction 4 × 10⁻⁵ has no mechanism.

## Sources

- LLNL NIF FY2025: https://annual.llnl.gov/fy-2025/national-ignition-facility-2025
- Sandia MagLIF 2020 record (PRL 125, 155002): https://www.sandia.gov/labnews/?p=5650
- General Fusion LM26 compression: https://generalfusion.com/wp-content/uploads/2026/06/The_Science_of_Compressional_Heating_in_LM26.pdf
- FDR NIAC Phase I final report: https://www.nasa.gov/wp-content/uploads/2017/07/niac_2011_phasei_slough_fusionrocket_tagged.pdf ; Phase II NTRS 20190001178; NTRS 20160010608
- FDR projections (secondary): https://nextbigfuture.com/2012/09/the-fusion-driven-rocket-nuclear.html ; https://en.wikipedia.org/wiki/Nuclear_pulse_propulsion
- Pulsed magnetic nozzle efficiency: UAH thesis https://louis.uah.edu/uah-theses/835 , dissertation https://louis.uah.edu/uah-dissertations/249 , MSFC NTRS 20020016726
- Daedalus: https://en.wikipedia.org/wiki/Project_Daedalus ; Icarus https://arxiv.org/pdf/1005.3833
- D–³He inertial burn: https://www.osti.gov/biblio/7107437 ; https://wx1.ans.org/pubs/journals/fst/a_30055
- Pulsed X-rays on tungsten: https://www.osti.gov/biblio/20849929
- ARC / REBCO fluence: https://arxiv.org/abs/1409.3540
- Liquid-lithium PFC (modelled 10 MW/m²): https://nstx.pppl.gov/DragNDrop/NSTX_Meetings/Monday_Physics_Meetings/2020/2020_11_23/Maingi%20LMPFC%20NSTXUPM%2023Nov20.pdf
- DFD: Cohen et al. JBIS 2019 https://w3.pppl.gov/ppst/docs/cohen2019jbis.pdf ; Thomas et al. AIAA 2017 https://w3.pppl.gov/ppst/docs/thomas2017aiaa.pdf
- Reactivities: Bosch & Hale, Nucl. Fusion 32 (1992) 611. Bremsstrahlung: Rider, Phys. Plasmas 2 (1995) 1853.
