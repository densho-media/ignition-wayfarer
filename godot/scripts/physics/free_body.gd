class_name WfFreeBody
extends RigidBody3D
## A body that Godot only collides: `_integrate_forces` adds the frame field to the velocity (semi-implicit), and nothing else. No
## gravity, no damping, no key input (DYN-016, SIM-010, GEN-005). The field comes from a shared WfFrameField (rig `dynamics`).

var field: WfFrameField
var field_now := Vector3.ZERO     # the field applied in the last step
var steps := 0                    # integrator calls since spawn
var contacts := 0
var contact_step := -1            # first step that reported a contact, and where
var contact_pos := Vector3.ZERO
var held := false                 # joined to a hand: the position correction below is skipped
var v_solved := Vector3.ZERO      # velocity at the start of the step, i.e. after the last contact solve (linear_velocity reads one field step ahead)
var pre_pos := Vector3.ZERO       # state and field of the last step before the first contact (for an impact point inside the step)
var pre_vel := Vector3.ZERO
var pre_acc := Vector3.ZERO
var pre_step := 0
var _last_pos := Vector3.ZERO
var _last_vel := Vector3.ZERO
var _last_acc := Vector3.ZERO

func setup_body(mass_kg: float) -> void:
	mass = mass_kg
	custom_integrator = true
	gravity_scale = 0.0
	linear_damp_mode = RigidBody3D.DAMP_MODE_REPLACE
	angular_damp_mode = RigidBody3D.DAMP_MODE_REPLACE
	linear_damp = 0.0
	angular_damp = 0.0
	can_sleep = false
	continuous_cd = true
	contact_monitor = true
	max_contacts_reported = 8
	var pm := PhysicsMaterial.new()    # PROTOTYPE contact surface: no bounce; tangential friction is the foot model in crew_body.gd
	pm.friction = 0.0
	pm.bounce = 0.0
	physics_material_override = pm

func _integrate_forces(state: PhysicsDirectBodyState3D) -> void:
	steps += 1
	contacts = state.get_contact_count()
	if contacts > 0 and contact_step < 0:
		contact_step = steps
		contact_pos = state.transform.origin
		pre_pos = _last_pos
		pre_vel = _last_vel
		pre_acc = _last_acc
		pre_step = steps - 1
	var dt := state.step
	var v := state.linear_velocity
	v_solved = v
	_last_pos = state.transform.origin
	_last_vel = v
	var a := field.accel(state.transform.origin, v)
	if contacts == 0 and not held:
		# free flight: the field is evaluated at the half step (position and velocity), exact for a constant field and second order for Coriolis
		a = field.accel(state.transform.origin + v * (0.5 * dt), v + a * (0.5 * dt))
	field_now = a
	_last_acc = a
	state.linear_velocity = v + a * dt
	# the engine moves the body by v_new * dt; remove the extra a*dt^2/2 so a free body follows x + v t + a t^2 / 2 (skipped in contact or held)
	if contacts == 0 and not held:
		var t := state.transform
		t.origin -= a * (0.5 * dt * dt)
		state.transform = t
	_after_field(state, a)

func _after_field(_state: PhysicsDirectBodyState3D, _a: Vector3) -> void:
	pass
