"""READBACK-001: measure the saved vehicle for the owner (S&E 34!A94:A110, 31!A39/A53/A104, 33!A66:A68, 27!A12, 37!A56, 41!A83).

Measurements only: world bounds, closed-mesh solid volumes, envelopes of revolution for rotating parts, the stationary body's free
axial corridor, and pressurized volumes from the generator dimensions (pressure_volumes; the pressure meshes are wall shells). No mass,
power or heat is computed here: Sheets owns them, so dry_kg stays unknown. Nothing is written back into canon.
Writes readback.csv (34!A105 columns), station_map.csv and readback.json into --out-dir."""
from pathlib import Path
import argparse
import csv
import json
import math
import re
import sys
import bpy
ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT/'src/wayfarer')]
import importlib.util
import spec as spec_module
import hull_geometry
import habitat_ring
import pressure_volumes
_spec=importlib.util.spec_from_file_location('wf_inspect',Path(__file__).resolve().with_name('inspect.py'))
wf_inspect=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(wf_inspect)

ROTATING={'WF_HABITAT','WF_RING_SECTOR','WF_INTERIOR_HABITATION','WF_INTERIOR_WORK','WF_INTERIOR_GARDEN'}
# Display-only objects: fields, beams, plasma and envelopes show a state; they are not hardware and occupy no packing volume.
DISPLAY_KINDS={'plasma','optical_beam','magnetic_field','hull_envelope'}
DISPLAY_NAMES=('MagneticNozzle_FieldEnvelope','Body_Envelope_Reference')
# Long members that run through the whole stationary body; the free-corridor scan ignores them and reports them instead.
THROUGH=('Hull_Aft_Body','Hull_Forward_Collar','Body_Envelope_Reference','Structural_Spine','Primary_Frame','Primary_Rail','Primary_XBrace',
         'Hub_Web','CRYO_FEED_LINE')
STEM=re.compile(r'_(?:-?\d+|[A-Z]?\d+[a-z]?)(?:_|$)')
COLUMNS=['ID','subsystem','zone','category','count','x_min','x_max','y_min','y_max','z_min','z_max','r_min','r_max','solid_m3','swept_m3',
         'pressure_gross_m3','pressure_net_m3','dry_kg','unresolved']


def fmt(v):
    return f'{v:.3f}' if isinstance(v,float) else str(v)


def closed(data):
    """Every edge borders exactly two faces."""
    uses={}
    for poly in data.polygons:
        for key in poly.edge_keys:uses[key]=uses.get(key,0)+1
    return bool(uses) and all(n==2 for n in uses.values())


def measure():
    """One record per evaluated mesh instance at the saved pose."""
    records=[]
    for instance in bpy.context.evaluated_depsgraph_get().object_instances:
        obj=instance.object
        if obj.type not in {'MESH','CURVE'} or obj.get('kind')=='scale_reference':continue
        data=obj.to_mesh()
        if not data.polygons:obj.to_mesh_clear();continue
        m=instance.matrix_world;vs=[m@v.co for v in data.vertices]
        is_closed=closed(data);solid=wf_inspect.mesh_volume(data)*abs(m.to_3x3().determinant()) if is_closed else None
        obj.to_mesh_clear()
        lib=obj.original.library;sub=Path(lib.filepath).stem if lib else 'WF_WAYFARER_001'
        rs=[math.hypot(v.y,v.z) for v in vs]
        records.append(dict(name=obj.name,kind=obj.get('kind') or 'geometry',subsystem=sub,stem=STEM.split(obj.name)[0],
                            lo=[min(v[i] for v in vs) for i in range(3)],hi=[max(v[i] for v in vs) for i in range(3)],
                            r_min=min(rs),r_max=max(rs),solid=solid,closed=is_closed,
                            centroid=sum(vs,vs[0]*0)/len(vs)))
    return records


def display(r):
    return r['kind'] in DISPLAY_KINDS or r['name'].startswith(DISPLAY_NAMES)


def zone(sub):
    return 'ROTATING' if sub in ROTATING else 'STATIONARY'


def row(rid,sub,category,group,gross='',net='',notes=(),zone_name=None):
    lo=[min(r['lo'][i] for r in group) for i in range(3)];hi=[max(r['hi'][i] for r in group) for i in range(3)]
    r0=min(r['r_min'] for r in group);r1=max(r['r_max'] for r in group)
    open_meshes=sum(not r['closed'] for r in group);unresolved=list(notes)
    if open_meshes:unresolved.append(f'solid: {open_meshes} of {len(group)} meshes open')
    solid=sum(r['solid'] for r in group if r['closed']) if open_meshes<len(group) else 'unresolved'
    zone_name=zone_name or zone(sub);rotating=zone_name!='STATIONARY'
    # Rotating parts: the envelope of revolution about +X that they sweep (rings, spokes, tubes, sectors), not a dynamic sweep.
    swept=math.pi*(r1*r1-r0*r0)*(hi[0]-lo[0]) if rotating else 'static'
    if any(display(r) for r in group):unresolved.append('display only, not hardware')
    unresolved.append('mass owned by Sheets')
    return dict(zip(COLUMNS,[rid,sub,zone_name,category,len(group),*[x for pair in zip(lo,hi) for x in pair],r0,r1,solid,swept,gross,net,
                             'unknown','; '.join(unresolved)]))


def sector_names(s,records):
    """Pair each Sector_Pressure_Envelope instance with its habitat_ring sector: ring by axial order, index by angle at the saved pose."""
    found=[r for r in records if r['kind']=='sector_pressure'];wanted=habitat_ring.sectors(s);centres=habitat_ring.centers(s)
    pairs={}
    for r in found:
        c=r['centroid'];ring=min(range(len(centres)),key=lambda k:abs(centres[k]-c.x))+1;ang=math.atan2(c.z,c.y)
        best=min((q for q in wanted if q['ring']==ring),key=lambda q:abs(math.remainder(ang-q['angle'],2*math.pi)))
        pairs[id(r)]=best['name']
    assert len(set(pairs.values()))==len(found)==len(wanted),'Sector instances do not pair one to one with habitat_ring.sectors'
    return pairs


# Thin radiator mounting members cross the body at single stations; the "between equipment" view lists them instead of splitting on them.
CROSSING=('Blade_Stay','Radiator_Root','Coolant_Feed','Coolant_Return','Coolant_Chase','Blade_Root_Post','Blade_Mount','Blade_Datum_Lug')


def corridor(s,records,crossing=()):
    """Free x-intervals of the stationary body: no stationary non-display object other than the through members (and the given
    crossing members, which are listed per interval) reaches inside the hull's inner radius."""
    hull=[r for r in records if r['name'].startswith(('Hull_Aft_Body','Hull_Forward_Collar'))]
    x0=min(r['lo'][0] for r in hull);x1=max(r['hi'][0] for r in hull)
    spine=max((r['r_max'] for r in records if r['name'].startswith('Structural_Spine')),default=0.0)
    busy=[];crossers=[]
    for r in records:
        if zone(r['subsystem'])=='ROTATING' or display(r) or r['name'].startswith(THROUGH):continue
        if r['hi'][0]<x0 or r['lo'][0]>x1:continue
        mid=min(max((r['lo'][0]+r['hi'][0])/2,x0),x1)
        if r['r_min']<hull_geometry.inner_radius_at(s,mid)-0.05:
            (crossers if r['name'].startswith(crossing) else busy).append((r['lo'][0],r['hi'][0],r['name']))
    busy.sort();free=[];at=x0;last=None
    for a,b,name in busy:
        if a>at+1e-6:free.append((at,a,last,name))
        if b>at:at,last=b,name
    if x1>at+1e-6:free.append((at,x1,last,None))
    out=[]
    for a,b,aft,fwd in free:
        n=max(1,int((b-a)/0.05));dx=(b-a)/n
        annulus=sum(math.pi*(hull_geometry.inner_radius_at(s,a+(k+.5)*dx)**2-spine**2)*dx for k in range(n))
        cross=sorted({STEM.split(n)[0] for lo,hi,n in crossers if hi>a and lo<b})
        stations=sorted({round((lo+hi)/2,2) for lo,hi,n in crossers if hi>a and lo<b})
        out.append(dict(x_min=a,x_max=b,length_m=b-a,annulus_m3=annulus,aft_neighbour=aft,fwd_neighbour=fwd,
                        crossed_by=cross,crossing_stations_x=stations))
    return dict(hull_x=[x0,x1],spine_radius_m=spine,through_members=list(THROUGH),crossing_members=list(crossing),intervals=out)


def radiator_root(s,records):
    """Radial gap between the hot blades' inner edge and the stationary hull under them, and against nominal 12/13/14 m bodies (34!A88:A91)."""
    cells=[r for r in records if r['kind']=='radiator_cell'];hull=[r for r in records if r['name'].startswith('Hull_Aft_Body')]
    edge=min(r['r_min'] for r in cells);outer=max(r['r_max'] for r in hull)
    return dict(blade_inner_edge_r_m=edge,hull_outer_r_m=outer,gap_to_built_hull_m=edge-outer,
                gap_to_nominal_body_m={f'{d:g} m':edge-d/2 for d in (12.0,13.0,14.0)},
                note='radial clearance numbers only; root booms and stays bridge the gap by design')


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=ROOT);p.add_argument('--out-dir',type=Path,required=True)
    args=p.parse_args(sys.argv[sys.argv.index('--')+1:])
    s,_,spec_text,source_text=spec_module.load(args.root)
    vehicle=s['vehicle']
    bpy.ops.wm.open_mainfile(filepath=str(args.root/'assets/wayfarer'/(vehicle['asset']+'.blend')))
    bpy.context.scene.frame_set(1)
    records=measure();rooms=pressure_volumes.rooms(s);names=sector_names(s,records)
    for r in records:r['room']=names.get(id(r),r['name'])
    rows=[]
    groups={}
    for r in records:groups.setdefault((r['subsystem'],r['stem'],r['kind']),[]).append(r)
    for (sub,stem,kind),group in sorted(groups.items()):
        rows.append(row(f"{sub.removeprefix('WF_')}.{stem}" if kind=='geometry' else f"{sub.removeprefix('WF_')}.{stem}[{kind}]",sub,kind,group))
    for r in sorted((r for r in records if r['room'] in rooms),key=lambda r:r['room']):
        q=rooms[r['room']]
        rows.append(row(f"ROOM.{r['room']}",r['subsystem'],q['category'],[r],q['gross_m3'],'unresolved' if q['net_m3'] is None else q['net_m3'],
                        [f"pressure: {q['basis']}","solid = pressure wall"]+(['net: fit-out not modelled'] if q['net_m3'] is None else []),q['zone']))
    missing=sorted(set(rooms)-{r['room'] for r in records})
    free=corridor(s,records);coarse=corridor(s,records,CROSSING)
    stations=sorted(([x['ID'],x['zone'],x['x_min'],x['x_max'],x['r_min'],x['r_max']] for x in rows if not x['ID'].startswith('ROOM.')),key=lambda x:(x[2],x[0]))
    args.out_dir.mkdir(parents=True,exist_ok=True)
    with (args.out_dir/'readback.csv').open('w',newline='') as f:
        w=csv.writer(f,lineterminator='\n');w.writerow(COLUMNS);[w.writerow([fmt(x[c]) for c in COLUMNS]) for x in rows]
    with (args.out_dir/'station_map.csv').open('w',newline='') as f:
        w=csv.writer(f,lineterminator='\n');w.writerow(['ID','zone','x_min','x_max','r_min','r_max'])
        for x in stations:w.writerow([fmt(v) for v in x])
        for k,iv in enumerate(free['intervals'],1):
            w.writerow([f'FREE_CORRIDOR_{k}','STATIONARY',fmt(iv['x_min']),fmt(iv['x_max']),fmt(free['spine_radius_m']),'hull inner radius'])
    report=dict(spec_hash=spec_module.digest(spec_text),source_map_hash=spec_module.digest(source_text),pose=vehicle['saved_preset'],
                objects=len(records),groups=len(groups),rooms_measured=len(rooms)-len(missing),rooms_missing=missing,
                room_totals=pressure_volumes.totals(s),free_corridor=free,free_corridor_between_equipment=coarse,
                radiator_root=radiator_root(s,records))
    (args.out_dir/'readback.json').write_text(json.dumps(report,indent=1,default=str)+'\n')
    print('WF_READBACK',json.dumps({k:report[k] for k in ('objects','groups','rooms_measured','rooms_missing')}))


main()
