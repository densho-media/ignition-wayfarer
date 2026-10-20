class_name WfForwardExplorer
extends RefCounted
## FWD-V2 forward defense explorer (Tale 28 AVA-001..005/008/013, S&E 50 AG-016): the forward hotspot's SHOW ME page in the Ship Navigator.
## Data: the rig block `forward_explorer` (src/wayfarer/forward_explorer.py) and the COAST manifest's baked display tracks (offset and turn per
## state) for the Crown and EYE eyelid meshes, applied to their own map parts. Three modes on X:
##   OBSERVE        Y Eye placement (r4 built; r16 / r24 STUDY rings, not built) · Z Crown sector state, or 1..5 to pick one ·
##                  K Crown bay, or click a bay mark (AVA-003 hotspot)
##   DEFENSE_SIM    Z play / restart the unresolved-microdust replay (SIMULATION ONLY, outcome UNKNOWN) · K PHYSICAL / EXPLAINER view
##                  (Tale 28 AVA-011, Eye 45 FD-E15): PHYSICAL runs in real time and draws only what vacuum shows, a flash where the grain
##                  meets the disruptor layer; EXPLAINER expands time and draws the grain (not to scale), its path and the labels as UI
##   DAMAGE_REPAIR  Z next damage pose (jammed / closed eyelids, degraded Crown bay) with what repair can and cannot do
## Remote observation only: nothing here changes the ship state, a route or an access gate (AVA-001, NAV-014). Display, never telemetry.

const KINDS := ["crown_shutter", "crown_port_cover", "crown_carriage", "crown_emitter", "crown_launcher", "eye_shutter"]
const GROUP := "Assembly_FORWARD_SHIELD"

var nav                              # WfShipNavigator
var data: Dictionary                 # rig forward_explorer
var tracks := {}                     # GLB node name -> {states}
var posed: Array = []                # {node, rest, track}
var mode := 0
var variant := 0
var crown := 0
var bay := 1
var damage := 0
var pose_name := "COAST"
var playing := false
var physical := false               # DEFENSE_SIM view: PHYSICAL (0.016 c, nothing vacuum hides) or EXPLAINER (time expanded, overlays), AG-014 E, AVA-011
var t := 0.0                         # replay display seconds
var root := Node3D.new()
var rings := Node3D.new()
var marks := Node3D.new()           # one clickable mark per Crown bay (AVA-003)
var grain := MeshInstance3D.new()
var path := MeshInstance3D.new()     # EXPLAINER: the display path, drawn as UI
var flash := MeshInstance3D.new()    # PHYSICAL: the target flash at the disruptor layer (display marker, size not to scale)
var labels := {}

func _init(n) -> void:
	nav = n
	data = nav.host.rig_all.get("forward_explorer", {})
	var f := FileAccess.open("res://generated/manifest.json", FileAccess.READ)
	if f == null:
		return
	var m: Dictionary = JSON.parse_string(f.get_as_text())
	for r in m["nodes"]:
		if r.has("display") and str(r.get("kind", "")) in KINDS:
			tracks[str(r["node"])] = r["display"]

func ready() -> bool:
	return not data.is_empty() and not tracks.is_empty()

## A forward-defense display mesh keeps its own map node (never merged) so its baked state can move it.
func wants(r: Dictionary) -> bool:
	return tracks.has(str(r.get("node", ""))) and str(r["lineage"][0]) == GROUP

func add_part(mi: MeshInstance3D, name: String) -> void:
	posed.append({"node": mi, "rest": mi.transform, "track": tracks[name]})

func build() -> void:
	nav.map_root.add_child(root)
	root.add_child(rings)
	var sm := SphereMesh.new()
	sm.radius = 1.6
	sm.height = 3.2
	grain.mesh = sm
	grain.material_override = nav._flat(nav.pal["danger"])
	root.add_child(grain)
	var sc: Dictionary = data["scenario"]
	path.mesh = nav._tube(PackedVector3Array([_p(sc["start"]), _p(sc["end"])]), 0.12)
	path.material_override = nav._flat(nav.pal["caution"])
	root.add_child(path)
	var fm := SphereMesh.new()
	fm.radius = 0.8
	fm.height = 1.6
	flash.mesh = fm
	flash.material_override = nav._flat(nav.pal["text"])
	root.add_child(flash)
	root.add_child(marks)
	var mm := SphereMesh.new()
	mm.radius = 1.2
	mm.height = 2.4
	for k in int(data["crown"]["bay_count"]):
		var m := MeshInstance3D.new()
		m.mesh = mm
		m.position = _p(data["crown"]["bay_marks"][k])
		marks.add_child(m)
	for k in ["variant", "bay", "step", "veil", "layer", "brow", "view"]:
		labels[k] = nav._label(30, nav.pal["text"], 30)
		root.add_child(labels[k])
	root.visible = false

func active() -> bool:
	return ready() and nav.card_page == 2 and str(nav.hotspot.get("id", "")) == "WF.HOTSPOT.SHIELD_EYE"

func bay_point(k: int) -> Vector3:
	return root.global_transform * _p(data["crown"]["bay_marks"][k - 1])

## AVA-003 Crown bay hotspot: a left click within 18 px of a bay mark selects that bay (OBSERVE only). True when the click was a bay.
func click(at: Vector2) -> bool:
	if not active() or mode != 0:
		return false
	var best := [0, 18.0]
	for k in range(1, int(data["crown"]["bay_count"]) + 1):
		var q := bay_point(k)
		if nav.cam.is_position_behind(q):
			continue
		var d: float = nav.cam.unproject_position(q).distance_to(at)
		if d < best[1]:
			best = [k, d]
	if best[0] == 0:
		return false
	bay = best[0]
	return true

## Blender ship coordinates (x, y, z) -> the stationary map frame (runtime axes x, z, -y; the frame is the ship root).
func _p(v: Array) -> Vector3:
	return Vector3(float(v[0]), float(v[2]), -float(v[1]))

# ------------------------------------------------------------------------------------------------------------------- state

func pose(name: String) -> void:
	pose_name = name
	for p in posed:
		var v: Dictionary = p["track"]["states"].get(name, {})
		var o: Array = v.get("offset", [0.0, 0.0, 0.0])
		var turn := Basis.IDENTITY
		if v.has("turn"):
			var m: Array = v["turn"]
			turn = Basis(Vector3(m[0], m[3], m[6]), Vector3(m[1], m[4], m[7]), Vector3(m[2], m[5], m[8]))
		var rest: Transform3D = p["rest"]
		(p["node"] as MeshInstance3D).transform = Transform3D(turn * rest.basis, rest.origin + Vector3(o[0], o[1], o[2]))

func reset() -> void:
	mode = 0
	variant = 0
	crown = 0
	bay = 1
	damage = 0
	playing = false
	physical = false
	t = 0.0
	pose("COAST")
	root.visible = false

func key(code: int) -> bool:
	if not active():
		return false
	match code:
		KEY_X:
			mode = (mode + 1) % data["modes"].size()
			playing = false
			t = 0.0
		KEY_Y:
			if mode != 0:
				return false
			variant = (variant + 1) % data["eye_variants"].size()
		KEY_K:
			match mode:
				0: bay = bay % int(data["crown"]["bay_count"]) + 1
				1:
					physical = not physical
					playing = false
					t = 0.0
				_: return false
		KEY_1, KEY_2, KEY_3, KEY_4, KEY_5, KEY_6, KEY_7, KEY_8, KEY_9:
			var i: int = code - KEY_1
			if mode != 0 or i >= data["crown"]["states"].size():
				return false
			crown = i
		KEY_Z:
			match mode:
				0: crown = (crown + 1) % data["crown"]["states"].size()
				1:
					playing = true
					t = 0.0
				2: damage = (damage + 1) % data["damage"]["states"].size()
		_: return false
	return true

func advance(dt: float) -> void:
	if playing:
		var sc: Dictionary = data["scenario"]
		# PHYSICAL: the display clock runs at the time-expansion factor, so the whole path passes in its real microseconds.
		var rate: float = float(sc["physical"]["time_expansion"]) if physical else 1.0
		t = minf(t + dt * rate, float(sc["step_display_s"]) * sc["steps"].size())
		playing = t < float(sc["step_display_s"]) * sc["steps"].size()

func step_index() -> int:
	var sc: Dictionary = data["scenario"]
	return mini(int(t / float(sc["step_display_s"])), sc["steps"].size() - 1)

func finished() -> bool:
	var sc: Dictionary = data["scenario"]
	return t >= float(sc["step_display_s"]) * sc["steps"].size() - 1e-6

## Called from the navigator's update: the pose of the current mode, the overlays, the grain on its path.
func update() -> void:
	if not active():
		if root.visible or pose_name != "COAST":
			reset()
		return
	root.visible = true
	var want := "COAST"
	if mode == 0:
		want = str(data["crown"]["states"][crown]["pose"])
	elif mode == 2:
		want = str(data["damage"]["states"][damage]["pose"])
	if want != pose_name:
		pose(want)
	_rings()
	marks.visible = mode == 0
	for k in marks.get_child_count():
		(marks.get_child(k) as MeshInstance3D).material_override = nav._flat(nav.pal["go"] if k + 1 == bay else nav.pal["text"])
	var bl: Label3D = labels["bay"]
	bl.visible = mode == 0
	bl.position = _p(data["crown"]["bay_marks"][bay - 1])
	bl.text = "bay %d · %s" % [bay, str(data["crown"]["states"][crown]["bays"][bay - 1])]
	var sc: Dictionary = data["scenario"]
	var steps: Array = sc["steps"]
	var on := mode == 1
	var explain := on and not physical
	grain.visible = explain
	path.visible = explain
	for k in ["step", "veil", "layer", "brow"]:
		labels[k].visible = explain
	labels["view"].visible = on
	var hit := float(steps[3]["x"])
	flash.visible = on and physical and (playing or t > 0.0) and step_index() >= 3
	if on:
		var a0 := _p(sc["start"])
		flash.position = Vector3(hit, a0.y, a0.z)
		labels["view"].position = _p(sc["end"]) + Vector3(0, 10.0, 0)
		labels["view"].text = "PHYSICAL VIEW · dust, fields and beams invisible in vacuum" if physical else "EXPLAINER VIEW · drawn UI, not observation"
	if explain:
		var a := _p(sc["start"])
		var b := _p(sc["end"])
		var i := step_index()
		var frac := clampf(t / float(sc["step_display_s"]) - i, 0.0, 1.0)
		var x0: float = float(steps[maxi(i - 1, 0)]["x"]) if i > 0 else float(steps[0]["x"])
		var x1: float = float(steps[i]["x"])
		grain.position = Vector3(lerpf(x0, x1, frac), a.y, a.z)
		labels["step"].position = grain.position + Vector3(0, 3.0, 0)
		labels["step"].text = "%d/%d %s" % [i + 1, steps.size(), steps[i]["title"]]
		labels["veil"].position = a + Vector3(0, -3.0, 0)
		labels["veil"].text = "veil · HYPOTHESIS, not to scale"
		labels["layer"].position = Vector3(float(steps[3]["x"]), a.y - 3.0, a.z)
		labels["layer"].text = "disruptor layer"
		labels["brow"].position = Vector3(b.x, b.y + 6.0, b.z)
		labels["brow"].text = "Brow"

func _rings() -> void:
	var v: Dictionary = data["eye_variants"][variant]
	for c in rings.get_children():
		c.queue_free()
		rings.remove_child(c)
	rings.visible = mode == 0
	var color: Color = nav.pal["go"] if v["built"] else nav.pal["caution"]
	for w in v["wells"]:
		var c := _p([w["x"] + 0.2, w["y"], w["z"]])
		var pts := PackedVector3Array()
		for k in 33:
			var a := TAU * k / 32.0
			pts.append(c + Vector3(0.0, cos(a), sin(a)) * float(w["radius_m"]))
		var mi := MeshInstance3D.new()
		mi.mesh = nav._tube(pts, 0.35)
		mi.material_override = nav._flat(color)
		rings.add_child(mi)
	var l: Label3D = labels["variant"]
	l.visible = mode == 0
	l.position = _p([v["wells"][0]["x"] + 0.5, v["wells"][0]["y"], v["wells"][0]["z"] + 5.0])
	l.text = v["label"]
	l.modulate = color

# ------------------------------------------------------------------------------------------------------------------- text

func _num(x: float, digits := 3) -> String:
	return String.num(x, digits)

func text() -> String:
	var s := "\nFORWARD DEFENSE EXPLORER · %s · %s · %s\n" % [str(data["modes"][mode]).replace("_", " "), data["status"], data["remote_view_only"]]
	match mode:
		0:
			var v: Dictionary = data["eye_variants"][variant]
			s += "Eye placement %s  [%s]\n" % [v["label"], v["status"]]
			for f in v["findings"]:
				s += "  %s: %s  [%s]\n" % [f["label"], f["text"], f["status"]]
			var c: Dictionary = data["crown"]["states"][crown]
			s += "Crown sector state %s (pose %s) · bay %d: %s\n  %s\n" % [c["state"], c["pose"], bay, c["bays"][bay - 1], data["crown"]["status"]]
			var pick := []
			for i in data["crown"]["states"].size():
				var n := str(data["crown"]["states"][i]["state"])
				pick.append("%d %s" % [i + 1, "[%s]" % n if i == crown else n])
			s += "  states: %s · per-bay state OPEN until the AG-009 fixture\n" % "  ".join(pick)
			s += WfInput.keys("{explorer.next} mode · {explorer.view} Eye placement · {explorer.back} / {explorer.bay_1}-%d Crown state · {explorer.step} or click a bay mark") % data["crown"]["states"].size()
		1:
			var sc: Dictionary = data["scenario"]
			var ph: Dictionary = sc["physical"]
			s += "%s · %s · %s\n" % [sc["id"].replace("_", " ").to_lower(), sc["tale"], sc["status"]]
			var scale: Dictionary = sc["state"]["time_scales"][0 if physical else 1]
			if physical:
				s += "PHYSICAL VIEW: the grain, the fields and any beam are invisible in vacuum; only the flash where the grain meets the disruptor layer is drawn (a display marker, not to scale) [AVA-011, FD-E15]\n"
			else:
				s += "EXPLAINER VIEW: the grain (not to scale), its path and the labels are drawn UI, not observation; field extents are not drawn (OPEN) [AVA-011, FD-E15]\n"
			s += "%s: the %s m display path takes %s us at 0.016 c [%s]\n" % [scale["label"], _num(ph["path_m"], 0), _num(ph["path_time_s"] * 1e6, 1), ph["speed_status"]]
			s += "A 1 ug grain carries %s kJ [%s · %s]\n" % [_num(ph["energy_1ug_j"] / 1000.0, 1), ph["energy_source"]["source_status"], ph["energy_source"]["range"]]
			if playing or t > 0.0:
				var st: Dictionary = sc["steps"][step_index()]
				s += "%d/%d %s\n  %s  [%s · %s]\n" % [step_index() + 1, sc["steps"].size(), st["title"], st["text"], st["status"], st["range"]]
				if str(st["open"]) != "":
					s += "  ? OPEN: %s\n" % st["open"]
				var fr: Dictionary = sc["state"]["frames"][step_index()]
				s += "  frame t %s us · %s m to the Brow · %s us to impact · detection %s · response %s\n" % [_num(fr["t_s"] * 1e6, 2), _num(fr["range_m"], 1), _num(fr["time_to_impact_s"] * 1e6, 2), fr["detection_state"], ", ".join(fr["permitted_response"])]
				s += "  mass, energy, cross section, thermal, pulse bank, repair: OPEN  [%s v%d]\n" % [sc["state"]["contract"], sc["state"]["version"]]
			if finished():
				s += "OUTCOME %s\n  unknown: %s\n" % [sc["outcome"], ", ".join(sc["unknown"])]
			var h: Dictionary = data["reference"]["warning_horizon"][3]
			s += "Warning horizon: an object detected at %s km arrives in %s s [%s]\n" % [_num(h["range_m"] / 1000.0, 0), _num(h["time_to_range_s"], 1), h["status"]]
			s += WfInput.keys("{explorer.next} mode · {explorer.back} play / restart · {explorer.step} physical / explainer view")
		2:
			var d: Dictionary = data["damage"]["states"][damage]
			s += "%s: %s\n" % [d["pose"].replace("_", " ").to_lower(), d["text"]]
			for r in data["damage"]["repair"]:
				s += "  %s: %s  [%s]\n" % [r["label"], r["text"], r["status"]]
			s += WfInput.keys("{explorer.next} mode · {explorer.back} next damage state")
	return s

# ------------------------------------------------------------------------------------------------------------------- checks

## nav_forward_explorer (AVA-013): open the hotspot's SHOW ME, switch the Eye placements, step the Crown states and a bay, replay the
## microdust case to its UNKNOWN outcome, pose the damage states, close: every posed mesh back at rest, the ship state and route unchanged.
func checks() -> Dictionary:
	var bad := []
	if not ready():
		return {"id": "nav_forward_explorer", "ok": false, "actual": ["no forward_explorer rig block or display tracks"]}
	var saved := [nav.card_page, nav.level, nav.isolate, nav.hotspot]
	var st0 := JSON.stringify(nav.state())
	var plan0 := JSON.stringify(nav.plan)
	nav.isolate = -1
	nav.hotspot = nav.hotspots["WF.NAVMOD.SHIELD_EYE"]
	nav.card_page = 2
	nav.level = 2
	nav.card.visible = true
	nav.update_now()
	if not active() or not root.visible:
		bad.append("explorer not active on the SHOW ME page")
	if posed.size() < 4 * 5 + 8:
		bad.append("only %d forward display meshes kept separate" % posed.size())
	# OBSERVE: Eye placements (ring centres at the rig's well centres) and Crown states (each posed mesh = rest + its baked track).
	for i in data["eye_variants"].size():
		nav.update_now()
		var v: Dictionary = data["eye_variants"][variant]
		if rings.get_child_count() != v["wells"].size():
			bad.append("variant %s: %d rings" % [v["label"], rings.get_child_count()])
		if not v["built"] and not str(v["label"]).contains("STUDY"):
			bad.append("variant %s not labelled STUDY" % v["label"])
		key(KEY_Y)
	for i in data["crown"]["states"].size():
		nav.update_now()
		var c: Dictionary = data["crown"]["states"][crown]
		var moved := 0
		for p in posed:
			var o: Array = p["track"]["states"].get(c["pose"], {}).get("offset", [0.0, 0.0, 0.0])
			var want: Vector3 = (p["rest"] as Transform3D).origin + Vector3(o[0], o[1], o[2])
			if (p["node"] as MeshInstance3D).position.distance_to(want) > 1e-4:
				bad.append("%s: %s off its baked track" % [c["pose"], p["node"].name])
			if Vector3(o[0], o[1], o[2]).length() > 1e-6:
				moved += 1
		if (c["state"] == "STOWED") != (moved == 0):
			bad.append("%s: %d meshes moved" % [c["state"], moved])
		if not text().contains(str(c["bays"][bay - 1])):
			bad.append("%s: bay state missing from the card" % c["state"])
		key(KEY_Z)
	key(KEY_K)
	nav.update_now()
	if bay != 2 or not labels["bay"].text.contains("bay 2"):
		bad.append("bay selection")
	# AVA-003: the state picker sets a state directly; a click on a bay mark selects that bay, a click in empty space does not.
	key(KEY_3)
	nav.update_now()
	if crown != 2 or not text().contains("[%s]" % data["crown"]["states"][2]["state"]):
		bad.append("state picker 3")
	key(KEY_1)
	var hit := false
	for k in [7, 11]:
		var q := bay_point(k)
		if not nav.cam.is_position_behind(q) and click(nav.cam.unproject_position(q)):
			hit = bay == k
			break
	if not hit:
		bad.append("no bay mark clickable in the map view")
	if click(Vector2(2.0, 2.0)):
		bad.append("an empty corner selected a bay")
	if marks.get_child_count() != int(data["crown"]["bay_count"]):
		bad.append("%d bay marks" % marks.get_child_count())
	bay = 2
	# DEFENSE_SIM: replay to the end; every step shows its status; the outcome is UNKNOWN; OPEN items are named.
	key(KEY_X)
	key(KEY_Z)
	var seen := {}
	for k in 400:
		advance(0.05)
		nav.update_now()
		var tx := text()
		seen[step_index()] = tx
		if not tx.contains("TIME EXPANDED") or not tx.contains("SIMULATION_ONLY"):
			bad.append("replay text lacks the time-expanded / simulation tag")
			break
		if finished():
			break
	if seen.size() != data["scenario"]["steps"].size() or not finished():
		bad.append("replay reached %d of %d steps" % [seen.size(), data["scenario"]["steps"].size()])
	if not text().contains("OUTCOME UNKNOWN"):
		bad.append("outcome not UNKNOWN")
	if pose_name != "COAST":
		bad.append("the replay posed %s" % pose_name)
	if not text().contains("frame t") or not text().contains("OPEN  [WF_FORWARD_SCENARIO"):
		bad.append("contract frame missing from the card")
	key(KEY_K)
	key(KEY_Z)
	advance(1.0 / 60.0)
	nav.update_now()
	if not physical or not finished() or not text().contains("PHYSICAL TIME"):
		bad.append("physical time replay did not pass in one frame")
	# AVA-011 / FD-E15: PHYSICAL draws nothing vacuum hides (no grain, path or labels), only the layer flash; EXPLAINER draws the overlays.
	if grain.visible or path.visible or labels["step"].visible or not flash.visible or not text().contains("PHYSICAL VIEW"):
		bad.append("physical view draws hidden things or lacks the layer flash")
	key(KEY_K)
	key(KEY_Z)
	advance(0.05)
	nav.update_now()
	if not grain.visible or not path.visible or flash.visible or not text().contains("EXPLAINER VIEW"):
		bad.append("explainer view lacks its overlays")
	key(KEY_K)
	key(KEY_K)
	# DAMAGE_REPAIR: each pose applied; repair rates OPEN.
	key(KEY_X)
	for i in data["damage"]["states"].size():
		nav.update_now()
		if pose_name != str(data["damage"]["states"][damage]["pose"]):
			bad.append("damage pose %s not applied" % data["damage"]["states"][damage]["pose"])
		key(KEY_Z)
	if not text().contains("OPEN"):
		bad.append("repair rates not shown OPEN")
	# Return: closing the card restores every mesh and the navigator; no state or route changed (remote view only).
	nav.card_page = -1
	nav.card.visible = false
	nav.update_now()
	for p in posed:
		if not (p["node"] as MeshInstance3D).transform.is_equal_approx(p["rest"]):
			bad.append("%s not back at rest" % p["node"].name)
			break
	if root.visible:
		bad.append("explorer overlay still shown after close")
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
	return {"id": "nav_forward_explorer", "ok": bad.is_empty(), "actual": bad, "posed_meshes": posed.size(),
		"note": "AVA-013 slice: SHOW ME of the forward hotspot; Eye placements, Crown states and bay, microdust replay (UNKNOWN), damage poses, clean return; remote view only"}
