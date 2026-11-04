extends SceneTree
## EVA runtime smoke test (docs/WAYFARER_EVA_SYSTEM.md "Runtime export"): loads the exported suits (eva_characters.json), the EVA
## system and the drone (eva_system.json) at run time through GLTFDocument, and checks that each imports, carries its skeleton, its
## animations and the nodes the runtime drives (hand-controller links, drone arm bones, every nozzle), and that the system clip moves
## what the states say: the drone rides the suit's dock socket while docked and leaves it in the detached states, and the hand
## controller is deployed exactly in the states whose suit pose grips it.
##   godot --headless --path godot --script res://scripts/check_eva.gd -- --dir=/abs/path
## Prints one WF_GODOT_EVA JSON line; exits 1 on any failure.

func _initialize() -> void:
	await process_frame
	var dir := "res://generated/characters"
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--dir="):
			dir = a.substr(6)
	var out := {"result": "PASS", "suits": {}, "fail": []}
	var chars = JSON.parse_string(FileAccess.get_file_as_string(dir.path_join("eva_characters.json")))
	var sysm = JSON.parse_string(FileAccess.get_file_as_string(dir.path_join("eva_system.json")))
	if chars == null or sysm == null:
		_finish({"result": "FAIL", "fail": ["eva_characters.json or eva_system.json missing in " + dir]})
		return
	for key in chars["variants"]:
		var rec: Dictionary = chars["variants"][key]
		out["suits"][key] = await _suit(dir.path_join(rec["glb"]), rec)
		for f in out["suits"][key]["fail"]:
			out["fail"].append(key + ": " + f)
	out["system"] = await _system(dir.path_join(sysm["glb"]["system"]), sysm)
	for f in out["system"]["fail"]:
		out["fail"].append("system: " + f)
	out["drone"] = await _drone(dir.path_join(sysm["glb"]["drone"]), sysm)
	for f in out["drone"]["fail"]:
		out["fail"].append("drone: " + f)
	if out["fail"].size() > 0:
		out["result"] = "FAIL"
	_finish(out)

func _load(path: String) -> Node3D:
	var doc := GLTFDocument.new()
	var state := GLTFState.new()
	if doc.append_from_file(path, state) != OK:
		return null
	var scene: Node3D = doc.generate_scene(state)
	root.add_child(scene)
	return scene

func _player(scene: Node) -> AnimationPlayer:
	var p := scene.find_children("*", "AnimationPlayer", true, false)
	return p[0] if p.size() > 0 else null

func _node(scene: Node, name: String) -> Node3D:
	var n := scene.find_children(name, "Node3D", true, false)
	return n[0] if n.size() > 0 else null

func _pose_at(player: AnimationPlayer, anim: String, t: float) -> void:
	player.play(anim)
	player.seek(t, true)
	player.pause()

func _suit(path: String, rec: Dictionary) -> Dictionary:
	var r := {"fail": []}
	var scene := _load(path)
	if scene == null:
		r["fail"].append("glTF import failed")
		return r
	await process_frame
	var skels := scene.find_children("*", "Skeleton3D", true, false)
	r["bones"] = skels[0].get_bone_count() if skels.size() > 0 else 0
	if r["bones"] < 53:
		r["fail"].append("skeleton has %d bones" % r["bones"])
	var player := _player(scene)
	var anims: Array = player.get_animation_list() if player else []
	r["animations"] = anims.size()
	for a in rec["eva_actions"] + ["EVA_SYSTEM_POSES"]:
		if not a in anims:
			r["fail"].append("animation %s missing" % a)
	r["meshes"] = scene.find_children("*", "MeshInstance3D", true, false).size()
	scene.queue_free()
	return r

func _system(path: String, m: Dictionary) -> Dictionary:
	var r := {"fail": []}
	var scene := _load(path)
	if scene == null:
		r["fail"].append("glTF import failed")
		return r
	await process_frame
	var player := _player(scene)
	if player == null or player.get_animation_list().size() == 0:
		r["fail"].append("no animation")
		return r
	var anim: String = player.get_animation_list()[0]
	var fps := float(m["fps"])
	r["animation"] = anim
	r["length_s"] = snappedf(player.get_animation(anim).length, 0.001)
	var want: float = (m["states"].size() * int(m["segment_frames"]) - 1) / fps
	if absf(r["length_s"] - want) > 2.0 / fps:
		r["fail"].append("clip %.3f s, states need %.3f s" % [r["length_s"], want])
	var missing := []
	for n in m["nozzles"]["suit"] + m["nozzles"]["drone"] + m["controls"]["hand_controller"]["nodes"]:
		if _node(scene, n) == null:
			missing.append(n)
	r["missing_nodes"] = missing
	if missing.size() > 0:
		r["fail"].append("%d driven nodes missing" % missing.size())
	var drone := _node(scene, "RIG_EVA_DRONE")
	var sock := _node(scene, "SOCKET_DRONE_DOCK")
	var link := _node(scene, m["controls"]["hand_controller"]["nodes"][0])
	if drone == null or link == null or sock == null:
		r["fail"].append("drone, dock socket or hand controller node missing")
		_finish_scene(scene)
		return r
	var per := {}
	for s in m["states"]:
		_pose_at(player, anim, (float(s["frame"]) + 3.0) / fps)
		await process_frame
		var p := drone.global_position
		per[s["key"]] = {"drone": [snappedf(p.x, 0.001), snappedf(p.y, 0.001), snappedf(p.z, 0.001)], "drone_from_dock_m": snappedf(p.distance_to(sock.global_position), 0.001),
			"hcm_yaw_deg": snappedf(rad_to_deg(link.rotation.y), 0.1)}
	var hc_stow := float(per["ready"]["hcm_yaw_deg"])
	for s in m["states"]:
		var rec: Dictionary = per[s["key"]]
		var moved: float = rec["drone_from_dock_m"]
		if s["place"] in ["free", "hull"] and moved < 0.3:
			r["fail"].append("%s: drone did not leave the dock" % s["key"])
		if s["place"] == null and moved > 0.01:
			r["fail"].append("%s: docked drone %.3f m off the dock" % [s["key"], moved])
		var deployed: bool = s["suit_pose"] in m["controls"]["hand_controller"]["deploy_poses"]
		var swung: bool = absf(float(rec["hcm_yaw_deg"]) - hc_stow) > 5.0
		if deployed != swung:
			r["fail"].append("%s: hand controller %s" % [s["key"], "not deployed" if deployed else "deployed while stowed expected"])
	r["states"] = per
	_finish_scene(scene)
	return r

func _drone(path: String, m: Dictionary) -> Dictionary:
	var r := {"fail": []}
	var scene := _load(path)
	if scene == null:
		r["fail"].append("glTF import failed")
		return r
	await process_frame
	var player := _player(scene)
	var anims: Array = player.get_animation_list() if player else []
	r["animations"] = anims
	for a in m["drone_animations"]:
		if not a in anims:
			r["fail"].append("animation %s missing" % a)
	var skels := scene.find_children("*", "Skeleton3D", true, false)
	var bones := []
	if skels.size() > 0:
		for i in skels[0].get_bone_count():
			bones.append(skels[0].get_bone_name(i))
	for K in m["controls"]["arm_bones"]:
		for b in m["controls"]["arm_bones"][K]:
			if not b in bones:
				r["fail"].append("arm bone %s missing" % b)
	r["bones"] = bones.size()
	_finish_scene(scene)
	return r

func _finish_scene(scene: Node) -> void:
	scene.queue_free()

func _finish(out: Dictionary) -> void:
	print("WF_GODOT_EVA ", JSON.stringify(out))
	quit(0 if out["result"] == "PASS" else 1)
