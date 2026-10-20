"""SIM-026 / owner NEXT ACTION 3 (2026-10-11 16:45): the measured inputs Claude supplies back to the owner calculation workbooks for
R-01..R-07. READBACK only: every value is a model measurement or a source value already in the spec, labelled with its basis; every
quantity the model does not have stays null (the Sheets own the physics, 45 I-24..I-27, 09 OD-034..OD-039). Pure, writes Markdown + JSON.

    python3 src/wayfarer/studies/sheets_inputs.py
"""
from pathlib import Path
import json
import math
import sys
ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT/'src/wayfarer'), str(ROOT/'src/wayfarer/studies')]
from spec import load
import radiator_expansion as rx
import rotor_interface as ri

OUT_JSON = ROOT/'references/p1_sheets_inputs.json'
OUT_MD = ROOT/'references/SHEETS_INPUTS_2026-10-11b.md'
G15 = 1.5*9.80665


def J(p):
    return json.loads((ROOT/'references'/p).read_text())


def sp11():
    r = J('p1_eva_sp11.json')['sliding_plug']['retention']; g = r['geometry']; n = g['dog_count']
    return dict(for_='R-01 / OD-034 (15!A145, 45 I-24)', basis='STUDY geometry, references/p1_eva_sp11.json sliding_plug.retention (PROTOTYPE)',
                values=dict(bore_d_m=2*g['bore_r_m'], leaf_outer_d_m=2*g['leaf_r_m'], seat_band_m=g['seat_band_m'], seal_line_d_m=g['seal_line_d_m'],
                            dog_count=n, dog_angles_deg=[round(360.0*i/n, 1) for i in range(n)], dog_w_m=g['dog_w_m'], dog_h_m=g['dog_h_m'],
                            dog_stroke_m=g['dog_stroke_m'], keeper_ledge_h_m=g['ledge_h_m'], dog_bearing_area_each_cm2=round(g['dog_w_m']*g['dog_stroke_m']*1e4, 1),
                            dog_pitch_circle_d_m=round(2*g['leaf_r_m'], 3), loads_80kpa_kN=r['loads_kn']),
                open=dict(design_dp_kpa=None, design_factor=None, dog_allowable_N=None, seal_seat_diameter_m=None, lever_force_N=None, unlatch_dp_kpa=None))


def hoist():
    h = J('p1_hum003.json'); car = h['carriers']; hz = h['local']['hoist']
    cases = []
    for k, c in car.items():
        dims = c.get('size') or [c['length'], 2*c['radius'], 2*c['radius']]
        cases.append(dict(carrier=k, name=c['name'], envelope_m=dims, kit_envelope_m=c.get('kit'), patient_mass_kg=220.0 if k == 'S' else 75.0,
                          patient_static_N_at_1_5g=round((220.0 if k == 'S' else 75.0)*G15, 1), carrier_mass_kg=None, kit_mass_kg=None, attendant_mass_kg=None))
    return dict(for_='R-04 / OD-036 (15!A148, 45 I-14/I-15/I-26)', basis='PROTOTYPE carrier envelopes (references/p1_hum003.json carriers); patient masses are the DYN-024 '
                'test fixtures (75 kg IVA, 220 kg suited), 1.5 g = 14.71 N/kg (15!A148)',
                geometry=dict(trunk_ladder_deg=hz['ladder_deg'], guide_deg=hz['guide_deg'], ladder_x_m=hz['ladder_x'], guide_rail_clear_spans_x_m=hz['guide_rail_clear_spans_x'],
                              line_offsets_studied_m=sorted({v['offset_m'] for c in hz['offsets'].values() for v in c.values()}),
                              vertical_run_m=round(hz['ladder_x'][1]-hz['ladder_x'][0], 2)),
                cases=cases, open=dict(carrier_mass_kg=None, kit_mass_kg=None, rated_line_tension_N=None, dynamic_factor=None, brake_decel_m_s2=None,
                                       guide_friction=None, capstan_advantage=None))


def locks(s):
    out = []
    for q in ri.ring_stop_locks(s):
        out.append(dict(name=q['name'], rotor=q['rotor'], angle_deg=round(math.degrees(q['angle']) % 360, 2), x_m=round(q['x'], 4), rod_radius_m=q['radius']))
    r = s['rotor_interface']; rd = s['physics']['rotor_dynamics']
    return dict(for_='R-05 / OD-037 (15!A149, 16!D12)', basis='PROTOTYPE lock placements from rotor_interface.ring_stop_locks (one per crew-spoke angle)',
                pins=out, stationary_inner_radius_m=r['stationary_inner_radius_m'], pin_outer_radius_m=r['ring_lock_pin_outer_radius_m'],
                ring_mass_kg=rd['mass_each_kg'], inertia_kg_m2=rd['inertia_each_kg_m2'], omega_rad_s=rd['omega_rad_s'],
                axial_load_1_5g_N=round(rd['mass_each_kg']*G15, 0), spokes=dict(per_ring=s['habitat']['spokes']['per_ring'], crew=s['habitat']['spokes']['crew'], spacing_deg=s['habitat']['spokes']['spacing_deg']),
                open=dict(pin_diameter_m=None, pin_stroke_m=None, engagement_tolerance=None, pin_rating_N=None, stop_time_s=None, reindex_at_1_5g='NOT ALLOWED (CALC-R05)'))


def reserve():
    d = J('p1_eclss_rec2.json')['reserve']
    return dict(for_='R-03 / OD-035 (15!A147, 45 I-25)', basis='packaging space on each rotor drum (references/p1_eclss_rec2.json reserve); NOT a vessel volume or gas capacity',
                rings={k: dict(rotor_x_m=round(v['rotor_x_m'], 3), u_m=v['u_m'], x_m=v['x_m'], r_m=v['r_m'], segments_deg=v['segments_deg_ring_local'],
                               segment_width_deg=v['segment_width_deg'], envelope_m3=v['envelope_m3'], to_sector_floor_m=v['distance_to_sector_floor_m'])
                       for k, v in d.items()},
                open=dict(gas_species=None, tank_volume_m3=None, tank_pressure_kpa=None, gas_mass_kg=None, imbalance_kg=None, flow_kg_s=None, r4_supply=None))


def radiator(s):
    g = rx.geometry(s); n = s['radiators']['count']; ph = s['prototype']['radiator_phase_deg']
    seams_as_built = [g['seam']]*9; seams_cand = [0.20]*8+[0.30]
    span = g['width']-g['band']
    return dict(for_='R-07 / OD-039 (15!A151, 40!A87:F95)', basis='built blade (radiator_expansion.geometry) and the RAD-004 candidate seams',
                blades=dict(count=n, azimuths_deg=[(ph+360.0*k/n) % 360 for k in range(n)], length_m=round(g['frames'][-1]-g['frames'][0], 3), span_m=g['width'],
                            root_band_m=g['band'], frames_x_m=[round(x, 3) for x in g['frames']], bays=g['bays'], datum_x_m=round(g['datum_x'], 3),
                            sheet_depth_m=g['sheet_depth'], truss_depth_m=g['truss_depth'], slide_travel_m=g['travel']),
                seams=dict(as_built_m=seams_as_built, candidate_m=seams_cand, extra_axial_per_blade_m=round(sum(seams_cand)-sum(seams_as_built), 4),
                           extra_raw_both_faces_m2=round((sum(seams_cand)-sum(seams_as_built))*span*2*n, 3), emitting_span_m=span),
                open=dict(alpha_T=None, E_T=None, truss_temperature_map=None, coating=None, cyclic_stress=None, front_post_sizing=None))


def run():
    s, *_ = load(ROOT)
    return dict(status='READBACK / measured inputs for owner calculations; unknowns null; no rating, no release (47 SIM-026)',
                sp11=sp11(), hoist=hoist(), ring_stop_locks=locks(s), r1_reserve=reserve(), radiator=radiator(s))


def md(r):
    L = ['# Measured inputs for the owner calculation workbooks (SIM-026, 2026-10-11)', '',
         f"{r['status']}. Code `src/wayfarer/studies/sheets_inputs.py`, data `references/p1_sheets_inputs.json`. Null = the Sheets own it.", '']
    for key, title in (('sp11', 'SP-11 seat, leaf and dogs'), ('hoist', 'Hoist load cases'), ('ring_stop_locks', 'Ring-stop locks'),
                       ('r1_reserve', 'R1 reserve packaging'), ('radiator', 'Radiator blades and seams')):
        x = r[key]; L += [f'## {title} ({x["for_"]})', '', f'Basis: {x["basis"]}.', '', '```json',
                          json.dumps({k: v for k, v in x.items() if k not in ('for_', 'basis')}, indent=1), '```', '']
    return '\n'.join(L)


if __name__ == '__main__':
    r = run(); OUT_JSON.write_text(json.dumps(r, indent=1)+'\n'); OUT_MD.write_text(md(r))
    print('locks', len(r['ring_stop_locks']['pins']), 'radiator extra m2', r['radiator']['seams']['extra_raw_both_faces_m2'], 'hoist cases', len(r['hoist']['cases']))
    print(OUT_JSON, OUT_MD)
