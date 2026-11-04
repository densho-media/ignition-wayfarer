class_name WfEvaControl
extends RefCounted
## Flight control of one EVA body (EVA-OPS-001). It only ever writes the body's commanded force and torque (body frame); the allocator
## turns them into valve duties and the body burns the gas they need. So every correction, including assisted braking, attitude hold,
## position keeping and every autopilot move, is real thrust with a real gas cost. MANUAL passes the player's stick straight to the
## valves (full axis authority at full deflection); ASSIST adds rate damping and, with the stick centred, attitude hold, braking and
## position keeping relative to the ship (or to a moving target). Gains are the PROTOTYPE values of data/eva_ops.toml [assist].

enum Mode { MANUAL, ASSIST }

var body: WfEvaBody
var mode := Mode.ASSIST
var g: Dictionary                    # [assist]
var rate_max := 0.25                 # rad/s at full stick (assisted)
var throttle := 1.0                  # fine control scales the stick
var attitude_hold := true
var brake := false                   # assisted: null the velocity relative to the reference
var hold_pos := false                # assisted: keep station at hold_point
var hold_point := Vector3.ZERO
var ref_vel := Vector3.ZERO          # reference velocity (ship frame: zero; a target body's velocity when matching it)
var _hold_basis := Basis.IDENTITY
var _had_rot := true

func _init(b: WfEvaBody, assist: Dictionary, rate := 0.25) -> void:
	body = b
	g = assist
	rate_max = rate
	_hold_basis = b.global_transform.basis.orthonormalized()

## Player step: t_in and r_in are stick values in [-1, 1] per body axis (translation x y z, rotation about x y z).
func step_player(t_in: Vector3, r_in: Vector3) -> void:
	var a := body.alloc
	if a == null:
		return
	var f := Vector3.ZERO
	var t := Vector3.ZERO
	var tl := a.force_limit(t_in)
	f = Vector3(t_in.x * tl.x, t_in.y * tl.y, t_in.z * tl.z) * throttle
	if mode == Mode.MANUAL:
		var rl := a.torque_limit(r_in)
		t = Vector3(r_in.x * rl.x, r_in.y * rl.y, r_in.z * rl.z) * throttle
		_had_rot = true
	else:
		var rot_cmd := r_in.length() > 0.01
		if rot_cmd:
			t = rate_torque(r_in * rate_max * throttle)
			_had_rot = true
		elif attitude_hold:
			if _had_rot:
				# hold the attitude reached once the rates have been damped
				if body.angular_velocity.length() < float(g["deadband_rad_s"]) * 3.0:
					_hold_basis = body.global_transform.basis.orthonormalized()
					_had_rot = false
				t = rate_torque(Vector3.ZERO)
			else:
				t = attitude_torque(_hold_basis)
		else:
			t = rate_torque(Vector3.ZERO)
		if t_in.length() < 0.01:
			if hold_pos:
				f = position_force(hold_point, ref_vel)
			elif brake:
				f = velocity_force(ref_vel)
	body.cmd_f = f
	body.cmd_t = t

func idle() -> void:
	body.cmd_f = Vector3.ZERO
	body.cmd_t = Vector3.ZERO

## Torque (body frame) that drives the body rate to w_des_body within the rate-damping time, limited by the axis authority.
func rate_torque(w_des_body: Vector3) -> Vector3:
	var r := body.global_transform.basis.orthonormalized()
	var w_b := r.transposed() * body.angular_velocity
	var err := w_des_body - w_b
	if err.length() < float(g["deadband_rad_s"]) and w_des_body.length() < 1e-6:
		return Vector3.ZERO
	var t := body.inertia_t * err / float(g["rate_damp_s"])
	return clamp_t(t)

## Torque that turns the body to `target` (world basis): a rate command proportional to the rotation error.
func attitude_torque(target: Basis) -> Vector3:
	var r := body.global_transform.basis.orthonormalized()
	var q := Quaternion(r.transposed() * target.orthonormalized())       # rotation from the body to the target, body frame
	if q.w < 0.0:
		q = -q
	var axis := Vector3(q.x, q.y, q.z)
	var s := axis.length()
	var ang := 2.0 * atan2(s, q.w)
	var w_des := Vector3.ZERO
	if s > 1e-9 and ang > 0.004:
		w_des = axis / s * minf(ang / float(g["attitude_hold_s"]), rate_max)
	return rate_torque(w_des)

## Force (body frame) that brings the velocity to v_ref (world) within the brake time.
func velocity_force(v_ref: Vector3) -> Vector3:
	var dv := v_ref - body.linear_velocity
	if dv.length() < float(g["deadband_m_s"]):
		return Vector3.ZERO
	var f_w := dv * body.total_mass() / float(g["brake_s"])
	return clamp_f(body.global_transform.basis.orthonormalized().transposed() * f_w)

## Force that keeps station at p (world), moving with v_ref.
func position_force(p: Vector3, v_ref: Vector3) -> Vector3:
	var e := p - body.global_position
	var tau := float(g["hold_position_s"])
	var v_des := v_ref + e / tau
	if v_des.distance_to(v_ref) > 0.3:
		v_des = v_ref + (v_des - v_ref).normalized() * 0.3
	return velocity_force(v_des)

func clamp_f(f_b: Vector3) -> Vector3:
	var l := body.alloc.force_limit(f_b)
	return Vector3(clampf(f_b.x, -l.x, l.x), clampf(f_b.y, -l.y, l.y), clampf(f_b.z, -l.z, l.z))

func clamp_t(t_b: Vector3) -> Vector3:
	var l := body.alloc.torque_limit(t_b)
	return Vector3(clampf(t_b.x, -l.x, l.x), clampf(t_b.y, -l.y, l.y), clampf(t_b.z, -l.z, l.z))

## Smallest pure force authority of the configuration (N): what braking can count on along any axis.
func min_force() -> float:
	var a := body.alloc
	var m := INF
	for ax in ["+Fx", "-Fx", "+Fy", "-Fy", "+Fz", "-Fz"]:
		m = minf(m, a.authority(ax))
	return m

## Autopilot step towards p_goal (world), arriving with v_goal, nose (-Z) along `face` (world, or zero to keep pointing at the goal).
## The approach speed follows the braking the configuration can actually do: v = sqrt(2 a d) with a = brake_fraction x min authority / m.
func step_goto(p_goal: Vector3, v_goal: Vector3, face: Vector3, v_max: float, up_hint := Vector3.UP) -> float:
	var e := p_goal - body.global_position
	var d := e.length()
	var a_brk := float(g["autopilot_brake_fraction"]) * min_force() / body.total_mass()
	var sp := minf(v_max, sqrt(2.0 * a_brk * d))
	var v_des := v_goal + (e / d * sp if d > 1e-4 else Vector3.ZERO)
	var dv := v_des - body.linear_velocity
	var f_w := Vector3.ZERO
	if dv.length() > float(g["deadband_m_s"]) * 0.5:
		f_w = dv * body.total_mass() / maxf(0.6, float(g["brake_s"]) * 0.5)
	body.cmd_f = clamp_f(body.global_transform.basis.orthonormalized().transposed() * f_w)
	var fwd := face if face.length() > 0.01 else (e if d > 0.5 else Vector3.ZERO)
	if fwd.length() > 0.01:
		var z := -fwd.normalized()
		var up := up_hint
		if absf(z.dot(up)) > 0.95:
			up = Vector3.RIGHT
		var x := up.cross(z).normalized()
		var y := z.cross(x)
		body.cmd_t = attitude_torque(Basis(x, y, z))
	else:
		body.cmd_t = rate_torque(Vector3.ZERO)
	return d
