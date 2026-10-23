"""Read saved P0 assets and check geometry, provenance and relative links.

--scope limits the slow posed checks to named groups (GROUPS) for an iteration; the core checks (production file set, spec and
provenance hashes, IDs, links, per-file assertions, interface pairing, the rig contract, anchors and proxies, the evaluated envelope,
EYE rays and the saved forward and radiator checks) always run. The report's `scope` lists what ran and what was omitted; only the
default `--scope all` is a whole-ship inspection."""
from pathlib import Path
import argparse
import collections
import json
import math
import sys
import bpy
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree
ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT/'src/wayfarer'),str(ROOT/'src/wayfarer/build')]
import spec as spec_module
from spec import load,digest,derived,buildable_configurations
from common import pose_drive_state, pose_configuration, pose_timeline, pose_transfer
from build import COMPONENTS, SUBSYSTEMS, RETIRED, RING_FAMILY
import sim_rig
import hull_geometry
import layout
import habitat_interior
import route_fitout
import production_detail
import modules
import habitat_ring
import drive_manifold
import drive_hot_section
import power_storage
import rotor_interface
import crew_transfer
import human_entry
import thermal_geometry
import forward_shield
import radiator_health
import importlib.util
# forward_inspect lives next to this file; loading it by path avoids putting this directory (and its inspect.py) ahead of the standard library.
_spec=importlib.util.spec_from_file_location('forward_inspect',Path(__file__).resolve().with_name('forward_inspect.py'))
forward_inspect=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(forward_inspect)
_spec=importlib.util.spec_from_file_location('radiator_inspect',Path(__file__).resolve().with_name('radiator_inspect.py'))
radiator_inspect=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(radiator_inspect)
import time
_STAGE=[time.monotonic()]
def stage(name):
    """Print the seconds spent since the previous stage (WF_INSPECT_STAGE), for profiling the inspection."""
    now=time.monotonic();print(f'WF_INSPECT_STAGE {name} {now-_STAGE[0]:.2f}',flush=True);_STAGE[0]=now


def detail_checks(s,root,path,objects,detail_assets):
    """Modular detail (docs/MODULES.md). In a detail asset: only production detail, its contract stamps current (anchor frame, pack inputs).
    In any host: exactly one detail instance per pack assembly anchored there, the registered asset, parented to its anchor object with an
    identity local transform, and the anchor object at its pure frame. Returns a short report."""
    reg=modules.registry(root);anchors=modules.anchors(s,reg);asm=modules.assemblies(s['detail_packs']);out={}
    stem=path.stem
    if stem in detail_assets:
        a=detail_assets[stem];t=asm[a];coll=bpy.data.collections[stem]
        assert coll.get('detail_assembly')==a and coll.get('anchor')==t['anchor'],f'{stem}: built for {coll.get("detail_assembly")} at {coll.get("anchor")}'
        assert coll.get('anchor_hash')==modules.anchor_hash(reg,anchors[t['anchor']]),f'{stem}: built against another frame of {t["anchor"]}: rebuild it (module build)'
        assert coll.get('inputs_hash')==modules.inputs_hash(root,t['pack']),f'{stem}: pack {t["pack"]} changed since it was built: rebuild it (module build)'
        assert all(o.get('kind')=='production_detail' and o.get('detail_pack')==t['pack'] for o in objects),f'{stem}: only the pack\'s production detail'
        assert all(o.parent is None for o in objects),f'{stem}: detail sits in the anchor frame, unparented'
        art=bpy.data.collections.get(f'ART_{stem}');authored=[o for o in (art.all_objects if art else []) if o.library is None and o.type=='MESH']
        anchor_now=modules.anchor_hash(reg,anchors[t['anchor']])
        assert all(o.get('wf_adopted') and o.get('wf_authored_against')==anchor_now for o in authored),f'{stem}: hand-authored detail not adopted or authored against another anchor frame: module build, then review and module rebind'
        out=dict(assembly=a,objects=len(objects),authored=len(authored),enabled=production_detail.enabled(s,a))
    host=stem[3:] if stem.startswith('WF_') else stem
    want={a:t for a,t in asm.items() if anchors[t['anchor']]['host']==host}
    have={o['detail_assembly']:o for o in objects if o.get('kind')=='detail_instance'}
    assert set(have)==set(want),f'{stem}: detail instances {sorted(have)}, registered {sorted(want)}'
    for a,o in have.items():
        q=anchors[want[a]['anchor']]
        assert o.instance_collection is not None and o.instance_collection.name==modules.asset_name(a),f'{o.name}: links {o.instance_collection}'
        assert (o.parent.name if o.parent else None)==q['object'],f'{o.name}: parent {o.parent} is not the anchor object {q["object"]}'
        assert all(abs(o.matrix_basis[i][j]-(1.0 if i==j else 0.0))<1e-9 for i in range(4) for j in range(4)),f'{o.name}: local transform not identity'
        assert all(abs(o.matrix_parent_inverse[i][j]-(1.0 if i==j else 0.0))<1e-9 for i in range(4) for j in range(4)),f'{o.name}: parent inverse not identity'
        assert o.get('anchor_hash')==modules.anchor_hash(reg,q),f'{o.name}: linked against another frame of {want[a]["anchor"]}'
        if q['object'] and q.get('motion'):
            # A rotor or despun drum: at its anchor's centre, turning only about +X (its driver sets the angle; the rest angle is checked
            # where the presets pose it, shot_tools.pose_preset).
            m=o.parent.matrix_basis
            assert all(abs(m[i][3]-q['matrix'][i][3])<1e-6 for i in range(3)),f'{q["object"]}: not at the centre of {want[a]["anchor"]}'
            assert abs(m[0][0]-1)<1e-9 and all(abs(m[0][k])<1e-9 and abs(m[k][0])<1e-9 for k in (1,2)),f'{q["object"]}: turns about another axis than +X'
        elif q['object']:
            m=o.parent.matrix_basis
            assert all(abs(m[i][j]-q['matrix'][i][j])<1e-6 for i in range(4) for j in range(4)),f'{q["object"]}: not at the anchor frame of {want[a]["anchor"]}'
            assert (o.parent.parent.name if o.parent.parent else None)==q['parent'],f'{q["object"]}: parent is not {q["parent"]}'
        out.setdefault('instances',[]).append(a)
    return out


def mesh_volume(data):
    """Absolute enclosed volume of a closed mesh (signed tetrahedra over a fan triangulation of every polygon)."""
    total=0.0
    for poly in data.polygons:
        v=[data.vertices[i].co for i in poly.vertices]
        for k in range(1,len(v)-1):total+=v[0].dot(v[k].cross(v[k+1]))/6
    return abs(total)


def extent(points):
    lo=[min(p[i] for p in points) for i in range(3)]
    hi=[max(p[i] for p in points) for i in range(3)]
    return {'min_m':lo,'max_m':hi,'size_m':[hi[i]-lo[i] for i in range(3)]}


def evaluated(frame):
    """World-space evaluated meshes of every visible instance at a frame."""
    bpy.context.scene.frame_set(frame);records=[]
    for instance in bpy.context.evaluated_depsgraph_get().object_instances:
        obj=instance.object
        if obj.type not in {'MESH','CURVE'}:continue
        data=obj.to_mesh();vs=[instance.matrix_world@v.co for v in data.vertices];fs=[tuple(p.vertices) for p in data.polygons];obj.to_mesh_clear()
        if vs and fs:records.append({'name':obj.name,'kind':obj.get('kind'),'vs':vs,'fs':fs,
                                     'lo':Vector([min(v[i] for v in vs) for i in range(3)]),'hi':Vector([max(v[i] for v in vs) for i in range(3)])})
    return records


def blade_plates(s,d):
    """Fixed blade plates from the shared blade dimensions: origin at the aft inner corner, unit u (along), v (across), n (normal)."""
    out=[]
    for j in range(s['radiators']['count']):
        a=math.radians(s['prototype']['radiator_phase_deg']+j*120);r=Vector((0,math.cos(a),math.sin(a)))
        out.append({'O':Vector((d['aft_x_m'],0,0))+r*d['inner_radius_min_m'],'u':Vector((d['cos'],0,0))-r*d['sin'],'v':Vector((d['sin'],0,0))+r*d['cos'],
                    'L':d['blade_length_m'],'W':d['net_width_m']})
    return out


def plate_distance(q,b):
    w=Vector(q)-b['O'];su=min(max(w.dot(b['u']),0),b['L']);sv=min(max(w.dot(b['v']),0),b['W'])
    return (Vector(q)-(b['O']+b['u']*su+b['v']*sv)).length


def radiator_pose(s,d):
    """Largest distance of any evaluated radiator-cell bound-box corner from the fixed blade plates."""
    plates=blade_plates(s,d);worst=0.0
    for instance in bpy.context.evaluated_depsgraph_get().object_instances:
        if instance.object.get('kind')!='radiator_cell':continue
        for corner in instance.object.bound_box:
            worst=max(worst,min(plate_distance(instance.matrix_world@Vector(corner),b) for b in plates))
    return worst


def blade_matrices():
    """World matrices of the three radiator instances in the evaluated scene, keyed by component id."""
    return {i.object['component_id']:[list(r) for r in i.matrix_world] for i in bpy.context.evaluated_depsgraph_get().object_instances if str(i.object.get('component_id','')).startswith('WF.RADIATOR.0')}


SKIN={'hull_shell'}


def drive_readback(obj,path,index,deps):
    ob=obj.evaluated_get(deps)
    if path in {'hide_viewport','hide_render'}:return float(getattr(ob,path))
    if path==drive_manifold.EXHAUST_END:return ob.data.splines[0].points[4].co[index]
    return ob.data.bevel_depth if path=='data.bevel_depth' else (ob.scale[index] if path=='scale' else ob.color[index])


def debug_layers_shown(deps):
    """Debug layers whose geometry the depsgraph actually instances (viewport evaluation)."""
    return {i.object.get('debug_layer') for i in deps.object_instances if str(i.object.get('kind','')).startswith('debug')}


def drive_mismatch(s,values):
    """Pose the linked drive control in memory; largest difference between evaluated drivers and drive_manifold.display().
    Settings the state leaves out (debug toggles, thrust_level) return to their saved values, as display() assumes."""
    pose_drive_state({**drive_manifold.SAVED_SETTINGS,**values});deps=bpy.context.evaluated_depsgraph_get()
    return max(abs(drive_readback(bpy.data.objects[n],p,i,deps)-want) for (n,p,i),want in drive_manifold.display(s,values).items())


def propulsion_checks(s,objects):
    """P1F: drive hierarchy, neutral control, drivers, actions and optics as drive_manifold defines them."""
    dm=drive_manifold;g=dm.geometry(s);ob=bpy.data.objects
    def points(name):return [tuple(p.co[:3]) for sp in ob[name].data.splines for p in sp.points]
    def same(a,b):return len(a)==len(b) and all((Vector(p)-Vector(q)).length<1e-5 for p,q in zip(a,b))
    for j in range(1,5):
        assert same(points(f'Magnetic_Flow_Domain_{j:02}'),g['branches'][j-1]) and same(points(f'PLASMA_BRANCH_{j}'),g['branches'][j-1]),f'Flux path {j}'
        assert all(same(points(f'GATE_BEAM_{k}_L{j}'),g['gate_beams'][(k,j)]) for k in 'AB'),f'Gate beams L{j}'
        chain=[f'Nozzle_{j:02}',f'DRIVE_NOZZLE_{j}',f'DRIVE_FLUX_CHANNEL_{j}','DRIVE_MANIFOLD','DRIVE_CONVERGENCE_THROAT','DRIVE_COMMON_PLASMA','WF_DRIVE_ROOT']
        assert all(ob[a].parent==ob[b] for a,b in zip(chain,chain[1:])),f'Drive hierarchy {j}'
        assert ob[f'GATE_L{j}']['conditions']==f'LATTICE_SECTOR_{j}' and ob[f'LATTICE_SECTOR_{j}']['flux_channel']==f'DRIVE_FLUX_CHANNEL_{j}','Gate -> lattice -> channel map'
    assert all(same(points(f'OPTICAL_BEAM_{k}'),g['lasers'][k]['path']) and same(points(f'OPTICAL_BORE_{k}'),g['routes'][k]['bore']) for k in 'AB'),'Optical trunk and bore'
    assert all(same(points(f'OPTICAL_LEG_{k}_{leg["index"]}'),leg['points']) for k in 'AB' for leg in g['routes'][k]['legs']),'Optical corridor legs'
    hub=ob['SPINE_TERMINATION_HUB'];xs=[v.co.x for v in hub.data.vertices]
    assert abs(min(xs)-g['hub']['x0'])<1e-5 and abs(max(xs)-g['hub']['x1'])<1e-5 and abs(max(math.hypot(v.co.y,v.co.z) for v in hub.data.vertices)-g['hub']['radius'])<1e-5,'Spine hub'
    assert (ob['IF_SPINE_TERMINATION'].matrix_world.translation-Vector((g['hub']['x1'],0,0))).length<1e-5,'IF_SPINE_TERMINATION'
    for n,rings in (('PLASMA_COMMON',2),('PLASMA_THROAT',len(g['throat_rings']))):
        assert len(ob[n].data.polygons)==32*(rings-1)+2 and all(r_[1]==0 for r_ in g['throat_rings']),f'{n} must be a solid column with end caps'
    assert not any(n in ob for n in ('AXIAL_OPTICAL_BEAM','AXIAL_OPTICAL_CHANNEL','OPTICAL_SHIELD_PLUG','BEAM_COMBINER','OPTICAL_FOCUS_STAGE','OPTICAL_DISTRIBUTOR')),'Retired optics objects'
    ring=ob['H2_INJECTION_RING'];rp=[tuple(p.co[:3]) for sp in ring.data.splines for p in sp.points];ir=drive_hot_section.injection_ring(s)
    assert all(abs(q[0]-ir['x'])<1e-5 and abs(math.hypot(q[1],q[2])-ir['radius'])<1e-5 for q in rp) and abs(ring.data.bevel_depth-ir['tube'])<1e-6 and (ob['IF_H2_INJECTION'].matrix_world.translation-Vector((ir['x'],0,0))).length<1e-5,'H2 injection ring'
    for y in dm.nozzle_yokes(s):
        for r_ in y['rings']:
            vs=[v.co for v in ob[r_['name']].data.vertices];rr=[math.hypot(v.y-y['axis'][0],v.z-y['axis'][1]) for v in vs]
            assert all(min(abs(q-r_['r_in']),abs(q-r_['r_out']))<1e-5 for q in rr),r_['name']
            assert abs(min(v.x for v in vs)-r_['x0'])<1e-5 and abs(max(v.x for v in vs)-r_['x1'])<1e-5 and abs(ob[r_['name']]['coil_standoff_m']-s['drive_hot_section']['yoke_standoff_m'])<1e-9,r_['name']
        for st_ in y['straps']:assert same(points(st_['name']),st_['points']),st_['name']
    for o in objects:
        if o.get('kind')=='drive_node':assert o.matrix_world==Matrix.Identity(4),o.name
    ctrl=ob[dm.CONTROL]
    want={**dm.neutral(s),**dm.SAVED_SETTINGS}
    assert all(math.isclose(ctrl[k],v) for k,v in want.items()) and ctrl.animation_data is None,'Drive control must be saved neutral with no action assigned'
    for layer,toggle in dm.DEBUG_LAYERS.items():
        inst=ob[f'DRIVE_{layer}']
        assert inst.parent==ob['WF_DRIVE_ROOT'] and inst.instance_collection.name==f'WF_{layer}' and inst.instance_collection.library.filepath.endswith(f'WF_{layer}.blend'),inst.name
        assert inst.hide_viewport and inst.hide_render and inst['toggle']==f'{dm.CONTROL}["{toggle}"]',f'{inst.name} must be saved hidden and name its toggle'
    drivers=0
    for name,path,index,expression in dm.drivers(s):
        owner=ob[name].data if path.startswith('data.') else ob[name];prop=path[5:] if path.startswith('data.') else path
        fc=next(f for f in owner.animation_data.drivers if f.data_path==prop and (index==-1 or f.array_index==index))
        assert fc.driver.expression==expression and fc.driver.is_valid and fc.driver.is_simple_expression,(name,path)
        assert all(v.targets[0].id==ctrl and v.targets[0].data_path==f'["{dm.VARIABLES[v.name]}"]' for v in fc.driver.variables),(name,path)
        drivers+=1
    tables=dm.actions(s);owned=[a for a in bpy.data.actions if a.get('wf_owner')=='wayfarer.p0']
    assert sorted(a.name for a in owned)==sorted(tables),'Drive actions'
    for action in owned:
        spec=tables[action.name]
        assert action.use_fake_user and len(action.slots)==1 and list(action.frame_range)==[float(x) for x in spec['frame_range']],action.name
        curves={f.data_path:f for layer in action.layers for strip in layer.strips for bag in strip.channelbags for f in bag.fcurves}
        assert set(curves)=={f'["{p}"]' for p in dm.PROPS},action.name
        for prop in dm.PROPS:
            kps=curves[f'["{prop}"]'].keyframe_points
            assert [(k.co[0],round(k.co[1],6),k.interpolation) for k in kps]==[(float(f),round(v[prop],6),'LINEAR') for f,v in spec['keys']],(action.name,prop)
    return {'drivers':drivers,'actions':sorted(tables),'hierarchy_root':'WF_DRIVE_ROOT','control_saved':'NEUTRAL (drive off)'}


def tile_block_ok(o,tiles):
    """A tile mesh holds one closed solid per tile, in drive_hot_section order, inside that tile's axial and radial bounds."""
    per=4*(drive_hot_section.TILE_STEPS+1);vs=o.data.vertices
    if len(vs)!=per*len(tiles):return False
    for i,t in enumerate(tiles):
        for v in vs[i*per:(i+1)*per]:
            r=math.hypot(v.co.y,v.co.z)
            if not (t['x0']-1e-5<=v.co.x<=t['x1']+1e-5 and t['r_in']-1e-5<=r<=t['r_out']+1e-5):return False
    return True


def hot_section_checks(s,objects,name):
    """AFT-002: plasma-facing liners and coil designation (WF_PROPULSION), nozzle bands (WF_NOZZLE), pickups (WF_STRUCTURE), feed lines (WF_STORAGE)."""
    hs=drive_hot_section;ob=bpy.data.objects;mh=s['propulsion']['magnet_hardware'];pf=s['propulsion']['plasma_facing']
    by={o.name:o for o in objects};report={}
    def coil_designated(o,coil_set):
        assert o['coil_set']==coil_set and o['conductor']==mh['conductor'] and o['flux_pinning_rule']==mh['flux_pinning_rule'] and o['conductor_canon_status']=='WORKING' and o['conductor_source_ref']==mh['source_ref'] and o['conductor_architecture_ref']=='hts_coil_architecture',o.name
        # geometry stays PROTOTYPE for every coil; WORKING appears only in the conductor_* designation keys
        assert o['canon_status']=='PROTOTYPE' and o['source_ref']!='hts_coil_architecture',o.name
        if coil_set=='seed_manifold':
            assert o['wf_status']=='PROTOTYPE' and o['wf_source'].startswith('local PROTOTYPE'),o.name
        assert o['seed_field_calibration_T']==5.0 and o['seed_field_calibration_status']=='BASELINE' and o['seed_field_calibration_source_ref']=='baseline_seed_field',o.name
        assert 'amplification' in o['field_note'] and not any('amplif' in k for k in o.keys() if k!='field_note'),o.name
        assert all(f'({hs.open_text(ref)})' in o['open_quantities'] for k,ref in hs.open_keys(s).items() if k.startswith('propulsion.magnet_hardware.')),o.name
    def pfc_ok(o,zone,tiles,modules):
        assert o.get('kind')=='pfc_liner' or o.get('kind')=='pfc_band',o.name
        assert o['zone']==zone and o['replaceable'] is True and o['tile_count']==len(tiles) and o['axial_modules']==modules and o['canon_status']=='WORKING' and o['source_ref']==pf['evidence_ref'],o.name
        assert o['material_stack']==' -> '.join(pf['material_stack']),o.name
        assert all(str(o[k]).startswith('OPEN OD-025') for k in ('heat_flux','erosion_rate','module_size','replacement_interval','exact_material')),o.name
        assert tile_block_ok(o,tiles),f'{o.name}: tiles differ from drive_hot_section'
    if name=='WF_PROPULSION.blend':
        seeds=sorted(o.name for o in objects if o.get('kind')=='seed_coil');assert seeds==['SEED_COIL_1','SEED_COIL_2'],seeds
        for n in seeds:coil_designated(by[n],'seed_manifold')
        for zone,obj,parent,label in [(hs.CORE,'PFC_LINER_CORE','DRIVE_FUSION_CORE','fusion_core'),(hs.THROAT,'PFC_LINER_THROAT','DRIVE_CONVERGENCE_THROAT','convergence_throat')]:
            tiles=hs.liner_tiles(s,zone);assert by[obj].parent==by[parent],obj
            pfc_ok(by[obj],label,tiles,max(t['module'] for t in tiles)+1)
        assert len([o for o in objects if o.get('kind')=='pfc_liner'])==2,'One liner mesh per zone'
        report['liners']={'core_tiles':len(hs.liner_tiles(s,hs.CORE)),'throat_tiles':len(hs.liner_tiles(s,hs.THROAT))}
    elif name=='WF_NOZZLE.blend':
        coils=drive_manifold.nozzle_coils(s);assert sorted(o.name for o in objects if o.name.startswith('Nozzle_Coil_'))==[c['name'] for c in coils]
        bands=hs.liner_tiles(s,hs.NOZZLE)
        for c in coils:
            o=by[c['name']];pts=curve_points(o);assert all(abs(q[0]-c['x'])<1e-5 and abs(math.hypot(q[1],q[2])-c['ring_radius'])<1e-5 for q in pts) and abs(o.data.bevel_depth-c['tube'])<1e-6,c['name']
            coil_designated(o,'nozzle')
            tiles=[t for t in bands if t['coil']==c['index']]
            if tiles:o=by[f'PFC_NOZZLE_STRIKE_{c["index"]:02}'];pfc_ok(o,'nozzle_adjacent',tiles,1);assert o['strike_module'] and o['liner_performance'].startswith('UNKNOWN'),o.name
        assert len([o for o in objects if o.get('kind')=='pfc_band'])==len(s['drive_hot_section']['nozzle_strike_module_coils'])
        report['bands']=len(bands)
    elif name=='WF_STRUCTURE.blend':
        for q in drive_manifold.nozzle_pickups(s):
            pts=curve_points(by[q['name']]);assert len(pts)==2 and (Vector(pts[0])-Vector(q['a'])).length<1e-5 and (Vector(pts[1])-Vector(q['b'])).length<1e-5,q['name']
        sp=drive_manifold.spine_span(s);xs=[v.co.x for v in by['Structural_Spine'].data.vertices]
        assert abs(min(xs)-sp[0])<1e-5 and abs(max(xs)-sp[1])<1e-5,'Structural_Spine ends on the terminated hub'
        assert all(by[q['name']]['attach_yoke']==f"Nozzle_Yoke_{q['nozzle']}_{q['yoke']}" and by[q['name']]['geometry_basis']==q['geometry_basis'] for q in drive_manifold.nozzle_pickups(s)),'Pickup attachment'
        report['pickups']=4;report['spine_x']=list(sp)
    elif name=='WF_STORAGE.blend':
        lines=hs.cryo_feed(s);assert sorted(o.name for o in objects if o.get('kind')=='cryo_feed_line')==[l['name'] for l in lines]
        for l in lines:
            o=by[l['name']];pts=curve_points(o)
            assert len(pts)==len(l['points']) and all((Vector(u)-Vector(v)).length<1e-5 for u,v in zip(pts,l['points'])) and abs(o.data.bevel_depth-l['radius'])<1e-6,l['name']
            assert o['fluid']==l['family'] and o['terminus']==l['terminus'] and str(o['quantity']).startswith('OPEN OD-026') and o['storage_stack_status']=='WORKING' and str(o['engineering_status']).startswith('OPEN OD-026'),l['name']
            assert o['storage_stack_source_ref']=='cryogenic_storage_stack' and by[l['tank']]['fuel_family']==l['family'] and 'PROTOTYPE' in by[l['tank']]['family_assignment'],l['name']
            for label,point in [('TANK',l['a']),('SHIELD',l['shield_point']),('CORE' if l['terminus']=='core' else 'INJECTION',l['b'])]:
                i=by[f'IF_CRYO_FEED_{label}_{l["index"]:02}'];assert (i.matrix_world.translation-Vector(point)).length<1e-5 and str(i['engineering_status']).startswith('OPEN OD-026'),i.name
        report['feed_lines']=len(lines)
    return report


def power_storage_checks(s,objects):
    """P1-007: packs exactly where power_storage puts them, statuses per layer, control saved at step 0, black-start keys."""
    ob=bpy.data.objects;layers={'MAIN_BATTERY':'main_battery','PULSE_BANK':'pulse_bank','SURVIVAL_RESERVE':'survival_reserve'}
    packs=power_storage.packs(s)
    assert {o.name for o in objects if o.get('kind')=='power_storage'}=={p['name'] for p in packs},'Storage packs'
    for p in packs:
        o=ob[p['name']];field=s['power']['storage'][layers[p['layer']]]
        assert all((o.matrix_world@v.co-Vector(c)).length<1e-5 for v,c in zip(o.data.vertices,p['corners'])),p['name']
        assert o['layer']==p['layer'] and o['canon_status']==field['canon_status'] and o['source_ref']==field['source_ref'],p['name']
        assert (ob[p['interface']].matrix_world.translation-Vector(p['center'])).length<1e-5,p['interface']
    for f in power_storage.pack_interfaces(s):
        assert (ob[f['name']].matrix_world.translation-Vector(f['at'])).length<1e-5,f['name']
    ctrl=ob[power_storage.CONTROL]
    assert all(math.isclose(ctrl[k],v) for k,v in power_storage.step_state(0).items()) and ctrl.animation_data is None,'Storage control must be saved at step 0 with no action assigned'
    spec=power_storage.action(s);owned=[a for a in bpy.data.actions if a.get('wf_owner')=='wayfarer.p0']
    assert [a.name for a in owned]==[power_storage.ACTION],'Black-start action'
    action=owned[0]
    assert action.use_fake_user and len(action.slots)==1 and list(action.frame_range)==[float(x) for x in spec['frame_range']],action.name
    curves={f.data_path:f for layer in action.layers for strip in layer.strips for bag in strip.channelbags for f in bag.fcurves}
    assert set(curves)=={f'["{k}"]' for k in power_storage.PROPS},'Black-start channels'
    for prop in power_storage.PROPS:
        kps=curves[f'["{prop}"]'].keyframe_points
        assert [(k.co[0],k.co[1],k.interpolation) for k in kps]==[(float(f),v[prop],'CONSTANT') for f,v in spec['keys']],prop
    return {'packs':[p['name'] for p in packs],'interfaces':len(power_storage.pack_interfaces(s)),'ride_through':len(power_storage.ride_through_points(s)),
            'action':power_storage.ACTION,'action_keys':len(spec['keys']),'control_saved':'STEP 0 (cold ship)'}
def curve_points(o):
    return [tuple(p.co[:3]) for sp in o.data.splines for p in sp.points]


def rotor_interface_checks(s,objects,name):
    """P1-008: hub parts exactly where rotor_interface puts them (stationary in the vehicle frame, rotating in the rotor frame),
    ring-stop lock pins, interfaces, saved mechanism state and action keys per rotor slot."""
    ob=bpy.data.objects;same=lambda o,vs:len(o.data.vertices)==len(vs) and all((v.co-Vector(c)).length<1e-5 for v,c in zip(o.data.vertices,vs))
    near=lambda a,b:(Vector(a)-Vector(b)).length<1e-5
    if name==rotor_interface.SUBSYSTEM:
        parts=rotor_interface.stationary(s)
        assert {o.name for o in objects if o.get('kind')=='rotor_mechanism'}=={p['name'] for p in parts},'Stationary hub parts'
        for p in parts:
            o=ob[p['name']];assert o.parent is None and same(o,p['vertices']),p['name']
            assert o['function']==p['function'] and o['source_ref']==rotor_interface.SOURCES[p['function']] and o['side']=='STATIONARY',p['name']
        for sp in rotor_interface.spokes(s):
            pts=curve_points(ob[sp['name']]);assert near(pts[0],sp['a']) and near(pts[-1],sp['b']),sp['name']
        side=[f for f in rotor_interface.interfaces(s) if f['side']=='STATIONARY']
        for f in side:assert near(ob[f['name']].matrix_world.translation,f['at']),f['name']
        # Retracted ring-stop lock pins (MEC-011 geometry OPEN): where rotor_interface puts them, each with an OPEN drive interface.
        locks=rotor_interface.ring_stop_locks(s)
        assert {o.name for o in objects if o.get('kind')=='ring_stop_lock'}=={b['name'] for b in locks},'Ring-stop locks'
        for b in locks:
            o=ob[b['name']];pts=curve_points(o)
            assert o.parent is None and near(pts[0],b['a']) and near(pts[-1],b['b']) and near(ob[b['drive']].matrix_world.translation,b['a']),b['name']
            assert o['source_ref']==rotor_interface.SOURCES['RING_STOP_LOCK'] and str(o['engineering_status']).startswith('OPEN'),b['name']
        return {'stationary_parts':len(parts),'spokes':len(rotor_interface.spokes(s)),'ring_stop_locks':len(locks),'interfaces':len(side)}
    parts=rotor_interface.rotating(s)
    assert {o.name for o in objects if o.get('kind') in ('rotor_mechanism','rotor_hub_drum')}=={p['name'] for p in parts},'Rotating hub parts'
    for p in parts:
        o=ob[p['name']];assert o.parent is ob[f"Rotor_{p['rotor']}"] and o.matrix_basis==Matrix.Identity(4) and same(o,p['vertices']),p['name']
    for f in (f for f in rotor_interface.interfaces(s) if f['side']=='ROTATING'):
        o=ob[f['name']];assert o.parent is ob[f"Rotor_{f['rotor']}"] and near(o.location,f['at']),f['name']
    assert not {o.name for o in objects if o.get('kind') in ('ring_stop_lock','habitat_burn_lock')},'Lock pins belong to WF_ROTOR_INTERFACE'
    saved=rotor_interface.saved_states(s)
    for rot in rotor_interface.rotors(s):
        ctrl=ob[rotor_interface.control(rot['index'])]
        assert ctrl.parent is None and ctrl.animation_data is None and all(math.isclose(ctrl[k],v) for k,v in saved['state'].items()),ctrl.name
        assert all(ctrl[k]==0 for k in rotor_interface.TURN_PROPS),f'{ctrl.name}: saved with the product rotation (spin_integrated 0)'
        # The rotation driver reads the control's spin_fraction (so a preset decides whether the ring turns) and, integrated, its spin_turned (FUT-007).
        fc=next(f for f in ob[f"Rotor_{rot['index']}"].animation_data.drivers if f.data_path=='rotation_euler' and f.array_index==0)
        assert fc.driver.is_valid and fc.driver.is_simple_expression and [(v.name,v.targets[0].id,v.targets[0].data_path) for v in fc.driver.variables]==[
            ('spin',ctrl,'["spin_fraction"]'),('turned',ctrl,'["spin_turned"]'),('integ',ctrl,'["spin_integrated"]')],ctrl.name
    owned={a.name:a for a in bpy.data.actions if a.get('wf_owner')=='wayfarer.p0'}
    specs=rotor_interface.actions(s);assert set(owned)==set(specs),'Rotor actions'
    for aname,spec in specs.items():
        action=owned[aname]
        assert action.use_fake_user and list(action.frame_range)==[float(x) for x in spec['frame_range']] and {sl.name_display for sl in action.slots}==set(spec['slots']),aname
        for layer in action.layers:
            for strip in layer.strips:
                for slot in action.slots:
                    keys=spec['slots'][slot.name_display];curves={f.data_path:f for f in strip.channelbag(slot).fcurves}
                    assert set(curves)=={f'["{k}"]' for k in [*rotor_interface.PROPS,*rotor_interface.TURN_PROPS]},aname
                    for prop in rotor_interface.PROPS:
                        interp='LINEAR' if prop=='spin_fraction' else 'CONSTANT'
                        assert [(k.co[0],k.co[1],k.interpolation) for k in curves[f'["{prop}"]'].keyframe_points]==[(float(f),v[prop],interp) for f,v in keys],(aname,slot.name_display,prop)
                    turned=rotor_interface.spin_turned(s,[(f,v['spin_fraction']) for f,v in keys])
                    got=[(k.co[0],k.co[1]) for k in curves['["spin_turned"]'].keyframe_points]
                    assert len(got)==len(turned) and all(math.isclose(a,float(f)) and math.isclose(b,v,abs_tol=1e-4) for (a,b),(f,v) in zip(got,turned)),(aname,slot.name_display,'spin_turned')
    return {'rotating_parts':len(parts),'saved_preset':saved['preset'],'actions':sorted(specs)}


def closure_checks(s,objects,stationary):
    """Q46: the closures exactly where crew_transfer.closures puts them, saved closed: the gates (stationary file) in the vehicle frame, the drum
    doors (habitat file) on their drum and the tube hatches on their rotor; each a ring segment."""
    ob=bpy.data.objects;closures=[q for j in s['human_entry']['vestibule_rotors'] for q in crew_transfer.closures(s,j) if (q['kind']=='PORT_GATE')==stationary]
    assert {o.name for o in objects if o.get('kind')=='transfer_closure'}=={q['name'] for q in closures},'Transfer closures'
    for q in closures:
        o=ob[q['name']];par={'PORT_GATE':None,'DRUM_DOOR':ob.get(f"Drum_{q['rotor']}"),'TUBE_HATCH':ob.get(f"Rotor_{q['rotor']}")}[q['kind']]
        vs,_=rotor_interface.solid(q['x0'],q['x1'],q['r0'],q['r1'],q['t0'],q['t1'])
        assert o.parent is par and len(o.data.vertices)==len(vs) and all((v.co-Vector(c)).length<1e-5 for v,c in zip(o.data.vertices,vs)),q['name']
    return len(closures)


def crew_transfer_checks(s,objects,name):
    """P1-001: crew parts exactly where crew_transfer puts them (stationary in the vehicle frame, rotating in the rotor frame),
    crew tubes ending on their sector's hatch, interfaces placed and paired."""
    ob=bpy.data.objects;near=lambda a,b:(Vector(a)-Vector(b)).length<1e-5
    if name==crew_transfer.SUBSYSTEM:
        parts=crew_transfer.stationary(s)
        assert {o.name for o in objects if o.get('kind') in ('crew_trunk','crew_passage')}=={q['name'] for q in parts},'Stationary crew parts'
        bores=crew_transfer.bores(s)
        for q in parts:
            o=ob[q['name']]
            if 'hollow' in q:
                # HUM-001 zone 2: a mesh inside its outer radius about its axis (connectors start on the ship axis), opened where bores cuts it.
                a=Vector(q['points'][0]) if q['role']=='TRUNK' else Vector((q['points'][0][0],0,0));b=Vector(q['points'][1]);e=(b-a).normalized()
                vs=[v.co for v in o.data.vertices]
                assert o.type=='MESH' and o.parent is None and all(((v-a)-e*(v-a).dot(e)).length<=q['radius']+1e-4 and -1e-4<=(v-a).dot(e)<=(b-a).length+1e-4 for v in vs),q['name']
                for c0,c1,r in bores[q['name']]:
                    # The cutters are 64-gons, so cut edges lie up to r (1 - cos(pi/64)) inside the true radius.
                    c0,c1=Vector(c0),Vector(c1);k=(c1-c0).normalized();r_in=r*math.cos(math.pi/64)-1e-4
                    assert not any(1e-4<(v-c0).dot(k)<(c1-c0).length-1e-4 and ((v-c0)-k*(v-c0).dot(k)).length<r_in for v in vs),f"{q['name']}: not opened"
                for _,_,r in crew_transfer.trims(s).get(q['name'],[]):
                    assert all(math.hypot(v.y,v.z)<=r+1e-4 for v in vs),f"{q['name']}: stands in the vestibule annulus"
                continue
            pts=curve_points(o)
            assert o.parent is None and len(pts)==len(q['points']) and all(near(a,b) for a,b in zip(pts,q['points'])) and math.isclose(o.data.bevel_depth,q['radius'],abs_tol=1e-6),q['name']
        assert {o.name for o in objects if o.get('kind')=='entry_fixture'}=={q['name'] for q in human_entry.trunk_fixtures(s)+human_entry.refuge_fixtures(s)},'Trunk and refuge fixtures'
        side=[f for f in crew_transfer.interfaces(s) if f['side']=='STATIONARY']
        for f in side:assert near(ob[f['name']].matrix_world.translation,f['at']),f['name']
        return {'stationary_parts':len(parts),'interfaces':len(side),'closures':closure_checks(s,objects,True)}
    parts=crew_transfer.rotating(s);hat=crew_transfer.sector_hatches(s)
    assert {o.name for o in objects if o.get('kind') in ('crew_vestibule','crew_passage','vestibule_strut','crew_bracket')}=={q['name'] for q in parts},'Rotating crew parts'
    # Q46: the human-entry vestibule and its guard rings are the despun transfer drum, parented to Drum_j (saved despun at the index).
    home=lambda q:ob[f"Drum_{q['rotor']}" if q.get('drum') else f"Rotor_{q['rotor']}"]
    for q in parts:
        o=ob[q['name']];assert o.parent is home(q) and o.matrix_basis==Matrix.Identity(4),q['name']
        if q.get('hollow') and q['role']=='COAST_TUBE':
            # HUM-001 zone 4: a hollow mitered tube, every vertex between its clear bore and its outer wall (measured in its own elbow segment); on
            # ring B, below the bulkhead's top face, between the neck's bore and the neck's wall (the bulkhead: the tube's wall).
            fr=crew_transfer.tube_frames_of(s,q['rotor'],dict(crew_transfer.sectors(s))[q['sector']]);neck=crew_transfer.tube_neck(s,q['rotor'])
            p0,d0=Vector(fr['points'][0]),Vector(fr['d'][0]);bad=[]
            for v in o.data.vertices:
                t=(v.co-p0).dot(d0)
                if neck and t<neck['wall']+1e-4:
                    x=((v.co-p0)-d0*t).length;lo,hi=neck['clear'],neck['outer'] if t<-1e-4 else q['radius']
                else:
                    x=crew_transfer.tube_radius_at(fr,tuple(v.co),1e-4);lo,hi=q['hollow'],q['radius']
                if not lo*math.cos(math.pi/48)-1e-4<=x<=hi+1e-4:bad.append(round(x,4))
            assert not bad,f"{q['name']}: not a hollow tube ({bad[:4]})"
        elif q.get('hollow'):
            # HUM-001 zone 3: a shell inside its ring envelope with an empty transit cavity, open toward the spine.
            rho=lambda v:math.hypot(v.y,v.z);w=q['wall'];vs=[v.co for v in o.data.vertices]
            assert all(q['x0']-1e-5<=v.x<=q['x1']+1e-5 and q['r0']-1e-5<=rho(v)<=q['r1']+1e-5 for v in vs),q['name']
            assert not any(q['x0']+w+1e-4<v.x<q['x1']-w-1e-4 and q['r0']+1e-4<rho(v)<q['hollow']*math.cos(math.pi/64)-1e-4 for v in vs),f"{q['name']}: cavity not open"
        elif q['shape']=='ring':
            vs,_=rotor_interface.solid(q['x0'],q['x1'],q['r0'],q['r1'],0.0,math.tau)
            assert len(o.data.vertices)==len(vs) and all((v.co-Vector(c)).length<1e-5 for v,c in zip(o.data.vertices,vs)),q['name']
        else:
            pts=curve_points(o);assert len(pts)==len(q['points']) and all(near(a,b) for a,b in zip(pts,q['points'])),q['name']
        if q.get('sector'):
            # The tube ends on its sector's hatch in the saved pose (frame 1).
            sector=ob[f"Sector_{q['rotor']}_{q['sector']}"];target=sector.matrix_world@Vector(hat['overhead_wall'])
            tip=o.matrix_world@Vector(q['points'][-1])
            assert (tip-target).length<1e-5,f"{q['name']} misses its sector hatch by {(tip-target).length}"
    for f in (f for f in crew_transfer.interfaces(s) if f['side'] in ('ROTATING','DRUM')):
        o=ob[f['name']];assert o.parent is ob[f"{'Drum' if f['side']=='DRUM' else 'Rotor'}_{f['rotor']}"] and near(o.location,f['at']),f['name']
    closure_checks(s,objects,False)
    for j in s['human_entry']['vestibule_rotors']:
        d=ob[f'Drum_{j}'];assert d.parent is None and near(d.location,ob[f'Rotor_{j}'].location) and math.isclose(d.rotation_euler.x,ob[f'Rotor_{j}'].rotation_euler.x,abs_tol=1e-6),d.name
    # HUM-001 zone 5: each hollow crew tube passes through its ring's inner hoop (rays along the run, on the axis and inside its outer radius).
    for rot in rotor_interface.rotors(s):
        cuts=crew_transfer.hoop_cuts(s,rot['index']);o=ob[f"Ring_{rot['index']}_Hoop_Inner"]
        if not cuts:continue
        tree=BVHTree.FromPolygons([v.co for v in o.data.vertices],[tuple(q.vertices) for q in o.data.polygons])
        for a,b,r in cuts:
            a,b=Vector(a),Vector(b);e=(b-a).normalized();n=e.cross(Vector((1,0,0))).normalized()
            for off in (Vector((0,0,0)),Vector((.8*r,0,0)),Vector((-.8*r,0,0)),n*.8*r,-n*.8*r):
                assert tree.ray_cast(a+off,e,(b-a).length)[0] is None,f"{o.name}: crew tube opening blocked at {tuple(round(x,2) for x in a+off)}"
    # HUM-001 zones 3-4: the vestibule and crew-tube fixtures ride on their rotors.
    fixtures={rot['index']:human_entry.ring_fixtures(s,rot['index']) for rot in rotor_interface.rotors(s)}
    assert {o.name for o in objects if o.get('kind')=='entry_fixture'}=={q['name'] for v in fixtures.values() for q in v},'Vestibule fixtures'
    drums={q['name'] for j in s['human_entry']['vestibule_rotors'] for q in human_entry.vestibule_fixtures(s,j)}
    assert all(ob[q['name']].parent is ob[f"{'Drum' if q['name'] in drums else 'Rotor'}_{j}"] and ob[q['name']].matrix_basis==Matrix.Identity(4) for j,v in fixtures.items() for q in v),'Vestibule fixtures ride on the drum, tube fixtures on the rotor'
    return {'rotating_parts':len(parts),'sector_links':len([q for q in parts if q.get('sector')]),'ring_fixtures':sum(len(v) for v in fixtures.values())}


CHECKED=SKIN|{'service_fitting','crew_refuge','power_storage','rotor_mechanism','ring_stop_lock','crew_trunk','crew_passage','crew_vestibule','transfer_closure','storeroom_shell','survival_envelope','exterior_hardware','comms_antenna','casing_detail'}
# Designed contacts, symmetric: fluid-cartridge spokes land on their cartridge; crew passages open into the trunk, the
# vestibule, the fittings, the refuge and the sector overhead walls (through the inner hoop, ending on the overhead panel that carries the
# OPEN hatch); struts end on the vestibule; spoke brackets and ladders end on the crew tubes.
MATES={'rotor_mechanism':{'rotor_mount'},
       'crew_passage':{'crew_trunk','crew_vestibule','crew_passage','service_fitting','crew_refuge','sector_pressure','ring_frame','sector_interior_overhead','crew_bracket','entry_fixture'},
       'crew_vestibule':{'vestibule_strut','crew_vestibule','entry_fixture'},
       'dock_capture_ring':{'service_fitting'},
       # HUM-001: the entry shells meet each other at the bulkheads; frames, leaves, rails, lights, panels and valves sit on them, on the trunk
       # or on the vestibule shell.
       'service_fitting':{'service_fitting'},
       'entry_fixture':{'service_fitting','entry_fixture','crew_trunk','crew_vestibule','crew_passage','crew_refuge','refuge_wall'},
       # The refuge leg: the inner pressure wall closes the refuge shell's inner face and is opened by the refuge port.
       'refuge_wall':{'crew_refuge','crew_passage'},
       # IND-001: the fit-out sits on the entry shells and fixtures (a bezel behind each panel), and its parts on each other (text on its
       # placard, frames over stringers). 3.1: on the trunk wall, and the landing's hatch-rim mark under the overhead panel; since Q46 on the
       # drum's walls and the crew tubes' bore.
       'route_fitout':{'service_fitting','entry_fixture','route_fitout','crew_trunk','sector_interior_overhead','crew_vestibule','crew_passage'},
       # Q46: a gate crosses its spine port's wall in the spine shell; a drum door rides on its opening's seal land (the frame); a tube hatch
       # crosses its collar's (or neck's) wall into the pocket beside it.
       'transfer_closure':{'crew_passage','entry_fixture','crew_vestibule'},
       # HUM-002: the storeroom port opens into the SP-45 shell; racks, nets, rails, light, panel and the hatch leaf stand on its walls.
       'storeroom_shell':{'crew_passage','storeroom_fixture','storeroom_stowage','entry_fixture'},
       # SP-46..54: masts stand in the hull skin, crawler docks on their rails, the text on its placard.
       'survival_envelope':{'hull_shell','survival_envelope'},
       # M4 slice 2: each casing boot's flange lies on the casing round its member's opening.
       'casing_boot':{'hull_shell'},
       # S02 slice 1: docking aids, floods and aft beacons stand on (or are flush in) the casing.
       'exterior_hardware':{'hull_shell','exterior_hardware','thrust_node','thrust_node_plate'},
       'comms_antenna':{'hull_shell','comms_antenna','thrust_node','thrust_node_plate'},
       'casing_detail':{'hull_shell','casing_detail'},
       # M7: the production layer sits on the walls, frames and fixtures of the route it details and on its own families.
       'production_detail':{'service_fitting','entry_fixture','route_fitout','production_detail','crew_trunk','crew_vestibule','crew_passage',
                            'sector_pressure','sector_interior_overhead','sector_interior_deck','ring_frame','hull_shell','dock_capture_ring',
                            'exterior_hardware','transfer_closure','vestibule_strut','crew_bracket'}}
CREW_KINDS={'crew_trunk','crew_passage'}


def route_sweep(s):
    """HUM-001 review: the suited body (human_entry.route_bodies) swept along the primary boarding route to every sector of both rings (on ring
    B through the tube neck) and into the storm refuge from the dock (route R) and from the spine ports (route E) against every built surface, docked, with both entry leaves open; per route (ring letter + sector) and zone the least margin
    (nearest surface less the suited radius) and its object.
    The mannequins and the deck the standing body stands on are left out. Sampled clear, not a continuous-motion proof."""
    import numpy as np
    f=human_entry.ports(s)[0];ctrl=bpy.data.objects['DOCK_ENTRY_CTRL'];keys=[f"{f['name']}_{w}_open" for w in ('outer','inner')];old=[ctrl[k] for k in keys]
    def hatches(values):
        for k,v in zip(keys,values):ctrl[k]=v
        ctrl.update_tag()
        for o in bpy.data.objects:
            if o.name.endswith('_Hatch_Hinge'):o.update_tag()
    pose_configuration(s,'DOCKED');hatches([1.0]*len(keys));pose_transfer(s,1.0)     # Q46: indexed transfer, every closure open
    records=[r for r in evaluated(1) if r['kind'] not in ('scale_reference','sector_interior_deck')];hatches(old);pose_transfer(s,0.0)
    R=s['human_entry']['mannequin']['suited_envelope_diameter_m']/2;lo=np.array([list(r['lo']) for r in records]);hi=np.array([list(r['hi']) for r in records]);trees={};out={}
    for k,bodies in human_entry.route_bodies(s).items():
        zones={}
        for zone,axis in bodies:
            for p in axis:
                q=np.array(p);best=(math.inf,None)
                for i in np.nonzero(np.sqrt((np.maximum(np.maximum(lo-q,0),q-hi)**2).sum(1))<R+1.0)[0]:
                    if i not in trees:trees[i]=BVHTree.FromPolygons(records[i]['vs'],records[i]['fs'])
                    hit=trees[i].find_nearest(Vector(p))
                    if hit[0] is not None and hit[3]<best[0]:best=(hit[3],records[i]['name'])
                if best[0]-R<zones.get(zone,(math.inf,))[0]:zones[zone]=(best[0]-R,best[1])
        out[k]={f'zone_{z}':{'margin_m':round(m,4),'nearest':n} for z,(m,n) in sorted(zones.items(),key=lambda z:str(z[0]))}
        bad={z:v for z,v in out[k].items() if v['margin_m']<-1e-4}
        assert not bad,f'HUM-001 route {k}: the suited envelope hits {bad}'
    return {'sectors':out,'bodies':sum(len(b) for b in human_entry.route_bodies(s).values()),'suited_envelope_m':2*R,
            'scope':'sampled clear: two-chord suited body every 0.1 m along the route, docked, entry leaves open; not a continuous-motion proof'}


def designed(a,b):
    """True for a designed contact between evaluated records a and b."""
    if b['kind'] in MATES.get(a['kind'],()) or a['kind'] in MATES.get(b['kind'],()):return True
    # Crew trunk and spine ports sit in the spine bore by design; Q46: each spine-port gate slides in a pocket of the spine shell (pocket OPEN).
    spine=lambda r:r['kind'] in CREW_KINDS or r['name'].startswith('Crew_Port_') and r['kind']=='transfer_closure'
    return (spine(a) and b['name']=='Structural_Spine') or (spine(b) and a['name']=='Structural_Spine')


def hull_contacts(frame):
    """Pairs of hull shell, service fitting, refuge, hub mechanism or crew part with any other geometry whose surfaces intersect
    (annotations excluded). Skin-to-skin pairs are skipped."""
    records=evaluated(frame);shells=[r for r in records if r['kind'] in CHECKED];contacts=[]
    order={id(r):i for i,r in enumerate(records)};trees={}      # first index of each record (records.index) and one BVH per record
    tree_of=lambda r:trees[id(r)] if id(r) in trees else trees.setdefault(id(r),BVHTree.FromPolygons(r['vs'],r['fs']))
    for shell in shells:
        tree=tree_of(shell)
        for other in records:
            if other is shell or other['name']==shell['name'] or other['kind'] in {'scale_reference','hull_envelope'}:continue
            if shell['kind'] in SKIN and other['kind'] in SKIN:continue
            if designed(shell,other):continue
            if other['kind'] in CHECKED and order[id(other)]<order[id(shell)]:continue
            if any(other['lo'][i]>shell['hi'][i] or other['hi'][i]<shell['lo'][i] for i in range(3)):continue
            if tree.overlap(tree_of(other)):contacts.append(f"{shell['name']}:{other['name']}")
    bpy.context.scene.frame_set(1)
    return len([r for r in shells if r['kind']=='hull_shell']),contacts


def timeline_checks(s,root,blades):
    """FUT-005: the First Ignition timeline file is current and named by the rig; at each mark, posed in memory on the saved vehicle, the
    rotor controls pass their rules and the rings turn only as fast as spin_fraction says, the drive drivers and the exhaust run follow the
    sample, the radiator and forward-defense displays match, and the blades stay fixed."""
    import flight_timeline as ft
    assert ft.check(root),'Stale simulations/wf_first_ignition_timeline.json'
    ps=ft.phases(s);ch=ft.channels(s,ps);marks={}
    for name in ft.marks(s,ps):
        values=ft.sample(s,name,ch,ps)['values'];by=ft.control_values(ch,values)
        pose_timeline(s,by)
        rotor=by[rotor_interface.control(1)];assert not rotor_interface.state_rules(rotor),(name,rotor_interface.state_rules(rotor))
        turn=[]
        for frame in [1,91]:
            bpy.context.scene.frame_set(frame)
            turn.append([bpy.data.objects[f'Rotor_{j}'].evaluated_get(bpy.context.evaluated_depsgraph_get()).rotation_euler.x for j in [1,2]])
        bpy.context.scene.frame_set(1)
        # FUT-007: integrated, the ring sits at its turn at the mark (phase + rate x spin_turned) and stays there; at rest that is the index angle.
        rate=s['habitat']['rpm']*math.tau/60/24;rev=rotor_interface.frames_per_turn(s)
        for j in range(2):
            want=math.radians(s['prototype']['rotor_phase_deg'][j])+(1 if j==0 else -1)*rate*rotor['spin_turned']
            assert rotor['spin_integrated']==1 and abs(math.remainder(turn[0][j]-want,math.tau))<1e-5,(name,j,turn[0][j],want)
            assert math.isclose(turn[1][j],turn[0][j],abs_tol=1e-9),(name,j)
            if rotor['spin_fraction']==0:
                assert abs(math.remainder(turn[0][j]-math.radians(s['prototype']['rotor_phase_deg'][j]),math.tau))<1e-5,(name,j,'off the index angle at rest')
        drive=by[drive_manifold.CONTROL];worst=drive_mismatch(s,drive);assert worst<1e-5,f'{name}: drive drivers off by {worst}'
        end=bpy.data.objects['PLASMA_EXHAUST_1'].evaluated_get(bpy.context.evaluated_depsgraph_get()).data.splines[0].points[4].co[0]
        assert abs(end-drive_manifold.exhaust_end_x(s,drive['thrust_level']))<1e-5,f'{name}: exhaust run end {end}'
        radiator=radiator_inspect.check_state(s,name,by[radiator_health.CONTROL])
        forward_inspect.check_state(s,name,by[forward_shield.CONTROL])
        assert blade_matrices()==blades,f'{name}: radiator blade matrices moved'
        marks[name]={'frame':ft.marks(s,ps)[name]['frame'],'spin_fraction':rotor['spin_fraction'],'ring_turn_deg':round(rotor['spin_turned']%rev/rev*360,4),'ring_locks':rotor['ring_locks_engaged'],'drive_active':drive['drive_active'],
                     'thrust_level':round(drive['thrust_level'],6),'exhaust_end_x_m':round(end,6),'radiator_step':radiator['glow_step'],
                     'acceleration_g':values['kinematics.acceleration_g'],'speed_c':values['kinematics.speed_c'],'distance_AU':values['kinematics.distance_AU']}
    return {'file':ft.table(s)['output'],'current':True,'rig_section':'flight_timeline','marks':marks}


GROUPS={'drive':'drive debug toggles, action keys, widest-pose hull check and each preset\'s drive drivers and exhaust run',
        'rotation':'each preset\'s ring rotation, full-revolution sector and interior samples and rotor sweep coverage',
        'hull':'each preset\'s hull BVH contacts (rotating presets at four ring angles)',
        'thermal':'each preset\'s fixed radiator blades, proxy plates and health state; radiator display poses and control sweep',
        'forward':'each preset\'s forward state and EYE rays; forward display poses',
        'timeline':'First Ignition timeline marks posed on the vehicle',
        'route':'induction route sweep with the hatches posed'}


def inspect(root=ROOT, output=None, scope=None):
    scope=set(GROUPS) if scope is None else set(scope)
    unknown=scope-set(GROUPS);assert not unknown,f'Unknown inspection groups {sorted(unknown)}; choose from {sorted(GROUPS)}'
    in_scope=lambda group:group in scope
    s,_,spec_text,source_text=load(root)
    assets=root/'assets/wayfarer'
    # Parts are relative to assets/wayfarer: studies embed their own inputs and are summarized separately.
    parts=lambda p:set(p.relative_to(assets).parts)
    files=sorted(p for p in assets.rglob('*.blend') if not {'milestones','studies'}&parts(p))
    # FGR-002: exactly the components, the subsystems and the one vehicle. Retired files (build.RETIRED) are moved to milestones/ by a full build.
    # Modular detail (docs/MODULES.md): plus one detail asset per registered pack assembly, under detail/.
    detail_assets={modules.asset_name(a):a for a in modules.assemblies(s['detail_packs'])}
    expected={*(f'components/WF_{n}.blend' for n in COMPONENTS),*(f'subsystems/WF_{n}.blend' for n in SUBSYSTEMS),s['vehicle']['asset']+'.blend',
              *(f'{modules.ASSET_DIR}/{n}.blend' for n in detail_assets)}
    found={str(p.relative_to(assets)) for p in files}
    assert found==expected,f'Production file set differs from components + subsystems + vehicle + detail assets: unexpected {sorted(found-expected)} (retired files are listed in RETIRED and moved by a full build: {sorted(RETIRED)}), missing {sorted(expected-found)}'
    studies={}
    blade_registry={}
    hot_report={};summaries={};graph={};area=0;detail_report={};interfaces={};interior_report={};drive_report=None;power_report=None;rotor_report={};crew_report={}
    interior_files={f'WF_{v}.blend':k for k,v in s['interior']['components'].items()}
    prev=None
    for path in files:
        if prev:stage(f'file:{prev}')
        prev=path.name
        bpy.ops.wm.open_mainfile(filepath=str(path))
        scene=bpy.context.scene
        assert scene['spec_hash']==digest(spec_text),f'Stale spec: {path.name}'
        assert scene['source_map_hash']==digest(source_text),f'Stale provenance: {path.name}'
        assert bpy.data.texts['WF_SOURCE_SNAPSHOT'].as_string()==spec_text
        assert bpy.data.texts['WF_PROVENANCE_SNAPSHOT'].as_string()==source_text
        objects=[o for o in bpy.data.objects if o.library is None and o.get('wf_owner')=='wayfarer.p0']
        identifiers=[o['component_id'] for o in objects]
        assert len(identifiers)==len(set(identifiers)),f'Duplicate IDs in {path}'
        links=[]
        for lib in bpy.data.libraries:
            assert lib.filepath.startswith('//'),f'Non-relative link {lib.filepath}'
            resolved=Path(bpy.path.abspath(lib.filepath)).resolve()
            assert resolved.is_file(),f'Missing library {resolved}'
            assert resolved.is_relative_to(root.resolve()),f'Link escapes project {resolved}'
            if lib.parent is None:links.append(str(resolved.relative_to(assets)))
        graph[str(path.relative_to(assets))]=links
        summaries[str(path.relative_to(assets))]={'generated_objects':len(objects),'ids':sorted(identifiers),'direct_links':sorted(links)}
        interfaces[path.name]={o.name:o.matrix_world.translation.copy() for o in objects if o.name.startswith('IF_')}
        detail_report[path.name]=detail_checks(s,root,path,objects,detail_assets)
        for o in objects:
            if o.name.startswith(('IF_ROTOR_TRANSFER_','IF_HULL_OPENING_','IF_HULL_ROTOR_BAY_','IF_AIRLOCK_','IF_DOCK_','IF_CREW_REFUGE','IF_SECTOR_OVERHEAD_HATCH','IF_CONVERGENCE_THROAT','IF_OPTICAL_','IF_LASER_','IF_CRYO_FEED_','IF_NOZZLE_YOKE_','IF_SPINE_','IF_H2_')):
                assert str(o.get('engineering_status','')).startswith('OPEN'),f'{o.name} must be flagged OPEN'
            if o.name.startswith(('IF_RIDE_THROUGH_','IF_MAIN_BATTERY_BUS_TIE','IF_PULSE_BANK_')) or o.name.endswith('_ISOLATOR'):
                assert str(o.get('engineering_status','')).startswith('OPEN'),f'{o.name} must be flagged OPEN'
            if o.name.startswith(('IF_HUB','IF_RING_STOP_LOCK_','IF_CREW_','IF_VESTIBULE_')):
                assert str(o.get('engineering_status','')).startswith('OPEN'),f'{o.name} must be flagged OPEN'
            if o.name.startswith('IF_RAD_') and o.name.endswith('_COOLANT_JOINT'):
                assert str(o.get('engineering_status','')).startswith('OPEN'),f'{o.name} must be flagged OPEN'
        if path.name=='WF_RADIATOR.blend':
            cells=[o for o in objects if o.get('kind')=='radiator_cell']
            area=sum(poly.area for o in cells for poly in o.data.polygons)
            assert math.isclose(area,thermal_geometry.emitting_planform(s),rel_tol=1e-6),area     # AFT-009: the gross rectangle less the non-emitting joints
            # AFT-001 thermal compliance, in the blade-local frame of the library: isolatable cells, the root band, expansion joints and mounts.
            p=s['prototype'];blade=thermal_geometry.blade_of(s);band=thermal_geometry.root_band(s);joints=thermal_geometry.bay_joints(s,blade)
            ribbons=p['radiator_ribbon_count'];bays=s['radiators']['geometry']['major_bays']
            assert len(cells)==p['radiator_longitudinal_cells']*p['radiator_transverse_cells'],len(cells)
            assert len({o['thermal_cell_id'] for o in cells})==len(cells) and all(o['isolatable'] and o['isolation_group']==o['thermal_cell_id'] for o in cells),'Thermal cells must be unique and isolatable'
            zone=[o for o in cells if o['thermal_zone']=='ROOT_TRANSITION']
            assert {o['thermal_zone'] for o in cells}<={'ROOT_TRANSITION','HOT_FACE'} and len(zone)==band['cells_per_blade'],len(zone)
            assert all(max(v.co.y for v in o.data.vertices)<=band['width_m']+1e-6 for o in zone),'Root band cells leave the band'
            assert all(bool(o['variable_emissivity_permitted'])==(o['thermal_zone']=='ROOT_TRANSITION') for o in cells),'Variable emissivity only in the root transition'
            assert math.isclose(sum(o['planform_m2'] for o in zone),band['planform_m2'],rel_tol=1e-6),'Root band planform'
            seams=[o for o in objects if o.get('kind')=='expansion_joint']
            assert len(seams)==3*(bays-1)*ribbons and not any(o.get('kind')=='radiator_cell' for o in seams),len(seams)     # bead + feed and return bellows
            # AFT-009: no cell reaches into a joint's gap; two lugs carry the datum; two guided shoes cross every joint.
            half=thermal_geometry.seam_width(s)/2
            assert all(min(abs(v.co.x-jt['u']) for jt in joints)>=half-1e-5 for o in cells for v in o.data.vertices),'A cell enters a bay joint'
            assert len([o for o in objects if o.get('kind')=='datum_lug'])==len(thermal_geometry.datum_lugs(s,blade)),'Datum lugs'
            assert len([o for o in objects if o.get('kind')=='joint_shoe'])==len(thermal_geometry.joint_shoes(s,blade)),'Joint shoes'
            # M4 slice 2: saddles and slide stops as thermal_geometry.root_construction defines them, none on the sheet side of the root edge.
            want={q['name']:q for q in thermal_geometry.root_construction(s,blade) if q['kind']!='casing_boot'}
            got={o.name:o for o in objects if o.get('kind') in ('root_saddle','slide_stop')}
            assert set(got)==set(want),sorted(set(got)^set(want))
            for n,o in got.items():
                assert all(max(abs(a-b) for a,b in zip(v.co,w))<=1e-5 for v,w in zip(o.data.vertices,want[n]['vertices'])),n
            for o in seams:
                u=sum(pt.co.x for pt in o.data.splines[0].points)/len(o.data.splines[0].points)
                assert abs(u-joints[o['bay_boundary']-1]['u'])<=1e-4 and o['planform_m2']==0,o.name
            mounts=[o for o in objects if o.get('kind')=='thermal_mount' and not o.name.endswith('_Rail')]
            assert sum(o['mount_role']=='FIXED_DATUM' for o in mounts)==1 and sum(o['mount_role']=='AXIAL_SLIDE' for o in mounts)==1+len(p['radiator_stay_bays']),[o.name for o in mounts]
            assert all(str(o['travel_allowance']).startswith('OPEN') for o in mounts),'Mount travel is OPEN'
            for m in thermal_geometry.mounts(s,blade):
                o=bpy.data.objects[m['name']];assert abs(sum(v.co.x for v in o.data.vertices)/len(o.data.vertices)-m['u'])<=1e-4 and abs(o['lever_arm_m']-m['lever_arm_m'])<=1e-6,m['name']
            assert len([o for o in objects if o.name=='IF_BLADE_FIXED_DATUM'])==1,'One fixed datum per blade'
        if path.name=='WF_RING_SECTOR.blend':
            # FGR-003: the envelope is the sector solid of habitat_ring (its extent); HUM-001 zone 5 makes it a skin around the cavity, opened under
            # the crew tube: the mesh volume is the envelope less the cavity and the opening (the cutter's 64-gon across the skin, about its thickness).
            env=bpy.data.objects['Sector_Pressure_Envelope'];L=human_entry.landing(s);t_skin=s['habitat_ring']['sector_skin_m']
            lo,hi=habitat_ring.sector_frame_extent(s)
            assert all(math.isclose(a,h-l,abs_tol=1e-4) for a,l,h in zip(env.dimensions,lo,hi)),(list(env.dimensions),lo,hi)
            hole=32*L['clear_r']**2*math.sin(math.pi/32)*t_skin
            assert abs(mesh_volume(env.data)-(habitat_ring.polygon_volume(s)-habitat_ring.cavity_m3(s)-hole))<=.1*hole,mesh_volume(env.data)
            # Open along the hatch axis and up to the clear radius, closed just outside the frame.
            tree=BVHTree.FromPolygons([v.co for v in env.data.vertices],[tuple(q.vertices) for q in env.data.polygons]);up=Vector((0,-1,0))
            for dx,dz,closed in ((0,0,False),(.75,0,False),(0,.75,False),(-.75,0,False),(0,-.75,False),(0,L['frame_r']+.05,True)):
                hit=tree.ray_cast(Vector((L['x']+dx,L['seat']-.05,L['z']+dz)),up,.4)[0]
                assert (hit is not None)==closed,f'Sector skin opening at ({dx}, {dz}): {hit}'
            assert env['rule_ref']=='pressurized_ring_rule' and env['geometry_status']=='PROTOTYPE'
            assert {o.name for o in objects if o.get('kind')=='entry_fixture'}=={q['name'] for q in human_entry.landing_fixtures(s)},'Landing fixtures'
            r=s['habitat_ring']
            for name,at in [('IF_SECTOR_FLOOR',(0,0,0)),('IF_SECTOR_OVERHEAD',(0,r['sector_inner_radius_m']-habitat_ring.floor(s),0))]:
                assert (bpy.data.objects[name].matrix_world.translation-Vector(at)).length<1e-6,name
            assert bpy.data.objects['IF_SECTOR_AFT_BULKHEAD'].matrix_world.translation.x==-r['sector_axial_m']/2
        if path.name in interior_files:
            # P1-004: every block where habitat_interior puts it, in the sector frame.
            function=interior_files[path.name];blocks=habitat_interior.plates(s)+habitat_interior.zones(s,function)
            # IND-001 3.1, 3.2: besides the blocks, only the sector's fit-out (route_fitout: the identity placard, the sector elements and Seraph's
            # space, with their texts), which keeps out of the aisle, the well and the strips.
            fit=route_fitout.sector_sign(s,function)
            if function in s['sector_whitebox']['functions']:
                fit+=route_fitout.sector_elements(s,function)+route_fitout.seraph_elements(s,function)[0]
                assert not route_fitout.sector_check(s,function),route_fitout.sector_check(s,function)
            assert {o.name for o in objects if o.type=='MESH' and o.get('kind') not in ('route_fitout','production_detail')}=={b['name'] for b in blocks},path.name
            # M7: the shared interior components carry no production layer (it is placed per selected sector in WF_HABITAT).
            assert not any(o.get('kind')=='production_detail' for o in objects),path.name
            assert {o.name for o in objects if o.get('kind')=='route_fitout'}=={n for q in fit for n in (q['name'],)+((q['name']+'_Text',) if q.get('text') else ())},path.name
            recess=route_fitout.service_recess(s,function) if function in s['sector_whitebox']['functions'] else None
            for b in blocks:
                o=bpy.data.objects[b['name']];vs=[o.matrix_world@v.co for v in o.data.vertices];want=[list(b['min']),list(b['max'])]
                if recess and b['name']==recess[0]:want[int(recess[3])][recess[1]]=recess[2]   # 3.2: the open face recessed
                assert all(abs(min(v[k] for v in vs)-want[0][k])<1e-5 and abs(max(v[k] for v in vs)-want[1][k])<1e-5 for k in range(3)),b['name']
                assert o['function']==function,b['name']
            assert (bpy.data.objects['IF_SECTOR_OVERHEAD_HATCH'].matrix_world.translation-Vector(habitat_interior.hatch(s))).length<1e-6
            # HUM-001 zone 5: the overhead panel is open around the hatch frame (the cutter is a 64-gon).
            x,z,r=habitat_interior.hatch_opening(s);ov=bpy.data.objects['Interior_Overhead']
            assert not any(math.hypot(v.co.x-x,v.co.z-z)<r*math.cos(math.pi/64)-1e-4 for v in ov.data.vertices),'Overhead panel not opened'
            assert not BVHTree.FromPolygons([v.co for v in ov.data.vertices],[tuple(q.vertices) for q in ov.data.polygons]).ray_cast(Vector((x,0,z)),Vector((0,-1,0)),5)[0],'Overhead panel not opened'
            assert 'IF_SECTOR_END_HATCH' not in bpy.data.objects,'No room turns: no end hatch'
            interior_report[path.name]={'function':function,'blocks':len(blocks)}
        ring_files={f'WF_{n}.blend':j for j,n in enumerate(RING_FAMILY,1)}
        if path.name in ring_files:
            # One engineering asset per ring (docs/MODULES.md): ring j's rotor, control, sectors and nothing of the other ring; the
            # whole-habitat actions live in the assembly.
            j=ring_files[path.name]
            assert {o.name for o in objects if o.get('kind')=='rotor'}=={f'Rotor_{j}'},path.name
            assert {o.name for o in objects if o.get('kind')=='state_control'}=={rotor_interface.control(j)},path.name
            assert {o.name for o in objects if o.get('kind')=='ring_sector'}=={q['name'] for q in habitat_ring.sectors(s) if q['ring']==j},path.name
            assert not [a for a in bpy.data.actions if a.library is None and a.get('wf_owner')=='wayfarer.p0'],f'{path.name}: rotor actions belong to WF_HABITAT'
        if path.name=='WF_HABITAT.blend':
            # The habitat assembly: both ring assets linked once, unparented at the ship origin, and no geometry of its own. The ring checks
            # below then run on the linked rings exactly as on the one file they replaced.
            rings=[o for o in objects if o.get('kind')=='ring_assembly']
            assert sorted((o['ring'],o.instance_collection.name) for o in rings)==sorted((j,n[:-len('.blend')]) for n,j in ring_files.items()),'Habitat rings'
            assert len(rings)==len(objects) and all(o.parent is None and o.matrix_world==Matrix.Identity(4) for o in rings),'Habitat assembly'
            objects=objects+[o for o in bpy.data.objects if o.library and Path(o.library.filepath).name in ring_files and o.get('wf_owner')=='wayfarer.p0']
            assert len([o for o in objects if o.get('kind')=='rotor'])==habitat_ring.ring_count(s)
            sector_objs=[o for o in objects if o.get('kind')=='ring_sector']
            assert len(sector_objs)==habitat_ring.ring_count(s)*s['habitat_ring']['sectors_per_ring']==len(habitat_ring.sectors(s))
            # Each sector carries exactly the interior of its function, in the sector frame.
            for sec_obj in sector_objs:
                rooms=[o for o in sec_obj.children if o.get('kind')=='sector_interior']
                assert len(rooms)==1 and rooms[0].instance_collection.name=='WF_'+s['interior']['components'][sec_obj['function']],sec_obj.name
                assert all(abs(a-b)<1e-6 for ra,rb in zip(rooms[0].matrix_world,sec_obj.matrix_world) for a,b in zip(ra,rb)),sec_obj.name
            # Sector floor (local +Y): always radially outward of the overhead; no room turns (fixed interior orientation).
            r=s['habitat_ring']
            for sec_obj in sector_objs:
                floor=sec_obj.matrix_world@Vector((0,0,0));overhead=sec_obj.matrix_world@Vector((0,r['sector_inner_radius_m']-habitat_ring.floor(s),0))
                assert sec_obj['floor_direction']=='RADIAL_OUTWARD',sec_obj.name
                assert math.hypot(floor.y,floor.z)>math.hypot(overhead.y,overhead.z)+habitat_ring.floor(s)-r['sector_inner_radius_m']-1e-4,(sec_obj.name,floor)
            # Ring frame, fills and spoke rails exactly where habitat_ring puts them, in the rotor frame.
            parts={q['name']:q for q in habitat_ring.frame_parts(s)}
            frame_objs=[o for o in objects if o.get('kind') in ('ring_frame','ring_fill')]
            assert {o.name for o in frame_objs}==set(parts),'Ring frame parts'
            for o in frame_objs:
                vs,_=habitat_ring.frame_solid(s,parts[o.name]);q=parts[o.name]
                assert o.get('kind')==q['kind'] and o.parent is bpy.data.objects[f"Rotor_{q['ring']}"] and o.matrix_basis==Matrix.Identity(4),o.name
                if o.get('crew_openings'):
                    # HUM-001 zone 5: an inner hoop opened for the crew tubes keeps the frame solid's extent and lies inside its band (the openings
                    # themselves are checked with the crew parts).
                    rho=lambda v:math.hypot(v.y,v.z);n=s['habitat_ring']['display']['hoop_facets']
                    assert all(q['u0']-1e-5<=v.co.x<=q['u1']+1e-5 and q['r0']*math.cos(math.pi/n)-1e-4<=rho(v.co)<=q['r1']+1e-4 for v in o.data.vertices),o.name
                    assert all(abs(min(v.co[i] for v in o.data.vertices)-min(c[i] for c in vs))<1e-4 and abs(max(v.co[i] for v in o.data.vertices)-max(c[i] for c in vs))<1e-4 for i in range(3)),o.name
                    assert o['crew_openings']==len(crew_transfer.hoop_cuts(s,q['ring'])),o.name
                    continue
                vs,_,cls=habitat_ring.frame_mesh(s,q)      # M4 slice 1: the part's construction, inside its band
                assert len(o.data.vertices)==len(vs) and all((v.co-Vector(c)).length<1e-5 for v,c in zip(o.data.vertices,vs)),o.name
                assert len(o.data.polygons)==len(cls) and len({p.material_index for p in o.data.polygons})==len(set(cls)),o.name
            rails={q['name']:q for q in habitat_ring.spokes(s)}
            rail_objs=[o for o in objects if o.get('kind')=='ring_spoke']
            assert {o.name for o in rail_objs}==set(rails) and len(rail_objs)==2*s['habitat_ring']['spokes_per_ring']*habitat_ring.ring_count(s),'Ring spoke rails'
            for o in rail_objs:
                q=rails[o.name];pts=curve_points(o)
                assert o.parent is bpy.data.objects[f"Rotor_{q['ring']}"] and (Vector(pts[0])-Vector((q['u'],q['r0']*math.cos(q['angle']),q['r0']*math.sin(q['angle'])))).length<1e-5 and (Vector(pts[-1])-Vector((q['u'],q['r1']*math.cos(q['angle']),q['r1']*math.sin(q['angle'])))).length<1e-5,o.name
                assert bool(o['crew_spoke'])==q['crew'],o.name
            assert len([o for o in rail_objs if o['crew_spoke']])==2*len(habitat_ring.sector_angles(s))*habitat_ring.ring_count(s)
            assert not [o for o in objects if o.get('kind') in ('habitat_pod','rotor_arm')],'Pods and arms are retired'
        if path.name in ('WF_NOZZLE.blend','WF_STRUCTURE.blend','WF_STORAGE.blend'):
            hot_report[path.name]=hot_section_checks(s,objects,path.name)
        if path.name=='WF_STRUCTURE.blend':
            assert len([o for o in objects if o.get('kind')=='thrust_node'])==12
            assert len([o for o in objects if o.get('kind')=='generator_proxy'])==2
        if path.name=='WF_EYE.blend':
            assert len([o for o in objects if o.get('kind')=='eye_facet'])==4
            # Owner facet map (14_HULL_SERVICE!A11): EYE_Facet_0j sits in quadrant Fj, +Y left looking forward.
            for j,(yy,zz) in enumerate(s['eye']['facet_map']['quadrants'],1):
                obj=bpy.data.objects[f'EYE_Facet_{j:02}'];facet=sum((obj.matrix_world@Vector(b) for b in obj.bound_box),Vector())/8
                assert (math.copysign(1,facet.y),math.copysign(1,facet.z))==(yy,zz),(j,facet)
            for j in range(1,5):
                aperture=bpy.data.objects[f'EYE_Aperture_{j:02}']
                assert math.isclose(aperture.dimensions.y,s['eye']['aperture']['value'],abs_tol=1e-5)
                assert math.isclose(aperture.dimensions.z,s['eye']['aperture']['value'],abs_tol=1e-5)
        if path.name=='WF_PROPULSION.blend':
            assert len([o for o in objects if o.get('component_id','').startswith('WF.NOZZLE.')])==4
            assert len([o for o in objects if o.get('component_id','').startswith('WF.FLUX.')])==4
            drive_report=propulsion_checks(s,objects)
            hot_report[path.name]=hot_section_checks(s,objects,path.name)
        if path.name=='WF_POWER_STORAGE.blend':
            power_report=power_storage_checks(s,objects)
        if path.name in (rotor_interface.SUBSYSTEM,'WF_HABITAT.blend'):
            rotor_report[path.name]=rotor_interface_checks(s,objects,path.name)
        if path.name in (crew_transfer.SUBSYSTEM,'WF_HABITAT.blend'):
            crew_report[path.name]=crew_transfer_checks(s,objects,path.name)
        if path.name=='WF_DEBUG_SEPARATRICES.blend':
            assert sorted(o.name for o in objects)==sorted(sp['name'] for sp in drive_manifold.geometry(s)['separatrices']) and all(o.get('kind')=='debug_separatrix' for o in objects),'Separatrix layer'
        if path.name=='WF_DEBUG_MAGNETICS.blend':
            g=drive_manifold.geometry(s)
            assert not any(o.get('kind')=='debug_separatrix' for o in objects),'Separatrices live in WF_DEBUG_SEPARATRICES'
            assert sum(len(bpy.data.objects[f'DBG_MAG_FLUX_LINES_{j}'].data.splines) for j in range(1,5))==len(g['field_lines'])
            assert all(o.get('kind','').startswith('debug') for o in objects),'Debug layers hold debug geometry only'
        if path.name=='WF_DEBUG_OPTICS.blend':
            g=drive_manifold.geometry(s)
            for (k,j),b in g['gate_beams'].items():
                pts=[tuple(p.co[:3]) for p in bpy.data.objects[f'DBG_OPT_GATE_PATH_{k}_L{j}'].data.splines[0].points]
                assert len(pts)==len(b) and all((Vector(p)-Vector(q)).length<1e-5 for p,q in zip(pts,b)),(k,j)
            for k,r in g['routes'].items():
                pts=[tuple(p.co[:3]) for p in bpy.data.objects[f'DBG_OPT_BORE_{k}'].data.splines[0].points]
                assert len(pts)==len(r['bore']) and all((Vector(p)-Vector(q)).length<1e-5 for p,q in zip(pts,r['bore'])),k
            assert 'DBG_OPT_TUNNEL_SIGHT_CONE' not in bpy.data.objects and 'DBG_OPT_FOCUS' not in bpy.data.objects,'Retired optics debug objects'
            assert all(o.get('kind')=='debug_optics' for o in objects),'Debug layers hold debug geometry only'
        if path.name=='WF_THERMAL.blend':
            assert len([o for o in objects if o.get('component_id','').startswith('WF.RADIATOR.0')])==3
            # Radiators are fixed (R1/R8, MEC-012): no radiator state control, hinge or animation; blades are unparented. The only drivers are the
            # AFT-005 display drivers on the health overlays, and the only control is RADIATOR_HEALTH_CTRL (thermal state and cell display, never geometry).
            assert not any(o.animation_data and o.animation_data.action for o in bpy.data.objects if o.library is None),'THERMAL file must hold no actions'
            assert all(o.get('kind') in radiator_inspect.OVERLAY_KINDS for o in bpy.data.objects if o.library is None and o.animation_data and o.animation_data.drivers),'THERMAL drivers belong to the health overlays only'
            assert {o.name for o in bpy.data.objects if o.get('kind')=='state_control'}=={radiator_health.CONTROL},'THERMAL file holds only the radiator health control'
            assert not any(o.get('kind')=='radiator_hinge' or o.name.startswith(('Radiator_State_Control','Radiator_Hinge_')) for o in bpy.data.objects),'THERMAL file must hold no radiator hinge'
            assert not any(o.name.endswith('_HINGE') for o in bpy.data.objects),'No hinge interfaces'
            d=derived(s)
            # AFT-001: root booms are booms (no deployment), exactly one fixed datum per sector, every feed has an expansion loop ending at the OPEN joint.
            booms=[o for o in objects if o.name.startswith('Radiator_Root_')]
            assert len(booms)==2*s['radiators']['count'] and all(o['kind']=='root_boom' for o in booms),'Root booms'
            assert not any(o.get('kind')=='deployed_lock' for o in objects),'No deployed locks in the thermal file'
            boots=[o for o in objects if o.get('kind')=='casing_boot']
            assert len(boots)==s['radiators']['count']*len([q for q in thermal_geometry.root_construction(s,thermal_geometry.blade_of(s)) if q['kind']=='casing_boot']),len(boots)
            for j in range(s['radiators']['count']):
                assert sum(bpy.data.objects[f'Radiator_Root_{j}_{sign}']['mount_role']=='FIXED_DATUM' for sign in (-1,1))==1,f'sector {j} datum'
                for feed_name,joint_name in (('Coolant_Feed','COOLANT_JOINT'),('Coolant_Return','RETURN_JOINT')):     # AFT-009: feed A and return B
                    feed=bpy.data.objects[f'{feed_name}_{j}'];pts=feed.data.splines[0].points
                    assert len(pts)>=6,len(pts)
                    assert bpy.data.objects[f"{feed_name.replace('Coolant_','Coolant_Chase_')}_{j}"].get('kind')=='coolant_chase',feed_name
                    # Every leg of the saved feed (not only the loop) clears the fixed-datum block by the mechanical clearance.
                    lo,hi=thermal_geometry.mount_block_box(next(m for m in thermal_geometry.mounts(s,thermal_geometry.blade_of(s)) if m['role']=='FIXED_DATUM')['u'],s['prototype']['radiator_mount_block_m'])
                    a_j=math.radians(s['prototype']['radiator_phase_deg']+j*120);bl=thermal_geometry.blade_of(s)
                    lp=[thermal_geometry.ship_to_local(bl,a_j,tuple(feed.matrix_world@Vector(pt.co[:3]))) for pt in pts]
                    gap=min(thermal_geometry.segment_box_distance(a,b,lo,hi) for a,b in zip(lp,lp[1:]))-s['prototype']['coolant_feed_radius_m']
                    assert gap>=s['prototype']['mechanical_clearance_m']-1e-6,('Feed legs vs fixed-datum block',j,gap)
                    joint=bpy.data.objects[f'IF_RAD_{j+1}_{joint_name}']
                    assert (feed.matrix_world@Vector(pts[-1].co[:3])-joint.matrix_world.translation).length<1e-5 and str(joint['engineering_status']).startswith('OPEN'),'Feed end / coolant joint'
                inst=bpy.data.objects[f'Radiator_{j+1:02}']
                assert len(inst['nano_stack'])==len(s['radiators']['nano_stack']['layers']) and str(inst['expansion_allowance']).startswith('OPEN') and inst['emissivity_root_baseline']==s['radiators']['emissivity']['value'],inst.name
            for j in range(s['radiators']['count']):
                blade=bpy.data.objects[f'Radiator_{j+1:02}'];a=math.radians(s['prototype']['radiator_phase_deg']+j*120)
                assert blade.parent is None,'Radiator blade must be unparented and static'
                assert blade['operating_state']=='FIXED' and {blade['operating_state']}==spec_module.RADIATOR_STATES,'Blade operating_state must come from RADIATOR_STATES'
                assert (blade.matrix_world.translation-Vector((d['center_x_m'],d['center_radius_m']*math.cos(a),d['center_radius_m']*math.sin(a)))).length<1e-6,blade.name
        if path.name=='WF_HULL.blend':
            shells=[o for o in objects if o.get('kind')=='hull_shell']
            assert len(shells)==len(hull_geometry.intervals(s)),'Hull span count'
            deps=bpy.context.evaluated_depsgraph_get()
            for o in shells:
                data=o.evaluated_get(deps).to_mesh()
                assert all(math.hypot(v.co.y,v.co.z)<=s['ship']['body_diameter']['value']/2+1e-6 and abs(v.co.x)<=s['ship']['length']['value']/2 for v in data.vertices),f'{o.name} leaves body envelope'
                # FGR-005 casing: under the blade span the shell is exactly the casing radius (root radius less the member clearance).
                span=layout.origins(s);cas=hull_geometry.casing_radius(s)
                under=[v.co for v in data.vertices if span['RADIATOR_AFT']<=v.co.x<=span['RADIATOR_FRONT']]
                assert all(math.hypot(v.y,v.z)<=cas+1e-5 for v in under),f'{o.name} exceeds the {cas} m casing under the blade span'
                if o.name.startswith('Hull_Aft'):assert under,'Aft body has no vertices under the blade span'
                o.evaluated_get(deps).to_mesh_clear()
            assert len([o for o in objects if o.name.startswith('IF_HULL_OPENING_')])==len(hull_geometry.openings(s,derived(s))),'Hull openings'
    stage(f'file:{prev}')
    # Subsystem-to-subsystem interface pairing: thermal members land on structure sector frames.
    sectors=[v for k,v in interfaces['WF_STRUCTURE.blend'].items() if k.startswith('IF_SECTOR_')]
    paired=[k for k in interfaces['WF_THERMAL.blend'] if '_HULL' in k]
    assert len(paired)==(2+len(s['prototype']['radiator_stay_bays']))*s['radiators']['count'],paired     # two root booms and the bay stays per sector
    for k in paired:
        assert min((interfaces['WF_THERMAL.blend'][k]-v).length for v in sectors)<1e-5,f'{k} does not meet a structure sector frame'
    # P1-007 ride-through markers coincide with the load interfaces they bridge (other subsystems).
    for r in power_storage.ride_through_points(s):
        asset,name=r['pairs_with']
        assert (interfaces['WF_POWER_STORAGE.blend'][r['name']]-interfaces[asset][name]).length<1e-5,f"{r['name']} does not meet {asset}:{name}"
    # P1-008 hub power feed meets the ride-through marker and the rotor-transfer interface it bridges.
    for f in (f for f in rotor_interface.interfaces(s) if 'pairs_with' in f):
        for asset,name in f['pairs_with']:
            assert (interfaces[rotor_interface.SUBSYSTEM][f['name']]-interfaces[asset][name]).length<1e-5,f"{f['name']} does not meet {asset}:{name}"
    # P1-001 crew interfaces pair by name with the fitting, refuge and vestibule interfaces they open into.
    for f in crew_transfer.interfaces(s):
        if f['side']=='STATIONARY' and f.get('pairs_with'):
            assert any(f['pairs_with'] in names for names in interfaces.values()),f"{f['name']}: no {f['pairs_with']}"
    stage('interface_pairing')
    def visit(node,stack):
        assert node not in stack,f'Circular dependency: {stack+[node]}'
        for dependency in graph[node]:visit(dependency,stack+[node])
    for node in graph:visit(node,[])
    contract_path=root/sim_rig.OUTPUT
    assert contract_path.exists() and json.loads(contract_path.read_text())==sim_rig.contract(s,spec_text,source_text),'Stale simulation rig contract'
    rig_anchors=sim_rig.anchors(s)
    configurations={}
    # One vehicle file. Preset-independent checks run once at the saved pose (frame 1); every buildable preset is then posed in memory
    # through the linked rotor and drive controls and checked for what a preset changes (rotation, drive state, hull contacts, sweeps).
    vehicle=s['vehicle'];saved=vehicle['saved_preset'];presets=buildable_configurations(s)
    bpy.ops.wm.open_mainfile(filepath=str(assets/(vehicle['asset']+'.blend')))
    root_obj=bpy.data.objects['WF_ROOT']
    assert list(root_obj['configurations'])==presets and root_obj['saved_preset']==saved and bpy.context.scene['configuration']==saved,'Stale configuration metadata'
    # Linked subsystems sit at the vehicle origin, so library-local interfaces are vehicle-frame positions.
    for obj in bpy.data.objects:
        if obj.library is None and obj.name.startswith('Assembly_'):
            assert all(math.isclose(a,b,abs_tol=1e-9) for r1,r2 in zip(obj.matrix_world,Matrix.Identity(4)) for a,b in zip(r1,r2)),obj.name
    assert not any(name.startswith(('Assembly_HABITAT_BURN','Assembly_ROTOR_BAY_DOORS')) for name in bpy.data.objects.keys()),'Retired subsystems must not be linked'
    assert 'WF_SIM_COM' not in bpy.data.objects,'COM is unknown and must not be placed'
    for item in rig_anchors:
        obj=bpy.data.objects[item['name']];at=obj.matrix_world.translation
        assert (at-Vector(item['position_m'])).length<1e-6,item['name']
        assert (obj.matrix_world.col[0].xyz-Vector(item['axis'])).length<1e-6 and (obj.matrix_world.col[2].xyz-Vector(item['up'])).length<1e-6,item['name']
        refs=[bpy.data.objects[r['object']].matrix_world.translation if r['asset']=='VEHICLE' else interfaces[r['asset']][r['object']] for r in item['interface_refs']]
        assert (at-sum(refs,Vector())/len(refs)).length<1e-5,f"{item['name']} does not match {item['relation']} of its interfaces"
    # P1-003 proxies: massless, hidden from evaluation and render, parented to their anchors and shaped as the contract says.
    proxy_items=sim_rig.proxies(s)
    assert {o.name for o in bpy.data.objects if o.library is None and o.get('kind')=='sim_proxy'}=={x['name'] for x in proxy_items},'Simulation proxies'
    for item in proxy_items:
        obj=bpy.data.objects[item['name']]
        assert obj.parent.name==item['anchor'] and obj.hide_viewport and obj.hide_render and not obj['mass_known'],item['name']
        vs=[v.co for v in obj.data.vertices];lo=[min(v[k] for v in vs) for k in range(3)];hi=[max(v[k] for v in vs) for k in range(3)]
        if item['shape']=='box':want=([c-z/2 for c,z in zip(item['center_m'],item['size_m'])],[c+z/2 for c,z in zip(item['center_m'],item['size_m'])])
        else:
            r=item.get('radius_m') or item.get('outer_radius_m') or max(item['radius0_m'],item['radius1_m'])
            want=([min(item['x0_m'],item['x1_m']),-r,-r],[max(item['x0_m'],item['x1_m']),r,r])
        assert all(abs(a-b)<1e-4 for a,b in zip(lo+hi,want[0]+want[1])),(item['name'],lo,hi,want)
    stage('vehicle_open_rig')
    rotor_libraries={'WF_HABITAT.blend',*(f'WF_{n}.blend' for n in RING_FAMILY),'WF_RING_SECTOR.blend',*interior_files}
    # A detail asset belongs to the asset it is linked into (its anchor's host): ring-sector detail spins with its ring, blade detail is thermal.
    host_of={f'{k}.blend':f'{v}.blend' for k,v in modules.detail_hosts(root,s['detail_packs']).items()}
    library_of=lambda lib:host_of.get(Path(bpy.path.abspath(lib.filepath)).name,Path(bpy.path.abspath(lib.filepath)).name) if lib else ''
    excluded={'WF_RADIATOR.blend','WF_THERMAL.blend',*rotor_libraries}
    def spinning_points():
        """Evaluated vertices of everything that rotates with the rings (hub rotating side, frame, spokes, crew parts, sectors, interiors)."""
        out=[]
        for instance in bpy.context.evaluated_depsgraph_get().object_instances:
            obj=instance.object
            if obj.type not in {'MESH','CURVE'} or obj.get('kind')=='scale_reference':continue
            if library_of(obj.original.library) not in rotor_libraries:continue
            data=obj.to_mesh();vs=[instance.matrix_world@v.co for v in data.vertices];faces=len(data.polygons);obj.to_mesh_clear()
            if faces:out.extend(vs)
        return out
    points=[];body=[];forward_points=[];fitting_points=[];appendage_points=[];thermal_points=[];blade_cells=[];stay_names=set();counts=collections.Counter();sector_centers=[];sector_volume=0.0;spinning=[];refuge_mesh=[];capture_centres={}
    for instance in bpy.context.evaluated_depsgraph_get().object_instances:
        obj=instance.object
        if obj.type not in {'MESH','CURVE'} or obj.get('kind')=='scale_reference':continue
        evaluated_mesh=obj.to_mesh()
        transformed=[instance.matrix_world@v.co for v in evaluated_mesh.vertices];faces=len(evaluated_mesh.polygons)
        volume=mesh_volume(evaluated_mesh) if obj.get('kind') in ('sector_pressure','crew_refuge') else 0.0
        obj.to_mesh_clear()
        # P1F: collapsed plasma and switched-off light evaluate without faces in the saved (drive-off) state.
        if not faces:continue
        points.extend(transformed);counts[obj.get('kind','untagged')]+=1
        if obj.get('kind')=='sector_pressure':sector_centers.append(sum(transformed,Vector())/len(transformed));sector_volume+=volume
        if obj.get('kind')=='crew_refuge':refuge_mesh.append((abs(volume),min(v.x for v in transformed),max(v.x for v in transformed)))
        if obj.get('kind')=='dock_capture_ring':capture_centres[obj.name]=list(transformed)
        library=library_of(obj.original.library)
        if library not in excluded:
            # Service fittings are radial tubes on the stationary structure (collar to r ~6.8 m); the body zone excludes them and they are
            # bounded separately by the 14 m BASELINE maximum body diameter.
            # SP-51/SP-53 and the A29 trackers stand on the casing like the fittings (survival_envelope; inside it they are fit-out).
            # M8.1: the exterior production layer on the shield (Brow aft face, Crown rim) is forward structure like its host.
            if obj.get('kind')=='production_detail' and library==forward_shield.SUBSYSTEM+'.blend':forward_points.extend(transformed)
            elif obj.get('kind') in ('service_fitting','dock_capture_ring','survival_envelope','exterior_hardware','casing_detail','production_detail'):fitting_points.extend(transformed)      # HAB-001: the capture rings are fittings on the same collar tips
            # FGR-006: the shield hub plate (r <= body radius) is body; the skin, rim, truss, wells, Lance, Crown and displays are forward structure
            # (they reach r 45 and 12 m ahead of the body) and are bounded by forward_inspect instead.
            elif library==forward_shield.SUBSYSTEM+'.blend' and obj.get('kind')!='shield_hub':forward_points.extend(transformed)
            # FWD-V2 outer Eye layout (forward_defense.eye_layout): the facets sit in cone wells on the shield, forward structure like the wells.
            elif library=='WF_EYE.blend' and forward_shield.eye_layout_active(s):forward_points.extend(transformed)
            # DRONE-001: the Brow docks, rails and arm base hang on the shield truss (forward structure); every other drone proxy stands on
            # or inside the body like the survival envelopes (bounded by the 14 m maximum).
            # S02 slice 2: the comms booms and dishes are deployed appendages like the blades, bounded by the shield shadow, not the body.
            elif obj.get('kind')=='comms_antenna':appendage_points.extend(transformed)
            elif obj.get('kind')=='drone_proxy':(forward_points if obj.get('station') in ('DS-10','DS-15') else fitting_points).extend(transformed)
            else:body.extend(transformed)
        elif library not in {'WF_RADIATOR.blend','WF_THERMAL.blend'}:spinning.extend(transformed)
        if library in {'WF_RADIATOR.blend','WF_THERMAL.blend'}:thermal_points.extend(transformed)
        if obj.get('kind')=='radiator_cell':blade_cells.extend(transformed)
        if obj.name.startswith('Blade_Stay_'):stay_names.add(obj.name)
    stage('instance_sweep')
    full=extent(points);body_bounds=extent(body)
    plume_margins={}
    for angle in [5,10,15,20]:
        # Aft of the exit plane: radial distance outside the cone; ahead of it no cone reaches the geometry, so the margin is the axial
        # distance from the exit plane (a lower bound). Thermal members and blades lie wholly ahead of the plane in this layout.
        exit_x=-s['ship']['length']['value']/2
        margins=[(v.x-exit_x) if v.x>=exit_x else math.hypot(v.y,v.z)-(math.sqrt(2)*s['prototype']['nozzle_offset_m']+s['prototype']['nozzle_exit_radius_m']+(exit_x-v.x)*math.tan(math.radians(angle))) for v in thermal_points]
        plume_margins[str(angle)]=min(margins)
    assert plume_margins['15']>s['prototype']['radiator_member_clearance_m'],plume_margins
    for v in thermal_points:
        if any(abs(v.x-x)<habitat_ring.sweep_half(s) for x in habitat_ring.centers(s)):
            assert math.hypot(v.y,v.z)>habitat_ring.outer(s)+s['prototype']['radiator_member_clearance_m'],'Thermal geometry intersects rotor swept envelope'
    assert math.isclose(body_bounds['size_m'][0],s['ship']['length']['value'],abs_tol=.002),body_bounds
    assert max(body_bounds['size_m'][1:]) <= s['ship']['body_diameter']['value']+.002,body_bounds
    assert fitting_points and max(math.hypot(v.y,v.z) for v in fitting_points)<=s['ship']['body_diameter']['max']/2+1e-6,'Service fittings exceed the 14 m BASELINE maximum body diameter'
    assert all(math.hypot(v.y,v.z)<=s['forward_shield']['diameter']['value']/2-s['forward_shield']['radiator_shadow_margin']['value']+1e-6 for v in appendage_points),'Comms appendages leave the shield shadow (radius less the radiator shadow margin)'
    # FGR-005 radiators: measured blade length, radial width, outer radius, member outer radius and total planform against the derived values.
    rd=derived(s);shield_r=rd['forward_shield_radius_m'];blade_angles=[math.radians(s['prototype']['radiator_phase_deg']+j*120) for j in range(s['radiators']['count'])]
    measured={}
    for j,a in enumerate(blade_angles):
        mine=[v for v in blade_cells if math.cos(math.atan2(v.z,v.y)-a)>.999]
        radial_u=[v.y*math.cos(a)+v.z*math.sin(a) for v in mine]
        measured[j]=(max(v.x for v in mine)-min(v.x for v in mine),max(radial_u)-min(radial_u),max(math.hypot(v.y,v.z) for v in mine))
    for j,(length_m,width_m,outer_m) in measured.items():
        assert abs(length_m-rd['blade_length_m'])<=1e-3 and abs(width_m-rd['net_width_m'])<=1e-3,(j,length_m,width_m)
        assert outer_m<=s['radiators']['outer_radius']['value']+1e-3,(j,outer_m)
    thermal_outer=max(math.hypot(v.y,v.z) for v in thermal_points)
    assert thermal_outer<=shield_r,'Radiator members leave the forward-shield silhouette'
    measured_total=sum(measured[j][0]*measured[j][1] for j in measured)
    assert math.isclose(measured_total,rd['total_planform_m2'],rel_tol=1e-6),measured_total
    assert len(stay_names)==len(s['prototype']['radiator_stay_bays'])*s['radiators']['count'],stay_names
    assert counts['radiator_cell']==3*s['prototype']['radiator_longitudinal_cells']*s['prototype']['radiator_transverse_cells']
    assert counts['eye_facet']==4 and counts['sector_pressure']==habitat_ring.ring_count(s)*s['habitat_ring']['sectors_per_ring']
    # Evaluated sector skins (HUM-001 zone 5): each the closed-form envelope less its cavity and the hatch opening; the envelopes (the gross volume,
    # molded to the skin's outer face) stay inside the BASELINE gross range.
    n_sec=len(habitat_ring.sectors(s));hole=32*human_entry.landing(s)['clear_r']**2*math.sin(math.pi/32)*s['habitat_ring']['sector_skin_m']
    assert abs(sector_volume-n_sec*(habitat_ring.polygon_volume(s)-habitat_ring.cavity_m3(s)-hole))<=n_sec*.1*hole,sector_volume
    assert s['habitat']['volume']['gross_min_m3']<=n_sec*habitat_ring.polygon_volume(s)<=s['habitat']['volume']['gross_max_m3'],n_sec*habitat_ring.polygon_volume(s)
    assert counts['sim_proxy']==0,'Simulation proxies must stay out of evaluated geometry'
    assert not counts['hull_door'],'No rotor-bay doors: the rings stay at full size'
    # Everything that spins sits inside the body proxy or a rotor sweep proxy (axisymmetric, so one frame covers the turn).
    cover={x['name']:x for x in proxy_items}
    # Vertices are stored as float32: the ring's outer hoop sits exactly on the 30 m sweep radius and rounds by ~2e-6 m there.
    f32=1e-5
    def covered(v):
        r=math.hypot(v.y,v.z);b=cover['WF_SIMPROXY_BODY']
        if b['x0_m']<=v.x<=b['x1_m'] and r<=b['radius_m']:return True
        return any(abs(v.x-a['position_m'][0])<=cover[n]['x1_m']+f32 and cover[n]['inner_radius_m']-f32<=r<=cover[n]['outer_radius_m']+f32
                   for n in cover if n.endswith('_SWEEP') for a in rig_anchors if a['name']==cover[n]['anchor'])
    assert spinning and all(covered(v) for v in spinning),'Rotating geometry escapes the body and sweep proxies'
    # P1B service fittings; fittings are bevelled curves, which evaluate as two instances each (like rotor arms).
    # HUM-001: a hollow entry port is four revolved meshes (one instance each) instead of a curve.
    hollow=len(human_entry.ports(s));assert counts['service_fitting']==2*(3-hollow)+4*hollow and counts['crew_refuge']==1,counts
    assert counts['power_storage']==len(power_storage.packs(s)),counts
    # HAB-001: the refuge mesh is the closed shell section revolved in 32 chords (volume = exact shell volume x n sin(2pi/n)/2pi) and spans its envelope;
    # one capture ring per dock, centred on the collar tip axis.
    rf=hull_geometry.refuge(s);facet=32*math.sin(2*math.pi/32)/(2*math.pi)
    assert len(refuge_mesh)==1 and abs(refuge_mesh[0][0]-rf['shield_volume_m3']*facet)<1e-3*rf['shield_volume_m3'] and abs(refuge_mesh[0][1]-rf['x0'])<1e-4 and abs(refuge_mesh[0][2]-rf['x1'])<1e-4,refuge_mesh
    rings=hull_geometry.capture_rings(s);assert counts['dock_capture_ring']==len(rings)==2 and set(capture_centres)=={q['name'] for q in rings},counts
    for q in rings:
        pts=capture_centres[q['name']];along=[v.y*math.cos(q['theta'])+v.z*math.sin(q['theta']) for v in pts]
        assert abs(min(along)-q['r0'])<1e-3 and abs(max(along)-q['r1'])<1e-3 and abs(min(v.x for v in pts)-(q['x']-q['radius']))<1e-3 and abs(max(v.x for v in pts)-(q['x']+q['radius']))<1e-3,q['name']
    stage('envelope_measures')
    r=s['eye']['aperture']['value']/2*.90
    clear=0;deps=bpy.context.evaluated_depsgraph_get()
    for w in forward_shield.wells(s):          # each facet face at its well bottom (r4 hub, or a cone well of the study layout)
        front=w['x0']
        for dy,dz in [(0,0),(r,0),(-r,0),(0,r),(0,-r)]:
            origin=Vector((front+.05,w['y']+dy,w['z']+dz))
            while True:   # the EYE window cartridge is optical, not an obstruction
                hit,loc,_,_,obj,_=bpy.context.scene.ray_cast(deps,origin,Vector((1,0,0)),distance=10-(origin.x-front))
                if not(hit and obj.get('kind')=='eye_window'):break
                origin=loc+Vector((1e-3,0,0))
            assert not hit,'Blocked EYE aperture sightline'
            clear+=1
    # FGR-006 forward structure at the saved pose: shield, wells, Lance, Crown, displays and the control, against forward_shield.py.
    assert forward_points,'Forward structure missing from the vehicle'
    stage('eye_rays')
    forward_report=forward_inspect.check_saved(s,dict(body_min_x=min(v.x for v in body),thermal=thermal_points,blade_cells=blade_cells,spinning=spinning,interfaces=interfaces))
    forward_states={}
    # AFT-005 radiator health display at the saved pose: overlays hidden, drivers exact, the control neutral; records the fixed-object snapshot.
    stage('forward_saved')
    radiator_report=radiator_inspect.check_saved(s)
    radiator_states={}
    sec=habitat_interior.section(s);d=derived(s)
    # Radiator blades and their proxies are fixed (R1/R8, MEC-012): checked at the saved pose and again for every preset below.
    blades=blade_matrices();assert len(blades)==s['radiators']['count'],'Radiator instances missing'
    plates=[bpy.data.objects[x['name']] for x in proxy_items if x['name'].startswith('WF_SIMPROXY_RADIATOR_')]
    assert len(plates)==s['radiators']['count'] and all(x['motion']['type']=='FIXED' for x in proxy_items),'Proxies must be fixed'
    half=s['prototype']['radiator_thickness_m']/2+1e-4
    def proxy_offset():
        for obj in plates:obj.hide_viewport=False
        deps=bpy.context.evaluated_depsgraph_get();pl=blade_plates(s,d)
        worst=max(min(plate_distance(tuple(o.evaluated_get(deps).matrix_world@Vector(c)),b) for b in pl) for o in plates for c in o.bound_box)
        for obj in plates:obj.hide_viewport=True
        return worst
    # P1F drive layers and actions are preset-independent: debug layers saved hidden; every action key posed in memory through the
    # linked control, evaluated drivers compared with drive_manifold.display(); one hull check at the widest pose.
    assert not any(name.startswith('Assembly_DEBUG') for name in bpy.data.objects.keys()),'Debug layers come through WF_PROPULSION only'
    assert not any(str(k).startswith('debug') for k in counts),'Debug geometry must stay out of evaluated geometry'
    deps=bpy.context.evaluated_depsgraph_get()
    assert not debug_layers_shown(deps),'Debug layers must be saved hidden'
    # Each toggle shows exactly its own layer through the linked drivers, and switching it off hides it again.
    toggles={};action_keys=0
    for layer,toggle in drive_manifold.DEBUG_LAYERS.items() if in_scope('drive') else ():
        pose_drive_state({toggle:1.0});shown=debug_layers_shown(bpy.context.evaluated_depsgraph_get())
        assert shown=={f'WF_{layer}'},f'{toggle} shows {shown}'
        pose_drive_state({toggle:0.0});toggles[toggle]=f'WF_{layer}'
    assert not debug_layers_shown(bpy.context.evaluated_depsgraph_get()),'Debug toggles must switch off again'
    for action,spec in drive_manifold.actions(s).items() if in_scope('drive') else ():
        for frame,_ in spec['keys']:
            worst=drive_mismatch(s,drive_manifold.action_state(s,action,frame))
            assert worst<1e-5,f'{action} frame {frame}: drive drivers off by {worst}'
            action_keys+=1
    widest={**drive_manifold.nominal(s),'flux_share_1':1.0,'flux_share_2':0.0,'flux_share_3':0.0,'flux_share_4':0.0}
    pose_drive_state(widest)
    if s['hull']['enabled'] and in_scope('drive'):
        _,contacts=hull_contacts(1)
        assert not contacts,f'Hull intersects the active drive: {contacts[:8]}'
    pose_drive_state({**drive_manifold.SAVED_SETTINGS,**drive_manifold.neutral(s)})
    assert all(v==0 for (n,p,i),v in drive_manifold.display(s,drive_manifold.neutral(s)).items() if not p.startswith('hide') and p!=drive_manifold.EXHAUST_END and (p!='color' or n.startswith('PLASMA'))),'Neutral drive must collapse'
    stage('drive_actions')
    for name in presets:
        cfg=s['configuration'][name];rotating=cfg['habitat']=='ROTATING'
        pose_configuration(s,name)
        # Rotation: every preset starts at the index angle (phase); rotating presets turn each ring a quarter period in 90 frames in
        # its own direction, stopped and locked presets do not move at all.
        rotations={};sample_count=0;interior_state=worst=offset=drive_state=hull_report=None
        for frame in [1,91] if in_scope('rotation') else ():
            bpy.context.scene.frame_set(frame)
            rotations[frame]=[bpy.data.objects[f'Rotor_{j}'].evaluated_get(bpy.context.evaluated_depsgraph_get()).rotation_euler.x for j in [1,2]]
        for j in range(2) if in_scope('rotation') else ():
            assert math.isclose(rotations[1][j],math.radians(s['prototype']['rotor_phase_deg'][j]),abs_tol=1e-5),(name,j,rotations[1][j])
            expected=(1 if j==0 else -1)*math.pi/2 if rotating else 0
            assert math.isclose(rotations[91][j]-rotations[1][j],expected,abs_tol=1e-5),(name,j,rotations[91][j]-rotations[1][j])
        bpy.context.scene.frame_set(1)
        # Full-revolution samples verify evaluated sector centres, interiors riding with their sectors and axial slab separation.
        sample_count=0;sector_count=len(habitat_ring.sectors(s));chord=2*s['habitat_ring']['sector_outer_radius_m']*math.sin(habitat_ring.sector_arc(s)/2)
        for frame in (range(1,362,15) if rotating else [1]) if in_scope('rotation') else ():
            bpy.context.scene.frame_set(frame)
            centers=[];sectors_=[];decks=[]
            for instance in bpy.context.evaluated_depsgraph_get().object_instances:
                if instance.object.get('kind')=='sector_pressure':
                    sectors_.append(instance.matrix_world.copy());centers.append(instance.matrix_world.translation.copy())
                elif instance.object.get('kind')=='sector_interior_deck':decks.append(instance.matrix_world.copy())
            assert len(centers)==sector_count and len(decks)==sector_count
            # Interiors ride in the sector frame: deck up (-Y) always points at the spin axis (no room turns).
            for m in decks:
                assert min(max(abs(a-b) for ra,rb in zip(m,pm) for a,b in zip(ra,rb)) for pm in sectors_)<1e-4,'Interior does not follow its sector'
                up=m.to_3x3()@Vector((0,-1,0));c=m.translation
                assert (up-(-Vector((0,c.y,c.z)).normalized())).length<1e-4,(name,frame,up)
            # Sector origins sit on the deck radius in their ring plane; sectors of one ring are separated by more than one sector chord.
            for center in centers:
                assert math.isclose(math.hypot(center.y,center.z),habitat_ring.floor(s),abs_tol=1e-4)
                assert min(abs(center.x-x) for x in habitat_ring.centers(s))<1e-4
            for i,c1 in enumerate(centers):
                for c2 in centers[i+1:]:
                    if abs(c1.x-c2.x)<.01:
                        assert (c1-c2).length > chord
            sample_count+=1
        bpy.context.scene.frame_set(1)
        if in_scope('rotation'):
          deck_points=[m@Vector((0,sec['deck_y_m'],0)) for m in decks]
          interior_state={'instances':len(decks),'deck_up':'toward the spin axis','deck_radius_m':[math.hypot(v.y,v.z) for v in deck_points]}
          assert all(math.isclose(r,habitat_ring.floor(s)+sec['deck_y_m'],abs_tol=1e-4) for r in interior_state['deck_radius_m'])
        # FGR-003 ring parts are PROTOTYPE geometry (BASELINE only covers the sourced ring rule on the sectors).
        assert all(o.get('geometry_status')=='PROTOTYPE' for o in bpy.data.objects if o.get('kind') in ('ring_sector','ring_frame','ring_fill','ring_spoke')),'Ring parts must carry geometry_status PROTOTYPE'
        # Sweep coverage: rotating presets keep every ring part inside the body or sweep proxies (stopped rings sit inside them too).
        assert not in_scope('rotation') or all(covered(v) for v in spinning_points()),f'{name}: rotating geometry escapes the body and sweep proxies'
        stage(f'{name}:rotation')
        # Radiators are fixed: every preset sees the same blade matrices and plates.
        if in_scope('thermal'):
            worst=radiator_pose(s,d)
            assert worst<=half,f'{name}: radiator cells off the fixed plates by {worst}'
            assert blade_matrices()==blades,f'{name}: radiator blade matrices differ between presets'
            offset=proxy_offset();assert offset<=half,f'{name}: radiator proxies off the fixed plates by {offset}'
            radiator_states[name]=radiator_inspect.check_state(s,name,radiator_health.configuration_state(s,name))
        stage(f'{name}:thermal')
        if in_scope('forward'):
            forward_state=forward_shield.configuration_state(s,name)
            forward_states[name]=forward_inspect.check_state(s,name,forward_state)
            eye_clear=forward_inspect.eye_rays(s,forward_state)
            assert eye_clear==clear,f'{name}: EYE sightlines with the field display off ({eye_clear} of {clear})'
        stage(f'{name}:forward')
        # P1F drive state of this preset: evaluated drivers against drive_manifold.display(); the exhaust run follows the throttle.
        if in_scope('drive'):
          state_values=drive_manifold.configuration_state(s,name)
          worst_drive=drive_mismatch(s,state_values);assert worst_drive<1e-5,f'{name}: drive drivers off by {worst_drive}'
          level=drive_manifold.thrust_level(s,name);end=bpy.data.objects['PLASMA_EXHAUST_1'].evaluated_get(bpy.context.evaluated_depsgraph_get()).data.splines[0].points[4].co[0]
          assert abs(end-drive_manifold.exhaust_end_x(s,level))<1e-5,f'{name}: exhaust run end {end}'
          drive_state={'state':'ACTIVE' if state_values['drive_active'] else 'OFF','thrust_level':round(level,6),'action_keys_checked':action_keys,'debug_toggles':toggles}
        stage(f'{name}:drive')
        if s['hull']['enabled'] and in_scope('hull'):
            frames=[1,91,181,271] if rotating else [1]
            checks=[hull_contacts(f) for f in frames]
            assert all(n==len(hull_geometry.intervals(s)) for n,_ in checks),'Hull not linked into vehicle'
            contacts=sorted({c for _,cs in checks for c in cs})
            assert not contacts,f'{name}: hull intersects geometry: {contacts[:8]}'
            hull_report={'frames_checked':frames,'bvh_contacts':0,'openings':len(hull_geometry.openings(s,derived(s))),**hull_geometry.summary(s)}
        stage(f'{name}:hull')
        configurations[name]={'realizes':[name],'habitat':cfg['habitat'],'controls':dict(cfg['controls']),'hull':hull_report,'body_bounds':body_bounds,'deployed_bounds':full,'clear_eye_rays':clear,
              'evaluated_geometry_counts':dict(counts),'sector_centers_frame_1':[list(v) for v in sector_centers],
              'rotor_sweep_samples':sample_count,'radiator_states':{name:{'max_cell_offset_m':worst}},'interiors':interior_state,
              'sim_proxies':{'names':[x['name'] for x in proxy_items],'radiator_proxy_max_offset_m':{name:offset}},'drive_states':drive_state,
              'rotation_quarter_period_verified':rotating,'rotation_locked_at_index_angle':not rotating,'hypothetical_plume_vertex_margins_m':plume_margins}
    # Display poses (previews only, never saved or configurations): drivers, only the N_crown nearest bays raised, emitter rays and envelope.
    stage('presets_done')
    forward_poses={name:forward_inspect.check_state(s,name,forward_shield.display_pose(s,name)) for name in (('DEFENSE_ENGAGED','SHIELD_DAMAGED','EYE_SHUTTERS_CLOSED','EYE_F1_JAMMED','CROWN_PREPARED','CROWN_ENGAGED','CROWN_RECOVERING','CROWN_DEGRADED') if in_scope('forward') else ())}
    stage('forward_poses')
    radiator_poses={name:radiator_inspect.check_state(s,name,radiator_health.display_pose(s,name)) for name in (radiator_health.pose_names(s) if in_scope('thermal') else ())}
    stage('radiator_poses')
    radiator_sweep=radiator_inspect.sweep(s) if in_scope('thermal') else None
    stage('radiator_sweep')
    timeline_report=timeline_checks(s,root,blades) if in_scope('timeline') else None
    stage('timeline')
    entry_route=route_sweep(s) if in_scope('route') else None
    # Leave the saved preset posed.
    stage('route_sweep')
    pose_configuration(s,saved)
    result={'result':'PASS','blender':bpy.app.version_string,'spec_hash':digest(spec_text),'source_map_hash':digest(source_text),
            'configurations':configurations,'radiators':{**derived(s),'measured_petal_planform_m2':area,'measured_blade_length_m':measured[0][0],'measured_blade_width_m':measured[0][1],
                                                               'measured_cell_outer_radius_m':max(m[2] for m in measured.values()),'measured_member_outer_radius_m':thermal_outer,
                                                               'measured_total_planform_m2':measured_total,'blade_stays':len(stay_names)},
            'clearance_scope':'Conservative thermal-envelope/rotor screening; sampled ring motion with the rings rotating and stopped; 15-degree hypothetical plume screen, not validated plume/field clearance or general collision certification.',
            'simulation_rig':{'contract':str(contract_path.relative_to(root)),'contract_version':sim_rig.CONTRACT_VERSION,'anchors':len(rig_anchors),'proxies':len(sim_rig.proxies(s)),'center_of_mass_placed':False},
            'detail':{k:v for k,v in detail_report.items() if v},
            'interiors':{'components':interior_report,**habitat_interior.check(s,derived(s))},
            'rotor_interface':{'assets':rotor_report,'check_pass':rotor_interface.check(s)['passed'],'report':'references/p1_rotor_interface.json'},
            'crew_transfer':{'assets':crew_report,'check_pass':crew_transfer.check(s)['passed'],'report':'references/p1_crew_transfer.json'},
            'human_entry':{'route_sweep':entry_route,'check_pass':human_entry.check(s)['passed'],'report':'references/p1_human_entry.json'},
            'power_storage':{**(power_report or {}),'check_pass':power_storage.check(s)['passed'],'report':'references/p1_power_storage.json'},
            'drive_manifold':{**(drive_report or {}),'hot_section':hot_report,'screen_pass':drive_manifold.check(s,derived(s))['passed'],'report':'references/p1_drive_manifold.json'},
            'forward_shield':{**forward_report,'preset_states':forward_states,'display_poses':forward_poses,'contract_section':'forward_defense'},
            'radiator_health':{**radiator_report,'preset_states':radiator_states,'display_poses':radiator_poses,'control_sweep':radiator_sweep,'contract_section':'radiator_health'},
            'flight_timeline':timeline_report,
            'assets':summaries,'studies':studies,
            'scope':{'mode':'full' if scope==set(GROUPS) else 'scoped','checked':['core',*sorted(scope)],'omitted':sorted(set(GROUPS)-scope)}}
    if output:
        output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(result,indent=2)+'\n')
    print('WF_INSPECT '+json.dumps({k:v for k,v in result.items() if k!='assets'}),flush=True)
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=ROOT);p.add_argument('--output',type=Path)
    p.add_argument('--scope',nargs='+',default=['all'],help=f"'all' (whole-ship) or groups: {' '.join(GROUPS)}")
    a=p.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    inspect(a.root.resolve(),a.output,None if a.scope==['all'] else [g for g in a.scope if g!='core'])
