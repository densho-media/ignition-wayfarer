"""Redesign study (owner brief 2026-11-01): numbers behind the layout, storage split, radiator zoning, shield shadow and RCS choices.
Pure Python, reads the spec; nothing in src/ reads this file. Run from the project root: python3 lab/variants/redesign-layout/study.py
Writes lab/variants/redesign-layout/study_results.json. Every result is PROTOTYPE screening, not qualification."""
import copy
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT/'src/wayfarer'))
import spec  # noqa: E402
import layout, fuel_storage as fs, mass_model as mm, operating_point as op, habitat_ring as hr  # noqa: E402,E401
import radiator_zones as rz, thermal_geometry as tg, forward_shield as fsh, exterior_hardware as eh, attitude  # noqa: E402,E401

SIGMA = 5.670374419e-8
G0 = 9.80665


def r3(x):
    return round(x, 3) if isinstance(x, float) else x


# ---------- 1. storage split: adopted (small forward, large aft) against a balanced split ----------------------------------------------

def spine_load_profile(parts, accel, stations):
    """Axial compression the spine carries at each station under thrust: the inertia of everything ahead of it (thrust enters aft)."""
    return {name: sum(p['m'] for p in parts if p['c'][0] > x)*accel for name, x in stations.items()}


def variant_parts(s, variant, left=1.0):
    """Point-mass parts for a split variant. 'adopted': as built. 'balanced': the two He-3 tori move ahead of the rings (forward bank
    1.42 kt, aft bank 1.38 kt); the aft stack shortens by their 27 m and the forward district grows by the same, so the length is unchanged
    but the rings and their rotating mass sit 27 m further aft."""
    dry = mm.dry_parts(s); st = mm.stores_at(s, left); prop = mm.propellant_parts(s, st)
    if variant == 'adopted':
        return dry+prop
    shift_tori = {'aft_he3_a', 'aft_he3_b'}
    step = 2*fs.cfg(s)['aft_he3_a']['minor_radius_m']+2.5                  # one torus plus its 2.5 m gap (aft_stack)
    xa, xb = hr.centers(s); ring_new = (xa-2*step, xb-2*step)
    sweep = hr.sweep_half(s); clear = 4.75
    he3_x = [ring_new[1]+sweep+clear+5.5, ring_new[1]+sweep+clear+5.5+step]
    names = {fs.torus(s, k)['prefix']: k for k in shift_tori}
    out = []
    for p in dry:
        q = dict(p)
        if xa-10 < p['c'][0] < xb+10 and p['name'] not in ('structure', 'hull'):    # ring-plane items (rotating mass, rotor interface)
            q['c'] = (p['c'][0]-2*step, p['c'][1], p['c'][2])
        out.append(q)
    for p in prop:
        q = dict(p)
        for pre, k in names.items():
            if p['name'].startswith(pre):
                q['c'] = (he3_x[0] if k == 'aft_he3_a' else he3_x[1], p['c'][1], p['c'][2])
        # the D2 and H2 tori keep their places next to the LOW section; the 27 m freed ahead of them goes to the forward district
        out.append(q)
    return out


def split_comparison(s):
    b = op.burn(s); a0 = b['peak_thrust_N']/b['departure_mass_kg']
    o = layout.origins(s); xa, xb = hr.centers(s)
    rows = {}
    for v in ('adopted', 'balanced'):
        dep = mm.totals(variant_parts(s, v, 1.0)); end = mm.totals(variant_parts(s, v, 0.0))
        ring_x = xa if v == 'adopted' else xa-27.0
        st = {'aft of ring A': ring_x-3.0, 'drive end of the aft storage': o['RADIATOR_ZONE_FRONT'], 'hot blade front': o['RADIATOR_FRONT']}
        load = spine_load_profile(variant_parts(s, v, 1.0), a0, st)
        fwd_kg = sum(p['m'] for p in variant_parts(s, v, 1.0) if p['name'].startswith('Fuel_') and p['c'][0] > ring_x)
        rows[v] = dict(forward_bank_t=fwd_kg/1e3, departure_cg_x=dep['cg_m'][0], depleted_cg_x=end['cg_m'][0], cg_travel_m=dep['cg_m'][0]-end['cg_m'][0],
                       I_pitch_departure=dep['I_pitch'], I_pitch_depleted=end['I_pitch'],
                       spine_compression_MN={k: v_/1e6 for k, v_ in load.items()},
                       ring_to_shield_m=o['FWD']-ring_x, forward_district_m=o['FWD']-(xb+hr.sweep_half(s)) if v == 'adopted' else o['FWD']-(xb-27+hr.sweep_half(s)))
    rows['note'] = ('Balanced = both He-3 tori ahead of the rings. Point-mass screen: dry items near the ring planes move with the rings; '
                    'the shield, the Brow and the forward torus stay. Same length, same propellant.')
    return rows


def drawdown(s):
    out = {}
    for order in (None, 'aft_first', 'forward_first'):
        rows = mm.burn_states(s, steps=4, order=order)
        out[order or 'proportional'] = [dict(left=r3(r['mission_left']), mass_t=r3(r['mass_kg']/1e3), cg_x=r3(r['cg_m'][0]), lateral_mm=r3(r['lateral_m']*1e3),
                                             I_pitch=f"{r['I_pitch']:.3e}") for r in rows]
    out['mission'] = [dict(label=m['label'], mass_t=r3(m['mass_kg']/1e3), cg_x=r3(m['cg_m'][0]), I_roll=f"{m['I_roll']:.3e}", I_pitch=f"{m['I_pitch']:.3e}",
                           I_yaw=f"{m['I_yaw']:.3e}", lateral_mm=r3(m['lateral_m']*1e3)) for m in mm.mission_states(s)]
    return out


# ---------- 2. aft-bank heating: LOW radiator view, baffle, drive neutrons --------------------------------------------------------------

def low_to_torus_view(s, n=40000, seed=3):
    """Fraction of one LOW plate face's emission that lands on the aft face of the nearest aft torus (annulus r 17..28 at its aft face),
    with the LOW/WARM baffle and the other blades ignored (upper bound). Cosine-weighted MC from the plate."""
    import random
    R = random.Random(seed); low = [p for p in rz.placed(s) if p['id'] == 'LOW'][0]
    keys = [k for k in fs.tori_keys(s) if fs.bank_of(s, k) == 'aft']; t = min((fs.torus(s, k) for k in keys), key=lambda t: t['x'])
    x_face = t['x']-t['a']; r_in, r_out = t['R']-t['a'], t['R']+t['a']
    r0 = s['radiators']['root_radius']['value']+s['radiators']['root_band']['width_m']; r1 = s['radiators']['outer_radius']['value']
    hit = 0
    for _ in range(n):
        x = low['x0']+(low['x1']-low['x0'])*R.random(); r = r0+(r1-r0)*R.random()
        u1, u2 = R.random(), R.random(); st = math.sqrt(u1); ct = math.sqrt(1-u1); ph = 2*math.pi*u2
        d = (st*math.cos(ph), st*math.sin(ph), ct)                    # (X, radial, plate normal)
        if d[0] <= 0:
            continue
        tt = (x_face-x)/d[0]
        y = r+tt*d[1]; z = tt*d[2]
        if r_in <= math.hypot(y, z) <= r_out:
            hit += 1
    return dict(F_plate_to_torus_face=hit/n, torus=t['key'], gap_m=x_face-low['x1'])


def mli_leak(T_tank, q_in, eps_out=0.05, e_star=0.003):
    """Outer MLI layer in equilibrium: absorbs eps_out*q_in, emits eps_out*sigma*T^4 to space; leak through the blanket e*sigma(To^4-Tt^4)."""
    To = (q_in/SIGMA)**0.25 if q_in > 0 else 4.0
    To = max(To, 4.0)
    return dict(outer_K=To, leak_W_m2=e_star*SIGMA*max(0.0, To**4-T_tank**4))


def aft_heating(s):
    F = low_to_torus_view(s)
    low = [p for p in rz.placed(s) if p['id'] == 'LOW'][0]
    q_low = rz.cfg(s)['emissivity']*SIGMA*low['T_K']**4
    q_face = q_low*F['F_plate_to_torus_face']*6*(low['x1']-low['x0'])*(s['radiators']['outer_radius']['value']-s['radiators']['root_radius']['value'])
    t = fs.torus(s, F['torus']); face_area = math.pi*((t['R']+t['a'])**2-(t['R']-t['a'])**2)
    q_on_face = q_face/face_area
    sun = 0.0                                         # interstellar cruise; the near-Sun departure is a separate case
    rows = dict(view=F, LOW_emission_W_m2=q_low, mean_irradiance_on_aft_face_W_m2=q_on_face,
                mli_deep_space=mli_leak(20.0, 3e-6), mli_with_LOW_view=mli_leak(20.0, q_on_face))
    rows['added_boiloff_W'] = (rows['mli_with_LOW_view']['leak_W_m2']-rows['mli_deep_space']['leak_W_m2'])*face_area
    # drive neutrons: 1 % of peak fusion power, isotropic from the plasma near the throat; tanks behind the reactor shadow shield
    b = op.burn(s); Pn = 0.01*b['peak_fusion_power_W']; x_plasma = layout.origin(s, 'AFT')+5.0
    aft_face = min(fs.torus(s, k)['x']-fs.torus(s, k)['a'] for k in fs.tori_keys(s) if fs.bank_of(s, k) == 'aft')
    old_face = 95.1-9.0; old_plasma = -122.5+5.0                                      # pass 7: return torus aft face, plasma
    for name, d in (('adopted', aft_face-x_plasma), ('pass7', old_face-old_plasma)):
        flux = Pn/(4*math.pi*d*d)
        rows[f'neutron_{name}'] = dict(distance_m=d, unshielded_W_m2=flux, shield_decades_for_1W_m2=math.log10(flux))
    rows['neutron_note'] = ('Unshielded side-reaction neutron flux is MW/m2 class at either position: the reactor shadow shield (mass OPEN, '
                            'Reactor_Shadow_Shield_Envelope) must cover every tank and the crew. The aft bank is farther from the plasma than '
                            'the pass-7 return torus, so it needs slightly less attenuation, not more.')
    rows['sun'] = sun
    return rows


# ---------- 3. radiator zoning numbers -----------------------------------------------------------------------------------------------

def zoning(s):
    secs = rz.placed(s)
    out = dict(sections=[dict(id=x['id'], T_K=x['T_K'], load_MW=x['load_W']/1e6, length_m=x['length_m'], capacity_MW=x['capacity_W']/1e6,
                              margin=x['margin'], x=[x['x0'], x['x1']], area_m2_per_face_all_blades=3*x['length_m']*rz.emitting_height_m(s)) for x in secs],
               hot=dict(T_K=s['radiators']['temperature']['value'], blade=tg.blade_of(s)['length_m'] if 'length_m' in tg.blade_of(s) else None),
               baffle=rz.baffle_temperature(s))
    out['mutual_unbaffled'] = [dict(section=r['section'], emitted=r3(r['emitted_W_m2']), absorbed=r3(r['absorbed_W_m2']), net=r3(r['net_fraction']))
                               for r in rz.mutual_screen(s, 12000, baffled=False)]
    out['mutual_baffled'] = [dict(section=r['section'], emitted=r3(r['emitted_W_m2']), absorbed=r3(r['absorbed_W_m2']), net=r3(r['net_fraction']))
                             for r in rz.mutual_screen(s, 12000, baffled=True)]
    # thermal expansion of each section's plate (aluminium-lithium skin assumed, 22e-6 /K, from 250 K assembly)
    out['expansion_mm'] = {x['id']: 22e-6*(x['T_K']-250)*x['length_m']*1e3 for x in secs}
    out['heat_pump_comparison'] = ('Optional only: pumping the 1 MW LOW load to 440 K at a Carnot fraction of 0.4 needs about 1.3 MW of work and '
                                   'adds 2.3 MW to WARM; it would remove 19.5 m of LOW plate but add about 10 m of WARM plate and the power. '
                                   'Not adopted; radiators are not shrunk by heat pumps.')
    return out


# ---------- 4. shield shadow ----------------------------------------------------------------------------------------------------------

def shadow(s):
    st = fsh.stations(s); R = st['shield_r']; x_sh = layout.origin(s, 'FWD')
    rows = []
    items = [('hot blade aft edge', tg.blade_of(s)['aft_x_m'], s['radiators']['outer_radius']['value']),
             ('WARM/LOW zone aft edge', rz.placed(s)[-1]['x0'], s['radiators']['outer_radius']['value']),
             ('baffle annuli', min(b['x'] for b in rz.baffles(s)), max(b['r1'] for b in rz.baffles(s))),
             ('aft tori', min(fs.torus(s, k)['x']-fs.torus(s, k)['a'] for k in fs.tori_keys(s) if fs.bank_of(s, k) == 'aft'), 28.0),
             ('habitat rings', hr.centers(s)[0]-hr.sweep_half(s), hr.outer(s)),
             ('forward torus', fs.torus(s, 'torus')['x']-fs.torus(s, 'torus')['a'], fs.torus(s, 'torus')['R']+fs.torus(s, 'torus')['a'])]
    for name, x, r in items:
        L = x_sh-x; margin = R-r
        rows.append(dict(item=name, distance_behind_shield_m=L, radius_m=r, radial_margin_m=margin,
                         allowed_misalignment_deg=math.degrees(math.atan2(margin, L))))
    att = s['physics']['attitude']
    return dict(shield_r=R, rows=rows, limit_item=min(rows, key=lambda r: r['allowed_misalignment_deg'])['item'],
                limit_deg=min(r['allowed_misalignment_deg'] for r in rows),
                note=('Geometric shadow only (straight-line dust at 0.016 c along the velocity vector). Ejecta from a grain strike on the '
                      'shield spray at wide angles and secondary radiation (X-rays, neutrons from the impact plasma) is not stopped by the '
                      'shadow line: the Brow, the forward H2 torus (325 t) and the hull carry that, between the shield and the rings. '
                      'OPEN: an ejecta cone model.'))


# ---------- 5. RCS ---------------------------------------------------------------------------------------------------------------------

def rcs(s):
    t = eh.table(s); F = t['rcs_thrust_N']; rep = attitude.report(s)
    ms = mm.mission_states(s); dep, end = ms[0], ms[-1]
    lever = rep['rcs_lever_m']; tau = rep['rcs_couple_N_m']
    def flip_min(I, tq):
        return math.sqrt(4*math.pi*I/tq)/60
    axial_aft = 3*F*math.cos(math.radians(t['rcs_axial_cant_deg']))
    axial_fwd = 4*F*math.cos(math.radians(t['rcs_rim_forward_cant_deg']))
    out = dict(thrust_per_nozzle_N=F, pitch_yaw_couple_N_m=tau, lever_m=lever,
               flip_departure_min=flip_min(dep['I_pitch'], tau), flip_depleted_min=flip_min(end['I_pitch'], tau),
               one_pod_out_flip_departure_min=flip_min(dep['I_pitch'], tau/2),
               roll_accel_departure_deg_s2=math.degrees(rep['flips']['departure']['roll_accel_deg_s2'] and rep['flips']['departure']['roll_accel_deg_s2']),
               translation=dict(plus_x_N=axial_aft, minus_x_N=axial_fwd, plus_x_mm_s2_departure=axial_aft/dep['mass_kg']*1e3,
                                minus_x_mm_s2_departure=axial_fwd/dep['mass_kg']*1e3, docking_closing_0p1_m_s_at_departure_s=0.1/(axial_fwd/dep['mass_kg'])),
               propellant_per_flip_kg=rep['flips']['departure']['propellant_kg'],
               jets=[dict(name=r['name'], ok=r['ok'], hits=r['hits']) for r in eh.jets(s)],
               high_speed_rule='Unchanged: at cruise the shield axis stays on the velocity vector within the shadow limit; RCS trims only.')
    out['jet_failures'] = [j['name'] for j in out['jets'] if not j['ok']]
    return out


# ---------- 6. added dry mass and its propellant consequence ---------------------------------------------------------------------------

def dry_mass_consequence(s):
    """The extension, zone plates and baffles are not in the canon mass budget (kept OPEN). Bounding estimate and the propellant it would
    need at the same delta-v (rocket equation scaling: propellant grows with dry mass at a fixed mass ratio)."""
    z = rz.placed(s); h = rz.emitting_height_m(s)
    plate_area = sum(3*x['length_m']*h for x in z)                       # one sheet per blade per section
    plates = plate_area*6.0                                               # 6 kg/m2 two-face sheet with heat pipes (PROTOTYPE)
    baffles = sum(math.pi*(b['r1']**2-b['r0']**2)*b['layers']*1.2 for b in rz.baffles(s))   # 1.2 kg/m2 per layer incl. frame
    spine = 98.5*125000.0/245.0                                          # 98.5 m more spine/casing at the main structure's 0.51 t/m (125 t fixed over 245 m)
    vents = 30*80.0; cryo = 12*400.0
    total = plates+baffles+spine+vents+cryo
    m = op.mission(s); dep = m['departure_mass_kg']; prop = m['propellant_kg']; dry = dep-prop
    extra_prop = total*prop/dry
    return dict(plates_kg=plates, baffles_kg=baffles, spine_kg=spine, vents_kg=vents, cryocoolers_kg=cryo, total_kg=total,
                propellant_to_keep_delta_v_kg=extra_prop, fraction_of_inventory=extra_prop/prop,
                rule='Inventory not reduced and not yet grown: the added dry mass is reported, the canon budget stays as is (OPEN).')


def main():
    s = spec.load()[0]
    res = dict(status='PROTOTYPE screening (owner brief 2026-11-01); not flight qualification',
               layout=layout.origins(s), length_m=s['ship']['length']['value'],
               storage=fs.screen(s), split=split_comparison(s), drawdown=drawdown(s), aft_heating=aft_heating(s), zoning=zoning(s),
               shadow=shadow(s), rcs=rcs(s), dry_mass=dry_mass_consequence(s))
    out = Path(__file__).with_name('study_results.json')
    out.write_text(json.dumps(res, indent=1, default=float)+'\n')
    print(json.dumps(dict(split=res['split'], aft_heating={k: v for k, v in res['aft_heating'].items() if k != 'sun'}, shadow=res['shadow'],
                          rcs={k: v for k, v in res['rcs'].items() if k != 'jets'}, dry=res['dry_mass'], zoning=res['zoning']['sections'],
                          mutual=[res['zoning']['mutual_unbaffled'], res['zoning']['mutual_baffled']], exp=res['zoning']['expansion_mm']), indent=1, default=float))


if __name__ == '__main__':
    main()
