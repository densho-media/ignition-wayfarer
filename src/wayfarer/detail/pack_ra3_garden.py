"""Detail pack ra3_garden (docs/MODULES.md): RA3.GDN, the S8b Z1 cultural pass of ring A sector 3 (LIFE_SUPPORT_GARDEN_COMMON).

Built in the sector frame (+X axial, +Y radially outward = down in spin, +Z tangential; deck at y 0, the overhead at -2.90 m) into
WF_DETAIL_RA3_GDN.blend, which WF_HABITAT links at the sector instance (1, 3). The whitebox blocks stay as they are; this pack dresses them:
cushions on the mess benches, a fiddle rail round the table, a mug rail and a cubby shelf on the outer wall above the far bench, daylight
panels over the table between the overhead frames, grow-light bars under the Garden rack's lid and trays, and on the ECLSS bay's face (in
its service recess) a labelled WATER / O2 / CO2 resource board, an access panel with quarter-turn fasteners and a maintenance tag.
Owned with data/detail/ra3_garden.toml.
"""
import production_detail as pd

PACK = 'ra3_garden'
ASM = 'RA3.GDN'
FUNCTION = 'LIFE_SUPPORT_GARDEN_COMMON'
X, DOWN, Z = (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)
# Illustrative stock levels on the resource board (share of each gauge filled); the live values are UJ-004's learning-station hook.
GAUGES = (('WATER', 'ra3_water', .78), ('O2', 'ra3_oxygen', .66), ('CO2', 'ra3_co2', .22))


def blocks(s):
    import habitat_interior as hi
    return {b['name']: b for b in hi.zones(s, FUNCTION)}


def wall(s, y):
    """The outer (+Z) wall's face at height y (it leans inward toward the overhead)."""
    import ring_circulation as rc
    return rc.sector_wall_half(s, y)


def slab(name, family, material, cls, fn, lo, hi, bevel=0.0):
    c = tuple((lo[k]+hi[k])/2 for k in range(3)); size = tuple(hi[k]-lo[k] for k in range(3))
    vs, fs = pd.box(c, (X, DOWN, Z), size)
    return pd.element(ASM, family, name, material, cls, fn, vs, fs, bevel=bevel)


@pd.builder(ASM)
def garden_elements(s):
    import sector_whitebox as sw
    q = pd.params(s, PACK); B = blocks(s); out = []; F = 'ENGINEERING_FLEXIBLE'; ART = 'ARTISTIC'
    # Mess: seat and back cushions on both benches, a fiddle rail round the table.
    mess = B['Mess']; parts = {p['part']: p for p in sw.shapes(s, mess)}; i = q['cushion_inset_m']
    for k, side in ((1, 1), (2, -1)):
        seat, back = parts[f'Seat_{k}'], parts[f'Back_{k}']
        z_back = back['max'][2] if side > 0 else back['min'][2]; z_front = seat['max'][2] if side > 0 else seat['min'][2]
        x0, x1 = seat['min'][0]+i, seat['max'][0]-i; top = seat['min'][1]
        out.append(slab(f'RA3_Seat_Cushion_{k}', 'Mess', 'ra3_cushion', ART, 'bench seat cushion', (x0, top-q['cushion_m'], min(z_back, z_front-side*i)),
                        (x1, top, max(z_back, z_front-side*i)), q['bevel_m']*3))
        yb0, yb1 = q['back_cushion_y_m']; zc = z_back+side*q['back_cushion_m']
        out.append(slab(f'RA3_Back_Cushion_{k}', 'Mess', 'ra3_cushion', ART, 'bench back cushion', (x0, yb0, min(z_back, zc)), (x1, yb1, max(z_back, zc)),
                        q['bevel_m']*3))
    t = parts['Table']; r, d = q['rail_r_m'], q['rail_inset_m']; y = t['min'][1]-q['rail_h_m']+r
    xa, xb, za, zb = t['min'][0]+d, t['max'][0]-d, t['min'][2]+d, t['max'][2]-d
    for k, (a, b) in enumerate((((xa, y, za), (xb, y, za)), ((xb, y, za), (xb, y, zb)), ((xb, y, zb), (xa, y, zb)), ((xa, y, zb), (xa, y, za))), 1):
        vs, fs = pd.rod(a, b, r)
        out.append(pd.element(ASM, 'Mess', f'RA3_Table_Rail_{k}', 'ra3_table_rail', F, 'table fiddle rail (spill lip for Coriolis and burn transients)', vs, fs))
    # Outer wall above the far bench: a mug rail with one mug per booth place and a cubby shelf.
    g = q['wall_gap_m']; n = q['crew']; yr = q['mug_rail_y_m']; zr = wall(s, yr)-g-q['mug_r_m']
    x0, x1 = mess['min'][0]+.10, mess['max'][0]-.10
    vs, fs = pd.rod((x0, yr, zr), (x1, yr, zr), q['mug_rail_r_m'])
    out.append(pd.element(ASM, 'Mess', 'RA3_Mug_Rail', 'ra3_table_rail', F, 'mug rail on the outer wall', vs, fs))
    for j in range(n):
        xm = x0+(j+.5)*(x1-x0)/n; ytop = yr+q['mug_rail_r_m']; zm = min(zr, wall(s, ytop)-g-q['mug_r_m'])
        vs, fs = pd.rod((xm, ytop, zm), (xm, ytop+q['mug_h_m'], zm), q['mug_r_m'], 12)
        out.append(pd.element(ASM, 'Mess', f'RA3_Mug_{j+1}', f'ra3_mug_{j+1}', ART, f'crew mug {j+1} (one colour per booth place)', vs, fs))
    (sx0, sx1), yf, h, dp = q['shelf_x_m'], q['shelf_y_m'], q['shelf_h_m'], q['shelf_depth_m']; yt = yf-h; zw = wall(s, yt)-g
    out.append(slab('RA3_Cubby_Floor', 'Mess', 'ra3_shelf', F, 'personal cubby shelf', (sx0, yf-.02, zw-dp), (sx1, yf, zw)))
    out.append(slab('RA3_Cubby_Top', 'Mess', 'ra3_shelf', F, 'personal cubby shelf top', (sx0, yt, zw-dp), (sx1, yt+.02, zw)))
    for j in range(n+1):
        xd = sx0+j*(sx1-sx0)/n; xd = min(max(xd, sx0+.01), sx1-.01)
        out.append(slab(f'RA3_Cubby_Divider_{j}', 'Mess', 'ra3_shelf', F, 'cubby divider', (xd-.01, yt+.02, zw-dp), (xd+.01, yf-.02, zw)))
    for j in range(n):
        xm = sx0+(j+.5)*(sx1-sx0)/n
        out.append(slab(f'RA3_Cubby_Tab_{j+1}', 'Mess', f'ra3_mug_{j+1}', ART, f'cubby tab, booth place {j+1}', (xm-.03, yf-.05, zw-dp-.004), (xm+.03, yf-.02, zw-dp)))
    # Daylight panels over the table, in the overhead frame bays clear of the supply diffuser.
    za, zb = q['daylight_z_m']; yo = -2.87
    for k, (a, b) in enumerate(((mess['min'][0]+.05, -.10), (.10, .55)), 1):
        out.append(slab(f'RA3_Daylight_{k}', 'Lights', 'ra3_daylight', F, 'daylight panel over the table', (a, yo, za), (b, yo+q['daylight_m'], zb), q['bevel_m']))
    # Garden rack: grow-light bars under the lid and under every tray.
    rack = B['Garden_Rack_1']; rp = {p['part']: p for p in sw.shapes(s, rack)}; w, dy = q['light_bar_m']
    ceilings = [('Lid', rp['Lid']['max'][1])]+[(k, p['max'][1]) for k, p in rp.items() if k.startswith('Tray_')]
    lo_x, hi_x = rack['min'][0]+.10, rack['max'][0]-.10
    for name, yc in ceilings:
        for j in range(q['light_bars']):
            zc = rack['min'][2]+(rack['max'][2]-rack['min'][2])*(j+1)/(q['light_bars']+1)
            out.append(slab(f'RA3_Growlight_{name}_{j+1}', 'Lights', 'ra3_growlight', F, 'grow-light bar', (lo_x, yc, zc-w/2), (hi_x, yc+dy, zc+w/2)))
    # ECLSS bay face, in its service recess: resource board, access panel and a maintenance tag.
    fx = q['eclss_face_x_m']+0.06; pt = q['panel_t_m']
    (bz0, bz1), (by0, by1) = q['board_z_m'], q['board_y_m']
    out.append(slab('RA3_Resource_Board', 'ECLSS', 'panel_service', F, 'GU resource board: water, oxygen and CO2 stock', (fx-pt, by0, bz0), (fx, by1, bz1), q['bevel_m']))
    cols = len(GAUGES); pitch = (bz1-bz0)/cols; gy0, gy1 = by0+.10, by1-.04
    for j, (label, mat, share) in enumerate(GAUGES):
        zc = bz1-(j+.5)*pitch                                   # read left to right facing +X: +Z is on the reader's left
        out.append(slab(f'RA3_Gauge_Slot_{label}', 'ECLSS', 'ra3_gauge_slot', F, f'{label} gauge slot', (fx-pt-.004, gy0, zc-.04), (fx-pt, gy1, zc+.04)))
        out.append(slab(f'RA3_Gauge_Fill_{label}', 'ECLSS', mat, F, f'{label} stock level (illustrative)', (fx-pt-.007, gy1-(gy1-gy0)*share, zc-.03), (fx-pt-.004, gy1, zc+.03)))
        out.append(pd.lettering(ASM, 'ECLSS', f'RA3_Gauge_Label_{label}', 'xf_mark', f'{label} label', label, (fx-pt-.002, by0+.05, zc), (0.0, 0.0, -1.0),
                                (0.0, -1.0, 0.0), .035))
    out.append(pd.lettering(ASM, 'ECLSS', 'RA3_Board_Title', 'xf_mark', 'board title', 'LIFE SUPPORT', (fx-pt-.002, by0-.0, (bz0+bz1)/2), (0.0, 0.0, -1.0),
                            (0.0, -1.0, 0.0), .03))
    (az0, az1), (ay0, ay1) = q['access_z_m'], q['access_y_m']
    out.append(slab('RA3_Access_Panel', 'ECLSS', 'service_ochre', F, 'ECLSS access panel (removable)', (fx-pt, ay0, az0), (fx, ay1, az1), q['bevel_m']))
    for k, (yy, zz) in enumerate(((ay0+.05, az0+.05), (ay0+.05, az1-.05), (ay1-.05, az0+.05), (ay1-.05, az1-.05)), 1):
        vs, fs = pd.rod((fx-pt, yy, zz), (fx-pt-.006, yy, zz), .012)
        out.append(pd.element(ASM, 'ECLSS', f'RA3_Access_Fastener_{k}', 'fastener', F, 'quarter-turn fastener', vs, fs))
    out.append(slab('RA3_Maint_Tag', 'ECLSS', 'safety_orange', ART, 'Bolt-Sworn maintenance tag (last service card)', (fx-pt-.004, ay0+.12, az0+.12),
                    (fx-pt, ay0+.24, az0+.20)))
    return out


def garden_check(s, els):
    """Every element inside the envelope's blocks or wall strip: off the clear volumes (aisle, access strips, through-passage, landing well)
    unless it is in the overhead band, off the outer wall, and not inside any whitebox part or fit-out item."""
    import route_fitout as rf
    import sector_whitebox as sw
    q = pd.params(s, PACK); fails = []
    clear = [(c['name'], c['min'], c['max']) for c in sw.clear_volumes(s, FUNCTION)]
    solid = [(p['name'], list(p['min']), list(p['max'])) for b in blocks(s).values() for p in sw.shapes(s, b)]
    rec = rf.service_recess(s, FUNCTION)
    if rec:                                   # the service block is drawn only behind its recessed face
        name, k, plane, out_max = rec
        for n, a, b in solid:
            if n == name:
                (b if out_max else a)[k] = plane
    for e in rf.sector_elements(s, FUNCTION)+rf.garden_elements(s, FUNCTION):
        pts = [e['min'], e['max']] if 'min' in e else pd.fixture_points(e)
        if pts:
            solid.append((e['name'], [min(p[k] for p in pts) for k in range(3)], [max(p[k] for p in pts) for k in range(3)]))
    over = lambda lo, hi, a, b, tol: all(lo[k] < b[k]-tol and hi[k] > a[k]+tol for k in range(3))
    for e in els:
        if 'text' in e:
            continue
        lo = [min(p[k] for p in e['vs']) for k in range(3)]; hi = [max(p[k] for p in e['vs']) for k in range(3)]
        if hi[1] > q['band_y_m']+1e-9 or lo[1] < q['overhead_y_m']-1e-9:
            hit = [n for n, a, b in clear if over(lo, hi, a, b, 1e-6)]
            if hit:
                fails.append(f"{e['name']}: in clear volume {hit[:2]}")
        if any(p[2] > wall(s, p[1])-1e-4 for p in e['vs']):
            fails.append(f"{e['name']}: through the outer wall")
        hit = [n for n, a, b in solid if over(lo, hi, a, b, 2e-3)]
        if hit:
            fails.append(f"{e['name']}: inside {hit[:2]}")
    return fails


pd.CHECKS[ASM] = garden_check
