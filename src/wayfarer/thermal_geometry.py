"""Pure radiator-blade geometry (FGR-005). The blade is DERIVED from the physical area and the radial extent between the
central-body/root radius and the outer radius (07_PRIMARY_STRUCTURE A52:A55, 15_MODEL_INTERFACES R4). Exclusion cones are
hypotheses, not drive physics."""
import math
import layout

AREA=50000/9


def blade(area, root_r, outer_r):
    """Equivalent rectangle: width = outer - root, length = area / width, aspect ratio = length / width."""
    width=outer_r-root_r
    if not (math.isfinite(width) and width>0 and area>0):
        raise ValueError('Radiator blade needs positive area and an outer radius above the root radius')
    length=area/width
    return dict(width_m=width,length_m=length,aspect_ratio=length/width)


def dimensions(area=AREA, root=6.5, outer=37.0, aft_x=0.0, cant=0, ribbons=1, gap=2.0, mount_fraction=0.0):
    """Blade placement from its aft edge. mount_fraction moves the root-pair centre along the blade from its mid-length."""
    b=blade(area,root,outer);length=b['length_m'];width=b['width_m']
    c=math.cos(math.radians(cant));sn=math.sin(math.radians(cant))
    span=width+(ribbons-1)*gap
    center=aft_x+length*c/2
    mount=center+mount_fraction*length
    radius=root+(mount-center)*math.tan(math.radians(cant))
    return dict(area_m2=area,ratio=b['aspect_ratio'],aspect_ratio=b['aspect_ratio'],ribbons=ribbons,gap_m=gap,blade_length_m=length,
                net_width_m=width,radial_pack_width_m=span,ribbon_width_m=width/ribbons,
                root_radius_m=root,front_x_m=aft_x+length*c+span*sn,center_x_m=center,center_radius_m=radius,
                cant_deg=cant,cos=c,sin=sn,mount_x_m=mount,
                aft_x_m=aft_x,inner_radius_min_m=radius-length*abs(sn)/2,
                outer_radius_m=radius+length*abs(sn)/2+span*c)


def blade_at(s, aft_x):
    """Blade placed with its aft edge at ship X aft_x, from the spec inputs."""
    p=s['prototype'];r=s['radiators']
    return dimensions(r['physical_area']['value'],r['root_radius']['value'],r['outer_radius']['value'],aft_x,
                      p['radiator_axis_cant_deg'],p['radiator_ribbon_count'],p['radiator_ribbon_gap_m'],p['radiator_root_station_blade_fraction'])


def blade_of(s):
    """The one blade geometry shared by spec, hull, recipes, crew transfer and validation."""
    return blade_at(s,layout.origin(s,'RADIATOR_AFT'))


def casing_radius(s):
    """Hull casing radius under the blade span: root radius less the shared member clearance."""
    return s['radiators']['root_radius']['value']-s['prototype']['radiator_member_clearance_m']


def point(d,u,v):
    """Local axial/radial coordinates (origin at the blade mid-length centre) -> ship X and radial distance."""
    return d['center_x_m']+u*d['cos']+v*d['sin'],d['center_radius_m']-u*d['sin']+v*d['cos']


def inner_radius(d,x):
    return d['root_radius_m']+(d['mount_x_m']-x)*math.tan(math.radians(d['cant_deg']))


def stations(s,d):
    """Axial stations the primary cage must carry frames at: the two root booms and the stays at the chosen bays."""
    g=s['radiators']['geometry'];p=s['prototype']
    roots=[d['mount_x_m']+sign*g['root_station_separation_m']/2 for sign in (-1,1)]
    bay=d['blade_length_m']*d['cos']/g['major_bays']
    stays=[d['aft_x_m']+k*bay for k in p['radiator_stay_bays']]
    return dict(roots=roots,stays=stays)


def radial(x,r,a):
    return (x,r*math.cos(a),r*math.sin(a))


def seam_width(s):
    """Width of each non-emitting bay joint (Q13, 07!A42: 0.10-0.15 m; 0.125 m working)."""
    return s['radiators']['bay_joints']['width_working_m']


def emitting_planform(s):
    """Planform of a blade's cells: the gross rectangle less its interior bay joints (AFT-009); the root band is still in it."""
    r=s['radiators'];area=r['physical_area']['value'];width=blade(area,r['root_radius']['value'],r['outer_radius']['value'])['width_m']
    return area-(r['geometry']['major_bays']-1)*seam_width(s)*width


def root_band(s):
    """Hot/cold root transition band (R6, 40_THERMAL A57): the innermost transverse cell row(s) along the root edge. It is radiating
    physical sheet, so it lies inside the equivalent rectangle; width and planform follow from the cell grid, never from a typed size.
    Since AFT-009 the cells stop at the bay joints, so the planforms share the emitting planform, not the gross rectangle."""
    p=s['prototype'];r=s['radiators'];n=p['radiator_transverse_cells'];rows=p['radiator_root_band_cell_rows']
    area=r['physical_area']['value'];net=blade(area,r['root_radius']['value'],r['outer_radius']['value'])['width_m'];cells=emitting_planform(s)
    return dict(rows=rows,width_m=rows*net/n,planform_m2=rows/n*cells,hot_face_planform_m2=(n-rows)/n*cells,
                cells_per_blade=rows*p['radiator_longitudinal_cells'])


def bay_joints(s,d):
    """Interior bay boundaries of one blade (major_bays - 1): blade-local u and ship X. Since AFT-009 each is a seam_width non-emitting gap
    centred on the bay-frame station (the cells stop at its edges), so the stays at bays 2/4/6/8 sit on joints and the blade length is unchanged."""
    bays=s['radiators']['geometry']['major_bays'];length=d['blade_length_m']
    return [dict(index=b,u=-length/2+length*b/bays,x=point(d,-length/2+length*b/bays,0.0)[0]) for b in range(1,bays)]


def cell_span(s,d,j):
    """Blade-local (u0, u1) of longitudinal cell column j: the uniform grid, cut back by half a seam at each interior bay joint."""
    nx=s['prototype']['radiator_longitudinal_cells'];bays=s['radiators']['geometry']['major_bays'];per=nx//bays;L=d['blade_length_m'];h=seam_width(s)/2
    u0=-L/2+L*j/nx;u1=-L/2+L*(j+1)/nx
    return (u0+(h if j%per==0 and j>0 else 0.0),u1-(h if (j+1)%per==0 and j+1<nx else 0.0))


def joint_shoes(s,d):
    """AFT-009 (Q12): guided sliding shoes across every bay joint, two per joint per ribbon at a quarter and three quarters of the width,
    each with the WORKING local travel; blade-local centre (u, v)."""
    w=d['ribbon_width_m'];out=[]
    for ribbon in range(d['ribbons']):
        v0=ribbon*(w+d['gap_m'])
        for jt in bay_joints(s,d):
            out+=[dict(name=f'Blade_Joint_Shoe_{ribbon}_{jt["index"]}_{k}',u=jt['u'],v=v0+w*f,bay_boundary=jt['index']) for k,f in ((1,.25),(2,.75))]
    return out


def datum_lugs(s,d):
    """Q15: the single axial datum carried by several redundant lugs at one station: the datum mount block plus two lugs on the root post,
    radiator_datum_lug_offset_m either side of the sheet; blade-local centres (u, v, z)."""
    m=next(q for q in mounts(s,d) if q['role']=='FIXED_DATUM');z=s['prototype']['radiator_datum_lug_offset_m']
    return [dict(name=f'Blade_Datum_Lug_{k}',u=m['u'],v=s['prototype']['radiator_mount_block_m']/4,z=sz*z) for k,sz in ((1,-1),(2,1))]


def fixed_datum_sign(s):
    return s['prototype']['radiator_fixed_datum_root']


def mounts(s,d):
    """One record per root boom and stay: the aft root is the single FIXED_DATUM, every other mount is an AXIAL_SLIDE that lets the blade
    grow along its length. lever_arm_m is the axial distance to the datum (geometry only; travel = lever arm x strain stays OPEN)."""
    p=s['prototype'];at=stations(s,d);datum=fixed_datum_sign(s)
    xd=at['roots'][0 if datum==-1 else 1]
    rows=[]
    for sign,x in zip((-1,1),at['roots']):
        rows.append(dict(name=f'Blade_Mount_{"Fixed" if sign==datum else "Slide"}_Root_{sign}',station='ROOT',key=sign,
                         role='FIXED_DATUM' if sign==datum else 'AXIAL_SLIDE',x=x,u=(x-d['center_x_m'])/d['cos']))
    for k,x in zip(p['radiator_stay_bays'],at['stays']):
        rows.append(dict(name=f'Blade_Mount_Slide_Stay_{k}',station='STAY',key=k,role='AXIAL_SLIDE',x=x,u=(x-d['center_x_m'])/d['cos']))
    for m in rows:
        m['lever_arm_m']=abs(m['x']-xd)/d['cos']
    return rows


def local_to_ship(d,a,u,v,z):
    """Blade-local (axial u, radial v, tangential z) -> ship frame for a blade at sector angle a."""
    x,r=point(d,u,v)
    return (x,r*math.cos(a)-z*math.sin(a),r*math.sin(a)+z*math.cos(a))


def ship_to_local(d,a,q):
    """Inverse of local_to_ship."""
    r=q[1]*math.cos(a)+q[2]*math.sin(a);z=-q[1]*math.sin(a)+q[2]*math.cos(a)
    dx=q[0]-d['center_x_m'];dr=r-d['center_radius_m']
    return (dx*d['cos']-dr*d['sin'],dx*d['sin']+dr*d['cos'],z)


FRAME_R=.10           # truss member radii shared with revision.radiator
CHORD_R=.14
DIAG_R=.09
POST_R=.22
TRUNK_RADIUS_M=.10     # coolant trunk radius in revision.radiator
FEED_TRUNK_V=.65      # blade-local radial position of the coolant trunk (matches the trunk in revision.radiator)
FEED_TRUNK_Z=.2       # and its tangential offset


LINES={'A':1,'B':-1}     # AFT-009 (Q16): feed A on the +z side of the sheet, return B on the -z side, each in its own chase


def feed_end(s,d,a,line='A'):
    u=(stations(s,d)['roots'][0]-d['center_x_m'])/d['cos']
    return local_to_ship(d,a,u,FEED_TRUNK_V,LINES[line]*FEED_TRUNK_Z)


def coolant_feed_path(s,d,a,line='A'):
    """Coolant line polyline (A feed, B return) for the blade at sector angle a, in its protected chase beside the aft root post (Q16): it
    leaves the hull coolant_feed_loop_span_m aft of the post's mount block, on its own side of the sheet at the loop offset, rises past
    the casing into the root band, runs forward, drops back to the trunk height (a U expansion loop, PROTOTYPE) and joins its trunk at the
    root station. It never passes through the post, the boom, the mount block or the root-bay diagonal. Loop points are the ones from index
    2 on."""
    p=s['prototype'];hull=s['structure']['sector_radius_m'];at=stations(s,d);sz=LINES[line]
    xr=at['roots'][0];u0=(xr-d['center_x_m'])/d['cos']
    lead_v=-(s['radiators']['root_radius']['value']-casing_radius(s))/2     # midway between casing and root edge
    ua=u0-p['radiator_mount_block_m'];uc=ua-p['coolant_feed_loop_span_m']
    top=FEED_TRUNK_V+p['coolant_feed_loop_rise_m'];off=sz*p['coolant_feed_loop_offset_m']
    hull_v=hull-d['center_radius_m']
    pts=[(uc,hull_v,off),(uc,lead_v,off),(uc,top,off),(ua,top,off),(ua,FEED_TRUNK_V,off)]
    return [local_to_ship(d,a,*q) for q in pts]+[feed_end(s,d,a,line)]


def chase_radius(s):
    """Outer radius of a coolant chase (Q16): the line, the chase clearance and the wall."""
    p=s['prototype'];return p['coolant_feed_radius_m']+p['coolant_chase_gap_m']+p['coolant_chase_wall_m']


def legs(m):
    """Straight segments of a support member: consecutive path points, or start-end for a plain member."""
    pts=m.get('path') or [m['start'],m['end']]
    return list(zip(pts,pts[1:]))


def supports(s,d):
    """Hull-side thermal members for each sector: root booms, bay stays, coolant feed. Shared by recipes and hull openings."""
    p=s['prototype'];st=s['structure'];hull=st['sector_radius_m'];members=[]
    at=stations(s,d);datum=fixed_datum_sign(s)
    for j in range(s['radiators']['count']):
        a=math.radians(p['radiator_phase_deg']+j*120)
        for sign,xr in zip((-1,1),at['roots']):
            members.append(dict(name=f'Radiator_Root_{j}_{sign}',kind='root_boom',sector=j,a=a,start=radial(xr,hull,a),end=radial(xr,inner_radius(d,xr),a),radius=p['radiator_boom_radius_m'],
                                mount_role='FIXED_DATUM' if sign==datum else 'AXIAL_SLIDE'))
        # Stays join the hull-side cage to the blade inner edge at the chosen structural bays (07!A31 multi-point stays).
        for k,xk in zip(p['radiator_stay_bays'],at['stays']):
            members.append(dict(name=f'Blade_Stay_{j}_{k}',kind='thermal_support',sector=j,a=a,start=radial(xk,hull,a),end=radial(xk,inner_radius(d,xk),a),radius=p['radiator_stay_radius_m'],mount_role='AXIAL_SLIDE'))
        for line,name in (('A','Coolant_Feed'),('B','Coolant_Return')):
            path=coolant_feed_path(s,d,a,line)
            members.append(dict(name=f'{name}_{j}',kind='coolant_proxy',sector=j,a=a,start=path[0],end=path[-1],path=path,radius=p['coolant_feed_radius_m'],line=line))
    return members


def mount_block_box(u,block):
    """Mount block in blade-local axes: block wide along the blade and tangentially, half as deep radially, sitting on the sheet side of
    the root edge (v 0 .. block/2). Keeping it off the hull side leaves the feed lead-in clear of it."""
    return (u-block/2,0.0,-block/2),(u+block/2,block/2,block/2)


def segment_box_distance(a,b,lo,hi,steps=64):
    """Smallest distance from segment ab to the axis-aligned box lo..hi (sampled; the box is convex, so the sampled minimum is a close upper bound)."""
    best=float('inf')
    for k in range(steps+1):
        q=[a[i]+(b[i]-a[i])*k/steps for i in range(3)]
        best=min(best,math.sqrt(sum(max(lo[i]-q[i],0,q[i]-hi[i])**2 for i in range(3))))
    return best


def segment_distance(a,b,c,e,steps=120):
    """Sampled minimum distance between segments ab and ce."""
    pa=[[a[i]+(b[i]-a[i])*k/steps for i in range(3)] for k in range(steps+1)]
    pc=[[c[i]+(e[i]-c[i])*k/steps for i in range(3)] for k in range(steps+1)]
    return min(math.dist(x,y) for x in pa for y in pc)


def root_truss_members(s,d):
    """Blade-local (name, a, b, radius) of the post at the aft root and the root-edge truss members of the bay holding it."""
    g=s['radiators']['geometry'];half=g['truss_depth_m']/2;length=d['blade_length_m'];bays=g['major_bays']
    u0=(stations(s,d)['roots'][0]-d['center_x_m'])/d['cos'];j=min(bays-1,int((u0+length/2)/(length/bays)))
    x=-length/2+length*j/bays;x2=-length/2+length*(j+1)/bays
    out=[('root_post',(u0,0,-half),(u0,0,half),POST_R),('diagonal',(x,0,-half),(x2,0,half),DIAG_R)]
    out+=[(f'chord_{z}',(x,0,z),(x2,0,z),CHORD_R) for z in (-half,half)]
    out+=[(f'frame_{xx}',(xx,0,-half),(xx,0,half),FRAME_R) for xx in (x,x2)]
    return out


def radial_tube(u,z,v0,v1,r_in,r_out,n=24):
    """Closed ring solid (r_in..r_out) along blade-local v from v0 to v1, centred at (u, z): vertices (u, v, z) and faces."""
    vs=[];fs=[]
    for v in (v0,v1):
        for r in (r_in,r_out):
            vs+=[(u+r*math.cos(math.tau*k/n),v,z+r*math.sin(math.tau*k/n)) for k in range(n)]
    ring=lambda a,b:[(a+k,a+(k+1)%n,b+(k+1)%n,b+k) for k in range(n)]
    fs+=ring(0,n)+ring(3*n,2*n)+ring(n,3*n)+ring(2*n,0)     # bottom, top, outer and inner walls
    return vs,fs


def box_mesh(lo,hi):
    """Axis-aligned box lo..hi: vertices and outward faces."""
    vs=[(x,y,z) for x in (lo[0],hi[0]) for y in (lo[1],hi[1]) for z in (lo[2],hi[2])]
    return vs,[(0,1,3,2),(4,6,7,5),(0,4,5,1),(2,3,7,6),(0,2,6,4),(1,5,7,3)]


def casing_surface_v(s,d,z0,z1):
    """Blade-local v range of the 48-gon casing surface (outer face) between tangential offsets z0..z1 about a sector radial."""
    n=s['hull']['segments'];A=casing_radius(s)*math.cos(math.pi/n);rs=[]
    for k in range(17):
        z=z0+(z1-z0)*k/16
        rs.append(min((A-z*math.sin(t))/math.cos(t) for t in (math.tau*j/n for j in range(-n//4+1,n//4))))
    return min(rs)-d['center_radius_m'],max(rs)-d['center_radius_m']


def chase_plate(s,d,u0,u1,lines,margin):
    """Bent plate on the 48-gon casing over the whole-quad opening of the chases (hull_geometry.shell omits every quad a window overlaps):
    lines are blade-local z of the chase axes; the plate follows the polygon faces from margin before the first omitted quad edge to margin
    past the last, from u0 to u1, flange_thickness_m thick. Vertices (u, v, z) and faces."""
    p=s['prototype'];n=s['hull']['segments'];step=math.tau/n;cas=casing_radius(s);cr=d['center_radius_m']
    ft=s['radiators']['root_construction']['flange_thickness_m'];e0=-step/2
    lo=hi=None
    for z in lines:
        tc=math.atan2(z,math.sqrt(cas*cas-z*z));dt=(p['coolant_feed_radius_m']+p['mechanical_clearance_m'])/cas
        a=e0+math.floor((tc-dt-e0)/step)*step;b=e0+math.ceil((tc+dt-e0)/step)*step
        lo=a if lo is None else min(lo,a);hi=b if hi is None else max(hi,b)
    k=round((hi-lo)/step);ang=[lo+i*step for i in range(k+1)]
    vert=lambda f:(cas*math.cos(f)-cr,cas*math.sin(f))
    f=margin/(2*cas*math.sin(step/2))
    lerp=lambda a,b:(a[0]+(b[0]-a[0])*f,a[1]+(b[1]-a[1])*f)
    prof=[lerp(vert(lo),vert(lo-step))]+[vert(a) for a in ang]+[lerp(vert(hi),vert(hi+step))]
    out=[]
    for v,z in prof:      # outward offset along the sector radial direction of each point (ft is small against the 7.5 deg facets)
        rho=math.hypot(v+cr,z);out.append(((v+cr)*(1+ft/rho)-cr,z*(1+ft/rho)))
    m=len(prof);vs=[(u,v-.005,z) for u in (u0,u1) for v,z in prof]+[(u,v,z) for u in (u0,u1) for v,z in out]
    I=lambda side,uu,i:side*2*m+uu*m+i
    fs=[]
    for i in range(m-1):
        fs+=[(I(0,0,i),I(0,0,i+1),I(0,1,i+1),I(0,1,i)),(I(1,0,i),I(1,1,i),I(1,1,i+1),I(1,0,i+1)),
             (I(0,0,i),I(1,0,i),I(1,0,i+1),I(0,0,i+1)),(I(0,1,i),I(0,1,i+1),I(1,1,i+1),I(1,1,i))]
    fs+=[(I(0,0,0),I(0,1,0),I(1,1,0),I(1,0,0)),(I(0,0,m-1),I(1,0,m-1),I(1,1,m-1),I(0,1,m-1))]
    return vs,fs,max(v for v,_ in out)


def root_construction(s,d):
    """M4 slice 2 (radiators.root_construction, PROTOTYPE): readable root construction off the emitting sheet. Blade-local parts:
    boots: one per support member (booms, stays, coolant chases), a flange on the casing round its opening and a sleeve round the member,
      for the sector-0 blade (every sector is the same in its own frame); saddles: a cradle under each root post on its boom; stops: two
      hard stops at the ends of every slide rail, inner faces at the slot ends. Each part: name, kind, vertices, faces (u, v, z)."""
    p=s['prototype'];c=s['radiators']['root_construction'];out=[]
    gap,wall,fw,ft=c['boot_gap_m'],c['boot_wall_m'],c['flange_width_m'],c['flange_thickness_m']
    at=stations(s,d);roots=at['roots']
    chases=[m for m in supports(s,d) if m['sector']==0 and m['kind']=='coolant_proxy']
    plate_top=None
    if chases:
        q0=[ship_to_local(d,m['a'],m['start']) for m in chases];u=q0[0][0];w=p['coolant_feed_radius_m']+p['mechanical_clearance_m']
        vs,fs,plate_top=chase_plate(s,d,u-w-fw/2,u+w+fw/2,[q[2] for q in q0],fw/2)
        out.append(dict(name='Casing_Boot_Chase_Plate',kind='casing_boot',vertices=vs,faces=fs,member='coolant_proxy'))
    for m in supports(s,d):
        if m['sector']!=0:continue
        q=ship_to_local(d,m['a'],m['start']);u,z=q[0],q[2]
        if m['kind']=='coolant_proxy':
            r_in=chase_radius(s)+gap
        else:
            r_in=m['radius']+gap
        # The flange covers the derived square opening (hull_geometry.openings: member radius + clearance) to its corners.
        r_out=r_in+wall;r_fl=max(r_out+fw,(m['radius']+p['mechanical_clearance_m'])*math.sqrt(2)+fw/4)
        lo,hi=casing_surface_v(s,d,z-r_fl,z+r_fl)
        top=hi+ft
        if m['kind']=='root_boom':sleeve=c['saddle_bottom_v_m']-gap
        elif m['kind']=='thermal_support':sleeve=-.10-c['stay_boot_top_gap_m']      # under the 0.10 m slide rail at the root edge
        else:sleeve=top+c['chase_boot_rise_m']
        tag=m['name'].replace('_0_','_').replace('_0','')
        if m['kind']=='coolant_proxy':     # the sleeve stands on the chase plate (the plate replaces its flange)
            top=plate_top-.01;sleeve=plate_top+c['chase_boot_rise_m']
        else:
            vs,fs=radial_tube(u,z,lo-.005,top,r_in,r_fl);out.append(dict(name=f'Casing_Boot_Flange_{tag}',kind='casing_boot',vertices=vs,faces=fs,member=m['kind']))
        vs,fs=radial_tube(u,z,top,sleeve,r_in,r_out);out.append(dict(name=f'Casing_Boot_Sleeve_{tag}',kind='casing_boot',vertices=vs,faces=fs,member=m['kind']))
    h=c['saddle_half_m']
    for sign,x in zip((-1,1),roots):
        u=(x-d['center_x_m'])/d['cos']
        vs,fs=box_mesh((u-h,c['saddle_bottom_v_m'],-h),(u+h,c['saddle_top_v_m'],h))
        out.append(dict(name=f'Blade_Root_Saddle_{sign}',kind='root_saddle',vertices=vs,faces=fs))
    su,sv,sz=c['stop_m'];half=p['radiator_mount_slot_length_m']/2
    for m in mounts(s,d):
        if m['role']!='AXIAL_SLIDE':continue
        for k,e in ((1,-1),(2,1)):
            u0=m['u']+e*half;u1=u0+e*su
            vs,fs=box_mesh((min(u0,u1),-sv/2,-sz/2),(max(u0,u1),sv/2,sz/2))
            out.append(dict(name=f'{m["name"]}_Stop_{k}',kind='slide_stop',vertices=vs,faces=fs,mount=m['name']))
    return out


def root_construction_screen(s,d):
    """Every part off the emitting sheet and root band (v <= 0 except the stops on the rail, |v| within the rail), boots outside the
    member and its opening radius, stop inner faces exactly at the slot ends (0.20 m travel for the 0.6 m block)."""
    p=s['prototype'];fails=[];parts=root_construction(s,d)
    rail=.10;travel=p['radiator_mount_slot_length_m']-p['radiator_mount_block_m']
    for q in parts:
        vmax=max(v[1] for v in q['vertices'])
        if q['kind']=='slide_stop':
            if vmax>p['radiator_mount_block_m']/2+1e-9:fails.append(q['name']+' above the mount block')
        elif vmax>1e-9:fails.append(q['name']+' enters the sheet side')
    if abs(travel-s['radiators']['thermal_expansion']['distributed_compliance']['local_travel_m'])>1e-9:fails.append('slot less block is not the local travel')
    return dict(parts=len(parts),kinds={k:sum(q['kind']==k for q in parts) for k in ('casing_boot','root_saddle','slide_stop')},rail_radius_m=rail,
                travel_m=travel,fails=fails or 'PASS')


def compliance(s,d):
    """Thermal-compliance screen (AFT-001, AFT-009): one fixed datum per blade, the cells' net of the root band equal to the as-built net
    area (Q52 option D), the feed and return lines in their chases on opposite sides of the sheet, inside the root band and clear of the sheet,
    post, truss and mount hardware (the lead-in too, since it leaves the hull aft of the mount block), and the mounts clear of each other.
    Blade-local coordinates; independent of every configuration. Distances are sampled (segment_distance): screen values, not proofs."""
    p=s['prototype'];clr=p['mechanical_clearance_m'];g=s['radiators']['geometry'];half=g['truss_depth_m']/2
    band=root_band(s);feed_r=p['coolant_feed_radius_m'];block=p['radiator_mount_block_m']
    ms=mounts(s,d);datums=[m for m in ms if m['role']=='FIXED_DATUM']
    off=p['coolant_feed_loop_offset_m'];sheath=chase_radius(s)-feed_r
    lines={k:[ship_to_local(d,0.0,q) for q in coolant_feed_path(s,d,0.0,k)] for k in LINES}
    lower=p['radiator_thickness_m']/2+feed_r+clr;upper=half-CHORD_R-feed_r-clr
    aft=next(m for m in ms if m['role']=='FIXED_DATUM')
    lo,hi=mount_block_box(aft['u'],block)
    members=root_truss_members(s,d)
    def gap(legs):
        return min(segment_distance(a,b,m[1],m[2])-m[3]-feed_r for a,b in legs for m in members)
    block_gap=min(segment_box_distance(a,b,lo,hi) for local in lines.values() for a,b in zip(local,local[1:]))-feed_r
    # Every leg but the last (the joint into the trunk, outside the chase) runs in the chase; the chase must clear the post and truss too.
    later=min(gap(list(zip(local,local[1:]))[2:]) for local in lines.values());lead=min(gap(list(zip(local,local[1:]))[:2]) for local in lines.values())
    chase=min(gap(list(zip(local,local[1:]))[:-1]) for local in lines.values())-sheath
    loops=[q for local in lines.values() for q in local[2:]]
    spacing=min((abs(a['u']-b['u']) for i,a in enumerate(ms) for b in ms[i+1:]),default=float('inf'))
    # Q13/Q52 option D: the cells' net of the 3 m root band is the as-built net area at the working seam.
    width=d['ribbon_width_m']*d['ribbons'];cells=emitting_planform(s)
    net=cells*(width-s['radiators']['root_band']['width_m'])/width
    ab=s['radiators']['as_built_net_area'];want=ab['net_area_m2'][ab['joint_width_m'].index(seam_width(s))]
    # The aggregate free-growth envelope (Q12) if it all accumulated from the datum: a diagnostic bound, not a solved motion (CTE OPEN).
    dc=s['radiators']['thermal_expansion']['distributed_compliance'];L=d['blade_length_m']
    front=(L/2-aft['u'])/L*dc['aggregate_envelope_m'];back=(aft['u']+L/2)/L*dc['aggregate_envelope_m']
    rows=dict(root_band_width_m=band['width_m'],root_band_planform_m2=band['planform_m2'],emitting_planform_m2=cells,
              net_of_root_band_m2=net,as_built_net_area_m2=want,seam_width_m=seam_width(s),
              feed_loop_max_v_m=max(q[1] for q in loops),feed_loop_offset_bounds_m=[lower,upper],feed_legs_to_mount_block_m=block_gap,
              feed_loop_to_post_and_truss_m=later,feed_lead_in_to_post_and_truss_m=lead,chase_to_post_and_truss_m=chase,
              mount_min_spacing_m=spacing,joint_count=len(bay_joints(s,d)),joint_shoes=len(joint_shoes(s,d)),datum_lugs=1+len(datum_lugs(s,d)),
              local_travel_m=dc['local_travel_m'],aggregate_growth_if_accumulated_front_m=front,aggregate_growth_if_accumulated_aft_m=back)
    checks=dict(one_fixed_datum_per_blade=len(datums)==1 and datums[0]['station']=='ROOT',
                cells_net_equals_as_built_net_area=abs(net-want)<1e-6,
                feed_loop_inside_root_band=all(q[1]+feed_r+clr<=band['width_m']+1e-9 for q in loops) and all(min(q[1] for q in local[3:])>=-1e-9 for local in lines.values()),
                feed_loop_clear_of_sheet_and_chords=lower-1e-9<=off<=upper+1e-9 and all(abs(abs(q[2])-off)<1e-9 for local in lines.values() for q in local[:-1]),
                feed_and_return_on_opposite_sides=all(q[2]*LINES[k]>0 for k,local in lines.items() for q in local),
                feed_legs_clear_of_mount_block=block_gap>=clr-1e-9,
                feed_lead_in_clear_of_post_and_truss=lead>=clr-1e-9,
                feed_loop_clear_of_post_and_truss=later>=clr-1e-9,
                chases_clear_of_post_and_truss=chase>=clr-1e-9,
                mounts_clear_of_each_other=spacing>=p['radiator_mount_slot_length_m']+block+clr-1e-9)
    return dict(rows=rows,checks=checks)


def screen(s,d):
    """Shadow, casing, ring and exclusion screen of the blade against the shared inputs. Field clearance stays OPEN."""
    import habitat_ring
    p=s['prototype'];shield=s['forward_shield'];length=s['ship']['length']['value'];clr=p['mechanical_clearance_m']
    margin=p['radiator_member_clearance_m'];shield_r=shield['diameter']['value']/2
    casing=casing_radius(s);root=s['radiators']['root_radius']['value']
    back,front=d['aft_x_m']-.3,d['front_x_m']+.3          # members and the leading spar inflate the blade envelope
    nozzle_x=-length/2
    eye_rear=length/2-p['eye_front_inset_m']-p['eye_module_depth_m']-p['eye_backing_depth_m']
    spar=p['radiator_leading_spar_radius_m']
    rows=dict(
        casing_to_blade_root_m=root-casing,
        casing_radius_m=casing,
        blade_aft_to_nozzle_exit_m=d['aft_x_m']-nozzle_x,
        ring_sweep_to_blade_front_m=[x-habitat_ring.sweep_half(s)-(d['front_x_m']+spar) for x in habitat_ring.centers(s)],
        radiator_shadow_margin_m=shield_r-d['outer_radius_m'],
        ring_shadow_margin_m=shield_r-habitat_ring.outer(s),
        blade_front_to_eye_rear_m=eye_rear-d['front_x_m'])
    # Hypothetical plume cone (aft of the exit plane, half-angle a). Behind the plane the margin is the radial distance outside the cone;
    # geometry ahead of the plane is reached by no cone, so its margin is the axial distance from the plane (a lower bound).
    plume={}
    for angle in [5,10,15,20]:
        minimum=float('inf')
        for k in range(101):
            x=back+(front-back)*k/100
            if x>=nozzle_x:margin_here=x-nozzle_x
            else:margin_here=inner_radius(d,x)-.3-(math.sqrt(2)*p['nozzle_offset_m']+p['nozzle_exit_radius_m']+(nozzle_x-x)*math.tan(math.radians(angle)))
            minimum=min(minimum,margin_here)
        plume[str(angle)]=minimum
    rows['plume_margin_m']=plume
    thermal=compliance(s,d);rows.update(thermal['rows'])
    checks=dict(
        casing_clears_blade_root=rows['casing_to_blade_root_m']>=margin-1e-9,
        casing_holds_body_minimum=casing>=s['ship']['body_diameter']['min']/2-1e-9,
        blade_ahead_of_nozzle_exit=rows['blade_aft_to_nozzle_exit_m']>0,
        ring_sweeps_clear_of_blade=all(g>=clr for g in rows['ring_sweep_to_blade_front_m']),
        radiators_inside_shield_shadow=rows['radiator_shadow_margin_m']>=shield['radiator_shadow_margin']['value']-1e-9,
        rings_inside_shield_shadow=rows['ring_shadow_margin_m']>=shield['ring_shadow_margin']['value']-1e-9,
        blade_clear_of_eye=rows['blade_front_to_eye_rear_m']>0,
        plume_15_clear=plume['15']>margin,
        root_construction_off_sheet=root_construction_screen(s,d)['fails']=='PASS',
        **thermal['checks'])
    return dict(rows=rows,checks=checks,screen_pass=all(checks.values()),
                scope='Blade aft edge ahead of the nozzle exit plane (necessary condition for the OPEN plume/field exclusion), 90 m shield shadow margins, ring sweeps and casing. 5/10/15/20-degree hypothetical plume margins kept for report (radial outside the cone aft of the exit plane, axial from the plane ahead of it). Field clearance OPEN.')
