"""Vertex 2.11 Stern Mirror: 1D electrostatic particle-in-cell model of the reflector stack (research, not canon).

One planar column through the mirror, normal to the stern disk (x = depth into the mirror, from the grounded entrance grid at x = 0):

    entrance grid (0 V, transparency T) | suppressor grid (-V_s, T) | graded decelerating grids (T) ... | solid reflector plate (V_top)

Physics in the model
- Kinetic ions (relativistic leapfrog), several species and energy spectra, injected as the pulsed forward stream: each pulse's ions are
  born within tau_s at the burn point and arrive after their time of flight over L_tof (244 m), so species and energies separate in time.
  Periodic pulse train (period tau_p); the last period is diagnosed after the earlier ones have set the periodic state.
- Space charge of ions and electrons on a uniform grid (CIC deposit, Lewis energy-conserving field: E is the derivative of the linear
  potential, constant per cell). Fixed-potential electrodes are Dirichlet nodes; the transparency T of a grid is the chance that a
  particle crossing its plane survives.
- The stream's electrons in front of the suppressor: isothermal Boltzmann fluid (n_e0 = ion density at the entrance, T_e); behind the
  suppressor no stream electron is present (leakage exp(-V_s/T_e) is reported separately).
- Electrode interception: an intercepted particle deposits its kinetic energy as heat in that electrode and its charge on it; the charge
  times the electrode potential is electrical energy taken by (ions) or drawn from (electrons) the high-voltage system.
- Secondary electrons: yield per intercepted ion scales with electronic stopping at the impact energy (gamma_p = Y_p at 1 MeV/u, x Z^2),
  an escape factor f_esc for magnetic or geometric suppression; secondaries are kinetic macro-electrons (relativistic, sub-cycled) that
  accelerate toward higher potential and are intercepted or absorbed like ions; photoelectrons from the isotropic X-ray load are an
  optional source on every grid.
- Diagnostics: reflected, intercepted, plate, electrical and escaped energy per window; energy closure with the supply work (exact
  theorem for fixed-potential electrodes), charge closure, surface fields at every electrode, potential maximum (virtual anode),
  reflected-power time series.

Not in the model (handled elsewhere in 2.11 or stated as open): transverse motion and grid-lens scattering (3D check), oblique two-stream
modes (needs 2D/3D PIC), wire-scale field enhancement and real breakdown (breakdown screen), neutral gas, sputtering, electron
backscatter and electron-induced secondaries, X-rays from electron impact.
"""
import math

import numpy as np
from numba import njit

QE = 1.602176634e-19; EPS0 = 8.8541878128e-12; C = 2.99792458e8; ME = 9.1093837015e-31; AMU = 1.66053906660e-27
MEV = 1e6*QE
SPECIES = {   # name: (mass kg, charge number)
    'p': (1.007276*AMU, 1), 'D': (2.013553*AMU, 1), 'T': (3.015501*AMU, 1), 'He3': (3.014932*AMU, 2), 'alpha': (4.001506*AMU, 2)}


def stopping_rel(E_per_u_MeV):
    """Electronic stopping of a bare ion per Z^2 relative to 1 MeV/u (Bethe above 0.3 MeV/u, sqrt below; metal target, I 300 eV)."""
    def bethe(e):
        g = 1+e/931.494; b2 = 1-1/g**2
        return max(math.log(2*0.511e6*b2*g*g/300.0)-b2, 0.1)/b2
    e = max(E_per_u_MeV, 1e-4)
    if e >= 0.3:
        return bethe(e)/bethe(1.0)
    return bethe(0.3)/bethe(1.0)*math.sqrt(e/0.3)


def gamma_table(n=400, emax=30.0):
    """Tabulated relative yield vs MeV/u for numba (linear in energy)."""
    es = np.linspace(0.0, emax, n)
    return es, np.array([stopping_rel(e) for e in es])


@njit(cache=True)
def _thomas(a, b, c, d):
    n = d.size
    cp = np.empty(n); dp = np.empty(n); x = np.empty(n)
    cp[0] = c[0]/b[0]; dp[0] = d[0]/b[0]
    for i in range(1, n):
        m = b[i]-a[i]*cp[i-1]
        cp[i] = c[i]/m; dp[i] = (d[i]-a[i]*dp[i-1])/m
    x[n-1] = dp[n-1]
    for i in range(n-2, -1, -1):
        x[i] = dp[i]-cp[i]*x[i+1]
    return x


@njit(cache=True)
def solve_phi(rho, fixed, fval, dx, kb, ne0, Te, phi):
    """Poisson with Dirichlet electrode nodes; Boltzmann electrons on nodes 1..kb-1 (Newton). Returns phi."""
    N = rho.size
    a = np.zeros(N); b = np.zeros(N); c = np.zeros(N); d = np.zeros(N)
    k = dx*dx/EPS0
    for it in range(30 if (kb > 1 and ne0 > 0.0) else 1):
        for i in range(N):
            if fixed[i]:
                a[i] = 0.0; b[i] = 1.0; c[i] = 0.0; d[i] = fval[i]-phi[i]
            else:
                ex = 0.0; dex = 0.0
                if i < kb and ne0 > 0.0:
                    arg = min(phi[i]/Te, 50.0)
                    ex = QE*ne0*math.exp(arg); dex = ex/Te
                f = phi[i-1]-2*phi[i]+phi[i+1]+k*(rho[i]-ex)
                a[i] = 1.0; b[i] = -2.0-k*dex; c[i] = 1.0; d[i] = -f
        dphi = _thomas(a, b, c, d)
        mx = 0.0
        for i in range(N):
            phi[i] += dphi[i]
            if abs(dphi[i]) > mx:
                mx = abs(dphi[i])
        if mx < 1e-6*Te+1e-3:
            break
    return phi


@njit(cache=True)
def _ke(u, m):
    return (math.sqrt(1.0+(u/C)**2)-1.0)*m*C*C


@njit(cache=True)
def run_core(dx, N, dt, nsteps, t_diag0, sample_every,
             el_node, el_V, el_T, el_is_supp, kb, Te, boltz_on,
             inj_t, inj_u, inj_s, inj_w,
             sp_m, sp_q, sp_Z, sp_A, gam_e, gam_v, Yp, f_esc, sec_on,
             ph_rate, ph_every, seed, cap_i, cap_e, sc_on):
    np.random.seed(seed)
    L = (N-1)*dx
    nel = el_node.size
    fixed = np.zeros(N, np.bool_); fval = np.zeros(N); elmap = -np.ones(N, np.int64)
    for k in range(nel):
        fixed[el_node[k]] = True; fval[el_node[k]] = el_V[k]; elmap[el_node[k]] = k
    # ions
    xi = np.zeros(cap_i); ui = np.zeros(cap_i); si = np.zeros(cap_i, np.int64); wi = np.zeros(cap_i); ni = 0
    # electrons
    xe = np.zeros(cap_e); ue = np.zeros(cap_e); we = np.zeros(cap_e); ne_ = 0
    phi = np.zeros(N); rho = np.zeros(N); Ec = np.zeros(N-1)
    for i in range(N):
        phi[i] = np.interp(i*dx, el_node.astype(np.float64)*dx, el_V)
    phi = solve_phi(rho, fixed, fval, dx, 0, 0.0, Te, phi)
    for j in range(N-1):
        Ec[j] = -(phi[j+1]-phi[j])/dx
    # diagnostics in the window t >= t_diag0
    acc = np.zeros(16)   # 0 E_in, 1 Q_in, 2 E_ref, 3 Q_ref, 4 E_e_up, 5 Q_e_up, 6 E_plate_overV (ions > V_top), 7 n_sec, 8 E_ph_src,
    #                      9 lost_cap, 10 E_ref_window_count, 11 Q_e_plate, 12 E_leak, 13 spare
    heat_i = np.zeros(nel); heat_e = np.zeros(nel); Qc_i = np.zeros(nel); Qc_e = np.zeros(nel)
    Esurf = np.zeros((nel, 2))          # max |E| on the upstream and downstream face of each electrode in the window
    sig0 = np.zeros(nel); sig1 = np.zeros(nel); W0 = 0.0; W1 = 0.0; KE0 = 0.0; KE1 = 0.0
    nsamp = nsteps//sample_every+2
    ts_ref = np.zeros(nsamp); ts_in = np.zeros(nsamp); ts_phimax = np.zeros(nsamp); ts_xmax = np.zeros(nsamp)
    ts_ref_cur = 0.0; ts_in_cur = 0.0
    sp_E_in = np.zeros(sp_m.size); sp_E_ref = np.zeros(sp_m.size); sp_E_int = np.zeros(sp_m.size); sp_E_plate = np.zeros(sp_m.size)
    phimax_window = -1e30
    ptr = 0; ninj = inj_t.size
    nsub = int(math.ceil(C*dt/(0.4*dx)))
    dte = dt/nsub
    in_window = False
    for step in range(nsteps):
        t = step*dt
        if (not in_window) and t >= t_diag0:
            in_window = True
            for k in range(nel):
                j = el_node[k]
                el_ = Ec[j-1] if j > 0 else 0.0
                er_ = Ec[j] if j < N-1 else 0.0
                sig0[k] = EPS0*(er_-el_)
            W0 = 0.0
            for j in range(N-1):
                W0 += 0.5*EPS0*Ec[j]*Ec[j]*dx
            KE0 = 0.0
            for p in range(ni):
                KE0 += wi[p]*_ke(ui[p], sp_m[si[p]])
            for p in range(ne_):
                KE0 += we[p]*_ke(ue[p], ME)
        # ---- injection (particles placed just inside x = 0 after crossing the entrance grid)
        while ptr < ninj and inj_t[ptr] < t+dt:
            s = inj_s[ptr]; m = sp_m[s]; q = sp_q[s]; w = inj_w[ptr]; u = inj_u[ptr]
            ke = _ke(u, m)
            if in_window:
                acc[0] += w*ke; acc[1] += w*q; sp_E_in[s] += w*ke; ts_in_cur += w*ke
            if np.random.random() > el_T[0]:
                # intercepted by the entrance grid on the way in
                if in_window:
                    heat_i[0] += w*ke; Qc_i[0] += w*q; sp_E_int[s] += w*ke
                ptr += 1
                continue
            if ni < cap_i:
                g = math.sqrt(1.0+(u/C)**2)
                xi[ni] = min(u/g*(t+dt-inj_t[ptr]), 0.5*dx)
                ui[ni] = u; si[ni] = s; wi[ni] = w; ni += 1
            else:
                acc[9] += w*ke
            ptr += 1
        # ---- photoelectrons (constant source on each grid, both directions)
        if ph_rate > 0.0 and step % ph_every == 0:
            for k in range(1, nel-1):
                if ne_ < cap_e:
                    xe[ne_] = el_node[k]*dx+(1e-3*dx if np.random.random() < 0.5 else -1e-3*dx)
                    ue[ne_] = 0.0; we[ne_] = ph_rate*dt*ph_every; ne_ += 1
                    if in_window:
                        Qc_e[k] += ph_rate*dt*ph_every*QE; acc[8] += ph_rate*dt*ph_every
        # ---- charge deposit and field
        for j in range(N):
            rho[j] = 0.0
        if sc_on:
            for p in range(ni):
                f = xi[p]/dx; j = int(f); fr = f-j
                if j >= N-1:
                    j = N-2; fr = 1.0
                qq = wi[p]*sp_q[si[p]]/dx
                rho[j] += qq*(1-fr); rho[j+1] += qq*fr
            for p in range(ne_):
                f = xe[p]/dx; j = int(f); fr = f-j
                if j < 0:
                    j = 0; fr = 0.0
                if j >= N-1:
                    j = N-2; fr = 1.0
                qq = -we[p]*QE/dx
                rho[j] += qq*(1-fr); rho[j+1] += qq*fr
        ne0 = 0.0
        if boltz_on:
            # stream electron density at the entrance = local ion density (incoming + reflected), from the first cells
            ne0 = max(0.0, (rho[1]+rho[2]+rho[3])/3.0/QE) if sc_on else 0.0
        phi = solve_phi(rho, fixed, fval, dx, kb, ne0, Te, phi)
        for j in range(N-1):
            Ec[j] = -(phi[j+1]-phi[j])/dx
        if in_window:
            for k in range(nel):
                j = el_node[k]
                if j > 0 and abs(Ec[j-1]) > Esurf[k, 0]:
                    Esurf[k, 0] = abs(Ec[j-1])
                if j < N-1 and abs(Ec[j]) > Esurf[k, 1]:
                    Esurf[k, 1] = abs(Ec[j])
            pm = -1e30; xm = 0.0
            for j in range(N):
                if phi[j] > pm:
                    pm = phi[j]; xm = j*dx
            if pm > phimax_window:
                phimax_window = pm
        # ---- push ions
        p = 0
        while p < ni:
            s = si[p]; m = sp_m[s]; q = sp_q[s]; w = wi[p]
            x0 = xi[p]
            j = int(x0/dx)
            if j > N-2:
                j = N-2
            ui[p] += q*Ec[j]*dt/m
            g = math.sqrt(1.0+(ui[p]/C)**2)
            x1 = x0+ui[p]/g*dt
            dead = False
            # plane crossing (step < dx so at most one node)
            jn = -1
            if x1 > x0 and int(x1/dx) > int(x0/dx):
                jn = int(x1/dx)
            elif x1 < x0 and int(x0/dx) > int(x1/dx) and x1 >= 0.0:
                jn = int(x0/dx)
            if x1 >= L:
                jn = N-1
            if jn >= 0 and elmap[jn] >= 0:
                k = elmap[jn]
                if np.random.random() > el_T[k]:
                    # intercepted: kinetic energy at the plane = KE now + q (phi(x1) - V_k)
                    f = min(max(x1, 0.0), L)/dx; jj = min(int(f), N-2); fr = f-jj
                    ph1 = phi[jj]*(1-fr)+phi[jj+1]*fr
                    ke = _ke(ui[p], m)+q*(ph1-el_V[k])
                    if ke < 0.0:
                        ke = 0.0
                    if in_window:
                        heat_i[k] += w*ke; Qc_i[k] += w*q; sp_E_int[s] += w*ke
                        if k == nel-1:
                            sp_E_plate[s] += w*(ke+q*el_V[k])
                    if sec_on:
                        epu = ke/MEV/sp_A[s]
                        jt = int(epu/gam_e[1])
                        if jt > gam_e.size-2:
                            jt = gam_e.size-2
                        gy = Yp*gam_v[jt]*sp_Z[s]*sp_Z[s]*f_esc
                        nsec = int(gy)+(1 if np.random.random() < gy-int(gy) else 0)
                        for _ in range(nsec):
                            if ne_ < cap_e:
                                dirn = 1.0 if np.random.random() < 0.5 else -1.0
                                if k == nel-1:
                                    dirn = -1.0
                                if k == 0 and dirn < 0:
                                    continue
                                xe[ne_] = el_node[k]*dx+dirn*1e-3*dx
                                ue[ne_] = dirn*math.sqrt(2*2.0*QE/ME); we[ne_] = w; ne_ += 1
                                if in_window:
                                    acc[7] += w; Qc_e[k] += w*QE
                    dead = True
            if not dead and x1 < 0.0:
                # reflected out through the entrance grid (crossing tested above only for interior nodes)
                if np.random.random() > el_T[0]:
                    ke = _ke(ui[p], m)
                    if in_window:
                        heat_i[0] += w*ke; Qc_i[0] += w*q; sp_E_int[s] += w*ke
                else:
                    ke = _ke(ui[p], m)
                    if in_window:
                        acc[2] += w*ke; acc[3] += w*q; sp_E_ref[s] += w*ke; ts_ref_cur += w*ke
                dead = True
            if dead:
                ni -= 1
                xi[p] = xi[ni]; ui[p] = ui[ni]; si[p] = si[ni]; wi[p] = wi[ni]
                continue
            xi[p] = x1
            p += 1
        # ---- push electrons (sub-cycled)
        p = 0
        while p < ne_:
            dead = False
            w = we[p]
            for sb in range(nsub):
                x0 = xe[p]
                j = int(x0/dx)
                if j < 0:
                    j = 0
                if j > N-2:
                    j = N-2
                ue[p] += -QE*Ec[j]*dte/ME
                g = math.sqrt(1.0+(ue[p]/C)**2)
                x1 = x0+ue[p]/g*dte
                jn = -1
                if x1 > x0 and int(x1/dx) > int(x0/dx):
                    jn = int(x1/dx)
                elif x1 < x0 and x1 >= 0.0 and int(x0/dx) > int(x1/dx):
                    jn = int(x0/dx)
                if x1 >= L:
                    jn = N-1
                if x1 < 0.0:
                    if in_window:
                        acc[4] += w*_ke(ue[p], ME); acc[5] += -w*QE
                    dead = True
                    break
                if jn >= 0 and elmap[jn] >= 0:
                    k = elmap[jn]
                    if np.random.random() > el_T[k]:
                        f = min(x1, L)/dx; jj = min(int(f), N-2); fr = f-jj
                        ph1 = phi[jj]*(1-fr)+phi[jj+1]*fr
                        ke = _ke(ue[p], ME)-QE*(ph1-el_V[k])
                        if ke < 0.0:
                            ke = 0.0
                        if in_window:
                            heat_e[k] += w*ke; Qc_e[k] += -w*QE
                        dead = True
                        break
                xe[p] = x1
            if dead:
                ne_ -= 1
                xe[p] = xe[ne_]; ue[p] = ue[ne_]; we[p] = we[ne_]
                continue
            p += 1
        if step % sample_every == 0:
            js = step//sample_every
            ts_ref[js] = ts_ref_cur; ts_in[js] = ts_in_cur; ts_ref_cur = 0.0; ts_in_cur = 0.0
            pm = -1e30; xm = 0.0
            for j in range(N):
                if phi[j] > pm:
                    pm = phi[j]; xm = j*dx
            ts_phimax[js] = pm; ts_xmax[js] = xm
    # end of window
    for k in range(nel):
        j = el_node[k]
        el_ = Ec[j-1] if j > 0 else 0.0
        er_ = Ec[j] if j < N-1 else 0.0
        sig1[k] = EPS0*(er_-el_)
    for j in range(N-1):
        W1 += 0.5*EPS0*Ec[j]*Ec[j]*dx
    for p in range(ni):
        KE1 += wi[p]*_ke(ui[p], sp_m[si[p]])
    for p in range(ne_):
        KE1 += we[p]*_ke(ue[p], ME)
    acc[13] = ne0
    return (acc, heat_i, heat_e, Qc_i, Qc_e, Esurf, sig0, sig1, W0, W1, KE0, KE1, ts_ref, ts_in, ts_phimax, ts_xmax,
            sp_E_in, sp_E_ref, sp_E_int, sp_E_plate, phimax_window, phi.copy(), ni, ne_)


# ------------------------------------------------------------------ spectra and pulses

def spectrum(name, rng, n):
    """Return (species names, energies J) for n ions of the forward stream."""
    if isinstance(name, tuple):    # ('mono', species, E_MeV)
        _, nm, e = name
        return np.array([nm]*n), np.full(n, e*MEV)
    if name == 'thermal':          # 2.8 traced set: equal energy per ion (8.25 MeV), b 0.99, 3 % numerical spread
        sp = rng.choice(['p', 'alpha', 'D', 'He3'], size=n, p=[0.495, 0.495, 0.005, 0.005])
        E = 8.25*MEV*np.clip(rng.normal(1.0, 0.03, n), 0.5, 1.5)
    elif name == 'thermal_broad':  # same mean per ion, energy shared broadly (gamma distribution, sigma/mean 0.41)
        sp = rng.choice(['p', 'alpha', 'D', 'He3'], size=n, p=[0.495, 0.495, 0.005, 0.005])
        E = rng.gamma(6.0, 8.25/6.0, n)*MEV
    elif name == 'charge':         # equal energy per charge, mean 8.25 MeV per ion: E/q 5.5 MV
        sp = rng.choice(['p', 'alpha', 'D', 'He3'], size=n, p=[0.495, 0.495, 0.005, 0.005])
        Z = np.array([SPECIES[s][1] for s in sp])
        E = 5.5*MEV*Z*np.clip(rng.normal(1.0, 0.03, n), 0.5, 1.5)
    elif name == 'birth':          # unthermalized fusion products: D-He3 p 14.68 + alpha 3.67 MeV (Doppler spread at T_i ~50 keV),
        #                            D-D side reactions 3 % of the energy: p 3.02 + T 1.01 MeV, He-3 0.82 MeV (+ neutron, not charged)
        # numbers: D-He3 pairs : D-D reactions so that D-D carries 3 % of the charged energy
        e_dhe3 = 18.35; e_dd = 0.5*(3.02+1.01)+0.5*0.82
        r = 0.03/0.97*e_dhe3/e_dd               # D-D reactions per D-He3 reaction
        w = np.array([1, 1, 0.5*r, 0.5*r, 0.5*r]); w = w/w.sum()
        sp = rng.choice(['p', 'alpha', 'p_dd', 'T', 'He3'], size=n, p=w)
        E = np.empty(n)
        for nm, mu, sg in (('p', 14.68, 0.6), ('alpha', 3.67, 0.15), ('p_dd', 3.02, 0.15), ('T', 1.01, 0.08), ('He3', 0.82, 0.08)):
            k = sp == nm; E[k] = rng.normal(mu, sg, k.sum())*MEV
        sp = np.where(sp == 'p_dd', 'p', sp)
    else:
        raise ValueError(name)
    return sp, E


def make_injection(spec, S_W_m2, tau_p, n_per, n_mac, L_tof=244.0, tau_s=1.0e-6, seed=1):
    """Pulse train: per period n_mac macro-ions, equal number weight; energy flux S (W/m^2, time average)."""
    rng = np.random.default_rng(seed)
    names = list(SPECIES)
    ts, us, ss, ws = [], [], [], []
    for k in range(n_per):
        sp, E = spectrum(spec, rng, n_mac)
        m = np.array([SPECIES[s][0] for s in sp])
        g = 1+E/(m*C*C); v = C*np.sqrt(1-1/g**2); u = g*v
        t = k*tau_p+rng.random(n_mac)*tau_s+L_tof/v
        Ebar = E.mean()
        w = S_W_m2*tau_p/Ebar/n_mac
        ts.append(t); us.append(u); ss.append(np.array([names.index(s) for s in sp])); ws.append(np.full(n_mac, w))
    t = np.concatenate(ts); o = np.argsort(t)
    return t[o], np.concatenate(us)[o], np.concatenate(ss)[o], np.concatenate(ws)[o]


def stack(V_top, n_stage, d_stage, T, V_s=0.75e6, d_s=0.5, T_supp=None, T_entr=None):
    """Electrode list [(x, V, T)]: entrance grid, suppressor, n_stage equal steps to the solid plate at V_top."""
    els = [(0.0, 0.0, T if T_entr is None else T_entr), (d_s, -V_s, T if T_supp is None else T_supp)]
    for k in range(1, n_stage+1):
        V = -V_s+k*(V_top+V_s)/n_stage
        els.append((d_s+k*d_stage, V, T if k < n_stage else 0.0))
    return els


def run(els, spec='thermal', S_W_m2=8.5e6, tau_p=17.87e-6, n_per=2, n_mac=100000, dx=0.01, cfl=0.5, Te=50e3, boltz=True,
        Yp=1.0, f_esc=1.0, sec=True, ph_rate=0.0, seed=1, sc=True, L_tof=244.0, tau_s=1.0e-6, inj=None, t_end=None,
        t_diag0=None, sample_dt=5e-8, v_max=None):
    L = els[-1][0]
    N = int(round(L/dx))+1
    dx = L/(N-1)
    el_node = np.array([int(round(x/dx)) for x, _, _ in els], np.int64)
    el_V = np.array([v for _, v, _ in els], float); el_T = np.array([t for _, _, t in els], float)
    if len(set(el_node.tolist())) != len(els):
        raise ValueError('electrodes closer than dx')
    if inj is None:
        inj = make_injection(spec, S_W_m2, tau_p, n_per+1, n_mac, L_tof, tau_s, seed)
    t_in, u_in, s_in, w_in = inj
    names = list(SPECIES)
    sp_m = np.array([SPECIES[n][0] for n in names]); sp_Z = np.array([SPECIES[n][1] for n in names], float)
    sp_q = sp_Z*QE; sp_A = sp_m/AMU
    if v_max is None:
        g = np.sqrt(1+(u_in.max()/C)**2); v_max = max(u_in.max()/g, 1e6)
        # ions gain at most V_s on the way to the suppressor
        v_max *= 1.05
    dt = cfl*dx/v_max
    if t_end is None:
        t_end = n_per*tau_p+L_tof/v_max
    if t_diag0 is None:
        t_diag0 = t_end-tau_p
    nsteps = int(t_end/dt)
    se = max(1, int(sample_dt/dt))
    kb = int(el_node[1]) if boltz else 0
    gam_e, gam_v = gamma_table()
    cap_i = 400000; cap_e = 400000
    ph_every = 50
    out = run_core(dx, N, dt, nsteps, t_diag0, se, el_node, el_V, el_T, np.zeros(len(els), np.bool_), kb, Te, boltz,
                   t_in, u_in, s_in, w_in, sp_m, sp_q, sp_Z, sp_A, gam_e, gam_v, Yp, f_esc, sec, ph_rate, ph_every, seed,
                   cap_i, cap_e, sc)
    (acc, heat_i, heat_e, Qc_i, Qc_e, Esurf, sig0, sig1, W0, W1, KE0, KE1, ts_ref, ts_in, ts_phimax, ts_xmax,
     sp_E_in, sp_E_ref, sp_E_int, sp_E_plate, phimax_window, phi, ni, ne_) = out
    Ein = acc[0]
    supply = float(np.sum(el_V*((sig1-sig0)-(Qc_i+Qc_e))))
    heat = float(np.sum(heat_i+heat_e))
    closure = (Ein+supply-(acc[2]+acc[4]+heat+(KE1-KE0)+(W1-W0)))/max(Ein+abs(supply), 1e-30)
    elec = float(np.sum(el_V*(Qc_i+Qc_e)))
    window = t_end-t_diag0
    res = dict(
        L_m=L, dx=dx, dt=dt, nsteps=nsteps, N=N, window_s=window,
        E_in_J_m2=Ein, P_in_W_m2=Ein/window,
        reflect=acc[2]/Ein, heat=heat/Ein, heat_ion=float(np.sum(heat_i))/Ein, heat_elec=float(np.sum(heat_e))/Ein,
        electrical=elec/Ein, electrical_ion=float(np.sum(el_V*Qc_i))/Ein, electrical_elec=float(np.sum(el_V*Qc_e))/Ein,
        e_escape_up=acc[4]/Ein, closure=closure, boltz_on=boltz,
        charge_in=acc[1], charge_closure=(acc[1]-acc[3]-float(np.sum(Qc_i)))/max(acc[1], 1e-30),
        sec_per_ion=acc[7]/max(acc[1]/QE, 1e-30), lost_cap=acc[9]/max(Ein, 1e-30),
        electrodes=[dict(x=float(x), V=float(V), T=float(T), heat_frac=float((heat_i[k]+heat_e[k])/Ein),
                         heat_ion_frac=float(heat_i[k]/Ein), heat_elec_frac=float(heat_e[k]/Ein),
                         I_ion_A_m2=float(Qc_i[k]/window), I_elec_A_m2=float(Qc_e[k]/window),
                         heat_W_m2=float((heat_i[k]+heat_e[k])/window), Esurf_up_MV_m=float(Esurf[k, 0]/1e6),
                         Esurf_dn_MV_m=float(Esurf[k, 1]/1e6), E_vac_MV_m=0.0)
                    for k, (x, V, T) in enumerate(els)],
        species={n: dict(E_in=float(sp_E_in[i]/Ein), reflect=float(sp_E_ref[i]/max(sp_E_in[i], 1e-30)),
                         intercepted=float(sp_E_int[i]/max(sp_E_in[i], 1e-30)),
                         to_plate=float(sp_E_plate[i]/max(sp_E_in[i], 1e-30)))
                 for i, n in enumerate(names) if sp_E_in[i] > 0},
        phi_max_window_MV=float(phimax_window/1e6), V_top_MV=float(el_V[-1]/1e6),
        ts=dict(dt=se*dt, ref=(ts_ref/(se*dt)).tolist(), inn=(ts_in/(se*dt)).tolist(), phimax=(ts_phimax/1e6).tolist(),
                xmax=ts_xmax.tolist()),
        phi_end_MV=(phi[::max(1, N//200)]/1e6).tolist(), alive=(int(ni), int(ne_)),
        energy_terms=dict(E_in=Ein, supply=supply, ref=acc[2], e_up=acc[4], heat=heat, dKE=KE1-KE0, dW=W1-W0))
    # vacuum design field per gap (for the breakdown screen)
    for k in range(1, len(els)):
        g = els[k][0]-els[k-1][0]
        res['electrodes'][k]['E_vac_MV_m'] = abs(els[k][1]-els[k-1][1])/g/1e6
    return res
