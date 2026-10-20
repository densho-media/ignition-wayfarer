class_name WfM6Sim
extends Node3D
## M6 (owner 2026-10-19, S&E 15!A220 / 15!A227, 98!A121): the shared shape of the interactive hologram chapters (EYE / shield, habitat,
## radiators). A chapter sim reads its m6 block from generated/m5/wf_m5_holo.json, drives only presentation (exported display poses,
## rotor pivots, overlay colours, drawn lines) and answers next_state / event / response / loop keys. Every value it prints is the
## data's sourced, DERIVED or DIAGNOSTIC number with its status, a CAD readback measured here, or UNKNOWN.

var host: Node                      # m5_holo.gd
var m: Dictionary                   # the chapter's m6 block
var active := false
var note := ""                      # the last action's one-line result or refusal
var mesh := ImmediateMesh.new()
var draw := MeshInstance3D.new()
var line_mat := StandardMaterial3D.new()

func _init(h: Node, block: Dictionary) -> void:
	host = h
	m = block
	line_mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	line_mat.vertex_color_use_as_albedo = true
	line_mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	draw.mesh = mesh
	draw.material_override = line_mat
	draw.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF

func _ready() -> void:
	add_child(draw)
	draw.visible = false

func set_active(on: bool) -> void:
	active = on
	draw.visible = on

func _process(dt: float) -> void:
	if active:
		step(dt)
		redraw()

## Mission / presentation step; the headless checks call it directly.
func step(_dt: float) -> void:
	pass

func redraw() -> void:
	pass

func next_state() -> void:
	pass

func event() -> void:
	pass

func response() -> void:
	pass

func loop() -> void:
	pass

## A composed camera for the chapter: {focus, radius, yaw, pitch}; empty frames the subjects.
func frame_hint() -> Dictionary:
	return {}

## Overlay colour per node for the chapter's subjects: id -> [Color, role] (role: subject, hot, dim, flow).
func tints() -> Dictionary:
	return {}

func panel_lines() -> Array[String]:
	return []

## Key bar for the HUD: [[action, what]].
func controls() -> Array:
	return []

static func unknown(text: String) -> String:
	return "[color=#e0a040][b]UNKNOWN[/b][/color] " + text

func line(a: Vector3, b: Vector3, c: Color) -> void:
	mesh.surface_set_color(c)
	mesh.surface_add_vertex(a)
	mesh.surface_set_color(c)
	mesh.surface_add_vertex(b)
