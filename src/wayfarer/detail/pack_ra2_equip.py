"""Detail pack ra2_equip (docs/MODULES.md): RA2.EQP, overhead cable trays and junction boxes of ring A sector 2 (WORK_MEDICAL_OPS).

Built in the sector frame (+X axial, +Y radially outward = down in spin, +Z tangential; deck at y 0, the overhead at -2.90 m) into
WF_DETAIL_RA2_EQP.blend, which WF_HABITAT links at the sector instance (1, 2). In each bay of the route fit-out's overhead frame grid a
transverse tray runs along +Z at the bay centre, broken round every item that reaches the overhead (route_fitout and human_entry fixtures of
the sector and its landing), the hatch opening and the landing well's column, each widened by margin_m; a junction box closes each run.
Everything stays in the overhead band. Owned with data/detail/ra2_equip.toml.
"""
import math
import production_detail as pd

PACK = 'ra2_equip'
ASM = 'RA2.EQP'
FUNCTION = 'WORK_MEDICAL_OPS'
X, DOWN, Z = (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)


def overhead_items(s):
    """(name, min, max) of the sector's fit-out and landing items that reach the overhead zone."""
    import human_entry as he
    import route_fitout as rf
    q = pd.params(s, PACK)
    els = rf.sector_elements(s, FUNCTION)+rf.sector_sign(s, FUNCTION)+rf.seraph_elements(s, FUNCTION)[0]+rf.landing_elements(s)+he.landing_fixtures(s)
    out = []
    for e in els:
        pts = [e['min'], e['max']] if e['shape'] in ('box', 'wbox') and 'min' in e else pd.fixture_points(e)
        if pts and min(p[1] for p in pts) < q['item_floor_y_m']:
            lo = [min(p[k] for p in pts) for k in range(3)]; hi = [max(p[k] for p in pts) for k in range(3)]
            if e['shape'] == 'tube':
                r = e.get('r1', .9); c = e['a']; lo, hi = [c[0]-r, lo[1], c[2]-r], [c[0]+r, hi[1], c[2]+r]
            out.append((e['name'], lo, hi))
    return out


def bays(s):
    """x intervals between the overhead frames (the fit-out's frame grid)."""
    xs = sorted({(round(lo[0], 4), round(hi[0], 4)) for name, lo, hi in overhead_items(s) if '_Frame_' in name})
    edges = [x for c in xs for x in c]
    return [(edges[2*i+1], edges[2*i+2]) for i in range(len(edges)//2-1) if edges[2*i+2]-edges[2*i+1] > .2]


def keepouts(s, x0, x1):
    """z intervals a run between x0 and x1 must leave: overhead items deep enough to meet it, the hatch opening and the landing well."""
    import habitat_interior as hi
    import human_entry as he
    q = pd.params(s, PACK); m = q['margin_m']; low = q['overhead_y_m']+max(q['tray_depth_m'], q['box_depth_m']); out = []
    for name, lo, hi_ in overhead_items(s):
        if lo[1] > low+.02:
            continue                          # hangs at least 2 cm clear below the trays and boxes
        if lo[0]-m < x1 and x0 < hi_[0]+m:
            out.append((lo[2]-m, hi_[2]+m))
    hx, hz, hr = hi.hatch_opening(s); hr += q['hatch_margin_m']
    dx = 0.0 if x0 <= hx <= x1 else min(abs(x0-hx), abs(x1-hx))
    if dx < hr:
        half = math.sqrt(hr*hr-dx*dx); out.append((hz-half, hz+half))
    L = he.landing(s)
    if L['well_x'][0]-m < x1 and x0 < L['well_x'][1]+m:
        out.append((L['well_z'][0]-m, L['well_z'][1]+m))
    return out


@pd.builder(ASM)
def equipment_elements(s):
    q = pd.params(s, PACK); Y = q['overhead_y_m']; w, d, lip = q['tray_width_m'], q['tray_depth_m'], q['tray_lip_m']; out = []
    for b, (bx0, bx1) in enumerate(bays(s), 1):
        xc = (bx0+bx1)/2; x0, x1 = xc-w/2, xc+w/2
        runs = [r for r in pd.windows_free(keepouts(s, x0, x1), -q['span_z_m'], q['span_z_m'], 0.0) if r[1]-r[0] >= q['min_run_m']]
        for k, (z0, z1) in enumerate(runs, 1):
            zc, L = (z0+z1)/2, z1-z0
            vs, fs = pd.box((xc, Y+d/4, zc), (X, DOWN, Z), (w, d/2, L))
            out.append(pd.element(ASM, 'Trays', f'RA2_B{b}_R{k}_Tray', 'ra2_tray', 'ENGINEERING_FLEXIBLE', 'overhead cable tray (base)', vs, fs, bevel=q['bevel_m']))
            for side, x in enumerate((x0+lip/2, x1-lip/2), 1):
                vs, fs = pd.box((x, Y+d/2, zc), (X, DOWN, Z), (lip, d, L))
                out.append(pd.element(ASM, 'Trays', f'RA2_B{b}_R{k}_Lip_{side}', 'ra2_tray', 'ENGINEERING_FLEXIBLE', 'overhead cable tray (side lip)', vs, fs))
            for end, z in enumerate((z0+q['box_inset_m'], z1-q['box_inset_m']), 1):
                vs, fs = pd.box((xc, Y+q['box_depth_m']/2, z), (X, DOWN, Z), (q['box_size_m'], q['box_depth_m'], q['box_size_m']))
                out.append(pd.element(ASM, 'Boxes', f'RA2_B{b}_R{k}_Box_{end}', 'ra2_box', 'ENGINEERING_FLEXIBLE', 'junction box (removable cover)', vs, fs, bevel=q['bevel_m']))
    return out


def equipment_check(s, els):
    """Every element in the overhead band, off the hatch opening and the landing well's column, and off every overhead item it could meet."""
    import habitat_interior as hi
    import human_entry as he
    q = pd.params(s, PACK); hx, hz, hr = hi.hatch_opening(s); L = he.landing(s); fails = []
    low = q['overhead_y_m']+max(q['tray_depth_m'], q['box_depth_m'])
    items = [(n, lo, h) for n, lo, h in overhead_items(s) if lo[1] <= low+.02]
    for e in els:
        lo = [min(p[k] for p in e['vs']) for k in range(3)]; hi_ = [max(p[k] for p in e['vs']) for k in range(3)]
        if hi_[1] > -2.85+1e-9 or lo[1] < q['overhead_y_m']-1e-9:
            fails.append(f"{e['name']}: leaves the overhead band"); continue
        if any(math.hypot(p[0]-hx, p[2]-hz) < hr-1e-6 for p in e['vs']) or (lo[0] < L['well_x'][1] and hi_[0] > L['well_x'][0] and lo[2] < L['well_z'][1] and hi_[2] > L['well_z'][0]):
            fails.append(f"{e['name']}: over the hatch opening or the landing well"); continue
        hit = [n for n, a, b in items if lo[0] < b[0]-1e-9 and hi_[0] > a[0]+1e-9 and lo[2] < b[2]-1e-9 and hi_[2] > a[2]+1e-9]
        if hit:
            fails.append(f"{e['name']}: meets {hit[:2]}")
    return fails


pd.CHECKS[ASM] = equipment_check
