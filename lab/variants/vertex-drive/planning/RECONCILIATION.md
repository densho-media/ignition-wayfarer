# Vertex Phase 4: reconciliation of the T01-T04 and T06 handoffs

| | |
| --- | --- |
| Kind | variant (research, NON-CANON) |
| Owner | T00 integration |
| Date | 2026-11-09 |
| Base | `8de3ffa` (Phase 1 base); research branches T01 `1302708`, T02 `3c665ec`, T03 `59244a9`, T04 `fd4ff3d`, T06 `f39023a` |
| Applied by | `planning/integrate_phase4.py` (registry), `registry/generations.toml` (V3-V5), `convergence.py` (adapter) |

Each item gives the conflict, both sides with their source, the resolution and why. No conflict was resolved by taking the more
optimistic value. Where two values are both right for different cases, both are kept with their case.

## R. Contradictions and inconsistent units

| ID | Conflict | Side A | Side B | Resolution |
| --- | --- | --- | --- | --- |
| R-01 | T02 dust specific energy | HANDOFF D, REPORT (two places), registry proposal: "1.15e10 J/kg" | T02's own grain table and every calculation: 11.5 kJ per µg | **Unit error in the text**: ½v² at 0.016 c is 1.15e13 J/kg (= 1.15e10 J/g). The calculations are right; the registry carries 1.15e13 J/kg. T02's study files are not edited (owned by T02); this note is the correction. |
| R-02 | Nozzle efficiency definition | Atlas V0-V2 and FDP-1: 0.79 booked as thrust efficiency | T03: 0.79 is Thio's momentum efficiency; thrust efficiency is its square, 0.62 | **T03 decides** (D-19). V0-V2 keep 0.79 as historical conditional cases. V3-V5 use T03's ideal closure-coil η_T 0.791 at 15 E_p as a TARGET upper bound, with 0.740 (10 E_p) and 0.64 (literature) reported beside it. The FDP-1 calculator is unchanged. |
| R-03 | Gain bound | T06: power law G ≤ 1,787 η_c/α (ρ/3,000)^(-2/3), no ignitor term | T04: `ignition.ceiling_V1` with the ignitor energy | **T04 decides**: T06's form is 8-12 % optimistic. At 2,000 g/cm³ and coupling 0.5 the T04 ceiling is 1,084 (T06 used 1,171). V3-V5 take the gain from T04's function at run time. |
| R-04 | House load | T06: 2.6e-5 of fusion | T01 planning case: 4.4e-5 (bottom-up 0.012-0.014 % conservative) | **T01 decides** (the thread that booked it); 4.4e-5 in V3-V5. |
| R-05 | Warm loop | Atlas V1/V2: 700 / 800 K single loop at 1.0 kg/m² | T01: booked circuits give 628 K (TARGET components), 489 K with today's parts | **T01 decides** (owner 2026-11-09, D-13). 628 K at 0.96 kg/m² (V3) or 0.5 kg/m² droplet-sheet TARGET (V4). 489 K and 670 K reported as bands. |
| R-06 | FDP-1 injection figures | T01: "FDP-1 107 Hz, 3.74 m apart, 12.5 targets" | T04: V0 212 Hz, 1.88 m, 22.9 targets | Both right for different ships: T01 quoted V1. Fluence on the next target 5.3e6 (V1) and 2.1e7 J/m² (V0) X-rays, 1.4 and 5.5 kJ on target. |
| R-07 | One-target-in-flight speed | T01: 4.7-7.5 km/s (path 46.6 m, V0-V1 cases) | T04: 4.6 (V1) and 9.2 (V0) km/s (stand-off 43 m) | Both consistent within their path definitions. Phase 4 measures it on the corrected ships: V4 needs ≥ 12 km/s (path 68-83 m), V5 ≥ 6 km/s (results/convergence.json `V4_launcher_sweep`, `V5_launcher_sweep`). |
| R-08 | Merged duplicates | T01-NEW-1 (launcher) | T04-NEW-4 (one target in flight) | Same technology: merged as **VTX-01H**; both threads' claims kept with their source. |
| R-09 | D-03 basis | Register: 340 GW trim power at 80 GJ stored (1 E_p) | T03: 3.2-4.8 TW at 10-15 E_p | D-03 conclusion unchanged, evidence restated: the fast-trim argument gets stronger at 10-15 E_p. |
| R-10 | Coupling needed for gain 3,000 | T04 record: η_c/α 0.39 / 0.19 / 0.12 at 500 / 1,500 / 3,000 g/cm³ | T04 handoff: 0.41 / 0.20 / 0.13 | Rounding of the same function at two burn fractions; the registry quotes T04's function (`ignition.eta_needed`) at run time, and convergence.json carries the value per generation. |
| R-11 | Source states | T06 handoff: S-T06-NIF-DENSITY and S-T06-CNTF-2024 UNVERIFIED (snippets) | T06 proposal: SECONDARY_VERIFIED | **Lower state kept** (UNVERIFIED). |
| R-12 | Source kinds / bases | T01 patent, catalogue, lecture; T03 paper, experiment; T01 basis EXTRAPOLATION; S-T01-LEDGER verification "MODEL" | Atlas schema | Atlas gains patent, catalogue and lecture; paper and experiment map to journal; EXTRAPOLATION maps to ASSUMPTION; thread study models are `model` and PRIMARY_VERIFIED only because T00 reran them (study reproductions below). |
| R-13 | T02 links and purposes | `note` instead of `effect`/`quantified`; loop sectors tagged P03 (injection) | Atlas schema | `effect` = T02's note, `quantified` = UNKNOWN; sectors are P05/P06 magnet hardware. |
| R-14 | T06 link cases | Quantified by T06 study cases absent from convergence.json | Atlas schema | Validator accepts `study:<folder>:<case>` and checks the case is present in that study's committed JSON. |
| R-15 | T03 claims | String ranges ("10-15", "0.0013 (0.0012-0.0020)") | Atlas claims need a number | Number = first value, the full range kept as `range` and shown in the rendered Atlas. |
| R-16 | Share of the nozzle loss that strikes hardware | FDP-1 / four-burn scenario: 0.02 (ASSUMPTION) | T03: 0.06-0.07 for nozzle C at 10-15 E_p (MODEL) | **T03 decides** (a model over an assumption, and the worse value): 0.065 in V3-V5; T03's solid-angle increase (0.017 → 0.040-0.051) is **not booked** by the calculator and is listed as an unbooked penalty. |
| R-17 | Stale file on main | `lab/variants/fdp1/VALIDATION_V3.md` | `check_v3.py` regenerates it with different numbers | Pre-existing on main, not caused by Vertex; the check is run and its rewrite reverted. Reported, not fixed (out of scope). |

## Study reproductions (T00, worktree at 80d757a)

Every thread script was rerun from a clean checkout of the merge commit. Exit codes and output comparison are in
`INTEGRATION_REPORT_PHASE4.md` §7.

## IGNITION timeline: historical context and conflicts (D-25)

The IGNITION Timeline workbook was read through the Drive connector, read only, on 2026-11-09 (source S-IGNITION-TIMELINE). Its text is not
copied into the repository. T06's history scaffold was undated because T06 could not read it; the events below anchor it. Each line is a
paraphrase with the workbook's own row ID, and a verdict against the engineering.

| Timeline row | Paraphrase | Engineering | Verdict |
| --- | --- | --- | --- |
| T055 | First Ignition, Y155: the first practical relativistic drive | Vertex gives the Fiji lattice no numeric credit (D-07); O04 keeps the Fiji Drive performance ladder OPEN | **Flag**: "relativistic" fits 0.016 c only as a story label; no conflict with canon, which leaves performance OPEN |
| T056 | Wayfarer 001 departs in an unplanned, self-reinforcing drive state at about 0.016 c with six unintended occupants | A pulsed ICF drive stops when injection stops; no Vertex or FDP-1 mechanism is self-sustaining | **Conflict**: needs either a story mechanism outside the drive physics (a control or target-feed fault that keeps firing) or a Level C property. Do not resolve in engineering; owner question |
| T057 / G10 | Out Y155, back about Y161: about six years | FDP-1 round trip minimum 6.35 y at 0.0069 g; 6.0 y needs about 0.0073 g (T06) | **Conflict, small**: 6.0 vs 6.35 y (already open since FDP-1) |
| T058 | First Loop: a years-long powered redirection using gravity | Four-burn out-and-back at 0.016 c; T02 stopping distance 1,717 AU; destination and heading not locked (owner 2026-11-09) | **Compatible in principle, not modelled**: a gravity-assisted turn is a mission-design question; stays OPEN with D-15/D-17 |
| T042 / G08 | A full burn stack (high-g drives) before First Ignition | Vertex ceiling about 0.019 g; 1 g is 5,084× out of reach in specific mass | **Flag**: those high-g stages must be short-duration, low-Δv chemical or fission stages, not this drive class |
| T060 | Post-Wayfarer fail-safe doctrine (field quenching, a hard stop) | VTX-05B fault tolerance and replaceable sectors | Compatible |
| T089 | Lattice degradation over time | Replaceable sectors (VTX-03E); radiation damage limits (VTX-03F) | Compatible |
| G07 | Technology does not cancel inertia, heat or radiation | Every Vertex generation books heat and radiation | Consistent |
| O03 | Naming: Lattice Drive (current), Alcyone (legacy) | Vertex is a lab name | Naming only; no conflict |

## Not reconciled (open)

- Compression coupling achievable today (percent range) vs the 0.5 research target: an unresolved scientific barrier, not a data conflict.
- Closure-coil η_T from a vacuum-field model vs any self-consistent plasma result: D-21 (proposal only).
- Dust survival at 0.016 c with no locked heading: D-06, D-15, D-17.
- T056 runaway ignition vs a pulse-limited drive: owner question.
