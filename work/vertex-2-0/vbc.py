"""Vertex 2.2: Vertex Burn Channeling requirement model (research; VBC is a named speculative principle, not canon).

  python3 work/vertex-2-0/vbc.py        writes work/vertex-2-0/vbc.json and prints the requirements

What VBC must do, and what established physics already fixes around it. Two findings shape the model:
1. A continuously fed burn that sustains itself without confinement hardware is an inertial burn; at 5.6 TW per engine the inertial
   scaling puts it far below atomic size at absurd density (computed below), so a steady self-sustaining stream is not a physical operating state.
   VBC is therefore defined as CHAIN IGNITION: a train of fuel pellets, each micro-burn compressing and igniting the next through
   wave-mediated, collisionless transfer of its charged products' energy. Confinement stays inertial (pellet rho R, established), and
   the energy that an external driver would supply comes from inside the plasma, so its conversion losses leave in the exhaust instead
   of heating hardware.
2. The same wave field moves the products' electron-bound energy to ions (Fisch-Rax channeling, established theory): the electron
   temperature and photon share follow from the 1.6B burn balance as functions of the channeled share.
Everything else (gain scaling, Doppler spread, slowing-down rates, reactivity, burn stability) is standard physics with stated brackets.
"""
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT/'src'/'wayfarer'))
import spec  # noqa: E402
import vertex_source as vs  # noqa: E402

C = 299792458.0
MEV = 1.602176634e-13
KEV = 1.602176634e-16
AMU = 1.66053906660e-27
M_P = 1.67262192e-27
MU0 = 4e-7*math.pi


def channel_requirement(s):
    """Photon share and electron temperature of the S1 (spin-polarized, optimistic) burn at 200 keV against the channeled share of the
    products' electron-bound energy (1.6B balance solver, radiative electrons)."""
    case = [x for x in vs.config(s)['cases'] if x['id'] == 'S1'][0]; rows = []
    for ch in (0.0, 0.25, 0.5, 0.66, 0.8, 0.9, 0.95):
        o = vs.opts(s, case, vs.OPT); o['channel'] = ch
        r = vs.solve(s, 200.0, o, vs.burnup())
        rows.append(dict(channel=ch, Te_keV=r['Te_keV'], photon_share=r['photon_share'], neutron_share=r['neutron_share'], exhaust_share=r['exhaust_share'],
                         ntau_m3s=r['ntau_m3s'], fusion_W_m3_at_1e21=r['fusion_W_m3']))
    return rows


def steady_inertial(P, ntau, Ti_keV=200.0, p21=None):
    """Why a steady unconfined burn is impossible: n tau with tau = r / c_s and P = p(n) 4/3 pi r^3 with p ~ n^2."""
    cs = math.sqrt(2*Ti_keV*KEV/(2.5*AMU))
    k = p21/(1e21)**2                              # W m^3 per n^2
    # n = ntau cs / r ; P = k n^2 4/3 pi r^3 = k (ntau cs)^2 4/3 pi r  ->  r = P / (k (ntau cs)^2 4/3 pi)
    r = P/(k*(ntau*cs)**2*4/3*math.pi); n = ntau*cs/r
    return dict(sound_speed_m_s=cs, radius_m=r, density_m3=n)


def chain(P_engine, f_c, gains=(30.0, 100.0, 300.0), E_B_max=3.4e9, v_pellet=1.0e4, r_pellet=1.0e-3, e_fuel=2.83e14):
    """Chain ignition at the pulse rate the nozzle field can contain (yield <= the field energy inside R/2, from the 2.3 trace design)."""
    f = P_engine/E_B_max; Y = P_engine/f; d = v_pellet/f
    rows = []
    for G in gains:
        Ed = Y/G; eps = Ed/(f_c*Y)
        omega_geo = math.pi*r_pellet**2/(4*math.pi*d*d)
        rows.append(dict(gain=G, drive_J=Ed, transfer_share_of_charged=eps, geometric_share=omega_geo, focusing_gain_needed=eps/omega_geo,
                         drive_pulse_W_at_10ns=Ed/1e-8))
    # products' arrival spread at the next pellet (Doppler broadening of the 14.7 MeV proton line, D-3He at Ti)
    out = dict(rate_Hz=f, yield_J=Y, pellet_fuel_kg=Y/e_fuel, spacing_m=d, pellet_speed_m_s=v_pellet, rows=rows)
    for Ti in (100.0, 200.0):
        sigE = math.sqrt(4*(M_P/(5.03*AMU))*Ti*1e-3*14.68)*1.0        # MeV, Brysk line width (1-sigma ~ sqrt(4 mp/(m1+m2) T E0))
        v = C*math.sqrt(1-1/(1+14.68*MEV/(M_P*C*C))**2); dv = v*sigE/(2*14.68)
        out[f'arrival_spread_ns_{int(Ti)}keV'] = d*dv/v/v*1e9
        out[f'proton_line_sigma_MeV_{int(Ti)}keV'] = sigE
    out['transit_ns'] = d/v*1e9
    return out


def stability(s, alpha_bracket=(0.3, 0.5)):
    """Chain map Y_{k+1} = G(E_k) E_k with E_k = eps f_c Y_k and G ~ E^alpha (ICF gain scaling): the fixed point multiplies a yield
    error by (1 + alpha) per pulse, so it is unstable without per-pulse feedback; the upper bound is the pellet's fuel (burnup 0.8 -> 1)."""
    lo = vs.sv(s, 'DHe3', 100.0); hi = vs.sv(s, 'DHe3', 190.0)
    slope = math.log(hi/lo)/math.log(1.9)
    return dict(error_growth_per_pulse=[1+a for a in alpha_bracket], pulses_to_double=[math.log(2)/math.log(1+a) for a in alpha_bracket],
                overyield_cap=1/0.8, dhe3_reactivity_log_slope_100_190keV=slope,
                note='Error grows 1.3-1.5x per pulse: each pulse must be corrected before the next (0.6 ms at 1.6 kHz) by hardware loops '
                     '(pellet mass, injection timing, wave phase); the AI tunes their gains and predicts drift. The pellet fuel caps an '
                     'overshoot at 1.25x; a missed correction quenches the chain within a few pulses (restart by the startup driver).')


def phase(B_burn, d, f):
    """Wave and control timescales at the burn station (ion cyclotron of D and He-3 in the burn-zone field)."""
    fD = 1.602176634e-19*B_burn/(2*math.pi*2.013553*AMU); fHe = 2*1.602176634e-19*B_burn/(2*math.pi*3.014932*AMU)
    return dict(B_burn_T=B_burn, f_ci_D_Hz=fD, f_ci_He3_Hz=fHe, pulse_period_s=1/f, hardware_loop_needed_s=0.2/f,
                ai_setpoint_s=100/f, note='Wave phase must be set per pulse within the pulse period; the AI updates set-points over about '
                                          'a hundred pulses (tens of ms) from predicted versus measured yield, plume and leakage.')


def failures():
    return [
        dict(mode='Chain break (misfire, missed transfer)', timescale='1-3 pulses (ms)', consequence='burn quenches; thrust steps to zero on one engine',
             response='other engines throttle to balance within ms; startup driver relights (1.74 GJ store = dozens of restarts)'),
        dict(mode='Overyield (gain above set-point)', timescale='per pulse', consequence='pulse up to 1.25x (fuel-capped); field overpressure, leakage spike',
             response='next pellet lighter or delayed; ring current headroom sized for 1.25x'),
        dict(mode='Phase drift of the transfer wave', timescale='tens of pulses', consequence='transfer share falls -> electrons heat -> photon share rises toward 47 %',
             response='AI re-phases from the plume and photon diagnostics; below the threshold the chain quenches safely'),
        dict(mode='Pellet trajectory error', timescale='per pellet', consequence='off-centre burn: asymmetric plume, more forward loss and leakage',
             response='in-flight correction at the burn station (electromagnetic steering), metrology tracks each pellet'),
        dict(mode='Ring quench (superconductor)', timescale='seconds', consequence='nozzle field decays: plume loses collimation, leakage rises',
             response='stop the chain within one pulse; ring energy dumped into its armour heat sink; dynamos recharge'),
        dict(mode='Tether or boom fault', timescale='seconds to minutes', consequence='burn station off its line; thrust misaligned',
             response='stop the chain; reel in; the other three engines carry a reduced, balanced burn'),
        dict(mode='Four-engine asymmetry', timescale='ms', consequence='torque on the ship from differential thrust',
             response='pulse-rate trim per engine (0.3 % differential today) and canted tethers'),
    ]


def run(design=None):
    s = spec.load(ROOT)[0]
    design = design or dict(P_engine=5.64e12, f_c=0.88, E_B_max=3.4e9, B_burn=0.022)
    ch = channel_requirement(s)
    p21 = ch[-2]['fusion_W_m3_at_1e21']
    st = steady_inertial(design['P_engine'], ch[-2]['ntau_m3s'], p21=p21)
    cn = chain(design['P_engine'], design['f_c'], E_B_max=design['E_B_max'])
    out = dict(design=design, channel=ch, steady_inertial=st, chain=cn, stability=stability(s), phase=phase(design['B_burn'], cn['spacing_m'], cn['rate_Hz']),
               failures=failures())
    return out


if __name__ == '__main__':
    out = run()
    (HERE/'vbc.json').write_text(json.dumps(out, indent=1)+'\n')
    for r in out['channel']:
        print(f"channel {r['channel']:.2f}: Te {r['Te_keV']:.0f} keV, photons {r['photon_share']:.3f}, exhaust {r['exhaust_share']:.3f}, ntau {r['ntau_m3s']:.2e}")
    print('steady inertial', out['steady_inertial'])
    print('chain', {k: v for k, v in out['chain'].items() if k != 'rows'})
    for r in out['chain']['rows']:
        print('  ', r)
    print('stability', out['stability'])
    print('phase', out['phase'])
