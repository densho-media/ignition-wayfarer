"""IND-001 / HUM-001 zones 6-8 (phase 2): the human-scale whitebox of the ring sectors, in the sector frame of habitat_interior
(origin on the centreline at the deck, +X axial with the aft bulkhead at -X, +Y radially outward, which is down in coast, +Z tangential).

[interior.layouts] blocks are functional envelopes: a berth with its clear space, a couch with its occupant, a compartment. shapes() depicts each
as whitebox furniture, figures() places the review mannequins and check() screens a function's layout at human scale for both gravity vectors:
the radial floor in coast (rings spinning, ~0.5 g) and aft down with the rings stopped and locked for major thrust (habitat.interior_orientation).
It also reports how much of the function's 12A program fits ([sector_whitebox.program]). Every dimension is a PROTOTYPE review selection
([sector_whitebox]), not anthropometric canon. Standard library only.

    python3 src/wayfarer/sector_whitebox.py [FUNCTION]
"""
from pathlib import Path
import json
import math
import sys
import habitat_interior as hi
import habitat_ring


MATTRESS_M = 0.08    # PROTOTYPE: the treatment couch's mattress on its medical_table_m top (characters.couch lays the patient on it)


def extent(b, k):
    return b['max'][k]-b['min'][k]


def face(b):
    """A block's open (service) face: 'inner' toward the aisle ('aisle' in the data: on it), 'outer', 'fore' or 'aft'."""
    return {'aisle': 'inner'}.get(b['open'], b['open'])


def facing(b):
    """Unit vector from the open face out into the space in front of it."""
    return {'fore': (1, 0, 0), 'aft': (-1, 0, 0), 'inner': (0, 0, -b['side']), 'outer': (0, 0, b['side'])}[face(b)]


def depth(b):
    """Extent of a block away from its open face."""
    return extent(b, 0 if face(b) in ('fore', 'aft') else 2)


def access_strip(s, b):
    """The access_width_min_m strip in front of a block's open face, deck to overhead, or None when that face is on the aisle. A fore or aft
    strip runs from the aisle to the block's outer edge, so it opens onto the aisle."""
    i, sec, d = s['interior'], hi.section(s), s['sector_whitebox']['access_width_min_m']
    lo, hi_ = list(b['min']), list(b['max']); lo[1], hi_[1] = sec['ceiling_y_m'], sec['deck_y_m']; f = face(b)
    if f in ('fore', 'aft'):
        lo[0], hi_[0] = (b['min'][0]-d, b['min'][0]) if f == 'aft' else (b['max'][0], b['max'][0]+d)
        lo[2], hi_[2] = (i['aisle_m']/2, b['max'][2]) if b['side'] > 0 else (b['min'][2], -i['aisle_m']/2)
    else:
        n = facing(b)[2]; edge = b['max'][2] if n > 0 else b['min'][2]
        if f == 'inner' and abs(abs(edge)-i['aisle_m']/2) < 1e-6:
            return None
        lo[2], hi_[2] = sorted((edge, edge+n*d))
    return dict(min=tuple(lo), max=tuple(hi_))


def clear_volumes(s, function):
    """RT-006: the walkable clear space of a sector, as overlapping boxes (name, kind, min, max, suited_access) in the sector frame, deck to overhead:
    the aisle and the landing well, each block's access strip (access_strip) and each couch's free strip, each berth's space above its
    platform, and Seraph's niche. suited_access says whether the 0.70 m suited envelope fits its narrow side; false is shirt-sleeve-only
    maintenance access, not suited egress or repair passage (SERV-STRIPS-2026-10-10, 15!A119). A runtime
    keeps a camera or a body inside their union; they are clear of the blocks by construction, not swept."""
    import human_entry as he
    i, sec, w = s['interior'], hi.section(s), s['sector_whitebox']; L = he.landing(s); xl = sec['length_m']/2-i['end_allowance_m']
    y0, y1 = sec['ceiling_y_m'], sec['deck_y_m']; a = i['aisle_m']/2; R = s['human_entry']['mannequin']['suited_envelope_diameter_m']
    out = [dict(name='Aisle', kind='aisle', min=(-xl, y0, -a), max=(xl, y1, a)),
           dict(name='Landing_Well', kind='landing', min=(L['well_x'][0], y0, L['well_z'][0]), max=(L['well_x'][1], y1, L['well_z'][1]))]
    blocks = hi.zones(s, function)
    for b in blocks:
        st = access_strip(s, b)
        if st:
            out.append(dict(name=f"{b['name']}_Strip", kind='access strip', min=st['min'], max=st['max']))
        if b['zone'] == 'burn_couch':
            out.append(dict(name=f"{b['name']}_Free_Strip", kind='couch strip', min=(b['max'][0], y0, b['min'][2]), max=(b['max'][0]+w['couch_front_clear_m'], y1, b['max'][2])))
        if b['zone'] == 'bunk':
            p, t = w['platform_m'], w['panel_m']
            out.append(dict(name=f"{b['name']}_Space", kind='berth', min=(b['min'][0]+t, b['min'][1]+t, b['min'][2]+t), max=(b['max'][0]-t, b['max'][1]-p, b['max'][2]-t)))
    rf = s.get('route_fitout', {})
    if rf.get('seraph_spaces', {}).get(function) == 'niche':
        lk = next(b for b in blocks if b['name'] == 'Couch_Lockers_2'); x0, x1 = rf['seraph_niche_x_m']
        out.append(dict(name='Seraph_Niche', kind='niche', min=(x0, -rf['seraph_niche_height_m']+.03, lk['min'][2]), max=(x1-.02, y1, lk['max'][2])))
    # A strip that runs into another block (the stowage under an end-opening berth column, whose strip is the inner column) is no clear volume.
    def hits(q, b):
        return all(min(q['max'][k], b['max'][k])-max(q['min'][k], b['min'][k]) > .01 for k in range(3))
    out = [q for q in out if q['kind'] in ('berth', 'niche') or not any(hits(q, b) for b in blocks)]
    for q in out:
        q['suited_access'] = min(q['max'][k]-q['min'][k] for k in (0, 2)) >= R-1e-9 and q['max'][1]-q['min'][1] >= s['prototype']['human_height_m']
    return out


def garden_tiers(s, b):
    """Tray surface heights above a Garden rack's bottom: from the reservoir top at the tier pitch, each with a full pitch of growing room."""
    w = s['sector_whitebox']; base, pitch = w['garden_tier_base_m'], w['garden_tier_pitch_m']
    return [base+k*pitch for k in range(int((extent(b, 1)-base)/pitch+1e-9))]


def stack(b, blocks):
    """The berths stacked with berth b (the same footprint and open face), bottom first."""
    return sorted((q for q in blocks if q['zone'] == 'bunk' and q['open'] == b['open'] and q['min'][0] == b['min'][0] and q['max'][0] == b['max'][0]
                   and q['min'][2] == b['min'][2]), key=lambda q: -q['max'][1])


def berth_steps(s, b, blocks):
    """Steps of berth b's stack when its top platform is above step_free_max_m: rung heights (above the deck) and whether b carries one. Each
    berth below the top carries a rung across the near end of its opening, halfway up from its platform to the next, so the climb from the deck
    is platform edge, rung, platform edge, rung, top platform; every berth of the stack carries a grab bar beside the rungs."""
    w = s['sector_whitebox']; tops = [-q['max'][1]+w['platform_m'] for q in stack(b, blocks)]
    if not tops or tops[-1] <= w['step_free_max_m']:
        return []
    return [(a+c)/2 for a, c in zip(tops, tops[1:])]


def shapes(s, b, blocks=()):
    """Whitebox parts of block b, each a box (name, zone, part, min, max) in the sector frame; together they fill the block's bounds. A berth is its
    mattress platform, a lid and thin panels on every vertical face but the open one; given its function's blocks, a berth in a stack that needs
    steps (berth_steps) also carries a rung and a grab bar recessed in the near end of its opening (the foot end, or the aisle side of an end
    opening), and an end-opening berth carries a footboard, the floor that holds its sleeper aft down; a burn couch a backrest on the aft bulkhead, a foot
    plate, a headrest, two bolsters, a five-point harness and a burn-go console on each armrest; a Garden rack a reservoir base, trays with
    their crop, a lid (lights, ducts) and panels on the back and ends; a mess (common) a booth, benches with backs along both long sides and
    the table between; a treatment couch (medical) a pedestal table with a mattress and a foot plate at its aft end; a work bench (workshop,
    laboratory) a top over a cabinet, a tool wall and a shelf; an operations row standing desks with displays (served from the aisle) or a
    seated console on the outer side with a chair per station; anything else stays a solid block."""
    w = s['sector_whitebox']; (x0, y0, z0), (x1, y1, z1) = b['min'], b['max']        # y0 is the top (up is -Y), y1 the bottom
    box = lambda part, lo, hi: dict(name=f"{b['name']}_{part}", zone=b['zone'], part=part, min=lo, max=hi)

    def slab(k, at_max, th, top=y0, bottom=y1):
        lo, hi_ = [x0, top, z0], [x1, bottom, z1]
        if at_max:
            lo[k] = hi_[k]-th
        else:
            hi_[k] = lo[k]+th
        return tuple(lo), tuple(hi_)
    if b['zone'] == 'bunk':
        p, t = w['platform_m'], w['panel_m']
        faces = {'aft': ((x0, y0, z0), (x0+t, y1, z1)), 'fore': ((x1-t, y0, z0), (x1, y1, z1)),
                 'inner': ((x0, y0, z0), (x1, y1, z0+t)) if b['side'] > 0 else ((x0, y0, z1-t), (x1, y1, z1)),
                 'outer': ((x0, y0, z1-t), (x1, y1, z1)) if b['side'] > 0 else ((x0, y0, z0), (x1, y1, z0+t))}
        shut = {'aisle': 'inner'}.get(b['open'], b['open'])
        out = [box('Platform', (x0, y1-p, z0), (x1, y1, z1)), box('Lid', (x0, y0, z0), (x1, y0+t, z1))]+[
            box(f'Panel_{k.title()}', *v) for k, v in faces.items() if k != shut]
        # FUT-003 S004 look: a reading light recessed in the lid across the berth near the head (the closed end of the long axis, as the
        # 'berth' review figure lies), its lens berth_light_m[1] proud of the lid.
        ax = 0 if extent(b, 0) >= extent(b, 2) else 2; head = {'fore': -1, 'aft': 1}.get(b['open'], 1) if ax == 0 else b['side']
        d, proud = w['berth_light_m']; at = (x1 if head > 0 else x0) if ax == 0 else (z1 if head > 0 else z0)
        a0, a1 = sorted((at-head*w['berth_light_head_m'], at-head*(w['berth_light_head_m']+d)))
        lo, hi_ = [x0+.10, y0+t-.008, z0+.10], [x1-.10, y0+t+proud, z1-.10]; lo[ax], hi_[ax] = a0, a1
        out.append(box('Reading_Light', tuple(lo), tuple(hi_)))
        if shut in ('fore', 'aft'):
            out.append(box('Footboard', (x0, y1-p-w['berth_footboard_m'], z0+t), (x0+t, y1-p, z1-t)) if shut == 'aft' else
                       box('Footboard', (x1-t, y1-p-w['berth_footboard_m'], z0+t), (x1, y1-p, z1-t)))
        rungs = berth_steps(s, b, blocks)
        if rungs:
            # Across the opening: n is the opening's axis and its plane, the recess goes into the berth; u runs along the opening from its
            # near end (aft for a side opening, the aisle side for an end opening).
            n, plane, into = (2, z0, 1) if (shut == 'inner') == (b['side'] > 0) else (2, z1, -1)
            if shut in ('fore', 'aft'):
                n, plane, into = (0, x0, 1) if shut == 'aft' else (0, x1, -1)
            u = 2-n; near, along = ((x0+t, 1) if u == 0 else ((z0+t, 1) if b['side'] > 0 else (z1-t, -1)))
            def part(name, a, c, top, bottom):
                lo, hi_ = [0.0, top, 0.0], [0.0, bottom, 0.0]; lo[n], hi_[n] = sorted((plane+into*.04, plane+into*(.04+t)))
                lo[u], hi_[u] = sorted((near+along*a, near+along*c)); return box(name, tuple(lo), tuple(hi_))
            rw = w['berth_rung_width_m']; mine = [h for h in rungs if -y1 < h < -y0]
            out += [part('Step_Rung', 0.0, rw, -h, -h+t) for h in mine]
            out.append(part('Grab_Bar', rw, rw+t, y0+t, y1-p))
        return out
    if b['zone'] == 'burn_couch':
        # The back and the foot plate (stood on in coast) span the envelope, so the parts' bounds are the block's.
        # The harness lies on the backrest; each armrest console is under the hand of an arm hanging at the side (heights above the foot plate).
        k = w['couch_back_m']; zc = (z0+z1)/2; H = s['prototype']['human_height_m']; f = y1-.03; c0, c1 = w['couch_console_m']
        return [box('Back', (x0, y0, z0), (x0+k, y1, z1)), box('Foot', (x0+k, f, z0+.04), (x1, y1, z1-.04)),
                box('Headrest', (x0+k, y1-H-.12, zc-.16), (x0+k+.14, y1-H+.20, zc+.16)),
                box('Bolster_1', (x0+k, y1-.75*H, z0+.04), (x0+k+.22, y1-.50*H, z0+.10)),
                box('Bolster_2', (x0+k, y1-.75*H, z1-.10), (x0+k+.22, y1-.50*H, z1-.04)),
                box('Console_1', (x0+k, f-c1, z0+.02), (x1-.02, f-c0, z0+.12)), box('Console_2', (x0+k, f-c1, z1-.12), (x1-.02, f-c0, z1-.02)),
                box('Strap_1', (x0+k, f-.78*H, zc-.13), (x0+k+.01, f-.52*H, zc-.08)), box('Strap_2', (x0+k, f-.78*H, zc+.08), (x0+k+.01, f-.52*H, zc+.13)),
                box('Lap_Belt', (x0+k, f-.53*H, zc-.20), (x0+k+.01, f-.50*H, zc+.20))]
    if b['zone'] == 'garden':
        t, ax = w['panel_m'], (0 if face(b) in ('fore', 'aft') else 2); other = 2-ax
        out = [box('Base', (x0, y1-w['garden_tier_base_m'], z0), (x1, y1, z1)), box('Lid', (x0, y0, z0), (x1, y0+.05, z1)),
               box('Back', *slab(ax, facing(b)[ax] < 0, t)), box('End_1', *slab(other, False, t)), box('End_2', *slab(other, True, t))]
        for k, h in enumerate(garden_tiers(s, b)):
            if k:
                out.append(box(f'Tray_{k}', (x0, y1-h, z0), (x1, y1-h+.04, z1)))
            out.append(box(f'Crop_{k}', (x0+.06, y1-h-.24, z0+.06), (x1-.06, y1-h, z1-.06)))
        return out
    if b['zone'] == 'common':
        L = 0 if extent(b, 0) >= extent(b, 2) else 2; S = 2-L; k, sh, th = w['bench_m'], w['seat_height_m'], w['table_height_m']
        s0, s1 = b['min'][S], b['max'][S]; c = [(b['min'][j]+b['max'][j])/2 for j in range(3)]

        def band(a, e, top, bottom):
            lo, hi_ = [x0, top, z0], [x1, bottom, z1]; lo[S], hi_[S] = a, e; return tuple(lo), tuple(hi_)
        leg = [c[0]-.06, y1-th+.04, c[2]-.06], [c[0]+.06, y1, c[2]+.06]
        return [box('Seat_1', *band(s0, s0+k, y1-sh, y1)), box('Back_1', *band(s0, s0+.06, y0, y1-sh)),
                box('Seat_2', *band(s1-k, s1, y1-sh, y1)), box('Back_2', *band(s1-.06, s1, y0, y1-sh)),
                box('Table', *band(s0+k, s1-k, y1-th, y1-th+.04)), box('Pedestal', tuple(leg[0]), tuple(leg[1]))]
    c = [(b['min'][j]+b['max'][j])/2 for j in range(3)]
    if b['zone'] == 'medical':
        th = w['medical_table_m']; L = 0 if extent(b, 0) >= extent(b, 2) else 2; half = [.10, 0, .10]; half[L] = .45
        return [box('Top', (x0, y1-th, z0), (x1, y1-th+.06, z1)), box('Mattress', (x0+.03, y1-th-MATTRESS_M, z0+.03), (x1-.03, y1-th, z1-.03)),
                box('Pedestal', (c[0]-half[0], y1-th+.06, c[2]-half[2]), (c[0]+half[0], y1, c[2]+half[2])), box('Foot', *slab(L, False, .03))]
    if b['zone'] in ('workshop', 'laboratory'):
        n = facing(b); ax = 0 if n[0] else 2; bh = w['bench_height_m']; back = n[ax] < 0
        cab = list(slab(ax, back, depth(b)-.08, y1-bh+.04, y1))
        return [box('Top', (x0, y1-bh, z0), (x1, y1-bh+.04, z1)), box('Cabinet', *cab), box('Tool_Wall', *slab(ax, back, .03, y0, y1-bh)),
                box('Shelf', *slab(ax, back, .30, y1-bh-.64, y1-bh-.60))]
    if b['zone'] == 'operations':
        L = 0 if extent(b, 0) >= extent(b, 2) else 2; S = 2-L
        if face(b) == 'inner':
            # Standing desks served from the aisle, displays on the back edge.
            n = facing(b); back = n[S] < 0; dh = w['standing_console_m']
            return [box('Desk', *slab(S, back, depth(b), y1-dh, y1-dh+.04)), box('Cabinet', *slab(S, back, depth(b)-.08, y1-dh+.04, y1)),
                    box('Display', *slab(S, back, .05, y0, y1-dh))]
        # Seated stations: the console on the outer side, a chair per station in front of it and a floor mat under them.
        out_max = b['side'] > 0 if S == 2 else True; cd, th = w['console_depth_m'], w['table_height_m']
        edge = (b['max'][S]-cd) if out_max else (b['min'][S]+cd); toward = 1 if out_max else -1
        # The display stands display_setback_m behind the desk's front edge, not on the wall, to bring it within reading distance.
        disp = list(slab(S, out_max, .05, y0, y1-th)); lo, hi_ = list(disp[0]), list(disp[1])
        lo[S], hi_[S] = sorted((edge+toward*w['display_setback_m'], edge+toward*(w['display_setback_m']+.05)))
        parts = [box('Desk', *slab(S, out_max, cd, y1-th, y1-th+.04)), box('Cabinet', *slab(S, out_max, .25, y1-th+.04, y1)),
                 box('Display', tuple(lo), tuple(hi_)), box('Mat', *slab(1, True, .01))]
        for j in range(int(extent(b, L)/w['station_width_m']+1e-9)):
            m = b['min'][L]+(j+.5)*w['station_width_m']; sc = edge-toward*.35
            lo, hi_ = [0, y1-w['seat_height_m'], 0], [0, y1-.01, 0]; lo[L], hi_[L] = m-.22, m+.22; lo[S], hi_[S] = sorted((sc-.22, sc+.22))
            parts.append(box(f'Chair_{j+1}', tuple(lo), tuple(hi_)))
            lo, hi_ = list(lo), list(hi_); lo[1], hi_[1] = y1-.95, y1-w['seat_height_m']; lo[S], hi_[S] = sorted((sc-toward*.22, sc-toward*.16))
            parts.append(box(f'Chair_Back_{j+1}', tuple(lo), tuple(hi_)))
        return parts
    return [dict(name=b['name'], zone=b['zone'], part='', min=b['min'], max=b['max'])]


def rods(at, H, arms):
    """A generic standing-posture mannequin as rods (name, points, radius) through at(x, y, z): x across the body, y toward the face, z up from
    the soles; arms maps a name to the hand point."""
    shoulder = at(0, 0, .75*H)
    out = [('Torso', [at(0, 0, .38*H), at(0, 0, .78*H)], .13), ('Head', [at(0, 0, H-.20), at(0, 0, H-.11)], .11)]
    out += [(f'Arm_{n}', [shoulder, p], .055) for n, p in arms.items()]
    out += [(f'Leg_{sg}', [at(sg*.13, 0, .07), at(0, 0, .40*H)], .07) for sg in (-1, 1)]
    return out, shoulder


def figures(s, blocks):
    """Review mannequins (non-canon scale guides) in the sector frame: 'aisle' stands on the deck at the centre of the aisle beside the berths
    of side +1 (or the first berth's side), facing them, one hand on the top berth's platform edge; 'berth' lies on its back in the middle tier
    of that stack, head at the closed end of the long axis; 'couch' stands in the first burn couch, back on the backrest, facing fore, the
    pose that is supine aft-down under thrust, one hand on the belt buckle and one on its armrest console; 'garden' stands 0.20 m off the
    first Garden rack's service face, a hand on the top tray's centre; 'seated' sits at the aft end of the mess bench nearer the aisle, facing
    the table; 'operator' sits at the first crew station of the first operations row (the first station that is not Seraph's post,
    [route_fitout] seraph_station; or stands at it, served from the aisle); 'patient' lies on
    the first treatment couch, feet at its aft end, and 'medic' stands at its open face, a hand on the patient's chest. Returns
    {pose: dict(rods, eye, reach, block, outside)}; outside marks a figure standing beside its block rather than in it."""
    H = s['prototype']['human_height_m']; w = s['sector_whitebox']; out = {}
    bunks = sorted([b for b in blocks if b['zone'] == 'bunk'], key=lambda b: (-b['side'], abs(b['min'][2]), b['max'][1]))
    if bunks:
        side = bunks[0]['side']; stack = [b for b in bunks if b['min'][0] == bunks[0]['min'][0] and b['min'][2] == bunks[0]['min'][2]]
        stack.sort(key=lambda b: -b['max'][1]); top = stack[-1]; mid = stack[len(stack)//2]
        xm = (top['min'][0]+top['max'][0])/2; edge = (xm, top['max'][1]-w['platform_m'], top['min'][2] if side > 0 else top['max'][2])
        at = lambda x, y, z: (xm-side*x, -z, side*(y+.12))      # facing +side, 0.12 m off the aisle centre
        r, sh = rods(at, H, {'Reach': edge, 'Low': at(.25, .12, .45*H)})
        out['aisle'] = dict(rods=r, eye=at(0, .08, s['human_entry']['mannequin']['eye_height_m']), reach={'top_berth_edge_m': math.dist(sh, edge)}, block=top['name'],
                            outside=True)
        # Lying on the platform of the middle tier along the berth's long axis, head at the end away from the opening (or aft).
        (x0, y0, z0), (x1, y1, z1) = mid['min'], mid['max']; ax = 0 if extent(mid, 0) >= extent(mid, 2) else 2
        c = ((x0+x1)/2, y1-w['platform_m']-.13, (z0+z1)/2); L = (x1-x0) if ax == 0 else (z1-z0)
        sign = {'fore': -1, 'aft': 1}.get(mid['open'], 1) if ax == 0 else side    # +1: the head toward +axis (closed ends: feet aft)
        def lie(t, up=0.0):
            p = list(c); p[ax] += sign*(t-H/2); p[1] -= up; return tuple(p)
        r = [('Torso', [lie(.38*H), lie(.78*H)], .13), ('Head', [lie(H-.20), lie(H-.11)], .11),
             ('Leg_1', [lie(.07), lie(.40*H)], .07), ('Arm_1', [lie(.75*H), lie(.45*H, .12)], .055)]
        out['berth'] = dict(rods=r, eye=lie(H-.12, .08), reach={}, block=mid['name'], axis='X' if ax == 0 else 'Z', head=sign, length_m=L)
    couches = [b for b in blocks if b['zone'] == 'burn_couch']
    if couches:
        b = couches[0]; zc = (b['min'][2]+b['max'][2])/2; xb = b['min'][0]+w['couch_back_m']+.13+.01
        at = lambda x, y, z: (xb+y, -z, zc-x)                    # facing fore (+X), back on the backrest
        con = next(q for q in shapes(s, b) if q['part'] == 'Console_1'); key = tuple((con['min'][k]+con['max'][k])/2 for k in (0, 2))
        key = (key[0], con['min'][1]-.02, key[1])                 # the hand rests on the console top
        r, sh = rods(at, H, {'Belt': at(-.08, .20, .62*H), 'Console': key})
        out['couch'] = dict(rods=r, eye=at(0, .08, s['human_entry']['mannequin']['eye_height_m']), block=b['name'],
                            reach={'belt_m': math.dist(sh, at(-.08, .20, .62*H)), 'console_m': math.dist(sh, key)})
    up = (0, -1, 0)

    def frame(foot, f):
        a = (-f[2], 0, f[0])                                     # across the body
        return lambda x, y, z: tuple(foot[k]+x*a[k]+y*f[k]+z*up[k] for k in range(3))

    def sit(at, sh_y, th):
        # Seated at a table or desk of height th in front of the figure (+y), hips over the seat centre; returns rods and the shoulder.
        shoulder = at(0, -.03, sh_y+.55)
        r = [('Torso', [at(0, -.04, sh_y+.12), at(0, -.04, sh_y+.58)], .13), ('Head', [at(0, -.02, sh_y+.74), at(0, -.02, sh_y+.83)], .11)]
        for k, sg in ((1, -1), (2, 1)):
            r += [(f'Thigh_{k}', [at(sg*.10, -.02, sh_y+.08), at(sg*.10, .40, sh_y+.10)], .07), (f'Shin_{k}', [at(sg*.10, .40, sh_y+.10), at(sg*.10, .45, .07)], .055),
                  (f'Arm_{k}', [shoulder, at(sg*.18, .45, th+.03)], .055)]
        return r, shoulder

    def stand_at(b, height, frac):
        # Standing service_standoff_m off the open face of b at its middle, facing it; the target point frac of its depth in, at height.
        n = facing(b); ax = 0 if n[0] else 2; at_face = b['max'][ax] if n[ax] > 0 else b['min'][ax]
        c = [(b['min'][k]+b['max'][k])/2 for k in range(3)]; foot = list(c); foot[1] = b['max'][1]; foot[ax] = at_face+n[ax]*w['service_standoff_m']
        target = list(c); target[1] = b['max'][1]-height; target[ax] = at_face-n[ax]*depth(b)*frac
        return frame(foot, tuple(-v for v in n)), tuple(target)
    garden = sorted((b for b in blocks if b['zone'] == 'garden'), key=lambda b: b['name'])
    if garden:
        b = garden[0]; n = facing(b); ax = 0 if n[0] else 2; d = depth(b); top = garden_tiers(s, b)[-1]
        at_face = b['max'][ax] if n[ax] > 0 else b['min'][ax]; c = [(b['min'][k]+b['max'][k])/2 for k in range(3)]
        foot = list(c); foot[1] = b['max'][1]; foot[ax] = at_face+n[ax]*w['service_standoff_m']
        at = frame(foot, tuple(-v for v in n))
        tray, back = list(c), list(c); tray[1] = back[1] = b['max'][1]-top-.10; tray[ax] = at_face-n[ax]*d/2; back[ax] = at_face-n[ax]*(d-.02)
        r, sh = rods(at, H, {'Reach': tuple(tray), 'Low': at(.25, .12, .45*H)})
        out['garden'] = dict(rods=r, eye=at(0, .08, s['human_entry']['mannequin']['eye_height_m']), block=b['name'], outside=True,
                             reach={'top_tray_centre_m': math.dist(sh, tray), 'top_tray_back_m': math.dist(sh, back)})
    mess = [b for b in blocks if b['zone'] == 'common']
    if mess:
        b = mess[0]; L = 0 if extent(b, 0) >= extent(b, 2) else 2; S = 2-L; sh_y, th = w['seat_height_m'], w['table_height_m']
        f = (0, 0, b['side']) if S == 2 else (1, 0, 0)          # from the bench nearer the aisle (or the aft one) toward the table
        near = (b['min'][2] if b['side'] > 0 else b['max'][2]) if S == 2 else b['min'][0]
        foot = [0.0, b['max'][1], 0.0]; foot[S] = near+f[S]*w['bench_m']/2; foot[L] = b['min'][L]+w['seat_width_m']/2
        at = frame(foot, f); r, shoulder = sit(at, sh_y, th)
        out['seated'] = dict(rods=r, eye=at(0, .06, sh_y+.77), reach={'table_m': math.dist(shoulder, at(0, .45, th+.03))}, block=b['name'])
    ops = [b for b in blocks if b['zone'] == 'operations']
    if ops:
        b = ops[0]; L = 0 if extent(b, 0) >= extent(b, 2) else 2; S = 2-L; eye = s['human_entry']['mannequin']['eye_height_m']
        if face(b) == 'inner':
            at, desk = stand_at(b, w['standing_console_m']+.02, .35)
            r, sh = rods(at, H, {'Desk': desk, 'Low': at(.25, .12, .45*H)})
            out['operator'] = dict(rods=r, eye=at(0, .08, eye), reach={'desk_m': math.dist(sh, desk)}, block=b['name'], outside=True)
        else:
            out_max = b['side'] > 0 if S == 2 else True; toward = 1 if out_max else -1
            edge = (b['max'][S]-w['console_depth_m']) if out_max else (b['min'][S]+w['console_depth_m'])
            rf = s.get('route_fitout', {}); post = rf.get('seraph_station', 0) if rf.get('seraph_spaces', {}).get('WORK_MEDICAL_OPS') == 'post' else 0
            j = 1 if post == 1 else 0                                # IND-001 3.2: the first station that is not Seraph's
            foot = [0.0, b['max'][1], 0.0]; foot[S] = edge-toward*.35; foot[L] = b['min'][L]+(j+.5)*w['station_width_m']
            f = [0, 0, 0]; f[S] = toward; at = frame(foot, tuple(f)); r, shoulder = sit(at, w['seat_height_m'], w['table_height_m'])
            display = at(0, .35+w['display_setback_m'], w['table_height_m']+.35)
            out['operator'] = dict(rods=r, eye=at(0, .06, w['seat_height_m']+.77), block=b['name'],
                                   reach={'desk_m': math.dist(shoulder, at(0, .45, w['table_height_m']+.03)), 'display_eye_m': math.dist(at(0, .06, w['seat_height_m']+.77), display)})
    med = [b for b in blocks if b['zone'] == 'medical']
    if med:
        b = med[0]; ax = 0 if extent(b, 0) >= extent(b, 2) else 2; (x0, y0, z0), (x1, y1, z1) = b['min'], b['max']
        c = [(x0+x1)/2, y1-w['medical_table_m']-MATTRESS_M-.13, (z0+z1)/2]; start = b['min'][ax]+.04     # feet at the aft (or first) end
        def lie(t, up=0.0):
            p = list(c); p[ax] = start+t; p[1] -= up; return tuple(p)
        r = [('Torso', [lie(.38*H), lie(.78*H)], .13), ('Head', [lie(H-.20), lie(H-.11)], .11), ('Leg_1', [lie(.07), lie(.40*H)], .07),
             ('Arm_1', [lie(.75*H), lie(.45*H, .12)], .055)]
        out['patient'] = dict(rods=r, eye=lie(H-.12, .08), reach={}, block=b['name'])
        at, _ = stand_at(b, w['medical_table_m'], .5); chest = lie(.70*H, .13)
        foot = list(at(0, 0, 0)); foot[ax] = chest[ax]; n = facing(b); at = frame(foot, tuple(-v for v in n))
        r, sh = rods(at, H, {'Chest': chest, 'Low': at(.25, .12, .45*H)})
        out['medic'] = dict(rods=r, eye=at(0, .08, s['human_entry']['mannequin']['eye_height_m']), reach={'patient_chest_m': math.dist(sh, chest)},
                            block=b['name'], outside=True)
    return out


def box_gap(b, p):
    return math.sqrt(sum(max(b['min'][i]-p[i], 0.0, p[i]-b['max'][i])**2 for i in range(3)))


def inside(b, p, r):
    return all(b['min'][i]+r-1e-9 <= p[i] <= b['max'][i]-r+1e-9 for i in range(3))


def check(s, function):
    """Human-scale screen of one function's layout (PROTOTYPE): berths (length, width, clear height, the access strip in front of the open
    face, steps, the axis against the spin axis, what holds a sleeper aft-down), burn couches (width, height, the free strip in front),
    hygiene floor and height, standing headroom in the aisle, racks and benches served from one face (depth, the strip in front, reach to the
    top tray, which way the worker faces against the spin axis), the mess seats, operations stations, treatment couches (size, the medic's
    strip, aft down), the burn-go console reach, the mannequins inside their envelopes and clear of every other block,
    the 12A program fit and volume, and the Garden's rack volume against the owner's per-ring share (Q50). The envelope rules (walls, overlaps, aft couches, counts) stay in habitat_interior.check."""
    w, i, sec = s['sector_whitebox'], s['interior'], hi.section(s); blocks = hi.zones(s, function); failures = []
    fail = lambda ok, message: ok or failures.append(message)
    H = s['prototype']['human_height_m']; x_lim = sec['length_m']/2-i['end_allowance_m']; tol = 1e-6
    free = lambda box, skip=(): not [b['name'] for b in blocks if b['name'] not in skip and hi.overlap(b, box)]
    berths = {}

    def rise(b, platform):
        # The highest step from the deck to the platform over the rungs and the platform edges below it.
        h = sorted({0.0, platform}|{x for x in berth_steps(s, b, blocks)+[-q['max'][1]+w['platform_m'] for q in stack(b, blocks)] if x < platform})
        return max(c-a for a, c in zip(h, h[1:]))
    for b in [b for b in blocks if b['zone'] == 'bunk']:
        ax = 0 if extent(b, 0) >= extent(b, 2) else 2; length, width = extent(b, ax), extent(b, 2 if ax == 0 else 0)
        clear = extent(b, 1)-w['platform_m']-w['panel_m']; platform = -b['max'][1]+w['platform_m']
        strip = access_strip(s, b)
        aft_closed = b['open'] != 'aft'
        berths[b['name']] = dict(axis='X' if ax == 0 else 'Z', length_m=length, width_m=width, clear_m=clear, platform_m=platform, open=b['open'],
                                 access_clear=strip is None or (free(strip) and -x_lim-tol <= strip['min'][0] and strip['max'][0] <= x_lim+tol),
                                 steps_needed=platform > w['step_free_max_m'], step_rungs_m=berth_steps(s, b, blocks), step_rise_max_m=rise(b, platform),
                                 # Rolling over turns the head about the body's long axis; across the spin axis that is a cross-coupled stimulus.
                                 roll_cross_coupled=ax != 0,
                                 # Aft down: a sleeper along X stands on the aft end (if closed); across, they fall sideways to the aft panel.
                                 aft_down=('feet on the closed aft end' if aft_closed else 'feet on the footboard across the open aft end') if ax == 0
                                 else f'falls {extent(b, 0)-.30:.2f} m sideways onto the aft panel')
        fail(length >= w['berth_length_min_m']-tol and width >= w['berth_width_min_m']-tol and clear >= w['berth_clear_min_m']-tol,
             f"{b['name']}: berth {length:.2f} x {width:.2f} m, {clear:.2f} m clear")
        fail(berths[b['name']]['access_clear'], f"{b['name']}: no clear {w['access_width_min_m']} m access strip at its open face")
        fail(not berths[b['name']]['steps_needed'] or berths[b['name']]['step_rise_max_m'] <= w['step_free_max_m']/2+tol,
             f"{b['name']}: {berths[b['name']]['step_rise_max_m']:.2f} m step to its {platform:.2f} m platform")
    couches = {}
    for b in [b for b in blocks if b['zone'] == 'burn_couch']:
        front = dict(min=(b['max'][0], sec['ceiling_y_m'], b['min'][2]), max=(b['max'][0]+w['couch_front_clear_m'], sec['deck_y_m'], b['max'][2]))
        couches[b['name']] = dict(width_m=extent(b, 2), height_m=extent(b, 1), depth_m=extent(b, 0), front_clear=free(front))
        fail(extent(b, 2) >= w['couch_width_min_m']-tol and extent(b, 1) >= H+.10-tol, f"{b['name']}: couch {extent(b, 2):.2f} m wide, {extent(b, 1):.2f} m tall")
        fail(couches[b['name']]['front_clear'], f"{b['name']}: the {w['couch_front_clear_m']} m in front of the couch is not free")
    hygiene = {b['name']: dict(floor_m=sorted((extent(b, 0), extent(b, 2))), height_m=extent(b, 1)) for b in blocks if b['zone'] == 'hygiene'}
    for n, h in hygiene.items():
        fail(all(a >= m-tol for a, m in zip(h['floor_m'], sorted(w['hygiene_floor_min_m']))) and h['height_m'] >= w['standing_headroom_m']-tol,
             f"{n}: hygiene floor {h['floor_m']} m, {h['height_m']:.2f} m tall")
    fail(sec['headroom_m'] >= w['standing_headroom_m'], f"Aisle headroom {sec['headroom_m']:.2f} m")
    reach, off, shoulder = s['human_entry']['mannequin']['reach_m'], w['service_standoff_m'], .75*H; racks = {}
    for b in [b for b in blocks if b['zone'] in ('garden', 'life_support', 'workshop', 'laboratory')]:
        n, d, strip = facing(b), depth(b), access_strip(s, b)
        r = dict(zone=b['zone'], face=face(b), depth_m=d, access_clear=strip is None or free(strip),
                 # Nodding while working at a face across the spin axis (facing fore or aft) is a cross-coupled (Coriolis) stimulus.
                 worker_faces='tangential' if n[2] else 'axial', nod_cross_coupled=not n[2],
                 reach_top_m=shoulder+math.sqrt(max(reach**2-(off+d/2)**2, 0.0)))
        if b['zone'] == 'garden':
            tiers = garden_tiers(s, b)
            # Aft down, a tray's water and substrate run to its aft edge: trays are closed and partitioned along X.
            r.update(tiers=len(tiers), tray_heights_m=tiers, growing_m2=len(tiers)*extent(b, 0)*extent(b, 2), aft_down_run_m=extent(b, 0),
                     top_tray_reach_m=math.hypot(off+d/2, tiers[-1]+.10-shoulder))
            fail(r['top_tray_reach_m'] <= reach+tol, f"{b['name']}: top tray centre {r['top_tray_reach_m']:.2f} m from the shoulder")
        fail(d <= w['service_depth_max_m']+tol, f"{b['name']}: {d:.2f} m deep, served from one face")
        fail(r['access_clear'], f"{b['name']}: no clear {w['access_width_min_m']} m strip at its {face(b)} face")
        racks[b['name']] = r
    seats_needed = math.ceil(s['crew']['rated_occupancy']['value']/habitat_ring.ring_count(s)); mess = {}
    for b in [b for b in blocks if b['zone'] == 'common']:
        L = 0 if extent(b, 0) >= extent(b, 2) else 2; strip = access_strip(s, b)
        mess[b['name']] = dict(seats=2*int(extent(b, L)/w['seat_width_m']+1e-9), seats_needed=seats_needed, table_m=extent(b, 2-L)-2*w['bench_m'],
                               # Diners nod over their plates: facing tangentially (benches along the spin axis) that is about the spin axis.
                               diners_face='tangential' if L == 0 else 'axial', access_clear=strip is None or free(strip))
        fail(mess[b['name']]['seats'] >= seats_needed, f"{b['name']}: {mess[b['name']]['seats']} seats for {seats_needed}")
        fail(mess[b['name']]['access_clear'], f"{b['name']}: no clear {w['access_width_min_m']} m strip at its {face(b)} end")
    ops = {}
    for b in [b for b in blocks if b['zone'] == 'operations']:
        L = 0 if extent(b, 0) >= extent(b, 2) else 2; strip = access_strip(s, b); standing = face(b) == 'inner'
        ops[b['name']] = dict(stations=int(extent(b, L)/w['station_width_m']+1e-9), standing=standing, access_clear=strip is None or free(strip),
                              # Operators nod at their displays: facing tangentially (a row along the spin axis) that is about the spin axis.
                              operators_face='tangential' if L == 0 else 'axial')
        fail(ops[b['name']]['stations'] >= 1 and ops[b['name']]['access_clear'], f"{b['name']}: {ops[b['name']]['stations']} stations, access clear: {ops[b['name']]['access_clear']}")
        fail(standing or extent(b, 2-L) >= w['console_depth_m']+.70-tol, f"{b['name']}: too shallow for a console and seats")
    medical = {}
    for b in [b for b in blocks if b['zone'] == 'medical']:
        ax = 0 if extent(b, 0) >= extent(b, 2) else 2; strip = access_strip(s, b)
        medical[b['name']] = dict(axis='X' if ax == 0 else 'Z', length_m=extent(b, ax), width_m=extent(b, 2-ax), access_clear=strip is None or free(strip),
                                  medic_faces='tangential' if facing(b)[2] else 'axial',
                                  # Aft down a patient along X stands on the foot plate (+Gz, not the couches' chest-to-back load).
                                  aft_down='the patient stands on the aft foot plate (+Gz): move patients to a burn couch before a burn' if ax == 0
                                  else 'the patient falls sideways onto the aft side')
        fail(extent(b, ax) >= w['berth_length_min_m']-tol and extent(b, 2-ax) >= w['couch_width_min_m']-tol, f"{b['name']}: treatment couch {extent(b, ax):.2f} x {extent(b, 2-ax):.2f} m")
        fail(medical[b['name']]['access_clear'], f"{b['name']}: no clear {w['access_width_min_m']} m strip at its {face(b)} face")
    figs = figures(s, blocks); posed = {}
    for pose, fg in figs.items():
        own = next(b for b in blocks if b['name'] == fg['block'])
        samples = lambda keep: [(p, r) for n, ps, r in fg['rods'] if keep(n) for p in (tuple(ps[0][k]+(ps[1][k]-ps[0][k])*j/6 for k in range(3)) for j in range(7))]
        others = [b for b in blocks if b['name'] != fg['block']]
        gap = min(box_gap(b, p)-r for b in others for p, r in samples(lambda n: True))
        # The body (not the arms) lies or stands inside its own berth or couch.
        held = fg.get('outside', False) or all(inside(own, p, r*.5) for p, r in samples(lambda n: not n.startswith('Arm')))
        posed[pose] = dict(block=fg['block'], clear_of_others_m=gap, reach_m=fg['reach'], body_inside=held)
        fail(gap >= -tol and held, f"Mannequin '{pose}': {gap:.3f} m from other blocks, body inside its own: {held}")
    fail('couch' not in figs or figs['couch']['reach']['belt_m'] <= reach, 'Couch occupant cannot reach the belt')
    # Burn-go consoles: aft down the arms lie on the armrests, so the consoles need no lift against the load, only this reach.
    burn_console = dict(heights_m=w['couch_console_m'], reach_m=figs['couch']['reach']['console_m']) if 'couch' in figs else {}
    fail(not burn_console or burn_console['reach_m'] <= reach+tol, 'Couch occupant cannot reach the burn-go console')
    for pose in ('operator', 'medic'):
        if pose in figs:
            fail(max(figs[pose]['reach'].get(k, 0.0) for k in ('desk_m', 'patient_chest_m')) <= reach+tol, f"Mannequin '{pose}' cannot reach its work")
    fail('operator' not in figs or figs['operator']['reach'].get('display_eye_m', 0.0) <= w['display_eye_max_m']+tol, 'Station display too far from the eye')
    vol = lambda zs: sum(hi.volume(b) for b in blocks if b['zone'] in zs)
    program = [dict(q, fitted=sum(1 for b in blocks if b['zone'] in q['zones']), volume_m3=vol(q['zones'])) for q in s['sector_whitebox']['program'].get(function, [])]
    occupied = sum(hi.volume(b) for b in blocks)
    floor = sum(extent(b, 0)*extent(b, 2) for b in blocks if b['max'][1] >= -tol)
    # Q50: 12!A7 gives 80 m3 for the Garden in both rings. Read as rack (growing) volume, the ring's racks are this share of it; read as the
    # usable volume of the two life-support/Garden/common sectors, it is the whole sector and the racks are their share of that.
    ring = sum(hi.volume(b) for f in s['habitat']['layout']['functions'] for b in hi.zones(s, f) if b['zone'] == 'garden')
    per_ring = s['habitat']['layout']['garden_m3']/habitat_ring.ring_count(s)
    garden = dict(racks_m3=vol(['garden']), growing_m2=sum(r.get('growing_m2', 0.0) for r in racks.values()), ring_racks_m3=ring,
                  owner_per_ring_m3=per_ring, ring_share_as_racks=ring/per_ring, sector_share=vol(['garden'])/sec['usable_m3'])
    return dict(status='PROTOTYPE_WHITEBOX_NOT_CANON', function=function, passed=not failures, failures=failures, berths=berths, couches=couches,
                hygiene=hygiene, racks=racks, mess=mess, operations=ops, medical=medical, burn_console=burn_console, garden=garden, mannequins=posed, program=program,
                program_fitted=[q['sp'] for q in program if q['fitted'] >= q['need']], program_missing=[q['sp'] for q in program if q['fitted'] < q['need']],
                envelope_m3=occupied, usable_m3=sec['usable_m3'], free_m3=sec['usable_m3']-occupied,
                deck_m2=sec['length_m']*sec['deck_width_m'], deck_covered_m2=floor, spin_rpm=habitat_ring.omega(s)*60/(2*math.pi))


if __name__ == '__main__':
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from spec import load
    s, *_ = load()
    for fn in sys.argv[1:] or s['habitat']['layout']['functions']:
        r = check(s, fn)
        print(json.dumps(r, indent=1, default=float))
