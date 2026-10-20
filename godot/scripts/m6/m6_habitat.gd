class_name WfM6Habitat
extends WfM6Sim
## M6 chapter: the counter-rotating habitat rings, the stationary spine and a crew member's route. The rings turn on the exported rotor
## bindings (pivot, axis and sign of WF.ROTOR.1 / WF.ROTOR.2) at the sourced 4 rpm in real time; N stops them and locks them at an index
## angle (08!A47, MEC-011) or spins them up again; the ramp time is PRESENTATION (spin-down and release durations OPEN, MEC-010). X walks a
## crew marker along the induction route rail (stationary entry and trunk, despun drum, then the ring's tube, landing and aisle) at the
## rig's review pace times the display factor. Local spin gravity w^2 r / g0 and the Coriolis push on the tube ladder are DERIVED from the
## sourced rpm, the rail radius and the rig's ladder figures; nothing is simulated beyond that.

const RAMP_S := 12.0                # PRESENTATION spin-up / spin-down ramp (owner duration OPEN)

var pivots: Array = []              # [{node, origin, axis, sign, key}]
var angle := 0.0                    # ring 1 turn from the index pose, rad (ring 2 turns by -angle)
var f := 1.0                        # spin fraction 0..1
var target := 1.0
var stop_t := -1.0                  # time into a spin-down that lands on a lock, or -1
var stop_T := 0.0
var stop_a0 := 0.0
var stop_f0 := 1.0
var locked := false
var walking := false
var walk_m := 0.0
var rail_len := 0.0
var marker := MeshInstance3D.new()
var path_ring: Array = []           # rail points in the ring frame
var omega := 0.0

func _init(h: Node, block: Dictionary) -> void:
	super(h, block)
	omega = float(m.rotors[0].omega)
	rail_len = float(m.rail[-1].m)
	var sphere := SphereMesh.new()
	sphere.radius = 1.1
	sphere.height = 2.2
	var mat := StandardMaterial3D.new()
	mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	mat.albedo_color = Color(1.0, 0.95, 0.55)
	mat.no_depth_test = true
	sphere.material = mat
	marker.mesh = sphere
	marker.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF

## The host builds the pivots under the ship and reparents each rotor's meshes onto them (kept in place).
func attach(ship: Node3D, by_id: Dictionary) -> int:
	var moved := 0
	for r in m.rotors:
		var pivot := Node3D.new()
		pivot.name = "M6_" + str(r.key)
		var p: Array = r.pivot
		pivot.position = Vector3(p[0], p[1], p[2])
		ship.add_child(pivot)
		for id in r.nodes:
			if by_id.has(id):
				by_id[id].reparent(pivot, true)
				moved += 1
		pivots.append({"node": pivot, "origin": pivot.position, "axis": Vector3(r.axis[0], r.axis[1], r.axis[2]).normalized(), "sign": float(r.sign), "key": r.key})
	ship.add_child(marker)
	marker.visible = false
	return moved

func set_active(on: bool) -> void:
	super(on)
	marker.visible = on

func frame_hint() -> Dictionary:
	var c := Vector3.ZERO
	for p in pivots:
		c += p.origin / pivots.size()
	return {"focus": c, "radius": 125.0, "yaw": 0.7, "pitch": 0.42}

## The rings stack hundreds of fitted parts: a softer overlay keeps the legend colours readable instead of saturating to white.
func tints() -> Dictionary:
	var out := {}
	var ch: Dictionary = host.data.chapters[host.chapter]
	for id in ch.nodes:
		var t: Array = ch.tint.get(id, [])
		out[id] = [Color(t[0], t[1], t[2]) if t.size() == 3 else host.info[id].color, "soft"]
	return out

func ring_angle(i: int) -> float:
	return angle * float(pivots[i].sign)

func lock_step() -> float:
	return TAU / float(m.lock_angles_deg.size())

func next_state() -> void:
	if target > 0.0:
		target = 0.0
		# Choose the first index angle ahead that a linear ramp of at least RAMP_S can reach, and time the ramp to land on it.
		var reach := angle + omega * f * RAMP_S * 0.5
		var lock_a := ceilf(reach / lock_step() - 1e-6) * lock_step()
		stop_a0 = angle
		stop_f0 = f
		stop_T = 2.0 * (lock_a - angle) / maxf(1e-6, omega * f)
		stop_t = 0.0
		note = "Spin-down to the index angle and lock (before high thrust, 08!A47); ramp PRESENTATION %.0f s, real duration OPEN" % stop_T
	else:
		target = 1.0
		locked = false
		stop_t = -1.0
		note = "Locks released; paired spin-up (Q53: may start once isolation is verified)"

func event() -> void:
	walking = not walking
	if walking and walk_m >= rail_len:
		walk_m = 0.0
	note = "Crew walk %s (review pace x%.0f display)" % ["on" if walking else "paused", float(m.walk_display_x)]

func step(dt: float) -> void:
	var f0 := f
	if stop_t >= 0.0:
		stop_t = minf(stop_t + dt, stop_T)
		f = stop_f0 * (1.0 - stop_t / maxf(1e-6, stop_T))
		angle = stop_a0 + omega * stop_f0 * (stop_t - stop_t * stop_t / (2.0 * stop_T))
		if stop_t >= stop_T:
			f = 0.0
			locked = true
			stop_t = -1.0
			angle = roundf(angle / lock_step()) * lock_step()
	else:
		if target > f:
			f = minf(target, f + dt / RAMP_S)
		angle += omega * 0.5 * (f0 + f) * dt
	if stop_t < 0.0:
		angle = fposmod(angle, TAU)
	for i in pivots.size():
		var p: Dictionary = pivots[i]
		p.node.transform = Transform3D(Basis(p.axis, ring_angle(i)), p.origin)
	if walking:
		walk_m = minf(rail_len, walk_m + float(m.walk_speed_m_s) * float(m.walk_display_x) * dt)
		if walk_m >= rail_len:
			walking = false
	var at := walker()
	marker.position = at.p

## Rail point -> ship frame now: ring-frame points turn with ring 1; the drum is despun at the index (Q46); entry and trunk are fixed.
func placed(q: Dictionary) -> Vector3:
	var p := Vector3(q.p[0], q.p[1], q.p[2])
	if q.frame == "RING" and not pivots.is_empty():
		var o: Vector3 = pivots[0].origin
		return o + Basis(pivots[0].axis, ring_angle(0)) * (p - o)
	return p

func walker() -> Dictionary:
	var rail: Array = m.rail
	for i in rail.size() - 1:
		if walk_m <= rail[i + 1].m:
			var t := (walk_m - float(rail[i].m)) / maxf(1e-6, float(rail[i + 1].m) - float(rail[i].m))
			var a := placed(rail[i])
			var b := placed(rail[i + 1])
			return {"p": a.lerp(b, t), "zone": rail[i + 1].zone, "frame": rail[i + 1].frame, "radial": Vector2(b.y - a.y, b.z - a.z).length() > 0.5 * a.distance_to(b)}
	return {"p": placed(rail[-1]), "zone": rail[-1].zone, "frame": rail[-1].frame, "radial": false}

func radius_of(p: Vector3) -> float:
	var o: Vector3 = pivots[0].origin if not pivots.is_empty() else Vector3.ZERO
	return Vector2(p.y - o.y, p.z - o.z).length()

func local_g(at: Dictionary) -> float:
	if at.frame != "RING":
		return 0.0
	var w := omega * f
	return w * w * radius_of(at.p) / float(m.g0)

func stop_title() -> String:
	var title := ""
	for s in m.stops:
		if walk_m + 0.5 >= float(s.m):
			title = s.title
	return title

func redraw() -> void:
	mesh.clear_surfaces()
	mesh.surface_begin(Mesh.PRIMITIVE_LINES)
	var rail: Array = m.rail
	for i in rail.size() - 1:
		var done := float(rail[i + 1].m) <= walk_m
		var c := Color(1.0, 0.95, 0.55, 0.95) if done else Color(0.6, 0.9, 1.0, 0.45)
		line(placed(rail[i]), placed(rail[i + 1]), c)
	# Spin axis and the two senses of rotation (ring 1 / ring 2), short arcs at the CoM radius.
	for i in pivots.size():
		var p: Dictionary = pivots[i]
		var r := float(m.com_radius_m)
		var col := Color(0.45, 0.75, 1.0, 0.9) if i == 0 else Color(1.0, 0.6, 0.35, 0.9)
		var span := 0.9 * f + 0.05
		for k in 12:
			var a0: float = ring_angle(i) + p.sign * span * k / 12.0
			var a1: float = ring_angle(i) + p.sign * span * (k + 1) / 12.0
			line(p.origin + Basis(p.axis, a0) * Vector3(0, r, 0), p.origin + Basis(p.axis, a1) * Vector3(0, r, 0), col)
	mesh.surface_end()

func panel_lines() -> Array[String]:
	var r0: Dictionary = m.rotors[0]
	var out: Array[String] = []
	var state := "LOCKED at the index angle (rings stopped)" if locked else ("SPINNING %.2f of %s rpm" % [f, r0.rpm] if stop_t < 0.0 else "SPIN-DOWN to lock, %.2f" % f)
	out.append("[b]HABITAT RINGS[/b]   %s   %s" % [state, host.badge_bb("BASELINE", "two rings, counter-rotating, 4 rpm (08)")])
	var L := float(r0.momentum)
	out.append("Ring 1 %+.1f MN m s · ring 2 %+.1f MN m s · net %.1f (DERIVED, %s per ring at r %.0f m)" % [L * f / 1e6, -L * f / 1e6, 0.0, "%.0f t" % (float(r0.mass_kg) / 1000.0), float(m.com_radius_m)])
	var at := walker()
	var g := local_g(at)
	out.append("Crew marker: [b]%s[/b] (%s frame) · r %.1f m · spin gravity [b]%.2f g[/b] (DERIVED w^2 r)%s" % [at.zone, at.frame.to_lower(), radius_of(at.p), g,
		"  ·  Coriolis on the ladder %.3f g at %.1f m/s" % [float(m.coriolis_g_per_m_s) * float(m.walk_speed_m_s) * f, float(m.walk_speed_m_s)] if at.zone == "tube" and f > 0.0 else ""])
	out.append("  %s" % stop_title())
	if locked:
		out.append("Locked: no spin gravity. In the burn the load is axial toward aft; above the %.1f g LOW_THRUST limit (%s) crew ride couches." % [float(m.low_thrust.limit_g), m.low_thrust.status])
	out.append(host.badge_bb("HOLD", "Ring A casualty transfer unqualified: unsuited -0.013 m, suited ~-0.17 m at the spin port (15!A221)"))
	out.append(unknown("spin-down and lock durations (MEC-010), ring section and lock loads; ramp shown is PRESENTATION"))
	if note != "":
		out.append("[color=#888780]%s[/color]" % note)
	return out

func controls() -> Array:
	return [["holo.state", "stop and lock / spin up"], ["holo.event", "crew walk"]]
