"""Ring B in-sector care + refuge-in-place study (owner answer S&E 15_MODEL_INTERFACES!A169, 2026-10-13, PREFERRED STUDY / MEDICAL, PRESSURE,
RADIATION CERTIFICATION OPEN; decision log 98!A104). NONCANON DISPOSABLE STUDY: nothing here changes data/, a generator or a saved asset. The
garden-sector fit-out swap and the fold-down couch exist only in memory (zone blocks and the evaluated Blender records of the built model, which
is opened read-only and never saved).

Owner direction: prefer REVERSIBLE distributed in-sector medical stabilisation + protected refuge-in-place over a destructive 1.6 m ring B
transfer port (no ring B pressure cutout); a fold-down garden-sector care couch with Garden_Rack_1 / Mess displaced in PROTOTYPE only; ring A's
central rescue path kept as the comparator. Verify every sector-state worst case (1.5 g and a lost ring; patient, kit, attendants); define the
sustained local atmosphere and shelter access; the 20 g/cm2 SPE target is study only. No credit for the 80 t water distribution, the 4.1 t
shelter, 25.1 g/cm2 or a one-ring stop; both-ring stop stays the working constraint; GCR protection is not implied. Mass, shield and closure
budgets stay OPEN.

Layers (status bands of access_integrated: PASS >= 0.05 m, MARGINAL 0..0.05, FAIL < 0; never widened):
  screen   zone-block fit screen of every sector (ringb_unified.distributed's geometry conventions), deck frame (0 g / spin / stopped) and aft frame
           (locked 1.5 g): care station (care point + kit + two attendants), patient transfer station (carrier beside the care point + two
           rescuers), attendant reach and egress past the deployed care station to every other station (widest-path bottleneck, 0.60 m body),
           stowed-couch egress; the garden couch placement is searched inside the footprint Garden_Rack_1 and the Mess give up.
  sweep    Blender, the built model with the swap applied in memory: hum003_routes' worst-case carrier sweep (ringb_unified.survey's method: classes
           A/C/K/S, x1.00/x1.08, doors 1.00/0.90, seeds, six pose families with wobbles, two inline rescuers) from the sector hatch through the
           landing to the transfer position beside the care point, then the sideways slide onto it as explicit poses; deck frame and an aft-frame
           (locked 1.5 g) geometry route to each burn couch. Station check: the two attendants (capsules) and the kit against the built meshes.
  ringa    Blender: ring A's central chain re-run with ringb_unified.survey's worst-case method on the built model (replaces the single-seed
           built_A quote for the comparator).

    python3 src/wayfarer/studies/ringb_insector_care.py run [--workers 16] [--only <substr>]     # all Blender jobs, in parallel
    /snap/bin/blender -b --factory-startup --python src/wayfarer/studies/ringb_insector_care.py -- screen
    /snap/bin/blender -b --factory-startup --python src/wayfarer/studies/ringb_insector_care.py -- sweep --sector B3 --frame deck --carrier S
    /snap/bin/blender -b --factory-startup --python src/wayfarer/studies/ringb_insector_care.py -- station
    /snap/bin/blender -b --factory-startup --python src/wayfarer/studies/ringb_insector_care.py -- ringa --route A1 --carrier K
    python3 src/wayfarer/studies/ringb_insector_care.py collect     # references/p1_ringb_insector_care.json, p1_access_seg_ringb_care.json, the .md

Owner 2026-10-13, S&E 15!A173:A175 (a1 1.5 g handling aids, a2 local care-point changes, a3 ring A comparator); needs the run above:
    python3 src/wayfarer/studies/ringb_insector_care.py o13run [--workers 12] [--only <substr>]   # plane screens, a2 plane options, mesh jobs
    /snap/bin/blender -b --factory-startup --python src/wayfarer/studies/ringb_insector_care.py -- o13screen --fn HABITATION
    /snap/bin/blender -b --factory-startup --python src/wayfarer/studies/ringb_insector_care.py -- o13sweep --sector B2 --variant V1 --couch Burn_Couch_2 --carrier S
    /snap/bin/blender -b --factory-startup --python src/wayfarer/studies/ringb_insector_care.py -- o13care --sector B2 --option fold_foot --carrier A
    python3 src/wayfarer/studies/ringb_insector_care.py o13collect  # p1_ringb_insector_care_o13.json, |o13- segments, the report section
WF_SPEC_ROOT=<dir with data/> reads the parameters from a snapshot while another session edits data/ (geometry inputs must be identical).
"""
from pathlib import Path
import argparse
import json
import math
import re
import subprocess
import sys
import time
ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT/'src/wayfarer'), str(ROOT/'src/wayfarer/build'), str(ROOT/'src/wayfarer/studies'), str(ROOT/'tools')]
BLENDER = '/snap/bin/blender'
RUN = ROOT/'runs/20261013T1515Z-ringb-insector-care'
OUT_JSON = ROOT/'references/p1_ringb_insector_care.json'
SEG_JSON = ROOT/'references/p1_access_seg_ringb_care.json'
OUT_MD = ROOT/'references/RINGB_INSECTOR_CARE_2026-10-13.md'

GARDEN = 'LIFE_SUPPORT_GARDEN_COMMON'
SWAP = ('Garden_Rack_1', 'Mess')                 # PROTOTYPE fit-out swap (15!A169): these blocks give their deck to the fold-down couch
STUDY_MARGIN_M = 0.05
CAP_M = 0.30                                     # zone screen: gaps are searched up to this value ("at least")
STATES = ('0g', 'spin', 'stopped', 'locked_1.5g')
SECTORS = {f'{t}{k}': (j, k) for j, t in ((1, 'A'), (2, 'B')) for k in (1, 2, 3)}
CARRIER_IDS = 'ACKS'
SCALES = (1.0, 1.08)
HAB_OWN = ('Bunk_Base_1', 'Bunk_2', 'Bunk_3')    # the berth's own structure (ringb_unified.EXISTING)


def couch_spec(s):
    """The PROTOTYPE fold-down couch, from envelopes the rescue studies already use (no new physical numbers)."""
    import ringb_unified as ru
    import hum003_routes as hr
    c = ru.CARE
    return dict(length_m=c['couch'][0], width_m=c['couch'][1], top_m=s['sector_whitebox']['medical_table_m'],
                stowed_depth_m=hr.CARRIERS['A']['size'][2], stowed_top_m=s['sector_whitebox']['medical_table_m']+c['couch'][1],
                attendant_w_m=c['attendant_w'], head_end_m=c['head_end'], stand_h_m=c['stand_h'], kneel_h_m=c['kneel_h'], walk_w_m=c['walk_w'],
                kit_m=list(hr.CARRIERS['K']['kit']), patient_t_m=hr.CARRIERS['A']['size'][2],
                provenance={'length_m, width_m': 'ringb_unified.CARE couch 2.00 x 0.70 (PROTOTYPE care envelope)',
                            'top_m': 'sector_whitebox.medical_table_m (the built treatment couch height; = CARE thick_deck 0.80)',
                            'stowed_depth_m': 'PROTOTYPE stand-in: hum003 carrier A litter depth 0.30 m (no couch mechanism is sourced)',
                            'stowed_top_m': 'top_m + width_m: the top panel folded up about its wall-side hinge at couch height',
                            'attendant_w_m, head_end_m, stand_h_m, kneel_h_m, walk_w_m': 'ringb_unified.CARE (PROTOTYPE)',
                            'kit_m': 'hum003 carrier K kit box (monitor, oxygen, suction) 0.60 x 0.55 x 0.15 (PROTOTYPE)',
                            'patient_t_m': 'hum003 carrier A depth (the patient + litter under the kit)'})


def carriers_plan():
    """Plan envelopes (length, width, thickness) of every carrier class and body size (hum003_routes.CARRIERS, scaled as SIM-027)."""
    import hum003_routes as hr
    out = {}
    for cid in CARRIER_IDS:
        c = hr.CARRIERS[cid]
        for k in SCALES:
            if c['shape'] == 'box':
                L, W, T = c['size']
            else:
                L, W, T = c['length'], 2*c['radius'], 2*c['radius']
            out[f'{cid} x{k:.2f}'] = (L*k, W*k, T*k)
    return out


# ------------------------------------------------------------------------------------------------------------------------------------
# zone-block screen (Blender's numpy)

def _gap(a, b):
    g = [max(a[0][k]-b[1][k], b[0][k]-a[1][k]) for k in range(3)]
    if max(g) < 0:
        return max(g)
    return math.sqrt(sum(max(0.0, x)**2 for x in g))


class Plane:
    """One sector's floor plane in one frame. deck: u = x (sector length), v = z, h = -y above the deck. aft (locked 1.5 g, aft down): u = y
    (radial, the overhead at ceil, the deck at 0), v = z, h = x above the aft skin. Obstacles: the zone blocks, the landing well / ladder
    keep-outs (ringb_unified.distributed) and any extra boxes."""

    def __init__(self, s, fn, frame, drop=(), extra=()):
        import habitat_interior as hi
        import human_entry as he
        sec = hi.section(s); self.L = L = he.landing(s); skin = s['habitat_ring']['sector_skin_m']; wall = s['interior']['wall_allowance_m']
        ln = sec['length_m']; self.xlo, self.xhi = -ln/2+skin, ln/2-skin; self.ceil = ceil = sec['ceiling_y_m']; self.frame = frame
        self.half = lambda y: hi.wall_half_width(s, y)-wall
        self.blocks = [b for b in hi.zones(s, fn) if b['name'] not in drop]
        ts = he.thrust_step(s)
        if frame == 'deck':          # the landing well / ladder column under the hatch (ringb_unified.distributed)
            keep = [((L['well_x'][0], ceil, min(L['well_z'][0], L['chase_z'][0])), (L['well_x'][1], 0.0, max(L['well_z'][1], L['chase_z'][1])), 'landing_well'),
                    ((L['stile_x'][0]-.1, ceil, L['stile_z']-.1), (L['stile_x'][1]+.1, 0.0, L['stile_z']+.1), 'landing_ladder')]
        else:                        # aft down: the deck-frame well column is a horizontal prism, not a floor keep-out; the Q47 step ladder is
            keep = [((ts['x'][0]-.05, ts['y']-.1, ts['stile_z'][0]-.1), (ts['x'][1]+.05, ts['y']+.1, ts['stile_z'][1]+.1), 'thrust_step_ladder')]
        boxes = [(tuple(b['min']), tuple(b['max']), b['name']) for b in self.blocks]+keep+list(extra)
        self.rects = [self.P(lo, hi_)+(n,) for lo, hi_, n in boxes]
        self.urng = (self.xlo, self.xhi) if frame == 'deck' else (ceil, 0.0)
        self.start_hint = ((L['well_x'][0]+L['well_x'][1])/2, (L['well_z'][0]+L['well_z'][1])/2) if frame == 'deck' else (ts['y']+0.35, ts['z'])      # on the room side of the Q47 step ladder

    def P(self, lo, hi_):
        if self.frame == 'deck':
            return (lo[0], hi_[0], lo[2], hi_[2], -hi_[1], -lo[1])
        return (lo[1], hi_[1], lo[2], hi_[2], lo[0]-self.xlo, hi_[0]-self.xlo)

    def zhalf(self, u0, u1, h):
        return self.half(-h) if self.frame == 'deck' else min(self.half(u0), self.half(u1))

    def clearance(self, env, exclude=()):
        """env: [(u0, u1, v0, v1, h0, h1, label)] -> (least gap, nearest, env label), capped at CAP_M; side/end walls count only if poked through."""
        best = (CAP_M, None, None)
        for e in env:
            for r in self.rects:
                if r[6] in exclude:
                    continue
                g = _gap(((e[0], e[2], e[4]), (e[1], e[3], e[5])), ((r[0], r[2], r[4]), (r[1], r[3], r[5])))
                if g < best[0]:
                    best = (g, r[6], e[6])
            zh = self.zhalf(e[0], e[1], e[5])
            for g, n in ((e[0]-self.urng[0], 'end_wall'), (self.urng[1]-e[1], 'end_wall'), (e[2]+zh, 'side_wall'), (zh-e[3], 'side_wall')):
                if g < -1e-9 and g < best[0]:
                    best = (g, n, e[6])
        return best

    def field(self, env=(), exclude=(), grid=0.02, stand_h=1.90):
        """Distance (m) from each floor cell to the nearest obstacle a standing body column (0.05..stand_h) meets: blocks, keep-outs, env boxes,
        side walls (at the floor) and end walls."""
        import numpy as np
        us = np.arange(self.urng[0], self.urng[1]+1e-9, grid); vs = np.arange(-2.8, 2.8+1e-9, grid)
        U, V = np.meshgrid(us, vs, indexing='ij'); d = np.full(U.shape, 9.0)
        for r in list(self.rects)+[tuple(e) for e in env]:
            if r[6] in exclude or r[6] == 'landing_well' or not (r[5] > 0.05 and r[4] < stand_h):
                continue
            du = np.maximum(np.maximum(r[0]-U, U-r[1]), 0.0); dv = np.maximum(np.maximum(r[2]-V, V-r[3]), 0.0)
            d = np.minimum(d, np.hypot(du, dv))
        d = np.minimum(d, np.minimum(U-self.urng[0], self.urng[1]-U))
        zh = np.array([self.zhalf(u, u, 0.0) for u in us])[:, None]
        d = np.minimum(d, zh-np.abs(V)); d[d < 0] = 0.0
        return us, vs, d

    def widest(self, fld, start):
        """Bottleneck (maximin) distance from the start cell to every cell over 4-connected paths."""
        import heapq
        import numpy as np
        us, vs, d = fld; n, m = d.shape; B = np.full(d.shape, -1.0); i0 = int(np.argmin(abs(us-start[0]))); j0 = int(np.argmin(abs(vs-start[1])))
        B[i0, j0] = d[i0, j0]; h = [(-B[i0, j0], i0, j0)]
        while h:
            b, i, j = heapq.heappop(h); b = -b
            if b < B[i, j]:
                continue
            for a, c in ((i+1, j), (i-1, j), (i, j+1), (i, j-1)):
                if 0 <= a < n and 0 <= c < m:
                    nb = min(b, d[a, c])
                    if nb > B[a, c]:
                        B[a, c] = nb; heapq.heappush(h, (-nb, a, c))
        return B

    def start(self, fld):
        """Where a body arrives: deck frame, the best-cleared cell of the landing well (off the ladder); aft frame, within 0.6 m of the Q47
        step. The well is walkable for paths (it only keeps care envelopes off the landing)."""
        import numpy as np
        us, vs, d = fld; U, V = np.meshgrid(us, vs, indexing='ij')
        if self.frame == 'deck':
            L = self.L; near = (U >= L['well_x'][0]) & (U <= L['well_x'][1]) & (V >= L['well_z'][0]) & (V <= L['well_z'][1])
        else:
            near = np.hypot(U-self.start_hint[0], V-self.start_hint[1]) < 0.6
        k = np.unravel_index(np.argmax(np.where(near, d, -1)), d.shape)
        return (float(us[k[0]]), float(vs[k[1]]))

    def at(self, fld, B, p):
        import numpy as np
        us, vs, _ = fld
        return float(B[int(np.argmin(abs(us-p[0]))), int(np.argmin(abs(vs-p[1])))])

    def targets(self, skip=()):
        """Station fronts of the remaining blocks a person stands at (blocks that reach the floor): the points 0.45 m off each face that has floor
        room in this plane without any care envelope (a 0.60 m body plus 0.15 m, so the target does not cap the path value); a station is reached if any of its fronts is (max over the fronts)."""
        base = self.field(); out = []
        for b in self.blocks:
            if b['name'] in skip:
                continue
            u0, u1, v0, v1, h0, h1 = self.P(b['min'], b['max'])
            if h0 > 0.10:
                continue
            uc, vc = (u0+u1)/2, (v0+v1)/2
            pts = [(u0-0.45, vc), (u1+0.45, vc), (uc, v0-0.45), (uc, v1+0.45)]
            pts = [p for p in pts if self.urng[0] < p[0] < self.urng[1] and abs(p[1]) < 2.8 and self.at(base, base[2], p) > 0.0]
            out.append((b['name'], pts))
        return out


def env_station(cp, side, end, axis, c, surface, attendants=True, shift=0.0, stance='standing'):
    """Care station round a care point footprint cp = (u0, u1, v0, v1, h_surface): the care point, the kit on the patient's legs, attendant 1 in
    a strip along the open long side, attendant 2 at the head (airway) end."""
    u0, u1, v0, v1 = cp; aw, he_ = c['attendant_w_m'], c['head_end_m']; H = c['stand_h_m'] if stance == 'standing' else c['kneel_h_m']
    kl, kw, kt = c['kit_m']; pt = c['patient_t_m']
    if axis == 'u':
        strip = (u0, u1, *((v1, v1+aw) if side > 0 else (v0-aw, v0)))
        head = (*((u1, u1+he_) if end > 0 else (u0-he_, u0)), v0+side*shift, v1+side*shift)
        fu = (u0, u0+kl) if end > 0 else (u1-kl, u1); vc = (v0+v1)/2; kit = (*fu, vc-kw/2, vc+kw/2)
    else:
        strip = (*((u1, u1+aw) if side > 0 else (u0-aw, u0)), v0, v1)
        head = (u0+side*shift, u1+side*shift, *((v1, v1+he_) if end > 0 else (v0-he_, v0)))
        fv = (v0, v0+kl) if end > 0 else (v1-kl, v1); uc = (u0+u1)/2; kit = (uc-kw/2, uc+kw/2, *fv)
    env = [(*kit, surface+pt, surface+pt+kt, 'kit')]
    if attendants:
        env += [(*strip, 0.0, H, 'attendant_1_strip'), (*head, 0.0, H, 'attendant_2_head_end')]
    return env


def env_transfer(cp, side, axis, car, c, surface, offset=0.0, arrangement='beside'):
    """Transfer station: the carrier beside the care point on its open side at the care surface; the two rescuers in a strip beyond it
    ('beside') or one at each end of the carrier ('ends', each attendant_w deep across the carrier's width)."""
    u0, u1, v0, v1 = cp; L, W, T = car; aw, H = c['attendant_w_m'], c['stand_h_m']
    if axis == 'u':
        mc = (u0+u1)/2+offset; a0, a1 = mc-L/2, mc+L/2
        lit = (a0, a1, *((v1, v1+W) if side > 0 else (v0-W, v0))); res = (a0, a1, *((v1+W, v1+W+aw) if side > 0 else (v0-W-aw, v0-W)))
    else:
        mc = (v0+v1)/2+offset; a0, a1 = mc-L/2, mc+L/2
        lit = (*((u1, u1+W) if side > 0 else (u0-W, u0)), a0, a1); res = (*((u1+W, u1+W+aw) if side > 0 else (u0-W-aw, u0-W)), a0, a1)
    if arrangement == 'ends':
        if axis == 'u':
            res = [(a0-aw, a0, lit[2], lit[3]), (a1, a1+aw, lit[2], lit[3])]
        else:
            res = [(lit[0], lit[1], a0-aw, a0), (lit[0], lit[1], a1, a1+aw)]
        return [(*lit, surface, surface+T, 'carrier'), (*res[0], 0.0, H, 'rescuer_end_1'), (*res[1], 0.0, H, 'rescuer_end_2')]
    return [(*lit, surface, surface+T, 'carrier'), (*res, 0.0, H, 'rescuers_strip')]


def assess_point(pl, cp, axis, surface, own, c, cars, sides=(-1, 1), ends=(-1, 1), extra_cp=None, base=None):
    """Best strip side / head end (and the head attendant's inboard shift) for one care point: care-station clearance, transfer clearance per
    carrier (best offset along the point and best rescuer arrangement: rescuers choose where they stand; the carrier classes stay worst case),
    attendant reach, egress past the deployed station; the governing value is the least of them."""
    import numpy as np
    best = None
    for side in sides:
        tr = {}
        for cid, car in cars.items():
            cand = []
            for arr in ('beside', 'ends'):
                for off in np.arange(-0.6, 0.6+1e-9, 0.05):
                    g = pl.clearance(env_transfer(cp, side, axis, car, c, surface, off, arr), exclude=own)
                    cand.append((g, round(float(off), 2), arr))
            g, off, arr = max(cand, key=lambda q: q[0][0]); tr[cid] = dict(clearance_m=round(g[0], 3), nearest=g[1], part=g[2], offset_m=off, rescuers=arr)
        tw = min(tr.items(), key=lambda kv: kv[1]['clearance_m'])
        for end in ends:
            for shift, stance in ((a, b) for a in (0.0, 0.1, 0.2, 0.3) for b in ('standing', 'kneeling')):
                care = env_station(cp, side, end, axis, c, surface, shift=shift, stance=stance)
                cg = pl.clearance(care, exclude=own)
                if extra_cp is not None:
                    g2 = pl.clearance([extra_cp], exclude=own)
                    if g2[0] < cg[0]:
                        cg = g2
                key = (min(cg[0], tw[1]['clearance_m']), cg[0])
                if best is None or key > best[0]:
                    best = (key, dict(side=side, head_end=end, head_shift_m=shift, stance=stance, care=dict(clearance_m=round(cg[0], 3), nearest=cg[1], part=cg[2]), transfer=tr,
                                      transfer_worst=dict(carrier=tw[0], **tw[1]), env=[[round(float(x), 3) if not isinstance(x, str) else x for x in e] for e in care]))
    r = best[1]
    env = [tuple(e) for e in r['env']]+([extra_cp] if extra_cp is not None else [])
    att = [e for e in env if e[6].startswith('attendant')]
    fld_open = pl.field([e for e in env if not e[6].startswith('attendant')])
    B = pl.widest(fld_open, pl.start(fld_open)); reach = {}
    for a in att:                         # the attendant steps in from the best point on the box's free edges (not the care point's side)
        u0, u1, v0, v1 = a[:4]; pts = []
        for f in np.linspace(0, 1, 11):
            pts += [(u0+(u1-u0)*f, v0), (u0+(u1-u0)*f, v1), (u0, v0+(v1-v0)*f), (u1, v0+(v1-v0)*f)]
        cpb = extra_cp[:4] if extra_cp is not None else cp
        pts = [p for p in pts if not (cpb[0]-0.02 <= p[0] <= cpb[1]+0.02 and cpb[2]-0.02 <= p[1] <= cpb[3]+0.02)]
        reach[a[6]] = round(max(pl.at(fld_open, B, p) for p in pts)-c['walk_w_m']/2, 3) if pts else None
    fld = pl.field(env); st2 = pl.start(fld); B2 = pl.widest(fld, st2)
    eg = {n: round(max(pl.at(fld, B2, p) for p in ps)-c['walk_w_m']/2, 3) for n, ps in pl.targets(skip=own) if ps}
    r.update(reach=reach, start_uv=[round(x, 3) for x in st2], **egress_vs(eg, base))
    egw = (r['egress_worst']['target'], r['egress_worst']['clearance_m'])
    r['governing_m'] = round(min([r['care']['clearance_m'], r['transfer_worst']['clearance_m'], egw[1]]+[v for v in reach.values() if v is not None]), 3)
    return r


def egress_vs(eg, base):
    """Egress to every station against the as-built layout: a station the as-built layout serves (>= 0.05 m) must stay >= 0.05 m and governs;
    stations already below 0.05 m as built are pre-existing layout limits: listed, flagged when the care station makes them worse, not governing."""
    rows = {n: dict(care_m=v, as_built_m=(base or {}).get(n)) for n, v in eg.items()}
    served = {n: r['care_m'] for n, r in rows.items() if r['as_built_m'] is None or r['as_built_m'] >= STUDY_MARGIN_M}
    pre = {n: r for n, r in rows.items() if n not in served}
    worse = {n: r for n, r in pre.items() if r['care_m'] < r['as_built_m']-1e-6}
    w = min(served.items(), key=lambda kv: kv[1]) if served else (None, CAP_M)
    return dict(egress=rows, egress_preexisting=pre, egress_preexisting_made_worse=worse, egress_worst=dict(target=w[0], clearance_m=w[1]))


def egress_values(pl, c, extra=(), skip=()):
    fld = pl.field(list(extra)); st = pl.start(fld); B = pl.widest(fld, st)
    return {n: round(max(pl.at(fld, B, p) for p in ps)-c['walk_w_m']/2, 3) for n, ps in pl.targets(skip=skip) if ps}


def stowed_egress(pl, c, extra=(), base=None):
    r = egress_vs(egress_values(pl, c, extra), base)
    return dict(r, worst=r['egress_worst'])


def garden_couch(s, c, cars):
    """Search the deployed fold-down couch inside the footprint the swapped blocks give up (long axis along the sector length, hinged on the
    outboard wall; or across, hinged on the end wall), the best strip side / head end, then measure it."""
    import numpy as np
    import habitat_interior as hi
    pl = Plane(s, GARDEN, 'deck', drop=SWAP); base = egress_values(Plane(s, GARDEN, 'deck'), c)
    sw = [b for b in hi.zones(s, GARDEN) if b['name'] in SWAP]
    fu = (min(b['min'][0] for b in sw), max(b['max'][0] for b in sw)); fv = (min(b['min'][2] for b in sw), max(b['max'][2] for b in sw))
    L, W, top = c['length_m'], c['width_m'], c['top_m']; zw = pl.half(-c['stowed_top_m'])       # the wall face over the stowed panel's height
    cands = []
    for u0 in np.arange(fu[0], fu[1]-L+1e-9, 0.05):                      # along: hinge on the outboard wall, open side inboard
        cands.append(('u', (float(u0), float(u0)+L, min(zw, fv[1])-W, min(zw, fv[1])), -1))
    for v0 in np.arange(fv[0], min(zw, fv[1])-L+1e-9, 0.05):             # across: hinge on the forward end wall (u = fu[1]), open side aft
        cands.append(('v', (fu[1]-W, fu[1], float(v0), float(v0)+L), -1))
    res = []
    for axis, cp, side in cands:
        cpbox = (*cp, 0.0, top, 'care_couch_deployed')
        r = assess_point(pl, cp, axis, top, (), c, cars, sides=(side,), extra_cp=cpbox, base=base)
        r.update(axis=axis, footprint_uv=[round(x, 3) for x in cp]); res.append(r)
    best = max(res, key=lambda r: r['governing_m'])
    cp = best['footprint_uv']
    if best['axis'] == 'u':
        stow = (cp[0], cp[1], cp[3]-c['stowed_depth_m'], cp[3], 0.0, c['stowed_top_m'], 'care_couch_stowed')
    else:
        stow = (cp[1]-c['stowed_depth_m'], cp[1], cp[2], cp[3], 0.0, c['stowed_top_m'], 'care_couch_stowed')
    best['stowed_uvh'] = [round(x, 3) if not isinstance(x, str) else x for x in stow]
    best['stowed_clearance'] = dict(zip(('clearance_m', 'nearest', 'part'), pl.clearance([stow])))
    best['stowed_egress'] = stowed_egress(pl, c, [stow], base)
    best['candidates'] = len(res); best['freed_footprint_uv'] = [round(fu[0], 3), round(fu[1], 3), round(fv[0], 3), round(fv[1], 3)]
    return best, pl


def local_box(pl, uvh):
    """A plane box (u0, u1, v0, v1, h0, h1) back to the sector frame ((x, y, z) min, max)."""
    u0, u1, v0, v1, h0, h1 = uvh[:6]
    if pl.frame == 'deck':
        return (u0, -h1, v0), (u1, -h0, v1)
    return (h0+pl.xlo, u0, v0), (h1+pl.xlo, u1, v1)


def screen():
    import habitat_interior as hi
    from spec import load
    s = load(ROOT)[0]; c = couch_spec(s); cars = carriers_plan(); sec = hi.section(s)
    out = dict(couch=c, carriers_plan_m={k: [round(x, 3) for x in v] for k, v in cars.items()}, functions={})
    g, gpl = garden_couch(s, c, cars)
    dep_lo, dep_hi = local_box(gpl, (*g['footprint_uv'], 0.0, c['top_m']))
    stow_lo, stow_hi = local_box(gpl, g['stowed_uvh'])
    out['garden_couch'] = dict(g, deployed_local_min=list(dep_lo), deployed_local_max=list(dep_hi), stowed_local_min=list(stow_lo), stowed_local_max=list(stow_hi))
    for fn in s['habitat']['layout']['functions']:
        res = {}
        for frame in ('deck', 'aft'):
            fr = {}
            if frame == 'deck':
                if fn == GARDEN:
                    pl0 = Plane(s, fn, 'deck')
                    fr['as_built_egress'] = stowed_egress(pl0, c, base=egress_values(pl0, c))
                    fr['care_point'] = 'fold-down care couch (PROTOTYPE, garden swap)'; fr['station'] = g
                    fr['stowed_egress'] = g['stowed_egress']
                else:
                    pl = Plane(s, fn, 'deck')
                    name, own = ('Medical_Couch', ()) if fn == 'WORK_MEDICAL_OPS' else ('Bunk_1', HAB_OWN)
                    b = next(q for q in pl.blocks if q['name'] == name); u0, u1, v0, v1, h0, h1 = pl.P(b['min'], b['max'])
                    surface = s['sector_whitebox']['medical_table_m'] if name == 'Medical_Couch' else h0
                    sides = (-1,) if (v0+v1)/2 > 0 else (1,)
                    base = egress_values(pl, c, skip=(name,)+own)
                    r = assess_point(pl, (u0, u1, v0, v1), 'u', surface, (name,)+own, c, cars, sides=sides, base=base)
                    fr['care_point'] = name; fr['station'] = r; fr['surface_m'] = surface
                    fr['as_built_egress'] = stowed_egress(pl, c, base=egress_values(pl, c))
            else:
                extra = []
                if fn == GARDEN:
                    lo, hi_ = out['garden_couch']['stowed_local_min'], out['garden_couch']['stowed_local_max']
                    extra = [(tuple(lo), tuple(hi_), 'care_couch_stowed')]
                pl = Plane(s, fn, 'aft', drop=SWAP if fn == GARDEN else (), extra=extra); pa = Plane(s, fn, 'aft')
                best = None
                for name, own in (('Burn_Couch_1', ('Couch_Lockers_1',)), ('Burn_Couch_2', ('Couch_Lockers_2',))):
                    b = next(q for q in pl.blocks if q['name'] == name); u0, u1, v0, v1, h0, h1 = pl.P(b['min'], b['max'])
                    sides = (-1,) if (v0+v1)/2 > 0 else (1,)
                    r = assess_point(pl, (u0, u1, v0, v1), 'u', h1, (name,)+own, c, cars, sides=sides, base=egress_values(pa, c, skip=(name,)+own))
                    r['care_point'] = name
                    if best is None or r['governing_m'] > best['governing_m']:
                        best = r
                    fr.setdefault('alternatives', {})[name] = dict(governing_m=r['governing_m'], care=r['care'], transfer_worst=r['transfer_worst'],
                                                                   egress_worst=r['egress_worst'], reach=r['reach'])
                fr['care_point'] = best['care_point']; fr['station'] = best
                fr['as_built_egress'] = stowed_egress(pa, c, base=egress_values(pa, c))
                if fn == GARDEN:
                    fr['stowed_egress'] = stowed_egress(pl, c, base=egress_values(pa, c))
            res[frame] = fr
        out['functions'][fn] = res
    # measured volumes / areas (geometry facts only)
    gb = [b for b in hi.zones(s, GARDEN)]
    vol = lambda b: (b['max'][0]-b['min'][0])*(b['max'][1]-b['min'][1])*(b['max'][2]-b['min'][2])
    st = g['env']; dep = (*g['footprint_uv'], 0.0, c['top_m'])
    allx = [e for e in st if e[6] != 'kit']+[list(dep)+['couch']]
    bb = (min(e[0] for e in allx), max(e[1] for e in allx), min(e[2] for e in allx), max(e[3] for e in allx), 0.0, max(e[5] for e in allx))
    out['measured'] = dict(
        sector_deck_to_overhead_m3=round(sec['deck_to_overhead_m3'], 2), sector_usable_m3_owner=sec['usable_m3'], sector_length_m=sec['length_m'],
        deck_width_m=round(sec['deck_width_m'], 3), headroom_m=round(sec['headroom_m'], 3),
        garden_blocks_m3_as_built=round(sum(vol(b) for b in gb), 2), garden_blocks_m3_swap=round(sum(vol(b) for b in gb if b['name'] not in SWAP), 2),
        swapped_blocks_m3=round(sum(vol(b) for b in gb if b['name'] in SWAP), 2),
        couch_stowed_m3=round((g['stowed_uvh'][1]-g['stowed_uvh'][0])*(g['stowed_uvh'][3]-g['stowed_uvh'][2])*(g['stowed_uvh'][5]-g['stowed_uvh'][4]), 3),
        care_station_bbox_uvh=[round(x, 3) for x in bb],
        care_station_bbox_m3=round((bb[1]-bb[0])*(bb[3]-bb[2])*(bb[5]-bb[4]), 2),
        care_station_bbox_surface_m2=round(2*((bb[1]-bb[0])*(bb[3]-bb[2])+(bb[1]-bb[0])*(bb[5]-bb[4])+(bb[3]-bb[2])*(bb[5]-bb[4])), 2),
        note='zone-block volumes (overlaps not removed); the care-station box is the couch + two attendants\' envelope, a measurement, not a shelter')
    out['status'] = 'PROTOTYPE fit screen of the zone blocks; no medical, atmosphere, pressure or radiation qualification'
    RUN.mkdir(parents=True, exist_ok=True); (RUN/'screen.json').write_text(json.dumps(out, indent=1, default=float)+'\n')
    g = out['garden_couch']
    print('WF_CARE_SCREEN couch', g['axis'], g['footprint_uv'], 'gov', g['governing_m'], 'care', g['care'], 'tw', g['transfer_worst'], 'egress', g['egress_worst'], 'reach', g['reach'], flush=True)
    for fn, r in out['functions'].items():
        for frame, fr in r.items():
            print('WF_CARE_SCREEN', fn, frame, fr['care_point'], fr['station']['governing_m'], fr['station']['care'],
                  fr['station']['transfer_worst'], fr['station']['egress_worst'], fr['station']['reach'], 'asbuilt', fr['as_built_egress']['worst'], 'stowed', fr.get('stowed_egress', {}).get('worst'), flush=True)
            print('   transfer', {k: (v['clearance_m'], v['nearest'], v['rescuers']) for k, v in fr['station']['transfer'].items()}, 'egress', fr['station']['egress'], flush=True)
    return out


# ------------------------------------------------------------------------------------------------------------------------------------
# Blender: the built model with the swap in memory

def box_record(pts_world, name, kind='study_couch'):
    fs = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    lo = [min(p[k] for p in pts_world) for k in range(3)]; hi = [max(p[k] for p in pts_world) for k in range(3)]
    return dict(name=name, kind=kind, vs=[tuple(p) for p in pts_world], fs=fs, lo=lo, hi=hi)


def sector_world(s, j, k):
    import crew_transfer
    import human_entry as he
    rot, v, la = he.vestibule_station(s, j)
    return lambda p: tuple(he.at_index(rot, crew_transfer.sector_point(s, la[k], p)))


def local_box_world(s, j, k, lo, hi):
    w = sector_world(s, j, k)
    return [w((x, y, z)) for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])]


def swapped_records(s, records, scr, couch_state):
    """Drop the swapped blocks (and their fit-out: pull rails, handles, the room label) from both garden sectors and add the couch box."""
    gk = s['habitat']['layout']['functions'].index(GARDEN)+1
    keep = [r for r in records if not any(n in r['name'] for n in SWAP) or r['name'].startswith('Sector_Fit_Room_Mess_')]
    keep = [r for r in keep if not ('Garden_Rack_1' in r['name'] or r['name'] == 'Mess')]
    g = scr['garden_couch']
    lo, hi = (g['deployed_local_min'], g['deployed_local_max']) if couch_state == 'deployed' else (g['stowed_local_min'], g['stowed_local_max'])
    for j in (1, 2):
        keep.append(box_record(local_box_world(s, j, gk, lo, hi), f'Care_Couch_{couch_state}_{j}'))
    return keep


def care_routes(s, scr, j, k, frame, car, key):
    """The in-sector route of one carrier: from the tube tip through the sector hatch (human_entry.route) to a straight leg beside the care point
    at its surface (deck frame: 0 g / spin / stopped) or over a burn couch (aft frame, locked 1.5 g, aft down: the carrier comes out of the
    overhead hatch toward the deck, now a side wall, and runs along the couch), then the placement onto it as explicit poses (deck: sideways;
    aft: lowered aft). The last pose rests 0.08 + 0.05 m above the care surface (the medical route's pad + the study margin).
    Returns {care point: (path, poses)}."""
    import numpy as np
    import hum003_routes as hr
    import human_entry as he
    import habitat_interior as hi_
    fn = s['habitat']['layout']['functions'][k-1]; L_ = he.landing(s); W = sector_world(s, j, k)
    route = hr.trunk_routes(s)['AB'[j-1]+str(k)]['path']
    i4 = max(i for i, q in enumerate(route) if q[0] == 4)
    hl = hr.length(car); half = car['size'][2]/2 if car['shape'] == 'box' else car['radius']; wid = car['size'][1] if car['shape'] == 'box' else 2*car['radius']
    fr = scr['functions'][fn][frame]; out = {}
    unit = lambda a, b: (lambda d: tuple(d/np.linalg.norm(d)))(np.subtract(W(b), W(a)))
    if frame == 'deck':
        if fn == GARDEN:
            g = scr['garden_couch']; lo, hi = g['deployed_local_min'], g['deployed_local_max']; surface = scr['couch']['top_m']; name = 'Care_Couch'; axis = g['axis']
        else:
            name = fr['care_point']; b = next(q for q in hi_.zones(s, fn) if q['name'] == name); lo, hi = b['min'], b['max']; surface = fr['surface_m']; axis = 'u'
        st = fr['station']; side = st['side']; off = st['transfer'][key]['offset_m']
        ys = -(surface+0.08+half+0.05)
        # plane (a = along the care point, b = across) <-> sector (x, z)
        A, Bi = (0, 2) if axis == 'u' else (2, 0)
        bb = (lo[Bi]-wid/2-0.10) if side < 0 else (hi[Bi]+wid/2+0.10); bc = (lo[Bi]+hi[Bi])/2; am = (lo[A]+hi[A])/2+off
        P = lambda a, y, b: (a, y, b) if axis == 'u' else (b, y, a)
        land = (L_['x'], L_['z']) if axis == 'u' else (L_['z'], L_['x'])
        best = None
        for sgn in (1, -1):                       # the head runs toward +a or -a along the care point; keep the gentler turn
            ae = am+sgn*hl/2; as_ = am-sgn*(hl/2+0.05)
            v1 = np.subtract((as_, bb), land); v2 = np.array((ae-as_, 0.0))
            ang = math.acos(max(-1, min(1, float(np.dot(v1, v2)/np.linalg.norm(v1)/np.linalg.norm(v2)))))
            if best is None or ang < best[0]:
                best = (ang, as_, ae)
        _, as_, ae = best
        path = [route[i4], ('5', W((L_['x'], cs_carry(), L_['z']))), ('C', W(P(as_, cs_carry(), bb))), ('C', W(P(ae, ys, bb)))]
        d = unit(P(ae, ys, bb), P(as_, ys, bb))
        poses = [(W(P(ae, ys, bb+(bc-bb)*t)), d, 0.0, f'slide {t:.1f}') for t in np.linspace(0, 1, 6)]
        out[name] = (path, poses)
    else:
        for name in ('Burn_Couch_1', 'Burn_Couch_2'):
            b = next(q for q in hi_.zones(s, fn) if q['name'] == name); lo, hi = b['min'], b['max']
            zc = (lo[2]+hi[2])/2; xr = hi[0]+0.08+half+0.05; xh = xr+0.40; yb = min(-0.05, (lo[1]+hi[1])/2+hl/2); ya = yb-hl-0.05
            path = [route[i4], ('C', W((xh, ya, zc))), ('C', W((xh, yb, zc)))]
            d = unit((xh, yb, zc), (xh, ya, zc))
            poses = [(W((xh+(xr-xh)*t, yb, zc)), d, 0.0, f'lower {t:.1f}') for t in np.linspace(0, 1, 6)]
            out[name] = (path, poses)
    return out


def cs_carry():
    import casualty_sweep as cs
    return cs.CARRY_Y_M


DOOR_PARTIAL = 0.90


def sweep(args):
    """ringb_unified.survey's worst-case method on an in-sector care route: (door, scale) states, seeds, families, inline rescuers; then the
    slide poses (best-found pose about each, per state)."""
    import bpy
    import numpy as np
    import casualty_sweep as cs
    import hum003_routes as hr
    import ringb_unified as ru
    from spec import load
    s = load(ROOT)[0]; scr = json.loads((RUN/'screen.json').read_text()); j, k = SECTORS[args.sector]
    bpy.ops.wm.open_mainfile(filepath=str(ROOT/'assets/wayfarer/WF_WAYFARER_001.blend')); ins = cs.load_inspect()
    car0 = hr.CARRIERS[args.carrier]; t0 = time.time()
    out = dict(sector=args.sector, frame=args.frame, carrier=args.carrier, couch_state='deployed' if args.frame == 'deck' else 'stowed', points={})
    for door, scale in ((1.0, 1.0), (1.0, hr.BODY_SCALE_LARGE), (DOOR_PARTIAL, 1.0)):
        records = swapped_records(s, cs.scene(s, ins, door), scr, out['couch_state']); car = hr.scaled(car0, scale)
        for name, (path, slide) in care_routes(s, scr, j, k, args.frame, car, f'{args.carrier} x{scale:.2f}').items():
            o = out['points'].setdefault(name, dict(sweeps=[], families=[], slide=[]))
            walls = hr.Walls(records, [p for _, p in path]+[q[0] for q in slide])
            seeds = ru.SEEDS_NOMINAL if (door, scale) == (1.0, 1.0) else (ru.SEEDS_LARGE if scale != 1.0 else (301,))
            for seed in seeds:
                r = hr.sweep_route(walls, car, path, np.random.default_rng(seed), couch=True)
                o['sweeps'].append(dict(door=door, scale=scale, seed=seed, carrier_m=r['least_m'], carrier_nearest=r['nearest'], staff_m=r['staff_least_m'],
                                        staff_nearest=r['staff_nearest'], by_zone={z: v['least_m'] for z, v in r['by_zone'].items()}))
                sp = hr.sweep_poses(walls, car, slide, np.random.default_rng(seed))
                o['slide'].append(dict(door=door, scale=scale, seed=seed, least_m=sp['least_m'], nearest=sp['nearest'], at=sp['at']))
                print('WF_CARE_SWEEP', args.sector, args.frame, name, args.carrier, door, scale, seed, r['least_m'], r['nearest'], r['staff_least_m'], 'slide', sp['least_m'], sp['nearest'], flush=True)
            f = hr.family_sweep(walls, car, path, couch=True); f.update(door=door, scale=scale); o['families'].append(f)
            print('WF_CARE_FAM', args.sector, args.frame, name, args.carrier, door, scale, f['worst_family_m'], f['best_family_m'], f['staff_least_m'], flush=True)
    out['seconds'] = round(time.time()-t0, 1); out['done'] = True
    d = RUN/'sweep'; d.mkdir(parents=True, exist_ok=True); (d/f'{args.sector}_{args.frame}_{args.carrier}.json').write_text(json.dumps(out, indent=1, default=str)+'\n')


def station(args):
    """The two attendants (standing capsules, hum003 rescuer radius) and the kit on the patient, at the screen's care stations, against the built
    meshes with the swap (deck: couch deployed; aft: couch stowed). The care point itself is excluded for the kit (it rests on the patient)."""
    import bpy
    import casualty_sweep as cs
    import hum003_routes as hr
    from spec import load
    s = load(ROOT)[0]; scr = json.loads((RUN/'screen.json').read_text())
    bpy.ops.wm.open_mainfile(filepath=str(ROOT/'assets/wayfarer/WF_WAYFARER_001.blend')); ins = cs.load_inspect()
    base = cs.scene(s, ins, 1.0); out = {}
    for sec, (j, k) in SECTORS.items():
        fn = s['habitat']['layout']['functions'][k-1]; W = sector_world(s, j, k)
        for frame in ('deck', 'aft'):
            recs = swapped_records(s, base, scr, 'deployed' if frame == 'deck' else 'stowed')
            st = scr['functions'][fn][frame]['station']; pl = Plane(s, fn, frame)
            res = {}
            for e in st['env']:
                lo, hi = local_box(pl, e[:6])
                c = [(lo[i]+hi[i])/2 for i in range(3)]
                if e[6].startswith('attendant'):
                    R = hr.STAFF_R_M
                    if frame == 'deck':
                        a, b = (c[0], -(R+0.10), c[2]), (c[0], -(scr['couch']['stand_h_m']-R), c[2])               # feet on the deck: floor contact not counted
                    else:
                        a, b = (pl.xlo+R+0.10, c[1], c[2]), (pl.xlo+scr['couch']['stand_h_m']-R, c[1], c[2])    # feet on the aft skin: floor contact not counted
                    # the attendant stands against the care point by design: it is excluded (its own gap is the screen's)
                    cpn = scr['functions'][fn][frame]['care_point']; skip = ('Care_Couch_deployed_', ) if (fn == GARDEN and frame == 'deck') else (cpn,)
                    a, b = W(a), W(b); walls = hr.Walls([q for q in recs if not q['name'].startswith(skip)], [a, b]); m = walls.cl.capsule(a, b, R)
                    res[e[6]] = dict(least_m=round(m[0], 3), nearest=m[1])
                else:
                    pts = [W((x, y, z)) for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])]
                    walls = hr.Walls(recs, pts); vs, fs = pts, [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
                    hit = walls.overlaps(vs, fs); cen = W(tuple(c)); dmin = walls.cl.point(cen, 0.0)
                    res[e[6]] = dict(overlap=hit, centre_to_surface_m=round(dmin[0], 3), nearest=dmin[1])
            out[f'{sec}|{frame}'] = res
            print('WF_CARE_STATION', sec, frame, res, flush=True)
    (RUN/'station.json').write_text(json.dumps(out, indent=1, default=str)+'\n')


RING_A_ROUTES = ('A1', 'A2', 'A3', 'A1-A2', 'A3-A2', 'A2-M', 'A1-A2-M', 'A3-A2-M')


def ringa(args):
    """ringb_unified.survey on the built model (ring A as built): output under RUN/ringA/built/survey."""
    import ringb_unified as ru
    ru.UNI = RUN/'ringA'; ru.work_of = lambda v: ROOT
    ru.survey(argparse.Namespace(variant='built', route=args.route, carrier=args.carrier))


# ------------------------------------------------------------------------------------------------------------------------------------
# launcher (system python)

def jobs():
    js = [('screen', ['screen'], RUN/'screen.json')]
    sw = [(f'sweep {sec} {fr} {c}', ['sweep', '--sector', sec, '--frame', fr, '--carrier', c], RUN/'sweep'/f'{sec}_{fr}_{c}.json')
          for sec in SECTORS for fr in ('deck', 'aft') for c in CARRIER_IDS]
    ra = [(f'ringa {r} {c}', ['ringa', '--route', r, '--carrier', c], RUN/'ringA/built/survey'/f'{r}_{c}.json') for r in RING_A_ROUTES for c in CARRIER_IDS]
    st = [('station', ['station'], RUN/'station.json')]
    return js, sw+ra+st


def run(args):
    from concurrent.futures import ThreadPoolExecutor
    RUN.mkdir(parents=True, exist_ok=True); (RUN/'logs').mkdir(exist_ok=True)
    first, rest = jobs()
    def go(j):
        label, argv, done = j
        if done.exists() and not args.force and (done.suffix != '.json' or 'survey' not in str(done) or json.loads(done.read_text()).get('done')):
            return 0
        log = RUN/'logs'/(re.sub(r'[^A-Za-z0-9_.-]+', '_', label)+'.log'); t = time.time()
        for attempt in range(3):                  # Blender occasionally crashes while evaluating the assembly; retry
            with open(log, 'w') as f:
                code = subprocess.call(['timeout', '-s', 'KILL', str(args.timeout), BLENDER, '-b', '--factory-startup', '--python-exit-code', '1',
                                        '--python', str(Path(__file__).resolve()), '--']+argv, stdout=f, stderr=subprocess.STDOUT, cwd=ROOT)
            if code == 0:
                break
        print('done', label, code, f'{time.time()-t:.0f}s', flush=True); return code
    for j in first:
        if args.only in j[0] or j[0] == 'screen':
            go(j)
    rest = [j for j in rest if args.only in j[0]]
    rest.sort(key=lambda j: (0 if j[0].startswith('ringa') and ('-' in j[0].split()[1]) else 1 if j[0].startswith('ringa') else 2))
    with ThreadPoolExecutor(args.workers) as ex:
        list(ex.map(go, rest))


# ------------------------------------------------------------------------------------------------------------------------------------
# collect (system python)

def _st(m):
    return 'OPEN' if m is None else ('FAIL' if m < 0 else ('MARGINAL' if m < STUDY_MARGIN_M else 'PASS'))


RANK = {'FAIL': 0, 'OPEN': 1, 'MARGINAL': 2, 'PASS': 3}


def _worse(*sts):
    return min(sts, key=lambda q: RANK[q])


def sweep_stats(d, name):
    """Worst over sweeps (carrier, staff), families (best family per step, staff families) and slide poses of one care point; zone C alone."""
    o = d['points'].get(name)
    if not o:
        return None
    e = []
    for sw in o['sweeps']:
        lab = f"{d['carrier']} x{sw['scale']:.2f} doors {sw['door']:.2f} seed {sw['seed']}"
        e.append((sw['carrier_m'], sw['carrier_nearest'], lab+' carrier'))
        if sw['staff_m'] is not None:
            e.append((sw['staff_m'], sw['staff_nearest'], lab+' staff'))
    for f in o['families']:
        lab = f"{d['carrier']} x{f['scale']:.2f} doors {f['door']:.2f}"
        if f['best_family_m'] is not None:
            e.append((f['best_family_m'], f['best_family_nearest'], lab+' best family (+-0.02 m wobble)'))
        if f['staff_least_m'] is not None:
            e.append((f['staff_least_m'], f['staff_nearest'], lab+' staff families'))
    sl = [(q['least_m'], q['nearest'], f"{d['carrier']} x{q['scale']:.2f} doors {q['door']:.2f} seed {q['seed']} {q['at']}") for q in o['slide']]
    w = min(e+sl, key=lambda q: q[0])
    zc = [sw['by_zone'].get('C') for sw in o['sweeps'] if sw['by_zone'].get('C') is not None]
    z5 = [sw['by_zone'].get('5') for sw in o['sweeps'] if sw['by_zone'].get('5') is not None]
    unad = [f['worst_family_m'] for f in o['families'] if f['worst_family_m'] is not None]
    return dict(least_m=round(w[0], 3), nearest=w[1], case=w[2], route_least_m=round(min(q[0] for q in e), 3), slide_least_m=round(min(q[0] for q in sl), 3) if sl else None,
                slide_nearest=min(sl, key=lambda q: q[0])[1] if sl else None, zone_C_sweeps_m=round(min(zc), 3) if zc else None, zone_5_sweeps_m=round(min(z5), 3) if z5 else None,
                unadapted_family_m=round(min(unad), 3) if unad else None, seconds=d.get('seconds'))


def collect():
    import ringb_unified as ru
    scr = json.loads((RUN/'screen.json').read_text()); spec_fn = ['HABITATION', 'WORK_MEDICAL_OPS', GARDEN]
    station = json.loads((RUN/'station.json').read_text()) if (RUN/'station.json').exists() else {}
    sweeps = {}
    for f in sorted((RUN/'sweep').glob('*.json')):
        d = json.loads(f.read_text())
        for name in d['points']:
            sweeps[(d['sector'], d['frame'], name, d['carrier'])] = sweep_stats(d, name)
    segs = []; matrix = {}
    WORST = ['injury classes A rigid litter, C vacuum mattress, K litter + kit, S suited', 'body size x1.00 and x1.08', 'doors 1.00 and 0.90 (the sector hatch leaf)',
             'search seeds 17,101,102,103 (+201,202 large, 301 doors 0.90)', '6 pose families with six +-0.02 m / +-0.05 rad wobbles',
             'two inline rescuers (both ends, inline and +-0.10 m)', 'slide onto the care point: six poses, best-found about each, every state and seed']
    for sec, (j, k) in SECTORS.items():
        fn = spec_fn[k-1]; row = {}
        for frame, states in (('deck', ('0g', 'spin', 'stopped')), ('aft', ('locked_1.5g',))):
            fr = scr['functions'][fn][frame]; st = fr['station']
            # sweep: per care point the worst over classes; the care point used is the best (aft: of the two burn couches)
            pts = sorted({n for (s_, f_, n, c) in sweeps if s_ == sec and f_ == frame})
            per_point = {}
            for n in pts:
                cls = {c: sweeps[(sec, frame, n, c)] for c in CARRIER_IDS if sweeps.get((sec, frame, n, c))}
                if len(cls) < len(CARRIER_IDS):
                    per_point[n] = dict(least_m=None, missing=[c for c in CARRIER_IDS if c not in cls], per_class={c: v['least_m'] for c, v in cls.items()})
                    continue
                w = min(cls.items(), key=lambda kv: kv[1]['least_m'])
                per_point[n] = dict(least_m=w[1]['least_m'], carrier=w[0], **{k_: w[1][k_] for k_ in ('nearest', 'case', 'route_least_m', 'slide_least_m', 'slide_nearest', 'zone_C_sweeps_m', 'zone_5_sweeps_m', 'unadapted_family_m')},
                                    per_class={c: v['least_m'] for c, v in cls.items()},
                                    per_class_unsuited=min(v['least_m'] for c, v in cls.items() if c != 'S'))
            # the sweep of the screen's care point (aft: the burn couch the screen chose; the other is reported alongside)
            want = 'Care_Couch' if (frame == 'deck' and fn == GARDEN) else fr['care_point']
            sw_name = want if want in per_point else None
            sw_best = per_point.get(sw_name) if sw_name and per_point[sw_name].get('least_m') is not None else None
            sw_u = sw_best['per_class_unsuited'] if sw_best else None
            stn = station.get(f'{sec}|{frame}', {})
            att = [v['least_m'] for kk, v in stn.items() if kk.startswith('attendant')]
            kit = stn.get('kit')
            parts = {'screen care station (care point + kit + two attendants)': st['care']['clearance_m'],
                     'screen transfer station (worst carrier beside + rescuers)': st['transfer_worst']['clearance_m'],
                     'screen attendant reach (0.60 m)': min(st['reach'].values()) if st['reach'] else None,
                     'screen egress past the deployed station (0.60 m)': st['egress_worst']['clearance_m'],
                     'mesh attendants (capsules, built meshes)': min(att) if att else None,
                     'mesh kit (no overlap)': (None if kit is None else (0.0 if kit.get('overlap') else CAP_M)),
                     'carrier sweep hatch -> care point + slide (worst class)': sw_best['least_m'] if sw_best else None}
            if frame == 'deck' and fn == GARDEN:
                parts['screen stowed-couch egress (0.60 m)'] = st['stowed_egress']['worst']['clearance_m']
            least = min((v for v in parts.values() if v is not None), default=None)
            status = _worse(*[_st(v) for v in parts.values()])
            unsuited_parts = dict(parts); unsuited_parts['carrier sweep hatch -> care point + slide (worst class)'] = sw_u
            unsuited_parts['screen transfer station (worst carrier beside + rescuers)'] = min(v['clearance_m'] for kk, v in st['transfer'].items() if not kk.startswith('S'))
            least_u = min((v for v in unsuited_parts.values() if v is not None), default=None)
            status_u = _worse(*[_st(v) for v in unsuited_parts.values()])
            for stt in states:
                row[stt] = dict(status=status, least_m=least, status_unsuited=status_u, least_unsuited_m=least_u,
                                care_point=(sw_name or fr['care_point']), frame=frame)
            row[f'_{frame}'] = dict(parts=parts, sweep=per_point, station_mesh=stn, screen_care_point=fr['care_point'],
                                    screen=dict(care=st['care'], transfer_worst=st['transfer_worst'], transfer=st['transfer'], reach=st['reach'],
                                                egress_worst=st['egress_worst'], governing_m=st['governing_m']))
            seg_states = list(states)
            segs.append(dict(id=f'care|{sec}|{frame}', route=f'ringB-care:{sec} in-sector care' if j == 2 else f'ringA-care:{sec} in-sector care', states=seg_states,
                             variant='garden swap + fold-down couch (PROTOTYPE)' if fn == GARDEN else 'as built', case=f"worst part: {min(parts.items(), key=lambda kv: 9 if kv[1] is None else kv[1])[0]}",
                             least_m=least, status=status, worst_case_over=WORST+['zone screen: care, transfer (A/C/K/S x1.00/x1.08), reach, egress'],
                             seed_spread_m=None, nearest=(sw_best or {}).get('nearest'),
                             note=f"{fn} sector {sec}, {frame} frame; care point {sw_name or fr['care_point']}; parts {json.dumps(parts)}; unsuited-only least {least_u}."))
        # lost ring: the in-sector chain uses no transfer and no other ring; geometry as 'stopped'; dynamics not represented
        row['lost_ring'] = dict(row['stopped'], represented='dependency + geometry only (= stopped, deck frame); lost-ring dynamics (residual momentum, '
                                'uncommanded spin-down, attitude) NOT represented')
        matrix[sec] = dict(function=fn, **row)
    # ring A comparator (worst-case re-run)
    ru.UNI = RUN/'ringA'
    states_a = {'A1': ['0g', 'stopped', 'locked_1.5g'], 'A2': ['spin'], 'A3': ['spin'], 'A2-M': ['spin'],
                'A1-A2': ['stopped', 'locked_1.5g'], 'A3-A2': ['stopped', 'locked_1.5g'], 'A1-A2-M': ['stopped', 'locked_1.5g'], 'A3-A2-M': ['stopped', 'locked_1.5g']}
    quoted = json.loads((ROOT/'references/p1_hum003.json').read_text())['sim027_worst_case_2026_10_11']['ringA_quoted']
    ringA = {}
    for r, sts in states_a.items():
        row = {}
        for grp, classes in (('U', 'ACK'), ('S', 'S')):
            stt = ru.seg_stats('built', r, classes)
            if not stt:
                continue
            row[grp] = stt
            rid = 'ringA-wc:'+r.replace('-', '=>')
            segs.append(dict(id=f'{rid}|built_wc|{grp}', route=rid, states=sts, variant='built (ring A as built), worst-case re-run',
                             case=('unsuited A/C/K, worst: ' if grp == 'U' else 'suited S, worst: ')+stt['case'], least_m=stt['least_m'], status=_st(stt['least_m']),
                             worst_case_over=ru.WORST_OVER[grp], seed_spread_m=stt['spread'], nearest=stt['nearest'],
                             note=f"ring A comparator (15!A169), ringb_unified.survey method on the built model; per class {json.dumps({c: x['least_m'] for c, x in stt['per_class'].items()})}; "
                                  f"single-seed quote was {quoted.get(r, [None])[0]}"))
        ringA[r] = dict(states=sts, quoted_single_seed=quoted.get(r), **row)
    def chain(keys, st):
        vals = []
        for kk in keys:
            if st in ringA.get(kk, {}).get('states', []):
                for grp in ('U', 'S'):
                    if grp in ringA[kk]:
                        vals.append((ringA[kk][grp]['least_m'], f'{kk}|{grp}'))
        return min(vals) if vals else None
    ringA_chain = {}
    for st in STATES:
        allk = chain(list(states_a), st); unk = None
        vals = [(ringA[kk]['U']['least_m'], kk) for kk in states_a if st in ringA.get(kk, {}).get('states', []) and 'U' in ringA[kk]]
        unk = min(vals) if vals else None
        ringA_chain[st] = dict(all_classes=dict(least_m=allk[0] if allk else None, governing=allk[1] if allk else None, status=_st(allk[0] if allk else None)),
                               unsuited=dict(least_m=unk[0] if unk else None, governing=unk[1] if unk else None, status=_st(unk[0] if unk else None)))
    tally = {k: sum(1 for r in matrix.values() for st in STATES if r[st]['status'] == k) for k in RANK}
    tally_u = {k: sum(1 for r in matrix.values() for st in STATES if r[st]['status_unsuited'] == k) for k in RANK}
    ringB_tally = {k: sum(1 for sec, r in matrix.items() if sec[0] == 'B' for st in STATES if r[st]['status'] == k) for k in RANK}
    res = dict(study='Ring B in-sector care + refuge in place (owner 15!A169, 98!A104), NONCANON DISPOSABLE STUDY',
               status='PREFERRED STUDY / MEDICAL, PRESSURE, RADIATION CERTIFICATION OPEN; nothing released; mass, shield and closure budgets OPEN',
               owner=dict(source='S&E 15_MODEL_INTERFACES!A169 (2026-10-13), decision log 98!A104',
                          prohibited_credits=['80 t water distribution', '4.1 t shelter', '25.1 g/cm2 from an idealized shell', 'one-ring stop'],
                          working_constraint='both-ring stop', gcr='NOT implied'),
               couch=scr['couch'], garden_couch={k: v for k, v in scr['garden_couch'].items() if k not in ('candidates',)},
               sector_state_count=dict(repo=len(SECTORS)*len(STATES), sectors=len(SECTORS), states=list(STATES),
                                       note='6 occupied sectors x 4 ship states (access_integrated / ringb_unified); lost ring is not one of them: added as a 5th condition column'),
               matrix=matrix, tally_24=tally, tally_24_unsuited=tally_u, tally_ringB_12=ringB_tally, ringA_comparator=dict(routes=ringA, chain=ringA_chain),
               measured=scr['measured'], open=OPEN, screen_status=scr['status'],
               method=dict(screen='zone blocks (habitat_interior.zones) + keep-outs, analytic box gaps capped at 0.30 m; widest-path bottleneck on a 0.02 m grid for reach/egress',
                           sweep='hum003_routes.sweep_route + family_sweep + sweep_poses on the evaluated built meshes (swap and couch in memory)',
                           ringa='ringb_unified.survey on the built model (all four ship states use the same stationary geometry; spin routes A2/A3 swept with the full 3 door/scale states)'))
    OUT_JSON.write_text(json.dumps(res, indent=1, default=str)+'\n')
    if SEG_JSON.exists():              # keep the owner 2026-10-13 (o13) segments written by collect13
        segs += [q for q in json.loads(SEG_JSON.read_text())['segments'] if '|o13-' in q['id'] or '|o13c-' in q['id']]
    SEG_JSON.write_text(json.dumps(dict(study='Ring B in-sector care + ring A worst-case comparator (owner 15!A169, 2026-10-13); NONCANON PROTOTYPE disposable',
                                        source=['src/wayfarer/studies/ringb_insector_care.py', str(RUN.relative_to(ROOT))],
                                        note='route keys deliberately outside access_integrated.CHAINS filters: re-running access_integrated does not change its chains until a chain is added',
                                        segments=segs), indent=1, default=str)+'\n')
    OUT_MD.write_text(md(res))
    if OUT13_JSON.exists():
        r13_ = json.loads(OUT13_JSON.read_text()); write_md13(r13_)
        if 'o13c' in r13_:
            write_md13c(r13_['o13c'])
    print('tally', tally, 'unsuited', tally_u, 'ringB', ringB_tally)
    for st, v in ringA_chain.items():
        print('ringA', st, v)
    print('wrote', OUT_JSON, SEG_JSON, OUT_MD, len(segs), 'segments')


OPEN = [
    dict(item='Sustained local atmosphere at the care couch', must_specify=['local free volume served (the sector, or a curtained care zone)', 'O2 supply rate and source for patient + 2 attendants',
         'CO2 removal and trace-contaminant control rate', 'ventilation flow at the couch and air change rate', 'smoke / contaminant isolation from the rest of the sector',
         'pressure hold time if the sector leaks; isolation valves; who closes the sector hatch', 'medical gas (O2 / suction) outlets at the couch', 'power and thermal load of the care kit',
         'duration the care must be sustained (stabilisation vs definitive care)'], known=False, owner='S&E / ECLSS (Sheets)'),
    dict(item='Shelter access (refuge in place)', must_specify=['which casualties shelter in place and which go to the storm refuge', 'time from SPE warning to sheltered',
         'access path and its width with the couch deployed (measured here)', 'shelter boundary around the couch (the sector, or a local box)', 'how a non-movable casualty and the attendants are covered',
         'communications and monitoring inside the shelter'], known=False, owner='S&E / Medical'),
    dict(item='SPE protection of the in-sector care station', must_specify=['the 20 g/cm2 water-equivalent target is STUDY ONLY', 'water placement round each ring (80 t distribution not credited)',
         'local shelter mass (4.1 t not credited)', 'areal density actually achieved (25.1 g/cm2 not credited)', 'GCR protection: NOT implied'], known=False, owner='Shielding / mass budget'),
    dict(item='Mass, shield and closure budget of the swap', must_specify=['couch mass and mounting loads', 'displaced Garden_Rack_1 / Mess function: where the growing and common space go',
         'any local closure or curtain'], known=False, owner='owner (15!A169 Claude task: budget OPEN)'),
    dict(item='Couch mechanism', must_specify=['hinge, legs, latch, stowed depth (0.30 m is a PROTOTYPE stand-in)', 'patient restraint in 0 g, spin and 1.5 g', 'rating'], known=False, owner='PROTOTYPE'),
    dict(item='Medical qualification', must_specify=['what stabilisation is done at the couch and for how long', 'kit list (the 0.60 x 0.55 x 0.15 m box is the HUM-003 PROTOTYPE kit)',
         'attendant count and skills'], known=False, owner='Medical'),
    dict(item='Lost-ring and 1.5 g handling', must_specify=['lost-ring dynamics: residual momentum, uncommanded spin-down, attitude (not represented)',
         'in-sector casualty handling under 1.5 g (lowering onto the burn couch: hoist/handling concept and line loads)', 'one-ring stop stays uncredited; both-ring stop is the working constraint'],
         known=False, owner='S&E DYN / Medical'),
]


def md(r):
    L = ['# Ring B in-sector care + refuge in place (2026-10-13)', '',
         'NONCANON DISPOSABLE STUDY. Owner answer S&E 15_MODEL_INTERFACES!A169 (2026-10-13, PREFERRED STUDY / MEDICAL, PRESSURE, RADIATION CERTIFICATION',
         'OPEN) and decision log 98!A104: reversible distributed in-sector stabilisation + refuge in place instead of a 1.6 m ring B transfer port (no ring',
         'B pressure cutout); a fold-down garden-sector care couch with Garden_Rack_1 / Mess displaced in PROTOTYPE only; ring A\'s central rescue path as',
         'the comparator. Code `src/wayfarer/studies/ringb_insector_care.py`; results `references/p1_ringb_insector_care.json`; segments',
         f'`references/p1_access_seg_ringb_care.json`; run `{RUN.relative_to(ROOT)}`. Nothing is released; no data, generator or asset changed.', '',
         '**Not credited** (owner): the 80 t water distribution, a 4.1 t shelter, 25.1 g/cm² from an idealized shell, a one-ring stop. Both-ring stop',
         'stays the working constraint. GCR protection is not implied. The 20 g/cm² SPE target is a study target only.', '']
    c = r['couch']; g = r['garden_couch']
    L += ['## The PROTOTYPE fold-down couch', '',
          '| Item | Value | Source |', '| --- | --- | --- |']
    for k in ('length_m', 'width_m', 'top_m', 'stowed_depth_m', 'stowed_top_m', 'kit_m'):
        src = next((v for kk, v in c['provenance'].items() if k in kk), '')
        L.append(f"| {k} | {c[k]} | {src} |")
    ax = 'along the sector length, hinged on the outboard wall' if g['axis'] == 'u' else 'across the sector, hinged on the forward end wall'
    L += ['', f"Placement (searched over {r['garden_couch'].get('candidates', 'the')} positions inside the footprint the two blocks give up, x {g['freed_footprint_uv'][0]}..{g['freed_footprint_uv'][1]} m, "
          f"z {g['freed_footprint_uv'][2]}..{g['freed_footprint_uv'][3]} m): long axis {ax}; deployed sector-frame box x {g['deployed_local_min'][0]:.2f}..{g['deployed_local_max'][0]:.2f}, "
          f"z {g['deployed_local_min'][2]:.2f}..{g['deployed_local_max'][2]:.2f}, top {c['top_m']} m; stowed x {g['stowed_local_min'][0]:.2f}..{g['stowed_local_max'][0]:.2f}, "
          f"z {g['stowed_local_min'][2]:.2f}..{g['stowed_local_max'][2]:.2f}, up to {c['stowed_top_m']} m. Attendant 1 on the {'inboard' if g['axis'] == 'u' else 'aft'} side, attendant 2 at the head end "
          f"({'+' if g['head_end'] > 0 else '-'}{'x' if g['axis'] == 'u' else 'z'}). Displaced (in memory only): Garden_Rack_1 and the Mess, in both garden sectors (A3, B3), with the rack's pull rails, "
          'handles and room label. Both rings\' garden sectors carry the same swap so the 24 sector-states use one layout.', '']
    m = r['measured']
    L += [f"Measured: sector deck-to-overhead {m['sector_deck_to_overhead_m3']} m³ (owner usable {m['sector_usable_m3_owner']} m³); garden zone blocks {m['garden_blocks_m3_as_built']} m³ as built, "
          f"{m['garden_blocks_m3_swap']} m³ with the swap ({m['swapped_blocks_m3']} m³ given up); stowed couch {m['couch_stowed_m3']} m³; care-station envelope (couch + two attendants) "
          f"{m['care_station_bbox_m3']} m³, bounding surface {m['care_station_bbox_surface_m2']} m². These are geometry measurements, not a shelter or an atmosphere volume.", '']
    sc = r['sector_state_count']
    L += ['## Sector-states', '', f"The repo defines {sc['repo']} sector-states: {sc['sectors']} occupied sectors x {len(sc['states'])} ship states ({', '.join(sc['states'])}), as in "
          'access_integrated / ringb_unified. This matches the owner\'s 24. "Lost ring" is not one of them; it is added as a fifth condition (geometry = stopped; the in-sector chain uses no '
          'transfer and no other ring; lost-ring dynamics are not represented).', '',
          'Each cell is the worst of: the zone screen (care station, transfer station for A/C/K/S at x1.00/x1.08, attendant reach, egress past the deployed station, and for the garden the stowed-couch egress), '
          'the mesh station check (two attendant capsules and the kit against the built meshes) and the Blender carrier sweep from the sector hatch to the care point with the slide onto it (worst over '
          'classes, sizes, doors, seeds, families, rescuers). Deck frame for 0 g / spin / stopped (Coriolis and spin transport not credited, as in SIM-027); aft frame (aft down) for locked 1.5 g, '
          'care at the better burn couch with the garden couch stowed. Second value: unsuited classes (A/C/K) only.', '',
          '| Sector | Function | Care point (deck / aft) | 0g | spin | stopped | locked_1.5g | lost_ring | unsuited A/C/K (deck / 1.5 g) |', '| --- | --- | --- | --- | --- | --- | --- | --- | --- |']
    f = lambda x: x['status']+(f" {x['least_m']:+.3f}" if x.get('least_m') is not None else '')
    fm = lambda v: '' if v is None else f'{v:+.3f}'
    for sec, row in r['matrix'].items():
        L.append(f"| {sec} | {row['function']} | {row['0g']['care_point']} / {row['locked_1.5g']['care_point']} | {f(row['0g'])} | {f(row['spin'])} | {f(row['stopped'])} | "
                 f"{f(row['locked_1.5g'])} | {f(row['lost_ring'])} | {row['0g']['status_unsuited']} {fm(row['0g']['least_unsuited_m'])} / {row['locked_1.5g']['status_unsuited']} {fm(row['locked_1.5g']['least_unsuited_m'])} |")
    L += ['', f"Tally (24, all classes): {r['tally_24']}; unsuited only: {r['tally_24_unsuited']}; ring B's 12: {r['tally_ringB_12']}.", '',
          '### Parts per sector and frame (m)', '', '| Sector | Frame | ' + ' | '.join(['care stn', 'transfer stn', 'reach', 'egress', 'mesh att.', 'mesh kit', 'sweep+slide', 'stowed egress']) + ' | Governing |',
          '| --- | --- |' + ' --- |'*9]
    keys = ['screen care station (care point + kit + two attendants)', 'screen transfer station (worst carrier beside + rescuers)', 'screen attendant reach (0.60 m)',
            'screen egress past the deployed station (0.60 m)', 'mesh attendants (capsules, built meshes)', 'mesh kit (no overlap)', 'carrier sweep hatch -> care point + slide (worst class)',
            'screen stowed-couch egress (0.60 m)']
    for sec, row in r['matrix'].items():
        for frame in ('deck', 'aft'):
            p = row[f'_{frame}']['parts']; sw = row[f'_{frame}']['sweep']
            gov = min(((k, v) for k, v in p.items() if v is not None), key=lambda kv: kv[1], default=(None, None))
            swb = sw.get(row['0g' if frame == 'deck' else 'locked_1.5g']['care_point'])
            extra = f"; sweep worst {swb['carrier']} {swb['case']} at {swb['nearest']}" if swb and gov[0] and gov[0].startswith('carrier') else ''
            nearest = ''
            if gov[0] and gov[0].startswith('screen transfer'):
                tw = row[f'_{frame}']['screen']['transfer_worst']; nearest = f"; {tw['carrier']} {tw['part']} vs {tw['nearest']}"
            elif gov[0] and gov[0].startswith('screen care'):
                cw = row[f'_{frame}']['screen']['care']; nearest = f"; {cw['part']} vs {cw['nearest']}"
            elif gov[0] and gov[0].startswith('screen egress'):
                nearest = f"; to {row[f'_{frame}']['screen']['egress_worst']['target']}"
            L.append(f"| {sec} | {frame} | " + ' | '.join('' if p.get(k) is None else f"{p[k]:+.3f}" for k in keys) + f" | {gov[0]}{extra}{nearest} |")
    L += ['', 'Screen values are capped at +0.30 m ("at least"); sweep values at +0.10 m (hum003 CAP_M). The kit column is +0.30 when the kit box overlaps no mesh, 0.000 when it does.', '']
    L += ['### Carrier sweep per care point (worst class; per class)', '', '| Sector | Frame | Care point | Worst | Class | Route | Slide | Per class | Case |', '| --- | --- | --- | --- | --- | --- | --- | --- | --- |']
    for sec, row in r['matrix'].items():
        for frame in ('deck', 'aft'):
            for n, v in row[f'_{frame}']['sweep'].items():
                if v.get('least_m') is None:
                    L.append(f"| {sec} | {frame} | {n} | OPEN (missing {v.get('missing')}) | | | | {v.get('per_class')} | |"); continue
                L.append(f"| {sec} | {frame} | {n} | {_st(v['least_m'])} {v['least_m']:+.3f} | {v['carrier']} | {v['route_least_m']:+.3f} | "
                         f"{'' if v['slide_least_m'] is None else format(v['slide_least_m'], '+.3f')} | {', '.join(f'{c} {x:+.3f}' for c, x in v['per_class'].items())} | {v['case']} ({v['nearest']}) |")
    ra = r['ringA_comparator']
    L += ['', '## Ring A central rescue path (comparator, worst-case re-run)', '',
          'ringb_unified.survey\'s worst-case method (classes, body sizes, doors, seeds, families, two rescuers) on the built model, replacing the single-seed built_A quote. '
          'The refuge tail (hoist, slot) is not re-run: it was measured only in the ring B study workspaces (ACCESS-005: hoist +0.017 MARGINAL, slot).', '',
          '| Leg | States | Unsuited A/C/K | Suited S | Single-seed quote |', '| --- | --- | --- | --- | --- |']
    for k, v in ra['routes'].items():
        u = v.get('U'); s_ = v.get('S')
        cell = lambda x: 'not run' if not x else f"{_st(x['least_m'])} {x['least_m']:+.3f} ({x['nearest']}; {x['case']})"
        q = v.get('quoted_single_seed')
        L.append(f"| {k} | {', '.join(v['states'])} | {cell(u)} | {cell(s_)} | {'' if not q else format(q[0], '+.3f')} |")
    L += ['', '| State | All classes | Unsuited only |', '| --- | --- | --- |']
    for st, v in ra['chain'].items():
        a, u = v['all_classes'], v['unsuited']
        L.append(f"| {st} | {a['status']} {'' if a['least_m'] is None else format(a['least_m'], '+.3f')} ({a['governing']}) | {u['status']} {'' if u['least_m'] is None else format(u['least_m'], '+.3f')} ({u['governing']}) |")
    L += ['', '## OPEN (known = false; nothing invented)', '']
    for o in r['open']:
        L.append(f"- **{o['item']}** ({o['owner']}): " + '; '.join(o['must_specify']) + '.')
    L += ['', REVIEW_MARK, '']
    return '\n'.join(L)


REVIEW_MARK = """## Review of the 2026-10-13 run (Claude; numbers from the tables above)

1. **The fold-down couch works in the garden sectors at 0 g, spinning and stopped.** Garden_Rack_1 and the Mess give up a 2.15 x 2.18 m
   footprint. The best placement runs across the sector, hinged on the forward end wall (x 0.90..1.60, z 0.45..2.45, top 0.80 m; stowed
   0.30 m deep against that wall, up to 1.50 m). Attendant 1 stands on its aft side and attendant 2 at the inboard head end. Every part passes:
   care station, transfer of every class (A/C/K/S, x1.08 too) and the hatch-to-couch carrier sweep and slide, all at least +0.10 m. The
   governing value is egress to the ECLSS bay at +0.075 m, the same as the as-built layout. The swap also improves egress to Burn_Couch_1 and
   Couch_Lockers_1. The deck-frame cells of A3 and B3 PASS, and so does the lost-ring column (geometry only).
2. **Locked 1.5 g fails in every sector (6 of 6).** The garden couch is not usable aft-down; care falls back to the burn couches. Three
   things fail there:
   - Transfer onto a burn couch with two standing rescuers: unsuited worst -0.094 m (medical, garden) and -0.194 m (habitation), suited S
     -0.28 m. Beside the couch the rescuers stand on the other burn couch or under the hanging bunk; at the ends the room is too short.
   - Egress past the care station to the other burn couch: -0.066 m, against +0.08 m as built.
   - The aft-down carrier route from the hatch: down to -0.45 m at the burn couch the screen chose. The other burn couch sweeps PASS
     (+0.06..+0.10 m), but the transfer screen still fails there.
   In-sector casualty handling under thrust needs a handling concept (hoist or lowering, restraint), not furniture.
3. **The habitation and medical sectors fail even at 0 g with the existing care points (the earlier zone screen did not show this).**
   - Medical couch: the sideways slide of every class hits the Medical_Couch mesh at -0.14 m. The built couch is higher than its 0.80 m
     table at the slide position.
   - Lowest bunk: the suited S casualty does not fit the 0.81 m berth (-0.44 m). Unsuited classes are -0.14 m. The kit box overlaps the
     berth mesh.
   - Bunk care in the aisle cuts Hygiene egress to -0.142 m, against +0.15 m as built.
   - The S x1.08 transfer station beside either point is -0.03 m: the landing well and the end walls.
   The owner's 24/24 does not hold: 6 PASS / 18 FAIL (ring B 3/12). With unsuited classes only it is still 6/18, because the 0 g failures are
   unsuited too.
4. **Ring A comparator, worst-case re-run: every leg FAILs.** The single-seed quote (A1 +0.100, annulus legs +0.031..+0.081) does not
   survive the body-size and pose-family worst case:
   - A1 to the trunk: unsuited -0.103 m (Crew_Trunk, A x1.08), suited -0.171 m;
   - annulus legs: unsuited -0.065 / -0.073 m (Crew_Vestibule_1), suited -0.24 / -0.25 m (Structural_Spine);
   - spin port turn: unsuited -0.14 m, suited -0.455 m.
   Ring A's central rescue path is therefore not a passing comparator either. The refuge tail (hoist, slot) was not re-run.
5. **What the decision would need** (owner, not claimed here):
   - accept care in the garden sectors only, with others carried there (the inter-sector legs fail as in SIM-027);
   - or rework the medical couch slide side and the bunk-care aisle use;
   - and define 1.5 g in-sector handling.
   Atmosphere, shelter, SPE target, mass, shield and closure budgets stay OPEN (list above).

Limits: zone-block screen plus mesh sweeps of PROTOTYPE envelopes. Inside a closed mesh, the BVH overlap and nearest-surface tests cannot see
a carrier fully enclosed. Spin transport and Coriolis are not credited. Lost-ring dynamics are not represented. Nothing here is a medical,
pressure, radiation or structural qualification, and passing checks are not engineering proof.
"""


# ====================================================================================================================================
# Owner 2026-10-13, S&E 15_MODEL_INTERFACES!A173:A175 (answers to Claude's Doc item 2026-10-13T18:18 a1-a3)
#   a1 (A173, STUDY AUTHORIZED / PERFORMANCE HOLD): reversible hoist / lowering aid / guided load transfer for 1.5 g in-sector handling with
#      passive/manual recovery, independent anchors, no furniture-only assumption; compare local controlled lowering, restrained platform and
#      rated assist with patient + 2 rescuers + kit over the worst-case 24-state sweep. Mass, dynamics, loads, ratings: OPEN.
#   a2 (A174, PREFERRED ARCHITECTURE / FULL REACH OPEN): distributed stabilisation kept in every sector; the Garden couch is a PROTOTYPE, not
#      the sole facility; improve medical-couch / bunk handling locally; per-district function table.
#   a3 (A175, FAIL / REDESIGN REQUIRED): ring A with the same exhaustive method, per-state minima, full patient + kit + bearer route.
# Disposable as the rest of the module: hardware, rescuers and fit-out changes exist only in memory.

RUN13 = ROOT/'runs/20261013T1937Z-ringb-hoist'
OUT13_JSON = ROOT/'references/p1_ringb_insector_care_o13.json'
O13_HEAD = '## Owner 2026-10-13 (15!A173:A175)'
G0 = 9.80665
VARIANTS = {'V1': 'local controlled lowering: removable radial rail on two independent hard points (deck-wall bracket + a tie to the forward '
                  'bulkhead or the outboard side wall, placed where clearest), trolley and manual descender; the litter runs out of the hatch '
                  'under the rail, then is lowered vertically onto the couch',
            'V2': 'restrained platform: strapped incline board hinged at the hatch lip; the litter slides out of the hatch onto it and is belayed '
                  'down and along onto the couch; the board is removed after the transfer',
            'V3': 'rated assist: wall jib on a bracket (deck wall or overhead wall, between the burn couches) with a rated hoist and manual '
                  'lowering; once the litter is out of the hatch the jib carries it (order chosen per couch: shift then lower, or lower then '
                  'shift) and sets it down; the boom is removed after the set-down'}
COUCHES = ('Burn_Couch_1', 'Burn_Couch_2')
COUCH_OWN = {'Burn_Couch_1': ('Burn_Couch_1', 'Couch_Lockers_1'), 'Burn_Couch_2': ('Burn_Couch_2', 'Couch_Lockers_2')}
V3_ORDERS = ('shift_then_lower', 'lower_then_shift')
V3_BASES = ('deck_wall', 'overhead_wall')
P13 = dict(section_m=0.10, hoist_head_m=0.15, allowance_m=0.07, hatch_keepout_m=0.30, platform_t_m=0.05, platform_edge_m=0.05,
           platform_lip_m=0.10, column_m=0.20, low_lift_m=0.10, rescuer_m=0.60, guide_reach_m=0.30, ctrl_reach_m=0.40, anchor_zone_m=0.10,
           pad_m=0.08, setdown_margin_m=0.05, med_lift_clear_m=0.05, kit_inset_m=0.05, attendant_short_m=1.00, park_search_m=1.00,
           hatch_zone_m=0.10, bracket_m=0.30)
P13_SRC = {
    'section_m': 'PROTOTYPE rail / tie / boom section 0.10 x 0.10 m (no hardware is sourced)',
    'hoist_head_m': 'hum003_routes.HOIST_HEAD_M 0.15 m (PROTOTYPE trolley / sheave / brake / spreader depth between the litter top and the rail or boom)',
    'allowance_m': 'positioning allowance: rail / boom heights leave STUDY_MARGIN 0.05 + 0.02 m to the fit-out above where the room allows; the measurement decides',
    'hatch_keepout_m': 'hardware other than the hinged platform stays 0.30 m off the overhead wall in front of the sector hatch (casualty and rescuer passage)',
    'platform_t_m, platform_edge_m': 'PROTOTYPE board 0.05 m thick, 0.05 m wider than the widest carrier (S x1.08) on each side',
    'platform_lip_m': 'platform top at the hatch lip 0.10 m above the lowest point of the hatch clear circle (human_entry.landing clear_r)',
    'column_m': 'PROTOTYPE jib bracket footprint 0.20 x 0.20 m, 0.05 m off the deck wall or the overhead wall, centred between the two burn couches (z = 0)',
    'low_lift_m': 'rated assist, lower-then-shift: the litter travels 0.10 m above its set-down height',
    'rescuer_m': 'each of the two rescuers: a 0.60 x 0.60 m footprint, standing 1.90 m or kneeling 1.20 m (ringb_unified.CARE walk_w / stand_h / kneel_h)',
    'guide_reach_m, ctrl_reach_m': 'guide rescuer within 0.30 m of the set-down litter; control rescuer within 0.40 m of the device control point (descender / belay / arm controls)',
    'anchor_zone_m': 'the last 0.10 m of a hardware item at its designed anchor is its fitting, not a clearance',
    'pad_m, setdown_margin_m': 'set-down 0.08 m pad + 0.05 m margin above the care surface (this module\'s care route)',
    'med_lift_clear_m': 'lift option: the litter clears the treatment-couch foot plate by 0.05 m before it is lowered',
    'kit_inset_m': 'kit box 0.05 m inside the berth end panel (PROTOTYPE placement)',
    'attendant_short_m': 'bunk care: attendant 1 on a 1.00 m strip at one end of the berth side instead of the whole length',
    'park_search_m': 'transfer-station search: carrier parked up to 1.00 m along the care point (was 0.60 m)',
    'hatch_zone_m': 'the first 0.10 m in front of the overhead wall is the hatch frame: litter and board there are checked by the mesh sweep, not the plane screen',
    'bracket_m': 'PROTOTYPE jib wall bracket 0.30 m deep below the boom (knee brace)'}


def _spec():
    """The parameter set; WF_SPEC_ROOT may point at a snapshot of data/ while another session edits the tree (geometry inputs identical)."""
    import os
    from spec import load
    return load(Path(os.environ.get('WF_SPEC_ROOT', str(ROOT))))[0]


def _sub(a, b):
    return tuple(a[i]-b[i] for i in range(3))


def _add(a, b, k=1.0):
    return tuple(a[i]+k*b[i] for i in range(3))


def _norm(a):
    n = math.sqrt(sum(x*x for x in a))
    return tuple(x/n for x in a) if n > 1e-12 else (0.0, 0.0, 0.0)


def _cross(a, b):
    return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])


def _lerp(a, b, f):
    return tuple(a[i]+(b[i]-a[i])*f for i in range(3))


IDENT = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))


def ob_aa(lo, hi):
    """Axis-aligned box as an oriented box (centre, axes, half sizes), sector frame."""
    return (tuple((lo[i]+hi[i])/2 for i in range(3)), IDENT, tuple((hi[i]-lo[i])/2 for i in range(3)))


def ob_axis(a, b, w, t, up=(1.0, 0.0, 0.0)):
    """Box along the segment a -> b, width w across (perpendicular to the segment and to up), thickness t (toward up)."""
    d = _norm(_sub(b, a)); wv = _cross(d, up)
    wv = _norm(wv) if math.sqrt(sum(x*x for x in wv)) > 1e-6 else (0.0, 0.0, 1.0); tv = _norm(_cross(wv, d))
    return (tuple((a[i]+b[i])/2 for i in range(3)), (d, wv, tv), (math.dist(a, b)/2, w/2, t/2))


def ob_aabb(ob):
    c, ax, hs = ob
    e = [sum(abs(ax[j][i])*hs[j] for j in range(3)) for i in range(3)]
    return tuple(c[i]-e[i] for i in range(3)), tuple(c[i]+e[i] for i in range(3))


def ob_split(ob, n):
    """n boxes along the first axis (the plane screen's AABBs of an inclined / diagonal item)."""
    c, ax, hs = ob
    return [(_add(c, ax[0], -hs[0]+hs[0]*(2*i+1)/n), ax, (hs[0]/n, hs[1], hs[2])) for i in range(n)]


def ob_trim(ob, anchors, m):
    """Shorten an oriented box by m at each anchored end (axis index, side +-1): the anchor fitting is not a clearance."""
    c, ax, hs = ob; c = list(c); hs = list(hs)
    for k, sgn in anchors:
        hs[k] -= m/2; c = list(_add(c, ax[k], -sgn*m/2))
    return (tuple(c), ax, tuple(hs))


def ob_corners(ob):
    """8 corners in the order box_record / hum003 box_mesh use (index 4i + 2j + k)."""
    c, ax, hs = ob
    return [_add(_add(_add(c, ax[0], i*hs[0]), ax[1], j*hs[1]), ax[2], k*hs[2]) for i in (-1, 1) for j in (-1, 1) for k in (-1, 1)]


def litter_obs(pts, W, T, ceil):
    """Sub-boxes of a litter laid along a polyline (head first), clipped at the overhead-wall plane y = ceil (the part in the hatch and tube
    is the mesh sweep's)."""
    out = []
    for a, b in zip(pts, pts[1:]):
        if a[1] < ceil and b[1] < ceil:
            continue
        if a[1] < ceil or b[1] < ceil:
            p = _lerp(a, b, (ceil-a[1])/(b[1]-a[1]))
            a, b = (p, b) if a[1] < ceil else (a, p)
        if math.dist(a, b) > 1e-6:
            out.append(ob_axis(a, b, W, T))
    return out


def follow(path, t, L, n=10):
    """n + 1 points from the head (arc length t along the polyline) back over arc length L."""
    cum = [0.0]
    for a, b in zip(path, path[1:]):
        cum.append(cum[-1]+math.dist(a, b))

    def at(q):
        q = max(0.0, min(cum[-1], q))
        for i in range(len(path)-1):
            if q <= cum[i+1]+1e-12:
                return _lerp(path[i], path[i+1], 0.0 if cum[i+1]-cum[i] < 1e-12 else (q-cum[i])/(cum[i+1]-cum[i]))
        return path[-1]
    return [at(t-L*i/n) for i in range(n+1)], cum[-1]


def frange(a, b, st):
    n = int(math.floor((b-a)/st+1e-9))
    return [a+st*i for i in range(n+1)]


# ------------------------------------------------------------------------------------------------------------------------------------
# a1: the three 1.5 g handling variants, aft frame (locked 1.5 g, aft down: local x is height above the aft skin + xlo)

def o13_geometry(s, pl, fn, couch, variant, cars, order=None, base=None):
    """Nominal PROTOTYPE geometry of one variant at one burn couch: per carrier the in-room path waypoints (after the tube) and the explicit
    pose sequence (head, axis, label), the hardware (oriented boxes; contact = the litter rides on / hangs from it by design) and the parked
    hardware that stays during care. Every dimension is P13 or existing sector geometry."""
    import habitat_interior as hi
    import human_entry as he
    L_ = he.landing(s); xlo = pl.xlo; xhi = -xlo; ceil = pl.ceil; hx, hz, r = L_['x'], L_['z'], L_['clear_r']; p = P13
    b = next(q for q in hi.zones(s, fn) if q['name'] == couch); lo, hi_ = b['min'], b['max']; zc = (lo[2]+hi_[2])/2; top = hi_[0]
    half_max = max(v[2] for v in cars.values())/2; wmax = max(v[1] for v in cars.values()); Lmax = max(v[0] for v in cars.values())
    hatch_min = hx-(r-STUDY_MARGIN_M-half_max)          # lowest litter-centre height that passes the worst carrier through the clear circle

    def cap(u0, u1, v0, v1, above):                    # lowest fit-out bottom (sector x) over a plan footprint, above `above`
        hs = [q[4]+xlo for q in pl.rects if q[0] < u1 and q[1] > u0 and q[2] < v1 and q[3] > v0 and q[4]+xlo > above]
        return min(hs) if hs else xhi

    def line(a, b_, lab):
        n = max(1, math.ceil(math.dist(a, b_)/0.10))
        return [(_lerp(a, b_, i/n), (0.0, -1.0, 0.0), f'{lab} {i/n:.2f}') for i in range(n+1)]
    out = dict(variant=variant, couch=couch, order=order, base=base, zc=zc, top_x=top, per={}, hw=[], parked=[], hatch=dict(x=hx, z=hz, r=r))
    yb_of = lambda Lk: min(-0.05, (lo[1]+hi_[1])/2+Lk/2)
    xr_of = lambda Tk: top+p['pad_m']+Tk/2+p['setdown_margin_m']
    if variant == 'V1':
        u0, u1 = ceil+p['hatch_keepout_m']+p['allowance_m'], -0.05
        c_ = cap(u0, u1, zc-wmax/2, zc+wmax/2, top+0.30)
        rail_bot = min(hx+half_max+p['hoist_head_m'], c_-p['allowance_m']-p['section_m'])
        x_run = max(rail_bot-p['hoist_head_m']-half_max, hatch_min); rail_bot = x_run+half_max+p['hoist_head_m']; sec_ = p['section_m']
        rail = ob_aa((rail_bot, u0, zc-sec_/2), (rail_bot+sec_, u1, zc+sec_/2))
        best = None; sgn = -1.0 if zc < 0 else 1.0           # second independent anchor: a tie to the forward bulkhead or to the outboard side wall
        for k in range(int((u1-0.10-u0)/0.05)):
            ut = u0+0.05+0.05*k
            for kind in ('forward_bulkhead', 'side_wall'):
                if kind == 'forward_bulkhead':
                    ob = ob_aa((rail_bot+sec_, ut-sec_/2, zc-sec_/2), (xhi, ut+sec_/2, zc+sec_/2)); anc = [(0, 1)]
                else:
                    zw = sgn*pl.half(ut); z0, z1 = sorted((zc+sgn*sec_/2, zw)); ob = ob_aa((rail_bot, ut-sec_/2, z0), (rail_bot+sec_, ut+sec_/2, z1)); anc = [(2, int(sgn))]
                g = pl.clearance([pl.P(*ob_aabb(ob_trim(ob, anc, p['anchor_zone_m'])))+('tie',)])[0]
                if best is None or g > best[0]+1e-9:
                    best = (g, ob, ut, kind, anc)
        out['hw'] = [dict(name='V1_rail', ob=rail, contact=False, anchors=[(1, 1)]), dict(name='V1_tie', ob=best[1], contact=False, anchors=best[4])]
        out['parked'] = [dict(h) for h in out['hw']]
        out.update(x_run=x_run, cap_x=c_, control=(-0.35, 0.0), tie=dict(u=best[2], kind=best[3]))
        for key, (Lk, Wk, Tk) in cars.items():
            yb = yb_of(Lk); ya = yb-Lk-0.05; xr = xr_of(Tk)
            out['per'][key] = dict(way=[(x_run, ya, zc), (x_run, yb, zc)], poses=line((x_run, yb, zc), (xr, yb, zc), 'lower'))
    elif variant == 'V2':
        x_lip = hx-r+p['platform_lip_m']; x_end = top+p['pad_m']+p['setdown_margin_m']; u_end = lo[1]-0.05
        a = (x_lip-p['platform_t_m']/2, ceil, hz); b_ = (x_end-p['platform_t_m']/2, u_end, zc)
        out['hw'] = [dict(name='V2_platform', ob=ob_axis(a, b_, wmax+2*p['platform_edge_m'], p['platform_t_m']), contact=True, anchors=[(0, -1)])]
        out.update(x_run=x_lip, control=None, platform_end_u=u_end)      # the belaying rescuer is the route sweep's inline rescuer in the hatch
        for key, (Lk, Wk, Tk) in cars.items():
            half = Tk/2; yb = yb_of(Lk)
            fin = ((x_end+half, yb, zc), (0.0, -1.0, 0.0), 'set down')
            out['per'][key] = dict(way=[(x_lip+half, ceil, hz), (x_end+half, u_end, zc), (x_end+half, yb, zc)], poses=[fin])
    else:
        if order == 'shift_then_lower':
            c_ = cap(ceil+0.10, -0.05, min(hz, zc)-wmax/2, max(hz, zc)+wmax/2, top+0.30)
        else:
            c_ = cap(ceil+0.10, ceil+0.10+Lmax, hz-wmax/2, hz+wmax/2, top+0.30)
        x_out = max(min(hx, c_-p['allowance_m']-p['section_m']-p['hoist_head_m']-half_max), hatch_min)
        bh = x_out+half_max+p['hoist_head_m']+p['section_m']/2       # jib boom axis height (fixed); the hoist line lowers the litter
        if base == 'deck_wall':
            cu0, cu1 = -0.05-p['column_m'], -0.05; anc = [(1, 1)]
        else:
            cu0 = ceil+0.05; cu1 = cu0+p['column_m']; anc = [(1, -1)]
        cv0, cv1 = -p['column_m']/2, p['column_m']/2; cu, cv = (cu0+cu1)/2, (cv0+cv1)/2
        for key, (Lk, Wk, Tk) in cars.items():
            half = Tk/2; xr = xr_of(Tk); xl = xr+p['low_lift_m']; yb = yb_of(Lk); yo = ceil+0.10+Lk
            if order == 'shift_then_lower':
                seq = line((x_out, yo, hz), (x_out, yo, zc), 'shift')+line((x_out, yo, zc), (x_out, yb, zc), 'slide')[1:]+line((x_out, yb, zc), (xr, yb, zc), 'lower')[1:]
            else:
                seq = (line((x_out, yo, hz), (xl, yo, hz), 'lower')+line((xl, yo, hz), (xl, yo, zc), 'shift')[1:]+line((xl, yo, zc), (xl, yb, zc), 'slide')[1:]
                       + line((xl, yb, zc), (xr, yb, zc), 'set down')[1:])
            booms = []
            for h, d, lab in seq:
                cen = _add(h, d, Lk/2)
                booms.append(ob_axis((bh, cu, cv), (bh, cen[1], cen[2]), p['section_m'], p['section_m']) if math.hypot(cen[1]-cu, cen[2]-cv) > 0.05 else None)
            out['per'][key] = dict(way=[(x_out, yo, hz)], poses=seq, booms=booms)
        brk = ob_aa((bh-p['section_m']/2-p['bracket_m'], cu0, cv0), (bh+p['section_m']/2, cu1, cv1))
        out['hw'] = [dict(name='V3_jib_bracket', ob=brk, contact=False, anchors=anc)]
        out['parked'] = [dict(name='V3_jib_bracket', ob=brk, contact=False, anchors=anc)]          # boom removed after the set-down (stowage OPEN)
        out.update(x_run=x_out, cap_x=c_, control=(cu+(0.30 if base != 'deck_wall' else -0.30), 0.0), base=base, boom_x=bh)
    for key, (Lk, Wk, Tk) in cars.items():
        q = out['per'][key]; q['final'] = q['poses'][-1]; q['tube'] = (hx, ceil-Lk-0.5, hz); q['dims'] = (Lk, Wk, Tk)
    return out


def o13_frames(g, key, ceil):
    """Plane-screen frames of one carrier: [(litter oriented boxes, time-dependent hardware)] along the path (head every 0.10 m once it is in
    the room) and at each explicit pose."""
    q = g['per'][key]; Lk, Wk, Tk = q['dims']; path = [q['tube']]+list(q['way']); frames = []
    _, tot = follow(path, 0.0, Lk)
    t0 = math.dist(path[0], path[1])*(ceil-path[0][1])/max(1e-9, path[1][1]-path[0][1]) if path[1][1] > ceil else 0.0
    for t in frange(max(t0, 0.0), tot, 0.10)+[tot]:
        pts, _ = follow(path, t, Lk); obs = litter_obs(pts, Wk, Tk, ceil)
        if obs:
            frames.append((obs, [], f'path {t:.2f}'))
    for i, (h, d, lab) in enumerate(q['poses']):
        pts = [_add(h, d, Lk*k/10) for k in range(11)]
        frames.append((litter_obs(pts, Wk, Tk, ceil), [q['booms'][i]] if q.get('booms') and q['booms'][i] is not None else [], lab))
    return frames


def _gap7(a, b):
    return _gap(((a[0], a[2], a[4]), (a[1], a[3], a[5])), ((b[0], b[2], b[4]), (b[1], b[3], b[5])))


def rescuer_scores(pl, U0, V0, size, H, obstacles):
    """Least clearance (capped CAP_M) of every candidate footprint box (u0, v0, size, 0..H) to the room (Plane.clearance rules) and the
    obstacle boxes, vectorised."""
    import numpy as np
    U1, V1 = U0+size, V0+size; g = np.full(U0.shape, CAP_M)

    def box_gap(r):
        gu = np.maximum(U0-r[1], r[0]-U1); gv = np.maximum(V0-r[3], r[2]-V1); gh = np.full(U0.shape, max(0.0-r[5], r[4]-H))
        mx = np.maximum(np.maximum(gu, gv), gh)
        pos = np.sqrt(np.maximum(gu, 0)**2+np.maximum(gv, 0)**2+np.maximum(gh, 0)**2)
        return np.where(mx < 0, mx, pos)
    for r in list(pl.rects)+list(obstacles):
        g = np.minimum(g, box_gap(r))
    zh = np.array([min(pl.half(a), pl.half(b)) if pl.frame == 'aft' else pl.half(-H) for a, b in zip(U0.ravel(), U1.ravel())]).reshape(U0.shape)
    for w in (U0-pl.urng[0], pl.urng[1]-U1, V0+zh, zh-V1):
        g = np.where(w < -1e-9, np.minimum(g, w), g)
    return g


def rescuer_candidates(pl, obstacles, near, c, n=4):
    """Up to n diverse best stations (footprint boxes, standing or kneeling) inside the mask `near`: (score, box, stance), at least 0.25 m apart."""
    import numpy as np
    sz = P13['rescuer_m']; us = np.array(frange(pl.urng[0], pl.urng[1]-sz, 0.05)); vs = np.array(frange(-2.9, 2.9-sz, 0.05))
    U0, V0 = np.meshgrid(us, vs, indexing='ij'); allc = []
    for stance, H in (('standing', c['stand_h_m']), ('kneeling', c['kneel_h_m'])):
        sc = np.where(near(U0, V0), rescuer_scores(pl, U0, V0, sz, H, obstacles), -9.0)
        allc += [(float(sc[i, j]), (float(U0[i, j]), float(U0[i, j])+sz, float(V0[i, j]), float(V0[i, j])+sz, 0.0, H), stance)
                 for i, j in zip(*np.nonzero(sc > -9.0))]
    allc.sort(key=lambda q: (-round(q[0], 3), q[2] != 'standing')); out = []
    for q in allc:
        if all(math.hypot(q[1][0]-o[1][0], q[1][2]-o[1][2]) >= 0.25 for o in out):
            out.append(q)
        if len(out) >= n:
            break
    return out


def o13_assess(s, pl, pa, fn, g, key, c, care_extra, pl_lit):
    """Plane-screen parts of one variant / couch / carrier (aft frame)."""
    p = P13; own = COUCH_OWN[g['couch']]; frames = o13_frames(g, key, pl.ceil)
    P = lambda ob, n: pl.P(*ob_aabb(ob))+(n,)
    static = [h for h in g['hw']]
    hz0 = pl.ceil+p['hatch_zone_m']

    def clip(bs):                                        # the hatch-frame zone in front of the overhead wall is the mesh sweep's
        return [(max(b_[0], hz0),)+tuple(b_[1:]) for b_ in bs if b_[1] > hz0+1e-6]
    lit = clip([P(o, 'litter') for f in frames for o in f[0]])
    lit_room = pl_lit.clearance(lit)
    hw_boxes, nc = [], []                                # plane boxes of the hardware (anchor fittings trimmed); nc: not in designed contact
    for h in static:
        ob = ob_trim(h['ob'], h['anchors'], p['anchor_zone_m'])
        bx = clip([P(o, h['name']) for o in ob_split(ob, 10)]) if h['name'] == 'V2_platform' else [P(ob, h['name'])]
        hw_boxes += bx; nc += [] if h['contact'] else bx
    booms = [P(o, 'V3_boom') for f in frames for o in f[1]]
    hw_room = pl.clearance(hw_boxes+booms)
    hx, hz, r = g['hatch']['x'], g['hatch']['z'], g['hatch']['r']
    passage = (pl.ceil, pl.ceil+p['hatch_keepout_m'], hz-r, hz+r, hx-r-pl.xlo, hx+r-pl.xlo, 'hatch_passage')
    hp = min([(round(_gap7(b, passage), 3), b[6]) for b in hw_boxes+booms if b[6] != 'V2_platform'], default=(CAP_M, None))
    hw_lit = (CAP_M, None, None)                         # non-contact hardware vs the litter at the same instant
    for f in frames:
        for lb in clip([P(o, 'litter') for o in f[0]]):
            for hb in nc:
                gg = _gap7(lb, hb)
                if gg < hw_lit[0]:
                    hw_lit = (gg, hb[6], f[2])
    q = g['per'][key]; Lk, Wk, Tk = q['dims']; h0, d0, _ = q['final']
    fin_obs = litter_obs([_add(h0, d0, Lk*k/10) for k in range(11)], Wk, Tk, pl.ceil); fin_boxes = clip([P(o, 'litter_set_down') for o in fin_obs])
    fin = (min(b[0] for b in fin_boxes), max(b[1] for b in fin_boxes), min(b[2] for b in fin_boxes), max(b[3] for b in fin_boxes))
    sz = p['rescuer_m']; obst = lit+hw_boxes+booms

    def near_fin(U0, V0):
        import numpy as np
        gu = np.maximum(np.maximum(fin[0]-(U0+sz), U0-fin[1]), 0); gv = np.maximum(np.maximum(fin[2]-(V0+sz), V0-fin[3]), 0)
        return np.hypot(gu, gv) <= p['guide_reach_m']

    def near_ctl(U0, V0):
        import numpy as np
        cu = np.maximum(np.maximum(U0-g['control'][0], g['control'][0]-(U0+sz)), 0); cv = np.maximum(np.maximum(V0-g['control'][1], g['control'][1]-(V0+sz)), 0)
        return np.hypot(cu, cv) <= p['ctrl_reach_m']
    # rescuers take station before the board (V2) is lowered; the litter is at its set-down; the other hardware is rigged
    env_reach = fin_boxes+[b for b in hw_boxes if b[6] != 'V2_platform']+[P(o, 'V3_boom') for o in (frames[-1][1] if frames else [])]
    env_dep = fin_boxes+hw_boxes+[P(o, 'V3_boom') for o in (frames[-1][1] if frames else [])]
    fld0 = pl.field(env_reach); B0 = pl.widest(fld0, pl.start(fld0)); base_eg = egress_values(pa, c, skip=own)

    def reach_of(rb):
        u0, u1, v0, v1 = rb[:4]; pts = []
        for f in [i/10 for i in range(11)]:
            pts += [(u0+(u1-u0)*f, v0), (u0+(u1-u0)*f, v1), (u0, v0+(v1-v0)*f), (u1, v0+(v1-v0)*f)]
        return round(max(pl.at(fld0, B0, pt) for pt in pts)-c['walk_w_m']/2, 3)

    def egress_of(rbs):
        fld = pl.field(env_dep+list(rbs)); B2 = pl.widest(fld, pl.start(fld))
        eg = {n: round(max(pl.at(fld, B2, pt) for pt in ps)-c['walk_w_m']/2, 3) for n, ps in pl.targets(skip=own) if ps}
        return egress_vs(eg, base_eg)
    gs = rescuer_candidates(pl, obst, near_fin, c)
    best = None
    for gc in gs:
        gb = gc[1]+('rescuer_guide',)
        if g['control'] is None:
            cands = [(None, None)]
        else:
            cs_ = rescuer_candidates(pl, obst+[gb], near_ctl, c)
            cands = [(cc, cc[1]+('rescuer_control',)) for cc in cs_]
        for cc, cb in cands:
            rbs = [gb]+([cb] if cb else [])
            eg = egress_of(rbs); rch = {b_[6]: reach_of(b_) for b_ in rbs}
            key_ = min([gc[0]]+([cc[0]] if cc else [])+list(rch.values())+[eg['egress_worst']['clearance_m']])
            if best is None or key_ > best[0]+1e-9:
                best = (key_, gc, cc, eg, rch)
    _, gc, cc, egr, reach = best
    resc = {'guide': dict(clearance_m=round(gc[0], 3), box=list(gc[1]), stance=gc[2])}
    if cc:
        resc['control'] = dict(clearance_m=round(cc[0], 3), box=list(cc[1]), stance=cc[2])
    # care after set-down with the parked hardware (V2's board removed): care point + kit + two attendants, best side / end / stance
    import habitat_interior as hi
    plc = care_extra(g)
    b = next(x for x in hi.zones(s, fn) if x['name'] == g['couch']); u0, u1, v0, v1, _, h1 = plc.P(b['min'], b['max'])
    side = -1 if (v0+v1)/2 > 0 else 1; care = None
    for end in (-1, 1):
        for shift in (0.0, 0.1, 0.2, 0.3):
            for stance in ('standing', 'kneeling'):
                env = env_station((u0, u1, v0, v1), side, end, 'u', c, h1, shift=shift, stance=stance)
                cg = plc.clearance(env, exclude=own)
                if care is None or cg[0] > care[0][0]+1e-9:
                    care = (cg, env, dict(side=side, head_end=end, head_shift_m=shift, stance=stance))
    parts = {'litter swept envelope vs room (plane)': round(lit_room[0], 3), 'hardware vs room (plane)': round(hw_room[0], 3),
             'hardware vs hatch passage (plane)': hp[0], 'hardware vs litter, same instant (plane)': round(hw_lit[0], 3),
             'rescuer guide (plane)': resc['guide']['clearance_m'], 'rescuer control (plane)': resc['control']['clearance_m'] if 'control' in resc else None,
             'rescuer reach (0.60 m path)': min(reach.values()), 'egress past the deployed aid (0.60 m)': egr['egress_worst']['clearance_m'],
             'care after set-down, aid parked (plane)': round(care[0][0], 3)}
    loc = lambda bx: [list(x) for x in local_box(pl, bx[:6])]
    return dict(parts=parts, nearest={'litter': lit_room[1:], 'hardware': hw_room[1:], 'hatch_passage': hp[1], 'hw_litter': hw_lit[1:], 'care': care[0][1:]},
                rescuers={k: dict(v, local=loc(tuple(v['box']))) for k, v in resc.items()}, reach=reach, egress=egr,
                care=dict(care[2], env=[[round(float(x), 3) if not isinstance(x, str) else x for x in e] for e in care[1]],
                          env_local=[loc(e)+[e[6]] for e in care[1]]))


def o13_screen(args):
    """Blender (numpy): plane screen of every variant at both burn couches of one function, worst over carriers; JSON for the mesh jobs."""
    s = _spec(); c = couch_spec(s); cars = carriers_plan(); fn = args.fn
    scr = json.loads((RUN/'screen.json').read_text()); extra = []
    if fn == GARDEN:
        extra = [(tuple(scr['garden_couch']['stowed_local_min']), tuple(scr['garden_couch']['stowed_local_max']), 'care_couch_stowed')]
    drop = SWAP if fn == GARDEN else ()
    import human_entry as he
    L_ = he.landing(s); ceil = L_['ceiling']
    # sector fixtures the aft plane does not carry (from human_entry.landing): the landing chase column and the open hatch leaf with its rails
    # on the overhead wall; obstacles for hardware, rescuers, egress and care (the litter's hatch passage is the mesh sweep's)
    lz = (L_['z']-L_['frame_r'], L_['leaf_open_z']+L_['leaf_r']+0.05); lo_, lf = L_['leaf_open']
    fix = [((L_['well_x'][0], ceil, L_['chase_z'][0]), (L_['well_x'][1], 0.0, L_['chase_z'][1]), 'landing_chase'),
           ((-L_['leaf_r'], lo_, L_['leaf_open_z']-L_['leaf_r']), (L_['leaf_r'], lf, L_['leaf_open_z']+L_['leaf_r']), 'hatch_leaf_open'),
           ((-L_['frame_r']-0.04, lo_, lz[0]), (-L_['frame_r'], lf, lz[1]), 'hatch_rail_1'), ((L_['frame_r'], lo_, lz[0]), (L_['frame_r']+0.04, lf, lz[1]), 'hatch_rail_2')]
    pl = Plane(s, fn, 'aft', drop=drop, extra=extra+fix); pa = Plane(s, fn, 'aft', extra=fix); pl_lit = Plane(s, fn, 'aft', drop=drop, extra=extra)

    def care_extra(g):
        return Plane(s, fn, 'aft', drop=drop, extra=extra+fix+[tuple(ob_aabb(h['ob']))+(h['name'],) for h in g['parked']])
    ser = lambda x: json.loads(json.dumps(x, default=lambda o: list(o)))
    out = dict(function=fn, couches={}); t0 = time.time()
    for couch in COUCHES:
        out['couches'][couch] = {}
        for v in VARIANTS:
            combos = [(o, b_) for o in V3_ORDERS for b_ in V3_BASES] if v == 'V3' else [(None, None)]
            for order, base in combos:
                g = o13_geometry(s, pl, fn, couch, v, cars, order, base); per = {}
                for key in cars:
                    per[key] = o13_assess(s, pl, pa, fn, g, key, c, care_extra, pl_lit)
                    print('WF_O13_SCREEN', fn, couch, v, order, base, key, per[key]['parts'], flush=True)
                worst = {k: min((per[c_]['parts'][k] for c_ in per if per[c_]['parts'][k] is not None), default=None) for k in next(iter(per.values()))['parts']}
                gov = min(x for x in worst.values() if x is not None)
                rec = dict(geometry=ser({k: v_ for k, v_ in g.items() if k != 'per'}), per_geometry=ser(g['per']), per=per, worst=worst, governing_m=gov)
                out['couches'][couch][v if v != 'V3' else f'V3:{order}:{base}'] = rec
            if v == 'V3':          # the jib's order and base: the better worst-carrier plane value; the others are kept for the report
                alts = {k_: x['governing_m'] for k_, x in out['couches'][couch].items() if k_.startswith('V3:')}
                pick = max(alts, key=lambda k_: alts[k_])
                out['couches'][couch]['V3'] = dict(out['couches'][couch][pick], order=pick.split(':')[1], base=pick.split(':')[2], alternative=alts)
    out['seconds'] = round(time.time()-t0, 1)
    RUN13.mkdir(parents=True, exist_ok=True); (RUN13/f'screen13_{fn}.json').write_text(json.dumps(out, indent=1, default=float)+'\n')


# ------------------------------------------------------------------------------------------------------------------------------------
# Blender mesh checks (a1 variants, a2 local changes)

def _world(s, j, k):
    """Sector frame -> world: point map, direction map and the inverse point map (rigid)."""
    W = sector_world(s, j, k); o = W((0.0, 0.0, 0.0)); M = [_sub(W(e), o) for e in IDENT]
    R = lambda v: tuple(sum(M[i][a]*v[i] for i in range(3)) for a in range(3))
    inv = lambda p: tuple(sum(M[i][a]*(p[a]-o[a]) for a in range(3)) for i in range(3))
    return W, R, inv


def ob_world(W, R, ob):
    import numpy as np
    c, ax, hs = ob
    return [(np.asarray(W(c)), tuple(np.asarray(R(a)) for a in ax), hs)]


def ob_margin(walls, bx, cap=None):
    """hum003_routes.margin's box bisection for a given oriented box list: (margin, nearest), at most cap."""
    import hum003_routes as hr
    cap = hr.CAP_M if cap is None else cap
    if walls.overlaps(*hr.box_mesh(bx, cap)) is None:
        return (cap, None)
    lo, hi = -0.14, cap; name = walls.overlaps(*hr.box_mesh(bx, lo))
    if name is not None:
        return (lo, name)
    name = walls.overlaps(*hr.box_mesh(bx, hi))
    for _ in range(7):
        mid = (lo+hi)/2; n2 = walls.overlaps(*hr.box_mesh(bx, mid))
        if n2 is None:
            lo = mid
        else:
            hi, name = mid, n2
    return (round(lo, 3), name)


def flat_roll(d, up):
    import hum003_routes as hr
    import numpy as np
    _, w0, t0 = hr.frame(d, 0.0)
    return math.atan2(-float(np.dot(w0, up)), float(np.dot(t0, up)))


def drop_parts(s, records, j, k, block_name, parts, fn):
    """Remove whitebox parts (sector_whitebox.shapes of block_name, e.g. the treatment-couch foot plate) from the evaluated records of sector
    (j, k) in memory: the record's 8-vertex box groups whose sector-frame bounds match the part are dropped."""
    import habitat_interior as hi
    import sector_whitebox as sw
    blocks = hi.zones(s, fn); b = next(q for q in blocks if q['name'] == block_name)
    boxes = [(q['min'], q['max']) for q in sw.shapes(s, b, blocks) if q['part'] in parts]
    _, _, inv = _world(s, j, k); out = []; dropped = 0
    for rcd in records:
        if rcd['name'] != block_name:
            out.append(rcd); continue
        loc = [inv(v) for v in rcd['vs']]
        if not all(-1.8 < x < 1.8 and -3.1 < y < 0.1 and -3.1 < z < 3.1 for x, y, z in loc):
            out.append(rcd); continue
        kill = set()
        for gi in range(len(loc)//8):
            grp = loc[8*gi:8*gi+8]; glo = [min(v[a] for v in grp) for a in range(3)]; ghi = [max(v[a] for v in grp) for a in range(3)]
            if any(all(abs(glo[a]-bl[a]) < .02 and abs(ghi[a]-bh[a]) < .02 for a in range(3)) for bl, bh in boxes):
                kill.add(gi)
        if kill:
            dropped += len(kill)
            rcd = dict(rcd, fs=[f for f in rcd['fs'] if f[0]//8 not in kill])
        out.append(rcd)
    return out, dropped


def o13_sweep(args):
    """a1 mesh job: the variant's carrier route (hatch -> device) and pose sequence with ringb_unified.survey's worst-case method, the
    hardware against the built meshes, the two rescuers (capsules) and the care station with the parked hardware."""
    import bpy
    import numpy as np
    import casualty_sweep as cs
    import hum003_routes as hr
    import ringb_unified as ru
    assert abs(hr.HOIST_HEAD_M-P13['hoist_head_m']) < 1e-9
    s = _spec(); scr = json.loads((RUN/'screen.json').read_text()); j, k = SECTORS[args.sector]; fn = s['habitat']['layout']['functions'][k-1]
    rk = getattr(args, 'rack', None)                     # 2026-10-13c: Garden_Rack_1 variant (rack in its 1.5 g emergency state, couch stowed)
    sc_all = json.loads(((RUN13C/f'screen13c_{rk}.json') if rk else (RUN13/f'screen13_{fn}.json')).read_text())
    sc = sc_all['couches'][args.couch][args.variant]
    geo, perg = sc['geometry'], sc['per_geometry']
    bpy.ops.wm.open_mainfile(filepath=str(ROOT/'assets/wayfarer/WF_WAYFARER_001.blend')); ins = cs.load_inspect()
    W, R, _ = _world(s, j, k); up = np.asarray(R((1.0, 0.0, 0.0)))
    route = hr.trunk_routes(s)['AB'[j-1]+str(k)]['path']; i4 = max(i for i, q in enumerate(route) if q[0] == 4)
    tob = lambda o: (tuple(o[0]), tuple(tuple(a) for a in o[1]), tuple(o[2]))
    hw = [dict(h, ob=tob(h['ob'])) for h in geo['hw']]; parked = [dict(h, ob=tob(h['ob'])) for h in geo['parked']]
    hw_rec = lambda items: [box_record([W(p_) for p_ in ob_corners(h['ob'])], f"Study_{h['name']}", kind='study_hw') for h in items]
    car0 = hr.CARRIERS[args.carrier]; t0 = time.time()
    out = dict(sector=args.sector, variant=args.variant, couch=args.couch, carrier=args.carrier, order=sc.get('order'), points={}, mesh={}, rack=rk)
    o = out['points'].setdefault(args.couch, dict(sweeps=[], families=[], slide=[]))
    for door, scale in ((1.0, 1.0), (1.0, hr.BODY_SCALE_LARGE), (DOOR_PARTIAL, 1.0)):
        base = (rack_records(s, cs.scene(s, ins, door), _rk_boxes(sc_all['geometry']['aft']), sc_all['couch']['stowed'], 'stowed') if rk
                else swapped_records(s, cs.scene(s, ins, door), scr, 'stowed'))
        car = hr.scaled(car0, scale); key = f'{args.carrier} x{scale:.2f}'
        q = perg[key]; Lk = q['dims'][0]
        records = base+hw_rec([h for h in hw if not h['contact']])
        path = [route[i4]]+[('C', W(tuple(p_))) for p_ in q['way']]
        poses = []
        for h, d, lab in q['poses']:
            dw = np.asarray(R(tuple(d))); poses.append((W(tuple(h)), tuple(dw), flat_roll(dw, up), lab))
        pts = [p_ for _, p_ in path]+[pp[0] for pp in poses]+[tuple(np.asarray(pp[0])+np.asarray(pp[1])*Lk) for pp in poses]
        walls = hr.Walls(records, pts)
        seeds = ru.SEEDS_NOMINAL if (door, scale) == (1.0, 1.0) else (ru.SEEDS_LARGE if scale != 1.0 else (301,))
        for seed in seeds:
            r = hr.sweep_route(walls, car, path, np.random.default_rng(seed), couch=True)
            o['sweeps'].append(dict(door=door, scale=scale, seed=seed, carrier_m=r['least_m'], carrier_nearest=r['nearest'], staff_m=r['staff_least_m'],
                                    staff_nearest=r['staff_nearest'], by_zone={z: v['least_m'] for z, v in r['by_zone'].items()}))
            sp = hr.sweep_poses(walls, car, poses, np.random.default_rng(seed))
            o['slide'].append(dict(door=door, scale=scale, seed=seed, least_m=sp['least_m'], nearest=sp['nearest'], at=sp['at']))
            print('WF_O13_SWEEP', args.sector, args.variant, args.couch, args.carrier, door, scale, seed, r['least_m'], r['nearest'], r['staff_least_m'], 'poses', sp['least_m'], sp['nearest'], sp['at'], flush=True)
        f = hr.family_sweep(walls, car, path, couch=True); f.update(door=door, scale=scale); o['families'].append(f)
        print('WF_O13_FAM', args.sector, args.variant, args.couch, args.carrier, door, scale, f['worst_family_m'], f['best_family_m'], f['staff_least_m'], flush=True)
        if door != 1.0:
            continue
        # mesh checks at doors open: hardware (anchor fittings trimmed), boom at every pose, rescuers, care station with the parked aid
        m = {}
        hw_walls_pts = [W(p_) for h in hw for p_ in ob_corners(h['ob'])]+pts
        wb = hr.Walls(base, hw_walls_pts)
        for h in hw:
            ob = ob_trim(h['ob'], [tuple(a) for a in h['anchors']], P13['anchor_zone_m'])
            m[h['name']] = ob_margin(wb, ob_world(W, R, ob))
        if q.get('booms'):
            bm = [ob_margin(hr.Walls(base, [W(p_) for p_ in ob_corners(tob(b))]), ob_world(W, R, ob_trim(tob(b), [(0, -1)], P13['column_m']/2+0.05)))
                  for b in q['booms'] if b is not None]
            m['V3_boom'] = min(bm, key=lambda x: x[0])
        res_rec = base+hw_rec(hw if args.variant != 'V2' else [])
        rs = {}
        for nm, rv in sc['per'][key]['rescuers'].items():
            lo, hi = rv['local']; cen = [(lo[a]+hi[a])/2 for a in range(3)]; Rr = hr.STAFF_R_M; H = hi[0]-lo[0]
            a_, b_ = W((lo[0]+Rr+0.10, cen[1], cen[2])), W((lo[0]+H-Rr, cen[1], cen[2]))
            rs[nm] = hr.Walls(res_rec, [a_, b_]).capsule(a_, b_, Rr)
        m['rescuers'] = {nm: (round(v[0], 3), v[1]) for nm, v in rs.items()}
        care_rec = base+hw_rec(parked); cs_ = {}
        for e in sc['per'][key]['care']['env_local']:
            lo, hi, nm = e[0], e[1], e[2]; cen = [(lo[a]+hi[a])/2 for a in range(3)]
            if nm.startswith('attendant'):
                Rr = hr.STAFF_R_M; H = hi[0]-lo[0]; a_, b_ = W((lo[0]+Rr+0.10, cen[1], cen[2])), W((lo[0]+H-Rr, cen[1], cen[2]))
                v = hr.Walls([x for x in care_rec if x['name'] != args.couch], [a_, b_]).capsule(a_, b_, Rr); cs_[nm] = (round(v[0], 3), v[1])
            else:
                ob = ob_aa(tuple(lo), tuple(hi)); cs_[nm] = ob_margin(hr.Walls(care_rec, [W(p_) for p_ in ob_corners(ob)]), ob_world(W, R, ob))
        m['care'] = cs_
        out['mesh'][key] = m
        print('WF_O13_MESH', args.sector, args.variant, args.couch, key, m, flush=True)
    out['seconds'] = round(time.time()-t0, 1); out['done'] = True
    d = (RUN13C if rk else RUN13)/'sweep'; d.mkdir(parents=True, exist_ok=True)
    (d/(f'{args.sector}_{rk}_{args.variant}_{args.couch}_{args.carrier}.json' if rk else f'{args.sector}_{args.variant}_{args.couch}_{args.carrier}.json')).write_text(json.dumps(out, indent=1, default=str)+'\n')


A2_OPTIONS = {'WORK_MEDICAL_OPS': {'fold_foot': 'treatment-couch foot plate hinged, folded to table level for the transfer (PROTOTYPE); room labels moved',
                                   'lift': 'litter slid across 0.05 m above the as-built foot plate, then lowered (foot plate kept); room labels moved'},
              'HABITATION': {'fold_grab': 'Bunk_1 grab bar and step rung in the berth opening hinged / folded flat for the transfer (PROTOTYPE); room labels moved; '
                                          'kit inset 0.05 m; attendant 1 on a 1.00 m strip'}}
A2_PARTS = {'fold_foot': ('Medical_Couch', ('Foot',)), 'fold_grab': ('Bunk_1', ('Grab_Bar', 'Step_Rung'))}
A2_SIGNS = ('Sector_Fit_Room_Medical_Couch', 'Sector_Fit_Room_Medical_Couch_Text', 'Sector_Fit_Room_Bunk_1', 'Sector_Fit_Room_Bunk_1_Text',
            'Sector_Fit_Room_Bunk_2', 'Sector_Fit_Room_Bunk_2_Text')


def care13_routes(s, scr, j, k, car, key, off=None, lift=0.0):
    """care_routes' deck branch with an along-couch offset override and an optional lift: the carrier slides across at the lifted height and is
    then lowered onto the care point."""
    import numpy as np
    import hum003_routes as hr
    import human_entry as he
    import habitat_interior as hi_
    fn = s['habitat']['layout']['functions'][k-1]; L_ = he.landing(s); W = sector_world(s, j, k)
    route = hr.trunk_routes(s)['AB'[j-1]+str(k)]['path']; i4 = max(i for i, q in enumerate(route) if q[0] == 4)
    hl = hr.length(car); half = car['size'][2]/2 if car['shape'] == 'box' else car['radius']; wid = car['size'][1] if car['shape'] == 'box' else 2*car['radius']
    fr = scr['functions'][fn]['deck']; name = fr['care_point']; b = next(q for q in hi_.zones(s, fn) if q['name'] == name); lo, hi = b['min'], b['max']
    st = fr['station']; side = st['side']; off = st['transfer'][key]['offset_m'] if off is None else off
    ys = -(fr['surface_m']+0.08+half+0.05); yl = ys-lift
    bb = (lo[2]-wid/2-0.10) if side < 0 else (hi[2]+wid/2+0.10); bc = (lo[2]+hi[2])/2; am = (lo[0]+hi[0])/2+off
    best = None
    for sgn in (1, -1):
        ae = am+sgn*hl/2; as_ = am-sgn*(hl/2+0.05)
        v1 = np.subtract((as_, bb), (L_['x'], L_['z'])); v2 = np.array((ae-as_, 0.0))
        ang = math.acos(max(-1, min(1, float(np.dot(v1, v2)/np.linalg.norm(v1)/np.linalg.norm(v2)))))
        if best is None or ang < best[0]:
            best = (ang, as_, ae)
    _, as_, ae = best
    path = [route[i4], ('5', W((L_['x'], cs_carry(), L_['z']))), ('C', W((as_, cs_carry(), bb))), ('C', W((ae, yl, bb)))]
    d = tuple(np.subtract(W((as_, ys, bb)), W((ae, ys, bb)))/np.linalg.norm(np.subtract(W((as_, ys, bb)), W((ae, ys, bb)))))
    poses = [(W((ae, yl, bb+(bc-bb)*t)), d, 0.0, f'slide {t:.1f}') for t in np.linspace(0, 1, 6)]
    if lift > 0:
        n = max(1, math.ceil(lift/0.10))
        poses += [(W((ae, yl+(ys-yl)*i/n, bc)), d, 0.0, f'lower {i/n:.2f}') for i in range(1, n+1)]
    return name, path, poses


def o13_care(args):
    """a2 mesh job (deck frame: 0 g / spin / stopped): the carrier sweep + slide onto the medical couch or the lowest berth with a local
    PROTOTYPE change, best along-couch offset; with carrier A also the care-station attendants and kit with the change, the room labels moved
    and (bunk) the kit inset."""
    import bpy
    import numpy as np
    import casualty_sweep as cs
    import hum003_routes as hr
    import ringb_unified as ru
    import habitat_interior as hi
    import sector_whitebox as sw
    s = _spec(); scr = json.loads((RUN/'screen.json').read_text()); j, k = SECTORS[args.sector]; fn = s['habitat']['layout']['functions'][k-1]
    bpy.ops.wm.open_mainfile(filepath=str(ROOT/'assets/wayfarer/WF_WAYFARER_001.blend')); ins = cs.load_inspect()
    car0 = hr.CARRIERS[args.carrier]; t0 = time.time(); opt = args.option
    out = dict(sector=args.sector, option=opt, carrier=args.carrier, points={}, dropped={})
    lift = 0.0
    if opt == 'lift':
        blocks = hi.zones(s, fn); b = next(q for q in blocks if q['name'] == 'Medical_Couch')
        foot = next(q for q in sw.shapes(s, b, blocks) if q['part'] == 'Foot')
        lift = (-foot['min'][1]+P13['med_lift_clear_m'])-(scr['functions'][fn]['deck']['surface_m']+P13['pad_m']+P13['setdown_margin_m'])
        out['lift_m'] = round(lift, 3)
    offs = (None, 0.0)
    for door, scale in ((1.0, 1.0), (1.0, hr.BODY_SCALE_LARGE), (DOOR_PARTIAL, 1.0)):
        records = swapped_records(s, cs.scene(s, ins, door), scr, 'deployed')
        if opt in A2_PARTS:
            for jj in (1, 2):
                records, n = drop_parts(s, records, jj, k, A2_PARTS[opt][0], A2_PARTS[opt][1], fn); out['dropped'][str(jj)] = n
        with_labels = records; records = [q for q in records if q['name'] not in A2_SIGNS]       # room labels moved (every option)
        car = hr.scaled(car0, scale); key = f'{args.carrier} x{scale:.2f}'
        for off in offs:
            name, path, slide = care13_routes(s, scr, j, k, car, key, off=off, lift=lift)
            o = out['points'].setdefault(f"{name}@{'screen' if off is None else off}", dict(sweeps=[], families=[], slide=[]))
            walls = hr.Walls(records, [p for _, p in path]+[q[0] for q in slide])
            seeds = ru.SEEDS_NOMINAL if (door, scale) == (1.0, 1.0) else (ru.SEEDS_LARGE if scale != 1.0 else (301,))
            for seed in seeds:
                r = hr.sweep_route(walls, car, path, np.random.default_rng(seed), couch=True)
                o['sweeps'].append(dict(door=door, scale=scale, seed=seed, carrier_m=r['least_m'], carrier_nearest=r['nearest'], staff_m=r['staff_least_m'],
                                        staff_nearest=r['staff_nearest'], by_zone={z: v['least_m'] for z, v in r['by_zone'].items()}))
                sp = hr.sweep_poses(walls, car, slide, np.random.default_rng(seed))
                o['slide'].append(dict(door=door, scale=scale, seed=seed, least_m=sp['least_m'], nearest=sp['nearest'], at=sp['at']))
                print('WF_O13_CARE', args.sector, opt, off, args.carrier, door, scale, seed, r['least_m'], r['nearest'], r['staff_least_m'], 'slide', sp['least_m'], sp['nearest'], flush=True)
            f = hr.family_sweep(walls, car, path, couch=True); f.update(door=door, scale=scale); o['families'].append(f)
        if door == 1.0 and scale == 1.0 and args.carrier == 'A':
            # the screen's care station with the change, then also the room labels moved, then (bunk) the kit inset from the end panel
            pl = Plane(s, fn, 'deck'); st = scr['functions'][fn]['deck']['station']; W, R, _ = _world(s, j, k); res = {}
            for tag, recs in (('change, labels kept', with_labels), ('change+labels', records)):
                cs_ = {}
                for e in st['env']:
                    lo, hi_ = local_box(pl, e[:6]); cen = [(lo[a]+hi_[a])/2 for a in range(3)]
                    if e[6].startswith('attendant'):
                        Rr = hr.STAFF_R_M; a_, b_ = W((cen[0], -(Rr+0.10), cen[2])), W((cen[0], -(scr['couch']['stand_h_m']-Rr), cen[2]))
                        v = hr.Walls([q for q in recs if q['name'] != scr['functions'][fn]['deck']['care_point']], [a_, b_]).capsule(a_, b_, Rr); cs_[e[6]] = (round(v[0], 3), v[1])
                    else:
                        variants_ = {'as screened': (lo, hi_)}
                        if fn == 'HABITATION':          # kit moved off the berth end panel by panel + inset, length kept
                            bk = next(q for q in hi.zones(s, fn) if q['name'] == 'Bunk_1'); sh = s['sector_whitebox']['panel_m']+P13['kit_inset_m']
                            dx = -sh if hi_[0] > bk['max'][0]-0.031 else (sh if lo[0] < bk['min'][0]+0.031 else 0.0)
                            variants_['inset'] = ((lo[0]+dx, lo[1], lo[2]), (hi_[0]+dx, hi_[1], hi_[2]))
                        for vn, (l2, h2) in variants_.items():
                            ob = ob_aa(tuple(l2), tuple(h2)); cs_[f'kit {vn}'] = ob_margin(hr.Walls(recs, [W(p_) for p_ in ob_corners(ob)]), ob_world(W, R, ob))
                res[tag] = cs_
            out['station'] = res
            print('WF_O13_CARE_STATION', args.sector, opt, res, flush=True)
    out['seconds'] = round(time.time()-t0, 1); out['done'] = True
    d = RUN13/'care'; d.mkdir(parents=True, exist_ok=True); (d/f'{args.sector}_{opt}_{args.carrier}.json').write_text(json.dumps(out, indent=1, default=str)+'\n')


def a2_plane(args=None):
    """a2 plane options (Blender numpy): transfer park search widened, far-side approach, couch rotated 90 deg (medical), attendant on a short
    strip (bunk: Hygiene egress)."""
    s = _spec(); c = couch_spec(s); cars = carriers_plan(); scr = json.loads((RUN/'screen.json').read_text()); out = {}
    import numpy as np
    for fn, name, own in (('WORK_MEDICAL_OPS', 'Medical_Couch', ()), ('HABITATION', 'Bunk_1', HAB_OWN)):
        pl = Plane(s, fn, 'deck'); b = next(q for q in pl.blocks if q['name'] == name); u0, u1, v0, v1, h0, h1 = pl.P(b['min'], b['max'])
        fr = scr['functions'][fn]['deck']; st = fr['station']; surface = fr['surface_m']; own_ = (name,)+tuple(own); r = {}
        # transfer station: carrier parked up to park_search_m along the point, both rescuer arrangements, the screen's side and the far side
        for side in (st['side'], -st['side']):
            tr = {}
            for cid, car in cars.items():
                cand = []
                for arr in ('beside', 'ends'):
                    for off in np.arange(-P13['park_search_m'], P13['park_search_m']+1e-9, 0.05):
                        g = pl.clearance(env_transfer((u0, u1, v0, v1), side, 'u', car, c, surface, off, arr), exclude=own_)
                        cand.append((g, round(float(off), 2), arr))
                g, off, arr = max(cand, key=lambda q: q[0][0]); tr[cid] = dict(clearance_m=round(g[0], 3), nearest=g[1], part=g[2], offset_m=off, rescuers=arr)
            w = min(tr.items(), key=lambda kv: kv[1]['clearance_m'])
            r[f"transfer side {'+' if side > 0 else '-'}{'' if side == st['side'] else ' (far side)'}"] = dict(worst=dict(carrier=w[0], **w[1]),
                                                                                                           unsuited=min(v['clearance_m'] for k_, v in tr.items() if not k_.startswith('S')), per=tr)
        if fn == 'WORK_MEDICAL_OPS':        # couch rotated 90 deg about its centre (long axis across the sector), care point only
            uc, vc = (u0+u1)/2, (v0+v1)/2; L, Wd = u1-u0, v1-v0
            rot = (uc-Wd/2, uc+Wd/2, vc-L/2, vc+L/2, h0, h1, 'Medical_Couch_rotated')
            r['couch rotated 90 deg (footprint only)'] = dict(zip(('clearance_m', 'nearest', 'part'), pl.clearance([rot], exclude=own_)))
        else:                               # attendant 1 on a short strip at either end of the berth side: egress to every station
            base = egress_values(pl, c, skip=own_); env = [tuple(e) for e in st['env']]
            for end in ('aft', 'fore'):
                e1 = next(e for e in env if e[6] == 'attendant_1_strip'); L_ = P13['attendant_short_m']
                e1s = ((e1[0], e1[0]+L_) if end == 'aft' else (e1[1]-L_, e1[1]))+tuple(e1[2:])
                env2 = [e for e in env if e[6] != 'attendant_1_strip']+[e1s]
                fld = pl.field(env2); B = pl.widest(fld, pl.start(fld))
                eg = {n: round(max(pl.at(fld, B, p) for p in ps)-c['walk_w_m']/2, 3) for n, ps in pl.targets(skip=own_) if ps}
                cg = pl.clearance(env2, exclude=own_)
                r[f'attendant 1 on a {L_:.2f} m strip at the {end} end'] = dict(egress=egress_vs(eg, base), care=dict(zip(('clearance_m', 'nearest', 'part'), cg)))
        out[fn] = r
        print('WF_O13_A2PLANE', fn, json.dumps(r, default=str)[:2000], flush=True)
    RUN13.mkdir(parents=True, exist_ok=True); (RUN13/'a2_plane.json').write_text(json.dumps(out, indent=1, default=str)+'\n')


# ------------------------------------------------------------------------------------------------------------------------------------
# launcher and collect (system python)

def jobs13():
    first = [(f'o13screen {fn}', ['o13screen', '--fn', fn], RUN13/f'screen13_{fn}.json') for fn in ('HABITATION', 'WORK_MEDICAL_OPS', GARDEN)]
    first.append(('a2plane', ['a2plane'], RUN13/'a2_plane.json'))
    rest = [(f'o13sweep {sec} {v} {cch} {c}', ['o13sweep', '--sector', sec, '--variant', v, '--couch', cch, '--carrier', c],
             RUN13/'sweep'/f'{sec}_{v}_{cch}_{c}.json') for sec in SECTORS for v in VARIANTS for cch in COUCHES for c in CARRIER_IDS]
    rest += [(f'o13care {sec} {o} {c}', ['o13care', '--sector', sec, '--option', o, '--carrier', c], RUN13/'care'/f'{sec}_{o}_{c}.json')
             for sec, (j, k) in SECTORS.items() for o in A2_OPTIONS.get(('HABITATION', 'WORK_MEDICAL_OPS', GARDEN)[k-1], {}) for c in CARRIER_IDS]
    return first, rest


def run13(args):
    from concurrent.futures import ThreadPoolExecutor
    RUN13.mkdir(parents=True, exist_ok=True); (RUN13/'logs').mkdir(exist_ok=True)
    first, rest = jobs13()

    def go(jb):
        label, argv, done = jb
        if done.exists() and not args.force:
            return 0
        log = RUN13/'logs'/(re.sub(r'[^A-Za-z0-9_.-]+', '_', label)+'.log'); t = time.time()
        for attempt in range(3):
            with open(log, 'w') as f:
                code = subprocess.call(['timeout', '-s', 'KILL', str(args.timeout), BLENDER, '-b', '--factory-startup', '--python-exit-code', '1',
                                        '--python', str(Path(__file__).resolve()), '--']+argv, stdout=f, stderr=subprocess.STDOUT, cwd=ROOT)
            if code == 0:
                break
        print('done', label, code, f'{time.time()-t:.0f}s', flush=True); return code
    with ThreadPoolExecutor(args.workers) as ex:
        list(ex.map(go, [jb for jb in first if args.only in jb[0]]))
    with ThreadPoolExecutor(args.workers) as ex:
        list(ex.map(go, [jb for jb in rest if args.only in jb[0]]))


FUNCS = ('HABITATION', 'WORK_MEDICAL_OPS', GARDEN)


def collect13():
    """Write references/p1_ringb_insector_care_o13.json, the o13 segments into p1_access_seg_ringb_care.json (same schema) and the report section."""
    base = json.loads(OUT_JSON.read_text()); a2p = json.loads((RUN13/'a2_plane.json').read_text())
    scr13 = {fn: json.loads((RUN13/f'screen13_{fn}.json').read_text()) for fn in FUNCS}
    # ---- a1: per sector, variant, couch: plane parts (worst carrier) + mesh parts (worst carrier) ----
    a1 = {}
    for sec, (j, k) in SECTORS.items():
        fn = FUNCS[k-1]; a1[sec] = dict(function=fn, variants={})
        for v in VARIANTS:
            per_couch = {}
            for cch in COUCHES:
                sc = scr13[fn]['couches'][cch][v]; parts = dict(sc['worst']); per_class = {}; sweeps = {}; mesh = {}
                for c in CARRIER_IDS:
                    f = RUN13/'sweep'/f'{sec}_{v}_{cch}_{c}.json'
                    if not f.exists():
                        continue
                    d = json.loads(f.read_text()); st = sweep_stats(d, cch); sweeps[c] = st; per_class[c] = st['least_m']
                    for key, m in d['mesh'].items():
                        mesh[key] = m
                if len(sweeps) == len(CARRIER_IDS):
                    w = min(sweeps.items(), key=lambda kv: kv[1]['least_m'])
                    parts['carrier sweep hatch -> device + poses (mesh, worst class)'] = w[1]['least_m']
                    parts['  of which route (incl. two inline rescuers)'] = min(x['route_least_m'] for x in sweeps.values())
                    parts['  of which device poses'] = min(x['slide_least_m'] for x in sweeps.values() if x['slide_least_m'] is not None)
                    sw_case = dict(carrier=w[0], case=w[1]['case'], nearest=w[1]['nearest'])
                else:
                    parts['carrier sweep hatch -> device + poses (mesh, worst class)'] = None; sw_case = dict(missing=[c for c in CARRIER_IDS if c not in sweeps])
                hwm = {}
                for key, m in mesh.items():
                    for n_, val in m.items():
                        if n_ in ('rescuers', 'care'):
                            for n2, v2 in val.items():
                                kk = f'{n_}:{n2}'
                                if kk not in hwm or v2[0] < hwm[kk][0]:
                                    hwm[kk] = (v2[0], v2[1], key)
                        elif n_ not in hwm or val[0] < hwm[n_][0]:
                            hwm[n_] = (val[0], val[1], key)
                if mesh:
                    parts['hardware vs built meshes (mesh)'] = min([x[0] for n_, x in hwm.items() if ':' not in n_], default=None)
                    parts['rescuers vs built meshes (mesh capsules)'] = min([x[0] for n_, x in hwm.items() if n_.startswith('rescuers:')], default=None)
                    parts['care after set-down vs built meshes (mesh)'] = min([x[0] for n_, x in hwm.items() if n_.startswith('care:')], default=None)
                main_ = [x for n_, x in parts.items() if not n_.startswith('  ') and n_ != 'rescuer control (plane)' or (n_ == 'rescuer control (plane)' and x is not None)]
                least = None if any(x is None for x in main_) else round(min(main_), 3)
                hand = [x for n_, x in parts.items() if not n_.startswith('  ') and not n_.startswith('egress') and x is not None]
                # unsuited A/C/K only: plane parts per carrier key, the mesh sweep per class and the mesh items per key
                un = [x for key, q in sc['per'].items() if not key.startswith('S') for x in q['parts'].values() if x is not None]
                un += [x for c_, x in per_class.items() if c_ != 'S']
                un += [v2[0] for key, m in mesh.items() if not key.startswith('S') for n_, val in m.items()
                       for v2 in (val.values() if n_ in ('rescuers', 'care') else [val])]
                per_key = {key: round(min(x for x in q['parts'].values() if x is not None), 3) for key, q in sc['per'].items()}
                per_couch[cch] = dict(least_m=least, status=_st(least), handling_m=None if least is None else round(min(hand), 3),
                                      least_unsuited_m=round(min(un), 3) if un else None, plane_least_per_carrier=per_key,
                                      parts=parts, sweep=sw_case, sweep_per_class=per_class, mesh_items=hwm,
                                      order=sc.get('order'), base=sc.get('base'), alternatives=sc.get('alternative'),
                                      geometry={k_: sc['geometry'].get(k_) for k_ in ('x_run', 'cap_x', 'control', 'tie', 'platform_end_u', 'base', 'boom_x')},
                                      governing=min(((n_, x) for n_, x in parts.items() if not n_.startswith('  ') and x is not None), key=lambda kv: kv[1], default=(None, None)))
            bc = max(per_couch.items(), key=lambda kv: -9 if kv[1]['least_m'] is None else kv[1]['least_m'])
            a1[sec]['variants'][v] = dict(best_couch=bc[0], least_m=bc[1]['least_m'], status=bc[1]['status'], handling_m=bc[1]['handling_m'],
                                          least_unsuited_m=bc[1]['least_unsuited_m'], couches=per_couch)
        bv = max(a1[sec]['variants'].items(), key=lambda kv: -9 if kv[1]['least_m'] is None else kv[1]['least_m'])
        a1[sec]['best'] = dict(variant=bv[0], couch=bv[1]['best_couch'], least_m=bv[1]['least_m'], status=bv[1]['status'], handling_m=bv[1]['handling_m'])
    # ---- a2: deck-frame care points with the local change ----
    a2 = {}
    for sec, (j, k) in SECTORS.items():
        fn = FUNCS[k-1]
        if fn not in A2_OPTIONS:
            continue
        row = base['matrix'][sec]; parts0 = dict(row['_deck']['parts']); a2[sec] = dict(function=fn, as_built=dict(least_m=row['0g']['least_m'], status=row['0g']['status'], parts=parts0), options={})
        for opt, desc in A2_OPTIONS[fn].items():
            sweeps = {}; station = None
            for c in CARRIER_IDS:
                f = RUN13/'care'/f'{sec}_{opt}_{c}.json'
                if not f.exists():
                    continue
                d = json.loads(f.read_text())
                stats = {n: sweep_stats(d, n) for n in d['points']}
                sweeps[c] = max(stats.items(), key=lambda kv: kv[1]['least_m'])        # rescuers choose the offset; classes stay worst case
                station = d.get('station', station)
            parts = dict(parts0)
            if len(sweeps) == len(CARRIER_IDS):
                w = min(sweeps.items(), key=lambda kv: kv[1][1]['least_m'])
                parts['carrier sweep hatch -> care point + slide (worst class)'] = w[1][1]['least_m']; swc = dict(carrier=w[0], offset=w[1][0], case=w[1][1]['case'], nearest=w[1][1]['nearest'])
                per_class = {c: dict(offset=x[0], least_m=x[1]['least_m']) for c, x in sweeps.items()}
            else:
                parts['carrier sweep hatch -> care point + slide (worst class)'] = None; swc = dict(missing=[c for c in CARRIER_IDS if c not in sweeps]); per_class = {}
            tr = a2p[fn]
            near = next(v_ for k_, v_ in tr.items() if k_.startswith('transfer') and 'far side' not in k_)
            parts['screen transfer station (worst carrier beside + rescuers)'] = near['worst']['clearance_m']
            if station:
                lab = station['change+labels']
                parts['mesh attendants (capsules, built meshes)'] = min(v_[0] for k_, v_ in lab.items() if k_.startswith('attendant'))
                kits = {k_: v_ for k_, v_ in lab.items() if k_.startswith('kit')}
                kv = max(kits.values(), key=lambda x: x[0]); parts['mesh kit (no overlap)'] = kv[0]
            if fn == 'HABITATION':
                eg = max((v_ for k_, v_ in tr.items() if k_.startswith('attendant 1')), key=lambda x: x['egress']['egress_worst']['clearance_m'])
                parts['screen egress past the deployed station (0.60 m)'] = eg['egress']['egress_worst']['clearance_m']
                parts['screen care station (care point + kit + two attendants)'] = round(min(parts['screen care station (care point + kit + two attendants)'], eg['care']['clearance_m']), 3)
            vals = [x for x in parts.values() if x is not None]
            least = round(min(vals), 3) if len(vals) == len(parts) else None
            un = dict(parts); un['carrier sweep hatch -> care point + slide (worst class)'] = min((x['least_m'] for c, x in per_class.items() if c != 'S'), default=None)
            un['screen transfer station (worst carrier beside + rescuers)'] = near['unsuited']
            least_u = round(min(x for x in un.values() if x is not None), 3)
            a2[sec]['options'][opt] = dict(description=desc, least_m=least, status=_st(least), least_unsuited_m=least_u, status_unsuited=_st(least_u),
                                           parts=parts, sweep=swc, sweep_per_class=per_class, station=station,
                                           governing=min(((n_, x) for n_, x in parts.items() if x is not None), key=lambda kv: kv[1]))
        bo = max(a2[sec]['options'].items(), key=lambda kv: -9 if kv[1]['least_m'] is None else kv[1]['least_m'])
        a2[sec]['best'] = dict(option=bo[0], least_m=bo[1]['least_m'], status=bo[1]['status'], least_unsuited_m=bo[1]['least_unsuited_m'])
    # ---- the 24 states: as built (2026-10-13 run) and with the best a2 change (deck) + the best a1 aid (locked 1.5 g) ----
    states = {}
    for sec in SECTORS:
        row = base['matrix'][sec]; r = {}
        for stt in STATES:
            ab = dict(least_m=row[stt]['least_m'], status=row[stt]['status'])
            if stt == 'locked_1.5g':
                b_ = a1[sec]['best']; new = dict(least_m=b_['least_m'], status=b_['status'], by=f"{b_['variant']} at {b_['couch']}")
                per_v = {v: dict(least_m=x['least_m'], status=x['status'], couch=x['best_couch']) for v, x in a1[sec]['variants'].items()}
            elif sec in a2:
                b_ = a2[sec]['best']; new = dict(least_m=b_['least_m'], status=b_['status'], by=b_['option']); per_v = None
            else:
                new = dict(ab, by='unchanged (garden fold-down couch, 2026-10-13 run)'); per_v = None
            r[stt] = dict(as_built=ab, with_change=new, variants=per_v)
        states[sec] = r
    tally = lambda key: {s_: sum(1 for r in states.values() for st in STATES if r[st][key]['status'] == s_) for s_ in RANK}
    # ---- a3: ring A comparator, same method, per state, carrier / kit carrier / bearers ----
    import ringb_unified as ru
    ru.UNI = RUN/'ringA'; ra = base['ringA_comparator']; legs = {}
    for leg, v in ra['routes'].items():
        rows = {}
        for c in CARRIER_IDS:
            f = RUN/'ringA/built/survey'/f'{leg}_{c}.json'
            if not f.exists():
                continue
            d = json.loads(f.read_text())
            car = [sw_['carrier_m'] for sw_ in d['sweeps']]+[f_['best_family_m'] for f_ in d['families'] if f_['best_family_m'] is not None]
            staff = [sw_['staff_m'] for sw_ in d['sweeps'] if sw_['staff_m'] is not None]+[f_['staff_least_m'] for f_ in d['families'] if f_['staff_least_m'] is not None]
            rows[c] = dict(carrier_m=round(min(car), 3), bearers_m=round(min(staff), 3) if staff else None)
        q = v.get('quoted_single_seed')
        legs[leg] = dict(states=v['states'], per_class=rows,
                         patient_m=min(rows[c]['carrier_m'] for c in 'ACS' if c in rows), kit_m=rows.get('K', {}).get('carrier_m'),
                         bearers_m=min((rows[c]['bearers_m'] for c in rows if rows[c]['bearers_m'] is not None), default=None),
                         raw_single_seed_regression=q)
    per_state = {}
    for stt in STATES:
        ls = [l_ for l_, v in legs.items() if stt in v['states']]
        vals = {kk: min((legs[l_][kk] for l_ in ls if legs[l_][kk] is not None), default=None) for kk in ('patient_m', 'kit_m', 'bearers_m')}
        allm = min(x for x in vals.values() if x is not None) if ls else None
        rb = [states[s_][stt] for s_ in SECTORS if s_[0] == 'B']
        per_state[stt] = dict(legs=ls, **vals, least_m=allm, status=_st(allm), label='FAIL / REDESIGN REQUIRED' if allm is not None and allm < 0 else _st(allm),
                              ringB_in_sector_as_built=min(x['as_built']['least_m'] for x in rb), ringB_in_sector_with_change=min((x['with_change']['least_m'] for x in rb if x['with_change']['least_m'] is not None), default=None))
    a3 = dict(label='FAIL / REDESIGN REQUIRED (owner 15!A175)', legs=legs, per_state=per_state,
              provenance='single-seed built_A quotes (incl. A1 +0.100) are raw regression provenance only, not release evidence (15!A175)')
    res = dict(study='Owner 2026-10-13 S&E 15!A173:A175 applied to the ring B in-sector care study (NONCANON DISPOSABLE STUDY)',
               status='a1 STUDY AUTHORIZED / PERFORMANCE HOLD; a2 PREFERRED ARCHITECTURE / FULL REACH OPEN; a3 FAIL / REDESIGN REQUIRED; nothing released',
               run=str(RUN13.relative_to(ROOT)), base_run=str(RUN.relative_to(ROOT)), params=P13, params_source=P13_SRC, variants=VARIANTS, a2_options=A2_OPTIONS,
               a1=a1, a2=a2, a2_plane=a2p, states=states, tally_as_built=tally('as_built'), tally_with_change=tally('with_change'),
               tally_ringB_with_change={s_: sum(1 for sec, r in states.items() if sec[0] == 'B' for st in STATES if r[st]['with_change']['status'] == s_) for s_ in RANK},
               a3=a3, districts=DISTRICTS, loads=LOADS13)
    if OUT13_JSON.exists() and 'o13c' in json.loads(OUT13_JSON.read_text()):      # keep the 2026-10-13c rack-stowage results
        res['o13c'] = json.loads(OUT13_JSON.read_text())['o13c']
    OUT13_JSON.write_text(json.dumps(res, indent=1, default=str)+'\n')
    # ---- segments (same schema as the module's p1_access_seg_ringb_care.json) ----
    seg = json.loads(SEG_JSON.read_text()); segs = [q for q in seg['segments'] if '|o13-' not in q['id']]
    for q in segs:
        if q['id'].startswith('ringA-wc:') and 'REDESIGN REQUIRED' not in q['note']:
            q['note'] += '; owner 15!A175: FAIL / REDESIGN REQUIRED; the single-seed quote is raw regression provenance only'
    WORST13 = ['injury classes A rigid litter, C vacuum mattress, K litter + kit, S suited', 'body size x1.00 and x1.08', 'doors 1.00 and 0.90 (the sector hatch leaf)',
               'search seeds 17,101,102,103 (+201,202 large, 301 doors 0.90)', '6 pose families with six +-0.02 m / +-0.05 rad wobbles', 'two inline rescuers on the route',
               'device poses: best-found about each, every state and seed', 'plane screen: litter swept envelope, hardware, two rescuers (standing / kneeling), reach, egress, care with the aid parked',
               'mesh: hardware, rescuer capsules, care attendants and kit']
    for sec, (j, k) in SECTORS.items():
        ring = 'ringB' if j == 2 else 'ringA'
        for v, x in a1[sec]['variants'].items():
            cc = x['couches'][x['best_couch']]
            segs.append(dict(id=f'care|{sec}|aft|o13-{v}', route=f'{ring}-care:{sec} in-sector care, locked 1.5 g aid {v}', states=['locked_1.5g'],
                             variant=f"{v} {VARIANTS[v].split(':')[0]} at {x['best_couch']} (PROTOTYPE, owner 15!A173)", case=f"worst part: {cc['governing'][0]}",
                             least_m=x['least_m'], status=x['status'], worst_case_over=WORST13, seed_spread_m=None, nearest=cc['sweep'].get('nearest'),
                             note=f"{FUNCS[k-1]} {sec}; other couch {[c_ for c_ in COUCHES if c_ != x['best_couch']][0]} "
                                  f"{x['couches'][[c_ for c_ in COUCHES if c_ != x['best_couch']][0]]['least_m']}; loads, mass, dynamics, ratings OPEN"))
        if sec in a2:
            b_ = a2[sec]['best']; o_ = a2[sec]['options'][b_['option']]
            segs.append(dict(id=f'care|{sec}|deck|o13-{b_["option"]}', route=f'{ring}-care:{sec} in-sector care, local change {b_["option"]}', states=['0g', 'spin', 'stopped'],
                             variant=f"{o_['description']} (PROTOTYPE, owner 15!A174)", case=f"worst part: {o_['governing'][0]}", least_m=b_['least_m'], status=b_['status'],
                             worst_case_over=WORST13[:6]+['slide onto the care point, best along-couch offset, every state and seed', 'zone screen: care, transfer (park search 1.00 m), reach, egress', 'mesh: care attendants and kit'],
                             seed_spread_m=None, nearest=o_['sweep'].get('nearest'), note=f"{FUNCS[k-1]} {sec}; unsuited-only least {b_['least_unsuited_m']}"))
    seg['segments'] = segs
    seg['note_o13'] = 'segments with |o13- in the id: owner 2026-10-13 15!A173:A175 (1.5 g aids, local care-point changes); same keys as the other segments'
    SEG_JSON.write_text(json.dumps(seg, indent=1, default=str)+'\n')
    write_md13(res)
    print('a1 best', {s_: a1[s_]['best'] for s_ in a1}); print('a2 best', {s_: a2[s_]['best'] for s_ in a2})
    print('tally as built', res['tally_as_built'], 'with change', res['tally_with_change'], 'ringB', res['tally_ringB_with_change'])


DISTRICTS = {
    'HABITATION': {'patient access': 'GEOMETRY: lowest berth (Bunk_1) and burn couches measured (tables above); suited casualty does not fit the 0.81 m berth',
                   'atmosphere isolation': 'OPEN: sector hatch leaf is the only modelled closure; no local care-zone isolation, leak hold time or flow',
                   'sanitation': 'GEOMETRY (partial): Hygiene compartment in the sector; egress to it with care deployed measured; waste handling for a casualty OPEN',
                   'medications': 'OPEN: no medication store in the sector; kit box (0.60 x 0.55 x 0.15 PROTOTYPE) only',
                   'loads': 'OPEN: F = m x 1.5 x 9.80665 m/s2 per anchor before dynamic factors; m, dynamics, ratings unknown',
                   'service kit': 'GEOMETRY (envelope): HUM-003 kit box placed and measured; medical gas, suction, power outlets OPEN'},
    'WORK_MEDICAL_OPS': {'patient access': 'GEOMETRY: treatment couch (SP-33) and burn couches measured (tables above)',
                         'atmosphere isolation': 'OPEN: SP-34 isolation / recovery berth is a programme line, not a modelled closure; sector hatch leaf only',
                         'sanitation': 'OPEN: no hygiene compartment in the sector; SP-46 sealed waste collection point in the workbench cabinet (collection only)',
                         'medications': 'GEOMETRY (envelope): Medical_Stowage block in the sector; contents, quantities, shelf life OPEN',
                         'loads': 'OPEN: F = m x 1.5 x 9.80665 m/s2 per anchor before dynamic factors; m, dynamics, ratings unknown',
                         'service kit': 'GEOMETRY (envelope): SP-50 overhead medical unit envelope over the couch; kit box measured; gas, suction, power OPEN'},
    GARDEN: {'patient access': 'GEOMETRY: PROTOTYPE fold-down couch (0 g / spin / stopped) and burn couches (1.5 g) measured; Garden_Rack_1 / Mess displaced in memory only',
           'atmosphere isolation': 'OPEN: sector hatch leaf only; ECLSS bay in the sector is not a care-zone isolation',
           'sanitation': 'OPEN: no hygiene compartment in the sector',
           'medications': 'OPEN: none in the sector; kit box only',
           'loads': 'OPEN: F = m x 1.5 x 9.80665 m/s2 per anchor before dynamic factors; m, dynamics, ratings unknown',
           'service kit': 'GEOMETRY (envelope): kit box measured; gas, suction, power OPEN'}}
LOADS13 = dict(formula='F_anchor = m x 1.5 x 9.80665 m/s2 (static, locked 1.5 g, aft down), before dynamic, off-axis, shared-load and arrest factors',
               m='OPEN (casualty + litter + kit + device moving mass; no source)', dynamics='OPEN', ratings='OPEN (rail, tie, platform, hinge, arm, anchors, descender)',
               recovery='passive / manual: descender brake, belay, arm hand drive: mechanisms OPEN', known=False)


def write_md13(r):
    """Insert / replace the owner 2026-10-13 section at the end of the report."""
    md_text = OUT_MD.read_text()
    i = md_text.find(O13_HEAD); j = md_text.find(O13C_HEAD); tail = md_text[j:] if j >= 0 else ''    # keep the 2026-10-13c section after it
    if i >= 0:
        md_text = md_text[:i].rstrip('\n')+'\n'
    OUT_MD.write_text(md_text.rstrip('\n')+'\n\n'+md13(r)+('\n\n'+tail if tail else ''))


def md13(r):
    f3 = lambda x: '' if x is None else f'{x:+.3f}'
    cell = lambda x: 'OPEN' if x is None or x.get('least_m') is None else f"{x['status']} {x['least_m']:+.3f}"
    L = [O13_HEAD, '',
         'Owner answers 2026-10-13 to Claude\'s Doc item 2026-10-13T18:18 (a1-a3), applied to this study. NONCANON DISPOSABLE STUDY: hardware, rescuers and',
         f'fit-out changes exist only in memory. Run `{r["run"]}`; results `references/p1_ringb_insector_care_o13.json`; segments with `|o13-` in',
         '`references/p1_access_seg_ringb_care.json`. Status bands unchanged: PASS >= 0.05 m, MARGINAL 0..0.05 m, FAIL < 0.', '',
         '- **15!A173 (a1) STUDY AUTHORIZED / PERFORMANCE HOLD.** Reversible hoist / lowering aid / guided load transfer for 1.5 g in-sector handling,',
         '  passive / manual recovery, independent anchors, no furniture-only assumption; compare local controlled lowering, restrained platform and',
         '  rated assist with patient + 2 rescuers + kit over the worst-case 24-state sweep. No safe 1.5 g care, shielding or medical certification implied.',
         '- **15!A174 (a2) PREFERRED ARCHITECTURE / FULL REACH OPEN.** Distributed stabilisation in every sector; the Garden couch is a PROTOTYPE, not the',
         '  sole facility; no permanent displacement of canon Garden; improve medical-couch and bunk handling locally. Patient survival while the route',
         '  is blocked remains an unsolved P0 risk.',
         '- **15!A175 (a3) FAIL / REDESIGN REQUIRED.** Ring A with the same exhaustive worst-case method, per-state minima and the full patient + kit +',
         '  bearer route; the earlier single-seed +0.100 m is raw regression provenance only.', '',
         '### a1: 1.5 g handling aids (locked 1.5 g, aft down)', '',
         'Each variant is PROTOTYPE geometry derived from the sector (hatch clear circle, burn couches, fit-out above) and the P13 dimensions below; both',
         'burn couches are tried and the better is kept. Worst case over A/C/K/S x1.00/x1.08, doors 1.00/0.90, the module\'s seeds and pose families,',
         'two inline rescuers on the route; plus the plane screen (litter swept envelope, hardware, two rescuers standing or kneeling, reach, egress,',
         'care with the aid parked) and mesh checks (hardware, rescuer capsules, care attendants and kit). Garden sectors carry the couch stowed.', '']
    for v, d in r['variants'].items():
        L.append(f'- **{v}** {d}.')
    L += ['', '| Item | Value | Source |', '| --- | --- | --- |']
    for k_, v in r['params_source'].items():
        L.append(f"| {k_} | {', '.join(str(r['params'][x.strip()]) for x in k_.split(','))} | {v} |")
    L += ['', '#### Per sector and variant, locked 1.5 g (better couch: all parts / handling only, without egress past the station / unsuited A/C/K only)', '',
          '| Sector | Function | V1 lowering | V2 platform | V3 assist | Best | As built (2026-10-13) |', '| --- | --- | --- | --- | --- | --- | --- |']
    for sec, x in r['a1'].items():
        vv = x['variants']; ab = r['states'][sec]['locked_1.5g']['as_built']
        L.append(f"| {sec} | {x['function']} | " + ' | '.join(f"{cell(vv[v])} / {f3(vv[v]['handling_m'])} / {f3(vv[v]['least_unsuited_m'])} ({vv[v]['best_couch'].replace('Burn_Couch_', 'BC')})" for v in VARIANTS)
                 + f" | {x['best']['variant']} {x['best']['status']} {f3(x['best']['least_m'])} | {cell(ab)} |")
    L += ['', '#### Parts (m), both couches, worst carrier', '',
          '| Sector | Variant | Couch | Litter vs room | HW vs room | HW vs hatch | HW vs litter | Rescuers (plane) | Reach | Egress | Care parked | Sweep (mesh) | HW mesh | Rescuers mesh | Care mesh | Least | Governing |',
          '| --- |'*17]
    L[-1] = '| ' + ' | '.join(['---']*17) + ' |'
    keys = ['litter swept envelope vs room (plane)', 'hardware vs room (plane)', 'hardware vs hatch passage (plane)', 'hardware vs litter, same instant (plane)',
            None, 'rescuer reach (0.60 m path)', 'egress past the deployed aid (0.60 m)', 'care after set-down, aid parked (plane)',
            'carrier sweep hatch -> device + poses (mesh, worst class)', 'hardware vs built meshes (mesh)', 'rescuers vs built meshes (mesh capsules)', 'care after set-down vs built meshes (mesh)']
    for sec, x in r['a1'].items():
        for v in VARIANTS:
            for cch, cc in x['variants'][v]['couches'].items():
                p = cc['parts']; cells = []
                for k_ in keys:
                    if k_ is None:
                        cells.append(f3(min(x for x in (p['rescuer guide (plane)'], p['rescuer control (plane)']) if x is not None)))
                    else:
                        cells.append(f3(p.get(k_)))
                gov = cc['governing']; extra = ''
                if gov[0] and gov[0].startswith('carrier sweep'):
                    extra = f"; {cc['sweep'].get('carrier')} {cc['sweep'].get('case')} at {cc['sweep'].get('nearest')}"
                L.append(f"| {sec} | {v}{'' if not cc.get('order') else ' ' + cc['order']} | {cch.replace('Burn_Couch_', 'BC')} | " + ' | '.join(cells)
                         + f" | {cell(cc)} | {gov[0]}{extra} |")
    L += ['', 'Plane values are capped at +0.30 m, mesh values at +0.10 m ("at least"). Rescuer columns are the worse of the guide and the control rescuer.', '',
          '#### Loads (OPEN, nothing computed)', '', f"- {r['loads']['formula']}; m: {r['loads']['m']}; dynamics {r['loads']['dynamics']}; ratings {r['loads']['ratings']};",
          f"  recovery: {r['loads']['recovery']}.", '',
          '### a2: local changes at the built medical couch and the lowest berth (0 g / spin / stopped, deck frame)', '',
          '| Sector | Care point | As built | Option | Least (all classes) | Unsuited A/C/K | Governing part |', '| --- | --- | --- | --- | --- | --- | --- |']
    for sec, x in r['a2'].items():
        for opt, o in x['options'].items():
            L.append(f"| {sec} | {'Medical_Couch' if x['function'] == 'WORK_MEDICAL_OPS' else 'Bunk_1'} | {cell(x['as_built'])} | {opt}: {o['description']} | {cell(o)} | "
                     f"{o['status_unsuited']} {f3(o['least_unsuited_m'])} | {o['governing'][0]} {f3(o['governing'][1])} |")
    L += ['', 'Options screened on the zone blocks only (no mesh sweep):', '']
    for fn, opts in r['a2_plane'].items():
        for k_, v in opts.items():
            if k_.startswith('transfer'):
                L.append(f"- {fn} {k_}, park search +-{P13['park_search_m']:.2f} m: worst {v['worst']['carrier']} {f3(v['worst']['clearance_m'])} ({v['worst']['part']} vs {v['worst']['nearest']}, "
                         f"offset {v['worst']['offset_m']}, rescuers {v['worst']['rescuers']}); unsuited {f3(v['unsuited'])}.")
            elif 'rotated' in k_:
                L.append(f"- {fn} {k_}: {f3(v['clearance_m'])} vs {v['nearest']}.")
            else:
                L.append(f"- {fn} {k_}: egress worst {v['egress']['egress_worst']['target']} {f3(v['egress']['egress_worst']['clearance_m'])}; care station {f3(v['care']['clearance_m'])} vs {v['care']['nearest']}.")
    L += ['', '#### Per district: what is addressed geometrically and what stays OPEN (both rings, same layout)', '',
          '| District | ' + ' | '.join(next(iter(r['districts'].values())).keys()) + ' |', '| --- |' + ' --- |'*6]
    for fn, row in r['districts'].items():
        L.append(f'| {fn} | ' + ' | '.join(row.values()) + ' |')
    L += ['', '### 24 sector-states with the changes (as built -> with the best local change / aid)', '',
          '| Sector | 0g | spin | stopped | locked_1.5g |', '| --- | --- | --- | --- | --- |']
    for sec, row in r['states'].items():
        L.append(f'| {sec} | ' + ' | '.join(f"{cell(row[st]['as_built'])} -> {cell(row[st]['with_change'])}" for st in STATES) + ' |')
    L += ['', f"Tally (24): as built {r['tally_as_built']}; with the changes {r['tally_with_change']}; ring B's 12 with the changes {r['tally_ringB_with_change']}.", '',
          '### a3: ring A comparator (FAIL / REDESIGN REQUIRED)', '',
          'Same exhaustive method as ring B (ringb_unified.survey on the built model: classes, x1.00/x1.08, doors, seeds, pose families, two bearers).',
          'Patient = worst of A/C/S carriers; kit = K (litter + kit); bearers = the two rescuers along the route. The single-seed quote is raw regression',
          'provenance only.', '', '| Leg | States | Patient | Kit | Bearers | Raw single-seed (provenance) |', '| --- | --- | --- | --- | --- | --- |']
    for leg, v in r['a3']['legs'].items():
        q = v['raw_single_seed_regression']
        L.append(f"| {leg} | {', '.join(v['states'])} | {f3(v['patient_m'])} | {f3(v['kit_m'])} | {f3(v['bearers_m'])} | {'' if not q else f3(q[0])} |")
    L += ['', '| State | Ring A legs | Patient | Kit | Bearers | Ring A | Ring B in-sector, as built | Ring B in-sector, with changes |', '| --- | --- | --- | --- | --- | --- | --- | --- |']
    for st, v in r['a3']['per_state'].items():
        L.append(f"| {st} | {', '.join(v['legs'])} | {f3(v['patient_m'])} | {f3(v['kit_m'])} | {f3(v['bearers_m'])} | {v['label']} {f3(v['least_m'])} | "
                 f"{_st(v['ringB_in_sector_as_built'])} {f3(v['ringB_in_sector_as_built'])} | {_st(v['ringB_in_sector_with_change'])} {f3(v['ringB_in_sector_with_change'])} |")
    L += ['', O13_REVIEW_MARK, '']
    return '\n'.join(L)


O13_REVIEW_MARK = """#### Result (Claude; numbers from the tables above)

1. **a1: no variant makes a locked 1.5 g cell PASS (0 of 6; ring B 0 of 3).** The aids fix the casualty transfer itself; the room around
   the burn couch does not fit two rescuers and a passage.
   - What now clears: with V1 (rail) or V3 (wall jib) at Burn_Couch_2, the hatch -> couch carrier sweep and the lowering poses pass for every
     class and size, +0.06 to +0.10 m (the 2026-10-13 aft route at the screen's couch was down to -0.45 m). In the medical and garden sectors the
     hardware clears the built meshes (+0.068 m), and so do the rescuer capsules (+0.074 to +0.10 m) and the care station with the aid parked
     (+0.057 to +0.10 m).
   - What still fails: the 0.9 m strip between the couch head and the overhead wall is the only way from the thrust step to the inter-couch gap.
     It also carries the open hatch leaf and its rail at knee height. A x1.08 rigid litter (2.16 m) or the S x1.08 casualty (2.26 m) is longer than
     the 2.0 m couch and closes that strip. Rescuer reach: -0.09 m (A / K x1.08) and -0.14 m (S x1.08). Egress past the station to the other burn
     couch: -0.02 to -0.22 m.
   - Best per function, all parts / handling without egress / unsuited A/C/K:
     - Habitation: V1 or V3 at BC2, -0.220 / -0.140 / -0.210. V1's second anchor finds no clear place: Hygiene, Crew_Stowage_Upper and the
       landing chase are in the way (mesh -0.14). V3's deck-wall bracket clears (+0.068).
     - Medical: V1 or V3 at BC2, -0.140 / -0.140 / -0.090. Unsuited x1.00 carriers reach -0.02 at worst.
     - Garden: V3 at BC1 (shift then lower, deck-wall jib), -0.066 / -0.003 / -0.066. The -0.066 is egress past the care station, the same
       value the care station has without any aid. This placement uses the space Garden_Rack_1 gives up in the PROTOTYPE swap. With the canon
       rack in place BC1 is blocked as in habitation, and BC2 governs at -0.140.
   - V2 (restrained platform) is the worst everywhere: -0.278 to -0.379.
     - The incline tilts the litter through the hatch frame (sweep -0.15 to -0.31 m at Sector_Hatch_Frame).
     - The board meets the frame / couch (mesh -0.14).
     - While the board is down it blocks the head-end strip (egress -0.28 / -0.29).
   - Burn_Couch_1 is unusable in habitation and medical with any aid: the bunk stack / treatment couch overhead (litter -0.31 to -0.58 m).
   - Ranking: V3 (wall jib) >= V1 (rail) >> V2. V3 needs one structural bracket instead of a rail and a tie. Its anchor redundancy (two
     independent attachment points on the bracket) and every rating are OPEN.
2. **a2: medical couch toward PASS; bunk not.**
   - Medical couch, best option: a fold-down foot plate (the 1.2 m foot plate was what the slide hit) plus the room label moved off the head
     end.
     - Unsuited A/C/K: PASS +0.066 (governing: K x1.08 sweep).
     - All classes: FAIL -0.031 (S x1.08 bearers vs Burn_Couch_2; S x1.08 transfer station -0.030 vs the end wall). Deck states A2 / B2 move
       from -0.140 to -0.031.
     - Rejected: lift over the kept foot plate (-0.061), the far-side approach (-0.80, Ops_Stations), rotating the couch 90 deg (-0.60, Ops_Stations).
   - Lowest berth, with grab bar and rung folded flat, the kit inset and the label moved: -0.338 (S x1.08). Unsuited: -0.142 (Hygiene egress).
     - A rigid litter (2.00 / 2.16 m) is longer than the berth's 1.94 m inner length (-0.112). C is at -0.029.
     - The suited casualty does not fit the 0.70 m clear height.
     - Care in the 0.9 m aisle blocks the Hygiene door; a 1.00 m attendant strip does not change that.
     - Berth care needs the casualty moved off the carrier. That procedure is OPEN.
   - The district table: patient access is geometry. Atmosphere isolation, sanitation (except the Hygiene compartment in habitation),
     medications (except the Medical_Stowage envelope), loads and service-kit outlets are OPEN.
3. **24 sector-states with the best change: still 6 PASS / 18 FAIL (ring B 3 / 9).** Every FAIL got smaller:
   - medical 0 g: -0.140 -> -0.031;
   - bunk: -0.439 -> -0.338;
   - 1.5 g: -0.28 / -0.45 / -0.31 -> -0.22 / -0.14 / -0.066.
4. **a3: ring A FAIL / REDESIGN REQUIRED in every state.** Same exhaustive method.
   - 0 g: -0.171 (patient S; kit carrier -0.103; bearers -0.049).
   - Spin: -0.455.
   - Stopped and locked 1.5 g: -0.251.
   - The single-seed +0.100 m (A1) is kept only as raw regression provenance.
   - Ring B in-sector with the changes: -0.338 (0 g / spin / stopped, the berth) and -0.220 (locked 1.5 g). Neither ring passes.
5. **OPEN.** Nothing invented:
   - Loads: F = m x 1.5 x 9.80665 m/s2 per anchor before dynamic factors; m, dynamics and ratings unknown.
   - Mechanisms: descender, hoist, hinge, board straps.
   - Stowage of the removable rail, boom and board in coast; deck states are measured without them.
   - Anchor redundancy.
   - Atmosphere, sanitation and medication per district.
   - The off-carrier transfer procedure.
   - Patient survival while the route is blocked (P0).

Method notes: the o13 aft plane adds two fixtures the 2026-10-13 aft screen did not carry: the landing chase and the open hatch leaf with
its rails (from human_entry.landing). The as-built egress base includes them too. The plane screen treats the suited capsule as a box
(conservative); the mesh sweep uses the capsule. Rescuers are placed by the screen (four diverse best stations each, best pair by
clearance, reach and egress) and then checked as mesh capsules. Ring A and ring B sectors share one layout and give identical numbers.
Passing checks are not engineering proof.
"""


# ------------------------------------------------------------------------------------------------------------------------------------
# 2026-10-13c: Garden_Rack_1 emergency stowage. Main-agent decision on 15!A174 ("without displacing canon Garden permanently") and H174 (no
# removal of the original Garden room): the o13 garden results that relied on Garden_Rack_1 being removed do not count. A rack section that is
# swung / slid / emptied clear ONLY during an emergency and returns afterwards is a PROTOTYPE study. The Mess stays displaced as in the
# 15!A169 swap (that displacement is not re-decided here; its canon-Mess overlap is reported). Plants, trays, water, power: OPEN.

RUN13C = ROOT/'runs/20261013T2100Z-garden-rack'
O13C_HEAD = '## Garden emergency rack stowage (2026-10-13c)'
RACK = 'Garden_Rack_1'
RACKS = {'canon': 'rack in its normal (canon) position, nothing moved: the time-independent state',
         'swing': 'centre-post double leaf: the rack splits at the fold-down couch\'s aft edge into an aft leaf A and a forward leaf F, both hinged on '
                  'one vertical post at the split, back (outboard) corner; a leaf swings 90 deg outboard into the bay the Mess gives up (A169) and '
                  'stands across the sector until it is swung back',
         'slide': 'lateral drawer: the moved section runs outboard on floor runners (parallel to the split plane) until its back is at the outboard '
                  'wall allowance; slides back afterwards',
         'trays': 'removable tray modules: the crop modules of the moved section (Crop_0 and each tray with its crop) are pulled out through the '
                  'aisle face and stacked in a stowage column against the outboard wall in the Mess bay; the frame (base reservoir, back, lid, '
                  'ends) stays in place; modules return afterwards'}
RACK_MOVES = {'aft': ('A',), 'deck': ('A', 'F')}     # sections moved per emergency frame (locked 1.5 g: only A is in the way; deck: both)
SWING_STEP_DEG = 10
P13C_SRC = {'split_x_m': 'rack split at the screened fold-down couch\'s aft edge (screen.json garden_couch deployed x min 0.90 m); in 1.5 g the '
                         'section forward of it is above the aid hardware (o13 cap 0.90 m from the hatch rail)',
            'section boxes': 'each rack section is its bounding box over the built zone block (2.00 m tall, 0.50 m deep): conservative to the '
                             'whitebox parts (base, trays, crops, lid, back, ends)',
            'swing': f'leaf poses every {SWING_STEP_DEG} deg, swept envelope = the oriented leaf at each pose (split in 6 for the plane screen)',
            'slide': 'stop at the outboard wall allowance at the rack top height (habitat_interior.wall_half_width - interior.wall_allowance_m)',
            'trays': 'module = tray + crop above it (Crop_0 alone), heights from sector_whitebox.shapes; no spacing in the stack; pull-out '
                     'envelope = the section footprint plus one rack depth into the aisle over the tray heights; carry path OPEN',
            'couch': 'fold-down couch as screened (ringb_unified.CARE 2.00 x 0.70, top 0.80, stowed 0.30 x 1.50); re-placement searched only '
                     'on the two hinge lines the screen used (forward fit-out line x 1.60, outboard wall)'}


def rack_geometry(s, rk, state, split):
    """Local (sector-frame) boxes of Garden_Rack_1 for one variant in one state ('normal', 'aft', 'deck'): in-place sections / frame,
    stowed boxes and the swept oriented boxes of the stowage motion."""
    import habitat_interior as hi
    import sector_whitebox as sw
    blocks = hi.zones(s, GARDEN); b = next(q for q in blocks if q['name'] == RACK); lo, hi_ = b['min'], b['max']
    x0, x1 = lo[0], hi_[0]; y0, y1 = lo[1], hi_[1]; z0, z1 = lo[2], hi_[2]; D = z1-z0; wall = s['interior']['wall_allowance_m']
    secs = {'A': (x0, split), 'F': (split, x1)}
    moved = () if (rk == 'canon' or state == 'normal') else RACK_MOVES[state]
    out = dict(rack=rk, state=state, split_x=split, sections={k: list(v) for k, v in secs.items()}, moved=list(moved), in_place=[], stowed=[], swept=[],
               sliding_interface=False)
    for k, (xa, xb) in secs.items():
        if k not in moved:
            out['in_place'].append([[xa, y0, z0], [xb, y1, z1], f'{RACK}_{k}'])
    if rk == 'swing':
        for k in moved:
            xa, xb = secs[k]; L = xb-xa; sg = -1.0 if k == 'A' else 1.0
            for deg in range(SWING_STEP_DEG, 91, SWING_STEP_DEG):
                t = math.radians(deg); a = (sg*math.cos(t), math.sin(t)); d = (sg*math.sin(t), -math.cos(t))
                c = (split+a[0]*L/2+d[0]*D/2, (y0+y1)/2, z1+a[1]*L/2+d[1]*D/2)
                ob = (c, ((a[0], 0.0, a[1]), (0.0, 1.0, 0.0), (d[0], 0.0, d[1])), (L/2, (y1-y0)/2, D/2))
                # the last anchor_zone_m (0.10) at the hinge post is the fitting, not a clearance (P13 rule); the stowed box below is untrimmed
                out['swept'].append(dict(section=k, pose=f'{deg} deg', ob=ob_trim(ob, [(0, -1)], P13['anchor_zone_m']), full=ob))
            lo2, hi2 = ob_aabb(out['swept'][-1]['full'])
            out['stowed'].append([list(lo2), list(hi2), f'{RACK}_{k}_stowed'])
    elif rk == 'slide':
        zw = hi.wall_half_width(s, y0)-wall; out['sliding_interface'] = True
        for k in moved:
            xa, xb = secs[k]
            out['stowed'].append([[xa, y0, zw-D], [xb, y1, zw], f'{RACK}_{k}_stowed'])
            out['swept'].append(dict(section=k, pose='slide', ob=ob_aa((xa, y0, z0), (xb, y1, zw))))
    elif rk == 'trays':
        parts = sw.shapes(s, b, blocks)
        crops = {q['part']: q for q in parts if q['part'].startswith(('Crop', 'Tray'))}
        mods = [[crops['Crop_0']]]+[[crops[f'Tray_{i}'], crops[f'Crop_{i}']] for i in (1, 2, 3)]
        mod_h = [max(q['max'][1] for q in m)-min(q['min'][1] for q in m) for m in mods]
        frame = [q for q in parts if not q['part'].startswith(('Crop', 'Tray'))]
        out['sliding_interface'] = True                   # the modules ride out on the frame (base, tray guides): contact by design
        for k in moved:
            xa, xb = secs[k]
            for q in frame:
                if q['min'][0] < xb-1e-9 and q['max'][0] > xa+1e-9:
                    out['in_place'].append([[max(q['min'][0], xa), q['min'][1], q['min'][2]], [min(q['max'][0], xb), q['max'][1], q['max'][2]], f"{RACK}_{k}_{q['part']}"])
            ylo = min(q['min'][1] for m in mods for q in m); yhi = max(q['max'][1] for m in mods for q in m)
            zbk = next(q['min'][2] for q in frame if q['part'] == 'Back')          # modules come out in front of the back panel, between the end panels
            xe0 = max(xa, next(q['max'][0] for q in frame if q['part'] == 'End_1')); xe1 = min(xb, next(q['min'][0] for q in frame if q['part'] == 'End_2'))
            out['swept'].append(dict(section=k, pose='pull-out', ob=ob_aa((xe0, ylo, z0-D), (xe1, yhi, zbk))))
        h = 0.0; cols = []
        for k in moved:                                   # one stowage column from the deck up, aft end at the rack's aft end
            xa, xb = secs[k]; L = xb-xa; hk = sum(mod_h); cols.append((k, L, h, h+hk)); h += hk
        top = h; zw = hi.wall_half_width(s, -top)-wall
        for k, L, h0, h1 in cols:
            out['stowed'].append([[x0, -h1, zw-D], [x0+L, -h0, zw], f'{RACK}_{k}_modules_stowed'])
        out['module_heights_m'] = [round(x, 3) for x in mod_h]
    return out


def _rk_boxes(geo, with_stowed=True):
    return [(tuple(b_[0]), tuple(b_[1]), b_[2]) for b_ in geo['in_place']+(geo['stowed'] if with_stowed else [])]


def _ob_plane_boxes(pl, ob, n=6, name='rack_swept'):
    return [pl.P(*ob_aabb(o))+(name,) for o in (ob_split(ob, n) if ob[2][0] > 0.15 else [ob])]


def _stow_check(pl, geo):
    """Plane boxes of the stowed position for the clearance checks: swing uses its 90 deg pose trimmed at the hinge post (the fitting)."""
    if geo['rack'] == 'swing':
        return [pl.P(*ob_aabb(sw_['ob']))+(f"{RACK}_{sw_['section']}_stowed",) for sw_ in geo['swept'] if sw_['pose'] == '90 deg']
    return [pl.P(tuple(b_[0]), tuple(b_[1]))+(b_[2],) for b_ in geo['stowed']]


def _couch_stow(c, axis, cp):
    """Stowed box of a fold-down couch from its deployed plan footprint (deck plane u, v): folded up about the hinge edge (as the screen)."""
    if axis == 'u':
        return (cp[0], cp[1], cp[3]-c['stowed_depth_m'], cp[3], 0.0, c['stowed_top_m'], 'care_couch_stowed')
    return (cp[1]-c['stowed_depth_m'], cp[1], cp[2], cp[3], 0.0, c['stowed_top_m'], 'care_couch_stowed')


def _aft_fix(s):
    import human_entry as he
    L_ = he.landing(s); ceil = L_['ceiling']
    lz = (L_['z']-L_['frame_r'], L_['leaf_open_z']+L_['leaf_r']+0.05); lo_, lf = L_['leaf_open']
    return [((L_['well_x'][0], ceil, L_['chase_z'][0]), (L_['well_x'][1], 0.0, L_['chase_z'][1]), 'landing_chase'),
            ((-L_['leaf_r'], lo_, L_['leaf_open_z']-L_['leaf_r']), (L_['leaf_r'], lf, L_['leaf_open_z']+L_['leaf_r']), 'hatch_leaf_open'),
            ((-L_['frame_r']-0.04, lo_, lz[0]), (-L_['frame_r'], lf, lz[1]), 'hatch_rail_1'), ((L_['frame_r'], lo_, lz[0]), (L_['frame_r']+0.04, lf, lz[1]), 'hatch_rail_2')]


def o13c_screen(args):
    """Blender (numpy): one rack variant. Deck frame: the screened fold-down couch with the rack in its emergency state, then the couch
    re-placed on the two hinge lines (normal-state stow vs the canon rack and the stowage motion vs the stowed couch are criteria); motion
    and stowed-position checks; locked 1.5 g: the o13 V1 / V3 screens at both burn couches with the rack in its 1.5 g emergency state."""
    import numpy as np
    import human_entry as he
    s = _spec(); c = couch_spec(s); cars = carriers_plan(); rk = args.rack; fn = GARDEN
    scr = json.loads((RUN/'screen.json').read_text()); g0 = scr['garden_couch']; split = g0['deployed_local_min'][0]
    geo = {st: rack_geometry(s, rk, st, split) for st in ('normal', 'aft', 'deck')}
    out = dict(rack=rk, description=RACKS[rk], split_x_m=split, geometry=geo); t0 = time.time()
    L_ = he.landing(s)
    # ---- deck frame (0 g / spin / stopped) ----
    gd = geo['deck']; pl = Plane(s, fn, 'deck', drop=SWAP, extra=_rk_boxes(gd)); base = egress_values(Plane(s, fn, 'deck'), c)
    pn = Plane(s, fn, 'deck', drop=('Mess',))                       # normal: canon rack in place, Mess displaced (A169)
    pm = Plane(s, fn, 'deck', drop=SWAP, extra=_rk_boxes(gd, with_stowed=False))   # before the motion: moved sections absent, the rest in place
    excl = tuple(b_[2] for b_ in gd['in_place']) if gd['sliding_interface'] else ()
    swept_d = [bx for sw_ in gd['swept'] for bx in _ob_plane_boxes(pm, sw_['ob'], name=f"{sw_['section']} {sw_['pose']}")]
    stow_d = _stow_check(pm, gd)
    import habitat_interior as hi
    W, Lc, top = c['width_m'], c['length_m'], c['top_m']; zb = {b_['name']: b_ for b_ in hi.zones(s, fn)}
    zw = min(pl.half(-c['stowed_top_m']), zb['Mess']['max'][2]); xf = zb[RACK]['max'][0]           # the screen's two hinge lines
    cands = [('v', (xf-W, xf, float(v0), float(v0)+Lc), -1) for v0 in np.arange(-0.40, zw-Lc+1e-9, 0.05)]
    cands += [('u', (float(u0), float(u0)+Lc, zw-W, zw), -1) for u0 in np.arange(-1.10, xf-Lc+1e-9, 0.05)]
    g0cp = tuple(g0['footprint_uv']); res = []
    for axis, cp, side in cands:
        cpbox = (*cp, 0.0, top, 'care_couch_deployed'); stow = _couch_stow(c, axis, cp)
        r = assess_point(pl, cp, axis, top, (), c, cars, sides=(side,), extra_cp=cpbox, base=base)
        nrm = pn.clearance([stow])                                    # normal state: stowed couch vs the canon rack and the room
        mot = min([(_gap7(b_, stow), b_[6]) for b_ in swept_d], default=(CAP_M, None))     # rack moves first: motion vs the stowed couch
        r.update(axis=axis, footprint_uv=[round(x, 3) for x in cp], stowed_uvh=[round(x, 3) if not isinstance(x, str) else x for x in stow],
                 normal_stowed=dict(zip(('clearance_m', 'nearest', 'part'), (round(nrm[0], 3), nrm[1], nrm[2]))),
                 motion_vs_stowed_couch=dict(clearance_m=round(min(mot[0], CAP_M), 3), part=mot[1]),
                 screened=bool(axis == g0['axis'] and max(abs(a-b_) for a, b_ in zip(cp, g0cp)) < 1e-6))
        r['governing_all_m'] = round(min(r['governing_m'], r['normal_stowed']['clearance_m'], r['motion_vs_stowed_couch']['clearance_m']), 3)
        res.append(r)
    scr_r = next((r for r in res if r['screened']), None)
    best = max(res, key=lambda r: (r['governing_all_m'], r['governing_m']))
    for r in (scr_r, best):
        if r is None:
            continue
        stow = tuple(r['stowed_uvh'])
        r['normal_stowed_egress'] = stowed_egress(Plane(s, fn, 'deck', drop=('Mess',), extra=[local_box(pn, stow)+('care_couch_stowed',)]), c, base=base)['worst']
        dep_lo, dep_hi = local_box(pl, (*r['footprint_uv'], 0.0, top)); st_lo, st_hi = local_box(pl, stow)
        r.update(deployed_local_min=list(dep_lo), deployed_local_max=list(dep_hi), stowed_local_min=list(st_lo), stowed_local_max=list(st_hi))
    mess = next(b_ for b_ in Plane(s, fn, 'deck').blocks if b_['name'] == 'Mess'); mess_p = pl.P(mess['min'], mess['max'])+('Mess',)
    mot_room = pm.clearance(swept_d, exclude=excl); stow_room = pm.clearance(stow_d, exclude=excl)
    wellk = [r_ for r_ in pm.rects if r_[6] in ('landing_well', 'landing_ladder')]
    hatch_d = min([(_gap7(b_, w_), w_[6]) for b_ in swept_d+stow_d for w_ in wellk], default=(CAP_M, None))
    out['deck'] = dict(screened=scr_r, best=best, candidates=len(res),
                       ranking=sorted([dict(axis=r['axis'], footprint_uv=r['footprint_uv'], governing_m=r['governing_m'], governing_all_m=r['governing_all_m'],
                                            normal_stowed_m=r['normal_stowed']['clearance_m'], motion_vs_stowed_couch_m=r['motion_vs_stowed_couch']['clearance_m'])
                                       for r in res], key=lambda q: -q['governing_all_m'])[:8],
                       motion_vs_room=dict(zip(('clearance_m', 'nearest', 'part'), (round(mot_room[0], 3), mot_room[1], mot_room[2]))) if swept_d else None,
                       stowed_vs_room=dict(zip(('clearance_m', 'nearest', 'part'), (round(stow_room[0], 3), stow_room[1], stow_room[2]))) if stow_d else None,
                       motion_stowed_vs_landing_well=dict(clearance_m=round(min(hatch_d[0], CAP_M), 3), part=hatch_d[1]) if swept_d else None,
                       canon_mess_overlap_m=round(min([_gap7(b_, mess_p) for b_ in stow_d]+[_gap7((*best['footprint_uv'], 0.0, top, 'couch'), mess_p)]), 3))
    print('WF_O13C_DECK', rk, 'screened', None if scr_r is None else (scr_r['governing_m'], scr_r['governing_all_m']), 'best', best['axis'], best['footprint_uv'],
          best['governing_m'], best['governing_all_m'], 'motion', out['deck']['motion_vs_room'], 'stowed', out['deck']['stowed_vs_room'], flush=True)
    # ---- locked 1.5 g (aft frame) with the couch stowed where the chosen deck placement stows it ----
    chosen = best
    couch_stow = (tuple(chosen['stowed_local_min']), tuple(chosen['stowed_local_max']), 'care_couch_stowed')
    out['couch'] = dict(axis=chosen['axis'], deployed=[chosen['deployed_local_min'], chosen['deployed_local_max']],
                        stowed=[chosen['stowed_local_min'], chosen['stowed_local_max']], screened_placement=chosen['screened'])
    ga = geo['aft']; fix = _aft_fix(s); extra = [couch_stow]+_rk_boxes(ga)
    pl = Plane(s, fn, 'aft', drop=SWAP, extra=extra+fix); pa = Plane(s, fn, 'aft', extra=fix); pl_lit = Plane(s, fn, 'aft', drop=SWAP, extra=extra)

    def care_extra(g):
        return Plane(s, fn, 'aft', drop=SWAP, extra=extra+fix+[tuple(ob_aabb(h['ob']))+(h['name'],) for h in g['parked']])
    ser = lambda x: json.loads(json.dumps(x, default=lambda o: list(o)))
    out['couches'] = {}
    for couch in COUCHES:
        out['couches'][couch] = {}
        for v in ('V1', 'V3'):
            combos = [(o, b_) for o in V3_ORDERS for b_ in V3_BASES] if v == 'V3' else [(None, None)]
            for order, base_ in combos:
                g = o13_geometry(s, pl, fn, couch, v, cars, order, base_); per = {}
                for key in cars:
                    per[key] = o13_assess(s, pl, pa, fn, g, key, c, care_extra, pl_lit)
                worst = {k: min((per[c_]['parts'][k] for c_ in per if per[c_]['parts'][k] is not None), default=None) for k in next(iter(per.values()))['parts']}
                gov = min(x for x in worst.values() if x is not None)
                out['couches'][couch][v if v != 'V3' else f'V3:{order}:{base_}'] = dict(geometry=ser({k: v_ for k, v_ in g.items() if k != 'per'}), per_geometry=ser(g['per']),
                                                                                        per=per, worst=worst, governing_m=gov)
                print('WF_O13C_AFT', rk, couch, v, order, base_, gov, flush=True)
            if v == 'V3':
                alts = {k_: x['governing_m'] for k_, x in out['couches'][couch].items() if k_.startswith('V3:')}
                pick = max(alts, key=lambda k_: alts[k_])
                out['couches'][couch]['V3'] = dict(out['couches'][couch][pick], order=pick.split(':')[1], base=pick.split(':')[2], alternative=alts)
                for k_ in list(alts):
                    out['couches'][couch][k_] = dict(governing_m=alts[k_])          # keep the alternatives' values only
    # motion / stowed position in the aft frame: before the motion the moved section is absent; the couch is stowed
    pam = Plane(s, fn, 'aft', drop=SWAP, extra=[couch_stow]+_rk_boxes(ga, with_stowed=False)+fix)
    excl = tuple(b_[2] for b_ in ga['in_place']) if ga['sliding_interface'] else ()
    swept_a = [bx for sw_ in ga['swept'] for bx in _ob_plane_boxes(pam, sw_['ob'], name=f"{sw_['section']} {sw_['pose']}")]
    stow_a = _stow_check(pam, ga)
    hx, hz, r_ = L_['x'], L_['z'], L_['clear_r']
    passage = (pam.ceil, pam.ceil+P13['hatch_keepout_m'], hz-r_, hz+r_, hx-r_-pam.xlo, hx+r_-pam.xlo, 'hatch_passage')
    if swept_a:
        m_ = pam.clearance(swept_a, exclude=excl); s_ = pam.clearance(stow_a, exclude=excl)
        hp = min((_gap7(b_, passage), b_[6]) for b_ in swept_a+stow_a)
        out['aft'] = dict(motion_vs_room=dict(zip(('clearance_m', 'nearest', 'part'), (round(m_[0], 3), m_[1], m_[2]))),
                          stowed_vs_room=dict(zip(('clearance_m', 'nearest', 'part'), (round(s_[0], 3), s_[1], s_[2]))),
                          motion_stowed_vs_hatch_passage=dict(clearance_m=round(min(hp[0], CAP_M), 3), part=hp[1]),
                          canon_mess_overlap_m=round(min(_gap7(b_, pam.P(mess['min'], mess['max'])+('Mess',)) for b_ in stow_a), 3))
    else:
        out['aft'] = dict(motion_vs_room=None, stowed_vs_room=None, motion_stowed_vs_hatch_passage=None, canon_mess_overlap_m=None)
    # normal state (canon rack, couch stowed): the stowed couch against the canon rack in the aft frame too
    pna = Plane(s, fn, 'aft', drop=('Mess',), extra=fix)
    nr = pna.clearance([pna.P(*couch_stow[:2])+('care_couch_stowed',)])
    out['normal'] = dict(stowed_couch_vs_canon_rack=dict(zip(('clearance_m', 'nearest', 'part'), (round(nr[0], 3), nr[1], nr[2]))))
    out['seconds'] = round(time.time()-t0, 1)
    RUN13C.mkdir(parents=True, exist_ok=True); (RUN13C/f'screen13c_{rk}.json').write_text(json.dumps(out, indent=1, default=float)+'\n')


def rack_records(s, records, boxes, couch_lohi, couch_state):
    """Drop Garden_Rack_1 and the Mess (A169) from both garden sectors (as swapped_records), then add the rack boxes of the state (in place +
    stowed, axis-aligned local boxes) and the couch box."""
    gk = s['habitat']['layout']['functions'].index(GARDEN)+1
    keep = [r for r in records if not any(n in r['name'] for n in SWAP) or r['name'].startswith('Sector_Fit_Room_Mess_')]
    keep = [r for r in keep if not ('Garden_Rack_1' in r['name'] or r['name'] == 'Mess')]
    for j in (1, 2):
        for lo, hi, nm in boxes:
            keep.append(box_record(local_box_world(s, j, gk, lo, hi), f'Study_{nm}_{j}', kind='study_rack'))
        if couch_lohi is not None:
            keep.append(box_record(local_box_world(s, j, gk, couch_lohi[0], couch_lohi[1]), f'Care_Couch_{couch_state}_{j}'))
    return keep


def o13c_care(args):
    """Deck-frame mesh job (0 g / spin / stopped) for one rack variant, sector and carrier: the module's garden care sweep (hatch -> beside the
    couch + slide, classes / sizes / doors / seeds / families / two rescuers) with the rack in its deck emergency state and the couch the
    screen chose; with carrier A also the care-station attendants and kit, and the stowage motion (deck and 1.5 g) against the built meshes."""
    import copy
    import bpy
    import numpy as np
    import casualty_sweep as cs
    import hum003_routes as hr
    import ringb_unified as ru
    s = _spec(); scr = json.loads((RUN/'screen.json').read_text()); j, k = SECTORS[args.sector]; rk = args.rack
    sc = json.loads((RUN13C/f'screen13c_{rk}.json').read_text()); g = sc['deck']['best']
    scr2 = copy.deepcopy(scr); scr2['garden_couch'] = dict(scr['garden_couch'], **{q: g[q] for q in ('axis', 'deployed_local_min', 'deployed_local_max')})
    scr2['functions'][GARDEN]['deck']['station'] = g
    bpy.ops.wm.open_mainfile(filepath=str(ROOT/'assets/wayfarer/WF_WAYFARER_001.blend')); ins = cs.load_inspect()
    W, R, _ = _world(s, j, k); car0 = hr.CARRIERS[args.carrier]; t0 = time.time()
    boxes = _rk_boxes(sc['geometry']['deck']); dep = (g['deployed_local_min'], g['deployed_local_max'])
    out = dict(sector=args.sector, rack=rk, carrier=args.carrier, points={}, couch=dict(axis=g['axis'], footprint_uv=g['footprint_uv']))
    for door, scale in ((1.0, 1.0), (1.0, hr.BODY_SCALE_LARGE), (DOOR_PARTIAL, 1.0)):
        raw = cs.scene(s, ins, door); records = rack_records(s, raw, boxes, dep, 'deployed'); car = hr.scaled(car0, scale)
        for name, (path, slide) in care_routes(s, scr2, j, k, 'deck', car, f'{args.carrier} x{scale:.2f}').items():
            o = out['points'].setdefault(name, dict(sweeps=[], families=[], slide=[]))
            walls = hr.Walls(records, [p for _, p in path]+[q[0] for q in slide])
            seeds = ru.SEEDS_NOMINAL if (door, scale) == (1.0, 1.0) else (ru.SEEDS_LARGE if scale != 1.0 else (301,))
            for seed in seeds:
                r = hr.sweep_route(walls, car, path, np.random.default_rng(seed), couch=True)
                o['sweeps'].append(dict(door=door, scale=scale, seed=seed, carrier_m=r['least_m'], carrier_nearest=r['nearest'], staff_m=r['staff_least_m'],
                                        staff_nearest=r['staff_nearest'], by_zone={z: v['least_m'] for z, v in r['by_zone'].items()}))
                sp = hr.sweep_poses(walls, car, slide, np.random.default_rng(seed))
                o['slide'].append(dict(door=door, scale=scale, seed=seed, least_m=sp['least_m'], nearest=sp['nearest'], at=sp['at']))
                print('WF_O13C_CARE', args.sector, rk, args.carrier, door, scale, seed, r['least_m'], r['nearest'], r['staff_least_m'], 'slide', sp['least_m'], sp['nearest'], flush=True)
            f = hr.family_sweep(walls, car, path, couch=True); f.update(door=door, scale=scale); o['families'].append(f)
        if door == 1.0 and scale == 1.0 and args.carrier == 'A':
            pl = Plane(s, GARDEN, 'deck'); st = {}
            for e in g['env']:
                lo, hi_ = local_box(pl, e[:6]); cen = [(lo[a]+hi_[a])/2 for a in range(3)]
                if e[6].startswith('attendant'):
                    Rr = hr.STAFF_R_M; a_, b_ = W((cen[0], -(Rr+0.10), cen[2])), W((cen[0], -(scr['couch']['stand_h_m']-Rr), cen[2]))
                    v = hr.Walls([q for q in records if not q['name'].startswith('Care_Couch_deployed_')], [a_, b_]).capsule(a_, b_, Rr); st[e[6]] = (round(v[0], 3), v[1])
                else:
                    ob = ob_aa(tuple(lo), tuple(hi_)); st[e[6]] = ob_margin(hr.Walls(records, [W(p_) for p_ in ob_corners(ob)]), ob_world(W, R, ob))
            out['station'] = st
            # stowage motion vs the built meshes: before the motion (moved sections absent, the rest in place, couch stowed)
            mot = {}
            for frame in ('deck', 'aft'):
                gg = sc['geometry'][frame]
                if not gg['swept']:
                    continue
                stw = sc['couch']['stowed']
                pre = rack_records(s, raw, [] if gg['sliding_interface'] else _rk_boxes(gg, with_stowed=False), stw, 'stowed')
                rows = []
                for sw_ in gg['swept']:
                    ob = (tuple(sw_['ob'][0]), tuple(tuple(a) for a in sw_['ob'][1]), tuple(sw_['ob'][2]))
                    m = ob_margin(hr.Walls(pre, [W(p_) for p_ in ob_corners(ob)]), ob_world(W, R, ob)); rows.append((m[0], m[1], f"{sw_['section']} {sw_['pose']}"))
                for lo, hi_, nm in ([] if rk == 'swing' else [tuple(b_) for b_ in gg['stowed']]):     # swing: the 90 deg pose is the stowed position
                    ob = ob_aa(tuple(lo), tuple(hi_)); m = ob_margin(hr.Walls(pre, [W(p_) for p_ in ob_corners(ob)]), ob_world(W, R, ob)); rows.append((m[0], m[1], f'{nm} (stowed)'))
                mot[frame] = min(rows, key=lambda q: q[0]); mot[frame + '_all'] = rows
            out['motion_mesh'] = mot
            print('WF_O13C_STATION', args.sector, rk, st, {k_: v for k_, v in mot.items() if not k_.endswith('_all')}, flush=True)
    out['seconds'] = round(time.time()-t0, 1); out['done'] = True
    d = RUN13C/'care'; d.mkdir(parents=True, exist_ok=True); (d/f'{args.sector}_{rk}_{args.carrier}.json').write_text(json.dumps(out, indent=1, default=str)+'\n')


def jobs13c():
    first = [(f'o13cscreen {rk}', ['o13cscreen', '--rack', rk], RUN13C/f'screen13c_{rk}.json') for rk in RACKS]
    rest = [(f'o13sweep {sec} {v} {cch} {c} {rk}', ['o13sweep', '--sector', sec, '--variant', v, '--couch', cch, '--carrier', c, '--rack', rk],
             RUN13C/'sweep'/f'{sec}_{rk}_{v}_{cch}_{c}.json') for rk in RACKS for sec in ('A3', 'B3') for v in ('V1', 'V3') for cch in COUCHES for c in CARRIER_IDS]
    rest += [(f'o13ccare {sec} {rk} {c}', ['o13ccare', '--sector', sec, '--rack', rk, '--carrier', c], RUN13C/'care'/f'{sec}_{rk}_{c}.json')
             for rk in RACKS for sec in ('A3', 'B3') for c in CARRIER_IDS]
    return first, rest


def run13c(args):
    from concurrent.futures import ThreadPoolExecutor
    RUN13C.mkdir(parents=True, exist_ok=True); (RUN13C/'logs').mkdir(exist_ok=True)
    first, rest = jobs13c()

    def go(jb):
        label, argv, done = jb
        if done.exists() and not args.force:
            return 0
        log = RUN13C/'logs'/(re.sub(r'[^A-Za-z0-9_.-]+', '_', label)+'.log'); t = time.time()
        for attempt in range(3):
            with open(log, 'w') as f:
                code = subprocess.call(['timeout', '-s', 'KILL', str(args.timeout), BLENDER, '-b', '--factory-startup', '--python-exit-code', '1',
                                        '--python', str(Path(__file__).resolve()), '--']+argv, stdout=f, stderr=subprocess.STDOUT, cwd=ROOT)
            if code == 0:
                break
        print('done', label, code, f'{time.time()-t:.0f}s', flush=True); return code
    with ThreadPoolExecutor(args.workers) as ex:
        list(ex.map(go, [jb for jb in first if args.only in jb[0]]))
    with ThreadPoolExecutor(args.workers) as ex:
        list(ex.map(go, [jb for jb in rest if args.only in jb[0]]))


def _aft_cell(sc, files):
    """One aid at one burn couch: plane parts (worst carrier) + the mesh parts (worst class), as collect13's a1."""
    parts = dict(sc['worst']); sweeps = {}; mesh = {}
    for c in CARRIER_IDS:
        f = files(c)
        if not f.exists():
            continue
        d = json.loads(f.read_text()); sweeps[c] = sweep_stats(d, d['couch']); mesh.update(d['mesh'])
    if len(sweeps) == len(CARRIER_IDS):
        w = min(sweeps.items(), key=lambda kv: kv[1]['least_m'])
        parts['carrier sweep hatch -> device + poses (mesh, worst class)'] = w[1]['least_m']; swc = dict(carrier=w[0], case=w[1]['case'], nearest=w[1]['nearest'])
    else:
        parts['carrier sweep hatch -> device + poses (mesh, worst class)'] = None; swc = dict(missing=[c for c in CARRIER_IDS if c not in sweeps])
    hwm = {}
    for key, m in mesh.items():
        for n_, val in m.items():
            for n2, v2 in (val.items() if n_ in ('rescuers', 'care') else [(None, val)]):
                kk = n_ if n2 is None else f'{n_}:{n2}'
                if kk not in hwm or v2[0] < hwm[kk][0]:
                    hwm[kk] = (v2[0], v2[1], key)
    if mesh:
        parts['hardware vs built meshes (mesh)'] = min([x[0] for n_, x in hwm.items() if ':' not in n_], default=None)
        parts['rescuers vs built meshes (mesh capsules)'] = min([x[0] for n_, x in hwm.items() if n_.startswith('rescuers:')], default=None)
        parts['care after set-down vs built meshes (mesh)'] = min([x[0] for n_, x in hwm.items() if n_.startswith('care:')], default=None)
    vals = [x for n_, x in parts.items() if not (n_ == 'rescuer control (plane)' and x is None)]
    least = None if any(x is None for x in vals) else round(min(vals), 3)
    gov = min(((n_, x) for n_, x in parts.items() if x is not None), key=lambda kv: kv[1], default=(None, None))
    un = [x for key, q in sc['per'].items() if not key.startswith('S') for x in q['parts'].values() if x is not None]
    un += [x['least_m'] for c_, x in sweeps.items() if c_ != 'S']
    return dict(least_m=least, status=_st(least), parts=parts, sweep=swc, mesh_items=hwm, governing=gov, order=sc.get('order'), base=sc.get('base'),
                least_unsuited_m=round(min(un), 3) if un else None, geometry={k_: sc['geometry'].get(k_) for k_ in ('x_run', 'cap_x', 'control', 'tie', 'base', 'boom_x')})


def collect13c():
    """o13c results into p1_ringb_insector_care_o13.json (key o13c), the |o13c- segments and the report section."""
    r13 = json.loads(OUT13_JSON.read_text()); base = json.loads(OUT_JSON.read_text())
    res = dict(study='Garden_Rack_1 emergency stowage (2026-10-13c): main-agent decision on 15!A174 / H174 (the rack-removal result does not count; '
                     'an emergency-only stowed rack section is a PROTOTYPE study)', run=str(RUN13C.relative_to(ROOT)), racks=RACKS, source=P13C_SRC, variants={})
    for rk in RACKS:
        sc = json.loads((RUN13C/f'screen13c_{rk}.json').read_text()); v = dict(description=RACKS[rk], geometry=sc['geometry'], couch=sc['couch'],
                                                                               normal=sc['normal'], aft_motion=sc['aft'], deck_motion={k_: sc['deck'][k_] for k_ in
                                                                               ('motion_vs_room', 'stowed_vs_room', 'motion_stowed_vs_landing_well', 'canon_mess_overlap_m')})
        # ---- locked 1.5 g ----
        aft = {}
        for sec in ('A3', 'B3'):
            aft[sec] = {}
            for vv in ('V1', 'V3'):
                cells = {cch: _aft_cell(sc['couches'][cch][vv], lambda c, sec=sec, vv=vv, cch=cch: RUN13C/'sweep'/f'{sec}_{rk}_{vv}_{cch}_{c}.json') for cch in COUCHES}
                mo = [] if rk == 'canon' else [('rack stowage motion + stowed position (plane, aft)', min(sc['aft']['motion_vs_room']['clearance_m'], sc['aft']['stowed_vs_room']['clearance_m'])),
                                               ('rack motion / stowed vs hatch passage (plane)', sc['aft']['motion_stowed_vs_hatch_passage']['clearance_m'])]
                for cch, x in cells.items():
                    for n_, val in mo:
                        x['parts'][n_] = val
                    vals = [y for n_, y in x['parts'].items() if not (n_ == 'rescuer control (plane)' and y is None)]
                    x['least_m'] = None if any(y is None for y in vals) else round(min(vals), 3); x['status'] = _st(x['least_m'])
                    x['governing'] = min(((n_, y) for n_, y in x['parts'].items() if y is not None), key=lambda kv: kv[1])
                bc = max(cells.items(), key=lambda kv: -9 if kv[1]['least_m'] is None else kv[1]['least_m'])
                aft[sec][vv] = dict(best_couch=bc[0], least_m=bc[1]['least_m'], status=bc[1]['status'], couches=cells)
            bv = max(aft[sec].items(), key=lambda kv: -9 if kv[1]['least_m'] is None else kv[1]['least_m'])
            aft[sec]['best'] = dict(aid=bv[0], couch=bv[1]['best_couch'], least_m=bv[1]['least_m'], status=bv[1]['status'])
        v['aft'] = aft
        # ---- deck (0 g / spin / stopped) ----
        dk = {}; g = sc['deck']['best']; gs = sc['deck']['screened']
        for sec in ('A3', 'B3'):
            parts = {'screen care station (care point + kit + two attendants)': g['care']['clearance_m'],
                     'screen transfer station (worst carrier beside + rescuers)': g['transfer_worst']['clearance_m'],
                     'screen attendant reach (0.60 m)': min(x for x in g['reach'].values() if x is not None),
                     'screen egress past the deployed station (0.60 m)': g['egress_worst']['clearance_m'],
                     'normal state: stowed couch vs canon rack / room (plane)': g['normal_stowed']['clearance_m'],
                     'normal state: egress with the couch stowed (0.60 m)': g['normal_stowed_egress']['clearance_m'],
                     'rack motion vs the stowed couch (plane)': g['motion_vs_stowed_couch']['clearance_m']}
            if rk != 'canon':
                parts['rack stowage motion + stowed position (plane, deck)'] = min(sc['deck']['motion_vs_room']['clearance_m'], sc['deck']['stowed_vs_room']['clearance_m'])
                parts['rack motion / stowed vs landing well + ladder (plane)'] = sc['deck']['motion_stowed_vs_landing_well']['clearance_m']
            sweeps = {}; station = None; motion = None
            for c in CARRIER_IDS:
                f = RUN13C/'care'/f'{sec}_{rk}_{c}.json'
                if not f.exists():
                    continue
                d = json.loads(f.read_text()); sweeps[c] = sweep_stats(d, 'Care_Couch'); station = d.get('station', station); motion = d.get('motion_mesh', motion)
            if len(sweeps) == len(CARRIER_IDS):
                w = min(sweeps.items(), key=lambda kv: kv[1]['least_m'])
                parts['carrier sweep hatch -> care point + slide (worst class)'] = w[1]['least_m']; swc = dict(carrier=w[0], case=w[1]['case'], nearest=w[1]['nearest'])
            else:
                parts['carrier sweep hatch -> care point + slide (worst class)'] = None; swc = dict(missing=[c for c in CARRIER_IDS if c not in sweeps])
            if station:
                parts['mesh attendants (capsules, built meshes)'] = min(v_[0] for k_, v_ in station.items() if k_.startswith('attendant'))
                parts['mesh kit (no overlap)'] = station['kit'][0]
            if motion:
                parts['rack stowage motion + stowed position (mesh, deck)'] = motion['deck'][0] if 'deck' in motion else None
            vals = [x for x in parts.values()]
            least = None if any(x is None for x in vals) else round(min(vals), 3)
            un = dict(parts)
            if len(sweeps) == len(CARRIER_IDS):
                un['carrier sweep hatch -> care point + slide (worst class)'] = min(x['least_m'] for c_, x in sweeps.items() if c_ != 'S')
            un['screen transfer station (worst carrier beside + rescuers)'] = min(x['clearance_m'] for k_, x in g['transfer'].items() if not k_.startswith('S'))
            least_u = None if any(x is None for x in un.values()) else round(min(un.values()), 3)
            dk[sec] = dict(least_m=least, status=_st(least), least_unsuited_m=least_u, parts=parts, sweep=swc, sweep_per_class={c_: x['least_m'] for c_, x in sweeps.items()},
                           station=station, motion_mesh={k_: v_ for k_, v_ in (motion or {}).items() if not k_.endswith('_all')},
                           governing=min(((n_, x) for n_, x in parts.items() if x is not None), key=lambda kv: kv[1]),
                           couch=dict(axis=g['axis'], footprint_uv=g['footprint_uv'], screened_placement=g['screened']),
                           screened_placement=None if gs is None else dict(governing_m=gs['governing_m'], governing_all_m=gs['governing_all_m'], care=gs['care'],
                                                                          transfer_worst=gs['transfer_worst'], egress_worst=gs['egress_worst'], reach=gs['reach'],
                                                                          normal_stowed=gs['normal_stowed'], motion_vs_stowed_couch=gs['motion_vs_stowed_couch']))
        v['deck'] = dk; v['deck_ranking'] = sc['deck']['ranking']
        # mesh motion in the aft frame (from the deck jobs, carrier A)
        f = RUN13C/'care'/f'A3_{rk}_A.json'
        if f.exists():
            mm = json.loads(f.read_text()).get('motion_mesh') or {}
            v['aft_motion']['mesh'] = mm.get('aft')
            if mm.get('aft'):
                for sec in ('A3', 'B3'):
                    for vv in ('V1', 'V3'):
                        for cch, x in v['aft'][sec][vv]['couches'].items():
                            x['parts']['rack stowage motion + stowed position (mesh, aft)'] = mm['aft'][0]
                            x['least_m'] = None if x['least_m'] is None else round(min(x['least_m'], mm['aft'][0]), 3); x['status'] = _st(x['least_m'])
                            x['governing'] = min(((n_, y) for n_, y in x['parts'].items() if y is not None), key=lambda kv: kv[1])
                        bc = max(v['aft'][sec][vv]['couches'].items(), key=lambda kv: -9 if kv[1]['least_m'] is None else kv[1]['least_m'])
                        v['aft'][sec][vv].update(best_couch=bc[0], least_m=bc[1]['least_m'], status=bc[1]['status'])
                    bv = max(((k_, y) for k_, y in v['aft'][sec].items() if k_ != 'best'), key=lambda kv: -9 if kv[1]['least_m'] is None else kv[1]['least_m'])
                    v['aft'][sec]['best'] = dict(aid=bv[0], couch=bv[1]['best_couch'], least_m=bv[1]['least_m'], status=bv[1]['status'])
        res['variants'][rk] = v
    # ---- the 24 sector-states: o13 'with change' with A3 / B3 replaced by each rack variant (the removal result no longer counts) ----
    states13 = r13['states']; tallies = {}
    for rk, v in res['variants'].items():
        rows = {}
        for sec in SECTORS:
            rows[sec] = {}
            for stt in STATES:
                if sec in ('A3', 'B3'):
                    x = v['aft'][sec]['best'] if stt == 'locked_1.5g' else v['deck'][sec]
                    rows[sec][stt] = dict(least_m=x['least_m'], status=x['status'])
                else:
                    rows[sec][stt] = dict(least_m=states13[sec][stt]['with_change']['least_m'], status=states13[sec][stt]['with_change']['status'])
        tallies[rk] = dict(all={s_: sum(1 for r in rows.values() for st in STATES if r[st]['status'] == s_) for s_ in RANK},
                           ringB={s_: sum(1 for sec, r in rows.items() if sec[0] == 'B' for st in STATES if r[st]['status'] == s_) for s_ in RANK}, garden=
                           {sec: {st: rows[sec][st] for st in STATES} for sec in ('A3', 'B3')})
    res['tally_o13_with_change'] = r13['tally_with_change']; res['tally_o13_ringB'] = r13['tally_ringB_with_change']; res['tallies'] = tallies
    best = max((rk for rk in RACKS if rk != 'canon'), key=lambda rk: (min(x['least_m'] for sec in ('A3',) for x in (res['variants'][rk]['aft'][sec]['best'], res['variants'][rk]['deck'][sec])
                                                                        if x['least_m'] is not None), tallies[rk]['all']['PASS']))
    res['best_variant'] = best
    res['open'] = ['stowage time per variant (crew action sequence from the emergency call to a clear care station): OPEN, not estimated',
                   'crew actions and number of crew for the motion (unlock, swing / slide / pull-out, lock in the stowed position, return): OPEN',
                   'plant survival while stowed (light, water, nutrient flow, root-zone aeration, tilt and spill): OPEN',
                   'water (reservoir base) and power / lighting / sensor interfaces across the motion (flexible lines, quick disconnects): OPEN',
                   'hinge, runner, latch, restraint and lock ratings; loads F = m x 1.5 x 9.80665 m/s2 per support before dynamic factors with the rack '
                   'and module mass m OPEN (known = false)',
                   'module carry path and restraint of the stacked modules in the stowage column (trays variant): OPEN',
                   'return to normal after the emergency and verification that the canon Garden function is restored: OPEN',
                   'the Mess displacement (15!A169 swap) is carried unchanged: whether it may stay displaced under 15!A174 / H174 is not decided here']
    r13['o13c'] = res; OUT13_JSON.write_text(json.dumps(r13, indent=1, default=str)+'\n')
    # ---- segments ----
    seg = json.loads(SEG_JSON.read_text()); segs = [q for q in seg['segments'] if '|o13c-' not in q['id']]
    W13C = ['injury classes A rigid litter, C vacuum mattress, K litter + kit, S suited', 'body size x1.00 and x1.08', 'doors 1.00 and 0.90 (the sector hatch leaf)',
            'search seeds 17,101,102,103 (+201,202 large, 301 doors 0.90)', '6 pose families with six +-0.02 m / +-0.05 rad wobbles', 'two inline rescuers on the route']
    for rk, v in res['variants'].items():
        for sec in ('A3', 'B3'):
            ring = 'ringB' if sec[0] == 'B' else 'ringA'
            for vv in ('V1', 'V3'):
                x = v['aft'][sec][vv]; cc = x['couches'][x['best_couch']]; oth = [c_ for c_ in COUCHES if c_ != x['best_couch']][0]
                segs.append(dict(id=f'care|{sec}|aft|o13c-{rk}-{vv}', route=f'{ring}-care:{sec} in-sector care, locked 1.5 g aid {vv}, Garden_Rack_1 {rk}', states=['locked_1.5g'],
                                 variant=f"{vv} at {x['best_couch']}; rack {rk}: {RACKS[rk]} (PROTOTYPE, 15!A173 / A174)", case=f"worst part: {cc['governing'][0]}",
                                 least_m=x['least_m'], status=x['status'], worst_case_over=W13C+['device poses: best-found about each, every state and seed',
                                 'plane screen: litter, hardware, rescuers, reach, egress, care with the aid parked', 'mesh: hardware, rescuer capsules, care attendants and kit',
                                 'rack stowage motion and stowed position (plane + mesh)'], seed_spread_m=None, nearest=cc['sweep'].get('nearest'),
                                 note=f"{GARDEN} {sec}; other couch {oth} {x['couches'][oth]['least_m']}; Mess displaced as 15!A169; loads, mass, ratings, stowage time, plant survival OPEN"))
            x = v['deck'][sec]
            segs.append(dict(id=f'care|{sec}|deck|o13c-{rk}', route=f'{ring}-care:{sec} in-sector care, fold-down couch, Garden_Rack_1 {rk}', states=['0g', 'spin', 'stopped'],
                             variant=f"fold-down couch {x['couch']['axis']} {x['couch']['footprint_uv']}{' (as screened)' if x['couch']['screened_placement'] else ' (re-placed)'}; rack {rk}: {RACKS[rk]} (PROTOTYPE)",
                             case=f"worst part: {x['governing'][0]}", least_m=x['least_m'], status=x['status'],
                             worst_case_over=W13C+['slide onto the care point, every state and seed', 'zone screen: care, transfer, reach, egress, normal-state stow',
                                                   'mesh: care attendants and kit', 'rack stowage motion and stowed position (plane + mesh)'],
                             seed_spread_m=None, nearest=x['sweep'].get('nearest'), note=f"{GARDEN} {sec}; unsuited-only least {x['least_unsuited_m']}; Mess displaced as 15!A169"))
    seg['segments'] = segs
    seg['note_o13c'] = 'segments with |o13c- in the id: Garden_Rack_1 emergency stowage 2026-10-13c (canon / swing / slide / trays); same keys'
    SEG_JSON.write_text(json.dumps(seg, indent=1, default=str)+'\n')
    write_md13c(res)
    try:
        plan_svg(res)
    except Exception as e:                           # the still is optional
        print('plan_svg failed', e)
    print('best', best, {rk: (v['aft']['A3']['best'], v['deck']['A3']['least_m']) for rk, v in res['variants'].items()}, {rk: t['all'] for rk, t in tallies.items()})


def write_md13c(r):
    md_text = OUT_MD.read_text(); i = md_text.find(O13C_HEAD)
    if i >= 0:
        md_text = md_text[:i].rstrip('\n')+'\n'
    OUT_MD.write_text(md_text.rstrip('\n')+'\n\n'+md13c(r))


def md13c(r):
    f3 = lambda x: 'n/a' if x is None else f'{x:+.3f}'
    cell = lambda x: 'OPEN' if x is None or x.get('least_m') is None else f"{x['status']} {x['least_m']:+.3f}"
    V = r['variants']
    L = [O13C_HEAD, '',
         'Main-agent decision on owner 15!A174 ("without displacing canon Garden permanently") and H174 (no removal of the original Garden room):',
         'the o13 garden numbers that removed Garden_Rack_1 (deck +0.075, V3 at BC1 -0.066) do not count. This section keeps the rack in its canon',
         'place and moves a section of it only during the emergency (PROTOTYPE), then re-runs the worst cases. The Mess stays displaced as in',
         'the 15!A169 swap; that is not re-decided here, and its overlap with the canon Mess is listed. NONCANON DISPOSABLE STUDY; everything is in',
         f'memory. Run `{r["run"]}`; results key `o13c` in `references/p1_ringb_insector_care_o13.json`; segments `|o13c-` in',
         '`references/p1_access_seg_ringb_care.json`. Status bands unchanged: PASS >= 0.05 m, MARGINAL 0..0.05 m, FAIL < 0.', '',
         '### Variants (derived from the built rack: x -0.55..1.60, 2.00 m tall, 0.50 m deep, open to the aisle)', '']
    for rk, d in r['racks'].items():
        L.append(f'- **{rk}**: {d}.')
    L += ['', f"Split at x {V['canon']['geometry']['normal']['split_x']:+.2f} m: aft section A ({V['canon']['geometry']['normal']['sections']['A']}),"
          f" forward section F ({V['canon']['geometry']['normal']['sections']['F']}). Locked 1.5 g moves A only; 0 g / spin / stopped move A and F.", '',
          '| Item | Source / rule |', '| --- | --- |']
    L += [f'| {k} | {v} |' for k, v in r['source'].items()]
    L += ['', '#### Stowed positions and motion (sector frame, m)', '',
          '| Variant | Frame | Stowed boxes (x / y / z) | Motion + stowed vs room | Nearest | vs hatch passage / landing well | Mesh motion (built meshes) | Canon Mess overlap |',
          '| --- | --- | --- | --- | --- | --- | --- | --- |']
    for rk, v in V.items():
        if rk == 'canon':
            continue
        for fr in ('aft', 'deck'):
            gg = v['geometry'][fr]; mo = v['aft_motion'] if fr == 'aft' else v['deck_motion']
            boxes = '; '.join(f"{b_[2].replace(RACK + '_', '')} {b_[0][0]:+.2f}..{b_[1][0]:+.2f} / {-b_[1][1]:.2f}..{-b_[0][1]:.2f} h / {b_[0][2]:+.2f}..{b_[1][2]:+.2f}" for b_ in gg['stowed'])
            mr, sr = mo['motion_vs_room'], mo['stowed_vs_room']; mv = min(mr['clearance_m'], sr['clearance_m']); nn = mr['nearest'] if mr['clearance_m'] <= sr['clearance_m'] else sr['nearest']
            hk = mo.get('motion_stowed_vs_hatch_passage') or mo.get('motion_stowed_vs_landing_well')
            mm = (v['aft_motion'].get('mesh') if fr == 'aft' else (v['deck']['A3']['motion_mesh'].get('deck')))
            L.append(f"| {rk} | {'locked 1.5 g' if fr == 'aft' else 'deck'} | {boxes} | {_st(mv)} {f3(mv)} | {nn} | {f3(hk['clearance_m'])} | "
                     f"{'' if not mm else f'{_st(mm[0])} {f3(mm[0])} ({mm[1]}, {mm[2]})'} | {f3(mo['canon_mess_overlap_m'])} |")
    L += ['', 'Plane values capped at +0.30 m, mesh at +0.10 m. "Canon Mess overlap": the stowed boxes (and the deck couch) against the Mess block',
          'the A169 swap displaces; negative = they occupy the Mess\'s place.', '',
          '#### Locked 1.5 g (aft down): V1 / V3 at Burn_Couch_1 and Burn_Couch_2 with the rack in its 1.5 g state', '',
          '| Variant | Sector | V1 BC1 | V1 BC2 | V3 BC1 | V3 BC2 | Best | Governing (best) |', '| --- | --- | --- | --- | --- | --- | --- | --- |']
    for rk, v in V.items():
        for sec in ('A3', 'B3'):
            a = v['aft'][sec]; b_ = a['best']; bc = a[b_['aid']]['couches'][b_['couch']]
            L.append(f"| {rk} | {sec} | " + ' | '.join(cell(a[vv]['couches'][cch]) for vv in ('V1', 'V3') for cch in COUCHES)
                     + f" | {b_['aid']} {b_['couch'].replace('Burn_Couch_', 'BC')} {cell(b_)} | {bc['governing'][0]} {f3(bc['governing'][1])}"
                     + (f"; {bc['sweep'].get('carrier')} {bc['sweep'].get('case')} at {bc['sweep'].get('nearest')}" if bc['governing'][0] and bc['governing'][0].startswith('carrier') else '') + ' |')
    L += ['', '#### Parts (m), locked 1.5 g, A3 (B3 identical layout), worst carrier', '',
          '| Variant | Aid | Couch | Litter | HW room | HW hatch | HW litter | Rescuers | Reach | Egress | Care parked | Sweep (mesh) | HW mesh | Rescuers mesh | Care mesh | Rack motion (plane) | Rack hatch | Rack motion (mesh) | Least |',
          '| ' + ' | '.join(['---']*19) + ' |']
    ks = ['litter swept envelope vs room (plane)', 'hardware vs room (plane)', 'hardware vs hatch passage (plane)', 'hardware vs litter, same instant (plane)', None,
          'rescuer reach (0.60 m path)', 'egress past the deployed aid (0.60 m)', 'care after set-down, aid parked (plane)', 'carrier sweep hatch -> device + poses (mesh, worst class)',
          'hardware vs built meshes (mesh)', 'rescuers vs built meshes (mesh capsules)', 'care after set-down vs built meshes (mesh)',
          'rack stowage motion + stowed position (plane, aft)', 'rack motion / stowed vs hatch passage (plane)', 'rack stowage motion + stowed position (mesh, aft)']
    for rk, v in V.items():
        for vv in ('V1', 'V3'):
            for cch, x in v['aft']['A3'][vv]['couches'].items():
                p = x['parts']; cells = []
                for k_ in ks:
                    cells.append(f3(min(y for y in (p['rescuer guide (plane)'], p['rescuer control (plane)']) if y is not None)) if k_ is None else f3(p.get(k_)) if k_ in p else '')
                L.append(f"| {rk} | {vv}{'' if not x.get('order') else ' ' + x['order']} | {cch.replace('Burn_Couch_', 'BC')} | " + ' | '.join(cells) + f' | {cell(x)} |')
    L += ['', '#### 0 g / spin / stopped (deck frame): fold-down couch with the rack in its deck emergency state', '',
          '| Variant | Sector | Couch placement | Care | Transfer | Reach | Egress | Normal: stow vs canon rack | Normal: egress | Rack motion vs stowed couch | Rack motion + stowed (plane) | Landing well | Sweep (mesh) | Attendants (mesh) | Kit (mesh) | Rack motion (mesh) | Least | Unsuited A/C/K | Governing |',
          '| ' + ' | '.join(['---']*19) + ' |']
    pk = ['screen care station (care point + kit + two attendants)', 'screen transfer station (worst carrier beside + rescuers)', 'screen attendant reach (0.60 m)',
          'screen egress past the deployed station (0.60 m)', 'normal state: stowed couch vs canon rack / room (plane)', 'normal state: egress with the couch stowed (0.60 m)',
          'rack motion vs the stowed couch (plane)', 'rack stowage motion + stowed position (plane, deck)', 'rack motion / stowed vs landing well + ladder (plane)',
          'carrier sweep hatch -> care point + slide (worst class)', 'mesh attendants (capsules, built meshes)', 'mesh kit (no overlap)', 'rack stowage motion + stowed position (mesh, deck)']
    for rk, v in V.items():
        for sec in ('A3', 'B3'):
            x = v['deck'][sec]; p = x['parts']; cp = x['couch']
            L.append(f"| {rk} | {sec} | {cp['axis']} {cp['footprint_uv']}{' screened' if cp['screened_placement'] else ' re-placed'} | "
                     + ' | '.join(f3(p[k_]) if k_ in p else '' for k_ in pk) + f" | {cell(x)} | {f3(x['least_unsuited_m'])} | {x['governing'][0]} |")
    L += ['', 'Screened placement (x 0.90..1.60, z 0.45..2.45, across, hinged on the forward fit-out line) with each variant, zone screen only:', '']
    for rk, v in V.items():
        q = v['deck']['A3']['screened_placement']
        if q:
            L.append(f"- {rk}: station {f3(q['governing_m'])} (care {f3(q['care']['clearance_m'])} vs {q['care']['nearest']}, transfer {f3(q['transfer_worst']['clearance_m'])} "
                     f"{q['transfer_worst']['carrier']} vs {q['transfer_worst']['nearest']}, egress {f3(q['egress_worst']['clearance_m'])} to {q['egress_worst']['target']}); "
                     f"normal-state stow {f3(q['normal_stowed']['clearance_m'])} vs {q['normal_stowed']['nearest']}; motion vs stowed couch {f3(q['motion_vs_stowed_couch']['clearance_m'])}; "
                     f"all {f3(q['governing_all_m'])}.")
    L += ['', '### 24 sector-states with A3 / B3 replaced (the rack-removal result no longer counts)', '',
          f"o13 with the changes (rack removed, superseded): {r['tally_o13_with_change']}; ring B {r['tally_o13_ringB']}.", '',
          '| Variant | A3 0g / spin / stopped | A3 locked 1.5 g | Tally (24) | Ring B (12) |', '| --- | --- | --- | --- | --- |']
    for rk, t in r['tallies'].items():
        gd = t['garden']['A3']
        L.append(f"| {rk} | {cell(gd['0g'])} | {cell(gd['locked_1.5g'])} | {t['all']} | {t['ringB']} |")
    L += ['', '#### OPEN (nothing estimated)', '']+[f'- {x}' for x in r['open']]+['', O13C_REVIEW, '']
    return '\n'.join(L)


O13C_REVIEW = """#### Result (Claude; numbers from the tables above)

1. **No variant restores a PASS. Tally: 24 FAIL of 24 for every variant (ring B: 12 FAIL).** The o13 tally of 6 PASS / 18 FAIL
   depended on removing the rack: the 6 PASS were the garden deck states at +0.075, and they do not survive.
2. **Normal state, canon rack: the screened fold-down couch does not fit.**
   - Stowed, the couch overlaps Garden_Rack_1's forward end by 0.30 m: the screened stow at x 1.30..1.60 lies on rack x 1.30..1.60.
   - Couches hinged on the forward fit-out line all overlap the rack by 0.30 m when stowed. The outboard wall leaves only 1.65 m of
     length beside the rack, and the couch is 2.00 m long.
   - Only the outboard-wall line (in the Mess bay, x -1.10..0.90, z 1.92..2.62) stows clear of the canon rack (+0.050).
   - With the rack left in place (canon), that couch gives FAIL -0.444. The S x1.08 litter meets the rack on the way round its aft end,
     and the S x1.08 transfer -0.270 meets Couch_Lockers_1. Unsuited classes only: -0.250.
3. **Locked 1.5 g: only the slide brings back the o13 value, and it is still FAIL.**
   - Slide (aft section A, x -0.55..0.90, runs outboard to z 2.07..2.57 for the emergency): V3 at BC1, -0.066. This equals the removal
     result.
     - The aid, the litter sweep (+0.100 mesh), the hardware and the rescuer capsules clear.
     - The motion clears the room (plane +0.30; mesh +0.089 to the pressure envelope) and the hatch passage.
     - What governs is egress past the deployed aid, the same -0.066 the care station has without any aid. Rescuer reach is -0.003.
   - Swing: V3 BC1 -0.150. The leaf, stowed at x 0.40..0.90, z 0.95..2.40, narrows the litter path. The motion vs leaf F is +0.021
     (MARGINAL).
   - Trays: the frame stays, so BC1 stays blocked (litter -0.456).
   - Canon: BC1 is blocked (-0.513 / -0.556). BC2 governs at -0.140 (rescuer reach and egress), as stated in the o13 review.
4. **0 g / spin / stopped: every variant FAILs, and the motion itself conflicts.**
   - Slide is closest. Couch re-placed across at z 0.10..2.10; the carrier sweep passes for every class (+0.092).
     - The station still fails: head-end attendant vs ECLSS_Bay -0.050 (mesh -0.000), kit vs the slid F section -0.035.
     - Section F slides through the stowed couch (-0.183 plane), and the stowed couch overlaps the canon rack in normal state (-0.300).
   - Swing: F's far corner hits the forward end wall at 40 deg (-0.058), and the leaves take the bay the care station needs (-0.500).
   - Trays: the frame and the module column take the aisle and bay (-0.531).
   - All moved positions also overlap the canon Mess footprint (-0.47 to -0.85). The study still needs the A169 Mess displacement.
5. **Best variant: slide.** It is the only one with a motion that clears the room and the hatch in both frames. It is horizontal in
   both frames, so it never lifts the rack against 1.5 g.
   - It brings 1.5 g to -0.066, still FAIL.
   - It does not give a working deck care point. The fold-down couch has no stow position compatible with the canon rack and the slid
     sections.
   - A consistent single design is not found. The outboard-wall couch (stow +0.050 in normal state) and the slid section would share
     the outboard wall (overlap 0.25 m).
   - Next useful geometry question: a fold-down couch whose stowed form fits the canon garden, or a care point outside the rack / Mess
     footprint. It is not a better rack mechanism.
6. **OPEN** as listed. Stowage time, crew actions, plant survival, water / power interfaces, ratings and masses are not estimated.

Method notes:
- Rack sections are bounding boxes (conservative to the whitebox parts).
- The swing leaves are trimmed by 0.10 m at the hinge post (the fitting, P13 anchor rule). The trays modules ride on the frame, and the
  slide runs along the split plane: design contact, not counted.
- Mesh values come from hum003_routes on the built model with the rack and the Mess replaced in memory. Plane values are capped at
  +0.30 m and mesh values at +0.10 m.
- A3 and B3 share one layout and give identical numbers.
- Passing checks are not engineering proof.
"""


def plan_svg(r):
    """One plan still (deck frame, looking down from the overhead): the garden sector, the canon rack, each variant's stowed boxes and
    motion, the couch, the landing well and the burn couches."""
    s = _spec()
    import habitat_interior as hi
    import human_entry as he
    L_ = he.landing(s); sc = 120.0; X0, Z0 = 2.0, 3.0
    P = lambda x, z: ((x+X0)*sc, (z+Z0)*sc)
    blocks = hi.zones(s, GARDEN); out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{int(4.0*sc*4+60)}" height="{int(6.0*sc+60)}" font-family="sans-serif" font-size="11">',
                                         '<rect width="100%" height="100%" fill="#fff"/>']
    cols = {'swing': '#c0392b', 'slide': '#2471a3', 'trays': '#7d6608', 'canon': '#333'}
    for i, (rk, v) in enumerate(r['variants'].items()):
        ox = i*(4.0*sc+15)
        rect = lambda lo, hi_, st: (lambda a, b_: f'<rect x="{ox+min(a[0], b_[0]):.1f}" y="{min(a[1], b_[1]):.1f}" width="{abs(b_[0]-a[0]):.1f}" height="{abs(b_[1]-a[1]):.1f}" {st}/>')(P(lo[0], lo[2]), P(hi_[0], hi_[2]))
        out.append(f'<text x="{ox+10}" y="16" font-size="14" font-weight="bold">{rk}</text>')
        out.append(rect((-1.7, 0, -2.775), (1.7, 0, 2.775), 'fill="none" stroke="#999"'))
        for b_ in blocks:
            if b_['name'] in SWAP:
                continue
            out.append(rect(b_['min'], b_['max'], 'fill="#ddd" stroke="#888"'))
        out.append(rect((L_['well_x'][0], 0, L_['well_z'][0]), (L_['well_x'][1], 0, L_['well_z'][1]), 'fill="none" stroke="#999" stroke-dasharray="4 3"'))
        mess = next(b_ for b_ in blocks if b_['name'] == 'Mess')
        out.append(rect(mess['min'], mess['max'], 'fill="none" stroke="#aaa" stroke-dasharray="2 4"'))
        rb = next(b_ for b_ in blocks if b_['name'] == RACK)
        out.append(rect(rb['min'], rb['max'], 'fill="none" stroke="#2e7d32" stroke-width="2" stroke-dasharray="6 3"'))
        gg = v['geometry']['deck']
        for b_ in gg['in_place']:
            out.append(rect(b_[0], b_[1], 'fill="#a5d6a7" stroke="#2e7d32"'))
        for sw_ in gg['swept']:
            cs_ = ob_corners((tuple(sw_['ob'][0]), tuple(tuple(a) for a in sw_['ob'][1]), tuple(sw_['ob'][2])))
            pts = [P(q[0], q[2]) for q in (cs_[0], cs_[4], cs_[6], cs_[2])]
            out.append('<polygon points="' + ' '.join(f'{ox+x:.1f},{y:.1f}' for x, y in pts) + f'" fill="none" stroke="{cols[rk]}" stroke-opacity="0.35"/>')
        for b_ in gg['stowed']:
            out.append(rect(b_[0], b_[1], f'fill="{cols[rk]}" fill-opacity="0.35" stroke="{cols[rk]}"'))
        cp = v['couch']
        out.append(rect(cp['deployed'][0], cp['deployed'][1], 'fill="none" stroke="#6a1b9a" stroke-width="2"'))
        out.append(rect(cp['stowed'][0], cp['stowed'][1], 'fill="#6a1b9a" fill-opacity="0.25" stroke="#6a1b9a"'))
        x = v['deck']['A3']; a = v['aft']['A3']['best']
        out.append(f'<text x="{ox+10}" y="{6.0*sc+30}">deck {x["status"]} {x["least_m"]:+.3f}; 1.5 g {a["aid"]} {a["couch"].replace("Burn_Couch_", "BC")} {a["status"]} {a["least_m"]:+.3f}</text>')
    out.append(f'<text x="10" y="{6.0*sc+50}">Plan, deck frame (x right = forward, z down = outboard). Grey: fit-out kept; green dashed: canon rack; green: in place; colour: stowed (filled) and motion (outline); purple: fold-down couch deployed / stowed; dashed grey: Mess (A169 displaced) and landing well.</text>')
    out.append('</svg>')
    RUN13C.mkdir(parents=True, exist_ok=True); (RUN13C/'garden_rack_plan.svg').write_text('\n'.join(out)+'\n')


def main():
    argv = sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else sys.argv[1:]
    a = argparse.ArgumentParser()
    a.add_argument('mode', choices=('screen', 'sweep', 'station', 'ringa', 'run', 'collect', 'o13screen', 'o13sweep', 'o13care', 'a2plane', 'o13run', 'o13collect',
                                    'o13cscreen', 'o13ccare', 'o13crun', 'o13ccollect'))
    a.add_argument('--rack', choices=tuple(RACKS))
    a.add_argument('--sector'); a.add_argument('--frame', default='deck'); a.add_argument('--carrier', default='A'); a.add_argument('--route')
    a.add_argument('--workers', type=int, default=16); a.add_argument('--only', default=''); a.add_argument('--timeout', type=int, default=7200)
    a.add_argument('--force', action='store_true'); a.add_argument('--fn'); a.add_argument('--variant'); a.add_argument('--couch'); a.add_argument('--option')
    args = a.parse_args(argv)
    {'screen': lambda: screen(), 'sweep': lambda: sweep(args), 'station': lambda: station(args), 'ringa': lambda: ringa(args),
     'run': lambda: run(args), 'collect': lambda: collect(), 'o13screen': lambda: o13_screen(args), 'o13sweep': lambda: o13_sweep(args),
     'o13care': lambda: o13_care(args), 'a2plane': lambda: a2_plane(args), 'o13run': lambda: run13(args), 'o13collect': lambda: collect13(),
     'o13cscreen': lambda: o13c_screen(args), 'o13ccare': lambda: o13c_care(args), 'o13crun': lambda: run13c(args), 'o13ccollect': lambda: collect13c()}[args.mode]()


if __name__ == '__main__':
    main()
