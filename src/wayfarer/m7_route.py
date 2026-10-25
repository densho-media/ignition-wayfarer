"""The M7 route production modules (standard library only): the despun transfer drum's lining, a crew tube's radial-run cladding and a
sector's overhead service layer, in the accepted M7 panel grammar ([production.entry]), parameterised by ring, sector and function. Ring A's
accepted packs (ring_a_transfer: M7.XFR, M7.SPK; m7_ra1: M7.RA1) and ring B's Phase 4 S8a pack (ring_b_transfer: RB.XFR, RB.SPK, RB.SEC)
build from these definitions; moved unchanged from ring A's packs, whose output stays identical (geometry fingerprint). Reads crew_transfer,
human_entry, route_fitout and habitat_interior; changes none of them. Closures, seals, bearings and interfaces stay physics-locked proxies.
"""
import math
import production_detail as pd


# The drum (drum frame, parented to Drum_j): a lining of replaceable panels on the drum's outer wall above the crawl rail, between and around
# the route frames, off the tube openings (their frames and door seal lands are physics-locked closures), the handrails, lights, transfer
# panel and placards; housings round the drum lights. No closure, seal, bearing or interface is touched.
def drum_keepouts(s, j, drum):
    import human_entry as he
    import route_fitout as rf
    rot, v, la = he.vestibule_station(s, j); R = v['clear']; h = s['human_entry']
    coord = lambda p: (p[0], math.degrees(math.atan2(p[2], p[1])))
    out = []
    edge = v['port_clear']+h['hatch_frame_width_m']+drum['opening_margin_m']
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


def drum_elements(s, j, assembly, drum, tag):
    import crew_transfer as ct
    import human_entry as he
    q = dict(s['production']['entry'], **{k: v for k, v in drum.items() if k in s['production']['entry']})
    rot, v, la = he.vestibule_station(s, j); R = v['clear']; h = s['human_entry']; w = h['chamber_wall_m']
    a0 = v['cu0']+w+h['crawl_rail_height_m']+h['handrail_radius_m']+.06; a1 = v['cu1']-w-.02
    at = lambda x, r, a: ct.radial(x, r, a); keep = drum_keepouts(s, j, drum); gap = math.degrees(q['seam_m']/R); out = []
    wins = [(lo, hi) for w0, w1, lo, hi in keep if w0 < a1 and a0 < w1]
    for k, (p0, p1) in enumerate(pd.windows_free(wins, -180.0, 180.0, gap), 1):
        out += pd.clad_bay(assembly, f'{tag}_P{k}', at, R, a0, a1, p0, p1, q, 'panel_machinery', n_min=1)
    for fx in (x for x in he.vestibule_fixtures(s, j) if x['role'] == 'light strip'):
        c, ax = he.box_frame(None, fx); la_, lt, lr = fx['size']; lip, hd = q['housing_lip_m'], q['housing_depth_m']
        x = c[0]; phi = math.degrees(math.atan2(c[2], c[1])); dp = math.degrees((lt/2+lip)/R)
        for side, (lo, hi) in enumerate(((phi-dp, phi-dp+math.degrees(lip/R)), (phi+dp-math.degrees(lip/R), phi+dp)), 1):
            vs, fs = pd.bent(at, x-la_/2-lip, x+la_/2+lip, R-hd, R-.001, lo, hi, n=1)
            out.append(pd.element(assembly, 'Housings', f"{fx['name']}_Lip_{side}", 'housing', 'ENGINEERING_FLEXIBLE', 'light-strip housing lip', vs, fs, bevel=.002))
    return out


def drum_check(s, j, els, drum):
    import human_entry as he
    rot, v, la = he.vestibule_station(s, j); R = v['clear']; keep = drum_keepouts(s, j, drum); fails = []
    depth = s['production']['entry']['housing_depth_m']
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


# A crew tube's radial run (rotor frame, parented to Rotor_j): ring frames every frame_pitch_m and the cladding between them, off the
# ladder, its arrest rail and brackets, the light strips, the hatch panel and the fit-out (deck band, placards, bezel, handles). The tube's
# collar, elbows, neck and the sector hatch stay as they are.
def tube_frame(s, j, sector):
    import human_entry as he
    rot, v, la, frames = he.spoke_station(s, j); fr = frames[sector]; R_ = he.RUN
    o, d, n1, n2 = fr['points'][R_], fr['d'][R_], fr['n1'][R_], fr['n2'][R_]
    def at(t, r, a):
        return tuple(o[i]+d[i]*t+r*(math.cos(a)*n1[i]+math.sin(a)*n2[i]) for i in range(3))
    def coord(p):
        q = [p[i]-o[i] for i in range(3)]
        return (sum(q[i]*d[i] for i in range(3)), math.degrees(math.atan2(sum(q[i]*n2[i] for i in range(3)), sum(q[i]*n1[i] for i in range(3)))))
    return j, fr, at, coord


def tube_keepouts(s, j, sector):
    import human_entry as he
    import route_fitout as rf
    j, fr, at, coord = tube_frame(s, j, sector); t0, t1 = he.run_span(s, fr); out = []
    for q in he.spoke_fixtures(s, j)+rf.tube_end_elements(s, j):
        if q['shape'] == 'tarc':
            out.append((q['t'][0]-.03, q['t'][1]+.03, q['phi'][0]-2.0, q['phi'][1]+2.0)); continue
        pts = [p for p in pd.fixture_points(q) if t0-.5 <= coord(p)[0] <= t1+.5]
        w = pd.windows_of(pts, coord, .05, 3.0)
        if w:
            out.append(w)
    return out


def tube_elements(s, j, sector, assembly, tube, tag):
    import crew_transfer as ct
    import human_entry as he
    q = s['production']['entry']; t_ = tube; j, fr, at, coord = tube_frame(s, j, sector); rc = ct.tube_radii(s, j)[1]
    t0, t1 = he.run_span(s, fr); t0 += t_['end_inset_m']; t1 -= t_['end_inset_m']; keep = tube_keepouts(s, j, sector); out = []
    gap = math.degrees(q['seam_m']/rc); n = max(1, round((t1-t0)/t_['frame_pitch_m'])); edges = [t0+(t1-t0)*i/n for i in range(n+1)]
    fw, fd = t_['frame_width_m'], t_['frame_depth_m']
    for i, tc in enumerate(edges):
        a, b = tc-fw/2, tc+fw/2
        wins = [(lo, hi) for w0, w1, lo, hi in keep if w0 < b and a < w1]
        for k, (p0, p1) in enumerate(pd.windows_free(wins, -180.0, 180.0, 1.0), 1):
            vs, fs = pd.bent(at, max(a, t0-fw/2), min(b, t1+fw/2), rc-fd, rc-.0003, p0, p1)
            out.append(pd.element(assembly, 'Frames', f'{tag}_Frame_{i}_{k}', 'frame_structural', 'ENGINEERING_FLEXIBLE',
                               'tube ring frame carrying the lining panels', vs, fs, bevel=.004))
    for i, (a, b) in enumerate(zip(edges, edges[1:]), 1):
        s0, s1 = a+fw/2, b-fw/2
        wins = [(lo, hi) for w0, w1, lo, hi in keep if w0 < s1 and s0 < w1]
        for k, (p0, p1) in enumerate(pd.windows_free(wins, -180.0, 180.0, gap), 1):
            out += pd.clad_bay(assembly, f'{tag}_B{i}_P{k}', at, rc, s0, s1, p0, p1, q, 'panel_inhabited')
    return out


def tube_check(s, j, sector, els, tube):
    import crew_transfer as ct
    import human_entry as he
    j, fr, at, coord = tube_frame(s, j, sector); rc = ct.tube_radii(s, j)[1]; keep = tube_keepouts(s, j, sector); fails = []
    lim = tube['frame_depth_m']; t0, t1 = he.run_span(s, fr)
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


# A sector's overhead (sector frame: +X axial, +Y radially outward = down in spin, +Z tangential; deck at y 0), parented to that sector's
# instance only: removable service panels on trays in the bays of the route fit-out's overhead frame grid, off the aisle lights, route
# bands and chevrons, diffuser, landing chase, thrust step, hatch frame and its rails, and the hatch opening plus the landing well's column
# the route descends through; housings round the aisle lights. Nothing comes below overhead_floor_y_m, so the aisle, the fit-out's access
# strips and every route body stay as they were. `function` is the sector's (its fit-out decides the keep-outs).
def sector_overhead_items(s, function, sq):
    import human_entry as he
    import route_fitout as rf
    els = rf.sector_elements(s, function)+rf.sector_sign(s, function)+rf.seraph_elements(s, function)[0]+rf.landing_elements(s)+he.landing_fixtures(s)
    out = []
    for q in els:
        pts = [q['min'], q['max']] if q['shape'] == 'box' and 'min' in q else pd.fixture_points(q)
        if pts and min(p[1] for p in pts) < sq['item_floor_y_m']:
            out.append((q['name'], [min(p[k] for p in pts) for k in range(3)], [max(p[k] for p in pts) for k in range(3)], q))
    return out


def sector_keepouts(s, function, sq, x0, x1):
    """z intervals of the overhead a bay x0..x1 leaves: overhead items (frames excluded: they bound the bays), the hatch opening and the
    landing well, each widened by the margin."""
    import habitat_interior as hi
    import human_entry as he
    m = sq['margin_m']; out = []
    for name, lo, hi_, el in sector_overhead_items(s, function, sq):
        if '_Frame_' in name or lo[1] > sq['touch_y_m']:
            continue                                     # frames bound the bays; items hanging clear below the panels pass under them
        if el['shape'] == 'tube':
            r = el.get('r1', .9); c = el['a']; lo, hi_ = [c[0]-r, lo[1], c[2]-r], [c[0]+r, hi_[1], c[2]+r]
        if lo[0]-m < x1 and x0 < hi_[0]+m:
            out.append((lo[2]-m, hi_[2]+m))
    hx, hz, hr = hi.hatch_opening(s); hr += sq['hatch_margin_m']
    if abs((x0+x1)/2-hx) < hr or (x0 < hx < x1):
        dx = max(0.0, min(abs(x0-hx), abs(x1-hx))) if not (x0 < hx < x1) else 0.0
        half = math.sqrt(max(0.0, hr*hr-dx*dx)); out.append((hz-half, hz+half))
    L = he.landing(s)
    if L['well_x'][0]-m < x1 and x0 < L['well_x'][1]+m:
        out.append((L['well_z'][0]-m, L['well_z'][1]+m))
    return out


def sector_bays(s, function, sq):
    xs = sorted({(round(lo[0], 4), round(hi_[0], 4)) for name, lo, hi_, _ in sector_overhead_items(s, function, sq) if '_Frame_' in name})
    edges = [x for c in xs for x in c]
    return [(edges[2*i+1], edges[2*i+2]) for i in range(len(edges)//2-1) if edges[2*i+2]-edges[2*i+1] > .2]


def sector_elements(s, function, assembly, sq, tag):
    import habitat_interior as hi
    q = s['production']['entry']; out = []
    oh = next(b for b in hi.plates(s) if b['name'] == 'Interior_Overhead'); Y = oh['max'][1]; Z0, Z1 = -sq['span_z_m'], sq['span_z_m']
    seam, th, st, ins = q['seam_m'], q['panel_thickness_m'], q['fastener_m'], q['fastener_inset_m']
    down = (0.0, 1.0, 0.0); X, Zv = (1.0, 0.0, 0.0), (0.0, 0.0, 1.0)
    for b, (x0, x1) in enumerate(sector_bays(s, function, sq), 1):
        free = pd.windows_free(sector_keepouts(s, function, sq, x0, x1), Z0, Z1, 0.0)
        for k, (z0, z1) in enumerate(free, 1):
            if z1-z0 < sq['panel_min_m']:
                continue
            vs, fs = pd.box(((x0+x1)/2, Y+.0015, (z0+z1)/2), (X, down, Zv), (x1-x0-seam, .003, z1-z0-seam/2))
            out.append(pd.element(assembly, 'Trays', f'{tag}_B{b}_T{k}', 'gasket', 'ENGINEERING_FLEXIBLE', 'overhead panel carrier and seam gasket', vs, fs))
            n = max(1, math.ceil((z1-z0)/sq['panel_max_m']))
            for i in range(n):
                a, c = z0+(z1-z0)*i/n+seam/2, z0+(z1-z0)*(i+1)/n-seam/2
                vs, fs = pd.box(((x0+x1)/2, Y+.003+th/2, (a+c)/2), (X, down, Zv), (x1-x0-2*seam, th, c-a))
                out.append(pd.element(assembly, 'Panels', f'{tag}_B{b}_P{k}_{i+1}', 'panel_inhabited', 'ENGINEERING_FLEXIBLE',
                                   'removable overhead service panel (ducts, power and data above)', vs, fs, bevel=q['panel_bevel_m']))
                for sx in (x0+seam+ins, x1-seam-ins):
                    for sz in (a+ins, c-ins):
                        vs, fs = pd.box((sx, Y+.003+th+q['fastener_proud_m']/2, sz), (X, down, Zv), (st, q['fastener_proud_m'], st))
                        out.append(pd.element(assembly, 'Fasteners', f'{tag}_B{b}_P{k}_{i+1}_F{len(out)}', 'fastener', 'ENGINEERING_FLEXIBLE', 'quarter-turn panel fastener', vs, fs))
    lip, hd = q['housing_lip_m'], sq['housing_depth_m']
    for name, lo, hi_, el in sector_overhead_items(s, function, sq):
        if 'Aisle_Light' not in name:
            continue
        for side, x in enumerate((lo[0]-lip/2, hi_[0]+lip/2), 1):
            vs, fs = pd.box((x, Y+hd/2, (lo[2]+hi_[2])/2), (X, down, Zv), (lip, hd, hi_[2]-lo[2]+2*lip))
            out.append(pd.element(assembly, 'Housings', f'{name}_Housing_{side}', 'housing', 'ENGINEERING_FLEXIBLE', 'aisle light housing (long sides)', vs, fs, bevel=.002))
        for side, z in enumerate((lo[2]-lip/2, hi_[2]+lip/2), 1):
            vs, fs = pd.box(((lo[0]+hi_[0])/2, Y+hd/2, z), (X, down, Zv), (hi_[0]-lo[0], hd, lip))
            out.append(pd.element(assembly, 'Housings', f'{name}_Cap_{side}', 'housing', 'ENGINEERING_FLEXIBLE', 'aisle light housing (end caps)', vs, fs, bevel=.002))
    return out


def sector_check(s, els, sq):
    import habitat_interior as hi
    import human_entry as he
    hx, hz, hr = hi.hatch_opening(s); L = he.landing(s); fails = []
    for q in els:
        ys = [p[1] for p in q['vs']]
        if max(ys) > sq['overhead_floor_y_m']:
            fails.append(f"{q['name']}: reaches {max(ys):.3f} m, below the overhead zone ({sq['overhead_floor_y_m']} m)")
        for p in q['vs']:
            if math.hypot(p[0]-hx, p[2]-hz) < hr-1e-6 or (L['well_x'][0] < p[0] < L['well_x'][1] and L['well_z'][0] < p[2] < L['well_z'][1]):
                fails.append(f"{q['name']}: inside the hatch opening or the landing well's column"); break
    return fails
