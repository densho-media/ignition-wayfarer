class_name WfDroneOps
extends RefCounted
## The companion drone's autonomy, manipulators and the rescue procedure (EVA-OPS-001). Everything here commands thrust through the
## drone's WfEvaControl (so it costs gas and is limited by the real nozzle authority) or changes an attachment state under a physical
## precondition (reach, relative speed, alignment). Nothing is repositioned.
##
## Modes: MANUAL (the player flies, or nothing fires), HOLD (keep station), FOLLOW (a station beside the astronaut), RETURN_ASTRONAUT
## (to the approach gate behind the suit, then the docking approach), RETURN_SHIP (to the station's service socket), RESCUE (the
## state machine below).
##
## Rescue: REQUEST -> CHECK (gas, cartridges, astronaut speed) -> either FETCH (to the station -> ACQUIRE a cartridge with arm B ->
## CARRY to the astronaut -> PRESENT: arm B seats it in the empty dock channel) or SHARE (approach and dock: the pair then flies on the
## drone's gas). Success only when the suit's available delta-v has actually risen. Every refusal names its reason.

enum Mode { MANUAL, HOLD, FOLLOW, RETURN_ASTRONAUT, RETURN_SHIP, RESCUE }
const MODE_NAMES := ["MANUAL", "HOLD", "FOLLOW", "RETURN TO ASTRONAUT", "RETURN TO SHIP", "RESCUE"]

var ops                               # the WfEvaOps scene (bodies, world, docking)
var ctl: WfEvaControl
var mode := Mode.MANUAL
var phase := ""                       # docking / rescue sub-state
var hold_at := Vector3.ZERO
var arms_deployed := false
var arms_t := 0.0                     # 0 stowed .. 1 deployed (2 s motion)
var gripper_closed := false
var holding                           # the WfCartridge in arm B, or null
var rescue_kind := ""                 # FETCH / SHARE
var rescue_speed := 1.0               # cruise speed of this rescue (economy when gas is short)
var rescue_dv0 := 0.0
var report := ""                      # last rescue / docking message
var report_ok := true
var seat_t := 0.0
var stuck_t := 0.0
var _last_d := INF
var avoid_wp = null                   # obstacle waypoint (Vector3) or null

func _init(o, c: WfEvaControl) -> void:
	ops = o
	ctl = c

func set_mode(m: int) -> void:
	mode = m
	phase = ""
	avoid_wp = null
	hold_at = ops.drone.global_position
	stuck_t = 0.0
	_last_d = INF

func name() -> String:
	return MODE_NAMES[mode] + ((" · " + phase) if phase != "" else "")

func say(t: String, ok := true) -> void:
	report = t
	report_ok = ok
	ops.say(t)

# -------------------------------------------------------------------------------------------------------------------------- planning
## Delta-v the drone needs for a leg of `d` metres at the autopilot's speed, plus matching a target moving at `v_t`.
func leg_dv(d: float, v_t: float, v_cruise := -1.0) -> float:
	var a: float = float(ctl.g["autopilot_brake_fraction"]) * ctl.min_force() / ops.drone.total_mass()
	var vc := v_cruise if v_cruise > 0.0 else float(ctl.g["autopilot_speed_m_s"])
	var v := minf(vc, sqrt(maxf(a * d, 0.0)))
	return 2.0 * v + v_t

## Economy cruise: the fastest cruise speed (down to ECO_MIN) whose fetch, with margin, fits the gas left.
const ECO_MIN := 0.15
func _fetch_need(to_st: float, st_to_s: float, back: float, vs: float, vc: float, margin: float) -> float:
	return (leg_dv(to_st, 0.0, vc) + leg_dv(st_to_s, vs, vc) + leg_dv(back, 0.0, vc)) * margin

## Evaluate a rescue: {ok, kind, reason, need, have}.
func evaluate() -> Dictionary:
	var d: WfEvaBody = ops.drone
	var s: WfEvaBody = ops.suit
	var rules: Dictionary = ops.pkg["rules"]
	var margin := float(rules["rescue_margin"])
	if ops.docked:
		return {"ok": false, "reason": "the drone is docked: the pair already flies on drone gas"}
	if ops.drone_fault_valves() > 3:
		return {"ok": false, "reason": "drone propulsion fault: too many valves failed"}
	var vs := s.linear_velocity.length()
	if vs > float(rules["rescue_max_target_speed_m_s"]):
		return {"ok": false, "reason": "astronaut moving too fast for a safe approach (%.2f m/s > %.2f): brake first or use the tether" % [vs, float(rules["rescue_max_target_speed_m_s"])]}
	var have: float = d.dv_left() * ops.a_free.gas_efficiency() * 0.85      # canted-nozzle losses, and about 15 % for attitude and avoidance
	var st: Vector3 = ops.world.station["rack"]
	var to_st := d.global_position.distance_to(st)
	var st_to_s := st.distance_to(s.global_position)
	var back := s.global_position.distance_to(st)
	var vc := float(ctl.g["autopilot_speed_m_s"])
	var fetch_need := _fetch_need(to_st, st_to_s, back, vs, vc, margin)
	while fetch_need > have and vc > ECO_MIN + 1e-6:
		vc = maxf(ECO_MIN, vc * 0.8)
		fetch_need = _fetch_need(to_st, st_to_s, back, vs, vc, margin)
	var share_need := (leg_dv(d.global_position.distance_to(s.global_position), vs)) * margin
	# docked, the pair (about 7 x the drone's mass) must still get back: count the return on the pair's mass
	var pair_dv := WfEvaPkg.dv(d.total_mass() + s.total_mass(), maxf(0.0, d.usable_kg() - share_need * d.total_mass() / d.ve), d.ve)
	var pair_need := (2.0 * minf(0.3, sqrt(0.02 * back)) + vs) * margin
	var cart_ok := int(ops.world.station["cartridges"]) > 0 and ops.cartridge_seated == null
	if cart_ok and have >= fetch_need:
		return {"ok": true, "kind": "FETCH", "need": fetch_need, "have": have, "cruise": vc}
	if have >= share_need and pair_dv >= pair_need:
		return {"ok": true, "kind": "SHARE", "need": share_need, "have": have, "pair_dv": pair_dv}
	if not cart_ok:
		var why := "station empty" if int(ops.world.station["cartridges"]) <= 0 else "a cartridge is already seated"
		return {"ok": false, "reason": "%s, and the drone's %.2f m/s cannot dock and bring the pair back (needs %.2f + %.2f pair)" % [why, have, share_need, pair_need]}
	return {"ok": false, "reason": "drone gas too low: %.2f m/s left, a fetch needs %.2f and docking needs %.2f" % [have, fetch_need, share_need]}

func request_rescue() -> void:
	var e := evaluate()
	if not e["ok"]:
		say("RESCUE UNAVAILABLE: " + e["reason"] + (". Training: F5 resets the scenario." if ops.training else "."), false)
		return
	mode = Mode.RESCUE
	rescue_kind = e["kind"]
	rescue_dv0 = ops.suit_dv_available()
	rescue_speed = float(e.get("cruise", ctl.g["autopilot_speed_m_s"]))
	phase = "TO STATION" if rescue_kind == "FETCH" else "TO ASTRONAUT"
	say("Drone: resupply accepted (%s). Gas check: %.2f m/s left, %.2f needed with margin%s." % [
		"fetch an RC-1 cartridge" if rescue_kind == "FETCH" else "dock and share my gas", e["have"], e["need"],
		" (economy cruise %.2f m/s)" % rescue_speed if rescue_speed < float(ctl.g["autopilot_speed_m_s"]) - 1e-6 else ""])

# ---------------------------------------------------------------------------------------------------------------------------- step
func step(dt: float) -> void:
	_arms(dt)
	var d: WfEvaBody = ops.drone
	if ops.docked:
		return
	match mode:
		Mode.MANUAL:
			pass
		Mode.HOLD:
			ctl.hold_pos = true
			ctl.hold_point = hold_at
			ctl.ref_vel = Vector3.ZERO
			ctl.step_player(Vector3.ZERO, Vector3.ZERO)
		Mode.FOLLOW:
			var s: WfEvaBody = ops.suit
			var off := WfEvaPkg.v(ctl.g["follow_offset_m"])
			var goal := s.global_position + s.global_transform.basis.orthonormalized() * Vector3(off.x, off.y, -off.z)
			_goto(goal, s.linear_velocity, s.global_position - d.global_position, dt)
		Mode.RETURN_ASTRONAUT:
			_dock_approach(dt)
		Mode.RETURN_SHIP:
			var st: Dictionary = ops.world.station
			var goal: Vector3 = st["socket"] + st["out"] * 0.8
			var dist := _goto(goal, Vector3.ZERO, -st["out"], dt)
			if dist < 0.1 and d.linear_velocity.length() < 0.03:
				set_mode(Mode.HOLD)
				say("Drone: holding at the station socket.")
		Mode.RESCUE:
			_rescue(dt)

func _goto(goal: Vector3, v_goal: Vector3, face: Vector3, dt: float, vmax := -1.0) -> float:
	var d: WfEvaBody = ops.drone
	var target := goal
	# obstacle avoidance: look ahead along the planned path; on a hit, detour to a point off the surface
	var path := goal - d.global_position
	var look := minf(path.length(), 1.5 + d.linear_velocity.length_squared() / maxf(0.02, 2.0 * 0.5 * ctl.min_force() / d.total_mass()))
	if avoid_wp != null:
		if d.global_position.distance_to(avoid_wp) < 0.6:
			avoid_wp = null
		else:
			target = avoid_wp
	elif path.length() > 0.5:
		var hit: Dictionary = ops.ray(d.global_position, d.global_position + path.normalized() * look)
		if not hit.is_empty():
			var n: Vector3 = hit["normal"]
			var side := path.normalized().cross(n).cross(n).normalized() * -1.0
			avoid_wp = hit["position"] + n * 2.5 + side * 1.0
			target = avoid_wp
	var vm := vmax if vmax > 0.0 else float(ctl.g["transit_speed_m_s"])
	# never build up more speed than the gas left can take off again, twice over (canted-nozzle losses included)
	vm = minf(vm, maxf(0.02, 0.25 * d.dv_left() * d.alloc.gas_efficiency()))
	return ctl.step_goto(target, v_goal if target == goal else Vector3.ZERO, face, vm, ops.suit.global_transform.basis.y)

# --------------------------------------------------------------------------------------------------------------------------- docking
## Docked pose and approach gate of the drone (world), from the package dock transform and the suit's present pose.
func dock_target() -> Transform3D:
	return ops.dock_world()

func _dock_approach(dt: float) -> void:
	var d: WfEvaBody = ops.drone
	var s: WfEvaBody = ops.suit
	if ops.cartridge_seated != null:
		say("Drone: the dock channel holds a cartridge. Stow it at the station first (E at the rack), or take it with the gripper.", false)
		set_mode(Mode.HOLD)
		return
	var T := dock_target()
	var back: Vector3 = -s.global_transform.basis.orthonormalized().z          # behind the astronaut: the dock axis
	var gate := float(ctl.g["approach_gate_m"])
	var ns: Dictionary = ops.pkg["drone"]["near_suit"]
	var to_dock := T.origin - d.global_position
	var along := to_dock.dot(-back)                     # distance still to close along the dock axis
	var lateral := to_dock + back * along               # off-axis error
	var face := -T.basis.z                              # nose direction when docked
	if phase == "" or phase == "TO GATE":
		phase = "TO GATE"
		var gp := T.origin + back * gate
		var dist := _goto(gp, s.linear_velocity, face, dt)
		if dist < 0.06 and (d.linear_velocity - s.linear_velocity).length() < 0.04:
			phase = "FINAL"
	elif phase == "FINAL":
		# straight in along the axis: speed limited to approach_speed_m_s, then the capture speed limit in the last 0.12 m
		var vmax := float(ns["approach_speed_m_s"]) if along > float(ns["approach_m"][1]) else float(ops.pkg["drone"]["approach_speed_max_m_s"]) * 0.8
		var goal := T.origin
		var e := goal - d.global_position
		var v_des := s.linear_velocity + e.normalized() * minf(vmax, e.length() / 1.5)
		var dv := v_des - d.linear_velocity
		var f_w := dv * d.total_mass() / 0.8
		d.cmd_f = ctl.clamp_f(d.global_transform.basis.orthonormalized().transposed() * f_w)
		d.cmd_t = ctl.attitude_torque(T.basis)
		var ang := _angle(d.global_transform.basis, T.basis)
		var rel := (d.linear_velocity - s.linear_velocity).length()
		if e.length() <= float(ns["capture_m"]) and rel <= float(ops.pkg["drone"]["approach_speed_max_m_s"]) and ang <= float(ns["align_tol_deg"]):
			ops.capture()
			say("Drone: captured and latched (%.0f mm, %.3f m/s, %.1f deg)." % [e.length() * 1000.0, rel, ang])
			if mode == Mode.RESCUE:
				_rescue_done()
			else:
				set_mode(Mode.MANUAL)
		elif lateral.length() > 0.15 or along < -0.05:
			phase = "TO GATE"                                # off the corridor: back out to the gate and try again

func _angle(a: Basis, b: Basis) -> float:
	var q := Quaternion(a.orthonormalized().transposed() * b.orthonormalized())
	return rad_to_deg(2.0 * acos(clampf(absf(q.w), 0.0, 1.0)))

# ------------------------------------------------------------------------------------------------------------------------ manipulators
func toggle_arms() -> void:
	if ops.docked:
		say("Arms stay stowed while docked (the bay covers face the suit).", false)
		return
	if holding != null and arms_deployed:
		say("Release the cartridge before stowing the arms.", false)
		return
	arms_deployed = not arms_deployed
	say("Drone arms " + ("deploying" if arms_deployed else "stowing") + ".")

func _arms(dt: float) -> void:
	arms_t = move_toward(arms_t, 1.0 if arms_deployed else 0.0, dt / 2.0)

func arms_ready() -> bool:
	return arms_deployed and arms_t >= 1.0

## Arm B's shoulder (world) and reach.
func shoulder_b() -> Vector3:
	var a: Dictionary = ops.pkg["drone"]["arms"]["B"]
	return ops.drone_frame() * WfEvaPkg.v(a["shoulder_local"])

func reach_b() -> float:
	return float(ops.pkg["drone"]["arms"]["B"]["reach_m"])

## Gripper: close on the cartridge in reach (rack slot, free-floating or seated), or release what it holds.
func toggle_gripper() -> void:
	if holding != null:
		ops.release_cartridge(holding)
		holding = null
		gripper_closed = false
		say("Gripper open: cartridge released (it keeps the drone's velocity).")
		return
	if not arms_ready():
		say("Deploy the arms first (%s)." % ops.key("evaops.arms"), false)
		return
	var c = ops.cartridge_in_reach(shoulder_b(), reach_b())
	if c == null:
		say("Nothing in reach of arm B (%.2f m from the shoulder)." % reach_b(), false)
		return
	if c is String:
		say(c, false)
		return
	holding = c
	gripper_closed = true
	ops.attach_cartridge_to_drone(c)
	say("Gripper closed on the RC-1 cartridge (%.3f kg N2 usable)." % c.tank.usable())

## Seat the held cartridge in the suit's dock channel: arm B must reach the channel, the drone must move with the suit.
func try_seat() -> bool:
	if holding == null:
		return false
	var s: WfEvaBody = ops.suit
	if ops.docked or ops.cartridge_seated != null:
		say("The dock channel is occupied.", false)
		return false
	var seat: Vector3 = dock_target().origin
	var reach := shoulder_b().distance_to(seat)
	var rel: float = (ops.drone.linear_velocity - s.linear_velocity).length()
	var limit := float(ops.pkg["cartridge"]["seat_speed_max_m_s"])
	if reach > reach_b():
		say("Channel out of arm B's reach (%.2f m > %.2f m): close in behind the astronaut." % [reach, reach_b()], false)
		return false
	if rel > limit:
		say("Too fast relative to the astronaut (%.3f m/s > %.3f): match velocity first." % [rel, limit], false)
		return false
	seat_t += ops.get_physics_process_delta_time()
	if seat_t < 2.0:
		phase = "SEATING %.0f %%" % (seat_t / 2.0 * 100.0)
		return false
	seat_t = 0.0
	ops.seat_cartridge(holding)
	holding = null
	gripper_closed = false
	say("RC-1 seated: the suit's latch bolts closed and the probe opened the dock poppet. Suit thrusters now draw cartridge gas first.")
	return true

# ---------------------------------------------------------------------------------------------------------------------------- rescue
func _rescue(dt: float) -> void:
	var d: WfEvaBody = ops.drone
	var s: WfEvaBody = ops.suit
	if ops.drone_fault_valves() > 3:
		_rescue_fail("drone propulsion fault during the rescue")
		return
	if d.usable_kg() <= 0.0:
		_rescue_fail("drone gas exhausted on the way")
		return
	var st: Dictionary = ops.world.station
	match phase:
		"TO STATION":
			if not arms_deployed:
				toggle_arms()
			var goal: Vector3 = st["rack"] + st["out"] * 0.55 + Vector3.RIGHT * 0.05
			var dist := _goto(goal, Vector3.ZERO, -st["out"], dt, rescue_speed)
			_stuck(dist, dt, "route to the station obstructed")
			if dist < 0.08 and d.linear_velocity.length() < 0.03:
				phase = "ACQUIRE"
		"ACQUIRE":
			ctl.hold_pos = true
			ctl.hold_point = st["rack"] + st["out"] * 0.55 + Vector3.RIGHT * 0.05
			ctl.step_player(Vector3.ZERO, Vector3.ZERO)
			if arms_ready():
				if int(st["cartridges"]) <= 0:
					_rescue_fail("supply station empty")
					return
				toggle_gripper()
				if holding == null:
					_rescue_fail("cartridge unavailable: " + report)
					return
				phase = "CARRY"
				_last_d = INF
		"CARRY", "TO ASTRONAUT":
			var T := dock_target()
			var back: Vector3 = -s.global_transform.basis.orthonormalized().z
			if rescue_kind == "SHARE":
				phase = ""
				mode = Mode.RESCUE
				_dock_approach_rescue(dt)
				return
			# hold station behind the suit with arm B's shoulder within reach of the channel
			var goal := T.origin + back * 0.32
			var dist := _goto(goal, s.linear_velocity, -back, dt, rescue_speed)
			_stuck(dist, dt, "approach to the astronaut obstructed")
			if dist < 0.1 and (d.linear_velocity - s.linear_velocity).length() < 0.03:
				phase = "PRESENT"
		"PRESENT":
			var T := dock_target()
			var back: Vector3 = -s.global_transform.basis.orthonormalized().z
			ctl.step_goto(T.origin + back * 0.32, s.linear_velocity, -back, 0.1, s.global_transform.basis.y)
			if try_seat():
				_rescue_done()
		_:
			if phase.begins_with("SEATING"):
				phase = "PRESENT"
			elif rescue_kind == "SHARE":
				_dock_approach_rescue(dt)

func _dock_approach_rescue(dt: float) -> void:
	if phase == "" or phase == "TO ASTRONAUT":
		phase = "TO GATE"
	_dock_approach(dt)

func _stuck(dist: float, dt: float, why: String) -> void:
	if dist < _last_d - 0.02:
		_last_d = dist
		stuck_t = 0.0
	else:
		stuck_t += dt
	if stuck_t > 45.0:
		_rescue_fail(why)

func _rescue_done() -> void:
	var dv1: float = ops.suit_dv_available()
	if dv1 > rescue_dv0 + 0.01:
		say("RESUPPLY COMPLETE: the astronaut's available delta-v rose from %.2f to %.2f m/s (%s)." % [rescue_dv0, dv1,
			"RC-1 cartridge" if rescue_kind == "FETCH" else "docked on drone gas"])
		ops.rescues += 1
	else:
		say("Transfer interface connected, but the suit's available delta-v did not rise (%.2f m/s): not a resupply." % dv1, false)
	set_mode(Mode.HOLD if not ops.docked else Mode.MANUAL)

func _rescue_fail(why: String) -> void:
	say("RESCUE FAILED: " + why + (". Tether and winch back, or abort. Training: F5 resets the scenario." if ops.training else ". Tether and winch back, or abort."), false)
	ops.rescue_failures += 1
	set_mode(Mode.HOLD)
