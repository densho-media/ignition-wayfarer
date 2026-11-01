"""B02 mass placement (WORKING, Claude under the owner's delegation of 2026-10-31; S&E 13_MASS_POSITIONS, 15 OWN-B02-MASS-PLACEMENT-2026-10-31).

Function: put every sourced mass at a place, so the ship has a centre of mass and inertia at departure, through the First Ignition burn and
at burnout, and check the three things those numbers decide:
- the thrust line: the drive pushes along the X axis, so any lateral centre-of-mass offset e needs a steering torque F e from the four
  magnetic nozzles (differential thrust e / nozzle_offset); the tank farm's vessels stand where the lanes leave room, not symmetrically, so
  each species is loaded across its vessels with zero lateral moment of its own and drawn in the same proportion (metered outlets), like an
  aircraft's fuel trim, and the vessels' own dry mass is placed with them;
- the counter-rotating rings: equal angular momentum within the 0.1 % tolerance (08) when people move between them, and static balance
  within a ring when a sector fills, using the ring water as ballast;
- the spoke axial load at 1.5 g with the CIRC-001 corridor mass added to the 330 t rotating allowance.

Placement: the 13_MASS_POSITIONS regions as X spans and radial models (the [exterior_hardware] inertia_items, PROTOTYPE), split per ring
where an item rotates; the 20 t refuge water at the refuge; the operating inventory above the 1.1 kt protected ship (B01, 200 t) as an
unallocated cylinder along the body; propellant in the TANK-AXIAL vessels (fuel_storage), settled aft under thrust. Standard library only.

    python3 src/wayfarer/mass_model.py      # prints the cases and writes references/p1_mass_model.json
"""
import json
import math
from pathlib import Path

import fuel_storage
import habitat_ring
import layout
import operating_point

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT/'references/p1_mass_model.json'
G0 = habitat_ring.G0


def q(s):
    return s['physics']['mass_placement']


def _part(name, m, x0, x1, model, yz=(0.0, 0.0)):
    """A mass m spread over X x0..x1 with a radial model, its own centre (x, y, z) and its own inertia about that centre
    (Ixx roll, Iyy, Izz). Models: ('cyl', r) solid cylinder, ('ring', r) thin hoop, ('disc', r), ('blade', r0, r1) three radial strips at
    120 deg (axisymmetric on average), ('point',) lumped."""
    L = x1-x0; kind = model[0]
    if kind == 'ring':
        rx = m*model[1]**2; rt = rx/2
    elif kind == 'blade':
        rx = m*(model[1]**2+model[1]*model[2]+model[2]**2)/3; rt = rx/2
    elif kind in ('cyl', 'disc'):
        rx = m*model[1]**2/2; rt = rx/2
    else:
        rx = rt = 0.0
    ax = m*L**2/12
    return dict(name=name, m=m, c=((x0+x1)/2, yz[0], yz[1]), I=(rx, rt+ax, rt+ax), x=(x0, x1))


def dry_parts(s):
    """The 1.1 kt protected ship plus the operating inventory: each budget item over its PROTOTYPE span; rotating shares on the ring planes."""
    p = q(s); items = {i['id']: i for i in s['physics']['mass_budget']['items']}
    spans = {i['id']: i for i in s['exterior_hardware']['inertia_items']}
    xa, xb = habitat_ring.centers(s); r_com = habitat_ring.com(s); out = []
    for iid, it in items.items():
        rot = it.get('rotating_allowance_kg', 0.0); refuge = it.get('refuge_allowance_kg', 0.0); fixed = it['mass_kg']-rot-refuge
        sp = spans[iid]
        if fixed > 0:
            model = sp['model'] if not rot else ['cyl', 5.5]
            out.append(_part(iid, fixed, sp['x'][0], sp['x'][1], model))
        if rot:
            r = sp['model'][1] if sp['model'][0] == 'ring' else r_com
            for tag, xc in (('A', xa), ('B', xb)):
                out.append(_part(f'{iid}@ring_{tag}', rot/2, xc-1.0, xc+1.0, ['ring', r]))
        if refuge:
            x0 = layout.at(s, s['prototype']['refuge_x0']) if 'refuge_x0' in s['prototype'] else xa+9.1
            x1 = layout.at(s, s['prototype']['refuge_x1']) if 'refuge_x1' in s['prototype'] else xa+11.9
            out.append(_part(f'{iid}@refuge', refuge, x0, x1, ['ring', p['refuge_r_m']]))
    if p['include_circulation']:
        import ring_circulation
        m = ring_circulation.budget(s)['mass_kg']['total']
        for tag, xc in (('A', xa), ('B', xb)):
            out.append(_part(f'circ001@ring_{tag}', m/2, xc-1.0, xc+1.0, ['ring', r_com]))
    out += tankage_parts(s)
    op = s['physics']['operating_point']; extra = op['protected_and_operational_kg']-sum(i['mass_kg'] for i in items.values())
    if extra > 0:
        out.append(_part('operating_inventory', extra, p['operating_inventory_x'][0], p['operating_inventory_x'][1], ['cyl', p['operating_inventory_r_m']]))
    return out


def tankage_parts(s):
    """The added tankage of the full return (operating_point.mission added_tank_kg: shell, insulation and supports at tank_dry_fraction of
    the capacity beyond today's inventory) on the tank farm: each vessel's share in proportion to its shell area, at its own axis, so an
    uneven vessel layout shows in the dry ship's centre of mass."""
    add = operating_point.mission(s)['added_tank_kg']
    if add <= 0:
        return []
    ts = fuel_storage.tanks(s); A = {t['name']: shell_area(t) for t in ts}; tot = sum(A.values())
    return [_part(f"tankage_{t['id']}", add*A[t['name']]/tot, t['x0'], t['x1'], ['cyl', t['a']], (t['y'], t['z'])) for t in ts]


def shell_area(t):
    """Pressure shell area of a vessel (barrel plus two 2:1 ellipsoidal heads, 1.38 pi a^2 each)."""
    a = t['a']; return 2*math.pi*a*(t['y_ring'][1]-t['y_ring'][0])+2*1.38*math.pi*a*a


def tank_capacity(s):
    """Liquid capacity (kg) of each vessel at its species' density."""
    rho = fuel_storage.cfg(s)['density_kg_m3']
    return [dict(t, cap_kg=t['liquid_m3']*rho[fuel_storage.INV_KEY[t['species']]]) for t in fuel_storage.tanks(s)]


def _solve(M, b):
    n = len(b); A = [row[:]+[b[i]] for i, row in enumerate(M)]
    for c in range(n):
        piv = max(range(c, n), key=lambda r: abs(A[r][c]))
        if abs(A[piv][c]) < 1e-12:
            return None
        A[c], A[piv] = A[piv], A[c]
        for r in range(n):
            if r != c:
                f = A[r][c]/A[c][c]
                for k in range(c, n+1):
                    A[r][k] -= f*A[c][k]
    return [A[i][n]/A[i][i] for i in range(n)]


def balance(s, species, kg):
    """One species' load per vessel with no lateral moment of its own: as close to an equal fill as the moment and total allow (weighted
    least squares, active set on 0 <= load <= capacity x fill_max), so the load stays balanced at any fill when drawn in the same proportion.
    Returns (rows per vessel, residual moment kg m)."""
    cs = [c for c in tank_capacity(s) if c['species'] == species]; n = len(cs); umax = [c['cap_kg']*fuel_storage.fill_max(s) for c in cs]
    caps = [c['cap_kg'] for c in cs]; pts = [(c['y'], c['z']) for c in cs]; t = [kg*c/sum(caps) for c in caps]; fixed = {}; ms = None
    for _ in range(3*n):
        free = [i for i in range(n) if i not in fixed]
        rows = [[1.0]*len(free), [pts[i][0] for i in free], [pts[i][1] for i in free]]
        b = [kg-sum(fixed.values()), -sum(v*pts[i][0] for i, v in fixed.items()), -sum(v*pts[i][1] for i, v in fixed.items())]
        if len(free) < 3:
            rows, b = rows[:len(free)], b[:len(free)]
        w = [caps[i] for i in free]; tt = [t[i] for i in free]
        M = [[sum(r1[k]*w[k]*r2[k] for k in range(len(free))) for r2 in rows] for r1 in rows]
        lam = _solve(M, [bb-sum(r[k]*tt[k] for k in range(len(free))) for r, bb in zip(rows, b)])
        if lam is None:
            break
        m = {i: tt[k]+w[k]*sum(lam[j]*rows[j][k] for j in range(len(rows))) for k, i in enumerate(free)}
        bad = [(max(-m[i], m[i]-umax[i]), i) for i in free if m[i] < -1e-6 or m[i] > umax[i]+1e-6]
        if not bad:
            ms = [fixed.get(i, m.get(i)) for i in range(n)]; break
        _, i = max(bad); fixed[i] = 0.0 if m[i] < 0 else umax[i]
    if ms is None:
        ms = [min(u, kg*c/sum(caps)) for c, u in zip(caps, umax)]
    res = math.hypot(sum(m*p[0] for m, p in zip(ms, pts)), sum(m*p[1] for m, p in zip(ms, pts)))
    return [dict(name=c['name'], kg=m, cap_kg=c['cap_kg'], fill=m/c['cap_kg']) for c, m in zip(cs, ms)], res


def propellant_parts(s, he3_kg, d2_kg, h2_kg, balanced=True):
    """Propellant as slugs settled aft in each vessel under thrust (the liquid spans the aft fill fraction of the shell length), balanced per
    species or (balanced=False) filled in proportion to each vessel's capacity."""
    byname = {c['name']: c for c in tank_capacity(s)}; out = []
    for sp, kg in (('helium-3', he3_kg), ('deuterium', d2_kg), ('hydrogen', h2_kg)):
        if kg <= 0:
            continue
        if balanced:
            rows, _ = balance(s, sp, kg)
        else:
            cs = [c for c in byname.values() if c['species'] == sp]; tot = sum(c['cap_kg'] for c in cs)
            rows = [dict(name=c['name'], kg=kg*c['cap_kg']/tot) for c in cs]
        for r in rows:
            if r['kg'] > 0:
                c = byname[r['name']]; x0, x1 = c['x_shell']; f = r['kg']/c['cap_kg']
                out.append(_part(c['name'], r['kg'], x0, x0+f*(x1-x0), ['cyl', c['a']], (c['y'], c['z'])))
    return out


def totals(parts):
    """Mass, centre (x, y, z) and the inertia tensor's diagonal about the centre (Ixx roll, Iyy, Izz), parallel-axis included."""
    M = sum(p['m'] for p in parts); c = [sum(p['m']*p['c'][k] for p in parts)/M for k in range(3)]
    Ixx = Iyy = Izz = Ixy = Ixz = 0.0
    for p in parts:
        dx, dy, dz = (p['c'][k]-c[k] for k in range(3)); m = p['m']
        Ixx += p['I'][0]+m*(dy*dy+dz*dz); Iyy += p['I'][1]+m*(dx*dx+dz*dz); Izz += p['I'][2]+m*(dx*dx+dy*dy)
        Ixy -= m*dx*dy; Ixz -= m*dx*dz
    return dict(mass_kg=M, cg_m=c, lateral_m=math.hypot(c[1], c[2]), I_roll=Ixx, I_pitch=Iyy, I_yaw=Izz, I_xy=Ixy, I_xz=Ixz)


def stores_at(s, left):
    """Propellant aboard with `left` (0..1) of the mission's propellant still aboard: every species drains in proportion."""
    inv = fuel_storage.inventory(s)
    return dict(he3=inv['helium_3']*left, d2=inv['deuterium']*left, h2=inv['hydrogen']*left)


def burn_states(s, steps=10, balanced=True):
    """Departure to burnout along the First Ignition burn (power-limited, operating_point): every store drained in proportion to the
    mission's propellant used. Each state: mass, CG, lateral offset, inertia, thrust and the steering the offset needs."""
    b = operating_point.burn(s); m_ = operating_point.mission(s); dry = dry_parts(s)
    T = b['duration_s']; m0 = b['departure_mass_kg']; mf = b['burnout_mass_kg']; F = b['peak_thrust_N']
    r_noz = s['prototype']['nozzle_offset_m']; out = []; P = m_['propellant_kg']; dep_dry = None
    for i in range(steps+1):
        t = T*i/steps; m = m0-(m0-mf)*i/steps; left = 1-(m0-m)/P
        st = stores_at(s, left)
        tot = totals(dry+propellant_parts(s, st['he3'], st['d2'], st['h2'], balanced))
        tot.update(t_s=t, thrust_N=F, steer_torque_N_m=F*tot['lateral_m'], differential_thrust=tot['lateral_m']/r_noz,
                   propellant_kg=st['he3']+st['d2']+st['h2'], mission_left=left)
        out.append(tot)
    return out


def ring_balance(s):
    """Counter-rotating rings: momentum residual when people move between rings, the rpm trim that restores it, and the in-ring static
    imbalance of a full sector against the ring-water ballast."""
    p = q(s); d = habitat_ring.dynamics(s); w = d['omega_rad_s']; r = habitat_ring.com(s); I = d['inertia_each_kg_m2']
    if p['include_circulation']:
        import ring_circulation
        I += ring_circulation.budget(s)['mass_kg']['total']/2*r**2
    tol = s['physics']['rotor_operations']['momentum_balance_tolerance']; person = p['person_kg']; rows = []
    r_out, r_in = p['ballast_r_m']
    for n in p['crew_shift_cases']:
        dI = n*person*habitat_ring.floor(s)**2
        resid = 2*dI/I                                     # same rpm: ring A loses dI, ring B gains it; net H = 2 dI w against I w
        rows.append(dict(people=n, residual_H_N_m_s=2*dI*w, residual_fraction=resid, within_tolerance=resid <= tol,
                         rpm_trim=60/(2*math.pi)*w*dI/I,     # each ring retrimmed by dI/I to equal momentum
                         water_trim_kg=dI/(r_out**2-r_in**2)))   # or: the receiving ring moves this much water from floor to overhead
    n_sector = p['full_sector_people']; e = n_sector*person*habitat_ring.floor(s)
    ballast = e/habitat_ring.floor(s)                       # water moved to the two other sectors' floor to cancel it
    M = operating_point.burn(s)['burnout_mass_kg']
    return dict(momentum_tolerance=tol, ring_inertia_kg_m2=I, crew_shift=rows,
                full_sector=dict(people=n_sector, imbalance_kg_m=e, whirl_force_N=e*w*w, ship_orbit_mm=e/M*1e3,
                                 ballast_water_kg=ballast, ring_water_kg=habitat_ring.water_item(s)['rotating_allowance_kg']/2))


def spokes(s):
    p = q(s); d = habitat_ring.dynamics(s); n = s['habitat_ring']['spokes_per_ring']; a = s['mission']['first_ignition']['max_accel']*G0
    base = d['mass_each_kg']; out = dict(spokes_per_ring=n, ring_mass_kg=base, axial_per_spoke_N=base*a/n)
    if p['include_circulation']:
        import ring_circulation
        m = base+ring_circulation.budget(s)['mass_kg']['total']/2
        out.update(ring_mass_with_circ_kg=m, axial_per_spoke_with_circ_N=m*a/n, increase=m/base-1)
    return out


def report(s):
    trimmed = burn_states(s); untrimmed = burn_states(s, balanced=False); inv = fuel_storage.inventory(s)
    lim = q(s)['max_differential_thrust']
    worst = max(trimmed, key=lambda r: r['differential_thrust']); worst_u = max(untrimmed, key=lambda r: r['differential_thrust'])
    loads = {sp: dict(zip(('cells', 'residual_kg_m'), balance(s, sp, inv[k]))) for sp, k in fuel_storage.INV_KEY.items()}
    dry = totals(dry_parts(s))
    fails = []
    if worst['differential_thrust'] > lim:
        fails.append(f"balanced burn needs {worst['differential_thrust']:.3f} differential thrust (limit {lim})")
    if dry['lateral_m']/s['prototype']['nozzle_offset_m'] > lim:
        fails.append(f"dry ship lateral CG {dry['lateral_m']:.3f} m needs more than {lim} differential thrust")
    for sp, r in loads.items():
        if r['residual_kg_m'] > 1.0:
            fails.append(f'{sp} cannot be loaded with zero lateral moment ({r["residual_kg_m"]:.0f} kg m)')
    rb = ring_balance(s)
    return dict(status=q(s)['canon_status'], departure=trimmed[0], burnout=trimmed[-1], dry_ship=dry,
                cg_travel_m=trimmed[0]['cg_m'][0]-trimmed[-1]['cg_m'][0],
                trimmed_worst=dict(t_s=worst['t_s'], lateral_m=worst['lateral_m'], differential_thrust=worst['differential_thrust']),
                untrimmed_worst=dict(t_s=worst_u['t_s'], lateral_m=worst_u['lateral_m'], differential_thrust=worst_u['differential_thrust'],
                                     steer_torque_N_m=worst_u['steer_torque_N_m']),
                loads=loads, ring_balance=rb, spokes=spokes(s), burn=trimmed, failures=fails)


def check(s):
    return report(s)['failures']


if __name__ == '__main__':
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from spec import load
    r = report(load(ROOT)[0])
    OUTPUT.write_text(json.dumps(r, indent=1, default=float)+'\n')
    for k in ('departure', 'burnout'):
        d = r[k]
        print(f"{k}: {d['mass_kg']/1e3:.0f} t, CG x {d['cg_m'][0]:.2f} m, lateral {d['lateral_m']*1e3:.0f} mm, I roll {d['I_roll']:.3e}, "
              f"pitch {d['I_pitch']:.3e}, yaw {d['I_yaw']:.3e}")
    print('CG travel', round(r['cg_travel_m'], 2), 'm; trimmed worst', r['trimmed_worst'], '; untrimmed worst', r['untrimmed_worst'])
    print('dry ship', round(r['dry_ship']['mass_kg']/1e3), 't, lateral', round(r['dry_ship']['lateral_m']*1e3), 'mm')
    for sp, l in r['loads'].items():
        print(sp, [(c['name'], round(c['kg']/1e3, 1), round(c['fill'], 3)) for c in l['cells']], round(l['residual_kg_m']))
    print('rings', json.dumps(r['ring_balance'], default=float)[:600]); print('spokes', r['spokes']); print('failures', r['failures'])
