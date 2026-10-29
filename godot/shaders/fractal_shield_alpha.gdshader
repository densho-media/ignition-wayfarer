// Fractal shielding, translucent ram materials (the disruptor layer display): see fractal_shield_surface.gdshaderinc.
shader_type spatial;
render_mode cull_disabled, depth_draw_opaque;

#define FS_ALPHA
#include "res://shaders/fractal_shield_surface.gdshaderinc"
