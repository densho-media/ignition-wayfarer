class_name WfEvaHud
extends CanvasLayer
## EVA Operations HUD (display only): both inventories side by side in physical units, the controlled body's state, warnings, the
## scenario card and the keys that work now. It reads the scene and never changes it.

var ops
var top: Label
var left: Label
var right: Label
var mid: RichTextLabel                     # rich text: the keys show as coloured chips (WfKeyText)
var keys: RichTextLabel
var card: RichTextLabel
var font_size := 15

func setup(o) -> void:
	ops = o
	# top centre: the scenario card; below it, left the astronaut and right the drone; bottom centre warnings; bottom left the keys
	card = _rich(Color(1.0, 0.95, 0.75), true)
	card.set_anchors_and_offsets_preset(Control.PRESET_CENTER_TOP)
	card.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	card.custom_minimum_size = Vector2(820, 0)
	card.offset_left = -410
	card.offset_right = 410
	card.offset_top = 8
	top = _panel(Color(0.95, 0.85, 0.4))
	top.set_anchors_and_offsets_preset(Control.PRESET_TOP_LEFT)
	top.offset_left = 16
	top.offset_top = 112
	left = _panel(Color(0.9, 0.95, 1.0))
	left.set_anchors_and_offsets_preset(Control.PRESET_TOP_LEFT)
	left.offset_left = 16
	left.offset_top = 160
	right = _panel(Color(0.85, 1.0, 0.95))
	right.set_anchors_and_offsets_preset(Control.PRESET_TOP_RIGHT)
	right.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	right.grow_horizontal = Control.GROW_DIRECTION_BEGIN
	right.offset_right = -16
	right.offset_top = 160
	mid = _rich(Color(1, 1, 1), false)
	mid.set_anchors_and_offsets_preset(Control.PRESET_CENTER_BOTTOM)
	mid.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	mid.grow_horizontal = Control.GROW_DIRECTION_BOTH
	mid.grow_vertical = Control.GROW_DIRECTION_BEGIN
	mid.offset_bottom = -96
	keys = _rich(Color(0.7, 0.75, 0.8), false)
	keys.set_anchors_and_offsets_preset(Control.PRESET_BOTTOM_LEFT)
	keys.grow_vertical = Control.GROW_DIRECTION_BEGIN
	keys.offset_left = 16
	keys.offset_bottom = -10
	keys.add_theme_font_size_override("normal_font_size", 13)

func _rich(c: Color, wrap: bool) -> RichTextLabel:
	var l := WfKeyText.label(font_size, c, wrap)
	add_child(l)
	return l

func _panel(c: Color) -> Label:
	var l := Label.new()
	l.add_theme_color_override("font_color", c)
	l.add_theme_color_override("font_outline_color", Color(0, 0, 0, 0.85))
	l.add_theme_constant_override("outline_size", 4)
	l.add_theme_font_size_override("font_size", font_size)
	add_child(l)
	return l

func refresh() -> void:
	var s: WfEvaBody = ops.suit
	var d: WfEvaBody = ops.drone
	var md: Dictionary = ops.pkg["modes"][ops.frame_mode]
	top.text = "EVA OPERATIONS · %s · %s · %s\nControl: %s · camera %s" % [
		"TRAINING SIMULATION" if ops.training else "OPERATIONAL RULES (FLIGHT_EVA HOLD: simulation only)", md["label"],
		"%.2f g" % float(md["accel_g"]), "ASTRONAUT" if ops.active == "suit" else "DRONE", ops.CAMS[ops.active][ops.cam_mode[ops.active]]]
	# ---- astronaut
	var feed := "drone vessels (docked; reserve isolated)" if ops.docked else ("RC-1 cartridge, then reserve" if ops.cartridge_seated != null else "suit reserve")
	var lines := ["ASTRONAUT %s" % ("◀ CONTROL" if ops.active == "suit" else ""), "Status: " + ops.suit_status(), "Feed: " + feed]
	if ops.docked:
		lines.append("Dock line N2: %.3f kg usable (%.0f %%)" % [ops.drone_gas.usable(), ops.drone_gas.fraction() * 100.0])
	elif ops.cartridge_seated != null:
		lines.append("Cartridge N2: %.3f kg usable (%.0f %%)" % [ops.cartridge_seated.tank.usable(), ops.cartridge_seated.tank.fraction() * 100.0])
	var floor_kg: float = ops.reserve.usable_full() * float(ops.pkg["rules"]["emergency_floor_fraction"])
	lines.append("Reserve N2: %.3f kg usable (%.0f %%) · emergency floor %.3f kg%s" % [ops.reserve.usable(), ops.reserve.fraction() * 100.0, floor_kg,
		" · ISOLATED" if ops.docked else ""])
	lines.append("Δv available: %.2f m/s · mass %.1f kg" % [s.dv_left(), s.total_mass()])
	lines.append("Control: %s%s%s" % ["MANUAL" if ops.suit_ctl.mode == WfEvaControl.Mode.MANUAL else "ASSISTED",
		" · att hold" if ops.suit_ctl.attitude_hold and ops.suit_ctl.mode == WfEvaControl.Mode.ASSIST else "", " · pos hold" if ops.suit_ctl.hold_pos else ""])
	lines.append("v rel ship %.3f m/s · rate %.1f °/s" % [s.linear_velocity.length(), rad_to_deg(s.angular_velocity.length())])
	var contact := []
	if s.held:
		contact.append("holding " + (ops.hold_id if ops.hold_id != "" else "hold"))
	if s.standing:
		contact.append("standing (%.2f g into the surface)" % (s.field_now.length() / 9.80665) if s.mag_a <= 0.0
			else "boots on the walkway (%.0f N pull)" % (s.mag_a * s.total_mass()))
	if s.tether_on:
		contact.append("tether %.1f / %.0f m%s" % [s.global_position.distance_to(s.tether_anchor), s.tether_len, " TAUT" if s.tether_taut else ""])
	lines.append("Contact: " + (", ".join(contact) if not contact.is_empty() else "free"))
	if s.boots != null:
		var b := s.boots
		lines.append("Mag boots %s · L %s · R %s%s%s" % ["ON" if b.armed else "OFF", b.state_name(0), b.state_name(1),
			" · SLIPPING" if b.slipping else "", (" · " + b.blocked) if b.blocked != "" else ""])
	lines.append("Hatch %.1f m · Brow aft face %.1f m" % [s.global_position.distance_to(ops.world.hatch), maxf(0.0, ops.world.face_x(ops.world.radius_of(s.global_position)) - 0.1 - s.global_position.x)])
	if s.gas_short:
		lines.append("!! THRUSTERS STARVED: no gas in the feed")
	left.text = "\n".join(lines)
	# ---- drone
	var dl := ["%s DRONE" % ("CONTROL ▶" if ops.active == "drone" else ""), "Mode: " + ("DOCKED" if ops.docked else ops.dops.name()),
		"N2: %.3f kg usable (%.0f %%)" % [ops.drone_gas.usable(), ops.drone_gas.fraction() * 100.0]]
	if not ops.docked:
		dl.append("Δv available: %.1f m/s · mass %.2f kg" % [d.dv_left(), d.total_mass()])
		dl.append("Valves: %s (%d live)%s" % ["near-suit set" if d.alloc == ops.a_near else "free flight set", d.alloc.count() - d.alloc.failed.size(),
			" · %d FAILED" % d.alloc.failed.size() if d.alloc.failed.size() > 0 else ""])
		dl.append("v rel ship %.3f m/s · to astronaut %.2f m at %.3f m/s" % [d.linear_velocity.length(), d.global_position.distance_to(s.global_position),
			(d.linear_velocity - s.linear_velocity).length()])
		dl.append("Arms %s · gripper %s%s" % ["deployed" if ops.dops.arms_ready() else ("moving" if ops.dops.arms_t > 0.0 else "stowed"),
			"closed" if ops.dops.gripper_closed else "open", " · holding RC-1 (%.3f kg)" % ops.dops.holding.tank.usable() if ops.dops.holding != null else ""])
		dl.append("Control: " + ("MANUAL" if ops.drone_ctl.mode == WfEvaControl.Mode.MANUAL else "ASSISTED"))
	dl.append("Station rack: %d RC-1 cartridges" % int(ops.world.station["cartridges"]))
	right.text = "\n".join(dl)
	# ---- messages and warnings
	var w := []
	for k in ["suit", "drone"]:
		var h: Dictionary = ops.hazard_now[k]
		if not h.is_empty():
			w.append("%s %s: %s (%.1f m)" % ["⚠ INSIDE" if h["inside"] else "⚠ NEAR", "ASTRONAUT" if k == "suit" else "DRONE", h["label"], maxf(0.0, h["distance"])])
	var st: String = ops.suit_status()
	if st != "NOMINAL":
		w.append("⚠ ASTRONAUT N2: " + st)
	if not ops.docked and ops.drone_gas.fraction() < float(ops.pkg["rules"]["low_fraction"]):
		w.append("⚠ DRONE N2 LOW (%.0f %%)" % (ops.drone_gas.fraction() * 100.0))
	for m in ops.messages.slice(maxi(0, ops.messages.size() - 3)):
		w.append(("" if m["ok"] else "✖ ") + m["t"])
	mid.text = WfKeyText.rich("\n".join(w))
	card.text = WfKeyText.rich(ops.scenario.card())
	keys.text = WfKeyText.rich(_keys(), "now")

func _keys() -> String:
	var k = func(id): return ops.key(id)
	var t := "%s%s%s%s%s%s move · %s%s%s%s%s%s rotate · %s fine · %s brake · %s assist · %s astronaut · %s drone · %s camera\n" % [
		k.call("evaops.fwd"), k.call("evaops.back"), k.call("evaops.left"), k.call("evaops.right"), k.call("evaops.up"), k.call("evaops.down"),
		k.call("evaops.pitch_up"), k.call("evaops.pitch_down"), k.call("evaops.yaw_left"), k.call("evaops.yaw_right"), k.call("evaops.roll_left"),
		k.call("evaops.roll_right"), k.call("evaops.fine"), k.call("evaops.brake"), k.call("evaops.assist"), k.call("evaops.astronaut"),
		k.call("evaops.drone"), k.call("evaops.camera")]
	if ops.active == "suit":
		t += "%s grab/release · %s push off · %s tether · %s dock/undock · %s call drone · %s use · %s attitude hold · %s position hold" % [
			k.call("evaops.grab"), k.call("evaops.push"), k.call("evaops.tether"), k.call("evaops.dock"), k.call("evaops.help"), k.call("evaops.interact"),
			k.call("evaops.att_hold"), k.call("evaops.pos_hold")]
	else:
		t += "%s drone mode · %s arms · %s gripper · %s seat/inspect · %s dock/undock · %s position hold" % [k.call("evaops.autopilot"),
			k.call("evaops.arms"), k.call("evaops.gripper"), k.call("evaops.interact"), k.call("evaops.dock"), k.call("evaops.pos_hold")]
	t += "\n%s drift/burn · %s operational/training · %s First Flight / free · %s TRAINING RESET · %s checkpoint · %s valve fault · %s back to the walk · right mouse: look" % [
		k.call("evaops.frame"), k.call("evaops.training"), k.call("evaops.scenario"), k.call("evaops.reset"), k.call("evaops.checkpoint"),
		k.call("evaops.fault"), k.call("evaops.exit")]
	return t
