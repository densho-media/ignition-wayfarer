class_name WfM6Radiator
extends WfM6Sim
## M6 chapter: the three fixed radiator blades, their coolant loops and the damage / isolation states. N steps the BASELINE operating
## sequence (fixed structure, coolant flow, heat admitted, high-power rejection, post-shutdown cooldown; 07!A39, 11); X damages the
## next cells in the PROTOTYPE fault order (radiator_health: global index x stride mod 480, scattered over all blades); V isolates the
## damaged cells, or requalifies the isolated ones; K isolates or restores blade 1's coolant loop (PROTOTYPE one feed / return pair per
## blade). The in-service share is a CAD readback of the cell planforms measured here; the physical blade area is unchanged, and the
## heat rejection, flow rate, drive waste heat and margin stay UNKNOWN (no number is computed for them).

const STEP_COLORS := [Color(0.42, 0.52, 0.68), Color(0.30, 0.85, 1.00), Color(1.00, 0.72, 0.30), Color(1.00, 0.38, 0.14), Color(0.85, 0.58, 0.40)]
const STEP_ROLES := ["subject", "flow", "flow", "hot", "flow"]
const DAMAGED := Color(1.0, 0.12, 0.12)
const ISOLATED := Color(0.30, 0.30, 0.36)
const PER_PRESS := 6

var step_i := 1                     # COOLANT_FLOW: COAST circulates (11!E2)
var cells: Array = []               # [{id, blade, j, kk, rank, zone, area}]
var state := {}                     # id -> "HEALTHY" | "DAMAGED" | "ISOLATED"
var order: Array = []               # ids in fault-rank order
var next_fault := 0
var loop_out := false               # blade 1 loop isolated
var total_area := 0.0

## Cells take the blade of the nearest root boom in azimuth (the blades link the same cell meshes); planform areas are measured.
func attach(by_id: Dictionary) -> void:
	var root_az := {}
	for b in m.roots:
		var c := Vector3.ZERO
		for id in m.roots[b]:
			c += _centre(by_id[id])
		root_az[int(b)] = atan2(c.z, c.y)
	var nx := int(m.grid.longitudinal)
	var ny := int(m.grid.transverse)
	var n: int = m.cells.size()
	for row in m.cells:
		var item: MeshInstance3D = by_id[row[0]]
		var c := _centre(item)
		var az := atan2(c.z, c.y)
		var blade := 0
		var best := INF
		for b in root_az:
			var d := absf(angle_difference(az, root_az[b]))
			if d < best:
				best = d
				blade = b
		var g: int = blade * nx * ny + int(row[1]) * ny + int(row[2])
		var box: AABB = item.get_aabb()
		var s: Vector3 = item.global_transform.basis.get_scale()
		var dims := [box.size.x * s.x, box.size.y * s.y, box.size.z * s.z]
		dims.sort()
		var area: float = dims[1] * dims[2]
		cells.append({"id": row[0], "blade": blade, "j": row[1], "kk": row[2], "rank": (g * int(m.fault.stride)) % n, "zone": row[3], "area": area})
		state[row[0]] = "HEALTHY"
		total_area += area
	cells.sort_custom(func(a, b): return a.rank < b.rank)
	order = cells.map(func(c): return c.id)

func _centre(item: MeshInstance3D) -> Vector3:
	return item.global_transform * item.get_aabb().get_center()

func step_id() -> String:
	return m.steps[step_i].id

func next_state() -> void:
	step_i = (step_i + 1) % m.steps.size()
	note = "%s (%s, %s)" % [step_id().replace("_", " "), m.steps[step_i].status, m.steps[step_i].source]
	host.refresh()

func event() -> void:
	var hit := 0
	while hit < PER_PRESS and next_fault < order.size():
		var id: String = order[next_fault]
		next_fault += 1
		if state[id] == "HEALTHY" and not (loop_out and blade_of(id) == 1):
			state[id] = "DAMAGED"
			hit += 1
	note = "%d cells damaged (PROTOTYPE scattered order, stride %d); no damage distribution is sourced (OD-010)" % [hit, int(m.fault.stride)]
	host.refresh()

func response() -> void:
	var damaged := count("DAMAGED")
	if damaged > 0:
		for id in state:
			if state[id] == "DAMAGED":
				state[id] = "ISOLATED"
		note = "%d damaged cells isolated: their flow is valved off, the rest of the loop keeps circulating" % damaged
	else:
		var n := count("ISOLATED")
		for id in state:
			if state[id] == "ISOLATED":
				state[id] = "HEALTHY"
		note = "%d isolated cells resurfaced and requalified (repair method and time OPEN)" % n
	host.refresh()

func loop() -> void:
	loop_out = not loop_out
	note = "Blade 1 coolant loop %s (PROTOTYPE topology)" % ("isolated: the whole blade is out of service" if loop_out else "restored")
	host.refresh()

func blade_of(id: String) -> int:
	for c in cells:
		if c.id == id:
			return c.blade
	return -1

func count(s: String) -> int:
	return state.values().filter(func(v): return v == s).size()

func in_service(c: Dictionary) -> bool:
	return state[c.id] == "HEALTHY" and not (loop_out and c.blade == 1)

func service_share() -> float:
	var a := 0.0
	for c in cells:
		if in_service(c):
			a += c.area
	return a / maxf(1e-6, total_area)

func tints() -> Dictionary:
	var out := {}
	var flow := step_i in [1, 2, 3, 4]
	for c in cells:
		var s: String = state[c.id]
		if loop_out and c.blade == 1:
			out[c.id] = [ISOLATED, "dim"]
		elif s == "DAMAGED":
			out[c.id] = [DAMAGED, "hot"]
		elif s == "ISOLATED":
			out[c.id] = [ISOLATED, "dim"]
		else:
			out[c.id] = [STEP_COLORS[step_i], STEP_ROLES[step_i]]
	for b in m.loops:
		for id in m.loops[b]:
			if loop_out and int(b) == 1:
				out[id] = [DAMAGED, "dim"]
			else:
				out[id] = [Color(0.30, 0.85, 1.00), "flow" if flow else "subject"]
	return out

func panel_lines() -> Array[String]:
	var s: Dictionary = m.steps[step_i]
	var out: Array[String] = []
	out.append("[b]RADIATORS[/b]   step %d/5 %s   %s" % [step_i + 1, step_id().replace("_", " "), host.badge_bb(s.status, "operating sequence (%s)" % s.source)])
	out.append("Coolant in COAST: %s — %s. Flow rate %s." % [m.fluid.COAST.fluid_status, m.fluid.COAST.duty, "UNKNOWN"])
	var share := service_share()
	out.append("Cells: %d healthy · [color=#e24b4a]%d damaged[/color] · %d isolated%s  (of %d, PROTOTYPE grid)" % [count("HEALTHY"), count("DAMAGED"), count("ISOLATED"),
		" · blade 1 loop OUT" if loop_out else "", cells.size()])
	out.append("In service: [b]%.1f %%[/b] of the cell planform (CAD readback) → about %s m2 of the %s m2 as-built net one-face (%s)" % [share * 100.0,
		_thousands(share * float(m.area.as_built_net_m2)), _thousands(float(m.area.as_built_net_m2)), m.area.net_status])
	out.append("Hot face %.0f K, emissivity %.2f (WORKING) · the physical blade area never changes; damage and isolation are display states." % [float(m.hot_K), float(m.emissivity)])
	out.append(unknown("heat rejection margin, drive waste heat, heat debt, loop flow and temperatures (owner science track, 15!A227)"))
	if note != "":
		out.append("[color=#888780]%s[/color]" % note)
	return out

static func _thousands(v: float) -> String:
	var s := str(int(roundf(v)))
	var out := ""
	while s.length() > 3:
		out = "," + s.right(3) + out
		s = s.left(s.length() - 3)
	return s + out

func controls() -> Array:
	return [["holo.state", "operating step"], ["holo.event", "damage cells"], ["holo.response", "isolate / requalify"], ["holo.loop", "blade 1 loop"]]
