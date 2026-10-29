// Fractal shielding: hexagonal facing plates with Sierpinski-subdivided triangles on the Brow's ram faces (the Brow skin and the disruptor
// layer). The reference is src/wayfarer/fractal_shield.py (`sample`); this follows it line for line. Uniform values come from the manifest
// (look.exterior.grammar.fractal_shield.uniforms) or the web viewer's build.json. Written in the subset Godot's shading language and GLSL ES
// 3.0 share, so the web viewer (three.js) injects this same file: no hints, no arrays, no Godot built-ins. Presentation only, no
// spacecraft fact: the height is a surface relief for procedural normals, never geometry or an opening.

uniform float fs_side;          // plate side (= circumradius), m
uniform float fs_gap;           // plate gap, m
uniform int fs_depth;           // Sierpinski levels
uniform float fs_density;       // chance a triangle subdivides further
uniform float fs_groove;        // level-0 groove width, m
uniform float fs_ratio;         // groove width ratio per level
uniform float fs_relief;        // groove depth, m
uniform float fs_inset;         // recess of the Sierpinski centre triangles, m
uniform float fs_fastener;      // tri-clamp radius, m
uniform float fs_lod_px;        // pixels a level's triangles span before it draws
uniform float fs_gap_value;
uniform float fs_groove_value;
uniform float fs_inset_value;
uniform float fs_jitter;
uniform float fs_repair_share;
uniform float fs_repair_value;
uniform float fs_well_q;        // EYE well keep-outs: centres at (+-q, +-q), radius (or, with fs_well_hex 1, the flat-top hexagon's apothem)
uniform float fs_well_r;
uniform float fs_well_hex;
uniform float fs_lance_r;       // Lance root keep-out radius
uniform float fs_crown_n;       // Crown bays: count, first azimuth, keep-out radial centre and half sizes
uniform float fs_crown_phase;
uniform float fs_crown_rm;
uniform float fs_crown_hr;
uniform float fs_crown_hw;
uniform float fs_rim_r;         // rim closeout radius

const float FS_SQRT3 = 1.7320508;
const float FS_PI = 3.14159265;

// Integer hash (lowbias32) of three whole numbers in [0, 1): exact on every GPU and in the Python reference.
uint fs_ihash(uint x) {
	x ^= x >> 16u;
	x *= 2146121005u;
	x ^= x >> 15u;
	x *= 2221713035u;
	x ^= x >> 16u;
	return x;
}

float fs_hash3(vec3 p) {
	uint h = fs_ihash(uint(int(p.x)) + fs_ihash(uint(int(p.y)) + fs_ihash(uint(int(p.z)))));
	return float(h >> 8u) / 16777216.0;
}

float fs_line(float d, float w, float fw) {
	float we = max(w, fw);
	return clamp(0.5 + (we * 0.5 - d) / fw, 0.0, 1.0) * (w / we);
}

// V-groove relief profile at distance d from a groove w wide, for the footprint fw: a groove under three pixels wide flattens out and
// widens to two pixels, so the procedural normal never breaks up into speckle at a distance.
float fs_vgroove(float d, float w, float fw) {
	return clamp(1.0 - 2.0 * d / max(w, 2.0 * fw), 0.0, 1.0) * smoothstep(fw, 3.0 * fw, w);
}

float fs_closeout(vec2 p) {
	float r = length(p);
	vec2 wv = abs(abs(p) - vec2(fs_well_q));
	float dw = fs_well_hex > 0.5 ? max(wv.y, wv.x * 0.8660254 + wv.y * 0.5) - fs_well_r : length(wv) - fs_well_r;
	float dl = r - fs_lance_r;
	float step_a = 2.0 * FS_PI / fs_crown_n;
	float th = atan(p.y, p.x) - fs_crown_phase;
	float dth = th - step_a * floor(th / step_a + 0.5);
	float dx = abs(r * sin(dth)) - fs_crown_hw;
	float dr = abs(r - fs_crown_rm) - fs_crown_hr;
	float dc = length(max(vec2(dx, dr), vec2(0.0))) + min(max(dx, dr), 0.0);
	return min(min(dw, dl), min(dc, fs_rim_r - r));
}

// p: the point in the plane across the ship axis (Blender Y, Z), m; fw: metres per pixel there. value multiplies the shell colour; height
// is the relief in metres (0 the plate face, negative into it).
void fs_pattern(vec2 p, float fw, out float value, out float height) {
	float e = fs_closeout(p);
	if (e < 0.0) {
		value = 1.0 + fs_line(-e, fs_gap, fw) * (fs_gap_value - 1.0);
		height = -2.0 * fs_relief * fs_vgroove(-e, fs_gap, fw);
		return;
	}
	float a = fs_side;
	float h0 = a * FS_SQRT3 * 0.5;
	// the flat-top hexagon holding p (axial coordinates, cube rounding)
	float fq = (2.0 / 3.0 * p.x) / a;
	float fr = (-p.x / 3.0 + FS_SQRT3 / 3.0 * p.y) / a;
	float fs = -fq - fr;
	float q = floor(fq + 0.5);
	float rr = floor(fr + 0.5);
	float t = floor(fs + 0.5);
	float dq = abs(q - fq);
	float dr = abs(rr - fr);
	float dt = abs(t - fs);
	if (dq > dr && dq > dt) {
		q = -rr - t;
	} else if (dr > dt) {
		rr = -q - t;
	}
	vec2 l = p - vec2(a * 1.5 * q, a * FS_SQRT3 * (rr + q * 0.5));
	float tone = 1.0 + (fs_hash3(vec3(q, rr, 7.0)) - 0.5) * 2.0 * fs_jitter
			+ (fs_hash3(vec3(q + 37.0, rr - 11.0, 3.0)) < fs_repair_share ? fs_repair_value - 1.0 : 0.0);
	// the plate's sector k and the barycentric coordinates of p in its triangle (centre, V_k, V_k+1), rotated into sector 0
	float k = mod(floor(atan(l.y, l.x) / (FS_PI / 3.0)), 6.0);
	float ang = -k * FS_PI / 3.0;
	vec2 pr = vec2(l.x * cos(ang) - l.y * sin(ang), l.x * sin(ang) + l.y * cos(ang));
	float b1 = 2.0 * pr.y / (a * FS_SQRT3);
	float b0 = pr.x / a - b1 * 0.5;
	vec3 b = vec3(1.0 - b0 - b1, b0, b1);
	float bc = b.x;
	vec2 va = mod(k, 2.0) < 0.5 ? vec2(a, 0.0) : vec2(a * 0.5, h0);     // the A corner of this sector: the tri-clamp
	float df = length(pr - va);
	float f0 = smoothstep(fs_lod_px * fw, 2.0 * fs_lod_px * fw, a);
	float sd = min(b0, b1) * h0;
	float groove = fs_line(sd, fs_groove, fw) * f0;
	float h = -fs_relief * f0 * fs_vgroove(sd, fs_groove, fw);
	float v = tone;
	float path = 1.0;
	float side = a;
	float w = fs_groove;
	for (int lv = 1; lv <= 6; lv++) {
		if (lv > fs_depth || fs_hash3(vec3(q * 7.0 + k, rr * 7.0 + float(lv), path)) >= fs_density) {
			break;
		}
		float hk = side * FS_SQRT3 * 0.5;
		w *= fs_ratio;
		float fk = smoothstep(fs_lod_px * fw, 2.0 * fs_lod_px * fw, side * 0.5);
		vec3 m = abs(b - vec3(0.5));
		float d = min(m.x, min(m.y, m.z)) * hk;
		groove = max(groove, fs_line(d, w, fw) * fk);
		h = min(h, -fs_relief * fk * fs_vgroove(d, w, fw));
		float bm = max(b.x, max(b.y, b.z));
		if (bm < 0.5) {
			v *= 1.0 + fk * (fs_inset_value - 1.0);
			h = min(h, -fs_inset * fk);
			break;
		}
		float j = b.x >= bm ? 0.0 : (b.y >= bm ? 1.0 : 2.0);
		b = 2.0 * b - vec3(j < 0.5 ? 1.0 : 0.0, abs(j - 1.0) < 0.5 ? 1.0 : 0.0, j > 1.5 ? 1.0 : 0.0);
		path = path * 4.0 + j + 1.0;
		side *= 0.5;
	}
	v *= 1.0 + groove * (fs_groove_value - 1.0);
	if (df < fs_fastener) {
		float ring = fs_line(fs_fastener - df, fs_groove, fw);
		value = tone * (1.0 + ring * (fs_groove_value - 1.0));
		height = -fs_relief * fs_vgroove(fs_fastener - df, fs_groove, fw);
		return;
	}
	float cg = fs_line(bc * h0, fs_gap, fw);
	value = v + cg * (fs_gap_value - v);
	height = min(h, -2.0 * fs_relief * fs_vgroove(bc * h0, fs_gap, fw));
}

// Surface-gradient bump (Mikkelsen 2010): the normal of a surface at pos with normal n displaced by a height whose screen derivatives are
// dhx, dhy; pos, n and the result share one space (view space in both runtimes). dpx, dpy are the screen derivatives of pos.
vec3 fs_bump(vec3 dpx, vec3 dpy, vec3 n, float dhx, float dhy) {
	vec3 r1 = cross(dpy, n);
	vec3 r2 = cross(n, dpx);
	float det = dot(dpx, r1);
	vec3 grad = sign(det) * (dhx * r1 + dhy * r2);
	return normalize(abs(det) * n - grad);
}
