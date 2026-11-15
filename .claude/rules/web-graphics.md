---
paths:
  - "web/**"
  - "godot/**"
  - "src/wayfarer/export/**"
  - "src/wayfarer/look.py"
  - "src/wayfarer/fractal_shield.py"
  - "src/wayfarer/presentation/**"
  - "src/wayfarer/detail/**"
  - "data/materials/**"
  - "data/detail/**"
  - "shots/**"
  - "tools/web_*.py"
  - "tools/runtime_export.py"
  - ".github/workflows/**"
  - "docs/WEB_GRAPHICS.md"
---

# Web graphics work

AGENTS.md "Web Graphics Engineering" holds the principles and `docs/WEB_GRAPHICS.md` the standard; this is the step list,
not a copy of either. TODO section W is the tracker.

1. **Experience.** Name which experience the change affects: the engineering viewer (Explore Ship and the Engineering
   3-D pages), the interior walk, the exterior EVA, or several.
2. **Standard and state.** Read TODO W and the relevant section of `docs/WEB_GRAPHICS.md` (renderer limits §3, budgets
   §9.4). Continue from the last accepted GFX task; reuse what §2 and §11 list as built.
3. **Engineering identity.** Leave engineering geometry, clearances, routes, colliders, mechanisms, component IDs and
   manifest metadata unchanged; generate any rendering representation from the saved assets (§6.1).
4. **Budget.** Classify the change as a performance improvement, a visual-quality improvement or both, and state the
   visual gain and the expected cost (frame time, memory, download, complexity) against that experience's budget. A
   visual improvement need not raise FPS; it needs review, documentation and a cost within the budget.
5. **Browser.** Confirm the technique exists in Godot Compatibility / WebGL 2 or three.js 0.170.0 in the browser, not
   only in Blender or native Forward+ (§3); note Pages hosting limits.
6. **Reuse.** Use PMDS appearances, the WEB-005 identity tokens, the existing look data, shaders and mesh sharing;
   add no parallel material catalogue, framework or CI service.
7. **Validate.** Run the checks the change selects (`workflow.py checks`, `web_check.py` parts, `runtime-check`) and
   compare before/after screenshots of the affected views; check picking, selection, input and touch where touched.
8. **Measure.** For a significant graphics or performance change, record baseline and result on the same view and
   machine with the evidence class (HW, EMU, SW) in `references/evidence/gfx_<task>.json`, reporting performance and
   visual-quality results separately. SW numbers never stand for real-GPU performance. Cosmetic edits need no benchmark.
9. **Record.** When a GFX task is done, update `docs/WEB_GRAPHICS.md` (§2, §11, §12) and remove or narrow its TODO W
   entry; add a justified new opportunity to TODO W instead of widening the current task.
