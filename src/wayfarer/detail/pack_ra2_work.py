"""Detail pack ra2_work (docs/MODULES.md): RA2.WRK, the S8b Z2 cultural pass of ring A sector 2 (WORK_MEDICAL_OPS).

Built in the sector frame (+X axial, +Y radially outward = down in spin, +Z tangential; deck at y 0) into WF_DETAIL_RA2_WRK.blend, which
WF_HABITAT links at the sector instance (1, 2). The whitebox blocks stay as they are; this pack dresses them below the overhead band (the
trays of ra2_equip keep the band): one ops screen per chair on the display wall with its station number and a keyboard on the desk;
restraint straps over the medical mattress; a drawer-front pattern, the red-cross mark and a MEDICAL label on the medical stowage; and on
both tool walls a shadow board of outlined tool silhouettes with each tool held in front of its outline by a tether; on the workbench a
contained fabrication cell with its filter box (S05). Owned with
data/detail/ra2_work.toml.
"""
import production_detail as pd

PACK = 'ra2_work'
ASM = 'RA2.WRK'
FUNCTION = 'WORK_MEDICAL_OPS'
X, DOWN, Z = (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)


def parts(s):
    import habitat_interior as hi
    import sector_whitebox as sw
    return {f"{b['name']}.{p['part']}" if p['part'] else b['name']: p for b in hi.zones(s, FUNCTION) for p in sw.shapes(s, b)}


def slab(name, family, material, cls, fn, lo, hi, bevel=0.0):
    c = tuple((lo[k]+hi[k])/2 for k in range(3)); size = tuple(hi[k]-lo[k] for k in range(3))
    vs, fs = pd.box(c, (X, DOWN, Z), size)
    return pd.element(ASM, family, name, material, cls, fn, vs, fs, bevel=bevel)


@pd.builder(ASM)
def work_elements(s):
    q = pd.params(s, PACK); P = parts(s); out = []; F = 'ENGINEERING_FLEXIBLE'; ART = 'ARTISTIC'; d = q['decal_m']
    # Ops: one family (one exported node) per station, so each can carry its own learning point (learning_stations.py).
    # A screen per chair on the display wall (its face toward the chairs at -Z), a keyboard on the desk.
    disp = P['Ops_Stations.Display']; zf = disp['min'][2]; desk = P['Ops_Stations.Desk']; sw_, sh = q['screen_m']; yc = q['screen_y_m']
    for k in (1, 2, 3):
        ch = P[f'Ops_Stations.Chair_{k}']; xc = (ch['min'][0]+ch['max'][0])/2
        out.append(slab(f'RA2_Ops_Screen_Rim_{k}', f'Ops_{k}', 'ra2_screen_rim', F, f'ops screen {k} bezel', (xc-sw_/2-.02, yc-sh/2-.02, zf-d), (xc+sw_/2+.02, yc+sh/2+.02, zf)))
        out.append(slab(f'RA2_Ops_Screen_{k}', f'Ops_{k}', 'ra2_screen', F, f'ops screen {k}', (xc-sw_/2, yc-sh/2, zf-2*d*.66), (xc+sw_/2, yc+sh/2, zf-d)))
        out.append(pd.lettering(ASM, f'Ops_{k}', f'RA2_Ops_Number_{k}', 'xf_mark', f'ops station {k} number', f'OPS {k}', (xc, yc+sh/2+.06, zf-d), X, (0.0, -1.0, 0.0), q['label_h_m']))
        kw, kh, kd = q['keyboard_m']; top = desk['min'][1]
        out.append(slab(f'RA2_Keyboard_{k}', f'Ops_{k}', 'ra2_keyboard', F, f'ops keyboard {k}', (xc-kw/2, top-kh, q['keyboard_z_m']-kd/2), (xc+kw/2, top, q['keyboard_z_m']+kd/2), .002))
    # Medical couch: restraint straps over the mattress.
    mat = P['Medical_Couch.Mattress']; top = mat['min'][1]
    for k, xs in enumerate(q['strap_x_m'], 1):
        x = mat['min'][0]+xs
        out.append(slab(f'RA2_Med_Strap_{k}', 'Medical', 'ra2_strap', F, 'patient restraint strap', (x-q['strap_w_m']/2, top-q['strap_t_m'], mat['min'][2]), (x+q['strap_w_m']/2, top, mat['max'][2])))
    # Medical stowage front (its face toward the aisle at -Z): drawer lines, the red-cross mark and the label.
    st = P['Medical_Stowage']; zf = st['min'][2]; (x0, y0, _), (x1, y1, _) = st['min'], st['max']; g = q['drawer_gap_m']
    nr, nc = q['drawer_rows'], q['drawer_cols']
    for i in range(1, nr):
        y = y0+(y1-y0)*i/nr
        out.append(slab(f'RA2_Drawer_Row_{i}', 'Medical', 'ra2_drawer_line', F, 'drawer joint', (x0+.02, y-g/2, zf-d), (x1-.02, y+g/2, zf)))
    for j in range(1, nc):
        x = x0+(x1-x0)*j/nc
        out.append(slab(f'RA2_Drawer_Col_{j}', 'Medical', 'ra2_drawer_line', F, 'drawer joint', (x-g/2, y0+.02, zf-d), (x+g/2, y1-.02, zf)))
    L, W = q['cross_m']; xc, ycr = x0+(x1-x0)/(2*nc), (y0+y1)/2
    out.append(slab('RA2_Cross_Field', 'Medical', 'ra2_cross_field', ART, 'medical mark field', (xc-L/2-.03, ycr-L/2-.03, zf-d), (xc+L/2+.03, ycr+L/2+.03, zf)))
    out.append(slab('RA2_Cross_H', 'Medical', 'ra2_cross', ART, 'red cross (medical stowage)', (xc-L/2, ycr-W/2, zf-2*d*.66), (xc+L/2, ycr+W/2, zf-d)))
    out.append(slab('RA2_Cross_V', 'Medical', 'ra2_cross', ART, 'red cross (medical stowage)', (xc-W/2, ycr-L/2, zf-2*d*.66), (xc+W/2, ycr-W/2, zf-d)))
    out.append(slab('RA2_Cross_V2', 'Medical', 'ra2_cross', ART, 'red cross (medical stowage)', (xc-W/2, ycr+W/2, zf-2*d*.66), (xc+W/2, ycr+L/2, zf-d)))
    out.append(pd.lettering(ASM, 'Medical', 'RA2_Medical_Label', 'xf_mark', 'stowage label', 'MEDICAL', ((x0+x1)/2+.25, y1-.08, zf-d), X, (0.0, -1.0, 0.0), q['label_h_m']))
    # Tool walls (Lab_Bench, Workbench): the wall face toward the bench at +Z; a shadow board per tool and the tool on a tether.
    for bench in ('Lab_Bench', 'Workbench'):
        wall = P[f'{bench}.Tool_Wall']; zw = wall['max'][2]; shelf = P[f'{bench}.Shelf']
        xs0, xs1 = wall['min'][0]+.08, wall['max'][0]-.08; n = len(q['tools']); y = q['tool_y_m']
        for j, (tool, w, h) in enumerate(q['tools']):
            xc = xs0+(xs1-xs0)*(j+.5)/n; lo_y, hi_y = y-h/2, y+h/2
            if hi_y > shelf['min'][1]-.01 and lo_y < shelf['max'][1]+.01:
                lo_y, hi_y = shelf['max'][1]+.02, shelf['max'][1]+.02+h
            out.append(slab(f'RA2_{bench}_Shadow_{tool}', f'Tools_{bench}', 'ra2_shadow', ART, f'{tool} shadow outline', (xc-w/2-.01, lo_y-.01, zw), (xc+w/2+.01, hi_y+.01, zw+d)))
            td = q['tool_d_m']
            out.append(slab(f'RA2_{bench}_Tool_{tool}', f'Tools_{bench}', 'ra2_tool', F, f'{tool} (held on its outline)', (xc-w/2, lo_y, zw+td), (xc+w/2, hi_y, zw+td+min(w, .03)), .003))
            a, b = (xc, lo_y-.005, zw+d), (xc, lo_y-.005, zw+td+.01)
            out.append(pd.element(ASM, f'Tools_{bench}', f'RA2_{bench}_Tether_{tool}', 'ra2_tether', F, 'tool tether', *pd.rod(a, b, q['tether_r_m'], 6)))
        out.append(slab(f'RA2_{bench}_Maint_Tag', f'Tools_{bench}', 'safety_orange', ART, 'Bolt-Sworn maintenance tag (last calibration card)', (xs1-.10, -1.95, zw), (xs1-.02, -1.84, zw+d)))
    # S05 workshop and fabrication (2026-10-31): a contained fabrication cell on the workbench (sealed cabinet, window and glove ports facing
    # the aisle) recirculating through a HEPA / carbon filter box beside it; spares are made here, never an open process in the cabin.
    top = P['Workbench.Top']; yb = top['min'][1]; (x0, x1), (z0, z1), h = q['fab_x_m'], q['fab_z_m'], q['fab_h_m']; wt = q['fab_wall_m']
    out.append(slab('RA2_Fab_Cell', 'Fab', 'ra2_fab_body', F, 'contained fabrication cell (sealed cabinet: printer / mill, PROTOTYPE)', (x0, yb-h, z0), (x1, yb, z1), .01))
    out.append(slab('RA2_Fab_Window', 'Fab', 'ra2_fab_window', F, 'cell window', (x0+.06, yb-h+.05, z1), (x1-.06, yb-h*.45, z1+d)))
    for k, xg in enumerate((x0+(x1-x0)*.3, x0+(x1-x0)*.7)):
        a, b = (xg, yb-h*.25, z1), (xg, yb-h*.25, z1+.02)
        out.append(pd.element(ASM, 'Fab', f'RA2_Fab_Glove_Port_{k+1}', 'ra2_fab_glove', F, 'glove port', *pd.rod(a, b, q['fab_glove_r_m'], 16)))
    (f0, f1), fh = q['filter_x_m'], q['filter_h_m']
    out.append(slab('RA2_Fab_Filter', 'Fab', 'ra2_fab_body', F, 'HEPA / carbon filter box: the cell recirculates through it', (f0, yb-fh, z0+.05), (f1, yb, z1-.05), .01))
    out.append(slab('RA2_Fab_Filter_Band', 'Fab', 'service_ochre', F, 'filter cartridge access cover', (f0+.03, yb-fh+.04, z1-.05), (f1-.03, yb-.04, z1-.05+d)))
    duct_y = yb-h*.6
    out.append(pd.element(ASM, 'Fab', 'RA2_Fab_Duct', 'ra2_fab_glove', F, 'cell to filter duct', *pd.rod((x0, duct_y, (z0+z1)/2), (f1, duct_y, (z0+z1)/2), wt, 12)))
    out.append(pd.lettering(ASM, 'Fab', 'RA2_Fab_Label', 'xf_mark', 'cell label', 'FAB CELL - CONTAINED', ((x0+x1)/2, yb-h+.025, z1+d), X, (0.0, -1.0, 0.0), q['label_h_m']*.8))
    out.append(pd.lettering(ASM, 'Fab', 'RA2_Fab_Filter_Label', 'xf_mark', 'filter label', 'HEPA / C', ((f0+f1)/2, yb-fh+.02, z1-.05+d), X, (0.0, -1.0, 0.0), q['label_h_m']*.7))
    return out


def work_check(s, els):
    """Every element off the aisle, access strips, through-passage and landing well (decals may stand decal_m proud of a face into them)
    and not inside a whitebox part."""
    import sector_whitebox as sw
    q = pd.params(s, PACK); fails = []; P = parts(s); V = {c['name']: c for c in sw.clear_volumes(s, FUNCTION)}
    over = lambda lo, hi, a, b, tol: all(lo[k] < b[k]-tol and hi[k] > a[k]+tol for k in range(3))
    for e in els:
        if 'text' in e:
            continue
        lo = [min(p[k] for p in e['vs']) for k in range(3)]; hi = [max(p[k] for p in e['vs']) for k in range(3)]
        thin = min(hi[k]-lo[k] for k in range(3)) <= q['decal_m']*1.4+1e-6
        hit = [n for n, v in V.items() if over(lo, hi, v['min'], v['max'], (q['decal_m']*1.4 if thin else 0)+1e-6)]
        if hit:
            fails.append(f"{e['name']}: in clear volume {hit[:2]}")
        hit = [n for n, p in P.items() if over(lo, hi, p['min'], p['max'], 2e-3)]
        if hit:
            fails.append(f"{e['name']}: inside {hit[:2]}")
    return fails


pd.CHECKS[ASM] = work_check
