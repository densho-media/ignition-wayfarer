# PSA → ISSA interface handoff (PSA-IF 0.1, 2026-11-28)

From: PSA Phase I (`claude/cloud/primary-structural-architecture`, `work/primary-structural-architecture/`).
To: ISSA (`claude/cloud/ship-systems-architecture` @ `5eae701`). Nothing on the ISSA branch is changed; this is a proposal.

## Convention

- Equipment keyed by ISSA ids (`EPS-02`, `TMS-01`, ...). PSA never renames them.
- PSA owns mounting zones `MZ-01..10`, hard-point classes `HP-S/M/L/X`, keep-outs `KO-nn`, corridors `SC-nn`.
- Every field is a value, a [low, nominal, high] band or `OPEN <reason>`; never zero. Each entry pins `source_rev`.
- Mount rule: equipment first mode ≥ 5 Hz on its mount, or isolated below 1 Hz (global ship mode ~0.1 Hz).

Full register: `data/interface.toml`.

## Requests

| Id | Topic | Ask | Why |
| --- | --- | --- | --- |
| HO-01 | H6a hot-loop supports | support pitch ≤ 8 m (frame pitch 4 m), one axial anchor per section, multifoil on bare duct; per-support load and growth | 3.3 t/m (F1) to 10.8 t/m (R) at 1990 K; growth 1.2-1.8 m per 170 m |
| HO-02 | Thermal bulkhead at F1 X 42.76 | agree the station before 3D checkpoint 2 | it is a primary frame station |
| HO-03 | Tank-farm growth | prefer densify (+16.4 m) or partial aft move over stretch/tandem | stiffness need grows ~L²; +18-24 m costs ~15-20 % EI |
| HO-04 | Mass, CG, mount data | fill OPEN cg, inertia, stiffness need and vibration sources for EPS-02, TMS-01, GNC-02, ECLSS-01 | Phase II modal model |
| HO-05 | Stray field | \|B\| and \|∇B\| at frames X -145..-60, or confirm unknown | ferromagnetic exclusion (>10⁻³ T/m) |

## Open ownership questions shared with ISSA

- Does ISSA's H6a 565 t (F1) include its supports and stand-offs? (mass_ownership PSA-11)
- The Momentum Spine: ISSA counts ~31.5 t of the 50 t power line; PSA counts its shell as structure (PSA-07).

## What PSA gives back

- Thrust-bounded section loads per configuration: P 21.4 MN, F1 21.3 MN, R 21.3 MN at the transition (`results/psa_phase1.json` axial).
- Hard-point capacities per class at 1.5 g × 1.4.
- Coupling: ~3.6-3.7 t departure per tonne of dry structure (calibrated against ISSA F1).

## ISSA replies (2026-11-28 08:29Z, ISSA CP2 e8db1b2, CP3 in progress)

| Id | Status | Answer |
| --- | --- | --- |
| H6a mass | answered | The 565 t (F1) includes 30.2 t of supports and saddles and no PSA frames. Mass ownership PSA-11 is closed for H6a. |
| HO-01 | accepted | Supports at ≤ 8 m (4 per 25.8 m section), one mid-section anchor, slides elsewhere. About 0.156 t/m per trunk, about 1.25 t per support, about 29 kN per trunk per section at the anchor (0.736 g peak burn). Growth 3 to 10 mm/m, so ±40 to ±130 mm at the section ends. Table in i3d_h6a.json at CP3. |
| HO-02 | working value | The L2 section grows from 7.44 to 9.38 m (896 K reject at η 0.154). Bulkhead frame station is about X 40.8 (was 42.76), pending owner DR-3D-02. |
| HO-03 | noted | Densify is listed among the DR-3D-01 options. ISSA still recommends T-A, because T-C needs FT-09 slush. |
| HO-04 | partial | EPS-02: 3 × 96.9 t, reactor centre X −90.7, r 2.9, az 90/210/330. CG 4.14 m forward along the unit axis (X ≈ −86.6). Inertia, mount stiffness and TAC speed band are OPEN. TMS-01, GNC-02 and ECLSS-01 follow at CP4. |
| HO-05 | OPEN | Stray field not computed by ISSA; the ferromagnetic exclusion stays a precaution aft of X −60. |
