"""Concept scenes (study). Each builder returns (scene, dict of section -> load W, list of adiabatic sheet groups)."""
import math
import ship, radmc as m

HF = ship.HOT_FRONT; E0 = ship.R0+3.0   # emitting sheet starts outside the 3 m root band


def wedge(sc, x, name, coat, r0=ship.CASING+0.1, r1=ship.R1, frac0=0.0):
    """Triangular wedge reflectors at station x: between each pair of neighbouring blade planes, from r0 on both planes out to
    the chord joining the blade tips (the cross-section of the convex hull). frac0 > 0 keeps only the outer part (from the
    fraction frac0 of the way from root to tip)."""
    g = sc.group(name, coat, None)
    for k in range(3):
        a, b = ship.PHASE[k], ship.PHASE[(k+1) % 3]
        ra = r0+(r1-r0)*frac0
        p = [m.radial(a, x, ra), m.radial(a, x, r1), m.radial(b, x, r1), m.radial(b, x, ra)]
        sc.add_quad(*p, g, g)
        if frac0 == 0.0:      # close the small triangle between the two inner points and the casing
            pass
    return g


def annulus_baffle(sc, x, name, coat):
    g = sc.group(name, coat, None)
    m.annulus(sc, x, ship.CASING+0.1, ship.R1, g, g, n=36)
    return g


def build(cfg):
    """cfg keys: coat (WARM/LOW coating), lw, ll (section lengths), gap (HOT->WARM), gap2 (WARM->LOW), blocker
    ('none'|'annulus2'|'annulus2x2'|'wedge1'|'wedge2'|'wedge2_outer'), hot_T, rings/tanks flags."""
    sc = m.Scene(); ship.base(sc, hot_T=cfg.get('hot_T', ship.T_HOT))
    gap, gap2, lw, ll = cfg['gap'], cfg['gap2'], cfg['lw'], cfg['ll']
    xw0 = HF+gap; xw1 = xw0+lw; xl0 = xw1+gap2; xl1 = xl0+ll
    coat_w = cfg.get('coat_w', cfg['coat']); coat_l = cfg.get('coat_l', cfg['coat'])
    ship.section_plates(sc, 'WARM', coat_w, cfg.get('T_w', 440.0), xw0, xw1, r0=E0, nx=3)
    ship.section_plates(sc, 'LOW', coat_l, cfg.get('T_l', 300.0), xl0, xl1, r0=E0, nx=3)
    rb = sc.group('ROOTBAND', m.RERAD)      # zone root bands: structure/transition, adiabatic
    for az in ship.PHASE:
        m.plate(sc, az, xw0, xl1, ship.R0, E0, rb, rb)
    sheets = []; b = cfg['blocker']; lay = cfg.get('layer_gap', 0.30); coat_b = cfg.get('coat_b', m.POLISHED_BAFFLE)
    xb1 = HF+gap/2; xb2 = xw1+gap2/2
    if b.startswith('annulus'):
        stations = [xb1, xb2] if b == 'annulus2x2' else [xb1]
        for i, xs in enumerate(stations):
            for k in range(2):
                sheets.append(annulus_baffle(sc, xs+(k-0.5)*lay, f'BAF{i}_{k}', coat_b))
    elif b.startswith('wedge'):
        nl = 2 if b.startswith('wedge2') else 1; f0 = cfg.get('frac0', 0.0)
        for k in range(nl):
            sheets.append(wedge(sc, xb1+(k-(nl-1)/2)*lay, f'WEDGE_{k}', coat_b, frac0=f0))
        if cfg.get('wedge_low'):
            sheets.append(wedge(sc, xb2, 'WEDGE_L', coat_b))
    loads = dict(WARM=cfg.get('load_w', 5.0e6), LOW=cfg.get('load_l', 1.0e6))
    span = dict(WARM=(xw0, xw1), LOW=(xl0, xl1), total_front=xl1)
    return sc.compile(), loads, sheets, span


def cone_layer(sc, x_in, slope_deg, name, coat, r0=ship.CASING+0.1, r1=ship.R1, n=36, nr=3):
    """Conical reflector sheet: x(r) = x_in + (r - r0) tan(slope). slope 0 is a flat annulus; a positive slope leans forward
    with radius, so neighbouring layers open into a V-groove that vents the space between them to deep space at the rim."""
    g = sc.group(name, coat, None); t = math.tan(math.radians(slope_deg))
    X = lambda r: x_in+(r-r0)*t
    for k in range(n):
        a = 2*math.pi*k/n; b = 2*math.pi*(k+1)/n
        for j in range(nr):
            ra = r0+(r1-r0)*j/nr; rb = r0+(r1-r0)*(j+1)/nr
            p = [m.radial(a, X(ra), ra), m.radial(a, X(rb), rb), m.radial(b, X(rb), rb), m.radial(b, X(ra), ra)]
            sc.add_quad(*p, g, g)
    return g


def build_v(cfg):
    global E0
    E0 = ship.R0+cfg.get('root_strip', 3.0)
    """Graded blade with a V-groove thermal bulkhead: layers (x offset from the hot front, slope deg) at the HOT/WARM break;
    the WARM section's aft edge clears the last layer at the rim (its start X is the last layer's rim X plus a clearance)."""
    sc = m.Scene(); ship.base(sc, hot_T=cfg.get('hot_T', ship.T_HOT))
    layers = cfg['layers']; coat_b = cfg.get('coat_b', m.POLISHED_BAFFLE); sheets = []
    for i, (dx, sl) in enumerate(layers):
        sheets.append(cone_layer(sc, HF+dx, sl, f'VG_{i}', cfg.get('coats_b', [coat_b]*len(layers))[i]))
    last_dx, last_sl = layers[-1]
    rim = HF+last_dx+(ship.R1-ship.CASING-0.1)*math.tan(math.radians(last_sl))
    clear = cfg.get('clear', 0.5)
    lw, ll, gap2 = cfg['lw'], cfg['ll'], cfg['gap2']
    if cfg.get('diagonal', True) and last_sl > 0:
        # WARM aft edge follows the last layer: model as two plates, a trapezoid split (inner strip from the root, outer full)
        xw0_in = HF+last_dx+(E0-ship.CASING-0.1)*math.tan(math.radians(last_sl))+clear
    else:
        xw0_in = rim+clear
    xw0 = rim+clear if not cfg.get('diagonal', True) else xw0_in
    xw1 = xw0_in+lw; xl0 = xw1+gap2; xl1 = xl0+ll
    coat_w = cfg.get('coat_w', cfg['coat']); coat_l = cfg.get('coat_l', cfg['coat'])
    gW = sc.group('WARM', coat_w, cfg.get('T_w', 440.0))
    t = math.tan(math.radians(last_sl)) if cfg.get('diagonal', True) else 0.0
    for az in ship.PHASE:
        # trapezoidal WARM plate: aft edge x = HF+last_dx+(r-r0)t+clear, front edge xw1 (straight)
        ra, rb = E0, ship.R1
        xa = lambda r: HF+last_dx+(r-ship.CASING-0.1)*t+clear if t else xw0
        nseg = 4
        for j in range(nseg):
            r_a = ra+(rb-ra)*j/nseg; r_b = ra+(rb-ra)*(j+1)/nseg
            p = [m.radial(az, xa(r_a), r_a), m.radial(az, xw1, r_a), m.radial(az, xw1, r_b), m.radial(az, xa(r_b), r_b)]
            sc.add_quad(*p, gW, gW)
    ship.section_plates(sc, 'LOW', coat_l, cfg.get('T_l', 300.0), xl0, xl1, r0=E0, nx=3)
    rb_ = sc.group('ROOTBAND', m.RERAD)
    for az in ship.PHASE:
        m.plate(sc, az, xw0_in, xl1, ship.R0, E0, rb_, rb_)
    loads = dict(WARM=cfg.get('load_w', 5.0e6), LOW=cfg.get('load_l', 1.0e6))
    span = dict(WARM=(xw0_in, xw1), WARM_rim_start=xa(ship.R1) if t else xw0, LOW=(xl0, xl1), total_front=xl1)
    return sc.compile(), loads, sheets, span


def build_gill(cfg):
    """Concept A: directional gills. The WARM and LOW sections become rows of fins in each blade plane, each fin turned about its
    radial axis by beta so its emissive face looks forward and away from the hot blades; the aft face is polished (eps 0.06) and
    cooled by the same circuit. No blocker."""
    sc = m.Scene(); ship.base(sc, hot_T=cfg.get('hot_T', ship.T_HOT))
    beta = math.radians(cfg['beta']); c = cfg['chord']; pitch = cfg['pitch']
    gF = {k: sc.group(k, cfg['coat'], T) for k, T in (('WARM', 440.0), ('LOW', 300.0))}
    gB = {k: sc.group(k+'_BACK', m.POLISHED, T) for k, T in (('WARM', 440.0), ('LOW', 300.0))}
    x = HF+cfg['gap']; spans = {}
    for sec, L in (('WARM', cfg['lw']), ('LOW', cfg['ll'])):
        x0 = x; n = int(L/pitch)
        for az in ship.PHASE:
            u = (0.0, math.cos(az), math.sin(az)); t = (0.0, -math.sin(az), math.cos(az))
            for i in range(n):
                xc = x0+pitch*(i+0.5)
                # fin chord direction in the X / tangential plane, normal n = (sin b, cos b) (X, tangential): front face looks forward-out
                dx, dt = math.cos(beta)*c/2, -math.sin(beta)*c/2     # chord vector half
                def P(sg, r):
                    return (xc+sg*dx, r*u[1]+sg*dt*t[1], r*u[2]+sg*dt*t[2])
                p = [P(-1, E0), P(1, E0), P(1, ship.R1), P(-1, ship.R1)]
                sc.add_quad(*p, gF[sec], gB[sec])
        spans[sec] = (x0, x0+n*pitch); x = x0+n*pitch+cfg['gap2']
    loads = dict(WARM=5.0e6, LOW=1.0e6)
    return sc.compile(), loads, [], spans
