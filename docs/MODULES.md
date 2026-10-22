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
`WF-EYE`, `WF-SPINE`, `WF-RING-A`, `WF-RING-B`, `WF-DRIVE`, `WF-THERMAL`, `WF-FUEL`, `WF-UTILITY`) it lists:
- the existing build targets it owns (no renames);
- the source files it owns (globs; a file belongs to one module at most);
- its dependencies (acyclic);
- the inspection groups that guard its interfaces.

It also defines the anchor families. These module IDs are new names. They are not the S&E 48 workflow-gate IDs (WF-001…).

HABITAT, the ring-sector skin and the interior components are one engineering asset set shared by both rings. WF-RING-A owns their
engineering until HABITAT is split. Until then WF-RING-B owns detail packs only.

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

`production_detail.py` stays the shared detail core, owned by WF-CORE. It holds:
- the mesh helpers (`box`, `bent`, `rod`, `clad_bay`, `windows_free`, …);
- the materials, scopes and switches (`built`, `enabled`, `scope`);
- the runtime `standard()`;
- the not-yet-migrated assemblies.

**Anchor: a stable attachment frame.** `modules.anchors()` computes each anchor from the pure engineering formulas. No anchor is ever read back from a built file. Each anchor has:
- an ID;
- its host target;
- the host object a detail instance is parented to (or none, meaning the host collection's origin);
- that object's local 4×4 matrix.

| Family | ID | Host object | Frame |
| --- | --- | --- | --- |
| `ring_sector` | `WF-RING-<A\|B>.SECTOR.<ring>.<sector>` | `Sector_<ring>_<sector>` in WF_HABITAT, under `Rotor_<ring>` | the sector frame: origin on the centreline at the deck, +X axial, +Y radially outward (down in spin), +Z tangential; turns with the ring |
| `asset_origin` | `<module>.<TARGET>.ORIGIN` | none (the collection origin) | identity. A component linked several times (the radiator blade) carries its detail on every copy |

Units are metres. The ship axes stay +X bow, +Z dorsal, +Y left.

**Contract.** A module's contract is its anchors plus the envelopes its packs claim. It is written to the tracked
`simulations/wf_module_contracts.json` by every build and by `module contracts --write`; `tests/test_modules.py` keeps it current. Its
hashes change whenever an anchor frame, an envelope or `interface_version` changes. Each anchor also has its own hash (`anchor_hash`),
which is what detail is pinned to.

**Attachment and build order.** `build.py` builds detail assets first, then components, subsystems and the vehicle:
- **Linking.** Before each host is saved, `components/detail.attach()` links every pack assembly anchored on that host. The link is a collection instance, `Detail_<assembly>`, of kind `detail_instance`, parented to the anchor object with an identity local transform and parent inverse.
- **Disabled packs.** A disabled pack is still built (empty) and linked, so switching it never rewrites the host.
- **`DETAIL_<assembly>` targets.** Such a target rewrites only its own file and returns. The host and the vehicle pick the change up through the nested link.
- **Host targets.** A host target also rebuilds the details anchored on it.
- **Stamps.** Detail assets carry the spec hash, `anchor_hash`, `inputs_hash` (the pack's manifest and code) and `contract_hash`. Pack TOMLs are outside the spec hash, so a pack edit stales only its own files.

**Geometry-detail classes.** `representation.DETAIL_CLASSES` defines `BLOCKOUT`, `FUNCTIONAL`, `PRODUCTION` and `HERO`. These classes are separate from the L0–L5 maturity (S&E 48 WF-018…023) and from PROTOTYPE/WORKING/BASELINE/OPEN/HOLD, and replace neither.
- Production detail carries its pack's class.
- Engineering geometry is `FUNCTIONAL` when it is a mechanism, interface, closure, route or access part (`FUNCTIONAL_KINDS`), and `BLOCKOUT` otherwise.
- The runtime manifest gives every node its `detail_class`, plus `pack` for pack detail.

**Hand-authored detail (local for now).** A mesh modelled by hand goes into the `ART_WF_DETAIL_<assembly>` collection of its detail asset.
- **Adoption.** The next `module build` adopts it: it gets `wf_adopted`, the pack's labels and `wf_authored_against = <anchor hash>`. It never gets `wf_owner`, so regeneration keeps it.
- **Contract change.** If the anchor frame changes, the build stops with `WF_DETAIL_REVIEW` until someone has reviewed the mesh and run `module rebind <pack>`.
- **Where it shows up.** The export carries adopted meshes like generated detail. The fingerprint lists them under `authored`, outside the canonical `objects`, so baselines stay machine-independent.
- **Not in the runtime package.** Authored `.blend` files are not committed (user decision 2026-10-22). The runtime-export fresh build therefore cannot carry authored detail; `web_export`, which reads the saved assets, does.
- **Evidence.** `tests/verify_detail_authoring.py` proves the whole path on a disposable copy.

**Publication.** `module publish` refuses unless `module validate` passes. It then writes `references/modules/<pack>.json` with:
- the pack and module;
- the pack version, `inputs_hash`, spec hash, contract and anchor hashes;
- the git revision;
- the switches and maturity;
- the fingerprint of the pack's detail assets.

`assembly validate` compares every pack's saved assets and current contract with its record. An unpublished pack, changed inputs, a moved anchor or different geometry all fail.

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
python3 tools/workflow.py module rebind <pack>                  # after reviewing authored detail against a changed anchor
python3 tools/workflow.py assembly validate                     # every pack against its record
/snap/bin/blender -b --python src/wayfarer/build/build.py -- --target DETAIL_<assembly> [--rebind]
python3 tests/verify_detail_authoring.py [--keep]               # authored-detail end-to-end check on a disposable copy (~2 min)
python3 tests/compare_fingerprint.py <before> <after> --relocate <prefix> <old file> <new file> <instance>   # a migration's proof
```

`checks` and `pipeline --quick --target auto` select, for an edited pack, its `DETAIL_<assembly>` target, `test_production` and
`test_modules`, and its declared inspection groups. A new pack, or a pack whose anchor moved, selects its host, which must link it. A
change to an engineering module that a pack's code imports also selects that pack.

## Rules for parallel sessions

- **Ownership.**
  - One writable owner per pack and per asset.
  - A session edits only the files `module show` lists as owned.
  - The registry, the detail core, the generators, `data/wayfarer_3d.toml` and the anchors are integration-owned (WF-CORE or the engineering module).
  - Two sessions never edit the same `.blend`; detail assets are generated and local, so they never merge.
- **Branches.** Work on `claude/<task>` (cloud) or `local/<task>` (workstation), one branch per pack. Each branch carries:
  - its pack files;
  - its publication record;
  - the contract file a build rewrites. This file names every pack, so two new packs add neighbouring lines to it; regenerate it after merging.

  Integration merges the branches, then runs the full pipeline, `accept` and `runtime-export`. Accepting a new baseline happens only after the merge, because `references/baselines.json` is shared.
- **Gates.**
  - A pack branch passes `module validate`, `pipeline --quick --target auto --inspect <its groups> --expect Prod_ Detail_ WF_DETAIL <host file>` and `module publish`.
  - Passing makes it eligible for integration. It authorizes no canon, engineering or architecture change.
- **New content.** New detail starts as `L4_VISUAL_CANDIDATE` (scope `pack`) until the owner reviews it.
  - Physics-locked parts stay proxy grey: radiator hot faces, drive and nozzles, EYE apertures, closures and seals.
  - Physical radiator area never shrinks: radiator detail stays off the emitting cells (`thermal_geometry.cell_span`), only on non-emitting structure, joints and edges.
- **Worktrees.** Each needs its own full build (assets are not tracked). The build lock is per checkout.

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
2. If the change moves an anchor, the contract hash changes and `assembly validate` reports the pack stale.
3. Generated detail recomputes from the same formulas. Rerun `module validate` (the envelope and screens show any incompatibility) and republish.
4. Hand-authored detail stops the build with `WF_DETAIL_REVIEW` until it is reviewed and rebound.
5. Never reshape engineering geometry to keep cosmetic detail attached.

**Migrate a legacy assembly into a pack.** Follow the M7.RA1 pilot:
1. Move the builder, its screen and its exclusive parameters into a pack, leaving shared parameters as read-only spec dependencies.
2. Remove the assembly from `ASSEMBLIES`, `[production].assemblies` and the host recipe's hard-coded call.
3. Compare a digest of `production_detail.elements()` before and after; it must be identical.
4. Run the full pipeline, then prove the move with `compare_fingerprint.py --relocate` against the accepted baseline, which must give PASS.
5. `accept` the run.

**Roll back.**
- `git revert` the pack's commit, or set `enabled = false` in its manifest. A disabled pack builds empty, so the geometry diff shows the layer gone.
- Retired generated files are moved to `milestones/` by a full build. Detail assets are backed up there like every asset (newest three).
- A failed integration is undone by resetting the integration branch to the last accepted commit and rebuilding (`all`).

## Session handoff template

```text
MODULE:                  <module ID>: <title> (pack <name>)
TASK:                    <the one visible result this session delivers>
SOURCE CONTRACT:         simulations/wf_module_contracts.json, module hash <h>; anchors <ID: host object, frame>
OWNED FILES:             data/detail/<pack>.toml, src/wayfarer/detail/pack_<pack>.py, assets/wayfarer/detail/WF_DETAIL_<asm>.blend (local)
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
  - **Git LFS.** Deferred, since no authored binary is committed yet.
  - **Moving every engineering asset into packs.** Rejected: no demonstrated need. Engineering targets keep their files and get registry ownership instead.

## Limitations and next migrations

- Only M7.RA1 (and the Pilot 2 packs) run as packs. M7.XFR/SPK, M7.ENT/EXT.PORT/TRK and M8 are still built inside their hosts; TODO ranks their migration.
- Drum and rotor anchors (needed for XFR/SPK) are not defined yet.
- HABITAT still serves both rings, so ring-B engineering cannot be owned separately.
- Authored meshes are local. A committed path (glTF as data under `data/detail/<pack>/`, imported by the builder) is backlog.
- `assembly validate` is a separate integration command, not part of `inspect`. A pack is expected to be unpublished while it is being edited.
