class_name WfDroneDemo
extends RefCounted
## DRONE-001 maintenance drone demonstration (S&E 54 DGT-013/014, Tale 29 DN-11, Eye 46 EYS-DR-10): the drones hotspot's SHOW ME page in
## the Ship Navigator. Data: the rig block `drones` (src/wayfarer/drone_fleet.py, drone_demo.py): the study fleet's docks and tracks, and the
## WF_DRONE_SCENARIO run of the spine utility crawler DR-EVA-03-U03 on its DS-13 track. The guidance mode (J) sets how it plays:
##   GUIDED    Z play / restart the selected run (explainer time)
##   ASSISTED  Z next frame · Y previous frame
##   FREE      Z jog forward · Y jog aft along the track (stops at the track ends; the ring A keep-out is the forward end)
## X next run (nominal, power loss, rail jam, lost link) · K what-if ship configuration (the 53 DOP gate; display only).
## C route overlay (S&E 54 DGT-009, rig `drones.routes`, drone_routes.py): OFF, all classes, then one class at a time. ROUTED legs as tubes;
## each job target coloured by status (ROUTED / CARRIED / HOLD / PROHIBITED) with a dashed line for the reach a tool would need from the route
## (reach OPEN: a measurement for the owner, not a capability). The interior classes are listed on the card only.
## Markers are not to scale. SIMULATION ONLY: no speed, energy, mass or rating is shown because none exists; nothing here changes the ship
## state, a route or an access gate (remote view only, NAV-014).

const JOG_M := 5.0
const MARK_R := 0.9                  # display radius of dock markers (not to scale)
const UNIT_SIZE := 1.6               # display crawler box edge (not to scale; the proxy is 0.70 m)

var nav                              # WfShipNavigator
var fleet: Dictionary
var sc: Dictionary
var run := 0                         # 0 nominal, 1.. faults
var cfg := 0                         # index into CONFIGS
var configs: Array = []
var playing := false
var t := 0.0                         # display seconds into the run
var free_x := 0.0
var root := Node3D.new()
var crawler := MeshInstance3D.new()
var helper := MeshInstance3D.new()
var labels := {}
var dock_count := 0
var routes: Dictionary
var route_view := 0                  # 0 off, 1 all, 2.. one class (route_ids)
var route_ids: Array = []            # classes with vehicle-frame geometry
var route_root := Node3D.new()
var route_nodes := {}                # class id -> Node3D
var reach_drawn: Array = []          # [class, target, drawn length m, reach_needed_m]

func _init(n) -> void:
	nav = n
	var d: Dictionary = nav.host.rig_all.get("drones", {})
	fleet = d.get("fleet", {})
	sc = d.get("demo", {})
	routes = d.get("routes", {})
	if not sc.is_empty():
		configs = sc["config_gates"].keys()
		configs.sort()
		cfg = maxi(configs.find("COAST"), 0)
		free_x = float(sc["track"]["dock_x_m"][2])

func ready() -> bool:
	return not fleet.is_empty() and not sc.is_empty()

func active() -> bool:
	return ready() and nav.card_page == 2 and str(nav.hotspot.get("id", "")) == "WF.HOTSPOT.DRONES"

## Blender ship coordinates (x, y, z) -> the stationary map frame (runtime axes x, z, -y).
func _p(v: Array) -> Vector3:
	return Vector3(float(v[0]), float(v[2]), -float(v[1]))

## A point on the spine track at ship X (the casing radius interpolated between the track ends, at the track azimuth).
func track_point(x: float) -> Vector3:
	var tr: Dictionary = sc["track"]
	var a := deg_to_rad(float(tr["azimuth_deg"]))
	var r0: Array = tr["surface_r_m"][0]
	var r1: Array = tr["surface_r_m"][1]
	var r := lerpf(float(r0[1]), float(r1[1]), clampf((x - float(r0[0])) / (float(r1[0]) - float(r0[0])), 0.0, 1.0))
	return _p([x, r * cos(a), r * sin(a)])

func build() -> void:
	if not ready():
		return
	nav.map_root.add_child(root)
	var dock_mat: Material = nav._flat(nav.pal["structure"])
	for st in fleet["stations"]:
		if st["frame"] != "VEHICLE":
			continue
		for d in st["docks"] + st["existing"]:
			var c: Array = d["center_m"] if d["shape"] == "box" else d["a_m"]
			var mi := MeshInstance3D.new()
			var sm := SphereMesh.new()
			sm.radius = MARK_R
			sm.height = 2.0 * MARK_R
			mi.mesh = sm
			mi.material_override = nav._flat(nav.pal["caution"]) if str(d["name"]).begins_with("Drone_ArmBase") else dock_mat
			mi.position = _p(c)
			root.add_child(mi)
			dock_count += 1
		for rl in st["rails"]:
			var pts := PackedVector3Array()
			for q in rl["points_m"]:
				pts.append(_p(q))
			var tube := MeshInstance3D.new()
			tube.mesh = nav._tube(pts, 0.3)
			tube.material_override = nav._flat(nav.pal["structure_faint"])
			root.add_child(tube)
		var all: Array = st["docks"] + st["existing"]
		if not all.is_empty():
			var first: Dictionary = all[0]
			var l: Label3D = nav._label(24, nav.pal["quiet"], 24)
			l.text = "%s %s" % [st["id"], st["cls"]]
			l.position = _p(first["center_m"] if first["shape"] == "box" else first["a_m"]) + Vector3(0, 2.2, 0)
			root.add_child(l)
	for m in [crawler, helper]:
		var bm := BoxMesh.new()
		bm.size = Vector3.ONE * UNIT_SIZE
		m.mesh = bm
		root.add_child(m)
	crawler.material_override = nav._flat(nav.pal["go"])
	helper.material_override = nav._flat(nav.pal["player"])
	for k in ["unit", "state", "target", "scale"]:
		labels[k] = nav._label(30, nav.pal["text"], 30)
		root.add_child(labels[k])
	_build_routes()
	root.visible = false

func _status_color(st: String) -> Color:
	match st:
		"ROUTED": return nav.pal["go"]
		"CARRIED": return nav.pal["player"]
		"PROHIBITED": return nav.pal["danger"]
	return nav.pal["caution"]

func _build_routes() -> void:
	if routes.is_empty():
		return
	root.add_child(route_root)
	for g in routes["classes"]:
		var node := Node3D.new()
		var drawn := false
		for e in g["edges"]:
			if e.has("points_m") and e["status"] == "ROUTED":
				var pts := PackedVector3Array()
				for q in e["points_m"]:
					pts.append(_p(q))
				var tube := MeshInstance3D.new()
				tube.mesh = nav._tube(pts, 0.45)
				tube.material_override = nav._flat(nav.pal["go"])
				node.add_child(tube)
				drawn = true
		for job in g["jobs"]:
			for tg in g["jobs"][job]:
				if not tg.has("point_m"):
					continue
				var a := _p(tg["point_m"])
				var b := _p(tg["from_m"])
				var mi := MeshInstance3D.new()
				var sm := SphereMesh.new()
				sm.radius = 0.7
				sm.height = 1.4
				mi.mesh = sm
				mi.material_override = nav._flat(_status_color(str(tg["status"])))
				mi.position = a
				node.add_child(mi)
				var line := MeshInstance3D.new()
				line.mesh = nav._tube_pairs(nav._dashed(PackedVector3Array([b, a]), 1.0), 0.15)
				line.material_override = nav._flat(nav.pal["quiet"])
				node.add_child(line)
				var l: Label3D = nav._label(22, nav.pal["text"], 22)
				l.text = "%s m" % String.num(float(tg["reach_needed_m"]), 1)
				l.position = a.lerp(b, 0.5) + Vector3(0, 1.4, 0)
				node.add_child(l)
				reach_drawn.append([g["cls"], tg["target"], a.distance_to(b), float(tg["reach_needed_m"])])
				drawn = true
		if drawn:
			route_ids.append(g["cls"])
			route_nodes[g["cls"]] = node
			route_root.add_child(node)
	route_root.visible = false

func route_name() -> String:
	if route_view == 0:
		return "OFF"
	return "ALL" if route_view == 1 else str(route_ids[route_view - 2])

func _show_routes() -> void:
	route_root.visible = route_view > 0
	for k in route_nodes:
		route_nodes[k].visible = route_view == 1 or k == route_name()

# ------------------------------------------------------------------------------------------------------------------- state

func frames() -> Array:
	return sc["nominal"] if run == 0 else sc["faults"][run - 1]["frames"]

func gate() -> Dictionary:
	return sc["config_gates"][configs[cfg]]

func permitted() -> bool:
	return str(gate()["gate"]).begins_with("PERMITTED")

## Frames the selected configuration lets the run reach: a run outside a permitted configuration stops at its precheck, docked.
func reach() -> int:
	if permitted():
		return frames().size()
	return mini(2, frames().size()) if run == 0 else 1

func index() -> int:
	return mini(int(t / float(sc["step_display_s"])), reach() - 1)

func finished() -> bool:
	return t >= float(sc["step_display_s"]) * reach() - 1e-6

func mode() -> String:
	return str(nav.mode_id)

func reset() -> void:
	run = 0
	cfg = maxi(configs.find("COAST"), 0)
	playing = false
	t = 0.0
	free_x = float(sc["track"]["dock_x_m"][2]) if ready() else 0.0
	route_view = 0
	_show_routes()
	root.visible = false

func key(code: int) -> bool:
	if not active():
		return false
	var step := float(sc["step_display_s"])
	match code:
		KEY_X:
			run = (run + 1) % (sc["faults"].size() + 1)
			playing = false
			t = 0.0
		KEY_K:
			cfg = (cfg + 1) % configs.size()
			playing = false
			t = 0.0
		KEY_C:
			if routes.is_empty():
				return false
			route_view = (route_view + 1) % (route_ids.size() + 2)
			_show_routes()
		KEY_Z:
			match mode():
				"GUIDED":
					playing = true
					t = 0.0
				"FREE": free_x = _clamp_x(free_x + JOG_M)
				_: t = minf((index() + 1) * step, step * (reach() - 1))
		KEY_Y:
			match mode():
				"FREE": free_x = _clamp_x(free_x - JOG_M)
				"GUIDED": return false
				_: t = maxf((index() - 1) * step, 0.0)
		_: return false
	return true

func _clamp_x(x: float) -> float:
	if not permitted():
		return float(sc["track"]["dock_x_m"][2])
	return clampf(x, float(sc["track"]["x0_m"]), float(sc["track"]["x1_m"]))

func advance(dt: float) -> void:
	if playing:
		t = minf(t + dt, float(sc["step_display_s"]) * reach())
		playing = t < float(sc["step_display_s"]) * reach()

## The crawler's ship X now: FREE follows the jog; otherwise between the previous and the current frame.
func unit_x() -> float:
	if mode() == "FREE":
		return free_x
	var fr := frames()
	var i := index()
	var frac := clampf(t / float(sc["step_display_s"]) - i, 0.0, 1.0)
	var x0: float = float(fr[maxi(i - 1, 0)]["x_m"])
	return lerpf(x0, float(fr[i]["x_m"]), frac) if i > 0 else float(fr[0]["x_m"])

func helper_x() -> float:
	var f: Dictionary = frames()[index()]
	if mode() == "FREE" or not f.has("helper_from_x_m"):
		return NAN
	var frac := clampf(t / float(sc["step_display_s"]) - index(), 0.0, 1.0)
	return lerpf(float(f["helper_from_x_m"]), float(f["x_m"]) - 1.0, frac)

func update() -> void:
	if not active():
		if root.visible:
			reset()
		return
	if not root.visible:
		cfg = maxi(configs.find(nav.ship_mode()), configs.find("COAST"))   # opens on the ship's own configuration (what-if with K)
	root.visible = true
	var x := unit_x()
	crawler.position = track_point(x) + Vector3(0, UNIT_SIZE * 0.5, 0)
	var hx := helper_x()
	helper.visible = not is_nan(hx)
	if helper.visible:
		helper.position = track_point(hx) + Vector3(0, UNIT_SIZE * 0.5, 0)
	var f: Dictionary = frames()[index()]
	labels["unit"].position = crawler.position + Vector3(0, 3.0, 0)
	labels["unit"].text = "%s · %s" % [sc["unit"], "FREE JOG" if mode() == "FREE" else f["state"]]
	labels["state"].position = crawler.position + Vector3(0, 5.2, 0)
	labels["state"].text = "%s %s" % [configs[cfg], gate()["gate"]]
	labels["state"].modulate = nav.pal["go"] if permitted() else nav.pal["caution"]
	labels["target"].position = _p(sc["target"]["point_m"]) + Vector3(0, 2.5, 0)
	labels["target"].text = "inspection target"
	labels["scale"].position = track_point(float(sc["track"]["x1_m"])) + Vector3(0, 4.0, 0)
	labels["scale"].text = "track end · ring A keep-out · markers not to scale"

# ------------------------------------------------------------------------------------------------------------------- text

func text() -> String:
	var s := "\nMAINTENANCE DRONE DEMO · %s · %s\n" % [mode(), sc["status"]]
	var fl: Dictionary = {"id": "NOMINAL", "title": "Service run"} if run == 0 else sc["faults"][run - 1]
	s += "%s (%s) · %s · %s\n" % [fl["title"], fl["id"], sc["unit"], sc["time"]]
	s += "Ship configuration %s: %s  [%s]\n" % [configs[cfg], gate()["gate"], gate()["rule"]]
	if mode() == "FREE":
		s += "FREE jog: X %s m on the %s m track (%s to %s m)\n" % [String.num(free_x, 1), String.num(float(sc["track"]["x1_m"]) - float(sc["track"]["x0_m"]), 0), String.num(float(sc["track"]["x0_m"]), 1), String.num(float(sc["track"]["x1_m"]), 1)]
	else:
		var f: Dictionary = frames()[index()]
		s += "%d/%d %s · %s\n  %s  [%s]\n" % [index() + 1, frames().size(), f["state"], f["title"], f["text"], f["rule"]]
		if not f["open"].is_empty():
			s += "  ? OPEN: %s\n" % ", ".join(f["open"])
		if not permitted() and index() == reach() - 1:
			s += "  HOLD: the run stops here in %s; the crawler stays latched.\n" % configs[cfg]
	s += "Fleet (study): %d mobile + %d arms at %d proposed docks · mass, power, speed OPEN\n" % [fleet["units"].filter(func(u): return u["domain"] != "FIXED").size(), fleet["units"].filter(func(u): return u["domain"] == "FIXED").size(), dock_count]
	s += route_text()
	match mode():
		"GUIDED": s += WfInput.keys("{explorer.next} run · {explorer.step} configuration · {explorer.back} play · {explorer.cycle} routes")
		"FREE": s += WfInput.keys("{explorer.next} run · {explorer.step} configuration · {explorer.back} / {explorer.view} jog fwd / aft · {explorer.cycle} routes")
		_: s += WfInput.keys("{explorer.next} run · {explorer.step} configuration · {explorer.back} next · {explorer.view} back · {explorer.cycle} routes")
	return s

## The route overlay's card section: per class the legs by status and, for one class, every job target with the reach it would need.
func route_text() -> String:
	if routes.is_empty() or route_view == 0:
		return ""
	var s := "ROUTES (DGT-009 HOLD · %s) · %s · reach OPEN: measured need, not capability\n" % [routes["status"].split(",")[0], route_name()]
	for g in routes["classes"]:
		if route_view > 1 and g["cls"] != route_name():
			continue
		var n := {"ROUTED": 0, "CARRIED": 0, "HOLD": 0, "PROHIBITED": 0}
		var routed := 0.0
		var swept := INF
		for e in g["edges"]:
			n[e["status"]] += 1
			if e["status"] == "ROUTED":
				routed += float(e["length_m"]) if e["length_m"] != null else 0.0
				if e["swept_clearance_m"] != null:
					swept = minf(swept, float(e["swept_clearance_m"]))
		s += "  %s: routed %s m%s · legs R%d C%d H%d P%d\n" % [g["cls"], String.num(routed, 1), "" if swept == INF else " (swept clear %s m)" % String.num(swept, 2), n["ROUTED"], n["CARRIED"], n["HOLD"], n["PROHIBITED"]]
		if route_view > 1:
			for job in g["jobs"]:
				for tg in g["jobs"][job]:
					s += "    %s %s%s\n" % [tg["status"], tg["target"], "" if tg["reach_needed_m"] == null else " · reach %s m" % String.num(float(tg["reach_needed_m"]), 1)]
			for e in g["edges"]:
				if e["status"] != "ROUTED":
					s += "    %s %s -> %s: %s\n" % [e["status"], e["a"], e["b"], e["why"]]
	if route_view == 1:
		s += dgt019_text()
	return s

## DGT-019 (owner 2026-10-17, S&E 15!A201 / 54!A29): the five route choices as a per-job gap matrix from the rig; every job keeps a deficit.
const DGT019_CHOICE := {"a": "DS-16 aft utilities; roots by DS-11 / DR-EVA-02", "b": "ring rovers sector-bound, crew carry between sectors",
	"c": "one-sided 110 deg spine rail; arm / crew for the far side", "d": "remote dock recovery by fixed arms / crew",
	"e": "Brow rail + arm first; circumferential rails only for a verified gap"}

func dgt019_text() -> String:
	var g: Dictionary = routes.get("dgt019", {})
	if g.is_empty():
		return ""
	var s := "DGT-019 HOLD (owner route choices, %s) · %d of %d jobs pass · %s\n" % [g["source"].split(" (")[0], int(g["passes"]), g["rows"].size(), g["inventory"]]
	for k in DGT019_CHOICE:
		var rows: Array = g["rows"].filter(func(r): return r["choice"] == k)
		var worst = null
		for r in rows:
			if r["reach_needed_m"] != null and (worst == null or float(r["reach_needed_m"]) > float(worst["reach_needed_m"])):
				worst = r
		s += "  (%s) %s · %d jobs%s\n" % [k, DGT019_CHOICE[k], rows.size(), "" if worst == null else " · largest gap: %s" % worst["deficit"]]
	return s

# ------------------------------------------------------------------------------------------------------------------- checks

## nav_drone_routes (DGT-009): C steps OFF -> ALL -> each class -> OFF; the overlay shows exactly the selected classes; every drawn reach line
## is as long as the contract's reach_needed_m (to 5 cm); the card names the gate HOLD and reach OPEN; closing hides it and changes nothing.
func route_checks() -> Dictionary:
	var bad := []
	if routes.is_empty():
		return {"id": "nav_drone_routes", "ok": false, "actual": ["no drones.routes rig block"]}
	var saved := [nav.card_page, nav.level, nav.isolate, nav.hotspot, nav.mode_id]
	var st0 := JSON.stringify(nav.state())
	var plan0 := JSON.stringify(nav.plan)
	nav.isolate = -1
	nav.hotspot = nav.hotspots["WF.NAVMOD.DRONES"]
	nav.card_page = 2
	nav.level = 2
	nav.card.visible = true
	nav.update_now()
	if route_root.visible:
		bad.append("overlay shown before C")
	var seen := []
	for k in route_ids.size() + 2:
		key(KEY_C)
		nav.update_now()
		var want: Array = [] if route_view == 0 else (route_ids if route_view == 1 else [route_name()])
		var shown := route_nodes.keys().filter(func(c): return route_root.visible and route_nodes[c].visible)
		shown.sort()
		var w := want.duplicate()
		w.sort()
		if shown != w:
			bad.append("view %s shows %s" % [route_name(), shown])
		if route_view > 0 and not (text().contains("DGT-009 HOLD") and text().contains("reach OPEN")):
			bad.append("view %s card lacks the gate / reach tags" % route_name())
		if route_view == 1 and not (text().contains("DGT-019 HOLD") and text().contains("0 of %d jobs pass" % routes.get("dgt019", {}).get("rows", []).size())):
			bad.append("all-classes card lacks the DGT-019 gap matrix")
		seen.append(route_name())
	if route_view != 0:
		bad.append("C did not cycle back to OFF")
	for r in reach_drawn:
		if absf(float(r[2]) - float(r[3])) > 0.05:
			bad.append("%s %s drawn %.2f m != %.2f m" % r)
	if reach_drawn.size() < 20:
		bad.append("%d reach lines" % reach_drawn.size())
	key(KEY_C)
	nav.card_page = -1
	nav.card.visible = false
	nav.update_now()
	if route_root.visible or route_view != 0:
		bad.append("overlay still shown after close")
	if JSON.stringify(nav.state()) != st0:
		bad.append("ship state changed")
	nav.card_page = saved[0]
	nav.level = saved[1]
	nav.isolate = saved[2]
	nav.hotspot = saved[3]
	nav.mode_id = saved[4]
	nav.card.visible = nav.card_page >= 0
	nav.update_now()
	if JSON.stringify(nav.plan) != plan0:
		bad.append("route plan changed")
	return {"id": "nav_drone_routes", "ok": bad.is_empty(), "actual": bad, "views": seen, "reach_lines": reach_drawn.size(),
		"note": "DGT-009 route overlay on the drones SHOW ME: routed legs, job targets by status, reach lines equal to the contract; gate HOLD, reach OPEN; clean return"}


## nav_drone_demo (DGT-014 / DN-11): open the drones SHOW ME; every proposed dock drawn; each run played to its end on the track and in a
## safe state; HIGH_POWER keeps the crawler latched; FREE jogging never leaves the track; closing restores the navigator, ship state and route.
func checks() -> Dictionary:
	var bad := []
	if not ready():
		return {"id": "nav_drone_demo", "ok": false, "actual": ["no drones rig block"]}
	var saved := [nav.card_page, nav.level, nav.isolate, nav.hotspot, nav.mode_id]
	var st0 := JSON.stringify(nav.state())
	var plan0 := JSON.stringify(nav.plan)
	nav.isolate = -1
	nav.hotspot = nav.hotspots["WF.NAVMOD.DRONES"]
	nav.card_page = 2
	nav.level = 2
	nav.card.visible = true
	nav.mode_id = "GUIDED"
	nav.update_now()
	if not active() or not root.visible:
		bad.append("demo not active on the SHOW ME page")
	var want := 0
	for x in fleet["stations"]:
		if x["frame"] == "VEHICLE":
			want += x["docks"].size() + x["existing"].size()
	if dock_count != want or want < 22:
		bad.append("%d dock markers for %d vehicle-frame docks" % [dock_count, want])
	var mobile: int = fleet["units"].filter(func(u): return u["domain"] != "FIXED").size()
	if mobile != 24 or fleet["units"].size() != 26:
		bad.append("fleet %d mobile / %d total" % [mobile, fleet["units"].size()])
	var x0 := float(sc["track"]["x0_m"])
	var x1 := float(sc["track"]["x1_m"])
	var runs := {}
	for r in sc["faults"].size() + 1:
		playing = true
		t = 0.0
		for k in 600:
			advance(0.05)
			nav.update_now()
			var ux := unit_x()
			if ux < x0 - 1e-4 or ux > x1 + 1e-4:
				bad.append("run %d: crawler at X %.2f off the track" % [r, ux])
				break
			if not text().contains("SIMULATION ONLY") or not text().contains("OPEN"):
				bad.append("run %d: card lacks the simulation / OPEN tags" % r)
				break
			if not playing:
				break
		var last: Dictionary = frames()[index()]
		runs[r] = last["state"]
		if not finished() or not (last["state"] in ["CHARGE", "DOCK", "SAFE_HOLD", "PARKED_LOCKED"]):
			bad.append("run %d ended in %s" % [r, last["state"]])
		key(KEY_X)
	# HIGH_POWER: the run stops at its precheck with the crawler latched at its dock.
	run = 0
	cfg = configs.find("HIGH_POWER")
	playing = true
	t = 0.0
	for k in 200:
		advance(0.05)
	nav.update_now()
	if absf(unit_x() - float(sc["track"]["dock_x_m"][2])) > 1e-4 or not text().contains("LOCKED") or index() > 1:
		bad.append("HIGH_POWER did not keep the crawler latched (X %.2f, frame %d)" % [unit_x(), index()])
	# FREE: jog past both ends; the crawler stops at the track ends (the forward end is the ring A keep-out).
	cfg = configs.find("COAST")
	nav.mode_id = "FREE"
	for k in 40:
		key(KEY_Z)
	if absf(free_x - x1) > 1e-4:
		bad.append("FREE forward stop %.2f != %.2f" % [free_x, x1])
	for k in 60:
		key(KEY_Y)
	if absf(free_x - x0) > 1e-4:
		bad.append("FREE aft stop %.2f != %.2f" % [free_x, x0])
	# Close: overlay hidden and reset; nothing in the ship state or the route changed.
	nav.card_page = -1
	nav.card.visible = false
	nav.mode_id = saved[4]
	nav.update_now()
	if root.visible:
		bad.append("drone overlay still shown after close")
	if JSON.stringify(nav.state()) != st0:
		bad.append("ship state changed")
	nav.card_page = saved[0]
	nav.level = saved[1]
	nav.isolate = saved[2]
	nav.hotspot = saved[3]
	nav.card.visible = nav.card_page >= 0
	nav.update_now()
	if JSON.stringify(nav.plan) != plan0:
		bad.append("route plan changed")
	return {"id": "nav_drone_demo", "ok": bad.is_empty(), "actual": bad, "docks": dock_count, "runs": runs,
		"note": "DGT-014 / DN-11 slice: drones SHOW ME; study docks; spine crawler service run and three fault replays end safe; HIGH_POWER latched; FREE jog bounded by the ring A keep-out; clean return; simulation only"}
