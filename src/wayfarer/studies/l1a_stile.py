"""L1-A: the built trunk ladder at Crew_Port_2_2 (X 88.95) and Crew_Refuge_Port (X 95.55), owner 2026-10-13 15!A179 (OWN-RES-D1).

NONCANON PROTOTYPE study, disposable geometry, zero canonical change: nothing in data/, no generator, no GEN_*, no saved asset (the vehicle .blend is
opened, never saved). It reuses the L1-A measurement of eva3_sp13_l1a (`--o13 l1a`: the ladder-line rule against every trunk opening, the district port
at 205-215 deg as a reversible WHITEBOX, the SP-13 exit and the A170 SP-12 choice) and its multi-carrier sweep, and tries local, non-destructive changes
of the ladder only (stile / rail / rungs / brackets): reprofile, narrowing, bracket relocation, a radial offset toward the wall and a local rotation
(joggle) of the whole ladder section, alone and combined. No trunk wall, port frame or pressure member is cut or moved; every change is PROTOTYPE.

Measured per candidate (geometry is the same in 0 g, spin, stopped and locked 1.5 g, the trunk being on the non-rotating spine):
  * every ladder member (both stiles, the arrest rail, the rungs, the stile brackets) against every opening, as the 3D distance from the member surface
    to the opening's bore cylinder carried into the trunk (for an axis-parallel line this is the eva3 signed gap); the dock mouth stays bridged;
  * grip-line continuity (no new break at margin 0), stile kink, ladder width, boot room behind the rungs;
  * ladder vs the built trunk fixtures, hoist line margins, the 1.5 g climber figure (body following the ladder) against the Crew_Port_2_2 and refuge rims;
  * pressure boundary separately: wall gap of the members and the bracket feet against the opening edges (anchor placement); no rating;
  * carriers S, A, K (two rescuers) and the suited crew member swept over the FULL trunk route, district landing X 105.3 aft past Crew_Port_2_2 to X 88.2.
Loads (tether fall, bracket and stile bending, arrester passage over a kinked rail) stay OPEN: no number is assumed.

Run: /snap/bin/blender -b --factory-startup --python src/wayfarer/studies/l1a_stile.py -- --out runs/<stamp>-l1a-stile [--parts geom,sweep,six,write]
Writes references/L1A_STILE_2026-10-13.json (+ .md written by hand from it) and, if a candidate passes, references/p1_access_seg_l1a_stile.json.
"""
from pathlib import Path
import argparse
import json
import math
import sys
import time
import numpy as np
ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT/'src/wayfarer/studies')]
import eva3_sp13_l1a as L1                     # read-only reuse (measurement rule, ctx, carriers, segment schema)
ex, h3, he, ct, cs = L1.ex, L1.h3, L1.he, L1.ct, L1.cs

TAG = 'A179-L1A-STILE'
ROUTE = 'L1-A district (A179 stile at Crew_Port_2_2)'
WIN_PAD_M = 0.25                # PROTOTYPE: the change is full over the opening's X extent +- this pad ...
RAMP_M = 0.90                   # ... and blends to the built ladder over this length (three rung pitches)
DOCK_X = 99.4
ROUTE_END_X = 88.2              # the carriers' head goes aft past Crew_Port_2_2 (X 88.45-89.45)
SIX = tuple(L1.SEEDS)+(59, 73, 97)

# candidates: drl = radial offset of the ladder section toward the wall (m; the stile chord stays 0.40 m), dth = local rotation of the whole section away
# from the port (deg), nar = near stile moved toward the ladder centre (deg), prof = stile tangential half-thickness in the window (m; flat-bar reprofile),
# brk = stile brackets inside a window moved fore/aft out of the opening band, win = windows changed ('both' or 'p22' = Crew_Port_2_2 only)
CANDS = {
    'BASE':   dict(desc='built ladder (eva3 o13 reference)'),
    'RP10':   dict(prof=0.010, desc='stile reprofiled to a flat bar 20 mm across (tangential), 35 mm deep, in both windows'),
    'NW6':    dict(nar=6.5, desc='near stile moved 6.5 deg toward the ladder centre (local narrowing) in both windows'),
    'BRK':    dict(brk=True, desc='stile brackets moved fore/aft out of the opening band (0.20 m margin) in both windows'),
    'OR3':    dict(drl=0.03, desc='ladder section offset 0.03 m outward (standoff 0.16 -> 0.13 m) in both windows'),
    'OR4':    dict(drl=0.04, desc='ladder section offset 0.04 m outward (standoff 0.16 -> 0.12 m) in both windows'),
    'JG10':   dict(dth=10.0, desc='ladder section rotated 10 deg away from the port (joggle) in both windows'),
    'JG15':   dict(dth=15.0, desc='ladder section rotated 15 deg away from the port (joggle) in both windows'),
    'CB2J6':  dict(drl=0.02, dth=6.0, desc='offset 0.02 m outward (standoff 0.14 m) + rotated 6 deg away, both windows'),
    'CB2J8':  dict(drl=0.02, dth=8.0, desc='offset 0.02 m outward (standoff 0.14 m) + rotated 8 deg away, both windows'),
    'OR4P22': dict(drl=0.04, win='p22', desc='OR4 at Crew_Port_2_2 only (refuge window left as built)'),
    'OR4DP':  dict(drl=0.04, dp=True, desc='OR4 in both windows and at the moved district port (X 104.1, on the study ladder extension)'),
    'CB2J8DP': dict(drl=0.02, dth=8.0, dp=True, desc='CB2J8 in both windows and at the moved district port (X 104.1, on the study ladder extension)'),
    'CB2J6DP': dict(drl=0.02, dth=6.0, dp=True, desc='CB2J6 in both windows and at the moved district port (X 104.1, on the study ladder extension)'),
}
SWEEP = ('BASE', 'OR4', 'CB2J6', 'CB2J8', 'OR4DP', 'CB2J6DP', 'CB2J8DP')     # carrier sweeps (the others are geometry screens only)


def W(s, c=None, alpha=None):
    """The changed windows: (name, x, angle, radius, sign) with sign = the rotation that moves the ladder away from that port (ladder at 285 deg)."""
    c = c or {}; ops = {n: (x, th, r) for n, x, th, r in he.openings(s)}
    w = [('Crew_Port_2_2', *ops['Crew_Port_2_2'], +1)]+([('Crew_Refuge_Port', *ops['Crew_Refuge_Port'], -1)] if c.get('win', 'both') == 'both' else [])
    if c.get('dp') and alpha is not None:
        w.append(('District_Port', 104.1, math.radians(alpha), 0.45, +1 if alpha < 285 else -1))
    return w


def weight(x, xc, r):
    a = r+WIN_PAD_M; d = np.abs(np.asarray(x, float)-xc)
    return np.clip(1.0-(d-a)/RAMP_M, 0.0, 1.0)


class Lad:
    """The candidate ladder as functions of X: stile / rail radius and angle, rod radii."""

    def __init__(self, s, c, alpha=None):
        self.s, self.c = s, c; L0 = he.trunk_ladder(s); h = s['human_entry']
        self.rl0, self.phi0, self.th0, self.floor, self.top = L0['rl'], L0['phi'], L0['th'], L0['floor'], L0['top']
        self.r = h['handrail_radius_m']; self.rr_rail = h['spoke_arrest_rail_radius_m']; self.halfw = h['spoke_ladder_width_m']/2
        self.tr = s['crew_transfer']['trunk_clear_radius_m']; self.pitch = h['spoke_rung_pitch_m']
        self.win = W(s, c, alpha)
        self.rungs = list(L0['rungs'])+list(np.arange(max(L0['rungs'])+self.pitch, L1.LADDER_TOP_X-0.05, self.pitch))
        nb = math.ceil((L0['top']-L0['floor']-.2)/h['trunk_bracket_pitch_m'])
        self.brackets0 = [L0['floor']+.1+(L0['top']-L0['floor']-.2)*i/nb for i in range(nb+1)]

    def w(self, x):
        """(w of the windows on the low-angle side, w of the high-angle side, w_any)."""
        z = np.zeros_like(np.asarray(x, float)); wp, wm = z.copy(), z.copy()
        for _, xc, _, r, sg in self.win:
            if sg > 0:
                wp = np.maximum(wp, weight(x, xc, r))
            else:
                wm = np.maximum(wm, weight(x, xc, r))
        return wp, wm, np.maximum(wp, wm)

    def at(self, x):
        c = self.c; x = np.asarray(x, float); w1, w2, wa = self.w(x)
        rl = self.rl0+c.get('drl', 0.0)*(w1+w2); th = self.th0+math.radians(c.get('dth', 0.0))*(w1-w2); phi = np.arcsin(self.halfw/rl)
        a = th-phi+math.radians(c.get('nar', 0.0))*w1; b = th+phi-math.radians(c.get('nar', 0.0))*w2
        half = (b-a)/2; mid = (a+b)/2; rail_r = rl*np.cos(half)-self.r-self.rr_rail
        rr = self.r-(self.r-c['prof'])*wa if c.get('prof') else np.full_like(x, self.r)
        return dict(rl=rl, a=a, b=b, mid=mid, rail_r=rail_r, rr=rr, th=th)

    def lines(self, xs):
        g = self.at(xs); P = lambda rho, ang: np.stack([xs, rho*np.cos(ang), rho*np.sin(ang)], 1)
        return {'stile_a': (P(g['rl'], g['a']), g['rr']), 'stile_b': (P(g['rl'], g['b']), g['rr']), 'rail': (P(g['rail_r'], g['mid']), np.full_like(xs, self.rr_rail))}

    def rung_pts(self, n=9):
        out = []
        for x in self.rungs:
            g = self.at(np.array([x])); A = np.array([x, g['rl'][0]*math.cos(g['a'][0]), g['rl'][0]*math.sin(g['a'][0])])
            B = np.array([x, g['rl'][0]*math.cos(g['b'][0]), g['rl'][0]*math.sin(g['b'][0])])
            out.append((x, A, B, np.array([A+(B-A)*k/(n-1) for k in range(n)])))
        return out

    def bracket_x(self):
        """Stile bracket stations per stile; 'brk' moves a near-stile bracket inside a window to the nearer edge of the band (opening r + 0.20 + 0.05)."""
        out = {'stile_a': list(self.brackets0), 'stile_b': list(self.brackets0)}
        if self.c.get('brk'):
            for nm, xc, _, r, sg in self.win:
                st = 'stile_a' if sg > 0 else 'stile_b'; band = r+0.20+0.05
                out[st] = [(xc-band if x < xc else xc+band) if abs(x-xc) < band else x for x in out[st]]
        return out

    def bracket_segs(self):
        out = []
        for st, xs_ in self.bracket_x().items():
            for x in xs_:
                g = self.at(np.array([x])); ang = g['a'][0] if st == 'stile_a' else g['b'][0]; r0 = g['rl'][0]+self.r
                out.append((st, x, np.array([[x, rho*math.cos(ang), rho*math.sin(ang)] for rho in np.linspace(r0, self.tr, 8)])))
        return out


def ops_l1a(s, alpha, Lo):
    """The o13 opening set: built openings + district port at alpha + the SP-13 exit + the A170 SP-12 choice (eva3_sp13_l1a.run_o13_l1a)."""
    e13 = Lo['sp13_exit']; q = Lo['sp12_exit']; o = [tuple(v) for v in he.openings(s)]
    o += [('District_Port', 104.1, math.radians(alpha), 0.45), ('SP13_Exit', e13['xp'], math.radians(e13['az']), e13['D']/2)]
    if q and q.get('kind') in ('oblique', 'fwd'):
        o.append(('SP12_Exit_'+q['name'], q['wall_x'], ex.AZ, q['D']/2/math.sin(math.radians(q['psi_deg']))))
    return o


def pt_gap(P, rr, ops, skip=None):
    """Least distance (m) from member points (surface = point - rr) to each opening's bore cylinder carried into the trunk; (value, opening, x)."""
    best = (math.inf, None, None); rr = np.broadcast_to(rr, (len(P),))
    for n, x, th, r in ops:
        c_, s_ = math.cos(th), math.sin(th); along = P[:, 1]*c_+P[:, 2]*s_
        perp = np.sqrt(np.maximum(P[:, 1]**2+P[:, 2]**2-along**2, 0.0)); g = np.hypot(P[:, 0]-x, perp)-r-rr
        g = np.where(along > 0, g, np.inf)
        if skip is not None:
            g = np.where(skip, np.inf, g)
        i = int(np.argmin(g))
        if g[i] < best[0]:
            best = (float(g[i]), n, float(P[i, 0]))
    return best


def dock_skip(s, ops, Lad0, xs):
    """The bridged dock window per line (as eva3: the 0.20 m-margin gap that contains X 99.4 on the built line is excluded)."""
    G = L1.ladder_geom(s, 285.0); out = {}
    for ln, (rho, ang, rr) in G['lines'].items():
        sk = [(g[0], g[1]) for g in L1.merge_gaps(L1.line_blocks(rho, ang, ops, 0.2), G['floor'], L1.LADDER_TOP_X) if g[0] <= DOCK_X <= g[1]]
        m = np.zeros_like(xs, bool)
        for a, b in sk:
            m |= (xs >= a) & (xs <= b)
        out[ln] = m
    return out


def geometry(s, c, alpha, Lo):
    """Pure geometry of one candidate at one district-port angle."""
    lad = Lad(s, c, alpha); ops = ops_l1a(s, alpha, Lo); xs = np.arange(lad.floor, L1.LADDER_TOP_X+1e-9, 0.01)
    w = lad.w(xs)[2]
    sk = dock_skip(s, ops, lad, xs); assert not np.any(w[np.any(np.stack(list(sk.values())), 0)] > 0), 'candidate window reaches the dock bridge'
    lines = lad.lines(xs); res = dict(lines={}, rungs=None, brackets=None)
    for ln, (P, rr) in lines.items():
        g = pt_gap(P, rr, ops, sk[ln]); res['lines'][ln] = dict(least_m=round(g[0], 4), opening=g[1], x=round(g[2], 2))
        # the same line against the two named windows (what the owner asked about) and against the district port only
        for nm in ('Crew_Port_2_2', 'Crew_Refuge_Port', 'District_Port'):
            q = pt_gap(P, rr, [o for o in ops if o[0] == nm], sk[ln]); res['lines'][ln][f'vs_{nm}'] = round(q[0], 4)
    skip_x = [(xs[m].min(), xs[m].max()) for m in sk.values() if m.any()]; lo_, hi_ = min(a for a, b in skip_x), max(b for a, b in skip_x)
    rg = [(x, pt_gap(pts, lad.r, ops)) for x, A, B, pts in lad.rung_pts() if not (lo_ <= x <= hi_)]
    k = min(rg, key=lambda t: t[1][0]); res['rungs'] = dict(least_m=round(k[1][0], 4), opening=k[1][1], x=round(k[0], 2))
    br = [(st, x, pt_gap(P, lad.r*.7, ops)) for st, x, P in lad.bracket_segs() if not (lo_ <= x <= hi_)]
    k = min(br, key=lambda t: t[2][0]); res['brackets'] = dict(least_m=round(k[2][0], 4), opening=k[2][1], stile=k[0], x=round(k[1], 2),
                                                               near_port_2_2=[dict(stile=st, x=round(x, 2), gap_m=round(g[0], 3)) for st, x, g in br if abs(x-88.949) < 1.0])
    # pressure boundary (separate from clearance): members stay inside the bore; bracket feet on the plain wall vs opening edges (0.20 m rule)
    feet = [(st, x, P[-1]) for st, x, P in lad.bracket_segs() if not (lo_ <= x <= hi_)]
    fg = [(st, x, pt_gap(f[None, :], lad.r*.7, ops)) for st, x, f in feet]; kf = min(fg, key=lambda t: t[2][0])
    g_ = lad.at(xs); wall_gap = float(np.min(lad.tr-(g_['rl']+g_['rr'])))
    res['pressure_boundary'] = dict(member_to_trunk_wall_min_m=round(wall_gap, 3), bracket_foot_to_opening_edge_min_m=round(kf[2][0], 3), at=dict(stile=kf[0], x=round(kf[1], 2), opening=kf[2][1]),
                                    feet_inside_0_20_band=[dict(stile=st, x=round(x, 2), opening=g[1], gap_m=round(g[0], 3)) for st, x, g in fg if g[0] < 0.20],
                                    new_penetrations=0, cut_members=0, note='no trunk-wall, port-frame or pressure-shell change; anchors re-use the plain wall; bracket-anchor and wall local loads OPEN')
    # continuity, kink, width, boot room
    allg = min(v['least_m'] for v in res['lines'].values())
    res['no_new_ladder_break'] = bool(allg > 0.0)
    lat = {ln: P[:, 1:] for ln, (P, _) in lines.items()}; kink = 0.0
    for ln, Q in lat.items():
        d = np.linalg.norm(np.diff(Q, axis=0), axis=1)/0.01; kink = max(kink, math.degrees(math.atan(float(np.max(d)))))
    chord = 2*g_['rl']*np.sin((g_['b']-g_['a'])/2); rung_centre = g_['rl']*np.cos((g_['b']-g_['a'])/2)
    res['form'] = dict(max_member_slope_deg=round(kink, 1), ladder_chord_min_m=round(float(chord.min()), 3), ladder_chord_built_m=round(2*lad.halfw, 3),
                       boot_room_behind_rung_min_m=round(float(np.min(lad.tr-rung_centre-lad.r)), 3), boot_room_built_m=round(lad.tr-lad.rl0*math.cos(lad.phi0)-lad.r, 3),
                       rail_lateral_shift_max_m=round(float(np.max(np.abs(g_['rail_r']*np.sin(g_['mid']-lad.th0)))), 3),
                       stile_unsupported_span_max_m=round(max(max(np.diff(sorted(v))) for v in lad.bracket_x().values()), 2))
    # hoist line 0.25 m @105 deg (HUM-003) vs the ladder lines, cross-section
    hc = np.array([0.25*math.cos(math.radians(105)), 0.25*math.sin(math.radians(105))]); hm = {}
    for cid, rad in (('A', math.hypot(0.275, 0.15)), ('S', h3.CARRIERS['S']['radius'])):
        hm[cid] = round(min(float(np.min(np.linalg.norm(P[:, 1:]-hc, axis=1)-rr-rad)) for P, rr in lines.values()), 3)
    res['hoist_offset_margin_m'] = hm
    res['least_ladder_m'] = round(min(allg, res['rungs']['least_m'], res['brackets']['least_m']), 3)
    return res


# ---------------------------------------------------------------------------------------------------------------------------------
# Blender parts: fixtures, climber, carriers

def tube_mesh(P, rad, n=12):
    """Vertices and quads of an open tube along a polyline (for one BVH)."""
    vs, fs = [], []
    P = np.asarray(P, float); rad = np.broadcast_to(rad, (len(P),))
    for i, p in enumerate(P):
        t = P[min(i+1, len(P)-1)]-P[max(i-1, 0)]; t = t/np.linalg.norm(t); ref = np.array([0.0, 0.0, 1.0]) if abs(t[2]) < 0.9 else np.array([1.0, 0.0, 0.0])
        u = np.cross(t, ref); u /= np.linalg.norm(u); v = np.cross(t, u)
        vs += [tuple(p+rad[i]*(math.cos(2*math.pi*k/n)*u+math.sin(2*math.pi*k/n)*v)) for k in range(n)]
    for i in range(len(P)-1):
        for k in range(n):
            a, b = i*n+k, i*n+(k+1) % n; fs.append((a, b, b+n, a+n))
    return vs, fs


def ladder_bvh(s, c, alpha):
    """The whole candidate ladder (floor to X 104.9: stiles, rail, rungs, brackets) as one BVH for the carrier sweep (replaces the built ladder records)."""
    from mathutils.bvhtree import BVHTree
    lad = Lad(s, c, alpha); xs = np.arange(lad.floor+lad.r, L1.LADDER_TOP_X+1e-9, 0.05); vs, fs = [], []
    def add(m):
        o = len(vs); vs.extend(m[0]); fs.extend(tuple(i+o for i in f) for f in m[1])
    for ln, (P, rr) in lad.lines(xs).items():
        if ln == 'rail':
            P, rr = P[xs >= lad.floor+0.2], rr[xs >= lad.floor+0.2]
        add(tube_mesh(P, rr))
    for x, A, B, pts in lad.rung_pts(n=5):
        add(tube_mesh(pts, lad.r, n=10))
    for st, x, P in lad.bracket_segs():
        add(tube_mesh(P, lad.r*.7, n=8))
    return BVHTree.FromPolygons(vs, fs), 'L1A_LADDER_CANDIDATE'


def fixture_clearance(s, c, tree_pack, alpha):
    """Candidate ladder lines and rungs vs the built trunk fixtures (handrails, lights, frames, port rails; the ladder itself excluded)."""
    from mathutils import Vector
    import bisect
    tree, names, foffs = tree_pack; lad = Lad(s, c, alpha); xs = np.arange(lad.floor, 100.0, 0.05); best = (math.inf, None, None, None)
    nm = lambda idx: names[bisect.bisect_right(foffs, idx)-1]
    items = [(ln, P, rr) for ln, (P, rr) in lad.lines(xs).items()]+[('rung', pts, np.full(len(pts), lad.r)) for x, A, B, pts in lad.rung_pts(n=5) if x < 100.0]
    for ln, P, rr in items:
        for p, q in zip(P, rr):
            loc, n, idx, dist = tree.find_nearest(Vector(p))
            if loc is not None and dist-q < best[0]:
                best = (dist-q, ln, round(float(p[0]), 2), nm(idx))
    return dict(least_m=round(best[0], 3), line=best[1], x=best[2], nearest=best[3])


def climber_vs_port_rims(s, c, alpha):
    """The 1.5 g climber figure (he.trunk_climber) moved rung by rung up the candidate ladder, its body following the local offset/rotation, against the
    rims of Crew_Port_2_2 and Crew_Refuge_Port (edges a hand or boot can catch)."""
    from mathutils import Vector
    from mathutils.kdtree import KDTree
    lad = Lad(s, c, alpha); clim = he.trunk_climber(s); out = {}
    rims = {nm: L1.port_rim(math.degrees(th) % 360, x=xc, r=r, rt=lad.tr) for nm, xc, th, r, sg in W(s, dict(dp=True), alpha)}
    for nm, rim in rims.items():
        kd = KDTree(len(rim)); [kd.insert(Vector(q), i) for i, q in enumerate(rim)]; kd.balance(); worst = (math.inf, None, None)
        for x_f in np.arange(lad.floor, L1.LADDER_TOP_X-1.6, 0.1):
            dx = x_f-clim['feet_x']
            for rn, pts, rad in clim['rods']:
                Q = np.array([np.add(pts[0], np.subtract(pts[1], pts[0])*k/6) for k in range(7)])+np.array((dx, 0, 0))
                g = lad.at(Q[:, 0]); dth = g['th']-lad.th0; drl = g['rl']-lad.rl0
                y = Q[:, 1]*np.cos(dth)-Q[:, 2]*np.sin(dth); z = Q[:, 1]*np.sin(dth)+Q[:, 2]*np.cos(dth)
                y, z = y+drl*np.cos(g['th']), z+drl*np.sin(g['th'])
                for xx, yy, zz in zip(Q[:, 0], y, z):
                    dd = kd.find(Vector((xx, yy, zz)))[2]-rad
                    if dd < worst[0]:
                        worst = (dd, rn, round(float(x_f), 2))
        out[nm] = dict(least_m=round(min(worst[0], 1.0), 3), body_part=worst[1], feet_x=worst[2], status=L1.status(worst[0]))
    return out


def sweep(ctx, s, c, alpha, Lo, seeds, label):
    """Carriers S, A, K (two rescuers) and the suited crew member over the full trunk route X 105.3 -> 88.2 with the candidate ladder."""
    import bpy
    w = s['crew_transfer']['passage_wall_m']; e13 = Lo['sp13_exit']; tro = Lo['ladder_rows'][str(int(alpha))]['port_screen']['port_tube_outer_r_m']
    port = lambda: h3.prim_cyl(ct.radial(104.1, 0.60, math.radians(alpha)), ct.radial(104.1, tro, math.radians(alpha)), 0.45)
    obj, tree = ex.build_free(s, ctx.data, [port, L1.exit_solid(e13)], [], ex.TRUNK_EXT_X, sp12=False, sp13=False, ref=True, fit=False)
    walls = L1.WallsPlus(ctx.fx_noladder, ctx.pts_full, free=tree, extra=ladder_bvh(s, c, alpha))
    route = [('E', (105.3, 0.0, 0.0)), ('E', (104.1, 0.0, 0.0)), ('T', (101.0, 0.0, 0.0)), ('T', (97.0, 0.0, 0.0)), ('T', (ROUTE_END_X, 0.0, 0.0))]
    cars = L1.carriers(ctx); row = {}; t0 = time.time()
    for cid in ('S', 'A', 'K', 'U'):
        per = [h3.sweep_route(walls, cars[cid], route, np.random.default_rng(sdv), staff=(cid != 'U')) for sdv in seeds]
        body = [r['least_m'] for r in per]; stf = [r['staff_least_m'] for r in per if r['staff_least_m'] is not None]; k = int(np.argmin(body)); least = min(body+stf)
        row[cid] = dict(least_m=round(least, 3), body_least_m=min(body), rescuers_least_m=min(stf) if stf else None, status=L1.status(least), nearest=per[k]['nearest'],
                        zone=per[k]['zone'], at_m=per[k]['at_m'], rescuer_nearest=[r['staff_nearest'] for r in per], seed_spread_m=[round(min(body+stf), 3), round(max(body+stf), 3)])
        print('WF_L1A_STILE carriers', label, alpha, cid, row[cid]['least_m'], body, stf, row[cid]['nearest'], flush=True)
    row['seeds'] = list(seeds); row['seconds'] = round(time.time()-t0)
    bpy.data.objects.remove(obj)
    return row


def load_ctx():
    ctx = L1.load_ctx(); recs = cs.scene(ctx.s, cs.load_inspect(), 1.0)
    ctx.fx_noladder = h3.fixtures(recs, drop=lambda q: 'Ladder' in q['name'] or 'Arrest_Rail' in q['name'])
    ctx.pts_full = [(x_, y, z) for x_ in np.linspace(86.5, 107.5, 43) for y in (-3, 0, 3) for z in (-3, 0, 3)]
    ctx.tp = L1.fixture_tree(recs)
    return ctx


# ---------------------------------------------------------------------------------------------------------------------------------

def whole_route(G, F, CL, Lo, CR, al):
    """Every measured element for one port angle; the port-tube items are imported unchanged from references/p1_eva_sp13_l1a.json (owner_2026_10_13.l1a)."""
    k = str(int(al)); o = Lo['whole_route'][k]['items']
    items = {'stiles + arrest rail vs every opening (candidate ladder, whole length)': min(v['least_m'] for v in G['lines'].values()),
             'rungs vs every opening': G['rungs']['least_m'], 'stile brackets vs every opening': G['brackets']['least_m'],
             'moved port edge vs ladder': min(v['vs_District_Port'] for v in G['lines'].values()),
             'ladder vs trunk fixtures': F['least_m'],
             'climber (1.5 g pose, following the ladder) vs moved district port rim': CL['District_Port']['least_m'],
             'climber (1.5 g pose, following the ladder) vs Crew_Port_2_2 rim': CL['Crew_Port_2_2']['least_m'],
             'climber (1.5 g pose, following the ladder) vs Crew_Refuge_Port rim': CL['Crew_Refuge_Port']['least_m'],
             'hoist line 0.25 m @105 deg, A vs ladder rods': G['hoist_offset_margin_m']['A'], 'hoist line, S vs ladder rods': G['hoist_offset_margin_m']['S'],
             'port tube vs SP-13 exit solid [o13, unchanged]': o['port tube vs SP-13 exit solid']}
    if 'port tube vs SP-12 exit solid' in o:
        items['port tube vs SP-12 exit solid [o13, unchanged]'] = o['port tube vs SP-12 exit solid']
    if CR is not None:
        for cid in ('S', 'A', 'K', 'U'):
            items[f'carrier {cid} full trunk route X 105.3 -> {ROUTE_END_X}' + (' with rescuers' if cid != 'U' else ' (suited crew, self-propelled)')] = CR[cid]['least_m']
    kk = min(items, key=items.get); ok = G['no_new_ladder_break'] and Lo['pressure_boundary'][k]['status'] == 'CLEAR'
    st = L1.status(items[kk]) if ok else 'FAIL'
    return dict(items=items, least_m=round(items[kk], 3), limiting=kk, status=st, carriers_swept=CR is not None,
                passes=bool(st == 'PASS' and CR is not None))


def segments(R):
    out = []; ALL = list(L1.ALL_STATES)
    for cn, r in R['candidates'].items():
        wr = {al: w for al, w in r.get('whole_route', {}).items() if w['carriers_swept']}
        if not any(w['passes'] for w in wr.values()):
            continue
        for al, w in wr.items():
            base = f'{TAG}-{cn}-PORT{al}'
            out.append(L1.seg(f'{base}-ROUTE', ROUTE, ALL, f'PROTOTYPE {cn}: {r["desc"]}; district port {al} deg (reversible WHITEBOX), ladder 285 deg',
                              'whole route: minimum over every measured element', w['least_m'], list(w['items']), None, w['limiting'],
                              f'no new ladder break: {r["geometry"][al]["no_new_ladder_break"]}; pressure boundary untouched (no cut, no new penetration); loads OPEN. {L1.STATES_NOTE}.', w['status']))
            for i_, (it, val) in enumerate(w['items'].items()):
                out.append(L1.seg(f'{base}-E{i_:02d}', ROUTE, ALL, f'{cn}, port {al} deg', it, val, [it], None, None, 'element of the whole-route minimum.'))
        out.append(L1.seg(f'{TAG}-{cn}-LOADS', ROUTE, ALL, cn, 'stile/rail/bracket load path, tether fall load, arrester passage over the local offset', None, [], None, None,
                          'OPEN: no load, stiffness or arrest number assumed.', 'OPEN'))
    return out


def evaluate(R, Lo):
    for cn, r in R['candidates'].items():
        if 'blend' not in r:
            continue
        r['whole_route'] = {}
        for k in r['geometry']:
            cr = (r.get('carriers') or {}).get(k)
            if cr and r.get('recheck_6_seeds', {}).get(k):          # the six-seed result replaces the three-seed one where it is lower
                six = r['recheck_6_seeds'][k]; cr = {cid: (six[cid] if six[cid]['least_m'] < cr[cid]['least_m'] else cr[cid]) for cid in ('S', 'A', 'K', 'U')}
            r['whole_route'][k] = whole_route(r['geometry'][k], r['blend'][k]['fixtures'], r['blend'][k]['climber'], Lo, cr, float(k))


def main(out, parts):
    out.mkdir(parents=True, exist_ok=True); jf = out/'l1a_stile.json'
    R = json.loads(jf.read_text()) if jf.exists() else dict(candidates={})
    Lo = json.loads((ROOT/'references/p1_eva_sp13_l1a.json').read_text())[L1.O13_TAG]['l1a']
    from spec import load
    s = load(ROOT)[0]; save = lambda: jf.write_text(json.dumps(R, indent=1, default=str)+'\n')
    if 'geom' in parts:
        for cn, c in CANDS.items():
            G = {str(int(al)): geometry(s, c, al, Lo) for al in L1.PORT_ALPHAS}
            R['candidates'].setdefault(cn, {}).update(desc=c['desc'], params={k: v for k, v in c.items() if k != 'desc'}, geometry=G)
            print('WF_L1A_STILE geom', cn, {al: g['least_ladder_m'] for al, g in G.items()}, G['210']['form'], flush=True)
        save()
    ctx = None
    if any(p in parts for p in ('blend', 'sweep', 'six')):
        ctx = load_ctx()
    if 'blend' in parts:
        for cn, c in CANDS.items():
            r = R['candidates'][cn]; r['blend'] = {str(int(al)): dict(fixtures=fixture_clearance(s, c, ctx.tp, al), climber=climber_vs_port_rims(s, c, al)) for al in L1.PORT_ALPHAS}
            print('WF_L1A_STILE blend', cn, {k: (v['fixtures']['least_m'], {n: q['least_m'] for n, q in v['climber'].items()}) for k, v in r['blend'].items()}, flush=True)
        save()
    # carriers over the full route: the built ladder at every angle, the SWEEP candidates where the ladder geometry clears 0.05 m; three seeds
    if 'sweep' in parts:
        for cn in SWEEP:
            r = R['candidates'][cn]; r.setdefault('carriers', {})
            for al in L1.PORT_ALPHAS:
                k = str(int(al))
                if k in r['carriers'] or not (cn == 'BASE' or r['geometry'][k]['least_ladder_m'] >= L1.MARGIN):
                    continue
                r['carriers'][k] = sweep(ctx, s, CANDS[cn], al, Lo, L1.SEEDS, cn); save()
    evaluate(R, Lo)
    # six-seed recheck of every passing (candidate, angle)
    if 'six' in parts:
        for cn, r in R['candidates'].items():
            for k, w in r.get('whole_route', {}).items():
                if w['passes'] and k not in r.setdefault('recheck_6_seeds', {}):
                    r['recheck_6_seeds'][k] = sweep(ctx, s, CANDS[cn], float(k), Lo, SIX, cn+'_6SEEDS'); save()
        evaluate(R, Lo)
    ok = {(cn, k): w['least_m'] for cn, r in R['candidates'].items() for k, w in r.get('whole_route', {}).items() if w['passes']}
    R['passing'] = sorted(f'{cn}@{k}' for cn, k in ok)
    R['best'] = (lambda b: dict(candidate=b[0], port_deg=b[1], least_m=ok[b]))(max(ok, key=ok.get)) if ok else None
    save()
    if 'write' in parts:
        R.update(study='L1-A Crew_Port_2_2 / refuge-port stile study (owner 2026-10-13 15!A179 OWN-RES-D1), NONCANON PROTOTYPE, disposable geometry',
                 owner_refs=['15!A179 OWN-RES-D1-2026-10-13', '15!A171 DIST-L1-STEP'], band=L1.BAND, seeds=list(L1.SEEDS), seeds_recheck=list(SIX), run=str(out.relative_to(ROOT)),
                 window=dict(pad_m=WIN_PAD_M, ramp_m=RAMP_M), route=f'district landing X 105.3 -> trunk X {ROUTE_END_X} (past Crew_Port_2_2), carriers S, A, K with two rescuers, suited crew U',
                 states=list(L1.ALL_STATES), states_note=L1.STATES_NOTE,
                 loads=dict(status='OPEN', note='tether fall load, stile/bracket/anchor loads, arrester passage over a kinked rail: no number assumed'))
        (ROOT/'references/L1A_STILE_2026-10-13.json').write_text(json.dumps(R, indent=1, default=str)+'\n')
        segs = segments(R)
        if segs:
            (ROOT/'references/p1_access_seg_l1a_stile.json').write_text(json.dumps(dict(
                study='A179 L1-A stile / bracket at Crew_Port_2_2 and Crew_Refuge_Port (owner 2026-10-13 15!A179 OWN-RES-D1), NONCANON PROTOTYPE',
                source=['src/wayfarer/studies/l1a_stile.py', 'references/L1A_STILE_2026-10-13.json', 'references/p1_eva_sp13_l1a.json'], segments=segs), indent=1)+'\n')
        print('WF_L1A_STILE written', len(segs), 'segments', [g['id'] for g in segs if g['id'].endswith('-ROUTE')], flush=True)


if __name__ == '__main__':
    argv = sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
    ap = argparse.ArgumentParser(); ap.add_argument('--out', type=Path, required=True); ap.add_argument('--parts', default='geom,blend,sweep,six,write')
    a = ap.parse_args(argv); o = a.out if a.out.is_absolute() else ROOT/a.out
    main(o, a.parts.split(','))
