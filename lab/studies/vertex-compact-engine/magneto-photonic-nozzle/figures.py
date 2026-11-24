"""Figures for the MPN study, drawn as plain SVG from results/mpn.json (standard library only):

    python3 lab/studies/vertex-compact-engine/magneto-photonic-nozzle/figures.py

Charts are calculated values; the concept diagram (fig6) is a schematic, not to scale, and its rays are illustrative.
"""
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
R = json.loads((HERE/'results'/'mpn.json').read_text())
OUT = HERE/'figures'
OUT.mkdir(exist_ok=True)
SER = ['#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#e87ba4', '#008300', '#6250d6', '#e34948']
INK, INK2, GRID, BG = '#0b0b0b', '#52514e', '#e4e3df', '#fcfcfb'
FONT = "font-family='Inter, Helvetica, Arial, sans-serif'"


def esc(s):
    return str(s).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


class Plot:
    def __init__(self, title, sub, xlab, ylab, xr, yr, logx=True, logy=True, w=760, h=470):
        self.w, self.h = w, h
        self.l, self.r, self.t, self.b = 78, 190, 64, 58
        self.xr, self.yr, self.logx, self.logy = xr, yr, logx, logy
        self.el = [f"<rect width='{w}' height='{h}' fill='{BG}'/>",
                   f"<text x='20' y='26' {FONT} font-size='16' font-weight='600' fill='{INK}'>{esc(title)}</text>",
                   f"<text x='20' y='46' {FONT} font-size='12' fill='{INK2}'>{esc(sub)}</text>"]
        self.xlab, self.ylab = xlab, ylab

    def X(self, x):
        a, b = self.xr
        f = (math.log10(x)-math.log10(a))/(math.log10(b)-math.log10(a)) if self.logx else (x-a)/(b-a)
        return self.l+f*(self.w-self.l-self.r)

    def Y(self, y):
        a, b = self.yr
        y = min(max(y, a), b)
        f = (math.log10(y)-math.log10(a))/(math.log10(b)-math.log10(a)) if self.logy else (y-a)/(b-a)
        return self.h-self.b-f*(self.h-self.t-self.b)

    def axes(self, xt, yt, xfmt=lambda v: f'{v:g}', yfmt=lambda v: f'{v:g}'):
        for v in yt:
            y = self.Y(v)
            self.el.append(f"<line x1='{self.l}' x2='{self.w-self.r}' y1='{y:.1f}' y2='{y:.1f}' stroke='{GRID}'/>")
            self.el.append(f"<text x='{self.l-8}' y='{y+4:.1f}' text-anchor='end' {FONT} font-size='11' fill='{INK2}'>{yfmt(v)}</text>")
        for v in xt:
            x = self.X(v)
            self.el.append(f"<text x='{x:.1f}' y='{self.h-self.b+18}' text-anchor='middle' {FONT} font-size='11' fill='{INK2}'>{xfmt(v)}</text>")
        self.el.append(f"<line x1='{self.l}' x2='{self.w-self.r}' y1='{self.h-self.b}' y2='{self.h-self.b}' stroke='{INK2}'/>")
        self.el.append(f"<text x='{(self.l+self.w-self.r)/2}' y='{self.h-14}' text-anchor='middle' {FONT} font-size='12' fill='{INK2}'>{esc(self.xlab)}</text>")
        self.el.append(f"<text transform='translate(18,{(self.t+self.h-self.b)/2}) rotate(-90)' text-anchor='middle' {FONT} font-size='12' fill='{INK2}'>{esc(self.ylab)}</text>")

    def line(self, pts, color, label, dash=None, width=2):
        d = ' '.join(f"{'M' if i == 0 else 'L'}{self.X(x):.1f},{self.Y(y):.1f}" for i, (x, y) in enumerate(pts))
        da = f" stroke-dasharray='{dash}'" if dash else ''
        self.el.append(f"<path d='{d}' fill='none' stroke='{color}' stroke-width='{width}' stroke-linejoin='round'{da}><title>{esc(label)}</title></path>")

    def hline(self, y, label):
        yy = self.Y(y)
        self.el.append(f"<line x1='{self.l}' x2='{self.w-self.r}' y1='{yy:.1f}' y2='{yy:.1f}' stroke='{INK}' stroke-dasharray='5 4'/>")
        self.el.append(f"<text x='{self.w-self.r+6}' y='{yy+4:.1f}' {FONT} font-size='11' fill='{INK}'>{esc(label)}</text>")

    def legend(self, items):
        y = self.t+6
        for color, label, dash in items:
            da = f" stroke-dasharray='{dash}'" if dash else ''
            self.el.append(f"<line x1='{self.w-self.r+14}' x2='{self.w-self.r+36}' y1='{y}' y2='{y}' stroke='{color}' stroke-width='2.5'{da}/>")
            self.el.append(f"<text x='{self.w-self.r+42}' y='{y+4}' {FONT} font-size='11' fill='{INK}'>{esc(label)}</text>")
            y += 20

    def save(self, name, desc):
        svg = (f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 {self.w} {self.h}' width='{self.w}' height='{self.h}' role='img'>"
               f"<title>{esc(desc)}</title>" + ''.join(self.el) + '</svg>')
        (OUT/name).write_text(svg)


def fig1():
    o = R['optics']
    p = Plot('Steering cost: what it costs to turn a photon', 'Loss per radian of deflection by grazing reflection, 2β/θc³ (xraylib data). '
             'A 10 mrad turn loses ≈ g × 0.01.', 'photon energy (keV)', 'g, loss per radian', (3, 1000), (0.005, 300))
    p.axes([3, 10, 30, 100, 300, 1000], [0.01, 0.1, 1, 10, 100])
    items = []
    for i, m in enumerate(('C_diamond', 'Be', 'Ni', 'W', 'Pt')):
        pts = sorted((float(E), g) for E, g in o['steering_cost'][m].items())
        p.line(pts, SER[i], m); items.append((SER[i], m.replace('C_diamond', 'diamond'), None))
    for j, (lab, row) in enumerate(o['compton_floor'].items()):
        pts = sorted((float(E), g) for E, g in row.items())
        p.line(pts, INK2, 'Compton floor', dash='4 3' if j == 0 else '1 3', width=1.5)
        items.append((INK2, 'Compton floor, ' + ('diamond nₑ' if j == 0 else 'osmium nₑ'), '4 3' if j == 0 else '1 3'))
    p.legend(items)
    p.save('fig1_steering_cost.svg', 'Steering cost of grazing reflection versus photon energy for five materials and the Compton floors')


def fig2():
    o = R['optics']['R_curves']
    p = Plot('Grazing reflectivity falls off a cliff above θc', 'Fresnel reflectivity, 0.2 nm roughness. Solid: diamond; dashed: platinum.',
             'grazing angle (mrad)', 'reflectivity', (0.02, 60), (0, 1), logy=False)
    p.axes([0.03, 0.1, 0.3, 1, 3, 10, 30], [0, 0.25, 0.5, 0.75, 1.0])
    items = []
    for i, E in enumerate((10, 30, 100, 300)):
        for m, dash in (('C_diamond', None), ('Pt', '5 3')):
            p.line([q for q in o[f'{m}@{E}'] if 0.02 <= q[0] <= 60], SER[i], f'{m} {E} keV', dash=dash)
        items.append((SER[i], f'{E} keV', None))
    items.append((INK2, 'platinum', '5 3'))
    p.legend(items)
    p.save('fig2_reflectivity.svg', 'Reflectivity versus grazing angle for diamond and platinum at 10, 30, 100 and 300 keV')


def fig3():
    sk = R['maps']['skimmer_vs_L_over_a']
    p = Plot('A skimmer must be thousands of times longer than what it hides', 'Absorbed share of bremsstrahlung on a grazing wedge of flank atan(a/L). '
             'Solid V0 (Te 55 keV), dashed V2 (46 keV).', 'wedge length / half-width hidden, L/a', 'absorbed share',
             (10, 30000), (1e-4, 1))
    p.axes([10, 30, 100, 300, 1000, 3000, 10000, 30000], [1e-4, 1e-3, 0.01, 0.1, 1])
    items = []
    for i, m in enumerate(('C_diamond', 'Pt', 'Os')):
        for key, dash in (('V0', None), ('V2', '5 3')):
            p.line(sk[f'{key}/{m}'], SER[i], f'{key} {m}', dash=dash)
        items.append((SER[i], m.replace('C_diamond', 'diamond'), None))
    p.legend(items)
    p.save('fig3_skimmer_law.svg', 'Absorbed share of a grazing skimmer versus its length-to-half-width ratio for diamond, platinum and osmium')


def fig4():
    """Feasibility: four-engine photon + neutron heat over the 10.8 GW drive share, V2 source, by sky share and absorptance."""
    m = R['maps']['intercept']['V2']
    fs, As, g = m['f'], m['A'], m['heat_over_budget']
    w, h = 760, 520; l, r, t, b = 90, 170, 64, 62
    cw = (w-l-r)/len(As); ch = (h-t-b)/len(fs)
    ramp = ['#cde2fb', '#9ec5f4', '#6da7ec', '#3987e5', '#256abf', '#184f95', '#0d366b']
    el = [f"<rect width='{w}' height='{h}' fill='{BG}'/>",
          f"<text x='20' y='26' {FONT} font-size='16' font-weight='600' fill='{INK}'>Where the heat fits: hardware sky × absorbed share</text>",
          f"<text x='20' y='46' {FONT} font-size='12' fill='{INK2}'>Four engines, V2 source, photons and neutrons (half deposited), over the 10.8 GW drive share. White cells fit.</text>"]
    for i, f in enumerate(fs):
        for j, A in enumerate(As):
            v = g[i][j]
            if v <= 1:
                col = '#ffffff'
            else:
                col = ramp[min(len(ramp)-1, int(math.log10(v)))]
            x = l+j*cw; y = t+i*ch
            el.append(f"<rect x='{x:.1f}' y='{y:.1f}' width='{cw-2:.1f}' height='{ch-2:.1f}' rx='2' fill='{col}' stroke='{GRID}' stroke-width='0.5'>"
                      f"<title>sky {f:.1e}, absorbed {A:.1e}: {v:.3g} x budget</title></rect>")
    for i, f in enumerate(fs):
        if i % 4 == 0:
            el.append(f"<text x='{l-8}' y='{t+i*ch+ch/2+4:.1f}' text-anchor='end' {FONT} font-size='11' fill='{INK2}'>{f:.0e}</text>")
    for j, A in enumerate(As):
        if j % 4 == 0:
            el.append(f"<text x='{l+j*cw+cw/2:.1f}' y='{h-b+16}' text-anchor='middle' {FONT} font-size='11' fill='{INK2}'>{A:.0e}</text>")
    el.append(f"<text x='{(l+w-r)/2}' y='{h-20}' text-anchor='middle' {FONT} font-size='12' fill='{INK2}'>effective photon absorbed share A (1 = black body, 1e-4 = 99.99 % reflector)</text>")
    el.append(f"<text transform='translate(22,{(t+h-b)/2}) rotate(-90)' text-anchor='middle' {FONT} font-size='12' fill='{INK2}'>hardware share of the sky seen from the burn</text>")

    def mark(f, A, label, dy=0):
        j = (math.log10(1)-math.log10(A))*4; i = (math.log10(1)-math.log10(f))*4
        x = l+j*cw+cw/2; y = t+i*ch+ch/2
        v = g[min(len(fs)-1, round(i))][min(len(As)-1, round(j))]
        label = f"{label}: {'fits' if v <= 1 else f'{v:.2g}x'}"
        el.append(f"<circle cx='{x:.1f}' cy='{y:.1f}' r='6' fill='{SER[1]}' stroke='{BG}' stroke-width='2'/>")
        el.append(f"<text x='{x+10:.1f}' y='{y+4+dy:.1f}' {FONT} font-size='11' fill='{INK}'>{esc(label)}</text>")
    mark(0.617, 1.0, 'drawn engine (A, C)')
    mark(8.0e-4, 1.0, 'Halo 2.5 ring on V2')
    mark(4.8e-5, 1.0, 'F ribbon ring', dy=-14)
    mark(4.8e-5, 0.3, 'F + skimmer', dy=14)
    for k, v in enumerate(('fits', '1-10x', '10-100x', '100-1000x', '>1000x')):
        col = '#ffffff' if k == 0 else ramp[k-1]
        el.append(f"<rect x='{w-r+16}' y='{t+10+k*20}' width='14' height='14' rx='2' fill='{col}' stroke='{GRID}'/>")
        el.append(f"<text x='{w-r+36}' y='{t+21+k*20}' {FONT} font-size='11' fill='{INK}'>{v}</text>")
    (OUT/'fig4_feasibility_map.svg').write_text(f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 {w} {h}' width='{w}' height='{h}' role='img'>"
                                               "<title>Heat over budget versus hardware sky share and absorbed share</title>"+''.join(el)+'</svg>')


def fig5():
    """Ledger: four-engine heat by candidate (log bars), drive share line."""
    A = R['A_C_drawn_engine']['by_source']['V2']; B = R['B_collimator']['by_source']['V2']
    D = R['D_halo_mpn']; F = R['F_hybrid']; rec = R['F_recommended']['sensitivity']
    halo = sum(D['halo']['heat_engine_GW'].values())*4
    d40 = [r for r in D['rows'] if r['Ls_m'] == 40 and r['material'] == 'Pt'][0]['engine_heat_GW']*4
    rows = [('Drawn engine, bare (photons)', A['bare_photon_heat_four_GW']),
            ('A: best coatings on drawn engine', A['A_photon_heat_four_GW']),
            ('C: grazing fairings, drawn engine', A['C_photon_heat_four_GW']),
            ('Drawn engine, neutrons (upper)', A['neutron_heat_four_GW_upper']),
            ('B: collimator, added heat', B['heat_four_GW']),
            ('D: Halo 2.5 ledger (own source)', halo),
            ('D: same + 40 m Pt skimmer', d40),
            ('F: thick-face ring, cables', 4*F['V2 | Halo-like thick face (0.24 m), round cables']['total_W']/1e9),
            ('F: edge-on ribbon + tapes', 4*F['V2 | edge-on ribbon + edge-on tapes']['total_W']/1e9),
            ('F: recommended (R 90, D 2 km)', rec[0]['total_four_GW']),
            ('F: recommended + 20 m skimmer', [r for r in rec if r['case'].startswith('Pt knife')][0]['total_four_GW'])]
    w, h = 760, 40+36*len(rows)+70
    l, rr = 250, 110
    lo, hi = 1.0, 30000.0
    X = lambda v: l+(math.log10(max(v, lo))-math.log10(lo))/(math.log10(hi)-math.log10(lo))*(w-l-rr)
    el = [f"<rect width='{w}' height='{h}' fill='{BG}'/>",
          f"<text x='20' y='26' {FONT} font-size='16' font-weight='600' fill='{INK}'>Heat into hardware, four engines (GW, log scale)</text>",
          f"<text x='20' y='46' {FONT} font-size='12' fill='{INK2}'>V2 source (1.6B S5). Dashed line: the 10.8 GW drive share of the hot radiator. F rows include self-radiated parts.</text>"]
    for v in (1, 10, 100, 1000, 10000):
        el.append(f"<line x1='{X(v):.1f}' x2='{X(v):.1f}' y1='60' y2='{h-50}' stroke='{GRID}'/>")
        el.append(f"<text x='{X(v):.1f}' y='{h-34}' text-anchor='middle' {FONT} font-size='11' fill='{INK2}'>{v:g}</text>")
    for i, (lab, v) in enumerate(rows):
        y = 66+i*36
        col = SER[0] if v <= 10.8 else SER[1]
        el.append(f"<text x='{l-10}' y='{y+15}' text-anchor='end' {FONT} font-size='12' fill='{INK}'>{esc(lab)}</text>")
        el.append(f"<rect x='{l}' y='{y+3}' width='{max(2, X(v)-l):.1f}' height='18' rx='4' fill='{col}'><title>{esc(lab)}: {v:.3g} GW</title></rect>")
        el.append(f"<text x='{max(X(v), X(10.8))+8:.1f}' y='{y+16}' {FONT} font-size='11' fill='{INK}'>{v:,.3g}</text>")
    el.append(f"<line x1='{X(10.8):.1f}' x2='{X(10.8):.1f}' y1='60' y2='{h-50}' stroke='{INK}' stroke-dasharray='5 4'/>")
    el.append(f"<text x='{X(10.8)+4:.1f}' y='{h-52}' {FONT} font-size='11' fill='{INK}'>10.8 GW</text>")
    el.append(f"<text x='20' y='{h-12}' {FONT} font-size='11' fill='{INK2}'>Blue: fits the drive share. Orange: exceeds it. Charged leakage in F is the Halo 2.2 95 % bound (OPEN).</text>")
    (OUT/'fig5_ledger.svg').write_text(f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 {w} {h}' width='{w}' height='{h}' role='img'>"
                                      "<title>Heat into hardware for every MPN candidate against the drive share</title>"+''.join(el)+'</svg>')


def fig6():
    """Concept F schematic (not to scale): edge-on remote ring, tapes, plug, spine, ship; illustrative rays."""
    w, h = 900, 520
    el = [f"<rect width='{w}' height='{h}' fill='{BG}'/>",
          f"<text x='20' y='26' {FONT} font-size='16' font-weight='600' fill='{INK}'>Candidate F: edge-on remote ring (schematic, not to scale)</text>",
          f"<text x='20' y='46' {FONT} font-size='12' fill='{INK2}'>Every member is laid along the rays from its burn, so the burn sees only edges. Rays are illustrative, not computed trajectories.</text>"]
    bx, by = 160, 290           # burn
    rx, rt = 470, 120           # ring section points (upper and lower) at x = rx
    # plume cone (charged exhaust, aft = left)
    el.append(f"<path d='M{bx},{by} L20,{by-70} L20,{by+70} Z' fill='{SER[0]}' fill-opacity='0.12' stroke='none'/>")
    el.append(f"<text x='26' y='{by+90}' {FONT} font-size='11' fill='{INK}'>charged exhaust (magnetic, aft)</text>")
    # photon rays (fan)
    for ang in range(-80, 81, 10):
        a = math.radians(ang)
        L = min(520, (by-80 if ang > 0 else h-100-by)/max(1e-9, abs(math.sin(a))))
        x2 = bx+L*math.cos(a); y2 = by-L*math.sin(a)
        el.append(f"<line x1='{bx}' y1='{by}' x2='{x2:.0f}' y2='{y2:.0f}' stroke='{SER[3]}' stroke-width='1' stroke-opacity='0.55'/>")
    el.append(f"<text x='640' y='96' {FONT} font-size='11' fill='{INK}'>X-rays and neutrons: released to space</text>")
    # ring ribbons (upper and lower cross-section), laid along the ray through them
    for sgn in (1, -1):
        ang = math.atan2(rt, rx-bx)
        x0 = rx-40*math.cos(ang); y0 = by-sgn*(rt-40*math.sin(ang))
        x1 = rx+30*math.cos(ang); y1 = by-sgn*(rt+30*math.sin(ang))
        el.append(f"<line x1='{x0:.0f}' y1='{y0:.0f}' x2='{x1:.0f}' y2='{y1:.0f}' stroke='{SER[1]}' stroke-width='5' stroke-linecap='round'/>")
        el.append(f"<line x1='{x0:.0f}' y1='{y0:.0f}' x2='{x0+12*math.cos(ang):.0f}' y2='{y0-sgn*12*math.sin(ang):.0f}' stroke='{SER[7]}' stroke-width='7' stroke-linecap='round'/>")
        # tethers to the plug node
        el.append(f"<line x1='{x0:.0f}' y1='{y0:.0f}' x2='{bx+100}' y2='{by}' stroke='{INK2}' stroke-width='1.5'/>")
    el.append(f"<text x='{rx+40}' y='{by-rt-18}' {FONT} font-size='11' fill='{INK}'>REBCO ribbon ring, 4.4 cm thick, edge-on</text>")
    el.append(f"<text x='{rx+40}' y='{by-rt-4}' {FONT} font-size='11' fill='{INK}'>hot nose (red) radiates its own heat, ~1700 K</text>")
    el.append(f"<text x='{bx+110}' y='{by-60}' {FONT} font-size='11' fill='{INK}'>edge-on tension tapes</text>")
    # plug and spine and ship
    el.append(f"<polygon points='{bx+100},{by} {bx+130},{by-9} {bx+130},{by+9}' fill='{SER[7]}'/>")
    el.append(f"<text x='{bx+90}' y='{by+30}' {FONT} font-size='11' fill='{INK}'>shadow plug (self-radiating)</text>")
    el.append(f"<line x1='{bx+130}' y1='{by}' x2='840' y2='{by}' stroke='{INK2}' stroke-width='3'/>")
    el.append(f"<path d='M{bx+130},{by-9} L840,{by-30} L840,{by+30} L{bx+130},{by+9} Z' fill='{INK2}' fill-opacity='0.08'/>")
    el.append(f"<text x='420' y='{by+48}' {FONT} font-size='11' fill='{INK}'>spine inside the plug's shadow cone</text>")
    el.append(f"<rect x='840' y='{by-30}' width='40' height='60' rx='4' fill='{SER[0]}'/>")
    el.append(f"<text x='880' y='{by+48}' text-anchor='end' {FONT} font-size='11' fill='{INK}'>ship, ~2 km forward</text>")
    el.append(f"<circle cx='{bx}' cy='{by}' r='7' fill='{SER[1]}' stroke='{BG}' stroke-width='2'/>")
    el.append(f"<text x='{bx-10}' y='{by-16}' text-anchor='end' {FONT} font-size='11' fill='{INK}'>burn</text>")
    rec = R['F_recommended']['engine']['params']
    el.append(f"<text x='20' y='{h-40}' {FONT} font-size='11' fill='{INK2}'>Recommended point (V2 source): ring R {rec['R_m']:.0f} m, burn {rec['burn_aft_m']:.0f} m aft of it, {rec['I_MA']:.0f} MA, "
              f"ribbon {rec['thickness_m']*100:.1f} cm, nose {rec['nose_m']:.2f} m; ship 2 km, engines 2 km apart.</text>")
    el.append(f"<text x='20' y='{h-22}' {FONT} font-size='11' fill='{INK2}'>Heat, four engines: {R['F_recommended']['sensitivity'][0]['total_four_GW']:.1f} GW of the 10.8 GW drive share; "
              f"mass about {R['F_recommended']['sensitivity'][0]['mass_t']:.0f} t per engine (magnet-driven, does not close).</text>")
    (OUT/'fig6_concept_F.svg').write_text(f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 {w} {h}' width='{w}' height='{h}' role='img'>"
                                         "<title>Schematic of the edge-on remote ring concept</title>"+''.join(el)+'</svg>')


def fig7():
    """Why coatings fail on the drawn engine: incidence angles of the first hits vs the critical-angle band."""
    q = R['A_C_drawn_engine']['graze_deg_quantiles']
    w, h = 760, 230
    l, rr = 80, 40
    X = lambda d: l+math.log10(d/0.01)/math.log10(90/0.01)*(w-l-rr)
    el = [f"<rect width='{w}' height='{h}' fill='{BG}'/>",
          f"<text x='20' y='26' {FONT} font-size='16' font-weight='600' fill='{INK}'>The drawn engine is hit head-on, not at grazing angles</text>",
          f"<text x='20' y='46' {FONT} font-size='12' fill='{INK2}'>Grazing angle of the first hit of 16,384 rays through the 263 real part meshes (Vertex 1.5 trace).</text>"]
    tc_lo, tc_hi = math.degrees(0.0382e-3*10), math.degrees(8.27e-3)   # diamond 100 keV .. Ir 10 keV, in degrees
    el.append(f"<rect x='{X(0.01):.1f}' y='80' width='{X(tc_hi)-X(0.01):.1f}' height='60' rx='4' fill='{SER[2]}' fill-opacity='0.25'/>")
    el.append(f"<text x='{X(0.01)+6:.1f}' y='98' {FONT} font-size='11' fill='{INK}'>total reflection possible</text>")
    el.append(f"<text x='{X(0.01)+6:.1f}' y='114' {FONT} font-size='11' fill='{INK}'>(below θc, 10-100 keV)</text>")
    el.append(f"<rect x='{X(q['0.05']):.1f}' y='88' width='{X(q['0.5'])-X(q['0.05']):.1f}' height='44' rx='4' fill='{SER[1]}'/>")
    el.append(f"<line x1='{X(q['0.0']):.1f}' x2='{X(q['0.05']):.1f}' y1='110' y2='110' stroke='{SER[1]}' stroke-width='2'/>")
    el.append(f"<text x='{w-rr}' y='160' text-anchor='end' {FONT} font-size='11' fill='{INK}'>5 % of hits: {q['0.05']:.0f}°   median: {q['0.5']:.0f}°   lowest: {q['0.0']:.2f}°</text>")
    for d in (0.01, 0.1, 1, 10, 90):
        el.append(f"<text x='{X(d):.1f}' y='{h-30}' text-anchor='middle' {FONT} font-size='11' fill='{INK2}'>{d:g}°</text>")
    el.append(f"<text x='{(w)/2}' y='{h-10}' text-anchor='middle' {FONT} font-size='12' fill='{INK2}'>grazing angle (log)</text>")
    (OUT/'fig7_drawn_engine_incidence.svg').write_text(f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 {w} {h}' width='{w}' height='{h}' role='img'>"
                                                      "<title>Incidence angles on the drawn engine versus the total-reflection band</title>"+''.join(el)+'</svg>')


if __name__ == '__main__':
    for f in (fig1, fig2, fig3, fig4, fig5, fig6, fig7):
        f()
    print('wrote', sorted(p.name for p in OUT.glob('*.svg')))
