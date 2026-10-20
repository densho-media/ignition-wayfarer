"""Cosine-weighted geometric sky-escape sampling; not a qualified thermal solver."""
from pathlib import Path
import sys,math,json,argparse
import bpy
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT/'src/wayfarer'),str(ROOT/'src/wayfarer/build')]
from spec import load,derived
from common import pose_configuration
from thermal_geometry import point


def inspect(root=ROOT,output=None,state='COAST'):
    s,*_=load(root);d=derived(s);p=s['prototype'];rays=96
    cfg=s['configuration'][state]
    if not cfg['buildable']:raise ValueError(f'Not a buildable configuration: {state}')
    bpy.ops.wm.open_mainfile(filepath=str(root/f"assets/wayfarer/{s['vehicle']['asset']}.blend"))
    pose_configuration(s,state)
    # Radiators are fixed in every mode (R1/R8, MEC-012): the saved geometry is sampled as is.
    deps=bpy.context.evaluated_depsgraph_get();results=[]
    for sector in range(s['radiators']['count']):
        a=math.radians(p['radiator_phase_deg']+sector*120)
        radial=Vector((0,math.cos(a),math.sin(a)));normal=Vector((0,-math.sin(a),math.cos(a)))
        u=Vector((d['cos'],0,0))-radial*d['sin'];v=Vector((d['sin'],0,0))+radial*d['cos']
        for face in [-1,1]:
            clear=total=0
            for f in [-.37,-.09,.23,.43]:
                for ribbon in range(d['ribbons']):
                    for w in [.17,.53,.87]:
                        x,rr=point(d,f*d['blade_length_m'],ribbon*(d['ribbon_width_m']+d['gap_m'])+w*d['ribbon_width_m'])
                        origin=Vector((x,0,0))+rr*radial+face*normal*(p['radiator_thickness_m']/2+.025)
                        for k in range(rays):
                            rho=math.sqrt((k+.5)/rays);phi=k*math.pi*(3-math.sqrt(5))
                            direction=u*(rho*math.cos(phi))+v*(rho*math.sin(phi))+face*normal*math.sqrt(1-rho*rho)
                            hit,*_=bpy.context.scene.ray_cast(deps,origin,direction,distance=2000)
                            clear+=not hit;total+=1
            results.append({'sector':sector+1,'face':face,'escape_fraction':clear/total,'rays':total})
    escape=sum(x['escape_fraction'] for x in results)/len(results)
    report={'status':'GEOMETRIC_SCREEN_ONLY','configuration':state,'method':'Deterministic cosine-weighted rays from 12 points per face per ribbon, 96 rays/point, frame 1 of the posed preset; any mesh hit blocks sky. No emissivity, scattering, temperature or re-radiation solution.',
            'faces':results,'mean_sky_escape_fraction':escape,
            'effective_area_if_escape_used_as_factor_m2':d['total_net_area_m2']*2*escape,
            'working_view_factor':s['radiators']['view_factor']['value'],
            'sensitivity_effective_area_m2':{str(f):d['total_net_area_m2']*2*f for f in [.6,.75,.9]},
            'physical_area_unchanged_m2':d['total_planform_m2'],
            'limitations':'Finite samples, proxy hardware and one rotor phase; directional visibility is not proof of 0.9 thermal view factor. Physical geometry is not resized to compensate.'}
    default=root/('references/p1_visibility.json' if state=='COAST' else f'references/p1_visibility_{state.lower()}.json')
    (output or default).write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--root',type=Path,default=ROOT);a.add_argument('--output',type=Path);a.add_argument('--state',default='COAST')
    a=a.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    inspect(a.root.resolve(),a.output,a.state)
