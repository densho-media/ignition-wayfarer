# Runaway departure: a story mechanism for T056 and the six-year check

NON-CANON story proposal, 2026-11-09. Numbers from `runaway.py` on the Vertex V4 ship (42.9 kt, thrust 2.90 MN, ve 19,201 km/s,
196 Hz); `results/runaway.json`. The four-burn minimum round trip reproduces the Phase 4 value (6.352 y).

## Summary

- **Yes, a sustained pulse-control failure can carry the story, and the timeline is already shaped for it.** The failure must last the
  whole first burn: reaching 0.016 c at V4's thrust takes **1.99 years and 12.3 billion pulses**, and ends 964 AU out. No glitch lasts
  that long, so the proposal is a *locked reference profile*: the controller rejects the planned test cut-off and flies the stored
  departure burn to its programmed end, 0.016 c. That explains why the story's peak speed is exactly the mission's cruise speed.
- **"Self-reinforcing" is physical in one precise sense:** each pulse pays for the next. The drivers (about 110 GW electrical in V4) are
  fed from the previous pulses' yield, so once lit the drive needs nothing from outside. It cannot mean growing power: the pulse rate is
  capped by the one-target-in-flight launcher and by the radiators.
- **The crew cannot stop it without stranding themselves.** The stop sequence belongs to the failed controller; there is no independent
  hard stop (exactly what T060's doctrine adds afterwards); the drive section is lethal while firing; the controller owns the thrust vector.
  In V4 a forced stop freezes the tin droplet radiator in under 3 seconds, and the ship then has no drive at all.
- **"Beyond rescue" arrives within days.** The ship passes 10 km/s after 1.7 days and 50 km/s after 8.5 days (0.12 AU). After that, a
  destructive stop leaves the six drifting beyond any short-range rescue, so their only way home is to let the burn run out.
- **Six years: compatible without changing any event.** The timeline gives years only. A 6.35-year round trip leaving Y155 returns in
  Y161 if the departure falls in the first 236 days of Y155 (before about late August). "About six years" covers 6.35. The 6.0-year
  alternative needs a0 0.0073 g and a 50.3 kt ship and is not needed.
- **T058 fits the minimum mission directly:** the brake and return burns run back to back as a 2.76-year continuous powered reversal at
  1,716 AU, a "years-long powered redirection" rather than a hairpin.

## 1. What the runaway has to do

The minimum four-burn trip at V4 (each burn 0.016 c, constant thrust, mass falling):

| Burn | Years | Propellant | Distance | Acceleration |
| --- | --- | --- | --- | --- |
| 1 outbound (the runaway) | 1.989 | 9,487 t | 964 AU | 0.0069 to 0.0089 g |
| 2 brake | 1.549 | 7,390 t | 751 AU | 0.0089 to 0.0114 g |
| 3 return | 1.207 | 5,756 t | 585 AU | 0.0114 to 0.0146 g |
| 4 brake at home | 0.940 | 4,484 t | 456 AU | 0.0146 to 0.0187 g |
| Coast home | 0.667 | | 1,716 - 1,041 AU | |
| **Round trip** | **6.352** | 27,116 t | turn at 1,716 AU | |

The runaway is burn 1. It uses 35 % of the propellant and leaves 17.6 kt, which is exactly what burns 2-4 need. So **the ship must have
been loaded with its full return propellant at First Ignition** (S2). A part-fuelled ship that runs to 0.016 c cannot come back.

The acceleration is gentle: the danger is not the push but the fact that it does not stop. Burn 1 milestones:

| Day | Speed | Distance | Light time |
| --- | --- | --- | --- |
| 1 | 5.8 km/s | 0.002 AU | 0.8 s |
| 7 | 41 km/s | 0.08 AU | 41 s |
| 30 | 176 km/s | 1.5 AU | 13 min |
| 100 | 593 km/s | 17 AU | 2.4 h |
| 365 | 2,261 km/s | 234 AU | 32 h |
| 726 (cut-off) | 4,797 km/s (0.016 c) | 964 AU | 5.6 d |

## 2. Why a pulsed drive can run away at all

A pulsed fusion drive has no burning core to run away: each 182 GJ pulse ends in microseconds, and with no target in the chamber nothing
happens. What it does have is a **closed energy loop**. Inductive recovery from each pulse recharges the drivers (168 MJ per pulse at
196 Hz, about 110 GW electrical at 0.30 wall-plug), the target factory, the launcher and the house load. Once the loop is running the
drive is self-powered, so nothing outside it keeps it alive and nothing outside it can switch it off. That is the self-reinforcing state.

At 196 Hz with one cryogenic target in flight at a time and nanosecond timing, only an automated controller can run the loop. It sits
in the drive section, near the drivers, because the timing does not survive long cables.

## 3. Proposed failure: the locked reference profile (S1)

1. **Set-up.** First Ignition is an integrated acceptance firing at full flight mass, so propellant is loaded but stores and crew are
   not. The controller flies the first minutes of the real departure-burn profile, the *reference profile*, with a planned test cut-off.
2. **Fault.** The cut-off is the one transition the controller treats as hazardous: a controlled ramp-down must retract the radiator
   sheet, drain the warm loop and stop the target train in a verified order. Its precondition, a verified field and target state, cannot
   be met because a redundant channel disagrees (a failed sensor, a corrupted state estimate). The interlock was written to protect the
   ship from a bad stop, so with the stop unverifiable it holds the last valid mode: the reference profile, at full thrust.
3. **Self-confirmation.** Every good pulse confirms the controller's state estimate in that mode, so its own health checks keep passing.
   Mode changes need authority the six people aboard do not hold. From outside, the controller is working perfectly.
4. **End.** The reference profile ends at its programmed cut-off, 0.016 c, 1.99 years later. The ramp-down at the planned end does not
   need the failed check, so the drive shuts down cleanly. That is why the story's peak is exactly 0.016 c, and why the drive is still
   usable for the brake.

Any similar fault works if it has these properties: it blocks the commanded stop but not the programmed stop, it is invisible to the
controller's self-checks, and the crew cannot reach it while the drive fires.

## 4. Why the six cannot stop it

| Way to stop it | Why it fails |
| --- | --- |
| Command a stop | The stop is the faulted transition; mode authority is not aboard |
| Independent hard stop | None exists. T060 adds field quenching, sacrificial collapse paths and core destruction afterwards, as the lesson of Wayfarer |
| Go aft and repair the controller | The drive section is inside the radiation and X-ray zone of a 36 TW drive (stand-off 64.7 m) while it fires |
| Turn the ship so the burn does less harm | The controller holds the burn attitude with the thrust vector; 1° of vectoring is about 50 kN, more than any RCS |
| Starve the target feed or cut power by force | An unsequenced stop. In V4 the 628 K tin droplet sheet (0.5 kg/m², 2,476 t over 4.95 km²) falls below tin's melting point 0.9 s after the heat stops and is solid in 2.7 s: the sheet freezes in flight and the warm loop solidifies, so the drive can never run again |

With today's panel radiators the freezing argument is weaker (heat pipes cool slowly), and the lock rests on the other four rows.

**The decision window.** A destructive stop is only survivable while a rescue craft can still match the ship's speed. The Y155 rescue
fleet is not canon, so the table gives the window per rescue Δv:

| Rescue craft Δv | Window (match speed only) | Window (match and return) |
| --- | --- | --- |
| 10 km/s | 1.7 days | 0.9 days |
| 20 km/s | 3.4 days | 1.7 days |
| 50 km/s | 8.5 days (0.12 AU) | 4.3 days |
| 100 km/s | 17 days (0.49 AU) | 8.5 days |

T042/G08's pre-Ignition high-g stages are short, low-Δv stages, so the window is days. After it closes, wrecking the drive means drifting
outward for ever. The rational choice is to let the burn run out and fly the rest of the mission, so the six are committed within the
first week. This matches T057's "beyond rescue", and it is a strong story beat.

## 5. Rejected explanations

| Explanation | Verdict |
| --- | --- |
| The fusion burn sustains itself | No. A pulse ends when its target is spent (G07) |
| A Level C lattice property | Possible only as an owner decision; Vertex gives the lattice no numeric credit (D-07) and none is needed |
| Power runs away upward | No. The pulse rate is capped by the target launcher and radiators (below) |
| The crew choose to keep burning | No. Stopping earlier always means less Δv to undo and a shorter trip home; only an inability to stop reaches 0.016 c |

## 6. Does about six years hold 6.35?

**Yes, with no change to any event.** The timeline dates Wayfarer by year only (T055 and T056 Y155, T059 Y161, G10 "around Y161 after
roughly six years").

| Check | Result |
| --- | --- |
| Return inside Y161 | Departure in the first 64.8 % of Y155, before day 236 (about late August) |
| "About six years" | 6.35 rounds to six |
| Relativistic clock on board | γ = 1.000128; the crew age at most 7 hours less, not a lever |
| Coasting before the brake burn (repair, the flip) | Every coast day at 0.016 c adds two days to the trip. Leaving on the first day of Y155 leaves at most 118 days |
| The 6.0-year alternative | a0 0.0073 g, a 50.3 kt ship (+17 %). Not needed |
| Overdriving the runaway to reach 6.0 y | Burn 1 at 1.21× power: 238 Hz, a 16.3 km/s launcher (13.4 nominal), a 659 K warm loop. Rejected as the baseline: it would damage the ship's radiators, and the calendar already fits |

T058 is consistent with the minimum mission: on the 6.35-year trip, the brake (burn 2) and the return burn (burn 3) run back to back,
2.76 years of continuous thrust turning the velocity vector around at about 1,716 AU. That is a years-long powered redirection rather
than a hairpin. Solar gravity at 1,716 AU is negligible, so gravity belongs to the inner-system end of the return, as T058 says; that
heliocentric solution (O17) is not modelled here.

## 7. Owner questions

| ID | Question | Recommendation |
| --- | --- | --- |
| S1 | Adopt the locked reference profile (a faulted stop interlock flies the stored departure burn to its 0.016 c cut-off) as the T056 mechanism? | Yes. It explains both the duration and the exact peak speed |
| S2 | Was Wayfarer loaded with its full return propellant at First Ignition (an acceptance firing at full flight mass, with stores and crew not yet aboard)? | Yes. Without it there is no return in any generation |
| S3 | Place the Y155 departure in the first 236 days of the year? | Yes. Otherwise the return slips into early Y162 |
| S4 | How long may the crew coast at 0.016 c before the brake burn (repair, the flip of a 20 km-span ship)? | Keep it under about 118 days, less for a later departure |

Not in scope: Seraph's role (the mechanism does not depend on it), life-support budgets, the heliocentric return and Kuiper timing (O17).
