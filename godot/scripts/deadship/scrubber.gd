class_name WfDeadship
extends RefCounted
## Deadship DS-1 "Scrubber" (Phase 1, `#interior-deadship` / `-- --deadship`): the unscored training tutorial, run on the walk's ring start
## (simulated COAST). The scenario layer only: it reads its definition from the package (data/deadship/ds1_scrubber.toml through
## src/wayfarer/deadship.py), drives the CO2 model (WfCabinAir) through its public operations and the equipment points (WfEquipment),
## and advances each of the eight steps from the model's state and the trainee's own actions. It owns no engineering value and decides
## no physics: the model refuses unsafe operations, and the stability watch is the same model run forward. No score is kept.
##
## Interaction (no new action): Use at the bay inspects the unit (and pages through the evidence), or installs a carried spare; Use at
## the sector 2 workbench takes the spare; Ops at the bay isolates or restores the unit, starts the watch once restored, and replays
## the training after it ends.

const FILE := "res://generated/wf_deadship_ds1.json"
const DT_REF := 1.0               # the reference replay's event step (deadship.reference)
const DT_WATCH_REF := 60.0        # and its watch step

var doc := {}
var sc := {}
var eq: WfEquipment = null
var air: WfCabinAir = null
var host: Node = null
var verified := false
var errors: Array = []

var index := 0                    # the current step (0..7); 8 when the run has ended
var flags := {}                   # inspected, diagnosed, watch_passed
var page := -1                    # -1 no page; 0 the inspection overview; 1.. the evidence pages; 100 the debrief
var watching := false
var watch_t0 := 0.0
var watch_x_max := 0.0
var watch_reached := false
var watch_result := {}
var result := ""                  # "" running, PASS (stable) or FAIL (operational failure)
var t0_ship := 0.0                # the model's clock when the trainee started
var real_s := 0.0                 # real seconds played
var runs := 0
var events: Array = []            # [real_s, ship_s, what] for the record and the debrief

var panel := PanelContainer.new()
var rendered_compact := false                     # the page's text was laid out for a touch-first screen
var text := RichTextLabel.new()
var carried := MeshInstance3D.new()   # small runtime placeholders (no exported geometry changes): the spare on the bench / in hand
var on_bench := MeshInstance3D.new()

func _init(by_name: Dictionary, manifest: Dictionary, owner: Node, layer: CanvasLayer) -> void:
	host = owner
	if not FileAccess.file_exists(FILE):
		errors = ["%s is not in the package; run runtime-export" % FILE]
		return
	doc = JSON.parse_string(FileAccess.get_file_as_string(FILE))
	sc = doc["scenario"]
	eq = WfEquipment.new(by_name, manifest, owner)
	air = eq.air
	if air == null or not eq.ready():
		errors = ["the CO2 model is missing or does not reproduce its reference: %s" % (str(air.errors) if air != null else "no package")]
		return
	if int(doc["model"]["version"]) != int(air.doc["version"]) or str(doc["model"]["schema"]) != str(air.doc["schema"]):
		errors = ["scenario built for model %s v%s, package has %s v%s" % [doc["model"]["schema"], doc["model"]["version"], air.doc["schema"], air.doc["version"]]]
		return
	var bench: Dictionary = sc["bench"]
	if not eq.add_point("bench", str(bench["node"]), float(bench["reach_m"]), str(air.doc["binding"]["ring"])):
		errors = ["the workbench node %s is not in the package" % bench["node"]]
		return
	errors = replay()
	verified = errors.is_empty()
	_build_ui(layer)
	_build_parts()
	if verified:
		begin()

# ---- the run ---------------------------------------------------------------------------------------------------------------------------------

## The model state the trainee meets (deadship.begin): the initial state, the fault, then fault_lead_h ship hours with no input.
func _begin_model() -> void:
	var ini: Dictionary = sc["initial"]
	air.reset(str(ini["mode"]), str(ini["fan"]), str(ini["spare"]))
	var r := air.operate(str(ini["fault"]))
	assert(r == "", r)
	air.step(float(ini["fault_lead_h"]) * 3600.0)

## Start (or replay) the training.
func begin() -> void:
	_begin_model()
	t0_ship = air.t_s
	index = 0
	flags = {}
	page = -1
	watching = false
	watch_result = {}
	result = ""
	real_s = 0.0
	runs += 1
	events = []
	eq.timelapse = float(sc["time"]["scale"])
	eq.paused = false
	eq.operations = 0
	_close()
	_event("start")
	_parts_visible()
	eq.update()

func ended() -> bool:
	return result != ""

func current() -> Dictionary:
	return sc["steps"][mini(index, 7)]

func _event(what: String) -> void:
	events.append([snappedf(real_s, 0.01), snappedf(air.t_s - t0_ship, 0.01), what])
	if host != null and host.has_method("_log"):
		host.call("_log", "deadship", {"what": what, "step": current()["id"], "index": index})

func _cond(c: String) -> bool:
	var kind := c.get_slice(":", 0)
	var v := c.get_slice(":", 1)
	if kind == "at":
		return eq.in_reach(host.get("actor").global_position, str(host.get("walk_zone")), v)
	if kind == "flag":
		return flags.get(v, false)
	return air.field(kind) == v

func _done(st: Dictionary) -> bool:
	for c in st["done"]:
		if not _cond(str(c)):
			return false
	return true

## The pause rule ([time] pause): the model's clock stops while a tutorial page or the controls menu is open, and after the run ends.
func _pause_now() -> bool:
	if ended() or page >= 0:
		return true
	return WfInput.overlay != null and WfInput.overlay.is_modal()

func step(dt: float) -> void:
	if not verified:
		return
	if not ended():
		real_s += dt
	if watching:
		_step_watch(dt)
	else:
		eq.paused = _pause_now()
		eq.step(dt)
		if not ended() and air.x() > float(air.p["co2_max"]):
			_finish("FAIL")
	while not ended() and index < 8 and _done(current()):
		_event("done " + str(current()["id"]))
		index += 1
		if index < 8:
			_say("Step %d · %s: %s" % [index + 1, current()["title"], fill(str(current()["objective"]))])
	if page >= 0 and page < 100 and not eq.in_reach(host.get("actor").global_position, str(host.get("walk_zone")), "bay"):
		_close()                                  # a page closes when the trainee walks away (as a learning station does)
	carried.visible = air.spare == "CARRIED"
	eq.update()

# ---- the stability watch -------------------------------------------------------------------------------------------------------------------------

func _start_watch() -> String:
	watching = true
	watch_t0 = air.t_s
	watch_x_max = air.x()
	watch_reached = false
	eq.timelapse = float(sc["time"]["watch_scale"])
	eq.paused = false
	_close()
	_event("watch start")
	return "Stability watch: the model runs %s ship hours forward with nobody touching the unit (x%d)." % [str(sc["watch"]["ship_h"]), int(eq.timelapse)]

func _step_watch(dt: float) -> void:
	var left := float(sc["watch"]["ship_h"]) * 3600.0 - (air.t_s - watch_t0)
	air.step(minf(dt * eq.timelapse, left))
	watch_x_max = maxf(watch_x_max, air.x())
	watch_reached = watch_reached or air.x() > float(air.p["co2_max"])
	if left - dt * eq.timelapse <= 1e-9:
		watch_result = verdict(watch_reached)
		watching = false
		eq.timelapse = float(sc["time"]["scale"])
		_event("watch " + ("PASS" if watch_result["passed"] else "FAIL"))
		if watch_result["passed"]:
			flags["watch_passed"] = true
			_finish("PASS")
		else:
			_say("Stability watch failed: the unit does not hold the ring at or below the target. Check it and run the watch again.")

## The watch verdict (deadship.watch): removing, never reached the control limit, ended at or below the target, steady state too.
func verdict(reached: bool) -> Dictionary:
	var r := air.readout()
	var xs = air.steady_x() if r["removing"] else null
	var ok: bool = r["removing"] and not reached and float(r["x"]) <= float(air.p["co2_target"]) and xs != null and float(xs) <= float(air.p["co2_target"])
	return {"passed": ok, "x_end": r["x"], "steady_x": xs, "removing": r["removing"], "dxdt_per_h": r["dxdt_per_h"]}

func _finish(how: String) -> void:
	result = how
	index = 8 if how == "PASS" else index
	eq.paused = true
	_event("end " + how)
	page = 100
	_render()

# ---- the trainee's actions --------------------------------------------------------------------------------------------------------------------

func _at() -> String:
	if host.get("move") != "WALK":
		return ""
	return eq.point_in_reach(host.get("actor").global_position, str(host.get("walk_zone")))

## Use at a point: "" when no point is in reach, or a door or the ladder is the walk's target (the walk's own Use then applies, as a
## door wins over a learning station).
func use() -> String:
	if not verified or _door_first():
		return ""
	var at := _at()
	if at == "bench":
		if air.spare == "BENCH":
			var r := eq.request("take_spare")
			_event("take_spare" if not r.begins_with("ECLSS: refused") else "refused take_spare")
			_parts_visible()
			_say(r.replace("ECLSS: ", "Workbench: "))
			return "take_spare"
		_say("Workbench: %s" % ("you carry the spare fan." if air.spare == "CARRIED" else "nothing for you here."))
		return "bench"
	if at != "bay":
		return ""
	if ended():
		page = 100 if page != 100 else -1
		_render()
		return "debrief"
	if air.spare == "CARRIED":
		var r2 := eq.request("install_spare")
		_event("install_spare" if not r2.begins_with("ECLSS: refused") else "refused install_spare")
		_say(r2)
		return "install_spare"
	# inspection: the overview, then each evidence page, then closed
	var n: int = sc["evidence"].size()
	page = 0 if page < 0 else (page + 1 if page < n else -1)
	if page == 0:
		flags["inspected"] = true
		_event("inspect")
	if page == n:
		flags["diagnosed"] = true
		_event("diagnosed")
	_render()
	return "inspect %d" % page

## Ops at the bay: "" when the bay is not in reach (the walk's own Ops then applies).
func ops() -> String:
	if not verified or _at() != "bay":
		return ""
	if ended():
		begin()
		_say("Training restarted: " + fill(str(current()["objective"])))
		return "replay"
	if watching:
		return "watching"
	if index == 7 and air.removing():
		_say(_start_watch())
		return "watch"
	var op := eq.next_op()
	var r := eq.request(op)
	_event(op if not r.begins_with("ECLSS: refused") else "refused " + op)
	_say(r)
	return op

## A door (or the ladder) keeps Use when the trainee looks more towards it than towards the training point in reach.
func _door_first() -> bool:
	if page >= 0:
		return false
	var w := str(host.call("_walk_target"))
	if w == "":
		return false
	var at := _at()
	if at == "":
		return true
	var eye: Vector3 = host.get("actor").global_position
	var fwd: Vector3 = -(host.call("look_basis") as Basis).z
	var to_point := eq.centre(at) - eye
	var to_door: Vector3 = (host.get("lines")["ACCESS_A"].p[-1] if w == "ladder" else (host.get("circ_doors")[w]["collider"] as Node3D).global_position) - eye
	return fwd.angle_to(to_door) < fwd.angle_to(to_point)

func use_label() -> String:
	if _door_first():
		return ""
	var at := _at()
	if at == "bench":
		return "Use · take spare fan" if air.spare == "BENCH" else ""
	if at != "bay":
		return ""
	if ended():
		return "Use · debrief"
	if air.spare == "CARRIED":
		return "Use · install spare fan"
	return "Use · inspect" if page < 0 else ("Use · next reading" if page < sc["evidence"].size() else "Use · close")

func ops_label() -> String:
	if _at() != "bay":
		return ""
	if ended():
		return "Ops · replay training"
	if watching:
		return ""
	if index == 7 and air.removing():
		return "Ops · stability watch"
	return "Ops · " + ("isolate unit" if air.mode == "RUNNING" else "restore unit")

# ---- text ---------------------------------------------------------------------------------------------------------------------------------------

func _hm(h) -> String:
	if h == null:
		return "not approaching"
	var mins := int(round(float(h) * 60.0))
	return "%d h %02d min" % [mins / 60, mins % 60]

## The scenario's texts with the model's present values (never a fixed number).
func fill(t: String) -> String:
	var r := air.readout()
	var d := air.diagnostics()
	var p := air.p
	var none_to := func(kpa: float) -> String:
		var x_to := kpa * 1000.0 / float(p["P_Pa"])
		return _hm(air.hours_between(air.x(), x_to)) + " (ship time, from now)" if air.x() < x_to else "reached"
	var use_k: String = host.call("key", "exc.use") if host != null else "Use"
	var ops_k: String = host.call("key", "exc.ops") if host != null else "Ops"
	var gen := float(p["occupants"]) * float(p["per_person_kg_s"]) * 3600.0
	return t.format({"x": "%.3f" % (100.0 * float(r["x"])), "trend": "%+.3f %%" % (100.0 * float(r["dxdt_per_h"])),
		"target": "%.1f" % (100.0 * float(p["co2_target"])), "limit": "%.1f" % (100.0 * float(p["co2_max"])),
		"limit_time": _hm(r["hours_to_control_limit"]) + " of ship time" if r["hours_to_control_limit"] != null else "not approaching",
		"use": use_k, "ops": ops_k, "watch_h": str(sc["watch"]["ship_h"]),
		"supply": d["supply"], "controller": d["controller"], "fan_command": d["fan_command"], "fan_speed": "%d" % int(d["fan_speed_pct"]),
		"flow": "%.0f" % float(d["scrubbed_flow_m3_h"]), "bed": d["bed"], "removal": "%.3f" % float(d["removal_kg_h"]),
		"gen": "%.2f" % gen, "k": "%.0f" % (float(p["k_m3_s"]) * 3600.0), "steady": "%.3f" % (100.0 * air.steady_x()),
		"degraded_kpa": "%.1f" % air.band_kpa("DEGRADED"), "danger_kpa": "%.1f" % air.band_kpa("DANGER"),
		"to_degraded": none_to.call(air.band_kpa("DEGRADED")), "to_danger": none_to.call(air.band_kpa("DANGER"))})

func _say(t: String) -> void:
	if host != null:
		host.call("say", t)

## The goal line on the HUD.
func goal_text() -> String:
	if not verified:
		return "DEADSHIP TRAINING unavailable: " + (str(errors[0]) if not errors.is_empty() else "")
	var head := "DEADSHIP TRAINING · %s %s (simulation, unscored)" % [sc["scenario"]["id"], sc["scenario"]["name"]]
	if result == "PASS":
		return head + " · COMPLETE: the ring is stable. " + fill(str(sc["debrief"]["replay"]))
	if result == "FAIL":
		return head + " · OPERATIONAL FAILURE: the control limit was passed. " + fill(str(sc["debrief"]["replay"]))
	if watching:
		return head + " · Step 8 · Verify: stability watch running (%.1f of %s ship hours)" % [(air.t_s - watch_t0) / 3600.0, str(sc["watch"]["ship_h"])]
	var carry := " · Carrying: the spare fan." if air.spare == "CARRIED" else ""
	return "%s · Step %d of 8 · %s: %s%s" % [head, index + 1, current()["title"], fill(str(current()["objective"])), carry]

## The hint and the step list for the HUD's side block.
func lines() -> Array:
	var out := []
	for i in 8:
		var st: Dictionary = sc["steps"][i]
		out.append("%s %d %s" % ["[x]" if i < index else ("[>]" if i == index and not ended() else "[ ]"), i + 1, st["title"]])
	if not ended():
		out.append("Hint: " + fill(str(current()["hint"])))
	return out

func _build_ui(layer: CanvasLayer) -> void:
	var back := StyleBoxFlat.new()                 # the learning stations' panel look (WfLearning)
	back.bg_color = Color(0.02, 0.04, 0.08, 0.94)
	back.border_color = Color(0.75, 0.55, 0.25)
	back.set_border_width_all(2)
	back.set_content_margin_all(14.0)
	panel.add_theme_stylebox_override("panel", back)
	panel.mouse_filter = Control.MOUSE_FILTER_IGNORE
	text.bbcode_enabled = true
	text.fit_content = true
	text.scroll_active = false
	text.mouse_filter = Control.MOUSE_FILTER_IGNORE
	text.custom_minimum_size = Vector2(540, 0)
	text.add_theme_font_size_override("normal_font_size", 15)
	text.add_theme_font_size_override("bold_font_size", 16)
	panel.add_child(text)
	panel.visible = false
	if layer != null:
		layer.add_child(panel)

func _close() -> void:
	page = -1
	panel.visible = false

func _render() -> void:
	if page < 0:
		panel.visible = false
		return
	var out := []
	var ev: Array = sc["evidence"]
	var tabs := []
	for i in 8:
		var st: Dictionary = sc["steps"][i]
		tabs.append(("[b][color=#ffd27a]%d %s[/color][/b]" if i == mini(index, 7) and not ended() else "[color=#7f8fa8]%d %s[/color]") % [i + 1, st["title"]])
	var small := WfInput.compact()                 # a phone: the step in the title, no tab row, no spacer lines, a one-line source note
	if small:
		out.append("[b]DEADSHIP · %s %s[/b] · %s" % [sc["scenario"]["id"], sc["scenario"]["name"],
			"debrief" if ended() else "step %d of 8 · %s" % [mini(index, 7) + 1, sc["steps"][mini(index, 7)]["title"]]])
	else:
		out.append("[b]DEADSHIP TRAINING · %s %s[/b]  [color=#9fb4d0](simulation, unscored)[/color]" % [sc["scenario"]["id"], sc["scenario"]["name"]])
		out.append("[font_size=12]" + "  ".join(tabs) + "[/font_size]")
		out.append("")
	if page == 100:
		var pass_run := result == "PASS"
		out.append("[b]%s · %s[/b]" % [sc["debrief"]["title"], "the ring is stable" if pass_run else "operational failure"])
		for l in sc["debrief"]["pass" if pass_run else "fail"]:
			out.append("· " + fill(str(l)))
		out.append("")
		out.append("[color=#9fb4d0]Played %d min real time, %.1f h of ship time. %s[/color]" % [int(real_s / 60.0), (air.t_s - t0_ship) / 3600.0,
			fill(str(sc["debrief"]["replay"]))])
	elif page == 0:
		var d := air.diagnostics()
		var r := air.readout()
		out.append("[b]Inspect · ring A CO2-removal unit[/b]")
		out.append("[i]GU instructor: symptoms first. Read what the unit reports before you guess.[/i]")
		out.append("Unit %s · supply %s · CO2 %.3f %% (%s %%/h)" % [air.mode, d["supply"], 100.0 * float(r["x"]), "%+.3f" % (100.0 * float(r["dxdt_per_h"]))])
		out.append("Removal now %.3f kg/h against the crew's %.2f kg/h: the unit is %s." % [float(d["removal_kg_h"]),
			float(air.p["occupants"]) * float(air.p["per_person_kg_s"]) * 3600.0, "removing CO2" if air.removing() else "not removing CO2"])
		out.append("")
		out.append("[color=#9fb4d0]%s for the evidence, one reading at a time.[/color]" % (host.call("key", "exc.use") if host != null else "Use"))
	else:
		var e: Dictionary = ev[page - 1]
		out.append("[b]Evidence %d of %d · %s[/b]" % [page, ev.size(), str(e["id"]).capitalize()])
		out.append(fill(str(e["reading"])))
		out.append("")
		out.append("[i]" + fill(str(e["meaning"])) + "[/i]")
		if page == ev.size():
			out.append("")
			out.append("[color=#9fb4d0]Next: " + fill(str(sc["steps"][3]["objective"])) + "[/color]")
	if small:
		out = out.filter(func(l): return l != "")
		out.append("[color=#8090a0]Simulation, unscored · PROTOTYPE values · 0.5 % limit WORKING canon[/color]")
	else:
		out.append("")
		out.append("[font_size=12][color=#8090a0]Engineering model: ring A cabin CO2 (src/wayfarer/cabin_air.py); volume, occupancy, unit rating and the "
			+ "degraded / danger levels are PROTOTYPE, the 0.5 %% control limit is WORKING canon. Scenario %s: %s.[/color][/font_size]" % [doc["source"], sc["scenario"]["status"]])
	text.text = "\n".join(out)
	rendered_compact = small
	panel.visible = true
	panel.reset_size()

func update_panel(size: Vector2) -> void:
	if panel.visible and WfInput.compact() != rendered_compact:
		_render()                                  # the screen changed between desktop and touch layouts (a resize or a first touch)
	WfPagePanel.place(panel, text, size, 540.0)

# ---- the spare's placeholder ---------------------------------------------------------------------------------------------------------------------

func _build_parts() -> void:
	for m in [carried, on_bench]:
		var box := BoxMesh.new()
		box.size = Vector3(0.30, 0.30, 0.22)        # PROTOTYPE stand-in for a fan cartridge (the ECLSS parts are OPEN, 12!G26:G27)
		var mat := StandardMaterial3D.new()
		mat.albedo_color = Color(0.95, 0.60, 0.20)
		box.material = mat
		m.mesh = box
	var actor: Node3D = host.get("actor")
	if actor != null:
		actor.add_child(carried)
		carried.position = Vector3(0.0, 1.3, -0.45)  # held in front at chest height (the actor's frame: -Z forward): about 34 deg under the
		                                             # eyes, inside the 75 deg view (at waist height it was out of the first-person view)
	var bench: MeshInstance3D = eq.points["bench"]["mesh"]
	bench.add_child(on_bench)
	on_bench.position = eq.above(bench, 0.16)
	_parts_visible()

func _parts_visible() -> void:
	carried.visible = air != null and air.spare == "CARRIED"
	on_bench.visible = air != null and air.spare == "BENCH"

# ---- the reference replay -------------------------------------------------------------------------------------------------------------------------

## The model-level ideal run (deadship.reference) on this runtime: the same begin, the reference events at 1 s steps, the watch at 60 s
## steps; every event's CO2 mass and state and the watch verdict must match the packaged reference within the model's tolerance.
func replay() -> Array:
	var bad := []
	var ref: Dictionary = doc["reference"]
	var tol: Dictionary = air.doc["tolerance"]
	var keep := air.save()
	_begin_model()
	var close := func(a: float, b: float) -> bool: return absf(a - b) <= float(tol["abs_kg"]) + float(tol["rel"]) * absf(b)
	if not close.call(air.m_kg, float(ref["start_m_kg"])):
		bad.append("start: m %s kg, reference %s" % [str(air.m_kg), str(ref["start_m_kg"])])
	var t0 := air.t_s
	var evs := []
	for e in sc["reference"]["events"]:
		evs.append([t0 + float(e[0]), str(e[1])])
	var end_t: float = evs[-1][0]
	var got := []
	while true:
		while not evs.is_empty() and air.t_s >= float(evs[0][0]) - 1e-9:
			var e: Array = evs.pop_front()
			var r := air.operate(e[1])
			if r != "":
				bad.append("reference event %s refused: %s" % [e[1], r])
			got.append({"op": e[1], "m_kg": air.m_kg, "mode": air.mode, "fan": air.fan, "spare": air.spare})
		if air.t_s >= end_t - 1e-9:
			break
		air.step(DT_REF)
	var want: Array = ref["events"]
	if got.size() != want.size():
		bad.append("%d reference events replayed, %d packaged" % [got.size(), want.size()])
	for i in mini(got.size(), want.size()):
		if not close.call(float(got[i]["m_kg"]), float(want[i]["m_kg"])) or [got[i]["mode"], got[i]["fan"], got[i]["spare"]] != [want[i]["mode"], want[i]["fan"], want[i]["spare"]]:
			bad.append("reference event %s: %s, reference %s" % [want[i]["op"], str(got[i]), str(want[i])])
	var n := int(round(float(sc["watch"]["ship_h"]) * 3600.0 / DT_WATCH_REF))
	var reached := false
	for i in n:
		air.step(DT_WATCH_REF)
		reached = reached or air.x() > float(air.p["co2_max"])
	var w := verdict(reached)
	var ww: Dictionary = ref["watch"]
	if bool(w["passed"]) != bool(ww["passed"]) or absf(float(w["x_end"]) - float(ww["x_end"])) > float(tol["rel"]) * float(ww["x_end"]) + 1e-15:
		bad.append("watch %s, reference %s" % [str(w), str(ww)])
	air.load_state(keep)
	return bad

## The browser / headless record (window.wayfarerWalk.deadship).
func record() -> Dictionary:
	return {"verified": verified, "errors": errors.slice(0, 2), "step": current()["id"] if verified else "", "index": index, "flags": flags.keys(),
		"page": page, "watching": watching, "result": result, "runs": runs, "real_s": snappedf(real_s, 0.01),
		"ship_h": snappedf((air.t_s - t0_ship) / 3600.0, 0.0001) if air != null else 0.0, "events": events.slice(-12),
		"watch": watch_result, "unit": eq.record() if eq != null else {}}
