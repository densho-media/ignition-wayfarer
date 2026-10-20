"""RAD-004-2026-10-11 (S&E 15!A138, FRONT DATUM STUDY PRIORITY / ROOT GEOMETRY UNCHANGED; 47 SIM-023): the front-datum comparison the owner
asked for after RAD-003. Pure, writes JSON, never edits canon or geometry (the built 9 x 0.125 m seams and aft-root datum stay the source).

Owner: the FRONT post at X 81.149 m (~490 kN/sector working reaction, owner value, not computed here) is the leading structural
comparison, not a flight datum; a cold-start (hot sheet / cold truss) case is mandatory; an insulated C/C or SiC truss at ~550-650 K is a
candidate band, not an achieved temperature; joint 9 needs >= 0.28 m in the worst owner-equivalent case, so 0.25 m is not released as
sufficient: compare >= 0.30 m joint and >= 0.35 m bellows stroke with the material-specific strain and area budget; Mo and Nb are off the
near-term shortlist.

Method: radiator_rad003.combo (the RAD-002 1-D free-strain screen, 0.025 m PROTOTYPE least gap, FRONT scheme) over
  joint 9 in JOINT9_M, the other eight joints in OTHERS_M, sheet materials owner_equivalent / C/C / SiC / W, truss same material or C/C,
  truss states 100 K cold start .. 900 K plus the 550 / 650 K candidate band;
and a bellows check per candidate stroke: the hot displacement and the cold-to-hot stroke range must both fit the candidate stroke.
Strain is the free thermal strain of sheet and truss (no stiffness, so no stress: stress, creep and bond stay OPEN). Area is READBACK.

    python3 src/wayfarer/studies/radiator_rad004.py [--out references/p1_rad004.json]
"""
from pathlib import Path
import argparse
import json
import sys
ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT/'src/wayfarer'), str(ROOT/'src/wayfarer/studies')]
from spec import load
import radiator_expansion as rx
import radiator_rad002 as r2
import radiator_rad003 as r3

JOINT9_M = (0.25, 0.28, 0.30, 0.35)            # 0.25 = RAD-003 reference (not released as sufficient); >= 0.30 the owner's comparison
OTHERS_M = (0.175, 0.20)
STROKES_M = (0.25, 0.30, 0.35)                 # candidate bellows strokes (PROTOTYPE); owner: compare >= 0.35 m
MATERIALS = ('owner_equivalent', 'CC_composite', 'SiC', 'W')     # Mo / Nb removed from the shortlist (15!A138)
TRUSS = dict(r3.TRUSS_STATES, CANDIDATE_550K=550.0, CANDIDATE_650K=650.0)
TRUSS_ORDER = ('COLD_START_100K', 'INSTALL_293K', 'WARM_450K', 'CANDIDATE_550K', 'HOT_600K', 'CANDIDATE_650K', 'POOR_900K')


def run():
    s, *_ = load(ROOT); g0 = rx.geometry(s); mats = r2.materials(g0)
    r3.TRUSS_STATES.update(TRUSS)                 # combo() looks the truss temperature up by name
    out = {}
    for name in MATERIALS:
        m = mats[name]
        for tm in ('same', 'CC_composite'):
            if tm == 'CC_composite' and name == 'CC_composite':
                continue
            mc = m if tm == 'same' else mats['CC_composite']
            for j9 in JOINT9_M:
                for ow in OTHERS_M:
                    seams = [ow]*8+[j9]
                    rows = {}
                    for tn in TRUSS_ORDER:
                        c, _ = r3.combo(s, m, mc, seams, 'FRONT', tn)
                        c['bellows'] = {f'{st:.2f}': c['bellows_max_m'] <= st+1e-9 and c['bellows_stroke_range_m'] <= st+1e-9 for st in STROKES_M}
                        c['strain_sheet_hot'] = m['eps'](rx.T_HOT_K); c['strain_truss'] = mc['eps'](TRUSS[tn])
                        rows[tn] = c
                    ok = [tn for tn in TRUSS_ORDER if rows[tn]['pass']]
                    band = all(rows[t]['pass'] for t in ('COLD_START_100K', 'CANDIDATE_550K', 'CANDIDATE_650K'))
                    stroke_need = max(max(r['bellows_max_m'], r['bellows_stroke_range_m']) for r in rows.values())
                    out[f'{name}|truss_{tm}|j9_{j9:.2f}|others_{ow:.3f}'] = dict(
                        material=name, truss=tm, joint9_m=j9, others_m=ow, passing_truss_states=ok,
                        cold_start_pass=rows['COLD_START_100K']['pass'], candidate_band_pass=band,
                        joint9_min_gap_m=min(r['joint9_min_gap_m'] for r in rows.values()),
                        min_gap_m=min(r['min_gap_m'] for r in rows.values()),
                        ring_A_min_m=min(r['ring_A_min_m'] for r in rows.values()),
                        max_global_slide_m=max(r['max_global_slide_m'] for r in rows.values()),
                        bellows_needed_m=stroke_need,
                        smallest_passing_stroke_m=next((st for st in STROKES_M if stroke_need <= st+1e-9), None),
                        fails={tn: rows[tn]['fails'] for tn in TRUSS_ORDER if not rows[tn]['pass']},
                        area=r3.area(g0, seams))
    return dict(status='DIAGNOSTIC_STUDY_NONCANON (RAD-004-2026-10-11, 15!A138; ROOT GEOMETRY UNCHANGED)',
                method='radiator_rad003.combo, FRONT scheme, free strain only; bellows: hot displacement and cold-to-hot range within the '
                       'candidate stroke; area READBACK (Sheets owns net area, 40!C81:C85)',
                owner_values={'front_post_x_m': g0['frames'][-1], 'front_post_reaction_kN_per_sector': '~490 (owner working, not computed here)',
                              'joint9_worst_owner_equivalent_m': 0.28, 'candidate_truss_band_K': [550, 650]},
                margin_m=r3.MARGIN, joint9_m=JOINT9_M, others_m=OTHERS_M, strokes_m=STROKES_M, truss_states_K={k: TRUSS[k] for k in TRUSS_ORDER},
                shortlist=MATERIALS, removed=['Mo_TZM', 'Nb_C103'], cases=out)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('--out', type=Path, default=ROOT/'references/p1_rad004.json'); a = ap.parse_args()
    r = run()
    a.out.write_text(json.dumps(r, indent=1, default=float)+'\n')
    print(f"{'case':52s} cold  band  j9gap   ringA  slide  bellows stroke  passing truss states")
    for k, c in r['cases'].items():
        print(f"{k:52s} {'P' if c['cold_start_pass'] else 'F':4s}  {'P' if c['candidate_band_pass'] else 'F':4s}  {c['joint9_min_gap_m']:+.3f} "
              f"{c['ring_A_min_m']:.3f} {c['max_global_slide_m']:.3f} {c['bellows_needed_m']:.3f}  {c['smallest_passing_stroke_m']}  "
              f"{','.join(t.split('_')[-1] for t in c['passing_truss_states'])}")
    print(a.out)
