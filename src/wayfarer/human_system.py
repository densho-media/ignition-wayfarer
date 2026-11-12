"""Wayfarer human character system (C1-C3, docs/CHARACTERS.md): the shared contract, MPFB recipes, the shared action library and the
retarget source format. Standard library only; the Blender side is build/human.py.

Ownership: Tale owns identity, Art Style depiction, Fashion clothing. Recipes in data/characters.toml are PROTOTYPE bodies; the
contract (rig, axes, units, fps) is a local technical decision.

Retarget source format. A motion source is a list of frames; each frame is a dict of world joint positions with the keys of
characters.skeleton() (hip_c, waist, chest, neck, head, shoulder_*, elbow_*, wrist_*, hand_*, hip_*, knee_*, ankle_*, toe_*), plus
`head_up` and `face` (directions), `root` (the ground point the Root bone carries) and `contacts` (limbs held still in the world:
'foot_right', 'foot_left', 'hand_right', 'hand_left', 'knee_right', 'knee_left'). A source also carries its rest frame (the same keys
in its rest pose). The procedural library below writes this format from characters.py postures at a given stature; build/human.py
reads it from any armature (an MPFB rig, later an external library) through a bone map, so one solver serves every source:
long bones by two-bone IK to the source's wrists and ankles (poles from the elbows and knees), pelvis, chest and head by the change
of their source frames from rest, feet by the ankle flexion change, everything else held at rest.
"""
import math
from pathlib import Path
import tomllib

import characters as ch

ROOT = Path(__file__).resolve().parents[2]
SIDES = ('right', 'left')
SUFFIX = dict(right='r', left='l')

# The game_engine skeleton (MPFB 2.0.17 data/rigs/standard/rig.game_engine.json): the runtime contract. A build fails if the
# generated rig differs.
BONES = ('Root', 'pelvis', 'spine_01', 'spine_02', 'spine_03', 'neck_01', 'head',
         *(f'{b}_{s}' for s in 'lr' for b in ('clavicle', 'upperarm', 'lowerarm', 'hand', 'thigh', 'calf', 'foot', 'ball')),
         *(f'{f}_{k:02d}_{s}' for s in 'lr' for f in ('thumb', 'index', 'middle', 'ring', 'pinky') for k in (1, 2, 3)))

# Reading a game_engine rig as a motion source: joint key -> (bone, 'head' | 'tail').
RIG_JOINTS = dict(hip_c='pelvis.head', waist='spine_02.head', chest='spine_03.head', neck='neck_01.head', head='head.head',
                  **{f'{j}_{side}': f'{b}_{SUFFIX[side]}.{e}' for side in SIDES for j, b, e in (
                      ('shoulder', 'upperarm', 'head'), ('elbow', 'lowerarm', 'head'), ('wrist', 'hand', 'head'), ('hand', 'hand', 'tail'),
                      ('hip', 'thigh', 'head'), ('knee', 'calf', 'head'), ('ankle', 'foot', 'head'), ('toe', 'ball', 'head'))})


def add(a, b): return tuple(x+y for x, y in zip(a, b))
def sub(a, b): return tuple(x-y for x, y in zip(a, b))
def mul(a, k): return tuple(x*k for x in a)
def lerp(a, b, t): return add(a, mul(sub(b, a), t))
def smooth(t): t = min(1.0, max(0.0, t)); return t*t*(3-2*t)


def load(root=ROOT):
    """data/characters.toml, checked against the manifest's MPFB pin and the recipe rules."""
    data = tomllib.loads((root / 'data/characters.toml').read_text())
    manifest = tomllib.loads((root / 'assets/external/manifest.toml').read_text())
    sys_ = data['human_system']; mpfb = next(d for d in manifest['dependency'] if d['name'] == 'mpfb')
    assert sys_['mpfb'] == mpfb['version'], f"characters.toml expects MPFB {sys_['mpfb']}, the manifest pins {mpfb['version']}"
    proxies = tomllib.loads((root / 'data/wayfarer_3d.toml').read_text())['characters']
    for key, q in data['human'].items():
        assert q['kind'] in ('fixture', 'induction'), key
        assert 1.40 <= q['stature_m'] <= 2.10, f'{key}: stature outside the adult range the bisection supports'
        assert all(0.0 <= v <= 1.0 for v in q['phenotype'].values()), f'{key}: MPFB macros are 0..1'
        assert math.isclose(sum(q['race'].values()), 1.0, abs_tol=1e-6), f'{key}: race weights must sum to 1'
        if q['kind'] == 'induction':
            assert q.get('identity_ref'), f'{key}: an induction recipe cites its Tale rows'
            assert math.isclose(q['stature_m'], proxies[q['proxy']]['stature_m']), f"{key}: stature differs from its proxy [characters.{q['proxy']}]"
    return data


def human_info(sys_, q, height):
    """MPFB 2.0.17 human_info dict (HumanService.deserialize_from_dict) for a recipe at MPFB height macro `height`."""
    skin = q['skin']
    return dict(name=q.get('id', 'HUMAN'), phenotype=dict(q['phenotype'], height=height, race=dict(q['race'])), rig=sys_['rig'],
                eyes=q['eyes'], eyebrows=q['eyebrows'], eyelashes=q['eyelashes'], tongue='', teeth='', hair='', proxy='', targets=[],
                clothes=[], skin_mhmat='' if skin == 'clay' else skin, skin_material_type='NONE' if skin == 'clay' else 'GAMEENGINE',
                eyes_material_type='GAMEENGINE', skin_material_settings={}, eyes_material_settings={}, expressions=[])


# ----------------------------------------------------------------------------------------------------------------------------------
# Procedural action library (PROTOTYPE motion). Every action is a function of the figure (stature) and the shared values, returning
# frames in the source format, character facing -Y (MPFB's front) with the Root at the origin at frame 0.

FORWARD = (0.0, -1.0, 0.0)
UP = (0.0, 0.0, 1.0)


def figure(stature):
    return dict(title='source', role='source', stature=stature, build=1.0, suit='suit', over=None, kit=())


def leg_lengths(H):
    return ch.P['thigh']*H, ch.P['shank']*H, ch.P['ankle']*H, ch.P['foot']*H


def legs_to(j, H, ankles, forward, up, toes=None):
    """Replace the legs of a skeleton() pose with two-bone IK to ankle targets (knees bend toward `forward`), feet toward toes."""
    l1, l2, _, lf = leg_lengths(H)
    for side in SIDES:
        if side not in ankles:
            continue
        knee, ankle = ch.ik(j[f'hip_{side}'], ankles[side], l1, l2, forward)
        j[f'knee_{side}'], j[f'ankle_{side}'] = knee, ankle
        fd = ch.unit(sub(toes[side], ankle)) if toes and side in toes else forward
        j[f'toe_{side}'] = add(ankle, mul(fd, lf*.75)); j[f'heel_{side}'] = add(ankle, mul(fd, -lf*.25))
        j[f'sole_{side}'] = sub(ankle, mul(up, ch.P['ankle']*H))
    return j


def frame_of(j, root, contacts):
    out = {k: v for k, v in j.items() if k != 'axes'}
    out['root'] = root; out['contacts'] = tuple(contacts)
    return out


def rest(H):
    """The procedural source's rest frame: standing, arms at the sides (STAND)."""
    return frame_of(ch.skeleton(figure(H), ch.STAND, (0.0, 0.0, (sum(leg_lengths(H)[:3]))), UP, FORWARD), (0.0, 0.0, 0.0), ())


def idle(H, a, fps):
    """4 s standing loop: breathing (trunk +-1 deg), a 1 cm weight shift; both feet planted."""
    n = 4*fps; leg = sum(leg_lengths(H)[:3])*.995; out = []
    right = ch.frame(UP, FORWARD)[0]
    for i in range(n):
        t = i/n; sway = .010*math.sin(2*math.pi*t)
        pose = dict(ch.STAND, trunk=1.0*math.sin(4*math.pi*t), head=-2.0)
        j = ch.skeleton(figure(H), pose, add((0.0, 0.0, leg), mul(right, sway)), UP, FORWARD)
        ank = {s: (sg*ch.P['hip_x']*H*1.25*right[0], 0.0, ch.P['ankle']*H) for s, sg in zip(SIDES, (1, -1))}
        out.append(frame_of(legs_to(j, H, ank, FORWARD, UP), (0.0, 0.0, 0.0), ('foot_right', 'foot_left')))
    return dict(frames=out, loop=True, root_motion=False)


# LOCO-003 gait (docs/LOCOMOTION.md "Movement design"): the walk and the run carry Saunders, Inman and Eberhart's determinants of gait
# (1953) that the first clips lacked, which is what made them read as a robot: pelvic rotation about the vertical, pelvic list (the swing
# side's hip drops), lateral shift of the pelvis over the stance foot, the heel strike / flat foot / heel rise roll of the foot, the
# thorax turning against the pelvis, and arms swinging in phase with the opposite leg. Angles are PROTOTYPE display values in the range
# of normal adult gait (Perry & Burnfield, Gait Analysis, 2010), not mocap.
GAIT = dict(
    walk=dict(pelvis_yaw=4.0, pelvis_list=4.0, sway_m=.020, thorax=4.5, heel_up=10.0, toe_off=22.0, strike=.08, heel_off=.42,
              arm=(6.0, 16.0), elbow=(14.0, .7), trunk=3.0, head=-3.0),
    run=dict(pelvis_yaw=6.0, pelvis_list=5.0, sway_m=.010, thorax=8.0, heel_up=8.0, toe_off=28.0, strike=.05, heel_off=.20,
             arm=(-4.0, 26.0), elbow=(72.0, .25), trunk=9.0, head=-6.0),
)


def _pivot_foot(plant, pitch, forward, up, lf, la, about):
    """Ankle and toe direction of a foot planted with its flat-foot ankle at `plant`, pitched `pitch` deg (toes up +) about its floor
    heel ('heel') or ball ('ball') point, so the pivot stays on the floor while the ankle lifts."""
    c, sn = math.cos(math.radians(pitch)), math.sin(math.radians(pitch))
    f2 = add(mul(forward, c), mul(up, sn)); u2 = add(mul(forward, -sn), mul(up, c))
    lh, lb = lf*.25, lf*.75
    if about == 'heel':
        piv = sub(sub(plant, mul(forward, lh)), mul(up, la)); ank = add(piv, add(mul(f2, lh), mul(u2, la)))
    else:
        piv = sub(add(plant, mul(forward, lb)), mul(up, la)); ank = add(piv, add(mul(f2, -lb), mul(u2, la)))
    return ank, f2


def _foot(ph, st, g, plant_prev, plant_next, plant, lift_h, forward, up, lf, la, lift_pow=1.0):
    """(ankle, toe direction, held) of one foot at its cycle phase: heel strike (rolling down about the heel), flat (held: the only frames
    the source holds it still), heel rise (rolling up about the ball) and a swing from the toe-off pose to the next heel strike."""
    if ph < g['strike']:
        a, f = _pivot_foot(plant, g['heel_up']*(1-smooth(ph/g['strike'])), forward, up, lf, la, 'heel'); return a, f, False
    if ph < g['heel_off']:
        return plant, forward, True
    if ph < st:
        a, f = _pivot_foot(plant, -g['toe_off']*smooth((ph-g['heel_off'])/(st-g['heel_off'])), forward, up, lf, la, 'ball'); return a, f, False
    s = (ph-st)/(1-st)
    a0, _ = _pivot_foot(plant_prev, -g['toe_off'], forward, up, lf, la, 'ball')
    a1, _ = _pivot_foot(plant_next, g['heel_up'], forward, up, lf, la, 'heel')
    pitch = -g['toe_off']*(1-smooth(s/.5)) if s < .5 else g['heel_up']*smooth((s-.5)/.5)
    c, sn = math.cos(math.radians(pitch)), math.sin(math.radians(pitch))
    return add(lerp(a0, a1, smooth(s)), mul(up, lift_h*math.sin(math.pi*s)**lift_pow)), add(mul(forward, c), mul(up, sn)), False


def _body(j, yaw, lst, sway, thorax, up, forward, right):
    """Pelvis rotation (yaw about up, + turns the right hip forward), list (+ drops the left hip) and the lateral shift of the whole body
    (+ toward the right); the shoulders and arms turn against the pelvis by `thorax` deg about the spine. The head keeps facing ahead."""
    hc = j['hip_c']; sh = mul(right, sway); skip = ('head_up', 'face')
    for k in list(j):
        if k not in skip and isinstance(j[k], tuple) and len(j[k]) == 3 and all(isinstance(x, float) for x in j[k]):
            j[k] = add(j[k], sh)
    hc = j['hip_c']
    for side in SIDES:
        v = sub(j[f'hip_{side}'], hc)
        v = ch.rot(v, up, yaw); v = ch.rot(v, forward, -lst)
        j[f'hip_{side}'] = add(hc, v)
    piv = j['chest']
    for side in SIDES:
        for part in ('shoulder', 'elbow', 'wrist', 'hand'):
            k = f'{part}_{side}'
            j[k] = add(piv, ch.rot(sub(j[k], piv), up, thorax))
    return j


def _gait(H, a, fps, v, T, st, lift_h, g, height_cap, lift_pow=1.0, mid=None):
    """One gait cycle (two steps) at speed v and cycle time T, stance fraction st: the right foot strikes at t = 0, the left at T/2. The
    flat foot passes under the hip at phase `mid` (default st / 2); a walk's 0.25 puts the leading heel and the trailing toe equally far
    from the hip in double support, so the pelvis dips about 4 cm there instead of 9."""
    mid = st/2 if mid is None else mid
    n = round(T*fps); stride = v*T
    l1, l2, la, lf = leg_lengths(H); reach = .985*(l1+l2); right = ch.frame(UP, FORWARD)[0]; out = []
    hw = ch.P['hip_x']*H*(1.0 if st >= .5 else .8)
    for i in range(n):
        t = i*T/n; y = v*t; contacts = []; ank = {}; toes = {}; stance = []
        for side, off, sg in (('right', 0.0, 1), ('left', .5, -1)):
            ph = (t/T+off) % 1.0; cyc = math.floor(t/T+off)
            P = lambda c: add(mul(right, sg*hw), (0.0, -v*(c+mid-off)*T, la))     # the flat-foot ankle of the step in cycle c
            A, fd, held = _foot(ph, st, g, P(cyc), P(cyc+1), P(cyc), lift_h, FORWARD, UP, lf, la, lift_pow)
            ank[side] = A; toes[side] = add(A, fd)
            if held:
                contacts.append(f'foot_{side}')
            if ph < st:
                stance.append(A)
        # the pelvis rides as high as the stance legs allow (it dips in double support), capped by `height_cap`
        h = min([height_cap(t)]+[A[2]-la+math.sqrt(max(0.0, reach**2-(y+A[1])**2)) for A in stance])+la
        w = 2*math.pi*t/T
        yaw = g['pelvis_yaw']*math.cos(w)                     # right hip forward at the right strike
        lst = g['pelvis_list']*math.sin(w-2*math.pi*.05) * (1.0 if st >= .5 else .7)    # the swing side drops in single support
        sway = g['sway_m']*math.sin(w-2*math.pi*.05)
        arm0, arm1 = g['arm']; e0, ek = g['elbow']
        flex_r = arm0-arm1*math.cos(w); flex_l = arm0+arm1*math.cos(w)                 # each arm with the opposite leg
        arms = {sd: dict(flex=f, abduct=8.0 if st >= .5 else 10.0, elbow=e0+ek*max(0.0, f)) for sd, f in (('right', flex_r), ('left', flex_l))}
        pose = dict(ch.STAND, trunk=g['trunk'], head=g['head'], arms=arms)
        j = ch.skeleton(figure(H), pose, (0.0, -y, h), UP, FORWARD)
        j = _body(j, yaw, lst, sway, -g['thorax']*math.cos(w), UP, FORWARD, right)
        out.append(frame_of(legs_to(j, H, ank, FORWARD, UP, toes), (0.0, -y, 0.0), contacts))
    return out


def walk(H, a, fps):
    """One gait cycle (two steps) at walk_speed_m_s and walk_cadence_steps_min: 60 % stance with heel strike, flat foot and heel rise,
    swing arcs of step_height_m, the pelvis riding over the stance leg, the gait determinants of GAIT['walk']. Root motion along -Y."""
    v = a['walk_speed_m_s']; T = 120.0/a['walk_cadence_steps_min']
    l1, l2, _, _ = leg_lengths(H); reach = .985*(l1+l2)
    out = _gait(H, a, fps, v, T, .6, a['step_height_m'], GAIT['walk'], lambda t: reach*.97, mid=.25)
    return dict(frames=out, loop=True, root_motion=True, speed_m_s=v)


def sit(H, a, fps, seat):
    """Stand to seated on a seat of height `seat` behind the figure (1.5 s), held 1 s; feet planted, trunk leans forward mid-way."""
    n1, n2 = round(1.5*fps), fps; l1, l2, la, _ = leg_lengths(H); stand = l1+l2+la-.005
    end = (0.0, l1*.92, seat+.10); start = (0.0, 0.0, stand); right = ch.frame(UP, FORWARD)[0]; out = []
    ank = {s: add(mul(right, sg*ch.P['hip_x']*H*1.25), (0.0, -.04, la)) for s, sg in zip(SIDES, (1, -1))}
    for i in range(n1+n2):
        t = smooth(min(1.0, i/(n1-1))); hip = lerp(start, end, t)
        pose = dict(ch.SIT if t > .5 else ch.STAND, trunk=-32.0*math.sin(math.pi*t), head=-6.0*t,
                    arms=dict(right=dict(flex=25.0*t, abduct=10.0, elbow=10.0+50.0*t), left=dict(flex=25.0*t, abduct=10.0, elbow=10.0+50.0*t)))
        j = ch.skeleton(figure(H), pose, hip, UP, FORWARD)
        out.append(frame_of(legs_to(j, H, ank, FORWARD, UP), (0.0, 0.0, 0.0), ('foot_right', 'foot_left')))
    return dict(frames=out, loop=False, root_motion=False, seat_height_m=seat)


def crawl(H, a, fps):
    """Hands-and-knees crawl (the drum chambers' crawl rail, ring B's crawl): diagonal gait, period 1.6 s, crawl_speed_m_s along -Y.
    One knee is planted at a time (half its cycle; two rigid thighs cannot both stay planted under a level pelvis) and the pelvis
    rides on it; each hand is planted 70 % of its cycle. Body head-first along -Y, face down."""
    v = a['crawl_speed_m_s']; T = 1.6; n = round(T*fps); stride = v*T
    l1, l2, la, lf = leg_lengths(H); arm = (ch.P['upper_arm']+ch.P['forearm'])*H*.93; trunk = ch.P['shoulder_z']*H; kz = .05; out = []
    def plant(t, off, lead, stance):
        """World Y of a limb's floor point, its lift and whether it is held: held for `stance` of the cycle, then carried one stride."""
        ph = (t/T+off) % 1.0; cyc = math.floor(t/T+off); y = -(v*(cyc+stance/2-off)*T+lead)
        if ph < stance:
            return y, 0.0, True
        s = smooth((ph-stance)/(1-stance)); return y-stride*s, .05*math.sin(math.pi*s), False
    for i in range(n):
        t = i*T/n; y = v*t; contacts = []; kn = {}
        for side, off in (('right', 0.0), ('left', .5)):
            kn[side] = plant(t, off, 0.0, .5)
        held = next(s for s in SIDES if kn[s][2]); dy = abs(-y-kn[held][0])
        hip_h = kz+math.sqrt(max(0.0, l1**2-dy**2)); rise = math.asin(max(-.9, min(.9, (arm+.03-hip_h)/trunk)))
        body_up = (0.0, -math.cos(rise), math.sin(rise)); face = (0.0, 0.0, -1.0); hip = (0.0, -y, hip_h)
        j0 = ch.skeleton(figure(H), dict(ch.STAND, head=35.0), hip, body_up, face); hd = {}
        for side, off in (('right', 0.0), ('left', .5)):
            hy, lift, h = plant(t, off+.5, trunk*math.cos(rise), .7)
            hd[side] = ((j0[f'shoulder_{side}'][0], hy, .03+lift), (0.0, 1.0, 0.0))
            if h:
                contacts.append(f'hand_{side}')
        j = ch.skeleton(figure(H), dict(ch.STAND, head=35.0), hip, body_up, face, hands=hd)
        for side in SIDES:
            ky, lift, h = kn[side]; hp = j[f'hip_{side}']
            knee = (hp[0], ky, kz) if h else add(hp, mul(ch.unit(sub((hp[0], ky, kz+lift), hp)), l1))
            j[f'knee_{side}'] = knee; j[f'ankle_{side}'] = add(knee, mul(ch.unit((0.0, 1.0, .10)), l2))
            j[f'toe_{side}'] = add(j[f'ankle_{side}'], (0.0, lf*.45, -.07))
            if h:
                contacts.append(f'knee_{side}')
        out.append(frame_of(j, (0.0, -y, 0.0), contacts))
    return dict(frames=out, loop=True, root_motion=True, speed_m_s=v)


def climb(H, a, fps, pitch):
    """Vertical ladder climb, facing the rungs, at climb_rungs_per_s: a hand and the opposite foot move up two rungs together while the
    other pair holds, so each limb holds half the cycle. Feet on the rungs' front edge, hands on rungs above the shoulders. Root motion
    up (+Z). Rungs every `pitch` m in the plane Y = -0.30 (in front of the body)."""
    rate = a['climb_rungs_per_s']*pitch; T = 2*pitch/rate; n = round(T*fps); l1, l2, la, lf = leg_lengths(H); yr = -.30; out = []
    right = ch.frame(UP, FORWARD)[0]; hip_y = yr+.28; foot_y = yr+.10
    reach = .97*(l1+l2); hip0 = math.sqrt(reach**2-(hip_y-foot_y)**2)+la+.02-pitch      # the leg nearly straight at the end of a hold
    hand0 = math.floor((hip0+ch.P['shoulder_z']*H+.45)/pitch)*pitch      # a hold starts with the hand about 0.45 m above the shoulder
    def limb(t, off, base):
        """(height, held) of a limb: it holds its rung for half the cycle, then moves up two rungs. Limbs half a cycle out of phase
        start one rung lower, so the feet (and the hands) leapfrog on alternate rungs and every hold starts at the same body height."""
        off %= 1.0; ph = (t/T+off) % 1.0; lo = base-(pitch if off else 0.0)+2*pitch*math.floor(t/T+off)
        return (lo, True) if ph < .5 else (lo+2*pitch*smooth((ph-.5)/.5), False)
    for i in range(n):
        t = i*T/n; z = rate*t; contacts = []; ank = {}; toes = {}; hd = {}
        for side, sg, off in (('right', 1, 0.0), ('left', -1, .5)):
            fz, held = limb(t, off, 0.0)
            if held:
                contacts.append(f'foot_{side}')
            ank[side] = add(mul(right, sg*.12), (0.0, foot_y, fz+la+.02)); toes[side] = add(mul(right, sg*.12), (0.0, yr-.02, fz+.02))
            hz, held = limb(t, off+.5, hand0)
            if held:
                contacts.append(f'hand_{side}')
            hd[side] = (add(mul(right, sg*.17), (0.0, yr+.02, hz)), (0.0, 1.0, -.2))
        j = ch.skeleton(figure(H), dict(ch.STAND, trunk=4.0, head=-15.0), (0.0, hip_y, hip0+z), UP, FORWARD, hands=hd)
        out.append(frame_of(legs_to(j, H, ank, FORWARD, UP, toes), (0.0, 0.0, z), contacts))
    return dict(frames=out, loop=True, root_motion=True, speed_m_s=rate, rung_pitch_m=pitch)


def run(H, a, fps):
    """One running cycle (two steps) at run_speed_m_s and run_cadence_steps_min (LOCO-001, PROTOTYPE): each foot on the deck for
    run_stance_fraction of its cycle (so there are flight phases), swing arcs of run_step_height_m, a pelvis bob of one dip per step at
    mid-stance, bent arms swinging with the opposite leg, the trunk leaning 7 deg into the run, the determinants of GAIT['run']. Root
    motion along -Y."""
    v = a['run_speed_m_s']; T = 120.0/a['run_cadence_steps_min']; st = a['run_stance_fraction']
    l1, l2, _, _ = leg_lengths(H); reach = .985*(l1+l2)
    bob = lambda t: .95*reach-.025*reach*math.cos(4*math.pi*(t/T-st/2))      # one dip per step at mid-stance, highest in flight
    out = _gait(H, a, fps, v, T, st, a['run_step_height_m'], GAIT['run'], bob, lift_pow=.8)
    return dict(frames=out, loop=True, root_motion=True, speed_m_s=v)


def _stance(H, drop, arms, trunk=0.0, head=0.0, fps=30):
    """A standing frame with both feet planted where idle plants them and the pelvis `drop` m below standing."""
    leg = sum(leg_lengths(H)[:3])*.995; right = ch.frame(UP, FORWARD)[0]
    pose = dict(ch.STAND, trunk=trunk, head=head, arms=arms)
    j = ch.skeleton(figure(H), pose, (0.0, .02*drop, leg-drop), UP, FORWARD)
    ank = {s: (sg*ch.P['hip_x']*H*1.25*right[0], 0.0, ch.P['ankle']*H) for s, sg in zip(SIDES, (1, -1))}
    return frame_of(legs_to(j, H, ank, FORWARD, UP), (0.0, 0.0, 0.0), ('foot_right', 'foot_left'))


def _arms(flex, elbow, abduct=12.0):
    return dict(right=dict(flex=flex, abduct=abduct, elbow=elbow), left=dict(flex=flex, abduct=abduct, elbow=elbow))


def jump(H, a, fps):
    """The take-off (LOCO-001, PROTOTYPE): from standing the body crouches by jump_crouch_m with the arms swung back, then extends to
    straight legs as the arms swing forward. Both feet stay planted: the runtime applies the jump impulse when this clip ends (the
    legs' push is the physics impulse, not root motion)."""
    T = a['jump_takeoff_s']; n = max(4, round(T*fps)); out = []; c = a['jump_crouch_m']
    for i in range(n):
        t = i/(n-1); down = .6
        drop = c*smooth(t/down) if t < down else c*(1-smooth((t-down)/(1-down)))
        flex = -35.0*smooth(t/down) if t < down else -35.0+95.0*smooth((t-down)/(1-down))
        out.append(_stance(H, drop, _arms(flex, 20.0+20.0*smooth(t/down)), trunk=18.0*drop/c, head=-4.0))
    return dict(frames=out, loop=False, root_motion=False)


def fall(H, a, fps):
    """Airborne (LOCO-001, PROTOTYPE): a 1 s loop with the knees and hips a little bent, arms out for balance; no contacts. The body
    follows its own ballistic path in the runtime."""
    n = fps; out = []; leg = sum(leg_lengths(H)[:3])*.995
    for i in range(n):
        w = math.sin(2*math.pi*i/n)
        pose = dict(ch.STAND, trunk=4.0, head=-6.0, hip=(22.0+4*w, 16.0-4*w), knee=(30.0+5*w, 24.0-5*w), ankle=(-12.0, -10.0),
                    arms=dict(right=dict(flex=25.0+5*w, abduct=38.0, elbow=35.0), left=dict(flex=25.0-5*w, abduct=38.0, elbow=35.0)))
        out.append(frame_of(ch.skeleton(figure(H), pose, (0.0, 0.0, leg), UP, FORWARD), (0.0, 0.0, 0.0), ()))
    return dict(frames=out, loop=True, root_motion=False)


def land(H, a, fps):
    """Landing (LOCO-001, PROTOTYPE): feet planted, the legs absorb the touchdown down to land_crouch_m at a third of the clip and
    recover to standing; the arms come forward and settle."""
    T = a['land_s']; n = max(4, round(T*fps)); out = []; c = a['land_crouch_m']
    for i in range(n):
        t = i/(n-1); k = .3
        drop = c*math.sin(.5*math.pi*t/k) if t < k else c*(1-smooth((t-k)/(1-k)))
        out.append(_stance(H, drop, _arms(30.0*drop/c, 15.0+35.0*drop/c, 14.0), trunk=14.0*drop/c, head=-6.0))
    return dict(frames=out, loop=False, root_motion=False)


def step(H, a, fps):
    """Stepping in place (LOCO-001, PROTOTYPE): the feet lift in turn by step_height_m at walk cadence, so a body turning on the spot
    turns on its feet; root fixed. Turning itself is the body's heading in the runtime."""
    T = 120.0/a['walk_cadence_steps_min']; n = round(T*fps); out = []; leg = sum(leg_lengths(H)[:3])*.995
    right = ch.frame(UP, FORWARD)[0]; la = ch.P['ankle']*H
    for i in range(n):
        t = i/n; contacts = []; ank = {}
        for side, off, sg in (('right', 0.0, 1), ('left', .5, -1)):
            ph = (t+off) % 1.0; lift = 0.0
            if ph < .6:
                contacts.append(f'foot_{side}')
            else:
                lift = .6*a['step_height_m']*math.sin(math.pi*(ph-.6)/.4)
            ank[side] = (sg*ch.P['hip_x']*H*1.25*right[0], 0.0, la+lift)
        dip = .01*math.cos(4*math.pi*t)
        j = ch.skeleton(figure(H), dict(ch.STAND, trunk=2.0, head=-3.0), (0.0, 0.0, leg-.012-dip), UP, FORWARD)
        out.append(frame_of(legs_to(j, H, ank, FORWARD, UP), (0.0, 0.0, 0.0), contacts))
    return dict(frames=out, loop=True, root_motion=False)


ACTIONS = ('idle', 'walk', 'sit', 'crawl', 'climb', 'run', 'jump', 'fall', 'land', 'step')


def proportions(bones, H):
    """characters.P segment fractions measured on a rig: bones = {name: (head, tail)} in the rest pose, feet on the floor. The
    procedural source is generated with the target body's own segments, so its contacts are reachable by that body."""
    L = lambda b: math.dist(*bones[b]); hz = bones['thigh_l'][0][2]; z = lambda b: bones[b][0][2]-hz
    return dict(hip_x=abs(bones['thigh_l'][0][0])/H, waist_z=z('spine_02')/H, chest_z=z('spine_03')/H, shoulder_z=z('upperarm_l')/H,
                shoulder_x=abs(bones['upperarm_l'][0][0])/H, neck_z=z('neck_01')/H, head_z=(z('head')+.5*L('head'))/H,
                upper_arm=L('upperarm_l')/H, forearm=L('lowerarm_l')/H, hand=L('hand_l')/H*1.6, thigh=L('thigh_l')/H, shank=L('calf_l')/H,
                ankle=bones['foot_l'][0][2]/H, foot=(L('foot_l')+L('ball_l'))/H)


def actions(H, a, fps, seat, pitch, P=None):
    """The library at stature H; with P (proportions()) the characters.P fractions are those of the target body while it is built."""
    saved = dict(ch.P)
    try:
        ch.P.update(P or {})
        return dict(idle=idle(H, a, fps), walk=walk(H, a, fps), sit=sit(H, a, fps, seat), crawl=crawl(H, a, fps), climb=climb(H, a, fps, pitch),
                    run=run(H, a, fps), jump=jump(H, a, fps), fall=fall(H, a, fps), land=land(H, a, fps), step=step(H, a, fps),
                    rest=rest(H))
    finally:
        ch.P.clear(); ch.P.update(saved)


def scale_source(frames, k):
    """A source from a differently sized body: every position scaled by k about the origin (hip-height ratio), directions kept.
    Stationary contacts stay stationary, so planted feet stay planted."""
    out = []
    for f in frames:
        g = {key: (mul(v, k) if key not in ('head_up', 'face', 'contacts') and isinstance(v, tuple) and len(v) == 3 else v) for key, v in f.items()}
        out.append(g)
    return out


def contact_slip(points, contacts):
    """Largest drift (m) of each limb's contact point while the source holds it still: points = per-frame {limb: (x, y, z)},
    contacts = per-frame tuples of held limbs. A hold is measured from its first frame."""
    worst = {}; anchor = {}
    for pts, held in zip(points, contacts):
        for limb, p in pts.items():
            if limb in held:
                a = anchor.setdefault(limb, p)
                worst[limb] = max(worst.get(limb, 0.0), math.dist(a, p))
            else:
                anchor.pop(limb, None)
    return worst
