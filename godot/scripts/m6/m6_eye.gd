class_name WfM6Eye
extends WfM6Sim
## M6 chapter: forward EYE, Dust Lance and shield. N steps through the exported forward-defence display poses (eyelids, a jammed
## facet, Crown prepared / engaged / degraded, shield damage cells), X runs an ILLUSTRATIVE dust stream (direction only: no flux, speed or
## impact energy) and V steps the ram-alignment error. The protected-shadow verdict is the built-model ray screen in the data (limit per
## azimuth, worst 2.22 deg, binding at radiator blade 1); the 0.2 deg 3-sigma figure is an L2 TARGET; field strength, impact and repair
## rates and the dust-speed limit are UNKNOWN.

const N_DUST := 260
const DUST_SPEED := 70.0            # display m/s (ILLUSTRATIVE)
const AZIMUTH_DEG := 30.0           # the worst shadow azimuth, where the error is applied
const UPSTREAM_M := 170.0
const DOWNSTREAM_M := -140.0

var pose := 0
var error_i := 0
var dust_on := false
var dust: Array = []                # [position, state] state 0 incoming, 1 outside the shield
var hits: Array = []                # [position, age]
var absorbed := 0
var passed_outside := 0
var rng := RandomNumberGenerator.new()

func _init(h: Node, block: Dictionary) -> void:
	super(h, block)
	rng.seed = 155

func state_name() -> String:
	return m.poses[pose].state

func set_active(on: bool) -> void:
	super(on)
	host.apply_display_state(state_name() if on else "COAST")

func frame_hint() -> Dictionary:
	return {"focus": Vector3(float(m.shield.face_x_m) - 70.0, 0.0, 0.0), "radius": 270.0, "yaw": 0.95, "pitch": 0.28}

func next_state() -> void:
	pose = (pose + 1) % m.poses.size()
	host.apply_display_state(state_name())
	note = "%s: %s" % [m.poses[pose].label, m.poses[pose].status]

func event() -> void:
	dust_on = not dust_on
	if dust_on:
		_seed_dust()
	note = "Dust stream %s (ILLUSTRATIVE)" % ("on" if dust_on else "off")

func response() -> void:
	error_i = (error_i + 1) % m.errors_deg.size()
	note = "Ram alignment error %.1f deg" % error_deg()

func error_deg() -> float:
	return float(m.errors_deg[error_i])

## Shadow limit at an azimuth (deg from +Y toward +Z, Blender frame), interpolated in the built-model table.
func limit_deg(az: float) -> float:
	var t: Array = m.shadow.per_azimuth
	var a := fposmod(az, 360.0)
	for i in t.size() - 1:
		if a >= t[i][0] and a <= t[i + 1][0]:
			return lerpf(t[i][1], t[i + 1][1], (a - t[i][0]) / maxf(1e-6, t[i + 1][0] - t[i][0]))
	return t[0][1]

func worst_limit() -> float:
	return m.shadow.per_azimuth.reduce(func(s, p): return minf(s, p[1]), 99.0)

func exposed() -> bool:
	return error_deg() > limit_deg(AZIMUTH_DEG)

## Dust velocity in the runtime frame: aft along -X, tilted by the alignment error toward the worst azimuth.
func flow_dir() -> Vector3:
	var az := deg_to_rad(AZIMUTH_DEG)
	var side := Vector3(0.0, sin(az), -cos(az))       # Blender (0, cos, sin) -> runtime (0, sin, -cos)
	var e := deg_to_rad(error_deg())
	return (Vector3(-cos(e), 0.0, 0.0) + side * sin(e)).normalized()

func _seed_dust() -> void:
	dust.clear()
	for i in N_DUST:
		dust.append([_spawn(rng.randf() * UPSTREAM_M), 0])        # all start upstream of the shield face

func _spawn(back: float) -> Vector3:
	var r := sqrt(rng.randf()) * float(m.shield.radius_m) * 1.6
	var a := rng.randf() * TAU
	return Vector3(float(m.lance.tip_x_m) + UPSTREAM_M, r * cos(a), r * sin(a)) + flow_dir() * back

func step(dt: float) -> void:
	for h in hits:
		h[1] += dt
	hits = hits.filter(func(h): return h[1] < 0.6)
	if not dust_on:
		return
	var face := float(m.shield.face_x_m)
	var radius := float(m.shield.radius_m)
	var v := flow_dir() * DUST_SPEED
	for d in dust:
		var p: Vector3 = d[0]
		var q: Vector3 = p + v * dt
		if d[1] == 0 and p.x >= face and q.x < face:
			var f := (p.x - face) / maxf(1e-6, p.x - q.x)
			var at: Vector3 = p.lerp(q, f)
			if Vector2(at.y, at.z).length() <= radius:
				hits.append([at, 0.0])
				absorbed += 1
				d[0] = _spawn(0.0)
				continue
			d[1] = 1
			passed_outside += 1
		d[0] = q
		if q.x < DOWNSTREAM_M:
			d[0] = _spawn(0.0)
			d[1] = 0

func redraw() -> void:
	mesh.clear_surfaces()
	mesh.surface_begin(Mesh.PRIMITIVE_LINES)
	var face := float(m.shield.face_x_m)
	var radius := float(m.shield.radius_m)
	var dir := flow_dir()
	var edge := Color(1.0, 0.3, 0.25, 0.85) if exposed() else Color(0.35, 0.95, 0.6, 0.55)
	# Protected-shadow boundary: lines from the shield rim along the dust direction.
	for i in 24:
		var a := TAU * i / 24.0
		var rim := Vector3(face, radius * cos(a), radius * sin(a))
		line(rim, rim + dir * 240.0, edge)
		var b := TAU * (i + 1) / 24.0
		line(rim, Vector3(face, radius * cos(b), radius * sin(b)), edge)
	# Ram direction (white) against the body axis.
	line(Vector3(float(m.lance.tip_x_m) + 60.0, 0, 0), Vector3(float(m.lance.tip_x_m) + 60.0, 0, 0) + dir * 60.0, Color(1, 1, 1, 0.9))
	if dust_on:
		var v := dir * DUST_SPEED * 0.12
		for d in dust:
			var c := Color(0.85, 0.88, 0.95, 0.7) if d[1] == 0 else Color(1.0, 0.7, 0.25, 0.9)
			line(d[0], d[0] - v, c)
	for h in hits:
		var s: float = 1.2 + 3.0 * h[1]
		var c := Color(1.0, 0.45, 0.3, 1.0 - float(h[1]) / 0.6)
		line(h[0] + Vector3(0, -s, 0), h[0] + Vector3(0, s, 0), c)
		line(h[0] + Vector3(0, 0, -s), h[0] + Vector3(0, 0, s), c)
	mesh.surface_end()

func panel_lines() -> Array[String]:
	var p: Dictionary = m.poses[pose]
	var out: Array[String] = []
	out.append("[b]FORWARD DEFENCE[/b]   %s   %s" % [p.label, host.badge_bb(p.status, "display pose (Blender drivers, baked)")])
	out.append("[color=#b4b2a9]%s[/color]" % p.text)
	var lim := limit_deg(AZIMUTH_DEG)
	var verdict := "[color=#e24b4a][b]EXPOSED[/b][/color] blade 1 leaves the shadow" if exposed() else "[color=#5dcaa5][b]PROTECTED[/b][/color] whole ship inside the shadow"
	out.append("Ram alignment error [b]%.1f deg[/b] at the worst azimuth: limit %.2f deg (built-model rays)  ·  %s" % [error_deg(), lim, verdict])
	out.append("  0.2 deg 3-sigma is the %s; the margin for dust spread, plasma and sensors is not shown." % m.shadow.target_status)
	if dust_on:
		out.append("Dust stream (ILLUSTRATIVE, direction only): %d stopped on the Brow · %d passed outside the rim" % [absorbed, passed_outside])
	else:
		out.append("Dust stream off.")
	out.append(unknown("field strength (OD-018), impact rating, repair rate (OD-019), dust-speed limit"))
	if note != "":
		out.append("[color=#888780]%s[/color]" % note)
	return out

func controls() -> Array:
	return [["holo.state", "next defence pose"], ["holo.event", "dust stream"], ["holo.response", "alignment error"]]
