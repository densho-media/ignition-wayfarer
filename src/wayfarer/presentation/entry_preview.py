"""HUM-001 eye-level previews of the primary boarding route (zones 1-5, zones 3-4 at ring B, the refuge leg and the thrust review): the port from
outside, the eighteen first-person cameras saved in the vehicle (port, chamber mannequin, trunk node, trunk mannequin, ring-A spine port, vestibule
mannequin, top of the sector-1 spoke run, spoke mannequin, landing mannequin, sector aisle, ring-B spine port, ring-B vestibule mannequin, ring-B
bulkhead, refuge port, refuge mannequin, refuge approach from the rings, the trunk shaft from its floor and the trunk climber under thrust), a
cutaway through the port and the trunk junction with the mannequins, a long cutaway of the trunk through the spine and both hubs, a cutaway through
each ring's vestibule and its spine port (on ring B up through the neck and bulkhead), a cutaway along the crew tube of each ring's spine-port
sector (ring B's labelled with its ladder push, human_entry.ladder_push), a cross-section of the sector-1 landing and a cross-section of the storm
refuge through its port. IND-001 adds the S004A greeting: the induction figures and their two cameras appended from the characters asset
(the zone-1 mannequin hidden; in the point of view the newcomer's own head, torso and upper arms too). IND-001 2.5 adds a view from the aisle
at each induction sector stop, at its review figure (human_entry.induction_stations), labelled from the sector_whitebox screen. IND-001 4.2
adds one still per induction stop (ind_<stop>): the stop's eye-level view ([induction].stops `view`) with the staged characters of its scenes and no review
figures, labelled with the stop, its scenes, its operating state (human_entry.induction_sequence) and its sources. Poses the hatches in memory
only (the docked state holds the rotors at their index angle, where the ring stops are drawn too); saves nothing."""
from pathlib import Path
import argparse
import math
import sys
import bpy
from mathutils import Matrix, Vector
ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT/'src/wayfarer'),str(ROOT/'src/wayfarer/build')]
from common import apply_look, material, pose_configuration, pose_transfer
from spec import load
import human_entry as he
import characters

VIEWS=['exterior','port_eye','mannequin_eye','node_eye','trunk_eye','vestibule_port','vestibule_eye','spoke_top','spoke_eye','landing_eye','landing_aisle',
       'vestibule_b_port','vestibule_b_eye','spoke_b_bulkhead','cutaway','trunk_cutaway','vestibule_cutaway','spoke_cutaway','landing_cutaway',
       'vestibule_b_cutaway','spoke_b_cutaway','refuge_port','refuge_eye','refuge_approach','refuge_section','trunk_shaft','trunk_climb','thrust_elbow','thrust_step',
       'greeting','greeting_pov','stop_habitat','stop_garden','stop_burn_readiness','stop_specialists','stop_burn_station',
       'ind_arrival','ind_spine','ind_transfer','ind_habitat','ind_garden','ind_burn_readiness','ind_specialists','ind_burn_station']
CAMERAS={'port_eye':'CAM_HUM_ENTRY_PORT','mannequin_eye':'CAM_HUM_ENTRY_EYE','node_eye':'CAM_HUM_NODE','trunk_eye':'CAM_HUM_TRUNK_EYE',
         'vestibule_port':'CAM_HUM_VESTIBULE_PORT','vestibule_eye':'CAM_HUM_VESTIBULE_EYE','spoke_top':'CAM_HUM_SPOKE_TOP','spoke_eye':'CAM_HUM_SPOKE_EYE',
         'landing_eye':'CAM_HUM_LANDING_EYE','landing_aisle':'CAM_HUM_LANDING_AISLE','vestibule_b_port':'CAM_HUM_VESTIBULE_B_PORT','vestibule_b_eye':'CAM_HUM_VESTIBULE_B_EYE',
         'spoke_b_bulkhead':'CAM_HUM_SPOKE_B_BULKHEAD','refuge_port':'CAM_HUM_REFUGE_PORT','refuge_eye':'CAM_HUM_REFUGE_EYE',
         'refuge_approach':'CAM_HUM_REFUGE_APPROACH','trunk_shaft':'CAM_HUM_TRUNK_SHAFT','trunk_climb':'CAM_HUM_TRUNK_CLIMB_EYE',
         'thrust_elbow':'CAM_HUM_THRUST_ELBOW','thrust_step':'CAM_HUM_THRUST_STEP',
         'greeting':'CAM_IND_GREETING','greeting_pov':'CAM_IND_GREETING_POV','stop_habitat':'CAM_IND_HABITAT','stop_garden':'CAM_IND_GARDEN',
         'stop_burn_readiness':'CAM_IND_BURN_READINESS','stop_specialists':'CAM_IND_SPECIALISTS','stop_burn_station':'CAM_IND_BURN_STATION'}


def frame(look, up):
    z=-Vector(look).normalized();x=Vector(up).cross(z).normalized();y=z.cross(x)
    return Matrix((x,y,z)).transposed().to_euler()


def label(scene, camera, lines, width, aspect, depth, dark=False):
    out=[]
    for i,text in enumerate(lines):
        data=bpy.data.curves.new(f'Preview_Label_{i}','FONT');data.body=text;data.size=width*(.024 if i==0 else .016)
        data.materials.append(material('LabelDark',(.02,.03,.05)) if dark else material('Label',(.70,.85,.93),1))
        obj=bpy.data.objects.new(data.name,data);scene.collection.objects.link(obj);obj.parent=camera
        obj.location=(-width*.47,width/aspect*(.44-i*.05),-depth);obj.visible_shadow=False;out.append(obj)
    if not dark:
        # A translucent dark plate behind light labels keeps them readable over bright interiors.
        y0,y1=width/aspect*(.44-.05*(len(lines)-1))-width*.012,width/aspect*.44+width*.032;x0,x1=-width*.48,width*.48
        data=bpy.data.meshes.new('Preview_Label_Plate');data.from_pydata([(x0,y0,0),(x1,y0,0),(x1,y1,0),(x0,y1,0)],[],[(0,1,2,3)])
        data.materials.append(material('LabelPlate',(0,0,0),0,.85))
        obj=bpy.data.objects.new(data.name,data);scene.collection.objects.link(obj);obj.parent=camera;obj.location=(0,0,-depth*1.002)
        obj.visible_shadow=False;out.append(obj)
    return out


def render(root=ROOT, views=None, size=768, state='DOCKED', hatch='open', out_dir=None, look=False):
    s,*_=load(root);f=he.ports(s)[0];st=he.stations(s,f);report=he.check(s);r=report['ports'][f['name']];tk=report['trunk'];vb=report['vestibule'];sp=report['spoke'];ld=report['landing']
    bpy.ops.wm.open_mainfile(filepath=str(root/'assets/wayfarer'/(s['vehicle']['asset']+'.blend')))
    scene=bpy.context.scene;pose_configuration(s,state)
    ctrl=bpy.data.objects['DOCK_ENTRY_CTRL']
    for which in ('outer','inner'):ctrl[f"{f['name']}_{which}_open"]=1.0 if hatch=='open' else 0.0
    ctrl.update_tag()
    for obj in bpy.data.objects:
        if obj.name.endswith('_Hatch_Hinge'):obj.update_tag()
    pose_transfer(s,1.0 if hatch=='open' else 0.0)    # Q46: gates, drum doors and tube hatches with the leaves (indexed transfer when docked)
    scene.frame_set(scene.frame_current)
    if look:
        # FUT-003: the S004 look in memory; Cycles lights the interior from the emitting light strips and berth lights alone.
        apply_look(s);scene.view_settings.view_transform='AgX'
    scene.render.resolution_x=size;scene.render.resolution_y=round(size*.75);scene.render.image_settings.file_format='PNG'
    scene.cycles.device='CPU';scene.cycles.samples=48;scene.cycles.use_denoising=True;scene.cycles.seed=0
    scene.world.use_nodes=True;bg=next(n for n in scene.world.node_tree.nodes if n.type=='BACKGROUND')
    bg.inputs['Color'].default_value=(.02,.025,.035,1);bg.inputs['Strength'].default_value=.4
    for i,(direction,energy) in enumerate([((.3,-.8,-.6),2.5),((-.5,.6,-.4),1.2)]):
        data=bpy.data.lights.new(f'Preview_Sun_{i}','SUN');data.energy=energy;data.angle=.15
        obj=bpy.data.objects.new(data.name,data);scene.collection.objects.link(obj);obj.rotation_euler=frame(direction,(1,0,0))
    out=out_dir or root/'runs/renders/p1/human_entry';out.mkdir(parents=True,exist_ok=True)
    people=None
    if any(v.startswith(('greeting','ind_')) for v in views or VIEWS):
        # IND-001: append (not link) the characters asset, so its objects can be hidden per view; nothing is saved.
        name=s['characters']['asset']
        with bpy.data.libraries.load(str(root/'assets/characters'/f'{name}.blend'),link=False) as (src,dst):dst.collections=[name]
        people=dst.collections[0];scene.collection.children.link(people);people=[o.name for o in people.all_objects if o is not None]
    aspect=scene.render.resolution_x/scene.render.resolution_y;u,w=he.axes(f);labels=[]
    data=bpy.data.cameras.new('Preview_Camera');preview=bpy.data.objects.new(data.name,data);scene.collection.objects.link(preview)
    head=f"WAYFARER 001 / HUM-001 boarding route, zones 1-5 / {state}, hatches {hatch} (display)"+(' / S004 look (PROTOTYPE)' if look else '')
    entry=(f"zone 1: passage 1.6 m (Q33) | chamber {2*st['chamber_r']:.1f} x {st['a_out']-st['a_in']:.1f} m | hull gap {r['hull_gap_m']:.2f} m | "
           f"leaf to wall {r['leaf_wall_gap_m']:.2f} m | suited margin {r['suited_margin_m']:.2f} m | PROTOTYPE")
    trunk=(f"zone 2: node {2*st['node_r']:.1f} x {st['bottom']-st['node_in']:.2f} m | trunk 1.6 m bore, {tk['clear_between_fixtures_m']:.2f} m between rails | "
           f"spine core r {s['prototype']['spine_core_radius_m']:.2f} m, hubs +0.075 m | PROTOTYPE")
    def ring_facts(vb,name):
        return (f"zone 3: ring-{name} vestibule chamber {vb['chamber_clear_length_m']:.1f} m long, {vb['clear_depth_m']:.2f} m deep | spine port {vb['spine_port_clear_m']:.1f} m | "
                f"sector hatches {vb['outer_hatch_clear_m']:.1f} m | suited margin {vb['suited_margin_m']:.2f} m | PROTOTYPE")
    ring=ring_facts(vb,'A');ring_b=ring_facts(report['vestibule_B'],'B')
    one=sp['sectors'][sp['mannequin']['sector']]
    spoke=(f"zone 4: ring-A crew tube {sp['tube_clear_m']:.1f} m clear, {one['length_m']:.1f} m, elbows {'/'.join(f'{e:.0f}' for e in one['elbows_deg'])} deg | "
           f"ladder {one['rungs']} rungs, {one['clear_between_fixtures_m']:.2f} m clear | suited margin {one['suited_sweep_margin_m']:.2f} m | PROTOTYPE")
    sb=report['spoke_B'];nk=sb['neck'];one_b=sb['sectors'][sb['mannequin']['sector']]
    spoke_b=(f"zone 4: ring-B crew tube {sb['tube_clear_m']:.1f} m on a {nk['clear_m']:.2f} m neck, bulkhead +{nk['above_outer_wall_m']:.2f} m | {one_b['length_m']:.1f} m, "
             f"{one_b['rungs']} rungs | suited margin: neck {nk['suited_margin_m']:.2f} m, tube {one_b['suited_sweep_margin_m']:.2f} m | PROTOTYPE")
    lp=sb['ladder_push']
    push_b=(f"zone 4: ring-B ladder {lp['ladder_wall']} | {lp['pulled_off_when']} at {lp['review_speed_m_s']:.1f} m/s: {lp['pulled_off_g']:.3f} g off the rungs, "
            f"{lp['overhang_deg']['run_top']:.0f} deg overhang at the run top | none below {lp['neutral_speed_m_s']:.2f} m/s | PROTOTYPE")
    land=(f"zone 5: sector hatch {ld['hatch_clear_m']:.1f} m, sliding leaf | ladder {ld['ladder']['rungs']} rungs to the deck | "
          f"well {ld['well_m']['width']:.1f} x {ld['well_m']['depth']:.2f} m | headroom {ld['headroom_m']:.2f} m | suited margin {ld['descent_suited_margin_m']:.2f} m | PROTOTYPE")
    rq=report['refuge'];oc=rq['occupants']
    refuge=(f"refuge: port {rq['port']['clear_m']:.2f} m | cavity {rq['cavity']['depth_m']:.2f} x {rq['cavity']['length_m']:.2f} m, "
            f"{rq['cavity']['volume_per_person_m3']:.2f} m3 each | {oc['stations']} anchor rails, {oc['neighbour_gap_m']:.2f} m between bodies | "
            f"suited margin: port {rq['port']['suited_margin_m']:.2f}, round {oc['circulation_margin_m']:.2f} m | PROTOTYPE")
    em=rq['emergency'];far=max(em['sectors'].values(),key=lambda e:e['to_refuge_m'])
    emergency=(f"to the refuge: {far['to_refuge_m']:.0f} m, {far['rungs']} rungs from the farthest aisle, {far['minutes_at_review_pace']:.1f} min "
               f"at {em['review_speed_m_s']:.1f} m/s | port rails {em['port_rail_reach_m']:.2f} m reach | rings stopped | PROTOTYPE")
    th=tk['thrust'];lad=th['ladder'];ps=th['ports'];pb=next(v for k,v in ps.items() if k.startswith('Crew_Port_2_'));fr=th['falls']['refuge_port']['first_ignition_peak_g']
    thrust=(f"thrust, aft down: ladder {lad['height_m']:.1f} m, {lad['rungs']} rungs, arrest rail | ports {pb['sill_above_floor_m']:.2f} m (ring B), "
            f"{ps['Crew_Refuge_Port']['sill_above_floor_m']:.2f} m (refuge) up | refuge fall {fr['speed_m_s']:.0f} m/s at 1.5 g | PROTOTYPE")
    q=th['q47'];fa=q['tubes']['A1']['floor_ladders'];ss=q['sector_step']
    q47=(f"Q47 aft down to 1.5 g: elbow floor ladders {fa[0]['slope_deg']:.0f} deg / {fa[1]['slope_deg']:.0f} deg, {fa[0]['rungs']}+{fa[1]['rungs']} rungs every "
         f"{fa[0]['rise_per_rung_m']:.2f} m of rise | hatch sill {ss['sill_above_floor_m']:.2f} m up, steps at {', '.join(f'{x:.2f}' for x in ss['rungs_above_floor_m'])} m | "
         f"ring-B chamber {q['vestibules']['B']['clear_length_m']:.2f} m high, crawl rail | PROTOTYPE")
    induction=(f"induction S004A: {s['characters']['instructor']['title']} greets the newcomer | fit-out: {s['route_fitout']['title']} | "
               f"identities open (Q49) | PROTOTYPE")
    import sector_whitebox as sw
    stations=he.induction_stations(s);fit={fn:sw.check(s,fn) for fn in {q['function'] for q in stations.values()}};stops={q['key']:q for q in s['induction']['stops']}
    def stop_facts(key):
        q=stations[key];c=fit[q['function']];reach=c['mannequins'][q['pose']]['reach_m'];w=s['sector_whitebox']
        if q['pose']=='aisle':
            b=next(iter(c['berths'].values()))
            return (f"zone 6: {len(c['berths'])} berths along {b['axis']}, {b['clear_m']:.2f} m clear, top platform {max(v['platform_m'] for v in c['berths'].values()):.2f} m up | "
                    f"top berth edge {reach['top_berth_edge_m']:.2f} m from the shoulder | PROTOTYPE")
        if q['pose']=='garden':
            r=c['racks'][q['block']];m=next(iter(c['mess'].values()))
            return (f"zone 7: rack {r['depth_m']:.2f} m deep, {r['tiers']} tray levels, top tray {reach['top_tray_centre_m']:.2f} m (back {reach['top_tray_back_m']:.2f} m) "
                    f"from the shoulder | mess {m['seats']} seats | PROTOTYPE")
        if q['pose']=='patient':
            m=c['medical'][q['block']]
            return (f"zone 8: treatment couch {m['length_m']:.1f} x {m['width_m']:.2f} m at {w['medical_table_m']:.2f} m, feet aft | medic reach "
                    f"{c['mannequins']['medic']['reach_m']['patient_chest_m']:.2f} m | aft down: to a burn couch | PROTOTYPE")
        if q['pose']=='operator':
            o=c['operations'][q['block']]
            return (f"zone 8: {o['stations']} {'standing' if o['standing'] else 'seated'} stations facing {o['operators_face']}ly | desk {reach['desk_m']:.2f} m, "
                    f"display {reach.get('display_eye_m',0):.2f} m from the eye | {w['access_width_min_m']:.2f} m couch strip | PROTOTYPE")
        return (f"burn station: five-point harness | burn-go consoles {w['couch_console_m'][0]:.2f}-{w['couch_console_m'][1]:.2f} m up, "
                f"{reach['console_m']:.2f} m from the shoulder | belt {reach['belt_m']:.2f} m | PROTOTYPE")
    # IND-001 4.2: each induction still reuses the preview view of its stop's camera ([induction].stops `view`; "stage" -> its stop_* facts).
    seq=he.induction_sequence(s);order=[q['key'] for q in s['induction']['stops']];sv=characters.stop_views(s)
    STOP_VIEWS={q['key']:('stop_'+q['key'] if q['view']=='stage' else next(v for v,c in CAMERAS.items() if c==q['view'])) for q in s['induction']['stops']}
    for name in views or VIEWS:
        for obj in labels:bpy.data.objects.remove(obj,do_unlink=True)
        ind=name.startswith('ind_');view=STOP_VIEWS[name[4:]] if ind else name;greet=view in ('greeting','greeting_pov')
        for obj in bpy.data.objects:
            if obj.name.startswith('Human_Entry_'):obj.hide_render=greet or ind
            elif obj.name.startswith('Human_Ind_') or obj.get('kind')=='scale_reference':obj.hide_render=ind    # no review figure in a stop still
        if people is not None:
            scenes=stops[name[4:]]['scenes'] if ind else ()
            for obj in filter(None,map(bpy.data.objects.get,people)):
                obj.hide_render=(obj.get('scene') not in scenes) if ind else (not greet or (view=='greeting_pov' and bool(obj.get('pov_hidden'))))
        scene.render.engine='CYCLES'
        if view=='exterior':
            target=Vector(he.world(f,st['a_out']));eye=Vector(he.world(f,st['port_face']+5.5,2.6,math.radians(40)))
            data.type='PERSP';data.lens=24;data.clip_start=.05;data.clip_end=600
            preview.location=eye;preview.rotation_euler=frame(target-eye,(1,0,0));camera=preview;depth=1.0
            note='outside the port: capture ring, open outer hatch, chamber and mannequin; no docked vehicle modelled';facts=entry
        elif view in ('vestibule_cutaway','vestibule_b_cutaway'):
            # Ortho section on the plane through the ship axis and the spine-port axis, seen from the +Y side (the mannequin's half); the near
            # half is clipped away.
            # On ring B the frame reaches up through the neck and bulkhead to the first elbow. The plane turns with the port's angle.
            b=view=='vestibule_b_cutaway';x0,x1=report['vestibule_B' if b else 'vestibule']['x_m'];D=20.0
            rot,v,la=he.vestibule_station(s,2 if b else None);a=rot['phase']+la[v['ports'][0]];up=Vector((0,math.cos(a),math.sin(a)));side=Vector((0,math.sin(a),-math.cos(a)))
            target=Vector(((x0+x1)/2+(.2 if b else .6),0,0))+up*(1.6 if b else .5);data.ortho_scale=4.8 if b else (x1-x0)+2.7
            data.type='ORTHO';preview.location=target+side*D;preview.rotation_euler=frame(-side,up)
            data.clip_start=D;data.clip_end=D+30;camera=preview;depth=D+.02;facts=ring_b if b else ring
            note=(f"cut through the ship axis and the ring-B spine port, near half removed: trunk, port, chamber, neck, bulkhead, collar; bow left" if b else
                  "cut through the ship axis and the ring-A spine port, near half removed: trunk, port, vestibule chamber, guards, hub 1; bow left")
            scene.render.engine='BLENDER_WORKBENCH';sh=scene.display.shading;sh.light='STUDIO';sh.color_type='MATERIAL';sh.show_backface_culling=False;sh.show_cavity=True;sh.show_object_outline=True
        elif view in ('spoke_cutaway','spoke_b_cutaway'):
            # Ortho section on the plane through the sector-1 tube's run axis and the ship X axis, seen from the side away from the crew spoke (+Y at
            # the index pose); the near half is clipped away, so the ladder wall, the mannequin and the elbows show. On ring B the climber stands
            # near the top of the run.
            b=view=='spoke_b_cutaway';mm=(sb if b else sp)['mannequin']
            rot,_,_,frames=he.spoke_station(s,2 if b else None);fr=frames[mm['sector']];p0=Vector(he.at_index(rot,fr['points'][he.RUN]))
            n1=Vector(he.at_index(rot,fr['n1'][he.RUN],False));d=Vector(he.at_index(rot,fr['d'][he.RUN],False));D=20.0
            top=mm['feet_radius_m']+(2.5 if b else 1.0);target=p0-d*p0.dot(d)+Vector((-1.0,0,0))+d*(top-.5)/2;data.ortho_scale=(top+.5)*aspect
            data.type='ORTHO';preview.location=target+n1*D;preview.rotation_euler=frame(-n1,d)
            data.clip_start=D;data.clip_end=D+30;camera=preview;depth=D+.02;facts=push_b if b else spoke
            note=(f"cut through the ring-{'B' if b else 'A'} sector-{mm['sector']} crew tube and the ship axis, half toward the spoke removed: "
                  +('elbows, ladder, climber at the top of the run; bow right' if b else 'vestibule, elbows, ladder, mannequin; bow right'))
            scene.render.engine='BLENDER_WORKBENCH';sh=scene.display.shading;sh.light='STUDIO';sh.color_type='MATERIAL';sh.show_backface_culling=False;sh.show_cavity=True;sh.show_object_outline=True
        elif view=='landing_cutaway':
            # Ortho cross-section of the sector-1 landing on the axial plane through the hatch axis, seen from the bow; the forward half is clipped.
            L=he.landing(s);_,_,point,vector=he.sector_frame(s);D=20.0;data.ortho_scale=7.0
            data.type='ORTHO';preview.location=Vector(point((L['x']+D,-2.45,0.0)));preview.rotation_euler=frame(Vector(vector((-1,0,0))),Vector(vector((0,-1,0))))
            data.clip_start=D;data.clip_end=D+30;camera=preview;depth=D+.02;facts=land
            note='cross-section through the sector-1 hatch axis, forward half removed: tube end, hoop, skin, hatch frame, slid leaf, ladder, well, aisle'
            scene.render.engine='BLENDER_WORKBENCH';sh=scene.display.shading;sh.light='STUDIO';sh.color_type='MATERIAL';sh.show_backface_culling=False;sh.show_cavity=True;sh.show_object_outline=True
        elif view=='refuge_section':
            # Perspective cutaway of the storm refuge from the bow, the near clip on the plane through its port, so the forward half is removed and the
            # aft hoop rail, the mannequin and the anchor rails recede to the aft wall. The cut plane is 1/0.8 of the shell's diameter high, the shell
            # low in it, below the label band.
            rs=he.refuge_station(s);D=6.0;up=Vector((0,math.cos(rs['th']),math.sin(rs['th'])))
            data.type='PERSP';data.sensor_fit='HORIZONTAL';data.lens=data.sensor_width/2*D/(rs['outer']/.8*aspect)
            preview.location=Vector((rs['x']+D,0,0))+up*.5;preview.rotation_euler=frame((-1,0,0),up)
            data.clip_start=D;data.clip_end=D+30;camera=preview;depth=D+.02;facts=refuge
            note='cutaway through the refuge port, forward half removed: trunk, port, inner wall, mannequin, hoop rail, one anchor rail per occupant; port up'
            scene.render.engine='BLENDER_WORKBENCH';sh=scene.display.shading;sh.light='STUDIO';sh.color_type='MATERIAL';sh.show_backface_culling=False;sh.show_cavity=True;sh.show_object_outline=True
        elif view in ('cutaway','trunk_cutaway'):
            # Ortho section on the plane through the port axis and the ship axis, seen from -w; the near half is clipped away (in memory only).
            D=20.0;trunk_view=view=='trunk_cutaway'
            if trunk_view:
                x0,x1=tk['cavity_x_m'];target=Vector(((x0+x1)/2,0,0));data.ortho_scale=(x1-x0+2.0);up=Vector(he.vec(f,1.0))
                note='cut along the ship axis, near half removed: trunk in the bored spine through both hubs; up = port outward, bow left'
            else:
                target=Vector(he.world(f,(st['port_face']-1.0)/2))+Vector((-1.2,0,0));data.ortho_scale=(st['port_face']+1.0+.6)*1.05;up=Vector((1,0,0))
                note='cut through the port and ship axes, near half removed: chamber, open leaves, node, neck, junction, trunk; up = ship +X'
            data.type='ORTHO';preview.location=target-Vector(w)*D;preview.rotation_euler=frame(w,up)
            data.clip_start=D;data.clip_end=D+30;camera=preview;depth=D+.02;facts=trunk
            scene.render.engine='BLENDER_WORKBENCH';sh=scene.display.shading;sh.light='STUDIO';sh.color_type='MATERIAL';sh.show_backface_culling=False;sh.show_cavity=True;sh.show_object_outline=True
        else:
            camera=bpy.data.objects[CAMERAS[view]];depth=.25
            facts=(entry if view in ('port_eye','mannequin_eye') else ring_b if view.startswith('vestibule_b') else ring if view.startswith('vestibule')
                   else spoke_b if view.startswith('spoke_b') else spoke if view.startswith('spoke') else land if view.startswith('landing')
                   else emergency if view=='refuge_approach' else refuge if view.startswith('refuge') else thrust if view in ('trunk_shaft','trunk_climb') else q47 if view.startswith('thrust_')
                   else induction if view.startswith('greeting') else trunk)
            note=camera.get('role','')+f" | {camera.data.lens:g} mm"
        title=head
        if ind and stops[name[4:]]['view']=='stage':
            # 4.2: the stop's aisle camera stands too close to its station, so a wider view (characters.STAGE_VIEWS) shows it.
            v=sv[name[4:]];note=v['role']
            data.type='PERSP';data.lens=v['lens'];data.sensor_fit='AUTO';data.clip_start=.05;data.clip_end=600
            preview.location=Vector(v['at']);preview.rotation_euler=frame(v['look'],v['up']);camera=preview;depth=.25
        if view.startswith('stop_'):
            key=view[5:];q=stations[key];facts=stop_facts(key)
            title=f"WAYFARER 001 / IND-001 stop '{key}' ({', '.join(stops[key]['scenes'])}) / ring A sector {q['sector']} / {state} (display)"
        lines=[title,facts,note]
        if ind:
            # 4.2: stop, scenes, operating state and sources; the view's facts stay as the third line.
            key=name[4:];q=stops[key];o=seq['stops'][key];step=next(n for n,st in enumerate(seq['steps']) if st['key']==o['step'])
            where=f"ring A sector {q['sector']}" if q['at']=='sector' else {'entry':'primary airlock','refuge_port':'trunk at the refuge port','vestibule':'ring-A transfer drum'}[q['at']]
            spin=(f"rings at {o['rpm']:g} rpm, {o['g']:.2f} g {'in the drum, synchronized with ring A' if q['at']=='vestibule' else 'at the deck'}, drawn at the index angle"
                  if o['habitat']=='ROTATING' else 'rings stopped and locked at their index angles')
            lines=[f"IND-001 induction {order.index(key)+1}/{len(order)}: {q['title']} ({', '.join(q['scenes'])})"+(' | S004 look (PROTOTYPE)' if look else ''),
                   f"{where} | {o['state']} (step {step+1}/{len(seq['steps'])} '{o['step']}'): {spin} | sequence: owner Q48",facts,note,
                   f"sources: {s['induction']['sequence_sources']}, 12_WAYFARER_CREW | identities open (Q49)"]
        scene.camera=camera
        width=camera.data.ortho_scale if camera.data.type=='ORTHO' else 2*depth*math.tan(camera.data.angle_x/2)
        labels=label(scene,camera,lines,width,aspect,depth,dark=view=='cutaway')
        scene.render.filepath=str(out/f'entry_{name}.png')
        bpy.ops.render.render(write_still=True)
        print(f'WF_ENTRY_PREVIEW {name}',flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=ROOT);p.add_argument('--views',nargs='+',choices=VIEWS)
    p.add_argument('--size',type=int,default=768);p.add_argument('--state',default='DOCKED');p.add_argument('--hatch',choices=['open','closed'],default='open')
    p.add_argument('--out-dir',type=Path)
    p.add_argument('--look',action='store_true',help='FUT-003: render with the S004 look ([look]) applied in memory')
    a=p.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    if a.size<128 or a.size>1024:raise ValueError('Use inexpensive 128–1024 px previews')
    render(a.root.resolve(),a.views,a.size,a.state,a.hatch,a.out_dir,a.look)
