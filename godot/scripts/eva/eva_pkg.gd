class_name WfEvaPkg
extends RefCounted
## EVA-OPS-001: the EVA Operations package (data/simulations/wf_eva_ops.json, written by src/wayfarer/eva_ops.py from the canonical EVA
## system). Godot holds no EVA facts of its own: masses, gas, tanks, nozzles, allocation tables, the Brow and the hazards are all read here.

const PATHS := ["res://generated/wf_eva_ops.json"]

static func load_package() -> Dictionary:
	var paths: Array = PATHS.duplicate()
	paths.append(ProjectSettings.globalize_path("res://").path_join("../data/simulations/wf_eva_ops.json"))   # development checkout
	for p in paths:
		if FileAccess.file_exists(p):
			var d = JSON.parse_string(FileAccess.get_file_as_string(p))
			if d is Dictionary and d.get("contract", "") == "wf_eva_ops v1":
				return d
	return {}

static func v(a) -> Vector3:
	return Vector3(float(a[0]), float(a[1]), float(a[2]))

## Rocket equation: delta-v left from `usable_kg` of gas on a body of `mass_kg` now (ve = Isp g0).
static func dv(mass_kg: float, usable_kg: float, ve: float) -> float:
	if usable_kg <= 0.0 or mass_kg <= usable_kg:
		return 0.0
	return ve * log(mass_kg / (mass_kg - usable_kg))
