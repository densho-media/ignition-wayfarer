# Website visual identity (WEB-005)

The look of the public site: the start page, the launchers, the status page, the Engineering section (including Engineering 2.0:
Baseline, Weakest Links, Breakthrough Lab, Ship Evolution, and the 3D comparison) and the chrome of Explore Ship. The Godot shell
(`web/play/shell.html`) and the game scenes keep their own look. Presentation only: nothing here changes geometry, a material, a
calculation, a research record or lore.

**Principle.** Dark, restrained foundations; precise luminous accents; materially believable engineering colours. Light and colour
mark state, energy and function. No neon, glowing borders, glass or decorative circuitry.

## One source

`tools/web_identity.py` owns every colour value. It writes the generated block between the `<wf-identity>` markers of
`web/site.css` and `web/viewer/viewer.css`; all other CSS uses the tokens only. `python3 tools/web_identity.py` rewrites the
blocks, `--check` reports a stale one, and `web_export.verify_site` fails the site build while a block is stale. The generator
also gives `tools/story.py` and `tools/story_lab.py` the topic chips and material swatches.

## Four colour layers

They are kept apart on purpose. A component may carry more than one; the hierarchy is: **status** decides a chip's colour, the
**function** marks the card edge and its labelled chip, a **material** shows only in a swatch, and the **identity** colours
everything else.

| Layer | Tokens | Source | Used for |
| --- | --- | --- | --- |
| 1 UI identity | `--wf-*`, `--bg`, `--surface-0..3`, `--line*`, `--ink*`, `--muted`, `--accent*`, `--link`, `--action*`, `--focus`, `--selected` | `IDENTITY` in the generator | surfaces, text, navigation, buttons, focus and selection |
| 2 Engineering function | `--fn-<KEY>` (class `fn-<KEY>` sets `--fn`) | `src/wayfarer/functional_colors.py` PALETTE | the subsystem a topic, card, problem, weakest link or breakthrough is about |
| 2b M5 subsystem | `--sub-S01..S12` | `shots/m5_subsystems.toml` | legends that refer to the viewer's subsystem holograms |
| 3 Material | inline `--mat` on a swatch | `data/materials/appearances.toml` base colour | PMDS material codes (`.mat`) |
| 4 Status | `--good`, `--info`, `--warn`, `--bad` | `IDENTITY` | status chips (`.st-*`, `.bt-*`, `.tag`), errors |

### 1 · Identity: First Ignition

| Role | Token | Value |
| --- | --- | --- |
| Deep spacecraft charcoal | `--wf-charcoal`, `--surface-2` | `#1B2633` |
| Blue-white ignition | `--wf-ignition`, `--ink-strong`, `--focus` | `#D8EAFF` |
| Deuterium plasma pink | `--wf-plasma`, `--accent`, `--selected` | `#D99AC9` |
| Plasma violet | `--wf-violet`, `--accent-2` | `#8C83C5` |
| Radiator orange | `--wf-radiator`, `--action` | `#FF843C` |

Derived: page `--bg #0A0F15` (charcoal at 40 % lightness: deep space), reading sheet `--surface-0` (88 % opaque), panel
`--surface-1 #121A24`, selected `--surface-3 #243246`, hairlines `--line #2A3747` and `--line-strong #3B4B60`, text `--ink #DCE5EF`
(13.8:1 on a panel), secondary text `--muted #9AA9BA` (7.3:1), links `--link #E7B9DA` (10.1:1, underlined in running text). The
primary action is radiator orange with charcoal text (6.3:1). Full-strength accents appear only as small marks: the ignition rule
under a page title, eyebrows, the selected edge, the action button.

Status (on a panel): good `#7FD39B` 9.8:1, info `#8FC1F0` 9.2:1, warn `#E9B85A` 9.6:1, bad `#FF7F73` 7.1:1. Status never borrows a
function colour: an error is `--bad`, not the hot-radiator red, and PROTOTYPE is `--warn`, not the action orange. OPEN and LOCKED
chips also carry a ○ / ● glyph so state never depends on colour alone.

### 2 · Engineering functions

The registry values are Blender scene-linear viewport colours (`obj.color`). The site shows their **sRGB encoding**, the hue the
Blender viewport shows under the Standard view transform. Every mark carries its name (`.fnchip`): colour is never the only cue.

| Key | Site label | Registry label | Site colour |
| --- | --- | --- | --- |
| `STRUCTURE` | Structure | Primary structure and supports | `#C5C5C8` |
| `SHIELD` | Shielding | Shield and dust protection | `#E7C876` |
| `SENSORS_COMMS` | EYE and sensors | EYE, sensors and communications | `#59E7EF` |
| `HABITAT` | Habitat and crew | Habitat and crew transfer | `#86DA95` |
| `HYDROGEN` | Hydrogen | Hydrogen storage and feed | `#6999F6` |
| `DEUTERIUM` | Deuterium | Deuterium storage and feed | `#27C5BF` |
| `HELIUM3` | Helium-3 | Helium-3 storage and feed | `#C595F1` |
| `HOT_RADIATOR` | Hot radiators | Hot radiator circuit (1800 K drive) | `#EF6159` |
| `WARM_RADIATOR` | Warm radiators | Warm radiator circuit (440 K machinery) | `#FABC59` |
| `LOW_RADIATOR` | Low-temperature radiators | Low-temperature radiator circuit (300 K) | `#D4ECFD` |
| `MAIN_PROPULSION` | Fusion propulsion | Main propulsion | `#EF6FE2` |
| `RCS` | Manoeuvring | RCS and manoeuvring (incl. momentum storage) | `#FAF169` |
| `POWER` | Electrical power | Electrical power and storage | `#8E81D1` |
| `SERVICE` | Docking and service | Docking, EVA and service equipment | `#FAF5E2` |
| `SHIP` (site only) | Whole ship | a topic with no single subsystem: mass loop, mission, layout | `--wf-ignition` |

**Topics.** `TOPICS` in the generator files each engineering topic under one function:

| Function | Topics |
| --- | --- |
| Fusion propulsion | lab `fdp1`, `fiji-drive`, `fdp1-requirements`; P01, P03, P04; WL-001, WL-002, WL-004, WL-007, WL-009; BT-001, BT-003, BT-005 |
| Hot radiators | P07; WL-005; BT-004 |
| Warm radiators | lab `graded-thermal-blade`; P06 |
| Structure | P09; WL-006; BT-002, BT-007 |
| Shielding | P05, P11; WL-008 |
| Electrical power | P02; BT-006 |
| Hydrogen | P08 |
| Whole ship | lab `breakthrough-lab`, `four-burn-mission`, `redesign-layout`; P10; WL-003 |

Known overlaps, accepted because every mark is labelled: `POWER` and the identity violet are near twins (the identity violet is
never used as a category mark); `HELIUM3` and `POWER` share Blender's violet tag; `SERVICE` and `LOW_RADIATOR` are both near-white.

Charts keep their own categorical colours where the categories are not subsystems (problem-map elevation, envelope plots). Only a
mark that *is* a subsystem takes its function colour: the radiator wings in the Ship Evolution envelopes are now the hot-radiator
colour.

**M5 subsystems.** Explore Ship's Subsystems and Hybrid holograms use the twelve M5 overlay colours (`shots/m5_subsystems.toml`,
sRGB, set in three.js with `SRGBColorSpace`). They are a second, older registry that does not follow the functional palette (for
example S08 power is green, S10 propulsion brown). The site carries them as `--sub-*` and does not mix them with `--fn-*`. Aligning
the M5 overlay colours with the functional palette would change the Blender M5 shots and the viewer holograms: an owner decision.

### 3 · Materials

A PMDS material code on a page shows a swatch of its first appearance's base colour (linear → sRGB), a brushed gradient when the
appearance is metallic, and its level letter (A/B/C). A material without an appearance shows its parent's swatch, marked
"inherited" in the tooltip (for example `MAT-W-ADV01` shows `MAT-W`'s tungsten), or a hatched blank when neither has one. Appearance
colours are presentation (`docs/MATERIALS.md`): they are never brightened or tinted for the UI.

## The lunar scene

An original illustration drawn by the generator (no third-party imagery, so no licence or attribution is needed): a fixed layer
behind the page (`body::before`), never scrolling, never taking input, absent in print.

- **Composition.** The lunar horizon from low orbit along the bottom, Earth rising beyond it on the right, sparse stars, and the
  Sun off-screen upper left as a faint warm wash. The centre stays open for the content.
- **Physics it respects.** One light direction: the regolith, the crater walls (sunward inner walls in shadow) and the gibbous Earth
  are all lit from the upper left. The Moon has no atmosphere, no clouds and no glow halo; only Earth has a thin day-side limb.
  The terminator crosses the horizon right of centre; on the night side a faint earthshine and a cluster of warm station lights
  hint at lunar infrastructure. Stars are sparse and dim, as an exposure for a sunlit scene allows.
- **Layers.** Horizon (3200 × 360 SVG, sized by height so any width sees an unbroken horizon), Earth (SVG), two star tiles of
  prime sizes (397 and 653 px, so the repeat is not visible), a CSS radial gradient for the Sun, then `--bg`. All are data URIs in
  `site.css` (about 28 kB, 9.6 kB gzipped); the start page still loads only `index.html`, `site.css` and `release.json`.
- **Responsive.** Desktop: Earth just above the horizon at the right. Phone (≤ 640 px): a lower horizon and a small Earth in the
  upper right beside the title. Engineering and status pages use `body.scene-quiet`: a lower, dimmer scene, and the content sits on a
  reading sheet (`.story`, `--surface-0`) so long text never lies on the terrain. Explore Ship has no scene: its canvas is the scene.
- **Motion.** None. The scene is static; `prefers-reduced-motion` also removes UI transitions (`--dur: 0ms`).
- **Fallback.** If the images fail, every page is plain `--bg` with full contrast.

## Components

`.sitebar` (mark and site links on every page), `.ignite` (the title rule), `.choice` and `.card` (navigation cards; `.topic`
adds the function edge), `.fnchip` (function mark + name), `.mat` (material swatch + code + level), `.st-*` / `.bt-*` / `.tag`
(status), `.toc` and `.subnav` (pill navigation), `.panel`, `.figure`, `.scroll` (focusable, for wide tables), the compare
`.pairs` (each problem button carries its function dot), and the button family (`button` = action, `.secondary`).

## Accessibility

Text contrast is at least 7:1 for body and secondary text and 4.5:1 for every small label; focus is a 2 px ignition ring on every
focusable element; links in running text are underlined; status and function never rely on colour alone; wide tables scroll in
focusable regions; the compare problem buttons are tabs. axe-core 4.10 (WCAG 2 A and AA rules) reports no violations on the start,
Engineering, Engineering 2.0, compare, problem map, status and launcher pages.
