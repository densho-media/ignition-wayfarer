"""Shared setup for the Vertex feasibility gate (T00, research only, NON-CANON).

The gate reuses T03's field and thin-shell code (studies/nozzle) and T00's Revision 4 V4 adapter (studies/rev4) without changing either.
Frame (as T03): origin at the burn point, +z toward the bow (ship +X), lengths in metres.
"""
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
STUDIES = HERE.parent
sys.path.insert(0, str(STUDIES / 'nozzle'))
sys.path.insert(0, str(STUDIES / 'rev4'))

import numpy as np                       # noqa: E402

import fields as F                       # noqa: E402
import ledger as LG                      # noqa: E402
from common import C, G0, MU0, YEAR, core, solve_full, v4_overrides   # noqa: E402,F401

RESULTS = HERE / 'results'
KERNEL = HERE / 'inputs' / 't05_axis_kernel_4c1a29b.json'
T03 = LG.T03


def write(name, obj):
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / name).write_text(json.dumps(obj, indent=1, default=lambda x: float(x) if hasattr(x, '__float__') else str(x)))


def read(name):
    return json.loads((RESULTS / name).read_text())


def v4():
    """V4 solve, the T03 C_W15 coil set scaled to it (geometry x stand-off scale, currents field-limited) and the V4 plasma pulse."""
    ov = v4_overrides(); R = solve_full(ov)
    cg = LG.coils_v4(R); s, fI = cg['scale'], cg['current_factor']
    L = []
    for q in T03['designs']['C_W15']['loops']:
        I = q['current_MA'] * 1e6 * fI
        L.append({'name': q['name'], 'alpha_deg': q['polar_deg'], 'd': q['distance_m'] * s, 'R': q['radius_m'] * s, 'z': q['z_m'] * s,
                  'I': I, 'a': q['winding_minor_m'] * fI})        # field-limited winding: minor radius ~ I
    f = R['fusion']; Lw = f['ledger_W']; rate = f['pellet_rate_Hz']
    Ep = (Lw['jet'] + Lw['plume_to_space'] + Lw['plume_to_hardware']) / rate      # plasma energy entering the nozzle per pulse
    lay = R['layout']
    return {'ov': ov, 'R': R, 'scale': s, 'current_factor': fI, 'loops': L, 'E_plasma_J': Ep, 'rate_Hz': rate,
            'mass_per_pulse_kg': f['mass_flow_kg_s'] / rate, 'shield_z_m': lay['d_shield'],
            'shield_r_m': json.loads(KERNEL.read_text())['shield_r_hw_m'], 'x_burn': lay['x_burn']}


def shell_weights(th):
    w = np.sin(th) * np.gradient(th)
    return w / w.sum()                    # share of 4 pi per polar bin (axisymmetric)


def loop_general(Rl, centre, axis, I, P):
    """Cartesian field (N,3) at points P of a circular loop of radius Rl with any centre and axis (exact, elliptic integrals)."""
    ax = np.asarray(axis, float); ax = ax / np.linalg.norm(ax)
    d = P - np.asarray(centre, float)[None, :]
    a_comp = d @ ax
    rad_vec = d - a_comp[:, None] * ax[None, :]
    r = np.linalg.norm(rad_vec, axis=1)
    Br, Ba = F.loop_field(Rl, 0.0, I, r, a_comp)
    u = np.where(r[:, None] > 1e-12, rad_vec / np.maximum(r, 1e-12)[:, None], 0.0)
    return Br[:, None] * u + Ba[:, None] * ax[None, :]


def tilted(loops, names, chi_deg, about=(0.0, 1.0, 0.0)):
    """Loops as (R, centre, axis, I); those in `names` rotated rigidly about the burn point by chi about the y axis (x-z plane)."""
    c, s = math.cos(math.radians(chi_deg)), math.sin(math.radians(chi_deg))
    rot = np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])
    out = []
    for L in loops:
        cen = np.array([0.0, 0.0, L['z']]); ax = np.array([0.0, 0.0, 1.0])
        if L['name'] in names:
            cen = rot @ cen; ax = rot @ ax
        out.append({'name': L['name'], 'R': L['R'], 'centre': cen, 'axis': ax, 'I': L['I']})
    return out


def rotated(loops, angle_deg_by_name, default_deg=0.0):
    """Like tilted(), but each loop gets its own rotation about the y axis (degrees; positive tilts +z toward +x)."""
    out = []
    for L in loops:
        a = math.radians(angle_deg_by_name.get(L['name'], default_deg))
        rot = np.array([[math.cos(a), 0, math.sin(a)], [0, 1, 0], [-math.sin(a), 0, math.cos(a)]])
        out.append({'name': L['name'], 'R': L['R'], 'centre': rot @ np.array([0.0, 0.0, L['z']]), 'axis': rot @ np.array([0.0, 0.0, 1.0]),
                    'I': L['I']})
    return out


def field_general(gl, P):
    B = np.zeros_like(P)
    for L in gl:
        B += loop_general(L['R'], L['centre'], L['axis'], L['I'], P)
    return B


def loop_field_axis(Rl, zc, I, P, axis):
    """Cartesian field (N,3) at points P of a circular loop of radius Rl centred at zc on the z axis but with its own axis along
    unit vector `axis` (x or y only: used for transverse plug coils)."""
    ax = np.asarray(axis, float)
    c = np.array([0.0, 0.0, zc])
    d = P - c
    a_comp = d @ ax
    rad_vec = d - a_comp[:, None] * ax[None, :]
    r = np.linalg.norm(rad_vec, axis=1)
    Br, Ba = F.loop_field(Rl, 0.0, I, r, a_comp)
    u = np.where(r[:, None] > 1e-12, rad_vec / np.maximum(r, 1e-12)[:, None], 0.0)
    return Br[:, None] * u + Ba[:, None] * ax[None, :]
