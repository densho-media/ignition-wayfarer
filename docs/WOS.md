# Wayfarer Operating System (WOS)

The website is the interface of G.U. WAYFARER 001, not a site about it: one ship, one operating system, multiple devices.
This is the standard for the shell, the modules, the layout profiles, the data classes and the checks. Colour and components are in
`docs/WEB_IDENTITY.md`, rendering budgets in `docs/WEB_GRAPHICS.md`, the site as built in `web/README.md`. TODO section O tracks the
remaining phases.

## 1. Shell

Every page except the Godot launch page (`play/`, its own check contract until Phase 4) sits under one **ship line**, baked into the
HTML at build time by `tools/wos.py` from a single registry, so it works without JavaScript and never shifts the layout.

| Part | What it holds |
| --- | --- |
| Vessel mark | G.U. WAYFARER 001; returns to the Overview |
| Module bar | Overview, Ship, Simulations, Records, Aboard, System (icons and names; the current module is marked) |
| Ship line chips | reference configuration, drive, rings, cabin, advisories count; narrower screens drop chips from the right, the sheet keeps all |
| Ship state sheet | the whole state table and advisories (on pages that already show them, the sheet links there instead) |
| Station label | OPS Console, Engineering Workstation, Simulation Workstation on a workstation layout, Personal Terminal on a phone: labels, PROTOTYPE until canon names them |
| Scenario chip | `SIM · <name>` or `SCENARIO · <name>` while a module runs one; a property of that page only |

Pages mark where the shell goes with `<!--wos:bar-->`, and may show the state table and advisories with `<!--wos:state-->` and
`<!--wos:advisories-->`. `web_export.verify_site` requires exactly one ship line per page and no unreplaced marker.

`web/wos.js` (classic script, deferred, about 4 kB) adds behaviour only: `g` then o/s/m/r/a/y opens a module, `\` toggles focus mode
(the workspace takes the screen), Esc closes the sheet or leaves focus mode; `data-wos-toggle="<id>"` buttons open and close panels and
remember it per page in one `localStorage` key (`wos.v1`, presentation only); `window.wos.scenario({label, class})` sets the scenario
chip. Every page works without it.

## 2. Modules

| Module | Station | Pages | Function |
| --- | --- | --- | --- |
| Overview | OPS Console | `/` | entry to everything, ship state, advisories, release |
| Ship | Engineering Workstation | `viewer/` | the whole vehicle in 3D: presets, assemblies, holograms, drive, engine parts, part status |
| Simulations | Simulation Workstation | `engineering/ignition/`, `dust/`, `build/`, `compare/`, `breakthrough-lab/` | interactive studies; each runs on its own page |
| Records | Engineering Workstation | `engineering/` and its study pages | the engineering record: goal, constraints, lab, open problems |
| Aboard | OPS Console | `interior/`, `exterior/`, `play/` | the walk and the EVA |
| System | OPS Console | `status/` | release, checks, limits, interface profiles, this browser |

A new simulation, visualization, subsystem view or experience joins a module in `tools/wos.py` `MODULES`; it is never an isolated page
with its own navigation. A module needs existing functionality: no empty modules.

## 3. Layout profiles

Width, height, orientation and pointer choose the profile; never the feature set, never the user agent.

| Profile | Screen | Shell |
| --- | --- | --- |
| Workstation | 1100 px wide or more | ship line on top with the module bar, chips and station label |
| Compact | 700 to 1099 px | same line, fewer chips, icon-only names under 900 px |
| Personal terminal | under 700 px wide, or under 500 px high | module bar at the bottom (a left rail on a short landscape screen), vessel, state and advisories on top |

Coarse pointers get 44 px targets in the shell on every profile. `body.wos[data-kind]` names the workspace kind:

- `app` (Ship): the canvas fills the workspace below the ship line; panels overlay it inside the workspace, never `position: fixed`
  to the window. Picking uses the canvas rectangle.
- `overview`: a grid that fits 1366 × 768 without page scroll on a workstation; panels scroll inside; one column on a terminal.
- `sim` (Ignition, Dust): on a workstation the width limit goes, the stage takes the remaining height and the side panel docks right;
  on a terminal the stage is sticky (about 46 % of the height) and every control scrolls beneath it. No control is hidden at any size.
- `record`: long reading pages keep a reading width and scroll.

## 4. Data classes

| Class | Mark | Where it lives |
| --- | --- | --- |
| Specification | `SPEC` | `data/wayfarer_3d.toml` with status and `source_ref` |
| Nominal operating condition | `NOM` | the reference configuration (COAST) of the same data |
| Simulation state | `SIM` | the running module only, never written to the shell or another module |
| Scenario state | `SCENARIO` | the running module only (training, failure scenarios) |
| Illustrative | `EXAMPLE` | labelled where it is shown |

The shell shows only values from `wos.json`, generated by `tools/wos.py` from the parameters through the shared formulas
(`spec.load`, `habitat_ring.floor_gravity_g`) with their canon status and source reference; every `source_ref` must exist in
`data/source_map.toml`. An unknown is shown as OPEN, never as a number. There is no mission clock, bus health or consumables line
until canon gives one (no fabricated telemetry).

## 5. Checks and preview

- `python3 tools/wos.py --out runs/wos-preview`: the site without Blender (web files, the Engineering pages, the bake); about 20 s.
- `python3 tools/workflow.py web`: the full site; `web_export` bakes the shell, writes `wos.json`, fails on registry problems and checks
  the start budget (76 kB raw for `index.html`, `site.css` and `wos.js`, about 19 kB gzipped).
- `tools/web_check.py` (main part): start page loads only `index.html`, `site.css`, `wos.js` and `release.json`; the vessel mark returns
  to the Overview; viewer picks use the canvas rectangle.
- The viewport matrix (ultrawide 2560 × 1080, desktop 1920 × 1080, laptop 1366 × 768, tablet 1180 × 820 and 820 × 1180, phone
  390 × 844 and 844 × 390): no horizontal overflow, the ship line in view, all six modules reachable, the same controls on every
  profile, 44 px shell targets with touch. It and an axe-core WCAG 2.1 A/AA pass ran by hand in Phase 1 (no violations on the
  Overview, System, Records, Dust and Aboard pages at 1366 × 768 and 390 × 844); WOS-2 in TODO O makes both a `web_check` part.

## 6. Principles

- One shell, one registry, one implementation of each simulation and calculation for every profile.
- The viewport is the workstation for `app`, `overview` and `sim` workspaces: no hero, bezel, casing or max-width.
- Function makes the look: colour carries state and hierarchy through the generated tokens; no decorative hardware, glow, scan lines or
  controls without a function.
- Light: vanilla CSS and one script, heavy modules on demand, the budgets of `tools/web_export.py` and `docs/WEB_GRAPHICS.md`.
