<!-- lab entry -->
| Lab entry | |
| --- | --- |
| Kind | Study |
| Status | ACTIVE |
| Question | In what order could the approved ship be assembled in orbit, from the first structure to first ignition? |
| Model base | main 0aa94a3 (the Explore Ship model of that commit) |
| Branch | claude/project-thread-mi3h1k, 2026-11-10 |
| Open owner questions | Is the order right (phase by phase); the assembly yard and its fixture; where the ship is built (orbit, station) |
| Review | GitHub Pages /engineering/build/ after a squash; preview screenshots in the project files review/build_sequence_2026-11-10/ |

# assembly-sequence: notes

Owner brief 2026-11-10: show on the Engineering pages how Wayfarer would be built, step by step, from the foundation to the last
part, first with today's prototype and later in more detail as the design grows. This study writes that order down as data and checks
it; `tools/story.py` publishes it as `engineering/build/`, where every step is shown on the Explore Ship model.

## Function

- `sequence.toml`: 7 phases, 25 steps. Each step says what it installs (selectors on the Explore Ship parts), what must be complete
  first (`after`), what carries its loads (`rests_on`), why it comes where it does, finer sub-steps (`detail`), open questions and
  which mass-model parts it completes (`mass`).
- `sequence.py`: checks the file (unique ids, phases in order, `after` only to earlier steps, valid selectors), books every part of
  the placed mass model (`src/wayfarer/mass_model.py`, B02) and the mission propellant onto exactly one step, and with
  `--manifest`/`--holo` (a `web` run's `work/manifest.json` and `site/viewer/model/holo-*.json`) reports which step every exported
  part lands in.
- `site.py --json`: the record the website reads. The browser (`web/engineering/build.js`) classifies the Explore Ship parts with the
  same rules as `sequence.classify`.

## Fixed constraints

- The model on `main` is the ship. The sequence adds no geometry and changes no part; it only orders the parts that exist.
- Load paths decide the order: a part is installed only after the structure it hands its loads into (`rests_on`, `after`).
- Mass comes from the mass model and the operating point, never from the sequence.

## Assembly logic (PROTOTYPE judgment, Claude 2026-11-10)

1. **Backbone first.** The spine and primary cage are the datum and the end of every load path, then the thrust ring that will take
   the drive, then the bypass collar and thrust deck that carry the forward end around the rings.
2. **Drive and power at the open aft end.** Shadow shield, then core and manifold along the axis, then the four nozzles on their
   pickups, then the Brayton plant and storage beside the reactor, while nothing crowds the aft end.
3. **Thermal: inside out.** Coolant chases in the open cage, the casing over them with the boots set in, the datum and sliding mounts,
   then the fragile blades after the heavy lifts, then the WARM and LOW sections and the bulkhead.
4. **Habitat on true bearings.** Rotor hubs run in on the spine first; both rings grow from 15° segments in opposite pairs to bound
   imbalance; the pressure sectors are the first pressure volume and can be held at pressure from then on.
5. **Propellant, then the bow.** Empty vessels onto the deck after the rings (the outer vessels would block the ring segments), cold
   plumbing after the vessels, then the 90 m shield that closes the bow, then the EYE, Crown and Lance on it.
6. **Crew access and services.** Trunk and refuge once the drums exist, the ship's own ports and airlock, then everything whose field
   of view or plume must be checked against finished structure.
7. **Outfitting and commissioning.** Interiors through the ports into pressurised spaces, water shielding into proven frames, drones,
   then propellant, spin-up and the first-ignition ramp.

## Findings

- All 5,287 exported parts of the Explore Ship model at `0aa94a3` land in a step by an explicit selector (none by the subsystem
  fallback, none unplaced), and every step has parts except the last, which adds none: commissioning is loading, spin-up and ignition.
- Mass ledger: 1,670 t of hardware and stores plus 2,797 t of propellant = 4,466 t, which is the operating point's departure mass of
  4,426 t plus the 40.2 t CIRC-001 ring corridors that the placed mass model carries and the operating point does not yet include.
- The fixed main structure (125 t) is booked when the backbone is complete; the budget does not split it between the spine, the thrust
  ring and the collars, so the page shows it as one step.

## Unknowns

- The assembly yard: where the ship is built, what holds it, how sections arrive (launch size limits section length).
- Bearing imbalance tolerance while the rings are incomplete; bolt and splice preloads; alignment tolerances at the nozzle pickups.
- Q45 collar load split; OD-014 shield material and mass; OD-018 lance field and power; the drive topology (FDP-1, Vertex).

## Design freedom

The order inside a phase is judgment and can change freely; the order between phases follows the load paths and the fragile-last
rule. To extend: split a step by adding a step after it with narrower selectors (file order decides), move a `detail` line into its
own step when the model gains its parts, and add `after` links. A new part in the model lands in its subsystem's step through the
`fallback` selectors until a step claims it. Run `python3 lab/studies/assembly-sequence/sequence.py --manifest ... --holo ...` after a
model change to see where new parts land.

## Decisions

- 2026-11-10: kept as a lab study (not canon, no workbook owns an assembly sequence); published read-only as `engineering/build/`.
