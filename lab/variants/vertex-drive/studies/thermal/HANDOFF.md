# T01 handoff: thermal systems, electrical efficiency and mass

| | |
| --- | --- |
| Thread | T01, propulsion-systems and thermal engineering |
| Date | 2026-11-09 |
| Status | DONE (phase 1). Open dependencies: T03 recovery fraction (placeholder used), T04 consistent gain (not folded in), T02 exposure limits (none received) |

## A. Mission and scope

- Investigated (prompt section 3):
  1. Target-factory energy per pellet, built bottom-up, and the house fraction (REPORT 3.1). Also found that FDP-1's 12.5 targets in
     flight are not survivable, which sets the one-in-flight launcher speed.
  2. Driver loss split into seven components, each with a reject temperature (REPORT 3.2).
  3. Component circuits replacing the single warm loop, with area- and mass-weighted results and areas per circuit (REPORT 3.3, RESULTS.md).
  4. Driver-efficiency cases 0.25 / 0.30 / 0.45 on V1 and V2, Atlas and split, with gain cliffs (REPORT 3.4).
  5. Hot power electronics, capacitors and core materials: demonstrated vs projected (REPORT 3.5).
  6. Radiator architectures per circuit (REPORT 3.6).
  7. Trade-offs, quantified (REPORT 3.7).
  8. Compounding, overlap, conflicts and single booking (REPORT 3.8).
- Deliberately excluded, and why:
  - Recovery physics (T03 owns it).
  - Target design and gain (T04).
  - Dust exposure (T02).
  - Any calculator change: injection rate is run through the existing `max_rep_Hz` input, and the proposal goes to T00.
  - Transient and coast thermal behaviour: the closure is a burn-average model.
  - Driver core mass model: flagged as an EXTRAPOLATION, not built.

## B. Repository state

| Item | Value |
| --- | --- |
| Starting commit (Phase 1 base) | `8de3ffa189b47ce9a1212b550b7ea75f8c36314a` |
| Branch | `claude/project-thread-93sqqi` |
| Resulting commit | the commit that adds this file (see `/mnt/project-files/vertex/threads/T01.md`); EARLY at `57fe625` |
| Changed paths | `lab/variants/vertex-drive/studies/thermal/` only: `split.py`, `ledger.json`, `RESULTS.md`, `EARLY.md`, `REPORT.md`, `HANDOFF.md`, `registry_proposal.toml` |
| Rerun | `python3 lab/variants/vertex-drive/studies/thermal/split.py` (about 5 min on 4 cores; `--quick` skips the gain cliffs, about 1.5 min). It rewrites `ledger.json` and `RESULTS.md`; only `secs` and `runtime_s` differ between runs |

## C. Research findings

### Published evidence

- Ti-water heat pipes reach about 500-550 K. The 450-700 K band is poorly characterised. A halide/AlN radiator is estimated at
  5.2 kg/m2. NASA's goal is 2-3 kg/m2 at 500-600 K. (S-T01-TFAWS-2024, S-T01-NASA-ITHP; SECONDARY_VERIFIED)
- Tube-and-fin heat-pipe radiators are 5-10 kg/m2. A tin droplet sheet is about 0.1 kg/m2 for the sheet alone. Liquid-metal
  emissivity is 0.1-0.2. Tin works from 505 to 1,000 K. (S-T01-LDR-PATENT, S-MATTICK-LDR; SECONDARY_VERIFIED)
- Core loss is the primary induction-linac loss; pulser efficiency is 50-75 %. (S-T01-HIF-EFF; SECONDARY_VERIFIED)
- SiC power modules run continuously at a 523 K junction. SiC MOSFETs fail within 300 h at 573 K. SiC logic ICs have run over a year at
  773 K. (S-T01-SIC-250C, S-NASA-SIC-500C; SECONDARY_VERIFIED)
- Pulse capacitors are rated to 473 K. (S-T01-CAP-200C; SECONDARY_VERIFIED)
- HITPERM holds its magnetisation to about 1,250 K, but its core loss is reported only at room temperature. (S-T01-HITPERM;
  SECONDARY_VERIFIED)
- 1.8 K refrigeration costs about 1 kW/W (0.15 of Carnot); the best plants reach 28.5 % of Carnot. (S-T01-CRYO; SECONDARY_VERIFIED)
- IFE targets cost about 0.17 USD each, which bounds the energy per target at no more than about 7.6 MJ. (S-T01-IFE-TARGET-COST;
  SECONDARY_VERIFIED)

### Calculated results

All from `split.py`, with the case names in `ledger.json`:

- The house load is 0.012-0.014 % of fusion (conservative) and 0.003-0.005 % (advanced). Case `V1_house_bottomup_*`. It is set by the
  per-pellet energy divided by the 81 GJ yield.
- The equivalent warm loop is 628 K in the advanced case and 489 K in the conservative case. Cases `S1_advanced_*` and `S1_cons_T_*`.
- Split advanced comes to 9,702 t, 12,654 t and 15,473 t at driver efficiencies 0.45, 0.30 and 0.25, with wing tips of 460 m,
  1,088 m and 1,688 m and gain cliffs of 769, 1,299 and 1,617.
- Split conservative does not close at any efficiency, and neither does the demonstrated case.
- V1 on 5 kg/m2 radiators is 50,589 t. V0 does not close at 2.5 kg/m2 or at 500 K.
- Planning case driver mass: 15.4 kt at 0.075 kg/kW, 19.6 kt at 0.1 and 43.7 kt at 0.15; it does not close at 0.2.
- Planning case launcher: +6.3 % at 4 km/s and +17.5 % at 2.5 km/s; it does not close at 1.5 km/s or below.
- D-04: keeping the H2 vessels adds 667 t (Atlas V1) and 809 t (split planning case).

### Engineering extrapolations

- **Driver-loss shares** (cores 45 %, modulators 30 %, dumps 8 %, storage 5 %, busbars 5 %, ion source 4 %, cryoplant 3 %). These rest
  on the HIF ranking only. A driver design with a component loss budget would confirm or replace them.
- **Factory per-pellet items** (REPORT 3.1 table). A target-fabrication process energy study would confirm or replace them.
- **Driver core mass.** Volt-second scaling suggests far more than 0.05 kg/kW. A core volt-second model per gallery would settle it.
- **Targets in flight do not survive the previous pulse.** This uses fluences at a distance of v/f, with sublimation as the failure
  limit. A shielded-path concept would refute it.

### Fictional assumptions

- The canon Fiji lattice card is used only as FDP-1 uses it; it gets no thermal credit.
- No Level C proposal.

### Unknowns

- Core loss of FeCo nanocrystalline material at 600-700 K (no data found).
- Sheet emissivity of a tin droplet layer (0.3-0.8 tested).
- Droplet collection loss under dust impact (T02).
- Driver mass per W.
- Whether a field-sheltered target path exists (T03).
- Consistent target gain (T04).

### Negative results

- The 700-800 K warm loop of V1/V2 does not survive booking: it is 628 K even on TARGET parts.
- Near-term and demonstrated components do not close the ship.
- The Atlas warm areal mass (1.0 kg/m2) is a TARGET in V0 as well.
- FDP-1's 400 m/s train of 12.5 targets is not physical.
- The optimistic cryo factor (15 W/W rejected at 600-800 K) violates Carnot, although its effect is negligible.
- Hot cryoplant rejection costs 2.4x input power.
- A hotter warm loop is worth much less once the house is small, so the Atlas generations overlap.

## D. Quantitative effects

| Quantity | Value | Unit | Uncertainty / range | Label | Source |
| --- | --- | --- | --- | --- | --- |
| House load, conservative | 1.23e-4 | of fusion | 1.2-1.4e-4 across cases | MODEL | `V1_house_bottomup_cons`, S-T01-IFE-TARGET-COST |
| House load, advanced | 2.6e-5 | of fusion | 2.6-5.4e-5 | TARGET | `V1_house_bottomup_adv`, `S1_advanced_*` |
| Factory energy per pellet | 8.6 / 0.6 | MJ | conservative / advanced | EXTRAPOLATION / TARGET | REPORT 3.1 |
| Equivalent warm T, advanced | 628 | K | 577-679 (emissivity 0.3-0.8, panels) | TARGET | `S1_advanced_eta0.30`, `S1_adv_*` |
| Equivalent warm T, conservative | 489 | K | | EXTRAPOLATION | `S1_cons_T_*` |
| Departure, split advanced, eta 0.45 / 0.30 / 0.25 | 9,702 / 12,654 / 15,473 | t | | MODEL (TARGET inputs) | `S1_advanced_eta*` |
| Warm area, same | 0.222 / 0.547 / 0.857 | km2 | | MODEL | same |
| Wing tip radius, same | 460 / 1,088 / 1,688 | m | | MODEL | same |
| Hot area, same | 0.033 / 0.043 / 0.053 | km2 | | MODEL | same |
| Gain cliff, same | 769 / 1,299 / 1,617 | 1 | bisection 9 steps | MODEL | `gain_cliffs` |
| Atlas V1 wing tip at eta 0.45 / 0.30 / 0.25 | 653 / 1,124 / 1,537 | m | | MODEL | `V1`, `V1_eta*` |
| Atlas V2 wing tip at eta 0.45 / 0.30 / 0.25 | 356 / 570 / 737 | m | | MODEL | `V2`, `V2_eta*` |
| One-in-flight launcher speed | 4.7-7.5 | km/s | by case | MODEL | `injection_speed_m_s` |
| Mass penalty, launcher 4.0 / 2.5 km/s | +6.3 / +17.5 | % | | MODEL | `S1_advanced_eta0.30_vinj*` |
| X-ray / plasma fluence on the next target at 400 m/s | 5.3e6 / 4.6e8 | J/m2 | | MODEL | REPORT 3.1 |
| V1 on 5 kg/m2 warm panels | 50,589 | t | | MODEL | `V1_areal_by_band_700K` |
| Cryoplant input multiplier, reject 700 K vs 300 K | 2.38 | 1 | 10 K cold end | MODEL (Carnot) | split.py `carnot_scale` |
| Induction-core share of warm area | 39 | % | planning case | MODEL | `S1_advanced_eta0.30` circuits |
| Driver mass per W for closure (planning case) | < 0.2 | kg/kW | closes at 0.15 (43.7 kt) | MODEL | `S1_advanced_eta0.30_drvkg*` |
| Driver loss share of warm heat | 75-95 | % | | MODEL | circuits |

## E. Model and geometry implications

- **Architecture.** Warm heat is driver-dominated. The warm radiator is decided by the induction cores (640 K) and the capacitors
  (550 K), not by the power electronics. A droplet sheet is the only path to about 1 kg/m2 above 520 K.
- **For T05** (envelopes in metres, +X bow, +Z dorsal):
  - W2 wings at azimuth 0 and 180 deg, x -178.75 to +88.0, root r 10 m.
  - Planning tip r 1,088 m (warm root r 63 m, span 1,024 m); bracket 460-1,688 m.
  - Circuit bands from the root outward: 1,800 K hot band, then 1,000 K, 740 K, 700 K, 640 K and 550 K.
  - Low-loop panels about 1,000 m2 on the module.
  - One target in flight on the axis; the muzzle at the shield face, path 46.6 m.
  - Droplet-sheet option: a generator bar on the forward edge and a collector on the aft edge, with the drops flying along -x.
- **Evidence status.** Wings and bands are PARAMETRIC_PLACEHOLDER. The droplet sheet is a CONCEPTUAL_ILLUSTRATION. The injection axis
  is ENGINEERING_SUPPORTED (the constraint), though the launcher is a placeholder.
- **Changes from earlier figures.** Remove the FDP-1 pellet train. Replace the Atlas V1 653 m wing with the planning case.

## F. Dependencies

| Needed from | What | Status (received at commit / placeholder used) |
| --- | --- | --- |
| T03 | recovery fraction, coil cryogenic loads | placeholder: Atlas recovery efficiency 0.95, its loss in the hot loop; coil static leak 10 kW assumed |
| T04 | target designs, energy per pulse, consistent gain, injection | T04 EARLY at `1b85941` read via the board: an independent one-in-sky injection constraint (4.6 km/s V1) agrees with T01; the gain-consistency finding (V1 59-97 kt) is not folded in |
| T02 | radiator exposure and retraction constraints | not received; T01 published wing envelopes in EARLY.md |
| T05 | ISSUES.md | not in this launch |

## G. Decisions

- **Existing register.** These are recommendations only.
  - D-04: reported both ways (+667 t Atlas, +809 t split).
  - D-05: wings researched as experimental geometry only. The split planning case needs a wing of about 1.1 km.
  - D-08: not touched.
- **Proposed new decisions** (`registry_proposal.toml`):
  - **D-T01-1.** Generations should claim the booked equivalent warm temperature (about 630 K on TARGET parts) instead of 700/800 K.
    Recommendation: yes. Decided by T00 and ApeDevil.
  - **D-T01-2.** The target injection speed should be a closure input (one target in flight), through a calculator change proposal.
    Recommendation: yes. Needs owner approval.
- A recommendation is not an owner approval.

## H. Validation

- **Checks run on this branch:**
  - `python3 lab/variants/vertex-drive/atlas.py validate`: 34 records, 24 sources, 29 links, 12 decisions, 0 errors.
  - `python3 lab/variants/vertex-drive/tests/test_vertex_atlas.py`: 21 tests OK.
  - `python3 -m unittest discover -s lab/variants/fdp1/tests`: 45 tests OK.
  - `python3 lab/studies/four-burn-mission/tests/test_fourburn.py`: 18 tests OK.
  - V0 through the adapter: 20,760 t (`v0_reproduces_fdp1` true).
  - Every split case: booking error below 1e-6, ledger sum 1.000000000.
  - Rerun reproduces `ledger.json` (only timings differ).
- **Note on the canon guards.** Both lab guards need a current `origin/main`. With a stale local ref (92b83f0) they fail, listing
  every file changed on `main` since then. Run `git fetch origin main` first.
- **Model limitations.** See REPORT section 6. The main ones:
  - One equivalent radiator; component shares are extrapolated.
  - Burn-average only.
  - Sources are SECONDARY_VERIFIED.
- **Unresolved failures:** none.

## I. Integration instructions for T00

1. Bring in `lab/variants/vertex-drive/studies/thermal/` as a whole. Nothing outside it changed.
2. `registry_proposal.toml`:
   - Add sources S-T01-TFAWS-2024, S-T01-NASA-ITHP, S-T01-LDR-PATENT, S-T01-HIF-EFF, S-T01-SIC-250C, S-T01-CAP-200C,
     S-T01-HITPERM, S-T01-CRYO, S-T01-IFE-TARGET-COST and S-T01-LEDGER.
   - Revise VTX-07, VTX-07A, VTX-07B, VTX-07C (physics verdict to PLAUSIBLE_FUTURE), VTX-01B and VTX-01C as listed.
   - Add T01-NEW-1 (one-in-flight launcher) and T01-NEW-2 (circuit-booked warm radiator), plus four links.
   - Add decisions D-T01-1 and D-T01-2 as OPEN proposals.
3. Generation changes proposed, each tied to its technology and basis:
   - V1 and V2: replace the warm `T_K` override (700/800 K, VTX-07A TARGET) with the equivalent radiator from the split ledger. That
     is T 628 K, areal 0.96 kg/m2 and transport 2e-6 kg/W, basis TARGET, technologies VTX-07A and VTX-07B.
   - Replace the house 5e-4 (VTX-07C TARGET) with the bottom-up value: 1.2e-4 conservative or 2.6-5e-5 advanced.
   - Carry driver efficiency 0.30 as the planning value.
   - Optionally add `max_rep_Hz` per launcher speed (T01-NEW-1) once D-T01-2 is decided.
   - This requires `convergence.py` to accept areal and transport overrides. Its `put` helper already does, so it is a
     `generations.toml` change only.
4. Conflicts with other threads:
   - **T04 gain consistency.** If adopted, every T01 mass scales up; the deciding test is the V1 gain cliff against T04's
     consistent gain.
   - **T04 target design.** A hohlraum or a lower yield per target raises the house fraction (per-pellet energy divided by yield).
   - **T03.** A recovery fraction different from 0.95 changes the electric chain. T01 credits none beyond the placeholder.
5. Re-run after integrating:
   - `atlas.py validate`, the Atlas tests, the FDP-1 tests and the four-burn tests (after `git fetch origin main`).
   - `split.py`, checking that V0 reproduces 20,760 t.
   - `convergence.py` if the generations change.

## J. Recommended next experiment

**Driver mass and loss budget from first principles (VTX-01B).**

- **Question.** What are the induction-core volt-seconds, the core mass and the per-component loss of a 27 MJ, 100-150 Hz, 9-beam Pb
  driver at 470 K and at 640 K core temperature?
- **Why this one.** It is now the steepest lever in the closure (+55 % at 0.1 kg/kW, no closure at 0.2), and it would replace T01's
  extrapolated loss shares with a design.
- **Method.** An analytic induction-linac model: energy gain per cell, pulse duration along the linac, core flux swing and loss per
  pulse versus temperature from published core-loss data. Feed it back through the existing `driver_kg_per_W` and
  `driver_efficiency` inputs.
- **Expected output.** kg/kW and the loss shares with uncertainty.
- **Cost.** One thread session.
- **Owner.** T01 phase 2, or T04 with T01.
