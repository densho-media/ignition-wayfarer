# T02 handoff: dust, radiation exposure and braking protection

| | |
| --- | --- |
| Thread | T02, spacecraft protection and mission survivability |
| Date | 2026-11-09 |
| Status | DONE. Partial items that need other threads are listed in F and C "Unknowns". |

## A. Mission and scope
- Investigated (numbering follows `planning/T02-DUST.md` section 3):
  1. two-orientation exposure map for V0, V1, V2 and the canon ship at 0 / 0.4 / 2.29 / 5° (REPORT section 1);
  2. environment and fluence per leg, four cases (section 2);
  3. impact physics, regimes, hits per leg and component, erosion (section 3);
  4. sacrificial multilayer bumpers: stand-off, layers, mass, re-coverage (section 4);
  5. detection and active mitigation (section 5);
  6. electromagnetic control of gas and ions; D-12 for grains (section 6);
  7. geometry protection: the shadow-cone skirt, the canon aft annulus, guard rings (section 7);
  8. plume interaction as a hypothesis (section 8);
  9. radiators: edge-on exposure, retraction, droplet sheets (section 9);
  10. radiation dose in both orientations, crew and engine hardware (section 10).
- Deliberately excluded, and why:
  - changes to mission duration, speed, burn count or orientation (forbidden; written as owner questions D-T02-1 and D-T02-3);
  - hydrocode or MHD/PIC simulation (D-09 not approved; energy scaling used instead);
  - structural design of the skirt;
  - Drive reads through `wayfarer-drive-reader` (the agent does not exist in this session). Canon was read from the repository only.

## B. Repository state
| Item | Value |
| --- | --- |
| Starting commit (Phase 1 base) | `8de3ffa189b47ce9a1212b550b7ea75f8c36314a` |
| Branch | `claude/project-thread-uwi5pl` |
| EARLY commit | `c1abd54` |
| Resulting commit | the commit that adds this file (recorded in `/mnt/project-files/vertex/threads/T02.md`), pushed |
| Changed paths | `lab/variants/vertex-drive/studies/dust/` only: `EARLY.md`, `REPORT.md`, `HANDOFF.md`, `TABLES.md`, `registry_proposal.toml`, `environment.py/.json`, `exposure.py/.json`, `impacts.py/.json`, `radiation.py/.json`, `tables.py` |
| Rerun | from the repo root: `python3 lab/variants/vertex-drive/studies/dust/environment.py` (~8 s), `exposure.py` (~30 s), `impacts.py` (~1 s), `radiation.py` (<1 s), `tables.py`. Together ~40 s; the JSON files reproduce byte for byte. |

## C. Research findings
### Published evidence
- Kuiper-belt dust density of order 35 per km³ above ~0.6 µm, above models to 55-60 AU (S-T02-SDC). SECONDARY_VERIFIED.
- Interstellar dust 2.1e-24 kg/m³ (S-T02-KRUGER-2015) to 6.2e-24 (S-T02-FRISCH-1999). SECONDARY_VERIFIED.
- Large interstellar grains: a bound of 1e-10 m⁻²s⁻¹ above 3e-10 kg (S-T02-LANDGRAF-2000), or 2e-9 by radar, which is disputed (S-T02-AMOR). SECONDARY_VERIFIED.
- Interplanetary flux model (S-T02-GRUN-1985). TRANSCRIBED.
- LIC gas (S-T02-LIC) and heliopause near 120 AU (S-T02-VOYAGER-HP). SECONDARY_VERIFIED.
- Atomic-regime impacts by relativistic grains (S-HOANG-2017). TRANSCRIBED from the registry.
- Laboratory limits: dust accelerators reach about 100 km/s (S-T02-HIGGINS-2018, UNVERIFIED); Whipple ballistic-limit equations hold to 7-10 km/s (S-WHIPPLE-BLE).
- REBCO critical current and n-value degrade from about 1-4e22 neutrons/m² (S-T02-REBCO-N). SECONDARY_VERIFIED.

### Calculated results
- P11 reproduced: 112.55 m, 50 parts, 1,491.7 m² (`exposure.py`, `p11_reproduction`).
- Engine-first exposure at 0.4°: V1 12,282 m², V0 12,260 m², canon 4,015 m². The back of the forward shield adds 6,312 m² (`exposure.json`).
- The skirt (T02-NEW-1) cuts V1 to 2,281 m² at 0.4°, 4,060 at 2.29° and 9,194 at 5°. The canon aft annulus cuts the canon ship to 368 m² at 0.4°.
- NOMINAL hit counts over the mission:

  | Configuration | Bare 5 mm wall | Beyond 2 m bumpers |
  | --- | --- | --- |
  | V1 with skirt | 12,000 | 540 (F5 390, F1 125) |
  | Canon with annulus | 1,570 | 67 |

  Across cases (V1 with skirt, beyond 2 m bumpers): LOW 3.4, HIGH 17,300, HILAT 89 (`impacts.json`).
- Canon Brow, bow-first, NOMINAL: 5,180 grains beyond its 2 m disruptor and 489 above 1 MJ.
- Uniform erosion is 0.04-35 µm per leg. Gas effects are negligible: 0.03 W/m², about 1e15 H/cm², under 1 nm of sputtering.
- Burn radiation is the same in both orientations (`radiation.json`, `orientation_check`).
- Nozzle-loop neutron fluence per mission is 9.3e18 to 1.9e20 n/cm², or 3-62 times the REBCO tolerance. LiH shoes that would bring it down cost 180-260 t and add 0.0127 to the burn's hardware solid-angle share.
- The plume vaporises only grains below 1e-15 to 4e-13 kg and takes no momentum from them, so it earns no credit.
- Detection gives 0.2-21 ms of warning, which is not enough to clear anything.

### Engineering extrapolations
- Crater volume = k·E with k between 1e-11 and 1e-10 m³/J. Bumper defeat energy grows with stand-off squared. Both come from the energy-scaling physics. A hydrocode or a test at 100 km/s or more would confirm or refute them.
- Grazing impacts on radiator planforms at 0.4° have a normal component of about 33 km/s, so they behave as gouges. This can be tested in a dust accelerator now.
- Droplet-sheet loss is about 1 kg per burn.
- Burn-facing bumpers add +0.001 to +0.004 to the hardware solid-angle share.

### Fictional assumptions
- The canon Fiji card is not used.
- T02-NEW-4, a conductor that tolerates neutrons, is a proposed Level C need. It is labelled as such and not used anywhere.

### Unknowns
- How many grains above 1e-9 kg exist in the Kuiper belt. Nothing has measured them, and they set the LOW-HIGH spread of about 5,000 times.
- The damage a 0.1-10 mg grain does at 1,000-5,000 km/s. No experiment covers it.
- The quench or cut threshold of a REBCO sector.
- How much REBCO degrades under in-situ irradiation.
- Rim scatter and finite source size at the skirt. These need T04's hot-spot size and a transport code.
- Radiator leading-edge thickness (T01).
- The canon destination and heading.

### Negative results
- Active clearing, magnetic deflection of grains and plume screening all fail.
- Retracting the warm wings during braking does not work while drivers are running.
- No external shield can cover the hardware visible through the open nozzle.
- Shielding the loops in place against neutrons nearly doubles the hardware's share of the burn's sky.
- The HIGH environment does not close: a stand-off of 287 m would be needed.
- FDP-1/Vertex cannot stop inside the Kuiper belt.

## D. Quantitative effects
| Quantity | Value | Unit | Uncertainty / range | Label | Source |
| --- | --- | --- | --- | --- | --- |
| Grain energy at 0.016 c | 1.15e10 | J/kg | - | MODEL | impacts.py |
| Engine-first exposure V1, 0.4° | 12,282 | m² | 12,175-12,735 over 0-5° | MODEL | exposure.json |
| Engine-first exposure V1 with skirt | 2,281 | m² | 2,022-9,194 over 0-5° | MODEL | exposure.json |
| Engine-first exposure canon / with annulus | 4,015 / 368 | m² | 207-3,385 with annulus over 0-5° | MODEL | exposure.json |
| Skirt mass V1 | 22-90 | t | 0.5-2 kg/m² | MODEL / ASSUMPTION | impacts.json skirt |
| Canon annulus mass | 6-31 | t | 1-5 kg/m² | MODEL / ASSUMPTION | impacts.json canon_skirt |
| Residual events V1, skirt + 2 m bumpers | 540 | per mission | 3.4 (LOW) to 17,300 (HIGH) | MODEL on EXTRAPOLATION | impacts.json hits |
| Residual events canon, annulus + 2 m bumpers | 67 | per mission | 14 to 970 | MODEL on EXTRAPOLATION | impacts.json hits |
| Stand-off for < 0.1 events, V1 with skirt | 25 | m | 8 to 287 | MODEL on EXTRAPOLATION | impacts.json |
| Energy defeated by a 2 m bumper | 8.4e4 | J | 5.4e3 to 7.5e5 | EXTRAPOLATION | impacts.json |
| Canon Brow events beyond its 2 m disruptor | 5,180 | per mission | 823 to 79,400 | MODEL on EXTRAPOLATION | impacts.json brow_bow_first |
| Uniform erosion per leg | 0.04-35 | µm | k band ×10 | EXTRAPOLATION | impacts.json erosion |
| Loop 1 neutron fluence, V1 | 9.4e19 | n/cm² | first-order 1/r² | MODEL | radiation.json |
| Loop fluence / REBCO tolerance, V1 | 31 / 14 / 3.5 | ratio | up to ×100 in situ | MODEL / PUBLISHED range | radiation.json |
| LiH shoes on all loops, V1 | 193 | t | λ 0.10-0.17 m | MODEL on ASSUMPTION | radiation.json |
| Added solid-angle share of the shoes | 0.0127 | - | chord 0.6 m ASSUMPTION | MODEL | radiation.json |
| Detection warning, 1 mm grain at 10-100 km | 2-21 | ms | - | MODEL | impacts.json detection |
| Gas power flux in the LIC | 0.030 | W/m² | - | MODEL | impacts.json gas |
| FDP-1/Vertex minimum stopping distance | 1,717 | AU | - | MODEL | environment.json |

## E. Model and geometry implications
- **Skirt** (CONCEPTUAL_ILLUSTRATION): a cone with its apex at (-227.54, 0, 0).
  - V1/V2: half-angle 7.94°, r 7.2-45 m, x -175.8 to +95.1 m.
  - V0: half-angle 9.60°, r 8.5-45 m.
  - Keep-out: nothing may cross the sheet except along burn rays.
- **Canon aft annulus** (CONCEPTUAL_ILLUSTRATION): x -98 m, r 5.7-45 m.
- **Guard rings and local bumpers** (PARAMETRIC_PLACEHOLDER):
  - guard rings 20-25 m forward of loops 2 and 3, at r 64.7 m and 112.0 m, about 0.8 m wide;
  - local bumpers of ≤ 2 m stand-off on the faces of every loop, strut and feed outside r 45 m.
- **Nozzle loops** (PARAMETRIC_PLACEHOLDER): drawn as six separable sectors each, with a replacement path to the hull.
- **Attitude:** braking requires the stream within about 1° of the axis.
- Nothing is drawn without D-10.

## F. Dependencies
| Needed from | What | Status (received at commit / placeholder used) |
| --- | --- | --- |
| T04 | neutron and X-ray escape shares, emission spectra | received at `1b85941`; FDP-1 escape share 5.52e-6 used (T04 agrees) |
| T04 | burn hot-spot size, for the skirt's rim and penumbra margin | not received; point source assumed |
| T01 | radiator envelopes | received at `57fe625`; frontal area for the 1.1 km planning wing scaled (EXTRAPOLATION) |
| T01 | leading-edge thickness | UNKNOWN |
| T03 | coil positions and added coils; nozzle efficiency with a sector lost; plasma reaching the guard-ring zone | T03 had not published; FDP-1 loop positions used |
| T05 | illustrations of section E | not requested before D-10 |

## G. Decisions
- Existing register:
  - D-06: options quantified in D-T02-2; recommendation only.
  - D-12: confirmed for grains, with no challenge.
  - D-05: wings treated as experimental geometry; their edge-on exposure was computed.
  - D-09: no MHD/PIC was run.
  - D-08 and D-11: untouched.
- Proposed new decisions (all for the owner; full wording in `registry_proposal.toml`):
  - D-T02-1: the FDP-1/Vertex destination versus the Kuiper anchorage.
  - D-T02-2: which D-06 option to develop (a-d with numbers; recommendation a).
  - D-T02-3: whether the departure heading is free to leave the ecliptic.
  - D-T02-4: replace loop sectors, or require a Level C conductor (recommendation: replacement).
- A recommendation is not an owner approval.

## H. Validation
- Tests and checks, run on the branch after `git fetch origin main`:
  - `atlas.py validate`: 0 errors;
  - Atlas tests: 21 OK;
  - FDP-1 tests: 45 OK;
  - four-burn tests: 18 OK;
  - `check_v3.py`: 127/127.
  - Before the fetch, the canon-guard tests in the Atlas and FDP-1 suites failed only because the local `origin/main` was stale (merge-base 92b83f0). After the fetch they pass.
  - Running `check_v3.py` without `--regen` rewrites `VALIDATION_V3.md`. That file belongs to the problem map, so the rewrite was reverted and not committed.
- Own reproductions: P11 matches. All JSON files regenerate byte for byte.
- Model limitations:
  - First-hit geometric coverage.
  - Straight axial grain tracks inside a cone.
  - Damage by energy scaling.
  - First-order radiation: no build-up, no (n,γ) secondaries, no scatter.
  - Radial mission legs with ignition at 1 AU.
  - Assumed environment shapes outside the measured ranges.
- Unresolved failures: none.

## I. Integration instructions for T00
1. Bring in `studies/dust/` as is. It reads, and never writes, `results/convergence.json`, the FDP-1 baseline and the problem-map geometry.
2. From `registry_proposal.toml`:
   - add T02-NEW-1 to T02-NEW-4, the S-T02-* sources and the links;
   - apply the revisions to VTX-08A, VTX-08B (verdict IMPOSSIBLE), VTX-08C and VTX-08D;
   - add D-T02-1 to D-T02-4 as OPEN.
3. Generation changes proposed:
   - none to the drive;
   - add the skirt mass (22-90 t, MODEL) as a fixed item to V1/V2 if D-T02-2 (a) is chosen;
   - add loop-sector spares once T03 gives the sector mass.
4. Known conflicts:
   - Burn-facing loop shields and bumpers worsen the burn solid angle (T03/T01). The deciding test is T03's nozzle efficiency with a sector missing, set against the shoe solid-angle cost.
   - T01's planning wing (tip 1.1 km) is larger than the Atlas V1 wing, so its frontal area should be recomputed with `exposure.py` once T01 commits an envelope.
5. Re-run after integrating:
   - `atlas.py validate`;
   - the Atlas, FDP-1 and four-burn tests;
   - `check_v3.py`;
   - the five T02 scripts, then compare the JSON.

## J. Recommended next experiment
**Question:** do thin sheets turn hypervelocity grains into harmless spread-out plasma, and how much damage does a grazing grain do to a radiator planform?

**Method:** dust-accelerator shots (about 30-100 km/s, the upper end of the lab range) on two targets:
- a 0.5-2 kg/m² two-layer bumper at 0.1-1 m stand-off;
- radiator coupons at 0.4-5° incidence.

**Expected output:** a measured debris-cone angle α and allowable wall fluence F_allow, the two numbers that set the ×10 bumper band. Then extend analytically to 4,800 km/s.

**In the lab:** a model-side bound on the Kuiper-belt large-grain population from New Horizons SDC and Kuiper-belt collision models.

**Cost:** existing facilities, research only.

**Owner:** a future T02 phase, or T00 to assign. In parallel, T03 should compute nozzle efficiency with one of six sectors lost per loop, because it decides whether T02-NEW-3 is the pathway.
