class_name WfShipNavigator
extends Node
## WAYFARER Ship Navigator (SNAV-001; S&E 49_SHIP_NAVIGATOR NAV-001..029, PROTOTYPE): the in-world GU orientation instrument of Demonstrator 01.
## One registry (rig `navigator`, data/ship_navigator.toml) drives three levels in one map world:
##  L1 corner locator   the occupied module highlighted, the visitor's marker and facing, the route to the target, the next HOLD point;
##  L2 overview         the same map enlarged: orbit (left-drag), zoom (wheel), pan (shift-drag), click a module to isolate it, H hull cutaway, U isolate the next;
##  L3 systems card     WHAT / WHY / SHOW ME of a hotspot with its owner-range facts (unknown = OPEN, never 0).
## The map is a SubViewport with its own world: the loaded DOCKED GLB's meshes merged per frame and assembly (no second ship model), pivots
## that copy the playable ship's ring and drum transforms each update (rings shown stopped when they are stopped), the induction rail, and a
## marker placed in the frame the visitor is actually in (NAV-008/009). Routes come from WfNavRoute over the rig's own gates; the guidance
## mode (WfNavPolicy) changes hints only. Nothing here is a spacecraft fact; status words carry a glyph as well as a colour (NAV-019).
## Keys: M locator / overview / hidden · J guidance mode · , . target stop · I systems card (WHAT, WHY, SHOW ME, close) · H cutaway · U isolate.
## On the forward hotspot's SHOW ME page the forward defense explorer (forward_explorer.gd) takes X / Y / Z / K.
## On the drones hotspot's SHOW ME page the maintenance drone demo (drone_demo.gd) takes X / Y / Z / K, and C for the route overlay.

const UPDATE_HZ := 30.0             # IMPLEMENTATION: map re-render rate (the main view is not slowed by it)
const CORNER_SIZE := Vector2i(306, 150)
const CORNER_SPAN_M := 64.0         # PROTOTYPE display: the corner view's ortho height around the visitor
const VIEW_DIR := Vector3(0.62, 0.55, 0.56)   # PROTOTYPE display: three-quarter view direction (Godot axes: +X bow, +Y dorsal)
const RAIL_R := 0.22                # display radius of the rail and route tubes, metres in the map
const SIDE_W := 330.0               # boarding.gd's right column width

class Acc:
	var v := PackedVector3Array()
	var n := PackedVector3Array()
	var i := PackedInt32Array()

var host
var demo
var nav: Dictionary
var planner: WfNavRoute
var policy: WfNavPolicy
var mode_id := ""
var chosen := "habitat"             # ASSISTED / FREE target (the visitor's pick)
var level := 1                      # 0 hidden, 1 corner, 2 overview
var card_page := -1                 # -1 closed, 0 WHAT, 1 WHY, 2 SHOW ME
var hotspot: Dictionary            # the card's hotspot: the picked / isolated module's, else the visitor's module's
var hotspots := {}                  # module id -> hotspot (one per module)
var cutaway := false
var isolate := -1                   # module index isolated in the overview, -1 all
var pal := {}
var modules: Array = []

var layer := CanvasLayer.new()
var panel := PanelContainer.new()
var vbox := VBoxContainer.new()
var view_box := SubViewportContainer.new()
var vp := SubViewport.new()
var cam := Camera3D.new()
var map_root := Node3D.new()
var map_frames := {}                # frame id -> Node3D in the map world
var parts: Array = []               # {node, frame, group, mat}
var rail_root := {}                 # frame id -> Node3D holding the route overlay
var marker := Node3D.new()
var arrow := MeshInstance3D.new()
var target_mark := Label3D.new()
var block_mark := Label3D.new()
var opening_marks := {}             # opening id -> Label3D
var eva := {}                       # res://generated/wf_eva.json (the EVA scene's own export), for the remote view only
var eva_root := Node3D.new()        # overview overlay: training rail, EVA hatch, ring-sweep keep-out (NAV-014, NAV-TOUR-06)
var eva_hatch: Label3D = null
var hazard_marks := {}              # NO_ENTRY module id -> Label3D
var loc_label := Label.new()
var state_label := Label.new()
var route_label := Label.new()
var hint_label := Label.new()
var keys_label := Label.new()
var card := PanelContainer.new()
var card_label := Label.new()
var mats := {}
var plan := {}
var plan_key := ""
var tick := 0.0
var focus := Vector3.ZERO
var yaw := 1.15
var pitch := 0.42
var span := 260.0
var pan := Vector3.ZERO
var dragging := false
var press_at := Vector2.ZERO
var dragged := false
var setup_ms := 0.0
var ship_box := AABB()
var last := {}                      # the last tracked place: {ship, map, frame, module, sector}
var samples := {"err": 0.0, "n": 0, "switch": [], "jump": 0.0}
var explorer: WfForwardExplorer       # FWD-V2 forward defense explorer on the forward hotspot's SHOW ME page
var drones: WfDroneDemo              # DRONE-001 maintenance drone demo on the drones hotspot's SHOW ME page
var space: WfSpaceNavigator          # S&E 55 SPACE view of the same navigator (B switches); draws only while shown

func setup(h, d = null) -> void:
	var t0 := Time.get_ticks_usec()
	host = h
	demo = d
	nav = host.rig_all["navigator"]
	planner = WfNavRoute.new(host.rig_all)
	policy = WfNavPolicy.new(nav)
	mode_id = policy.default_id()
	modules = nav["modules"]
	for x in nav["hotspots"]:
		hotspots[x["module"]] = x
	hotspot = nav["hotspots"][0]
	for k in nav["palette"]:
		if k != "status":
			pal[k] = Color.html(str(nav["palette"][k]))
	_build_ui()
	_build_world()
	explorer = WfForwardExplorer.new(self)
	drones = WfDroneDemo.new(self)
	_build_silhouette()
	_build_marks()
	explorer.build()
	drones.build()
	_build_eva()
	update_now()
	for p in parts:
		var b: AABB = (p["node"] as MeshInstance3D).global_transform * (p["node"] as MeshInstance3D).get_aabb()
		ship_box = b if ship_box.size == Vector3.ZERO else ship_box.merge(b)
	space = WfSpaceNavigator.new()
	add_child(space)
	space.setup(self)
	if WfInput.compact():
		level = 0                                # MOB-001: a phone's view first; the Map button shows the locator
	setup_ms = (Time.get_ticks_usec() - t0) / 1000.0
	update_now()

func space_shown() -> bool:
	return space != null and space.active

# ---------------------------------------------------------------------------------------------------------------------------- UI

func _lab(l: Label, size: int, color: Color) -> Label:
	l.add_theme_font_size_override("font_size", size)
	l.add_theme_color_override("font_color", color)
	l.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	l.custom_minimum_size.x = CORNER_SIZE.x
	return l

func _build_ui() -> void:
	layer.layer = 6
	add_child(layer)
	var sb := StyleBoxFlat.new()
	sb.bg_color = Color(pal["base"], 0.86)
	sb.border_color = Color(pal["structure_faint"], 0.9)
	sb.set_border_width_all(1)
	sb.set_content_margin_all(6.0)
	panel.add_theme_stylebox_override("panel", sb)
	layer.add_child(panel)
	panel.add_child(vbox)
	var title := _lab(Label.new(), 12, pal["quiet"])
	title.text = "GU WAYFARER · NAVIGATOR · ▸ SHIP  space · PROTOTYPE"
	vbox.add_child(title)
	view_box.stretch = true
	view_box.focus_mode = Control.FOCUS_NONE        # a click on the map must never take the keyboard from the scene's own keys
	view_box.custom_minimum_size = Vector2(CORNER_SIZE)
	view_box.mouse_filter = Control.MOUSE_FILTER_IGNORE
	view_box.gui_input.connect(_map_input)
	vbox.add_child(view_box)
	vp.own_world_3d = true
	vp.size = CORNER_SIZE
	vp.msaa_3d = Viewport.MSAA_2X
	vp.render_target_update_mode = SubViewport.UPDATE_ONCE
	view_box.add_child(vp)
	for l in [loc_label, state_label, route_label, hint_label]:
		vbox.add_child(_lab(l, 13, pal["text"]))
	vbox.add_child(_lab(keys_label, 11, pal["quiet"]))
	keys_label.text = keys_text()
	WfInput.bindings_changed.connect(_on_bindings)
	var cs := StyleBoxFlat.new()
	cs.bg_color = Color(pal["base"], 0.92)
	cs.border_color = Color(pal["structure"], 0.8)
	cs.set_border_width_all(1)
	cs.set_content_margin_all(10.0)
	card.add_theme_stylebox_override("panel", cs)
	card.visible = false
	layer.add_child(card)
	card.add_child(_lab(card_label, 14, pal["text"]))
	card_label.custom_minimum_size.x = 520

func layout() -> void:
	var size: Vector2 = get_viewport().get_visible_rect().size
	if WfInput.compact():
		_layout_compact(size)
		return
	panel.visible = level > 0 and not space_shown()
	if level != 1:
		for c in host.stop_list.get_parent().get_children():
			if c is Button:
				c.visible = true
	if level == 2:
		var w := minf(size.x - 2.0 * 28.0 - SIDE_W - 16.0, 900.0)
		view_box.custom_minimum_size = Vector2(w, minf(size.y * 0.62, w * 0.62))
		for l in [loc_label, state_label, route_label, hint_label, keys_label]:
			l.custom_minimum_size.x = w
		panel.position = Vector2(28.0, size.y - panel.get_combined_minimum_size().y - 20.0)
		view_box.mouse_filter = Control.MOUSE_FILTER_STOP
	else:
		view_box.custom_minimum_size = Vector2(CORNER_SIZE)
		for l in [loc_label, state_label, route_label, hint_label, keys_label]:
			l.custom_minimum_size.x = CORNER_SIZE.x
		view_box.mouse_filter = Control.MOUSE_FILTER_IGNORE
		# Under the stop panel (boarding.gd's right column), never over it: the map view gives up height first.
		var side: Control = host.stop_list.get_parent().get_parent()
		for c in host.stop_list.get_parent().get_children():
			if c is Button:
				c.visible = false                       # the locator takes their place; M hides the map and brings them back
		var free_top := side.get_global_rect().end.y + 8.0 if side.visible else 20.0
		var over := free_top + panel.get_combined_minimum_size().y + 20.0 - size.y
		if over > 0.0:
			view_box.custom_minimum_size.y = maxf(CORNER_SIZE.y - over, 72.0)
		panel.size = Vector2.ZERO
		panel.position = Vector2(size.x - 24.0 - panel.get_combined_minimum_size().x, maxf(free_top, size.y - panel.get_combined_minimum_size().y - 20.0))
	panel.size = panel.get_combined_minimum_size()
	card.position = Vector2(28.0, size.y - card.get_combined_minimum_size().y - 20.0) if level != 2 else Vector2(28.0, 92.0)
	if (explorer != null and explorer.active()) or (drones != null and drones.active()):
		card.position = Vector2(size.x - card.get_combined_minimum_size().x - 24.0, 20.0)   # beside the map, over the stop column, never over the view
	card.size = card.get_combined_minimum_size()   # vp follows view_box itself (stretch)
	if space_shown():
		card.visible = false
	else:
		card.visible = card_page >= 0

## MOB-001 phone / tablet: the corner locator small under the touch utility row (top right), the overview top left (a finger on it
## stays the map's: drag turns, tap picks), the systems card in place of the chapter text; the key line is left out (Map and Systems
## are touch buttons). The map starts hidden: Map shows it.
func _layout_compact(size: Vector2) -> void:
	var safe: Array = WfInput.touch.safe
	var top := float(safe[1]) + 76.0
	if size.x < 640.0 and demo != null:
		top = demo.hud.position.y + (demo.hud.size.y + 8.0 if demo.hud.visible else 0.0)    # upright: under the chapter text
	panel.visible = level > 0 and not space_shown()
	keys_label.visible = false
	hint_label.visible = level == 2
	route_label.visible = level == 2
	if level == 2:
		var w := minf(size.x * 0.58, 640.0)
		view_box.custom_minimum_size = Vector2(w, minf(size.y * 0.5, w * 0.62))
		for l in [loc_label, state_label, route_label, hint_label]:
			l.custom_minimum_size.x = w
		view_box.mouse_filter = Control.MOUSE_FILTER_STOP
		panel.size = Vector2.ZERO
		panel.position = Vector2(float(safe[0]) + 12.0, float(safe[1]) + 12.0)
	else:
		view_box.custom_minimum_size = Vector2(220, 104)
		for l in [loc_label, state_label]:
			l.custom_minimum_size.x = 220
		view_box.mouse_filter = Control.MOUSE_FILTER_IGNORE
		panel.size = Vector2.ZERO
		panel.position = Vector2(size.x - float(safe[2]) - 12.0 - panel.get_combined_minimum_size().x, top)
	panel.size = panel.get_combined_minimum_size()
	var cw := clampf(size.x * 0.56 - float(safe[0]), 240.0, 520.0) if size.x >= 640.0 else size.x - float(safe[0]) - float(safe[2]) - 48.0
	card_label.custom_minimum_size.x = cw
	card.size = Vector2.ZERO
	card.size = card.get_combined_minimum_size()
	# under the page's Exit and Full screen buttons (shell, top left), where the chapter text it replaces sits
	card.position = Vector2(float(safe[0]) + 12.0, float(safe[1]) + 62.0) if level != 2 else Vector2(size.x - float(safe[2]) - 12.0 - card.size.x, top)
	card.visible = card_page >= 0 and not space_shown()

# ------------------------------------------------------------------------------------------------------------------------- world

func _mat(color: Color, fill: float, rim: float, on_top := false) -> ShaderMaterial:
	var key := "%s|%s|%s|%s" % [color.to_html(), fill, rim, on_top]
	if mats.has(key):
		return mats[key]
	var sh := Shader.new()
	sh.code = """shader_type spatial;
render_mode unshaded, blend_mix, cull_disabled, depth_draw_never, shadows_disabled%s;
uniform vec4 tint : source_color;
uniform float fill;
uniform float rim;
void fragment() {
	float f = 1.0 - abs(dot(normalize(NORMAL), normalize(VIEW)));
	ALBEDO = tint.rgb;
	ALPHA = clamp(fill + rim * f * f, 0.0, 1.0) * tint.a;
}
""" % (", depth_test_disabled" if on_top else "")
	var m := ShaderMaterial.new()
	m.shader = sh
	m.set_shader_parameter("tint", color)
	m.set_shader_parameter("fill", fill)
	m.set_shader_parameter("rim", rim)
	if on_top:
		m.render_priority = 10
	mats[key] = m
	return m

func _flat(color: Color) -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	m.albedo_color = color
	m.no_depth_test = true
	m.render_priority = 20
	m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA if color.a < 1.0 else BaseMaterial3D.TRANSPARENCY_DISABLED
	return m

func _build_world() -> void:
	vp.add_child(map_root)
	var env := WorldEnvironment.new()
	env.environment = Environment.new()
	env.environment.background_mode = Environment.BG_COLOR
	env.environment.background_color = pal["base"]
	vp.add_child(env)
	cam.projection = Camera3D.PROJECTION_ORTHOGONAL
	cam.near = 1.0
	cam.far = 2000.0
	cam.current = true
	vp.add_child(cam)
	map_frames["STATIONARY"] = map_root
	for id in host.frames:
		if id == "STATIONARY":
			continue
		var n := Node3D.new()
		n.name = id
		map_root.add_child(n)
		map_frames[id] = n
	for id in map_frames:
		var r := Node3D.new()
		r.name = "route"
		map_frames[id].add_child(r)
		rail_root[id] = r

func _record(n: Node, rec: Dictionary) -> Dictionary:
	var p := n
	while p != null and p != host.ship:
		if rec.has(str(p.name)):
			return rec[str(p.name)]
		p = p.get_parent()
	return {}

func _frame_id(n: Node, frame_nodes: Dictionary) -> String:
	var p := n
	while p != null:
		if frame_nodes.has(p):
			return frame_nodes[p]
		p = p.get_parent()
	return "STATIONARY"

## The silhouette: the GLB's meshes of the registry's assemblies above the size floor (plus the passages), merged per frame and assembly.
func _build_silhouette() -> void:
	var sil: Dictionary = nav["silhouette"]
	var rec := {}
	for r in host.manifest.nodes:
		rec[str(r.node)] = r
	var frame_nodes := {}
	for id in host.frames:
		frame_nodes[host.frames[id].node] = id
	var acc := {}
	for node in host.ship.find_children("*", "MeshInstance3D", true, false):
		var mi: MeshInstance3D = node
		if mi.mesh == null:
			continue
		var r := _record(mi, rec)
		if r.is_empty() or r.get("lineage", []).is_empty():
			continue
		var group := str(r["lineage"][0])
		if not group in sil["groups"]:
			continue
		var gx := mi.global_transform
		if explorer.ready() and explorer.wants(r):
			# A Crown or eyelid mesh keeps its own node (no size floor, never merged) so the explorer can pose its baked state.
			var fe := _frame_id(mi, frame_nodes)
			var own := MeshInstance3D.new()
			own.mesh = mi.mesh
			own.name = str(r["node"])
			own.transform = (host.frames[fe].node as Node3D).global_transform.affine_inverse() * gx
			map_frames[fe].add_child(own)
			parts.append({"node": own, "frame": fe, "group": group, "tris": 0})
			explorer.add_part(own, str(r["node"]))
			continue
		var size := (gx.basis * mi.get_aabb().size).abs()
		if maxf(size.x, maxf(size.y, size.z)) < float(sil["min_extent_m"]) and not str(r.get("kind", "")) in sil["always_kinds"]:
			continue
		var f := _frame_id(mi, frame_nodes)
		var local: Transform3D = (host.frames[f].node as Node3D).global_transform.affine_inverse() * gx
		var key := f + "|" + group
		if not acc.has(key):
			acc[key] = Acc.new()
		var a: Acc = acc[key]
		var nb := Transform3D(local.basis, Vector3.ZERO)
		for s in mi.mesh.get_surface_count():
			var arr := mi.mesh.surface_get_arrays(s)
			var verts: PackedVector3Array = arr[Mesh.ARRAY_VERTEX]
			var base := a.v.size()
			a.v.append_array(local * verts)
			var norms = arr[Mesh.ARRAY_NORMAL]
			if norms is PackedVector3Array and norms.size() == verts.size():
				a.n.append_array(nb * norms)
			else:
				var z := PackedVector3Array()
				z.resize(verts.size())
				a.n.append_array(z)
			var idx = arr[Mesh.ARRAY_INDEX]
			if idx is PackedInt32Array and not idx.is_empty():
				var off := PackedInt32Array(idx)
				for k in off.size():
					off[k] += base
				a.i.append_array(off)
			else:
				for k in verts.size():
					a.i.append(base + k)
	for key in acc:
		var a: Acc = acc[key]
		var arrays := []
		arrays.resize(Mesh.ARRAY_MAX)
		arrays[Mesh.ARRAY_VERTEX] = a.v
		arrays[Mesh.ARRAY_NORMAL] = a.n
		arrays[Mesh.ARRAY_INDEX] = a.i
		var mesh := ArrayMesh.new()
		mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)
		var mi := MeshInstance3D.new()
		mi.mesh = mesh
		mi.name = key
		var parts_key: Array = key.split("|")
		map_frames[parts_key[0]].add_child(mi)
		parts.append({"node": mi, "frame": parts_key[0], "group": parts_key[1], "tris": a.i.size() / 3})

func _tube(points: PackedVector3Array, radius: float) -> ArrayMesh:
	# A thin square tube along a polyline (legible at any zoom, unlike 1 px lines).
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	for k in range(1, points.size()):
		var a := points[k - 1]
		var b := points[k]
		var d := b - a
		if d.length() < 1e-4:
			continue
		var u := d.normalized().cross(Vector3.UP if absf(d.normalized().dot(Vector3.UP)) < 0.9 else Vector3.RIGHT).normalized() * radius
		var w := d.normalized().cross(u).normalized() * radius
		var ring := [u + w, u - w, -u - w, -u + w]
		for j in 4:
			var p0: Vector3 = ring[j]
			var p1: Vector3 = ring[(j + 1) % 4]
			for v in [a + p0, b + p0, b + p1, a + p0, b + p1, a + p1]:
				st.set_normal((p0 + p1).normalized())
				st.add_vertex(v)
	return st.commit()

func _build_marks() -> void:
	var dot := MeshInstance3D.new()
	var sm := SphereMesh.new()
	sm.radius = 1.5
	sm.height = 3.0
	dot.mesh = sm
	dot.material_override = _flat(pal["player"])
	marker.add_child(dot)
	var cone := CylinderMesh.new()
	cone.top_radius = 0.0
	cone.bottom_radius = 1.3
	cone.height = 4.4
	arrow.mesh = cone
	arrow.material_override = _flat(pal["player"])
	map_root.add_child(arrow)
	for l in [target_mark, block_mark]:
		l.billboard = BaseMaterial3D.BILLBOARD_ENABLED
		l.no_depth_test = true
		l.fixed_size = true
		l.pixel_size = 0.0016
		l.font_size = 28
		l.outline_size = 6
		l.outline_modulate = pal["base"]
		l.render_priority = 30
		l.outline_render_priority = 29
		l.visible = false
	map_root.add_child(marker)
	map_root.add_child(target_mark)
	map_root.add_child(block_mark)
	target_mark.modulate = pal["go"]
	block_mark.modulate = pal["caution"]
	for o in nav["openings"]:
		var l := Label3D.new()
		l.billboard = BaseMaterial3D.BILLBOARD_ENABLED
		l.no_depth_test = true
		l.fixed_size = true
		l.pixel_size = 0.0014
		l.font_size = 24
		l.outline_size = 5
		l.outline_modulate = pal["base"]
		l.render_priority = 28
		l.outline_render_priority = 27
		l.visible = false
		map_root.add_child(l)
		opening_marks[o["id"]] = l

func _label(size: int, color: Color, priority := 26) -> Label3D:
	var l := Label3D.new()
	l.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	l.no_depth_test = true
	l.fixed_size = true
	l.pixel_size = 0.0014
	l.font_size = size
	l.outline_size = 5
	l.outline_modulate = pal["base"]
	l.render_priority = priority
	l.outline_render_priority = priority - 1
	l.modulate = color
	return l

## The EVA remote view (NAV-014, NAV-TOUR-06): what the EVA scene exports, drawn as a picture, never as a route. The training rail is a
## dashed SIMULATION_ONLY line, the hatch carries the FLIGHT_EVA state and its blocking hazards as exported, ring B's sweep is a keep-out.
## The exterior hazard modules get a RESTRICTED remote-view label. Nothing here is selectable as a target: no stop maps to an EVA node.
func _build_eva() -> void:
	map_root.add_child(eva_root)
	for m in modules:
		if m["access"] == "NO_ENTRY":
			var l := _label(22, pal["caution"])
			l.text = "%s · %s · remote view only" % [_status("RESTRICTED"), str(m["label"]).to_lower()]
			l.visible = false
			var pts := _module_points(m, 64)          # the module's outer edge (stationary: placed once)
			l.position = pts[0] if not pts.is_empty() else Vector3.ZERO
			map_root.add_child(l)
			hazard_marks[m["id"]] = l
	if not FileAccess.file_exists("res://generated/wf_eva.json"):
		return
	eva = JSON.parse_string(FileAccess.get_file_as_string("res://generated/wf_eva.json"))
	var anchors: Array = eva["anchors"].duplicate()
	anchors.sort_custom(func(a, b): return float(a["x"]) < float(b["x"]))
	var line := PackedVector3Array()
	for a in anchors:
		line.append(Vector3(a["p"][0], a["p"][1], a["p"][2]))
	var rail := MeshInstance3D.new()
	rail.mesh = _tube_pairs(_dashed(line, 0.9), 0.3)
	rail.material_override = _flat(Color(pal["quiet"], 0.95))
	eva_root.add_child(rail)
	var fl: Dictionary = eva["flight"]
	eva_hatch = _label(22, pal["caution"], 27)
	eva_hatch.text = "%s EVA airlock · %s %s\n%s training simulation only · blocking: %s" % [nav["statuses"]["HOLD"]["glyph"] if fl["state"] == "HOLD" else "",
		fl["mode"], fl["state"], nav["statuses"]["SIMULATION_ONLY"]["glyph"], ", ".join(fl["blocking"]).replace("_", " ")]
	eva_hatch.position = Vector3(eva["hatch"][0], eva["hatch"][1], eva["hatch"][2])
	eva_root.add_child(eva_hatch)
	var sw: Dictionary = eva["ring_sweep"]
	var keep := _label(22, pal["danger"])
	keep.text = "%s ring B sweep · keep out (rotating)" % nav["statuses"]["DANGER"]["glyph"]
	keep.position = Vector3((float(sw["x0"]) + float(sw["x1"])) / 2.0, float(sw["r_outer"]), 0.0)
	eva_root.add_child(keep)

# --------------------------------------------------------------------------------------------------------------------- tracking

func frame_of_zone(zone: String) -> String:
	return host.frame_of(zone)

## Where the visitor is: the physics body when it is shown, the review camera on the rail, or (exterior views) the visitor's rail place.
func tracked() -> Dictionary:
	var tour = host.body_tour
	var chapter := _chapter()
	if tour != null and tour.active and tour.body_vis.visible:
		var frame_nodes := {}
		for id in host.frames:
			frame_nodes[host.frames[id].node] = id
		var cam3 := get_viewport().get_camera_3d()
		return {"global": tour.body_vis.global_position, "forward": -cam3.global_basis.z if cam3 else Vector3.FORWARD,
			"frame": _frame_id(tour.body_vis, frame_nodes), "source": "body"}
	if chapter in ["EXTERIOR", "MODE"]:
		var seg: int = host.segment_at(host.progress)
		var f: String = frame_of_zone(host.zones[seg])
		var span_m := maxf(host.distances[seg] - host.distances[seg - 1], 1e-6)
		var p: Vector3 = host.points[seg - 1].lerp(host.points[seg], clampf((host.progress - host.distances[seg - 1]) / span_m, 0.0, 1.0))
		var fx: Transform3D = (host.frames[f].node as Node3D).global_transform
		return {"global": fx * (p - host.frames[f].rest), "forward": fx.basis * (host.points[seg] - host.points[seg - 1]).normalized(),
			"frame": f, "source": "rail_place"}
	return {"global": host.camera.global_position, "forward": -host.camera.global_basis.z, "frame": host.camera_frame, "source": "rail_camera"}

## The rail distance nearest a frame-local place, over the rail segments of that frame (the body's place on the induction line).
func rail_at(local: Vector3, frame: String) -> float:
	var rest: Vector3 = host.frames[frame].rest
	var best := float(host.progress)
	var d := INF
	for i in range(1, host.points.size()):
		if frame_of_zone(host.zones[i]) != frame:
			continue
		var a: Vector3 = host.points[i - 1] - rest
		var b: Vector3 = host.points[i] - rest
		var ab := b - a
		var u := clampf((local - a).dot(ab) / maxf(ab.length_squared(), 1e-9), 0.0, 1.0)
		var e := (a + ab * u).distance_to(local)
		if e < d:
			d = e
			best = lerpf(host.distances[i - 1], host.distances[i], u)
	return best

func _chapter() -> String:
	if demo != null and demo.chapter >= 0:
		return demo.CHAPTERS[demo.chapter]
	return ""

func module_of(frame: String, node: String) -> Dictionary:
	for m in modules:
		if m["frame"] == frame and (frame != "STATIONARY" or node in m["nav"]):
			if not m["zones"].is_empty():
				return m
	return modules[1]

## Ring A sector from the nearest induction room (ring frame, index pose), with its function.
func sector_of(local: Vector3, frame: String) -> Dictionary:
	var best := {}
	var d := INF
	var rest: Vector3 = host.frames[frame].rest
	for b in host.route.rooms.boxes:
		var c: Vector3 = host.vector(b.centre_m) - rest
		if c.distance_to(local) < d:
			d = c.distance_to(local)
			best = {"sector": int(b.sector), "function": str(b.function), "room": str(b.id), "d": d}
	return best

func ship_mode() -> String:
	return demo.ctl.mode if demo != null and demo.ctl != null else "DOCKED"

func state() -> Dictionary:
	var open := {}
	for o in host.openings:
		open[o.id] = host.opening_open(o)
	return {"mode": ship_mode(), "actor": "human_iva", "ring_mode": str(host.rings[host.ring_id].mode), "open": open}

func guidance() -> Dictionary:
	return policy.guidance(mode_id, _chapter(), chosen)

# ------------------------------------------------------------------------------------------------------------------------ update

func _process(delta: float) -> void:
	tick += delta
	if explorer != null:
		explorer.advance(delta)
	if drones != null:
		drones.advance(delta)
	if tick >= 1.0 / UPDATE_HZ:
		tick = 0.0
		update_now()

func update_now() -> void:
	var ship_inv: Transform3D = (host.ship as Node3D).global_transform.affine_inverse()
	for id in map_frames:
		if id != "STATIONARY":
			map_frames[id].transform = ship_inv * (host.frames[id].node as Node3D).global_transform
	var tr := tracked()
	var f: String = tr["frame"]
	var local: Vector3 = (host.frames[f].node as Node3D).global_transform.affine_inverse() * tr["global"]
	if marker.get_parent() != map_frames[f]:
		if marker.get_parent() != null:
			marker.get_parent().remove_child(marker)
		map_frames[f].add_child(marker)
	marker.position = local
	var at := float(host.progress) if tr["source"] != "body" else rail_at(local, f)
	var node := planner.node_at(at)
	var mod := module_of(f, node)
	var sec := sector_of(local, f) if f == host.ring_id else {}
	last = {"ship": ship_inv * tr["global"], "map": marker.global_position, "frame": f, "module": mod["id"], "sector": sec, "local": local,
		"source": tr["source"]}
	var fwd: Vector3 = ship_inv.basis * tr["forward"]
	if card_page < 0:
		hotspot = hotspots.get(_focus_module(mod["id"]), hotspot)
	var g := guidance()
	var st := state()
	var key := JSON.stringify([g["target"], g["show_route"], at, st])
	if key != plan_key:
		plan_key = key
		plan = planner.plan(at, g["target"], st) if g["target"] != "" else {}
		_draw_route(g)
	_place_marks(g, st)
	_highlight(mod)
	_camera(marker.global_position, fwd)
	_texts(tr, mod, sec, g, st)
	explorer.update()
	drones.update()
	if card_page >= 0:
		card_label.text = card_text()
	layout()
	if not space_shown():                            # SPACE-024: one map renders at a time; tracking above continues
		vp.render_target_update_mode = SubViewport.UPDATE_ONCE

func _camera(at: Vector3, fwd: Vector3) -> void:
	var scale := 1.0
	if level == 2:
		focus = pan + (ship_box.get_center() if isolate < 0 and card_page != 2 else _module_centre())
		var dir := Vector3(cos(pitch) * cos(yaw), sin(pitch), cos(pitch) * sin(yaw))
		cam.size = span
		cam.global_transform = Transform3D(Basis.looking_at(-dir, Vector3.UP), focus + dir * 600.0)
		scale = span / 120.0
	else:
		focus = at
		cam.size = CORNER_SPAN_M
		cam.global_transform = Transform3D(Basis.looking_at(-VIEW_DIR.normalized(), Vector3.UP), at + VIEW_DIR.normalized() * 600.0)
		scale = CORNER_SPAN_M / 120.0
	marker.scale = Vector3.ONE * scale
	if fwd.length() > 1e-6:
		var d := fwd.normalized()
		var up := Vector3.UP if absf(d.dot(Vector3.UP)) < 0.95 else Vector3.RIGHT
		arrow.global_transform = Transform3D(Basis.looking_at(d, up) * Basis(Vector3.RIGHT, -PI / 2.0), at + d * 3.4 * scale).scaled_local(Vector3.ONE * scale)

func _module_centre() -> Vector3:
	var m: Dictionary = modules[isolate] if isolate >= 0 else _module_by_id(hotspot["module"])
	if m["id"] == "WF.NAVMOD.EVA" and not eva.is_empty():
		return eva_hatch.global_position
	if m["id"] == "WF.NAVMOD.DRONES" and drones != null and drones.ready():
		return drones.root.global_transform * drones.track_point(drones.unit_x())
	return _centre_of(m, marker.global_position)

func _centre_of(m: Dictionary, fallback: Vector3) -> Vector3:
	var box := AABB()
	var first := true
	for p in parts:
		if p["frame"] == m["frame"] and p["group"] in m["groups"]:
			var b: AABB = p["node"].global_transform * (p["node"] as MeshInstance3D).get_aabb()
			box = b if first else box.merge(b)
			first = false
	return box.get_center() if not first else fallback

## The module the card follows: the one isolated (U) or picked in the overview, else the visitor's own.
func _focus_module(own: String) -> String:
	if level == 2 and isolate >= 0:
		return modules[isolate]["id"]
	return own

func _module_by_id(id: String) -> Dictionary:
	for m in modules:
		if m["id"] == id:
			return m
	return {}

func _highlight(mod: Dictionary) -> void:
	var show: Array = hotspot["show_modules"] if card_page == 2 else ([modules[isolate]["id"]] if isolate >= 0 and level == 2 else [])
	for p in parts:
		var mi: MeshInstance3D = p["node"]
		var hull: bool = p["group"] in ["Assembly_HULL", "Assembly_STRUCTURE", "Assembly_SHIELDING"]
		var in_mod: bool = p["frame"] == mod["frame"] and p["group"] in mod["groups"]
		var in_show := false
		for id in show:
			var m := _module_by_id(id)
			if p["frame"] == m["frame"] and p["group"] in m["groups"]:
				in_show = true
		# The EVA module has no mesh: its remote view keeps the stationary hull as faint context around the hatch.
		var context: bool = show == ["WF.NAVMOD.EVA"] and hull and p["frame"] == "STATIONARY"
		mi.visible = context or (not ((cutaway or card_page == 2) and level == 2 and hull and not in_show) and (show.is_empty() or in_show or not level == 2))
		if context:
			mi.material_override = _mat(pal["structure_faint"], 0.03, 0.45)
		elif in_show:
			mi.material_override = _mat(pal["structure"], 0.10, 0.85)
		elif in_mod:
			mi.material_override = _mat(pal["structure"], 0.07, 0.75)
		elif level == 2:
			mi.material_override = _mat(pal["structure"], 0.035, 0.55)
		else:
			mi.material_override = _mat(pal["structure_faint"], 0.03, 0.35)

## The route as tubes on the rail in each frame: GO solid, HOLD as a dashed amber tube; never GO past a closure that is not open.
func _draw_route(g: Dictionary) -> void:
	for id in rail_root:
		for c in rail_root[id].get_children():
			c.queue_free()
	if plan.is_empty() or not g["show_route"]:
		return
	var go: Array = plan["go_m"]
	if go[1] != go[0]:
		_rail_tubes(go[0], go[1], _flat(Color(pal["go"], 0.95)), 0.0)
	if not plan["hold_m"].is_empty():
		_rail_tubes(plan["hold_m"][0], plan["hold_m"][1], _flat(Color(pal["caution"], 0.9)), 1.2)

func _rail_tubes(a: float, b: float, mat: Material, dash: float) -> void:
	var lo := minf(a, b)
	var hi := maxf(a, b)
	var runs := {}
	var cur := ""
	var pts := PackedVector3Array()
	for i in range(1, host.points.size()):
		var d0: float = host.distances[i - 1]
		var d1: float = host.distances[i]
		if d1 < lo or d0 > hi or d1 - d0 < 1e-6:
			continue
		var f: String = frame_of_zone(host.zones[i])
		var rest: Vector3 = host.frames[f].rest
		var p0: Vector3 = host.points[i - 1].lerp(host.points[i], clampf((lo - d0) / (d1 - d0), 0.0, 1.0)) - rest
		var p1: Vector3 = host.points[i - 1].lerp(host.points[i], clampf((hi - d0) / (d1 - d0), 0.0, 1.0)) - rest
		if f != cur:
			if pts.size() > 1:
				runs[cur] = runs.get(cur, []) + [pts]
			pts = PackedVector3Array([p0])
			cur = f
		pts.append(p1)
	if pts.size() > 1:
		runs[cur] = runs.get(cur, []) + [pts]
	for f in runs:
		for line in runs[f]:
			var pl: PackedVector3Array = line
			if dash > 0.0:
				pl = _dashed(pl, dash)
			var mi := MeshInstance3D.new()
			mi.mesh = _tube(pl, RAIL_R) if dash <= 0.0 else _tube_pairs(pl, RAIL_R)
			mi.material_override = mat
			rail_root[f].add_child(mi)

func _dashed(pl: PackedVector3Array, dash: float) -> PackedVector3Array:
	# Pairs of points: every other dash-length piece of the polyline.
	var out := PackedVector3Array()
	var s := 0.0
	for k in range(1, pl.size()):
		var a := pl[k - 1]
		var b := pl[k]
		var len := a.distance_to(b)
		var u := 0.0
		while u < len:
			var e := minf(u + dash, len)
			if int(floor((s + u) / dash)) % 2 == 0:
				out.append(a.lerp(b, u / len))
				out.append(a.lerp(b, e / len))
			u = e
		s += len
	return out

func _tube_pairs(pairs: PackedVector3Array, radius: float) -> ArrayMesh:
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var k := 0
	while k + 1 < pairs.size():
		var one := _tube(PackedVector3Array([pairs[k], pairs[k + 1]]), radius)
		if one.get_surface_count() > 0:
			st.append_from(one, 0, Transform3D.IDENTITY)
		k += 2
	return st.commit()

func _rail_point(at: float) -> Array:
	var seg: int = host.segment_at(at)
	var f: String = frame_of_zone(host.zones[seg])
	var span_m := maxf(host.distances[seg] - host.distances[seg - 1], 1e-6)
	return [f, host.points[seg - 1].lerp(host.points[seg], clampf((at - host.distances[seg - 1]) / span_m, 0.0, 1.0)) - host.frames[f].rest]

func _put(l: Label3D, f: String, p: Vector3) -> void:
	if l.get_parent() != map_frames[f]:
		if l.get_parent() != null:
			l.get_parent().remove_child(l)
		map_frames[f].add_child(l)
	l.position = p

func _status(key: String) -> String:
	var s: Dictionary = nav["statuses"].get(key, nav["statuses"]["OPEN"])
	return "%s %s" % [s["glyph"], s["text"]]

func _place_marks(g: Dictionary, st: Dictionary) -> void:
	target_mark.visible = g["target"] != "" and not plan.is_empty()
	if target_mark.visible:
		var tp := _rail_point(float(plan.get("to_m", 0.0)))
		_put(target_mark, tp[0], tp[1])
		target_mark.text = "◆ " + str(planner.stops[g["target"]]["title"]).get_slice(":", 0)
	block_mark.visible = not plan.is_empty() and not plan["block"].is_empty() and g["show_route"]
	if block_mark.visible:
		var bp := _rail_point(float(plan["block"]["rail_m"]))
		_put(block_mark, bp[0], bp[1])
		block_mark.text = "‖ HOLD " + str(plan["block"]["kind"]).replace("_", " ").to_lower()
	var iso: String = modules[isolate]["id"] if isolate >= 0 else ""
	eva_root.visible = level == 2 and card_page != 2 and (iso == "" or iso == "WF.NAVMOD.EVA")
	for id in hazard_marks:
		var l: Label3D = hazard_marks[id]
		l.visible = level == 2 and (iso == "" or iso == id) and (card_page != 2 or hotspot["module"] == id)
	var show_all := level == 2 or card_page == 2
	for o in nav["openings"]:
		var l: Label3D = opening_marks[o["id"]]
		var wanted: bool = show_all and (card_page != 2 or o["kind"] in hotspot["show_openings"]) and o["leg"] == "WF.LEG.IND.A1"
		l.visible = wanted
		if wanted:
			var p := _rail_point(float(o["rail_m"]))
			_put(l, p[0], p[1])
			var v := float(st["open"].get(o["id"], 1.0))
			l.text = ("▶ " if v >= 0.999 else "‖ ") + str(o["kind"]).replace("_", " ").to_lower() + (" open" if v >= 0.999 else " closed")
			l.modulate = pal["go"] if v >= 0.999 else pal["caution"]

# ------------------------------------------------------------------------------------------------------------------------- texts

func _texts(tr: Dictionary, mod: Dictionary, sec: Dictionary, g: Dictionary, st: Dictionary) -> void:
	var where := ""
	match str(mod["id"]):
		"WF.NAVMOD.RING_A":
			var phase := rad_to_deg(float(host.frames[host.ring_id].angle))
			where = "RING A · sector %d %s · turning with the ring (phase %03.0f°)" % [sec.get("sector", 0), str(sec.get("function", "")).replace("_", " ").to_lower(), phase]
		"WF.NAVMOD.VESTIBULE_A":
			where = "RING A TRANSFER DRUM · drum %s" % str(host.drum_mode)
		_:
			where = str(mod["label"]).to_upper() + " · stationary" + ("" if level != 2 else " · " + str(mod.get("detail", "")))
	var who := "▶ YOU" if tr["source"] != "rail_place" else "○ VISITOR (exterior view)"
	if level != 2:
		where = where.replace("turning with the ring ", "")
	loc_label.text = "%s · %s" % [who, where]
	var dyn: Dictionary = host.rig_all["dynamics"]["modes"].get(st["mode"], {})
	var ring_state: String = demo.ctl.ring_state if demo != null and demo.ctl != null else str(dyn.get("habitat", ""))
	state_label.text = "Ship %s · rings %s" % [st["mode"], ring_state.replace("_", " ").to_lower()]
	var r := "%s · " % g["title"].to_upper()
	if g["target"] == "":
		r += "no target (%s to choose)" % WfInput.label("ship.target_next")
	elif plan.is_empty():
		r += "?"
	else:
		var title := str(planner.stops[g["target"]]["title"]).get_slice(":", 0)
		match str(plan["status"]):
			"GO": r += "▶ %s · route clear (%.0f m)" % [title, absf(plan["to_m"] - plan["from_m"])]
			"ARRIVED": r += "◆ at %s" % title
			"HOLD": r += "%s %s · %s" % [_status("HOLD"), title, plan["reason"] if level == 2 else plan["short"]]
			"RESTRICTED": r += "%s %s · %s" % [_status("RESTRICTED"), title, plan["reason"] if level == 2 else plan["short"]]
		if not g["show_route"]:
			r = r.get_slice(" · ", 0) + " · " + title + " (marker only)"
	route_label.text = r + ("  · PROTOTYPE route, SIMULATION ONLY" if not plan.is_empty() and g["show_route"] and level == 2 else ("  ◇ PROTOTYPE · SIM" if not plan.is_empty() else ""))
	var h := ""
	if g["hints"] and not plan.is_empty() and not plan["techniques"].is_empty():
		h = "Next: " + str(plan["techniques"][0]).replace("_", " ").to_lower()
	if (g["hints"] or level == 2) and (hotspot["module"] == _focus_module(mod["id"]) or mod["id"] in hotspot["show_modules"]):
		h += ("  ·  " if h != "" else "") + WfInput.label("ship.card") + ": " + hotspot["title"].to_lower()
		if panel.visible:
			WfInput.discover("inspect")              # ACI-09: a component worth inspecting is here: the INSPECT COMPONENT lesson
	if g["narration"] and g["target"] != "":
		h += ("\n" if h != "" else "") + "Instructor's stop: " + str(planner.stops[g["target"]]["title"])
	hint_label.text = h
	hint_label.visible = h != ""

func fact_text(f: Dictionary) -> String:
	var v := ""
	if not f["known"]:
		v = nav["statuses"]["OPEN"]["glyph"] + " OPEN" + ("" if f["items"].is_empty() else " (%s)" % ", ".join(f["items"]).replace("_", " "))
	elif f["value"] is float:
		v = ("%s %s" % [_num(f["value"]), f["unit"]]).strip_edges()
	else:
		v = str(f["value"])
		if v == v.to_upper() and not v.contains(" "):
			v = v.replace("_", " ").to_lower()   # an enum value (MIRRORED, DESPUN_TRANSFER_VESTIBULE); prose stays as written
	return "%s: %s  [%s · %s!%s]" % [f["label"], v, f["status"], f["sheet"], f["range"]]

## Display rounding only (the owner value stays in the rig): whole numbers plain, large values to the unit, small to three places.
static func _num(x: float) -> String:
	if is_equal_approx(x, roundf(x)):
		return str(int(roundf(x)))
	return "~" + String.num(x, 0) if absf(x) >= 1000.0 else String.num(x, 3)

func card_text() -> String:
	var h := hotspot
	var head := "%s · SYSTEMS EXPLORER · wording %s\n" % [h["title"].to_upper(), h["wording"]]
	match card_page:
		0:
			var s: String = head + "WHAT IS IT?  " + h["what"] + "\n"
			for f in h["facts"]:
				s += "  " + fact_text(f) + "\n"
			return s + WfInput.label("ship.card") + ": why"
		1: return head + "WHY THIS DESIGN?  " + h["why"] + "\n" + WfInput.label("ship.card") + ": show me"
		2: return head + "SHOW ME  " + h["show"] + (explorer.text() if explorer.active() else "") + (drones.text() if drones.active() else "") + "\n" + WfInput.label("ship.card") + ": close"
	return ""

# ------------------------------------------------------------------------------------------------------------------------- input

func _unhandled_input(e: InputEvent) -> void:
	# ACI-09: the ship-map keys are WfInput actions (ship.*, context nav); the forward explorer and drone demo still read raw keys
	# (WfInput.RESERVED["nav"]) and see them first, as before.
	if e.is_echo() or not e.is_pressed() or not (e is InputEventKey or e is InputEventJoypadButton or e is InputEventAction):
		return
	if space_shown():
		if e.is_action_pressed("ship.mode"):        # the guidance mode is shared by both views (SPACE-020)
			var ms := policy.ids()
			mode_id = ms[(ms.find(mode_id) + 1) % ms.size()]
			space.update_now()
			get_viewport().set_input_as_handled()
		return                                       # every other ship-map key waits until SHIP is back
	var xk := WfInput.key_of(e, ["explorer"])         # ACI-10: explorer.* actions (SHOW ME views), matched by their default keys
	if xk != KEY_NONE and (explorer.key(xk) or drones.key(xk)):
		get_viewport().set_input_as_handled()
		update_now()
		return
	if e.is_action_pressed("ship.map"):
		level = (level + 1) % 3 if level != 0 else 1
	elif e.is_action_pressed("ship.mode"):
		var ids := policy.ids()
		mode_id = ids[(ids.find(mode_id) + 1) % ids.size()]
	elif e.is_action_pressed("ship.target_next") or e.is_action_pressed("ship.target_prev"):
		var keys: Array = planner.stops.keys()
		var i := keys.find(chosen)
		chosen = keys[(i + (1 if e.is_action_pressed("ship.target_next") else keys.size() - 1)) % keys.size()]
	elif e.is_action_pressed("ship.card"):
		card_page = card_page + 1 if card_page < 2 else -1
		card.visible = card_page >= 0
		if card_page == 0:
			WfInput.performed("ship.card")
		if card_page == 2 and level != 2:
			level = 2
			span = 90.0
	elif e.is_action_pressed("ship.cutaway"):
		cutaway = not cutaway
	elif e.is_action_pressed("ship.isolate"):
		isolate = isolate + 1 if isolate < modules.size() - 1 else -1
	else:
		return
	get_viewport().set_input_as_handled()
	update_now()

func _on_bindings() -> void:
	keys_label.text = keys_text()
	update_now()

## ACI-09: the visitor's current inputs for the key line (WfInput labels; rebinds and the device in use show at once).
func keys_text() -> String:
	var k := func(id): return WfInput.label(id)
	return "%s map · %s mode · %s %s target · %s systems · %s space" % [k.call("ship.map"), k.call("ship.mode"), k.call("ship.target_prev"),
		k.call("ship.target_next"), k.call("ship.card"), k.call("ship.space")]

func _map_input(e: InputEvent) -> void:
	if level != 2:
		return
	if e is InputEventMouseButton:
		if e.button_index == MOUSE_BUTTON_WHEEL_UP and e.pressed:
			span = maxf(span * 0.85, 12.0)
		elif e.button_index == MOUSE_BUTTON_WHEEL_DOWN and e.pressed:
			span = minf(span * 1.18, 420.0)
		elif e.button_index == MOUSE_BUTTON_LEFT:
			dragging = e.pressed
			if e.pressed:
				press_at = e.position
				dragged = false
			elif not dragged and not explorer.click(e.position):
				select(pick(e.position))
	elif e is InputEventMouseMotion and dragging:
		dragged = dragged or e.position.distance_to(press_at) > 4.0
		if e.shift_pressed:
			pan -= cam.global_basis.x * e.relative.x * span / vp.size.y - cam.global_basis.y * e.relative.y * span / vp.size.y
		else:
			yaw += e.relative.x * 0.008
			pitch = clampf(pitch + e.relative.y * 0.008, -1.4, 1.4)
	view_box.accept_event()
	update_now()

## The module under a point of the map view (NAV-TOUR-03 Systems Explorer by selecting known modules): the nearest visible map triangle
## hit, preferring an inner module over the hull, structure and shielding it shows through. "" for empty space or unregistered parts.
func pick(at: Vector2) -> String:
	if eva_hatch != null and eva_root.is_visible_in_tree() and cam.unproject_position(eva_hatch.global_position).distance_to(at) < 14.0:
		return "WF.NAVMOD.EVA"                  # the EVA module has no map mesh of its own: its hatch mark stands for it
	var from := cam.project_ray_origin(at)
	var dir := cam.project_ray_normal(at)
	var best := ["", INF, ""]                 # [module id, distance, module id of a hull-like hit]
	var hull_d := INF
	for p in parts:
		var mi: MeshInstance3D = p["node"]
		if not mi.is_visible_in_tree():
			continue
		var m := _module_of_part(p)
		if m.is_empty():
			continue
		var inv := mi.global_transform.affine_inverse()
		var o := inv * from
		var d_local := (inv.basis * dir).normalized()
		if mi.get_aabb().grow(0.01).intersects_ray(o, d_local) == null:
			continue                            # the ray misses the mesh's box: no triangle data needed (built on the first box hit)
		if not p.has("tri"):
			p["tri"] = mi.mesh.generate_triangle_mesh()
		var hit: Dictionary = (p["tri"] as TriangleMesh).intersect_ray(o, d_local)
		if hit.is_empty():
			continue
		var d := (mi.global_transform * Vector3(hit["position"]) - from).length()
		if p["group"] in ["Assembly_HULL", "Assembly_STRUCTURE", "Assembly_SHIELDING"]:
			if d < hull_d:
				hull_d = d
				best[2] = m["id"]
		elif d < best[1]:
			best = [m["id"], d, best[2]]
	return best[0] if best[0] != "" else best[2]

func _module_of_part(p: Dictionary) -> Dictionary:
	for m in modules:
		if p["frame"] == m["frame"] and p["group"] in m["groups"]:
			return m
	return {}

## Select a module in the overview: isolate it and point the card at its hotspot ("" clears).
func select(id: String) -> void:
	isolate = -1
	for i in modules.size():
		if modules[i]["id"] == id:
			isolate = i
	if card_page >= 0:
		card_page = -1
		card.visible = false
	update_now()

# ------------------------------------------------------------------------------------------------------------------------ checks
# NAV-024 / SIM-037: run inside demo01's --check-demo (the runtime-export demo01 step). The marker is checked against the scene, the routes
# against the rig's own gates over a state sweep, the modes for parity, the card for unsourced numbers, and ring A over a full revolution.

func sample(chapter: String) -> void:
	var prev: Dictionary = last
	update_now()
	var truth: Vector3 = last["ship"]
	samples["err"] = maxf(samples["err"], (last["map"] - truth).length())
	samples["n"] += 1
	if not prev.is_empty() and prev.get("chapter", "") == chapter and prev["source"] == last["source"]:
		var d_map: Vector3 = last["map"] - prev["map"]
		var d_true: Vector3 = truth - prev["ship"]
		samples["jump"] = maxf(samples["jump"], (d_map - d_true).length())
		if prev["frame"] != last["frame"]:
			samples["switch"].append({"chapter": chapter, "from": prev["frame"], "to": last["frame"], "map_step_m": d_map.length(), "true_step_m": d_true.length()})
	last["chapter"] = chapter

func _crossed(at: float, to: float) -> Array:
	var dir := 1.0 if to > at else -1.0
	var out := planner.openings.filter(func(o): return (float(o["rail_m"]) - at) * dir > 1e-6 and (to - float(o["rail_m"])) * dir >= -1e-6)
	if dir < 0.0:
		out.reverse()
	return out

func _route_checks() -> Array:
	var ids := {}
	for o in planner.openings:
		ids[o["kind"] + ":" + o["id"].get_slice(".", 2)] = o["id"]
	var closed := {}
	for o in planner.openings:
		closed[o["id"]] = 0.0
	var s: Callable = func(k): return float(planner.stops[k]["rail_m"])
	var with: Callable = func(open_ids: Array) -> Dictionary:
		var d := closed.duplicate()
		for id in open_ids:
			d[id] = 1.0
		return d
	var gate: String = ids["PORT_GATE:A"]
	var door: String = ids["DRUM_DOOR_TUBE_HATCH:A1"]
	var leaf: String = ids["SECTOR_LEAF:A1"]
	var inner: String = ids["AIRLOCK_INNER:DOCK_PRIMARY"]
	var cases := [
		["docked_locked_closed", s.call("spine"), "habitat", {"mode": "DOCKED", "ring_mode": "STOPPED", "open": closed}, "HOLD", "PORT_GATE"],
		["ring_ramp_no_transfer", s.call("spine"), "habitat", {"mode": "COAST", "ring_mode": "SPIN_UP", "open": with.call([gate, door, leaf])}, "HOLD", ""],
		["coast_gate_closed", s.call("spine"), "habitat", {"mode": "COAST", "ring_mode": "RUNNING", "open": closed}, "HOLD", "PORT_GATE"],
		["coast_door_closed", s.call("spine"), "habitat", {"mode": "COAST", "ring_mode": "RUNNING", "open": with.call([gate])}, "HOLD", "DRUM_DOOR_TUBE_HATCH"],
		["coast_drum_to_ring_open", s.call("transfer"), "habitat", {"mode": "COAST", "ring_mode": "RUNNING", "open": with.call([door, leaf])}, "GO", ""],
		["coast_sector_hatch_closed", s.call("transfer"), "habitat", {"mode": "COAST", "ring_mode": "RUNNING", "open": with.call([door])}, "HOLD", "SECTOR_LEAF"],
		["coast_dock_restricted", s.call("spine"), "arrival", {"mode": "COAST", "ring_mode": "RUNNING", "open": with.call([inner])}, "RESTRICTED", ""],
		["docked_airlock_inner_open", s.call("spine"), "arrival", {"mode": "DOCKED", "ring_mode": "STOPPED", "open": with.call([inner])}, "GO", ""],
	]
	var bad := []
	for c in cases:
		var p := planner.plan(c[1], c[2], c[3])
		var kind: String = p["block"].get("kind", "")
		if p["status"] != c[4] or kind != c[5]:
			bad.append({"case": c[0], "status": p["status"], "block": kind, "expected": [c[4], c[5]], "reason": p["reason"]})
	# Off the rail: the exterior is never navigable (FLIGHT_EVA HOLD), ring B is topology only (not on the demonstrator route).
	var eva := [
		["eva_iva_restricted", planner.plan_node("TRUNK", "EVA_EXTERIOR", {"mode": "DOCKED", "actor": "human_iva"}), "RESTRICTED"],
		["eva_suited_coast_restricted", planner.plan_node("SP12", "EVA_EXTERIOR", {"mode": "COAST", "actor": "human_suited"}), "RESTRICTED"],
		["eva_suited_eva_hold", planner.plan_node("SP12", "EVA_EXTERIOR", {"mode": "EVA", "actor": "human_suited", "ring_mode": "RUNNING"}), "HOLD"],
		["ring_b_topology_only", planner.plan_node("TRUNK", "SECTOR_2_1", {"mode": "COAST", "ring_mode": "RUNNING"}), "TOPOLOGY_ONLY"],
	]
	for c in eva:
		if c[1]["status"] != c[2]:
			bad.append({"case": c[0], "status": c[1]["status"], "expected": c[2]})
	# Sweep: every stop pair x mode x ring state x 48 closure sets. GO never crosses a closure that is not open, HOLD stops at the first one,
	# a ramping ring never gives GO through the spine port, the dock never GO outside DOCKED.
	var rng := RandomNumberGenerator.new()
	rng.seed = 33
	var sweeps := 0
	var violations := []
	for k in 48:
		var open := {}
		for o in planner.openings:
			open[o["id"]] = 1.0 if rng.randf() < 0.6 else rng.randf_range(0.0, 0.99)
		for mode in ["DOCKED", "COAST"]:
			for ring in ["STOPPED", "SPIN_UP", "RUNNING"]:
				for a in planner.stops:
					for b in planner.stops:
						var st := {"mode": mode, "ring_mode": ring, "open": open}
						var p := planner.plan(s.call(a), b, st)
						sweeps += 1
						var crossed := _crossed(s.call(a), s.call(b))
						var shut := crossed.filter(func(o): return float(open[o["id"]]) < 0.999)
						var kinds := crossed.map(func(o): return o["kind"])
						if p["status"] == "GO" and (not shut.is_empty() or (ring == "SPIN_UP" and "PORT_GATE" in kinds) or (mode != "DOCKED" and "AIRLOCK_INNER" in kinds)):
							violations.append([a, b, mode, ring, "GO through " + str(shut.map(func(o): return o["id"]))])
						if p["status"] == "HOLD" and not p["block"].is_empty() and (shut.is_empty() or shut[0]["id"] != p["block"]["id"]):
							violations.append([a, b, mode, ring, "HOLD not at the first closure"])
	return [{"id": "nav_route_gated", "ok": bad.is_empty() and violations.is_empty(), "actual": {"cases": cases.size() + eva.size(), "bad": bad,
		"sweeps": sweeps, "violations": violations.slice(0, 5)},
		"note": "never GO past a closure that is not open, through the spine port while ring A ramps, to the dock outside DOCKED, or to the exterior (FLIGHT_EVA HOLD)"}]

func _parity_checks() -> Array:
	var bad := []
	var st := state()
	var keys := {}
	for chapter in WfNavPolicy.TOUR_TARGET:
		var t: String = WfNavPolicy.TOUR_TARGET[chapter]
		var results := {}
		for id in policy.ids():
			var g := policy.guidance(id, chapter, t)
			for k in g:
				keys[k] = true
			results[id] = JSON.stringify(planner.plan(float(host.progress), g["target"], st))
		var vals := results.values()
		if vals.any(func(v): return v != vals[0]):
			bad.append(chapter)
	var forbidden := keys.keys().filter(func(k): return k in ["open", "closed", "synced", "allow", "allowed", "unlock", "permission", "access", "ring_mode", "mode_state"])
	return [{"id": "nav_modes_parity", "ok": bad.is_empty() and forbidden.is_empty(), "actual": {"differ": bad, "guidance_keys": keys.keys(), "forbidden": forbidden},
		"note": "GUIDED / ASSISTED / FREE give the same route for the same target and state; a policy returns guidance keys only"}]

func _value_checks() -> Array:
	var out := []
	var saved_h := hotspot
	for h in nav["hotspots"]:
		hotspot = h
		out.append_array(_hotspot_checks())
	hotspot = saved_h
	var bad := []
	var facts := 0
	for r in out:
		bad.append_array(r[0])
		facts += r[1]
	for key in nav["statuses"]:
		if str(nav["statuses"][key]["glyph"]) == "" or str(nav["statuses"][key]["text"]) == "":
			bad.append(key + ": a status without glyph and text")
	return [{"id": "nav_no_fabricated_values", "ok": bad.is_empty(), "actual": bad, "hotspots": nav["hotspots"].size(), "facts": facts,
		"note": "every number on every card is an owner-range fact; unknown facts read OPEN; statuses carry a glyph and text"}]

func _hotspot_checks() -> Array:
	var bad := []
	var tag: String = hotspot["id"].get_slice(".", 2) + " "
	for k in ["what", "why", "show"]:
		if RegEx.create_from_string("[0-9]").search(str(hotspot[k])) != null:
			bad.append(tag + k + " has a number outside the sourced facts")
	for f in hotspot["facts"]:
		var line := fact_text(f)
		if f["known"]:
			if f["value"] == null or str(f["source_ref"]) == "" or str(f["range"]) == "":
				bad.append(tag + f["label"] + ": known without value or owner range")
		else:
			var shown := line.get_slice("  [", 0)
			if f["value"] != null or not shown.contains("OPEN") or RegEx.create_from_string("[0-9]").search(shown) != null:
				bad.append(tag + f["label"] + ": unknown not shown as OPEN")
	var saved := card_page
	card_page = 0
	var text := card_text()
	card_page = saved
	for f in hotspot["facts"]:
		if not text.contains(fact_text(f)):
			bad.append(tag + f["label"] + ": fact missing from the card")
	return [[bad, hotspot["facts"].size()]]

func _registry_checks() -> Array:
	var bad := []
	var ids := {}
	for m in modules + nav["hotspots"] + nav["modes"]:
		if ids.has(m["id"]):
			bad.append("duplicate " + m["id"])
		ids[m["id"]] = true
	for m in modules:
		if not host.frames.has(m["frame"]):
			bad.append(m["id"] + ": frame " + m["frame"] + " not in the scene")
		if not m["groups"].is_empty() and parts.filter(func(p): return p["frame"] == m["frame"] and p["group"] in m["groups"]).is_empty() and m["frame"] != "WF.ROTOR.2" and m["frame"] != "STATIONARY":
			bad.append(m["id"] + ": no map geometry in its frame")
	var nav_open := {}
	for o in nav["openings"]:
		nav_open[o["id"]] = true
	for o in host.openings:
		if not nav_open.has(o.id):
			bad.append(str(o.id) + ": a scene opening the registry does not know")
	if planner.rail_nodes.size() != host.points.size():
		bad.append("rail nodes %d != rail points %d (stale registry vs export)" % [planner.rail_nodes.size(), host.points.size()])
	for k in planner.stops:
		if not nav["stop_nodes"].has(k):
			bad.append("stop " + k + " without a nav node")
	var tris := 0
	for p in parts:
		tris += int(p["tris"])
	return [{"id": "nav_registry_bound", "ok": bad.is_empty() and not parts.is_empty(), "actual": bad, "map_meshes": parts.size(), "map_triangles": tris,
		"setup_ms": setup_ms, "rig_contract": host.rig_all["contract_version"], "navigator_version": nav["version"],
		"parts": parts.map(func(p): return "%s %d" % [p["node"].name, p["tris"]])}]

func _ring_radius(ship_p: Vector3) -> float:
	var c: Vector3 = (host.ship as Node3D).global_transform.affine_inverse() * (host.frames[host.ring_id].node as Node3D).global_position
	var d := ship_p - c
	var axis: Vector3 = host.frames[host.ring_id].axis
	return (d - axis * d.dot(axis)).length()

func _revolution() -> Dictionary:
	var ring: String = host.ring_id
	var w := float(host.frames[ring].rate) * float(host.rings[ring].f)
	update_now()
	if absf(w) < 1e-6 or last["frame"] != ring:
		return {"id": "nav_ring_full_revolution", "ok": false, "actual": {"w": w, "frame": last["frame"]}}
	var dt := 1.0 / 60.0
	var n := int(ceil(TAU / absf(w) / dt)) + 30
	var l0: Vector3 = last["local"]
	var actor: Node3D = host.body_tour.actor
	var off0: Vector3 = l0 - actor.global_position             # the body's physics world is ring A's frame (ring-centre coordinates)
	var frame_err := 0.0
	var s0: int = last["sector"].get("sector", -1)
	var r0 := _ring_radius(last["ship"])
	var prev_map: Vector3 = last["map"]
	var prev_a := float(host.frames[ring].angle)
	var swept := 0.0
	var wraps := 0
	var drift := 0.0
	var jump := 0.0
	var rerr := 0.0
	var same := true
	var pivot_err := 0.0
	for k in n:
		await get_tree().physics_frame
		update_now()
		var a := float(host.frames[ring].angle)
		swept += absf(host.wrap_angle(a - prev_a))
		if absf(a - prev_a) > PI:
			wraps += 1
		prev_a = a
		drift = maxf(drift, (last["local"] - l0).length())
		frame_err = maxf(frame_err, (last["local"] - actor.global_position - off0).length())
		jump = maxf(jump, (last["map"] - prev_map).length())
		prev_map = last["map"]
		rerr = maxf(rerr, absf(_ring_radius(last["ship"]) - r0))
		same = same and last["frame"] == ring and last["sector"].get("sector", -1) == s0
		var want: Transform3D = (host.ship as Node3D).global_transform.affine_inverse() * (host.frames[ring].node as Node3D).global_transform
		var got: Transform3D = map_frames[ring].transform
		pivot_err = maxf(pivot_err, (got.origin - want.origin).length() + (got.basis.y - want.basis.y).length() + (got.basis.z - want.basis.z).length())
	var step_limit := absf(w) * r0 * dt * 1.5 + 0.01
	var ok := same and swept >= TAU and wraps >= 1 and frame_err < 1e-3 and jump <= step_limit and pivot_err < 1e-4
	return {"id": "nav_ring_full_revolution", "ok": ok, "actual": {"swept_rad": swept, "phase_wraps": wraps, "marker_vs_physics_ring_frame_m": frame_err,
		"body_sway_m": drift, "sector": s0,
		"same_frame_and_sector": same, "max_map_step_m": jump, "step_limit_m": step_limit, "radius_m": r0, "radius_err_m": rerr, "map_pivot_err": pivot_err, "steps": n},
		"note": "the body stands on ring A's deck for one revolution: the marker's ring-local place follows the body's ring-frame physics position to 1 mm (sway is the body's own), keeps its sector, turns with the ring through the phase wrap with no jump, and the map's ring pivot matches the scene's"}

## Triangle centres of a module's map meshes in map-world coordinates, spread over its triangles, outermost from the ship axis first.
func _module_points(m: Dictionary, n := 24) -> Array:
	var pts := []
	for p in parts:
		if p["frame"] == m["frame"] and p["group"] in m["groups"]:
			var mi: MeshInstance3D = p["node"]
			var a := mi.mesh.surface_get_arrays(0)
			var v: PackedVector3Array = a[Mesh.ARRAY_VERTEX]
			var idx: PackedInt32Array = a[Mesh.ARRAY_INDEX]
			var tris := idx.size() / 3
			for k in range(0, tris, maxi(1, tris / n)):
				pts.append(mi.global_transform * ((v[idx[3 * k]] + v[idx[3 * k + 1]] + v[idx[3 * k + 2]]) / 3.0))
	pts.sort_custom(func(a, b): return Vector2(a.y, a.z).length() > Vector2(b.y, b.z).length())
	return pts

## What clicks on these points select: {module id: count}, "" for a miss.
func _picks(pts: Array) -> Dictionary:
	var out := {}
	for q in pts:
		var id := pick(cam.unproject_position(q))
		out[id] = out.get(id, 0) + 1
	return out

func _pick_checks() -> Dictionary:
	var saved := [level, isolate, cutaway, span, yaw, pitch, pan, card_page]
	level = 2
	card_page = -1
	pan = Vector3.ZERO
	span = 260.0
	var bad := []
	var got := {}
	for i in modules.size():
		var m: Dictionary = modules[i]
		isolate = i
		update_now()
		var pts := _module_points(m)
		if pts.is_empty():
			continue
		var r := _picks(pts)
		got[m["id"].get_slice(".", 2)] = r.get(m["id"], 0)
		if r.get(m["id"], 0) == 0 or r.keys().any(func(k): return k != "" and k != m["id"]):
			bad.append("%s isolated: %s" % [m["id"], r])
		if hotspot["module"] != m["id"] and hotspots.has(m["id"]):
			bad.append(m["id"] + ": card does not follow the isolated module")
	isolate = -1
	update_now()
	var rad := _picks(_module_points(_module_by_id("WF.NAVMOD.RADIATORS")).slice(0, 6))
	if rad.get("WF.NAVMOD.RADIATORS", 0) < 3:
		bad.append("radiator blade edges, whole ship shown: %s" % rad)
	var empty := pick(Vector2(2.0, 2.0))
	if empty != "":
		bad.append("empty corner picked " + empty)
	level = saved[0]; isolate = saved[1]; cutaway = saved[2]; span = saved[3]; yaw = saved[4]; pitch = saved[5]; pan = saved[6]; card_page = saved[7]
	update_now()
	return {"id": "nav_pick_modules", "ok": bad.is_empty() and got.size() >= 6, "actual": bad, "hits_per_module": got, "radiators_whole_ship": rad,
		"note": "a click in the overview selects the registered module under it (inner modules before the hull), the card follows it, empty space selects none"}

## NAV-014: the exterior is a picture. FLIGHT_EVA as exported, no route to the exterior for any mode and actor, no stop on an EVA node, and
## the exported hatch sits on the map's own hull (the EVA export and the map share the ship frame).
func _eva_checks() -> Dictionary:
	var bad := []
	if eva.is_empty():
		return {"id": "nav_eva_remote_only", "ok": false, "actual": ["res://generated/wf_eva.json missing"]}
	var fl: Dictionary = eva["flight"]
	if not eva_hatch.text.contains(str(fl["mode"]) + " " + str(fl["state"])):
		bad.append("hatch label does not carry the exported FLIGHT_EVA state")
	var eva_nodes: Array = _module_by_id("WF.NAVMOD.EVA")["nav"]
	var routes := {}
	for mode in host.rig_all["dynamics"]["modes"]:
		for actor in ["human_iva", "human_suited", "seraph"]:
			var r := planner.plan_node("SP12" if actor == "human_suited" else "TRUNK", "EVA_EXTERIOR", {"mode": mode, "actor": actor, "ring_mode": "STOPPED"})
			routes[r["status"]] = routes.get(r["status"], 0) + 1
			if not r["status"] in ["HOLD", "RESTRICTED"]:
				bad.append("%s %s: exterior %s" % [mode, actor, r["status"]])
	for k in nav["stop_nodes"]:
		if nav["stop_nodes"][k] in eva_nodes:
			bad.append("stop %s on an EVA node" % k)
	var h := eva_hatch.position
	var near := INF
	for p in parts:
		if p["frame"] == "STATIONARY" and p["group"] in ["Assembly_HULL", "Assembly_STRUCTURE"]:
			for v in (p["node"] as MeshInstance3D).mesh.surface_get_arrays(0)[Mesh.ARRAY_VERTEX]:
				near = minf(near, h.distance_to(v))
	if near > 1.5:
		bad.append("hatch %.2f m from the map hull" % near)
	return {"id": "nav_eva_remote_only", "ok": bad.is_empty(), "actual": bad, "flight": "%s %s" % [fl["mode"], fl["state"]], "exterior_routes": routes,
		"hatch_to_map_hull_m": near, "note": "the exterior is remote view only while FLIGHT_EVA is HOLD (NAV-014); the overlay is the EVA scene's export"}

func run_checks() -> Array:
	var out := []
	out.append_array(_registry_checks())
	out.append_array(_route_checks())
	out.append_array(_parity_checks())
	out.append_array(_value_checks())
	out.append(_pick_checks())
	out.append(_eva_checks())
	out.append(explorer.checks())
	out.append(drones.checks())
	out.append(drones.route_checks())
	out.append({"id": "nav_marker_matches_body", "ok": samples["n"] > 0 and samples["err"] < 1e-3, "actual": samples["err"], "tol_m": 1e-3, "samples": samples["n"],
		"note": "map marker (through the map's copied frames) = the tracked body, review camera or rail place in ship coordinates, every check step"})
	var sw: Array = samples["switch"]
	var transfer := sw.filter(func(e): return e["chapter"] == "TRANSFER")
	out.append({"id": "nav_frame_switch_continuous", "ok": samples["jump"] < 1e-3 and not transfer.is_empty(), "actual": {"max_step_mismatch_m": samples["jump"], "switches": sw.slice(0, 6)},
		"note": "within a chapter the marker moves exactly as the visitor does, including the stationary -> drum -> ring hand-offs of TRANSFER"})
	out.append(await _revolution())
	out.append_array(space.checks())
	return out

## Key-driven stills of the current chapter (capture with -- --capture-demo=DIR --navigator-stills). The keys go through Input.parse_input_event,
## so the real _unhandled_input paths run: I through the systems card's three pages, M to the overview and back, H / U cutaway and isolation,
## J through the modes, "." to another target; P must still reach the demonstrator (the map never traps a key it does not use).
## Prints WF_NAV_KEYS with what each key did. Display only; the state is restored afterwards.
var key_log: Array = []

func _click(at: Vector2) -> void:
	for down in [true, false]:
		var e := InputEventMouseButton.new()
		e.button_index = MOUSE_BUTTON_LEFT
		e.position = at
		e.global_position = at
		e.pressed = down
		Input.parse_input_event(e)
		await get_tree().process_frame
	await get_tree().process_frame

func _press(k: Key) -> void:
	for down in [true, false]:
		var e := InputEventKey.new()
		e.keycode = k
		e.physical_keycode = k
		e.pressed = down
		Input.parse_input_event(e)
		await get_tree().process_frame
	await get_tree().process_frame

func _expect(what: String, ok: bool) -> void:
	key_log.append({"step": what, "ok": ok})

func stills(dir: String, stem: String, shot: Callable) -> void:
	if stem.ends_with("microgravity") or stem.ends_with("transfer"):
		for page in 3:
			await _press(KEY_I)
			_expect("I page %d" % (page + 1), card_page == page and card.visible and (page < 2 or level == 2))
			await shot.call(dir, "%s_nav_card_%d" % [stem, page + 1])
		await _press(KEY_I)
		_expect("I close", card_page == -1 and not card.visible)
		await _press(KEY_M)
		await _press(KEY_M)
		_expect("M back to corner", level == 1)
	if stem.ends_with("microgravity") and explorer.ready():
		# FWD-V2 forward defense explorer (AVA-013): isolate the shield, SHOW ME, then X / Y / Z / K through the three modes; I closes.
		level = 2
		for i in modules.size():
			if modules[i]["id"] == "WF.NAVMOD.SHIELD_EYE":
				isolate = i
		update_now()
		for page in 3:
			await _press(KEY_I)
		_expect("SHOW ME opens the forward explorer", explorer.active())
		span = 100.0
		yaw = 0.2
		pitch = 0.22
		update_now()
		await shot.call(dir, stem + "_fwd_observe_r4")
		await _press(KEY_Y)
		_expect("Y Eye placement r16", explorer.variant == 1)
		await shot.call(dir, stem + "_fwd_observe_r16")
		await _press(KEY_Y)
		await _press(KEY_Y)
		for k in 2:
			await _press(KEY_Z)
		_expect("Z Crown ENGAGED", explorer.data["crown"]["states"][explorer.crown]["state"] == "ENGAGED")
		await _press(KEY_K)
		_expect("K bay 2", explorer.bay == 2)
		span = 30.0
		yaw = 0.95
		pitch = 0.35
		pan = explorer.bay_point(2) - _module_centre()
		update_now()
		await shot.call(dir, stem + "_fwd_crown_engaged")
		pan = Vector3.ZERO
		await _press(KEY_X)
		await _press(KEY_Z)
		_expect("X DEFENSE SIM, Z play", explorer.mode == 1 and explorer.playing)
		span = 120.0
		yaw = 1.45
		pitch = 0.2
		pan = Vector3(30.0, 0.0, 0.0)
		explorer.t = 3.5 * float(explorer.data["scenario"]["step_display_s"])
		update_now()
		await shot.call(dir, stem + "_fwd_microdust_layer")
		explorer.t = 99.0
		explorer.playing = false
		update_now()
		await shot.call(dir, stem + "_fwd_microdust_outcome")
		await _press(KEY_K)
		await _press(KEY_Z)
		_expect("K PHYSICAL view", explorer.physical)
		await shot.call(dir, stem + "_fwd_microdust_physical")
		await _press(KEY_K)
		await _press(KEY_X)
		_expect("X DAMAGE REPAIR", explorer.mode == 2 and explorer.pose_name == "EYE_F1_JAMMED")
		span = 22.0
		yaw = 0.5
		pitch = 0.35
		pan = Vector3.ZERO
		update_now()
		await shot.call(dir, stem + "_fwd_damage_f1_jammed")
		await _press(KEY_I)
		_expect("I closes and resets the explorer", not explorer.root.visible and explorer.pose_name == "COAST")
		isolate = -1
		span = 260.0
		yaw = 1.15
		pitch = 0.42
		pan = Vector3.ZERO
		level = 1
		update_now()
	if stem.ends_with("microgravity") and drones.ready():
		# DRONE-001 maintenance drone demo (DN-11): isolate the drones, SHOW ME, the study docks, the service run's inspection, a power-loss
		# retrieval and the HIGH_POWER lock; I closes.
		level = 2
		for i in modules.size():
			if modules[i]["id"] == "WF.NAVMOD.DRONES":
				isolate = i
		update_now()
		for page in 3:
			await _press(KEY_I)
		_expect("SHOW ME opens the drone demo", drones.active())
		var keep := mode_id
		mode_id = "GUIDED"
		span = 250.0
		yaw = 1.15
		pitch = 0.5
		pan = Vector3.ZERO
		update_now()
		pan = -_module_centre()
		update_now()
		await shot.call(dir, stem + "_drones_fleet")
		await _press(KEY_C)
		_expect("C shows the DGT-009 route overlay", drones.route_root.visible)
		await shot.call(dir, stem + "_drones_routes")
		drones.route_view = 0
		drones._show_routes()
		var step := float(drones.sc["step_display_s"])
		drones.t = 4.5 * step
		span = 26.0
		yaw = 0.35
		pitch = 0.55
		update_now()
		pan = Vector3.ZERO
		update_now()
		await shot.call(dir, stem + "_drones_inspect")
		await _press(KEY_X)
		_expect("X power-loss run", drones.run == 1)
		drones.t = 2.9 * step
		update_now()
		await shot.call(dir, stem + "_drones_power_loss_retrieval")
		await _press(KEY_X)
		await _press(KEY_X)
		await _press(KEY_X)
		while drones.configs[drones.cfg] != "HIGH_POWER":
			await _press(KEY_K)
		drones.t = 9.0 * step
		update_now()
		_expect("K HIGH_POWER keeps the crawler latched", drones.index() <= 1 and drones.text().contains("LOCKED"))
		await shot.call(dir, stem + "_drones_high_power_locked")
		mode_id = keep
		await _press(KEY_I)
		_expect("I closes and resets the drone demo", not drones.root.visible)
		isolate = -1
		span = 260.0
		yaw = 1.15
		pitch = 0.42
		pan = Vector3.ZERO
		level = 1
		update_now()
	if stem.ends_with("microgravity") or stem.ends_with("gravity"):
		await _press(KEY_M)
		_expect("M overview", level == 2)
		span = 250.0
		update_now()
		await shot.call(dir, stem + "_nav_overview")
		if stem.ends_with("_gravity"):
			var q: Vector3 = _module_points(_module_by_id("WF.NAVMOD.RADIATORS"))[0]
			await _click(view_box.get_global_transform() * cam.unproject_position(q))
			_expect("click selects the radiators", isolate >= 0 and modules[isolate]["id"] == "WF.NAVMOD.RADIATORS")
			await _press(KEY_I)
			_expect("I opens the radiator card", card.visible and hotspot["id"] == "WF.HOTSPOT.RADIATORS")
			await shot.call(dir, stem + "_nav_pick_radiators")
			await _press(KEY_I)
			await _press(KEY_I)
			await _press(KEY_I)
			await _click(view_box.get_global_transform() * Vector2(2.0, 2.0))
			_expect("click on empty space clears", isolate == -1 and not card.visible)
			level = 2
			span = 250.0
			update_now()
		await _press(KEY_H)
		for k in 4:
			await _press(KEY_U)
		_expect("H cutaway, U isolate ring A", cutaway and isolate == 3 and modules[isolate]["id"] == "WF.NAVMOD.RING_A")
		span = 120.0
		update_now()
		await shot.call(dir, stem + "_nav_overview_ring_a_cutaway")
		await _press(KEY_U)
		await _press(KEY_U)
		_expect("U isolate the EVA airlock (remote view)", isolate >= 0 and modules[isolate]["id"] == "WF.NAVMOD.EVA" and eva_root.visible)
		span = 60.0
		update_now()
		await shot.call(dir, stem + "_nav_overview_eva")
		while isolate != -1:
			await _press(KEY_U)
		await _press(KEY_H)
		await _press(KEY_M)
		await _press(KEY_M)
		_expect("M hidden then corner", level == 1 and not cutaway)
		for want in ["FREE", "GUIDED"]:
			await _press(KEY_J)
			_expect("J " + want, mode_id == want)
			await shot.call(dir, "%s_nav_%s" % [stem, want.to_lower()])
		await _press(KEY_J)
		_expect("J back to ASSISTED", mode_id == "ASSISTED")
		var before := chosen
		await _press(KEY_PERIOD)
		_expect(". next target", chosen != before)
		await shot.call(dir, "%s_nav_target_%s" % [stem, chosen])
		await _press(KEY_COMMA)
		_expect(", previous target", chosen == before)
		var paused: bool = demo.paused
		await _press(KEY_P)
		_expect("P reaches the demonstrator", demo.paused != paused)
		await _press(KEY_P)
	print("WF_NAV_KEYS " + JSON.stringify({"stem": stem, "steps": key_log, "fail": key_log.filter(func(e): return not e["ok"]).map(func(e): return e["step"])}))
	key_log = []
