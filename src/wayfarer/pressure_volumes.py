"""Pressurized volumes of the built PROTOTYPE rooms for the owner's readback (READBACK-001; S&E 34!A96:A97, 33!A5:A68).

The pressure meshes are wall shells, so a mesh volume measures the wall. These figures come from the generator dimensions the meshes are
built from: gross is the clear cavity inside the pressure wall, net subtracts the fit-out the model knows. Junction overlaps (a neck
opening into a chamber) are not deducted. Correspondence evidence only: nothing here goes back into canon (AGENTS.md)."""
import math

import crew_transfer
import habitat_interior
import habitat_ring
import hull_geometry
import human_entry


def _path_length(points):
    return sum(math.dist(a, b) for a, b in zip(points, points[1:]))


def _cylinder(r, length):
    return math.pi*r*r*length


def rooms(s):
    """{object name: record} for every pressurized room the vehicle builds. A record has gross_m3, net_m3 (None when the model holds
    no fit-out figure for it), zone (STATIONARY or ROTATING), category and basis."""
    out = {}

    def add(name, gross, zone, category, basis, net=None):
        out[name] = dict(gross_m3=gross, net_m3=net, zone=zone, category=category, basis=basis)

    # Ring sectors: one library mesh per sector instance. Gross is the faceted sector solid inside the outer skin face (habitat_ring);
    # net is the walkable deck-to-overhead space less the modelled fit-out zones (berths, couches, racks, stations), the free volume
    # after hardware in the sense of 33!A3. The sourced allocation (240 m3 / 6 = 40 m3 usable per sector) is only quoted.
    import survival_fit
    sec = habitat_interior.section(s); report = habitat_interior.check(s)['functions']
    # SP-46..54 envelopes in a sector (survival_fit.sector), less the SP-46 station, which is inside the workbench's zone already.
    extra = {fn: sum(q['volume_m3'] for q in survival_fit.sector(s, fn) if q['sp'] != 'SP-46') for fn in s['sector_whitebox']['functions']}
    for q in habitat_ring.sectors(s):
        fitted = report[q['function']]['zone_volume_m3']+extra.get(q['function'], 0.0)
        add(q['name'], habitat_ring.sector_gross_m3(s), 'ROTATING', f"ring sector ({q['function']})",
            f"habitat_ring.sector_gross_m3 (faceted solid, r {q['r0']:g}-{q['r1']:g} m x {q['axial']:g} m); inside the skin "
            f"{habitat_ring.cavity_m3(s):.2f} m3; net = deck to overhead {sec['deck_to_overhead_m3']:.2f} m3 less {fitted:.2f} m3 of "
            f"modelled fit-out zones and SP envelopes; subfloor {sec['subfloor_m3']:.2f} m3 not counted; sourced usable allocation {sec['usable_m3']:g} m3",
            net=sec['deck_to_overhead_m3']-fitted)
    r = hull_geometry.refuge(s); sp = sum(q['volume_m3'] for q in survival_fit.refuge(s))
    add('Refuge_Storm_Shelter', r['pressure_volume_m3'], 'STATIONARY', 'storm refuge',
        f"hull_geometry.refuge annular cavity r {r['inner']:.2f}-{r['pressure']:.2f} m, x {r['cavity_x0']:.2f}-{r['cavity_x1']:.2f} m; "
        f"net = less {sp:.2f} m3 of SP-48/SP-50/SP-54 envelopes (survival_fit.refuge); anchor rails and lights not deducted",
        net=r['pressure_volume_m3']-sp)
    # HUM-002: the SP-45 storeroom's clear cuboid; net less the racks (storeroom.rows), whose containers are illustrative.
    import storeroom
    st = storeroom.station(s); racks = storeroom.check(s)[0]['rack_m3']
    add('Storeroom_Shell', st['L']*st['W']*st['H'], 'STATIONARY', 'general storeroom (SP-45)',
        f"storeroom clear cuboid {st['L']:g} x {st['W']:g} x {st['H']:g} m (33!C85:C87, PROVISIONAL); net = less {racks:.2f} m3 of full-height racks",
        net=st['L']*st['W']*st['H']-racks)
    # Hollow rods: the trunk, the human-entry connectors and spine ports, the refuge port, the storeroom port and the crew tubes.
    for q in crew_transfer.stationary(s)+crew_transfer.rotating(s):
        if not q.get('hollow'):
            continue
        if q['shape'] == 'rod':
            length = _path_length(q['points'])
            zone = 'ROTATING' if q.get('rotor') and q['role'] == 'COAST_TUBE' else 'STATIONARY'
            add(q['name'], _cylinder(q['hollow'], length), zone, f"crew passage ({q['role']})",
                f"crew_transfer clear radius {q['hollow']:.3f} m x path {length:.2f} m")
        elif q['shape'] == 'ring':
            wall = q.get('wall', 0.0); inner = q['r0']+wall; length = (q['x1']-q['x0'])
            add(q['name'], math.pi*(q['hollow']**2-inner**2)*length, 'DESPUN', f"transfer drum chamber ({q['role']})",
                f"crew_transfer annular chamber r {inner:.3f}-{q['hollow']:.3f} m x {length:.2f} m (despun drum, MEC-019)")
    # The primary entry: revolved shells about the port axis (human_entry.stations).
    for f in hull_geometry.service_fittings(s):
        if f['name'] != 'Dock_Primary':
            continue
        st = human_entry.stations(s, f); c = st['clear']
        add('Dock_Primary_Entry_Chamber', _cylinder(st['chamber_r'], st['a_out']-st['a_in']), 'STATIONARY', 'entry chamber',
            f"human_entry.stations chamber r {st['chamber_r']:.2f} m x {st['a_out']-st['a_in']:.2f} m between the hatches")
        add('Dock_Primary_Trunk_Node', _cylinder(st['node_r'], st['bottom']-st['node_in']), 'STATIONARY', 'trunk node',
            f"human_entry.stations node r {st['node_r']:.2f} m x {st['bottom']-st['node_in']:.2f} m")
        add('Dock_Primary', _cylinder(c, st['port_face']-st['top']), 'STATIONARY', 'outer docking neck',
            f"clear r {c:.2f} m x {st['port_face']-st['top']:.2f} m from the chamber to the docking face")
        add('Dock_Primary_Inboard_Neck', _cylinder(c, st['node_floor']-st['root']), 'STATIONARY', 'inboard neck',
            f"clear r {c:.2f} m x {st['node_floor']-st['root']:.2f} m")
    return out


def totals(s):
    """Rotating, despun and stationary sums, with the counts behind them."""
    sums = {}
    for name, q in rooms(s).items():
        t = sums.setdefault(q['zone'], dict(rooms=0, gross_m3=0.0, net_m3=0.0, net_known=0))
        t['rooms'] += 1; t['gross_m3'] += q['gross_m3']
        if q['net_m3'] is not None:
            t['net_m3'] += q['net_m3']; t['net_known'] += 1
    return sums
