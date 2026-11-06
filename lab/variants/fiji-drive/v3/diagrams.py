"""SVG diagrams for the Fiji Drive v3 report (energy flow of IFD-1, interfaces and plumbing). Pure Python; PNGs via Chromium (playwright).
  python3 lab/variants/fiji-drive/v3/diagrams.py --png
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
R = json.loads((HERE/'results/integrated.json').read_text()); DP = R['design_point']['central']; P = DP['P_fus_TW']*1e3  # GW
COL = {'prop': '#DB29C2', 'hot': '#DB1F1A', 'h2': '#2452EB', 'd': '#058F85', 'he3': '#8F4DE0', 'power': '#45389E', 'struct': '#8F8F94',
       'escape': '#B8B8A0', 'text': '#111', 'bg': '#FAFAF7'}


def box(x, y, w, h, title, sub, col, fill='#fff'):
    return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" fill="{fill}" stroke="{col}" stroke-width="3"/>'
            f'<text x="{x+w/2}" y="{y+24}" text-anchor="middle" font-weight="700" font-size="16">{title}</text>'
            + ''.join(f'<text x="{x+w/2}" y="{y+46+18*i}" text-anchor="middle" font-size="13">{s}</text>' for i, s in enumerate(sub)))


def arrow(x1, y1, x2, y2, col, w, label='', lx=None, ly=None, dash=''):
    d = f' stroke-dasharray="{dash}"' if dash else ''
    s = f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{col}" stroke-width="{max(1.5, w)}" marker-end="url(#a)"{d}/>'
    if label:
        s += f'<text x="{lx if lx is not None else (x1+x2)/2+6}" y="{ly if ly is not None else (y1+y2)/2-6}" font-size="13" fill="{col}" font-weight="600">{label}</text>'
    return s


def svg(w, h, body, title):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" font-family="DejaVu Sans, Arial">'
            f'<defs><marker id="a" markerUnits="userSpaceOnUse" markerWidth="14" markerHeight="14" refX="12" refY="5" orient="auto"><path d="M0,0 L13,5 L0,10 z" fill="#333"/></marker></defs>'
            f'<rect width="{w}" height="{h}" fill="{COL["bg"]}"/><text x="20" y="34" font-size="22" font-weight="700">{title}</text>{body}</svg>')


def energy_flow():
    L = DP['ledger_GW']; g = lambda k: [v for kk, v in L.items() if kk.startswith(k)][0]
    ex, nz, sy = g('directed exhaust'), g('nozzle divergence'), g('synchrotron')
    br, ne = g('bremsstrahlung escaping'), g('neutrons escaping')
    ar, sh = g('neutral radiation into coil'), g('neutral radiation into the shadow')
    ch = ex+nz
    b = []
    b.append(box(40, 70, 230, 90, 'D + He-3 fuel', [f'{R["channels"]["central"]["he3_to_d"]:.0f}:1, Ti = Te = 100 keV', 'axial fueller (shield sleeves)'], COL['d']))
    b.append(box(330, 70, 300, 90, 'Fiji-confined reaction zone', [f'{P:.0f} GW fusion, r {DP["r_plasma_m"]:.0f} m x {DP["L_m"]:.0f} m', f'B {DP["field_T"]:.1f} T (lattice ~1.5x), {DP["power_density_MW_m3"]:.0f} MW/m3'], COL['prop']))
    b.append(arrow(270, 115, 328, 115, COL['d'], 3))
    # three carriers
    b.append(box(40, 250, 260, 90, 'Charged products', [f'{ch:.0f} GW  (p 14.7 MeV, alpha 3.7 MeV)', 'Fiji field: steered, not stopped'], COL['prop']))
    b.append(box(360, 250, 260, 90, 'Photons', [f'brems {br/DP["fractions"]["escape"]:.0f} GW GW, synchrotron {sy:.0f} GW net', 'straight lines; no field steers them'], '#777'))
    b.append(box(680, 250, 260, 90, 'Neutrons (D-D 2.45 MeV)', [f'{ne/DP["fractions"]["escape"]:.1f} GW emitted', 'tritium exhausted (canon)'], '#777'))
    b.append(arrow(420, 160, 170, 248, COL['prop'], 6, f'{ch/P*100:.0f} %', 250, 210))
    b.append(arrow(480, 160, 490, 248, '#777', 3, f'{(br/DP["fractions"]["escape"]+sy)/P*100:.0f} %', 495, 210))
    b.append(arrow(560, 160, 800, 248, '#777', 2, f'{ne/DP["fractions"]["escape"]/P*100:.1f} %', 690, 200))
    # sinks
    b.append(box(40, 430, 260, 110, 'Magnetic nozzle (1 axial)', [f'{ex:.0f} GW directed exhaust', f'thrust {DP["thrust_kN"]:.1f} kN at ve 19,201 km/s', f'H2 mass loading {DP["mass_flow_g_s"]:.2f} g/s', f'{nz:.0f} GW divergence loss (aft)'], COL['h2']))
    b.append(box(360, 430, 300, 110, 'Escape to space (no ship heat)', [f'brems {br:.0f} GW + neutrons {ne:.1f} GW', f'through the 75 % coil gaps and aft', f'synchrotron {sy:.0f} GW (net of 0.98 reflection)', f'{DP["fractions"]["escape"]*100:.0f} % of neutral radiation'], COL['escape']))
    b.append(box(700, 430, 280, 110, 'Permanent hardware', [f'coil armour {ar:.1f} GW (W on Li heat pipes)', f'shadow shield {sh:.2f} GW', f'= {DP["hot_loop_GW"]:.1f} GW into the hot loop', f'peak wall {DP["wall_MW_m2"]:.0f} MW/m2 (limit)'], COL['hot']))
    b.append(arrow(170, 340, 170, 428, COL['prop'], 6))
    b.append(arrow(490, 340, 510, 428, '#777', 3)); b.append(arrow(810, 340, 560, 428, '#777', 2, '72 % escapes', 400, 395))
    b.append(arrow(520, 340, 760, 428, COL['hot'], 2, '28 % intercepted', 700, 372, '6,4')); b.append(arrow(830, 340, 840, 428, COL['hot'], 1.5, '', dash='6,4'))
    b.append(box(700, 610, 280, 100, 'Hot loop -> radiator blades', [f'{DP["hot_loop_GW"]:.1f} GW of {DP["hot_budget_GW"]:.1f} GW drive budget', '1800 K, 26,882 m2 effective', 'Li heat-pipe trunks to blade roots'], COL['hot']))
    b.append(arrow(840, 540, 840, 608, COL['hot'], 4))
    b.append(box(40, 610, 600, 100, 'Not available as an energy path (rejected in the register)', ['X-ray mirrors (2 theta_c < 1 deg), absorber-to-exhaust routing (pressure 10^5x the 150 T field),',
                                                                                                    f'propellant regenerative cooling ({R["absorbers"]["regenerative_cooling"]["capacity_GW"]:.2f} GW for the whole 261 TW-class H2 flow),',
                                                                                                    'expendable ablation (10^4-10^6 kg/s per TW)'], '#999', '#f0f0f0'))
    b.append(f'<text x="20" y="745" font-size="13">Ledger sums to {DP["ledger_sum"]:.3f} of gross fusion power; every joule counted once (results/integrated.json design_point.central).</text>')
    return svg(1020, 760, ''.join(b), f'IFD-1 energy flow at the closed design point ({P:.0f} GW fusion, central case)')


def interfaces():
    b = []
    rows = [('Forward ship', 'tank farm, rings, EYE', COL['struct'], 40), ('Hull aft body', 'primary frames, rails', COL['struct'], 250),
            ('Shadow shield', 'W|B4C|LiH|steel, r 7.2 m', COL['prop'], 460), ('Open-cage core', '16 coils, 1.4 m shield', COL['prop'], 670),
            ('Axial nozzle', '6 coils, 4 trim sectors', COL['prop'], 880)]
    for t, s, c, x in rows:
        b.append(box(x, 90, 200, 70, t, [s], c))
    for i in range(4):
        b.append(arrow(rows[i+1][3]-2, 125, rows[i][3]+202, 125, COL['struct'], 3))
    b.append('<text x="40" y="190" font-size="13" fill="#555">thrust path: nozzle coils -> strongback -> shield ring frame -> hull primary frames (arrows point forward, toward +X)</text>')
    lines = [(COL['h2'], 'H2 (HYDROGEN)', 'tank farm -> axial feed -> forward gas box (edge mass loading) + nozzle mass-loading ring', 220),
             (COL['d'], 'D (DEUTERIUM)', 'tank farm -> shield sleeve -> axial fueller (pellet/gas), metered separately', 255),
             (COL['he3'], 'He-3 (HELIUM3)', 'tank farm -> shield sleeve -> axial fueller; unburned He-3 leaves in the exhaust', 290),
             (COL['hot'], 'Hot loop (HOT_RADIATOR)', 'coil armour (Li heat pipes, ~1850 K) + shield W face -> 3 trunks in the blade planes -> blade roots, 1800 K', 325),
             (COL['power'], 'Power (POWER)', 'Brayton A/B + pulse bank -> coil power bus -> 4 coil power units; seed field before lattice activation', 360),
             ('#777', 'Diagnostics / control', 'field probes per coil, bolometers, neutron spectrometer behind the shield, nozzle trim feedback', 395)]
    for c, t, s, y in lines:
        b.append(f'<rect x="40" y="{y-16}" width="22" height="22" fill="{c}"/><text x="72" y="{y}" font-size="15" font-weight="700">{t}</text>'
                 f'<text x="300" y="{y}" font-size="14">{s}</text>')
    seq = ['STARTUP: seed field 5 T on (power bus) -> lattice heated through 650 K activation to ~700 K -> Li heat pipes primed, W armour at temperature',
           '-> H2 gas box and NBI/ICRF heating -> D/He-3 fuelling -> burn; nozzle trim closes the loop on thrust axis',
           'SHUTDOWN: fuel off -> plasma decays (s) -> field stepped down through the dump resistors (canon shutdown law) -> lattice cooled below 550 K release',
           'FAULTS: armour over-temperature or heat-pipe loss -> fuel cut within the plasma energy time; coil quench -> sector isolation, field dump;',
           'shield loop loss -> burn stop (shield holds ~minutes of heat capacity); H2 loss -> gas box off, burn stop; one nozzle sector out -> trim 1-2 deg']
    for i, s in enumerate(seq):
        b.append(f'<text x="40" y="{450+i*24}" font-size="13">{s}</text>')
    return svg(1110, 590, ''.join(b), 'IFD-1 interfaces, plumbing, startup and fault isolation')


def main():
    out = HERE/'diagrams'; out.mkdir(exist_ok=True)
    for name, s in (('energy_flow', energy_flow()), ('interfaces', interfaces())):
        (out/f'{name}.svg').write_text(s)
    if '--png' in sys.argv:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            b = p.chromium.launch(); pg = b.new_page(device_scale_factor=2)
            for name in ('energy_flow', 'interfaces'):
                pg.goto((out/f'{name}.svg').as_uri()); pg.screenshot(path=str(out/f'{name}.png'), full_page=True)
            b.close()
    print('WF_DIAGRAMS', out)


if __name__ == '__main__':
    main()
