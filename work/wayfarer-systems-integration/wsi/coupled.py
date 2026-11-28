"""WSI Checkpoint 2: coupled architecture (WSI-A convergence, WSI-C propellant trade, WSI-D materials, WSI-E mission profiles).

    python3 work/wayfarer-systems-integration/wsi/coupled.py        # -> results/wsi_cp2.json

The loop: structure (scaled PSA families + stability increments) -> mass -> mission -> propellant and reserves -> tanks -> cryo and
radiators -> structural loads (thrust x mass shares) and stability (ROM + PSA FE anchor) -> structure, repeated to a fixed point.
Numerical convergence (the fixed point) is reported separately from physical satisfaction (stability margin, thermal, volume rules).

STUDY / PROTOTYPE, Track F working configuration unless a row says RESEARCH; noncanon.
"""
import copy
import contextlib
import json
import math

import common
from common import G0, R, THRUST_N, S, cs, issa_point, mm, psa_p2
import rom
import tomllib
from common import PSA

P2 = psa_p2()['variants']['H:hub:F1']
FAM = P2['items_t']
LAM_REQ = 1.95
FE_P2 = dict(static=0.7119, follower=0.6831, groups_static={'trans:00': 0.185, 'frame:00': 0.138, 'ring': 0.102, 'pickup': 0.086, 'diag:01': 0.046,
                                                            'diag:02': 0.040, 'frame:01': 0.036, 'modframe:01': 0.035},
             groups_follower={'deck:15': 0.199, 'rail:04': 0.111, 'rail:05': 0.098, 'rail:03': 0.066, 'rail:06': 0.057, 'iface': 0.05, 'rail:12': 0.049,
                              'rail:13': 0.043}, source='PSA Phase II c3138d8 results/p2_var/H_hub_F1.json')


# ------------------------------------------------------------------------------------------------ structure scaling model (SMM)
def shares(P):
    """Mass shares that set the strength loads under the fixed thrust: farm (deck reaction) and everything forward of the cage."""
    T = P['T']; L = P['L']; farm = T['loaded_t']+L['tankage_t']
    fwd = farm+300.0   # rings, Brow, hub items ahead of the cage end (production rotors 2 x 45 + shield 100 + eye 25 + ECLSS/LOG ~80)
    return dict(farm=farm/L['departure_t'], ahead=fwd/L['departure_t'], farm_len=T['farm_x'][1]-T['farm_x'][0])


REF = None


def smm(P, stiff=None):
    """Structure mass at point P from the PSA Phase II families: deck ~ farm share, cage families ~ ahead share (fixed thrust),
    keels/guides ~ farm length, joints ~ members; plus stability increments `stiff` {family: t}."""
    s = shares(P); r = REF
    k_deck = s['farm']/r['farm']; k_cage = s['ahead']/r['ahead']; k_len = s['farm_len']/r['farm_len']
    out = {}
    for k, v in FAM.items():
        if k.startswith('common thrust deck'):
            out[k] = v*k_deck
        elif k.startswith('forward keels'):
            out[k] = v*k_len*k_deck
        elif k.startswith(('protective casing', 'rotating ring')):
            out[k] = v
        elif k.startswith('node fittings'):
            continue
        else:
            out[k] = v*k_cage
    for k, v in (stiff or {}).items():
        out[k] = out.get(k, 0.0)+v
    mem = sum(v for k, v in out.items() if not k.startswith(('protective', 'rotating')))
    ref_mem = sum(v for k, v in FAM.items() if not k.startswith(('protective', 'rotating', 'node fittings')))
    out['node fittings and joints (explicit, Ti-6Al-4V)'] = FAM['node fittings and joints (explicit, Ti-6Al-4V)']*mem/ref_mem
    return sum(out.values()), out


# ------------------------------------------------------------------------------------------------ stability increments
def local_increment(lam0, groups, group_t, target=LAM_REQ, margin=1.0):
    """Rayleigh energy split of a critical FE mode: 1/lam ~ (1/lam0) sum_g e_g / s_g. Stiffening the listed groups by s (mass x s at
    fixed radius) raises lam until the untouched energy share caps it. Returns the stiffening factor, the added mass and the cap."""
    e_in = sum(groups.values()); cap = lam0/max(1e-9, 1-e_in)
    if cap <= target*margin:
        return dict(possible=False, cap=cap, s=None, added_t=None, note='untouched modal energy caps lambda below the target: stiffen more groups')
    s = e_in/((lam0/(target*margin))-(1-e_in))
    return dict(possible=True, cap=cap, s=s, added_t=(s-1)*group_t, note='Rayleigh estimate on the PSA Phase II mode; FE confirmation required')


def global_increment(P, partial=0.0, rail_t=None, **kw):
    """ROM: rail mass that lifts the global (beam) mode to the target; lambda scales with EI at fixed mass, so iterate for the added mass."""
    rail_t = rail_t or FAM['longerons (rails)']
    ms = rom.mesh(P, rail_t=rail_t, **kw); lam = rom.stability(ms, partial, lam_hi=20.0)['lam']
    return dict(lam=lam, factor_needed=max(1.0, LAM_REQ/lam) if lam else 1.0, rail_t=rail_t)


# ------------------------------------------------------------------------------------------------ mission profiles (WSI-E)
@contextlib.contextmanager
def profile(v_c=0.016, extra_end_t=0.0):
    """Run the coupled mission at cruise v_c (four burns, power-limited at the same drive): dv scales with v; extra_end_t adds provisions."""
    orig = mm.coupled_mission
    import operating_point as op
    s = S(); m0 = op.mission(s); q = op.p(s); ve = q['exhaust_velocity_m_s']; dv0 = ve*math.log(m0['mass_ratio_per_burn'])
    def cm(s_, extra_end_kg=0.0):
        t = copy.deepcopy(s_); qq = op.p(t); n = qq['mission_burns']; f = t['physics']['fuel_loads']['tank_dry_fraction']
        end0 = qq['protected_and_operational_kg']+extra_end_kg+extra_end_t*1e3; p0 = qq['legacy_inventory_kg']
        Rb = math.exp(dv0*v_c/0.016/ve); P = (Rb**n-1)*(end0-f*p0)/(1-(Rb**n-1)*f); end = end0+f*(P-p0)
        return dict(burns=n, mass_ratio_per_burn=Rb, propellant_kg=P, end_mass_kg=end, added_tank_kg=f*(P-p0), departure_mass_kg=end+P)
    mm.coupled_mission = cm
    try:
        yield dict(v_c=v_c, dv_per_burn_m_s=dv0*v_c/0.016, ve=ve)
    finally:
        mm.coupled_mission = orig


# ------------------------------------------------------------------------------------------------ the coupled loop (WSI-A)
def converge(label, stiff_fn=None, iters=12, tol_t=0.5, tank_fn=None, extra_dry=None):
    """Fixed point structure <-> mass. stiff_fn(P) -> {family: t} stability increments (None = strength only)."""
    hist = []; st_t = FAM and sum(FAM.values()); stiff = {}
    for k in range(iters):
        P = issa_point(st_t-common.STRUCT_LINE_T+(extra_dry or 0.0), tank_fn=tank_fn)
        if stiff_fn:
            stiff = stiff_fn(P)
        new_t, fam = smm(P, stiff)
        hist.append(dict(it=k+1, structure_t=new_t, departure_t=P['L']['departure_t'], propellant_t=P['L']['propellant_t'], farm_m=P['T']['added_length_m'],
                         ship_m=P['T']['ship_length_m'], stiff_t=sum(stiff.values())))
        if abs(new_t-st_t) < tol_t:
            st_t = new_t; break
        st_t = new_t
    P = issa_point(st_t-common.STRUCT_LINE_T+(extra_dry or 0.0), tank_fn=tank_fn)
    return dict(label=label, P=P, structure_t=st_t, families_t=fam, stiff_t=stiff, history=hist, converged=len(hist) < iters,
                a_end_g=THRUST_N/(P['L']['end_t']*1e3)/G0)


def summary(c):
    P = c['P']; L = P['L']; T = P['T']
    return dict(label=c['label'], departure_t=L['departure_t'], propellant_t=L['propellant_t'], loaded_t=T['loaded_t'], tankage_t=L['tankage_t'], end_t=L['end_t'],
                structure_t=c['structure_t'], stiffening_t=sum(c['stiff_t'].values()), farm_added_m=T['added_length_m'], ship_length_m=T['ship_length_m'],
                a_end_g=c['a_end_g'], iterations=len(c['history']), converged=c['converged'], history=c['history'],
                families_t={k: round(v, 2) for k, v in c['families_t'].items()})


def rigid(P, h2_aft=None):
    """CG and pitch inertia of the departure ship (c11 rigid bodies at the WSI point)."""
    import c11
    from structure import use_point
    use_point(P); b = c11.config(1.0, True, h2_aft)['bodies']; M, c, J = c11.totals(b)
    return dict(M_t=M/1e3, cg_x=float(c[0]), I_pitch=float(J[1, 1]), I_roll=float(J[0, 0]))


# ------------------------------------------------------------------------------------------------ propellant candidates (WSI-C)
TB_DL_M, TB_AREA = 5.65, 26617.7/24361.4          # ISSA CP1 T-B vs T-A: second deck gap and shell-area ratio (i3d_tanks.json)


def tanks_TB(s, prop_t, carried_t=None):
    T = cs.tanks(s, prop_t, carried_t); d = TB_DL_M
    T = dict(T); T['added_length_m'] += d; T['farm_x'] = (T['farm_x'][0], T['farm_x'][1]+d); T['brow_x'] = (T['brow_x'][0]+d, T['brow_x'][1]+d)
    T['ship_length_m'] += d; T['shell_area_m2'] *= TB_AREA
    T['vessels'] = [dict(v, x1=v['x1']+d) for v in T['vessels']]
    return T


def g_screens(P):
    """Concept G aft storage, screened against the joint layout (owner: not at x -70..-20)."""
    sig = 5.670374e-8
    hull = dict(x=(-119.0, -94.0), a=4.0)
    V = math.pi*hull['a']**2*(hull['x'][1]-hull['x'][0])*0.88           # heads, spine/utility clearance
    rho = dict(H2=70.8, D2=175.2)
    H2_loaded = P['T']['loaded_by_species_t']['hydrogen']
    ann = dict(x=(-125.0, -95.0), r=(8.2, 20.0), sectors=3, sector_deg=110.0)
    A_face = ann['sectors']*(ann['x'][1]-ann['x'][0])*(ann['r'][1]-ann['r'][0])*2             # tank faces toward the two blades of each sector
    q_view = sig*1800.0**4                                                                     # HOT blade face, W/m2 (view factor ~0.5 in a 110 deg sector)
    q_mli = 0.03*q_view*0.5                                                                    # refractory multi-foil shield e* 0.02-0.05
    heat = q_mli*A_face; W_per_W_20K = 50.0
    blade_block = (ann['x'][1]-ann['x'][0])/(41.02+133.25)
    return [dict(id='G-HULL', what='aft vessel inside the hull, x -119..-94 (between the drive transition and the L2 units; MRU, buses and spine start at x -92.7)',
                 volume_m3=V, H2_t=V*rho['H2']/1e3, D2_t=V*rho['D2']/1e3, H2_fraction=V*rho['H2']/1e3/H2_loaded,
                 nuclear='inside the drive-side of the L2 shadow shields: no shadow-cone cover from the drive and L1; neutron/gamma heating at 20 K OPEN (OpenMC surrogate '
                         'not run for this position)', verdict='feasible as a small store; structurally negligible (~3 % of H2)'),
            dict(id='G-ANNULAR', what='three annular sector vessels outside the hull between the HOT blade planes, x -125..-95, r 8.2-20',
                 face_area_m2=A_face, hot_view_W_m2=q_view, heat_through_shield_W=heat, cryo_input_W=heat*W_per_W_20K, HOT_blade_length_blocked=blade_block,
                 verdict=f'NOT FEASIBLE: the sectors are the HOT blades\' view to space; behind a refractory multi-foil shield (e* 0.03) the 20 K load is {heat/1e6:.1f} MW, '
                         f'about {heat*W_per_W_20K/1e9:.1f} GWe of cooler input, and {blade_block*100:.0f} % of the HOT blade length loses its view (radiator must be replaced, owner rule)'),
            dict(id='G-AFT-OF-DRIVE', what='storage aft of the nozzle plane', verdict='NOT FEASIBLE: inside the 15 deg plume cone (K-PLUME)'),
            dict(id='G-BODY-BAY', what='x -70..-20 (PSA Phase II g_aft = 0.3)', verdict='EXCLUDED by the owner (P2-D3); kept as the FE upper bound on the benefit: '
                 'static lambda 0.712 -> 0.817 (+15 %), structure 1,175.7 -> 1,107.8 t', fe_ref='PSA p2_var/H_hub_F1_g_aft=0.3.json')]


def material_table():
    d = tomllib.loads((PSA/'data/materials.toml').read_text()); rows = []
    for mid in ('R-AL6061', 'R-ALLI2195', 'R-TI64', 'R-CFRP-IM', 'R-CFRP-HM', 'F-ALSC-NANO', 'F-CNT-CFRP', 'F-CNT-YARN', 'F-FGM-TI-SIC', 'F-SICSIC-1800'):
        m = next(x for x in d['material'] if x['id'] == mid)
        g = lambda v: (v[1] if isinstance(v, list) else v)
        E, rho = g(m['E']), m['rho']; Fcy = g(m.get('Fcy', m.get('Fty')))
        rows.append(dict(id=mid, track=mid[0], name=m['name'], rho=rho, E_GPa=E, Fcy_MPa=Fcy, alpha_ppm_K=m.get('alpha'), T_max_K=m.get('T_max', m.get('T_max_K')),
                         specific_modulus_MJ_kg=E*1e3/rho, specific_compression_kJ_kg=Fcy*1e3/rho, rail_mass_for_AL_EI=68.9/2700*rho/E,
                         creep=('negligible below 0.4 Tm' if mid.startswith(('R-AL', 'F-AL', 'R-TI')) else 'matrix-limited above ~400 K' if 'CFRP' in mid or 'CNT' in mid else 'fibre creep 1600-1800 K'),
                         fatigue=('97 MPa @1e7 (6061)' if mid == 'R-AL6061' else 'good in fibre direction, interlaminar-limited' if 'CFRP' in mid else 'n/a' if 'YARN' in mid else 'OPEN'),
                         joint_efficiency=(0.6 if 'CFRP' in mid or 'CNT' in mid else 0.85),
                         radiation=('metallic: displacement damage negligible at hull doses' if mid.startswith(('R-AL', 'F-AL', 'R-TI', 'F-FGM')) else 'matrix crosslink/scission: OPEN dose limit; keep inside shadow cones'),
                         manufacturing=m.get('lunar', m.get('source', ''))[:80], restricted=m.get('restricted', '')))
    return rows


def main():
    global REF
    base = issa_point(sum(FAM.values())-common.STRUCT_LINE_T)        # S-COMB (Phase II structure)
    REF = shares(base)
    ms = rom.mesh(base); f_raw = rom.stability(ms, 1.0, lam_hi=20.0, cal=False)['f1_Hz']
    rom.CAL['factor'] = (0.0956/f_raw)**2; rom.CAL['basis'] = f'first free-free bending frequency matched to PSA FE 0.0956 Hz (ROM {f_raw:.4f} Hz)'
    out = dict(rom_calibration=dict(rom.CAL), reference_shares=REF, fe_phase2=FE_P2)
    # 1 strength-only convergence (T-A)
    A = converge('T-A strength-sized (no stability closure)')
    PA = A['P']
    gs = {p: rom.stability(rom.mesh(PA, struct_t=A['structure_t']), p, lam_hi=20.0) for p in (0.0, 1.0)}
    out['strength_only'] = dict(summary(A), rom_lambda={('fixed' if p == 0 else 'follower'): gs[p] for p in gs})
    # 2 global closure for the fixed-direction (TVC) case by rail material; follower and local modes from FE (PSA)
    lam_fix = gs[0.0]['lam']; need = LAM_REQ/lam_fix if lam_fix else 1.0
    mats = []
    for mt in material_table():
        if mt['id'] not in ('R-AL6061', 'R-CFRP-HM', 'F-ALSC-NANO', 'F-CNT-CFRP'):
            continue
        rail_t = FAM['longerons (rails)']*max(need, 1.0)*mt['rail_mass_for_AL_EI']
        def sf(P, rail_t=rail_t):
            return {'longerons (rails)': rail_t-FAM['longerons (rails)']}
        c = converge(f'T-A + global EI x{need:.2f} with {mt["id"]} rails', sf)
        lam2 = rom.stability(rom.mesh(c['P'], rail_t=FAM['longerons (rails)']*need, struct_t=c['structure_t']), 0.0, lam_hi=20.0)
        mats.append(dict(material=mt['id'], track=mt['track'], rail_t=rail_t, **{k: v for k, v in summary(c).items() if k != 'history'}, rom_fixed_lambda=lam2))
    out['global_closure'] = dict(rom_fixed_lambda=lam_fix, factor=need, options=mats,
                                 note='global beam mode only (TVC-held thrust); the local aft-structure and deck modes need the FE (PSA TD-A..F)')
    # 3 propellant candidates
    cand = []
    for lab, tf, extra in (('T-A', None, 0.0), ('T-B tandem modular', tanks_TB, 64.0*(base['L']['tankage_t']/686.4)+0.15*FAM['common thrust deck (tank-farm aft)'])):
        c = converge(lab, tank_fn=tf, extra_dry=extra); P = c['P']
        rg = rigid(P); lamr = {p: rom.stability(rom.mesh(P, struct_t=c['structure_t']), p, lam_hi=20.0)['lam'] for p in (0.0, 1.0)}
        cr = cs.cryo(S(), P['T']['shell_area_m2'])
        cand.append(dict(id=lab, **{k: v for k, v in summary(c).items() if k != 'history'}, cg_x=rg['cg_x'], I_pitch=rg['I_pitch'], rom_lambda=lamr,
                         shell_area_m2=P['T']['shell_area_m2'], cryo_input_kW=cr['operating_input_W']/1e3, extra_dry_t=extra))
    gsc = g_screens(PA)
    gh = gsc[0]
    h2 = dict(fraction=gh['H2_fraction'], x=(-119.0, -94.0), r=0.0, n=1, az=(0.0,), a=4.0)
    rgh = rigid(PA, h2); lam_gh = {p: rom.stability(rom.mesh(PA, h2_aft=h2, struct_t=A['structure_t']), p, lam_hi=20.0)['lam'] for p in (0.0, 1.0)}
    cand.append(dict(id='G-HULL (3 % H2 aft)', departure_t=PA['L']['departure_t'], cg_x=rgh['cg_x'], I_pitch=rgh['I_pitch'], rom_lambda=lam_gh,
                     note='same mass; farm shortening ignored (<1 m)'))
    out['propellant'] = dict(candidates=cand, g_screens=gsc)
    # 4 mission profiles (strength-sized T-A; stability closure is the same family of increments)
    prof = []
    for pid, v, ext in (('P-MAX maximum capability', 0.016, 0.0), ('P-REF reference high-performance', 0.014, 0.0), ('P-STD standard', 0.012, 0.0),
                        ('P-EXT extended (standard speed, +12 months provisions)', 0.012, 23.0)):
        with profile(v, ext) as pr:
            c = converge(pid)
        sm = summary(c); burn_s = (sm['propellant_t']*1e3/4)*pr['ve']/THRUST_N
        prof.append(dict(id=pid, v_c=v, provisions_extra_t=ext, **{k: v_ for k, v_ in sm.items() if k != 'history'}, burn_days_each=burn_s/86400,
                         cruise_time_ratio=0.016/v))
    out['profiles'] = prof
    out['materials'] = material_table()
    (R/'wsi_cp2.json').write_text(json.dumps(out, indent=1, default=float))
    s = out['strength_only']
    print(f"strength-only T-A: {s['departure_t']:,.0f} t, structure {s['structure_t']:,.0f} t, ship {s['ship_length_m']:.1f} m, it {s['iterations']}, ROM lambda {s['rom_lambda']}")
    for m in mats:
        print(f"  {m['material']}: rails {m['rail_t']:.0f} t, departure {m['departure_t']:,.0f} t, ROM fixed {m['rom_fixed_lambda']['lam']:.2f}")
    for c in cand:
        print('  ', c['id'], round(c['departure_t']), c.get('ship_length_m'), round(c['cg_x'], 1), '%.3g' % c['I_pitch'], c['rom_lambda'])
    for p in prof:
        print('  ', p['id'], round(p['departure_t']), round(p['propellant_t']), round(p['ship_length_m'], 1), round(p['burn_days_each'], 1))


if __name__ == '__main__':
    main()
