class_name WfCrewBody
extends WfFreeBody
## The crew actor: a capsule from the rig profile. An unpowered body never accelerates from input (DYN-016): input only selects grab,
## release, push and a walking request. A grip is a rigid joint to a marked handhold (DYN-011); a push is an impulse at the hand point
## J = mass * test_push_dv by default (DYN-010; DYN-024: a test input, not a physical cap), so an off-centre hand point gives a spin. Walking exists only on a floor under a real field,
## as a friction-limited contact force.

const WALK_MU := 0.6                 # PROTOTYPE friction coefficient of the foot contact
const GRIP_FIELD_G := 0.05           # below this the field is too weak to define an "up" (walk and keep-upright need more)

var profile := {}
var profile_name := ""
var g0 := 9.80665
var grip: WfHandhold = null
var grip_joint: Generic6DOFJoint3D = null
var hand_offset := Vector3.ZERO      # from the body centre to the gripped anchor point, in world axes at the grab
var tool_joint: Generic6DOFJoint3D = null
var held_tool: WfFreeBody = null
var walk_dir := Vector3.ZERO         # requested direction along the floor (|.| <= 1); zero holds still on a floor
var standing := false
var up_now := Vector3.UP
# LADDER technique (PROTOTYPE, M2): hand over hand on the rungs the hands carry the body at `ladder_v` (frame axes, m/s); INF = off. The field
# still acts; the hands supply the difference, logged as `hand_impulse` (N s per step) = m (ladder_v - v after the field). No hand-load limit is
# sourced, so the load is measured, never judged.
var ladder_v := Vector3.INF
var ladder_up := Vector3.ZERO        # on the ladder the hands hold the body parallel to it (head inboard), not along the apparent gravity
var hand_impulse := Vector3.ZERO

func configure(dyn: Dictionary, name: String, f: WfFrameField) -> void:
	profile_name = name
	profile = dyn["profiles"][name]
	g0 = dyn["standard_gravity_m_s2"]
	field = f
	setup_body(profile["mass_kg"])
	var cs := CollisionShape3D.new()
	var cap := CapsuleShape3D.new()
	cap.radius = profile["radius_m"]
	cap.height = profile["height_m"]
	cs.shape = cap
	add_child(cs)
	var mi := MeshInstance3D.new()
	var cm := CapsuleMesh.new()
	cm.radius = cap.radius
	cm.height = cap.height
	mi.mesh = cm
	add_child(mi)

func reach() -> float: return profile["reach_m"]
func test_push_impulse() -> float: return profile["mass_kg"] * profile["test_push_dv_m_s"]

static func _lock(j: Generic6DOFJoint3D, angular: bool) -> void:
	for ax in 3:
		var set_flag: Callable = [j.set_flag_x, j.set_flag_y, j.set_flag_z][ax]
		var set_param: Callable = [j.set_param_x, j.set_param_y, j.set_param_z][ax]
		set_flag.call(Generic6DOFJoint3D.FLAG_ENABLE_LINEAR_LIMIT, true)
		set_param.call(Generic6DOFJoint3D.PARAM_LINEAR_LOWER_LIMIT, 0.0)
		set_param.call(Generic6DOFJoint3D.PARAM_LINEAR_UPPER_LIMIT, 0.0)
		if angular:
			set_flag.call(Generic6DOFJoint3D.FLAG_ENABLE_ANGULAR_LIMIT, true)
			set_param.call(Generic6DOFJoint3D.PARAM_ANGULAR_LOWER_LIMIT, 0.0)
			set_param.call(Generic6DOFJoint3D.PARAM_ANGULAR_UPPER_LIMIT, 0.0)

func _joint(a: PhysicsBody3D, b: PhysicsBody3D, angular: bool) -> Generic6DOFJoint3D:
	var j := Generic6DOFJoint3D.new()
	j.transform = Transform3D(Basis.IDENTITY, b.global_position)     # the world node above is at the identity
	j.node_a = a.get_path()
	j.node_b = b.get_path()
	_lock(j, angular)
	get_parent().add_child(j)
	return j

func can_reach(h: WfHandhold) -> bool:
	return global_position.distance_to(h.anchor_near(global_position)) <= reach()

func nearest_reachable(handholds: Array) -> WfHandhold:
	var best: WfHandhold = null
	var d := INF
	for h in handholds:
		var dd: float = global_position.distance_to(h.anchor_near(global_position))
		if dd <= reach() and dd < d:
			best = h
			d = dd
	return best

## Close the hand on a marked handhold within reach. The joint pins the body centre to the handhold, so its constraint impulse stops the
## body; the angular rate is taken out by the hand while the grip lasts.
func grab(h: WfHandhold) -> bool:
	if grip != null or h == null or not can_reach(h):
		return false
	hand_offset = h.anchor_near(global_position) - global_position
	grip = h
	held = true
	grip_joint = _joint(h, self, false)
	return true

func grab_nearest(handholds: Array) -> bool:
	return grab(nearest_reachable(handholds))

func release() -> void:
	if grip_joint:
		grip_joint.free()
	grip_joint = null
	grip = null
	held = false

## Push off the gripped handhold: release, then an impulse (default m * test_push_dv, DYN-024 test value) at the hand point (world axes).
func push(dir: Vector3, impulse := -1.0, offset := Vector3.INF) -> bool:
	if grip == null or dir.length() < 1e-9:
		return false
	var j := test_push_impulse() if impulse < 0.0 else impulse      # the test speed is a demo input, not a cap (DYN-024)
	var off := hand_offset if offset == Vector3.INF else offset
	release()
	apply_impulse(dir.normalized() * j, off)
	return true

func can_reach_tool(t: WfFreeBody) -> bool:
	return global_position.distance_to(t.global_position) <= reach()

func grab_tool(t: WfFreeBody) -> bool:
	if held_tool != null or t == null or not can_reach_tool(t):
		return false
	held_tool = t
	t.held = true
	tool_joint = _joint(self, t, true)
	return true

func release_tool() -> void:
	if tool_joint:
		tool_joint.free()
	tool_joint = null
	if held_tool:
		held_tool.held = false
	held_tool = null

func on_ladder(v: Vector3) -> void:
	release()
	ladder_v = v
	held = true

func off_ladder() -> void:
	ladder_v = Vector3.INF
	hand_impulse = Vector3.ZERO
	held = false

func _after_field(state: PhysicsDirectBodyState3D, a: Vector3) -> void:
	var dt := state.step
	standing = false
	var strong := a.length() > GRIP_FIELD_G * g0
	var climbing := ladder_v != Vector3.INF
	if climbing:
		hand_impulse = mass * (ladder_v - state.linear_velocity)
		state.linear_velocity = ladder_v
	if strong:
		up_now = -a.normalized()
		var nf := Vector3.ZERO
		for i in contacts:
			var n := state.get_contact_local_normal(i)
			if n.dot(up_now) < 0.0:
				n = -n
			if n.dot(up_now) > 0.5:
				nf += n
		standing = nf != Vector3.ZERO and not climbing
		if standing:
			nf = nf.normalized()
			# foot contact: tangential speed toward the request, limited by mu * N (N/m = the support acceleration)
			var v := state.linear_velocity
			var want := walk_dir - nf * walk_dir.dot(nf)
			want = want.limit_length(1.0) * profile["test_push_dv_m_s"]
			var dv := (want - (v - nf * v.dot(nf))).limit_length(WALK_MU * maxf(0.0, -a.dot(nf)) * dt)
			state.linear_velocity = v + dv
	if climbing and ladder_up != Vector3.ZERO:
		up_now = ladder_up
	if (standing or grip != null or climbing) and (strong or (climbing and ladder_up != Vector3.ZERO)):     # the hands set the pose on a line
		var t := state.transform
		if t.basis.y.angle_to(up_now) > 1e-4:
			var fwd := -t.basis.z
			fwd -= up_now * fwd.dot(up_now)
			if fwd.length() < 0.1:
				fwd = up_now.cross(Vector3.RIGHT if absf(up_now.x) < 0.9 else Vector3.UP)
			t.basis = Basis.looking_at(fwd.normalized(), up_now)
			state.transform = t
		state.angular_velocity = Vector3.ZERO
	elif grip != null or climbing:
		state.angular_velocity = Vector3.ZERO
