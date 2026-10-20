class_name WfFrameField
extends RefCounted
## Apparent acceleration of a free body in the SHIP or a RING zone (S&E 46 DYN-001..008, Technology 54 GEN-001/003), from the rig's
## `dynamics` block only (contract 27). SHIP: a = -a_ship. RING: -w x (w x r) - 2 w x v - alpha x r - a_ship, r from the ring centre on
## the axis; the geometry is static in that frame, so nothing else moves with the ring. a_ship is the mode's demonstration bound along +X
## (SIMULATION_ONLY: the actual thrust history is an open sheet channel).

var dyn: Dictionary
var zone := "SHIP"
var mode := "COAST"
var alpha := PackedFloat64Array([0.0, 0.0, 0.0])    # Euler term, rad/s2 about the spin axis (Godot axes); zero while the rings are not ramping
var w := PackedFloat64Array([0.0, 0.0, 0.0])
var a_ship := PackedFloat64Array([0.0, 0.0, 0.0])

func _init(d: Dictionary, z := "SHIP", m := "COAST") -> void:
	dyn = d
	set_state(z, m)

func set_state(z: String, m: String) -> void:
	zone = z
	mode = m
	var k := WfFrames.ring_index(z)
	w = WfFrames.ring_omega(dyn, k, m) if k >= 0 else WfFrames.v3(0.0, 0.0, 0.0)
	a_ship = WfFrames.v3(dyn["modes"][m]["demo_ship_accel_g"] * dyn["standard_gravity_m_s2"], 0.0, 0.0)

func ring_zone() -> bool:
	return WfFrames.ring_index(zone) >= 0

## Double-precision field at r (from the frame origin) moving at v in this frame.
func eval(r, v) -> PackedFloat64Array:
	var a := WfFrames.mul(a_ship, -1.0)
	if ring_zone():
		a = WfFrames.sub(a, WfFrames.cross(w, WfFrames.cross(w, r)))
		a = WfFrames.sub(a, WfFrames.mul(WfFrames.cross(w, v), 2.0))
		a = WfFrames.sub(a, WfFrames.cross(alpha, r))
	return a

func accel(pos: Vector3, vel: Vector3) -> Vector3:
	return WfFrames.to_vec(eval(WfFrames.from_vec(pos), WfFrames.from_vec(vel)))

func g_of(a) -> float:
	return sqrt(a[0] * a[0] + a[1] * a[1] + a[2] * a[2]) / dyn["standard_gravity_m_s2"]

## Fixture zone/mode (rig fixtures carry `ring` + `config`, or `zone` + `config`).
static func for_fixture(d: Dictionary, f: Dictionary) -> WfFrameField:
	var z := "SHIP"
	if f.has("ring"):
		z = "RING_A" if int(f["ring"]) == 0 else "RING_B"
	var ff := WfFrameField.new(d, z, f["config"])
	if f.has("alpha"):
		ff.alpha = WfFrames.b2g(f["alpha"])        # spin-down fixture: Euler term at t = 0 of the WORKING ramp (DYN-026)
	return ff
