"""PSA Phase II load cases, equilibrium checks, member sizing and global stability for one structural build.

Load philosophy (owner D01): thrust-bounded, configuration-specific, one factor applied once.
  limit     = the largest load expected in service for the configuration (steady thrust x dynamic load factor, engine-out, TVC/ACS,
              shutdown reversal), each over the propellant-depletion history
  ultimate  = 1.4 x limit (sizing, material design values, no further factor)
  yield     = 1.25 x limit (no permanent set)
  proof     = 1.10 x limit (verification test level for joints and modules; checked, not sized)
  accidental= damaged structure (member, joint or shared-node loss) at the thrust the procedure allows (factor 1.0, ultimate allowables)
  1.5 g     = a SEPARATE envelope (equipment qualification, light configurations, emergency): reported, not used to size the primary
              structure of a configuration whose thrust cannot produce it
All solves are free-free with inertia relief (the ship is never fixed); each reports its equilibrium residual.
"""
import math

import numpy as np
import scipy.linalg as sla
import scipy.sparse.linalg as spla

import fe
import model as mdl

LF_ULT, LF_YLD, LF_PROOF = 1.4, 1.25, 1.10
KD_COL, KD_SHELL = mdl.META['column_knockdown'], mdl.META['shell_knockdown']
RAMP_S = 30.0           # thrust ramp time at startup and shutdown (PROTOTYPE requirement on the drive: >= 3 x the first axial period;
                        # a 2 s ramp is run as a sensitivity, drive data OPEN)
TVC_FRAC = 0.02         # lateral thrust fraction from gimbal / plume misalignment (1.15 deg, PROTOTYPE)
DIFF_FRAC = 0.10        # nozzle-to-nozzle thrust mismatch (PROTOTYPE)
ACS_N = 2.0e5
LAM_REQ = 1.4/0.75      # global stability margin on the limit thrust (follower: rigidly mounted nozzles): ultimate factor over the global
                        # imperfection knockdown (one factor on load, the knockdown on the critical value; owner D01). Sized on the
                        # conservative (dead, fixed-direction) load: static global buckling, monotone in stiffness. The follower and
                        # partial-follower results are dynamic (flutter) and are reported, not sized: stiffness does not cure them.
STIFF_PASSES = 0        # stability-driven resizing is OFF: the reduced-basis indicators are not monotone in stiffness (see report E)
LONGITUDINAL = ('rail', 'trans', 'keel', 'spine', 'hub', 'collar', 'hubcone', 'cone')           # attitude-control pair force at the Brow (PROTOTYPE; Phase VI RCS order)


def dlf_ramp(f, tr):
    """Peak dynamic load factor of an undamped oscillator under a linear ramp to a constant load in tr seconds."""
    x = math.pi*f*tr
    return 1.0+abs(math.sin(x))/x if x > 1e-9 else 2.0


def forces(b, u):
    return b.m.element_forces(u)


def axial_modes(b, k=14):
    f, V, w2 = b.m.modes(k=k, sigma=-0.5)
    el = [(fi, i) for i, fi in enumerate(f) if fi > 0.02]
    # classify by participation: axial = dominant X translation
    out = []
    for fi, i in el:
        v = V[:, i]; ux = np.linalg.norm(v[0::6]); ut = np.linalg.norm(np.r_[v[1::6], v[2::6]]); rx = np.linalg.norm(v[3::6])
        out.append(dict(f=float(fi), kind='axial' if ux > ut else ('torsion' if rx*5 > ut else 'lateral')))
    return out


def solve(b, mode='steady', out=None, lateral=None, T=None, extra=None, cache=None):
    T = b.cfg['thrust'] if T is None else T
    b.apply_thrust(T, follower=True, out=out, lateral=lateral)
    if mode == 'diff':
        b.m.loads = {}; b.m.follow = {}
        for i, n in enumerate(b.noz):
            b.m.thrust(n, (T/4*(1+DIFF_FRAC*(1 if i == 0 else -1/3)), 0, 0))
    if mode == 'acs':
        b.m.loads = {}; b.m.follow = {}
        n0, n1 = b.brow_nodes[0], b.brow_nodes[1]
        b.m.load(n0, (0, 0, ACS_N)); b.m.load(n1, (0, 0, -ACS_N))
    if extra:
        for n, F in extra:
            b.m.load(n, F)
    if cache is not None and 'K' not in cache:
        cache['K'] = b.m.assemble('K'); cache['M'] = b.m.assemble('M')
    if cache is not None:
        r = b.m.solve_static(inertia_relief=True, K=cache['K'], M=cache['M'], cache=cache)
    else:
        r = b.m.solve_static(inertia_relief=True)
    return r, forces(b, r['u'])


def cases(b, states, ramp=None):
    """Limit load cases over the depletion states. Returns a list of (name, scale, forces) where member force = scale x forces."""
    out = []
    for st in states:
        b.attach(st['cfg']['parts'])
        T = st['cfg']['thrust']
        md = axial_modes(b); fax = next((m['f'] for m in md if m['kind'] == 'axial'), md[0]['f'])
        dlf = dlf_ramp(fax, RAMP_S if ramp is None else ramp)
        cc = {}
        r, f = solve(b, cache=cc); res = r['accel']['multiplier_residual']
        out.append(dict(name=f'steady x DLF {dlf:.2f} (left {st["left"]:.2f})', scale=dlf, f=f, res=res, left=st['left'], dlf=dlf, f_axial=fax, modes=md))
        out.append(dict(name=f'shutdown reversal (left {st["left"]:.2f})', scale=-(dlf-1.0), f=f, res=res, left=st['left']))
        r, f = solve(b, out=0, cache=cc); out.append(dict(name=f'engine-out, 3 of 4 (left {st["left"]:.2f})', scale=dlf, f=f, res=r['accel']['multiplier_residual'], left=st['left']))
        r, f = solve(b, mode='diff', cache=cc); out.append(dict(name=f'differential thrust 10 % (left {st["left"]:.2f})', scale=1.0, f=f, res=r['accel']['multiplier_residual'], left=st['left']))
        for ax, lat in (('y', (0, TVC_FRAC*T/4, 0)), ('z', (0, 0, TVC_FRAC*T/4))):
            r, f = solve(b, lateral=lat, cache=cc); out.append(dict(name=f'steady + TVC {ax} 2 % (left {st["left"]:.2f})', scale=dlf, f=f, res=r['accel']['multiplier_residual'], left=st['left']))
        r, f = solve(b, mode='acs', cache=cc); out.append(dict(name=f'attitude control pair (left {st["left"]:.2f})', scale=1.0, f=f, res=r['accel']['multiplier_residual'], left=st['left'], acs=True))
    return out


def envelope(b, cs, acs_with_steady=True):
    """Per-member limit envelope: max compression, max tension, max resultant moment, max torque over the cases. The ACS pair is
    added to the steady case of the same state (it fires during burns)."""
    n = len(b.m.el); Nc = np.zeros(n); Nt = np.zeros(n); Mm = np.zeros(n); Tq = np.zeros(n); gov = [''] * n
    by_state = {}
    for c in cs:
        by_state.setdefault(c['left'], []).append(c)
    for left, lst in by_state.items():
        acs = next((c for c in lst if c.get('acs')), None)
        for c in lst:
            if c.get('acs'):
                continue
            for i, f in enumerate(c['f']):
                if f is None:
                    continue
                s = c['scale']; N = s*f['N']; M = abs(s)*math.hypot(f['My'], f['Mz']); T = abs(s*f['T'])
                if acs is not None and acs_with_steady and s > 0:
                    fa = acs['f'][i]; N2 = [N+fa['N'], N-fa['N']]; M += math.hypot(fa['My'], fa['Mz']); T += abs(fa['T'])
                else:
                    N2 = [N]
                for v in N2:
                    if -v > Nc[i]:
                        Nc[i] = -v; gov[i] = c['name']
                    if v > Nt[i]:
                        Nt[i] = v
                Mm[i] = max(Mm[i], M); Tq[i] = max(Tq[i], T)
    return dict(Nc=Nc, Nt=Nt, M=Mm, T=Tq, gov=gov)


# ---------- sizing ------------------------------------------------------------------------------------------------------------
R_GRID = np.geomspace(0.03, 1.2, 56)
T_GRID = np.geomspace(0.0015, 0.08, 44)


def tube_props(r, t):
    ri = np.maximum(r-t, 0.0); A = np.pi*(r**2-ri**2); I = np.pi/4*(r**4-ri**4); return A, I, I/r


def check(mat, A, I, S, r, t, L, Nc, Nt, M):
    """Ultimate utilisation of a tube (arrays broadcast): strength, beam-column with Euler knockdown, local shell buckling."""
    E = mat['E']; Pcr = KD_COL*math.pi**2*E*I/np.maximum(L, 0.1)**2
    sc = LF_ULT*Nc/A; st = LF_ULT*Nt/A; sb = LF_ULT*M/S
    amp = 1.0/np.maximum(1.0-LF_ULT*Nc/Pcr, 1e-3)
    u_str = np.maximum((sc+sb)/mat['Fc'], (st+sb)/mat['Ft'])
    u_col = LF_ULT*Nc/Pcr + sb*amp/mat['Fc']
    s_shell = KD_SHELL*mdl.META['classic_shell_coeff']*E*t/r
    u_sh = (sc+sb)/s_shell
    return np.maximum.reduce([u_str, u_col, u_sh]), (u_str, u_col, u_sh)


def size(b, env, passes_only=True):
    """Lightest tube (r, t) per design group passing every member in the group at ultimate. Spine and hub keep their radius."""
    groups = {}
    for i, (e, md) in enumerate(zip(b.m.el, b.meta)):
        if e['kind'] == 'spring' or md['fam'] == 'iface':
            continue
        groups.setdefault(md['group'], []).append(i)
    rep = {}
    for g, idx in groups.items():
        s = b.sec[g]; mat = mdl.mat(s['mat'])
        L = np.array([b.m.frame(b.m.el[i])[0] for i in idx])
        Nc, Nt, M = env['Nc'][idx], env['Nt'][idx], env['M'][idx]
        if s['fam'] in ('spine', 'hub'):
            rr = np.array([mdl.R_SPINE])
        else:
            rr = R_GRID[R_GRID <= s['rmax']]
        R, Tt = np.meshgrid(rr, T_GRID, indexing='ij'); ok = (Tt >= mat['tmin']) & (Tt <= R/4)
        R, Tt = R[ok], Tt[ok]
        A, I, S = tube_props(R, Tt)
        u, _ = check(mat, A[:, None], I[:, None], S[:, None], R[:, None], Tt[:, None], L[None, :], Nc[None, :], Nt[None, :], M[None, :])
        umax = u.max(axis=1); mass = mat['rho']*A*L.sum()
        good = umax <= 1.0
        if good.any():
            k = np.argmin(np.where(good, mass, np.inf))
        else:
            k = np.argmin(umax)
        s['r'], s['t'] = float(R[k]), float(Tt[k])
        rep[g] = dict(r=s['r'], t=s['t'], mat=s['mat'], util=float(umax[k]), mass_t=float(mass[k]/1e3), n=len(idx), L_m=float(L.sum()),
                      Nc_MN=float(Nc.max()/1e6), Nt_MN=float(Nt.max()/1e6), M_MNm=float(M.max()/1e6), passes=bool(good.any()))
    b.update_sections()
    return rep


def joints(b, env):
    """Explicit node fittings: every node joining two or more members gets a Ti-6Al-4V fitting sized for the largest member force
    through it: load-transfer volume = sum over members of (1.4 F / Fty) x transfer length (2 x member radius + 0.1 m) x 1.6 (lugs,
    bolting, flanges); minimum 2 kg. Replaces the Phase I mass factor for joints (correction 3.7)."""
    ti = mdl.mat('TI64'); nodes = {}
    for i, (e, md) in enumerate(zip(b.m.el, b.meta)):
        if e['kind'] == 'spring' or md['fam'] == 'iface':
            continue
        F = max(env['Nc'][i], env['Nt'][i]) + env['M'][i]/max(b.sec[md['group']]['r'], 0.03)
        r = b.sec[md['group']]['r']
        for n in (e['a'], e['b']):
            nodes.setdefault(n, []).append((F, r))
    tot = 0.0; per = {}
    for n, lst in nodes.items():
        if len(lst) < 2:
            continue
        v = sum(LF_ULT*F/ti['Fy']*(2*r+0.1) for F, r in lst)*1.6
        m = max(2.0, ti['rho']*v); tot += m; per[n] = m
    return tot, per


def run(b, states, iters=4, log=None, ramp=None):
    """Load cases -> envelope -> size -> repeat (the stiffness redistribution converges in 3-4 passes)."""
    hist = []
    for k in range(iters):
        cs = cases(b, states, ramp); env = envelope(b, cs); rep = size(b, env)
        sm, by = b.structure_mass(); hist.append(sm/1e3)
        if log:
            log(f'  pass {k+1}: members {sm/1e3:.1f} t')
    # global stability sizing: the free-free ship under its own thrust must not diverge or flutter below LAM_REQ x thrust; the
    # longitudinal primary groups are thickened together (global EI is carried by the rails at r 5 m and the rotor-bay path)
    stiff = []
    strength_t = b.structure_mass()[0]/1e3
    for k in range(STIFF_PASSES):
        cs = cases(b, states[:1], ramp); st = next(c for c in cs if c['name'].startswith('steady x'))
        N = [f['N'] if f else 0.0 for f in st['f']]
        b.attach(states[0]['cfg']['parts']); solve(b)
        gs = global_stability(b, partial=0.0); lam = gs['lam'] or 12.0
        req = LAM_REQ*st['dlf']; stiff.append(dict(pass_=k, lam=lam, req=req, kind=gs['kind'], members_t=b.structure_mass()[0]/1e3, mode_groups=gs.get('mode_groups', {})))
        if log:
            log(f'  stability pass {k+1}: lambda {lam:.2f} (required {req:.2f}), members {stiff[-1]["members_t"]:.1f} t')
        if lam >= req:
            break
        f = min(3.0, (req/lam)*1.05)
        # stiffen the groups the critical mode lives in (a laced column buckles in shear when its lacing is light: Engesser);
        # groups carrying >= 5 % of the mode's geometric energy are thickened
        hit = {g for g, v in gs.get('mode_groups', {}).items() if v >= 0.05} or {g for g, s_ in b.sec.items() if s_['fam'] in LONGITUDINAL}
        for g, s in b.sec.items():
            if g in hit:
                s['t'] *= f
                if s['t'] > s['r']/4:
                    s['r'] = min(s['rmax'] if s['fam'] not in ('spine', 'hub') else s['r'], s['r']*math.sqrt(s['t']/(s['r']/4))); s['t'] = min(s['t'], s['r']/4)
                if g in rep:
                    rep[g]['r'], rep[g]['t'] = s['r'], s['t']
        b.update_sections()
    sm = b.structure_mass()[0]/1e3
    for g in rep:
        s = b.sec[g]; A, I, S = tube_props(np.array(s['r']), np.array(s['t']))
        rep[g]['mass_t'] = float(mdl.mat(s['mat'])['rho']*A*rep[g]['L_m']/1e3)
    cs = cases(b, states, ramp); env = envelope(b, cs)
    jt, per = joints(b, env)
    return dict(cases=cs, env=env, sizing=rep, mass_hist_t=hist, joints_t=jt/1e3, joints=per, stiffness=stiff,
                strength_members_t=strength_t, stiffness_increment_t=sm-strength_t)


# ---------- reduced-basis stability ----------------------------------------------------------------------------------------
def reduced_stability(b, N, lam_hi=40.0, nbasis=60, follower=True, partial=1.0, tvc_gain=0.0, zeta=0.005):
    """Nonconservative stability of the free-free ship under follower thrust in a modal basis (the lowest `nbasis` free-free modes,
    rigid modes removed). partial: fraction of the thrust that follows the nozzle rotation (0 = fixed direction, 1 = full follower).
    tvc_gain: closed-loop TVC that steers thrust against the measured attitude at the nozzle (rad/rad); it enters as an extra
    follower-like term proportional to the Brow rotation (PROTOTYPE control model). Returns the first load factor (x the case thrust)
    at flutter or divergence, or None to lam_hi."""
    K = b.m.assemble('K'); M = b.m.assemble('M'); G = b.m.assemble('G', N=N); Lf = b.m.follower_stiffness()
    free = b.m.free_mask(); Kf, Mf, Gf, Lff = (A[free][:, free].tocsc() for A in (K, M, G, Lf))
    w2, V = spla.eigsh(Kf, M=Mf, k=nbasis+6, sigma=-0.5, which='LM')
    o = np.argsort(w2); w2, V = w2[o], V[:, o]
    keep = w2 > 1e-4*w2.max()
    V = V[:, keep][:, :nbasis]
    k = V.T @ (Kf @ V); m = V.T @ (Mf @ V); g = V.T @ (Gf @ V); lf = V.T @ (Lff @ V)
    if tvc_gain:
        # thrust direction rotated by -gain x Brow rotation: lateral force at the nozzles proportional to the Brow's rotation dofs
        fidx = np.where(free)[0]; pos = {d: i for i, d in enumerate(fidx)}
        C = np.zeros((len(fidx), len(fidx))); T = sum(np.linalg.norm(v[0]) for v in b.m.follow.values())
        bn = b.brow_nodes[0]
        for n in b.noz:
            for (fd, rd) in ((1, 5), (2, 4)):
                if 6*n+fd in pos and 6*bn+rd in pos:
                    C[pos[6*n+fd], pos[6*bn+rd]] += (1 if fd == 1 else -1)*tvc_gain*T/4
        lf = lf + V.T @ C @ V
    # standard form through the Cholesky factor of the modal mass (m ~ I for M-orthonormal modes): the generalized QZ on a
    # badly scaled pair showed spurious complex pairs at zero load once very soft modes entered the basis (Phase III fix)
    Li = sla.inv(sla.cholesky(0.5*(m+m.T), lower=True))
    def std(A):
        return Li @ A @ Li.T
    def status(lam):
        # flutter only when a complex pair grows faster than structural damping removes energy: Im(sqrt mu) > zeta Re(sqrt mu).
        # A follower load splits every degenerate (axisymmetric) pair into a complex pair at once with a negligible growth rate
        # (Phase III: Im/Re ~ 1e-5 at lambda 0.02); without damping that read as flutter at lambda ~0.01
        e = sla.eigvals(std(k + lam*(g + partial*lf))); sq = np.sqrt(e.astype(complex))
        if np.any((np.abs(np.imag(sq)) > zeta*np.abs(np.real(sq))) & (np.real(e) > 0)):
            return 'flutter'
        if np.any(np.real(e) < 0):
            return 'divergence'
        return 'stable'
    grid = np.linspace(0.0, lam_hi, 81); prev = 0.0
    if status(0.0) != 'stable':
        return dict(lam=0.0, kind='unstable_at_zero')
    for gv in grid[1:]:
        s = status(gv)
        if s != 'stable':
            a, c = prev, gv
            for _ in range(30):
                mid = 0.5*(a+c)
                if status(mid) == 'stable':
                    a = mid
                else:
                    c = mid
            e, Q = sla.eig(std(k + c*1.02*(g + partial*lf))); Q = Li.T @ Q; j = int(np.argmin(np.real(e)) if status(c) == 'divergence' else np.argmax(np.abs(np.imag(e))))
            uf = np.zeros(b.m.ndof); uf[free] = np.real(V @ Q[:, j])
            return dict(lam=float(c), kind=status(c), f1=float(np.sqrt(w2[keep][0])/(2*math.pi)), mode=uf)
        prev = gv
    return dict(lam=None, kind=f'stable_to_{lam_hi:g}', f1=float(np.sqrt(w2[keep][0])/(2*math.pi)))

def global_stability(b, partial=1.0, nbasis=60, lam_hi=12.0, tvc_gain=0.0, zeta=0.005):
    """Global stability of the free-free ship: thrust T introduced at the 12 thrust-ring nodes (the drive yoke sets the thrust
    direction, so the follower rotation is the ring's), axial force field from inertia relief, then the reduced-basis eigen sweep.
    partial = 1 follower (rigidly mounted nozzles), 0 fixed inertial direction (TVC holding the line of thrust faster than the
    structure bends), between = partial follower."""
    T = b.cfg['thrust']; ring = list(b.station_nodes[b.xs[0]].values())
    b.m.loads = {}; b.m.follow = {}
    for n in ring:
        b.m.thrust(n, (T/len(ring), 0.0, 0.0), follower=True)
    r = b.m.solve_static(inertia_relief=True); fs = b.m.element_forces(r['u'])
    N = [f['N'] if f else 0.0 for f in fs]
    out = reduced_stability(b, N, lam_hi=lam_hi, nbasis=nbasis, partial=partial, tvc_gain=tvc_gain, zeta=zeta)
    if out.get('mode') is not None:
        # geometric-stiffness energy of the critical mode per design group: which groups the mode lives in
        u = out.pop('mode'); en = {}
        for j, (e, md) in enumerate(zip(b.m.el, b.meta)):
            if e['kind'] != 'beam' or not N[j]:
                continue
            L, R_, Tm = b.m.frame(e); ul = Tm @ u[b.m._dofs(e)]
            en[md['group']] = en.get(md['group'], 0.0) + abs(float(ul @ b.m.kg_local(L, N[j]) @ ul))
        tot = sum(en.values()) or 1.0
        out['mode_groups'] = {g: v/tot for g, v in sorted(en.items(), key=lambda kv: -kv[1])[:8]}
    b.apply_thrust(T)
    return out
