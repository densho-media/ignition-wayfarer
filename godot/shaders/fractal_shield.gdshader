// Fractal shielding, opaque ram materials (the Brow skin): see fractal_shield_surface.gdshaderinc.
shader_type spatial;
render_mode cull_disabled;           // the exported glTF materials are double-sided (Blender's default)

#include "res://shaders/fractal_shield_surface.gdshaderinc"
