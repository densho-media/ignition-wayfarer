"""Vertex Engine 1.8: Adaptive Engine Architecture, 3D integration and mechanical animation study (owner brief 2026-11-16 11:08Z).

Research and design only: nothing in the generators, the canon or the built geometry reads this module. It answers the brief from the
drawn engine itself (vertex_engine.parts, the families that become Blender objects, the cluster's linked instances, the effect drivers
and DRIVE_MANIFOLD_CTRL) and from the earlier evidence (1.6A Fiji, 1.6B source, 1.7 dynamic):

  audit      what the built engine is: parts, objects, triangles, instances, drivers, states, and which parts can move as they are
  carriages  L4 slides on straightened aft longeron rails (continuous winding): stowed and extended strokes, field, sky, mass
  alignment  what a millimetre of loop offset does to the field direction at the burn and to the thrust vector
  petals     a petal that splits a winding needs demountable superconducting joints: their heat, decay and what persistent mode needs
  fiji       what the lattice can do with its one property (1.6A), so the animation does not promise more
  concepts   A Minimal Adaptive, B Bloom (compact), C Integrated, and the recommended A+ hybrid, each with mass, envelope, sky, heat,
             objects, draw calls, failure modes and the speculative principles it needs
  sequence   the nine states on existing and proposed controller properties, with physical and display durations
  field      axisymmetric field lines from the coil currents (vertex_magnet), for the field-visualization mode and the figure
  browser    object, node, triangle and byte estimates against the viewer budget (planning numbers; measured only in Phase F)
  roadmap    the generator files each step changes, and what is reused, modified, new, animation-only or shader-only

Run: python3 src/wayfarer/vertex_adaptive.py [--evidence]
"""
import hashlib
import json
import math
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
import spec  # noqa: E402
import drive_manifold as dm  # noqa: E402
import vertex_cluster as vc  # noqa: E402
import vertex_dynamic as vd  # noqa: E402
import vertex_engine as ve  # noqa: E402
import vertex_fiji_a as va  # noqa: E402
import vertex_magnet as vm  # noqa: E402
import vertex_source as vso  # noqa: E402

EVIDENCE_PATH = ROOT/'references/evidence/vertex_adaptive.json'
OPT, NOM, PES = 0, 1, 2
LOOPS = ('L1', 'L2', 'L3', 'L4')


def config(s):
    return s['vertex_adaptive']


def _j(p):
    return json.loads(Path(p).read_text())


def _tris(p):
    return sum(len(f)-2 for f in ve.mesh_of(p)[1])


def _mass(s, p):
    mt = ve.config(s)['materials']; key = p['material'] if p['material'] in mt['density_kg_m3'] else 'sensor'
    return ve._volume(p)*mt['density_kg_m3'][key]*mt['solid_fraction'][key]


def ring_members(name):
    """Parts that travel with a nozzle loop when it moves: winding, cryostat segments and joint flanges, armour, cage hoop (the carriage
    ring), loop seats (the rail shoes), armour header and its lithium jumpers, and the lead and cryogen branches (flexible on a carriage)."""
    stems = (f'VTX_{name}_Winding', f'VTX_{name}_Segment_', f'VTX_{name}_Joint_', f'VTX_{name}_Armour_', f'VTX_Cage_Hoop_{name}',
             f'VTX_Loop_Seat_{name}_', f'VTX_{name}_Armour_Header', f'VTX_{name}_Lithium_', f'VTX_{name}_Lead_', f'VTX_{name}_Cryo_')
    return lambda n: any(n == x or n.startswith(x) for x in stems)


# ---------- 1-2: audit of the built engine ---------------------------------------------------------------------------------------------

def audit3d(s):
    P = ve.parts(s); fams = ve.families(P); D = vd.audit(s)
    movers = {n: ring_members(n) for n in LOOPS}
    rows = []
    for name, ps in fams:
        moving = sorted({l for p in ps for l, f in movers.items() if f(p['name'])})
        if not moving:
            cls = 'STATIC'
        elif len(ps) == 1:
            cls = 'TRANSFORM_READY'
        else:
            cls = 'NEEDS_SPLIT'
        rows.append(dict(object=name, parts=len(ps), category=ps[0]['category'], material=ps[0]['material'], tris=sum(_tris(p) for p in ps),
                         moves_with=moving, status=cls))
    windings = [p['name'] for p in P if p['name'].endswith('_Winding') and p['category'] == 'MAGNETIC_NOZZLE']
    by_cat = {}
    for p in P:
        by_cat[p['category']] = by_cat.get(p['category'], 0)+1
    drv = vc.drivers(s); eff = vc.effect_objects(s); pls = vc.placements(s); gp = vc.gaps(s); env = ve.envelope(s)
    return dict(
        parts=len(P), parts_by_category=by_cat, objects=len(fams), tris=sum(r['tris'] for r in rows), families=rows,
        status_counts={k: sum(1 for r in rows if r['status'] == k) for k in ('STATIC', 'TRANSFORM_READY', 'NEEDS_SPLIT')},
        windings=windings, winding_note='each nozzle loop is one continuous torus winding inside eight cryostat segments with joint flanges; '
                                         'a petal that opens a segment must cut the winding',
        instances=dict(count=len(pls), mechanism='one linked collection instance of WF_VERTEX_ENGINE per engine (ENGINE_N1..N4)',
                       consequence='every engine shows the same pose of anything inside the linked engine; per-engine motion needs per-engine '
                                   'objects in the cluster sharing one mesh each (the pattern the 56 effect objects already use) or library '
                                   'overrides', placements=[dict(name=p['name'], label=p['label'], azimuth_deg=p['azimuth_deg']) for p in pls]),
        effects=dict(objects=len(eff), per_engine=len(eff)//len(pls), field_envelopes=len(pls)),
        drivers=dict(count=len(drv), by_path={k: sum(1 for d in drv if d[1] == k) for k in sorted({d[1] for d in drv})}),
        control=dict(object=dm.CONTROL, properties=list(dm.PROPS), settings=dict(dm.SAVED_SETTINGS), variables=dict(dm.VARIABLES),
                     states=list(vc.STATES)),
        envelope=dict(length_m=env['length'], max_radius_m=env['max_radius'], x0=env['x0'], x1=env['x1']),
        cluster=dict(gp, adjacent_m=D['geometry']['adjacent_m'], cluster_radius_m=D['geometry']['cluster_radius_m'],
                     maintenance_m=D['geometry']['maintenance_m']),
        coils=D['geometry']['coils'], burn_x=D['geometry']['burn_x'], exit_x=D['geometry']['exit_x'],
        shield=dict(aft_x=D['geometry']['shield_aft_x'], radius_m=D['geometry']['shield_aft_radius_m']),
        cage=dict(longeron=[(x, math.hypot(y, z)) for x, y, z in next(p for p in P if p['name'] == 'VTX_Cage_Longeron_1')['points']],
                  hoops=[dict(name=p['name'][-2:], x=p['x'], R=p['R'], a=p['a']) for p in P if p['name'].startswith('VTX_Cage_Hoop_')],
                  collar=next(p for p in P if p['name'] == 'VTX_Thrust_Collar')['profile']),
        mass=dict(engine_kg=D['mass']['engine_kg'], margin_kg=D['mass']['margin_kg'], engines_and_frame_kg=D['mass']['engines_and_frame_kg'],
                  protected_ship_kg=D['mass']['protected_ship_kg']),
        field=D['field'])


# ---------- field helpers --------------------------------------------------------------------------------------------------------------

def _currents(AU):
    return list(AU['field']['currents_At'])


def BURN(s):
    return vd.audit(s)['geometry']['burn_x']


def hold(s, AU, geom, moved):
    """Scale the moved loops' currents so the stop field at the burn is the canon value; returns the scale and the field."""
    cs0 = vm.coil_set(s); I = _currents(AU); bx = BURN(s); B0 = vm.field(cs0, I, bx, 0.0)[1]
    cs = vm.coil_set(s, geom); names = [c['name'] for c in cs]
    fixed = [0.0 if n in moved else i for n, i in zip(names, I)]; mov = [i if n in moved else 0.0 for n, i in zip(names, I)]
    Bf = vm.field(cs, fixed, bx, 0.0)[1]; Bm = vm.field(cs, mov, bx, 0.0)[1]
    k = (B0-Bf)/Bm if abs(Bm) > 1e-12 else float('inf')
    return k, B0, cs, [i*(k if n in moved else 1.0) for n, i in zip(names, I)]


def self_energy_factor(c0, c1, k):
    """Self-inductance of a thin ring ~ r (ln(8r/a) - 7/4); energy ~ L I^2."""
    L = lambda c: c['r']*(math.log(8*c['r']/c['a'])-1.75)
    return L(c1)/L(c0)*k**2


def coil_sky(s, AU, geom):
    """Burn-sky share of all six coil cryostats (vertex_source.band, the 1.6B rule), with per-coil overrides of x and r."""
    out = {}; bx = BURN(s)
    for c in AU['coils']:
        o = geom.get(c['name'], {}); x = o.get('x', c['x']); r = o.get('r', c['r'])
        out[c['name']] = vso.band(x-bx, r, c['cryostat'])
    return out


# ---------- 4B: ring carriages -------------------------------------------------------------------------------------------------------

def carriages(s, AU):
    """The carriage loops (L4) slide on the eight cage longerons: their windings stay closed (no joint). Stowed, each nests forward against the loop
    ahead of it with stow_gap_m between cryostats; extended, they move aft. For every stroke: the engine length, the current the moved
    loops need to keep the canon stop field, their stored-energy factor, the exit field, the coil sky and the moved and carriage mass."""
    c = config(s); P = ve.parts(s); coils = {x['name']: x for x in AU['coils']}; vg0 = ve.config(s)['geometry']
    order = [n for n in LOOPS]
    hoops = {p['name'][-2:]: p for p in P if p['name'].startswith('VTX_Cage_Hoop_')}
    stow = {}
    for n in c['carriage_loops']:       # the hoop parks behind the hoop ahead of it; the loop travels with its hoop
        ahead = LOOPS[LOOPS.index(n)-1]
        stow[n] = hoops[ahead]['x']-hoops[ahead]['a']-hoops[n]['a']-c['stow_gap_m']-hoops[n]['x']
    rail_R = max(hoops[n]['R'] for n in c['carriage_loops'])
    rail = dict(radius_m=rail_R, from_x=min(hoops[LOOPS[LOOPS.index(n)-1]]['x'] for n in c['carriage_loops']),
                to_x=min(hoops[n]['x'] for n in c['carriage_loops']),
                reshaped={LOOPS[LOOPS.index(n)-1]: dict(hoop_R_m=hoops[LOOPS[LOOPS.index(n)-1]]['R'], new_R_m=rail_R) for n in c['carriage_loops']},
                envelope_change_m=max(rail_R+vg0['cage_longeron_radius_m']-AU['envelope']['max_radius_m'], 0.0))
    collar = min(x for p in P if p['name'] == 'VTX_Thrust_Collar' for x, _ in p['profile'])
    arm_factor = {n: (coils[n]['x']+stow[n]-collar)/(coils[n]['x']-collar) for n in c['carriage_loops']}
    vg = ve.config(s)['geometry']; arm = vg['armour_offset_m']+vg['armour_minor_m']
    aft = lambda dx: min(coils[n]['x']+dx.get(n, 0.0)-coils[n]['cryostat']-arm for n in LOOPS)
    aft0 = aft({})
    moved_kg = {n: sum(_mass(s, p) for p in P if ring_members(n)(p['name'])) for n in c['carriage_loops']}
    moved_tris = {n: sum(_tris(p) for p in P if ring_members(n)(p['name'])) for n in c['carriage_loops']}
    moved_parts = {n: sorted(p['name'] for p in P if ring_members(n)(p['name'])) for n in c['carriage_loops']}
    moved_objects = {n: len({(p['category'], p['material']) for p in P if ring_members(n)(p['name'])}) for n in c['carriage_loops']}
    sky0 = coil_sky(s, AU, {}); I0 = _currents(AU); cs0 = vm.coil_set(s); B_exit0 = vm.field(cs0, I0, coils['L4']['x'], 0.0)[1]
    rows = []
    cases = [('STOWED', stow)]+[('CANON', {n: 0.0 for n in c['carriage_loops']})]+[(f'EXTEND_{d:g}', {n: d*(-1.0) for n in c['carriage_loops']}) for d in c['extend_m']]
    for label, dx in cases:
        geom = {n: dict(x=coils[n]['x']+dx[n]) for n in c['carriage_loops']}
        k, B0, cs, I = hold(s, AU, geom, set(c['carriage_loops']))
        sky = coil_sky(s, AU, geom)
        E = sum(self_energy_factor(dict(r=coils[n]['r'], a=coils[n]['winding']), dict(r=coils[n]['r'], a=coils[n]['winding']), k)
                * next(r['energy_J'] for r in AU['field']['rows'] if r['name'] == n) for n in c['carriage_loops'])
        E0 = sum(next(r['energy_J'] for r in AU['field']['rows'] if r['name'] == n) for n in c['carriage_loops'])
        rows.append(dict(case=label, stroke_m={n: dx[n] for n in c['carriage_loops']}, current_factor=k,
                         stored_moved_factor=E/E0, B_burn_T=vm.field(cs, I, BURN(s), 0.0)[1],
                         B_exit_T=vm.field(cs, I, coils['L4']['x']+dx.get('L4', 0.0), 0.0)[1], B_exit_canon_T=B_exit0,
                         coil_sky=sum(sky.values()), coil_sky_factor=sum(sky.values())/sum(sky0.values()),
                         moved_sky={n: sky[n] for n in c['carriage_loops']}, length_m=AU['envelope']['length_m']+(aft0-aft(dx))))
    total = sum(moved_kg.values())
    stroke = max(abs(v) for v in stow.values())
    return dict(loops=c['carriage_loops'], stow_stroke_m=stow, rail=rail, bending_arm_factor=arm_factor, rows=rows, moved_kg=moved_kg, moved_total_kg=total, moved_tris=moved_tris,
                moved_parts=moved_parts, moved_objects=moved_objects, carriage_kg=[total*x for x in c['carriage_share']],
                travel_s=stroke/c['carriage_speed_m_s'],
                rails='the eight cage longerons are conical today (a fixed ring cannot slide on them); their aft segments between the L3 and L4 '
                      'hoops become cylindrical rails at the L4 hoop radius, the L3 hoop grows to that radius, and the L4 loop seats become rail shoes',
                services='lead and cryogen branches and the lithium jumpers become flexible festoon lines over the stroke (or, with C2 dynamos, '
                         'the lead branches go away)',
                evidence='FIELD_SOLVED (thin-filament axisymmetric coil set, vertex_magnet); capture and detachment with moved loops OPEN')


# ---------- alignment ---------------------------------------------------------------------------------------------------------------

def alignment(s, AU):
    """A loop displaced sideways by d gives a transverse field at the burn B_perp ~ (d/2) dB_x,loop/dx (axisymmetric expansion,
    B_rho = -(rho/2) dB_x/dx); the field direction there tilts by B_perp/B, and so would the exhaust it guides. For each loop and each
    survey state: the tilt and the side force it would put on the canon thrust if the plume followed the tilted field."""
    c = config(s); cs = vm.coil_set(s); I = _currents(AU); bx = BURN(s); B0 = vm.field(cs, I, bx, 0.0)[1]
    thrust = AU['loads'].get('thrust_mission_N') or vd.audit(s)['loads']['thrust_mission_N']
    h = 1e-3; rows = []
    for j, cc in enumerate(cs):
        only = [i if k == j else 0.0 for k, i in enumerate(I)]
        dBdx = (vm.field(cs, only, bx+h, 0.0)[1]-vm.field(cs, only, bx-h, 0.0)[1])/(2*h)
        per_m = abs(dBdx)/2
        rows.append(dict(name=cc['name'], dBx_dx_T_m=dBdx, B_perp_T_per_mm=per_m*1e-3,
                         tilt_rad=[per_m*d/B0 for d in c['alignment_offset_m']],
                         side_force_N=[thrust*per_m*d/B0 for d in c['alignment_offset_m']]))
    worst = max(rows, key=lambda r: r['B_perp_T_per_mm'])
    return dict(rows=rows, offsets_m=c['alignment_offset_m'], B_burn_T=B0, thrust_N=thrust, worst=worst['name'],
                note='Field errors of this kind are why fusion magnets are surveyed and aligned to millimetres; the carriages are the '
                     'actuators that close that loop in state 3. Whether the plume follows the field tilt one-for-one is OPEN (detachment).',
                evidence='FIELD_SOLVED (axisymmetric first-order error field); plume response OPEN')


# ---------- 4A: petals and superconducting joints ------------------------------------------------------------------------------------

def petals(s, AU, DY):
    """A petal that opens a loop cuts its winding at every petal boundary; each turn needs a demountable joint there. The joints dissipate
    I^2 R at 20 K (lifted to the radiators by the cryocooler factor 1.7 used for the leads) and make the persistent current decay with
    tau = L/R. For the inner-loop petals of Concept B (inside today's envelope) and the all-loop petals of Concept C (at the clearance
    limit): sky, current, stored energy, joints, heat and decay, and the joint resistance persistent mode would need."""
    c = config(s); coils = {x['name']: x for x in AU['coils']}; rows_f = {r['name']: r for r in AU['field']['rows']}
    I_lead = AU['field']['lead_current_A']; burn_s = s['vertex_dynamic'].get('burn_s') or 10*86400.0
    lead = DY['dynamo']['leads'][NOM]; lift = lead['radiator_W']/lead['cold_W']
    vg = ve.config(s)['geometry']; outer = AU['envelope']['max_radius_m']
    def arm(n):
        return coils[n]['cryostat']+vg['armour_offset_m']+vg['armour_minor_m']
    rmax_env = {n: outer-arm(n) for n in LOOPS}
    kmax = (AU['cluster']['adjacent_m']-AU['cluster']['maintenance_m'])/2/outer
    cases = [('B_INNER', {n: rmax_env[n] for n in c['inner_loops']}),
             ('C_ALL_1.2', {n: coils[n]['r']*1.2 for n in LOOPS}),
             ('C_ALL_KMAX', {n: coils[n]['r']*kmax for n in LOOPS})]
    sky0 = coil_sky(s, AU, {}); out = []
    for label, rr in cases:
        geom = {n: dict(r=r) for n, r in rr.items()}; moved = set(rr)
        k, B0, cs, I = hold(s, AU, geom, moved); sky = coil_sky(s, AU, geom)
        E0 = sum(rows_f[n]['energy_J'] for n in moved)
        E1 = sum(self_energy_factor(dict(r=coils[n]['r'], a=coils[n]['winding']), dict(r=rr[n], a=coils[n]['winding']), k)*rows_f[n]['energy_J'] for n in moved)
        joints = sum(c['petal_boundaries']*rows_f[n]['turns'] for n in moved)
        jrows = []
        for R in c['joint_ohm']:
            cold = joints*I_lead**2*R
            tau = 2*E1/(I_lead**2*joints*R)
            jrows.append(dict(joint_ohm=R, cold_W=cold, radiator_W=cold*lift, tau_s=tau, burn_decay=1-math.exp(-burn_s/tau),
                              persistent_ok=(1-math.exp(-burn_s/tau)) <= c['persistent_decay_max']))
        R_need = 2*E1/(I_lead**2*joints*(-burn_s/math.log(1-c['persistent_decay_max'])))
        env_after = max(outer, max(rr[n]+arm(n) for n in rr))
        out.append(dict(case=label, radii_m=rr, current_factor=k, stored_moved_factor=E1/E0, coil_sky=sum(sky.values()),
                        coil_sky_factor=sum(sky.values())/sum(sky0.values()), joints=joints, joint_rows=jrows, joint_ohm_needed=R_need,
                        envelope_m=env_after, envelope_factor=env_after/outer, fits=env_after <= outer*kmax+1e-9,
                        strain_if_continuous=max(rr[n]/coils[n]['r']-1 for n in rr)))
    return dict(rows=out, k_max=kmax, rmax_in_envelope=rmax_env, lift=lift, lead_current_A=I_lead, burn_s=burn_s,
                rebco_strain_limit=c['rebco_strain_limit'],
                continuous_radial_limit_m={n: coils[n]['r']*c['rebco_strain_limit'] for n in LOOPS},
                note='A closed REBCO ring cannot change radius by more than its strain limit (centimetres), so every petal that moves a winding '
                     'needs joints. 1.7 C3 did not count them.',
                evidence='SCALING_ESTIMATE (filament field solved, joints by I^2 R and L/R; joint resistances LITERATURE class)')


# ---------- 4E: Fiji ---------------------------------------------------------------------------------------------------------------

def fiji(s):
    F = _j(va.EVIDENCE_PATH); M = {r['id']: r for r in F['matrix']}
    pick = ['FG-0/FM-1/SEEDED', 'FG-5/FM-1/SEEDED', 'FG-5/FM-1/ORIENTED', 'FG-2/FM-1/SEEDED', 'FG-2/FM-1/ORIENTED']
    rows = [dict(id=i, geometry=F['geometries'][M[i]['geometry']]['name'], mode=M[i]['mode'], share_of_stop=M[i]['share_of_stop'],
                 mass_engine_kg=M[i]['mass_engine_kg'], line_of_sight=F['geometries'][M[i]['geometry']]['line_of_sight']) for i in pick if i in M]
    return dict(rows=rows,
                rule='One property (canon, 1.6A): the lattice follows the applied field inside its 550-1400 K window. Moving it changes where it '
                     'sits in the field, not what it can do. In the shield shadow (FG-5) it adds 0.3 % of the stop field for ~700 t per engine; '
                     'the existing liner adds nothing measurable. A visible field-shaping role needs the coercive orientation (SP-17C).',
                display='lattice_activation stays a thermal-state and readiness indicator (activation glow from 650 K); no animation shows the '
                        'lattice bending the field.', evidence='REUSED 1.6A REDUCED_MODEL')


# ---------- 13: concepts ------------------------------------------------------------------------------------------------------------

def concepts(s, AU, CA, PE, DY, AL):
    """Four concepts with the same columns. Masses per engine; nominal brackets."""
    c = config(s); n_coils = len(AU['coils']); T = DY['tread']; boot = DY['dynamo']['startup'][NOM]['mass_kg']['flywheel']/4
    car = CA['carriage_kg'][NOM]; dyn = n_coils*(c['dynamo_kg']+c['switch_kg']); trim = c['trim_coil_kg']
    lead_saved = DY['dynamo']['leads'][NOM]['radiator_W']
    canon = next(r for r in CA['rows'] if r['case'] == 'CANON'); stowed = next(r for r in CA['rows'] if r['case'] == 'STOWED')
    B = next(r for r in PE['rows'] if r['case'] == 'B_INNER'); Cc = next(r for r in PE['rows'] if r['case'] == 'C_ALL_1.2')
    jB = B['joint_rows'][NOM]; jC = Cc['joint_rows'][NOM]
    hinge = s['vertex_dynamic']['hinge_share'][NOM]
    cat = vd.audit(s)['mass']['by_category']
    loopB_kg = sum(_mass(s, p) for p in ve.parts(s) if any(ring_members(n)(p['name']) for n in c['inner_loops']))
    rings = sum(CA['moved_objects'].values()); petal_objs = 8*2      # one object per petal per material (cryostat shell, armour)
    loopC_kg = cat['MAGNETIC_NOZZLE']+cat['STRUCTURE']
    def row(cid, title, parts, mass, env, length, sky, heat, joints, objs, sps, level, motion, fail, compat, anim, visual):
        return dict(id=cid, title=title, parts=parts, added_kg=mass, added_four_kg=4*mass, fits_margin=4*mass <= AU['mass']['margin_kg'],
                    fits_without_flywheel=4*(mass-boot) <= AU['mass']['margin_kg'], flywheel_share_kg=boot,
                    envelope_m=env, stowed_length_m=length, coil_sky_factor=sky, cold_heat_W=heat, joints=joints, moving_objects=objs,
                    speculative=sps, evidence=level, motion=motion, failures=fail, compatibility=compat, animation=anim, visual=visual)
    A = row('A', 'Minimal Adaptive Vertex',
            ['L4 ring carriage on straightened aft longeron rails (stow, operate); actuated loop seats on L1-L3 (millimetre alignment)', 'six HTS dynamos and persistent switches at the lead turrets',
             'shared ignition flywheel at the cluster hub', 'trim coils at L3/L4 (electronic)', 'field and diagnostic view modes'],
            car+dyn+trim+boot, AU['envelope']['max_radius_m'], stowed['length_m'], canon['coil_sky_factor'], -DY['dynamo']['leads'][NOM]['cold_W'], 0,
            rings+n_coils, [], 'level 1-2 (carriages, dynamos, persistent mode, trim coils all exist in kind)',
            'L4 telescopes aft before the field, seats trim by millimetres, rotors spin only during field formation',
            ['F-CARRIAGE (a ring jams or a lock fails: burn inhibited, field not raised)', 'F-ALIGN (alignment not reached: plasma calibration held)',
             'F-DYNAMO', 'F-QUENCH', 'F-TRIM (trim supply lost: bounded steering error)'],
            'reuses every existing loop, hoop, seat and longeron; splits two object families', 'rigid transforms only', 'moderate: the nozzle visibly extends')
    Bm = car+dyn+trim+boot+hinge*loopB_kg+T['added_kg']
    Bc = row('B', 'Bloom Vertex (compact)',
             ['A', 'L1/L2 open as eight petals each inside today\'s envelope (demountable joints)', 'armour treads on C2, L1, L2 (1.7 C4)',
              'startup shutters over the treads\' service ports'],
             Bm, B['envelope_m'], stowed['length_m'], B['coil_sky_factor'], jB['cold_W'], B['joints'],
             rings+n_coils+2*petal_objs+3, ['SP-18A (persistent demountable joints) or keep L1/L2 on leads'],
             'level 2 (demountable HTS joints exist at nOhm class; persistent operation through them does not)',
             'A plus petals swing open, treads circulate during the burn',
             A['failures']+['F-PETAL (latch)', 'F-JOINT (a joint warms: local quench)', 'F-TREAD (12 ms to tile failure)'],
             'splits L1/L2 windings (redesign), adds tread tracks', 'rigid transforms; tread tiles instanced', 'strong: the engine opens')
    Cm = car+dyn+trim+boot+hinge*loopC_kg+T['added_kg']*2+vd._j(vd.EVIDENCE_PATH)['petals']['coil_loop_kg']*(1.2**0.5-1)
    Cc_ = row('C', 'Integrated Adaptive Vertex',
              ['all four loops on articulated petals (k 1.2)', 'segmented Fiji lattice carriers on the petals', 'treads on every lit cryostat',
               'carriages, dynamos, flywheel, trim coils', 'per-petal actuators under continuous AI trim'],
              Cm, Cc['envelope_m'], stowed['length_m'], Cc['coil_sky_factor'], jC['cold_W'], Cc['joints'], rings+n_coils+4*petal_objs+8+6,
              ['SP-18A (persistent demountable joints)', 'SP-17C (Fiji coercive orientation) for any lattice role'],
              'level 3 (joints at the needed resistance and an oriented lattice are both beyond known materials)',
              'everything articulates; petals trim during the burn',
              Bc['failures']+['F-LATTICE (a carrier misaligns: field error)', 'F-SYNC-PETAL (petals out of step)'],
              'replaces the nozzle loops, cage and armour', 'rigid transforms, many nodes', 'maximal')
    Ap = row('A_PLUS', 'Recommended: Adaptive Vertex A+ (A with B\'s visible startup machinery)',
             A['parts']+['maintenance petals: cryostat and armour shells of L1/L2 open for service only (windings stay closed)',
                         'engineering view modes: field lines, plasma flow, energy, thermal, control, synchronization'],
             A['added_kg'], A['envelope_m'], A['stowed_length_m'], A['coil_sky_factor'], A['cold_heat_W'], 0,
             A['moving_objects']+2*petal_objs, [], A['evidence'], A['motion']+'; service petals open only when the engine is cold and the field is down',
             A['failures']+['F-PETAL-SERVICE (a shell not latched: field formation inhibited)'], A['compatibility']+'; splits the L1/L2 cryostat family',
             'rigid transforms; per-state pose table', 'strong at startup and in service, honest during the burn')
    return dict(rows=[A, Bc, Cc_, Ap], lead_heat_removed_radiator_W=lead_saved,
                note='Masses per engine. A+ adds no joint and no tread; its service petals are shells, not field hardware, so they add hinge '
                     'mass only where a service opening is wanted (counted as zero here; a design choice for Phase F).')


def scores(CO):
    """Qualitative ranking 1 (worst) to 5 (best) on the brief's nine criteria, each with its reason from the numbers."""
    crit = ['credibility', 'mechanical_function', 'mass', 'thermal', 'compatibility', 'animation', 'browser', 'distinctiveness', 'maintenance']
    table = {
        'A': [5, 4, 4, 4, 5, 4, 5, 3, 4],
        'B': [3, 4, 2, 3, 3, 3, 3, 5, 2],
        'C': [1, 5, 1, 2, 1, 2, 2, 5, 1],
        'A_PLUS': [5, 4, 4, 4, 5, 4, 4, 4, 5],
    }
    return dict(criteria=crit, scores=table, totals={k: sum(v) for k, v in table.items()},
                basis='judgement from the concept rows: joints, treads and petals cost credibility, mass and maintenance; A+ adds service '
                      'petals that open only cold, which helps maintenance and startup visuals without touching the field')


# ---------- 6: nine-state sequence --------------------------------------------------------------------------------------------------

PROPOSED = {
    'nozzle_deployment': 'ring carriage position: 0 stowed, 1 canon operating position (A+); per engine',
    'field_ring_trim': 'alignment trim of the L4 carriage: 0 coarse survey error, 1 aligned within tolerance; per engine',
    'induction_rotor_speed': 'HTS dynamo rotor speed: 0 still, 1 charging, -1 discharging; per engine',
    'service_petals': 'L1/L2 cryostat and armour shells: 0 closed, 1 open for service (cold, field down only)',
    'ai_optimization_state': 'convergence display: 0 untrained guess, 1 converged (drives diagnostic overlays only)',
    'plasma_stability': 'display of the calibration residual: 0 unstable, 1 locked',
    'thermal_load': 'display share of the drive heat allowance (0..1, above 1 flagged)',
    'vertex_lock': 'all locks engaged, alignment and plasma in tolerance: 0/1',
    'fault_code': 'none, F-CARRIAGE, F-ALIGN, F-DYNAMO, F-QUENCH, F-LATTICE-HOT, F-THERMAL, F-ASYM, F-TRIM, F-PETAL-SERVICE',
}


def sequence(s, CA, DY, AU):
    c = config(s); P = DY['dynamo']; ramp = max(r['ramp_s'] for r in AU['field']['rows'])
    charge = [r['hours']*3600 for r in P['dynamo_charge']]
    S = [
        (1, 'DORMANT', 'OFF', None, 'Rings stowed and locked forward, rotors still, coils at zero, petals shut.',
         dict(nozzle_deployment=0, induction_rotor_speed=0, manifold_field_strength=0, nozzle_field_strength=0, lattice_activation=0, drive_active=0)),
        (2, 'MECHANICAL_PREPARATION', 'OFF', CA['travel_s'], 'Locks release; L4 runs aft on the rails to its operating station; service lines pay out; locks engage; dynamo rotors spin up.',
         dict(nozzle_deployment=1, induction_rotor_speed=1, manifold_field_strength=0, nozzle_field_strength=0)),
        (3, 'DIGITAL_ALIGNMENT', 'OFF', 3600.0, 'Metrology scans the loops; carriages trim position and tilt from the as-stowed error to the fine tolerance; the AI checks clearances, locks and the predicted field.',
         dict(nozzle_deployment=1, field_ring_trim=1, ai_optimization_state=0.4)),
        (4, 'FIELD_FORMATION', 'PRE_IGNITION', charge[0], f'Dynamos pump the coils to the stop field ({charge[0]/3600:.0f}-{charge[1]/3600:.0f} h at 1-0.1 V), persistent switches close, rotors stop; the lattice is heated through activation to its operating point.',
         dict(manifold_field_strength=1, induction_rotor_speed=0, lattice_activation=0.6, magnetic_field_debug=1)),
        (5, 'PLASMA_CALIBRATION', 'IGNITION_PULSE', 600.0, 'Low-power test pulses; trim coils adjust the topology; the AI compares the predicted and measured plume and converges.',
         dict(drive_active=0.2, laser_A_power=0.3, laser_B_power=0.3, nozzle_field_strength=0.3, plasma_stability=0.5, ai_optimization_state=0.7)),
        (6, 'FIRST_IGNITION', 'IGNITION_PULSE', 60.0, 'The bootstrap flywheel feeds the first driver pulses; the burn starts; exhaust appears.',
         dict(drive_active=0.5, laser_A_power=0.5, laser_B_power=0.5, lattice_activation=1, nozzle_field_strength=0.6, plasma_stability=0.8)),
        (7, 'VERTEX_LOCK', 'SUSTAINED', 30.0, 'All locks and the alignment in tolerance, calibration residual below the threshold: lock indicators close round each engine, then across the four.',
         dict(vertex_lock=1, plasma_stability=1, ai_optimization_state=1, drive_active=1, nozzle_field_strength=1)),
        (8, 'SUSTAINED_MODULATION', 'SUSTAINED', 10*86400.0, 'Pulse rate and flux shares follow the throttle; trim coils steer; only the plume, the diagnostics and the four-engine balance change.',
         dict(drive_active=1, nozzle_field_strength=1, thrust_level=1, thermal_load=1)),
        (9, 'SHUTDOWN_OR_FAILURE', 'SHUTDOWN', ramp, 'Pulses stop; coils stay persistent or ramp down by the dynamos run backwards; after cool-down the rings stow. A fault ends in its own trip.',
         dict(drive_active=0, nozzle_field_strength=0.5, manifold_field_strength=0.5, induction_rotor_speed=-1, nozzle_deployment=0)),
    ]
    faults = [
        dict(code='F-CARRIAGE', subsystem='ring carriage', cue='one ring stops short of its station; its lock lamp stays amber', response='field formation inhibited; ring retracted and inspected'),
        dict(code='F-ALIGN', subsystem='alignment', cue='the alignment readout does not converge; field preview shows a tilted plume line', response='plasma calibration held'),
        dict(code='F-QUENCH', subsystem='coil', cue='cryostat vent plume and frost on one coil; its field lines collapse', response='engine trip; the cluster rebalances on three engines'),
        dict(code='F-LATTICE-HOT', subsystem='Fiji lattice', cue='lattice glow shifts towards white and fades as its response falls above 1300 K', response='throttle down; trim coils take over'),
        dict(code='F-THERMAL', subsystem='thermal', cue='thermal mode shows the radiator load bar above its line', response='throttle down to the radiator allowance'),
        dict(code='F-ASYM', subsystem='plume', cue='the plume bends and touches one side of the cage in the plasma mode', response='trip; one engine off'),
        dict(code='F-DYNAMO', subsystem='induction', cue='a rotor stops during charging; its current bar stalls', response='charging paused; spare dynamo or leads'),
        dict(code='F-PETAL-SERVICE', subsystem='service petal', cue='a shell not latched: amber latch lamp', response='field formation inhibited'),
    ]
    return dict(states=[dict(n=n, state=k, maps_to=m, duration_s=t, description=d, values=v) for n, k, m, t, d, v in S], faults=faults,
                proposed_properties=PROPOSED, reused_properties=list(dm.PROPS)+list(dm.SAVED_SETTINGS),
                display_time='The viewer compresses time per state and shows the physical duration beside it; nothing pretends field formation takes seconds.')


# ---------- 7: field lines --------------------------------------------------------------------------------------------------------

def field_lines(s, AU, geom=None, n=None, pts=None, I=None):
    """Field lines in the (x, rho) half-plane of one engine, seeded across the burn plane inside the L2 bore and traced both ways along the
    field (RK4 on the unit direction, one consistent sense per half): aft until past the exit, forward until the shield face, a turn-back
    (the C1/C2 cusp) or the edge of the drawing. For the field view mode and the figure; a display of the vacuum field, not of the plasma."""
    c = config(s); n = n or c['field_lines']; pts = pts or c['field_line_points']; cs = vm.coil_set(s, geom); I = I or _currents(AU)
    g = vd.audit(s)['geometry']; bx = g['burn_x']; x_fwd = g['shield_aft_x']; x_end = AU['exit_x']-12.0
    L2 = next(x for x in AU['coils'] if x['name'] == 'L2'); r_top = L2['r']-L2['cryostat']-0.4
    h = (x_fwd-x_end)/pts
    def unit(x, r):
        br, bx_ = vm.field(cs, I, x, r); m = math.hypot(br, bx_) or 1.0
        return bx_/m, br/m
    def trace(x, r, sense):
        out = []; first = None
        for _ in range(3*pts):
            f = lambda xx, rr: tuple(sense*v for v in unit(xx, rr))
            k1 = f(x, r); k2 = f(x+h*k1[0]/2, r+h*k1[1]/2); k3 = f(x+h*k2[0]/2, r+h*k2[1]/2); k4 = f(x+h*k3[0], r+h*k3[1])
            dx = h*(k1[0]+2*k2[0]+2*k3[0]+k4[0])/6; dr = h*(k1[1]+2*k2[1]+2*k3[1]+k4[1])/6
            first = first if first is not None else math.copysign(1.0, dx)
            if math.copysign(1.0, dx) != first and abs(dx) > 0.2*h:
                break
            x += dx; r = abs(r+dr); out.append((round(x, 3), round(r, 3)))
            if x < x_end or x > x_fwd or r > 16.0:
                break
        return out
    lines = []
    for i in range(n):
        r0 = r_top*(i+0.5)/n
        a = unit(bx, r0); aft = -1.0 if a[0] > 0 else 1.0          # the sense that heads aft (-x) from the burn plane
        lines.append(list(reversed(trace(bx, r0, -aft)))+[(bx, round(r0, 3))]+trace(bx, r0, aft))
    return lines


# ---------- 11: browser --------------------------------------------------------------------------------------------------------------

def browser(s, AU, CA, CO, FL):
    c = config(s); node_kB = 0.43
    rows = []
    for r in CO['rows']:
        objs = r['moving_objects']
        states = 9
        pose_bytes = 4*objs*states*c['state_bytes_per_node']
        rows.append(dict(id=r['id'], moving_objects_per_engine=objs, nodes_four=4*objs, draw_calls_added=4*objs,
                         pose_table_bytes=pose_bytes, play_package_kB=4*objs*node_kB))
    fl_bytes = sum(len(l) for l in FL)*2*4*4      # Float32 (x, rho), 4 engines share one set: x4 for 4 state variants
    return dict(rows=rows, field_line_bytes=fl_bytes, viewer_headroom_bytes=c['viewer_budget_bytes']-c['viewer_used_bytes'],
                engine_tris=AU['tris'], moved_tris=CA['moved_tris'],
                method=['rigid transforms only (no deformation, no skinning, no morph targets)',
                        'one shared mesh per moving part type, one node per engine (the effect-object pattern), so download grows by nodes, not meshes',
                        'a per-state pose table (JSON) interpolated in JS in the viewer, as effect_states already is for opacities; no glTF animation channels',
                        'field lines: precomputed polylines per state drawn as one line batch; plasma flow: a dash-offset shader along the same lines',
                        'diagnostic overlays (control, energy, thermal, sync) as HTML/canvas panels, not 3D geometry',
                        'view modes switch layers on and off; the default exterior view shows hardware and plume only',
                        'tread tiles (if ever used) instanced; dynamo rotors instanced'],
                caution='Draw calls today: 5,241 in the default exterior view (Vertex 1.2 evidence). Every number here is an estimate; frame time is '
                        'measured in Phase F on the viewer (evidence class SW in the cloud, HW on a real GPU) before anything ships.')


# ---------- 12: engineering consistency -------------------------------------------------------------------------------------------

def consistency(s, CA, AL, PE, DY, FJ):
    canon = next(r for r in CA['rows'] if r['case'] == 'CANON'); stow = next(r for r in CA['rows'] if r['case'] == 'STOWED')
    ext = next(r for r in CA['rows'] if r['case'].startswith('EXTEND_4'))
    al = next(r for r in AL['rows'] if r['name'] == AL['worst']); B = next(r for r in PE['rows'] if r['case'] == 'B_INNER')
    lead = DY['dynamo']['leads']; rot = DY['dynamo']['dynamo_charge']
    return [
        dict(mechanism='L4 ring carriage', purpose='stow the nozzle short when cold (shorter cantilever); set the operating station; align L4',
             speculative='none', problem='alignment and field quality; service access; none of the six open problems',
             benefit=f'stowed engine {stow["length_m"]:.1f} m instead of {canon["length_m"]:.1f} m; extending 4 m aft changes the coil sky x{ext["coil_sky_factor"]:.3f} '
                     f'and needs x{ext["current_factor"]:.2f} current in the moved loops: no thermal benefit',
             mass=f'{CA["carriage_kg"][NOM]/1e3:.0f} t carriage gear per engine (nominal) on {CA["moved_total_kg"]/1e3:.0f} t moved',
             how='axial slide on the eight longerons; small tilt from differential drive', when='states 2, 3 and 9, field down only',
             limits='never moves with current in the coils (loads of hundreds of MN)', failures='F-CARRIAGE, F-ALIGN'),
        dict(mechanism='Alignment loop (metrology + carriages + AI)', purpose='bring loop offsets from centimetres to sub-millimetre',
             speculative='AI quality is fiction-level, the physics is not', problem='thrust-vector error and plume asymmetry (F-ASYM)',
             benefit=f'{AL["worst"]} offset 10 mm tilts the burn field by {al["tilt_rad"][0]*1e3:.2f} mrad ({al["side_force_N"][0]/1e3:.0f} kN side force on the canon thrust); '
                     f'0.5 mm: {al["tilt_rad"][2]*1e3:.3f} mrad ({al["side_force_N"][2]/1e3:.1f} kN)',
             mass='metrology heads only', how='scan, compute, trim', when='state 3, re-checked in 5 and 7', limits='plume response to field tilt OPEN',
             failures='F-ALIGN'),
        dict(mechanism='HTS dynamos and persistent switches', purpose='charge the coils without current leads; then stand still',
             speculative='none (level 2 at 68 kA)', problem='magnetic hardware heat',
             benefit=f'removes {lead[NOM]["radiator_W"]/1e6:.1f} MW of lead heat at the radiators per engine (nominal)',
             mass='~11 t per engine (PROTOTYPE)', how='rotor spin', when=f'state 4 ({rot[0]["hours"]:.0f}-{rot[1]["hours"]:.0f} h), reversed in 9',
             limits='slow by nature; persistent mode decays only through joints', failures='F-DYNAMO, F-QUENCH'),
        dict(mechanism='Ignition flywheel (shared)', purpose='deliver the first driver pulses before the burn feeds itself',
             speculative='driver efficiency and target gain OPEN (SP-17D)', problem='fusion driver power at start only',
             benefit='10 pulses at 1 Hz (1.7)', mass='58 t for the cluster', how='spin-up, discharge', when='states 2 to 6', limits='cannot carry the sustained driver load',
             failures='F-OVERSPEED (contained), F-DRIVER'),
        dict(mechanism='Trim coils (electronic)', purpose='fast field shaping and steering', speculative='none', problem='plume shape, steering',
             benefit='the fast layer that motion cannot be', mass='4 t per engine (PROTOTYPE)', how='current only', when='states 5 to 8',
             limits='normal-conducting: ohmic heat', failures='F-TRIM'),
        dict(mechanism='Service petals (A+)', purpose='open the L1/L2 cryostat and armour shells for inspection and tile exchange',
             speculative='none', problem='maintainability', benefit='no performance claim', mass='hinges only where a service opening is wanted',
             how='shell segments swing on the existing joint flanges', when='cold, field down (dormant/service)', limits='never with current in the coils',
             failures='F-PETAL-SERVICE'),
        dict(mechanism='Field petals (B/C)', purpose='move windings outward to cut the coil sky', speculative='SP-18A persistent demountable joints',
             problem='magnetic hardware survival (sky)',
             benefit=f'inner loops to the envelope: coil sky x{B["coil_sky_factor"]:.3f}; at 10 nOhm {B["joint_rows"][NOM]["radiator_W"]/1e6:.0f} MW radiator and a {B["joint_rows"][NOM]["tau_s"]/3600:.0f} h decay',
             mass='hinges and joints', how='petal swing', when='state 2', limits='persistent mode needs < {:.1e} Ohm per joint'.format(B['joint_ohm_needed']),
             failures='F-PETAL, F-JOINT'),
        dict(mechanism='Armour treads (B/C)', purpose='spread the peak heat', speculative='none', problem='local face flux only',
             benefit='peak /pi (1.7); total heat unchanged', mass='151 t per engine', how='poloidal circulation', when='states 6 to 9',
             limits='a stopped tread gives ~12 ms before tile failure', failures='F-TREAD'),
        dict(mechanism='Fiji lattice', purpose='bounded thermomagnetic element (canon)', speculative='SP-17C for any field-shaping role',
             problem='none of the six (1.6A)', benefit=FJ['rule'], mass='as built', how='heats, glows', when='state 4 onward', limits='550-1400 K',
             failures='F-LATTICE-HOT'),
    ]


# ---------- 14: roadmap -------------------------------------------------------------------------------------------------------------

def roadmap(s, CA):
    return dict(
        steps=[
            dict(step=1, what='Owner decisions: concept, SP-18A status, Phase F go', files=[]),
            dict(step=2, what='Pure geometry: carriage stations (stowed, canon) and service-petal hinge axes as parameters; motion limits as functions',
                 files=['data/wayfarer_3d.toml [vertex_engine.geometry] (new keys)', 'src/wayfarer/vertex_engine.py parts(), stations()']),
            dict(step=3, what='Split the moving groups out of the merged families: the L4 ring (coil, cryostat, structure, armour, hot), the L1/L2 cryostat shells',
                 files=['src/wayfarer/vertex_engine.py families() (a moving-group key)']),
            dict(step=4, what='Per-engine moving objects in the cluster sharing one mesh each, parented at the engine placement (the effect-object pattern); '
                              'the static engine instance keeps everything else',
                 files=['src/wayfarer/components/vertex.py cluster()', 'src/wayfarer/vertex_cluster.py (moving_objects(), drivers())']),
            dict(step=5, what='Controller: the proposed properties on DRIVE_MANIFOLD_CTRL, per-engine where needed; drivers for location/rotation; nine STATES',
                 files=['src/wayfarer/drive_manifold.py PROPS', 'src/wayfarer/vertex_cluster.py STATES, drivers()', 'src/wayfarer/components/drive.py build_actions()']),
            dict(step=6, what='Root machinery parts: dynamo housings and rotors at the six lead turrets, persistent-switch boxes, flywheel at the hub',
                 files=['src/wayfarer/vertex_engine.py parts()', 'src/wayfarer/vertex_cluster.py distribution()']),
            dict(step=7, what='Review file WORK_VTX18 with the nine states as markers and cameras (Phase F)', files=['work/vertex-1-8/ (study script)']),
            dict(step=8, what='Inspection: clearance and motion-limit checks for every pose (ring overlap, lock positions, envelope)',
                 files=['src/wayfarer/inspect.py (drive group)', 'tests/test_vertex_adaptive.py']),
            dict(step=9, what='Export: per-state pose table and field-line polylines next to the GLB; web viewer interpolation and view modes',
                 files=['src/wayfarer/export/godot.py', 'tools/web_export.py', 'web/viewer/viewer.js']),
            dict(step=10, what='Measure: draw calls, frame time, download before and after on the same views (GFX method)', files=['docs/WEB_GRAPHICS.md record']),
        ],
        classes=dict(
            reused=['all four loops, windings, cryostat segments and joint flanges', 'cage longerons (as rails)', 'cage hoops L3/L4 (as carriage rings)',
                    'loop seats L3/L4 (as rail shoes)', 'C1/C2 and their struts', 'shield, armour', 'effect objects and their drivers', 'DRIVE_MANIFOLD_CTRL'],
            modified=['VTX_MAGNETIC_NOZZLE_* and VTX_SHIELDING_armour, VTX_STRUCTURE_structure, VTX_HOT_THERMAL_hot families (split by moving group)',
                      'lead and cryogen branches, lithium jumpers of L4 (flexible festoon form)', 'vertex_cluster.STATES (5 -> 9)'],
            new=['HTS dynamo housings and rotors (6 per engine)', 'persistent-switch boxes', 'carriage drive and lock blocks (8 per ring)',
                 'shared flywheel at the hub', 'trim coil sets at L3/L4', 'service-petal hinge blocks on L1/L2'],
            animation_only=['ring translation and tilt', 'rotor spin', 'service petal swing', 'lock pins', 'flywheel spin'],
            shader_only=['field-line view mode', 'plasma-flow dashes', 'thermal false colour', 'lock ring indicators', 'control/sync overlays (HTML)']),
        moved_parts=CA['moved_parts'])


# ---------- verdict and report ----------------------------------------------------------------------------------------------------

def verdict(s, CO, PE, CA):
    B = next(r for r in PE['rows'] if r['case'] == 'B_INNER')
    return dict(recommended=config(s)['recommended'],
                statement='Recommend A+: rings that telescope on the existing longerons and align to sub-millimetre, leadless dynamos that spin '
                          'only while the field forms, a shared ignition flywheel, trim coils for the fast layer, service petals that open only '
                          'cold, and engineering view modes for field, plasma, energy, heat, control and synchronization. Field petals are '
                          'not recommended: a petal that moves a winding cuts it, and at 10 nOhm per joint the inner-loop petals alone would '
                          f'dissipate {B["joint_rows"][NOM]["radiator_W"]/1e6:.0f} MW at the radiators and lose persistent current in '
                          f'{B["joint_rows"][NOM]["tau_s"]/3600:.0f} h. No mechanism here closes capture, source radiation, driver power, coil '
                          'survival, mass or thermal closure.',
                speculative=[dict(id='SP-18A', name='Persistent demountable joints', supplies=f'joint resistance below {B["joint_ohm_needed"]:.1e} Ohm at 68 kA',
                                  precedent='demountable REBCO joints reach the nOhm class (fusion magnet R&D)', status='PROPOSED_FOR_AUTHOR_APPROVAL',
                                  needed_by='Concepts B and C only')])


def input_hash(s):
    keys = ['vertex_adaptive', 'vertex_dynamic', 'vertex_engine', 'vertex_cluster', 'drive_manifold', 'propulsion_cluster']
    blob = json.dumps({k: s.get(k) for k in keys}, sort_keys=True, default=str)
    src = b''.join((HERE/f).read_bytes() for f in ('vertex_adaptive.py', 'vertex_engine.py', 'vertex_cluster.py', 'vertex_magnet.py'))
    return hashlib.sha256(blob.encode()+src+vd.EVIDENCE_PATH.read_bytes()+va.EVIDENCE_PATH.read_bytes()).hexdigest()[:16]


def report(s):
    t0 = time.time(); c = config(s)
    AU = audit3d(s); DY = _j(vd.EVIDENCE_PATH)
    AU['loads'] = DY['audit']['loads']
    CA = carriages(s, AU); AL = alignment(s, AU); PE = petals(s, AU, DY); FJ = fiji(s)
    CO = concepts(s, AU, CA, PE, DY, AL); SC = scores(CO); SQ = sequence(s, CA, DY, AU)
    stow = next(r for r in CA['rows'] if r['case'] == 'STOWED')
    geo_stow = {n: dict(x=next(x for x in AU['coils'] if x['name'] == n)['x']+CA['stow_stroke_m'][n]) for n in CA['loops']}
    FL = dict(canon=field_lines(s, AU), stowed=field_lines(s, AU, geo_stow, I=hold(s, AU, geo_stow, set(CA['loops']))[3]))
    BR = browser(s, AU, CA, CO, FL['canon']); CS = consistency(s, CA, AL, PE, DY, FJ); RM = roadmap(s, CA); V = verdict(s, CO, PE, CA)
    AU.pop('loads', None)
    return dict(version=c['version'], input_hash=input_hash(s), evidence=c['evidence'], baseline_commit=c['baseline_commit'], audit=AU,
                carriages=CA, alignment=AL, petals=PE, fiji=FJ, concepts=CO, scores=SC, sequence=SQ, field_lines=FL, browser=BR,
                consistency=CS, roadmap=RM, verdict=V, stowed_length_m=stow['length_m'], cost=dict(seconds=round(time.time()-t0, 2)))


def _round(x):
    if isinstance(x, float):
        return float(f'{x:.6g}')
    if isinstance(x, dict):
        return {k: _round(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_round(v) for v in x]
    return x


def evidence(s, path=EVIDENCE_PATH):
    R = _round(report(s)); path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(R, indent=1)+'\n')
    return R


if __name__ == '__main__':
    S = spec.load(ROOT)[0]
    R = evidence(S) if '--evidence' in sys.argv else report(S)
    print(json.dumps(R['verdict'], indent=1)); print(f'{R["cost"]["seconds"]} s')
