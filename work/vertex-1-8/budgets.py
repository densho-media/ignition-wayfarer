"""Vertex 1.8 Phase F: independent reconciliation of the propulsion power and spacecraft mass budgets (work, not canon).

  python3 work/vertex-1-8/budgets.py        writes work/vertex-1-8/budgets.json and prints the ledger

Owner item 8 (2026-11-16): reconcile the complete power and mass budgets before recommending the research-chain squashes. Every number
is recomputed here from first principles (rocket equation, jet power, D-He3 specific energy) and from the drawn parts (volume x density x
solid fraction, the same rule as vertex_engine.mass_estimate), then compared with the numbers each earlier study carried:
  canon            data/wayfarer_3d.toml (mass budget, departure envelope, power storage), operating_point (the mission)
  1.2 / 1.7 / 1.8  references/evidence/vertex_adaptive.json, vertex_dynamic.json (drawn engine mass, startup stores, A+ additions)
  1.5 / 1.6B       vertex_radiation.json, vertex_source.json (heat to reject, neutrons, realistic fusion power)
Pure standard library; reads src/ and references/, writes only into work/vertex-1-8/.
"""
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
import aplus  # noqa: E402
import vertex_engine as ve  # noqa: E402
import operating_point as op  # noqa: E402

C = 299792458.0
U = 1.66053907e-27
MEV = 1.602176634e-13
EV = ROOT/'references'/'evidence'


def ev(name):
    return json.loads((EV/f'{name}.json').read_text())


def drawn_mass(s, parts):
    mt = ve.config(s)['materials']; tot = 0.0
    for p in parts:
        key = p['material'] if p['material'] in mt['density_kg_m3'] else 'sensor'
        tot += ve._volume(p)*mt['density_kg_m3'][key]*mt['solid_fraction'][key]
    return tot


def rapidity_dv(ve_, R):
    """Relativistic rocket: v = c tanh((ve/c) ln R)."""
    return C*math.tanh(ve_/C*math.log(R))


def mission_with_added(m_end, R, burns, dm):
    """Fixed propellant per burn (the tanks are full), dm of hardware carried through all burns: the delta-v each burn still gives."""
    m = m_end*R**burns; dv = []
    for k in range(burns):
        m0 = m; m1 = m0/R; dv.append(math.log((m0+dm)/(m1+dm))); m = m1
    return dv


def run():
    s, R = aplus.load()
    rep = op.report(s); o = rep['operating_point']; mi = rep['mission']
    A, D, SRC, RAD = ev('vertex_adaptive'), ev('vertex_dynamic'), ev('vertex_source'), ev('vertex_radiation')
    P = s['physics']; budget = {i['id']: i['mass_kg'] for i in P['mass_budget']['items']}
    out = {}

    # ---------- 1. mission and propellant (independent rocket equation) -------------------------------------------------------------
    v_target = 0.016*C; ve_ = o['exhaust_velocity_m_s']; burns = mi['burns'] if 'burns' in mi else 4
    Rb = math.exp(v_target/ve_); m_end = mi['end_mass_kg']; m0 = m_end*Rb**burns
    F = o['peak_thrust_N']; mdot = F/ve_; Pjet = 0.5*F*ve_; Pf = Pjet/P['operating_point']['directed_efficiency']
    prop = m0-m_end; t_burn = prop/mdot
    e_dhe3 = 18.35*MEV/((2.014102+3.016029)*U)               # D + He-3 -> He-4 + p, 18.35 MeV
    E_fusion = Pf*t_burn; fuel = E_fusion/e_dhe3
    sp = rep['species_kg']
    out['mission'] = dict(
        target_c=0.016, exhaust_c=ve_/C, mass_ratio_burn=Rb, burns=burns, end_t=m_end/1e3, departure_t=m0/1e3,
        departure_canon_t=o['departure_mass_kg']/1e3, propellant_t=prop/1e3, propellant_canon_t=mi['propellant_kg']/1e3,
        relativistic_c=rapidity_dv(ve_, Rb)/C, mdot_kg_s=mdot, jet_TW=Pjet/1e12, jet_canon_TW=o['peak_jet_power_W']/1e12 if 'peak_jet_power_W' in o else None,
        fusion_TW=Pf/1e12, fusion_canon_TW=o['peak_fusion_power_W']/1e12, burn_days_each=t_burn/burns/86400, burn_days_total=t_burn/86400,
        fusion_EJ=E_fusion/1e18, fuel_needed_t=fuel/1e3, fuel_canon_t=(sp.get('helium_3', 0)+sp.get('deuterium', 0))/1e3,
        reaction_mass_canon_t=sp.get('hydrogen', 0)/1e3, species_canon_t={k: v/1e3 for k, v in sp.items()},
        failures=rep['failures'],
        verdict='CLOSES on its own assumptions: 0.016 c per burn, four burns, 2.80 kt propellant of which the D-He3 share is exactly what 261 '
                'TW for 28.6 days needs at 18.35 MeV per reaction; the relativistic correction is 0.08 %.')

    # ---------- 2. dry mass: what canon allots against what the drawn propulsion weighs ------------------------------------------------
    eng = A['audit']['mass']['engine_kg']; ef = A['audit']['mass']['engines_and_frame_kg']; frame = ef-4*eng
    base_parts = ve.parts(s); new = aplus.parts_aplus(s, R)
    m_base = drawn_mass(s, base_parts); m_ap = drawn_mass(s, new)
    row = {r['id']: r for r in A['concepts']['rows']}['A_PLUS']
    fly4 = 4*row['flywheel_share_kg']; ap4 = row['added_four_kg']; ap4_nofly = ap4-fly4
    margin = P['departure_mass']['upper_kg']-o['departure_mass_kg']
    drive_alloc = budget['drive_package']
    # carrying hardware through the mission: same delta-v needs R^burns more departure mass per kg of hardware
    grow = Rb**burns
    def keep_dv(dm):
        return dict(added_t=dm/1e3, departure_t=(m0+grow*dm)/1e3, propellant_t=(prop+(grow-1)*dm)/1e3,
                    in_departure_envelope=m0+grow*dm <= P['departure_mass']['upper_kg'],
                    in_propellant_envelope=prop+(grow-1)*dm <= P['propulsion_inventory']['upper_kg'])
    def keep_tanks(dm):
        dv = mission_with_added(m_end, Rb, burns, dm); tot = sum(ve_*x for x in dv)
        return dict(added_t=dm/1e3, dv_per_burn_c=[ve_*x/C for x in dv], last_burn_c=ve_*dv[-1]/C, shortfall_last_burn=1-ve_*dv[-1]/v_target,
                    accel_factor_first=m0/(m0+dm))
    out['mass'] = dict(
        canon_drive_package_t=drive_alloc/1e3, canon_dry_items_t={k: v/1e3 for k, v in budget.items()},
        canon_dry_total_t=sum(budget.values())/1e3, mission_end_t=m_end/1e3,
        drawn_engine_t=eng/1e3, drawn_engine_recomputed_t=m_base/1e3, drawn_cluster_frame_t=frame/1e3, drawn_propulsion_t=ef/1e3,
        drawn_over_allocation=ef/drive_alloc, drawn_vs_departure=ef/o['departure_mass_kg'],
        aplus_engine_recomputed_t=(m_ap-m_base)/1e3, aplus_engine_evidence_t=row['added_kg']/1e3,
        aplus_four_t=ap4/1e3, aplus_four_no_flywheel_t=ap4_nofly/1e3, flywheel_cluster_t=fly4/1e3,
        departure_margin_t=margin/1e3, margin_rule='upper departure envelope less the mission departure mass (the 1.7/1.8 check)',
        aplus_in_margin=ap4 <= margin, aplus_no_flywheel_in_margin=ap4_nofly <= margin,
        keep_dv=dict(aplus=keep_dv(ap4), aplus_no_flywheel=keep_dv(ap4_nofly), drawn_cluster_over_alloc=keep_dv(ef-drive_alloc),
                     max_added_in_envelope_t=margin/grow/1e3),
        keep_tanks=dict(aplus=keep_tanks(ap4), aplus_no_flywheel=keep_tanks(ap4_nofly)),
        verdict='DOES NOT CLOSE. The mission numbers carry the canon 250 t drive package; the drawn Vertex cluster weighs 6.33 kt '
                '(25x that allotment, 1.4x the whole departure mass) and no mission number reads it. Against the 174 t departure margin the A+ '
                'additions look small (132 t without the flywheel, 190 t with it), but hardware carried through four burns costs 2.72 kg of '
                'departure mass per kg at fixed delta-v, so only 64 t fits the envelope: A+ without the flywheel already needs 360 t.')

    # ---------- 3. power and heat ------------------------------------------------------------------------------------------------------
    alloc = SRC['combined']['allocation']; rows = SRC['mission']['rows']
    realistic = [r['fusion_four_W'] for r in rows]
    neut = SRC['neutrons']['rows'][0]
    bud = [r for r in D['budget']['rows'] if r['candidate'] == 'static']
    th = RAD['thermal']['cases']['NOMINAL']['RADIATION_low']
    out['power'] = dict(
        jet_TW=Pjet/1e12, fusion_canon_TW=Pf/1e12, fusion_per_engine_TW=Pf/4e12,
        fusion_realistic_TW=[x/1e12 for x in realistic], useful_share_realistic=[r['useful_share'] for r in rows],
        fuel_realistic_t=[r['fuel_dhe3_kg']/1e3 for r in rows],
        installed_rejection_GW=alloc['installed_W']/1e9, drive_share_GW=alloc['drive_W']/1e9, per_engine_GW=alloc['per_engine_W']/1e9,
        canon_absorbed_GW=o['peak_absorbed_heat_W']/1e9, canon_absorbed_fraction=P['operating_point']['absorbed_fraction'],
        heat_to_reject_per_engine_TW=bud[0]['reject_W']/1e12 if bud else None, ratio_to_drive_share=bud[0]['ratio'] if bud else None,
        neutron_case=neut['case'], neutron_W_TW=neut['neutron_W']/1e12, neutron_shield_four_t=neut['shield_mass_four_kg']/1e3,
        radiation_low_radiator_ratio=th['ratio'],
        realistic_fuel_over_canon=[r['fuel_dhe3_kg']/r['fuel_canon_kg'] for r in rows],
        verdict='DOES NOT CLOSE. Canon assumes 80 % of the fusion power leaves as directed exhaust and 4e-5 is absorbed (10.45 GW of the '
                '10.80 GW drive share). The 1.6B source model finds a useful share of 41-44 %, so 476-511 TW of fusion and 4.7-5.0 kt of D-He3 '
                '(1.8-2.0x canon fuel); the heat reaching the engine is 12,700x its 2.70 GW share, neutrons alone 10 TW per engine, and a '
                'coil shield against them weighs 45 kt for the cluster. These are 3-4 orders of magnitude, not margins.')

    # ---------- 4. startup energy (the optional flywheel question) ----------------------------------------------------------------------
    st = P.get('power', {}) if 'power' in P else s['power']
    store = s['power']['storage']
    batt_J = store['main_battery']['usable_energy_Wh']*3600; bank_J = store['pulse_bank']['energy_Wh']*3600; bank_W = store['pulse_bank']['power_W']
    field_J = A['audit']['field']['stored_J']; charge_h = D['dynamo']['dynamo_charge'][0]['hours']
    boots = D['dynamo']['startup']
    out['startup'] = dict(
        field_energy_cluster_GJ=4*field_J/1e9, field_charge_h_at_1V=charge_h, field_charge_avg_kW=4*field_J/(charge_h*3600)/1e3,
        main_battery_GJ=batt_J/1e9, pulse_bank_GJ=bank_J/1e9, pulse_bank_MW=bank_W/1e6,
        bootstrap=[dict(bracket=b['bracket'], energy_GJ=b['energy_J']/1e9, power_MW=b['power_W']/1e6, flywheel_t=b['mass_kg']['flywheel']/1e3,
                        bank_power_ok=b['power_W'] <= bank_W, battery_energy_ok=b['energy_J'] <= batt_J) for b in boots],
        verdict='OPEN. Charging the four engines\' coils takes 38.9 GJ (5.4x the main battery); spread over 31 h it is a 350 kW load the '
                'ship bus or the departure station can carry. The first driver pulses need 0.3-15.7 GJ at 31-1,570 MW: the 50 MW pulse bank '
                'covers only the lowest bracket, the 58 t flywheel the middle one. Without the flywheel, ignition at the middle bracket has '
                'no sourced power path; with it, the mass does not fit. Ignition energy stays OPEN (power.storage.pulse_bank.ignition_energy).')

    out['summary'] = dict(
        mission='closes on its own assumptions', mass='does not close (drawn propulsion 25x its allotment; A+ needs 360 t of departure mass at fixed delta-v, 64 t fits)',
        power='does not close (absorbed heat 10^3-10^4 x the drive share; realistic fuel 1.8-2.0x canon)', startup='open (ignition power path without the flywheel)',
        consequence='A+ is affordable relative to the engine it modifies (3 % of its drawn mass) but no A+ choice changes whether the Vertex '
                    'cluster reaches 0.016 c. The blocking problems are the engine mass, the absorbed heat and the useful power share, together.')
    return out


if __name__ == '__main__':
    out = run()
    (HERE/'budgets.json').write_text(json.dumps(out, indent=1, default=float)+'\n')
    m, ms, p, st = out['mission'], out['mass'], out['power'], out['startup']
    print(f"mission: R {m['mass_ratio_burn']:.4f}/burn, departure {m['departure_t']:.0f} t (canon {m['departure_canon_t']:.0f}), propellant "
          f"{m['propellant_t']:.0f} t, jet {m['jet_TW']:.0f} TW, fusion {m['fusion_TW']:.0f} TW, fuel needed {m['fuel_needed_t']:.0f} t "
          f"(canon {m['fuel_canon_t']:.0f}), burns {m['burn_days_total']:.1f} d, relativistic {m['relativistic_c']:.5f} c")
    print(f"mass: drive package {ms['canon_drive_package_t']:.0f} t vs drawn {ms['drawn_propulsion_t']:.0f} t ({ms['drawn_over_allocation']:.1f}x); "
          f"engine {ms['drawn_engine_t']:.0f} t (recomputed {ms['drawn_engine_recomputed_t']:.0f}); A+ per engine {ms['aplus_engine_recomputed_t']:.1f} t "
          f"(evidence {ms['aplus_engine_evidence_t']:.1f}); four {ms['aplus_four_t']:.0f} t / {ms['aplus_four_no_flywheel_t']:.0f} t no flywheel; margin "
          f"{ms['departure_margin_t']:.0f} t; keep-dv departure {ms['keep_dv']['aplus_no_flywheel']['departure_t']:.0f} t; max in envelope "
          f"{ms['keep_dv']['max_added_in_envelope_t']:.0f} t; keep-tanks last burn shortfall {100*ms['keep_tanks']['aplus_no_flywheel']['shortfall_last_burn']:.1f} %")
    print(f"power: realistic fusion {p['fusion_realistic_TW']} TW, fuel {p['fuel_realistic_t']} t; heat/engine {p['heat_to_reject_per_engine_TW']:.1f} TW "
          f"= {p['ratio_to_drive_share']:.0f}x share; neutrons {p['neutron_W_TW']:.1f} TW; shield {p['neutron_shield_four_t']:.0f} t")
    print(f"startup: field {st['field_energy_cluster_GJ']:.1f} GJ ({st['field_charge_avg_kW']:.0f} kW over {st['field_charge_h_at_1V']:.1f} h); battery "
          f"{st['main_battery_GJ']:.1f} GJ, bank {st['pulse_bank_GJ']:.2f} GJ @ {st['pulse_bank_MW']:.0f} MW; {st['bootstrap']}")
