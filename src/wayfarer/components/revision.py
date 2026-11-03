"""Canon-alignment proxy recipes. Mechanism dimensions remain prototype studies."""
import math
import bpy
from common import empty, material, mesh, cylinder, cylinder_mesh, annulus, line, ring, link_instance, cut, loft
from spec import derived, station_x, RADIATOR_STATES
from thermal_geometry import root_construction, local_to_ship, supports, stations as blade_stations, blade_of, root_band, bay_joints, mounts, mount_block_box, cell_span, joint_shoes, datum_lugs, seam_width, chase_radius, TRUNK_RADIUS_M, FEED_TRUNK_V, FEED_TRUNK_Z, FRAME_R, CHORD_R, DIAG_R, POST_R
import rotor as rotor_parts
import rotor_interface
import habitat_ring
import layout
import drive_manifold
import radiator_health as rh
import warm_panels
import radiator_zones
import crew as crew_parts
import crew_transfer
import human_entry
from mathutils import Matrix


def radial(x,r,a):
    return (x,r*math.cos(a),r*math.sin(a))


def sector(c,s):
    """WF_RING_SECTOR: the pressure skin of one ring sector in the sector frame (origin on the centreline at the deck, +X axial, +Y
    radially outward, +Z tangential), opened under the crew tube by the overhead hatch's clear bore, and the HUM-001 zone 5 landing (hatch
    frame, sliding leaf, ladder, chase, panel and lights), the same in every sector. The interior components are separate libraries; the
    frame and fills live in WF_HABITAT."""
    vs,fs=habitat_ring.sector_skin(s);L=human_entry.landing(s)
    obj=mesh(c,'Sector_Pressure_Envelope',vs,fs,material('Habitat',(.68,.77,.73)),kind='sector_pressure')
    obj=cut(obj,[((L['x'],L['tip_y']-.2,L['z']),(L['x'],L['seat']-.05,L['z']),L['clear_r'])])
    if 'ring_circulation' in s:
        # CIRC-001: a pressure-door opening in each side wall at the through-passage band (ring_circulation.sector_door_cutters).
        import ring_circulation
        obj=cut(obj,ring_circulation.sector_door_cutters(s));obj['circulation_doors']=2
    obj['rule_ref']='pressurized_ring_rule';obj['geometry_status']='PROTOTYPE';obj['gross_m3']=habitat_ring.sector_gross_m3(s)
    obj['cavity_m3']=habitat_ring.cavity_m3(s);obj['skin_m']=s['habitat_ring']['sector_skin_m'];obj['clear_radius_m']=L['clear_r']
    obj['geometry_basis']=('PROTOTYPE sector arc solved from the gross-volume target; the pressure rule (400-460 m3 gross across occupied sectors) is BASELINE. '
                           'HUM-001 zone 5: a skin inside the envelope (gross molded to its outer face), opened under the crew tube')
    crew_parts.fixtures(c,s,human_entry.landing_fixtures(s))
    import fitout
    fitout.landing(c,s)                # IND-001 3.1: the landing's fit-out (ARCHITECTURE layer, kind route_fitout)
    r=s['habitat_ring']
    empty(c,'IF_SECTOR_FLOOR',(0,0,0))
    empty(c,'IF_SECTOR_OVERHEAD',(0,r['sector_inner_radius_m']-habitat_ring.floor(s),0))
    empty(c,'IF_SECTOR_AFT_BULKHEAD',(-r['sector_axial_m']/2,(r['sector_inner_radius_m']-habitat_ring.floor(s))/2,0))   # aft bulkhead, halfway between deck and overhead


def box(c,name,lo,hi,mat,kind='geometry'):
    """Axis-aligned cuboid mesh (blade-local axes) between corners lo and hi."""
    vs=[(x,y,z) for x in (lo[0],hi[0]) for y in (lo[1],hi[1]) for z in (lo[2],hi[2])]
    fs=[(0,1,3,2),(4,6,7,5),(0,4,5,1),(2,3,7,6),(0,2,6,4),(1,5,7,3)]
    return mesh(c,name,vs,fs,mat,kind=kind)


def radiator(c,s):
    p=s['prototype'];g=s['radiators']['geometry'];d=derived(s)
    length=d['blade_length_m'];width=d['ribbon_width_m'];n=d['ribbons']
    nx=p['radiator_longitudinal_cells'];ny=p['radiator_transverse_cells']//n
    metal=material('Structure',(.30,.40,.48));lock=material('Locks',(.69,.45,.16))
    # Phase 4 S5: the transverse frames and edge chords carry their own display material (same review colour), so the exterior grammar
    # can give the blade's frame rhythm a light value over the dark sheet ([production.exterior] ship_families); no geometry change.
    frame=material('BladeFrame',(.30,.40,.48))
    half=g['truss_depth_m']/2
    band=root_band(s);blade=blade_of(s);joints=bay_joints(s,blade)
    seam=material('ExpansionJoint',(.93,.93,.80));bellows=material('TrunkBellows',(.55,.95,.15))
    for ribbon in range(n):
        v0=ribbon*(width+d['gap_m']);v1=v0+width
        for j in range(nx):
            x0,x1=cell_span(s,blade,j)     # AFT-009: the cells stop at the edges of each 0.125 m non-emitting bay joint
            for k in range(ny):
                y0=v0+width*k/ny;y1=v0+width*(k+1)/ny
                # The innermost cell row(s) along the root edge are the hot/cold root transition band (R6; the only zone where a
                # variable-emissivity surface is permitted, 40_THERMAL A57). The cell stays a radiating sheet: its planform still counts.
                zone='ROOT_TRANSITION' if ribbon==0 and k<band['rows'] else 'HOT_FACE'
                tint=material('RadiatorRoot',(.62,.30,.70)) if zone=='ROOT_TRANSITION' else material('RadiatorA' if (j+k)%2 else 'RadiatorB',(.11,.23,.29) if (j+k)%2 else (.14,.28,.34))
                obj=mesh(c,f'Blade_Cell_{ribbon}_{j:02}_{k:02}',[(x0,y0,0),(x1,y0,0),(x1,y1,0),(x0,y1,0)],[(0,1,2,3)],tint,kind='radiator_cell')
                obj['planform_m2']=(x1-x0)*(y1-y0);obj['structural_bay']=j//(nx//g['major_bays'])
                obj['thermal_cell_id']=f'R{ribbon}.CELL.{j:02}.{k:02}'
                obj['thermal_zone']=zone;obj['variable_emissivity_permitted']=zone=='ROOT_TRANSITION'
                obj['isolatable']=True;obj['isolation_group']=obj['thermal_cell_id']
                mod=obj.modifiers.new('Editable_Prototype_Thickness','SOLIDIFY');mod.thickness=p['radiator_thickness_m'];mod.offset=0
        for j in range(g['major_bays']+1):
            x=-length/2+length*j/g['major_bays']
            for z in [-half,half]:
                line(c,f'Blade_Frame_{ribbon}_{j}_{z}',[(x,v0,z),(x,v1,z)],FRAME_R,frame)
            for edge,v in enumerate([v0,v1]):
                line(c,f'Blade_Depth_{ribbon}_{j}_{edge}',[(x,v,-half),(x,v,half)],FRAME_R,metal)
            if j==g['major_bays']:continue
            x2=-length/2+length*(j+1)/g['major_bays']
            for edge,v in enumerate([v0,v1]):
                for z in [-half,half]:
                    line(c,f'Blade_Chord_{ribbon}_{j}_{edge}_{z}',[(x,v,z),(x2,v,z)],CHORD_R,frame)
                line(c,f'Blade_Diagonal_{ribbon}_{j}_{edge}',[(x,v,-half),(x2,v,half)],DIAG_R,metal)
            line(c,f'Blade_PlaneBrace_{ribbon}_{j}',[(x,v0,-half),(x2,v1,-half)],.075,metal)
        line(c,f'Forward_Leading_Spar_{ribbon}',[(length/2,v0,0),(length/2,v1,0)],p['radiator_leading_spar_radius_m'],lock,kind='leading_edge_proxy')
        # AFT-009 (Q16): feed trunk A on the +z side, return trunk B on the -z side, each with its own bellows at every joint.
        for name,zt in (('Coolant_Trunk',FEED_TRUNK_Z),('Coolant_Return_Trunk',-FEED_TRUNK_Z)):
            line(c,f'{name}_{ribbon}',[(-length/2,v0+FEED_TRUNK_V,zt),(length/2,v0+FEED_TRUNK_V,zt)],TRUNK_RADIUS_M,material('Coolant',(.15,.43,.51)),kind='coolant_proxy')
        # R6/MEC-013 expansion joints (AFT-009, Q13): a seam_width non-emitting gap across the sheet with a bead in it, and a bellows on each
        # trunk at every interior bay boundary. The truss chords run unbroken through them (07!A37); actual growth is OPEN (OD-007).
        for jt in joints:
            b=jt['index']
            obj=line(c,f'Blade_Expansion_Joint_{ribbon}_{b}',[(jt['u'],v0,0),(jt['u'],v1,0)],p['radiator_expansion_joint_radius_m'],seam,kind='expansion_joint')
            obj['planform_m2']=0.0;obj['joint_u']=jt['u'];obj['bay_boundary']=b;obj['gap_m']=seam_width(s);obj['emitting']=False
            obj['gap_status']='WORKING width (Q13, 07!A42); actual growth OPEN (OD-007)';obj['source_ref']='radiator_joint_width'
            for name,zt in (('Coolant_Trunk_Bellows',FEED_TRUNK_Z),('Coolant_Return_Bellows',-FEED_TRUNK_Z)):
                obj=line(c,f'{name}_{ribbon}_{b}',[(jt['u']-p['coolant_trunk_bellows_length_m']/2,v0+FEED_TRUNK_V,zt),(jt['u']+p['coolant_trunk_bellows_length_m']/2,v0+FEED_TRUNK_V,zt)],p['coolant_trunk_bellows_radius_m'],bellows,kind='expansion_joint')
                obj['planform_m2']=0.0;obj['joint_u']=jt['u'];obj['bay_boundary']=b;obj['source_ref']='radiator_coolant_chases'
    # Root stations attach to the innermost longitudinal chord; no hull-length clipping.
    for sign in [-1,1]:
        xr=d['mount_x_m']+sign*g['root_station_separation_m']/2
        u=(xr-d['center_x_m'])/d['cos']
        line(c,f'Blade_Root_Post_{sign}',[(u,0,-half),(u,0,half)],POST_R,metal,kind='deployed_lock')
        empty(c,f'IF_PETAL_ROOT_{sign}',(u,0,0))
    empty(c,'IF_PETAL_ROOT')
    # R6 mounts (AFT-009, Q12/Q15): the aft root boom is the one fixed datum, carried by its block and two lugs on the root post; the forward
    # root and every stay carry the blade radially and tangentially but slide axially on a rail of the block plus the WORKING 0.20 m local
    # travel; guided shoes across each bay joint carry the same travel. Actual growth is OPEN (OD-007).
    # Owner 2026-10-17 (S&E 15!A202 OWN-M4, m2; Art Style Bible Spacecraft!A16): the hardware reads in structural greys; red (datum) and
    # yellow (slide) are a non-diegetic review legend only (Godot inspector L), never paint. The material names carry the role.
    datum_mat=material('MountDatum',(.15,.16,.18));slide_mat=material('MountSlide',(.30,.32,.34))
    travel=s['radiators']['thermal_expansion']['distributed_compliance']['local_travel_m']
    for m in mounts(s,blade):
        fixed=m['role']=='FIXED_DATUM'
        obj=box(c,m['name'],*mount_block_box(m['u'],p['radiator_mount_block_m']),datum_mat if fixed else slide_mat,kind='thermal_mount')
        if not fixed:
            rail=line(c,m['name']+'_Rail',[(m['u']-p['radiator_mount_slot_length_m']/2,0,0),(m['u']+p['radiator_mount_slot_length_m']/2,0,0)],.10,slide_mat,kind='thermal_mount')
            rail['mount_role']=m['role'];rail['source_ref']='radiator_local_travel';rail['local_travel_m']=travel
        obj['mount_role']=m['role'];obj['mount_station']=m['station'];obj['lever_arm_m']=m['lever_arm_m']
        obj['travel_allowance']='OPEN (R6): actual growth; WORKING local travel %.2f m per station (Q12)'%travel if not fixed else 'OPEN (R6): datum, no travel'
        obj['source_ref']='radiator_axial_datum' if fixed else 'radiator_local_travel'
        obj['geometry_basis']='PROTOTYPE block; one axial datum with redundant lugs (Q15)' if fixed else 'PROTOTYPE block on a rail of block + local travel (Q12)'
        if fixed:
            empty(c,'IF_BLADE_FIXED_DATUM',(m['u'],0,0))['geometry_basis']='Single fixed axial/radial/tangential datum of the blade (PROTOTYPE selection), carried by redundant lugs (Q15)'
    lu,lv,lz=p['radiator_datum_lug_m']
    for g_ in datum_lugs(s,blade):
        obj=box(c,g_['name'],(g_['u']-lu/2,g_['v']-lv/2,g_['z']-lz/2),(g_['u']+lu/2,g_['v']+lv/2,g_['z']+lz/2),datum_mat,kind='datum_lug')
        obj['mount_role']='FIXED_DATUM_LUG';obj['source_ref']='radiator_axial_datum';obj['geometry_basis']='PROTOTYPE redundant load lug of the one datum (Q15); member sizes are FEA outputs (OPEN)'
    # M4 slice 2 (radiators.root_construction, PROTOTYPE): a saddle cradle under each root post on its boom and two hard stops at the ends
    # of every slide rail (inner faces at the slot ends: the 0.20 m local travel). All off the emitting sheet and the root band.
    steel=material('RootSteel',(.22,.25,.28))
    for q in (q for q in root_construction(s,blade) if q['kind']!='casing_boot'):
        obj=mesh(c,q['name'],q['vertices'],q['faces'],steel,kind=q['kind']);obj['geometry_status']='PROTOTYPE';obj['source_ref']='radiators.root_construction'
        if q['kind']=='slide_stop':obj['mount']=q['mount'];obj['local_travel_m']=travel
    su,sv,sz=p['radiator_joint_shoe_m']
    for g_ in joint_shoes(s,blade):
        obj=box(c,g_['name'],(g_['u']-su/2,g_['v']-sv/2,-sz/2),(g_['u']+su/2,g_['v']+sv/2,sz/2),slide_mat,kind='joint_shoe')
        obj['mount_role']='JOINT_SLIDE';obj['bay_boundary']=g_['bay_boundary'];obj['local_travel_m']=travel;obj['source_ref']='radiator_local_travel'
        obj['geometry_basis']='PROTOTYPE guided sliding shoe across the joint; WORKING local travel (Q12), actual growth OPEN (OD-007)'


def structure(c,s):
    p=s['prototype'];st=s['structure'];length=s['ship']['length']['value']
    metal=material('Structure',(.30,.40,.48));gold=material('Locks',(.69,.45,.16))
    xring=layout.at(s,p['thrust_ring_x']);phase=math.radians(p['ring_phase_deg'])
    nodes=st['ring_nodes'];strut=p['structural_strut_radius_m'];node_r=st['ring_node_radius_m'];half=st['ring_depth_m']/2
    outer=st['ring_od_m']/2;inner=outer-st['ring_radial_depth_m']
    sectors=[phase+n*math.tau/nodes for n in st['sector_pickup_nodes']]
    # Deep annular truss: section spans radii 5..6, with nodes at 5.5.
    for face in [-1,1]:
        xx=xring+face*half
        for rr in [outer,inner]:
            ring(c,f'Thrust_Ring_{face}_{rr}',xx,rr-strut if rr==outer else rr+strut,strut,metal)
    for j in range(nodes):
        a=phase+j*math.tau/nodes;xyz=radial(xring,node_r,a)
        node=empty(c,f'IF_THRUST_NODE_{j:02}',xyz);node['node_index']=j
        cylinder(c,f'Thrust_Node_{j:02}',xring,st['ring_depth_m'],.20,gold,xyz[1],xyz[2],kind='thrust_node')
        line(c,f'Ring_Web_{j}',[radial(xring-half,inner+strut,a),radial(xring+half,outer-strut,a+math.tau/nodes)],.12,metal)
        # S04 slice 4 (PROTOTYPE judgment, M4 grammar): a node diaphragm plate fills the ring section in the node's radial plane, between
        # the chords, so the thrust ring reads as jointed and the aft RCS pods and comms booms bear on a plate, not a bare tube.
        tw=s['prototype']['thrust_node_plate_m']/2;cs,sn=math.cos(a),math.sin(a);vs=[]
        for xx in (xring-half+strut,xring+half-strut):
            for rr in (inner+strut,outer-strut):
                for w in (-tw,tw):vs.append((xx,rr*cs-w*sn,rr*sn+w*cs))
        plate=mesh(c,f'Thrust_Node_Plate_{j:02}',vs,[(0,2,3,1),(4,5,7,6),(0,1,5,4),(2,6,7,3),(0,4,6,2),(1,3,7,5)],metal,kind='thrust_node_plate')
        plate['geometry_status']='PROTOTYPE';plate['role']='node diaphragm of the thrust ring (load into the node from the aft pods and comms booms); sizing OPEN'
    # S04 slice 6 (PROTOTYPE judgment): the ring is assembled from twelve bay segments; a bolted splice sleeve on each of the four chords
    # at mid-bay marks the assembly division (one mesh per bay).
    sl,sw=p['thrust_splice_m']
    for j in range(nodes):
        a=phase+(j+.5)*math.tau/nodes;da=sl/2/node_r;vs,fs=[],[]
        for xx in (xring-half,xring+half):
            for rr in (outer-strut,inner+strut):
                v,f=cylinder_mesh(radial(xx,rr,a-da*node_r/rr),radial(xx,rr,a+da*node_r/rr),strut+sw,16);n=len(vs);vs+=v;fs+=[tuple(i+n for i in q) for q in f]
        sp=mesh(c,f'Thrust_Ring_Splice_{j:02}',vs,fs,metal,kind='thrust_node_plate')
        sp['geometry_status']='PROTOTYPE';sp['role']='bolted chord splice: thrust-ring bay segment joint (assembly division); sizing OPEN'
    annulus(c,'Central_Thrust_Hub',xring,1.6,st['hub_diameter_m']/2,p['spine_radius_m']+.03,metal)
    empty(c,'IF_THRUST_RING_CENTER',(xring,0,0))['geometry_basis']='Aft thrust ring plane on the ship axis; load-path reference'
    for j,n in enumerate(st['nozzle_pickup_nodes']):
        a=phase+n*math.tau/nodes
        line(c,f'Hub_Web_{j}',[radial(xring,st['hub_diameter_m']/2,a),radial(xring,node_r,a)],.15,metal)
    for q in drive_manifold.nozzle_pickups(s):
        obj=line(c,q['name'],[q['a'],q['b']],q['radius'],gold)
        obj['attach_yoke']=f"Nozzle_Yoke_{q['nozzle']}_{q['yoke']}";obj['geometry_basis']=q['geometry_basis']
    # End the fixed outer cage before the rotor sweep region.
    xs=[xring+t for t in st['transition_frame_offsets_m']]
    xx=xs[-1]+st['frame_spacing_m']
    cage_end=layout.at(s,p['outer_cage_end_x'])
    while xx<cage_end:
        xs.append(xx);xx+=st['frame_spacing_m']
    xs.append(cage_end)
    # Frames also exist at every root boom and bay stay station (thermal_geometry.stations), shared with the hull cage points.
    at=blade_stations(s,blade_of(s))
    xs=sorted(set(xs+at['roots']+at['stays']))
    for n,xx in enumerate(xs):
        rr=node_r if n==0 else st['sector_radius_m']
        # Transverse ring avoids routing a solid triangular chord through machinery.
        ring(c,f'Primary_Frame_{n:02}',xx,rr,strut,metal)
        for j,a in enumerate(sectors):
            empty(c,f'IF_SECTOR_{j}_{n}',radial(xx,rr,a))
        if n:
            prev=xs[n-1];rp=node_r if n==1 else st['sector_radius_m']
            for j,a in enumerate(sectors):
                line(c,f'Primary_Rail_{n}_{j}',[radial(prev,rp,a),radial(xx,rr,a)],p['structural_rail_radius_m'],metal)
                # Bracing follows two tangential segments around the machinery envelope.
                points=[radial(prev+(xx-prev)*k/8,rp+(rr-rp)*k/8,a+math.tau/3*k/8) for k in range(9)]
                line(c,f'Primary_XBrace_{n}_{j}',points,.075,metal)
    # Spine runs from the terminated hub on the shield bulkhead to the forward inset, via drive_manifold.spine_span (06!A47, 15!A72).
    aft,fwd=drive_manifold.spine_span(s)
    # HUM-001 zone 2: the forward spine core (layout.spine_core) carries the crew trunk; a cone joins it to the aft spine.
    x_core,x_cone,r_core=layout.spine_core(s)
    spine=loft(c,'Structural_Spine',[(aft,p['spine_radius_m']),(x_cone,p['spine_radius_m']),(x_core,r_core),(fwd,r_core)],metal)
    # HUM-001 zone 2: the crew trunk fills the spine bore over its span, and each boarding port's 1.6 m branch opens through the spine wall.
    cut(spine,crew_transfer.bores(s)['Structural_Spine'])
    # Thin body-limit annotation at the maximum-envelope station; not a pressure hull or structural rail.
    ring(c,'Body_Envelope_Reference',station_x(s,'WF.STATION.SERVICES'),s['ship']['body_diameter']['value']/2-.04,.04,material('Envelope',(.23,.30,.34)),kind='hull_envelope')
    cylinder(c,'Engineering_Envelope',layout.at(s,p['engineering_center_x']),p['engineering_length_m'],p['engineering_radius_m'],material('Engineering',(.25,.36,.39)))
    # Exposed pair of Brayton proxies just forward of machinery; sizes are local choices.
    for j,yy in enumerate([-p['brayton_offset_y_m'],p['brayton_offset_y_m']]):
        cylinder(c,f'Brayton_Train_{j+1}',layout.at(s,p['brayton_center_x']),p['brayton_length_m'],p['brayton_radius_m'],material('Generator',(.62,.48,.25)),yy,0,kind='generator_proxy')
        empty(c,f'IF_POWER_BUS_{s["power"]["bus_names"][j]}',(layout.at(s,p['power_bus_x']),yy,0))
    for j,xx in enumerate(habitat_ring.centers(s)):
        # P1-008: the hub mechanisms themselves live in WF_ROTOR_INTERFACE (stationary) and the habitat files (rotating).
        empty(c,f'IF_ROTOR_BEARING_{j+1}',(xx,0,0))
        empty(c,f'IF_ROTOR_TRANSFER_{j+1}',(xx,0,0))['engineering_status']='OPEN OD-002: rotary vestibule per rotor is WORKING (I5); P1-008 PROTOTYPE hub mechanisms in WF_ROTOR_INTERFACE; sizing, crew vestibule and fluid circuits not designed'
    for j,a in enumerate(sectors):
        line(c,f'Forward_Mount_Strut_{j}',[radial(layout.at(s,p['forward_mount_aft_x']),p['forward_mount_inner_radius_m'],a),radial(layout.at(s,p['forward_mount_fwd_x']),p['forward_mount_outer_radius_m'],a)],strut,metal)


RINGS=('HABITAT_A','HABITAT_B')      # one engineering asset per ring (docs/MODULES.md): ring j is RINGS[j-1], linked by WF_HABITAT


def habitat(c,s,assets):
    """WF_HABITAT, the habitat assembly: the two ring assets linked at the ship origin (their own frames are the vehicle frame) and the
    whole-habitat rotor actions, whose slots name both rings' controls. It holds no geometry of its own; the vehicle links it once."""
    bpy.context.scene.render.fps=24
    bpy.context.scene.frame_start=1;bpy.context.scene.frame_end=361
    for j,name in enumerate(RINGS,1):
        obj=link_instance(c,assets/f'subsystems/WF_{name}.blend',f'WF_{name}',f'Habitat_Ring_{j}',ident=f'WF.HABITAT.RING.{j}')
        obj['kind']='ring_assembly';obj['ring']=j
    rotor_parts.actions(s)
    bpy.context.scene['configuration']=s['vehicle']['saved_preset']
    bpy.context.scene.frame_set(1)


def ring_asset(c,s,assets,j):
    """WF_HABITAT_<A|B>: rigid ring j at full size with its frame, fills, spokes, pressurized sectors, hub, crew parts and its rotor's
    mechanism control. The rotation driver reads ROTOR_j_MECH_CTRL['spin_fraction'], so a preset (ring_spin) decides whether the ring
    turns or sits at its index angle."""
    p=s['prototype'];h=s['habitat'];hr=s['habitat_ring']
    metal=material('HabitatArms',(.46,.57,.63));fill=material('RingFill',(.34,.50,.55));hub=s['rotor_interface']
    construction=dict(frame=metal,joint=material('RingJoint',(.16,.19,.22)),band=material('RingPressureBand',(.72,.52,.22)),index=material('RingSpinIndex',(.05,.05,.06)),cassette=fill,
                      cover=material('RingCover',(.44,.56,.60)),service=material('RingService',(.30,.26,.16)),service_cover=material('RingServiceCover',(.78,.60,.24)),portal=material('RingPortalCollar',(.36,.40,.44)))
    bpy.context.scene.render.fps=24
    bpy.context.scene.frame_start=1;bpy.context.scene.frame_end=361
    # The control comes first: the rotation driver targets it. The saved pose is the vehicle's saved preset (spin 1).
    controls=rotor_parts.controls(c,s,j)
    for rotor,xx in [(j-1,habitat_ring.centers(s)[j-1])]:      # this asset's ring only (it was one loop over both rings)
        parent=empty(c,f'Rotor_{j}',(xx,0,0),ident=f'WF.ROTOR.{j}',kind='rotor')
        phase=math.radians(p['rotor_phase_deg'][rotor]);sign=1 if rotor==0 else -1
        parent['rpm']=sign*h['rpm']
        parent['saved_preset']=s['vehicle']['saved_preset']
        # Frame 1 is the index angle (phase) in every preset (spin_integrated 0): at spin 1 the ring turns at the nominal rate, at 0 it
        # stays at phase. FUT-007: with spin_integrated 1 (the rotor actions, the flight timeline) the ring turns by spin_turned, the
        # integral of spin (rotor_interface.spin_turned), so a spin ramp slows it to rest at its index angle without reversing.
        # PROTOTYPE display driver, not a control law.
        driver=parent.driver_add('rotation_euler',0).driver
        for name,prop in (('spin','spin_fraction'),('turned','spin_turned'),('integ','spin_integrated')):
            var=driver.variables.new();var.name=name;var.type='SINGLE_PROP'
            var.targets[0].id=controls[rotor_interface.control(j)];var.targets[0].data_path=f'["{prop}"]'
        driver.expression=f'{phase!r}+{sign*h["rpm"]*math.tau/60/24!r}*(integ*turned+(1-integ)*spin*(frame-1))'
        # P1-008 rotating hub: drum and the rotating half of each mechanism, in the rotor frame.
        rotor_parts.hub(c,s,parent,j)
        # P1-001 PROTOTYPE crew route: vestibule and struts, plus the crew tubes.
        crew_parts.hub(c,s,parent,j)
        # FGR-003 ring frame: hoops and the fills between the sectors (water/storage/structure), PROTOTYPE display geometry.
        # M4 slice 1: each part carries its PROTOTYPE construction (segments, webs, cassettes, service nodes, pressure-segment band) inside its own band.
        for q in (q for q in habitat_ring.frame_parts(s) if q['ring']==j):
            vs,fs,cls=habitat_ring.frame_mesh(s,q)
            obj=mesh(c,q['name'],vs,fs,metal,kind=q['kind'])
            used=sorted(set(cls),key=list(construction).index)
            for k in used[1:]:obj.data.materials.append(construction[k])
            obj.data.materials[0]=construction[used[0]]
            obj.data.polygons.foreach_set('material_index',[used.index(k) for k in cls])
            if q['name']==f'Ring_{j}_Hoop_Inner' and crew_transfer.hoop_cuts(s,j):
                # HUM-001 zone 5: the hollow crew tubes pass through the inner hoop into their sectors (framed openings OPEN).
                obj=cut(obj,crew_transfer.hoop_cuts(s,j));obj['crew_openings']=len(crew_transfer.hoop_cuts(s,j))
            obj.parent=parent
            obj['evidence_ref']='ring_architecture';obj['rule_ref']='ring_shielding'
            obj['geometry_basis']='PROTOTYPE display frame; section, spokes and sizing are OPEN (08!A53, OD-016)';obj['geometry_status']='PROTOTYPE'
        if 'ring_circulation' in s:
            # CIRC-001: the walking corridors through the fills, their portals and pressure doors (components/circulation.py).
            import circulation
            circulation.ring(c,s,parent,j)
        # Twin spoke rails per spoke join the hub drum to the frame; the three on the sector angles carry the crew tubes.
        for q in (q for q in habitat_ring.spokes(s) if q['ring']==j):
            rail=line(c,q['name'],[radial(q['u'],q['r0'],q['angle']),radial(q['u'],q['r1'],q['angle'])],q['radius'],metal,kind='ring_spoke');rail.parent=parent
            rail['crew_spoke']=q['crew'];rail['evidence_ref']='rigid_ring_structure_open';rail['geometry_status']='PROTOTYPE'
        # Pressurized sectors sit on the deck radius, recessed in the frame; the floor is radially outward (no room turns).
        for q in (q for q in habitat_ring.sectors(s) if q['ring']==j):
            k=q['index']
            obj=link_instance(c,assets/'components/WF_RING_SECTOR.blend','WF_RING_SECTOR',q['name'],radial(0,q['deck_radius'],q['angle']),q['angle'],ident=q['ident'])
            obj.parent=parent;obj['kind']='ring_sector';obj['canon_status']='BASELINE';obj['geometry_status']='PROTOTYPE';obj['source_ref']='pressurized_ring_rule'
            obj['floor_direction']='RADIAL_OUTWARD'
            # PROTOTYPE assignment: one sector of each function per ring keeps each ring autonomous (12_HABITAT_LAYOUT I5).
            obj['function']=q['function'];obj['function_source']='habitat_layout'
            # P1-004 rough interior for that function, in the sector frame so it follows the ring rotation.
            component='WF_'+s['interior']['components'][obj['function']]
            room=link_instance(c,assets/f'components/{component}.blend',component,f'Interior_{j}_{k}',ident=f"{q['ident']}.INTERIOR")
            room.parent=obj;room['kind']='sector_interior';room['function']=obj['function'];room['rooms_status']='OPEN (habitat.layout.rooms)'
            mount=empty(c,f'IF_SECTOR_{j}_{k}',radial(0,q['r0'],q['angle']));mount.parent=parent
            # Production detail on a sector (M7.RA1 and later packs) is its own detail asset, linked here by build.detail.attach at the
            # anchor WF-RING-<A|B>.SECTOR.<ring>.<sector> (docs/MODULES.md); the shared components stay without it.
    bpy.context.scene['configuration']=s['vehicle']['saved_preset']
    bpy.context.scene.frame_set(1)


def shielding(c,s):
    p=s['prototype']
    obj=cylinder(c,'Reactor_Shadow_Shield_Envelope',layout.at(s,p['shadow_center_x']),p['shadow_thickness_m'],p['shadow_radius_m'],material('Shield',(.48,.43,.28)))
    sub=s['physics']['mass_suballocations'];obj['mass_known']=False;obj['com_contribution']='unknown (not zero)';obj['mass_suballocation']='reactor_shadow_shield (P5/P6, non-additive, 10!A24)';obj['mass_source_ref']=sub['source_ref']


def health_driver(target,path,index,expression,control):
    """Simple-expression driver on a health overlay, reading RADIATOR_HEALTH_CTRL. rh.drivers() defines every expression."""
    fc=target.driver_add(path) if index==-1 else target.driver_add(path,index)
    fc.driver.type='SCRIPTED';fc.driver.expression=expression
    for var in rh.expression_variables(expression):
        v=fc.driver.variables.new();v.name=var;v.type='SINGLE_PROP'
        v.targets[0].id_type='OBJECT';v.targets[0].id=control;v.targets[0].data_path=f'["{rh.VARIABLES[var]}"]'
    if not fc.driver.is_simple_expression:
        raise ValueError(f'{target.name}.{path}: driver is not a simple expression: {expression}')
    target['radiator_driven']=True
    return fc


def radiator_health(c,s,parents):
    """AFT-005 display overlays on the fixed blades (blade-local, parented to the Radiator_0n instance) and RADIATOR_HEALTH_CTRL with its drivers.
    Everything is display only: zero planform, no thermal zone, no emissivity change, saved hidden or neutral."""
    t=s['radiator_health'];disp=t['display'];geo=rh.overlay_geometry(s)
    # Fixed materials only: no shader reads driven object colour (Cycles returns the instancer's colour for collection-instanced objects).
    glow_mats={k:material(f'RadiatorGlowStep{k}',tuple(disp['step_glow_rgba'][k][:3]),disp['step_glow_emission'][k],disp['step_glow_rgba'][k][3]) for k in rh.glow_steps(s)}
    iso_mat=material('RadiatorCellIsolated',tuple(disp['isolated_rgb']))
    rep_mat=material('RadiatorCellResurfaced',tuple(disp['resurfaced_rgb']),disp['resurfaced_emission'])
    def flags(obj,source,kind_basis):
        obj.hide_viewport=obj.hide_render=True
        obj['planform_m2']=0.0;obj['display_only']=True;obj['emissivity_change']=False;obj['variable_emissivity_permitted']=False
        obj['canon_status']='BASELINE';obj['source_ref']=source;obj['geometry_status']='PROTOTYPE';obj['display_status']='IMPLEMENTATION'
        obj['geometry_basis']=kind_basis
    for blade,parent in enumerate(parents):
        vs,fs=geo['glow']
        for step in rh.glow_steps(s):
            obj=mesh(c,rh.glow_name(blade,step),vs,fs,glow_mats[step],ident=f'WF.THERMAL.GLOW.{blade+1:02}.{step}',kind='radiator_thermal_glow')
            obj.parent=parent;flags(obj,'radiator_operations','Display colour for one thermal-state step; not a temperature, emissivity or flux. Hot face only; the root band never glows.')
            obj['blade']=blade+1;obj['glow_step']=rh.steps(s)[step]
    for cell in rh.cells(s):
        for resurfaced in (False,True):
            vs,fs=(geo['resurfaced'] if resurfaced else geo['markers'])[(cell['ribbon'],cell['j'],cell['k'])]
            name=cell['resurfaced_name'] if resurfaced else cell['name']
            obj=mesh(c,name,vs,fs,rep_mat if resurfaced else iso_mat,ident=f"WF.THERMAL.HEALTH.{cell['blade']+1:02}.{cell['thermal_cell_id']}"+('.R' if resurfaced else ''),kind='radiator_health_marker')
            obj.parent=parents[cell['blade']]
            flags(obj,'radiator_cell_isolation','Display marker of one isolatable thermal cell; the cell count and the isolation order are PROTOTYPE (40!A26 gives no count, OD-010 OPEN).')
            obj['thermal_cell_id']=cell['thermal_cell_id'];obj['blade']=cell['blade']+1;obj['cell_rank']=cell['rank'];obj['marker_state']='RESURFACED' if resurfaced else 'ISOLATED'
    d=derived(s)
    ctrl=empty(c,rh.CONTROL,(d['center_x_m'],0.0,-(s['radiators']['root_radius']['value']+2.0)),ident='WF.THERMAL.HEALTH_CONTROL',kind='state_control')
    ctrl.empty_display_type='CUBE';ctrl.empty_display_size=.6
    for key,value in rh.neutral(s).items():
        ctrl[key]=float(value)
        ctrl.id_properties_ui(key).update(min=0.0,max=1.0,soft_min=0.0,soft_max=1.0,description=rh.PROPS[key])
        ctrl.property_overridable_library_set(f'["{key}"]',True)
    ctrl['units']=t['controls']['unit']+'; no temperature, emissivity or flux'
    ctrl['state']='NEUTRAL (all controls 0); configurations are posed in memory'
    ctrl['engineering_status']='OPEN: degraded-mode matrix (OD-010), repair rates and the interim derate of resurfaced cells (Q42); PROTOTYPE: 480-cell grid, fault order and per-configuration thermal_state; display only, the physical radiator area is unchanged'
    ctrl['canon_status']='IMPLEMENTATION'
    objects={o.name:o for o in c.objects}
    for name,path,index,expression in rh.drivers(s):
        health_driver(objects[name],path,index,expression,ctrl)


def thermal(c,s,assets):
    p=s['prototype'];g=s['radiators']['geometry'];d=derived(s)
    mats={'root_boom':material('Structure',(.30,.40,.48)),'thermal_support':material('Structure',(.30,.40,.48)),'coolant_proxy':material('Coolant',(.15,.43,.51))}
    chase_mat=material('CoolantChase',(.55,.58,.62),alpha=.35)
    members=supports(s,d);instances=[]
    # Radiators are fixed in every mode (R1/R8, MEC-012): static blades, no state control, hinge or driver.
    for j in range(s['radiators']['count']):
        a=math.radians(p['radiator_phase_deg']+j*120)
        obj=link_instance(c,assets/'components/WF_RADIATOR.blend','WF_RADIATOR',f'Radiator_{j+1:02}',radial(d['center_x_m'],d['center_radius_m'],a),a,ident=f'WF.RADIATOR.{j+1:02}')
        obj.rotation_euler=(Matrix.Rotation(a,4,'X')@Matrix.Rotation(-math.radians(d['cant_deg']),4,'Z')).to_euler()
        # Production direction is BASELINE (07!A18, 15!A2 R1); blade geometry stays PROTOTYPE (15_MODEL_INTERFACES R4).
        instances.append(obj)
        obj['canon_status']='BASELINE';obj['source_ref']='radiator_production_direction';obj['operating_state']=next(iter(RADIATOR_STATES))
        # Thermal-architecture metadata (40_THERMAL A51:A59, WORKING; OD-023 OPEN): carried as properties, never as modelled layers.
        r=s['radiators']
        obj['nano_stack']=list(r['nano_stack']['layers']);obj['sensor_mesh']=list(r['sensor_mesh']['sensing'])
        obj['repair_doctrine']=list(r['repair_doctrine']['sequence']);obj['hot_face_repair_rule']=r['repair_doctrine']['hot_face_rule']
        obj['variable_emissivity_zones']=list(r['variable_emissivity_zoning']['permitted_model_zones'])
        obj['emissivity_root_baseline']=r['emissivity']['value'];obj['emissivity_nano_target']=[r['emissivity_target']['candidate_low'],r['emissivity_target']['candidate_high']]
        obj['expansion_allowance']='OPEN (R6, OD-007)';obj['angular_emission']='OPEN (OD-023)'
        obj['thermal_architecture']=list(r['thermal_expansion']['architecture'])
        # Root booms, bay stays and coolant feed come from thermal_geometry.supports, shared with hull openings.
        for m in (m for m in members if m['sector']==j):
            curve=line(c,m['name'],m.get('path') or [m['start'],m['end']],m['radius'],mats[m['kind']],kind=m['kind'])
            if 'mount_role' in m:curve['mount_role']=m['mount_role']
            if m['kind']=='root_boom':
                sign=int(m['name'].rsplit('_',1)[1])
                empty(c,f'IF_RAD_{j+1}_ROOT_{sign}',m['end']).rotation_euler.x=a
                empty(c,f'IF_RAD_{j+1}_HULL_{sign}',m['start'])['pairs_with']='WF_STRUCTURE IF_SECTOR_*'
            elif m['kind']=='thermal_support':
                empty(c,f'IF_RAD_{j+1}_STAY_{m["name"].rsplit("_",1)[1]}_HULL',m['start'])['pairs_with']='WF_STRUCTURE IF_SECTOR_*'
            elif m['kind']=='coolant_proxy':
                # Fixed blade: a rigid or flexible joint into the trunk is OPEN. AFT-009 (Q16): each line runs in its own protected chase (a
                # translucent sheath along every leg but the joint into the trunk), so it never passes through the post, boom or block.
                curve['loop_status']='PROTOTYPE U expansion loop (R6, MEC-013); span, rise and offset are display choices';curve['line']=m['line']
                pts=m['path'][:-1]
                sheath=line(c,m['name'].replace('Coolant_','Coolant_Chase_'),pts,chase_radius(s),chase_mat,kind='coolant_chase')
                sheath['line']=m['line'];sheath['source_ref']='radiator_coolant_chases';sheath['geometry_basis']='PROTOTYPE protected chase sheath (Q16); line size and routing PROTOTYPE (15!G65)'
                name='COOLANT_JOINT' if m['line']=='A' else 'RETURN_JOINT'
                empty(c,f'IF_RAD_{j+1}_{name}',m['end'])['engineering_status']='OPEN: coolant joint design (MEC-013 thermal expansion); the PROTOTYPE expansion loop is a display geometry and no motion crosses the joint'
    # M4 slice 2: a sealed boot (flange on the casing round its opening, sleeve round the member) where every boom, stay and coolant chase
    # leaves the service casing; the same blade-local parts in each sector's frame (radiators.root_construction, PROTOTYPE).
    boot=material('CasingBoot',(.80,.78,.72))
    for j in range(s['radiators']['count']):
        a=math.radians(p['radiator_phase_deg']+j*120)
        for q in (q for q in root_construction(s,d) if q['kind']=='casing_boot'):
            obj=mesh(c,q['name'].replace('Casing_Boot_',f'Casing_Boot_{j}_'),[local_to_ship(d,a,*v) for v in q['vertices']],q['faces'],boot,kind='casing_boot')
            obj['member_kind']=q['member'];obj['geometry_status']='PROTOTYPE';obj['source_ref']='radiators.root_construction'
            obj['engineering_status']='OPEN: boot material, sealing, MMOD and thermal function; the member slides free inside the sleeve'
    # AFT-005: thermal-state glow and cell-health markers over the fixed blades, driven by RADIATOR_HEALTH_CTRL (display only).
    radiator_health(c,s,instances)
    # RAD-ZONE / Graded Thermal Blade (owner briefs 2026-11-01): the thermal bulkhead, WARM and LOW sections ahead of the hot blade.
    if 'zones' in s['radiators']:
        radiator_zones_geometry(c,s)
    # Q38: candidate warm panels flanking the bypass-collar truss in each blade plane (removed 2026-11-01: enabled = false).
    import bmesh
    q=s['thermal']['loops']['candidate_panels'];warm=material('WarmPanel',(.42,.36,.30))
    for pnl in warm_panels.panels(s):
        obj=mesh(c,pnl['name'],pnl['corners'],pnl['faces'],warm,kind='warm_panel_candidate')
        bm=bmesh.new();bm.from_mesh(obj.data);bmesh.ops.recalc_face_normals(bm,faces=bm.faces);bm.to_mesh(obj.data);bm.free()
        obj['loop']='warm 450 K (Q38 candidate)';obj['evidence_ref']=q['evidence_ref'];obj['capacity']=q['capacity']
        obj['radiating_face_area_m2']=pnl['radiating_area_m2'];obj['radiating_normal']=list(pnl['normal'])
        obj['engineering_status']='OPEN: baffles, coolant routing via the collar aft spoke, temperature map and net balance against the blades (Q38, 40!F68)'
        for name,pts in pnl['brackets']:
            line(c,name,pts,q['bracket_radius_m'],mats['thermal_support'],kind='warm_panel_bracket')


def radiator_zones_geometry(c,s):
    """Graded Thermal Blade (owner briefs 2026-11-01): the WARM and LOW sheets ahead of the hot blade, one plate per blade plane with its
    own root booms and feed/return trunk, and one V-groove thermal bulkhead (three thin specular sheets, the forward two leaning forward
    with radius) at the hot blade front, carried on spokes along the blade planes and a rim ring per layer (radiator_zones, PROTOTYPE).
    The WARM aft edge follows the last layer (diagonal seam); the WARM/LOW joint is an open 0.5 m gap with no shield."""
    z=s['radiators']['zones'];bh=z['bulkhead'];p=s['prototype'];th=p['radiator_thickness_m'];casing=__import__('thermal_geometry').casing_radius(s)
    sheet={'LOW':(material('RadiatorZoneLowA',(.66,.84,.98)),material('RadiatorZoneLowB',(.60,.79,.95))),
           'WARM':(material('RadiatorZoneWarmA',(.96,.56,.18)),material('RadiatorZoneWarmB',(.90,.50,.14)))}
    metal=material('Structure',(.30,.40,.48));coolant=material('Coolant',(.15,.43,.51));strip=material('RadiatorZoneRootStrip',(.42,.44,.46));zone_frame=material('BladeFrame',(.30,.40,.48))
    layer_mat=[material('BulkheadHotLayer',(.62,.60,.58)),material('BulkheadMidLayer',(.74,.74,.72)),material('BulkheadColdLayer',(.86,.72,.36))]
    nx,nr=6,4
    for pl in radiator_zones.plates(s):
        a=pl['azimuth'];u=(0.0,math.cos(a),math.sin(a));n=(0.0,-math.sin(a),math.cos(a))
        P=lambda x,r,w:(x,r*u[1]+w*n[1],r*u[2]+w*n[2])
        r_c=radiator_zones.inner_radius_m(s)
        xa=(lambda r:radiator_zones.warm_aft_x(s,r)) if pl['section']=='WARM' else (lambda r:pl['x0'])
        for k in range(nr):
            r0=pl['r0']+(pl['r1']-pl['r0'])*k/nr;r1=pl['r0']+(pl['r1']-pl['r0'])*(k+1)/nr
            for i in range(nx):
                f0=i/nx;f1=(i+1)/nx
                X=lambda f,r:xa(r)+(pl['x1']-xa(r))*f
                vs=[P(X(f,r),r,w) for f in (f0,f1) for r in (r0,r1) for w in (-th/2,th/2)]
                fs=[(0,2,3,1),(4,5,7,6),(0,1,5,4),(2,6,7,3),(0,4,6,2),(1,3,7,5)]
                obj=mesh(c,f"{pl['name']}_Cell_{i}_{k}",vs,fs,sheet[pl['section']][(i+k)%2],kind='radiator_zone_cell')
                obj['radiator_section']=pl['section'];obj['temperature_K']=pl['T_K'];obj['circuit']=pl['circuit'];obj['coating']=pl['coating']
                obj['thermal_zone']=pl['section']
                obj['planform_m2']=0.5*((X(f1,r0)-X(f0,r0))+(X(f1,r1)-X(f0,r1)))*(r1-r0);obj['source_ref']='radiator_zoning'
                obj['engineering_status']='PROTOTYPE (Graded Thermal Blade); panel design, coolant and coating qualification OPEN'
        # root strip (0.5 m, non-emitting structure between the root boom line and the sheet)
        vs=[P(x,r,w) for x in (xa(pl['r_root']),pl['x1']) for r in (pl['r_root'],pl['r0']) for w in (-th/2,th/2)]
        obj=mesh(c,f"{pl['name']}_Root_Strip",vs,[(0,2,3,1),(4,5,7,6),(0,1,5,4),(2,6,7,3),(0,4,6,2),(1,3,7,5)],strip,kind='radiator_zone_support')
        obj['function']='zone root strip: sheet carrier and trunk land, not emitting';obj['source_ref']='radiator_zoning'
        for tag,(x0,x1) in (('Aft',(xa(casing)+0.4,xa(pl['r1'])+0.4)),('Fwd',(pl['x1']-0.4,pl['x1']-0.4))):
            line(c,f"{pl['name']}_Root_Boom_{tag}",[P(x0,casing+0.02,0),P(x1,pl['r1'],0)],0.16,metal,kind='radiator_zone_support')
        trunk=line(c,f"{pl['name']}_Trunk",[P(xa(pl['r0']+0.6)+0.4,pl['r0']+0.6,th/2+0.12),P(pl['x1']-0.4,pl['r0']+0.6,th/2+0.12)],0.10,coolant,kind='radiator_zone_trunk')
        trunk['circuit']=pl['circuit'];trunk['engineering_status']='own feed/return trunk and isolation valves; no coolant crosses the bulkhead or the joint (OPEN: sizing, joints)'
        # exterior production refinement (2026-11-01, PROTOTYPE): the return trunk on the other face, an outer edge chord, and thin
        # transverse ribs at the panel-module boundaries standing edge-on on both faces (0.025 m footprint, at sheet temperature: under
        # 1 % of the face, and they radiate as fins, so the net capacity is unchanged); guided shoes bridge the WARM/LOW joint.
        ret=line(c,f"{pl['name']}_Trunk_Return",[P(xa(pl['r0']+0.6)+0.4,pl['r0']+0.6,-th/2-0.12),P(pl['x1']-0.4,pl['r0']+0.6,-th/2-0.12)],0.10,coolant,kind='radiator_zone_trunk')
        ret['circuit']=pl['circuit'];ret['engineering_status']='return trunk of the section (feed on the other face); sizing OPEN'
        X=lambda f,r:xa(r)+(pl['x1']-xa(r))*f
        line(c,f"{pl['name']}_Edge_Chord",[P(X(0,pl['r1']),pl['r1'],0),P(X(1,pl['r1']),pl['r1'],0)],0.06,zone_frame,kind='radiator_zone_support')
        parts=[]
        for i in range(1,nx):
            f=i/nx
            for sgn in (-1,1):
                for (a0,a1) in (((0,sgn*th/2),(0,sgn*(th/2+0.12))),):
                    pass
                c0=P(X(f,pl['r0']),pl['r0'],sgn*th/2);c1=P(X(f,pl['r1']),pl['r1'],sgn*th/2)
                d=(c1[0]-c0[0],c1[1]-c0[1],c1[2]-c0[2]);ln=math.sqrt(sum(v*v for v in d));e=tuple(v/ln for v in d)
                nn=(0.0,n[1]*sgn,n[2]*sgn);tt=(e[1]*nn[2]-e[2]*nn[1],e[2]*nn[0]-e[0]*nn[2],e[0]*nn[1]-e[1]*nn[0])
                vs=[tuple(cc[m]+tt[m]*wv+nn[m]*hv for m in range(3)) for cc in (c0,c1) for wv in (-0.0125,0.0125) for hv in (0.0,0.12)]
                parts.append((vs,[(0,1,3,2),(4,6,7,5),(0,4,5,1),(2,3,7,6),(0,2,6,4),(1,5,7,3)]))
        obj=mesh(c,f"{pl['name']}_Ribs",*_merge(parts),zone_frame,kind='radiator_zone_support')
        obj['function']='transverse ribs at the panel-module boundaries (edge-on, at sheet temperature; replaceable modules between them)';obj['source_ref']='radiator_zoning'
        obj['engineering_status']='PROTOTYPE; rib section and attachment OPEN'
        if pl['section']=='LOW':
            parts=[]
            for r in (pl['r0']+0.6,0.5*(pl['r0']+pl['r1']),pl['r1']-0.4):
                cc=P(pl['x0']-z['joint_m']/2,r,0);vs=[(cc[0]+dx,cc[1]+u[1]*dr+n[1]*dw,cc[2]+u[2]*dr+n[2]*dw) for dx in (-0.45,0.45) for dr in (-0.12,0.12) for dw in (-0.08,0.08)]
                parts.append((vs,[(0,2,3,1),(4,5,7,6),(0,1,5,4),(2,6,7,3),(0,4,6,2),(1,3,7,5)]))
            obj=mesh(c,f"{pl['name']}_Joint_Shoes",*_merge(parts),metal,kind='radiator_zone_support')
            obj['function']='guided shoes across the WARM/LOW expansion joint: carry the sheets radially and tangentially, slide axially; no coolant crosses'
            obj['engineering_status']='PROTOTYPE';obj['source_ref']='radiator_zoning'
    bulkhead_geometry(c,s)


def _merge(parts):
    vs=[];fs=[]
    for v,f in parts:
        o=len(vs);vs+=list(v);fs+=[tuple(i+o for i in q) for q in f]
    return vs,fs


def _tube_loop(pts,radius,n=8,closed=True):
    """Closed (or open) polyline as one tube mesh of cylinders (vertices, faces)."""
    seg=list(zip(pts,pts[1:]+pts[:1])) if closed else list(zip(pts,pts[1:]))
    return _merge([cylinder_mesh(a,b,radius,n) for a,b in seg if (a[0]-b[0])**2+(a[1]-b[1])**2+(a[2]-b[2])**2>1e-8])


def bulkhead_geometry(c,s):
    """Graded Thermal Blade bulkhead construction (exterior production refinement 2026-11-01, radiator_zones.panels/trusses/gates;
    PROTOTYPE): per layer 36 shingled foil gores in three replaceable panels, radial seam battens, anti-flutter hoops, a segmented rim
    with sliding sleeve joints and a hub ring on sliding casing brackets; three tapered C/C trusses in the layer 1-2 gap along the blade
    planes; layer 3 hung from the WARM aft root booms; one sliding-door gate per blade plane per layer on the crawler rail line. The foils
    are drawn as sheets without thickness (radiator_zones.membrane gives the 59-79 um they stand for)."""
    z=s['radiators']['zones'];bh=z['bulkhead'];p=s['prototype'];casing=__import__('thermal_geometry').casing_radius(s)
    L=radiator_zones.layers(s);mem={m['layer']:m for m in radiator_zones.membrane(s)}
    foil=[(material('BulkheadFoilMoA',(.62,.62,.63)),material('BulkheadFoilMoB',(.58,.58,.60))),
          (material('BulkheadFoilTiA',(.56,.53,.50)),material('BulkheadFoilTiB',(.53,.50,.47))),
          (material('BulkheadFoilAuA',(.83,.62,.30)),material('BulkheadFoilAuB',(.80,.59,.28)))]
    batten=material('BulkheadBatten',(.20,.20,.22));rimm=material('BulkheadRim',(.30,.31,.33));cc=material('BulkheadTrussCC',(.12,.12,.13))
    door=material('BulkheadGateFrame',(.80,.59,.21))
    P=lambda x,r,a:(x,r*math.cos(a),r*math.sin(a))
    na=4;nr=6
    by_gore={}
    for q in radiator_zones.panels(s):
        by_gore.setdefault((q['layer'],q['gore']),[]).append(q)
    notches={}
    for g in radiator_zones.gates(s):
        notches.setdefault(g['layer'],[]).append(g)
    def in_notch(li,r,a):
        return any(r<g['u1'] and abs((a-g['az']+math.pi)%(2*math.pi)-math.pi)<g['da'] for g in notches.get(li,[]))
    for (li,k),qs in by_gore.items():
        Li=L[li-1];vs=[];fs=[];mats=[];cut_here=False
        for q in qs:
            dx=q['step']+0.012*((q['panel']-1)%2)
            r1=q['r1']+(bh['overlap_m'] if q['r1']<Li['r1']-1e-6 else 0.0)
            hit=[g for g in notches.get(li,[]) if q['r0']<g['u1'] and any(in_notch(li,g['u0']+0.05,q['a0']+(q['a1']+bh['overlap_m']/g['u0']-q['a0'])*j/40) for j in range(41))]
            if hit:                      # finer grid so the notch is cut on its top edge and within a few cm of its flanks (the yoke covers them)
                u1=hit[0]['u1'];rs=[q['r0']+(u1-q['r0'])*i/16 for i in range(17)]+[u1+(r1-u1)*i/5 for i in range(1,6)];nA=32;cut_here=True
            else:
                rs=[q['r0']+(r1-q['r0'])*i/nr for i in range(nr+1)];nA=na
            o=len(vs)
            for r in rs:
                a1=q['a1']+bh['overlap_m']/r
                for j in range(nA+1):
                    a=q['a0']+(a1-q['a0'])*j/nA;vs.append(P(radiator_zones.x_on(Li,r)+dx,r,a))
            for i in range(len(rs)-1):
                for j in range(nA):
                    rc=(rs[i]+rs[i+1])/2;a1=q['a1']+bh['overlap_m']/rc;ac=q['a0']+(a1-q['a0'])*(j+.5)/nA
                    if hit and in_notch(li,rc,ac):continue
                    fs.append((o+i*(nA+1)+j,o+i*(nA+1)+j+1,o+(i+1)*(nA+1)+j+1,o+(i+1)*(nA+1)+j));mats.append((q['panel']+k)%2)
        obj=mesh(c,f"Radiator_Bulkhead_Layer_{li}_Gore_{k:02}",vs,fs,foil[li-1][0],kind='radiator_bulkhead')
        obj.data.materials.append(foil[li-1][1])
        for poly,mi in zip(obj.data.polygons,mats):poly.material_index=mi
        obj['layer']=li;obj['gore']=k;obj['panels']=len(qs);obj['emissivity']=Li['emissivity'];obj['slope_deg']=Li['slope_deg']
        obj['material_note']=Li['material'];obj['foil_thickness_um']=round(mem[li]['thickness_um'],1);obj['source_ref']='radiator_zoning'
        obj['function']='V-groove thermal bulkhead gore: replaceable foil panels between the hub, the anti-flutter hoops and the rim, shingled over its neighbours (labyrinth overlap)'+('; its inner panel is cut by a gate notch, hemmed to the yoke' if cut_here else '')
        obj['engineering_status']='PROTOTYPE; foil qualification, tension, flutter and MMOD OPEN; drawn without thickness'
    for Li in L:
        i=Li['index'];hx=0.006
        parts=[cylinder_mesh(P(radiator_zones.x_on(Li,Li['r0'])+hx,Li['r0'],a),P(radiator_zones.x_on(Li,Li['r1'])+hx,Li['r1'],a),bh['tendon']['radius_m'],6)
               for a in radiator_zones.seam_angles(s,i)]
        obj=mesh(c,f"Radiator_Bulkhead_Layer_{i}_Battens",*_merge(parts),batten,kind='radiator_bulkhead_frame')
        obj['function']=bh['tendon']['note'];obj['engineering_status']='PROTOTYPE';obj['source_ref']='radiator_zoning'
        parts=[]
        for r in [r for r in bh['panel_hoops_r_m'] if Li['r0']<r<Li['r1']]:
            parts.append(_tube_loop([P(radiator_zones.x_on(Li,r)+hx,r,2*math.pi*m/144) for m in range(144)],bh['hoop']['radius_m'],6))
        obj=mesh(c,f"Radiator_Bulkhead_Layer_{i}_Hoops",*_merge(parts),batten,kind='radiator_bulkhead_frame')
        obj['function']=bh['hoop']['note'];obj['engineering_status']='PROTOTYPE';obj['source_ref']='radiator_zoning'
        rr=bh['rim']['radius_m'];n=bh['rim']['segments'];xr=Li['x_rim']
        obj=mesh(c,f"Radiator_Bulkhead_Layer_{i}_Rim",*_tube_loop([P(xr,Li['r1']+rr*.5,2*math.pi*m/(4*n)) for m in range(4*n)],rr,10),rimm,kind='radiator_bulkhead_frame')
        obj['function']=bh['rim']['note']+'; the foil hems wrap over it (rolled edge)';obj['segments']=n;obj['joint_travel_m']=bh['rim']['joint_travel_m']
        obj['engineering_status']='PROTOTYPE; segment joints slide for the layer growth (radiator_zones.construction)';obj['source_ref']='radiator_zoning'
        parts=[]
        for a in radiator_zones.seam_angles(s,i)[::1]:
            ta=(0.0,-math.sin(a),math.cos(a));c0=P(xr,Li['r1']+rr*.5,a)
            parts.append(cylinder_mesh(tuple(c0[m]-ta[m]*.22 for m in range(3)),tuple(c0[m]+ta[m]*.22 for m in range(3)),rr*1.45,10))
        obj=mesh(c,f"Radiator_Bulkhead_Layer_{i}_Rim_Joints",*_merge(parts),batten,kind='radiator_bulkhead_frame')
        obj['function']='sliding sleeve joint between rim segments (travel per radiator_zones.construction)';obj['engineering_status']='PROTOTYPE';obj['source_ref']='radiator_zoning'
        xh=radiator_zones.x_on(Li,Li['r0']);rh_=Li['r0']+bh['hub']['radius_m']
        parts=[];gaps=sorted((g['az']-g['da']-0.012,g['az']+g['da']+0.012) for g in notches[i])
        for (g0,g1),(h0,h1) in zip(gaps,gaps[1:]+[(gaps[0][0]+2*math.pi,gaps[0][1]+2*math.pi)]):
            nseg=max(4,int((h0-g1)/(2*math.pi)*96))     # hub ring arcs between the notches; the yokes carry its hoop load round each notch
            parts.append(_tube_loop([P(xh,rh_,g1+(h0-g1)*m/nseg) for m in range(nseg+1)],bh['hub']['radius_m'],8,False))
        for a in radiator_zones.hub_bracket_angles(s):
            parts.append(cylinder_mesh(P(xh,casing+.01,a),P(xh,rh_,a),0.045,8))
            ta=(0.0,-math.sin(a),math.cos(a));c0=P(xh,casing+.04,a)
            parts.append(cylinder_mesh(tuple(c0[q]-ta[q]*.18 for q in range(3)),tuple(c0[q]+ta[q]*.18 for q in range(3)),0.035,8))
        obj=mesh(c,f"Radiator_Bulkhead_Layer_{i}_Hub",*_merge(parts),rimm,kind='radiator_bulkhead_frame')
        obj['function']=bh['hub']['note']+f" (radial slide {bh['hub']['slide_m']} m)";obj['engineering_status']='PROTOTYPE';obj['source_ref']='radiator_zoning'
    for tr in radiator_zones.trusses(s):
        a=tr['azimuth'];A=[P(x,r,a) for x,r in tr['aft']];F=[P(x,r,a) for x,r in tr['fwd']]
        parts=[_tube_loop(A,0.05,8,False),_tube_loop(F,0.05,8,False)]
        for m in range(len(A)):
            parts.append(cylinder_mesh(A[m],F[m],0.03,6))
            if m+1<len(A):parts.append(cylinder_mesh(A[m],F[m+1],0.025,6))
        obj=mesh(c,tr['name'],*_merge(parts),cc,kind='radiator_bulkhead_frame')
        obj['function']=s['radiators']['zones']['bulkhead']['truss']['note']+'; carries layers 1 and 2 on low-conductance standoffs, sliding at the rim'
        obj['depth_hub_m']=round(tr['depth_hub'],3);obj['depth_rim_m']=round(tr['depth_rim'],3)
        obj['engineering_status']='PROTOTYPE; sizing, standoffs and dynamics OPEN; behind layer 1, never in view of the 1800 K blades';obj['source_ref']='radiator_zoning'
    L3=L[-1]
    for k in range(3):
        a=math.radians(p['radiator_phase_deg']+120*k);parts=[]
        r=L3['r0']+1.0
        while r<L3['r1']-.5:
            x=radiator_zones.x_on(L3,r);parts.append(cylinder_mesh(P(x+0.01,r,a),P(x+bh['clearance_m'],r,a),0.02,6));r+=bh['hanger']['pitch_m']
        obj=mesh(c,f"Radiator_Bulkhead_Layer_3_Hangers_{k+1}",*_merge(parts),rimm,kind='radiator_bulkhead_frame')
        obj['function']=bh['hanger']['note'];obj['engineering_status']='PROTOTYPE';obj['source_ref']='radiator_zoning'
    gate_geometry(c,s,L,foil)


def _box_q(Q,u0,u1,v0,v1,d0,d1):
    """Box in a gate's local frame (Q maps u, v, dx to ship coordinates): vertices and faces."""
    vs=[Q(u,v,d) for u in (u0,u1) for v in (v0,v1) for d in (d0,d1)]
    return vs,[(0,2,3,1),(4,5,7,6),(0,1,5,4),(2,6,7,3),(0,4,6,2),(1,3,7,5)]


def gate_geometry(c,s,L,foil):
    """Thermal bulkhead gate mechanism (thermal bulkhead mechanisms 2026-11-02, radiator_zones.gate_parts / gate_checks / interlock;
    PROTOTYPE), the same at all nine gates: a notch from the layer's inner edge framed by a C/C yoke, a door forward of the layer that
    overlaps the notch (radiation labyrinth) and slides radially outward on two guides, two latch pawls, the drive shaft in the casing gap
    with a capstan and cable per layer; per blade plane the drive unit and the SP-51 bridge rail cassette on the casing forward of layer 3.
    Drawn closed and latched (the burn pose); each door carries its slide vector, so a review file can show it parked open."""
    bh=s['radiators']['zones']['bulkhead'];m=bh['gate_mechanism'];gp=radiator_zones.gate_parts(s);casing=gp['casing']
    yoke=material('BulkheadYokeCC',(.13,.13,.14));frame=material('BulkheadGateFrame',(.80,.59,.21));guide=material('BulkheadGateGuide',(.45,.46,.48))
    drive=material('BulkheadGateDrive',(.22,.23,.25));cable=material('BulkheadGateCable',(.55,.55,.57));latch=material('BulkheadGateLatch',(.85,.45,.12))
    def frame_of(Li,az):
        er=(0.0,math.cos(az),math.sin(az));et=(0.0,-math.sin(az),math.cos(az))
        def Q(u,v,d=0.0):
            r=math.hypot(u,v);return (radiator_zones.x_on(Li,r)+d,u*er[1]+v*et[1],u*er[2]+v*et[2])
        return Q,er
    for g in gp['gates']:
        Li=L[g['layer']-1];Q,er=frame_of(Li,g['az']);tn=math.tan(g['da']);y=g['yoke'];d=g['door'];gd=g['guides'];yw=y['width']
        tag=lambda o,f,st='PROTOTYPE':(o.__setitem__('function',f),o.__setitem__('engineering_status',st),o.__setitem__('source_ref','radiator_zoning'),
                                       o.__setitem__('layer',g['layer']),o.__setitem__('blade',g['blade']))
        # yoke: two legs along the flank lines (outside the notch), a head beam over it, feet on the hub ring arcs
        hw=lambda u:u*tn+yw/2
        parts=[]
        for sg in (-1,1):
            pts=[(y['u0'],sg*hw(y['u0'])),(y['u1'],sg*hw(y['u1']))]
            vs=[Q(u,v+sg*o,dd) for (u,v) in pts for o in (-yw/2,yw/2) for dd in (-0.03,0.03)]
            parts.append((vs,[(0,2,3,1),(4,5,7,6),(0,1,5,4),(2,6,7,3),(0,4,6,2),(1,3,7,5)]))
        vs=[Q(u,v,dd) for u in (g['u1'],g['u1']+yw) for v in (-hw(y['u1'])-yw/2,hw(y['u1'])+yw/2) for dd in (-0.03,0.03)]
        parts.append((vs,[(0,2,3,1),(4,5,7,6),(0,1,5,4),(2,6,7,3),(0,4,6,2),(1,3,7,5)]))
        for sg in (-1,1):                       # feet: the leg foot bears on the hub bracket moved under it (hub_bracket_angles)
            parts.append(_box_q(Q,y['u0']-0.05,y['u0']+0.10,sg*hw(y['u0'])-yw*0.75,sg*hw(y['u0'])+yw*0.75,-0.05,0.05))
        obj=mesh(c,g['name']+'_Yoke',*_merge(parts),yoke,kind='radiator_bulkhead_gate')
        tag(obj,'gate yoke: C/C box section framing the notch, carries the hub ring hoop load round it; the cut gore panels hem to it')
        # door closed: foil face on a stiff frame, forward of the layer by the labyrinth standoff
        corners=[(d['u0'],-d['v0']),(d['u0'],d['v0']),(d['u1'],d['v1']),(d['u1'],-d['v1'])]
        vs=[Q(u,v,d['dx']) for u,v in corners]
        obj=mesh(c,g['name']+'_Door',vs,[(0,1,2,3)],foil[g['layer']-1][1],kind='radiator_bulkhead_gate')
        slope=Li['tan'];sv=(d['travel']*slope,d['travel']*er[1],d['travel']*er[2])
        obj['slide_vector']=sv;obj['travel_m']=round(d['travel'],3);obj['pose']='CLOSED_LATCHED'
        tag(obj,'gate door: a foil face of the layer metal, overlaps the notch by %.2f m at %.2f m standoff (labyrinth, rays pass only within %.1f deg of grazing); slides radially outward %.2f m to park above the notch'
            %(m['overlap_m'],m['standoff_m'],math.degrees(math.atan(m['standoff_m']/m['overlap_m'])),d['travel']),'PROTOTYPE; drawn closed and latched (burn pose)')
        itf=empty(c,f"IF_{g['name'].upper()}",Q((g['u0']+g['u1'])/2,0.0))       # the passage interface at the notch centre, in the layer plane
        itf['mechanism']='sliding door, radial';itf['door']=g['name']+'_Door';itf['slide_vector']=sv;itf['interlock']='radiator_zones.interlock'
        fr=_tube_loop([Q(u,v,d['dx']+d['depth']/2) for u,v in corners],0.018,6)
        vsf,fsf=fr
        for u in (d['u0']+(d['u1']-d['u0'])*k/3 for k in (1,2)):      # two stiffening bars
            hvv=d['v0']+(d['v1']-d['v0'])*(u-d['u0'])/(d['u1']-d['u0'])
            vsf,fsf=_merge([(vsf,fsf),cylinder_mesh(Q(u,-hvv,d['dx']+d['depth']/2),Q(u,hvv,d['dx']+d['depth']/2),0.012,6)])
        obj=mesh(c,g['name']+'_Door_Frame',vsf,fsf,frame,kind='radiator_bulkhead_gate');obj['slide_vector']=sv;obj['pose']='CLOSED_LATCHED'
        tag(obj,'gate door frame: TZM edge tube and stiffeners on the door\'s forward face, ceramic (Si3N4) rollers in the guides, no lubricant (moves only cold)')
        # guides with their standoffs to the layer, cable pulleys at the top
        parts=[]
        for v in gd['v']:
            parts.append(cylinder_mesh(Q(gd['u0'],v,gd['dx']),Q(gd['u1'],v,gd['dx']),gd['radius'],8))
            for u in (gd['u0']+0.15,(gd['u0']+gd['u1'])/2,gd['u1']-0.1):
                parts.append(cylinder_mesh(Q(u,v,0.0),Q(u,v,gd['dx']),0.012,6))
            parts.append(cylinder_mesh(Q(gd['u1'],v,gd['dx']-0.03),Q(gd['u1'],v,gd['dx']+0.03),0.05,10))
        obj=mesh(c,g['name']+'_Guides',*_merge(parts),guide,kind='radiator_bulkhead_gate')
        tag(obj,'two TZM door guides on the layer\'s forward face, from the casing gap to above the parked door; cable pulley at the top')
        # latch pawls at the notch foot (spring pawls into the door frame; released by the drive's first motion)
        parts=[_box_q(Q,u-0.04,u+0.04,v-0.03,v+0.03,d['dx'],d['dx']+d['depth']+0.03) for u,v in g['latches']]
        obj=mesh(c,g['name']+'_Latches',*_merge(parts),latch,kind='radiator_bulkhead_gate')
        tag(obj,'two spring latch pawls: hold the door closed under thrust and vibration; position sensed (two sensors per door, drive arm interlock)')
        # capstan on the drive shaft (casing gap) and the cable up the guide to the door
        sh=g['shaft'];xs=radiator_zones.x_on(Li,sh['u'])
        parts=[cylinder_mesh((xs-0.03,)+Q(sh['u'],sh['v'])[1:],(xs+0.05,)+Q(sh['u'],sh['v'])[1:],0.04,12)]
        pa=Q(sh['u'],sh['v'],0.01);pb=Q(gd['u0']+0.05,gd['v'][0],gd['dx']);pc=Q(gd['u1'],gd['v'][0],gd['dx'])
        parts+=[cylinder_mesh(pa,pb,0.005,4),cylinder_mesh(pb,pc,0.005,4)]
        obj=mesh(c,g['name']+'_Capstan',*_merge(parts),cable,kind='radiator_bulkhead_gate')
        tag(obj,'capstan on the stack\'s common drive shaft and the Mo cable loop to the door (constant-tension take-up for the hub slide)')
    # per blade plane: drive shaft through the casing gap, drive unit and bridge-rail cassette forward of layer 3
    L1=L[0]
    for pl in gp['planes']:
        Q,er=frame_of(L[-1],pl['az']);dv=pl['drive'];br=pl['bridge'];sh_u=casing+bh['casing_gap_m']/2
        Qc=lambda x,u,v:(x,)+Q(u,v)[1:]
        x_aft=radiator_zones.x_on(L1,sh_u)-0.06
        parts=[cylinder_mesh(Qc(x_aft,sh_u,dv['v']),Qc(dv['x0']+0.05,sh_u,dv['v']),bh['gate_mechanism']['shaft_radius_m'],10)]
        dl,dw,dh=dv['size']
        vs=[Qc(x,u,v) for x in (dv['x0'],dv['x1']) for u in (casing,casing+dh) for v in (dv['v']-dw/2,dv['v']+dw/2)]
        parts.append((vs,[(0,2,3,1),(4,5,7,6),(0,1,5,4),(2,6,7,3),(0,4,6,2),(1,3,7,5)]))
        obj=mesh(c,f"Radiator_Bulkhead_Gate_Drive_{pl['blade']}",*_merge(parts),drive,kind='radiator_bulkhead_gate')
        obj['function']=('gate drive: motor, brake and constant-force closing spring on the casing forward of layer 3 (cold side), turning a C/C shaft along X '
                         'in the casing gap (no layer reaches it) with one capstan per layer, so the three doors of the stack move together; manual EVA drive socket')
        obj['engineering_status']='PROTOTYPE; motor sizing, shaft dynamics and feedthroughs OPEN';obj['source_ref']='radiator_zoning';obj['blade']=pl['blade']
        x0,x1,chh=br['cassette'];cw=bh['bridge']['cassette_m'][0]
        vs=[Qc(x,u,v) for x in (x0,x1) for u in (casing,casing+chh) for v in (-cw/2,cw/2)]
        obj=mesh(c,f"Radiator_Bulkhead_Bridge_Cassette_{pl['blade']}",vs,[(0,2,3,1),(4,5,7,6),(0,1,5,4),(2,6,7,3),(0,4,6,2),(1,3,7,5)],drive,kind='radiator_bulkhead_gate')
        obj['function']=('SP-51 bridge rail cassette: %d telescoping two-rail sections of %.2f m, extend aft %.2f m through the three open notches to the crawler track end; '
                         'an extended bridge lies in every door\'s closing path') %(br['sections'],br['section_m'],br['x_extended'][1]-br['x_extended'][0])
        obj['engineering_status']='PROTOTYPE; stowed (burn pose)';obj['source_ref']='radiator_zoning';obj['blade']=pl['blade']
        obj['bridge_extended_x']=br['x_extended'];obj['bridge_rails_v']=br['rails_v'];obj['bridge_u']=br['u'];obj['azimuth']=pl['az']
    panel_clips(c,s,L)


def panel_clips(c,s,L):
    """Representative replaceable panel interface (radiator_zones.panel_mount; PROTOTYPE): on the gore beside each gate of layers 1 and 3
    (the faces a panel is exchanged from), the hem clips at their pitch in the batten clip track (the fixed clip at each panel's inner
    edge centre larger) and a constant-force tensioner at each panel's outer corners. The other gores carry the same interface, not drawn."""
    bh=s['radiators']['zones']['bulkhead'];pm=bh['panel_mount'];clip=material('BulkheadPanelClip',(.70,.30,.10));P=lambda x,r,a:(x,r*math.cos(a),r*math.sin(a))
    by={}
    for q in radiator_zones.panels(s):
        by.setdefault((q['layer'],q['gore']),[]).append(q)
    for g in radiator_zones.gates(s):
        if g['layer'] not in (1,3):continue
        Li=L[g['layer']-1];a_side=g['az']+g['da']+0.12           # the gore next to the notch, beside the passage
        k=next(kk for (li,kk),qs in by.items() if li==g['layer'] and qs[0]['a0']<=a_side<qs[0]['a1'])
        parts=[];sgn=1 if g['layer']==3 else -1
        for q in by[(g['layer'],k)]:
            for a in (q['a0'],q['a1']):
                n=max(2,int((q['r1']-q['r0'])/pm['clip_pitch_m']))
                for j in range(n+1):
                    r=q['r0']+(q['r1']-q['r0'])*j/n;x=radiator_zones.x_on(Li,r)+sgn*0.015
                    parts.append(cylinder_mesh(P(x-0.012,r,a),P(x+0.012,r,a),0.022,6))
            am=(q['a0']+q['a1'])/2;x=radiator_zones.x_on(Li,q['r0'])+sgn*0.02          # fixed clip, inner edge centre
            parts.append(cylinder_mesh(P(x-0.02,q['r0']+0.05,am),P(x+0.02,q['r0']+0.05,am),0.045,8))
            for a in (q['a0']+0.004,q['a1']-0.004):                                    # tensioners at the outer corners
                x=radiator_zones.x_on(Li,q['r1'])+sgn*0.02
                parts.append(cylinder_mesh(P(x,q['r1']-0.25,a),P(x,q['r1']-0.25+pm['tensioner_travel_m']+0.1,a),0.03,8))
        obj=mesh(c,f"Radiator_Bulkhead_Layer_{g['layer']}_Gore_{k:02}_Panel_Mounts",*_merge(parts),clip,kind='radiator_bulkhead_frame')
        obj['function']=('replaceable panel interface: hem clips every %.2f m in the batten clip track, one fixed clip per panel (inner edge centre), the others '
                         'slide radially and float %.2f m tangentially; constant-force tensioners (%.2f m travel) at the outer corners')%(pm['clip_pitch_m'],pm['clip_float_m'],pm['tensioner_travel_m'])
        obj['engineering_status']='PROTOTYPE; representative gore; exchange tooling OPEN';obj['source_ref']='radiator_zoning';obj['layer']=g['layer'];obj['gore']=k
