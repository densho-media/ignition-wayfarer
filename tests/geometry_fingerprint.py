"""Read-only geometry fingerprint of production assets (Blender). Independent of spec, so it runs on stale assets."""
from pathlib import Path
import argparse
import json
import sys
import bpy
ROOT=Path(__file__).resolve().parents[1]


def production(assets):
    return sorted(p for p in assets.rglob('*.blend') if not {'milestones','studies'}&set(p.relative_to(assets).parts))


def record(obj,deps):
    item={'type':obj.type,'kind':obj.get('kind'),'component_id':obj.get('component_id'),
          'parent':obj.parent.name if obj.parent else None,
          'instance':obj.instance_collection.name if obj.instance_collection else None,
          'matrix_world':[list(row) for row in obj.matrix_world]}
    if obj.type in {'MESH','CURVE'}:
        evaluated=obj.evaluated_get(deps);data=evaluated.to_mesh()
        vs=[v.co for v in data.vertices]
        item['vertices']=len(vs);item['faces']=len(data.polygons)
        if vs:
            item['min']=[min(v[i] for v in vs) for i in range(3)];item['max']=[max(v[i] for v in vs) for i in range(3)]
            item['centroid']=[sum(v[i] for v in vs)/len(vs) for i in range(3)]
        evaluated.to_mesh_clear()
    return item


def fingerprint(root=ROOT,only=None):
    """Every production asset, or only the given paths relative to assets/wayfarer (a detail pack's slice, docs/MODULES.md)."""
    assets=root/'assets/wayfarer';result={}
    for path in production(assets):
        if only is not None and str(path.relative_to(assets)) not in only:continue
        bpy.ops.wm.open_mainfile(filepath=str(path))
        scene=bpy.context.scene;scene.frame_set(1);deps=bpy.context.evaluated_depsgraph_get()
        owned=sorted((o for o in bpy.data.objects if o.library is None and o.get('wf_owner')=='wayfarer.p0'),key=lambda o:o.name)
        objects={o.name:record(o,deps) for o in owned}
        for name,item in objects.items():
            if item['kind']=='rotor':
                angles=[]
                for frame in [1,91]:
                    scene.frame_set(frame);angles.append(bpy.data.objects[name].evaluated_get(bpy.context.evaluated_depsgraph_get()).rotation_euler.x)
                item['rotation_x_frames_1_91']=angles
        scene.frame_set(1)
        result[str(path.relative_to(assets))]={'objects':objects,'direct_links':sorted(l.filepath for l in bpy.data.libraries if l.parent is None)}
        # Hand-authored detail adopted into a detail asset (docs/MODULES.md): listed so a diff shows it, but outside 'objects', so the
        # canonical comparison and the accepted baselines stay machine-independent (authored .blend files are local).
        authored={o.name:record(o,deps) for o in sorted((o for o in bpy.data.objects if o.library is None and o.get('wf_adopted')),key=lambda o:o.name)}
        if authored:result[str(path.relative_to(assets))]['authored']=authored
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=ROOT);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--only',nargs='+',help='asset paths relative to assets/wayfarer')
    a=p.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    data=fingerprint(a.root.resolve(),set(a.only) if a.only else None)
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(data,indent=1,sort_keys=True)+'\n')
    print('WF_FINGERPRINT',len(data),'assets',sum(len(v['objects']) for v in data.values()),'objects',flush=True)
