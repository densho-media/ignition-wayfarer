"""Fractal shielding: the hexagonal facing-plate tiling with Sierpinski-subdivided triangles on the Brow's ram faces. Pure reference.

`[production.exterior.fractal_shield]` holds the PROTOTYPE parameters (plate size, fractal depth, density, grooves, relief, gaps,
fasteners, closeouts, LOD). The pattern is shading and a height field for procedural normals, never geometry: the skin, the disruptor
layer, their thickness, openings and clearances are unchanged, and nothing here is a shielding, mass or stack claim (forward_shield.stack
stays OPEN). The runtime and web viewer run the same formulas in GLSL (godot/shaders/fractal_shield.gdshaderinc); `sample` is the
reference they follow, `uniforms` the values they receive and `screen` the fit checks.

Pattern, in the plane across the ship axis (Blender Y, Z; the faces are within 5 degrees of it, so the axial projection is kept):
  - flat-top regular hexagons of side a (= circumradius), one centred on the axis; a dark plate gap on every edge;
  - each plate is six equilateral triangles round its centre (the level-0 spokes); every triangle is subdivided Sierpinski-fashion
    to fractal_depth levels: its three edge midpoints cut it into four, the centre triangle becomes a shallow recessed face (inset_m,
    never an opening) and the three corner triangles subdivide again, each with the stable-hash chance `density`;
  - a tri-clamp fastener at every other plate corner (the hexagonal lattice's A vertices): each clamp holds three plates and each plate
    hangs on three clamps, so every plate is replaceable alone (forward_defense.regenerative escalation: panel replacement);
  - a plain closeout collar of closeout_m round every opening: the EYE wells and their layer ports, the Lance root, the Crown skin
    windows and layer ports, and the rim. A hexagonal EYE shell (forward_defense.eye_shell) is itself one plate of the tiling: its keep-out
    is the shell's hexagon plus the plate gap.
Level k's triangles have side a / 2^k and grooves groove_m * groove_ratio^k wide; a level draws once its triangles span lod_px pixels.
"""
import math
from pathlib import Path
import struct
import sys
import zlib

import forward_shield

SQRT3 = math.sqrt(3.0)
MAX_DEPTH = 6               # the shader's unrolled loop bound


def params(s):
    """The pattern parameters with the ram face's per-plate value jitter and repairs."""
    X = s['production']['exterior']
    return dict(X['fractal_shield'], jitter=X['ram_face']['jitter'], repair_share=X['ram_face']['repair_share'],
                repair_value=X['ram_face']['repair_value'], ram_materials=list(X['ram_face']['ram_materials']),
                x_min_m=X['ram_face']['x_min_m'], normal_x_min=X['ram_face']['normal_x_min'])


def interfaces(s):
    """Keep-outs of the pattern, derived from the forward geometry: every opening in the skin or the layer plus closeout_m. The EYE wells sit
    in the four quadrants at one radius (eye.facet_map), so one offset q and one radius describe them; the Crown bays are a regular ring."""
    p = params(s); c = p['closeout_m']; layer = forward_shield.disruptor_layers(s)[0]
    wells = forward_shield.wells(s); ports = forward_shield.eye_ports(s, layer)
    q = abs(wells[0]['y'])
    if any(abs(abs(w['y'])-q) > 1e-9 or abs(abs(w['z'])-q) > 1e-9 for w in wells):
        raise ValueError('fractal_shield: the EYE wells are not one quadrant-symmetric set; the shader keep-out assumes it')
    shell = forward_shield.eye_shell(s)
    if shell:          # hexagonal EYE shells (forward_defense.eye_shell): each Eye is one plate, set off from the tiling by the plate gap only
        well_hex, well_r = 1.0, shell['apothem']+p['plate_gap_m']
    else:
        well_hex, well_r = 0.0, max(max(w['radius'] for w in wells), max(o['radius'] for o in ports))+c
    lance_r = max(forward_shield.lance_radius_at(s, forward_shield.stations(s)['face'])+forward_shield.clearance(s),
                  forward_shield.lance_hole_radius(s, layer))+c
    openings = forward_shield.crown_skin_windows(s)+forward_shield.crown_ports(s)
    r0 = min(o['r0'] for o in openings); r1 = max(o['r1'] for o in openings)
    hw = max(o['half_angle'] for o in openings)*r1            # the windows are angular sectors: widest at their outer radius
    n = len(forward_shield.crown_skin_windows(s))
    phase = forward_shield.crown_skin_windows(s)[0]['azimuth']
    return dict(well_q=q, well_r=well_r, well_hex=well_hex, lance_r=lance_r, crown_n=n, crown_phase=phase, crown_rm=(r0+r1)/2, crown_hr=(r1-r0)/2+c,
                crown_hw=hw+c, rim_r=forward_shield.shield_radius(s)-p['rim_closeout_m'])


def uniforms(s):
    """Shader uniforms (godot/shaders/fractal_shield.gdshaderinc names): the pattern parameters and the keep-outs, plain numbers."""
    p = params(s)
    out = dict(fs_side=p['plate_side_m'], fs_gap=p['plate_gap_m'], fs_depth=int(p['fractal_depth']), fs_density=p['density'],
               fs_groove=p['groove_m'], fs_ratio=p['groove_ratio'], fs_relief=p['relief_m'], fs_inset=p['inset_m'],
               fs_fastener=p['fastener_radius_m'], fs_lod_px=p['lod_px'], fs_gap_value=p['gap_value'], fs_groove_value=p['groove_value'],
               fs_inset_value=p['inset_value'], fs_jitter=p['jitter'], fs_repair_share=p['repair_share'], fs_repair_value=p['repair_value'])
    out.update({'fs_'+k: v for k, v in interfaces(s).items()})
    return out


def runtime(s):
    """The manifest/web block: the selected pattern, the materials and faces it applies to, and the uniforms. Presentation only."""
    p = params(s)
    return dict(status=p['status'], source_ref=p['evidence_ref'], pattern=p['pattern'], materials=p['ram_materials'], x_min_m=p['x_min_m'],
                normal_x_min=p['normal_x_min'], uniforms=uniforms(s))


# ---------- the reference pattern (the GLSL follows it line for line) -------------------------------------------------------------------

def _ihash(x):
    """lowbias32 integer hash on 32-bit unsigned words (the shader's uint arithmetic)."""
    x &= 0xffffffff
    x ^= x >> 16; x = (x*2146121005) & 0xffffffff
    x ^= x >> 15; x = (x*2221713035) & 0xffffffff
    return x ^ (x >> 16)


def _hash3(x, y, z):
    """Hash in [0, 1) of three whole numbers, exact on every GPU (24 bits, so the float conversion is exact too)."""
    h = _ihash(int(x)+_ihash(int(y)+_ihash(int(z))))
    return (h >> 8)/16777216.0


def _smoothstep(a, b, x):
    t = min(max((x-a)/(b-a), 0.0), 1.0)
    return t*t*(3.0-2.0*t)


def _line(d, w, fw):
    """Antialiased coverage of a line of width w at distance d from its centre, for a footprint of fw metres per pixel; a line thinner than
    a pixel is drawn one pixel wide at w/fw strength, so it fades instead of breaking up."""
    we = max(w, fw)
    return min(max(.5+(we/2-d)/fw, 0.0), 1.0)*(w/we)


def _vgroove(d, w, fw):
    """V-groove relief profile; a groove under three pixels wide flattens out and widens to two pixels (no speckled normals)."""
    return min(max(1.0-2.0*d/max(w, 2*fw), 0.0), 1.0)*_smoothstep(fw, 3*fw, w)


def plate_of(y, z, a):
    """Axial (q, r) of the flat-top hexagon of side a holding (y, z) and the point relative to its centre."""
    fq = (2.0/3.0*y)/a; fr = (-y/3.0+SQRT3/3.0*z)/a; fs = -fq-fr
    q, r, t = math.floor(fq+.5), math.floor(fr+.5), math.floor(fs+.5)
    dq, dr, dt = abs(q-fq), abs(r-fr), abs(t-fs)
    if dq > dr and dq > dt:
        q = -r-t
    elif dr > dt:
        r = -q-t
    cy = a*1.5*q; cz = a*SQRT3*(r+q/2.0)
    return q, r, y-cy, z-cz


def closeout_distance(u, y, z):
    """Signed distance (m) from the nearest keep-out boundary: negative inside a closeout collar."""
    r = math.hypot(y, z)
    vy, vz = abs(abs(y)-u['fs_well_q']), abs(abs(z)-u['fs_well_q'])
    # a round keep-out, or the flat-top hexagon of the EYE shell (corners on +-Y; fs_well_r its apothem)
    dw = max(vz, vy*SQRT3/2+vz/2)-u['fs_well_r'] if u['fs_well_hex'] > .5 else math.hypot(vy, vz)-u['fs_well_r']
    dl = r-u['fs_lance_r']
    step = 2*math.pi/u['fs_crown_n']; th = math.atan2(z, y)-u['fs_crown_phase']
    dth = th-step*math.floor(th/step+.5)
    dx = abs(r*math.sin(dth))-u['fs_crown_hw']; dr = abs(r-u['fs_crown_rm'])-u['fs_crown_hr']
    dc = math.hypot(max(dx, 0.0), max(dr, 0.0))+min(max(dx, dr), 0.0)
    return min(dw, dl, dc, u['fs_rim_r']-r)


def sample(u, y, z, fw=0.002):
    """Value multiplier, height (m, 0 the plate face, negative into it) and region at (y, z) for a footprint of fw metres per pixel.
    Regions: closeout, collar_seam, gap, fastener, groove, inset, face."""
    e = closeout_distance(u, y, z)
    if e < 0.0:
        c = _line(-e, u['fs_gap'], fw)
        return dict(value=1.0+c*(u['fs_gap_value']-1.0), height=-2*u['fs_relief']*_vgroove(-e, u['fs_gap'], fw), region='collar_seam' if c > .5 else 'closeout', level=-1)
    a = u['fs_side']; h0 = a*SQRT3/2
    q, rr, ly, lz = plate_of(y, z, a)
    tone = 1.0+(_hash3(q, rr, 7.0)-.5)*2*u['fs_jitter']+(u['fs_repair_value']-1.0 if _hash3(q+37.0, rr-11.0, 3.0) < u['fs_repair_share'] else 0.0)
    k = int(math.floor(math.atan2(lz, ly)/(math.pi/3))) % 6
    ang = -k*math.pi/3; py = ly*math.cos(ang)-lz*math.sin(ang); pz = ly*math.sin(ang)+lz*math.cos(ang)
    b1 = 2*pz/(a*SQRT3); b0 = py/a-b1/2; bc = 1.0-b0-b1
    vy, vz = (a, 0.0) if k % 2 == 0 else (a/2, h0)      # the plate's A vertex in this sector: the tri-clamp
    df = math.hypot(py-vy, pz-vz)
    value, height, region, level = tone, 0.0, 'face', 0
    f0 = _smoothstep(u['fs_lod_px']*fw, 2*u['fs_lod_px']*fw, a)
    groove = _line(min(b0, b1)*h0, u['fs_groove'], fw)*f0
    height = -u['fs_relief']*f0*_vgroove(min(b0, b1)*h0, u['fs_groove'], fw)
    if groove > .5:
        region = 'groove'
    b = [bc, b0, b1]; path = 1.0; side = a; w = u['fs_groove']
    for lv in range(1, MAX_DEPTH+1):
        if lv > u['fs_depth'] or _hash3(q*7.0+k, rr*7.0+lv, path) >= u['fs_density']:
            break
        hk = side*SQRT3/2; w *= u['fs_ratio']; fk = _smoothstep(u['fs_lod_px']*fw, 2*u['fs_lod_px']*fw, side/2)
        d = min(abs(bi-.5) for bi in b)*hk
        c = _line(d, w, fw)*fk
        if c > groove:
            groove = c
            if c > .5:
                region, level = 'groove', lv
        height = min(height, -u['fs_relief']*fk*_vgroove(d, w, fw))
        if max(b) < .5:
            value *= 1.0+fk*(u['fs_inset_value']-1.0)
            height = min(height, -u['fs_inset']*fk)
            if region == 'face':
                region, level = 'inset', lv
            break
        j = b.index(max(b)); b = [2*bi for bi in b]; b[j] -= 1.0
        path = path*4.0+j+1.0; side /= 2
    value *= 1.0+groove*(u['fs_groove_value']-1.0)
    if df < u['fs_fastener']:                                  # the clamp cap covers the plate gap at the corner
        ring = _line(u['fs_fastener']-df, u['fs_groove'], fw)
        return dict(value=tone*(1.0+ring*(u['fs_groove_value']-1.0)), height=-u['fs_relief']*_vgroove(u['fs_fastener']-df, u['fs_groove'], fw),
                    region='fastener', level=0)
    cg = _line(bc*h0, u['fs_gap'], fw)
    value += cg*(u['fs_gap_value']-value)
    height = min(height, -2*u['fs_relief']*_vgroove(bc*h0, u['fs_gap'], fw))
    if cg > .5:
        region = 'gap'
    return dict(value=value, height=height, region=region, level=level)


def eye_keepout_corner(u):
    """Corner radius of the hexagonal EYE keep-out (fs_well_r is its apothem), or the round keep-out's radius."""
    return u['fs_well_r']*2/SQRT3 if u['fs_well_hex'] else u['fs_well_r']


def eye_shell_probes(s, u):
    """Closeout distances along the edge of every hexagonal EYE shell (= its layer port): corners and edge midpoints."""
    sh = forward_shield.eye_shell(s)
    return [closeout_distance(u, y, z) for w in forward_shield.wells(s) for y, z in forward_shield.hexagon(sh['side'], w['y'], w['z'], 4)]


# ---------- fit screen ------------------------------------------------------------------------------------------------------------------

def screen(s):
    """Fit checks of the PROTOTYPE parameters against the grammar and the forward geometry: (name, ok, detail)."""
    p = params(s); u = uniforms(s); X = s['production']['exterior']; fp = forward_shield.prototype(s)
    a = p['plate_side_m']; depth = int(p['fractal_depth']); smallest = a/2**depth
    skin = fp['skin_thickness_m']; layer = forward_shield.disruptor_layers(s)[0]
    lo, hi = X['shell_panel_m']; micro = X['tier_min_feature_m']['micro']
    layer_t = min(skin, layer['thickness'])
    out = [('pattern', p['pattern'] in ('fractal_hex', 'running_bond'), p['pattern']),
           ('plate edge inside the shell module range', lo <= a <= hi, f'{a} m in {lo}-{hi} m'),
           ('fractal depth inside the shader loop', 0 <= depth <= MAX_DEPTH, f'{depth} <= {MAX_DEPTH}'),
           ('smallest triangle at least the micro feature', smallest >= micro, f'{smallest:.3f} m >= {micro} m'),
           ('density a probability', 0.0 <= p['density'] <= 1.0, str(p['density'])),
           ('relief is surface only (thinnest sheet)', p['relief_m']+p['inset_m'] <= p['max_relief_fraction']*layer_t,
            f"{p['relief_m']+p['inset_m']:.4f} m <= {p['max_relief_fraction']} x {layer_t} m"),
           ('gap relief inside the thinnest sheet', 2*p['relief_m'] < layer_t, f"{2*p['relief_m']:.4f} m < {layer_t} m"),
           ('groove narrower than the plate gap', p['groove_m'] < p['plate_gap_m'], f"{p['groove_m']} < {p['plate_gap_m']} m"),
           ('clamp covers the gap junction', p['fastener_radius_m'] > p['plate_gap_m'], f"{p['fastener_radius_m']} > {p['plate_gap_m']} m"),
           ('clamp inside its corner triangles', p['fastener_radius_m'] < a/4, f"{p['fastener_radius_m']} < {a/4} m"),
           ('EYE wells and ports inside the collar', (u['fs_well_r']-p['plate_gap_m'] if u['fs_well_hex'] else u['fs_well_r']-p['closeout_m'])
            >= max(w['radius'] for w in forward_shield.wells(s)), f"keep-out r {u['fs_well_r']:.3f} m"),
           ('Lance root inside the collar', u['fs_lance_r']-p['closeout_m'] >= forward_shield.lance_radius_at(s, forward_shield.stations(s)['face']),
            f"keep-out r {u['fs_lance_r']:.3f} m"),
           ('wells and Lance keep-outs inside the flat hub' if not forward_shield.eye_layout_active(s) else 'EYE keep-outs clear of the Crown keep-outs',
            *((u['fs_well_q']*math.sqrt(2)+u['fs_well_r'] < forward_shield.cone_start_radius(s),
               f"{u['fs_well_q']*math.sqrt(2)+u['fs_well_r']:.3f} m < {forward_shield.cone_start_radius(s)} m") if not forward_shield.eye_layout_active(s) else
              (u['fs_well_q']*math.sqrt(2)+eye_keepout_corner(u) < u['fs_crown_rm']-u['fs_crown_hr'],
               f"{u['fs_well_q']*math.sqrt(2)+eye_keepout_corner(u):.3f} m < {u['fs_crown_rm']-u['fs_crown_hr']:.3f} m")))]
    probes = []
    for o in forward_shield.crown_skin_windows(s)+forward_shield.crown_ports(s):
        for rr in (o['r0'], o['r1'], (o['r0']+o['r1'])/2):
            for t in (-1.0, 0.0, 1.0):
                th = o['azimuth']+t*o['half_angle']
                probes.append(closeout_distance(u, rr*math.cos(th), rr*math.sin(th)))
    if not u['fs_well_hex']:
        for w in forward_shield.wells(s)+forward_shield.eye_ports(s, layer):
            for k in range(16):
                th = 2*math.pi*k/16
                probes.append(closeout_distance(u, w['y']+w['radius']*math.cos(th), w['z']+w['radius']*math.sin(th)))
    worst = max(probes)
    out.append(('every opening edge at least closeout_m inside a collar', worst <= -p['closeout_m']+1e-9, f'worst {worst:.3f} m'))
    if u['fs_well_hex']:          # the hexagonal EYE shell: its edge (the port's) sits one plate gap inside the keep-out, like a neighbouring plate
        worst = max(eye_shell_probes(s, u))
        out.append(('EYE shell edge one plate gap inside its keep-out', worst <= -p['plate_gap_m']+1e-9, f'worst {worst:.3f} m'))
    lowest = min(sample(u, y*.0173, z*.0173)['height'] for y in range(-400, 401, 7) for z in range(-400, 401, 7))
    out.append(('no sample deeper than the gap relief (no perforation)', lowest >= -2*p['relief_m']-1e-12, f'lowest {lowest:.4f} m'))
    return out


def area_shares(s, n=240, extent=None):
    """Region shares over a square of the cone (default: two plates either side of r 25 m) at a close footprint: the read of the pattern."""
    u = uniforms(s); half = extent or 2*u['fs_side']; counts = {}
    for i in range(n):
        for j in range(n):
            reg = sample(u, 25.0+(i/(n-1)*2-1)*half, (j/(n-1)*2-1)*half)['region']
            counts[reg] = counts.get(reg, 0)+1
    return {k: round(v/n/n, 4) for k, v in sorted(counts.items())}


def png(s, path, size=1024, centre=(0.0, 0.0), half=10.0, fw=None, light=(-.55, .45)):
    """A grey preview raster of the pattern over a square (Blender Y right, Z up) with a raking light on the height field. Standard library."""
    u = uniforms(s); fw = fw or 2*half/size; rows = []
    lx, lz = light; lzz = math.sqrt(max(0.0, 1-lx*lx-lz*lz))
    hs = {}
    for j in range(size+1):
        for i in range(size+1):
            y = centre[0]+(i/size*2-1)*half; z = centre[1]+(1-j/size*2)*half
            hs[i, j] = sample(u, y, z, fw)
    for j in range(size):
        row = bytearray([0])
        for i in range(size):
            c = hs[i, j]; gx = (hs[i+1, j]['height']-c['height'])/fw; gz = (c['height']-hs[i, j+1]['height'])/fw
            nx, nz = -gx, -gz; nn = math.sqrt(nx*nx+nz*nz+1)
            shade = max(0.0, (nx*lx+nz*lz+lzz)/nn)
            v = min(255, int(255*(.73*c['value'])*(.35+.75*shade)))
            row += bytes((v, v, v))
        rows.append(bytes(row))
    def chunk(t, d):
        return struct.pack('>I', len(d))+t+d+struct.pack('>I', zlib.crc32(t+d) & 0xffffffff)
    data = b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR', struct.pack('>IIBBBBB', size, size, 8, 2, 0, 0, 0))+chunk(b'IDAT', zlib.compress(b''.join(rows), 9))+chunk(b'IEND', b'')
    Path(path).write_bytes(data)
    return path


if __name__ == '__main__':
    import argparse
    import json
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from spec import load
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--png', help='write a preview raster here (with --centre y z and --half m)')
    ap.add_argument('--centre', nargs=2, type=float, default=(0.0, 0.0))
    ap.add_argument('--half', type=float, default=10.0)
    ap.add_argument('--size', type=int, default=768)
    ap.add_argument('--fw', type=float, help='metres per pixel for the LOD (default: the raster footprint)')
    args = ap.parse_args()
    s, *_ = load()
    checks = screen(s)
    print(json.dumps({'result': 'PASS' if all(ok for _, ok, _ in checks) else 'FAIL', 'checks': [dict(name=n, ok=ok, detail=d) for n, ok, d in checks],
                      'uniforms': uniforms(s), 'area_shares': area_shares(s)}, indent=1))
    if args.png:
        png(s, args.png, args.size, tuple(args.centre), args.half, args.fw)
        print('wrote', args.png)
