class_name WfRouteState
extends RefCounted
## PHYS-001 phase 9 (DYN-001, DYN-014, DYN-021; 26 C-001..C-013): the imported NAV-001 route (generated/wf_route_v1.json) as a source-driven
## ship state. Rows are the sheet's values; between rows the state is linear in mission time (C-010). Nothing is integrated or extrapolated:
## outside the released rows, or without a route file, sample() returns {} and callers show "no released trajectory".
## Translation and attitude are independent (C-013): this gives position, velocity and acceleration only; attitude stays OPEN.
## Local scenes rebase on the ship (floating origin, GEN-001): the ship stays at the local origin and the mission-frame position is carried
## as a float64 scalar for readouts and display transforms, never as a Godot node coordinate at AU scale.

var route: Dictionary = {}
var col := {}
var times: PackedFloat64Array = []

func load_file(path: String, rig: Dictionary) -> String:
	if not FileAccess.file_exists(path):
		return "no released trajectory (%s missing)" % path
	return load_data(JSON.parse_string(FileAccess.get_file_as_string(path)), rig)

## The same gate on an already parsed route (the Space Navigator's rejection checks feed it altered copies).
func load_data(data, rig: Dictionary) -> String:
	if not data is Dictionary or data.get("schema", "") != "WF_ROUTE_IMPORT":
		return "route file is not a WF_ROUTE_IMPORT"
	if rig.has("flight_timeline") and str(data.route_version) != str(rig.flight_timeline.route.route_version):
		return "route %s does not match the rig's %s" % [data.route_version, rig.flight_timeline.route.route_version]
	var open_checks := []
	var gate_rows := {}
	for v in data.get("validation", []):
		gate_rows[int(v.row)] = true
	for r in range(2, 14):
		if not gate_rows.has(r):
			return "route validation row %d missing (C-009 needs rows 2:13 PASS)" % r
	for v in data.validation:
		if int(v.row) <= 13 and v.result != "PASS":
			return "route validation %s is %s (C-009 needs rows 2:13 PASS)" % [v.check_id, v.result]
		if v.result != "PASS":
			open_checks.append(v.check_id)   # rows 14+: frame, ephemerides, full solve stay OPEN and are shown, never assumed
	route = data
	route["open_checks"] = open_checks
	for i in data.columns.size():
		col[data.columns[i]] = i
	for row in data.frames:
		times.append(float(row[col.mission_t_s]))
	return ""

func ok() -> bool:
	return not route.is_empty()

func row(i: int) -> Array:
	return route.frames[i]

func sample(t: float) -> Dictionary:
	# Linear between released rows in mission time; {} outside them.
	if not ok() or t < times[0] or t > times[times.size() - 1]:
		return {}
	var i := times.bsearch(t, true) - 1
	i = clampi(i, 0, times.size() - 2)
	if times[i + 1] == t:
		i += 1
	var a: Array = route.frames[i]
	var out := {"frame_id": route.frame_id, "scenario_id": route.scenario_id, "status": route.scenario_status, "route_version": route.route_version, "open_checks": route.open_checks,
		"mission_t_s": t, "phase": a[col.phase]}
	var f := 0.0 if i == times.size() - 1 or times[i] == t else (t - times[i]) / (times[i + 1] - times[i])
	var b: Array = route.frames[mini(i + 1, times.size() - 1)]
	for k in ["local_x_m", "local_y_m", "local_z_m", "vx_mps", "vy_mps", "vz_mps", "ax_mps2", "ay_mps2", "az_mps2", "accel_g", "speed_fraction_c", "distance_traveled_AU"]:
		out[k] = float(a[col[k]]) + (float(b[col[k]]) - float(a[col[k]])) * f
	return out

func ship_accel_mps2(t: float):
	# The ship's acceleration along its local +X (bow) at mission time t, or null: the source the local SHIP/RING field uses instead of an
	# envelope bound when a released row covers t (DYN-008 "thrust change follows approved source data").
	var s := sample(t)
	return null if s.is_empty() else float(s.ax_mps2)

static func display_offset_m(x_m: float, unit_m: float) -> float:
	# Named, reversible display transform (C-004): log scale for the ignition-origin marker; inverse in display_inverse_m.
	return unit_m * log(1.0 + absf(x_m) / 1000.0) / log(10.0) * signf(x_m)

static func display_inverse_m(d: float, unit_m: float) -> float:
	return 1000.0 * (pow(10.0, absf(d) / unit_m) - 1.0) * signf(d)
