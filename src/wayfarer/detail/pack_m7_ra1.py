"""Detail pack m7_ra1 (docs/MODULES.md): the M7.RA1 production layer of ring A sector 1 (HABITATION), module WF-RING-A.

Owned with data/detail/m7_ra1.toml (manifest and [params]) and the generated asset assets/wayfarer/detail/WF_DETAIL_M7_RA1.blend, which
WF_HABITAT links at the anchor WF-RING-A.SECTOR.1.1 (the sector instance). Accepted by the owner on 2026-10-20 with the M7 section
(L4_VISUAL_ACCEPTED, scope M7); migrated unchanged from production_detail.py. Reads route_fitout, human_entry and habitat_interior and the
shared [production.entry] values; changes none of them.
"""
import math
import production_detail as pd

PACK = 'm7_ra1'


# M7.RA1: ring A sector 1 (HABITATION), sector frame (+X axial, +Y radially outward = down in spin, +Z tangential; deck at y 0),
# parented to that sector's instance only. The overhead is the zone the layer details: removable service panels on trays in the bays of
# the route fit-out's overhead frame grid, off the aisle lights, route bands and chevrons, diffuser, landing chase, thrust step, hatch frame
# and its rails, and the hatch opening plus the landing well's column the route descends through; housings round the aisle lights.
# Nothing comes below overhead_floor_y_m, so the aisle, the berths' access strips and every route body stay as they were.
def sector_overhead_items(s):
    import human_entry as he
    import route_fitout as rf
    els = rf.sector_elements(s, 'HABITATION')+rf.sector_sign(s, 'HABITATION')+rf.seraph_elements(s, 'HABITATION')[0]+rf.landing_elements(s)+he.landing_fixtures(s)
    out = []
    for q in els:
        pts = [q['min'], q['max']] if q['shape'] == 'box' and 'min' in q else pd.fixture_points(q)
        if pts and min(p[1] for p in pts) < pd.params(s, PACK)['item_floor_y_m']:
            out.append((q['name'], [min(p[k] for p in pts) for k in range(3)], [max(p[k] for p in pts) for k in range(3)], q))
    return out


def sector_keepouts(s, x0, x1):
    """z intervals of the overhead a bay x0..x1 leaves: overhead items (frames excluded: they bound the bays), the hatch opening and the
    landing well, each widened by the margin."""
    import habitat_interior as hi
    import human_entry as he
    q = pd.params(s, PACK); m = q['margin_m']; out = []
    for name, lo, hi_, el in sector_overhead_items(s):
        if '_Frame_' in name or lo[1] > q['touch_y_m']:
            continue                                     # frames bound the bays; items hanging clear below the panels pass under them
        if el['shape'] == 'tube':
            r = el.get('r1', .9); c = el['a']; lo, hi_ = [c[0]-r, lo[1], c[2]-r], [c[0]+r, hi_[1], c[2]+r]
        if lo[0]-m < x1 and x0 < hi_[0]+m:
            out.append((lo[2]-m, hi_[2]+m))
    hx, hz, hr = hi.hatch_opening(s); hr += q['hatch_margin_m']
    if abs((x0+x1)/2-hx) < hr or (x0 < hx < x1):
        dx = max(0.0, min(abs(x0-hx), abs(x1-hx))) if not (x0 < hx < x1) else 0.0
        half = math.sqrt(max(0.0, hr*hr-dx*dx)); out.append((hz-half, hz+half))
    L = he.landing(s)
    if L['well_x'][0]-m < x1 and x0 < L['well_x'][1]+m:
        out.append((L['well_z'][0]-m, L['well_z'][1]+m))
    return out


def sector_bays(s):
    xs = sorted({(round(lo[0], 4), round(hi_[0], 4)) for name, lo, hi_, _ in sector_overhead_items(s) if '_Frame_' in name})
    edges = [x for c in xs for x in c]
    return [(edges[2*i+1], edges[2*i+2]) for i in range(len(edges)//2-1) if edges[2*i+2]-edges[2*i+1] > .2]


@pd.builder('M7.RA1')
def sector_elements(s):
    import habitat_interior as hi
    q = s['production']['entry']; sq = pd.params(s, PACK); out = []
    oh = next(b for b in hi.plates(s) if b['name'] == 'Interior_Overhead'); Y = oh['max'][1]; Z0, Z1 = -sq['span_z_m'], sq['span_z_m']
    seam, th, st, ins = q['seam_m'], q['panel_thickness_m'], q['fastener_m'], q['fastener_inset_m']
    down = (0.0, 1.0, 0.0); X, Zv = (1.0, 0.0, 0.0), (0.0, 0.0, 1.0)
    for b, (x0, x1) in enumerate(sector_bays(s), 1):
        free = pd.windows_free(sector_keepouts(s, x0, x1), Z0, Z1, 0.0)
        for k, (z0, z1) in enumerate(free, 1):
            if z1-z0 < sq['panel_min_m']:
                continue
            vs, fs = pd.box(((x0+x1)/2, Y+.0015, (z0+z1)/2), (X, down, Zv), (x1-x0-seam, .003, z1-z0-seam/2))
            out.append(pd.element('M7.RA1', 'Trays', f'RA1_B{b}_T{k}', 'gasket', 'ENGINEERING_FLEXIBLE', 'overhead panel carrier and seam gasket', vs, fs))
            n = max(1, math.ceil((z1-z0)/sq['panel_max_m']))
            for i in range(n):
                a, c = z0+(z1-z0)*i/n+seam/2, z0+(z1-z0)*(i+1)/n-seam/2
                vs, fs = pd.box(((x0+x1)/2, Y+.003+th/2, (a+c)/2), (X, down, Zv), (x1-x0-2*seam, th, c-a))
                out.append(pd.element('M7.RA1', 'Panels', f'RA1_B{b}_P{k}_{i+1}', 'panel_inhabited', 'ENGINEERING_FLEXIBLE',
                                   'removable overhead service panel (ducts, power and data above)', vs, fs, bevel=q['panel_bevel_m']))
                for sx in (x0+seam+ins, x1-seam-ins):
                    for sz in (a+ins, c-ins):
                        vs, fs = pd.box((sx, Y+.003+th+q['fastener_proud_m']/2, sz), (X, down, Zv), (st, q['fastener_proud_m'], st))
                        out.append(pd.element('M7.RA1', 'Fasteners', f'RA1_B{b}_P{k}_{i+1}_F{len(out)}', 'fastener', 'ENGINEERING_FLEXIBLE', 'quarter-turn panel fastener', vs, fs))
    lip, hd = q['housing_lip_m'], sq['housing_depth_m']
    for name, lo, hi_, el in sector_overhead_items(s):
        if 'Aisle_Light' not in name:
            continue
        for side, x in enumerate((lo[0]-lip/2, hi_[0]+lip/2), 1):
            vs, fs = pd.box((x, Y+hd/2, (lo[2]+hi_[2])/2), (X, down, Zv), (lip, hd, hi_[2]-lo[2]+2*lip))
            out.append(pd.element('M7.RA1', 'Housings', f'{name}_Housing_{side}', 'housing', 'ENGINEERING_FLEXIBLE', 'aisle light housing (long sides)', vs, fs, bevel=.002))
        for side, z in enumerate((lo[2]-lip/2, hi_[2]+lip/2), 1):
            vs, fs = pd.box(((lo[0]+hi_[0])/2, Y+hd/2, z), (X, down, Zv), (hi_[0]-lo[0], hd, lip))
            out.append(pd.element('M7.RA1', 'Housings', f'{name}_Cap_{side}', 'housing', 'ENGINEERING_FLEXIBLE', 'aisle light housing (end caps)', vs, fs, bevel=.002))
    return out


def sector_check(s, els):
    import habitat_interior as hi
    import human_entry as he
    sq = pd.params(s, PACK); hx, hz, hr = hi.hatch_opening(s); L = he.landing(s); fails = []
    for q in els:
        ys = [p[1] for p in q['vs']]
        if max(ys) > sq['overhead_floor_y_m']:
            fails.append(f"{q['name']}: reaches {max(ys):.3f} m, below the overhead zone ({sq['overhead_floor_y_m']} m)")
        for p in q['vs']:
            if math.hypot(p[0]-hx, p[2]-hz) < hr-1e-6 or (L['well_x'][0] < p[0] < L['well_x'][1] and L['well_z'][0] < p[2] < L['well_z'][1]):
                fails.append(f"{q['name']}: inside the hatch opening or the landing well's column"); break
    return fails


pd.CHECKS['M7.RA1'] = sector_check
