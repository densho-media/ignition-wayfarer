"""B02 mass placement (WORKING, Claude under the owner's delegation of 2026-10-31; S&E 13_MASS_POSITIONS, 15 OWN-B02-MASS-PLACEMENT-2026-10-31).

Function: put every sourced mass at a place, so the ship has a centre of mass and inertia at departure, through the First Ignition burn and
at burnout, and check the three things those numbers decide:
- the thrust line: the drive pushes along the X axis, so any lateral centre-of-mass offset e needs a steering torque F e from the four
  magnetic nozzles (differential thrust e / nozzle_offset); the torus propellant (deuterium in one cell, three uneven hydrogen vessels) is
  the one large asymmetric mass, so its fill is trimmed between the hydrogen vessels like an aircraft's fuel trim;
- the counter-rotating rings: equal angular momentum within the 0.1 % tolerance (08) when people move between them, and static balance
  within a ring when a sector fills, using the ring water as ballast;
- the spoke axial load at 1.5 g with the CIRC-001 corridor mass added to the 330 t rotating allowance.

Placement: the 13_MASS_POSITIONS regions as X spans and radial models (the [exterior_hardware] inertia_items, PROTOTYPE), split per ring
where an item rotates; the 20 t refuge water at the refuge; the operating inventory above the 1.1 kt protected ship (B01, 200 t) as an
unallocated cylinder along the body; propellant in its FUEL-SPLIT stores (fuel_storage). Standard library only.

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
    return dict(name=name, m=m, c=((x0+x1)/2, yz[0], yz[1]), I=(rx, rt+ax, rt+ax))


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
    op = s['physics']['operating_point']; extra = op['protected_and_operational_kg']-sum(i['mass_kg'] for i in items.values())
    if extra > 0:
        out.append(_part('operating_inventory', extra, p['operating_inventory_x'][0], p['operating_inventory_x'][1], ['cyl', p['operating_inventory_r_m']]))
    return out


def _arc_centroid(a0, a1, R):
    """Centroid (y, z) of a thin arc a0..a1 at radius R."""
    da = a1-a0; k = R*2*math.sin(da/2)/da; mid = (a0+a1)/2
    return k*math.cos(mid), k*math.sin(mid)


def torus_capacity(s):
    """Liquid capacity (kg) of each torus cell at the species density."""
    rho = fuel_storage.cfg(s)['density_kg_m3']; tor = fuel_storage.torus(s)
    return [dict(c, cap_kg=c['liquid_m3']*rho[c['species']]) for c in tor['cells']], tor


def _det3(m):
    return (m[0][0]*(m[1][1]*m[2][2]-m[1][2]*m[2][1])-m[0][1]*(m[1][0]*m[2][2]-m[1][2]*m[2][0])
            + m[0][2]*(m[1][0]*m[2][1]-m[1][1]*m[2][0]))


def balance(s, species, kg):
    """One species' load per torus cell with no lateral moment of its own (the three cells' total and two moment equations), so the load
    stays balanced at any fill when drawn in the same proportion. Falls back to the least-moment split within the ullage limit.
    Returns (rows per cell, residual moment kg m)."""
    cells, tor = torus_capacity(s); R = tor['R']; cs = [c for c in cells if c['species'] == species]
    pts = [_arc_centroid(c['a0'], c['a1'], R) for c in cs]; fill_max = 1/(1+fuel_storage.cfg(s)['ullage'])
    hi = [c['cap_kg']*fill_max for c in cs]; ms = None
    if len(cs) == 3 and kg > 0:
        A = [[1, 1, 1], [p[0] for p in pts], [p[1] for p in pts]]; D = _det3(A)
        if abs(D) > 1e-9:
            x = []
            for k in range(3):
                mk = [row[:] for row in A]
                for r, b in enumerate((kg, 0.0, 0.0)):
                    mk[r][k] = b
                x.append(_det3(mk)/D)
            if all(0 <= xi <= h for xi, h in zip(x, hi)):
                ms = x
    if ms is None and len(cs) == 3 and kg > 0:
        err = None; N = 240
        for i in range(N+1):
            for j in range(N+1):
                m0, m1 = hi[0]*i/N, hi[1]*j/N; m2 = kg-m0-m1
                if not 0 <= m2 <= hi[2]:
                    continue
                e = math.hypot(sum(m*p[0] for m, p in zip((m0, m1, m2), pts)), sum(m*p[1] for m, p in zip((m0, m1, m2), pts)))
                if err is None or e < err:
                    ms, err = [m0, m1, m2], e
    if ms is None:
        tot = sum(c['cap_kg'] for c in cs); ms = [kg*c['cap_kg']/tot for c in cs]
    res = math.hypot(sum(m*p[0] for m, p in zip(ms, pts)), sum(m*p[1] for m, p in zip(ms, pts)))
    return [dict(name=c['name'], kg=m, cap_kg=c['cap_kg'], fill=m/c['cap_kg']) for c, m in zip(cs, ms)], res


def propellant_parts(s, he3_kg, d2_kg, h2_kg, balanced=True):
    """Propellant as point masses: helium-3 spread over the 27 body lobes by volume (axisymmetric), deuterium and hydrogen in the torus
    cells, balanced per species or (balanced=False) filled in proportion to each cell's capacity."""
    cells, tor = torus_capacity(s); R, a = tor['R'], tor['a_in']; xc = tor['x']; out = []
    lobes = fuel_storage.body_lobes(s)
    if he3_kg > 0:
        tot = sum(l['liquid_m3'] for l in lobes)
        for l in lobes:
            m = he3_kg*l['liquid_m3']/tot; rr = (l['r_in']+l['r_out'])/2
            y, z = _arc_centroid(l['a0'], l['a1'], rr)
            out.append(_part(l['name'], m, l['x0'], l['x1'], ['point'], (y, z)))
    byname = {c['name']: c for c in cells}
    for sp, kg in (('deuterium', d2_kg), ('hydrogen', h2_kg)):
        if balanced:
            rows, _ = balance(s, sp, kg)
        else:
            cs = [c for c in cells if c['species'] == sp]; tot = sum(c['cap_kg'] for c in cs)
            rows = [dict(name=c['name'], kg=kg*c['cap_kg']/tot) for c in cs]
        for r in rows:
            if r['kg'] > 0:
                c = byname[r['name']]; y, z = _arc_centroid(c['a0'], c['a1'], R)
                out.append(_part(c['name'], r['kg'], xc-a, xc+a, ['point'], (y, z)))
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


def burn_states(s, steps=10, balanced=True):
    """Departure to burnout along the First Ignition burn: the propellant consumed in proportion to the expelled mass (operating_point),
    the reserve hydrogen left at burnout. Each state: mass, CG, lateral offset, inertia, thrust and the steering the offset needs."""
    inv = fuel_storage.cfg(s)['inventory_kg']; b = operating_point.burn(s); dry = dry_parts(s)
    fi = __import__('first_ignition').result(s); T = fi['time_s']; ve = b['exhaust_velocity_m_s']; m0 = b['departure_mass_kg']
    a_max = s['mission']['first_ignition']['max_accel']*G0; r_noz = s['prototype']['nozzle_offset_m']; out = []
    for i in range(steps+1):
        t = T*i/steps; v = a_max*t*t/(2*T); m = m0*math.exp(-v/ve); f = (m0-m)/b['expelled_kg']   # fraction of the burn's expelled mass
        he3 = inv['helium_3']*(1-f); d2 = inv['deuterium']*(1-f); h2 = inv['hydrogen_reserve']+inv['hydrogen_first_ignition']*(1-f)
        tot = totals(dry+propellant_parts(s, he3, d2, h2, balanced))
        F = m*a_max*t/T
        tot.update(t_s=t, thrust_N=F, steer_torque_N_m=F*tot['lateral_m'], differential_thrust=tot['lateral_m']/r_noz,
                   propellant_kg=he3+d2+h2)
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
    trimmed = burn_states(s); untrimmed = burn_states(s, balanced=False); inv = fuel_storage.cfg(s)['inventory_kg']
    lim = q(s)['max_differential_thrust']
    worst = max(trimmed, key=lambda r: r['differential_thrust']); worst_u = max(untrimmed, key=lambda r: r['differential_thrust'])
    dep_d2, d2_res = balance(s, 'deuterium', inv['deuterium'])
    dep_trim, dep_res = balance(s, 'hydrogen', inv['hydrogen_first_ignition']+inv['hydrogen_reserve'])
    end_trim, end_res = balance(s, 'hydrogen', inv['hydrogen_reserve'])
    fails = []
    if worst['differential_thrust'] > lim:
        fails.append(f"balanced burn needs {worst['differential_thrust']:.3f} differential thrust (limit {lim})")
    rb = ring_balance(s)
    return dict(status=q(s)['canon_status'], departure=trimmed[0], burnout=trimmed[-1],
                cg_travel_m=trimmed[0]['cg_m'][0]-trimmed[-1]['cg_m'][0],
                trimmed_worst=dict(t_s=worst['t_s'], lateral_m=worst['lateral_m'], differential_thrust=worst['differential_thrust']),
                untrimmed_worst=dict(t_s=worst_u['t_s'], lateral_m=worst_u['lateral_m'], differential_thrust=worst_u['differential_thrust'],
                                     steer_torque_N_m=worst_u['steer_torque_N_m']),
                load_deuterium=dict(cells=dep_d2, residual_kg_m=d2_res), trim_departure=dict(cells=dep_trim, residual_kg_m=dep_res), trim_burnout=dict(cells=end_trim, residual_kg_m=end_res),
                ring_balance=rb, spokes=spokes(s), burn=trimmed, failures=fails)


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
    print('deuterium', [(c['name'], round(c['kg']/1e3, 1), round(c['fill'], 2)) for c in r['load_deuterium']['cells']], round(r['load_deuterium']['residual_kg_m']))
    print('hydrogen departure', [(c['name'], round(c['kg']/1e3, 1), round(c['fill'], 2)) for c in r['trim_departure']['cells']], round(r['trim_departure']['residual_kg_m']))
    print('hydrogen burnout', [(c['name'], round(c['kg']/1e3, 1), round(c['fill'], 2)) for c in r['trim_burnout']['cells']], round(r['trim_burnout']['residual_kg_m']))
    print('rings', json.dumps(r['ring_balance'], default=float)[:600]); print('spokes', r['spokes']); print('failures', r['failures'])
