"""P1-004 interior previews: one ring sector plus one interior component, in the sector frame. Does not save anything.
The pressure envelope and overhead panel are hidden in memory so the blocking reads. With --details, the detail assets anchored on ring A's
sector of that function (docs/MODULES.md) are linked at the sector origin too; the `overhead` view looks up from the deck at the overhead,
which it keeps shown, to review overhead production detail."""
from pathlib import Path
import argparse
import math
import sys
import bpy
from mathutils import Matrix, Vector
ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT/'src/wayfarer'),str(ROOT/'src/wayfarer/build')]
from common import material
from spec import load, derived
import habitat_interior

VIEWS=['plan','section','cutaway','overhead']


def frame(direction, up):
    """Camera rotation looking along direction with image-up toward up."""
    z=-Vector(direction).normalized();x=Vector(up).cross(z).normalized();y=z.cross(x)
    return Matrix((x,y,z)).transposed().to_euler()


def label(scene, camera, lines, field_width, aspect, depth):
    for i,text in enumerate(lines):
        data=bpy.data.curves.new(f'Preview_Label_{i}','FONT');data.body=text;data.size=field_width*(.026 if i==0 else .019)
        data.materials.append(material('Label',(.70,.85,.93),1))
        obj=bpy.data.objects.new(data.name,data);scene.collection.objects.link(obj);obj.parent=camera
        obj.location=(-field_width*.47,field_width/aspect*(.44-i*.05),-depth)


def render(root=ROOT, functions=None, views=None, size=768, out_dir=None, details=False):
    s,*_=load(root);sec=habitat_interior.section(s);fit=habitat_interior.check(s,derived(s))
    assets=root/'assets/wayfarer';out=out_dir or root/'renders/p1/interior';out.mkdir(parents=True,exist_ok=True)
    for function in functions or list(s['interior']['components']):
        component='WF_'+s['interior']['components'][function]
        bpy.ops.wm.read_factory_settings(use_empty=True);scene=bpy.context.scene
        for path,name in [(assets/'components/WF_RING_SECTOR.blend','WF_RING_SECTOR'),(assets/f'components/{component}.blend',component)]:
            with bpy.data.libraries.load(str(path),link=True) as (_,dst):dst.collections=[name]
            inst=bpy.data.objects.new(f'Preview_{name}',None);inst.instance_type='COLLECTION';inst.instance_collection=dst.collections[0];scene.collection.objects.link(inst)
        if details:
            import modules
            anchors=modules.anchors(s)
            for a,t in sorted(modules.assemblies(s['detail_packs']).items()):
                q=anchors[t['anchor']]
                if q['family']=='ring_sector' and q['function']==function and t['anchor'].split('.')[-2]=='1':
                    name=modules.asset_name(a)
                    with bpy.data.libraries.load(str(assets/modules.ASSET_DIR/f'{name}.blend'),link=True) as (_,dst):dst.collections=[name]
                    inst=bpy.data.objects.new(f'Preview_{name}',None);inst.instance_type='COLLECTION';inst.instance_collection=dst.collections[0];scene.collection.objects.link(inst)
        for name in ['Sector_Pressure_Envelope','Interior_Overhead']:bpy.data.objects[name].hide_render=True
        # Orange 1.8 m human in the aisle, standing on the deck (sector +Y is down).
        h=s['prototype']['human_height_m']
        bpy.ops.mesh.primitive_cylinder_add(radius=.22,depth=h,location=(-1.0,sec['deck_y_m']-h/2,0),rotation=(math.pi/2,0,0))
        bpy.context.object.data.materials.append(material('HumanScale',(1.0,.45,.05)))
        scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=16;scene.cycles.use_denoising=True;scene.cycles.seed=0
        scene.render.resolution_x=size;scene.render.resolution_y=round(size*.75);scene.render.image_settings.file_format='PNG'
        scene.world=bpy.data.worlds.new('Preview_World');scene.world.use_nodes=True
        background=next(n for n in scene.world.node_tree.nodes if n.type=='BACKGROUND')
        background.inputs['Color'].default_value=(.055,.075,.10,1);background.inputs['Strength'].default_value=.8
        for i,(direction,energy) in enumerate([((.4,1,.5),3.0),((-.6,.8,-.7),1.6),((.2,-1,.3),.8)]):
            data=bpy.data.lights.new(f'Preview_Sun_{i}','SUN');data.energy=energy;data.angle=.2
            obj=bpy.data.objects.new(data.name,data);scene.collection.objects.link(obj);obj.rotation_euler=frame(direction,(1,0,0))
        cam_data=bpy.data.cameras.new('Preview_Camera');camera=bpy.data.objects.new(cam_data.name,cam_data);scene.collection.objects.link(camera);scene.camera=camera
        aspect=scene.render.resolution_x/scene.render.resolution_y
        for view in views or VIEWS:
            for obj in [o for o in scene.objects if o.name.startswith(('Preview_Label','Preview_Tag'))]:bpy.data.objects.remove(obj,do_unlink=True)
            target=Vector((0,(sec['deck_y_m']+sec['ceiling_y_m'])/2,0))
            if view=='plan':
                direction,up,cam_data.type=(0,1,0),(0,0,1),'ORTHO';cam_data.ortho_scale=9.0   # the 5.9 m wide sector must fit the 3:4 frame's short side
                # Zone names on the block tops, readable from above.
                for b in habitat_interior.zones(s,function):
                    data=bpy.data.curves.new(f'Preview_Tag_{b["name"]}','FONT');data.body=b['name'].replace('_',' ');data.size=.13;data.align_x='CENTER'
                    data.materials.append(material('Tag',(1,1,1),2))
                    obj=bpy.data.objects.new(data.name,data);scene.collection.objects.link(obj)
                    obj.location=((b['min'][0]+b['max'][0])/2,b['min'][1]-.02,(b['min'][2]+b['max'][2])/2);obj.rotation_euler=frame(direction,up)
            elif view=='section':direction,up,cam_data.type=(-1,0,0),(0,-1,0),'ORTHO';cam_data.ortho_scale=7.0
            elif view=='overhead':direction,up,cam_data.type=(.25,-1,.15),(1,0,0),'PERSP';cam_data.lens=18
            else:direction,up,cam_data.type=(-.55,.9,.95),(0,-1,0),'PERSP';cam_data.lens=24
            bpy.data.objects['Interior_Overhead'].hide_render=view!='overhead'
            if view=='overhead':target=Vector((0,sec['ceiling_y_m'],0))   # looking up from about 1 m above the deck
            distance=30 if cam_data.type=='ORTHO' else 2.0 if view=='overhead' else 7.5
            camera.location=target-Vector(direction).normalized()*distance;camera.rotation_euler=frame(direction,up)
            # Plan cuts just below the overhead; section cuts the +X end cap. The cutaway relies on the hidden shell.
            cam_data.clip_start={'plan':distance+sec['ceiling_y_m']-target.y+.02,'section':distance-sec['length_m']/2+.08}.get(view,.1);cam_data.clip_end=200
            # Ortho labels sit just past the clip plane (their size does not depend on depth).
            width=cam_data.ortho_scale if cam_data.type=='ORTHO' else 2*2*math.tan(cam_data.angle_x/2)
            label(scene,camera,[f'WAYFARER 001 / P1 INTERIOR / {function.replace("_"," ")} / {view.upper()}',
                                f'PROTOTYPE blocking, rooms OPEN | {sec["usable_m3"]:.0f} m3 usable of {sec["deck_to_overhead_m3"]:.0f} m3 deck-to-overhead | headroom {sec["headroom_m"]:.2f} m | aisle {s["interior"]["aisle_m"]:g} m',
                                f'coast deck r {fit["coast_gravity"]["deck_radius_m"]:.1f} m ({fit["coast_gravity"]["deck_g"]:.3f} g) | orange human {h:g} m | shell and overhead hidden'],width,aspect,cam_data.clip_start+.05 if cam_data.type=='ORTHO' else 2)
            scene.render.filepath=str(out/f'{component[3:].lower()}_{view}{"_detail" if details else ""}.png')
            bpy.ops.render.render(write_still=True)
            print(f'WF_INTERIOR_PREVIEW {function} {view}',flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=ROOT);p.add_argument('--functions',nargs='+');p.add_argument('--views',nargs='+',choices=VIEWS)
    p.add_argument('--size',type=int,default=768);p.add_argument('--out-dir',type=Path)
    p.add_argument('--details',action='store_true',help="link the detail assets anchored on ring A's sector of each function")
    a=p.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    if a.size<128 or a.size>1024:raise ValueError('Use inexpensive 128–1024 px previews')
    render(a.root.resolve(),a.functions,a.views,a.size,a.out_dir,a.details)
