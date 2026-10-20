"""PROTOTYPE centre-of-mass and inertia proposal for owner feedback; writes JSON, never edits canon.

15_MODEL_INTERFACES S1 lets the Blender model propose X positions and feed them back. Each sourced 1,100 t
burnout budget item is spread uniformly over the proxy volume of its 13_MASS_POSITIONS region. The placement
rules are local assumptions, so physics.center_of_mass and physics.inertia stay known = false in the spec and rig.
Propellant and fusion fuel are OPEN and excluded, so this is a burnout (dry) proposal only.
"""
from pathlib import Path
import json
import math
import sys
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'src/wayfarer'))
from spec import load, derived
import hull_geometry
import forward_shield
import habitat_ring
import layout

OUTPUT=ROOT/'references/p1_mass_proposal.json'
N=24


def line_x(x0,x1,r=0.0,n=N):
    """Uniform samples along X on a ring of radius r (r = 0 is the axis)."""
    pts=[]
    for i in range(n):
        x=x0+(x1-x0)*(i+.5)/n
        pts+=[(x,r*math.cos(k*math.pi/4),r*math.sin(k*math.pi/4)) for k in range(8)] if r else [(x,0.0,0.0)]
    return pts


def shield_disc(s,n=N):
    """Area-uniform samples of the forward shield disc (forward_shield.stations): n equal-area rings of eight points at the skin mid-plane."""
    st=forward_shield.stations(s);x=(st['face']+st['skin_aft'])/2;pts=[]
    for i in range(n):
        r=st['shield_r']*math.sqrt((i+.5)/n)
        pts+=[(x,r*math.cos(k*math.pi/4),r*math.sin(k*math.pi/4)) for k in range(8)]
    return pts


def annular_points(x,phase,u0,u1,r0,r1,t0,t1,cell=1.0):
    """Equal-volume samples of a ring-local annular solid (habitat_ring frame: u axial from the ring plane at ship X x, angle t
    about +X from +Y, turned by the ring phase): area-uniform in r, uniform in t and u, about one point per `cell` m3, so
    parts of one item get points in proportion to their volume."""
    vol=(t1-t0)*.5*(r1*r1-r0*r0)*(u1-u0);edge=cell**(1/3)
    nr=max(1,round((r1-r0)/edge));nu=max(1,round((u1-u0)/edge));nt=max(1,round(vol/cell/(nr*nu)));pts=[]
    for i in range(nr):
        r=math.sqrt(r0*r0+(r1*r1-r0*r0)*(i+.5)/nr)
        for k in range(nt):
            a=phase+t0+(t1-t0)*(k+.5)/nt
            pts+=[(x+u0+(u1-u0)*(m+.5)/nu,r*math.cos(a),r*math.sin(a)) for m in range(nu)]
    return pts


def ring_frame(s):
    """(ship X, phase in rad) of each ring at its index angle (habitat_ring.centers, prototype.rotor_phase_deg)."""
    return [(x,math.radians(a)) for x,a in zip(habitat_ring.centers(s),s['prototype']['rotor_phase_deg'])]


def sectors(s):
    """The six pressurized sector envelopes (habitat_ring.sectors)."""
    rings=ring_frame(s);pts=[]
    for q in habitat_ring.sectors(s):
        x,phase=rings[q['ring']-1]
        pts+=annular_points(x,phase,-q['axial']/2,q['axial']/2,q['r0'],q['r1'],q['angle']-q['arc']/2,q['angle']+q['arc']/2)
    return pts


def frame(s,kind):
    """The ring frames' hoops ('ring_frame') or the fills between the sectors ('ring_fill') of both rings (habitat_ring.frame_parts)."""
    rings=ring_frame(s);pts=[]
    for q in habitat_ring.frame_parts(s):
        if q['kind']==kind:
            x,phase=rings[q['ring']-1]
            pts+=annular_points(x,phase,q['u0'],q['u1'],q['r0'],q['r1'],q['t0'],q['t1'])
    return pts


def eye_wells(s,n=N):
    """The four EYE facet modules: module depth aft of each well floor, on the well axes (forward_shield.wells)."""
    x1=forward_shield.stations(s)['front'];x0=x1-s['prototype']['eye_module_depth_m'];pts=[]
    for y,z in forward_shield.well_centres(s):
        pts+=[(x0+(x1-x0)*(i+.5)/n,y,z) for i in range(n)]
    return pts


def blades(s,d):
    p=s['prototype'];pts=[]
    for j in range(3):
        a=math.radians(p['radiator_phase_deg']+j*120)
        for i in range(N):
            x=d['aft_x_m']+(d['front_x_m']-d['aft_x_m'])*(i+.5)/N
            for k in range(8):
                r=d['inner_radius_min_m']+(d['outer_radius_m']-d['inner_radius_min_m'])*(k+.5)/8
                pts.append((x,r*math.cos(a),r*math.sin(a)))
    return pts


def placements(s,d,drive='spread'):
    """Budget item -> (sample points, rule). Rules follow the owner's qualitative regions."""
    p=s['prototype'];L=s['ship']['length']['value'];c=lambda k:layout.at(s,p[k+'_center_x'])
    xring=layout.at(s,p['thrust_ring_x']);spine=(-L/2+p['nozzle_length_m'],L/2-p['spine_forward_inset_m'])
    stations={x['id'].rsplit('.',1)[1]:layout.at(s,x['x']) for x in s['layout']['stations']}
    ref=hull_geometry.refuge(s);water=habitat_ring.water_item(s)
    drive_pts={'spread':line_x(-L/2,c('reactor')+p['reactor_length_m']/2),'core':line_x(c('reactor')-p['reactor_length_m']/2,c('reactor')+p['reactor_length_m']/2),
               'nozzles':line_x(-L/2,-L/2+p['nozzle_length_m'])}[drive]
    return {
        'main_structure':[(frame(s,'ring_frame'),25000.0,'rotating 25 t volume-uniform over the inner and outer hoops of both ring frames; spokes, hubs, bearings and locks are not separated (OD-016)'),(line_x(xring,layout.at(s,p['outer_cage_end_x']),s['structure']['sector_radius_m']),125000.0,'stationary 125 t on the primary-cage shell')],
        'forward_impact_shielding':[(shield_disc(s),100000.0,'forward shield disc (r 45 m, area-uniform samples at the skin mid-plane); the 100 t Brow mass is PROVISIONAL and not validated for 90 m')],
        'habitat_pressure_structure':[(sectors(s),90000.0,'volume-uniform over the six pressurized sector envelopes')],
        'eye_sensors':[(eye_wells(s),25000.0,'four facet modules, module depth aft of each well floor on the well axes (r 4.0 m)')],
        'life_support_garden_medical':[(sectors(s),55000.0,'volume-uniform over the six occupied sectors (12!A4,A6)')],
        'water_radiation_shielding':[(frame(s,'ring_fill'),water['rotating_allowance_kg'],'rotating ~160 t, volume-uniform over the frame fills between the sectors (12!A13; 13!A7 splits the 180 t water 160 t rotating + 20 t refuge, Q32)'),
                                     (line_x(ref['x0'],ref['x1'],(ref['pressure']+ref['outer'])/2),water['refuge_allowance_kg'],'stationary ~20 t of the 180 t water as the refuge shell (Q32), on the cylinder mid-radius; the shell the PROTOTYPE geometry would need is larger (owner_targets refuge_water_shell_kg, HAB-001)')],
        'workshop_spares_cargo':[(line_x(stations['STORAGE'],stations['RADIATOR_FRONT'],3.0),60000.0,'midship service volume between the STORAGE station and the radiator front (aft of the rings), r 3 m')],
        'drive_package':[(drive_pts,250000.0,{'spread':'uniform from the nozzle exits to the core front','core':'fusion-core envelope only','nozzles':'nozzle length only'}[drive])],
        'radiators_thermal':[(blades(s,d),100000.0,'uniform over the three blade planforms (upper bound; exchangers and buffers sit inboard)')],
        'power_computers_steering_comms':[(line_x(*spine),50000.0,'uniform along the Momentum Spine')],
        'food_consumables':[(line_x(ref['x0'],ref['x1'],ref['pressure']),10000.0,'stationary stores around the refuge (usable as refuge shielding)')],
        'design_margin':[(line_x(-L/2,L/2),30000.0,'uniform along the body axis')]}


def properties(s,d,drive='spread'):
    budget={i['id']:i['mass_kg'] for i in s['physics']['mass_budget']['items']}
    places=placements(s,d,drive);points=[];rules={}
    for item,parts in places.items():
        assert math.isclose(sum(m for _,m,_ in parts),budget[item]),item
        rules[item]=[r for *_,r in parts]
        for pts,m,_ in parts:points+=[(m/len(pts),q,item) for q in pts]
    assert set(places)==set(budget)
    M=sum(m for m,*_ in points);com=[sum(m*q[i] for m,q,_ in points)/M for i in range(3)]
    rel=[(m,[q[i]-com[i] for i in range(3)],item) for m,q,item in points]
    I={'Ixx_roll':sum(m*(v[1]**2+v[2]**2) for m,v,_ in rel),'Iyy_pitch':sum(m*(v[0]**2+v[2]**2) for m,v,_ in rel),'Izz_yaw':sum(m*(v[0]**2+v[1]**2) for m,v,_ in rel)}
    share={}
    for m,v,item in rel:share[item]=share.get(item,0)+m*(v[0]**2+v[2]**2)/I['Iyy_pitch']
    return M,com,I,rules,share


def refuge_shield(s):
    """Water-equivalent shell for the sourced 20 g/cm2 on the refuge's outer cylinder and both end annuli."""
    r=hull_geometry.refuge(s);rho=s['prototype']['refuge_shield_density_g_cm3']*1000
    outer=math.pi*(r['outer']**2-r['pressure']**2)*(r['x1']-r['x0']);ends=2*math.pi*(r['outer']**2-r['inner']**2)*r['shield_m']
    return {'shield_thickness_m':r['shield_m'],'mass_kg':rho*(outer+ends),'pressure_volume_m3':r['pressure_volume_m3'],'per_person_m3':r['pressure_volume_m3']/s['shielding']['refuge']['capacity_persons'],
            'allocation_kg':habitat_ring.refuge_water_allocation_kg(s),'exceeds_allocation_by_kg':rho*(outer+ends)-habitat_ring.refuge_water_allocation_kg(s),
            'note':'Outer cylinder plus end annuli at water density; the spine side is left open. 13_MASS_POSITIONS splits the 180 t water into ~160 t rotating and ~20 t stationary refuge (Q32); the PROTOTYPE refuge envelope needs more than that allocation (pending HAB-001), and the proposal places only the 20 t.'}


def run(root=ROOT):
    s,*_=load(root);d=derived(s)
    M,com,I,rules,share=properties(s,d)
    sens={k:properties(s,d,k)[1][0] for k in ['core','nozzles']}
    # One pose: the rings keep full size in every preset and their three-fold layout keeps the COM and transverse inertia independent
    # of the ring angle, so the index-angle pose holds for every preset.
    out={'mass_kg':M,'com_m':com,'inertia_about_com_kg_m2':I,'com_x_if_drive_package_at':sens,
         'pitch_inertia_share':dict(sorted(share.items(),key=lambda kv:-kv[1]))}
    result={'status':'PROTOTYPE_PROPOSAL_NOT_CANON',
            'scope':'Burnout (dry) 1,100 t budget only; reaction mass and fusion fuel are OPEN. Positions are local placement rules for owner review (15_MODEL_INTERFACES S1); spec and rig keep centre of mass and inertia unknown.',
            'placement_rules':rules,'pose':out,'refuge_shield':refuge_shield(s),
            'observations':[f"Dry COM sits about {out['com_m'][0]:.1f} m forward of the body midpoint (range {out['com_x_if_drive_package_at']['nozzles']:.1f}-{out['com_x_if_drive_package_at']['core']:.1f} m with the drive package at the nozzles or the core); the thrust line passes through it only because the layout is axisymmetric.",
                            'Largest pitch-inertia shares: '+', '.join(f'{k} {v:.0%}' for k,v in list(out['pitch_inertia_share'].items())[:4])+'.',
                            'Where the propellant tanks go (unsourced) will move the departure COM more than any dry-mass placement choice.']}
    OUTPUT.write_text(json.dumps(result,indent=1)+'\n')
    return result


if __name__=='__main__':
    r=run()
    for o in r['observations']:print('-',o)
    v=r['pose'];print([round(c,2) for c in v['com_m']],{a:f'{b:.3e}' for a,b in v['inertia_about_com_kg_m2'].items()},{a:round(b,2) for a,b in v['com_x_if_drive_package_at'].items()})
    print({k:(round(v,2) if isinstance(v,float) else v) for k,v in r['refuge_shield'].items() if k!='note'})
