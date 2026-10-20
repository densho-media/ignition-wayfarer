"""M6 hologram chapters (owner 2026-10-19: S&E 15!A220 OWN-M5-VIS, 15!A227 OWN-M6-FOCUS, 98!A121): the forward EYE / Dust Lance /
shield, the counter-rotating habitat with its spine and crew route, and the radiator blades with their loops and damage / isolation
states, added to the M5 hologram package (m5_hologram.py) over the same published COAST nodes. Pure: reads the spec, the published
manifest and rig, and the M5 comms reference; types no value.

Every number a chapter shows is a sourced, DERIVED or DIAGNOSTIC value with its status, or a CAD readback the runtime measures. What
the workbooks have not released (field strength, impact and repair rates, ring spin-down time, coolant flow, drive waste heat, heat
rejection margin) is carried as null and drawn UNKNOWN. The interactive states replay the exported display poses (the Blender drivers'
baked values) and the rotor bindings; nothing here changes a configuration, a mechanism or a physical budget.
"""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(HERE)]
import radiator_health
from spec import load, derived


def runtime(p):
    """Vehicle frame (x, y, z) -> runtime (x, z, -y)."""
    return [round(p[0], 3), round(p[2], 3), round(-p[1], 3)]


def eye(s, d, rig, shadow, states):
    fd, lance = s['forward_defense'], s['forward_defense']['dust_lance']
    ctl = rig['forward_defense']['controls']
    face_x = d['length_m']/2
    poses = [('COAST', 'WATCH', 'BASELINE', 'COAST configuration: the four EYE facets open (Quiet Watch), diversion field display on, Crown '
                                            'stowed behind the rim.'),
             ('EYE_SHUTTERS_CLOSED', 'EYELIDS CLOSED', 'IMPLEMENTATION', ctl['eye_shutter_1'].split(':')[0]+' x4: '+
              'all facets closed; the ship is blind forward until they reopen (impact rating OPEN).'),
             ('EYE_F1_JAMMED', 'F1 JAMMED', 'IMPLEMENTATION', 'Facet F1 eyelid jammed: three facets keep watch; FACET_DEGRADED '
                                                                '(BASELINE mode), repair access OPEN.'),
             ('CROWN_PREPARED', 'CROWN PREPARED', 'IMPLEMENTATION', ctl['crown_prepare']),
             ('CROWN_ENGAGED', 'CROWN ENGAGED', 'IMPLEMENTATION', ctl['crown_engage']),
             ('CROWN_DEGRADED', 'CROWN DEGRADED', 'IMPLEMENTATION', ctl['crown_fault']),
             ('SHIELD_DAMAGED', 'SHIELD DAMAGED', 'IMPLEMENTATION', ctl['damage_state'])]
    for p in poses:
        if p[0] not in states:
            raise ValueError(f'{p[0]} is not an exported display state')
    return dict(kind='eye', poses=[dict(state=a, label=b, status=c, text=t) for a, b, c, t in poses],
                order=fd['order']['sequence'], order_status=fd['order']['canon_status'],
                shield=dict(radius_m=d['forward_shield_radius_m'], face_x_m=face_x, status='WORKING envelope (90 m, 15 Q2)'),
                lance=dict(length_m=lance['length']['value'], tip_x_m=face_x+lance['length']['value'], base_radius_m=lance['geometry']['base_radius_m'],
                           status=lance['length']['canon_status']),
                shadow=dict(per_azimuth=shadow['per_azimuth'], target_deg=0.2, target_status='L2 TARGET ONLY (15!A211)',
                            diag_deg=fd['shadow_angle']['value_deg'], diag_status=fd['shadow_angle']['canon_status']),
                errors_deg=[0.0, 0.2, 1.0, 2.0, 2.5, 3.0],
                facet_modes={k: v for k, v in rig['eye']['facet_modes'].items()},
                unknown=dict(field_strength=None, impact_rating=None, repair_rate=None, dust_speed_limit=None,
                             why='OD-018 field strength and topology, OD-019 repair rates, window impact rating and the dust-speed slew '
                                 'limit are OPEN'))


def habitat(s, d, rig, manifest):
    rings, rot = rig['habitat']['rings'], rig['rotors']
    mech = manifest['timeline']['mechanisms']
    frames = {}
    for r in manifest['nodes']:
        if r.get('frame') in mech:
            frames.setdefault(r['frame'], []).append(r['node'])
    route = rig['induction_route']
    zone_frame = route['frames']['zones']
    rail = [dict(p=runtime(q['position_m']), zone=q['zone'], frame=zone_frame[q['zone']], m=round(q['rail_m'], 3)) for q in route['rail']]
    stops = [dict(title=q['title'], m=round(q['rail_m'], 3)) for q in route['stops']]
    lo = rig['habitat']['low_thrust_limit']
    return dict(kind='habitat',
                rotors=[dict(key=k, pivot=mech[k]['pivot_runtime_m'], axis=mech[k]['axis_runtime'], sign=1.0 if mech[k]['rad_per_unit'] > 0 else -1.0,
                             nodes=sorted(frames.get(k, [])), rpm=r['rpm'], omega=r['omega_rad_s'], mass_kg=r['mass_kg'], inertia=r['inertia_kg_m2'],
                             momentum=r['angular_momentum_N_m_s'], status=r['canon_status'],
                             spin_sign=r['spin_sign_by_configuration'])
                        for k, r in zip(sorted(mech), rot)],
                lock_angles_deg=rings['lock_angles_deg']['ROTOR_1'], floor_radius_m=rings['floor_radius']['value'],
                com_radius_m=rings['com_radius']['value'], outer_radius_m=rings['outer_radius']['value'],
                floor_gravity_g=d['floor_gravity_g'], g0=route['body']['standard_gravity_m_s2'],
                low_thrust=dict(limit_g=lo['value'], status=lo['canon_status'], tilt_deg=rig['habitat']['low_thrust_gravity_tilt_deg']['value']),
                occupancy=dict(rated=rings['rated_occupancy']['value'], story=rings['story_manifest']['value']),
                pressure_rule=rings['pressure_rule']['rule'],
                rail=rail, stops=stops, walk_speed_m_s=route['body']['review_speed_m_s'], walk_display_x=8.0,
                coriolis_g_per_m_s=route['body']['ladder_push']['coriolis_g_per_m_s'],
                unknown=dict(spin_down_s=None, lock_load=None, ring_section=None,
                             why='spin-down and lock durations (MEC-010, 20!E25:E26), ring section and lock sizing are OPEN; the ramp shown '
                                 'is PRESENTATION timing'))


def radiator(s, rig, manifest):
    rh = rig['radiator_health']
    # The three blades link the same cell meshes, so the names repeat per blade: the runtime assigns each cell to the blade whose root
    # booms (Radiator_Root_<b>_*) share its azimuth and ranks it by radiator_health's global index (blade, j, kk) and stride.
    zone = {(c['j'], c['kk']): c['zone'] for c in radiator_health.cells(s) if c['blade'] == 0}
    cells = []
    for r in manifest['nodes']:
        m = re.match(r'Blade_Cell_\d_(\d\d)_(\d\d)$', r['source_name'])
        if r['kind'] == 'radiator_cell' and m:
            j, kk = int(m.group(1)), int(m.group(2))
            cells.append([r['node'], j, kk, zone[(j, kk)]])
    if len(cells) != radiator_health.cell_count(s):
        raise ValueError(f'{len(cells)} radiator cells in the package, {radiator_health.cell_count(s)} in the spec')
    roots = {}
    for r in manifest['nodes']:
        m = re.match(r'Radiator_Root_(\d)_', r['source_name'])
        if m:
            roots.setdefault(m.group(1), []).append(r['node'])
    loops = {}
    for r in manifest['nodes']:
        m = re.match(r'Coolant_(?:Chase_)?(Feed|Return)_(\d)$', r['source_name'])
        if m:
            loops.setdefault(int(m.group(2)), []).append(r['node'])
    th = rig['thermal']
    return dict(kind='radiator', steps=[dict(id=k, value=v['value'], status=v['canon_status'], source=v['source_ref']) for k, v in rh['steps'].items()],
                cells=cells, roots={k: sorted(v) for k, v in sorted(roots.items())},
                grid=dict(longitudinal=radiator_health.grid(s)[1], transverse=radiator_health.grid(s)[2]), loops={str(k): sorted(v) for k, v in sorted(loops.items())}, loop_status='PROTOTYPE: one feed / return pair per blade (coolant proxies)',
                fault=dict(stride=rh['fault_pattern']['cell_order_stride'], status=rh['fault_pattern']['canon_status']),
                fluid=rh['fluid_status']['configurations'],
                area=dict(as_built_net_m2=th['as_built_net_area_total']['value'], physical_m2=th['physical_area_total']['value'],
                          effective_m2=th['effective_area']['value'], net_status=th['as_built_net_area_total']['canon_status'],
                          effective_status=th['effective_area']['canon_status']),
                hot_K=th['temperature']['value'], emissivity=th['emissivity']['value'],
                unknown=dict(flow_rate=None, drive_waste_heat_W=None, heat_debt=None, rejection_margin_W=None,
                             why='loop flow and temperatures (15!G101), drive waste heat and heat debt (40, OD-023/028/039) are OPEN; '
                                 'no rejection margin is computed here (owner science track, 15!A227)'))


def chapters(root, out):
    s, *_ = load(root)
    d = derived(s)
    rig = json.loads((out/'wf_sim_rig.json').read_text())
    manifest = json.loads((out/'manifest.json').read_text())
    shadow = json.loads((root/'references/m5_gnc_comms.json').read_text())['shadow']
    states = manifest['timeline']['states']
    e, h, r = eye(s, d, rig, shadow, states), habitat(s, d, rig, manifest), radiator(s, rig, manifest)
    rings = rig['habitat']['rings']
    rot = rig['rotors'][0]
    return [
        dict(id='eye', title='Forward EYE, Dust Lance and shield: watch, close, defend, absorb', show=['S01'],
             select=['subsystem:S01', 'name:Shield_Rim*'],
             colors=[['kind:eye_*', [0.30, 0.90, 1.00], 'EYE wells, windows and eyelids (four facets)'],
                     ['kind:dust_lance*', [1.00, 0.85, 0.35], f"Dust Lance, {e['lance']['length_m']:g} m ahead of the shield (WORKING)"],
                     ['kind:crown_*', [0.98, 0.55, 0.20], 'Crown bays: close-in mitigation behind the rim'],
                     ['kind:damage_cell', [1.00, 0.25, 0.25], 'shield damage cells (display pose)'],
                     ['kind:disruptor_*', [0.70, 0.55, 1.00], 'disruptor layer and posts'],
                     ['kind:shield_*', [0.40, 0.62, 1.00], 'Brow shield skin, rim, hub and mounts']],
             badges=[['WORKING', f"90 m shield and {e['lance']['length_m']:g} m Lance envelope (15 Q2); defence order {e['order_status']}"],
                     ['PROTOTYPE', 'truss, Crown, EYE wells and eyelid rig; display poses only'],
                     ['OPEN', 'field strength (OD-018), impact and repair rates (OD-019), dust-speed limit'],
                     ['TARGET', '<= 0.2 deg 3-sigma ram alignment is an L2 target, not a certified cap (15!A211)']],
             lines=['Defence order (BASELINE, 14!C18): ' + ' > '.join(x.replace('_', ' ').lower() for x in e['order']) + '.',
                    f"Shield shadow: geometric limit {min(a for _, a in e['shadow']['per_azimuth']):.2f} deg (worst azimuth) from the built "
                    f"model; the 0.2 deg target is not margin for dust or plasma. The {e['shadow']['diag_deg']:.2f} deg 8 m / 200 m figure is "
                    f"{e['shadow']['diag_status']}.",
                    'The dust stream is ILLUSTRATIVE: direction only, no flux, speed or impact energy.'],
             m6=e),
        dict(id='habitat', title='Habitat rings, spine and crew movement: spin, counter-rotation, lock', show=['S03', 'S04'],
             select=['subsystem:S03', 'subsystem:S04', 'kind:crew_trunk', 'kind:crew_passage', 'kind:spine_tunnel', 'name:Structural_Spine*'],
             colors=[['kind:sector_pressure', [0.45, 0.85, 0.55], 'pressurized sectors (occupied arcs only)'],
                     ['kind:sector_interior*', [0.75, 0.95, 0.70], 'sector interiors (human-scale whitebox)'],
                     ['kind:ring_*', [0.40, 0.70, 1.00], 'ring frames, spokes and fill'],
                     ['kind:rotor*', [0.95, 0.75, 0.30], 'rotor bearings, drives and mounts'],
                     ['kind:ring_stop_lock', [1.00, 0.40, 0.30], 'stop locks (index angles 90 / 210 / 330 deg)'],
                     ['kind:transfer_*', [0.85, 0.55, 1.00], 'despun transfer drums and closures'],
                     ['kind:crew_trunk', [0.95, 0.95, 0.95], 'stationary crew trunk along the spine']],
             badges=[['BASELINE', f"two counter-rotating rings, {rings['rpm']:g} rpm (08)"],
                     ['DERIVED', f"floor {d['floor_gravity_g']:.2f} g at r {rings['floor_radius']['value']:g} m; each ring "
                                 f"{rot['angular_momentum_N_m_s']/1e6:.1f} MN m s, opposite"],
                     ['PROTOTYPE', 'frames, spokes, rotor mechanisms, route rail'],
                     ['HOLD', 'Ring A casualty transfer UNQUALIFIED: no suited passage (15!A221)']],
             lines=[f"Spin gravity rises with radius (g = w^2 r): {rot['omega_rad_s']:.3f} rad/s gives {d['floor_gravity_g']:.2f} g on the "
                    f"{rings['floor_radius']['value']:g} m floor; the spine is weightless. Counter-rotation cancels the rings' angular momentum.",
                    'Before high thrust the rings stop and lock at an index angle (08!A47, MEC-011); in the burn the floor load is axial '
                    f"(LOW_THRUST limit {h['low_thrust']['limit_g']:g} g {h['low_thrust']['status']}). Spin-down time is OPEN: the ramp is "
                    'PRESENTATION timing.',
                    'Ring A casualty transfer: unsuited spin-port turn FAIL -0.013 m, suited about -0.17 m; in-place stabilization, no '
                    'pressure-hull flare (15!A221, 98!A122). Not a rescue route.'],
             m6=h),
        dict(id='radiator', title='Radiator blades and loops: operating steps, damage and isolation', show=['S09'],
             select=['subsystem:S09', 'kind:radiator_cell', 'kind:radiator_thermal_glow', 'kind:expansion_joint', 'kind:coolant_*',
                     'kind:root_*', 'kind:leading_edge_proxy'],
             colors=[['kind:coolant_*', [0.30, 0.85, 1.00], 'coolant feed / return trunks and chases'],
                     ['kind:root_*', [0.95, 0.70, 0.25], 'root booms and saddles'],
                     ['kind:expansion_joint', [0.70, 0.70, 0.78], 'expansion joints (fixed blades never fold)']],
             badges=[['BASELINE', 'three fixed blades; operating sequence (07!A39, 11)'],
                     ['DERIVED', f"{r['area']['as_built_net_m2']:,.0f} m2 as-built net one-face, {r['area']['effective_m2']:,.0f} m2 effective"],
                     ['PROTOTYPE', '480-cell grid, fault order and per-blade loops are display constructs'],
                     ['DIAGNOSTIC', 'thermal balance FAIL at First Ignition (28 col E); no rejection margin shown']],
             lines=[f"Hot face {r['hot_K']:g} K, emissivity {r['emissivity']:g} (WORKING). Coolant state is independent of thrust; flow "
                    'rate and loop temperatures are OPEN (15!G101).',
                    'Damage and isolation are display states: the physical area is unchanged; the in-service share is a CAD readback of '
                    'the prototype cell grid, not a heat-rejection value.',
                    'Drive waste heat, heat debt and the rejection margin stay UNKNOWN until the owner science track releases them '
                    '(15!A227).'],
             m6=r),
    ]
