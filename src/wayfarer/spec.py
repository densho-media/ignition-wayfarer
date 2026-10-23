"""Offline P0 inputs and small, pure-Python validation. No Blender dependency."""
import copy
from pathlib import Path
import hashlib
import json
import math
import re
import tomllib
import thermal_geometry
import thermal_budget
import thermal_loops
import warm_panels
import radiator_net_area
import hull_geometry
import forward_shield
import radiator_health
import flight_timeline
import drive_manifold
import habitat_ring
import cabin_atmosphere
import owner_targets
import first_ignition
import layout

ROOT = Path(__file__).resolve().parents[2]
CROSS_RANGE = re.compile(r'[A-Za-z0-9_]+![A-Z]{1,3}[0-9]+(:[A-Z]{1,3}[0-9]+)?')
STATUSES = {'LOCKED', 'BASELINE', 'WORKING', 'PROVISIONAL', 'OPEN', 'PROTOTYPE', 'SUPERSEDED', 'DERIVED', 'DIAGNOSTIC'}


_VALIDATED = {}


def load(root=ROOT):
    """Parse and validate the input pair; identical file contents are validated once per process."""
    spec_text = (root / 'data/wayfarer_3d.toml').read_text()
    source_text = (root / 'data/source_map.toml').read_text()
    key = (spec_text, source_text)
    if key not in _VALIDATED:
        spec, sources = tomllib.loads(spec_text), tomllib.loads(source_text)
        apply_eye_layout(spec)
        validate(spec, sources)
        _VALIDATED.clear()
        _VALIDATED[key] = (spec, sources)
    spec, sources = _VALIDATED[key]
    spec = copy.deepcopy(spec)
    # Detail packs (data/detail/*.toml, docs/MODULES.md) travel with the spec but outside its hash: a pack edit stales only its own detail
    # assets. Malformed packs are refused here like a bad spec.
    import modules
    spec['detail_packs'] = modules.packs(root)
    fails = modules.check_packs(spec['detail_packs'], sources)
    if fails:
        raise ValueError('Detail packs: '+'; '.join(fails))
    return spec, copy.deepcopy(sources), spec_text, source_text


def apply_eye_layout(s):
    """FWD-V2 Eye layout switch (forward_defense.eye_layout): the selected layout's well centre radius replaces the WORKING r 4 m in memory, so the
    generators, checks, rig and Navigator all see one layout. r4 changes nothing; any other layout is a labelled STUDY (owner FD-B07: r4 and
    B_array 8 m stay WORKING) and keeps the source value as source_centre_radius_m."""
    lay = s['forward_defense'].get('eye_layout')
    if not lay or lay['selected'] == 'r4':
        return s
    if lay['selected'] not in lay['radii_m']:
        raise ValueError(f"forward_defense.eye_layout.selected: unknown layout {lay['selected']}")
    w = s['forward_defense']['eye_wells']
    w['source_centre_radius_m'] = w['centre_radius_m']; w['centre_radius_m'] = float(lay['radii_m'][lay['selected']])
    w['study'] = f"FWD-V2 {lay['selected']} layout ({lay['status']}; owner keeps r4 WORKING, FD-B07)"
    return s


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


def station_x(s, ident):
    return layout.at(s, next(x['x'] for x in s['layout']['stations'] if x['id']==ident))


def stale_position_keys(s):
    """Paths of pre-FGR-004 position keys (fractions or bare-metre X) left in the tables that hold ship-frame positions."""
    out = []
    def walk(node, path):
        if isinstance(node, dict):
            for k, v in node.items():
                if k.endswith('_center_fraction') or k.endswith('_x_m') or k in ('x_fraction', 'x0_m', 'x1_m', 'rotor_centers_m'):
                    out.append(f'{path}.{k}')
                walk(v, f'{path}.{k}')
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk(v, f'{path}[{i}]')
    for name in ('prototype', 'drive_manifold', 'power_storage'):
        walk(s[name], name)
    walk(s['layout']['stations'], 'layout.stations')
    return out


def station_radius_ok(station):
    """A station carries exactly one of radius_fraction (0, 1] or the radius_rule RADIATOR_CASING."""
    has_fraction, has_rule = 'radius_fraction' in station, 'radius_rule' in station
    if has_fraction == has_rule:
        return False
    return 0 < station['radius_fraction'] <= 1 if has_fraction else station['radius_rule'] == 'RADIATOR_CASING'


def derived(s):
    p, r, h = s['prototype'], s['radiators'], s['habitat']
    g = r['geometry']
    per = r['physical_area']['value']
    blade = thermal_geometry.blade_of(s)
    if abs(blade['front_x_m'] - layout.origin(s, 'RADIATOR_FRONT')) > 1e-9:
        raise ValueError('RADIATOR_FRONT datum differs from the blade front')
    thrust = s['propulsion']['design_thrust']['value']*1e6
    flight = s['propulsion']['flight_thrust']['value']*1e6
    floor_g = habitat_ring.floor_gravity_g(s)
    band = thermal_geometry.root_band(s)
    net = radiator_net_area.working_net_area(s)
    return {'petal_planform_m2': per, 'total_planform_m2': per * r['count'],
            'design_thrust_N': thrust, 'nozzle_design_thrust_share_N': thrust/s['propulsion']['nozzle_count'],
            'flight_thrust_N': flight, 'nozzle_flight_thrust_share_N': flight/s['propulsion']['nozzle_count'],
            'low_thrust_gravity_tilt_deg': habitat_ring.tilt_deg(s),
            **blade,
            'nominal_net_area_m2': r['nominal_net_area']['value'],
            'net_area_m2': net, 'total_net_area_m2': net*r['count'],
            'assumed_effective_area_m2': net*r['count']*r['emitting_faces']*r['view_factor']['value'],
            'local_circumscribed_diameter_m': 2*blade['outer_radius_m'],
            'ring_com_radius_m': habitat_ring.com(s), 'ring_outer_radius_m': habitat_ring.outer(s),
            'ring_sweep_half_m': habitat_ring.sweep_half(s), 'sector_arc_deg': math.degrees(habitat_ring.sector_arc(s)),
            'sector_gross_m3': habitat_ring.sector_gross_m3(s), 'sector_deck_to_overhead_m3': habitat_ring.deck_to_overhead_m3(s),
            'usable_per_sector_m3': h['layout']['usable_per_ring_m3']/s['habitat_ring']['sectors_per_ring'],
            'gross_pressure_volume_m3': habitat_ring.gross_total(s),
            'floor_gravity_g': floor_g,
            'forward_shield_radius_m': s['forward_shield']['diameter']['value']/2, 'casing_radius_m': thermal_geometry.casing_radius(s),
            'root_band_width_m': band['width_m'], 'root_band_planform_m2': band['planform_m2'], 'root_calibration_margin_W': thermal_budget.root_calibration_margin_W(s),
            'bay_length_m': blade['blade_length_m']/g['major_bays'], 'radiator_aft_x_m': layout.origin(s, 'RADIATOR_AFT'),
            'length_m': s['ship']['length']['value'], 'body_diameter_m': s['ship']['body_diameter']['value']}


DRIVE_STATES = {'OFF', 'ACTIVE'}
# Rings spin in COAST/LOW_THRUST/EVA and are stopped and locked at full size for high thrust and docking; never retracted or turned.
HABITAT_STATES = {'ROTATING', 'STOPPED_LOCKED'}
# Radiator blades are fixed in every mode (R1/R8, MEC-012): the one geometric radiator state. Thermal load is a separate operating field.
RADIATOR_STATES = {'FIXED'}
THERMAL_LOADS = {'LOW', 'CONTINUOUS', 'MAXIMUM', 'EVA_LOW_POWER', 'COLD'}
# IMPLEMENTATION preset values of the rotor controls (ring_spin, ring_lock) for each habitat state.
CONTROLS = {'ROTATING': {'ring_spin': 1.0, 'ring_lock': 0.0}, 'STOPPED_LOCKED': {'ring_spin': 0.0, 'ring_lock': 1.0}}


def validate_configuration(cfg, rpm, low_thrust_limit_g):
    """Operating rules for one configuration: drive/habitat/radiator states, habitat rpm, preset controls and the thrust envelope."""
    drive, habitat, radiators = cfg['drive'], cfg['habitat'], cfg['radiators']
    if drive not in DRIVE_STATES or habitat not in HABITAT_STATES or radiators not in RADIATOR_STATES or cfg.get('thermal_load', 'LOW') not in THERMAL_LOADS:
        raise ValueError('Unknown operating configuration state')
    accel = cfg.get('max_accel_g', 0)
    if drive == 'OFF' and accel:
        raise ValueError('Drive OFF cannot carry an acceleration')
    if drive == 'ACTIVE':
        if not accel > 0:
            raise ValueError('Active drive needs a positive acceleration')
        # 08_ROTATING_HABITAT H54 / 15_MODEL_INTERFACES E5: above the working limit both rings stop and lock.
        if accel > low_thrust_limit_g and habitat != 'STOPPED_LOCKED':
            raise ValueError('Above the 0.1 g working limit both rings must be stopped and locked')
    if habitat == 'ROTATING' and rpm <= 0:
        raise ValueError('A rotating habitat needs a positive rpm')
    if habitat == 'STOPPED_LOCKED' and rpm != 0:
        raise ValueError('A stopped and locked habitat must have zero rpm')
    if cfg.get('controls') != CONTROLS[habitat]:
        raise ValueError(f'Preset controls must be {CONTROLS[habitat]} for a {habitat} habitat')


def configuration_rpm(s, cfg):
    return s['habitat']['rpm'] if cfg['habitat'] == 'ROTATING' else 0


def buildable_configurations(s, habitat=None):
    """Buildable presets, optionally only those with the given habitat state."""
    return [name for name, cfg in s['configuration'].items() if cfg['buildable'] and habitat in (None, cfg['habitat'])]


def display_poses(s):
    """Preview-only display poses of every control surface: {name: (table, base preset)}. Names are unique across tables and never configurations."""
    out = {}
    for table, poses in (('forward_defense', s['forward_defense']['display_poses']), ('radiator_health', s['radiator_health']['display_poses'])):
        for name, pose in poses.items():
            if not isinstance(pose, dict):
                continue
            if name in out or name in s['configuration']:
                raise ValueError(f'Display pose {name}: names must be unique and never a configuration')
            out[name] = (table, pose['base'])
    return out


def validate_vehicle(s):
    v = s['vehicle']
    if not (isinstance(v['asset'], str) and v['asset'] and isinstance(v['saved_preset'], str)):
        raise ValueError('vehicle: asset and saved_preset must be strings')
    if v['saved_preset'] not in buildable_configurations(s, 'ROTATING'):
        raise ValueError('vehicle: saved_preset must be a buildable ROTATING configuration')
    if not all(buildable_configurations(s, state) for state in HABITAT_STATES):
        raise ValueError('vehicle: every habitat state needs a buildable preset')


def validate_configurations(s):
    eye_modes = set(s['eye']['facet_modes']) | set(s['eye']['laser_modes'])
    validate_vehicle(s)
    for name, cfg in s['configuration'].items():
        if 'eye_mode' in cfg and cfg['eye_mode'] not in eye_modes:
            raise ValueError(f'{name}: unknown EYE mode')
        if cfg['buildable']:
            validate_configuration(cfg, configuration_rpm(s, cfg), s['habitat']['low_thrust_limit']['value'])
        else:
            if 'controls' in cfg or 'habitat' in cfg:
                raise ValueError(f'{name}: unbuildable configuration cannot claim a habitat state or controls')
            if not any(isinstance(v, dict) and v.get('known') is False for v in cfg.values()):
                raise ValueError(f'{name}: unbuildable configuration must name its unknown inputs')


def validate_derived_sources(s):
    """Captured DERIVED workbook values must still follow from current inputs."""
    rd=s['physics']['rotor_dynamics'];g0=habitat_ring.G0
    expected=habitat_ring.dynamics(s)
    if set(rd)-{'model','canon_status','source_ref'} != set(expected):
        raise ValueError(f'rotor_dynamics keys differ from habitat_ring.dynamics: {sorted(set(rd)^set(expected))}')
    for key,value in expected.items():
        if not math.isclose(rd[key],value,rel_tol=1e-6):
            raise ValueError(f'Stale DERIVED rotor value {key}: captured {rd[key]}, inputs give {value}')
    xd=s['physics']['rotor_dynamics_diagnostic'];exp=habitat_ring.diagnostics(s)
    if set(xd)-{'example_slew_rate_deg_s','flywheel_mass_kg','flywheel_radius_m','model','note','canon_status','source_ref'} != set(exp):
        raise ValueError(f'rotor_dynamics_diagnostic keys differ from habitat_ring.diagnostics: {sorted(set(xd)^set(exp))}')
    for key,value in exp.items():
        if not math.isclose(xd[key],value,rel_tol=1e-6):
            raise ValueError(f'Stale DIAGNOSTIC ring value {key}: captured {xd[key]}, inputs give {value}')
    a=s['habitat']['atmosphere']
    if not math.isclose(a['o2_partial']['value'],cabin_atmosphere.o2_partial_kpa(a['cabin_pressure_kpa'],a['o2_fraction']),rel_tol=1e-6):
        raise ValueError('Stale DERIVED cabin O2 partial pressure')
    r=s['radiators'];eq=r['equivalent_blade'];b=thermal_geometry.blade(r['nominal_net_area']['value'],r['root_radius']['value'],r['outer_radius']['value'])
    for key,value in [('width_m',b['width_m']),('length_m',b['length_m']),('aspect_ratio',b['aspect_ratio'])]:
        if not math.isclose(eq[key],value,rel_tol=1e-6):
            raise ValueError(f'Stale DERIVED equivalent blade {key}: captured {eq[key]}, inputs give {value}')
    sh=s['forward_shield'];shield_r=sh['diameter']['value']/2
    if not math.isclose(sh['ring_shadow_margin']['value'],shield_r-habitat_ring.outer(s),rel_tol=1e-9):
        raise ValueError('Stale DERIVED ring shadow margin')
    thrust=s['mission']['first_ignition']['max_accel']*g0*s['physics']['departure_mass']['upper_kg']/1e6
    if not math.isclose(s['propulsion']['design_thrust']['value'],thrust,rel_tol=1e-6):
        raise ValueError('Stale DERIVED design thrust')
    flight=s['mission']['first_ignition']['max_accel']*g0*s['physics']['protected_burnout_mass']['value']/1e6
    if not math.isclose(s['propulsion']['flight_thrust']['value'],flight,rel_tol=1e-6):
        raise ValueError('Stale DERIVED flight thrust')
    # Q35: the S&E result (20_FIRST_IGNITION C13/C16) and the Sanity Check reference (01!B13) follow from the linear ramp, never from the 7.75 d label.
    fi=first_ignition.result(s);res=s['mission']['first_ignition_result'];ref=s['mission']['first_ignition_reference']
    for key,value in (('duration_d',fi['duration_d']),('distance_AU',fi['distance_AU'])):
        if not math.isclose(res[key],value,rel_tol=1e-8):
            raise ValueError(f'Stale DERIVED first_ignition_result {key}: captured {res[key]}, the ramp gives {value}')
    if not math.isclose(ref['duration_d'],fi['duration_d'],rel_tol=1e-8):
        raise ValueError(f'The Sanity Check reference duration {ref["duration_d"]} d must equal the S&E result {fi["duration_d"]} d')


SIGMA = thermal_budget.SIGMA
# 20_LASER_POWER columns B/C/F reference these 02_EYE_INPUTS rows.
LASER_INPUTS = {'SURVEY_LIDAR': ('survey_pulse_energy_J', 'survey_rep_rate_Hz', None),
                'BURN_WATCH': ('hazard_pulse_energy_J', 'hazard_rep_rate_Hz', None),
                'EMERGENCY_ABLATION': (None, None, 'ablation_optical_power_W')}


def validate_sourced_budgets(s):
    """Captured mass, EYE power and drive-heat rows must reproduce the workbook formulas that tie them together."""
    def close(a, b):
        return math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-9)
    ph=s['physics'];budget=ph['mass_budget'];items={i['id']:i for i in budget['items']}
    if len(items) != len(budget['items']) or not all(i['mass_kg'] > 0 and 0 <= i.get('rotating_allowance_kg',0) <= i['mass_kg'] for i in items.values()):
        raise ValueError('Mass budget items')
    if not close(sum(i['mass_kg'] for i in items.values()), ph['protected_burnout_mass']['value']):
        raise ValueError('Mass budget does not sum to the protected burnout mass')
    if not close(sum(i.get('rotating_allowance_kg',0) for i in items.values()), ph['rotor_sizing']['mass_kg']):
        raise ValueError('Rotating allowances do not sum to the rotating-system mass')
    if budget['positions_known'] or ph['center_of_mass'].get('known') is not False:
        raise ValueError('Mass budget carries no positions; centre of mass must stay unknown')
    regions={i['id']:i for i in ph['mass_regions']['items']}
    if set(regions) != set(items) or any(not close(regions[k]['rotating_kg'], items[k].get('rotating_allowance_kg',0)) for k in items):
        raise ValueError('Mass regions must cover every budget item with its rotating allowance')
    failures=owner_targets.budget_failures(s)
    if failures:
        raise ValueError(f'Mass basis (Q32): {failures}')
    for group in ['eye', 'brow']:
        m=s[group]['mass']
        if m['budget_item'] not in items or not close(m['value'], items[m['budget_item']]['mass_kg']):
            raise ValueError(f'{group} mass differs from the Wayfarer mass budget')
    e=s['eye'];inp=e['power_inputs'];eff=inp['laser_wall_plug_efficiency']
    if not 0 < eff <= 1 or set(e['laser_modes']) != set(LASER_INPUTS):
        raise ValueError('EYE laser inputs')
    for name, mode in e['laser_modes'].items():
        pulse, rate, cont = LASER_INPUTS[name]
        expected={'pulse_energy_J':inp[pulse] if pulse else 0.0,'rep_rate_Hz':inp[rate] if rate else 0.0,'continuous_optical_W':inp[cont] if cont else 0.0}
        expected['optical_W']=expected['pulse_energy_J']*expected['rep_rate_Hz']*mode['active_facets']+expected['continuous_optical_W']
        expected['electrical_W']=expected['optical_W']/eff
        expected['waste_heat_W']=max(0.0,expected['electrical_W']-expected['optical_W'])
        if not 0 < mode['active_facets'] <= e['facet_count'] or not all(close(mode[k], v) for k, v in expected.items()):
            raise ValueError(f'Stale EYE laser mode {name}')
    for name, mode in e['facet_modes'].items():
        if len(mode['facet_roles']) != e['facet_count']:
            raise ValueError(f'EYE facet mode {name} must assign every facet')
    lm=e['laser_modes'];active=inp['active_non_laser_W'];demand=e['electrical_demand']
    for key, mode in [('survey_W','SURVEY_LIDAR'),('burn_watch_W','BURN_WATCH'),('ablation_W','EMERGENCY_ABLATION')]:
        if not close(demand[key], lm[mode]['electrical_W']+active):
            raise ValueError(f'Stale EYE electrical demand {key}')
    if not close(demand['ablation_laser_waste_heat_W'], lm['EMERGENCY_ABLATION']['waste_heat_W']):
        raise ValueError('Stale EYE ablation waste heat')
    r=s['radiators'];cal=r['drive_heat_calibration']
    heat=s['propulsion']['field_calibration_power']['value']*s['propulsion']['internal_waste_heat_fraction']['value']
    area=thermal_budget.ideal_area_m2(heat,r['emissivity']['value'],r['temperature']['value'])
    if not close(cal['absorbed_heat_W'], heat) or not math.isclose(cal['ideal_area_m2'], area, rel_tol=1e-9):
        raise ValueError('Stale DIAGNOSTIC drive heat calibration')
    if r['drive_waste_heat'].get('known') is not False:
        raise ValueError('Operating drive waste heat is OPEN; the calibration value must not fill it')
    # 40_THERMAL B45 (DIAGNOSTIC, owner truncates to whole watts): ideal rejection minus the calibration heat at the 0.90 root emissivity.
    margin=thermal_budget.root_calibration_margin_W(s)
    if not math.isclose(r['root_calibration_margin']['value'], margin, rel_tol=0, abs_tol=1.0):
        raise ValueError(f'Stale DIAGNOSTIC root calibration margin: captured {r["root_calibration_margin"]["value"]}, inputs give {margin}')
    if r['emissivity']['value'] != 0.9:
        raise ValueError('Root emissivity stays the 0.90 conservative baseline until OD-023 qualifies a higher value')
    target=r['emissivity_target']
    if target['build_input'] is not False or not r['emissivity']['value'] < target['candidate_low'] <= target['candidate_high'] <= 1:
        raise ValueError('The nano-skin emissivity target is a candidate, not a build input, and lies above the root baseline')
    for key in ['angular_emission']:
        if r[key].get('known') is not False or 'value' in r[key]:
            raise ValueError(f'radiators.{key} is OPEN')
    if r['thermal_expansion']['allowance'].get('known') is not False:
        raise ValueError('The thermal expansion allowance is OPEN (R6, OD-007)')
    z=r['variable_emissivity_zoning']
    if z['permitted_model_zones'] != ['ROOT_TRANSITION'] or z['forbidden_model_zones'] != ['HOT_FACE']:
        raise ValueError('Variable emissivity is permitted only in the cooler root transition, never on the hot face')
    if r['cell_isolation']['isolatable_cells'] is not True:
        raise ValueError('Radiator cells are isolatable (40_THERMAL A26)')


def _ref(s, path):
    node = s
    for part in path.split('.'):
        node = node[part]
    return node


def validate_aft_answers(s):
    """AFT-011 stage A1: the owner's aft answers (Q12-Q27, Q34, Q36) are recorded as data and checked against each other and against the
    PROTOTYPE screen. Nothing here feeds a generator; the Q52 as-built net area is DERIVED by radiator_net_area."""
    def require(condition, message):
        if not condition:
            raise ValueError(message)
    def unknown(node, name):
        require(node.get('known') is False and 'value' not in node and node['canon_status'] == 'OPEN', f'{name}: OPEN, no value')
    p, r, dm = s['propulsion'], s['radiators'], s['drive_manifold']
    man = p['manifold']
    # Nozzle quadrant map (Q22) = the EYE facet grammar; the 20/30/20/30 example is a yaw couple under it.
    nmap = man['nozzle_map']
    require(nmap['quadrants'] == s['eye']['facet_map']['quadrants'] and len(nmap['labels']) == len(nmap['quadrants']) == p['nozzle_count'], 'nozzle_map: quadrants must equal the EYE facet map')
    shares = man['example_maneuver']['shares']
    pitch = sum(x*qz for x, (qy, qz) in zip(shares, nmap['quadrants']))
    yaw = sum(x*qy for x, (qy, qz) in zip(shares, nmap['quadrants']))
    require(math.isclose(pitch, 0.0, abs_tol=1e-12) and abs(yaw) > 1e-6, 'nozzle_map: the 20/30/20/30 example must be a yaw couple')
    # Nozzle labels are the owner map (WORKING, Q22); each pickup node keeps one fixed azimuth offset from its nozzle (the pickups follow Nk).
    require(dm['nozzle_label_status'] == 'WORKING', 'drive_manifold.nozzle_label_status: the owner N1-N4 map is WORKING')
    st_, pr_ = s['structure'], s['prototype']
    offsets = {round((pr_['ring_phase_deg']+n*360/st_['ring_nodes']-math.degrees(math.atan2(qz, qy))) % 360, 6) % 360 for n, (qy, qz) in zip(st_['nozzle_pickup_nodes'], nmap['quadrants'])}
    require(len(offsets) == 1, f'structure.nozzle_pickup_nodes: every pickup must sit at the same azimuth offset from its nozzle, got {sorted(offsets)}')
    # Throat (Q25): drive_manifold reads the WORKING throat_geometry and carries no copy; the field profile stays OPEN.
    require(not any(k.startswith('throat_') for k in dm), 'drive_manifold must not carry throat keys: read propulsion.manifold.throat_geometry')
    unknown(man['throat_field_profile'], 'manifold.throat_field_profile')
    # Nozzle placement (Q26): the paths resolve; drive_manifold.check compares the geometry with the owner's figures.
    npl = man['nozzle_placement']
    for path in npl['applies_to']:
        node = s
        for part in path.split('.'):
            require(isinstance(node, dict) and part in node, f'nozzle_placement.applies_to: {path} does not resolve')
            node = node[part]
    # Channel-loss recovery (Q27).
    rec = man['channel_loss_recovery']
    require(rec['surviving_channels'] == 2 and math.isclose(rec['surviving_thrust_fraction'], rec['surviving_channels']*man['nominal_share']), 'channel_loss_recovery: two channels at their nominal share')
    # Vector study (Q27): ordered, DIAGNOSTIC emergency limit, no adopted range.
    vs = p['nozzle_vector_study']
    require(0 < vs['normal_deg'] < vs['emergency']['limit_deg'] < 90 and vs['emergency']['canon_status'] == 'DIAGNOSTIC' and 'source_ref' not in vs['emergency'], 'nozzle_vector_study: 0 < normal < emergency < 90, emergency DIAGNOSTIC')
    unknown(p['vectoring_range'], 'propulsion.vectoring_range')
    # Plasma-facing stack (Q17): ranges ordered, PROTOTYPE liners inside them.
    st, hs = p['plasma_facing']['stack_thickness'], s['drive_hot_section']
    require(0 < st['core_low_m'] < st['core_high_m'] and 0 < st['throat_low_m'] < st['throat_high_m'], 'stack_thickness: low < high')
    require(st['core_low_m'] <= hs['core_liner_thickness_m'] <= st['core_high_m'] and st['throat_low_m'] <= hs['throat_liner_thickness_m'] <= st['throat_high_m'], 'drive_hot_section: liner thickness outside the WORKING stack range')
    # Spine termination (Q21, Q23), optical service (Q24, Q34), pickups (Q18), injection and inventories (Q20).
    sp = p['spine_termination']
    require(sp['central_bore'] is False and sp['spine_side_liner'] is False, 'spine_termination: no central bore and no spine-side liner')
    osv = man['optical_service']
    require(osv['route_count'] == man['optical_control']['source_count'] and osv['shared_combiner'] is False, 'optical_service: one route per source and no shared combiner')
    unknown(osv['cartridge_geometry'], 'optical_service.cartridge_geometry')
    require('nozzle axis' in p['nozzle_pickup']['forbidden_attachments'] and 'superconducting coil windings' in p['nozzle_pickup']['forbidden_attachments'], 'nozzle_pickup: not on the axis or the windings')
    require(len(p['inventories']['separate']) == 4 and 'reaction_mass' in p['injection'] and 'fusion_fuel' in p['injection'], 'inventories: four separate inventories and both injection points')
    # AFT-007: the build follows the answers. The spine ends on the hub, hydrogen goes to the injection ring and D/3He to the core, and
    # the cartridge/nozzle-yoke rows are PROTOTYPE data of the drive tables.
    import drive_hot_section as hot
    hsec = s['drive_hot_section']
    require(drive_manifold.spine_span(s)[0] == layout.at(s, dm['hub_forward_x']), 'spine_termination: the spine ends on the hub face (drive_manifold.hub_forward_x)')
    require(set(hsec['tank_families']) == hot.inventory_families(s) and sorted(hsec['tank_families']) == ['deuterium', 'helium-3', 'hydrogen', 'hydrogen'],
            'inventories: tank_families must cover the separate inventories (water excluded), hydrogen in two tanks')
    require([f == 'hydrogen' for f in hsec['tank_families']] == [t_ == 'injection_ring' for t_ in hsec['feed_terminus']], 'injection: hydrogen to the injection ring, D and 3He to the core')
    require('injection ring' in p['injection']['reaction_mass']['point'] or 'downstream' in p['injection']['reaction_mass']['point'], 'injection: reaction mass is injected downstream of the burn')
    stack = p['cryogenic_feed']['storage_stack']
    require(all(w not in json.dumps([stack['insulation'], stack['sensing'], stack['refrigeration']]) for w in ('nanoporous', 'leak', 'boil')) and bool(stack.get('interface_wording')), 'storage_stack: strings follow 14!C22; the 06!C46 wording is kept apart')
    unknown(p['cryogenic_feed']['streaming_dose'], 'cryogenic_feed.streaming_dose')
    for node, name in [(r['thermal_expansion']['allowance'], 'allowance'), (r['thermal_expansion']['material_cte'], 'material_cte'), (r['root_band']['temperature_map'], 'root_band.temperature_map'),
                       (s['thermal']['loops']['warm']['area'], 'warm area'), (s['thermal']['loops']['cold']['area'], 'cold area'), (r['drive_waste_heat'], 'drive_waste_heat')]:
        unknown(node, name)
    # Compliance (Q12, Q15).
    dc, ad = r['thermal_expansion']['distributed_compliance'], r['thermal_expansion']['axial_datum']
    lo, hi = dc['local_travel_range_m']
    require(lo <= dc['local_travel_m'] <= hi and (r['geometry']['major_bays']-1)*dc['local_travel_m'] >= dc['aggregate_envelope_m'], 'distributed_compliance: travel inside its range and covering the aggregate envelope')
    require(ad['datums_per_blade'] == 1, 'axial_datum: one datum per blade')
    # Joints and root band (Q13, Q14); the physical area is never shrunk.
    bj, rb = r['bay_joints'], r['root_band']
    require(0 < bj['width_low_m'] < bj['width_high_m'] and bj['emitting'] is False, 'bay_joints: ordered width range, non-emitting')
    require(0 < rb['width_m'] < r['equivalent_blade']['width_m'] and rb['counted_in_hot_area'] is False, 'root_band: narrower than the blade, not counted in the hot area')
    require(math.isclose(r['nominal_net_area']['value'], 5000.0, rel_tol=1e-12), 'radiators.nominal_net_area is the owner\'s nominal 5,000 m2 net target (Q52)')
    require(bj['width_low_m'] < bj['width_working_m'] < bj['width_high_m'], 'bay_joints: working seam inside the range (07!D60)')
    # Q52 option D: the recorded as-built net area equals the pure recomputation, and the effective area derives from it.
    check, want = r['as_built_net_area'], radiator_net_area.as_built(s)
    require(check['canon_status'] == 'DERIVED', 'as_built_net_area: DERIVED')
    for key, values in want.items():
        require(len(check[key]) == len(values) and all(math.isclose(a, b, rel_tol=1e-9) for a, b in zip(check[key], values)), f'as_built_net_area.{key} differs from radiator_net_area.as_built')
    require(math.isclose(r['effective_area']['value'], want['net_area_m2'][1]*r['count']*r['emitting_faces']*r['view_factor']['value'], rel_tol=1e-9), 'radiators.effective_area: as-built net area x blades x faces x view factor (40!B7, 07!D62)')
    # Three heat-rejection regimes (Q36): ordered temperatures, owner examples equal the formula, contiguous defense bands, references resolve.
    loops = s['thermal']['loops']
    hot_t = _ref(s, loops['hot']['temperature_ref'])['value']
    _ref(s, loops['hot']['area_ref'])
    require(hot_t > loops['warm']['temperature_K'] > loops['cold']['temperature_K'] > 0, 'thermal.loops: hot > warm > cold temperature')
    for name, owner in (('warm', 2390.0), ('cold', 187.0)):
        ex = loops[name]['example']
        ideal = thermal_budget.ideal_area_m2(ex['load_W'], ex['emissivity'], loops[name]['temperature_K'])
        require(math.isclose(ex['ideal_area_m2'], ideal, rel_tol=1e-9) and abs(ex['ideal_area_m2']-owner) < 1.0, f'thermal.loops.{name}.example: ideal area')
    df = loops['defense_routing']
    bands = [df['normal_W'], df['limited_duty_W'], df['short_burst_W']]
    require(all(b[0] < b[1] for b in bands) and bands[0][1] == bands[1][0] and bands[1][1] == bands[2][0], 'defense_routing: contiguous ascending bands')
    thermal_loops.check_study(s)
    fails = warm_panels.check(s)[1]
    require(not fails, f'thermal.loops.candidate_panels (Q38): {fails}')


def validate(s, source_map):
    def require(condition, message):
        if not condition:
            raise ValueError(message)
    require(s['schema_version'] == 5, 'Unsupported schema')
    require(source_map.get('schema_version') == s['schema_version'], 'Source map schema mismatch')
    c = s['coordinates']
    require((c['length_unit'], c['forward_axis'], c['up_axis'], c['left_axis']) == ('m', '+X', '+Z', '+Y'), 'Coordinate units/axes')
    require(s['representation'] == 'REP_PROXY', 'P0 only supports REP_PROXY')
    source_records = source_map['sources']
    def walk(node, path=''):
        if isinstance(node, dict):
            if 'canon_status' in node:
                require(node['canon_status'] in STATUSES, f'{path}: status')
            if 'source_ref' in node:
                ref = node['source_ref']
                require(ref in source_records, f'{path}: unresolved source {ref}')
                require(node['canon_status'] == source_records[ref]['canon_status'], f'{path}: source status mismatch')
            if 'evidence_ref' in node:
                # Evidence rows may carry a sourced status while this sub-value stays OPEN.
                require(node['evidence_ref'] in source_records, f'{path}: unresolved evidence {node["evidence_ref"]}')
            if 'lower_kg' in node:
                require(0 < node['lower_kg'] <= node['upper_kg'], f'{path}: sourced range order')
            if node.get('known') is False:
                require('value' not in node, f'{path}: unknown cannot have numeric value')
            if 'min' in node:
                require(node['min'] <= node['value'] <= node['max'], f'{path}: outside source envelope')
                require(node['selection_status'] == 'PROTOTYPE', f'{path}: selection must be prototype')
            for key, value in node.items():
                walk(value, f'{path}.{key}')
        elif isinstance(node, list):
            for value in node:
                walk(value, path)
    walk(s)
    for group, key, unit in [('ship', 'length', 'm'), ('ship', 'body_diameter', 'm'), ('eye', 'aperture', 'm'), ('eye', 'array_baseline', 'm'), ('radiators', 'physical_area', 'm2'), ('radiators', 'outer_radius', 'm'), ('radiators', 'root_radius', 'm'), ('forward_shield', 'diameter', 'm'), ('radiators', 'effective_area', 'm2'), ('radiators', 'view_factor', 'ratio'),
                             ('mission', 'target_speed', 'c'), ('mission', 'duration', 'yr'), ('physics', 'protected_burnout_mass', 'kg'), ('propulsion', 'design_thrust', 'MN'), ('propulsion', 'flight_thrust', 'MN'), ('habitat', 'low_thrust_limit', 'g'), ('habitat', 'outer_radius', 'm'), ('habitat', 'floor_radius', 'm'), ('habitat', 'mass_radial_depth', 'm'), ('radiators', 'temperature', 'K'), ('radiators', 'emissivity', 'ratio'),
                             ('eye', 'mass', 'kg'), ('brow', 'mass', 'kg'), ('propulsion', 'field_calibration_power', 'W'), ('propulsion', 'internal_waste_heat_fraction', 'ratio')]:
        field = s[group][key]
        require(field['unit'] == unit, f'{group}.{key}: unit')
        require(math.isfinite(field['value']) and field['value'] > 0, f'{group}.{key}: positive finite value required')
    require(s['crew']['count'] == 6, 'Locked crew count')
    occupancy = s['crew']['rated_occupancy']
    require(occupancy['unit'] == 'persons' and type(occupancy['value']) is int and occupancy['value'] >= s['crew']['count'], 'Rated occupancy is a whole number of persons, at least the story manifest')
    for key, count in [('core_count', 1), ('common_region_count', 1), ('manifold_count', 1), ('channel_count', 4), ('nozzle_count', 4)]:
        require(s['propulsion'][key] == count, f'Locked {key}')
    require(s['eye']['facet_count'] == 4 and s['brow']['count'] == 1, 'EYE/Brow counts')
    quads = [tuple(q) for q in s['eye']['facet_map']['quadrants']]
    require(len(quads) == s['eye']['facet_count'] == len(s['eye']['facet_map']['labels']) and set(quads) == {(1, 1), (-1, 1), (1, -1), (-1, -1)}, 'EYE facet map must name each quadrant once')
    require(s['radiators']['count'] == 3 and s['radiators']['emitting_faces'] == 2 and s['radiators']['separation_deg'] == 120, 'Radiator baseline architecture')
    require(s['radiators']['view_factor']['value'] <= 1, 'View factor cannot exceed one')
    p = s['prototype']
    require(p['status'] == 'PROTOTYPE' and p['unit'] == 'm', 'Prototype labeling/units')
    for key, value in p.items():
        if key.endswith('_m') and isinstance(value, (int, float)):
            require(math.isfinite(value) and value > 0, f'{key}: positive dimension')
    for key in ['radiator_longitudinal_cells', 'radiator_transverse_cells']:
        require(type(p[key]) is int and p[key] > 0, f'{key}: positive integer')
    layout_failures = layout.check(s)
    require(not layout_failures, f'Layout datums: {layout_failures}')
    stale = stale_position_keys(s)
    require(not stale, f'Positions must be {{datum, offset_m}} (layout.py), not fractions or bare metres: {stale}')
    stations = s['layout']['stations']
    require(len({x['id'] for x in stations}) == len(stations), 'Duplicate station IDs')
    length = s['ship']['length']['value']
    station_xs = [layout.at(s, x['x']) for x in stations]
    require(all(-length/2-1e-9 <= x <= length/2+1e-9 for x in station_xs) and all(station_radius_ok(x) for x in stations), 'Station envelope')
    # Q2 (2026-10-03b): the 220-240 m envelope INCLUDES the Dust Lance, so it bounds the overall length (aft end to Lance tip), not the body value.
    overall = forward_shield.overall_length(s)
    require(length > 0 and 220 <= overall <= 240 and s['ship']['length']['min'] == 220 and s['ship']['length']['max'] == 240,
            'Overall ship length INCLUDING the Dust Lance must stay inside the 220-240 m WORKING envelope')
    require(all(a < b for a, b in zip(station_xs, station_xs[1:])), 'Station order')
    require(type(p['radiator_ribbon_count']) is int and 1 <= p['radiator_ribbon_count'] <= 2, 'Study ribbon count')
    d = derived(s)
    h = s['habitat']; g = s['radiators']['geometry']; st = s['structure']
    gap = p['mechanical_clearance_m']
    require(habitat_ring.ring_count(s) == 2, 'Two rigid rings')
    for value in [habitat_ring.floor(s), habitat_ring.outer(s), habitat_ring.depth(s), h['rpm'], *[v for k,v in g.items() if k.endswith('_m')]]:
        require(math.isfinite(value) and value > 0, 'Positive finite geometry')
    require(habitat_ring.outer(s) > habitat_ring.floor(s), 'The ring outer radius lies outside the occupied floor')
    ring_failures = habitat_ring.check(s)
    require(not ring_failures, f'Habitat rings: {ring_failures}')
    lay = h['layout']
    # 12!A16:A17 DERIVED usable volume per rated and per story occupant.
    density = h['occupancy_density']
    require(math.isclose(density['usable_per_rated_person_m3'], lay['usable_working_m3']/occupancy['value'], rel_tol=1e-9) and
            math.isclose(density['usable_per_story_person_m3'], lay['usable_working_m3']/s['crew']['count'], rel_tol=1e-9), 'Stale DERIVED usable volume per person')
    refuge = s['shielding']['refuge']
    require(refuge['capacity_persons'] >= occupancy['value'], 'Refuge must hold the rated occupancy')
    require(hull_geometry.refuge(s)['pressure_volume_m3'] >= refuge['capacity_persons']*refuge['volume_per_person_m3'], 'Refuge pressure volume below the WORKING per-person volume (Q31)')
    require(p['dock_radius_m'] >= p['dock_clear_radius_m']+s['crew_transfer']['passage_wall_m']-1e-12, 'Dock fitting outer radius must hold the clear passage plus the passage wall')
    # 08_ROTATING_HABITAT H54 / 15_MODEL_INTERFACES E5 quote ~11.29 degrees at 28 m / 4 rpm for 0.1 g.
    require(abs(d['low_thrust_gravity_tilt_deg'] - 11.29) < 0.05, 'Low-thrust gravity tilt no longer matches the owner note')
    require(abs(habitat_ring.tilt_deg(s, s['mission']['first_ignition']['max_accel']) - 71.5) < 0.05, '08!H37 ~71.5 deg high-thrust tilt')
    failures = cabin_atmosphere.check(s); require(not failures, f'Cabin atmosphere: {failures}')
    require(type(g['major_bays']) is int and g['major_bays'] > 0 and p['radiator_longitudinal_cells'] % g['major_bays'] == 0, 'Radiator structural bays / thermal cells')
    require(p['radiator_transverse_cells'] % p['radiator_ribbon_count'] == 0, 'Thermal cells divisible across ribbons')
    require(type(p['radiator_ribbon_count']) is int and 1 <= p['radiator_ribbon_count'] <= 2, 'Study ribbon count')
    require(0 <= p['radiator_axis_cant_deg'] <= 3, 'Prototype axis-cant study range')
    rows, ribbons = p['radiator_root_band_cell_rows'], p['radiator_ribbon_count']
    require(type(rows) is int and 1 <= rows <= p['radiator_transverse_cells']//ribbons - 1, 'Root band rows: integer in 1..transverse cells per ribbon - 1')
    require(type(p['radiator_fixed_datum_root']) is int and p['radiator_fixed_datum_root'] in (-1, 1), 'Fixed datum root must be -1 (aft) or +1 (forward)')
    require(p['coolant_trunk_bellows_radius_m'] > thermal_geometry.TRUNK_RADIUS_M, 'Trunk bellows must be wider than the trunk')
    bell=p['coolant_trunk_bellows_radius_m']
    require(bell <= thermal_geometry.FEED_TRUNK_Z - p['radiator_thickness_m']/2 + 1e-12, 'Trunk bellows must not pierce the sheet (radius <= trunk height - half thickness)')
    require(thermal_geometry.FEED_TRUNK_V - bell - p['radiator_mount_block_m']/2 >= p['mechanical_clearance_m'] - 1e-12, 'Trunk bellows must clear the stay and root mount blocks')
    require(len(thermal_geometry.bay_joints(s, d)) == g['major_bays'] - 1, 'One expansion joint per interior bay boundary')
    checks=thermal_geometry.screen(s,d)
    require(checks['screen_pass'], f'Blade envelope fails the shadow/casing/ring/exclusion screen: {[k for k, v in checks["checks"].items() if not v]}')
    for xr in [-g['root_station_separation_m']/2,g['root_station_separation_m']/2]:
        require(d['aft_x_m'] < d['mount_x_m']+xr < d['front_x_m'], 'Root station outside blade')
    require(all(st['spine_diameter_min_m'] <= 2*r <= st['spine_diameter_max_m'] for r in (p['spine_radius_m'], p['spine_core_radius_m'])), 'Spine envelope (aft and core)')
    require(st['ring_nodes'] == 12 and st['ring_od_m'] <= s['ship']['body_diameter']['value'], 'Aft ring envelope')
    offsets=st['transition_frame_offsets_m']
    require(offsets[0] == 0 and all(a < b for a, b in zip(offsets, offsets[1:])) and offsets[-1] == st['transition_length_m'], 'Transition frames')
    for key, count in [('nozzle_pickup_nodes', s['propulsion']['nozzle_count']), ('sector_pickup_nodes', s['radiators']['count'])]:
        nodes=st[key]
        require(len(nodes) == count == len(set(nodes)) and all(type(n) is int and 0 <= n < st['ring_nodes'] for n in nodes), f'{key}: ring nodes')
    for j, node in enumerate(st['sector_pickup_nodes']):
        require(math.isclose((p['radiator_phase_deg']+j*s['radiators']['separation_deg']) % 360, node*360/st['ring_nodes']), 'Radiator sectors must sit on sector pickup nodes')
    require(-.5 <= p['radiator_root_station_blade_fraction'] <= .5, 'Root station blade fraction')
    bays = p['radiator_stay_bays']
    require(isinstance(bays, list) and all(type(k) is int and 1 <= k < g['major_bays'] for k in bays) and all(a < b for a, b in zip(bays, bays[1:])), 'Stay bays: strictly increasing integers inside 1..major_bays-1')
    at = thermal_geometry.stations(s, d)
    cage_x0 = layout.at(s, p['thrust_ring_x']) + offsets[-1]
    root_clear = 2*p['radiator_boom_radius_m'] + gap
    require(all(cage_x0 < x <= layout.at(s, p['outer_cage_end_x']) for x in at['roots'] + at['stays']), 'Root and stay stations must lie inside the primary cage')
    require(all(abs(xs-xr) >= root_clear for xs in at['stays'] for xr in at['roots']), 'Stays too close to a root boom')
    bus=s['power']['bus_names']
    require(len(bus) == s['power']['generator_count'] == len(set(bus)), 'Power bus names')
    half = habitat_ring.sweep_half(s)
    centers = habitat_ring.centers(s)
    cage_end = layout.at(s, p['outer_cage_end_x']); mount_aft = layout.at(s, p['forward_mount_aft_x']); mount_fwd = layout.at(s, p['forward_mount_fwd_x'])
    require(len(centers) == 2 and len(p['rotor_phase_deg']) == 2 and all(math.isfinite(x) for x in centers), 'Rotor stations')
    require(centers[1]-centers[0] >= 2*half+gap, 'Rotor axial sweep overlap')
    eye_rear = length/2-p['eye_front_inset_m']-p['eye_module_depth_m']-p['eye_backing_depth_m']
    require(centers[1]+half+gap < eye_rear, 'Habitat intersects forward EYE support')
    require(cage_end <= min(centers)-half-gap, 'Outer cage enters rotor sweep')
    require(max(centers)+half+gap <= mount_aft < mount_fwd < eye_rear, 'Forward mount struts')
    require(p['forward_mount_inner_radius_m'] < p['forward_mount_outer_radius_m'] <= s['ship']['body_diameter']['value']/2, 'Forward mount radii')
    require(s['power']['generator_count']==2 and s['power']['habitat_motor_count']==habitat_ring.ring_count(s), 'Power architecture')
    rules=s['operating_rules']
    require(rules['habitat']['high_power_habitat_stopped_locked'] and rules['habitat']['ring_retraction'] is False and rules['radiators_fixed_all_modes'] and rules['radiator_deployment_mechanism'] == 'NONE' and not rules['hot_articulation'], 'Operating rules')
    validate_configurations(s)
    require(s['interior']['status'] == 'PROTOTYPE', 'Interior layout must stay PROTOTYPE')
    # Geometry fit screens (interior, hull, drive manifold, power storage, rotor interface, crew transfer) are not
    # input validation: run them on demand with each module's __main__; inspect.py checks the built geometry.
    # P1F optically gated manifold: WORKING optical layer on the LOCKED four-way topology; geometry and controls PROTOTYPE.
    man, dm = s['propulsion']['manifold'], s['drive_manifold']
    require(dm['status'] == 'PROTOTYPE' and dm['unit'] == 'm' and dm['nozzle_label_status'] == 'WORKING', 'Drive manifold geometry must stay PROTOTYPE with WORKING owner nozzle labels')
    oc = man['optical_control']
    require(oc['direction'] == '-X' and oc['source_count'] == 2 and oc['gate_count'] == s['propulsion']['channel_count'] and oc['throat_count'] == 1 and man['optical_distributor']['count'] == 1, 'Optical control counts/direction')
    require(man['physical_plasma_pipes'] == 0 and man['architecture'] == 'four_way_magnetic', 'Manifold topology')
    for shares in [[man['nominal_share']]*4, man['example_maneuver']['shares']]:
        require(len(shares) == s['propulsion']['nozzle_count'] and all(0 <= x <= 1 for x in shares) and math.isclose(sum(shares), 1.0), 'Flux shares must sum to 1')
    require(all(man[k].get('known') is False for k in ['optical_power', 'optical_wavelength', 'gate_response_time', 'optical_to_lattice_coupling', 'throat_field_profile']), 'Optical ratings, coupling and the throat field profile stay OPEN')
    require(dm['nozzle_labels'] == [f'Nozzle_{j:02}' for j in range(1, 5)] and type(dm['branch_samples']) is int and dm['branch_samples'] >= 8, 'Drive manifold labels/samples')
    for key in ['nominal_laser_share', 'nominal_gate_command']:
        require(0 < dm[key] <= 1, f'{key}: normalized')
    # P1-006 display throttle: a display curve over the sourced acceleration limits; drive outputs stay unknown.
    require(0 < dm['thrust_display_exponent'] <= 1, 'thrust_display_exponent: display curve in (0, 1]')
    require(s['physics']['drive_outputs'].get('known') is False and 'value' not in s['physics']['drive_outputs'], 'Drive outputs (exhaust velocity, mass flow) stay OPEN')
    for key, value in dm.items():
        if key.endswith('_m') and isinstance(value, (int, float)):
            require(math.isfinite(value) and value > 0, f'drive_manifold.{key}: positive dimension')
    # AFT-002 conventional HTS coils, plasma-facing refractory and cryogenic feed: WORKING architecture, BASELINE 5 T anchor, OPEN design quantities.
    hs = s['drive_hot_section']
    require(hs['status'] == 'PROTOTYPE' and hs['unit'] == 'm' and 'source_ref' not in hs and 'canon_status' not in hs and bool(hs.get('rationale')), 'drive_hot_section is PROTOTYPE with no source_ref and a rationale')
    for key, value in hs.items():
        if key.endswith('_m'):
            require(isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value > 0, f'drive_hot_section.{key}: positive dimension')
        if key.endswith(('_modules', '_segments')):
            require(type(value) is int and value > 0, f'drive_hot_section.{key}: positive integer')
    require(type(hs['pickup_attach_yoke']) is int and 0 <= hs['pickup_attach_yoke'] < 4, 'drive_hot_section.pickup_attach_yoke: nozzle yoke index 0..3')
    require(type(hs['yoke_strap_count']) is int and hs['yoke_strap_count'] >= 3, 'drive_hot_section.yoke_strap_count: at least three straps')
    require(len(hs['tank_families']) == len(hs['feed_terminus']) == 4 and set(hs['feed_terminus']) <= {'core', 'injection_ring'} and hs['h2_outward_jog'] and set(hs['h2_outward_jog']) <= {'aft', 'forward'}
            and len(hs['h2_outward_jog']) == hs['feed_terminus'].count('injection_ring'), 'drive_hot_section: tank families, termini and hydrogen jogs')
    require(all(isinstance(dm[k], dict) and set(dm[k]) == {'A', 'B'} for k in ('splitter_x', 'route_heads_deg', 'route_run_angles_deg')) and all(len(dm[k][r]) == 2 for k in ('route_heads_deg', 'route_run_angles_deg') for r in 'AB'), 'drive_manifold: route tables carry A and B with two legs each')
    require('spine_plasma_clearance_m' not in dm and dm['hub_radius_m'] > p['spine_radius_m'] and dm['route_jog_m'] > 2*dm['optical_channel_radius_m'], 'drive_manifold: terminated hub wider than the spine; a bore jog wider than the bore diameter')
    require(hs['cryo_feed_sleeve_jog_inset_m'] < s['prototype']['shadow_thickness_m']/2, 'drive_hot_section.cryo_feed_sleeve_jog_inset_m: both jogs inside the shield slab')
    sleeve_r = hs['cryo_feed_line_radius_m']+hs['cryo_feed_sleeve_gap_m']
    require(hs['cryo_feed_sleeve_jog_inset_m'] >= sleeve_r, 'drive_hot_section.cryo_feed_sleeve_jog_inset_m: at least the sleeve bore radius (jog legs clear the slab faces)')
    require(s['prototype']['shadow_thickness_m']-2*hs['cryo_feed_sleeve_jog_inset_m'] > 2*sleeve_r, 'drive_hot_section.cryo_feed_sleeve_jog_inset_m: the jog planes must be more than one bore diameter apart (no straight line through both)')
    require(hs['cryo_feed_sleeve_step_m'] > 2*(hs['cryo_feed_line_radius_m']+hs['cryo_feed_sleeve_gap_m']), 'drive_hot_section.cryo_feed_sleeve_step_m: step wider than the sleeve bore')
    require(0 < hs['nozzle_coil_mid_radius_factor'] <= 1, 'drive_hot_section.nozzle_coil_mid_radius_factor in (0, 1]')
    mh = s['propulsion']['magnet_hardware']; cal = mh['seed_field_calibration']
    require(cal['unit'] == 'T' and math.isfinite(cal['value']) and cal['value'] > 0 and cal['canon_status'] == 'BASELINE', 'seed_field_calibration is a positive BASELINE field in T')
    require(not [k for k in mh if 'amplif' in k.lower()] and 'amplif' not in json.dumps({k: v for k, v in cal.items() if k != 'note'}).lower(), 'Lattice amplification is a separate Fiji layer: no amplification value in propulsion.magnet_hardware')
    for section, ref, names in [('magnet_hardware', 'od_024', ['current_density', 'operating_temperature', 'mechanical_stress', 'quench_protection', 'radiation_lifetime']),
                                ('plasma_facing', 'od_025', ['exact_material', 'heat_flux', 'erosion_rate', 'module_size', 'replacement_interval']),
                                ('cryogenic_feed', 'od_026', ['tank_geometry', 'temperatures', 'fuel_split', 'boil_off', 'refrigeration_power', 'transfer_layout', 'streaming_dose'])]:
        for k in names:
            node = s['propulsion'][section][k]
            require(node.get('known') is False and node['canon_status'] == 'OPEN' and node['source_ref'] == ref and 'value' not in node, f'propulsion.{section}.{k}: OPEN, no value, owner {ref}')
    require(all(s['physics'][k].get('known') is False and 'value' not in s['physics'][k] for k in ('reaction_mass', 'fusion_fuel')), 'Reaction mass and fusion fuel inventories stay OPEN')
    validate_derived_sources(s)
    validate_sourced_budgets(s)
    validate_aft_answers(s)
    # FGR-006 forward structure: shield, EYE wells, Dust Lance, diversion/damage displays and the Dustbreak Crown (OPEN values stay unknown).
    forward_shield.validate(s)
    # AFT-005 radiator health display: sequence, presets, fault order and overlay geometry (the blades and every area stay unchanged).
    radiator_health.validate(s)
    display_poses(s)
    # FUT-004 First Ignition timeline: phase order, key segments, thrust-with-locked-rings and the 07!A39 radiator order.
    flight_timeline.validate(s, source_map)
    # OWN-002 (F1) owner answers of 2026-10-03b: mass basis, Q35 timing, WORKING targets and the pending checks owned by FWD-001 / HAB-001.
    for label, failures in (('Owner targets provenance', owner_targets.source_failures(s, source_map)), ('Owner targets', owner_targets.failures(s))):
        require(not failures, f'{label}: {failures}')
    for name, value in source_records.items():
        for key in ['workbook', 'workbook_id', 'url', 'sheet', 'range', 'canon_status', 'inspected_on']:
            require(bool(value[key]), f'Source missing {key}')
        # Schema 5: optional further ranges of the same workbook that state the same fact, as "<sheet>!<A1:B2>".
        for ref in value.get('cross_ranges', []):
            require(isinstance(ref, str) and CROSS_RANGE.fullmatch(ref) is not None, f'{name}: cross_ranges entries are "<sheet>!<A1:B2>"')
    return derived(s)


if __name__ == '__main__':
    data, _, _, _ = load()
    print(json.dumps({'validation': 'PASS', **derived(data), 'hull': hull_geometry.summary(data),
                      'configurations': {k: v.get('habitat', 'NOT BUILDABLE') for k, v in data['configuration'].items()}}, indent=2))
