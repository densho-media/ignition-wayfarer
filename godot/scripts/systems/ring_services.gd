class_name WfRingServices
extends RefCounted
## SYS-003 ring services (src/wayfarer/ring_services.py): the runtime copy of the engineering state. Both rings' cabin heat, water vapour
## and CO2, the cooling chain (the cabin heat exchanger's fan and coil, two coolant pumps, the heat pump into the 320 K cold loop), the
## buses, generators, battery converters, main battery and survival packs, and the parts the machines are made of. The step is the module's:
## the switchboard settled at the step's start, then one classical Runge-Kutta step of the continuous state and its ledgers, in the same
## order of operations. It must reproduce the packaged proof within the packaged tolerance (verify()) before anyone shows its state. Godot
## computes no parameter and knows nothing of games, scenarios, input or scores. The state is a Dictionary shaped as the module's `st`, so
## a scenario mirrors the module's scenario code line for line. SIMULATION: PROTOTYPE values travel labelled.

const RINGS := ["A", "B"]
const BUSES := ["A", "B"]
const Y_RING := 17
const ACC_RING := ["w_gen", "w_cond", "c_gen", "c_rem", "q_crew", "q_elec", "q_rem", "q_lat", "w_hp", "rejected", "t_hot", "t_rh", "t_co2", "t_wet"]
const ACC_POWER := ["E_batt", "E_gen", "E_pack.A", "E_pack.B", "E_served", "E_unserved"]

var doc := {}
var p := {}
var k := {}                       # the module's constants
var slots := {}                   # slot (CO2.FAN ...) -> LRU family
var conv_slots := {}
var lru := {}
var equipment: Array = []
var verified := false
var errors: Array = []
var R := 0.0
var R_V := 0.0
var M_CO2 := 0.0
var H_FG := 0.0
var CP_AIR := 0.0
var CP_W := 0.0
var M_AIR := 0.0
var ITER := 4

static func load_package(path := "res://generated/wf_ring_services.json") -> WfRingServices:
	if not FileAccess.file_exists(path):
		return null
	var a := WfRingServices.new()
	a.doc = JSON.parse_string(FileAccess.get_file_as_string(path))
	a.p = a.doc["params"]
	a.k = a.doc["constants"]
	a.R = float(a.k["R"]); a.R_V = float(a.k["R_V"]); a.M_CO2 = float(a.k["M_CO2"]); a.H_FG = float(a.k["H_FG"])
	a.CP_AIR = float(a.k["CP_AIR"]); a.CP_W = float(a.k["CP_W"]); a.M_AIR = float(a.k["M_AIR"])
	a.ITER = int(a.doc["iterations"])
	a.slots = a.doc["slots"]
	a.conv_slots = a.doc["converter_slots"]
	a.lru = a.doc["lru"]
	a.equipment = a.p["equipment"]
	var t0 := Time.get_ticks_usec()
	a.errors = a.verify()
	a.doc["verify_ms"] = (Time.get_ticks_usec() - t0) / 1000.0
	a.verified = a.errors.is_empty()
	return a

# ---- thermodynamics ------------------------------------------------------------------------------------------------------------------

func p_sat(T: float) -> float:
	var t := T - 273.15
	return 610.94 * exp(17.625 * t / (t + 243.04))

func rho_sat(T: float) -> float:
	return p_sat(T) / (R_V * T)

func rho_air(T: float) -> float:
	return float(p["P_Pa"]) * M_AIR / (R * T)

func rh(T: float, m_w: float) -> float:
	return m_w / float(p["V_m3"]) * R_V * T / p_sat(T)

func x_co2(T: float, m_c: float) -> float:
	return m_c / M_CO2 / (float(p["P_Pa"]) * float(p["V_m3"]) / (R * T))

func m_w_at(T: float, rh_: float) -> float:
	return rh_ * p_sat(T) / (R_V * T) * float(p["V_m3"])

func m_c_at(T: float, x: float) -> float:
	return x * float(p["P_Pa"]) * float(p["V_m3"]) / (R * T) * M_CO2

func dew_point(T: float, m_w: float) -> float:
	var e := maxf(m_w / float(p["V_m3"]) * R_V * T, 1e-6)
	var lg := log(e / 610.94)
	return 273.15 + 243.04 * lg / (17.625 - lg)

static func eps_counterflow(ntu: float, cr: float) -> float:
	if cr > 0.999999:
		return ntu / (1.0 + ntu)
	var e := exp(-ntu * (1.0 - cr))
	return (1.0 - e) / (1.0 - cr * e)

func coil(T: float, m_w: float, fan: bool, pumps: int, hp_on: bool, T_s0 = null) -> Dictionary:
	if not fan or pumps <= 0 or not hp_on:
		return {"Q_s": 0.0, "cond": 0.0, "Q_hp": 0.0, "W_hp": 0.0, "T_s": T, "T_coil": T, "f": 0.0}
	var f := minf(maxf(0.5 + (T - float(p["T_set"])) / float(p["band"]), float(p["f_min"])), 1.0)
	var Qa := f * float(p["Q_air"])
	var Ca := rho_air(T) * CP_AIR * Qa
	var Cc := pumps * float(p["pump"]) * CP_W
	var cmin := minf(Ca, Cc)
	var cmax := maxf(Ca, Cc)
	var eps := eps_counterflow(float(p["UA"]) / cmin, cmin / cmax)
	var rho_v := m_w / float(p["V_m3"])
	var ts0: float = float(p["T_s"]) if T_s0 == null else float(T_s0)
	var T_s := ts0
	var cond := 0.0
	var Q_s := 0.0
	var T_coil := T_s
	var hp_max := float(p["hp_max"])
	for _i in ITER:
		Q_s = eps * cmin * maxf(T - T_s, 0.0)
		var latent := H_FG * cond
		if Q_s + latent > hp_max:
			T_s = maxf(ts0, T - maxf(hp_max - latent, 0.0) / (eps * cmin))
			Q_s = eps * cmin * maxf(T - T_s, 0.0)
		T_coil = T_s + (Q_s + latent) / (2.0 * Cc)
		cond = Qa * eps * maxf(rho_v - rho_sat(T_coil), 0.0)
	var Q_hp := Q_s + H_FG * cond
	var cop := float(p["eta_hp"]) * T_s / (float(p["T_rad"]) - T_s)
	return {"Q_s": Q_s, "cond": cond, "Q_hp": Q_hp, "W_hp": Q_hp / cop, "T_s": T_s, "T_coil": T_coil, "f": f}

# ---- state ---------------------------------------------------------------------------------------------------------------------------

func acc_keys() -> Array:
	var out := []
	for r in RINGS:
		for a in ACC_RING:
			out.append("%s.%s" % [r, a])
	out.append_array(ACC_POWER)
	return out

func start(occupants = null, fusion := true) -> Dictionary:
	var occ := {"A": 6, "B": 0}
	if occupants != null:
		occ = {"A": int(occupants["A"]), "B": int(occupants["B"])}
	var ring := {}
	for r in RINGS:
		var T := float(p["T0"])
		var x := 0.0004
		if int(occ[r]) != 0:
			x = int(occ[r]) * float(p["g_c"]) / float(p["k_m3_s"]) * R * T / (float(p["P_Pa"]) * M_CO2)
		var on := {}
		var iso := {}
		for e in equipment:
			on[str(e["id"])] = true
			iso[str(e["id"])] = false
		ring[r] = {"T": T, "m_w": m_w_at(T, float(p["rh0"])), "m_c": m_c_at(T, x), "economy": false, "on": on, "isolated": iso}
	var parts := {}
	for r in RINGS:
		for slot in slots:
			parts["%s.%s" % [r, slot]] = {"lru": str(slots[slot]), "at": "%s.%s" % [r, slot], "ok": true}
	for slot in conv_slots:
		parts[str(slot)] = {"lru": str(conv_slots[slot]), "at": str(slot), "ok": true}
	var st := {"t_s": 0.0, "ring": ring, "occ": occ, "parts": parts, "fusion": fusion, "gen": {"A": true, "B": true}, "tie": false,
		"breaker": {"A": true, "B": true}, "conv_on": {"A": true, "B": true}, "E": float(p["battery_Wh"]) * 3600.0,
		"pack": {"A": float(p["pack_Wh"]) * 3600.0, "B": float(p["pack_Wh"]) * 3600.0}, "log": [], "trips": []}
	st["E0"] = st["E"]
	st["pack0"] = (st["pack"] as Dictionary).duplicate()
	st["pulse_J"] = 0.0
	var a := {}
	for key in acc_keys():
		a[key] = 0.0
	st["acc"] = a
	var init := {}
	for r in RINGS:
		init[r] = {"T": ring[r]["T"], "m_w": ring[r]["m_w"], "m_c": ring[r]["m_c"]}
	st["init"] = init
	return st

func slots_all() -> Dictionary:
	var out := {}
	for r in RINGS:
		for s in slots:
			out["%s.%s" % [r, s]] = str(slots[s])
	for s in conv_slots:
		out[str(s)] = str(conv_slots[s])
	return out

func slot_ok(st: Dictionary, slot: String) -> bool:
	for part in st["parts"].values():
		if str(part["at"]) == slot:
			var want = null
			if slot.begins_with("A.") or slot.begins_with("B."):
				want = slots.get(slot.split(".", true, 1)[1])
			else:
				want = conv_slots.get(slot)
			return bool(part["ok"]) and want != null and str(part["lru"]) == str(want)
	return false

func move_part(st: Dictionary, part_id: String, to: String) -> String:
	if not st["parts"].has(part_id):
		return "no such part"
	var part: Dictionary = st["parts"][part_id]
	var sa := slots_all()
	if sa.has(to):
		var fam := str(sa[to])
		if fam != str(part["lru"]):
			return "%s does not fit %s: %s against %s" % [part_id, to, lru[part["lru"]]["title"], lru[fam]["title"]]
		for q in st["parts"].values():
			if str(q["at"]) == to:
				return "%s already holds a part" % to
	part["at"] = to
	st["log"].append([st["t_s"], "part", part_id, to])
	return ""

func fail_part(st: Dictionary, part_id: String) -> void:
	st["parts"][part_id]["ok"] = false
	st["log"].append([st["t_s"], "fail", part_id, ""])

func set_on(st: Dictionary, ring: String, e: String, on: bool) -> void:
	st["ring"][ring]["on"][e] = on
	st["log"].append([st["t_s"], "switch", "%s.%s" % [ring, e], on])

func set_isolated(st: Dictionary, ring: String, e: String, iso: bool) -> void:
	st["ring"][ring]["isolated"][e] = iso
	st["log"].append([st["t_s"], "isolate", "%s.%s" % [ring, e], iso])

func set_occupants(st: Dictionary, occ: Dictionary) -> void:
	st["occ"] = occ.duplicate()
	st["log"].append([st["t_s"], "occupants", "", occ.duplicate()])

func set_tie(st: Dictionary, closed: bool) -> void:
	st["tie"] = closed
	st["log"].append([st["t_s"], "tie", "", closed])

func reset_breaker(st: Dictionary, bus: String) -> void:
	st["breaker"][bus] = true
	st["log"].append([st["t_s"], "breaker", bus, true])

func set_converter(st: Dictionary, bus: String, on: bool) -> void:
	st["conv_on"][bus] = on
	st["log"].append([st["t_s"], "converter", bus, on])

func set_economy(st: Dictionary, ring: String, on: bool) -> void:
	st["ring"][ring]["economy"] = on
	st["log"].append([st["t_s"], "economy", ring, on])

func supply(st: Dictionary, ring: String) -> float:
	return float(p["T_s_economy"]) if bool(st["ring"][ring]["economy"]) else float(p["T_s"])

func charge_pulse(st: Dictionary) -> bool:
	var need := float(p["pulse_Wh"]) * 3600.0
	if float(st["E"]) < need:
		return false
	st["E"] = float(st["E"]) - need
	st["pulse_J"] = float(st["pulse_J"]) + need
	st["log"].append([st["t_s"], "pulse", "", need])
	return true

func set_fusion(st: Dictionary, on: bool) -> void:
	st["fusion"] = on
	st["log"].append([st["t_s"], "fusion", "", on])

# ---- the switchboard -----------------------------------------------------------------------------------------------------------------

func eq(i: String) -> Dictionary:
	for e in equipment:
		if str(e["id"]) == i:
			return e
	return {}

func equipment_ready(st: Dictionary, ring: String, e: Dictionary) -> bool:
	var rr: Dictionary = st["ring"][ring]
	if not bool(rr["on"][e["id"]]) or bool(rr["isolated"][e["id"]]):
		return false
	for s in e["slots"]:
		if not slot_ok(st, "%s.%s" % [ring, s]):
			return false
	return true

func sources(st: Dictionary) -> Dictionary:
	var out := {}
	for b in BUSES:
		var g := float(p["gen_W"]) if bool(st["fusion"]) and bool(st["gen"][b]) else 0.0
		var c := float(p["conv_W"]) if bool(st["conv_on"][b]) and slot_ok(st, "BC-" + b) and float(st["E"]) > 0.0 else 0.0
		out[b] = {"gen": g, "conv": c}
	return out

func demand(st: Dictionary, coils: Dictionary) -> Dictionary:
	var d := {}
	for b in BUSES:
		d[b] = float(p["ship_W"][b])
	for r in RINGS:
		for e in equipment:
			if equipment_ready(st, r, e):
				d[e["bus"]] = float(d[e["bus"]]) + (float(coils[r]["W_hp"]) if str(e["id"]) == "HP" else float(e["W"]))
	return d

func _pumps_ready(st: Dictionary, r: String) -> int:
	var n := 0
	for e in equipment:
		if str(e["id"]) in ["P1", "P2"] and equipment_ready(st, r, e):
			n += 1
	return n

func settle(st: Dictionary) -> Dictionary:
	var coils := {}
	for r in RINGS:
		var rr: Dictionary = st["ring"][r]
		coils[r] = coil(float(rr["T"]), float(rr["m_w"]), equipment_ready(st, r, eq("CHX")), _pumps_ready(st, r), equipment_ready(st, r, eq("HP")), supply(st, r))
	var src := sources(st)
	var dem := demand(st, coils)
	var live := {}
	var groups := [["A", "B"]] if bool(st["tie"]) else [["A"], ["B"]]
	for g in groups:
		var cap := 0.0
		var need := 0.0
		var closed := []
		for b in g:
			if bool(st["breaker"][b]):
				cap += float(src[b]["gen"]) + float(src[b]["conv"])
				closed.append(b)
			need += float(dem[b])
		if closed.is_empty() or cap <= 0.0:
			for b in g:
				live[b] = false
			continue
		if need > cap + 1e-9:
			for b in closed:
				st["breaker"][b] = false
				st["trips"].append([st["t_s"], b, need, cap])
				st["log"].append([st["t_s"], "trip", b, [need, cap]])
			for b in g:
				live[b] = false
			continue
		for b in g:
			live[b] = bool(st["breaker"][b]) and (bool(st["tie"]) or float(src[b]["gen"]) + float(src[b]["conv"]) > 0.0)
		if bool(st["tie"]):
			for b in g:
				live[b] = true
	var run := {}
	for r in RINGS:
		run[r] = {}
		for e in equipment:
			var s = null
			if not equipment_ready(st, r, e):
				s = null
			elif bool(live[e["bus"]]):
				s = "BUS"
			elif bool(e["survival"]) and float(st["pack"][r]) > 0.0:
				s = "PACK"
			else:
				s = "DARK"
			run[r][e["id"]] = s
	var gen_share := {}
	for g in groups:
		var gsum := 0.0
		for b in g:
			if bool(live.get(b, false)):
				gsum += float(src[b]["gen"])
		gen_share["".join(g)] = gsum
	return {"live": live, "run": run, "src": src, "groups": groups, "gen": gen_share}

# ---- the step ------------------------------------------------------------------------------------------------------------------------

static func _powered(run: Dictionary, i: String) -> bool:
	var s = run[i]
	return s == "BUS" or s == "PACK"

func derivs(st: Dictionary, plan: Dictionary, y: PackedFloat64Array) -> PackedFloat64Array:
	var dy := PackedFloat64Array()
	dy.resize(y.size())
	dy.fill(0.0)
	var bus_load := {}
	for b in BUSES:
		bus_load[b] = float(p["ship_W"][b]) if bool(plan["live"][b]) else 0.0
	var pack_load := {"A": 0.0, "B": 0.0}
	var unserved := 0.0
	var all_live := true
	for b in BUSES:
		all_live = all_live and bool(plan["live"][b])
	if not all_live:
		for b in BUSES:
			if not bool(plan["live"][b]):
				unserved += float(p["ship_W"][b])
	var C := float(p["C"])
	var V := float(p["V_m3"])
	for kr in RINGS.size():
		var r: String = RINGS[kr]
		var o := kr * Y_RING
		var T := y[o]
		var m_w := y[o + 1]
		var m_c := y[o + 2]
		var run: Dictionary = plan["run"][r]
		var pumps := (1 if _powered(run, "P1") else 0) + (1 if _powered(run, "P2") else 0)
		var c := coil(T, m_w, _powered(run, "CHX"), pumps, _powered(run, "HP"), supply(st, r))
		var elec := 0.0
		for e in equipment:
			var s = run[e["id"]]
			var w: float = float(c["W_hp"]) if str(e["id"]) == "HP" else float(e["W"])
			if s == "BUS":
				bus_load[e["bus"]] = float(bus_load[e["bus"]]) + w
				if str(e["id"]) != "HP":
					elec += w
			elif s == "PACK":
				pack_load[r] = float(pack_load[r]) + w
				if str(e["id"]) != "HP":
					elec += w
			elif s == "DARK":
				unserved += w
		var n := int(st["occ"][r])
		var qc := n * float(p["q_sens"])
		var k_rem := float(p["k_m3_s"]) if _powered(run, "CO2") else 0.0
		var hp_on := _powered(run, "HP")
		dy[o] = (qc + elec - float(c["Q_s"])) / C
		dy[o + 1] = n * float(p["g_w"]) - float(c["cond"])
		dy[o + 2] = n * float(p["g_c"]) - k_rem * m_c / V
		dy[o + 3] = n * float(p["g_w"])
		dy[o + 4] = float(c["cond"])
		dy[o + 5] = n * float(p["g_c"])
		dy[o + 6] = k_rem * m_c / V
		dy[o + 7] = qc
		dy[o + 8] = elec
		dy[o + 9] = float(c["Q_s"])
		dy[o + 10] = H_FG * float(c["cond"])
		dy[o + 11] = float(c["W_hp"]) if hp_on else 0.0
		dy[o + 12] = float(c["Q_hp"]) + (float(c["W_hp"]) if hp_on else 0.0)
		var x := x_co2(T, m_c)
		var h := rh(T, m_w)
		dy[o + 13] = 1.0 if T > float(p["T_max"]) else 0.0
		dy[o + 14] = 1.0 if h > float(p["rh_max"]) else 0.0
		dy[o + 15] = 1.0 if x > float(p["co2_max"]) else 0.0
		dy[o + 16] = 1.0 if h > float(p["rh_limit"]) else 0.0
	var E_gen := 0.0
	var E_batt := 0.0
	for g in plan["groups"]:
		var ok := true
		for b in g:
			ok = ok and bool(plan["live"][b])
		if not ok:
			continue
		var load := 0.0
		for b in g:
			load += float(bus_load[b])
		var gen := minf(load, float(plan["gen"]["".join(g)]))
		E_gen += gen
		E_batt += load - gen
	var o2 := Y_RING * RINGS.size()
	dy[o2] = -E_batt
	dy[o2 + 1] = -float(pack_load["A"])
	dy[o2 + 2] = -float(pack_load["B"])
	dy[o2 + 3] = E_batt
	dy[o2 + 4] = E_gen
	dy[o2 + 5] = float(pack_load["A"])
	dy[o2 + 6] = float(pack_load["B"])
	dy[o2 + 7] = E_gen + E_batt + float(pack_load["A"]) + float(pack_load["B"])
	dy[o2 + 8] = unserved
	return dy

func pack_y(st: Dictionary) -> PackedFloat64Array:
	var y := PackedFloat64Array()
	for r in RINGS:
		var rr: Dictionary = st["ring"][r]
		y.append(float(rr["T"])); y.append(float(rr["m_w"])); y.append(float(rr["m_c"]))
		for a in ACC_RING:
			y.append(float(st["acc"]["%s.%s" % [r, a]]))
	y.append(float(st["E"])); y.append(float(st["pack"]["A"])); y.append(float(st["pack"]["B"]))
	for a in ACC_POWER:
		y.append(float(st["acc"][a]))
	return y

func unpack_y(st: Dictionary, y: PackedFloat64Array) -> void:
	for kr in RINGS.size():
		var r: String = RINGS[kr]
		var o := kr * Y_RING
		var rr: Dictionary = st["ring"][r]
		rr["T"] = y[o]; rr["m_w"] = y[o + 1]; rr["m_c"] = y[o + 2]
		for j in ACC_RING.size():
			st["acc"]["%s.%s" % [r, ACC_RING[j]]] = y[o + 3 + j]
	var o2 := Y_RING * RINGS.size()
	st["E"] = y[o2]; st["pack"]["A"] = y[o2 + 1]; st["pack"]["B"] = y[o2 + 2]
	for j in ACC_POWER.size():
		st["acc"][ACC_POWER[j]] = y[o2 + 3 + j]

static func _axpy(y: PackedFloat64Array, a: float, k: PackedFloat64Array) -> PackedFloat64Array:
	var out := PackedFloat64Array()
	out.resize(y.size())
	for i in y.size():
		out[i] = y[i] + a * k[i]
	return out

func step(st: Dictionary, dt: float) -> void:
	var plan := settle(st)
	var y := pack_y(st)
	var k1 := derivs(st, plan, y)
	var k2 := derivs(st, plan, _axpy(y, 0.5 * dt, k1))
	var k3 := derivs(st, plan, _axpy(y, 0.5 * dt, k2))
	var k4 := derivs(st, plan, _axpy(y, dt, k3))
	var out := PackedFloat64Array()
	out.resize(y.size())
	for i in y.size():
		out[i] = y[i] + dt / 6.0 * (k1[i] + 2.0 * k2[i] + 2.0 * k3[i] + k4[i])
	var o := Y_RING * RINGS.size()
	for j in 3:
		if out[o + j] < 0.0:
			var short := -out[o + j]
			out[o + j] = 0.0
			var idx := o + 3 + (0 if j == 0 else 1 + j)
			out[idx] = out[idx] - short
			out[o + 7] = out[o + 7] - short
			out[o + 8] = out[o + 8] + short
	unpack_y(st, out)
	st["t_s"] = float(st["t_s"]) + dt
	st["plan"] = plan

# ---- ledgers and readouts ------------------------------------------------------------------------------------------------------------

func ledgers(st: Dictionary) -> Dictionary:
	var out := {}
	var a: Dictionary = st["acc"]
	var C := float(p["C"])
	for r in RINGS:
		var rr: Dictionary = st["ring"][r]
		var i0: Dictionary = st["init"][r]
		out["%s.water_kg" % r] = (float(rr["m_w"]) + float(a[r + ".w_cond"])) - (float(i0["m_w"]) + float(a[r + ".w_gen"]))
		out["%s.co2_kg" % r] = (float(rr["m_c"]) + float(a[r + ".c_rem"])) - (float(i0["m_c"]) + float(a[r + ".c_gen"]))
		out["%s.heat_J" % r] = (C * (float(rr["T"]) - float(i0["T"])) + float(a[r + ".q_rem"])) - (float(a[r + ".q_crew"]) + float(a[r + ".q_elec"]))
		out["%s.coolant_J" % r] = float(a[r + ".rejected"]) - (float(a[r + ".q_rem"]) + float(a[r + ".q_lat"]) + float(a[r + ".w_hp"]))
	out["battery_J"] = (float(st["E0"]) - float(st["E"])) - float(a["E_batt"]) - float(st["pulse_J"])
	out["packs_J"] = ((float(st["pack0"]["A"]) - float(st["pack"]["A"])) + (float(st["pack0"]["B"]) - float(st["pack"]["B"]))) - (float(a["E_pack.A"]) + float(a["E_pack.B"]))
	out["served_J"] = float(a["E_served"]) - (float(a["E_gen"]) + float(a["E_batt"]) + float(a["E_pack.A"]) + float(a["E_pack.B"]))
	var ok := true
	for q in st["parts"].values():
		ok = ok and str(q["at"]) != ""
	out["parts"] = 0 if ok else 1
	return out

func coil_now(st: Dictionary, r: String) -> Dictionary:
	var plan: Dictionary = st["plan"] if st.has("plan") else settle(st.duplicate(true))
	var run: Dictionary = plan["run"][r]
	var pumps := (1 if _powered(run, "P1") else 0) + (1 if _powered(run, "P2") else 0)
	var rr: Dictionary = st["ring"][r]
	return coil(float(rr["T"]), float(rr["m_w"]), _powered(run, "CHX"), pumps, _powered(run, "HP"), supply(st, r))

## Each bus's demand now if every ready machine runs (the overview's number).
func demand_now(st: Dictionary) -> Dictionary:
	var coils := {}
	for r in RINGS:
		var rr: Dictionary = st["ring"][r]
		coils[r] = coil(float(rr["T"]), float(rr["m_w"]), equipment_ready(st, r, eq("CHX")), _pumps_ready(st, r), equipment_ready(st, r, eq("HP")), supply(st, r))
	return demand(st, coils)

# ---- proof -----------------------------------------------------------------------------------------------------------------------------

func apply(st: Dictionary, ev: Array) -> void:
	var kd := str(ev[1])
	match kd:
		"fail": fail_part(st, str(ev[2]))
		"fusion": set_fusion(st, bool(ev[2]))
		"shed":
			for e in ["GARDEN", "GALLEY", "LAB"]:
				set_on(st, str(ev[2]), e, false)
		"tie": set_tie(st, bool(ev[2]))
		"reset": reset_breaker(st, str(ev[2]))
		"move": move_part(st, str(ev[2]), str(ev[3]))
		"occupants": set_occupants(st, ev[2])
		"switch": set_on(st, str(ev[2]), str(ev[3]), bool(ev[4]))

func snapshot(st: Dictionary) -> Dictionary:
	var T := {}
	var mw := {}
	var mc := {}
	for r in RINGS:
		T[r] = st["ring"][r]["T"]; mw[r] = st["ring"][r]["m_w"]; mc[r] = st["ring"][r]["m_c"]
	return {"t_s": st["t_s"], "T": T, "m_w": mw, "m_c": mc, "E": st["E"], "pack": (st["pack"] as Dictionary).duplicate(),
		"acc": (st["acc"] as Dictionary).duplicate(), "breaker": (st["breaker"] as Dictionary).duplicate()}

static func close_enough(a: float, b: float, tol: Dictionary) -> bool:
	return absf(a - b) <= float(tol["abs"]) + float(tol["rel"]) * maxf(absf(a), absf(b))

func verify() -> Array:
	var pr: Dictionary = doc["proof"]
	var tol: Dictionary = doc["tolerance"]
	var evs: Array = pr["events"].duplicate()
	evs.sort_custom(func(a, b): return float(a[0]) < float(b[0]))
	var st := start()
	var want: Array = pr["checkpoints"]
	var got := [snapshot(st)]
	var j := 0
	var dt := float(pr["dt_s"])
	var every := float(pr["every_s"])
	while float(st["t_s"]) < float(pr["end_s"]) - 1e-9:
		while j < evs.size() and float(evs[j][0]) <= float(st["t_s"]) + 1e-9:
			apply(st, evs[j])
			j += 1
		step(st, dt)
		var q := float(st["t_s"]) / every
		if absf(q - roundf(q)) < 1e-9:
			got.append(snapshot(st))
	if got.size() != want.size():
		return ["proof: %d checkpoints, the package has %d" % [got.size(), want.size()]]
	var bad := []
	for i in got.size():
		var g: Dictionary = got[i]
		var w: Dictionary = want[i]
		var pairs := [["E", float(g["E"]), float(w["E"])]]
		for r in RINGS:
			pairs.append(["T." + r, float(g["T"][r]), float(w["T"][r])])
			pairs.append(["m_w." + r, float(g["m_w"][r]), float(w["m_w"][r])])
			pairs.append(["m_c." + r, float(g["m_c"][r]), float(w["m_c"][r])])
			pairs.append(["pack." + r, float(g["pack"][r]), float(w["pack"][r])])
			if bool(g["breaker"][r]) != bool(w["breaker"][r]):
				bad.append("proof t %.0f: breaker %s %s, the module %s" % [float(g["t_s"]), r, g["breaker"][r], w["breaker"][r]])
		for key in w["acc"]:
			pairs.append(["acc." + str(key), float(g["acc"][key]), float(w["acc"][key])])
		for pq in pairs:
			if not close_enough(float(pq[1]), float(pq[2]), tol):
				bad.append("proof t %.0f: %s %s, the module %s" % [float(g["t_s"]), pq[0], float(pq[1]), float(pq[2])])
		if bad.size() > 6:
			break
	return bad
