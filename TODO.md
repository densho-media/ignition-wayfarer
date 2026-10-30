# Wayfarer implementation plan

## Goal — Wayfarer Review Release 1 (WF-R1)

Deliver one source-grounded spacecraft model and a matching playable/cinematic experience ready for a proper whole-project review:
exterior and inhabited spaces, the two induction characters, boarding and ring transfer, local crew physics, navigators, defense,
maintenance drones, EVA training, and the HR-001 heat-recovery study. Integrate the owner-released mass, thermal, survival and mission
inputs needed by those features. Review the whole ship, assemblies and human scale together, with reproducible evidence.

**Implementation complete** means every required step below meets its acceptance criterion. **Review accepted** additionally means
step R03 has explicit user/owner acceptance and no unresolved blocking findings. A required step waiting for owner data remains
incomplete; an UNKNOWN label or a passing simulation cannot close it. A partial prototype review may happen earlier but is not WF-R1.
Nonblocking engineering unknowns may remain only where the feature's stated maturity permits them, with their consequences and HOLDs
visible in the final review. No real spacecraft certification or automatic L5 qualification is claimed.

Scope: the existing standalone Blender/Godot project, its approved prototype studies and production presentation. No new runtime,
full filmed series, six-crew character production or optional web deployment. Physical operation of flight EVA remains HOLD until its
owner gates release; the review release includes the honest training experience. Comprehensive material/FEA qualification is required
only where an owner release or the accepted feature needs it. Scope changes require an explicit decision, never silent task deletion.

The dated [project overview](references/PROJECT_OVERVIEW_2026-10-16.md) records the starting assessment (~55%, judgment only).
Do not derive completion from the number of checkboxes: steps vary greatly in effort and risk.

## S — Primary focus: complete the spacecraft (user brief 2026-10-18)

Development effort moves from new Godot features to the ship itself; keep the walk and Explore Ship working
(maintenance fixes only; the other Godot scenes were retired 2026-10-29; commit 038ae90 holds them). Two coordinated tracks: A science/systems through the owner workbooks, B Blender/interactive production;
unresolved science blocks only irreversible steps. Each slice: validate the changed assembly and interfaces, whole-ship view plus a
close-up, regression check, MODEL/TODO and Model Status update.

- [ ] **P4 — Phase 4 visual production and art direction ([docs/PHASE4_PLAN.md](docs/PHASE4_PLAN.md)). PRODUCTION 2026-10-24:
  S1 art gate passed (owner selected VC+ Expressive Hybrid, moderated values; Art Style Spacecraft row 19); S2 done; S3 (M8.2), S4
  (ring exteriors), S5 (radiator frames), S6 (spine casing, `spine_casing`) and S9 (library coverage, ram face, wear layer, ship name,
  runtime grammar), S8a (ring B transfer, crew tube and sector 2 in the M7 grammar, `ring_b_transfer`) and S10 (hero set,
  `presentation/p4_hero.py`) and S11 (runtime package, sharing and llvmpipe frame-time records, whole-ship review sheet) BUILT,
  owner review.**
  The grammar is
  `[production.exterior]` (families, tiers, marking scale, accent budget, ship-material mapping) with the grammar look
  (`hero_preview.dress(grammar=True, wear=)`), the runtime exterior (`look.exterior.grammar`) and the review set
  `presentation/p4_review.py`. **Open:** desktop-GPU and web frame-time measurement on the owner's machine (`profile_views.gd
  --hide-assemblies RA.EXT,RB.,SP.` and `--look 1/2/3`); S8b zones after their
  whitebox and cultural reviews (Z1 Garden/mess `ra3_garden`, Z2 work/medical/ops `ra2_work`, Z3 berths `ra1_berths`, and ring B's three
  sectors by one definition `rb_fitout` BUILT, owner review); S7 waits on engineering releases. **Owner review:** the ram-face look and the wear layer (P4-LOCKED (b), P4-STATE) with the other candidates. Every new asset
  stays `L4_VISUAL_CANDIDATE` until the owner reviews it; nothing reaches `main` without the owner's squash approval.
  **Done when:** the plan's S11 whole-ship review is accepted by the owner.
- [ ] **FSH — Fractal shielding on the Brow's ram faces (user brief 2026-10-27), BUILT as shading, on main (owner squash 2026-10-29).** The
  hexagonal plate and Sierpiński pattern (`[production.exterior.fractal_shield]`, docs/MODEL.md) replaces the S9 running-bond ram tiles by
  default in the Blender grammar look, the walk and Explore Ship. **Open:** `runtime-check excursion`, the Blender grammar stills
  (`p4_review.py` ram_face, ram_close) and a desktop-GPU frame-time comparison of the Brow view with `pattern` fractal_hex against running_bond.
- [ ] **MOD — Modular detail (docs/MODULES.md).** Every production assembly is a detail pack (phase 2, 2026-10-23: `m7_spine`,
  `ring_a_transfer`, `m8_forward` migrated with geometry, motion, runtime and pixel equivalence), packs carry their own contracts, and
  approved authored meshes travel as committed glTF data; each ring is its own engineering asset (phase 3, `WF_HABITAT_A`/`_B`).
  `assembly validate` passes for all six packs.
  - **Candidates (owner S1 art gate 2026-10-24):** `rad_frame` revised in Phase 4 S5 (frame rhythm by value: `BladeFrame` → `xf_frame`;
    PHASE4_PLAN section 4.6), awaiting owner review; `ra2_equip` RETAINED as designed, owner acceptance pending (before/after close-ups
    delivered 2026-10-24); both stay `L4_VISUAL_CANDIDATE` until accepted. M8 is under its own entry below.
  - Deferred: a linked part library for repeated fittings, until a detail pack repeats one detailed form often enough that measured sharing
    pays (the export already shares identical meshes; RAD.FRAME's three blades share one mesh).
  **Done when:** the owner has accepted or replaced the candidates.

- [ ] **M8 — Exterior production identity. M8.2 BUILT 2026-10-24 (Phase 4 S3, the owner's REVISE of M8.1), awaiting owner review.** The accepted M7 standard on the
  exterior as `[production.m8]` (its own switch and maturity). M8.1: the Brow aft face (`M8.BROW.AFT`) and the Aegis Crown rim
  (`M8.CROWN.RIM`, all 12 bays after bay 1 passed its gates), all `L4_VISUAL_CANDIDATE`. Report and evidence:
  [M8_EXTERIOR_2026-10-20](references/M8_EXTERIOR_2026-10-20.md) (off-diff empty, 0 BVH clashes, r 45.0043 m, runtime-export 31/31,
  exterior +0.22 ms within noise; stills `runs/20261020T1445Z-m8-stills`).
  - **M8.2 (S3, PHASE4_PLAN section 4.4):** lane deck with blue boundary lines and graphite trays, calm cladding fields, light Crown
    panels on the graphite housing, markings sized for their distance; evidence `runs/20261024T-p4-s3`. **Owner review:** accept, correct
    or reject M8.2. The ram-face tile-and-repair look moves to S9.
  - Physics-locked: radiator hot faces, drive and nozzles (Q40), EYE apertures, the Dust Lance field, docking (Q33), EVA rails (RUN-011),
    livery (GU WAYFARER 001 stays provisional, 15!A216/A225). No access, rescue or pressure-boundary geometry.
  - Left over from M7: disposal of the original 869 MB capture `runs/20261019T1245Z-m7-walkthrough` waits on the owner.
  **Done when:** the owner has reviewed M8.1 and the agreed next module is built behind the same switch with the same gates.

- [ ] **M6 — Interactive subsystem expansion (owner 2026-10-19, S&E 15!A220 / 15!A227, 98!A121). PRIMARY presentation track.**
  M5 is closed: the owner accepted the hologram look and grammar as the preferred production direction (15!A220). The decisions of
  2026-10-19 are consumed in [OWNER_RESOLUTION_2026-10-19](references/OWNER_RESOLUTION_2026-10-19.md).
  - **Built:** the first M6 deliverable ([report](references/M6_HOLO_2026-10-19.md)). Chapters 6-8 of the same hologram scene:
    - EYE / Dust Lance / shield poses with the shadow test;
    - counter-rotating rings with lock and a crew walk;
    - radiator steps, damage and isolation.
    The report includes the discrepancy table.
  - **Left:**
    - the owner's optional hands-on review;
    - a user-visible clip at the milestone;
    - the next bounded chapters only after review.
  - **Not here:** the owner science track computes coupled fuel, engine, mass and heat in Sheets (15!A227). Claude canonizes none of
    those numbers.
  - Study states kept from M5, each a reversible L2 study with its numbers OPEN in the owner registers:
    - **Attitude and comms (15!A210/A211):** link budget, disturbances, dust limit and momentum storage OPEN.
    - **Nozzle supports (15!A214/A215, 15!A226):**
      - F8 into the central hub / spine and the sector trusses is the preferred topology;
      - load shares come only from FEA or a rigorous hand balance with joint stiffness;
      - the 0.20 m yoke standoff and the bore growth stay L2 comparisons;
      - next, when asked: parameterized joint stiffness, full 3D load cases and a readable cutaway.
    - **Aft robotic service (15!A213, 15!A225):** HGA gimbal ORU (0.88 m tool access) and the third cradle at 210 deg are the
      preferred studies. No HGA tool rating, no cradle build.
    - **BODY-C3 (15!A224):** the preferred L2 storage study. Deficits -1,752 / -4,294 m3 kept. No WF_STORAGE install, no wet-mass
      rebalance.
    - **Lettering (15!A225):** L1 GU WAYFARER 001 preferred, L2 the comparator. The project title is "G.U. WAYFARER 001" (the
      Y155 Great Union; the G.U.C. is founded in Y310, so it never names this ship).
- [ ] **S01 — Whole-body internal architecture (BODY-001). BUILT 2026-10-30 as PROTOTYPE (FUEL-SPLIT, WORKING), owner-accepted 2026-10-30.**
  `fuel_storage.py`, `components/storage.py`, `[fuel_storage]`: He-3 in 27 lobes of nine BODY-C3 stations, H2 and D2 in a torus behind the
  Brow split into three vessels (gaps at 50/195/315 deg keep the EVA azimuth and keel lanes clear), transfer lines over the bypass
  collar into the hull at X 80.02 and along the keel lanes to the four feed run tanks (the schematic `Tank_Volume_0n`, renamed
  `Feed_Run_Tank_0n`). Fit-screen margins He-3 +1,690 m³, D2 +65 m³, H2 +416 m³ at 3 % ullage. **Open:** the hull penetration, boil-off
  and cryocooler power, torus support loads, MLI. **Done when:** those owner inputs are released and applied.
- [ ] **S02 — Essential external hardware. READY where placement is independent of S01.** High-gain RF and laser comms, RCS clusters
  and tankage, star trackers and navigation sensors, position/warning/service lights, docking guidance and proximity sensors, EVA
  handrails and tether anchors along the maintenance routes, service panels. Size from bounded requirements (link budget, control
  authority, field of view); check ring sweeps, radiator/plume exclusions and the shield shadow before placing; each part with a
  function and a placement reason (S&E 37 F14–F17). **Done when:** reusable assemblies are built and inspected and a placement report exists.
  Slice 1 built 2026-10-18 (`exterior_hardware.py`, `components/exterior.py`, `[exterior_hardware]`; quick run
  `runs/20261018T065938Z-quick`, 27 added, 0 unexpected): docking targets, alignment lights and proximity sensors at both ports (below
  the corridor base, outside the capture rings, screened), airlock floods, rim and aft position strobes. Slice 2 built 2026-10-18 (report
  `references/S02_COMMS_RCS_2026-10-18.md`): two 4 m Ka dishes and a 0.5 m optical terminal aft of the blades, three aft and four
  rim RCS pods, all screened; sizing is a PROTOTYPE bounding case (owner rate, band, thrust and flip time NOT FOUND). Left: the owner's
  answers to the slice-2 questions; momentum storage (CMGs) inside the BODY-001 equipment bay once S01 is built; slice 3 (2026-10-29,
  owner review): three primary star trackers with coarse sun sensors at X 20 m, screened; lights' look pass done 2026-10-29
  (beacon and approach light classes); the service panels are the S04 casing access covers (ochre, S03). Slice 4 (2026-10-30, owner-accepted): the guided-EVA handrail on standoffs along `eva_route` at the airlock azimuth, tether anchor rings and two
  foot restraints on the forward collar (`exterior_hardware.eva_rails`, ochre); still a training fixture (EVA-048 HOLD, 44 RUN-011).
  Momentum storage built 2026-10-30: six CMGs on the body utility frames (`body_equipment`, PROTOTYPE sizing). Left: the owner's answers
  to the slice-2 questions.
- [ ] **S03 — Whole-ship material library and visual identity (Art Style Bible).** Structure, casing, insulation, hot radiator faces,
  cryogenic systems, optics, shielding, GU markings, maintenance zones; before/after hero renders.
  Slice 1 2026-10-18: the S02/S04 parts take the accepted M4 grammar (15!A202, 98!A112, Spacecraft!A16): ochre covers, dark
  joints and nozzles, off-white dishes and target (`look.exterior.functional_materials`). PARKED on the owner: the exterior stays proxy grey
  (15!H120) and the Drive gave no spacecraft palette, finish, GU marking, registry lettering or nav-light colour (reader 2026-10-18).
  Unparked 2026-10-24 into Phase 4 S9: the owner released a depiction-only PROTOTYPE family library and text-only markings (Art Style
  Spacecraft row 18, S&E 15 OWN-P4-LOCKED); its balance was selected at the S1 art gate 2026-10-24 (row 19), codified in S2
  (`[production.exterior]`) and completed in Phase 4 S9 (coverage, ram face, wear layer, ship name, runtime parity), with the S10 hero
  set. Remaining: the owner's review. The COAST exposure stays the owner's call (C01).
- [ ] **S04 — Construction detail across the remaining ship (M4 method).** Casing and access panels, drive section, thrust ring and
  nozzles, shield assemblies, internal framing and equipment mounts; L2 → L3 → L4 per assembly.
  Slice 1 built 2026-10-18 (`casing_panels.py`, `[casing_panels]`): aft body casing joint straps at the frame stations, longitudinal
  straps and access panels beside the keel lanes, screened. Slice 2 (`forward_shield.brow_panel_joints`): the Brow's replaceable-panel
  joints on the skin's aft face (owner allowance 15!G202). Slice 3: forward collar straps broken round its openings and aids. Slice 4: thrust-ring node diaphragm plates. Left: drive section (physics-locked
  magnetic nozzles, Q40: no validated shell to detail), thrust ring and nozzles, further shield
  assemblies, internal framing and equipment mounts. Slice 5 (2026-10-30): cryocoolers on every fuel station and lobe hangers to the
  frames (S01). Slice 6 (2026-10-30): internal ring frames in the body module gaps, utility-frame beams (equipment mounts) and the
  thrust ring's bay splice sleeves. Left: drive section (physics-locked), nozzles, further shield assemblies.
- [ ] **S05 — Working interiors.** Workshop and fabrication, medical, operations/navigation, life support, cabins, storage and repair,
  Garden; connected to the traversal system, inside the pressure, rotation, thrust-gravity and evacuation rules.

## How to work through this plan

- A01–A03 are done (capture 2026-10-16, full pipeline and runtime export PASS). **Primary focus: S** (the spacecraft). Select one step per implementation slice; the plan itself does not start all steps at once.
- Studies named `studies/<name>.py` below are retired: `git show 038ae90:src/wayfarer/studies/<name>.py`
  restores one into `work/<task>/` when its entry is picked up (AGENTS.md "Where things go").
- IDs remain stable when entries are removed; do not renumber. Only unfinished work stays here. On completion, put current behavior in
  `docs/MODEL.md`, evidence in the existing relevant review, and remove the entry. Git and `references/` retain history.
- Dependency IDs refer to acceptance evidence even after a completed entry is removed. A later phase may proceed when its own
  dependencies are satisfied. Numbering is the preferred order, not a requirement to idle behind an unrelated owner answer.
- Keep two primary tracks: **owner science** and **local production**, plus at most **one bounded architecture study**. Finish or park
  that study before starting another. Rescue, HR, EYE and drone architecture do not become four simultaneous studies.
- Status meanings: **READY** = actionable now; **AFTER IDs** = local prerequisites; **OWNER** = named release/review is required;
  **PARKED** = explicitly outside the current critical path. A step can contain preparation that proceeds before its owner gate.
- Every slice uses the existing AGENTS.md loop and selected checks. Geometry: scoped quick pipeline, expected prefixes and affected
  interface inspection; review whole-ship previews first. Full pipeline before a geometry-changing commit; accept only intended full
  results. Runtime: check a current package, export when stale, inspect the three runtime views after visual changes. Docs need no tests.
- Work on main, preserve ART and backups, one build writer. Commit only when asked. Pruning remains a separate user-approved action.
- Sheets owns physical calculations. Unsourced choices remain PROTOTYPE and unknowns remain `known = false`. No model measurements
  become canon automatically. S&E 27–31 remain HOLD / DO NOT REBUILD: no engine, ship-size or radiator redesign from those studies.
- Owner questions are batched root-impact decisions (S&E 48 WF-009..017), with timestamp IDs and existing queue threads reused.
  Any Drive write needs user authorization; completing a local step does not itself authorize posting or deleting correspondence.

## B — Obtain the science inputs that control shape and operation

These are owner tasks with local measurement/import support (WF-003, SIM-031). Reuse the posted P0 packet
[references/P0_SCIENCE_REQUEST_2026-10-14.md](references/P0_SCIENCE_REQUEST_2026-10-14.md), Doc 2026-10-14T12:12.
Reversible production work in C can proceed while these wait.

- [ ] **B01 — Release a bounded mass/fuel/drive-heat scenario. OWNER; AFTER A01.** Request or consume one WORKING operating point,
  or explicitly released bounds: reaction mass, fusion fuel/He3 load, operating thrust and actual absorbed drive heat, with compatible
  assumptions and units. Provide requested geometric measurements only. **Done when:** owning rows supply a consistent scenario
  usable for packaging; imported values preserve status. The 16 GW calibration / 14.4 GW ideal rejection / −1.60 GW diagnostic margin
  is not an operating heat release. 2026-10-17 (15!A200 OWN-SCI, 98!A114): still no release; only source-tagged parametric
  envelopes (default UNKNOWN), model tank-bay volumes and centroids may be measured; flight playback stays SIMULATION_ONLY.
  Measured 2026-10-17 (`studies/tank_bay_survey.py`, `references/TANK_BAY_SURVEY_2026-10-17.md`): 9,773 m³ free annulus forward of
  the engineering envelope, 9,256 m³ in one bay X −57.5…81.3 m; the bay allocation question is posted with the B01 thread. 2026-10-18 BODY-001 (S01) compares three packagings; its BODY-Q1..Q3
  carry the storage-target, fuel-load and tank-mass questions.

- [ ] **B02 — Release mass allocation, power and shielding interfaces. OWNER; AFTER A01; reconcile with B01.** Obtain mass positions/CG,
  non-additive subsystem budgets, whole-ship electrical loads and coast/survival generation, shield stack and ring-water/storage
  distribution. Include load-path and protection assumptions that could change the silhouette or occupied spaces.
  **Done when:** the in-scope packaging interfaces have owner values/bounds, no double counting and an explicit list of still-unsized
  details. Use `physics.mass_distribution`, `power.rating`, `forward_shield.stack` and S&E 10/13/17/37–41.

- [ ] **B03 — Import authoritative flight and thermal histories (FUT-001). OWNER; AFTER B01.** Consume released frames through the
  existing importer: twelve time-tagged channels and two phase/event streams, including acceleration and the First Ignition heat clock.
  **Done when:** applicable released channels drive Blender/Godot consistently and provenance is verified; required missing channels
  keep this step open. Do not replace the 1-D route with an invented solution.

- [ ] **B04 — Release absolute mission/navigation data. OWNER; AFTER B01.** Obtain epoch, heliocentric frame, absolute 3-D states,
  ephemerides and timed Kuiper/return events through S&E 22–26 and 50; 25 rows 14–21 are currently OPEN.
  **Done when:** the owner validation gates support the intended journey, Kuiper maneuver/resource assumptions and six-year return;
  data is ready for J03. This does not authorize a local mission solver.

## C — Finish the existing production milestone before expanding it

- [ ] **C01 — M4 final render signoff. OWNER REVIEW.** Direction answered 2026-10-17 (S&E 15!A202, 98!A112, Art Style Spacecraft!A16):
  the construction grammar is accepted for the continuing model; red/yellow root colours are a review legend only (applied: datum and
  slide mounts grey, Godot inspector key L draws the legend); IGNITION keeps physically plausible 1800 K emission, hierarchy by
  silhouette/framing/exposure; COAST off-burn carries the ordered shield/Crown/rings/radiator/drive read. Matched IGNITION and COAST stills
  of the current model: `runs/20261017T1200Z-m4-burn-coast` (`hero_preview.py --state COAST --functional`). Left: owner inspection of
  those images and the next shield-rear slices. 2026-10-19 (15!A222, 98!A123): matched pair kept as the comparison truth; COAST editorial
  stills `runs/20261019T0800Z-m4-c01-editorial` (`--editorial-ev`, +1 and +2 EV; +2 selected, no clipping, emission unchanged, captioned
  "COAST — +2 EV editorial exposure, not comparable brightness"). Left: owner inspection of the final stills.
  **Done when:** the owner signs off the final views; no render is marked approved unseen, concept fill stays labelled ILLUSTRATIVE.

- [ ] **C02 — Review Ship/Space Navigator and defense text. OWNER REVIEW; AFTER A03.** Review six Ship WHAT/WHY/SHOW ME cards,
  instrument appearance (NAV-018), Space chart/legend/line styles (SPACE-033), DRAFT WHY wording and celestial lore scope
  (Tale NAV-TOUR-11), and AVA PHYSICAL/EXPLAINER wording. **Done when:** reviewed wording and visuals are applied, provenance and
  LIVE/PREVIEW/SCHEMATIC/UNKNOWN/HOLD disclosures remain intact. No extra hotspots without a purpose/source.

- [ ] **C03 — Complete outstanding hands-on reviews. AFTER A03; repeat affected parts after C01/C02.** Review the walk (both rings, desktop,
  web and phone; J06) and Explore Ship's picking and styles. The 13 October M1/M2 user run is
  existing evidence, not a request to repeat unchanged work. **Done when:** remaining interactions have recorded human review,
  reproducible findings are fixed and affected checks pass. Scripted screenshots alone do not establish hands-on acceptance.

## D — Resolve the coupled rescue and service architecture (M3 / ACCESS-005)

Use `studies/access_integrated.py`, `references/ACCESS_INTEGRATED_2026-10-11.md`, `SHEETS_INPUTS_2026-10-11b.md` and
`RESCUE_REPLY_2026-10-14.md`. Current result: no chain passes; Ring B care 0/24 (the six Garden passes needed Garden_Rack_1 removed, which 15!A174 keeps; composer
re-run 2026-10-16), Ring A −0.171 to −0.455 m, 31/32 closures unqualified.
The earlier Garden 24/24 was a zone screen only. No pressure cutout, port, guard, pin, mass or rating is released by these studies.

- [ ] **D02 — Prove Ring A/B care and transport coverage. READY (D01 answered 2026-10-17, 15!A197:A198, 98!A109).** Owner rules:
  no routine nonambulant transfer under locked 1.5 g (burn-couch stabilization, transfer after a safe thrust reduction; hold time and
  trigger HOLD); Ring B in-sector care 0/24 with Garden_Rack_1 kept; ring A is a FAIL comparator, its port and spin-port turn a
  reversible L2 whitebox (`studies/ringa_port_whitebox.py`, 2026-10-17: a deeper chamber gives unsuited annulus legs MARGINAL +0.012 /
  +0.033 m; with the 0.40 m chamber, the trunk ladder / arrest rail joggled or cut clear of the port bend lift A1 / A2 / A3 from about
  −0.10 to −0.033…−0.050 m (still FAIL), and a couch-side transfer space (Lab_Bench relocated) removes the Medical_Couch limit, so best
  RA_D40_CL_CS is unsuited +0.033 m on the annulus legs, −0.046…−0.050 m on the trunk legs, suited FAIL −0.114…−0.169 m; third pass
  RA_D40_CF100_TR_CS (cut 1.00 m above the port incl. trunk handrail 2, tube floor-ladder-2 arrest rails folded): A1 unsuited MARGINAL
  +0.012 m, the spin-port turn −0.013 m and suited A2 / A3 −0.165…−0.169 m both set by the 1.60 m port rim; suited needs a port wider than
  the trunk, i.e. a trunk-side flare). Owner 2026-10-19 (15!A221, 98!A122): no suited ring-A passage in the baseline (in-place
  stabilization), no flare, fold-away ladder / rails study only until fall-arrest continuity is proven; ring A stays a FAIL comparator.
  B3H2 links <= 0.206 m, 0.207–0.213 m only as sensitivity. Study selected limiting segments and care arrangements across
  all occupied sectors, gravity/lost-ring states, patient/carrier/attendants/kit variants. Preserve full-length support requirements.
  **Done when:** the integrated coverage matrix meets the owner-selected requirements, including failure contingencies; outstanding
  FAIL/MARGINAL keeps the relevant route open. Current best 1.5-g aid still fails Garden by 0.066 m; furniture alone is not closure.
  2026-10-30 re-run of the casualty sweep on the current model (`references/evidence/d02_coverage_2026-10-30.md`): ring A sector 1 and
  sector-to-sector legs MARGINAL, sectors 2/3 and the refuge legs FAIL at the crew port and trunk; ring B only the staged mattress to
  sector 2's hatch (MARGINAL +0.001 m). Open: the in-sector care screen, bend limits, 1.5 g and lost-ring cases.

- [ ] **D03 — Establish an independent SP-13 exit. OWNER (pressure architecture).** Study done 2026-10-16: refuge gallery outside
  the trunk (`studies/d03_sp13_gallery.py`, `references/D03_SP13_GALLERY_2026-10-16.md`): U/A/K PASS, S MARGINAL +0.021 m; no single
  fault in the studied cases leaves SP-13 without an exit. Owner 2026-10-17 (15!A199, 98!A110): the side gallery is the preferred L2
  TOPOLOGY STUDY (no cutout, not an installed pressure facility). Next: model the pressure volumes and two distinct closures; compare a
  shielded stepped/offset dogged refuge closure with an isolation antechamber (storm shielding not weakened); jam and depressurization
  single faults; carrier and swept-ladder sweeps; 1.5 g steep/shaft portions as ladder + protected fall arrest + hoist-only casualty
  carrier; positively dogged leaf versus guided parallel plug; 80 kPa both polarities as analysis input. Original scope: Follow S&E 15 A177/A178:
  compare a destination/bypass outside the shared single trunk, with pressure partition and jam-tolerant dogged closure. Include
  opposite-side operation, complete carriers, manual recovery and single faults. Reuse `EVA3_SP13_L1A_REDLINES.md` and
  `studies/eva3_sp13_l1a.py`; SP-12 N2 fwd45 is only MARGINAL +0.044 m and a jam blocks SP-13 by −0.373 m.
  **Done when:** selected topology gives independent usable egress under the required fault cases and owner approves any changed
  pressure architecture. Nominal 80 kPa both ways is an analysis input, not an approved door rating.

- [ ] **D04 — Close SP-11/SP-12 and forward-district access. AFTER D03 and applicable D01 loads.** Complete the 1.20 m sliding-plug,
  limp-casualty, transfer/hoist, one-handed and fault cases. Carry L1-A 205/210° and CB2J6 stile through the full route and load review;
  its +0.064 m geometric result does not qualify its S-bends, knees or tether load. Sources: `EVA3_REPORT.md`,
  `EVA3_SP13_L1A_REDLINES.md`, `L1A_STILE_2026-10-13.md`.
  **Done when:** selected access and pressure boundaries satisfy their required sweeps and released loads, with owner approval for
  production changes. Only then build the hollow shirt-sleeve SP-12 entrance and service-district access.

- [ ] **D05 — Close thrust steps, arrest and closure families. OWNER; AFTER D01–D04 as affected.** Resolve B3H2 newcomer +0.049 m and
  always-held grip +0.030–0.033 m margins without relaxing the 0.05 m study target; links above 0.206 m remain candidates until rated.
  Apply released closure-family two-way loads, seals/isolation and recovery requirements, including refuge egress/rotary interfaces.
  **Done when:** required actor/kit transitions and pressure/fault cases pass at the stated maturity; no family retrofit before
  owner qualification. Sources: `CHAR_STEP2_HATCH_STEP.md`, S&E CLOSURE-005 / OD-034–040.

- [ ] **D06 — Integrate selected access architecture. AFTER D02–D05 and required owner releases.** Move only selected forms into
  shared formulas/generators, preserve route/pressure interfaces, update the integrated chains and readback.
  **Done when:** affected build/inspection and complete required route cases pass, visual/human-scale review is complete, and MODEL
  distinguishes installed geometry from studies. No final fit-out on a failing rescue path.

## E — Implement HR-001 as one bounded L2 study

Dependencies: A01 and the architecture-study slot. Does not wait for a fictional numeric performance claim; geometry may be PROTOTYPE.
Source handoff: Model Status Heat Recovery Implementation HR-P00..19; S&E HR-001..004 / OD-041. Reuse existing Brayton A/B and all
four nozzles; preserve hot/warm/cold loop separation, fixed radiators, core and cryogenic tanks.

E04 accepted 2026-10-17 (15!A203, 98!A113): candidate B is the preferred L2 packaging study (fail-to-BYPASS, Brayton A/B and the
original H2 line kept); HR-F09..F11 replay the owner's register S&E 39!A32:I36 (`studies/hr001_states.py`). The first owner physics
packet (Q_src, T_src; H2 mdot, p, T, phase, enthalpy in/out; field/plume/dose keepouts) is an F02/F03 input; energy and flight HOLD.

## F — Integrate physical systems from released inputs

- [ ] **F01 — Package fuel/reaction mass and structural/shield consequences. AFTER B01/B02.** Build sourced tank volume envelopes,
  feed/service/thermal clearances and mass-placement interfaces. Apply released shield layering/water distribution and consequential
  spine, ring, collar and thrust load-path changes through owner-approved designs. **Done when:** installed envelopes and source
  budgets agree, service routes fit, affected interfaces pass, and remaining unsized members are clearly bounded. No speculative
  acceptance of the held linear-engine/size studies; no additional mass hidden in proxy details.
  2026-10-30: the volume envelopes, feed lines and cryocoolers are built with S01 (PROTOTYPE); masses, loads and the shield/water
  consequences still wait on B01/B02.

- [ ] **F02 — Close warm/cold cooling and SP-52 packaging. OWNER; AFTER B01/B02 and D04 for service access.** Obtain view factors,
  loads and selected baffles/routing, then build the required warm/cold equipment and rejection surfaces. Re-screen the built warm
  panels; no credited area/capacity from hot-facing casing. Reuse Q38 (40 F68), `SERVICE_HOST_SURVEY.md`,
  `SERV002_FORWARD_DISTRICT.md`, `SP52_SENSITIVITY_2026-10-13.md`; low-e + shield is a study candidate, not installed wall protection.
  **Done when:** owner heat balance supports the selected interfaces, geometry/service separation is checked and the required
  capacities are imported. Keep all three loops separate; incorporate HR only with released accounting.

- [ ] **F03 — Integrate electrical, black-start and survival power. AFTER B02/F02.** Size/place owner-released A/B distribution,
  storage, survival reserve and drive-off generation; preserve category suballocations and failure domains.
  **Done when:** required operating/black-start/failure states consume sourced budgets and endurance, with matching geometry and
  presentation. Finite batteries alone cannot become a six-year energy source.

- [ ] **F04 — Resolve radiator expansion and material-dependent interfaces. OWNER; AFTER B01 and thermal/material release.** Reuse
  `RAD004_FRONT_DATUM_COMPARISON.md` (CALC-R07, OD-039, SIM-028); compare wider seams/bellows, shadow/collision and actual net-area
  consequences only when the owner thermal case exists. Include truss temperature, material gradients and root/support interfaces.
  **Done when:** selected owner-released construction passes affected thermal-growth/geometry checks and its real area is retained
  in the shared data. No provisional datum/root move or radiator shrink to fit a visual/runtime budget.

## G — Complete habitat, survival and service implementation

Owner scope: S&E 12A, 33–39, 41–42, existing room/recovery reviews. The 42 equipment groups and 32 survival groups overlap; map each
physical item once, reuse existing envelopes and do not fund components twice. No automatic factory or mining hardware release.

- [ ] **G01 — Complete the equipment-to-space and resource allocation. AFTER B02; coordinate D/F.** Map owner-required ECLSS,
  refuge, food/water, waste, medical, comms/attitude, repair and stores to existing spaces, mass owners, utilities and service paths.
  Use existing source/readback tables, not a new tracking framework. **Done when:** each in-scope requirement has a released installed
  allocation or a named unresolved owner gate; actual missing hardware is split into bounded steps G02–G04 before modeling it.
  An unresolved allocation keeps its dependent installation step open.

- [ ] **G02 — Integrate life support and refuge equipment. AFTER G01/D06/F02/F03 and capacity releases.** Complete air/CO2/gas reserves,
  water recovery, food preservation/Garden support, waste isolation, medical access, alarm/comms/fire protection and independent
  refuge support. **Done when:** required capacity/endurance is owner-supported, equipment and utility access fit, pressure/fault
  isolation is represented and no protection credit is inferred from a visual envelope.

- [ ] **G03 — Integrate selected workshop and service district. AFTER G01/D04/F02/F03 and equipment release.** Package approved
  machine shop, contained process cell, spares/stock, waste and SP-49 support within the existing non-additive budgets. Preserve
  contamination/pressure separation and SP-45's general-storeroom role; verify its aft-down entrance.
  **Done when:** selected equipment, stock, access and utilities fit and their source allocations close. S&E 42 fabrication/mining
  candidates remain studies until actually selected; no full industrial plant implied by the workshop proxy.

- [ ] **G04 — Validate survival/failure coverage. AFTER G02/G03 and relevant F/H/I.** Reconcile S&E 38 requirements, 39 failure scenarios
  and 41 resource budgets with installed systems, including repair stocks, communications, safe attitude and drive-off endurance.
  **Done when:** every required in-scope capability has evidence and stated failure behavior; missing capability keeps WF-R1 blocked
  unless the user/owner explicitly revises scope. Geometric, functional and engineering evidence stay distinct.

## H — Finish forward defense and EYE service integration

Sources: Eye 45, S&E 50 AG-001..020, Tale 28; `references/FWD_V2_EYE_PLACEMENT_2026-10-13.md`.
The layout switch is already built. User 2026-10-29: the saved model carries r30 (2/3 of the shield radius) with hexagonal EYE shells;
the Drive owner rows (FD-B07) keep r4 / B_array 8 m and stay as they are (user 2026-10-29).

- [ ] **H02 — Carrier/station/raceway geometry. BUILT 2026-10-30 as PROTOTYPE, owner-accepted 2026-10-30.** Per facet of the r30
  layout (`eye_release_evidence.service_hardware`, `components/forward.py`): carrier guide out of the well-wall hatch, truss aft-face
  hand-off station, a parked raceway sled on two captured rails along the aft leg, the hull-side service station; the hand-off margins
  are positive at r30 (carrier 0.33 m, sled 1.50 m). A second crawler on the same DS-10 track stays the stranded-sled recovery (15!C191).
  **Open:** the in-well carrier and hatch, rail supports, mass, tow load, latches and the flight-time safe state (owner gates).

- [ ] **H03 — Review/publish the r24 variant and apply any geometry release. AFTER H02.** For a requested r24 showing, run its full
  geometry gate and runtime export as a labelled study. Change the default only after coupled Eye 02 + S&E 14 / mass / optics release.
  2026-10-17 (user): `runtime-export --eye-layout r24` publishes the r24 Godot package labelled STUDY for the hands-on review (TOML
  stays r4); restore canon with a plain `runtime-export`.
  **Done when:** the selected review variant has matching assets/evidence and the owner's layout disposition is recorded; study
  publication never silently changes canonical optical baseline, port radius or performance.

- [ ] **H04 — Complete sourced Crown/AVA cases. OWNER; AFTER C02 and relevant H03 release.** Add per-bay thermal/pulse-bank telemetry
  only with AG-009 fixture; detected-centimeter early/late, meter-class course-change-first and Eye/Crown jam cases only with AG-015
  scenario rows. Resolve FD-E13's unsupported timing/range references before displaying them.
  **Done when:** accepted scenarios replay source-bound states and failures; engaged beams only with an engaged case, no invented
  effectiveness/range. Review physical/explainer views and closed/shutter/jam behavior together.

## I — Finish maintenance drone function at the selected maturity

Sources: S&E 51–54, 56, Eye 46, Tale 29; `references/DRONE_001_2026-10-13.md`. Fleet, crawler demo and route overlay already exist;
all 54 engineering gates currently HOLD. No detailed robot art in the ship before the L2 layout is accepted (DGT-017): the body
candidates of all nine classes are separate accessory assets (docs/ACCESSORIES.md).

- [ ] **I04 — Review and integrate the accessory drone bodies. OWNER REVIEW; AFTER DGT-017.** Owner review of the GU-SIF interface
  proposal (DGT-012) and the class forms (owner 2026-10-24: continue as a separate accessory prototype, not integration or canon); then
  the ship session runs the placement and keep-out study for the taller exterior bodies (interface requests 1–4 in docs/ACCESSORIES.md;
  the owner review and handoff register was accessories/review/HANDOFF.md, now at commit 038ae90;
  no automatic proxy resizing), and the ship viewer uses the GLBs for the drones card and the crawler demo (the retired standalone accessory
  viewer played them). **Done when:** the bodies replace the proxies in the review views with every dock, keep-out and route check
  unchanged or re-run, and nothing implies a released capability.

- [ ] **I02 — Integrate drone stations, conduits and safe operating envelopes. OWNER thermal/alcove releases.** I01 answered 2026-10-17
  (15!A201, 54!A29 DGT-019, 98!A111): the five route choices are a per-job gap matrix (`drone_routes.dgt019`, 29 jobs, 0 pass; shown
  on the drones card); no rail, station or drone added; reach, force, mass, power, thermal and anchors stay HOLD. Resolve
  DS-01/09 stationary alcove beside SP-49 (CAD HOLD), DS-09 conduits outside the crew path, and DS-13 radiant-heat/baffle/cooldown/
  retrieval duty. Preserve HOME dock versus unpowered stops. **Done when:** selected placement and recovery routes fit, hot operation
  remains blocked unless released, and route/keepout inspection and the crawler replay agree.

- [ ] **I03 — Integrate payload, power, heat and mass forms. OWNER; AFTER I01/I02.** Supply measured envelopes, cycle times and track
  lengths for DGT-010/011; consume owner 51 H / DOP-12 mass and bus sizing. **Done when:** required job capacities and budget interfaces
  are source-bound, gate states reflect real evidence and the L3 demo/fault cases use the accepted configuration. Do not turn all 54
  gates green merely to complete the feature; required unreleased capability stays blocked.

## J — Complete runtime movement and navigation

- [ ] **J01 — Finish local physics coverage (PHYS-001). AFTER A03; D06 for changed access.** In bounded edits (trunk branch
  openings done 2026-10-16: seven rig openings cut into the SPINE trunk, closed 0.6 m stubs, `spine_branch_openings` check; Ring B room
  boxes done 2026-10-16: rig v41 `ring_rooms.rings.RING_B`, ring B beat and drop on the B1 boxes; vestibule drill done 2026-10-16: the handoff at the rig's real drum restraint pose, in
  the drum annulus; EVA rail contact and two-tether drift done 2026-10-16: rail rods, protocol keys T/Y/R, both tethers in the
  integrator step), consume the actor float pose from K02. Use shared geometry/frames; preserve DYN-023..027 handoff.
  **Done when:** each exposed interaction matches its geometry and source state, targeted runtime checks pass and hands-on review
  covers it. Transition timing and casualty/flight-EVA HOLDs remain until their own releases. `docs/PHYSICS.md` is the working guide.

- [ ] **J03 — Implement Space Navigator Stage 3. AFTER B03/B04; needs a runtime view again (retired 2026-10-29).** Replace only the
  schematic/unknown portions of `space_navigator.py` supported by released mission states. **Done when:** absolute ship/planet
  positions and accepted timed events reproduce owner data and LIVE versus future preview remains clear.

- [ ] **J04 — Interactive simulation systems (user brief 2026-10-17, S&E 57–59).** Plan and reuse matrix:
  `references/SIM_INTEGRATION_PLAN_2026-10-17.md`. Milestones A–C had Godot views (Space Navigator replay, thermal
  explorer, life-support simulator), retired 2026-10-29 with their scenes; the pure modules and data stay. Left: the owner's MECH approvals (58 all PROPOSAL, 59
  POL-015 selection pending), the out-of-date 55/47 SPACE statuses and the thermal owner conflicts in the plan to report; the drive
  waste heat, loop heat capacity and sunlight inputs for a real thermal clock (40!B11/B13/B15, OPEN); life support waits on the O₂ and water stores, O₂ recovery, Garden yield and ECLSS power (38 S02/S03/
  S05/S10, OPEN); D one fault chain from 39; F light time and detection uncertainty from the
  Eye workbook. No library is imported; the first import needs `references/THIRD_PARTY.md` (POL-010/011).
  **Done when:** each milestone has its owner rows, a playable view, checks against the owner values and its OPEN list.

- [ ] **UJ — Learning journey in the walk (Tale 30_UNIFIED_JOURNEY UJ-001..014; owner brief 2026-10-29). STATIONS BUILT 2026-10-30.**
  Eight UJ-013 stations in ring A (`learning_stations.py`, `learning.gd`): spin (UJ-003) and life support (UJ-004) in sector 3; the
  Eyes (UJ-006), Aegis (UJ-007) and mission preview (UJ-010) at the three ops screens, radiators (UJ-008) and drive (UJ-009) at the two
  engineering benches and the debrief (UJ-011) at the medical couch in sector 2, as internal teaching stops (S&E 15 Q48). The UJ-014
  coverage matrix is in `wf_learning.json`; 2026-10-30 a ninth station (drones, UJ-014) and a remote camera per station. **Open:** the
  SNAV map for UJ-010, physical egress for UJ-011, the instructor's appearance (K01).

- [ ] **J05 — Adaptive Control Induction (user brief 2026-10-17).** Plan, audit and library decision:
  `references/ACI_PLAN_2026-10-17.md`. ACI-01 to ACI-10 are built: the walk's keys are `WfInput` actions, with hold/toggle, stick
  dead zone and sensitivity, and text size. Prune the retired scenes' contexts and actions from `wf_input.gd` and decide whether the
  walk opens the first-launch flow (nothing opens it since the review menu was retired). Left: the three first-run walkthroughs by a person (keyboard
  Personal, keyboard/mouse Suggested, controller Personal, with a real controller); a check of the labels on an AZERTY or QWERTZ
  layout; controller glyphs (optional, `godot_input_icons` MIT); the owner's controller/accessibility review (49 NAV-019 OPEN).
  **Done when:** the walkthroughs pass.

- [ ] **J06 — Station-to-ring excursion with continuous ring circulation (user brief 2026-10-26; EXC-001, CIRC-001, STN-001).**
  Built and checked: the circulation (`ring_circulation.py`, `[ring_circulation]`, both rings' corridors, doors and fit-out; baseline
  `p4_s9_circulation`), the station boarding area (`station.py`, `[station]`) and the playable excursion (`excursion.tscn`, the Godot main
  scene and the web launcher's Start: the main interactive experience; touch controls; runtime check `excursion`: both rings round
  trip, 72/72 bins; web check "touch walk" on an emulated phone). Left: the
  owner's decision on CIRC-001 against 12!A13, the 400–460 m³ gross envelope and the 330 t rotating allowance (CIRC-C1..C8 in
  `ring_circulation.conflicts`; draft in `references/OWNER_Q_CIRC_2026-10-26.md`, not posted); the frame load path round the tunnels
  (CIRC-C7, OPEN); the station's owner workbook and the boarding straps versus ship hatch-rim handholds (STN-001 PROTOTYPE); a
  hands-on walk of both rings by a person (keyboard and controller, desktop and web, and on a real phone); the corridors' cultural pass (31_ARCHITECTURE)
  after the whitebox review. **Done when:** the owner accepts or replaces the circulation, the conflicts are canonized or removed and a
  person completes both excursions in the desktop and web builds.

## K — Finish the two characters, EVA training and production art

- [ ] **K01 — Set the pair's approved appearance. OWNER REVIEW; AFTER C01.** Consume Tale WTF-16, Art Style and Fashion for the
  instructor and newcomer: identity/POV policy, silhouette, face/hair/skin, garments and kit. Reuse MPFB and existing fitted bodies.
  **Done when:** selected greybox/look is reviewed at ship and human scale; no prototype instructor body is silently treated as casting.

- [ ] **K02 — Finish required motion and garment/kit geometry (CHAR-001). AFTER K01 and D05 for hatch-step fit.** Add real garments,
  kit volumes, textures and required float/traversal actions; preserve corrective shapes. UAL/UAL2 Standard retarget of 3–5 actions
  waits for the manual licensed download/pinning; use current actions until available, with any substitute accepted explicitly.
  **Done when:** both characters fit every intended stop/action and gravity mode, required assets/licenses are pinned and Blender/
  Godot rig checks agree. Stepped material-zone outfits alone do not close garment production. See `docs/CHARACTERS.md`.

- [ ] **K03 — Complete the selected suit/PLSS and EVA training pass. AFTER K02/D04 and affected owner gate inputs.** The suit look
  passes and the compact PLSS ASSET-10 study are in docs/ACCESSORIES.md (provisional design candidates). Owner choice between the baseline and
  compact PLSS (deferred: every subsystem's sizing OPEN, EVA-051), owner Art/Fashion markings, refresh the eva references
  (`workflow.py eva`), then re-gate the two actors and seven-station training/abort experience.
  **Done when:** suited envelopes, airlock, tether/anchor behavior and training review pass; actual H-05..H-11/O-01..O-06 releases
  are required for any operational claim. Missing flight gates remain visible and locked; no training PASS becomes FLIGHT_EVA GO.
  Sources: `docs/EVA.md`, S&E 43–45, Technology 53, Tale 26.

- [ ] **K04 — Finish accepted exterior and interior art (FUT-003). AFTER C01/K01; D06/G for affected rooms; F/H/I for affected hardware.**
  Work one bounded zone at a time: stable assembly construction, cultural architecture, lighting/materials, functional wear and
  approved furnishings. Preserve engineering envelopes and human routes; retain ART separation and deliberate backups.
  **Done when:** each in-scope zone passes whole-ship/assembly/human-scale visual review with selected construction integrated, and
  owner art review accepts the result. Final tank/shield finish waits on their physical decisions.

- [ ] **K05 — Finish review shots and scenario presentation. AFTER K02–K04 and applicable B03/J03/H04.** Produce the accepted interior,
  First Ignition, survival-damage and route views using the shared assets/state data. Physical light and explanatory fill stay labelled;
  unsupported attitude, thermal clock or mission positions are never invented for a shot.
  **Done when:** the agreed review scenes are reproducible, readable and owner-reviewed in Blender and the relevant runtime views.
  This step produces a project review set, not an entire series.

## R — Whole-project verification and proper final review

- [ ] **R01 — Freeze and verify the review candidate. AFTER all required A–K steps.** Select one source/parameter/code snapshot;
  perform whole-ship inspection and full pipeline for the final geometry candidate, review the fingerprint and accept only intended
  changes, then export/check the matching runtime. Reuse an unchanged valid full receipt; do not rerun checks without cause.
  **Done when:** source capture, saved blends, rig, GLBs, runtime identity, character assets and documentation agree; required route,
  physics, failure and import checks pass. No unexplained geometry delta, stale package or missing required implementation.

- [ ] **R02 — Assemble and conduct the integrated review. AFTER R01.** Use existing preview/capture tools; no new review framework.
  Review in this order: whole-ship COAST/HIGH_POWER silhouette → assemblies/service access → occupied human-scale spaces → boarding,
  microgravity, both accepted ring routes and return → navigators/mission states → defense/drone faults → EVA training → art/characters.
  Include a playable replay plus manual interaction, source/status/readback summary, selected physical/fill stills and an explicit
  register of residual engineering limits with owner, consequence and HOLD behavior. Record hardware/resolution and measure only
  suspected performance problems; file triangle counts are not frame-time evidence.
  **Done when:** user and relevant owners have a concrete versioned review package and their findings are recorded as blocking or
  nonblocking with rationale. A test log cannot substitute for visual or hands-on review.

- [ ] **R03 — Resolve review findings and accept WF-R1. AFTER R02.** Fix blockers in bounded slices, rerun only affected checks plus
  the required final geometry/export gates if the candidate changes, and return changed views/interactions for review.
  **Done when:** user/owner explicitly accepts the final snapshot, all required scope is implemented and no blocking finding remains.
  Unresolved required science/architecture cannot be waived locally. An agreed scope reduction must be recorded as such, not “done.”
  Update MODEL and the dated review evidence; prepare authorized status/queue cleanup. Commit only on request, then propose pruning
  per AGENTS.md; do not delete evidence or ART backups automatically.

## Parked / optional work — not implicit WF-R1 prerequisites

- [ ] **P01 — FUT-006 PlayCanvas / Densho Expo. PARKED, separate scope decision.** If selected, resolve hosting, IP/public-source
  exposure, embed/CSP permissions and browser performance/accessibility before a prototype. Reuse the GLB pipeline and stable IDs;
  keep Godot. Acceptance would include publication, desktop/mobile interaction, iframe/new-tab fallback, credits and update procedure.
- [ ] **P05 — Website follow-ups (WEB-002). Optional, outside WF-R1.** The site, play build, checks, deploy and verify exist (rollback = revert on main) (docs/wayfarer-web-experience-plan.md); the first deploy (`b1db258`) passed the live verify job. Owner's order:
  - Measure on real hardware: frame rates on real GPUs (viewer and Godot, desktop and phone); all numbers so far are software
    rendering. Record them in the plan §5–6.
  - Firefox (then Safari on macOS and iOS): test by hand, then add to the browser check where a headless build exists.
  - Navigator glyphs ▶ ◆ ○ render as boxes on Web: ship a font with them or use drawn markers (Godot presentation only).
  - Build time: the site walk (5-8 min under software WebGL) is the longest step.
  - Touch (MOB-001, branch `claude/mobile-touch-controls`, docs/wayfarer-mobile-controls-plan.md): test on a real Android phone
    and an iPhone (plan §9 procedure), agree the reference phone and its 30 fps budget, then tune RENDER_DENSITY and the
    adaptive band from those measurements. Before promotion: Android Chrome and iOS Safari (iPhone; iPad if available) each
    complete the journey by touch, with real-GPU frame rate, input latency and thermal behaviour recorded in plan §11.
  - CI cost: split the browser check into independent jobs (desktop walk and equivalence; mobile touch journey) so each
    runs, fails and reruns alone and they no longer share one runner's four cores. Run 39926690587 spent 31 of its 35 minutes
    in the single browser-check step.
  - Hologram and hybrid appearance (WEB-003/004, branch `claude/affectionate-goodall-orfxcx`, web/README.md): owner review of the
    Subsystems, Engine holo and Hybrid looks, ghost strength default (6 %) and two-layer hologram cap, on real hardware (desktop GPU
    and phone frame times; all numbers so far are SwiftShader).
    Radiator blades cannot be isolated one by one: their cells carry no lineage below Assembly_THERMAL in the export (the viewer's
    Group scope reads the manifest lineage); a blade-level lineage in export/godot.py would add it. Later (P3): exploded views,
    section planes and cutaways.
- [ ] **P03 — Optional compliant-tether stress study. PARKED, owner-led.** Do only when OD-038/required interaction needs it; do not
  confuse a timestep-dependent impulse diagnostic with rated human loads. Required operational tether releases remain in D/K.
- [ ] **P04 — Full-gate policy relaxation. PARKED, optional process change.** Retain the existing full pre-commit geometry gate. Consider
  relaxation only after scoped-versus-full evidence over several real changes demonstrates no misses. No special benchmark project.

## Owner routing and question continuity

Canonical route: IGNITION TOC → owner workbook → S&E `15_MODEL_INTERFACES`. Request Doc is the temporary queue; Model Status
Implementation/Readback are correspondence. Owner question IDs use ISO local timestamps; legacy Q39 stays as named. S&E A86's Q37
is the entrance workflow, not the retired local radiator-planform question.

Known queue items (2026-10-24, Phase 4 production):
- `2026-10-24T10:55+02:00 — P4`: the remainder of the Phase 4 packet, candidate acceptance (`ra2_equip` now; M8.2 and the
  `rad_frame` revision when presented). The S1 art gate is answered, canonicalized (Art Style Spacecraft row 19) and deleted.

Before that (2026-10-19), none. Q39 closed 2026-10-19 (12A!H5/H22 and 40!A18 repaired and read back on the owner's approval,
15!A223; references/Q39_PROVENANCE.md); 14:31 (D02) and 14:32 (C01) consumed and deleted (references/OWNER_RESOLUTION_2026-10-19.md).
The H02 crawler count is decided locally (same-track second crawler, payload-gated; 15!C191).
HR-001 is a new canonical study handoff, not an assumed numeric release. Maintain POST → RESOLVE → CANONICALIZE → CONSUME/APPLY →
VERIFY → DELETE; remove only consumed portions and keep unresolved remainders with their existing owner records.
