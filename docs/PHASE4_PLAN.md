# Phase 4 plan: visual production, art direction and modular detailing

**Status: STAGE A, a draft for the owner.** No Phase 4 slice is authorized yet. This plan models nothing, changes no parameter and
promotes no candidate. The owner decisions are in the request Doc "IGNITION — Wayfarer Claude Request", packet
`2026-10-24T10:55+02:00 — P4` (section 6). Stage B starts only after the owner answers and authorizes it. Then this file is revised
and stays the single Phase 4 plan. Commands and contracts are in AGENTS.md, docs/MODULES.md and docs/IMPLEMENTATION.md.

## 1. Baseline (Deliverable A)

**Inspected sources:**
- Repository: `main` 15997fe (2026-10-24 06:35 UTC, MOD-010).
- Web release: `web-20261024-15997fe`. Its viewer GLB is the COAST snapshot: 741,424 triangles, 14 assembly groups.
- Drive, read 2026-10-24 08:20–08:50 UTC:
  - TOC `01_WORKBOOKS`, `03_DOMAIN_ROUTING` and `98_CHANGE_PROTOCOL`.
  - S&E `15_MODEL_INTERFACES` rows A1, A119:A121 and A196:A227, the last row being OWN-M6-FOCUS.
  - S&E `09_OPEN_DESIGN_ITEMS` OD-001..041 and `48_WORKFLOW_GATES` WF-017..025.
  - Art Style Bible `Spacecraft` rows 1–17, `Anti-Rules`, `Objects & Tech` and `Architecture`.
  - Culture `31_ARCHITECTURE` and `43_TERMS_SYMBOLS`.
  - Model Status `Implementation` rows 1–32.
  - The request Doc. Its only open item is `2026-10-21T08:55+02:00`, livery consistency. That item is applied in the
    repository (a5ceda2), but the rendered readback is still pending.

**What the ship is now.** The ship is one REP_PROXY engineering model. All production detail sits in switchable layers over it:
- **Body and bow:** a 225 m body (13 m diameter) and a 12 m Dust Lance, 237 m overall. The 90 m Brow carries a twelve-sector Aegis
  Crown and four recessed EYE wells. EYE layout r4 is WORKING; r16 and r24 are studies.
- **Rings:** two counter-rotating rings, 60 m in diameter, sit immediately aft of the Brow. Each is its own asset, `WF_HABITAT_A` and
  `WF_HABITAT_B`.
- **Thermal and drive:** three fixed 182.149 m × 30.5 m blades run at 1800 K. A thrust ring carries four magnetic nozzles.
- **Exterior hardware:** two Ka dishes, an optical terminal and the RCS pods.

**Accepted grammar (owner):**
- **M4 constructed exterior** (15!A202, Art Style Spacecraft row 16): 15° ring frames with webs and inspection covers, muted amber
  bands over pressurized sectors, ochre service covers, off-white radiator root boots, grey saddles and stops, and dark joints.
  Hierarchy comes from silhouette, framing and exposure. The 1800 K emission is never dimmed.
- **M5 hologram look** (15!A220).
- **M7 interior production section** (`L4_VISUAL_ACCEPTED`): its value ladder of inhabited, service, machinery, structure and seams
  is the production standard.
- **Lettering** (15!A216, A225): restrained uppercase industrial sans. The working stencil "GU WAYFARER 001" is preferred; it is not a
  registry and carries no crest.

**Packs** (docs/MODULES.md):

| Pack | Content | Maturity |
| --- | --- | --- |
| `m7_spine`, `ring_a_transfer`, `m7_ra1` | the M7 route from the port to ring A sector 1 | `L4_VISUAL_ACCEPTED` |
| `m8_forward` | M8.BROW.AFT and M8.CROWN.RIM: aft-face panel modules, service lanes, the graphite hub band, doubler frames, access panels, closeouts and markings on all 12 Crown bays | `L4_VISUAL_CANDIDATE` |
| `rad_frame` | band clamps, gussets and an aft guard on all three blades (shared mesh) | `L4_VISUAL_CANDIDATE` |
| `ra2_equip` | ring A sector 2 overhead cable trays | `L4_VISUAL_CANDIDATE` |

Ring B, the drive, fuel, EYE and the utility modules have no pack. Ring B has anchors but no detail.

**Engineering construction already in the generators** (S04 slices 1–4): casing joint straps and access panels, Brow aft-face panel
joints, forward collar straps and the thrust-ring diaphragm plates.

**Visual assessment.** This comes from the release viewer (captures listed under Evidence below) and the M7/M8 review packets.
- **Strong, keep:**
  - The thrust-axis hierarchy, read in plan: Lance, Brow, rings, blades, nozzles.
  - The fixed three-blade thermal identity.
  - The M4 colour grammar: ochre service, amber occupancy, dark joints.
  - The M7 value ladder.
  - The M8 Crown bay logic, one module per bay with a service lane on its azimuth.
  - The modular pack, anchor and contract system.
- **Too primitive or generic:**
  - The rings read as smooth white tori: no frames, shell panels or hub machinery at ship scale.
  - The Brow ram face is one undifferentiated cream disc, although the Art Style canon names regenerative-shield surface language
    and subtle repaired patches.
  - The spine reads as a plain tube between the blades.
  - The nozzles are simple bells. They are physics-locked (Q40), so they correctly stay simple for now.
- **Hierarchy:**
  - The blades are about 5,000 m² each. From the side and three-quarter views their area dominates every other read, and the rings
    disappear between the Brow and the blade roots.
  - Their area is physics-locked. Hierarchy must therefore come from surface value, structure rhythm, lighting and camera, never from
    shrinking them.
- **Invisible at use distance:**
  - `rad_frame` fittings (its own self-review agrees).
  - The 0.20 m M8 hatch stencil.
  - Most S04 straps at whole-ship scale.
- **Missing construction:**
  - Assembly divisions on the ring shells.
  - Hub, bearing and drum machinery read from outside.
  - Blade root saddles and coolant manifolds at the scale the camera sees.
  - Spine casing modules between the frame stations.
  - Service routes the eye can follow.
- **Material differentiation:**
  - Everything physics-locked is proxy grey (15!H120), and there are no texture maps.
  - The off-white M8 cladding sits close to the truss grey (M8 self-review).
  - The web viewer draws the blades in pastel diagnostic colours, which does not match the Blender COAST look. This is a presentation
    parity issue, not a model issue.
- **Engineering conflicts:** none found in the accepted or candidate packs. All of them pass contracts, BVH and route margins.

**Pipeline capability:**
- Detail packs with stable anchors, envelopes, pack contracts and switches.
- Committed `.glb` authored meshes with hash and anchor pinning (none committed yet).
- `pipeline --quick` with scoped inspection, and the full pipeline as the gate.
- Draft, material, review and look previews, and `m8_exterior` before/after stills.
- `runtime-export` with per-pack draw ranges, and the web export.

**Pipeline gaps:**
- No shared material library: S03 is parked on the owner.
- No texture or UV workflow: M7 uses flat values.
- No wear or repair layer.
- No hero lighting rig beyond the `hero_preview` COAST/IGNITION pair.
- **This cloud container has no Blender or Godot.** Stage B modeling needs a Blender-equipped session: the workstation, or a cloud
  environment whose setup installs Blender. Planning and Drive work do not.

### Visual Design Freedom Map

| Class | Assemblies | Phase 4 may | Phase 4 may not |
| --- | --- | --- | --- |
| Engineering-locked (physics) | blade planform, cells and 1800 K emission; drive core, manifold and nozzles (Q40); EYE apertures and optics (r4 WORKING, r16/r24 study only); Dust Lance and field (OD-017/018); Brow thickness and stack (OD-014/019); pressure shells, hatches, seals and closures (OD-034); rotor interface and bearings (OD-013) | show existing seams and load paths; depiction-only surface finish **if the owner allows it** (Q P4-LOCKED) | change area, emission, radius, apertures or clearances, or hero-finish an unqualified interface (15!H120) |
| Functionally constrained working geometry | Crown sectors, carriages and shutters (OD-021); radiator roots, saddles and frames (OD-007/039); ring frames and spokes (OD-016); exterior hardware S02; crawler lane and service routes (50!AG-A02); docking port (Q33) | clad, frame and mark within the anchor envelopes; make the mechanisms legible | imply a qualified mechanism, rating, rail (RUN-011) or new opening |
| Artistically flexible | cladding modules, panel rhythm, fasteners, closeouts, markings and stencils, value and material hierarchy, interior fit-out, lighting, camera, wear placement | design freely within HSFP and the Art Style Anti-Rules | add greebles, fins, neon, decorative glow, panoramic windows or random grime |
| Blocked by HOLD | WF_STORAGE tanks (OD-026, 15!A224); aft robotic cradle and HGA ORU (15!A225); workshop (OD-030); r16 EYE geometry; flight EVA rails | nothing beyond the existing study layers | build production detail on them |
| Accepted production assets | M7 (six assemblies, three packs) | extend the M7 language; correct only on owner request | restyle them to fit a new direction |
| Candidates awaiting review | M8.1 (`m8_forward`), `rad_frame`, `ra2_equip` | fold them into the first experiment as its baseline variant | accept them, or replace them without a decision |

## 2. Design direction

**Research lessons.** These are methods, not shapes to copy. No proprietary asset or distinctive design is reused.

| Reference | Lesson for Wayfarer | Licence note |
| --- | --- | --- |
| [ISS Integrated Truss Structure](https://en.wikipedia.org/wiki/Integrated_Truss_Structure): segments, utility runs, rail | A truss reads as an assembly when its segment joints, utility trays and transport rail are distinct, repeating elements. Use this for the spine and the blade roots. | facts and photos only, as reference |
| [ITER blanket modules and remote handling](https://www.iter.org/node/2752) ([design paper](https://www-pub.iaea.org/MTCD/publications/PDF/csp_008c/pdf/iter_5.pdf)) | Many identical, replaceable, bolt-on modules with a visible handling interface and manifold side make a repairable protective wall: an analogue for the Brow and Crown bay construction. | reference only |
| [Beta cloth](https://en.wikipedia.org/wiki/Beta_cloth) and [NASA MLI guidance](https://ntrs.nasa.gov/citations/19930015285) | Protective blanket families (white woven covers, stitched seams, vent and closeout lines) give pressure volumes a soft, legible "institutional shell" against hard machine parts. | public-domain NASA documents |
| ISS ORUs and the [Mobile Servicing System](https://en.wikipedia.org/wiki/Mobile_Servicing_System) | Robot-serviceable units share standard grapple fixtures, alignment marks and handling colours: a GU standardization grammar the drones (DRONE-001) can justify. | reference only |
| *The Expanse* production design ([ArtStation interview](https://magazine.artstation.com/2016/02/scenes-concept-art-expanse/)) | Fix the side-view proportions first; add wear and texture to unchanged architecture in later seasons. Silhouette before surface; history as a later layer. | method only; no designs copied |
| Interstellar, 2001, Alien, Elite Dangerous, Star Citizen | Scale through restrained surface rhythm against large calm fields. Interactive LOD keeps the silhouette and drops micro detail. Kitbash libraries pay only once a family repeats. | method only |

**The three candidate directions against the actual model:**
- **A, Civic Monumentalism** (enclosed standardized GU cladding). It fits the Brow and the rings, and GU "Order" with prefabricate,
  standardize, assemble (Culture 31). On its own it hides the very consequences HSFP wants visible. The ship would read as a smooth
  liner, the "sleek yacht" the Spacecraft canon forbids.
- **B, Open Machine** (exposed frames and mechanisms). It fits the Crown, the roots, the spine truss and the drive region, and the
  Robocracy and Bolt-Sworn layer of request Doc §13. On its own it turns into uniform greeble (Anti-Rule "everything equally
  detailed").
- **C, Thermal Leviathan** (thermal architecture as the dominant identity). The blades already are the largest element. It is
  legitimate only through structure rhythm and physically motivated surface value: real 1800 K emission in IGNITION and no fake glow
  in COAST.

**Preliminary recommendation (not approved): a controlled hybrid allocated by function.** Working name: *GU shell, honest machine*.
- **Pressure volumes and the Brow ram face:** civic shell (A). Calm modular cladding and blanket families, GU markings, large
  negative space.
- **Interfaces:** open machine (B). The Crown carriages and shutters, ring hubs and drums, blade roots and saddles, spine truss
  nodes, the thrust ring, docking and the service lanes.
- **Blades and drive region:** thermal leviathan (C). Expressed by frame rhythm, dark high-emissivity surface value and true emission
  only.
- **Value hierarchy across zones:** light shells, mid-grey structure, dark machinery and thermal. Colour stays at functional accents:
  ochre service, amber occupancy, GU blue wayfinding, safety orange inside.

Deciding this is question P4-ART.

## 3. Slice plan (Deliverable B)

**Execution order:** baseline, then the visual experiment, the selected grammar, reusable detail, subsystem integration, look
development and the whole-ship review. P4-A..L in the brief are workstreams; they map onto twelve executable slices (S0–S11). Each
slice owns one pack set and follows the AGENTS.md loop:
- `module show`, then `pipeline --quick --target auto --expect Prod_ Detail_ WF_DETAIL [--inspect auto]` while iterating;
- the full pipeline before commit;
- `module publish`;
- new work stays `L4_VISUAL_CANDIDATE` until the owner reviews it.

Every slice keeps the switch-off empty geometry diff, the silhouette radius, BVH and route margins, and adds no mass key.

**Review set.** Every slice reviews this set, unless it names a smaller one:
1. whole-ship three-quarter;
2. side silhouette;
3. subsystem three-quarter;
4. human-scale close-up with a 1.78 m figure;
5. cutaway;
6. COAST cinematic, matched and +2 EV editorial (15!A222).

**Human review criteria:** silhouette and hierarchy, originality, mechanical credibility, manufacturing logic, scale, material
consistency, GU and IGNITION identity, close-up quality, reuse and cost. No numeric art gate.

**Common definition of done:**
- the slice's deliverable is built behind its switch;
- the full pipeline PASS shows only the expected prefixes, and `module validate` and `assembly validate` pass;
- `runtime-export` passes where the runtime is touched;
- the review set is rendered and self-reviewed;
- MODEL, TODO and the Model Status row are updated;
- the owner review is requested.

### S0 — Production environment and before-set (P4-A) · Low

- **Objective:** a Blender session and a frozen "before" reference set, so every later slice is compared against the same images.
- **Baseline:** 15997fe with the M7/M8 stills from 2026-10-20.
- **Sources:** 15!A222 exposure rules.
- **Owns:** no pack. The run folders it writes are local.
- **Read-only:** everything else.
- **Constraints:** none new.
- **Freedom:** camera choice for the six standard views.
- **Technique:**
  - render the review set at `--quality review` from the saved assets;
  - render the web viewer at the same cameras to log the material parity gap;
  - read back the livery item `2026-10-21T08:55` (stencil and label scan) and close it per protocol if it passes.
- **Reusable:** a fixed camera list in `shots/` for every later slice.
- **Validation:** the preview run alone; no build.
- **Parallel:** first; it blocks only the image comparisons.
- **Done when:** the before-set exists and the livery item is verified or reported back.

### S1 — First experiment: Crown bay and Brow aft sector grammar (P4-A/B) · Medium–High

Deliverable D is section 4. The experiment produces comparative variants in an `ART_*` or study collection, plus a short
transfer probe on one ring A 15° segment. Its output is a written design grammar, with no production rollout.

### S2 — Codify the selected grammar (P4-A/I) · Medium · integration-owned

- **Objective:** turn the selected S1 variant into shared, reusable parameters, so the subsystem packs speak one language.
- **Baseline:** `[production.entry]` (the M7 panel grammar), `[production.m8.materials]` and `production_detail.py` helpers.
- **Owns:** WF-CORE, one writer: `[production]` shared keys, `production_detail.py` (new helpers only if two packs need them), and
  `[production.materials]`.
- **Read-only:** all packs.
- **Constraints:**
  - a shared-key change rebuilds every reader, and accepted M7 must stay pixel-equivalent, or the change is reported;
  - no mass key.
- **Freedom:** naming, value steps, scale tiers.
- **Technique:** add exterior grammar keys alongside the existing ones:
  - panel module tiers (macro bay, meso panel, micro fastener) by view distance;
  - closeout and doubler dimensions;
  - the marking type scale;
  - the material family table.

  Decide on a part library only if S1 shows a family repeating enough that measured sharing pays (TODO MOD deferral).
- **Reusable:** the grammar itself.
- **Validation:** full pipeline, all packs rebuilt, M7 stills compared.
- **Parallel:** must precede S3–S6.
- **Done when:** the shared keys exist, M7 is unchanged or the change is explained, and the grammar is documented in MODEL.

### S3 — Forward production: Brow and Crown rollout (P4-B) · Medium · WF-FWD

- **Objective:** apply the selected grammar to the whole Brow aft face and all twelve Crown bays, as M8.2.
- **Baseline:** M8.1 (all 12 bays) plus the S1 corrections.
- **Sources:** Eye 45, S&E 50, OD-020/021.
- **Owns:** `m8_forward` (data, code, glb).
- **Read-only:** `forward_shield.py`, EYE.
- **Constraints:**
  - r ≤ 45.0 m;
  - nothing on the sunward side of the skin;
  - shutters, carriages, emitters, launchers, ports, windows and EYE wells untouched;
  - the crawler lane stays clear;
  - OD-021 stays open: detail must not finalize the mechanism.
- **Freedom:** cladding, closeouts, markings, lane treatment.
- **Technique:** procedural modules per bay with a stable seed per bay. Authored `.glb` is used only for the one hero carriage cover,
  if S1 selects one.
- **Ram face:** only if P4-LOCKED allows it — a depiction-only material or normal pattern for the regenerative tile field and a few
  repair patches, no geometry.
- **Reusable:** the bay module and the doubler and closeout families.
- **Validation:** `--inspect forward`, `m8_readback`, BVH.
- **Parallel:** yes, with S4, S5 and S6 after S2.
- **Done when:** all bays are rebuilt in the grammar and the review set shows the Brow and Crown hierarchy at whole-ship distance.

### S4 — Habitat ring exterior (P4-C) · High · WF-RING-A, then WF-RING-B

- **Objective:** M8.2 ring outer shells.
- **Content:**
  - the 15° segment frames;
  - shell panel modules and blanket families over pressurized sectors, with the amber occupancy band integrated;
  - spoke collars;
  - hub and bearing housings read from outside;
  - sector numbers.
- **Baseline:** smooth ring tori; the M4 15° frames, webs and inspection covers are in the generator.
- **Sources:** S&E 08, 12, 15 R-rows, OD-003/013/016.
- **Owns:** new packs `ring_a_exterior` (anchor `WF-RING-A.ROTOR.1`) and later `ring_b_exterior` (`WF-RING-B.ROTOR.2`), one session
  each.
- **Read-only:** `habitat_ring.py`, `revision.ring_asset`.
- **Constraints:**
  - detail inside the existing outer-skin envelope;
  - ring sweep clearance to the Brow, the blade roots and the other ring kept (`--inspect rotation`);
  - motion inherited from the rotor;
  - nothing claims shielding, mass or balance.
- **Freedom:** panel rhythm, blanket versus hard-shell split, markings.
- **Technique:** one 15° segment gated first, then a procedural repeat, with stable seeds per segment so local edits do not reshuffle
  the ring. Ring B mirrors the selected grammar with its own sector program.
- **Reusable:** the segment module, which both rings instance.
- **Validation:** `--inspect rotation route`; runtime-export, because the rings move.
- **Parallel:** ring A and ring B in separate sessions once segment 1 is accepted.
- **Done when:** both rings read as assembled pressure structures in the side and three-quarter views, and the motion checks pass.

### S5 — Thermal roots and blade frames (P4-E) · Medium · WF-THERMAL

- **Objective:** make the thermal architecture legible at ship scale: root saddles, boots and coolant manifolds; frame rhythm that
  reads at distance (a revision of `rad_frame`); and the aft edge guard.
- **Baseline:** `rad_frame` (candidate); the M4 root boots and saddles in the generator.
- **Sources:** 40_THERMAL, OD-007/012/023/039, 15!A204 (Y155 radiator scenario).
- **Owns:** `rad_frame` and a new `rad_root` pack (anchor `WF-THERMAL.THERMAL.ORIGIN` or `RADIATOR.ORIGIN`).
- **Read-only:** `thermal_geometry.py`, `radiator_net_area.py`.
- **Constraints:**
  - every footprint stays in non-emitting bay joints or beyond the blade ends (the net area is unchanged);
  - root expansion travel stays clear;
  - no hot-face finish unless P4-LOCKED allows it;
  - IGNITION emission unchanged.
- **Freedom:** frame scale and value, manifold routing appearance.
- **Validation:** `--inspect thermal`, `radiator_net_area` unchanged, HIGH_POWER preview.
- **Parallel:** with S3, S4 and S6.
- **Done when:** the blades read as framed thermal machines in COAST and the IGNITION read is unchanged.

### S6 — Spine casing, service routes and exterior equipment (P4-F) · Medium · WF-SPINE

- **Objective:**
  - casing modules between the frame stations;
  - legible service routes, drone tracks and lanes, shown as existing study routes only;
  - the S02 hardware look pass: dishes, the optical terminal, RCS pods, strobes and docking aids.
- **Baseline:** the S04 straps and panels, S02 slices 1–2, M7.EXT.PORT.
- **Sources:** 14_HULL_SERVICE, 37 F14–F17, 51–54, 15!A213/A225.
- **Owns:** a new `spine_casing` pack (`WF-SPINE.HULL.ORIGIN`). The equipment look goes through the S02 generator as an integration
  edit, or through a small `ext_equipment` pack if the anchors allow it.
- **Read-only:** `hull_geometry.py`, `casing_panels.py`, `exterior_hardware.py`.
- **Constraints:**
  - no new opening, rail (RUN-011), cradle or HGA ORU (HOLD);
  - EVA handrails stay parked;
  - the docking port Q33 is unchanged;
  - plume and ring-sweep exclusions are kept.
- **Validation:** `--inspect hull route`.
- **Parallel:** with S3, S4 and S5.
- **Done when:** the spine reads as a serviced keel between the blades, with routes the eye can follow.

### S7 — Propulsion-adjacent structure (P4-G) · Low–Medium · WF-DRIVE · mostly blocked

- **Objective:** only what is released: the thrust-ring exterior (diaphragm plates exist), the aft collar and shadow-shield cladding,
  and service closeouts.
- **Kept simplified:** the nozzles, coils and plasma path (Q40, OD-024/025); the nozzle support topology stays the L2 study
  (15!A214/A226).
- **Owns:** a new `drive_aft` pack, if anything is releasable.
- **Constraints:**
  - plasma, field and plume keepouts;
  - no change to the yoke, bore or support.
- **Parallel:** late.
- **Done when:** the aft end matches the grammar without implying a solved drive.

### S8 — Human-scale path: ring B transfer and interiors (P4-D/H) · Medium each

- **S8a, ring B M7-equivalent path:**
  - **Content:** the drum lining, crew tube and first sector overhead on ring B, in the accepted M7 language.
  - **Owns:** new packs `ring_b_transfer` and `m7_rb1` (WF-RING-B).
  - **Constraints:** ring B rescue and closure HOLDs (15!A197, OD-032/034/040); route margins unchanged.
- **S8b, cultural architecture pass** (request Doc §13, Culture 31):
  - **Zones:** the zones the owner selects (P4-INT), each after its human-scale review.
  - **Language:** Spacer *Contain* shell, GU *Order* wayfinding and standardized interfaces, Bolt-Sworn *Humanize* insertions where
    crew live.
  - **Owns:** new interior packs per zone.
  - **Constraints:** fit-out never changes a pressure boundary, an interface or route clearance; SERV-STRIPS 0.60 m stays
    shirt-sleeve only.
- **Validation:** `--inspect route`, the route sweep, the Godot walk.
- **Parallel:** S8a with anything; S8b after P4-INT.
- **Done when:** the selected interior zones pass human-scale and cultural review.

### S9 — Materials, markings and wear (P4-I) · Medium–High · integration-owned

- **Objective:** the whole-ship material library (S03 unparked), the GU marking system and an optional wear and repair layer.
- **Material families:** shell cladding, blanket, structure, machinery, thermal and the accents.
- **Markings:** the L1 name band, sector and bay numbers, service, hazard and keep-out stencils, robotic handling marks.
- **Wear and repair layer:** switchable, placed only at touch, load and repair points; repaired Brow patches if P4-STATE wants them.
- **Baseline:** `[look]`, `[production.*.materials]`, `m5_lettering`, SURFACE_BRIEF.
- **Sources:** Art Style Spacecraft rows 14–17 and Anti-Rules; Culture 31/43; 15!A216/A225.
- **Owns:** WF-CORE material keys and `look.py` (one writer).
- **Constraints:**
  - no G.U.C. on the Y155 hull and no invented registry or crest;
  - no unsupported coating claim;
  - no 1800 K change.
- **Technique:** physically based families with roughness, value and emission. Baked or procedural texture only where a measured
  view benefits. Moving lights stay correct, so no static lighting is baked into textures.
- **Validation:** previews at `review` and `look`; runtime parity in Godot and the web viewer.
- **Parallel:** starts after P4-MAT, beside S3–S6. The material key file has one writer.
- **Done when:** every exterior zone uses a library family, markings are legible at their intended distance, and wear is switchable.

### S10 — Look development and hero renders (P4-J) · Medium

- **Objective:** a COAST and IGNITION lighting rig and a hero shot list from the Tale: S004 induction, departure, First Ignition,
  survival damage and return. The matched and editorial pairs are kept.
- **Owns:** `presentation/` hero scripts and `shots/`.
- **Constraints:**
  - no impossible dimming;
  - concept fill is labelled ILLUSTRATIVE;
  - unreleased attitude, thermal clock and mission positions are never invented (K05).
- **Parallel:** after S3–S6 have a first pass.
- **Done when:** the agreed hero set renders reproducibly and the owner reviews it.

### S11 — Runtime integration, performance and whole-ship review (P4-K/L) · Medium

- **Runtime:**
  - per-pack draw ranges and LOD;
  - instance and mesh sharing verified in the export;
  - web viewer material parity;
  - frame time measured in representative views on real hardware (TODO P05) before and after, reported measured, not estimated.
- **Review:** the whole-ship cohesion review and owner acceptance, to the Phase 4 completion criteria in the brief.
- **Owns:** export and runtime presentation (integration).
- **Done when:** runtime checks pass, measurements are recorded, and the owner accepts the identity.

### Dependencies and parallelism

**Order:**
- S0 comes first; S1 follows it.
- S2 needs both S1 and P4-ART.
- S3, S4, S5 and S6 need S2.
- S9 needs S2 and P4-MAT.
- S10 needs S3–S6 and S9.
- S11 needs S3–S10.
- S7 needs releases.
- S8a can run in parallel any time after S0.
- S8b needs P4-INT.

**Parallel sessions:** after S2 (one each): WF-FWD (S3), WF-RING-A then WF-RING-B (S4), WF-THERMAL (S5), WF-SPINE (S6), and
WF-RING-B (S8a). The coordinator keeps S2, S9, S10, S11, every `data/modules.toml` change, the shared materials and the plan.

**Single build lock:** sessions queue for builds. Parallel sessions pay off for authoring and review time, not for build throughput.

**Critical technical dependencies:**
1. A Blender-equipped environment.
2. The shared-key rebuild of accepted M7 in S2.
3. The ring rotation and sweep checks in S4.
4. Thermal net area in S5.
5. Runtime draw-range and sharing behaviour in S11.

## 4. Recommended first experiment (Deliverable D)

**Candidates assessed:**

| Candidate | Visual significance | Transfer | Engineering risk | Reuse | Cost | Independence | Comparison value |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Aegis Crown bay and Brow aft sector | the bow is the first read; the Crown rim frames the rings | high: shell, machine and marking all in one 30° sector | low–medium: mechanisms fixed, OD-021 open | ×12 | medium (M8.1 exists) | high | high: M8.1 is a ready baseline |
| Ring exterior segment | highest gain: rings are now smooth tori | medium: shell-dominant | medium: rotation, sweep, OD-016 | ×48 | medium | high | medium: no baseline detail |
| Radiator root / thermal frame | thermal identity | low: thermal-specific | high: physics-locked, emission, net area | ×3 | medium | low: depends on P4-LOCKED | low until P4-LOCKED |

**Recommendation:** the Crown bay and Brow aft sector, with a small transfer probe on one ring A 15° segment. The bay is the only
place where the civic shell (Brow aft cladding), the open machine (carriage, shutter and service hatch) and markings (lane, sector,
hazard) meet inside one accepted envelope with an existing baseline (M8.1) and existing gates. The probe then tests whether the
resulting rules carry to a pressure shell, the largest later repeat. Deciding this is question P4-EXP.

**What it tests:**
1. Which construction language makes the bow read at whole-ship distance and at a 1.78 m human scale.
2. The value ladder for exterior surfaces, which fixes the M8.1 self-review points (lane grey, stencil size, cladding versus truss).
3. How much mechanism is exposed.
4. Marking scale and placement.
5. Whether the rules transfer to a ring shell segment.

**Variants, each on bay 1 with one ring A segment, under the same cameras and lights:**
- **V0:** M8.1 as built (control).
- **VA civic:** continuous cladding and blanket over the bay; carriage and hatch behind flush covers.
- **VB open:** cladding removed to the frames; carriage rails, cable trays, actuators and closeouts exposed.
- **VC hybrid:** the recommendation. Cladding on the Brow aft face and the pressure or equipment volumes; frames and mechanisms
  exposed at the interfaces; doubler and closeout families; corrected values.
- **VC+:** VC with bolder material differentiation, to inform P4-MAT. This includes a GU-blue wayfinding accent and higher value
  contrast between shell and machine.

**References needed:**
- ITER blanket module and handling interface photos;
- ISS truss segment joints and utility trays;
- ORU and grapple fixture marking conventions;
- beta cloth and MLI closeouts;
- Eye 45, S&E 50 (crawler, AG-A02), OD-020/021;
- `m8_forward` manifest.

**Engineering boundaries:**
- **Crown and Brow:** r ≤ 45.0 m; nothing on the sunward skin side; the Crown housing volume, shutters, ports, carriages, emitters,
  launchers and their travel unchanged; the crawler lane kept clear.
- **Ring segment probe:** inside the existing skin envelope with rotation sweep clearance.
- **All variants:** no mass, mechanism, shielding or rating implication; everything stays in `ART_*` or study collections until a
  variant is selected.

**Expected reusable rules:**
- scale tiers (module, panel, fastener) by view distance;
- the exterior value ladder and its relation to M7's ladder;
- an exposure rule: machinery is visible where it moves, mates or is serviced, and the shell covers where it protects;
- doubler and closeout families at every opening;
- a marking type scale with minimum legible size per view distance;
- seed and variation rules per repeated module.

**Deliverable:** a comparison sheet with the six-view set per variant, an owner-facing review packet and a recommended grammar. It
does not roll anything out.

## 5. Risks

**Process risks:**
- **Visual drift across parallel sessions.** Mitigation: S2 codifies the grammar before the fan-out; the coordinator reviews every
  pack against the same review set.
- **Shared-key rebuild touching accepted M7.** Mitigation: S2 runs the full gate and compares the M7 stills.
- **Detail that implies engineering.** Examples: a Crown mechanism (OD-021), ring shielding, radiator coatings. Mitigation: the
  depiction-only rule and labels; P4-LOCKED.
- **Over-detailing.** Mitigation: the scale tiers and negative space; review at whole-ship distance first.

**Delivery and runtime risks:**
- **Runtime cost.** Mitigation: draw ranges and mesh sharing; real-hardware measurement in S11.
- **No Blender in the cloud.** Mitigation: S0 environment.
- **Drive-reader agents cannot reach Drive in this cloud session.** Their allowlists name connector IDs from another environment, so
  Stage A read Drive directly in bounded ranges.

## 6. Owner decision register (Deliverable C)

Posted to the request Doc as the packet `2026-10-24T10:55+02:00 — P4`. Each item carries its decision, context, source, options,
recommendation, trade-offs, affected slices, blocking status and default.

| ID | Decision | Blocking | Default if unanswered |
| --- | --- | --- | --- |
| P4-EXP | First experiment, variants, and authorization of Stage B | **now** (Stage B start) | none: Stage B waits |
| P4-ART | Exterior construction language and its allocation by zone | **now** for S2; not for S1 | S1 runs all variants |
| P4-CAND | Disposition of M8.1, `rad_frame` and `ra2_equip` | **now** for S3/S5 rollout; not for S1 | they stay candidates; M8.1 is V0 in S1 |
| P4-MAT | Material and colour boldness and the exterior hierarchy (S03 unpark) | later (S9) | VC+ is compared in S1 |
| P4-LOCKED | Depiction on physics-locked surfaces: blade COAST finish, Brow ram face, drive | later (S3 ram face, S5, S9) | proxy grey stays |
| P4-SCOPE | Hero, production and simplified tiers; cinematic versus interactive; runtime targets | later (sizing of S3–S11) | the recommended tiers |
| P4-STATE | Ship state (launch versus post-voyage wear) and the GU marking system | later (S9, S10) | launch state, text-only markings |
| P4-INT | Interior zones and cultural character for S8b | later (S8b) | S8b not started |

## Evidence

- Stage A web viewer captures of the 15997fe release (local, not committed): whole ship, side, bow and aft quarters, top, rings, Brow
  aft face, blade root, nozzles, spine and Crown rim.
- Review packets: M7 (`claude.ai/artifact/FHx9ycPyhqQHybbJ2b7W7x`) and M8.1 (`claude.ai/artifact/SBgn9RASfCzWwo1nT97JKt`), cited from
  Model Status rows 29–30.
