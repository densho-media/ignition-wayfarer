"""Feasibility gate: machine-readable geometry for T05 (T00, research only, NON-CANON).

  python3 lab/variants/vertex-drive/studies/gate/handoff.py      # writes results/t05_handoff_gate.json from the gate results

Frames: 'nozzle' = origin at the burn point, +z toward the bow (ship +X), +x the tilt plane; ship X = x_burn + z. T05 chooses the
physical azimuth of the tilt plane (the results are for any azimuth; pick it to put the leak cone between struts and wings).
"""
import math

import gate_common as G


def main():
    ax = G.read('axis_base.json'); cc = G.read('concepts.json')
    try:
        cp = G.read('coupled.json')
    except FileNotFoundError:
        cp = None
    v = ax['v4']
    a14 = cc['A1_aligned']['14']; a12 = cc['A1_aligned']['12']
    x_burn = G.v4()['x_burn']

    def ship(pt):
        return {'X_m': x_burn + pt[2], 'Y_m_in_tilt_plane': pt[0], 'Z_m': pt[1]}

    out = {'version': 'gate handoff v1 (T00 -> T05)', 'coupled_note': 'research ghost only: the coupled ships are approximations; '
           'the preferred converged case uses a relaxed spine criterion (free-free 0.2 Hz); T05 basis (cantilever 0.2 Hz) does not converge', 'status': 'MODEL, research only, NON-CANON', 'frame': __doc__.split('Frames: ', 1)[1].strip(),
           'x_burn_m': x_burn,
           'axis_channel': {
               'what': 'unstopped plasma channel of the axisymmetric V4 closure (forward field zero on the axis)',
               'half_angle_deg': ax['baseline']['leak_half_angle_deg'],
               'half_angle_band_deg': [min(x['leak_half_angle_deg'] for x in ax['anisotropy'].values()),
                                       max(x['leak_half_angle_deg'] for x in ax['anisotropy'].values())],
               'band_note': 'angular plasma profiles from oblate P2 -0.25 to a x5 forward jet; isotropic 3.5 deg',
               'shield_angular_radius_deg': ax['baseline']['shield_angular_radius_deg'],
               'centre_fluence_J_cm2_at_shield': ax['baseline']['centre_fluence_J_cm2'],
               'keep_out_recommendation_deg': 4.0,
               'note': 'T05 6 deg keep-out = shield angular radius (6.37 deg), not a plasma result. The plasma channel is 3.5 deg '
                       '(3.0-4.7 for plausible profiles, 6.35 for a strong forward jet). Inside it the face takes the full free-expansion '
                       'fluence whatever its width.'},
           'lanes': {
               'A1_tilted_closure_RETAINED': {
                   'status': cc['chosen']['status'], 'tilt_C1_C2_deg': 14.0, 'nozzle_turn_deg': a14['nozzle_turn_deg'],
                   'loops': [{**L, 'centre_ship': ship(L['centre_m'])} for L in a14['loops_geometry']],
                   'leak_cone': {'centre_polar_deg': a14['footprint']['centre_polar_deg'], 'centre_azimuth_deg_in_tilt_frame': 0.0,
                                 'radius_deg': a14['footprint']['radius_deg'], 'share_of_plasma': cc['chosen']['leak_share_of_plasma'],
                                 'GW': cc['chosen']['leak_share_of_plasma'] * v['E_plasma_J'] * v['rate_Hz'] / 1e9,
                                 'fluence_J_cm2_at_d': {f'{d}': v['E_plasma_J'] / (4 * math.pi) / (d * 100) ** 2 for d in (65, 100, 200, 400, 650)},
                                 'rays_polar_azimuth_deg': a14['footprint']['rays_polar_azimuth_deg']},
                   'C1_conductor_min_polar_deg': a14['C1_conductor_min_polar_deg'], 'shield_rim_polar_deg': a14['shield_rim_polar_deg'],
                   'shadow_cone_limit_deg': 7.5,
                   'coupling_conflict': 'works only while the shadow cone stays at or below about 7.5 deg; the converged coupled ships (wide '
                                        'tank farm) need 9.4 deg (shield radius 11.4 m), which puts the moved leak back on the shield rim',
                   'asks': ['ray-cast the leak cone (rays list) against the FULL ship (canon parts included) over a sweep of the tilt-plane '
                            'azimuth; report the clear azimuth windows and the parts hit',
                            'check the tilted C1 envelope against the shield rim, the loop-1 strut feet and the beam ports (C1 conductor '
                            'comes to 8.7 deg polar, the rim is at 6.37 deg)',
                            'draw the 2.7 deg nozzle turn relative to the ship axis'],
                   'twelve_deg_alternative': {'nozzle_turn_deg': a12['nozzle_turn_deg'], 'leak_centre_polar_deg': a12['footprint']['centre_polar_deg'],
                                              'leak_radius_deg': a12['footprint']['radius_deg'], 'note': 'grazes the shield rim; not retained'}},
               'E_shadow_coil_REJECTED': {'what': 'axisymmetric coil behind the shield: narrows the channel, does not remove it',
                                          'rows': [{k: r[k] for k in ('current_MA', 'coil_radius_m', 'coil_z_m', 'leak_half_angle_deg', 'leak_W',
                                                                       'hoop_tension_MN', 'axial_force_from_main_MN')} for r in cc['E']['rows']]},
               'A2_transverse_plug_REJECTED': {'what': 'coil with its axis across the nozzle axis behind the shield',
                                               'rows': [{k: r[k] for k in ('current_MA', 'coil_radius_m', 'centre_z_m', 'shield_share',
                                                                            'static_torque_MN_m', 'stored_J')} for r in cc['A2']['rows']]},
               'B_target_cap_RESEARCH_ONLY': {'what': 'forward cap on the target; sits in the driver-beam path (T04 target physics)'},
               'C_twin_splayed_nozzles_OPEN': {'what': 'two nozzles splayed about the ship axis; a different architecture, not evaluated as a ship'},
               'S_centre_insert_REJECTED': {'what': 'sacrificial or renewable shield-centre insert', 'reduction_needed_x': cc['S']['reduction_needed_x']}}}
    if cp:
        pick = next((c for c in cp['cases'] if c['label'] == 'full: + spine free-free 0.2 Hz (upper bound), rate free' and c.get('summary')), None)
        out['coupled_ship'] = {'preferred_case': pick['label'] if pick else None, 'status': pick['status'] if pick else None,
                               'summary': pick.get('summary') if pick else None, 'coils': pick.get('coils') if pick else None,
                               'spine': {k: pick['spine'][k] for k in ('farm', 'basis', 'longeron_ring_m', 'tube_r_m', 'added_t', 'length_m', 'shield')}
                               if pick and pick.get('spine') else None,
                               'launcher': pick.get('launcher') if pick else None, 'all_cases': [{k: c.get(k) for k in ('label', 'status', 'iterations')}
                                                                                               for c in cp['cases']]}
    G.write('t05_handoff_gate.json', out)
    print('written', list(out['lanes']))


if __name__ == '__main__':
    main()
