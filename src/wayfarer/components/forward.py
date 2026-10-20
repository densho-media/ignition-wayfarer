"""WF_FORWARD_SHIELD recipe (FGR-006, FWD-001): conical fixed shield on a conical truss, recessed EYE wells, Dust Lance, the full-area sacrificial
disruptor layer, sector keels and ties, diversion-field zone and damage displays and the Aegis Dustbreak Crown. Every position, radius and driver
expression comes from forward_shield.py; nothing here defines physics.

Statuses: the bow form, shield diameter and ~3 m crown depth are WORKING sourced values; the structure (skin, truss, rim, keels, ties, layer, posts,
wells, Lance profile, housing, bays, carriages, shutters) is PROTOTYPE geometry; the diversion field zone and damage cells are normalized display layers
over OPEN values. The Crown is a PROTOTYPE proxy of a WORKING / accepted direction (OD-021 OPEN). Every object carries its HSFP design class
(forward_shield.design_classes, 98!A58).
"""
import math
import bpy
from mathutils import Matrix, Vector, geometry
from common import empty, material, mesh, loft, line, ring, cut, cylinder
import forward_shield as fsh

TAU = 2*math.pi
SKIN_SEGMENTS = 96


CLASSES = {}      # kind -> HSFP design class, set from the spec at the start of forward_shield()


def mark(obj, status, ref, kind, note=None):
    """Canon status of what the object represents; geometry is always PROTOTYPE. A kind without a design class fails the build."""
    obj['canon_status'] = status; obj['source_ref'] = ref; obj['kind'] = kind
    obj['geometry_status'] = 'PROTOTYPE'; obj['design_class'] = CLASSES[kind]
    if note:
        obj['note'] = note
    return obj


def circle(r, n, cy=0.0, cz=0.0):
    return [(cy+r*math.cos(TAU*i/n), cz+r*math.sin(TAU*i/n)) for i in range(n)]


def box_vertices(center, size):
    """Axis-aligned box about `center`; faces wound outward (same layout as the rig proxies)."""
    lo = [a-b/2 for a, b in zip(center, size)]; hi = [a+b/2 for a, b in zip(center, size)]
    vertices = [(x, y, z) for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])]
    return vertices, [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]


def local_box(c, name, center, size, mat, kind, parent=None):
    vertices, faces = box_vertices(center, size)
    obj = mesh(c, name, vertices, faces, mat, kind=kind)
    if parent is not None:
        obj.parent = parent
    return obj


def flat_ring(c, name, x, r0, r1, mat, kind, segments=SKIN_SEGMENTS):
    """One-sided annulus in the plane X = x (normal +X)."""
    vertices = [(x, r*math.cos(TAU*j/segments), r*math.sin(TAU*j/segments)) for r in (r0, r1) for j in range(segments)]
    faces = [(j, segments+j, segments+(j+1) % segments, (j+1) % segments) for j in range(segments)]
    return mesh(c, name, vertices, faces, mat, kind=kind)


def plate_mesh(loops, x_top, x_aft):
    """Top (+X) and aft (-X) faces of a flat plate from outline polylines (first = outer boundary, the rest are holes), triangulated, so holes are exact
    circles. Returns (vertices, faces)."""
    triangles = geometry.tessellate_polygon([[Vector((y, z, 0.0)) for y, z in loop] for loop in loops])
    flat = [pt for loop in loops for pt in loop]
    vertices = [(x_top, y, z) for y, z in flat]+[(x_aft, y, z) for y, z in flat]
    n = len(flat); faces = []
    for a, b, d in triangles:
        # tessellate_polygon winds in the (y, z) plane; the top face must face +X, the aft face -X.
        top = (a, b, d); cross = (flat[b][0]-flat[a][0])*(flat[d][1]-flat[a][1])-(flat[b][1]-flat[a][1])*(flat[d][0]-flat[a][0])
        if cross < 0:
            top = (a, d, b)
        faces.append(top); faces.append((n+top[0], n+top[2], n+top[1]))
    return vertices, faces


def hub_plate(c, s, mat):
    """The skin disc inside the body radius: top and aft faces with a hole for every EYE well and the Dust Lance."""
    st = fsh.stations(s); p = fsh.prototype(s)
    loops = [circle(st['hub_r'], SKIN_SEGMENTS)]
    for w in fsh.wells(s):
        if fsh.in_hub(s, w):
            loops.append(circle(w['radius'], 48, w['y'], w['z']))
    loops.append(circle(p['lance_base_radius_m'], 48))
    vertices, faces = plate_mesh(loops, st['face'], st['skin_aft'])
    obj = mesh(c, 'Shield_Hub_Plate', vertices, faces, mat, kind='shield_hub')
    obj['wells'] = len(fsh.wells(s))
    return obj


def disruptor_layer_mesh(c, s, layer, mat):
    """One layer: the flat hub disc (EYE ports and Lance hole) and the conical annulus (12 Crown ports), merged into one mesh."""
    flat = fsh.disruptor_flat(s, layer)
    v0, f0 = plate_mesh(flat['loops'], flat['x_front'], flat['x_aft'])
    v1, f1, omitted = fsh.disruptor_mesh(s, layer)
    obj = mesh(c, layer['name'], v0+v1, f0+[tuple(len(v0)+i for i in f) for f in f1], mat, kind='disruptor_layer')
    obj['ports'] = len(fsh.wells(s))+len(fsh.crown_ports(s))+1; obj['omitted_cone_quads'] = omitted
    return obj


def field_zone_mesh(c, s, mat):
    """The diversion-field display: a closed elongated surface of revolution (outer surface plus the pinched inner clearance surface around the Lance),
    local to the object origin at the shield face so the strength driver scales it about the face."""
    st = fsh.stations(s); z = fsh.field_zone(s); n = s['forward_shield']['display']['field_zone_around']; N = len(z['x'])
    ring = lambda x, r: [(x-st['face'], r*math.cos(TAU*j/n), r*math.sin(TAU*j/n)) for j in range(n)]
    vs = []
    for i in range(N):
        vs += ring(z['x'][i], z['r_out'][i])
    inner = {}
    for i in range(1, N-1):
        inner[i] = len(vs)//n; vs += ring(z['x'][i], z['r_in'][i])
    inner[0] = 0; inner[N-1] = N-1                       # the surfaces meet at both pinched ends
    faces = []
    for i in range(N-1):
        for j in range(n):
            j1 = (j+1) % n
            faces.append((i*n+j, (i+1)*n+j, (i+1)*n+j1, i*n+j1))
            faces.append((inner[i]*n+j1, inner[i+1]*n+j1, inner[i+1]*n+j, inner[i]*n+j))
    obj = mesh(c, 'Field_Zone', vs, faces, mat, kind='field_display')
    obj.location = (st['face'], 0.0, 0.0)
    return obj


def damage_cell(c, cell, mat, segments=3):
    vertices = []
    for i in range(segments+1):
        a = cell['a0']+(cell['a1']-cell['a0'])*i/segments
        vertices += [(cell['x_r1'], cell['r1']*math.cos(a), cell['r1']*math.sin(a)), (cell['x_r0'], cell['r0']*math.cos(a), cell['r0']*math.sin(a))]   # on the conical face
    faces = [(2*i, 2*i+2, 2*i+3, 2*i+1) for i in range(segments)]
    obj = mesh(c, f"Shield_Damage_Cell_{cell['ring']:02}_{cell['sector']:02}", vertices, faces, mat, kind='damage_cell')
    obj.hide_viewport = obj.hide_render = True      # saved neutral: no damage shown; the hide drivers follow damage_state and repair_state
    return obj


def add_driver(target, path, index, expression, control):
    owner = target.data if path.startswith('data.') else target
    prop = path[5:] if path.startswith('data.') else path
    fc = owner.driver_add(prop) if index == -1 else owner.driver_add(prop, index)
    fc.driver.type = 'SCRIPTED'; fc.driver.expression = expression
    for var in fsh.expression_variables(expression):
        v = fc.driver.variables.new(); v.name = var; v.type = 'SINGLE_PROP'
        v.targets[0].id_type = 'OBJECT'; v.targets[0].id = control; v.targets[0].data_path = f'["{fsh.VARIABLES[var]}"]'
    if not fc.driver.is_simple_expression:
        raise ValueError(f'{target.name}.{path}: driver is not a simple expression: {expression}')
    target['forward_driven'] = True
    return fc


def forward_shield(c, s):
    st = fsh.stations(s); p = fsh.prototype(s); fd = s['forward_defense']; disp = s['forward_shield']['display']
    CLASSES.clear(); CLASSES.update(fsh.design_classes(s))
    skin = material('Shield', (.48, .43, .28)); structure = material('Structure', (.30, .40, .48)); well = material('EyeWell', (.13, .20, .24))
    lance_mat = material('DustLance', (.70, .66, .58)); field_mat = material('DiversionField', (.12, .62, .83), 1.2, alpha=disp['field_zone_alpha'])
    layer_mat = material('DisruptorLayer', (.78, .72, .46), 0.15, alpha=disp['disruptor_alpha']); keel_mat = material('SectorKeel', (.36, .52, .60))
    damage_mat = material('ShieldDamage', (1.0, .28, .10), 1.5)
    housing = material('CrownHousing', (.26, .29, .33)); carriage_mat = material('CrownCarriage', (.58, .38, .22))
    emitter_mat = material('CrownEmitter', (.95, .32, .30), .6); shutter_mat = material('CrownShutter', (.40, .42, .47))
    # --- skin: the conical annulus outside the body radius (12 Crown windows), and the flat hub plate with the well and Lance holes ---
    vs, fs_, omitted = fsh.shield_skin_mesh(s)
    obj = mesh(c, 'Shield_Skin', vs, fs_, skin, kind='shield_skin')
    mark(obj, 'WORKING', 'shield_profile', 'shield_skin', f"[PHYSICS_LOCKED] Radius 45 m = WORKING 90 m diameter / 2; the face is flat to r {st['cone_r']:g} m then a cone sweeping aft by the WORKING ~3 m crown depth; 0.10 m skin is a display thickness (stack OPEN).")
    obj['windows'] = len(fsh.crown_skin_windows(s)); obj['omitted_quads'] = omitted
    outer = [w for w in fsh.wells(s) if not fsh.in_hub(s, w)]
    if outer:          # outer Eye layout: the wells open the cone (study layout, forward_defense.eye_layout)
        cut(obj, [((st['truss_aft_hub']-4.0, w['y'], w['z']), (st['face']+1.0, w['y'], w['z']), w['radius']) for w in outer]); obj['cone_wells'] = len(outer)
    mark(hub_plate(c, s, skin), 'WORKING', 'bow_form', 'shield_hub', '[ENGINEERING_FLEXIBLE] Flat skin inside the body radius, open at the four EYE wells and the Dust Lance root.')
    R = st['shield_r']; ri = st['rim_inner_r']
    obj = loft(c, 'Shield_Rim', [(fsh.truss_aft_at(s, R), R), (fsh.skin_aft_at(s, R), R), (fsh.skin_aft_at(s, ri), ri), (fsh.truss_aft_at(s, ri), ri), (fsh.truss_aft_at(s, R), R)],
               structure, caps=False, segments=SKIN_SEGMENTS, kind='shield_rim')
    mark(obj, 'OPEN', 'bow_form', 'shield_rim', '[ENGINEERING_FLEXIBLE] Rim girder r 44.5-45 m over the full truss depth; it is the Crown housing outer wall. Final rim/truss geometry OPEN (14!G12).')
    # --- conical truss ---
    t = fsh.truss(s)
    x0, x1, ro, ri_ = t['hub_ring']
    mark(loft(c, 'Shield_Truss_Hub_Ring', [(x0, ro), (x1, ro), (x1, ri_), (x0, ri_), (x0, ro)], structure, caps=False, segments=SKIN_SEGMENTS, kind='shield_truss'), 'OPEN', 'bow_form', 'shield_truss',
         '[ENGINEERING_FLEXIBLE] Flat hub ring.')
    for sp in t['spokes']:
        for label, pts in sp['members']:
            if f"Truss_Spoke_{sp['index']:02}_{label}" in t['removed']:
                continue          # replaced by the outer-Eye alternate truss (forward_defense.eye_layout)
            mark(line(c, f"Truss_Spoke_{sp['index']:02}_{label}", pts, t['member_radius'], structure, kind='shield_truss'), 'OPEN', 'bow_form', 'shield_truss',
                 '[ENGINEERING_FLEXIBLE] Conical two-chord truss member; sizing and FEA OPEN (14!G26).')
    for k, r in enumerate(t['rings']):
        if f"Truss_Ring_{k+1:02}" in t['removed']:
            continue
        mark(ring(c, f"Truss_Ring_{k+1:02}", r['x'], r['radius'], t['member_radius'], structure, kind='shield_truss'), 'OPEN', 'bow_form', 'shield_truss', '[ENGINEERING_FLEXIBLE] Truss ring.')
    # FWD-V2 outer Eye layout (forward_defense.eye_layout, STUDY): collars round each well, split spokes, ring arcs, per-facet frames and raceways.
    raceway = material('EyeRaceway', (.55, .45, .30))
    for q in t['alternate']:
        kind = {'facet_frame': 'eye_facet_frame', 'raceway': 'eye_raceway'}.get(q['role'], 'shield_truss')
        if q.get('plate'):
            (x0, y, z), (x1, _, _) = q['pts']; obj = cylinder(c, q['name'], (x0+x1)/2, x1-x0, q['radius'], structure, y, z, kind=kind)
        else:
            obj = line(c, q['name'], q['pts'], q['radius'], raceway if q['role'] == 'raceway' else structure, kind=kind)
        mark(obj, 'OPEN', 'eye_layout', kind, f"[ENGINEERING_FLEXIBLE] FWD-V2 {q['role']} of the outer-Eye alternate truss (Eye 45 FD-A01/A02, STUDY layout; r4 WORKING, FD-B07); sizing, mass and FEA OPEN.")
        obj['alt_role'] = q['role']; obj['owner_well'] = q['well']
    # --- sector path: keels at the sourced sector radius and azimuths, end hoops and the nine ties ---
    keels = fsh.sector_keels(s)
    for k in keels:
        mark(line(c, k['name'], [k['a'], k['b']], k['radius'], keel_mat, kind='sector_keel'), 'OPEN', 'shield_load_path', 'sector_keel',
             '[ENGINEERING_FLEXIBLE] Brow-side sector keel at the sourced sector radius and azimuth (07!A10, A13, WORKING); existence ahead of ring B, length and free aft end PROTOTYPE; sizing OPEN (14!G26).')
    for label, key in (('Aft', 'x0'), ('Head', 'x1')):
        mark(ring(c, f'Shield_Sector_Frame_{label}', keels[0][key], keels[0]['r'], keels[0]['hoop_radius'], keel_mat, kind='sector_frame'), 'OPEN', 'shield_load_path', 'sector_frame',
             '[ENGINEERING_FLEXIBLE] Keel aft hoop: tied out to the Q45 bypass collar by the three keel ties.' if label == 'Aft'
             else '[ENGINEERING_FLEXIBLE] Keel-end hoop tying the three sector keels together.')
    for tie in fsh.sector_ties(s):
        mark(line(c, tie['name'], [tie['a'], tie['b']], tie['radius'], structure, kind='sector_tie'), 'OPEN', 'shield_load_path', 'sector_tie',
             '[ENGINEERING_FLEXIBLE] Tie from the keel head into the Brow truss through a derived hull opening; part of the Brow sector frame.')
    # --- Q45 bypass collar: two-chord girders round the rotor bay from the Brow truss into the sector rails ---
    col = fsh.bypass_collar(s); note = ('[ENGINEERING_FLEXIBLE] Q45 stationary external bypass collar (15!A99, WORKING principle): carries the Brow keels and outer '
                                       'truss round the swept rotor bay into the three primary sectors; radii, depth, lacing and sizes PROTOTYPE (15!G99), FEA and mass OPEN.')
    for m in col['members']:
        obj = mark(line(c, m['name'], [m['a'], m['b']], m['radius'], keel_mat, kind='bypass_collar'), 'WORKING', 'brow_rotor_bypass', 'bypass_collar', note)
        obj['collar_role'] = m['role']; obj['sector'] = m['sector']
    for h in col['hoops']:
        mark(ring(c, h['name'], h['x'], h['r'], h['radius'], keel_mat, kind='bypass_collar'), 'WORKING', 'brow_rotor_bypass', 'bypass_collar', note)['collar_role'] = 'hoop'
    # --- EYE wells: open tubes from each facet face to the shield face ---
    for w in fsh.wells(s):
        obj = loft(c, f"EYE_Well_{w['index']:02}", [(w['x0'], w['radius']), (w['x1'], w['radius'])], well, center=(0, w['y'], w['z']), caps=False, segments=32, kind='eye_well')
        mark(obj, 'WORKING', 'eye_wells', 'eye_well', '[PHYSICS_LOCKED] Protected aperture well; shutter/window/baffle solution OPEN (OD-020).')
        obj['owner_facet'] = w['label']; obj['component_id'] = f"WF.FORWARD.WELL.{w['index']:02}"
    # --- EYE eyelids (FD-E03, AG-007): two armoured leaves per well on the face under the layer, parting tangentially; window cartridge in the well ---
    lid_mat = material('EyeShutter', (.34, .36, .40)); window_mat = material('EyeWindow', (.55, .80, .86), .1, alpha=.35)
    for e in fsh.eye_shutters(s):
        j = e['index']
        frame = empty(c, f'EYE_Shutter_Frame_{j:02}', (e['x'], e['y'], e['z']), ident=f'WF.FORWARD.EYE_SHUTTER.{j:02}', kind='eye_shutter_frame')
        frame.rotation_euler = (Matrix.Rotation(e['azimuth'], 4, 'X') @ Matrix.Rotation(e['tilt'], 4, 'Z')).to_euler('XYZ')   # tilt 0 in the flat hub
        frame.empty_display_type = 'PLAIN_AXES'; frame['owner_facet'] = e['label']
        frame['frame'] = 'local +X axial, +Y radial, +Z tangential'
        mark(frame, 'WORKING', 'eye_wells', 'eye_shutter_frame', '[ENGINEERING_FLEXIBLE] Eyelid frame at the well mouth (FD-E03).')
        for leaf in e['leaves']:
            obj = local_box(c, leaf['name'], (0.0, 0.0, 0.0), (e['thickness'], e['radial'], e['tangential']), lid_mat, 'eye_shutter', frame)
            obj.location = (leaf['axial'], 0.0, leaf['sign']*e['open_t']); obj['owner_facet'] = e['label']      # leaf B one thickness forward: lap seam (FD-B10)
            mark(obj, 'WORKING', 'eye_wells', 'eye_shutter', '[ENGINEERING_FLEXIBLE] PROTOTYPE armoured eyelid leaf (Eye 45 FD-E03, S&E 50 AG-007); saved open (observe); drive, materials, closing time and erosion life OPEN (OD-020).')
        wn = e['window']
        obj = loft(c, wn['name'], [(wn['x']-wn['thickness']/2, wn['radius']), (wn['x']+wn['thickness']/2, wn['radius'])], window_mat, center=(0, e['y'], e['z']), segments=32, kind='eye_window')
        obj['owner_facet'] = e['label']
        mark(obj, 'WORKING', 'eye_wells', 'eye_window', '[ENGINEERING_FLEXIBLE] Replaceable sacrificial window cartridge inside the well, ahead of the facet (Q43: no exposed pane); material, thickness and swap path OPEN (OD-020).')
    # --- Dust Lance: root sleeve from the EYE shared-mount face, cone, replaceable tip cartridge ---
    L = fsh.lance(s)
    mark(loft(c, 'Shield_Spine_Column', [(L['column'][0], L['base_r']), (L['column'][1], L['base_r'])], lance_mat, kind='shield_spine_column'), 'BASELINE', 'dust_lance', 'shield_spine_column',
         'PROTOTYPE load path: continuation of the Momentum Spine / shield hub (14!H15) from the spine end through the EYE mount bore to the hub; the Lance roots on it. Sizing OPEN.')
    for m in fsh.mount_struts(s):
        mark(line(c, m['name'], [m['a'], m['b']], m['radius'], structure, kind='shield_mount'), 'BASELINE', 'dust_lance', 'shield_mount',
             'PROTOTYPE radial strut (hub path) from the spine-continuation column to the truss hub ring, through a derived hull opening; sizing OPEN.')
    obj = mark(loft(c, 'Dust_Lance', [(L['x0'], L['base_r']), (L['cone_end'], L['tip_r'])], lance_mat, kind='dust_lance'), 'BASELINE', 'dust_lance', 'dust_lance', 'Length, taper and material OPEN (OD-017); 12 m is a WORKING value.')
    obj['engineering_status'] = 'OPEN: Dust Lance length, taper, material and tip life (OD-017)'
    mark(loft(c, 'Dust_Lance_Tip_Cartridge', [(L['cone_end'], L['tip_r']), (L['x1'], L['tip_r'])], lance_mat, kind='dust_lance_tip'), 'WORKING', 'mec_lance_tip', 'dust_lance_tip',
         'Replaceable instrumented sacrificial tip (MEC-016); lifetime OPEN.')
    # --- full-area sacrificial disruptor: conical layer(s) with EYE, Lance and Crown ports, carried on posts at truss nodes ---
    for layer in fsh.disruptor_layers(s):
        obj = disruptor_layer_mesh(c, s, layer, layer_mat)
        outer_ports = [q for q in fsh.eye_ports(s, layer) if math.hypot(q['y'], q['z'])-q['radius'] > st['cone_r']]
        if outer_ports:
            cut(obj, [((st['face'], q['y'], q['z']), (st['lance_tip'], q['y'], q['z']), q['radius']) for q in outer_ports])
        mark(obj, 'WORKING', 'eye_disruptor_layer', 'disruptor_layer',
             f"[PHYSICS_LOCKED existence, full diameter and ahead of the Brow; standoff {layer['standoff']:g} m, display thickness and ports ENGINEERING_FLEXIBLE for owner review] FWD1 sacrificial layer: material, thickness, count and spacing OPEN (Eye 40!E33). Rendered translucent; checks treat it as opaque.")
        obj['standoff_m'] = layer['standoff']; obj['open_fraction_diagnostic'] = fsh.disruptor_open_fraction(s, layer)
    for post in fsh.disruptor_posts(s):
        mark(line(c, post['name'], [post['a'], post['b']], post['radius'], structure, kind='disruptor_post'), 'OPEN', 'eye_disruptor_layer', 'disruptor_post',
             '[ENGINEERING_FLEXIBLE] Post carrying the layer on a truss node (load path layer - post - truss node - truss); sizing OPEN.')
    # --- diversion field zone: collapsed (hidden) at field_on = 0 ---
    mark(field_zone_mesh(c, s, field_mat), 'OPEN', 'magnetic_diversion', 'field_display',
         '[ARTISTIC] PROTOTYPE display of an elongated axial/cusp-like zone around and behind the Lance (Q4); field strength, topology and coil geometry are OPEN (OD-018). Not the 10,000 m3 study volume.')
    # --- damage cells (state only) ---
    for cell in fsh.damage_cells(s):
        mark(damage_cell(c, cell, damage_mat), 'WORKING', 'regenerative_shield', 'damage_cell', '[ARTISTIC] Display state only; repair rates and feedstock OPEN (OD-019).')
    # --- Aegis Dustbreak Crown ---
    cr = fsh.crown(s); n = len(cr['bays']); sh = cr['shutter']; car = cr['carriage']
    mark(loft(c, 'Crown_Housing_Inner_Wall', [(cr['x0'], cr['inner_r']), (cr['x1'], cr['inner_r'])], housing, caps=False, segments=SKIN_SEGMENTS, kind='crown_housing'), 'OPEN', 'crown_architecture', 'crown_housing',
         '[PHYSICS_LOCKED housing band r 41.0-44.5] Housing inner wall.')
    mark(flat_ring(c, 'Crown_Housing_Aft_Plate', cr['x0'], cr['inner_r'], cr['outer_r'], housing, 'crown_housing'), 'OPEN', 'crown_architecture', 'crown_housing', '[PHYSICS_LOCKED housing band] Housing aft plate; the rim girder is the outer wall.')
    half = math.pi/n; pt = s['forward_shield']['prototype']['crown_partition_thickness_m']
    for k, b in enumerate(cr['bays']):
        phi = b['azimuth']+half
        # Partition between bays k and k+1, in a frame rotated to phi; it sits on a truss-spoke azimuth and carries the spoke on to the rim girder.
        vertices, faces = box_vertices((cr['xc'], (cr['inner_r']+cr['outer_r'])/2, 0.0), (cr['x1']-cr['x0'], cr['outer_r']-cr['inner_r'], pt))
        cs, sn = math.cos(phi), math.sin(phi)
        vertices = [(x, y*cs-z*sn, y*sn+z*cs) for x, y, z in vertices]
        mark(mesh(c, f'Crown_Partition_{k+1:02}', vertices, faces, housing, kind='crown_housing'), 'OPEN', 'crown_architecture', 'crown_housing')
    # M4 slice 3 (forward_shield.rear_construction, PROTOTYPE): gussets at every truss node, a dark rib on each bay partition and an ochre
    # service hatch per bay on the housing aft plate, all inside the truss envelope.
    rear_mats = {'truss_node': structure, 'crown_housing_rib': material('CrownRib', (.16, .19, .22)), 'crown_service_hatch': material('CrownServiceHatch', (.78, .60, .24)),
                 'brow_panel_joint': material('BrowPanelJoint', (.16, .19, .22))}
    rear_notes = {'truss_node': '[ENGINEERING_FLEXIBLE] Gusset plate at a truss node in its spoke plane; joint design and sizing OPEN (14!G26).',
                  'crown_housing_rib': '[ENGINEERING_FLEXIBLE] Rib on the housing aft plate over a bay partition (where the truss spoke lands); sizing OPEN.',
                  'crown_service_hatch': '[ENGINEERING_FLEXIBLE] Service hatch for carriage maintenance from behind; mechanism and service path OPEN.',
                  'brow_panel_joint': '[ENGINEERING_FLEXIBLE] Joint between replaceable Brow panels on the skin aft face (14 regenerative_brow); panel size, seal and attachment OPEN (S04 slice 2).'}
    for q in fsh.rear_construction(s):
        mark(mesh(c, q['name'], q['vertices'], q['faces'], rear_mats[q['kind']], kind=q['kind']), 'OPEN', 'bow_form' if q['kind'] in ('truss_node', 'brow_panel_joint') else 'crown_architecture', q['kind'], rear_notes[q['kind']])
    for b in cr['bays']:
        j = b['index']
        bay = empty(c, f'Crown_Bay_{j:02}', ident=f'WF.FORWARD.CROWN.BAY.{j:02}', kind='crown_bay')
        bay.rotation_euler.x = b['azimuth']; bay.empty_display_type = 'PLAIN_AXES'; bay.empty_display_size = 1.0
        bay['azimuth_turns'] = b['turn']; bay['frame'] = 'local +X axial, +Y radial, +Z tangential'
        mark(bay, 'WORKING', 'crown_architecture', 'crown_bay', '[PHYSICS_LOCKED] One of 12 bays at 30 degrees (Q6).')
        shutter = local_box(c, f'Crown_Shutter_{j:02}', (0.0, 0.0, 0.0), (sh['thickness'], sh['radial'], sh['tangential']), shutter_mat, 'crown_shutter', bay)
        shutter.location = (sh['x'], sh['r_centre'], 0.0)
        mark(shutter, 'WORKING', 'crown_architecture', 'crown_shutter', '[ENGINEERING_FLEXIBLE] Armoured shutter under the conical skin window; it slides tangentially. Geometry, opening time and erosion life OPEN (14!G20).')
        cv = fsh.crown_port_covers(s)[j-1]
        cover = local_box(c, f'Crown_Port_Cover_{j:02}', (0.0, 0.0, 0.0), (cv['thickness'], cv['radial'], cv['tangential']), shutter_mat, 'crown_port_cover', bay)
        cover.location = (cv['x'], cv['r_centre'], 0.0)
        mark(cover, 'WORKING', 'eye_crown', 'crown_port_cover', '[ENGINEERING_FLEXIBLE] Q44 normally closed armoured cover behind the small disruptor port; it slides tangentially with the skin shutter when the bay engages. Exact aperture, cover size and cycle OPEN (Eye 40!A36, OD-021).')
        frame = empty(c, f'Crown_Carriage_{j:02}', ident=f'WF.FORWARD.CROWN.CARRIAGE.{j:02}', kind='crown_carriage_frame')
        frame.parent = bay; frame.location = (cr['carriage_x'], cr['stowed_r'], 0.0); frame.empty_display_type = 'PLAIN_AXES'; frame.empty_display_size = .5
        mark(frame, 'WORKING', 'crown_architecture', 'crown_carriage_frame', '[ENGINEERING_FLEXIBLE] Stowed behind the shutter; the engaged pose translates it forward along +X (driver), never radially.')
        body = local_box(c, f'Crown_Carriage_Body_{j:02}', (0.0, 0.0, 0.0), (car['axial'], car['radial'], car['tangential']), carriage_mat, 'crown_carriage', frame)
        mark(body, 'WORKING', 'crown_architecture', 'crown_carriage', '[ENGINEERING_FLEXIBLE] Carriage size and travel OPEN (OD-021); MEC-018 wear surfaces apply.')
        e, l = cr['emitter'], cr['launcher']; front = car['axial']/2
        # AG-008 gimbal head: emitter and launcher turn together about a pivot on the carriage front (local +X boresight); crown_point drives it.
        head = empty(c, f'Crown_Head_{j:02}', ident=f'WF.FORWARD.CROWN.HEAD.{j:02}', kind='crown_head_frame')
        head.parent = frame; head.location = (front, 0.0, 0.0); head.empty_display_type = 'ARROWS'; head.empty_display_size = .6
        mark(head, 'WORKING', 'crown_architecture', 'crown_head_frame', f"[ENGINEERING_FLEXIBLE] Precision gimbal pivot (FD-E04); {fsh.prototype(s)['crown_head_max_deg']:g} deg is a PROTOTYPE display limit, pointing range and accuracy OPEN (OD-021).")
        em = loft(c, f'Crown_Emitter_{j:02}', [(0.0, e['radius']), (e['length'], e['radius'])], emitter_mat, center=(0, 0.0, e['t']), segments=16, kind='crown_emitter')
        em.parent = head; mark(em, 'WORKING', 'crown_architecture', 'crown_emitter', '[ENGINEERING_FLEXIBLE] One pulsed ablation/ionization emitter per carriage; effector mix OPEN.')
        lt = loft(c, f'Crown_Launcher_{j:02}', [(e['length']-l['length'], l['radius']), (e['length'], l['radius'])], emitter_mat, center=(0, 0.0, l['t']), segments=12, kind='crown_launcher')
        lt.parent = head; mark(lt, 'WORKING', 'crown_architecture', 'crown_launcher', '[ENGINEERING_FLEXIBLE] One interceptor launcher tube per carriage; mass and dispersion OPEN.')
        iface = empty(c, f'IF_CROWN_SECTOR_{j:02}', (cr['carriage_x'], cr['stowed_r'], 0.0), kind='interface'); iface.parent = bay
        iface['engineering_status'] = 'OPEN: Crown carriage mechanics, shutter and effector interfaces not designed (OD-021); position PROTOTYPE'
    # --- interfaces ---
    f = empty(c, 'IF_SHIELD_FACE', (st['face'], 0, 0)); f['engineering_status'] = f'OPEN: shield stack not designed (OD-014, OQ-F2); OPEN: attachment to primary structure not designed ({fsh.ATTACHMENT_REFS})'
    t_ = empty(c, 'IF_DUST_LANCE_TIP', (st['lance_tip'], 0, 0)); t_['engineering_status'] = 'OPEN: Dust Lance tip cartridge interface (MEC-016)'
    z = empty(c, 'IF_FIELD_ZONE', ((st['field'][0]+st['field'][1])/2, 0, 0)); z['engineering_status'] = 'OPEN: field topology, coils and power (OD-018)'
    r_ = empty(c, 'IF_SHIELD_SPINE_JOINT', (st['spine_end'], 0, 0)); r_['engineering_status'] = f'OPEN: joint between the Momentum Spine end and the shield column; sizing and attachment not designed ({fsh.ATTACHMENT_REFS})'
    for k in keels:
        q = empty(c, f"IF_SHIELD_SECTOR_{k['index']}", k['b']); q['engineering_status'] = 'OPEN: joint between the forward sector keel and the shield truss; sizing OPEN (14!G26)'
        a = empty(c, f"IF_SHIELD_SECTOR_AFT_{k['index']}", k['a']); a['engineering_status'] = 'OPEN: joint between the keel aft end and its Q45 bypass-collar keel tie; sizing and FEA OPEN (15!E99, 14!G26)'
    layer0 = fsh.disruptor_layers(s)[0]
    q = empty(c, 'IF_DISRUPTOR_LAYER', (layer0['aft_hub'], 0, 0)); q['engineering_status'] = 'OPEN: disruptor layer material, thickness, count, spacing and attachment not designed (Eye 40!E33, 15!G45)'
    # --- control, drivers ---
    ctrl = empty(c, fsh.CONTROL, ident='WF.FORWARD.STATE_CONTROL', kind='state_control')
    ctrl.empty_display_type = 'CUBE'; ctrl.empty_display_size = .6; ctrl.location = (st['face']-5, 0, -(st['shield_r']+3))
    for key, value in fsh.neutral(s).items():
        ctrl[key] = float(value)
        ctrl.id_properties_ui(key).update(min=0.0, max=1.0, soft_min=0.0, soft_max=1.0, description=fsh.PROPS[key])
        ctrl.property_overridable_library_set(f'["{key}"]', True)
    ctrl['units'] = 'normalized 0-1; no physical rating'
    ctrl['state'] = 'NEUTRAL (all controls 0); configurations are posed in memory'
    ctrl['engineering_status'] = 'OPEN: field strength and topology (OD-018), repair rates (OD-019), Crown geometry and power (OD-021) are OPEN; this is a normalized PROTOTYPE rig'
    ctrl['crown_azimuth_rule'] = 'turn fraction from +Y toward +Z; the four bays around it open when crown_engage > 0'
    mark(ctrl, 'WORKING', 'magnetic_diversion', 'state_control', '[ENGINEERING_FLEXIBLE] Normalized PROTOTYPE rig control.')
    objects = {o.name: o for o in c.objects}
    for name, path, index, expression in fsh.drivers(s):
        add_driver(objects[name], path, index, expression, ctrl)
    # Flush world matrices (bay frames rotate their children) so the saved interfaces carry current positions.
    bpy.context.view_layer.update()
    return ctrl
