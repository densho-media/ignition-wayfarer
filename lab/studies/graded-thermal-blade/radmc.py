"""Band-spectral Monte Carlo radiation exchange for the Wayfarer radiator district (study code, lab/studies/graded-thermal-blade).

Surfaces are planar triangles; each side of a triangle belongs to a named group with a spectral emissivity per band and a
reflection kind (diffuse or specular). Rays are traced from receiver groups only; reciprocity
(A_i eps_ib G_ij,b = A_j eps_jb G_ji,b) turns the traced Gebhart factors into absorbed power from every hotter group, including
multiple diffuse and specular bounces. A group marked `reradiate` is adiabatic: it absorbs nothing and re-emits all it receives
diffusely (gray), the usual treatment of an MLI-wrapped or insulated body.
"""
import math
import numpy as np

SIGMA = 5.670374419e-8
C2 = 14387.77          # um K
EDGES = [0.0, 2.5, 4.5, 6.0, 8.0, 9.5, 12.0, 20.0, math.inf]   # band edges, micrometres
NB = len(EDGES)-1


def planck_fraction(lam_um, T):
    """Fraction of blackbody emission below lam at T (series of Chang & Rhee / Siegel-Howell)."""
    if lam_um <= 0:
        return 0.0
    if math.isinf(lam_um):
        return 1.0
    z = C2/(lam_um*T); s = 0.0
    for n in range(1, 60):
        s += math.exp(-n*z)/n*(z**3+3*z*z/n+6*z/n**2+6/n**3)
    return 15/math.pi**4*s


def band_fractions(T):
    f = [planck_fraction(EDGES[i+1], T)-planck_fraction(EDGES[i], T) for i in range(NB)]
    return np.array(f)


def effective(eps_bands, T):
    """Total hemispherical emissivity of a band coating at T (= its absorptance for blackbody radiation from a source at T)."""
    return float(np.dot(np.asarray(eps_bands), band_fractions(T)))


# ---------- coatings (per band, edges above) ----------
GRAY90 = dict(eps=[0.90]*NB, spec=False, note='gray 0.90 diffuse (current zone value)')
# Silvered fused-silica second-surface mirror (OSR): silver reflects through ~4 um, the glass is opaque and emissive beyond ~4.5-5 um,
# with the Si-O reststrahlen dip near 9 um. Band values rounded from the published OSR family (alpha_solar 0.05-0.08, eps_IR ~0.80).
OSR = dict(eps=[0.07, 0.15, 0.60, 0.85, 0.55, 0.85, 0.85, 0.85], spec=True, note='silvered fused-silica OSR (existing technology)')
# Degraded OSR (radiation darkening / contamination): +0.10 short-wave absorptance, -0.05 IR.
OSR_DEG = dict(eps=[0.17, 0.25, 0.60, 0.80, 0.52, 0.80, 0.80, 0.80], spec=True, note='OSR end of life (darkened)')
POLISHED = dict(eps=[0.06]*NB, spec=True, note='polished metal (Mo/Pt), 0.06')
POLISHED_BAFFLE = dict(eps=[0.08]*NB, spec=True, note='current baffle 0.08 polished')
# White ceramic radiator paint (ZnO / potassium silicate family, AZ-93 / Z-93 as flown on ISS radiators): alpha_solar ~0.15,
# eps_IR ~0.91; near-IR absorption rises beyond ~2.5 um. End of life: alpha_solar ~0.30 after UV/particle darkening, eps ~0.88.
WHITE = dict(eps=[0.15, 0.60, 0.90, 0.91, 0.91, 0.91, 0.91, 0.91], spec=False, note='white ceramic AZ-93 family (ISS radiators)')
WHITE_EOL = dict(eps=[0.30, 0.65, 0.88, 0.88, 0.88, 0.88, 0.88, 0.88], spec=False, note='white ceramic end of life')
REFRACTORY_HOTLAYER = dict(eps=[0.12]*NB, spec=True, note='polished Mo/Nb-alloy layer at ~1200 K, 0.12')
MID_LAYER = dict(eps=[0.08]*NB, spec=True, note='polished Ti/superalloy layer, 0.08')
GOLD_LAYER = dict(eps=[0.05]*NB, spec=True, note='gold or silver film on Ti, 0.05 (below 700 K)')
REFRACTORY_EOL = dict(eps=[0.18]*NB, spec=True, note='hot layer end of life 0.18')
MID_EOL = dict(eps=[0.12]*NB, spec=True, note='mid layer end of life 0.12')
GOLD_EOL = dict(eps=[0.08]*NB, spec=True, note='cold layer end of life 0.08')
BLACK = dict(eps=[1.0]*NB, spec=False, note='black receiver')
RERAD = dict(eps=[0.0]*NB, spec=False, rerad=True, note='adiabatic re-radiating surface')


class Scene:
    def __init__(self):
        self.tri = []        # (p0, p1, p2, front_group, back_group)
        self.groups = {}     # name -> dict(coat, T, area)

    def group(self, name, coat, T=None):
        if name not in self.groups:
            self.groups[name] = dict(coat=coat, T=T, area=0.0)
        return name

    def add_tri(self, p0, p1, p2, gf, gb):
        p0, p1, p2 = map(np.asarray, (p0, p1, p2))
        a = 0.5*np.linalg.norm(np.cross(p1-p0, p2-p0))
        if a < 1e-9:
            return
        for g in (gf, gb):
            if g is not None:
                self.groups[g]['area'] += a
        self.tri.append((p0, p1, p2, gf, gb))

    def add_quad(self, p0, p1, p2, p3, gf, gb):
        self.add_tri(p0, p1, p2, gf, gb); self.add_tri(p0, p2, p3, gf, gb)

    def compile(self):
        P = np.array([[t[0], t[1], t[2]] for t in self.tri])
        self.P0 = P[:, 0]; self.E1 = P[:, 1]-P[:, 0]; self.E2 = P[:, 2]-P[:, 0]
        n = np.cross(self.E1, self.E2); self.area = 0.5*np.linalg.norm(n, axis=1); self.N = n/np.linalg.norm(n, axis=1)[:, None]
        names = list(self.groups); self.names = names; idx = {k: i for i, k in enumerate(names)}
        self.gf = np.array([idx[t[3]] if t[3] is not None else -1 for t in self.tri])
        self.gb = np.array([idx[t[4]] if t[4] is not None else -1 for t in self.tri])
        G = len(names)
        self.eps = np.zeros((G+1, NB)); self.spec = np.zeros(G+1, bool); self.rerad = np.zeros(G+1, bool)
        for k, i in idx.items():
            c = self.groups[k]['coat']; self.eps[i] = c['eps']; self.spec[i] = c['spec']; self.rerad[i] = c.get('rerad', False)
        self.eps[G] = 1.0      # index -1 -> a side that absorbs everything (should not be hit)
        return self

    # ---------- ray tracing ----------
    def _hit(self, O, D):
        n = len(O); best = np.full(n, np.inf); bi = np.full(n, -1)
        for s in range(0, len(self.P0), 64):
            P0 = self.P0[s:s+64]; E1 = self.E1[s:s+64]; E2 = self.E2[s:s+64]
            h = np.cross(D[:, None, :], E2[None]); a = np.einsum('nmk,mk->nm', h, E1)
            ok = np.abs(a) > 1e-12; f = np.where(ok, 1/np.where(ok, a, 1), 0)
            S = O[:, None, :]-P0[None]; u = f*np.einsum('nmk,nmk->nm', S, h)
            q = np.cross(S, E1[None]); v = f*np.einsum('nk,nmk->nm', D, q); t = f*np.einsum('mk,nmk->nm', E2, q)
            m = ok & (u >= 0) & (v >= 0) & (u+v <= 1) & (t > 1e-6)
            t = np.where(m, t, np.inf); j = np.argmin(t, axis=1); tj = t[np.arange(n), j]
            better = tj < best; best[better] = tj[better]; bi[better] = j[better]+s
        return best, bi

    @staticmethod
    def _cosine(Nrm, rng):
        n = len(Nrm); u1 = rng.random(n); u2 = rng.random(n)
        st = np.sqrt(u1); ct = np.sqrt(1-u1); ph = 2*np.pi*u2
        a = np.where(np.abs(Nrm[:, 0:1]) < 0.9, np.array([[1.0, 0, 0]]), np.array([[0, 1.0, 0]]))
        t1 = np.cross(Nrm, a); t1 /= np.linalg.norm(t1, axis=1)[:, None]; t2 = np.cross(Nrm, t1)
        return st[:, None]*np.cos(ph)[:, None]*t1+st[:, None]*np.sin(ph)[:, None]*t2+ct[:, None]*Nrm

    def trace(self, src, n=100000, seed=1, max_bounce=40, chunk=20000, bands=None):
        """Gebhart factors from group `src` (both sides it owns): array [band, group+space] of absorbed fractions."""
        gi = self.names.index(src); rng = np.random.default_rng(seed)
        sides = [(k, +1) for k in np.where(self.gf == gi)[0]]+[(k, -1) for k in np.where(self.gb == gi)[0]]
        A = np.array([self.area[k] for k, _ in sides]); pr = A/A.sum()
        G = np.zeros((NB, len(self.names)+1))
        for b in (range(NB) if bands is None else bands):
            done = 0
            while done < n:
                m = min(chunk, n-done); done += m
                pick = rng.choice(len(sides), m, p=pr); k = np.array([sides[i][0] for i in pick]); sg = np.array([sides[i][1] for i in pick])
                r1 = rng.random(m); r2 = rng.random(m); sw = r1+r2 > 1; r1[sw] = 1-r1[sw]; r2[sw] = 1-r2[sw]
                O = self.P0[k]+r1[:, None]*self.E1[k]+r2[:, None]*self.E2[k]; Nn = self.N[k]*sg[:, None]
                D = self._cosine(Nn, rng); O = O+Nn*1e-4
                alive = np.ones(m, bool)
                for _ in range(max_bounce):
                    idx = np.where(alive)[0]
                    if len(idx) == 0:
                        break
                    t, j = self._hit(O[idx], D[idx])
                    miss = j < 0; G[b, -1] += miss.sum(); alive[idx[miss]] = False
                    idx = idx[~miss]; t = t[~miss]; j = j[~miss]
                    if len(idx) == 0:
                        break
                    d = D[idx]; nrm = self.N[j]; front = np.einsum('nk,nk->n', d, nrm) < 0
                    g = np.where(front, self.gf[j], self.gb[j]); gg = np.where(g < 0, len(self.names), g)
                    e = self.eps[gg, b]; absorb = (rng.random(len(idx)) < e) & ~self.rerad[gg]
                    np.add.at(G[b], np.where(gg == len(self.names), -1, gg)[absorb], 1)
                    alive[idx[absorb]] = False
                    keep = ~absorb; idx = idx[keep]; j = j[keep]; d = d[keep]; t = t[keep]; gg = gg[keep]
                    ns = np.where(front[keep][:, None], nrm[keep], -nrm[keep])        # normal on the hit side
                    P = O[idx]+t[:, None]*d
                    spec = self.spec[gg] & ~self.rerad[gg]
                    dn = d-2*np.einsum('nk,nk->n', d, ns)[:, None]*ns
                    dd = self._cosine(ns, rng)
                    D[idx] = np.where(spec[:, None], dn, dd); O[idx] = P+ns*1e-4
                G[b, -1] += alive.sum()   # rays still bouncing counted as lost to space (small)
            G[b] /= n
        return G

    def absorbed_from(self, rec, G):
        """Absorbed power at group rec from every group with a temperature, by reciprocity: A_rec * sum_b eps_rec,b G_rec->j,b E_b(T_j)."""
        g = self.groups[rec]; A = g['area']; e = np.asarray(g['coat']['eps']); out = {}
        for j, name in enumerate(self.names):
            T = self.groups[name]['T']
            if T is None:
                continue
            Eb = SIGMA*T**4*band_fractions(T)
            out[name] = float(A*np.sum(e*G[:, j]*Eb))
        return out

    def emitted(self, name):
        g = self.groups[name]; T = g['T']
        return g['area']*SIGMA*T**4*float(np.dot(g['coat']['eps'], band_fractions(T)))


# ---------- geometry helpers ----------
def radial(az, x, r):
    return (x, r*math.cos(az), r*math.sin(az))


def plate(sc, az, x0, x1, r0, r1, gplus, gminus, nx=1):
    """Radial plate in the half-plane at azimuth az; the +phi side is gplus."""
    for i in range(nx):
        a = x0+(x1-x0)*i/nx; b = x0+(x1-x0)*(i+1)/nx
        p = [radial(az, a, r0), radial(az, b, r0), radial(az, b, r1), radial(az, a, r1)]
        # normal of (p1-p0)x(p2-p0) = X x radial = +phi
        sc.add_quad(*p, gplus, gminus)


def cylinder(sc, r, x0, x1, gout, gin=None, n=24):
    for k in range(n):
        a = 2*math.pi*k/n; b = 2*math.pi*(k+1)/n
        p = [radial(a, x0, r), radial(b, x0, r), radial(b, x1, r), radial(a, x1, r)]
        sc.add_quad(p[0], p[3], p[2], p[1], gout, gin)   # outward normal on gout


def annulus(sc, x, r0, r1, gaft, gfwd, n=36, a0=0.0, a1=2*math.pi):
    for k in range(n):
        a = a0+(a1-a0)*k/n; b = a0+(a1-a0)*(k+1)/n
        p = [radial(a, x, r0), radial(a, x, r1), radial(b, x, r1), radial(b, x, r0)]
        sc.add_quad(*p, gfwd, gaft)      # (r-dir) x (phi-dir) = +X -> front side faces forward


def solve_adiabatic(sc, Gs, names, iters=60):
    """Temperatures of adiabatic sheets (T=None groups listed in `names`) from their traced Gebhart factors Gs[name]:
    emitted(T) = absorbed from all groups at their temperatures (self-exchange included)."""
    for nm in names:
        sc.groups[nm]['T'] = 300.0
    for _ in range(iters):
        for nm in names:
            g = sc.groups[nm]; q = sum(sc.absorbed_from(nm, Gs[nm]).values())
            lo, hi = 3.0, 3000.0
            for _ in range(50):
                mid = 0.5*(lo+hi); g['T'] = mid
                e = sc.emitted(nm)-sc.absorbed_from(nm, Gs[nm]).get(nm, 0.0)
                q = sum(v for k, v in sc.absorbed_from(nm, Gs[nm]).items() if k != nm)
                if e > q:
                    hi = mid
                else:
                    lo = mid
            g['T'] = 0.5*(lo+hi)
    return {nm: sc.groups[nm]['T'] for nm in names}
