"""PSA Phase II mass ledger (D02, D04, D05, section 10), coupled mission mass and supply scenarios (D07).

Reads results/p2_variants.json (study.py) and writes results/p2_ledger.json. Every line is an explicitly sized part (correction 3.7):
FE member families, FE node fittings, and three hand-sized parts the global model does not carry (protective casing, rotating ring
structure, spine pressure liner). STUDY / NONCANON; the 150 t main-structure line stays the reference (D02).
"""
import json
import math
import sys
from pathlib import Path

H = Path(__file__).resolve().parent
sys.path.insert(0, str(H))
import configs  # noqa: E402
import model as mdl  # noqa: E402

OUT = H.parent / 'results'
REF_LINE_T = 150.0

FAMILY_ITEM = {
    'ring': 'thrust ring, transition and drive pickups', 'trans': 'thrust ring, transition and drive pickups', 'pickup': 'thrust ring, transition and drive pickups',
    'rail': 'longerons (rails)', 'frame': 'frames (4 m)', 'modframe': 'module frames (L3 joints)', 'diag': 'diagonals (shear and torsion)',
    'tie': 'spine ties and axial datum', 'cone': 'spine ties and axial datum', 'hubcone': 'rotor-bay hub path (cones)',
    'spine': 'Momentum Spine structural shell', 'hub': 'Momentum Spine structural shell', 'collar': 'rotor-bay collar (Q45 bypass)',
    'keel': 'forward keels to the Brow', 'deck': 'common thrust deck (tank-farm aft)',
}

# ---- ownership (D04, D05): one explicit owner per item ------------------------------------------------------------------------
OWNERS = [
    ('longerons, frames, module frames, diagonals', 'PSA', 'primary load path'),
    ('thrust ring, transition, pickups to the nozzle yoke', 'PSA', 'drive owns the nozzle yoke and cage; PSA owns the struts from the yoke lug outward'),
    ('common thrust deck (tank-farm aft fixity) and the farm forward ring', 'PSA', 'D04: common decks and major frames are PSA'),
    ('tank shells, insulation, internal structure (baffles, slosh), tank cradles and skirts, tank mounts (V-links), containment', 'Tankage budget', 'D04: tankage has its own budget; PSA provides the deck hard-points and V-link lugs'),
    ('V-link lugs on the deck (structure side of the tank mount)', 'PSA', 'shared item: the lug is PSA, the link and its tank fitting are tankage'),
    ('Momentum Spine structural shell (load-bearing tube, ties, axial datum)', 'PSA', 'D05'),
    ('spine pressure liner and its seals (crew transit tube)', 'Habitat / crew transfer', 'D05 option B: pressure-retaining liner separate from the load-bearing shell; the liner hangs on the shell, carries pressure hoop only'),
    ('spine utilities (power, data, coolant, ducts, rails)', 'their subsystems (ISSA)', 'D05'),
    ('rotor-bay collar or hub path', 'PSA', 'primary path around or through the rotor'),
    ('rotating ring structure (rim, spokes, bearing races)', 'PSA (rotating structure)', 'correction 3.7 sized explicitly; habitat pressure structure stays habitat-owned'),
    ('protective casing (Whipple and MLI carrier)', 'PSA (secondary structure)', 'carried by frames; protection layers are ISSA PROT'),
    ('Brow truss and forward shield carrier', 'Forward defense', 'PSA ends at the keel-to-Brow interface ring'),
    ('radiator backbone and blade roots', 'Thermal (with PSA frame interface)', 'section 3.6 trade; PSA owns the frame lugs'),
    ('hot-loop saddles and anchors', 'ISSA (TMS)', 'PSA owns the frame hard-points and their reactions'),
    ('MRU carriage rail', 'ISSA (logistics)', 'PSA owns the lugs'),
]


def casing_t(length=229.0, r=6.0):
    """Protective casing: 0.8 mm Al 5083 skin on Z-stringers at 0.5 m plus clips; 2.6 kg/m2 structural (protection layers excluded)."""
    area = 2*math.pi*r*length; return area*2.6/1e3, area


def rotating_t(ring_mass_t, a_axial=7.2, r=30.0, g=9.81):
    """Rotating ring structure: rim hoop for the spin load, radial spokes for 1 g, axial bracing (stays) for the burn
    acceleration with the rings spun, bearing races. Ultimate 1.4, Al 6061 design values; stays sized on tension; spokes on
    column buckling with 6 spokes of 30 m (L/r <= 120)."""
    al = mdl.mat('AL6061'); v2 = g*r; mprime = ring_mass_t*1e3/(2*math.pi*r)
    hoop = 1.4*mprime*v2/al['Ft']*2*math.pi*r*al['rho']
    spokes_A = 1.4*ring_mass_t*1e3*g/al['Ft']; spoke_min = 6*math.pi*0.25**2*0.25*0.02  # minimum 6 x (r 0.25 m, t 5 mm) column
    spokes = max(spokes_A, 6*2*math.pi*0.25*0.005)*r*al['rho']
    stays = 1.4*ring_mass_t*1e3*a_axial/al['Ft']/math.sin(math.radians(20))*r/math.cos(math.radians(20))*al['rho']
    races = 0.035*ring_mass_t*1e3
    return dict(hoop_t=hoop/1e3, spokes_t=spokes/1e3, stays_t=stays/1e3, races_t=races/1e3, total_t=(hoop+spokes+stays+races)/1e3)


def spine_liner_t(L=208.3, r=0.9, p=101e3):
    """Spine pressure liner (habitat-owned, D05): Al 5083, hoop stress at 1.4 x 2 x MEOP / Fty, minimum 2 mm; seals and flanges 15 %."""
    al = mdl.mat('AL5083'); t = max(1.4*2*p*r/al['Fy'], 0.002); return 2*math.pi*r*t*L*al['rho']*1.15/1e3, t


def coupling(cfg):
    """dDeparture/dDry at fixed delta-v with tankage proportional to propellant: 1 + (1+k)(R-1)/(1-k(R-1)) with R = departure/end."""
    if cfg == 'F1':
        led = configs.issa('i3d_ledger.json'); dep, prop, tank = led['departure_t'], led['propellant_t'], led['tankage_t']
        issa_c = led.get('coupling')
    elif cfg == 'R':
        p6 = configs.issa('phase6.json', '5eae701'); c = p6['configs']['R']; dep = c['mass']['departure_t'][1]; prop = c['mass']['propellant_t'][1]
        tank = configs.config('R')['tankage_derived_t']; issa_c = None
    else:
        st = configs.config('P'); dep = sum(p['m'] for p in st['parts'])/1e3+150.0; prop = st['propellant_full_t']; tank = 329.5; issa_c = None
    R = dep/(dep-prop); k = tank/prop
    return dict(R=R, k=k, coupling=1+(1+k)*(R-1)/(1-k*(R-1)), issa_coupling=issa_c, departure_t=dep)


# ---- supply (D07) --------------------------------------------------------------------------------------------------------------
# imported mass per kg of finished material by category, per scenario: lunar-first / balanced / performance-first. Carbon from
# terrestrial supply; asteroid carbon is a separate sensitivity (not assumed mature). Fractions are PROTOTYPE judgements with the
# alloy chemistry as their basis (6061: Cu 0.15-0.4 %, Cr 0.04-0.35 %; 5083: Mn 0.4-1.0 %, Cr 0.05-0.25 %; Ti-6Al-4V: V 4 %).
CATS = ['carbon fibres', 'polymer matrices', 'alloying elements', 'specialty metals', 'ceramic precursors', 'manufacturing consumables', 'finished specialist components']
SUPPLY = {
    'AL6061':   {'lunar-first': {'alloying elements': 0.006}, 'balanced': {'alloying elements': 0.006}, 'performance-first': {'alloying elements': 0.006, 'specialty metals': 0.0}},
    'AL5083':   {'lunar-first': {'alloying elements': 0.010}, 'balanced': {'alloying elements': 0.010}, 'performance-first': {'alloying elements': 0.010}},
    'TI64':     {'lunar-first': {'alloying elements': 0.040}, 'balanced': {'alloying elements': 0.040}, 'performance-first': {'alloying elements': 0.040, 'specialty metals': 0.96}},
    'ALAL2O3F': {'lunar-first': {'ceramic precursors': 0.03}, 'balanced': {'ceramic precursors': 0.03, 'alloying elements': 0.003},
                 'performance-first': {'ceramic precursors': 0.0, 'finished specialist components': 0.58}},
    'CFPEEK':   {'lunar-first': {'carbon fibres': 0.60, 'polymer matrices': 0.40}, 'balanced': {'carbon fibres': 0.60, 'polymer matrices': 0.40},
                 'performance-first': {'carbon fibres': 0.60, 'polymer matrices': 0.40}},
}
CONSUMABLES = {'lunar-first': 0.02, 'balanced': 0.02, 'performance-first': 0.03}     # per kg of structure: FSW tools, filler, argon, bagging
SPECIALIST = {'lunar-first': 0.03, 'balanced': 0.03, 'performance-first': 0.05}      # per kg of joints: high-strength fasteners, bearings, FBG/AE sensors


def imports(v, scen):
    by = {c: 0.0 for c in CATS}; longeron = {c: 0.0 for c in CATS}; long_mass = 0.0
    for g, s in v['sizing'].items():
        fr = SUPPLY.get(s['mat'], {}).get(scen, {})
        for c, f in fr.items():
            by[c] += f*s['mass_t']
            if g.startswith('rail'):
                longeron[c] += f*s['mass_t']
        if g.startswith('rail'):
            long_mass += s['mass_t']
    by['manufacturing consumables'] += CONSUMABLES[scen]*v['members_t']
    by['finished specialist components'] += SPECIALIST[scen]*v['joints_t']
    ti_j = v['joints_t']; by['alloying elements'] += 0.04*ti_j
    if scen == 'performance-first':
        by['specialty metals'] += 0.96*ti_j
    tot = sum(by.values())
    return dict(by_category_t=by, total_t=tot, structure_fraction=tot/v['structure_t'], longeron_fraction=sum(longeron.values())/max(long_mass, 1e-9),
                whole_ship_fraction_psa_only=tot/v['departure_t'])


def main():
    V = json.loads((OUT / 'p2_variants.json').read_text())
    ringm = 45.0+27.5+80.0+20.1
    rot = rotating_t(ringm); cas, area = casing_t(); liner, tl = spine_liner_t()
    out = dict(reference_line_t=REF_LINE_T, owners=OWNERS, hand_sized=dict(casing_t=cas, casing_area_m2=area, rotating_per_ring=rot, rings=2,
               spine_liner_t=liner, spine_liner_t_mm=tl*1e3), variants={}, coupling={c: coupling(c) for c in ('P', 'F1', 'R')})
    for k, v in V.items():
        items = {}
        for fam, m in v['by_family_t'].items():
            it = FAMILY_ITEM.get(fam, fam); items[it] = items.get(it, 0.0)+m
        items['node fittings and joints (explicit, Ti-6Al-4V)'] = v['joints_t']
        items['protective casing (secondary)'] = cas
        items['rotating ring structure (2 rings)'] = 2*rot['total_t']
        psa = sum(items.values())
        c = out['coupling'][v['config']]
        # allowable uncertainty: strength-governed sizing scales with 1/F; low / high design values from allowables.toml
        lo = hi = 0.0
        for g, s in v['sizing'].items():
            m = mdl.MATS[s['mat']]; Fc = m['Fcy']; lo += s['mass_t']*(Fc[1]/Fc[0]-1); hi += s['mass_t']*(Fc[1]/Fc[2]-1)
        dline = psa-REF_LINE_T
        dep_delta = c['coupling']*dline
        out['variants'][k] = dict(items_t=items, psa_total_t=psa, delta_vs_line_t=dline, coupled_departure_delta_t=dep_delta,
                                  coupled_departure_t=c['departure_t']+dep_delta, uncertainty_t=dict(low_allowables=lo, high_allowables=hi),
                                  imports={s: imports(v, s) for s in ('lunar-first', 'balanced', 'performance-first')},
                                  failing_groups=v['failing'], config=v['config'], concept=v['concept'], rotor=v['rotor'])
    (OUT / 'p2_ledger.json').write_text(json.dumps(out, indent=1, default=float))
    for k, v in out['variants'].items():
        print(f"{k:<16} PSA {v['psa_total_t']:7.1f} t  vs line {v['delta_vs_line_t']:+7.1f}  departure {v['coupled_departure_delta_t']:+7.0f} t  "
              f"imports LF {v['imports']['lunar-first']['total_t']:.1f} / BAL {v['imports']['balanced']['total_t']:.1f} / PF {v['imports']['performance-first']['total_t']:.1f} t")
    print('coupling', {k: round(v['coupling'], 3) for k, v in out['coupling'].items()}, 'rot/ring', round(rot['total_t'], 1), 'casing', round(cas, 1), 'liner', round(liner, 1))


if __name__ == '__main__':
    main()
