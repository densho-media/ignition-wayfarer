// Phase 4 S9: the selected exterior grammar's family finish with the ILLUSTRATIVE ram-face tile-and-repair shading and the switchable
// post-voyage wear layer (manifest look.exterior.grammar; the Blender grammar look hero_preview.surface runs the same formulas with
// Blender's noise and hash). Uniforms come from the manifest; colours are linear. Presentation only, no spacecraft fact.
// With fractal_on the ram face takes the fractal shielding pattern (fractal_shield.gdshaderinc, manifest look.exterior.grammar.fractal_shield)
// instead of the running-bond tiles: its value pattern and a procedural normal from the relief, faded per level by the pixel footprint.
shader_type spatial;
render_mode cull_disabled;           // the exported glTF materials are double-sided (Blender's default); some generated faces wind inward

uniform vec3 base = vec3(0.7);
uniform float rough = 0.5;
uniform float metal = 0.0;
uniform bool wear_on = false;
uniform float grime = 0.0;
uniform float wear_scale = 1.0;
uniform float coverage = 0.5;
uniform float wear_rough = 0.0;
uniform vec3 tint = vec3(1.0);
uniform bool ram_on = false;
uniform float tile = 1.6;
uniform float seam = 0.03;
uniform float seam_value = 0.55;
uniform float jitter = 0.045;
uniform float repair_share = 0.03;
uniform float repair_value = 1.1;
uniform float pitting = 0.0;
uniform float x_min = 100.0;
uniform float nx_min = 0.5;
uniform bool fractal_on = false;

#include "res://shaders/fractal_shield.gdshaderinc"

varying vec3 wpos;
varying vec3 wnrm;

void vertex() {
	wpos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	wnrm = normalize((MODEL_MATRIX * vec4(NORMAL, 0.0)).xyz);
}

float hash3(vec3 p) {
	p = fract(p * 0.3183099 + 0.1) * 17.0;
	return fract(p.x * p.y * p.z * (p.x + p.y + p.z));
}

float vnoise(vec3 x) {
	vec3 i = floor(x);
	vec3 f = fract(x);
	f = f * f * (3.0 - 2.0 * f);
	return mix(mix(mix(hash3(i), hash3(i + vec3(1, 0, 0)), f.x), mix(hash3(i + vec3(0, 1, 0)), hash3(i + vec3(1, 1, 0)), f.x), f.y),
			mix(mix(hash3(i + vec3(0, 0, 1)), hash3(i + vec3(1, 0, 1)), f.x), mix(hash3(i + vec3(0, 1, 1)), hash3(i + vec3(1, 1, 1)), f.x), f.y), f.z);
}

float fbm(vec3 p) {
	float a = 0.5;
	float sum = 0.0;
	float norm = 0.0;
	for (int k = 0; k < 3; k++) {
		sum += a * vnoise(p);
		norm += a;
		p *= 2.0;
		a *= 0.5;
	}
	return sum / norm;
}

float hash2(vec2 p) {
	return fract(sin(dot(p, vec2(12.9898, 78.233))) * 43758.5453);
}

void fragment() {
	vec3 bp = vec3(wpos.x, -wpos.z, wpos.y);          // Blender axes: runtime (x, z, -y) back to (x, y, z)
	vec3 b = base;
	float r = rough;
	float value = 1.0;
	if (wear_on) {
		float m = clamp((fbm(bp / wear_scale) - (0.55 - 0.3 * coverage)) / 0.3, 0.0, 1.0);
		value *= 1.0 - m * grime;
		r += m * wear_rough;
		b *= mix(vec3(1.0), tint, m);
	}
	if (ram_on && fractal_on) {
		// Derivatives stay outside the per-pixel face test: the pattern runs on every ram-material pixel, the face mask picks the result.
		vec2 fp = bp.yz;
		vec2 fwv = fwidth(fp);
		float fv;
		float fh;
		fs_pattern(fp, max(max(fwv.x, fwv.y), 1e-5), fv, fh);
		float on = (wnrm.x > nx_min && wpos.x > x_min) ? 1.0 : 0.0;
		if (pitting > 0.0) {
			fv *= 1.0 - 0.45 * step(hash3(floor(bp * 25.0)), pitting);
		}
		value *= mix(1.0, fv, on);
		NORMAL = fs_bump(dFdx(VERTEX), dFdy(VERTEX), NORMAL, dFdx(fh * on), dFdy(fh * on));
	} else if (ram_on && wnrm.x > nx_min && wpos.x > x_min) {
		float th = tile * 0.5;
		float u = bp.y / tile;
		float v = bp.z / th;
		float row = floor(v);
		float uu = u + mod(row, 2.0) * 0.5;
		float col = floor(uu);
		float fu = uu - col;
		float fv = v - row;
		float d = min(min(fu, 1.0 - fu) * tile, min(fv, 1.0 - fv) * th);
		float t = 1.0 + (hash2(vec2(col, row)) - 0.5) * 2.0 * jitter + (hash2(vec2(col + 37.0, row - 11.0)) < repair_share ? repair_value - 1.0 : 0.0);
		if (pitting > 0.0) {
			t *= 1.0 - 0.45 * step(hash3(floor(bp * 25.0)), pitting);
		}
		value *= d < seam * 0.5 ? seam_value : t;
	}
	ALBEDO = b * value;
	ROUGHNESS = clamp(r, 0.0, 1.0);
	METALLIC = metal;
}
