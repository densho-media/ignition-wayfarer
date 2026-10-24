"""Before/after equivalence of the production detail for a detail migration (docs/MODULES.md), Blender.

Opens the saved vehicle and records every production_detail object as the vehicle evaluates it: its world-space evaluated vertices
(digested at 1e-5 m, modifiers applied) under the poses that move or open things near the detail, its custom properties, materials and
modifiers, and the file it is saved in. Poses: saved; COAST with the rings turned; the same with the despun drums turning with their rings
(drum_sync 1); HIGH_POWER (rings stopped at their index angles); DOCKED with the primary port's leaves, the drum doors, the crew-tube hatches
and the spine-port gates open; the Crown stowed, prepared and engaged at two azimuths. Comparing two records (plain python3 with --compare)
proves a migration moved files and parents without moving, reshaping, retagging or rebinding anything: only the saved-in file, the
detail-pack labels it adds and the lineage may differ.

--habitat records instead everything the vehicle evaluates under Assembly_HABITAT (rings, hubs, crew route, sectors, interiors and the
detail on them: meshes, curves and text as world-space vertex digests, empties as world matrices) and the saved objects of the habitat
files, for an engineering-asset split (docs/MODULES.md, phase 3).

    blender -b --factory-startup --python tests/detail_equivalence.py -- --root . --out before.json [--habitat]
    python3 tests/detail_equivalence.py --compare before.json after.json
"""
from pathlib import Path
import argparse
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
# Labels a migration adds to an object (production.build: a pack's assembly carries its pack, class and module).
ADDED_KEYS = {'detail_pack', 'detail_class', 'module'}


def digest(values):
    return hashlib.sha256(json.dumps(values, separators=(',', ':')).encode()).hexdigest()[:16]


GEOMETRY = {'MESH', 'CURVE', 'FONT'}
HABITAT_FILES = ('WF_HABITAT', 'WF_RING_SECTOR', 'WF_INTERIOR_', 'WF_DETAIL_')


def record(root, habitat=False):
    import bpy
    sys.path[:0] = [str(root/'src/wayfarer'), str(root/'src/wayfarer/build')]
    from spec import load
    from common import pose_configuration, pose_transfer, pose_forward_state
    import human_entry
    import rotor_interface
    s = load(root)[0]
    bpy.ops.wm.open_mainfile(filepath=str(root/'assets/wayfarer'/(s['vehicle']['asset']+'.blend')))
    scene = bpy.context.scene

    def sample():
        scene.frame_set(1); deps = bpy.context.evaluated_depsgraph_get(); out = {}
        for inst in deps.object_instances:
            obj = inst.object
            if habitat:
                if not (inst.parent and inst.parent.original.name == 'Assembly_HABITAT'):
                    continue
                if obj.type == 'EMPTY':
                    out.setdefault(obj.original.name, []).append(digest([round(c, 5)+0.0 for row in inst.matrix_world for c in row]))
                    continue
                if obj.type not in GEOMETRY:
                    continue
            elif obj.type != 'MESH' or obj.original.get('kind') != 'production_detail':
                continue
            me = obj.to_mesh(); m = inst.matrix_world
            vs = [[round(c, 5)+0.0 for c in m@v.co] for v in me.vertices]; nf = len(me.polygons); obj.to_mesh_clear()
            out.setdefault(obj.original.name, []).append(digest([vs, nf]))
        return {k: sorted(v) for k, v in sorted(out.items())}

    def rotors(turned=0.0, sync=None):
        for rot in rotor_interface.rotors(s):
            c = bpy.data.objects[rotor_interface.control(rot['index'])]
            c['spin_integrated'], c['spin_turned'] = (1.0, turned) if turned else (0.0, 0.0); c.update_tag()
            bpy.data.objects[f"Rotor_{rot['index']}"].update_tag()
            drum = bpy.data.objects.get(f"Drum_{rot['index']}")
            if drum is not None:
                drum.update_tag()
        if sync is not None:
            pose_transfer(s, 0.0, sync)

    def docked_open():
        pose_configuration(s, 'DOCKED')
        control = bpy.data.objects['DOCK_ENTRY_CTRL']; port = human_entry.ports(s)[0]
        for which in ('outer', 'inner'):
            control[f"{port['name']}_{which}_open"] = 1.0
        control.update_tag()
        for obj in bpy.data.objects:
            if obj.name.endswith('_Hatch_Hinge'):
                obj.update_tag()
        pose_transfer(s, 1.0)

    poses = {}
    poses['saved'] = sample()
    pose_configuration(s, 'COAST'); rotors(37.0); poses['coast_turned'] = sample()
    rotors(37.0, 1.0); poses['coast_turned_drum_sync'] = sample()
    rotors(0.0, 0.0); pose_configuration(s, 'HIGH_POWER'); poses['high_power'] = sample()
    docked_open(); poses['docked_open'] = sample()
    pose_transfer(s, 0.0, 0.0); pose_configuration(s, 'COAST')
    for name, values in (('crown_prepared', dict(crown_prepare=1.0, crown_azimuth=0.0)),
                         ('crown_engaged_0', dict(crown_prepare=1.0, crown_engage=1.0, crown_azimuth=0.0)),
                         ('crown_engaged_137', dict(crown_prepare=1.0, crown_engage=1.0, crown_azimuth=137/360))):
        pose_forward_state(values); poses[name] = sample()
    pose_forward_state(dict(crown_prepare=0.0, crown_engage=0.0, crown_azimuth=0.0))

    objects = {}
    for obj in bpy.data.objects:
        if habitat:
            if not (obj.library and Path(obj.library.filepath).name.startswith(HABITAT_FILES)):
                continue
        elif obj.type != 'MESH' or obj.get('kind') != 'production_detail':
            continue
        props = {k: (v if isinstance(v, (int, float, str, bool)) else str(list(v)) if hasattr(v, '__len__') else str(v)) for k, v in obj.items()}
        mats = []
        for slot in obj.material_slots:
            m = slot.material; node = next((n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None) if m and m.node_tree else None
            mats.append([m.name if m else None, None if node is None else
                         [round(x, 6) for x in [*node.inputs['Base Color'].default_value, node.inputs['Roughness'].default_value,
                                                 node.inputs['Metallic'].default_value]]])
        mesh = digest([[round(c, 6) for c in v.co] for v in obj.data.vertices]) if obj.type == 'MESH' else None
        mods = [[md.type, md.name, *([round(md.width, 6), md.segments, md.limit_method, round(md.angle_limit, 6)] if md.type == 'BEVEL' else [])]
                for md in obj.modifiers]
        objects[obj.name] = dict(file=Path(obj.library.filepath).name if obj.library else None, parent=obj.parent.name if obj.parent else None,
                                 props=props, materials=mats, modifiers=mods, mesh=mesh)
    return dict(poses=poses, objects=dict(sorted(objects.items())))


def compare(a, b):
    """Differences that a migration must not make; the saved-in file and parent of an object may change (reported, not failed)."""
    fails, moved = [], {}
    for pose in sorted(set(a['poses'])|set(b['poses'])):
        pa, pb = a['poses'].get(pose, {}), b['poses'].get(pose, {})
        for n in sorted(set(pa)|set(pb)):
            if pa.get(n) != pb.get(n):
                fails.append(f'{pose}: {n} evaluated geometry differs')
    for n in sorted(set(a['objects'])|set(b['objects'])):
        x, y = a['objects'].get(n), b['objects'].get(n)
        if x is None or y is None:
            fails.append(f'{n}: only {"after" if x is None else "before"}'); continue
        for k in ('materials', 'modifiers', 'mesh'):
            if x[k] != y[k]:
                fails.append(f'{n}: {k} differ')
        px = {k: v for k, v in x['props'].items() if k not in ADDED_KEYS}; py = {k: v for k, v in y['props'].items() if k not in ADDED_KEYS}
        for k in sorted(set(px)|set(py)):
            if px.get(k) != py.get(k):
                fails.append(f'{n}: property {k} {px.get(k)!r} -> {py.get(k)!r}')
        if (x['file'], x['parent']) != (y['file'], y['parent']):
            moved[n] = dict(before=[x['file'], x['parent']], after=[y['file'], y['parent']])
    return dict(result='FAIL' if fails else 'PASS', fails=fails, moved=moved,
                poses=sorted(a['poses']), objects=len(b['objects']))


if __name__ == '__main__':
    argv = sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else sys.argv[1:]
    p = argparse.ArgumentParser(); p.add_argument('--root', type=Path, default=ROOT); p.add_argument('--out', type=Path)
    p.add_argument('--compare', nargs=2, type=Path)
    p.add_argument('--habitat', action='store_true')
    a = p.parse_args(argv)
    if a.compare:
        r = compare(*(json.loads(x.read_text()) for x in a.compare))
        print(json.dumps(r, indent=1)); sys.exit(r['result'] != 'PASS')
    data = record(a.root.resolve(), a.habitat)
    a.out.write_text(json.dumps(data, indent=1, sort_keys=True)+'\n')
    print('WF_DETAIL_EQUIVALENCE', len(data['objects']), 'objects', {k: len(v) for k, v in data['poses'].items()}, flush=True)
