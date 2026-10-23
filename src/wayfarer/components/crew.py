"""P1-001 crew-transfer recipes. Shapes, positions and interfaces come from crew_transfer.

WF_CREW_TRANSFER holds the stationary side (trunk in the spine bore, spine ports, fitting connectors, refuge port and, since Q46, the
spine-port gates). The rotating side (one crew tube per ring sector with its hatch and spoke brackets) lives in WF_HABITAT, parented to its
rotor; the human-entry vestibule is the despun transfer drum (Q46, MEC-019), parented to Drum_j, which follows its rotor only while
TRANSFER_j_CTRL['drum_sync'] is 1. The same route serves both habitat states because no room turns.
"""
import math
from mathutils import Vector
import bpy
from common import empty, material, mesh, line, cut, cylinder_mesh, revolve_mesh, tag
import crew_transfer as ct
import human_entry as he
import rotor_interface as ri

BASIS = 'PROTOTYPE [crew_transfer] proposal for owner review; no seal, hatch, pressure or structural sizing'
STATUS = {'TRUNK': 'OPEN OD-002: crew trunk in the spine bore; pressure shell and spine structure not designed',
          'SPINE_PORT': 'OPEN OD-002: spine-wall hatch into the rotary vestibule; framed spine opening not designed',
          'FITTING_CONNECTOR': 'OPEN D1/E4: connector from the crew trunk to the fitting; hatch and isolation not designed',
          'REFUGE_PORT': 'OPEN OD-011: refuge entry from the crew trunk; hatch, second egress and framed spine opening not designed',
          'STORE_PORT': 'OPEN HUM-002: SP-45 storeroom entry from the crew trunk; hatch seal, latch and framed spine opening not designed',
          'VESTIBULE': 'OPEN OD-002/MEC-006: hatch-isolated rotary vestibule; seals, volume and procedure not designed',
          'VESTIBULE_GUARD': 'OPEN OD-002/MEC-015: guard cavity between the primary and secondary rotary seal planes; seals, pressure sensing and procedure not designed',
          'STRUT': 'OPEN OD-002: vestibule-to-drum struts between the ring-stop lock pins; loads not designed',
          'COAST_TUBE': 'OPEN OD-002: pressurized crew passage carried by the crew spoke to the sector overhead hatch; pressure shell, elbows and loads not designed',
          'TUBE_BRACKET': 'OPEN OD-016: bracket tying the crew passage to its crew spoke rail; loads not designed',
          'PORT_GATE': 'OPEN OD-002/MEC-019: stationary-side closure (Q46): gate across the spine port, sliding forward in a pocket of the spine shell; seal, drive and pocket framing not designed',
          'DRUM_DOOR': 'OPEN OD-002/MEC-019: door of the despun transfer drum (Q46), sliding round the drum wall; seal, latch and drive not designed',
          'TUBE_HATCH': 'OPEN OD-002/MEC-019: rotating-side closure (Q46): hatch across the crew-tube collar, sliding round the ring into a pocket; seal, latch and drive not designed'}
DRUM_BASIS = 'Q46 / MEC-019 despun transfer drum (BASELINE architecture, 15!A87); PROTOTYPE drum, bearings, despin drive, seals and sync cycle'


def closure(c, s, q, ctrl, key, parent=None):
    """Q46: a closure plate (crew_transfer.closures) as a ring-segment mesh, driven by ctrl[key] (0 closed, saved; 1 open): a gate slides +X,
    a door or hatch turns about the ship axis (its parent's X axis)."""
    mat = material('TransferClosure', (.30, .44, .52)); vs, fs = ri.solid(q['x0'], q['x1'], q['r0'], q['r1'], q['t0'], q['t1'])
    obj = mesh(c, q['name'], vs, fs, mat, kind='transfer_closure'); ctrl[key] = 0.0
    if parent is not None:
        obj.parent = parent
    path, index, size = ('location', 0, q['slide']) if q['kind'] == 'PORT_GATE' else ('rotation_euler', 0, q['turn'])
    fc = obj.driver_add(path, index); fc.driver.type = 'SCRIPTED'; fc.driver.expression = f'o*{size!r}'
    v = fc.driver.variables.new(); v.name = 'o'; v.type = 'SINGLE_PROP'; v.targets[0].id_type = 'OBJECT'; v.targets[0].id = ctrl; v.targets[0].data_path = f'["{key}"]'
    if not fc.driver.is_simple_expression:
        raise ValueError(f'{obj.name}: driver is not a simple expression')
    obj['function'] = q['kind']; obj['canon_status'] = 'BASELINE'; obj['source_ref'] = 'despun_transfer_vestibule'; obj['geometry_basis'] = DRUM_BASIS
    obj['engineering_status'] = STATUS[q['kind']]; obj['opens'] = f'{size:.3f} m forward' if q['kind'] == 'PORT_GATE' else f'{math.degrees(size):.1f} deg round the axis'
    obj['clear_radius_m'] = q['clear']
    return obj


def label(obj, part):
    obj['function'] = part['role']
    seal = part['role'] in ('VESTIBULE', 'VESTIBULE_GUARD')
    obj['canon_status'] = 'WORKING' if seal else 'OPEN'
    obj['source_ref'] = 'rotary_transfer' if seal else 'rotor_transfer_open_item'
    obj['geometry_basis'] = BASIS
    obj['engineering_status'] = STATUS[part['role']]
    if part.get('edge'):
        obj['route_edge'] = ' <-> '.join(part['edge'])
    return obj


def interface(c, f, parent=None):
    obj = empty(c, f['name'], f['at']); obj['engineering_status'] = f['status']
    if f.get('pairs_with'):
        obj['pairs_with'] = f['pairs_with']
    if parent is not None:
        obj.parent = parent
    return obj


def hollow(c, s, part, mat, kind, cutters):
    """HUM-001 zone 2: a hollow crew part as a mesh, opened by the crew_transfer.bores cuts. The trunk is a closed pressure shell with end
    bulkheads of the passage wall; a connector is an open tube from the ship axis to its fitting root, trimmed by the trunk bore into an equal tee."""
    w = s['crew_transfer']['passage_wall_m']; a, b = part['points']; r, rc = part['radius'], part['hollow']
    if part['role'] == 'TRUNK':
        e = (Vector(b)-Vector(a)).normalized(); vs, fs = cylinder_mesh(a, b, r); vi, fi = cylinder_mesh(tuple(Vector(a)+e*w), tuple(Vector(b)-e*w), rc)
        vs, fs = vs+vi, fs+[tuple(reversed([k+len(vs) for k in q])) for q in fi]
    else:
        a = (a[0], 0.0, 0.0); L = (Vector(b)-Vector(a)).length
        vs, fs = revolve_mesh(a, b, [(0.0, rc), (L, rc), (L, r), (0.0, r)])
    obj = cut(mesh(c, part['name'], vs, fs, mat, kind=kind), cutters)
    obj['clear_radius_m'] = rc
    return obj


def lines(c, name, segments, radius, mat, kind):
    """Several straight rods as one curve object (one POLY spline each): ladder rungs and bracket sets."""
    data = bpy.data.curves.new(f'{name}_Curve', 'CURVE'); data.dimensions = '3D'; data.resolution_u = 1; data.bevel_depth = radius; data.bevel_resolution = 1
    for a, b in segments:
        sp = data.splines.new('POLY'); sp.points.add(1); sp.points[0].co = (*a, 1); sp.points[1].co = (*b, 1)
    obj = bpy.data.objects.new(name, data); c.objects.link(obj); data.materials.append(mat)
    return tag(obj, name, kind)


def tube_mesh(fr, r, rc, n=48, neck=None):
    """HUM-001 zone 4: a hollow mitered tube along crew_transfer sweep frames: outer and inner rings on every joint's miter plane, quads between
    them and flat annular ends (outward-wound closed manifold). With a neck (crew_transfer.tube_neck, ring B) the root is a bulkhead of the
    passage wall, opened by the neck, which runs down from it to the neck's root: two more rings on each side of the profile."""
    P = ct.tube_point; outer = [(i, r, None) for i in range(len(fr['points']))]; inner = [(i, rc, None) for i in range(len(fr['points']))]
    if neck:
        low = neck['root']-neck['base']
        outer = [(0, neck['outer'], low), (0, neck['outer'], 0.0)]+outer
        inner = [(0, neck['clear'], low), (0, neck['clear'], neck['wall']), (0, rc, neck['wall'])]+inner[1:]
    m = len(outer); vs = [P(fr, i, rho, 2*math.pi*k/n, t) for i, rho, t in outer+inner for k in range(n)]
    o = lambda i, k: i*n+k % n; w = lambda i, k: (m+i)*n+k % n; fs = []
    for i in range(m-1):
        for k in range(n):
            fs += [(o(i, k), o(i, k+1), o(i+1, k+1), o(i+1, k)), (w(i, k), w(i+1, k), w(i+1, k+1), w(i, k+1))]
    for k in range(n):
        fs += [(o(0, k), w(0, k), w(0, k+1), o(0, k+1)), (o(m-1, k), o(m-1, k+1), w(m-1, k+1), w(m-1, k))]
    return vs, fs


def fixtures(c, s, items, parent=None):
    """HUM-001 handrails, brackets, frames, leaves, rails, chases, lights and panels (kind entry_fixture), in the vehicle or sector frame or
    parented to a rotor. A tube with r0 0 is a solid disc (a hatch leaf)."""
    rail = material('EntryHandrail', (.92, .78, .22)); light = material('EntryLight', (1.0, .93, .80), 12.0); frame = material('EntryFrame', (.55, .58, .60))
    panel = material('EntryPanel', (.10, .16, .20))
    for q in items:
        if q['shape'] == 'rod':
            obj = line(c, q['name'], q['points'], q['radius'], frame if 'guide' in q['role'] else rail, kind='entry_fixture')
        elif q['shape'] == 'rods':
            obj = lines(c, q['name'], q['segments'], q['radius'], rail, 'entry_fixture')
        elif q['shape'] == 'tube':
            L = (Vector(q['b'])-Vector(q['a'])).length
            vs, fs = cylinder_mesh(q['a'], q['b'], q['r1']) if q['r0'] == 0 else revolve_mesh(q['a'], q['b'], [(0.0, q['r0']), (L, q['r0']), (L, q['r1']), (0.0, q['r1'])])
            obj = mesh(c, q['name'], vs, fs, frame, kind='entry_fixture')
        else:
            mat = panel if 'panel' in q['role'] else light if 'light' in q['role'] else frame
            obj = mesh(c, q['name'], he.box_corners(None, q), [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)],
                       mat, kind='entry_fixture')
        obj['role'] = q['role']; obj['evidence_ref'] = 'human_entry_workflow'
        if parent is not None:
            obj.parent = parent


def crew_transfer(c, s):
    """WF_CREW_TRANSFER: stationary crew parts and interfaces in the vehicle frame; HUM-001 zone 2 hollow trunk, connector and trunk fixtures;
    the refuge leg's hollow port and the refuge's fixtures (rails, lights, panel)."""
    passage = material('CrewPassage', (.86, .78, .56)); trunk = material('CrewTrunk', (.74, .66, .48)); bores = ct.bores(s); trims = ct.trims(s)
    for part in ct.stationary(s):
        kind = 'crew_trunk' if part['role'] == 'TRUNK' else 'crew_passage'; mat = trunk if kind == 'crew_trunk' else passage
        obj = hollow(c, s, part, mat, kind, bores[part['name']]) if 'hollow' in part else line(c, part['name'], part['points'], part['radius'], mat, kind=kind)
        if part['name'] in trims:
            obj = cut(obj, trims[part['name']], operation='INTERSECT')
        label(obj, part)
    fixtures(c, s, he.trunk_fixtures(s)+he.refuge_fixtures(s))
    import survival
    survival.refuge(c, s)              # SP-48 / SP-50 / SP-54 envelopes in the refuge's end zones (PROTOTYPE)
    import fitout
    fitout.trunk(c, s)                 # IND-001 3.1: the trunk's fit-out (ARCHITECTURE layer, kind route_fitout)
    # Q46: the spine-port gates (stationary-side closures), saved closed; previews and the route sweep open them in memory.
    gates = [q for j in s['human_entry']['vestibule_rotors'] for q in ct.closures(s, j) if q['kind'] == 'PORT_GATE']
    if gates:
        ctrl = empty(c, 'CREW_PORT_GATE_CTRL', (gates[0]['x0'], 0.0, 0.0), kind='entry_control')
        ctrl['role'] = 'IMPLEMENTATION display control: spine-port gate opening (Q46 stationary-side closure), saved closed (0); previews pose them in memory'
        for q in gates:
            closure(c, s, q, ctrl, f"{q['name']}_open")
    for f in ct.interfaces(s):
        if f['side'] == 'STATIONARY':
            interface(c, f)


def drum(c, s, parent, j):
    """Q46 / MEC-019: rotor j's despun transfer drum (an empty at the rotor centre) and its control TRANSFER_j_CTRL. The drum sits at the
    index angle while drum_sync is 0 (despun under the spine port) and turns with its ring while it is 1 (synchronized, its openings on the
    crew tubes): its driver is the rotor's (components.revision.habitat) scaled by drum_sync, a PROTOTYPE display, not a control law."""
    rot = next(r for r in ri.rotors(s) if r['index'] == j); rc = bpy.data.objects[ri.control(j)]
    ctrl = empty(c, f'TRANSFER_{j}_CTRL', tuple(parent.location), kind='entry_control')
    ctrl['role'] = ('IMPLEMENTATION display control (Q46): drum_sync 0 despun at the index, 1 turning with the ring; door_open_k and hatch_open_k '
                    'open the drum doors and the crew-tube hatches; saved despun and closed (0); previews pose them in memory')
    ctrl['drum_sync'] = 0.0
    obj = empty(c, f'Drum_{j}', tuple(parent.location), ident=f'WF.CREW.{j}.DRUM', kind='transfer_drum')
    obj['function'] = 'DESPUN_TRANSFER_DRUM'; obj['canon_status'] = 'BASELINE'; obj['source_ref'] = 'despun_transfer_vestibule'; obj['geometry_basis'] = DRUM_BASIS
    fc = obj.driver_add('rotation_euler', 0); d = fc.driver
    for name, prop, target in (('spin', 'spin_fraction', rc), ('turned', 'spin_turned', rc), ('integ', 'spin_integrated', rc), ('sync', 'drum_sync', ctrl)):
        var = d.variables.new(); var.name = name; var.type = 'SINGLE_PROP'; var.targets[0].id = target; var.targets[0].data_path = f'["{prop}"]'
    d.expression = f"{rot['phase']!r}+sync*{parent['rpm']*math.tau/60/24!r}*(integ*turned+(1-integ)*spin*(frame-1))"
    if not d.is_simple_expression:
        raise ValueError(f'{obj.name}: driver is not a simple expression')
    return obj, ctrl


def hub(c, s, parent, j):
    """Rotating crew parts of rotor j in its local frame: vestibule, struts, crew tubes and their spoke brackets. HUM-001 zone 3: the human-entry
    vestibule is a pressure shell open toward the spine (outer wall and two end walls), with its fixtures. Zone 4: its crew tubes are hollow
    mitered tubes; each opens the vestibule's outer wall with its clear bore and is trimmed flush to the chamber's inner face. Ring B's tubes
    rise from a bulkhead on a 0.90 m neck (crew_transfer.tube_neck), which opens the wall and is trimmed the same way."""
    vest = material('CrewVestibule', (.80, .70, .46)); passage = material('CrewPassage', (.86, .78, .56)); arms = material('HabitatArms', (.46, .57, .63)); guard = material('SealGuard', (.58, .40, .24))
    v = ct.vestibule(s, j); _, tc = ct.tube_radii(s, j); neck = ct.tube_neck(s, j); tc = neck['clear'] if neck else tc
    body, ctrl = drum(c, s, parent, j) if v['human'] else (parent, None)
    for part in (q for q in ct.rotating(s) if q['rotor'] == j):
        if part.get('hollow') and part['role'] == 'COAST_TUBE':
            la = dict(ct.sectors(s))[part['sector']]; fr = ct.tube_frames_of(s, j, la); vs, fs = tube_mesh(fr, part['radius'], part['hollow'], neck=neck)
            obj = cut(mesh(c, part['name'], vs, fs, passage, kind='crew_passage'), [((v['cu0'], 0.0, 0.0), (v['cu1'], 0.0, 0.0), v['clear'])])
            obj['clear_radius_m'] = part['hollow']
        elif part.get('hollow'):
            L, w, r0, rc, r1 = part['x1']-part['x0'], part['wall'], part['r0'], part['hollow'], part['r1']
            vs, fs = revolve_mesh((part['x0'], 0.0, 0.0), (part['x1'], 0.0, 0.0), [(0.0, r0), (0.0, r1), (L, r1), (L, r0), (L-w, r0), (L-w, rc), (w, rc), (w, r0)])
            obj = mesh(c, part['name'], vs, fs, vest, ident=f'WF.CREW.{j}.VESTIBULE', kind='crew_vestibule'); obj['clear_radius_m'] = rc
            if tc:
                # Each crew tube's (or neck's) clear bore through the outer wall, from below the wall's lowest point across the bore.
                low = math.sqrt(part['hollow']**2-tc**2)-.05
                obj = cut(obj, [(ct.radial(v['hatch_u'], low, a), ct.radial(v['hatch_u'], part['r1']+.05, a), tc) for _, a in ct.sectors(s)])
        elif part['shape'] == 'ring':
            vs, fs = ri.solid(part['x0'], part['x1'], part['r0'], part['r1'], 0.0, math.tau)
            obj = mesh(c, part['name'], vs, fs, guard if part['role'] == 'VESTIBULE_GUARD' else vest, ident=part.get('ident', f'WF.CREW.{j}.VESTIBULE'), kind='crew_vestibule')
        elif part['role'] == 'STRUT':
            obj = line(c, part['name'], part['points'], part['radius'], arms, kind='vestibule_strut')
        elif part['role'] == 'TUBE_BRACKET':
            obj = line(c, part['name'], part['points'], part['radius'], arms, kind='crew_bracket')
        else:
            obj = line(c, part['name'], part['points'], part['radius'], passage, kind='crew_passage')
        obj.parent = body if part.get('drum') else parent; label(obj, part)
        if part.get('drum'):
            obj['engineering_status'] = 'OPEN OD-002/MEC-019: despun transfer drum and its seal/bearing/drive cartridges (guard rings); sizes and sync cycle not designed'
    h = s['human_entry']
    fixtures(c, s, he.vestibule_fixtures(s, j) if j in h['vestibule_rotors'] else [], body)
    fixtures(c, s, he.spoke_fixtures(s, j) if j in h['tube_rotors'] else [], parent)
    import fitout                      # IND-001 3.1 since Q46: the drum's and the tube ends' fit-out (ARCHITECTURE layer, kind route_fitout)
    if j in h['vestibule_rotors']:
        fitout.drum(c, s, j, body)
    if j in h['tube_rotors']:
        fitout.tube_ends(c, s, j, parent)
    if ctrl is not None:
        for q in ct.closures(s, j):
            if q['kind'] != 'PORT_GATE':
                door = q['kind'] == 'DRUM_DOOR'
                closure(c, s, q, ctrl, f"{'door' if door else 'hatch'}_open_{q['sector']}", body if door else parent)
    for f in (f for f in ct.interfaces(s) if f['side'] in ('ROTATING', 'DRUM') and f['rotor'] == j):
        interface(c, f, body if f['side'] == 'DRUM' else parent)
