"""ISSA Phase IV: physical closure (STUDY, NONCANON). Pure Python; reads the spec, references/p1_power_loads.json and the Phase II/III and
IV-B results; writes results/phase4.json.

    python3 work/ship-systems-architecture/phase3/study.py          (Phase III inputs)
    python3 work/ship-systems-architecture/phase4/study4.py

Class labels as before: MODEL-DERIVED, STUDY, PROTOTYPE, SPECULATIVE, OPEN, and TRANSPORT-INFORMED (uses the IV-B OpenMC results, 1-D,
not validated for Wayfarer). Bands are (low, nominal, high).
"""
import json
import math
import sys
import tomllib
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORK = HERE.parent
ROOT = WORK.parents[1]
R = WORK/'results'
sys.path.insert(0, str(ROOT/'src/wayfarer'))
sys.path.insert(0, str(WORK/'phase2'))
sys.path.insert(0, str(WORK/'phase3'))
sys.path.insert(0, str(HERE))
import spec  # noqa: E402
import operating_point as op  # noqa: E402
import mass_model  # noqa: E402
import radiator_zones as rz  # noqa: E402
import eps_b  # noqa: E402
import eps_g1  # noqa: E402
import mission as msn  # noqa: E402
import study as s3  # noqa: E402
from viewfactor import view_factor, R_IN, R_OUT, CASING_R  # noqa: E402

SIG = s3.SIG; EPS = s3.EPS; G0 = 9.80665; C = 299792458.0; AU = 1.495978707e11; DAY = 86400.0; YR = 365.25*DAY
B = (0, 1, 2); BANDS = ('low', 'nominal', 'high')
FACE_PER_M = s3.FACE_PER_M; MARGIN = s3.MARGIN
T_HOT = 1800.0; EPS_HOT = 0.9; ALPHA = 0.9
BULKHEAD_X = 50.4                       # graded bulkhead (WARM x0), MODEL-DERIVED from radiator_zones.placed
F_SPACE = 0.9                           # view factor to space of a blade face, as the hot-blade effective area uses (MODEL-DERIVED)


def r3(x, n=3):
    return [round(v, n) for v in x]


# ======================================================================== IV-A 3.1 one radiator relation =============================
def section(units_running, Pe, T_rej=550.0, standby_units=1, standby_frac=0.03, F_hot=0.0, f_space=F_SPACE, fin_eff=1.0, margin=MARGIN,
            eta=None, band=1, per_m=FACE_PER_M, load_frac=1.0):
    """The one relation Phase IV uses everywhere: installed capacity -> operating output -> efficiency -> waste heat (+ standby heat) ->
    net flux at temperature (emission to space minus absorption from the hot blades) -> effective area -> geometric area -> length.
    Pe is the rating per unit; load_frac the share of rating each running unit delivers."""
    eta = eta if eta is not None else eps_b.brayton_eff(T_rej, band)
    out_W = units_running*Pe*load_frac
    waste = out_W*(1/eta-1)+standby_units*Pe/eta*standby_frac
    emit = EPS*SIG*T_rej**4*f_space*fin_eff
    absorb = ALPHA*EPS_HOT*SIG*T_HOT**4*F_hot
    net = emit-absorb
    geo = waste*margin/net if net > 0 else math.inf
    return dict(units_running=units_running, Pe_W=Pe, load_frac=load_frac, eta=eta, output_W=out_W, waste_W=waste, T_K=T_rej, F_hot=F_hot,
                emit_W_m2=emit, absorbed_W_m2=absorb, net_W_m2=net, effective_area_m2=waste*margin/(EPS*SIG*T_rej**4),
                geometric_area_m2=geo, length_m=geo/per_m if geo != math.inf else math.inf,
                hot_capacity_W=(geo/per_m)*s3.cap(FACE_PER_M, T_HOT) if geo != math.inf else math.inf)


def reconcile_thermal():
    """Explain the 10 m / 23-37 m / 29 m figures of Phase III from the one relation, then give the reconciled configuration."""
    rows = []
    # Phase III option D: 10.5 m of the existing 22.5 m WARM section run at 550 K (not new length): what it holds
    f550 = 10.5/22.5; cap550 = s3.cap(s3.WARM['area']*f550, 550.0)/MARGIN
    rows.append(dict(figure='10.5 m', origin='Phase III option D: the forward 10.5 m of today\'s WARM section re-run at 550 K (no new length)',
                     relation='capacity = area x eps sigma T^4 / margin; no view factor; no hot exchange', holds_W=cap550,
                     units=f'{int(cap550/(1.75e6*(1/eps_b.brayton_eff(550.0, 1)-1)))} x 1.75 MWe'))
    for i in B:
        S = section(2, 2.66e6, band=i, standby_units=0, f_space=1.0)
        rows.append(dict(figure=f'{S["length_m"]:.1f} m ({BANDS[i]})', origin='Phase III section550(2, 2.66 MWe): two units running, Brayton '
                         'efficiency band 0.26 / 0.219 / 0.181 at 550 K', relation='f_space = 1, no standby heat, no hot exchange',
                         area_m2=S['geometric_area_m2'], length_m=S['length_m']))
    rec = []
    for F in (0.0, 0.0213):
        for i in B:
            S = section(2, 3.0e6, band=i, standby_units=1, F_hot=F)
            rec.append(dict(band=BANDS[i], F_hot=F, **{k: S[k] for k in ('waste_W', 'effective_area_m2', 'geometric_area_m2', 'length_m',
                                                                         'absorbed_W_m2', 'net_W_m2', 'hot_capacity_W')}))
    return dict(rows=rows, reconciled=rec, finding=(
        'All three figures come from one relation with different inputs: 10.5 m is a share of today\'s WARM section (no new length); 23 / 29 / 37 m '
        'are the same 2 x 2.66 MWe section across the efficiency band with f_space = 1 and no standby heat. Phase IV uses one configuration in '
        'the geometry, thermal and mass ledgers: 2 running + 1 warm standby x 3.0 MWe, f_space 0.9, 3 % standby heat, margin 1.2. Placed on the '
        'forward end of the hot blades it does not close at all: the other two blades\' 1800 K faces (F = 0.021) deposit more than a 550 K '
        'surface emits (IV-D).'))


# ======================================================================== IV-A 3.2 reference mass ====================================
def reconcile_mass(s):
    parts = mass_model.dry_parts(s); agg = {}
    for p in parts:
        n = p['name']; k = 'added tankage (full return)' if n.startswith('tankage') else ('CIRC-001 ring circulation' if n.startswith('circ') else n.split('@')[0])
        agg[k] = agg.get(k, 0.0)+p['m']/1e3
    m = op.mission(s); P = op.p(s)
    end0 = P['protected_and_operational_kg']/1e3; budget = sum(v for k, v in agg.items() if k not in ('added tankage (full return)', 'CIRC-001 ring circulation', 'operating_inventory'))
    dP = s3_dPdM(s)
    circ = agg.get('CIRC-001 ring circulation', 0.0)
    rcs = (9.3, 10.6, 16.1)
    defs = [
        ('Budget lines (1.1 kt protected ship)', budget, 'sum of the 12 mass_budget items (incl. 60 t workshop/spares/cargo, 10 t food line, 30 t margin)'),
        ('Operating inventory (B01)', agg.get('operating_inventory', 0.0), 'protected_and_operational - budget lines'),
        ('Protected + operational end mass', end0, 'operating_point protected_and_operational_kg: the mass the propellant is computed for'),
        ('Added tankage (full return)', m['added_tank_kg']/1e3, 'tank_dry_fraction 0.15 x (propellant - 600 t legacy inventory)'),
        ('End mass (operating point)', m['end_mass_kg']/1e3, 'protected + operational + added tankage = burnout mass after burn 4'),
        ('CIRC-001 ring circulation', circ, 'in mass_model.dry_parts only: NOT in the operating point end mass'),
        ('Dry ship (mass model)', mass_model.report(s)['dry_ship']['mass_kg']/1e3, 'end mass + CIRC-001 = 1,669.7 t'),
        ('Main propellant', m['propellant_kg']/1e3, 'operating_point closed form for the 1,300 t end mass (4 burns, 0.016 c)'),
        ('Departure (operating point)', m['departure_mass_kg']/1e3, 'end mass + propellant = 4,426 t'),
        ('Departure (mass model)', mass_model.report(s)['departure']['mass_kg']/1e3, 'dry ship + propellant = 4,466 t (propellant not re-solved for CIRC-001)'),
        ('Departure, coupled (CIRC-001 included)', m['departure_mass_kg']/1e3+circ*(1+dP*(1+0.15)), f'adds {circ:.1f} t x (1 + {dP:.2f} x 1.15)'),
        ('RCS propellant (Phase III, not in the model)', rcs[1], 'band 9.3-16.1 t; outside both ledgers'),
        ('Mission provisioning beyond the 10 t food line', None, 'per mission (IV-H): 10-30 t'),
    ]
    return dict(rows=[dict(item=a, t=b, definition=c) for a, b, c in defs], by_part=agg, dP_dM=dP, finding=(
        f'1,670 t is the mass-model dry ship; 1,630 t is the operating-point end mass the propellant is solved for; the {circ:.1f} t difference is '
        'CIRC-001, which mass_model carries but operating_point does not. 2,797 t of propellant therefore belongs to 1,630 t, and the mass model\'s '
        f'4,466 t departure adds 40 t without the propellant it needs: coupled, the reference departure is ~{m["departure_mass_kg"]/1e3+circ*(1+dP*1.15):,.0f} t. '
        'Every ISSA increment in Phase IV is coupled from this corrected base. Production data stays unchanged (finding for the owner).'))


def s3_dPdM(s):
    Rn = op.mission(s)['mass_ratio_per_burn']**4; f = s['physics']['fuel_loads']['tank_dry_fraction']
    return (Rn-1)/(1-(Rn-1)*f)


# ======================================================================== IV-C heat transport ========================================
LI = dict(rho=430.0, cp=4200.0, mu=1.6e-4, k=55.0, sigma=0.26, h_fg=19.5e6, M=6.94e-3, T_boil_1atm=1615.0)


def li_vapour_pressure(T):
    # Clausius-Clapeyron anchored at 1 atm, 1615 K (STUDY)
    return 101325.0*math.exp(-LI['h_fg']*LI['M']/8.314*(1/T-1/LI['T_boil_1atm']))


def transport(s):
    q_peak = 10.45e9; per_blade = q_peak/3
    L_hot = s3.HOT_ALLOWANCE_W and 162.0      # hot length on the blade (14.4 GW / 89 MW per m)
    a_max = 1.362*G0                          # burn-4 end acceleration (operating point)
    rows = []
    for name, dT, v, dp_panel, eta_p, hp, zones, cls in (
            ('H1 existing pumped loop (one loop per blade)', 200.0, (4.0, 5.0, 6.0), (1.5e5, 3e5, 6e5), 0.6, False, 1, 'STUDY'),
            ('H2 optimised pumped (dT 400 K, tapered headers)', 400.0, (6.0, 8.0, 10.0), (1.5e5, 3e5, 6e5), 0.7, False, 1, 'STUDY'),
            ('H3 hybrid: pumped trunk and radial manifolds, ~1.5 m Li heat-pipe fins', 300.0, (6.0, 8.0, 10.0), (3e4, 6e4, 1.2e5), 0.7, True, 1, 'STUDY'),
            ('H4 predominantly passive: axial Li vapour trunk (thermosyphon in burns)', None, None, None, None, True, 1, 'SPECULATIVE'),
            ('H5 distributed independent zones (6 loops per blade, own pumps)', 300.0, (6.0, 8.0, 10.0), (3e4, 6e4, 1.2e5), 0.65, True, 6, 'STUDY')):
        r = dict(name=name, cls=cls)
        if dT is None:
            p_v = li_vapour_pressure(T_HOT); rho_v = p_v*LI['M']/(8.314*T_HOT); mdot = per_blade/LI['h_fg']
            vv = 100.0; A = mdot/rho_v/vv; D = math.sqrt(4*A/math.pi)
            cap_head = 2*LI['sigma']/20e-6; grav = LI['rho']*a_max
            wall = math.pi*D*0.004*L_hot*10.2e3/1e3*3
            r.update(vapour_pressure_Pa=p_v, vapour_density=rho_v, vapour_mdot_kg_s=mdot, duct_area_m2=A, duct_D_m=D, duct_wall_t=wall,
                     capillary_head_Pa=cap_head, gravity_head_Pa_per_m=grav, pump_W=[0.0, 0.2e6, 1e6], inventory_t=[20.0, 40.0, 80.0],
                     mass_t=[wall*0.7, wall, wall*1.5],
                     phases=dict(accel='condensate returns aft (downhill): thermosyphon works', braking='same: the ship always accelerates +x in its own frame',
                                 coast='0 g: capillary only, cannot carry decay heat over 160 m; needs a pump', startup='frozen Li (454 K) start under '
                                 'acceleration: known front-tracking failure; pump-assisted start required', postburn='decay heat with no acceleration: pump'),
                     verdict='Rejected as the primary path: a ~%.1f m vapour duct per blade, no 0 g operation and a frozen start. Gravity-assisted '
                             'return is a real asset in burns and is kept as a backup mode in H3/H5.' % D)
        else:
            mdot = per_blade/(LI['cp']*dT); Vdot = mdot/LI['rho']
            pw, inv, mass = [], [], []
            for i in B:
                A = Vdot/v[i]/zones; D = math.sqrt(4*A/math.pi)
                L_tr = 0.5*L_hot+30.0                            # tapered header (mean half length) + drive-to-root run
                Re = LI['rho']*v[i]*D/LI['mu']; f = 0.316*Re**-0.25
                dp = f*(2*L_tr)/D*LI['rho']*v[i]**2/2+dp_panel[i]+1e5      # trunk supply+return, panel, drive HX
                pw.append(3*Vdot*dp/eta_p)
                trunk_m3 = 3*zones*2*A*L_tr
                panel_m3 = 3*L_hot*30.0*(0.002 if not hp else 0.0008)    # radial channels (or manifolds feeding fins)
                inv.append((trunk_m3+panel_m3)*LI['rho']/1e3)
                wall = 3*zones*2*math.pi*D*0.003*L_tr*10.2e3/1e3        # Nb-1Zr / Mo trunk walls 3 mm
                pumps = 3*zones*(2.0, 4.0, 8.0)[i]
                fins = 3*L_hot*30.0*2*(0.0, 1.0, 2.0)[i]/1e3*(1 if hp else 0)    # heat-pipe fin increment over channels, kg/m2 of two faces
                mass.append(inv[-1]+wall+pumps+fins)
            r.update(dT_K=dT, mdot_kg_s_per_blade=mdot, Vdot_m3_s_per_blade=Vdot, pump_W=pw, inventory_t=inv, mass_t=mass, zones=zones,
                     heat_pipes=hp, subcooling_Pa_needed=li_vapour_pressure(T_HOT)+LI['rho']*a_max*30.0,
                     phases=dict(accel='pumped; hydrostatic head along the 160 m header %.0f kPa (sets pressurisation, not work)' % (LI['rho']*a_max*L_hot/1e3),
                                 braking='identical (same +x acceleration)', coast='part flow on decay heat; Li must stay above 454 K or drain',
                                 startup='pre-heat from L2 before ignition (MW-h class); frozen sections thawed in order',
                                 postburn='15-30 % flow on decay heat; heat pipes (H3/H5) cool passively once below their limit'),
                     failure=('one puncture drains a whole blade loop' if not hp and zones == 1 else
                              'a puncture loses one fin (H3) or one zone of six (H5); the loop survives'))
        rows.append(r)
    fin_L = math.sqrt(2*1.56e13*1e-5*2e-4/(9.6e5*0.03))
    return dict(rows=rows, per_blade_W=per_blade, hot_length_m=L_hot, accel_max_m_s2=a_max, coolant='lithium (OPEN in canon; STUDY choice at 1800 K)',
                li_vapour_pressure_1800K_Pa=li_vapour_pressure(T_HOT), fin_capillary_length_m=fin_L,
                separation=dict(drive_to_root='trunks from the drive heat exchanger to the blade roots (~30 m) and the tapered root headers (162 m)',
                                distribution='radial manifolds or channels across the 30 m blade width, then fins'),
                finding=('The OPEN hot-loop pumps are derived: an existing-type pumped Li loop (H1, dT 200 K) needs ~12-34 MW of pump work and carries '
                         '~470-700 t of lithium in its trunks and channels, which no mass line holds today. Raising dT to 400 K and tapering the headers '
                         '(H2) cuts that to ~5-15 MW and ~150-240 t. Long heat pipes '
                         f'fail on capillary limits: an Li fin across the blade carries its strip only to ~{fin_L:.1f} m, so passive transport is local. '
                         'H3 (pumped trunk + short heat-pipe fins) and H5 (six independent zones) keep the pump work near 4-9 MW, cut the panel inventory, '
                         'and turn a dust puncture from a loop loss into a fin or zone loss. H4 (vapour trunk) exploits the gravity-assisted return in '
                         'every burn but cannot start frozen or run in 0 g. Recommended study basis: H5 with heat-pipe fins (H3 inside each zone).'))


# ======================================================================== IV-D thermal zones and view factors ========================
def thermal(s, pl, planning):
    hot0, hot1 = BULKHEAD_X-162.0, BULKHEAD_X
    BK = (50.0, 37.0)                    # production graded bulkhead: three V-groove layers r 6.1-37 m at x ~47.8-50 (radiator_zones.layers), as a disk
    L7 = 24.0                            # the 700 K section length of N2-R4a (convergence); 550 K Phase III lengths for comparison
    vf = {}
    vf['WARM, production bulkhead in place'] = view_factor(50.4, 72.9, hot0, hot1, n=60000, baffle=BK)
    vf['LOW, production bulkhead in place'] = view_factor(73.4, 93.4, hot0, hot1, n=60000, baffle=BK)
    vf['WARM if the bulkhead were absent'] = view_factor(50.4, 72.9, hot0, hot1)
    vf['LOW if the bulkhead were absent'] = view_factor(73.4, 93.4, hot0, hot1)
    for L in (20.0, 29.0, 37.0):
        vf[f'550 K on the hot-blade forward end, {L:.0f} m (Phase III F, aft of the bulkhead)'] = view_factor(BULKHEAD_X-L, BULKHEAD_X, hot0, BULKHEAD_X-L)
    vf[f'700 K section {L7:.0f} m with the bulkhead moved aft of it (N2-R4a)'] = view_factor(BULKHEAD_X-L7, BULKHEAD_X, hot0, BULKHEAD_X-L7, n=60000,
                                                                                            baffle=(BULKHEAD_X-L7-0.2, 37.0))
    vf['Forward extension beyond LOW (x 93.9-118; collides with the aft storage front at 93.4)'] = view_factor(93.9, 118.0, hot0, hot1, baffle=BK)
    base = dict(vf)
    baff = {}
    for Rb in (20.0, 30.0, 37.0):
        baff[Rb] = dict(WARM=view_factor(50.4, 72.9, hot0, hot1, n=60000, baffle=(50.0, Rb)), LOW=view_factor(73.4, 93.4, hot0, hot1, n=60000, baffle=(50.0, Rb)))
    hotabs = ALPHA*EPS_HOT*SIG*T_HOT**4
    rows = []
    for name, (F, e) in base.items():
        T = 440.0 if name.startswith('WARM') else (300.0 if name.startswith('LOW') else (700.0 if name.startswith('700') else 550.0))
        emit = EPS*SIG*T**4; absb = hotabs*F
        T_eq = (absb/(EPS*SIG))**0.25
        rows.append(dict(surface=name, T_K=T, F_hot=F, F_sigma=e, emit_W_m2=emit, absorbed_W_m2=absb, ratio=absb/emit, T_equilibrium_no_load_K=T_eq,
                         works_in_burn=absb < 0.3*emit, debit=absb/emit))
    bf = []
    for Rb, d in baff.items():
        for k, (F, e) in d.items():
            T = 440.0 if k == 'WARM' else 300.0; emit = EPS*SIG*T**4
            bf.append(dict(baffle_R_m=Rb, surface=k, F_hot=F, F_sigma=e, absorbed_W_m2=hotabs*F, ratio=hotabs*F/emit, works_in_burn=hotabs*F < 0.3*emit))
    A_baffle = 4248.5
    baffle = dict(station_x=50.0, R_m=37.0, area_m2=A_baffle, layers=3, existing_t=3*A_baffle*0.35/1e3, mass_t=[0.0, 2.0, 5.0],
                  hot_capacity_lost_W=[0.0, 0.0, 0.0], silhouette='the production bulkhead moves aft by the section length: no new element, same envelope',
                  cls='PROTOTYPE (isolated radiator variant; relocation of an existing production element)')
    # hot allowance recomputed
    ideal = 14.40e9; absorbed = 10.45e9; per_m = s3.cap(FACE_PER_M, T_HOT)
    allow = dict(ideal_W=ideal, peak_absorbed_W=absorbed, budget_W=10.8e9, per_m_W=per_m,
                 L_max_no_margin_m=(ideal-absorbed)/per_m, L_max_with_margin_m=(ideal-absorbed*MARGIN)/per_m,
                 L_max_budget_m=(ideal-10.8e9)/per_m,
                 note='Fiji/current-drive operating point only (MODEL-DERIVED); Vertex hot loads are not used '
                 '(no Vertex reopening). With the 20 % rule applied to the hot blade the margin is negative already: 10.45 x 1.2 = 12.5 GW of 14.4 GW '
                 'leaves 1.9 GW (21 m); without it 3.95 GW (44 m).')
    # LOW / WARM closure with single failures from the Phase III ledger loads
    P3 = json.loads((R/'phase3.json').read_text())
    warm_use = P3['thermal_closure']['warm_usable_W']; low_use = P3['thermal_closure']['low_usable_W']
    closure = []
    for r in P3['thermal_closure']['rows']:
        if r['condition'] != 'intact': continue
        for cond, k in (('intact', 1.0), ('one blade sector lost', 2/3)):
            fails = []
            for c in r['circuits']:
                cap = c['capacity_W']*k
                if c['load_W'] > cap: fails.append(dict(circuit=c['circuit'], load_W=c['load_W'], capacity_W=cap))
            closure.append(dict(state=r['state'], band=r['band'], condition=cond, closes=not fails, fails=fails))
    # LOW extension needed
    low_need = [1.10e6*MARGIN*1.5, 1.10e6*MARGIN, 0.60e6*MARGIN*1.5]
    per_m_low = s3.cap(s3.LOW['area']/s3.LOW['length'], 300.0)
    ext = dict(high_band_one_sector_W=1.10e6*MARGIN*1.5, available_W=low_use*MARGIN, added_length_m=max(0.0, (1.10e6*MARGIN*1.5-low_use*MARGIN))/per_m_low,
               per_m_W=per_m_low)
    # L2 cooling availability by state for each geometry option
    states = ('drive start', 'full power', 'drive trip', 'cooldown', 'drain / refill', 'one unit lost', 'one sector lost')
    avail = {
        'G0 production: L2 on warm channels (coast only)': ['no (channels drained before ignition)', 'no', 'no for 0.3-4 h', 'after refill', 'no', 'coast yes', 'coast 2/3'],
        'G1 550 K on the hot-blade forward end, bulkhead unchanged (Phase III F)': ['no: F = 0.02 to 1800 K surfaces', 'no', 'yes once the hot blades cool (~80 s)', 'yes', 'yes', 'n/a', 'n/a'],
        'G2 forward extension beyond LOW': ['geometry conflict: aft storage front at x 93.4', '-', '-', '-', '-', '-', '-'],
        'G3 700 K on the hot-blade forward end, bulkhead moved aft of it (N2-R4a)': ['yes', 'yes (F < 1e-3)', 'yes', 'yes', 'yes (independent of the channels)',
                                                                                    'yes: two units on two sectors', 'yes if one unit per sector'],
        'G4 separate panels on the casing forward of the bulkhead': ['yes', 'yes', 'yes', 'yes', 'yes', 'yes', 'yes; small area (casing ~2,000 m2)'],
    }
    return dict(view_factors=rows, baffle_scan=bf, baffle=baffle, hot_allowance=allow, closure=closure, low_extension=ext,
                l2_cooling=dict(states=states, options=avail), hot_absorbed_per_F_W_m2=hotabs, finding=(
                    'In a burn every radiator surface on a blade can see the 1800 K hot sections of the other two blades. The production design already '
                    'answers this for WARM and LOW: its three-layer graded bulkhead (r 6.1-37 m) is a full annular baffle, and behind it WARM and LOW see '
                    'the hot faces with F ~2-6e-4 (verified here): in a burn they absorb ~15-20 % of what they emit, a capacity debit the ledger does not '
                    'yet carry (it worsens the LOW margin), not a failure. Without the bulkhead F would be 0.025 and 0.008 and neither could work. The '
                    'Phase III 550 K section on the hot-blade forward end sits aft of that bulkhead and is fully exposed (F 0.02: it absorbs 2-3x what it '
                    'emits), so option F as drawn has no sink in a burn. Moving the bulkhead aft of the new section (N2-R4a) restores the shadow (F < 1e-3) '
                    'with no new element. A forward extension beyond LOW collides with the aft storage front at x 93.4.'))


# ======================================================================== IV-E L2 power ==============================================
def l2(pl, planning):
    pro = s3.st(pl, 'COAST_HV_PROACTIVE'); ess = s3.st(pl, 'SURVIVAL_MISSION')
    aux = 0.03; pmad = 0.95; eol = 0.90
    E_eng = 21e6*10.0; recharge_W = [E_eng/600.0/0.9]*3             # 10 s / 10 min pattern recharge (one scenario)
    standby_W = [30e3, 60e3, 120e3]
    def demand(i, plan=True):
        return pro[i]+(planning[i] if plan else 0.0)+recharge_W[i]+standby_W[i]
    rows = []
    for Pe in (2.66e6, 3.0e6, 3.5e6, 4.0e6):
        for strat, run in (('A 2 running + cold standby', 2), ('B 2 running + warm standby', 2), ('C 3 at partial load', 3)):
            r = dict(Pe_W=Pe, strategy=strat)
            avail = {}
            for life, k in (('BOL', 1.0), ('EOL', eol)):
                net = Pe*k*(1-aux)*pmad
                avail[life] = dict(intact=[run*net-demand(i) for i in B],
                                   immediate_after_loss=[(run-1)*net-demand(i) for i in B],
                                   one_unit=[2*net-demand(i) for i in B],
                                   immediate_essential=[(run-1)*net-ess[i] for i in B])
            # after a loss: A runs on one until the cold unit is up, B ~1 h, C instantly on two
            r.update(margins=avail, restore_h=dict(A=(6.0, 12.0, 24.0), B=(0.5, 1.0, 2.0), C=(0.0, 0.0, 0.0))[strat[0]],
                     standby_heat_W=Pe/eps_b.brayton_eff(550.0, 1)*(0.0, 0.03, 0.0)[('A', 'B', 'C').index(strat[0])],
                     wear='C runs three units at 2/3 load: 1.5x operating hours per unit; A minimises hours but its restart is the slowest')
            m = []
            for i in B:
                p = eps_b.fission_plant(Pe, 550.0, 80.0, i, 2.69e4, EPS)
                ns = sum(v for k, v in p['parts_kg'].items() if k not in ('shield', 'rejection'))
                U = eps_g1.unit(Pe_W=Pe, eta=p['eta'], n_running=run, i=i)
                m.append(3*(ns+U['shadow_kg']+U['slab_kg'])/1e3)
            r['mass_t'] = m
            rows.append(r)
    # continuous optimum: smallest Pe with two units at EOL carrying the nominal demand incl. planning; and the high band
    opt = [demand(i)/(2*eol*(1-aux)*pmad) for i in B]
    opt_no_plan = [demand(i, plan=False)/(2*eol*(1-aux)*pmad) for i in B]
    refs = []
    for name, n, Pe in (('4 x 1.75 (C-lean 3+1)', 4, 1.75e6), ('5 x 1.33 (4+1)', 5, 1.33e6), ('2 x 100 % (5.3)', 2, 5.3e6)):
        net = Pe*eol*(1-aux)*pmad
        refs.append(dict(name=name, units=n, after_one_loss_EOL_W=[(n-1)*net-demand(i) for i in B]))
    return dict(rows=rows, demand_W=[demand(i) for i in B], demand_parts=dict(proactive_state=pro, planning=planning, buffer_recharge=recharge_W,
                standby=standby_W, aux_frac=aux, pmad=pmad, eol=eol), optimum_Pe_W=opt, optimum_without_planning_W=opt_no_plan, references=refs, finding=(
        f'Two units at EOL must carry {demand(1)/1e6:.1f} MW nominal ({demand(2)/1e6:.1f} MW at the high band) once the OPEN planning loads, buffer '
        f'recharge and standby are counted, so the continuous optimum rating is {opt[1]/1e6:.2f} MWe nominal and {opt[2]/1e6:.2f} MWe at the high band '
        f'({opt_no_plan[1]/1e6:.2f} / {opt_no_plan[2]/1e6:.2f} MWe without the planning loads). 2.66 and 3.0 MWe fail after one loss at EOL; '
        '3.5 MWe closes the nominal band with ~0.6 MW margin; no rating in the 2.66-4 MWe range closes the high band after a loss unless the '
        'planning loads are shed. Strategy C (three at 2/3 load) loses nothing at the moment of a trip; B needs ~1 h on one unit and costs ~3 % of '
        'a unit\'s heat in standby; A leaves 6-24 h on one unit. Recommended study basis: 3 x 3.5 MWe, strategy C, B as the maintenance mode, '
        'with high-band planning loads sheddable.'))


def storage():
    pats = [('10 s every 10 min', 10.0, 600.0), ('60 s every 30 min', 60.0, 1800.0), ('1 s bursts, 10 per minute', 1.0, 6.0),
            ('5 min continuous, once a day', 300.0, 86400.0)]
    tech = dict(li_power=dict(Wh_kg=(100, 140, 180), W_kg=(2500, 1500, 1000), dod=0.8, cls='STUDY'),
                supercap=dict(Wh_kg=(5, 7, 10), W_kg=(10000, 8000, 5000), dod=0.9, cls='STUDY'),
                flywheel=dict(Wh_kg=(20, 40, 60), W_kg=(5000, 3000, 2000), dod=0.9, cls='STUDY (gyroscopic coupling with the CMGs)'),
                pcm_thermal=dict(Wh_kg=(60, 80, 100), W_kg=None, dod=1.0, cls='heat only'))
    excess = (14e6, 21e6, 28e6)
    rows = []
    for name, t, every in pats:
        for i in B:
            P = excess[i]; E = P*t/3600.0
            best = None
            for k, v in tech.items():
                if v['W_kg'] is None: continue
                m = max(E/v['Wh_kg'][i]/v['dod'], P/v['W_kg'][i])/1e3
                best = (k, m) if best is None or m < best[1] else best
            rows.append(dict(pattern=name, band=BANDS[i], power_W=P, energy_kWh=E/1e3, recharge_W=P*t/every/0.9, best=best[0], mass_t=best[1],
                             limited_by='power' if P/tech[best[0]]['W_kg'][i] > E/tech[best[0]]['Wh_kg'][i]/tech[best[0]]['dod'] else 'energy',
                             sustainable_on_L2=P*t/every/0.9 < 1.0e6))
    stores = [
        dict(store='Main battery (EPS-A)', energy_kWh=2000, power_MW=2.0, mass_t=2.5, role='coast ride-through and black-start services',
             note='1C limits it to 2 MW < 3.4 MW coast load'),
        dict(store='Independent restart pack (new, DR3-01)', energy_kWh=[300, 500, 900], power_MW=[0.3, 0.5, 0.8], mass_t=[2.0, 3.5, 6.5],
             role='one L2 unit restart (pumps, heaters, controls, instrumentation) with no propulsion and no crew-reserve draw',
             note='physically separate cells and bus; recharged only by L2; never connected to the refuge'),
        dict(store='Pulse bank (canon)', energy_kWh='canon', power_MW='canon', mass_t='canon', role='drive ignition only', note='unchanged'),
        dict(store='Defense buffer', energy_kWh=[39, 58, 78], power_MW=[14, 21, 28], mass_t=[9.3, 14.0, 19.1], role='engagements above L2 surplus',
             note='power-sized for the 10 s pattern; energy-sized for the 60 s and 5 min patterns (table)'),
        dict(store='Survival storage (refuge)', energy_kWh=[150, 250, 400], power_MW=0.05, mass_t=[1.2, 2.0, 3.2], role='crew survival bridge to L3',
             note='isolated: never used for propulsion restart (owner rule)'),
        dict(store='Distributed ride-through cells', energy_kWh=[30, 60, 120], power_MW=[0.3, 0.6, 1.0], mass_t=[0.4, 0.8, 1.5],
             role='per-bus 5-15 min ride-through for switching faults', note='one per bus segment'),
        dict(store='Auxiliary restart unit (APU, option)', energy_kWh='fuel-limited', power_MW=[0.2, 0.3, 0.5], mass_t=[3.0, 5.0, 9.0],
             role='RTG/ radioisotope-Stirling or a small fuel cell that restarts one L2 unit with no stored-energy draw', note='OPEN technology; listed for DR4'),
    ]
    restart = dict(sequence_R1b='restart pack -> one L2 unit (pumps, heaters, I&C) -> unit at power -> second unit -> battery recharge -> pulse bank '
                   '-> drive', canon_kept=True, R2_pack_t=2.3, note='canon black-start sequence kept until the owner reviews R1b (DR3-01)')
    scaling = dict(phase3='P_def ~ (v / 0.016 c)^3 (Phase III missions), no source', provenance='none found in the canon or the dust study',
                   physics=[('particle encounter rate', 'n v', 1), ('kinetic energy per particle', 'm v^2 / 2', 2), ('detection range for fixed warning time', 'v', 1)],
                   band=('v^1 (rate-limited: fixed energy per engagement)', 'v^2', 'v^3 (energy-limited: neutralise kinetic energy)'),
                   at_0_008c=[0.5, 0.25, 0.125], cls='OPEN; the v^3 law is an upper bound, not a derivation')
    return dict(patterns=rows, technologies=tech, stores=stores, restart=restart, defense_scaling=scaling, finding=(
        'Buffers are power-limited for short engagements and energy-limited for long ones: the 10 s and 1 s patterns need 21 MW in ~10-15 t of '
        'high-power cells or supercapacitors; a 60 s engagement doubles the energy but not the mass; a 5 min engagement is energy-limited at '
        '~15-35 t and cannot be recharged by L2 inside a day without shedding. An independent 2-6 t restart pack (or a small APU) restarts one '
        'L2 unit with no propulsion and no crew-reserve draw. The v^3 defense scaling has no source: it is an upper bound.'))


# ======================================================================== IV-F district and cryo heating =============================
def district(s):
    W = json.loads((R/'phase4_rad_wayfarer.json').read_text())
    S1, S2, S3 = W['S1'], W['S2'], W['S3']
    nu_leak = S1['neutrons_leaking_per_fission']; g_leak = S1['photons_leaking_per_fission']
    lam_n = S2['relaxation_cm']['neutron_number']; lam_g = S2['relaxation_cm']['secondary_gamma']
    E_he3_n = S3['per_incident_neutron']['he3_eV']*1.602e-19; E_wall_n = S3['per_incident_neutron']['wall_eV']*1.602e-19
    E_he3_g = S3['per_incident_photon']['he3_eV']*1.602e-19; E_wall_g = S3['per_incident_photon']['wall_eV']*1.602e-19
    P3 = json.loads((R/'phase3.json').read_text()); lift = P3['shielding']['he3_stage_lift_W']
    import fuel_storage as fs
    G3 = json.loads((R/'phase3_eps_g1.json').read_text()); U3 = G3['reference_unit']
    units3 = G3['districts']['2+1 x 2.66 MWe (one unit per blade)']['units']
    shadow_cm = U3['shadow_t_m']*100; cone = 12.5
    geo = []
    for t_ in fs.tanks(s):
        if t_['species'] != 'helium-3': continue
        for u in units3:
            a = math.radians(u['azimuth_deg']); ux, uy, uz = u['x_aft']+5.5, 2.9*math.cos(a), 2.9*math.sin(a)
            dx, dy, dz = t_['x0']-ux, t_['y']-uy, t_['z']-uz; d = math.sqrt(dx*dx+dy*dy+dz*dz)
            geo.append(dict(tank=t_['name'], unit=u['unit'], d_m=d, off_axis_deg=math.degrees(math.acos(dx/d)), in_cone=math.degrees(math.acos(dx/d)) <= cone,
                            a_env=t_['a_env']))
    d = min(g['d_m'] for g in geo); ang_max = max(g['off_axis_deg'] for g in geo)
    rows = []
    for Pe in (3.0e6, 3.5e6):
        Pt = Pe/eps_b.brayton_eff(550.0, 1); fis = Pt/(200e6*1.602e-19)
        Sn = fis*nu_leak; Sg = fis*g_leak
        A_tank = math.pi*geo[0]['a_env']**2
        for side_cm in (0.0, 40.0, 80.0, shadow_cm):
            Tn = math.exp(-side_cm/lam_n) if side_cm else 1.0; Tg = math.exp(-side_cm/lam_g)*(0.08 if side_cm else 1.0)
            flux_n = Sn*Tn/(4*math.pi*d**2); flux_g = Sg*Tg/(4*math.pi*d**2)+(Sn*0.08*math.exp(-side_cm/lam_g) if side_cm else 0.0)/(4*math.pi*d**2)
            q3 = flux_n*A_tank*E_he3_n+flux_g*A_tank*E_he3_g; qw = flux_n*A_tank*E_wall_n+flux_g*A_tank*E_wall_g
            rows.append(dict(Pe_W=Pe, Pt_W=Pt, side_shield_cm_LiH_after_5cm_W=side_cm, n_per_s=Sn, flux_n_m2_s=flux_n, he3_W_per_tank_per_unit=q3,
                             wall_W_per_tank_per_unit=qw, path='shadow cone (direct)' if side_cm == shadow_cm else 'direct'))
    allow_W = 0.25*lift/4/3
    phi_max = allow_W/(A_tank*E_he3_n)
    Sn35 = 3.5e6/eps_b.brayton_eff(550.0, 1)/(200e6*1.602e-19)*nu_leak
    need_T = min(1.0, phi_max*4*math.pi*d**2/Sn35)
    t_cm = -lam_n*math.log(need_T) if need_T < 1 else 0.0
    bare35 = next(r for r in rows if r['Pe_W'] == 3.5e6 and r['side_shield_cm_LiH_after_5cm_W'] == 0.0)['he3_W_per_tank_per_unit']
    corr = dict(phase3_tank_x=-35.5, actual_tank_x=min(t_['x0'] for t_ in fs.tanks(s)), phase3_d_m=P3['shielding']['tanks'][0]['d_m'], actual_d_m=d,
                phase3_off_axis_deg=P3['shielding']['tanks'][0]['off_axis_deg'], actual_off_axis_deg_max=ang_max,
                note='Phase III read fuel_storage x0 as a span from the aft end; it is ship x. The tank farm is forward of the radiator zone, ~200 m '
                     'from the district and inside the 12.5 deg shadow cone.')
    layers = [
        dict(layer='Outer structure / micrometeoroid shell (~300 K)', neutron='~2 % of incident neutron energy (scatter)', gamma='~55 % of incident photon energy (Al 2 cm)',
             status='TRANSPORT-INFORMED (S3, 1-D)'),
        dict(layer='Thermal shields / MLI (40-80 K)', neutron='small (thin, light)', gamma='part of the wall share, by mass', status='STUDY (by mass fraction)'),
        dict(layer='Intermediate stages (4-20 K)', neutron='small', gamma='by mass', status='OPEN (needs the tank layer stack)'),
        dict(layer='He-3 liquid (3 K stage)', neutron='~100 %: He-3(n,p)T captures essentially every neutron that enters; 764 keV + recoil energy deposited '
             'locally (1.01 MeV per incident leakage neutron)', gamma='~45 % of incident photon energy (0.10 MeV per photon in 50 cm)',
             status='TRANSPORT-INFORMED (S3)'),
        dict(layer='Coolers', neutron='indirect: the deposit is the 3 K load', gamma='indirect', status='STUDY'),
    ]
    units = [
        dict(item='Placement', value='one unit per radiator sector (blades 90/210/330), bays M1-M2 at the 120 deg sectors'),
        dict(item='Attachment', value='four-point kinematic mount to the keel ring frames; shield slab bolted to the module frame, not the unit'),
        dict(item='Separation', value='units 120 deg apart; a unit sees the others edge-on through its own slab (side e-folds)'),
        dict(item='Thermal', value='each unit rejects to its own sector (550 K section, IV-D G3) and the blade warm channels in coast'),
        dict(item='Electrical', value='unit 1 -> bus A, unit 2 -> bus B, unit 3 -> bus A/B tie; strategy C splits load 1/3 each'),
        dict(item='Maintenance', value='conversion ORUs swappable at power-off + 24-72 h decay; reactor side not serviced in flight'),
        dict(item='Robotics', value='keel-lane manipulator reaches the ORU faces; removal hatch per bay (Phase III P3-14 interface)'),
        dict(item='Replacement', value='between missions at the yard; whole-unit swap through the bay hatch'),
        dict(item='Crew restrictions', value='no crew in M1-M2 with a unit at power; transit through the keel lane only behind the shadow wall'),
        dict(item='Aft machinery interfaces', value='L1 machinery, hot-loop trunks (IV-C) and the drive service bay stay aft of the district; '
             'coolant risers cross the casing at the sector roots'),
    ]
    return dict(units=units, transport=dict(nu_leak=nu_leak, g_leak=g_leak, lambda_n_cm=lam_n, lambda_g_cm=lam_g, he3_per_n_J=E_he3_n,
                he3_per_g_J=E_he3_g, d_m=d, lift_W=lift), geometry=geo, correction=corr, tank_rows=rows, layers=layers, allowed_flux_n_m2_s=phi_max,
                needed_transmission=need_T, needed_LiH_cm=t_cm, finding=(
        f'Phase III placed the He-3 tanks 54 m from the district and outside the shadow cone; the tank farm is in fact forward of the radiator zone '
        f'(ship x 109-138), ~{d:.0f} m from the units and {ang_max:.1f} deg off axis at most: inside the 12.5 deg shadow cone. With the transport-informed '
        f'leakage (0.94 n per fission, surrogate core) and the S3 deposit (1.01 MeV in the He-3 per incident neutron, almost all at 3 K), one bare 3.5 MWe '
        f'unit would put ~{bare35:.1f} W into each tank at that distance; three units against a 25 % share of the {lift:.0f} W lift (PROTOTYPE allocation) '
        f'need a transmission of {need_T:.2f} (~{t_cm:.0f} cm of LiH), which the {shadow_cm:.0f} cm shadow shield exceeds by many orders. The direct '
        'path closes. What stays OPEN is scatter: neutrons and gammas leaving the unshielded sides scatter off the blades, the casing and the tank '
        'farm structure toward the tanks; that needs the 3-D transport model (DR4-08). Gammas deposit mostly in the warm wall, not at 3 K.'))


# ======================================================================== IV-G ECLSS and logistics ===================================
def eclss():
    unit_cap = 4; unit_t = (0.9, 1.2, 1.6); unit_kW = (0.27, 0.36, 0.48)
    cases = []
    for name, ringA, ringB, hub in (('Phase III: 5 units (3 + 2)', 3, 2, 0), ('6 units (3 + 3)', 3, 3, 0), ('7 units (3 + 3 + 1 hub, cross-ring)', 3, 3, 1),
                                    ('8 units (4 + 4)', 4, 4, 0)):
        n = ringA+ringB+hub
        def cap_after(lostA=False, lost_mod=0, movable=True):
            a = 0 if lostA else ringA; b = ringB; h = hub
            tot = a+b+h-lost_mod
            return tot*unit_cap
        res = {
            '12 nominal (6 + 6)': n*unit_cap >= 12 and min(ringA, ringB)*unit_cap >= 6,
            '6 crew': n*unit_cap >= 6,
            'one module lost': (n-1)*unit_cap >= 12,
            'ring A lost (12 in ring B)': (ringB+hub)*unit_cap >= 12,
            'ring A lost + one module failed': (ringB+hub-1)*unit_cap >= 12,
            'extended emergency (12 in B, 30 d, units moved)': (ringB+hub+(ringA if True else 0))*unit_cap >= 12,
        }
        cases.append(dict(option=name, units=n, mass_t=[n*u for u in unit_t], added_vs_2x6_t=[n*u-2*6/4*u*1.0 for u in unit_t],
                          kW=[n*k for k in unit_kW], checks=res, transfer=('units move by the spoke lift in ~2-6 h each (1.2 t, 1.0 x 1.2 x 2.0 m); '
                          'moving happens before or after, not during, a ring loss' if hub == 0 else 'the hub unit serves either ring through spoke ducts: no transfer')))
    return dict(rows=cases, reconciliation=('Phase III wrote "a 2-3 t premium" for the modular option; its own table gave 9.6 t for 5 units (8 extra '
                'person-capacities x 1.2 t). The premium of the modular approach over two 6-person strings is the extra capacity, 1.2 t per 4-person '
                'unit beyond the three that 12 people need.'), finding=(
        'Five units (3 + 2) carry 12 in ring A but not after the loss of ring A (8 capacity in B). Six units (3 + 3) survive a ring loss but '
        'not a ring loss plus one failed unit. Seven units with one cross-ring unit in the hub, or eight (4 + 4), close every case: 12 in one '
        'ring after a ring loss and a unit failure. Nominal aggregate capacity is not emergency availability. Recommended: 7 units (8.4 t nominal, '
        '+4.8 t over two 6-person strings).'))


def logistics():
    P3 = json.loads((R/'phase3.json').read_text())['logistics']
    tare = (0.8, 1.0, 1.3); gross_max = 6.0; vol = 44.8; usable = 0.7
    compat = {'FOOD_SHELF': 'A', 'FOOD_FROZEN': 'F', 'WATER_O2': 'W', 'ECLSS_EXP': 'A', 'MEDICAL': 'M', 'HYGIENE': 'A', 'SPARES_ORU': 'S',
              'RESERVE': 'R', 'HAZMAT': 'H', 'GARDEN': 'A'}
    rows = []
    for r in P3['rows']:
        ded = 0; groups = {}
        for c in r['categories']:
            kg = c['kg']; payload = (gross_max-tare[1])*1e3
            ded += max(1, math.ceil(kg/payload)) if kg > 0 else 0
            g = compat[c['category']]; groups[g] = groups.get(g, 0.0)+kg
        shared = sum(max(1, math.ceil(kg/((gross_max-tare[1])*1e3))) for kg in groups.values())
        rows.append(dict(mission=r['mission'], payload_t=r['total_t'], dedicated=ded, shared_by_compatibility=shared, phase3_count=r['containers'],
                         gross_t=r['total_t']+ded*tare[1], tare_t=ded*tare[1]))
    return dict(container=dict(tare_t=tare, gross_max_t=gross_max, payload_max_t=gross_max-tare[1], volume_m3=vol, usable_fraction=usable,
                               structural='6 t gross at 1.36 g peak axial = 80 kN per container on four twist-locks (rated 1.5 g: 88 kN)'),
                compatibility=compat, rows=rows, finding=('Counts follow mass (6 t gross, 1 t tare), not volume: dense loads (water, food) fill a '
                'container by mass at a third of its volume. Sharing containers between compatible categories (dry consumables A; frozen F; water W; '
                'medical M; spares S; reserve R; hazardous H always alone) saves ~20-35 % of containers against one category per container. Phase III '
                'counts omitted the tare: 1 t per container adds 10-20 t of departure mass.'))


# ======================================================================== IV-H missions =============================================
def missions(s, dM_hw_t, life):
    ve = op.p(s)['exhaust_velocity_m_s']; f = s['physics']['fuel_loads']['tank_dry_fraction']
    end0 = op.p(s)['protected_and_operational_kg']+40.2e3; p0 = op.p(s)['legacy_inventory_kg']; F = op.power_cap_N(s)
    Rmax = math.exp(0.016*C/ve)**4
    dM = dM_hw_t*1e3
    P_max = (Rmax-1)*(end0+dM-f*p0)/(1-(Rmax-1)*f); tank_fixed = f*(P_max-p0)        # tankage sized once for 0.016 c
    rows = []
    for D in (45.0, 120.0, 200.0, 500.0, 1000.0):
        for vf in (0.004, 0.008, 0.012, 0.016):
            Rr = math.exp(vf*C/ve)
            prov = None; tot = None
            for _ in range(3):
                cons = (prov or 0.0)
                end = end0+dM+tank_fixed+cons
                P = (Rr**4-1)*end
                ms = [end*Rr**(4-i) for i in range(5)]
                Tb = sum((a-b)*ve/F for a, b in zip(ms, ms[1:]))
                dist = 0.0
                for a, b in zip(ms, ms[1:]):
                    tb = (a-b)*ve/F; mdot = F/ve; N = 60
                    for j in range(N):
                        t = tb*(j+.5)/N; dist += ve*math.log(a/(a-mdot*t))*tb/N
                cruise = max(0.0, 2*D*AU-dist)/(vf*C)
                tot = cruise/DAY+Tb/DAY+30
                prov = max(0.0, msn.provisioning(12, tot, 'mixed', life=life)['total_kg']-10e3)
            rows.append(dict(D_AU=D, v_c=vf, round_trip_d=tot, months=tot/30.44, burn_d=Tb/DAY, burn_AU=dist/AU, propellant_t=P/1e3,
                             tank_fill=P/P_max, tankage_t=tank_fixed/1e3, consumables_t=prov/1e3, end_t=end/1e3, departure_t=(end+P)/1e3,
                             L2_MWh=tot*24*6.0, defense_rel=[(vf/0.016)**k for k in (1, 2, 3)], dust_fluence_rel=(vf/0.016)*cruise/YR,
                             equipment_h=tot*24, feasible_36mo=tot/30.44 <= 36.0))
    best = []
    for D in (45.0, 120.0, 200.0, 500.0, 1000.0):
        rs = [r for r in rows if r['D_AU'] == D]
        ok = [r for r in rs if r['feasible_36mo']]
        slow = min(ok, key=lambda r: r['v_c']) if ok else None
        pays = []
        for a, b in zip(rs, rs[1:]):
            dd = a['round_trip_d']-b['round_trip_d']; dm = b['departure_t']-a['departure_t']
            pays.append(dict(step=f'{a["v_c"]}->{b["v_c"]} c', days_saved=dd, departure_added_t=dm, days_per_100t=100*dd/dm if dm > 0 else None))
        best.append(dict(D_AU=D, slowest_within_36mo=slow['v_c'] if slow else None, steps=pays))
    return dict(rows=rows, crossover=best, tankage_fixed_t=tank_fixed/1e3, P_max_t=P_max/1e3, hardware_added_t=dM_hw_t, finding=(
        'With one hardware set (tanks sized once for 0.016 c), a slower mission carries the same tankage and its end mass changes only by its '
        'consumables. At 45 AU every speed fits in a few months and 0.004-0.008 c costs a third to a half of the propellant; at 120-200 AU 0.008 c '
        'keeps round trips near 1-1.5 years; from ~500 AU the 0.004 c case exceeds 36 months and higher speed pays most; at 1,000 AU only 0.012-'
        '0.016 c stay inside 36 months. The table gives days saved per 100 t of departure mass for each step; the owner sets the value of a day.'))


# ======================================================================== IV-I convergence ==========================================
def convergence(s, Th, Tr, L2r, D, EC, ST):
    P3 = json.loads((R/'phase3.json').read_text())['convergence']
    end0 = op.p(s)['protected_and_operational_kg']+40.2e3; f = s['physics']['fuel_loads']['tank_dry_fraction']; p0 = op.p(s)['legacy_inventory_kg']
    Rn = op.mission(s)['mass_ratio_per_burn']**4
    base_P = (Rn-1)*(end0-f*p0)/(1-(Rn-1)*f); base_dep = end0+f*(base_P-p0)+base_P
    def coupled(dM_t):
        dM = dM_t*1e3; P = (Rn-1)*(end0+dM-f*p0)/(1-(Rn-1)*f); end = end0+dM+f*(P-p0)
        return dict(propellant_t=P/1e3, tankage_t=f*(P-p0)/1e3, departure_t=(end+P)/1e3, extra_departure_t=(end+P-base_dep)/1e3)
    cand = []
    for c in P3['candidates']:
        tot = c['dry_added_t']; cc = [coupled(t) for t in tot]
        cand.append(dict(name=c['name'], source='Phase III (recoupled on the corrected base)', dry_added_t=tot, coupled=cc,
                         status=dict(thermal='does not close in burns (IV-D: WARM/LOW heated by hot blades)', electrical='see IV-E', protection='OPEN',
                                     radiation='TRANSPORT GATE open'), still_valid='no' if c['name'].startswith('N2') else 'reference'))
    l2 = next(r for r in L2r['rows'] if r['Pe_W'] == 3.5e6 and r['strategy'].startswith('C'))['mass_t']
    H5 = next(r for r in Tr['rows'] if r['name'].startswith('H5'))
    H1 = next(r for r in Tr['rows'] if r['name'].startswith('H1'))
    baffle = Th['baffle']['mass_t']       # relocation of the existing bulkhead (re-support, longer coolant runs)
    # L2 rejection temperature scan for the burn sink (two units carrying the ship, one in standby): shorter section vs larger reactor
    scan = []
    for T in (550.0, 650.0, 700.0, 750.0):
        S = section(2, 3.5e6, T_rej=T, band=1, standby_units=1, F_hot=3e-4)
        p = eps_b.fission_plant(3.5e6, T, 80.0, 1, 2.69e4, EPS); U = eps_g1.unit(Pe_W=3.5e6, eta=p['eta'], T_rej=T, n_running=3, i=1)
        scan.append(dict(T_K=T, eta=S['eta'], length_m=S['length_m'], hot_capacity_W=S['hot_capacity_W'],
                         unit_t=(sum(v for k, v in p['parts_kg'].items() if k not in ('shield', 'rejection'))+U['shadow_kg']+U['slab_kg'])/1e3))
    T_sel = 700.0
    sec = [section(2, 3.5e6, T_rej=T_sel, band=i, standby_units=1, F_hot=3e-4) for i in B]
    sec_t = [x['geometric_area_m2']*(0.3, 0.5, 0.8)[i]/1e3+(2.0, 4.0, 8.0)[i] for i, x in enumerate(sec)]
    tank_side = [0.0, 3.0, 10.0]          # scatter allowance (side shielding toward the blades and casing): OPEN until 3-D transport
    restart = [2.0, 3.5, 6.5]; buf = [9.3+3.0, 14.0+4.0, 19.1+6.0]; l3 = [9.0, 12.0, 16.0]; dist = [4.0, 8.0, 15.0]
    ecl = [x-2*6/4*u for x, u in zip(EC['rows'][2]['mass_t'], (0.9, 1.2, 1.6))]
    l1_t = [(0.1e6+H5['pump_W'][i])/1e3*(1.5, 3.0, 5.0)[i]/1e3+s3.q_area((0.1e6+H5['pump_W'][i])*(1/0.3-1), 900.0)/2*(6, 10, 15)[i]/1e3 for i in B]
    l2_700 = []
    for i in B:
        p = eps_b.fission_plant(3.5e6, T_sel, 80.0, i, 2.69e4, EPS); U = eps_g1.unit(Pe_W=3.5e6, eta=p['eta'], T_rej=T_sel, n_running=3, i=i)
        l2_700.append(3*(sum(v for k, v in p['parts_kg'].items() if k not in ('shield', 'rejection'))+U['shadow_kg']+U['slab_kg'])/1e3)
    ext_struct = [x['geometric_area_m2']/2*k/1e3 for x, k in zip(sec, (3.0, 4.0, 6.0))]
    common = dict(L2=l2_700, L1=l1_t, L3=l3, storage=[b+r for b, r in zip(buf, restart)], distribution=dist, scatter_allowance=tank_side,
                  ECLSS_modular=ecl, heat_transport_H5=H5['mass_t'])
    def cand_add(name, extra, status, valid, **kw):
        items = dict(common); items.update(extra)
        tot = [sum(v[i] for v in items.values()) for i in B]; noT = [x-H5['mass_t'][i] for i, x in enumerate(tot)]
        cand.append(dict(name=name, source='Phase IV', items_t=items, dry_added_t=tot, dry_added_without_transport_t=noT,
                         coupled=[coupled(x) for x in tot], coupled_without_transport=[coupled(x) for x in noT], status=status, still_valid=valid, **kw))
    hot_margin = 14.40e9-10.45e9
    cand_add('N2-R4a: 3 x 3.5 MWe (C), 700 K section on the hot-blade forward end, bulkhead moved aft of it (silhouette kept)',
             dict(section_700K=sec_t, bulkhead_relocation=baffle),
             dict(thermal=f'L2 sink works behind the relocated bulkhead (F < 1e-3); takes {sec[1]["length_m"]:.0f} m = {sec[1]["hot_capacity_W"]/1e9:.1f} GW of hot capacity against '
                          f'{hot_margin/1e9:.2f} GW ideal margin (fits) and 1.9 GW with the 20 % rule (does not); WARM/LOW unchanged',
                  electrical='closes after one loss at EOL to the nominal band', protection='OPEN (dust doctrine, DR3-02)',
                  radiation='TRANSPORT-INFORMED tank band; 3-D gate open'),
             'leading research candidate if the hot-blade margin rule can be relaxed (not closed)', length_m=[x['length_m'] for x in sec])

    return dict(base=dict(end_t=(end0+f*(base_P-p0))/1e3, propellant_t=base_P/1e3, departure_t=base_dep/1e3, note='includes CIRC-001 (IV-A 3.2)'),
                candidates=cand, T_scan=scan, T_selected=T_sel, claim_283t=('The Phase III N2 figure (283 t dry, +1,035 t departure) is no longer valid: its 550 K section does not '
                                             'reject in burns, its 2.66 MWe units fail after one loss at EOL, and it carried no tank-side shield, '
                                             'restart pack, transport hardware or ECLSS cross-ring unit.'),
                no_r4b='A forward-extension alternative (700 K beyond LOW) is not carried: it collides with the aft storage front at x 93.4.')


def problems():
    P = [
        ('P4-01', 'BLOCKER', 'The Phase III 550 K section sits aft of the graded bulkhead and sees the other blades\' 1800 K faces (F 0.02): it absorbs '
         '2-3x what it emits', 'option F as drawn has no L2 sink in a burn; the bulkhead must move aft of any new section (N2-R4a)'),
        ('P4-02', 'MAJOR', 'Scatter toward the He-3 tanks (blades, casing, tank structure) is not assessed; the direct path closes inside the shadow cone', '3-D transport needed before tank protection is closed'),
        ('P4-03', 'BLOCKER', 'No 3-D radiation transport with the real geometry (district, blades, tanks)', 'crew and tank safety not established; workflow now exists'),
        ('P4-04', 'MAJOR', 'Hot-loop transport: 4-34 MW pump work and 150-700 t of lithium in trunks and channels (by candidate); in no mass line', 'drive package / radiator mass OPEN'),
        ('P4-05', 'MAJOR', 'CIRC-001 (40.2 t) is in the mass model but not the operating point end mass', 'propellant under-solved by ~93 t; departure ~4,573 t'),
        ('P4-06', 'MAJOR', 'Hot-blade 20 % margin rule: 10.45 GW x 1.2 = 12.5 GW of 14.4 GW leaves 1.9 GW (21 m) for anything taken from the blade', 'option F length (29-37 m) does not fit'),
        ('P4-07', 'MAJOR', '2.66 MWe units fail after one loss at EOL once planning loads, recharge and standby are counted', 'rating >= 3.0-3.5 MWe'),
        ('P4-08', 'MAJOR', 'LOW at the high band with one sector lost needs ~2.0 MW (1.28 MW available)', 'LOW extension ~11 m or load shedding'),
        ('P4-09', 'MAJOR', 'Five ECLSS units do not carry 12 after a ring loss', '7 units (cross-ring hub unit) needed'),
        ('P4-10', 'MAJOR', 'Secondary gammas in LiH relax over ~33 cm (neutrons 7.7 cm): beyond ~40 cm LiH the gamma term dominates', 'shield needs a gamma layer after the LiH'),
        ('P4-11', 'OPEN', 'Defense power vs speed: v^3 has no source (v^1-v^3)', 'mission protection power uncertain by up to 8x at 0.008 c'),
        ('P4-12', 'OPEN', 'Relocated bulkhead: its own heat balance at the new station and the coolant headers crossing it', 'research variant only'),
        ('P4-16', 'MAJOR', 'Phase III tank geometry error (span read as ship x): tanks are ~200 m forward, inside the shadow cone', 'Phase III P3-05 withdrawn'),
        ('P4-13', 'OPEN', 'Surrogate core: leakage per fission depends on the real reactor (OPEN, no core design)', 'transport results are scalable, not final'),
        ('P4-14', 'MINOR', 'Phase III ECLSS premium misprinted (2-3 t vs 9.6 t)', 'corrected'),
        ('P4-15', 'MINOR', 'Container tare missing from Phase III logistics', 'corrected: +10-20 t departure'),
    ]
    return [dict(id=a, severity=b, problem=c, consequence=d) for a, b, c, d in P]


def decisions():
    D = [
        ('DR4-01', 'Take N2-R4a as the radiator research variant: 700 K L2 section on the hot-blade forward end with the graded bulkhead moved aft of it', 'R4a'),
        ('DR4-02', 'Move the L2 study rating to 3 x 3.5 MWe, strategy C (3 at partial load), strategy B as maintenance mode', '3 x 3.5, C'),
        ('DR4-03', 'Take H5 (six independent pumped zones per blade with Li heat-pipe fins) as the hot-transport study basis, as a propulsion-interface request', 'H5'),
        ('DR4-04', 'Keep the 12.5 deg shadow cone as the tank protection (tanks at ~200 m, <= 8 deg off axis) and carry a 0-10 t scatter allowance until 3-D transport', 'yes'),
        ('DR4-05', 'Couple CIRC-001 into the operating point end mass (owner/canon change; not done here)', 'owner'),
        ('DR4-06', 'Adopt 7 modular ECLSS units (3 + 3 + 1 cross-ring hub unit)', '7 units'),
        ('DR4-07', 'Adopt the independent restart pack (2-6 t) for R1b; study an APU as its alternative', 'pack'),
        ('DR4-08', 'Commission a 3-D OpenMC model of the district, blades and tank farm with the IV-B workflow (local or CI-side)', 'yes'),
        ('DR4-09', 'Choose how to value mission days against departure mass for the speed choice (IV-H)', 'owner'),
    ]
    return [dict(id=a, question=b, recommended=c) for a, b, c in D]


def next_sequence():
    return ['1. Owner decisions DR4-01..09 (R4a bulkhead relocation, rating, transport basis, tank protection, CIRC-001 coupling).',
            '2. 3-D OpenMC model: district (three units, slabs, shadow walls), blades as scatterers, He-3 tank stack; crew dose and 3 K deposit.',
            '3. R4a variant: the relocated bulkhead\'s heat balance from a radiosity model, and the hot-blade margin rule (owner).',
            '4. Hot-transport interface with propulsion (H5): pump hardware, Li inventory, mass line.',
            '5. Dust doctrine (DR3-02) to fix the engagement pattern; then size the buffer once.',
            '6. Only then: EPS-G1 generator geometry for the selected district (owner go).']


def main():
    s = spec.load()[0]
    pl = json.loads((ROOT/'references/p1_power_loads.json').read_text())
    E = json.loads((R/'phase2_eps_b.json').read_text()); planning = E['demand']['planning_open_W']
    life = tomllib.loads((ROOT/'data/life_support.toml').read_text())
    RT = reconcile_thermal(); RM = reconcile_mass(s)
    Tr = transport(s); Th = thermal(s, pl, planning); L2r = l2(pl, planning); ST = storage(); D = district(s); EC = eclss(); LG = logistics()
    CV = convergence(s, Th, Tr, L2r, D, EC, ST)
    dM = next(c for c in CV['candidates'] if c['name'].startswith('N2-R4a'))['dry_added_t'][1]
    MI = missions(s, dM, life)
    L1c = dict(rows=[dict(case='Phase III N2 (0.6 MW)', condition='L2 carries the ship in burns AND no hot-loop pumps (heat-pipe hot blades)', L1_W=0.6e6),
                     dict(case='With H1 pumped loop', condition='derived pump work', L1_W=0.6e6+next(r for r in Tr['rows'] if r['name'].startswith('H1'))['pump_W'][1]),
                     dict(case='With H5 zones + fins', condition='derived pump work', L1_W=0.6e6+next(r for r in Tr['rows'] if r['name'].startswith('H5'))['pump_W'][1]),
                     dict(case='Parasitic: Li trace heating and pre-heat', condition='before ignition, from L2', L1_W=None)],
               finding='The 0.6 MW L1 is conditional on two things that Phase IV does not find: an L2 sink in burns (needs the bulkhead moved aft of a new section) and pump-free '
                       'hot transport (not credible over 160 m). With H5 the L1 load is ~5-10 MW, dominated by hot-loop pumps.')
    CL = dict(terms=[('individual-state thermal closure', 'every active circuit of one state passes at one band'),
                     ('all-conditions thermal closure', 'every state passes at every band with one sector or unit lost'),
                     ('electrical availability', 'demand met after one unit loss at EOL, with restore time stated'),
                     ('protection availability', 'proactive defense held in every state incl. transitions (dust doctrine OPEN)'),
                     ('radiation closure', 'crew dose and 3 K deposit within limits from 3-D transport'),
                     ('whole-ship closure', 'all of the above plus the coupled mass ledger')],
              status={'N2 (Phase III)': ['coast only', 'no', 'no at EOL', 'no (burn gap)', 'not assessed', 'no'],
                      'N2-R4a': ['yes (bulkhead moved aft)', 'no (LOW high band, sector lost)', 'yes', 'OPEN', 'TRANSPORT-INFORMED only', 'no']})
    out = dict(status='ISSA Phase IV STUDY (NONCANON)', reconcile_thermal=RT, reconcile_mass=RM, l1_conditional=L1c, closure_terms=CL, eclss=EC,
               transport=Tr, thermal=Th, l2=L2r, storage=ST, district=D, logistics=LG, missions=MI, convergence=CV, problems=problems(),
               decisions=decisions(), next_sequence=next_sequence(),
               radiation=dict(bench=json.loads((R/'phase4_rad_bench.json').read_text()), wayfarer=json.loads((R/'phase4_rad_wayfarer.json').read_text())))
    (R/'phase4.json').write_text(json.dumps(out, indent=1, default=lambda o: None if o == math.inf else str(o)).replace('Infinity', 'null'))
    print('mass', [(r['item'][:30], None if r['t'] is None else round(r['t'], 1)) for r in RM['rows']])
    print('recon', [(r['figure'], round(r.get('length_m', 0) or 0, 1)) for r in RT['rows']], [(r['band'], r['F_hot'], round(r['length_m'], 1) if r['length_m'] != math.inf else 'inf') for r in RT['reconciled']])
    for r in Tr['rows']: print('H', r['name'][:40], [round(x/1e6, 1) for x in r['pump_W']], [round(x) for x in r['inventory_t']], [round(x) for x in r['mass_t']])
    print('fin L', round(Tr['fin_capillary_length_m'], 2), 'pv', round(Tr['li_vapour_pressure_1800K_Pa']))
    for r in Th['view_factors']: print('VF', r['surface'][:40], r['F_hot'], round(r['ratio'], 2), round(r['T_equilibrium_no_load_K']))
    for r in Th['baffle_scan']: print('BF', r['baffle_R_m'], r['surface'], r['F_hot'], round(r['ratio'], 3))
    print('allow', {k: (round(v, 1) if isinstance(v, float) else v) for k, v in Th['hot_allowance'].items() if k.startswith('L_')}, 'LOWext', round(Th['low_extension']['added_length_m'], 1))
    print('L2 opt', r3([x/1e6 for x in L2r['optimum_Pe_W']]), 'demand', r3([x/1e6 for x in L2r['demand_W']]))
    for r in L2r['rows']: print('L2', r['Pe_W']/1e6, r['strategy'][:3], 'EOL imm', r3([x/1e6 for x in r['margins']['EOL']['immediate_after_loss']], 2), 'restored', r3([x/1e6 for x in r['margins']['EOL']['one_unit']], 2), [round(x) for x in r['mass_t']])
    for r in ST['patterns']:
        if r['band'] == 'nominal': print('ST', r['pattern'], r['best'], round(r['mass_t'], 1), r['limited_by'], round(r['recharge_W']/1e6, 2))
    print('district', 'lam', round(D['transport']['lambda_n_cm'], 1), 'need T', D['needed_transmission'], 'LiH cm', round(D['needed_LiH_cm']))
    for r in D['tank_rows']: print('tank', r['Pe_W']/1e6, r['side_shield_cm_LiH_after_5cm_W'], round(r['he3_W_per_tank_per_unit'], 2), round(r['wall_W_per_tank_per_unit'], 2))
    for r in EC['rows']: print('EC', r['option'], r['checks'])
    for r in LG['rows']: print('LG', r)
    for r in MI['crossover']: print('MI', r['D_AU'], r['slowest_within_36mo'], [(x['step'], round(x['days_saved']), round(x['departure_added_t']), None if x['days_per_100t'] is None else round(x['days_per_100t'], 1)) for x in r['steps']])
    for r in MI['rows']:
        if r['D_AU'] in (45.0, 500.0): print('M', r['D_AU'], r['v_c'], round(r['months'], 1), round(r['propellant_t']), round(r['departure_t']), round(r['consumables_t'], 1))
    for c in CV['candidates']: print('CV', c['name'][:45], [round(x) for x in c['dry_added_t']], [round(x['extra_departure_t']) for x in c['coupled']], [round(x) for x in c.get('dry_added_without_transport_t', [])])
    print('Tscan', [(r['T_K'], round(r['length_m'], 1), round(r['unit_t'], 1)) for r in CV['T_scan']])
    print('base', CV['base'])


if __name__ == '__main__':
    main()
