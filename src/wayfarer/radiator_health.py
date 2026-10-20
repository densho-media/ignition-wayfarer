"""Radiator health display (AFT-005): the thermal-state glow and the isolated/resurfaced cell markers of the fixed radiator blades. Pure geometry.

Layers stay separate. SOURCED: the operating sequence (07!A39 D39/H39, BASELINE), the isolatable cell fact (40!A26), the fault-display permission
(15!G29, 09!F11; OPEN). DERIVED: the cell count and grid, the cell order, the step breakpoints and the diagnostic available-cell fraction below. PROTOTYPE:
the per-configuration thermal_state, the fault order and the 480-cell grid inputs. IMPLEMENTATION: the normalized RADIATOR_HEALTH_CTRL controls and the renderer
offsets and colours (`radiator_health.*`). The blades never move and no area, emissivity or temperature changes with any control: the available
fraction is DIAGNOSTIC display only and never feeds an area or the thermal budget.

Standard library only; thermal_geometry and layout are the shared pure modules the blade recipe already uses.
"""
import math
import thermal_geometry

SUBSYSTEM = 'WF_THERMAL'
CONTROL = 'RADIATOR_HEALTH_CTRL'
PROPS = {'thermal_state': 'Radiator thermal-state display, stepping through the operating sequence (fixed structure, coolant flow, heat admitted, high-power rejection, '
                          'post-shutdown cooldown); display only, no temperature, emissivity or flux (normalized 0-1)',
         'cell_isolation': 'Fraction of the 480 PROTOTYPE thermal cells shown isolated, in a deterministic scattered order (display only; the degraded-mode matrix is OPEN, OD-010)',
         'cell_resurface': 'Fraction of the 480 PROTOTYPE thermal cells shown resurfaced after isolation, in the same order: unqualified and derated (display only; repair rates and durations are unsourced)',
         'cell_requalify': 'Fraction of the 480 PROTOTYPE thermal cells shown requalified after resurfacing, in the same order: back in service, markers hidden (display only; the tests and the interim derate are OPEN, Q42)'}
# Driver variables (short names the simple expressions use) and the control property each one reads.
VARIABLES = {'th': 'thermal_state', 'iso': 'cell_isolation', 'res': 'cell_resurface', 'req': 'cell_requalify'}
STEPS = ('FIXED_STRUCTURE', 'COOLANT_FLOW', 'HEAT_ADMITTED', 'HIGH_POWER_REJECTION', 'POST_SHUTDOWN_COOLDOWN')   # 07!A39 D39 phrases, in order
HIGH_POWER_STEP = 'HIGH_POWER_REJECTION'
DIAGNOSTIC_STATUS = 'DIAGNOSTIC display only; physical area unchanged'
# Hull-side limits shared with the recipe: the overlays sit below the lowest coolant trunk surface and the expansion bead, and below the visibility ray origin.
# Blender passes driver variables as 32-bit floats, so 0.1 * 480 can arrive as 48.0000007. A cell count that lands exactly on a cell boundary must not flip with
# that rounding: a cell counts only when the fraction exceeds its rank by more than EDGE cells (0.001 cell, far above float32 error at 480 cells).
EDGE = .001
RAY_ORIGIN_LIFT_M = .025      # validation/visibility.py: ray origin at thickness/2 + 0.025 m
# Owner references of the fixed-geometry statements and the status each carries in the source map (tests compare them with the source map).
FIXED_GEOMETRY_REFS = {'radiator_fixed_contract': 'BASELINE', 'radiator_no_mechanism': 'BASELINE', 'radiator_eva_fixed': 'BASELINE', 'radiator_fixed_contract_thermal': 'BASELINE'}


def table(s):
    return s['radiator_health']


# ---------- sequence --------------------------------------------------------------------------------------------------

def steps(s):
    return list(s['radiators']['operating_sequence']['steps'])


def step_value(s, k):
    """Control value at which step k is shown exactly: k / (n - 1)."""
    return k/(len(steps(s))-1)


def breakpoints(s):
    """Control values at which the displayed step changes: (k - 0.5) / (n - 1) for k = 1 .. n - 1."""
    n = len(steps(s))
    return [(k-.5)/(n-1) for k in range(1, n)]


def step_index(s, t):
    """Displayed step for a thermal_state value; the input is clamped to [0, 1]."""
    t = min(1.0, max(0.0, float(t)))
    return sum(1 for b in breakpoints(s) if t >= b)


def glow_rgba(s, t):
    return tuple(float(x) for x in table(s)['display']['step_glow_rgba'][step_index(s, t)])


# ---------- cells -----------------------------------------------------------------------------------------------------

def grid(s):
    """(blades, longitudinal cells, transverse cells per blade, ribbons, transverse cells per ribbon)."""
    p = s['prototype']; n = p['radiator_ribbon_count']
    return s['radiators']['count'], p['radiator_longitudinal_cells'], p['radiator_transverse_cells'], n, p['radiator_transverse_cells']//n


def cell_count(s):
    blades, nx, ny, _, _ = grid(s)
    return blades*nx*ny


def stride(s):
    return table(s)['fault_pattern']['cell_order_stride']


def rank(s, g):
    """Position of global cell g in the fault order; a permutation of range(cell_count) when the stride is coprime with the count."""
    return (g*stride(s)) % cell_count(s)


def cells(s):
    """Every thermal cell of every blade, in global order: blade (0-based), ribbon, j (longitudinal), k (within the ribbon), kk (within the blade; the name index),
    the library cell id, zone, global index and fault-order rank."""
    blades, nx, ny, ribbons, ny_r = grid(s); rows = thermal_geometry.root_band(s)['rows']; out = []
    for blade in range(blades):
        for j in range(nx):
            for ribbon in range(ribbons):
                for k in range(ny_r):
                    kk = ribbon*ny_r+k; g = blade*nx*ny+j*ny+kk
                    out.append(dict(blade=blade, ribbon=ribbon, j=j, k=k, kk=kk, g=g, rank=rank(s, g), thermal_cell_id=f'R{ribbon}.CELL.{j:02}.{k:02}',
                                    zone='ROOT_TRANSITION' if ribbon == 0 and k < rows else 'HOT_FACE',
                                    name=f'Radiator_Health_Cell_{blade+1}_{j:02}_{kk:02}', resurfaced_name=f'Radiator_Health_Cell_{blade+1}_{j:02}_{kk:02}_R'))
    return out


def cell_states(s, values):
    """State of every cell (aligned with cells(s)) for a control state, one of radiators.cell_qualification.states (Q42): HEALTHY, ISOLATED,
    RESURFACED (unqualified, derated) or REQUALIFIED. The fractions nest (requalified within resurfaced within isolated); the same strict-inequality
    rule as the drivers."""
    n = cell_count(s); iso, res, req = (values[k]*n for k in ('cell_isolation', 'cell_resurface', 'cell_requalify'))
    def state(r):
        if not iso > r+EDGE:
            return 'HEALTHY'
        if not res > r+EDGE:
            return 'ISOLATED'
        return 'REQUALIFIED' if req > r+EDGE else 'RESURFACED'
    return [state(c['rank']) for c in cells(s)]


def counts(s, values):
    states = cell_states(s, values)
    return {k: states.count(k) for k in s['radiators']['cell_qualification']['states']}


def available_cell_fraction(s, values):
    """DIAGNOSTIC display only: share of cells in service (radiators.cell_qualification.in_service: healthy or requalified). A resurfaced cell is
    derated by an OPEN amount, so it is not counted (Q42). Never an area or a rating."""
    c = counts(s, values)
    return sum(c[k] for k in s['radiators']['cell_qualification']['in_service'])/cell_count(s)


# ---------- overlay geometry (blade-local, identical for every blade) --------------------------------------------------

def sheet_z(s):
    return s['prototype']['radiator_thickness_m']/2


def glow_z(s):
    return sheet_z(s)+table(s)['display']['glow_lift_m']


def marker_z(s):
    return sheet_z(s)+table(s)['display']['marker_lift_m']


def resurfaced_z(s):
    return sheet_z(s)+table(s)['display']['resurfaced_lift_m']


def z_limit(s):
    """Lowest hardware surface above the sheet that an overlay must stay under: the coolant trunk. Since AFT-009 the expansion-joint bead
    lies in the seam gap between cells (radius under half the seam width), so it never sits over a cell's overlay."""
    if s['prototype']['radiator_expansion_joint_radius_m'] >= thermal_geometry.seam_width(s)/2:
        return min(thermal_geometry.FEED_TRUNK_Z-thermal_geometry.TRUNK_RADIUS_M, s['prototype']['radiator_expansion_joint_radius_m'])
    return thermal_geometry.FEED_TRUNK_Z-thermal_geometry.TRUNK_RADIUS_M


def cell_rectangle(s, c):
    """(u0, u1, v0, v1) of one cell, blade-local, as the recipe lays the Blade_Cell sheets out."""
    d = thermal_geometry.blade_of(s); _, nx, _, _, ny_r = grid(s); width = d['ribbon_width_m']
    v_base = c['ribbon']*(width+d['gap_m'])
    return (*thermal_geometry.cell_span(s, d, c['j']), v_base+width*c['k']/ny_r, v_base+width*(c['k']+1)/ny_r)


def marker_rectangle(s, c):
    u0, u1, v0, v1 = cell_rectangle(s, c); f = table(s)['display']['marker_inset_fraction']
    return (u0+(u1-u0)*f, u1-(u1-u0)*f, v0+(v1-v0)*f, v1-(v1-v0)*f)


def quad_pair(u0, u1, v0, v1, z, offset=0):
    """Two quads, one facing +z at +z and one facing -z at -z: (vertices, faces)."""
    vs = [(u0, v0, z), (u1, v0, z), (u1, v1, z), (u0, v1, z), (u0, v0, -z), (u0, v1, -z), (u1, v1, -z), (u1, v0, -z)]
    return [(x, y, zz) for x, y, zz in vs], [(offset, offset+1, offset+2, offset+3), (offset+4, offset+5, offset+6, offset+7)]


def marker_geometry(s, c, resurfaced=False):
    return quad_pair(*marker_rectangle(s, c), resurfaced_z(s) if resurfaced else marker_z(s))


def glow_regions(s):
    """Blade-local (u0, u1, v0, v1) of the hot-face glow: whole ribbons, minus the root-transition band along ribbon 0 (it never glows)."""
    d = thermal_geometry.blade_of(s); length = d['blade_length_m']; width = d['ribbon_width_m']; band = thermal_geometry.root_band(s)['width_m']; out = []
    for ribbon in range(d['ribbons']):
        v0 = ribbon*(width+d['gap_m'])
        out.append((-length/2, length/2, v0+(band if ribbon == 0 else 0.0), v0+width))
    return out


def glow_geometry(s):
    vs = []; fs = []
    for region in glow_regions(s):
        v, f = quad_pair(*region, glow_z(s), len(vs)); vs += v; fs += f
    return vs, fs


def overlay_geometry(s):
    """Blade-local geometry shared by every blade: the glow, and one marker per (ribbon, j, k) cell."""
    return dict(glow=glow_geometry(s), markers={(c['ribbon'], c['j'], c['k']): marker_geometry(s, c) for c in cells(s) if c['blade'] == 0},
                resurfaced={(c['ribbon'], c['j'], c['k']): marker_geometry(s, c, True) for c in cells(s) if c['blade'] == 0})


# ---------- controls, presets, display poses --------------------------------------------------------------------------

def neutral(s):
    return {k: 0.0 for k in PROPS}


def configuration_state(s, name):
    """Control values a buildable preset poses."""
    preset = table(s)['presets'][name]
    return {k: float(preset[k]) for k in PROPS}


def display_pose(s, name):
    """Control values of a preview-only pose: the base preset plus its overrides. Never saved, never a configuration."""
    pose = table(s)['display_poses'][name]
    return {**configuration_state(s, pose['base']), **{k: float(v) for k, v in pose.items() if k in PROPS}}


def preset_names(s):
    return sorted(k for k, v in table(s)['presets'].items() if isinstance(v, dict))


def pose_names(s):
    return sorted(k for k, v in table(s)['display_poses'].items() if isinstance(v, dict))


# ---------- drivers ---------------------------------------------------------------------------------------------------

def glow_steps(s):
    """Steps that show a glow (every step after FIXED_STRUCTURE); each has its own object per blade and a fixed material."""
    return list(range(1, len(steps(s))))


def glow_name(blade, step):
    return f'Radiator_Thermal_Glow_{blade+1}_{step}'


def glow_hidden_expression(s, step):
    """Hide expression of a glow object: hidden outside its step window of th."""
    b = breakpoints(s); lo = f'th<{b[step-1]!r}'
    return lo if step == len(b) else f'({lo}) or (th>={b[step]!r})'


def drivers(s):
    """(object, data path, index, expression). Blender builds exactly these; display() evaluates them. Only visibility is driven: colours are fixed materials."""
    out = []; n = cell_count(s)
    for blade in range(grid(s)[0]):
        for step in glow_steps(s):
            for path in ('hide_viewport', 'hide_render'):
                out.append((glow_name(blade, step), path, -1, glow_hidden_expression(s, step)))
    for c in cells(s):
        # The dark marker shows while the cell is isolated; the pale one sits above it once the cell is resurfaced. A requalified cell is back in
        # service and shows neither (the owner allows a visible patch; the display does not draw it).
        r = c['rank']+EDGE
        for path in ('hide_viewport', 'hide_render'):
            out.append((c['name'], path, -1, f"(iso*{n}<={r!r}) or (req*{n}>{r!r})"))
            out.append((c['resurfaced_name'], path, -1, f"(iso*{n}<={r!r}) or (res*{n}<={r!r}) or (req*{n}>{r!r})"))
    return out


def expression_variables(expression):
    names = set(); token = ''
    for ch in expression+' ':
        if ch.isalnum() or ch == '_':
            token += ch
        else:
            if token in VARIABLES:
                names.add(token)
            token = ''
    return sorted(names)


def display(s, values):
    """Evaluate every driver for a control state: the exact values Blender should show."""
    env = {'min': min, 'max': max, '__builtins__': {}}
    env.update({var: float(values[prop]) for var, prop in VARIABLES.items()})
    return {(obj, path, index): float(eval(expr, env)) for obj, path, index, expr in drivers(s)}


# ---------- validation ------------------------------------------------------------------------------------------------

def validate(s):
    """Spec-level rules of the radiator health display. Raises ValueError on the first failure."""
    def need(ok, message):
        if not ok:
            raise ValueError(message)
    import spec
    r = s['radiators']; seq = r['operating_sequence']; t = table(s); disp = t['display']; ctl = t['controls']; fp = t['fault_pattern']
    need(tuple(seq['steps']) == STEPS and seq['canon_status'] == 'BASELINE' and seq['source_ref'] == 'radiator_operations', 'radiators.operating_sequence: the five D39 steps in order, BASELINE')
    need('Geometry remains unchanged' in seq['rule'], 'radiators.operating_sequence.rule: geometry stays fixed')
    fd = r['fault_display']
    need(fd['canon_status'] == 'OPEN' and fd['source_ref'] == 'radiator_fault_display' and str(fd['degraded_matrix']).startswith('OPEN'), 'radiators.fault_display stays OPEN (OD-010)')
    need(ctl['status'] == 'IMPLEMENTATION' and disp['status'] == 'IMPLEMENTATION' and t['display_poses']['status'] == 'IMPLEMENTATION', 'radiator_health controls, display and poses are IMPLEMENTATION')
    need(t['presets']['status'] == 'PROTOTYPE' and fp['status'] == 'PROTOTYPE', 'radiator_health presets and fault pattern are PROTOTYPE')
    need(set(ctl['names']) == set(PROPS) and len(ctl['names']) == len(PROPS), 'radiator_health.controls.names must equal the control properties')
    n = len(STEPS)
    need(len(disp['step_glow_rgba']) == n and all(len(x) == 4 and all(0 <= v <= 1 for v in x) for x in disp['step_glow_rgba']), 'step_glow_rgba: one RGBA in 0..1 per step')
    em = disp['step_glow_emission']
    need(len(em) == n and all(isinstance(x, (int, float)) and x >= 0 for x in em) and em[0] == 0 and isinstance(disp['resurfaced_emission'], (int, float)) and disp['resurfaced_emission'] >= 0, 'step_glow_emission: one non-negative strength per step, none for FIXED_STRUCTURE; resurfaced_emission non-negative')
    need(em[2] <= .25 and em[2]*disp['step_glow_rgba'][2][3] < em[3]*disp['step_glow_rgba'][3][3], 'The HEAT_ADMITTED glow stays dim (emission <= 0.25) and below the high-power glow, so the cell grid reads in COAST')
    need(disp['step_glow_rgba'][2][3] <= .35, 'The HEAT_ADMITTED glow stays translucent (alpha <= 0.35)')
    need(disp['step_glow_rgba'][0][3] == 0, 'The FIXED_STRUCTURE step shows no glow (alpha 0)')
    need(len(disp['isolated_rgb']) == 3 and len(disp['resurfaced_rgb']) == 3 and all(0 <= v <= 1 for v in disp['isolated_rgb']+disp['resurfaced_rgb']), 'Marker colours are RGB in 0..1')
    need(0 < disp['glow_lift_m'] < disp['marker_lift_m'] < disp['resurfaced_lift_m'] and 0 < disp['marker_inset_fraction'] < .5, 'Glow below markers below repaired markers, positive; inset in (0, 0.5)')
    ray = sheet_z(s)+RAY_ORIGIN_LIFT_M
    need(resurfaced_z(s) < z_limit(s) and resurfaced_z(s) < ray, 'Overlays stay below the coolant trunk, the expansion bead and the visibility ray origin')
    # Fault order: coprime stride, permutation of the cells.
    count = cell_count(s)
    need(type(fp['cell_order_stride']) is int and math.gcd(fp['cell_order_stride'], count) == 1, 'radiator_health.fault_pattern.cell_order_stride must be coprime with the cell count')
    need(sorted(c['rank'] for c in cells(s)) == list(range(count)), 'Cell ranks must be a permutation')
    # Markers sit inside their cells, clear of the mount block and post; the glow stays on the hot face.
    band = thermal_geometry.root_band(s); p = s['prototype']
    for c in cells(s)[:grid(s)[1]*grid(s)[2]]:
        u0, u1, v0, v1 = cell_rectangle(s, c); m = marker_rectangle(s, c)
        need(u0 < m[0] < m[1] < u1 and v0 < m[2] < m[3] < v1, f"{c['name']}: marker inside its cell")
    root_cells = [c for c in cells(s) if c['zone'] == 'ROOT_TRANSITION']
    need(len(root_cells) == band['cells_per_blade']*s['radiators']['count'], 'Root-transition cells follow the root band')
    root_v = min(marker_rectangle(s, c)[2] for c in root_cells)
    need(root_v > p['radiator_mount_block_m']/2 and root_v > thermal_geometry.POST_R, 'Root-band markers clear the mount block and post by their inset')
    need(all(region[2] >= band['width_m']-1e-12 for region in glow_regions(s)[:1]), 'The glow never covers the root transition band')
    # Presets and poses.
    presets = {k: v for k, v in t['presets'].items() if isinstance(v, dict)}
    need(set(presets) == set(spec.buildable_configurations(s)), 'radiator_health.presets must name exactly the buildable configurations')
    names = set(PROPS)
    for name, preset in presets.items():
        need(set(preset) == names and all(0 <= v <= 1 for v in preset.values()), f'{name}: preset controls must be the three normalized controls')
        need(preset['cell_isolation'] == 0 and preset['cell_resurface'] == 0 and preset['cell_requalify'] == 0, f'{name}: no isolated cells in a preset')
        idx = step_index(s, preset['thermal_state'])
        need(preset['thermal_state'] == step_value(s, idx) and idx < n-1, f'{name}: thermal_state sits on a step and never on the cooldown step')
        cfg = s['configuration'][name]
        if cfg.get('thermal_load') == 'MAXIMUM':
            need(STEPS[idx] == HIGH_POWER_STEP, f'{name}: maximum thermal duty shows {HIGH_POWER_STEP}')
        if cfg['drive'] == 'OFF':
            need(idx < STEPS.index(HIGH_POWER_STEP), f'{name}: a drive-off configuration shows less than {HIGH_POWER_STEP}')
    need(presets['HIGH_POWER']['thermal_state'] == .75, 'HIGH_POWER thermal_state is the high-power rejection step (0.75)')
    poses = {k: v for k, v in t['display_poses'].items() if isinstance(v, dict)}
    others = {k for k, v in s['forward_defense']['display_poses'].items() if isinstance(v, dict)}
    for name, pose in poses.items():
        need(pose['base'] in presets and name not in presets and name not in s['configuration'] and name not in others, f'{name}: display poses name a base preset and are never configurations or forward poses')
        values = display_pose(s, name)
        need(all(0 <= v <= 1 for v in values.values()) and values['cell_requalify'] <= values['cell_resurface'] <= values['cell_isolation'], f'{name}: pose values (requalify <= repair <= isolation)')
    # Q41: every buildable configuration has a coolant state of its own, and none is off just because the drive is (40!A69).
    cm = s['radiators']['coolant_modes']
    need({k for k, v in cm.items() if isinstance(v, dict) and 'fluid_status' in v} == set(presets), 'radiators.coolant_modes names exactly the buildable configurations')
    need(all(cm[k]['fluid_status'] in ('CIRCULATING', 'CIRCULATING_UNTIL_SAFE') for k in presets), 'radiators.coolant_modes: the loop is never off by configuration')
    need(STEPS[step_index(s, presets['DOCKED']['thermal_state'])] != 'FIXED_STRUCTURE', 'DOCKED keeps the coolant flowing until safe (11!G6), so it never shows FIXED_STRUCTURE')
    cq = s['radiators']['cell_qualification']
    need(set(cq['in_service']) <= set(cq['states']) and 'RESURFACED' not in cq['in_service'], 'radiators.cell_qualification: a resurfaced cell is never in service before requalification')
    return True


# ---------- contract ---------------------------------------------------------------------------------------------------

def diagnostics(s, values):
    c = counts(s, values)
    return {'isolated': c['ISOLATED'], 'resurfaced': c['RESURFACED'], 'requalified': c['REQUALIFIED'], 'cells': cell_count(s),
            'available_cell_fraction': available_cell_fraction(s, values), 'status': DIAGNOSTIC_STATUS}


def contract(s):
    """Simulation-rig section: control, steps, presets, poses, sources, diagnostics and invariants. Plain JSON types only."""
    import spec
    r = s['radiators']; t = table(s); f = float; d = spec.derived(s)
    presets = {k: {a: f(b) for a, b in configuration_state(s, k).items()} for k in preset_names(s)}
    poses = {k: {a: f(b) for a, b in display_pose(s, k).items()} for k in pose_names(s)}
    rule = lambda node, key='rule': {key: node[key], 'canon_status': node['canon_status'], 'source_ref': node['source_ref']}
    sources = {'operating_sequence': {**rule(r['operating_sequence']), 'sequence': list(r['operating_sequence']['steps'])},
               'cell_isolation': {**rule(r['cell_isolation'], 'isolation_unit'), 'count': 'PROTOTYPE (not sourced)'},
               'sensor_mesh': {**rule(r['sensor_mesh'], 'consumer'), 'sensing': list(r['sensor_mesh']['sensing'])},
               'repair_doctrine': {**rule(r['repair_doctrine'], 'hot_face_rule'), 'sequence': list(r['repair_doctrine']['sequence'])},
               'cell_qualification': {**rule(r['cell_qualification']), 'states': list(r['cell_qualification']['states']), 'in_service': list(r['cell_qualification']['in_service']),
                                      'interim_derate': {'known': False, **{k: v for k, v in r['cell_qualification']['interim_derate'].items() if k != 'known'}}},
               'fault_display': {**rule(r['fault_display']), 'degraded_matrix': r['fault_display']['degraded_matrix']},
               'fixed_geometry': {ref: {'rule': 'Radiator geometry is fixed in every mode; no deployment mechanism or articulation', 'canon_status': status, 'source_ref': ref}
                                  for ref, status in FIXED_GEOMETRY_REFS.items()}}
    return {
        'status': 'IMPLEMENTATION display of BASELINE/WORKING radiator facts; presets, fault order and the 480-cell grid are PROTOTYPE; the degraded-mode matrix stays OPEN (OD-010)',
        'control': f'{SUBSYSTEM}.blend:{CONTROL}', 'units': t['controls']['unit']+'; no temperature, emissivity or flux', 'saved_state': 'NEUTRAL (all controls 0)',
        'controls': {k: PROPS[k] for k in PROPS},
        'steps': {name: {'value': f(step_value(s, k)), 'canon_status': r['operating_sequence']['canon_status'], 'source_ref': r['operating_sequence']['source_ref']} for k, name in enumerate(steps(s))},
        'presets': presets, 'display_poses': poses,
        'fluid_status': {'canon_status': r['coolant_modes']['canon_status'], 'source_ref': r['coolant_modes']['source_ref'], 'rule': r['coolant_modes']['rule'],
                         'flow_rate': {'known': False, **{k: v for k, v in r['coolant_modes']['flow_rate'].items() if k != 'known'}},
                         'configurations': {k: dict(r['coolant_modes'][k]) for k in preset_names(s)}},
        'preset_status': {'canon_status': t['presets']['status'], 'rationale': t['presets']['rationale']},
        'fault_pattern': {'canon_status': t['fault_pattern']['status'], 'cell_order_stride': t['fault_pattern']['cell_order_stride'], 'rationale': t['fault_pattern']['rationale'],
                          'cell_count': {'known': True, 'value': f(cell_count(s)), 'canon_status': 'PROTOTYPE', 'basis': 'radiators.count x prototype radiator_longitudinal_cells x radiator_transverse_cells; the sourced count is OPEN (40!A26 "many")'}},
        'sources': sources,
        'diagnostics': {**{k: diagnostics(s, configuration_state(s, k)) for k in preset_names(s)}, **{k: diagnostics(s, display_pose(s, k)) for k in pose_names(s)}},
        'invariants': {'as_built_net_area_total_m2': {'value': d['total_net_area_m2'], 'unit': 'm2', 'canon_status': 'DERIVED', 'evidence_ref': r['as_built_net_area']['evidence_ref']},
                       'physical_area_total_m2': {'value': d['total_planform_m2'], 'unit': 'm2', 'canon_status': r['physical_area']['canon_status'], 'source_ref': r['physical_area']['source_ref']},
                       'emissivity': {'value': f(r['emissivity']['value']), 'canon_status': r['emissivity']['canon_status'], 'source_ref': r['emissivity']['source_ref']},
                       'hot_face_temperature_K': {'value': f(r['temperature']['value']), 'canon_status': r['temperature']['canon_status'], 'source_ref': r['temperature']['source_ref']},
                       'variable_emissivity_zones': list(r['variable_emissivity_zoning']['permitted_model_zones']),
                       'geometry': 'fixed in every control state'}}
