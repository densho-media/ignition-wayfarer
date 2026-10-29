"""Simulation rig contract: semantic anchor frames plus sourced physical quantities. Standard library only.

Positions reuse the recipe formulas and are checked against the saved IF_* interfaces. Geometry illustrates
the physics; data defines it. Centre of mass and vehicle inertia stay unknown: no position is ever emitted.
"""
from pathlib import Path
import argparse
import json
import math
import sys
import thermal_budget
import tomllib
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(Path(__file__).resolve().parent))
from spec import load, derived, digest, buildable_configurations
import hull_geometry
import drive_manifold
import power_storage
import rotor_interface
import crew_transfer
import human_entry
import route_fitout
import flight_timeline
import forward_shield
import radiator_health
import habitat_ring
import layout
import crew_dynamics
import ship_navigator
import space_navigator
import forward_explorer
import drone_fleet
import drone_demo
import drone_routes
import tomllib

CONTRACT='WF_SIM_RIG'
CONTRACT_VERSION=43
GENERATED_BY='WF_PROXY_P1_001'
OUTPUT='data/simulations/wf_sim_rig.json'


def quantity(field):
    """TOML field → JSON quantity. Unknown fields keep their reason and never carry a value."""
    keep=['canon_status','source_ref','evidence_ref','reason','item','unit','note','basis']
    if field.get('known') is False:
        return {'known':False,**{k:field[k] for k in keep if k in field}}
    out={'known':True,**{k:field[k] for k in keep if k in field}}
    for key in ['value','lower_kg','upper_kg','start_accel','max_accel','duration_d','distance_AU','profile','study_ceiling_deg']:
        if key in field:out[key]=float(field[key]) if isinstance(field[key],(int,float)) and not isinstance(field[key],bool) else field[key]
    return out


def frame(axis,up):
    """Orthonormal anchor frame: local +X = axis, local +Z = up (made orthogonal), local +Y = Z × X."""
    n=math.sqrt(sum(a*a for a in axis));x=[a/n for a in axis]
    d=sum(a*b for a,b in zip(up,x));z=[u-d*a for u,a in zip(up,x)]
    n=math.sqrt(sum(a*a for a in z));z=[a/n for a in z]
    y=[z[1]*x[2]-z[2]*x[1],z[2]*x[0]-z[0]*x[2],z[0]*x[1]-z[1]*x[0]]
    return x,y,z


def anchor(name,role,position,axis,up,relation,refs,status,**quantities):
    x,y,z=frame(axis,up)
    return {'name':name,'id':'WF.SIM.'+name.removeprefix('WF_SIM_'),'role':role,'known':True,
            'position_m':[float(v) for v in position],'axis':x,'side':y,'up':z,'geometry_status':status,
            'relation':relation,'interface_refs':[{'asset':a,'object':o} for a,o in refs],'quantities':quantities}


def radiator_sectors(s):
    """(1-based sector, azimuth rad) of each fixed blade, the recipe's sector rule."""
    return [(j+1,math.radians(s['prototype']['radiator_phase_deg']+j*120)) for j in range(s['radiators']['count'])]


def radiator_root(d,a):
    """Midpoint of the two root-boom ends (IF_RAD_n_ROOT_-1/+1) at azimuth a."""
    return (d['mount_x_m'],d['root_radius_m']*math.cos(a),d['root_radius_m']*math.sin(a))


def forward_anchors(s,X,Z):
    """FGR-006 front anchors: shield face, Dust Lance tip, diversion-field zone and one frame per Crown bay (stowed carriage centre; up radially outward)."""
    st=forward_shield.stations(s);cr=forward_shield.crown(s);d=s['forward_defense'];asset=forward_shield.SUBSYSTEM+'.blend'
    out=[anchor('WF_SIM_FORWARD_SHIELD','centre of the fixed forward shield face; the shield never moves',(st['face'],0,0),X,Z,'COINCIDENT',[(asset,'IF_SHIELD_FACE')],'PROTOTYPE',
                diameter=quantity(s['forward_shield']['diameter']),bow_form={'known':True,'value':s['forward_shield']['bow_form']['value'],'canon_status':'WORKING','source_ref':'bow_form'},
                stack=quantity(s['forward_shield']['stack'])),
         anchor('WF_SIM_DUST_LANCE_TIP','tip of the central Dust Lance on the +X axis; the foremost sacrificial, replaceable element',(st['lance_tip'],0,0),X,Z,'COINCIDENT',[(asset,'IF_DUST_LANCE_TIP')],'PROTOTYPE',
                length=quantity(d['dust_lance']['length']),
                taper={'known':True,'unit':'m','base_radius_m':float(d['dust_lance']['geometry']['base_radius_m']),'tip_radius_m':float(d['dust_lance']['geometry']['tip_radius_m']),
                       'tip_cartridge_m':float(d['dust_lance']['geometry']['tip_cartridge_m']),'canon_status':d['dust_lance']['geometry']['canon_status'],'source_ref':d['dust_lance']['geometry']['source_ref'],
                       'basis':'WORKING length, taper and tip cartridge (Q2); material and detailed profile OPEN (OD-017). The length counts inside the 220-240 m overall length.'}),
         anchor('WF_SIM_FIELD_ZONE','centre of the PROTOTYPE diversion-field display zone around and behind the Lance',((st['field'][0]+st['field'][1])/2,0,0),X,Z,'COINCIDENT',[(asset,'IF_FIELD_ZONE')],'PROTOTYPE',
                field=quantity(d['magnetic_diversion']['field']),boundary={'known':True,'value':d['magnetic_diversion']['boundary']['rule'],'canon_status':'LOCKED','source_ref':'eye_magnetic_boundary'})]
    for b in cr['bays']:
        c,sn=math.cos(b['azimuth']),math.sin(b['azimuth'])
        out.append(anchor(f"WF_SIM_CROWN_SECTOR_{b['index']:02}",f"Aegis Dustbreak Crown bay {b['index']:02}: stowed carriage centre; axis +X (fire direction), up radially outward",
                          (cr['carriage_x'],cr['stowed_r']*c,cr['stowed_r']*sn),X,(0.0,c,sn),'COINCIDENT',[(asset,f"IF_CROWN_SECTOR_{b['index']:02}")],'PROTOTYPE',
                          azimuth_turns={'known':True,'value':float(b['turn']),'unit':'turn','canon_status':'PROTOTYPE','basis':'Bay k at k/12 turns from +Y toward +Z.'},
                          crown={**quantity(d['crown']['open']),'concealment':d['crown']['concealment']['rule']}))
    return out


def dock_quantities(s,f):
    """Docking standard (WORKING), the clear passage and the PROTOTYPE capture ring of one dock port (HAB-001)."""
    dk=s['service']['docking']['standard'];p=s['prototype']
    return dict(docking_standard={'known':True,'value':dk['standard'],'canon_status':dk['canon_status'],'source_ref':dk['source_ref']},
                clear_passage={'known':True,'value':2*p['dock_clear_radius_m'],'unit':'m','canon_status':'PROTOTYPE','basis':'2 x dock_clear_radius_m, equal to the WORKING 1.6 m passage (14!A30)'},
                capture_ring_radius={'known':True,'value':p['dock_capture_ring_radius_m'],'unit':'m','canon_status':'PROTOTYPE','basis':'Structural capture ring larger than the passage; Q33 leaves its size OPEN (14!G30).'})


def anchors(s):
    p=s['prototype'];st=s['structure'];d=derived(s);length=s['ship']['length']['value']
    inlet=-length/2+p['nozzle_length_m'];q=p['nozzle_offset_m']
    nozzles=[(inlet,yy*q,zz*q) for yy,zz in drive_manifold.quadrants(s)]
    bearings=[(x,0.0,0.0) for x in habitat_ring.centers(s)]
    eye=(length/2-p['eye_front_inset_m']-p['eye_module_depth_m'],0.0,0.0)
    mean=lambda pts:[sum(v[i] for v in pts)/len(pts) for i in range(3)]
    X,Z=(1.0,0.0,0.0),(0.0,0.0,1.0)
    unknown={'known':False,'canon_status':'OPEN'}
    flight,structural=quantity(s['propulsion']['flight_thrust']),quantity(s['propulsion']['design_thrust'])
    out=[anchor('WF_SIM_ROOT','simulation root; vehicle frame origin',(0,0,0),X,Z,'COINCIDENT',[('VEHICLE','WF_ROOT')],'PROTOTYPE',
                center_of_mass=quantity(s['physics']['center_of_mass']),inertia=quantity(s['physics']['inertia']),
                mass_distribution=quantity(s['physics']['mass_distribution'])),
         anchor('WF_SIM_THRUST_CENTER','nominal line of action of the four equal nozzle thrusts',mean(nozzles),X,Z,'CENTROID',
                [('WF_PROPULSION.blend',f'IF_NOZZLE_{j:02}') for j in range(1,5)],'DERIVED',
                flight_thrust=flight,structural_design_load=structural,
                assumption='Nominal equal thrust per nozzle; only the line of action is meaningful, not the point along it. Use flight_thrust for flight dynamics and structural_design_load only for structural proof (15_MODEL_INTERFACES S3a).'),
         anchor('WF_SIM_REACTOR_CENTER','geometric centre of the PROTOTYPE fusion-core envelope; not a mass or heat centre',
                (layout.at(s,p['reactor_center_x']),0,0),X,Z,'COINCIDENT',[('WF_PROPULSION.blend','IF_REACTOR_MOUNT')],'PROTOTYPE'),
         anchor('WF_SIM_HABITAT_CENTER','midpoint of the two rotor planes; not a centre of mass',mean(bearings),X,Z,'MIDPOINT',
                [('WF_STRUCTURE.blend','IF_ROTOR_BEARING_1'),('WF_STRUCTURE.blend','IF_ROTOR_BEARING_2')],'PROTOTYPE'),
         anchor('WF_SIM_EYE_CENTER','shared mount of the four LOCKED EYE facets',eye,X,Z,'COINCIDENT',[('WF_EYE.blend','IF_EYE_MOUNT')],'PROTOTYPE',
                facet_count=float(s['eye']['facet_count']),aperture=quantity(s['eye']['aperture']),array_baseline=quantity(s['eye']['array_baseline'])),
         anchor('WF_SIM_SENSOR_FORWARD_AXIS','EYE boresight along +X',eye,X,Z,'COINCIDENT',[('WF_EYE.blend','IF_EYE_MOUNT')],'PROTOTYPE',
                field_of_view={**unknown,'reason':'No EYE field of view is sourced (Eye 05_FOUR_FACETS only says "Broad forward cone"); operating modes are in the contract eye section.'})]
    share,load=d['nozzle_flight_thrust_share_N'],d['nozzle_design_thrust_share_N']
    study=s['propulsion']['nozzle_vector_study']
    vector_study={'unit':'deg','normal':{'known':True,'value':float(study['normal_deg']),'canon_status':study['canon_status'],'source_ref':study['source_ref']},
                  'emergency':{'known':True,'value':float(study['emergency']['limit_deg']),'canon_status':study['emergency']['canon_status'],'evidence_ref':study['emergency']['evidence_ref'],'rule':study['emergency']['rule']},
                  'authority':quantity(s['propulsion']['vectoring_range']),
                  'use':'Limits only (15!G76): no vector pose is keyed and no gimbal hardware is modelled; the nozzles are mounted on the 15!A67 load path (yokes and pickups). The magnetic steering principle is grounded (Fiji 25!D64); the electromagnetic/mechanical vector authority is OPEN (06!E52).'}
    for j,(position,node) in enumerate(zip(nozzles,st['nozzle_pickup_nodes']),1):
        out.append(anchor(f'WF_SIM_NOZZLE_{j:02}_VECTOR','force on the ship (+X); exhaust leaves along -X',position,X,Z,'COINCIDENT',
                          [('WF_PROPULSION.blend',f'IF_NOZZLE_{j:02}')],'PROTOTYPE',
                          flight_thrust_share={'known':True,'value':share,'unit':'N','canon_status':'DERIVED','evidence_ref':'flight_thrust',
                                               'basis':'Equal quarter share of the DERIVED peak flight thrust; the workbook notes 4.045 MN per nozzle.'},
                          structural_design_load_share={'known':True,'value':load,'unit':'N','canon_status':'DERIVED','evidence_ref':'design_thrust',
                                                        'basis':'Equal quarter share of the structural proof/design load (about 7.355 MN per nozzle); not flight thrust.'},
                          pickup_ring_node={'known':True,'value':float(node),'canon_status':'WORKING','source_ref':'structure_geometry'},vector_study=vector_study,
                          vectoring_range=quantity(s['propulsion']['vectoring_range']),off_nominal_factors=quantity(s['propulsion']['off_nominal_factors'])))
    # Fixed radiators (R1/R8, MEC-012): one root frame per blade at the midpoint of its two root booms; axis +X, up radially outward.
    for j,a in radiator_sectors(s):
        out.append(anchor(f'WF_SIM_RADIATOR_{j:02}_ROOT','fixed radiator root; the blade never folds, hinges or cants in any mode',radiator_root(d,a),(1.0,0.0,0.0),(0.0,math.cos(a),math.sin(a)),'MIDPOINT',
                          [('WF_THERMAL.blend',f'IF_RAD_{j}_ROOT_{sg}') for sg in (-1,1)],'PROTOTYPE',
                          deployment_mechanism={'known':True,'value':s['operating_rules']['radiator_deployment_mechanism'],'canon_status':'BASELINE','source_ref':'radiator_no_mechanism'},
                          coolant_joint={**unknown,'reason':'Joint design is OPEN; thermal expansion is handled by structure (MEC-013), with no articulation.'}))
    for j,position in enumerate(bearings,1):
        out.append(anchor(f'WF_SIM_ROTOR_{j}_AXIS','rotor spin axis along +X',position,X,Z,'COINCIDENT',[('WF_STRUCTURE.blend',f'IF_ROTOR_BEARING_{j}')],'PROTOTYPE'))
    # Owner facet map (BASELINE): one boresight frame per facet Fj at its aperture centre.
    # The facet face is the well bottom: length/2 - inset in the flat hub, further aft on the cone for an outer Eye layout (forward_defense.eye_layout).
    for j,(w,label) in enumerate(zip(forward_shield.wells(s),s['eye']['facet_map']['labels']),1):
        front,y,z=w['x0'],w['y'],w['z']
        out.append(anchor(f'WF_SIM_EYE_FACET_F{j}',f'EYE facet {label}; boresight +X',(front,y,z),X,Z,'COINCIDENT',[('WF_EYE.blend',f'IF_EYE_FACET_{j:02}')],'PROTOTYPE',
                          facet_map={'known':True,'value':label,'canon_status':'BASELINE','source_ref':'eye_facet_map'},field_of_view=quantity(s['eye']['field_of_view'])))
    out+=forward_anchors(s,X,Z)
    for f in hull_geometry.service_fittings(s):
        u=(0.0,math.cos(f['theta']),math.sin(f['theta']))
        out.append(anchor('WF_SIM_'+f['name'].upper(),f"{f['role']}; axis points outward along the port",(f['x'],f['r1']*u[1],f['r1']*u[2]),u,X,'COINCIDENT',
                          [('WF_SERVICE.blend',f['interface'])],'PROTOTYPE',location_rule={'known':True,'value':'STATIONARY_CENTRAL_STRUCTURE','canon_status':'WORKING','source_ref':f['source_ref']},
                          mechanism={**unknown,'reason':'Hatch size, lock/port mechanism and docking standard are OPEN.'},
                          **(dock_quantities(s,f) if f['name'].startswith('Dock_') else {})))
    r=hull_geometry.refuge(s);ref=s['shielding']['refuge']
    out.append(anchor('WF_SIM_CREW_REFUGE','geometric centre of the PROTOTYPE storm-refuge envelope; not a mass centre',((r['x0']+r['x1'])/2,0,0),X,Z,'COINCIDENT',
                      [('WF_SERVICE.blend','IF_CREW_REFUGE')],'PROTOTYPE',
                      capacity_persons={'known':True,'value':float(ref['capacity_persons']),'canon_status':ref['canon_status'],'source_ref':ref['source_ref']},
                      areal_density_g_cm2={'known':True,'value':float(ref['areal_density_g_cm2']),'unit':'g/cm2','canon_status':ref['canon_status'],'source_ref':ref['source_ref']},
                      pressure_volume_m3={'known':True,'value':r['pressure_volume_m3'],'unit':'m3','canon_status':'PROTOTYPE','basis':'Annular PROTOTYPE cavity pi (r_p^2-r_i^2)(L-2t), not a sourced volume.'},
                      shell_water_equivalent_kg={'known':True,'value':r['shield_volume_m3']*s['prototype']['refuge_shield_density_g_cm3']*1000,'unit':'kg','canon_status':'DERIVED','source_ref':'storm_refuge',
                                                 'basis':'Shell volume (envelope minus cavity) at the selected shield density; the 20 t of the 180 t water (13!F7) is its limit. DIAGNOSTIC, not a mass-budget input.'}))
    # P1-007 storage packs: centre of each PROTOTYPE display envelope; axis +X, up radially outward. Not mass centres.
    st=s['power']['storage']
    for pack in power_storage.packs(s):
        layer={'MAIN_BATTERY':st['main_battery'],'PULSE_BANK':st['pulse_bank'],'SURVIVAL_RESERVE':st['survival_reserve']}[pack['layer']]
        name='WF_SIM_'+pack['name'].upper()
        out.append(anchor(name,f"centre of the PROTOTYPE {pack['layer'].lower().replace('_',' ')} envelope; not a mass centre",pack['center'],X,pack['u'],'COINCIDENT',
                          [('WF_POWER_STORAGE.blend',pack['interface'])],'PROTOTYPE',
                          layer={'known':True,'value':pack['layer'],'canon_status':layer['canon_status'],'source_ref':layer['source_ref']},
                          mass={**unknown,'evidence_ref':'power_storage_mass','reason':'Storage mass sits inside the 50 t power/computers/steering/comms allowance; no pack mass or position is sourced.'}))
    return out


def proxies(s):
    """Massless simulation proxies, each posed in its anchor's frame (local +X = anchor axis, +Z = anchor up).
    Shapes: box (center, size), cylinder/annulus/frustum along local X (x0 to x1, radii). No proxy carries mass or density."""
    p=s['prototype'];d=derived(s);h=s['habitat'];length=s['ship']['length']['value'];body=s['ship']['body_diameter']['value']/2
    no_mass={'known':False,'canon_status':'OPEN','reason':'Proxies are shapes only; masses have no positions (physics.mass_distribution) and the centre of mass is unknown.'}
    out=[{'name':'WF_SIMPROXY_BODY','anchor':'WF_SIM_ROOT','shape':'cylinder','x0_m':-length/2,'x1_m':length/2,'radius_m':body,
          'purpose':'occlusion and contact envelope of the stationary body; excludes radiators and the rotating rings','configurations':buildable_configurations(s),
          'motion':{'type':'FIXED'},'mass':no_mass,'geometry_status':'PROTOTYPE','source_ref':'body_diameter','basis':'Ship length and the 13 m body diameter (15_MODEL_INTERFACES H4 working choice inside the 12-14 m envelope); inspect proves the body stays inside it.'}]
    for j,a in radiator_sectors(s):
        x0=d['aft_x_m']-d['mount_x_m'];x1=d['front_x_m']-d['mount_x_m'];w=d['net_width_m'];t=p['radiator_thickness_m']
        out.append({'name':f'WF_SIMPROXY_RADIATOR_{j:02}','anchor':f'WF_SIM_RADIATOR_{j:02}_ROOT','shape':'box','center_m':[(x0+x1)/2,0.0,w/2],'size_m':[x1-x0,t,w],
                    'purpose':'radiating plate for view-factor, shadow and contact studies; both faces emit','configurations':buildable_configurations(s),
                    'motion':{'type':'FIXED','note':'Radiators are fixed in every mode (R1/R8, MEC-012).'},'mass':no_mass,'mass_region':'radiators_thermal',
                    'geometry_status':'PROTOTYPE','planform_m2':(x1-x0)*w,
                    'basis':'Gross planform of the accepted as-built blade (radiators.physical_area, Q52 option D; its net hot area is radiators.as_built_net_area); thickness is the PROTOTYPE cell thickness.'})
    for j in range(habitat_ring.ring_count(s)):
        out.append({'name':f'WF_SIMPROXY_RING_{j+1}_SWEEP','anchor':f'WF_SIM_ROTOR_{j+1}_AXIS','shape':'annulus','x0_m':-d['ring_sweep_half_m'],'x1_m':d['ring_sweep_half_m'],
                    'inner_radius_m':body,'outer_radius_m':d['ring_outer_radius_m'],
                    'purpose':'keep-out swept by the rotating ring (frame, sectors and spokes) over a full turn','configurations':buildable_configurations(s,'ROTATING'),
                    'motion':{'type':'FIXED','note':'Envelope of the ring motion; the ring spin itself is in the rotors section.'},'mass':no_mass,
                    'mass_region':'habitat_pressure_structure; life_support_garden_medical; water_radiation_shielding; rotating share of main_structure',
                    'geometry_status':'PROTOTYPE','source_ref':'ring_architecture','basis':'Body radius to the sourced ring outer radius (08!A20, WORKING); axial half-length is half the PROTOTYPE frame depth plus the allowance.'})
    st=forward_shield.stations(s)
    out.append({'name':'WF_SIMPROXY_SHIELD','anchor':'WF_SIM_FORWARD_SHIELD','shape':'cylinder','x0_m':-(st['face']-st['truss_aft']),'x1_m':forward_shield.layer_x(s,forward_shield.disruptor_layers(s)[0],0.0)[1]-st['face'],'radius_m':st['shield_r'],
                'purpose':'occlusion and shadow envelope of the fixed forward shield: the conical skin, rim and truss behind the face and the disruptor layer ahead of it (a cylinder bounding the cone)','configurations':buildable_configurations(s),
                'motion':{'type':'FIXED'},'mass':no_mass,'geometry_status':'PROTOTYPE','source_ref':'forward_shield_diameter',
                'basis':'WORKING 90 m shield diameter (radius 45 m DERIVED); the cylinder spans the aft face of the truss at the rim to the front of the PROTOTYPE disruptor layer, so it bounds the conical profile. The shield stack and mass are OPEN.'})
    lance=forward_shield.lance(s)
    out.append({'name':'WF_SIMPROXY_DUST_LANCE','anchor':'WF_SIM_DUST_LANCE_TIP','shape':'frustum','x0_m':-lance['length'],'x1_m':0.0,'radius0_m':lance['base_r'],'radius1_m':lance['tip_r'],
                'purpose':'contact envelope of the central Dust Lance from its root at the shield face to the tip, drawn in the tip frame','configurations':buildable_configurations(s),
                'motion':{'type':'FIXED'},'mass':no_mass,'geometry_status':'PROTOTYPE','source_ref':'dust_lance',
                'basis':'WORKING 12 m length and 1.0 to 0.25 m radii (Q2); the shape is a PROTOTYPE simplification (one cone over the full length, the 1.5 m tip cartridge not separated); material, detailed taper and tip life are OPEN.'})
    angle=p['sim_plume_study_half_angle_deg'];x_exit=-length/2;r0=math.sqrt(2)*p['nozzle_offset_m']+p['nozzle_exit_radius_m']
    thrust=[a for a in anchors(s) if a['name']=='WF_SIM_THRUST_CENTER'][0]['position_m'][0]
    reach=p['sim_plume_study_reach_m']       # PROTOTYPE display reach; the blades lie wholly ahead of the exit plane
    out.append({'name':'WF_SIMPROXY_PLUME_STUDY','anchor':'WF_SIM_THRUST_CENTER','shape':'frustum','x0_m':x_exit-thrust,'x1_m':x_exit-thrust-reach,
                'radius0_m':r0,'radius1_m':r0+reach*math.tan(math.radians(angle)),
                'purpose':f'hypothetical {angle:g} deg plume keep-out around all four nozzle exits, drawn aft of the exit plane for a PROTOTYPE display reach (the radiator blades lie wholly ahead of that plane)','configurations':buildable_configurations(s),
                'motion':{'type':'FIXED'},'mass':no_mass,'geometry_status':'PROTOTYPE','spec_ref':'physics.plume_boundary',
                'basis':'15_MODEL_INTERFACES R2 allows a 15 deg study case (20 deg stress case); the plume boundary is OPEN. Do not treat as canon.'})
    return out


def rotors(s):
    h=s['habitat'];rd=s['physics']['rotor_dynamics'];out=[]
    for j in range(habitat_ring.ring_count(s)):
        sign=1 if j==0 else -1;spins={}
        for name in buildable_configurations(s):
            spins[name]=float(sign*s['configuration'][name]['controls']['ring_spin'])+0.0
        out.append({'name':f'ROTOR_{j+1}','anchor':f'WF_SIM_ROTOR_{j+1}_AXIS','spin_sign_by_configuration':spins,
                    'rpm':float(h['rpm']),'omega_rad_s':rd['omega_rad_s'],'mass_kg':rd['mass_each_kg'],'com_radius_m':rd['com_radius_m'],
                    'inertia_kg_m2':rd['inertia_each_kg_m2'],'angular_momentum_N_m_s':sign*rd['angular_momentum_each_N_m_s'],
                    'spin_torque_N_m':rd['spin_torque_each_N_m'],'centripetal_force_N':rd['centripetal_force_per_ring_N'],
                    'high_thrust_axial_load_N':rd['high_thrust_axial_load_each_N'],'canon_status':'DERIVED','source_ref':'rotor_dynamics','model':rd['model']})
    return out


def configurations(s):
    out={}
    for name,cfg in s['configuration'].items():
        item={k:cfg[k] for k in ['buildable','drive','habitat','radiators','thermal_load','eye_mode','canon_status','source_ref','acceleration_profile','prototype_choices'] if k in cfg}
        if 'controls' in cfg:item['controls']={k:float(v) for k,v in cfg['controls'].items()}
        if 'max_accel_g' in cfg:item['max_accel_g']=float(cfg['max_accel_g'])
        item['open_fields']=sorted(k for k,v in cfg.items() if isinstance(v,dict) and v.get('known') is False)
        out[name]=item
    return out


def mass_budget(s):
    """Sourced component allowances. No item has a position, so none can feed a centre of mass."""
    b=s['physics']['mass_budget']
    items=[{'id':i['id'],'label':i['label'],'mass_kg':float(i['mass_kg']),**({'rotating_allowance_kg':float(i['rotating_allowance_kg'])} if 'rotating_allowance_kg' in i else {}),**({'refuge_allowance_kg':float(i['refuge_allowance_kg'])} if 'refuge_allowance_kg' in i else {})} for i in b['items']]
    return {'known':True,'unit':'kg','canon_status':b['canon_status'],'source_ref':b['source_ref'],'evidence_ref':b['evidence_ref'],'note':b['note'],
            'positions_known':False,'total_kg':sum(i['mass_kg'] for i in items),'items':items}


def eye_power(s):
    e=s['eye'];inp=e['power_inputs'];demand=e['electrical_demand']
    return {'mass':quantity(e['mass']),'brow_mass':quantity(s['brow']['mass']),
            'quiet_W':{'value':float(inp['quiet_W']),'canon_status':inp['canon_status'],'source_ref':inp['source_ref']},
            'bioheat_W':{'value':float(inp['bioheat_W']),'canon_status':inp['canon_status'],'source_ref':inp['source_ref']},
            **{k:{'value':float(demand[k]),'canon_status':demand['canon_status'],'source_ref':demand['source_ref']} for k in ['survey_W','burn_watch_W','ablation_W','ablation_laser_waste_heat_W']},
            'facet_modes':{k:{'label':v['label'],'canon_status':v['canon_status']} for k,v in e['facet_modes'].items()},
            'laser_modes':{k:{'label':v['label'],'electrical_W':float(v['electrical_W']),'waste_heat_W':float(v['waste_heat_W']),'canon_status':v['canon_status']} for k,v in e['laser_modes'].items()}}


def drive_manifold_contract(s):
    """P1F optically gated manifold rig: normalized controls only. Optical ratings, coupling and the throat field profile stay OPEN.
    AFT-008: the nozzle order is the owner map; the channel-loss recovery and the vector limits (limits only) are carried."""
    dm=drive_manifold;m=s['propulsion']['manifold'];dmp=s['drive_manifold']
    rec=m['channel_loss_recovery'];failed=3
    shares={'balanced':[m['nominal_share']]*4,'pitch_demo':[.3,.3,.2,.2],'yaw_demo':[.3,.2,.3,.2],'owner_example_yaw':m['example_maneuver']['shares'],
            'channel_loss_recovery_F3':dm.channel_loss_shares(s,failed)}
    survivors=[j for j,x in enumerate(shares['channel_loss_recovery_F3'],1) if x>0]
    study=s['propulsion']['nozzle_vector_study']
    return {'control':f'WF_PROPULSION.blend:{dm.CONTROL}','units':'normalized 0-1; no physical rating',
            'status':'PROTOTYPE rig over the WORKING optical control layer and the LOCKED four-way topology',
            'causal_chain':'laser A/B -> distributor -> optical_gate_n -> LATTICE_SECTOR_n -> flux domain n -> PLASMA_BRANCH_n -> Nozzle_0n',
            'properties':dict(dm.PROPS),'display_requests':dict(dm.DEBUG_TOGGLES),
            'configuration_settings':dict(dm.CONFIGURATION_SETTINGS),'saved_settings':{k:float(v) for k,v in dm.SAVED_SETTINGS.items()},
            'thrust_display':{'status':'PROTOTYPE display only','exponent':float(dmp['thrust_display_exponent']),'full_run_m':float(dmp['exhaust_length_m']),'note':dmp['thrust_display_note']},
            'debug_layers':{f'WF_{k}':{'instance':f'WF_PROPULSION.blend:DRIVE_{k}','toggle':v,'shown_at':'>= 0.5','saved':'hidden'} for k,v in dm.DEBUG_LAYERS.items()},
            'nozzle_order':{'labels':list(dmp['nozzle_labels']),'quadrants_yz':[list(map(float,q)) for q in dm.quadrants(s)],'status':dmp['nozzle_label_status'],'source_ref':m['nozzle_map']['source_ref'],'note':dmp['nozzle_label_note']},
            'channel_loss_recovery':{'status':rec['canon_status'],'source_ref':rec['source_ref'],'steps':list(rec['steps']),'action':'WF_FLUX_CHANNEL_FAIL','failed_channel':failed,'derated_channel':dm.opposite(s,failed),'survivors':survivors,
                                     'drive_level':float(rec['surviving_thrust_fraction']),'couple_arm_m':dm.couple_arm(s,shares['channel_loss_recovery_F3']),
                                     'rejected_default':rec['rejected_default'],
                                     'transition_torque':{'known':False,'canon_status':'OPEN','evidence_ref':'channel_loss_recovery','reason':'Handled by RCS/Momentum control (15!I76); torque magnitude and duration are not sourced and no RCS hardware is modelled.'},
                                     'vectoring_after_stabilization':{'animated':False,'reason':'Vector authority OPEN (06!E52); limits only.'}},
            'vectoring':{'unit':'deg','normal_deg':float(study['normal_deg']),'normal_status':study['canon_status'],'emergency_deg':float(study['emergency']['limit_deg']),'emergency_status':study['emergency']['canon_status'],
                         'authority':quantity(s['propulsion']['vectoring_range']),'keyed':False,'note':'Limits only (15!G76); the preview draws them as cones.'},
            'topology':{'architecture':m['architecture'],'physical_plasma_pipes':float(m['physical_plasma_pipes']),'nominal_share':float(m['nominal_share']),'canon_status':m['canon_status'],'source_ref':m['source_ref']},
            'shares':{k:[float(x) for x in v] for k,v in shares.items()},
            'couple_arm_m':{k:dm.couple_arm(s,v) for k,v in shares.items()},
            'couple_basis':'Moment arm per unit total thrust from branch allocation at equal exhaust velocity (Fiji 25!E23); the change from balanced is a pure couple, independent of the unknown centre of mass. Axial thrust gives no roll.',
            'optical':{k:quantity(m[k]) for k in ['optical_power','optical_wavelength','gate_response_time','optical_to_lattice_coupling','throat_field_profile']}|
                      {'throat_geometry':{**quantity(m['throat_geometry']),'length_m':float(m['throat_geometry']['length_m']),'waist_radius_m':float(m['throat_geometry']['waist_radius_m'])},
                       'control':{'known':True,**{k:(float(v) if isinstance(v,(int,float)) else v) for k,v in m['optical_control'].items()}}},
            'configuration_states':{n:{k:float(v) for k,v in dm.configuration_state(s,n).items()} for n in buildable_configurations(s)},
            'actions':{k:{'frame_range':[float(x) for x in v['frame_range']],'description':v['description']} for k,v in dm.actions(s).items()}}


def power_contract(s):
    """P1-007 layered storage and black start. Survival power and restart capability are separate channels."""
    pw=s['power'];st=pw['storage'];ps=power_storage;q=ps.quantities(s);item=ps.mass_allowance(s)
    def layer(field,numbers):
        out={'known':True,'canon_status':field['canon_status'],'source_ref':field['source_ref'],'technology':field['technology']}
        out.update({k:(float(field[k]) if isinstance(field[k],(int,float)) and not isinstance(field[k],bool) else field[k]) for k in numbers})
        out.update({k:quantity(v) for k,v in field.items() if isinstance(v,dict)})
        return out
    main,pulse,surv,ride=st['main_battery'],st['pulse_bank'],st['survival_reserve'],st['ride_through']
    frames=s['power_storage']['black_start_frames']
    return {'generation':{'generator_count':float(pw['generator_count']),'bus_names':list(pw['bus_names']),'canon_status':pw['canon_status'],'source_ref':pw['source_ref'],'rating':quantity(pw['rating'])},
            'architecture':{'layers':list(st['layers']),'canon_status':st['canon_status'],'source_ref':st['source_ref'],'note':st['note']},
            'main_battery':layer(main,['usable_energy_Wh','specific_energy_Wh_kg','specific_energy_basis','normal_source','role']),
            'pulse_bank':layer(pulse,['energy_Wh','power_W','charge_sources','role']),
            'survival_reserve':layer(surv,['loads','normal_source','isolated_from','distribution']),
            'ride_through':layer(ride,['scope','propulsion_store','role']),
            'derived':{k:{'known':True,'value':v,'unit':'kg' if k.endswith('_kg') else ('s' if k.endswith('_s') else ('J' if k.endswith('_J') else ('W' if k.endswith('_W') else 'ratio'))),
                          'canon_status':'DIAGNOSTIC' if k.endswith('_kg') else 'DERIVED','evidence_ref':'power_storage_mass' if k.endswith('_kg') else ('power_storage_pulse' if 'pulse' in k else 'power_storage_main')} for k,v in q.items()},
            'rules':{k:v for k,v in st['rules'].items()},
            'capabilities':{'survival_power':{'provided_by':'SURVIVAL_RESERVE','loads':list(surv['loads']),'capacity':quantity(surv['capacity']),'endurance':quantity(surv['endurance']),
                                              'can_restart_fusion':False,'canon_status':surv['canon_status'],'source_ref':surv['source_ref']},
                            'restart_capability':{'requires':['MAIN_BATTERY','PULSE_BANK'],'pulse_charge_sources':list(pulse['charge_sources']),'reactor_may_be_fully_off':True,
                                                  'pulse_charges_per_main_battery':q['pulse_charges_per_main_battery'],'ignition_energy':quantity(pulse['ignition_energy']),
                                                  'canon_status':'WORKING','evidence_ref':'black_start_sequence'}},
            'black_start':{'control':f'WF_POWER_STORAGE.blend:{ps.CONTROL}','action':ps.ACTION,'properties':dict(ps.PROPS),'saved_state':'STEP 0 (cold ship)',
                           'canon_status':pw['black_start']['canon_status'],'source_ref':pw['black_start']['source_ref'],
                           'timing':'PROTOTYPE frames at 24 fps; steps 3-8 coincide with WF_PROPULSION.blend WF_DRIVE_STARTUP keys',
                           'steps':[{**{k:x[k] for k in ['step','path','state','reactor','supplied_by','charges']},'frame':float(frames[x['step']]),'display':ps.step_state(x['step'])} for x in pw['black_start']['steps']],
                           'drive_alignment':ps.drive_alignment(s)['steps']},
            'hotel_source':quantity(pw['hotel_source']),'degraded_modes':quantity(pw['degraded_modes']),
            'configuration_power_states':{'known':False,'canon_status':'OPEN','evidence_ref':'power_hotel_interfaces',
                                          'reason':'Whether fusion or storage carries hotel load in each configuration is OPEN (S7/OD-009); only ACTIVE-drive configurations imply a running core.'},
            'mass_allocation':{'budget_item':item['id'],'allowance_kg':float(item['mass_kg']),'rotating_kg':0.0,'canon_status':'PROVISIONAL','source_ref':'power_storage_mass',
                               'note':'Storage shares the existing allowance with computers, steering and comms; no new mass line.'}}


def rings(s):
    """Rigid habitat rings: sourced radii and occupancy, DERIVED loads, and the PROTOTYPE frame, sectors, spokes and locks."""
    h=s['habitat'];r=s['habitat_ring'];rd=s['physics']['rotor_dynamics'];d=derived(s)
    def src(field,**extra):
        return {'known':True,'value':float(field['value']),'unit':field['unit'],'canon_status':field['canon_status'],'source_ref':field['source_ref'],**extra}
    arc=habitat_ring.sector_arc(s)
    return {'count':float(habitat_ring.ring_count(s)),'rpm':float(h['rpm']),'canon_status':h['canon_status'],'source_ref':h['source_ref'],
            'outer_radius':src(h['outer_radius']),'floor_radius':src(h['floor_radius']),'mass_radial_depth':src(h['mass_radial_depth']),
            'com_radius':{'known':True,'value':d['ring_com_radius_m'],'unit':'m','canon_status':'DERIVED','source_ref':'rotor_dynamics','basis':'floor radius - mass radial depth/2 (08!C10)'},
            'frame':{'inner_radius_m':r['frame_inner_radius_m'],'outer_radius_m':habitat_ring.outer(s),'axial_m':r['frame_axial_m'],'geometry_status':'PROTOTYPE','evidence_ref':r['evidence_ref'],
                     'section':quantity(h['ring_section'])},
            'sectors':[{'name':q['name'],'ring':q['ring'],'index':q['index'],'local_angle_deg':math.degrees(q['angle']),'arc_deg':math.degrees(arc),
                        'inner_radius_m':q['r0'],'outer_radius_m':q['r1'],'deck_radius_m':q['deck_radius'],'axial_m':q['axial'],'gross_m3':q['gross_m3'],'usable_m3':q['usable_alloc_m3'],
                        'deck_to_overhead_m3':q['deck_to_overhead_m3'],'function':q['function'],'geometry_status':'PROTOTYPE'} for q in habitat_ring.sectors(s)],
            'gross_total_m3':habitat_ring.gross_total(s),'pressure_rule':{'rule':h['pressure_rule']['rule'],'canon_status':h['pressure_rule']['canon_status'],'source_ref':h['pressure_rule']['source_ref']},
            'spokes':[{'name':q['name'],'ring':q['ring'],'index':q['index'],'side':q['side'],'angle_deg':math.degrees(q['angle']),'crew':q['crew'],'depth_m':habitat_ring.spoke_depth_m(s),'geometry_status':'PROTOTYPE'} for q in habitat_ring.spokes(s)],
            'lock_angles_deg':{f'ROTOR_{j}':[math.degrees(a) for a in habitat_ring.lock_angles(s,j)] for j in range(1,habitat_ring.ring_count(s)+1)},
            'rated_occupancy':src(s['crew']['rated_occupancy']),
            'story_manifest':{'known':True,'value':float(s['crew']['count']),'unit':'persons','canon_status':s['crew']['canon_status'],'source_ref':s['crew']['source_ref']},
            'usable_per_person_m3':{'rated':h['occupancy_density']['usable_per_rated_person_m3'],'story':h['occupancy_density']['usable_per_story_person_m3'],
                                    'canon_status':h['occupancy_density']['canon_status'],'source_ref':h['occupancy_density']['source_ref']},
            'centripetal_force_each_N':{'known':True,'value':rd['centripetal_force_per_ring_N'],'unit':'N','canon_status':'DERIVED','source_ref':'rotor_dynamics'},
            'high_thrust_axial_load':{'each_N':rd['high_thrust_axial_load_each_N'],'total_N':rd['high_thrust_axial_load_total_N'],'canon_status':'DERIVED','source_ref':'rotor_dynamics',
                                      'basis':'Ring mass x 1.5 g before safety and dynamic factors; the locks that carry it are OPEN (MEC-011, OD-016).'}}


def flight_timeline_contract(s,spec_text,source_text):
    """FUT-005 (v19): where the First Ignition timeline is and what it binds; the keys stay in its own file, checked by this hash."""
    ft=flight_timeline;t=ft.table(s);ps=ft.phases(s);ch=ft.channels(s,ps)
    return {'file':t['output'],'schema':ft.SCHEMA,'timeline_version':t['timeline_version'],'sha256':digest(ft.text(s,spec_text,source_text)),
            'status':t['phases']['status'],'fps':t['fps'],'frame_range':[ps[0]['frame_start'],ps[-1]['frame_end']],'classes':dict(ft.CLASSES),
            'phases':[{'id':p['id'],'frames':[p['frame_start'],p['frame_end']],**({'configuration':p['configuration']} if 'configuration' in p else {'from':p['from'],'to':p['to']}),
                       'duration':p['duration'],'scale':ft.display(s,p)['scale']} for p in ps],
            'marks':{n:{'phase':m['phase'],'frame':m['frame']} for n,m in ft.marks(s,ps).items()},
            'route':{k:ft.kinematics(s)[k] for k in ('scenario_id','scenario_status','frame_id','route_version','route_frames','source_ref')}|{'file':t['route']},
            'bindings':{n:c['binding'] for n,c in ch.items() if c['binding']},'unknown':list(t['unknown']['paths'])}


def contract(s,spec_text,source_text):
    ph=s['physics'];r=s['radiators'];d=derived(s);graph=human_entry.induction_graph(s)
    return {'contract':CONTRACT,'contract_version':CONTRACT_VERSION,'asset_id':s['asset_id'],'spec_schema':s['schema_version'],
            'spec_hash':digest(spec_text),'source_map_hash':digest(source_text),'generated_by':GENERATED_BY,
            'coordinates':{'length_unit':'m','forward_axis':'+X','up_axis':'+Z','left_axis':'+Y','origin':'WF_ROOT','handedness':'right','source_ref':'axis_contract'},
            'frame_convention':'Anchor local +X = axis, local +Z = up, local +Y = up x axis. Positions are in the vehicle frame.',
            'vehicle':{'asset':s['vehicle']['asset'],'file':s['vehicle']['asset']+'.blend','saved_preset':s['vehicle']['saved_preset']},
            'presets':{state:buildable_configurations(s,state) for state in ('ROTATING','STOPPED_LOCKED')},
            'configurations':configurations(s),'anchors':anchors(s),'proxies':proxies(s),'rotors':rotors(s),
            'mass_properties':{k:quantity(ph[k]) for k in ['protected_burnout_mass','departure_mass','propulsion_inventory','operational_reserve',
                                                         'reaction_mass','fusion_fuel','mass_distribution','center_of_mass','inertia']}|
                              {'rotating_system_mass':{'known':True,'value':ph['rotor_sizing']['mass_kg'],'unit':'kg','canon_status':'PROVISIONAL','source_ref':'rotor_mass'},
                               'mass_budget':mass_budget(s),
                               'suballocations':{'additive':False,'canon_status':ph['mass_suballocations']['canon_status'],'source_ref':ph['mass_suballocations']['source_ref'],
                                                 'parent':ph['mass_suballocations']['parent'],
                                                 'items':[{**i,'mass':{'known':False},'com_contribution':{'known':False}} for i in ph['mass_suballocations']['items']]},
                               'fuel_tanks':{'representation':ph['fuel_tanks']['representation'],'dimensions_status':ph['fuel_tanks']['dimensions_status'],'fuel_mass':quantity(ph['fuel_tanks']['fuel_mass'])}},
            'propulsion':{'flight_thrust':quantity(s['propulsion']['flight_thrust']),'structural_design_load':quantity(s['propulsion']['design_thrust']),
                          'nozzle_count':float(s['propulsion']['nozzle_count']),
                          'off_nominal_factors':quantity(s['propulsion']['off_nominal_factors']),'vectoring_range':quantity(s['propulsion']['vectoring_range']),
                          'drive_outputs':quantity(ph['drive_outputs']),'plume_boundary':quantity(ph['plume_boundary']),'field_boundary':quantity(ph['field_boundary']),
                          'drive_manifold':drive_manifold_contract(s)},
            'thermal':{'effective_area':quantity(r['effective_area']),'as_built_net_area_total':{'known':True,'value':d['total_net_area_m2'],'unit':'m2','canon_status':'DERIVED','evidence_ref':r['as_built_net_area']['evidence_ref'],'basis':'as-built net one-face hot area at the working seam, three blades'},
                       'nominal_net_area_total':{'known':True,'value':d['nominal_net_area_m2']*r['count'],'unit':'m2','canon_status':r['nominal_net_area']['canon_status'],'source_ref':r['nominal_net_area']['source_ref'],'basis':r['nominal_net_area']['basis']},
                       'physical_area_total':{'known':True,'value':d['total_planform_m2'],'unit':'m2','canon_status':r['physical_area']['canon_status'],'source_ref':r['physical_area']['source_ref'],'basis':r['physical_area']['basis']},
                       'view_factor':quantity(r['view_factor']),'temperature':quantity(r['temperature']),'emissivity':quantity(r['emissivity']),
                       'drive_waste_heat':quantity(r['drive_waste_heat']),'heat_debt':quantity(r['heat_debt']),
                       # v42: OWN-RAD-Y155 (40!A110:F123) opt-in material/view scenarios, DIAGNOSTIC / UNQUALIFIED; never a geometry input.
                       'y155_scenario':{'canon_status':r['y155_scenario']['canon_status'],'source_ref':r['y155_scenario']['source_ref'],'result_status':r['y155_scenario']['result_status'],
                                        'note':r['y155_scenario']['note'],'cases':thermal_budget.y155(s)},
                       'drive_heat_calibration':{'known':True,'canon_status':r['drive_heat_calibration']['canon_status'],'source_ref':r['drive_heat_calibration']['source_ref'],
                                                 'note':r['drive_heat_calibration']['note'],'absorbed_heat_W':float(r['drive_heat_calibration']['absorbed_heat_W']),
                                                 'ideal_area_m2':float(r['drive_heat_calibration']['ideal_area_m2']),
                                                 'calibration_power':quantity(s['propulsion']['field_calibration_power']),
                                                 'absorbed_heat_fraction':quantity(s['propulsion']['internal_waste_heat_fraction'])}},
            'eye':eye_power(s),
            'forward_defense':forward_shield.contract(s),
            'forward_explorer':forward_explorer.contract(s,tomllib.loads(source_text)),
            # DRONE-001 (v39): the study maintenance fleet (S&E 51-54 STUDY / HOLD) and the L3 spine crawler scenario WF_DRONE_SCENARIO v1.
            'drones':{'fleet':drone_fleet.contract(s),'demo':drone_demo.contract(s),'routes':drone_routes.contract(s)},
            'radiator_health':radiator_health.contract(s),
            'power':power_contract(s),
            # P1-008: hub mechanisms per rotor, OPEN sizing/losses, service paths and PROTOTYPE display states.
            'rotor_interface':rotor_interface.contract(s),
            'crew_transfer':crew_transfer.contract(s),
            # IND-001 5.1 (v18): the induction route graph (rail, stops, legs, ladders, openings) for a runtime; PROTOTYPE, docked pose.
            'induction_route':graph,
            # SNAV-001 (v33): the Ship Navigator registry (49_SHIP_NAVIGATOR): modules, rail nav nodes, opening edges, hotspots, modes.
            'navigator':ship_navigator.contract(s,tomllib.loads(source_text),graph,crew_dynamics.nav(s),habitat_ring.ring_count(s)),
            # SPACE-030 (v40): the Space Navigator's Solar System chart references (55_SPACE_NAVIGATOR; sizes and orbit shapes, no epoch).
            'space_navigator':space_navigator.contract(space_navigator.load()),
            # Q50/Q51 (v24): Seraph's post, niche and workshop service path; the Garden expansion state.
            'interior_states':route_fitout.interior_contract(s),
            # FUT-005 (v19): the First Ignition timeline file, its hash, phases, marks and control bindings.
            'flight_timeline':flight_timeline_contract(s,spec_text,source_text),
            # PHYS-001 (v27): local crew/object dynamics: frames, signed rings, modes, transitions, profiles and fixtures (46/47).
            # PHYS-002 (v28): dynamics.stages, the collision stages on the real route (trunk passage and handrails, ring A's induction rooms).
            # J01 (v41): dynamics.stages.ring_rooms.rings.RING_B, ring B's sector clear volumes for the body mode.
            # EXC-001 (v43): dynamics.stages.boarding / access_b / tube_b / circuit, the station-to-ring excursion.
            'dynamics':crew_dynamics.contract(s),
            'mission':{k:quantity(v) for k,v in s['mission'].items()},
            'habitat':{'low_thrust_limit':quantity(s['habitat']['low_thrust_limit']),
                       'low_thrust_gravity_tilt_deg':{'known':True,'value':d['low_thrust_gravity_tilt_deg'],'unit':'deg','canon_status':'DERIVED','evidence_ref':'low_thrust_limit'},
                       'rings':rings(s)},
            # OD-005, OD-006 and OD-011 became WORKING on 2026-09-27 (09_OPEN_DESIGN_ITEMS); OD-013 (magnetic bearings) was added OPEN in capture 27c.
            'open_items':[f'OD-{j:03}' for j in range(1,14) if j not in (5,6,11)]}


def write(root=ROOT,output=None):
    s,_,spec_text,source_text=load(root)
    path=output or root/OUTPUT;path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(contract(s,spec_text,source_text),indent=1)+'\n')
    return path


def check(root=ROOT,path=None):
    s,_,spec_text,source_text=load(root)
    return json.loads((path or root/OUTPUT).read_text())==contract(s,spec_text,source_text)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=ROOT);p.add_argument('--output',type=Path);p.add_argument('--check',action='store_true')
    a=p.parse_args()
    if a.check:
        ok=check(a.root.resolve(),a.output);print('WF_SIM_RIG','CURRENT' if ok else 'STALE');sys.exit(0 if ok else 1)
    print('WF_SIM_RIG written',write(a.root.resolve(),a.output))
