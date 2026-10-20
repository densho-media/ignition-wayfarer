class_name WfTool
extends WfFreeBody
## A loose tool: PROTOTYPE 2 kg box (the rig has no tool mass), same field integrator as the crew body, continuous CD on.

const MASS_KG := 2.0                       # PROTOTYPE
const SIZE := Vector3(0.3, 0.08, 0.08)     # PROTOTYPE

func _init() -> void:
	setup_body(MASS_KG)
	var cs := CollisionShape3D.new()
	var bx := BoxShape3D.new()
	bx.size = SIZE
	cs.shape = bx
	add_child(cs)
	var mi := MeshInstance3D.new()
	var bm := BoxMesh.new()
	bm.size = SIZE
	mi.mesh = bm
	add_child(mi)
