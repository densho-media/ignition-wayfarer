"""Write the machine-readable T00 -> T05 Revision 4 handoff (results/t05_handoff_rev4.json at the Vertex entry, the agreed path).

  python3 lab/variants/vertex-drive/studies/rev4/handoff.py      # after ledger.py, injection.py, durability.py, spine.py

Every number is copied from this folder's result files; nothing is computed here except unit changes. NON-CANON research geometry.
"""
import json
import subprocess

from common import HERE, VX, read_json

VERSION = 1


def main():
    lg, inj, dur, sp = (read_json(n) for n in ('ledger.json', 'injection.json', 'durability.json', 'spine.json'))
    base = subprocess.run(['git', 'rev-parse', '--short', 'HEAD'], capture_output=True, text=True, cwd=VX).stdout.strip()
    pref = next(c for c in lg['cases'] if c['label'] == lg['preferred'])
    ray = next(c for c in lg['cases'] if c['label'].startswith('T05 Rev 4 ray cast'))
    coils = {}
    for x, cg, per in zip(pref['assembly'], lg['coils_v4']['coils'], pref['coil_heat']['per_coil']):
        coils[x['name']] = {
            'radius_m': cg['radius_m'], 'z_from_burn_m': cg['z_from_burn_m'], 'polar_deg': cg['polar_deg'], 'current_MA': cg['current_A'] / 1e6,
            'winding_minor_m': cg['winding_minor_m'], 'design_hoop_tension_GN': cg['design_tension_N'] / 1e9,
            'radial_build_m': {'winding_minor': cg['winding_minor_m'], **lg['assumptions']['layers_m']['value'],
                               'lithium_channel': lg['assumptions']['coolant_channel_m']['value'],
                               'CFC_armour': lg['assumptions']['armour_W_m']['value'],
                               'LiH_neutron_screen_burn_face': x['screen_m']},
            'projected_half_width_m': x['projected_half_width_m'], 'share_ring': x['share'], 'share_struts': x['strut_share'],
            'case': 'hoop case behind the winding (in its own shadow), TARGET composite; area m2 = ' + f"{x['case_area_m2']:.2f}",
            'struts': {'count': 6, 'width_m': x['strut_width_m'], 'length_m': x['strut_length_m'], 'to': 'shield rim' if x['name'] == 'C1' else 'C1'},
            'masses_t': x['masses_t'],
            'cooling_W': {'armour_hot_1800K': per['armour_hot_W'], 'back_face_leak_warm': per['back_face_leak_warm_W'],
                          'neutron_screen_warm': per['neutron_screen_warm_W'], 'shield_80K': per['shield_80K_W'],
                          'winding_20K': per['winding_20K_W'], 'cryoplant_input_electric': per['cryo_input_W']},
            'neutron_fluence_n_cm2_unshielded': x['mission_fluence_n_cm2']}
    cand = {c['label']: c for c in inj['candidates'] if 'kinematics' in c}
    bm = next(c for c in inj['candidates'] if c['label'].startswith('B-modified'))
    surfaces = {}
    for sname in ('shield face and coil armour', 'snout tip (launcher B)'):
        rows = [r for r in dur['rows'] if r['surface'] == sname]
        surfaces[sname] = {'steady_MW_m2': dur['cooling'][sname]['steady_MW_m2'],
                           'max_armour_mm': {k.replace('max_armour_mm_', ''): v for k, v in dur['cooling'][sname].items() if k.startswith('max_')},
                           'verdicts': {f"{r['material']} | {r['band']}": r['verdict'] for r in rows}}
    sz = {f"{s['layout']} bow {s['bow_t']:.0f} t": {k: s[k] for k in ('tube_r_m', 'added_structure_t', 'structure_t', 'f1_cantilever_Hz',
                                                                        'f1_free_free_Hz', 'buckling_factor_SF2', 'longeron_buckling_margin')}
          for s in sp['sizing_for_0.2Hz']}
    v4 = lg['v4']['summary']; cp = pref['coupled']['summary']
    out = {
        'version': VERSION, 'from': 'T00', 'to': 'T05', 'base_commit': base,
        'published_in': 'the commit that adds this file on claude/project-thread-9rsgog (git log -- lab/variants/vertex-drive/results/t05_handoff_rev4.json)',
        'status': 'NON-CANON research geometry; numbers MODEL / PROTOTYPE as labelled in studies/rev4/results/*.json',
        'coils': coils,
        'coil_totals': {'preferred_case': lg['preferred'], 'share_total': pref['share'], 'intercepted_W': pref['coil_heat']['xray_W'] + pref['coil_heat']['neutron_W'],
                        'hot_W': pref['coil_heat']['hot_W'], 'warm_W': pref['circuits']['warm_added_W'], 'cryo_input_W': pref['coil_heat']['cryo_input_W'],
                        'pump_electric_W': pref['coil_heat']['pump_electric_W'], 'li_flow_m3_s': pref['coil_heat']['li_flow_m3_s'],
                        'coolant': 'lithium loop, 1,500 -> 1,800 K, 1 MPa, EM pumps, Li/Sn exchanger at the hot-radiator root (T05 Rev 4 plant)',
                        'cooling_mass_t': {k: (v / 1e3 if isinstance(v, (int, float)) else [w / 1e3 for w in v]) for k, v in pref['cooling_mass'].items()
                                           if k.endswith('_kg')},
                        't05_ray_cast_case': {'share': ray['share'], 'other_share': ray['other_share'],
                                              'intercepted_W': ray['coil_heat']['xray_W'] + ray['coil_heat']['neutron_W'],
                                              'other_hw_W': ray['coil_heat']['other_hw_W'], 'coupled_departure_t': ray['coupled']['summary']['departure_t']}},
        'ship_consequence': {
            'answer_to_T05_question_B': 'more propellant: the coupled solve re-sizes the whole ship, so propellant and tanks grow with the dry mass',
            'V4': {k: v4[k] for k in ('departure_t', 'propellant_t', 'tank_t', 'fusion_TW', 'pellet_rate_Hz', 'wing_tip_radius_m')},
            'coupled_preferred': {k: cp[k] for k in ('departure_t', 'propellant_t', 'tank_t', 'fusion_TW', 'pellet_rate_Hz', 'wing_tip_radius_m')},
            'propellant_ratio': cp['propellant_t'] / v4['propellant_t'],
            'tank_stretch_length_m_if_same_section': 275.4 * cp['propellant_t'] / v4['propellant_t'],
            'note': 'COUPLED APPROXIMATION, not a converged spacecraft design. Draw it as a labelled envelope (ghost), keep V4 as the drawn '
                    'baseline. The rate rises to about 312 Hz unless capped; capped at 196 Hz the same ship is 91 kt (injection.json).'},
        'launcher': {
            'recommended_for_blender': 'B-modified geometry (B kinematics) as the preferred lane, labelled TARGET PHYSICS UNPROVEN; B and B-long '
                                       'kept as labelled failed lanes; no fewer-larger-pulse lane (does not fit or does not close)',
            'B_modified': {k: bm['kinematics'][k] for k in ('rate_Hz', 'open_flight_m', 'muzzle_m_s', 'accel_g', 'accelerator_m', 'launch_ms',
                                                            'target_kg', 'sabot_kg', 'electric_W', 'sabot_catcher_W', 'launcher_kg', 'tip_xray_J_cm2')},
            'target': next(c for c in inj['target_classes']['classes'] if '30 K, HDC' in c['class']),
            'type': 'contactless coilgun (linear induction); railgun life cannot reach 1e10 shots',
            'sabot': 'split EM armature sabot, stripped magnetically before the snout; catcher in the shadow cone takes the sabot energy',
            'shutter': inj['b_requirements']['shutter'], 'alignment': {k: v for k, v in inj['b_requirements'].items() if k not in ('shutter',)},
            'mounting': 'own kinematic straight rail, actively aligned; not a primary spine member (thermal bow of the stretch 0.4-2 mrad)',
            'axis_field_T': inj['axis_field_summary'], 'axis_plasma': inj['axis_plasma'],
            'verdicts': {k: c['verdict'] for k, c in cand.items()}},
        'surfaces': {
            'recommendation': 'CFC monoblocks on Mo-TZM lithium tubes for every X-ray face (shield rim, coil armour, snout cartridge sides): '
                              'the only solid that survives every spectrum band at 4.0 and 8.3 J/cm2. W, Mo and SiC fail for spectra '
                              'at or below 10 keV. A renewable liquid-Li surface is the only option for the snout tip face if CFC '
                              'neutron damage or the axis plasma rules it out',
            'thickness_mm': {'shield_face_and_coil_armour': 5.0, 'snout_tip': 2.5},
            'replacement': 'cartridges: the snout tip on a magazine (CFC face, 2.5 mm, exchanged at the axis-plasma rate; see axis_plasma); coil armour '
                           'and shield rim by sector at maintenance stops (neutron conductivity loss of CFC, not erosion, sets the interval)',
            'axis_plasma_blocker': dur['plasma_on_axis']['finding'], 'per_surface': surfaces},
        'spine': {'recommended': 'N9 in the inter-tank gaps at R 31 m, tube r 0.61 m t/r 0.1 (cantilever-sized for 0.2 Hz at 300 t bow)',
                  'sizing': sz, 'frames': 'ring frames every 7.65 m need spokes or tie rods to the keel hub: a free ring frame (r 0.15 m tube) '
                                          'ovalises at 0.14 Hz, inside the requirement band',
                  'lacing': 'diagonal lacing in every bay panel (0.25 x longeron area) is part of the stiffness; without it shear governs',
                  'joints': {'J1': next(r for r in sp['rows'] if r['geometry'] == 'N9_gaps' and r['bow_t'] == 300 and r['fill'] == 1.0)['J1'],
                             'J3': next(r for r in sp['rows'] if r['geometry'] == 'N9_gaps' and r['bow_t'] == 300 and r['fill'] == 1.0)['J3']},
                  'tank_saddles': sp['requirements']['tank_saddle'], 'independence': sp['independence'], 'keel_loss_f1_cantilever_Hz': sp['keel_loss']},
    }
    p = VX / 'results/t05_handoff_rev4.json'
    p.write_text(json.dumps(out, indent=1, default=float) + '\n')
    print(p)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
