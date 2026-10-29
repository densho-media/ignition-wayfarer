extends SceneTree
## RT-005: measure the walk's runtime views on the current machine (windowed, vsync off). Loads the walk (excursion.tscn), lets it settle,
## then records WARM frames: wall-clock frame time (median, p95), draw calls, objects and primitives in frame, video and static memory, and
## the scene's load time. One view per run:  godot-4 --path godot --script res://scripts/profile_views.gd -- --view=station|ship
##   station  the walk as it starts: the trainee at the development station, looking down the boarding line toward Wayfarer
##   ship     a fixed camera outside the ship framing the whole vehicle (the exterior cost of the same package)
## Numbers are machine- and driver-specific; compare runs on the same machine only.
## --hide-assemblies=<prefix,...> hides the production nodes whose manifest assembly starts with a prefix (the same package without that
## detail); --hide-zone=<EXTERIOR|INTERIOR> hides the nodes whose manifest zone starts with it, when the package carries zones.

const WARM := 120
const FRAMES := 600
var view := "station"
var node: Node
var times: Array[float] = []
var calls: Array[float] = []
var prims: Array[float] = []
var objects: Array[float] = []
var count := 0
var last := 0
var load_ms := 0.0
var hidden := 0

func hide_where(pred: Callable) -> int:
	var manifest = JSON.parse_string(FileAccess.get_file_as_string("res://generated/manifest_docked.json"))
	var ids := {}
	for record in manifest.get("nodes", []):
		if pred.call(record):
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
	if view not in ["station", "ship"]:
		push_error("unknown view %s: station or ship" % view)
		quit(1)
		return
	DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_DISABLED)
	var t0 := Time.get_ticks_usec()
	node = (load("res://scenes/excursion.tscn") as PackedScene).instantiate()
	root.add_child(node)
	load_ms = (Time.get_ticks_usec() - t0) / 1000.0
	last = Time.get_ticks_usec()

func _process(_delta: float) -> bool:
	count += 1
	if count == 3:
		for arg in OS.get_cmdline_user_args():
			if arg.begins_with("--hide-assemblies="):
				var prefixes := arg.trim_prefix("--hide-assemblies=").split(",")
				hidden += hide_where(func(r): return r.get("layer", "") == "PRODUCTION" and Array(prefixes).any(func(p): return str(r.get("assembly", "")).begins_with(p)))
			if arg.begins_with("--hide-zone="):
				var zone := arg.trim_prefix("--hide-zone=")
				hidden += hide_where(func(r): return str(r.get("zone", "")).begins_with(zone))
	if view == "ship" and count >= 3:
		# The walk drives its own camera every frame; a separate current camera outside the ship takes over (+X bow, +Z dorsal in
		# Blender is -Z forward, +Y up in Godot): three-quarter view from the bow quarter at 420 m.
		var cam := node.get_node_or_null("ProfileShipCamera") as Camera3D
		if cam == null:
			cam = Camera3D.new()
			cam.name = "ProfileShipCamera"
			cam.far = 4000.0
			node.add_child(cam)
		cam.global_transform = Transform3D(Basis.IDENTITY, Vector3(300.0, 140.0, -260.0)).looking_at(Vector3.ZERO, Vector3.UP)
		cam.current = true
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
			"hidden_nodes": hidden, "args": OS.get_cmdline_user_args(),
			"renderer": RenderingServer.get_video_adapter_name(), "driver": RenderingServer.get_video_adapter_api_version()}))
		return true
	return false
