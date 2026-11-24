<!-- lab entry -->
| Lab entry | |
| --- | --- |
| Kind | Variant (compact cluster C1-C4, with study and problem map) |
| Status | ACTIVE (research, not canon; awaiting owner review) |
| Question | How far can the compact integrated Wayfarer (aft four-engine cluster, moved at most a few tens of metres) be pushed while staying physically informed and honest about what does not close? |
| Model base | Approved ship built from this branch on 2026-11-23 (geometry diff 0 to the baseline); RON/AMPN/HIMS engine and dust models read-only |
| Branch | claude/project-thread-1p6mtu, 2026-11-23 |
| Open owner questions | Q-CMP-1 adopt C4 as the compact working direction; Q-CMP-2 allow the blade aft station (PROTOTYPE) to move forward or cant; Q-CMP-3 next session: the absorbed-fraction problem ENG-030 (plasma model) or the cluster shadow disc ENG-036 |
| Review | REVIEW_COMPACT.blend (local, not in Git); renders/; PROBLEMS.md |

# vertex-compact: notes

**Direction (owner 2026-11-23).** The compact ship and its aft cluster are the main path. The remote-engine studies (MPN, RON, AMPN,
HIMS) are kept as non-canonical research and comparison; nothing here reopens them.

**Function.** Four Vertex engines in one aft cluster (pitch radius 24 m, cant 2 deg), integrated with the thrust ring, the run-tank feeds
and the radiator blades; protection of the aft ship in braking (engines first).

**Fixed constraints.** Ship silhouette and layout as built (tank aft dome x -100 m, spine r 6.5 m, three blades at 30/150/270 deg from
x -133 m, r 6.5-37 m); canon mission and jet power; dust environment and rules of lab/studies/dust-impacts; NOMINAL and JUSTIFIED both run.

**Design freedom used.** Cluster position (0, 30, 36 m aft), shield standoff (6 or 12 m), loop section (round cryostat or ribbon), field
multiple (x1-x4), shadow-shield size, screens, armour. All PROTOTYPE.

## Variants and results (results/compact.md; quick run, 48 directions x 4 species)

| | C1 as built | C2 30 m aft | C3 +6 m nozzle, ribbons, big shields | C4 C3 + braking package |
| --- | --- | --- | --- | --- |
| Burn x | -153 m | -183 m | -189 m | -189 m |
| Engine piped heat / 10.8 GW budget | 16,295 x | 16,393 x | 10,798 x | 10,844 x |
| Direct burn on the ship / 0.1 GW | 12,547 x | 760 x | 361 x | 139 x |
| Axial efficiency | 0.31 | 0.31 | 0.51 | 0.51 |
| Winding fluence / limit | 7,260 x | 7,260 x | 7,260 x | 7,260 x |
| Braking dust protection (NOMINAL / JUSTIFIED) | 444 / 780 t | 444 / 780 t | 480 / 847 t | 409 / 935 t |
| Departure if the heat closed | 142 kt | 145 kt | 48.7 kt | 52.3 kt |

What works: moving the cluster 30 m aft takes the spine and tank dome out of the burn (direct burn on the ship /16); the stronger field and
the 12 m shield standoff raise efficiency to 0.51 and cut piped heat by a third; three compact screens in a 15 m zone close the tank dome
for NOMINAL dust at 5.5 t; engine faces, hub and blade edges close with 8-10 cm armour.
What does not: the engine hardware still absorbs about 10,000 times the heat the canon radiators reject (ENG-030); the windings take
7,000 times their fluence and no armour thickness fixes it (ENG-033); the blade aft ends still see the burns (ENG-032); efficiency 0.51
makes the mass ratio grow (ENG-031).

## Recommendation

Adopt C4 as the compact working direction: cluster 36 m aft on a longer thrust truss, burn 12 m aft of enlarged shadow shields, ribbon
loops at a stronger field, compact screens ahead of the tank dome and armour on everything that leads in braking. It keeps the
silhouette and is the best compact point found, by a wide margin on ship exposure and efficiency. It does not close: the absorbed
fraction (ENG-030) is the problem that decides the compact engine, and the next propulsion session should go there.

## Files (standard library unless noted; run from the project root)

- `compact.py`: variant evaluation (ron.py engine physics, ship exposure against the measured ship, ripple, fluence, dust, mass);
  writes results/compact.json, compact.log, compact.md. `--quick` for 48 directions (used here), default 160.
- `problems.py`: compact register entries ENG-030..038 plus the remote branch as part 2; writes PROBLEMS.md and results/problems_compact.json.
- `blender_compact.py` (Blender): REVIEW_COMPACT.blend and renders/ (whole ship, aft cluster, braking-facing, side, top, rear, component
  breakdown, variants, aft close-ups per variant, problems overlays); `ONLY=<views>` renders a subset.
- `make_sheet.py` (Pillow): renders/compact_comparison_sheet.png, the one-page variant comparison.
