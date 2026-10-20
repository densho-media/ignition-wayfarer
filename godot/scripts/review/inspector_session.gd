class_name WfInspectorSession
extends WfReviewSession
## U05: the ship inspector review. Every step completes on the inspector's own state (views pressed, the selected subsystem, focus,
## isolation, the radiator mount legend); the inspector's side panel keeps the selected part's source status and reference.

var host: Node                               # the inspector scene (inspector.gd)
var views_seen := {}
var isolated_once := false

func _init(h: Node) -> void:
	host = h
	title = "Ship inspector"
	steps = [
		{"title": "Whole-ship views", "goal": "Look at the whole ship from the side, from above and in three-quarter view.",
			"expect": "Shield and Crown forward (+X bow), the two rings and the long spine, three radiator blades and the drive aft; static COAST, REP_PROXY."},
		{"title": "Select a subsystem", "goal": "Click a part of the ship or a subsystem in the list on the right.",
			"expect": "The subsystem is tinted blue; the panel shows its parts, geometry status and source references."},
		{"title": "Focus on it", "goal": "Bring the camera to the selection.", "expect": "The view centres on the selected subsystem; orbit and zoom work around it."},
		{"title": "Isolate it", "goal": "Hide everything except the selection.", "expect": "Only the selected subsystem stays visible."},
		{"title": "Restore", "goal": "Show the whole ship again.", "expect": "Every subsystem is visible again."},
		{"title": "Radiator mount legend", "goal": "Show the radiator mount review legend.",
			"expect": "Fixed axial datum mounts turn red, sliding mounts yellow. It is a review legend, not paint: the model's mounts are structure grey."},
	]

func done(i: int) -> bool:
	match i:
		0: return views_seen.size() >= 3
		1: return host.selected_group != ""
		2: return host.selected_group != "" and host.focus.distance_to(host.home_focus) > 0.5
		3:
			isolated_once = isolated_once or host.isolated
			return host.isolated
		4: return isolated_once and not host.isolated
		5: return host.legend_on
	return false

func progress(i: int) -> String:
	return "%d / 3 views" % views_seen.size() if i == 0 else ""

func result(i: int) -> String:
	match i:
		1: return "Selected %s" % host.TITLES.get(host.selected_group, host.selected_group)
		5: return "Legend on %d surfaces (L hides it)" % host.legend_meshes
	return ""

func on_key(keycode: int, i: int) -> Array:
	if keycode in [KEY_1, KEY_2, KEY_3, KEY_HOME]:
		views_seen[3 if keycode == KEY_HOME else keycode - KEY_0] = true
	if keycode in [KEY_F, KEY_I] and host.selected_group == "":
		return ["%s needs a selection: click the ship or the list first." % OS.get_keycode_string(keycode), false]
	return []

func keys(i: int) -> Array:
	var exit := [WfInput.label("ui.cancel"), "clear the selection" if host.selected_group != "" else "back to the review menu", "exit"]
	var look := ["Drag", "orbit · shift-drag pan · wheel zoom", "now"]
	match i:
		0: return [[" ".join(WfInput.labels(["insp.view_side", "insp.view_top", "insp.view_whole"])), "side / top / three-quarter view", "next"], look, exit]
		1: return [["Click", "a part or a list entry", "next"], look, exit]
		2: return [[WfInput.label("insp.focus"), "focus (or double-click)", "next"], look, exit]
		3: return [[WfInput.label("insp.isolate"), "isolate", "next"], [WfInput.label("insp.hide"), "hide / show", "now"], exit]
		4: return [[WfInput.label("insp.isolate"), "restore", "next"], exit]
		5: return [[WfInput.label("insp.legend"), "radiator mount legend", "next"], [WfInput.label("insp.hide"), "hide / show", "now"], exit]
	return [exit]

func labels(i: int) -> Array:
	match i:
		0: return [["PROTOTYPE", "REP_PROXY geometry from the shared formulas (static COAST)"]]
		1, 2, 3, 4:
			if host.selected_mesh != null:
				var r: Dictionary = host.records.get(str(host.selected_mesh.name), {})
				return [[str(r.get("canon_status", "OPEN")), "selected part: %s" % r.get("source_ref", "no source ref")],
					[str(r.get("geometry_status", "PROTOTYPE")), "its geometry"]]
			if host.selected_group != "":                 # a whole subsystem: one badge per source status among its parts, with the count
				var n := {}
				for m in host.meshes:
					if m.get_meta("subsystem") == host.selected_group:
						var st := str(host.records.get(str(m.name), {}).get("canon_status", "OPEN"))
						n[st] = n.get(st, 0) + 1
				return n.keys().slice(0, 4).map(func(k): return [k, "%d parts" % n[k]])
			return [["PROTOTYPE", "REP_PROXY geometry; click a part for its own source status"]]
		5: return [["WORKING", "legend only, not paint (owner 2026-10-17, 15!A202)"]]
	return []
