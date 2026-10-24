# Phase 4 plan: visual production, art direction and modular detailing

**Status: PRODUCTION (2026-10-24).** The owner answered the eight Stage A questions and, at the **S1 art gate** (2026-10-24), selected
the exterior grammar **VC+ Expressive Hybrid with moderated material values** and disposed of the three candidates (section 0). S0, S1
and S2 are done on this branch; S3–S11 proceed in dependency order (section 3.4) without another general authorization, inside the
engineering HOLDs, the candidate gates and the promotion rule. This file is the single Phase 4 plan. Commands and contracts are in
AGENTS.md, docs/MODULES.md and docs/IMPLEMENTATION.md. Nothing here is canon; the canonical records are named in section 0.

Program authorization does not promote a branch to `main` (owner approval per squash, AGENTS.md step 5) and does not accept any visual
candidate (each stays `L4_VISUAL_CANDIDATE` until the owner's own review).

## 0. Owner decisions consumed

Read from the request Doc on 2026-10-24 (each item's `OWNER ANSWER — 2026-10-24:` paragraph). The answers supersede the Stage A
recommendations where they differ.

| Item | Owner answer (short; the Doc text governs) | Canonical destination | Plan effect |
| --- | --- | --- | --- |
| P4-EXP | B: Crown bay 1 + its 30° Brow aft sector, plus a ring A 15° segment probe; variants V0, civic, open machine, restrained hybrid, expressive hybrid in matched views. Stage B authorized for the plan, the queue and S0–S1. S2–S11 approved in principle; no grammar codified or rolled out before the owner selects it at the S1 review. Branch promotion approvals stay. | this plan (procedure); Model Status Phase 4 row (state) | S0, S1 run now; S1 art gate before S2 |
| P4-ART | H, functionally allocated hybrid, as the **leading hypothesis**; lean **expressive**: strong mechanical readability and light/dark separation, calm institutional shell fields and negative space. Civic shells on pressure volumes and Brow protection; exposed construction where parts articulate, attach, carry load or need service; thermal drama only where thermal design explains it. Provisional until the S1 review. Rings more legible without changing size, clearance or motion. | this plan only (a hypothesis is not canon); Model Status Phase 4 row | S1 compares VC and VC+ against the controls; S2 waits on the selection |
| P4-CAND | Option 3 for all three (`m8_forward`, `rad_frame`, `ra2_equip`): **defer** to an owner-facing visual comparison; they stay `L4_VISUAL_CANDIDATE`. M8.1 is the untouched V0. S0 makes targeted stills of `rad_frame` and `ra2_equip`; keep/revise/reject recommendations with images at the S1 review. No removal or silent replacement; approved corrections enter their later slice. | Model Status rows 30 and 32 (candidate state) | S0 candidate stills; dispositions at the S1 review |
| P4-MAT | B: physically motivated, depiction-only PROTOTYPE material-family library; value separation (light GU/Spacer shells and cladding, middle structure, graphite machinery, dark thermal) with ochre service and amber occupancy; GU deep blue only as a restrained tested wayfinding/marking accent; no emblem, paint standard or registry; restrained and expressive versions at S1; emission and cross-viewer parity preserved; balance reviewable. | Art Style Spacecraft row 18; S&E 15 OWN-P4-LOCKED (material appearance qualifies nothing) | S1 VC/VC+ families; S9 library |
| P4-LOCKED | B with bounds, labelled ILLUSTRATIVE/PROTOTYPE: (a) dark high-emissivity-looking blade surface in COAST, no change to cells, emissivity assumption, area or IGNITION 1800 K emission; (b) subtle regenerative tile-and-repair look on the 90 m ram face by shader/normal/texture only, no tile size or shielding claim. Drive/nozzle cores simplified until released. No qualified coating or service mechanism; no hero finish on unresolved interfaces. Validate silhouette, emission and runtime. | S&E 15 row 228 `OWN-P4-LOCKED-2026-10-24` | S1 V0T and VA–VC+ use (a); (b) in S3/S9 |
| P4-SCOPE | A, interactive-first: one master asset system (reused meshes, instancing, draw ranges, LOD); hero shots from the same source. HERO: one Crown/Brow bay, one ring exterior segment and hub, one blade root, the primary port. PRODUCTION: repeated Crown bays, both ring exteriors, blade frames, spine/equipment, ring B M7-equivalent path. SIMPLIFIED/HOLD: drive/nozzles, tanks, unreleased EYE optics, Dust Lance, unresolved aft features. Desktop Godot is the measured budget; web/mobile get measured coarser views; no invented FPS targets. | this plan (production procedure) | tier column in section 3; S11 measures |
| P4-STATE | S2 + M1: Y155 launch/departure baseline (clean, serviced, institutional, never sterile) plus a separately switchable post-voyage wear/repair layer at plausible touch, heat, load, impact, repair or maintenance points, no geometry or canon change. Text-only markings: GU WAYFARER 001, Crown/ring sector IDs, handling, hazard, service stencils; no G.U.C., crest or registry; civic phrase plate not a standard. | Art Style Spacecraft row 18 | S9 layers; S1 markings text-only |
| P4-INT | Order Z4 (ring B transfer + first sector, accepted M7 grammar), Z1 (ring A Garden/mess), Z2 (ring A work/medical/ops), Z3 (berths/private niches), adjusted only for real dependencies. K2 at launch (GU Order + Spacer Contain, restrained Bolt-Sworn/Robocrat-humanized serviceable details where people live); K3 only in the post-voyage layer, grounded in story and crew roles. Ergonomics, pressure/route envelopes and M7 acceptance protected; workshop excluded while OD-030 is OPEN. | Art Style Spacecraft row 18 (character); this plan (order) | S8 order |

**S1 art gate (owner, 2026-10-24, instruction "Phase 4 S1 Art Direction Resolution & S2–S11 Production Instructions"):**

| Item | Owner decision | Canonical destination | Plan effect |
| --- | --- | --- | --- |
| Grammar (P4-ART remainder) | **VC+ Expressive Hybrid, moderated values**: Civic Monumentalism + Open Machine + Thermal Leviathan; institutional order outside, experimental engineering within, human ingenuity throughout. VC+ is the starting grammar, not a requirement to copy every S1 value or detail; moderate the brightest shells, keep calm fields. Adopt the dark COAST blade depiction. | Art Style Bible Spacecraft row 19 (written 2026-10-24, read back) | S2 codifies it (`[production.exterior]`); S3–S11 apply it |
| Values | Starting linear ranges for material tests, not a reflectance specification: shell 0.70–0.78, structure 0.22–0.30, machinery 0.03–0.08, thermal 0.02–0.035; tuned under matched COAST/IGNITION; no blown-out whites at human scale | Art Style Spacecraft row 19 | `[production.exterior.families]` |
| GU deep blue | Approved as a restrained functional wayfinding accent only: service-lane boundaries, selected pressure-segment identifiers, navigation references; no flag, crest or paint standard | Art Style Spacecraft row 19 | `accent_area_max`, `wayfinding_uses` |
| M8.1 (`m8_forward`) | **REVISE in S3**: keep the bay/module construction; improve mechanical readability, shell/structure/equipment separation, lane values, access-panel contrast, stencil scale and placement; no wholesale rebuild | Model Status row 30 | S3 (M8.2); stays `L4_VISUAL_CANDIDATE` until reviewed |
| `rad_frame` | **REVISE in S5**: larger structural rhythm, load paths, root interfaces and band placement before enlarging fittings; thermal area and expansion clearance preserved | Model Status row 32 | S5; stays a candidate until reviewed |
| `ra2_equip` | **RETAIN as designed** as a candidate; no redesign without a demonstrated reason; before/after close-ups for owner acceptance | Model Status row 32; request Doc remainder | acceptance pending; S8b Z2 builds on it |
| Caption overlap | correct the overlapping interior-preview captions in the presentation tooling (not an asset defect) | — | done in S2 (interior_preview.py) |

**Doc disposition (protocol POST → RESOLVE → CANONICALIZE → CONSUME/APPLY → VERIFY → DELETE):** the Stage A items were deleted after
canonicalization. The S1 art gate was recorded in the Doc (owner answer, 2026-10-24), canonicalized in Art Style Spacecraft row 19 and
Model Status rows 30, 32 and 33 (all read back), and its resolved part deleted; the unresolved remainder **candidate acceptance**
(`ra2_equip` now; M8.2 and the `rad_frame` revision when presented) stays under the original timestamp `2026-10-24T10:55+02:00`.

## 1. Baseline

**Repository:** branch `claude/compassionate-feynman-jmgsnl`, merged with `main` 6890af3 (WEB-003/004) on 2026-10-24. The Stage A
baseline (15997fe) is unchanged in geometry: 6890af3 adds web/Godot hologram presentation only.

**What the ship is now.** One REP_PROXY engineering model with switchable production layers:
- **Body and bow:** 225 m body (13 m diameter) + 12 m Dust Lance = 237 m. The 90 m Brow carries the twelve-bay Aegis Crown
  (housing r 41.0–44.5 m, aft plate at x 106.44 m) and four recessed EYE wells (r4 WORKING).
- **Rings:** `WF_HABITAT_A` (centre x 85.05 m) and `WF_HABITAT_B` (x 91.05 m), 60 m diameter, frame r 24.5–30.0 m × 4.0 m axial,
  sweep half-depth 2.15 m, three pressure sectors (r 25.0–28.7 m × 3.5 m, recessed 0.25 m per side) and six spokes each.
- **Thermal and drive:** three fixed 182.149 m × 30.5 m blades at 1800 K; thrust ring and four magnetic nozzles (Q40).

**Accepted grammar (owner):** M4 constructed exterior (15!A202, Art Style Spacecraft row 16); M5 hologram look (15!A220); M7 interior
production section (`L4_VISUAL_ACCEPTED`, value ladder inhabited / service / machinery / structure / seams); lettering L1 "GU WAYFARER
001" stencil (15!A216, A225; Art Style row 17); Phase 4 depiction rules (Art Style row 18; S&E 15 OWN-P4-LOCKED).

**Packs:** `m7_spine`, `ring_a_transfer`, `m7_ra1` (`L4_VISUAL_ACCEPTED`); `m8_forward` (M8.1), `rad_frame`, `ra2_equip`
(`L4_VISUAL_CANDIDATE`). Ring B, drive, fuel, EYE and the utility modules have no pack.

**Visual assessment (Stage A, confirmed by S0 renders):**
- **Keep:** thrust-axis hierarchy (Lance, Brow, rings, blades, nozzles); fixed three-blade thermal identity; M4 functional colour; M7
  value ladder; one Crown module per bay with a service lane on its azimuth; the pack/anchor system.
- **Primary defect:** the blades (≈5,000 m² each, physics-locked) dominate side and three-quarter views; the rings, 4 m-wide hoops seen
  edge-on or foreshortened behind the 90 m Brow, read as thin smooth bands. In the hero look every non-functional surface is one proxy
  grey (0.62), so nothing separates rings, Brow back, spine and blades by value.
- **Too primitive:** smooth ring tori; one cream ram-face disc; plain spine tube; `rad_frame` and the 0.20 m M8 hatch stencil invisible
  at use distance.
- **Engineering conflicts:** none in the accepted or candidate packs.

### 1.1 S0 evidence

See section 4.1 (filled by the S0 run on this branch).

### 1.2 Visual Design Freedom Map

| Class | Assemblies | Phase 4 may | Phase 4 may not |
| --- | --- | --- | --- |
| Engineering-locked (physics) | blade planform, cells and 1800 K emission; drive core, manifold and nozzles (Q40); EYE apertures and optics (r4 WORKING, r16/r24 study only); Dust Lance and field (OD-017/018); Brow thickness and stack (OD-014/019); pressure shells, hatches, seals and closures (OD-034); rotor interface and bearings (OD-013) | show existing seams and load paths; **depiction-only finish within OWN-P4-LOCKED**: dark high-ε-looking blades in COAST, ram-face tile-and-repair by shader/normal/texture | change area, emission, radius, apertures or clearances; claim a coating, emissivity, tile size or rating; hero-finish an unresolved interface |
| Functionally constrained working geometry | Crown sectors, carriages and shutters (OD-021); radiator roots, saddles and frames (OD-007/039); ring frames and spokes (OD-016); exterior hardware S02; crawler lane and service routes (50!AG-A02); docking port (Q33) | clad, frame and mark within the anchor envelopes; make mechanisms legible | imply a qualified mechanism, rating, rail (RUN-011) or new opening |
| Artistically flexible | cladding modules, panel rhythm, fasteners, closeouts, text-only markings, value and material families, interior fit-out, lighting, camera, wear placement (switchable layer) | design freely within HSFP, the Anti-Rules and Art Style row 18 | greebles, fins, neon, decorative glow, panoramic windows, random grime, crest, registry, G.U.C. |
| Blocked by HOLD | WF_STORAGE tanks (OD-026, 15!A224); aft robotic cradle and HGA ORU (15!A225); workshop (OD-030); r16 EYE geometry; flight EVA rails | nothing beyond the existing study layers | production detail on them |
| Accepted production assets | M7 (six assemblies, three packs) | extend the M7 language; correct only on owner request | restyle them |
| Candidates awaiting review | M8.1 (`m8_forward`, REVISE in S3), `rad_frame` (REVISE in S5), `ra2_equip` (RETAINED, acceptance pending) | revise in their slice, keeping the candidate label | accept, remove or silently replace them |

## 2. Design direction

**Selected grammar (owner S1 art gate, 2026-10-24): VC+ Expressive Hybrid with moderated values** (Art Style Spacecraft row 19), the
expressive functional hybrid below with the owner's corrections: calm institutional shells with negative space, mid-value structure only
at real interfaces, graphite machinery with readable assembly logic, dark functional thermal surfaces, ochre service, selective muted
amber occupancy, GU deep blue only for wayfinding. Detail at distance comes from large-scale structural rhythm, value contrast and
composition, never from enlarged small parts; hero assemblies withstand close-up inspection through interfaces and layered construction.
The S2 codification is section 4.3.

**The hypothesis the S1 study tested (owner P4-ART):**
- **Civic shell** on pressure volumes and the Brow protection: calm, modular, institutional GU fields with negative space.
- **Exposed construction** where parts articulate, attach, carry load or need service: Crown hatch and doubler, service lanes and
  their utilities, ring segment joints and spoke nodes, blade roots and saddles, spine truss nodes, docking.
- **Thermal identity** only where the thermal design explains it: frame rhythm, the dark high-ε COAST depiction, true emission in
  IGNITION.
- **Value hierarchy:** light shells, middle structure, graphite machinery, dark thermal; colour for function only (ochre service,
  amber occupancy, GU deep blue wayfinding as a tested accent).

The owner selected its expressive version (VC+) with moderated values on 2026-10-24.

**Research lessons** (methods, not shapes; no proprietary asset or distinctive design reused):

| Reference | Lesson for Wayfarer | Licence note |
| --- | --- | --- |
| [ISS Integrated Truss Structure](https://en.wikipedia.org/wiki/Integrated_Truss_Structure) | A truss reads as an assembly when segment joints, utility trays and transport rail are distinct, repeating elements (spine, blade roots). | facts and photos, reference only |
| [ITER blanket modules and remote handling](https://www.iter.org/node/2752) | Identical, replaceable, bolt-on modules with a visible handling interface make a repairable protective wall (Brow, Crown bay). | reference only |
| [Beta cloth](https://en.wikipedia.org/wiki/Beta_cloth), [NASA MLI guidance](https://ntrs.nasa.gov/citations/19930015285) | Blanket families give pressure volumes a soft institutional shell against hard machine parts. | public-domain NASA documents |
| ISS ORUs and the [Mobile Servicing System](https://en.wikipedia.org/wiki/Mobile_Servicing_System) | Robot-serviceable units share standard fixtures, alignment marks and handling colours. | reference only |
| *The Expanse* production design ([ArtStation interview](https://magazine.artstation.com/2016/02/scenes-concept-art-expanse/)) | Silhouette before surface; history as a later layer. | method only |
| Interstellar, 2001, Alien, Elite Dangerous, Star Citizen | Scale through restrained rhythm against calm fields; LOD keeps silhouette, drops micro detail. | method only |

## 3. Authorization and slice plan

### 3.1 Authorization classes

| Class | Slices | Starts when |
| --- | --- | --- |
| 1. Authorized for immediate production | **S0**, **S1** | done (section 4) |
| 2. Approved, dependent on the S1 art decision | **S2**, then S3, S4, S5, S6, S9, S10, S11 | **released 2026-10-24** (grammar selected); each continues without another general authorization |
| 3. Dependent on engineering releases | **S7** (drive/nozzle, aft features); ring B rescue/closures inside S8a (15!A197, OD-032/034/040); tanks (OD-026); EYE r16; aft cradle/HGA ORU (15!A225); workshop (OD-030) | the owning workbook releases them |
| 4. Awaiting specific visual-asset acceptance | acceptance of M8.2 (S3) and of the `rad_frame` revision (S5) as assets; `ra2_equip` acceptance (evidence delivered); S4 rollout (the gated ring A segment) | the dispositions are made (M8.1 and `rad_frame` REVISE, `ra2_equip` RETAIN); the work proceeds, the assets stay `L4_VISUAL_CANDIDATE` until the owner reviews them |

S8a (ring B transfer and first sector, Z4) uses the already accepted M7 interior grammar, not the S1 exterior grammar; it is approved in
principle and is the first slice to start after the S1 gate.

**Tiers (P4-SCOPE):** HERO — Crown bay 1 + Brow sector, ring A segment and hub, one blade root, the primary port. PRODUCTION — the other
Crown bays, both ring exteriors, blade frames, spine/equipment, ring B M7-equivalent path. SIMPLIFIED/HOLD — drive/nozzles, tanks,
unreleased EYE optics, Dust Lance, unresolved aft features. One master asset system: HERO is the same source at higher presentation
quality, never divergent cinematic geometry.

### 3.2 Common rules

**Per slice:** read source → `module show <pack>` (ownership) → implement → `module validate` and `pipeline --quick --target auto
--expect Prod_ Detail_ WF_DETAIL [--inspect auto]` → render the review set → self-review → full `pipeline` → `module publish` →
MODEL, TODO, Model Status row → owner review. A technically valid asset is not artistically accepted; new work stays
`L4_VISUAL_CANDIDATE`. Every slice keeps the switch-off empty geometry diff, silhouette radius, BVH and route margins, and adds no
mass key.

**Review set** (matched cameras from `src/wayfarer/studies/p4_s1_grammar.py` `frames()`): whole-ship three-quarter; side silhouette;
rings three-quarter; subsystem close-up; 1.8 m human scale; functional cutaway; COAST +2 EV editorial with the matched COAST/IGNITION
pair (15!A222).

**Review criteria:** silhouette and hierarchy, ring legibility, originality, mechanical credibility, manufacturing logic, scale,
material consistency, GU and IGNITION identity, close-up quality, reuse and cost. No numeric art gate.

**Parallel sessions (after S2):** one writer each — WF-FWD (S3), WF-RING-A then WF-RING-B (S4), WF-THERMAL (S5), WF-SPINE (S6),
WF-RING-B interiors (S8a). The coordinator keeps S2, S9, S10, S11, `data/modules.toml`, the shared materials, `production_detail.py`,
the generators and this plan. One build lock: sessions queue for builds.

### 3.3 Slices

#### S0 — Production baseline · Low · class 1 · DONE (section 4.1)
- **Direction:** a reproducible before-set and a working toolchain, so later slices compare against the same images.
- **Boundaries:** no geometry; run folders local.
- **Sources:** 15!A222 (exposure); request Doc `2026-10-21T08:55` (livery readback); Model Status rows 29–32.
- **Outputs:** Blender 5.2.2 and Godot 4.7.2 verified; full build and pipeline gate; before-set at the review cameras; M8.1, `rad_frame`,
  `ra2_equip` review stills with contract evidence; livery readback.
- **Done when:** the above exist and are recorded (section 4.1).

#### S1 — Grammar experiment: Crown bay 1, Brow aft sector, ring A segment · Medium–High · class 1 · DONE (owner selection 2026-10-24)
- **Direction:** V0 (M8.1 control), V0T (thermal depiction only), VA civic, VB open machine, VC restrained hybrid, VC+ expressive hybrid
  (section 4.2).
- **Boundaries:** in-memory ART_P4 study only; M8.1 unchanged; all pack screens and the ring frame/sweep/sector screens pass.
- **Outputs:** labelled comparison set, candidate review, recommended grammar (a recommendation), owner review packet.
- **Review gate:** **S1 art gate** — passed 2026-10-24: VC+ moderated selected; M8.1 and `rad_frame` REVISE, `ra2_equip` RETAIN.
- **Done when:** the owner has selected (done).

#### S2 — Codify the selected grammar · Medium · class 2 · integration-owned (WF-CORE) · DONE (section 4.3)
- **Direction:** the selected VC+ moderated grammar as a reusable production system: material families, macro/meso/micro tiers,
  panel, joint and service-interface rules, marking scale, accent allocation, reusable component families (only where two packs need
  them), the Blender/Godot material mapping, review cameras and the negative-space rule.
- **Boundaries:** shared keys only (`[production]` exterior grammar keys, `[production.materials]` families, `production_detail.py`
  helpers only if two packs need them); accepted M7 stays pixel-equivalent or the change is reported; no mass key.
- **Sources:** S1 review; Art Style rows 16–18; S&E 15 OWN-P4-LOCKED, I120/H120.
- **Dependencies:** S1 art gate.
- **Candidates:** none promoted; M8.1 corrections listed for S3.
- **Outputs:** scale tiers (macro bay, meso panel, micro fastener by view distance); exposure rule; closeout/doubler families; marking
  type scale with minimum legible size per distance; material family table (restrained/expressive as selected); seed rules.
- **Review gate:** M7 stills unchanged; S1 cameras re-rendered.
- **Parallel:** precedes S3–S6 and S9.
- **Done when:** keys exist, M7 unchanged or explained, MODEL documents the grammar.

#### S3 — Forward production: Brow and twelve Crown bays (M8.2) · Medium · class 2 + 4 · WF-FWD · BUILT, owner review (section 4.4)
- **Direction:** the selected grammar on the Brow aft face and all twelve bays; the ram face tile-and-repair appearance by
  shader/normal/texture only (OWN-P4-LOCKED (b)).
- **Boundaries:** r ≤ 45.0 m; nothing sunward of the skin; shutters, carriages, emitters, launchers, ports, windows, EYE wells untouched;
  crawler lane clear; OD-021 open (no mechanism finalized); ram-face appearance implies no tile size or shielding.
- **Sources:** Eye 45, S&E 50 (AG-A02), OD-020/021, Art Style row 10 (repaired shield patches).
- **Dependencies:** S2; M8.1 disposition: REVISE (owner 2026-10-24) — keep the bay/module construction, no wholesale rebuild.
- **Candidates:** M8.1 stays a candidate until replaced by M8.2 with the owner's approval; never silently removed.
- **Outputs:** M8.2 in `m8_forward`; one HERO bay (bay 1) and eleven PRODUCTION bays from the same module with stable per-bay seeds.
- **Review gate:** `--inspect forward`, `m8_readback`, BVH; review set.
- **Parallel:** with S4, S5, S6.
- **Done when:** the Brow and Crown hierarchy reads at whole-ship distance and at human scale.

#### S4 — Habitat ring exteriors · High · class 2 + 4 · WF-RING-A, then WF-RING-B · BUILT, owner review (section 4.5)
- **Direction:** the rings as visibly distinct, assembled, maintainable pressure structures: shell over the pressure faces and fill,
  exposed segment joints and spoke nodes, amber occupancy, text-only sector IDs; legibility from value contrast and construction
  rhythm, never from size.
- **Boundaries:** inside r 24.5–30.0 m, |u| ≤ 2.15 m and outside the sector pressure envelopes; rotor independence and sweep clearance
  (`--inspect rotation`); motion inherited from the rotor; no shielding, mass or balance claim.
- **Sources:** S&E 08, 12, 15 R-rows, OD-003/013/016; S1 ring probe.
- **Dependencies:** S2; one ring A segment gated first (HERO), then the repeat.
- **Outputs:** new packs `ring_a_exterior` (anchor `WF-RING-A.ROTOR.1`) and `ring_b_exterior` (`WF-RING-B.ROTOR.2`); the hub read from
  outside (HERO tier).
- **Review gate:** `--inspect rotation route`; runtime-export (moving parts).
- **Parallel:** ring A and ring B in separate sessions after segment 1 passes.
- **Done when:** both rings read as distinct assembled structures in the side, three-quarter and rings views; motion checks pass.

#### S5 — Radiator roots and blade frames · Medium · class 2 + 4 · WF-THERMAL · BUILT, owner review (section 4.6)
- **Direction:** framed thermal machines: root saddles, boots and manifolds (HERO: one root); frame rhythm readable from whole-ship
  distance; the dark high-ε COAST depiction (OWN-P4-LOCKED (a)).
- **Boundaries:** footprints only in non-emitting joints or beyond the blade ends (net area unchanged); root expansion travel clear;
  IGNITION emission unchanged; no coating claim.
- **Sources:** 40_THERMAL, OD-007/012/023/039, 15!A204.
- **Dependencies:** S2; `rad_frame` disposition: REVISE (owner 2026-10-24) — structural rhythm, load paths, root interfaces and band
  placement before enlarging fittings.
- **Candidates:** `rad_frame` revised only through this slice, keeping its maturity until the owner reviews the revision.
- **Outputs:** `rad_frame` revision; new `rad_root` pack.
- **Review gate:** `--inspect thermal`, `radiator_net_area` unchanged, HIGH_POWER preview, Godot/web emission parity.
- **Parallel:** with S3, S4, S6.
- **Done when:** the blades read as framed thermal machines in COAST and the IGNITION read is unchanged.

#### S6 — Spine casing, service routes, exterior equipment · Medium · class 2 · WF-SPINE
- **Direction:** a serviced keel between the blades: casing modules between frame stations, utility routes the eye can follow, the S02
  hardware in the selected families.
- **Boundaries:** no new opening, rail (RUN-011), cradle or HGA ORU (HOLD); EVA handrails parked; docking Q33 unchanged; plume and
  ring-sweep exclusions kept.
- **Sources:** 14_HULL_SERVICE, 37 F14–F17, 51–54, 15!A213/A225.
- **Dependencies:** S2.
- **Outputs:** new `spine_casing` pack; equipment look through the S02 generator (integration) or a small `ext_equipment` pack; HERO:
  the primary port.
- **Review gate:** `--inspect hull route`.
- **Done when:** the spine reads as a serviced keel with followable routes.

#### S7 — Propulsion-adjacent structure · Low–Medium · class 3 · WF-DRIVE
- **Direction:** only released exterior: thrust-ring plates, aft collar, shadow-shield cladding, service closeouts.
- **Boundaries:** nozzles, coils, plasma path SIMPLIFIED (Q40, OD-024/025; 15!A214/A226); plasma, field and plume keep-outs.
- **Dependencies:** engineering release; S2.
- **Done when:** the aft end matches the grammar without implying a solved drive.

#### S8 — Interiors in the owner's order · Medium each · S8a class 2 (M7 grammar), S8b class 2 + 4
- **Order (P4-INT):** Z4 ring B transfer and first sector (S8a) → Z1 ring A Garden and mess → Z2 ring A work/medical/ops (`ra2_equip`
  retained as designed; its acceptance is pending) → Z3 berths and private niches. Workshop excluded while OD-030 is OPEN.
- **Direction:** S8a in the accepted M7 grammar (packs `ring_b_transfer`, `m7_rb1`); S8b cultural pass K2 at launch: Spacer *Contain*,
  GU *Order* wayfinding and standardized interfaces, restrained Bolt-Sworn/Robocrat *Humanize* where people live; K3 only in the
  post-voyage layer (S9).
- **Boundaries:** fit-out never changes a pressure boundary, interface or route clearance; ergonomics, SERV-STRIPS 0.60 m, ring B
  rescue/closure HOLDs (15!A197, OD-032/034/040) and M7 acceptance protected.
- **Review gate:** `--inspect route`, the route sweep, the Godot walk; human-scale whitebox review before each cultural pass.
- **Done when:** each zone passes human-scale and cultural review.

#### S9 — Material, livery and condition system · Medium–High · class 2 · integration-owned
- **Direction:** the depiction-only PROTOTYPE family library (Art Style row 18); Y155 launch baseline; switchable post-voyage
  wear/repair layer; text-only markings (GU WAYFARER 001, Crown/ring sector IDs, handling, hazard, service).
- **Boundaries:** no G.U.C., crest, registry, paint standard or phrase plate; wear only at plausible touch, heat, load, impact, repair
  or maintenance points and never as geometry or canon; no coating claim; no 1800 K change; no static lighting baked into textures.
- **Dependencies:** S2 (families selected at S1).
- **Outputs:** `[production.materials]` families and `look.py` (one writer); marking type scale; wear layer switch.
- **Review gate:** `review` and `look` previews; Godot and web material/emission parity.
- **Done when:** every exterior zone uses a library family, markings read at their distance, wear is switchable.

#### S10 — Cinematic presentation · Medium · class 2
- **Direction:** reproducible hero renders from the same master assets: S004 induction, departure, First Ignition, survival damage
  (wear layer), return.
- **Boundaries:** no impossible dimming; concept fill labelled ILLUSTRATIVE; no invented attitude, thermal clock or release (K05).
- **Dependencies:** first passes of S3–S6 and S9.
- **Done when:** the agreed hero set renders reproducibly and the owner reviews it.

#### S11 — Runtime integration and whole-ship review · Medium · class 2
- **Direction:** Godot/web parity, per-pack draw ranges and LOD, verified mesh sharing; frame time measured on desktop Godot (primary
  budget) in representative views before and after; web/mobile coarser views measured; no invented targets.
- **Done when:** runtime checks pass, measurements are recorded, and the owner accepts the identity. Phase 4 is complete only when the
  implementation, evidence and owner approvals justify it.

### 3.4 Dependencies

S0 → S1 → **S1 art gate (passed 2026-10-24)** → S2 → {S3, S4, S5, S6, S9} → S10 → S11. S8a after the gate (M7 grammar); S8b zones in
order. S7 on engineering release. One build lock: in a single session the slices run in the order S3, S4 (ring A segment gate, then
the rings), S5, S6, S9, S8a, S10, S11, each committed on its own.

**Progress model (measurable):** Phase 4 has twelve slices (S0–S11). A slice counts as complete when its "Done when" holds and its commit
is on the branch; a slice that ends at an owner review counts when the evidence is delivered, and the owner's acceptance is tracked
separately in the decision register. Percentages in reports are completed slices / 12, nothing else.

**Critical technical dependencies:** a Blender-equipped session (this cloud session installs the pinned Blender 5.2.2 and Godot 4.7.2,
section 4.1); the S2 shared-key rebuild of accepted M7; ring rotation and sweep checks (S4); radiator net area (S5); runtime draw ranges
and sharing (S11).

## 4. S0 and S1 results

### 4.1 S0 — production baseline

Run 2026-10-24 on this branch (run folders local, under `runs/`):
- **Environment limit:** Workbench and Eevee need an OpenGL/EGL context the container lacks (no GPU, no `libEGL`), so `--quality draft`
  and `material` previews and the Workbench section views cannot run here; `review` and `look` (Cycles) can.
- **Environment:** this cloud session installed Blender 5.2.2 LTS from the official archive (SHA-256 checked against
  `blender-5.2.2.sha256`) at `/snap/bin/blender`, Godot 4.7.2 through the project's own pinned toolchain (`tools/web_play.py`,
  SHA-512) at `/snap/bin/godot-4`, and the pinned MPFB and MakeHuman assets (`workflow.py deps fetch/install`). No Blender-dependent step
  is blocked any more. Cycles runs on 4 CPU cores (no GPU): ~10–15 s per 1280×720 frame at 24 samples.
- **Full pipeline gate** (`runs/20261024T093930Z-pipeline`): PASS in 235 s — 150 unit tests (1 skipped), build 37 s, whole-ship
  inspection, fingerprint diff **0 changed / 0 added / 0 removed** against `references/baseline_modules_phase3`. A from-scratch cloud
  build reproduces the committed baseline exactly. Rig contract 42, 36 assets, 237.0 m × 90.009 m deployed, radiator 5,555.556 m² per
  blade.
- **Packs:** `module validate` PASS for `m8_forward` (4,172 elements, 112,412 faces), `rad_frame` (155 elements, 930 faces) and
  `ra2_equip` (45 elements, 270 faces), no screen or envelope failures; `assembly validate` PASS for all six packs.
- **Before-set:** `runs/20261024T-p4-s0/before` (review quality, the standard preview views) and the S1 matched cameras with V0 (section
  4.2); M8.1 off/on stills and x-ray at the M8 cameras (`runs/20261024T-p4-s0/m8`).
- **Livery readback** (request Doc `2026-10-21T08:55`): no active G.U.C., GUC or `0.16c` string in code, data, Godot or web (every
  hit is a negation, the legal notice or the annotated GU-WF-001 test string of the NONCANON lettering study); the 51 generated
  production stencils contain none; the 37 saved `.blend` assets carry no retired label in any datablock name; the web pages and both
  web/native release contracts name `G.U. WAYFARER 001`; Godot HUDs read `WAYFARER 001`; the L1 band renders `GU WAYFARER 001`
  (`SH_M5_LETTERING_L1`, `_MID`, `renders/shots/`). Root invariants: crew 6 (LOCKED), 237.0 m overall (inspection), 0.016 c
  (source map). Typeface, material, placement and final livery stay visual review items; no physics hold changes.

**Candidate review (owner P4-CAND: deferred to this comparison; all three stay `L4_VISUAL_CANDIDATE`):**

| Candidate | Evidence | Strengths | Defects | Recommendation |
| --- | --- | --- | --- | --- |
| M8.1 `m8_forward` (= S1 V0) | validate PASS; M8 off/on stills; S1 V0 at every camera | one module per bay with the lane on the bay azimuth; ochre hatch inside a graphite doubler reads as a serviced interface; `C01` numeral (1.1 m) legible at bay distance | lane grey (0.32) and cladding (0.59) sit close, so the 12-spoke wheel barely reads past the bay; the 0.20 m hatch stencil is unreadable at the 13 m bay camera; cladding near the truss grey; fasteners invisible beyond ~20 m; whole-ship: the Brow aft face reads as one grey disc | **REVISE** in S3 (M8.2) with the selected grammar; keep the module logic, the bay/lane allocation and the doubler; do not reject |
| `rad_frame` | validate PASS (net area untouched: footprints only in non-emitting joints); `root_detail`, `joint_detail` stills; S1 whole-ship views | band clamps, gussets and the aft guard are credible and sit where the frames are | the 0.1–0.3 m fittings are invisible beyond ~30 m; the frame rhythm at ship scale comes from the blade's own frame lines, which only read once the cells are dark (S1 V0T) | **REVISE** in S5: keep the fittings as the close-up tier; carry the ship-scale rhythm with the middle structure value on the transverse frames against the dark COAST cell depiction |
| `ra2_equip` | validate PASS (rotation, route); interior overhead and cutaway stills; trays only in the 0.05 m overhead band (−2.90 to −2.85 m), 0.04 m from overhead items, 0.10 m from the hatch | follows the M7 value ladder (trays 0.26 machinery, boxes 0.45 service); no clearance cost; quiet, credible service layer | small (0.12 × 0.028 m) trays read as dark slots rather than equipment; close to overhead fit-out items | **KEEP** (accept as is); revisit spacing only inside the Z2 cultural pass (S8b) |

### 4.2 S1 — grammar experiment

`src/wayfarer/studies/p4_s1_grammar.py`, run `runs/20261024T-p4-s1` (1280×720, Cycles 24 samples; VA–VC+ re-rendered once after the
ship-wide structure family was extended to the generic `Structure` material). Owner review packet:
<https://claude.ai/artifact/JgmTkPa4YbgbsKcjpMbi41>.
Every variant's pure screen passes: the `m8_forward` pack checks (aft-face zone between skin and truss, chord keep-outs, Crown plate,
ribs, hatch, rim, beacons) and the ring frame/sweep (r 24.5–30.0 m, |u| ≤ 2.15 m) and sector pressure envelopes. No generated mesh,
parameter or canon changed.

**Matched cameras:** whole-ship three-quarter, side silhouette, rings three-quarter (between blades on the sun side), Brow sector, Crown
bay, human scale at the Crown hatch, functional cutaway (a function map in the m8_exterior x-ray convention: engineering clay, the layer
coloured by role), ring segment (the pressure segment of sector A3, the one farthest from the blades in the posed frame; every segment
carries the same module), human scale at the ring flank; COAST +2 EV editorial for all, the matched COAST/IGNITION pair for V0, VC and VC+. One sun 40° from aft, azimuth −20°
(presentation choice), no fill.

**Variants:**
- **V0** — M8.1 as built; hero look (proxy grey + M4 functional marks).
- **V0T** — V0 plus only the dark high-ε-looking COAST blade surface (OWN-P4-LOCKED (a)).
- **VA civic** — Brow: large calm cladding fields (≤ 6.5 m), lane flush, no visible fasteners or caps; Crown: one flush cover each side
  of the hatch; truss wrapped (light); rings: flush flank cladding over fill and pressure recess, amber band, 1.3 m IDs.
- **VB open machine** — Brow: cladding removed except the protected band; skin-back stiffeners, lane utility trays (0.30 × 0.14 m) and
  node plates exposed; Crown: plate stiffener grid; rings: joint webs, ribs, stringers and conduits exposed, no IDs.
- **VC restrained hybrid** — Brow: M8.1 cladding kept as the civic shell, the lane opened to its two utility trays with dark edge lines;
  Crown: access panels in shell value against the graphite doubler and ochre hatch, hatch stencil 0.35 m, numeral 1.4 m; rings: light
  cassettes on the flanks, a calm pressure-face panel in each recess, exposed mid-value joint caps with dark gaps every 15°, graphite spoke
  nodes with ochre covers, amber occupancy band, 0.9 m IDs.
- **VC+ expressive hybrid** — VC geometry; lighter shells (0.78), darker structure (0.22) and machinery (0.03); GU deep-blue lane-edge
  lines and a rim wayfinding stripe over each pressure segment; hatch stencil 0.45 m, numeral 1.6 m, bolder boundary stripes.

**Findings** (detail and images in the owner review packet):
1. **Ring legibility comes first from value, then from rhythm.** V0T alone (dark COAST blades) lets the light rings, Brow and spine
   separate from the blades in every whole-ship view; no geometry change is involved. The 15° joint rhythm (VC/VC+) then makes the rings
   read as assembled structures in the rings view; VA keeps them calm but smooth; VB makes them busy and darker than the Brow.
2. **At whole-ship distance VA–VC+ differ little**; the grammar shows at bay, segment and human distance. Hierarchy across the ship is
   carried by the material families.
3. **Crown bay:** VC/VC+ give the clearest functional read (light shell, graphite doubler, ochre hatch, readable stencil); VA hides the
   serviced interface (the hatch and doubler disappear under flush covers); VB is credible but noisy and loses the bay's calm field.
4. **Transfer to the pressure shell works for VC/VC+:** the same rules (shell where it protects, exposed joint where it attaches,
   ochre where it is serviced, amber where people live) produce a readable ring segment without new mechanisms.
5. **VC+ vs VC:** the expressive value step improves distance read and the blue wayfinding reads as navigation, not livery; at the
   human-scale cameras VC+ shells sit near the top of the +2 EV editorial range; the matched exposure is unaffected. The side silhouette
   still shows the rings edge-on: there the gain comes only from the dark blades and the darker structure tier.
6. **IGNITION parity:** the 1800 K emission is unchanged (peak 223 vs 222 8-bit, V0 vs VC+); only reflected sunlight on the blade face
   drops with the darker base (mean frame luminance −5 %).

**Recommended grammar (a recommendation, not a selection): VC+ geometry with values between VC and VC+.** Expressive functional
hybrid: civic light shells on the Brow back and pressure faces with large calm fields; exposed mid-value structure at segment joints,
truss nodes and lane edges; graphite machinery at serviced interfaces (doubler, spoke nodes, trays); ochre service, amber occupancy, GU
deep blue only for lane edges and pressure-segment wayfinding; the dark high-ε COAST blade depiction; text-only markings sized by
distance (bay numeral ≥ 1.4 m, hatch stencil ≥ 0.35 m, ring IDs ~1.0 m; fasteners only in the close-up tier). Proposed exterior value
ladder (linear base colour): shell 0.70–0.78, structure 0.22–0.30, machinery 0.03–0.08, thermal 0.02–0.035.

**Unresolved artistic decisions blocking rollout:** (1) the grammar (VC, VC+ or the recommended blend); (2) value strength (VC vs
VC+ ladder); (3) GU deep blue as a standard wayfinding accent or not; (4) the three candidate dispositions above.

### 4.3 S2 — grammar codification (2026-10-24)

- **Implemented:** `[production.exterior]` in `data/wayfarer_3d.toml` (source `p4_exterior_grammar` → Art Style Spacecraft row 19):
  material families `xf_*` inside the owner's ranges (shell 0.73, structure 0.25, machinery 0.05, thermal 0.028), scale tiers with
  draw ranges, minimum feature sizes and bevels, shell panel/seam/joint rules, the calm-field rule, the marking scale (cap height for
  20 px at each class's reading distance), the accent budget and the wayfinding uses, and the ship-material → family mapping.
  `production_detail.py`: `marking_height`, `tier_of`, `area`, `accent_report`, `ship_family`; `material_value` resolves the families.
  `hero_preview.dress(grammar=True)`: the grammar look (dark COAST blade depiction included; production layers keep their finishes).
  `presentation/p4_review.py`: the review set (13 matched views + the COAST/IGNITION pair) and before/after sheets. Interior preview
  captions moved in front of the scene on a dark band (they overlapped the geometry in the overhead view).
- **Reusable component families (only those two or more packs need):** marking sizing, accent measurement and the family materials
  (every exterior pack); the 15° ring segment module (both ring packs, S4) goes into a shared pure module when S4 builds it. No universal
  kitbash library.
- **Preserved:** geometry diff 0 changed / 0 added / 0 removed against `baseline_modules_phase3` (`runs/20261024T-p4-s2-gate`, PASS);
  accepted M7 unchanged by construction (`[production.materials]`, `[look.surfaces]` and the M7 stills' code untouched; the grammar look
  is opt-in, so every existing still renders as before); 1800 K IGNITION emission unchanged (matched pair).
- **Evidence:** `runs/20261024T-p4-s2-before` (pre-Phase-4 hero look) and `runs/20261024T-p4-s2` (grammar look), 1600×900 Cycles 48
  samples, with before/after sheets in `runs/20261024T-p4-s2/pairs`. Whole ship: the dark blades now separate the light spine, rings and
  Brow; the Brow aft face reads as a 12-spoke wheel; the rings read light against the dark blades in the rings view; IGNITION keeps its
  emission and the hull reads darker against it.
- **Maturity:** the grammar is canon in Art Style row 19; the code is PROTOTYPE presentation; no asset changed maturity.

### 4.4 S3 — forward production: M8.2 (2026-10-24)

- **Implemented** (`m8_forward`, revision M8.2; M8.1's bay/module construction kept): materials moved to the shared families
  (`[production.m8.materials]` retired); the service lane became a mid-value deck with GU deep-blue boundary lines and exposed graphite
  utility trays on brackets; fasteners only on the serviced lane deck and the Crown panels/doubler (Brow cladding fields calm, 864 + 360
  fasteners instead of 3,072); Crown access panels light against the graphite housing; protected-band edge a dark closeout instead of
  amber (amber is reserved for occupancy); markings sized by `marking_height`: Brow sector IDs 1.06 m, lane label 0.48 m, bay numeral
  1.38 m, hatch stencil 0.28 m (band-capped), boundary half-stripes 0.24 m. 2,924 elements (M8.1: 4,172); accent shares blue 1.7 %,
  ochre 0.3 %.
- **Preserved:** pack screens (aft-face zone between skin and truss, chord keep-outs, Crown plate, ribs, hatch, rim, beacons) and the
  envelope PASS (the Brow envelope widened 0.18 m aft for the trays, 3.5 m short of the truss); `module validate` readback PASS; full
  pipeline PASS (`runs/20261024T-p4-s3-pipeline`: all tests, whole-ship and forward inspection, fingerprint changes only in the M8
  detail assets: fasteners, markings, new lane lines and trays); the 90 m silhouette, EYE wells, Crown mechanisms, sunward face and Lance
  untouched. New baseline `baseline_p4_s3_m8_2`.
- **Evidence:** `runs/20261024T-p4-s3` (whole ship, rings view, Brow sector, Crown bay, human scale) with before/after sheets against
  the S2 grammar look in `runs/20261024T-p4-s3/pairs`.
- **Not done here:** the ram-face tile-and-repair appearance (OWN-P4-LOCKED (b)) is a shader/texture effect and moves to S9, where the
  Godot parity check lives.
- **Maturity:** `L4_VISUAL_CANDIDATE`; the owner reviews M8.2 (request Doc remainder).

### 4.5 S4 — habitat ring exteriors (2026-10-24)

- **Implemented:** packs `ring_a_exterior` and `ring_b_exterior` with the shared segment module `ring_exterior.py` (WF-HABITAT): per 15°
  segment and flank, light shell cassettes, mid-value joint caps over dark joint gaps (the frame rhythm), graphite spoke-node housings
  with ochre covers, calm pressure-face panels in the recess, amber occupancy bands, text-only sector IDs (1.06 m) with a GU deep-blue
  identifier bar. Ring A segment gated first (`runs/20261024T-p4-s4a`), then both rings. 246 elements per ring; accents blue 0.06 %,
  amber 1.3 %, ochre 0.6 %. Each ring's detail is two flank assemblies (+u, −u) so its claimed envelope stays off ring A's crew-tube pack
  (an annulus does not fit one box).
- **Preserved:** no size, position or motion change; every element inside r 24.5–30.0 m and |u| ≤ 2.15 m (sweep), outside the frame
  body and the sector pressure envelopes; full pipeline PASS including the rotation inspection (`runs/20261024T-p4-s4-pipeline`; the
  fingerprint adds only the four detail instances); baseline `baseline_p4_s4_rings`.
- **Evidence:** `runs/20261024T-p4-s4` (whole ship three-quarter and side, rings view, ring segment, human scale; COAST/IGNITION pair)
  with sheets against S3 (`pairs_vs_s3`) and against the pre-Phase-4 look (`pairs_vs_pre`). At segment and human scale the rings read as
  assembled modules; in the rings view the joint rhythm and IDs read on the flank; in the side silhouette the rings stay edge-on (owner:
  accepted geometric reality), separated from the dark blades by value.
- **Maturity:** `L4_VISUAL_CANDIDATE` (both packs). The hub read from outside (HERO tier) is not detailed in this pass.

### 4.6 S5 — radiator frames and roots (2026-10-24)

- **Tried first and withdrawn:** mid-value seam bands over the 0.125 m bay joints. They duplicated the generated joint bead
  (`Blade_Expansion_Joint`) and added nothing at 35 m or ship scale (`runs/20261024T-p4-s5-pipeline`, superseded).
- **Implemented:** the larger structural rhythm by value, not by size. The radiator generator gives the transverse frames and edge chords
  their own display material `BladeFrame` (same review colour as `Structure`; no geometry change); the grammar maps `BladeFrame` and the
  joint beads to the new light family `xf_frame` (0.58) over the dark thermal sheet (0.028), so every frame station reads as a line
  across the blade and the chords outline it. `rad_frame` keeps its clamps, gussets and aft edge guard as the close-up tier, now in the
  shared families (clamps graphite, the rest structure).
- **Root interfaces:** the M4 root construction (boots, flanges, chase plate, saddles, stops) already shows the load path and the
  thermal break; in the grammar the boots read off-white (`xf_root`) against the structure-value booms and the light casing. No new
  `rad_root` pack: nothing purposeful to add without implying an unqualified mechanism (H120). Revisit with the owner if wanted.
- **Preserved:** geometry diff empty (`runs/20261024T-p4-s5b-pipeline`, full PASS with the thermal inspection: net hot area
  4,978.17 m² per face per blade, unchanged); cells, emissivity assumption, expansion joints and travel untouched; IGNITION 1800 K
  emission unchanged (matched pair).
- **Evidence:** `runs/20261024T-p4-s5` (whole ship, rings view, blade clamp, aft edge, 35 m, root; COAST/IGNITION pair), sheets against S4
  (`pairs_vs_s4`) and S2 (`pairs_vs_s2`). The frame lines read clearly at 35 m and as a fine rhythm at ship scale; the 0.2 m tubes stay
  thin at whole-ship distance.
- **Escalation (art/engineering trade, owner's call):** a stronger ship-scale frame read would need geometry in front of the radiating
  sheet (for example off-white thermal wraps on the transverse frames). That changes the blade's physical view factor, so it is not done
  without the owner and the thermal owner.
- **Maturity:** `rad_frame` stays `L4_VISUAL_CANDIDATE`; the revision goes to the owner for review.

## 5. Risks

- **Visual drift across parallel sessions:** S2 codifies the grammar before the fan-out; the coordinator reviews every pack against the
  same cameras.
- **Shared-key rebuild touching accepted M7:** S2 runs the full gate and compares the M7 stills.
- **Detail that implies engineering** (Crown mechanism OD-021, ring shielding, radiator coatings): depiction-only rule, labels,
  OWN-P4-LOCKED.
- **Over-detailing:** scale tiers and negative space; whole-ship review first.
- **Runtime cost:** draw ranges and mesh sharing; desktop Godot measurement in S11.
- **Cloud environment:** each cloud session must install the pinned Blender (official archive, SHA-256 checked) and Godot
  (`tools/web_play.py` toolchain) before modelling; CPU-only Cycles limits samples.
- **Drive-reader agents** cannot reach Drive in cloud sessions (their allowlists name another environment's connector IDs); bounded
  Drive reads run in the main conversation.

## 6. Decision register

| ID | State | Remaining |
| --- | --- | --- |
| P4-EXP, P4-MAT, P4-LOCKED, P4-SCOPE, P4-STATE, P4-INT | answered 2026-10-24, canonicalized (section 0) | none |
| P4-ART | answered; **S1 art gate 2026-10-24: VC+ moderated selected** (Art Style Spacecraft row 19) | none |
| P4-CAND | answered; **S1 art gate 2026-10-24: M8.1 REVISE (S3), `rad_frame` REVISE (S5), `ra2_equip` RETAIN** | owner acceptance: `ra2_equip` now (request Doc remainder); M8.2 and the `rad_frame` revision when presented |
| Promotion | every squash to `main` needs the owner's approval | open for this branch |
