"""Phase III member check (owner 3.3): the Phase II check (axial, resultant bending, beam-column, local shell) extended with
transverse shear, torsion, combined stress, torsional shell buckling, effective-length uncertainty and material anisotropy.

  stresses (ultimate, 1.4 x limit, applied once)
    sigma = N/A + M/S              M = resultant of My, Mz (biaxial; exact for a round tube)
    tau   = T r / (2 I) + 2 V / A  torsion + peak transverse shear of a thin tube, V = resultant of Vy, Vz
  checks
    strength (isotropic)  von Mises sqrt(sigma^2 + 3 tau^2) <= F (Fc in compression, Ft in tension)
    strength (composite)  (sigma/F)^2 + (tau/Fs)^2 <= 1 (Tsai-Hill form; Fs = in-plane shear design value, PROTO)
    beam-column           1.4 Nc / Pcr(K L) + sigma_b x amp / Fc, Euler with column knockdown, K = effective-length factor
    shell                 sigma / sigma_cr + (tau / tau_cr)^2 <= 1; sigma_cr = 0.33 x 0.605 E t/r, tau_cr = 0.67 x 0.747 E (t/r)^1.25 (r/L)^0.5
                          (Batdorf torsion of a moderately long cylinder; knockdown 0.67, LIT order). For an orthotropic tube E is the
                          axial modulus and the shell checks use sqrt(E_ax E_hoop) via the anisotropy ratio.
"""
import math
import sys
from pathlib import Path

import numpy as np

H = Path(__file__).resolve().parent
sys.path.insert(0, str(H.parent / 'phase2'))
import analysis as an  # noqa: E402
import model as mdl  # noqa: E402

LF = an.LF_ULT
K_EFF = 1.0                     # nominal effective-length factor (pin-ended between nodes); 1.2 as the uncertainty case
# composite in-plane shear design values and hoop/axial modulus ratios (PROTO, documented in the report)
FS_COMPOSITE = {'CFPEEK': 110e6, 'ALAL2O3F': 80e6, 'CC': 20e6, 'SICSIC': 60e6}
HOOP_RATIO = {'CFPEEK': 0.45, 'ALAL2O3F': 0.55, 'CC': 1.0, 'SICSIC': 1.0}


def envelope3(b, cs):
    env = an.envelope(b, cs)
    n = len(b.m.el); V = np.zeros(n)
    by = {}
    for c in cs:
        by.setdefault(c['left'], []).append(c)
    for lst in by.values():
        acs = next((c for c in lst if c.get('acs')), None)
        for c in lst:
            if c.get('acs'):
                continue
            s = abs(c['scale'])
            for i, f in enumerate(c['f']):
                if f is None:
                    continue
                v = s*math.hypot(f['Vy'], f['Vz'])
                if acs is not None and c['scale'] > 0:
                    fa = acs['f'][i]; v += math.hypot(fa['Vy'], fa['Vz'])
                V[i] = max(V[i], v)
    env['V'] = V
    return env


def check3(mat, A, I, S, r, t, L, Nc, Nt, M, T, V, K=K_EFF):
    E = mat['E']; mid = mat['id']; comp = mid in FS_COMPOSITE
    Le = np.maximum(K*L, 0.1)
    Pcr = an.KD_COL*math.pi**2*E*I/Le**2
    sc = LF*Nc/A; st = LF*Nt/A; sb = LF*M/S
    tau = LF*(T*r/(2*I) + 2*V/A)
    if comp:
        Fs = FS_COMPOSITE[mid]
        u_str = np.maximum(((sc+sb)/mat['Fc'])**2 + (tau/Fs)**2, ((st+sb)/mat['Ft'])**2 + (tau/Fs)**2)**0.5
        Eeff = E*math.sqrt(HOOP_RATIO[mid])
    else:
        u_str = np.maximum(np.sqrt((sc+sb)**2 + 3*tau**2)/mat['Fc'], np.sqrt((st+sb)**2 + 3*tau**2)/mat['Ft'])
        Eeff = E
    amp = 1.0/np.maximum(1.0-LF*Nc/Pcr, 1e-3)
    u_col = LF*Nc/Pcr + sb*amp/mat['Fc']
    s_cr = an.KD_SHELL*mdl.META['classic_shell_coeff']*Eeff*t/r
    tau_cr = 0.67*0.747*Eeff*(t/r)**1.25*np.sqrt(r/np.maximum(L, 0.1))
    u_sh = (sc+sb)/s_cr + (tau/tau_cr)**2
    return np.maximum.reduce([u_str, u_col, u_sh]), (u_str, u_col, u_sh)


def utilisation(b, env, K=K_EFF, which='full'):
    """Per-member ultimate utilisation for the current sections: Phase II check ('p2') or the full Phase III check ('full')."""
    u = np.zeros(len(b.m.el)); mode = [''] * len(b.m.el)
    for i, (e, md) in enumerate(zip(b.m.el, b.meta)):
        if e['kind'] == 'spring' or md['fam'] in ('iface', 'mount') or not e['on']:
            continue
        s = b.sec[md['group']]; mat = mdl.mat(s['mat'])
        A, I, S = an.tube_props(np.array(s['r']), np.array(s['t'])); L = b.m.frame(e)[0]
        if which == 'p2':
            v, parts = an.check(mat, A, I, S, s['r'], s['t'], L, env['Nc'][i], env['Nt'][i], env['M'][i])
        else:
            v, parts = check3(mat, A, I, S, s['r'], s['t'], L, env['Nc'][i], env['Nt'][i], env['M'][i], env['T'][i], env['V'][i], K)
        u[i] = float(v); mode[i] = ('strength', 'column', 'shell')[int(np.argmax([float(p) for p in parts]))]
    return u, mode


def size3(b, env, K=K_EFF):
    """Phase II grid sizing with the full Phase III check."""
    groups = {}
    for i, (e, md) in enumerate(zip(b.m.el, b.meta)):
        if e['kind'] == 'spring' or md['fam'] in ('iface', 'mount'):
            continue
        groups.setdefault(md['group'], []).append(i)
    rep = {}
    for g, idx in groups.items():
        s = b.sec[g]; mat = mdl.mat(s['mat'])
        L = np.array([b.m.frame(b.m.el[i])[0] for i in idx])
        Nc, Nt, M, T, V = (env[k][idx] for k in ('Nc', 'Nt', 'M', 'T', 'V'))
        if s['fam'] == 'tankwall':
            rr = np.array([s['r']]); tg = np.unique(np.concatenate([[s['tmin']], an.T_GRID[an.T_GRID > s['tmin']]]))
        else:
            rr = np.array([mdl.R_SPINE]) if s['fam'] in ('spine', 'hub') else an.R_GRID[an.R_GRID <= s['rmax']]; tg = an.T_GRID
        R, Tt = np.meshgrid(rr, tg, indexing='ij'); ok = (Tt >= max(mat['tmin'], s.get('tmin', 0.0))) & (Tt <= R/4); R, Tt = R[ok], Tt[ok]
        A, I, S = an.tube_props(R, Tt)
        u, _ = check3(mat, A[:, None], I[:, None], S[:, None], R[:, None], Tt[:, None], L[None, :], Nc[None, :], Nt[None, :], M[None, :],
                      T[None, :], V[None, :], K)
        umax = u.max(axis=1); mass = mat['rho']*A*L.sum(); good = umax <= 1.0
        k = np.argmin(np.where(good, mass, np.inf)) if good.any() else np.argmin(umax)
        s['r'], s['t'] = float(R[k]), float(Tt[k])
        rep[g] = dict(r=s['r'], t=s['t'], mat=s['mat'], util=float(umax[k]), mass_t=float(mass[k]/1e3), n=len(idx), L_m=float(L.sum()),
                      Nc_MN=float(Nc.max()/1e6), Nt_MN=float(Nt.max()/1e6), M_MNm=float(M.max()/1e6), T_MNm=float(T.max()/1e6),
                      V_MN=float(V.max()/1e6), passes=bool(good.any()))
    b.update_sections()
    return rep


def run3(b, states, iters=4, K=K_EFF, log=None):
    hist = []
    for k in range(iters):
        cs = an.cases(b, states); env = envelope3(b, cs); rep = size3(b, env, K)
        sm = b.structure_mass()[0]/1e3; hist.append(sm)
        if log:
            log(f'  pass {k+1}: members {sm:.1f} t')
    cs = an.cases(b, states); env = envelope3(b, cs)
    jt, per = an.joints(b, env)
    return dict(cases=cs, env=env, sizing=rep, mass_hist_t=hist, joints_t=jt/1e3, joints=per)
