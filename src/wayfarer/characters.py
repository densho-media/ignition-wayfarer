"""IND-001 character proxies for the induction (CHARACTER layer, PROTOTYPE, standard library only).

Request Doc section 13 and S&E 98!A36: the instructor is a real Y155 professional in an occupation-specific induction / test-flight outfit,
and the newcomer's issued garment reads as uncertified. The Fashion Bible owns clothing (sources.spacer_fashion), the Art Style
Bible the character design order (sources.character_design: silhouette -> posture -> face/gaze -> body -> role -> clothing -> equipment ->
modification -> fine detail), Tale the identities (open: Q49). These proxies stop at silhouette, posture, body, role, clothing and equipment
blocks: no faces, no fine detail. Every garment or kit part names the job it does (pressure seal, fall arrest, emergency breathing, comms,
certification); Spacer clothing is body-close, modular and has no loose fabric (Fashion 08 Spacer); nothing comes from later eras.

A figure is a list of parts in the vehicle frame: 'loft' (rings of centre, side and front axes and the two half-widths, capped), 'ellipsoid'
(centre, three axes with radii), 'capsule' (two end points and radii), 'torus' (centre, axis, major and minor radius), 'box' (centre, three
axes, half sizes). Joints come from stature proportions and a posture
(joint angles, or two-bone IK to a hand or foot target). The generic mannequin stays the ergonomic gauge; these figures only stage scenes.
"""
import math

# Segment proportions of stature H (adult, PROTOTYPE, rounded from common anthropometric tables). Body frame: x right, y forward
# (the face), z up (head); origin at the hip-joint centre.
P = dict(hip_x=.052, waist_z=.10, chest_z=.20, shoulder_z=.285, shoulder_x=.105, neck_z=.31, head_z=.405, upper_arm=.186,
         forearm=.146, hand=.108, thigh=.245, shank=.246, ankle=.039, foot=.152)

# Torso sections (height above the hip-joint centre as a fraction of H; half-width and half-depth in m for a 1.75 m figure of build 1).
TORSO = [(-.035, .145, .100), (.02, .165, .110), (.07, .150, .101), (.10, .140, .098), (.15, .155, .110), (.20, .172, .118),
         (.25, .180, .112), (.285, .168, .092), (.305, .100, .070)]
# Great Union field vest: a straight vertical drop from the chest to the hips, no waist and no loose hem.
VEST = [(.0, .182, .126), (.10, .182, .126), (.20, .190, .130), (.265, .192, .120), (.30, .125, .088)]


def figure(s, who):
    """[characters.instructor] or [characters.newcomer] as a figure dict (studies build their own variants the same way)."""
    q = s['characters'][who]
    return dict(title=q['title'], role=who, stature=q['stature_m'], build=q.get('build', 1.0), suit=q.get('suit', 'suit'), over=q.get('over') or None,
                kit=tuple(q.get('kit', ())))


STAND = dict(trunk=0.0, head=0.0, hip=(0.0, 0.0), abduct=(4.0, 4.0), knee=(0.0, 0.0), ankle=(0.0, 0.0),
             arms=dict(right=dict(flex=0.0, abduct=12.0, elbow=10.0), left=dict(flex=0.0, abduct=12.0, elbow=10.0)))
# Microgravity neutral body posture (hips and knees flexed, arms floating up, head forward), approximate.
# Seated at a console or table: thighs level, shanks down, arms by IK to the desk.
SIT = dict(trunk=0.0, head=-8.0, hip=(88.0, 88.0), abduct=(6.0, 6.0), knee=(86.0, 86.0), ankle=(0.0, 0.0),
           arms=dict(right=dict(flex=30.0, abduct=10.0, elbow=60.0), left=dict(flex=30.0, abduct=10.0, elbow=60.0)))
FLOAT = dict(trunk=-5.0, head=-15.0, hip=(40.0, 40.0), abduct=(8.0, 8.0), knee=(50.0, 50.0), ankle=(-20.0, -20.0),
             arms=dict(right=dict(flex=40.0, abduct=30.0, elbow=75.0), left=dict(flex=40.0, abduct=30.0, elbow=75.0)))


def add(a, b): return tuple(x+y for x, y in zip(a, b))
def sub(a, b): return tuple(x-y for x, y in zip(a, b))
def mul(a, k): return tuple(x*k for x in a)
def dot(a, b): return sum(x*y for x, y in zip(a, b))
def cross(a, b): return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])
def norm(a): return math.sqrt(dot(a, a))
def unit(a): n = norm(a); return mul(a, 1/n)


def rot(v, axis, deg):
    """Rodrigues rotation of v about a unit axis."""
    k = unit(axis); c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return add(add(mul(v, c), mul(cross(k, v), s)), mul(k, dot(k, v)*(1-c)))


def ik(a, target, l1, l2, pole):
    """Two-bone IK: the middle joint for a chain a -> mid -> end reaching target, bending toward pole. Too far: the chain straightens."""
    d = sub(target, a); L = norm(d); e = unit(d); L = min(L, (l1+l2)*.999)
    cos_a = (l1*l1+L*L-l2*l2)/(2*l1*L); sin_a = math.sqrt(max(0.0, 1-cos_a*cos_a))
    p = sub(pole, mul(e, dot(pole, e))); p = unit(p) if norm(p) > 1e-6 else unit(cross(e, (0.0, 0.0, 1.0)))
    mid = add(a, add(mul(e, l1*cos_a), mul(p, l1*sin_a)))
    return mid, add(mid, mul(unit(sub(add(a, mul(e, L)), mid)), l2))


def frame(up, forward):
    """Body axes (x right, y forward, z up) from world up and face directions."""
    z = unit(up); y = unit(sub(forward, mul(z, dot(forward, z)))); x = cross(y, z)
    return x, y, z


def skeleton(fig, pose, root=(0.0, 0.0, 0.0), up=(0.0, 0.0, 1.0), forward=(0.0, 1.0, 0.0), hands=None, feet=None):
    """World joints for a figure. pose: STAND or FLOAT style angles; hands/feet: optional {'right'|'left': (target, pole)} for IK.
    If a feet target is given the figure is first shifted so its soles meet it (mean of the two), then the arms are solved."""
    if feet:
        j0 = skeleton(fig, pose, root, up, forward)
        root = add(root, sub(feet, mul(add(j0['sole_right'], j0['sole_left']), .5)))
    H = fig['stature']; ax = frame(up, forward)
    W = lambda v: add(root, add(add(mul(ax[0], v[0]), mul(ax[1], v[1])), mul(ax[2], v[2])))
    Wd = lambda v: add(add(mul(ax[0], v[0]), mul(ax[1], v[1])), mul(ax[2], v[2]))
    trunk_up = rot((0.0, 0.0, 1.0), (1.0, 0.0, 0.0), -pose['trunk'])        # negative trunk angle leans back
    spine = lambda z: mul(trunk_up, z*H)
    j = dict(hip_c=W((0, 0, 0)), waist=W(spine(P['waist_z'])), chest=W(spine(P['chest_z'])), neck=W(spine(P['neck_z'])))
    head_dir = rot(trunk_up, (1.0, 0.0, 0.0), pose['head'])
    j['head'] = W(add(spine(P['neck_z']), mul(head_dir, (P['head_z']-P['neck_z'])*H)))
    j['head_up'] = Wd(head_dir); j['face'] = Wd(rot(rot((0.0, 1.0, 0.0), (1.0, 0.0, 0.0), -pose['trunk']), (1.0, 0.0, 0.0), pose['head']))
    for k, (side, s) in enumerate((('right', 1.0), ('left', -1.0))):
        sh = add(spine(P['shoulder_z']), (s*P['shoulder_x']*H, 0.0, 0.0)); j[f'shoulder_{side}'] = W(sh)
        if hands and side in hands:
            target, pole = hands[side]
            j[f'elbow_{side}'], j[f'wrist_{side}'] = ik(j[f'shoulder_{side}'], target, P['upper_arm']*H, P['forearm']*H, pole)
        else:
            a = pose['arms'][side]
            d = rot(rot((0.0, 0.0, -1.0), (0.0, 1.0, 0.0), -s*a['abduct']), (1.0, 0.0, 0.0), a['flex'])
            el = add(sh, mul(d, P['upper_arm']*H)); f2 = rot(d, (1.0, 0.0, 0.0), a['elbow'])
            j[f'elbow_{side}'] = W(el); j[f'wrist_{side}'] = W(add(el, mul(f2, P['forearm']*H)))
        hd = unit(sub(j[f'wrist_{side}'], j[f'elbow_{side}'])); j[f'hand_{side}'] = add(j[f'wrist_{side}'], mul(hd, P['hand']*H*.45))
        hip = (s*P['hip_x']*H, 0.0, 0.0); j[f'hip_{side}'] = W(hip)
        th = rot(rot((0.0, 0.0, -1.0), (0.0, 1.0, 0.0), -s*pose['abduct'][k]), (1.0, 0.0, 0.0), pose['hip'][k])
        kn = add(hip, mul(th, P['thigh']*H)); sh_dir = rot(th, (1.0, 0.0, 0.0), -pose['knee'][k])
        an = add(kn, mul(sh_dir, P['shank']*H)); foot_dir = rot(rot(sh_dir, (1.0, 0.0, 0.0), 90.0), (1.0, 0.0, 0.0), pose['ankle'][k])
        j[f'knee_{side}'], j[f'ankle_{side}'] = W(kn), W(an)
        j[f'toe_{side}'] = W(add(an, mul(foot_dir, P['foot']*H*.75))); j[f'heel_{side}'] = W(add(an, mul(foot_dir, -P['foot']*H*.25)))
        j[f'sole_{side}'] = W(add(an, mul(sh_dir, P['ankle']*H)))
    j['axes'] = ax
    return j


def parts(fig, j):
    """Body, garment and kit parts of a posed figure."""
    H, b = fig['stature'], fig['build']; k = H/1.75; ax = j['axes']; out = []
    def ell(name, c, axes, radii, paint, layer='body', job=''):
        out.append(dict(name=name, shape='ellipsoid', centre=c, axes=axes, radii=radii, paint=paint, layer=layer, job=job))
    def cap(name, a, b2, r0, r1, paint, layer='body', job=''):
        out.append(dict(name=name, shape='capsule', a=a, b=b2, r0=r0, r1=r1, paint=paint, layer=layer, job=job))
    def loft(name, rows, paint, layer='body', job=''):
        rings = [(add(j['hip_c'], mul(up_t, z*H)), rt, fw, rx*k*b, ry*k*b) for z, rx, ry in rows]
        out.append(dict(name=name, shape='loft', rings=rings, paint=paint, layer=layer, job=job))
    def tor(name, c, axis, R, r, paint, job):
        out.append(dict(name=name, shape='torus', centre=c, axis=unit(axis), R=R, r=r, paint=paint, layer='kit', job=job))
    def box(name, c, axes, half, paint, job, layer='kit'):
        out.append(dict(name=name, shape='box', centre=c, axes=axes, half=half, paint=paint, layer=layer, job=job))
    up_t = unit(sub(j['neck'], j['hip_c'])); fw = unit(sub(ax[1], mul(up_t, dot(ax[1], up_t)))); rt = cross(fw, up_t)
    T = (rt, fw, up_t); suit = fig['suit']
    # Body under the suit: one lofted torso, neck, head, limbs.
    loft('Torso', TORSO, suit)
    cap('Neck', j['neck'], add(j['neck'], mul(up_t, .07*k)), .052*k, .048*k, 'skin')
    hu = unit(j['head_up']); hf = unit(sub(j['face'], mul(hu, dot(j['face'], hu)))); hr = cross(hf, hu)
    ell('Head', add(j['head'], mul(hf, .01*k)), (hr, hf, hu), (.075*k, .095*k, .115*k), 'skin')
    for side in ('right', 'left'):
        S = side.title()
        cap(f'Upper_Arm_{S}', j[f'shoulder_{side}'], j[f'elbow_{side}'], .054*k*b, .040*k*b, suit)
        cap(f'Forearm_{S}', j[f'elbow_{side}'], j[f'wrist_{side}'], .041*k*b, .029*k, suit)
        cap(f'Hand_{S}', j[f'wrist_{side}'], j[f'hand_{side}'], .032*k, .036*k, 'glove')
        cap(f'Thigh_{S}', j[f'hip_{side}'], j[f'knee_{side}'], .088*k*b, .056*k*b, suit)
        cap(f'Shank_{S}', j[f'knee_{side}'], j[f'ankle_{side}'], .058*k*b, .036*k, suit)
        cap(f'Boot_{S}', j[f'heel_{side}'], j[f'toe_{side}'], .045*k, .040*k, 'boot', 'kit', 'deck boot: magnetic-free grip sole, foot-restraint compatible')
        cap(f'Boot_Cuff_{S}', j[f'ankle_{side}'], add(j[f'ankle_{side}'], mul(unit(sub(j[f'knee_{side}'], j[f'ankle_{side}'])), .10*k)), .046*k, .044*k, 'boot', 'kit',
            'boot cuff: sealed to the suit leg')
    kit = fig['kit']
    if fig['over'] == 'vest':
        # Great Union: vertical, controlled; a fitted field vest with a high collar to the hips, no loose hem (Fashion 03; microgravity).
        loft('Field_Vest', VEST, 'over', 'garment', 'field vest: rank and qualification panel, pockets, no loose hem')
        cap('Vest_Collar', add(j['neck'], mul(up_t, -.01)), add(j['neck'], mul(up_t, .06*k)), .078*k, .074*k, 'over', 'garment', 'high stand collar of the field vest')
        for side, s in (('Right', 1.0), ('Left', -1.0)):
            c = add(j[f'shoulder_{side.lower()}'], add(mul(rt, -s*.02*k), mul(up_t, .045*k)))
            box(f'Shoulder_Board_{side}', c, T, (.06*k, .06*k, .012*k), 'over', 'shoulder board: Great Union rank, squares the shoulder line', 'garment')
    if 'collar' in kit:
        tor('Seal_Collar', add(j['neck'], mul(up_t, .015*k)), up_t, .075*k, .016*k, 'collar', 'neck seal ring: emergency hood or helmet locks here')
    if 'harness' in kit:
        ring = add(add(j['chest'], mul(fw, .118*k*b)), mul(up_t, .02*H))
        tor('Arrest_Ring', ring, fw, .028*k, .008*k, 'metal', 'chest ring: the fall-arrest lanyard clips here (route rails)')
        for side, s in (('Right', 1.0), ('Left', -1.0)):
            top = add(j[f'shoulder_{side.lower()}'], add(mul(up_t, .05*k), mul(fw, .02*k)))
            low = add(j['hip_c'], add(add(mul(rt, s*.12*k*b), mul(fw, .10*k*b)), mul(up_t, .03*H)))
            cap(f'Harness_Strap_{side}', top, add(ring, mul(rt, s*.02)), .012*k, .012*k, 'strap', 'kit', 'harness strap')
            cap(f'Harness_Leg_{side}', add(ring, mul(rt, s*.02)), low, .012*k, .012*k, 'strap', 'kit', 'harness strap')
        cap('Harness_Belt', add(j['hip_c'], add(mul(rt, -.15*k*b), add(mul(fw, .07*k), mul(up_t, .045*H)))),
            add(j['hip_c'], add(mul(rt, .15*k*b), add(mul(fw, .07*k), mul(up_t, .045*H)))), .016*k, .016*k, 'strap', 'kit', 'harness belt')
    if 'mask' in kit:
        c = add(j['hip_c'], add(add(mul(rt, -.17*k*b), mul(fw, .03*k)), mul(up_t, -.02*H)))
        box('Mask_Pouch', c, T, (.03*k, .07*k, .08*k), 'pouch', 'emergency mask and short-duration O2, on the left hip')
    if 'comms' in kit:
        c = add(j['shoulder_left'], add(mul(up_t, .045*k), mul(fw, .03*k)))
        box('Comms_Unit', c, T, (.04*k, .03*k, .025*k), 'device', 'shoulder comms unit: route and crew channel')
    if 'wrist' in kit:
        c = add(mul(add(j['elbow_left'], j['wrist_left']), .5), mul(unit(sub(j['wrist_left'], j['elbow_left'])), .04*k))
        da = unit(sub(j['wrist_left'], j['elbow_left'])); n2 = unit(cross(da, rt if abs(dot(da, rt)) < .9 else fw)); n3 = cross(da, n2)
        box('Wrist_Display', add(c, mul(n3, .035*k)), (n2, da, n3), (.03*k, .05*k, .008*k), 'device', 'wrist interface: suit and route status')
    if 'marks' in kit:
        c = add(j['chest'], add(add(mul(rt, -.09*k*b), mul(fw, (.13 if fig['over'] else .118)*k*b)), mul(up_t, .045*H)))
        box('Cert_Panel', c, T, (.045*k, .006, .03*k), 'mark', 'qualification panel: certification and vessel affiliation (Great Union marks)')
        for side, s in (('Right', 1.0), ('Left', -1.0)):
            c = add(j[f'shoulder_{side.lower()}'], add(mul(rt, s*.05*k), mul(up_t, -.02*k)))
            box(f'Rank_Band_{side}', c, T, (.012*k, .05*k, .03*k), 'mark', 'shoulder band: instructor qualification')
    if 'seams' in kit:
        for side in ('right', 'left'):
            for joint, nxt, r in (('elbow', 'wrist', .040), ('knee', 'ankle', .055)):
                d = unit(sub(j[f'{nxt}_{side}'], j[f'{joint}_{side}']))
                tor(f'Seam_{joint.title()}_{side.title()}', add(j[f'{joint}_{side}'], mul(d, .06*k)), d, r*k*b, .006*k, 'seam', 'module joint: replaceable limb section')
    if 'pockets' in kit:
        for side, s in (('Right', 1.0), ('Left', -1.0)):
            c = add(mul(add(j[f'hip_{side.lower()}'], j[f'knee_{side.lower()}']), .5), mul(rt, s*.08*k*b))
            box(f'Thigh_Pocket_{side}', c, T, (.025*k, .06*k, .08*k), 'pouch', 'thigh pocket: checklist and tools, closed flaps')
    if 'helmet' in kit:
        c = add(j['hip_c'], add(mul(rt, .22*k*b), add(mul(fw, -.02*k), mul(up_t, -.03*H))))
        ell('Helmet_Stowed', c, T, (.13*k, .14*k, .15*k), 'helmet', 'kit', 'pressure helmet, stowed on the hip clip: burn and emergency readiness')
    if 'visitor' in kit:
        d = unit(sub(j['elbow_left'], j['shoulder_left']))
        tor('Visitor_Band', add(j['shoulder_left'], mul(d, .10*k)), d, .052*k, .013*k, 'visitor', 'visitor band: uncertified, under escort')
    if 'pack' in kit:
        c = add(j['chest'], add(mul(fw, -.17*k*b), mul(up_t, -.02*H)))
        box('Kit_Pack', c, T, (.13*k, .06*k, .17*k), 'pack', 'personal kit pack, strapped close (no loose bag in microgravity)')
    return out



# IND-001 4.2: the wider view of a stop whose own aisle camera stands too close to its station to show it: the sector function, a sector-frame
# eye and target (up is -Y, the deck's up), the lens (mm) and a caption. Display only (entry_preview ind_<stop>, the runtime stop views).
STAGE_VIEWS = {
    'burn_readiness': ('WORK_MEDICAL_OPS', (1.52, -1.70, -.40), (-.30, -1.15, 1.20), 13.0,
                       'from the fore end of the aisle: the newcomer on the treatment couch'),
    'specialists': ('WORK_MEDICAL_OPS', (-1.30, -1.62, -.10), (1.60, -1.15, .55), 14.0,
                    'from the aft end of the aisle: the operations stations, Seraph\'s post and the workbench'),
    'garden': ('LIFE_SUPPORT_GARDEN_COMMON', (.95, -1.60, .40), (.70, -1.25, -1.10), 16.0,
               'from the aisle beside the landing well: the life-support bay'),
}


def stop_views(s):
    """IND-001 4.2/5.1: each induction stop's eye-level view ([induction].stops `view`) in the vehicle frame at the docked pose, as a guide
    camera dict (name, at, look direction, up, lens in mm on a 36 mm sensor width, role)."""
    import crew_transfer
    import human_entry as he
    f = he.ports(s)[0]; g = greeting(s, f)
    _, ij = staged(g['instructor'], figure(s, 'instructor')); _, nj = staged(g['newcomer'], figure(s, 'newcomer'))
    cams = {c['name']: c for c in he.cameras(s, f)+cameras(s, f, ij, nj)}; rot, _, la = he.vestibule_station(s, s['induction']['ring']); out = {}
    for q in s['induction']['stops']:
        if q['view'] != 'stage':
            out[q['key']] = dict(cams[q['view']]); continue
        fn, eye, target, lens, role = STAGE_VIEWS[q['key']]; k = s['habitat_ring']['sector_functions'].index(fn)+1
        pt = lambda v: he.at_index(rot, crew_transfer.sector_point(s, la[k], v)); e = pt(eye)
        out[q['key']] = dict(name=f"STAGE_{q['key'].upper()}", at=e, look=sub(pt(target), e), up=sub(pt((0, -1, 0)), pt((0, 0, 0))), lens=lens, role=role)
    return out


def couch(s, back=0.11):
    """IND-001 3.3 staging (PROTOTYPE): the newcomer lying on the treatment couch at the S004B burn-readiness stop, in the shared sector
    frame (deck at y 0, +Y down), as skeleton() arguments with the sector function and the scene. `back` is the depth from the body's joint
    plane to its back surface, which rests on the mattress (MATTRESS_M on the table top): 0.11 m for the IND-001 proxy, measured per body for an MPFB human (CHAR-001)."""
    import habitat_interior
    from sector_whitebox import MATTRESS_M
    w = s['sector_whitebox']; up = (0.0, -1.0, 0.0)
    med = {b['name']: b for b in habitat_interior.zones(s, 'WORK_MEDICAL_OPS')}['Medical_Couch']
    zc = (med['min'][2]+med['max'][2])/2; top = -w['medical_table_m']-MATTRESS_M; feet_x = med['min'][0]+.04
    return dict(function='WORK_MEDICAL_OPS', scene='S004B', pose=STAND, root=(feet_x+.9, top-back, zc), up=(1.0, 0.0, 0.0), forward=up,
                feet=(feet_x, top-back, zc), hands=None)


def greeting(s, f, newcomer_offset=(0.0, 0.0, 0.0), hand_offset=None):
    """Study staging of S004A in the entry chamber: the instructor anchored upright on the deck band (head fore), offering a hand; the
    newcomer coming head-first through the open outer hatch, one hand in the instructor's, the other pulling on the hatch rim (the wall rails
    are out of reach from the passage axis). newcomer_offset (along the port axis, along X, across) moves the newcomer's body for a body
    whose reach differs from the proxy's (CHAR-001 re-staging); hand_offset (along the port axis) moves the hands' meeting point, the
    instructor reaching further toward the hatch ([characters.greeting] hand_offset_m when None)."""
    import human_entry as he
    st = he.stations(s, f); u, w = he.axes(f)
    pt = lambda a, p, q: (f['x']+p, a*u[1]+q*w[1], a*u[2]+q*w[2])
    # The hands meet where the MPFB instructor's right hand reaches from the deck band (0.09 m inboard of the proxy's reach).
    hand = pt(5.49+(s['characters'].get('greeting', {}).get('hand_offset_m', 0.0) if hand_offset is None else hand_offset), .10, .05)
    # Facing u with head fore, the instructor's left is +w: the free left hand rests forward of his left hip, elbow down.
    inst = dict(fig=None, pose=FLOAT, up=(1.0, 0.0, 0.0), forward=u, root=pt(5.30, -.30, -.05), feet=pt(5.30, -st['chamber_r']+.08, -.05),
                hands=dict(right=(hand, (0.0, -1.0, 0.0)), left=(pt(5.42, -.15, .23), (-1.0, 0.0, 0.0))))
    rim = (st['clear']+st['r_hinge'])/2
    da, dp, dq = newcomer_offset
    # Head along -u and facing fore, the newcomer's left is +w: the right hand takes the instructor's right, the left the near (+w)
    # rim, elbow inboard so the forearm meets the rim from the chamber side, not across the frame.
    newc = dict(fig=None, pose=FLOAT, up=tuple(-x for x in u), forward=(1.0, 0.0, 0.0), root=pt(6.48+da, .05+dp, .28+dq), feet=None,
                hands=dict(right=(add(hand, mul(u, .05)), (1.0, 0.0, 0.0)), left=(pt(st['outer_frame'][0]-.03, 0.0, rim), tuple(-x for x in u))))
    newc['pose'] = dict(FLOAT, head=35.0, hip=(10.0, 20.0), knee=(25.0, 35.0))
    return dict(instructor=inst, newcomer=newc)


def staged(spec, fig):
    """Parts of a figure posed by a greeting() entry."""
    j = skeleton(fig, spec['pose'], spec['root'], spec['up'], spec['forward'], spec['hands'], spec['feet'])
    return parts(fig, j), j


# The newcomer's own head, torso and upper arms are hidden in the point-of-view still (first person); forearms and hands stay.
OWN_VIEW = ('Forearm', 'Hand', 'Wrist')


def cameras(s, f, ij, nj):
    """Greeting cameras (non-canon guides, fore up): a profile view across the chamber from the -w side, and the newcomer's point of view
    looking at the instructor's face."""
    import human_entry as he
    u, w = he.axes(f); pt = lambda a, p, q: (f['x']+p, a*u[1]+q*w[1], a*u[2]+q*w[2])
    eye = add(add(nj['head'], mul(unit(nj['face']), .09)), mul(unit(nj['head_up']), .02))
    return [dict(name='CAM_IND_GREETING', at=pt(5.35, .30, -1.02), look=sub(pt(5.62, -.10, .40), pt(5.35, .30, -1.02)), up=(1.0, 0.0, 0.0),
                 lens=18.0, role='profile across the entry chamber: the instructor anchored on the deck band greets the newcomer at the outer hatch'),
            dict(name='CAM_IND_GREETING_POV', at=eye, look=sub(add(ij['head'], (-.1, 0.0, 0.0)), eye), up=(1.0, 0.0, 0.0), lens=18.0,
                 role="the newcomer's point of view coming through the outer hatch (camera up = fore, for readability)")]
