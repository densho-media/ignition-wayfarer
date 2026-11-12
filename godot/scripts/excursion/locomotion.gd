class_name WfLocomotion
extends RefCounted
## LOCO-001 (docs/LOCOMOTION.md): the trainee on a ring deck as a third-person character: walk, run, turn, jump and land in spin gravity.
## The physics stays WfCrewBody's: the ring-frame field (centrifugal, Coriolis, Euler) and a friction-limited foot contact. This only turns
## the keys into a walking request (direction and speed), queues the legs' jump impulse, keeps the body's heading, and makes the newcomer
## model follow: the clip, its playback rate (physics speed / clip speed: no foot sliding) and the crossfades. Root motion is stripped in
## WfCharacterRig, so the clip never moves the body.
##
## States: GROUND (idle / step / walk / walk backward / run, by the measured speed over the floor), TAKEOFF (the jump clip's crouch and
## extension; the impulse at its end), AIR (ballistic in the ring frame until a floor contact), LAND (the landing clip).

enum S { GROUND, TAKEOFF, AIR, LAND }

var actor: WfCrewBody
var rig: WfCharacterRig
var p := {}                         # data/characters.toml [locomotion], through characters.json
var state := S.GROUND
var t_state := 0.0
var heading := Vector3.FORWARD      # the body's facing on the floor (ring-frame axes)
var turn_now := 0.0                 # rad/s of heading change in the last step (for the stepping clip)
var backpedal := false
var clip := ""
var air_t := 0.0
var jumps := 0
var landings := 0
var last_takeoff_speed := 0.0
var max_rise := 0.0
var _rise0 := 0.0
var land_speed := 0.0
var log: Array = []
var axis_point := Vector3.ZERO      # the ring's spin axis (ring frame): the deck's local up points at it
var axis_dir := Vector3.RIGHT
var _r0 := 0.0

func _init(a: WfCrewBody, r: WfCharacterRig, params: Dictionary) -> void:
	actor = a
	rig = r
	p = params

func num(k: String, d: float) -> float:
	return float(p.get(k, d))

## One physics step. `wish`: the requested direction on the floor (camera-relative, |.| <= 1); `run`: Shift; `back_only`: S alone.
func step(dt: float, wish: Vector3, run: bool, back_only: bool, jump_pressed: bool) -> void:
	t_state += dt
	var up := deck_up()
	var h := (heading - up * heading.dot(up))
	heading = h.normalized() if h.length() > 1e-4 else _any_perp(up)
	var on_floor := actor.standing
	match state:
		S.GROUND:
			if not on_floor:
				air_t += dt
				if air_t > 0.15:
					_enter(S.AIR)
			else:
				air_t = 0.0
			if jump_pressed and on_floor:
				_enter(S.TAKEOFF)
		S.TAKEOFF:
			if t_state >= rig.length("jump") or not rig.ok:
				if actor.jump(num("jump_dv_m_s", 1.4)):
					jumps += 1
					last_takeoff_speed = num("jump_dv_m_s", 1.4)
					_r0 = _radius()
					max_rise = 0.0
					_enter(S.AIR)
				else:
					_enter(S.GROUND)
		S.AIR:
			max_rise = maxf(max_rise, _r0 - _radius())
			if on_floor and t_state > 0.1:
				landings += 1
				land_speed = absf(actor.v_solved.dot(up))
				_enter(S.LAND)
		S.LAND:
			if t_state >= rig.length("land") or not rig.ok:
				_enter(S.GROUND)
	# the walking request: the feet act only in GROUND and LAND (the contact force model limits what they can do)
	var speed := num("run_speed_m_s", 2.4) if run else num("walk_speed_m_s", 1.0)
	backpedal = back_only
	var d := wish - up * wish.dot(up)
	if state == S.TAKEOFF:
		d = Vector3.ZERO                # the legs are pushing down, not along
	if back_only:
		d = -heading * minf(1.0, d.length())
		speed = num("backpedal_speed_m_s", 0.6)
	actor.walk_speed = speed
	actor.walk_dir = d if state != S.AIR else Vector3.ZERO
	# heading: toward the requested direction (not while backpedalling or in the air), at most turn_rate
	var h0 := heading
	if not back_only and d.length() > 0.05 and state != S.AIR:
		var target := d.normalized()
		var ang := heading.signed_angle_to(target, up)
		var lim := deg_to_rad(num("turn_rate_deg_s", 360.0)) * dt
		heading = heading.rotated(up, clampf(ang, -lim, lim)).normalized()
	turn_now = h0.signed_angle_to(heading, up) / maxf(dt, 1e-6)

func _enter(s: S) -> void:
	state = s
	t_state = 0.0
	log.append({"state": S.keys()[s], "frame": Engine.get_physics_frames()})

## The deck's local up: from the body toward the spin axis (the centrifugal field's direction, without the Coriolis part that tilts the
## apparent field of a moving body). The view, the camera and the model use it; the physics uses the full field.
func deck_up() -> Vector3:
	var p := actor.global_position - axis_point
	var radial := p - axis_dir * p.dot(axis_dir)
	return -radial.normalized() if radial.length() > 0.5 else actor.up_now

## Distance from the spin axis (m): a jump's rise is how much nearer the axis it carries the body.
func _radius() -> float:
	var p := actor.global_position - axis_point
	return (p - axis_dir * p.dot(axis_dir)).length()

static func _any_perp(up: Vector3) -> Vector3:
	return up.cross(Vector3.RIGHT if absf(up.x) < 0.9 else Vector3.BACK).normalized()

## Speed over the floor (m/s): the body's ring-frame velocity across the floor normal.
func floor_speed() -> float:
	var v := actor.linear_velocity
	var n := actor.floor_normal
	return (v - n * v.dot(n)).length()

## The clip for the current physics state, and its rate. Called every rendered frame (dt: the frame time). With the gait tree (LOCO-003)
## the deck clips are one speed-indexed blend; otherwise the clip is picked by speed and crossfaded (LOCO-001).
func animate(dt := 1.0 / 60.0) -> void:
	if not rig.ok:
		return
	var v := floor_speed()
	_lean_step(dt)
	match state:
		S.TAKEOFF:
			_play("jump", 1.0, 0.08)
		S.AIR:
			_play("fall", 1.0, 0.15)
		S.LAND:
			_play("land", 1.0, 0.06)
		_:
			var fwd_v := actor.linear_velocity.dot(heading)
			if rig.tree != null:
				if v < 0.08 and absf(turn_now) > deg_to_rad(25.0):
					_play("step", 1.0, 0.2)
				else:
					rig.gait(v, backpedal and fwd_v < 0.0, dt, num("walk_run_from_m_s", 1.3), num("walk_run_to_m_s", 1.9))
					clip = rig.current
				return
			if v < 0.08:
				if absf(turn_now) > deg_to_rad(25.0):
					_play("step", 1.0, 0.2)
				else:
					_play("idle", 1.0, 0.3)
			elif backpedal and fwd_v < 0.0:
				_play("walk", -rig.rate_for("walk", v), 0.25)
			elif v > 0.5 * (num("walk_speed_m_s", 1.0) + num("run_speed_m_s", 2.4)) * 0.75:
				_play("run", rig.rate_for("run", v), 0.25)
			else:
				_play("walk", rig.rate_for("walk", v), 0.25)

## LOCO-003: the whole body leans into its horizontal acceleration (speeding up, braking, the centripetal pull of a turn) as a runner's
## does: tan(lean) = a / g with g the deck's support load, so at 0.5 g the same push leans twice as far as on Earth. Smoothed over
## about 0.15 s and capped; only while the feet are on the deck.
var lean := Vector3.ZERO           # rotation vector (axis * angle, rad) of the model about its soles
var _v_prev := Vector3.INF
var _acc := Vector3.ZERO
func _lean_step(dt: float) -> void:
	if dt <= 0.0:
		return
	var up := deck_up()
	var v := actor.linear_velocity - up * actor.linear_velocity.dot(up)
	if _v_prev == Vector3.INF:
		_v_prev = v
	var a := (v - _v_prev) / dt
	_v_prev = v
	_acc = _acc.lerp(a - up * a.dot(up), 1.0 - exp(-dt / 0.15))
	var want := Vector3.ZERO
	if state in [S.GROUND, S.LAND] and actor.standing:
		var g := maxf(actor.floor_load, 0.5)
		var ang := minf(atan(_acc.length() / g) * num("lean_gain", 0.7), deg_to_rad(num("lean_max_deg", 12.0)))
		if _acc.length() > 0.05:
			want = up.cross(_acc.normalized()) * ang
	lean = lean.lerp(want, 1.0 - exp(-dt / 0.1))

func _play(c: String, rate: float, blend: float) -> void:
	clip = c
	rig.play(c, rate, blend)

## The model's transform: feet on the floor under the capsule (its bottom is the sole plane), facing the heading, up the body's up.
func model_transform() -> Transform3D:
	var up := deck_up()
	var z := heading
	var x := up.cross(z).normalized()
	var half: float = float(actor.profile["height_m"]) * 0.5
	var b := Basis(x, up, z)
	if lean.length() > 1e-5:
		b = Basis(lean.normalized(), lean.length()) * b
	return Transform3D(b, actor.global_position - up * half)

func record() -> Dictionary:
	return {"state": S.keys()[state], "clip": clip, "speed": snappedf(floor_speed(), 0.01), "standing": actor.standing,
		"jumps": jumps, "landings": landings, "rise": snappedf(max_rise, 0.001), "model": rig.ok}
