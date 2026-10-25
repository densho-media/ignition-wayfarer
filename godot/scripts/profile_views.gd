extends SceneTree
## RT-005: measure the three runtime views on the current machine (windowed, vsync off). Loads a scene, lets it settle, then records
## WARM frames: wall-clock frame time (median, p95), draw calls, objects and primitives in frame, video and static memory, and the scene's
## load time. One view per run:  godot-4 --path godot --script res://scripts/profile_views.gd -- --view=exterior|boarding|flight|demo_spine|demo_ring
## The demo views are Demonstrator 01 in MICROGRAVITY (the body in the trunk) and GRAVITY (the body on ring A's deck), with the Ship Navigator's
## corner locator; add --no-navigator for the same view without it (SNAV-001 before / after), or --navigator-overview for the expanded
## overview (whole ship, EVA remote view, hazard labels), which also times the first and a repeat click pick (--no-pick skips it), or --space
## (--space-solar: on the Solar System chart) for the SPACE view open on First Ignition row 451 (S&E 55 SPACE-024/028: the ship map stops rendering while SPACE shows).
## Numbers are machine- and driver-specific; compare runs on the same machine only.
## Phase 4 S11: --hide-assemblies=<prefix,...> hides the production nodes whose manifest assembly starts with a prefix (the same package
## without that detail); --look=<0-3> sets the flight scene's exterior look (0 off, 1 grammar, 2 grammar + wear, 3 proxy grey).

const WARM := 120
const FRAMES := 600
var view := "exterior"
var node: Node
var times: Array[float] = []
var calls: Array[float] = []
var prims: Array[float] = []
var objects: Array[float] = []
var count := 0
var last := 0
var load_ms := 0.0
var pick_ms := {}
var hidden := 0

func hide_assemblies(prefixes: PackedStringArray) -> int:
	var manifest = JSON.parse_string(FileAccess.get_file_as_string("res://generated/manifest.json"))
	var ids := {}
	for record in manifest.get("nodes", []):
		if record.get("layer", "") == "PRODUCTION" and Array(prefixes).any(func(p): return str(record.get("assembly", "")).begins_with(p)):
			ids[record.node] = true
	var n := 0
	for item in node.find_children("WF_*", "MeshInstance3D", true, false):
		if ids.has(str(item.name).get_slice(".", 0)):
			item.visible = false
			n += 1
	return n

func _initialize() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--view="):
			view = arg.trim_prefix("--view=")
	DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_DISABLED)
	var scene: String = {"exterior": "res://scenes/inspector.tscn", "boarding": "res://scenes/boarding.tscn", "flight": "res://scenes/flight.tscn",
		"demo_entry": "res://scenes/demo01.tscn", "demo_spine": "res://scenes/demo01.tscn", "demo_ring": "res://scenes/demo01.tscn"}[view]
	var t0 := Time.get_ticks_usec()
	node = (load(scene) as PackedScene).instantiate()
	root.add_child(node)
	load_ms = (Time.get_ticks_usec() - t0) / 1000.0
	last = Time.get_ticks_usec()

func _process(_delta: float) -> bool:
	count += 1
	if count == 3 and view == "boarding" and node.has_method("go_to_stop"):
		node.go_to_stop(4)                        # a sector stop (the Garden), looking along the aisle
	if count == 3 and view.begins_with("demo_") and node.get("demo") != null:
		node.demo.begin({"demo_entry": 1, "demo_spine": 2}.get(view, 6))   # M7: demo_entry is the ENTRY chapter (the entry chamber)
	if count == 10 and "--navigator-overview" in OS.get_cmdline_user_args() and node.get("demo") != null and node.demo.navigator != null:
		var nv = node.demo.navigator
		nv.level = 2
		nv.span = 260.0
		nv.update_now()
		var at: Vector2 = nv.vp.size / 2.0
		for k in ([] if "--no-pick" in OS.get_cmdline_user_args() else ["first", "repeat"]):
			var t := Time.get_ticks_usec()
			pick_ms[k + "_module"] = nv.pick(at)
			pick_ms[k + "_ms"] = (Time.get_ticks_usec() - t) / 1000.0
	if count == 10 and ("--space" in OS.get_cmdline_user_args() or "--space-solar" in OS.get_cmdline_user_args()) and node.get("demo") != null and node.demo.navigator != null:
		var t := Time.get_ticks_usec()
		node.demo.navigator.space.set_active(true)
		node.demo.navigator.space.select(450)
		if "--space-solar" in OS.get_cmdline_user_args():
			node.demo.navigator.space.scale = "SOLAR"
			node.demo.navigator.space.update_now()
		pick_ms["space_open_ms"] = (Time.get_ticks_usec() - t) / 1000.0
	if count == 3:
		for arg in OS.get_cmdline_user_args():
			if arg.begins_with("--look=") and node.has_method("set_look_mode"):
				node.set_look_mode(int(arg.trim_prefix("--look=")))
			if arg.begins_with("--hide-assemblies="):
				hidden = hide_assemblies(arg.trim_prefix("--hide-assemblies=").split(","))
	var now := Time.get_ticks_usec()
	if count > WARM:
		times.append((now - last) / 1000.0)
		calls.append(Performance.get_monitor(Performance.RENDER_TOTAL_DRAW_CALLS_IN_FRAME))
		prims.append(Performance.get_monitor(Performance.RENDER_TOTAL_PRIMITIVES_IN_FRAME))
		objects.append(Performance.get_monitor(Performance.RENDER_TOTAL_OBJECTS_IN_FRAME))
	last = now
	if count >= WARM + FRAMES:
		times.sort()
		var med: float = times[times.size() / 2]
		var p95: float = times[int(times.size() * 0.95)]
		print("WF_PROFILE ", JSON.stringify({"view": view, "frames": times.size(), "frame_ms_median": med, "frame_ms_p95": p95,
			"draw_calls": calls.max(), "objects": objects.max(), "primitives": prims.max(),
			"video_mem_mb": Performance.get_monitor(Performance.RENDER_VIDEO_MEM_USED) / 1048576.0,
			"static_mem_mb": Performance.get_monitor(Performance.MEMORY_STATIC) / 1048576.0, "scene_load_ms": load_ms,
			"navigator": ("space_solar" if "--space-solar" in OS.get_cmdline_user_args() else "space" if "--space" in OS.get_cmdline_user_args() else "overview" if "--navigator-overview" in OS.get_cmdline_user_args() else not "--no-navigator" in OS.get_cmdline_user_args()) if view.begins_with("demo_") else null,
			"pick": pick_ms, "hidden_nodes": hidden, "args": OS.get_cmdline_user_args(),
			"renderer": RenderingServer.get_video_adapter_name(), "driver": RenderingServer.get_video_adapter_api_version()}))
		return true
	return false
