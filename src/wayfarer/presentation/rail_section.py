"""Crawler rail cross-section for the ship-session interface request (docs/ACCESSORIES.md, request 3): wheel capture, the support web and
the corridor a passing truck leaves for rail mounts. Standard library only; writes an SVG from the PROTOTYPE truck parameters in
data/drone_bodies.toml (drone_bodies.truck). Every dimension is a proposal for the owner's rail study, not a rating or an approved section.

  python3 src/wayfarer/presentation/rail_section.py --out runs/rail_section.svg
"""
import argparse
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT/'src/wayfarer'))
import drone_bodies as db       # noqa: E402

MARGIN = .005                   # proposed running clearance between an under-wheel and the web (PROTOTYPE)


def geometry(d):
    """Section numbers (m) of one rail and its captive truck, in the rail's cross plane (y across, z up, rail centre at 0)."""
    i = d['interface']; rr, wr, ww = i['rail_radius_m'], i['truck_wheel_r_m'], i['truck_wheel_w_m']
    R = rr+2*wr+.015; tube = .010; arc = 126.0                                   # as drone_bodies.truck
    wheels = []
    for phi in (0.0, 120.0, -120.0):
        c, s = math.cos(math.radians(phi)), math.sin(math.radians(phi))
        pts = [(yy*c-zz*s, yy*s+zz*c) for yy, zz in ((-ww/2, rr), (ww/2, rr), (ww/2, rr+2*wr), (-ww/2, rr+2*wr))]
        wheels.append(dict(phi=phi, pts=pts))
    inner = min(min(abs(p[0]) for p in w['pts']) for w in wheels[1:])          # under-wheel inner edge from the web centreline
    lowest = min(p[1] for w in wheels for p in w['pts'])
    edge = (R*math.sin(math.radians(arc)), R*math.cos(math.radians(arc)))
    return dict(rail_r=rr, wheel_r=wr, wheel_w=ww, clamp_R=R, clamp_tube=tube, clamp_arc=arc, wheels=wheels,
                opening=2*(edge[0]-tube), clamp_low=edge[1]-tube, under_wheel_inner=inner, wheel_low=lowest,
                web_corridor=2*(inner-MARGIN), corridor_depth=min(edge[1]-tube, lowest)-.010, gauge=i['rail_gauge_m'])


def svg(g):
    S = 2400.0; W, H = 1500, 980; ox, oy = 450, 420                           # px per m; rail centre on screen
    P = lambda y, z: (ox+y*S, oy-z*S)
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" font-family="Helvetica, Arial, sans-serif">',
           '<rect width="100%" height="100%" fill="#ffffff"/>',
           '<defs><pattern id="h" width="8" height="8" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">'
           '<line x1="0" y1="0" x2="0" y2="8" stroke="#d9534f" stroke-width="2"/></pattern></defs>']
    t = lambda x, y, s, size=17, w='normal', c='#222', a='start': out.append(
        f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" font-weight="{w}" fill="{c}" text-anchor="{a}">{s}</text>')
    t(40, 48, 'CRAWLER RAIL CROSS-SECTION — interface request to the ship session (PROTOTYPE, not a rated section)', 24, 'bold')
    t(40, 78, 'One rail of a GU twin-rail track and the captive three-wheel truck of DR-EVA-01/02/03 (data/drone_bodies.toml). Rail loads, '
              'wheel and latch ratings: OPEN (DGT-004).', 16, c='#555')
    # keep-out: everything a passing truck sweeps (clamp ring + wheels), and the web corridor below
    R, tube = g['clamp_R'], g['clamp_tube']
    x0, y0 = P(-R-tube, R+tube); out.append(f'<circle cx="{ox}" cy="{oy}" r="{(R+tube)*S:.1f}" fill="#fbe9e7" stroke="#d9534f" stroke-dasharray="6 5"/>')
    cw = g['web_corridor']; zc = g['corridor_depth']
    a = P(-cw/2, -g['rail_r']); b = P(cw/2, zc)
    out.append(f'<rect x="{a[0]:.1f}" y="{a[1]:.1f}" width="{cw*S:.1f}" height="{b[1]-a[1]:.1f}" fill="#e3f2fd" stroke="#1e88e5" stroke-dasharray="4 4"/>')
    # support web and its foot
    web_t, standoff = .012, .15
    a = P(-web_t/2, -g['rail_r']*.6); out.append(f'<rect x="{a[0]:.1f}" y="{a[1]:.1f}" width="{web_t*S:.1f}" height="{(standoff-g["rail_r"]*.6)*S:.1f}" fill="#9e9e9e"/>')
    a = P(-.04, -standoff+.012); out.append(f'<rect x="{a[0]:.1f}" y="{a[1]:.1f}" width="{.08*S:.1f}" height="{.012*S:.1f}" fill="#9e9e9e"/>')
    a = P(-.16, -standoff); out.append(f'<rect x="{a[0]:.1f}" y="{a[1]:.1f}" width="{.32*S:.1f}" height="{.02*S:.1f}" fill="#cfd8dc"/>')
    # rail
    out.append(f'<circle cx="{ox}" cy="{oy}" r="{g["rail_r"]*S:.1f}" fill="#b0bec5" stroke="#455a64" stroke-width="2"/>')
    # clamp arc (open below)
    a0, a1 = math.radians(-g['clamp_arc']), math.radians(g['clamp_arc'])
    p0 = P(R*math.sin(a0), R*math.cos(a0)); p1 = P(R*math.sin(a1), R*math.cos(a1))
    out.append(f'<path d="M {p0[0]:.1f} {p0[1]:.1f} A {R*S:.1f} {R*S:.1f} 0 1 1 {p1[0]:.1f} {p1[1]:.1f}" fill="none" stroke="#37474f" stroke-width="{2*tube*S:.1f}" stroke-linecap="round"/>')
    for w in g['wheels']:                                                       # strut from the wheel to the clamp ring, then the wheel
        c, s_ = math.cos(math.radians(w['phi'])), math.sin(math.radians(w['phi'])); r0 = g['rail_r']+2*g['wheel_r']
        q = [(yy*c-zz*s_, yy*s_+zz*c) for yy, zz in ((-.011, r0-.004), (.011, r0-.004), (.011, R), (-.011, R))]
        out.append(f'<polygon points="{" ".join(f"{P(*p)[0]:.1f},{P(*p)[1]:.1f}" for p in q)}" fill="#455a64"/>')
        pts = ' '.join(f'{P(*p)[0]:.1f},{P(*p)[1]:.1f}' for p in w['pts'])
        out.append(f'<polygon points="{pts}" fill="#90a4ae" stroke="#263238" stroke-width="2"/>')
        a = P(-(g['wheel_w']/2+.004)*c-(g['rail_r']+g['wheel_r'])*s_, -(g['wheel_w']/2+.004)*s_+(g['rail_r']+g['wheel_r'])*c)
        b = P((g['wheel_w']/2+.004)*c-(g['rail_r']+g['wheel_r'])*s_, (g['wheel_w']/2+.004)*s_+(g['rail_r']+g['wheel_r'])*c)
        out.append(f'<line x1="{a[0]:.1f}" y1="{a[1]:.1f}" x2="{b[0]:.1f}" y2="{b[1]:.1f}" stroke="#111" stroke-width="2"/>')   # axle
    # dimensions
    def dim(y0_, z0_, y1_, z1_, label, dy=0, side='start'):
        a, b = P(y0_, z0_), P(y1_, z1_)
        out.append(f'<line x1="{a[0]:.1f}" y1="{a[1]+dy:.1f}" x2="{b[0]:.1f}" y2="{b[1]+dy:.1f}" stroke="#111" stroke-width="1.5" marker-start="url(#m)" marker-end="url(#m)"/>')
        t((a[0]+b[0])/2, (a[1]+b[1])/2+dy-8, label, 15, a='middle')
    out.insert(3, '<defs><marker id="m" markerWidth="8" markerHeight="8" refX="4" refY="4" orient="auto"><circle cx="4" cy="4" r="2.2" fill="#111"/></marker></defs>')
    dim(-g['rail_r'], 0, g['rail_r'], 0, f"rail Ø{2*g['rail_r']*1000:.0f}", dy=0)
    e = R*math.sin(math.radians(g['clamp_arc']))-tube
    dim(-e, g['clamp_low']+tube, e, g['clamp_low']+tube, f"clamp opening {g['opening']*1000:.0f}", dy=26)
    dim(-cw/2, zc, cw/2, zc, f"web corridor ≤ {cw*1000:.0f}", dy=22)
    # notes
    x = 900; y = 140
    for line, c, wgt in [
            ('What the section shows', '#111', 'bold'),
            (f"• Rail Ø{2*g['rail_r']*1000:.0f} mm, gauge {g['gauge']*1000:.0f} mm between the two rails (PROTOTYPE).", '#222', 'normal'),
            (f"• Three wheels Ø{2*g['wheel_r']*1000:.0f} × {g['wheel_w']*1000:.0f} mm at 0° and ±120°: a load wheel on top,", '#222', 'normal'),
            ('  two up-stop wheels under the rail on either side of the web:', '#222', 'normal'),
            ('  captive in every direction (no reliance on gravity or magnets).', '#222', 'normal'),
            ('  (wheels cut through their axles: seen edge-on as rectangles)', '#555', 'normal'),
            (f"• C-clamp frame R{R*1000:.0f} mm, open {360-2*g['clamp_arc']:.0f}° at the bottom ({g['opening']*1000:.0f} mm gap)", '#222', 'normal'),
            ('  so the truck passes every support web without opening.', '#222', 'normal'),
            ('', '#222', 'normal'),
            ('What the ship session is asked to keep', '#111', 'bold'),
            (f"• Blue: support web corridor ≤ {cw*1000:.0f} mm wide from the rail down to", '#1565c0', 'normal'),
            (f"  {abs(zc)*1000:.0f} mm below the rail centre ({MARGIN*1000:.0f} mm running clearance", '#1565c0', 'normal'),
            (f"  to each under-wheel, inner edge at ±{g['under_wheel_inner']*1000:.0f} mm).", '#1565c0', 'normal'),
            ('• Wider brackets, feet and fasteners only below that depth.', '#1565c0', 'normal'),
            (f"• Red dashed: swept truck envelope Ø{2*(R+tube)*1000:.0f} mm around the rail axis,", '#c62828', 'normal'),
            ('  free of structure, harness and markings along the whole track.', '#c62828', 'normal'),
            ('', '#222', 'normal'),
            ('Open before approval', '#111', 'bold'),
            ('• rail section and material, web spacing, rail and wheel loads,', '#555', 'normal'),
            ('  thermal expansion of rail vs. casing, joint and switch details,', '#555', 'normal'),
            ('  truck preload, bearing rating in vacuum, dust/debris tolerance.', '#555', 'normal'),
            ('• A request for a placement and section study, not an edit', '#555', 'normal'),
            ('  of ship geometry: the ship session owns rails and anchors.', '#555', 'normal')]:
        t(x, y, line, 17, wgt, c); y += 27
    t(40, H-30, 'Section across the rail (y across, z up), 2.4 px per mm. Grey web and foot: the review fixture\'s support, '
               'shown as the proposed pattern. Generated by src/wayfarer/presentation/rail_section.py.', 14, c='#666')
    out.append('</svg>')
    return '\n'.join(out)+'\n'


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--out', type=Path, default=ROOT/'runs/rail_section.svg')
    a = ap.parse_args(); _, d = db.load(ROOT); g = geometry(d)
    a.out.parent.mkdir(parents=True, exist_ok=True); a.out.write_text(svg(g))
    print({k: (round(v, 4) if isinstance(v, float) else v) for k, v in g.items() if k != 'wheels'})


if __name__ == '__main__':
    main()
