class_name WfTetheredBody
extends WfCrewBody
## Crew body with the EVA tethers applied inside the integrator step, so the body ends each step on or inside the sphere of each clipped
## tether's length (no one-step overshoot). A tether never pulls; at its limit it applies the logged tension impulse on the outward speed
## only. Two tethers (A, B: the two-tether protocol, EVA-014) are applied one after the other in the same step (PROTOTYPE rigid limit).

var tether: WfTether = null
var tether_b: WfTether = null

func _after_field(state: PhysicsDirectBodyState3D, a: Vector3) -> void:
	super(state, a)
	for t in [tether, tether_b]:
		if t == null:
			continue
		if grip == null:
			var r := (t as WfTether).constrain(state.transform.origin, state.linear_velocity, state.step, mass)
			if r[0] != state.transform.origin:
				var tf := state.transform
				tf.origin = r[0]
				state.transform = tf
			state.linear_velocity = r[1]
		else:
			(t as WfTether).constrain(state.transform.origin, Vector3.ZERO, state.step, mass)    # state only: a gripped body is held by the hand
