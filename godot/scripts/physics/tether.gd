class_name WfTether
extends RefCounted
## EVA training tether (DYN-025 / EVA-065, 15 CREW-EVA-004; mirror of crew_dynamics.tether): SIMULATION_ONLY, physical loads OPEN.
## `length` is the 2.0 m PROTOTYPE training reach (eva_suit.toml route.tether_reach_m); stiffness, damping, load limiter, crew attachment
## and anchor strength are OPEN (rig `dynamics.tether.known = false`). Unilateral and inextensible: slack, or taut but moving inward, it
## does nothing; taut and moving outward it applies the impulse J = -m (v . n) n that cancels the outward speed (perfectly inelastic,
## PROTOTYPE), and -J goes to the anchor. Every impulse is logged with its step, so momentum is accounted (no silent velocity erase).
## The reaction force is the rigid-limit mean |J|/dt over the step: with stiffness OPEN it scales with the timestep, so it is a
## diagnostic, never a load. Unclipped means no restraint at all.

const SLACK := "SLACK"
const TAUT := "TAUT"
const UNCLIPPED := "UNCLIPPED"

var anchor := Vector3.ZERO
var anchor_id := ""
var length := 2.0
var clipped := true
var state := SLACK
var status := "PROTOTYPE 2.0 m training length; SIMULATION_ONLY; stiffness, damping and loads OPEN"
var impulse_sum := Vector3.ZERO      # N s on the body since the last clip (the anchor took -impulse_sum)
var impulse_abs := 0.0               # sum of |J|
var peak_impulse := 0.0              # largest single |J| (N s)
var peak_force := 0.0                # largest |J|/dt (N, rigid-limit diagnostic)
var peak_dt := 0.0                   # the step that produced it: |J|/dt scales with 1/dt (CALC-R06: a timestep artifact, not a rating)
var events := 0
var last := {}                       # the last impulse record

func _init(anchor_point := Vector3.ZERO, reach_m := 2.0, is_clipped := true, id := "") -> void:
	anchor = anchor_point
	length = reach_m
	clipped = is_clipped
	anchor_id = id
	state = SLACK if clipped else UNCLIPPED

func clip() -> void:
	clipped = true
	state = SLACK
	reset_log()

func unclip() -> void:
	clipped = false
	state = UNCLIPPED

func reset_log() -> void:
	impulse_sum = Vector3.ZERO
	impulse_abs = 0.0
	peak_impulse = 0.0
	peak_force = 0.0
	peak_dt = 0.0
	events = 0
	last = {}

## Pure limit: returns [position, velocity, taut, impulse on the body (N s)].
static func limit(p: Vector3, v: Vector3, anchor_p: Vector3, len: float, mass: float) -> Array:
	var d := p - anchor_p
	var dist := d.length()
	if dist <= len:
		return [p, v, false, Vector3.ZERO]
	var n := d / dist
	var out := v.dot(n)
	if out <= 0.0:
		return [anchor_p + n * len, v, true, Vector3.ZERO]
	var j := -n * out * mass
	return [anchor_p + n * len, v + j / mass, true, j]

## One step for a body of `mass`: the engine will move it to p + v*dt, so the limit is applied to that predicted point and the origin set
## so the body ends exactly on the sphere. Returns [origin, velocity]; the impulse is logged.
func constrain(p: Vector3, v: Vector3, dt: float, mass := 1.0) -> Array:
	if not clipped:
		state = UNCLIPPED
		return [p, v]
	var r := limit(p + v * dt, v, anchor, length, mass)
	state = TAUT if r[2] else (TAUT if p.distance_to(anchor) >= length - 1e-6 else SLACK)
	if not r[2]:
		return [p, v]
	var j: Vector3 = r[3]
	if j != Vector3.ZERO:
		var jm := j.length()
		impulse_sum += j
		impulse_abs += jm
		peak_impulse = maxf(peak_impulse, jm)
		if jm / dt > peak_force:
			peak_force = jm / dt
			peak_dt = dt
		events += 1
		last = {"impulse_n_s": [j.x, j.y, j.z], "impulse_mag_n_s": jm, "anchor_force_n": jm / dt, "dt_s": dt, "anchor_id": anchor_id}
	return [r[0] - r[1] * dt, r[1]]

func record() -> Dictionary:
	return {"length_m": length, "state": state, "anchor_id": anchor_id, "events": events, "impulse_sum_n_s": [impulse_sum.x, impulse_sum.y, impulse_sum.z],
		"impulse_abs_n_s": impulse_abs, "peak_impulse_n_s": peak_impulse, "peak_anchor_force_n": peak_force, "peak_dt_s": peak_dt,
		"status": "SIMULATION_ONLY; |J|/dt is a timestep artifact, not an anchor rating (CALC-R06, 45 I-18/I-19); flight stiffness, stroke and rating OPEN (45 I-27)"}

func label() -> String:
	var step := (" at dt 1/%d s" % roundi(1.0 / peak_dt)) if peak_dt > 0.0 else ""
	return "tether %s  L %.2f m  J %.1f N s  |J|/dt %.0f N%s: timestep artifact, not a rating (CALC-R06)  [%s]" % [state, length, impulse_abs, peak_force, step, status]
