"""Cheap whole-ship previews plus a body detail view. Does not save the scene.

Quality (--quality): draft (the default) renders every view in Workbench (studio light, material colours: form and fit, no emission or shadows);
material renders Eevee for quick material previews (GPU rasterization, no baked indirect light);
review renders Cycles at 16 samples for material, emission and display review, with the section views in Workbench;
look renders Cycles at 64 samples for an explicit look review. The section views stay Workbench in every mode (their cut shells read
only there). Without --views the standalone default is DEFAULT_VIEWS; `--views all` renders every view."""
from pathlib import Path
import argparse
import itertools
import math
import sys
import bpy
from mathutils import Vector, Quaternion, Matrix
ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT/'src/wayfarer'),str(ROOT/'src/wayfarer/build')]
from common import material, pose_configuration, pose_forward_state, pose_radiator_state, pose_timeline
from spec import load, derived, display_poses
import drive_manifold
import forward_shield
import habitat_ring
import hull_geometry
import layout
import power_storage
import radiator_health
import flight_timeline
import thermal_geometry


def bounds():
    points=[]
    for item in bpy.context.evaluated_depsgraph_get().object_instances:
        obj=item.object
        if obj.type in {'MESH','CURVE'} and obj.get('kind')!='scale_reference':
            points.extend(item.matrix_world@Vector(p) for p in obj.bound_box)
    low=Vector(tuple(min(p[i] for p in points) for i in range(3)))
    high=Vector(tuple(max(p[i] for p in points) for i in range(3)))
    return low,high


BLADE_VIEWS=('root_detail','joint_detail')
SECTION_VIEWS=('hub_section_detail','refuge_section_detail')     # camera-clipped axial cuts (near half removed in memory only)
COLLAR_STEP_M=2.0    # display-wire spacing of the collar radius loft in sector_keel_detail (IMPLEMENTATION)
TILT_DEG=15.0     # PROTOTYPE camera tilt, aft and outboard of the blade-plane normal
DEFAULT_VIEWS=('side','top','threequarter','body_detail')      # whole-ship context plus one body close-up
QUALITY={'draft':('BLENDER_WORKBENCH',0),'material':('BLENDER_EEVEE',16),'review':('CYCLES',16),'look':('CYCLES',64)}      # engine and render samples per mode


def blade_view(s,d,name):
    """Camera frame for the thermal-detail views from thermal_geometry: blade 0 seen along its plane normal, tilted aft and outboard so the
    root booms, mounts and the coolant loop read, with a clip slab about the blade plane. Returns focus, view direction, frame corners,
    the slab margin (added to the frame depth in render) and the legend."""
    p=s['prototype'];blade=thermal_geometry.blade_of(s);a=math.radians(p['radiator_phase_deg'])
    tangent=Vector((0,-math.sin(a),math.cos(a)));outward=Vector((0,math.cos(a),math.sin(a)))
    direction=(tangent+math.tan(math.radians(TILT_DEG))*(Vector((-1,0,0))+outward)).normalized()
    half=s['radiators']['geometry']['truss_depth_m']/2
    at=thermal_geometry.stations(s,blade);bays=p['radiator_stay_bays']
    if name=='root_detail':
        x0,x1=at['stays'][bays.index(4)]-3,at['stays'][bays.index(6)]+3;r0,r1=4.5,12.0
    else:
        joints=[j for j in thermal_geometry.bay_joints(s,blade) if j['index'] not in bays]
        xj=joints[min(1,len(joints)-1)]['x'];x0,x1=xj-6,xj+6;r0,r1=6.0,20.0
    centre=Vector(((x0+x1)/2,(r0+r1)/2*math.cos(a),(r0+r1)/2*math.sin(a)))
    corners=[Vector((x,r*math.cos(a)+z*(-math.sin(a)),r*math.sin(a)+z*math.cos(a))) for x in (x0,x1) for r in (r0,r1) for z in (-half,half)]
    legend=["red block + 2 lugs: the one fixed datum (aft root) | yellow block + rail: slide mount, 0.20 m local travel | yellow shoes: joint slides",
            "purple band: root transition, the only variable-emissivity zone",
            "pale bead: 0.125 m non-emitting joint | green: feed and return bellows | grey sheath: coolant chase round its U loop",
            "dark cell: isolated/cooled | pale green: resurfaced, unqualified | glow: thermal-state display, not emissivity",
            "sizes PROTOTYPE; actual growth, CTE and temperature map OPEN"]
    return centre,direction,corners,half+2.5,legend


def tube_mesh(name,rings):
    """Open quad tube through a list of rings (each a list of 3D points); displayed with a temporary Wireframe modifier, never saved."""
    n=len(rings[0]);verts=[v for r in rings for v in r];faces=[(i*n+j,i*n+(j+1)%n,(i+1)*n+(j+1)%n,(i+1)*n+j) for i in range(len(rings)-1) for j in range(n)]
    mesh=bpy.data.meshes.new(name);mesh.from_pydata(verts,[],faces);return mesh


def sector_wires(s,k0,st,near):
    """In-memory display wires for sector_keel_detail: each docking corridor (hull_geometry.dock_corridors, collar tip out to the clip radius) and the
    forward collar inner radius over the keel span (hull_geometry.inner_radius_at), so the nine tie crossings read with the hull hidden."""
    out=[];seg=24
    def add(name,mesh,colour):
        obj=bpy.data.objects.new(name,mesh);bpy.context.scene.collection.objects.link(obj);mesh.materials.append(material(name,colour,1))
        obj.modifiers.new('Preview_Wire','WIREFRAME').thickness=.04;obj.visible_shadow=False;out.append(obj)
    for c in hull_geometry.dock_corridors(s):
        u=Vector((0,math.cos(c['theta']),math.sin(c['theta'])));e1=Vector((1,0,0));e2=u.cross(e1)
        rings=[[Vector((c['x'],0,0))+u*r+(e1*math.cos(2*math.pi*j/seg)+e2*math.sin(2*math.pi*j/seg))*c['radius'] for j in range(seg)] for r in (c['r0'],(c['r0']+near)/2,near)]
        add('Preview_Corridor_'+c['name'],tube_mesh(c['name'],rings),(1.0,.78,.15))
    n=int(math.ceil((st['truss_aft_hub']-k0['x0'])/COLLAR_STEP_M));xs=[k0['x0']+(st['truss_aft_hub']-k0['x0'])*i/n for i in range(n+1)];seg=96
    for i,x in enumerate(xs):            # one thin band per station, so only the circles read (no axial lines that hide the keels)
        r=hull_geometry.inner_radius_at(s,x)
        add(f'Preview_Collar_Radius_{i}',tube_mesh('collar',[[Vector((x+dx,r*math.cos(2*math.pi*j/seg),r*math.sin(2*math.pi*j/seg))) for j in range(seg)] for dx in (-.03,.03)]),(.2,.9,.9))
    return out


def render(root=ROOT, views=None, size=768, state="COAST", out_dir=None, hull='show', sim_proxies='hide', study=None, quality='draft'):
    # study (FWD-V2 and later in-memory studies): .spec(s) returns the study spec, .apply(s, state) adds its overlay after posing, .note is a caption line.
    s,*_=load(root);s=study.spec(s) if study else s;d=derived(s)
    # A display pose (DEFENSE_ENGAGED, SHIELD_DAMAGED, RADIATOR_DAMAGED) renders its base preset with the pose's control values; never saved.
    # A timeline mark (TL_*, FUT-005) renders the configuration its phase shows, posed with the timeline's control values at the mark.
    poses=display_poses(s);marks=flight_timeline.marks(s)
    base=poses[state][1] if state in poses else flight_timeline.shown(next(p for p in flight_timeline.phases(s) if p['id']==marks[state]['phase'])) if state in marks else state
    cfg=s['configuration'].get(base)
    if cfg is None or not cfg['buildable']:raise ValueError(f'Not a buildable configuration, display pose or timeline mark: {state}')
    rotating=cfg['habitat']=='ROTATING'
    bpy.ops.wm.open_mainfile(filepath=str(root/'assets/wayfarer'/(s['vehicle']['asset']+'.blend')))
    scene=bpy.context.scene
    # The preset is posed in memory on the linked controls: ring spin and locks, and the P1F drive state (plasma, light). Never saved.
    pose_configuration(s,base)
    if state in poses:
        if poses[state][0]=='forward_defense':pose_forward_state(forward_shield.display_pose(s,state))
        else:pose_radiator_state(radiator_health.display_pose(s,state))
    if state in marks:
        ch=flight_timeline.channels(s);pose_timeline(s,flight_timeline.control_values(ch,flight_timeline.sample(s,state,ch)['values']))
    if study:study.apply(s,state)
    # Hull visibility is an in-memory preview toggle; the saved assembly is untouched.
    shell=bpy.data.objects.get('Assembly_HULL')
    if shell and hull=='hide':shell.hide_render=shell.hide_viewport=True
    # P1-003 simulation proxies are saved hidden; showing them is an in-memory toggle (after bounds, so framing is unchanged).
    proxies=[o for o in bpy.data.objects if o.get('kind')=='sim_proxy']
    engine,samples=QUALITY[quality]
    scene.render.engine=engine
    if engine=='CYCLES':
        scene.cycles.device='CPU';scene.cycles.samples=samples;scene.cycles.use_denoising=True;scene.cycles.seed=0
    elif engine=='BLENDER_EEVEE':
        scene.eevee.taa_render_samples=samples
        scene.eevee.use_raytracing=False      # fast direct-light preview; Cycles remains the lighting review
        scene.eevee.shadow_ray_count=4;scene.eevee.shadow_step_count=16      # C04: the default 1/6 leaves soft-sun shadow speckle on shaded blade faces at 16 samples
    scene.render.resolution_x=size;scene.render.resolution_y=round(size*.75);scene.render.resolution_percentage=100
    scene.render.image_settings.file_format='PNG'
    scene.render.film_transparent=False
    scene.world.use_nodes=True
    background=next(n for n in scene.world.node_tree.nodes if n.type=='BACKGROUND')
    background.inputs['Color'].default_value=(.055,.075,.10,1)
    background.inputs['Strength'].default_value=.65
    scene.world.color=(.055,.075,.10)      # Workbench background
    shading=scene.display.shading;shading.light='STUDIO';shading.color_type='MATERIAL';shading.show_backface_culling=False
    if quality=='draft':shading.show_cavity=True;shading.cavity_type='WORLD'      # draft: crease shading so forms read without Cycles light
    for i,location in enumerate([(70,-100,180),(-90,60,100),(20,100,-100)]):
        data=bpy.data.lights.new(f'Preview_Sun_{i}','SUN');data.energy=[2.5,1.8,1.0][i];data.angle=.15
        obj=bpy.data.objects.new(data.name,data);scene.collection.objects.link(obj);obj.location=location
        obj.rotation_euler=(-obj.location).to_track_quat('-Z','Y').to_euler()
    data=bpy.data.cameras.new('Preview_Camera');camera=bpy.data.objects.new(data.name,data);scene.collection.objects.link(camera)
    scene.camera=camera;data.clip_end=2000;data.clip_start=.1
    low,high=bounds();corners=[Vector(p) for p in itertools.product(*[(low[i],high[i]) for i in range(3)])]
    target=(low+high)/2
    if sim_proxies=='show':
        # Wire display is viewport-only, so a temporary Wireframe modifier makes the proxies read as cages in Cycles.
        for obj in proxies:
            obj.hide_viewport=obj.hide_render=False
            obj.modifiers.new('Preview_Wire','WIREFRAME').thickness=.12
        bpy.context.scene.frame_set(bpy.context.scene.frame_current)
    directions={'side':(0,-1,0),'top':(0,0,1),'bow':(1,0,0),'aft':(-1,0,0),'threequarter':(1,-1.4,.9),'body_detail':(1,-1.6,.8),'bow_detail':(1,0,0),'aft_detail':(-1,0,0),'habitat_detail':(1,-1.4,.6),'ring_detail':(-1,-1,.8),'root_detail':(.6,-1,.8),'joint_detail':(.6,-1,.8),'hull_detail':(1,-1.3,.45),'service_detail':(.35,1,.3),'sector_keel_detail':(0,-1,0),'bay_detail':(1,-1.3,.6),'power_detail':(.45,-1,.55),'hub_detail':(1,-1.2,.7),'hub_section_detail':(0,-1,0),'refuge_section_detail':(0,-1,0),'ring_spar_detail':(0,-1,0),'dock_ring_detail':(0,1,0),'crew_detail':(-1,-1.1,.5),'gap_detail':(.4,-1,.5),'survival_detail':(.45,-1,.55),'shield_detail':(1,-.8,.5),'shield_rear_detail':(-1,-.9,.45),'shield_profile_detail':(0,-1,0),'eye_well_detail':(1,-.55,.4),'eye_facet_detail':(1,-.55,.4),'crown_detail':(.7,.55,.7),'crown_bay_detail':(1,.35,.55),'drone_spine_detail':(-.45,-.4,1.0),'drone_brow_detail':(-.35,.95,.35),'drone_root_detail':(.7,.1,1.0)}
    out=out_dir or root/'runs'/'renders'/'p1'/(state.lower()+('_nohull' if hull=='hide' else '')+('_simproxies' if sim_proxies=='show' else ''));out.mkdir(parents=True,exist_ok=True)
    labels=[];extras=[]
    views=list(directions) if views==['all'] else views or list(DEFAULT_VIEWS)
    unknown=[v for v in views if v not in directions]
    if unknown:raise ValueError(f'Unknown views {unknown}; choose from {sorted(directions)} or all')
    for name in views:
        for obj in labels:
            bpy.data.objects.remove(obj,do_unlink=True)
        labels=[]
        for obj in extras:bpy.data.objects.remove(obj,do_unlink=True)
        extras=[]
        direction=Vector(directions[name]).normalized()
        focus=Vector((0,0,0)) if name.endswith('_detail') else target
        slab=None
        scene.render.resolution_y=round(size*.75)
        if shell:shell.hide_render=shell.hide_viewport=hull=='hide' or name in BLADE_VIEWS or name=='sector_keel_detail'       # blade views hide the casing in memory only
        # Detail frames come from the layout datums and the shared geometry, never from fixed X numbers.
        box=lambda x0,x1,y,z:(Vector(((x0+x1)/2,0,0)),[Vector(p) for p in itertools.product((x0,x1),(-y,y),(-z,z))])
        L=s['ship']['length']['value'];c=habitat_ring.centers(s);o=layout.origins(s);ref=hull_geometry.refuge(s)
        local_corners=box(-L/2,L/2,9,9)[1] if name.endswith('_detail') else corners
        if name=='habitat_detail':
            # The rings are full size in every state, so one frame serves every preset.
            focus,local_corners=box(c[0]-6,c[1]+6,32,32)
        elif name=='ring_detail':
            x=layout.at(s,s['prototype']['thrust_ring_x']);focus,local_corners=box(x-6,x+6,7,7)
        elif name in BLADE_VIEWS:
            focus,direction,local_corners,slab,legend=blade_view(s,d,name)
        elif name=='gap_detail':
            # Blade front against ring A's aft frame face; the whole ring and blade width stays in view.
            gap=((d['front_x_m']+layout.at(s,s['prototype']['rotor_centers_x'][0])-s['habitat_ring']['frame_axial_m']/2)/2)
            focus,local_corners=box(gap-6,gap+6,38,38)
        elif name=='service_detail':
            # Forward service zone ahead of ring B: refuge, airlock, both docks and the docking corridors.
            dock=layout.at(s,s['prototype']['dock_x']);focus,local_corners=box(ref['x0']-2,dock+s['prototype']['dock_corridor_radius_m']+1,8,8)
        elif name=='sector_keel_detail':
            # FWD-001 sector frame: both docks, their corridors, the three keels with both hoops and the nine ties, broadside from the near-dock side. The view
            # direction is the circular mean of the two dock azimuths (zero X component), the near side beyond the first truss ring is clipped away.
            pr=s['prototype'];angs=[math.radians(pr['dock_primary_angle_deg']),math.radians(pr['dock_service_angle_deg'])]
            phi=math.atan2(sum(math.sin(a) for a in angs),sum(math.cos(a) for a in angs));direction=Vector((0,math.cos(phi),math.sin(phi)))
            k0=forward_shield.sector_keels(s)[0];st_=forward_shield.stations(s)
            R=hull_geometry.service_fittings(s)[1]['r1']+pr['dock_corridor_radius_m']+1.0
            focus,local_corners=box(k0['x0']-1,st_['truss_aft_hub']+1,R,R)
            near=forward_shield.prototype(s)['truss_ring_radii_m'][0]+1.0
        elif name=='power_detail':
            # P1-007 main battery and pulse bank beside the reactor and Brayton trains; best with --hull hide.
            main=[q for q in power_storage.packs(s) if q['layer'] in {'MAIN_BATTERY','PULSE_BANK'}]
            focus,local_corners=box(min(q['x0'] for q in main)-5,max(q['x1'] for q in main)+5,5,5)
        elif name=='survival_detail':
            # The two survival packs in the service zone beside the refuge and airlock; best with --hull hide.
            surv=[q for q in power_storage.packs(s) if q['layer']=='SURVIVAL_RESERVE']
            focus,local_corners=box(min(q['x0'] for q in surv)-3,max(q['x1'] for q in surv)+3,7,7)
        elif name=='hub_detail':
            # P1-008 rotor hubs from outside: drums, fluid cartridges, spokes and ring spoke rails.
            focus,local_corners=box(c[0]-2.2,c[1]+2.1,2,2.5)
        elif name=='hub_section_detail':
            # P1-008 rotor-1 hub cut on the axial XZ plane (camera clipping, in memory only): stationary segments, rotating rings and
            # drum appear as coloured strips above and below the spine. Workbench lighting keeps the cut shells readable.
            # P1-001 widens it aft to include the crew vestibule, its struts and ports.
            # HAB-001: the aft bound is the vestibule's aft guard face less 0.3 m, so both seal planes (guard outer faces) are in the cut.
            x0=c[0];xa=x0+s['crew_transfer']['vestibule_u_m'][0]-.3;xb=x0+2.8;focus=Vector(((xa+xb)/2,0,0));local_corners=[Vector(p) for p in itertools.product((xa,xb),(-1,1),(-2.1,2.1))]
        elif name=='ring_spar_detail':
            # HAB-001: ring A against the leading radiator spar from the side: the 1.5 m service gap between the nominal spar front and ring A's aft sweep face.
            focus,local_corners=box(o['RADIATOR_FRONT']-3,c[0]+3,32,32)
        elif name=='refuge_section_detail':
            # HAB-001: the refuge cut on the axial XZ plane (camera clipping, in memory only): the 0.20 m water jacket, end caps and the spine bore.
            focus,local_corners=box(ref['x0']-1.5,ref['x1']+1.5,4,4)
        elif name=='dock_ring_detail':
            # HAB-001: the first dock port and its capture ring from outside, along the port axis (box dock +-3 m).
            q=hull_geometry.capture_rings(s)[0];u=Vector((0,math.cos(q['theta']),math.sin(q['theta'])));w=Vector((0,-math.sin(q['theta']),math.cos(q['theta'])))
            direction=u;focus=Vector((q['x'],0,0))+u*q['r1']
            local_corners=[focus+Vector((dx,0,0))+u*dr+w*dt for dx,dr,dt in itertools.product((-3,3),(-3,3),(-3,3))]
        elif name=='crew_detail':
            # P1-001 crew route from aft: vestibules, struts, tube roots and bends at the hubs. No room turns, so the same view
            # serves every preset (hub_section_detail shows the hub cut).
            focus,local_corners=box(c[0]-3.7,c[1]+1.1,6.5,6.5)
        elif name in ('shield_detail','shield_rear_detail'):
            # FGR-006 whole forward structure: shield disc, truss depth, Dust Lance and the field zone; the rear view shows the truss and Crown housing.
            fs=forward_shield.stations(s);focus,local_corners=box(fs['truss_aft'],fs['lance_tip'],fs['shield_r'],fs['shield_r'])
        elif name=='shield_profile_detail':
            # FWD-001 side profile of the conical Brow: flat hub, cone to the swept rim, truss depth, the layer ahead and the Lance (hull hidden is best for the truss).
            fs=forward_shield.stations(s);focus,local_corners=box(fs['truss_aft']-2,fs['lance_tip']+1,fs['shield_r'],fs['shield_r'])
        elif name=='eye_well_detail':
            # The four recessed EYE wells around the Lance root, from ahead and above.
            fs=forward_shield.stations(s);focus,local_corners=box(fs['front']-1.0,fs['face']+6.0,7,7)
        elif name=='eye_facet_detail':
            # FWD-V2: the F1 well wherever the (study) layout puts it, with its truss neighbourhood.
            fs=forward_shield.stations(s);w=forward_shield.wells(s)[0]
            focus=Vector(((w['x0']+w['x1'])/2,w['y'],w['z']));local_corners=[Vector(p) for p in itertools.product((w['x0']-2,w['x1']+3),(w['y']-6,w['y']+6),(w['z']-6,w['z']+6))]
        elif name=='crown_bay_detail':
            # FWD-V2 AG-008 / AVA-003: bays 1-3 (azimuth 0-60 deg) close up, shutters, carriages and gimballed heads (CROWN_* poses face 45 degrees).
            fs=forward_shield.stations(s);cr=forward_shield.crown(s);a=math.radians(30);y,z=cr['stowed_r']*math.cos(a),cr['stowed_r']*math.sin(a)
            focus=Vector((cr['xc']+2,y,z));local_corners=[Vector(p) for p in itertools.product((cr['x1']-1,cr['x1']+3.5),(y-2.5,y+2.5),(z-2.5,z+2.5))]
        elif name=='crown_detail':
            # One quadrant of the shield rim where the Crown housing, partitions and bay windows sit (best with the DEFENSE_ENGAGED pose, whose open bays surround azimuth 45 degrees).
            fs=forward_shield.stations(s);cr=forward_shield.crown(s);y=z=cr['outer_r']*math.sqrt(.5)    # rim point at azimuth 45 degrees
            focus=Vector((cr['xc'],y,z));local_corners=[Vector(p) for p in itertools.product((fs['truss_aft']-2,fs['face']+3),(y-12,y+12),(z-12,z+12))]
        elif name=='bay_detail':
            focus,local_corners=box(c[0]-4.7,c[1]+4.6,8,8)
        elif name=='hull_detail':
            _,a0,a1=hull_geometry.intervals(s)[0];focus,local_corners=box(a0,a1,8,8)
        elif name.startswith('drone_'):
            # DRONE-001 close-ups: the forward DS-13 spine dock and its track, a DS-10 Brow dock on its truss spoke, a DS-11 unit on its SP-51 root dock.
            import drone_fleet
            st_={r['id']:r for r in drone_fleet.stations(s)};k={'drone_spine_detail':('DS-13',-1,3.5),'drone_brow_detail':('DS-10',0,5.0),'drone_root_detail':('DS-11',0,2.5)}[name]
            q=(st_[k[0]]['docks'] or st_[k[0]]['units'])[k[1]];focus=Vector(q['world_centre']);h=k[2]
            local_corners=[focus+Vector(d) for d in itertools.product((-h,h),(-h,h),(-h,h))]
        if name=='sector_keel_detail':extras=sector_wires(s,k0,st_,near)
        quat=Quaternion((1,0,0,0)) if name=='top' else (-direction).to_track_quat('-Z','Y')
        if slab:
            # Blade views: image right = ship +X, image up = the blade's outward radial, so the blade reads root edge at the bottom.
            a0=math.radians(s['prototype']['radiator_phase_deg']);right=(Vector((0,math.cos(a0),math.sin(a0))).cross(direction)).normalized()
            quat=Matrix((right,direction.cross(right),direction)).transposed().to_quaternion()
        projected=[quat.inverted()@(p-focus) for p in local_corners]
        width=max(p.x for p in projected)-min(p.x for p in projected)
        height=max(p.y for p in projected)-min(p.y for p in projected)
        if slab:
            # The clip slab is perpendicular to the (tilted) view, so it must also span the blade plane across the frame: margin + frame depth.
            slab+=max(abs(p.z) for p in projected)
            # Wide, short frames get a matching image shape (room for the legend above the blade edge).
            scene.render.resolution_y=round(size*min(max(height/width+.2,.35),.75))
        aspect=scene.render.resolution_x/scene.render.resolution_y
        data.type='PERSP' if name=='threequarter' else 'ORTHO'
        data.ortho_scale=max(width,height*aspect/.66)*1.05 if slab else max(width,height*aspect)*1.24      # slab views keep the top third for the legend
        data.lens=50
        tanx=math.tan(data.angle_x/2);tany=tanx/aspect
        distance=max(max(abs(p.x)/tanx+p.z,abs(p.y)/tany+p.z) for p in projected)*1.22 if data.type=='PERSP' else 400
        camera.location=focus+direction*distance;camera.rotation_euler=quat.to_euler()
        # C04: a perspective near plane at 0.1 m with a ~400 m camera loses the 1-2 cm radiator overlay lifts in the rasterized depth buffer
        # (Eevee/Workbench z-fighting); half the distance to the nearest whole-ship bound corner keeps the far/near ratio small.
        data.clip_start=distance if name in SECTION_VIEWS else distance-near if name=='sector_keel_detail' else max(.1,.5*(distance-max((quat.inverted()@(p-focus)).z for p in corners))) if data.type=='PERSP' else .1
        data.clip_end=2000
        if slab:data.clip_start,data.clip_end=distance-slab,distance+slab      # keep a slab about the blade plane: other blades and the far hull drop out
        scene.render.engine='BLENDER_WORKBENCH' if name in SECTION_VIEWS else engine
        depth=distance+.02 if name in SECTION_VIEWS else distance-slab+.5 if slab else distance-near+.5 if name=='sector_keel_detail' else max(2,data.clip_start+2)
        field_width=2*depth*tanx if data.type=='PERSP' else data.ortho_scale
        field_height=field_width/aspect
        lines=[f'WAYFARER 001 / preset {state} (rings {cfg["habitat"]}) / {name.upper().replace("_"," ")}',
               f"{d['length_m']:g} m body length | {d['body_diameter_m']:g} m body diameter | REP_PROXY | hull {'PROTOTYPE' if shell and hull=='show' and not slab else 'hidden'}"+(' | magenta wire: massless sim proxies' if sim_proxies=='show' else ''),
               'radiator glow: PROTOTYPE thermal-state display, not emissivity'+(f" | drive {cfg['max_accel_g']:g} g limit: display throttle {drive_manifold.thrust_level(s,base):.2f}, exhaust run {drive_manifold.exhaust_end_x(s,drive_manifold.thrust_level(s,base))-drive_manifold.stations(s)['exit']:+.1f} m (display only)" if cfg.get('drive')=='ACTIVE' else ''),
               f"3 x {d['net_area_m2']:,.0f} m2 net hot area per blade | blade {d['blade_length_m']:.1f} x {d['net_width_m']:.1f} m" if not name.endswith('_detail') else f"DETAIL: radiators intentionally cropped | orange human {s['prototype']['human_height_m']:g} m"]
        if state in marks:
            caption=flight_timeline.caption(s,state)
            lines=[f'WAYFARER 001 / timeline {caption[0]} / {name.upper().replace("_"," ")}',lines[1],*caption[1:],'radiator glow: PROTOTYPE thermal-state display, not emissivity | exhaust run length is display only',lines[3]]
        if study and study.note:lines.insert(1,study.note)
        if engine=='BLENDER_WORKBENCH' and name not in SECTION_VIEWS:lines[0]+=' / DRAFT (Workbench, no glow)'
        if engine=='BLENDER_EEVEE' and name not in SECTION_VIEWS:lines[0]+=' / MATERIAL (Eevee)'
        if name=='sector_keel_detail':lines+=[f"hull hidden; near side beyond {near:g} m from the axis clipped (Crown, rim, ring-B rim); corridor and collar radius are display wires; keel aft ends FREE at X {k0['x0']:.2f} m (draft Q45)"]
        if slab:lines=lines[:3]+legend+[f"blade 0 along its plane normal, tilted {TILT_DEG:g} deg aft and outboard | hull hidden, clip slab +-{slab:.1f} m"]
        for i,title in enumerate(lines):
            text=bpy.data.curves.new(f'Preview_Label_{i}','FONT');text.body=title;text.size=field_width*(.019 if i==0 else .013)
            text.materials.append(material('Label',(.70,.85,.93),1))
            obj=bpy.data.objects.new(text.name,text);scene.collection.objects.link(obj)
            obj.rotation_euler=quat.to_euler()
            obj.location=camera.location+quat@Vector((-field_width*.47,field_height*(.45-i*.038),-depth))
            labels.append(obj)
            if hasattr(obj,'visible_shadow'):obj.visible_shadow=False          # no stray label shadows on the geometry
        if slab:
            # Dark backing panel behind the legend so it reads over the pale hot face.
            rows=len(lines);w=field_width*.66;h=field_height*(.038*rows+.03)
            panel=bpy.data.meshes.new('Preview_Label_Panel');panel.from_pydata([(0,0,0),(w,0,0),(w,-h,0),(0,-h,0)],[],[(0,1,2,3)])
            obj=bpy.data.objects.new(panel.name,panel);scene.collection.objects.link(obj);panel.materials.append(material('LabelPanel',(.02,.03,.05)))
            obj.rotation_euler=quat.to_euler();obj.visible_shadow=False
            obj.location=camera.location+quat@Vector((-field_width*.49,field_height*.47,-depth-.2))
            labels.append(obj)
        scene.render.filepath=str(out/f'preview_{name}.png')
        bpy.ops.render.render(write_still=True)
        print(f'WF_PREVIEW {name}',flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=ROOT);p.add_argument('--views',nargs='+');p.add_argument('--size',type=int,default=768);p.add_argument('--state',default='COAST');p.add_argument('--hull',choices=['show','hide'],default='show');p.add_argument('--sim-proxies',choices=['show','hide'],default='hide');p.add_argument('--out-dir',type=Path);p.add_argument('--quality',choices=list(QUALITY),default='draft')
    a=p.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    if a.size<128 or a.size>1024:raise ValueError('Use inexpensive 128–1024 px previews')
    render(a.root.resolve(),a.views,a.size,a.state,a.out_dir,a.hull,a.sim_proxies,quality=a.quality)
