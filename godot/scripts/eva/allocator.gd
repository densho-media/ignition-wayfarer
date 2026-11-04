class_name WfAllocator
extends RefCounted
## Thruster allocation of one flight configuration (EVA-OPS-001). The package carries, per signed pure axis, the valve duty cycles that
## give a unit force or torque, computed with the canonical non-negative least squares (eva_system.nnls) on the built nozzle layout.
## A command wrench mixes those columns linearly; if any duty passes 1 the whole mix is scaled down (direction kept, authority limited).
## The body then receives the wrench the duties actually produce (wrench()), never the commanded one, so a saturated or failed valve
## shows up as real lost authority.

const AXES := ["Fx", "Fy", "Fz", "Tx", "Ty", "Tz"]
var key := ""
var thrust_n := 0.0
var names: Array = []
var pos: Array = []          # Vector3 per nozzle, body frame, from the configuration's mass centre
var dir: Array = []          # exhaust direction per nozzle (force on the body is -thrust * dir)
var cols := {}               # "+Fx" -> PackedFloat64Array duty per unit
var maxv := {}               # "+Fx" -> largest pure value (N or N m)
var failed := {}             # nozzle index -> true: valve failed closed (duty forced to 0)
var duties := PackedFloat64Array()

func _init(k: String, table: Dictionary, layout: Array, from_com := Vector3.ZERO) -> void:
	key = k
	thrust_n = float(table["thrust_n"])
	var by := {}
	for n in layout:
		by[n["name"]] = n
	for nm in table["nozzles"]:
		var n: Dictionary = by[nm]
		names.append(nm)
		pos.append(WfEvaPkg.v(n["p"]) - from_com)
		dir.append(WfEvaPkg.v(n["e"]).normalized())
	for ax in table["axes"]:
		var a: Dictionary = table["axes"][ax]
		cols[ax] = PackedFloat64Array(a["duty_per_unit"])
		maxv[ax] = float(a["max"]) if a["ok"] else 0.0
	duties.resize(names.size())

func count() -> int:
	return names.size()

## Mean translation gas efficiency of the configuration: net force over the sum of nozzle thrusts, averaged over the six signed
## force axes (canted nozzles waste part of every pulse). Delta-v planning divides by it: real gas buys ve x efficiency.
func gas_efficiency() -> float:
	var e := 0.0
	var n := 0
	for ax in ["+Fx", "-Fx", "+Fy", "-Fy", "+Fz", "-Fz"]:
		var s := 0.0
		for v in cols[ax]:
			s += v
		if s > 0.0:
			e += 1.0 / (s * thrust_n)
			n += 1
	return e / n if n > 0 else 1.0

## Largest pure force (N) or torque (N m) along a signed body axis, e.g. "+Fx".
func authority(ax: String) -> float:
	return maxv.get(ax, 0.0)

func force_limit(d: Vector3) -> Vector3:
	return Vector3(authority("+Fx" if d.x >= 0.0 else "-Fx"), authority("+Fy" if d.y >= 0.0 else "-Fy"), authority("+Fz" if d.z >= 0.0 else "-Fz"))

func torque_limit(d: Vector3) -> Vector3:
	return Vector3(authority("+Tx" if d.x >= 0.0 else "-Tx"), authority("+Ty" if d.y >= 0.0 else "-Ty"), authority("+Tz" if d.z >= 0.0 else "-Tz"))

## Duties for a body-frame force (N) and torque (N m). Returns the saturation scale applied (1 = delivered as asked).
func mix(f: Vector3, t: Vector3) -> float:
	for i in duties.size():
		duties[i] = 0.0
	var w := [f.x, f.y, f.z, t.x, t.y, t.z]
	for k in 6:
		var c: float = w[k]
		if absf(c) < 1e-9:
			continue
		var col: PackedFloat64Array = cols[("+" if c > 0.0 else "-") + AXES[k]]
		for i in duties.size():
			duties[i] += absf(c) * col[i]
	var peak := 0.0
	for i in duties.size():
		if failed.has(i):
			duties[i] = 0.0
		peak = maxf(peak, duties[i])
	var s := 1.0
	if peak > 1.0:
		s = 1.0 / peak
		for i in duties.size():
			duties[i] *= s
	return s

func scale(k: float) -> void:
	for i in duties.size():
		duties[i] *= k

func duty_sum() -> float:
	var s := 0.0
	for d in duties:
		s += d
	return s

## The force and torque (body frame, about the configuration's mass centre) that the current duties produce.
func wrench() -> Array:
	var f := Vector3.ZERO
	var t := Vector3.ZERO
	for i in duties.size():
		if duties[i] <= 0.0:
			continue
		var fi: Vector3 = -dir[i] * (thrust_n * duties[i])
		f += fi
		t += (pos[i] as Vector3).cross(fi)
	return [f, t]

## Gas the current duties burn in dt (kg): mdot = F / ve per open valve.
func gas(dt: float, ve: float) -> float:
	return duty_sum() * thrust_n / ve * dt
