<!-- lab entry -->
| Lab entry | |
| --- | --- |
| Kind | Variant (with study and problem map) |
| Status | ACTIVE (research, not canon; awaiting owner review) |
| Question | Does a hybrid ionisation-magnetic shield (HIMS) protect the braking Vertex ship better than passive screens, and what does the integrated four-engine ship look like? |
| Model base | 250a756 + RON (lab/studies/vertex-compact-engine/vertex-ron) + AMPN B today (lab/studies/vertex-compact-engine/vertex-ampn); production geometry, data and canon unchanged |
| Branch | claude/project-thread-1p6mtu, 2026-11-22 |
| Open owner questions | Q-HIMS-1 drop HIMS-C as a protection path and keep the passive screen (recommended); Q-HIMS-2 adopt HIMS-B (2-3 screens) where mast length matters; Q-HIMS-3 move the problem register to lab/problems/ on approval; Q-AMPN-1..4 still open |
| Review | REVIEW_HIMS.blend (local, not in Git); renders/; PROBLEMS.md |

# vertex-hims: notes

**Function.** Protect the braking ship (engines first, dust from ahead) at the stern and the engine faces, and show the whole Vertex ship
with its services: feeds, injector, cooling, armour, maintenance, spares and the burn's keep-out zones.

**Fixed constraints.** AMPN B today (R 15 m, kappa 2.28, D 1,910 m, S 767 m); canon mission (0.016 c, four burns); dust environment and
damage rules of lab/studies/dust-impacts (read-only); 0.1 expected breaches per area as the target; NOMINAL and JUSTIFIED both run.

**Unknowns (OPEN).** Impact physics above 100 km/s (cone angle, ionised share, wall rule: EXTRAPOLATED); collective behaviour of a dense
debris plasma in a field (beta limit only, no plasma model); screen hole growth under repeated hits.

**Design freedom.** Stand-offs, number and spacing of screens, field strength and bore of a deflector, mast and frame. All PROTOTYPE.

## Claims by class

| Claim | Class |
| --- | --- |
| Isolated fully stripped silicate ions (rigidity 0.1 T m) turn in >= 0.01 T over 20 m; singly charged ions need >= 0.3 T | Modeled (Boris test particles) |
| Grains at 4,800 km/s are fully vaporised and 70-90 % ionised by a thin screen | Extrapolated |
| A dense debris cloud is deflected as a whole | Unresolved (beta limit used as a cap; no plasma model) |
| Vertex ring fields protect the stern (A) | Rejected: 3.3e-6 T at the stern path, Si14+ gyroradius 30 km |
| Laser pre-ionisation of incoming dust | Rejected: 1,185 TW (NOMINAL) |
| A screen ahead of the engine faces | Rejected: in the burn view or the exhaust (ENG-014); armour only |
| Distributed screens (B) shorten the stand-off for little mass | Modeled (NOMINAL 64 to 32 m for +13 t) |
| Passive stern screen is the lightest closing option in both cases | Modeled |

## Results (stern disc 6,362 m2; results/hims.json, results/integration.md)

| Option | NOMINAL stand-off, stack, departure | JUSTIFIED stand-off, stack, departure |
| --- | --- | --- |
| Passive screen (AMPN) | 64 m, 41 t, 10,987 t | 330 m, 100 t, 15,805 t |
| A: screen + ring field | same as passive | same as passive |
| B: 2 screens | 45 m, 47 t, 11,006 t | 276 m, 125 t, 15,879 t |
| B: 3 screens | 32 m, 54 t, 11,026 t | 231 m, 150 t, 15,954 t |
| C: 0.1 T deflector | 58 m, 219 t, 11,518 t | 181 m, 274 t, 16,324 t |
| C: 0.3 T deflector | 38 m, 543 t, 12,487 t | 181 m, 598 t, 17,295 t |
| C: 1 T deflector | 28 m, 1,816 t, 16,292 t | 181 m, 1,872 t, 21,101 t |

The field is easy for single ions and expensive as a structure: a 0.3 T cos-theta dipole over the 50 m bore needs 95 MA-turns,
stores 7.3 GJ and weighs 503 t (369 t of it conductor at Je 1.53e8 A/m2). Under JUSTIFIED the 30 % neutral share caps every deflector at the same 181 m stand-off.
C2 (a boom bus deflector) costs 1,859 t against 1,580 t of boom-duct armour: rejected.

## Assessment

1. Passive-only (AMPN): lightest in both cases. It stays the working answer.
2. HIMS-B (distributed screens): a genuine, cheap trade of mast length for screen mass (+19 to +149 t departure). Worth keeping where the
   stand-off is awkward (the stern mast must clear the field lines and fold for the flip).
3. HIMS-C (ionisation + deflector): mass-negative by 0.5-5 kt departure and rests on two unproven links (ionised share, collective
   deflection). Kept as a labelled prototype in the review file, not as a design path.
4. HIMS-A and laser pre-ionisation: rejected on physics.
The dominant protection costs are elsewhere: the engine-face armour and, under JUSTIFIED, the boom ducts (ENG-014, ENG-015).

## Roadmap (one item per session, each with a visible result)

1. Boom-duct redundancy criterion (ENG-015): the largest JUSTIFIED mass; answer it before any new shield idea.
2. Plasma-coupled pulse and detachment model (ENG-002, ENG-003): fixes eps_c and eta, the two numbers the magnet mass rests on.
3. Engine-face armour shape study at the nose (ENG-014, ENG-005): edge-on tiles and cassettes, in the Blender model.
4. Literature bound on cluster-ion and microparticle impacts at 100-1,000 km/s (ENG-017): narrows NOMINAL vs JUSTIFIED.
5. Hybrid PIC of one debris plasmoid entering 0.3 T (ENG-011): only if a constrained stand-off appears that screens cannot meet.
6. Mission-level trade (ENG-001, owner): nothing here brings the ship within 2.2x of 4,426 t.

## Files (standard library unless noted; run from the project root)

- `hims.py`: stage model (design grain, laser stage, screens, erosion, Boris ion paths, deflector mass, beta limit, boom bus); writes
  results/hims.json, hims.log, trajectories.json.
- `integrate.py`: departure mass of each option through the AMPN ship model; writes results/integration.json and integration.md.
- `problems.py`: the Engineering Problems Register (data in the file); writes results/problems.json and PROBLEMS.md.
- `blender_hims.py` (Blender): REVIEW_HIMS.blend and renders/ (see its docstring for the collections).
