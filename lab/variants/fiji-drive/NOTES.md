<!-- lab entry -->
| Lab entry | |
| --- | --- |
| Kind | Variant |
| Status | SUPERSEDED by lab/variants/fdp1 |
| Question | Integrated Fiji Drive v2-v4: can a continuous D-3He core with a magnetic split reach the mission thrust? |
| Model base | main 5a913f9 |
| Salvaged from | claude/project-thread-fefi5d @ 80410fc (same files on 8e13aa), 2026-11-06 |
| Open owner questions | None left; its owner decisions moved to fdp1. Former TODO entry FIJI is kept below. |
| Review | project files review/fiji_drive_2026-11-02/, fiji_drive_v3_2026-11-03/, fiji_drive_v4_2026-11-03/ |

# Fiji Drive revision (owner brief 2026-11-02 21:35Z)

Branch `claude/project-thread-fefi5d` from main 5a913f9 (propulsion detail 5a20073, rings 15a49be, docking 5a913f9 included).
Study files: `fiji_drive.toml` (every PROTOTYPE number), `fiji_geometry.py` (pure geometry, 650 parts), `fiji_budget.py` (physics budget,
writes `results/budget.json`), `make_review.py` (builds `REVIEW_FIJI_DRIVE.blend` and the renders). Nothing in `src/` reads this folder;
on approval the chosen form moves into `src/wayfarer/components/drive.py`, `drive_hot_section.py` and `data/wayfarer_3d.toml`.

## 1. Function

The primary propulsion of Wayfarer: one shared D-³He fusion core whose charged products heat injected hydrogen directly (no electricity
in the thrust path), one magnetic four-way split, four independently trimmed open magnetic nozzles. Electrical power (Brayton bus) runs
only the coils' cryoplant, the neutral-beam and RF heating, the per-nozzle trim heaters and the pumps.

## 2. Fixed constraints (kept, not moved)

- LOCKED/WORKING canon: one core, one common region, one manifold, four channels, four nozzles (`[propulsion]`); four-way magnetic
  manifold with zero plasma pipes; photons, fields and plasma kept as separate layers; HTS coils beneath the Fiji amplification; D and ³He
  metered separately into the core, hydrogen injected downstream of the burn ahead of the manifold; optical A/B gating of lattice
  sectors L1–L4 (lasers, bores, mirrors, heads and gate pads are kept unchanged from main); stepped shield sleeves.
- Stations: core X −121.75…−114.75 (r ≤ 4.6), common −127.75…−122.75, throat −129.25…−127.75 (waist ~2.4 m, Q25), lattice
  −131.45…−129.45, nozzle inlet −136.75, exit plane −144.75 (the AFT datum, nothing aft of it), thrust ring −135.25, shadow shield
  −113.75…−112.75 (r 5.7). Nozzle offset 2.6 m (accepted placement 15!H75), throat r 0.85, exit r 1.75, length 8 m.
- Habitat rings, forward shield, radiators, bulkhead and tanks are not touched.

## 3. Architecture decision

**Kept: one shared core feeding four nozzles through a magnetic split.** Defensible because magnetised plasma follows field lines: a
quadrupole-shaped field divides one flux bundle into four lobes the way a tokamak divertor or a cusp divides flux. Its real costs are
modelled rather than hidden: edge plasma crosses the four X-lines and strikes four cooled **separatrix septa** between the channels
(divertor-like strike plates with the X-point shaping coils inside), and each channel has an **isolation choke** that, driven to full
field, mirrors the channel shut for the channel-loss recovery (isolate, derate the opposite channel, run on the diagonal pair).

**Added: local control per nozzle** (the brief's alternative, used as a complement). Each engine has its own hydrogen **trim injector**
(local mass-flow trim: a few per cent of that nozzle's flow shifts its thrust balance without touching the shared core), an
ion-cyclotron **inlet antenna** (a few MW from the Brayton bus: controls the ions' anisotropy for clean detachment and damps
instabilities at the inlet; electric power cannot meaningfully add to a 52 TW jet, so it is not a thrust stage), and eight **Fiji trim
modules** per expansion coil for field asymmetry (vectoring 5° normal, 8° emergency study, as in canon). Gross thrust split stays with the optical lattice gates (canon); fine balance and fault response are local.

**Core: an asymmetric linear core, not a tokamak.** A field-reversed/mirror-type central cell of six solenoid coils, a strong forward
choke (closed end, high mirror ratio) and a weaker aft mirror (the exit), so the plasma leaks only aft into the mixing cell. Fuel: D and
³He by an axial pellet/gas fueller through the choke and by three tangential ~1 MeV neutral-beam injectors (fuel, heating, FRC current);
ion-cyclotron antennas trim the heating. Tungsten **limiter rings** in each coil bore take the edge contact; there is no continuous first
wall (the shell of main is replaced by limiters plus W/B4C **coil shield inserts**). This is the Princeton direct-fusion-drive principle
scaled up: products leak along open field lines into a cold hydrogen layer and heat it by collisions.

**Mixing cell (the common region).** Three solenoids and the main hydrogen ring (16 radial injectors, X −123.75, the B01 station).
Between the coils, four-segment **Fiji coupling bands** drive field ripple at the products' gyro-frequency so their energy reaches the
hydrogen faster than collisions alone — this is the speculative coupling the brief asks for, and it is the only Fiji claim in the thrust
path.

**Engines (shared parametric design, `engine_coils`).** Per engine: a mount collar with three pinned links (two to the neighbouring
thrust-ring nodes, one to the thrust hub); the trim injector and inlet antenna; a throat coil and five expansion coils in four-segment
casings whose bores follow the WORKING field envelope plus 0.12 m along r = 0.85 + 0.90 u^1.6 (slow at first, then opening: the field
area grows ~4.2× to the exit so the ions turn their gyration into axial speed, and the plume detaches past the exit with ~10° spread);
six tie struts carry each coil's forward magnetic reaction to the collar (≈0.9 MN per strut at the flight thrust, ≈1.2 MN at the 1.5 g
design load; 51–69 MPa in a 0.15 m solid section); Fiji trim modules; a coolant ring per coil and a header; field probe and plume probes.
No bell: the field is the wall, the rings make and hold the field, and the exhaust passes through open rings with daylight between them.
Thrust axes are parallel to X, symmetric about the ship axis, so the resultant passes through the axis (and through the centre of mass
if B02 keeps it on the axis); vector trim, not canted nozzles.

**Open reactor bay.** The hull casing aft of the shadow shield (X < −112.75) is removed in the revision (cut in the review file only):
every surface that sees the plasma must be actively cooled into the hot loop, and an uncooled skin around a 261 TW D-³He core would take
about 1 TW (2.5 % of the radiated power, Monte Carlo, enclosed variant). The primary frames and rails stay and carry the core cradle.
**Conflict:** the casing carried the crawler rails and the drone docks DS-13/DS-14 and units DR-EVA-03/04 inside the bay; in the review
file they are hidden/cut aft of the shield. They need a park position forward of the shield during burns (owner question).

## 4. Physics budget (`python3 lab/variants/fiji-drive/fiji_budget.py`)

### 4.1 The drive as flown today (B01, pass 7)

| Quantity | Value |
| --- | --- |
| Thrust | 21.77 MN (5.44 MN per nozzle) |
| Exhaust velocity | 19,201 km/s (0.064 c) |
| Mass flow | 1.134 kg/s (0.284 kg/s per nozzle); ~0.74 kg/s D+³He reacted, the rest hydrogen |
| Jet power / fusion power | 209 TW / 261 TW (directed efficiency 0.8) |
| Absorbed heat allowed | 10.45 GW at the 4e-5 absorbed fraction (hot-loop drive share 10.80 GW) |
| Burns (four, full return, 0.016 c each) | 0.50–0.64 g (10.0 d), 0.64–0.83 g (7.8 d), 0.83–1.06 g (6.1 d), 1.06–1.36 g (4.7 d) |

### 4.2 The owner's 1.1–1.5 g target

The flown ship reaches the band only in its last burn. 1.1 g at departure (4,426 t) needs 47.7 MN and 573 TW of fusion (2.2× today);
1.5 g needs 65.1 MN and 781 TW (3.0×). Holding today's power instead means ve 8,755 / 6,421 km/s and a four-burn mass ratio of 8.9 /
19.9 instead of 2.7 — not closable. At the end of the mission (1,629 t) 1.1 g needs only 0.81× today's power. **So 1.1–1.5 g is a
lightly loaded ship's figure, not the full-return departure's.** Not changed; documented.

### 4.3 Where the fusion power goes (D-³He, He-3:D 1:1, Bosch–Hale reactivities, relativistic bremsstrahlung)

| Case | Bremsstrahlung | Neutrons (D-D) | Synchrotron | Radiated (not directable) |
| --- | --- | --- | --- | --- |
| Ti = Te = 100 keV (baseline) | 18.4 % | 1.5 % | 1 % (judgment) | **20.9 %** |
| Hot-ion mode, Te = 40 keV | 10.3 % | 1.0 % | 0.5 % | 11.9 % |
| He-3 rich 2:1, Te = 60 keV | 20.0 % | 0.5 % | 0.5 % | 21.0 % |

About a fifth of the fusion power leaves as X-rays and neutrons in straight lines; no magnetic field, Fiji or otherwise, can steer it.

### 4.4 The discrepancy: radiated power against the hot loop

The B01 absorbed fraction 4e-5 (already marked "a requirement on the Fiji drive, not shown physics") is not reachable by geometry:

- **Coils see the plasma.** Any magnetic confinement puts coils around the plasma. Monte Carlo (60,000 rays from the core plasma) gives an
  intercepted share of **0.82** for the revision (coils 0.39, limiters/NBI/fueller 0.17, coil shield inserts 0.10, frames and rails 0.07,
  lattice 0.03, HX 0.016, shield 0.008, blades 0.007, engines 0.005) and **0.995** for the enclosed main-branch bay. At 261 TW that is
  **~45 TW absorbed** (25 TW in hot-ion mode) against 10.8 GW: about 4,000×.
- **Even a perfect design has a floor.** Whatever shields the forward ship must subtend the protected cone. The governing target is the
  thermal bulkhead rim (r 37 m, X 48.9): 12.5° half-angle, 1.18 % of the sphere, so the shadow shield alone absorbs at least
  0.0118 × 20.9 % × 261 TW ≈ **645 GW**, 60× the drive's share of the hot loop.
- **Radiation-limited drive:** with today's radiators the absorbed heat fits at ~**4.4 TW** of fusion in the ideal (cone-only) case,
  0.36 MN, 0.008 g, a ~600-day first burn; with the revision's coil coverage only ~0.06 TW.
- **What 4e-5 would require:** a radiated fraction of ≤ 0.34 % with ideal geometry, ~60× below the D-³He physics above.

The brief forbids letting the lattice remove radiation, so this stays an open contradiction for the owner (decision card in the thread):
(a) keep 261 TW and name an explicit, bounded Fiji radiation property (a canon change); (b) accept the radiation-limited, milli-g drive
(burns of years; the cruise at 0.016 c is unchanged); (c) scale the hot loop by ~60× (ideal) to ~4,000× (as built); or (d) another
fuel cycle (p-¹¹B is worse; D-T is far worse in neutrons). Nothing in the model or canon is changed by this finding.

### 4.5 Shadow shield and dose

- Unshielded at ring A (215 m from the core) the D-D neutrons alone give ~6.6e5 Sv/s at 261 TW. 1 mSv per burn-day needs an attenuation
  of ~1.7e-14: about **3.5 m of LiH-equivalent** (point-kernel, 0.11 m removal length; secondary gammas, D-T neutrons, scatter round the
  rim and transport OPEN). The WORKING envelope is 1.0 m.
- The revision builds the 1.0 m as a layered stack (W hot face 0.05, B4C 0.10, LiH 0.65, W gamma 0.10, steel shell with coolant 0.10)
  with a segmented rim band and a rim coolant manifold. That stack is ~4.5 t/m², ~450 t over r 5.7 m; the habitat dose needs ~650 t or
  more. The B02 shadow-shield mass is "unknown" today; this is the first estimate.
- r 5.7 m at X −113.25 already covers the 12.5° protected cone from every point of the r 2.6 m core plasma (worst ray 4.6 m at the shield).
- The tank farm is forward of the rings, so the hydrogen inventory does not shield the habitat.

## 5. Thermal

All plasma-facing and radiation-absorbing parts (limiters, coil shield inserts and casings, septa, nozzle strike faces, the shadow shield)
are on coolant rings and headers that run to three **drive heat exchangers** in the blade planes beside the blade roots (r 5.45–6.30, X
−120.6…−116.2, edge-on to the core), each feeding its blade root trunk (feed and return) — the drive heat goes straight into the 1800 K
blades, the shortest hot-loop path. The engines and septa collect into an aft ring (X −134, r 4.7) and run forward to the HX. Low-
conductance standoffs isolate the warm coil cage from the cradle; the HTS windings' cryogen stays a separate cold loop (OD-024). No new
radiator area: the existing 1800 K blades are the drive's radiator, unchanged.

## 6. Collections and colours (`REVIEW_FIJI_DRIVE.blend`)

`WORK_FIJI_DRIVE / PROPULSION_FIJI_DRIVE / FIJI_00_DRIVE_STRUCTURE … FIJI_12_VISUALIZATION` (`FIJI_12_VIS_ACTIVE_STATE`,
`FIJI_12_VIS_FIELD_LINES`). Each collection has a parent empty (`FIJI_ROOT_*`; the engines' at their inlet centre). Every object has the
function's viewport colour (`obj.color`; the file opens in Solid / Object colour), `fiji_function`, `role` and `wf_status`.

| Function | Colour | Tag |
| --- | --- | --- |
| Structure | neutral grey | brown (Blender has no grey tag) |
| Fusion core | orange | orange |
| Electromagnetic coils | blue | blue |
| Fiji lattice | violet | violet |
| Plasma transfer | cyan | blue |
| Propellant | green | green |
| Thermal | red | red |
| Shielding | dark grey | brown |
| Diagnostics | yellow | yellow |
| Engine collections | magenta (main propulsion) | pink |

**Conflict with the ship palette (owner brief 2026-11-01, `functional_colors.py`):** there hydrogen is blue, sensors cyan, the warm
radiator orange, He-3 violet and RCS yellow. The drive uses the 2026-11-02 palette; which one wins ship-wide is an owner question.

## 7. Established physics vs Fiji

| Established | Speculative (Fiji) |
| --- | --- |
| D-³He fusion, reactivities, bremsstrahlung, D-D neutrons | Core confinement good enough to burn D-³He at 100 keV steadily |
| Linear mirror/FRC confinement, neutral-beam and ICRF heating | Coil fields well beyond HTS limits (lattice amplification) |
| Collisional heating of cold propellant by fusion products (DFD) | Fast coupling of product energy into hydrogen (coupling bands) |
| Magnetic nozzles (VASIMR, lab experiments), detachment | Clean four-way flux split at hundreds of TW with small septum losses |
| Divertor-like separatrix strike plates, mirror chokes | Lattice trim modules giving 5° vectoring at full thrust |
| Shadow shields, LiH/B4C/W stacks, hot-loop radiators | — (and nothing removes the radiated fifth: section 4.4) |

## 8. Geometry review

`check_review.py` on the saved review file writes `results/geometry_check.json` (639 revision objects, 207 kept ship objects within the
drive bay; the main model's hidden debug layers are excluded).

- **Clashes with the kept ship: none.** 115 ship contacts are all intended and classified in the report: cradle links and the
  spectrometer on the primary rails, septum roots in the thrust hub, engine collars and links on the thrust-ring nodes, the main-model
  H2 lines on the injection ring, the D/He-3 take-offs on the main-model fuel lines, HX tubes into the blade roots, the strongbacks on
  the lattice gate frames, and 61 shield penetrations (rails, braces, feed lines and optical bores pass through stepped sleeves; the
  shield bolts to the spine termination hub). On integration the drive_hot_section D/He-3 terminus moves 0.5 m forward, off the choke face.
- **Floating parts: none** (every part overlaps another or lies within 0.08 m of one). This pass added coil saddles from the mixing
  and throat coils to the manifold cage bars, a guide-coil strongback per channel carrying the isolation choke and the field-control
  modules, ICRF straps that span their coil gap, ties that bear on the nozzle coils, and HX loops routed inside the primary frames
  (radial drop mid-bay, then axial at r 4.75 m, clear of the cradle links and the X-braces).
- Contacts inside the revision (599 pairs) are assemblies by design: coils with their inserts, limiters, trim modules and coolant rings;
  ties on coils; the four engines' links share pins at the thrust-ring nodes.
- **Plume:** nothing enters the 15° half-angle cone aft of any exit. **Engine gaps:** 0.76 m minimum between neighbouring nozzle coil
  stacks (trim modules and coolant included). **Envelope:** every core coil stays inside the LOCKED r 4.6 m. Every object carries a
  functional colour and every collection a colour tag. Non-manifold edges are only the open end caps of curve tubes.
- Passing checks are not engineering proof: coil loads, strut sizing, fatigue and field shapes are not computed.

## 9. Open questions and compromises

1. The radiation discrepancy (4.4): which reconciliation (owner decision).
2. The 1.1–1.5 g target holds only late in the mission (4.2).
3. Shadow-shield thickness and mass: 1.0 m envelope vs ~3.5 m LiH-equivalent; B02 mass.
4. Drone docks DS-13/14 and the crawler rails aft of the shield in an open bay.
5. Ship-wide palette: 2026-11-01 functional colours vs the 2026-11-02 Fiji palette.
6. OD-024 (coil currents, stress, quench, radiation life — now with a quantified heat load on the coil shield inserts), OD-025 (limiter
   and septum heat flux, erosion), OD-026 (feed layout); septum loss fraction; hydrogen trim range and valve response; inlet-antenna power.
7. Neutron transport, activation, streaming through the fuel sleeves and the NBI ducts.

## 10. Overlap with other branches

- `claude/thermal-bulkhead-mechanisms` changes `Radiator_Bulkhead*`: not touched here.
- Hero cameras (rerender after the other branches): `CAM_HERO_PROPULSION` will show the open bay and the new nozzles after integration.
- Propulsion detail (main 5a20073): the revision supersedes the WF_NOZZLE casing detail and services, and the main core liner; on
  integration those `[drive_hot_section]` keys are replaced, not edited in place.

## 11. Files

New: `lab/variants/fiji-drive/{NOTES.md, fiji_drive.toml, fiji_geometry.py, fiji_budget.py, make_review.py, results/budget.json}`.
Modified: none in `src/`, `data/`, `tests/` (the revision is a work study until the owner picks it).

## 12. Drive rows (drafted, not written; written after the owner's pick)

- S&E `15_MODEL_INTERFACES`, new row `OWN-FIJI-DRIVE-REVISION-2026-11-02` (PROTOTYPE, owner review): asymmetric linear D-³He core
  (forward choke, aft mirror, limiters, coil shield inserts, 3 tangential NBI, axial fueller), mixing cell with Fiji coupling bands, kept
  four-way magnetic split with four cooled separatrix septa and per-channel isolation chokes, four open magnetic nozzles (throat + 5
  expansion coils, flare u^1.6, six tie struts, 3-link pinned mount, H2 trim injector, inlet antenna, 8 Fiji trim modules per coil), open
  reactor bay aft of the shadow shield, drive HX into the blade roots, layered 1.0 m shield.
- S&E `15_MODEL_INTERFACES`, new row `OWN-FIJI-RADIATION-BUDGET-2026-11-02` (OPEN, owner decision): D-³He radiates ~21 % of fusion power
  (18.4 % bremsstrahlung, 1.5 % D-D neutrons, ~1 % synchrotron at 100 keV); the protected 12.5° cone alone sets a floor of 0.25 % absorbed
  (645 GW at 261 TW); as modelled 0.82 × 21 % ≈ 17 % (45 TW). The B01 4e-5 needs ≤ 0.34 % radiated. Options (a)–(d) of section 4.4.
- Fiji workbook, propulsion rules: a line that the lattice "does not remove bremsstrahlung or neutrons" (the brief's boundary) next to the
  existing photon/plasma boundary (`photon_plasma_boundary`, LOCKED) — only if the owner picks (b), (c) or (d); (a) changes it instead.


## Former TODO entry (branch fefi5d)

- [ ] **FIJI — Integrated Fiji Drive (owner briefs 2026-11-02 v2, 2026-11-03 v3), study in `lab/variants/fiji-drive/`, owner review.** v3
  (`lab/variants/fiji-drive/v3/REPORT.md`, `integrated.py`, `CONCEPT_FIJI_V3.blend`): neutral radiation (brems + D-D neutrons, 10-33 % of
  fusion power) sets a first-wall flux limit P <= 2 pi R L q / f_neutral; the best coherent drive IFD-1 (one open-cage core aft of the
  hull, one axial nozzle with 4 trim sectors, W armour on Li heat pipes into the 1800 K loop, layered shadow shield) reaches ~0.15 TW /
  0.23 mg against 261 TW today and 739-1,008 TW for 1.1-1.5 g. **Owner decisions:** mission redefinition (power-limited milli-g, or
  another fuel/drive class), canon topology change (1 core -> 1 axial nozzle), ~60-75 m aft lengthening, ~4.4 kt drive mass into B01,
  ship-wide palette (Nov-1 standard used). v4 (owner 2026-11-03 11:55Z, `lab/variants/fiji-drive/v4/REPORT.md`): independent recheck lowers IFD-1 to 0.082 TW
  (e-e brems, coil sides, safety factor; 1,587 y burn with the complete 21.8 kt ship); pulsed point-burn IFD-P (fuel-only rhoR 111 g/cm2
  targets, stand-off heavy-ion driver, three Fiji loops at 170-1,000 m, one nozzle with four vectoring sectors) reaches 5-10 TW, 54-327 y;
  both miss the mission (ship heat must stay below 3.7e-5 of fusion power). **Done when:** the owner picks a direction; then canon rows and generators follow.
