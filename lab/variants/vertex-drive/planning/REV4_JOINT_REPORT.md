# Vertex Revision 4: joint report (T00 engineering, T05 geometry)

| | |
| --- | --- |
| Kind | research report, NON-CANON |
| T00 | `claude/project-thread-9rsgog`, from `e24fc7a`; details in `studies/rev4/REPORT.md` |
| T05 | `claude/project-thread-ctwplp`, Rev 4 step 1 `f6f527d` (`work/vertex-blender/rev4_geometry.json`, `rev4.json`); T05's later Rev 4 commits are named in its own thread |
| Handoffs | T00 → T05 `lab/variants/vertex-drive/results/t05_handoff_rev4.json` (v1); T05 → T00 `work/vertex-blender/rev4_geometry.json` (v1) |
| Unchanged | canon, IGNITION Drive, production geometry, `data/`, `src/`, FDP-1 and four-burn physics; nothing on `main` |
| Date | 2026-11-09 |

## 1. Resolved

- **ISS-014 closure-coil radiation accounting.** An eight-term ledger now separates:
  - radiation to space;
  - radiation on the coils;
  - radiation on other hardware;
  - plasma on hardware;
  - plasma through the nozzle;
  - the jet;
  - conversion losses;
  - coil cooling loads.

  It conserves energy to 1e-9 and books each watt once. Coil heat is 6.2 GW on the bottom-up assembly and 11.3 GW on T05's ray cast.
  The 11.9 / 15.5 / 30.1 GW cases are kept.
- **Coil assembly projected solid angle.** T00's analytic build and T05's 2-million-ray cast agree within 5 % per coil (C1 0.0151,
  C2 0.0082 on T05's build).
- **Fluid basis:** a lithium loop with a Li/Sn exchanger (both threads).
- **Launcher kinematics** reproduced independently (8.81 km/s, 289 m, 8.3 J/cm² at the snout tip).
- **S5 stiffness error** found by T05 and confirmed by T00's beam model: S5 as drawn gives a cantilever f₁ of 0.075 Hz, not 0.2 Hz.

## 2. Reduced

- The coil heat is a small ship cost (about 260 t of departure for 6 GW).
- Neutron heating of the windings stays small (about 14 kW at 20 K) once the screen meets the REBCO fluence limit.
- Buckling of the stretch is not critical (factor about 500 with SF 2).
- The pulse rate does not excite the longeron bays (79-121 Hz).

## 3. Made harder (new or larger problems)

| Problem | Number | Owner of the next step |
| --- | --- | --- |
| Closure-coil hardware is unbooked: winding packs, LiH screen, struts, cryostat, Li plant | 2.0-2.3 kt; V4 gears 12.4 t of departure per tonne, so **68-72 kt** coupled (approximation) | design decision: accept the growth, or reduce the winding mass (J_e) and the neutron fluence |
| REBCO neutron fluence at the coils | about 1.1e20 n/cm² unshielded, 35× the degradation level | 0.56 m LiH screen, or a lower-neutron fuel model |
| FDP-1 loops carry no conductor mass | same finding for every FDP-1 loop | OPEN (FDP-1 code protected) |
| FDP-1's Ω misses hardware | T05's ray cast: loops + struts + shield 0.033 against 0.0248; wing spars 0.0030 | booked as a case (+5 GW hot) |
| **Near-axis plasma channel** | the shield-face centre and the snout tip receive about 340-470 J/cm² of 2.4 MeV/u ions per pulse | **blocker**: an axis plug or a non-axisymmetric field; D-21-class modelling |
| Soft X-ray spectrum | W, Mo and SiC fail at or below 10 keV; only CFC and lithium survive every band | spectrum calculation (radiation transport) |
| Pulse rate on the heavier ship | rises to 312 Hz, so the launcher needs 14 km/s; capped at 196 Hz the ship is 91 kt | joint launcher and ship closure |
| S5 mass | **2.0-2.2 kt** (N9, cantilever-sized), against 1.18 kt in the brief | T05 draws N9 |
| Ring frames | a free frame ovalises at 0.14 Hz | frames need spokes or ties |

## 4. Still unproven

- **Launcher B-modified.** The 30 K gas-filled HDC capsule survives 13,700 g mechanically. Its compression from gas density (convergence
  about 44), the 196 Hz cold fill and the sabot stripping at km/s are not demonstrated.
- **The ideal-nozzle efficiency 0.791** (D-21, unchanged).
- The coupled masses are **approximations**, not a converged spacecraft design.
- The CFC conductivity loss under neutrons at 1,500 K, which sets the armour replacement interval.
- The pulsed-field AC loss and eddy-screen heating in the coils: screened by a warm conductor whose time constant is about 1 s, against a
  5 ms period. Not quantified.

## 5. Options

| Option | Status |
| --- | --- |
| Launcher B (layered target, 13,700 g) | **REJECT** (NOT DEFENSIBLE); keep as a labelled failed lane |
| Launcher B-long (594 m, 6,660 g) | **REJECT** (NOT DEFENSIBLE); keep as a labelled failed lane |
| **Launcher B-modified** (gas-filled strong shell) | **RETAIN** as the only candidate, labelled target physics unproven |
| Fewer, larger pulses (≤ 150 Hz) | **REJECT** (does not fit at 150-100 Hz; V4 does not close at ≤ 60 Hz) |
| Coil case of cryogenic steel | **REJECT** (409-417 kt) |
| Coil case of CFRP at 1.2 GPa | retain as a sensitivity (91-95 kt) |
| Coil case at the FDP-1 TARGET composite, in its own shadow | **RETAIN** (preferred) |
| WC / steel neutron screen | reject in favour of LiH (98 kt against 68 kt) |
| W armour on X-ray faces | **REJECT** for soft spectra; retain only if the spectrum is shown to be at or above 30 keV |
| **CFC monoblock on Mo-TZM Li tubes** (shield rim, coil armour, snout sides) | **RETAIN** (shared technology) |
| Renewable lithium surface (snout tip face) | retain as the fallback |
| S5 as drawn (N6, r 0.29 m) | **REJECT** (0.075 Hz) |
| **N9 longerons in the inter-tank gaps** (R 31 m, r 0.61 m) | **RETAIN** (preferred) |
| N6 corrected (r 0.80 m) | retain as the alternative (2.8-3.1 kt) |

## 6. Mass and geometry changes (research only)

**Mass changes:**
- Coil hardware: +2.0-2.3 kt.
- S5: 2.0-2.2 kt instead of 1.18 kt.
- Launcher B-modified: about 73 t plus a 28 MW sabot catcher and 94 MWe.
- Coupled departure: 68-72 kt against V4's 42.9 kt. Propellant ×1.6, so a 439 m stretch at the same section if drawn (ghost envelope).

**Geometry for T05:**
- the LiH screen on the coil burn faces (0.56 m);
- CFC faces;
- the N9 spine;
- spoked frames;
- the launcher on its own rail;
- the axis plasma channel drawn as a keep-out;
- B, B-long and B-modified as labelled lanes.

## 7. Next work (not started; Revision 4 stops here)

1. **Axis plug concept and D-21 modelling.** This is the blocker for the shield face and the snout.
2. A radiation-transport estimate of the escaping spectrum (it decides W against CFC).
3. B-modified target physics: compression from a gas fill, at T04's level.
4. A closed ship with coil hardware scaling with the pulse (replacing the payload proxy), and the launcher rate cap in the same solve.
5. Conductor mass for the FDP-1 loops (needs an authorised change to protected code, or an adapter term).
6. CFC neutron data at 1,500 K, and REBCO fluence data at 20 K.

## 8. Branches, commits, tests and review files

| Item | Location |
| --- | --- |
| T00 branch | `claude/project-thread-9rsgog` (Rev 4 commit after `e24fc7a`) |
| T00 code and results | `lab/variants/vertex-drive/studies/rev4/` |
| T00 tests | `python3 lab/variants/vertex-drive/studies/rev4/test_rev4.py` (15, OK); Atlas 24 OK; FDP-1 45 OK; four-burn 18 OK |
| T05 branch | `claude/project-thread-ctwplp` (`f6f527d` and its later Rev 4 commits) |
| T05 review file | T05's `work/vertex-blender/` review `.blend`, as named in T05's Rev 4 report |
| Squash | none; nothing goes onto `main` without a separate authorisation |
