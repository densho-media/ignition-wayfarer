// The fractal shielding surface for scenes that keep the exported finishes (WfFractalShield.apply): the material's own colour, roughness,
// metallic and alpha, the pattern's value and its procedural normal on the forward-facing ram faces (world normal x > nx_min, x > x_min,
// Blender axes). fractal_shield.gdshader (opaque) and fractal_shield_alpha.gdshader (the translucent disruptor layer display) include it.

uniform vec4 albedo : source_color = vec4(0.7, 0.7, 0.7, 1.0);
uniform float rough = 0.5;
uniform float metal = 0.0;
uniform float x_min = 100.0;
uniform float nx_min = 0.5;

#include "res://shaders/fractal_shield.gdshaderinc"

varying vec3 wpos;
varying vec3 wnrm;

void vertex() {
	wpos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	wnrm = normalize((MODEL_MATRIX * vec4(NORMAL, 0.0)).xyz);
}

void fragment() {
	vec2 fp = vec2(-wpos.z, wpos.y);              // Blender (y, z) from runtime axes (x, z, -y)
	vec2 fwv = fwidth(fp);
	float fv;
	float fh;
	fs_pattern(fp, max(max(fwv.x, fwv.y), 1e-5), fv, fh);
	float on = (wnrm.x > nx_min && wpos.x > x_min) ? 1.0 : 0.0;
	ALBEDO = albedo.rgb * mix(1.0, fv, on);
	ROUGHNESS = rough;
	METALLIC = metal;
	NORMAL = fs_bump(dFdx(VERTEX), dFdy(VERTEX), NORMAL, dFdx(fh * on), dFdy(fh * on));
#ifdef FS_ALPHA
	ALPHA = albedo.a;
#endif
}
