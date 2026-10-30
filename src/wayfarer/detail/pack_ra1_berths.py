"""Detail pack ra1_berths (docs/MODULES.md): RA1.BRT, the S8b Z3 cultural pass of ring A sector 1 (HABITATION).

Built in the sector frame (+X axial, +Y radially outward = down in spin, +Z tangential; deck at y 0) into WF_DETAIL_RA1_BRT.blend, which
WF_HABITAT links at the sector instance (1, 1). The whitebox berths stay as they are; this pack dresses them: a mattress, a pillow at the
head (fore) end and a sleep-restraint strap on every platform, a privacy curtain on a rail across every berth mouth (the aisle side for
berths 1-3, the aft end above the footboard for berths 4-6) drawn back to the foot, a photo card on the berth's outer wall, a stencilled
berth number and a crew-colour name tab on each platform edge, and the hygiene cubicle's door skin with its label. Owned with
data/detail/ra1_berths.toml.
"""
import production_detail as pd

PACK = 'ra1_berths'
ASM = 'RA1.BRT'
FUNCTION = 'HABITATION'
X, DOWN, Z = (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)
BUNKS = 6


def parts(s):
    import habitat_interior as hi
    import sector_whitebox as sw
    return {f"{b['name']}.{p['part']}" if p['part'] else b['name']: p for b in hi.zones(s, FUNCTION) for p in sw.shapes(s, b)}


def spaces(s):
    import sector_whitebox as sw
    return {c['name']: c for c in sw.clear_volumes(s, FUNCTION)}


def slab(name, family, material, cls, fn, lo, hi, bevel=0.0):
    c = tuple((lo[k]+hi[k])/2 for k in range(3)); size = tuple(hi[k]-lo[k] for k in range(3))
    vs, fs = pd.box(c, (X, DOWN, Z), size)
    return pd.element(ASM, family, name, material, cls, fn, vs, fs, bevel=bevel)


@pd.builder(ASM)
def berth_elements(s):
    q = pd.params(s, PACK); P = parts(s); V = spaces(s); out = []; F = 'ENGINEERING_FLEXIBLE'; ART = 'ARTISTIC'
    d = q['decal_m']
    for k in range(1, BUNKS+1):
        sp = V[f'Bunk_{k}_Space']; (x0, y0, z0), (x1, y1, z1) = sp['min'], sp['max']; place = f'ra1_place_{k}'; fam = f'Berth_{k}'
        top = P[f'Bunk_{k}.Platform']['min'][1]; m = q['mattress_inset_m']; mt = q['mattress_m']
        out.append(slab(f'RA1_Mattress_{k}', fam, 'ra1_mattress', ART, 'berth mattress', (x0+m, top-mt, z0+m), (x1-m, top, z1-m), .01))
        pl, ph, pw = q['pillow_m']; zc = (z0+z1)/2
        out.append(slab(f'RA1_Pillow_{k}', fam, place, ART, 'pillow in the crew place colour', (x1-m-pl, top-mt-ph, zc-pw/2), (x1-m-.02, top-mt, zc+pw/2), .015))
        xs = x1-m-q['strap_x_m']; sw_, st = q['strap_w_m'], q['strap_t_m']
        out.append(slab(f'RA1_Sleep_Strap_{k}', fam, 'ra1_strap', F, 'sleep-restraint strap (burn and spin transients)', (xs-sw_/2, top-mt-st, z0+m), (xs+sw_/2, top-mt, z1-m)))
        lid = P[f'Bunk_{k}.Lid']['max'][1]; yr = lid+q['rail_drop_m']; ct, r = q['curtain_t_m'], q['rail_r_m']
        foot = P.get(f'Bunk_{k}.Footboard')
        if foot is None:                         # berths 1-3: the mouth faces the aisle (-Z), between the end panels
            zm = (P[f'Bunk_{k}.Lid']['min'][2]+z0)/2
            a, b = (x0, yr, zm), (x1, yr, zm)
            out.append(pd.element(ASM, fam, f'RA1_Curtain_Rail_{k}', 'ra1_rail', F, 'curtain rail across the berth mouth', *pd.rod(a, b, r)))
            out.append(slab(f'RA1_Curtain_{k}', fam, place, ART, 'privacy curtain, drawn to the foot', (x0, yr+r, zm-ct/2), (x0+(x1-x0)*q['curtain_open'], top-.01, zm+ct/2)))
            plat = P[f'Bunk_{k}.Platform']; tw, th = q['tab_m']; ze = plat['min'][2]
            out.append(slab(f'RA1_Name_Tab_{k}', fam, place, ART, 'name tab in the crew place colour', (x1-.05-tw, plat['min'][1]+.025, ze-d), (x1-.05, plat['min'][1]+.025+th, ze)))
            out.append(pd.lettering(ASM, fam, f'RA1_Berth_Number_{k}', 'xf_mark', 'berth number', f'A1-{k}', (x0+.20, (plat['min'][1]+plat['max'][1])/2, ze-d),
                                    X, (0.0, -1.0, 0.0), q['number_h_m']))
        else:                                    # berths 4-6: the mouth is the aft end above the footboard
            xm = (foot['min'][0]+x0)/2; zo = P[f'Bunk_{k}.Panel_Outer']['min'][2]
            a, b = (xm, yr, z0), (xm, yr, zo)
            out.append(pd.element(ASM, fam, f'RA1_Curtain_Rail_{k}', 'ra1_rail', F, 'curtain rail across the berth mouth', *pd.rod(a, b, r)))
            out.append(slab(f'RA1_Curtain_{k}', fam, place, ART, 'privacy curtain, drawn to the outer wall', (xm-ct/2, yr+r, zo-(zo-z0)*q['curtain_open']), (xm+ct/2, foot['min'][1]-.01, zo)))
            tw, th = q['tab_m']; xf = foot['min'][0]
            out.append(slab(f'RA1_Name_Tab_{k}', fam, place, ART, 'name tab in the crew place colour', (xf-d, foot['min'][1]+.03, zo-.06-tw), (xf, foot['min'][1]+.03+th, zo-.06)))
            out.append(pd.lettering(ASM, fam, f'RA1_Berth_Number_{k}', 'xf_mark', 'berth number', f'A1-{k}', (xf-d, (foot['min'][1]+foot['max'][1])/2+.03, z0+.25),
                                    (0.0, 0.0, -1.0), (0.0, -1.0, 0.0), q['number_h_m']))
        pw_, ph_ = q['photo_m']; zw = z1; yc = (y0+y1)/2
        out.append(slab(f'RA1_Photo_{k}', fam, 'ra1_photo', ART, 'photo card on the berth wall', (x1-.45-pw_, yc-ph_/2, zw-d), (x1-.45, yc+ph_/2, zw)))
    # Hygiene cubicle: a door skin on its aisle face with a recessed pull and its label.
    h = P['Hygiene']; zf = h['max'][2]; i = q['door_inset_m']; x0, x1 = h['min'][0]+i, h['max'][0]-i
    out.append(slab('RA1_Hygiene_Door', 'Hygiene', 'ra1_door', F, 'hygiene cubicle door skin', (x0, h['min'][1]+i, zf), (x1, -.02, zf+d), .001))
    out.append(slab('RA1_Hygiene_Pull', 'Hygiene', 'ra1_rail', F, 'recessed door pull', (x0+.04, -1.15, zf+d), (x0+.06, -.95, zf+2*d*.66)))
    out.append(pd.lettering(ASM, 'Hygiene', 'RA1_Hygiene_Label', 'xf_mark', 'cubicle label', 'HYGIENE', ((x0+x1)/2, -1.75, zf+2*d), (-1.0, 0.0, 0.0),
                            (0.0, -1.0, 0.0), q['door_label_h_m']))
    return out


def berth_check(s, els):
    """Every element off the aisle, access strips, through-passage and landing well (decals may stand decal_m proud of a face into them),
    not inside a whitebox part, and inside a berth's own volume only within space_margin_m of its walls or platform."""
    q = pd.params(s, PACK); fails = []; P = parts(s); V = spaces(s)
    over = lambda lo, hi, a, b, tol: all(lo[k] < b[k]-tol and hi[k] > a[k]+tol for k in range(3))
    for e in els:
        if 'text' in e:
            continue
        lo = [min(p[k] for p in e['vs']) for k in range(3)]; hi = [max(p[k] for p in e['vs']) for k in range(3)]
        thin = min(hi[k]-lo[k] for k in range(3)) <= q['decal_m']*1.4+1e-6
        for n, v in V.items():
            if not over(lo, hi, v['min'], v['max'], (q['decal_m']*1.4 if thin else 0)+1e-6):
                continue
            if n.startswith('Bunk_') and n.endswith('_Space') and e['family'] == f"Berth_{n.split('_')[1]}":
                # inside its own berth: must hug a boundary (platform below, walls) within the margin
                gap = min(min(hi[k]-v['min'][k], v['max'][k]-lo[k]) for k in range(3))
                if gap > q['space_margin_m']+1e-9:
                    fails.append(f"{e['name']}: {gap:.3f} m into {n}")
                continue
            fails.append(f"{e['name']}: in clear volume {n}")
        hit = [n for n, p in P.items() if over(lo, hi, p['min'], p['max'], 2e-3)]
        if hit:
            fails.append(f"{e['name']}: inside {hit[:2]}")
    return fails


pd.CHECKS[ASM] = berth_check
