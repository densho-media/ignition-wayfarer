# Wayfarer Operating System (WOS): Phase 0 architecture

Kind: architecture record for the task `project-thread-2uwmwa`. Authority for the requirements: `BRIEF_WOS.md` (owner brief
2026-11-21). Nothing here is implemented. File and line facts were read from the branch at `a6f6669`; sizes are measured raw bytes.

**One ship. One operating system. Multiple devices.** The short version of this document:

- WOS is a **shell and a set of rules over the existing multi-page static site**, not a new application. One baked status bar, one
  module registry, one generated ship-state record, two workspace kinds (viewport-locked `app`, scrolling `record`).
- **Vanilla CSS + one small classic script (`web/wos.js`) + one Python module (`tools/wos.py`).** No framework, no router, no bundler.
- **Screen size picks a layout profile, never a fictional device and never a feature set.** Fictional devices are labels on profiles
  now and real HUD configurations in Godot later.
- **Every number in the shell comes from `data/wayfarer_3d.toml` through the Python export**, with its status and source ref. The shell
  shows no clock, no bus health and no consumable until canon or a model provides one.

---

## 1. Architectural assessment of the current site

### 1.1 Surfaces

| Path | What it is | Built by | Styles / scripts | Heavy load |
| --- | --- | --- | --- | --- |
| `/` | start page: hero, 2 primary + 3 secondary cards, note, footer | static `web/index.html` | `site.css`, one inline script reading `release.json` | none (checked) |
| `/viewer/` | Explore Ship, three.js 0.170.0 | static `web/viewer/index.html` | **own** `viewer.css`; ES modules `viewer.js` (55 kB), `appearance.js`, `shield.js`; lazy `inspect.js`, `fuel.js` | GLB 5.9 MB on open; engine parts, field, fuel, holo JSON on demand |
| `/interior/`, `/exterior/` | launchers for the Godot walk and EVA Operations | static | `site.css`, `play/launch.js` | none before Start |
| `/play/` | hub for old links; Godot export; `shell.html` is an export input, not a site file | static + `tools/web_play.py` | own look (shell) | engine 39.5 MB + pack 23.1 MB on Start |
| `/status/` | release, checks, limitations, browser probe | static + `status.js` | `site.css` | `release.json` |
| `/engineering/` + 24 pages | story, 4 Engineering 2.0 pages, vertex, 14 lab entries, compare, build, ignition, dust | `tools/story.py` (`page()` at line 328 is the single template) and `tools/story_lab.py` | `site.css` + `story.css` + per-page css/js | see 1.2 |

Assembly: `tools/web_export.py run()` copies `web/` (minus `README.md`, `play/shell.html`), calls `story.build()`, vendors three.js,
exports the GLB and the per-feature JSON (`nodes`, `holo`, `shield`, `drive`, `engine`, `field`, `fuel`), builds the Godot package,
writes `viewer/build.json`, `play/play.json`, `release.json`, then `verify_site()`. `python3 tools/story.py --out DIR` builds the
Engineering pages alone in about 22 s without Blender (measured here: 25 pages, 68 files, 7.8 MB).

### 1.2 Simulations and interactive visualizations

| Surface | Script | Data (generated) | Model download | State lives in |
| --- | --- | --- | --- | --- |
| Explore Ship: styles, states, focus | `viewer.js`, `appearance.js` | `nodes-*.json`, `holo-*.json` | GLB | URL hash (`#view`, `#cam`, `style=`, `focus=`, `ov=`) |
| Explore Ship: Drive drawer | `viewer.js` | `drive-*.json` (`vertex_cluster.effect_states`) | - | memory, `#drive=` |
| Explore Ship: Engine parts | `inspect.js` | `engine-*.json`, `engine-parts-*.bin`, `field-*.json` | 0.4 MB on open | memory |
| Explore Ship: Fuel drawer | `fuel.js` | `fuel-*.json` (`fuel_system.web`) | - | memory |
| Compare (have / need) | `compare.js` | `compare.json` (problem map `site.py --compare`) | GLB on click | hash |
| Build sequence | `build.js` | `sequence.json` | GLB on click | hash (step id) |
| Ignition: what breaks | `ignition.js` (46 kB) | `ignition.json` | engine parts + three.js on click | hash (`mode=`, `lv=`) |
| Dust: what hits at speed | `dust.js` (50 kB) | `dust.json` (0.14 MB) | three.js only, procedural | hash |
| Breakthrough Lab | `lab.js` | inline `#bt-data` (page is 313 kB) | none | hash |
| Deadship DS-1..3, navigator, EVA Ops | Godot scenes over `ship_ops.py`, `ring_services.py` models | `data/deadship/*.toml`, `data/simulations/*.json` | Godot package | in-engine only |

### 1.3 What is good and must survive

- **Click-to-load isolation and page-per-experience.** Navigation unloads engines; `web_check` measures that renderer memory returns
  to the start-page level. An SPA shell would throw this away. WOS stays a multi-page site.
- **No hand-typed ship numbers on generated pages.** `story.py` takes every figure from the spec and pure modules.
- **One token source** (`tools/web_identity.py`, `--check`, stale block fails the build) and four colour layers with a status layer
  that already carries the canon statuses (`.st-LOCKED` ... `.st-OPEN`, glyphs so state never depends on colour).
- **State in the URL hash, nothing in web storage.** No page uses `localStorage` or `sessionStorage` today. Simulations are already
  isolated from each other and from "the ship"; WOS only has to not break that.
- **Budgets enforced in code** (`START_BUDGET` 60 kB, `VIEWER_BUDGET` 12 MB, `PLAY_BUDGET` 90 MB, `INSPECT_BUDGET` 600 kB).

### 1.4 Duplication and inconsistency (the work WOS actually has to do)

| Finding | Evidence |
| --- | --- |
| Navigation is copied by hand into every page and differs per page | `.sitebar` in `index.html`, `status/`, `interior/`, `exterior/`, `story.py:346`; the viewer has none, only `a.back`; no page links to the simulations or to Interior/Exterior from the bar |
| The viewer is a separate design island | `viewer.css` has its own token subset (`VIEWER_KEYS`), its own `button`, `.panel`, fonts; does not load `site.css` |
| Three breakpoints, all viewport based | 640 px (`site.css`, `viewer.css`, `lab.css`), 760 px (`build`, `ignition`, `dust`, `story`), 560 px (`story`) |
| Desktop wastes the viewport | `.wrap { max-width: 1000px }`, `.story { max-width: 1080px }`, sim stages capped at `min(68vh, 640px)`; hero `clamp(30px, 6.4vw, 56px)` title with up to 72 px top padding |
| Viewer overlays are `position: fixed` with magic offsets | `top: 140px`, `top: 96px`, `bottom: 216px`, sibling selectors to hide the pick box when a panel is open on a phone |
| Controls restyled per page | `.itools button`, `.ign .cases button`, `.btools`, `.ctools`, `.chips button`, each with its own min-height (22 to 40 px) |
| No shared ship state | ring g appears in `story.ship_numbers`, in launcher prose ("about 0.49 g"), nowhere on the start page; nothing says which configuration a surface shows (viewer COAST, walk DOCKED) |
| Touch targets under 44 px | viewer legend buttons 22 to 26 px, chips 30 px, sim buttons 32 to 34 px |
| **Functional parity gap that exists today** | Explore Exterior is keyboard-and-mouse only (`LIMITATIONS`, `launch.js` "no touch controls yet", start page "desktop browser") |
| **axe-core is not automated** | `docs/WEB_IDENTITY.md:154` reports a manual axe 4.10 run; no file under `tools/`, `tests/` or `.github/` references axe. The brief's "existing axe-core checks" are a past manual result |

### 1.5 Hard dependencies of CI on today's markup (verified in `tools/web_check.py` and `web_export.verify_site`)

| Dependency | Where | Consequence for WOS |
| --- | --- | --- |
| Start page requests equal exactly `index.html`, `release.json`, `site.css` | `web_check.py:927` | adding `wos.js` needs this list changed deliberately |
| Start page contains none of `.glb`, `.wasm`, `.pck`, `vendor/`, `engine-`, `<script src`, `type="module"` | `web_export.py verify_site` | `<script src` must be relaxed to "only `wos.js`"; keep `wos.js` a classic script |
| `#release` text starts with `Release 2`; `#go-viewer`, `#go-interior`, `#go-exterior` are clickable | `web_check.py:921, 941, 1160+` | keep these ids on the new Overview |
| `.sitebar .mark` returns to the start page from a launcher; `a.back` in the viewer | `web_check.py:1196`, `centre_of('a.back')` | keep both hook classes on the WOS bar mark, or change the selectors in the same commit |
| Viewer: fixed click and drag coordinates around (640, 400) in a 1280 x 800 window; `[data-view=*]`, `[data-style=*]`, `#pick`, `#status`, `#panel-toggle`, `#appearance-toggle`, `#engine-toggle`, `#show-all`, `#reset-appearance`, `#assemblies li select`, `.part-list button`, `.part-details`, `window.wayfarer.*` | `web_check.py:941-1060` | keep every id and data attribute; the canvas centre must stay near the window centre |
| Viewer sizes by `window.innerWidth/innerHeight` | `viewer.js:540, 562` | moving the canvas into a grid cell needs these two places changed to the canvas rect |
| Phone 390 x 844: start page has no overflow; viewer orbits and pinches; status page renders; `engineering/ignition/#autostart` and `engineering/dust/#autostart` expose `window.__dust` / ignition mirrors with "no horizontal overflow" | `web_check.py:1364-1447` | the sim page keeps `#autostart`, `window.__dust`, its ids |
| Every local `href`, `src`, `from '...'`, `fetch('...')`, `url()` resolves inside the site | `verify_site` REFERENCE regex | baked links must be relative and real |
| Live verify fetches `/`, `site.css`, `viewer/`, `play/`, `interior/`, `exterior/`, `play/launch.js` | `web-explorer.yml verify` | no existing URL may move |

---

## 2. Critical review of the v1 Crew Interfaces concept

| v1 proposal | Verdict | Reason |
| --- | --- | --- |
| Device families with repository-cited placements (cuff, slate, suit display, OPS, engineering workstation, burn-go console) | **Keep** as the taxonomy seed | cites `docs/CHARACTERS.md`, `docs/EVA.md`, `docs/MODEL.md`; all PROTOTYPE |
| "The activity picks the frame in the experiences" | **Keep** (owner approved in principle, brief §10) | applies inside Godot (Phase 4), independent of the visitor's screen |
| A ship status strip that never leaves | **Keep, re-source** | must be generated from the spec, not typed |
| Tokens only from the generator; no glow, glass, scan lines; 7:1; pure CSS first | **Keep** | matches `docs/WEB_IDENTITY.md` |
| Casing, nameplate, bezel, "one new token pair: casing and nameplate" | **Drop** | brief §5 and §9: no hardware casings on the web; they spend the viewport on decoration |
| Phone = Crew Cuff, "one task per screen", glove-sized rows, three hard keys BACK / HOME / ALERT | **Drop** | brief §4: mobile is the unrestricted Personal Terminal; the cuff is an in-world device. Hard keys duplicate the browser's Back |
| Explore Ship on a phone = "Service slate view"; tablet = slate | **Drop** | couples a fictional device to a screen width. A slate is an activity (maintenance), not a size |
| F1 to F8 soft-key row "that are the real keyboard shortcuts" | **Drop** | F1, F3, F5, F6, F11 are browser keys; a permanent key row is the wasted space the brief names |
| "EVA · best on a desktop" accepted as a property of the cuff | **Change** | it is a parity gap to close (touch EVA), not a feature of a device |
| Strip values `MET 0001:142:07:31`, `BUS A OK`, `AIR NOMINAL`, suit `O2 PRI 87 %` with a footnote "values are examples" | **Drop** | brief §8: fabricated telemetry must be identifiable where it is shown. A footnote is not a label, and a persistent strip reads as authoritative |
| Start-page figures typed into the mock: "Crew 12", "Drive PROTOTYPE", "Rings SPINNING" | **Drop** | the figures are right (the ship is designed for 12, `crew.rated_occupancy`; 6 is the story manifest) but typed by hand, with no status or source. The shell shows them from the generated record |
| Three panes (index, document, context) as the workstation layout | **Change** | brief §5: the module decides the composition; a canvas module and a record do not share a layout |
| Deliverable = a detached `concept.html` mockup | **Change** | brief Phase 1: prove it on the real pages, not on a mockup |
| Phases 0 to 4 | **Change** | renumbered to the brief's 0 to 5; Phase 1 now includes a real simulation and Explore Ship, not only launchers |
| Mirror-reversed chest labels | **Keep for Godot only** | a hardware property (brief §9: hardware characteristics inside Godot experiences) |

What v1 got right in spirit and under-delivered: the site should feel like the ship's own interface. The correction is that the feeling
comes from **operational grammar** (state, units, statuses, source, density, keyboard), not from drawn hardware.

---

## 3. Revised WOS concept

### 3.1 Identity

WOS is how Wayfarer shows itself to whoever holds a display. The visitor is not reading about the ship; they are signed in to it with a
guest session. What makes it read as an operating interface, each item costing no screen area:

1. **A persistent ship line.** Vessel, active module, the reference configuration and its sourced state, advisories, release. Always
   in the same place, on every surface, at every size.
2. **Every value is a typed quantity**: number, unit, status mark, source. The existing canon statuses are the visual language
   (`.st-*`), extended by the data-class marks of section 7. A reader can always tell a locked specification from a simulation output.
3. **Modules, not pages.** The bar names the module and the station (`ENGINEERING WORKSTATION · SHIP`), links are module switches,
   and the URL stays a plain shareable address.
4. **Advisories are real.** The open-problem register, OPEN spec items and HOLD rules are the ship's standing advisories. No invented alarms.
5. **Operator ergonomics**: keyboard paths for everything, tabular numerals, stable positions, no hero, no marketing copy, no motion
   that is not a state change.
6. **One vocabulary with the in-world devices**: the same module names, status words and tokens appear on the Godot HUDs (Phase 4).

Not part of the identity: boot sequences, typewriter text, fake logins, scan lines, glow, sound.

### 3.2 The shell

```
+--------------------------------------------------------------------------------------------------------------+
| (o) G.U. WAYFARER 001 | OVERVIEW SHIP SIMULATIONS RECORDS ABOARD SYSTEM | COAST  RINGS 4.0 rpm 0.50 g | ADV 11 | REL |   <- bar, 36 px
+--------------------------------------------------------------------------------------------------------------+
|                                                                                              |               |
|   primary workspace (canvas, simulation stage, record sheet, overview grid)                  |  context      |
|                                                                                              |  panel(s)     |
|   module toolbar docks to an edge of the workspace                                           |  collapsible  |
+--------------------------------------------------------------------------------------------------------------+
```

| Part | Content | Behaviour |
| --- | --- | --- |
| **Ship line** (`.wos-bar`) | mark + vessel (link to Overview); module switcher; state chips; advisories chip; release chip; station label | baked into the HTML at build time, so it works without JavaScript and causes no layout shift. One row. Chips drop from the right as width shrinks and stay reachable in the status sheet |
| **Module switcher** | Overview, Ship, Simulations, Records, Aboard, System | plain links (`aria-current="page"`). Workstation: in the bar. Terminal: bottom module bar (portrait) or left rail (short landscape) |
| **Status sheet** | the full ship-state list with statuses and sources, the data-class legend, SIMULATION_ONLY note | a `<details>` on the state chips; the phone path to everything the wide bar shows |
| **Workspace** (`.wos-work`) | the module's own content | `app` kind: fills the viewport under the bar, no page scroll. `record` kind: scrolls, reading width, sticky bar |
| **Panels** (`.wos-panel`) | module context: assemblies, levers, readouts, part record, section index | docked beside the workspace when it is wide, a drawer or sheet when narrow, always toggleable; state persisted |
| **Advisories** | count by level, link to the register (`engineering/#problems`), HOLD items | generated; a module may add its own *scenario* advisory, visibly marked, for the life of the page |
| **Scenario chip** | "SCENARIO · Dust · 1 mg at cruise" | appears only while a module runs a simulation or scenario; never changes the nominal chips |

The lunar scene stays as the background of Overview, records and launchers (it is already in `site.css`); `app` workspaces draw no scene.

---

## 4. Device and workspace taxonomy

### 4.1 Three independent axes (v1 merged them)

| Axis | Chosen by | Changes | Never changes |
| --- | --- | --- | --- |
| **Layout profile** | available width and height, pointer type, orientation, user override | density, panel arrangement, navigation placement, target sizes | which functions exist |
| **Workspace kind** | the module | `app` or `record`, the panel set, the toolbar | the shell |
| **Fictional device** (station label) | the module on the web; the activity inside Godot | a label in the bar now; HUD composition in Godot later | data or logic |

### 4.2 Layout profiles (the only thing screen size decides)

| Profile | Condition | Navigation | Panels | Targets |
| --- | --- | --- | --- | --- |
| `workstation` | width ≥ 1100 px and height ≥ 500 px | in the bar | docked, several at once | 32 px min; 44 px when the primary pointer is coarse |
| `compact` | 700 px ≤ width < 1100 px and height ≥ 500 px | in the bar, labels may shorten | one docked panel or a drawer over the workspace edge | as above |
| `terminal` | width < 700 px, or height < 500 px | bottom module bar; left rail when height < 500 px | bottom sheet or stacked under a sticky stage; one open at a time | 44 px |

Selected by CSS media queries on the shell (it is the viewport) and by **container queries inside a workspace** (a docked panel
narrows the workspace; the module reacts to its own width). `@media (pointer: coarse)` raises targets on any profile; `(hover: none)`
removes hover-only affordances. No user-agent test anywhere. A 1180 x 820 tablet is a workstation with large targets; a 600 px wide
desktop window is a terminal. A later preference (`auto | workstation | terminal`, Phase 3) sets `data-profile` on `<html>`.

### 4.3 Fictional devices

| Device (brief §4) | Web status | Justification from what exists |
| --- | --- | --- |
| **Personal Terminal** | **Now**: the station label of the `terminal` profile, every module | brief default for mobile; full function |
| **OPS Console** | **Now, label only**: Overview and System on `workstation`/`compact` | ship state and release monitoring exist |
| **Engineering Workstation** | **Now, label only**: Ship and Records | Explore Ship and the Engineering records exist |
| **Simulation Workstation** | **Now, label only**: Simulations | ignition, dust, build, compare, Breakthrough Lab exist |
| **Navigation Console** | Later (Phase 2+ if a web navigation module is built) | data exists (`wf_route_v1.json`, `space_navigator.toml`) but only Godot shows it |
| **Burn Console** | Later, Godot (Phase 4) | the First Ignition timeline exists as data; no interactive burn surface yet |
| **Crew Cuff** | Godot interior HUD (Phase 4) | in-world, the instructor already wears one |
| **Service Slate** | Godot, when a maintenance activity ships (Deadship bay work is the candidate) | none on the web |
| **EVA Display** | Godot exterior HUD (Phase 4) | `eva_hud.gd` exists with hard-coded colours |

Station labels are one string per module in the registry, not a layout fork. All device names and hardware traits are **PROTOTYPE**
until the Technology workbook carries them (Phase 5); the System module says so next to the label.

---

## 5. Functional module inventory

Derived from what exists. Six modules; no empty ones.

| Module | Station label | Existing functionality | URLs (all unchanged) | Kind |
| --- | --- | --- | --- | --- |
| **Overview** | OPS Console | start page: entry to everything, release line; gains ship state, advisories | `/` | `app` on workstation (fits 1366 x 768), flows on terminal |
| **Ship** | Engineering Workstation | Explore Ship: camera, styles, states, focus, assemblies, subsystem legend, Drive, Engine parts, Fuel, pick record | `/viewer/` (+ hash bookmarks) | `app` |
| **Simulations** | Simulation Workstation | Ignition, Dust, Build sequence, Compare, Breakthrough Lab | `/engineering/ignition/`, `/dust/`, `/build/`, `/compare/`, `/breakthrough-lab/` | `app` with a record tail (assumptions, tables) |
| **Records** | Engineering Workstation | Engineering story, Baseline, Weakest Links, Ship Evolution, Vertex lineage, 14 lab entries, problem register | `/engineering/`, `/engineering/baseline/`, `/weakest-links/`, `/evolution/`, `/vertex/`, `/engineering/<kind>/<name>/` | `record` |
| **Aboard** | OPS Console | Explore Interior, Explore Exterior launchers; the Godot page | `/interior/`, `/exterior/`, `/play/` (hub and old links), `play/walk-<hash>.html#...` | `record` (launcher); Godot page outside the shell until Phase 4 |
| **System** | OPS Console | Technical status: release, model, checks, limitations, browser; gains the ship-state record with classes and the interface-profile note | `/status/` | `record` |

Decisions inside this table:

- **Simulations keep their `/engineering/...` URLs.** They are generated by `story.py` beside their studies and are linked from the
  records; moving them buys nothing and breaks links. The module is a registry grouping. The Simulations switch opens a generated
  section of the Engineering index (`/engineering/#simulations`, Phase 1) and may get its own index page in Phase 2.
- **No Propulsion, Thermal, Power, Habitat, Life Support or Navigation module yet.** Their web functionality today is drawers of the
  Ship module and records. Phase 2 adds one generated **Systems** view (`/systems/`, from `wos.json`: per subsystem the sourced
  values, statuses, a deep link into the viewer focus `viewer/#style=hybrid&focus=s:S10` and its records). A subsystem becomes a
  module only when it has functionality of its own.
- **Alerts is not a module.** It is the advisories chip and a section of System, fed by the problem register and OPEN/HOLD items.
- The registry (`MODULES` in `tools/wos.py`) is the one list of id, label, station, entry URL, kind and member paths.

---

## 6. Adaptive layout strategy

### 6.1 Shell CSS (added to `site.css`)

```css
body.wos { display: grid; grid-template: "bar" auto "work" minmax(0, 1fr) / minmax(0, 1fr); min-height: 100dvh; }
body.wos[data-kind="app"] { height: 100dvh; overflow: hidden; }            /* the viewport is the workstation */
.wos-bar  { grid-area: bar; position: sticky; top: 0; z-index: 10; min-height: var(--bar-h); }
.wos-work { grid-area: work; position: relative; min-width: 0; min-height: 0; container: work / inline-size; }
@media (max-width: 699px), (max-height: 499px) {                           /* terminal */
  body.wos { grid-template: "bar" auto "work" minmax(0, 1fr) "nav" auto / minmax(0, 1fr); }
}
@media (max-height: 499px) and (min-width: 500px) {                        /* short landscape: rail, not a bottom bar */
  body.wos { grid-template: "nav bar" auto "nav work" minmax(0, 1fr) / auto minmax(0, 1fr); }
}
@media (pointer: coarse) { .wos-bar a, .wos-nav a, .wos-work :is(button, select, summary, input) { min-height: 44px; min-width: 44px; } }
```

Padding uses `env(safe-area-inset-*)` (the pages already set `viewport-fit=cover`). Heights use `dvh` so a phone's collapsing
address bar never hides the module bar.

### 6.2 Workspace compositions (the module decides; these are patterns, not a fixed three-pane)

| Pattern | Used by | Wide (`@container work (min-width: 1100px)`) | Medium | Narrow (`< 700px`) |
| --- | --- | --- | --- | --- |
| **Canvas** | Ship, Compare, Build | canvas fills the cell; panels are absolutely placed inside the workspace on named grid lines (left: legend; right: active drawer; bottom-left: pick record; top: toolbars). Phase 3: docked and resizable | one drawer at a time over the right edge | toolbars wrap above the module bar; drawer is a bottom sheet, max 50 % height, the ship stays visible above it |
| **Simulation** | Ignition, Dust, Breakthrough Lab | `"modes modes" "stage side" "tools side"`: the stage takes all remaining height (no `68vh` cap), levers and readouts in the side panel; the record tail (assumptions, tables) starts below the first viewport | stage above, side panel below in two columns | **sticky stage** (about 45 dvh) with modes, tools, levers and readouts scrolling under it; tables in `<details>`. Every control stays, none is hidden |
| **Record** | Records, System, launchers | text column 76 ch; the freed width carries a sticky section index (left) and context (right: status, sources, related simulation). Wide tables may use the full workspace width | text column + index as a `<details>` on top | single column; tables scroll in `.scroll` (already focusable) |
| **Overview** | Overview | grid: entry tiles, ship state, advisories, release; no scroll at 1366 x 768 | two columns | one column, flows |

Rules: the workspace never uses a viewport media query for its own composition (container queries only), so a docked panel or a
future split view works without new CSS. Nothing is removed with `display: none` unless a visible toggle brings it back.

### 6.3 Canvas in a grid cell

`viewer.js` sizes from the window (`:540`, `:562`). Phase 1 changes those two places to the canvas's `getBoundingClientRect()` and
adds a `ResizeObserver`, as `ignition.js` and `dust.js` already do. The canvas becomes `position: absolute; inset: 0` in `.wos-work`;
overlays change from `fixed` to `absolute` in the same container, which also removes the dependency on magic top offsets. The canvas
centre moves down by half the bar height (18 px), inside the tolerance of the check's fixed click points.

### 6.4 Preferences and keyboard

- **Preferences**: one `localStorage` key `wos.v1` (JSON), every access wrapped in try/catch, the page correct without it. Holds
  presentation only: panel open/closed per module, density, later the profile override and panel sizes. Never ship, simulation or
  scenario state. Godot keeps its own controls storage.
- **Shortcuts** (chosen to collide with nothing in `viewer.js` (1-5, S, H, E, X, F, D, I, P, Home, Esc), `build.js` (arrows) or the
  browser): `g` then `o s m r a y` = Overview, Ship, siMulations, Records, Aboard, sYstem; `[` and `]` toggle the left and right
  panel; `\` focus mode (hide bar and nav; Esc or `\` returns); `?` shortcut sheet. Ignored while typing in a field and inside the
  Godot page. Focus mode and fullscreen are the same class plus `requestFullscreen()` where available.
- **Page changes** use CSS cross-document view transitions (`@view-transition { navigation: auto; }`, bar named so it holds still),
  off under `prefers-reduced-motion`. No JavaScript, ignored by browsers without support.

---

## 7. Shared state strategy

### 7.1 Five classes, five homes

| # | Class | Example | Lives in | Mark on screen | May the shell show it |
| --- | --- | --- | --- | --- | --- |
| 1 | **Specification** (canon and derived) | ring floor radius 28 m WORKING; target speed 0.016 c LOCKED | `data/wayfarer_3d.toml` → `wos.json.spec` | existing status chip (`.st-*`) + source ref | yes |
| 2 | **Nominal operating condition** | COAST: drive OFF, rings ROTATING 4.0 rpm, 0.50 g at the floor, thermal LOW; cabin 80 kPa, O2 20 kPa | `[configuration.*]`, `[habitat.atmosphere]` → `wos.json.configurations`, `.nominal` | value + `NOM` + the configuration's status | yes, for the reference configuration |
| 3 | **Simulation state** | a dust grain's outcome, ignition quench time, a lever position | the module's memory and its URL hash | `SIM` chip (info colour), the panel titled as a simulation | only as the scenario chip |
| 4 | **Scenario state** | Deadship "Dark Bus": bus B tripped | the Godot scene / the module | `SCENARIO` chip (warn colour) with the scenario name | only as the scenario chip |
| 5 | **Illustrative / prototype** | any example reading, device hardware traits | nowhere in `wos.json.spec`; if ever needed, `wos.json.examples` with a mandatory label | `EXAMPLE` text + hatched underline; PROTOTYPE chip for choices | never in the bar |

Unknowns stay unknown: a `known = false` item renders as `OPEN` with its reason, never as 0 or a dash that looks like a reading
(`power.rating` is the first case: the bar must not say "BUS A OK").

### 7.2 The record: `wos.json`

Written by `tools/wos.py status(spec)` during `web_export.run()` (and by `story.py --out` for the no-Blender preview). It reuses
`sim_rig.quantity()`, `sim_rig.configurations()`, `sim_rig.rings()` and `story.ship_numbers()` so no formula is written twice.

```json
{ "contract": "WF_WOS_STATUS", "version": 1, "spec_hash": "...", "vessel": "G.U. WAYFARER 001",
  "reference_configuration": "COAST",
  "spec": { "crew_rated": {"value": 12, "unit": "persons", "canon_status": "LOCKED", "source_ref": "crew"},
            "ring_rpm": {...}, "ring_floor_radius": {...}, "spin_gravity": {"value": 0.50, "unit": "g", "canon_status": "DERIVED", "formula": "..."},
            "cabin_pressure": {...}, "cabin_o2_partial": {...}, "target_speed": {...}, "mission_duration": {...}, "length": {...},
            "power_rating": {"known": false, "canon_status": "OPEN", "reason": "..."} },
  "configurations": { "COAST": {"drive": "OFF", "habitat": "ROTATING", "thermal_load": "LOW", "eye_mode": "QUIET_WATCH",
                                "canon_status": "BASELINE", "source_ref": "config_coast"}, "...": {} },
  "surfaces": { "viewer": "COAST", "play": "DOCKED" },
  "advisories": { "open_problems": 11, "open_spec_items": 0, "holds": ["Flight EVA: HOLD (S&E 45 O-07)"] },
  "modules": [ {"id": "ship", "label": "Ship", "station": "Engineering Workstation", "href": "viewer/", "kind": "app"} ],
  "examples": {} }
```

- `reference_configuration` is `vehicle.saved_preset` (COAST): the configuration the published model is built in. `surfaces` records
  that the walk package is DOCKED, so the Aboard launchers can say "rings stopped and locked" from data instead of prose.
- **Baked, not fetched.** `tools/wos.py` renders the bar from this record into every page at assembly. The start page needs no extra
  data request; System (and later Systems) fetch `wos.json` for the full table. `release.json` gains `experiences.wos` (its bytes, hash).
- **Validation in `verify_site`**: every `spec` and `configurations` entry has a `canon_status` and a `source_ref` or `formula` that
  exists in `data/source_map.toml`; `known = false` entries carry no `value`; `examples` entries carry a `label`; every HTML page
  has exactly one baked bar and no unreplaced marker.
- **No mission clock.** No canonical epoch or mission date exists in the spec, so the bar shows none (open owner question 2).

### 7.3 Scenario isolation

- A module announces a running simulation with `wos.scenario({ id, label, class })` and clears it on stop. It is a property of the
  page: gone on navigation, never stored, never read by another module. The nominal chips are static HTML that no script writes to.
- Simulation parameters stay in the URL hash (the existing, shareable practice). `sessionStorage` is used only if a scenario must
  survive a reload inside one tab, namespaced `wos.scn.<module>`; `localStorage` never holds scenario state.
- The Godot scenes already keep Deadship state in-engine. When the Godot page gets the bar (Phase 4), it shows the scenario chip from
  `window.wayfarerWalk` / `wayfarerEva`, which the scenes already publish once a second.

---

## 8. Technical implementation plan

**Decision: vanilla CSS and JavaScript.** The site is static, multi-page, has 9 hand-written scripts and no build step for them; a
framework would add a bundler, a dependency and a hydration cost to solve a problem (a shared bar and a layout grid) that CSS grid,
container queries and 6 kB of script solve. Nothing found argues otherwise.

### 8.1 Files

| File | Change | Why this and not something smaller |
| --- | --- | --- |
| `tools/wos.py` | **new**, standard library: `MODULES`, `status(spec)`, `bar(rel_path, module, status, release)`, `bake_site(site, status, release)`, `write(site)`, `validate(status, source_map)`, CLI `--out DIR` (copy `web/`, run `story.build`, bake; no Blender) | one owner for the registry, the record and the bar; `story.py` (2,538 lines) and `web_export.py` should not grow a second job |
| `web/wos.js` | **new**, classic deferred script, ≤ 6 kB: preferences, panel toggles (`[data-wos-toggle]`, `aria-expanded`), shortcuts, focus/fullscreen, `wos.scenario()`, sets `html.js` | the only behaviour every page shares; a module script would break the start-page rule and load order |
| `web/site.css` | shell block (≤ 8 kB): `.wos-*`, the three workspace patterns, value/unit/class marks, coarse-pointer targets, view transition; remove `.wrap` max-width from workspace pages; `.sitebar` rules become `.wos-bar` | all pages already load it; no new request |
| `web/viewer/index.html`, `viewer.css` | load `../site.css` before `viewer.css`; delete the duplicated token block and base rules; `.title` header replaced by the bar marker; overlays `absolute` in `.wos-work` | ends the design island; the viewer pays 9.5 kB gzipped on a 7 MB page |
| `web/viewer/viewer.js` | size and pointer maths from the canvas rect; `ResizeObserver` | required by 6.3; two call sites |
| `web/index.html` | Overview: bar marker, tile grid keeping `#go-*`, state and advisory panels (baked), `#release` kept; hero removed | Phase 1 surface |
| `web/status/index.html`, `status.js` | bar marker; System sections for `wos.json` (classes, sources) and interface profiles (PROTOTYPE) | Phase 1 surface |
| `tools/story.py` `page()` | emits the bar marker with `module` and `kind`; drops its own `.sitebar` and crumbs duplication; `dust_page` (and `ignition_page`, same `.ign` markup) use the Simulation pattern | one template serves all 25 pages |
| `web/engineering/ignition.css`, `dust.css` | `.ign` becomes the Simulation pattern with container queries | shared by both pages already |
| `tools/web_identity.py` | add aliases `cls-sim`, `cls-scenario`, `cls-example`, `adv-caution`, `adv-warning` onto the status layer; drop `viewer_block` once the viewer loads `site.css`; Phase 4: a Godot token target | colour stays generator-owned; no new hue is needed |
| `tools/web_export.py` | call `wos.write()` and `wos.bake_site()` before `release_record`; `START_BUDGET` 60 → 68 kB; start page may name `<script src="wos.js"`; add `site.css`, `wos.js` to `viewer_files`; `verify_site` gains the 7.2 validations | the gate that already exists |
| `tools/web_check.py` | start request list `+ wos.js`; new part `layout` (section 10); axe run | see 8.3 |
| `.github/workflows/web-explorer.yml` | add `layout` to the browser-check matrix and to the merge list | one more parallel part, no new service |

**The bar marker.** Pages carry `<!--wos:bar module=ship kind=app-->`; `bake_site` replaces it in every `.html` under the site except
the Godot export, computing the relative prefix from the file's path. Static pages and generated pages go through the same pass, so
the advisories count (known only after `story.build`) is available to all of them. Raw files in `web/` show no bar; they were never
servable without an export, and `python3 tools/wos.py --out runs/wos-preview` gives a full no-Blender preview in about 25 s (the viewer page
opens without a model there).

### 8.2 Layers A to D in the codebase (how explicit)

| Layer | Representation | Deliberately not built |
| --- | --- | --- |
| A data and state | `wos.json` + the existing per-feature JSON (`fuel-*.json`, `dust.json`, ...); pure modules stay the only formulas | no client-side store, no event bus |
| B modules | the `MODULES` registry + each module's existing script | no module loader, no plugin interface |
| C profiles | CSS media and container queries; `data-kind`, later `data-profile`; station label string | no per-device templates |
| D presentation | shell CSS, `wos.js`, the three patterns | no component library |

### 8.3 Checks

- `verify_site`: identity block current (exists), bar baked once per page, `wos.json` valid, budgets, start page names only `wos.js`.
- `web_check --part layout`: the seven-viewport matrix of section 10 on the Phase 1 pages, with screenshots (these are the owner's
  visual comparison).
- **axe-core, automated for the first time**: the pinned npm tarball (integrity-checked and cached like three.js in
  `~/.cache/wayfarer/web`, never copied into the site) is injected through CDP on each Phase 1 page at three viewports; any WCAG 2 A/AA
  violation fails. `docs/WEB_IDENTITY.md` then cites a check instead of a past manual run.
- No unit test for layout or wording (AGENTS.md test policy). One unit test is justified: `wos.status(spec)` returns the spec's own
  values and statuses for the fields the bar shows (owner numbers).

---

## 9. Migration strategy

| Phase | Scope | Exit |
| --- | --- | --- |
| **1 Foundation** (one session) | `tools/wos.py`, `wos.json`, bake pass, shell CSS, `wos.js`; **Overview** (`/`), **Ship** shell around the canvas (`/viewer/`), **Dust** as the Simulation pattern (`/engineering/dust/`; Ignition gets it through the shared `.ign` CSS), **System** (`/status/`); every other page gets the baked bar only; layout part + axe in `web_check`; docs | section 10 passes on four surfaces; all existing checks pass; preview for the owner |
| **2 Integration** | Records pattern for all Engineering pages (index, context, full-width tables); Build, Compare, Breakthrough Lab as workspaces; Aboard launchers; `/systems/`; Simulations index; one control family replacing `.itools`/`.btools`/`.ctools`/`.chips`; viewer drawers and toolbars regrouped; ship silhouette on Overview from `hull_geometry` | every page is a WOS workspace; no page-specific button CSS left |
| **3 Workspace optimization** | docked and resizable panels (pointer + keyboard), focus and fullscreen everywhere, density preference, profile override, split view where a module asks for it | measured: work area share, no regressions in the SW viewer benchmark |
| **4 In-world** | Godot token target from `web_identity.py`; HUD profiles per activity (cuff, OPS, slate, EVA display, burn console); the bar on the Godot page; **touch controls for Explore Exterior** (the standing parity gap) | `runtime-export`, browser checks |
| **5 Canon** | proposed device and interface rows for the Technology workbook, as a draft for the owner | written to Drive only on authorization |

Why **Dust** is the Phase 1 simulation: it is fully procedural (no GLB, no engine parts), so it runs from the no-Blender preview and in
every check; it has the richest control surface (7 modes, grain and shield levers, readouts, four tables); the browser check already
covers it on a phone; and its CSS is shared with Ignition, so one pattern proves two pages. Build and Compare depend on the 5.9 MB GLB
and add nothing to the proof.

Order inside Phase 1 (each step leaves a working site): (1) `wos.py` + record + bake pass + bar CSS, bar on all pages, old layouts
intact; (2) checks updated, existing suite green; (3) Overview; (4) System; (5) viewer in the grid; (6) Simulation pattern; (7) layout
part + axe; (8) docs. If time runs out, step 6 or 5 moves to Phase 2 and the foundation still stands.

---

## 10. Performance and accessibility acceptance criteria

### 10.1 Performance (measured, reported with before and after)

| Criterion | Today | Limit after Phase 1 |
| --- | --- | --- |
| Start page requests | `index.html`, `site.css`, `release.json` | the same + `wos.js` (4); no canvas, engine, model, library or module script |
| Start page raw bytes (`index.html` + `site.css` + `wos.js`) | 46.3 kB (5.4 + 41.0) | ≤ 68 kB budget, target ≤ 64 kB; gzip target ≤ 20 kB |
| `wos.js` | - | ≤ 6 kB raw, no dependency, deferred, no work before first paint |
| Shell CSS added to `site.css` | - | ≤ 8 kB raw |
| `wos.json` | - | ≤ 8 kB; not requested by the start page |
| Layout shift from the shell | - | 0 (bar is baked HTML) |
| Viewer download | 7.35 MB (budget 12 MB) | + ≤ 60 kB; budget unchanged |
| Viewer rendering | 3,987 draw calls Standard; SW medians in `web/README.md` | draw calls identical; SW median frame time at 1280 x 800 three-quarter within ±5 % (evidence class SW, relative only); canvas pixel count not larger than today |
| Simulation pages | three.js on click or `#autostart` only | unchanged; 10 draw calls split view, 24 to 30 trip view |
| Godot package | 62.9 MB (budget 90 MB) | untouched in Phases 1 to 3 |
| Memory after leaving an experience | back to start-page level (+200 MB tolerance) | existing check unchanged and passing |
| Resource disposal | `pagehide` releases contexts | unchanged; `wos.js` holds no references to module objects |

### 10.2 Accessibility

- axe-core: 0 WCAG 2 A/AA violations on Overview, Ship (before and after model load), Dust, System at 1920 x 1080, 820 x 1180, 390 x 844.
- Contrast: body and secondary text ≥ 7:1, small labels ≥ 4.5:1 on every new surface colour (bar, panels, sheets); checked from the
  token values in the generator.
- Keyboard: Tab order is bar, module switcher, workspace, panels; every panel toggle has `aria-expanded` and `aria-controls`; a skip
  link jumps to the workspace; every shortcut has a visible control with the same function; focus ring 2 px on every focusable.
- Targets: with a coarse primary pointer, shell controls and the primary controls of the four Phase 1 surfaces are ≥ 44 x 44 px; no
  interactive element anywhere is under 24 x 24 px (WCAG 2.2 AA). Remaining sub-44 px controls (viewer legend rows and chips) are
  listed in TODO for Phase 2, not hidden.
- Reduced motion: no view transition, `--dur: 0ms` (exists); focus mode has no animation.
- State never by colour alone: class marks are words (`NOM`, `SIM`, `SCENARIO`, `EXAMPLE`), statuses keep their glyphs.
- Without JavaScript: bar, module switcher, status sheet and all record content work; panels are open in normal flow.

### 10.3 Viewport matrix (`web_check --part layout`)

| Viewport | Expected profile | Pointer emulated |
| --- | --- | --- |
| 2560 x 1080 ultrawide | workstation | fine |
| 1920 x 1080 desktop | workstation | fine |
| 1366 x 768 laptop | workstation | fine |
| 1180 x 820 tablet landscape | workstation, 44 px targets | coarse |
| 820 x 1180 tablet portrait | compact, 44 px targets | coarse |
| 390 x 844 phone portrait | terminal, bottom module bar | coarse |
| 844 x 390 phone landscape | terminal, left rail | coarse |

Per viewport and Phase 1 surface, the check asserts **function, not fit**:

1. no horizontal overflow of the document; the bar and the module switcher are inside the viewport;
2. all six module links are present and activatable (click or tap navigates);
3. **parity**: the set of interactive elements (by id or accessible name) is identical on all seven viewports, and each is either
   visible or inside a panel whose toggle is visible;
4. workspace share: on `app` surfaces the workspace is ≥ 88 % of the viewport area on workstation profiles and ≥ 70 % on terminal;
5. Overview does not scroll at 1366 x 768;
6. Ship: every `data-view`, `data-style` and drawer toggle responds (state attribute changes); model load itself is asserted at 1280 x 800
   and 390 x 844 only, as today, because SwiftShader makes seven loads too slow;
7. Dust: `#autostart` reaches `window.__dust.ready`, a lever change alters a readout, a mode switch alters `data-mode`, the study
   check points reproduce, on every viewport;
8. System: the release and the ship-state table render; each value shows a status or class mark;
9. targets ≥ 44 px on coarse viewports for the elements named in 10.2;
10. a screenshot per cell is saved as the comparison set.

---

## 11. Permanent principles and documents

**Authority.** A new `docs/WOS.md` is the one standard (concept, registry, profiles, workspace patterns, data classes, `wos.json`
contract, checks, the review matrix). It is justified because the content fits none of the existing documents:
`docs/WEB_IDENTITY.md` owns colour and components, `docs/WEB_GRAPHICS.md` owns rendering budgets, `web/README.md` describes the site
as built. Each of them links to `docs/WOS.md` instead of repeating it. This file (`work/.../WOS_ARCHITECTURE.md`) is deleted on
approval, as `work/` rules require; its lasting parts move into `docs/WOS.md`.

**AGENTS.md**, new section after "Web Graphics Engineering" (exact text):

```markdown
## Wayfarer Operating System

The website is the ship's interface, not a site about the ship: one ship, one operating system, multiple devices.
`docs/WOS.md` is the standard (modules, profiles, workspace patterns, data classes, checks); TODO section O is its tracker.

- **One shell.** Every page is a module workspace under the generated ship line (`tools/wos.py`). A new simulation, visualization,
  subsystem view or experience joins a module in the registry; it is never an isolated page with its own navigation.
- **Functional parity.** Width, height, orientation and pointer choose the layout profile (workstation, compact, terminal), never the
  feature set and never by user agent. A control hidden at one size is reachable through a visible toggle at that size. One
  implementation of each simulation and calculation serves every profile.
- **The viewport is the workstation.** `app` workspaces fill it: no hero, bezel, casing or max-width; the canvas, stage or diagram
  takes the space and panels dock, collapse or become drawers. Long records keep a reading width and scroll.
- **Five data classes stay apart**: specification, nominal operating condition, simulation state, scenario state, illustrative. Shell
  values come only from `wos.json` (generated from `data/wayfarer_3d.toml` with status and source); a simulation or scenario never
  writes to it or to another module; an example is labelled where it is shown; an unknown is shown as OPEN, never as a number.
- **Function makes the look.** Colour carries state and hierarchy through the generated tokens (`docs/WEB_IDENTITY.md`); no decorative
  hardware, glow, scan lines or controls without a function. Fictional devices are profile labels on the web and HUD configurations in
  Godot, PROTOTYPE until canon names them.
- **Light and accessible.** Vanilla CSS and JavaScript, no framework without a measured need; heavy modules load on demand; the
  budgets of `tools/web_export.py` and `docs/WEB_GRAPHICS.md` and the layout and axe checks of `tools/web_check.py` hold.
```

Also in AGENTS.md: the "Where things go" row for `godot/`, `web/` reads "...the website (the WOS modules: Overview, Ship, Simulations,
Records, Aboard, System)"; the check table gains a row "Web pages, `web/wos.js`, `tools/wos.py` | `python3 tools/wos.py --out
runs/wos-preview`, then `web_check --part layout` on a built site".

**CLAUDE.md**, new section after "Web graphics" (exact text):

```markdown
## Wayfarer Operating System

Apply AGENTS.md "Wayfarer Operating System". Before changing a web page, its navigation, layout or any value shown in the shell,
read the relevant section of `docs/WOS.md` and TODO section O. New web functionality joins a module of the registry in `tools/wos.py`
and must work on every layout profile; never add a page with its own navigation, a device-specific copy of a feature, or a typed ship value.
```

**Other documents.**

| Document | Change |
| --- | --- |
| `docs/WEB_IDENTITY.md` | scope line: the Godot scenes follow in WOS Phase 4; "Components": `.sitebar` → the shell components and the value/unit/class marks, the advisory levels on the status layer; "Accessibility": axe is automated in `web_check`; token table gains the aliases; link to `docs/WOS.md`. No layout rules here |
| `web/README.md` | path table: `wos.js`, `wos.json`, the baked bar, the Loads column for `/`; "Sources here": `tools/wos.py`; "What the browser check covers": the layout part and axe; local preview: `tools/wos.py --out` |
| `docs/WEB_GRAPHICS.md` | §2 delivery: start budget 76 kB; §9.4 unchanged; one line that shell work obeys the same budgets |
| `docs/IMPLEMENTATION.md` | web section: `tools/wos.py` and the bake pass |
| `TODO.md` | new section **O — Wayfarer Operating System track** with WOS-1 to WOS-5 (phases), the sub-44 px control list, touch EVA parity; P05 keeps the unrelated follow-ups and loses nothing |
| `README.md` | one sentence on the site if it describes the old start page |

---

## 12. Decisions, risks, owner questions

### 12.1 Decisions

| # | Decision | Reason | Rejected |
| --- | --- | --- | --- |
| D1 | Multi-page site with a shared baked shell | keeps click-to-load isolation, memory release, every URL and the whole check suite | single-page app with a router: reloads nothing, leaks engines, needs a framework |
| D2 | Vanilla CSS + one classic script | the need is a grid, queries and 6 kB of behaviour | a UI framework or web components library: dependency and build step with no function gained |
| D3 | The bar is baked at build time from one registry | no layout shift, works without JavaScript, values generated, one nav source for 31 pages | bar built by script at runtime (flash, no-JS failure); hand-copied nav (today's inconsistency) |
| D4 | Ship state as generated `wos.json`, reusing `sim_rig` and `story` functions | one source, statuses and sources travel with values | values typed into HTML without status or source (v1's mock); a client-side state store |
| D5 | Screen picks a layout profile; devices are labels (web) and HUDs (Godot) | functional parity; a slate is an activity, not a width | v1: phone = cuff, tablet = slate |
| D6 | Two workspace kinds, three patterns chosen by the module | a canvas and a record need different compositions (brief §5) | one three-pane layout for everything |
| D7 | Container queries inside workspaces, media queries only for the shell | a docked panel changes the workspace width, not the viewport | viewport breakpoints everywhere (today: 560, 640, 760) |
| D8 | No mission clock, bus health or consumables in the shell | no canonical source; fabricated telemetry is banned | labelled example telemetry in the bar |
| D9 | Simulations keep `/engineering/...` URLs; module membership is registry data | generated beside their studies, linked from records, covered by checks | moving them under `/simulations/` with redirects (GitHub Pages has no server redirects; meta-refresh stubs for nothing) |
| D10 | The viewer loads `site.css`; its own token block and base rules go | one design system, one button family; 9.5 kB gzipped on a 7 MB page | generator copies shell CSS into `viewer.css` (two copies to keep in step) |
| D11 | Preferences in one wrapped `localStorage` key, presentation only; simulation state stays in the hash | isolation by construction; links stay shareable | a global state object in storage |
| D12 | Start page loads `wos.js`; budget 60 → 76 kB raw (measured in Phase 1; about 19 kB gzipped) | uniform shell behaviour (shortcuts, panels) on every page for about 2.5 kB on the wire | a script-free start page with a different shell from the rest |
| D13 | axe-core runs in `web_check`, injected, never shipped | the standard claims it; today nothing enforces it | keep it manual |
| D14 | Leader-key shortcuts (`g` + letter), `[ ] \ ?` | collide with no existing key and no browser key | F-keys (v1) |
| D15 | Phase 1 simulation is Dust | procedural, checked on a phone, richest controls, shares CSS with Ignition | Build or Ignition (need the GLB or engine parts) |
| D16 | The Godot page stays outside the shell until Phase 4 | it is a content-named export with its own check contract; changing it makes the package STALE | wrapping it in an iframe now |

### 12.2 Risks

| Risk | Mitigation |
| --- | --- |
| Viewer check coordinates and framing shift when the canvas enters the grid | keep every id; canvas centre moves 18 px; run `web_check --part main` locally (Blender, Chrome and a pipeline run are present in this container) before pushing |
| `site.css` base rules (bare `button`, `.panel`, `table`) restyle the viewer | load order `site.css` then `viewer.css`; compare the existing desktop viewer screenshots of `web_check` before and after; fallback is to scope the base rules, not to fork tokens again |
| Start budget pressure (46.3 kB used of 60) | budgets in 10.1 are per file; the lunar scene (28 kB of the stylesheet) is the reserve if the owner prefers 60 kB kept |
| Phase 1 too large for one session | the order in section 9 leaves a working site after every step |
| `ignition.css` is shared: the Simulation pattern changes Ignition too | intended; its phone check (`engineering/ignition/#autostart`) is in the main part and must stay green |
| 44 px targets crowd the viewer on phones | Phase 1 applies them to the shell and primary controls only; the rest is listed, AA minimum (24 px) asserted |
| "Feels like an OS" is subjective | the owner reviews the screenshot matrix; the measurable proxies are workspace share, parity and the absence of page chrome |
| Scope creep into empty modules | registry rule: a module needs existing functionality (section 5) |

### 12.3 Open owner questions

1. **Preview.** The established workflow gives a branch only a downloadable artifact (`wayfarer-web-site`, 14 days) and screenshots;
   GitHub Pages deploys `main` only, and Pages from Actions serves one site, so a live branch URL does not exist. Is the artifact plus
   the screenshot matrix enough for review, or do you want a live preview (for example a second static host for `claude/*` branches,
   which is a new publication target and needs your go)?
2. **Mission clock.** Is there a canonical epoch (a First Ignition date, a mission day) the ship line may count from? Until then it
   shows none.
3. **Start-page budget.** Accept 60 → 76 kB raw (measured: the shell CSS, the baked ship line and state table, and `wos.js`; about 19 kB gzipped), or hold 60 kB and trim the lunar scene?
4. **Module names.** Overview, Ship, Simulations, Records, Aboard, System: keep, or do you prefer ship-style designations?
