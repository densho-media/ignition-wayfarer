# Vertex 1.8 Phase F: A+ ignition review (work, not canon)

| | |
| --- | --- |
| Kind | variant review (research prototype), noncanonical |
| Status | ACTIVE, awaiting owner review |
| Question | What do the A+ machinery and the nine-state ignition sequence look like on the real ship, what do they cost in the browser, and do the propulsion power and mass budgets close? |
| Model base | `710753c` (Vertex 1.8 study, A+ recommended); production geometry unchanged, four-engine architecture kept |
| Owner decisions applied (2026-11-16) | Phase F approved as a separate review file; SP-18A parked (no superconducting joints); flywheel optional and its mass still counted; physics problems stay OPEN; A+ is not a propulsion solution |

## Function

A+ adds the startup machinery of an adaptive Vertex engine without touching any winding: the L4 nozzle loop rides a carriage aft on
the cage longerons (4.8 m stroke, 480 s), trim coils and metrology heads align it to sub-millimetre, leadless HTS dynamos pump the coils
into persistent mode, and service petals (cryostat and armour shells only) open when the engine is cold and the field is down.

## Review path

- **Blender:** `REVIEW_VTX18.blend` (owner copy in the project files, `vertex-1-8/REVIEW_VTX18.blend`). Opens on the cinematic
  camera at frame 1; press play. 1,632 frames at 24 fps = 68 s, one timeline marker per state with its physical duration. The A+
  engines are in the pink `WORK_VTX18_A_PLUS_ENGINES` collection, today's engines `ENGINE_N1..N4` are hidden (not deleted), the optional
  flywheel is in the hidden `WORK_VTX18_OPTIONAL_FLYWHEEL`. The plumes and field effects are driver-driven: allow **Auto Run Python
  Scripts** when Blender asks (or Preferences > Save & Load), otherwise the effects stay at their rest values.
- **Browser:** artifact "Vertex A+ Ignition", the same timeline from `aplus_timeline.json`, seven diagnostic views (exterior, field,
  plasma, energy, thermal, control, sync) and a today/A+ toggle.

## Fixed constraints

Production geometry and data unchanged; nothing in `src/`, `tests/`, `tools/`, `godot/`, `web/` or CI reads this folder. Every moving part,
duration and readout derives from `[vertex_engine]`, `references/evidence/vertex_adaptive.json` and the operating point (`aplus.py`).

## The sequence (playback compressed per state, physical duration shown)

| # | State | Physical | Playback | What moves, what the AI shows |
| --- | --- | --- | --- | --- |
| 1 | DORMANT | indefinite | 7 s | rings stowed and locked, petals shut |
| 2 | MECHANICAL_PREPARATION | 8 min | 9 s | locks release, L4 carriage runs aft, festoon lines pay out, dynamo rotors spin up |
| 3 | DIGITAL_ALIGNMENT | 1 h | 7 s | metrology beams scan the loops, carriages trim from survey error to tolerance |
| 4 | FIELD_FORMATION | 30.7 h at 1 V (307 h at 0.1 V) | 10 s | dynamos pump the coils, persistent switches close, lattice heats through activation |
| 5 | PLASMA_CALIBRATION | 10 min | 8 s | test pulses, trim coils adjust, predicted against measured plume converges |
| 6 | FIRST_IGNITION | 60 s | 6 s | driver pulses start, exhaust appears (bootstrap power OPEN) |
| 7 | VERTEX_LOCK | 30 s | 5 s | lock lamps close round each engine, then across the four |
| 8 | SUSTAINED_MODULATION | 10 d | 8 s | only plume, diagnostics and four-engine balance change |
| 9 | SHUTDOWN_OR_FAILURE | 3.7 min | 8 s | pulses stop, coils persistent or ramped down, rings stow |

## Measurements (evidence class SW: SwiftShader, relative only)

Same views, 1280x720, headless Chromium, median of 3 x 120 frames; four engines plus the shared effects.

| | Today | A+ | Change |
| --- | --- | --- | --- |
| Sustained wide | 62.8 ms | 68.8 ms | +9.6 % |
| Draw calls (sustained wide) | 184 | 416 | +232 |
| Triangles (sustained wide) | 138,520 | 151,832 | +13,312 |
| Carriage side | 104.4 ms | 115.7 ms | +10.9 % |
| Dormant close | 129.0 ms | 144.3 ms | +11.8 % |
| Mesh nodes (4 engines) | 80 | 316 | +236 |
| GLB, Draco | 107 kB | 198 kB | +90 kB (viewer headroom 620 kB) |

Whole-ship default view: about +232 calls on 5,241 (+4 %). The cost is node count, not triangles: the moving groups need their own
nodes. A later GFX pass could merge the static A+ parts per engine (most of the 236 nodes) and keep only the 14 moving groups separate.

## Budget reconciliation (`budgets.py`, `budgets.json`)

| Ledger | Result |
| --- | --- |
| Mission | **Closes on its own assumptions.** 0.016 c per burn, mass ratio 1.2838, four burns, 1,629 t end, 4,426 t departure, 2,797 t propellant; 209 TW jet, 261 TW fusion; 28.5 burn days in all; the 1,825 t of D-He3 is what 261 TW for 28.5 d needs (1,831 t recomputed). Relativistic correction under 0.1 %. |
| Dry mass | **Does not close.** The mission carries the canon 250 t drive package. The drawn Vertex cluster weighs 6,328 t (1,244 t per engine, recomputed exactly, plus 1,353 t frame): 25x the allotment and 1.4x the whole departure mass. No mission number reads it. |
| A+ additions | 33.1 t per engine without the flywheel, 47.6 t with its share (the sized 1.8 estimate; the drawn review proxies weigh only 11.6 t). Four engines: 132 t, or 190 t with the 58 t flywheel. The 1.7/1.8 check compared that with the 174 t departure margin; but hardware carried through four burns at fixed delta-v needs 2.72 kg of departure mass per kg, so only **64 t** fits the envelope. A+ without the flywheel needs 4,786 t at departure (above the 4,600 t envelope); with the tanks unchanged the last burn falls 6.7 % short of 0.016 c. |
| Power and heat | **Does not close.** Canon assumes 80 % directed exhaust and 4e-5 absorbed (10.45 GW of the 10.80 GW drive share). The 1.6B source model gives a 41-44 % useful share: 476-511 TW of fusion and 4.7-5.0 kt of D-He3 (1.8-2.0x canon fuel). Heat reaching each engine is 34 TW, 12,700x its 2.70 GW share; neutrons alone 10 TW per engine; a coil shield against them weighs 45 kt for the cluster. |
| Startup | **OPEN.** Charging the coils takes 38.9 GJ (5.4x the 7.2 GJ main battery), a 350 kW load over 31 h the ship bus or the departure station can carry. The first driver pulses need 0.3-15.7 GJ at 31-1,570 MW: the 50 MW pulse bank covers only the lowest bracket, the 58 t flywheel the middle one. Without the flywheel the middle bracket has no sourced power path. |

**Consequence.** A+ is cheap relative to the engine it modifies (under 3 % of its drawn mass, +10 % frame time) and the sequence is
reviewable, but no A+ choice changes whether Vertex reaches 0.016 c. Mass, absorbed heat and useful power share block it together, by
one to four orders of magnitude. The research-chain squashes (1.6, 1.6A, 1.6B, 1.7, 1.8) are therefore squashes of **evidence** of
that, not of a working drive; they change no production geometry and are safe to squash on that understanding.

## Next milestone proposal: Vertex 2.0, integrated propulsion closure

**Question.** Is there any propulsion architecture, with one named and quantified fictional enabler at most, whose engine mass, heat
rejection, useful power share, fuel and startup close together for the full-return 0.016 c, 6-year mission? Pulsed fusion is one
candidate, not the premise.

**One ledger for every candidate** (extends `budgets.py` into a lab study): delta-v and burns, specific power (kW/kg of propulsion),
useful share, absorbed fraction against the 10.8 GW drive share, neutron share, propulsion dry mass against its allotment carried through
four burns (the 2.72 kg/kg rule), fuel against the inventory envelope, burn time against the 6 years, startup energy and power.

**Levers measured, not assumed.** Burn time: 28.5 burn days against 6 years leaves roughly one order of magnitude of jet power to trade
for time, which is not the three to four orders the heat needs, but it changes which architectures are in reach. The 250 t drive
allotment and the 4.6 kt departure envelope are owner numbers: the study reports what each candidate needs and leaves them unchanged.

**Candidate families.**
1. Pulsed Vertex as drawn (the reference; current evidence).
2. Steady-state charged-product exhaust: a mirror or field-reversed core whose products leave along open field lines (no armour, no
   pulse fatigue; absorbed heat set by bremsstrahlung, synchrotron and neutrons rather than by a target).
3. External energy for departure: beamed power or a beam-pushed sail from the departure system, a magnetic sail braking against the
   interstellar medium on arrival, onboard fusion only for the return pair of burns (it halves what the ship's own drive must carry).
4. Fission-fragment or other direct-product drives as a bound on what established physics gives at this exhaust speed.
5. The fiction route made explicit: the smallest single material or plasma property (for example a lattice that turns absorbed
   radiation into directed thrust at a stated efficiency) that closes family 1 or 2, with its required value, so the technology is
   fictional but quantified and consistent.

**Deliverables.** A lab study with the shared ledger and a Pareto table across the families; one recommended architecture and the
named enabler (if one is needed) for the owner; then a geometry phase that carries the A+ ignition machinery and nine-state sequence
over to whichever architecture is chosen, since a startup sequence, alignment and AI calibration are needed by every family.

## Unknowns (OPEN)

Ignition bootstrap power path without the flywheel; flywheel mass and energy; carriage mass (9-37 t bracket); plume response to the
alignment error; festoon-line life over the stroke; whether the drive allotment or the drawn engine is the number to revise.

## Files

`aplus.py` (pure: parts, states, timeline, shots), `blend_aplus.py` and `make_review.py` (Blender review file), `export_glb.py`,
`review_template.html`, `build_page.py` (browser review), `budgets.py` (pure ledger) and its `budgets.json`, `aplus_timeline.json`,
`review_summary.json`. `.blend` files and `runs/` are not committed.
