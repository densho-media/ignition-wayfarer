"""FDP-1 engineering package (lab/variants/fdp1). Pure standard library: runs under system python3 and Blender's bundled Python.

config      load fdp1.toml (+ a variant), build the four-burn scenario it overrides
propulsion  the four-burn closure (authoritative) and the per-pulse fusion record
shielding   layered shadow shield, protected envelopes, dose, streaming paths
structure   thrust path, nozzle struts, frames, wing spars
thermal     heat by loop, radiator areas and masses, packaging layouts
tanks       current versus required capacity, proposed layouts T-A/T-B/T-C, centre of mass
mission     four-burn timeline, distances, round-trip durations
model       the integrated solve (geometry <-> closure feedback) and checks
geometry    the procedural part list Blender draws (pure dicts)
"""
