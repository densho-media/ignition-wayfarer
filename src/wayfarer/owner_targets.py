"""Owner targets of 2026-10-03b (OWN-002, F1): the answers Q1-Q33 as WORKING numbers, compared with the PROTOTYPE geometry.

The targets are source values in their topical tables (habitat.spokes, habitat.ring_plane_spacing, habitat.ring_service_clearance, habitat.transfer,
shielding.refuge, service.docking, forward_defense.shield_profile / shield_load_path / crown / disruptor_layer / eye_wells / dust_lance), each with a
`source_ref`. Nothing here is a measurement copied back into canon: every check computes its current value from the spec through the shared pure
modules (habitat_ring, hull_geometry, forward_shield) and compares it with the target.

A check the geometry meets is HARD. A check it does not meet yet must be listed in `[owner_targets.pending]` (IMPLEMENTATION) with the task that
fixes it. FWD-001 (F2), HAB-001 (F3) and FWD-003 (Q45) met their targets, so their checks are hard. `failures` rejects an unmet check that is not
pending, a pending entry whose target is now met (the next stage deletes the entry and the check becomes hard), an unknown id, a duplicate id and
an entry owned by the wrong task. A value, tolerance or check is never edited to make a pending entry pass.

Pure functions over the spec dict; standard library plus the shared geometry modules.
"""
import math
import habitat_ring
import forward_shield
import hull_geometry

STAGES = {'FWD-001': 'F2', 'FWD-003': 'Q45', 'HAB-001': 'F3'}
EPS = 1e-9


def _rule(ok, current, target, detail=''):
    return {'ok': bool(ok), 'current': current, 'target': target, 'detail': detail}


def refuge_shell_kg(s):
    """Water-equivalent mass of the PROTOTYPE refuge shell (>= 20 g/cm2 at the selected shield density)."""
    return hull_geometry.refuge(s)['shield_volume_m3']*s['prototype']['refuge_shield_density_g_cm3']*1000


def seal_planes(s):
    """Seal planes per leak path of the rotary vestibule as the geometry builds them (crew_transfer.seal_planes counts built ring end faces, not a list)."""
    import crew_transfer
    return crew_transfer.seal_planes(s)


def crew_spoke_count(s):
    return len({q['index'] for q in habitat_ring.spokes(s) if q['ring'] == 1 and q['crew']})


def sector_tie_rule(s):
    """Q1: every primary sector is tied (hub tie plus both truss-node ties) from a keel at the sourced radius, each at a sourced sector azimuth, and the hub path exists (Brow side only; the path into the ship is shield_sector_continuity)."""
    sectors = habitat_ring_sector_azimuths(s); keels = forward_shield.sector_keels(s)
    ok_az = all(any(abs(((k['theta']-a+math.pi) % (2*math.pi))-math.pi) <= EPS for a in sectors) for k in keels)
    return (forward_shield.sector_truss_count(s) == s['forward_defense']['shield_load_path']['primary_sectors'] and ok_az and len(forward_shield.mount_struts(s)) >= 3
            and all(math.isclose(k['r'], s['structure']['sector_radius_m'], abs_tol=EPS) for k in keels))


def habitat_ring_sector_azimuths(s):
    """Sourced sector azimuths computed independently of forward_shield: structure.sector_pickup_nodes at the cage phase."""
    st = s['structure']
    return [math.radians(s['prototype']['ring_phase_deg'])+n*2*math.pi/st['ring_nodes'] for n in st['sector_pickup_nodes']]


def dock_capture_ring_radius_m(s):
    """Radius of the structural capture ring around a docking port (PROTOTYPE, hull_geometry.capture_rings)."""
    return min((q['radius'] for q in hull_geometry.capture_rings(s)), default=0.0)


def checks(s):
    """id -> (task, evaluator) of every target check. The evaluator returns {ok, current, target, detail}."""
    h = s['habitat']; d = s['forward_defense']; fs = forward_shield; hr = habitat_ring; p = fs.prototype(s); sh = s['shielding']['refuge']
    sp = h['spokes']; prof = d['shield_profile']; cg = d['crown']['geometry']; w = d['eye_wells']; dk = s['service']['docking']['standard']
    allocation = hr.refuge_water_allocation_kg(s)
    lo_v, hi_v = sh['total_volume_m3']; lo_d, hi_d = sp['depth_m']; lo_t, hi_t = prof['truss_standoff_depth_m']
    refuge = lambda: hull_geometry.refuge(s)
    tip = lambda: fs.overall_length(s)
    wells = lambda: [p['well_diameter_m'], fs.stations(s)['well_depth'], math.hypot(*fs.well_centres(s)[0])]
    eye_target = lambda: [w['diameter_m'], w['depth_m'], w.get('source_centre_radius_m', w['centre_radius_m'])]      # the WORKING r4, never the study radius
    return {
        # ---- F3 / HAB-001: rings, crew route, refuge, docking ----
        'refuge_volume_m3': ('HAB-001', lambda: _rule(lo_v <= refuge()['pressure_volume_m3'] <= hi_v, refuge()['pressure_volume_m3'], [lo_v, hi_v], 'Q31 usable ~50-60 m3 for 12 (~4 m3/person)')),
        'refuge_water_shell_kg': ('HAB-001', lambda: _rule(refuge_shell_kg(s) <= allocation+EPS, refuge_shell_kg(s), allocation, 'Q32 the >= 20 g/cm2 shell must fit the ~20 t refuge water allocation')),
        'ring_spar_clearance_m': ('HAB-001', lambda: _rule(hr.spar_clearance_m(s) >= h['ring_service_clearance']['min_m']-EPS, hr.spar_clearance_m(s), h['ring_service_clearance']['min_m'], 'Q29 ring A aft sweep to the radiator leading spar front')),
        'ring_plane_spacing_m': ('HAB-001', lambda: _rule(math.isclose(hr.plane_spacing_m(s), h['ring_plane_spacing']['value'], abs_tol=EPS), hr.plane_spacing_m(s), h['ring_plane_spacing']['value'], 'Q29 keep the close counter-rotating pair')),
        'spoke_depth_m': ('HAB-001', lambda: _rule(lo_d-EPS <= hr.spoke_depth_m(s) <= hi_d+EPS, hr.spoke_depth_m(s), [lo_d, hi_d], 'Q28 working structural depth')),
        'spoke_layout': ('HAB-001', lambda: _rule(s['habitat_ring']['spokes_per_ring'] == sp['per_ring'] and math.isclose(360.0/s['habitat_ring']['spokes_per_ring'], sp['spacing_deg'])
                                                  and crew_spoke_count(s) == sp['crew'] and s['habitat_ring']['spokes_per_ring']-crew_spoke_count(s) == sp['structural'],
                                                  [s['habitat_ring']['spokes_per_ring'], crew_spoke_count(s)], [sp['per_ring'], sp['crew']], 'Q28 six spokes at 60 degrees, three crew')),
        'vestibule_seal_planes': ('HAB-001', lambda: _rule(seal_planes(s) >= h['transfer']['seal_planes_min'], seal_planes(s), h['transfer']['seal_planes_min'], 'Q30 double-boundary rotary vestibule')),
        'dock_clear_passage_m': ('HAB-001', lambda: _rule(2*s['prototype']['dock_clear_radius_m'] >= dk['clear_passage_m']-EPS, 2*s['prototype']['dock_clear_radius_m'], dk['clear_passage_m'], 'Q33 ~1.6 m clear passage, compared with the clear radius (the fitting radius adds the passage wall)')),
        'dock_keep_out_corridor_m': ('HAB-001', lambda: _rule(s['prototype']['dock_corridor_radius_m'] >= dk['keep_out_corridor_m']-EPS, s['prototype']['dock_corridor_radius_m'], dk['keep_out_corridor_m'],
                                                              'Q33 ~3 m keep-out corridor; the modelled corridor is a cylinder of this RADIUS (strictest reading: it also holds as a width)')),
        'dock_capture_ring': ('HAB-001', lambda: _rule(dock_capture_ring_radius_m(s) > s['prototype']['dock_clear_radius_m'] and len(hull_geometry.capture_rings(s)) == s['service']['docking']['port_count'] and all(r['pass'] for r in hull_geometry.capture_ring_rows(s).values()),
                                                dock_capture_ring_radius_m(s), '> %s' % s['prototype']['dock_clear_radius_m'], 'Q33 structural capture ring larger than the clear passage on both ports, clear of the corridor, keels, ties, airlock and packs')),
        # ---- F2 / FWD-001: forward shield, Crown, field ----
        # Comparison rules (FWD-001): exact where the owner gives a number, the owner's stated range or bound where it gives one, and no invented tolerance.
        'shield_crown_depth_m': ('FWD-001', lambda: _rule(abs(fs.crown_depth_m(s)-prof['crown_depth_m']) <= EPS, fs.crown_depth_m(s), prof['crown_depth_m'], 'Q3 conical face: face X at the axis minus face X at r 45 equals the owner ~3 m exactly (an exact selection, no tolerance)')),
        'shield_truss_depth_m': ('FWD-001', lambda: _rule(lo_t-EPS <= p['truss_depth_m'] <= hi_t+EPS, p['truss_depth_m'], [lo_t, hi_t], 'Q3 ~3-4 m truss/standoff')),
        'shield_sector_truss_count': ('FWD-001', lambda: _rule(sector_tie_rule(s), [fs.sector_truss_count(s), len(fs.mount_struts(s))], [d['shield_load_path']['primary_sectors'], '>= 3 hub struts'],
                                                              'Q1 Brow side: sectors with a complete tie set from a keel at the sourced radius and azimuth into the Brow truss equal the primary sectors, plus the hub path. Says nothing about the path into the ship (see shield_sector_continuity)')),
        'shield_sector_continuity': ('FWD-003', lambda: _rule(fs.sector_continuity_gap_m(s) <= EPS and d['shield_load_path']['hub_alone_forbidden'] is True, round(fs.sector_continuity_gap_m(s), 6), 0.0,
                                                              'Q1/15!H50: each sector keel reaches the primary cage at its sourced radius and azimuth, so the hub is not the only path into the ship: through the Q45 bypass collar round the rotor bay')),
        'disruptor_layer_count': ('FWD-001', lambda: _rule(fs.disruptor_layer_count(s) >= 1, fs.disruptor_layer_count(s), '>= 1', 'FWD1 one or more full-diameter layers, all of it ahead of the Brow face (the count is OPEN, derived from the layers)')),
        'crown_engaged_hardware_radius_m': ('FWD-001', lambda: _rule(fs.engaged_hardware_radius_m(s) <= cg['engaged_radius_max_m']+EPS, fs.engaged_hardware_radius_m(s), cg['engaged_radius_max_m'],
                                                                     'Q6 largest Crown hardware radius over every preset, display pose and a 1/96-turn azimuth sweep at full engagement stays within the inclusive r 45 m bound')),
        'crown_housing_radius_m': ('FWD-001', lambda: _rule(cg['housing_radius_m'][0] <= p['crown_housing_inner_radius_m'] and p['rim_inner_radius_m'] <= cg['housing_radius_m'][1],
                                                              [p['crown_housing_inner_radius_m'], p['rim_inner_radius_m']], cg['housing_radius_m'], 'Q6 housing ~41-44.5 m (no tolerance stated; F2 states its comparison rule)')),
        'crown_engaged_motion': ('FWD-001', lambda: _rule(fs.crown_radial_travel_m(s) <= EPS and fs.crown_axial_stroke_m(s) > 0 and cg['engaged_motion'] == 'MAINLY_FORWARD',
                                                          [fs.crown_radial_travel_m(s), fs.crown_axial_stroke_m(s)], ['<= 0', '> 0'], 'Q6 engaged hardware translates mainly forward: no radial travel, a positive axial stroke')),
        'disruptor_ahead_of_crown': ('FWD-001', lambda: _rule(fs.engaged_muzzle_margin_m(s) >= s['prototype']['mechanical_clearance_m']-EPS, fs.engaged_muzzle_margin_m(s), s['prototype']['mechanical_clearance_m'],
                                                              'engaged muzzles fire at least one shared clearance ahead of the most forward layer front at the port edge')),
        'eye_line_of_sight': ('FWD-001', lambda: _rule(all(r['ok'] for r in fs.eye_line_of_sight(s)), [round(r['min_margin'], 6) for r in fs.eye_line_of_sight(s)], '>= 0',
                                                       'the boresight cylinder of every well meets no opaque forward solid and every port is at least the derived no-vignetting radius')),
        'docking_corridor_clear_of_shield': ('FWD-001', lambda: _rule(all(r['passes'] for r in fs.corridor_clearance_rows(s).values()) and all(r['pass'] for r in hull_geometry.corridor_rows(s).values()),
                                                                      {k: round(r['min_gap_m'], 3) for k, r in fs.corridor_clearance_rows(s).items()}, '>= %s' % s['prototype']['mechanical_clearance_m'],
                                                                      'Q33 each 3 m corridor clears the truss, rim, Crown housing, keels, hoops and ties by the shared clearance')),
        'crown_bays': ('FWD-001', lambda: _rule(p['crown_bay_count'] == cg['bay_count'] and math.isclose(360.0/p['crown_bay_count'], cg['bay_spacing_deg']) and d['crown_inputs']['active_sectors'] <= cg['max_cooperating_sectors'],
                                                  [p['crown_bay_count'], 360.0/p['crown_bay_count']], [cg['bay_count'], cg['bay_spacing_deg']], 'Q6 12 bays at 30 degrees, up to four cooperating')),
        'eye_wells': ('FWD-001', lambda: _rule(all(math.isclose(a, b) for a, b in zip(wells(), eye_target())), wells(), eye_target(), 'Q3 wells 3.5 x 2.0 m at r ~4 m')),
        'overall_length_with_lance_m': ('FWD-001', lambda: _rule(s['ship']['length']['min'] <= tip() <= s['ship']['length']['max']+EPS and math.isclose(tip()-s['ship']['length']['value'], d['dust_lance']['length']['value'], abs_tol=EPS),
                                                                  tip(), [s['ship']['length']['min'], s['ship']['length']['max']], 'Q2 overall length INCLUDES the Lance')),
        'shield_shadow_margins_m': ('FWD-001', lambda: _rule(fs.shield_radius(s)-habitat_ring.outer(s) >= s['forward_shield']['ring_shadow_margin']['value']-EPS and
                                                              fs.shield_radius(s)-s['radiators']['outer_radius']['value'] >= s['forward_shield']['radiator_shadow_margin']['value']-EPS,
                                                              [fs.shield_radius(s)-habitat_ring.outer(s), fs.shield_radius(s)-s['radiators']['outer_radius']['value']],
                                                              [s['forward_shield']['ring_shadow_margin']['value'], s['forward_shield']['radiator_shadow_margin']['value']], 'sourced 15 m ring and 8 m radiator shadow margins hold')),
    }


def pending(s):
    """{id: task} from the data."""
    return {x['id']: x['task'] for x in s['owner_targets']['pending']['items']}


def study_deviations(s):
    """Checks a declared STUDY switch deliberately moves off its owner target (never silently met): {id: reason}. Only the FWD-V2 Eye layout
    (forward_defense.eye_layout) today: at r24 the wells leave the Q3 r ~4 m target, which stays the WORKING value (FD-B07)."""
    lay = s['forward_defense'].get('eye_layout')
    return {'eye_wells': f"STUDY layout {lay['selected']} selected in forward_defense.eye_layout; owner keeps r4 WORKING (FD-B07)"} if forward_shield.eye_layout_active(s) else {}


def evaluate(s, only=None):
    """Rows for every check (or only the ids in `only`): id, task, stage, pending flag, any declared study deviation and the rule result. Never raises
    on an unmet check."""
    pend = pending(s); dev = study_deviations(s)
    return [{'id': cid, 'task': task, 'stage': STAGES[task], 'pending': cid in pend, 'study_deviation': dev.get(cid), **fn()} for cid, (task, fn) in checks(s).items()
            if only is None or cid in only]


def failures(s, only=None):
    """Hard failures: an unmet check that is not pending, a pending entry that is now met, unknown or owned by the wrong task, or a duplicate.
    With `only` (a set of check ids) just those checks and their pending entries are evaluated."""
    out = []; rows = {r['id']: r for r in evaluate(s, only)}; pend = s['owner_targets']['pending']['items']
    if only is not None:
        pend = [x for x in pend if x['id'] in only]
    ids = [x['id'] for x in pend]
    if len(set(ids)) != len(ids):
        out.append('owner_targets.pending lists an id twice')
    for x in pend:
        if x['id'] not in rows:
            out.append(f"owner_targets.pending: unknown check {x['id']}")
        elif x['task'] != rows[x['id']]['task'] or x['stage'] != STAGES.get(x['task']):
            out.append(f"owner_targets.pending {x['id']}: owned by {rows[x['id']]['task']} ({rows[x['id']]['stage']})")
        elif rows[x['id']]['ok']:
            out.append(f"owner_targets.pending {x['id']} is met now (current {rows[x['id']]['current']}): delete the entry so the check is hard")
    for cid, r in rows.items():
        if r['study_deviation'] and r['ok']:
            out.append(f"Owner target {cid} is met although a study deviation is declared: {r['study_deviation']}")
        if not r['ok'] and not r['pending'] and not r['study_deviation']:
            out.append(f"Owner target {cid} not met: current {r['current']}, target {r['target']} ({r['detail']}); fix the geometry or list it under owner_targets.pending for {r['task']}")
    return out


SOURCED_TABLES = ('habitat.spokes', 'habitat.ring_plane_spacing', 'habitat.ring_service_clearance', 'habitat.ring_axial_deflection_target', 'service.docking.standard',
                  'forward_defense.dust_lance.length', 'forward_defense.dust_lance.geometry', 'forward_defense.eye_wells', 'forward_defense.field_states',
                  'forward_defense.shield_load_path', 'forward_defense.shield_profile', 'forward_defense.crown.geometry', 'forward_defense.crown.sub_arrays',
                  'forward_defense.crown_mass', 'forward_defense.crown_pulse_banks', 'forward_defense.disruptor_layer', 'forward_defense.dustbreak_veil')


def _node(s, path):
    node = s
    for part in path.split('.'):
        node = node[part]
    return node


def source_failures(s, source_map):
    """Every sourced 2026-10-03b table carries its own WORKING status and cites a source record of the same status; the table values are self-consistent."""
    out = []; sources = source_map['sources']
    for path in SOURCED_TABLES:
        node = _node(s, path)
        ref = node.get('source_ref')
        if node.get('canon_status') != 'WORKING' or ref not in sources or sources[ref]['canon_status'] != 'WORKING':
            out.append(f'{path}: a WORKING table citing a WORKING source record (source_ref {ref})')
    pend = s['owner_targets']['pending']
    if pend.get('status') != 'IMPLEMENTATION' or not pend.get('rationale'):
        out.append('owner_targets.pending is an IMPLEMENTATION registry with a rationale, never canon')
    sp = s['habitat']['spokes']
    if not math.isclose(sp['spacing_deg']*sp['per_ring'], 360.0) or sp['crew']+sp['structural'] != sp['per_ring'] or not 0 < sp['depth_m'][0] < sp['depth_m'][1]:
        out.append('habitat.spokes: spacing x count = 360 degrees, crew + structural = count, ordered depth range')
    r = s['shielding']['refuge']
    if not r['volume_per_person_m3']*r['capacity_persons'] <= r['total_volume_m3'][0] < r['total_volume_m3'][1]:
        out.append('shielding.refuge: the ~50-60 m3 total includes circulation and equipment on top of ~4 m3 x the rated occupants')
    dk = s['service']['docking']['standard']
    if dk['known'] is not True or not dk['clear_passage_m'] < 2*dk['keep_out_corridor_m'] or s['service']['docking']['capture_ring'].get('known') is not False:
        out.append('service.docking: the passage fits the corridor and the capture ring stays OPEN')
    if s['habitat']['ring_axial_deflection_target']['checked'] is not False:
        out.append('habitat.ring_axial_deflection_target is an FEA target, not a checked result')
    lo, hi = s['forward_defense']['crown']['geometry']['housing_radius_m']
    if not lo < hi <= s['forward_defense']['crown']['geometry']['engaged_radius_max_m']:
        out.append('forward_defense.crown.geometry: housing range inside the engaged radius limit')
    return out


def budget_failures(s):
    """Mass basis of Q32: the 180 t water splits 160 t rotating + 20 t stationary refuge (not additive), the rotating allowances sum to the rotating
    mass, and the ring mass is that mass over the ring count."""
    out = []; ph = s['physics']; hr = habitat_ring
    w = hr.water_item(s); region = next(i for i in ph['mass_regions']['items'] if i['id'] == 'water_radiation_shielding')
    if 'refuge_allowance_kg' not in w or not math.isclose(w['rotating_allowance_kg']+w['refuge_allowance_kg'], w['mass_kg']):
        out.append('Water: rotating allowance plus the stationary refuge allowance must equal the water line (not additive)')
    elif not (math.isclose(region['rotating_kg'], w['rotating_allowance_kg']) and math.isclose(region.get('stationary_refuge_kg', -1.0), w['refuge_allowance_kg'])):
        out.append('mass_regions water split must equal the budget item split')
    if not math.isclose(hr.rotating_total_kg(s), ph['rotor_sizing']['mass_kg']):
        out.append('Rotating allowances must sum to physics.rotor_sizing.mass_kg')
    if not math.isclose(ph['rotor_sizing']['mass_kg']/hr.ring_count(s), ph['rotor_dynamics']['mass_each_kg'], rel_tol=1e-9):
        out.append('Ring mass is the rotating mass over the ring count')
    return out
