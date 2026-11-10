# Website visual identity (WEB-005): audit, plan, validation

Task branch `claude/project-thread-m2e2z9`, based on main 0fc013d (Engineering 2.0 squashed). The rules that stay are in
`docs/WEB_IDENTITY.md`; this file is the task record and is deleted on approval.

## Function, constraints, freedom

- Function: one coherent, readable identity for every site page, with engineering colours that mean the same thing as in Blender.
- Fixed: the start page loads only `index.html`, `site.css`, `release.json` (web_check A, 60 kB start budget); every path relative;
  the Lab checks (phone 390 px, no-JavaScript reading, `.filters[hidden]`, `.qa` and `form[data-evo]` min-width rules); viewer,
  compare and Godot behaviour unchanged; no geometry, physics, research, lore or Drive change.
- Freedom: palette derivation, layout, background art, components.

## Audit of main 0fc013d (before)

- One flat token set in `site.css` (`--bg #07090c`, `--panel #0c1015`, `--accent #e0a040` amber, `--sel #4fb3ff`, `--good`, `--bad`),
  copied by hand into `viewer.css`; `lab.css` and `story.css` added hard-coded fills (`#121820`, `#16202a`, `rgba(224,160,64,.35)`).
- `--accent` meant four things at once: brand, link, primary button, and the PROTOTYPE/PARKED/conditional status; `--sel` meant both
  "selected" and the WORKING/CALCULATED status.
- No relation between the site and the engineering colours: `functional_colors.py` (Blender) and the M5 subsystem colours (viewer
  holograms) were both unused by the pages, and the two registries disagree with each other.
- Backgrounds plain near-black; no shared header (start page footer links, engineering breadcrumbs, launchers "← Wayfarer" eyebrow).
- Typography: system UI stack, uppercase letter-spaced eyebrows and h2; sizes per page.
- Accessibility (axe-core 4.10, WCAG 2 A/AA): start page 6 contrast failures (kickers 2.8:1, meta 2.2:1 on the dimmed experience
  cards), SUPERSEDED chips 3.2:1, inline links distinguishable by colour only (1.6:1 against text) on 9 pages, a non-focusable
  scrolling table, compare tabs without `role="tab"`.
- Mobile: no horizontal overflow at 390 px on any page (kept). Performance: start page about 8 kB; no web fonts (kept).

## What changed

- `tools/web_identity.py`: the token source and the scene generator; writes the `<wf-identity>` blocks; `--check`; topic and
  material chips for the page generators. `web_export.verify_site` fails on a stale block.
- `web/site.css`: tokens only, the lunar scene, `.sitebar`, `.ignite`, cards, buttons, tables, `.fnchip`, `.topic`, `.mat`,
  underlined inline links. `web/viewer/viewer.css`: the shared identity tokens, focus ring, selected state.
- Start page: site bar, hero with the ignition rule, primary experience cards with an orange action line, Technical status added as
  a third secondary card. Launchers, status and play hub: site bar and ignition rule.
- Engineering (`story.py`, `story_lab.py`, `story.css`, `lab.css`, `compare.css`): reading sheet, pill navigation, function edges
  and labelled chips on lab cards, problems (register gets a System column), weakest links (cards and register), breakthrough cards
  and levers, compare problem tabs; PMDS swatches on breakthrough materials (now also visible in the card, not only in the details);
  statuses moved to the status layer; radiator wings in the evolution envelopes take the hot-radiator colour.

## Validation (this branch, local)

- `python3 tools/web_identity.py --check`: current.
- `node lab/studies/breakthrough-lab/tests/web_check.js <site>`: all checks passed (incl. 390 px, no JavaScript).
- `python3 lab/studies/breakthrough-lab/tests/test_breakthrough_lab.py`: 23 tests OK.
- axe-core 4.10 WCAG 2 A/AA on 11 pages: 0 violations (before: 7 pages with violations).
- Playwright at 1440 × 900, 820 × 1180, 390 × 844 and 2560 × 1080: no horizontal overflow, no page errors.
- Start page: still three requests; `site.css` 4 kB → about 44 kB raw, 10 kB gzipped (budget 60 kB raw with `index.html`).
- Not run locally: Explore Ship with its model and the Godot pages (no Blender build or Pages access in this container); the
  branch CI build and browser checks cover them.

## Decisions

- Name (owner, 2026-11-10): the ship is G.U. WAYFARER 001; G.U.C. is outdated. Site bar says "Wayfarer"; titles and specific text
  say "G.U. WAYFARER 001". The one stale "G.U.C." (lab/variants/fdp1/README.md) is corrected.

- Holograms (owner, 2026-11-10): the M5 overlay colours are aligned with functional_colors.py (shots/m5_subsystems.toml).

## Open owner questions

- Radiation shielding has no function of its own (shadow shield is MAIN_PROPULSION in Blender, SHIELD is the dust shield); the site
  files WL-008 and P05 under SHIELD.
- EVA suit and drone lettering read "G.U. WAYFARER 001" (was "G.U.C."); the marking objects are now `MARK_<KEY>_Suit_ShipName`
  and `MARK_Drone_ShipName_L/R`. `references/p1_eva_suit.json` still lists the old names and triangle counts until the next
  `workflow.py eva` run (needs the MPFB characters; CI builds the suit and drone from the generators).
