# Modular assets: modules, detail packs and contracts

This is how several sessions add production detail to Wayfarer at the same time without touching each other's files, while the ship stays
one assembly. The engineering generators, the Drive authority chain and the build/check loop in AGENTS.md are unchanged. This layer adds:
- a registry of subsystem modules;
- detail packs that one session owns;
- one detail asset per pack assembly, linked into its host at a declared anchor;
- contracts that detect incompatible detail;
- publication records for validated candidates.

## Start a module session

```bash
python3 tools/workflow.py module list                  # modules, their targets, packs, switches, maturity, publication state
python3 tools/workflow.py module show <module|pack>    # the filled handoff: owned files, read-only deps, anchors, envelope, tests
```

`module show` prints the handoff template at the end of this page, filled from the registry and the manifests. Read only what it names
(the pack's manifest and code, the anchor's engineering module, the relevant MODEL.md section). You don't need the whole codebase or the
workbooks.

## Architecture

**Registry: `data/modules.toml`.** This is the one authoritative table. Integration owns it and module sessions only read it. For each module (`WF-CORE`, `WF-FWD`,
`WF-EYE`, `WF-SPINE`, `WF-HABITAT`, `WF-RING-A`, `WF-RING-B`, `WF-DRIVE`, `WF-THERMAL`, `WF-FUEL`, `WF-UTILITY`) it lists:
- the existing build targets it owns (no renames);
- the source files it owns (globs; a file belongs to one module at most);
- its dependencies (acyclic);
- the inspection groups that guard its interfaces.

It also defines the anchor families. These module IDs are new names. They are not the S&E 48 workflow-gate IDs (WF-001…).

**Habitat: one assembly, one asset per ring (phase 3).** Each ring is its own engineering asset and build target: `WF_HABITAT_A`
(`HABITAT_A`, owned by WF-RING-A) and `WF_HABITAT_B` (`HABITAT_B`, WF-RING-B). Each holds its rotor, its mechanism control
`ROTOR_j_MECH_CTRL`, hub, despun drum and `TRANSFER_j_CTRL`, crew tubes, frame, spokes and sectors, and hosts its own anchors and
detail. `WF_HABITAT` (`HABITAT`, owned by WF-HABITAT) is the habitat assembly. It links both rings at the ship origin (`Habitat_Ring_j`) and
holds the whole-habitat rotor actions, whose slots name both controls, because matched spin-down cancels the momenta. The vehicle links it
once as `Assembly_HABITAT`, so runtime groups, node IDs and selectors are unchanged.

WF-HABITAT also owns the sector skin and the interior components. All twelve sectors of both rings instance them, so they belong to
neither ring. The ring geometry comes from one parameterised generator (`revision.ring_asset`) and one spec, so a ring session gets
its own asset, rebuild, anchors and packs, but no second source of engineering values.

Builds:
- `--target HABITAT_A` rewrites ring A and the detail on it, never ring B, the assembly or the vehicle (it sees the ring through the
  assembly's link, as with a detail target).
- `HABITAT` rebuilds both rings and the assembly.
- A sector-skin or interior change rebuilds both rings.

**Detail pack: the unit a session owns.** A pack is discovered by glob, so adding one edits no shared file. It consists of:
- `data/detail/<pack>.toml`: the manifest and its `[params]` (and optional `[materials]`);
- `src/wayfarer/detail/pack_<pack>.py`: the builders and the clearance screen, registered with `production_detail`'s `@builder` and `CHECKS`;
- one generated asset per assembly, `assets/wayfarer/detail/WF_DETAIL_<assembly>.blend` (local, rebuilt from code);
- its publication record, `references/modules/<pack>.json`.

The manifest declares:
- the module;
- `scope`: `M7` or `M8` to take that section's switch and maturity, or `pack` with its own `enabled`, `maturity`, `status` and `evidence_ref`;
- `detail_class`;
- an optional `detail_range_m`: the Godot draw distance of its nodes, for exterior detail; interior detail keeps the 28 m default;
- the inspection groups;
- the preview views;
- per assembly: its anchor, an optional `function` guard, zone and surface classes, and an envelope (`envelope_min`/`envelope_max`, metres, anchor frame).

A pack carrying a mass, density or centre-of-mass key is refused. Production detail never feeds an engineering budget.

**The packs.** Every production assembly is a pack (MOD phase 2, 2026-10-23):

| Pack | Module | Assemblies on anchors | Scope, maturity |
| --- | --- | --- | --- |
| `m7_spine` | WF-SPINE | M7.EXT.PORT, M7.ENT on `WF-SPINE.SERVICE.ORIGIN`; M7.TRK on `WF-SPINE.CREW_TRANSFER.ORIGIN` | M7, `L4_VISUAL_ACCEPTED` |
| `ring_a_transfer` | WF-RING-A | M7.XFR on `WF-RING-A.DRUM.1` (despun drum); M7.SPK on `WF-RING-A.ROTOR.1` | M7, `L4_VISUAL_ACCEPTED` |
| `m7_ra1` | WF-RING-A | M7.RA1 on `WF-RING-A.SECTOR.1.1` | M7, `L4_VISUAL_ACCEPTED` |
| `ra2_equip` | WF-RING-A | RA2.EQP on `WF-RING-A.SECTOR.1.2` | pack, `L4_VISUAL_CANDIDATE` |
| `m8_forward` | WF-FWD | M8.BROW.AFT, M8.CROWN.RIM on `WF-FWD.FORWARD_SHIELD.ORIGIN` | M8, `L4_VISUAL_CANDIDATE` |
| `rad_frame` | WF-THERMAL | RAD.FRAME on `WF-THERMAL.RADIATOR.ORIGIN` (all three blades) | pack, `L4_VISUAL_CANDIDATE` |

**Shared parameters.** A pack owns the parameters only it reads. What several packs read stays in the spec as a read-only dependency,
owned by WF-CORE: `[production]` and `[production.m8]` are the M7 and M8 scopes (switch, maturity, materials; M8 also `crown_sectors` and
the draw ranges, which the runtime manifest reads), and `[production.entry]` is the shared M7 panel grammar. Its consumers (2026-10-23):

| `[production.entry]` key | Read by |
| --- | --- |
| `panel_max_deg`, `panel_min_deg`, `panel_back_gap_m`, `seam_m` | `clad_bay` (M7.XFR, M7.SPK, M7.TRK), M7.ENT, M7.TRK, M7.XFR (merged with its own `[params.drum]` angles), M7.SPK |
| `panel_thickness_m`, `panel_bevel_m`, `fastener_m`, `fastener_inset_m`, `fastener_proud_m` | `clad_bay`, M7.ENT, M7.RA1 |
| `housing_lip_m`, `housing_depth_m` | M7.ENT, M7.TRK, M7.XFR, M7.RA1 |

The one M7.ENT-only key, `bulkhead`, moved to `m7_spine`. Changing a shared key is an integration change: it rebuilds every pack that reads it.

`production_detail.py` stays the shared detail core, owned by WF-CORE. It holds:
- the registration (`@builder`, `CHECKS`) the pack modules use;
- the mesh helpers several packs use (`box`, `bent`, `rod`, `clad_bay`, `windows_free`, `fixture_points`, `windows_of`, `patch_free`, `outward`, …);
- the materials, scopes and switches (`built`, `enabled`, `scope`) and `crown_sectors`;
- the runtime `standard()`.

It builds no assembly itself any more: the legacy `ASSEMBLIES` table and the `[production].assemblies` lists are gone.

**Anchor: a stable attachment frame.** `modules.anchors()` computes each anchor from the pure engineering formulas. No anchor is ever read back from a built file. Each anchor has:
- an ID;
- its host target;
- the host object a detail instance is parented to (or none, meaning the host collection's origin);
- that object's local 4×4 matrix.

| Family | ID | Host object | Frame |
| --- | --- | --- | --- |
| `ring_sector` | `WF-RING-<A\|B>.SECTOR.<ring>.<sector>` | `Sector_<ring>_<sector>` in the ring's asset `WF_HABITAT_<A\|B>`, under `Rotor_<ring>` | the sector frame: origin on the centreline at the deck, +X axial, +Y radially outward (down in spin), +Z tangential; turns with the ring |
| `rotor_frame` | `WF-RING-<A\|B>.ROTOR.<ring>` | `Rotor_<ring>` in `WF_HABITAT_<A\|B>` | the ring centre (`rotor_interface.rotors` x), rest angle the index phase; motion `ROTOR_SPIN_X`: the driver turns it about +X, so detail on it spins, spins down and stops with the ring |
| `drum_frame` | `WF-RING-<A\|B>.DRUM.<ring>` | `Drum_<ring>` in `WF_HABITAT_<A\|B>`, the despun transfer drum (human-entry rotors only) | same centre and rest angle; motion `DRUM_DESPUN_X`: it stays at the index angle while `drum_sync` is 0 and turns with its ring while it is 1 |
| `asset_origin` | `<module>.<TARGET>.ORIGIN` | none (the collection origin) | identity. A component linked several times (the radiator blade) carries its detail on every copy |

Units are metres. The ship axes stay +X bow, +Z dorsal, +Y left.

A moving anchor's matrix is its rest frame at the saved pose. `inspect` and `module validate` check its host object at the anchor's
centre and turning about +X only; the instance inherits the motion, and the runtime export finds the frame by posing the rings and drums.

**Contracts.** Two levels, so that packs never share a generated file:
- **Module contract** (integration-owned): a module's anchors, with one hash per module, in the tracked `simulations/wf_module_contracts.json`
  (contract v2). Every build and `module contracts --write` rewrite it; `tests/test_modules.py` keeps it current. It changes only when an
  anchor frame, the registry or `interface_version` changes, never when a pack is added or edited.
- **Pack contract** (pack-owned): `modules.pack_contract()` hashes `interface_version` plus the pack's own terms: each assembly's anchor with
  its frame, its envelope and its scope (`pack_terms`). Detail assets are stamped with it, and the publication record keeps it and its
  terms. Another pack, in the same module or not, never changes it.
- `module contracts` prints the combined view (module anchors plus every pack's contract), computed in a fixed order, so it does not depend
  on the order in which packs were developed or merged.
- Each anchor also has its own hash (`anchor_hash`), which is what hand-authored detail is pinned to.
- **Compatibility diagnostics** (`modules.check_packs`, `modules.validate`): an unknown module or anchor, an assembly in two packs, two
  packs' envelopes overlapping on the same anchor, a material key defined twice, an authored mesh that is missing, changed or authored
  against another frame. Each message names the remedy.

**Attachment and build order.** `build.py` builds detail assets first, then components, subsystems and the vehicle:
- **Linking.** Before each host is saved, `components/detail.attach()` links every pack assembly anchored on that host. The link is a collection instance, `Detail_<assembly>`, of kind `detail_instance`, parented to the anchor object with an identity local transform and parent inverse.
- **Disabled packs.** A disabled pack is still built (empty) and linked, so switching it never rewrites the host.
- **`DETAIL_<assembly>` targets.** Such a target rewrites only its own file and returns. The host and the vehicle pick the change up through the nested link.
- **Host targets.** A host target also rebuilds the details anchored on it.
- **Joined targets.** Several `DETAIL_*` targets, or several component and subsystem targets, may be joined with `+` (`DETAIL_M7_SPK+DETAIL_M7_XFR`, `CREW_TRANSFER+SERVICE`). `build.py` builds exactly those; `checks` selects that instead of a full build, so an edit to a pack with several assemblies rebuilds only its detail assets.
- **Stamps.** Detail assets carry the spec hash, `anchor_hash`, `inputs_hash` (the pack's manifest, code and committed authored meshes) and `contract_hash` (the pack contract). Pack files are outside the spec hash, so a pack edit stales only its own files.

**Geometry-detail classes.** `representation.DETAIL_CLASSES` defines `BLOCKOUT`, `FUNCTIONAL`, `PRODUCTION` and `HERO`. These classes are separate from the L0–L5 maturity (S&E 48 WF-018…023) and from PROTOTYPE/WORKING/BASELINE/OPEN/HOLD, and replace neither.
- Production detail carries its pack's class.
- Engineering geometry is `FUNCTIONAL` when it is a mechanism, interface, closure, route or access part (`FUNCTIONAL_KINDS`), and `BLOCKOUT` otherwise.
- The runtime manifest gives every node its `detail_class`, plus `pack` for pack detail.

**Hand-authored detail, local.** A mesh modelled by hand goes into the `ART_WF_DETAIL_<assembly>` collection of its detail asset.
- **Adoption.** The next `module build` adopts it: it gets `wf_adopted`, the pack's labels and `wf_authored_against = <anchor hash>`. It never gets `wf_owner`, so regeneration keeps it.
- **Contract change.** If the anchor frame changes, the build stops with `WF_DETAIL_REVIEW` until someone has reviewed the mesh and run `module rebind <pack>`.
- **Where it shows up.** The export carries adopted meshes like generated detail. The fingerprint lists them under `authored`, outside the canonical `objects`, so baselines stay machine-independent.
- **Not in the runtime package.** Authored `.blend` files are not committed (user decision 2026-10-22). The runtime-export fresh build therefore cannot carry local ART detail; `web_export`, which reads the saved assets, does. To make a mesh reproducible, export it to the committed path below.
- **Evidence.** `tests/verify_detail_authoring.py` proves the local path on a disposable copy.

**Hand-authored detail, committed (portable).** An approved authored mesh travels as data: a self-contained glTF binary under the pack's own
folder, `data/detail/<pack>/<id>.glb`, listed in the manifest:

```toml
[[assembly."M7.RA1".authored]]
id = "SHELF_A"                      # A-Z, 0-9, _; the object becomes Auth_<ASSEMBLY>_<id>, component <assembly>.AUTHORED.<id>
file = "shelf_a.glb"                # under data/detail/<pack>/
sha256 = "…"                        # of the file; a changed file stops the build until this is updated after review
authored_against = "…"              # the anchor_hash it was modelled in; a moved anchor stops the build until reviewed
license = "CC0-1.0"
author = "…"
provenance = "…"                    # how and from what it was made; nothing restricted, the repository is public
# optional: detail_class, surface_class, function
```

- **Export.** `module export-authored <assembly> --id <ID> --objects <names>` writes the ART meshes of the local detail asset (anchor
  frame; +Y-up conversion, transforms and modifiers applied; glTF PBR materials; no animation, camera, light or custom property) and
  prints the manifest entry. The editable sources move to `SRC_<asset>`, a collection outside the instanced root collection: they stay in
  the local `.blend`, are never adopted, linked into the ship, exported or fingerprinted, and the build imports the committed file instead.
- **Import.** The detail build checks each entry (`WF_DETAIL_MISSING`, `WF_DETAIL_STALE`, `WF_DETAIL_REVIEW`), imports it with fixed glTF
  options and makes it one generated object in the anchor frame (several meshes are joined in name order on one material list; a single
  mesh keeps its custom normals), tagged like generated detail with the file, checksum, licence, author and provenance. It is therefore in
  the export, the fingerprint and the baseline, and a fresh checkout rebuilds it exactly.
- **Checks.** `module validate` checks the files (present, checksum, frame, 2 MiB cap) and the saved asset (one object per entry, inside
  the envelope). The authored files are in `inputs_hash`, the `checks` selection, the pipeline's input hashes and the runtime package
  inputs, so an edited mesh stales the pack's publication and the package.
- **Why `.glb`.** One self-contained file per mesh: no sidecar `.bin` or texture to lose, one checksum. The costs: Git sees an opaque
  binary (no line diff; every revision is stored whole), and procedural, modifier, driver, constraint and custom-property data does not
  survive (modifiers are applied at export). The `.blend` stays the editable source, locally (storage policy below).
- **Evidence.** `tests/verify_authored_portable.py` proves the path from two disposable clean clones (see Evidence, phase 2).

**Publication.** `module publish` refuses unless `module validate` passes. It then writes `references/modules/<pack>.json` with:
- the pack and module;
- the pack version, `inputs_hash`, spec hash, the pack contract hash and its terms, the anchor hashes (record version 2);
- the git revision;
- the switches and maturity;
- the fingerprint of the pack's detail assets.

`assembly validate` compares every pack's saved assets and current pack contract with its record. An unpublished pack, changed inputs (authored meshes included), a moved anchor, a changed envelope or different geometry all fail; another pack's arrival does not.

A publication makes a pack eligible for integration. It is not an owner acceptance and changes no maturity or canon.

## Commands

```bash
python3 tools/workflow.py module list
python3 tools/workflow.py module show <module|pack|assembly>
python3 tools/workflow.py module contracts [--write]            # module hashes; STALE if the tracked file differs
python3 tools/workflow.py module build <id> [--integrate]       # detail assets only (seconds); --integrate also rebuilds the hosts + vehicle
python3 tools/workflow.py module validate <id> [--no-blender]   # registry, envelope and clearance screens, then the saved-asset readback
python3 tools/workflow.py module preview <id> [--views ...] [--quality draft|material|review|look]   # side view + the pack's views
python3 tools/workflow.py module publish <id>                   # validate, then the publication record
python3 tools/workflow.py module rebind <pack>                  # after reviewing local ART detail against a changed anchor
python3 tools/workflow.py module export-authored <assembly> --id <ID> --objects <names>   # ART meshes -> data/detail/<pack>/<id>.glb
python3 tools/workflow.py assembly validate                     # every pack against its record
/snap/bin/blender -b --python src/wayfarer/build/build.py -- --target DETAIL_<assembly>[+DETAIL_<other>] [--rebind]
python3 tests/verify_detail_authoring.py [--keep]               # local authored-detail check on a disposable copy (~2 min)
python3 tests/verify_authored_portable.py [--skip-runtime]      # committed authored detail from two clean clones (~35 min with runtime-export)
python3 tests/compare_fingerprint.py <before> <after> --relocate <prefix> <old file> <new file> <instance>   # a migration's proof
blender -b --python tests/detail_equivalence.py -- --out <json>; python3 tests/detail_equivalence.py --compare <before> <after>
```

`checks` and `pipeline --quick --target auto` select, for an edited pack (manifest, code or authored mesh), its `DETAIL_*` targets joined
with `+`, `test_production` and `test_modules`, and its declared inspection groups. A new pack, or a pack whose anchor moved, selects its
hosts, which must link it. A change to an engineering module that a pack's code imports also selects that pack.

## Rules for parallel sessions

- **Ownership.**
  - One writable owner per pack and per asset.
  - A session edits only the files `module show` lists as owned.
  - The registry, the detail core, the generators, `data/wayfarer_3d.toml` and the anchors are integration-owned (WF-CORE or the engineering module).
  - Two sessions never edit the same `.blend`; detail assets are generated and local, so they never merge.
- **Branches.** Work on `claude/<task>` (cloud) or `local/<task>` (workstation), one branch per pack. Each branch carries only its pack
  files (manifest, code, authored meshes) and its publication record. The module contract file names anchors only, so a pack branch leaves
  it unchanged; packs merge in any order without conflicts (measured below).

  Integration merges the branches, then runs the full pipeline, `accept` and `runtime-export`. Accepting a new baseline happens only after the merge, because `references/baselines.json` is shared.
- **Gates.**
  - A pack branch passes `module validate`, `pipeline --quick --target auto --inspect <its groups> --expect Prod_ Detail_ WF_DETAIL <host file>` and `module publish`.
  - Passing makes it eligible for integration. It authorizes no canon, engineering or architecture change.
- **New content.** New detail starts as `L4_VISUAL_CANDIDATE` (scope `pack`) until the owner reviews it.
  - Physics-locked parts stay proxy grey: radiator hot faces, drive and nozzles, EYE apertures, closures and seals.
  - Physical radiator area never shrinks: radiator detail stays off the emitting cells (`thermal_geometry.cell_span`), only on non-emitting structure, joints and edges.
- **Worktrees.** Each needs its own full build (assets are not tracked). The build lock is per checkout.
- **Never `git stash` in parallel sessions.** The stash is shared by every worktree of a repository. In the Pilot 2 trial, two sessions stashed their packs at the same time and each popped the other's. Move work aside to a session-private folder, or commit it on the session's branch.

## How to

**Add production detail to an existing anchor.**
1. Copy a pack (`data/detail/m7_ra1.toml`, `src/wayfarer/detail/pack_m7_ra1.py`) to a new name.
2. Give the assembly a new ID and the anchor, and set `scope = "pack"` with `maturity = "L4_VISUAL_CANDIDATE"`.
3. Write the builder in the anchor frame, a screen in `CHECKS`, and an envelope that encloses only the space the detail may use.
4. Run `module validate --no-blender`, then `module build <pack> --integrate`, then `pipeline --quick --target auto --expect Prod_ Detail_ WF_DETAIL WF_<host>`.
5. Review the previews, whole ship first, and run `module publish`.

**Add a subsystem module or an anchor.** This is an integration change to `data/modules.toml` (a module) or to `modules.anchors()` (a new anchor family computed from the engineering pure modules), with `tests/test_modules.py`. Bump `interface_version` only when an existing anchor's meaning changes.

**Update after an engineering-source change.**
1. A spec change rebuilds everything (`all`), including the detail assets.
2. If the change moves an anchor, the pack contract of every pack on it changes and `assembly validate` reports those packs stale.
3. Generated detail recomputes from the same formulas. Rerun `module validate` (the envelope and screens show any incompatibility) and republish.
4. Hand-authored detail stops the build with `WF_DETAIL_REVIEW` until it is reviewed and rebound (local) or its `authored_against` is updated (committed).
5. Never reshape engineering geometry to keep cosmetic detail attached.

**Move detail between files (a migration).** Every legacy assembly is migrated; a later move (another anchor, a split pack, an engineering
asset split) follows the same proof, recorded before the change. An engineering split moves whole objects between files instead (step 3 is
`compare_fingerprint.py --split OLD NEW...`, step 4 `detail_equivalence.py --habitat`; see Evidence, phase 3):
1. Move the builder, its screen and its exclusive parameters, leaving shared parameters as read-only spec dependencies (map the consumers first).
2. Compare a digest of `production_detail.elements()` before and after; it must be identical.
3. Run the full pipeline with the exact prefixes the move touches, then `compare_fingerprint.py --relocate` against the accepted baseline (PASS).
4. `tests/detail_equivalence.py` before and after: the evaluated geometry at the motion and configuration poses, properties and materials.
5. Compare the runtime manifests (nodes, triangles, bounds, frames; node IDs may change with the lineage) and the relevant stills pixel by pixel.
6. `accept` the run.

**Roll back.**
- `git revert` the pack's commit, or set `enabled = false` in its manifest. A disabled pack builds empty, so the geometry diff shows the layer gone.
- Retired generated files are moved to `milestones/` by a full build. Detail assets are backed up there like every asset (newest three).
- A failed integration is undone by resetting the integration branch to the last accepted commit and rebuilding (`all`).

## Session handoff template

```text
MODULE:                  <module ID>: <title> (pack <name>)
TASK:                    <the one visible result this session delivers>
SOURCE CONTRACT:         references/modules/<pack>.json, pack contract <h>; anchors <ID: host object, frame, motion>
OWNED FILES:             data/detail/<pack>.toml, data/detail/<pack>/*.glb, src/wayfarer/detail/pack_<pack>.py,
                         assets/wayfarer/detail/WF_DETAIL_<asm>.blend (local)
READ-ONLY DEPENDENCIES:  data/modules.toml, data/wayfarer_3d.toml, src/wayfarer/production_detail.py, the anchor's engineering modules
PERMITTED CHANGES:       the owned files; PROTOTYPE visual choices inside each envelope; new families and pack materials
FORBIDDEN CHANGES:       engineering geometry, anchors, registry, canon values, other modules' files, budgets, OPEN/HOLD statuses
DELIVERABLE:             <assembly IDs, assets, anchors, envelopes>
LOCAL TESTS:             module validate <pack>; unittest -k production; python3 src/wayfarer/production_detail.py
INTEGRATION TESTS:       module build <pack> --integrate; pipeline --quick --target auto --inspect <groups> --expect ...; module publish <pack>
ACCEPTANCE CRITERIA:     validate PASS; only expected prefixes in the diff; previews reviewed; publication written; maturity stays a
                         candidate until owner review
```

## Audit and decisions (2026-10-22)

**Before the refactoring** (at `b1db258`):
- **Strengths, kept.** Linked components, subsystems and vehicle (`build/build.py`, `common.link_instance`), GEN/ART ownership in `common.begin()`, per-target builds, the fingerprint diff with `--expect`, `accept`, the write lock, `checks.py` selection, the generated M7/M8 layer and export mesh sharing.
- **Problems, by impact on parallel detail work:**
  1. **One shared detail module.** All 8 production assemblies lived in one module (`production_detail.py`, one `ASSEMBLIES`, `BUILDERS` and `CHECKS`) with parameters in `data/wayfarer_3d.toml` `[production.*]`. The host recipes hard-coded each assembly, so two detail sessions edited the same files.
  2. **Detail inside engineering assets.** Production detail was generated into the engineering hosts' GEN (HABITAT, SERVICE, CREW_TRANSFER, FORWARD_SHIELD), and every target rebuilt the vehicle. A cosmetic change rewrote engineering files.
  3. **Over-wide invalidation.** Any spec edit stamped a new hash on all 24 assets, and `checks` forced target `all` for any TOML value change.
  4. **Authored meshes reached nothing downstream.** ART content survived a rebuild but was neither exported (`wf_owner` filter) nor fingerprinted, and nothing pinned it to a frame or contract.
  5. **No declared attachment frames.** Placement was recomputed in the builders. `IF_*` empties carry location only, and no table paired IDs with transforms.
  6. **No ownership map and no record of a validated candidate.**
  7. **Smaller:**
     - Both rings share one HABITAT.
     - No instancing in the production layer.
     - Runtime node IDs hash lineage + matrix; Godot binds through the manifest, so ID changes are safe.
     - Dead code in the RA1 builder.
- **Selected:** a hybrid of the existing generators and linked library files. One small linked detail asset per assembly gives real per-file ownership and edit isolation. Packs carry their own parameters, contracts are computed from the pure formulas, and adoption covers authored meshes.
- **Alternatives considered:**
  - **Asset Browser catalogs.** Rejected: they help manual drag-and-drop, but the build is scripted, and catalogs add no ownership or validation.
  - **Library overrides.** Rejected: they are fragile across rebuilds; the shots already document the nested-override pitfalls.
  - **Geometry Nodes.** Not needed for this layer: the joined, batched families already suit the runtime. They remain an option for artistic scatter where the inspection contract allows.
  - **One project per module.** Rejected: it would break the one-ship assembly and the shared formulas.
  - **Git LFS.** Not adopted (owner decision 2026-10-23) until a concrete production requirement justifies it.
  - **Moving every engineering asset into packs.** Rejected: no demonstrated need. Engineering targets keep their files and get registry ownership instead.

## Evidence (2026-10-22, cloud: 4 vCPU, Blender 5.2.2)

- **Pilot 1, M7.RA1 migrated** (commit `c8df4aa`):
  - All 8 assemblies' `production_detail.elements()` digests are identical before and after.
  - `compare_fingerprint.py --relocate Prod_RA1_ subsystems/WF_HABITAT.blend detail/WF_DETAIL_M7_RA1.blend Detail_M7_RA1` against `baseline_m8_exterior` gives PASS. All 4,770 objects are unchanged; the four RA1 objects moved with their world placement intact.
  - Full pipeline PASS, accepted as `baseline_modules_pilot1`.
  - `tests/verify_detail_authoring.py`: all six steps PASS (adopted, survives regeneration, contract change stops the build, rebind, exported as a production node of the pack).
- **Pilot 2, parallel packs:**
  - `rad_frame` (WF-THERMAL) and `ra2_equip` (WF-RING-A) were built in two worktrees from the same commit, at the same time.
  - Each branch changed only its pack, its publication record and the generated contract file. That file is the only one both touched, and git merged it without conflict.
  - Each branch passed `module validate`, `pipeline --quick --target auto` (selection: its host, `test_modules` and `test_production`, its declared groups) and `module publish`.
  - After the merge: full pipeline PASS, with a diff of 2 instances, 2 files and 2 links and 0 unexpected. Accepted as `baseline_modules_pilot2`.
  - `assembly validate` PASS: the records published in the separate worktrees match the integrated ship exactly, and an unpublished pack edit fails it.
  - One hazard found and fixed in the rules: `git stash` is shared across worktrees.
- **Runtime** (runtime-export, fresh build in a workspace, 31 Godot checks):

  | | Before (`b1db258`) | After (`004d0e2`) |
  | --- | --- | --- |
  | Result | PASS, 31/31 checks | PASS, 31/31 checks |
  | Nodes | 3,936 | 3,947 (+11: RAD.FRAME 3 families × 3 blades, RA2.EQP 2) |
  | Triangles | 718,984 | 741,424 |
  | Bounds | unchanged | unchanged |
  | GLB | 32.50 MB | 33.02 MB |
  | Wall time | 514 s | 485 s |

  - **RA1 in the package.** Same nodes, names, `L4_VISUAL_ACCEPTED` maturity and runtime frame (`WF.ROTOR.1`, so it still turns with ring A). Only its lineage shortened (`Assembly_HABITAT`), so its node IDs changed. Godot binds through the manifest.
  - **Radiator instancing.** Each RAD.FRAME family is 3 nodes sharing 1 GLB mesh.
  - **RA1 stills.** `m7_section.py --views ra1_aisle` before and after are pixel-identical, with the layer shown and hidden.
- **Rebuild regression** (`tests/verify_rebuild.py`, 2,199 s): all 10 steps PASS on a disposable copy of 27 assets. They cover the full rebuild, preserved ART content, the targeted radiator, hull and Garden builds (unrelated assets byte-identical), the detail-only build (every other asset byte-identical), a relocated project loading every nested detail link, and the retirement rules.
- **Timing** (measured on an idle machine unless marked):

  | Operation | Before | After |
  | --- | --- | --- |
  | Change RA1's detail and rebuild | `--target HABITAT`: 29.9 / 31.0 s, rewrites WF_HABITAT (1.54 MB) and the vehicle | `module build m7_ra1`: 4.9–5.0 s, rewrites only `WF_DETAIL_M7_RA1` (0.36 MB); every other asset byte-identical. The host target now takes 29.0–29.8 s and also rebuilds the sector's two detail assets |
  | Add a new pack (`module build <pack> --integrate`, under load) | n/a | 30–32 s (detail + host + vehicle) |
  | `module validate` / `module publish` | n/a | 9 s / 10 s (Blender readback 5.0 s) |
  | Quick loop for a pack change (`--target auto`, scoped inspection, under load) | n/a | 225–232 s (2 test modules, scoped inspection, draft previews) |
  | Full pipeline | 366.5 s (`b1db258`, idle) | 409–433 s (under load) |

  The pack edit selection runs 2 test modules instead of the whole suite. A pack-parameter edit no longer forces target `all`: pack TOMLs are outside the spec hash.
- **Sizes:**
  - Detail assets are 0.35–0.37 MB each; most of that is the per-file spec snapshot texts.
  - WF_HABITAT went from 1.538 to 1.499 MB with RA1 moved out.
  - Each accepted baseline adds a 3.3 MB fingerprint JSON to Git (existing practice).
  - Instancing: one `WF_DETAIL_RAD_FRAME` mesh set is carried by all three blades through the linked component.

## Evidence, phase 2 (2026-10-23, cloud: 4 vCPU, Blender 5.2.2)

Before-state recorded on `main` `80a6cb2`, whose saved assets matched `baseline_modules_pilot2` exactly (fingerprint diff empty).

- **Per-pack contracts.** Merge experiment, two sessions each adding a pack to WF-RING-A from one commit, each regenerating the contract
  file as the build does:
  - old model (`80a6cb2`): `simulations/wf_module_contracts.json` conflicts in both merge orders, and `m7_ra1`'s record hash changes with each
    new pack (`95e5c154…` → `a2cbcc47…` / `f5b072bf…`), so its publication goes stale;
  - new model: clean merges in both orders, identical trees, the contract file current after the merge, `m7_ra1`'s pack contract unchanged.
  - In practice: `ring_a_transfer` joined WF-RING-A next to `m7_ra1` and `ra2_equip`, whose records stayed valid (`assembly validate` PASS).
- **Migrations** (each: `elements()` digests of all ten assemblies identical; full pipeline PASS with only the named prefixes; then):

  | Pack | Relocation proof | Equivalence probe (8 poses) | Runtime manifest | Stills |
  | --- | --- | --- | --- | --- |
  | `ring_a_transfer` (M7.XFR on the drum, M7.SPK on the rotor) | PASS, 8 objects | PASS: SPK turns with ring A, XFR only while the drum is synchronized, as before | 3,947 nodes, 741,424 triangles, bounds and frames identical (`WF.CREW.1.DRUM`, `WF.ROTOR.1`); the 8 node IDs changed with the lineage | xfr_vestibule, spk_tube pixel-identical |
  | `m7_spine` (M7.EXT.PORT, M7.ENT, M7.TRK) | PASS, 20 objects cumulative | PASS (DOCKED with the port leaves, drum doors, tube hatches and gates open) | identical; the spine nodes keep their IDs | all 9 `m7_section` views pixel-identical |
  | `m8_forward` (M8.BROW.AFT, M8.CROWN.RIM) | PASS, 30 objects cumulative | PASS; static with the Crown prepared and engaged at two azimuths | identical | brow_aft and crown_sector off/on and the cutaway pixel-identical |

  `m8_readback` is identical in every field (PASS, 10 objects, 212,256 triangles, r 45.0043 m, 0 clashes against 440 engineering meshes,
  forward-most 0.03 m aft of the skin). Equivalence probe: `tests/detail_equivalence.py` (evaluated world vertices, properties, materials,
  modifiers). Node IDs hash the instance lineage; Godot binds through the manifest's component IDs.
- **Integrated gate:** full pipeline PASS (`runs/20261023T081840Z-pipeline`: 150 unit tests, whole-ship inspection with every group,
  0 unexpected geometry changes), the 7 relocations PASS again on its fingerprint, accepted as `baseline_modules_phase2`; `assembly validate`
  PASS for all six packs; `tests/verify_detail_authoring.py` PASS; `tests/verify_rebuild.py` all 11 steps PASS (2,570 s, partly beside
  the clone test), including the joined `DETAIL_M7_SPK+DETAIL_M7_XFR` rebuild with every other asset byte-identical.
- **Runtime:** `runtime-export` PASS, 31/31 Godot checks (`runs/20261023T083141145535Z-runtime`): 3,947 nodes, 741,424 triangles, bounds,
  GLB 33.02 MB and every node record, frame and the `production` block identical to the before-state export; only the 8 M7.XFR/M7.SPK node
  IDs changed (lineage).
- **Portable authored detail** (`tests/verify_authored_portable.py` at `6e75f73`, 12.8 min, all 11 steps PASS): in clone A a synthetic
  bracket (3 boxes, 24 vertices, one PBR material) was modelled in ART_ and exported by `module export-authored` (3,096 bytes); in clone B,
  cloned from A with no `.blend` anywhere, a full build imported it ("0 generated 1 imported"); `module validate` PASS; in the vehicle its
  instance sits exactly at Rotor_1 (frame and vertex error 0.0 against the `.glb` through the anchor) and follows the ring through a turn;
  runtime-export of B PASS 31/31 with 3,948 nodes and +36 triangles, the node `PROBE.AUTH.AUTHORED.PROBE_BRACKET` on frame `WF.ROTOR.1`; a
  re-exported `.glb` stopped the build (`WF_DETAIL_STALE`) until its checksum was recorded, which then staled only that pack's publication;
  a bumped `interface_version` stopped it (`WF_DETAIL_REVIEW`); ART meshes in `WF_DETAIL_RA2_EQP` and in the probe's own asset survived
  pack and full rebuilds. The character and EVA `.blend` files runtime-export requires were copied into B (generated by other loops).
- **Timing** (idle, one Blender process each, 2026-10-23):

  | Edit | Before (host target, assembly inside the host) | After |
  | --- | --- | --- |
  | M7.XFR / M7.SPK | `--target HABITAT` 32.5 s | `DETAIL_M7_SPK+DETAIL_M7_XFR` 5.1 s |
  | M7.EXT.PORT / M7.ENT / M7.TRK | `SERVICE` 37.1 s, `CREW_TRANSFER` 35.7 s | `DETAIL_M7_ENT+DETAIL_M7_EXT_PORT+DETAIL_M7_TRK` 11.1 s |
  | M8.BROW.AFT / M8.CROWN.RIM | `FORWARD_SHIELD` 30.6 s | `DETAIL_M8_BROW_AFT+DETAIL_M8_CROWN_RIM` 6.8 s, rewriting exactly its two files |
  | M7.RA1 (phase 1) | `HABITAT` | `DETAIL_M7_RA1` 5.5 s |

  The host targets cost what they did (HABITAT 31.2 s, SERVICE 37.1 s, CREW_TRANSFER 36.3 s, FORWARD_SHIELD 32.5 s) because they also
  rebuild their details; a full `build.py` is 61.4 s. A cosmetic edit of any pack now selects only its detail targets (`checks`), where an
  edit of a multi-assembly pack fell back to a full build until the joined targets.
- **Two faults found and fixed on the way:** the forward inspection read only the forward-shield file, so it now reads the detail assets
  linked into it (and skips the link carriers); `m8_exterior.py` restored the production materials by name, which reached only one of
  the per-file copies (the "on" stills differed until it addressed them per datablock).
## Evidence, phase 3: independent ring assets (2026-10-23, cloud: 4 vCPU, Blender 5.2.2)

The split of `WF_HABITAT` into `WF_HABITAT_A`, `WF_HABITAT_B` and the assembly `WF_HABITAT`. Before-evidence is in
`runs/20261023-phase3-before` (the before fingerprint equals the accepted `modules_phase2` baseline) and after-evidence in
`runs/20261023-phase3-after`. All proofs ran on the same machine.

| Proof | Result |
| --- | --- |
| Fingerprint, `compare_fingerprint.py --split subsystems/WF_HABITAT.blend …_A.blend …_B.blend` | PASS: all 507 objects moved verbatim (254 to ring A, 253 to ring B), keeping their records, parents and in-file matrices; the assembly gained exactly the two identity instances; links conserved; every other file and object in the ship unchanged |
| Evaluated geometry, `detail_equivalence.py --habitat` at the 8 poses (saved; COAST with the rings turned; drum sync; HIGH_POWER; DOCKED with every closure open; Crown prepared and engaged at two azimuths) | all 1,443 evaluated instances under `Assembly_HABITAT` (rings, hubs, crew route, sectors, interiors, detail) identical in every pose. The only differences: the two new `Habitat_Ring_j` instance empties, and the `anchor_hash` label of the four ring-A detail instances, whose anchors now name their ring's asset as host |
| Runtime manifest (COAST export against the published package) | 3,947 nodes, 741,424 triangles, bounds, groups, and every node record **including its node ID** identical: the ID hashes the outer `Assembly_HABITAT` group and each object's own parent chain, which the nested link does not change. Only the `host` label of the four ring-A production assemblies changed (`HABITAT` → `HABITAT_A`); no runtime script reads it |
| Sim rig, readback, station map | `wf_sim_rig.json`, `p1_readback` and the station map are byte-identical. The ring files are measured as part of `WF_HABITAT`, so the row IDs are unchanged |
| Stills | all 9 M7 section stills are pixel-identical. The Workbench draft previews are not deterministic: rendering the unchanged after-state twice differs in the same places (a hull-edge band, isolated pixels, up to 13/255). The before/after differences are of that kind and size (≤ 0.1 % of pixels, mostly 1–3/255); geometry is proven by the vertex-level proof above |
| Pack contracts | the anchors of `m7_ra1`, `ra2_equip` and `ring_a_transfer` keep their IDs, objects and frames. Their hash changed with the host, so `assembly validate` reported exactly those three stale; they were republished; 6/6 PASS |
| Inspection | per ring file: its own rotor, control and sectors, and no actions. The assembly: two ring instances at identity, the three actions, and no geometry. The habitat, rotor-interface and crew-transfer checks run unchanged over both linked rings |

Build times (idle, measured), and what each target rewrites:

| Target | Before | After |
| --- | --- | --- |
| `HABITAT` | 34.05 s; one 1.22 MB file + the vehicle | 37.68 s; both rings (0.88 + 0.90 MB), the assembly (0.35 MB) and the vehicle |
| `HABITAT_B` | — | 6.32 s; only `WF_HABITAT_B`; ring A, the assembly and the vehicle byte-identical |
| `HABITAT_A` | — | 8.27 s; `WF_HABITAT_A` and its four detail files |

Gates (all at code commit `cc154ba`, logs in `runs/20261023-phase3-after/gates`):

| Gate | Result |
| --- | --- |
| Full pipeline `--expect WF_HABITAT Habitat_Ring_` (`runs/20261023T110910Z-pipeline`, 482.6 s) | PASS: 150 unit tests OK (1 skipped), whole-ship inspection PASS, fingerprint diff against `modules_phase2`: 0 changed, 2 added (`Habitat_Ring_1/2`), 507 removed from `WF_HABITAT` (moved, proven above), 2 files added, 0 unexpected; Cycles COAST and HIGH_POWER previews. Accepted as baseline `modules_phase3` (`modules_phase2` stays in history) |
| `runtime-export` (`runs/20261023T111712967262Z-runtime`, 9 min 13 s) | PASS: 31/31 Godot checks, 3,947 nodes, 741,424 triangles |
| `tests/verify_detail_authoring.py` | PASS: probe adopted, adopted on build, survives regeneration, a contract change stops the build, rebind after review, exported as production |
| `tests/verify_rebuild.py` (51 min 27 s) | PASS, 15 cases, among them: full rebuild with stable IDs; ART and unowned GEN preserved; radiator, hull, Garden interior, detail-only and moving-anchor detail rebuilds leave every other asset byte-identical; **`HABITAT_B` then `HABITAT_A` each leave the other ring, the habitat assembly, the vehicle and the other ring's detail byte-identical**; relocated nested links; retirement to `milestones/` |

Combined with `main` (MOB-001 touch controls, `b95fb7b`; clean merge `4b6a7eb`, logs in `runs/20261023-phase3-after/combined`): the CI
pipeline (`--quick --previews none --tests none`) gives PASS, with an empty geometry diff against `modules_phase3`; 150 unit tests OK (1 skipped);
`runtime-export` 32/32 PASS (`controls-touch` and `review-ring-b` included; same 3,947 nodes and 741,424 triangles).

Visual maturity is unchanged by the split: `m7_ra1`, `m7_spine` and `ring_a_transfer` stay `L4_VISUAL_ACCEPTED`; `m8_forward`,
`ra2_equip` and `rad_frame` stay `L4_VISUAL_CANDIDATE`. Republishing a record on its new host is not an art review.

## Storage of authored binaries (owner decision 2026-10-23)

**Policy.** Approved authored meshes are committed as `.glb` files in ordinary Git, up to 2 MiB each, with the checksum, anchor hash,
licence, author and provenance the manifest requires. Editable `.blend` sources stay local. No Git LFS and no external asset store until a
concrete production requirement justifies one. Before a real authored asset is committed, its contents and licence must be checked to
permit publication in this public repository; owner material, Drive captures and unlicensed assets never enter the committed path.

The options evaluated, by what they cost this public repository:

| Option | Size and history | Exposure | Reproducibility | Permissions and CI |
| --- | --- | --- | --- | --- |
| `.glb` in Git (current, ≤ 2 MiB each) | every revision stored whole; fine for a few small meshes | public with the repository | full: a clean clone rebuilds it (proven) | none; the web-explorer checkout needs nothing |
| Git LFS for `.glb` (and `.blend`) | history outside the Git objects; GitHub's public-repo LFS storage and bandwidth quotas apply | public (LFS objects of a public repository are downloadable) | full when LFS is fetched; without it the pointer file fails the checksum, visibly | the CI checkout needs `lfs: true`; forks need LFS |
| Private store referenced by checksum | none in Git | private | only with credentials; a public clone cannot rebuild | a secret in CI; a fetch step |
| `.blend` sources in Git | large binaries, no diff, every save whole | public | the editable source travels | none |

Revisit the policy when a real asset exceeds the cap, many assets accumulate, or one may not be public.

## Limitations and next steps

- The two rings share one generator and one spec by design: a ring session owns its asset, anchors and detail packs, and an engineering
  value change still goes through `data/wayfarer_3d.toml` (WF-CORE) and rebuilds both rings when the value is shared.
- Remaining couplings between the rings, all deliberate:
  - **Owned no source file.** The ring modules own targets, anchors and packs; the ring generator (`revision.py`, WF-CORE), the rotor and
    crew-route builders (`rotor.py`, `crew.py`, WF-SPINE) and the sector skin and interiors (WF-HABITAT) are shared code. A change there
    is an integration change, built with target `HABITAT`.
  - **Shared components.** `WF_RING_SECTOR` and `WF_INTERIOR_*` serve all twelve sectors; changing them rebuilds both rings.
  - **One procedure for both rotors.** The stop-lock, touchdown and seal-fault actions live in the assembly, because a matched spin-down
    keeps the counter-rotating momenta cancelled.
  - **One formula couples B to A.** Ring B's vestibule port is sized clear of hub 1's forward cartridge-withdrawal paths
    (`crew_transfer.vestibule`), so a ring-A rotor or cartridge value can move ring B's vestibule. Rebuild both rings (`HABITAT`) after one.
  - **Serial integration.** The build lock, the whole-ship baseline (`accept`) and the published runtime package are single. Two ring
    sessions build in seconds each but serialise on one machine, and their branches integrate one after the other.
  - **Ring B has no detail pack yet.** Its anchors (`WF-RING-B.*`) exist; the first ring-B pack will be the first test of a parallel
    ring-B session.
- The committed authored path keeps PBR base colour, roughness and metallic, UVs and normals; procedural, modifier, driver and constraint
  data does not travel, and joined multi-mesh imports keep face smooth flags but not custom normals. Textures embedded in the `.glb` are
  imported but not checked by any gate yet.
- Each detail asset carries its own copy of a shared production material (same name, another library). The runtime export merges them by
  name; presentation code must address materials by datablock, not by name.
- `assembly validate` is a separate integration command, not part of `inspect`. A pack is expected to be unpublished while it is being edited.
- A new pack anchored on two hosts selects both hosts (`CREW_TRANSFER+SERVICE`); a pack and a host target are never joined, so a change
  touching both selects a full build.
