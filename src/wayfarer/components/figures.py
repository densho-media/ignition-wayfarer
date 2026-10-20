"""IND-001 character recipe (CHARACTER layer): the [characters] figures posed for the S004A greeting and its two cameras, and the
newcomer on the treatment couch at the S004B stop in ring A (characters.couch), built into their own asset (assets/characters/<[characters].asset>.blend), never into the vehicle. Mesh builders for characters.parts() shapes; the palette is
a PROTOTYPE depiction choice (Fashion Bible 08 Spacer, 03 Great Union; harness in safety orange).
"""
import math
import bpy
from mathutils import Matrix, Vector
from common import OWNER, tag
import characters as ch
import human_entry as he

PALETTE = dict(suit=(.085, .095, .12), suit_gu=(.085, .095, .12), issued=(.50, .52, .55), over=(.05, .11, .30), skin=(.58, .47, .40),
               glove=(.05, .05, .06), boot=(.07, .07, .08), collar=(.62, .65, .70), metal=(.75, .77, .80), strap=(.90, .38, .07),
               pouch=(.18, .19, .21), device=(.12, .13, .15), mark=(.88, .90, .93), seam=(.32, .34, .37), helmet=(.82, .83, .85),
               visitor=(.95, .66, .08), pack=(.28, .30, .32))


def mat(key):
    name = f'WF_MAT_Char_{key}'; m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    c = PALETTE[key]; m.diffuse_color = (*c, 1); m.use_nodes = True
    node = next(n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'); node.inputs['Base Color'].default_value = (*c, 1)
    node.inputs['Roughness'].default_value = .5 if key not in ('collar', 'metal', 'helmet') else .3
    return m


def mesh(c, name, vs, fs, key, smooth=True):
    data = bpy.data.meshes.new(name); data.from_pydata([tuple(v) for v in vs], [], fs); data.update()
    if smooth:
        data.shade_smooth()
    obj = bpy.data.objects.new(name, data); c.objects.link(obj); data.materials.append(mat(key)); return obj


def basis(e):
    e = Vector(e).normalized(); ref = Vector((1, 0, 0)) if abs(e.x) < .9 else Vector((0, 1, 0))
    n1 = (ref-e*ref.dot(e)).normalized(); return e, n1, e.cross(n1)


def ellipsoid(q, nu=24, nv=14):
    c = Vector(q['centre']); A = [Vector(x)*r for x, r in zip(q['axes'], q['radii'])]
    vs = [c-A[2]]+[c+A[0]*math.cos(t)*math.sin(p)+A[1]*math.sin(t)*math.sin(p)-A[2]*math.cos(p)
                   for p in (math.pi*i/nv for i in range(1, nv)) for t in (2*math.pi*k/nu for k in range(nu))]+[c+A[2]]
    fs = [(0, 1+(k+1) % nu, 1+k) for k in range(nu)]
    fs += [(1+i*nu+k, 1+i*nu+(k+1) % nu, 1+(i+1)*nu+(k+1) % nu, 1+(i+1)*nu+k) for i in range(nv-2) for k in range(nu)]
    top = len(vs)-1; fs += [(top, 1+(nv-2)*nu+k, 1+(nv-2)*nu+(k+1) % nu) for k in range(nu)]
    return vs, fs


def capsule(q, nu=20, nc=5):
    a, b = Vector(q['a']), Vector(q['b']); e, n1, n2 = basis(b-a)
    rings = [(a-e*q['r0']*math.cos(math.pi/2*i/nc), q['r0']*math.sin(math.pi/2*i/nc)) for i in range(1, nc+1)]
    rings += [(b+e*q['r1']*math.sin(math.pi/2*i/nc), q['r1']*math.cos(math.pi/2*i/nc)) for i in range(0, nc)]
    vs = [a-e*q['r0']]+[c+(n1*math.cos(2*math.pi*k/nu)+n2*math.sin(2*math.pi*k/nu))*r for c, r in rings for k in range(nu)]+[b+e*q['r1']]
    m = len(rings); fs = [(0, 1+(k+1) % nu, 1+k) for k in range(nu)]
    fs += [(1+i*nu+k, 1+i*nu+(k+1) % nu, 1+(i+1)*nu+(k+1) % nu, 1+(i+1)*nu+k) for i in range(m-1) for k in range(nu)]
    top = len(vs)-1; fs += [(top, 1+(m-1)*nu+k, 1+(m-1)*nu+(k+1) % nu) for k in range(nu)]
    return vs, fs


def torus(q, nu=32, nv=10):
    c = Vector(q['centre']); e, n1, n2 = basis(q['axis'])
    vs = [c+(n1*math.cos(2*math.pi*i/nu)+n2*math.sin(2*math.pi*i/nu))*(q['R']+q['r']*math.cos(2*math.pi*j/nv))+e*q['r']*math.sin(2*math.pi*j/nv)
          for i in range(nu) for j in range(nv)]
    return vs, [(i*nv+j, i*nv+(j+1) % nv, ((i+1) % nu)*nv+(j+1) % nv, ((i+1) % nu)*nv+j) for i in range(nu) for j in range(nv)]


def loft(q, nu=28, e=2.6):
    """Capped loft through superelliptic rings (exponent e: rounder than a box, flatter than an ellipse)."""
    sg = lambda x: math.copysign(abs(x)**(2/e), x)
    ring = lambda c, x, y, rx, ry: [Vector(c)+Vector(x)*rx*sg(math.cos(2*math.pi*k/nu))+Vector(y)*ry*sg(math.sin(2*math.pi*k/nu)) for k in range(nu)]
    vs = []; rs = q['rings']
    for c, x, y, rx, ry in rs:
        vs += ring(c, x, y, rx, ry)
    m = len(rs); fs = [(i*nu+k, i*nu+(k+1) % nu, (i+1)*nu+(k+1) % nu, (i+1)*nu+k) for i in range(m-1) for k in range(nu)]
    vs.append(Vector(rs[0][0])); vs.append(Vector(rs[-1][0])); b0, b1 = len(vs)-2, len(vs)-1
    fs += [(b0, (k+1) % nu, k) for k in range(nu)]+[(b1, (m-1)*nu+k, (m-1)*nu+(k+1) % nu) for k in range(nu)]
    return vs, fs


def box(q):
    c = Vector(q['centre']); A = [Vector(x)*h for x, h in zip(q['axes'], q['half'])]
    vs = [c+A[0]*x+A[1]*y+A[2]*z for x in (-1, 1) for y in (-1, 1) for z in (-1, 1)]
    return vs, [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]


def build(c, prefix, parts, tagged=False):
    made = []
    for q in parts:
        vs, fs = {'ellipsoid': ellipsoid, 'capsule': capsule, 'torus': torus, 'box': box, 'loft': loft}[q['shape']](q)
        obj = mesh(c, f"{prefix}_{q['name']}", vs, fs, q['paint'], smooth=q['shape'] != 'box')
        obj['layer'] = 'CHARACTER'; obj['part_layer'] = q['layer']; obj['job'] = q['job']; obj['geometry_status'] = 'PROTOTYPE'
        if tagged:
            tag(obj, obj.name, 'character', source='prototype'); obj['evidence_ref'] = 'spacer_fashion'; m = obj.active_material
            m['wf_owner'] = OWNER
        made.append(obj)
    return made


def look(obj, eye, target, up):
    z = (Vector(eye)-Vector(target)).normalized(); x = Vector(up).cross(z).normalized(); y = z.cross(x)
    obj.matrix_world = Matrix.Translation(Vector(eye))@Matrix((x, y, z)).transposed().to_4x4()



def sector_matrix(s, function):
    """The shared sector frame -> vehicle frame of the induction ring's sector with this function, at the docked pose."""
    import crew_transfer
    k = s['habitat_ring']['sector_functions'].index(function)+1; rot, _, la = he.vestibule_station(s, s['induction']['ring'])
    p = lambda v: Vector(he.at_index(rot, crew_transfer.sector_point(s, la[k], v)))
    o = p((0, 0, 0)); m = Matrix.Identity(4)
    for i, e in enumerate(((1, 0, 0), (0, 1, 0), (0, 0, 1))):
        m.col[i][:3] = p(e)-o
    m.col[3][:3] = o
    return m


def couch(c, s):
    """3.3: the newcomer on the treatment couch (S004B), named S004B_Newcomer_<part>, in the vehicle frame at the docked pose."""
    q = ch.couch(s); fig = ch.figure(s, 'newcomer'); m = sector_matrix(s, q['function'])
    made = build(c, f"{q['scene']}_Newcomer", ch.parts(fig, ch.skeleton(fig, q['pose'], q['root'], q['up'], q['forward'], q['hands'], q['feet'])), True)
    for o in made:
        o.matrix_world = m@o.matrix_world; o['scene'] = q['scene']; o['sector_function'] = q['function']; o['identity_status'] = 'OPEN Q49: face, body, identity'
    return made


def characters(c, s):
    """The instructor and the newcomer posed for the greeting, the greeting cameras, and the newcomer on the couch."""
    f = he.ports(s)[0]; g = ch.greeting(s, f)
    ip, ij = ch.staged(g['instructor'], ch.figure(s, 'instructor')); np_, nj = ch.staged(g['newcomer'], ch.figure(s, 'newcomer'))
    made = build(c, 'Instructor', ip, True)+build(c, 'Newcomer', np_, True)
    for o in made:
        o['scene'] = 'S004A'
        if o.name.startswith('Newcomer_') and not any(k in o.name for k in ch.OWN_VIEW):
            o['pov_hidden'] = True
    for q in ch.cameras(s, f, ij, nj):
        data = bpy.data.cameras.new(q['name']); data.lens = q['lens']; data.clip_start = .05
        cam = bpy.data.objects.new(q['name'], data); c.objects.link(cam); tag(cam, q['name'], 'camera', source='prototype')
        look(cam, q['at'], tuple(q['at'][i]+q['look'][i] for i in range(3)), q['up']); cam['role'] = q['role']
    return made+couch(c, s)
