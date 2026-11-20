"""Vertex 2.6: dust and impact model along a Vertex mission, the protected flight envelope, and the exposure of each architecture.

    python3 lab/studies/vertex-closure/vertex-2-6/protect.py            writes lab/studies/vertex-closure/vertex-2-6/protect.json and prints the tables (about 1 min)

NOTE 2026-11-17: protect.json / protect.log are the 874dca7 evidence, made with the superseded braking path (kept, not rerun). mission()
is now the corrected path; Vertex 2.7 and 2.8 use it. Rerunning this script writes corrected numbers over that evidence: do not.

Research, not canon. Standard library only. The dust environment is the Vertex T02 model (t02_environment.py, copied with attribution
from claude/project-thread-uwi5pl 3c665ec); the impact physics is T02's order-of-magnitude bracket (crater volume proportional to energy,
bumper cloud spreading over the stand-off), re-implemented here so that it can follow a Vertex burn profile instead of the canon
13 AU burns. Nothing here is validated at 4,797 km/s: dust accelerators reach about 100 km/s, Whipple ballistic limits 7-10 km/s.

What is new compared with T02:
- the mission path follows the Vertex ledger's burn time (total burn time Tb over four equal power-limited burns, constant thrust and mass
  flow), so long Vertex burns (about 117 d, 160 AU each) are integrated through the real speed profile;
- the protected flight envelope: each critical component has an angle theta_max inside which the forward shield shadows it; the shadow
  fails when attitude error plus the grain aberration angle atan(v_grain / v_ship) exceeds theta_max, which happens at the low-speed ends
  of every burn;
- the two flips at cruise speed (before each braking burn) are integrated as broadside exposure;
- protection is turned into mass: bumper stand-off and areal density for the design grain, a wall behind it, and an erosion allowance;
- three cases (LOW / NOMINAL / HIGH) bracket the environment (T02, envelopes of the literature, not probabilities) and the damage
  coefficients; no probability is claimed beyond the expected number of events in each bracket.

Magnetic fields, detection and the exhaust plume earn no credit (T02: neutral dust is not deflected; warning times are milliseconds; the
plume vaporises only grains below ~1e-15 kg).
"""
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import t02_environment as E  # noqa: E402

C = 299792458.0
AU = E.AU
VC = 0.016*C                                    # CANON cruise (LOCKED)
DV = VC
DAY = 86400.0
CASES = ('LOW', 'NOMINAL', 'HIGH')
K_CRATER = {'LOW': 1e-11, 'NOMINAL': 3e-11, 'HIGH': 1e-10}           # m3/J (T02, EXTRAPOLATION)
PERF_RATIO = 1.5                                                     # T02 ASSUMPTION
BUMPER = {'LOW': dict(g=0.5, alpha_deg=45.0, F_allow=3e4), 'NOMINAL': dict(g=0.5, alpha_deg=30.0, F_allow=1e4),
          'HIGH': dict(g=0.5, alpha_deg=15.0, F_allow=3e3)}            # T02 band: the LOW-damage case spreads widest
RHO_GRAIN = 2500.0
RHO_BUMPER = 1800.0                                                  # C/C class (LITERATURE)
T_OVER_D = {'LOW': 0.1, 'NOMINAL': 0.25, 'HIGH': 1.0}                 # bumper thickness / design-grain diameter (PROTOTYPE band)
WALL_KG_M2 = {'LOW': 2.0, 'NOMINAL': 5.0, 'HIGH': 10.0}               # wall behind the bumper that stops the cloud (PROTOTYPE band)
TARGET = 0.1                                                         # design rule: <= 0.1 expected critical events per mission (P >= 0.9)
POPS = ('IPD', 'KB', 'ISD')
# out-of-ecliptic approach (T02 NOMINAL_HILAT environment: Kuiper-belt dust x0.1, zodiacal x0.3; heading OPEN) with NOMINAL damage
for _d in (K_CRATER, BUMPER, T_OVER_D, WALL_KG_M2):
    _d['NOMINAL_HILAT'] = _d['NOMINAL']
VG = E.POP_SPEED


# ---------- impact physics ------------------------------------------------------------------------------------------------------------
def perforation_energy(t, k):
    p = t/PERF_RATIO
    return 2*math.pi*p**3/(3*k)


def bumper_defeat_energy(S, case='NOMINAL'):
    b = BUMPER[case]
    return b['F_allow']*math.pi*(S*math.tan(math.radians(b['alpha_deg'])))**2/b['g']


def design_grain(E_J):
    m = 2*E_J/VC**2
    return m, (6*m/(math.pi*RHO_GRAIN))**(1/3)


def bumper_kg_m2(S, case='NOMINAL'):
    """Bumper areal density that fully disrupts the largest grain this stand-off defeats (its design grain), plus the wall behind."""
    _, d = design_grain(bumper_defeat_energy(S, case))
    return T_OVER_D[case]*d*RHO_BUMPER, WALL_KG_M2[case]


from functools import lru_cache  # noqa: E402


@lru_cache(maxsize=None)
def _rho(pop, r, case):
    return E.mass_density(pop, r, E.CASE[case])


def N_pop(m, r, cs):
    return {'IPD': E.ipd_N(m, r, cs), 'KB': E.kb_N(m, r, cs), 'ISD': E.isd_N(m, r, cs)}


# ---------- mission path ----------------------------------------------------------------------------------------------------------------
def burn_profile(ratio, n=240):
    """Constant thrust and mass flow; mass falls from 1 to 1/ratio. Returns (dtau, v_fraction_mid) pairs for acceleration (v from 0 to 1)."""
    mu1 = 1/ratio; out = []
    vend = math.log(ratio)
    for i in range(n):
        t0, t1 = i/n, (i+1)/n
        tm = 0.5*(t0+t1); mu = 1-(1-mu1)*tm
        out.append((t1-t0, math.log(1/mu)/vend))
    return out


def mission(Tb_total, ve, dest_au=None, t_flip=300.0, n=240):
    """Segments (phase, orientation, r_AU, v, ds) of the full-return mission: accelerate out (bow first), coast, flip at cruise, brake engine
    first, accelerate home, coast, flip, brake home. Destination: the given heliocentric distance, or the nearest the burns allow.

    CORRECTED 2026-11-17 (Vertex 2.8, the same fix as lab/studies/dust-impacts model.py on claude/project-thread-6ryvmv a62118b): a
    constant-thrust braking burn covers more distance than an accelerating burn of the same duration (the ship is heaviest, so slowest
    to change speed, at the start), so each braking burn now starts one *braking*-burn length before its end point. The turn-around moves
    out to 1 + accelerate + brake distance (324.33 AU on the Vertex research path) and the home braking leg ends at 1.0 AU. The
    superseded version is kept as mission_superseded_874dca7()."""
    tb = Tb_total/4; ratio = math.exp(DV/ve); prof = burn_profile(ratio, n)
    sa = sum(dt*f for dt, f in prof)*VC*tb                    # accelerating-burn distance, m
    sd = sum(dt*(1-f) for dt, f in prof)*VC*tb                # braking-burn distance, m
    dmin = 1.0+(sa+sd)/AU
    D = max(dest_au or 0.0, dmin)
    segs = []

    def burn(phase, orient, r0, sign, decel):
        x = 0.0
        for dt, f in prof:
            v = VC*(1-f) if decel else VC*f
            ds = v*dt*tb
            segs.append(dict(phase=phase, orient=orient, r=r0+sign*(x+ds/2)/AU, v=max(v, 1.0), ds=ds, dt=dt*tb))
            x += ds

    def coast(phase, r0, r1, k=60):
        L = abs(r1-r0)*AU
        for i in range(k if L > 1 else 0):
            segs.append(dict(phase=phase, orient='BOW_FIRST', r=r0+(r1-r0)*(i+0.5)/k, v=VC, ds=L/k, dt=L/k/VC))

    def flip(phase, r):
        segs.append(dict(phase=phase, orient='BROADSIDE', r=r, v=VC, ds=VC*t_flip, dt=t_flip))

    burn('accelerate out', 'BOW_FIRST', 1.0, +1, False)
    coast('coast out', 1.0+sa/AU, D-sd/AU)
    flip('flip before braking (destination)', D-sd/AU)
    burn('brake at destination', 'ENGINE_FIRST', D-sd/AU, +1, True)
    burn('accelerate home', 'BOW_FIRST', D, -1, False)
    coast('coast home', D-sa/AU, 1.0+sd/AU)
    flip('flip before braking (home)', 1.0+sd/AU)
    burn('brake at home', 'ENGINE_FIRST', 1.0+sd/AU, -1, True)
    meta = dict(Tb_total_d=Tb_total/DAY, burn_d=tb/DAY, ve_c=ve/C, mass_ratio_per_burn=ratio, burn_AU=sa/AU, brake_AU=sd/AU,
                destination_AU=D, destination_min_AU=dmin, t_flip_s=t_flip, path_AU=sum(s['ds'] for s in segs)/AU,
                min_r_AU=min(s['r'] for s in segs))
    return segs, meta


def mission_superseded_874dca7(Tb_total, ve, dest_au=None, t_flip=300.0, n=240):
    """SUPERSEDED 2026-11-17 (kept so the 874dca7 evidence in protect.json can be reproduced; do not use). Its braking burns start one
    *accelerating*-burn length before their end point, so the home braking leg runs through the Sun (min r -10.96 AU). Use mission().

    Segments (phase, orientation, r_AU, v, ds) of the full-return mission: accelerate out (bow first), coast, flip at cruise, brake engine
    first, accelerate home, coast, flip, brake home. Destination: the given heliocentric distance, or the nearest the burns allow (the
    canon destination is OPEN; T02 assumed a 45 AU Kuiper anchorage, which these long burns cannot stop in)."""
    tb = Tb_total/4; ratio = math.exp(DV/ve); prof = burn_profile(ratio, n)
    sb = sum(dt*f for dt, f in prof)*VC*tb                    # burn distance, m
    dmin = 1.0+2*sb/AU
    D = max(dest_au or 0.0, dmin)
    segs = []

    def burn(phase, orient, r0, sign, decel):
        s = 0.0
        for dt, f in prof:
            v = VC*(1-f) if decel else VC*f
            ds = v*dt*tb
            segs.append(dict(phase=phase, orient=orient, r=r0+sign*(s+ds/2)/AU, v=max(v, 1.0), ds=ds, dt=dt*tb))
            s += ds

    def coast(phase, r0, r1, k=60):
        L = abs(r1-r0)*AU
        if L <= 0:
            return
        for i in range(k):
            segs.append(dict(phase=phase, orient='BOW_FIRST', r=r0+(r1-r0)*(i+0.5)/k, v=VC, ds=L/k, dt=L/k/VC))

    def flip(phase, r):
        segs.append(dict(phase=phase, orient='BROADSIDE', r=r, v=VC, ds=VC*t_flip, dt=t_flip))

    burn('accelerate out', 'BOW_FIRST', 1.0, +1, False)
    coast('coast out', 1.0+sb/AU, D-sb/AU)
    flip('flip before braking (destination)', D-sb/AU)
    burn('brake at destination', 'ENGINE_FIRST', D-sb/AU, +1, True)
    burn('accelerate home', 'BOW_FIRST', D, -1, False)
    coast('coast home', D-sb/AU, 1.0+sb/AU)
    flip('flip before braking (home)', 1.0+sb/AU)
    burn('brake at home', 'ENGINE_FIRST', 1.0+sb/AU, -1, True)
    meta = dict(Tb_total_d=Tb_total/DAY, burn_d=tb/DAY, ve_c=ve/C, mass_ratio_per_burn=ratio, burn_AU=sb/AU, destination_AU=D,
                destination_min_AU=dmin, t_flip_s=t_flip, path_AU=sum(s['ds'] for s in segs)/AU)
    return segs, meta


# ---------- exposure ------------------------------------------------------------------------------------------------------------------------
def exposed(item, seg, pop):
    """Is the item hit directly by this population on this segment?"""
    o = seg['orient']
    if o == 'BROADSIDE':
        return item.get('broadside', False)
    if o == item.get('leads'):
        return True
    th = item.get('theta_max_deg', {}).get(o)
    if th is None:
        return False
    ab = math.degrees(math.atan(VG[pop]/seg['v']))+item.get('attitude_deg', 0.2)
    return ab > th


def events(item, segs, E_J, case, by_phase=False):
    """Expected number of grains above the energy E_J (impact frame) striking the item over the mission."""
    cs = E.CASE[case]; tot = 0.0; ph = {}
    A = item['area_m2']
    for s in segs:
        if s['orient'] == 'BROADSIDE':
            Aeff = item.get('broadside_m2', 0.0)
        else:
            Aeff = A
        if Aeff <= 0:
            continue
        n = 0.0
        for p in POPS:
            if not exposed(item, s, p):
                continue
            m = 2*E_J/(s['v']**2+VG[p]**2)
            n += N_pop(m, s['r'], cs)[p]
        x = Aeff*n*s['ds']
        tot += x
        if by_phase and x > 0:
            ph[s['phase']] = ph.get(s['phase'], 0.0)+x
    return (tot, ph) if by_phase else tot


def energy_fluence(item, segs, case):
    """J/m2 of dust energy on the item's leading face (erosion budget)."""
    cs = E.CASE[case]; tot = 0.0
    for s in segs:
        for p in POPS:
            if exposed(item, s, p) and s['orient'] != 'BROADSIDE':
                tot += 0.5*_rho(p, round(s['r'], 1), case)*(s['v']**2+VG[p]**2)*s['ds']
    return tot


def required_standoff(item, segs, case, target=TARGET):
    """Smallest bumper stand-off (m) that keeps the expected number of grains above its defeat energy at the target; None above 1 km."""
    def n(S):
        return events(item, segs, bumper_defeat_energy(S, case), case)
    lo, hi = 0.05, 1000.0
    if n(lo) <= target:
        return lo
    if n(hi) > target:
        return None
    for _ in range(40):
        mid = math.sqrt(lo*hi)
        lo, hi = (mid, hi) if n(mid) > target else (lo, mid)
    return hi


# ---------- geometry: the protected flight envelope -------------------------------------------------------------------------------------
SHIELD_R = 45.0          # CANON WORKING 90 m Brow (14!A4)
SHIELD_X = 115.9         # rim girder aft face (MODEL.md Forward shield): the aft-most point at r 45 m, where the shadow starts
SHIP_AFT_X = -167.0      # body aft end: shield face 122.5 m less the 289.5 m body (MODEL.md Body)


def theta_max(r_out, x_aft):
    """Largest arrival angle (deg) at which the forward shield still shadows a component reaching r_out at x_aft (bow-first)."""
    L = SHIELD_X-x_aft
    return math.degrees(math.atan((SHIELD_R-r_out)/L)) if r_out < SHIELD_R else -90.0


def components(arch):
    """Critical components and their exposure rules per architecture. Areas are projected on the flight axis (bow-first or engine-first);
    broadside areas are mean projections during a 180 deg flip. Sources: MODEL.md (canon), vertex_adaptive evidence (A+), Halo 2.5."""
    canon = [
        dict(name='habitat rings (r 30 m)', r_out=30.0, x_aft=60.0, area_m2=2*math.pi*30.0*10.0, broadside=True, broadside_m2=2*60.0*10.0*2/math.pi,
             fail='bare', note='two rings, ~10 m wide rims (PROTOTYPE reading); a hull breach is critical'),
        dict(name='thermal blades (r 37 m)', r_out=37.0, x_aft=72.02-182.149, area_m2=4*30.5*0.1, broadside=True, broadside_m2=2*30.5*182.149*2/math.pi,
             fail='radiator', note='four 30.5 x 182 m blades seen edge-on in flight (0.1 m edge, PROTOTYPE); a puncture loses a cell, not the ship'),
        dict(name='body and tank farm (r 7 m)', r_out=7.0, x_aft=SHIP_AFT_X, area_m2=math.pi*7.0**2, broadside=True, broadside_m2=13.0*289.5*2/math.pi,
             fail='bare', note='13 m body; tanks and spine'),
        dict(name='forward shield, aft face', r_out=45.0, x_aft=115.9, area_m2=math.pi*45.0**2, broadside=True, broadside_m2=90.0*6.0*2/math.pi,
             fail='bare', leads_engine_first=True, note='the Brow back (truss, Crown, EYE services) leads when the ship flies engine first'),
    ]
    out = []
    for c in canon:
        c = dict(c)
        c['theta_max_deg'] = {'BOW_FIRST': 90.0 if c['name'].startswith('forward shield') else theta_max(c['r_out'], c['x_aft'])}
        if arch in ('HALO', 'APLUS', 'C_EXT', 'D_ROSETTE'):
            c['leads'] = None
            c['theta_max_deg']['ENGINE_FIRST'] = None        # covered by the stern annulus when one is fitted, else exposed (below)
        out.append(c)
    if arch == 'HALO':
        R, w, a, L = 41.6, 1.0, 208.0, 2000.0          # levers.json all_stretch: R 41.6 m, cluster ka R = 5 R; booms ~2 km
        out.append(dict(name='four halo rings (R 41.6 m at a 208 m)', r_out=a+R, x_aft=SHIP_AFT_X-L, area_m2=4*2*math.pi*R*w, leads='ENGINE_FIRST',
                        theta_max_deg={'BOW_FIRST': -90.0}, broadside=False, fail='bare', critical=True,
                        note='outside the 45 m shadow in every deployed state; exposed bow-first and engine-first while deployed'))
        out.append(dict(name='four 2 km compression booms', r_out=a, x_aft=SHIP_AFT_X-L, area_m2=4*2*2*0.6, leads='ENGINE_FIRST',
                        theta_max_deg={'BOW_FIRST': -90.0}, broadside=False, fail='bare', critical=True,
                        note='CFRP truss chords (two 0.6 m chord areas per boom, PROTOTYPE); a chord break buckles the boom'))
        return out
    # compact clusters: four engines at cluster radius 24 m, engine envelope r 11.44 m (vertex_adaptive audit), stowed aft x -164.5 m
    ext = {'APLUS': 0.0, 'C_EXT': 200.0, 'D_ROSETTE': 0.0}[arch]
    r_e = 11.4358; a = 24.0; x_aft = -164.482-ext
    out.append(dict(name=f'engine fronts (4 x r {r_e:.1f} m)', r_out=a+r_e, x_aft=x_aft, area_m2=4*math.pi*r_e**2, leads='ENGINE_FIRST',
                    theta_max_deg={'BOW_FIRST': theta_max(a+r_e, x_aft)}, broadside=True, broadside_m2=4*2*r_e*31.93*2/math.pi, fail='bumper',
                    critical=True, note='coil faces, carriage, petals; their own bumper petals at stand-off S (engine-first)'))
    out.append(dict(name='bore-visible block (4 x r 8 m)', r_out=a+8.0, x_aft=x_aft, area_m2=4*math.pi*8.0**2, leads='ENGINE_FIRST',
                    theta_max_deg={'BOW_FIRST': theta_max(a+8.0, x_aft)}, broadside=False, fail='block', critical=False,
                    note='what a grain sees through the open bore: the neutron shadow shield (>= 1 m LiH-W) behind the burn region'))
    out.append(dict(name='final optics / injector ports (4 x 0.5 m2)', r_out=a, x_aft=x_aft, area_m2=4*0.5, leads='ENGINE_FIRST',
                    theta_max_deg={'BOW_FIRST': theta_max(a, x_aft)}, broadside=False, fail='optic', critical=False,
                    note='periscoped driver optics and pellet-gun muzzle on the axis: sacrificial, replaced in service'))
    if ext:
        out.append(dict(name='telescoping spine (200 m, r 3 m)', r_out=3.0, x_aft=x_aft, area_m2=math.pi*3.0**2, leads='ENGINE_FIRST',
                        theta_max_deg={'BOW_FIRST': theta_max(3.0, x_aft)}, broadside=False, fail='bumper', critical=True,
                        note='extended only for burns; stowed before every flip'))
    return out


FAIL = {'bare': lambda k: perforation_energy(0.005, k), 'radiator': lambda k: perforation_energy(0.001, k),
        'block': lambda k: perforation_energy(1.0, k), 'optic': lambda k: 100.0}


def assess(arch, segs, stern=True, case='NOMINAL', attitude_deg=0.2):
    """Per component: failure energy, events, stand-off needed, mass of protection. With stern=True a stern annulus (r 45 m) covers every
    canon component from aft during engine-first flight, so only the engine group leads."""
    k = K_CRATER[case]; rows = []
    for c in components(arch):
        c = dict(c, attitude_deg=attitude_deg)
        if c.get('leads') is None and not stern:
            c['leads'] = 'ENGINE_FIRST'              # nothing between the dust and the aft face
        E_f = FAIL[c['fail']](k) if c['fail'] != 'bumper' else perforation_energy(0.005, k)
        n_bare, ph = events(c, segs, E_f, case, by_phase=True)
        row = dict(name=c['name'], theta_max_bow_first_deg=c['theta_max_deg'].get('BOW_FIRST'), leads=c.get('leads'), fail_class=c['fail'],
                   fail_energy_J=E_f, events_unprotected=n_bare, by_phase=ph, area_m2=c['area_m2'], note=c['note'])
        if c.get('leads') == 'ENGINE_FIRST' and c['fail'] in ('bumper', 'bare'):
            lead = dict(c, theta_max_deg={}, broadside=False)
            S = required_standoff(lead, segs, case)
            if S is not None:
                sb, sw = bumper_kg_m2(S, case)
                row.update(standoff_m=S, bumper_kg_m2=sb, wall_kg_m2=sw, design_grain_kg=design_grain(bumper_defeat_energy(S, case))[0],
                           protection_t=c['area_m2']*(sb+sw)/1e3)
            else:
                row.update(standoff_m=None)
            row['armour'] = armour_thickness(lead, segs, case)
            phi = energy_fluence(lead, segs, case)
            row.update(erosion_fluence_J_m2=phi, erosion_m=K_CRATER[case]*phi, erosion_t=c['area_m2']*K_CRATER[case]*phi*RHO_BUMPER/1e3)
        rows.append(row)
    return rows


def stern_annulus(arch, segs, case='NOMINAL'):
    """The stern annulus (aft Brow): r 45 m disc less the engine group, engine-first only, protects every canon component from aft."""
    holes = 0.0 if arch == 'CANON' else 4*math.pi*11.4358**2
    item = dict(name='stern annulus', area_m2=math.pi*45.0**2-holes, leads='ENGINE_FIRST', theta_max_deg={}, broadside=False)
    S = required_standoff(item, segs, case)
    sb, sw = bumper_kg_m2(S, case) if S else (None, None)
    phi = energy_fluence(item, segs, case)
    ero = K_CRATER[case]*phi
    return dict(area_m2=item['area_m2'], standoff_m=S, bumper_kg_m2=sb, wall_kg_m2=sw, armour=armour_thickness(item, segs, case),
                mass_t=(item['area_m2']*(sb+sw+ero*RHO_BUMPER)/1e3) if S else None, erosion_m=ero,
                events_beyond_2m=events(item, segs, bumper_defeat_energy(2.0, case), case))


def armour_thickness(item, segs, case, target=TARGET, rho=RHO_BUMPER):
    """Monolithic sacrificial armour (no stand-off): thickness whose perforation energy keeps the expected perforations at the target."""
    k = K_CRATER[case]
    def n(t):
        return events(item, segs, perforation_energy(t, k), case)
    lo, hi = 1e-4, 20.0
    if n(lo) <= target:
        return dict(t_m=lo, kg_m2=rho*lo)
    if n(hi) > target:
        return dict(t_m=None, kg_m2=None)
    for _ in range(40):
        mid = math.sqrt(lo*hi)
        lo, hi = (mid, hi) if n(mid) > target else (lo, mid)
    return dict(t_m=hi, kg_m2=rho*hi, mass_t=rho*hi*item['area_m2']/1e3)


def brow(segs, case='NOMINAL'):
    item = dict(name='Brow', area_m2=math.pi*45.0**2, leads='BOW_FIRST', theta_max_deg={}, broadside=False)
    phi = energy_fluence(item, segs, case)
    S = required_standoff(item, segs, case)
    return dict(events_beyond_disruptor_2m=events(item, segs, bumper_defeat_energy(2.0, case), case), standoff_needed_m=S,
                armour=armour_thickness(item, segs, case),
                bumper_kg_m2=bumper_kg_m2(S, case)[0] if S else None, erosion_m=K_CRATER[case]*phi, fluence_J_m2=phi)


S_AVAIL = {'stern': {'APLUS': 30.0, 'C_EXT': 150.0, 'D_ROSETTE': 30.0, 'HALO': 30.0},     # stern annulus to the hardware it covers (m)
           'brow': 2.0}                                                                  # canon disruptor stand-off (WORKING)


def lead_item(name, area):
    return dict(name=name, area_m2=area, leads='ENGINE_FIRST', theta_max_deg={}, broadside=False)


def protection_design(arch, segs, case='NOMINAL'):
    """Mass of the dust protection each architecture needs, per face: a bumper where its required stand-off fits the geometry, else
    monolithic sacrificial armour (C/C class). Faces that sit in or next to the exhaust (coil fronts, ring faces) cannot have a stand-off."""
    faces = []
    def face(name, area, s_avail, leads='ENGINE_FIRST'):
        it = dict(lead_item(name, area), leads=leads)
        S = required_standoff(it, segs, case)
        arm = armour_thickness(it, segs, case)
        phi = energy_fluence(it, segs, case); ero = K_CRATER[case]*phi*RHO_BUMPER*area/1e3
        if S is not None and S <= s_avail:
            sb, sw = bumper_kg_m2(S, case); kind = 'bumper'; m = area*(sb+sw)/1e3+ero
        else:
            kind = 'armour'; m = (arm.get('mass_t') if arm['t_m'] else float('inf'))
        faces.append(dict(face=name, area_m2=area, standoff_needed_m=S, standoff_available_m=s_avail, kind=kind, mass_t=m,
                          armour_t_m=arm['t_m'], armour_kg_m2=arm['kg_m2']))
    if arch == 'HALO':
        face('four ring faces, engine-first', 4*2*math.pi*41.6*1.0, 0.0)
        face('four ring faces, bow-first', 4*2*math.pi*41.6*1.0, 0.0, leads='BOW_FIRST')
        face('four boom chords', 4*2*2*0.6, 0.0)
        face('boom chords bow-first', 4*2*2*0.6, 0.0, leads='BOW_FIRST')
        face('stern annulus', math.pi*45.0**2, S_AVAIL['stern']['HALO'])
    else:
        n_sub = 7 if arch == 'D_ROSETTE' else 1
        face('engine fronts less the bores (coil faces, carriage, petals)', 4*math.pi*(11.4358**2-8.0**2), 0.0)
        face('stern annulus (r 45 m less the engine group)', math.pi*45.0**2-4*math.pi*11.4358**2, S_AVAIL['stern'][arch])
        if arch == 'C_EXT':
            face('telescoping spine front', math.pi*3.0**2, 0.0)
    brow_it = dict(lead_item('Brow', math.pi*45.0**2), leads='BOW_FIRST')
    S_b = required_standoff(brow_it, segs, case)
    opt = events(lead_item('optics', 4*0.5), segs, 100.0, case)
    tot = sum(f['mass_t'] for f in faces)
    return dict(faces=faces, total_t=tot, brow_standoff_needed_m=S_b,
                brow_upgrade_t=(math.pi*45.0**2*sum(bumper_kg_m2(S_b, case))/1e3 if S_b else None),
                optics_replacements=opt)


def flips(segs, case='NOMINAL'):
    """Whole-ship broadside exposure during the two flips at cruise."""
    k = K_CRATER[case]; cs = E.CASE[case]; out = {}
    side = dict(radiator_faces=2*30.5*182.149*2/math.pi, hull=(13.0*289.5+2*60*10)*2/math.pi, shield_edge=90*6*2/math.pi)
    for s in (x for x in segs if x['orient'] == 'BROADSIDE'):
        row = {}
        for name, A in side.items():
            Ef = perforation_energy(0.001, k) if name == 'radiator_faces' else perforation_energy(0.005, k)
            n = sum(N_pop(2*Ef/(s['v']**2+VG[p]**2), s['r'], cs)[p] for p in POPS)
            row[name] = dict(area_m2=A, fail_energy_J=Ef, events=A*n*s['ds'])
        out[s['phase']] = dict(r_AU=s['r'], t_flip_s=s['dt'], **row)
    return out


def flip_torque(t_flip, m_end=2.85e6, L=289.5, shield_kg=1.0e5):
    """Bang-bang 180 deg flip: peak rate, torque and tip acceleration (rigid ship, I ~ m L^2 / 12 plus the Brow at L/2)."""
    I = m_end*L*L/12+shield_kg*(L/2)**2
    alpha = 4*math.pi/t_flip**2
    return dict(t_flip_s=t_flip, I_kg_m2=I, peak_rate_deg_s=math.degrees(alpha*t_flip/2), torque_N_m=I*alpha, tip_accel_m_s2=alpha*L/2)


def run():
    out = dict(meta=dict(title='Vertex 2.6 dust, impact and protected-envelope model (research, not canon)',
                         environment='T02 copy (t02_environment.py); cases are literature envelopes, not probabilities',
                         k_crater=K_CRATER, bumper=BUMPER, t_over_d=T_OVER_D, wall_kg_m2=WALL_KG_M2, target_events=TARGET,
                         shield=dict(r=SHIELD_R, x_aft=SHIELD_X), ship_aft_x=SHIP_AFT_X), missions={}, theta=[], flip_torque=[])
    for t in (60.0, 300.0, 1800.0):
        out['flip_torque'].append(flip_torque(t))
    for arch in ('HALO', 'APLUS', 'C_EXT'):
        for c in components(arch):
            out['theta'].append(dict(arch=arch, name=c['name'], theta_max_bow_first_deg=c['theta_max_deg'].get('BOW_FIRST'),
                                     v_shadow_lost_km_s={p: (VG[p]/math.tan(math.radians(c['theta_max_deg']['BOW_FIRST']-0.2))/1e3
                                                             if c['theta_max_deg'].get('BOW_FIRST', -90) > 0.2 else None) for p in POPS}))
    # two mission paths: the Vertex research operating point (Halo 2.5 all-lever: 0.072 c, 467 d total burn) and the canon short burns
    paths = {'vertex_467d': (466.85*DAY, 0.072*C, None), 'vertex_467d_dest1000': (466.85*DAY, 0.072*C, 1000.0),
             'canon_28d': (28.55*DAY, 0.064*C, 45.0)}
    for pname, (Tb, ve, dest) in paths.items():
        segs, meta = mission(Tb, ve, dest)
        P = dict(meta=meta, cases={})
        for case in CASES:
            row = dict(brow=brow(segs, case), stern=stern_annulus('APLUS', segs, case), flips=flips(segs, case), arch={})
            for arch in ('HALO', 'APLUS', 'C_EXT'):
                row['arch'][arch] = dict(with_stern=assess(arch, segs, True, case), without_stern=assess(arch, segs, False, case) if arch != 'HALO' else None)
            P['cases'][case] = row
        # attitude sensitivity (NOMINAL)
        P['attitude'] = {f'{a:g}': [dict(name=r['name'], events_unprotected=r['events_unprotected']) for r in assess('APLUS', segs, True, 'NOMINAL', a)]
                         for a in (0.1, 0.5, 1.0, 2.0)}
        P['design'] = {case: {arch: protection_design(arch, segs, case) for arch in ('HALO', 'APLUS', 'C_EXT')} for case in CASES+('NOMINAL_HILAT',)}
        P['flip_time'] = {f'{t:g}': flips(mission(Tb, ve, dest, t_flip=t)[0], 'NOMINAL') for t in (60.0, 300.0, 1800.0)}
        out['missions'][pname] = P
    return out


def show(o):
    for pname, P in o['missions'].items():
        for case, d in P['design'].items():
            for arch, x in d.items():
                print(f"[{pname} {case} {arch}] protection {x['total_t']:.0f} t; Brow needs S {x['brow_standoff_needed_m']}; optics {x['optics_replacements']:.0f}: "
                      + '; '.join(f"{f['face'][:30]} {f['kind']} {f['mass_t']:.0f} t (S {f['standoff_needed_m'] and round(f['standoff_needed_m'])}/{f['standoff_available_m']:g})" for f in x['faces']))
        m = P['meta']
        print(f"\n== {pname}: burns {m['burn_d']:.0f} d x4, {m['burn_AU']:.1f} AU each, destination {m['destination_AU']:.0f} AU (min {m['destination_min_AU']:.0f})")
        for case in CASES:
            r = P['cases'][case]
            b = r['brow']; s = r['stern']
            print(f"  {case:8s} Brow: {b['events_beyond_disruptor_2m']:.3g} grains beyond the 2 m disruptor, needs S {b['standoff_needed_m']}, "
                  f"erosion {b['erosion_m']*1e3:.2f} mm | stern annulus S {s['standoff_m']} m, {s['bumper_kg_m2']} + {s['wall_kg_m2']} kg/m2, "
                  f"{s['mass_t']} t, erosion {s['erosion_m']*1e3:.2f} mm; armour Brow {b['armour']} stern {s['armour']}")
            for ph, f in r['flips'].items():
                print(f"           {ph}: " + ', '.join(f"{k} {v['events']:.3g}" for k, v in f.items() if isinstance(v, dict)))
            for arch, a in r['arch'].items():
                for row in a['with_stern']:
                    extra = (f" -> S {row.get('standoff_m')} m, {row.get('protection_t', 0):.1f} t; armour {row['armour']}" if 'standoff_m' in row else '')
                    print(f"           {arch:6s} {row['name'][:44]:44s} th {row['theta_max_bow_first_deg'] if row['theta_max_bow_first_deg'] is None else round(row['theta_max_bow_first_deg'], 2)} "
                          f"events>{row['fail_energy_J']:.3g} J: {row['events_unprotected']:.3g}{extra}")


if __name__ == '__main__':
    o = run()
    (HERE/'protect.json').write_text(json.dumps(o, indent=1, default=str)+'\n')
    show(o)
