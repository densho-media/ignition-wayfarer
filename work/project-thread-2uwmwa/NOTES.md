# UI devices: the site as crew hardware (Phase 0)

Owner request 2026-11-20: desktop and mobile layouts act like real G.U. WAYFARER 001 hardware; display types follow ship
activities (personal vs stational). Concept artifact: https://claude.ai/artifact/BHKkptGmhepf4eYFRJHD94 (concept.html here).

- Function: presentation only. No geometry, material, calculation or lore change.
- Fixed: WEB-005 tokens (tools/web_identity.py), docs/WEB_IDENTITY.md rules (no glow/glass/circuitry), 7:1 contrast, start page
  loads only index.html + site.css + release.json, docs/WEB_GRAPHICS.md budgets.
- Families (PROTOTYPE): PERSONAL crew cuff (left forearm, docs/CHARACTERS.md), service slate, EVA suit display (docs/EVA.md);
  STATIONAL OPS console (RA2 sector 2, Ops_1-3), engineering workstation, burn-go console.
- Rule proposed: the activity picks the frame in the experiences; screen size picks the default for site pages.
- Phases: 0 concept · 1 site shell (start, launchers, status) · 2 Engineering + Explore Ship chrome · 3 Godot HUDs · 4 Drive canon.
- Open owner questions: families right? activity rule? go for Phase 1?
