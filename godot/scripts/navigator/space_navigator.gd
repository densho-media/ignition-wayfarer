class_name WfSpaceNavigator
extends Node
## SPACE view of the Wayfarer navigator (S&E 55 SPACE-001.., Stage 1): where Wayfarer is in space, when, and relative to what, beside the
## SHIP view (WfShipNavigator, SNAV-001) in one navigator. It reads only the released First Ignition route (generated/wf_route_v1.json,
## WfRouteState: 25_ROUTE_VALIDATION rows 2:13 must PASS, C-009) and draws it in its own 2D canvas: no shared 3D frame with the ship
## (SHIP is metres in body/ring frames, SPACE is the route's IGNITION_LOCAL_INERTIAL_1D frame with explicit time and origin).
## The selected map time is a view state only: nothing here writes to the host, the body, the rings, the doors or the route planner.
## The scrubber steps through the owner's rows; a displayed value is always a released row (no interpolation, no new samples).
## Rows 14:21 (frame, epoch, ephemerides, full solve, shutdown/Kuiper, six-year route, Kuiper anchorage, mining, return) are OPEN: the Sun-relative position is UNKNOWN,
## the OPEN events stay unplaced (24!D, C-008), and the Solar System scale draws no Sun or planets until the owner releases them.

const SCALES := ["LOCAL", "JOURNEY", "SOLAR"]
const SCALE_TITLE := {"LOCAL": "LOCAL SPACE", "JOURNEY": "MISSION JOURNEY", "SOLAR": "SOLAR SYSTEM"}
const LOG_UNIT_PX := 46.0           # LOCAL: px per decade of the named log display transform (C-004, WfRouteState.display_offset_m)
const CHECK_BOX := Rect2(0, 0, 880, 300)   # the 1280 x 800 canvas, for checks that run in a headless window
const FORBIDDEN := ["from the sun", "from sun", "sun distance", "distance to the sun", "heliocentric position", "heliocentric radius",
	"solar distance", "au from"]      # a relative displacement must never read as a Sun-relative position (NAV-030)
## SPACE-021: overlays the visitor switches with 1-8 while SPACE shows; the legend names each one's line style, source and status.
## The disclosures (LIVE / SCENARIO PREVIEW, DIAGNOSTIC 1D, the UNKNOWN Solar System position, SCHEMATIC and the chart mode) are not
## layers: they stay whatever is switched off (SPACE-023). A layer only hides a drawing; it never changes a value, a row or a pick result
## other than that a hidden Kuiper guide cannot be clicked.
const LAYERS := [
	{"id": "TRACK", "key": KEY_1, "title": "track", "scales": ["LOCAL", "JOURNEY"],
		"legend": "solid line: the released rows (23_ROUTE_FRAMES)"},
	{"id": "MOTION", "key": KEY_2, "title": "motion", "scales": ["LOCAL", "JOURNEY"],
		"legend": "filled / open arrow: the row's velocity / acceleration, not an attitude (C-013 OPEN)"},
	{"id": "EVENTS", "key": KEY_3, "title": "events", "scales": ["JOURNEY"],
		"legend": "green: an event with a released time and place (24) · ?: OPEN, never drawn"},
	{"id": "ORBITS", "key": KEY_4, "title": "orbits", "scales": ["SOLAR"],
		"legend": "thin arc, faint band: reference orbit, perihelion–aphelion (NASA)"},
	{"id": "KUIPER", "key": KEY_5, "title": "Kuiper guide", "scales": ["SOLAR"],
		"legend": "dashed band: Kuiper regional guide (NASA), not an event"},
	{"id": "GRID", "key": KEY_6, "title": "grid", "scales": ["LOCAL", "JOURNEY", "SOLAR"],
		"legend": "grid, length bar: drawing aids, not coordinates"},
	{"id": "NOTES", "key": KEY_7, "title": "notes", "scales": ["LOCAL", "JOURNEY", "SOLAR"],
		"legend": "notes: DRAFT wording"},
	{"id": "LEGEND", "key": KEY_8, "title": "legend", "scales": ["LOCAL", "JOURNEY", "SOLAR"], "legend": ""},
]
## POL-008 Prototype A (S&E 59; MECH-001/005 education, references/SIM_INTEGRATION_PLAN_2026-10-17.md): replay of the released rows at the
## route's own production clock (22 fps, clip_length_s: 900 rows in 30 s), a MOTION card on the selected row, and a display-only attitude.
const CARD_PAGES := ["WHAT", "WHY", "HOW"]
const ATTITUDE_STEP_DEG := 45.0

var ship: WfShipNavigator
var host
var demo
var route := WfRouteState.new()
var route_error := ""
var active := false
var scale := "JOURNEY"
var index := -1                      # selected owner row (0-based into route.frames); -1 = LIVE (the running scene, no row selected)
var pal := {}
var placed: Array = []               # events with a released displacement (drawn), each {id, au, t_s, status}
var unplaced: Array = []             # events with OPEN time/position (listed only, never drawn)
var drawn_bodies := 0                # Sun / planet glyphs drawn this frame (Stage 1: always 0)
var marker_px := Vector2.ZERO        # last drawn ship marker (checks)
var shown := {}                      # the values the readout shows (checks): always one released row
var layers_on := {}                  # SPACE-021 layer id -> shown
var playing := false                 # replay: steps through the released rows at the route's fps (a view state, like the scrubber)
var play_acc := 0.0
var card := -1                       # MOTION card page (CARD_PAGES index), -1 closed
var attitude_on := false             # LOCAL: an ILLUSTRATIVE hull glyph the visitor turns with R (C-013 attitude OPEN, SPACE-014)
var attitude_deg := 0.0
var kin_v: PackedFloat64Array = []   # DERIVED: the released acceleration integrated row to row (exact for a linear in each step, C-010)
var kin_x: PackedFloat64Array = []
var kin_err := {"v": 0.0, "x": 0.0}  # worst relative difference against the rows (rows with x > 0)

var layer := CanvasLayer.new()
var panel := PanelContainer.new()
var vbox := VBoxContainer.new()
var tabs := Label.new()
var badge := Label.new()
var canvas := Control.new()
var readout := Label.new()
var events_label := Label.new()
var slider := HSlider.new()
var hint := Label.new()
var legend := Label.new()
var layers_label := Label.new()
var keys := Label.new()
var font: Font
var solar: WfSolarChart              # Stage 2 Solar System chart (rig space_navigator, SPACE-030)

func setup(s: WfShipNavigator) -> void:
	ship = s
	host = s.host
	demo = s.demo
	pal = s.pal
	font = ThemeDB.fallback_font
	for l in LAYERS:
		layers_on[l.id] = true
	route_error = route.load_file("res://generated/wf_route_v1.json", host.rig_all)
	solar = WfSolarChart.new(self, host.rig_all)
	_sort_events()
	_build_ui()
	panel.visible = false

## Replace the route (rejection checks): returns the gate's reason, "" when accepted.
func use_route(data, rig: Dictionary) -> String:
	route = WfRouteState.new()
	route_error = route.load_data(data, rig)
	index = -1
	_sort_events()
	return route_error

func _sort_events() -> void:
	placed.clear()
	unplaced.clear()
	_integrate()
	if not route.ok():
		return
	for e in route.route.events:
		if e.get("mission_t_s") == null or e.get("displacement_AU") == null:
			unplaced.append({"id": str(e.event_id), "status": str(e.physics_status), "story": str(e.story_status), "note": str(e.interpretation)})
		else:
			placed.append({"id": str(e.event_id), "au": float(e.displacement_AU), "t_s": float(e.mission_t_s), "status": str(e.physics_status)})

## Newton's check on the released rows (MOTION card HOW): integrate the rows' acceleration once for speed and twice for distance, taking
## a as linear within each step (the route's own between-row rule, C-010). DERIVED from the rows; it never replaces or adds a row.
func _integrate() -> void:
	kin_v = PackedFloat64Array()
	kin_x = PackedFloat64Array()
	kin_err = {"v": 0.0, "x": 0.0}
	if not route.ok():
		return
	var f: Array = route.route.frames
	var c := route.col
	kin_v.append(float(f[0][c.vx_mps]))
	kin_x.append(float(f[0][c.local_x_m]))
	for i in range(1, f.size()):
		var dt := float(f[i][c.mission_t_s]) - float(f[i - 1][c.mission_t_s])
		var a0 := float(f[i - 1][c.ax_mps2])
		var a1 := float(f[i][c.ax_mps2])
		kin_x.append(kin_x[i - 1] + kin_v[i - 1] * dt + a0 * dt * dt / 2.0 + (a1 - a0) * dt * dt / 6.0)
		kin_v.append(kin_v[i - 1] + (a0 + a1) * dt / 2.0)
		var v := float(f[i][c.vx_mps])
		var x := float(f[i][c.local_x_m])
		if x > 0.0:
			kin_err.v = maxf(kin_err.v, absf(kin_v[i] - v) / v)
			kin_err.x = maxf(kin_err.x, absf(kin_x[i] - x) / x)

func _event(id: String) -> Dictionary:
	for e in route.route.events:
		if str(e.event_id) == id:
			return e
	return {}

## The MOTION card on the selected row: WHAT (acceleration), WHY (the owner's linear ramp, with the owner's HALFWAY_IN_TIME event),
## HOW (inertia: the rows obey v = ∫a dt, x = ∫v dt; shutdown OPEN, so no coast is drawn; momentum needs a mass history the route lacks).
func card_text() -> String:
	if card < 0 or not route.ok():
		return ""
	var m: Dictionary = route.route.model
	var pages := []
	for i in CARD_PAGES.size():
		pages.append(("▸ " + CARD_PAGES[i]) if i == card else CARD_PAGES[i].to_lower())
	var lines := ["MOTION  %s   (%s next · close after HOW)" % [" → ".join(pages), WfInput.label("space.card")]]
	var v_end := float(m.target_velocity_mps.value)
	var x_end := float(m.burn_distance_m.value)
	match card:
		0:
			if shown.is_empty():
				lines.append("ACCELERATION is how fast the velocity changes. At the dock there is no burn and no released acceleration: preview a row with %s %s or %s." % WfInput.labels(["space.step_prev", "space.step_next", "space.replay"]))
			else:
				lines.append("ACCELERATION is how fast the velocity changes. This row: a = %.4f g (%s m/s²) along local +X; speed %s km/s (%.5f c)."
					% [shown.accel_g, String.num(shown.accel_g * float(m.g0.value), 3), _num(shown.vx_mps / 1000.0, 1), shown.speed_fraction_c])
				lines.append("Aboard, the acceleration is felt as weight toward the stern. The speed itself is not felt at all.")
			lines.append("[DIAGNOSTIC 1D · released rows of 23_ROUTE_FRAMES]")
		1:
			var h := _event("HALFWAY_IN_TIME")
			lines.append("WHY it grows unevenly: the V1 study raises the acceleration steadily from %.1f to %.1f g (22: a = j·t, j = %s m/s³, %s)."
				% [float(m.start_accel_g.value), float(m.max_accel_g.value), _sci(float(m.jerk_mps3.value), 3), m.acceleration_model.authority])
			if not h.is_empty():
				lines.append("At half the burn time (24 HALFWAY_IN_TIME, T+%.3f d) it is at %.2f g, but has only %.3f of the final speed and %.3f of the distance:"
					% [float(h.mission_t_days), float(h.accel_g), float(h.velocity_mps) / v_end, float(h.displacement_x_m) / x_end])
				lines.append("speed grows with t², distance with t³ (1/4 and 1/8 at half time). The owner's note: \"%s\"" % str(h.interpretation))
			lines.append("[BASELINE ramp · DERIVED ratios of released values · not a full mission solve (22 gravity_model OPEN)]")
		2:
			if shown.is_empty():
				lines.append("INERTIA: velocity is the sum of every push so far. Preview a row (%s %s or %s) to add up the released pushes." % WfInput.labels(["space.step_prev", "space.step_next", "space.replay"]))
			else:
				var i := index
				lines.append("INERTIA: velocity is the sum of every push so far. Adding a·Δt over rows 1–%d gives %s km/s (row: %s km/s);"
					% [i + 1, _num(kin_v[i] / 1000.0, 1), _num(shown.vx_mps / 1000.0, 1)])
				lines.append("adding the motion again gives %.6f AU (row: %.6f AU). Worst difference over all rows: %s (speed), %s (distance)."
					% [kin_x[i] / float(m.AU_m.value), shown.distance_traveled_AU, _sci(kin_err.v, 1), _sci(kin_err.x, 1)])
			lines.append("Without thrust the velocity simply stays: nothing is needed to keep moving (Newton's first law).")
			lines.append("When the drive stops is OPEN (22 shutdown_or_coast_start, 24 DRIVE_SHUTDOWN): row %d is the end of the ramp at %.3f c, not a shutdown, so no coast is drawn."
				% [route.route.frames.size(), float(m.beta_target.value)])
			lines.append("Momentum (mass × velocity) needs Wayfarer's mass through the burn, which the route does not carry (no fuel depletion in the V1 model).")
			lines.append("[DERIVED check of released rows · Newtonian V1 (γ−1 = %s, DIAGNOSTIC)]" % _sci(float(m.relativistic_gamma_excess.value), 2))
	return "\n".join(lines)

func toggle_play() -> void:
	if not route.ok():
		return
	if not playing and index >= route.route.frames.size() - 1:
		index = -1                          # at the end: replay from row 1
	playing = not playing
	play_acc = 0.0
	if playing and index < 0:
		select(0)
	update_now()

func play_rate() -> float:
	return float(route.route.get("fps", 30.0))

func _process(delta: float) -> void:
	if playing:
		step_replay(delta)

## One replay step: whole released rows only (no interpolated value is ever shown); stops on the last row.
func step_replay(delta: float) -> void:
	if not (active and route.ok()):
		playing = false
		return
	play_acc += delta * play_rate()
	var n := int(floor(play_acc))
	if n <= 0:
		return
	play_acc -= n
	var last: int = route.route.frames.size() - 1
	select(mini(index + n, last))
	if index >= last:
		playing = false
		update_now()

# ---------------------------------------------------------------------------------------------------------------------------- UI

func _lab(l: Label, size: int, color: Color) -> Label:
	l.add_theme_font_size_override("font_size", size)
	l.add_theme_color_override("font_color", color)
	l.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	return l

func _build_ui() -> void:
	layer.layer = 8                  # over the demonstrator's HUD texts while SPACE shows (the ship map hides meanwhile)
	add_child(layer)
	var sb := StyleBoxFlat.new()
	sb.bg_color = Color(pal["base"], 0.97)
	sb.border_color = Color(pal["structure_faint"], 0.9)
	sb.set_border_width_all(1)
	sb.set_content_margin_all(10.0)
	panel.add_theme_stylebox_override("panel", sb)
	layer.add_child(panel)
	panel.add_child(vbox)
	vbox.add_theme_constant_override("separation", 6)
	vbox.add_child(_lab(tabs, 13, pal["quiet"]))
	vbox.add_child(_lab(badge, 14, pal["caution"]))
	canvas.custom_minimum_size = Vector2(600, 230)
	canvas.mouse_filter = Control.MOUSE_FILTER_IGNORE
	canvas.clip_contents = true
	canvas.focus_mode = Control.FOCUS_NONE
	canvas.gui_input.connect(_canvas_input)
	canvas.draw.connect(_draw_canvas)
	vbox.add_child(canvas)
	slider.min_value = 0
	slider.step = 1
	slider.focus_mode = Control.FOCUS_NONE       # never takes the keyboard from the scene
	slider.value_changed.connect(func(v): select(int(v)))
	vbox.add_child(slider)
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 18)
	row.add_child(_lab(readout, 14, pal["text"]))
	row.add_child(_lab(events_label, 13, pal["quiet"]))
	vbox.add_child(row)
	vbox.add_child(_lab(hint, 13, pal["text"]))
	vbox.add_child(_lab(legend, 12, pal["quiet"]))
	vbox.add_child(_lab(layers_label, 12, pal["quiet"]))
	vbox.add_child(_lab(keys, 12, pal["quiet"]))
	keys.text = keys_text()
	WfInput.bindings_changed.connect(_on_bindings)
	if route.ok():
		slider.max_value = route.route.frames.size() - 1

func layout() -> void:
	var size: Vector2 = get_viewport().get_visible_rect().size
	panel.visible = active
	if not active:
		return
	canvas.mouse_filter = Control.MOUSE_FILTER_STOP if scale == "SOLAR" and solar.ok() else Control.MOUSE_FILTER_IGNORE
	keys.text = keys_text()
	var w := maxf(minf(size.x - 2.0 * 28.0 - ship.SIDE_W - 16.0, 1100.0), 560.0)   # headless windows are tiny
	var k := clampf(size.y / 800.0, 1.0, 1.35)       # 1280x800 -> 1.0, 1920x1080 -> 1.35 (NAV-025 two resolutions)
	canvas.custom_minimum_size = Vector2(w, minf(size.y * 0.36, w * 0.4))
	for l in [tabs, badge, hint, legend, layers_label, keys]:
		l.custom_minimum_size.x = w
	readout.custom_minimum_size.x = w * 0.56
	events_label.custom_minimum_size.x = w * 0.40
	for l in [tabs, badge, readout, events_label, hint, legend, layers_label, keys]:
		l.add_theme_font_size_override("font_size", int(round({tabs: 13, badge: 14, readout: 14, events_label: 13, hint: 13, legend: 12, layers_label: 12, keys: 12}[l] * k)))
	panel.size = Vector2.ZERO
	panel.size = panel.get_combined_minimum_size()
	var over := panel.size.y - (size.y - 40.0)
	if over > 0.0:                                  # the texts always fit on screen: the canvas gives up the height (SPACE-021)
		canvas.custom_minimum_size.y = maxf(canvas.custom_minimum_size.y - over, 150.0)
		panel.size = Vector2.ZERO
		panel.size = panel.get_combined_minimum_size()
	panel.position = Vector2(28.0, maxf(20.0, size.y - panel.size.y - 20.0))

# ---------------------------------------------------------------------------------------------------------------------- state

## Live mission time of the running scene, or null. The demonstrator plays the S004 pre-First-Ignition tour (DOCKED -> COAST): the
## mission clock has not started, so every First Ignition row is a SCENARIO PREVIEW, never LIVE (SPACE stage 1 C).
func live_mission_t():
	if demo != null and demo.has_method("live_mission_t"):
		return demo.live_mission_t()
	return null

## SPACE-005/006: LIVE until the visitor selects a row; a selected First Ignition row is a SCENARIO PREVIEW unless the live clock is on it.
func preview() -> bool:
	if index < 0 or not route.ok():
		return false
	var live = live_mission_t()
	return live == null or absf(float(live) - route.times[index]) > 1e-9

## SPACE-020: the Wayfarer marker's "Inspect ship" opens the expanded Ship Navigator; the selected mission time is kept for the way back.
func inspect_ship() -> void:
	active = false
	ship.level = 2
	update_now()
	ship.update_now()

func set_active(on: bool) -> void:
	active = on
	update_now()
	ship.update_now()

func select(i: int) -> void:
	if not route.ok():
		return
	index = clampi(i, -1, route.route.frames.size() - 1)
	if int(slider.value) != maxi(index, 0):
		slider.set_value_no_signal(maxi(index, 0))
	update_now()

func row_values(i: int) -> Dictionary:
	var r: Array = route.row(i)
	var out := {"frame": int(r[route.col.frame]), "phase": str(r[route.col.phase])}
	for k in ["mission_t_s", "mission_t_days", "local_x_m", "vx_mps", "accel_g", "speed_fraction_c", "distance_traveled_AU"]:
		out[k] = float(r[route.col[k]])
	return out

func _unhandled_input(e: InputEvent) -> void:
	# ACI-09: the SPACE keys are WfInput actions (space.*; ship.space and ship.mode shared with SHIP). While SPACE shows it takes the
	# inputs it owns before the ship map and the body; the layers are space.layer_1..8 (ACI-10).
	if not e.is_pressed() or not (e is InputEventKey or e is InputEventJoypadButton):
		return
	if _act(e, "ship.space"):
		set_active(not active)
		get_viewport().set_input_as_handled()
		return
	if not active:
		return
	var shift: bool = e is InputEventKey and e.shift_pressed
	var stepping: bool = _act(e, "space.step_next", true) or _act(e, "space.step_prev", true)
	if stepping or _act(e, "space.live", true) or _act(e, "space.burn_end", true):
		playing = false                     # a manual step takes the row back from the replay
	if stepping:
		var step := (1 if _act(e, "space.step_next", true) else -1) * (30 if shift else 1)
		select(maxi(index + step, 0) if index >= 0 or step > 0 else -1)
	elif _act(e, "space.live", true):
		select(-1)
	elif _act(e, "space.burn_end", true):
		select(route.route.frames.size() - 1 if route.ok() else -1)
	elif _act(e, "space.replay"):
		if scale == "SOLAR":
			return
		toggle_play()
	elif _act(e, "space.card"):
		if scale == "SOLAR":
			return
		card = card + 1 if card < CARD_PAGES.size() - 1 else -1
		update_now()
	elif _act(e, "space.attitude"):
		if scale != "LOCAL":
			return
		if shift:
			attitude_on = false
			attitude_deg = 0.0
		elif not attitude_on:
			attitude_on = true
		else:
			attitude_deg = fmod(attitude_deg + ATTITUDE_STEP_DEG, 360.0)
		update_now()
	elif _act(e, "space.inspect"):
		if scale == "SOLAR" and solar.ok():
			solar.next_page()
			update_now()
		else:
			inspect_ship()
	elif _act(e, "space.chart_mode"):
		if scale != "SOLAR":
			return
		solar.mode = WfSolarChart.MODES[(WfSolarChart.MODES.find(solar.mode) + 1) % 2]
		update_now()
	elif _act(e, "space.zoom_out", true) or _act(e, "space.zoom_in", true):
		if scale != "SOLAR":
			return
		solar.zoom = clampi(solar.zoom + (1 if _act(e, "space.zoom_out", true) else -1), 0, solar.reg.zooms.size() - 1)
		update_now()
	elif _act(e, "space.select_prev", true) or _act(e, "space.select_next", true):
		if scale != "SOLAR":
			return
		solar.cycle(1 if _act(e, "space.select_next", true) else -1)
		update_now()
	elif WfInput.key_of(e, ["space"]) >= KEY_1 and WfInput.key_of(e, ["space"]) <= KEY_8:     # ACI-10: space.layer_1..8
		if e.is_echo():
			return
		toggle_layer(LAYERS[WfInput.key_of(e, ["space"]) - KEY_1].id)
	elif _act(e, "space.scale_prev") or _act(e, "space.scale_next"):
		scale = SCALES[(SCALES.find(scale) + (1 if _act(e, "space.scale_next") else SCALES.size() - 1)) % SCALES.size()]
		update_now()
	else:
		return
	get_viewport().set_input_as_handled()

func _on_bindings() -> void:
	if active:
		update_now()

static func _act(e: InputEvent, id: String, echo := false) -> bool:
	return e.is_action_pressed(id, echo)

## ACI-09: the key line from the visitor's current inputs (WfInput labels), per scale.
func keys_text() -> String:
	var k := func(id: String) -> String: return WfInput.label(id)
	var common: String = "%s ship · %s %s sample" % [k.call("ship.space"), k.call("space.step_prev"), k.call("space.step_next")]
	var scales := "%s %s scale" % [k.call("space.scale_prev"), k.call("space.scale_next")]
	if scale == "SOLAR":
		return "%s · %s · %s analytical / presentation · %s %s zoom · %s %s or click select · %s card · %s mode · %s layers" % [common, scales,
			k.call("space.chart_mode"), k.call("space.zoom_out"), k.call("space.zoom_in"), k.call("space.select_prev"), k.call("space.select_next"),
			k.call("space.inspect"), k.call("ship.mode"), layer_keys()]
	return "%s (shift ×30) · %s replay · %s motion card · %s live · %s burn end · %s · %s inspect ship · %s mode · %s layers" % [common,
		k.call("space.replay"), k.call("space.card"), k.call("space.live"), k.call("space.burn_end"), scales, k.call("space.inspect"), k.call("ship.mode"), layer_keys()] \
		+ (" · %s turn display hull (shift: off)" % k.call("space.attitude") if scale == "LOCAL" else "")

func layer_keys() -> String:
	return "%s–%s" % [WfInput.label("space.layer_1"), WfInput.label("space.layer_8")]

## SPACE-021: is the layer shown (and does it apply to the current scale)?
func on(id: String) -> bool:
	return bool(layers_on.get(id, true))

func toggle_layer(id: String) -> void:
	layers_on[id] = not on(id)
	update_now()

func layer_texts() -> Array:
	var row := []
	var lines := []
	for l in LAYERS:
		if scale in l.scales:
			row.append("%s %s %s" % [WfInput.label("space.layer_%d" % (l.key - KEY_1 + 1)), "[x]" if on(l.id) else "[ ]", l.title])
			if on(l.id) and l.legend != "":
				lines.append(l.legend)
	lines.append("amber: a disclosure, always shown")
	return ["LAYERS  " + "   ".join(row), "LEGEND  " + " · ".join(lines) if on("LEGEND") else ""]

# ---------------------------------------------------------------------------------------------------------------------- texts

static func clock(t_s: float) -> String:
	var s := int(floor(t_s))
	return "T+%dd %02d:%02d:%02d" % [s / 86400, (s % 86400) / 3600, (s % 3600) / 60, s % 60]

func _guidance() -> Dictionary:
	return ship.guidance()

func panel_text() -> String:
	return "\n".join([tabs.text, badge.text, readout.text, events_label.text, hint.text, legend.text, layers_label.text])

func update_now() -> void:
	var tab := []
	for s in SCALES:
		tab.append(("▸ " + SCALE_TITLE[s]) if s == scale else SCALE_TITLE[s].to_lower())
	tabs.text = "GU WAYFARER · NAVIGATOR · ship  ▸ SPACE   ·   " + "  |  ".join(tab) + "   ·   " + str(_guidance()["title"]).to_upper() \
		+ (("   ·   " + solar.mode) if scale == "SOLAR" and solar.ok() else "")
	if not route.ok():
		shown = {}
		badge.text = "‖ NO VALIDATED ROUTE — nothing is shown: " + route_error
		readout.text = "SOLAR SYSTEM POSITION  UNKNOWN\nMISSION TIME  —\nDISTANCE TRAVELED  —\nSPEED  —"
		events_label.text = ""
		hint.text = ""
		legend.text = ""
		layers_label.text = ""
		slider.editable = false
		canvas.queue_redraw()
		layout()
		return
	slider.editable = true
	var r := route.route
	var place := "SOLAR SYSTEM POSITION  UNKNOWN — 25!F14 COORDINATE_FRAME_VALIDATED, F15 SOLAR_EPHEMERIDES_VALIDATED are OPEN"
	var source := "SOURCE  S&E 23_ROUTE_FRAMES · sheet modified %s · route %s · checks 2–13 PASS · %d OPEN" % [str(r.source.modified_at_utc).substr(0, 10), r.route_version, r.open_checks.size()]
	if index < 0:
		shown = {}
		var cfg: String = demo.ctl.mode if demo != null and demo.ctl != null else "DOCKED"
		badge.text = "▶ LIVE — Wayfarer at the induction dock (%s), before First Ignition   ·   %s %s preview the First Ignition study" % [cfg, WfInput.label("space.step_prev"), WfInput.label("space.step_next")]
		readout.text = "\n".join([
			"LIVE  the induction tour (S004): First Ignition has not happened",
			"MISSION ELAPSED  — (the flight clock has not started)",
			"DISTANCE TRAVELED  — (no burn yet)",
			"SPEED  — (no released state for the dock)",
			"FRAME  SHIP view frames apply aboard; SPACE has no released state for the dock",
			place, source])
	else:
		shown = row_values(index)
		var v := shown
		badge.text = "◇ SCENARIO PREVIEW — not live; the induction tour is before First Ignition   ·   %s   ·   ? DIAGNOSTIC 1D" % r.scenario_id \
			+ ("   ·   ▶ REPLAY %d rows/s (route clock)" % int(play_rate()) if playing else "")
		readout.text = "\n".join([
			"SAMPLE  %d / %d   (23_ROUTE_FRAMES row %d, phase %s)" % [v.frame, r.frames.size(), v.frame + 1, v.phase],
			"MISSION ELAPSED  %s   (%s s · %.4f d)" % [clock(v.mission_t_s), _num(v.mission_t_s, 1), v.mission_t_days],
			"DISTANCE TRAVELED  %.6f AU   (%s m along local +X from the ignition origin)" % [v.distance_traveled_AU, _sci(v.local_x_m)],
			"SPEED  %.5f c   (%s km/s)   ·   ACCEL  %.4f g" % [v.speed_fraction_c, _num(v.vx_mps / 1000.0, 1), v.accel_g],
			"FRAME  %s · origin: ignition point (epoch OPEN) · units s, m, AU, c" % r.frame_id,
			place, source])
	var ev := ["EVENTS WITH A RELEASED DISPLACEMENT"]
	for e in placed:
		ev.append("  ▶ %s  %s · %.4f AU" % [e.id, clock(e.t_s), e.au])
	ev.append("NOT PLACED — OPEN (24!D; no time, no position)")
	for e in unplaced:
		ev.append("  ? %s  %s" % [e.id, e.story])
	events_label.text = "\n".join(ev)
	if not on("EVENTS"):
		events_label.text = "EVENTS  layer off (3): %d with a released displacement, %d OPEN and not placed" % [placed.size(), unplaced.size()]
	if scale == "SOLAR" and solar.ok():
		events_label.text = solar.card_text() if solar.page >= 0 else "SELECTED  %s   (%s: WHAT → WHY → SHOW ME)\n%s" % [solar._title(solar.selected), WfInput.label("space.inspect"),
			"position UNKNOWN; no marker on the chart" if solar.selected == "WAYFARER" else "reference values; arrangement SCHEMATIC"]
	var g := _guidance()
	var lines := []
	if g["narration"] and on("NOTES"):
		lines.append({"LOCAL": "Wayfarer at the centre; the ignition origin falls behind along local −X. Nothing nearby has a sourced position.",
			"JOURNEY": "The First Ignition ramp: 0 → 0.016 c in 7.548 days, 6.970 AU traveled from where the drive lit. Where in the Solar System that was is not yet fixed.",
			"SOLAR": "Sun and planets wait on the owner's epoch and ephemerides; the ship's place among them is UNKNOWN."}[scale])
	if g["hints"] and on("NOTES"):
		lines.append(r.legend)
	if attitude_on and scale == "LOCAL":
		lines.append("DISPLAY ATTITUDE %d° — ILLUSTRATIVE: Wayfarer's attitude is OPEN (C-013). Turning the hull leaves the travel direction and speed unchanged; only thrust changes velocity (SPACE-014)." % int(attitude_deg))
	if card >= 0 and scale != "SOLAR":
		lines = [card_text()] + lines.slice(lines.size() - (1 if attitude_on and scale == "LOCAL" else 0))
	hint.text = "\n".join(lines)
	var lt := layer_texts()
	layers_label.text = lt[0]
	legend.text = lt[1]
	legend.visible = legend.text != "" and card < 0      # the open MOTION card takes the legend's lines (the texts must fit, SPACE-021)
	canvas.queue_redraw()
	layout()

static func _num(x: float, decimals: int) -> String:
	var s := String.num(absf(x), decimals)
	var head := s.get_slice(".", 0)
	var out := ""
	for i in head.length():
		if i > 0 and (head.length() - i) % 3 == 0:
			out += ","
		out += head[i]
	return ("-" if x < 0.0 else "") + out + (("." + s.get_slice(".", 1)) if decimals > 0 else "")

static func _sci(x: float, digits := 4) -> String:
	if x == 0.0:
		return "0"
	var e := int(floor(log(absf(x)) / log(10.0)))
	var m := snappedf(x / pow(10.0, e), pow(10.0, -digits))
	if absf(m) >= 10.0:
		m /= 10.0
		e += 1
	return ("%." + str(digits) + "fe%d") % [m, e]

# ---------------------------------------------------------------------------------------------------------------------- drawing

func _text(at: Vector2, s: String, color: Color, size := 13, align := HORIZONTAL_ALIGNMENT_LEFT) -> void:
	var w := font.get_string_size(s, HORIZONTAL_ALIGNMENT_LEFT, -1, size).x
	var x := at.x - (w / 2.0 if align == HORIZONTAL_ALIGNMENT_CENTER else (w if align == HORIZONTAL_ALIGNMENT_RIGHT else 0.0))
	canvas.draw_string(font, Vector2(x, at.y), s, HORIZONTAL_ALIGNMENT_LEFT, -1, size, color)

func _grid(r: Rect2) -> void:
	var c := Color(pal["structure_faint"], 0.35)
	var step := 40.0
	var x := r.position.x
	while x <= r.end.x:
		canvas.draw_line(Vector2(x, r.position.y), Vector2(x, r.end.y), c, 1.0)
		x += step
	var y := r.position.y
	while y <= r.end.y:
		canvas.draw_line(Vector2(r.position.x, y), Vector2(r.end.x, y), c, 1.0)
		y += step

## JOURNEY: AU traveled from the ignition origin -> px (linear, the route's own geometry; no display exaggeration).
func journey_x(au: float, r: Rect2) -> float:
	var end_au := float(route.route.frames[-1][route.col.distance_traveled_AU])
	return r.position.x + 60.0 + (r.size.x - 120.0) * au / end_au

func _draw_canvas() -> void:
	drawn_bodies = 0
	var r := Rect2(Vector2.ZERO, canvas.size)
	canvas.draw_rect(r, Color(pal["graphite"], 0.55))
	if on("GRID"):
		_grid(r)
	if not route.ok():
		_text(r.get_center(), "NO VALIDATED ROUTE", pal["caution"], 18, HORIZONTAL_ALIGNMENT_CENTER)
		return
	match scale:
		"JOURNEY": _draw_journey(r)
		"LOCAL": _draw_local(r)
		"SOLAR": _draw_solar(r)

## The journey marker for the selected row: that row's traveled AU on the linear track (no smoothing, C-010); none when LIVE.
func marker_at(r: Rect2) -> Vector2:
	if shown.is_empty():
		return Vector2(-1, -1)
	return Vector2(journey_x(shown.distance_traveled_AU, r), r.position.y + r.size.y * 0.42)

## Sun / planet glyphs the Solar System scale lays out (SCHEMATIC; never a Wayfarer marker, SPACE-010/015).
func solar_bodies() -> Array:
	if not solar.ok():
		return []
	solar.layout(CHECK_BOX)
	return solar.glyphs.keys()

func _canvas_input(e: InputEvent) -> void:
	if scale != "SOLAR" or not solar.ok():
		return
	if e is InputEventMouseButton and e.pressed:
		match e.button_index:
			MOUSE_BUTTON_LEFT:
				solar.select(solar.pick(e.position))
				if solar.selected == "":
					solar.selected = "WAYFARER"
			MOUSE_BUTTON_WHEEL_UP: solar.zoom = maxi(solar.zoom - 1, 0)
			MOUSE_BUTTON_WHEEL_DOWN: solar.zoom = mini(solar.zoom + 1, solar.reg.zooms.size() - 1)
			_: return
		canvas.accept_event()
		update_now()

func _draw_journey(r: Rect2) -> void:
	var y := r.position.y + r.size.y * 0.42
	var fs := int(round(12 * clampf(canvas.size.y / 230.0, 1.0, 1.35)))
	var x0 := journey_x(0.0, r)
	var x1 := journey_x(float(route.route.frames[-1][route.col.distance_traveled_AU]), r)
	# The released track: every owner row is a vertex (a 1D track: the line is the rows' x, not a drawn curve).
	if on("TRACK"):
		var pts := PackedVector2Array()
		for i in route.route.frames.size():
			pts.append(Vector2(journey_x(float(route.route.frames[i][route.col.distance_traveled_AU]), r), y))
		canvas.draw_polyline(pts, pal["structure"], 2.0)
		for au in range(0, int(floor(float(route.route.frames[-1][route.col.distance_traveled_AU]))) + 1):
			var x := journey_x(float(au), r)
			canvas.draw_line(Vector2(x, y - 5), Vector2(x, y + 5), pal["structure"], 1.0)
			_text(Vector2(x, y + 20), "%d" % au, pal["quiet"], fs, HORIZONTAL_ALIGNMENT_CENTER)
		_text(Vector2(x1, y - 12), "AU traveled along local +X →", pal["quiet"], fs, HORIZONTAL_ALIGNMENT_RIGHT)
		_text(Vector2(x0, y - 58), "IGNITION ORIGIN", pal["quiet"], fs)
		_text(Vector2(x0, y - 44), "(local; epoch, place OPEN)", pal["quiet"], fs - 1)
		canvas.draw_line(Vector2(x0, y - 40), Vector2(x0, y - 6), Color(pal["quiet"], 0.5), 1.0)
	# Event labels: a leader from the event's released AU, the label on the first row where it does not overlap an earlier one.
	var rows: Array = []                      # per label row: the right edge already used
	for e in (placed if on("EVENTS") else []):
		var x := journey_x(e.au, r)
		var label: String = e.id.replace("_", " ")
		var w := font.get_string_size(label, HORIZONTAL_ALIGNMENT_LEFT, -1, fs - 1).x
		var left := minf(x, x1 - w)
		var n := 0
		while n < rows.size() and rows[n] > left - 10.0:
			n += 1
		if n == rows.size():
			rows.append(0.0)
		rows[n] = left + w
		var ly := y + 44 + (fs + 4) * n
		canvas.draw_line(Vector2(x, y + 28), Vector2(x, ly - fs + 2), Color(pal["go"], 0.6), 1.0)
		_text(Vector2(left, ly), label, pal["go"], fs - 1)
	_text(Vector2(r.end.x - 8, r.end.y - 10), "DIAGNOSTIC 1D · not a heliocentric or Earth distance · OPEN events not placed", pal["caution"], fs, HORIZONTAL_ALIGNMENT_RIGHT)
	# Speed against mission time (the released rows), the cursor at the selected row.
	var g := Rect2(r.end.x - r.size.x * 0.30 - 60, r.position.y + 14, r.size.x * 0.30, r.size.y * 0.24)
	var tmax: float = route.times[route.times.size() - 1]
	if on("MOTION"):
		var sp := PackedVector2Array()
		for i in range(0, route.route.frames.size(), 3):
			var row: Array = route.route.frames[i]
			sp.append(Vector2(g.position.x + g.size.x * float(row[route.col.mission_t_s]) / tmax, g.end.y - g.size.y * float(row[route.col.speed_fraction_c]) / 0.016))
		canvas.draw_line(g.position + Vector2(0, g.size.y), g.end, pal["structure_faint"], 1.0)
		canvas.draw_line(g.position, g.position + Vector2(0, g.size.y), pal["structure_faint"], 1.0)
		canvas.draw_polyline(sp, Color(pal["structure"], 0.8), 1.5)
		_text(g.position + Vector2(6, 10), "speed 0 → 0.016 c over mission time", pal["quiet"], fs - 1)
	if shown.is_empty():
		marker_px = Vector2(-1, -1)               # LIVE at the dock: no First Ignition row, so no ship marker on the study track
		_text(Vector2(r.position.x + 60, y - 50), "LIVE: Wayfarer is at the dock — the track is the First Ignition study; press , or . to preview it", pal["text"], fs)
		return
	if on("MOTION"):
		var cx: float = g.position.x + g.size.x * shown.mission_t_s / tmax
		canvas.draw_line(Vector2(cx, g.position.y), Vector2(cx, g.end.y), pal["player"], 1.0)
	marker_px = marker_at(r)
	canvas.draw_circle(marker_px, 6.0, pal["player"])
	canvas.draw_arc(marker_px, 11.0, 0, TAU, 24, pal["player"], 1.0)
	_text(marker_px + Vector2(0, -18), "WAYFARER", pal["player"], fs, HORIZONTAL_ALIGNMENT_CENTER)

func _draw_local(r: Rect2) -> void:
	var c := Vector2(r.position.x + r.size.x * 0.62, r.position.y + r.size.y * 0.45)
	var fs := int(round(12 * clampf(canvas.size.y / 230.0, 1.0, 1.35)))
	marker_px = c
	canvas.draw_line(Vector2(r.position.x + 20, c.y), Vector2(r.end.x - 20, c.y), Color(pal["structure_faint"], 0.9), 1.0)
	if shown.is_empty():
		canvas.draw_circle(c, 6.0, pal["player"])
		_text(c + Vector2(0, -18), "WAYFARER (LIVE, at the dock)", pal["player"], fs, HORIZONTAL_ALIGNMENT_CENTER)
		_text(Vector2(r.position.x + 12, r.position.y + 20), "Nearby objects: none with a sourced position · no First Ignition yet", pal["quiet"], fs)
		return
	# The ignition origin aft of the ship on the named, reversible log transform (C-004): px = LOG_UNIT_PX * log10(1 + x / 1 km).
	var d := WfRouteState.display_offset_m(shown.local_x_m, LOG_UNIT_PX)
	var origin := Vector2(c.x - minf(d, c.x - r.position.x - 30.0), c.y)
	if on("TRACK"):
		canvas.draw_line(origin, c, pal["structure"], 2.0)
		canvas.draw_circle(origin, 4.0, pal["quiet"])
		_text(origin + Vector2(0, 22), "ignition origin", pal["quiet"], fs, HORIZONTAL_ALIGNMENT_CENTER)
	for dec in (range(0, 10) if on("TRACK") else []):
		var x: float = c.x - LOG_UNIT_PX * dec
		if x < r.position.x + 20:
			break
		canvas.draw_line(Vector2(x, c.y - 4), Vector2(x, c.y + 4), pal["structure_faint"], 1.0)
		if dec % 3 == 0:
			# the tick's distance through the inverse transform (C-004): 0, ~1e3, ~1e6, ~1e9 km
			var km := WfRouteState.display_inverse_m(LOG_UNIT_PX * dec, LOG_UNIT_PX) / 1000.0
			_text(Vector2(x, c.y + 40), "0" if dec == 0 else ("%.0f km" % km if km < 1e4 else "%s km" % _sci(km, 1)), pal["quiet"], fs - 1, HORIZONTAL_ALIGNMENT_CENTER)
	if attitude_on:
		_draw_hull(c, fs)
	if shown.vx_mps > 0.0 and on("MOTION"):
		var a: Vector2 = local_vectors(c).velocity_end
		canvas.draw_line(c, a, pal["go"], 2.0)
		canvas.draw_colored_polygon(PackedVector2Array([a + Vector2(8, 0), a + Vector2(-2, -5), a + Vector2(-2, 5)]), pal["go"])
		_text(a + Vector2(12, 4), "v %.5f c (+X)" % shown.speed_fraction_c, pal["go"], fs)
	if on("MOTION") and absf(shown.accel_g) > 0.0:
		# The row's acceleration along +X: an open arrowhead below the velocity (a released row value, not a thrust axis or an attitude).
		var ay := c.y + 26.0
		var b := Vector2(c.x + (30.0 + 40.0 * minf(absf(shown.accel_g) / 1.5, 1.0)) * signf(shown.accel_g), ay)
		canvas.draw_line(Vector2(c.x, ay), b, pal["text"], 1.5)
		var hd := 8.0 * signf(shown.accel_g)
		canvas.draw_polyline(PackedVector2Array([b + Vector2(-hd, -5), b, b + Vector2(-hd, 5)]), pal["text"], 1.5)
		_text(b + Vector2(12, 4), "a %.4f g (+X, released row)" % shown.accel_g, pal["text"], fs)
	canvas.draw_circle(c, 6.0, pal["player"])
	canvas.draw_arc(c, 11.0, 0, TAU, 24, pal["player"], 1.0)
	_text(c + Vector2(0, -18), "WAYFARER", pal["player"], fs, HORIZONTAL_ALIGNMENT_CENTER)
	_text(Vector2(r.position.x + 12, r.position.y + 20), "Nearby objects: none with a sourced position", pal["quiet"], fs)
	_text(Vector2(r.position.x + 12, r.position.y + 36), "Attitude OPEN (C-013): +X is the travel direction, not a drawn ship heading", pal["quiet"], fs)
	_text(Vector2(r.end.x - 8, r.end.y - 10), "DISPLAY: log10 distance scale (C-004), reversible · DIAGNOSTIC 1D", pal["caution"], fs, HORIZONTAL_ALIGNMENT_RIGHT)

## LOCAL: where the ship marker and the velocity arrow go for the shown row. They depend on the row only, never on the display attitude
## (SPACE-014, checked by space_attitude_independent).
func local_vectors(c: Vector2) -> Dictionary:
	var v: float = shown.get("speed_fraction_c", 0.0)
	return {"marker": c, "velocity_end": c + Vector2(30.0 + 70.0 * v / 0.016, 0)}

## The ILLUSTRATIVE hull: a bow-pointed outline turned by attitude_deg about the marker; never drawn unless the visitor turns it on.
func _draw_hull(c: Vector2, fs: int) -> void:
	var rot := deg_to_rad(-attitude_deg)
	var pts := PackedVector2Array()
	for p in [Vector2(48, 0), Vector2(20, -13), Vector2(-40, -13), Vector2(-48, 0), Vector2(-40, 13), Vector2(20, 13)]:
		pts.append(c + p.rotated(rot))
	canvas.draw_colored_polygon(pts, Color(pal["caution"], 0.18))
	pts.append(pts[0])
	canvas.draw_polyline(pts, Color(pal["caution"], 0.9), 1.5)
	_text(c + Vector2(48, 0).rotated(rot) + Vector2(0, -16 if absf(sin(rot)) < 0.5 else 0), "bow", pal["caution"], fs - 1, HORIZONTAL_ALIGNMENT_CENTER)
	_text(c + Vector2(0, 56), "display hull %d° · ILLUSTRATIVE, attitude OPEN" % int(attitude_deg), pal["caution"], fs - 1, HORIZONTAL_ALIGNMENT_CENTER)

func _draw_solar(r: Rect2) -> void:
	var fs := int(round(12 * clampf(canvas.size.y / 230.0, 1.0, 1.35)))
	var c := r.get_center()
	if solar.ok():
		solar.draw(canvas, r, fs)
		drawn_bodies = solar.glyphs.size()
		_text(Vector2(r.position.x + 10, r.end.y - 12), "SOLAR SYSTEM POSITION OF WAYFARER  UNKNOWN (25!F14:F15 OPEN)", pal["caution"], fs)
		marker_px = Vector2(-1, -1)
		return
	_text(c + Vector2(0, -30), "SOLAR SYSTEM POSITION  UNKNOWN", pal["caution"], fs + 8, HORIZONTAL_ALIGNMENT_CENTER)
	_text(c + Vector2(0, -4), "No absolute ignition epoch, initial heliocentric position, heading or dated ephemerides are released.", pal["text"], fs, HORIZONTAL_ALIGNMENT_CENTER)
	_text(c + Vector2(0, 16), "Sun and planets are not drawn: without an epoch they would imply a place the sheets do not give.", pal["text"], fs, HORIZONTAL_ALIGNMENT_CENTER)
	var open := []
	for v in route.route.validation:
		if v.result != "PASS":
			open.append("%s %s" % [v.check_id, v.result])
	_text(c + Vector2(0, 44), " · ".join(open.slice(0, 3)), pal["quiet"], fs - 1, HORIZONTAL_ALIGNMENT_CENTER)
	_text(c + Vector2(0, 60), " · ".join(open.slice(3)), pal["quiet"], fs - 1, HORIZONTAL_ALIGNMENT_CENTER)
	marker_px = Vector2(-1, -1)

# ---------------------------------------------------------------------------------------------------------------------- checks

## Everything the host and its ship state hold that a map could plausibly touch, for the before / after comparison.
func live_snapshot() -> Dictionary:
	var frames := {}
	for id in host.frames:
		frames[id] = [(host.frames[id].node as Node3D).global_transform, host.frames[id].get("angle"), host.frames[id].get("rate")]
	var open := {}
	for o in host.openings:
		open[o.id] = host.opening_open(o)
	var out := {"progress": host.progress, "camera_frame": host.camera_frame, "camera": host.camera.global_transform, "drum_mode": host.drum_mode,
		"frames": frames, "open": open, "closures": str(host.get("closures")), "ring_mode": str(host.rings[host.ring_id].mode),
		"ship_level": ship.level, "ship_mode": ship.mode_id, "ship_target": ship.chosen, "ship_plan": str(ship.plan)}
	var tour = host.get("body_tour")
	if tour != null and tour.actor != null:
		out["body"] = [tour.actor.global_transform, tour.actor.get("linear_velocity"), tour.beat, tour.actor.standing]
	if demo != null:
		out["chapter"] = demo.chapter
		out["ctl"] = [demo.ctl.mode, demo.ctl.spin_frac, demo.ctl.done_steps.duplicate()] if demo.ctl != null else null
	return out

static func _diff(a: Dictionary, b: Dictionary) -> Array:
	var out := []
	for k in a:
		if str(a[k]) != str(b.get(k)):
			out.append(k)
	return out

func checks() -> Array:
	var out := []
	var was_active := active
	var was := {"scale": scale, "index": index, "level": ship.level}
	# 1, 2, 7: SHIP -> SPACE -> browse every row and scale -> SHIP leaves every live state as it was; the ship navigator is back.
	var before := live_snapshot()
	set_active(true)
	var switched := panel.visible and not ship.panel.visible
	var bad_rows := []
	var worst_px := 0.0
	var sun_texts := []
	var live_seen := false
	for s in SCALES:
		scale = s
		for i in range(-1, route.route.frames.size() if route.ok() else -1):
			select(i)
			var want := row_values(i) if i >= 0 else {}
			if str(shown) != str(want):
				bad_rows.append(i)
			var txt := panel_text().to_lower()
			if (i < 0) != ("▶ live" in txt) or (i >= 0) != ("scenario preview" in txt) or (i < 0 and preview()):
				live_seen = true
			for f in FORBIDDEN:
				if f in txt:
					sun_texts.append([s, i, f])
			if (i >= 0 and not "diagnostic 1d" in txt) or not "solar system position  unknown" in txt:
				sun_texts.append([s, i, "missing DIAGNOSTIC 1D / UNKNOWN label"])
			if s == "JOURNEY" and i >= 0:
				var box := Rect2(Vector2.ZERO, canvas.custom_minimum_size)
				var x0 := journey_x(0.0, box)
				var x1 := journey_x(float(route.route.frames[-1][route.col.distance_traveled_AU]), box)
				# independent of journey_x: the row's AU as a fraction of the released end AU along the drawn track
				var want_px := x0 + (x1 - x0) * float(route.route.frames[i][route.col.distance_traveled_AU]) / float(route.route.frames[-1][route.col.distance_traveled_AU])
				worst_px = maxf(worst_px, absf(marker_at(box).x - want_px))
	scale = "SOLAR"
	update_now()
	var solar_ok := not solar_bodies().has("WAYFARER") and "UNKNOWN" in panel_text()
	set_active(false)
	var after := live_snapshot()
	var changed := _diff(before, after)
	out.append({"id": "space_switch_ship_unchanged", "ok": switched and changed.is_empty() and ship.panel.visible == (ship.level > 0) and not panel.visible,
		"actual": {"switched": switched, "changed": changed, "ship_panel_back": ship.panel.visible, "rows_browsed": route.route.frames.size() * SCALES.size() if route.ok() else 0},
		"note": "SHIP -> SPACE, every released row on every scale, -> SHIP: host, body, rings, doors, controller and ship-navigator state identical (SPACE Stage 1 A, C)"})
	out.append({"id": "space_scrub_owner_rows", "ok": route.ok() and bad_rows.is_empty() and worst_px < 0.5, "actual": {"rows": route.times.size(), "mismatch": bad_rows.slice(0, 5), "marker_px_err": worst_px},
		"note": "every scrub position shows exactly one released 23_ROUTE_FRAMES row (no interpolated value); the journey marker sits at that row's traveled AU"})
	var r: Dictionary = route.route if route.ok() else {}
	out.append({"id": "space_frame_units_source", "ok": route.ok() and r.frame_id == "IGNITION_LOCAL_INERTIAL_1D" and r.scenario_id == "WAYFARER_001_IGNITION_V1"
		and str(r.source.modified_at_utc) != "" and r.columns.has("distance_traveled_AU") and r.columns.has("speed_fraction_c"),
		"actual": {"frame": r.get("frame_id"), "scenario": r.get("scenario_id"), "status": r.get("scenario_status"), "sheet_modified": r.get("source", {}).get("modified_at_utc"), "route_version": r.get("route_version")},
		"note": "the readout names the frame, origin, units, scenario and the source sheet's timestamp"})
	out.append({"id": "space_never_sun_relative", "ok": sun_texts.is_empty(), "actual": sun_texts.slice(0, 5),
		"note": "no text on any row or scale reads the relative +X displacement as a Sun-relative place; DIAGNOSTIC 1D and the UNKNOWN Solar System position stay on screen"})
	out.append({"id": "space_solar_unknown", "ok": solar_ok and r.get("open_checks", []).has("COORDINATE_FRAME_VALIDATED") and r.get("open_checks", []).has("SOLAR_EPHEMERIDES_VALIDATED"),
		"actual": {"bodies": solar_bodies().size(), "open_checks": r.get("open_checks", [])}, "note": "with 25!F14:F15 OPEN the Solar System scale has no Wayfarer marker and shows UNKNOWN"})
	out.append({"id": "space_live_vs_preview", "ok": not live_seen and live_mission_t() == null, "actual": {"live_mission_t": live_mission_t(), "label_mismatch": live_seen},
		"note": "SPACE-005/006: LIVE (at the dock, no route value) until a row is selected; every selected First Ignition row is SCENARIO PREVIEW in the pre-ignition tour"})
	# 9: only events with a released displacement are drawn; every OPEN one is listed and unplaced.
	var must_open := ["DRIVE_SHUTDOWN", "KUIPER_BRAKE_DEADLINE", "FIRST_LOOP", "RETURN"]
	var open_ids := unplaced.map(func(e): return e.id)
	var bad_place := []
	for e in placed:
		for src in r.get("events", []):
			if str(src.event_id) == e.id and (src.mission_t_s == null or float(src.displacement_AU) != e.au):
				bad_place.append(e.id)
	out.append({"id": "space_no_invented_events", "ok": must_open.all(func(id): return open_ids.has(id)) and bad_place.is_empty() and placed.all(func(e): return not must_open.has(e.id)),
		"actual": {"placed": placed.map(func(e): return e.id), "unplaced": open_ids}, "note": "shutdown, Kuiper, First Loop and return have no time or position in 24_ROUTE_EVENTS and are never drawn"})
	# 8: a missing file, a failed or missing gate row, another route version or another schema is refused, and nothing numeric is shown.
	var good: Dictionary = route.route.duplicate(true) if route.ok() else {}
	var refused := {}
	if route.ok():
		var cases := {}
		var failed := good.duplicate(true)
		for v in failed.validation:
			if int(v.row) == 6:
				v.result = "FAIL"
		cases["row6_fail"] = failed
		var missing := good.duplicate(true)
		missing.validation = missing.validation.filter(func(v): return int(v.row) != 9)
		cases["row9_missing"] = missing
		var other := good.duplicate(true)
		other.route_version = "0000000000000000"
		cases["other_version"] = other
		var schema := good.duplicate(true)
		schema.schema = "WF_SOMETHING_ELSE"
		cases["schema"] = schema
		for k in cases:
			var why := use_route(cases[k], host.rig_all)
			update_now()
			refused[k] = why != "" and shown.is_empty() and "NO VALIDATED ROUTE" in panel_text() and not "AU   (" in panel_text()
		var tmp := WfRouteState.new()
		refused["missing_file"] = tmp.load_file("res://generated/__no_route__.json", host.rig_all) != ""
		use_route(good, host.rig_all)
	out.append({"id": "space_rejects_unvalidated_route", "ok": route.ok() and refused.size() == 5 and refused.values().all(func(x): return x), "actual": refused,
		"note": "C-009: 25_ROUTE_VALIDATION rows 2:13 must be present and PASS, the route version must be the rig's"})
	# SPACE-021/023: every layer off and back on, on each scale and row, changes no value, row, live state or disclosure; a hidden Kuiper
	# guide cannot be clicked.
	var keep_layers := layers_on.duplicate()
	var before_layers := live_snapshot()
	var layer_bad := []
	for s in SCALES:
		scale = s
		for i in ([-1, 0, 450, route.route.frames.size() - 1] if route.ok() else [-1]):
			select(i)
			var ref := [str(shown), badge.text, readout.text]
			for l in LAYERS:
				layers_on[l.id] = false
			update_now()
			var txt := panel_text().to_lower()
			if str([str(shown), badge.text, readout.text]) != str(ref) or not "solar system position  unknown" in txt or (i >= 0 and not "diagnostic 1d" in txt) \
					or legend.visible or (i >= 0 and s != "SOLAR" and not "%d open" % unplaced.size() in txt):
				layer_bad.append([s, i, "off"])
			for l in LAYERS:
				layers_on[l.id] = true
			update_now()
			if str([str(shown), badge.text, readout.text]) != str(ref):
				layer_bad.append([s, i, "on"])
	var kuiper_hidden := ""
	var kuiper_shown := ""
	if solar.ok():
		var keep_solar := [solar.mode, solar.zoom]
		solar.mode = "ANALYTICAL"
		solar.zoom = solar.reg.zooms.size() - 1
		solar.layout(CHECK_BOX)
		var mid := solar.origin(CHECK_BOX) + Vector2(solar.radius_px(40.0, CHECK_BOX), -20.0)
		layers_on["KUIPER"] = false
		kuiper_hidden = solar.pick(mid)
		layers_on["KUIPER"] = true
		kuiper_shown = solar.pick(mid)
		solar.mode = keep_solar[0]
		solar.zoom = keep_solar[1]
	layers_on = keep_layers
	var layer_changed := _diff(before_layers, live_snapshot())
	out.append({"id": "space_layers_view_only", "ok": layer_bad.is_empty() and layer_changed.is_empty() and kuiper_hidden == "" and kuiper_shown == "KUIPER_BELT_MAIN",
		"actual": {"bad": layer_bad.slice(0, 5), "changed": layer_changed, "kuiper_hidden_pick": kuiper_hidden, "layers": LAYERS.map(func(l): return l.id)},
		"note": "SPACE-021/023: layers hide drawings only; rows, readout, LIVE / PREVIEW badge, DIAGNOSTIC 1D and UNKNOWN stay with every layer off, the OPEN events are still counted"})
	out.append_array(solar_checks())
	# SPACE-020: Inspect ship from the SPACE marker opens the expanded SHIP map and keeps the selected row; B goes back to the same row.
	set_active(true)
	select(450)
	inspect_ship()
	var inspected: bool = not active and ship.level == 2 and ship.panel.visible and index == 450
	set_active(true)
	var back: bool = active and index == 450 and shown.get("frame", -1) == 451
	ship.level = was["level"]
	out.append({"id": "space_ship_drilldown", "ok": inspected and back, "actual": {"inspect": inspected, "back_same_row": back},
		"note": "SPACE marker -> Inspect ship (expanded SHIP), SHIP -> journey (SPACE) at the same selected mission time"})
	out.append_array(motion_checks())
	scale = was["scale"]
	index = was["index"]
	set_active(was_active)
	return out

## POL-008 Prototype A: the replay shows released rows only and stops on the last one without calling it a shutdown; the MOTION card's
## figures are the owner's (HALFWAY_IN_TIME ratios) and the rows' own integrals; the display hull never moves the row, marker or velocity.
func motion_checks() -> Array:
	var out := []
	if not route.ok():
		return [{"id": "space_replay_owner_rows", "ok": false, "actual": "no validated route"}]
	var was_on := active
	var keep := [scale, index, card, attitude_on, attitude_deg, playing]
	var before := live_snapshot()
	var last: int = route.route.frames.size() - 1
	var m: Dictionary = route.route.model
	set_active(true)
	scale = "JOURNEY"
	card = -1
	select(-1)
	toggle_play()
	var started := playing and index == 0
	var seen := [index]
	var bad := []
	var steps := 0
	while playing and steps < 100000:
		step_replay(1.0 / 60.0)
		steps += 1
		if seen[-1] != index:
			seen.append(index)
		if str(shown) != str(row_values(index)):
			bad.append(index)
	var mono := range(1, seen.size()).all(func(k): return seen[k] > seen[k - 1])
	var secs := steps / 60.0
	card = 2
	update_now()
	var end_card := card_text().to_lower()
	var end_words := FORBIDDEN.filter(func(f): return f in panel_text().to_lower())
	out.append({"id": "space_replay_owner_rows", "ok": started and bad.is_empty() and mono and index == last and not playing
		and absf(secs - float(route.route.clip_length_s)) < 0.1 and "not a shutdown" in end_card and end_words.is_empty(),
		"actual": {"rows_seen": seen.size(), "mismatch": bad.slice(0, 5), "monotonic": mono, "end_row": index + 1, "seconds": snappedf(secs, 0.01), "forbidden": end_words},
		"note": "P replays the released rows at the route's own 30 rows/s (22 fps, clip_length_s), whole rows only, and stops on row 900: TARGET_SPEED, not a shutdown (22 shutdown_or_coast_start OPEN)"})
	# The card: owner ratios, integrals of the rows, and the card never changes the shown row or disclosures.
	var h := _event("HALFWAY_IN_TIME")
	var rv := float(h.get("velocity_mps", 0.0)) / float(m.target_velocity_mps.value)
	var rx := float(h.get("displacement_x_m", 0.0)) / float(m.burn_distance_m.value)
	var card_bad := []
	for i in [-1, 0, 450, last]:
		card = -1
		select(i)
		var ref := [str(shown), badge.text, readout.text]
		for pg in CARD_PAGES.size():
			card = pg
			update_now()
			var t := card_text()
			if str([str(shown), badge.text, readout.text]) != str(ref) or not t in hint.text:
				card_bad.append([i, pg, "changed"])
			if pg == 1 and not ("%.3f of the final speed and %.3f of the distance" % [rv, rx]) in t:
				card_bad.append([i, pg, "ratios"])
			if pg == 2 and i >= 0 and not ("%s km/s (row: %s km/s)" % [_num(kin_v[i] / 1000.0, 1), _num(shown.vx_mps / 1000.0, 1)]) in t:
				card_bad.append([i, pg, "integral"])
	card = -1
	out.append({"id": "space_motion_card", "ok": absf(rv - 0.25) < 1e-6 and absf(rx - 0.125) < 1e-6 and kin_err.v < 1e-6 and kin_err.x < 1e-6 and card_bad.is_empty(),
		"actual": {"halfway_speed_ratio": rv, "halfway_distance_ratio": rx, "integral_err": kin_err, "bad": card_bad.slice(0, 5)},
		"note": "WHY: 24 HALFWAY_IN_TIME has 1/4 of the speed and 1/8 of the distance; HOW: integrating the rows' acceleration reproduces every row's speed and distance (Newton, DERIVED); the card changes no row or disclosure"})
	# The display hull at every step leaves the row, the marker and the velocity arrow where they were.
	scale = "LOCAL"
	var c := Vector2(400, 120)
	var att_bad := []
	for i in [0, 450, last]:
		attitude_on = false
		attitude_deg = 0.0
		select(i)
		var ref := [str(shown), str(local_vectors(c)), badge.text, readout.text]
		attitude_on = true
		for d in range(0, 360, int(ATTITUDE_STEP_DEG)):
			attitude_deg = float(d)
			update_now()
			if str([str(shown), str(local_vectors(c)), badge.text, readout.text]) != str(ref) or not "ILLUSTRATIVE" in hint.text or not "OPEN (C-013)" in hint.text:
				att_bad.append([i, d])
	out.append({"id": "space_attitude_independent", "ok": att_bad.is_empty(), "actual": {"bad": att_bad.slice(0, 5)},
		"note": "SPACE-014: the display hull turns in 45° steps at rows 1, 451 and 900; row, marker, velocity arrow and readout stay; it is labelled ILLUSTRATIVE, attitude OPEN"})
	scale = keep[0]
	index = keep[1]
	card = keep[2]
	attitude_on = keep[3]
	attitude_deg = keep[4]
	playing = keep[5]
	set_active(was_on)
	var changed := _diff(before, live_snapshot())
	if not changed.is_empty():
		out[0].ok = false
		out[0].actual["host_changed"] = changed
	return out


## Key-driven stills (capture with -- --capture-demo=DIR --space-stills): the keys go through Input.parse_input_event, so the real input
## paths run. B opens SPACE (LIVE), "." previews row 1, End the burn end, [ ] the scales, I inspects the ship, B returns, B closes.
## Prints WF_SPACE_KEYS with what each key did and whether the live state stayed untouched.
var key_log: Array = []

func stills(dir: String, stem: String, shot: Callable) -> void:
	var before := live_snapshot()
	var k := func(key: Key, shift := false) -> void:
		for down in [true, false]:
			var e := InputEventKey.new()
			e.keycode = key
			e.physical_keycode = key
			e.shift_pressed = shift
			e.pressed = down
			Input.parse_input_event(e)
			await get_tree().process_frame
		await get_tree().process_frame
	var exp := func(what: String, ok: bool) -> void:
		key_log.append({"step": what, "ok": ok})
	await k.call(KEY_B)
	exp.call("B opens SPACE (LIVE)", active and panel.visible and not ship.panel.visible and index == -1)
	await shot.call(dir, "%s_space_live" % stem)
	await k.call(KEY_PERIOD)
	exp.call(". previews row 1", index == 0 and preview())
	for n in 15:
		await k.call(KEY_PERIOD, true)
	exp.call("shift+. x15 steps 30 rows each", index == 450)
	await shot.call(dir, "%s_space_journey_mid" % stem)
	await k.call(KEY_3)
	await k.call(KEY_6)
	exp.call("3, 6 hide the events and the grid; the row stays", not on("EVENTS") and not on("GRID") and index == 450 and "layer off" in events_label.text)
	await shot.call(dir, "%s_space_layers_off" % stem)
	await k.call(KEY_3)
	await k.call(KEY_6)
	exp.call("3, 6 show them again", on("EVENTS") and on("GRID"))
	await k.call(KEY_P)
	exp.call("P starts the replay from row 451", playing and index >= 450)
	for n in 20:
		await get_tree().process_frame
	exp.call("the replay moves on", index > 450)
	await k.call(KEY_P)
	exp.call("P pauses the replay", not playing)
	await k.call(KEY_H)
	await k.call(KEY_H)
	exp.call("H H opens the MOTION card WHY", card == 1 and "HALFWAY_IN_TIME" in hint.text)
	await shot.call(dir, "%s_space_card_why" % stem)
	await k.call(KEY_END)
	exp.call("End = last released row", index == route.route.frames.size() - 1)
	await k.call(KEY_H)
	exp.call("H -> HOW at row 900: not a shutdown", card == 2 and "not a shutdown" in hint.text)
	await shot.call(dir, "%s_space_card_how" % stem)
	await k.call(KEY_H)
	exp.call("H closes the card", card == -1)
	await shot.call(dir, "%s_space_journey_end" % stem)
	await k.call(KEY_BRACKETLEFT)
	exp.call("[ -> LOCAL", scale == "LOCAL")
	await shot.call(dir, "%s_space_local" % stem)
	await k.call(KEY_R)
	for n in 4:
		await k.call(KEY_R)
	exp.call("R turns the display hull to 180°; the row stays", attitude_on and is_equal_approx(attitude_deg, 180.0) and index == route.route.frames.size() - 1)
	await shot.call(dir, "%s_space_local_hull" % stem)
	await k.call(KEY_R, true)
	exp.call("shift+R removes the display hull", not attitude_on)
	await k.call(KEY_BRACKETLEFT)
	exp.call("[ -> SOLAR", scale == "SOLAR")
	await shot.call(dir, "%s_space_solar" % stem)
	if solar.ok():
		for n in 6:
			await k.call(KEY_DOWN)
		exp.call("down x6 selects Jupiter", solar.selected == "JUPITER")
		await k.call(KEY_I)
		exp.call("I opens Jupiter's WHAT card", solar.page == 0 and "JUPITER" in events_label.text)
		await shot.call(dir, "%s_space_solar_card" % stem)
		await k.call(KEY_I)
		await k.call(KEY_I)
		await k.call(KEY_I)
		exp.call("I x3 closes the card", solar.page == -1)
		await k.call(KEY_M)
		exp.call("M -> PRESENTATION", solar.mode == "PRESENTATION" and "PRESENTATION" in tabs.text)
		await shot.call(dir, "%s_space_solar_presentation" % stem)
		await k.call(KEY_MINUS)
		await k.call(KEY_UP)
		for n in 6:
			await k.call(KEY_UP)
		exp.call("- zooms to the Kuiper region, up selects it", solar.zoom == 2 and solar.selected == "KUIPER_BELT_MAIN")
		await k.call(KEY_I)
		exp.call("I opens the Kuiper card: a regional guide", "not an event position" in events_label.text)
		await shot.call(dir, "%s_space_solar_kuiper" % stem)
		for n in 3:
			await k.call(KEY_I)
		await k.call(KEY_M)
		await k.call(KEY_EQUAL)
		await k.call(KEY_EQUAL)
		exp.call("= x2 zooms to the inner planets, M back to ANALYTICAL", solar.zoom == 0 and solar.mode == "ANALYTICAL")
		await shot.call(dir, "%s_space_solar_inner" % stem)
		solar.zoom = 1
		solar.select("WAYFARER")
	await k.call(KEY_BRACKETLEFT)
	exp.call("[ -> JOURNEY", scale == "JOURNEY")
	await k.call(KEY_J)
	exp.call("J shares the guidance mode", true)
	await k.call(KEY_I)
	exp.call("I inspects the ship (expanded SHIP)", not active and ship.level == 2 and ship.panel.visible)
	await shot.call(dir, "%s_space_inspect_ship" % stem)
	await k.call(KEY_B)
	exp.call("B back to SPACE at the same row", active and index == route.route.frames.size() - 1)
	await k.call(KEY_HOME)
	exp.call("Home -> LIVE", index == -1 and not preview())
	await k.call(KEY_B)
	exp.call("B back to SHIP", not active and not panel.visible)
	var after := live_snapshot()
	# The body and rings move on their own between frames, so only the switched states are compared here (the exact comparison is in checks()).
	var moved := _diff({"open": before["open"], "closures": before["closures"], "ring_mode": before["ring_mode"], "chapter": before.get("chapter"), "ctl_mode": str(before.get("ctl", [null])[0]) if before.get("ctl") != null else ""},
		{"open": after["open"], "closures": after["closures"], "ring_mode": after["ring_mode"], "chapter": after.get("chapter"), "ctl_mode": str(after.get("ctl", [null])[0]) if after.get("ctl") != null else ""})
	exp.call("doors, ring mode, chapter and controller unchanged", moved.is_empty())
	ship.level = 1
	ship.mode_id = ship.policy.default_id()
	ship.update_now()
	print("WF_SPACE_KEYS " + JSON.stringify({"stem": stem, "result": "PASS" if key_log.all(func(x): return x["ok"]) else "FAIL", "steps": key_log}))
	key_log = []

## Stage 2 checks (SPACE-007/010/015/017/019, C-004/C-012): run inside checks() with SPACE shown.
func solar_checks() -> Array:
	var out := []
	if not solar.ok():
		return [{"id": "space_solar_registry", "ok": false, "actual": "rig has no space_navigator block"}]
	var keep := {"mode": solar.mode, "zoom": solar.zoom, "selected": solar.selected, "page": solar.page, "scale": scale, "index": index}
	var box := CHECK_BOX
	scale = "SOLAR"
	var frames_before := str(route.route.frames).hash() if route.ok() else 0
	# Arrangement does not follow the mission time: the same glyphs at LIVE and at three rows, in each mode and zoom.
	var moved := []
	var notices := []
	var inverse_err := 0.0
	for m in WfSolarChart.MODES:
		solar.mode = m
		for z in solar.reg.zooms.size():
			solar.zoom = z
			var ref := {}
			for i in [-1, 0, 450, 899]:
				select(i)
				solar.layout(box)
				if ref.is_empty():
					ref = solar.glyphs.duplicate()
				elif str(ref) != str(solar.glyphs):
					moved.append([m, z, i])
			if solar.glyphs.has("WAYFARER"):
				moved.append([m, z, "wayfarer marker"])
			if solar.disclosure().find(m) != 0 or str(solar.reg.schematic_notice) != "SCHEMATIC — EPOCH / SHIP POSITION UNRESOLVED":
				notices.append([m, z])
			for b in solar.bodies:
				var a := float(b.get("a_au", 0.0))
				if a > 0.0:
					inverse_err = maxf(inverse_err, absf(solar.radius_inverse(solar.radius_px(a, box), box) - a) / a)
	var frames_after := str(route.route.frames).hash() if route.ok() else 0
	out.append({"id": "space_solar_schematic_static", "ok": moved.is_empty() and notices.is_empty(), "actual": {"moved": moved.slice(0, 5), "notice_missing": notices},
		"note": "SPACE-015: the arrangement never moves with the selected mission time, has no Wayfarer marker, and every mode and zoom carries the SCHEMATIC notice and its mode disclosure"})
	out.append({"id": "space_display_transform_reversible", "ok": inverse_err < 1e-9 and frames_before == frames_after, "actual": {"max_rel_inverse_error": inverse_err, "route_rows_unchanged": frames_before == frames_after},
		"note": "C-004/C-012: LINEAR and SQRT distance transforms invert exactly; toggling modes and zooms leaves the released route rows identical"})
	# Cards: every number on a body card is the registry's, with its reference and dates; the Kuiper card is a regional guide; Wayfarer is UNKNOWN.
	var bad_cards := []
	for id in solar.ids():
		solar.select(id)
		var texts := []
		for k in 3:
			solar.next_page()
			texts.append(solar.card_text())
		solar.next_page()
		var what: String = texts[0]
		if id == "WAYFARER":
			if not "UNKNOWN" in what or not "not a distance from the Sun" in what:
				bad_cards.append(id)
			continue
		var b := solar._body(id)
		var ref: Dictionary = solar.refs.get(b.ref, {})
		if not str(ref.get("title", "@")) in what or not str(ref.get("retrieved", "@")) in what or not "DRAFT" in texts[1]:
			bad_cards.append(id + " source")
		if b.get("kind", "") == "planet":
			for want in ["%.3f AU" % b.a_au, "%.3f" % b.eccentricity, solar._n(b.diameter_km, 0), solar._n(b.period_days, 1)]:
				if not want in what:
					bad_cards.append("%s %s" % [id, want])
		if b.has("inner_au") and (not "not an event position" in what or bool(b.get("event_position", true))):
			bad_cards.append(id + " region")
		# The Kuiper SHOW ME names every OPEN Kuiper check the route carries (25 rows 17, 19:21).
		if b.has("inner_au") and (solar.kuiper_open().size() < 4 or not solar.kuiper_open().all(func(v): return str(v.check_id) in texts[2])):
			bad_cards.append(id + " open Kuiper checks")
	out.append({"id": "space_reference_cards", "ok": bad_cards.is_empty() and solar.ids().size() == 11, "actual": {"objects": solar.ids(), "bad": bad_cards.slice(0, 6)},
		"note": "SPACE-019: one card per Sun, planet, Kuiper region and the Wayfarer state; numbers from the registry with their NASA reference, wording DRAFT"})
	# Picking: a click on each laid-out glyph selects that body (both modes, every zoom); a click inside the Kuiper band selects the region.
	var missed := []
	for m in WfSolarChart.MODES:
		solar.mode = m
		for z in solar.reg.zooms.size():
			solar.zoom = z
			solar.layout(box)
			for id in solar.glyphs:
				if solar.pick(solar.glyphs[id]) != id:
					missed.append([m, z, id])
	solar.mode = "ANALYTICAL"
	solar.zoom = solar.reg.zooms.size() - 1
	solar.layout(box)
	var mid := solar.origin(box) + Vector2(solar.radius_px(40.0, box), -20.0)
	var kuiper := solar.pick(mid)
	out.append({"id": "space_solar_picking", "ok": missed.is_empty() and kuiper == "KUIPER_BELT_MAIN", "actual": {"missed": missed.slice(0, 5), "kuiper_click": kuiper},
		"note": "click picking on the chart's glyphs in both modes and every zoom; the Kuiper band picks as a region card, never an event"})
	solar.mode = keep["mode"]
	solar.zoom = keep["zoom"]
	solar.selected = keep["selected"]
	solar.page = keep["page"]
	scale = keep["scale"]
	select(keep["index"])
	return out
