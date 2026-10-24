"""WAYFARER_EVA_Y155, the guided-EVA pressure suit (EVA-001, docs/EVA.md): its data contract, the tether protocol and the EVA motion
sources. Standard library only; the Blender side is build/eva_suit.py, the exterior route eva_route.py.

Ownership: S&E 43_EVA_SUIT_REQUIREMENTS / 44_EVA_SUIT_BLENDER own the suit contract, Technology 53 the science, Tale 26_GUIDED_EVA the tour.
Every physical value the owners have not released is None (OPEN) and the runtime treats it as unsafe (RIG-01, RUN-012). Dimensions are
PROTOTYPE fit choices of data/eva_suit.toml; nothing is CERTIFIED (QA-03).

The EVA actions use the retarget source format of human_system (world joints per frame, root, held contacts), so the shared Solver poses
any wearer's game_engine rig from them. They are authored in place: the travel actions keep the body still and record `travel_speed_m_s`;
the runtime moves the node at that speed, so a gripping hand is still in the world while its body passes it.
"""
import math
from pathlib import Path
import tomllib

import characters as ch
import human_system as hs

ROOT = Path(__file__).resolve().parents[2]
SIDES = hs.SIDES
add, sub, mul, lerp, smooth = hs.add, hs.sub, hs.mul, hs.lerp, hs.smooth


def load(root=ROOT):
    """data/eva_suit.toml with the OPEN rule applied: an empty value is None (TOML has no null), and an OPEN field must stay None."""
    data = tomllib.loads((root / 'data/eva_suit.toml').read_text())
    for key, f in data['telemetry'].items():
        if f['value'] == '':
            f['value'] = None
        assert (f['value'] is None) == (f['status'] == 'OPEN'), f'telemetry.{key}: OPEN fields carry no value and only OPEN fields are empty'
    chars = tomllib.loads((root / 'data/characters.toml').read_text())['human']
    for v in data['variant'].values():
        assert v['wearer'] in chars and chars[v['wearer']]['kind'] == 'induction', f"variant wearer {v['wearer']} must be an induction character"
    for key, f in data.get('thermal_case', {}).items():          # 45 H rows: OPEN REQUIRED stays None
        if f['value'] == '':
            f['value'] = None
        assert (f['value'] is None) == f['status'].startswith('OPEN'), f'thermal_case.{key}: OPEN rows carry no value'
    for s in data['station']:
        assert s['hold'] in ('airlock', 'rail_mid', 'aft_hold', 'forward_hold'), s['id']
        assert all(s[k] for k in ('what', 'why', 'show', 'sources', 'script', 'safety')), f"{s['id']}: What / Why / Show me, the Tale script and sources are required"
    assert data['suit']['status'] == 'PROTOTYPE' and 'NOT CERTIFIED' in data['suit']['certification']
    return data


def telemetry_contract(data):
    """EVA-039: one record per field with value, unit, status, source; None stays None (JSON null)."""
    return {k: dict(value=f['value'], unit=f['unit'], status=f['status'], source=f['source'], note=f.get('note', ''))
            for k, f in data['telemetry'].items()}


def part_ids(data):
    """Stable semantic ids of the assembly tree (RUN-005): WAYFARER_EVA_Y155/<ASSEMBLY>/<PART>."""
    return [f"{data['suit']['id']}/{a}/{p}" for a, q in data['assemblies'].items() for p in q['parts']]


# ----------------------------------------------------------------------------------------------------------------------------------
# Tether protocol (EVA-014, ANIM-06, SIM-03): two independent tethers. Mirrored by godot/scripts/eva.gd; the test drives this one.

class Tethers:
    """State of the two waist tethers A and B: each is None or {'anchor': i, 'tested': bool}. Rules: at most one anchor per tether;
    a tether may be released only while the other is clipped to a different anchor and tested; the body may move only within `reach`
    of every clipped anchor. Every refused action returns the reason; nothing silently passes."""

    def __init__(self, anchors, reach, start=0):
        self.anchors = list(anchors); self.reach = reach
        self.t = dict(A=dict(anchor=start, tested=True), B=None)

    def live(self):
        return [k for k, v in self.t.items() if v is not None]

    def clip(self, which, anchor, at):
        if self.t[which] is not None:
            return f'tether {which} is already clipped'
        if abs(self.anchors[anchor]-at) > self.reach:
            return f'anchor {anchor} is out of reach'
        if any(v and v['anchor'] == anchor for v in self.t.values()):
            return 'both tethers on one anchor are not independent'
        self.t[which] = dict(anchor=anchor, tested=False); return None

    def test(self, which):
        if self.t[which] is None:
            return f'tether {which} is not clipped'
        self.t[which]['tested'] = True; return None

    def release(self, which):
        other = 'B' if which == 'A' else 'A'
        if self.t[which] is None:
            return f'tether {which} is not clipped'
        if self.t[other] is None or not self.t[other]['tested']:
            return f'release refused: tether {other} must be clipped and tested first'
        self.t[which] = None; return None

    def limits(self):
        """The interval of rail positions the clipped tethers allow."""
        live = [self.anchors[v['anchor']] for v in self.t.values() if v]
        return max(live)-self.reach, min(live)+self.reach

    def move(self, at, to):
        lo, hi = self.limits(); return min(hi, max(lo, to))


def handoff_plan(anchors, start, goal):
    """The protocol steps from anchor `start` to anchor `goal`, one anchor at a time, alternating the tethers (the runtime's AUTO and
    abort sequences, ANIM-08): each step is (verb, tether, anchor) with verb in clip / test / release / move."""
    steps = []; held = 'A'; step = 1 if goal >= start else -1
    for a in range(start, goal, step):
        free = 'B' if held == 'A' else 'A'
        steps += [('move', None, a+step), ('clip', free, a+step), ('test', free, a+step), ('release', held, a)]; held = free
    return steps


# ----------------------------------------------------------------------------------------------------------------------------------
# EVA motion sources (ANIM-01..08), PROTOTYPE motion. Character frame: MPFB faces -Y, +Z up, Root at the origin.

def _fig(H):
    return hs.figure(H)


def _frame(j, root, contacts=()):
    return hs.frame_of(j, root, contacts)


def _legs(pose_knee, hip_flex=30.0):
    return dict(hip=(hip_flex, hip_flex+6.0), knee=(pose_knee, pose_knee+8.0), abduct=(7.0, 7.0), ankle=(-15.0, -15.0))


def floating(H, t_hip, up, face, arms, head=-8.0, trunk=0.0, legs=None):
    """A floating suited body: hip centre at t_hip, body axis `up`, facing `face`, arms {'right'|'left': (wrist target, pole)} by IK."""
    pose = dict(ch.STAND, trunk=trunk, head=head, **(legs or _legs(25.0)))
    return ch.skeleton(_fig(H), pose, t_hip, up, face, hands=suit_reach(H, pose, t_hip, up, face, arms))


ELBOW_LIMIT = [115.0]                                        # set from [mobility] while a library is generated


def suit_reach(H, pose, t_hip, up, face, arms):
    """A pressurized elbow does not fold past the mobility limit: a wrist target closer to its shoulder than that limit allows is moved
    out along the shoulder-to-target line (the hand stops short, as a suited hand does)."""
    if not arms:
        return arms
    j0 = ch.skeleton(_fig(H), pose, t_hip, up, face); l1, l2 = ch.P['upper_arm']*H, ch.P['forearm']*H
    dmin = math.sqrt(l1*l1+l2*l2+2*l1*l2*math.cos(math.radians(ELBOW_LIMIT[0])))*1.002
    out = {}
    for s, (target, pole) in arms.items():
        d = sub(target, j0[f'shoulder_{s}']); L = ch.norm(d)
        out[s] = (add(j0[f'shoulder_{s}'], mul(d, dmin/L)) if L < dmin else target, pole)
    return out


def grip(rail_point, normal, along):
    """A wrist target that puts the palm on a rail point: the wrist sits off the rail toward the body along `normal`; the pole bends
    the elbow back along the rail."""
    return add(rail_point, mul(normal, .085)), mul(along, -1.0)


def suit_check(H, mob, fps):
    """ANIM-01/02 (DON_SUIT end state and LOCK_CHECK): upright in a foot restraint (feet held), the checks a crew member makes before a
    GO: chest display, the left forearm status display, both hands on the helmet neck ring, each glove's wrist disconnect. 12 s."""
    legs = sum(hs.leg_lengths(H)[:3]); hip = (0.0, 0.0, legs*.99); F = (0.0, -1.0, 0.0); U = (0.0, 0.0, 1.0)
    j0 = ch.skeleton(_fig(H), ch.STAND, hip, U, F)
    chest = add(j0['chest'], (0.0, -.38, -.08)); neck = add(j0['neck'], (0.0, -.16, -.06))
    wrist_l_read = add(j0['chest'], (.04, -.44, .02))
    keys = [  # (time s, right wrist target, left wrist target, head angle)
        (0.0, None, None, -6.0),
        (1.5, add(chest, (-.03, 0.0, -.04)), None, -18.0),                    # right hand on the chest display
        (3.5, add(chest, (-.03, 0.0, -.04)), None, -18.0),
        (5.0, None, wrist_l_read, -16.0),                                     # left forearm raised: wrist display
        (6.5, None, wrist_l_read, -16.0),
        (8.0, add(neck, (-.18, -.26, -.12)), add(neck, (.18, -.26, -.12)), -4.0),   # both hands on the neck ring: helmet locked
        (9.0, add(neck, (-.18, -.26, -.12)), add(neck, (.18, -.26, -.12)), -4.0),
        (10.5, add(j0['chest'], (-.02, -.42, -.20)), add(j0['chest'], (.12, -.44, -.26)), -14.0),   # right hand on the left wrist ring
        (12.0, None, None, -6.0)]
    out = []; n = 12*fps
    rest = {s: j0[f'wrist_{s}'] for s in SIDES}
    for i in range(n):
        t = i/fps; k = max(q for q in range(len(keys)) if keys[q][0] <= t); a = keys[k]; b = keys[min(k+1, len(keys)-1)]
        u = smooth((t-a[0])/max(1e-6, b[0]-a[0])) if b is not a else 0.0
        arms = {}
        for idx, s in ((1, 'right'), (2, 'left')):
            pa = a[idx] or rest[s]; pb = b[idx] or rest[s]; arms[s] = (lerp(pa, pb, u), (0.0, .4, -1.0))
        head = a[3]+(b[3]-a[3])*u
        pose = dict(ch.STAND, head=head); j = ch.skeleton(_fig(H), pose, hip, U, F, hands=suit_reach(H, pose, hip, U, F, arms))
        ank = {s: (sg*ch.P['hip_x']*H*1.25, 0.0, ch.P['ankle']*H) for s, sg in zip(SIDES, (-1, 1))}
        out.append(_frame(hs.legs_to(j, H, ank, F, U), (0.0, 0.0, 0.0), ('foot_right', 'foot_left')))
    return dict(frames=out, loop=False, root_motion=False, events=[(1.5, 'chest_display'), (5.0, 'wrist_display'), (8.0, 'helmet_lock'),
                                                                  (10.5, 'glove_lock')])


def _rail_body(H):
    """Body along a rail on the hull: the rail runs along Y at z = 0, the body floats above it head first toward -Y, facing the hull."""
    U = (0.0, -1.0, 0.0); F = (0.0, 0.0, -1.0); hip = (0.0, .30, .50)
    return U, F, hip


def rail_translate(H, mob, fps, speed=None):
    """ANIM-04 HANDRAIL_TRANSLATION: hand over hand along a fixed rail, in place (travel_speed_m_s): each hand holds the rail while the body
    passes (it slides aft in the body frame at the travel speed) and is carried one stride forward; double support at each change."""
    v = speed or mob['translation_speed_m_s']; stride = mob['hand_stride_m']; T = 2*stride/v; n = round(T*fps); U, F, hip = _rail_body(H)
    y_front = hip[1]-ch.P['shoulder_z']*H-.22; out = []; grips = []
    for i in range(n):
        t = i*T/n; arms = {}; held = []
        for side, off, x in (('right', 0.0, -.07), ('left', .5, .07)):
            ph = (t/T+off) % 1.0; hold = .6; y_end = y_front+v*hold*T
            if ph < hold:                                  # gripping: the hand slides aft relative to the body at the travel speed
                y = y_front+v*ph*T; lift = 0.0; held.append(f'hand_{side}')
            else:                                          # carried forward one stride, clear of the rail
                s = smooth((ph-hold)/(1-hold)); y = y_end+(y_front-y_end)*s; lift = .10*math.sin(math.pi*s)
            arms[side] = grip((x, y, lift), (0.0, 0.0, 1.0), U)
        sway = .015*math.sin(2*math.pi*t/T)
        j = floating(H, add(hip, (sway, 0.0, 0.0)), U, F, arms, head=-14.0, legs=_legs(30.0, 20.0))
        out.append(_frame(j, (0.0, 0.0, 0.0))); grips.append(held)
    return dict(frames=out, loop=True, root_motion=False, travel_speed_m_s=v, grips=grips)


# At a hold point (PROTOTYPE training fixture, eva_route): a work-site handhold bar on a short stanchion beside the rail, at about the
# height of the floating body's hip. The body floats upright over the hull, the left hand on the bar.
BAR = (-1.0, 0.0, 0.0)                                       # from the bar toward the body: the wrist sits this side of it
SOLE_CLEAR = .08                                             # the floating body's soles stay this far off the skin at a hold


def hold_geometry(H):
    """Hip and handhold (bar centre) of a hold for a body of stature H, origin on the hull skin under the hip: the hip floats high
    enough that the slightly bent suited legs keep SOLE_CLEAR off the skin; the bar is a hand's breadth above the hip, to the left."""
    leg = sum(hs.leg_lengths(H)[:3]); hip = (0.0, 0.0, leg*.97+SOLE_CLEAR+.03)
    return hip, (.32, -.15, hip[2]+.10)


def _hold_pose(H):
    hip, bar = hold_geometry(H); return (0.0, 0.0, 1.0), (0.0, -1.0, 0.0), hip, bar


def _hold_left(H):
    return grip(hold_geometry(H)[1], BAR, (0.0, 1.0, 0.0))


def body_rotate(H, mob, fps):
    """ANIM-05 controlled body rotation: from translating along the low rail (head first, facing the hull) to upright at a hold's
    handhold. One hand always holds: the left moves to the handhold while the right keeps the rail, then the right follows. 5 s."""
    n = 5*fps; out = []; U0, F0, hip0 = _rail_body(H)
    y_front = hip0[1]-ch.P['shoulder_z']*H-.22
    a0 = {'right': grip((-.07, y_front, 0.0), (0.0, 0.0, 1.0), U0), 'left': grip((.07, y_front+.25, 0.0), (0.0, 0.0, 1.0), U0)}
    U1, F1, hip1, bar = _hold_pose(H); a1 = {'left': _hold_left(H), 'right': grip(add(bar, (0.0, -.18, 0.0)), BAR, (0.0, 1.0, 0.0))}
    for i in range(n):
        u = smooth(i/(n-1)); ang = math.radians(90.0*u)
        up = ch.unit(add(mul(U0, math.cos(ang)), mul(U1, math.sin(ang)))); face = ch.unit(add(mul(F0, math.cos(ang)), mul(F1, math.sin(ang))))
        hip = lerp(hip0, hip1, u); ul = smooth(min(1.0, i/(n-1)/.5)); ur = smooth(max(0.0, i/(n-1)-.5)/.5)
        arms = {'left': (lerp(a0['left'][0], a1['left'][0], ul), (.3, .6, -.7)), 'right': (lerp(a0['right'][0], a1['right'][0], ur), (-.3, .6, -.7))}
        held = [h for h, k in (('hand_left', ul), ('hand_right', ur)) if k in (0.0, 1.0)]
        j = floating(H, hip, up, face, arms, head=-12.0, legs=_legs(30.0-10*u, 20.0-5*u))
        out.append(_frame(j, (0.0, 0.0, 0.0), held))
    return dict(frames=out, loop=False, root_motion=False)


def _keyed(keys, t):
    """Smoothstep between (time, value) keys; value is a point."""
    k = max(q for q in range(len(keys)) if keys[q][0] <= t); a = keys[k]; b = keys[min(k+1, len(keys)-1)]
    u = smooth((t-a[0])/max(1e-6, b[0]-a[0])) if b is not a else 0.0
    return lerp(a[1], b[1], u)


def _at_hold(H, fps, seconds, right, head=lambda t: -10.0, trunk=0.0, pole=(.3, .6, -.7)):
    """Frames of a hold action: the left hand on the handhold, the right wrist at right(t)."""
    U, F, hip, _ = _hold_pose(H); out = []
    for i in range(round(seconds*fps)):
        t = i/fps; arms = {'left': _hold_left(H), 'right': (right(t), pole)}
        j = floating(H, hip, U, F, arms, head=head(t), trunk=trunk, legs=_legs(20.0, 15.0))
        out.append(_frame(j, (0.0, 0.0, 0.0), ('hand_left',)))
    return out


def _hold_joints(H):
    U, F, hip, _ = _hold_pose(H)
    return floating(H, hip, U, F, {'left': _hold_left(H)}, legs=_legs(20.0, 15.0))


def guide_point(H, mob, fps):
    """ANIM-07 GUIDE_POINT_EXPLAIN: left hand on the handhold, the right arm points out and up at a feature, the head follows inside the
    helmet, then the arm returns to a ready position. 6 s, the pointing held from 1.5 s to 4.5 s."""
    j0 = _hold_joints(H); sh = j0['shoulder_right']; reach = (ch.P['upper_arm']+ch.P['forearm'])*H*.97
    d = ch.unit((-.45, -.75, .45)); point = add(sh, mul(d, reach)); ready = add(j0['chest'], (-.20, -.28, -.10))
    u = lambda t: smooth(t/1.5) if t < 1.5 else (1.0 if t < 4.5 else 1.0-smooth((t-4.5)/1.5))
    return dict(frames=_at_hold(H, fps, 6, lambda t: lerp(ready, point, u(t)), head=lambda t: -6.0+12.0*u(t), pole=(.2, .8, -.6)),
                loop=False, root_motion=False, point_dir_body=list(d))


def tether_transfer(H, mob, fps):
    """ANIM-06 TETHER_HANDOFF at a hold: the left hand stays on the handhold; the right hand takes hook B from the right waist reel,
    clips it to the next anchor ahead, tugs it (test), then reaches hook A at the old anchor and releases it. The events time the
    protocol so the runtime shows two live anchors until B is tested (eva_suit.Tethers). 9 s."""
    j0 = _hold_joints(H)
    reel_b = add(j0['hip_right'], (-.10, -.14, .06)); hz = j0['hip_c'][2]
    anchor_b = (-.22, -.45, hz-.10); anchor_a = (.05, -.30, hz-.18)
    rest = add(j0['chest'], (-.20, -.25, -.15)); tug = add(anchor_b, (0.0, .10, .10))
    keys = [(0.0, rest), (1.2, reel_b), (1.8, reel_b), (3.2, anchor_b), (3.8, anchor_b), (4.4, tug), (4.9, anchor_b), (6.2, anchor_a),
            (7.0, anchor_a), (9.0, rest)]
    return dict(frames=_at_hold(H, fps, 9, lambda t: _keyed(keys, t), head=lambda t: -16.0), loop=False, root_motion=False,
                events=[(1.8, 'hook_B_in_hand'), (3.8, 'B_clipped'), (4.9, 'B_tested'), (7.0, 'A_released')],
                anchors_body=dict(A=list(anchor_a), B=list(anchor_b)))


def tool_inspect(H, mob, fps):
    """ANIM-07/ASSET-14: left hand on the handhold, the right hand holds the inspection tool toward a work point and sweeps it slowly;
    the head follows. 6 s loop."""
    z = hold_geometry(H)[0][2]+.15; target = lambda t: (-.20+.10*math.sin(2*math.pi*t/6), -.46, z+.04*math.cos(2*math.pi*t/6))
    return dict(frames=_at_hold(H, fps, 6, target, head=lambda t: -14.0, trunk=6.0), loop=True, root_motion=False)


def airlock_cycle(H, mob, fps):
    """ANIM-03 AIRLOCK_EXIT_RETURN, one crew member's part: floating upright in the chamber, the left hand on a handhold; the right hand
    works the panel (inner hatch confirmed shut, depress), then takes the outer hatch handle and pulls it open. The door order is the
    runtime's interlock; this is only the body. 8 s."""
    j0 = _hold_joints(H)
    rest = add(j0['chest'], (-.20, -.25, -.15)); panel = add(j0['chest'], (-.30, -.48, .05)); handle = add(j0['head'], (-.15, -.48, .05))
    keys = [(0.0, rest), (1.5, panel), (3.5, panel), (5.0, handle), (6.0, handle), (7.0, add(handle, (0.0, .12, -.05))), (8.0, rest)]
    return dict(frames=_at_hold(H, fps, 8, lambda t: _keyed(keys, t), head=lambda t: -4.0), loop=False, root_motion=False,
                events=[(1.5, 'panel'), (5.0, 'outer_hatch_handle')])


# EVA-002 (44 EVA2-003, 43 EVA-043/044/054): the suited motions the SP-11/12 study sweeps. They replace the interior crawl and climb,
# which take the head out of the helmet (docs/EVA.md); PROTOTYPE motion, simplified training representations.

def hatch_pass(H, mob, fps):
    """Head first through a hatch: the body axis is the passage axis (+Z), both hands pull on the frame ahead in turn, held inside the
    suited shoulder and elbow limits (the hands land ahead of the visor, not over the head). In place: travel_speed_m_s is a display
    pace. 4 s loop."""
    U = (0.0, 0.0, 1.0); F = (0.0, -1.0, 0.0); hip = (0.0, 0.0, 0.0); j0 = floating(H, hip, U, F, {})
    reach = (ch.P['upper_arm']+ch.P['forearm'])*H*.86; out = []; grips = []
    for i in range(4*fps):
        t = i/fps; arms = {}; held = []
        for side, sg, off in (('right', 1.0, 0.0), ('left', -1.0, .5)):
            ph = (t/4.0+off) % 1.0; pull = ph < .65; s = ph/.65 if pull else (ph-.65)/.35
            flex = math.radians(100.0-30.0*s if pull else 70.0+30.0*smooth(s))   # pull down from 100 deg, then reach back up
            d = (sg*.30, -math.sin(flex), -math.cos(flex)); target = add(j0[f'shoulder_{side}'], mul(ch.unit(d), reach))
            arms[side] = (target, (sg*.5, .3, -.8)); held += [f'hand_{side}'] if pull else []
        j = floating(H, hip, U, F, arms, head=-10.0, legs=_legs(15.0, 10.0))
        out.append(_frame(j, (0.0, 0.0, 0.0), held)); grips.append(held)
    return dict(frames=out, loop=True, root_motion=False, travel_speed_m_s=.15, grips=grips)


def buddy_check(H, mob, fps):
    """SP-12 buddy check (12A SP-12, 43 EVA-054): upright in a foot restraint behind the partner, both hands go over the partner's
    pack: the purge/emergency actuator, the tether hooks on both sides, the helmet neck ring. 10 s."""
    legs = sum(hs.leg_lengths(H)[:3]); hip = (0.0, 0.0, legs*.99); F = (0.0, -1.0, 0.0); U = (0.0, 0.0, 1.0)
    j0 = ch.skeleton(_fig(H), ch.STAND, hip, U, F); c = j0['chest']; rest = {s: j0[f'wrist_{s}'] for s in SIDES}
    pack = add(c, (0.0, -.50, -.05)); neck = add(j0['neck'], (0.0, -.46, .02))
    keys = [(0.0, None, None), (2.0, add(pack, (-.10, 0.0, -.12)), None), (3.5, add(pack, (-.10, 0.0, -.12)), None),
            (5.0, add(pack, (-.28, .08, -.40)), add(pack, (.28, .08, -.40))), (6.5, add(pack, (-.28, .08, -.40)), add(pack, (.28, .08, -.40))),
            (8.0, add(neck, (-.14, 0.0, 0.0)), add(neck, (.14, 0.0, 0.0))), (9.0, add(neck, (-.14, 0.0, 0.0)), add(neck, (.14, 0.0, 0.0))),
            (10.0, None, None)]
    out = []
    for i in range(10*fps):
        t = i/fps; k = max(q for q in range(len(keys)) if keys[q][0] <= t); a = keys[k]; b = keys[min(k+1, len(keys)-1)]
        u = smooth((t-a[0])/max(1e-6, b[0]-a[0])) if b is not a else 0.0
        arms = {s: (lerp(a[i2] or rest[s], b[i2] or rest[s], u), (0.0, .4, -1.0)) for i2, s in ((1, 'right'), (2, 'left'))}
        pose = dict(ch.STAND, head=-14.0); j = ch.skeleton(_fig(H), pose, hip, U, F, hands=suit_reach(H, pose, hip, U, F, arms))
        ank = {s: (sg*ch.P['hip_x']*H*1.25, 0.0, ch.P['ankle']*H) for s, sg in zip(SIDES, (-1, 1))}
        out.append(_frame(hs.legs_to(j, H, ank, F, U), (0.0, 0.0, 0.0), ('foot_right', 'foot_left')))
    return dict(frames=out, loop=False, root_motion=False, events=[(2.0, 'emergency_actuator'), (5.0, 'tether_hooks'), (8.0, 'neck_ring')])


def casualty(H, mob, fps):
    """An unresponsive suited crew member (43 EVA-054, 15 HUM-002): the relaxed microgravity neutral body posture (characters.FLOAT,
    hips and knees flexed, arms floating forward), drifting slightly. No hand holds anything. 4 s loop."""
    U = (0.0, 0.0, 1.0); F = (0.0, -1.0, 0.0); out = []
    for i in range(4*fps):
        w = math.sin(2*math.pi*i/(4*fps)); arms = {s: dict(ch.FLOAT['arms'][s], flex=40.0+6*w) for s in SIDES}
        pose = dict(ch.FLOAT, arms=arms, head=-15.0+3*w)
        out.append(_frame(ch.skeleton(_fig(H), pose, (0.0, 0.0, 0.0), U, F), (0.0, 0.0, 0.0)))
    return dict(frames=out, loop=True, root_motion=False)


def rescue_hold(H, mob, fps):
    """The rescuer's part of a casualty transfer (EVA-054): the left hand keeps the handhold, the right hand holds the casualty's pack
    handle ahead at chest height and steadies it (the casualty is moved by the rescuer and a tether, never by thrusters). 6 s."""
    j0 = _hold_joints(H); handle = add(j0['chest'], (-.10, -.50, -.02)); push = add(handle, (0.0, -.08, 0.0))
    keys = [(0.0, add(j0['chest'], (-.20, -.25, -.15))), (1.5, handle), (3.5, push), (5.0, handle), (6.0, handle)]
    return dict(frames=_at_hold(H, fps, 6, lambda t: _keyed(keys, t), head=lambda t: -12.0), loop=False, root_motion=False,
                events=[(1.5, 'casualty_handle')])


# EVA-003 (44 EVA3-002/003, 43 EVA-057/058): the SP-11 latch and the supported casualty, PROTOTYPE motion on the same rigs. Body frame
# as above (faces -Y, right hand toward -X). The handle and strap points are returned in the body frame so the study can mount the
# hardware where the rig's hand actually goes (eva_sp11.py), never the other way round.

def _restrained(H):
    legs = sum(hs.leg_lengths(H)[:3]); hip = (0.0, 0.0, legs*.99); F = (0.0, -1.0, 0.0); U = (0.0, 0.0, 1.0)
    return hip, U, F, ch.skeleton(_fig(H), ch.STAND, hip, U, F)


def _feet(j, H, U, F):
    ank = {s: (sg*ch.P['hip_x']*H*1.25, 0.0, ch.P['ankle']*H) for s, sg in zip(SIDES, (-1, 1))}
    return hs.legs_to(j, H, ank, F, U)


LATCH_ARC_M = .16                    # PROTOTYPE extension lever: grip radius about its pivot; a 90 deg throw releases the dogs


def latch_extension(H, mob, fps):
    """EVA3-002 preferred concept: upright in the chamber's foot restraint, the right hand on a handhold ahead of the waist, the left
    hand takes the extension lever ahead of the shoulder (a remote linkage to the outer hatch's latch dogs, frame mounted),
    throws it 90 deg from up to forward (release), then takes the leaf's opening strap above the helmet's brow and pulls it down to the chest (the
    leaf swings in). Left-handed because the two-person layout puts the partner on each crew member's right and the wall on the left.
    Every target sits below the suited shoulder limit; nothing goes over the head. 8 s."""
    hip, U, F, j0 = _restrained(H); sh = j0['shoulder_left']
    pivot = add(sh, (.05, -.36, -.12))                                        # the lever pivot: ahead of the left shoulder, a little below it
    lever = lambda a: add(pivot, (0.0, -LATCH_ARC_M*math.sin(math.radians(a)), LATCH_ARC_M*math.cos(math.radians(a))))  # from up, forward and down
    strap_hi = add(sh, (.10, -.42, .30)); strap_lo = add(j0['chest'], (.12, -.40, .02)); rest = add(j0['chest'], (.20, -.25, -.15))
    hold_r = add(j0['hip_c'], (-.06, -.32, .12))
    keys = [(0.0, rest), (1.5, lever(0.0)), (3.5, lever(90.0)), (4.5, lever(90.0)), (5.5, strap_hi), (7.0, strap_lo), (8.0, strap_lo)]
    out = []
    for i in range(8*fps):
        t = i/fps
        tgt = lever(90.0*smooth((t-1.5)/2.0)) if 1.5 <= t < 3.5 else _keyed(keys, t)
        arms = {'left': (tgt, (.4, .5, -.8)), 'right': (hold_r, (-.4, .5, -.8))}
        pose = dict(ch.STAND, head=-10.0 if t < 4.5 else 4.0); j = ch.skeleton(_fig(H), pose, hip, U, F, hands=suit_reach(H, pose, hip, U, F, arms))
        out.append(_frame(_feet(j, H, U, F), (0.0, 0.0, 0.0), ('foot_right', 'foot_left', 'hand_right')))
    return dict(frames=out, loop=False, root_motion=False, events=[(1.5, 'latch_handle'), (3.5, 'latch_released'), (5.5, 'open_strap'), (7.0, 'leaf_open')],
                handle_body=dict(pivot=list(pivot), grip_closed=list(lever(0.0)), grip_open=list(lever(90.0)), strap_high=list(strap_hi),
                                 strap_low=list(strap_lo), handhold_right=list(hold_r)))


def latch_pitch(H, mob, fps, pitch=None):
    """EVA3-002 backup only: the articulating foot restraint pitches the rigid suited body about the ankles toward the overhead hatch
    handle until the right arm reaches it straight up within the suited shoulder limit (EVA-057 measured 60 deg beyond it upright; on the
    rig the upper arm needs the smallest pitch in 5 deg steps from 60 that passes). The study tests the tilted body against the chamber
    wall and the partner. 3 s, held."""
    if pitch is None:
        for p in range(60, 95, 5):
            f = latch_pitch(H, mob, fps, float(p))['frames'][0]; tr = ch.unit(sub(f['neck'], f['hip_c']))
            sh = math.degrees(math.acos(max(-1.0, min(1.0, ch.dot(ch.unit(sub(f['elbow_right'], f['shoulder_right'])), mul(tr, -1.0))))))
            if sh <= mob['shoulder_flex_max_deg']:
                return latch_pitch(H, mob, fps, float(p))
        return latch_pitch(H, mob, fps, 90.0)
    hip0, U0, F0, _ = _restrained(H); ax = (1.0, 0.0, 0.0)
    U = ch.rot(U0, ax, -pitch); F = ch.rot(F0, ax, -pitch); hip = ch.rot(hip0, ax, -pitch)
    j0 = ch.skeleton(_fig(H), ch.STAND, hip, U, F); sh = j0['shoulder_right']
    d = (0.0, 0.0, 1.0)                                                       # straight up the chamber to the overhead handle
    reach = (ch.P['upper_arm']+ch.P['forearm'])*H*.97; target = add(sh, mul(d, reach)); out = []
    for i in range(3*fps):
        arms = {'right': (target, (-.4, .5, -.8))}
        pose = dict(ch.STAND, head=10.0); j = ch.skeleton(_fig(H), pose, hip, U, F, hands=suit_reach(H, pose, hip, U, F, arms))
        ank = {s: (sg*ch.P['hip_x']*H*1.25, 0.0, ch.P['ankle']*H) for s, sg in zip(SIDES, (-1, 1))}
        ank = {s: ch.rot(v, ax, -pitch) for s, v in ank.items()}
        out.append(_frame(hs.legs_to(j, H, ank, F, U), (0.0, 0.0, 0.0), ('foot_right', 'foot_left')))
    return dict(frames=out, loop=False, root_motion=False, pitch_deg=pitch, events=[(1.0, 'outer_hatch_handle')])


def casualty_supported(H, mob, fps):
    """EVA3-003 / EVA-058: an incapacitated suited crew member secured for transport on a full-length support (board, frame or vacuum
    mattress; the support itself is study equipment, eva_sp11.py): the supine spinal-neutral posture of a stretcher patient, body
    straight, arms along the sides, legs together; nothing bent or squeezed past the neutral range. Breathing only. 2 s loop."""
    hip, U, F, _ = _restrained(H); out = []
    for i in range(2*fps):
        w = math.sin(2*math.pi*i/(2*fps))
        arms = {s: dict(flex=2.0, abduct=6.0, elbow=12.0) for s in SIDES}
        pose = dict(ch.STAND, trunk=.5*w, head=-4.0, abduct=(2.0, 2.0), knee=(5.0, 5.0), ankle=(-5.0, -5.0), arms=arms)
        out.append(_frame(ch.skeleton(_fig(H), pose, hip, U, F), (0.0, 0.0, 0.0)))
    return dict(frames=out, loop=True, root_motion=False)


EVA_ACTIONS = ('eva_suit_check', 'eva_airlock', 'eva_translate', 'eva_body_rotate', 'eva_tether_transfer', 'eva_tool_inspect',
               'eva_guide_point', 'eva_abort_translate', 'eva_hatch_pass', 'eva_buddy_check', 'eva_casualty', 'eva_rescue_hold',
               'eva_latch_extension', 'eva_latch_pitch', 'eva_casualty_supported')
# Actions every suit asset inherits from the wearer's unsuited character rig (build/human.py, human_system.py). They are never suited EVA operations,
# whatever their coverage readback: not in eva_actions, not played as EVA, tagged NOT_SUITED_EVA in the asset (docs/ACCESSORIES.md).
SHARED_ACTIONS = {
    'idle': 'unsuited standing idle',
    'walk': 'unsuited walk in ring gravity',
    'sit': 'unsuited seated pose',
    'crawl': 'unsuited floor crawl: the head leaves the torso-fixed helmet (coverage FAIL)',
    'climb': 'unsuited ladder climb: overhead reach far past the 120 deg suit shoulder display limit; the outer layer thins under '
             'the scye bearing (instructor coverage FAIL)',
}


def actions(H, data, fps, P=None):
    """The EVA library at stature H, with the wearer's segment proportions P (human_system.proportions) while it is generated."""
    mob = data['mobility']; saved = dict(ch.P); ELBOW_LIMIT[0] = mob['elbow_max_deg']
    try:
        ch.P.update(P or {})
        return dict(eva_suit_check=suit_check(H, mob, fps), eva_airlock=airlock_cycle(H, mob, fps), eva_translate=rail_translate(H, mob, fps),
                    eva_body_rotate=body_rotate(H, mob, fps), eva_tether_transfer=tether_transfer(H, mob, fps),
                    eva_tool_inspect=tool_inspect(H, mob, fps), eva_guide_point=guide_point(H, mob, fps),
                    eva_abort_translate=rail_translate(H, mob, fps, mob['abort_speed_m_s']), eva_hatch_pass=hatch_pass(H, mob, fps),
                    eva_buddy_check=buddy_check(H, mob, fps), eva_casualty=casualty(H, mob, fps), eva_rescue_hold=rescue_hold(H, mob, fps),
                    eva_latch_extension=latch_extension(H, mob, fps), eva_latch_pitch=latch_pitch(H, mob, fps),
                    eva_casualty_supported=casualty_supported(H, mob, fps), rest=hs.rest(H))
    finally:
        ch.P.clear(); ch.P.update(saved)


def hinge(a, b, c):
    """Flexion (deg) at b of the chain a-b-c: 0 when straight."""
    u = ch.unit(sub(a, b)); w = ch.unit(sub(c, b)); return 180.0-math.degrees(math.acos(max(-1.0, min(1.0, ch.dot(u, w)))))


def mobility_report(lib, mob):
    """Largest elbow and knee flexion, shoulder flexion and head-in-helmet angle over every EVA action, against the PROTOTYPE limits."""
    out = {}
    for name in EVA_ACTIONS:
        worst = dict(elbow=0.0, knee=0.0, shoulder=0.0, head=0.0)
        for f in lib[name]['frames']:
            for s in SIDES:
                worst['elbow'] = max(worst['elbow'], hinge(f[f'shoulder_{s}'], f[f'elbow_{s}'], f[f'wrist_{s}']))
                worst['knee'] = max(worst['knee'], hinge(f[f'hip_{s}'], f[f'knee_{s}'], f[f'ankle_{s}']))
                trunk = ch.unit(sub(f['neck'], f['hip_c']))
                worst['shoulder'] = max(worst['shoulder'], math.degrees(math.acos(max(-1.0, min(1.0, ch.dot(ch.unit(sub(f[f'elbow_{s}'], f[f'shoulder_{s}'])), mul(trunk, -1.0)))))))
            body_up = ch.unit(sub(f['neck'], f['chest']))
            worst['head'] = max(worst['head'], math.degrees(math.acos(max(-1.0, min(1.0, ch.dot(ch.unit(f['head_up']), body_up))))))
        lim = dict(elbow=mob['elbow_max_deg'], knee=mob['knee_max_deg'], shoulder=mob['shoulder_flex_max_deg'], head=mob['head_in_helmet_max_deg'])
        out[name] = {k: dict(max_deg=round(v, 1), limit_deg=lim[k], ok=v <= lim[k]+1e-6) for k, v in worst.items()}
    return out


if __name__ == '__main__':
    import json
    d = load(); H = 1.70
    lib = actions(H, d, 30)
    print(json.dumps(dict(parts=len(part_ids(d)), open=[k for k, f in d['telemetry'].items() if f['value'] is None],
                          frames={k: len(lib[k]['frames']) for k in EVA_ACTIONS}, mobility=mobility_report(lib, d['mobility'])), indent=1))
