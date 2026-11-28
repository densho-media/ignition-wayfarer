"""WSI Checkpoint 1: the shared foundation.

Builds the one authoritative joint configuration (results/wsi_config.json, WSI-0.1) from the ISSA closeout (C1.1, SSI-1.1) and the PSA
structural model (concept H, stationary hub, six paired rails), reconciles the joint mass ledger, and reproduces both starting points:
ISSA C1.1 (9,078 t without a sized structure) and the provisional combined point (C1.1 + PSA Phase II H:hub:F1 structure).

    python3 work/wayfarer-systems-integration/wsi/foundation.py

STUDY / PROTOTYPE, Track F working configuration; noncanon; production geometry unchanged.
"""
import json
import tomllib

from common import (CIRC_KG, ISSA, ROOT, PSA, R, REFS, STRUCT_LINE_T, THRUST_N, G0, S, cs, issa_c11, issa_point, mission, mm, psa_p2)

CONFIG_ID = 'WSI-0.1'


def psa_structure_h_hub():
    """PSA Phase II H:hub:F1 primary structure by family (provisional: sized on CP4 stations, strength only, lambda 0.71)."""
    L = psa_p2()['variants']['H:hub:F1']
    return dict(variant='H:hub:F1', source=f'PSA Phase II {REFS["psa_phase2"]} results/p2_ledger.json', items_t=L['items_t'], total_t=L['psa_total_t'],
                delta_vs_line_t=L['delta_vs_line_t'], status='PROVISIONAL: strength-sized, follower lambda 0.68 / static 0.71 against 1.95 (operating basis)')


def topology():
    import model as mdl
    c = mdl.CONCEPTS['H']
    return dict(concept='H (leading reference; HC, A, C, H3 retained as alternatives)', rotor_bay='stationary hub path (hub cones, no bypass collar as primary path)',
                rails=dict(count=c['rails'], arrangement='three paired sectors at az 30/150/270 +- 8.6 deg', radius_m=mdl.R_RAIL),
                stations=dict(thrust_ring_x=mdl.X_RING, transition_x=mdl.X_TRANS, cage_end_x=mdl.X_CAGE_END, bay_m=4.0, module_frame_every_bays=c['module_bays']),
                spine=dict(x=(mdl.X_SPINE0, mdl.X_SPINE1), radius_m=mdl.R_SPINE, role='Momentum Spine structural shell (PSA), axial datum'),
                deck=dict(kind='TD-A corrected (PSA Phase III model3): aft layer x 107.0, skirt plane = farm aft end', alternatives='TD-B..TD-F (PSA analysis)'),
                keels='three sector keels from the deck to the Brow interface ring', brow_interface='keel-to-Brow interface ring (PSA ends there)',
                materials=c['mats'], pickup='four nozzle pickups, beam struts (3.8 MN limit, 5.3 MN ultimate per strut)',
                l2_interface_x=41.0, rotating='two habitat rings on the hub bearings, free in roll')


def materials():
    import model as mdl
    used = sorted(set(mdl.CONCEPTS['H']['mats'].values()))
    out = []
    for mid in used:
        m = mdl.MATS[mid]
        out.append(dict(id=mid, name=m['name'], track=m.get('track', 'R'), E_GPa=m['E'], rho=m['rho'], Fty_MPa=m['Fty'], alpha_ppm_K=m['alpha'],
                        specific_modulus_MJ_kg=(m['E'][1] if isinstance(m['E'], list) else m['E'])*1e3/m['rho']))
    return out


def thermal_interfaces(C):
    P = C['radiators']['preferred']
    return [dict(id='TI-HOT', loop='HOT (H6a Li)', T_K=1800.0, carries='drive waste heat, L2 primary', interfaces='trunk saddles (anchor/slide) on PSA frames; blade roots'),
            dict(id='TI-L2', loop='L2 NaK / K heat pipes', T_K=896.0, carries='L2 Brayton reject', interfaces='L2 section x 41.02-50.4; structural station x 41.0'),
            dict(id='TI-WARM', loop='WARM water', T_K=round(P['T_warm_K'], 1), carries='converter and pump losses, insulation leak (FT-09 machinery)',
                 interfaces='WARM section x 50.4-72.9'),
            dict(id='TI-LOW', loop='LOW ammonia', T_K=round(P['T_low_K'], 1), carries='avionics, cryocooler reject, batteries (sensitive items)',
                 interfaces='LOW section x 73.4-93.4 and tip extensions x 93.4-106.4'),
            dict(id='TI-CRYO', loop='3 K / 20 K cryocooler stages', T_K=(3.0, 20.0), carries='vessel leak and nuclear heating', interfaces='13 stations at the vessel forward guides')]


def utility_routes():
    return [dict(id='UR-BUS', what='sector HVDC buses', az=(30.0, 150.0, 270.0), r_m=5.0, x=(-92.0, 100.0)),
            dict(id='UR-DATA', what='data A/B', az=(0.0, 180.0), r_m=4.6, x=(-140.0, 160.0)),
            dict(id='UR-NAK', what='L2 NaK transport loops', az=(10.0, 50.0, 130.0, 170.0, 250.0, 290.0), r_m=5.8, x=(-81.6, 40.4)),
            dict(id='UR-H6A', what='H6a hot trunks (outside the hull)', az=(90.0, 210.0, 330.0), r_m=6.52, x=(-111.6, 41.02)),
            dict(id='UR-MRU', what='MRU twin rails', az=(255.0, 285.0), r_m=4.6, x=(-92.7, 92.0)),
            dict(id='UR-L1', what='L1 conductors (two half-rated segments)', az=(30.0, 150.0), r_m=5.0, x=(-140.0, -92.0))]


def maintenance(C):
    MR = C['mru']
    return [dict(id='ME-MRU-F', what='in-flight MRU swept tube (TAC)', lane_r_m=MR['flight']['route_r'], radius_m=MR['flight']['swept_radius_m'], x=MR['rail_x']),
            dict(id='ME-MRU-Y', what='yard MRU swept tube (reactor/IHX)', lane_r_m=MR['yard']['route_r'], radius_m=MR['yard']['swept_radius_m'], x=MR['rail_x'],
                 remove_first=MR['yard']['remove_first']),
            dict(id='ME-EXT-TA', what='EXT-TA reach', x=(-133.5, -125.0), reach_m=6.0),
            dict(id='ME-M10', what='module 10 item-level removal through the keel lanes; container-level = yard', x=(22.25, 33.25)),
            dict(id='ME-LOG-G1', what='LOG-G1 3 t containers hub store -> rings', x=(95.0, 106.0))]


def tech_deps():
    reg = tomllib.loads((ROOT/'data/technology_register.toml').read_text())
    return [dict(id=t['id'], name=t['name'], status=t['status'], dependents=t.get('dependents', [])) for t in reg['technology']]


def ledger_rows(P, struct):
    """Joint ledger: production items (150 t line replaced by PSA structure), ISSA C1.1 rows, PSA structure by family, tankage, propellant.
    One row per physical item, one owner per row."""
    rows = []
    for p in mm.dry_parts(S()):
        n = p['name']
        if n.startswith('main_structure'):
            continue
        if n.startswith('tankage_'):
            continue   # production tankage is inside the re-solved added tankage below (operating_point added_tank_kg), never twice
        rows.append(dict(item=n, t=p['m']/1e3, owner=n.split('@')[0], cat='HISTORICAL'))
    for r in P['L']['rows']:
        rows.append(dict(item=r['item'], t=r['t'], owner=r['owner'], cat=r['cat']))
    for k, v in struct['items_t'].items():
        rows.append(dict(item='PSA: '+k, t=v, owner='PSA', cat='STRUCTURE (provisional)'))
    rows.append(dict(item='tankage (all vessels: shells, insulation, supports; re-solved for this propellant)', t=P['L']['tankage_t'], owner='tankage', cat='TANKAGE'))
    rows.append(dict(item='payload: ECLSS CO2 reserve', t=sum(p['t'] for p in P['L']['payload']), owner='ISSA ECLSS', cat='PAYLOAD'))
    rows.append(dict(item='propellant residual + boil-off reserve (carried)', t=P['L']['carried_t'], owner='propellant', cat='CARRIED'))
    rows.append(dict(item='mission propellant', t=P['L']['propellant_t'], owner='propellant', cat='PROPELLANT'))
    names = [r['item'] for r in rows]; dup = sorted({n for n in names if names.count(n) > 1})
    overlap = [dict(pair=('PSA: rotating ring structure (2 rings)', 'habitat_pressure_structure@ring_A/B'), verdict='different items: PSA rim/spokes/races vs habitat '
                      'pressure shell (habitat-owned); no double count'),
               dict(pair=('PSA: protective casing (secondary)', 'ISSA protection layers'), verdict='casing carrier is PSA; ISSA C1.1 has no casing row'),
               dict(pair=('PSA: common thrust deck', 'tankage skirts'), verdict='deck PSA, skirts/cradles tankage (D04); V-link lugs PSA'),
               dict(pair=('PSA frames', 'ISSA saddles, rail chairs, rack brackets'), verdict='split at the SSI mount id'),
               dict(pair=('production main_structure 150 t', 'PSA structure'), verdict='replaced: the 150 t line leaves the ledger, PSA total enters')]
    return rows, dup, overlap


def main():
    C, SSI = issa_c11()
    # starting point A: ISSA C1.1 reproduced with consolidate.py (150 t line inside the production protected mass)
    A = issa_point(0.0)
    struct = psa_structure_h_hub()
    # starting point C: C1.1 + PSA Phase II structure (delta over the 150 t line)
    Cc = issa_point(struct['delta_vs_line_t'])
    p2 = psa_p2()['variants']['H:hub:F1']
    starts = [dict(id='S-ISSA', name='ISSA WF-F1-C1.1 (150 t structure line, no sized structure)', departure_t=A['L']['departure_t'], propellant_t=A['L']['propellant_t'],
                   loaded_t=A['T']['loaded_t'], tankage_t=A['L']['tankage_t'], end_t=A['L']['end_t'], farm_added_m=A['T']['added_length_m'], ship_length_m=A['T']['ship_length_m'],
                   structure_t=STRUCT_LINE_T, a_end_g=THRUST_N/(A['L']['end_t']*1e3)/G0, reproduces=C['ledger']['departure_t'], iterations=len(A['history'])),
              dict(id='S-PSA', name='PSA Phase II H:hub:F1 on ISSA CP4 stations (PSA coupling)', departure_t=p2['coupled_departure_t'], propellant_t=None, loaded_t=None,
                   tankage_t=None, end_t=None, farm_added_m=18.21, ship_length_m=307.7, structure_t=p2['psa_total_t'], a_end_g=0.56, reproduces=None,
                   note='PSA scaled the CP4 departure (8,573 t) by its coupling factor 3.52; no farm resize'),
              dict(id='S-COMB', name='C1.1 + PSA Phase II structure (provisional combined point)', departure_t=Cc['L']['departure_t'], propellant_t=Cc['L']['propellant_t'],
                   loaded_t=Cc['T']['loaded_t'], tankage_t=Cc['L']['tankage_t'], end_t=Cc['L']['end_t'], farm_added_m=Cc['T']['added_length_m'],
                   ship_length_m=Cc['T']['ship_length_m'], structure_t=struct['total_t'], a_end_g=THRUST_N/(Cc['L']['end_t']*1e3)/G0,
                   reproduces=C['combined']['departure_t'], iterations=len(Cc['history']),
                   note='C1.1 combined() kept cryo and radiators at the C1.1 farm area (13,193 t); WSI re-iterates them for the longer farm (+19 t)')]
    rows, dup, overlap = ledger_rows(Cc, struct)
    by_cat = {}
    for r in rows:
        by_cat[r['cat']] = by_cat.get(r['cat'], 0.0)+r['t']
    total = sum(r['t'] for r in rows)
    T = Cc['T']
    cfg = dict(id=CONFIG_ID, status='STUDY / PROTOTYPE, Track F working configuration; noncanon; production geometry unchanged',
               sources=dict(issa=f'claude/cloud/ship-systems-architecture {REFS["issa"]} (WF-F1-C1.1, SSI-1.1, register v1.2)',
                            psa=f'claude/cloud/primary-structural-architecture {REFS["psa_phase3"]} (Phase II {REFS["psa_phase2"]}, Phase III.0 WIP)',
                            production=f'main {REFS["main"]} (read only)'),
               ownership=SSI['ownership_rule'], coordinate_system=SSI['shared']['coordinate_system'],
               dimensions=dict(ship_length_m=T['ship_length_m'], farm_x=T['farm_x'], brow_x=T['brow_x'], body_radius_m=6.5, rail_radius_m=5.0,
                               radiator_envelope=SSI['shared']['dimensions']['radiator_envelope'], ring_radius_m=30.0, brow_radius_m=45.0),
               structural_topology=topology(), structural_materials=materials(),
               propellant=dict(species_t=T['mission_t'], mission_t=T['propellant_t'], loaded_t=T['loaded_t'], carried_t=T['carried_t'], allowances=T['allowances'],
                               fill=T['fill'], usable_m3=T['usable_m3'], capacity_m3=T['capacity_m3']),
               tanks=dict(arrangement='T-A (13 vessels, stretched forward farm)', added_length_m=T['added_length_m'],
                          vessels=[dict(id=v['id'], species=v['species'], x=(v['x0'], v['x1']), R=v['R'], az=v['az'], a=v['a'], volume_m3=v['volume_m3'],
                                        loaded_t=v['prop_t'], fill=v['fill']) for v in T['vessels']], supports=T['supports']),
               equipment=[dict(id=i['id'], name=i['name'], owner=i['owner'], mass_t=i['mass_t'], cg=i['cg'], envelope=i['envelope'], register=i.get('register', ''),
                               maturity=i.get('maturity', '')) for i in SSI['items']],
               mounts=[dict(item=i['id'], **m) for i in SSI['items'] for m in i['mounts']],
               load_cases=SSI['shared']['load_cases'] + [dict(id=f'PSA-{x}', what=n, axial_g=None, note='PSA data/load_cases.toml') for x, n in
                                                         (('LC-01', 'nominal propulsion'), ('LC-02', 'thrust-bounded envelope'), ('LC-03', 'startup/shutdown transients'),
                                                          ('LC-05', 'engine-out'), ('LC-08', 'thermal'), ('LC-10', 'member failure'), ('LC-14', 'rotating habitat'))],
               load_rule='thrust-bounded (owner PSA-D01): limit x 1.4 ultimate, 1.5 g a separate envelope; lambda target 1.95 x operating thrust (1.87 x DLF 1.04)',
               thermal_interfaces=thermal_interfaces(C), utility_routes=utility_routes(), maintenance_envelopes=maintenance(C), keepouts=SSI['shared']['keepouts'],
               technology_dependencies=tech_deps(),
               structure=struct, mission=dict(velocity_c=0.016, burns=4, thrust_N=THRUST_N, profile='maximum reference capability (WSI-E compares others)'),
               mass=dict(departure_t=Cc['L']['departure_t'], ledger_total_t=total, by_category_t=by_cat, duplicates=dup))
    out = dict(config=cfg, starting_points=starts, ledger=dict(rows=rows, by_category_t=by_cat, total_t=total, duplicates=dup, overlap_checks=overlap,
                                                                 check=f'ledger total {total:,.1f} t vs coupled departure {Cc["L"]["departure_t"]:,.1f} t'),
               history=dict(S_ISSA=A['history'], S_COMB=Cc['history']))
    R.mkdir(parents=True, exist_ok=True)
    (R/'wsi_config.json').write_text(json.dumps(cfg, indent=1, default=float))
    (R/'wsi_cp1.json').write_text(json.dumps(out, indent=1, default=float))
    for s in starts:
        print(f"{s['id']}: departure {s['departure_t']:,.1f} t (reproduces {s.get('reproduces')}), structure {s['structure_t']:,.1f} t, ship {s['ship_length_m']:.1f} m, a_end "
              f"{s['a_end_g']:.3f} g")
    print(f'ledger total {total:,.1f} t vs departure {Cc["L"]["departure_t"]:,.1f}; duplicates {dup}; by category', {k: round(v, 1) for k, v in by_cat.items()})


if __name__ == '__main__':
    main()
