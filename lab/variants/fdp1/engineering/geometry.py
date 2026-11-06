"""FDP-1 procedural geometry. Pure: turns the engineering record into a list of parts (plain dicts) that blender/build_fdp1.py draws.
Every dimension below is read from the record (and through it from fdp1.toml and the four-burn closure); only drawing choices
(segment counts, label sizes, marker sizes of things too small to see) are local and are flagged 'illustrative'.

Part: name, coll (collection key), func (functional colour key, src/wayfarer/functional_colors.PALETTE or VIS), shape, numbers,
status ('ENGINEERED' sized by the calculation, 'PLACEHOLDER' provisional placement or size, 'ILLUSTRATIVE' display only), alpha.
Shapes (ship frame, metres, +X bow; azimuth from +Y toward +Z):
  ring     annulus x0..x1, r0..r1 about the X axis, optional arc (a0, a1) degrees
  frustum  solid/shell of revolution: x0, r0 -> x1, r1 (inner radii ri0/ri1 for a shell)
  torus    about the X axis at x, major R, minor a, optional arc (a0, a1)
  sphere   centre, radius
  box      centre, size (dx, dy, dz), roll about X (degrees)
  tube     polyline points, radius
  panel    planar quad: corners p0..p3, thickness
  capsule  vessel: x0..x1, centre (y, z), radius
  text     location, body, size, facing ('side' = readable from -Y, 'top' = from +Z)
"""
import math

COLLECTIONS = {
    '00': ('FDP1_00_STRUCTURE', 'STRUCTURE'), '01': ('FDP1_01_FUEL_PREPARATION', 'HELIUM3'), '02': ('FDP1_02_PULSED_DRIVERS', 'MAIN_PROPULSION'),
    '03': ('FDP1_03_REACTION_ZONE', 'MAIN_PROPULSION'), '04': ('FDP1_04_MAGNETIC_NOZZLE', 'MAIN_PROPULSION'), '05': ('FDP1_05_RADIATION_SHIELDING', 'SHIELD'),
    '06': ('FDP1_06_THERMAL', 'WARM_RADIATOR'), '07': ('FDP1_07_ELECTRICAL_POWER', 'POWER'), '08': ('FDP1_08_SENSORS_GUIDANCE', 'SENSORS_COMMS'),
    '09': ('FDP1_09_MAINTENANCE', 'SERVICE'), '10': ('FDP1_10_TANKS_PROPOSED', 'HELIUM3'), '11': ('FDP1_11_KEEP_OUT_ZONES', 'SHIELD'),
    '12': ('FDP1_12_LABELS', 'SERVICE'),
}
VIS = {'PLASMA': (0.95, 0.35, 0.90, 1.0), 'XRAY': (1.0, 0.25, 0.20, 1.0), 'SAFE': (0.95, 0.80, 0.30, 1.0), 'BEAM': (1.0, 0.55, 0.95, 1.0)}
SPECIES_FUNC = {'helium_3': 'HELIUM3', 'deuterium': 'DEUTERIUM', 'hydrogen': 'HYDROGEN'}


def pol(x, r, az):
    a = math.radians(az)
    return (x, r*math.cos(a), r*math.sin(a))


def P(parts, name, coll, func, shape, status='ENGINEERED', alpha=1.0, **kw):
    d = {'name': name, 'coll': coll, 'func': func, 'shape': shape, 'status': status, 'alpha': alpha}
    d.update(kw); parts.append(d); return d


def parts(R):
    lay = R['layout']; noz = R['nozzle']; sh = R['shield']; drv = R['drivers']; st = R['structure']; th = R['thermal']
    out = []
    xB = lay['x_burn']; xSA = lay['x_shield_aft']; xSF = lay['x_shield_fwd']; xMF = lay['x_module_fwd']; xA = lay['x_attach']
    Rm = lay['module_radius']; Rs = lay['R_s']
    # ---------------------------------------------------------------- 00 structure
    P(out, 'FDP1_Module_Skin', '00', 'STRUCTURE', 'frustum', x0=xSF, r0=Rm, x1=xMF, r1=Rm, ri0=Rm-0.25, ri1=Rm-0.25, alpha=0.18,
      note='equipment module pressure-free skin (translucent in review)')
    k = 0; x = xSF+3.0
    while x < xMF-1.0:
        P(out, f'FDP1_Module_Frame_{k:02d}', '00', 'STRUCTURE', 'torus', x=x, R=Rm-0.2, a=0.18); k += 1; x += 6.0
    for i in range(6):
        az = 30.0+60.0*i
        P(out, f'FDP1_Module_Longeron_{i}', '00', 'STRUCTURE', 'tube', points=[pol(xSF, Rm-0.2, az), pol(xMF, Rm-0.2, az)], radius=0.22)
    P(out, 'FDP1_Thrust_Adapter', '00', 'STRUCTURE', 'frustum', x0=xMF, r0=Rm-0.2, x1=xA+2.0, r1=6.0, ri0=Rm-0.6, ri1=5.6,
      note='bolts to the existing thrust ring (canon) at the AFT datum')
    P(out, 'FDP1_Shield_Frame_Ring', '00', 'STRUCTURE', 'torus', x=xSF+0.6, R=sh['radius_hw_fwd_m']-0.3, a=0.35)
    n = int(R['structure']['struts'][0]['count']) if R['structure']['struts'] else 0
    for si, s in enumerate(st['struts']):
        (x0, r0), (x1, r1) = s['a'], s['b']
        for j in range(n):
            az = 360.0*j/n+(15.0 if si % 2 else 0.0)
            P(out, f"FDP1_Nozzle_Strut_{s['loop']}_{j}", '00', 'STRUCTURE', 'tube', points=[pol(x0, r0, az), pol(x1, r1, az)],
              radius=s['radius_m'], note=f"lattice column, {s['governs']}-governed, load {s['load_N']/1e3:.0f} kN, length {s['length_m']:.1f} m")
    # ---------------------------------------------------------------- 04 magnetic nozzle
    nsec = noz['trim_sectors']; gap = 5.0
    for L in noz['loops']:
        for q in range(nsec):
            a0 = 360.0*q/nsec+gap/2+45.0; a1 = a0+360.0/nsec-gap
            P(out, f"FDP1_{L['name']}_Sector_{q+1}", '04', 'MAIN_PROPULSION', 'torus', x=L['x'], R=L['r'], a=L['minor_radius_m']*1.6, arc=(a0, a1),
              note=f"REBCO winding + hoop structure, trim sector {q+1} of {nsec} (control authority, not an engine)")
            P(out, f"FDP1_{L['name']}_Cryostat_{q+1}", '04', 'LOW_RADIATOR', 'torus', x=L['x'], R=L['r'], a=L['envelope_radius_m'], arc=(a0, a1), alpha=0.35,
              note='cryostat envelope (20-40 K)')
            P(out, f"FDP1_{L['name']}_Fiji_Lattice_{q+1}", '04', 'HELIUM3', 'torus', x=L['x']+L['envelope_radius_m']*0.4*math.cos(math.radians(L['phi_deg'])),
              R=L['r']+L['envelope_radius_m']*0.9*math.sin(math.radians(L['phi_deg'])), a=L['envelope_radius_m']*0.45, arc=(a0+2, a1-2),
              status='PLACEHOLDER', note='Fiji amplification/stabilisation lattice band on the outer face (canon properties only)')
            mid = (a0+a1)/2
            P(out, f"FDP1_{L['name']}_Sector_Feed_{q+1}", '07', 'POWER', 'tube', status='PLACEHOLDER',
              points=[pol(L['x'], L['r']+L['envelope_radius_m'], mid), pol(xSA, sh['radius_hw_aft_m']*0.95, mid)], radius=0.12,
              note='independent trim-sector supply and inductive recovery feed')
        # coil armour shoe on the burn-facing side (renewable W over B4C/LiH)
        ph = math.radians(L['phi_deg']); off = L['envelope_radius_m']*1.05
        P(out, f"FDP1_{L['name']}_Armour_Shoe", '05', 'SHIELD', 'torus', x=L['x']-off*math.cos(ph), R=L['r']-off*math.sin(ph), a=L['envelope_radius_m']*0.55,
          note=f"coil protection: {L['armour_kg']/1e3:.1f} t renewable W/B4C armour")
    # ---------------------------------------------------------------- 05 shield
    w = sh['w_face_m']
    P(out, 'FDP1_Shield_W_Xray_Face', '05', 'SHIELD', 'frustum', x0=xSA, r0=sh['radius_hw_aft_m'], x1=xSA+max(w, 0.05), r1=sh['radius_hw_aft_m'],
      note=f"tungsten X-ray face {w*100:.0f} cm (needs {sh['w_needed_m']*1000:.1f} mm)")
    P(out, 'FDP1_Shield_LiH_Crew_Core', '05', 'SHIELD', 'frustum', x0=xSA+w, r0=sh['radius_crew_aft_m'], x1=xSA+w+sh['lih_core_m'], r1=sh['radius_crew_fwd_m'],
      note=f"crew shadow: {sh['neutron_decades']:.1f} decades, {sh['lih_core_m']:.2f} m LiH")
    P(out, 'FDP1_Shield_LiH_Hardware_Annulus', '05', 'SHIELD', 'frustum', x0=xSA+w, r0=sh['radius_hw_aft_m'], x1=xSA+w+sh['lih_annulus_m'], r1=sh['radius_hw_fwd_m'],
      ri0=sh['radius_crew_aft_m'], ri1=sh['radius_crew_aft_m']+(sh['radius_crew_fwd_m']-sh['radius_crew_aft_m'])*sh['lih_annulus_m']/max(sh['lih_core_m'], 1e-6),
      status='PLACEHOLDER', note=f"hardware shadow (tanks, drivers, forward hardware): {sh['hardware_decades']:.0f} decades placeholder")
    # ---------------------------------------------------------------- 03 reaction zone, 02 beams, 01 pellets
    P(out, 'FDP1_Ignition_Point', '03', 'VIS_PLASMA', 'sphere', centre=(xB, 0, 0), radius=1.2, status='ILLUSTRATIVE', note='burn point (target ~2 cm)')
    P(out, 'FDP1_Plasma_Expansion', '03', 'VIS_PLASMA', 'sphere', centre=(xB, 0, 0), radius=noz['focal_length_m'], alpha=0.10, status='ILLUSTRATIVE',
      note='expanding burn plasma, turned by the nozzle field')
    L3 = noz['loops'][-1]; L1 = noz['loops'][0]
    pts = [(xB, 0.0)]+[(L['x'], L['r']*0.92) for L in noz['loops']]
    for i, ((xa, ra), (xb, rb)) in enumerate(zip(pts, pts[1:])):
        P(out, f'FDP1_Exhaust_Envelope_Nozzle_{i}', '03', 'VIS_PLASMA', 'frustum', x0=xb, r0=rb, x1=xa, r1=ra, ri0=max(rb-0.2, 0), ri1=max(ra-0.2, 0), alpha=0.12, status='ILLUSTRATIVE')
    Lx = 3.0*Rs; ang = math.radians(noz['plume_half_angle_deg'])
    P(out, 'FDP1_Exhaust_Plume', '03', 'VIS_PLASMA', 'frustum', x0=L3['x']-Lx, r0=L3['r']*0.92+Lx*math.tan(ang), x1=L3['x'], r1=L3['r']*0.92,
      ri0=L3['r']*0.92+Lx*math.tan(ang)-0.3, ri1=L3['r']*0.92-0.3, alpha=0.08, status='ILLUSTRATIVE', note='detached charged-particle exhaust, -X')
    P(out, 'FDP1_Exhaust_Direction_Arrow', '03', 'VIS_PLASMA', 'frustum', x0=L3['x']-Lx-25, r0=0.0, x1=L3['x']-Lx, r1=8.0, status='ILLUSTRATIVE')
    P(out, 'FDP1_Exhaust_Direction_Shaft', '03', 'VIS_PLASMA', 'tube', points=[(xB-5, 0, 0), (L3['x']-Lx, 0, 0)], radius=2.0, alpha=0.5, status='ILLUSTRATIVE')
    P(out, 'FDP1_Target_Injection_Axis', '03', 'MAIN_PROPULSION', 'tube', points=[(xSF, 0, 0), (xB, 0, 0)], radius=0.08, note='pellet flight path (on axis)')
    sp = R['injection']['speed_m_s']/R['fusion']['pellet_rate_Hz']; xx = xSA-sp; k = 0
    while xx > xB+1.5 and k < 400:
        if k % max(1, int(4.0/sp)) == 0:
            P(out, f'FDP1_Pellet_In_Flight_{k:03d}', '03', 'DEUTERIUM', 'sphere', centre=(xx, 0, 0), radius=0.25, status='ILLUSTRATIVE',
              note=f"pellet marker (true diameter {R['pellet']['diameter_mm']:.0f} mm, spacing {sp:.1f} m)")
        xx -= sp; k += 1
    a_beam = math.radians(sh['hardware_half_angle_deg'])*0.7
    rp = lay['d_shield']*math.tan(a_beam)
    for b in range(drv['beams']):
        az = 360.0*b/drv['beams']+20.0
        P(out, f'FDP1_Beam_{b+1}_Final_Path', '03', 'VIS_BEAM', 'tube', points=[pol(xSA, rp, az), (xB, 0.0, 0.0)], radius=0.10, status='ILLUSTRATIVE',
          note='heavy-ion beam, final focus to target')
        P(out, f'FDP1_Beam_Port_{b+1}', '05', 'VIS_XRAY', 'tube', points=[pol(xSA-0.2, rp, az), pol(xSF+0.2, rp*(1+sh['thickness_m']/lay['d_shield']), az)],
          radius=0.2, note='streaming corridor through the shield (dog-legged)')
        P(out, f'FDP1_Final_Focus_{b+1}', '02', 'MAIN_PROPULSION', 'tube', points=[pol(xSF+0.5, rp*1.1, az), pol(xSF+8.0, rp*1.1+1.5, az)], radius=0.45,
          status='PLACEHOLDER', note='final-focus quadrupoles + dog-leg dipole')
        P(out, f'FDP1_Beam_Dump_{b+1}', '05', 'SHIELD', 'ring', x0=xSF+9.0, x1=xSF+9.0+sh['lih_core_m'], r0=0.0, r1=0.7, centre=pol(0, rp*1.1, az)[1:],
          note='LiH dump terminating the port line of sight')
        P(out, f'FDP1_Beam_Transport_{b+1}', '02', 'MAIN_PROPULSION', 'tube', status='PLACEHOLDER',
          points=[pol(xSF+8.0, rp*1.1+1.5, az), pol(xMF-2.0, Rm-1.2, az), pol(xA+1.0, drv['radius_m'], drv['azimuths_deg'][b % len(drv['azimuths_deg'])])],
          radius=0.18, note='beam transport from the gallery to the final focus')
    P(out, 'FDP1_Pellet_Bore', '05', 'VIS_XRAY', 'tube', points=[(xSA-0.2, 0, 0), (xSF+0.2, 0, 0)], radius=0.3, note='on-axis streaming corridor (pellet bore)')
    P(out, 'FDP1_Axial_Plug', '05', 'SHIELD', 'ring', x0=xSF+16.0, x1=xSF+16.0+R['shield']['streaming']['pellet_bore']['plug_length_m'],
      r0=0.0, r1=R['shield']['streaming']['pellet_bore']['plug_radius_m'], note='LiH plug behind the injector breech (crew trunk lies on this axis)')
    # ---------------------------------------------------------------- 01 fuel preparation
    xc = xSF+10.0
    P(out, 'FDP1_Pellet_Injector_A', '01', 'MAIN_PROPULSION', 'tube', points=[(xSF+14.0, 0, 0), (xSF+0.3, 0, 0)], radius=0.35, note='gas-gun injector, active')
    P(out, 'FDP1_Pellet_Injector_B_Spare', '01', 'MAIN_PROPULSION', 'tube', points=[(xSF+14.0, 0, 1.2), (xSF+0.3, 0, 0.25)], radius=0.3,
      note='fault-isolated spare injector, valved off')
    P(out, 'FDP1_Pellet_Magazine', '01', 'MAIN_PROPULSION', 'ring', x0=xSF+14.5, x1=xSF+16.0, r0=0.0, r1=1.6, note=f"{R['injection']['magazine_pulses']} pellets ({R['injection']['magazine_seconds']:.0f} s)")
    P(out, 'FDP1_Target_Conditioning_Cryostat', '01', 'LOW_RADIATOR', 'ring', x0=xc+12.0, x1=xc+18.0, r0=0.0, r1=2.0, centre=(0.0, 2.6),
      note='D2 shell layering around liquid He-3 at ~1.5 K')
    P(out, 'FDP1_Target_Factory', '01', 'MAIN_PROPULSION', 'box', centre=(xc+15.0, 0.0, -2.4), size=(9.0, 6.0, 3.6), status='PLACEHOLDER',
      note=f"{R['injection']['pellets_per_day']/1e6:.1f} million targets per day")
    P(out, 'FDP1_Fuel_Metering_He3', '01', 'HELIUM3', 'box', centre=(xMF-4.0, 2.8, 2.8), size=(3.0, 1.4, 1.4), status='PLACEHOLDER',
      note=f"He-3 {R['fusion']['species_flow_kg_s']['helium_3']*1e3:.1f} g/s")
    P(out, 'FDP1_Fuel_Metering_D2', '01', 'DEUTERIUM', 'box', centre=(xMF-4.0, -2.8, 2.8), size=(3.0, 1.4, 1.4), status='PLACEHOLDER',
      note=f"D2 {R['fusion']['species_flow_kg_s']['deuterium']*1e3:.1f} g/s")
    P(out, 'FDP1_Fuel_Isolation_Valves', '01', 'MAIN_PROPULSION', 'box', centre=(xMF-1.2, 0.0, 3.4), size=(1.0, 6.0, 1.0), status='PLACEHOLDER')
    ex = R['tanks']['existing']; x_out = min(t['x0'] for t in ex)
    for key, az, func in (('helium_3', 40.0, 'HELIUM3'), ('deuterium', 50.0, 'DEUTERIUM')):
        P(out, f'FDP1_Feed_Line_{key}', '01', func, 'tube', radius=0.15, status='PLACEHOLDER',
          points=[pol(x_out, 7.4, az), pol(xA, 7.4, az), pol(xMF-4.0, 4.0, az), ((xMF-4.0), 2.8 if key == 'helium_3' else -2.8, 2.8)],
          note='cryogenic transfer line, farm outlet to metering (inside the shadow cone)')
    # ---------------------------------------------------------------- 02 driver galleries
    nb = drv['beams']//max(drv['galleries'], 1); ap = 0.8; rg = drv['radius_m']; xg0 = drv['x_aft']; Lp = drv['pass_length_m']
    for gi, gaz in enumerate(drv['azimuths_deg']):
        for b in range(nb):
            ra = drv['arc_radius_m']+b*ap
            dphi = math.degrees(ra/rg)
            a_in, a_out = gaz-dphi, gaz+dphi
            nm = f'FDP1_Driver_G{gi+1}_Beam{b+1}'
            P(out, nm+'_Pass1', '02', 'MAIN_PROPULSION', 'tube', points=[pol(xg0, rg, a_in), pol(xg0+Lp, rg, a_in)], radius=max(drv['core_radius_m'], 0.08),
              note=f"induction linac pass {Lp:.0f} m, core section from the calculator's driver mass")
            P(out, nm+'_Pass2', '02', 'MAIN_PROPULSION', 'tube', points=[pol(xg0+Lp, rg, a_out), pol(xg0, rg, a_out)], radius=max(drv['core_radius_m'], 0.08))
            arc = [pol(xg0+Lp+ra*math.sin(math.pi*t/16), rg, gaz+dphi*math.cos(math.pi*t/16)*-1) for t in range(17)]
            P(out, nm+'_Arc', '02', 'MAIN_PROPULSION', 'tube', points=arc, radius=0.35, status='PLACEHOLDER', note=f"180 deg arc, B rho {drv['magnetic_rigidity_Tm']:.1f} T m")
        # gallery truss and walkway
        dmax = math.degrees((drv['arc_radius_m']+nb*ap)/rg)
        for side in (-1, 1):
            P(out, f'FDP1_Gallery_{gi+1}_Chord_{side:+d}', '00', 'STRUCTURE', 'tube', points=[pol(xg0, rg-1.0, gaz+side*dmax), pol(xg0+Lp+drv['arc_radius_m'], rg-1.0, gaz+side*dmax)], radius=0.2)
        P(out, f'FDP1_Gallery_{gi+1}_Walkway', '09', 'SERVICE', 'tube', points=[pol(xg0, rg-1.6, gaz), pol(xg0+Lp, rg-1.6, gaz)], radius=0.25, status='PLACEHOLDER',
          note='robot/EVA service rail along the gallery')
        P(out, f'FDP1_Gallery_{gi+1}_Bus', '07', 'POWER', 'tube', points=[pol(xg0, rg-0.6, gaz+dmax*0.5), pol(xg0+Lp, rg-0.6, gaz+dmax*0.5)], radius=0.2, status='PLACEHOLDER',
          note='pulse-power bus')
        P(out, f'FDP1_Gallery_{gi+1}_Warm_Header', '06', 'WARM_RADIATOR', 'tube', points=[pol(xg0, rg-0.6, gaz-dmax*0.5), pol(xg0+Lp, rg-0.6, gaz-dmax*0.5)], radius=0.25,
          status='PLACEHOLDER', note='driver waste-heat header to the warm wings')
    # ---------------------------------------------------------------- 07 electrical power in the module
    m_st = drv['storage_mass_kg']; vol = m_st/2500.0; nbank = 6; side = (vol/nbank/3.0)**0.5
    for i in range(nbank):
        az = 60.0*i; P(out, f'FDP1_Pulse_Storage_Bank_{i+1}', '07', 'POWER', 'box', centre=pol(xSF+24.0, Rm-2.2, az), size=(3.0, side, side), roll=az, status='PLACEHOLDER',
                         note=f"{m_st/1e3/nbank:.1f} t pulsed-power store, {R['drivers']['electric_energy_per_pulse_J']/1e6:.0f} MJ per pulse")
    P(out, 'FDP1_Power_Conditioning', '07', 'POWER', 'ring', x0=xSF+28.0, x1=xSF+32.0, r0=2.0, r1=Rm-0.8, note='recovery rectification and driver modulators')
    P(out, 'FDP1_Cryoplant', '06', 'LOW_RADIATOR', 'ring', x0=xSF+19.0, x1=xSF+22.0, r0=2.4, r1=Rm-0.8, arc=(200, 340), note='20-40 K coil cryoplant (input heat to the warm loop)')
    # ---------------------------------------------------------------- 06 thermal: wings (hot root band + warm field)
    sel = th['layouts'][th['selected_layout']]; xw0 = lay['wing_aft_x']; xw1 = lay['wing_forward_x']
    root = sel['warm_root_radius_m']-sel['hot_band_m']
    for wi, az in enumerate(sel['azimuths_deg']):
        r_hot1 = root+sel['hot_band_m']; r_tip = sel['tip_radius_m']
        P(out, f'FDP1_Wing_{wi+1}_Hot_Band', '06', 'HOT_RADIATOR', 'panel', corners=[pol(xw0, root, az), pol(xw1, root, az), pol(xw1, r_hot1, az), pol(xw0, r_hot1, az)], thickness=0.3,
          note=f"1800 K heat-pipe band {sel['hot_band_m']:.0f} m (the hot loop beyond the three reused blades)")
        P(out, f'FDP1_Wing_{wi+1}_Thermal_Break', '00', 'STRUCTURE', 'tube', points=[pol(xw0, r_hot1+1.0, az), pol(xw1, r_hot1+1.0, az)], radius=0.6)
        P(out, f'FDP1_Wing_{wi+1}_Warm_Field', '06', 'WARM_RADIATOR', 'panel', corners=[pol(xw0, r_hot1+2.0, az), pol(xw1, r_hot1+2.0, az), pol(xw1, r_tip, az), pol(xw0, r_tip, az)],
          thickness=0.4, note=f"{th['radiators']['warm']['T_K']:.0f} K driver/power radiator, span {sel['span_m']:.0f} m (full calculated extent)")
        for e, xe in (('Aft', xw0), ('Fwd', xw1)):
            P(out, f'FDP1_Wing_{wi+1}_Spar_{e}', '00', 'STRUCTURE', 'tube', points=[pol(xe, root, az), pol(xe, r_tip, az)], radius=1.0)
        P(out, f'FDP1_Wing_{wi+1}_Root_Boom', '00', 'STRUCTURE', 'tube', points=[pol(xw0, root, az), pol(xw1, root, az)], radius=0.8)
        for j, xr in enumerate((xw0+20, (xw0+xw1)/2, xw1-20)):
            P(out, f'FDP1_Wing_{wi+1}_Root_Strut_{j}', '00', 'STRUCTURE', 'tube', points=[pol(xr, 6.4, az), pol(xr, root, az)], radius=0.5)
        P(out, f'FDP1_Wing_{wi+1}_Hot_Header', '06', 'HOT_RADIATOR', 'tube', points=[pol(xSA+2, sh['radius_hw_aft_m']*0.8, az), pol(xw0, root+2.0, az), pol(xw1, root+2.0, az)], radius=0.5,
          status='PLACEHOLDER', note='hot-loop header from the loop armour and shield face')
        P(out, f'FDP1_Wing_{wi+1}_EVA_Crossing', '09', 'SERVICE', 'ring', x0=(xw0+xw1)/2-2, x1=(xw0+xw1)/2+2, r0=6.5, r1=root, arc=(az-3, az+3), status='PLACEHOLDER',
          note='hull-walking crossing under the wing root')
    lo = th['low_loop']
    if lo['area_m2'] > 0:
        span = 8.0; L_lo = lo['area_m2']/(2*span)
        xs = max(t['x1'] for t in ex)+2.0
        for az in (0.0, 180.0):
            P(out, f'FDP1_Low_Loop_Panel_{int(az)}', '06', 'LOW_RADIATOR', 'panel', corners=[pol(xs, 36.0, az), pol(xs+L_lo, 36.0, az), pol(xs+L_lo, 36.0+span, az), pol(xs, 36.0+span, az)],
              thickness=0.2, note=f"300 K panel for the added tank cryocooling ({lo['added_cooling_W']/1e3:.0f} kW)")
    # hot/cryo lines along the struts
    for si, s in enumerate(st['struts']):
        (x0, r0), (x1, r1) = s['a'], s['b']
        P(out, f"FDP1_Hot_Line_{s['loop']}", '06', 'HOT_RADIATOR', 'tube', points=[pol(x0, r0, 7.0), pol(x1, r1, 7.0)], radius=0.18, status='PLACEHOLDER')
        P(out, f"FDP1_Cryo_Line_{s['loop']}", '06', 'LOW_RADIATOR', 'tube', points=[pol(x0, r0, 11.0), pol(x1, r1, 11.0)], radius=0.12, status='PLACEHOLDER')
    # ---------------------------------------------------------------- 08 sensors and guidance
    for i in range(4):
        az = 45.0+90.0*i
        P(out, f'FDP1_Target_Tracker_{i+1}', '08', 'SENSORS_COMMS', 'box', centre=pol(xSA-0.6, sh['radius_hw_aft_m']*0.9, az), size=(1.0, 0.8, 0.8), roll=az, status='PLACEHOLDER',
          note=f"pellet tracking lidar: drift under thrust {R['injection']['drift_under_peak_accel_m']*1000:.1f} mm in flight")
        P(out, f'FDP1_Burn_Diagnostic_{i+1}', '08', 'SENSORS_COMMS', 'box', centre=pol(L1['x'], L1['r']+L1['envelope_radius_m']+0.5, az+45), size=(0.8, 0.8, 0.8), roll=az+45, status='PLACEHOLDER',
          note='neutron/X-ray yield monitor')
    for b in range(drv['beams']):
        az = 360.0*b/drv['beams']+20.0
        P(out, f'FDP1_Beam_Position_Monitor_{b+1}', '08', 'SENSORS_COMMS', 'torus', x=xSF+4.0, R=0.0, a=0.0, status='PLACEHOLDER', skip=True)
    P(out, 'FDP1_Injector_Alignment_Lidar', '08', 'SENSORS_COMMS', 'ring', x0=xSF+0.4, x1=xSF+1.2, r0=0.5, r1=0.9, status='PLACEHOLDER')
    # ---------------------------------------------------------------- 09 maintenance
    for i in range(4):
        az = 90.0*i
        P(out, f'FDP1_Module_Service_Hatch_{i+1}', '09', 'SERVICE', 'box', centre=pol((xSF+xMF)/2, Rm+0.15, az), size=(3.0, 0.3, 2.2), roll=az, status='PLACEHOLDER')
    P(out, 'FDP1_Shield_Face_Exchange_Rail', '09', 'SERVICE', 'torus', x=xSF+1.5, R=sh['radius_hw_fwd_m']+0.6, a=0.15, status='PLACEHOLDER',
      note='renewable W face / armour exchange interface')
    P(out, 'FDP1_Strut_Crawler_Rail', '09', 'SERVICE', 'tube', points=[pol(st['struts'][-1]['a'][0], st['struts'][-1]['a'][1], 3.0), pol(st['struts'][0]['b'][0], st['struts'][0]['b'][1], 3.0)],
      radius=0.1, status='PLACEHOLDER', note='armour-service crawler (no access while pulsing)')
    # ---------------------------------------------------------------- 11 keep-out zones
    P(out, 'FDP1_KeepOut_Xray_Fluence_Sphere', '11', 'VIS_XRAY', 'sphere', centre=(xB, 0, 0), radius=Rs, alpha=0.06, status='ENGINEERED',
      note=f"no permanent hardware inside R_s = {Rs:.1f} m (per-pulse X-ray fluence limit)")
    xfar = 260.0
    for kind, ang_deg, nm in (('crew', sh['crew_half_angle_deg'], 'Crew'), ('hw', sh['hardware_half_angle_deg'], 'Hardware')):
        t = math.tan(math.radians(ang_deg))
        P(out, f'FDP1_Shadow_Cone_{nm}', '11', 'VIS_SAFE', 'frustum', x0=xSA, r0=(xSA-xB)*t, x1=xfar, r1=(xfar-xB)*t, ri0=(xSA-xB)*t-0.3, ri1=(xfar-xB)*t-0.3,
          alpha=0.05, status='ENGINEERED', note=f"{nm.lower()} shadow, half-angle {ang_deg:.2f} deg from the burn point; EVA only inside it while pulsing")
    P(out, 'FDP1_KeepOut_Plume', '11', 'VIS_PLASMA', 'frustum', x0=L3['x']-Lx, r0=L3['r']+Lx*math.tan(ang)+10, x1=L3['x'], r1=L3['r']+5, ri0=L3['r']+Lx*math.tan(ang)+9.5, ri1=L3['r']+4.5,
      alpha=0.04, status='ILLUSTRATIVE', note='exhaust keep-out (no structure, no traffic)')
    return [p for p in out if not p.get('skip')]


def tank_parts(R):
    out = []
    for key, o in R['tanks']['options'].items():
        for t in o['vessels']:
            P(out, t['name'], f'10:{key}', SPECIES_FUNC[t['key']], 'capsule', x0=t['x0'], x1=t['x1'], centre=(t['y'], t['z']), radius=t['a_env'],
              alpha=0.35, status='PLACEHOLDER', note=f"proposed {key} vessel, {t['liquid_m3']:.0f} m3 {t['key']}")
    return out


def labels(R):
    lay = R['layout']; noz = R['nozzle']; sh = R['shield']; th = R['thermal']; sel = th['layouts'][th['selected_layout']]
    xB = lay['x_burn']; L3 = noz['loops'][-1]
    c = R['closure']; f = R['fusion']
    out = []
    S = 7.0
    rows = [
        ('Burn point', (xB, 0, -20), f"BURN POINT  {f['pellet_rate_Hz']:.0f} Hz x {f['yield_per_pulse_t_TNT']:.0f} t TNT"),
        ('Nozzle', (L3['x'], 0, L3['r']+12), f"FIJI MAGNETIC NOZZLE  {len(noz['loops'])} loops x {noz['trim_sectors']} trim sectors"),
        ('Shield', (lay['x_shield_aft'], 0, sh['radius_hw_aft_m']+10), f"SHADOW SHIELD  {sh['mass_kg']['total']/1e3:.0f} t"),
        ('Module', ((lay['x_shield_fwd']+lay['x_module_fwd'])/2, 0, 16), 'TARGET FACTORY / POWER MODULE'),
        ('Drivers', (lay['x_attach']+60, 0, R['drivers']['radius_m']+12), f"HEAVY-ION DRIVERS  {R['drivers']['beams']} beams, {R['drivers']['linac_length_m']:.0f} m linacs"),
        ('Plume', (L3['x']-80, 0, -30), f"EXHAUST  {c['ve_km_s']:.0f} km/s, {c['thrust_MN']:.2f} MN"),
        ('Wings', ((lay['wing_aft_x']+lay['wing_forward_x'])/2, 0, 60), f"RADIATOR WINGS  {sel['tip_radius_m']:.0f} m tip radius (W{sel['wings']})"),
    ]
    for nm, loc, body in rows:
        P(out, f'FDP1_Label_{nm}', '12', 'SERVICE', 'text', location=loc, body=body, size=S, facing='side', status='ILLUSTRATIVE')
    return out
