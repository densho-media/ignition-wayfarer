class_name WfEvaCheck
extends RefCounted
## EVA-OPS-001 headless check (-- --check-eva-ops): runs inside the real EVA Operations scene, through the same bodies, controllers,
## valves, tanks and player actions (do_action), in fixed 60 Hz steps. It asserts the physical promises (momentum, F = m a, Euler's
## equations, gas = F / ve dt, no negative or created gas, separate inventories, conservation through docking and cartridges), the
## drone procedures (undock, dock, follow, avoidance, arms, pickup and release, cartridge delivery, refusals) and a complete scripted
## First Flight. Prints one WF_GODOT_EVA_OPS JSON line and quits (exit 1 on any failure).
##   godot --headless --fixed-fps 60 --path godot res://scenes/eva_ops.tscn -- --check-eva-ops

var ops
var drives_input := true
var t_in := Vector3.ZERO
var r_in := Vector3.ZERO
var brake := false
var suit_goal = null
var suit_face := Vector3.ZERO
var suit_vmax := 0.2
var suit_up := Vector3.UP
var drone_goal = null
var drone_face := Vector3.ZERO
var drone_vmax := 0.5
var drone_up := Vector3.UP
var results := {}
var fails: Array = []
var t0 := 0

func run(o) -> void:
	ops = o
	t0 = Time.get_ticks_msec()
	suit_up = ops.world.rail_up
	drone_up = ops.world.rail_up
	ops.training = true
	await _steps(5)
	if _want("momentum"): await _momentum()
	if _want("thrust"): await _thrust()
	if _want("angular"): await _angular()
	if _want("braking"): await _braking()
	if _want("attitude_hold"): await _attitude_hold()
	if _want("ship_accel"): await _ship_accel()
	if _want("switching"): await _switching()
	if _want("depletion"): await _depletion()
	if _want("docking"): await _docking()
	if _want("follow"): await _follow()
	if _want("avoidance"): await _avoidance()
	if _want("manipulators"): await _manipulators()
	if _want("rescue_fetch"): await _rescue_fetch()
	if _want("refusals"): await _refusals()
	if _want("docked_idle"): await _docked_idle()
	if _want("first_flight"): await _first_flight()
	_ledger()
	if only == "" and results.size() < 34:
		fails.append("only %d of 34 checks ran" % results.size())
	var out := {"result": "PASS" if fails.is_empty() else "FAIL", "fail": fails, "tests": results, "sim_s": snappedf(ops.t_sim, 0.1),
		"wall_s": snappedf((Time.get_ticks_msec() - t0) / 1000.0, 0.1)}
	print("WF_GODOT_EVA_OPS ", JSON.stringify(out))
	ops.get_tree().quit(0 if fails.is_empty() else 1)

var only := OS.get_environment("EVA_ONLY")
var trace := OS.get_environment("EVA_TRACE") != ""
var frame := 0

func _want(n: String) -> bool:
	return only == "" or n in only.split(",")

func tick(_dt: float) -> void:
	frame += 1
	if trace and frame % 60 == 0:
		var d: WfEvaBody = ops.drone
		var s: WfEvaBody = ops.suit
		print(("TRACE t=%.0f drone %s v %.3f gas %.3f contacts %d | suit %s v %.3f held %s sc %d sat %.2f short %s | dgoal %s sgoal %s" % [ops.t_sim, d.global_position, d.linear_velocity.length(),
			ops.drone_gas.usable(), d.contacts, s.global_position, s.linear_velocity.length(), s.held, s.contacts, s.saturation, s.gas_short, drone_goal, suit_goal]) + " feeds " + str(s.feeds.map(func(x): return "%s:%.3f" % [x.id, x.usable()])) + " docked " + str(ops.docked) + " with " + s.contact_with + "/" + d.contact_with + " dcmd %s %s dsum %.1f phase %s mode %d" % [d.cmd_f, d.cmd_t, d.alloc.duty_sum() * d.alloc.thrust_n, ops.dops.phase, ops.dops.mode])

func _steps(n: int) -> void:
	for i in n:
		await ops.get_tree().physics_frame

func _ok(name: String, ok: bool, info: Dictionary) -> void:
	info["ok"] = ok
	results[name] = info
	if not ok:
		fails.append(name + ": " + JSON.stringify(info))

func _until(cond: Callable, max_s: float) -> float:
	var n := int(max_s * 60.0)
	for i in n:
		if cond.call():
			return i / 60.0
		await ops.get_tree().physics_frame
	return -1.0

func _state_pos(b: RigidBody3D) -> Vector3:
	return (PhysicsServer3D.body_get_state(b.get_rid(), PhysicsServer3D.BODY_STATE_TRANSFORM) as Transform3D).origin

func _clear() -> void:
	t_in = Vector3.ZERO
	r_in = Vector3.ZERO
	brake = false
	suit_goal = null
	drone_goal = null

## A free drone well clear of the ship, at rest, manual control, all valves live.
func _free_drone(p: Vector3) -> void:
	_clear()
	if ops.docked:
		ops.undock()
	ops.dops.set_mode(WfDroneOps.Mode.MANUAL)
	ops.drone_ctl.mode = WfEvaControl.Mode.MANUAL
	ops.active = "drone"
	ops._set_body(ops.drone, Transform3D(Basis.IDENTITY, p), Vector3.ZERO, Vector3.ZERO)
	await _steps(2)

func _far() -> Vector3:
	return ops.world.hatch + ops.world.rail_up * 25.0 + Vector3(-20, 0, 0)

# ------------------------------------------------------------------------------------------------------------------------- physics
func _momentum() -> void:
	await _free_drone(_far())
	var d: WfEvaBody = ops.drone
	var v0 := Vector3(0.12, 0.03, -0.05)
	var w0 := Vector3(0.05, 0.11, -0.02)
	ops._set_body(d, d.global_transform, v0, w0)
	await _steps(1)
	var p0 := _state_pos(d)
	var L0: Vector3 = d.world_inertia() * d.angular_velocity
	var g0: float = ops.drone_gas.n2_kg
	await _steps(300)
	var t := 300.0 / 60.0
	var L1: Vector3 = d.world_inertia() * d.angular_velocity
	var pe := _state_pos(d).distance_to(p0 + v0 * t)
	_ok("momentum_conserved", d.linear_velocity.distance_to(v0) < 1e-5 and pe < 2e-3 and L1.distance_to(L0) / L0.length() < 2e-3 and ops.drone_gas.n2_kg == g0,
		{"dv": d.linear_velocity.distance_to(v0), "pos_err_m": pe, "disp_ratio": _state_pos(d).distance_to(p0) / (v0.length() * t), "dL_rel": L1.distance_to(L0) / L0.length(), "gas_used": g0 - ops.drone_gas.n2_kg})

func _thrust() -> void:
	await _free_drone(_far())
	var d: WfEvaBody = ops.drone
	var F := 5.0
	var m0 := d.total_mass()
	var g0: float = ops.drone_gas.n2_kg
	var ax: float = d.alloc.authority("+Fx")
	t_in = Vector3(F / ax, 0, 0)
	await _steps(2)
	var sum_f: float = d.alloc.duty_sum() * d.alloc.thrust_n      # sum of nozzle thrusts (canted nozzles cancel side forces)
	await _steps(118)
	t_in = Vector3.ZERO
	await _steps(1)
	var t := 120.0 / 60.0
	var used: float = g0 - ops.drone_gas.n2_kg
	var want_gas := sum_f / d.ve * t
	var dvx := (d.global_transform.basis.orthonormalized().transposed() * d.linear_velocity).x
	var ve_eff := d.ve * F / sum_f
	var want_dv := ve_eff * log(m0 / (m0 - used))
	_ok("thrust_F_ma", absf(dvx - want_dv) / want_dv < 0.02 and absf(dvx - F / m0 * t) / (F / m0 * t) < 0.02,
		{"dv_m_s": dvx, "F_over_m_t": F / m0 * t, "rocket_eq_ve_eff": want_dv, "allocation_efficiency": F / sum_f})
	_ok("gas_sum_F_over_ve", absf(used - want_gas) / want_gas < 0.02, {"used_kg": used, "expected_kg": want_gas, "net_F_over_ve_kg": F / d.ve * t})
	# consumption scales with thrust: the same burn at 2 N
	await _free_drone(_far())
	g0 = ops.drone_gas.n2_kg
	t_in = Vector3(2.0 / ax, 0, 0)
	await _steps(120)
	t_in = Vector3.ZERO
	await _steps(1)
	var used2: float = g0 - ops.drone_gas.n2_kg
	_ok("gas_scales_with_thrust", absf(used / used2 - 2.5) < 0.05, {"ratio": used / used2, "expected": 2.5})
	_ok("suit_reserve_untouched_by_drone", ops.reserve.n2_kg == ops.reserve.capacity_kg, {"reserve_kg": ops.reserve.n2_kg})

func _angular() -> void:
	await _free_drone(_far())
	var d: WfEvaBody = ops.drone
	var T := 0.10
	var ty: float = d.alloc.authority("+Ty")
	r_in = Vector3(0, T / ty, 0)
	await _steps(30)
	r_in = Vector3.ZERO
	await _steps(1)
	var wb: Vector3 = d.global_transform.basis.orthonormalized().transposed() * d.angular_velocity
	var want := T / d.inertia_t.y.y * 0.5
	_ok("torque_euler", absf(wb.y - want) / want < 0.05 and absf(wb.x) < want * 0.05 and absf(wb.z) < want * 0.05,
		{"w_body": [wb.x, wb.y, wb.z], "expected_wy": want})

func _braking() -> void:
	await _free_drone(_far())
	var d: WfEvaBody = ops.drone
	ops.drone_ctl.mode = WfEvaControl.Mode.ASSIST
	ops._set_body(d, d.global_transform, Vector3(0.3, 0, 0.1), Vector3.ZERO)
	await _steps(1)
	var g0: float = ops.drone_gas.n2_kg
	var m := d.total_mass()
	brake = true
	var t := await _until(func(): return d.linear_velocity.length() < 0.005, 30.0)
	brake = false
	var used: float = g0 - ops.drone_gas.n2_kg
	var ideal := m * Vector3(0.3, 0, 0.1).length() / d.ve
	_ok("brake_uses_gas", t > 0.0 and used >= ideal * 0.95, {"time_s": t, "used_kg": used, "ideal_kg": ideal})
	# the drone, released with no command, keeps drifting: no invisible damping
	ops._set_body(d, d.global_transform, Vector3(0.1, 0, 0), Vector3.ZERO)
	ops.drone_ctl.mode = WfEvaControl.Mode.MANUAL
	await _steps(120)
	_ok("no_invisible_damping", absf(d.linear_velocity.x - 0.1) < 1e-6, {"v": d.linear_velocity.x})

func _attitude_hold() -> void:
	await _free_drone(_far())
	var d: WfEvaBody = ops.drone
	ops.drone_ctl.mode = WfEvaControl.Mode.ASSIST
	ops.drone_ctl.attitude_hold = true
	ops._set_body(d, d.global_transform, Vector3.ZERO, Vector3(0, 0.2, 0.05))
	await _steps(1)
	var g0: float = ops.drone_gas.n2_kg
	var t := await _until(func(): return d.angular_velocity.length() < 0.004, 30.0)
	_ok("assist_rate_damping_uses_gas", t > 0.0 and ops.drone_gas.n2_kg < g0, {"time_s": t, "used_kg": g0 - ops.drone_gas.n2_kg})

func _ship_accel() -> void:
	await _free_drone(_far())
	var d: WfEvaBody = ops.drone
	var a := 1.1 * 9.80665
	ops.field.a_ship = WfFrames.v3(a, 0, 0)
	await _steps(1)
	var v0 := d.linear_velocity
	await _steps(60)
	var acc := (d.linear_velocity - v0) / 1.0
	ops.field.a_ship = WfFrames.v3(0, 0, 0)
	_ok("ship_acceleration_relative", absf(acc.x + a) < 0.01 * a and Vector2(acc.y, acc.z).length() < 1e-4, {"a_rel": [acc.x, acc.y, acc.z], "a_ship": a})
	# burn preset: the astronaut stands on the ram face and walks; cold gas cannot lift the pair
	ops.set_frame("BURNBROW_11")
	await _steps(90)
	var s: WfEvaBody = ops.suit
	var st0 := s.standing
	t_in = Vector3(0, 0, 1)
	ops.active = "suit"
	var p0 := s.global_position
	await _steps(120)
	t_in = Vector3(0, 1, 0)                     # try to lift off with the thrusters
	await _steps(60)
	t_in = Vector3.ZERO
	await _steps(30)
	var walked := Vector2(s.global_position.y - p0.y, s.global_position.z - p0.z).length()
	_ok("burn_stand_walk_no_hover", st0 and s.standing and walked > 0.3 and s.global_position.x < p0.x + 0.2,
		{"standing": s.standing, "walked_m": walked, "x_rise_m": s.global_position.x - p0.x})
	ops.set_frame("DRIFT")
	ops.start_free(false)
	await _steps(5)

func _switching() -> void:
	await _free_drone(_far())
	var d: WfEvaBody = ops.drone
	var s: WfEvaBody = ops.suit
	ops._set_body(d, d.global_transform, Vector3(0.05, 0.01, 0), Vector3(0, 0.02, 0))
	await _steps(2)
	var pd := d.global_position
	var vd := d.linear_velocity
	var gd: float = ops.drone_gas.n2_kg
	var ps := s.global_position
	ops.do_action("evaops.astronaut")
	ops.do_action("evaops.drone")
	ops.do_action("evaops.astronaut")
	_ok("switch_keeps_state", d.global_position == pd and d.linear_velocity == vd and ops.drone_gas.n2_kg == gd and s.global_position == ps,
		{"drone_moved": d.global_position.distance_to(pd)})
	await _steps(60)
	_ok("switch_motion_continues", d.global_position.distance_to(pd + vd * 1.0) < 0.01, {"err_m": d.global_position.distance_to(pd + vd * 1.0)})

func _depletion() -> void:
	await _free_drone(_far())
	var d: WfEvaBody = ops.drone
	var tank: WfN2Tank = ops.drone_gas
	tank.draw(tank.usable() - 0.002)
	t_in = Vector3(1, 0, 0)
	await _steps(240)
	t_in = Vector3.ZERO
	_ok("tank_never_negative", tank.n2_kg >= tank.residual_kg - 1e-12 and tank.usable() == 0.0 and d.gas_short and d.delivered_f.length() < 1e-9,
		{"n2_kg": tank.n2_kg, "residual_kg": tank.residual_kg, "delivered_N": d.delivered_f.length()})
	tank.training_reset()
	# suit: emergency floor keeps the thrusters live; empty means nothing fires
	ops.start_free(false)
	ops.undock()
	await _steps(2)
	var s: WfEvaBody = ops.suit
	s.held = false
	ops.active = "suit"
	ops.training_vent_reserve(ops.reserve.usable_full() * 0.2)
	var st1: String = ops.suit_status()
	t_in = Vector3(0, 0, 0.5)
	await _steps(10)
	var live := s.delivered_f.length() > 0.1
	ops.training_vent_reserve(0.0)
	await _steps(10)
	var st2: String = ops.suit_status()
	var dead := s.delivered_f.length() < 1e-9
	t_in = Vector3.ZERO
	_ok("emergency_reserve_live", st1 == "EMERGENCY ONLY" and live, {"status": st1})
	_ok("depletion_disables", st2 == "MANEUVERING UNAVAILABLE" and dead, {"status": st2})
	ops.training_reset()
	await _steps(5)

func _docking() -> void:
	ops.training_reset()
	ops.start_free(false)
	await _steps(5)
	var s: WfEvaBody = ops.suit
	var gas0: float = ops.total_gas()
	ops.do_action("evaops.dock")                 # release
	await _steps(120)
	var sep: float = ops.drone.global_position.distance_to(s.global_position)
	_ok("undock", not ops.docked and sep > 0.3, {"separation_m": sep})
	ops.do_action("evaops.dock")                 # approach and dock
	var t := await _until(func(): return ops.docked, 240.0)
	var gas1: float = ops.total_gas()
	_ok("dock_autonomous", t > 0.0, {"time_s": t, "phase": ops.dops.phase, "msg": ops.dops.report})
	_ok("docking_creates_no_gas", gas1 <= gas0 + 1e-9, {"before_kg": gas0, "after_kg": gas1})

func _follow() -> void:
	ops.training_reset()
	ops.start_free(false)
	await _steps(5)
	ops.undock()
	ops.suit.held = true
	await _steps(30)
	ops.dops.set_mode(WfDroneOps.Mode.FOLLOW)
	var s: WfEvaBody = ops.suit
	var t := await _until(func():
		var off := WfEvaPkg.v(ops.pkg["assist"]["follow_offset_m"])
		var goal: Vector3 = s.global_position + s.global_transform.basis.orthonormalized() * Vector3(off.x, off.y, -off.z)
		return ops.drone.global_position.distance_to(goal) < 0.3 and ops.drone.linear_velocity.length() < 0.03, 120.0)
	_ok("follow_station", t > 0.0, {"time_s": t})
	ops.dops.set_mode(WfDroneOps.Mode.MANUAL)

func _avoidance() -> void:
	ops.training_reset()
	ops.start_free(false)
	await _steps(5)
	ops.undock()
	await _steps(5)
	var d: WfEvaBody = ops.drone
	var r := 12.0
	var p := Vector3(ops.world.face_x(r) + 3.0, r * 0.6, r * 0.8)
	ops._set_body(d, Transform3D(Basis.IDENTITY, p), Vector3.ZERO, Vector3.ZERO)
	d.max_contact_speed = 0.0
	ops.dops.set_mode(WfDroneOps.Mode.RETURN_SHIP)
	var crossed := false
	var touched := false
	for i in 90 * 60:
		await ops.get_tree().physics_frame
		var q := d.global_position
		var rq: float = ops.world.radius_of(q)
		if rq < ops.world.shield_r and q.x < ops.world.face_x(rq) - 0.12 and q.x > ops.world.face_x(rq) - 3.7:
			crossed = true
		if d.contacts > 0:
			touched = true
	_ok("obstacle_avoidance", not crossed and not touched, {"contact_v": d.max_contact_speed, "crossed_brow": crossed, "touched": touched, "end_r": ops.world.radius_of(d.global_position), "end_x": d.global_position.x})
	ops.dops.set_mode(WfDroneOps.Mode.MANUAL)

func _manipulators() -> void:
	ops.training_reset()
	ops.start_free(false)
	await _steps(5)
	ops.undock()
	await _steps(5)
	var d: WfEvaBody = ops.drone
	var st: Dictionary = ops.world.station
	ops.dops.toggle_arms()
	var ta := await _until(func(): return ops.dops.arms_ready(), 5.0)
	_ok("arms_deploy", ta > 0.0 and ta <= 2.2, {"time_s": ta})
	# put the drone at the rack, nose to it, then pick up
	var goal: Vector3 = st["rack"] + st["out"] * 0.55 + Vector3.RIGHT * 0.05
	ops.dops.set_mode(WfDroneOps.Mode.MANUAL)
	ops.active = "drone"
	ops.drone_ctl.mode = WfEvaControl.Mode.ASSIST
	drone_goal = goal
	drone_face = -st["out"]
	drone_vmax = 0.3
	var t := await _until(func(): return d.global_position.distance_to(goal) < 0.05 and d.linear_velocity.length() < 0.02, 120.0)
	drone_goal = null
	var n0 := int(st["cartridges"])
	ops.do_action("evaops.gripper")
	var got: bool = ops.dops.holding != null
	_ok("pickup_from_rack", t > 0.0 and got and int(st["cartridges"]) == n0 - 1, {"time_s": t, "msg": ops.dops.report, "rack": st["cartridges"],
		"miss_m": d.global_position.distance_to(goal), "v": d.linear_velocity.length(), "shoulder_to_rack": ops.dops.shoulder_b().distance_to(st["rack"])})
	if got:
		var c: WfCartridge = ops.dops.holding
		ops._set_body(d, d.global_transform, Vector3(0.02, 0, 0), Vector3.ZERO)
		await _steps(2)
		ops.do_action("evaops.gripper")
		await _steps(30)
		var free_ok: bool = c.where == WfCartridge.Where.FREE and c.body != null and absf(c.body.linear_velocity.x - 0.02) < 0.005
		_ok("release_object", free_ok, {"v": c.body.linear_velocity.x if c.body != null else -1.0})
		# catch it again
		ops._set_body(d, d.global_transform, c.body.linear_velocity, Vector3.ZERO)
		await _steps(2)
		ops.do_action("evaops.gripper")
		_ok("regrab_object", ops.dops.holding == c, {"msg": ops.dops.report})
	ops.start_free(false)
	await _steps(5)

func _rescue_fetch() -> void:
	ops.training_reset()
	ops.start_free(false)
	await _steps(5)
	ops.undock()
	ops.suit.held = false
	await _steps(5)
	var s: WfEvaBody = ops.suit
	# the astronaut drifts 3 m out from the hatch, at rest; the reserve is vented to its emergency level (training)
	ops.place_suit(ops.suit_frame().translated(ops.world.rail_up * 3.0 + Vector3.RIGHT * 2.0))
	ops.training_vent_reserve(ops.reserve.usable_full() * 0.1)
	ops.dops.set_mode(WfDroneOps.Mode.FOLLOW)
	await _steps(240)
	var dv0: float = ops.suit_dv_available()
	var r0: int = ops.rescues
	ops.active = "suit"
	ops.do_action("evaops.help")
	var kind: String = ops.dops.rescue_kind
	var t := await _until(func(): return ops.rescues > r0 or ops.rescue_failures > 0, 400.0)
	var dv1: float = ops.suit_dv_available()
	_ok("rescue_fetch_cartridge", t > 0.0 and ops.rescues > r0 and kind == "FETCH" and ops.cartridge_seated != null and dv1 > dv0 + 0.5,
		{"time_s": t, "kind": kind, "dv_before": dv0, "dv_after": dv1, "msg": ops.dops.report, "phase": ops.dops.phase})
	# the suit flies on cartridge gas first; the reserve is held
	var r_before: float = ops.reserve.n2_kg
	var c_before: float = ops.cartridge_seated.tank.n2_kg if ops.cartridge_seated != null else 0.0
	t_in = Vector3(0, 0, 0.5)
	await _steps(60)
	t_in = Vector3.ZERO
	_ok("cartridge_feeds_first", ops.cartridge_seated != null and ops.cartridge_seated.tank.n2_kg < c_before and ops.reserve.n2_kg == r_before,
		{"cartridge_used_kg": c_before - (ops.cartridge_seated.tank.n2_kg if ops.cartridge_seated != null else 0.0), "reserve_used_kg": r_before - ops.reserve.n2_kg})

func _refusals() -> void:
	# station empty and drone too low for a share
	ops.training_reset()
	await _steps(5)
	ops.undock()
	ops.suit.held = false
	await _steps(5)
	ops.world.station["cartridges"] = 0
	ops.drone_gas.draw(ops.drone_gas.usable() - 0.004)
	ops.dops.request_rescue()
	var r1: String = ops.dops.report
	_ok("refuse_empty_station_low_gas", ops.dops.mode != WfDroneOps.Mode.RESCUE and r1.contains("station empty"), {"msg": r1})
	ops.drone_gas.training_reset()
	# station empty but the drone can dock and share
	ops.dops.request_rescue()
	_ok("share_when_no_cartridge", ops.dops.mode == WfDroneOps.Mode.RESCUE and ops.dops.rescue_kind == "SHARE", {"msg": ops.dops.report})
	ops.dops.set_mode(WfDroneOps.Mode.MANUAL)
	# astronaut too fast
	ops._set_body(ops.suit, ops.suit.global_transform, Vector3(1.2, 0, 0), Vector3.ZERO)
	ops.dops.request_rescue()
	_ok("refuse_fast_astronaut", ops.dops.mode != WfDroneOps.Mode.RESCUE and ops.dops.report.contains("too fast"), {"msg": ops.dops.report})
	ops._set_body(ops.suit, ops.suit.global_transform, Vector3.ZERO, Vector3.ZERO)
	# propulsion fault
	for i in 4:
		ops.a_free.failed[i] = true
	ops.dops.request_rescue()
	_ok("refuse_propulsion_fault", ops.dops.mode != WfDroneOps.Mode.RESCUE and ops.dops.report.contains("fault"), {"msg": ops.dops.report})
	ops.training_reset()
	await _steps(5)

func _docked_idle() -> void:
	ops.training_reset()
	await _steps(5)
	var s: WfEvaBody = ops.suit
	ops.do_action("evaops.grab")
	ops._set_body(s, s.global_transform.translated(ops.world.rail_up * 3.0), Vector3.ZERO, Vector3.ZERO)
	await _steps(2)
	var g0: float = ops.drone_gas.n2_kg
	await _steps(1800)
	var idle: float = g0 - ops.drone_gas.n2_kg
	var b: Basis = s.global_transform.basis.orthonormalized()
	g0 = ops.drone_gas.n2_kg
	suit_goal = s.global_position + Vector3.RIGHT * 50.0
	suit_face = -b.z
	suit_up = b.y
	suit_vmax = 0.1
	await _steps(600)
	var g1: float = ops.drone_gas.n2_kg
	await _steps(1200)
	var cruise: float = (g1 - ops.drone_gas.n2_kg) / 20.0
	suit_goal = null
	_ok("docked_hold_and_cruise_gas", idle < 0.005 and cruise < 0.001, {"idle_30s_kg": idle, "accel_10s_kg": g0 - g1, "cruise_kg_per_s": cruise, "v": s.linear_velocity.length(),
		"w": s.angular_velocity.length()})

# ----------------------------------------------------------------------------------------------------------------- First Flight
## Fly the astronaut to p; with a lift, go out from the surface first and come down onto the target (clear of the hatch fitting).
## face / upv: the attitude to fly in (step_goto points body -Z at `face`, +Y towards `upv`); zero keeps the current attitude.
func _hop(p: Vector3, vmax: float, max_s: float, lift := 0.0, face := Vector3.ZERO, upv := Vector3.ZERO) -> bool:
	if ops.suit.held:
		ops.do_action("evaops.grab")
	if face == Vector3.ZERO:
		var b: Basis = ops.suit.global_transform.basis.orthonormalized()
		face = -b.z
		upv = b.y
	if lift > 0.0:
		var up: Vector3 = ops.world.rail_up
		var a: Vector3 = ops.suit.global_position + up * lift
		if not await _hop(a, vmax, max_s * 0.3, 0.0, face, upv):
			return false
		if not await _hop(p + up * lift, vmax, max_s * 0.5, 0.0, face, upv):
			return false
	suit_goal = p
	suit_face = face
	suit_up = upv
	suit_vmax = vmax
	var t := await _until(func(): return ops.suit.global_position.distance_to(p) < 0.12 and ops.suit.linear_velocity.length() < 0.03, max_s)
	suit_goal = null
	await _steps(2)
	return t >= 0.0

## True when rays along a->b, on the line and on a ring of radius r around it, meet nothing.
func _clear_path(a: Vector3, b: Vector3, r: float) -> bool:
	var u := (b - a).normalized()
	var x := u.cross(Vector3.RIGHT if absf(u.x) < 0.9 else Vector3.UP).normalized()
	var y := u.cross(x)
	var offs := [Vector3.ZERO]
	for i in 8:
		var t := TAU * i / 8.0
		offs.append((x * cos(t) + y * sin(t)) * r)
	for o in offs:
		if not ops.ray(a + o, b + o).is_empty():
			return false
	return true

func _first_flight() -> void:
	ops.scenario.start()
	ops.suit_ctl.rate_max = 0.04          # a trained astronaut turns slowly: rotation gas grows with the rate
	await _steps(5)
	var sc: WfEvaScenario = ops.scenario
	var rt: Dictionary = ops.pkg["ship"]["route"]
	var up: Vector3 = ops.world.rail_up
	var log := []
	# 1 preparation
	ops.do_action("evaops.interact")
	await _steps(2)
	log.append(sc.stage)
	# 2 surface: tether, then hand over hand along the forward anchors
	ops.do_action("evaops.tether")
	# keep the start pose relative to the grip (the airlock hold) for each anchor, without the along-rail part
	var s0: Vector3 = ops.suit.global_position - WfEvaPkg.v(rt["holds"]["airlock"]["p"])
	var s0p := s0 - Vector3.RIGHT * s0.x
	for a in rt["anchors"]:
		if a["run"] != "forward":
			continue
		# prone along the rail, chest to the hull, head forward: the CoM 0.55 m off the anchor line, hands on it
		var p := WfEvaPkg.v(a["p"]) + up * 0.55
		var first: bool = a["id"] == "ANC_FORWARD_00"
		if not await _hop(p, 0.04, 240.0, 0.45 if first else 0.0, up, Vector3.RIGHT):
			log.append("hop_fail:%s miss %.2f" % [a["id"], ops.suit.global_position.distance_to(p)])
			break
		ops.do_action("evaops.grab")
		await _steps(2)
	await _steps(5)
	log.append(sc.stage)
	# 3 free flight to the nearest Brow fixture on the aft face
	ops.do_action("evaops.tether")
	# the nearest fixture with a straight line through a gap in the Brow truss wide enough for the pair (rays around the line)
	var best := {}
	var bd := INF
	var sp: Vector3 = ops.suit.global_position
	for h in ops.world.holds:
		if h["kind"] != "brow_fixture":
			continue
		var tgt: Vector3 = h["p"] - Vector3.RIGHT * 0.6
		var dd := sp.distance_to(tgt)
		if dd < bd and _clear_path(sp, tgt, 0.75):
			best = h
			bd = dd
	if not best.is_empty():
		await _hop(best["p"] - Vector3.RIGHT * 0.6, 0.07, 400.0)
		ops.do_action("evaops.grab")
	else:
		log.append("no_clear_fixture")
	await _steps(5)
	log.append(sc.stage)
	# 4 deployment
	ops.do_action("evaops.dock")
	await _steps(150)
	log.append(sc.stage)
	# 5 drone flight and inspection of another fixture
	ops.do_action("evaops.drone")
	var tgt := {}
	for h in ops.world.holds:
		if h["kind"] == "brow_fixture" and h != best and h["p"].distance_to(best["p"]) > 4.0 and h["p"].distance_to(best["p"]) < 9.0:
			tgt = h
			break
	if not tgt.is_empty():
		drone_goal = tgt["p"] - Vector3.RIGHT * 1.6
		drone_face = Vector3.RIGHT
		drone_vmax = 0.15
		await _until(func(): return ops.drone.global_position.distance_to(drone_goal) < 0.1 and ops.drone.linear_velocity.length() < 0.02, 120.0)
		drone_goal = null
		await _until(func(): return ops.drone.angular_velocity.length() < 0.01, 10.0)
		ops.do_action("evaops.interact")
	await _steps(5)
	log.append(sc.stage)
	# 6 propellant: fly back gently with follow
	drone_goal = ops.suit.global_position - Vector3.RIGHT * 1.5
	drone_face = Vector3.RIGHT
	drone_vmax = 0.12
	await _until(func(): return sc.stage != 5, 150.0)
	drone_goal = null
	log.append(sc.stage)
	# 7 resupply: the drone fetches a cartridge
	ops.do_action("evaops.astronaut")
	ops.do_action("evaops.help")
	var f0: int = ops.rescue_failures
	await _until(func(): return sc.stage != 6 or ops.rescue_failures > f0, 400.0)
	log.append(sc.stage)
	# 8 return: back out through the same truss gap on cartridge gas, grip the station rack, stow the cartridge, let the drone dock
	# (the astronaut holds on, no gas), then fly the docked pair to the hatch handhold
	await _hop(sp, 0.08, 400.0)
	var rack: Vector3 = ops.world.station["rack"] + up * 0.6
	await _hop(rack, 0.08, 300.0)
	ops.do_action("evaops.grab")
	ops.do_action("evaops.interact")
	ops.do_action("evaops.dock")
	await _until(func(): return ops.docked, 240.0)
	var hatch := WfEvaPkg.v(rt["holds"]["airlock"]["p"]) + up * 0.5
	await _hop(hatch, 0.06, 300.0)
	ops.do_action("evaops.grab")
	await _steps(5)
	log.append(sc.stage)
	ops.suit_ctl.rate_max = 0.25
	_ok("first_flight_complete", sc.finished, {"stages_reached": log, "stage": sc.stage, "msgs": ops.messages.map(func(m): return m["t"])})

func _ledger() -> void:
	var err := 0.0
	var tanks: Array = [ops.reserve, ops.drone_gas]
	for c in ops.cartridges:
		tanks.append((c as WfCartridge).tank)
	for t in tanks:
		err = maxf(err, absf((t as WfN2Tank).ledger_error()))
	_ok("nitrogen_ledger", err < 1e-9, {"max_error_kg": err, "tanks": tanks.size()})
