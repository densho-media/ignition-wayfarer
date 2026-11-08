class_name WfMagBoots
extends RefCounted
## LOCO-002 (docs/LOCOMOTION.md): the Y155 suit's magnetic boots, a PROTOTYPE mechanism for the training simulation (FLIGHT_EVA HOLD).
## Two boots, each with its own state, on the one designated walkway (WfEvaWorld.mag_surface; data/eva_ops.toml [mag_boots]):
##   OFF       the pad is switched off (electro-permanent: no power either way); the boot holds nothing
##   SEEK      the pad is on and the boot is not on the plate; it attaches when its sole is within capture_gap_m of the plate, closing slower
##             than capture_speed_m_s and within capture_angle_deg of it
##   ATTACHED  the pad pulls the boot to the plate with attach_force_n; friction (sole_friction x the normal load) is what the feet can push with
##   SWING     a stepping boot lifted off the plate by the gait (no force); it lands, and attaches, at the start of its next stance
## The pull is a bounded force on the body (WfEvaBody adds it to the field's normal load), never a constraint: a thruster or a shear field
## stronger than the pull and friction moves the body, and a boot pulled release_gap_m off the plate has broken away. The gait is driven by
## the distance walked (the clip's stride), with stance_fraction > 0.5, and a boot only lifts while the other is attached: one boot is always
## on the plate while walking. A swinging boot that cannot land (the plate's edge) stops the walk.

enum B { OFF, SEEK, ATTACHED, SWING }

var p: Dictionary
var world: WfEvaWorld
var feet_local: Array = []         # sole centres in the body frame (body origin = mass centre)
var sole_local := Vector3.ZERO     # the sole plane's centre (the suit frame origin) in the body frame
var st := [B.OFF, B.OFF]
var armed := false
var phase := 0.0                   # gait cycle position (cycles)
var force_n := 200.0
var mu := 0.5
var stride := 0.6
var stance := 0.62
var normal := Vector3.UP           # the plate's outward normal under the feet
var gap := 1.0                     # sole gap to the plate (m); negative inside the contact tolerance
var on_plate := false
var blocked := ""                  # why the walk is stopped by the boots ("" when free)
var slipping := false
var captures := 0
var breakaways := 0
var slips := 0
var lifts := 0
var single_support_min := 2        # fewest boots attached while walking (the check asks for >= 1)
var events: Array = []

func _init(params: Dictionary, w: WfEvaWorld, feet: Array, sole: Vector3) -> void:
	p = params
	world = w
	feet_local = feet
	sole_local = sole
	force_n = float(p["attach_force_n"])
	mu = float(p["sole_friction"])
	stride = 2.0 * float(p["gait"]["step_m"])
	stance = float(p["gait"]["stance_fraction"])

func count() -> int:
	return (1 if st[0] == B.ATTACHED else 0) + (1 if st[1] == B.ATTACHED else 0)

func state_name(i: int) -> String:
	return B.keys()[st[i]]

## The pads on (SEEK: they attach when the soles meet the plate) or off (release: both boots let go at once).
func arm(on: bool) -> void:
	armed = on
	for i in 2:
		if not on:
			if st[i] == B.ATTACHED:
				_event("release", i)
			st[i] = B.OFF
		elif st[i] == B.OFF:
			st[i] = B.SEEK

func _event(kind: String, i: int) -> void:
	events.append({"kind": kind, "boot": "LR"[i], "frame": Engine.get_physics_frames()})
	if events.size() > 64:
		events.pop_front()

## Attach and break-away for this step; returns [pull per kg toward the plate (m/s2), plate normal]. v: the body's velocity (world).
func step(xf: Transform3D, v: Vector3, mass: float) -> Array:
	var sole := world.mag_surface(xf * sole_local)
	normal = sole["n"]
	gap = sole["gap"]
	var up := xf.basis.orthonormalized().y
	on_plate = true
	for i in 2:
		var q := world.mag_surface(xf * (feet_local[i] as Vector3))
		if not q["on"]:
			on_plate = false
		match st[i]:
			B.ATTACHED:
				if not q["on"] or gap > float(p["release_gap_m"]):
					st[i] = B.SEEK if armed else B.OFF
					breakaways += 1
					_event("break_away", i)
			B.SEEK:
				if armed and q["on"] and gap <= float(p["capture_gap_m"]) and absf(v.dot(normal)) <= float(p["capture_speed_m_s"]) \
						and up.dot(normal) >= cos(deg_to_rad(float(p["capture_angle_deg"]))):
					st[i] = B.ATTACHED
					captures += 1
					_event("attach", i)
	return [count() * force_n / maxf(mass, 1.0), normal]

## The gait for this step, after the feet acted: `speed` the body's speed over the plate, `ahead` the requested walking direction (world,
## or zero). The edge test uses the request, so a stopped walker stays stopped while it still asks to go over the edge.
func advance(xf: Transform3D, speed: float, ahead: Vector3, dt: float) -> void:
	var edge := false
	if not armed or (count() == 0 and st[0] != B.SWING and st[1] != B.SWING):
		blocked = ""
		return
	if ahead.length() > 0.05:
		# the landing point of the next step must be on the plate
		var land := xf * sole_local + ahead.normalized() * stride * 0.5
		edge = not world.mag_surface(land)["on"]
	var walking := speed > 0.01 or (ahead.length() > 0.05 and not edge)
	var wait := ""
	if walking:
		phase += speed * dt / stride
	for i in 2:
		var in_stance := fposmod(phase + 0.5 * i, 1.0) < stance
		var other: int = 1 - i
		if not walking:
			in_stance = true                   # standing still: both feet down
		if st[i] == B.ATTACHED and not in_stance:
			if st[other] == B.ATTACHED:
				st[i] = B.SWING
				lifts += 1
				_event("lift", i)
			else:
				phase -= speed * dt / stride       # the other boot is not down yet: this one stays planted, the step waits
				wait = "waiting for the other boot"
		elif st[i] == B.SWING and in_stance:
			var q := world.mag_surface(xf * (feet_local[i] as Vector3))
			if q["on"] and gap <= float(p["capture_gap_m"]):
				st[i] = B.ATTACHED
				captures += 1
				_event("attach", i)
			else:
				wait = "the stepping boot found no plate"
	blocked = "edge" if edge else wait
	if walking:
		single_support_min = mini(single_support_min, count())

func record() -> Dictionary:
	return {"armed": armed, "left": state_name(0), "right": state_name(1), "attached": count(), "gap_mm": snappedf(gap * 1000.0, 0.1),
		"on_plate": on_plate, "blocked": blocked, "slipping": slipping, "captures": captures, "breakaways": breakaways, "slips": slips,
		"lifts": lifts, "min_attached_walking": single_support_min}
