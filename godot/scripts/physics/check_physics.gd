class_name WfPhysicsCheck
extends Node
## Headless check of the local physics (PHYS-001, SIMULATION_ONLY): `godot --headless --fixed-fps 60 --path godot res://scenes/physics_lab.tscn -- --check-physics`.
## Every tolerance is in the output. Checks a..i follow the brief; walk and no-input checks are phase 3; m_* are the phase 4 mode controller.

var lab
var dyn: Dictionary
var checks: Array = []
var perf: Array = []

func rec(id: String, actual, expected, tol: float, note := "") -> bool:
	var err := 0.0
	if actual is Array or actual is PackedFloat64Array:
		for i in actual.size():
			err = maxf(err, absf(actual[i] - expected[i]))
	else:
		err = absf(actual - expected)
	var ok := err <= tol
	checks.append({"id": id, "actual": actual, "expected": expected, "error": err, "tol": tol, "ok": ok, "note": note})
	return ok

func flag(id: String, ok: bool, actual, expected, note := "") -> void:
	checks.append({"id": id, "actual": actual, "expected": expected, "tol": 0, "ok": ok, "note": note})

func ticks(n: int) -> void:
	for i in n:
		await get_tree().physics_frame
		perf.append(Performance.get_monitor(Performance.TIME_PHYSICS_PROCESS))

func run(l) -> Dictionary:
	lab = l
	dyn = lab.dyn
	var wall0 := Time.get_ticks_usec()
	var engine := str(ProjectSettings.get_setting("physics/3d/physics_engine"))
	await ticks(1)
	await check_a()
	await check_b()
	await check_c()
	await check_d()
	await check_e()
	await check_f("RING_A")
	await check_f("RING_B")
	flag("f_opposite_sides", signf(checks_value("f_RING_A_offset")) != signf(checks_value("f_RING_B_offset")), checks_value("f_RING_A_offset"), checks_value("f_RING_B_offset"), "ring-frame tangential offsets of A and B have opposite signs")
	await check_g()
	await check_walk()
	check_h()
	check_i()
	check_modes()
	check_owner_sequence()
	check_vestibule()
	await check_tether()
	await check_gravity_change()
	var ok := true
	for c in checks:
		ok = ok and c["ok"]
	var mean := 0.0
	var mx := 0.0
	for p in perf:
		mean += p
		mx = maxf(mx, p)
	return {"result": "PASS" if ok else "FAIL", "status": "SIMULATION_ONLY", "physics_engine": engine, "physics_server": _server_name(),
		"ticks_per_second": Engine.physics_ticks_per_second, "godot": Engine.get_version_info()["string"],
		"rig": {"contract_version": lab.rig.get("contract_version"), "spec_hash": lab.rig.get("spec_hash"), "source_map_hash": lab.rig.get("source_map_hash")},
		"perf_physics_process_ms": {"mean": mean / maxf(1.0, perf.size()) * 1000.0, "max": mx * 1000.0, "frames": perf.size(), "note": "Performance monitor, headless"},
		"wall_ms_per_tick_all_checks": (Time.get_ticks_usec() - wall0) / 1000.0 / maxf(1.0, perf.size()),
		"checks": checks}

func _server_name() -> String:
	# Jolt is the active server when its project setting is selected and its server class is registered
	return "JoltPhysicsServer3D" if ClassDB.class_exists("JoltPhysicsServer3D") and str(ProjectSettings.get_setting("physics/3d/physics_engine")) == "Jolt Physics" else "other"

func checks_value(id: String) -> float:
	for c in checks:
		if c["id"] == id:
			return c["actual"]
	return 0.0

# a. rig fixtures through the frame field (double precision, Godot axes)
func check_a() -> void:
	var n := 0
	for f in dyn["fixtures"]:
		if f.has("expect"):
			var ff := WfFrameField.for_fixture(dyn, f)
			var got := ff.eval(WfFrames.b2g(f["r"]), WfFrames.b2g(f["v"]))
			rec("a_field_" + f["id"], Array(got), Array(WfFrames.b2g(f["expect"])), 1e-9, "per component, Godot axes")
			if f.has("a_ship_g"):
				rec("a_ashipg_" + f["id"], dyn["modes"][f["config"]]["demo_ship_accel_g"], f["a_ship_g"], 1e-12)
			n += 1
		elif f.has("expect_impulse_n_s"):
			# tension-only tether fixture (DYN-025): same impulse and velocity as crew_dynamics.tether
			var p := WfFrames.to_vec(WfFrames.b2g(f["p"]))
			var v := WfFrames.to_vec(WfFrames.b2g(f["v"]))
			var r := WfTether.limit(p, v, Vector3.ZERO, f["length_m"], f["mass_kg"])
			var j: Vector3 = r[3]
			rec("a_tether_impulse_" + f["id"], [j.x, j.y, j.z], Array(WfFrames.b2g(f["expect_impulse_n_s"])), 1e-4, "J = -m (v.n) n")
			rec("a_tether_v_" + f["id"], [r[1].x, r[1].y, r[1].z], Array(WfFrames.b2g(f["expect_v"])), 1e-6)
			rec("a_tether_force_" + f["id"], j.length() / f["dt_s"], f["expect_anchor_force_n"], 1e-2, "rigid-limit mean force |J|/dt (diagnostic; loads OPEN)")
			# CALC-R06: the impulse does not depend on the step, |J|/dt does (half the step, twice the "force"): a timestep artifact, not a rating
			rec("a_tether_dt_artifact_" + f["id"], j.length() / (0.5 * f["dt_s"]), 2.0 * f["expect_anchor_force_n"], 1e-2, "|J|/(dt/2) = 2 |J|/dt with J unchanged")
			n += 1
		elif f.has("expect_dv"):
			var pname: String = f["id"].substr(5).to_lower()
			var m: float = f["mass_kg"]
			rec("a_profilemass_" + f["id"], dyn["profiles"][pname]["mass_kg"], m, 1e-12)
			var dv := WfFrames.mul(WfFrames.b2g(f["impulse_n_s"]), 1.0 / m)
			rec("a_dv_" + f["id"], Array(dv), Array(WfFrames.b2g(f["expect_dv"])), 1e-6, "dv = J/m")
			n += 1
	flag("a_fixture_count", n == dyn["fixtures"].size() and n > 0, n, dyn["fixtures"].size())
	await ticks(0)

# b. zero-g drift in the SHIP frame, no contact
func check_b() -> void:
	lab.build({"zone": "SHIP", "mode": "COAST", "actor": true, "tool": false, "walls": false, "rails": false, "actor_pos": Vector3.ZERO, "actor_vel": Vector3(0.3, 0, 0)})
	var a: WfCrewBody = lab.actor
	var f0 := Engine.get_physics_frames()
	await ticks(600)
	var n := Engine.get_physics_frames() - f0
	var t := n / float(Engine.physics_ticks_per_second)
	rec("b_drift_dv", (a.linear_velocity - Vector3(0.3, 0, 0)).length(), 0.0, 1e-6, "velocity change after 10 s, no contact")
	rec("b_drift_pos", a.global_position.x, 0.3 * t, 1e-4, "x vs v t, t = %.4f s" % t)
	rec("b_drift_off_axis", Vector2(a.global_position.y, a.global_position.z).length(), 0.0, 1e-6)

# c. push and contact torque
func check_c() -> void:
	for pn in ["human_iva", "human_suited"]:
		for centred in [true, false]:
			lab.build({"zone": "SHIP", "mode": "COAST", "actor": true, "tool": false, "profile": pn})
			var a: WfCrewBody = lab.actor
			await ticks(2)
			var g1: bool = a.grab(lab.rail(1))
			await ticks(3)
			var m: float = dyn["profiles"][pn]["mass_kg"]
			# centred: the hand point lies on the push line (the rail is on -X of the body, push along +X); off-centre: push across it
			var ok: bool = a.push(Vector3.RIGHT if centred else Vector3.UP, 30.0)
			await ticks(2)
			var tag := "c_%s_%s" % [pn, "centred" if centred else "offcentre"]
			flag(tag + "_grabbed_pushed", g1 and ok, [g1, ok], [true, true])
			var dv_exp := 30.0 / m
			rec(tag + "_dv", a.linear_velocity.length(), dv_exp, 1e-3, "J = 30 N s, m = %.1f kg" % m)
			if centred:
				rec(tag + "_angvel", a.angular_velocity.length(), 0.0, 1e-6)
			else:
				var w := a.angular_velocity.length()
				flag(tag + "_angvel", w > 1e-3, w, "> 1e-3", "contact torque from the off-centre hand point")
	flag("c_profiles_differ", absf(checks_value("c_human_iva_centred_dv") - checks_value("c_human_suited_centred_dv")) > 0.1,
		checks_value("c_human_iva_centred_dv"), checks_value("c_human_suited_centred_dv"), "same J, different dv")

# d. grab - push - drift - catch, twice (determinism)
func catch_once(name: String, save: bool) -> Dictionary:
	lab.build({"zone": "SHIP", "mode": "COAST", "actor": true, "tool": false, "profile": "human_iva"})
	var rec_: WfRecorder = lab.start_recording(name)
	var a: WfCrewBody = lab.actor
	await ticks(2)
	var g1: bool = a.grab(lab.rail(1))
	await ticks(5)
	var p: bool = a.push(Vector3.RIGHT, 30.0)
	var drift := 0
	while not a.can_reach(lab.rail(2)) and drift < 900:
		await ticks(1)
		drift += 1
	var d_at: float = a.global_position.distance_to(lab.rail(2).anchor_point())
	var v_at := a.linear_velocity.length()
	var g2: bool = a.grab(lab.rail(2))
	var stop := -1
	for i in 30:
		await ticks(1)
		if stop < 0 and a.linear_velocity.length() < 1e-2:
			stop = i + 1
	var v_after := a.linear_velocity.length()
	await ticks(60)
	var pos_held: Vector3 = a.global_position
	a.release()
	await ticks(120)
	var out := {"g1": g1, "pushed": p, "drift_ticks": drift, "dist": d_at, "v_at_grab": v_at, "g2": g2, "stop_ticks": stop, "v_after": v_after,
		"v_rest": a.linear_velocity.length(), "moved_after_release": a.global_position.distance_to(pos_held), "x_end": a.global_position.x, "rows": JSON.stringify(rec_.rows)}
	if save:
		rec_.save()
	return out

func check_d() -> void:
	var r1: Dictionary = await catch_once("push_drift_catch", true)
	var r2: Dictionary = await catch_once("push_drift_catch_repeat", false)
	flag("d_grab_push_catch", r1["g1"] and r1["pushed"] and r1["g2"], [r1["g1"], r1["pushed"], r1["g2"]], [true, true, true])
	rec("d_arrival_distance", r1["dist"], 0.75, 0.2, "distance to rail 2 at the grab (profile reach 0.75 m); drift ticks %d, speed %.4f m/s" % [r1["drift_ticks"], r1["v_at_grab"]])
	flag("d_grip_stops", r1["v_after"] < 1e-2 and r1["stop_ticks"] > 0 and r1["stop_ticks"] <= 30, r1["v_after"], "< 1e-2 within 30 ticks", "stopped after %d ticks" % r1["stop_ticks"])
	rec("d_release_at_rest", r1["v_rest"], 0.0, 1e-3, "speed 2 s after the release")
	rec("d_release_no_motion", r1["moved_after_release"], 0.0, 1e-3, "displacement during those 2 s")
	flag("d_deterministic", r1["rows"] == r2["rows"], r1["rows"].length(), r2["rows"].length(), "two runs, bitwise identical trace rows (JSON text)")

# e. tool: wall, CCD, no damping
func check_e() -> void:
	var half := WfTool.SIZE.x * 0.5
	for speed in [5.0, 25.0]:
		lab.build({"zone": "SHIP", "mode": "COAST", "actor": false, "tool": true, "rails": false, "tool_pos": Vector3.ZERO, "tool_vel": Vector3(speed, 0, 0)})
		var t: WfTool = lab.tool
		var wall_x: float = lab.LAB.x * 0.5
		var worst := -INF
		var outer: float = wall_x + lab.WALL
		var passed := false
		for i in 240:
			await ticks(1)
			worst = maxf(worst, t.global_position.x + half - wall_x)
			if t.global_position.x > outer:
				passed = true
		flag("e_wall_%dms" % int(speed), not passed and worst < 0.02, worst, "< 0.02 penetration", "max penetration of the tool face into the 0.1 m wall; never beyond the outer face")
	# a released tool keeps drifting: hold it, release, then it keeps its velocity (no damping)
	lab.build({"zone": "SHIP", "mode": "COAST", "actor": true, "tool": true, "walls": false, "rails": false, "actor_pos": Vector3.ZERO, "actor_vel": Vector3(0.3, 0, 0),
		"tool_pos": Vector3(0.5, 0.0, 0.0), "tool_vel": Vector3(0.3, 0, 0)})
	var a: WfCrewBody = lab.actor
	var t2: WfTool = lab.tool
	var tr: WfRecorder = lab.start_recording("tool_float")
	await ticks(2)
	var held: bool = a.grab_tool(t2)
	await ticks(60)
	a.release_tool()
	await ticks(2)
	var v0 := t2.linear_velocity
	var p0 := t2.global_position
	var f0 := Engine.get_physics_frames()
	await ticks(180)
	var dt := (Engine.get_physics_frames() - f0) / float(Engine.physics_ticks_per_second)
	flag("e_tool_held", held, held, true)
	rec("e_tool_drift_dv", (t2.linear_velocity - v0).length(), 0.0, 1e-6, "velocity change over 3 s after release")
	rec("e_tool_drift_pos", (t2.global_position - p0 - v0 * dt).length(), 0.0, 1e-4)
	tr.save()

# f. ring drop: released at rest in the ring frame 1.5 m above the floor
func check_f(zone: String) -> void:
	var k := WfFrames.ring_index(zone)
	var R: float = dyn["rings"][k]["floor_radius_m"]
	var w: float = dyn["rings"][k]["omega_rad_s"]
	var sg: float = dyn["rings"][k]["sign"]
	lab.build({"zone": zone, "mode": "COAST", "actor": false, "tool": true, "rails": false, "tool_pos": Vector3(0, -(R - 1.5), 0), "tool_vel": Vector3.ZERO})
	var t: WfTool = lab.tool
	var tr: WfRecorder = lab.start_recording("ring_%s_drop" % zone.substr(5).to_lower())
	for i in 240:
		await ticks(1)
		if t.contact_step >= 0:
			break
	await ticks(30)
	tr.save()
	var Re := R - WfTool.SIZE.y * 0.5          # tool centre when its face touches the floor
	var h := R - 1.5
	var s := sqrt(Re * Re - h * h)
	var tt := s / (w * h)
	var off_exp := sg * Re * (atan2(s, h) - w * tt)
	# impact point inside the step: from the last free state (p, v, a) solve p.y + v.y u + a.y u^2 / 2 = floor plane for the first u > 0
	var A := 0.5 * t.pre_acc.y
	var B := t.pre_vel.y
	var C := t.pre_pos.y + Re
	var disc := sqrt(maxf(0.0, B * B - 4.0 * A * C))
	var us: Array = [(-B - disc) / (2.0 * A), (-B + disc) / (2.0 * A)]
	var u := INF
	for x in us:
		if x > 0.0:
			u = minf(u, x)
	var tang := -(t.pre_pos.z + t.pre_vel.z * u + 0.5 * t.pre_acc.z * u * u)   # ring-frame tangential coordinate, Blender +Y
	var off_got := Re * atan2(tang, Re)
	var t_got := (t.pre_step - 1) / float(Engine.physics_ticks_per_second) + u
	rec("f_%s_offset" % zone, off_got, off_exp, 0.02, "landing offset (m, Blender +Y; negative = antispinward for A), analytic %.4f m" % off_exp)
	rec("f_%s_time" % zone, t_got, tt, 2.0 / Engine.physics_ticks_per_second, "landing time (s), analytic %.4f; first contact reported at step %d" % [tt, t.contact_step])
	flag("f_%s_landed_on_floor" % zone, t.contact_step >= 0 and absf(-t.contact_pos.y - Re) < 0.02, -t.contact_pos.y, Re, "first contact with the floor plane")

# g. standing on the ring floor
func check_g() -> void:
	lab.build({"zone": "RING_A", "mode": "COAST", "actor": true, "tool": false, "rails": false})
	var a: WfCrewBody = lab.actor
	var R: float = lab.ring_radius()
	await ticks(180)
	rec("g_standing_speed", a.v_solved.length(), 0.0, 1e-2, "after 3 s on the floor")
	rec("g_standing_height", a.global_position.y, -R + a.profile["height_m"] * 0.5, 0.03, "centre height above the floor plane")
	var g_floor: float = lab.field.g_of(lab.field.eval(WfFrames.v3(0, -R, 0), WfFrames.v3(0, 0, 0)))
	rec("g_floor_field_g", g_floor, 0.501, 1e-3, "sensed field at the floor point, 08 floor_g")
	rec("g_upright", a.global_transform.basis.y.angle_to(Vector3.UP), 0.0, 1e-3, "up = -field at the floor")
	flag("g_standing_flag", a.standing, a.standing, true)

# phase 3: walking is a friction-limited contact force; nothing moves a drifting body
func check_walk() -> void:
	lab.build({"zone": "RING_A", "mode": "COAST", "actor": true, "tool": false, "rails": false})
	var a: WfCrewBody = lab.actor
	await ticks(60)
	a.walk_dir = Vector3.RIGHT
	var vmax := a.profile["test_push_dv_m_s"] as float
	var worst := 0.0
	var vprev := a.v_solved.x
	var dt := 1.0 / Engine.physics_ticks_per_second
	for i in 90:
		await ticks(1)
		worst = maxf(worst, absf(a.v_solved.x - vprev) / dt)
		vprev = a.v_solved.x
	var lim := WfCrewBody.WALK_MU * absf(a.field_now.y)
	rec("walk_speed", a.v_solved.x, vmax, 0.02, "tangential speed along the floor reaches the profile pace (rig test_push_dv)")
	flag("walk_force_limit", worst <= lim * 1.02, worst, "<= mu*N/m = %.4f" % lim, "peak along-floor acceleration, mu = %.1f PROTOTYPE" % WfCrewBody.WALK_MU)
	a.walk_dir = Vector3.ZERO
	await ticks(90)
	rec("walk_stop_by_friction", a.v_solved.length(), 0.0, 1e-2, "no request: the foot contact holds still on the floor")
	lab.build({"zone": "SHIP", "mode": "COAST", "actor": true, "tool": false, "walls": false, "rails": false, "actor_pos": Vector3.ZERO, "actor_vel": Vector3(0.3, 0, 0)})
	var b: WfCrewBody = lab.actor
	b.walk_dir = Vector3.UP
	await ticks(120)
	rec("walk_no_input_accel_in_drift", (b.linear_velocity - Vector3(0.3, 0, 0)).length(), 0.0, 1e-6, "walk input does nothing without a floor and a field")

# h. spine <-> ring handoff
func check_h() -> void:
	var worst := 0.0
	for k in 2:
		var ring: Dictionary = dyn["rings"][k]
		var w := WfFrames.ring_omega(dyn, k, "COAST")
		var r := WfFrames.b2g([ring["centre_x_m"] + 3.0, -11.0, 22.0])
		var v := WfFrames.b2g([0.7, -0.4, 0.9])
		for ang in [0.0, 0.37, 2.5]:
			var rr := WfFrames.to_ring(r, v, ring["centre_x_m"], ang, w)
			var back := WfFrames.to_ship(rr[0], rr[1], ring["centre_x_m"], ang, w)
			for i in 3:
				worst = maxf(worst, maxf(absf(back[0][i] - r[i]), absf(back[1][i] - v[i])))
		# a body at rest in the ring frame has the inertial speed w x r in the ship frame, and vice versa
		var rs := WfFrames.to_ship(WfFrames.v3(0, -ring["floor_radius_m"], 0), WfFrames.v3(0, 0, 0), ring["centre_x_m"], 0.0, w)
		var rb := WfFrames.to_ring(rs[0], rs[1], ring["centre_x_m"], 0.0, w)
		for i in 3:
			worst = maxf(worst, absf(rb[1][i]))
	rec("h_handoff_roundtrip", worst, 0.0, 1e-6, "position and velocity, both rings, three phase angles")

# i. LOW_THRUST tilt and HIGH_POWER
func check_i() -> void:
	var R: float = dyn["rings"][0]["floor_radius_m"]
	var f := WfFrameField.new(dyn, "RING_A", "LOW_THRUST")
	var a := f.eval(WfFrames.v3(0, -R, 0), WfFrames.v3(0, 0, 0))
	rec("i_low_thrust_tilt_deg", rad_to_deg(atan2(-a[0], -a[1])), 11.29, 0.01, "toward aft (-X)")
	for z in ["RING_A", "RING_B"]:
		var h := WfFrameField.new(dyn, z, "HIGH_POWER")
		var ah := h.eval(WfFrames.v3(0, -R, 0), WfFrames.v3(0, 0, 0))
		rec("i_high_power_%s_gx" % z, ah[0] / dyn["standard_gravity_m_s2"], -1.5, 1e-9, "g along X, aft")
		rec("i_high_power_%s_radial" % z, sqrt(ah[1] * ah[1] + ah[2] * ah[2]), 0.0, 1e-9, "no radial component with the rings locked")

# phase 4: mode controller (SIMULATION_ONLY, untimed steps; ring ramp 1800 s WORKING, timing OPEN)
func mode_ctl(zone: String, mode: String) -> WfModeController:
	return WfModeController.new(dyn, WfFrameField.new(dyn, zone, mode), mode)

func check_modes() -> void:
	var R: float = dyn["rings"][0]["floor_radius_m"]
	var g0: float = dyn["standard_gravity_m_s2"]
	var T: float = dyn["spin_ramp"]["study_value_s"]
	var floor_r := WfFrames.v3(0, -R, 0)
	var zero := WfFrames.v3(0, 0, 0)
	var fx := {}
	for f in dyn["fixtures"]:
		fx[f["id"]] = f
	# each mode's field matches the rig fixtures
	var coast := mode_ctl("RING_A", "COAST")
	rec("m_coast_floor_g", coast.field.g_of(coast.field.eval(floor_r, zero)), fx["RING_A_FLOOR"]["expect_g"], 1e-9, "COAST ring floor 0.50097 g")
	var lt := mode_ctl("RING_A", "COAST")
	var e_lt := lt.request("LOW_THRUST")
	var a := lt.field.eval(floor_r, zero)
	rec("m_low_thrust_tilt_deg", rad_to_deg(atan2(-a[0], -a[1])), 11.29, 0.01, "LOW_THRUST tilt toward aft")
	flag("m_low_thrust_steps", e_lt["steps"] == ["DRIVE_ON"] and lt.mode == "LOW_THRUST" and not lt.busy(), e_lt["steps"], ["DRIVE_ON"], "COAST>LOW_THRUST is one instant step")
	# COAST -> HIGH_POWER: spin down and lock first, drive on after (rig table), Euler alpha = -omega/T with the right sign
	var worst_a := 0.0
	var worst_w := 0.0
	var worst_e := 0.0
	var steps_ok := true
	for k in 2:
		var c := mode_ctl("RING_A" if k == 0 else "RING_B", "COAST")
		var e := c.request("HIGH_POWER")
		var w0: float = c.omega_full(k)
		steps_ok = steps_ok and e["steps"] == ["OCCUPANTS_SECURED", "RINGS_SPIN_DOWN", "RINGS_LOCKED", "DRIVE_ON"] and c.ring_state == "SPINNING_DOWN" and not c.drive_on and c.field.a_ship[0] == 0.0
		for t in [0.0, 0.25 * T, 0.5 * T, 0.9 * T]:
			c.skip(t - c.ramp_t)
			var w: float = w0 * (1.0 - t / T)
			worst_w = maxf(worst_w, absf(c.field.w[0] - w))
			worst_a = maxf(worst_a, absf(c.field.alpha[0] - (-w0 / T)))
			# Euler z at the floor point (Godot axes) is -alpha_x * y = -w0 R / T
			var fl := c.field.eval(floor_r, zero)
			worst_e = maxf(worst_e, absf(fl[2] - (-w0 * R / T)))
			worst_e = maxf(worst_e, absf(fl[1] - (-w * w * R)))
		flag("m_ramp_mid_sign_%d" % k, signf(c.field.alpha[0]) == -signf(w0) and absf(c.omega_now(k)) < absf(w0), c.field.alpha[0], -w0 / T, "alpha opposes omega while spinning down (ring %s)" % "AB"[k])
	flag("m_coast_high_power_steps", steps_ok, steps_ok, true, "owner sequence (DYN-026): occupants secured, spin down, lock, then drive on; drive off during the ramp")
	rec("m_ramp_omega", worst_w, 0.0, 1e-12, "omega = omega_full (1 - t/T) at 0, T/4, T/2, 0.9 T")
	rec("m_ramp_alpha", worst_a, 0.0, 1e-15, "alpha = -omega_full / T constant, T = %.0f s" % T)
	rec("m_ramp_euler_and_centrifugal", worst_e, 0.0, 1e-9, "Euler z = -w0 R / T (ring A, floor point) and centrifugal -w^2 R")
	var h := mode_ctl("RING_A", "COAST")
	h.request("HIGH_POWER")
	h.skip(T * 0.5)
	var cross_ramp := h.can_cross("VESTIBULE_1")
	var reason_ramp := h.cross_reason
	h.skip(T)
	var ah := h.field.eval(floor_r, zero)
	flag("m_high_power_settled", h.mode == "HIGH_POWER" and h.ring_state == "STOPPED_LOCKED" and h.drive_on and not h.busy(), h.mode, "HIGH_POWER locked, drive on", "ramp done, drive on after the lock")
	rec("m_high_power_gx", ah[0] / g0, -1.5, 1e-9, "-1.5 g along X, rings locked (envelope bound, not a flight value)")
	rec("m_high_power_radial", sqrt(ah[1] * ah[1] + ah[2] * ah[2]), 0.0, 1e-9, "no radial component, alpha zero after the ramp")
	flag("m_label_envelope", h.ship_accel_label().contains("envelope bound") and h.hud_text().contains("timing OPEN") and h.hud_text().contains("1800"), h.ship_accel_label(), "envelope + timing OPEN label")
	# a drive-off mode leaves the drive off and known
	var dk := mode_ctl("RING_A", "HIGH_POWER")
	var e_h := dk.request("COAST")
	flag("m_high_power_to_coast", e_h["steps"] == ["DRIVE_OFF", "OCCUPANTS_SECURED", "RINGS_UNLOCKED", "RINGS_SPIN_UP"] and dk.field.a_ship[0] == 0.0 and dk.ring_state == "SPINNING_UP", e_h["steps"], "DRIVE_OFF, OCCUPANTS_SECURED, RINGS_UNLOCKED, RINGS_SPIN_UP", "drive off and occupants secured before the rings unlock")
	dk.skip(T * 0.5)
	rec("m_spin_up_alpha_sign", signf(dk.field.alpha[0]) * signf(dk.omega_full(0)), 1.0, 0.0, "alpha has the sign of omega while spinning up")
	dk.skip(T)
	flag("m_spin_up_done", dk.mode == "COAST" and absf(dk.field.w[0] - dk.omega_full(0)) < 1e-12 and dk.field.alpha[0] == 0.0, dk.mode, "COAST at full omega")
	# refusals are logged SIMULATION_ONLY and change nothing
	var rf := mode_ctl("SHIP", "COAST")
	var r1 := rf.request("WARP")
	var r2 := rf.request("HIGH_POWER")
	var r3 := rf.request("DOCKED")
	rf.skip(1.0)
	var bad := true
	for e in [r1, r3]:
		bad = bad and e.get("refused", false) and e["status"] == "SIMULATION_ONLY" and str(e["reason"]) != ""
	flag("m_invalid_refused", bad and rf.mode == "COAST" and r2["refused"] == false and rf.log.any(func(l): return l.get("refused", false) and l["to"] == "WARP"), r1, "refused, SIMULATION_ONLY, logged", "unknown target refused; a request while busy refused")
	var dm := mode_ctl("SHIP", "COAST")
	dm.damaged = ["COAST"]
	flag("m_damaged_refused", dm.request("LOW_THRUST")["refused"], true, true, "DAMAGED state refused")
	# vestibule interlock
	var ic := mode_ctl("SHIP", "COAST")
	var ok_idle := ic.can_cross("VESTIBULE_1")
	ic.drum_synced[0] = false
	var ok_unsync := ic.can_cross("VESTIBULE_1")
	ic.drum_synced[0] = true
	var ok_open := ic.can_cross("VESTIBULE_1", false)
	flag("m_cross_idle", ok_idle and not ok_unsync and not ok_open and not cross_ramp, [ok_idle, ok_unsync, ok_open, cross_ramp], [true, false, false, false], "COAST synchronized: open; unsynchronized, closure open, or mid-ramp (%s): blocked" % reason_ramp)
	flag("m_cross_stopped", h.can_cross("VESTIBULE_1") and not h.can_cross("HULL_NOWHERE"), h.cross_reason, "stopped and locked: open", "unknown edge refused")

# Recording gravity_change: SHIP-frame spine, actor on rail 1, loose tool. COAST -> HIGH_POWER; the ring ramp is skipped before the recording starts
# (no effect in the SHIP frame), then DRIVE_ON switches the ship acceleration on (the mode's envelope bound, not a flight value).
func check_gravity_change() -> void:
	lab.build({"zone": "SHIP", "mode": "COAST", "actor": true, "tool": true, "profile": "human_iva", "tool_pos": Vector3(-0.25, 0.4, 0.6)})
	var a: WfCrewBody = lab.actor
	var t: WfTool = lab.tool
	var m: WfModeController = lab.modes
	await ticks(2)
	var grabbed := a.grab(lab.rail(1))
	var e := m.request("HIGH_POWER")
	m.skip(m.ramp_s() - 0.01)                     # ring ramp done except the last 10 ms; drive still off
	var drive_before := m.drive_on
	await ticks(2)
	var tr: WfRecorder = lab.start_recording("gravity_change")
	tr.scene["labels"] = {"title": "COAST to HIGH_POWER: DRIVE_ON", "accel": m.ship_accel_label_for("HIGH_POWER"),
		"note": "ship acceleration is the mode's envelope bound, not a flight value (SIMULATION_ONLY, ring ramp skipped before the recording)", "drive_on_t_s": 1.0}
	await ticks(60)
	var x0 := t.global_position.x
	var v_float := t.linear_velocity.length()
	m.skip(0.02)                                   # last ramp step done: DRIVE_ON
	var drive_on := m.drive_on
	tr.scene["mode_after"] = field_mode()
	await ticks(120)
	tr.save()
	var g0: float = dyn["standard_gravity_m_s2"]
	flag("gc_steps", grabbed and e["steps"] == ["OCCUPANTS_SECURED", "RINGS_SPIN_DOWN", "RINGS_LOCKED", "DRIVE_ON"] and not drive_before and drive_on, [grabbed, drive_before, drive_on], [true, false, true], "tool floats until DRIVE_ON")
	rec("gc_tool_floats", v_float, 0.0, 1e-6, "tool speed before DRIVE_ON")
	flag("gc_tool_lands_aft", t.global_position.x < x0 - 1.0 and t.contact_step >= 0 and t.linear_velocity.length() < 0.5, t.global_position.x, "aft of %.2f" % (x0 - 1.0), "tool fell toward -X onto the aft wall")
	flag("gc_actor_hangs", a.grip != null and a.global_position.distance_to(lab.rail(1).anchor_point()) < 0.8, a.global_position.x, lab.rail(1).anchor_point().x, "actor still gripping rail 1 under %.2f g" % absf(m.field.a_ship[0] / g0))

func field_mode() -> String:
	return lab.field.mode

# Owner release 2026-10-11 (46 DYN-023/026): ring signs and the transition gates, SIMULATION_ONLY.
func check_owner_sequence() -> void:
	var ra: Dictionary = dyn["rings"][0]
	var rb: Dictionary = dyn["rings"][1]
	flag("o_ring_signs", ra["sign"] == 1 and rb["sign"] == -1 and ra["centre_x_m"] < rb["centre_x_m"], [ra["sign"], rb["sign"]], [1, -1], "ring A (aft) +, ring B (forward) - about +X (08 ring_sign_convention)")
	var wa := WfFrames.ring_omega(dyn, 0, "COAST")
	var wb := WfFrames.ring_omega(dyn, 1, "COAST")
	rec("o_omega_a", wa[0], TAU * 4.0 / 60.0, 1e-9, "+4 rpm about +X")
	rec("o_omega_b", wb[0], -TAU * 4.0 / 60.0, 1e-9, "-4 rpm about +X")
	# an occupant not secured holds the sequence before the ramp (fail closed); securing resumes it
	var c := mode_ctl("RING_A", "COAST")
	c.occupants_securable = false
	c.request("HIGH_POWER")
	var held := c.busy() and c.ring_state == "ROTATING" and c.hold_reason != "" and not c.drive_on
	c.skip(100.0)
	var still := c.ring_state == "ROTATING" and absf(c.spin_frac - 1.0) < 1e-12
	c.occupants_securable = true
	c.resume()
	flag("o_unsecured_holds", held and still and c.ring_state == "SPINNING_DOWN", [held, still, c.ring_state], [true, true, "SPINNING_DOWN"], "held: %s" % c.log.filter(func(l): return l.get("held", false))[0]["reason"])
	# LOW_THRUST during a ring speed change is not released
	var lt := c.request("LOW_THRUST")
	flag("o_low_thrust_in_ramp_refused", lt.get("refused", false) and str(lt["reason"]).contains("not released"), lt.get("reason", ""), "refused (DYN-026)")
	# a ramp never starts with the drive on
	var d := mode_ctl("RING_A", "COAST")
	d.drive_on = true
	d.occupants_secured = true
	flag("o_ramp_drive_on_refused", not d.ramp_allowed()["allowed"], d.ramp_allowed()["reason"], "refused")
	# HIGH_POWER only after the lock: the drive is still off at the end of the ramp's last step
	var h := mode_ctl("RING_A", "COAST")
	h.request("HIGH_POWER")
	h.skip(h.ramp_s() - 1e-3)
	var before := h.drive_on
	h.skip(1.0)
	flag("o_drive_after_lock", not before and h.drive_on and h.ring_state == "STOPPED_LOCKED", [before, h.drive_on, h.ring_state], [false, true, "STOPPED_LOCKED"], "rings locked, then HIGH_POWER permissible")

# Rotary vestibule (46 DYN-027): restraint, both boundaries, matched side only, (r, v) handoff with w x r. SIMULATION_ONLY.
func check_vestibule() -> void:
	var w_ring := float(dyn["rings"][0]["sign"]) * float(dyn["rings"][0]["omega_rad_s"])
	var v := WfVestibule.new(dyn, 0)
	v.dp_equalized = true
	var no_restraint := v.start_sync("RING", w_ring, 4.0)
	v.restrained = true
	v.closures["STATIONARY"] = false
	var open_boundary := v.start_sync("RING", w_ring, 4.0)
	v.closures["STATIONARY"] = true
	var ok_start := v.start_sync("RING", w_ring, 4.0)
	v.step(1.0)
	var mid := v.gate("RING", w_ring)
	v.restrained = false
	v.step(0.5)
	var lost := not v.ramping
	v.restrained = true
	v.start_sync("RING", w_ring, 2.5)
	v.step(3.0)
	var matched := v.gate("RING", w_ring)
	var stat_side := v.gate("STATIONARY", w_ring)
	v.dp_equalized = null
	var dp_unknown := v.gate("RING", w_ring)
	v.dp_equalized = true
	var opened := v.open("RING", w_ring)
	var both := v.open("STATIONARY", w_ring)
	flag("v_ramp_needs_restraint_and_closures", not no_restraint["ok"] and not open_boundary["ok"] and ok_start["ok"], [no_restraint["reason"], open_boundary["reason"]], "refused, refused, started")
	flag("v_closed_while_ramping", not mid["open"] and lost, [mid["reason"], lost], "both closed mid-ramp; ramp stops if restraint is lost")
	rec("v_drum_matched", v.drum_w, w_ring, v.tol(), "drum at the ring speed (rig match tolerance %s rad/s)" % String.num_scientific(v.tol()))
	flag("v_open_matched_only", matched["open"] and not stat_side["open"] and not dp_unknown["open"] and opened["ok"] and not both["ok"], [matched["reason"], stat_side["reason"], dp_unknown["reason"], both["reason"]], "ring side opens; stationary refused (speed), pressure unknown refused, never both open")
	# handoff: occupant restrained in the drum (inertial v = w x r) enters the ring frame at rest; back again unchanged
	var cx: float = dyn["rings"][0]["centre_x_m"]
	var w := WfFrames.v3(w_ring, 0.0, 0.0)
	var r := WfFrames.v3(cx + 0.4, 1.1, -0.6)
	var vin := WfFrames.cross(w, WfFrames.sub(r, WfFrames.v3(cx, 0.0, 0.0)))
	var to_r := WfVestibule.handoff_to_ring(r, vin, cx, 0.8, w)
	var back := WfVestibule.handoff_to_ship(to_r[0], to_r[1], cx, 0.8, w)
	var dv := WfFrames.sub(back[1], vin)
	var dr := WfFrames.sub(back[0], r)
	rec("v_handoff_ring_rest", sqrt(to_r[1][0] ** 2 + to_r[1][1] ** 2 + to_r[1][2] ** 2), 0.0, 1e-12, "co-rotating occupant is at rest in the ring frame")
	rec("v_handoff_inertial_v", sqrt(dv[0] ** 2 + dv[1] ** 2 + dv[2] ** 2), 0.0, 1e-12, "inertial velocity continuous across the handoff")
	rec("v_handoff_position", sqrt(dr[0] ** 2 + dr[1] ** 2 + dr[2] ** 2), 0.0, 1e-12)
	# J01: the same handoff at the real drum restraint pose (rig dynamics.stages.access hold point, ring A at the index): inside the drum
	var acc: Dictionary = dyn["stages"]["access"]
	var hp: Array = acc["line"][int(acc["hold_index"])]["p"]
	var rho := sqrt(hp[1] ** 2 + hp[2] ** 2)
	var drum: Dictionary = acc["drum"]
	flag("v_hold_pose_in_drum", hp[0] >= drum["x_m"][0] and hp[0] <= drum["x_m"][1] and rho >= drum["inner_radius_m"] and rho <= drum["outer_radius_m"],
		[hp[0], rho], [drum["x_m"], [drum["inner_radius_m"], drum["outer_radius_m"]]], "the occupant's restraint point lies in the drum annulus")
	var hv := WfFrames.cross(w, WfFrames.sub(hp, WfFrames.v3(cx, 0.0, 0.0)))
	var h_r := WfVestibule.handoff_to_ring(hp, hv, cx, 0.0, w)
	var h_b := WfVestibule.handoff_to_ship(h_r[0], h_r[1], cx, 0.0, w)
	rec("v_handoff_hold_pose_rest", sqrt(h_r[1][0] ** 2 + h_r[1][1] ** 2 + h_r[1][2] ** 2), 0.0, 1e-12, "restrained occupant at the drum pose is at rest in the ring frame")
	var e_v := WfFrames.sub(h_b[1], hv)
	var e_r := WfFrames.sub(h_b[0], hp)
	rec("v_handoff_hold_pose_continuous", sqrt(e_v[0] ** 2 + e_v[1] ** 2 + e_v[2] ** 2) + sqrt(e_r[0] ** 2 + e_r[1] ** 2 + e_r[2] ** 2), 0.0, 1e-12, "position and velocity back unchanged")
	var bare := sqrt(hv[0] ** 2 + hv[1] ** 2 + hv[2] ** 2)
	flag("v_bare_reparent_error", bare > 0.1, bare, "> 0.1 m/s", "a bare reparent at the drum pose (%.3f m from the axis) would carry w x r = %.3f m/s of spurious speed (why the transform is required)" % [rho, bare])

# Tension-only tether on the Jolt body (DYN-025): impulse accounted, none while slack, outward speed removed, varied masses and speeds.
func check_tether() -> void:
	for pn in ["human_iva", "human_suited"]:
		for vs in [0.3, 1.0]:
			lab.build({"zone": "SHIP", "mode": "EVA", "actor": false, "tool": false, "walls": false, "rails": false})
			var b := WfTetheredBody.new()
			b.configure(dyn, pn, lab.field)
			var anchor := Vector3(-1.5, 0.0, 0.0)
			b.position = anchor + Vector3(0.5, 0.0, 0.0)
			lab.world.add_child(b)
			var tt := WfTether.new(anchor, 2.0, true, "LAB_ANCHOR")
			b.tether = tt
			b.linear_velocity = Vector3(vs, 0.12, 0.0)
			await ticks(1)
			var v0 := b.linear_velocity
			var slack_events := -1
			var steps := 0
			while steps < 600:
				await ticks(1)
				steps += 1
				if slack_events < 0 and b.global_position.distance_to(anchor) > 1.9 and tt.events == 0:
					slack_events = tt.events
				if tt.events > 0 and steps > 5:
					break
			await ticks(30)
			var m: float = dyn["profiles"][pn]["mass_kg"]
			var dp := (b.linear_velocity - v0) * m
			var tag := "t_%s_%.1f" % [pn, vs]
			rec(tag + "_impulse_balance", [dp.x, dp.y, dp.z], [tt.impulse_sum.x, tt.impulse_sum.y, tt.impulse_sum.z], 1e-3 * m, "m dv of the body = logged tether impulse")
			flag(tag + "_slack_no_impulse", slack_events == 0, slack_events, 0, "no impulse while slack")
			rec(tag + "_outward_after", maxf(0.0, b.linear_velocity.dot((b.global_position - anchor).normalized())), 0.0, 1e-5, "no outward speed at the limit")
			flag(tag + "_within_L", b.global_position.distance_to(anchor) <= 2.0 + 1e-4, b.global_position.distance_to(anchor), "<= 2.0 m")
			checks[-1]["record"] = tt.record()
			b.queue_free()
