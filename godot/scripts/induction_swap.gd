extends SceneTree
## Controlled proxy replacement (docs/CHARACTERS.md "Blender to Godot"): the DOCKED vehicle export with the S004A greeting's two induction
## proxies (the instructor and the newcomer) hidden and the MPFB characters standing in for them, placed and posed as Blender staged them.
## Not part of the boarding walk.
##   godot [--headless] --path godot --script res://scripts/induction_swap.gd -- [--who=instructor,newcomer] [--dir=/abs/glb/dir] [--capture=/abs/file.png]
## Checks that each proxy's nodes were found and hidden and that each character's check bones land where Blender put them in the vehicle
## frame (TOL_M). Prints one WF_INDUCTION_SWAP JSON line; exits 1 on failure. --capture (needs a window) saves a still of the greeting.

const TOL_M := 0.01

func _initialize() -> void:
	await process_frame
	var who := PackedStringArray(["instructor", "newcomer"])
	var dir := "res://generated/characters"
	var capture := ""
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--who="):
			who = a.substr(6).split(",")
		elif a.begins_with("--dir="):
			dir = a.substr(6)
		elif a.begins_with("--capture="):
			capture = a.substr(10)
	var out := {"result": "PASS", "who": who, "fail": [], "proxy_nodes_hidden": {}, "max_deviation_from_blender_m": {}}
	var ship: Node3D = (load("res://generated/wayfarer_docked.glb") as PackedScene).instantiate()
	root.add_child(ship)
	var records: Dictionary = (JSON.parse_string(FileAccess.get_file_as_string(dir.path_join("characters.json"))) as Dictionary)["characters"]
	var manifest: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://generated/manifest_docked.json"))
	var placed: Array[Skeleton3D] = []
	for w in who:
		if not records.has(w) or not records[w].has("stage"):
			out["fail"].append(w + ": no staged character in characters.json")
			continue
		var rec: Dictionary = records[w]
		var stage: Dictionary = rec["stage"]
		var prefix := "%s_" % str(stage["proxy"]).capitalize()     # the greeting proxies: Instructor_*, Newcomer_* (S004B_Newcomer_* is the couch)
		var hidden := 0
		for n in manifest["nodes"]:
			if str(n.get("component_id", "")).begins_with(prefix):
				var node := ship.find_child(n["node"], true, false) as Node3D
				if node:
					node.visible = false
					hidden += 1
		out["proxy_nodes_hidden"][w] = hidden
		if hidden == 0:
			out["fail"].append("no proxy nodes " + prefix + "* in the DOCKED export")
		var doc := GLTFDocument.new()
		var state := GLTFState.new()
		if doc.append_from_file(dir.path_join(rec["glb"]), state) != OK:
			out["fail"].append("cannot load " + rec["glb"])
			continue
		var body: Node3D = doc.generate_scene(state)
		var p: Dictionary = stage["placement_godot"]
		var c: Array = p["basis_columns"]
		body.transform = Transform3D(Basis(Vector3(c[0][0], c[0][1], c[0][2]), Vector3(c[1][0], c[1][1], c[1][2]), Vector3(c[2][0], c[2][1], c[2][2])),
			Vector3(p["origin"][0], p["origin"][1], p["origin"][2]))
		ship.add_child(body)
		await process_frame
		var skel: Skeleton3D = body.find_children("*", "Skeleton3D", true, false)[0]
		var player: AnimationPlayer = body.find_children("*", "AnimationPlayer", true, false)[0]
		skel.reset_bone_poses()
		player.play(stage["action"])
		player.seek(0.0, true)
		var worst := 0.0
		for b in stage["bones_godot"]:
			var q: Array = stage["bones_godot"][b]
			var g := (skel.global_transform * skel.get_bone_global_pose(skel.find_bone(b))).origin
			worst = max(worst, g.distance_to(Vector3(q[0], q[1], q[2])))
		out["max_deviation_from_blender_m"][w] = snappedf(worst, 0.0001)
		if worst > TOL_M:
			out["fail"].append("%s: posed character deviates %.4f m from Blender in the vehicle frame" % [w, worst])
		placed.append(skel)
	if capture != "" and DisplayServer.get_name() != "headless" and placed.size() > 0:
		var mid := Vector3.ZERO
		for skel in placed:
			mid += (skel.global_transform * skel.get_bone_global_pose(skel.find_bone("spine_02"))).origin
		mid /= placed.size()
		var fore := Vector3(1, 0, 0)                               # Godot +X = Blender +X (bow): the greeting's "up" in the stationary chamber
		var cam := Camera3D.new()
		ship.add_child(cam)
		var eye := mid + Vector3(0, 0, 2.6) + fore * 0.2              # across the chamber, as CAM_IND_GREETING looks
		cam.look_at_from_position(eye, mid, fore)
		cam.near = 1.6
		cam.fov = 60.0
		cam.current = true
		var light := DirectionalLight3D.new()
		ship.add_child(light)
		light.look_at_from_position(eye, mid, fore)
		for i in 6:
			await process_frame
		get_root().get_viewport().get_texture().get_image().save_png(capture)
		out["capture"] = capture
	_finish(out)

func _finish(out: Dictionary) -> void:
	if out["fail"].size() > 0:
		out["result"] = "FAIL"
	print("WF_INDUCTION_SWAP ", JSON.stringify(out))
	quit(0 if out["result"] == "PASS" else 1)
