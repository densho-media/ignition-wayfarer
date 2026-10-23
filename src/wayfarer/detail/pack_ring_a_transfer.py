"""Detail pack ring_a_transfer (docs/MODULES.md): ring A's spin transfer, module WF-RING-A. M7.XFR, the lining of the despun transfer drum,
on the anchor WF-RING-A.DRUM.1 (Drum_1: despun at the index angle, turning with the ring only while drum_sync is 1), and M7.SPK, the
sector-1 crew tube's radial run, on WF-RING-A.ROTOR.1 (Rotor_1: turns with the ring). Each detail asset is built in its anchor object's local
frame and its instance inherits that motion, so the drum lining stays despun and the tube cladding spins.

Owned with data/detail/ring_a_transfer.toml (manifest, [params.drum] and [params.tube]) and the generated assets
assets/wayfarer/detail/WF_DETAIL_M7_XFR.blend and WF_DETAIL_M7_SPK.blend, which WF_HABITAT links. Accepted by the owner on 2026-10-20 with
the M7 section (L4_VISUAL_ACCEPTED, scope M7); migrated unchanged from production_detail.py (MOD phase 2). Reads crew_transfer, human_entry
and route_fitout and the shared M7 panel grammar [production.entry]; changes none of them. Closures, seals, bearings and interfaces stay
physics-locked proxies.
"""
import math
import production_detail as pd

PACK = 'ring_a_transfer'


# M7.XFR: ring A's despun drum (drum frame, parented to Drum_j): a lining of replaceable panels on the drum's outer wall above the crawl
# rail, between and around the route frames, off the tube openings (their frames and door seal lands are physics-locked closures), the
# handrails, lights, transfer panel and placards; housings round the drum lights. No closure, seal, bearing or interface is touched.
def drum_keepouts(s, j):
    import crew_transfer as ct
    import human_entry as he
    import route_fitout as rf
    rot, v, la = he.vestibule_station(s, j); R = v['clear']; h = s['human_entry']
    coord = lambda p: (p[0], math.degrees(math.atan2(p[2], p[1])))
    out = []
    edge = v['port_clear']+h['hatch_frame_width_m']+pd.params(s, PACK)['drum']['opening_margin_m']
    for a in la.values():
        half = math.degrees(math.asin(min(1.0, edge/R)))
        out.append((-1e3, 1e3, math.degrees(a)-half, math.degrees(a)+half))
    for q in he.vestibule_fixtures(s, j)+[e for e in rf.drum_elements(s, j) if e['shape'] != 'ring']:
        if '_Frame_' in q['name'] and q['shape'] == 'xarc':
            out.append((q['x'][0], q['x'][1], q['phi'][0]-.5, q['phi'][1]+.5)); continue
        w = pd.windows_of(pd.fixture_points(q), coord, .04, 2.5)
        if w:
            out.append(w)
    return out


@pd.builder('M7.XFR')
def drum_elements(s):
    import crew_transfer as ct
    import human_entry as he
    j = s['induction']['ring']; d = pd.params(s, PACK)['drum']; q = dict(s['production']['entry'], **{k: v for k, v in d.items() if k in s['production']['entry']})
    rot, v, la = he.vestibule_station(s, j); R = v['clear']; h = s['human_entry']; w = h['chamber_wall_m']
    a0 = v['cu0']+w+h['crawl_rail_height_m']+h['handrail_radius_m']+.06; a1 = v['cu1']-w-.02
    at = lambda x, r, a: ct.radial(x, r, a); keep = drum_keepouts(s, j); gap = math.degrees(q['seam_m']/R); out = []
    wins = [(lo, hi) for w0, w1, lo, hi in keep if w0 < a1 and a0 < w1]
    for k, (p0, p1) in enumerate(pd.windows_free(wins, -180.0, 180.0, gap), 1):
        out += pd.clad_bay('M7.XFR', f'XFR_P{k}', at, R, a0, a1, p0, p1, q, 'panel_machinery', n_min=1)
    for fx in (x for x in he.vestibule_fixtures(s, j) if x['role'] == 'light strip'):
        c, ax = he.box_frame(None, fx); la_, lt, lr = fx['size']; lip, hd = q['housing_lip_m'], q['housing_depth_m']
        x = c[0]; phi = math.degrees(math.atan2(c[2], c[1])); dp = math.degrees((lt/2+lip)/R)
        for side, (lo, hi) in enumerate(((phi-dp, phi-dp+math.degrees(lip/R)), (phi+dp-math.degrees(lip/R), phi+dp)), 1):
            vs, fs = pd.bent(at, x-la_/2-lip, x+la_/2+lip, R-hd, R-.001, lo, hi, n=1)
            out.append(pd.element('M7.XFR', 'Housings', f"{fx['name']}_Lip_{side}", 'housing', 'ENGINEERING_FLEXIBLE', 'light-strip housing lip', vs, fs, bevel=.002))
    return out


def drum_check(s, els):
    import human_entry as he
    j = s['induction']['ring']; rot, v, la = he.vestibule_station(s, j); R = v['clear']; keep = drum_keepouts(s, j); fails = []
    depth = s['production']['entry']['housing_depth_m']; h = s['human_entry']
    for q in els:
        rs = [math.hypot(p[1], p[2]) for p in q['vs']]; xs = [p[0] for p in q['vs']]
        if min(rs) < R-depth-1e-6:
            fails.append(f"{q['name']}: {R-min(rs):.3f} m off the drum wall (the suited annulus keeps {v['clear']-v['r0']:.2f} m)")
        if min(xs) < v['cu0']-1e-6 or max(xs) > v['cu1']+1e-6:
            fails.append(f"{q['name']}: beyond the drum chamber")
        if q['family'] in ('Panels', 'Trays', 'Fasteners'):
            w = pd.windows_of(q['vs'], lambda p: (p[0], math.degrees(math.atan2(p[2], p[1]))), 0.0, 0.0)
            if not pd.patch_free(keep, w[0]+1e-6, w[1]-1e-6, w[2]+1e-6, w[3]-1e-6):
                fails.append(f"{q['name']}: on a keep-out window")
    return fails


pd.CHECKS['M7.XFR'] = drum_check


# M7.SPK: ring A's crew tube to sector 1, its radial run (rotor frame, parented to Rotor_j): ring frames every frame_pitch_m and the
# cladding between them, off the ladder, its arrest rail and brackets, the light strips, the hatch panel and the fit-out (deck band,
# placards, bezel, handles). The tube's collar, elbows and the sector hatch stay as they are.
def tube_frame(s):
    import human_entry as he
    j = s['induction']['ring']; rot, v, la, frames = he.spoke_station(s, j); fr = frames[1]; R_ = he.RUN
    o, d, n1, n2 = fr['points'][R_], fr['d'][R_], fr['n1'][R_], fr['n2'][R_]
    def at(t, r, a):
        return tuple(o[i]+d[i]*t+r*(math.cos(a)*n1[i]+math.sin(a)*n2[i]) for i in range(3))
    def coord(p):
        q = [p[i]-o[i] for i in range(3)]
        return (sum(q[i]*d[i] for i in range(3)), math.degrees(math.atan2(sum(q[i]*n2[i] for i in range(3)), sum(q[i]*n1[i] for i in range(3)))))
    return j, fr, at, coord


def tube_keepouts(s):
    import human_entry as he
    import route_fitout as rf
    j, fr, at, coord = tube_frame(s); t0, t1 = he.run_span(s, fr); out = []
    for q in he.spoke_fixtures(s, j)+rf.tube_end_elements(s, j):
        if q['shape'] == 'tarc':
            out.append((q['t'][0]-.03, q['t'][1]+.03, q['phi'][0]-2.0, q['phi'][1]+2.0)); continue
        pts = [p for p in pd.fixture_points(q) if t0-.5 <= coord(p)[0] <= t1+.5]
        w = pd.windows_of(pts, coord, .05, 3.0)
        if w:
            out.append(w)
    return out


@pd.builder('M7.SPK')
def tube_elements(s):
    import crew_transfer as ct
    import human_entry as he
    q = s['production']['entry']; t_ = pd.params(s, PACK)['tube']; j, fr, at, coord = tube_frame(s); rc = ct.tube_radii(s, j)[1]
    t0, t1 = he.run_span(s, fr); t0 += t_['end_inset_m']; t1 -= t_['end_inset_m']; keep = tube_keepouts(s); out = []
    gap = math.degrees(q['seam_m']/rc); n = max(1, round((t1-t0)/t_['frame_pitch_m'])); edges = [t0+(t1-t0)*i/n for i in range(n+1)]
    fw, fd = t_['frame_width_m'], t_['frame_depth_m']
    for i, tc in enumerate(edges):
        a, b = tc-fw/2, tc+fw/2
        wins = [(lo, hi) for w0, w1, lo, hi in keep if w0 < b and a < w1]
        for k, (p0, p1) in enumerate(pd.windows_free(wins, -180.0, 180.0, 1.0), 1):
            vs, fs = pd.bent(at, max(a, t0-fw/2), min(b, t1+fw/2), rc-fd, rc-.0003, p0, p1)
            out.append(pd.element('M7.SPK', 'Frames', f'SPK_Frame_{i}_{k}', 'frame_structural', 'ENGINEERING_FLEXIBLE',
                               'tube ring frame carrying the lining panels', vs, fs, bevel=.004))
    for i, (a, b) in enumerate(zip(edges, edges[1:]), 1):
        s0, s1 = a+fw/2, b-fw/2
        wins = [(lo, hi) for w0, w1, lo, hi in keep if w0 < s1 and s0 < w1]
        for k, (p0, p1) in enumerate(pd.windows_free(wins, -180.0, 180.0, gap), 1):
            out += pd.clad_bay('M7.SPK', f'SPK_B{i}_P{k}', at, rc, s0, s1, p0, p1, q, 'panel_inhabited')
    return out


def tube_check(s, els):
    import crew_transfer as ct
    import human_entry as he
    j, fr, at, coord = tube_frame(s); rc = ct.tube_radii(s, j)[1]; keep = tube_keepouts(s); fails = []
    lim = pd.params(s, PACK)['tube']['frame_depth_m']; t0, t1 = he.run_span(s, fr)
    for q in els:
        loc = [coord(p) for p in q['vs']]
        rr = [math.dist(p, at(c[0], 0.0, 0.0)) for p, c in zip(q['vs'], loc)]
        if min(rr) < rc-lim-1e-6:
            fails.append(f"{q['name']}: {rc-min(rr):.3f} m off the tube wall")
        if min(c[0] for c in loc) < t0-.05 or max(c[0] for c in loc) > t1+.05:
            fails.append(f"{q['name']}: beyond the run")
        if q['family'] in ('Panels', 'Trays', 'Fasteners', 'Frames'):
            w = pd.windows_of(q['vs'], coord, 0.0, 0.0)
            if not pd.patch_free(keep, w[0]+1e-6, w[1]-1e-6, w[2]+1e-6, w[3]-1e-6):
                fails.append(f"{q['name']}: on a keep-out window")
    return fails


pd.CHECKS['M7.SPK'] = tube_check
