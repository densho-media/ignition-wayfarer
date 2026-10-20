"""Station-lofted PROTOTYPE hull shell. Pure geometry; a silhouette-editing proxy, not a pressure hull or armour claim.

Stations give (x, radius, section). A station's radius is a fraction of the body radius or the RADIATOR_CASING rule (root radius
less the member clearance: the casing under the blade span). Skinned spans exclude the exposed thrust ring, the open rotor bay and
the bow (the collar stops short of the forward shield skin, FGR-006). Openings are derived where existing radiator members cross the shell. Standard library only.
"""
import math
import thermal_geometry
from thermal_geometry import supports, casing_radius
import habitat_ring
import forward_shield
import layout


def stations(s):
    R=s['ship']['body_diameter']['value']/2
    return [dict(id=x['id'],x=layout.at(s,x['x']),r=casing_radius(s) if x.get('radius_rule')=='RADIATOR_CASING' else x['radius_fraction']*R,section=x.get('section','CIRCLE'),sides=x.get('sides',0),role=x['role'])
            for x in s['layout']['stations']]


def profile(s):
    return [x for x in stations(s) if x['section']!='NONE']


def radius_at(s,x):
    """Linear between skinned stations; clamped beyond the first and last."""
    pts=profile(s)
    if x<=pts[0]['x']:return pts[0]['r']
    for a,b in zip(pts,pts[1:]):
        if x<=b['x']:return a['r']+(b['r']-a['r'])*(x-a['x'])/(b['x']-a['x'])
    return pts[-1]['r']


def section_at(s,x):
    pts=profile(s)
    return min(pts,key=lambda p:abs(p['x']-x))


def section_radius(section,sides,r,theta):
    """Outer radius of a CIRCLE or POLYGON (circumradius r, a vertex at theta = 0) in direction theta."""
    if section!='POLYGON':return r
    step=2*math.pi/sides;local=theta%step-step/2
    return r*math.cos(step/2)/math.cos(local)


def intervals(s,d=None):
    """Skinned axial spans, all derived from existing geometry and the shared mechanical clearance."""
    p=s['prototype'];st=s['structure'];L=s['ship']['length']['value'];clr=p['mechanical_clearance_m']
    xring=layout.at(s,p['thrust_ring_x'])
    aft=xring+st['ring_depth_m']/2+p['structural_strut_radius_m']+clr
    # The open bay follows the swept axial extent of the rigid rings (habitat_ring.sweep_half) plus the shared clearance.
    half=habitat_ring.sweep_half(s)
    rc=habitat_ring.centers(s)
    bay=(min(rc)-half-clr,max(rc)+half+clr)
    # The collar passes through the shield's truss hub opening and stops one clearance short of the skin's aft face.
    fore=forward_shield.stations(s)['collar_end']
    return [('Hull_Aft_Body',aft,bay[0]),('Hull_Forward_Collar',bay[1],fore)]


def phase(s):
    """Angular offset so each radiator sector falls at a quad centre: one quad per opening."""
    step=2*math.pi/s['hull']['segments'];a=math.radians(s['prototype']['radiator_phase_deg'])
    return (a-step/2)%step


def openings(s,d):
    """Windows (x0, x1, theta0, theta1) where radiator members cross the shell; overlapping windows merge."""
    t=s['hull']['shell_thickness_m'];clr=s['prototype']['mechanical_clearance_m'];spans=intervals(s)
    windows=[]
    for m in supports(s,d):
        pts=m.get('path') or [m['start'],m['end']]
        S,E=pts[0],pts[1]      # the first leg crosses the shell (a path's later legs stay outside it)
        D=[b-a for a,b in zip(S,E)]
        P=lambda u:[a+u*b for a,b in zip(S,D)]
        rho=lambda q:math.hypot(q[1],q[2])
        crossings=[]
        for inset in [0,t]:
            f=lambda u:rho(P(u))-(radius_at(s,P(u)[0])-inset)
            if f(0)>=0 or f(1)<=0:continue
            lo,hi=0.0,1.0
            for _ in range(60):
                mid=(lo+hi)/2
                lo,hi=(mid,hi) if f(mid)<0 else (lo,mid)
            crossings.append(P(hi))
        if not crossings:continue
        xs=[q[0] for q in crossings];outer=crossings[0]
        if not any(a<=x<=b for _,a,b in spans for x in xs):continue
        w=m['radius']+clr;sin=math.hypot(D[1],D[2])/math.sqrt(sum(v*v for v in D))
        theta=math.atan2(outer[2],outer[1]);dt=w/math.hypot(outer[1],outer[2])
        windows.append(dict(members=[m['name']],x0=min(xs)-w/sin,x1=max(xs)+w/sin,t0=theta-dt,t1=theta+dt,at=outer,sector=m['sector']))
    for f in service_fittings(s):
        w=f['radius']+clr;dt=w/(f['r_hull']-t)
        windows.append(dict(members=[f['name']],x0=f['x']-w,x1=f['x']+w,t0=f['theta']-dt,t1=f['theta']+dt,
                            at=(f['x'],f['r_hull']*math.cos(f['theta']),f['r_hull']*math.sin(f['theta'])),sector=f['name']))
    # FGR-006 shield-mount struts cross the collar through their own windows, like the service fittings.
    for m in forward_shield.mount_struts(s):
        w=m['radius']+clr;r_hull=radius_at(s,m['x']);dt=w/(r_hull-t)
        windows.append(dict(members=[m['name']],x0=m['x']-w,x1=m['x']+w,t0=m['theta']-dt,t1=m['theta']+dt,
                            at=(m['x'],r_hull*math.cos(m['theta']),r_hull*math.sin(m['theta'])),sector=m['name']))
    # FWD-001 sector ties run from the keel heads (inside the collar) out to the truss hub ring and the first truss ring: they cross the collar like the supports.
    for m in forward_shield.sector_ties(s):
        w=member_window(s,m['a'],m['b'],m['radius'],spans)
        if w:windows.append(dict(w,members=[m['name']],sector=f"Shield_Sector_{m['sector']}"))
    # FWD-003 / Q45 bypass collar: the aft spokes and keel ties run from the sector rails (inside the hull) out to the collar.
    for m in forward_shield.bypass_collar(s)['members']:
        if m['role'] in ('aft_spoke','keel_tie'):
            w=member_window(s,m['a'],m['b'],m['radius'],spans)
            if w:windows.append(dict(w,members=[m['name']],sector=f"Bypass_{m['role']}_{m['sector']}"))
    merged=[]
    for w in sorted(windows,key=lambda w:(str(w['sector']),w['x0'])):
        o=next((v for v in merged if v['sector']==w['sector'] and w['x0']<=v['x1'] and v['x0']<=w['x1'] and angular_overlap(w['t0'],w['t1'],v['t0'],v['t1'])),None)
        if o:o.update(members=o['members']+w['members'],x0=min(o['x0'],w['x0']),x1=max(o['x1'],w['x1']),t0=min(o['t0'],w['t0']),t1=max(o['t1'],w['t1']))
        else:merged.append(w)
    return merged


def member_window(s,S,E,radius,spans):
    """Window (x0, x1, theta0, theta1, at) where a straight member from S to E crosses the shell, or None; same rule as the radiator supports."""
    t=s['hull']['shell_thickness_m'];clr=s['prototype']['mechanical_clearance_m']
    D=[b-a for a,b in zip(S,E)]
    P=lambda u:[a+u*b for a,b in zip(S,D)]
    rho=lambda q:math.hypot(q[1],q[2])
    crossings=[]
    for inset in [0,t]:
        f=lambda u:rho(P(u))-(radius_at(s,P(u)[0])-inset)
        if f(0)>=0 or f(1)<=0:continue
        lo,hi=0.0,1.0
        for _ in range(60):
            mid=(lo+hi)/2
            lo,hi=(mid,hi) if f(mid)<0 else (lo,mid)
        crossings.append(P(hi))
    if not crossings:return None
    xs=[q[0] for q in crossings];outer=crossings[0]
    if not any(a<=x<=b for _,a,b in spans for x in xs):return None
    w=radius+clr;sin=math.hypot(D[1],D[2])/math.sqrt(sum(v*v for v in D))
    theta=math.atan2(outer[2],outer[1]);dt=w/math.hypot(outer[1],outer[2])
    return dict(x0=min(xs)-w/sin,x1=max(xs)+w/sin,t0=theta-dt,t1=theta+dt,at=outer)


def service_fittings(s):
    """Radial PROTOTYPE tubes from near the spine through the hull: EVA airlock and two docking ports (14_HULL_SERVICE)."""
    p=s['prototype'];out=[]
    for name,role,x,deg,a,ref in [('Airlock_EVA','EVA airlock','airlock_x','airlock_angle_deg','airlock_radius_m','eva_access'),
                                  ('Dock_Primary','primary boarding port','dock_x','dock_primary_angle_deg','dock_radius_m','dock_ports'),
                                  ('Dock_Service','service/contingency port','dock_x','dock_service_angle_deg','dock_radius_m','dock_ports')]:
        xc=layout.at(s,p[x]);r_hull=radius_at(s,xc)
        out.append(dict(name=name,role=role,x=xc,theta=math.radians(p[deg]),radius=p[a],r0=p['service_inner_radius_m'],r_hull=r_hull,
                        r1=r_hull+p['service_collar_m'],interface='IF_'+name.upper(),source_ref=ref))
    return out


def refuge(s):
    """Annular storm-refuge shell around the spine (HAB-001, Q31/Q32). The envelope [x0, x1] holds both end caps; the shell thickness is the sourced areal
    density over the selected shield density (20 g/cm2 at 1 g/cm3 = 0.20 m). Pressure cavity V = pi (r_p^2 - r_i^2)(L - 2t); water-equivalent shell volume =
    envelope volume pi (r_o^2 - r_i^2) L minus V. `shell_profile` is the closed (x, r) section of the shell alone, revolved by the recipe."""
    p=s['prototype'];r=s['shielding']['refuge']
    shield=r['areal_density_g_cm2']/p['refuge_shield_density_g_cm3']/100
    x0=layout.at(s,p['refuge_x0']);x1=layout.at(s,p['refuge_x1'])
    inner=max(layout.spine_radius_at(s,x0),layout.spine_radius_at(s,x1))+p['mechanical_clearance_m']
    length=x1-x0;pressure=p['refuge_pressure_radius_m'];outer=pressure+shield
    cx0,cx1=x0+shield,x1-shield
    volume=math.pi*(pressure**2-inner**2)*(cx1-cx0)
    shield_volume=math.pi*(outer**2-inner**2)*length-volume
    profile=[(x0,outer),(x1,outer),(x1,inner),(cx1,inner),(cx1,pressure),(cx0,pressure),(cx0,inner),(x0,inner)]
    return dict(x0=x0,x1=x1,cavity_x0=cx0,cavity_x1=cx1,inner=inner,pressure=pressure,outer=outer,shield_m=shield,
                pressure_volume_m3=volume,capacity_persons=r['capacity_persons'],volume_per_person_m3=volume/r['capacity_persons'],
                shield_volume_m3=shield_volume,shell_profile=profile)


def frame_stations(s):
    """X of every primary-cage frame: the thrust ring, the transition frames, every frame_spacing_m to the cage end, plus the blade root and
    stay stations (as revision.structure builds them)."""
    p=s['prototype'];st=s['structure']
    xring=layout.at(s,p['thrust_ring_x']);cage_end=layout.at(s,p['outer_cage_end_x'])
    xs=[xring+t for t in st['transition_frame_offsets_m']];xx=xs[-1]+st['frame_spacing_m']
    while xx<cage_end:
        xs.append(xx);xx+=st['frame_spacing_m']
    xs.append(cage_end)
    at=thermal_geometry.stations(s,thermal_geometry.blade_of(s))
    return sorted(set(xs+at['roots']+at['stays']))


def cage_points(s):
    """Sampled primary-cage members (frames, rails, braces) as (x, y, z, member radius); mirrors revision.structure."""
    p=s['prototype'];st=s['structure']
    phase=math.radians(p['ring_phase_deg'])
    sectors=[phase+n*2*math.pi/st['ring_nodes'] for n in st['sector_pickup_nodes']]
    xs=frame_stations(s)
    R=st['sector_radius_m'];strut=p['structural_strut_radius_m'];pts=[]
    rad=lambda x,r,a:(x,r*math.cos(a),r*math.sin(a))
    for n,x in enumerate(xs):
        r=st['ring_node_radius_m'] if n==0 else R
        pts+=[(*rad(x,r,k*2*math.pi/240),strut) for k in range(240)]
        if n:
            prev=xs[n-1];rp=st['ring_node_radius_m'] if n==1 else R
            for a in sectors:
                pts+=[(*rad(prev+(x-prev)*k/60,rp+(r-rp)*k/60,a),p['structural_rail_radius_m']) for k in range(61)]
                pts+=[(*rad(prev+(x-prev)*k/120,rp+(r-rp)*k/120,a+2*math.pi/3*k/120),.075) for k in range(121)]
    return pts


def fitting_margin(fitting,points):
    """Smallest surface gap between a radial fitting tube and sampled members."""
    u=(math.cos(fitting['theta']),math.sin(fitting['theta']));worst=math.inf
    for x,y,z,rr in points:
        along=y*u[0]+z*u[1]
        if not fitting['r0']-rr<=along<=fitting['r1']+rr:continue
        worst=min(worst,math.sqrt((x-fitting['x'])**2+(y-along*u[0])**2+(z-along*u[1])**2)-fitting['radius']-rr)
    return worst


def angular_overlap(a0,a1,b0,b1):
    for k in [-1,0,1]:
        if a0<b1+2*math.pi*k and b0+2*math.pi*k<a1:return True
    return False


def shell(s,d):
    """Per span: vertices, quads (outward normals, common.loft order) and omitted quad count. No caps."""
    n=s['hull']['segments'];ph=phase(s);step=2*math.pi/n;holes=openings(s,d);parts=[]
    for name,x0,x1 in intervals(s):
        xs={x0,x1}|{p['x'] for p in profile(s) if x0<p['x']<x1}
        xs|={v for w in holes for v in [w['x0'],w['x1']] if x0<v<x1}
        # Sectors share window edges up to float noise; merge them so no zero-width rings appear.
        xs=[x for i,x in enumerate(sorted(xs)) if i==0 or x-sorted(xs)[i-1]>1e-6];vertices=[];faces=[];omitted=0
        for x in xs:
            sec=section_at(s,x);r=radius_at(s,x)
            for j in range(n):
                a=ph+j*step;rr=section_radius(sec['section'],sec['sides'],r,a)
                vertices.append((x,rr*math.cos(a),rr*math.sin(a)))
        for k in range(len(xs)-1):
            for j in range(n):
                a0=ph+j*step;a1=a0+step
                if any(xs[k]<w['x1']-1e-6 and w['x0']+1e-6<xs[k+1] and angular_overlap(a0,a1,w['t0'],w['t1']) for w in holes):
                    omitted+=1;continue
                faces.append((k*n+j,k*n+(j+1)%n,(k+1)*n+(j+1)%n,(k+1)*n+j))
        parts.append(dict(name=name,x0=x0,x1=x1,rings=xs,vertices=vertices,faces=faces,omitted=omitted))
    return parts


def enclosure_bands(s):
    """Existing internal geometry the shell must clear: (name, x0, x1, r at x0, r at x1)."""
    p=s['prototype'];st=s['structure'];e=s['eye'];L=s['ship']['length']['value'];xring=layout.at(s,p['thrust_ring_x'])
    rail=p['structural_rail_radius_m'];strut=p['structural_strut_radius_m'];off=st['transition_frame_offsets_m']
    c=lambda key:layout.at(s,p[key+'_center_x'])
    cage_end=layout.at(s,p['outer_cage_end_x']);bx=layout.at(s,p['brayton_center_x']);mount_aft=layout.at(s,p['forward_mount_aft_x']);mount_fwd=layout.at(s,p['forward_mount_fwd_x'])
    refuge_x0=layout.at(s,p['refuge_x0']);refuge_x1=layout.at(s,p['refuge_x1'])
    front=L/2-p['eye_front_inset_m'];mount=front-p['eye_module_depth_m']
    return [('transition cage',xring,xring+off[1],st['ring_node_radius_m']+rail,st['sector_radius_m']+rail),
            ('primary cage',xring+off[1],cage_end,st['sector_radius_m']+rail,st['sector_radius_m']+rail),
            ('reactor shadow shield',c('shadow')-p['shadow_thickness_m']/2,c('shadow')+p['shadow_thickness_m']/2,p['shadow_radius_m'],p['shadow_radius_m']),
            ('tank volumes',c('tank')-p['tank_length_m']/2,c('tank')+p['tank_length_m']/2,*[p['tank_offset_m']*math.sqrt(2)+p['tank_radius_m']]*2),
            ('engineering envelope',c('engineering')-p['engineering_length_m']/2,c('engineering')+p['engineering_length_m']/2,*[p['engineering_radius_m']]*2),
            ('fusion core',c('reactor')-p['reactor_length_m']/2,c('reactor')+p['reactor_length_m']/2,*[p['reactor_radius_m']]*2),
            ('Brayton trains',bx-p['brayton_length_m']/2,bx+p['brayton_length_m']/2,*[p['brayton_offset_y_m']+p['brayton_radius_m']]*2),
            ('forward mount struts',mount_aft,mount_fwd,p['forward_mount_inner_radius_m']+strut,p['forward_mount_outer_radius_m']+strut),
            ('EYE backing',mount-p['eye_backing_depth_m'],mount,*[p['eye_backing_radius_m']]*2),
            ('EYE facets',mount,front,*[e['array_baseline']['value']/2+e['aperture']['value']/2]*2),
            ('EYE wells',front,forward_shield.stations(s)['face'],*[math.hypot(*forward_shield.well_centres(s)[0])+forward_shield.prototype(s)['well_diameter_m']/2]*2),
            ('storm refuge',refuge_x0,refuge_x1,*[refuge(s)['outer']]*2)]+[
            # FWD-001 forward sector keels: Brow-side sector keels ahead of ring B (aft ends free, draft Q45) inside the collar (rail radius at the sourced sector radius).
            ('forward sector keels',k['x0'],k['x1'],k['r']+k['radius'],k['r']+k['radius']) for k in forward_shield.sector_keels(s)[:1]]


def inner_radius_at(s,x):
    """Smallest inner surface radius at x: polygon sections use their inscribed radius."""
    sec=section_at(s,x);r=radius_at(s,x)
    if sec['section']=='POLYGON':r*=math.cos(math.pi/sec['sides'])
    return r-s['hull']['shell_thickness_m']


def margins(s):
    """Minimum clearance per band inside skinned spans; piecewise-linear, so breakpoints suffice."""
    clr=s['prototype']['mechanical_clearance_m'];out={}
    for name,b0,b1,r0,r1 in enclosure_bands(s):
        for _,x0,x1 in intervals(s):
            lo,hi=max(b0,x0),min(b1,x1)
            if lo>hi:continue
            for x in [lo,hi]+[p['x'] for p in profile(s) if lo<p['x']<hi]:
                need=r0+(r1-r0)*((x-b0)/(b1-b0) if b1>b0 else 0)+clr
                m=inner_radius_at(s,x)-need
                if name not in out or m<out[name][0]:out[name]=(m,x,need)
    return out


def check(s):
    h=s['hull'];L=s['ship']['length']['value'];R=s['ship']['body_diameter']['value']/2
    if h['status']!='PROTOTYPE':raise ValueError('Hull shell is a PROTOTYPE proxy')
    if not (0<h['shell_thickness_m']<.5 and type(h['segments']) is int and h['segments']>=12 and h['segments']%s['radiators']['count']==0):
        raise ValueError('Hull thickness/segments')
    for x in stations(s):
        if x['section'] not in {'CIRCLE','POLYGON','NONE'} or (x['section']=='POLYGON' and (type(x['sides']) is not int or x['sides']<6)):
            raise ValueError(f"{x['id']}: hull section")
        if x['r']>R+1e-9:raise ValueError(f"{x['id']}: hull station outside body envelope")
    for name,x0,x1 in intervals(s):
        if not -L/2<=x0<x1<=L/2:raise ValueError(f'{name}: hull span outside body length')
    for name,(m,x,need) in margins(s).items():
        if m<0:
            near=section_at(s,x)
            raise ValueError(f"Hull does not enclose {name} at X={x:.2f} m: {near['id']} needs outer radius >= {need+s['hull']['shell_thickness_m']:.3f} m (fraction {(need+s['hull']['shell_thickness_m'])/R:.3f})")
    p=s['prototype'];clr=p['mechanical_clearance_m'];spans=intervals(s)
    ref=refuge(s);centers=habitat_ring.centers(s);sweep=habitat_ring.sweep_half(s);mount_aft=layout.at(s,p['forward_mount_aft_x'])
    span_of=lambda lo,hi:next((v for v in spans if v[1]<=lo and hi<=v[2]),None)
    if not (span_of(ref['x0'],ref['x1']) and ref['pressure']>ref['inner']):
        raise ValueError('Storm refuge must sit inside a skinned hull span and outside the spine')
    if ref['x0']-clr<max(centers)+sweep:
        raise ValueError('Storm refuge overlaps the rotor bay')
    if ref['x1']+clr>mount_aft:
        raise ValueError('Storm refuge reaches the forward mount struts')
    points=cage_points(s)+forward_shield.keel_points(s)
    for f in service_fittings(s):
        if not span_of(f['x']-f['radius']-clr,f['x']+f['radius']+clr):raise ValueError(f"{f['name']} must penetrate a skinned hull body")
        if f['x']+f['radius']+clr>ref['x0'] and f['x']-f['radius']-clr<ref['x1']:raise ValueError(f"{f['name']} intersects the storm refuge")
        m=fitting_margin(f,points)
        if m<clr:raise ValueError(f"{f['name']} clears the primary cage and the forward sector keels by {m:.3f} m; needs {clr} m")
    fittings=service_fittings(s)
    for i,a in enumerate(fittings):
        for b in fittings[i+1:]:
            gap=distance_between_radials(a,b)-a['radius']-b['radius']
            if gap<clr:raise ValueError(f"{a['name']} and {b['name']} clear each other by {gap:.3f} m; needs {clr} m")
    # Casing: exactly the casing radius at every breakpoint under the blade span; the forward collar keeps the full body radius.
    o=layout.origins(s);cas=casing_radius(s)
    for x in profile(s):
        if o['RADIATOR_AFT']-1e-9<=x['x']<=o['RADIATOR_FRONT']+1e-9 and abs(x['r']-cas)>1e-9:
            raise ValueError(f"{x['id']}: casing radius {x['r']} differs from {cas} under the blade span")
        if x['x']>=o['RING_A']-1e-9 and abs(x['r']-R)>1e-9:
            raise ValueError(f"{x['id']}: forward station must keep the {R} m body radius")
    rows=corridor_rows(s)
    for name,r in rows.items():
        if not r['pass']:raise ValueError(f'Docking corridor {name}: {r["fail"]}')
    for name,r in capture_ring_rows(s).items():
        if not r['pass']:raise ValueError(f'Capture ring {name}: {r["fail"]}')
    return summary(s)


def distance_between_radials(a,b,n=60):
    """Smallest distance between two radial segments given as ((x,r0,r1,theta)), sampled; both start outside the spine."""
    best=math.inf
    for i in range(n+1):
        ra=a['r0']+(a['r1']-a['r0'])*i/n
        pa=(a['x'],ra*math.cos(a['theta']),ra*math.sin(a['theta']))
        for k in range(n+1):
            rb=b['r0']+(b['r1']-b['r0'])*k/n
            pb=(b['x'],rb*math.cos(b['theta']),rb*math.sin(b['theta']))
            best=min(best,math.dist(pa,pb))
    return best


def dock_corridors(s):
    """PROTOTYPE visiting-vehicle keep-out of each docking port (15_MODEL_INTERFACES D1): a cylinder of dock_corridor_radius_m
    along the dock's radial axis from the collar tip out to the forward-shield radius. Not a docking standard."""
    p=s['prototype'];shield_r=s['forward_shield']['diameter']['value']/2
    return [dict(name=f['name'],x=f['x'],theta=f['theta'],r0=f['r1'],r1=shield_r,radius=p['dock_corridor_radius_m']) for f in service_fittings(s) if f['name'].startswith('Dock_')]


def corridor_rows(s):
    """Axial gaps of each corridor to the ring sweeps and the blade front plus spar, extent inside the forward collar, the smallest separation to
    the other corridor and to the airlock tube, and the gap to the shield structure (truss, rim, Crown, keels, ties). Each row has pass/fail."""
    p=s['prototype'];clr=p['mechanical_clearance_m'];d=thermal_geometry.blade_of(s);sweep=habitat_ring.sweep_half(s)
    _,collar=intervals(s);fittings={f['name']:f for f in service_fittings(s)};air=fittings['Airlock_EVA']
    out={};cs=dock_corridors(s)
    for c in cs:
        x0,x1=c['x']-c['radius'],c['x']+c['radius']
        ring_gaps=[x0-(rc+sweep) for rc in habitat_ring.centers(s)]
        blade_gap=x0-(d['front_x_m']+p['radiator_leading_spar_radius_m'])
        others=[distance_between_radials(c,o)-c['radius']-o['radius'] for o in cs if o is not c]
        airlock=distance_between_radials(c,dict(x=air['x'],theta=air['theta'],r0=air['r0'],r1=air['r1'],radius=air['radius']))-c['radius']-air['radius']
        fail=[]
        if min(ring_gaps)<clr:fail.append(f'ring sweep gap {min(ring_gaps):.3f} m < {clr}')
        if blade_gap<clr:fail.append(f'blade front gap {blade_gap:.3f} m < {clr}')
        if not (collar[1]<=x0 and x1<=collar[2]):fail.append('corridor leaves the forward collar span')
        if others and min(others)<=0:fail.append('corridors overlap')
        if airlock<=0:fail.append('corridor overlaps the airlock tube')
        shield=forward_shield.corridor_clearance_rows(s)[c['name']]
        if not shield['passes']:fail.append(f"shield structure gap {shield['min_gap_m']:.3f} m < {clr}: {shield['gaps_m']}")
        out[c['name']]=dict(x0=x0,x1=x1,ring_gaps_m=ring_gaps,blade_front_gap_m=blade_gap,corridor_separation_m=min(others) if others else None,
                            airlock_separation_m=airlock,shield_gap_m=shield['min_gap_m'],pass_=not fail,fail='; '.join(fail))
        out[c['name']]['pass']=out[c['name']].pop('pass_')
    return out


def capture_rings(s):
    """Structural capture ring of each docking port (Q33, PROTOTYPE, HSFP class F for the size, L for the passage): a short collar of outer radius
    dock_capture_ring_radius_m and radial depth dock_capture_ring_depth_m on the collar tip, around the fitting. Androgynous: both ports carry the same ring."""
    p=s['prototype']
    return [dict(name=f['name']+'_Capture_Ring',fitting=f['name'],x=f['x'],theta=f['theta'],r0=f['r1'],r1=f['r1']+p['dock_capture_ring_depth_m'],
                 radius=p['dock_capture_ring_radius_m'],inner=f['radius'],interface='IF_'+f['name'].upper()+'_CAPTURE_RING') for f in service_fittings(s) if f['name'].startswith('Dock_')]


def capture_ring_rows(s,around=72):
    """Gaps (sampled on the ring surface, sample half-spacing subtracted) of each capture ring to the other docking corridor, the airlock tube, the other
    dock fitting, the keels and keel hoops, the ties, the survival packs and the hull outer radius; plus the ring-against-passage and own-corridor
    proportions. Each row has pass/fail against the shared mechanical clearance."""
    import power_storage
    p=s['prototype'];clr=p['mechanical_clearance_m'];fittings={f['name']:f for f in service_fittings(s)};corr={c['name']:c for c in dock_corridors(s)}
    keels=forward_shield.keel_points(s);ties=forward_shield.sector_ties(s);packs=power_storage.packs(s);sd=forward_shield.segment_distance;out={}
    for q in capture_rings(s):
        u=(math.cos(q['theta']),math.sin(q['theta']));w=(-math.sin(q['theta']),math.cos(q['theta']))
        pts=[]
        for r in (q['r0'],q['r1']):
            for rho in [q['inner']+(q['radius']-q['inner'])*i/7 for i in range(8)]:
                for k in range(around):
                    a=2*math.pi*k/around
                    # the ring lies in the plane normal to the radial axis: x along the ship, tangential along w
                    pts.append((q['x']+rho*math.cos(a),r*u[0]+rho*math.sin(a)*w[0],r*u[1]+rho*math.sin(a)*w[1]))
        spacing=max(2*math.pi*q['radius']/around,(q['radius']-q['inner'])/7,q['r1']-q['r0'])
        pad=spacing/2
        gaps={}
        oc=next(c for n,c in corr.items() if n!=q['fitting'])
        oa=((oc['x'],oc['r0']*math.cos(oc['theta']),oc['r0']*math.sin(oc['theta'])),(oc['x'],oc['r1']*math.cos(oc['theta']),oc['r1']*math.sin(oc['theta'])))
        gaps['other_corridor']=min(sd(pt,pt,*oa) for pt in pts)-oc['radius']-pad
        for key,f in (('airlock_tube',fittings['Airlock_EVA']),('other_dock',next(v for n,v in fittings.items() if n.startswith('Dock_') and n!=q['fitting']))):
            seg=((f['x'],f['r0']*math.cos(f['theta']),f['r0']*math.sin(f['theta'])),(f['x'],f['r1']*math.cos(f['theta']),f['r1']*math.sin(f['theta'])))
            gaps[key]=min(sd(pt,pt,*seg) for pt in pts)-f['radius']-pad
        gaps['keels_hoops']=min(math.dist(pt,k[:3])-k[3] for pt in pts for k in keels)-pad
        gaps['ties']=min(sd(pt,pt,t['a'],t['b']) -t['radius'] for t in ties for pt in pts)-pad
        gaps['survival_packs']=min(power_storage.point_box(pt,pk) for pt in pts for pk in packs)-pad
        gaps['hull_outer']=min(math.hypot(pt[1],pt[2])-radius_at(s,pt[0]) for pt in pts)-pad
        gaps['own_corridor']=corr[q['fitting']]['radius']-q['radius']
        gaps['over_passage']=q['radius']-q['inner']
        # The flat ring's rim is its farthest point from the ship axis: it must stay inside the BASELINE maximum body diameter like every other fitting (no clearance needed).
        gaps['body_envelope']=s['ship']['body_diameter']['max']/2-math.hypot(q['r1'],q['radius'])
        fail=[f'{k} {v:.3f} m < {0.0 if k=="body_envelope" else clr}' for k,v in gaps.items() if k not in ('over_passage','body_envelope') and v<clr-1e-9 or (k=='body_envelope' and v<0)]
        if q['radius']<=p['dock_clear_radius_m'] or q['radius']<=q['inner']:fail.append('capture ring must exceed the clear passage and the fitting')
        out[q['name']]=dict(gaps_m=gaps,min_gap_m=min(v for k,v in gaps.items() if k not in ('over_passage','body_envelope')),r_m=q['radius'],pass_=not fail,fail='; '.join(fail))
        out[q['name']]['pass']=out[q['name']].pop('pass_')
    return out


def summary(s,d=None):
    return {'spans':[(n,round(a,3),round(b,3)) for n,a,b in intervals(s)],'min_enclosure_margin_m':round(min(m for m,_,_ in margins(s).values()),4),
            'casing_radius_m':round(casing_radius(s),4),
            'capture_rings':{k:{'min_gap_m':round(v['min_gap_m'],3),'pass':v['pass']} for k,v in capture_ring_rows(s).items()},
            'dock_corridors':{k:{'x_m':[round(v['x0'],3),round(v['x1'],3)],'min_ring_gap_m':round(min(v['ring_gaps_m']),3),'blade_front_gap_m':round(v['blade_front_gap_m'],3),'shield_gap_m':round(v['shield_gap_m'],3),'pass':v['pass']} for k,v in corridor_rows(s).items()}}
