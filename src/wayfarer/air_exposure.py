"""Crew exposure to a trace species along their actual places (SYS-002 v2). Standard library only.

A person's exposure is the time integral of the concentration where they are. `ring_air` carries, for every compartment, the exact integral
of its NH3 mole fraction (`exposure_ppm_s`), so a person who stays in compartment i from t1 to t2 receives exactly X_i(t2) - X_i(t1) ppm s.
A `Track` adds those pieces as the person moves (one compartment at a time; a transit is a sequence of short stays in the compartments
passed, never two places at once) and samples the running total E(t) at every step the caller takes.

Exposure-duration guidelines (NASA JSC 20584 Rev D) are compared with time-weighted means over their own durations, never with the
concentration at one instant:
    mean over [t - w, t] = (E(t) - E(t - w)) / w,    E = 0 before the event (the background is taken as 0, ring_air.TRACE)
evaluated at every sample (exact when the samples are a whole number of steps apart and w is a multiple of the step). The 1 h and 24 h
values are the largest such means over the run; a 24 h mean needs the run to cover at least 24 h after the event, and `assess` refuses to
call one complete otherwise. The long-term (7 d) value is reported only from a run that long. Nothing here judges health: an exceedance is
an exceedance of a reference value, to be evaluated (Rev D p. 7), not an injury.
"""


class Track:
    """One person's place over time and their exposure so far."""

    def __init__(self, name, node, t_s=0.0):
        self.name = name
        self.node = node            # compartment index (or None outside the model)
        self.t = [t_s]
        self.E = [0.0]              # running exposure, ppm s
        self.ppm = [0.0]            # the concentration where they are, at each sample
        self.places = [(t_s, node)]
        self._mark = None           # the compartment integral when they entered their place

    def begin(self, X, ppm_now):
        self._mark = X[self.node] if self.node is not None else 0.0
        self.ppm[-1] = ppm_now

    def sample(self, t_s, X, ppm_now):
        """After a step: X are the compartments' running integrals (ppm s), ppm_now the concentrations."""
        here = X[self.node] if self.node is not None else 0.0
        self.E.append(self.E[-1] + (here - self._mark))
        self._mark = here
        self.t.append(t_s)
        self.ppm.append(ppm_now[self.node] if self.node is not None else 0.0)

    def move(self, t_s, node, X, ppm_now):
        """Change place at a step boundary (the exposure up to now is already sampled)."""
        self.node = node
        self.places.append((t_s, node))
        self._mark = X[node] if node is not None else 0.0
        self.ppm[-1] = ppm_now[node] if node is not None else 0.0


def window_max(t, E, w, t_event=0.0):
    """The largest mean over any window of length w ending at a sample (E = 0 before the event). Returns (mean, end time)."""
    best = (0.0, t[0]); j = 0
    for k in range(len(t)):
        start = t[k] - w
        if start <= t_event:
            e0 = 0.0
        else:
            while t[j + 1] <= start + 1e-9:
                j += 1
            # E is exact at samples; between samples it is interpolated (exact when w is a multiple of the sample spacing)
            if abs(t[j] - start) < 1e-9:
                e0 = E[j]
            else:
                f = (start - t[j]) / (t[j + 1] - t[j]); e0 = E[j] + f * (E[j + 1] - E[j])
        m = (E[k] - e0) / w
        if m > best[0]:
            best = (m, t[k])
    return best


def assess(track, smac, t_event=0.0):
    """The person's exposure against each duration-specific reference the run is long enough to judge."""
    t, E = track.t, track.E
    span = t[-1] - t_event
    out = dict(name=track.name, peak_ppm=max(track.ppm), dose_ppm_h=E[-1] / 3600.0, span_h=span / 3600.0)
    m1, t1 = window_max(t, E, 3600.0, t_event)
    out['max_1h_ppm'] = m1; out['max_1h_end_h'] = t1 / 3600.0; out['ratio_1h'] = m1 / smac['1h']
    if span >= 24 * 3600.0 - 1e-6:
        m24, t24 = window_max(t, E, 24 * 3600.0, t_event)
        out['max_24h_ppm'] = m24; out['ratio_24h'] = m24 / smac['24h']; out['complete_24h'] = True
    else:
        out['max_24h_ppm'] = None; out['ratio_24h'] = None; out['complete_24h'] = False
    if span >= 7 * 24 * 3600.0 - 1e-6:
        m7, _ = window_max(t, E, 7 * 24 * 3600.0, t_event)
        out['max_7d_ppm'] = m7; out['ratio_7d'] = m7 / smac['7d']
    return out
