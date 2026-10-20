"""Rigid habitat rings (FGR-003): sourced ring radii and ring-equivalent dynamics, plus the PROTOTYPE sector, frame and spoke layout.

Canon (drive_capture_2026-10-02, S&E 08_ROTATING_HABITAT, 02_SHIP_INPUTS, 12_HABITAT_LAYOUT; 15_MODEL_INTERFACES H3): two coaxial
counter-rotating rigid annular rings of fixed ~60 m diameter that never deploy or retract. Pressurized rooms occupy only sectors of
the annular frames (400-460 m3 gross across both rings); water, storage and structure fill the rest of the frame. The occupied
floor is at r 28 m, the structural outer radius at r 30 m, and the ring-equivalent mass sits at floor - depth/2.

The ring cross-section, spokes, frame, locks and flexible modes are OPEN (08!A53, OD-016). Everything under [habitat_ring] is a
PROTOTYPE selection; the arc of one sector is solved from the gross-volume target and nothing here is a structural design.

Frames: ring-local, origin on the rotor centre, +X along the spin axis; angles about +X from +Y; u = axial offset from the ring plane.
Canon update drive_capture_2026-10-03: 08!C37 and C41:C45 are reproduced as DIAGNOSTIC comparisons (diagnostics()), not limits.
Leaf module: standard library and the pure layout module only; reads the spec dict.
"""
import math
import layout

G0 = 9.80665  # 01_CONSTANTS g0 (LOCKED)


# ---------- sourced accessors ---------------------------------------------------------------------------------------

def outer(s):
    return s['habitat']['outer_radius']['value']


def floor(s):
    return s['habitat']['floor_radius']['value']


def depth(s):
    return s['habitat']['mass_radial_depth']['value']


def com(s):
    """Ring-equivalent mass radius: floor - depth/2 (08!C10)."""
    return floor(s)-depth(s)/2


def ring_count(s):
    return s['habitat']['ring_count']


def omega(s):
    return s['habitat']['rpm']*2*math.pi/60


def centers(s):
    """Ship-frame X of the two ring planes (layout.py datums)."""
    return [layout.at(s, r) for r in s['prototype']['rotor_centers_x']]


def sweep_half(s):
    """Axial half-extent swept by one ring: half the frame plus the axial allowance."""
    r = s['habitat_ring']
    return r['frame_axial_m']/2+r['axial_allowance_m']


def floor_gravity_g(s, radius=None):
    return omega(s)**2*(floor(s) if radius is None else radius)/G0


def tilt_deg(s, axial_g=None):
    """Tilt of the perceived down for an axial acceleration; default the working low-thrust limit (08!H54)."""
    if axial_g is None:
        axial_g = s['habitat']['low_thrust_limit']['value']
    return math.degrees(math.atan2(axial_g, floor_gravity_g(s)))


# ---------- ring-equivalent dynamics (DERIVED, formula owner 08!C10:C36) ------------------------------------------------

def dynamics(s):
    """Every physics.rotor_dynamics number, from the workbook formulas and current inputs."""
    ph, ro = s['physics'], s['physics']['rotor_operations']
    w = omega(s); radius = com(s)
    mass = ph['rotor_sizing']['mass_kg']/ring_count(s)
    inertia = mass*radius**2; momentum = inertia*w; torque = momentum/ro['spin_up_time_s']
    accel = s['mission']['first_ignition']['max_accel']
    return {'omega_rad_s': w, 'com_radius_m': radius, 'mass_each_kg': mass, 'inertia_each_kg_m2': inertia,
            'angular_momentum_each_N_m_s': momentum, 'spin_torque_each_N_m': torque,
            'peak_spin_power_total_W': ring_count(s)*torque*w,
            'rpm_match_tolerance_rpm': s['habitat']['rpm']*ro['momentum_balance_tolerance'],
            'allowed_residual_momentum_N_m_s': momentum*ro['momentum_balance_tolerance'],
            'centripetal_force_per_ring_N': mass*w**2*radius,
            'high_thrust_axial_load_each_N': mass*accel*G0,
            'high_thrust_axial_load_total_N': ph['rotor_sizing']['mass_kg']*accel*G0}


def diagnostics(s):
    """08!C37, C41:C45 (DIAGNOSTIC owner comparisons, not limits) from current inputs."""
    x = s['physics']['rotor_dynamics_diagnostic']
    h_single = s['physics']['rotor_sizing']['mass_kg']*com(s)**2*omega(s)
    i_f = x['flywheel_mass_kg']*x['flywheel_radius_m']**2      # the owner's thin-rim m*r^2
    w_f = h_single/i_f
    return {'high_thrust_combined_g': math.hypot(floor_gravity_g(s), s['mission']['first_ignition']['max_accel']),
            'gyro_torque_example_N_m': dynamics(s)['allowed_residual_momentum_N_m_s']*math.radians(x['example_slew_rate_deg_s']),
            'single_ring_angular_momentum_N_m_s': h_single,
            'flywheel_example_rpm': w_f*60/(2*math.pi),
            'flywheel_example_rim_speed_m_s': w_f*x['flywheel_radius_m'],
            'flywheel_example_energy_J': 0.5*i_f*w_f**2}


def spoke_axial_load_N(s):
    """Nominal 1.5 g axial load carried by one spoke before safety and dynamic factors: ring load shared by the spokes (Q28, ~405 kN at 165 t)."""
    return dynamics(s)['high_thrust_axial_load_each_N']/s['habitat_ring']['spokes_per_ring']


# ---------- mass basis (Q32): 330 t rotating = the rotating allowances of the budget; 20 t of the water is the stationary refuge --------------

def water_item(s):
    return next(i for i in s['physics']['mass_budget']['items'] if i['id'] == 'water_radiation_shielding')


def rotating_total_kg(s):
    """Sum of the rotating allowances of the mass budget; must equal physics.rotor_sizing.mass_kg (spec.validate_sourced_budgets)."""
    return sum(i.get('rotating_allowance_kg', 0) for i in s['physics']['mass_budget']['items'])


def refuge_water_allocation_kg(s):
    """Stationary refuge share of the water line (Q32, ~20 t); rotating + refuge = the water item, never additive (owner_targets.budget_failures)."""
    return water_item(s)['refuge_allowance_kg']


def kinetic_energy_each(s):
    d = dynamics(s)
    return 0.5*d['inertia_each_kg_m2']*d['omega_rad_s']**2


# ---------- sector geometry (PROTOTYPE) -----------------------------------------------------------------------------------

def annulus_area_factor(r0, r1):
    return 0.5*(r1*r1-r0*r0)


def sector_arc(s):
    """Arc of one sector in rad, solved from the gross-volume target: V = arc * 1/2 (r1^2 - r0^2) * axial."""
    r = s['habitat_ring']
    return r['sector_gross_target_m3']/(annulus_area_factor(r['sector_inner_radius_m'], r['sector_outer_radius_m'])*r['sector_axial_m'])


def sector_gross_m3(s):
    return gross_for_arc(s, sector_arc(s))


def deck_to_overhead_m3(s, arc=None):
    """Volume between the deck (floor radius) and the sector's inner radius at the given arc."""
    r = s['habitat_ring']
    return (sector_arc(s) if arc is None else arc)*annulus_area_factor(r['sector_inner_radius_m'], floor(s))*r['sector_axial_m']


def gross_for_arc(s, arc):
    r = s['habitat_ring']
    return arc*annulus_area_factor(r['sector_inner_radius_m'], r['sector_outer_radius_m'])*r['sector_axial_m']


def arc_for_deck_volume(s, volume):
    """Arc that would give `volume` between deck and overhead (the alternative reading of 12!A3; used as a negative case)."""
    r = s['habitat_ring']
    return volume/(annulus_area_factor(r['sector_inner_radius_m'], floor(s))*r['sector_axial_m'])


def sector_angles(s):
    """Ring-local centre angles of the sectors (rad)."""
    n = s['habitat_ring']['sectors_per_ring']
    return [k*math.tau/n for k in range(n)]


def sectors(s):
    """Sectors of every ring: name, ident, ring-local angle, function, radii, axial extent and volumes."""
    r = s['habitat_ring']; arc = sector_arc(s); usable = s['habitat']['layout']['usable_per_ring_m3']/r['sectors_per_ring']
    out = []
    for j in range(1, ring_count(s)+1):
        for k, a in enumerate(sector_angles(s), 1):
            out.append(dict(name=f'Sector_{j}_{k}', ident=f'WF.SECTOR.{j}.{k}', ring=j, index=k, angle=a, arc=arc,
                            function=r['sector_functions'][k-1], r0=r['sector_inner_radius_m'], r1=r['sector_outer_radius_m'],
                            deck_radius=floor(s), axial=r['sector_axial_m'], gross_m3=sector_gross_m3(s),
                            usable_alloc_m3=usable, deck_to_overhead_m3=deck_to_overhead_m3(s, arc)))
    return out


def gross_total(s):
    return sum(q['gross_m3'] for q in sectors(s))


def polygon_volume(s):
    """Volume of the sector as the display mesh builds it: sector_arc_segments straight chords across the arc."""
    r = s['habitat_ring']; n = r['display']['sector_arc_segments']
    return r['sector_axial_m']*n*annulus_area_factor(r['sector_inner_radius_m'], r['sector_outer_radius_m'])*math.sin(sector_arc(s)/n)


def volume_numeric(s, steps=400):
    """Midpoint integration of one sector over r and the angle (independent of the closed form)."""
    r = s['habitat_ring']; arc = sector_arc(s); r0, r1 = r['sector_inner_radius_m'], r['sector_outer_radius_m']
    total = 0.0
    for a in range(steps):
        for b in range(steps):
            rr = r0+(r1-r0)*(b+.5)/steps
            total += rr*(r1-r0)/steps*arc/steps
    return total*r['sector_axial_m']


def ring_solid(x0, x1, r0, r1, t0, t1, n):
    """Closed ring or ring segment between radii r0..r1, axial x0..x1 and angles t0..t1 with n straight chords. Full rings wrap;
    segments get end caps. Vertices are (x, r cos t, r sin t)."""
    full = math.isclose(t1-t0, math.tau)
    m = n if full else n+1
    ts = [t0+(t1-t0)*k/n for k in range(m)]
    corners = [(x0, r0), (x0, r1), (x1, r1), (x1, r0)]
    vertices = [(x, rr*math.cos(t), rr*math.sin(t)) for x, rr in corners for t in ts]
    faces = []
    for b in range(4):
        c = (b+1) % 4
        for k in range(n):
            k1 = (k+1) % m
            faces.append((b*m+k, b*m+k1, c*m+k1, c*m+k))
    if not full:
        # End caps wound outward like the sides, so the mesh encloses a positive signed volume.
        for k in (0, m-1):
            faces.append(tuple(b*m+k for b in range(4)) if not k else tuple(b*m+k for b in reversed(range(4))))
    return vertices, faces


def sector_solid(s):
    """Pressure envelope of one sector in the sector frame (origin on the centreline at the deck, +X axial, +Y radially outward,
    +Z tangential): vertices (u, r cos t - deck, r sin t)."""
    r = s['habitat_ring']; arc = sector_arc(s); half = r['sector_axial_m']/2
    vs, fs = ring_solid(-half, half, r['sector_inner_radius_m'], r['sector_outer_radius_m'], -arc/2, arc/2, r['display']['sector_arc_segments'])
    return [(x, y-floor(s), z) for x, y, z in vs], fs


def cavity_section(s):
    """HUM-001 zone 5: corners (radius, half-angle) of the skin's inner face in the ring-local radial plane. The inner and outer faces are
    arcs sector_skin_m inside the envelope's; the side faces are the side walls' planes moved sector_skin_m inward, so each arc ends where its
    radius meets that plane (r sin(arc/2 - angle) = skin)."""
    r = s['habitat_ring']; t = r['sector_skin_m']; a = sector_arc(s)/2
    return [(rr, a-math.asin(t/rr)) for rr in (r['sector_inner_radius_m']+t, r['sector_outer_radius_m']-t)]


def cavity_m3(s):
    """Volume inside the skin, as the display mesh builds it (chords across each face's own arc, straight side planes)."""
    r = s['habitat_ring']; n = r['display']['sector_arc_segments']; (r0, a0), (r1, a1) = cavity_section(s)
    pts = [(r0*math.cos(-a0+2*a0*k/n), r0*math.sin(-a0+2*a0*k/n)) for k in range(n+1)]+[(r1*math.cos(a1-2*a1*k/n), r1*math.sin(a1-2*a1*k/n)) for k in range(n+1)]
    area = abs(sum(p[0]*q[1]-q[0]*p[1] for p, q in zip(pts, pts[1:]+pts[:1])))/2
    return area*(r['sector_axial_m']-2*r['sector_skin_m'])


def sector_skin(s):
    """Pressure skin of one sector in the sector frame: the envelope (sector_solid, outward faces) and the skin's inner face (the cavity, faces
    wound inward), one closed shell sector_skin_m thick."""
    r = s['habitat_ring']; t = r['sector_skin_m']; n = r['display']['sector_arc_segments']; half = r['sector_axial_m']/2-t
    vs, fs = sector_solid(s); (r0, a0), (r1, a1) = cavity_section(s)
    _, faces = ring_solid(-half, half, r0, r1, -1.0, 1.0, n)
    inner = [(x, rr*math.cos(-a+2*a*k/n)-floor(s), rr*math.sin(-a+2*a*k/n)) for x, rr, a in ((-half, r0, a0), (-half, r1, a1), (half, r1, a1), (half, r0, a0))
             for k in range(n+1)]
    return vs+inner, fs+[tuple(len(vs)+i for i in reversed(f)) for f in faces]


def sector_frame_extent(s):
    """Axis-aligned extent of the sector envelope in the sector frame (x, y, z), from the exact vertices."""
    vs, _ = sector_solid(s)
    return [[min(v[i] for v in vs) for i in range(3)], [max(v[i] for v in vs) for i in range(3)]]


# ---------- frame and spokes (PROTOTYPE) ----------------------------------------------------------------------------------

def frame_parts(s):
    """Hoops (full circle) and the fills between the sectors, as ring-local annular solids; u is the axial offset from the ring plane."""
    r = s['habitat_ring']; half = r['frame_axial_m']/2; arc = sector_arc(s); out = []
    fill_arc = math.tau/r['sectors_per_ring']-arc
    for j in range(1, ring_count(s)+1):
        out.append(dict(name=f'Ring_{j}_Hoop_Inner', ring=j, kind='ring_frame', u0=-half, u1=half, r0=r['frame_inner_radius_m'], r1=r['sector_inner_radius_m'], t0=0.0, t1=math.tau))
        out.append(dict(name=f'Ring_{j}_Hoop_Outer', ring=j, kind='ring_frame', u0=-half, u1=half, r0=r['sector_outer_radius_m'], r1=outer(s), t0=0.0, t1=math.tau))
        for k, a in enumerate(sector_angles(s), 1):
            t0 = a+arc/2
            out.append(dict(name=f'Ring_{j}_Fill_{k}', ring=j, kind='ring_fill', u0=-half, u1=half, r0=r['sector_inner_radius_m'], r1=r['sector_outer_radius_m'],
                            t0=t0, t1=t0+fill_arc, sector=k))
    return out


def frame_solid(s, q):
    """Display mesh of one frame part (a hoop or a fill): hoop_facets chords around a full circle, proportionally fewer on a fill."""
    n = max(2, math.ceil(s['habitat_ring']['display']['hoop_facets']*(q['t1']-q['t0'])/math.tau))
    return ring_solid(q['u0'], q['u1'], q['r0'], q['r1'], q['t0'], q['t1'], n)


def joints(s, t0, t1):
    """Assembly-segment joint angles strictly inside t0..t1: half a segment either side of each sector angle, then every segment."""
    c = s['habitat_ring']['construction']; seg = math.radians(c['segment_deg'])
    k = math.ceil((t0-seg/2)/seg-1e-9)
    out = []
    while seg/2+k*seg < t1-1e-9:
        out.append(seg/2+k*seg); k += 1
    return [a for a in out if a > t0+1e-9]


def frame_mesh(s, q):
    """Display mesh of one frame part with its construction (habitat_ring.construction, PROTOTYPE): vertices, faces and one class per
    face (frame, joint, band, cassette, cover, service, service_cover). The inner hoop stays frame_solid. Every piece lies inside the part's
    band (u0..u1, r0..r1, t0..t1), inset or flush, so the sweep and the volumes of frame_parts are unchanged."""
    r = s['habitat_ring']; c = r['construction']; n = r['display']['hoop_facets']
    vs, fs, cls = [], [], []

    def add(kind, u0, u1, r0, r1, t0, t1, k=None):
        if t1-t0 < 1e-9:
            return
        v, f = ring_solid(u0, u1, r0, r1, t0, t1, k or max(2, math.ceil(n*(t1-t0)/math.tau)))
        base = len(vs); vs.extend(v); fs.extend(tuple(base+i for i in face) for face in f); cls.extend([kind]*len(f))

    if q['name'].endswith('Hoop_Inner'):
        v, f = frame_solid(s, q)
        return v, f, ['frame']*len(f)
    u0, u1, r0, r1, t0, t1 = q['u0'], q['u1'], q['r0'], q['r1'], q['t0'], q['t1']; ins = c['inset_m']
    if q['name'].endswith('Hoop_Outer'):
        seg = math.radians(c['segment_deg']); g = c['groove_m']/2/r1; js = joints(s, -seg, math.tau)
        secs = sector_angles(s); bd = c['band_depth_m']; bu = c['band_half_u_m']
        for a, b in zip(js, js[1:]):
            if any(math.isclose(((a+b)/2-x+math.pi) % math.tau-math.pi, 0, abs_tol=1e-6) for x in secs):
                add('frame', u0, u1, r0, r1-bd, a+g, b-g)
                add('band', -bu, bu, r1-bd, r1, a+g, b-g)
                add('frame', bu, u1, r1-bd, r1, a+g, b-g); add('frame', u0, -bu, r1-bd, r1, a+g, b-g)
            else:
                add('frame', u0, u1, r0, r1, a+g, b-g)
            add('joint', u0+ins, u1-ins, r0, r1-ins, b-g, b+g, 1)
        return vs, fs, cls
    # A fill between two sectors: flank frames at both sector edges, web frames at the joints, cassettes between, and a service node at the
    # structural spoke (half way between the sectors).
    mid = (r0+r1)/2; w = c['web_m']/2/mid; f = c['flank_m']/mid; js = joints(s, t0, t1)
    add('frame', u0, u1, r0, r1, t0, t0+f, 1); add('frame', u0, u1, r0, r1, t0+f, js[0]-w, 1)
    add('frame', u0, u1, r0, r1, js[-1]+w, t1-f, 1); add('frame', u0, u1, r0, r1, t1-f, t1, 1)
    for a in js:
        add('frame', u0, u1, r0, r1, a-w, a+w, 1)
    node = (t0+t1)/2; nh = math.radians(c['node_half_deg']); m = c['cover_margin_m']
    face = lambda side: sorted((side*(u1-ins), side*(u1-ins+c['cover_m'])))
    for a, b in zip(js, js[1:]):
        lo, hi = a+w, b-w
        spans = [(lo, hi, r0)] if not lo < node < hi else [(lo, node-nh, r0), (node-nh, node+nh, c['node_outer_radius_m']), (node+nh, hi, r0)]
        for c0, c1, rin in spans:
            add('cassette', u0+ins, u1-ins, rin, r1, c0, c1)
            tiers = [(rin+m, (rin+r1)/2-m/4), ((rin+r1)/2+m/4, r1-m)] if r1-rin > 2.5 else [(rin+.75*m, r1-.75*m)]
            for side in (-1, 1):
                for p0, p1 in tiers:
                    add('cover', *face(side), p0, p1, c0+m/r1, c1-m/r1)
        if lo < node < hi:
            add('service', u0+ins, u1-ins, r0, c['node_outer_radius_m'], node-nh, node+nh)
            for side in (-1, 1):
                add('service_cover', *face(side), r0+.75*m, c['node_outer_radius_m']-.75*m, node-nh+.75*m/r0, node+nh-.75*m/r0)
    return vs, fs, cls


def spokes(s):
    """Rails of every spoke: n = 1..spokes_per_ring at (n-1)*360/spokes_per_ring; crew spokes sit on a sector angle. Two rails per
    spoke at u = +-spoke_rail_u, from the drum outer radius to the frame inner radius."""
    r = s['habitat_ring']; n = r['spokes_per_ring']; secs = sector_angles(s); out = []
    for j in range(1, ring_count(s)+1):
        for i in range(1, n+1):
            a = (i-1)*math.tau/n
            crew = any(math.isclose(a, b, abs_tol=1e-9) for b in secs)
            for side in (-1, 1):
                out.append(dict(name=f'Ring_Spoke_{j}_{i}_{side}', ring=j, index=i, side=side, angle=a, crew=crew, u=side*r['spoke_rail_u_m'],
                                radius=r['spoke_rail_radius_m'], r0=s['rotor_interface']['drum_outer_radius_m'], r1=r['frame_inner_radius_m']))
    return out


def spoke_depth_m(s):
    """Axial depth of one twin-rail spoke as built: the two rails at u = +-spoke_rail_u plus the rail radius (PROTOTYPE, 1.04 m); Q28 asks 1.2-1.5 m."""
    r = s['habitat_ring']
    return 2*(r['spoke_rail_u_m']+r['spoke_rail_radius_m'])


def spar_clearance_m(s):
    """Axial clearance from the ring-A aft sweep face to the front of the radiator leading spar (Q29: >= 1.5 m, was ~0.60 m)."""
    p = s['prototype']
    return centers(s)[0]-sweep_half(s)-(layout.origin(s, 'RADIATOR_FRONT')+p['radiator_leading_spar_radius_m'])


def plane_spacing_m(s):
    c0, c1 = centers(s)
    return c1-c0


def lock_angles(s, j):
    """World angles of the ring-stop locks of ring j: the crew-spoke angles at the ring's index phase."""
    phase = math.radians(s['prototype']['rotor_phase_deg'][j-1])
    return [phase+a for a in sector_angles(s)]


# ---------- checks ----------------------------------------------------------------------------------------------------------

def check(s):
    """Failure list for the ring layout against the sourced radii, volumes and clearances. Empty when the layout holds."""
    failures = []
    def need(ok, message):
        if not ok:
            failures.append(message)
    h, r, lay = s['habitat'], s['habitat_ring'], s['habitat']['layout']
    need(r['status'] == 'PROTOTYPE' and r['unit'] == 'm', 'habitat_ring stays a PROTOTYPE selection in metres')
    ri_, ro_, rf, rs_, rn = r['frame_inner_radius_m'], outer(s), floor(s), r['sector_inner_radius_m'], r['sector_outer_radius_m']
    need(ri_ < rs_ < rf < rn < ro_, f'Radius order frame inner {ri_} < sector inner {rs_} < floor {rf} < sector outer {rn} < ring outer {ro_}')
    need(r['sector_axial_m'] < r['frame_axial_m'], 'Sector must sit inside the frame axially')
    n = r['sectors_per_ring']
    need(type(n) is int and n >= 1, 'sectors_per_ring must be a positive integer')
    arc = sector_arc(s) if n >= 1 else 0.0
    need(n*arc < math.tau, 'Sectors must leave room for fills')
    total = gross_total(s) if n >= 1 else 0.0
    need(h['volume']['gross_min_m3'] <= total <= h['volume']['gross_max_m3'], f'Gross pressure volume {total:.3f} m3 outside the BASELINE 400-460 m3 envelope')
    need(deck_to_overhead_m3(s) >= lay['usable_per_ring_m3']/max(n, 1), 'Deck-to-overhead volume cannot hold the usable allocation per sector')
    need(math.isclose(lay['usable_per_ring_m3']*ring_count(s), lay['usable_working_m3']) and h['volume']['usable_min_m3'] <= lay['usable_working_m3'] <= h['volume']['usable_max_m3'],
         'Usable volume per ring x rings must equal the working volume inside the BASELINE envelope')
    need(type(r['spokes_per_ring']) is int and r['spokes_per_ring'] % max(n, 1) == 0, 'Spokes per ring must be a multiple of the sectors per ring')
    need(sorted(r['sector_functions']) == sorted(lay['functions']) and len(set(r['sector_functions'])) == len(r['sector_functions']) == n,
         'Sector functions must be a permutation of the habitat functions, one per sector')
    ri_cfg = s['rotor_interface']; d0, d1 = ri_cfg['drum_u_m']; rail = r['spoke_rail_u_m']+r['spoke_rail_radius_m']
    need(d0 < -rail and rail < d1 and r['spoke_rail_u_m'] > 0 and r['spoke_rail_radius_m'] > 0, 'Spoke rails must attach inside the hub drum span')
    need(ri_cfg['drum_outer_radius_m'] < ri_, 'Spokes must reach from the drum to the frame')
    need(rf-rs_ >= s['interior']['min_headroom_m'], 'Floor to sector inner radius must give the minimum headroom')
    c0, c1 = centers(s); p = s['prototype']
    need(c1-c0 >= 2*sweep_half(s)+p['mechanical_clearance_m'], 'Ring planes overlap axially')
    need(r['display']['hoop_facets'] >= 12 and r['display']['sector_arc_segments'] >= 2, 'Display facets')
    c = r['construction']; mid = (rs_+rn)/2; per = 360.0/c['segment_deg']
    need(math.isclose(per, round(per)) and round(per) % max(n, 1) == 0, 'Assembly segments must divide the ring evenly per sector')
    need(arc/2+(c['flank_m']+c['web_m']/2)/mid < math.radians(c['segment_deg'])/2, 'Sector and its flank frames must fit inside the pressure segment')
    need(0 < c['cover_m'] < c['inset_m'] and 0 < c['band_depth_m'] < ro_-rn and c['band_half_u_m'] < r['frame_axial_m']/2, 'Construction relief must stay inside the frame')
    need(rs_ < c['node_outer_radius_m'] < rn, 'Service node must sit inside the fill')
    if not failures:
        for q in frame_parts(s):
            vs, fs, cls = frame_mesh(s, q)
            ok = all(q['u0']-1e-6 <= u <= q['u1']+1e-6 and q['r0']*math.cos(math.pi/r['display']['hoop_facets'])-1e-6 <= math.hypot(y, z) <= q['r1']+1e-6 for u, y, z in vs)
            need(ok and len(fs) == len(cls), f"{q['name']}: construction leaves the frame part")
    return failures
