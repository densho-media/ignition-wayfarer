"""P0 envelope recipes. All unsourced shape choices live in prototype inputs."""
import math
from common import empty, material, mesh, loft, cylinder, annulus, line, ring, link_instance
from spec import derived
import layout
import revision
import hull
import interior
import drive
import drive_manifold
import drive_hot_section
import power
import rotor
import crew
import forward
import forward_shield


def build_component(kind, c, s):
    if kind=='RING_SECTOR':return revision.sector(c,s)
    if kind=='RADIATOR':return revision.radiator(c,s)
    functions={v:k for k,v in s['interior']['components'].items()}
    if kind in functions:return interior.interior(c,s,functions[kind])
    p = s['prototype']
    metal = material('Structure', (0.30,0.40,0.48))
    if kind == 'NOZZLE':
        length, exit_r, throat = p['nozzle_length_m'], p['nozzle_exit_radius_m'], p['nozzle_throat_radius_m']
        loft(c, 'MagneticNozzle_FieldEnvelope', [(0,exit_r),(length*.65,throat),(length,throat)], material('Nozzle',(.21,.33,.43)), caps=False)
        bands = drive_hot_section.liner_tiles(s, drive_hot_section.NOZZLE)
        pfc = material('PFC_Refractory', drive.PFC_COLOR)
        for coil in drive_manifold.nozzle_coils(s):
            drive.hts_designation(ring(c, coil['name'], coil['x'], coil['ring_radius'], coil['tube'], metal), s, 'nozzle')
            tiles = [t for t in bands if t['coil'] == coil['index']]
            if tiles:      # Q40: local strike modules only at the contact-risk coil stations
                obj = drive.pfc_metadata(drive.tile_mesh(c, f'PFC_NOZZLE_STRIKE_{coil["index"]:02}', tiles, pfc, 'pfc_band'), s, 'nozzle_adjacent', tiles, 1)
                obj['strike_module'] = True; obj['liner_performance'] = 'UNKNOWN (Q40, 15!I103): magnetic standoff first; heat flux, active cooling, erosion and life not designed'
                obj['geometry_basis'] = s['drive_hot_section']['nozzle_strike_module_basis']
        empty(c, 'IF_NOZZLE_INLET', (length,0,0))
        empty(c, 'IF_NOZZLE_EXIT')
    else:
        raise ValueError(kind)


def build_subsystem(kind, c, s, asset_dir):
    p=s['prototype']; length=s['ship']['length']['value']; radius=s['ship']['body_diameter']['value']/2
    x=lambda key:layout.at(s,p[key])
    structure=material('Structure',(.30,.40,.48))
    shield=material('Shield',(.48,.43,.28))
    if kind=='STRUCTURE':return revision.structure(c,s)
    elif kind=='HABITAT':return revision.habitat(c,s,asset_dir)
    elif kind in revision.RINGS:return revision.habitat_ring(c,s,asset_dir,revision.RINGS.index(kind)+1)
    elif kind=='STORAGE':
        for j,(y,z) in enumerate([(1,1),(-1,1),(-1,-1),(1,-1)],1):
            tank=cylinder(c,f'Tank_Volume_{j:02}',x('tank_center_x'),p['tank_length_m'],p['tank_radius_m'],material('Tank',(.39,.48,.56)),y*p['tank_offset_m'],z*p['tank_offset_m'])
            ft=s['physics']['fuel_tanks'];tank['representation']=ft['representation'];tank['dimensions_status']=ft['dimensions_status'];tank['fuel_mass_known']=False
        drive.cryo_feed(c,s)
    elif kind=='SHIELDING':return revision.shielding(c,s)
    elif kind=='EYE':
        front=length/2-p['eye_front_inset_m']; depth=p['eye_module_depth_m']
        r=s['eye']['aperture']['value']/2
        # Ring with a bore: the spine-continuation column of the forward shield passes through it without touching (FGR-006 load path).
        if any(forward_shield.in_hub(s,w) for w in forward_shield.wells(s)):      # an outer Eye layout carries each facet on its own frame (WF_FORWARD_SHIELD)
            annulus(c,'EYE_Shared_Mount',front-depth-p['eye_backing_depth_m']/2,p['eye_backing_depth_m'],p['eye_backing_radius_m'],forward_shield.eye_mount_bore(s),structure)
        # Facet j is owner facet Fj: eye.facet_map gives its (Y, Z) quadrant, +Y left looking forward.
        for j,w in enumerate(forward_shield.wells(s),1):
            fx=w['x0'];yq,zq=w['y'],w['z']
            obj=cylinder(c,f'EYE_Facet_{j:02}',fx-depth/2,depth,r,material('EyeHousing',(.20,.30,.34)),yq,zq,kind='eye_facet')
            obj['canon_status']='LOCKED';obj['source_ref']='eye_architecture';obj['component_id']=f'WF.EYE.FACET.{j:02}'
            obj['owner_facet']=s['eye']['facet_map']['labels'][j-1];obj['facet_map_source']='eye_facet_map'
            cylinder(c,f'EYE_Aperture_{j:02}',fx+.015,.02,r,material('Optical',(.10,.58,.64),.4),yq,zq)
            empty(c,f'IF_EYE_FACET_{j:02}',(fx,yq,zq))['owner_facet']=s['eye']['facet_map']['labels'][j-1]
        empty(c,'IF_EYE_MOUNT',(front-depth,0,0))
    elif kind=='FORWARD_SHIELD':
        import exterior
        r=forward.forward_shield(c,s);exterior.forward(c,s)     # S02 slice 1: rim beacons with the forward structure
        return r
    elif kind=='PROPULSION':return drive.propulsion(c,s,asset_dir)
    elif kind=='DEBUG_MAGNETICS':return drive.debug_magnetics(c,s)
    elif kind=='DEBUG_SEPARATRICES':return drive.debug_separatrices(c,s)
    elif kind=='DEBUG_OPTICS':return drive.debug_optics(c,s)
    elif kind=='THERMAL':return revision.thermal(c,s,asset_dir)
    elif kind=='HULL':return hull.hull(c,s)
    elif kind=='SERVICE':return hull.service(c,s)
    elif kind=='POWER_STORAGE':return power.power_storage(c,s)
    elif kind=='ROTOR_INTERFACE':return rotor.rotor_interface(c,s)
    elif kind=='CREW_TRANSFER':return crew.crew_transfer(c,s)
    elif kind=='DRONES':
        import drones
        return drones.drones(c,s)
    else:raise ValueError(kind)


def entry_guides(c,s):
    """HUM-001 non-canon guides (15!A86): the generic mannequins in the primary entry chamber (zone 1), the trunk (zone 2), the ring-A and
    ring-B vestibules (zone 3), on the ladders of both rings' spine-port-sector crew tubes (zone 4), at the foot of the sector landing ladder (zone 5;
    the ring ones placed for the rotors at their index angle, frame 1), in the storm refuge (refuge leg), on the trunk ladder under thrust
    (thrust review) and, for Q47, on a tube elbow's floor ladder and on the step below a sector hatch, the review figures of the induction sectors (IND-001 2.5),
    the HUM-002 storeroom figure and the first-person cameras."""
    import bpy
    from mathutils import Matrix, Vector
    from common import tag
    import human_entry as he
    mat=material('HumanScale',(.96,.55,.12),.15);f=he.ports(s)[0]
    for name,pts,r in he.mannequin(s,f)['rods']+he.trunk_mannequin(s,f)['rods']+[r for j in s['human_entry']['vestibule_rotors'] for r in he.vestibule_mannequin(s,j)['rods']]+[r for j in s['human_entry']['tube_rotors'] for r in he.spoke_mannequin(s,j)['rods']]+he.landing_mannequin(s)['rods']+he.refuge_mannequin(s)['rods']+he.trunk_climber(s)['rods']+he.elbow_climber(s)['rods']+he.thrust_stepper(s)['rods']:
        line(c,name,pts,r,mat,kind='scale_reference')['role']='HUM-001 generic mannequin, non-canon scale guide (15!A86)'
    import storeroom
    for name,pts,r in storeroom.mannequin(s)['rods']:
        line(c,name,pts,r,mat,kind='scale_reference')['role']='HUM-002 storeroom review figure, non-canon scale guide (15!A86)'
    for name,pts,r in he.induction_figures(s):
        line(c,name,pts,r,mat,kind='scale_reference')['role']='IND-001 2.5 sector review figure, non-canon scale guide (15!A86)'
    for cam in he.cameras(s,f)+storeroom.cameras(s):
        data=bpy.data.cameras.new(cam['name']);data.lens=cam['lens'];data.clip_start=cam['clip_start'];data.clip_end=600
        obj=bpy.data.objects.new(cam['name'],data);c.objects.link(obj);tag(obj,cam['name'],'first_person_camera')
        z=-Vector(cam['look']).normalized();x=Vector(cam['up']).cross(z).normalized();y=z.cross(x)
        obj.location=cam['at'];obj.rotation_euler=Matrix((x,y,z)).transposed().to_euler();obj['role']=cam['role']


def human_reference(c,s):
    p=s['prototype']; h=p['human_height_m']; base=(layout.at(s,p['human_reference_center_x']),-8.2,-h/2)
    mat=material('HumanScale',(.96,.55,.12),.15)
    def at(x,y,z):return(base[0]+x,base[1]+y,base[2]+z*h)
    line(c,'Human_Torso',[at(0,0,.38),at(0,0,.78)],.13,mat,kind='scale_reference')
    for sign in [-1,1]:
        line(c,f'Human_Leg_{sign}',[at(0,0,.4),at(sign*.13,0,.07/h)],.07,mat,kind='scale_reference')
        line(c,f'Human_Arm_{sign}',[at(0,0,.75),at(sign*.28,0,.43)],.055,mat,kind='scale_reference')
    # Low-poly head; no character detail.
    cylinder(c,'Human_Head',base[0],.22,.13,mat,base[1],base[2]+h-.13,kind='scale_reference')
