"""WF_HULL recipe: station-lofted PROTOTYPE shell with derived openings. Geometry comes from hull_geometry."""
import math
from common import empty, material, mesh
from spec import derived
import hull_geometry as hg

OPEN_OPENING='OPEN: penetration seal, fairing and thermal isolation not designed'
OPEN_BAY='OPEN: ring-bay hub fairings/service panels (14!G5, H3) and bearing seals (OD-002/OD-013) not designed'


def hull(c,s):
    h=s['hull'];d=derived(s);skin=material('Hull',(.42,.46,.50))
    for part in hg.shell(s,d):
        obj=mesh(c,part['name'],part['vertices'],part['faces'],skin,kind='hull_shell')
        obj['rationale']=h['rationale'];obj['span_m']=[part['x0'],part['x1']];obj['omitted_quads']=part['omitted']
        # Thickness grows inward so the outer surface stays on the station radii; never applied.
        mod=obj.modifiers.new('Editable_Prototype_Thickness','SOLIDIFY');mod.thickness=h['shell_thickness_m'];mod.offset=-1
    for st in hg.stations(s):
        obj=empty(c,f"IF_HULL_STATION_{st['id'].rsplit('.',1)[1]}",(st['x'],0,0),kind='hull_station')
        obj['station_id']=st['id'];obj['role']=st['role'];obj['section']=st['section'];obj['radius_m']=st['r']
    spans=hg.intervals(s)
    for name,x in [('AFT',spans[0][2]),('FWD',spans[1][1])]:
        empty(c,f'IF_HULL_ROTOR_BAY_{name}',(x,0,0),kind='hull_opening')['engineering_status']=OPEN_BAY
    for w in hg.openings(s,d):
        obj=empty(c,f"IF_HULL_OPENING_{w['members'][0]}",w['at'],kind='hull_opening')
        obj.rotation_euler.x=math.atan2(w['at'][2],w['at'][1])
        obj['members']=', '.join(w['members']);obj['x_range_m']=[w['x0'],w['x1']];obj['engineering_status']=OPEN_OPENING


def bpy_object(name):
    import bpy
    return bpy.data.objects[name]


def revolved(c,name,f,prof,mat,kind,n=48):
    """Closed (a, rho) profile revolved about port f's outward radial axis (a = radius along it). The profile is turned clockwise in
    (a, rho) so v1 x v2 = u and the faces wind outward like loft()."""
    u=(math.cos(f['theta']),math.sin(f['theta']));w=(-math.sin(f['theta']),math.cos(f['theta']))
    area=sum(a0*r1-a1*r0 for (a0,r0),(a1,r1) in zip(prof,prof[1:]+prof[:1]))
    prof=(list(reversed(prof)) if area>0 else list(prof))+[prof[-1] if area>0 else prof[0]]
    vs=[(f['x']+rho*math.cos(2*math.pi*k/n),a*u[0]-rho*math.sin(2*math.pi*k/n)*w[0],a*u[1]-rho*math.sin(2*math.pi*k/n)*w[1]) for a,rho in prof for k in range(n)]
    fs=[(m*n+k,m*n+(k+1)%n,(m+1)*n+(k+1)%n,(m+1)*n+k) for m in range(len(prof)-1) for k in range(n)]
    return mesh(c,name,vs,fs,mat,kind=kind)


def entry(c,s,f,lock):
    """HUM-001 zones 1-2: the hollow entry route of a boarding port (human_entry): shells down to the trunk node and the inboard neck,
    hatches on hinges, handrails, lights, panels and valves. Both leaves swing on hinges driven by DOCK_ENTRY_CTRL (saved closed): the
    outer one into the entry chamber, the inner one inboard into the trunk node."""
    import bpy
    from mathutils import Matrix
    from common import line
    import human_entry as he
    fixture=material('EntryFixture',(.70,.72,.74));leaf_mat=material('EntryHatch',(.55,.60,.66));light=material('EntryLight',(1.0,.93,.80),12.0)
    panel=material('EntryPanel',(.10,.16,.20),.6);rail=material('EntryHandrail',(.92,.78,.22))
    st=he.stations(s,f);shell=material('EntryShell',(.62,.64,.66))   # IND-001 fit-out: the shell grey of the picked scheme (fitout.SHELL)
    for q in he.shells(s,f):
        obj=revolved(c,q['name'],f,q['profile'],shell,'service_fitting')
        obj['role']=q['role'];obj['source_ref']=f['source_ref'];obj['canon_status']='WORKING';obj['evidence_ref']='human_scale_entry_anchor'
        obj['geometry_basis']='PROTOTYPE route (HUM-001 zones 1-2); the 1.6 m clear passage is WORKING (Q33); location rule WORKING'
        obj['clear_radius_m']=st['chamber_r'] if q['name'].endswith(('Chamber','Node')) else st['clear']
    for q in he.fixtures(s,f):
        mat=light if q['role']=='light strip' else panel if q['shape']=='box' else rail if q['role'].startswith('handrail') else fixture
        if q['shape']=='ring':obj=revolved(c,q['name'],f,q['profile'],fixture,'entry_fixture')
        elif q['shape']=='rod':obj=line(c,q['name'],q['points'],q['radius'],mat,kind='entry_fixture')
        else:
            vs=he.box_corners(f,q)
            obj=mesh(c,q['name'],vs,[(0,1,3,2),(4,6,7,5),(0,4,5,1),(2,3,7,6),(0,2,6,4),(1,5,7,3)],mat,kind='entry_fixture')
        obj['role']=q['role'];obj['evidence_ref']='human_entry_workflow'
    ctrl=empty(c,'DOCK_ENTRY_CTRL',he.world(f,(st['a_in']+st['a_out'])/2),kind='entry_control')
    ctrl['role']='IMPLEMENTATION display control: outer and inner hatch opening, saved closed (0); previews pose them in memory'
    for which in ('outer','inner'):
        key=f"{f['name']}_{which}_open";ctrl[key]=0.0
        g=he.hinge(s,f,which);name=f"{f['name']}_{which.title()}_Hatch"
        mount=empty(c,f'{name}_Hinge_Mount',g['origin'],kind='hatch_hinge')
        mount.rotation_euler=Matrix((g['e1'],g['e2'],g['e3'])).transposed().to_euler()
        hinge=empty(c,f'{name}_Hinge',kind='hatch_hinge');hinge.parent=mount;hinge.empty_display_size=.3
        n=32;vs=he.leaf_local(s,f,which,n)
        fs=[(k,(k+1)%n,n+(k+1)%n,n+k) for k in range(n)]+[tuple(reversed(range(n))),tuple(n+k for k in range(n))]
        leaf=mesh(c,f'{name}_Leaf',vs,fs,leaf_mat,kind='entry_fixture');leaf.parent=hinge
        leaf['role']=f'{which} hatch leaf, seats from the ship side (pressure-assisted)';leaf['evidence_ref']='human_entry_workflow'
        hinge['opens']='into the entry chamber' if which=='outer' else 'inboard into the trunk node'
        fc=hinge.driver_add('rotation_euler',0);fc.driver.type='SCRIPTED';fc.driver.expression=f"o*{math.radians(g['open_deg'])!r}"
        v=fc.driver.variables.new();v.name='o';v.type='SINGLE_PROP';v.targets[0].id_type='OBJECT';v.targets[0].id=ctrl;v.targets[0].data_path=f'["{key}"]'
        if not fc.driver.is_simple_expression:raise ValueError(f'{hinge.name}: driver is not a simple expression')
    report=he.check(s)
    # A HUM-002 study workspace ([human_entry.study], never in the spec) moves ports the scale figures are posed against; it sweeps carriers, not figures.
    if not report['passed'] and not s['human_entry'].get('study'):raise ValueError(f'HUM-001 fit screen failed: {report["failures"]}')


def service(c,s):
    """SERVICE recipe: EVA airlock, two docking ports, the storm refuge and (HUM-002) the SP-45 storeroom on the stationary central structure."""
    from common import line, loft
    from fitout import fitout
    import human_entry as he
    lock=material('ServiceFitting',(.83,.66,.28));haven=material('RefugeShield',(.30,.52,.55))
    hollow={f['name'] for f in he.ports(s)}
    for f in hg.service_fittings(s):
        u=(math.cos(f['theta']),math.sin(f['theta']))
        if f['name'] in hollow:entry(c,s,f,lock);fitout(c,s,f);obj=bpy_object(f['name'])
        else:obj=line(c,f['name'],[(f['x'],f['r0']*u[0],f['r0']*u[1]),(f['x'],f['r1']*u[0],f['r1']*u[1])],f['radius'],lock,kind='service_fitting')
        obj['role']=f['role'];obj['source_ref']=f['source_ref'];obj['canon_status']='WORKING'
        if f['name'] not in hollow:obj['geometry_basis']='PROTOTYPE size/position; location rule is WORKING'
        iface=empty(c,f['interface'],(f['x'],f['r1']*u[0],f['r1']*u[1]))
        iface.rotation_euler.x=f['theta'];iface['engineering_status']='OPEN: lock/port mechanism, hatch size and docking standard not designed'
        iface['axis']='outward radial'
    cap=material('DockCaptureRing',(.62,.64,.68))
    for q in hg.capture_rings(s):
        u=(math.cos(q['theta']),math.sin(q['theta']))
        # Profile (radial position, radius about the port axis), revolved about the radial axis.
        obj=revolved(c,q['name'],q,[(q['r0'],q['radius']),(q['r1'],q['radius']),(q['r1'],q['inner']),(q['r0'],q['inner'])],cap,'dock_capture_ring')
        obj['role']='androgynous soft-capture ring';obj['source_ref']='docking_standard';obj['canon_status']='OPEN'
        obj['geometry_basis']='PROTOTYPE capture ring larger than the 1.6 m clear passage (HSFP class F for the size, L for the passage); mechanism and diameter OPEN (14!G30)'
        obj['radius_m']=q['radius'];obj['clear_radius_m']=s['prototype']['dock_clear_radius_m']
        iface=empty(c,q['interface'],(q['x'],q['r1']*u[0],q['r1']*u[1]));iface.rotation_euler.x=q['theta']
        iface['engineering_status']='OPEN 14!G30: capture-ring diameter, latches and soft-capture mechanism not designed';iface['axis']='outward radial'
    r=hg.refuge(s)
    obj=loft(c,'Refuge_Storm_Shelter',list(r['shell_profile'])+[r['shell_profile'][0]],haven,caps=False)
    obj['kind']='crew_refuge';obj['canon_status']='WORKING';obj['source_ref']='storm_refuge'
    obj['capacity_persons']=s['shielding']['refuge']['capacity_persons'];obj['pressure_radius_m']=r['pressure'];obj['shield_thickness_m']=r['shield_m'];obj['cavity_x_m']=[r['cavity_x0'],r['cavity_x1']]
    obj['rationale']=s['prototype']['refuge_rationale']
    empty(c,'IF_CREW_REFUGE',((r['x0']+r['x1'])/2,0,0))['engineering_status']='OPEN OD-011 geometry: material stack, access path and endurance not designed'
    # HUM-001 refuge leg: the pressure wall that closes the cavity's inner face, opened by the refuge port (human_entry.refuge_station).
    from common import cut, revolve_mesh
    import crew_transfer as ct
    rs=he.refuge_station(s);w0,w1=rs['wall'];L=rs['x1']-rs['x0']
    vs,fs=revolve_mesh((rs['x0'],0,0),(rs['x1'],0,0),[(0.0,w0),(L,w0),(L,w1),(0.0,w1)])
    obj=cut(mesh(c,'Refuge_Inner_Wall',vs,fs,material('RefugeLiner',(.78,.80,.80)),kind='refuge_wall'),[((rs['x'],0,0),ct.radial(rs['x'],w1+.1,rs['th']),rs['outer_r'])])
    obj['role']='refuge inner pressure wall';obj['canon_status']='OPEN';obj['source_ref']='storm_refuge';obj['evidence_ref']='human_entry_workflow'
    obj['geometry_basis']='PROTOTYPE HUM-001 refuge leg: closes the cavity inside the clearance to the spine, so the cavity keeps its volume; unshielded inner face (OD-011)'
    storeroom(c,s)
    import survival
    survival.hull(c,s)     # SP-49 placard, SP-53 / Eye A25-A26 terminals, A29 trackers, SP-51 crawler track (PROTOTYPE envelopes)
    import exterior
    exterior.service(c,s)  # S02 slice 1: docking guidance, airlock floods, aft beacons (PROTOTYPE)


def storeroom(c,s):
    """HUM-002 (SP-45): the walk-in storeroom (storeroom): the pressure shell as a closed wall solid opened by the trunk port's clear bore, the
    racks (uprights, shelves, retention nets), illustrative containers, floor tie-down rails, the ceiling light and the room panel; the sealed
    hatch, a round leaf on the room side hinged on an axis along X, driven by STOREROOM_CTRL['hatch_open'] (0 closed, saved; 1 folded flat
    against the inner wall beside the door)."""
    import bmesh
    from common import cut, line
    from crew import lines
    import storeroom as sr
    st=sr.station(s);p=sr.port(s);lf=sr.leaf(s);W=sr.world
    F=[(0,1,3,2),(4,6,7,5),(0,4,5,1),(2,3,7,6),(0,2,6,4),(1,5,7,3)]
    outer=[W(s,x,u,t) for x in (st['x0'],st['x1']) for u in (st['d'],st['uout']) for t in (-st['half_out'],st['half_out'])]
    inner=[W(s,x,u,t) for x in (st['xf'],st['xc']) for u in (st['ui'],st['uo']) for t in (-st['half'],st['half'])]
    shell=mesh(c,'Storeroom_Shell',outer+inner,F+[tuple(reversed([k+8 for k in f])) for f in F],material('StoreroomShell',(.62,.64,.66)),kind='storeroom_shell')
    shell=cut(shell,[(W(s,p['x'],st['d']-.1,0.0),W(s,p['x'],st['ui']+.1,0.0),p['clear'])])
    shell['role']='SP-45 walk-in general storeroom pressure shell';shell['canon_status']='WORKING';shell['source_ref']='general_storeroom'
    shell['evidence_ref']='general_storeroom';shell['geometry_basis']='PROTOTYPE HUM-002 placement and shell around the owner program (33!C85:C88, DIMENSIONS PROVISIONAL)'
    shell['engineering_status']='OPEN: shell structure, door seals, ventilation, fire detection/suppression, lighting power and mass (33!B90, B95)'
    shell['clear_m']=[st['L'],st['W'],st['H']];shell['clear_m3']=st['L']*st['W']*st['H'];shell['floor']='aft wall (thrust, aft down)'
    frame=material('StoreroomRack',(.48,.52,.55));shelf=material('StoreroomShelf',(.70,.72,.72));net=material('StoreroomNet',(.20,.42,.40),0,.35)
    box_mat=material('StoreroomContainer',(.55,.50,.38));rail=material('EntryHandrail',(.92,.78,.22));light=material('EntryLight',(1.0,.93,.80),12.0)
    panel=material('EntryPanel',(.10,.16,.20),.6)
    import human_entry as he
    for q in sr.fixtures(s):
        if q['shape']=='rod':obj=line(c,q['name'],q['points'],q['radius'],rail,kind='storeroom_fixture')
        elif q['shape']=='rods':obj=lines(c,q['name'],q['segments'],q['radius'],frame,'storeroom_fixture')
        else:
            role=q['role'];mat=net if 'net' in role else box_mat if 'container' in role else light if 'light' in role else panel if 'panel' in role else shelf
            obj=mesh(c,q['name'],he.box_corners(None,q),F,mat,kind='storeroom_stowage' if 'container' in role else 'storeroom_fixture')
        obj['role']=q['role'];obj['evidence_ref']='general_storeroom'
    ctrl=empty(c,'STOREROOM_CTRL',p['b'],kind='entry_control');ctrl['hatch_open']=0.0
    ctrl['role']='IMPLEMENTATION display control: SP-45 hatch opening, saved closed (0); previews pose it in memory'
    hinge=empty(c,'Storeroom_Hatch_Hinge',lf['hinge'],kind='hatch_hinge');hinge.empty_display_size=.3
    _,eu,et=sr.frame(s);n=32;h0=lf['hinge'];vs=[]
    for side in (-1,1):
        for k in range(n):
            a=math.tau*k/n;cx,cy,cz=lf['centre']
            v=(cx+lf['radius']*math.cos(a),cy+lf['radius']*math.sin(a)*et[1]+side*lf['thickness']/2*eu[1],cz+lf['radius']*math.sin(a)*et[2]+side*lf['thickness']/2*eu[2])
            vs.append(tuple(v[i]-h0[i] for i in range(3)))
    leaf=mesh(c,'Storeroom_Hatch_Leaf',vs,[(k,(k+1)%n,n+(k+1)%n,n+k) for k in range(n)]+[tuple(range(n)),tuple(n+k for k in range(n))],
              material('EntryHatch',(.55,.60,.66)),kind='entry_fixture')
    bm=bmesh.new();bm.from_mesh(leaf.data);bmesh.ops.recalc_face_normals(bm,faces=bm.faces);bm.to_mesh(leaf.data);bm.free()
    leaf.parent=hinge;leaf['role']='SP-45 sealed hatch leaf, room side (room pressure holds it shut if the trunk loses pressure)';leaf['evidence_ref']='general_storeroom'
    hinge['opens']=f"{lf['open_deg']:.0f} deg into the room, folding flat against the inner wall beside the door"
    fc=hinge.driver_add('rotation_euler',0);fc.driver.type='SCRIPTED';fc.driver.expression=f"o*{math.radians(lf['open_deg'])!r}"
    v=fc.driver.variables.new();v.name='o';v.type='SINGLE_PROP';v.targets[0].id_type='OBJECT';v.targets[0].id=ctrl;v.targets[0].data_path='["hatch_open"]'
    if not fc.driver.is_simple_expression:raise ValueError(f'{hinge.name}: driver is not a simple expression')
    empty(c,'IF_STOREROOM',p['b'])['engineering_status']='OPEN HUM-002: storeroom hatch seal and latch, ventilation and fire isolation not designed'
    rows,fails=sr.check(s)
    if fails and not s['human_entry'].get('study'):raise ValueError(f'HUM-002 storeroom fit screen failed: {fails}')
