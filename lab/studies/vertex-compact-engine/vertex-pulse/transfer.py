#!/usr/bin/env python3
"""Extraction at equal thrust, and what moving charged-product energy into extra reaction mass before the final acceleration would
physically require (owner brief 2026-11-25 08:55Z, item 4). WORK, not canon. No transfer mechanism is invented here: the study states
the column, timing, opacity and exhaust-speed conditions such a mechanism would have to meet, and what the existing models show.

  1. Equal thrust: the research geometry with and without 80 % early extraction (vertex-optimize combination block), each run at the
     pulse rate that gives the same thrust, with the fusion power and the heat that costs.
  2. The mission's own condition: jet power = F ve / 2, so the mission thrust at the mission exhaust speed fixes the jet share of the
     fusion power. Adding mass raises thrust per joule only by lowering ve.
  3. Upstream transfer requirements: the stopping column of 14.7 MeV protons and 3.67 MeV alphas in hydrogen (Bethe, ANALYTIC), the
     hydrogen X-ray energy-absorption column, the shell mass at the target and at the cavity radius, the time window (the burn's
     disassembly), and the exhaust speed each added mass leaves against the need.
  4. Downstream mixing: inelastic sharing keeps the impulse and turns the difference into heat (vertex-optimize h2_bounds).

    python3 lab/studies/vertex-compact-engine/vertex-pulse/transfer.py       # seconds; writes results/transfer.json
"""
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
FI = ROOT / 'lab/studies/fusion-ignition/results/fusion_ignition.json'
OPT = ROOT / 'lab/studies/fusion-ignition/imports/optimize.json'
SRC = ROOT / 'lab/studies/vertex-compact-engine/vertex-source/results/source.json'
ME_C2 = 0.51099895        # MeV
K_BETHE = 0.307075        # MeV cm2 / mol
REFIRE = 0.3              # vertex-source P['refire'], PROTOTYPE
MU_EN_H = {30: 0.0300, 60: 0.0361, 100: 0.0406, 150: 0.0441}   # cm2/g, hydrogen energy-absorption coefficient (NIST, keV)


def range_g_cm2(E_MeV, M_MeV, z, I_eV=19.2, Z_A=0.99212, E_stop=0.01):
    """CSDA range by integrating the Bethe stopping power from E to E_stop (no shell or Barkas corrections: good to ~10 % above 1 MeV/u)."""
    E = E_MeV; R = 0.0; n = 4000; dE = (E_MeV - E_stop) / n
    for _ in range(n):
        g = 1 + E / M_MeV; b2 = 1 - 1 / (g * g)
        arg = 2 * ME_C2 * b2 * g * g / (I_eV * 1e-6)
        S = K_BETHE * z * z * Z_A / b2 * (math.log(arg) - b2)            # MeV cm2/g
        R += dE / S; E -= dE
    return R


def main():
    fi = json.loads(FI.read_text()); L = fi['ledger']; need = L['need']
    o = json.loads(OPT.read_text()); cb = o['combination']
    src = json.loads(SRC.read_text()); d = src['design']
    p = L['pulse']
    # 1. equal thrust
    base = cb['best']['base']; ext = cb['best']['ext80']
    eq = []
    for lbl, r in (('Research geometry', base), ('Research + 80 % early extraction', ext)):
        x = base['thrust_N'] / r['thrust_N']
        eq.append(dict(label=lbl, thrust_N=base['thrust_N'], rate_factor=x, fusion_factor=x, heat_over=r['heat_over'] * x,
                       exhaust_m_s=r['exhaust_m_s'], ve_over_need=r['exhaust_m_s'] / need['exhaust_m_s']))
    # 2. mission condition
    F, ve, Pf = need['thrust_per_engine_N'], need['exhaust_m_s'], need['fusion_per_engine_W']
    jet_need = F * ve / 2 / Pf
    # 3. upstream transfer
    rp = range_g_cm2(14.68, 938.272, 1); ra = range_g_cm2(3.67, 3727.379, 2)
    x_col = {kev: 1.0 / mu for kev, mu in MU_EN_H.items()}            # g/cm2 for 1/e of the X-ray energy
    R0 = d['R0_um'] * 1e-6; m_fuel = d['mass_kg']
    shells = []
    E_ch = p['plasma_J']; md = p['debris_kg']; I0 = p['impulse_Ns']; eta = I0 / math.sqrt(2 * md * E_ch)
    for where, R in (('at the target surface', R0), ('at 1 cm', 0.01), ('at 0.1 m', 0.1), ('at the cavity (1 m)', 1.0)):
        for what, col in (('stops the 14.7 MeV protons', rp), ('absorbs 63 % of 100 keV X-rays', x_col[100])):
            m = 4 * math.pi * R * R * col * 10.0                       # kg (g/cm2 -> kg/m2 is x10)
            # the X-ray shell also takes (1 - 1/e) of the X-ray energy, less the share a hot shell re-radiates (vertex-source refire 0.3);
            # cold-matter opacity: an upper bound, since a shell heated to keV stops absorbing by Compton recoil
            E = E_ch + (p['xray_J'] * (1 - math.exp(-1)) * (1 - REFIRE) if 'X-ray' in what else 0.0)
            I = eta * math.sqrt(2 * (md + m) * E)                       # ideal: all energy shared before the directed expansion
            v = I / ((md + m) * p['exhaust_mass_kg'] / md)               # the struck share stays in the engine
            shells.append(dict(where=where, R_m=R, purpose=what, column_g_cm2=col, mass_kg=m, mass_over_fuel=m / m_fuel,
                               energy_J=E, impulse_ratio=I / I0, exhaust_m_s=v, ve_over_need=v / ve))
    timing = dict(disassembly_s=src['levers'][0]['duration_ps'] * 1e-12 if src.get('levers') else None,
                  proton_slowing_s=src['slowing'][3]['p']['tau_s'], note='a transfer must finish inside the burn disassembly; '
                  'after it the debris is a collisionless shell moving at thousands of km/s and only fields act on it')
    fuel_column = d['rhoR_g_cm2']
    out = dict(cls='CALCULATED', source='lab/studies/vertex-compact-engine/vertex-pulse/transfer.py', equal_thrust=eq,
               mission=dict(thrust_N=F, exhaust_m_s=ve, fusion_W=Pf, jet_share_needed=jet_need,
                            jet_share_now=p['jet_share'], exhaust_now_m_s=p['exhaust_m_s']),
               ranges=dict(proton_g_cm2=rp, alpha_g_cm2=ra, fuel_rhoR_g_cm2=fuel_column, proton_over_fuel=rp / fuel_column,
                           xray_1e_g_cm2=x_col), shells=shells, timing=timing,
               requirements=[
                   'Column: at least the proton range (%.2f g/cm2 of hydrogen) on every line of sight, inside the burn region; the fuel '
                   'itself is already %.0f x thicker, so the products are already given to the fuel (self-heating) and no outside '
                   'hydrogen sees them' % (rp, fuel_column / rp),
                   'Opacity: hydrogen absorbs X-rays only by Compton recoil; %.0f g/cm2 for 63 %% of 100 keV photons, a shell %s the fuel '
                   'mass even at the target surface' % (x_col[100], f"{next(s for s in shells if s["R_m"] == R0 and "X-ray" in s["purpose"])["mass_over_fuel"]:.2f} x"),
                   'Time: the transfer must finish within the burn disassembly (ps); afterwards the debris is collisionless',
                   'Exhaust speed: every added kilogram lowers ve; the mission needs %.0f km/s and the research engine gives %.0f km/s '
                   '(%.2f of it), so added mass moves away from the requirement' % (ve / 1e3, p['exhaust_m_s'] / 1e3, p['exhaust_m_s'] / ve),
                   'Mission condition: the jet must carry %.0f %% of the fusion power (thrust x ve / 2); the coupled pulse carries %.1f %%'
                   % (jet_need * 100, p['jet_share'] * 100)],
               downstream=o['hydrogen'])
    (HERE / 'results' / 'transfer.json').write_text(json.dumps(out, indent=1))
    print(json.dumps(eq, indent=0)); print('jet need', jet_need, 'now', p['jet_share'], 'ranges', rp, ra, fuel_column)
    for s_ in shells:
        print(f"{s_['where']:24s} {s_['purpose']:34s} {s_['mass_kg']:.3g} kg x{s_['mass_over_fuel']:.3g} fuel I x{s_['impulse_ratio']:.2f} ve/need {s_['ve_over_need']:.3f}")
    for r in out['requirements']:
        print('-', r)


if __name__ == '__main__':
    main()
