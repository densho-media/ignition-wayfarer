"""Generated simulation-rig empties and massless proxies inside a vehicle assembly. Frames and shapes come from sim_rig; nothing here defines physics."""
import math
import bpy
from mathutils import Matrix
from common import empty, material, mesh, loft
from sim_rig import anchors, proxies, CONTRACT, CONTRACT_VERSION


def box(c,name,center,size,mat):
    lo=[a-b/2 for a,b in zip(center,size)];hi=[a+b/2 for a,b in zip(center,size)]
    # Vertex index = 4*ix + 2*iy + iz; faces wound outward.
    vertices=[(x,y,z) for x in (lo[0],hi[0]) for y in (lo[1],hi[1]) for z in (lo[2],hi[2])]
    return mesh(c,name,vertices,[(0,1,3,2),(4,6,7,5),(0,4,5,1),(2,3,7,6),(0,2,6,4),(1,5,7,3)],mat,kind='sim_proxy')


def shape(c,item,mat):
    kind=item['shape']
    if kind=='box':return box(c,item['name'],item['center_m'],item['size_m'],mat)
    if kind=='cylinder':rings=[(item['x0_m'],item['radius_m']),(item['x1_m'],item['radius_m'])]
    elif kind=='frustum':rings=[(item['x0_m'],item['radius0_m']),(item['x1_m'],item['radius1_m'])]
    elif kind=='annulus':
        a,b,ro,ri=item['x0_m'],item['x1_m'],item['outer_radius_m'],item['inner_radius_m']
        return loft(c,item['name'],[(a,ro),(b,ro),(b,ri),(a,ri),(a,ro)],mat,caps=False,kind='sim_proxy')
    else:raise ValueError(kind)
    return loft(c,item['name'],rings,mat,kind='sim_proxy')


def rig(c,s,root_obj):
    base=empty(c,'WF_SIM_ROOT',ident='WF.SIM.ROOT',kind='sim_root')
    base.parent=root_obj;base['contract']=f'{CONTRACT} v{CONTRACT_VERSION}'
    frames={'WF_SIM_ROOT':base}
    for item in anchors(s):
        if item['name']=='WF_SIM_ROOT':
            obj=base
        else:
            obj=empty(c,item['name'],item['position_m'],ident=item['id'],kind='sim_anchor');obj.parent=base
            obj.matrix_world=Matrix([[item['axis'][i],item['side'][i],item['up'][i],item['position_m'][i]] for i in range(3)]+[[0,0,0,1]])
        obj['role']=item['role'];obj['relation']=item['relation'];obj['geometry_status']=item['geometry_status']
        obj['interface_refs']='; '.join(f"{r['asset']}:{r['object']}" for r in item['interface_refs'])
        # Unknown quantities stay explicit ({'known': False, ...}); IDProperties never carry None.
        obj['sim']=item['quantities'];frames[item['name']]=obj
    # Proxies are hidden from viewport evaluation and render, so previews and geometry checks never see them.
    mat=material('SimProxy',(.85,.25,.75))
    for item in proxies(s):
        obj=shape(c,item,mat);obj.parent=frames[item['anchor']]
        obj.display_type='WIRE';obj.hide_viewport=obj.hide_render=True
        obj['anchor']=item['anchor'];obj['shape']=item['shape'];obj['purpose']=item['purpose'];obj['motion']=item['motion']['type']
        obj['mass_known']=False;obj['geometry_status']=item['geometry_status']
    return base
