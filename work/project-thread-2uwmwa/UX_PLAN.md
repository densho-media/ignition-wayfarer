# WOS UX plan: navigation, visual hierarchy, first-time experience

Answer to `BRIEF_UX.md` (owner brief 2026-11-21 09:30Z). Principle: **Show first. Explain progressively. Let users explore.**
Basis: `docs/WOS.md`, `WOS_ARCHITECTURE.md` §3–7 and §12, `tools/wos.py`, `web/`, `tools/story.py`, the `after/` screenshot matrix.
Nothing here changes canon, a route, a simulation or a calculation. Decisions are marked **D-UXn**; open owner points are in §9.4.

## 1. Findings

Measured on the built preview (`runs/wos-preview`): start page 74,098 B of the 76,000 B budget (index 15.7 kB, of which about 9 kB is
the baked state table and advisory list). The redesign has 1.9 kB of headroom unless it removes something (§9.3).

**A. New visitor** (`overview_laptop.png`, `overview_phone-port.png`, `compare_laptop_1366x768.png`)
- No picture of the ship anywhere on the entry page. The only imagery is the lunar background, which is not the ship.
- The first thing read after the name is process language: "generated from sourced or labelled parameters. Nothing heavy loads until
  you open a module." It answers how the site is built, not what Wayfarer is or why to care.
- A third of the laptop viewport is the Ship state table: `config_coast`, `NOM`, `BASELINE`, `ω² r / g0`. It is Level 3 data in the
  Level 1 position, and it is the brightest, densest block on the page.
- Two of the three most attractive entries (Explore Interior, Explore Exterior) render at 50 % opacity with no reason given, so the
  page appears to lead with disabled features.
- Eleven links with equal weight; no primary action. Titles such as "0.016 c and back" need the context a newcomer lacks.
- Nothing states that the ship is fictional; the only disclaimer is the `SIMULATION_ONLY … REP_PROXY` note in jargon.
- Bar chips `COAST`, `RINGS 4.0 rpm · 0.50 g`, `ADV 12`, `OPS CONSOLE` are unexplained codes next to the navigation.

**B. Curious explorer** (`ship_laptop.png`, `ship_phone-port.png`)
- The ship is under **Ship**, the walk and the EVA under **Aboard**: one intention ("look at the spacecraft") split over two modules,
  with no link between them inside the modules.
- The viewer opens with 15 unlabelled-by-purpose buttons and no hint for orbit, zoom or picking. "Engine holo", "Hybrid", "Appearance"
  say nothing before they are tried. No title names what is on screen.
- Phone: the camera row and the footer overlap ("Assemblies" sits on the build line), and two toolbars occupy both ends of the canvas.
- Interior and Exterior launchers open with a 90-word lead and a controls essay before the Start button's context is clear.

**C. Simulation user** (`dust_laptop.png`, `dust_phone-port.png`)
- **Simulations** in the bar opens `engineering/#simulations`, a block of text teasers in the middle of the Engineering page, and the
  bar then marks **Records** as current. The module has no home.
- A simulation page shows the stage and about 20 controls at once; the question it answers, what to try first and how to read the
  result sit below the fold in prose ("The question for you", "How the simulation works").
- Presets are labelled ("Giotto at Halley") but not what changing them demonstrates; the result panel does not link to the open problem
  it evidences.
- Phone: the sticky stage plus the readout overlay leave the first control off screen; the mode tabs are cut by the ship line.

**D. Technical visitor** (`records_laptop.png`, `system_laptop.png`)
- Three names for one thing: bar "Records", breadcrumb "Wayfarer / Engineering", URL `engineering/`, title "0.016 c and back".
- "System" mixes ship state (in-world), advisories (engineering), interface profiles (about the site) and the release review (build
  diagnostics). "System status" does not say which.
- The Engineering index has two navigation rows of different kinds (section anchors and page links mixed in one pill row, then four
  "ENGINEERING 2.0" cards) before any content; sub-pages (Baseline, Weakest Links, Evolution, Vertex, 14 lab entries) have no shared
  section navigation, only a two-step breadcrumb.
- Good and kept: values with status and source, the problem register, shareable URLs.

**E. Mobile visitor** (`overview_phone-port.png`, `overview_tablet-port.png`)
- Six bottom tabs at 390 px: "SIMULATIONS" and "RECORDS" touch; labels are 10 px capitals.
- The first phone screen is text only; the first usable entry is greyed out; the 3D ship is on the third screen.
- Tablet portrait (820 px) hides all module names: six icons alone, of which the waveform, the door and the dial are not self-evident.

Common cause: the Overview was built as a status report (WOS Phase 1 goal), every item has the same visual weight, and the registry
is organised by how the site is built (viewer, Godot, story pages) rather than by what a visitor wants to do.

## 2. Information architecture

### 2.1 Decision on the owner's proposal

**D-UX1: adopt Overview → Explore → Simulations → Engineering → Status, five primary modules.** It maps one-to-one to the five
intentions of the brief, removes the Ship/Aboard and Records/Engineering ambiguities, and five items fit a 390 px bottom bar with
readable labels. Two adjustments:

- **Status is in-world only**: ship state, advisories. Release review, interface profiles, browser support, shortcuts and the orientation
  become **utility** ("System", a `?` button at the end of the bar). Same page (`status/`), split by sections, so no route changes.
- **Simulations gets a home page** (`simulations/`, new, generated). It is the only added route; every existing route stays.

Rejected: keeping six modules with renames (does not fix the split of exploring); an Explore landing page with three cards (one more
click before anything moves; the secondary tabs do the same job in place); moving simulations to `/simulations/<name>/` (D9 stands).

### 2.2 Primary navigation (registry `MODULES`)

| # | id | Label | Icon | Key (`g` +) | Opens | Owns |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | `overview` | Overview | `overview` | `o` | `/` | `index.html` |
| 2 | `explore` | Explore | `ship` | `e` (alias `s`, `a`) | `viewer/` | `viewer/`, `interior/`, `exterior/`, `play/` |
| 3 | `sims` | Simulations | `sim` | `m` | `simulations/` | `simulations/`, `engineering/ignition/`, `dust/`, `build/`, `compare/`, `breakthrough-lab/` |
| 4 | `engineering` | Engineering | `engineering` | `n` (alias `r`) | `engineering/` | `engineering/` and every other page below it |
| 5 | `status` | Status | `status` | `t` (alias `y`) | `status/` | `status/` |

Old keys keep working as aliases (`data-wos-alias` on the link, read by `wos.js` next to `data-wos-key`). Labels are always visible
from 700 px up (five short words fit at 700 px; the `max-width: 899px` icon-only rule is deleted). Under 700 px: bottom bar, icon over
label, 11 px mixed case.

### 2.3 Secondary navigation (one row under the ship line, baked by `wos.py` as `<nav class="wos-sub">`)

| Module | Tabs | Target |
| --- | --- | --- |
| Overview | none | |
| Explore | **Ship 3D** · **Interior** · **Exterior** (icons `ship`, `interior`, `eva`) | `viewer/`, `interior/`, `exterior/` |
| Simulations | **All** · Ignition · Dust · Build sequence · Compare · Breakthrough Lab | `simulations/` and the five pages |
| Engineering | **Summary** · Baseline · Weakest links · Ship evolution · Vertex drive · Open problems · Lab records | `engineering/`, `baseline/`, `weakest-links/`, `evolution/`, `vertex/`, `engineering/#problems`, `engineering/#tried` |
| Status | **Ship state** · Advisories · System | `status/#ship-state`, `#advisories`, `#system` |

The row is 36 px, scrolls horizontally when it does not fit (scroll-snap, fade at the cut edge, the current tab scrolled into view by
`wos.js`), and marks the current tab with `aria-current="page"`. Registry: each module gains `sub: [{label, href, paths, icon?}]`;
`module_for` also returns the matching sub item. `play/` stays outside the shell (D16).

### 2.4 Contextual navigation (inside the workspace, belongs to the object on screen)

- Viewer: camera, display style, panels, focus bar (unchanged controls, regrouped in §7.2).
- Simulation: mode tabs, presets, levers, "Open the problem record" link from the result.
- Engineering index: the in-page section list (Goal, Constraints, The ship today, What we tried, Open problems, Follow along) as a
  sticky "On this page" list (right column from 1100 px, a `<details>` above the content below that). The page links in today's pill
  row ("Compare in 3D", "Build sequence") move to "Related" (§8).

### 2.5 Utility navigation (right end of the ship line)

| Element | Content | Change |
| --- | --- | --- |
| State chip | `COAST` + advisories count, opens the ship-state sheet | `RINGS` and `CABIN` chips stay from 1240 px and 1400 px; summary gets a visible text label "Ship state" for screen readers and a `title` |
| `?` System button (`icon help`) | sheet: Shortcuts · "Show the orientation again" · This screen (profile) · Release line · links System (`status/#system`), Source, Densho | new; replaces the station label and the footer links scattered over pages |
| Station label | removed from the bar; kept in the System sheet and `status/#system` | PROTOTYPE jargon leaves the first row |

Settings: there are none global today (panel states only). No settings page is added; the System sheet is where one would go.

### 2.6 Page map

| Page | Module → tab |
| --- | --- |
| `/` | Overview |
| `viewer/` | Explore → Ship 3D |
| `interior/`, `exterior/` | Explore → Interior, Exterior |
| `play/`, `play/walk-<hash>.html` | Explore (no shell; its back link reads "Explore") |
| `simulations/` (new) | Simulations → All |
| `engineering/ignition/`, `dust/`, `build/`, `compare/`, `breakthrough-lab/` | Simulations → its tab |
| `engineering/` | Engineering → Summary |
| `engineering/baseline/`, `weakest-links/`, `evolution/`, `vertex/` | Engineering → its tab |
| `engineering/<kind>/<name>/` (lab entries, problem map) | Engineering → Lab records |
| `status/` | Status (sections Ship state, Advisories, System) |

## 3. Overview redesign

`body.wos[data-kind="overview"]`, still an OS workspace: no marketing hero, no max-width on a workstation. Five blocks in this order.

### 3.1 Blocks and copy

**1 Identity band** (the ship, one sentence, the main action)

- Eyebrow: `IGNITION · fictional spacecraft`
- H1: `G.U. WAYFARER 001`
- Line: `A crewed fusion ship, designed as if it had to fly.`
- Primary action (`a.button#go-viewer`): `Explore the ship` · meta `3D model · about 12 MB` (size from `release.json`, as today)
- Secondary action (text link to `#about`): `What is this?`
- Visual: `ship-side` thumbnail (3:1), the whole ship in side view, bow right. The image is also a link to `viewer/` (`tabindex="-1"`,
  `aria-hidden`, so the button is the one accessible link).

**2 Experiences** (four cards; the fifth featured experience, the ship in 3D, is the band above)

| id | Thumb | Title | Line | Action | Availability |
| --- | --- | --- | --- | --- | --- |
| `go-interior` | `interior` | Walk inside | Walk the rotating habitat ring in half Earth gravity. | Enter the ship | `Desktop or touch · about N MB` |
| `go-exterior` | `exterior` | Go outside | Fly along the hull on a training spacewalk. | Start spacewalk | same; chip `Training simulation` |
| `go-sims` | `sim-dust` | Run simulations | See what breaks at ignition and at speed. | Open simulations | `5 simulations` (count from the registry) |
| `go-engineering` | `engineering` | Understand the engineering | The goal, the numbers and the open problems. | Read the engineering | `N open problems` (from `wos.json`) |

Each card is one `<a class="wos-card">`: thumbnail on top (16:9), icon + title, line, action label with arrow, availability row.
When `release.json` has no `play` entry, the two Godot cards keep full contrast, the action becomes `Not in this build` with the
`lock` icon and the card links to its launcher page, which explains (§7.3). `.off { pointer-events: none; opacity: .5 }` is no longer used.

**3 Key facts** (marker `<!--wos:facts-->`, rendered by `wos.facts(st)` from `wos.json` items; no typed value)

| Tile label (newcomer wording) | Item | Shown as | Sub-line (static words, generated numbers) |
| --- | --- | --- | --- |
| Length | `length` | `289.5 m` | bow shield to engines |
| Crew | `crew_rated` | `12` | design occupancy |
| Cruise speed | `target_speed` | `0.016 c` | c is the speed of light |
| Mission | `mission_duration` | `6.0 yr` | out and back |
| Gravity on the ring | `spin_gravity` | `0.50 g` | rings turn at `ring_rpm` rpm |
| Open problems | `advisories.problems` | `11` | where the design still fails → `engineering/#problems` |

Heading: `The ship in numbers`. Under the strip one disclosure, closed by default, works without JavaScript:
`<details class="wos-facts-src"><summary>Status and sources</summary>` holding a six-row table (label, value, class chip, canon status,
`source_ref`) and the link `Full ship state` → `status/#ship-state`. The Overview no longer embeds the full state table or the advisory
list (`<!--wos:state-->`, `<!--wos:advisories-->` leave `web/index.html`; both stay on `status/` and in the sheet of other pages).
On the Overview the sheet links to `status/` instead of embedding the table (the existing `local` branch of `bar()`), which returns
about 9 kB to the start budget. `#go-status` is the "Open problems" tile's sibling link `Ship status` at the end of the strip.

**4 Project context** (`<section id="about">`)

- Heading: `About this project`
- Text (two sentences, 34 words): `Wayfarer is a fictional spacecraft from the IGNITION world, worked out with real physics and
  engineering methods. It is an evolving design, not a real or operating ship: some problems are solved, others are still open.`
- Links: `How we work` → `engineering/#goal` · `Source` · `Densho`
- The `SIMULATION_ONLY / REP_PROXY` sentence moves into `<details><summary>What the labels mean</summary>` in the same block.

**5 Foot**: release line (`#release`, required by `web_check`), nothing else.

Word count of visible Overview copy: about 380 today, about 120 after (titles, lines, actions, context).

### 3.2 Layout per profile

| Profile | Grid |
| --- | --- |
| Workstation ≥ 1100 px, height ≥ 700 px | Rows: band (text 5 cols, image 7 cols, 190 px high) · four cards in one row (about 315 × 300 px at 1366) · facts strip of six tiles in one row (84 px) · context and foot in one row (two columns). Sum at 1366 × 768: 44 + 190 + 300 + 84 + 64 + 5 gaps of 14 = 752 px: fits without page scroll. The no-scroll lock (`height: 100dvh; overflow: hidden`) is **dropped**: the page scrolls normally if a disclosure opens or the window is short. |
| Ultrawide ≥ 1800 px | Same rows, content capped at 1760 px and centred; the band image grows to its 1920 px source, cards stay ≤ 420 px wide. |
| Compact 700–1099 px | Band stacked (image on top, full width, 3:1) · cards 2 × 2 · facts 3 × 2 · context. |
| Terminal < 700 px | Band: image full-bleed 3:1 (130 px at 390), then name, line, button (full width). Cards: one column, **horizontal card** (thumbnail 136 × 76 left, text right) so two and a half cards show per screen. Facts 2 × 3. First screen at 390 × 844 shows ship image, name, line, primary button and the first card. |

## 4. Thumbnail system

**D-UX2: one tool, committed output.** `tools/thumbs.py` (new) with three steps; the finished files are committed in `web/thumbs/`
(like `web/engineering/*.jpg` today) so the Pages build and `tools/wos.py --out` need neither Blender nor a browser.

- `thumbs.py capture <site>`: headless Chrome through the existing CDP classes of `tools/web_check.py` (`Chrome`, `Page`,
  `page.screenshot` with a clip rectangle). Playwright is not installed here and is not added.
- `thumbs.py render`: runs the existing Blender preview scripts on the built assets (no new cameras).
- `thumbs.py pack`: Pillow (WebP support present) crops to ratio, resizes, encodes, enforces the byte limits and writes
  `web/thumbs/thumbs.json` (per image: source, method, command or URL, git revision, date, representation class).

Conventions:

| Rule | Value |
| --- | --- |
| Ratios | 16:9 for every card; 3:1 for the identity band only |
| Sizes | cards `-480.webp` (480 × 270) and `-960.webp` (960 × 540); band `-960.webp` (960 × 320) and `-1920.webp` (1920 × 640) |
| Format | WebP, quality 72–78, no alpha, sRGB; no JPEG fallback (the site already requires WebGL 2 browsers) |
| Byte limits | 480: ≤ 24 kB · 960: ≤ 60 kB · band 960: ≤ 40 kB · band 1920: ≤ 110 kB |
| Overview image budget | ≤ 150 kB transferred at 1× (band 960 + four 480 cards), ≤ 350 kB at 2× |
| Naming | `web/thumbs/<name>-<width>.webp`, lower case, names from the table below |
| Markup | `<img src="…-480.webp" srcset="…-480.webp 480w, …-960.webp 960w" sizes="(min-width:1100px) 25vw, (min-width:700px) 50vw, 136px" width="480" height="270" alt="…" loading="lazy" decoding="async">`; the band image is `loading="eager" fetchpriority="high"`, everything else lazy |
| Background | captures use the page's own dark background; no frames, shadows, text baked into the image |
| Never | a thumbnail starts a simulation, a canvas or an engine; no decorative images |

Images:

| Name | Used on | Source and method | Class label |
| --- | --- | --- | --- |
| `ship-side` (3:1) | Overview band | Blender, `presentation/preview.py --state COAST --quality review --views side`, cropped to the hull | Model render |
| `ship-3d` | Explore tab preview, Simulations/Engineering "Related" | Chrome capture of `viewer/#view=threequarter`, Standard style, toolbars hidden by an injected class | Model, viewer |
| `interior` | Overview card, `interior/` launcher | Blender, `presentation/entry_preview.py --look --views ind_habitat` (eye level in ring A; pick `stop_habitat` if it frames better) | Model render · the walk renders in real time |
| `exterior` | Overview card, `exterior/` launcher | Blender, `presentation/hero_preview.py --state COAST --views brow` (hull at close range); replace with a Godot EVA frame when `runtime-export` shots exist | Model render · training simulation |
| `sim-dust` | Overview card, `simulations/` | Chrome capture of the stage element on `engineering/dust/` (One grain, Nominal, side by side, impact frame) | Simulation |
| `sim-ignition` | `simulations/` | Chrome capture of the stage on `engineering/ignition/#autostart` at the overload event | Simulation |
| `sim-build` | `simulations/` | Chrome capture of `engineering/build/` at a mid step (re-capture of today's `build_preview.jpg` at 16:9) | Model, build order PROTOTYPE as the page states |
| `sim-compare` | `simulations/` | Chrome capture of `engineering/compare/` (re-capture of `compare_preview.jpg`) | Problem map |
| `sim-lab` | `simulations/` | Chrome capture of the Breakthrough Lab result panel with the default scenario | Illustrative |
| `engineering` | Overview card | Chrome capture of the generated elevation drawing (`story.elevation_svg`) in `engineering/#ship` | Schematic, generated |
| `vertex` | Engineering "Vertex drive" related card | crop of the existing `vertex_engine.jpg` (960 × 600 → 960 × 540) | Model render |

**Canonical versus illustrative.** Every thumbnail carries one small caption chip, bottom left, on a solid `--surface-0` plate
(never text on the bare image): `MODEL` (generated from the approved model), `SIM` (a simulation frame, dashed border as the
existing `cls-SIM`), `SCHEMATIC`, or `ILLUSTRATIVE` (dotted border as `cls-EXAMPLE`). The chip text comes from `thumbs.json`, read by
`wos.py` at bake time. Alt text describes the picture ("Side view of Wayfarer: engines left, radiators, habitat rings, bow shield right").

## 5. Icon system

**D-UX3: keep our own inline set, redraw on a 24 px grid; no library.** One Python dict `ICONS` in `tools/wos.py`, emitted by
`wos.icon(name)` as `<svg class="wos-i" viewBox="0 0 24 24" aria-hidden="true">`. CSS: `fill: none; stroke: currentColor;
stroke-width: 1.75; stroke-linecap: round; stroke-linejoin: round`. Sizes 20 px (bar, tabs, cards) and 24 px (phone bar, card title).

| Name | Meaning (only this) | Drawing | Used |
| --- | --- | --- | --- |
| `overview` | Overview | four tiles | bar |
| `ship` | the spacecraft as an object | spine, bow shield, ring ellipse, engine pair | bar (Explore), Ship 3D tab, viewer links |
| `interior` | inside the ship | rounded hatch with hand wheel on a deck line | Interior tab, card |
| `eva` | outside, spacewalk | helmet with visor and shoulders | Exterior tab, card |
| `sim` | interactive simulation | axes with a response curve | bar, cards, SIM chip |
| `engineering` | engineering record | drafting compass | bar, card |
| `status` | ship status | gauge arc with needle | bar |
| `records` | a document or lab record | sheet with folded corner | Lab records tab, record links |
| `propulsion` | drive | nozzle bell with three exhaust strokes | viewer Drive, Vertex tab, Ignition |
| `power` | electrical power | bolt | fact tiles, future Systems view |
| `thermal` | heat rejection | radiator panel with heat strokes | same |
| `habitat` | habitat rings | ring, hub, four spokes | fact tile "Gravity on the ring" |
| `navigation` | trajectory, mission | arc with origin dot and arrow | fact tile "Mission", "Cruise speed" |
| `alert` | advisory, open problem | triangle with mark | ADV chip, "Open problems" |
| `settings` | display settings | three sliders | viewer Appearance |
| `help` | help and system utility | circled question mark | utility button |
| `info`, `lock`, `arrow`, `external`, `play`, `close`, `chevron`, `orbit`, `zoom` | glyphs: explanation, unavailable, go, leaves the site, start, close, disclose, drag, zoom | | guidance strips, cards, hints |

Path data for the eight shell icons (the rest follow the same construction and are drawn in the implementation session):

```
overview     <rect x="3.5" y="3.5" width="7" height="7" rx="1"/><rect x="13.5" y="3.5" width="7" height="7" rx="1"/><rect x="3.5" y="13.5" width="7" height="7" rx="1"/><rect x="13.5" y="13.5" width="7" height="7" rx="1"/>
ship         <path d="M4 12h15.5M19.5 6.5v11M4 9v6M6.5 10.5v3"/><ellipse cx="13.5" cy="12" rx="1.8" ry="5"/>
interior     <rect x="6" y="3.5" width="12" height="17" rx="5"/><circle cx="12" cy="12" r="2.2"/><path d="M3.5 20.5h17"/>
eva          <circle cx="12" cy="9.5" r="6"/><rect x="8.5" y="7.5" width="7" height="4.5" rx="2"/><path d="M5 20.5c.6-3 2.2-4.6 4-5.2M19 20.5c-.6-3-2.2-4.6-4-5.2"/>
sim          <path d="M3.5 4v16.5H20.5"/><path d="M7 16c2.5 0 3-8 6-8s3 5 6.5 5"/>
engineering  <circle cx="12" cy="5" r="1.8"/><path d="M11.2 6.6L6 20.5M12.8 6.6l5.2 13.9M8.2 15.5h7.6"/>
status       <path d="M4.5 17.5a8.5 8.5 0 1 1 15 0"/><path d="M12 14.5l4-5.5"/><circle cx="12" cy="14.5" r="1"/>
help         <circle cx="12" cy="12" r="8.5"/><path d="M9.6 9.6a2.5 2.5 0 1 1 3.6 2.2c-.8.4-1.2 1-1.2 1.8M12 16.6v.2"/>
```

Rules: one meaning per icon, one icon per meaning; an icon never appears without a visible label except the `?` and state-chip
buttons, which carry `aria-label` and `title`; no filled icons, no colour of their own (state colour comes from the parent);
no icon as decoration in running text; new icons join the dict, are listed in `docs/WOS.md`, and are checked at review size 20 px.

## 6. Visual hierarchy

Six levels, each with one treatment; a page uses level 2 once.

| Level | What | Treatment |
| --- | --- | --- |
| 1 Location and purpose | module title, page H1, breadcrumb | H1 28 px/600 (22 px on a terminal), `--ink-strong`; one sentence in 16 px `--ink` |
| 2 Main action | one per page: Explore the ship, Start, Run | the only filled `--action` button on the page, 44 px high |
| 3 Supporting actions | cards, tabs, presets | outlined or surface controls; card titles 18 px/600 |
| 4 Context | one-line descriptions, guidance strip, captions | 15 px `--ink`; guidance on `--surface-1` with the `info` icon |
| 5 Detailed data | tables, parameters, levers, readouts | 13.5 px, tabular numerals, inside panels or disclosures |
| 6 Metadata and diagnostics | status chips, sources, release, build line, sizes | 12 px `--muted` or mono chips; never above level 3 content |

Type scale (existing tokens plus two): 12 · 13.5 · 15 · 18 · 22 · 28 px. Nothing under 12 px except mono chips at 11 px; hierarchy
comes from weight, space, grouping and imagery, not from shrinking.

Emphasised: the ship image, the H1, the single action button, card thumbnails and titles, fact values (22 px/600 numerals).
Demoted: the eyebrow (one per page, 12 px), kickers on cards (removed; the icon and the tab say the category), status chips on the
Overview (behind "Status and sources"), `source_ref` codes (Status and disclosures only), tech stack words ("Godot · WebGL 2",
"three.js": removed from cards, kept in the System section), the station label, section H2s in spaced capitals (become 15 px/600
sentence case; capitals stay for chips).

Colour: `--action` only for level 2; `--accent` for the current location (bar, tab) and the eyebrow; `--info`, `--warn`, `--bad` only
for status. Spacing: 24 px between blocks, 12 px inside a block, 8 px inside a control group. Copy rule: title ≤ 4 words, line ≤ 12
words, action ≤ 3 words starting with a verb; a paragraph over 40 words on an `app`, `overview` or `sim` page goes into a disclosure.

## 7. Guidance and progressive disclosure

### 7.1 Shared pattern: the guidance strip

`<aside class="wos-guide" data-guide="<id>">`: icon `info`, **What this shows** (one sentence), **Try this** (one action), a `More`
link to the Level 3 section, and a close button. Baked in the HTML (visible without JavaScript); `wos.js` hides strips whose id is in
`prefs.guides` and the System sheet's "Show the orientation again" clears that list. It sits in the layout (never an overlay, never
modal) and collapses to a 32 px `info` button that reopens it.

### 7.2 Per module

| Page | What this shows | Try this | Other guidance |
| --- | --- | --- | --- |
| Ship 3D | The whole ship, generated from the engineering model. | Click any part to see what it is. | Controls hint, bottom centre, fades after the first drag: `Drag to orbit · scroll to zoom · click a part` (touch: `Drag to orbit · pinch to zoom · tap a part`). Toolbars regrouped under three labels: **View** (camera), **Show as** (Standard, Subsystems, Engine, X-ray; "Engine holo" → "Engine", "Hybrid" → "X-ray", old names in `title`), **Panels** (Assemblies, Appearance, Drive, Engine parts, Fuel). The `Loading model…` status states the size. Visible workspace title chip top left: `Ship 3D · COAST`. Phone: camera row moves into the View group at the top (fixes the footer overlap); footer build line goes to the System sheet. |
| Interior | Walk ring A while the ring turns. | Press Start, then click the view to look around. | Launcher reduced to: thumbnail, one line, Start button with size, three control lines; the long controls text in `<details>Controls</details>`. |
| Exterior | A training spacewalk along the hull. | Press Start; your gas is finite. | Same launcher pattern; chip `Training simulation`; the HOLD note in a disclosure. |
| Dust | One grain of dust hitting the shield at test speed and at cruise speed. | Move **Impact speed** and watch the right panel. | Each preset group gets a one-line caption ("Speed presets: real impacts for comparison"); the result table gains `Why this matters` → the open problem in `engineering/#problems`. Phone: readout overlay becomes a row under the stage. |
| Ignition | The drive switched on, as budgeted and with measured physics. | Press play, then open **Your design** and pull one lever. | Lever `what` text already exists (`lw-*`); show it under each lever, not as meta. Result links to the problem record. |
| Build sequence | How the ship would be assembled, step by step. | Press Next or drag the step slider. | |
| Compare | What the design has against what it needs. | Pick a problem in the list. | |
| Breakthrough Lab | Which assumed breakthroughs would close the design. | Switch one breakthrough on. | chip `Illustrative` on scenario output |
| Engineering index | Goal, constraints, the ship today and the open problems. | Start with Open problems. | "On this page" list |
| Status | The state the model is built in; not live telemetry. | Open an advisory to read its record. | |

**Unavailable experience** (no `play` package in the build, or WebGL 2 missing): the launcher shows the thumbnail and a panel
`Not available in this build` / `Your browser cannot run this (WebGL 2 needed)` with two actions: `Explore the ship in 3D` and
`See the engineering`. The Overview card says `Not in this build` in its availability row. No dead, greyed entries.

### 7.3 First-visit orientation (optional, non-blocking)

On the Overview only, a dismissible strip between the band and the cards, not a dialog and not focus-trapping:
`New here? Start with the ship in 3D, then walk inside. Everything is a simulation of a fictional design.` · `Got it`.
Dismissal writes `prefs.oriented = 1` in the existing `wos.v1` key (no new key); without JavaScript or storage it simply stays, 40 px
high. It never reappears after dismissal unless reset from the System sheet. No tour, no popups, no coach marks.

### 7.4 L1 / L2 / L3 on Engineering and simulation pages

Levels are positions on the page, never modes; every level has an anchor and direct links keep working.

- **L1 Discover** (first screen): H1 in plain words, one sentence, one visual, the guidance strip. Engineering index: H1 becomes
  `Engineering` with the line `Can a crewed fusion ship reach 0.016 c and come back?`; "0.016 c and back" stays as the eyebrow.
- **L2 Explore**: the diagram, simulation or model with its presets; captions of one line.
- **L3 Engineering**: parameters, constraints, assumptions, sources, open problems, in `<details class="wos-l3" open>` on a
  workstation and closed on a terminal for the long tables only (`How the simulation works`, `The numbers`, source tables). Section
  anchors open their `<details>` on navigation (`wos.js`, 6 lines: on `hashchange`, open the closest `details`).

`story.py page()` gains an optional `intro` argument (the L1 line and the guidance strip) so all generated pages share it.

## 8. Wayfinding

- **Where am I**: the bar marks the module, the sub-row marks the tab. One breadcrumb line under the sub-row on `record` pages only:
  `Engineering › Lab records › Dust impacts` (module name first, never "Wayfarer /"; the vessel mark is the way home). `app` and `sim`
  pages show a title chip in the workspace instead (`Ship 3D · COAST`, `Dust · simulation`).
- **What am I looking at**: every page has a visible H1 equal to its tab label (the viewer's `sr-only` H1 stays, the title chip shows it).
  `<title>` pattern: `<Page> · <Module> · G.U. Wayfarer 001`.
- **What can I do**: the guidance strip and the single level 2 action.
- **Related** (end of every page, `<nav class="wos-related" aria-label="Related">`, three thumbnail-less rows or small cards):
  Ship 3D → Walk inside · Vertex drive · Open problems. Interior ↔ Exterior ↔ Ship 3D. Dust → Problem record · Ignition · Brow shield
  in the viewer (`viewer/#…focus`). Ignition → Vertex drive · Dust · Drive in the viewer. Engineering pages → the simulation that
  demonstrates them. Status → Open problems · Engineering. Data: `related` lists in the registry sub items.
- **How to return**: vessel mark → Overview (unchanged, checked by `web_check`); breadcrumb; browser back always works (multi-page).
- Active states: `aria-current="page"` on bar link and tab; 2 px `--accent` underline (top border on the phone bar); focus ring
  `--focus` 2 px on everything. Depth is at most module → tab → page.

## 9. Implementation

### 9.1 Order (each step leaves a working site)

| # | Step | Files |
| --- | --- | --- |
| 1 | Registry and shell: five modules, `sub`, aliases, 24 px icons, `wos.icon()`, sub-row, `?` System sheet, station label out of the bar, `facts()` renderer and `<!--wos:facts-->`, `<!--wos:sub-->` handled inside `bar()` | `tools/wos.py`, `web/site.css` (shell block), `web/wos.js` (aliases, guides, orientation, hash-opens-details, tab scroll) |
| 2 | Simulations home `simulations/index.html` (five cards from the registry) and `engineering/#simulations` kept as an anchor that now holds one line linking there | `tools/story.py` (`main_page`, new `sims_page`), registry |
| 3 | Thumbnails: `tools/thumbs.py`, captures and renders, `web/thumbs/*.webp`, `thumbs.json` | new tool, `web/thumbs/`, `tools/web_export.py` (copy, byte checks) |
| 4 | Overview: new markup, copy and CSS; remove `.wos-ov-*` grid rules and the embedded state table | `web/index.html`, `web/site.css` |
| 5 | Status page: three sections, System section takes profiles, release review, shortcuts, station labels | `web/status/index.html` |
| 6 | Guidance: `wos-guide` strips and L1 intros on viewer, launchers, simulations, Engineering; viewer toolbar groups and hint; unavailable panel | `web/viewer/index.html`, `viewer.css`, `viewer.js` (hint fade, labels only), `web/interior/`, `web/exterior/`, `tools/story.py` (`page()`, `dust_page`, `ignition_page`, `build_page`, `compare_page`), `tools/story_lab.py` |
| 7 | Breadcrumb, related links, titles | `tools/wos.py`, `tools/story.py page()` |
| 8 | Checks and docs | `tools/web_check.py`, `tools/web_export.py`, `tests/test_wos.py`, `docs/WOS.md` (§1 shell, §2 modules, new §7 UX rules: icons, thumbnails, hierarchy, guidance), `web/README.md`, `CLAUDE.md`/`AGENTS.md` WOS paragraph (module names), TODO O |

Preview loop per step: `python3 tools/wos.py --out runs/wos-preview`, then the screenshot matrix (`work/…/matrix.js`) and `axe.js`.

### 9.2 Selectors and contracts that must survive

- `#go-interior`, `#go-exterior`, `#go-viewer`, `#go-engineering`, `#go-status`: all kept as visible links on the Overview
  (`#go-viewer` is the band button; `web_check` clicks its centre, so it must not be covered by the orientation strip).
- `.wos-bar .mark` returns to the Overview; `#release` still starts with `Release 2`; `#interior-meta`, `#exterior-meta`,
  `#viewer-meta` either kept as the availability spans or removed together with their script lines.
- `data-wos-key` stays on bar links; `web_check` does not read the letters (verified by search), tests do not either.
- Viewer ids (`#view`, `#panel-toggle`, `[data-view]`, `[data-style]`, `#focusbar`, …) and `data-style` values are unchanged; only
  visible labels and grouping change. Hash bookmarks unchanged.
- `web_export.verify_site`: one ship line per page, no unreplaced marker: the two new markers must be in `MARK`.

### 9.3 Risks

| Risk | Handling |
| --- | --- |
| `web_check` part A requires the start page to request exactly `index.html, release.json, site.css, wos.js` and under 150 kB in total | Change the check: allow `thumbs/*.webp`; assert documents/CSS/JS < 150 kB and images ≤ 150 kB at 1× separately; still no canvas, engine or library. This is the one check that must be edited deliberately |
| Start budget: 74.1 of 76 kB used today | The Overview drops the state table and advisory list (about −9 kB) and the old `.wos-ov` grid (about −2.5 kB); new markup, facts, icons and CSS are estimated at +9 kB. Measure after step 4; if over, trim the lunar scene rules (28 kB reserve named in the architecture) before asking for a higher budget |
| Bar grows on every page (sub-row, System sheet) | about +1.2 kB per page; simulation and record pages have no byte budget but report it |
| Sub-row takes 36 px from `app` and `sim` workspaces | the row is part of the flex column, so canvases shrink, not overlap; viewer pick tests use the canvas rectangle already; focus mode hides it; on a short landscape phone it merges into the left rail's module (tabs shown as a strip only on the current module) |
| Removing the 1366 × 768 no-scroll lock contradicts `docs/WOS.md` §3 | The layout still fits that viewport; the doc rule changes to "fits without scroll in the default state" |
| Thumbnails drift from the model | `thumbs.json` records the revision; `web_export` warns (not fails) when a thumbnail is older than the newest accepted baseline; regeneration is a named step, not part of every build |
| Blender stills for Interior/Exterior look better than the real-time walk | caption chip `MODEL` plus the launcher line "the walk renders in real time"; swap to Godot frames when available |
| Renamed modules in docs, TODO, CLAUDE.md, the Godot HUD vocabulary | one search for "Records", "Aboard", "System" in `docs/`, `web/`, `tools/`; Godot is not touched (package would go STALE) |
| Label changes in the viewer ("Hybrid" → "X-ray") confuse returning users | old name kept in `title` and as the hash value |
| Scope for one session | steps 1–5 are the minimum reviewable result (priorities 1–3 of the brief); 6–7 can follow in the same branch |

### 9.4 Owner points (defaults chosen, change on request)

1. Status as a primary module with System as utility (chosen) versus Status wholly in utility with four primary modules.
2. The one new route `simulations/`.
3. Committed WebP thumbnails in `web/thumbs/` (about 0.7 MB in Git) versus generated in the web build.
4. Viewer style labels "Engine" and "X-ray".

## 10. Validation

Screenshot matrix after the change (same seven viewports as `docs/WOS.md` §5), saved beside `after/` as `ux/`:
`overview_*` (all seven), `explore-ship_{laptop,phone-port}`, `interior_{laptop,phone-port}`, `simulations_{laptop,phone-port}`,
`dust_{laptop,phone-port}`, `engineering_{laptop,tablet-port}`, `status_laptop`, plus `overview_laptop_no-play` (unavailable state)
and a before/after pair at 1366 × 768. axe-core WCAG 2.1 A/AA on Overview, Simulations, Dust, Explore/Interior and Status at 1366 × 768
and 390 × 844; keyboard pass (Tab order: skip link, mark, modules, tabs, utility, workspace).

| Scenario | The reviewer checks | Pass when |
| --- | --- | --- |
| A New visitor | Open `/` cold at 1366 × 768 and 390 × 844; read nothing but the first screen for five seconds | Can say: it is a fictional spacecraft, here is what it looks like, the first thing to do is Explore the ship. No status code is visible above the facts strip. The context block states "not a real ship". |
| B Curious explorer | From `/`: 3D ship, then Interior, then Exterior, without the Overview | One click to the 3D ship; Interior and Exterior each one click from there via tabs; the controls hint is seen before the first drag; a part can be picked; the unavailable state names an alternative. |
| C Simulation user | Bar → Simulations → Dust; change one parameter; find what the result means | Simulations has its own page with five pictured entries and stays marked in the bar; the strip states what Dust shows and what to try; a preset caption explains the change; the result links to the problem record. Same on a phone with no control hidden. |
| D Technical visitor | Find cruise speed with its source; the open problems; the Vertex record; the release review | Each within two clicks from any page (Status → Ship state; Engineering → Open problems; Engineering → Vertex drive; `?` → System). `g` shortcuts including the old letters work. Sources and statuses are unchanged in content. |
| E Mobile visitor | 390 × 844 and 844 × 390, touch | Five labelled tabs, no clipped label; thumbnails on every card; first screen shows the ship and the main action; tabs row scrolls; every function of the desktop page reachable; targets ≥ 44 px; no horizontal page scroll. |

Automated, unchanged in kind: `tests/test_wos.py` (plus: every fact tile item exists in `wos.json` with status and source; every
registry path resolves to one module and at most one tab), `web_export.verify_site`, `web_check --part main` with the edited start
check, thumbnail byte limits. Reported with the screenshots: start-page bytes before and after, Overview image bytes at 1× and 2×,
visible word count of the Overview before and after.
