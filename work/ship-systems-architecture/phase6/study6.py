"""ISSA Phase VI: dual-baseline integration (STUDY, NONCANON). Pure Python; reads the spec, the Phase III-V results, the fictional technology
register (data/technology_register.toml) and, when rad6.py has run, results/phase6_rad.json; writes results/phase6.json and the two
machine-readable baselines results/phase6_config_R.json (Track R, research) and results/phase6_config_F.json (Track F, fiction).

    python3 work/ship-systems-architecture/phase5/study5.py      (Phase V inputs)
    /opt/mf/envs/omc/bin/python work/ship-systems-architecture/phase6/rad6.py     (optional, OpenMC)
    python3 work/ship-systems-architecture/phase6/study6.py

Track R = what today's physics and engineering support (Phase V research hardware, corrected here). Track F = the idealized hard-SF ship:
the same physics, plus the advances written in the register (FT-xx), each Track F value naming the entry it depends on. F0 uses only the
owner-approved entries before 2026-11-28; F1 adds FT-03 (1500 K L2 turbines, approved by the owner 2026-11-28 07:03Z) and is the Track F reference. Cases are correlated sensitivity cases (opt/nom/cons),
not statistical bounds. Every value here is STUDY / PROTOTYPE unless it cites canon.
"""
import copy
import hashlib
import json
import math
import sys
import tomllib
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORK = HERE.parent
ROOT = WORK.parents[1]
R = WORK/'results'
for p in (ROOT/'src/wayfarer', WORK/'phase2', WORK/'phase3', WORK/'phase4', WORK/'phase5', HERE):
    sys.path.insert(0, str(p))
import spec  # noqa: E402
import operating_point as op  # noqa: E402
import mass_model as mm  # noqa: E402
import fuel_storage as fs  # noqa: E402
import habitat_ring  # noqa: E402
import study as s3  # noqa: E402
import study4 as s4  # noqa: E402
import study5 as s5  # noqa: E402
import hot  # noqa: E402

B = (0, 1, 2); CASES = hot.CASES; G0 = 9.80665; SIG = s3.SIG; EPS = s3.EPS
MARGIN = 1.2; ABSORBED = s5.ABSORBED; PER_M_HOT = s5.PER_M_HOT; CIRC = s5.CIRC
BULK = s4.BULKHEAD_X                    # 50.4: aft edge of WARM, forward end of the hot blades
HOT_X0 = s5.HOT_X0                      # -111.6: aft end of the hot length
REG = tomllib.loads((ROOT/'data/technology_register.toml').read_text())
FT = {t['id']: t for t in REG['technology']}
COMPOSITE = FT['FT-01']['adopted']
DC_ETA = FT['FT-04']['adopted']['efficiency']
PUMP_FACTOR = (1800.0/450.0-1)/0.5      # canon burn heat-pump work per W lifted (thermal.loops.architecture: eta_II 0.5, 450 K -> 1800 K)


def r3(x, n=3):
    return [round(v, n) for v in x]


def h(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()[:12]


# ============================================================================ hot network with a chosen material ====================
def h6a(L_hdr, a_g, sigma=None, rho=None, i=1):
    """H6a network for one blade (x3 at the caller) with the hot length L_hdr. sigma/rho None = research (Mo-Re class, per case)."""
    keep = (hot.SIGMA_ALLOW, hot.WALL['rho'], hot.T_WALL_MAX)
    if sigma:
        hot.SIGMA_ALLOW = (sigma*1.2, sigma, sigma*0.8); hot.WALL['rho'] = rho; hot.T_WALL_MAX = (2100.0, 2050.0, 2000.0)
    try:
        n = hot.network(hot.TOPOLOGIES[4], ABSORBED/3, L_hdr, a_g*G0, i=i)
    finally:
        hot.SIGMA_ALLOW, hot.WALL['rho'], hot.T_WALL_MAX = keep
    return n


def h6a_all(L_hdr, a_g, fictional):
    sig = COMPOSITE['allowable_stress_Pa'] if fictional else None; rho = COMPOSITE['density_kg_m3'] if fictional else None
    nets = [h6a(L_hdr, a_g, sig, rho, i) for i in B]
    return dict(total_t=[3*n['hardware_kg']/1e3 for n in nets], pump_W=[3*n['pump_W'] for n in nets], inventory_t=[3*n['inventory_kg']/1e3 for n in nets],
                by_item_t={k: [3*n['mass_kg'][k]/1e3 for n in nets] for k in nets[1]['mass_kg']}, net=nets[1],
                startup=hot.startup(nets[1], L_hdr), wall_over_limit=[n['wall_over_T_limit'] for n in nets])


# ============================================================================ VI-A 4.3 radiator consistency =========================
def eta_part(f, k=0.3):
    """closed-Brayton part-load efficiency factor (inventory control nominal k 0.3; Phase V V-D)."""
    return max(0.0, 1-k*(1-f)**2) if f >= 0.3 else 0.0


def l2_radiator(T_rej, eta, Pe=3.5e6, i=1):
    """Cross-strapped dual-header L2 sections at T_rej with a given full-load efficiency: two survivors at 100 % after a trip (strategy C).
    Uses the Phase IV relation (s4.section) so the 750 K research row reproduces Phase V exactly."""
    x = s4.section(2, Pe, T_rej=T_rej, band=i, standby_units=0, F_hot=3e-4, eta=eta)
    waste_full = Pe*(1/eta-1)
    return dict(T_K=T_rej, eta=eta, length_m=x['length_m'], area_m2=x['geometric_area_m2'], waste_per_unit_full_W=waste_full,
                capacity_W=2*waste_full*MARGIN, header_t=x['length_m']*3*2*0.15)


def radiator_consistency(P5):
    """700 K values left inside the 750 K configuration, and the margins after a cooling-section failure."""
    Rd = P5['radiators']; e750 = Rd['l2_750']['eta']; e700 = Rd['l2_700']['eta']
    found = [
        dict(where='phase5 config generation.L2.rejection_T_K', was='700 K', now='750 K (R5-A)', effect='label only; the ledgers already used 750 K'),
        dict(where='phase5 config radiators.L2', was='700 K, 24 m, x 26.4-50.4', now=f'750 K, {Rd["l2_750"]["cross"]["length_m"]:.1f} m, x {BULK-Rd["l2_750"]["cross"]["length_m"]:.1f}-{BULK:.1f}',
             effect='geometry label; the review file already drew 20.5 m'),
        dict(where='phase5 transport(): hot header length', was='162 - 24 = 138 m (700 K section)', now=f'162 - {Rd["l2_750"]["cross"]["length_m"]:.1f} = {162-Rd["l2_750"]["cross"]["length_m"]:.1f} m',
             effect='H6a recomputed below on the R5-A length'),
        dict(where='phase5 electrical(): part-load efficiency base', was=f'0.164 (700 K full-load)', now=f'{e750:.3f} (750 K full-load)',
             effect='part-load waste recomputed below'),
        dict(where='phase5 radiators(): bulkhead radiosity cold side', was='700 K', now='750 K', effect='bulkhead layer temperatures below'),
        dict(where='phase5 rad3d.py bulkhead station', was='x 26.2 (aft of a 24 m section)', now=f'x {BULK-Rd["l2_750"]["cross"]["length_m"]-0.2:.1f}',
             effect='3 mm Al layer moved 3.7 m; rerun in rad6.py (effect on tallies within statistics)'),
        dict(where='phase5 R5-C emitter Monte Carlo', was='700 K', now='kept (rejected variant, 700 K is its own design point)', effect='none'),
    ]
    # part-load: strategy C runs three units at 2/3 of rating; efficiency falls, waste rises above the linear share
    w_full = 3.5e6*(1/e750-1)
    part = []
    for f in (0.5, 2/3, 0.8, 1.0):
        e = e750*eta_part(f)
        part.append(dict(load_frac=f, eta=e, waste_per_unit_W=f*3.5e6*(1/e-1), linear_W=f*w_full))
    cap_true = Rd['l2_750']['cross']['area_m2']*EPS*SIG*750.0**4*0.9      # what the installed area rejects without margin
    cap_rule = cap_true                                                    # area already carries the 1.2 margin (2 units x full x 1.2)
    p23 = next(p for p in part if abs(p['load_frac']-2/3) < 1e-9)
    loads = dict(C_part_load=3*p23['waste_per_unit_W'], C_linear=3*p23['linear_W'], two_survivors_full=2*w_full)
    # failures: one L2 section (one of three blades) lost -> two thirds of the area; one H6a section (1 of 18); one trunk of a pair
    hot_cap = (162.0-Rd['l2_750']['cross']['length_m'])*PER_M_HOT
    fails = [
        dict(case='intact, strategy C (3 units at 2/3, part-load efficiency)', capacity_W=cap_rule, load_W=loads['C_part_load']),
        dict(case='trip: two survivors at 100 %', capacity_W=cap_rule, load_W=loads['two_survivors_full']),
        dict(case='one L2 section lost (one blade), strategy C', capacity_W=cap_rule*2/3, load_W=loads['C_part_load']),
        dict(case='one L2 section lost + one unit tripped (two survivors at 100 %)', capacity_W=cap_rule*2/3, load_W=loads['two_survivors_full']),
    ]
    def max_output(cap, units):
        lo, hi = 0.0, 1.0                                # share of rating per running unit at which the waste equals the capacity
        for _ in range(60):
            f = (lo+hi)/2; e = e750*eta_part(f)
            w = units*f*3.5e6*(1/e-1) if e else 0.0
            lo, hi = (f, hi) if w <= cap else (lo, f)
        return units*lo*3.5e6
    for f in fails:
        f['margin'] = f['capacity_W']/f['load_W']-1
        f['max_output_W'] = max_output(f['capacity_W']/MARGIN if f['margin'] < 0 else f['capacity_W'], 2 if 'survivors' in f['case'] else 3)
        f['note'] = ('closes with the 20 % margin' if f['margin'] >= 0 else
                     'margin used: units throttle to the output the remaining sections reject without margin')
    hfail = []
    for case, lost in (('intact', 0.0), ('one H6a section (1 of 6 on one blade)', 1/6), ('one trunk of a pair (60 % path rating)', 0.4),
                       ('isolation valve fails open: two sections', 2/6), ('whole blade', 1.0)):
        cap = hot_cap-hot_cap/3*lost
        hfail.append(dict(case=case, capacity_W=cap, margin=cap/ABSORBED-1, meets_20pct=cap >= MARGIN*ABSORBED,
                          drive_power_at_20pct=min(1.0, cap/(MARGIN*ABSORBED)), drive_power_no_margin=min(1.0, cap/ABSORBED)))
    bk = dict(intact=s5.bulkhead_radiosity(1000.0, 750.0), one_layer_lost=s5.bulkhead_radiosity(1000.0, 750.0, n_layers=2),
              holed_5pct=s5.bulkhead_radiosity(1000.0, 750.0, damaged=0.05))
    return dict(found=found, part_load=part, l2_loads=loads, l2_capacity_W=cap_rule, l2_failures=fails, hot_capacity_W=hot_cap, hot_failures=hfail,
                bulkhead=bk, finding=None)


# ============================================================================ VI-A 4.2 electrical states ============================
def electrical_states(P5, pumps_R, pumps_F, warm_short_W):
    """Installed rating, continuous, intermittent, startup energy, peak and storage discharge per item and operating state."""
    pl = json.loads((ROOT/'references/p1_power_loads.json').read_text())
    I = pl['items']; st = pl['states']
    hp = next(r for r in st['HIGH_THRUST']['loads'] if r['id'] == 'TMS.BURN_HEAT_PUMPS')
    hpp = next(r for r in st['HIGH_THRUST_PROACTIVE']['loads'] if r['id'] == 'TMS.BURN_HEAT_PUMPS')
    lift = warm_short_W*MARGIN; w_hp = lift*PUMP_FACTOR
    P4 = json.loads((R/'phase4.json').read_text()); dem = P4['l2']['demand_W']
    def item(iid, title, installed, cont_pro, cont_react, intermittent, startup_J, peak, storage, bus, basis, cls):
        return dict(id=iid, title=title, installed_W=installed, continuous_proactive_burn_W=cont_pro, continuous_reactive_burn_W=cont_react,
                    intermittent_W=intermittent, startup_J=startup_J, peak_W=peak, storage_discharge_W=storage, bus=bus, basis=basis, cls=cls)
    eye = I['PROT.EYE_BURN_WATCH']['W'][1]
    rows_R = [
        item('PROT.EYE_BURN_WATCH', I['PROT.EYE_BURN_WATCH']['title'], eye, eye, eye, 0.0, 0.0, eye, 0.0, 'L1', 'canon SPEC', 'DRIVE-SPECIFIC'),
        item('PROP.FEED_PUMPS', 'Propellant boost pumps and conditioning (OPEN in canon)', 1.0e6, 0.5e6, 0.5e6, 0.0, 0.0, 1.0e6, 0.0, 'L1', 'estimate 0.2-1.0 MW', 'OPEN'),
        item('TMS.HOT_LOOP_PUMPS', 'H6a EM pumps (Track R walls)', pumps_R*1.25, pumps_R, pumps_R, 0.0, 0.0, pumps_R, 0.0, 'L1', 'derived (H6a, R5-A length, coupled acceleration)', 'DERIVED'),
        item('TMS.BURN_HEAT_PUMPS', 'Burn heat pumps (canon F02 rating 210 MW at burnout, reactive defense)', I['TMS.BURN_HEAT_PUMPS']['W'][1],
             w_hp, hp['W'][1], hp['W'][1]-w_hp, 0.0, hp['W'][1], 0.0, 'L1',
             f'proactive doctrine (working): canon ledger runs them at {hpp["W"][1]/1e6:.0f} W; Phase VI adds the WARM shortfall lift '
             f'{lift/1e6:.2f} MW (incl. 20 %) x {PUMP_FACTOR:.0f} = {w_hp/1e6:.1f} MW. Reactive in a burn: canon HIGH_THRUST {hp["W"][1]/1e6:.0f} MW at burnout '
             '(defense heat ~ (t/T)^3, burn average ~1/4 of that). The 210 MW rating is installed equipment, never continuous demand.', 'EXISTING (canon)'),
        item('PROP.PULSE_DISCHARGE', 'Pulse bank discharge into startup heating and seed field', 50e6, 0.0, 0.0, 0.0, None, 50e6, 50e6, 'pulse bank',
             'storage discharge at ignition only; not a generation load', 'EXISTING (canon)'),
        item('EPS.PULSE_CHARGE', 'Main battery / L2 charging the pulse bank', I['EPS.PULSE_CHARGE']['W'][2], 0.0, 0.0, I['EPS.PULSE_CHARGE']['W'][1], None,
             I['EPS.PULSE_CHARGE']['W'][2], 0.0, 'A', 'before ignition, from L2 surplus', 'EXISTING (study)'),
        item('ISSA.COOLDOWN', 'cooldown circulation after a burn (25 % flow)', pumps_R*0.016, 0.0, 0.0, pumps_R*0.016, 0.0, pumps_R*0.016, 0.0, 'L2 / ride-through',
             'cube law at 25 % flow', 'DERIVED'),
    ]
    rows_F = copy.deepcopy(rows_R)
    for r in rows_F:
        if r['id'] == 'TMS.HOT_LOOP_PUMPS':
            r.update(title='H6a EM pumps (Track F composite walls, FT-01/02)', installed_W=pumps_F*1.25, continuous_proactive_burn_W=pumps_F,
                     continuous_reactive_burn_W=pumps_F, peak_W=pumps_F, basis='derived (H6a at the FT-01 allowable; larger, slower trunks)')
        if r['id'] == 'ISSA.COOLDOWN':
            r.update(installed_W=pumps_F*0.016, intermittent_W=pumps_F*0.016, peak_W=pumps_F*0.016)
    def sums(rows):
        L1 = [r for r in rows if r['bus'] == 'L1']
        return dict(continuous_proactive_W=sum(r['continuous_proactive_burn_W'] for r in L1),
                    continuous_reactive_W=sum(r['continuous_reactive_burn_W'] for r in L1),
                    installed_W=sum(r['installed_W'] for r in L1), phase5_counted_W=None)
    sR, sF = sums(rows_R), sums(rows_F)
    p5 = P5['electrical']['L1']; sR['phase5_counted_W'] = p5['drive_specific_W'][1]+p5['existing_W'][1]
    # L2 demand and preheat duration
    avail = dict(BOL=3*3.5e6*1.0*0.97*0.95, EOL=3*3.5e6*0.90*0.97*0.95, one_unit_EOL=3.5e6*0.90*0.97*0.95)
    l2 = dict(demand_W=dem, available_W=avail, surplus_coast_W={k: v-dem[1] for k, v in avail.items() if k != 'one_unit_EOL'},
              note='L2 demand = Phase IV ledger (proactive + planning + recharge + standby); pulse charging comes from this surplus before ignition')
    return dict(R=rows_R, F=rows_F, sum_R=sR, sum_F=sF, heat_pump=dict(installed_W=I['TMS.BURN_HEAT_PUMPS']['W'][1], rated_lift_basis='35 MW at burnout (5 MW machinery + 30 MW defense)',
                proactive_W=w_hp, proactive_lift_W=lift, reactive_peak_W=hp['W'][1], reactive_lift_W=hp['lift_W'][1], reactive_mean_W=hp['W'][1]/4, factor=PUMP_FACTOR),
                L2=l2)


# ============================================================================ VI-C direct conversion (FT-04) ========================
def direct_conversion(s, P_e_cases, hot_headroom_W, pumps_heat_W):
    """Energy and momentum ledger of an inductive pickup on the existing magnetic nozzle (FT-04). P_e_cases: {label: electrical W}."""
    p = op.p(s); ve = p['exhaust_velocity_m_s']; F = op.power_cap_N(s); Pj = F*ve/2; Pf = Pj/p['directed_efficiency']
    Pabs = Pf*p['absorbed_fraction']
    rows = []
    for label, Pe in P_e_cases.items():
        for k, eta in enumerate(DC_ETA):
            Px = Pe/eta; loss = Px-Pe
            dF = -0.5*Px/Pj                           # constant mass flow: F = mdot v, P = F v / 2 -> dF/F = dP/2P
            rows.append(dict(state=label, case=CASES[k], P_e_W=Pe, eta=eta, extracted_from_jet_W=Px, loss_to_hot_loop_W=loss,
                             thrust_change_rel=dF, ve_change_rel=dF, extra_propellant_rel=-dF,
                             hot_load_added_W=loss, hot_headroom_W=hot_headroom_W,
                             fits_hot_headroom=loss+pumps_heat_W.get(label, 0.0) <= hot_headroom_W))
    buffer = []
    for f in (10.0, 196.0, 1000.0):                   # pulse rate: parameter (196 Hz = Vertex V4 research value, sensitivity only)
        for Pe in (20e6, 100e6):
            E = Pe/f; buffer.append(dict(rate_Hz=f, P_e_W=Pe, energy_per_pulse_J=E, buffer_J=2*E, capacitor_t=2*E/2.0e3/1e3))
    ledger = dict(fusion_W=Pf, jet_W=Pj, absorbed_W=Pabs, other_W=Pf-Pj-Pabs, thrust_N=F, ve_m_s=ve,
                  note='P_fusion = P_jet + P_absorbed + P_other; the pickup takes P_e/eta from the jet (thrust falls by half that share at constant '
                       'mass flow); the loss is deposited in the pickup winding inside the existing nozzle structure and carried by the H6a loop to the '
                       'HOT radiators (1800 K): a real sink, inside the 20 % rule only while it fits the HOT headroom')
    startup = dict(rule='direct conversion produces power only while the drive burns: ignition, preheat and restart come from the pulse bank, '
                        'the main battery and L2 (continuous generation and stored pulse energy are separate)',
                   first_pulses='pulse bank (canon 50 MW discharge)', steady='DC feeds L1 after ignition; the pulse bank recharges from DC')
    physics = [
        dict(principle='Faraday induction (flux change in a pickup winding as the burn plasma expands against the nozzle field)', precedent='Daedalus induction loop (BIS 1978); '
             'pulsed inductive recovery in magneto-inertial fusion experiments', limit='steady flow induces no EMF: needs a pulsed or modulated exhaust'),
        dict(principle='Electrostatic deceleration of ions (Venetian blind)', precedent='Moir & Barr 1973 design studies, 50-70 % calculated', limit='large grid area in the beam; grid erosion'),
        dict(principle='Travelling-wave direct energy converter (TWDEC)', precedent='Momota et al. for D-3He 14.7 MeV protons, ~60-70 % calculated', limit='never demonstrated at power'),
    ]
    return dict(ledger=ledger, rows=rows, buffer=buffer, startup=startup, physics=physics, register='FT-04 (CONDITIONAL)',
                thermal='Track R keeps thermal conversion at 0.27 with a ~900 K reject (no radiator, OPEN). Track F replaces the 900 K cycle by DC losses at '
                        '~1900 K into the HOT loop: the rejection requirement moves to HOT and is checked against its headroom, not removed.')


# ============================================================================ VI-A 4.4 ECLSS, logistics ============================
def eclss6():
    layouts = {'7 (3 A + 3 B + 1 hub)': dict(A=3, B=3, hub=1), '8 (4 A + 4 B)': dict(A=4, B=4, hub=0), '8 (3 A + 3 B + 2 hub)': dict(A=3, B=3, hub=2)}
    cases = {'nominal 6 + 6': (0, 0, 0, False, False, 6, 6), 'hub unit failed (6 + 6)': (0, 0, 1, False, False, 6, 6),
             'one A unit + hub unit failed (6 + 6)': (1, 0, 1, False, False, 6, 6), 'two A units failed (6 + 6)': (2, 0, 0, False, False, 6, 6),
             'ring A lost (12 in B)': (0, 0, 0, True, False, 0, 12), 'ring A lost + one B unit failed': (0, 1, 0, True, False, 0, 12),
             'ring A lost + hub unit failed': (0, 0, 1, True, False, 0, 12), 'ring A lost + B unit + hub unit failed': (0, 1, 1, True, False, 0, 12),
             'ring A rotary coupling lost (A occupied 6 + 6)': (0, 0, 0, False, True, 6, 6),
             'ring A rotary coupling lost + one A unit failed': (1, 0, 0, False, True, 6, 6)}
    out = []
    for name, L in layouts.items():
        res = {}
        for case, (lA, lB, lH, deadA, couplingA, cA, cB) in cases.items():
            capA = 0 if deadA else 4*max(0, L['A']-lA); capB = 4*max(0, L['B']-lB); capH = 4*max(0, L['hub']-lH)
            needA = max(0, cA-capA); needB = max(0, cB-capB)
            hubA = 0 if couplingA else capH                  # the hub reaches ring A only through ring A's rotary coupling
            res[case] = needA <= hubA and needA+needB <= capH
        out.append(dict(layout=name, units=sum(L.values()), mass_t=1.2*sum(L.values()), results=res, passes=sum(res.values()), of=len(res)))
    rotary = dict(per_ring=['air duct D 0.28 m at 4 m/s through the existing fluid-coupling cartridge position (rotor_interface), labyrinth + lift-off face seal, '
                            '~300 Pa duct pressure', 'water supply/return DN25 swivel', 'O2 / N2 make-up swivel (DN15)', 'cooling loop pair to the ring cold loop',
                            'power: existing contactless power channel (2 x 60 kW per ring for ECLSS)', 'data: existing contactless data channel, two networks'],
                  leak_kg_d=(0.05, 0.2, 1.0), seal_boundary='HAB-001 double boundary: primary seal plane + monitored guard cavity (no single rotary seal leak path)',
                  verdict='CREDIBLE for Track F: both rings already carry a stationary-to-rotating fluid-coupling cartridge and contactless power/data channels at '
                          'the hub (rotor_interface, OD-013 OPEN). The hub unit reaches each ring through that ring\'s own coupling. Seven units pass 9 of 10 cases; '
                          'the one failure is three concurrent losses (ring A, one B unit and the hub unit). Eight units (4 + 4) pass all 10 for +1.2 t but '
                          'leave no unit that can serve either ring. Owner rule DR5-06: seven, because the hub unit can credibly serve both rings.',
                  consumables='O2/N2 90 d reserve (casing service bays), water buffer per ring 2 t, LiOH emergency canisters in the refuge (L3, 12 crew x 14 d)')
    return dict(layouts=out, rotary=rotary, unit=dict(crew=4, mass_t=1.2, power_kW=3.4, envelope_m=(2.0, 1.4, 2.2), oru_max_width_m=0.70, maint_clear_m=1.0),
                choice='7 (3 A + 3 B + 1 hub)', bug_fixed='Phase V counted a negative hub capacity (4 x (0 - 1)) for 8 (4 + 4) "ring A lost + hub failed": that case passes')


def logistics6(P5):
    c3 = next(c for c in P5['logistics']['containers'] if c['gross_t'] == 3.0)
    m12 = next(m for m in P5['logistics']['missions'] if m['months'] == 12)['options']['3.0 t']
    fit = dict(gross_t=3.0, edge_m=c3['edge_m'], tare_t=c3['tare_t'], payload_t=c3['payload_t'],
               fittings='4 corner fittings, each rated 3 t x 2 g x 1.5 / 4 = 22 kN (2 g covers the 1.36 g burn peak and handling)',
               hatch='2.5 m cargo hatch (clear 2.3 m): edge %.2f m passes with %.2f m clearance' % (c3['edge_m'], 2.3-c3['edge_m']),
               handling='single-arm manipulator in the stationary hub store (FT-07)',
               route='hard containers stay in the stationary hub store; goods transfer to the rotating rings in soft bags <= 0.70 m (ORU width) through the '
                     'crew-transfer vestibules; LOG-G1 never crosses a rotary seal',
               small='1.5 t containers for EVA/airlock use, permanent racks for spares that never move')
    acct = dict(phase5_mass_line_t=7*0.55, phase5_logistics_t=m12['tare_t'], phase6_t=m12['tare_t'], n=m12['n'],
                note='Phase V carried 7 x 0.55 t in the mass ledger while V-G computed 8 containers at %.2f t tare: Phase VI uses V-G' % c3['tare_t'])
    return dict(container=fit, accounting=acct, workshop=dict(volume_m3=40.0, mass_t=6.0, power_kW=8.0, zone='stationary hub', fab='fab cell (canon), '
                'small-part additive + machining; spares in permanent racks (60 t workshop/spares/cargo line holds the spares)'))


# ============================================================================ VI-A 4.4 cryogenic cooling =============================
def species_heat(rad6):
    """Per-species nuclear heating (W) from rad6's per-tank tallies. OpenMC tallies are per source particle; x the summed source strength
    (particles per fission in each of the three units, cone fraction included) gives eV per fission-in-every-unit; x the fission rate of
    one Track R 750 K unit at full power gives W. Components: TN neutrons split into uncollided (direct) and scattered with the uncollided
    flux share, TN photons = shield and structure secondaries, TG = transmitted source photons, S6 = side scatter outside the cone."""
    runs = rad6.get('runs', {})
    if not all(k in runs for k in ('S6', 'TN', 'TG')): return None, None
    import math as _m
    S1 = json.loads((R/'phase4_rad_wayfarer.json').read_text())['S1']
    mu_c = _m.cos(_m.radians(12.5)); fin = (1-mu_c)/2; fout = 1-fin
    Nn, Ng = S1['neutrons_leaking_per_fission'], S1['photons_leaking_per_fission']
    S_in_n, S_in_g, S_out = 3*Nn*fin, 3*Ng*fin, 3*(Nn+Ng)*fout
    Pt = 3.5e6/0.146; f = Pt/(200e6*1.602e-19); ev = 1.602e-19*f
    out = {}
    for t in rad6['tanks']:
        c = f'tank_{t["id"]}'; TN = runs['TN']['cells'][c]; TG = runs['TG']['cells'][c]; S6 = runs['S6']['cells'][c]
        un = TN['unc_n']/TN['flux_n'] if TN['flux_n'] > 0 else 0.0
        comp = dict(direct_n=TN['heat_n_eV']*un*S_in_n*ev, scattered_n=TN['heat_n_eV']*(1-un)*S_in_n*ev, secondary_g=TN['heat_g_eV']*S_in_n*ev,
                    transmitted_g=TG['heat_g_eV']*S_in_g*ev, side_scatter=(S6['heat_n_eV']+S6['heat_g_eV'])*S_out*ev)
        rel = max(TN['heat_n_rel'], S6['heat_n_rel'], S6['heat_g_rel']) if comp['side_scatter'] else TN['heat_n_rel']
        d = out.setdefault(t['species'], dict(total_W=0.0, tanks=0, rel_max=0.0, **{k: 0.0 for k in comp}))
        for k, v in comp.items(): d[k] += v; d['total_W'] += v
        d['tanks'] += 1; d['rel_max'] = max(d['rel_max'], rel if rel == rel else 0.0)
    basis = dict(unit_thermal_W=Pt, fission_rate_per_unit=f, strengths=dict(in_cone_n=S_in_n, in_cone_g=S_in_g, out_cone=S_out),
                 note='Track R surrogate source at the 750 K unit power, all three units at full power; components as in the docstring; '
                      'statistical rel_max is the worst tank tally; not a dose or design value')
    return out, basis


def rad_summary(rad6, CR):
    if not rad6: return dict(status='not run')
    r = {k: v for k, v in rad6.items() if k != 'tanks'}
    sp = CR.get('species')
    if sp:
        keys = ['direct_n', 'scattered_n', 'secondary_g', 'transmitted_g', 'side_scatter']
        comp = {k: dict(W=sum(v[k] for v in sp.values())*2/3, rel=max(v['rel_max'] for v in sp.values())) for k in keys}
        top = max(comp, key=lambda k: comp[k]['W']); tot = sum(c['W'] for c in comp.values())
        r['summary'] = dict(components=comp, total_W=tot,
                            finding=f'All tanks at C load: {tot:.0f} W of nuclear heating, {100*comp[top]["W"]/tot:.0f} % from {top.replace("_", " ")} outside '
                                    'the shadow cone (Phase V: ~161 W at the 700 K bulkhead station with the Phase V tally set; the cause of the difference is not '
                                    'isolated). The through-shield components are below 0.001 W, but the benchmark ladder shows the weight windows are NOT '
                                    'verified beyond 20 cm (40 cm: 1.3x at ±41 %, 60 cm: 9x high, 100 cm: 17x low against exp(-Sigma t), 254 cm: no score), so the 2.54 m transmission '
                                    'is not a credible number yet: it needs adjoint-based variance reduction (CADIS/FW-CADIS). Statistical: the worst single tank '
                                    'tally is ±100 %. Transport-informed on a surrogate source; shielding, crew dose and the installed cryocooler rating stay OPEN (DR5-08).')
        D = rad6['runs'].get('D', [])
        r['benchmark'] = dict(verified_to_cm=max([d['t_cm'] for d in D if d.get('ratio') and abs(d['ratio']-1) < 0.1 and d['rel_err'] < 0.1] or [0]),
                              note='uncollided ratio within 10 % at <10 % statistics; weight-window runs beyond that disagree with the analytic value')
    return r


def cryo(rad6):
    """Required vs installed cooling of the He-3 3 K stage and the 20 K shields; nuclear heating by species from the OpenMC runs."""
    sys.path.insert(0, str(ROOT/'src/wayfarer')); import fuel_loads
    s = spec.load()[0]; c = fuel_loads.cooling(s)
    out = dict(he3_leak_lift_W=c['he3_stage_lift_W'], shield_leak_lift_W=c['shield_lift_W'], he3_W_per_W=1500.0, shield_W_per_W=60.0,
               note='fuel_loads.cooling gives the REQUIRED lift for the conduction/radiation leak (it sizes the cryocoolers to the leak; the canon '
                    'band spread 0.8-1.5 is on the input work). Phase V called 118 W the "lift": it is that requirement, not an installed margin.')
    sp, basis = species_heat(rad6) if rad6 else (None, None)
    if sp:
        out['species'] = sp
        n3 = sp.get('helium-3', {}); n20 = {k: v for k, v in sp.items() if k != 'helium-3'}
        for load, frac in (('C (3 units at 2/3)', 2/3), ('full (3 units at 100 %)', 1.0)):
            q3 = n3.get('total_W', 0.0)*frac; q20 = sum(v.get('total_W', 0.0) for v in n20.values())*frac
            out.setdefault('cases', []).append(dict(load=load, he3_nuclear_W=q3, h_d_nuclear_W=q20, he3_required_W=out['he3_leak_lift_W']+q3,
                                                    shield_required_W=out['shield_leak_lift_W']+q20,
                                                    he3_installed_W=1.25*(out['he3_leak_lift_W']+q3),
                                                    added_input_W=q3*1500.0+q20*60.0, nuclear_share_he3=q3/(out['he3_leak_lift_W']+q3)))
        out['basis'] = basis
    return out


# ============================================================================ VI-D mass, tanks, CoM, acceleration ==================
def couple(s, items, fictional, L_hdr):
    """Iterate the H6a line on the coupled peak acceleration (power-limited drive: a heavier ship accelerates less, the head falls)."""
    g = 1.362; it = dict(items)
    for _ in range(5):
        H = h6a_all(L_hdr, g, fictional)
        it['hot loop H6a'] = (H['total_t'], -140.0, 26.0, 'FT-01/FT-02' if fictional else 'RESEARCH')
        M = s5.mass(s, it); g = M['accel']['a_end_nom_g']
    return it, M, H, g


def tank_geometry(s, M):
    """Fill > 1 means the propellant does not fit the historical farm. Option A: lengthen every tank (same diameters, shadow and ring
    clearances unchanged); the farm grows forward and pushes the forward assembly forward by the same distance."""
    x0 = min(t['x0'] for t in fs.tanks(s)); x1 = max(t['x1'] for t in fs.tanks(s)); L = x1-x0
    out = []
    for r in M['tanks']:
        f = max(r['fill'].values())
        out.append(dict(case=r['case'], max_fill=f, fill=r['fill'], tank_length_m=L*max(1.0, f*1.0), extension_m=max(0.0, L*(f-1.0)),
                        ship_length_m=289.5+max(0.0, L*(f-1.0)), extra_liquid_m3={k: max(0.0, r['need_m3'][k]-r['capacity_m3'][k]) for k in r['need_m3']}))
    return dict(farm_x=(x0, x1), farm_length_m=L, rows=out,
                options=['A: lengthen all 13 tanks forward (geometry below)', 'B: add a second farm forward of the first (more skirts, same diameters)',
                         'C: larger diameters or more vessels: blocked by the packing (1.0 m access gap, the three lanes and the girder panels are all at their limits), not by the Brow silhouette (r 45 m; the farm reaches 34.5 m)'])


def accel_profile(s, M):
    F = op.power_cap_N(s); ve = op.p(s)['exhaust_velocity_m_s']; out = []
    for c in M['cases']:
        end = c['end_t']*1e3; dep = c['departure_t']*1e3; R_ = (dep/end)**0.25
        ms = [end*R_**(4-i) for i in range(5)]
        burns = [dict(burn=i+1, a_start_g=F/ms[i]/G0, a_end_g=F/ms[i+1]/G0, t_days=(ms[i]-ms[i+1])*ve/F/86400) for i in range(4)]
        out.append(dict(case=c['case'], departure_t=c['departure_t'], end_t=c['end_t'], a_departure_g=F/dep/G0, a_end_g=F/end/G0, burns=burns,
                        burn_days_total=sum(b['t_days'] for b in burns),
                        tank_support_load_MN=(c['propellant_t']/c['departure_t'])*F/1e6, thrust_structure_load_MN=F/1e6))
    return out


# ============================================================================ VI-C integration layout (geometry data) ==============
def layout(cfgF, HF, RF, D_trunk, L2len):
    """Functional assemblies of the Track F development configuration, ship frame (m, +x bow). make_review6.py builds them from here."""
    AZ = (90.0, 210.0, 330.0); A = []
    def add(family, name, shape, c, d, meaning, iface=None, clear=None, route=None, domain=None, track='F', ft=None, axis='x'):
        A.append(dict(family=family, name=name, shape=shape, c=[round(v, 3) for v in c], d=[round(v, 3) for v in d], axis=axis, meaning=meaning,
                      interfaces=iface or [], clearance_m=clear, route=route, failure_domain=domain, track=track, register=ft))
    for k, az in enumerate(AZ):
        a = math.radians(az); y, z = 2.9*math.cos(a), 2.9*math.sin(a); dom = f'L2 unit {k+1} / sector {az:.0f}'
        add('POWER_DISTRICT', f'L2U{k+1}_ReactorEnvelope', 'cyl', (-90.7, y, z), (1.6, 0.75, 0.75),
            'reactor envelope (ADJUSTABLE, no core design)', ['IHX primary'], 0.5, None, dom, ft=None)
        add('POWER_DISTRICT', f'L2U{k+1}_ShadowShieldEnvelope', 'cyl', (-88.6, y, z), (2.54, 1.0, 1.0),
            'shadow shield envelope 12.5 deg (ADJUSTABLE, OPEN: final shielding not approved)', [], None, None, dom)
        add('POWER_DISTRICT', f'L2U{k+1}_TAC', 'cyl', (-86.1, y, z), (2.0, 0.45, 0.45), 'turbo-alternator-compressor (closed Brayton, He-Xe)',
            ['hot gas from IHX', 'recuperator', 'alternator bus'], 1.0, 'radial to keel lane, then forward', dom, ft='FT-03 (F1 only)')
        add('POWER_DISTRICT', f'L2U{k+1}_Recuperator', 'box', (-84.2, y, z), (1.4, 1.1, 0.9), 'recuperator', ['TAC'], 0.8, 'keel lane', dom)
        add('POWER_DISTRICT', f'L2U{k+1}_GasCooler', 'box', (-82.9, y, z), (1.0, 1.2, 1.0), 'gas cooler / L2 header manifold (dual headers to two sectors)',
            ['L2 headers A/B', 'casing header duct'], 0.8, 'keel lane', dom)
        add('POWER_DISTRICT', f'L2U{k+1}_PMAD', 'box', (-81.2, y*1.1, z*1.1), (1.2, 0.7, 1.6), 'alternator rectifier + unit switchgear',
            ['main bus sector', 'restart bus'], 1.0, 'keel lane', dom)
        add('POWER_DISTRICT', f'L2U{k+1}_MountFrame', 'ring', (-86.0, y, z), (0.12, 1.35, 1.35), 'unit mount ring (struts to the casing frames)', ['casing frame'], None, None, dom)
        add('POWER_DISTRICT', f'L2U{k+1}_Clearance', 'box', (-85.5, y, z), (8.0, 2.4, 2.4), 'maintenance clearance envelope (1 m around the PCU)', [], None, None, dom)
    add('POWER_DISTRICT', 'District_RemovalRoute', 'rod', (-92.0, 0, -3.6), (93.0, 0, -3.6), 'service and removal route (keel lane, 1.2 m clear, FT-07 robots)')
    # H6a fictional network
    for k, az in enumerate(AZ):
        a = math.radians(az); er = (0, math.cos(a), math.sin(a)); et = (0, -math.sin(a), math.cos(a)); dom = f'hot sector {az:.0f}'
        def P(x, r, t=0.0):
            return (x, er[1]*r+et[1]*t, er[2]*r+et[2]*t)
        x1 = BULK-L2len; n = 6
        for j, off in enumerate((-0.9, 0.9)):
            add('THERMAL_H6A', f'Trunk_{az:.0f}_{j}', 'rod', P(-140.0, 5.9, off), P(x1, 5.9, off), f'primary trunk path {"AB"[j]} (60 % each), D {D_trunk:.2f} m, FT-01 wall',
                ['drive HX', 'section headers'], None, None, f'{dom} path {"AB"[j]}', ft='FT-01/FT-02')
            add('THERMAL_H6A', f'EMPump_{az:.0f}_{j}', 'cyl', P(-134.0, 5.0, off), (2.4, 0.55, 0.55), 'annular linear induction pump (EM)', ['L1 bus', 'trunk'], 1.0,
                'drive bay removal hatch', f'{dom} path {"AB"[j]}', ft='FT-02')
        add('THERMAL_H6A', f'Accumulator_{az:.0f}', 'cyl', P(-128.0, 4.4), (3.0, 0.6, 0.6), 'accumulator / pressurizer (Ar cover gas)', ['trunk pair'], 0.8, None, dom, ft='FT-01')
        add('THERMAL_H6A', f'DrainRecovery_{az:.0f}', 'cyl', P(-124.0, 4.0), (4.0, 0.8, 0.8), 'drain and recovery tank with trace heating (frozen-start, section drain)',
            ['section drain lines', 'trace heat L2'], 0.8, None, dom, ft='FT-02')
        for sct in range(n):
            xa = HOT_X0+sct*(x1-HOT_X0)/n; xb = HOT_X0+(sct+1)*(x1-HOT_X0)/n
            add('THERMAL_H6A', f'Header_{az:.0f}_{sct+1}', 'rod', P(xa+0.4, 6.4), P(xb-0.4, 6.4), 'section header (feeds the heat-pipe fins)', ['trunk A', 'trunk B'], None, None,
                f'{dom} section {sct+1}', ft='FT-01/FT-06')
            for j, off in enumerate((-0.9, 0.9)):
                add('THERMAL_H6A', f'Valve_{az:.0f}_{sct+1}_{j}', 'box', P(xa+0.5, 6.0, off), (0.9, 0.9, 0.9), 'section isolation valve pair (detect + close ~8 s)',
                    ['trunk', 'header'], 0.6, 'robot access along the blade root', f'{dom} section {sct+1}', ft='FT-01')
            add('THERMAL_H6A', f'Support_{az:.0f}_{sct+1}', 'box', P((xa+xb)/2, 5.75), (0.5, 0.3, 2.4), 'trunk support saddle (sliding, thermal growth ~10 mm/m)',
                ['casing frame'], None, None, None)
            add('THERMAL_H6A', f'Inspection_{az:.0f}_{sct+1}', 'box', P((xa+xb)/2, 5.3, 1.6), (0.7, 0.7, 0.7), 'inspection and replacement port', [], 0.7, None, None)
    # radiators F0 / F1
    for tag, L2x, cls in (('F0', L2len, 'R5-A 750 K cross-strapped (approved DR5-01)'), ('F1', RF['F1']['length_m'], 'FT-03 1500 K inlet, 950 K reject (APPROVED 2026-11-28)')):
        for az in AZ:
            add(f'RADIATOR_{tag}', f'L2Section_{tag}_{az:.0f}', 'sector', (BULK-L2x, az, 6.5), (BULK, 36.1, 0.45), f'L2 section {cls}', ['dual headers from two units'],
                None, None, f'L2 section {az:.0f}', ft=('FT-03' if tag == 'F1' else None))
        add(f'RADIATOR_{tag}', f'Bulkhead_{tag}', 'tube', (BULK-L2x-0.3, 6.1, 37.0), (BULK-L2x, 0, 0), 'graded thermal bulkhead, relocated aft of the L2 section')
    # electrical and utilities
    for k, az in enumerate((30.0, 150.0, 270.0)):
        a = math.radians(az); y, z = 5.0*math.cos(a), 5.0*math.sin(a)
        add('ELECTRICAL', f'MainBus_{k+1}', 'rod', (-80.0, y, z), (95.0, y, z), f'main bus sector {k+1} (HVDC duct, own failure domain)', ['L2 unit', 'switchgear', 'ring hubs'],
            None, None, f'bus sector {k+1}')
        add('ELECTRICAL', f'Switchgear_{k+1}', 'box', (14.0, y*0.9, z*0.9), (3.0, 1.0, 1.8), 'main switchgear and protection (sector)', ['bus', 'ride-through'], 1.0, 'keel lane', f'bus sector {k+1}')
        for j, xs in enumerate((-40.0, 0.0, 40.0, 80.0)):
            add('ELECTRICAL', f'RideThrough_{k+1}_{j+1}', 'box', (xs, y*0.85, z*0.85), (0.8, 0.6, 0.6), 'ride-through cells (bus segment)', ['bus segment'], 0.6, None, f'bus sector {k+1}', ft='FT-05')
        add('ELECTRICAL', f'RestartPack_{k+1}', 'box', (-78.5, 4.4*math.cos(math.radians((90, 210, 330)[k])+0.5), 4.4*math.sin(math.radians((90, 210, 330)[k])+0.5)), (1.6, 0.9, 1.2),
            'independent restart pack R1b (own cells, bus, converter)', ['L2 unit start bus'], 0.8, 'keel lane', f'L2 unit {k+1}', ft='FT-05')
    for j in range(4):
        add('ELECTRICAL', f'DefenseBuffer_{j+1}', 'box', (32.0+3.2*j, 0.0, 3.8), (2.8, 2.4, 1.4), 'defense buffer module (21 MW class, defense bus only)', ['defense bus'], 1.0, 'keel lane', 'defense bus', ft='FT-05')
    add('ELECTRICAL', 'L1_DC_Pickup', 'ring', (-140.0, 0, 0), (1.2, 9.0, 9.0), 'L1 direct-conversion pickup winding in the existing nozzle structure (FT-04, CONDITIONAL)',
        ['nozzle field', 'H6a cooling', 'L1 bus'], None, None, 'L1', ft='FT-04')
    add('ELECTRICAL', 'L1_Conditioning', 'box', (-121.0, 0, 3.2), (4.0, 2.4, 1.6), 'L1 power conditioning + pulse buffer (FT-04/FT-05)', ['L1 bus', 'heat pumps', 'EM pumps'], 1.0, 'drive bay hatch', 'L1', ft='FT-04')
    add('ELECTRICAL', 'L1_Bus', 'rod', (-140.0, 0, 3.2), (-80.0, 0, 3.2), 'L1 bus (drive services; isolated from the main bus)', ['DC pickup', 'EM pumps', 'heat pumps', 'EYE'], None, None, 'L1')
    add('ELECTRICAL', 'SurvivalBridge', 'box', (101.0, 0, -3.0), (2.0, 1.2, 1.0), 'survival bridge (refuge bus, L3, independent)', ['refuge bus'], 0.8, None, 'refuge', ft='FT-05')
    for j, az in enumerate((0.0, 180.0)):
        a = math.radians(az)
        add('ELECTRICAL', f'DataNet_{"AB"[j]}', 'rod', (-140.0, 4.6*math.cos(a), 4.6*math.sin(a)), (140.0, 4.6*math.cos(a), 4.6*math.sin(a)),
            f'data and control network {"AB"[j]} (fibre, physically separated)', ['every unit'], None, None, f'network {"AB"[j]}')
    # habitat and life support
    xa, xb = habitat_ring.centers(spec.load()[0])
    for tag, xc in (('A', xa), ('B', xb)):
        for k, th in enumerate((30.0, 150.0, 270.0)):
            t = math.radians(th)
            add('ECLSS', f'ECLSS_{tag}{k+1}', 'box', (xc, 27.6*math.cos(t), 27.6*math.sin(t)), (2.0, 1.4, 2.2), 'ECLSS-G1 four-person unit',
                ['ring bus (two segments)', 'ring cold loop', 'O2/N2', 'water', 'data A/B'], 1.0, 'ring aisle; ORU <= 0.70 m', f'ring {tag}')
        add('ECLSS', f'RotaryCoupling_{tag}', 'ring', (xc+(1.9 if tag == 'A' else -1.9), 0, 0), (0.6, 1.45, 1.45),
            f'ring {tag} rotary utility coupling (air duct, water, gas swivels; contactless power/data): existing cartridge position', ['hub ECLSS duct'], 0.8, None, f'ring {tag} coupling')
    add('ECLSS', 'ECLSS_HUB', 'box', ((xa+xb)/2, 0, 3.2), (2.0, 2.2, 1.4), 'ECLSS-G1 hub unit (serves both rings through their couplings)', ['both couplings'], 1.0, None, 'stationary hub')
    add('ECLSS', 'HubDuct', 'rod', (xa+1.9, 0, 2.6), (xb-1.9, 0, 2.6), 'hub-to-ring air ducts (D 0.28 m) to both couplings', [], None, None, 'stationary hub')
    # logistics and maintenance
    for k in range(8):
        add('LOGISTICS', f'LOG_G1_{k+1}', 'box', (106.5+(k % 4)*2.25, -2.2+(k // 4)*2.25, -3.0), (2.05, 2.05, 2.05), 'LOG-G1 3 t container (12 months, 12 crew)',
            ['4 corner fittings'], 0.2, 'hub store rail', 'hub store', ft='FT-07')
    add('LOGISTICS', 'HubStoreRail', 'rod', (105.0, -3.4, 0.4), (115.0, -3.4, 0.4), 'manipulator rail (single-arm 3 t)', [], None, None, 'hub store', ft='FT-07')
    add('LOGISTICS', 'Workshop', 'box', (95.5, 0.0, -3.0), (4.0, 3.2, 2.6), 'workshop + fab cell (canon fab cell; additive + machining)', [], 1.0, None, 'stationary hub')
    add('LOGISTICS', 'SparesRacks', 'box', (92.5, 0.0, 3.4), (3.0, 3.6, 1.2), 'permanent spares racks (60 t line)', [], 0.8, None, 'stationary hub')
    return A


# ============================================================================ main =================================================
def main():
    s = spec.load()[0]
    P5 = json.loads((R/'phase5.json').read_text())
    rad6 = json.loads((R/'phase6_rad.json').read_text()) if (R/'phase6_rad.json').exists() else {}
    life = tomllib.loads((ROOT/'data/life_support.toml').read_text())
    Rd5 = P5['radiators']; L750 = Rd5['l2_750']['cross']['length_m']; Lhdr = 162.0-L750
    RC = radiator_consistency(P5)
    # radiators: research R5-A (750 K, 1150 K inlet), fictional F0 (same), F1 (FT-03: 1500 K inlet)
    e_R = Rd5['l2_750']['eta']
    scanF = []
    for T in (700.0, 750.0, 800.0, 850.0, 900.0, 950.0, 1000.0):
        e = 0.42*(1-T/1500.0); x = l2_radiator(T, e); x['reactor_MWt'] = 3.5/e; x['hot_free_gain_m'] = L750-x['length_m']
        x['within_research_reactor_power'] = 3.5/e <= 3.5/e_R+1e-9; scanF.append(x)
    pickF = max((x for x in scanF if x['within_research_reactor_power']), key=lambda x: x['hot_free_gain_m'])
    RF = dict(R=l2_radiator(750.0, e_R), F0=l2_radiator(750.0, e_R), F1=pickF, scan=scanF,
              rule='F1 picks the rejection temperature that frees the most HOT length while the reactor stays at or below the research thermal power')
    for k, Lx in (('R', L750), ('F0', L750), ('F1', pickF['length_m'])):
        cap = (162.0-Lx)*PER_M_HOT; RF[k]['hot_capacity_W'] = cap; RF[k]['hot_headroom_W'] = cap/MARGIN-ABSORBED; RF[k]['hot_length_m'] = 162.0-Lx
    # ledgers: the WARM shortfall in a burn (Phase V R5-D re-zoned) is lifted into HOT by the canon burn heat pumps
    rb = next(r for r in P5['ledgers']['rows'] if r['state'] == 'high-power burn'); wz = rb['zones']['WARM_R5D']
    warm_short = max(0.0, wz['load_W']-wz['capacity_W'])
    # Track R hot loop on the R5-A length and coupled acceleration; Track F composite
    base_items = {k: tuple(v['t']) for k, v in P5['mass']['items'].items()}
    def items_for(track, variant='F0'):
        it = {}
        for k, v in P5['mass']['items'].items():
            it[k] = (list(v['t']), v['x'][0], v['x'][1], v['cls'])
        it.pop('hot loop H6a (research)')
        it['LOG-G1 tare (3 t containers, 12 months)'] = ([logistics6(P5)['accounting']['phase6_t']]*3, 95.0, 106.0, 'NEW (V-G tare)')
        return it
    # electrical first pass (pump power from a first network), then L1 mass
    HR0 = h6a_all(Lhdr, 1.0, False); HF0 = h6a_all(Lhdr, 1.0, True)
    E = electrical_states(P5, HR0['pump_W'][1], HF0['pump_W'][1], warm_short)
    l1R = E['sum_R']['continuous_proactive_W']*1.25          # Track R L1 rated for the proactive doctrine + 25 %
    def l1_thermal_t(P):
        return [P/1e3*(1.5, 3.0, 5.0)[i]/1e3+s3.q_area(P*(1/0.27-1), 900.0)/2*(6, 10, 15)[i]/1e3 for i in B]
    def l1_dc_t(P):
        return [P/1e6*(0.2, 0.5, 1.0)[i]+(10.0, 20.0, 40.0)[i]*P/1e8 for i in B]     # conditioning t/MWe + refractory pickup winding (PROTOTYPE)
    itR = items_for('R'); itR['L1 (derived)'] = (l1_thermal_t(l1R), -140.0, -120.0, 'RESEARCH (thermal, 900 K reject OPEN)')
    itR['WARM shortfall lift (canon heat pumps)'] = ([0.0]*3, 0.0, 0.0, 'EXISTING (no added mass)')
    itR, MR, HR, gR = couple(s, itR, False, Lhdr)
    out_F = {}
    for var, Lx in (('F0', L750), ('F1', pickF['length_m'])):
        it = items_for('F', var)
        P_dc = (20e6 if var == 'F0' else 100e6)
        it['L1 (derived)'] = (l1_dc_t(P_dc), -140.0, -120.0, 'FT-04 (CONDITIONAL)')
        if var == 'F1':
            k750 = 'L2 (3 x 3.5 MWe, 750 K)'; t = it.pop(k750)
            f = 0.5+0.5*pickF['reactor_MWt']/(3.5/e_R)            # unit mass ~ half reactor/shield (scales with MWt), half conversion (PROTOTYPE)
            it['L2 (3 x 3.5 MWe, FT-03 1500 K inlet)'] = ([v*f for v in t[0]], t[1], t[2], 'FT-03 (APPROVED)')
            ks = 'L2 sections 750 K cross-strapped + dual headers'; t = it.pop(ks)
            it[f'L2 sections {pickF["T_K"]:.0f} K cross-strapped + dual headers'] = ([v*pickF['length_m']/L750 for v in t[0]], BULK-pickF['length_m'], BULK, 'FT-03 (APPROVED)')
        it, M, H, g = couple(s, it, True, 162.0-Lx)
        out_F[var] = dict(items=it, mass=M, H6a=H, a_end_g=g, P_dc_W=P_dc)
    HF = out_F['F0']['H6a']
    E = electrical_states(P5, HR['pump_W'][1], HF['pump_W'][1], warm_short)
    # HOT headroom use in a burn (Track F): DC loss + heat-pump lift and work
    hp = E['heat_pump']
    pumps_heat = {'proactive burn': hp['proactive_W']+hp['proactive_lift_W'], 'reactive burn (peak at burnout)': hp['reactive_peak_W']+hp['reactive_lift_W']}
    L1F_pro = E['sum_F']['continuous_proactive_W']; L1F_re = E['sum_F']['continuous_reactive_W']
    DC = {v: direct_conversion(s, {'proactive burn': L1F_pro, 'reactive burn (peak at burnout)': L1F_re}, RF[v]['hot_headroom_W'], pumps_heat) for v in ('F0', 'F1')}
    # Track R 900 K reject (thermal L1): what a radiator for it would take
    rej900 = l1R/1.25*(1/0.27-1)
    L900 = s3.q_area(rej900*MARGIN, 900.0)/s3.FACE_PER_M
    l1R_close = dict(L1_continuous_W=l1R/1.25, reject_W=rej900, section_900K_m=L900, hot_free_after_R5A_m=s5.MARGIN and (Rd5['hot_free_m']-L750),
                     fits=Rd5['hot_free_m']-L750 >= L900,
                     note='a 900 K section on the hot blades would take hot length the 20 % rule no longer has after R5-A; Track R L1 rejection stays OPEN')
    # fictional mass reconciliation (VI-A 4.1)
    conv = next(c for c in P5['convergence'] if 'FICTIONAL' in c['name'])
    c4 = json.loads((R/'phase4.json').read_text())['convergence']['candidates'][-1]['items_t']
    mf_items = {k: v['t'][1] for k, v in P5['mass_fictional']['items'].items()}
    conv_items = {k: v[1] for k, v in c4.items() if k not in ('heat_transport_H5', 'section_700K', 'bulkhead_relocation')}
    conv_items['hot loop (C/C-SiC)'] = next(x for x in P5['transport']['material_sensitivity'] if x['sigma_MPa'] == 100)['total_t']
    diff = [dict(item='L2 units', convergence_t=conv_items['L2'], mass_fictional_t=mf_items['L2 (3 x 3.5 MWe, 750 K)'],
                 cause='convergence row reused the Phase IV 700 K unit mass; mass_fictional scaled it to 750 K'),
            dict(item='L2 sections 750 K + dual headers', convergence_t=0.0, mass_fictional_t=mf_items['L2 sections 750 K cross-strapped + dual headers'],
                 cause='left out of the convergence row (it dropped the Phase IV 700 K section and added nothing)'),
            dict(item='bulkhead relocation', convergence_t=0.0, mass_fictional_t=mf_items['bulkhead relocation'], cause='left out of the convergence row'),
            dict(item='LOG-G1 tare', convergence_t=0.0, mass_fictional_t=mf_items['LOG-G1 tare (3 t containers, 12 months)'], cause='left out of the convergence row')]
    for d in diff: d['delta_t'] = d['mass_fictional_t']-d['convergence_t']
    rec41 = dict(convergence_departure_t=conv['coupled'][1]['departure_t'], mass_fictional_departure_t=P5['mass_fictional']['cases'][1]['departure_t'],
                 convergence_dry_t=conv['dry_added_t'][1], mass_fictional_dry_t=P5['mass_fictional']['cases'][1]['dry_added_t'], items=diff,
                 sum_delta_t=sum(d['delta_t'] for d in diff),
                 verdict='Two configurations, not one ship: the 7,888 t row was a convergence summary on Phase IV items (700 K L2, no sections, '
                         'no bulkhead, no container tare); 8,042 t was the full Phase V item list. Both also carried the 3 mm-era L1 mass (H5 pumps), '
                         'the 700 K hot header length and the research loading. Phase VI replaces both with the frozen F0 configuration below.')
    # other reconciliations (4.4)
    EC = eclss6(); LG = logistics6(P5); CR = cryo(rad6)
    l1mass = dict(phase5_t=P5['mass']['items']['L1 (derived)']['t'], basis5='Phase IV formula on 0.1 MW + H5 pump work (4-34 MW)',
                  R_t=itR['L1 (derived)'][0], R_basis=f'thermal conversion rated {l1R/1e6:.1f} MWe (proactive continuous x 1.25)',
                  F0_t=out_F['F0']['items']['L1 (derived)'][0], F1_t=out_F['F1']['items']['L1 (derived)'][0])
    st = HR['startup']; stF = HF['startup']
    pre = dict(R=dict(thaw_J=st['thaw_J'], blade_J=st['blade_preheat_J'], to_operating_J=st['heat_to_operating_J']),
               F=dict(thaw_J=stF['thaw_J'], blade_J=stF['blade_preheat_J'], to_operating_J=stF['heat_to_operating_J']))
    for k in ('R', 'F'):
        J = pre[k]['thaw_J']+pre[k]['blade_J']
        pre[k]['hours_on_L2'] = {lab: J/max(1.0, W)/3600 for lab, W in E['L2']['surplus_coast_W'].items()}
        pre[k]['hours_one_unit_black_start'] = J/(E['L2']['available_W']['one_unit_EOL']-0.8e6)/3600
        pre[k]['drive_10pct_minutes'] = pre[k]['to_operating_J']/(0.1*ABSORBED)/60
    pre['note'] = ('Phase V P5-07 said "L2 alone takes days": with all three units in strategy C the coast surplus thaws the loop in hours; only a '
                   'one-unit black start stretches it. Heating from the melt point to the operating temperature comes from the drive at ~10 % power (minutes).')
    tanksR = tank_geometry(s, MR); tanksF = {v: tank_geometry(s, out_F[v]['mass']) for v in out_F}
    accR = accel_profile(s, MR); accF = {v: accel_profile(s, out_F[v]['mass']) for v in out_F}
    msR = s5.missions(s, MR['cases'][1]['dry_added_t'], life)
    msF = s5.missions(s, out_F['F0']['mass']['cases'][1]['dry_added_t'], life)
    def pareto(ms):
        return [p for p in ms['pareto'] if p['defense_law'] == 'v2']
    # configurations
    def cfg(track, var=None):
        M = MR if track == 'R' else out_F[var]['mass']; it = itR if track == 'R' else out_F[var]['items']
        c = dict(id=f'WF-{"R" if track == "R" else var}-P6.0', track='R (research)' if track == 'R' else f'F (fiction) {var}', status='STUDY / NONCANON',
                 derived_from='N2-R4a-P5.0 (Phase V) + Phase VI corrections C6-01..', production_unchanged=True,
                 generation=dict(L2=dict(units=3, rating_We=3.5e6, strategy='C (B for maintenance)',
                                         turbine_inlet_K=1150.0 if track == 'R' or var == 'F0' else 1500.0,
                                         reject_K=750.0 if track == 'R' or var == 'F0' else RF['F1']['T_K'],
                                         eta=e_R if track == 'R' or var == 'F0' else RF['F1']['eta'], register=None if track == 'R' or var == 'F0' else 'FT-03'),
                                 L1=dict(type='thermal conversion 0.27, 900 K reject (OPEN)' if track == 'R' else 'direct conversion (FT-04, CONDITIONAL)',
                                         rated_W=l1R if track == 'R' else out_F[var]['P_dc_W']),
                                 L3='refuge survival (independent)'),
                 radiators=dict(hot=dict(T_K=1800.0, length_m=RF['R' if track == 'R' else var]['hot_length_m'], margin_rule=1.2),
                                L2=dict(T_K=RF['R' if track == 'R' else var]['T_K'], length_m=RF['R' if track == 'R' else var]['length_m'], layout='cross-strapped dual headers'),
                                bulkhead_x=BULK-RF['R' if track == 'R' else var]['length_m']-0.2, WARM='R5-D re-zoned + burn heat-pump lift of the shortfall', LOW='R5-D'),
                 hot_loop=dict(topology='H6a', coolant='Li', wall='Mo-Re class 8-30 MPa' if track == 'R' else 'refractory composite 100 MPa, 3 t/m3 (FT-01)',
                               mass_t=(HR if track == 'R' else out_F[var]['H6a'])['total_t'], pump_W=(HR if track == 'R' else out_F[var]['H6a'])['pump_W']),
                 eclss=EC['choice'], logistics='LOG-G1 3 t (hub store) + soft bags + racks', loading='12 crew, 12 months standard, modular extension; 0.016 c reference',
                 items_t={k: v[0] for k, v in it.items()}, mass=dict(departure_t=[c_['departure_t'] for c_ in M['cases']], dry_added_t=[c_['dry_added_t'] for c_ in M['cases']],
                                                                     propellant_t=[c_['propellant_t'] for c_ in M['cases']], end_t=[c_['end_t'] for c_ in M['cases']]),
                 register_refs=sorted({v[3].split(' ')[0] for v in it.values() if v[3].startswith('FT-')}) if track == 'F' else [])
        c['hash'] = h(c); return c
    cR = cfg('R'); cF0 = cfg('F', 'F0'); cF1 = cfg('F', 'F1')
    (R/'phase6_config_R.json').write_text(json.dumps(cR, indent=1, default=float))
    (R/'phase6_config_F.json').write_text(json.dumps(dict(F0=cF0, F1=cF1, baseline='F1 is the Track F reference (owner 2026-11-28); F0 = without FT-03, kept for comparison'), indent=1, default=float))
    LAY = layout(cF1, out_F['F1']['H6a'], RF, out_F['F1']['H6a']['net']['D_trunk'], pickF['length_m'])
    # problems and decisions
    probs = [
        dict(id='P6-01', track='R', sev='BLOCKER (research)', text=f'Hot-loop walls: {HR["total_t"][1]:,.0f} t nominal on the R5-A length; Mo-Re walls exceed their temperature limit at the nominal inlet.'),
        dict(id='P6-02', track='R', sev='HIGH', text=f'L1 thermal conversion rejects {rej900/1e6:.0f} MW at 900 K; a 900 K section needs {L900:.1f} m of hot length that the 20 % rule no longer has after R5-A.'),
        dict(id='P6-03', track='R/F', sev='HIGH', text='He-3 stage: OpenMC side scatter adds ~53 W (C load) to the 118 W leak lift (+45 %); the installed cryocooler rating and final shielding stay OPEN (DR5-08).'),
        dict(id='P6-10', track='R', sev='HIGH', text='Deep penetration not verified: MAGIC weight windows are verified against exp(-Sigma t) only to 20 cm of LiH-W (40 cm within statistics); the 2.54 m shadow-shield transmission needs adjoint (CADIS) variance reduction before any through-shield number is used.'),
        dict(id='P6-04', track='F', sev='HIGH', text=f'F0: HOT headroom under the 20 % rule is {RF["F0"]["hot_headroom_W"]/1e6:.0f} MW; a reactive defense engagement in a burn (heat pumps + DC loss) does not fit. F1 (FT-03) frees {RF["F1"]["hot_headroom_W"]/1e6:,.0f} MW.'),
        dict(id='P6-05', track='R/F', sev='HIGH', text='Propellant does not fit the historical tank farm in any coupled case; the farm must grow (Track F geometry below).'),
        dict(id='P6-06', track='F', sev='MEDIUM', text='FT-04 needs a pulsed or modulated exhaust; the production drive repetition rate is OPEN in canon.'),
        dict(id='P6-07', track='R/F', sev='MEDIUM', text='Rotary utility couplings (air, water, gas) at both ring hubs are not designed (OD-013); the 7-unit ECLSS depends on them.'),
        dict(id='P6-08', track='R/F', sev='MEDIUM', text='Strategy C part-load efficiency raises L2 waste above the linear share; the cross-strapped sections still close (see 4.3).'),
        dict(id='P6-09', track='R', sev='MEDIUM', text='OpenMC: surrogate source, simplified structure, no dose; deep-penetration convergence through the shadow shield reported with weight windows (rad6).'),
    ]
    decs = [
        dict(id='DR6-01', q='Freeze F1 as the Track F working reference (8.2 kt class), with F0 and Track R as comparisons?', rec='yes (owner 3D brief)'),
        dict(id='DR6-02', q=f'FT-03 approved (owner 07:03Z): confirm the {RF["F1"]["T_K"]:.0f} K L2 reject temperature chosen for F1 (most HOT length freed at no more reactor power than Track R)?', rec='yes'),
        dict(id='DR6-03', q='Track F tank farm: lengthen the 13 tanks forward (option A) in a fictional geometry variant?', rec='yes, as an isolated variant'),
        dict(id='DR6-04', q='Accept 7 ECLSS units with the hub unit served through each ring\'s rotary coupling (P6-07 stays open)?', rec='yes'),
        dict(id='DR6-05', q='Rate the Track F DC L1 at 100 MWe (reactive defense in a burn) only with F1, 20 MWe with F0?', rec='yes'),
        dict(id='DR6-06', q='Publish the Phase VI R/F comparison on the website after review (no deployment until approved)?', rec='owner'),
    ]
    corrections = [
        dict(id='C6-01', item='fictional mass 7,888 vs 8,042 t', fix=rec41['verdict']),
        dict(id='C6-02', item='L1 = 600 MW in the Phase V ledger', fix=f'installed 210 MW heat-pump rating and the 50 MW pulse discharge were counted as continuous; continuous proactive burn L1 is {E["sum_R"]["continuous_proactive_W"]/1e6:.1f} MW (R)'),
        dict(id='C6-03', item='700 K values in the 750 K configuration', fix='; '.join(f['where'] for f in RC['found'] if f['now'] != 'kept (rejected variant, 700 K is its own design point)')),
        dict(id='C6-04', item='ECLSS 8 (4 + 4) "ring A lost + hub failed"', fix=EC['bug_fixed']),
        dict(id='C6-05', item='LOG-G1 tare in the mass ledger', fix=LG['accounting']['note']),
        dict(id='C6-06', item='L1 machinery mass', fix=f'Phase V reused the Phase IV H5-pump basis ({l1mass["phase5_t"][1]:.0f} t nom); now {l1mass["R_t"][1]:.0f} t (R thermal) and {l1mass["F0_t"][1]:.0f}/{l1mass["F1_t"][1]:.0f} t (F0/F1 DC)'),
        dict(id='C6-07', item='He-3 "lift" 118 W', fix=CR['note']),
        dict(id='C6-08', item='startup preheat duration', fix=pre['note']),
        dict(id='C6-09', item='hot header length 138 m', fix=f'R5-A leaves {Lhdr:.1f} m; H6a recomputed'),
    ]
    out = dict(status='STUDY / NONCANON (ISSA Phase VI)', register=dict(version=REG['register']['version'], ids=[t['id'] for t in REG['technology']],
                                                                       statuses={t['id']: t['status'] for t in REG['technology']}),
               configs=dict(R=cR, F0=cF0, F1=cF1), reconciliation=dict(mass=rec41, electrical=E, radiators=RC, eclss=EC, logistics=LG, l1_mass=l1mass,
                                                                       cryo=CR, preheat=pre, corrections=corrections),
               radiators=RF, warm_shortfall_W=warm_short, direct_conversion=DC, l1_research_reject=l1R_close,
               hot=dict(R=dict(total_t=HR['total_t'], pump_W=HR['pump_W'], by_item_t=HR['by_item_t'], D_trunk=HR['net']['D_trunk'], t_trunk=HR['net']['t_trunk'], a_g=gR,
                               wall_over_limit=HR['wall_over_limit']),
                        F0=dict(total_t=HF['total_t'], pump_W=HF['pump_W'], by_item_t=HF['by_item_t'], D_trunk=HF['net']['D_trunk'], t_trunk=HF['net']['t_trunk'],
                                a_g=out_F['F0']['a_end_g']),
                        F1=dict(total_t=out_F['F1']['H6a']['total_t'], pump_W=out_F['F1']['H6a']['pump_W'], by_item_t=out_F['F1']['H6a']['by_item_t'], D_trunk=out_F['F1']['H6a']['net']['D_trunk'], t_trunk=out_F['F1']['H6a']['net']['t_trunk'], a_g=out_F['F1']['a_end_g'])),
               mass=dict(R=MR, F0=out_F['F0']['mass'], F1=out_F['F1']['mass']), tanks=dict(R=tanksR, **tanksF), accel=dict(R=accR, **accF),
               missions=dict(R=pareto(msR), F0=pareto(msF), note='one hardware set per track; v^2 defense law shown; Pareto sets only (owner DR4-09)'),
               layout=LAY, problems=probs, decisions=decs, radiation=rad_summary(rad6, CR))
    (R/'phase6.json').write_text(json.dumps(out, indent=1, default=lambda o: list(o) if isinstance(o, tuple) else str(o)))
    print('configs', cR['id'], cR['hash'], cF0['id'], cF0['hash'], cF1['id'], cF1['hash'])
    print('4.1', round(rec41['convergence_departure_t']), round(rec41['mass_fictional_departure_t']), [(d['item'], round(d['delta_t'], 1)) for d in diff], round(rec41['sum_delta_t'], 1))
    print('L1 R', {k: (round(v/1e6, 2) if v else v) for k, v in E['sum_R'].items()}, 'F', {k: (round(v/1e6, 2) if v else v) for k, v in E['sum_F'].items()})
    print('hp', {k: round(v/1e6, 2) for k, v in E['heat_pump'].items() if isinstance(v, float)})
    print('RF', {k: (round(RF[k]['T_K']), round(RF[k]['length_m'], 1), round(RF[k]['hot_headroom_W']/1e6)) for k in ('R', 'F0', 'F1')})
    print('L2 fails', [(f['case'][:30], round(f['margin'], 3), round(f['max_output_W']/1e6, 2)) for f in RC['l2_failures']], 'hot', [(f['case'][:20], round(f['margin'], 3)) for f in RC['hot_failures']])
    print('H6a R', r3(HR['total_t'], 0), r3([x/1e6 for x in HR['pump_W']], 1), round(gR, 3), 'F0', r3(HF['total_t'], 0), r3([x/1e6 for x in HF['pump_W']], 1), round(HF['net']['D_trunk'], 2))
    print('mass R', [round(c['departure_t']) for c in MR['cases']], 'F0', [round(c['departure_t']) for c in out_F['F0']['mass']['cases']],
          'F1', [round(c['departure_t']) for c in out_F['F1']['mass']['cases']])
    print('tanks', round(tanksR['rows'][2]['max_fill'], 2), round(tanksF['F0']['rows'][2]['max_fill'], 2), round(tanksF['F0']['rows'][2]['extension_m'], 1), round(tanksF['F1']['rows'][2]['extension_m'], 1))
    print('DC', [(r['state'][:9], r['case'], round(r['loss_to_hot_loop_W']/1e6, 1), r['fits_hot_headroom'], f"{r['thrust_change_rel']:.1e}") for v in ('F0', 'F1') for r in DC[v]['rows'] if r['case'] == 'nom'])
    print('L1R reject', round(rej900/1e6, 1), round(L900, 1), l1R_close['fits'], 'preheat', {k: {a: round(b, 1) for a, b in pre[k]['hours_on_L2'].items()} for k in ('R', 'F')})
    print('eclss', [(l['layout'], l['passes'], l['of']) for l in EC['layouts']], 'cryo', CR.get('cases'))
    print('accel F0', [(round(a['a_departure_g'], 3), round(a['a_end_g'], 3), round(a['burn_days_total'], 1)) for a in accF['F0']])
    print('layout', len(LAY))


if __name__ == '__main__':
    main()
