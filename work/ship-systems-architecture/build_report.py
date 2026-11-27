"""Builds the ISSA proposal page (results/issa.html) from systems.toml and the study results. Pure Python + Pillow for the stills.

    python3 work/ship-systems-architecture/build_report.py
"""
import html
import json
import tomllib
from pathlib import Path

H = Path(__file__).resolve().parent
R = H / 'results'
E = html.escape


def stills():
    from PIL import Image
    for n in ('cam_issa_whole_ship', 'cam_issa_power_district', 'cam_issa3_district', 'cam_issa3_unit', 'cam_issa3_tank_sightlines', 'cam_issa4_baffle', 'cam_issa4_sightlines'):
        if not (R / f'{n}.png').exists():
            continue
        im = Image.open(R / f'{n}.png').convert('RGB'); im.thumbnail((1500, 1500)); im.save(R / f'{n}.jpg', quality=82)


def fmt(b, k=1e6, d=2):
    return '–'.join(f'{v/k:.{d}f}' for v in (b[0], b[2])) + f' <span class="nom">({b[1]/k:.{d}f})</span>'


def gap_rows(reg):
    out = []
    for s in reg['system']:
        out.append(f'''<tr data-f="{s['family']}" data-imp="{s['impact']}">
<td class="mono">{E(s['id'])}</td><td><b>{E(s['name'])}</b><div class="fn">{E(s['function'])}</div></td>
<td>{E(s['current'])}</td><td>{E(s['missing'])}</td><td>{E(s['space_now'])}</td><td>{E(s['space_need'])}</td>
<td>{E(s['budget'])}</td><td class="mono">{E(', '.join(s['deps']))}</td>
<td><span class="mat m{s['maturity']}">M{s['maturity']}</span><div class="fn">{E(s['status'])}</div></td>
<td><span class="pri {s['priority']}">{s['priority']}</span> <span class="imp {s['impact']}">{s['impact'].replace('ARCH-', '')}</span></td>
<td>{E(s['next'])}</td></tr>''')
    return '\n'.join(out)


def main():
    stills()
    reg = tomllib.loads((H / 'systems.toml').read_text())
    eps = json.loads((R / 'eps_study.json').read_text())
    dist = json.loads((R / 'districts.json').read_text())
    lon = (R / 'fig_longitudinal.svg').read_text()
    sec = (R / 'fig_sections.svg').read_text()
    M = eps['modes']; st = eps['storage']; pl = eps['plants']; pc = eps['pcsc']; rj = eps['rejection']
    fams = {f['id']: f['name'] for f in reg['family']}
    mat_counts = {}
    for s in reg['system']:
        mat_counts[s['maturity']] = mat_counts.get(s['maturity'], 0) + 1
    archH = [s for s in reg['system'] if s['impact'] == 'ARCH-H']
    mode_rows = '\n'.join(f'<tr><td class="mono">{m}</td><td class="num">{fmt(r["continuous_W"])}</td><td class="num">{fmt(r["peak_add_W"]) if r["peak_add_W"][1] else "–"}</td><td>{E(r["note"])}</td></tr>' for m, r in M.items())
    load_rows = '\n'.join(f'<tr><td class="mono">{l["id"]}</td><td>{E(l["title"])}</td><td class="num">{fmt(l["W"], 1e3, 0)}</td><td>{l["role"]}</td><td><span class="cls {l["cls"]}">{l["cls"]}</span></td><td class="fn">{E(l["basis"])}</td></tr>' for l in eps['loads'])
    dist_rows = '\n'.join(f'<tr><td class="mono">{d["id"]}</td><td>{E(d["name"])}</td><td class="num">{d["x"][0]:.0f} … {d["x"][1]:.0f}</td><td class="num">{d["inside_casing_m3"]:,}</td><td class="num">{d["occupied_m3"]:,}</td><td class="num">{d["reserved_m3"]:,}</td><td class="num">{d["dry_store_m3"]:,}</td><td class="num">{d["free_m3"]:,}</td><td class="num"><b>{d["usable_m3"]:,}</b></td></tr>' for d in dist)
    tot = {k: sum(d[k] for d in dist) for k in ('inside_casing_m3', 'occupied_m3', 'reserved_m3', 'dry_store_m3', 'free_m3', 'usable_m3')}

    def plant_cell(case, k):
        v = pl[case]['candidates'][k]
        return f'{v["single_plant_t"][0]:.0f}–{v["single_plant_t"][2]:.0f} <span class="nom">({v["single_plant_t"][1]:.0f})</span>'
    plant_rows = ''
    for k, c in eps['candidates'].items():
        cells = ''.join(f'<td class="num">{plant_cell(case, k)}</td>' if c['alpha'] else '<td class="num">–</td>' for case in ('ship_service_no_defense', 'ship_service_plus_proactive', 'ship_service_plus_normal_active'))
        plant_rows += f'<tr><td><b>{k.split("_")[0]}</b> {E(c["title"])}</td><td>{E(c["maturity"])}</td>{cells}<td class="fn">{E(c["verdict"])}</td></tr>\n'
    pc_rows = '\n'.join(f'<tr><td>{E(i["item"])}</td><td class="num">{i["t"][0]:.1f}–{i["t"][2]:.1f} <span class="nom">({i["t"][1]:.1f})</span></td></tr>' for i in pc['items'])
    blade_rows = '\n'.join(f'<tr><td class="num">{r["plant_MWe"]:.0f}</td><td class="num">{r["plant_waste_MW"]:.0f}</td><td class="num">{r["defense_heat_MW"]:.0f}</td><td class="num {"bad" if r["blade_area_fraction"] > 1 else ("warn" if r["blade_area_fraction"] > 0.6 else "")}">{100*r["blade_area_fraction"]:.0f} %</td></tr>' for r in rj['shared_blade_area'])
    fam_opts = ''.join(f'<option value="{k}">{E(v)}</option>' for k, v in fams.items())
    import sys; sys.path.insert(0, str(H / 'phase2')); import report2
    sys.path.insert(0, str(H / 'phase3')); import report3
    sys.path.insert(0, str(H / 'phase4')); import report4
    P4 = json.loads((R / 'phase4.json').read_text())
    h5 = next(r for r in P4['transport']['rows'] if r['name'].startswith('H5'))
    P3 = json.loads((R / 'phase3.json').read_text()); cv = {c['name'][:2]: c for c in P3['convergence']['candidates']}
    em = json.loads((R / 'phase2_eclss_mass.json').read_text()); ms = json.loads((R / 'phase2_mission.json').read_text())
    pl2 = json.loads((H.parents[1] / 'references/p1_power_loads.json').read_text())
    l2 = next(r for r in em['mass']['adds'] if r['budget'] == 'PROPOSED.ship_service_generation')
    page = (H / 'report_template.html').read_text()
    for k, v in dict(PHASE4=report4.build(), P4_WARM=f"{next(r for r in P4['thermal']['view_factors'] if '29 m' in r['surface'])['ratio']:.1f}", P4_PUMP=f"{h5['pump_W'][1]/1e6:.0f}",
                     P4_LI=f"{h5['inventory_t'][1]:.0f}", P4_OPT=f"{P4['l2']['optimum_Pe_W'][1]/1e6:.1f}", P4_LIH=f"{P4['district']['transport']['d_m']:.0f}",
                     PHASE3=report3.build(), P3_N2=f"{cv['N2']['dry_added_t'][1]:.0f}", P3_N2DEP=f"{cv['N2']['extra_departure_t'][1]:,.0f}",
                     P3_P2=f"{cv['Ph']['dry_added_t'][1]:.0f}", P3_BAT=f"{100*P3['battery']['options']['R1 L2-first restart']['fraction_BOL'][1]:.0f} %",
                     P3_SH=f"{P3['shielding']['eps_g1']['per_unit_t']:.0f}", PHASE2=report2.build(), P2_COAST=f"{pl2['states']['COAST_HV_PROACTIVE']['continuous_W'][1]/1e6:.1f} MW",
                     P2_L2=f"{l2['t'][1]:.0f}", P2_ADD=f"~{em['mass']['total_added_t'][1]:.0f}", P2_STD=f"{ms['standard_load']['t']:.0f}",
                     P2_CONT=str(ms['standard_load']['containers'])).items():
        page = page.replace('{{' + k + '}}', v)
    for k, v in dict(GAP_ROWS=gap_rows(reg), MODE_ROWS=mode_rows, LOAD_ROWS=load_rows, DIST_ROWS=dist_rows, PLANT_ROWS=plant_rows,
                     PC_ROWS=pc_rows, BLADE_ROWS=blade_rows, FAM_OPTS=fam_opts, FIG_LON=lon, FIG_SEC=sec,
                     N_SYS=str(len(reg['system'])), N_ARCHH=str(len(archH)),
                     MAT_COUNTS=' · '.join(f'M{m}: {n}' for m, n in sorted(mat_counts.items())),
                     TOT_IN=f'{tot["inside_casing_m3"]:,}', TOT_OCC=f'{tot["occupied_m3"]:,}', TOT_RES=f'{tot["reserved_m3"]:,}',
                     TOT_DRY=f'{tot["dry_store_m3"]:,}', TOT_FREE=f'{tot["free_m3"]:,}', TOT_USE=f'{tot["usable_m3"]:,}',
                     PC_USED=f'{pc["used_t"][1]:.1f} t ({pc["used_t"][0]:.0f}–{pc["used_t"][2]:.0f})',
                     PC_LEFT=f'{pc["left_for_generation_t"][1]:.1f} t ({pc["left_for_generation_t"][2]:.0f} to {pc["left_for_generation_t"][0]:.0f})',
                     BAT_COAST=f'{st["NORMAL_COAST"]["main_battery_hours"][1]*60:.0f} min', BAT_HV=f'{st["HIGH_VELOCITY_COAST"]["main_battery_hours"][1]*60:.1f} min',
                     BAT_CRYO=f'{st["SURVIVAL_WITH_CRYO"]["main_battery_hours"][1]:.1f} h', BAT_SURV=f'{st["EMERGENCY_SURVIVAL"]["main_battery_hours"][1]:.0f} h',
                     PACKS=f'{st["survival_packs_2x8kWh_hours"][1]*60:.0f} min', BAT30=f'{st["battery_mass_for_30d_survival_t"][1]:.0f} t',
                     HE3=f'{st["he3_boiloff_uncooled_t_per_day"]:.0f} t').items():
        page = page.replace('{{' + k + '}}', v)
    (R / 'issa.html').write_text(page)
    print('wrote', R / 'issa.html', len(page))


if __name__ == '__main__':
    main()
