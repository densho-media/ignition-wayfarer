"""Corrected mission path for the Vertex 2.6 impact model (research, not canon).

protect.mission() (work/vertex-2-6, left unchanged as history) places each braking burn one *accelerating*-burn length before its end
point. A constant-thrust braking burn covers more distance than an accelerating burn of the same duration (167.65 against 155.68 AU on
the Vertex path), so the home braking leg ran from 156.7 AU to -10.96 AU, through the Sun. Found by the dust-impacts thread
(claude/project-thread-6ryvmv a62118b, lab/studies/dust-impacts/model.py); this is the same correction: each braking burn ends where it
should, and the turn-around moves out to 1 + accelerate + brake distance. Importing this module replaces protect.mission for 2.7.
"""
import math
import protect as P


def mission(Tb_total, ve, dest_au=None, t_flip=300.0, n=240):
    tb = Tb_total/4; ratio = math.exp(P.DV/ve); prof = P.burn_profile(ratio, n)
    sa = sum(dt*f for dt, f in prof)*P.VC*tb
    sd = sum(dt*(1-f) for dt, f in prof)*P.VC*tb
    dmin = 1.0+(sa+sd)/P.AU
    D = max(dest_au or 0.0, dmin)
    segs = []

    def burn(phase, orient, r0, sign, decel):
        x = 0.0
        for dt, f in prof:
            v = P.VC*(1-f) if decel else P.VC*f
            ds = v*dt*tb
            segs.append(dict(phase=phase, orient=orient, r=r0+sign*(x+ds/2)/P.AU, v=max(v, 1.0), ds=ds, dt=dt*tb))
            x += ds

    def coast(phase, r0, r1, k=60):
        L = abs(r1-r0)*P.AU
        for i in range(k if L > 1 else 0):
            segs.append(dict(phase=phase, orient='BOW_FIRST', r=r0+(r1-r0)*(i+0.5)/k, v=P.VC, ds=L/k, dt=L/k/P.VC))

    def flip(phase, r):
        segs.append(dict(phase=phase, orient='BROADSIDE', r=r, v=P.VC, ds=P.VC*t_flip, dt=t_flip))

    burn('accelerate out', 'BOW_FIRST', 1.0, +1, False)
    coast('coast out', 1.0+sa/P.AU, D-sd/P.AU)
    flip('flip before braking (destination)', D-sd/P.AU)
    burn('brake at destination', 'ENGINE_FIRST', D-sd/P.AU, +1, True)
    burn('accelerate home', 'BOW_FIRST', D, -1, False)
    coast('coast home', D-sa/P.AU, 1.0+sd/P.AU)
    flip('flip before braking (home)', 1.0+sd/P.AU)
    burn('brake at home', 'ENGINE_FIRST', 1.0+sd/P.AU, -1, True)
    meta = dict(Tb_total_d=Tb_total/P.DAY, burn_d=tb/P.DAY, ve_c=ve/P.C, mass_ratio_per_burn=ratio, burn_AU=sa/P.AU, brake_AU=sd/P.AU,
                destination_AU=D, destination_min_AU=dmin, t_flip_s=t_flip, path_AU=sum(s['ds'] for s in segs)/P.AU,
                min_r_AU=min(s['r'] for s in segs))
    return segs, meta


ORIGINAL = P.mission
P.mission = mission
