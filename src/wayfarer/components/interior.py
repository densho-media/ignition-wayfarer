"""P1-004 rough sector interiors: PROTOTYPE zone blocks in the sector frame, one component per ring-sector function."""
from common import cut, empty, material, mesh
import habitat_interior

COLORS={'bunk':(.78,.62,.42),'burn_couch':(.70,.34,.30),'stowage':(.55,.52,.47),'hygiene':(.45,.70,.74),'operations':(.32,.45,.62),
        'workshop':(.58,.50,.36),'medical':(.86,.88,.90),'laboratory':(.62,.66,.72),'garden':(.30,.62,.28),
        'life_support':(.50,.56,.58),'common':(.72,.52,.34),'deck':(.30,.32,.34),'overhead':(.62,.64,.66)}


def box(c,name,lo,hi,mat,kind,parts=None,extra=()):
    # Vertex index = 4*ix + 2*iy + iz; faces wound outward. parts: several boxes in one mesh (the IND-001 whitebox shapes), each (min, max,
    # slot); slot k > 0 takes extra[k-1].
    vertices,faces,slots=[],[],[]
    for plo,phi,k in parts or [(lo,hi,0)]:
        n=len(vertices);vertices+=[(x,y,z) for x in (plo[0],phi[0]) for y in (plo[1],phi[1]) for z in (plo[2],phi[2])]
        faces+=[tuple(n+i for i in f) for f in [(0,1,3,2),(4,6,7,5),(0,4,5,1),(2,3,7,6),(0,2,6,4),(1,5,7,3)]];slots+=[k]*6
    obj=mesh(c,name,vertices,faces,mat,kind=kind)
    for m in extra:obj.data.materials.append(m)
    if extra:
        for p,k in zip(obj.data.polygons,slots):p.material_index=k
    return obj


def interior(c,s,function):
    # IND-001: a function in [sector_whitebox].functions has passed its human-scale whitebox; its blocks are drawn as furniture (a Garden
    # rack's frame in its own material, its crop in the Garden colour; consoles, displays and the berth steps dark, harness straps yellow).
    import sector_whitebox
    shaped=function in s['sector_whitebox']['functions']
    import route_fitout
    rack,dark,strap=material('Interior_Garden_Rack',(.74,.76,.72)),material('Interior_Console',(.16,.19,.23)),material('Interior_Strap',(.85,.62,.12))
    lamp=material('Interior_Berth_Light',(1.0,.78,.52),6.0)    # FUT-003: the berths' warm reading lights (an emitter of the S004 look)
    # IND-001 3.2 fit-out: the service block's open face recessed for its exposed lines, and the parts Seraph's space replaces.
    recess=route_fitout.service_recess(s,function) if shaped else None;seraph=route_fitout.seraph_elements(s,function)[1] if shaped else {}
    blocks=habitat_interior.zones(s,function)
    for b in habitat_interior.plates(s)+blocks:
        kind='sector_interior_zone' if 'side' in b else f'sector_interior_{b["zone"]}'
        mats,parts=[material(f'Interior_{b["zone"].title()}',COLORS[b['zone']])],None
        if shaped and 'side' in b:
            parts=[]
            for q in sector_whitebox.shapes(s,b,blocks):
                if q['part'] in seraph.get('drop',()) and b['name']==seraph['block']:continue
                if recess and b['name']==recess[0]:
                    lo,hi=list(q['min']),list(q['max']);_,k,at,at_max=recess
                    if at_max:hi[k]=min(hi[k],at)
                    else:lo[k]=max(lo[k],at)
                    q=dict(q,min=tuple(lo),max=tuple(hi))
                m=(mats[0] if q['part'].startswith('Crop') else rack) if b['zone']=='garden' else dark if q['part'].startswith(('Console','Display','Step_Rung','Grab_Bar')) \
                    else strap if q['part'].startswith(('Strap','Lap_Belt')) else lamp if q['part']=='Reading_Light' else mats[0]
                mats+=[m] if m not in mats else []
                parts.append((q['min'],q['max'],mats.index(m)))
        obj=box(c,b['name'],b['min'],b['max'],mats[0],kind,parts,mats[1:])
        if b['zone']=='overhead':
            # HUM-001 zone 5: the overhead panel opens around the hatch frame.
            x,z,r=habitat_interior.hatch_opening(s);obj=cut(obj,[((x,b['min'][1]-.05,z),(x,b['max'][1]+.05,z),r)])
        obj['zone']=b['zone'];obj['function']=function;obj['function_source']='habitat_layout'
        obj['rooms_status']='OPEN (habitat.layout.rooms)'
    import fitout
    fitout.sector_sign(c,s,function)   # IND-001 3.1: the sector's identity placard on the landing chase
    if shaped:fitout.sector(c,s,function)   # 3.2: the sector fit-out and Seraph's post
    hatch=empty(c,'IF_SECTOR_OVERHEAD_HATCH',habitat_interior.hatch(s))
    hatch['engineering_status']='OPEN OD-002: coast crew hatch; the PROTOTYPE crew tube runs out beside the crew spoke and lands on the pressure skin above it (crew_transfer); the HUM-001 zone 5 frame, sliding leaf and ladder are PROTOTYPE, seal and mechanism not designed'
