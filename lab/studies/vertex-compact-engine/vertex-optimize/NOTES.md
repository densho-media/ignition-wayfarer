<!-- lab entry -->
| Lab entry | |
| --- | --- |
| Kind | Study |
| Status | ACTIVE (research geometry behind the Fusion Engineering page; not canon) |
| Question | Burn moved about 4 m aft with stronger closure coils (owner-approved for research geometry 2026-11-24): what does it do to interception, thrust and heat, how does it combine with early extraction, and what do the coils cost? |
| Model base | main e1f50a1; compact C1 geometry (vertex-compact), R2-B source levers (vertex-source), ron.py test particles, vertex-extraction engine ledger |
| Branch | claude/project-thread-1p6mtu, 2026-11-24 |
| Open owner questions | Adopt the moved burn as a canon direction (not done); capture field above conductor practice (ENG-067); hydrogen coupling (ENG-072) |
| Review | `engineering/fusion-ignition/` Engine switch (Original / Research) in 11 stages; `REVIEW_OPTIMIZE.blend` and renders in the project files (fusion-optimize) |

# vertex-optimize: notes

Owner brief 2026-11-24 12:16Z, "Fusion Energy Extraction & Magnetic Topology Optimization". The research geometry is `mirror4|4`: the burn
4 m aft of its drawn point, the closure coils (C1, C2, L1) at four times their drawn ampere-turns, every ribbon re-aimed edge-on at the
moved burn. The approved engine is unchanged and stays the default and the comparison. Nothing here is canon.

- `optimize.py` (about 9 min on 4 cores): 19 geometries (burn 3-6 m aft x closure x3/x4/x6, graded closure, aft spacing x1.25, the drawn
  engine and ENG-065's best), capture current re-solved for each; species test particles in two plasma pictures (vacuum; diamagnetic cavity
  to R_b = (3 mu0 E / 2 pi B^2)^(1/3), then the vacuum field); X-ray/neutron pickup re-traced per geometry; every vertex-source lever through
  every geometry and picture with the momentum-consistent ledger; momentum balance per species.
- `coils.py`: four coil cases (drawn as built, drawn at capture, research at capture, research at the as-built current scale): stored
  energy, field at the winding, hoop tension (ring self-force mu0 I^2 (ln 8R/a - 3/4) / 4 pi plus the other coils' field), axial forces,
  conductor and hoop structure, cryostat leak, quench dump; the drawn research geometry (winding and cryostat radii, hoop bands),
  clearances, and the thermal blades re-aimed at the moved burn.
- `findings.py`: findings, ranking, combination and hydrogen blocks; the page import `lab/studies/fusion-ignition/imports/optimize.json`.
- `blender_optimize.py`: `REVIEW_OPTIMIZE.blend` (scenes ORIGINAL and OPTIMIZED from the same cameras; the WORK_OPT_* collections) and renders.

## Findings (2026-11-24)

- **burn.** Moving the burn aft is the lever: every geometry with the burn 4 m or more aft gives 0.73-1.04 MN, median 0.96 MN (four engines), against 0.44 MN as drawn. The closure factor (x3 to x6), grading and aft spacing mostly stay within the sampling error (+-6 points of debris hit share at 24 directions, about +-0.1 MN); none is a clear win over x4 at 4 m.
- **closure.** Stronger closure coils matter mainly through the capture current: with the burn 4 m aft the field that stops the pulse needs 286 GJ per engine instead of 3090 GJ as drawn, still 26x the 11 GJ the drawn coils carry.
- **cavity.** Plasma picture: letting the debris expand as an unmagnetised bubble to R_b = 1.5 m before the field acts changes the research result by -3 % in thrust; as drawn the bubble (0.6 m) reaches nothing. Both pictures bracket a coupled plasma (still not modelled).
- **pickup.** Re-tracing the X-ray and neutron pickup for the moved burn: the hardware covers 40 % of the sky instead of 72 %, so the design-target heat falls from 2,188x to 1,155x the radiator share (ENG-065 had kept the old pickup and reported 1,967x).
- **balance.** Momentum balance (D debris, units of one particle momentum): as drawn the ship gets 0.33, made of +0.65 from particles striking the shield and closure hardware and -0.32 through the field: a pusher plate, not a nozzle. With the burn 4 m aft the ship gets 0.79, +0.68 through the field and +0.10 by impact. Closure 0e+00.
- **combination.** Combined, not multiplied: research geometry plus 80 % early extraction gives 0.36 MN at 228x; multiplying the separate gains would claim 0.94 MN at 256x. Extraction moves energy into fast products that carry almost no momentum, so it removes the thrust the topology won; the two levers compete.
- **hydrogen.** Hydrogen reaction mass: inelastic mixing keeps the impulse and lowers the exhaust speed; only ideal elastic transfer (no physics yet) raises thrust, x3.81 with ten times the debris mass. Coupling OPEN.
- **coils.** Coils at the capture current, burn 4 m aft: 286 GJ per engine, 30 T at the windings (above the 20-25 T REBCO practice), 16.1 GN axial on one coil, a 19 min dump at 50 kA and 10 kV, or 3,579 t of copper to absorb it. The drawn research geometry (closure x4 at the as-built current) carries 27 GJ, 12.5 T, 41 t of hoop structure; it does not capture the pulse.
- **frontier.** Lowest heat anywhere: Early extraction: 80% of the product energy leaves the target (mirror4|5) 0.39 MN at 165x, Early extraction: 80% of the product energy leaves the target (mirror6|6) 0.40 MN at 170x
- **none.** No geometry, lever or combination closes: the lowest heat found is 164x the radiator share, and thrust stays near a twentieth of the 21.8 MN need.

## Problems (register ENG-066..072, on the page)

ENG-066 burn position sets most of the interception; ENG-067 capture field beyond today's conductors; ENG-068 closure-coil forces and
clearances; ENG-069 quench energy at capture; ENG-070 thermal blades aimed at the old burn; ENG-071 target flight 4 m longer; ENG-072
extraction and topology compete (and hydrogen coupling is OPEN). Failed configurations stay as results: the graded and spaced closures and
x6 currents give no clear gain; field strength alone was already rejected (ENG-065).

## Classes

SAMPLED (test particles, +-6 points of hit share at 24 directions), CALCULATED (ledger and coil formulas), PROTOTYPE (geometry choices),
OPEN (coupled plasma, hydrogen coupling, deposition and sputtering, quench design).
