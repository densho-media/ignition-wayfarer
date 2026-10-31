class_name WfLearning
extends RefCounted
## UJ-013 learning stations in the walk: at a station, Use steps through WHAT, WHY and SHOW ME, framed by the GU instructor, then closes;
## walking away closes it too (every step is optional). The stations, their texts and every number come from the package
## (`wf_learning.json`, `src/wayfarer/learning_stations.py`); Godot only finds each station's exported node and follows it as its ring turns.

const STEPS := ["WHAT", "WHY", "SHOW ME"]

var doc := {}
var stations: Array = []          # {rec, mesh}
var open := -1                    # index of the open station, -1 none
var step := 0                     # 0 WHAT, 1 WHY, 2 SHOW ME
var done := {}                    # station id -> true once its SHOW ME was seen
var panel := PanelContainer.new()
var text := RichTextLabel.new()
var map := Control.new()           # UJ-010's schematic Space Navigator map, drawn under the text while that SHOW ME is open
var map_doc := {}
var host: Node = null

func _init(by_name: Dictionary, layer: CanvasLayer, owner: Node, manifest: Dictionary) -> void:
	host = owner
	if not FileAccess.file_exists("res://generated/wf_learning.json"):
		return
	doc = JSON.parse_string(FileAccess.get_file_as_string("res://generated/wf_learning.json"))
	var by_source := {}                 # the package names nodes by ID; the manifest maps each to its Blender source name
	for r in manifest.get("nodes", []):
		by_source[str(r.get("source_name", ""))] = str(r.get("node", ""))
	for rec in doc.get("stations", []):
		var mesh := _mesh(by_name.get(by_source.get(rec["node"], rec["node"])))
		if mesh == null:
			push_warning("learning station %s: node %s not in the package" % [rec["id"], rec["node"]])
			continue
		stations.append({"rec": rec, "mesh": mesh})
	var back := StyleBoxFlat.new()
	back.bg_color = Color(0.02, 0.04, 0.08, 0.86)
	back.border_color = Color(0.30, 0.45, 0.75)
	back.set_border_width_all(2)
	back.set_content_margin_all(14.0)
	panel.add_theme_stylebox_override("panel", back)
	panel.mouse_filter = Control.MOUSE_FILTER_IGNORE
	text.bbcode_enabled = true
	text.fit_content = true
	text.scroll_active = false
	text.mouse_filter = Control.MOUSE_FILTER_IGNORE
	text.custom_minimum_size = Vector2(520, 0)
	text.add_theme_font_size_override("normal_font_size", 15)
	text.add_theme_font_size_override("bold_font_size", 16)
	var box := VBoxContainer.new()
	box.mouse_filter = Control.MOUSE_FILTER_IGNORE
	box.add_child(text)
	map.custom_minimum_size = Vector2(520, 230)
	map.mouse_filter = Control.MOUSE_FILTER_IGNORE
	map.visible = false
	map.draw.connect(_draw_map)
	box.add_child(map)
	panel.add_child(box)
	panel.visible = false
	layer.add_child(panel)

static func _mesh(n: Node) -> MeshInstance3D:
	if n == null:
		return null
	if n is MeshInstance3D:
		return n
	for c in n.get_children():
		var m := _mesh(c)
		if m != null:
			return m
	return null

func welcome() -> String:
	return str(doc.get("instructor", {}).get("welcome", ""))

## The station's centre at the index pose, the frame the walking body lives in: a ring's meshes ride its spinning pivot, so the pivot's
## current turn is taken out (otherwise the centre runs at rim speed between rendered frames and the open station falls out of reach).
func centre(i: int) -> Vector3:
	var m: MeshInstance3D = stations[i]["mesh"]
	var g := m.global_transform * m.get_aabb().get_center()
	var frames = host.get("frames") if host != null else null
	if frames is Dictionary:
		for id in frames:
			var f: Dictionary = frames[id]
			if id != "STATIONARY" and (f["node"] as Node).is_ancestor_of(m):
				var piv: Node3D = f["node"]
				return piv.get_parent().global_transform * (f["rest"] + piv.global_transform.affine_inverse() * g)
	return g

## The station in reach of p in the ring zone, -1 none. The open station stays in reach until the trainee is 1.5 reaches away (the
## same rule that closes it); otherwise the nearest station not yet learned wins, then the nearest learned one, so a bank of
## consoles side by side (OPS 1-3) offers its points in turn.
func in_reach(p: Vector3, zone: String) -> int:
	if open >= 0 and stations[open]["rec"]["ring"] == zone and p.distance_to(centre(open)) <= 1.5 * float(stations[open]["rec"]["reach_m"]):
		return open
	var best := -1
	var bd := INF
	for pass_ in 2:
		for i in stations.size():
			var rec: Dictionary = stations[i]["rec"]
			if rec["ring"] != zone or (pass_ == 0) == done.has(rec["id"]):
				continue
			var d := p.distance_to(centre(i))
			if d < float(rec["reach_m"]) and d < bd:
				best = i
				bd = d
		if best >= 0:
			return best
	return best

func title(i: int) -> String:
	return str(stations[i]["rec"]["title"])

## Use at station i: open at WHAT, then WHY, SHOW ME, close. Returns the step now shown ("" closed).
func advance(i: int) -> String:
	if open != i:
		open = i
		step = 0
	elif step < 2:
		step += 1
	else:
		close()
		return ""
	if step == 2:
		done[stations[i]["rec"]["id"]] = true
	_render()
	return STEPS[step]

func close() -> void:
	open = -1
	panel.visible = false
	if host != null:
		host.set("view_out", false)

## The remote camera of the open station's SHOW ME (ship frame, Blender axes: +X bow, +Z dorsal), {} when none is showing.
func remote_camera() -> Dictionary:
	if open < 0 or step != 2:
		return {}
	var sm: Dictionary = stations[open]["rec"]["show_me"]
	return sm.get("camera", {}) if str(sm["kind"]) == "remote" else {}

func showing_outside() -> bool:
	return open >= 0 and step == 2 and str(stations[open]["rec"]["show_me"]["kind"]) == "outside"

## Close when the trainee walks away from the open station.
func update(p: Vector3, zone: String, size: Vector2) -> void:
	if open < 0:
		return
	if in_reach(p, zone) != open:
		close()
		return
	panel.position = Vector2(size.x - panel.size.x - 18.0, clampf(size.y - panel.size.y - 18.0, 18.0, 262.0))     # a tall panel (the map) moves up

func next_label() -> String:
	return "close" if step == 2 else STEPS[step + 1]

func _render() -> void:
	var rec: Dictionary = stations[open]["rec"]
	var tabs := []
	for k in 3:
		tabs.append(("[b][color=#ffd27a]%s[/color][/b]" if k == step else "[color=#7f8fa8]%s[/color]") % STEPS[k])
	var out := ["[b]%s[/b]   %s" % [rec["title"], "  ".join(tabs)], "[i]GU instructor: %s[/i]" % rec["instructor"], ""]
	if step == 0:
		out.append_array(rec["what"])
		out.append("")
		out.append("[color=#9fb4d0]Objective: %s[/color]" % rec["objective"])
	elif step == 1:
		for l in rec["why"]:
			out.append("· " + str(l))
	else:
		var sm: Dictionary = rec["show_me"]
		if sm["kind"] == "remote":
			out.append(str(sm["text"]))
		elif sm["kind"] == "outside":
			out.append(str(sm["text"]))
			if host != null:
				host.set("view_out", true)
		else:
			out.append("[b]%s[/b]" % sm["title"])
			for l in sm["text"]:
				out.append("· " + str(l))
			out.append("[color=#9fb4d0]%s[/color]" % sm["note"])
	map_doc = rec["show_me"].get("map", {}) if step == 2 else {}
	map.visible = not map_doc.is_empty()
	map.queue_redraw()
	out.append("")
	out.append("[font_size=12][color=#8090a0]Sources: %s. Status: %s.[/color][/font_size]" % ["; ".join(rec["sources"]), rec["status"]])
	text.text = "\n".join(out)
	panel.visible = true
	panel.reset_size()

## The Sun at the left, orbits as arcs on the PRESENTATION transform (r = R sqrt(a / a_ref)), the planets on one layout ray (no epoch:
## SCHEMATIC), the Kuiper Belt band and the ship's course as an arrow, with the chart's notice and disclosure.
func _draw_map() -> void:
	if map_doc.is_empty():
		return
	var sz := map.size
	var o := Vector2(14.0, sz.y * 0.5)
	var R := sz.x - 40.0
	var aref := float(map_doc["a_ref_au"])
	var font := ThemeDB.fallback_font
	var r_of := func(a: float) -> float: return R * sqrt(a / aref)
	var half_h := sz.y * 0.5 - 30.0   # arcs stay between the notice and the course lines
	var span_of := func(r: float) -> float: return asin(minf(1.0, half_h / maxf(r, 1.0))) if r > half_h else 0.9
	var kb: Dictionary = map_doc["region"]
	var k0: float = r_of.call(float(kb["inner_au"]))
	var k1: float = r_of.call(float(kb["outer_au"]))
	for k in 12:
		var rk: float = lerp(k0, k1, (k + 0.5) / 12.0)
		map.draw_arc(o, rk, -span_of.call(rk), span_of.call(rk), 48, Color(0.55, 0.62, 0.78, 0.10), (k1 - k0) / 12.0)
	map.draw_string(font, o + Vector2(k0 + 4.0, -half_h + 12.0), str(kb["name"]), HORIZONTAL_ALIGNMENT_LEFT, -1, 11, Color(0.70, 0.76, 0.88))
	var lane := 0
	for b in map_doc["bodies"]:
		var r: float = r_of.call(float(b["a_au"]))
		map.draw_arc(o, r, -span_of.call(r), span_of.call(r), 48, Color(0.45, 0.55, 0.72, 0.65), 1.0)
		var p := o + Vector2(r, 0.0)
		map.draw_circle(p, float(b["glyph_px"]) * 0.5, Color(0.85, 0.88, 0.95))
		map.draw_string(font, p + Vector2(-14.0, 18.0 + 11.0 * (lane % 2)), str(b["name"]), HORIZONTAL_ALIGNMENT_LEFT, -1, 10, Color(0.75, 0.80, 0.90))
		lane += 1
	map.draw_circle(o, float(map_doc["sun_px"]) * 1.6, Color(1.0, 0.85, 0.45))
	var a0 := o + Vector2(R * 0.18, -half_h * 0.55)
	var a1 := o + Vector2(R + 22.0, -half_h * 0.80)
	map.draw_dashed_line(a0, a1, Color(1.0, 0.82, 0.48), 2.0, 8.0)
	var d := (a1 - a0).normalized()
	map.draw_colored_polygon(PackedVector2Array([a1 + d * 6.0, a1 - d * 8.0 + d.orthogonal() * 6.0, a1 - d * 8.0 - d.orthogonal() * 6.0]), Color(1.0, 0.82, 0.48))
	map.draw_string(font, Vector2(6.0, 14.0), str(map_doc["notice"]), HORIZONTAL_ALIGNMENT_LEFT, -1, 12, Color(1.0, 0.70, 0.45))
	map.draw_string(font, Vector2(6.0, sz.y - 22.0), str(map_doc["course"]), HORIZONTAL_ALIGNMENT_LEFT, sz.x - 12.0, 10, Color(1.0, 0.85, 0.60))
	map.draw_string(font, Vector2(6.0, sz.y - 8.0), str(map_doc["disclosure"]), HORIZONTAL_ALIGNMENT_LEFT, sz.x - 12.0, 10, Color(0.62, 0.68, 0.80))
