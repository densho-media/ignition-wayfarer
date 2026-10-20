"""SP-52 warm module next to the workshop wall: bounded radiative sensitivity (owner 2026-10-13, S&E 15!A172 SP52-THERM-2026-10-13).

The owner permits "only bounded sensitivity study with explicit parameter ranges and cold/warm/hot loop separation"; the 0.756 view factor to
the workshop wall "is NOT safe"; every emissivity, insulation, wall flux / temperature, dissipation and fire rating stays UNKNOWN in the owner
model, so canon keeps them known = false. This study only shows how the radiative coupling scales over explicit ranges and what geometry or
material classes change it. Nothing here is a rating, an allowable or a design value.

Inputs:
- geometry: references/p1_eva_sp13_l1a.json sp52 (measured: facing areas, geometric view factor per standoff, containment fit);
- the only owner temperature: warm module ~450 K (15!C123, G123);
- SENSITIVITY ranges chosen by Claude (explicit, labelled, not owner data): wall temperature, surface emissivity classes, radiation-shield count,
  insulation conductivity classes.

Radiation between the module face (1) and the wall patch (2): two-surface grey exchange with the measured view factor,
    q1 = sigma (T1^4 - T2^4) / ((1-e1)/e1 + 1/F + (A1/A2)(1-e2)/e2)       [W per m2 of module face]
and N thin radiation shields of emissivity es between them, each adding 2 (1-es)/es + 1 to the resistance (shields close to the face, F ~ 1 between
shield layers). Conduction and convection paths are OPEN (pressurisation, mounts, coolant routing unknown); the conduction column only reports
k (T1-T2)/t for a blanket of thickness t that the containment geometry admits, as a scale, not a path.

Owner 2026-10-13 (15!A181, answer to Doc 18:18 (f1)): carry a LOW-EMISSIVITY wall-facing finish plus ONE radiation shield as the favoured
first sensitivity case; compare no shield and additional shields / insulation. The aerogel blanket stays optional, never selected until
conduction, convection / offgas and fire / pressure are modelled; the 0.2-0.4 m standoff is not insulation; the 746 m2 warm radiator face is
not credited as full rejection. The wall finish is unknown, so the trade crosses the favoured module-face finish with each wall class.

    python3 src/wayfarer/studies/sp52_sensitivity.py        # writes references/SP52_SENSITIVITY_2026-10-13.{md,json}
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SIGMA = 5.670374419e-8
T_WARM_K = 450.0                                   # owner ~450 K (15!C123, G123)
# SENSITIVITY ranges (Claude, explicit, not owner data)
T_WALL_K = (273.0, 295.0, 320.0)                   # workshop wall face temperature span tested
EMISSIVITY = {'polished metal / low-e foil': 0.05, 'oxidised or treated metal': 0.3, 'paint / anodise / fabric': 0.9}
SHIELDS = (0, 1, 2, 3)                             # low-e radiation shields between the faces
SHIELD_E = 0.05
K_CLASSES = {'aerogel blanket class': (0.015, 0.025), 'mineral / glass wool class': (0.035, 0.045), 'polyimide foam class': (0.04, 0.06)}
LOOPS = [('cold', 'crew cabin, workshop wall and occupied surfaces', 'never a heat sink for the warm or hot loop'),
         ('warm', 'SP-52 module (~450 K owner value)', 'rejects its heat through its own coolant loop (routing OPEN); the wall coupling below is leakage to minimise, not a rejection path'),
         ('hot', 'radiator blades (1800 K class)', 'not a sink for SP-52 (owner: do not treat the hot-blade loop as sink)')]


def exchange(F, e1, e2, A1, A2, T1, T2, shields=0, es=SHIELD_E):
    r = (1-e1)/e1 + 1/F + (A1/A2)*(1-e2)/e2 + shields*(2*(1-es)/es + 1)
    return SIGMA*(T1**4-T2**4)/r


def study():
    src = json.loads((ROOT/'references/p1_eva_sp13_l1a.json').read_text())['sp52']
    rows = src['rows']; owner = rows['0.30']; fa = owner['facing']; A1, A2 = fa['warm_aft_face_m2'], fa['workshop_forward_face_m2']
    vf = {k: r['facing']['view_factor_warm_face_to_workshop_wall'] for k, r in rows.items()}
    grid = []
    for name, e in EMISSIVITY.items():
        for n in SHIELDS:
            for Tw in T_WALL_K:
                q = exchange(fa['view_factor_warm_face_to_workshop_wall'], e, e, A1, A2, T_WARM_K, Tw, n)
                grid.append(dict(surfaces=name, emissivity=e, shields=n, wall_k=Tw, flux_w_m2=round(q, 1), power_w=round(q*A1, 0)))
    ref = next(g for g in grid if g['emissivity'] == 0.9 and g['shields'] == 0 and g['wall_k'] == 295.0)
    by_standoff = {k: round(exchange(v, 0.9, 0.9, A1, A2, T_WARM_K, 295.0)/ref['flux_w_m2'], 3) for k, v in sorted(vf.items())}
    gap = 0.30-0.20                                                   # the containment fit at 0.30 m: t up to 0.20 m leaves 0.10 m of air gap
    cond = {c: dict(k_w_mk=list(k), t_m=[0.05, 0.10, 0.20],
                    flux_w_m2=[[round(kk*(T_WARM_K-295.0)/t, 0) for t in (0.05, 0.10, 0.20)] for kk in k]) for c, k in K_CLASSES.items()}
    F = fa['view_factor_warm_face_to_workshop_wall']; e_lo = EMISSIVITY['polished metal / low-e foil']
    trade = []                                                        # owner 15!A181: favoured first case = low-e module face + 1 shield
    for wall_name, ew in EMISSIVITY.items():
        for n in SHIELDS:
            q = exchange(F, e_lo, ew, A1, A2, T_WARM_K, 295.0, n)
            trade.append(dict(module_face='low-e', wall=wall_name, wall_e=ew, shields=n, favoured=(n == 1), flux_w_m2=round(q, 1),
                              power_w=round(q*A1, 0), vs_reference=round(q/ref['flux_w_m2'], 4)))
    return dict(study='SP-52 bounded radiative sensitivity (owner 2026-10-13, S&E 15!A172)', status='SENSITIVITY ONLY; canon values stay known=false',
                geometry_source='references/p1_eva_sp13_l1a.json sp52 (standoff 0.30 m owner case)',
                measured=dict(module_face_m2=A1, wall_face_m2=A2, overlap_m2=fa['overlap_m2'], view_factor=vf, containment_max_t_m_at_030=0.20, air_gap_m=gap),
                owner_value=dict(warm_module_k=T_WARM_K, source='15!C123, G123'),
                sensitivity_ranges=dict(wall_k=T_WALL_K, emissivity=EMISSIVITY, shields=SHIELDS, shield_emissivity=SHIELD_E, conductivity_classes=K_CLASSES,
                                        label='Claude SENSITIVITY ranges (typical material classes), not owner data'),
                radiation_grid=grid, owner_trade_15_a181=trade, standoff_relative_flux_e09_295k=by_standoff, conduction_scale=cond, loops=LOOPS,
                open=dict(heat_transfer_w=None, wall_temperature_k=None, emissivity=None, insulation_conductivity=None, insulation_thickness_m=None,
                          fire_barrier_rating=None, allowable_wall_flux_w_m2=None, crew_touch_limit=None, component_dissipation_w=None,
                          coolant_routing=None, convection_path=None, conduction_path=None))


def markdown(r):
    m = r['measured']; g = r['radiation_grid']
    md = ['# SP-52 warm module: bounded radiative sensitivity (owner 2026-10-13, S&E 15!A172)', '',
          'Owner: actual emissivities, insulation, allowable wall flux and temperature, dissipated heat and fire / pressure qualifications are UNKNOWN; '
          'only a bounded sensitivity study with explicit ranges and the cold / warm / hot loops kept apart is permitted; the 0.756 view factor to the '
          'workshop wall is NOT safe. Every result below is a SENSITIVITY scale, not a rating; canon keeps every value known = false. Code: '
          '`src/wayfarer/studies/sp52_sensitivity.py`; data: `references/SP52_SENSITIVITY_2026-10-13.json`.', '',
          '## Measured geometry (owner standoff 0.30 m)', '',
          f"Module aft face {m['module_face_m2']} m2, workshop forward face {m['wall_face_m2']} m2, overlap {m['overlap_m2']} m2. Geometric view factor module face to "
          f"wall: {', '.join(f'{k} m: {v}' for k, v in sorted(m['view_factor'].items()))}. At 0.30 m the containment fits up to t {m['containment_max_t_m_at_030']} m "
          f"with {m['air_gap_m']:.2f} m of air gap (references/EVA3_SP13_L1A_REDLINES.md §3).", '',
          '## Loops kept apart', '', '| loop | surfaces | rule |', '|---|---|---|']
    md += [f'| {a} | {b} | {c} |' for a, b, c in r['loops']]
    md += ['', f"## Radiative flux into the wall, per m2 of module face (owner 450 K; SENSITIVITY ranges)", '',
           'Two-surface grey exchange with the measured view factor 0.756; N low-e shields (emissivity 0.05) between the faces. W/m2 for wall 273 / 295 / 320 K.', '',
           '| surfaces (both faces) | e | shields 0 | 1 | 2 | 3 |', '|---|---|---|---|---|---|']
    for name, e in r['sensitivity_ranges']['emissivity'].items():
        cells = []
        for n in r['sensitivity_ranges']['shields']:
            v = [x['flux_w_m2'] for x in g if x['emissivity'] == e and x['shields'] == n]
            cells.append(' / '.join(f'{q:.0f}' for q in v))
        md.append(f'| {name} | {e} | ' + ' | '.join(cells) + ' |')
    ref = next(x for x in g if x['emissivity'] == 0.9 and x['shields'] == 0 and x['wall_k'] == 295.0)
    lo = next(x for x in g if x['emissivity'] == 0.05 and x['shields'] == 1 and x['wall_k'] == 295.0)
    md += ['', f"Span at a 295 K wall: painted faces, no shield {ref['flux_w_m2']:.0f} W/m2 ({ref['power_w']:.0f} W over the face) down to low-e faces with one shield "
               f"{lo['flux_w_m2']:.0f} W/m2 ({lo['power_w']:.0f} W): about {ref['flux_w_m2']/lo['flux_w_m2']:.0f}x. Surface finish and shielding dominate; the standoff "
               f"does not: relative flux at e 0.9 for standoffs {', '.join(f'{k} m: {v}' for k, v in r['standoff_relative_flux_e09_295k'].items())} (0.60 m does not fit: shield column).",
           '', '## Conduction scale through a blanket that fits (NOT a path; mounts, pressurisation and convection OPEN)', '',
           'k (450 K - 295 K) / t, W/m2, for t 0.05 / 0.10 / 0.20 m (the containment admits t up to 0.20 m at 0.30 m standoff):', '',
           '| class | k (W/m K) | low k | high k |', '|---|---|---|---|']
    for c, d in r['conduction_scale'].items():
        md.append(f"| {c} | {d['k_w_mk'][0]}-{d['k_w_mk'][1]} | {' / '.join(str(int(x)) for x in d['flux_w_m2'][0])} | {' / '.join(str(int(x)) for x in d['flux_w_m2'][1])} |")
    md += ['', '## Owner trade (15!A181, 2026-10-13): low-e wall-facing finish + one shield first', '',
           'The owner carries a low-emissivity module face toward the workshop plus ONE radiation shield as the favoured first case and compares '
           'no shield and more shields. The wall finish is unknown, so each wall class is crossed. 450 K module, 295 K wall (SENSITIVITY), W/m2 of '
           'module face (ratio to painted, unshielded):', '', '| wall class | e wall | no shield | 1 shield (favoured) | 2 shields | 3 shields |',
           '|---|---|---|---|---|---|']
    for wall_name, ew in r['sensitivity_ranges']['emissivity'].items():
        rows = [x for x in r['owner_trade_15_a181'] if x['wall'] == wall_name]
        md.append(f'| {wall_name} | {ew} | ' + ' | '.join(f"{x['flux_w_m2']:.0f} ({x['vs_reference']:.3f})" for x in rows) + ' |')
    md += ['', 'Insulation (the aerogel or wool blanket) stays an optional addition, never selected until conduction, convection / offgas and fire / '
           'pressure are modelled. The 0.2-0.4 m standoff is not insulation. The 746 m2 warm radiator face is not credited as full rejection. Needed '
           'from the owner model: emissivities, the 450 K surface, wall 295 K limits, real view factors, shield conduction mounts, pressurised '
           'convection, warm / cold coolant and transient energy. Every value here is Claude\'s scenario value only.']
    md += ['', '## Candidates returned to the owner (geometry and material classes, no rating)', '',
           '- Low-emissivity finish on the module face toward the workshop and on the workshop wall patch (largest single lever).',
           '- One or more low-e radiation shields in the 0.10 m air gap (each shield roughly halves the exchange or better at low e).',
           '- A blanket of the aerogel or wool class up to 0.20 m in the containment envelope; fire rating, outgassing, pressure and touch limits OPEN.',
           '- Standoff alone cannot fix it: 0.20 -> 0.40 m changes the view factor only 0.788 -> 0.723, and 0.60 m hits the shield column.',
           '', '## OPEN (known = false)', '', ', '.join(k.replace('_', ' ') for k in r['open'])+'.', '']
    return '\n'.join(md)


if __name__ == '__main__':
    r = study()
    (ROOT/'references/SP52_SENSITIVITY_2026-10-13.json').write_text(json.dumps(r, indent=1)+'\n')
    (ROOT/'references/SP52_SENSITIVITY_2026-10-13.md').write_text(markdown(r))
    print(markdown(r))
