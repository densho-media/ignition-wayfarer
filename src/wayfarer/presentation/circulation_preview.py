"""CIRC-001 review renders of the continuous ring circulation from the saved ring assets (WF_HABITAT_A / _B), in memory only, nothing saved:

- overview_<R>: the whole ring from the bow, the fill and the outer hoop hidden so the corridors (liners), their portals and doors
  (ochre leaves) and the sectors read as one circuit; an orange 1.75 m figure for scale in each corridor;
- corridor_<R>: eye level (1.6 m) in a corridor of the ring, looking along it toward the spoke-node bulkhead door;
- door_<R>: eye level in the through-passage of the port sector, looking at the side-wall door (its leaf hidden: open), the corridor beyond;
- passage_<R>: eye level at a side-wall door looking back across the sector's through-passage and the aisle.

    /path/to/blender -b --python src/wayfarer/presentation/circulation_preview.py -- --out runs/<stamp>-circulation [--quality draft]
"""
from pathlib import Path
import argparse
import math
import sys
import bpy
from mathutils import Matrix, Vector
ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT/'src/wayfarer'), str(ROOT/'src/wayfarer/build')]
from spec import load
import habitat_ring
import ring_circulation as rc


def look(cam, at, target, up):
    z = (Vector(at)-Vector(target)).normalized(); x = Vector(up).cross(z).normalized(); y = z.cross(x)
    cam.matrix_world = Matrix.Translation(at) @ Matrix((x, y, z)).transposed().to_4x4()


def figure(scene, at, up, name):
    """A 1.75 m capsule figure standing at `at` (vehicle frame) with its head toward `up`."""
    h = 1.75; mesh = bpy.data.meshes.new(name)
    import bmesh
    bm = bmesh.new(); bmesh.ops.create_cone(bm, cap_ends=True, segments=12, radius1=.22, radius2=.22, depth=h-.44); bm.to_mesh(mesh); bm.free()
    obj = bpy.data.objects.new(name, mesh); scene.collection.objects.link(obj)
    mat = bpy.data.materials.new(name+'_Mat'); mat.diffuse_color = (1.0, .45, .08, 1); mesh.materials.append(mat)
    z = Vector(up).normalized(); x = Vector((1, 0, 0)); y = z.cross(x)
    obj.matrix_world = Matrix.Translation(Vector(at)+z*h/2) @ Matrix((x, y, z)).transposed().to_4x4()
    return obj


def render(root=ROOT, out=None, size=1024, quality='draft'):
    s, *_ = load(root); out = out or root/'renders/p1/circulation'; out.mkdir(parents=True, exist_ok=True); done = []
    sec = rc.section(s)
    for j, R in ((1, 'A'), (2, 'B')):
        bpy.ops.wm.open_mainfile(filepath=str(root/'assets/wayfarer/subsystems'/f'WF_HABITAT_{R}.blend'))
        scene = bpy.context.scene; scene.frame_set(1)
        rotor = bpy.data.objects[f'Rotor_{j}']
        # the rotor's index pose (frame 1), in its own frame: ring-local -> world through the rotor's matrix
        M = rotor.matrix_world.copy()
        W = lambda q: M @ Vector(q)
        Wd = lambda d: (M.to_3x3() @ Vector(d)).normalized()
        scene.render.engine = 'BLENDER_WORKBENCH' if quality == 'draft' else 'BLENDER_EEVEE'
        scene.render.resolution_x = size; scene.render.resolution_y = round(size*.66); scene.render.image_settings.file_format = 'PNG'
        sh = scene.display.shading; sh.light = 'STUDIO'; sh.color_type = 'MATERIAL'; sh.show_backface_culling = False
        sh.show_cavity = True; sh.cavity_type = 'WORLD'
        scene.world.color = (.055, .075, .10)
        data = bpy.data.cameras.new('Circ_Camera'); cam = bpy.data.objects.new('Circ_Camera', data); scene.collection.objects.link(cam); scene.camera = cam
        data.clip_start = .05; data.clip_end = 400
        # 1. overview from the bow: hide the fills and the outer hoop so the corridors read
        # (the exterior flank detail packs are linked instances over the fill's faces: hidden with it)
        hidden = [o for o in bpy.data.objects if o.name.startswith((f'Ring_{j}_Fill_', f'Ring_{j}_Hoop_Outer')) or o.get('kind') in ('ring_spoke',)
                  or (o.instance_type == 'COLLECTION' and o.instance_collection is not None and '_EXT_' in o.instance_collection.name)]
        for o in hidden:
            o.hide_render = True
        for f in rc.fills(s, j):
            tm = (f['t0']+f['tn'])/2
            figure(scene, W(rc.radial(sec['u_centre'], sec['floor_r'], tm)), Wd((0.0, -math.cos(tm), -math.sin(tm))), f'Circ_Figure_{f["fill"]}')
        centre = W((0.0, 0.0, 0.0))
        data.type = 'ORTHO'; data.ortho_scale = 96.0
        look(cam, centre+Vector((60.0, 0, 0)), centre, Vector((0, 0, 1)))
        scene.render.filepath = str(out/f'overview_{R}.png'); bpy.ops.render.render(write_still=True); done.append(scene.render.filepath)
        data.type = 'PERSP'
        f = rc.fills(s, j)[0]
        for o in hidden:
            o.hide_render = False
        for o in [o for o in bpy.data.objects if o.name.startswith('Circ_Figure_')]:
            o.hide_render = True
        data.lens = 18
        sh.light = 'FLAT'      # eye level: the whitebox's colours as they are (studio light darkens the curved liner's inward faces)
        # 2. eye level in the first corridor half, toward the node door
        eye = 1.60; up = lambda t: Wd((0.0, -math.cos(t), -math.sin(t)))
        t0 = f['t0']+1.6/sec['floor_r']
        look(cam, W(rc.radial(sec['u_centre'], sec['floor_r']-eye, t0)), W(rc.radial(sec['u_centre'], sec['floor_r']-1.45, t0+7.0/sec['floor_r'])), up(t0))
        scene.render.filepath = str(out/f'corridor_{R}.png'); bpy.ops.render.render(write_still=True); done.append(scene.render.filepath)
        # 3. in the port sector's through-passage, looking at its +z door (leaf hidden: open)
        k = s['human_entry']['vestibule_port_sectors'][j-1]; a = habitat_ring.sector_angles(s)[k-1]; x = sec['u_centre']
        leaves = [o for o in bpy.data.objects if o.name.startswith(f'Ring_{j}_Circ_Door_{R}{k}')]
        for o in leaves:
            o.hide_render = True
        P = lambda q: W(rc.sector_to_ring(s, a, q))
        figure(scene, P((x, 0.0, 2.45)), up(a), 'Circ_Figure_Door')
        look(cam, P((x+.05, -eye, -1.2)), P((x, -1.1, 3.4)), up(a))
        scene.render.filepath = str(out/f'door_{R}.png'); bpy.ops.render.render(write_still=True); done.append(scene.render.filepath)
        # 4. from the -z door, back across the passage and the aisle
        look(cam, P((x, -eye, -2.6)), P((x, -1.2, 1.5)), up(a))
        scene.render.filepath = str(out/f'passage_{R}.png'); bpy.ops.render.render(write_still=True); done.append(scene.render.filepath)
    print('WF_CIRCULATION_RENDERS', len(done), out)
    return done


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--root', type=Path, default=ROOT); p.add_argument('--out', type=Path); p.add_argument('--size', type=int, default=1024)
    p.add_argument('--quality', choices=['draft', 'material'], default='draft')
    a = p.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    render(a.root.resolve(), a.out, a.size, a.quality)
