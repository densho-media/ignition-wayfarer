"""V1 pulse and nozzle geometry used by T03, read from the committed Atlas results (results/convergence.json, generation V1) so that
nothing is retyped. Nozzle frame: origin at the burn point, +z toward the bow (ship +X), exhaust toward -z."""
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
ATLAS = HERE.parents[1]
U = 1.66053906660e-27
QE = 1.602176634e-19


def v1():
    c = json.loads((ATLAS / 'results/convergence.json').read_text())
    g = c['generations']['V1']; s = g['summary']; L = g['ledger_share']
    P = s['fusion_TW'] * 1e12; f = s['pellet_rate_Hz']
    E_pulse = P / f
    eta_n = 0.79                                            # FDP-1 optimistic nozzle_efficiency (scenario v1 [pulsed])
    stream = L['jet'] / eta_n                               # plasma energy that enters the nozzle, share of fusion
    jet_W = s['jet_TW'] * 1e12; ve = s['ve_km_s'] * 1e3
    mdot = 2 * jet_W / ve ** 2
    R_s = g['xray_standoff_m']
    f_par = 0.75 * R_s                                      # paraboloid focal length: forward loop at polar angle 60 deg sits at R_s
    loops = []
    for i, phi in enumerate((60.0, 90.0, 120.0)):
        a = math.radians(phi); d = 2 * f_par / (1 + math.cos(a))
        loops.append({'name': f'L{i+1}', 'alpha_deg': phi, 'd': d, 'R': d * math.sin(a), 'z': d * math.cos(a)})
    return {
        'generation': 'V1', 'fusion_W': P, 'rep_Hz': f, 'E_pulse_J': E_pulse, 'stream_share': stream,
        'E_plasma_J': stream * E_pulse, 'mass_per_pulse_kg': mdot / f, 'mdot_kg_s': mdot, 've_m_s': ve, 'thrust_N': s['thrust_MN'] * 1e6,
        'v_rms_m_s': math.sqrt(2 * stream * E_pulse / (mdot / f)), 'R_s_m': R_s, 'focal_m': f_par, 'loops': loops,
        'loop_radii_check_m': g['loop_radii_m'], 'shield_z_m': R_s,
        'shield_radius_m': R_s * math.tan(math.radians(g['hardware_cone_deg'])),
        'hardware_cone_deg': g['hardware_cone_deg'], 'ledger_share': L, 'fdp1_envelope_m': 0.21, 'fdp1_minor_m': 0.0713,
        'house_share': L['electric_house'], 'driver_loss_share': L['driver_loss'], 'recovery_loss_share': L['recovery_loss'],
        'eta_n_calculator': eta_n, 'recovery_efficiency': 0.95, 'nozzle_field_energy_ratio': 1.0, 'nozzle_kg_per_J': 1.07e-6,
        'solid_angle_V1': s['solid_angle'],
    }


SPECIES = {  # mass (u), charge (e); exhaust species of a D-3He pellet (the calculator's flow is D + He-3 fuel plus He-4 and p products)
    'p': (1.00728, 1), 'D': (2.01355, 1), 'He3': (3.01493, 2), 'He4': (4.00151, 2), 'e': (5.48579909e-4, -1),
}
