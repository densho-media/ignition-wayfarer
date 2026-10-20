extends SceneTree
## PHYS-001 phase 9: the packaged route sampled at every released row reproduces the row (C-001/C-010); no sample outside the rows; the
## display transform is reversible (C-004). Prints WF_GODOT_ROUTE {json}.

func _initialize() -> void:
	var rig = JSON.parse_string(FileAccess.get_file_as_string("res://generated/wf_sim_rig.json"))
	var r := WfRouteState.new()
	var err := r.load_file("res://generated/wf_route_v1.json", rig if rig != null else {})
	var fail := []
	var worst := 0.0
	if err != "":
		fail.append(err)
	else:
		for i in r.route.frames.size():
			var row: Array = r.row(i)
			var s := r.sample(float(row[r.col.mission_t_s]))
			for k in ["local_x_m", "vx_mps", "ax_mps2", "accel_g"]:
				var want := float(row[r.col[k]])
				worst = maxf(worst, absf(s[k] - want) / maxf(absf(want), 1.0))
		if worst > 1e-12:
			fail.append("row reproduction error %g" % worst)
		if not r.sample(r.times[r.times.size() - 1] + 1.0).is_empty() or not r.sample(-1.0).is_empty():
			fail.append("sample outside the released rows")
		for x in [0.0, 1.0, 2.4e9, 1.04e12]:
			if absf(WfRouteState.display_inverse_m(WfRouteState.display_offset_m(x, 10.0), 10.0) - x) > 1e-6 * maxf(x, 1.0):
				fail.append("display transform not reversible at %g" % x)
		if r.route.frame_id != "IGNITION_LOCAL_INERTIAL_1D":
			fail.append("unexpected frame %s" % r.route.frame_id)
	print("WF_GODOT_ROUTE " + JSON.stringify({"result": "PASS" if fail.is_empty() else "FAIL", "rows": r.times.size(), "max_rel_error": worst,
		"frame_id": r.route.get("frame_id", ""), "open_checks": r.route.get("open_checks", []), "status": r.route.get("scenario_status", ""), "fail": fail}))
	quit(0 if fail.is_empty() else 1)
