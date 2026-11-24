#!/usr/bin/env python3
"""AMPN Phase 3: braking-phase dust protection for the RON/AMPN engine layout (research, not canon).

Question (owner AMPN brief section 4): can the fusion exhaust, redistributed in a braking mode (Mode B), protect the ship from
interstellar and Kuiper-belt dust at up to 0.016 c, and how does it compare with passive stern shielding and hybrids?

Inputs
  * dust environment, mission path and damage rules: lab/studies/dust-impacts/model.py (Vertex 2.6 T02 environment, the corrected
    braking path, the JUSTIFIED envelope); imported read-only.
  * engine layout: the RON/AMPN design (ring radius, plug radius, ship distance D, engine spacing S) and its burn time and ve.
  * exhaust: canon jet (5.44 MN, ve 1.92e7 m/s per engine, 4 engines).

Physics classes: ESTABLISHED (stopping powers, charging limits, rigidity, Whipple scaling as the dust study uses it), MODELLED (plume
column, cloud expansion), EXTRAPOLATION (impacts above 100 km/s; the dust study's caveat), SPECULATIVE (hybrid plasma deflection).
Standard library only. `python3 lab/studies/vertex-compact-engine/vertex-ampn/dust.py` writes results/dust.json and results/dust.log.
"""
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT / 'lab' / 'studies' / 'dust-impacts'))
import model as M  # noqa: E402
P = M.P

C = 299792458.0
MU0 = 4e-7 * math.pi
EPS0 = 8.8541878128e-12
AMU = 1.66053907e-27
QE = 1.602176634e-19
V = 0.016 * C                      # CANON cruise
RHO_G = P.RHO_GRAIN                # 2,500 kg/m3
E_VAP = 1.3e7                      # J/kg, silicate heated, melted and vaporised (LITERATURE order, forsterite)
# Exhaust ions meet the grain at v_e + V (2.4e7 m/s, about 3 MeV/u). Bethe stopping for protons and alphas in silicate at 3 MeV/u
# (PSTAR/ASTAR order: 110 and 440 MeV cm2/g) gives the same energy per kg of exhaust crossed, because z^2/A is 1 for both.
K_DEP = 1.05e15                    # J per kg of grain per kg/m2 of exhaust column (ESTABLISHED order)
ION_RANGE = 9e-5                   # m, 3 MeV/u p and alpha in silicate (ESTABLISHED order)
E_FIELD_LIMIT = 3e10               # V/m, ion field evaporation limit on a positively charged grain (upper bound on charge)
VAPOUR_SPEED = 5e3                 # m/s, expansion of a grain vaporised by ion heating (energy ~ E_VAP)

THRUST = 5.44e6
VE = 1.92e7
MDOT = THRUST / VE                 # 0.283 kg/s per engine
N_ENG = 4
R_SHIP = 45.0
BOOM_FENCE = 50.0                  # m, a strip bumper on struts ahead of each duct, both sides (PROTOTYPE)
W_DUCT = 1.0                       # m, width of the protected services duct along each boom (PROTOTYPE)


def grain(a):
    m = 4 / 3 * math.pi * a ** 3 * RHO_G
    return m, 0.5 * m * V * V


# ---------- 1. what the exhaust can do to one grain ---------------------------------------------------------------------------------
def plume_column(theta_deg, x0, mdot=MDOT):
    """Effective exhaust column (kg/m2) a grain meets crossing a conical plume of half-angle theta from distance x0 outward, counting the
    plume moving toward it (encounter factor 1 + ve/V)."""
    t = math.tan(math.radians(theta_deg))
    return mdot * (1 / VE + 1 / V) / (math.pi * t * t * x0)


def grain_effects(a, sigma):
    """What an exhaust column sigma does to a grain of radius a."""
    m, KE = grain(a)
    path = 4 / 3 * a                                                   # mean chord of a sphere
    e_dep = K_DEP * sigma * min(1.0, ION_RANGE / path) if path > 0 else 0.0   # J/kg: ions that pass through deposit range/path share
    e_dep = K_DEP * sigma if path <= ION_RANGE else K_DEP * sigma * ION_RANGE / path
    frac_vap = min(1.0, e_dep / E_VAP)
    # momentum: exhaust momentum stopped in the grain (ions that cross it transfer the deposited share only)
    stop_share = min(1.0, path / ION_RANGE)
    dv = sigma * (VE + V) * stop_share / (RHO_G * path)               # m/s removed from the grain
    return dict(a_m=a, m_kg=m, KE_J=KE, KE_over_Evap=KE / (m * E_VAP), e_dep_J_kg=e_dep, vaporised_share=frac_vap,
                dv_m_s=dv, dv_over_V=dv / V, KE_removed_share=1 - (1 - min(1.0, dv / V)) ** 2)


def charge_limits(a, field_Tm):
    """Largest charge a grain can hold (field evaporation) and the deflection a field integral gives it at V."""
    q_m = 3 * EPS0 * E_FIELD_LIMIT / (RHO_G * a)                      # C/kg, phi = E_lim * a
    rig = V / q_m                                                     # T m
    return dict(q_over_m_C_kg=q_m, rigidity_Tm=rig, deflection_rad=field_Tm / rig)


def ring_far_field_integral(I_A, R, lateral):
    """Field integral (T m) of a ring dipole along a line passing it at a lateral distance (B ~ mu0 m / 4 pi r^3; integral ~ 2 mu0 m /
    (4 pi b^2))."""
    mdip = I_A * math.pi * R * R
    return 2 * MU0 * mdip / (4 * math.pi * lateral ** 2)


def rigidity_ion(A, q):
    return A * AMU * V / (q * QE)


# ---------- 2. Mode B: the exhaust spread to cover the ship --------------------------------------------------------------------------
def mode_b(v, thetas=(5, 10, 20, 30, 45, 60, 75)):
    """The four plumes widened until their edges cover the ship's stern line. In braking the dust comes from aft of the engines (the
    exhaust side); the ship's path lies a lateral offset S/sqrt2 from each engine axis, so a plume covers it only beyond x_cover."""
    lat = v['S'] / math.sqrt(2)
    rows = []
    a_dmg = (3 * v['m_damage'] / (4 * math.pi * RHO_G)) ** (1 / 3)
    for th in thetas:
        t = math.tan(math.radians(th))
        x_cover = (lat + R_SHIP) / t                                   # where the plume edge reaches the far side of the ship
        sig = N_ENG * plume_column(th, x_cover)                        # all four plumes overlap there at best
        e = grain_effects(a_dmg, sig)
        # column needed to stop the damaging grain's momentum outright (dv = V)
        need = RHO_G * 4 / 3 * a_dmg * V / (VE + V) / min(1.0, 4 / 3 * a_dmg / ION_RANGE)
        mdot_need = need / sig * N_ENG * MDOT
        # largest grain the column vaporises completely (ion heating)
        a_vap = None
        lo, hi = 1e-9, 1e-2
        if grain_effects(lo, sig)['vaporised_share'] >= 1:
            for _ in range(80):
                mid = math.sqrt(lo * hi)
                lo, hi = (mid, hi) if grain_effects(mid, sig)['vaporised_share'] >= 1 else (lo, mid)
            a_vap = lo
        # dispersal of what is vaporised: a puff expanding at VAPOUR_SPEED for the time to reach the ship
        t_fly = (x_cover + v['D']) / V
        r_puff = VAPOUR_SPEED * t_fly
        rows.append(dict(theta_deg=th, x_cover_m=x_cover, column_kg_m2=sig, column_needed_kg_m2=need, shortfall=need / sig,
                         mdot_needed_kg_s=mdot_need, mdot_available_kg_s=N_ENG * MDOT, a_vaporised_max_m=a_vap,
                         damaging_grain=e, puff_radius_at_ship_m=r_puff,
                         thrust_axial_share=math.cos(math.radians(th)) * 0.5 * (1 + math.cos(math.radians(th))) if th else 1.0))
    return rows


# ---------- 3. exposure and passive protection ---------------------------------------------------------------------------------------
def faces(v):
    """Faces each mode exposes. The RON layout puts the engines S/sqrt2 off the ship axis, outside the Brow's shadow, so they lead in both
    directions; the ship's stern leads in braking with no engine in front of it."""
    lat = v['S'] / math.sqrt(2)
    ring = N_ENG * 2 * math.pi * v['R'] * v['ring_w']
    plug = N_ENG * math.pi * v['r_plug'] ** 2
    # booms: the truss chords tolerate millimetre holes; the sensitive part is the services duct (cryo, Li, power) of width W_DUCT that
    # runs inside the boom; a strip bumper ('fence') on struts up to BOOM_FENCE ahead of it on each side, else armour
    boom = N_ENG * W_DUCT * max(0.0, lat - R_SHIP)
    return [
        dict(name='ship stern disc (stern screen on a mast)', area=math.pi * R_SHIP ** 2, leads='ENGINE_FIRST', standoff=v['D'] / 2),
        dict(name='ring aft faces (nose, in the exhaust)', area=ring, leads='ENGINE_FIRST', standoff=0.0),
        dict(name='plug aft faces (lit cone)', area=plug, leads='ENGINE_FIRST', standoff=0.0),
        dict(name='boom services ducts, braking', area=boom, leads='ENGINE_FIRST', standoff=BOOM_FENCE),
        dict(name='ring forward faces', area=ring, leads='BOW_FIRST', standoff=2.0),
        dict(name='plug forward faces (slug)', area=plug, leads='BOW_FIRST', standoff=5.0),
        dict(name='boom services ducts, bow-first', area=boom, leads='BOW_FIRST', standoff=BOOM_FENCE),
    ]


def protect_face(f, segs, case):
    it = dict(P.lead_item(f['name'], f['area']), leads=f['leads'])
    bare = P.events(it, segs, P.perforation_energy(0.005, P.K_CRATER[case]), case)
    S = P.required_standoff(it, segs, case)
    arm = P.armour_thickness(it, segs, case)
    ero = P.K_CRATER[case] * P.energy_fluence(it, segs, case)
    out = dict(face=f['name'], leads=f['leads'], area_m2=f['area'], bare_5mm_breaches=bare, standoff_needed_m=S,
               standoff_available_m=f['standoff'], armour_t_m=arm['t_m'], erosion_m=ero)
    opts = []
    if S is not None and S <= f['standoff'] and f['standoff'] > 0:
        sb, sw = P.bumper_kg_m2(S, case)
        opts.append(('bumper', f['area'] * (sb + sw + ero * P.RHO_BUMPER) / 1e3))
    if arm['t_m']:
        opts.append(('armour', arm['mass_t'] + f['area'] * ero * P.RHO_BUMPER / 1e3))
    kind, m = min(opts, key=lambda o: o[1]) if opts else ('none closes', None)
    out.update(kind=kind, mass_t=m)
    if S is not None:
        sb, sw = P.bumper_kg_m2(S, case)
        out['remote_screen_t'] = f['area'] * (sb + sw + ero * P.RHO_BUMPER) / 1e3
    return out


def hybrid(v, segs, case):
    """SPECULATIVE: sacrificial screen ahead of the stern turns grains to plasma; a stern magnet deflects the plasma. The cloud is
    super-Alfvenic (it pushes the field aside) until its kinetic energy falls below the field energy it occupies, so the magnet only
    handles grains with KE < (B^2/2mu0) * (4/3) pi (S tan a)^3. Compared with simply moving the screen further out."""
    rows = []
    b = P.BUMPER[case]
    for S in (10.0, 30.0, 100.0):
        rc = S * math.tan(math.radians(b['alpha_deg']))
        E_pass = P.bumper_defeat_energy(S, case)
        for B in (0.01, 0.1, 1.0):
            E_mag = B * B / (2 * MU0) * 4 / 3 * math.pi * rc ** 3
            W = B * B / (2 * MU0) * math.pi * R_SHIP ** 2 * max(S, 10.0)    # field filling the stern standoff volume
            m_struct = 2 * 8000 * W / 1e9 / 1e3                          # virial minimum, steel-class 1 GPa, x2 margin (t)
            # Si+ rigidity at V and the deflection the field gives over the stand-off
            defl = B * S / rigidity_ion(28, 1)
            rows.append(dict(standoff_m=S, B_T=B, defeat_passive_J=E_pass, defeat_magnet_J=E_mag, gain=max(E_pass, E_mag) / E_pass,
                             field_energy_J=W, magnet_structure_t=m_struct, si1_deflection_rad=defl))
    # the passive alternative: how far out the screen must go for the same gain as the best magnet
    return rows


# ---------- 4. run ------------------------------------------------------------------------------------------------------------------
DESIGNS = {
    # RON B at D 800 (audited start) and the Phase 2 today optimum region (R 30, D 1500, S 800); burn totals from ron.ship
    'B_D800': dict(R=50.0, ring_w=1.0, r_plug=10.46, D=800.0, S=400.0, r_boom=2.5, I_A=12.14e6, Tb_d=82.0, ve=1.61e7),
    'B_opt_today': dict(R=30.0, ring_w=1.0, r_plug=6.3, D=1500.0, S=800.0, r_boom=2.5, I_A=7.3e6, Tb_d=78.0, ve=1.67e7),
    'E_S250': dict(R=50.0, ring_w=1.0, r_plug=10.46, D=800.0, S=250.0, r_boom=2.5, I_A=12.14e6, Tb_d=88.0, ve=1.55e7),
}


def main():
    log = []
    def say(s=''):
        print(s); log.append(s)
    out = dict(meta=dict(title='AMPN Phase 3 braking dust protection (research, not canon)', V_m_s=V, mdot_per_engine=MDOT,
                         K_DEP=K_DEP, E_VAP=E_VAP, ion_range_m=ION_RANGE, E_field_limit=E_FIELD_LIMIT), grains=[], designs={})
    # damaging grain: the bare 5 mm face perforation energy (NOMINAL)
    E_dmg = P.perforation_energy(0.005, P.K_CRATER['NOMINAL'])
    m_dmg = 2 * E_dmg / V ** 2
    say(f'damaging grain (perforates a bare 5 mm face, NOMINAL): {E_dmg:,.0f} J, {m_dmg:.2e} kg, '
        f'a {(3 * m_dmg / (4 * math.pi * RHO_G)) ** (1 / 3) * 1e6:.1f} um')
    say('\n1. One grain against exhaust and fields (column 1e-8 kg/m2 = a dense plume near the engine; field integral 0.2 T m)')
    for a in (1e-8, 1e-7, 1e-6, 1e-5, 2.8e-5, 1e-4, 1e-3):
        g = grain_effects(a, 1e-8); ch = charge_limits(a, 0.2)
        g.update(charge=ch)
        out['grains'].append(g)
        say(f'  a {a * 1e6:9.2f} um  m {g["m_kg"]:.2e} kg  KE {g["KE_J"]:.2e} J  KE/E_vap {g["KE_over_Evap"]:.1e}  vaporised {g["vaporised_share"]:.2f}  '
            f'dv/V {g["dv_over_V"]:.1e}  max q/m {ch["q_over_m_C_kg"]:.2e} C/kg  deflection {ch["deflection_rad"]:.1e} rad')
    say(f'  ions after a screen: Si+ rigidity {rigidity_ion(28, 1):.2f} T m, Si14+ {rigidity_ion(28, 14):.3f} T m; C+ {rigidity_ion(12, 1):.2f} T m')
    for name, d in DESIGNS.items():
        v = dict(d, m_damage=m_dmg, stern_standoff=30.0)
        segs, meta = M.mission(Tb_total=d['Tb_d'] * P.DAY, ve=d['ve'])
        say(f'\n== {name}: R {d["R"]} m, D {d["D"]} m, S {d["S"]} m; burns {meta["Tb_total_d"]:.0f} d total, braking {meta["brake_AU"]:.0f} AU each')
        res = dict(meta=meta, ring_field_integral_at_ship_Tm=ring_far_field_integral(d['I_A'], d['R'], d['S'] / math.sqrt(2)))
        say(f'  ring far-field integral along the ship path: {res["ring_field_integral_at_ship_Tm"]:.3f} T m')
        res['mode_b'] = mode_b(v)
        say('  Mode B (plumes widened to cover the ship):')
        for r in res['mode_b']:
            av = r['a_vaporised_max_m']
            say(f'    theta {r["theta_deg"]:4.0f}  covers from {r["x_cover_m"]:8.0f} m  column {r["column_kg_m2"]:.1e}  needed {r["column_needed_kg_m2"]:.1e} '
                f'(x{r["shortfall"]:.1e})  mdot needed {r["mdot_needed_kg_s"]:.1e} kg/s  vaporises a <= {av * 1e6 if av else 0:.3f} um  '
                f'damaging grain dv/V {r["damaging_grain"]["dv_over_V"]:.1e}  axial thrust share {r["thrust_axial_share"]:.2f}')
        res['cases'] = {}
        for case in ('NOMINAL', 'JUSTIFIED', 'HIGH'):
            rows = [protect_face(f, segs, case) for f in faces(v)]
            brow = P.brow(segs, case)
            tot = sum(r['mass_t'] for r in rows if r['mass_t'] is not None)
            res['cases'][case] = dict(faces=rows, total_t=tot, brow=dict(standoff_needed_m=brow['standoff_needed_m'],
                                      events_beyond_2m=brow['events_beyond_disruptor_2m']), hybrid=hybrid(v, segs, case))
            say(f'  {case}: passive protection {tot:,.1f} t; Brow (reference) needs stand-off {brow["standoff_needed_m"]}, '
                f'{brow["events_beyond_disruptor_2m"]:.2e} events beyond its 2 m layer')
            for r in rows:
                say(f'    {r["face"]:42s} {r["leads"]:12s} {r["area_m2"]:8.0f} m2  bare breaches {r["bare_5mm_breaches"]:.2e}  '
                    f'S needed {r["standoff_needed_m"] if r["standoff_needed_m"] is None else round(r["standoff_needed_m"], 2)}  '
                    f'{r["kind"]:8s} {r["mass_t"] if r["mass_t"] is None else round(r["mass_t"], 2)} t  armour {r["armour_t_m"]}')
        out['designs'][name] = res
    say('\nHybrid (NOMINAL, B_D800): screen + stern magnet')
    for h in out['designs']['B_D800']['cases']['NOMINAL']['hybrid']:
        say(f'  S {h["standoff_m"]:5.0f} m  B {h["B_T"]:5.2f} T  passive defeats {h["defeat_passive_J"]:.1e} J  magnet {h["defeat_magnet_J"]:.1e} J  '
            f'gain x{h["gain"]:.1f}  field {h["field_energy_J"]:.1e} J  structure {h["magnet_structure_t"]:.1f} t  Si+ deflection {h["si1_deflection_rad"]:.2f} rad')
    (HERE / 'results').mkdir(exist_ok=True)
    (HERE / 'results' / 'dust.json').write_text(json.dumps(out, indent=1, default=str))
    (HERE / 'results' / 'dust.log').write_text('\n'.join(log) + '\n')


if __name__ == '__main__':
    main()


# ---------- 5. surrogate for the optimiser ---------------------------------------------------------------------------------------------
_SEGS = {}


def dust_mass_t(R, r_plug, S, D, case='NOMINAL', ring_w=1.0, r_boom=2.5, Tb_d=82.0, ve=1.61e7):
    """Whole-ship passive dust protection (t) for an engine layout: armour on ring and plug faces both ways, strip fences on the boom
    ducts, the stern screen. Mission path of the B design (82 d of burns); the dependence on the burn length is weak."""
    key = (Tb_d, ve)
    if key not in _SEGS:
        _SEGS[key] = M.mission(Tb_total=Tb_d * P.DAY, ve=ve)[0]
    v = dict(R=R, ring_w=ring_w, r_plug=r_plug, S=S, D=D, r_boom=r_boom)
    rows = [protect_face(f, _SEGS[key], case) for f in faces(v)]
    return sum(r['mass_t'] if r['mass_t'] is not None else 1e5 for r in rows), rows
