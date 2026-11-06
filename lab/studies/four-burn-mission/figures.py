"""Figures for the four-burn report (matplotlib; reads results/results.json): python3 figures.py"""
import json
import math
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt                                        # noqa: E402
from matplotlib.patches import Circle, Rectangle, FancyArrowPatch, Wedge  # noqa: E402

HERE = Path(__file__).resolve().parent; FIG = HERE/'figures'
R = json.loads((HERE/'results/results.json').read_text())
COL = {'IFD-C': '#2a78d6', 'IFD-CH': '#eb6834', 'IFD-P': '#1baf7a', 'IFD-PH': '#6250d6', 'CANON': '#52514e'}
TIER_LS = {'optimistic': '-', 'central': '--', 'pessimistic': ':'}
INK = '#0b0b0b'; INK2 = '#52514e'; GRID = '#e4e3df'
plt.rcParams.update({'font.size': 10, 'axes.edgecolor': INK2, 'axes.labelcolor': INK, 'xtick.color': INK2, 'ytick.color': INK2,
                     'axes.spines.top': False, 'axes.spines.right': False, 'figure.facecolor': '#fcfcfb', 'axes.facecolor': '#fcfcfb',
                     'axes.grid': True, 'grid.color': GRID, 'grid.linewidth': 0.6, 'legend.frameon': False})


def save(fig, name):
    fig.tight_layout(); fig.savefig(FIG/f'{name}.png', dpi=160); plt.close(fig)


def accel_time():
    A = R['matrix_A']; x = [r['accel_g'] for r in A]
    fig, ax = plt.subplots(1, 2, figsize=(11, 4.2))
    ax[0].loglog(x, [r['four_burn_days'] for r in A], color=COL['IFD-C'], lw=2, marker='o', ms=5)
    for yv, lab in ((365.25, '1 year'), (3652.5, '10 years')):
        ax[0].axhline(yv, color=INK2, lw=0.8, ls=':'); ax[0].text(x[0], yv*1.1, lab, color=INK2, fontsize=8)
    ax[0].set_xlabel('Constant acceleration (g)'); ax[0].set_ylabel('Time under thrust, four burns (days)')
    ax[0].set_title('Four 0.016 c burns: thrust time', loc='left', fontsize=11)
    ax[1].loglog(x, [r['min_destination_AU'] for r in A], color=COL['IFD-CH'], lw=2, marker='o', ms=5)
    ax[1].axhline(63241, color=INK2, lw=0.8, ls=':'); ax[1].text(x[0], 63241*1.15, '1 light year', color=INK2, fontsize=8)
    ax[1].set_xlabel('Constant acceleration (g)'); ax[1].set_ylabel('Shortest full-stop destination (AU)')
    ax[1].set_title('Destination must be at least this far', loc='left', fontsize=11)
    save(fig, 'A_accel_time')


def ve_propellant():
    rows = R['matrix_B']['existing_final_1629t']
    fig, ax = plt.subplots(figsize=(7.5, 4.4))
    v = [r['ve_km_s'] for r in rows]
    ax.semilogy(v, [r['departure_t_fixed_end'] for r in rows], color=COL['IFD-C'], lw=2, marker='o', ms=5, label='end mass fixed at 1,629 t')
    vv = [r['ve_km_s'] for r in rows if r['departure_t_with_tanks']]
    ax.semilogy(vv, [r['departure_t_with_tanks'] for r in rows if r['departure_t_with_tanks']], color=COL['IFD-CH'], lw=2, marker='o', ms=5,
                label='tanks grow with propellant (0.15 kg/kg)')
    ax.axvline(19201, color=INK2, lw=0.8, ls=':'); ax.text(19400, 2e3, 'canon ve', color=INK2, fontsize=8)
    ax.set_xlabel('Effective exhaust velocity (km/s)'); ax.set_ylabel('Departure mass (t)')
    ax.set_title('Four-burn departure mass versus exhaust velocity', loc='left', fontsize=11); ax.legend(fontsize=8)
    save(fig, 'B_ve_propellant')


def pareto():
    fig, ax = plt.subplots(figsize=(9, 5.6))
    for k, v in R['existing_payload'].items():
        a, t = k.split('/')
        if not v['front']:
            continue
        xs = [p['burn_time_years'] for p in v['front']]; ys = [p['departure_t'] for p in v['front']]
        ax.loglog(xs, ys, color=COL[a], ls=TIER_LS[t], lw=2, marker='o', ms=4, label=f'{a} {t}')
    ax.scatter([29/365.25], [4426], color=COL['CANON'], marker='s', s=50, zorder=5)
    ax.annotate('canon working point\n(261 TW, unsupported)', (29/365.25, 4426), xytext=(0.15, 1500), fontsize=8, color=INK2,
                arrowprops=dict(arrowstyle='-', color=INK2, lw=0.8))
    ax.axvline(4*0.016*299792458/9.80665/3.15576e7, color=INK2, lw=0.8, ls=':')
    ax.text(4*0.016*299792458/9.80665/3.15576e7*1.1, 2.5e5, 'four burns\nat 1 g', color=INK2, fontsize=8)
    ax.set_xlabel('Time under thrust, four burns (years)'); ax.set_ylabel('Departure mass (t)')
    ax.set_title('Pareto fronts: shortest burn time for each departure mass (860 t payload)', loc='left', fontsize=11)
    ax.legend(fontsize=8, ncol=2, loc='upper left', bbox_to_anchor=(0.2, 0.98)); ax.set_xlim(0.02, 3000)
    save(fig, 'C_pareto')


def energy_flow():
    keys = ['IFD-C/central', 'IFD-CH/central', 'IFD-P/central', 'IFD-PH/central', 'IFD-PH/optimistic', 'CANON/central']
    cats = [('jet', 'directed jet', '#2a78d6'), ('space', 'plume and radiation to space', '#c3c2b7'),
            ('hot', 'hot-loop heat (1,800 K)', '#eb6834'), ('warm', 'warm heat (driver, electronics, cryo)', '#e87ba4')]
    fig, ax = plt.subplots(figsize=(9, 4.4))
    for i, k in enumerate(keys):
        A = R['architectures_at_10TW'][k]; L = A['ledger']
        jet = L['jet']; hot = A['heat']['hot']; warm = A['heat']['warm']; space = 1-jet-hot-warm
        vals = {'jet': jet, 'space': space, 'hot': hot, 'warm': warm}; left = 0
        for c, lab, col in cats:
            ax.barh(i, vals[c], left=left, color=col, edgecolor='#fcfcfb', lw=1.5, label=lab if i == 0 else None)
            left += vals[c]
        ax.text(1.01, i, f"heat {100*(hot+warm):.2f} %", va='center', fontsize=8, color=INK2)
    ax.set_yticks(range(len(keys))); ax.set_yticklabels([k.replace('/', ' ') for k in keys]); ax.invert_yaxis()
    ax.set_xlim(0, 1.12); ax.set_xlabel('Share of gross fusion power (10 TW design point)')
    ax.set_title('Where the fusion energy goes', loc='left', fontsize=11); ax.legend(fontsize=8, ncol=2, loc='lower center', bbox_to_anchor=(0.45, -0.42))
    save(fig, 'D_energy_flow')


def mass_breakdown():
    D = R['designs']; keys = [k for k in ('CANON/central/1g', 'IFD-PH/optimistic/cap10kt', 'IFD-P/optimistic/cap10kt', 'IFD-CH/optimistic/cap10kt',
                                          'IFD-C/optimistic/cap10kt', 'IFD-PH/central/cap30kt', 'IFD-PH/optimistic/cap30kt') if D.get(k)]
    parts = [('payload', 'payload (crew ship)', '#52514e'), ('drive_t', 'drive', '#2a78d6'), ('radiator_t', 'radiators', '#eb6834'),
             ('tank_t', 'tanks', '#1baf7a'), ('reserve_t', 'reserve and allowances', '#eda100'), ('propellant_t', 'propellant', '#6250d6')]
    fig, ax = plt.subplots(figsize=(10, 4.8))
    for i, k in enumerate(keys):
        d = D[k]; vals = dict(d); vals['payload'] = d['dry_t']-d['drive_t']-d['radiator_t']-d['tank_t']; left = 0
        for key, lab, col in parts:
            ax.barh(i, vals[key], left=left, color=col, edgecolor='#fcfcfb', lw=1.5, label=lab if i == 0 else None); left += vals[key]
        ax.text(left*1.01+50, i, f"{d['burn_time_years']:.2g} y at {d['a0_g']:.2g} g", va='center', fontsize=8, color=INK2)
    ax.set_yticks(range(len(keys))); ax.set_yticklabels([k.replace('/cap', ' cap ').replace('/', ' ') for k in keys]); ax.invert_yaxis()
    ax.set_xlabel('Departure mass (t)'); ax.set_title('Closed designs: what the departure mass is made of', loc='left', fontsize=11)
    ax.legend(fontsize=8, ncol=3, loc='lower center', bbox_to_anchor=(0.5, -0.38))
    save(fig, 'E_mass_breakdown')


def alpha_gap():
    rows = [r for r in R['one_g'] if abs(r['ve_km_s']-19201.172) < 1 or (r['arch'] in ('IFD-C', 'IFD-CH') and r['ve_km_s'] == 13000)]
    seen = {}
    for r in R['one_g']:
        k = (r['arch'], r['tier'])
        if r['alpha_jet_kg_per_W'] and (k not in seen or r['ve_km_s'] == 16000):
            seen[k] = r
    fig, ax = plt.subplots(figsize=(9, 4.6))
    ks = [k for k in seen if k[1] != 'pessimistic']
    for i, k in enumerate(ks):
        ax.barh(i, seen[k]['alpha_jet_kg_per_W'], color=COL[k[0]], edgecolor='#fcfcfb')
    need = seen[ks[0]]['alpha_needed_zero_payload_kg_per_W']
    for g, ls in ((1.0, '-'), (0.01, '--'), (0.001, ':')):
        ax.axvline(need/g, color=INK, lw=1, ls=ls); ax.text(need/g*1.1, len(ks)-0.4, f'{g:g} g', fontsize=8, color=INK)
    ax.set_xscale('log'); ax.set_yticks(range(len(ks))); ax.set_yticklabels([f'{a} {t}' for a, t in ks]); ax.invert_yaxis()
    ax.set_xlabel('Propulsion specific mass, drive + radiators (kg per W of jet power)')
    ax.set_title('How far each drive is from the acceleration it would need (ve 16,000 km/s, zero payload)', loc='left', fontsize=10)
    save(fig, 'F_specific_mass_gap')


def tanks_fig():
    rows = R['matrix_D']; sp = ('helium_3', 'deuterium', 'hydrogen'); cols = ('#6250d6', '#1baf7a', '#2a78d6')
    fig, ax = plt.subplots(figsize=(10, 4.4)); w = 0.25
    for j, s in enumerate(sp):
        ax.bar([i+(j-1)*w for i in range(len(rows))], [r['ratio'][s] for r in rows], w*0.92, color=cols[j], label=s.replace('_', '-'))
    ax.axhline(1, color=INK, lw=1); ax.text(-0.45, 1.05, 'existing capacity', fontsize=8)
    ax.set_yscale('log'); ax.set_xticks(range(len(rows))); ax.set_xticklabels([r['config'].replace(' ve', '\nve') for r in rows], fontsize=7)
    ax.set_ylabel('Required / existing capacity'); ax.set_title('Tank need against the 13-vessel farm', loc='left', fontsize=11); ax.legend(fontsize=8)
    save(fig, 'G_tanks')


def tornado():
    for key, v in R['sensitivity'].items():
        if not v['base']:
            continue
        base = v['base']['burn_time_years']; rows = [r for r in v['rows'] if r.get('optimistic') or r.get('pessimistic')]
        def span(r):
            a = r.get('optimistic') or base; b = r.get('pessimistic') or base
            return abs(math.log(max(a, 1e-9)/base))+abs(math.log(max(b, 1e-9)/base))
        rows.sort(key=span, reverse=True); rows = rows[:12]
        fig, ax = plt.subplots(figsize=(8.5, 4.8))
        for i, r in enumerate(rows):
            for t, col in (('optimistic', '#2a78d6'), ('pessimistic', '#eb6834')):
                x = r.get(t)
                if x:
                    ax.barh(i, x/base-1 if x >= base else -(base/x-1), color=col, label=t if i == 0 else None)
                elif t in r:
                    ax.text(0.02, i, 'no closure', fontsize=7, color=INK2, va='center')
        ax.axvline(0, color=INK, lw=0.8); ax.set_yticks(range(len(rows))); ax.set_yticklabels([r['parameter'] for r in rows], fontsize=8)
        ax.invert_yaxis(); ax.set_xlabel(f'Change in four-burn time (fraction; base {base:.3g} y)')
        ax.set_title(f'Sensitivity: {key}', loc='left', fontsize=11); ax.legend(fontsize=8)
        save(fig, 'H_sensitivity_'+key.replace('/', '_'))


def concept():
    """IFD-PH concept to scale for the recommended design: ship, point burn, nozzle loops, driver beams."""
    d = R['designs'].get('IFD-PH/optimistic/cap10kt'); g = d['geometry']; Rs = g['standoff_m']
    fig, ax = plt.subplots(figsize=(11, 4.4)); ax.set_aspect('equal'); ax.grid(False)
    L = 289.5; ax.add_patch(Rectangle((0, -7), L, 14, color='#c3c2b7')); ax.text(L/2, 10, 'Wayfarer body 289.5 m (today)', ha='center', fontsize=8)
    ax.add_patch(Rectangle((L*0.25, -34), 40, 68, fill=False, ec='#52514e', lw=1)); ax.text(L*0.25+20, 37, 'tank farm', ha='center', fontsize=7)
    bx = -Rs*1.6
    ax.add_patch(Circle((bx, 0), 3, color='#eb6834')); ax.text(bx, -14, f"burn point: {g['yield_t_TNT']:.2g} t TNT\nevery {1/g['rep_Hz']:.3g} s", ha='center', fontsize=8)
    for ang in (-40, -15, 15, 40):
        a = math.radians(ang); ax.plot([bx+Rs*math.cos(math.pi-a)*0.98, bx+Rs*math.cos(math.pi-a)], [Rs*math.sin(a)*0.98, Rs*math.sin(a)], color='#6250d6')
    ax.add_patch(Wedge((bx, 0), Rs, -60, 60, width=Rs*0.05, color='#6250d6', alpha=0.6))
    ax.text(bx+Rs*0.55, Rs*0.95, f'Fiji nozzle loops, stand-off {Rs:.0f} m', fontsize=8, color='#6250d6')
    ax.add_patch(Rectangle((bx+Rs*1.02, -Rs*0.3), 6, Rs*0.6, color='#52514e')); ax.text(bx+Rs*1.05, -Rs*0.38, 'shadow shield', fontsize=7)
    ax.add_patch(FancyArrowPatch((bx-Rs*0.3, 0), (bx-Rs*1.3, 0), arrowstyle='-|>', mutation_scale=15, color='#2a78d6'))
    ax.text(bx-Rs*0.8, 6, f"exhaust {d['ve_km_s']:,.0f} km/s", ha='center', fontsize=8, color='#2a78d6')
    for y in (-Rs*0.25, Rs*0.25):
        ax.plot([0, bx], [y*0.2, 0], color='#1baf7a', lw=0.8, ls='--')
    ax.text(bx*0.5, Rs*0.12, 'driver beamlines', fontsize=7, color='#1baf7a')
    ax.set_xlim(bx-Rs*1.45, L+20); ax.set_ylim(-Rs*1.1, Rs*1.15); ax.set_xlabel('m (to scale)')
    ax.set_title('IFD-PH concept to scale: point burn aft, Fiji-amplified loops, tamper-captured X-rays', loc='left', fontsize=11)
    save(fig, 'I_concept_ifd_ph')


if __name__ == '__main__':
    FIG.mkdir(exist_ok=True)
    for fn in (accel_time, ve_propellant, pareto, energy_flow, mass_breakdown, alpha_gap, tanks_fig, tornado, concept):
        fn()
    print('figures written')
