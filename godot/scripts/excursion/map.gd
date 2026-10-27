class_name WfExcursionMap
extends Control
## The ring map of the excursion HUD (display only): the current ring seen from aft (dorsal up), its sectors, corridor halves, doors (green open,
## red shut), the stretch of circumference walked and the trainee; outside a ring, the ring the trainee last walked or ring A.

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
	for d in c["doors"]:
		var rec: Dictionary = host.circ_doors[d["id"]]
		var p: Vector3 = WfLine.g(d["centre_m"]) - Vector3(c["centre_x_m"], 0, 0)
		var ang := atan2(p.y, -p.z)
		draw_circle(ctr + Vector2(-cos(ang), -sin(ang)) * (R - 9.0), 4.0, Color(0.3, 0.95, 0.4) if rec["value"] >= 0.999 else Color(0.95, 0.3, 0.25))
	if host.move == "WALK":
		var pa := host.actor.global_position - Vector3(c["centre_x_m"], 0, 0)
		var ang := atan2(pa.y, -pa.z)
		draw_circle(ctr + Vector2(-cos(ang), -sin(ang)) * (R - 9.0), 6.0, Color(1, 1, 1))
	var pct := int(100.0 * bins.count(1) / bins.size())
	var cap := "Ring %s from aft, dorsal up · %d %% walked" % ["AB"[k], pct] if size.x >= 200.0 else "Ring %s · %d %% walked" % ["AB"[k], pct]
	draw_string(ThemeDB.fallback_font, Vector2(8, size.y - 8), cap, HORIZONTAL_ALIGNMENT_LEFT, -1, 12)
