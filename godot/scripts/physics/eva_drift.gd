class_name WfEvaDrift
extends Node3D
## EVA 3-D tethered drift (PHYS-001 phase 5, SIMULATION_ONLY; FLIGHT_EVA stays HOLD, DYN-013). A suited body (profile human_suited) in the
## non-rotating SHIP frame under mode EVA (drive off, field zero). Egress only from the airlock phase EXTERIOR, at rest relative to the
## ship (co-motion); the body grips the hatch anchor, pushes off at most mass * test_push_dv (DYN-010) and then drifts. It is never
## accelerated by keys and never braked (DYN-016, GEN-005); only the tether limit (WfTether) removes outward speed. The thruster is an
## experimental flag, OFF by default, with no binding when off.
## J01: two tethers A and B under the rail protocol (EVA-014, mirror of eva_suit.Tethers): clip a free tether to an anchor within hand reach,
## tug-test it, release the other only while this one is clipped to a different anchor and tested, so live tethers never drop to zero. The
## rail runs are graspable rods (the hand closes on the nearest point, as on the trunk rails) with a thin collider the body can touch.

var dyn: Dictionary
var field: WfFrameField
var body: WfTetheredBody
var tethers := {"A": null, "B": null}      # WfTether or null
var tested := {"A": false, "B": false}
var tether: WfTether:                        # the first live tether (checks and the HUD); null when none
	get:
		return tethers.A if tethers.A != null else tethers.B
var hold: WfHandhold
var line: MeshInstance3D
var experimental_thruster := false     # not canon: no owner thruster or SAFER data exists
var active := false
## The EVA package (generated/wf_eva.json, Godot axes). When set, egress builds the exterior around the drift: a PROTOTYPE collision proxy of the
## stationary body from `collider` (hull radius samples of the shared formulas and the Airlock_EVA fitting cylinder, never the visual mesh) and the
## real rail anchors as handholds. Empty: the bare staged drift of phase 5 (no colliders).
var eva: Dictionary = {}
var holds: Array = []                  # every WfHandhold: the hatch anchor first, then the rail anchors, then the rail rods
var anchor_holds: Array = []           # the tether anchor points: the hatch anchor and the rail anchors (not the rods)
var rail_radius := 0.0                 # the rods' radius (m)
var world: StaticBody3D
var out_dir := Vector3.UP              # outward collar normal at the hatch
var samples: Array = []                # [[x, r]] hull radius samples

const START_OFFSET_M := 0.45           # PROTOTYPE start: body centre this far out of the hatch face along the normal (capsule radius 0.4 clears the face, reach 0.6 holds the anchor)
const ARC_SEGMENTS := 48

func _init(d: Dictionary) -> void:
	dyn = d
	field = WfFrameField.new(d, "SHIP", "EVA")

## Egress: refused unless the airlock phase is EXTERIOR and a tether is live. Returns {ok, reason}.
func egress(phase: String, anchor: Vector3, outward: Vector3, reach_m: float, live_tethers: int) -> Dictionary:
	if active:
		return {"ok": false, "reason": "already outside"}
	if phase != "EXTERIOR":
		return {"ok": false, "reason": "egress only from the airlock phase EXTERIOR (now %s)" % phase}
	if live_tethers < 1:
		return {"ok": false, "reason": "no live tether"}
	out_dir = outward.normalized()
	hold = WfHandhold.new()
	hold.anchor_id = "EVA_HATCH_ANCHOR"
	hold.position = anchor
	add_child(hold)
	holds = [hold]
	anchor_holds = [hold]
	if not eva.is_empty():
		build_world()
	body = WfTetheredBody.new()
	body.configure(dyn, "human_suited", field)
	if eva.is_empty():
		body.position = anchor + out_dir * 0.3                  # staged start: inside hand reach of the anchor
	else:
		body.position = anchor + out_dir * START_OFFSET_M
		body.rotation = Vector3(0.0, 0.0, PI / 2.0)             # lying along the collar (axis X): a head-out posture would put the centre beyond reach
	add_child(body)
	body.linear_velocity = Vector3.ZERO                      # co-motion: the ship frame is the ship's own, v_rel = 0
	tethers = {"A": WfTether.new(anchor, reach_m, true, "EVA_HATCH_ANCHOR"), "B": null}
	tested = {"A": true, "B": false}                         # A is clipped to the hatch anchor ring and tested inside the airlock (rail mode)
	_bind()
	body.grab(hold)
	line = MeshInstance3D.new()
	line.mesh = ImmediateMesh.new()
	line.material_override = StandardMaterial3D.new()
	line.material_override.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	line.material_override.albedo_color = Color(1.0, 0.8, 0.2)
	add_child(line)
	active = true
	return {"ok": true, "reason": ""}

func end() -> void:
	for n in [body, line, world] + holds:
		if n:
			n.queue_free()
	body = null
	hold = null
	line = null
	tethers = {"A": null, "B": null}
	world = null
	holds = []
	anchor_holds = []
	active = false

## The collision proxy and the rail handholds, all from the EVA package (Godot axes, SHIP frame).
func build_world() -> void:
	var col: Dictionary = eva.collider
	samples = col.samples
	world = StaticBody3D.new()
	world.name = "EvaCollider"
	add_child(world)
	var i := 0
	while i < samples.size() - 1:        # frusta between samples; a run of equal radii is one segment
		var j := i + 1
		while j < samples.size() - 1 and is_equal_approx(float(samples[j][1]), float(samples[i][1])) and is_equal_approx(float(samples[j + 1][1]), float(samples[i][1])):
			j += 1
		var shape := ConvexPolygonShape3D.new()
		var pts := PackedVector3Array()
		for end in [[float(samples[i][0]), float(samples[i][1])], [float(samples[j][0]), float(samples[j][1])]]:
			var rr: float = end[1] / cos(PI / ARC_SEGMENTS)     # circumscribed: the flats lie on the radius, the surface never admits a point inside it
			for k in ARC_SEGMENTS:
				var a := TAU * k / ARC_SEGMENTS
				pts.append(Vector3(end[0], rr * cos(a), rr * sin(a)))
		shape.points = pts
		var cs := CollisionShape3D.new()
		cs.shape = shape
		world.add_child(cs)
		i = j
	var f: Dictionary = col.fitting
	var th := deg_to_rad(float(f.theta_deg))
	var n := Vector3(0.0, sin(th), -cos(th))
	var cyl := CylinderShape3D.new()
	cyl.radius = float(f.radius_m)
	cyl.height = float(f.r_outer) - float(f.r_inner)
	var fs := CollisionShape3D.new()
	fs.shape = cyl
	var xa := Vector3(1, 0, 0)
	fs.transform = Transform3D(Basis(xa, n, xa.cross(n)), Vector3(float(f.x), 0, 0) + n * (float(f.r_inner) + float(f.r_outer)) / 2.0)
	world.add_child(fs)
	for a in eva.anchors:
		var h := WfHandhold.new()
		h.anchor_id = str(a.id)
		h.position = Vector3(a.p[0], a.p[1], a.p[2])
		add_child(h)
		holds.append(h)
		anchor_holds.append(h)
	# J01 rail contact: each run is one rod along x through its anchors (eva_route: rail_standoff_m above the collar skin), from the run's start to
	# its end. The rod section is the trunk handrail's (rig dynamics.stages.trunk), PROTOTYPE: no exterior rail section is released (44!51 RUN-011).
	rail_radius = float(dyn["stages"]["trunk"]["handholds"][0]["radius_m"])
	for run in eva.runs:
		var on: Array = eva.anchors.filter(func(a): return str(a.run) == run)
		if on.is_empty():
			continue
		var x0 := float(eva.runs[run][0])
		var x1 := float(eva.runs[run][1])
		var rod := WfHandhold.new()
		rod.anchor_id = "EVA_RAIL_%s" % str(run).to_upper()
		rod.name = rod.anchor_id
		rod.transform = Transform3D(Basis(Vector3(0, 0, 1), -PI / 2.0), Vector3((x0 + x1) * 0.5, on[0].p[1], on[0].p[2]))   # local +Y along +X
		rod.seg_a = Vector3(0, -absf(x1 - x0) * 0.5, 0)
		rod.seg_b = Vector3(0, absf(x1 - x0) * 0.5, 0)
		var rc := CylinderShape3D.new()
		rc.radius = rail_radius
		rc.height = absf(x1 - x0)
		var cs := CollisionShape3D.new()
		cs.shape = rc
		rod.add_child(cs)
		add_child(rod)
		holds.append(rod)

## Hull radius at x from the samples (flat beyond the ends).
func hull_radius(x: float) -> float:
	var r := float(samples[0][1])
	for s in samples:
		if float(s[0]) > x:
			break
		r = float(s[1])
	return r

## Smallest radial gap between the suited capsule and the hull proxy (negative = inside): the centre and both axis ends, minus the capsule radius.
func hull_clearance() -> float:
	if samples.is_empty() or body == null:
		return INF
	var half: float = float(body.profile["height_m"]) / 2.0 - float(body.profile["radius_m"])
	var ax := body.global_transform.basis.y.normalized()
	var best := INF
	for q in [body.global_position, body.global_position + ax * half, body.global_position - ax * half]:
		best = minf(best, Vector2(q.y, q.z).length() - float(body.profile["radius_m"]) - hull_radius(q.x))
	return best

## ARTISTIC layer: a suit model (the one the rail walk uses) rides the capsule, pose only (it never moves the body, no collision). The model is lying
## along the capsule axis, head aft (-X), feet toward the forward end, face to the hull; the capsule mesh is hidden while it is attached.
func attach_artistic(model: Node3D, height_m := 1.75) -> void:
	model.name = "ARTISTIC_SuitModel"
	model.set_meta("layer", "ARTISTIC: presentation only, follows the physics capsule")
	body.add_child(model)
	for c in body.get_children():
		if c is MeshInstance3D:
			c.visible = false
	var head := Vector3(-1, 0, 0)                     # head direction in the start posture (the capsule +Y after the lying rotation)
	var face := -out_dir
	var wb := Basis(head.cross(face).normalized(), head, face)
	model.transform = Transform3D(body.global_transform.basis.inverse() * wb, body.global_transform.basis.inverse() * (-head * height_m * 0.5))

## Review/check helper: let go, put the body at rest half a metre out of a rail anchor along the collar normal and grip it.
func move_to_anchor(id: String) -> bool:
	for h in holds:
		if h.anchor_id == id:
			body.release()
			body.global_position = h.position + out_dir * 0.5
			body.linear_velocity = Vector3.ZERO
			body.angular_velocity = Vector3.ZERO
			return body.grab(h)
	return false

## Check helper: let go and put the body at rest at p (no grip).
func move_to(p: Vector3) -> void:
	body.release()
	body.global_position = p
	body.linear_velocity = Vector3.ZERO
	body.angular_velocity = Vector3.ZERO

func anchor_hold(id: String) -> WfHandhold:
	for h in anchor_holds:
		if h.anchor_id == id:
			return h
	return null

func v_rel() -> Vector3:
	return body.linear_velocity if body else Vector3.ZERO      # SHIP frame = the ship's own frame

func push(dir: Vector3) -> bool:
	return active and body.push(dir, -1.0, Vector3.ZERO)

func grab() -> bool:
	return active and body.grab_nearest(holds)

# ---- two-tether protocol (EVA-014; mirror of eva_suit.Tethers / eva.gd rail mode) ----------------------------------------------------------

func _bind() -> void:
	if body:
		body.tether = tethers.A
		body.tether_b = tethers.B

func live() -> Array:
	return ["A", "B"].filter(func(k): return tethers[k] != null)

func free_tether() -> String:
	return "B" if tethers.A != null and tethers.B == null else ("A" if tethers.A == null else "")

## The tether to release: the one whose anchor is farther from the body (the newest, nearer one stays).
func older_tether() -> String:
	if live().size() < 2:
		return ""
	return "A" if body.global_position.distance_to(tethers.A.anchor) > body.global_position.distance_to(tethers.B.anchor) else "B"

## Clip tether `which` to anchor `h`: the hand must reach the anchor, one tether per anchor. Returns the refusal, or "".
func clip(which: String, h: WfHandhold) -> String:
	if tethers[which] != null:
		return "tether %s is already clipped" % which
	if h == null or body.global_position.distance_to(h.anchor_point()) > body.reach():
		return "no anchor within hand reach"
	for k in live():
		if tethers[k].anchor_id == h.anchor_id:
			return "both tethers on one anchor are not independent"
	tethers[which] = WfTether.new(h.anchor_point(), tether.length if tether != null else float(eva.get("tether_reach_m", 2.0)), true, h.anchor_id)
	tested[which] = false
	_bind()
	return ""

func test(which: String) -> String:
	if tethers[which] == null:
		return "tether %s is not clipped" % which
	tested[which] = true
	return ""

func release(which: String) -> String:
	var other := "B" if which == "A" else "A"
	if tethers[which] == null:
		return "tether %s is not clipped" % which
	if tethers[other] == null or not tested[other]:
		return "release refused: tether %s must be clipped and tested first" % other
	tethers[which] = null
	tested[which] = false
	_bind()
	return ""

## T: clip the free tether to the nearest free anchor within hand reach.
func clip_next() -> String:
	var f := free_tether()
	if f == "":
		return "both tethers are clipped: release one first"
	var best: WfHandhold = null
	for h in anchor_holds:
		if live().any(func(k): return tethers[k].anchor_id == h.anchor_id):
			continue
		if best == null or body.global_position.distance_to(h.anchor_point()) < body.global_position.distance_to(best.anchor_point()):
			best = h
	return clip(f, best)

## Y: tug-test the untested tether.
func test_untested() -> String:
	for k in live():
		if not tested[k]:
			return test(k)
	return "nothing to test"

## R: release the older tether (refused unless the other is clipped and tested).
func release_older() -> String:
	var k := older_tether()
	return release(k) if k != "" else "release refused: only one tether is clipped"

## Check helper: drop tether `which` with no protocol (the unclipped review case only; never bound to a key).
func force_unclip(which := "A") -> void:
	if tethers[which] != null:
		tethers[which].unclip()

## Experimental jet (OFF by default; never bound to a key when off): one impulse of the profile push limit, not a canon capability.
func jet(dir: Vector3) -> bool:
	if not experimental_thruster or not active or body.grip != null:
		return false
	body.apply_central_impulse(dir.normalized() * body.test_push_impulse())
	return true

func hud_text() -> String:
	if not active:
		return ""
	var tl := ""
	for k in ["A", "B"]:
		var t: WfTether = tethers[k]
		tl += "\n%s: %s" % [k, "-" if t == null else "%s %s  dist %.2f m  %s" % [t.anchor_id, "tested" if tested[k] else "UNTESTED", body.global_position.distance_to(t.anchor), t.label()]]
	return "DRIFT (SIMULATION_ONLY, FLIGHT_EVA HOLD)  field %.3f g  v_rel %.3f m/s  grip %s  |  tethers live %d (never zero)  |  thruster %s%s\n" % [
		field.g_of(field.eval(WfFrames.from_vec(body.global_position), WfFrames.from_vec(body.linear_velocity))), v_rel().length(),
		body.grip.anchor_id if body.grip else "-", live().size(), "EXPERIMENTAL" if experimental_thruster else "off", tl] \
		+ WfInput.keys("{eva.drift} back to the hatch  {eva.push} push off  {eva.grab} grab nearest handhold or rail  {eva.clip} clip  {eva.tug_test} test  {eva.release_tether} release the older")

func _process(_dt: float) -> void:
	if not active:
		return
	var m: ImmediateMesh = line.mesh
	m.clear_surfaces()
	var any := false
	for k in live():
		if tethers[k].clipped:
			if not any:
				m.surface_begin(Mesh.PRIMITIVE_LINES)
				any = true
			m.surface_add_vertex(tethers[k].anchor)
			m.surface_add_vertex(body.global_position)
	if any:
		m.surface_end()
