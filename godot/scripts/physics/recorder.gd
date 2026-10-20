class_name WfRecorder
extends Node
## Fixed-step trace of the bodies, written as JSON under <repo>/runs/physics/<scenario>.json (SIMULATION_ONLY).

var scenario := "scenario"
var field: WfFrameField
var rig: Dictionary
var bodies := {}      # name -> RigidBody3D
var rows: Array = []
var grip_of: Callable = func(): return ""
var steps := 0
var scene := {}      # what Blender needs to rebuild the room (set by the lab)

func _physics_process(_dt: float) -> void:
	sample()

func sample() -> void:
	var row := {"t": steps / float(Engine.physics_ticks_per_second), "zone": field.zone, "mode": field.mode, "grip": grip_of.call(), "b": {}}
	for n in bodies:
		var b: RigidBody3D = bodies[n]
		if not is_instance_valid(b):
			continue
		var q := b.global_transform.basis.get_rotation_quaternion()
		row["b"][n] = {"p": _v(b.global_position), "q": [q.x, q.y, q.z, q.w], "v": _v(b.linear_velocity), "w": _v(b.angular_velocity)}
	rows.append(row)
	steps += 1

static func _v(v: Vector3) -> Array:
	return [v.x, v.y, v.z]

func text() -> String:
	return JSON.stringify(trace(), "", false)

func trace() -> Dictionary:
	return {"scenario": scenario, "status": "SIMULATION_ONLY", "source": {"spec_hash": rig.get("spec_hash", ""), "source_map_hash": rig.get("source_map_hash", ""),
		"contract_version": rig.get("contract_version", 0)}, "step_s": 1.0 / Engine.physics_ticks_per_second, "axes": "Godot metres (x, y, z) = (x, z, -y) of the ship axes; ring zones: ring-frame coordinates from the ring centre on the axis", "scene": scene, "rows": rows}

func save() -> String:
	var dir := ProjectSettings.globalize_path("res://").path_join("../runs/physics").simplify_path()
	DirAccess.make_dir_recursive_absolute(dir)
	var path := dir.path_join(scenario + ".json")
	var f := FileAccess.open(path, FileAccess.WRITE)
	if f:
		f.store_string(text())
	return path
