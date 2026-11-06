"""Wayfarer radiator district scenes for radmc (study code). Ship frame: +X bow, metres. Values from the spec where they exist."""
import math, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src', 'wayfarer'))
import spec, layout, thermal_geometry, habitat_ring
import radmc as m

S = spec.load()[0]
R = S['radiators']; Z = R['zones']; P = S['prototype']
PHASE = [math.radians(P['radiator_phase_deg']+120*k) for k in range(3)]
D = thermal_geometry.blade_of(S)
HOT_AFT, HOT_FRONT = D['aft_x_m'], D['front_x_m']
R0, R1 = R['root_radius']['value'], R['outer_radius']['value']
CASING = thermal_geometry.casing_radius(S)
T_HOT = R['temperature']['value']
RING_A = layout.origin(S, 'RING_A'); HALF = habitat_ring.sweep_half(S)
RING_R0, RING_R1 = 24.5, 30.0
TANK_X, TANK_R = 109.25, 34.5


def base(sc, hot_T=T_HOT, casing_to=None, rings=True, tanks=True):
    hot = sc.group('HOT', m.GRAY90, hot_T)
    for az in PHASE:
        m.plate(sc, az, HOT_AFT, HOT_FRONT, R0, R1, hot, hot, nx=4)
    cas = sc.group('CASING', m.RERAD)
    m.cylinder(sc, CASING, HOT_AFT, casing_to or (RING_A-HALF), cas, None)
    if rings:
        for k, xc in enumerate((RING_A, RING_A+S['habitat']['ring_plane_spacing']['value'])):
            g = sc.group(f'RING_{"AB"[k]}', m.BLACK, None)
            m.annulus(sc, xc-HALF, RING_R0, RING_R1, g, None, n=24)
            m.cylinder(sc, RING_R1, xc-HALF, xc+HALF, g, None, n=24)
            m.cylinder(sc, RING_R0, xc-HALF, xc+HALF, None, g, n=24)
    if tanks:
        g = sc.group('TANKS', m.BLACK, None)
        m.annulus(sc, TANK_X, CASING, TANK_R, g, None, n=24)
    return sc


def section_plates(sc, name, coat, T, x0, x1, r0=None, r1=None, nx=2):
    g = sc.group(name, coat, T)
    for az in PHASE:
        m.plate(sc, az, x0, x1, r0 or R0, r1 or R1, g, g, nx=nx)
    return g
