extends SceneTree
## Character export check (docs/CHARACTERS.md "Blender to Godot"): loads every <key>.glb named in characters.json at run time through
## GLTFDocument (no editor import needed), checks the skeleton against the contract, the animation list and lengths, compares the
## animated bone positions and corrective blend-shape weights with the ones Blender evaluated (tolerances TOL_M, WTOL) and measures the
## held contacts' drift in Godot.
##   godot --headless --path godot --script res://scripts/check_characters.gd -- [--dir=/abs/path]
## Prints one WF_GODOT_CHARACTERS JSON line; exits 1 on any failure.

const TOL_M := 0.01
const SLIP_M := 0.02
const WTOL := 0.02

func _initialize() -> void:
	await process_frame
	var dir := "res://generated/characters"
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--dir="):
			dir = a.substr(6)
	var text := FileAccess.get_file_as_string(dir.path_join("characters.json"))
	if text.is_empty():
		_finish({"result": "FAIL", "reason": "no characters.json in " + dir})
		return
	var manifest: Dictionary = JSON.parse_string(text)
	var out := {"result": "PASS", "characters": {}}
	for key in manifest["characters"]:
		var rec: Dictionary = manifest["characters"][key]
		var r := await _check(dir.path_join(rec["glb"]), rec)
		out["characters"][key] = r
		if r.get("fail", []).size() > 0:
			out["result"] = "FAIL"
	_finish(out)

func _check(path: String, rec: Dictionary) -> Dictionary:
	var r := {"fail": []}
	var doc := GLTFDocument.new()
	var state := GLTFState.new()
	if doc.append_from_file(path, state) != OK:
		r["fail"].append("glTF import failed")
		return r
	var scene: Node3D = doc.generate_scene(state)
	root.add_child(scene)
	await process_frame
	var skel: Skeleton3D = scene.find_children("*", "Skeleton3D", true, false)[0]
	var player: AnimationPlayer = scene.find_children("*", "AnimationPlayer", true, false)[0]
	var names := []
	for i in skel.get_bone_count():
		names.append(skel.get_bone_name(i))
	r["bones"] = names.size()
	var want: Array = rec["bones"]
	if names.size() != want.size() or not names.all(func(n): return n in want):
		r["fail"].append("skeleton differs from the contract")
	var meshes := scene.find_children("*", "MeshInstance3D", true, false)
	r["meshes"] = meshes.size()
	var top := -INF
	for m in meshes:
		var aabb: AABB = (m as MeshInstance3D).get_aabb()
		top = max(top, aabb.end.y)
	r["mesh_top_m"] = snappedf(top, 0.001)
	if absf(top - float(rec["stature_m"])) > TOL_M:
		r["fail"].append("mesh height %.3f m, stature %.3f m" % [top, rec["stature_m"]])
	# CHAR-001: the corrective shape keys arrive as blend shapes on the body, and each clip drives them as Blender evaluated them.
	var body: MeshInstance3D = null
	for m in meshes:
		if (m as MeshInstance3D).mesh.get_blend_shape_count() > 0:
			body = m
	var shapes: Array = rec.get("correctives", [])
	r["blend_shapes"] = 0 if body == null else body.mesh.get_blend_shape_count()
	if shapes.size() > 0 and (body == null or body.mesh.get_blend_shape_count() != shapes.size()):
		r["fail"].append("%d corrective blend shapes, expected %d" % [r["blend_shapes"], shapes.size()])
		body = null
	r["animations"] = {}
	var fps := float(rec["fps"])
	for act in rec["actions"]:
		var a: Dictionary = rec["actions"][act]
		var ar := {}
		if not player.has_animation(act):
			r["fail"].append("missing animation " + act)
			continue
		var anim := player.get_animation(act)
		ar["length_s"] = snappedf(anim.length, 0.001)
		var expect := (float(a["frames"]) - 1.0) / fps
		if absf(anim.length - expect) > 1.5 / fps:
			r["fail"].append("%s length %.3f s, expected %.3f s" % [act, anim.length, expect])
		skel.reset_bone_poses()
		player.play(act)
		var worst := 0.0
		for f in a["samples"]:
			player.seek(float(f) / fps, true)
			for b in a["samples"][f]:
				var p: Array = a["samples"][f][b]
				var g := skel.global_transform * skel.get_bone_global_pose(skel.find_bone(b))
				var dev := g.origin.distance_to(Vector3(p[0], p[1], p[2]))
				if dev > worst:
					worst = dev
					ar["worst"] = "%s at frame %s" % [b, f]
		var wworst := 0.0
		if body != null:
			for f in a.get("weights", {}):
				player.seek(float(f) / fps, true)
				for k in a["weights"][f]:
					wworst = max(wworst, absf(body.get_blend_shape_value(body.find_blend_shape_by_name(k)) - float(a["weights"][f][k])))
			ar["max_weight_deviation"] = snappedf(wworst, 0.0001)
			if wworst > WTOL:
				r["fail"].append("%s: corrective weights deviate %.3f from Blender" % [act, wworst])
		ar["max_deviation_from_blender_m"] = snappedf(worst, 0.0001)
		if worst > TOL_M:
			r["fail"].append("%s deviates %.4f m from Blender" % [act, worst])
		var anchor := {}
		var slip := {}
		for f in int(a["frames"]):
			player.seek(float(f) / fps, true)
			var held: Array = a["contacts"][f]
			for b in ["foot_l", "foot_r", "hand_l", "hand_r", "calf_l", "calf_r"]:
				var pos := (skel.global_transform * skel.get_bone_global_pose(skel.find_bone(b))).origin
				if b in held:
					if not anchor.has(b):
						anchor[b] = pos
					slip[b] = max(slip.get(b, 0.0), pos.distance_to(anchor[b]))
				else:
					anchor.erase(b)
		var slip_mm := {}
		for b in slip:
			slip_mm[b] = snappedf(slip[b] * 1000.0, 0.1)
			if slip[b] > SLIP_M:
				r["fail"].append("%s: %s drifts %.1f mm while held" % [act, b, slip[b] * 1000.0])
		ar["held_slip_mm"] = slip_mm
		player.stop()
		r["animations"][act] = ar
	scene.queue_free()
	await process_frame
	return r

func _finish(out: Dictionary) -> void:
	print("WF_GODOT_CHARACTERS ", JSON.stringify(out))
	quit(0 if out["result"] == "PASS" else 1)
