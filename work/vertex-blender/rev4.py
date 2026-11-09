"""T05 Stage B revision 4: geometry inputs for the closure-coil assemblies, and the geometry feedback T05 hands to T00.
Standard library only; run from the project root: python3 work/vertex-blender/rev4.py  -> work/vertex-blender/rev4.json

NON-CANON. The coil radial build is a PROTOTYPE assembly drawn around T03's field-limited windings (C_W15, scaled to V4). The
case uses T03's own virial strength basis, so its mass matches T03's 1,281 t ledger (scaled). Layer thicknesses outside the case are
PROTOTYPE allowances, taken from large superconducting magnet practice in shape only. No value here feeds the propulsion calculator;
T00 owns the energy ledger (lab/variants/vertex-drive/, branch claude/project-thread-9rsgog) and reads rev4_geometry.json.

If T00's handoff lab/variants/vertex-drive/results/t05_handoff_rev4.json exists on the T00 branch, the caller saves a copy as
work/vertex-blender/t00_handoff_rev4.json (git show) and this script carries its keys into rev4.json unchanged under 't00'."""
import json
import math
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
import screen  # noqa: E402

T00_BRANCH = 'origin/claude/project-thread-9rsgog'
T03_PATH = 'lab/variants/vertex-drive/studies/nozzle/results/nozzle_results.json'
ESCAPE_XRAY_W = 412e9          # T00 ISS-014 sec. 1: escaping X-ray power at V4 (radiation_on_hardware 10.2 GW / Omega 0.0248)

# PROTOTYPE layer allowances outside the structural case, burn side, metres (radial build, inner -> outer)
LAYERS = [
    ('cryostat_vacuum_mli', 0.10, 'vacuum gap and multilayer insulation around the 20 K case'),
    ('thermal_shield_80K', 0.07, 'actively cooled 80 K shield (He gas) plus its gap'),
    ('cryostat_wall', 0.03, 'vacuum boundary'),
    ('warm_eddy_screen', 0.05, 'T03 warm eddy screen, cooled; takes the armour back-face re-radiation'),
    ('standoff_gap', 0.30, 'low-conductance stand-offs carry the armour off the cryostat; robot tool clearance for segment exchange'),
    ('armour_coolant', 0.04, 'tin channels in the armour back plate (the 1,800 K hot-loop fluid)'),
    ('armour_face', 0.03, 'sacrificial plasma- and X-ray-facing tiles; material and thickness wait for T00 sec. 5'),
]
CASE_RHO = 1700.0              # T03 implies sigma/rho from virial_kg_per_J; the case is drawn at CFRP density on that basis
STEEL = {'rho': 7900.0, 'sigma': 6.6e8}   # cryogenic structural steel sensitivity case (316LN-class allowable, PROTOTYPE)
SEGMENTS = 12                  # replaceable armour segments per coil, as Rev 2 P2


def t03():
    try:
        txt = subprocess.run(['git', 'show', f'{T00_BRANCH}:{T03_PATH}'], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        txt = (HERE/'t03_nozzle_results_cache.json').read_text()
    (HERE/'t03_nozzle_results_cache.json').write_text(txt)
    d = json.loads(txt)
    return d['designs']['C_W15'], d['assumptions']


def coil_assemblies():
    des, asm = t03()
    e = json.loads((HERE/'screen.json').read_text())['generations']['V4']
    xB = e['x_burn_m']
    s = None
    out = {'basis': 'T03 nozzle_results.json C_W15 (T00 branch), scaled to V4 by the stand-off ratio; B 25 T at the winding surface',
           'escape_xray_W': ESCAPE_XRAY_W, 'layers_PROTOTYPE': [{'id': i, 't_m': t, 'what': w} for i, t, w in LAYERS], 'coils': {}, 'cases': {}}
    sig_eff = CASE_RHO/asm['virial_kg_per_J']
    for c, L in zip(e['closure_coils'], des['loops'][:2]):
        sc = c['r_m']/L['radius_m']; s = s or sc
        d = math.hypot(c['x_m']-xB, c['r_m']); polar = math.atan2(c['r_m'], c['x_m']-xB)
        i = [l['name'][:2] for l in des['loops']].index(c['name'])
        hoop = des['ledger']['hoop_tension_MN'][i]*1e6*sc*sc          # B fixed, I ~ s, hoop ~ B I R ~ s^2
        a_w = c['winding_minor_m']
        I = des['ledger']['currents_MA'][i]*1e6*sc
        A_cond = I/1e9                                                 # J_eng 1e9 A/m2 (T03 assumption)
        A_case = hoop/sig_eff
        A_case_steel = hoop/STEEL['sigma']
        builds = {
            # NOMINAL: case is an annulus outside the field-limited winding envelope (conservative for the X-ray share)
            'R4_NOMINAL': math.sqrt(A_case/math.pi+a_w*a_w),
            # COMPACT: case nested inside the 25 T envelope where it fits (conductor fills only A_cond of pi a_w^2)
            'R4_COMPACT': max(a_w, math.sqrt((A_cond+A_case)/math.pi)),
            # STEEL: the same annulus at a 660 MPa steel allowable
            'R4_STEEL_CASE': math.sqrt(A_case_steel/math.pi+a_w*a_w),
        }
        fixed = sum(t for _, t, _ in LAYERS)
        rows = {}
        for k, r_case in builds.items():
            r_out = r_case+fixed
            rows[k] = {'case_outer_m': r_case, 'assembly_outer_m': r_out}
        rows['T03_3X_WINDING'] = {'case_outer_m': None, 'assembly_outer_m': 3*a_w}
        rows['REV2_COPIED_C1'] = {'case_outer_m': None, 'assembly_outer_m': c['envelope_r_m'][1]}
        for k, r in rows.items():
            h = r['assembly_outer_m']
            share = math.sin(polar)*math.sin(math.asin(min(h/d, 1.0)))       # band between polar +- asin(h/d), half of (cos - cos)
            r['projected_half_width_m'] = h
            r['share'] = share
            r['xray_W'] = share*ESCAPE_XRAY_W
            r['burn_face_m2'] = 2*math.pi*c['r_m']*math.pi*h               # burn-facing half of the tube surface
            r['projected_m2'] = 2*math.pi*c['r_m']*2*h
            r['flux_mean_W_m2'] = r['xray_W']/r['burn_face_m2']
        # layer ladder for the nominal build: projected half-width of each layer as seen from the burn point
        ladder = [{'layer': 'winding_25T_envelope', 'outer_m': a_w}, {'layer': 'structural_case', 'outer_m': builds['R4_NOMINAL']}]
        r = builds['R4_NOMINAL']
        for lid, t, _ in LAYERS:
            r += t; ladder.append({'layer': lid, 'outer_m': r})
        for row in ladder:
            row['share_if_outermost'] = math.sin(polar)*row['outer_m']/d
        out['coils'][c['name']] = {
            'x_m': c['x_m'], 'r_m': c['r_m'], 'distance_from_burn_m': d, 'polar_deg': math.degrees(polar), 'scale_from_T03': sc,
            'current_A': I, 'hoop_tension_N': hoop, 'winding_25T_minor_m': a_w, 'conductor_area_m2': A_cond,
            'case_area_m2_T03_virial': A_case, 'case_area_m2_steel': A_case_steel,
            'case_mass_kg_T03_virial': A_case*2*math.pi*c['r_m']*CASE_RHO, 'case_mass_kg_steel': A_case_steel*2*math.pi*c['r_m']*STEEL['rho'],
            'builds': rows, 'ladder_nominal': ladder,
            'armour_segment_arc_deg': 360.0/SEGMENTS, 'armour_segment_length_m': 2*math.pi*c['r_m']/SEGMENTS,
            'armour_shell_area_m2_nominal': rows['R4_NOMINAL']['burn_face_m2'],
        }
    for k in ('R4_NOMINAL', 'R4_COMPACT', 'R4_STEEL_CASE', 'T03_3X_WINDING', 'REV2_COPIED_C1'):
        out['cases'][k] = {'C1_W': out['coils']['C1']['builds'][k]['xray_W'], 'C2_W': out['coils']['C2']['builds'][k]['xray_W']}
        out['cases'][k]['total_W'] = out['cases'][k]['C1_W']+out['cases'][k]['C2_W']
        out['cases'][k]['share_total'] = out['cases'][k]['total_W']/ESCAPE_XRAY_W
    out['preferred'] = 'R4_NOMINAL'
    out['note'] = ('the share uses the outermost layer of the full assembly (armour, which must shadow everything behind it); a share of '
                   'sin(polar) * h / d is the band between polar +- h/d; the Blender ray cast (rev4_geometry.json raycast) checks it on the drawn mesh')
    return out


# coolant plant (PROTOTYPE): tin hot loop shared with the wing hot band (T01 fluid), lines run in the shadow of the coil struts
TIN = {'cp_dT_J_kg': 72e3, 'rho': 6990.0}       # rev3.json basis: 300 K rise into the 1,800 K hot loop
LI = {'cp_dT_J_kg': 4170.0*300.0, 'rho': 430.0}   # liquid lithium near 1,700 K, 300 K rise; SP-100 heritage is Li in Nb-1Zr at about 1,350 K
FLUIDS = {'SN_DIRECT': TIN, 'LI_LOOP_HX': LI}
HX_KG_PER_W = 2.0e-5                             # Li -> Sn heat exchanger at the hot-band root, 20 t/GW, PROTOTYPE (UNKNOWN)
V_LINE = 5.0                                     # m/s
PAIRS = 6                                        # one supply + one return per strut (6 C1 struts, 6 C2 ties)
DP = 1.0e6                                       # Pa loop pressure drop, PROTOTYPE
ETA_PUMP = 0.5                                   # electromagnetic liquid-metal pump, PROTOTYPE
PIPE = {'sigma_creep_Pa': 5.0e7, 'rho': 10200.0, 'p_Pa': 1.0e6, 'min_t_m': 0.004}   # Mo-TZM class at 1,800 K, creep-limited, PROTOTYPE
PUMP_KG_PER_W = 1.0e-3                           # 1 t/MW electric, PROTOTYPE (UNKNOWN)
ARMOUR_AREAL = {'face_CFC_kg_m2': 0.03*1900.0, 'backplate_Mo_50pct_kg_m2': 0.04*0.5*10200.0}


def coil_plant(ca):
    e = json.loads((HERE/'screen.json').read_text())['generations']['V4']
    r2 = json.loads((HERE/'rev2.json').read_text())
    hot_x0 = r2['thermal']['preferred_rev2']['hot_x_m'][0]
    strut_L = r2['coils']['struts']['length_m']
    c1, c2 = e['closure_coils']
    tie_L = math.hypot(c1['x_m']-c2['x_m'], c1['r_m']-c2['r_m'])
    run_L = hot_x0-e['x_shield_aft_m']+3.0                      # reaction ring forward to the hot-band root, plus the radial drop
    out = {'basis': '300 K coolant rise, 5 m/s, six supply/return pairs per coil in the strut shadows, ring manifolds fed at six points '
                    '(12 segments, so each manifold arc carries 1/12 of the flow), 1 MPa, Mo-TZM pipe at 50 MPa creep (all PROTOTYPE)',
           'fluids': {k: dict(v) for k, v in FLUIDS.items()}, 'cases': {}}
    for fl, F in FLUIDS.items():
        for key, case in ca['cases'].items():
            V1 = case['C1_W']/F['cp_dT_J_kg']/F['rho']; V2 = case['C2_W']/F['cp_dT_J_kg']/F['rho']
            legs = [('C2_to_C1', V2, tie_L), ('C1_to_ring', V1+V2, strut_L), ('ring_to_hot_root', V1+V2, run_L)]
            lines = []; vol_m3 = 0.0; pipe_kg = 0.0
            for nm, V, L in legs:
                r = math.sqrt(V/PAIRS/V_LINE/math.pi)
                t = max(PIPE['p_Pa']*r/PIPE['sigma_creep_Pa'], PIPE['min_t_m'])
                vol = 2*PAIRS*math.pi*r*r*L; kg = 2*PAIRS*2*math.pi*r*t*L*PIPE['rho']
                vol_m3 += vol; pipe_kg += kg
                lines.append({'leg': nm, 'flow_m3_s': V, 'line_r_m': r, 'wall_m': t, 'length_m': L, 'fluid_m3': vol, 'pipe_kg': kg})
            arm_m2 = {n: ca['coils'][n]['builds'][key]['burn_face_m2'] for n in ('C1', 'C2')}
            chan_m3 = sum(arm_m2.values())*0.04*0.5
            man = {n: math.sqrt((V1 if n == 'C1' else V2)/12/V_LINE/math.pi) for n in ('C1', 'C2')}
            man_m3 = sum(2*2*math.pi*ca['coils'][n]['r_m']*math.pi*man[n]**2 for n in ('C1', 'C2'))      # supply + return rings
            vol_m3 += chan_m3+man_m3
            hyd = (V1+V2)*DP; el = hyd/ETA_PUMP
            armour_kg = sum(arm_m2.values())*sum(ARMOUR_AREAL.values())
            hx = case['total_W']*HX_KG_PER_W if fl == 'LI_LOOP_HX' else 0.0
            plant = vol_m3*F['rho']+pipe_kg+el*PUMP_KG_PER_W+hx
            out['cases'][f'{fl}:{key}'] = {
                'fluid': fl, 'build': key, 'heat_W': case['total_W'], 'flow_m3_s': V1+V2, 'flow_C1_m3_s': V1, 'flow_C2_m3_s': V2, 'lines': lines,
                'manifold_r_m': man, 'armour_channel_m3': chan_m3, 'manifold_m3': man_m3, 'fluid_m3': vol_m3, 'fluid_kg': vol_m3*F['rho'],
                'pipe_kg': pipe_kg, 'pump_hydraulic_W': hyd, 'pump_electric_W': el, 'pump_kg': el*PUMP_KG_PER_W, 'hx_kg': hx,
                'armour_m2': arm_m2, 'armour_kg_PROTOTYPE_areal': armour_kg, 'plant_kg': plant, 'plant_plus_armour_kg': plant+armour_kg}
    out['preferred'] = 'LI_LOOP_HX:R4_NOMINAL'
    out['armour_areal_PROTOTYPE'] = ARMOUR_AREAL
    return out


def main():
    out = {'revision': 4, 'coil_assembly': coil_assemblies()}
    out['coil_plant'] = coil_plant(out['coil_assembly'])
    hp = HERE/'t00_handoff_rev4.json'
    if hp.exists():
        out['t00'] = json.loads(hp.read_text())
    (HERE/'rev4.json').write_text(json.dumps(out, indent=1, default=float))
    ca = out['coil_assembly']
    for k, v in ca['cases'].items():
        print(f"{k:16s} C1 {v['C1_W']/1e9:5.2f} GW  C2 {v['C2_W']/1e9:5.2f} GW  total {v['total_W']/1e9:5.2f} GW  share {v['share_total']:.4f}")
    for n, c in ca['coils'].items():
        print(n, {k: round(v['assembly_outer_m'], 3) for k, v in c['builds'].items()}, f"hoop {c['hoop_tension_N']/1e9:.2f} GN",
              f"case {c['case_mass_kg_T03_virial']/1e3:,.0f} t (steel {c['case_mass_kg_steel']/1e3:,.0f} t)")
    for k, v in out['coil_plant']['cases'].items():
        print(f"plant {k:28s} flow {v['flow_m3_s']:5.1f} m3/s fluid {v['fluid_kg']/1e3:6.0f} t hx {v['hx_kg']/1e3:4.0f} t pipe {v['pipe_kg']/1e3:5.0f} t pump {v['pump_electric_W']/1e6:4.0f} MWe {v['pump_kg']/1e3:4.0f} t"
              f" armour {v['armour_kg_PROTOTYPE_areal']/1e3:5.0f} t  total {v['plant_plus_armour_kg']/1e3:6.0f} t; lines r " + ', '.join(f"{l['line_r_m']:.2f}" for l in v['lines']))


if __name__ == '__main__':
    main()
