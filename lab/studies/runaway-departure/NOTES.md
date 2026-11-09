<!-- lab entry -->
| Lab entry | |
| --- | --- |
| Kind | Study |
| Status | ACTIVE (story proposal, NON-CANON) |
| Question | Can a sustained automated pulse-control failure explain Wayfarer's runaway departure to 0.016 c, and does "about six years" (Y155 to Y161) hold the 6.35-year minimum round trip? |
| Model base | Vertex Phase 4, claude/project-thread-9rsgog @ a1c8246 (V4, 42.9 kt) |
| Branch | claude/project-thread-oeqad4 |
| Open owner questions | Adopt the locked-reference-profile mechanism (S1); full propellant load at First Ignition (S2); departure in the first 236 days of Y155 (S3); how long the crew may coast before the brake burn (S4) |
| Review | REPORT.md (this folder) |

# runaway-departure: notes

Owner brief 2026-11-09 (Vertex T05 message, story paragraph): investigate a sustained automated pulse-control failure as the explanation
for the runaway departure (timeline T056), and check whether about six years accommodates the calculated 6.35-year mission without
changing established narrative events. Research only: no lore, canon, Drive, `data/`, `src/` or geometry change. The IGNITION Timeline was
read through the Drive connector, read only, on 2026-11-09; its rows are paraphrased by ID and not copied here.

**Function.** Find a failure that a pulsed fusion drive can actually have, that keeps the drive firing to 0.016 c, and that the six people
aboard cannot end, then check the calendar.

**Fixed constraints.** The drive stops when target injection stops (Phase 4, T056 flag); G07, technology does not cancel inertia, heat
or radiation; T056 unplanned, self-reinforcing, about 0.016 c, six unintended occupants; T057 about six years beyond rescue, the ship
turned into a habitat; T058 First Loop, a years-long powered redirection with gravity used later in the return; T059 return Y161; T060
the post-Wayfarer fail-safe doctrine; G10 leaves Y155, back around Y161; O17 the 0.016 c peak and the First Loop are established.

**Unknowns.** The rescue capability of Y155 craft; the ship's RCS authority; the warm-radiator working fluid in the canon ship (V4 uses a
tin droplet sheet, a TARGET technology); months within Y155 and Y161 (the timeline gives years only).

**Design freedom.** Which controller fault, which interlock design, what the crew tries and when. These are story choices.

**Decisions.** Everything is calculated on V4, the principal experimental configuration. The kinematics do not depend on the generation:
every closing generation flies the same a0 0.0069 g and ve 19,201 km/s, so the burn times and the 6.35 years are the same for V0, V4 and V5.

Run: `python3 lab/studies/runaway-departure/runaway.py` (writes `results/runaway.json`; about 1 s, standard library only).
