class_name WfFractalShield
## Fractal shielding on the Brow's ram faces (manifest look.exterior.grammar.fractal_shield; reference src/wayfarer/fractal_shield.py):
## hexagonal facing plates with Sierpinski-subdivided triangles, drawn by shaders/fractal_shield.gdshaderinc. `apply` puts it on a model's
## exported ram materials, keeping each material's own colour, roughness and alpha, for scenes that show the exported finishes (the walk);
## the flight timeline's grammar look binds it through p4_exterior. Presentation only: no geometry, collider or spacecraft fact changes.

const OPAQUE := preload("res://shaders/fractal_shield.gdshader")
const BLENDED := preload("res://shaders/fractal_shield_alpha.gdshader")

## Sets the pattern's uniforms on a material; overrides (the ram face with its wear values) replace the per-plate jitter and repairs.
static func bind(material: ShaderMaterial, block: Dictionary, overrides: Dictionary = {}) -> void:
	var u: Dictionary = block.get("uniforms", {})
	for key in u:
		material.set_shader_parameter(key, int(u[key]) if key == "fs_depth" else float(u[key]))
	for pair in [["fs_jitter", "jitter"], ["fs_repair_share", "repair_share"], ["fs_repair_value", "repair_value"]]:
		if overrides.has(pair[1]):
			material.set_shader_parameter(pair[0], float(overrides[pair[1]]))

## Replaces the ram materials (Runtime_WF_MAT_<name>_<index>) of every mesh under model; returns the number of surfaces bound.
static func apply(model: Node, block: Dictionary) -> int:
	if block.get("pattern", "") != "fractal_hex":
		return 0
	var names: Array = block.get("materials", [])
	var made := {}
	var count := 0
	for item in model.find_children("*", "MeshInstance3D", true, false):
		var mesh := item as MeshInstance3D
		for index in mesh.mesh.get_surface_count():
			var source := mesh.get_active_material(index) as StandardMaterial3D
			if source == null or not names.has(material_name(source)):
				continue
			if not made.has(source):
				made[source] = shield_material(source, block)
			mesh.set_surface_override_material(index, made[source])
			count += 1
	return count

static func shield_material(source: StandardMaterial3D, block: Dictionary) -> ShaderMaterial:
	var m := ShaderMaterial.new()
	var blended := source.transparency != BaseMaterial3D.TRANSPARENCY_DISABLED and source.albedo_color.a < 1.0
	m.shader = BLENDED if blended else OPAQUE
	m.resource_name = source.resource_name + "_fractal"
	m.set_shader_parameter("albedo", source.albedo_color)
	m.set_shader_parameter("rough", source.roughness)
	m.set_shader_parameter("metal", source.metallic)
	m.set_shader_parameter("x_min", float(block.get("x_min_m", 100.0)))
	m.set_shader_parameter("nx_min", float(block.get("normal_x_min", 0.5)))
	bind(m, block)
	return m

## The generated material name of an exported material: Runtime_WF_MAT_<name>_<index> -> <name>.
static func material_name(material: Material) -> String:
	var name := material.resource_name.trim_prefix("Runtime_WF_MAT_")
	var cut := name.rfind("_")
	return name.substr(0, cut) if cut > 0 and name.substr(cut + 1).is_valid_int() else name
