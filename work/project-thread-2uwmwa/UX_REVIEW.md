# WOS navigation and first visit: usability review (2026-11-21)

Site: full build `runs/wos-ux/site` (no play package). Viewports: ultrawide 2560 × 1080, desktop 1920 × 1080, laptop 1366 × 768,
tablet 1180 × 820 and 820 × 1180, phone 390 × 844 and 844 × 390. Evidence class SW (software rendering, cloud container).

## Scenarios

| Scenario | Path walked | Result | Remaining friction |
| --- | --- | --- | --- |
| A. New visitor | Overview: band says "IGNITION · fictional spacecraft", the name, one line, a real side view of the ship, one button "Explore the ship" and "What is this?"; the orientation strip suggests 3D first, then inside | What it is, what can be done and that it is fictional are answered above the fold on every viewport except laptop, where the cards start just below it | "Fictional" and "evolving" are stated twice (eyebrow and About); kept, because the band is all some visitors read |
| B. Curious explorer | Explore the ship → Ship 3D (controls hint until the first touch) → tab row Interior → "Walk inside" launch page with picture and "Try this" → Exterior tab | Ship, inside and outside are one module with three tabs; each launch page offers the other two | The walk and EVA need the play package; this build says "Not in this build" on the cards and launch pages |
| C. Simulation user | Simulations → cards with frames of each simulation, one line on what it shows → Dust: breadcrumb "Simulations › Dust", guide strip "what this shows / try this", the levers | Finding and starting are one click from anywhere; the guide strip says what to change and what to watch | Presets are not yet labelled by what they demonstrate; result-to-record links are TODO O "WOS-UX follow-ups" |
| D. Technical visitor | Engineering tab row: Summary, Baseline, Weakest links, Ship evolution, Vertex drive, Open problems, Lab records; Overview facts → "Status and sources" table with class, status and source reference; Status → ship state, advisories, System | Every number keeps its status and source one click away; nothing technical was removed | Old letter shortcuts (s, r, a, y) still work alongside the new ones |
| E. Mobile visitor | Phone portrait: bottom bar with five icons and words, the tab row scrolls sideways, cards become horizontal rows with a picture, facts in two columns | No horizontal overflow, the ship line in view and all five modules reachable on all 49 page views; 44 px shell targets with touch | The viewer's toolbars still take two rows at the top on a phone (WOS-3 docks them) |

## Automated checks

- Viewport matrix: 7 pages × 7 viewports, no overflow, bar in view, 5/5 modules, the same controls on every profile, no small shell
  targets, no page errors.
- axe-core WCAG 2.1 A/AA at 1366 × 768 and 390 × 844 on Overview, Simulations, Status, Interior, Exterior, Engineering, Dust,
  Ignition and Ship 3D: two findings fixed (breadcrumb links now underlined; the Dust readouts are focusable).
- `web_export` budgets: start code 88.8 kB raw (21.4 kB gzipped), start pictures 122 kB at the widest size each srcset picks.
- `web_check --part main` against the full build (see the report).
