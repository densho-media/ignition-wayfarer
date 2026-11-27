"""ISSA Phase II, ECLSS-A + integrated mass ledger: crew-12 consumables, food and water architectures, shield water as makeup, RCS
propellant, and a whole-ship mass reconciliation with the EPS-B results. STUDY (NONCANON). Writes ../results/phase2_eclss_mass.json.

    python3 work/ship-systems-architecture/phase2/eclss_mass.py      (after eps_b.py)
"""
import json
import math
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT/'src/wayfarer'))
import spec  # noqa: E402
import mass_model  # noqa: E402
import power_loads as pl  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parent))
import mission as msn  # noqa: E402

OUT = Path(__file__).resolve().parents[1]/'results'
G0 = 9.80665


def main():
    s = spec.load()[0]; ls = tomllib.loads((ROOT/'data/life_support.toml').read_text())
    days = ls['duration']['value']; rate = {r['id']: r['value'] for r in ls['rate']}
    design = s['crew']['rated_occupancy']['value']; story = ls['consumers']['story']; aboard = s['crew']['count']
    occ = dict(design_12=dict(people=design, rings='6 + 6'), story=dict(people=aboard, consumers=story, note='Seraph eats no human food or O2'),
               one_ring_emergency=dict(people=design, rings='12 in one ring'), refuge=dict(people=design, rings='storm refuge'))
    # ECLSS strings (docs/MODEL.md, pack_ra3_garden.eclss_string, PROTOTYPE): one per ring, each sized for six, 10 at 1.7x (ISS OGA ratio)
    string = dict(count=2, nominal_people=6, max_people=10, o2_kg_day=5.0, electrolysis_kW=1.7, sabatier_ch4_vent_kg_day=1.3)
    strings = dict(string=string,
                   reading='six PER STRING (one string per ring), not six for the ship: 12 rated is two strings at 1.0x',
                   cases={k: dict(people=p, per_string=p/n, load=p/n/string['nominal_people'], within_max=p/n <= string['max_people'])
                          for k, p, n in (('design 12, both rings', design, 2), ('story 6, both rings', aboard, 2),
                                          ('12 in one ring', design, 1), ('12, one string failed', design, 1))},
                   finding='12 people in one ring, or 12 on one string, needs 2.0x a string: above the 1.7x surge. Hardware is not doubled: '
                           'a third (spare) string or per-ring surge to 2.0x is the question.')
    # ---------- resource ledger (12 crew, 2191.5 d) ----------
    def mission(per_p_day, people=design, d=days):
        return per_p_day*people*d
    sab_h2o_loss = string['sabatier_ch4_vent_kg_day']*(36/16)/2*string['count']   # 4 H in CH4 -> 2 H2O per CH4 vented, per string
    ledger = dict(
        O2_generated_t=mission(rate['O2'])/1e3, CO2_removed_t=mission(rate['CO2_REMOVED'])/1e3,
        water_turnover_t=mission(rate['WATER_TURNOVER'])/1e3,
        water_makeup_t={f'{int(f*100)} % recovery': mission(rate['WATER_TURNOVER'])*(1-f)/1e3 for f in ls['process']['water_recovery']['scenarios']},
        sabatier_methane_vent_water_loss_t=sab_h2o_loss*days/1e3,
        waste_t=mission(rate['WASTE'])/1e3,
        filters_cartridges_t=(3.0, 5.0, 9.0),        # ISS ECLSS spares order 0.5-1.5 t/yr for six, x2 crew, six years (STUDY)
        hygiene_clothing_medical_t=(4.0, 6.5, 10.5), # 0.15-0.4 kg/person-day
        note='O2 recovery credited 0 and Garden credit 0 (life_support process rules); Sabatier vents methane, so water is lost with its hydrogen.')
    # ---------- food architectures ----------
    food = {}
    arch = {
        'conventional packaged (ISS, 41!B18)': dict(kg=1.83, dry=0.80, water=0.70, pack=0.33, vol_L=3.6, power_W=0, note='owner rate incl. packaging'),
        'dehydrated + rehydration': dict(kg=0.95, dry=0.78, water=0.05, pack=0.12, vol_L=2.1, power_W=0, note='rehydration ~0.8 kg water/person-day from the recovered loop (no makeup if recovery holds)'),
        'mixed (50 % dehydrated)': dict(kg=1.39, dry=0.79, water=0.38, pack=0.22, vol_L=2.9, power_W=0, note=''),
        'bulk staples + galley + 25 % garden calories': dict(kg=0.80*0.75+0.05, dry=0.60, water=0.03, pack=0.05, vol_L=1.5, power_W=40e3,
                                                             note='garden 120 m2 at the nominal 40 kW lighting load; seeds, nutrients and spares ~1-2 t'),
    }
    for k, a in arch.items():
        food[k] = dict(per_person_day_kg=a['kg'], dry_kg=a['dry'], water_kg=a['water'], packaging_kg=a['pack'],
                       mission_12_t=mission(a['kg'])/1e3, mission_story_t=mission(a['kg'], story)/1e3,
                       volume_12_m3=mission(a['vol_L'])/1e3, extra_power_W=a['power_W'], note=a['note'])
    reserve = dict(emergency_30d_12_t=30*design*1.0/1e3, note='dense emergency rations 1.0 kg/person-day, kept in the refuge')
    preservation = dict(
        degradation='Vitamins (C, B1, A) and texture decline over 3-5 years at room temperature (NASA Advanced Food Technology: many ISS foods '
                    'fall below nutrition targets after ~3 years). A six-year store needs cold storage (~4 C) or frozen (-20 C) for the later '
                    'half, supplements, and fresh garden produce for vitamins.',
        cold_store=dict(volume_m3=(30, 50, 80), power_W=(3e3, 6e3, 12e3), note='refrigerated/frozen store for ~half the food; heat to the ring cold loops'),
        storage='low temperature, low oxygen (nitrogen-flushed packs), dark; rotation first-in first-out')
    budget = s['physics']['mass_budget']['items']; food_line = next(i for i in budget if i['id'] == 'food_consumables')['mass_kg']/1e3
    food_cmp = {k: dict(food_12_t=v['mission_12_t'], with_consumables_t=v['mission_12_t']+ledger['hygiene_clothing_medical_t'][1]+reserve['emergency_30d_12_t'],
                        vs_10t=v['mission_12_t']+ledger['hygiene_clothing_medical_t'][1]+reserve['emergency_30d_12_t']-food_line,
                        food_story_t=v['mission_story_t']) for k, v in food.items()}
    # ---------- shield water (DR-08) ----------
    sw = next(i for i in budget if i['id'] == 'water_radiation_shielding')
    makeup_need = [ledger['water_makeup_t']['98 % recovery']+ledger['sabatier_methane_vent_water_loss_t'],
                   ledger['water_makeup_t']['90 % recovery']+ledger['sabatier_methane_vent_water_loss_t']]
    shield = dict(total_t=sw['mass_kg']/1e3, rotating_t=sw['rotating_allowance_kg']/1e3, refuge_t=sw['refuge_allowance_kg']/1e3,
                  makeup_need_t=makeup_need,
                  share_needed=[m/(sw['rotating_allowance_kg']/1e3) for m in makeup_need],
                  dose_effect='GCR dose falls slowly with water areal density (~1-2 % per g/cm2 near 20-30 g/cm2): withdrawing 10 % of the ring '
                              'water raises the habitat GCR dose by roughly 2-5 % (order of magnitude, needs a transport calculation).',
                  rules=['mandatory floor: the refuge 20 t never; ring water no lower than 90 % (PROTOTYPE) of its design areal density',
                         'draw symmetrically from paired compartments 180 deg apart, per ring, within the ring-balance tolerance '
                         '(physics.ring_balance momentum 0.1 %)',
                         'shield water is non-potable until processed: biocide/additive chemistry and contamination checks, then the water processor',
                         'compartmentalised tanks with isolation valves; a leak isolates one cell, not the shield'],
                  verdict=f'A controlled 10 % draw ({0.1*sw["rotating_allowance_kg"]/1e3:.0f} t) covers the 98 %-recovery makeup plus the methane-vent '
                          f'loss ({makeup_need[0]:.1f} t, {makeup_need[0]/(sw["rotating_allowance_kg"]/1e3)*100:.1f} %) with margin; at 90 % recovery '
                          f'({makeup_need[1]:.1f} t) it is exceeded. Closing the Sabatier loop (methane pyrolysis / Bosch) removes the '
                          f'{ledger["sabatier_methane_vent_water_loss_t"]:.1f} t loss.')
    # ---------- RCS (DR-09) ----------
    att = json.loads((ROOT/'references/p1_attitude.json').read_text())
    flip_300 = sum(v['propellant_kg']['isp_300'] for v in att['flips'].values())
    m_dep = mass_model.report(s)['departure']['mass_kg']
    impulse = dict(flips_Ns=flip_300*300*G0*2, docking_translation_Ns=2*3.0*m_dep, trim_and_desat_Ns=2.0e6,
                   note='four flips (two per round trip, attitude.flips at Isp 300 s), 3 m/s of docking translation at departure and arrival '
                        'mass, trim and CMG desaturation (STUDY)')
    I_tot = sum(v for k, v in impulse.items() if k.endswith('_Ns'))
    rcs = {}
    for name, isp, tank_frac, note in (
            ('cold gas N2', 70, 0.8, 'simple, inert, very heavy; tank pressure vessels'),
            ('hydrazine monopropellant', 230, 0.15, 'flight-proven; toxic, freezes at 275 K, six-year storage heritage (Voyager)'),
            ('MMH/NTO bipropellant', 310, 0.12, 'flight-proven; toxic, hypergolic'),
            ('gaseous H2/O2 (boil-off H2 + electrolysis O2)', 380, 0.25, 'uses propellant and ECLSS the ship already carries; igniters; O2 competes with breathing'),
            ('H2 resistojet / arcjet (boil-off H2)', 700, 0.25, 'electric: ~F ve / 2 eta of power; good for trim and desaturation, too weak for flips')):
        m = I_tot/(isp*G0)
        rcs[name] = dict(isp_s=isp, propellant_t=m/1e3, with_tankage_t=m*(1+tank_frac)/1e3, note=note)
    # ---------- integrated mass ledger ----------
    eb = json.loads((OUT/'phase2_eps_b.json').read_text())
    reg = tomllib.loads((ROOT/'data/systems.toml').read_text())
    archs = {a['name']: a for a in eb['architectures']}
    lean = archs['C-lean: 3+1 at nominal demand']; mid = archs['C: 3+1 modular (N+1)']
    I = pl.items(s); L = pl.ledgers(s, I=I)
    pump_W = next(r['W'] for r in L['HIGH_THRUST']['loads'] if r['id'] == 'TMS.BURN_HEAT_PUMPS')
    pcsc_existing = [sum(r['mass_kg'][j] for r in reg['system'] if r['budget_item'] == 'power_computers_steering_comms' and not r.get('mass_open')) for j in range(3)]
    pcsc_other = (1.5+0.5+3.0+1.5+1.5, 3.0+1.0+4.5+2.5+2.5, 6.0+2.0+6.0+4.0+4.0)    # CDH, sensors, CMGs, RCS hardware, comms (ISSA Phase I ledger, t)
    adds = [
        ('L2 ship-service generation (C-lean 3+1, shadow + blade-scatter shield, layout L-E)', 'PROPOSED.ship_service_generation',
         [m/1e3 for m in json.loads((OUT/'phase2_placement.json').read_text())['eps_b_shield_check']['c_lean_mass_with_scatter_kg']], -78.0),
        ('L1 burn generation', 'PROPOSED.burn_generation', [m/1e3 for m in eb['L1']['mass_kg']], -100.0),
        ('Burn heat pumps (running lift at burnout, 0.5/1.5/5 kg/kW)', 'PROPOSED.power_thermal_machinery', [pump_W[1]*k/1e6 for k in (0.5, 1.5, 5.0)], -100.0),
        ('L3 survival source (crew + nav/comms, 30 d: RPS or fission-Stirling)', 'power_computers_steering_comms', [9.0, 12.0, 16.0], 113.0),
        ('Cryocoolers (TMS-07)', 'radiators_thermal', [3.0, 6.0, 12.0], 0.0),
        ('Defense buffer (1 GJ, D-variant only)', 'power_computers_steering_comms', [0.45, 2.4, 12.0], 120.0),
        # Owner 2026-11-27: six years is narrative. Crew consumables are mission cargo loaded per mission (mission.py); the dry-ship
        # ledger carries only the 12-month standard load beyond the 10 t line (12 crew, conventional / mixed / dehydrated).
        ('Standard 12-month crew load beyond the 10 t line (mission cargo, 12 crew)', 'food_consumables',
         sorted(max(0.0, msn.provisioning(12, 365, f)['crew_consumables_kg']/1e3-10.0) for f in ('dehydrated', 'mixed', 'conventional')), 100.0),
        ('RCS propellant (H2/O2 or biprop)', 'PROPOSED.rcs_propellant', [rcs['MMH/NTO bipropellant']['with_tankage_t']*0.8, rcs['gaseous H2/O2 (boil-off H2 + electrolysis O2)']['with_tankage_t'], rcs['hydrazine monopropellant']['with_tankage_t']], 0.0),
    ]
    dry = mass_model.report(s)['dry_ship']['mass_kg']; dep = m_dep; prop = mass_model.report(s)['departure']['propellant_kg']
    parts = mass_model.dry_parts(s)
    xs = sum(p['m']*(p['x'][0]+p['x'][1])/2 for p in parts)/sum(p['m'] for p in parts)
    rows = []
    tot = [0.0, 0.0, 0.0]; mx = 0.0
    for name, item, t, x in adds:
        rows.append(dict(item=name, budget=item, t=t, x_m=x)); tot = [a+b for a, b in zip(tot, t)]; mx += t[1]*1e3*x
    ratio = dep/(dep-prop)                                     # whole-mission mass ratio at fixed delta-v (B02 balanced loading)
    tank = s['physics']['fuel_loads']['tank_dry_fraction']
    growth = [d*1e3*(ratio-1)*(1+tank)/1e3 for d in tot]       # extra propellant (and its tankage) for the same mission
    dv_loss = [math.log(dep/(dep-prop))-math.log((dep+d*1e3)/(dep+d*1e3-prop)) for d in tot]
    cg_new = (xs*dry+mx)/(dry+tot[1]*1e3)
    pcsc = dict(allocation_t=50.0, registry_eps_t=[m/1e3 for m in pcsc_existing], cdh_gnc_rcs_comms_t=pcsc_other,
                committed_t=[pcsc_existing[j]/1e3+pcsc_other[j] for j in range(3)],
                left_t=[50.0-(pcsc_existing[j]/1e3+pcsc_other[j]) for j in range(3)],
                note='Battery corrected to pack-level 2.5 t (the 800 Wh/kg figure is already a pack figure; Phase I applied packaging twice).')
    res = dict(status='ISSA Phase II STUDY (NONCANON)', occupancy=occ, strings=strings, ledger=ledger, food=food, food_vs_budget=food_cmp,
               reserve=reserve, preservation=preservation, shield_water=shield, rcs=dict(impulse=impulse, total_Ns=I_tot, options=rcs),
               mass=dict(adds=rows, total_added_t=tot, dry_ship_t=dry/1e3, departure_t=dep/1e3, propellant_t=prop/1e3, mission_mass_ratio=ratio,
                         extra_propellant_t=growth, delta_v_fraction_lost_if_propellant_fixed=[d/math.log(ratio) for d in dv_loss],
                         dry_cg_x_m=xs, dry_cg_x_after_m=cg_new, cg_shift_m=cg_new-xs,
                         axial_load_added_N_at_1_5g=[t*1e3*1.5*G0 for t in tot], pcsc=pcsc,
                         note='Power mass kept apart from the Vertex drive-mass research; the drive_package (250 t) is unchanged here. '
                              'Volume is not mass: the empty dry store is not unused mass allowance.'))
    OUT.mkdir(exist_ok=True)
    (OUT/'phase2_eclss_mass.json').write_text(json.dumps(res, indent=1))
    print('strings', strings['cases'])
    print('ledger', {k: v for k, v in ledger.items() if k != 'note'})
    for k, v in food_cmp.items():
        print(f'{k:48s} 12: {v["food_12_t"]:.1f} t, +consumables {v["with_consumables_t"]:.1f} t, vs 10 t {v["vs_10t"]:+.1f}; story {v["food_story_t"]:.1f} t')
    print('shield', shield['makeup_need_t'], shield['share_needed'])
    print('rcs total Ns', f'{I_tot:.3g}', {k: round(v['with_tankage_t'], 2) for k, v in rcs.items()})
    print('pcsc', pcsc)
    for r in rows:
        print(f"{r['item'][:60]:60s} {'/'.join(f'{x:.1f}' for x in r['t'])} t")
    print('total added', [round(x) for x in tot], 'extra propellant', [round(x) for x in growth], 'cg shift', round(cg_new-xs, 2), 'm', 'dv lost', [f'{x:.3f}' for x in res['mass']['delta_v_fraction_lost_if_propellant_fixed']])


if __name__ == '__main__':
    main()
