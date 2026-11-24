# Wayfarer Operating System (WOS)

The website is the interface of G.U. WAYFARER 001, not a site about it: one ship, one operating system, multiple devices.
This is the standard for the shell, the modules, the layout profiles, the data classes and the checks. Colour and components are in
`docs/WEB_IDENTITY.md`, rendering budgets in `docs/WEB_GRAPHICS.md`, the site as built in `web/README.md`. TODO section O tracks the
remaining phases.

## 1. Shell

Every page except the Godot launch page (`play/`, its own check contract until Phase 4) sits under one **ship line**, baked into the
HTML at build time by `tools/wos.py` from a single registry, so it works without JavaScript and never shifts the layout. Navigation has
four layers, each in one place:

| Layer | Where | What it holds |
| --- | --- | --- |
| Primary | the module bar | Overview, Explore, Simulations, Engineering, Status: one icon and one word each, the current one marked |
| Secondary | the tab row under the ship line (`<nav class="wos-sub">`) | the sections of the current module (Explore: Ship 3D, Interior, Exterior); scrolls sideways on a phone |
| Contextual | inside the workspace | actions on the current object: viewer toolbars, simulation controls, a card's action |
| Utility | the `?` sheet at the end of the ship line | about the project, keyboard keys, "Show the guidance again", the device profile and station label, links |

| Part | What it holds |
| --- | --- |
| Vessel mark | G.U. WAYFARER 001; returns to the Overview |
| Ship line chips | reference configuration, rings, cabin, advisories count; narrower screens drop chips from the right, the sheet keeps all |
| Ship state sheet | the whole state table and advisories (on pages that already show them, the sheet links there instead) |
| Station label | OPS Console, Engineering Workstation, Simulation Workstation, Personal Terminal: PROTOTYPE labels, shown only in the `?` sheet |
| Scenario chip | `SIM · <name>` or `SCENARIO · <name>` while a module runs one; a property of that page only |
| Breadcrumb | record and simulation pages: `Module › page`, under the ship line |

Pages mark where the shell goes with `<!--wos:bar-->`, and may place `<!--wos:state-->`, `<!--wos:advisories-->`, `<!--wos:facts-->`
(the Overview's fact tiles), `<!--wos:sims-->` (the simulation cards) and `<!--wos:thumb <name> [band]-->`. `web_export.verify_site`
requires exactly one ship line per page and no unreplaced marker.

`web/wos.js` (classic script, deferred) adds behaviour only: `g` then o/e/m/n/t opens a module (the old letters s, r, a, y still work),
`\` toggles focus mode, Esc closes any open sheet or leaves focus mode, and only one ship-line sheet is open at a time;
`data-wos-toggle="<id>"` buttons open and close panels; guidance strips are dismissed per strip. Both are remembered in one
`localStorage` key (`wos.v1`, presentation only). `window.wos.scenario({label, class})` sets the scenario chip. Every page works without it.

## 2. Modules

Primary navigation follows what a visitor wants to do, not how the files are organized.

| Module | Intention | Sections (secondary) | Pages |
| --- | --- | --- | --- |
| Overview | discover: what is this, what can I do | — | `/` |
| Explore | explore the spacecraft | Ship 3D, Interior, Exterior | `viewer/`, `interior/`, `exterior/`, `play/` |
| Simulations | run something and see what breaks | All, Fusion Ignition, Fusion engine, Ignition, Dust, Build sequence, Compare, Breakthrough Lab | `simulations/`, `engineering/fusion-ignition/`, `fusion/`, `ignition/`, `dust/`, `build/`, `compare/`, `breakthrough-lab/` |
| Engineering | understand the design and its sources | Summary, Baseline, Weakest links, Ship evolution, Vertex drive, Open problems, Lab records | `engineering/` and its study pages, `studies/`, `variants/` |
| Status | check the ship state, advisories and this release | Ship state, Advisories, System | `status/` |

Every route of the earlier six-module shell (Ship, Records, Aboard, System) is kept. A new simulation, visualization, subsystem view or
experience joins a module in `tools/wos.py` `MODULES` (and a simulation also `SIMS`); it is never an isolated page with its own
navigation. A module needs existing functionality: no empty modules.

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
- `overview` (Overview, Simulations, Status): an identity band and card grids that use the width; the page scrolls; one column of
  horizontal cards on a terminal.
- `launch` (Interior, Exterior): the picture, one line, a "Try this" strip, the start panel; Controls and About behind disclosures.
- `sim` (Fusion Ignition, Ignition, Dust): on a workstation the width limit goes, the stage takes the remaining height and the side panel docks right;
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
  the start budget (96 kB raw for `index.html`, `site.css` and `wos.js`, accepted by the owner on 2026-11-21; 93.1 kB at the squash).
- `web_export` also counts the Overview's pictures apart from its code (`START_IMAGE_BUDGET`, 160 kB at the widest size each srcset
  can pick) and checks that every `thumbs/*.webp` a page names exists.
- `tools/web_check.py` (main part): start page loads only `index.html`, `site.css`, `wos.js`, `release.json` and `thumbs/*.webp`; the
  vessel mark returns to the Overview; viewer picks use the canvas rectangle.
- The viewport matrix (ultrawide 2560 × 1080, desktop 1920 × 1080, laptop 1366 × 768, tablet 1180 × 820 and 820 × 1180, phone
  390 × 844 and 844 × 390): no horizontal overflow, the ship line in view, all five modules reachable, the same controls on every
  profile, 44 px shell targets with touch. It and an axe-core WCAG 2.1 A/AA pass ran by hand in Phase 1 (no violations on the
  Overview, System, Records, Dust and Aboard pages at 1366 × 768 and 390 × 844); WOS-2 in TODO O makes both a `web_check` part.

## 6. First visit and visual hierarchy

The guiding principle is **show first, explain progressively, let people explore**. One interface serves a first-time visitor and a
technical user; nothing is gated by experience level.

- **The Overview** is the entry: (A) the ship's name, one line and a real picture of the ship, with "Explore the ship" as the one
  primary action (no full-screen hero); (B) four experience cards with a picture, a title, one sentence, an action and an availability
  line that says what the card is: interactive (filled dot, with its download), reading (open dot) or not in this release (amber ring,
  greyed picture, the action reads "What it is"). A card never promises an action that only opens a note; the launch page of a missing
  experience says "Not available in this release" and its Start stays off. The Overview reads availability from `release.json` and
  creates no graphics context; (C) five fact tiles from `wos.json` plus open problems, with the status and source table behind "Status and sources"; (D) what
  the project is: a fictional, evolving design worked out with real physics, not a real or operating ship.
- **Hierarchy** on every page, in this order: where am I (module tab, h1), the main action (one `.button`), supporting actions (links,
  secondary buttons), context (one lead line), detail (tables, panels, disclosures), metadata (status chips, release line). Hierarchy
  comes from size, weight, spacing, grouping and pictures, not from smaller text. A card's text is one sentence.
- **Progressive disclosure** has three conceptual levels: discovery (a picture and one sentence), exploration (the model, the
  simulation, the diagram) and engineering (parameters, constraints, open problems, sources). Level 3 is always one click away: the
  Engineering module, "Status and sources", a record link from a result.
- **Guidance** is contextual and optional: one-line `.wos-guide` strips ("New here?", "Try this", what a simulation shows) that close
  with "Got it" and come back from the `?` sheet; the 3D viewer shows its controls ("Drag to orbit · scroll to zoom · click a part", or
  the touch form) until the first touch. No wizard, modal tour or mandatory tutorial. An experience missing from a build says so on its
  card and its launch page.
- **Section row**: when tabs do not fit, the hidden side fades out and an arrow button scrolls the row (mouse users have no sideways
  wheel); the current tab is centred. Anchor jumps land below the sticky ship line and row (`scroll-padding`), and nothing in the
  workspace sits under the bottom bar or side rail on a terminal.
- **Wayfinding**: the marked module, the tab row, the page title and a breadcrumb on record and simulation pages say where you are;
  every launch page offers the other experiences; the vessel mark returns to the Overview.

## 7. Pictures and icons

- **Thumbnails** are the project's own imagery only: viewer frames, Blender renders from the saved assets, simulation frames and
  existing study figures (`tools/thumbs.py render | capture | pack`). They are committed WebP files in `web/thumbs/` with
  `thumbs.json` recording source, crop and bytes, so the site build needs neither Blender nor a browser. Cards are 16:9 at 480 and
  960 px, the Overview band 3:1 at 960 and 1920 px; every `<img>` has `width`, `height`, `srcset`, alt text and `loading="lazy"`
  except the band, which is preloaded. A thumbnail is a picture, never a running simulation.
- Each thumbnail carries a **class chip**: `MODEL` (a frame of the REP_PROXY ship), `SIM` (a simulation frame), `SCHEMATIC` (a diagram)
  or `ILLUSTRATIVE` (anything not a representation of the model). Update the pictures when the ship or a simulation changes visibly.
- **Icons** are one family in `tools/wos.py` `ICONS`: a 24 px grid, 1.75 px stroke, round caps, `currentColor`, no fill. One meaning
  per icon across the site (overview, ship, interior, eva, sim, engineering, status, help, records, propulsion, power, thermal,
  habitat, navigation, alert, settings, info, lock, arrow, close). An icon always sits next to its word, or carries an accessible
  name where space removes the word (the phone bar keeps both).

## 8. Principles

Owner-approved baseline (2026-11-21): the navigation, visual hierarchy, first visit, mobile presentation and identity described here.
Future work extends it and keeps: complete functional parity across desktop, tablet and phone; visual-first discovery with concise
explanations and meaningful pictures; the most useful workspace for simulations, engineering and exploration; specification, nominal
condition and simulated state kept apart; large assets loaded only when asked for, with loading monitored; consistent navigation,
contextual guidance and progressive disclosure. A budget increase needs a measured investigation and a justification.

- One shell, one registry, one implementation of each simulation and calculation for every profile.
- The viewport is the workstation for `app` and `sim` workspaces: no hero, bezel, casing or max-width; overview pages use the width.
- Function makes the look: colour carries state and hierarchy through the generated tokens; no decorative hardware, glow, scan lines or
  controls without a function.
- Light: vanilla CSS and one script, heavy modules on demand, the budgets of `tools/web_export.py` and `docs/WEB_GRAPHICS.md`.
