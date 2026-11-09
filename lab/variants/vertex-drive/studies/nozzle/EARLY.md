# T03 early findings: magnetic nozzle, helical fields, energy recovery

| | |
| --- | --- |
| Thread | T03, plasma physics and electromagnetic propulsion |
| Date | 2026-11-09 |
| Status | EARLY, superseded by `REPORT.md` and `HANDOFF.md` |
| Base | `8de3ffa`, generation V1 (10,416 t), branch `claude/project-thread-ujxhjo` |
| Methods | vacuum fields (exact loops, Biot-Savart), flux-excluding-sphere multipole work, thin-shell reflection model, Boris test particles. No MHD or PIC (D-09 not approved). |

Labels as in `planning/HANDOFF.md`. Every MODEL number below comes from `run_nozzle.py` or `calc_rerun.py` in this folder and is
written to `results/`. The thin-shell model is ideal (elastic, specular, no instabilities): its efficiencies are **upper bounds**.

## 1. Three findings that change the ledger

1. **The 0.79 in FDP-1 is very probably a momentum efficiency, booked as an energy efficiency.** The source behind S-MSFC-NOZZLE is
   Thio et al., "High-Energy Space Propulsion Based on Magnetized Target Fusion", AIAA 99-2703 (NASA MSFC, 1999): the nozzle turns
   "about 80 %" of the plasma's spherically radial momentum into axial impulse, theoretical maximum 86.3 % (PUBLISHED, secondary:
   abstract and summaries; full text not reached from this container). The four-burn calculator uses `nozzle_efficiency` as a share of
   energy (`jet = eta x stream`, `ve = sqrt(2 eta b eps)`), which is the thrust efficiency eta_T = F^2/(2 mdot P). For a
   monoenergetic elastic reflection eta_T = eta_mom^2, so 0.79 momentum is 0.624 energy. V1 at 0.624: **39,715 t** (3.8 x).
   Thio's 0.863 maximum as momentum gives 0.745: 12,118 t. Published simulations read the same way (Nagamine and Nakashima 1999,
   3D hybrid PIC: 0.65 momentum) give 0.42: V1 does not close. (MODEL, calculator re-run, `results/calculator_reruns.json`)
2. **One joule of stored field per joule of pulse (FDP-1 `nozzle_field_energy_ratio = 1`) cannot stop the pulse.** A flux-excluding
   bubble of the V1 pulse (80 GJ) needs a stored field energy of about 10 E_p before any three- or five-coil set turns it with useful
   efficiency; at 3 E_p the best pattern found reaches eta_mom 0.54. The virial structure scales with it: about 855 t of coil structure
   at 10 E_p (86 t in FDP-1 V0 at 1 E_p). V1 at eta_T 0.79 and ratio 10: 15,958 t; at ratio 30: 27,597 t. (MODEL)
3. **The FDP-1 three-loop cup leaks forward.** Near the axis the field is parallel to the plasma's motion, so the shell is not stopped:
   with the three loops alone 12-14 % of the shell (polar angles below about 40 deg) passes through loop 1 toward the shield and the
   ship, and another 7-8 % reflects forward. Best clean eta_mom 0.68 at 10 E_p. Two **forward closure coils** on the X-ray stand-off
   sphere (polar 20 deg and 40 deg, d = R_s) fix it: eta_mom 0.86 (eta_T 0.74) at 10 E_p, about 0.89 (eta_T 0.79) at 15 E_p, forward
   leak 0.3 %. (MODEL, upper bound) **Coupled V1** (calculator re-run with each C design's eta_T, stored-energy ratio and plume-strike
   share of the nozzle loss): 6 E_p 1.03 Mt, 10 E_p 30,949 t, **15 E_p 22,683 t (best)**, 20 E_p 30,269 t, 30 E_p 51,283 t; 3 E_p does
   not close. Even the ideal model puts V1 near 2.2 x its booked 10,416 t.

Coupled with T04's finding that gain 3,000 is inconsistent (59-97 kt), V1's 10.4 kt is optimistic on at least three independent levers.

## 2. Coil positions per configuration (nozzle frame: origin at the burn point, +z = ship +X, exhaust toward -z)

Ship frame: x = x_burn + z, x_burn = shield aft face - R_s, R_s = 43.11 m (V1). With V0's shield thickness x_burn is about -227.5 m
(PARAMETRIC_PLACEHOLDER until T00 reruns the V1 layout). Currents are the thin-shell optimum at 10 E_p (W = 8.0e11 J); winding radius
from a 25 T surface-field TARGET and 1e9 A/m2; envelope = 3 x winding radius (FDP-1 envelope factor) plus armour.

| Config | Coil | Polar deg | d m | Loop radius m | z m | Current MA | Winding radius m | Envelope radius m | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A (FDP-1) | L1 | 60 | 43.11 | 37.34 | +21.56 | 29.5 | 0.24 | 0.71 | ENGINEERING_SUPPORTED geometry, currents MODEL |
| A | L2 | 90 | 64.67 | 64.67 | 0 | 29.5 | 0.24 | 0.71 | as above |
| A | L3 | 120 | 129.34 | 112.01 | -64.67 | 29.5 | 0.24 | 0.71 | as above |
| C (shaped) | C1 | 20 | 43.11 | 14.74 | +40.51 | 80.7 | 0.65 | 1.94 | PARAMETRIC_PLACEHOLDER |
| C | C2 | 40 | 43.11 | 27.71 | +33.03 | 14.1 | 0.11 | 0.34 | PARAMETRIC_PLACEHOLDER |
| C | L1 | 60 | 43.11 | 37.34 | +21.56 | 15.5 | 0.12 | 0.37 | as A |
| C | L2 | 90 | 64.67 | 64.67 | 0 | 25.6 | 0.20 | 0.61 | as A |
| C | L3 | 120 | 129.34 | 112.01 | -64.67 | 24.1 | 0.19 | 0.57 | as A |

C1 sits 2.6 m aft of the shield face, outside its 6.0 m rim (the 7.9 deg hardware cone): it is in the burn's sky and takes the same
X-ray fluence as L1. FDP-1 draws a 0.21 m envelope for every loop; at the currents a 10 E_p field needs, every envelope is 2-9 x
larger. Solid angle of the envelopes (sin(polar) x envelope / d): A 0.030, C 0.040, against 0.017 in V1.

- **B (clocked sectors)**: the A or C loops with four sectors each, 5 deg gaps, clocked 0/45/90 deg loop to loop; no new envelope;
  sector joints at 45 + 90 q deg plus the clock angle; feeders modelled as a bus ring 5 m outside each loop (ASSUMPTION).
- **D (balanced)**: either the sectors clocked 0/45/0 deg, or two l = 2 helical windings on the paraboloid between L1 and L3 with
  the twist reversed at L2 (four conductors at 90 deg, each 2-20 MA). Helical conductors run through the burn's sky between the loops.
- **C3D (non-planar)**: one-handed l = 2 helical windings on the same paraboloid; not recommended (section 4).

Overlay data for T05: `results/field_lines.json` (field lines and the stopping surface in the r-z half-plane, ILLUSTRATIVE).

## 3. Heat loads and recovery (for T01, T02)

Per V1 pulse train (E_p = 8.0e10 J of plasma per pulse, 107 Hz, 8.56 TW of plasma), C design at 10 E_p:

| Quantity | Value | Label | Note |
| --- | --- | --- | --- |
| Plasma striking hardware | 1.6 % of plasma, 137 GW: shield face 0.55 % (47 GW), forward along the ship 0.83 % (71 GW), L1 0.23 % (19 GW) | MODEL (upper-bound geometry) | calculator books 0.415 % of fusion (36 GW) on all hardware; T03 share of the nozzle loss is about 0.06, not 0.02 |
| Low-beta tail and duds to the shield centre | 5.5 % of the tail mass (C), 34 % (A) | MODEL (test particles, matches adiabatic loss cone) | field-aligned, onto the crew shadow core; T04 duds: 27 MJ at 400 km/s |
| Unscreened REBCO pulse loss | 7.4 GW at the windings (20-40 K) | EXTRAPOLATION (Bean estimate, x10 band) | flux-conserving coils swing about 5 % of their current every pulse: **not acceptable**; windings need warm eddy-current screens |
| Screen dissipation | about 0.1 % of plasma energy, 8.6 GW (band 0.03-1 %) to the hot loop | EXTRAPOLATION | same hardware as the VTX-02C pickup |
| Coil armour radiation | about 2.4 x the V1 radiation_on_hardware share (solid angle 0.040 vs 0.017) | MODEL (scaling) | |
| Required recovery (extraction) | 0.13 % of fusion (eta_r 0.95) to 0.20 % (driver 0.30, eta_r 0.80) | MODEL (V1 ledger) | taken from the stream before the nozzle, as the calculator already does |

**Recovery fraction handed to T01:** extraction 0.0013 of fusion (bounds 0.0012-0.0020), recovery efficiency 0.80-0.95 (ASSUMPTION,
unmeasured at this rate), loss heat to the hot loop. At this size the coupling to nozzle efficiency is second order (the extraction
is 0.13 % of a transient that stores about 70 % of E_p); no recovery beyond the electric load is credited. Schilling, Cassibry and
Adams (JBIS 76, 2023) report that adding power generation costs 7 % of nozzle efficiency in their pulsed design (PUBLISHED; their
extraction share not reached).

## 4. Helical fields (VTX-03A/B/C)

- Clocked sectors (B) give **0.3-1.1 deg** of field-line rotation at the stopping surface (5 % differential trim), 3 deg at 20 %.
  Magnetic tension stabilises a flute only for wave vectors within about 45 deg of the field; shear has to reach tens of degrees within
  a wavelength to matter. The sectors cannot supply it. Roll torque 1-3 kN m at 5 % trim, 6-28 kN m at 20 % (RCS couple 26 kN m).
- Helical windings reach 7 deg (2 MA), 18 deg (5 MA), 52 deg (20 MA) of shear but cost collimation in the same model: eta_mom 0.86 ->
  0.83 / 0.76 / 0.63 on C. Roll torque 0.24-0.7 MN m one-handed; "balanced" windings cut it only at one current (2.7e4 N m at 5 MA)
  and not robustly. **Shear and collimation conflict**; any stability benefit has to be shown by D-09 and must outweigh about 10
  points of eta_mom per 18 deg of shear.
- Rayleigh-Taylor at the field-plasma interface: about 7 e-folds per phase (deceleration, re-acceleration) at the finite-Larmor-radius
  limit (l about 70, wavelength about 2.5 m): linear theory says the interface goes nonlinear every pulse. Nagamine and Nakashima's
  3D hybrid PIC found the effect on efficiency "limited" (PUBLISHED, laser scale). This is the question D-09 exists for.

## 5. One loop sector lost (T02 request)

C design at 10 E_p, one 85 deg sector at zero current (dust strike or quench), first-order thin-shell perturbation
(`sector_loss.py`, `results/sector_loss.json`; indicative, a lost sector is beyond first order near it). MODEL.

| Sector lost on | eta_mom (intact 0.859) | Plasma on hardware (intact 1.1 % of stopped rays) | Side force | Note |
| --- | --- | --- | --- | --- |
| C1 (forward closure) | 0.855 | 1.45 % | 3.9 kN | |
| C2 | 0.857 | 1.10 % | 3.0 kN | |
| L1 | 0.851 | 1.29 % | 2.1 kN | |
| L2 (burn plane) | 0.840 | 2.10 % | 8.3 kN | worst: the strike share doubles |
| L3 | 0.855 | 1.22 % | 1.9 kN | |

A lost sector costs 0.4-2 points of eta_mom (about 1-4 % of eta_T) and a 2-8 kN side force (0.3-1.2 % of the 0.70 MN thrust), which
the remaining sectors or the driver-side pointing must trim. On the leaky three-loop A* design a lost L1 sector costs 3 points and 15 kN.
The ship survives a single lost sector; the plume on the shield and the ship rises by up to 2 x while it is out, so replacement
time matters to T01's hot-loop margin.

## 6. What T03 still delivers

The full sweep (A, A*, C at 3-30 E_p), the coupled calculator runs, coil forces and struts, the D-09 study plan, `REPORT.md`,
`registry_proposal.toml` and `HANDOFF.md`.
