"""P1F propulsion recipes: the LOCKED four-way drive plus the WORKING optically gated manifold, and two static debug layers.

Layers stay separate (Wayfarer S&E 06!A42, LOCKED): photons (straight optical segments), magnetic field (domain
tubes, field lines, separatrices) and plasma (driven streams). Geometry comes from drive_manifold.geometry(); every
driver expression comes from drive_manifold.drivers(); every action from drive_manifold.actions().
"""
import math
from pathlib import Path
import tomllib
import bpy
from common import empty, material, driven_material, mesh, loft, cylinder, line, ring, link_instance, owned_action, OWNER
import drive_manifold as dm
import drive_hot_section as hsec
import layout

PHOTON = (.25, 1.0, .55)      # control light: green, never shares a colour with plasma or field
PLASMA = (.78, .62, 1.0)      # charged plasma: violet-white
FIELD = (.12, .62, .83)       # magnetic topology: blue (existing FieldFlow colour)
LATTICE = (1.0, .55, .18)     # Fiji lattice activity: amber
PFC_COLOR = (.34, .30, .27)   # plasma-facing refractory tiles (implementation colour)
FEED_COLOR = (.55, .74, .86)  # cryogenic feed lines


def sources(asset_dir):
    return tomllib.loads((Path(asset_dir).resolve().parents[1]/'data/source_map.toml').read_text())['sources']


def meta(obj, src, subsystem, status, ref, prototype=True):
    """Brief item 39 metadata; canon status of what the object represents, geometry always PROTOTYPE."""
    obj['canon_status'] = status; obj['source_ref'] = ref
    obj['wf_id'] = obj['component_id']; obj['wf_subsystem'] = subsystem; obj['wf_status'] = status
    rec = src.get(ref)
    obj['wf_source'] = rec['workbook'] if rec else 'local PROTOTYPE (data/wayfarer_3d.toml [drive_manifold])'
    obj['wf_source_range'] = f"{rec['sheet']}!{rec['range']}" if rec else 'drive_manifold'
    obj['wf_prototype'] = prototype
    return obj


def node(c, name, parent=None):
    obj = empty(c, name, ident=f'WF.DRIVE.NODE.{name}', kind='drive_node')
    obj.empty_display_type = 'PLAIN_AXES'; obj.empty_display_size = .01
    if parent is not None:
        obj.parent = parent
    return obj


def attach(obj, parent):
    # Groups sit at the origin with identity transforms, so world matrices are unchanged by re-parenting.
    obj.parent = parent
    return obj


def ident(obj, value, kind):
    obj['component_id'] = value; obj['kind'] = kind
    return obj


def curve(c, name, polylines, radius, mat, kind, resolution=1, radii=None):
    """One curve object from several POLY splines (optionally with per-point radius)."""
    data = bpy.data.curves.new(f'{name}_Curve', 'CURVE')
    data.dimensions = '3D'; data.resolution_u = 1; data.bevel_depth = radius; data.bevel_resolution = resolution
    for k, points in enumerate(polylines):
        sp = data.splines.new('POLY'); sp.points.add(len(points)-1)
        for j, (p, co) in enumerate(zip(sp.points, points)):
            p.co = (*co, 1)
            if radii:
                p.radius = radii[k][j]
    obj = bpy.data.objects.new(name, data); c.objects.link(obj); data.materials.append(mat)
    from common import tag
    return tag(obj, name, kind)


def sector_solid(x0, x1, r0, r1, a0, a1, steps, base=0):
    """Vertices and faces of a closed annular sector between two axial stations; face indices start at `base`."""
    vs = []
    for x in (x0, x1):
        for r in (r0, r1):
            vs += [(x, r*math.cos(a0+(a1-a0)*k/steps), r*math.sin(a0+(a1-a0)*k/steps)) for k in range(steps+1)]
    n = steps+1; f = []
    idx = lambda xi, ri, k: base+(xi*2+ri)*n+k
    for k in range(steps):
        f += [(idx(0, 1, k), idx(0, 1, k+1), idx(1, 1, k+1), idx(1, 1, k)), (idx(0, 0, k), idx(1, 0, k), idx(1, 0, k+1), idx(0, 0, k+1)),
              (idx(0, 0, k), idx(0, 0, k+1), idx(0, 1, k+1), idx(0, 1, k)), (idx(1, 0, k), idx(1, 1, k), idx(1, 1, k+1), idx(1, 0, k+1))]
    for k in (0, steps):
        f.append((idx(0, 0, k), idx(0, 1, k), idx(1, 1, k), idx(1, 0, k)))
    return vs, f


def sector(c, name, x0, x1, r0, r1, a0, a1, mat, kind, steps=12):
    """Closed annular sector between two axial stations."""
    vs, f = sector_solid(x0, x1, r0, r1, a0, a1, steps)
    return mesh(c, name, vs, f, mat, kind=kind)


def tile_mesh(c, name, tiles, mat, kind):
    """One mesh whose islands are the plasma-facing tiles (drive_hot_section.liner_tiles); each tile is a closed solid."""
    vs, f = [], []
    for t in tiles:
        v, ff = sector_solid(t['x0'], t['x1'], t['r_in'], t['r_out'], t['a0'], t['a1'], hsec.TILE_STEPS, len(vs))
        vs += v; f += ff
    return mesh(c, name, vs, f, mat, kind=kind)


def hts_designation(obj, s, coil_set):
    """AFT-002 conductor designation of a coil: WORKING HTS architecture, the BASELINE 5 T calibration anchor kept apart from the lattice
    amplification, and the OPEN coil quantities. The coil geometry stays PROTOTYPE: every object already carries geometry provenance
    (common.tag: PROTOTYPE) and keeps it, and the conductor designation cites its own WORKING records in the conductor_* keys."""
    mh = s['propulsion']['magnet_hardware']
    obj['conductor_canon_status'] = mh['canon_status']; obj['conductor_source_ref'] = mh['source_ref']; obj['conductor_architecture_ref'] = mh['evidence_ref']
    obj['coil_set'] = coil_set; obj['conductor'] = mh['conductor']; obj['flux_pinning_rule'] = mh['flux_pinning_rule']
    cal = mh['seed_field_calibration']
    obj['seed_field_calibration_T'] = cal['value']; obj['seed_field_calibration_status'] = cal['canon_status']; obj['seed_field_calibration_source_ref'] = cal['source_ref']
    obj['field_note'] = 'Unamplified calibration anchor only; lattice amplification is a separate Fiji layer and is not stored here. Coil geometry is PROTOTYPE.'
    obj['open_quantities'] = ', '.join(f'{k.rsplit(".", 1)[1]} ({hsec.open_text(ref)})' for k, ref in hsec.open_keys(s).items() if k.startswith('propulsion.magnet_hardware.'))
    obj['engineering_status'] = 'OPEN OD-024: current density, operating temperature, stress, quench protection and radiation lifetime not designed'
    return obj


def pfc_metadata(obj, s, zone, tiles, modules):
    """Plasma-facing tile set metadata: WORKING replaceable refractory shell; heat flux, erosion, module size and interval OPEN (OD-025)."""
    pf = s['propulsion']['plasma_facing']
    obj['canon_status'] = pf['canon_status']; obj['source_ref'] = pf['evidence_ref']; obj['material_source_ref'] = pf['source_ref']
    obj['zone'] = zone; obj['tile_count'] = len(tiles); obj['axial_modules'] = modules; obj['replaceable'] = True
    obj['material_stack'] = ' -> '.join(pf['material_stack']); obj['serviceability'] = pf['serviceability']
    for key in ('heat_flux', 'erosion_rate', 'module_size', 'replacement_interval'):
        obj[key] = hsec.open_text(pf[key]['source_ref'])
    obj['exact_material'] = hsec.open_text(pf['exact_material']['source_ref'])
    obj['engineering_status'] = 'OPEN OD-025: tile geometry is a PROTOTYPE display segmentation; module size and life not designed'
    return obj


def cryo_feed(c, s):
    """Cryogenic feed lines (WF_STORAGE): one jacketed line per tank, tank aft cap -> its terminus, with declared interfaces at both ends and at
    the shadow-shield sleeve. D and 3He end on the core forward face; hydrogen ends on the PROTOTYPE injection ring in the common region
    (15!A69, 06!A53, 06!A54). The tank-family assignment is PROTOTYPE (15!G69); layout, flow ratios and fault isolation stay OPEN (OD-026)."""
    cf = s['propulsion']['cryogenic_feed']; stack = cf['storage_stack']
    mat = material('CryoFeed', FEED_COLOR)
    status = 'OPEN OD-026: '
    for line_ in hsec.cryo_feed(s):
        j = line_['index']; core = line_['terminus'] == 'core'
        obj = line(c, line_['name'], line_['points'], line_['radius'], mat, kind='cryo_feed_line')
        obj['canon_status'] = cf['canon_status']; obj['source_ref'] = cf['source_ref']; obj['tank'] = line_['tank']
        obj['fluid'] = line_['family']; obj['fluid_assignment'] = 'PROTOTYPE tank-family assignment (15!G69); inventories per propulsion.inventories'
        obj['terminus'] = line_['terminus']; obj['quantity'] = hsec.open_text(cf['fuel_split']['source_ref'])+' (fuel split and reaction-mass quantity)'
        obj['insulation'] = stack['insulation']; obj['sensing'] = stack['sensing']; obj['refrigeration'] = stack['refrigeration']
        obj['storage_stack_status'] = stack['canon_status']; obj['storage_stack_source_ref'] = stack['source_ref']
        obj['sleeve_radius_m'] = line_['sleeve_radius']; obj['engineering_status'] = status+'line layout, temperatures, refrigeration, boil-off and fault isolation not designed; display line with a PROTOTYPE stepped (dog-leg) shield sleeve'
        end = ('CORE', 'terminus on the fusion-core forward face; metering point and flow ratio OPEN') if core else ('INJECTION', 'terminus on the PROTOTYPE hydrogen injection ring in the common region (downstream of the burn, ahead of the manifold); injector ports and mixing OPEN')
        for label, point, text in [('TANK', line_['a'], 'tank connection on the aft cap'),
                                   ('SHIELD', line_['shield_point'], 'shadow-shield stepped sleeve (offset leg mid-slab, no direct line of sight); thermal intercepts and labyrinth shielding annotated here, design OPEN; penetration design, scattering and dose OPEN (CRYO_FEED_SHIELD_PENETRATION)'),
                                   end[:1]+(line_['b'], end[1])]:
            iface = empty(c, f'IF_CRYO_FEED_{label}_{j:02}', point)
            iface['engineering_status'] = status+text; iface['feed_line'] = line_['name']
        tank = bpy.data.objects.get(line_['tank'])
        if tank is not None:
            tank['fuel_family'] = line_['family']; tank['feed_line'] = line_['name']; tank['family_assignment'] = 'PROTOTYPE (15!G69)'
            tank['volume_status'] = 'feed run tank (display envelope, volume OPEN); bulk storage in the fuel_storage stations and torus (FUEL-SPLIT)'


def patch(c, name, x0, x1, r, a0, a1, mat, kind, nx=4, na=6):
    vs = [(x0+(x1-x0)*i/nx, r*math.cos(a0+(a1-a0)*k/na), r*math.sin(a0+(a1-a0)*k/na)) for i in range(nx+1) for k in range(na+1)]
    f = [(i*(na+1)+k, i*(na+1)+k+1, (i+1)*(na+1)+k+1, (i+1)*(na+1)+k) for i in range(nx) for k in range(na)]
    return mesh(c, name, vs, f, mat, kind=kind)


def box(c, name, center, size, mat, kind):
    vs = [(center[0]+x*size[0]/2, center[1]+y*size[1]/2, center[2]+z*size[2]/2) for x, y, z in [(-1, -1, -1), (-1, -1, 1), (-1, 1, -1), (-1, 1, 1), (1, -1, -1), (1, -1, 1), (1, 1, -1), (1, 1, 1)]]
    return mesh(c, name, vs, [(0, 4, 6, 2), (1, 3, 7, 5), (0, 1, 5, 4), (2, 6, 7, 3), (0, 2, 3, 1), (4, 5, 7, 6)], mat, kind=kind)


def disc(c, name, point, radius, depth, mat, kind):
    return cylinder(c, name, point[0], depth, radius, mat, point[1], point[2], kind=kind)


def centred_loft(c, name, rings, mat, kind, x_center, caps=False):
    """Solid of revolution built about its own origin, so a scale driver collapses it in place."""
    obj = loft(c, name, [(x-x_center, r) for x, r in rings], mat, caps=caps, kind=kind)
    obj.location.x = x_center
    return obj


def lattice_cells(g, lat, s):
    """Directional Fiji cell pattern on a lattice sector's outer face: helical ribs whose pitch tightens toward the
    branch-forming aft end (denser organization near the split). Visual language only."""
    r = lat['r_out']+.015; lines = []
    for k in range(7):
        a_start = lat['a0']+(lat['a1']-lat['a0'])*k/6
        pts = []
        for i in range(13):
            u = i/12; x = lat['x0']+(lat['x1']-lat['x0'])*u
            twist = (lat['a1']-lat['a0'])*.35*u*u
            a = max(lat['a0'], min(lat['a1'], a_start+twist*(1 if k % 2 else -1)))
            pts.append(dm.radial(x, r, a))
        lines.append(pts)
    for i in range(7):
        u = (i/6)**.7; x = lat['x0']+(lat['x1']-lat['x0'])*u
        lines.append([dm.radial(x, r, lat['a0']+(lat['a1']-lat['a0'])*k/12) for k in range(13)])
    return lines


def add_driver(target, path, index, expression, control):
    owner = target.data if path.startswith('data.') else target
    prop = path[5:] if path.startswith('data.') else path
    fc = owner.driver_add(prop) if index == -1 else owner.driver_add(prop, index)
    fc.driver.type = 'SCRIPTED'; fc.driver.expression = expression
    for var in dm.expression_variables(expression):
        v = fc.driver.variables.new(); v.name = var; v.type = 'SINGLE_PROP'
        v.targets[0].id_type = 'OBJECT'; v.targets[0].id = control; v.targets[0].data_path = f'["{dm.VARIABLES[var]}"]'
    if not fc.driver.is_simple_expression:
        raise ValueError(f'{target.name}.{path}: driver is not a simple expression: {expression}')
    target['drive_driven'] = True
    return fc


def build_actions(s, control):
    """Reusable actions with one slot for DRIVE_MANIFOLD_CTRL; stored with a fake user, never assigned in the file."""
    made = []
    for name, spec in dm.actions(s).items():
        action = owned_action(name)
        slot = action.slots.new(id_type='OBJECT', name=control.name)
        strip = action.layers.new('Drive').strips.new(type='KEYFRAME')
        bag = strip.channelbag(slot, ensure=True)
        for prop in dm.PROPS:
            fc = bag.fcurves.new(data_path=f'["{prop}"]')
            fc.keyframe_points.add(len(spec['keys']))
            for kp, (frame, values) in zip(fc.keyframe_points, spec['keys']):
                kp.co = (frame, values[prop]); kp.interpolation = 'LINEAR'
            fc.extrapolation = 'CONSTANT'; fc.update()
        action.use_frame_range = True; action.frame_start, action.frame_end = spec['frame_range']
        action['description'] = spec['description']; action['status'] = 'PROTOTYPE timing; normalized controls'
        action['target'] = control.name
        made.append(action)
    return made


def propulsion(c, s, asset_dir):
    p = s['prototype']; m = s['drive_manifold']; L = s['ship']['length']['value']; g = dm.geometry(s); st = g['stations']; src = sources(asset_dir)
    x = lambda key: layout.at(s, p[key])
    # --- hierarchy (brief section 31; causal nesting of section 7) ---
    root = node(c, 'WF_DRIVE_ROOT')
    core_g = node(c, 'DRIVE_FUSION_CORE', root); common_g = node(c, 'DRIVE_COMMON_PLASMA', root)
    throat_g = node(c, 'DRIVE_CONVERGENCE_THROAT', common_g); manifold_g = node(c, 'DRIVE_MANIFOLD', throat_g)
    optics_g = node(c, 'DRIVE_OPTICAL_CONTROL', root)
    # --- existing LOCKED envelopes, same names, IDs and formulas as P0-004 ---
    hot = material('Core', (.66, .31, .12))
    envelopes = {}
    for label, center, ln, rr, mat in [('Fusion_Core', 'reactor_center_x', 'reactor_length_m', 'reactor_radius_m', hot),
                                       ('Common_Plasma_Region', 'common_center_x', 'common_length_m', 'common_radius_m', material('Plasma', (.17, .57, .66), .45)),
                                       ('Magnetic_Manifold', 'manifold_center_x', 'manifold_length_m', 'manifold_radius_m', material('Manifold', (.19, .38, .48)))]:
        obj = cylinder(c, label, x(center), p[ln], p[rr], mat)
        obj['canon_status'] = 'LOCKED'; obj['source_ref'] = 'propulsion'; obj['drive_envelope'] = True
        envelopes[label] = obj
    attach(envelopes['Fusion_Core'], core_g); attach(envelopes['Common_Plasma_Region'], common_g); attach(envelopes['Magnetic_Manifold'], manifold_g)
    # Field-transition surface bridges the separated core and common region (on the axis of the solid plasma column).
    attach(line(c, 'Core_Common_Field_Transition', [(x('reactor_center_x')-p['reactor_length_m']/2, 0, 0), (x('common_center_x')+p['common_length_m']/2, 0, 0)], .6, material('FieldFlow', FIELD, 1.2), kind='magnetic_field'), core_g)
    attach(empty(c, 'IF_REACTOR_MOUNT', (x('reactor_center_x'), 0, 0)), core_g)
    attach(empty(c, 'IF_MANIFOLD_INPUT', (st['throat_entry'], 0, 0)), throat_g)
    thr = empty(c, 'IF_CONVERGENCE_THROAT', ((st['throat_entry']+st['throat_exit'])/2, 0, 0))
    thr['engineering_status'] = 'OPEN 06!C49, 15!H74: the throat field profile is not designed or inferred from the envelope; the 1.5 m length and ~2.4 m waist radius are WORKING (Q25, propulsion.manifold.throat_geometry)'
    attach(thr, throat_g)
    # --- control ---
    ctrl = empty(c, dm.CONTROL, ident='WF.DRIVE.STATE_CONTROL', kind='state_control')
    ctrl.empty_display_type = 'CUBE'; ctrl.empty_display_size = .4; ctrl.location = (st['exit']-2, 0, -6)
    for key, value in {**dm.neutral(s), **dm.SAVED_SETTINGS}.items():
        ctrl[key] = float(value)
        ctrl.id_properties_ui(key).update(min=0.0, max=1.0, soft_min=0.0, soft_max=1.0, description={**dm.PROPS, **dm.DEBUG_TOGGLES, **dm.CONFIGURATION_SETTINGS}[key])
        ctrl.property_overridable_library_set(f'["{key}"]', True)
    ctrl['units'] = 'normalized 0-1; no physical rating'
    ctrl['state'] = 'NEUTRAL (drive off); configurations are posed in memory'
    ctrl['thrust_level_status'] = 'PROTOTYPE display throttle (P1-006): sourced max_accel_g ratio; shortens only the exhaust run; not a thrust or mass-flow value'
    ctrl['nozzle_order'] = 'N1..N4 = Nozzle_01..04: +Y+Z, -Y+Z, +Y-Z, -Y-Z (owner map 06!A48, 15!C71; WORKING; EYE F1-F4 order)'
    ctrl['causal_chain'] = 'optical_gate_n -> LATTICE_SECTOR_n -> flux domain n -> PLASMA_BRANCH_n -> Nozzle_0n'
    ctrl['engineering_status'] = 'OPEN: normalized PROTOTYPE rig; optical power, wavelength, gate response time and lattice coupling OPEN'
    meta(ctrl, src, 'drive_manifold_control', 'WORKING', 'drive_model_interfaces')
    attach(ctrl, root)
    # --- materials ---
    plasma = driven_material('Drive_Plasma', PLASMA, 1.4, .4)
    photon = driven_material('Drive_Photon', PHOTON, 30.0, 1.0)
    pad = driven_material('Drive_Gate_Light', PHOTON, 8.0, .9, base=.05)
    lat_glow = driven_material('Drive_Lattice_Cells', LATTICE, 4.0, 1.0)
    coil_glow = driven_material('Drive_Seed_Coil', (.85, .45, .2), 1.5, 1.0, base=.6)
    laser_mat = driven_material('Drive_Laser_Housing', PHOTON, .8, 1.0, base=.25)
    domain = material('FieldDomain', FIELD, .35, alpha=.14)
    lattice_body = material('Fiji_Lattice', (.13, .11, .09))
    optics_hw = material('OpticsHardware', (.55, .6, .62))
    channel = material('OpticalChannel', (.3, .35, .38), 0, alpha=.3)
    hub_mat = material('SpineHub', (.48, .43, .28))
    yoke_mat = material('NozzleYoke', (.50, .53, .56))
    ring_mat = material('H2InjectionRing', FEED_COLOR)
    # --- plasma: solid common column and throat (collapse in place); no spine passes through them (06!A47, 15!A70) ---
    cm = g['common']; xc = (cm['x0']+cm['x1'])/2
    obj = centred_loft(c, 'PLASMA_COMMON', [(cm['x0'], cm['outer']), (cm['x1'], cm['outer'])], plasma, 'plasma', xc, caps=True)
    ident(obj, 'WF.DRIVE.PLASMA.COMMON', 'plasma'); meta(obj, src, 'drive_plasma', 'LOCKED', 'manifold_topology'); attach(obj, common_g)
    rings = g['throat_rings']; xt = (rings[0][0]+rings[-1][0])/2
    obj = centred_loft(c, 'PLASMA_THROAT', [(xx, ro) for xx, ri, ro in rings], plasma, 'plasma', xt, caps=True)
    ident(obj, 'WF.DRIVE.PLASMA.THROAT', 'plasma'); meta(obj, src, 'drive_plasma', 'WORKING', 'optical_manifold_architecture'); attach(obj, throat_g)
    # --- terminated spine hub (PROTOTYPE) on the forward face of the shadow shield, the shielded end of Structural_Spine ---
    hub = g['hub']
    obj = cylinder(c, 'SPINE_TERMINATION_HUB', (hub['x0']+hub['x1'])/2, hub['x1']-hub['x0'], hub['radius'], hub_mat, kind='spine_hub')
    ident(obj, 'WF.DRIVE.SPINE_TERMINATION_HUB', 'spine_hub'); meta(obj, src, 'drive_structure', 'WORKING', 'spine_termination')
    obj['engineering_status'] = 'OPEN: terminated hub boss, bulkhead structure, load shares (07!H16), local shielding (15!G70) and streaming dose not designed (PROTOTYPE)'; attach(obj, root)
    iface = empty(c, 'IF_SPINE_TERMINATION', (hub['x1'], 0, 0))
    iface['engineering_status'] = 'OPEN: spine end on the shield bulkhead; bulkhead sizing and load shares not designed (PROTOTYPE hub)'; attach(iface, root)
    # --- manifold: Fiji lattice sectors (L1-L4), cell pattern, seed coils ---
    for k, coil in enumerate(g['coils'], 1):
        obj = ring(c, f'SEED_COIL_{k}', coil['x'], coil['radius'], coil['tube'], coil_glow, kind='seed_coil')
        ident(obj, f'WF.DRIVE.SEED_COIL.{k}', 'seed_coil'); meta(obj, src, 'drive_seed_field', 'PROTOTYPE', 'prototype'); obj['role'] = 'Slow/heavy control: base field, topology, confinement envelope'
        hts_designation(obj, s, 'seed_manifold')
        attach(obj, manifold_g)
    # --- plasma-facing liners (AFT-002): replaceable refractory tiles on the core and throat ---
    pfc = material('PFC_Refractory_Liner', PFC_COLOR)   # own material: WF_NOZZLE's PFC_Refractory is a linked ID here
    for zone, name, parent in [(hsec.CORE, 'PFC_LINER_CORE', core_g), (hsec.THROAT, 'PFC_LINER_THROAT', throat_g)]:
        tiles = hsec.liner_tiles(s, zone)
        obj = tile_mesh(c, name, tiles, pfc, 'pfc_liner')
        ident(obj, f'WF.DRIVE.PFC.{zone.upper()}', 'pfc_liner'); modules = max(t['module'] for t in tiles)+1
        pfc_metadata(obj, s, {hsec.CORE: 'fusion_core', hsec.THROAT: 'convergence_throat'}[zone], tiles, modules)
        obj['wf_id'] = obj['component_id']; obj['wf_subsystem'] = 'drive_plasma_facing'; obj['wf_status'] = obj['canon_status']; obj['wf_prototype'] = True
        attach(obj, parent)
    # --- flux channels, plasma branches, nozzles, exhaust ---
    nozzle_x = st['exit']; inlet = st['inlet']; yokes = dm.nozzle_yokes(s); pickups = dm.nozzle_pickups(s)
    for j, ((yy, zz), lat) in enumerate(zip(dm.quadrants(s), g['lattice']), 1):
        obj = sector(c, f'LATTICE_SECTOR_{j}', lat['x0'], lat['x1'], lat['r_in'], lat['r_out'], lat['a0'], lat['a1'], lattice_body, 'lattice_sector')
        ident(obj, f'WF.DRIVE.LATTICE.L{j}', 'lattice_sector'); meta(obj, src, 'fiji_lattice_sector', 'WORKING', 'optical_manifold_architecture')
        obj['gate'] = f'GATE_L{j}'; obj['flux_channel'] = f'DRIVE_FLUX_CHANNEL_{j}'; attach(obj, manifold_g)
        cells = curve(c, f'LATTICE_CELLS_{j}', lattice_cells(g, lat, s), .018, lat_glow, 'lattice_cells')
        ident(cells, f'WF.DRIVE.LATTICE.L{j}.CELLS', 'lattice_cells'); meta(cells, src, 'fiji_lattice_sector', 'PROTOTYPE', 'prototype'); attach(cells, obj)
        chan = node(c, f'DRIVE_FLUX_CHANNEL_{j}', manifold_g)
        y, z = yy*p['nozzle_offset_m'], zz*p['nozzle_offset_m']
        obj = line(c, f'Magnetic_Flow_Domain_{j:02}', g['branches'][j-1], m['domain_radius_m'], domain, kind='magnetic_field')
        obj.data.bevel_resolution = 3
        obj['component_id'] = f'WF.FLUX.{j:02}'; obj['canon_status'] = 'LOCKED'; obj['source_ref'] = 'propulsion'
        obj['representation_note'] = 'Magnetic flux domain (field layer), not a pipe: physical plasma pipes = 0 (Fiji 25!A12)'
        attach(obj, chan)
        obj = line(c, f'PLASMA_BRANCH_{j}', g['branches'][j-1], p['flow_radius_m'], plasma, kind='plasma')
        obj.data.bevel_resolution = 3
        ident(obj, f'WF.DRIVE.PLASMA.BRANCH.{j}', 'plasma'); meta(obj, src, 'drive_plasma', 'LOCKED', 'manifold_topology')
        obj['nozzle'] = f'Nozzle_{j:02}'; obj['visual_rule'] = 'Cross-section area ~ drive level x flow share; visualization, not a pressure law'
        attach(obj, chan)
        noz = node(c, f'DRIVE_NOZZLE_{j}', chan)
        obj = link_instance(c, asset_dir/'components/WF_NOZZLE.blend', 'WF_NOZZLE', f'Nozzle_{j:02}', (nozzle_x, y, z), ident=f'WF.NOZZLE.{j:02}')
        obj['canon_status'] = 'LOCKED'; obj['source_ref'] = 'propulsion'; obj['owner_label'] = f'N{j}'
        pl = s['propulsion']['manifold']['nozzle_placement']; obj['placement_status'] = pl['canon_status']; obj['placement_source_ref'] = pl['source_ref']
        attach(obj, noz)
        attach(empty(c, f'IF_NOZZLE_{j:02}', (inlet, y, z)), noz)
        ex = g['exhausts'][j-1]
        obj = curve(c, f'PLASMA_EXHAUST_{j}', [ex['points']], p['flow_radius_m'], plasma, 'plasma', resolution=3, radii=[ex['factors']])
        ident(obj, f'WF.DRIVE.PLASMA.EXHAUST.{j}', 'plasma'); meta(obj, src, 'drive_plasma', 'PROTOTYPE', 'prototype')
        obj['visual_rule'] = 'Follows the nozzle field envelope; no divergence past the exit (plume boundary OPEN, R2)'
        attach(obj, noz)
        # Warm structural yoke (15!A67, G67): four rings standing off the coils and straps; the pickup bears on the inlet ring.
        yk = yokes[j-1]
        for ring_ in yk['rings']:
            obj = loft(c, ring_['name'], [(ring_['x1'], ring_['r_out']), (ring_['x0'], ring_['r_out']), (ring_['x0'], ring_['r_in']), (ring_['x1'], ring_['r_in']), (ring_['x1'], ring_['r_out'])],
                       yoke_mat, (0, *yk['axis']), caps=False, kind='nozzle_yoke')
            ident(obj, f'WF.DRIVE.NOZZLE.YOKE.{j}.{ring_["coil"]}', 'nozzle_yoke'); meta(obj, src, 'drive_structure', 'WORKING', 'nozzle_pickup_yoke')
            obj['mass_known'] = False; obj['com_contribution'] = 'unknown (not zero)'; obj['mass_suballocation'] = 'magnet_cage_support (P5/P6, non-additive, 10!A25)'
            obj['coil_standoff_m'] = ring_['coil_gap']; obj['engineering_status'] = 'OPEN OD-024: yoke section and cold-mass supports not designed (PROTOTYPE warm casing ring)'
            attach(obj, noz)
        for strap in yk['straps']:
            obj = line(c, strap['name'], strap['points'], strap['radius'], yoke_mat, kind='nozzle_yoke_strap')
            ident(obj, f'WF.DRIVE.NOZZLE.YOKE.{j}.STRAP.{strap["name"].rsplit("_", 1)[1]}', 'nozzle_yoke_strap'); meta(obj, src, 'drive_structure', 'WORKING', 'nozzle_pickup_yoke')
            obj['engineering_status'] = 'OPEN OD-024: strap section not designed (PROTOTYPE)'; attach(obj, noz)
        iface = empty(c, f'IF_NOZZLE_YOKE_PICKUP_{j-1}', pickups[j-1]['a'])
        iface['engineering_status'] = 'OPEN OD-024: pickup strut seat on the inlet yoke; load path and cold-mass supports not designed (PROTOTYPE)'; attach(iface, noz)
    # --- H2 injection ring (PROTOTYPE) around the common region: reaction mass enters downstream of the burn (06!A54) ---
    ir = hsec.injection_ring(s)
    obj = ring(c, 'H2_INJECTION_RING', ir['x'], ir['radius'], ir['tube'], ring_mat, kind='h2_injection_ring')
    ident(obj, 'WF.DRIVE.H2_INJECTION_RING', 'h2_injection_ring'); meta(obj, src, 'drive_injection', 'WORKING', 'reaction_mass_injection')
    obj['engineering_status'] = 'OPEN: injector ports, count, mixing and ring heat load not designed (PROTOTYPE ring station)'; attach(obj, common_g)
    iface = empty(c, 'IF_H2_INJECTION', (ir['x'], 0, 0))
    iface['engineering_status'] = 'OPEN: hydrogen injection point in the common region; ports and mixing not designed'; attach(iface, common_g)
    # --- optics (06!A55, 15!A73, 15!A83): two independent routes, each laser -> turn -> entry -> dog-leg bore -> splitter -> two corridor legs -> heads ---
    for key, r in g['routes'].items():
        route_g = node(c, f'DRIVE_OPTICAL_ROUTE_{key}', optics_g)
        las = g['lasers'][key]
        obj = box(c, f'LASER_{key}', las['center'], las['size'], laser_mat, 'optical_source')
        ident(obj, f'WF.DRIVE.LASER.{key}', 'optical_source'); meta(obj, src, 'fiji_optical_source', 'WORKING', 'optical_manifold_architecture')
        obj['power_bus'] = key; obj['rating'] = 'OPEN (05_DRIVE_INTERFACE A34)'; obj['protected_zone'] = 'engineering bay forward of the shadow shield; no core line of sight'
        attach(obj, optics_g)    # sources keep their parent: only the routes below are new groups
        iface = empty(c, f'IF_LASER_{key}', las['center'])
        iface['engineering_status'] = 'OPEN 05!A34:A36: optical power, wavelength and mount not designed; position PROTOTYPE'; attach(iface, optics_g)
        obj = line(c, f'OPTICAL_BEAM_{key}', r['trunk'], m['beam_radius_m'], photon, kind='optical_beam')
        ident(obj, f'WF.DRIVE.BEAM.{key}', 'optical_beam'); meta(obj, src, 'fiji_optical_path', 'WORKING', 'optical_manifold_architecture')
        obj['physics'] = 'Straight segments between mirrors; magnetic fields do not bend the beam (SEED-BOUNDARY-02, LOCKED)'; attach(obj, route_g)
        obj = line(c, f'OPTICAL_BORE_{key}', r['bore'], m['optical_channel_radius_m'], channel, kind='optical_channel')
        ident(obj, f'WF.DRIVE.OPTICS.BORE.{key}', 'optical_channel'); meta(obj, src, 'fiji_optical_path', 'WORKING', 'hot_optics_service')
        obj['engineering_status'] = 'OPEN: dog-leg bore through the hub and shadow shield; material, streaming dose and thermal intercepts not designed (15!C73); jog and offset PROTOTYPE'; attach(obj, route_g)
        entry = empty(c, f'IF_OPTICAL_ENTRY_{key}', r['mirrors'][f'OPTICAL_ENTRY_MIRROR_{key}'])
        entry['engineering_status'] = 'OPEN: bore entry on the hub face; cartridge and seal not designed (PROTOTYPE)'; attach(entry, route_g)
        for name, point in r['mirrors'].items():
            hot = name.startswith(('OPTICAL_SPLITTER_', 'OPTICAL_CORRIDOR_MIRROR_')) or name.endswith('_2')
            obj = disc(c, name, point, m['mirror_radius_m'], .05, optics_hw, 'optical_mirror')
            ident(obj, f'WF.DRIVE.OPTICS.{name}', 'optical_mirror'); meta(obj, src, 'fiji_optical_path', 'PROTOTYPE', 'prototype')
            obj['side'] = 'hot' if hot else 'cold'
            if hot:
                obj['service'] = 'robotic replaceable cartridge; human service only after shutdown and cooldown (15!C83); cartridge geometry OPEN (14!G31)'
            attach(obj, route_g)
        for leg in r['legs']:
            i = leg['index']
            obj = line(c, f'OPTICAL_LEG_{key}_{i}', leg['points'], m['beam_radius_m'], photon, kind='optical_beam')
            ident(obj, f'WF.DRIVE.BEAM.{key}.LEG.{i}', 'optical_beam'); meta(obj, src, 'fiji_optical_path', 'WORKING', 'optical_manifold_architecture')
            obj['path'] = f'splitter -> corridor at {leg["run_deg"]:g} deg (r {m["route_corridor_radius_m"]:g} m) -> head at {leg["head_deg"]:g} deg'; attach(obj, route_g)
            obj = disc(c, f'OPTICAL_HEAD_{key}_{i}', leg['head'], m['head_size_m'], .5, optics_hw, 'optical_distributor')
            ident(obj, f'WF.DRIVE.OPTICS.HEAD.{key}.{i}', 'optical_distributor'); meta(obj, src, 'fiji_optical_distributor', 'WORKING', 'fiji_optical_manifold')
            obj['mechanism'] = 'Mirrors, diffractive optics or photonic routing; implementation OPEN (Fiji 25!E58). One logical A/B-fed network; this head is a PROTOTYPE cartridge (15!G83).'
            obj['side'] = 'hot'; attach(obj, route_g)
            iface = empty(c, f'IF_OPTICAL_HEAD_{key}_{i}', leg['head'])
            iface['engineering_status'] = 'OPEN: replaceable distributor-head cartridge in a lattice gap; geometry, exposure and service not designed (14!G31)'; attach(iface, route_g)
    for j, pd in enumerate(g['pads'], 1):
        gate_g = node(c, f'DRIVE_GATE_L{j}', optics_g)
        for key in 'AB':
            beam, window = g['gate_beams'][(key, j)], g['windows'][(key, j)]
            obj = line(c, f'GATE_BEAM_{key}_L{j}', beam, m['beam_radius_m'], photon, kind='optical_beam')
            ident(obj, f'WF.DRIVE.BEAM.{key}.L{j}', 'optical_beam'); meta(obj, src, 'fiji_optical_gate', 'WORKING', 'optical_manifold_architecture'); attach(obj, gate_g)
            obj = disc(c, f'OPTICAL_WINDOW_{key}_L{j}', window, m['window_radius_m'], .04, optics_hw, 'optical_window')
            ident(obj, f'WF.DRIVE.OPTICS.WINDOW.{key}.L{j}', 'optical_window'); meta(obj, src, 'fiji_optical_gate', 'PROTOTYPE', 'prototype'); attach(obj, gate_g)
            iface = empty(c, f'IF_OPTICAL_WINDOW_{key}_L{j}', window)
            iface['engineering_status'] = 'OPEN: sacrificial/replaceable window on the hot side; exposure and service not designed'; attach(iface, gate_g)
        obj = patch(c, f'GATE_L{j}', pd['x0'], pd['x1'], pd['r'], pd['a0'], pd['a1'], pad, 'optical_gate')
        ident(obj, f'WF.DRIVE.GATE.L{j}', 'optical_gate'); meta(obj, src, 'fiji_optical_gate', 'WORKING', 'optical_manifold_architecture')
        obj['conditions'] = f'LATTICE_SECTOR_{j}'; obj['flux_channel'] = f'DRIVE_FLUX_CHANNEL_{j}'; obj['nozzle'] = f'Nozzle_{j:02}'
        obj['sources'] = 'A and B: one chord from each route lights this gate'; attach(obj, gate_g)
    # --- debug layers: linked here, next to the control, so their switches survive a library override of the drive ---
    for layer, toggle in dm.DEBUG_LAYERS.items():
        obj = link_instance(c, asset_dir/f'subsystems/WF_{layer}.blend', f'WF_{layer}', f'DRIVE_{layer}', ident=f'WF.DRIVE.{layer}')
        meta(obj, src, 'drive_debug', 'WORKING', 'drive_model_interfaces')
        obj['debug_layer'] = f'WF_{layer}'; obj['toggle'] = f'{dm.CONTROL}["{toggle}"]'
        obj.hide_viewport = obj.hide_render = True; attach(obj, root)
    # --- drivers and actions ---
    objects = {o.name: o for o in c.objects}
    for name, path, index, expression in dm.drivers(s):
        add_driver(objects[name], path, index, expression, ctrl)
    build_actions(s, ctrl)
    bpy.context.scene.render.fps = m['fps']


def debug_magnetics(c, s):
    """WF_DEBUG_MAGNETICS: static nominal topology. WF_PROPULSION links it as DRIVE_DEBUG_MAGNETICS, shown by magnetic_field_debug."""
    m = s['drive_manifold']; g = dm.geometry(s); st = g['stations']
    field = material('Debug_FieldLines', FIELD, 4.0)
    dom = material('Debug_CommonDomain', FIELD, .2, alpha=.07)
    arrow = material('Debug_NozzleVector', (.95, .95, .95), 1.0)
    centre = material('Debug_PlasmaCentreline', PLASMA, 2.0)
    def mark(obj, ident_, kind):
        obj['component_id'] = ident_; obj['kind'] = kind; obj['debug_layer'] = 'WF_DEBUG_MAGNETICS'
        return obj
    cm = g['common']
    mark(loft(c, 'DBG_MAG_COMMON_DOMAIN', [(cm['x0'], cm['outer']+.05), (cm['x1'], cm['outer']+.05)], dom, caps=False), 'WF.DRIVE.DEBUG.MAG.COMMON_DOMAIN', 'debug_magnetics')
    for j in range(1, 5):
        lines = [f_['points'] for f_ in g['field_lines'] if f_['branch'] == j]
        mark(curve(c, f'DBG_MAG_FLUX_LINES_{j}', lines, .045, field, 'debug_magnetics'), f'WF.DRIVE.DEBUG.MAG.FLUX_LINES.{j}', 'debug_magnetics')
        mark(line(c, f'DBG_MAG_PLASMA_CENTRELINE_{j}', g['branches'][j-1], .04, centre), f'WF.DRIVE.DEBUG.MAG.CENTRELINE.{j}', 'debug_magnetics')
        a, b = g['nozzle_vectors'][j-1]
        mark(line(c, f'DBG_MAG_NOZZLE_VECTOR_{j}', [a, b], .06, arrow), f'WF.DRIVE.DEBUG.MAG.NOZZLE_VECTOR.{j}', 'debug_magnetics')
        head = loft(c, f'DBG_MAG_NOZZLE_VECTOR_{j}_HEAD', [(b[0]+.6, .25), (b[0], 0.001)], arrow, (0, b[1], b[2]), caps=True, segments=12)
        mark(head, f'WF.DRIVE.DEBUG.MAG.NOZZLE_VECTOR.{j}.HEAD', 'debug_magnetics')
        head['meaning'] = 'Exhaust leaves along -X; reaction thrust on the ship is +X'
    xm = (st['throat_entry']+st['throat_exit'])/2
    mark(ring(c, 'DBG_MAG_THROAT_WAIST', xm, dm.throat_geometry(s)[1], .04, field), 'WF.DRIVE.DEBUG.MAG.THROAT_WAIST', 'debug_magnetics')


def debug_separatrices(c, s):
    """WF_DEBUG_SEPARATRICES: the four flux-domain boundaries SEP_12/24/34/13 (named by the two adjacent nozzles), toggled apart from the other field debug."""
    sep = material('Debug_Separatrix', (1.0, .45, .1), .4, alpha=.2)
    for sp in dm.geometry(s)['separatrices']:
        rows = sp['rows']; a = sp['angle']; vs = []
        for xx, r0, r1 in rows:
            vs += [dm.radial(xx, r0, a), dm.radial(xx, r1, a)]
        faces = [(2*i, 2*i+1, 2*i+3, 2*i+2) for i in range(len(rows)-1)]
        obj = mesh(c, sp['name'], vs, faces, sep, kind='debug_separatrix')
        obj['component_id'] = f'WF.DRIVE.DEBUG.{sp["name"]}'; obj['debug_layer'] = 'WF_DEBUG_SEPARATRICES'
        obj['meaning'] = 'Magnetic separatrix / flux-domain boundary: a field boundary, not a material wall'


def debug_optics(c, s):
    """WF_DEBUG_OPTICS: both routes, gate paths, illuminated areas and the bore clearance volumes."""
    m = s['drive_manifold']; g = dm.geometry(s)
    axis = material('Debug_BeamAxis', PHOTON, 3.0)
    clear = material('Debug_BeamClearance', PHOTON, .2, alpha=.12)
    bore = material('Debug_BoreClearance', (1.0, .2, .15), .4, alpha=.12)
    def mark(obj, ident_):
        obj['component_id'] = ident_; obj['kind'] = 'debug_optics'; obj['debug_layer'] = 'WF_DEBUG_OPTICS'
        return obj
    paths = {}
    for key, r in g['routes'].items():
        paths[f'FEED_{key}'] = r['trunk']
        paths.update({f'LEG_{key}_{leg["index"]}': leg['points'] for leg in r['legs']})
    paths.update({f'GATE_PATH_{key}_L{j}': b for (key, j), b in g['gate_beams'].items()})
    for name, pts in paths.items():
        mark(line(c, f'DBG_OPT_{name}', pts, .02, axis), f'WF.DRIVE.DEBUG.OPT.{name}')
        mark(line(c, f'DBG_OPT_CLEARANCE_{name}', pts, m['beam_radius_m']+m['beam_clearance_m'], clear), f'WF.DRIVE.DEBUG.OPT.CLEARANCE.{name}')
    for j, pd in enumerate(g['pads'], 1):
        a0, a1, r = pd['a0'], pd['a1'], pd['r']-.03
        loop = [dm.radial(pd['x0'], r, a0+(a1-a0)*k/8) for k in range(9)]+[dm.radial(pd['x1'], r, a1-(a1-a0)*k/8) for k in range(9)]
        mark(line(c, f'DBG_OPT_ILLUMINATED_L{j}', loop+[loop[0]], .025, axis), f'WF.DRIVE.DEBUG.OPT.ILLUMINATED.L{j}')
    for key, r in g['routes'].items():
        obj = line(c, f'DBG_OPT_BORE_{key}', r['bore'], m['optical_channel_radius_m'], bore)
        mark(obj, f'WF.DRIVE.DEBUG.OPT.BORE.{key}')['meaning'] = 'Clearance volume of the dog-leg bore: no straight line passes it end to end (screened); cold optics stay outside its sight cone'
