class_name WfHoloStyle
extends RefCounted
## WEB-003: the two hologram styles as a presentation toggle over an imported ship (Demonstrator 01; the M5 scene shares the shader).
##  subsystem  the M5 subsystem hologram (m5_holo.gd): unshaded, additive, rim and scan bands in each functional subsystem's overlay colour;
##  engine     the Blender engine exposition hologram (SH_ENGINE_HOLOGRAM, shot_tools.material): one colour, emission 1.6, alpha
##             0.12 + 0.55 facing. Godot draws no wire edges (the browser viewer does).
## The colours and the node classification come from generated/wf_holo.json (representation.py holo-style over the package manifest:
## shots/m5_subsystems.toml and the SH_ENGINE_HOLOGRAM colour). Instance material_override only: the imported materials, visibility,
## colliders, mechanisms and every spacecraft fact stay as they are; "standard" removes the overrides again.

const DATA := "res://generated/wf_holo.json"
const STYLES := ["standard", "subsystem", "engine"]
const NAMES := {"standard": "Standard", "subsystem": "Subsystem hologram", "engine": "Engine hologram"}
const SUBSYSTEM_SHADER := """
shader_type spatial;
render_mode unshaded, blend_add, depth_draw_never, cull_disabled, shadows_disabled;
uniform vec4 tint : source_color = vec4(1.0);
uniform float energy = 0.6;
uniform bool cut = false;
uniform float cut_y = 0.0;
uniform float flow = 0.0;
varying vec3 wpos;
void vertex() { wpos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz; }
void fragment() {
	if (cut && wpos.y > cut_y) { discard; }
	float rim = pow(1.0 - abs(dot(NORMAL, VIEW)), 2.0);
	float scan = 0.88 + 0.12 * step(0.5, fract(wpos.y * 1.5));
	float pulse = flow * 1.2 * pow(0.5 + 0.5 * sin(wpos.x * 0.22 + TIME * 3.0), 6.0);
	ALBEDO = tint.rgb * energy * (0.3 + 1.7 * rim) * scan * (1.0 + pulse);
}
"""
const ENGINE_SHADER := """
shader_type spatial;
render_mode unshaded, blend_mix, depth_draw_never, cull_disabled, shadows_disabled;
uniform vec4 tint : source_color = vec4(1.0);
void fragment() {
	float facing = 1.0 - abs(dot(NORMAL, VIEW));
	ALBEDO = tint.rgb * 1.6;
	ALPHA = clamp(0.12 + 0.55 * pow(facing, 1.5), 0.0, 1.0);
}
"""
const OVERVIEW_ENERGY := 0.16                     # m5_holo.gd: the whole ship stacks many layers, so the overview is dim
const BACKGROUND := Color(0.012, 0.02, 0.035)     # m5_holo.gd's background

var style := "standard"
var data := {}
var meshes: Array[MeshInstance3D] = []
var _materials := {}
var _environment: Environment
var _saved := {}                                   # the environment's standard look, restored on "standard"
var _shadows := {}                                 # mesh -> its own shadow setting

## The meshes of the WF_* nodes under root; false when the package carries no wf_holo.json (the toggle is then not offered).
func setup(root: Node, environment: Environment) -> bool:
	if not FileAccess.file_exists(DATA):
		return false
	data = JSON.parse_string(FileAccess.get_file_as_string(DATA))
	_environment = environment
	for item in root.find_children("WF_*", "MeshInstance3D", true, false):
		meshes.append(item)
		_shadows[item] = item.cast_shadow
	return not meshes.is_empty()

func available() -> bool:
	return not meshes.is_empty()

func next_style() -> String:
	return STYLES[(STYLES.find(style) + 1) % STYLES.size()]

## The overlay colour and subsystem of one node: the wf_holo.json entry (an id, or [id, colour] for its own colour), else context.
func class_of(id: String) -> Array:
	var entry = data.get("nodes", {}).get(id, "CTX")
	var sid: String = entry[0] if entry is Array else str(entry)
	var c: Array = entry[1] if entry is Array else []
	if c.is_empty():
		for s in data.get("subsystems", []):
			if s.id == sid:
				c = s.color
	if c.is_empty():
		c = [0.3, 0.31, 0.33]
	return [sid, Color(c[0], c[1], c[2])]

func _material(c: Color) -> ShaderMaterial:
	var key := "%s|%s" % [style, c.to_html(false)]
	if not _materials.has(key):
		var m := ShaderMaterial.new()
		m.shader = Shader.new()
		m.shader.code = SUBSYSTEM_SHADER if style == "subsystem" else ENGINE_SHADER
		m.set_shader_parameter("tint", c)
		if style == "subsystem":
			m.set_shader_parameter("energy", OVERVIEW_ENERGY)
		_materials[key] = m
	return _materials[key]

func apply(name: String) -> void:
	if not available() or not name in STYLES:
		return
	style = name
	var engine: Array = data.get("engine_color", [0.3, 0.78, 1.0])
	for item in meshes:
		if not is_instance_valid(item):
			continue
		if style == "standard":
			item.material_override = null
		else:
			item.material_override = _material(Color(engine[0], engine[1], engine[2]) if style == "engine" else class_of(str(item.name).get_slice(".", 0))[1])
		item.cast_shadow = _shadows[item] if style == "standard" else GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	if _environment != null:
		if _saved.is_empty():
			_saved = {"bg": _environment.background_color, "glow": _environment.glow_enabled}
		_environment.background_color = _saved.bg if style == "standard" else BACKGROUND
		_environment.glow_enabled = _saved.glow if style == "standard" else true

## The legend line of the current style (display classification PROTOTYPE: colours explain function, never materials).
func legend() -> String:
	match style:
		"subsystem": return "SUBSYSTEM HOLOGRAM (PROTOTYPE display): overlay colour per functional subsystem (shots/m5_subsystems.toml), never a material."
		"engine": return "ENGINE HOLOGRAM (PROTOTYPE display): the engine exposition look in one colour, never a material."
	return ""
