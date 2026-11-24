"""AMPN Phase 1: audit of the RON 0.2 results (work, noncanonical; standard library only).

  python3 lab/studies/vertex-compact-engine/vertex-ampn/audit.py [--n 4000]      writes results/audit.json and results/audit.log

1. Thermal ledger reconciliation: absorbed, deposited, emitted (Stefan-Boltzmann with the actual one- and two-sided areas, emissivity,
   view factor) per part, the shadow plug's 24.3 GW against its cone face and fins, neutron deposition and transmission through the plug
   to the ship, cryogenic loads with refrigerator power and its rejected heat, pulsed (20 kHz) surface heating and field-perturbation
   (AC) losses in and around the superconducting ring.
2. Charged-particle convergence: hit, forward and directed shares against the number of launch directions, with binomial bounds.
3. Spacecraft-interception criterion replacing the RON forward-cone cant rule: forward escapers traced on straight lines from their exit
   state to the ship's actual position and cross-section, the own plug and the neighbouring engines' booms, over all azimuths.
"""
import json
import math
import sys
import time
from multiprocessing import Pool
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent/'vertex-ron'))
import ron  # noqa: E402

SIGMA = 5.670374e-8
SHIP_L = 289.5
# Fast-neutron removal cross sections (cm^-1, ESTIMATE for a fusion-product spectrum of mean ~7 MeV; fission-spectrum tables give
# W 0.12-0.13, LiH 0.12-0.14) and densities (kg/m3). Removal ~ the fraction scattered out of the direct beam (it does not mean absorbed).
REMOVAL = {'W': (0.12, 19300.0), 'LiH': (0.13, 780.0), 'B4C': (0.11, 2520.0)}


def log(lines, s):
    print(s, flush=True); lines.append(s)


# ----------------------------------------------------------------------------------------------------------------------------------
# 1. Thermal
# ----------------------------------------------------------------------------------------------------------------------------------

def thermal(v, k, src, led, lines, E):
    Pb, Ps, Pn = src['P_brems_W'], src['P_sync_W'], src['P_n_W']; Prad = Pb+Ps
    out = {}
    eps = 0.85
    q23 = eps*SIGMA*2300.0**4; q20 = eps*SIGMA*2000.0**4
    # --- plug ------------------------------------------------------------------------------------------------------------------
    pl = next(r for r in led['rows'] if r['part'] == 'PLUG')
    xp, rp = v['plug_x_m'], v['plug_r_m']; a = math.radians(v['plug_graze_deg'])
    sky_disc = (1-math.cos(math.atan(rp/xp)))/2                       # solid-angle fraction of the plug's disc from the burn
    A_face = math.pi*rp*rp/math.sin(a)                                 # lit outer cone face, one-sided (the ledger's radiating area)
    F_face = 0.97                                                      # view factor face -> space (ring and neighbours ~3 %, ESTIMATE)
    fin2 = pl.get('fin_m2', 0.0)                                       # two-sided fin area (fin_area() returns two-sided)
    eta_fin = 0.7
    # RON booked 0.9 Pn of the plug's sky as absorbed. A 15 kg/m2 W skin at 5 deg grazing is 17 g/cm2 along the ray: it scatters
    # 1-exp(-0.12*0.89)=10 % of the neutrons out of the beam and deposits about 5 % of their energy (elastic recoil on A=184 is <2 %;
    # inelastic gammas mostly escape a 0.8 mm skin). So the plug absorbs ~0.5 % of its neutron sky, and ~90 % reaches the ship.
    path_cm = 15.0/REMOVAL['W'][1]/math.sin(a)*100
    removed = 1-math.exp(-REMOVAL['W'][0]*path_cm)
    dep_n = 0.05*removed
    P_abs_ph = pl['sky']*Prad; P_abs_n_ron = pl['sky']*0.9*Pn; P_abs_n = pl['sky']*dep_n*Pn
    P_emit_face = F_face*q23*A_face; P_emit_fin = eta_fin*q23*fin2
    out['plug'] = dict(x_m=xp, r_m=rp, graze_deg=v['plug_graze_deg'], sky_ledger=pl['sky'], sky_disc_check=sky_disc,
                       face_one_sided_m2=A_face, fins_two_sided_m2=fin2, fin_plate_m2=fin2/2, emissivity=eps, F_face_space=F_face,
                       q_2300K_W_m2=q23, absorbed_photon_W=P_abs_ph, absorbed_neutron_ron_W=P_abs_n_ron, absorbed_neutron_audit_W=P_abs_n,
                       emitted_face_W=P_emit_face, emitted_fins_W=P_emit_fin, ledger_self_W=pl['self_W'],
                       balance_ron_W=P_abs_ph+P_abs_n_ron-(P_emit_face+P_emit_fin)/F_face*F_face,
                       T_audit_no_fins_K=((P_abs_ph+P_abs_n)/(eps*SIGMA*F_face*A_face))**0.25,
                       fins_needed_audit_m2=max(0.0, (P_abs_ph+P_abs_n-P_emit_face)/(eta_fin*q23)),
                       neutron_removed_in_skin=removed)
    o = out['plug']
    log(lines, f"PLUG x {xp:.0f} m r {rp:.1f} m graze {v['plug_graze_deg']:.0f} deg | sky {pl['sky']:.3e} (disc {sky_disc:.3e}) | face {A_face:,.0f} m2 one-sided, "
               f"fins {fin2:,.0f} m2 two-sided ({fin2/2:,.0f} m2 plate)")
    log(lines, f"     absorbed photons {P_abs_ph/1e9:.2f} GW + neutrons RON {P_abs_n_ron/1e9:.2f} GW (audit {P_abs_n/1e9:.3f} GW) | emitted face "
               f"{P_emit_face/1e9:.2f} GW + fins {P_emit_fin/1e9:.2f} GW = {(P_emit_face+P_emit_fin)/1e9:.2f} GW (ledger {pl['self_W']/1e9:.2f} GW per engine)")
    log(lines, f"     audit: no fins needed? T without fins {o['T_audit_no_fins_K']:.0f} K, fins needed {o['fins_needed_audit_m2']:.0f} m2; four plugs "
               f"{4*(P_abs_ph+P_abs_n)/1e9:.1f} GW (RON 24.3 GW)")
    # --- neutrons to the ship ---------------------------------------------------------------------------------------------------
    sky_ship = (1-math.cos(math.atan(v['r_ship_m']/v['D_m'])))/2
    P_ship_n = sky_ship*Pn*(1-dep_n)                                   # scattered neutrons stay roughly forward: no credit taken
    out['ship_neutrons'] = dict(sky_ship=sky_ship, per_engine_W=P_ship_n, four_W=4*P_ship_n)
    log(lines, f"SHIP neutrons: sky {sky_ship:.3e}, {P_ship_n/1e6:.0f} MW per engine, {4*P_ship_n/1e9:.2f} GW for four engines: NOT in the RON ledger")
    # shadow-shield slug for a target (LiH + W), mass = projected area x column; at the plug base (radius rp)
    rows = []
    for target in (1e9, 1e8, 1e7, 1e6):
        efolds = max(0.0, math.log(4*P_ship_n/target))
        col_LiH = efolds/REMOVAL['LiH'][0]/100*REMOVAL['LiH'][1]          # kg/m2 along the ray
        m = math.pi*rp*rp*col_LiH/1e3*1.15                                 # +15 % W gamma layer and canning (PROTOTYPE)
        heat = 4*P_ship_n*(1-math.exp(-efolds))/4                           # deposited in the slug, per engine (self-radiated, inside the plug cone)
        rows.append(dict(target_four_W=target, efolds=efolds, LiH_kg_m2=col_LiH, slug_t=m, slug_heat_W=heat, thickness_m=col_LiH/780))
        log(lines, f"     slug for <= {target/1e6:7.0f} MW at the ship (four engines): {efolds:4.1f} e-folds, LiH {col_LiH/780:4.2f} m, {m:6.0f} t per engine, "
                   f"{heat/1e9:.2f} GW deposited in it")
    out['slug'] = rows
    # --- coil noses ---------------------------------------------------------------------------------------------------------------
    for r in led['rows']:
        if r['part'].startswith('RING'):
            c = next(c for c in v['coils'] if c['name'] == r['part'])
            Ln = r['nose_m']; A2 = 2*Ln*2*math.pi*ron.hoop_r(c)
            # nose deposition: W-B4C of length Ln along the ray deposits most of the neutron energy (moderation + capture); RON booked 0.3
            dep = 1-math.exp(-Ln/0.25)
            P_ph = r['sky']*(Pb+Ps*(1-ron.mpn.far_ir_wall(2.0e6, 1e12))); P_nn = r['sky']*dep*Pn
            T_bare = ((P_ph+P_nn)/(eps*SIGMA*A2))**0.25
            fins = max(0.0, (P_ph+P_nn-q20*A2)/(0.7*q20))
            out[r['part']] = dict(nose_m=Ln, flank_two_m2=A2, absorbed_ron_W=r['absorbed_W'], photon_W=P_ph, neutron_dep_audit_W=P_nn,
                                  neutron_dep_fraction=dep, T_bare_K=T_bare, fins_needed_m2=fins, fins_ron_m2=r.get('fin_m2', 0.0))
            log(lines, f"{r['part']} nose {Ln:.2f} m, flanks {A2:,.0f} m2 | absorbed RON {r['absorbed_W']/1e9:.3f} GW, audit {(P_ph+P_nn)/1e9:.3f} GW "
                       f"(neutron deposition {dep:.2f} vs 0.30) | bare {T_bare:.0f} K, fins {fins:.0f} m2 (RON {r.get('fin_m2', 0):.0f})")
    # --- cryogenic chain ----------------------------------------------------------------------------------------------------------
    cold_n = sum(r['cold_W'] for r in led['rows'])
    A_cryo = sum(2*(c['depth']+c['thick'])*2*math.pi*ron.hoop_r(c) for c in v['coils'])
    static = 1.0*A_cryo                                                # W at 20 K through 30-layer MLI behind a 2,000 K nose: ~1 W/m2 (ESTIMATE)
    cold = cold_n+static
    elec = cold*(k['cold_cost']-1)
    out['cryo'] = dict(neutron_W=cold_n, static_W=static, cryostat_m2=A_cryo, total_20K_W=cold, refrigerator_electric_W=elec, rejected_W=cold+elec)
    log(lines, f"CRYO per engine: neutrons {cold_n/1e3:.1f} kW + static {static/1e3:.1f} kW = {cold/1e3:.1f} kW at 20 K -> refrigerator {elec/1e6:.1f} MW "
               f"electric, {(cold+elec)/1e6:.1f} MW rejected warm (four: {4*(cold+elec)/1e6:.0f} MW)")
    # --- pulsed loads ---------------------------------------------------------------------------------------------------------------
    f = v['f_pulse_Hz']; q_face = Prad/(4*math.pi*xp*xp)*math.sin(a)
    dT = q_face/f/(19300*134*50e-6)                                    # per-pulse X-ray energy into the first 50 um of W
    out['pulse_surface'] = dict(q_W_m2=q_face, J_m2_per_pulse=q_face/f, dT_K=dT)
    log(lines, f"PULSE plug surface: {q_face/1e6:.2f} MW/m2 mean, {q_face/f:.0f} J/m2 per pulse, surface swing {dT:.2f} K (negligible)")
    # field perturbation: the captured pulse compresses the ring field each pulse. dW/W ~ E/W at the capture surface; at the winding
    # dB/B ~ eps_c E/(2W) with an unknown coupling eps_c (0.1-1, nominal 0.3; a plasma-coupled model is needed, Vertex 1.4 class).
    c = v['coils'][0]
    I = abs(c['I'])*led['_k']; B_w = 4e-7*math.pi*I/(2*c['depth'])        # field at the winding of a ribbon of depth d (sheet estimate)
    W = led['_W']; A_w = 2*c['depth']*2*math.pi*ron.hoop_r(c)              # winding surface facing the perturbation (both faces)
    sig = 1.9e6; delta = 1/math.sqrt(math.pi*f*4e-7*math.pi*sig)             # Mo at ~1,500-2,000 K
    rows = []
    for eps_c in (0.1, 0.3, 1.0):
        dB = eps_c*E/(2*W)*B_w; H = dB/(4e-7*math.pi)
        Pa = H*H/(2*sig*delta); P = Pa*A_w
        T = (Pa/(eps*SIGMA))**0.25
        mu0 = 4e-7*math.pi; Jc = 3e8
        q_bean = lambda b: (2/3)*b**3/(mu0*mu0*Jc)*f                         # W/m2, Bean slab surface, b << full penetration
        rows.append(dict(eps_c=eps_c, dB_over_B=dB/B_w, dB_T=dB, shield_W_m2=Pa, shield_W=P, shield_T_K=T,
                         winding_unshielded_20K_W=q_bean(dB)*A_w, winding_3delta_20K_W=q_bean(dB*math.exp(-3))*A_w,
                         shield_3delta_t=A_w*3*delta*10200/1e3))
        log(lines, f"AC   coupling {eps_c:.1f}: dB/B {dB/B_w:.4f} ({dB:.3f} T at {B_w:.1f} T) | Mo eddy shield 3 skin depths ({3*delta*1e3:.1f} mm, "
                   f"{A_w*3*delta*10200/1e3:.0f} t): {Pa/1e3:6.1f} kW/m2 -> {P/1e9:5.2f} GW per engine at {T:4.0f} K | winding at 20 K: unshielded "
                   f"{q_bean(dB)*A_w/1e6:8.1f} MW, behind the shield {q_bean(dB*math.exp(-3))*A_w/1e3:6.2f} kW")
    out['ac'] = dict(B_winding_T=B_w, winding_m2=A_w, skin_m=delta, rows=rows, fatigue_cycles=f*k['burn_s'])
    log(lines, f"     fatigue: {f*k['burn_s']:.2e} load cycles over four burns (giga-cycle regime: stress amplitude must stay below the endurance limit)")
    return out


# ----------------------------------------------------------------------------------------------------------------------------------
# 2. Spacecraft interception
# ----------------------------------------------------------------------------------------------------------------------------------

def _rot(p, ang):
    c, s = math.cos(ang), math.sin(ang)
    return (p[0], c*p[1]-s*p[2], s*p[1]+c*p[2])


def _cant(p, c):
    """Engine frame -> flight frame: the engine axis is canted by c away from the ship (toward -y)."""
    cc, s = math.cos(c), math.sin(c)
    return (cc*p[0]+s*p[1], -s*p[0]+cc*p[1], p[2])


def _line_cyl_x(P, U, y0, z0, R, x0, x1):
    """Does the ray P + t U (t > 0) pass within R of the line (y0, z0) parallel to x, for x in [x0, x1]?"""
    dy, dz = P[1]-y0, P[2]-z0
    a = U[1]**2+U[2]**2; b = 2*(dy*U[1]+dz*U[2]); cc = dy*dy+dz*dz-R*R
    if a < 1e-15:
        return cc <= 0 and U[0] > 0 and P[0] < x1
    disc = b*b-4*a*cc
    if disc < 0:
        return False
    r = math.sqrt(disc); t0, t1 = (-b-r)/(2*a), (-b+r)/(2*a)
    if U[0] > 1e-12:
        ta, tb = (x0-P[0])/U[0], (x1-P[0])/U[0]
    else:
        return False
    lo, hi = max(t0, ta, 0.0), min(t1, tb)
    return lo <= hi


def _ray_seg(P, U, A, B, R):
    """Closest approach of ray P + tU (t > 0) to segment A-B below R?"""
    d = [B[i]-A[i] for i in range(3)]; w = [P[i]-A[i] for i in range(3)]
    a = sum(x*x for x in U); b = sum(U[i]*d[i] for i in range(3)); c = sum(x*x for x in d)
    dd = sum(U[i]*w[i] for i in range(3)); e = sum(d[i]*w[i] for i in range(3))
    den = a*c-b*b
    if den < 1e-12:
        return False
    t = max(0.0, (b*e-c*dd)/den); s = max(0.0, min(1.0, (a*e-b*dd)/den))
    q = [P[i]+t*U[i]-(A[i]+s*d[i]) for i in range(3)]
    return sum(x*x for x in q) <= R*R


def intercept(v, exits, cant_deg, P_charged, n_phi=360):
    """Charged power striking the ship, the own plug and the neighbours' booms, from the forward escapers, over all azimuths."""
    D, S, rs = v['D_m'], v['S_m'], v['r_ship_m']; ds = S/math.sqrt(2); c = math.radians(cant_deg)
    xp, rp = v['plug_x_m'], v['plug_r_m']
    L = math.hypot(D, ds); u_s = (D/L, ds/L, 0.0)                      # own plug on the burn -> ship-aft line (flight frame)
    pc = tuple(u_s[i]*xp for i in range(3))
    corners = [(ds, ds), (ds, -ds), (2*ds, 0.0)]                       # the other engines in (y, z), ship axis at (ds, 0)
    booms = []
    for cy, cz in corners:
        ux, uy, uz = D, ds-cy, -cz; Lb = math.sqrt(ux*ux+uy*uy+uz*uz)
        a = (xp*ux/Lb, cy+xp*uy/Lb, cz+xp*uz/Lb); booms.append((a, (D, ds, 0.0)))
    booms.append((pc, (D, ds, 0.0)))
    ship = plug = boom = 0.0
    for e in exits:
        for j in range(n_phi):
            ph = 2*math.pi*j/n_phi
            P = _cant(_rot(e['x'], ph), c); U = _cant(_rot(e['u'], ph), c)
            w = e['w']/n_phi*P_charged
            # plug: crossing of the plane through pc normal to u_s, within rp
            un = sum(U[i]*u_s[i] for i in range(3))
            if un > 1e-9:
                t = sum((pc[i]-P[i])*u_s[i] for i in range(3))/un
                if t > 0:
                    q = [P[i]+t*U[i]-pc[i] for i in range(3)]
                    if sum(x*x for x in q) <= rp*rp:
                        plug += w; continue
            if _line_cyl_x(P, U, ds, 0.0, rs, D, D+SHIP_L):
                ship += w; continue
            if any(_ray_seg(P, U, a, b, 2.5) for a, b in booms):
                boom += w
    return dict(ship_W=ship, plug_W=plug, booms_W=boom)


def min_cant(v, exits, P_charged, ship_max=1e8, plug_max=3e8, n_phi=180):
    rows = []
    for cd in [x*0.5 for x in range(0, 61)]:
        r = intercept(v, exits, cd, P_charged, n_phi); r['cant_deg'] = cd; rows.append(r)
        if r['ship_W'] <= ship_max and r['plug_W'] <= plug_max and r['booms_W'] <= plug_max:
            return cd, rows
    return None, rows


# ----------------------------------------------------------------------------------------------------------------------------------

def wilson(kk, n, z=1.96):
    if n == 0:
        return (0.0, 1.0)
    p = kk/n; d = 1+z*z/n; cen = (p+z*z/(2*n))/d; h = z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/d
    return (max(0.0, cen-h), min(1.0, cen+h))


def main():
    n_big = int(sys.argv[sys.argv.index('--n')+1]) if '--n' in sys.argv else 4000
    t0 = time.time(); lines = []; out = {}
    (HERE/'results').mkdir(exist_ok=True)
    k = ron.canon(); V = ron.variants()
    cases = [('B_D800', 1.6), ('E_hybrid_4_S250', 2.5), ('B_D500', 1.6)]
    with Pool(4) as pool:
        for name, mult in cases:
            p = V[name]; v, src, E, cap = ron.configure(p, k)
            log(lines, f"=== {name} at {mult}x capture current ===")
            conv = []
            for n in sorted({160, 640, 2560, n_big}):
                r = ron.evaluate(v, k, src, E, cap, mult, pool, n)
                part = r['particles']
                sp = {s: dict(hit=d['hit'], fwd=d['forward'], fwd_ci=wilson(round(d['forward']*n), n), hit_upper95=d['hit_upper95'])
                      for s, d in part['species'].items()}
                conv.append(dict(n=n, hit=part['hit_energy_share'], fwd=part['forward_energy_share'], eta=part['axial_efficiency'], species=sp))
                log(lines, f"  n {n:5d}/species: hit {part['hit_energy_share']:.5f} fwd {part['forward_energy_share']:.5f} eta {part['axial_efficiency']:.4f} | "
                           + ' '.join(f"{s} fwd {d['fwd']:.4f} [{d['fwd_ci'][0]:.4f}, {d['fwd_ci'][1]:.4f}] hit<{d['hit_upper95']:.1e}" for s, d in sp.items()))
            led = r['ledger']; led['_k'] = r['capture']['k']; led['_W'] = r['capture']['W_J']
            th = thermal(v, k, src, led, lines, E)
            Pc = src['P_charged_W']; exits = part['forward_exits']
            cant0 = intercept(v, exits, 0.0, Pc)
            log(lines, f"  INTERCEPT at cant 0: ship {cant0['ship_W']/1e9:.3f} GW, own plug {cant0['plug_W']/1e9:.3f} GW, booms {cant0['booms_W']/1e9:.3f} GW "
                       f"(ship offset {math.degrees(math.atan(v['S_m']/math.sqrt(2)/v['D_m'])):.1f} deg; RON cant {r['cant_deg']:.1f} deg)")
            cd, rows = min_cant(v, exits, Pc)
            log(lines, f"  minimum cant for ship <= 0.1 GW, plug and booms <= 0.3 GW: {cd} deg")
            eng = r['engine_t']
            sh_ron = r['ship']; sh_new = ron.ship(k, eng, 4*led['B01_W'], part['axial_efficiency'], cant_deg=cd if cd is not None else 30.0)
            log(lines, f"  departure: RON rule {sh_ron['departure_t']:,.0f} t (cant {r['cant_deg']:.1f}) -> interception rule {sh_new['departure_t']:,.0f} t "
                       f"(cant {cd}) before the audit's added masses")
            out[name] = dict(mult=mult, convergence=conv, thermal=th, intercept_cant0=cant0, cant_scan=rows, min_cant_deg=cd,
                             engine_t=eng, departure_ron_t=sh_ron['departure_t'], departure_intercept_t=sh_new['departure_t'],
                             ron_cant_deg=r['cant_deg'], eta=part['axial_efficiency'], n_exits=len(exits))
    out['wall_s'] = time.time()-t0
    (HERE/'results'/'audit.json').write_text(json.dumps(out, indent=1, default=str))
    (HERE/'results'/'audit.log').write_text('\n'.join(lines)+'\n')


if __name__ == '__main__':
    main()
