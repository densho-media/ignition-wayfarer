class_name WfDemo01
extends Node
## Wayfarer Integrated Demonstrator 01 (SIMULATION_ONLY): one continuous run that joins the parts already built and checked:
##  EXTERIOR   the DOCKED ship from outside (static REP_PROXY export);
##  ENTRY      the review rail from the outer hatch through the airlock to the stationary spine (RT-004 closures);
##  MICROGRAVITY  the crew-physics body in the real trunk: grip, push-off, drift, catch (body_tour SPINE beat, PHYS-001);
##  MODE       DOCKED -> COAST in the owner's step order (WfModeController, 46 DYN-026 / 15 CREW-MODE-004); the rings follow the controller;
##  TRANSFER   the body in physics from the trunk through the spine port into the despun drum, restrained on a chord while the drum syncs with
##             ring A (DYN-027 gate), feet first out through the drum door and the crew tube's elbows to the top of its radial run (rig
##             dynamics.stages.access; the rail follows the body and keeps the closures' sequence);
##  DESCENT    the same body climbs down the real tube and landing-well rungs hand over hand at the review pace (LADDER technique, PROTOTYPE)
##             and steps onto the landing-well deck (body_tour TUBE beat);
##  GRAVITY    in the same physics world: the body walks from the well into ring A's aisle in spin gravity, and the Coriolis drop.
##  ARRIVAL    M7: the review camera at ring A sector 1's habitat stop with the staged pair: the production section's destination.
##  INSPECT    M7: back at the entry chamber stop, the production layer (manifest v2, layer PRODUCTION) switched off and on in turn over the
##             same engineering geometry,
##             with its assemblies and maturity (manifest production.maturity, L4_VISUAL_ACCEPTED since 2026-10-20); Esc opens the inspector for picking. Training route only: ring A is
##             no certified rescue route (15!A221) and the transfer closures are PROTOTYPE (I5/Q46 OPEN).
## The chapters, camera paths, auto actions and the ramp time-lapse are display choices (PROTOTYPE); no transfer timing, procedure or
## interlock is released (transition timing HOLD, FLIGHT_EVA HOLD). Godot holds no spacecraft facts: everything comes from the rig/manifest.
## Keys: Enter next chapter · P pause/resume the auto camera · A autoplay of the body actions · O mark an occupant not secured (MODE) ·
## the body keys of the body tour in MICROGRAVITY and GRAVITY · F3 hologram style (WEB-003: standard, subsystem, engine; presentation
## only, WfHoloStyle) · Esc inspector.

const CHAPTERS := ["EXTERIOR", "ENTRY", "MICROGRAVITY", "MODE", "TRANSFER", "DESCENT", "GRAVITY", "ARRIVAL", "INSPECT"]
const ARRIVAL_S := 6.0          # PROTOTYPE display: seconds at the habitat stop
const INSPECT_FLIP_S := 2.5     # PROTOTYPE display: seconds per production-layer state (off / on) in INSPECT
const INSPECT_S := 10.0
const EXTERIOR_S := 10.0        # PROTOTYPE display: one exterior orbit segment, seconds
const TIMELAPSE := 90.0         # PROTOTYPE display: simulated seconds of the ring ramp per real second (the 1800 s study ramp in 20 s)
const SPINE_VIEW := Vector3(2.6, 0.45, -0.3)     # PROTOTYPE display: camera offset from the body (body_tour capture offsets)
const RING_VIEW := Vector3(0.7, -0.6, -1.3)       # body_tour aisle capture offset
const TUBE_VIEW := Vector3(0.0, -1.8, 0.65)       # PROTOTYPE display: inboard of the body inside the tube bore, looking down the ladder
const WELL_VIEW := Vector3(0.6, -0.7, 1.8)        # PROTOTYPE display: from the aisle side, looking back at the body leaving the well
const HAND_FREE_N := 1.0         # IMPLEMENTATION: hand loads below this count as a free drift (no grip needed)
const ACCESS_VIEW := Vector3(0.9, 0.35, 0.55)     # PROTOTYPE display: beside the body in the trunk and drum (V; behind the body by default)
const ORBIT_ARC := 1.1          # PROTOTYPE display: radians of the exterior orbit
const RECORD_TAIL_S := 1.5      # IMPLEMENTATION: display seconds held after INSPECT completes, so a recording writes its last frames
const RECORD_TIMEOUT_S := 900.0 # IMPLEMENTATION: watchdog (display seconds); a recording that has not completed INSPECT by then fails

var host                         # boarding.gd: rail, mechanisms, body tour
var chapter := -1
var t := 0.0
var paused := false
var autoplay := false
var goal_done := false            # the current chapter's goal is reached (U05 review guide)
var auto_next := true             # autoplay also moves to the next chapter; off under the review guide, where Enter does it
var ctl: WfModeController = null
var hud := Label.new()
const SIDE_PANEL_PX := 330.0               # boarding.gd's stop panel: offset_left -330 from the right edge
const HUD_MAX_W := 900.0
# The stop list marks where the body is in the body chapters (display only; boarding.gd marks the route rail's stop, which lags the body).
const CHAPTER_STOP := {"MICROGRAVITY": "spine", "MODE": "spine", "TRANSFER": "transfer", "DESCENT": "habitat", "GRAVITY": "habitat",
	"ARRIVAL": "habitat", "INSPECT": "entry"}
var production_nodes: Array = []          # M7: imported meshes of the production layer (WfProductionLayer metadata)
var production_flips := 0
var holo := WfHoloStyle.new()             # WEB-003: the hologram styles over the ship (instance overrides only)
var layer := CanvasLayer.new()
var sun := DirectionalLight3D.new()
var centre := Vector3.ZERO
var radius := 200.0
var auto_step := 0
var driven := false
# DYN-027 rotary vestibule on the drum: the owner interlock gates the port gate (STATIONARY side) and the drum door (RING side) and
# the drum's speed changes. Pressure equalization is a PROTOTYPE display input (the threshold is OPEN, PRESS-004); the occupant counts
# as restrained while the camera rides the drum frame (PROTOTYPE).
var vest: WfVestibule = null
var vest_refused: Array = []              # a check or capture steps the chapters itself
var log: Array = []
var access_log: Array = []                # TRANSFER: per step the vestibule ramp, the restraint and the body's place on the line
# Automated recording (-- --autoplay --record-exit): once INSPECT completes, the run holds RECORD_TAIL_S, prints WF_DEMO_RECORDING and
# quits (exit 0), so Movie Maker finalizes the file; the watchdog (--record-timeout=<s>) quits with exit 1 and a FAIL line instead.
# Interactive play (no --record-exit) keeps running after the last chapter until the user exits.
var record_exit := false
var record_timeout := RECORD_TIMEOUT_S
var record_t := 0.0
var record_done_t := -1.0
var navigator: WfShipNavigator = null     # SNAV-001 Ship Navigator (corner locator, route, systems card); -- --no-navigator leaves it out
var details := false                      # MOB-001 compact layout: the engineering readouts (body HUD, key line) shown on request

func setup(h) -> void:
	host = h
	for arg in OS.get_cmdline_user_args():
		if arg == "--record-exit":
			record_exit = true
		elif arg.begins_with("--record-timeout="):
			record_timeout = float(arg.trim_prefix("--record-timeout="))
	layer.layer = 5
	hud.position = Vector2(28, 92)
	hud.add_theme_color_override("font_outline_color", Color.BLACK)
	hud.add_theme_constant_override("outline_size", 4)
	hud.add_theme_font_size_override("font_size", 15)
	hud.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	hud.custom_minimum_size = Vector2(HUD_MAX_W, 0)
	layer.add_child(hud)
	add_child(layer)
	# Inspection illumination for the exterior chapters (display, not a sourced sun direction or attitude).
	sun.rotation = Vector3(-0.6, 0.8, 0.0)
	sun.visible = false
	add_child(sun)
	var aabb := AABB()
	var first := true
	for mi in host.ship.find_children("*", "MeshInstance3D", true, false):
		var box: AABB = mi.global_transform * mi.get_aabb()
		aabb = box if first else aabb.merge(box)
		first = false
	centre = aabb.get_center()
	host.help_label.visible = false
	holo.setup(host.ship, host.world.environment)
	var bt: WfBodyTour = host.ensure_body_tour()
	bt.hud.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	# Readable over the bright interiors: a translucent backing behind both left texts (display only).
	var back := StyleBoxFlat.new()
	back.bg_color = Color(0.0, 0.0, 0.0, 0.42)
	back.set_content_margin_all(6.0)
	hud.add_theme_stylebox_override("normal", back)
	bt.hud.add_theme_stylebox_override("normal", back)
	# The stop card stops short of the stop panel, as the left texts do.
	host.bottom_panel.offset_right = -(SIDE_PANEL_PX + 16.0)
	radius = aabb.size.length() * 0.62
	if host.rig_all.has("navigator") and not "--no-navigator" in OS.get_cmdline_user_args():
		navigator = WfShipNavigator.new()
		add_child(navigator)
		navigator.setup(host, self)
	# MOB-001: the touch layer asks this chapter which controls can be used now.
	WfInput.touch_provider = touch_state
	tree_exiting.connect(func(): WfInput.touch_provider = Callable(); WfInput.release_touch())
	if WfInput.compact():
		hud.add_theme_font_size_override("font_size", 13)
		bt.hud.add_theme_font_size_override("font_size", 12)

## MOB-001: the touch controls of the chapter now (wf_touch.gd). Only actions whose handler already exists in this scene, with the same
## checks as their keys; nothing here moves a body, a door or the rings by itself.
## move: "2d" walking on a deck, "1d" along the transfer line, the rungs or the rail; "" weightless or guided (the stick would add no force).
func touch_state() -> Dictionary:
	if chapter < 0:
		return {}
	var name: String = CHAPTERS[chapter]
	var tour: WfBodyTour = host.body_tour
	var body := tour != null and tour.active and tour.actor != null
	var acts := []
	var move := ""
	var pause := ["demo.pause", "Resume" if paused else "Pause", "nav"]
	match name:
		"EXTERIOR", "ARRIVAL":
			acts.append(pause)
		"ENTRY":
			move = "1d"
			acts.append(pause)
		"MODE":
			acts.append(pause)
			if ctl != null:
				acts.append(["demo.occupants", "Fault: occupant" if ctl.occupants_securable else "Secure occupant", "nav"])
		"MICROGRAVITY":
			if body:
				if tour.actor.grip == null:
					acts.append(["player.grab", "Grab", "primary_game"])
				else:
					acts.append(["player.push", "Push off", "primary_game"])
					acts.append(["player.release", "Release", "game"])
		"TRANSFER", "DESCENT":
			move = "1d" if body else ""
		"GRAVITY":
			move = "2d" if body else ""
			if body and tour.tool != null:
				acts.append(["body.drop_tool", "Drop object", "game"])
		"INSPECT":
			acts.append(["demo.pause", "Resume" if paused else "Hold layer on", "nav"])
	if body and name in ["MICROGRAVITY", "TRANSFER", "DESCENT", "GRAVITY"]:
		acts.append(["body.view", "View", "nav"])
		acts.append(["demo.autoplay", "Auto: on" if autoplay else "Auto", "nav"])
	if chapter < CHAPTERS.size() - 1:
		acts.append(["ui.confirm", "Next" if goal_done else "Skip", "primary" if goal_done else "nav"])
	var util := []
	if navigator != null:
		util.append(["ship.map", "Map"])
		util.append(["ship.card", ["Systems", "Why", "Show me", "Close"][navigator.card_page + 1]])
	util.append(["touch.info", "Details" if not details else "Less"])
	if holo.available():
		util.append(["demo.holo", {"standard": "Holo", "subsystem": "Engine", "engine": "Solid"}[holo.style]])
	return {"move": move, "look": camera_free() or body, "actions": acts, "utility": util,
		"local": {"touch.info": func(): details = not details}, "probe": touch_probe,
		"panels": [hud, host.body_tour.hud if host.body_tour != null else null] + ([navigator.panel, navigator.card] if navigator != null else [])}

## The chapter state a browser check reads (-- --touch-probe).
func touch_probe() -> Dictionary:
	var tour: WfBodyTour = host.body_tour
	var out := {"chapter": CHAPTERS[chapter] if chapter >= 0 else "", "goal_done": goal_done, "paused": paused, "autoplay": autoplay,
		"progress": snappedf(host.progress, 0.001), "look_offset": [snappedf(host.look_offset.x, 0.001), snappedf(host.look_offset.y, 0.001)],
		"card_page": navigator.card_page if navigator != null else -2, "map_level": navigator.level if navigator != null else -2}
	if tour != null and tour.active and tour.actor != null:
		var a: WfCrewBody = tour.actor
		out["body"] = {"grip": a.grip.anchor_id if a.grip != null else "", "v": snappedf(a.linear_velocity.length(), 0.0001),
			"standing": a.standing, "yaw": snappedf(tour.yaw, 0.001), "pitch": snappedf(tour.pitch, 0.001), "beat": tour.beat,
			"tube_s": snappedf(tour.tube_s, 0.001), "arrived": tour.arrived, "pos": [snappedf(a.global_position.x, 0.001),
			snappedf(a.global_position.y, 0.001), snappedf(a.global_position.z, 0.001)], "drops": tour.drops}
	return out

## The route camera is the visitor's (its look offset is kept) except in the orbiting exterior chapters, whose camera is guided.
func camera_free() -> bool:
	return chapter >= 0 and not CHAPTERS[chapter] in ["EXTERIOR", "MODE"]

func ring_frac() -> float:
	# The rings' speed fraction while the demonstrator runs: DOCKED (stopped, locked) until the MODE chapter, then the controller's.
	return ctl.spin_frac if ctl != null else 0.0

func _vest() -> WfVestibule:
	if vest == null:
		vest = WfVestibule.new(host.rig_all["dynamics"], 0)
		vest.dp_equalized = true
	return vest

func ring_w() -> float:
	return float(host.frames[host.ring_id].rate) * float(host.rings[host.ring_id].f)

func side_of(opening: Dictionary) -> String:
	match str(opening.kind):
		"PORT_GATE": return "STATIONARY"
		"DRUM_DOOR_TUBE_HATCH": return "RING"
	return ""

## host.allowed(): a vestibule side may start to open only when the interlock passes (or it is already open).
func vestibule_allows(opening: Dictionary) -> bool:
	var side := side_of(opening)
	if side == "":
		return true
	return not _vest().closures[side] or _vest().gate(side, ring_w())["open"]

## host drum state machine: a speed change starts only when the vestibule accepts it (restrained, both boundaries closed).
func vestibule_sync(side: String) -> bool:
	var v := _vest()
	var tour: WfBodyTour = host.body_tour
	v.restrained = tour.restrained if tour != null and tour.beat == "TUBE" and tour.from_access else host.camera_frame == host.drum_id
	var e := v.start_sync(side, ring_w(), host.SYNC_S)
	if not e["ok"]:
		vest_refused.append(e["action"] + ": " + e["reason"])
	return e["ok"]

## After the closures move: the vestibule follows the opening state and its drum ramp advances with the display.
func vestibule_follow(delta: float) -> void:
	var v := _vest()
	v.step(delta)
	var open := {"STATIONARY": false, "RING": false}       # a side is open while any of its openings is (ring A's three drum doors are one side)
	for opening in host.openings:
		var side := side_of(opening)
		if side != "" and host.opening_open(opening) > 0.0:
			open[side] = true
	for side in open:
		if open[side] and v.closures[side]:
			var e := v.open(side, ring_w())
			if not e["ok"]:
				vest_refused.append("open %s: %s" % [side, e["reason"]])
		elif not open[side] and not v.closures[side]:
			v.close(side)

func _opening(kind: String) -> Dictionary:
	for o in host.openings:
		if str(o.kind) == kind:
			return o
	return {}

## TRANSFER: the vestibule openings fully open (the body passes the port and leaves the restraint only then).
func access_open() -> Dictionary:
	return {"STATIONARY": host.opening_open(_opening("PORT_GATE")) >= 0.999, "RING": host.opening_open(_opening("DRUM_DOOR_TUBE_HATCH")) >= 0.999}

## TRANSFER: the drum frame as a fraction of ring A's spin and its rate (the vestibule's ramp).
func access_frame() -> Array:
	var rw := ring_w()
	if absf(rw) < 1e-9:
		return [0.0, 0.0]
	return [_vest().drum_w / rw, _vest().alpha() / rw]

## TRANSFER: the rail place of the body. Along the trunk 1:1 up to the port band's edge where the body first leaves the trunk bore; to the
## rail's point INSIDE_M past the port when it reaches the restraint pose (so the gate closes only behind the whole body); at the pose, the
## drum door band's edge (the drum syncs, the door opens); then to the run top.
func access_rail(s: float) -> float:
	var tour: WfBodyTour = host.body_tour
	var margin := float(host.route.envelope.radius_m)
	var p0: float = host.gate_rail - margin
	if s <= tour.s_port:
		return p0 - (tour.s_port - s)
	if s < tour.s_hold - 1e-9:
		return lerpf(p0, host.gate_rail + host.INSIDE_M, (s - tour.s_port) / (tour.s_hold - tour.s_port))
	var p1 := float(_opening("DRUM_DOOR_TUBE_HATCH").rail_m) - margin
	return lerpf(p1, tube_top_rail(), clampf((s - tour.s_hold) / (tour.s_run - tour.s_hold), 0.0, 1.0))

## The rail distance of the waypoint at the top of the crew tube's radial run, where the body is handed to the DESCENT chapter.
func tube_top_rail() -> float:
	var top: Array = host.rig_all["dynamics"]["stages"]["tube"]["axis_m"][0]
	var p: Vector3 = host.vector(top)
	var best := 0
	for i in range(host.points.size()):
		if host.points[i].distance_to(p) < host.points[best].distance_to(p):
			best = i
	return float(host.distances[best])

func stop_index(key: String) -> int:
	for i in range(host.route.stops.size()):
		if host.route.stops[i].key == key:
			return i
	return 0

func begin(index: int) -> void:
	chapter = index
	goal_done = false
	t = 0.0
	auto_step = 0
	var name: String = CHAPTERS[index]
	log.append({"chapter": name, "rail_m": host.progress})
	if record_exit:
		print("WF_DEMO_CHAPTER %s %.2f" % [name, record_t])    # chapter marks for the review cuts and contact sheet
	var tour: WfBodyTour = host.ensure_body_tour()
	if name in ["MICROGRAVITY", "TRANSFER", "DESCENT", "GRAVITY"]:
		if not tour.active:
			tour.enter(name == "MICROGRAVITY")
		if name == "TRANSFER":
			tour.drum_pivot = host.frames[host.drum_id].node
			tour.gate_fn = access_open
			tour.frame_fn = access_frame
			access_log = []
			tour.build_tube(true, true)
			tour.s_stop = tour.s_run
			tour.auto_descend = autoplay
		elif name == "DESCENT":
			if tour.beat == "TUBE" and tour.from_access:
				tour.s_stop = INF                        # the same body goes on down the run
			else:
				tour.build_tube()
			tour.auto_descend = autoplay
		elif name == "GRAVITY" and not (tour.beat == "TUBE" and tour.arrived):
			tour.build_ring("RING_A", true)
	elif tour.active:
		tour.leave()
		host.camera.current = true
	sun.visible = name in ["EXTERIOR", "MODE"]
	# The stop card belongs to the route rail (ENTRY); from TRANSFER on the body is in physics and the card would show a stale stop.
	host.bottom_panel.visible = name == "ENTRY" and not WfInput.compact()
	# The body is seen from the body tour's review offsets (PROTOTYPE camera); V switches to first person.
	tour.ext_offset = {"MICROGRAVITY": SPINE_VIEW, "DESCENT": TUBE_VIEW, "GRAVITY": WELL_VIEW if tour.beat == "TUBE" else RING_VIEW}.get(name, Vector3.INF)
	tour.view_out = name == "TRANSFER"
	match name:
		"EXTERIOR":
			host.progress = 0.0
			host.stop_view = -1
			host.settle()
		"ENTRY":
			host.body_mode = false
			host.progress = 0.0
			host.stop_view = -1
			host.settle()
			host.update_camera()
		"MODE":
			host.go_to_stop(stop_index("spine"))
			if ctl == null:
				var field := WfFrameField.new(host.rig_all["dynamics"], "SHIP", "DOCKED")
				ctl = WfModeController.new(host.rig_all["dynamics"], field, "DOCKED")
			if ctl.mode == "DOCKED" and not ctl.busy():
				log.append({"request": ctl.request("COAST")})
		"TRANSFER":
			host.body_mode = true
			host.stop_view = -1
			host.update_camera()
		"ARRIVAL", "INSPECT":
			# INSPECT switches the layer at the first stop, the entry chamber, where M7.ENT fills the eye-level view; from ring A sector
			# 1's habitat stop its overhead panels sit above the berth units, out of the stop's view.
			host.body_mode = false
			host.go_to_stop(stop_index("habitat") if name == "ARRIVAL" else 0)
			if production_nodes.is_empty():
				# the M7 section only: the M8 exterior layer (its own maturity) stays as it is while INSPECT flips the interior section
				production_nodes = host.ship.find_children("WF_*", "MeshInstance3D", true, false).filter(func(m): return m.has_meta("assembly") and str(m.get_meta("assembly")).begins_with("M7."))
			set_production(true)
	host.set_note()

func set_production(on: bool) -> void:
	for m in production_nodes:
		m.visible = on

func production_summary() -> String:
	var counts := {}
	for m in production_nodes:
		counts[m.get_meta("assembly")] = counts.get(m.get_meta("assembly"), 0) + 1
	var keys := counts.keys()
	keys.sort()
	return ", ".join(keys.map(func(k): return "%s (%d)" % [k, counts[k]]))

## The chapter the run starts at: 0, or -- --from-chapter=<NAME> (a short recording or review of the later chapters).
func first_chapter() -> int:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--from-chapter="):
			return maxi(0, CHAPTERS.find(arg.trim_prefix("--from-chapter=").to_upper()))
	return 0

## Automated recording: INSPECT completed (not merely entered), every chapter from the first one ran in order, and the production layer
## flipped and ended on; then the tail, the result line and the exit. The watchdog fails a run that never gets there.
func record_tick(dt: float, done: bool) -> void:
	record_t += dt
	if record_done_t < 0.0:
		if chapter == CHAPTERS.size() - 1 and done:
			record_done_t = record_t
		elif record_t > record_timeout:
			record_finish(false, "watchdog: chapter %s not completed after %.0f s" % [CHAPTERS[chapter], record_t])
		return
	if record_t - record_done_t >= RECORD_TAIL_S:
		var ran := log.filter(func(e): return e.has("chapter")).map(func(e): return e["chapter"])
		var want := CHAPTERS.slice(first_chapter())
		var restored := production_nodes.all(func(m): return m.visible)
		var ok: bool = ran == want and production_flips >= 2 and restored and not production_nodes.is_empty()
		record_finish(ok, "" if ok else "chapters %s, flips %d, layer restored %s" % [ran, production_flips, restored])

func record_finish(ok: bool, why: String) -> void:
	var out := {"result": "PASS" if ok else "FAIL", "chapters": log.filter(func(e): return e.has("chapter")).map(func(e): return e["chapter"]),
		"display_s": snappedf(record_t, 0.01), "frames": Engine.get_process_frames(), "flips": production_flips, "reason": why}
	print("WF_DEMO_RECORDING " + JSON.stringify(out))
	record_exit = false
	get_tree().quit(0 if ok else 1)

func next() -> void:
	if chapter < CHAPTERS.size() - 1:
		begin(chapter + 1)

func _unhandled_input(e: InputEvent) -> void:
	if chapter < 0 or not WfInput.pressed(e):
		return
	match WfInput.key_of(e, ["demo"]):               # ACI-10: ui.confirm (next chapter), demo.*, body.view
		KEY_ENTER: next()
		KEY_P: paused = not paused
		KEY_V:
			var tour: WfBodyTour = host.body_tour
			if tour == null or not tour.active:
				return
			var view: Vector3 = {"MICROGRAVITY": SPINE_VIEW, "TRANSFER": ACCESS_VIEW, "DESCENT": TUBE_VIEW}.get(CHAPTERS[chapter], WELL_VIEW if tour.beat == "TUBE" else RING_VIEW)
			tour.ext_offset = Vector3.INF if tour.ext_offset != Vector3.INF else view
		KEY_F2:
			autoplay = not autoplay
			if host.body_tour != null:
				host.body_tour.auto_descend = autoplay and CHAPTERS[chapter] in ["TRANSFER", "DESCENT"]
		KEY_F3:
			holo.apply(holo.next_style())
		KEY_O:
			if ctl != null:
				ctl.occupants_securable = not ctl.occupants_securable
				ctl.resume()
		_: return
	get_viewport().set_input_as_handled()

func orbit(angle: float, rise: float) -> void:
	var at := centre + Vector3(sin(angle), rise, cos(angle)) * radius
	host.camera.global_transform = Transform3D(Basis.looking_at(centre - at, Vector3.UP), at)

## One display step of the current chapter; returns true once its goal is reached (the run continues on Enter or in autoplay).
func step(dt: float) -> bool:
	t += dt
	var tour: WfBodyTour = host.body_tour
	match CHAPTERS[chapter]:
		"EXTERIOR":
			if not paused:
				orbit(-0.75 + ORBIT_ARC * minf(t / EXTERIOR_S, 1.0), 0.3)
			return t >= EXTERIOR_S
		"ENTRY":
			var goal := float(host.route.stops[stop_index("spine")].rail_m)
			if not paused and host.progress < goal:
				host.move_along(minf(dt * host.PACE, goal - host.progress))
			return host.progress >= goal - 1e-6
		"MICROGRAVITY":
			var a := tour.actor
			if a == null:
				return false
			var target := tour.rail_by_id(tour.CATCH_RAIL)
			if autoplay:
				if auto_step == 0 and a.grip != null and t > 1.0:
					a.push(tour.PUSH_DIR, -1.0, Vector3.ZERO)
					auto_step = 1
				elif auto_step == 1 and a.can_reach(target):
					a.grab(target)
					auto_step = 2
			return a.grip != null and a.grip.anchor_id != tour.START_RAIL and a.linear_velocity.length() < 1e-2
		"MODE":
			if not paused:
				ctl.advance(dt * TIMELAPSE)
				orbit(0.25 + 0.15 * minf(t / 20.0, 1.0), 0.15)
			return ctl.mode == "COAST" and not ctl.busy()
		"TRANSFER":
			if tour == null or tour.actor == null:
				return false
			host.progress = access_rail(tour.tube_s)
			host.update_camera()
			access_log.append({"s": tour.tube_s, "ramping": _vest().ramping, "restrained": tour.restrained, "drum": host.drum_mode, "progress": host.progress})
			return tour.tube_s >= tour.s_run - 1e-6 and tour.climb_v == 0.0
		"DESCENT":
			return tour.arrived and tour.actor != null and tour.actor.standing
		"GRAVITY":
			var a := tour.actor
			if a == null:
				return false
			if autoplay:
				var dir := Vector3.BACK if tour.beat == "TUBE" else Vector3.LEFT      # out of the landing well into the aisle, or along the aisle
				tour.auto_walk = dir if t > 1.0 and t < 2.0 else Vector3.ZERO
				if auto_step == 0 and t > 3.0 and tour.tool != null:
					tour.drop_tool()
					auto_step = 1
			return a.standing and t > 3.0
		"ARRIVAL":
			return t >= ARRIVAL_S
		"INSPECT":
			var on := int(t / INSPECT_FLIP_S) % 2 == 1 if not paused else true
			if t < INSPECT_S and production_nodes.size() > 0 and production_nodes[0].visible != on:
				set_production(on)
				production_flips += 1
			if t >= INSPECT_S:
				set_production(true)
				return true
			return false
	return false

func _process(dt: float) -> void:
	if chapter < 0 or driven:
		return
	var ran := chapter
	var done := step(dt)
	goal_done = done
	if done and autoplay and auto_next and chapter < CHAPTERS.size() - 1 and t > 1.0:
		next()
	if record_exit and autoplay:
		record_tick(dt, done and chapter == ran)    # a goal reached in the chapter just left does not complete the new one
	hud.text = hud_text(done)
	layout()

func layout() -> void:
	if WfInput.compact():
		_layout_compact()
		return
	# The left text wraps short of the stop panel (boarding.gd: 330 px from the right edge), so nothing runs under it at 1280 wide,
	# and the body tour's lines stack under the demonstrator's instead of a fixed height.
	var w := clampf(get_viewport().get_visible_rect().size.x - SIDE_PANEL_PX - hud.position.x - 16.0, 320.0, HUD_MAX_W)
	hud.custom_minimum_size.x = w
	hud.size = Vector2(w, 0.0)
	var bt: WfBodyTour = host.body_tour
	if bt != null:
		bt.hud.custom_minimum_size.x = w
		bt.hud.size = Vector2(w, 0.0)
		bt.hud.position = Vector2(hud.position.x, hud.position.y + hud.get_combined_minimum_size().y + 12.0)
	var key: String = CHAPTER_STOP.get(CHAPTERS[chapter], "") if chapter >= 0 else ""
	for i in range(host.route.stops.size()):
		if host.route.stops[i].key == key:
			host.stop_list.select(i)

## MOB-001 phone / tablet: the chapter text top left, clear of the touch utility row (top right) and the stick and action buttons
## (bottom); the body readouts only with Details; the systems card takes the text's place while it is open.
func _layout_compact() -> void:
	var vs := get_viewport().get_visible_rect().size
	var safe: Array = WfInput.touch.safe
	var narrow := vs.x < 640.0
	var top := float(safe[1]) + 62.0 + (64.0 if narrow else 0.0)      # under the page's Exit and full-screen buttons (shell, top left)
	var w := (vs.x - float(safe[0]) - float(safe[2]) - 24.0) if narrow else clampf(vs.x * 0.56 - float(safe[0]), 260.0, 640.0)
	hud.position = Vector2(float(safe[0]) + 12.0, top)
	hud.custom_minimum_size.x = w
	hud.size = Vector2(w, 0.0)
	hud.visible = navigator == null or navigator.card_page < 0
	var bt: WfBodyTour = host.body_tour
	if bt != null:
		bt.hud.visible = details and bt.active
		bt.hud.custom_minimum_size.x = w
		bt.hud.size = Vector2(w, 0.0)
		bt.hud.position = Vector2(hud.position.x, hud.position.y + (hud.get_combined_minimum_size().y + 8.0 if hud.visible else 0.0))

func tour_last() -> Dictionary:
	var tour: WfBodyTour = host.body_tour
	return tour.hand_log[-1] if tour != null and not tour.hand_log.is_empty() else {}

func hud_text(done: bool) -> String:
	var name: String = CHAPTERS[chapter]
	var touch := WfInput.device == "touch"
	var s := ("DEMONSTRATOR 01 · SIMULATION_ONLY · %d/%d %s%s%s\n" if WfInput.compact() else "WAYFARER INTEGRATED DEMONSTRATOR 01 · SIMULATION_ONLY · chapter %d/%d %s%s%s\n") % [chapter + 1, CHAPTERS.size(), name,
		"  [paused]" if paused else "", "  [autoplay]" if autoplay else ""]
	match name:
		"EXTERIOR": s += "The DOCKED ship, static REP_PROXY export; inspection light, not a sourced sun or attitude."
		"ENTRY": s += "Outer hatch, airlock and the stationary spine on the review rail; the closures cycle as the camera passes (display timing)."
		"MICROGRAVITY": s += "Crew physics in the real trunk: " + (touch_hint(name) if touch else WfInput.keys("{player.grab} grab, look aft (%s) and {player.push} push, {player.grab} at the next rail to catch." % look_label())) + " No thrust, no braking."
		"MODE":
			s += "DOCKED -> COAST in the owner's step order (46 DYN-026): %s.\n" % " -> ".join(ctl.steps_all)
			s += "%s · ring speed %.0f %% · ramp shown x%d of the %.0f s study value (WORKING); transition timing HOLD, no First Ignition time.%s" % [
				ctl.ring_state, ctl.spin_frac * 100.0, int(TIMELAPSE), ctl.ramp_s(), ("\nHELD: " + ctl.hold_reason) if ctl.hold_reason != "" else ""]
			s += "\n" + (touch_hint(name) if touch else "O: mark an occupant not secured (the sequence holds before the ramp, fail closed).")
		"TRANSFER":
			s += "The body in physics: trunk -> spine port -> despun drum (restrained on a chord while it syncs with ring A) -> feet first through the door and elbows to the run top. " + (touch_hint(name) if touch else WfInput.keys("{player.move_back}/{player.move_forward} move, {demo.autoplay} autoplay")) + "; drum sync time OPEN (MEC-019).\n"
			s += "Interlock (46 DYN-027): " + _vest().hud_text(ring_w()).strip_edges() + "  [pressure shown equalized: PROTOTYPE input, threshold OPEN]"
		"DESCENT":
			var tl := tour_last()
			s += "Crew tube A1, hand over hand on the real rungs at the review pace (LADDER technique, PROTOTYPE); " + (touch_hint(name) + "\n" if touch else WfInput.keys("{player.move_back} down, {player.move_forward} up, let go to stop.\n"))
			s += "r %.2f m  hand load %.0f N (measured, no limit sourced)  rungs in reach %d  %s" % [tl.get("r", 0.0), (tl.get("hand_n", Vector3.ZERO) as Vector3).length(),
				tl.get("reach", 0), "standing on the landing-well deck" if host.body_tour.arrived else ""]
		"GRAVITY": s += "Ring A deck in spin gravity: " + (touch_hint(name) if touch else WfInput.keys("{player.move_forward} {player.move_left} {player.move_back} {player.move_right} walk, {body.drop_tool} drop the object (Coriolis).")) + " Display of the sourced spin, not a comfort limit."
		"ARRIVAL": s += "Ring A sector 1, HABITATION: the end of the M7 production reference section (port, entry, trunk, drum, tube, sector).\nTRAINING ROUTE: ring A is no certified rescue route (15!A221); transfer closures PROTOTYPE (I5/Q46 OPEN)."
		"INSPECT":
			var on: bool = production_nodes.size() > 0 and production_nodes[0].visible
			s += ("Production layer %s (" + str(host.manifest.production.maturity) + ", S&E 48!A23; visual acceptance, not engineering GO) over the same engineering geometry, seen from the entry chamber stop (M7.ENT; its stop card shows the boarding configuration, DOCKED). %d meshes: %s.\n" + (touch_hint(name) if touch else WfInput.keys("{demo.pause} holds it on")) + ("." if WfInput.compact() else WfInput.keys("; {ui.cancel} inspector for picking."))) % [
				"ON" if on else "OFF (engineering + route fit-out)", production_nodes.size(), production_summary()]
	if holo.style != "standard":
		s += "\n" + holo.legend()
	s += "\n" + (("Done: tap Next." if touch else WfInput.keys("Done: {ui.confirm} for the next chapter.")) if done and chapter < CHAPTERS.size() - 1 else ("End of the demonstrator." if done else ""))
	if not WfInput.compact():
		s += WfInput.keys("   {ui.confirm} next · {demo.pause} pause · {demo.autoplay} autoplay · {body.view} body / first person" + (" · {demo.holo} hologram" if holo.available() else "") + " · {ui.cancel} inspector")
	return s.strip_edges(false, true)

## MOB-001: the chapter's instruction on a touch screen, in the words of its on-screen controls (touch_state).
func touch_hint(name: String) -> String:
	match name:
		"MICROGRAVITY": return "Grab a rail, drag on the right to aim, Push off; Grab the next rail to stop."
		"MODE": return "Fault: occupant marks one not secured; the sequence holds before the ramp (fail closed)."
		"TRANSFER": return "Stick: move along the line; Auto plays it"
		"DESCENT": return "Stick up or down to climb; let go to stop."
		"GRAVITY": return "stick to walk, Drop object to see Coriolis."
		"INSPECT": return "Hold layer on keeps it"
	return ""

func look_label() -> String:
	return "drag on the right" if WfInput.device == "touch" else "right-drag"

## Headless run of the whole demonstrator in autoplay (needs physics frames: --fixed-fps 60). Rail chapters step in fixed display steps
## and keep the transfer check's safety rules (never inside a closed opening's band, no closure open outside its safe state).
func run_check() -> Dictionary:
	var checks := []
	autoplay = true
	driven = true
	var dt := 1.0 / 60.0
	var margin := float(host.route.envelope.radius_m)
	var violations := []
	var frames_seen := {}
	var drum_seen := {}
	var nav_checks: Array = []
	for i in range(CHAPTERS.size()):
		begin(i)
		var name: String = CHAPTERS[i]
		var guard := 0
		var done := false
		while not done and guard < 60 * 600:
			guard += 1
			if name in ["MICROGRAVITY", "TRANSFER", "DESCENT", "GRAVITY"]:
				await get_tree().physics_frame          # the host's _process steps the mechanisms in real frames
			else:
				host.step_mechanisms(dt)
			done = step(dt)
			for opening in host.openings:
				var v: float = host.opening_open(opening)
				if absf(host.progress - float(opening.rail_m)) < margin - 1e-6 and v < 0.999 and name in ["ENTRY", "TRANSFER"]:
					violations.append("inside %s at %.2f m while %.2f open" % [opening.id, host.progress, v])
				if v > 0.0 and not host.safe(opening):
					violations.append("%s open outside its safe state" % opening.id)
			frames_seen[host.camera_frame] = true
			drum_seen[host.drum_mode] = true
			if navigator != null:
				navigator.sample(name)
		if name == "GRAVITY":
			for k in 120:
				await get_tree().physics_frame
				step(dt)
			# The navigator's checks follow the body in ring A's frame: run them while the body is still there (M7's ARRIVAL and
			# INSPECT hand the camera back to the review rail).
			if navigator != null:
				nav_checks = await navigator.run_checks()
		checks.append({"id": "chapter_" + name, "ok": done, "actual": done, "steps": guard})
		match name:
			"EXTERIOR":
				var d: float = host.camera.global_position.distance_to(centre)
				checks.append({"id": "exterior_outside_ship", "ok": d > radius * 0.9, "actual": d, "limit": radius * 0.9})
			"MICROGRAVITY":
				var a: WfCrewBody = host.body_tour.actor
				checks.append({"id": "micro_caught_real_rail", "ok": a.grip != null and a.grip.anchor_id.begins_with("Crew_Trunk_"), "actual": a.grip.anchor_id if a.grip else ""})
			"MODE":
				host.step_mechanisms(dt)                    # the rings read the settled controller on the next display step
				var want: Array = host.rig_all["dynamics"]["transitions"]["DOCKED>COAST"]["steps"]
				checks.append({"id": "mode_owner_order", "ok": ctl.done_steps == want and ctl.mode == "COAST", "actual": ctl.done_steps, "expected": want})
				checks.append({"id": "mode_rings_follow_controller", "ok": host.rings[host.ring_id].mode == "RUNNING" and absf(ctl.spin_frac - 1.0) < 1e-9, "actual": host.rings[host.ring_id].mode})
			"TRANSFER":
				checks.append({"id": "transfer_drum_synced", "ok": drum_seen.has("SYNCED"), "actual": drum_seen.keys()})
				checks.append({"id": "transfer_in_ring_frame", "ok": host.camera_frame == host.ring_id, "actual": host.camera_frame})
				var opened := vest.log.filter(func(e): return e["ok"] and str(e["action"]).begins_with("open")).map(func(e): return e["action"]) if vest else []
				checks.append({"id": "transfer_vestibule_gated", "ok": vest != null and "open STATIONARY" in opened and "open RING" in opened and vest_refused.is_empty(),
					"actual": {"opened": opened, "refused": vest_refused.slice(0, 5)}, "note": "each side opened only when the DYN-027 gate passed"})
				checks.append_array(access_checks())
			"DESCENT":
				checks.append_array(descent_checks())
			"ARRIVAL":
				checks.append({"id": "arrival_production_layer", "ok": production_nodes.size() > 0 and production_nodes.all(func(m): return str(m.get_meta("maturity")) == str(host.manifest.production.maturity)),
					"actual": production_nodes.size(), "note": "every production mesh carries its assembly and the manifest maturity"})
				var ids := {}
				for m in production_nodes:
					ids[m.get_meta("assembly")] = true
				checks.append({"id": "arrival_six_assemblies", "ok": ids.size() == host.manifest.production.assemblies.keys().filter(func(a): return str(a).begins_with("M7.")).size(), "actual": ids.keys()})
			"INSPECT":
				checks.append({"id": "inspect_toggled_and_restored", "ok": production_flips >= 2 and production_nodes.all(func(m): return m.visible), "actual": production_flips})
			"GRAVITY":
				var a: WfCrewBody = host.body_tour.actor
				var g: float = a.field_now.length() / float(host.rig_all["dynamics"]["standard_gravity_m_s2"])
				var fx: Dictionary = host.body_tour.fixture("RING_A_FLOOR")
				checks.append({"id": "gravity_standing", "ok": a.standing, "actual": a.standing})
				checks.append({"id": "gravity_floor_g", "ok": absf(g - float(fx["expect_g"])) < 0.02, "actual": g, "expected": fx["expect_g"], "tol": 0.02,
					"note": "body-centre field; the foot value is checked to 1e-3 in boarding-body"})
				var tool: WfTool = host.body_tour.tool
				checks.append({"id": "gravity_object_landed", "ok": tool != null and tool.contact_step >= 0, "actual": tool.contact_step if tool else -1})
	checks.append({"id": "rail_safety", "ok": violations.is_empty(), "actual": violations.slice(0, 5)})
	checks.append_array(nav_checks)
	var fail := checks.filter(func(c): return not c["ok"]).map(func(c): return c["id"])
	return {"result": "PASS" if fail.is_empty() else "FAIL", "status": "SIMULATION_ONLY", "chapters": CHAPTERS, "frames": frames_seen.keys(),
		"mode_log": ctl.log.size() if ctl else 0, "checks": checks, "fail": fail, "findings": access_findings()}

## M2 access (TRANSFER): the body reaches the run top in physics; no wall contact on the way (the rig line keeps margin_m from the clear
## surfaces); held still in the restraint pose for the whole drum ramp, the hands carrying the drum frame's centrifugal and Euler terms; the
## field zero before the ramp and ring A's after it; a rail, stile or rung in reach at every corner before the sync and at every step after
## it. Hand loads are measured only.
func access_checks() -> Array:
	var tour: WfBodyTour = host.body_tour
	var m := float(host.rig_all["dynamics"]["profiles"]["human_iva"]["mass_kg"])
	var acc: Array = tour.hand_log.filter(func(e): return float(e["s"]) < tour.s_run - 1e-9)
	var touched := acc.filter(func(e): return int(e["contacts"]) > 0)
	var hold_err := 0.0
	var hold_max := 0.0
	var before := 0.0
	var after := 0.0
	var fmax := 0.0
	var hold_grip := 99
	var field_grip := 99
	var prev_f := Vector3.ZERO
	var prev_held := false
	for e in acc:
		var hand: Vector3 = e["hand_n"]
		fmax = maxf(fmax, hand.length())
		var f: Vector3 = e["field"]
		if float(e["s"]) < tour.s_hold - 1e-9:
			before = maxf(before, f.length())
		elif float(e["s"]) > tour.s_hold + 1e-9:
			after = maxf(after, absf(float(e["frac"]) - 1.0))
		if float(e["s"]) >= tour.s_hold - 1e-9:
			field_grip = mini(field_grip, int(e["grips"]))
		if e["restrained"]:
			hold_grip = mini(hold_grip, int(e["grips"]))
			if prev_held and float(e["frac"]) > 0.0:
				# held still: the hands supplied -m a_field of the step before (the logged load is the last physics step's)
				hold_err = maxf(hold_err, (hand + prev_f * m).length())
				hold_max = maxf(hold_max, hand.length())
		prev_f = f
		prev_held = e["restrained"]
	var ramp := access_log.filter(func(e): return e["ramping"])
	var loose := ramp.filter(func(e): return not e["restrained"])
	var w := float(host.rig_all["dynamics"]["rings"][0]["omega_rad_s"])
	var a: Dictionary = host.rig_all["dynamics"]["stages"]["access"]
	var hold_p: Array = a["line"][int(a["hold_index"])]["p"]
	var rho := Vector2(float(hold_p[1]), float(hold_p[2])).length()
	var coast := acc.filter(func(e): return e["coast"])
	var coast_n := 0.0
	var coast_dv := 0.0
	for i in range(1, acc.size()):
		if acc[i]["coast"] and acc[i - 1]["coast"]:    # the logged load is the step before's: the first coast step carries the push-off
			coast_n = maxf(coast_n, (acc[i]["hand_n"] as Vector3).length())
			coast_dv = maxf(coast_dv, absf(float(acc[i]["cv"]) - float(coast[0]["cv"])))
	var in_coast := 0.0
	for c in tour.coasts:
		in_coast += float(c[1]) - float(c[0])
	return [
		{"id": "access_reached_run_top", "ok": tour.tube_s >= tour.s_run - 1e-6, "actual": tour.tube_s, "expected": tour.s_run, "steps": acc.size()},
		{"id": "access_no_wall_contact", "ok": touched.is_empty(), "actual": touched.size(), "first_s": touched[0]["s"] if not touched.is_empty() else null,
			"note": "rigid body proxy on the rig line (least clearance %.3f m in the shared formulas)" % float(a["least_clearance_m"])},
		{"id": "access_restrained_through_ramp", "ok": not ramp.is_empty() and loose.is_empty(), "actual": {"ramp_steps": ramp.size(), "loose": loose.size()}},
		{"id": "access_restraint_load", "ok": hold_max > 0.0 and hold_err < 0.5, "actual_err_n": hold_err, "tol_n": 0.5, "max_n": hold_max,
			"expected_end_n": m * w * w * rho, "note": "hands hold the body still in the drum frame: -m (centrifugal + Euler); drum ramp PROTOTYPE (MEC-019 OPEN)"},
		{"id": "access_field_zero_before_sync", "ok": before < 1e-9, "actual": before},
		{"id": "access_ring_frame_after_door", "ok": after < 1e-9, "actual": after, "note": "drum fraction of ring A's spin once past the door"},
		{"id": "access_restraint_grip", "ok": hold_grip >= 1 and hold_grip < 99, "actual": hold_grip, "note": "a rail within the profile reach of the body centre in the restraint pose (the vestibule figure's)"},
		{"id": "access_grip_in_field", "ok": field_grip >= 1 and field_grip < 99, "actual": field_grip,
			"note": "from the restraint pose to the run top (the drum in ring A's field) a rail, stile or rung within the profile reach at every step"},
		{"id": "access_coast_hands_free", "ok": in_coast == 0.0 or (not coast.is_empty() and coast_n <= HAND_FREE_N and coast_dv < 1e-9),
			"actual_n": coast_n, "limit_n": HAND_FREE_N, "speed_change": coast_dv, "steps": coast.size(), "coast_m": in_coast,
			"note": "across the spine port's bore no grip is in reach: pushed off at the trunk rails' end, the body coasts (zero field) to the catch by the drum's crawl rail"},
		{"id": "access_hand_load_measured", "ok": fmax > 0.0, "actual_max_n": fmax, "note": "measured only; no hand-load limit is sourced"},
	]

## M2 access findings (measured, not gates): where the hands carry load (start, turn, stop) with no rail, stile or rung within the profile reach
## of the body centre. Before the sync the rig line keeps a grip in reach at every corner and coasts across the spine port's bore; after it
## a grip is in reach at every step (both checked above), so a finding here means the body left the rig line.
func access_findings() -> Array:
	var tour: WfBodyTour = host.body_tour
	var out := []
	var cur := []
	for e in tour.hand_log:
		if float(e["s"]) >= tour.s_run - 1e-9:
			break
		var load: float = (e["hand_n"] as Vector3).length()
		if load > HAND_FREE_N and int(e["grips"]) < 1:
			if cur.is_empty() or float(e["s"]) - float(cur[1]) > 0.05:
				if not cur.is_empty():
					out.append(cur)
				cur = [e["s"], e["s"], 0.0, e["phase"]]
			cur[1] = e["s"]
			cur[2] = maxf(float(cur[2]), load)
	if not cur.is_empty():
		out.append(cur)
	return out.map(func(c): return {"id": "access_load_without_grip", "s_m": [snappedf(c[0], 0.01), snappedf(c[1], 0.01)], "max_n": snappedf(c[2], 0.1), "phase": c[3],
		"note": "hands load the body with no grip within %.2f m of the body centre (PROTOTYPE line on the bores' axes)" % float(host.rig_all["dynamics"]["profiles"]["human_iva"]["reach_m"])})

## M2 descent: arrival standing on the deck, a rung always in reach, the review pace, the body inside the tube's clear bore, and the hands'
## load toward the ladder against the rig's ladder_push (lean + Coriolis at the pace, human_entry.ladder_push). Hand loads are measured only.
func descent_checks() -> Array:
	var tour: WfBodyTour = host.body_tour
	var t: Dictionary = host.rig_all["dynamics"]["stages"]["tube"]
	var push: Dictionary = host.body_data.ladder_push
	var g0 := float(host.rig_all["dynamics"]["standard_gravity_m_s2"])
	var m := float(host.rig_all["dynamics"]["profiles"]["human_iva"]["mass_kg"])
	var pace := float(t["review_speed_m_s"])
	var rad := float(host.rig_all["dynamics"]["profiles"]["human_iva"]["radius_m"])
	var log: Array = tour.hand_log.filter(func(e): return float(e["s"]) >= tour.s_run - 1e-9)
	var min_reach := 99
	var fmax := 0.0
	var toward := []
	var radial_err := 0.0
	var w := float(host.rig_all["dynamics"]["rings"][0]["omega_rad_s"])
	var bore := 0.0
	var a: Vector3 = tour.tube_axis[0]
	var seat: float = ((tour.tube_axis[1] as Vector3) - a).dot(tour.tube_out)
	var prev_cv := [0.0, 0.0]
	for e in log:
		# the logged hand impulse is the last physics step's: steady = no speed change in this command or the two before
		var steady: bool = absf(float(e["cv"]) - pace) < 1e-9 and absf(prev_cv[0] - pace) < 1e-9 and absf(prev_cv[1] - pace) < 1e-9
		prev_cv = [float(e["cv"]), prev_cv[0]]
		min_reach = mini(min_reach, int(e["reach"]))
		fmax = maxf(fmax, (e["hand_n"] as Vector3).length())
		var d: Vector3 = (e["p"] as Vector3) - a
		if d.dot(tour.tube_out) < seat:                       # on the run, above the hatch seat
			bore = maxf(bore, (d - tour.tube_out * d.dot(tour.tube_out)).length() + rad)
		if steady:
			toward.append((e["hand_n"] as Vector3).dot(tour.tube_toward) / (m * g0))
			# at constant pace the hands carry the centrifugal term along the run: m w^2 (r . out)
			var cf: float = m * w * w * (e["p"] as Vector3).dot(tour.tube_out)
			radial_err = maxf(radial_err, absf(-(e["hand_n"] as Vector3).dot(tour.tube_out) - cf))
	var want := -(float(push["lean_toward_ladder_g"]) + float(push["coriolis_g_per_m_s"]) * pace)
	toward.sort()
	var med: float = toward[toward.size() / 2] if not toward.is_empty() else 0.0
	return [
		{"id": "descent_arrived_standing", "ok": tour.arrived and tour.actor.standing, "actual": [tour.arrived, tour.actor.standing], "steps": log.size()},
		{"id": "descent_rung_in_reach", "ok": min_reach >= 1, "actual": min_reach, "note": "rungs within the profile reach of the body centre at every step"},
		{"id": "descent_inside_bore", "ok": bore <= float(t["clear_radius_m"]), "actual": bore, "limit_m": t["clear_radius_m"], "note": "largest distance of the body centre from the run axis + body radius"},
		{"id": "descent_hand_toward_ladder", "ok": not toward.is_empty() and absf(med / want - 1.0) < 0.03, "actual": med, "expected": want,
			"note": "hands' load along the ladder direction per body weight at the review pace = -(lean + Coriolis), rig ladder_push"},
		{"id": "descent_hand_radial_centrifugal", "ok": not toward.is_empty() and radial_err < 5.0, "actual_n": radial_err, "tol_n": 5.0,
			"note": "largest difference between the hands' load along the run and m w^2 r (ring A spin) over the steady-pace steps; the rest is the line correction"},
		{"id": "descent_hand_load_measured", "ok": fmax > 0.0, "actual_max_n": fmax, "note": "measured only; no hand-load limit is sourced"},
	]

## Stills of each chapter (needs a display): autoplay runs, one shot per chapter at its goal and one mid-chapter.
func capture(dir: String) -> void:
	DirAccess.make_dir_recursive_absolute(dir)
	autoplay = true
	driven = true
	for i in range(CHAPTERS.size()):
		begin(i)
		var guard := 0
		var shot_mid := false
		while guard < 60 * 300:
			guard += 1
			await get_tree().process_frame
			var dt := 1.0 / 60.0
			if CHAPTERS[i] in ["ENTRY", "EXTERIOR", "MODE"]:
				host.step_mechanisms(dt)
			var done := step(dt)
			hud.text = hud_text(done)
			layout()
			if not shot_mid and t > (0.5 if CHAPTERS[i] == "GRAVITY" else 2.0):
				shot_mid = true
				await _shot(dir, "demo_%d_%s_a" % [i + 1, CHAPTERS[i].to_lower()])
			if done and t > 2.5:
				break
		await _shot(dir, "demo_%d_%s_b" % [i + 1, CHAPTERS[i].to_lower()])
		if "--holo-stills" in OS.get_cmdline_user_args() and holo.available():
			for s in ["subsystem", "engine"]:                       # WEB-003: the same frame in each hologram style
				holo.apply(s)
				hud.text = hud_text(true)
				await _shot(dir, "demo_%d_%s_holo_%s" % [i + 1, CHAPTERS[i].to_lower(), s])
			holo.apply("standard")
		if navigator != null and "--navigator-stills" in OS.get_cmdline_user_args():
			await navigator.stills(dir, "demo_%d_%s" % [i + 1, CHAPTERS[i].to_lower()], _shot)
		if navigator != null and "--space-stills" in OS.get_cmdline_user_args() and CHAPTERS[i] in ["ENTRY", "GRAVITY"]:
			await navigator.space.stills(dir, "demo_%d_%s" % [i + 1, CHAPTERS[i].to_lower()], _shot)

func _shot(dir: String, name: String) -> void:
	for k in 3:
		await RenderingServer.frame_post_draw
	get_viewport().get_texture().get_image().save_png(dir.path_join(name + ".png"))
