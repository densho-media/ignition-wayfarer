"""Reactor shadow-shield geometric screen for owner feedback; writes JSON, never edits canon.

Pure line-of-sight geometry on the PROTOTYPE proxies: which ring-sector and radiator volumes the flat shadow shield
covers from the fusion-core envelope, and what fraction of isotropic core emission the shield itself intercepts.
No emission spectrum, drive power, dose or heat load is computed; those stay OPEN.
"""
from pathlib import Path
import json
import math
import sys
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'src/wayfarer'))
from spec import load, derived
import habitat_ring
import layout

OUTPUT=ROOT/'references/p1_shadow_screen.json'


def cone_fraction(theta):
    """Share of isotropic emission from a point inside a cone of half-angle theta."""
    return (1-math.cos(theta))/2


def crosses(a,b,x0,x1,radius):
    """Does segment a->b pass through the full shield slab x0..x1 inside the given radius?"""
    if (a[0]-x0)*(b[0]-x0)>0 or (a[0]-x1)*(b[0]-x1)>0:return False
    for x in (x0,x1):
        t=(x-a[0])/(b[0]-a[0]);y=a[1]+t*(b[1]-a[1]);z=a[2]+t*(b[2]-a[2])
        if math.hypot(y,z)>radius:return False
    return True


def core_points(s):
    """Sample the fusion-core envelope: rim and axis points on both end faces and mid-length."""
    p=s['prototype'];xc=layout.at(s,p['reactor_center_x']);half=p['reactor_length_m']/2;r=p['reactor_radius_m'];pts=[]
    for x in (xc-half,xc,xc+half):
        pts.append((x,0.0,0.0))
        for rr in (r/2,r):
            pts+=[(x,rr*math.cos(k*math.pi/6),rr*math.sin(k*math.pi/6)) for k in range(12)]
    return pts


def sector_points(s,x,angle):
    """Occupied-volume samples of one ring sector: inner and outer sector radius at both axial faces and mid-length, at the sector
    angle. The rings rotate in LOW_THRUST, so run() takes 12 angles per ring."""
    hr=s['habitat_ring'];pts=[]
    for dx in (-hr['sector_axial_m']/2,0,hr['sector_axial_m']/2):
        for r in (hr['sector_inner_radius_m'],hr['sector_outer_radius_m']):
            pts.append((x+dx,r*math.cos(angle),r*math.sin(angle)))
    return pts


def run(root=ROOT):
    s,*_=load(root);d=derived(s);p=s['prototype'];L=s['ship']['length']['value']
    xs=layout.at(s,p['shadow_center_x']);x0,x1=xs-p['shadow_thickness_m']/2,xs+p['shadow_thickness_m']/2;R=p['shadow_radius_m']
    xc=layout.at(s,p['reactor_center_x'])
    full=math.atan2(R,x1-xc);partial=math.atan2(R,x0-xc)
    core=core_points(s)
    sectors=[];worst_angle=0.0
    for rotor,x in enumerate(habitat_ring.centers(s),1):
        for k in range(12):
            pts=sector_points(s,x,k*2*math.pi/12)
            angle=max(math.atan2(math.hypot(q[1],q[2]),q[0]-xc) for q in pts);worst_angle=max(worst_angle,angle)
            seen=[sum(not crosses(c,q,x0,x1,R) for c in core)/len(core) for q in pts]
            sectors.append({'sector':f'{rotor}.{k+1}','max_off_axis_deg':math.degrees(angle),
                            'max_core_samples_unshielded':max(seen),'mean_core_samples_unshielded':sum(seen)/len(seen)})
    # Radiator blade surfaces: share of cell centres outside the point-source full shadow (cell grid from the prototype cells).
    cells=[];r0=d['inner_radius_min_m'];r1=d['outer_radius_m'];nx=p['radiator_longitudinal_cells'];ny=p['radiator_transverse_cells']
    for i in range(nx):
        for k in range(ny):
            x=d['aft_x_m']+(d['front_x_m']-d['aft_x_m'])*(i+.5)/nx;r=r0+(r1-r0)*(k+.5)/ny
            cells.append(math.atan2(r,x-xc)>full)
    need=worst_angle
    result={'status':'GEOMETRIC_SCREEN_ONLY',
            'scope':'Line of sight on PROTOTYPE proxies (shield disk, fusion-core envelope, ring-sector samples, blade planform). No emission spectrum, drive power, dose or heat load; drive waste heat stays OPEN.',
            'inputs':{'shield_x_m':[x0,x1],'shield_radius_m':R,'core_center_x_m':xc,'core_radius_m':p['reactor_radius_m'],'core_length_m':p['reactor_length_m'],
                      'rotor_centers_m':habitat_ring.centers(s),'sector_radii_m':[s['habitat_ring']['sector_inner_radius_m'],s['habitat_ring']['sector_outer_radius_m']],
                      'blade_x_m':[d['aft_x_m'],d['front_x_m']],'radiator_cells':[nx,ny]},
            'point_source':{'full_shadow_half_angle_deg':math.degrees(full),'edge_shadow_half_angle_deg':math.degrees(partial),
                            'shield_intercept_fraction_full':cone_fraction(full),'shield_intercept_fraction_edge':cone_fraction(partial)},
            'rotating_sectors_low_thrust':{'max_off_axis_deg':math.degrees(worst_angle),'inside_point_source_full_shadow':worst_angle<full,
                                           'sectors':sectors,
                                           'note':'LOW_THRUST keeps the rings turning while the drive runs. A point source at the core centre shadows the sectors, but rim points of the 4.6 m core envelope may see past the 5.7 m disk.'},
            'minimum_cone_for_sectors':{'half_angle_deg':math.degrees(need),'intercept_fraction':cone_fraction(need),
                                        'note':'A shield sized only to cover the rotating sectors from the core centre (no margin) would intercept this share of isotropic emission.'},
            'radiator_cells_outside_full_shadow':sum(cells)/len(cells),
            'owner_questions':['Is the shadow shield meant to cover the rotating ring sectors during LOW_THRUST, and with what cone margin?',
                               'What share of core emission is radiated isotropically (bremsstrahlung, synchrotron, neutrons from D-D side reactions)? The shield intercepts that share times the fractions above, all of which must be rejected as heat.',
                               f'The cells outside the point-source shadow (about {sum(cells)/len(cells):.0%} of the blade cell centres, those aft of or beside the core) see the core directly; is that acceptable for neutron activation and heating?']}
    OUTPUT.write_text(json.dumps(result,indent=1)+'\n')
    return result


if __name__=='__main__':
    r=run()
    print(json.dumps({k:r[k] for k in ['point_source','minimum_cone_for_sectors','radiator_cells_outside_full_shadow']}|{'sectors_max_off_axis_deg':r['rotating_sectors_low_thrust']['max_off_axis_deg'],
                      'sectors_worst_unshielded_core_share':max(q['max_core_samples_unshielded'] for q in r['rotating_sectors_low_thrust']['sectors'])},indent=1))
