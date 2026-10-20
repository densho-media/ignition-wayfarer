"""IND-001 route fit-out recipe (ARCHITECTURE layer): the [route_fitout] elements of route_fitout as meshes in the SERVICE subsystem, next
to the entry they furnish (GEN collections cannot nest, so they share GEN_WF_SERVICE and carry layer = ARCHITECTURE and kind = route_fitout).
Placard text is converted to meshes. IND-001 3.1 adds the trunk (built with WF_CREW_TRANSFER), the shared sector landing (with
WF_RING_SECTOR), each function's sector placard (with its interior), and since Q46 each despun drum (parented to Drum_j) and both ends of
every crew tube (parented to Rotor_j), built with the rotor's crew parts; 3.2 the picked sector fit-out and Seraph's post (with the interior). The palette is a PROTOTYPE depiction choice of the picked study scheme D: greys for structure, blue for
wayfinding, orange for safety, line colours only in the service chase.
"""
import math
import bpy
from mathutils import Matrix, Vector
from common import line, material, mesh, revolve_mesh, tag
import human_entry as he
import route_fitout as rf

PALETTE = dict(crop=(.30, .62, .28), tray=(.74, .76, .72), frame=(.20, .21, .23), band=(.07, .16, .42), grille=(.12, .12, .13), placard=(.93, .94, .95), text=(.06, .14, .40),
               bezel=(.70, .73, .77), handle=(.90, .38, .07), cover=(.34, .36, .38), locker=(.90, .90, .88), safety=(.92, .40, .08),
               chase=(.07, .07, .08), tag=(.85, .66, .18), pipe_air=(.55, .70, .85), pipe_water=(.20, .40, .66), pipe_power=(.85, .52, .12),
               bottle_o2=(.90, .90, .90), extinguisher=(.70, .08, .06))
SHELL = (.62, .64, .66)
BOX_FACES = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]


def arc_mesh(f, q, n=6):
    """Curved wall element: a0..a1 along the port axis, rho0..rho1, phi0..phi1 (deg), as a closed box bent round the axis."""
    (a0, a1), (r0, r1), (p0, p1) = q['a'], q['rho'], q['phi']; k = max(n, int(abs(p1-p0)/3)+1)
    ring = [(a, r, math.radians(p0+(p1-p0)*j/k)) for j in range(k+1) for a, r in ((a0, r0), (a1, r0), (a1, r1), (a0, r1))]
    vs = [he.world(f, a, r, ph) for a, r, ph in ring]
    fs = [(4*j+i, 4*j+(i+1) % 4, 4*(j+1)+(i+1) % 4, 4*(j+1)+i) for j in range(k) for i in range(4)]+[(3, 2, 1, 0), (4*k, 4*k+1, 4*k+2, 4*k+3)]
    return vs, fs


def text_matrix(f, q):
    """World matrix and size of a placard's text: on the visible face, upright with ship +X (fore) up. A wall placard faces the axis, a
    bulkhead placard faces along the passage."""
    centre, (u, t, r) = he.box_frame(f, q); size = q['size']
    facing = q.get('facing', 'axis'); normal = {'axis': -Vector(r), 'outboard': Vector(u), 'inboard': -Vector(u)}[facing]
    depth = size[2] if facing == 'axis' else size[0]; w, h = (size[1], size[0]) if facing == 'axis' else (size[1], size[2])
    up = Vector((1.0, 0.0, 0.0)); up = up-normal*up.dot(normal); up = up.normalized() if up.length > .2 else Vector(u)
    lines = q['text'].split('\n'); letter = min(w/(.62*max(len(x) for x in lines)), h/(1.35*len(lines)))
    m = Matrix.Translation(Vector(centre)+normal*(depth/2+.002))@Matrix((up.cross(normal).normalized(), up, normal)).transposed().to_4x4()
    return m, letter


def text_mesh(c, f, q, mat):
    """Placard text as a mesh object (the runtime export takes meshes, not font curves)."""
    m, letter = text_matrix(f, q); data = bpy.data.curves.new(q['name']+'_Text', 'FONT')
    data.body = q['text']; data.align_x = 'CENTER'; data.align_y = 'CENTER'; data.size = letter
    tmp = bpy.data.objects.new(data.name, data); c.objects.link(tmp); tmp.matrix_world = m
    me = bpy.data.meshes.new_from_object(tmp.evaluated_get(bpy.context.evaluated_depsgraph_get()))
    bpy.data.objects.remove(tmp, do_unlink=True); bpy.data.curves.remove(data)
    me.name = q['name']+'_Text_Mesh'; me.materials.append(mat)
    obj = bpy.data.objects.new(q['name']+'_Text', me); c.objects.link(obj); obj.matrix_world = m
    return tag(obj, obj.name, 'route_fitout')


def xarc_mesh(q, n=6):
    """Curved trunk-wall element about the ship axis: x0..x1, rho0..rho1, phi0..phi1 (deg)."""
    (x0, x1), (r0, r1), (p0, p1) = q['x'], q['rho'], q['phi']; k = max(n, int(abs(p1-p0)/3)+1)
    vs = [(x, r*math.cos(a), r*math.sin(a)) for j in range(k+1) for a in [math.radians(p0+(p1-p0)*j/k)] for x, r in ((x0, r0), (x1, r0), (x1, r1), (x0, r1))]
    fs = [(4*j+i, 4*j+(i+1) % 4, 4*(j+1)+(i+1) % 4, 4*(j+1)+i) for j in range(k) for i in range(4)]+[(3, 2, 1, 0), (4*k, 4*k+1, 4*k+2, 4*k+3)]
    return vs, fs


wbox_corners = rf.wbox_corners


def wbox_text(c, q, mat):
    """A 'wbox' placard's text on its face (third axis), upright along its second axis, as a mesh object."""
    ax = [Vector(a) for a in q['axes']]; w, h, d = q['size']; lines = q['text'].split('\n')
    letter = min(w/(.62*max(len(x) for x in lines)), h/(1.35*len(lines)))
    right = ax[1].cross(ax[2])                                  # reads left to right for a viewer facing the face
    m = Matrix.Translation(Vector(q['centre'])+ax[2]*(d/2+.002))@Matrix((right, ax[1], ax[2])).transposed().to_4x4()
    data = bpy.data.curves.new(q['name']+'_Text', 'FONT'); data.body = q['text']; data.align_x = 'CENTER'; data.align_y = 'CENTER'; data.size = letter
    tmp = bpy.data.objects.new(data.name, data); c.objects.link(tmp); tmp.matrix_world = m
    me = bpy.data.meshes.new_from_object(tmp.evaluated_get(bpy.context.evaluated_depsgraph_get()))
    bpy.data.objects.remove(tmp, do_unlink=True); bpy.data.curves.remove(data)
    me.name = q['name']+'_Text_Mesh'; me.materials.append(mat)
    obj = bpy.data.objects.new(q['name']+'_Text', me); c.objects.link(obj); obj.matrix_world = m
    return tag(obj, obj.name, 'route_fitout')


def tarc_mesh(q, n=6):
    """Curved tube-wall element about a tube segment's axis: origin + d t (t0..t1), rho0..rho1, phi0..phi1 (deg) from n1 toward n2."""
    (t0, t1), (r0, r1), (p0, p1) = q['t'], q['rho'], q['phi']; k = max(n, int(abs(p1-p0)/3)+1); o, d, n1, n2 = q['origin'], q['d'], q['n1'], q['n2']
    at = lambda t, r, a: tuple(o[i]+d[i]*t+r*(math.cos(a)*n1[i]+math.sin(a)*n2[i]) for i in range(3))
    vs = [at(t, r, math.radians(p0+(p1-p0)*j/k)) for j in range(k+1) for t, r in ((t0, r0), (t1, r0), (t1, r1), (t0, r1))]
    fs = [(4*j+i, 4*j+(i+1) % 4, 4*(j+1)+(i+1) % 4, 4*(j+1)+i) for j in range(k) for i in range(4)]+[(3, 2, 1, 0), (4*k, 4*k+1, 4*k+2, 4*k+3)]
    return vs, fs


def build(c, els, palette=None, parent=None):
    """3.1 elements ('xarc', 'tarc', 'wbox', 'ring' about base->tip, 'rod') in the frame of the collection they are built in, or of parent."""
    pal = palette or PALETTE; mats = {k: material(f'Fit_{k}', v) for k, v in pal.items()}; made = []
    for q in els:
        mat = mats.get(q['paint'], mats['frame'])
        if q['shape'] == 'xarc':
            obj = mesh(c, q['name'], *xarc_mesh(q), mat, kind='route_fitout')
        elif q['shape'] == 'tarc':
            obj = mesh(c, q['name'], *tarc_mesh(q), mat, kind='route_fitout')
        elif q['shape'] == 'wbox':
            obj = mesh(c, q['name'], wbox_corners(q), BOX_FACES, mat, kind='route_fitout')
        elif q['shape'] == 'ring':
            obj = mesh(c, q['name'], *revolve_mesh(q['base'], q['tip'], q['profile']), mat, kind='route_fitout')
        else:
            obj = line(c, q['name'], q['points'], q['radius'], mat, kind='route_fitout')
        objs = [obj]+([wbox_text(c, q, mats['text'])] if q.get('text') else [])
        for o in objs:
            for key in ('layer', 'grammar', 'function', 'design_class', 'signage'):
                o[key] = q[key]
            o['evidence_ref'] = 'cultural_architecture'
            o['geometry_basis'] = 'PROTOTYPE [route_fitout] (IND-001 3.1, 3.2): depiction and fit-out only; no pressure, interface or clearance change'
            if parent is not None:
                o.parent = parent
        made += objs
    return made


def trunk(c, s):
    return build(c, rf.trunk_elements(s))


def landing(c, s):
    return build(c, rf.landing_elements(s))


def drum(c, s, j, parent):
    return build(c, rf.drum_elements(s, j), parent=parent)


def tube_ends(c, s, j, parent):
    return build(c, rf.tube_end_elements(s, j), parent=parent)


def sector_sign(c, s, function):
    return build(c, rf.sector_sign(s, function))


def sector(c, s, function):
    """3.2: the function's sector fit-out (scheme A) and Seraph's space where it has one (Q51: the post and the niche). Q50: the Garden
    expansion elements are built hidden; GARDEN_EXPANSION_CTRL['expansion'] (0 saved, 1 shown) drives their visibility, display only."""
    els = rf.sector_elements(s, function); made = build(c, els)
    by = {o.name: o for o in made}
    for q in els:
        if 'sp' in q:                  # SP-46..54 envelopes: their SP, source and installed volume
            for name in (q['name'], q['name']+'_Text'):
                if name in by:
                    by[name]['sp'] = q['sp']; by[name]['source_ref'] = q['source_ref']; by[name]['volume_m3'] = q['volume_m3']
    later = {q['name'] for q in els if q.get('state') == rf.GARDEN_EXPANSION}
    if later:
        ctrl = bpy.data.objects.new('GARDEN_EXPANSION_CTRL', None); c.objects.link(ctrl); tag(ctrl, ctrl.name, 'interior_control')
        ctrl['expansion'] = 0.0; ctrl['owner_status'] = 'Q50 ACCEPTED (15!A105): optional later Garden expansion into spare lab space; display only, no credited area'
        for o in made:
            if o.name in later:
                o['state'] = rf.GARDEN_EXPANSION; o['owner_status'] = ctrl['owner_status']
                for path in ('hide_render', 'hide_viewport'):
                    fc = o.driver_add(path); fc.driver.type = 'SCRIPTED'; v = fc.driver.variables.new(); v.name = 'expansion'; v.type = 'SINGLE_PROP'
                    v.targets[0].id_type = 'OBJECT'; v.targets[0].id = ctrl; v.targets[0].data_path = '["expansion"]'; fc.driver.expression = 'expansion < 0.5'
                o.hide_viewport = o.hide_render = True
    seraph = build(c, rf.seraph_elements(s, function)[0])
    for o in seraph:
        o['sp'] = 'SP-31'; o['owner_status'] = 'Q51 ACCEPTED (15!A106, 12!A29): post and private niche, no human berth; footprint, posture, charging and service OPEN (12A I34)'
    return made+seraph


def fitout(c, s, f, scheme=None, palette=None):
    """Builds the fit-out of port f; scheme/palette default to [route_fitout] and PALETTE (studies pass their variants)."""
    pal = palette or PALETTE; mats = {k: material(f'Fit_{k}', v) for k, v in pal.items()}; made = []
    for q in rf.elements(s, f, scheme):
        mat = mats.get(q['paint'], mats['frame'])
        if q['shape'] == 'arc':
            obj = mesh(c, q['name'], *arc_mesh(f, q), mat, kind='route_fitout')
        elif q['shape'] == 'box':
            obj = mesh(c, q['name'], he.box_corners(f, q), BOX_FACES, mat, kind='route_fitout')
        elif q['shape'] == 'ring':
            u, _ = he.axes(f); base = he.world(f, 0.0)
            obj = mesh(c, q['name'], *revolve_mesh(base, tuple(base[i]+u[i] for i in range(3)), q['profile']), mat, kind='route_fitout')
        else:
            obj = line(c, q['name'], q['points'] if q['shape'] == 'rod' else [q['a'], q['b']], q['radius'], mat, kind='route_fitout')
        made.append(obj)
        if q.get('text'):
            made.append(text_mesh(c, f, q, mats['text']))
        for o in made[-2:] if q.get('text') else made[-1:]:
            for key in ('layer', 'grammar', 'function', 'design_class', 'signage'):
                o[key] = q[key]
            o['evidence_ref'] = 'cultural_architecture'
            o['geometry_basis'] = 'PROTOTYPE [route_fitout] (IND-001): depiction and fit-out only; no pressure, interface or clearance change'
    return made
