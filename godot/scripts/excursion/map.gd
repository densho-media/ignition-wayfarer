class_name WfExcursionMap
extends Control
## The ring map of the excursion HUD (display only): the current ring seen from aft (dorsal up), its sectors, corridor halves, doors (green open,
## red shut), the stretch of circumference walked and the trainee; outside a ring, the ring the trainee last walked or ring A.
## Training starts: an amber diamond on the rim marks each equipment point (the ECLSS bay, the DS-1 workbench).
## SYS-002 (the airflow start): ring A's compartments coloured by the air model's CO2 and, inside each bulkhead, what joins its two sides
## now (green a door, blue the ventilation duct pair, red nothing); every mark is read from the model, nothing is drawn from the walk.

var host: WfExcursion

func _process(_dt: float) -> void:
	queue_redraw()

func _draw() -> void:
	if host == null or host.actor == null:
		return
	var k := host.ring_index()
	if k < 0:
		k = 0
	var zone := "RING_" + "AB"[k]
	var c: Dictionary = host.stages["circuit"][zone]
	var ctr := size * 0.5
	var R := size.x * 0.40
	draw_rect(Rect2(Vector2.ZERO, size), Color(0, 0, 0, 0.45))
	var ph: float = c["phase_rad"]
	var to_xy := func(t: float, rr: float) -> Vector2: return ctr + Vector2(-cos(t + ph), -sin(t + ph)) * rr
	# the walked bins
	var bins: PackedByteArray = host.progress[zone]["bins"]
	for i in bins.size():
		var a0 := TAU * i / bins.size()
		var a1 := TAU * (i + 1) / bins.size()
		var col := Color(0.25, 0.85, 0.55, 0.9) if bins[i] == 1 else Color(0.35, 0.38, 0.42, 0.9)
		draw_line(ctr + Vector2(-cos(a0), -sin(a0)) * R, ctr + Vector2(-cos(a1), -sin(a1)) * R, col, 7.0)
	for q in c["segments"]:
		if q["kind"] == "corridor":
			draw_arc(ctr, R - 9.0, float(q["t_rad"][0]) + ph + PI, float(q["t_rad"][1]) + ph + PI, 12, Color(0.6, 0.85, 0.95, 0.8), 3.0)
	var half := 0.104
	for s in 3:
		var t := TAU * s / 3.0
		var a: Vector2 = to_xy.call(t - half, R - 9.0)
		var b: Vector2 = to_xy.call(t + half, R - 9.0)
		draw_line(a, b, Color(0.95, 0.75, 0.45), 9.0)
		draw_string(ThemeDB.fallback_font, to_xy.call(t, R - 34.0) - Vector2(10, -5), "%s%d" % ["AB"[k], s + 1], HORIZONTAL_ALIGNMENT_LEFT, -1, 12)
	var air_layer: bool = k == 0 and host.equipment is WfAirflow and (host.equipment as WfAirflow).ready()
	for d in c["doors"]:
		if air_layer:
			break                                                   # the air layer marks each bulkhead itself
		var rec: Dictionary = host.circ_doors[d["id"]]
		var p: Vector3 = WfLine.g(d["centre_m"]) - Vector3(c["centre_x_m"], 0, 0)
		var ang := atan2(p.y, -p.z)
		draw_circle(ctr + Vector2(-cos(ang), -sin(ang)) * (R - 9.0), 4.0, Color(0.3, 0.95, 0.4) if rec["value"] >= 0.999 else Color(0.95, 0.3, 0.25))
	if air_layer:
		_air(c, ctr, R)
	if host.equipment != null:                                     # the training's equipment points (the ECLSS bay, the workbench)
		for id in host.equipment.points:
			var pt: Dictionary = host.equipment.points[id]
			if str(pt["ring"]) != zone:
				continue
			var pp: Vector3 = host.equipment.centre(id) - Vector3(c["centre_x_m"], 0, 0)
			var a := atan2(pp.y, -pp.z)
			var at := ctr + Vector2(-cos(a), -sin(a)) * (R + 1.0)
			draw_colored_polygon(PackedVector2Array([at + Vector2(0, -7), at + Vector2(6, 0), at + Vector2(0, 7), at + Vector2(-6, 0)]), Color(1.0, 0.82, 0.30))
			draw_string(ThemeDB.fallback_font, at + Vector2(-14, -9), {"bay": "ECLSS", "bench": "bench"}.get(id, str(id)), HORIZONTAL_ALIGNMENT_LEFT, -1, 11, Color(1.0, 0.85, 0.45))
	if host.move == "WALK":
		var pa := host.actor.global_position - Vector3(c["centre_x_m"], 0, 0)
		var ang := atan2(pa.y, -pa.z)
		draw_circle(ctr + Vector2(-cos(ang), -sin(ang)) * (R - 9.0), 6.0, Color(1, 1, 1))
	if air_layer:
		return                                                      # the air layer wrote its own caption
	var pct := int(100.0 * bins.count(1) / bins.size())
	var cap := "Ring %s from aft, dorsal up · %d %% walked" % ["AB"[k], pct] if size.x >= 200.0 else "Ring %s · %d %% walked" % ["AB"[k], pct]
	draw_string(ThemeDB.fallback_font, Vector2(8, size.y - 8), cap, HORIZONTAL_ALIGNMENT_LEFT, -1, 12)

## The air model's layer (WfRingAir readout): each compartment's arc between its two bulkheads in its CO2 colour, its value, and per
## bulkhead the connection the model counts as open.
func _air(c: Dictionary, ctr: Vector2, R: float) -> void:
	var af := host.equipment as WfAirflow
	var air := af.ring
	var r := air.readout()
	var ang := {}                                                  # door id -> map angle
	for d in c["doors"]:
		var p: Vector3 = WfLine.g(d["centre_m"]) - Vector3(c["centre_x_m"], 0, 0)
		ang[d["id"]] = atan2(p.y, -p.z)
	var ends := {}                                                 # node index -> [angles of its two bulkheads]
	for e in air.edges:
		if str(e["kind"]) == "door" and ang.has(e["id"]):
			for i in [int(e["i"]), int(e["j"])]:
				if not ends.has(i):
					ends[i] = []
				ends[i].append(float(ang[e["id"]]))
	var font := ThemeDB.fallback_font
	var small := size.x < 200.0
	for i in air.N:
		if not ends.has(i) or ends[i].size() != 2:
			continue
		var a0: float = ends[i][0] + PI
		var a1: float = ends[i][1] + PI
		var span := wrapf(a1 - a0, -PI, PI)                          # the short way between its bulkheads
		var q: Dictionary = r["nodes"][i]
		var col := _co2_colour(float(q["x"]), float(air.p["co2_target"]), float(air.p["co2_max"]))
		draw_arc(ctr, R - 20.0, a0 + 0.03 * signf(span), a0 + span - 0.03 * signf(span), 10, col, 8.0)
		var mid := a0 + span * 0.5
		var at := ctr + Vector2(cos(mid), sin(mid)) * (R - (44.0 if str(q["id"]).length() <= 2 else 36.0))
		if not small or str(q["id"]).length() <= 2:
			var s := "%.2f" % (100.0 * float(q["x"]))
			draw_string(font, at - Vector2(12, -4), s, HORIZONTAL_ALIGNMENT_LEFT, -1, 10 if small else 11, col)
	for e in air.edges:
		if str(e["kind"]) != "door" or not ang.has(e["id"]):
			continue
		var imv: Dictionary = {}
		for f in air.edges:
			if str(f["kind"]) == "imv" and str(f["door"]) == str(e["id"]):
				imv = f
		var p := ctr + Vector2(cos(float(ang[e["id"]]) + PI), sin(float(ang[e["id"]]) + PI)) * (R - 20.0)
		var through_door := air.flow(e) > 0.0
		var through_duct := not imv.is_empty() and air.flow(imv) > 0.0
		var mark := Color(0.3, 0.95, 0.4) if through_door else (Color(0.45, 0.7, 1.0) if through_duct else Color(0.95, 0.25, 0.2))
		draw_circle(p, 4.5, Color(0, 0, 0, 0.8))
		draw_circle(p, 3.5, mark)
	var cap := "Air · vent %s · %d group%s" % [r["vent"], r["groups"], "" if r["groups"] == 1 else "s"]
	draw_string(font, Vector2(8, size.y - 8), cap, HORIZONTAL_ALIGNMENT_LEFT, -1, 12)
	if not small:
		draw_string(font, Vector2(8, 16), "CO2 %  (SIMULATION, PROTOTYPE)", HORIZONTAL_ALIGNMENT_LEFT, -1, 11, Color(0.8, 0.85, 0.95))

## Teal at no CO2 to yellow at the target, orange to the control limit, red beyond (the spec's WORKING bands): a ramp on the value, so
## 0.11 % and 0.23 % read apart.
static func _co2_colour(x: float, target: float, limit: float) -> Color:
	if x <= target:
		return Color(0.30, 0.75, 0.95).lerp(Color(0.98, 0.88, 0.30), clampf(x / target, 0.0, 1.0))
	if x <= limit:
		return Color(0.98, 0.88, 0.30).lerp(Color(0.98, 0.50, 0.20), (x - target) / (limit - target))
	return Color(1.0, 0.25, 0.20)
