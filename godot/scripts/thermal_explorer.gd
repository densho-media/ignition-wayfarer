class_name WfThermalExplorer
extends CanvasLayer
## MECH-002 / POL-008 thermal coupling (references/SIM_INTEGRATION_PLAN_2026-10-17.md, Milestone B): an educational heat balance of the
## three fixed hot blades, in the First Ignition timeline scene. T opens it; ↑ ↓ pick a row, - = change it, Backspace resets.
## Every input starts at the rig's values (40_THERMAL B7:B10, B16, B23, the Y155 cases 40!A110:F123) and the rig's own numbers
## (thermal_budget.py) are the check reference: the explorer reproduces them (check_thermal) before it shows anything else.
## A changed heat input is HYPOTHETICAL; the operating drive waste heat (40!B11), the thermal buffer (B15) and the Heat Debt state (B13)
## stay OPEN, so accumulated heat is shown in joules and never as a temperature rise. The blades are drawn unchanged: nothing here
## resizes, recolours or moves them (40!A41, R1/R8).
## Physics: gross emission from the physical emitting faces eps*SIGMA*A*T^4; the share (1 - F) that lands on Wayfarer's own hull, rings and
## shield is not rejected (40!B23); net to space = F * gross. Sunlight and the space background are left out: neither is sourced and the
## absorbed sunlight depends on the Sun distance, which is UNKNOWN.

const SIGMA := 5.670374419e-8      # Stefan-Boltzmann, 01_CONSTANTS (LOCKED); the check reproduces the rig's Python results with it
const HEAT_STEP_W := 0.5e9
const HEAT_MAX_W := 40e9
const T_MIN_K := 1000.0
const T_STEP_K := 50.0
const AREA_STEP := 0.05
const ROWS := ["HEAT", "SURFACE", "TEMPERATURE", "AREA", "DURATION"]
const C_TEXT := Color("D3D1C7")
const C_MUTED := Color("888780")
const C_CAUTION := Color("EF9F27")
const C_HEAT := Color("F09595")
const C_NET := Color("5DCAA5")
const C_GROSS := Color("85B7EB")
const C_SHIP := Color("B4B2A9")

var rig: Dictionary
var th: Dictionary
var cases: Array = []
var faces := 2
var net_one_face_m2 := 0.0          # as-built net one-face hot area, three blades (DERIVED, 40!A21)
var calib_W := 0.0                  # 16 GW root calibration (DIAGNOSTIC, 40!B16)
var T_work := 0.0                   # 1800 K WORKING (40!B8): the explorer never goes above it (qualification OPEN)
var durations: Array = []           # [label, seconds]
var heat_W := 0.0
var case_i := 0
var T_K := 0.0
var area_frac := 1.0
var dur_i := 0
var row := 0
var shown := false
var panel := PanelContainer.new()
var text := Label.new()
var bars := Control.new()
var font: Font

func setup(r: Dictionary, burn_s) -> void:
	rig = r
	th = r.get("thermal", {})
	layer = 6
	cases = th.get("y155_scenario", {}).get("cases", [])
	net_one_face_m2 = float(th.as_built_net_area_total.value)
	# The emitting faces follow from the rig's own effective area: effective = net one-face x faces x F (40!B7).
	faces = int(round(float(th.effective_area.value) / (net_one_face_m2 * float(th.view_factor.value))))
	calib_W = float(th.drive_heat_calibration.absorbed_heat_W)
	T_work = float(th.temperature.value)
	durations = [["1 hour", 3600.0], ["1 day", 86400.0]]
	if burn_s != null:
		durations.append(["the First Ignition ramp (%.3f d, 22_ROUTE_MODEL)" % (float(burn_s) / 86400.0), float(burn_s)])
	durations.append(["30 days", 30.0 * 86400.0])
	reset()
	font = ThemeDB.fallback_font
	var sb := StyleBoxFlat.new()
	sb.bg_color = Color("0E1116", 0.94)
	sb.border_color = Color("444441")
	sb.set_border_width_all(1)
	sb.set_content_margin_all(12.0)
	panel.add_theme_stylebox_override("panel", sb)
	panel.position = Vector2(24, 92)
	add_child(panel)
	var col := VBoxContainer.new()
	col.add_theme_constant_override("separation", 8)
	panel.add_child(col)
	text.add_theme_font_size_override("font_size", 13)
	text.add_theme_color_override("font_color", C_TEXT)
	text.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	text.custom_minimum_size.x = 680
	col.add_child(text)
	bars.custom_minimum_size = Vector2(680, 124)
	bars.draw.connect(_draw_bars)
	col.add_child(bars)
	panel.visible = false

func reset() -> void:
	heat_W = calib_W
	case_i = 0
	T_K = T_work
	area_frac = 1.0
	dur_i = 0

func surface() -> Dictionary:
	return cases[case_i] if case_i < cases.size() else {"id": "BASELINE", "emissivity": float(th.emissivity.value), "view_factor": float(th.view_factor.value), "status": th.emissivity.canon_status}

## The balance for the current inputs (or any given ones): watts and joules, nothing else.
func current() -> Dictionary:
	return balance(heat_W, surface(), T_K, area_frac, -1.0)

func balance(q_W: float, s: Dictionary, t_K: float, frac: float, dur_s: float) -> Dictionary:
	var eps := float(s.emissivity)
	var f := float(s.view_factor)
	var area := net_one_face_m2 * faces * frac
	var gross := eps * SIGMA * area * pow(t_K, 4)
	var net := f * gross
	var dt: float = durations[dur_i][1] if dur_s < 0.0 else dur_s
	var out := {"area_m2": area, "gross_W": gross, "net_W": net, "ship_W": gross - net, "imbalance_W": q_W - net, "debt_J": maxf(q_W - net, 0.0) * dt, "duration_s": dt}
	out["T_required_K"] = pow(q_W / (eps * SIGMA * area * f), 0.25) if area > 0.0 and q_W > 0.0 else (0.0 if q_W <= 0.0 else INF)
	return out

func toggle() -> void:
	shown = not shown
	panel.visible = shown
	update_now()

func handle_key(e: InputEvent) -> bool:
	# ACI-10: thermal.toggle (flight context) and thermal.* while the panel shows, matched by their default keys.
	if WfInput.key_of(e, ["flight"]) == KEY_T and not e.is_echo():
		toggle()
		return true
	if not shown:
		return false
	var k := WfInput.key_of(e, ["thermal"])
	match k:
		KEY_UP: row = (row + ROWS.size() - 1) % ROWS.size()
		KEY_DOWN: row = (row + 1) % ROWS.size()
		KEY_MINUS, KEY_EQUAL: change(1 if k == KEY_EQUAL else -1)
		KEY_BACKSPACE: reset()
		_: return false
	update_now()
	return true

func change(d: int) -> void:
	match ROWS[row]:
		"HEAT": heat_W = clampf(heat_W + d * HEAT_STEP_W, 0.0, HEAT_MAX_W)
		"SURFACE": case_i = (case_i + d + cases.size()) % maxi(cases.size(), 1)
		"TEMPERATURE": T_K = clampf(T_K + d * T_STEP_K, T_MIN_K, T_work)
		"AREA": area_frac = clampf(snappedf(area_frac + d * AREA_STEP, AREA_STEP), 0.0, 1.0)
		"DURATION": dur_i = (dur_i + d + durations.size()) % durations.size()

static func sci(x: float) -> String:
	if x <= 0.0:
		return "0"
	var e := int(floor(log(x) / log(10.0)))
	return "%.3f×10^%d" % [x / pow(10.0, e), e]

static func gw(w: float) -> String:
	return "%.3f GW" % (w / 1e9)

func heat_label() -> String:
	if is_equal_approx(heat_W, calib_W):
		return "DIAGNOSTIC root calibration (%s calibration power × %s absorbed fraction, 40!B16) — not the operating heat" % [
			"%.0f TW" % (float(th.drive_heat_calibration.calibration_power.value) / 1e12), str(th.drive_heat_calibration.absorbed_heat_fraction.value)]
	return "HYPOTHETICAL input (the visitor's) — not a Wayfarer value"

func update_now() -> void:
	if not shown:
		return
	var s := surface()
	var b := current()
	var cur := func(i: int) -> String: return "▸ " if i == row else "   "
	var lines := [WfInput.keys("THERMAL EXPLORER · three fixed hot blades · HEAT BALANCE   ({thermal.toggle} close · {thermal.row_prev} {thermal.row_next} row · {thermal.less} {thermal.more} change · {thermal.reset} reset)"),
		"WHAT  The drive leaves heat inside the ship. In space the only way out is to glow it away from the radiator blades.",
		"WHY   Emission grows with T⁴ and with area: a 10 % cooler blade sheds a third less. A blade also sees parts of its own ship.",
		"",
		"%sHEAT INPUT     %s   %s" % [cur.call(0), gw(heat_W), heat_label()],
		"%sSURFACE        %s  ε %.2f · view factor %.2f   %s" % [cur.call(1), s.id, float(s.emissivity), float(s.view_factor), s.status],
		"%sBLADE TEMP     %.0f K   %s" % [cur.call(2), T_K, "WORKING target (40!B8); above it is not qualified" if is_equal_approx(T_K, T_work) else "HYPOTHETICAL, below the WORKING 1800 K"],
		"%sAREA IN USE    %.0f %% of %.1f m² (both faces of 3 × %.1f m² net, DERIVED 40!A21)%s" % [cur.call(3), area_frac * 100.0, net_one_face_m2 * faces, net_one_face_m2 / 3.0,
			"" if area_frac >= 1.0 else "   HYPOTHETICAL isolated cells (40!A26)"],
		"%sDURATION       %s" % [cur.call(4), durations[dur_i][0]],
		"",
		"HOW   gross emitted  ε σ A T⁴ = %s   →   net to space  F × gross = %s   ·   onto Wayfarer itself %s (not rejected)" % [gw(b.gross_W), gw(b.net_W), gw(b.ship_W)]]
	if b.imbalance_W > 0.0:
		var need := "none: no area in use"
		if b.T_required_K < INF:
			need = "%.0f K (%s the WORKING %.0f K)" % [b.T_required_K, "above" if b.T_required_K > T_work else "within", T_work]
		lines.append("      heat in − net out = %s DEFICIT  →  accumulates %s J over %s; blade temperature to close it %s" % [gw(b.imbalance_W), sci(b.debt_J), durations[dur_i][0], need])
		lines.append("      What that heat does to temperatures needs the loops' heat capacity: OPEN (40!B13 Heat Debt, B15 buffer). No temperature rise is shown.")
	else:
		lines.append("      net out − heat in = %s ideal spare: NOT a margin (EYE, Crown, machinery loads and qualification are not included)" % gw(-b.imbalance_W))
	lines.append("RESULT DIAGNOSTIC · actual drive waste heat OPEN (40!B11) · sunlight and space background not included (Sun distance UNKNOWN) · the blades are not resized")
	text.text = "\n".join(lines)
	bars.queue_redraw()

func _draw_bars() -> void:
	var b := current()
	var w := bars.size.x - 200.0
	var top := maxf(maxf(heat_W, b.gross_W), 1.0)
	var items := [["heat in", heat_W, C_HEAT], ["gross emitted", b.gross_W, C_GROSS], ["net to space", b.net_W, C_NET], ["onto own ship", b.ship_W, C_SHIP]]
	for i in items.size():
		var y := 4.0 + i * 30.0
		bars.draw_string(font, Vector2(0, y + 18), items[i][0], HORIZONTAL_ALIGNMENT_LEFT, -1, 13, C_MUTED)
		bars.draw_rect(Rect2(110, y, w * items[i][1] / top, 22), Color(items[i][2], 0.85))
		bars.draw_string(font, Vector2(118 + w * items[i][1] / top, y + 16), gw(items[i][1]), HORIZONTAL_ALIGNMENT_LEFT, -1, 13, C_TEXT)
	var xh: float = 110 + w * heat_W / top
	bars.draw_line(Vector2(xh, 2), Vector2(xh, 122), C_CAUTION, 1.0)

## Headless checks (flight.tscn -- --check-thermal): the rig's Python results, energy bookkeeping, honest labels and an untouched ship.
func checks(snapshot: Callable) -> Array:
	var out := []
	var before = snapshot.call()
	reset()
	# 1 The rig's thermal_budget.y155 rows (Python) at the default inputs, and the calibration ideal area 40!B17.
	var ref := []
	for i in cases.size():
		var b := balance(calib_W, cases[i], T_work, 1.0, 0.0)
		ref.append({"id": cases[i].id, "net_err": absf(b.net_W - float(cases[i].rejection_W)) / float(cases[i].rejection_W),
			"residual_err": absf((calib_W - b.net_W) - float(cases[i].residual_W)) / absf(float(cases[i].residual_W))})
	var eps0 := float(th.emissivity.value)
	var ideal_err := absf(eps0 * SIGMA * float(th.drive_heat_calibration.ideal_area_m2) * pow(T_work, 4) - calib_W) / calib_W
	out.append({"id": "thermal_owner_reference", "ok": faces == 2 and cases.size() >= 1 and ref.all(func(x): return x.net_err < 1e-9 and x.residual_err < 1e-6) and ideal_err < 1e-6,
		"actual": {"faces": faces, "cases": ref, "ideal_area_err": ideal_err},
		"note": "the explorer's Stefan–Boltzmann reproduces the rig's Python rejection and 16 GW residual for every Y155 case and 40!B17's 29,865.9 m² ideal area"})
	# 2 Bookkeeping: gross = net + onto the ship; the required temperature closes the balance; the debt is the integral of the imbalance.
	var worst := 0.0
	var t_err := 0.0
	var debt_err := 0.0
	for q in [0.0, 5e9, calib_W, 30e9]:
		for t in [T_MIN_K, 1500.0, T_work]:
			for fr in [0.25, 2.0 / 3.0, 1.0]:
				for c in cases:
					var b := balance(q, c, t, fr, 86400.0)
					worst = maxf(worst, absf(b.gross_W - b.net_W - b.ship_W) / b.gross_W)
					if q > 0.0:
						t_err = maxf(t_err, absf(balance(q, c, b.T_required_K, fr, 0.0).net_W - q) / q)
					var sum := 0.0
					for k in 1000:
						sum += maxf(q - b.net_W, 0.0) * 86.4
					debt_err = maxf(debt_err, absf(sum - b.debt_J) / maxf(b.debt_J, 1.0))
	var none := balance(calib_W, surface(), T_work, 0.0, float(durations[2][1]) if durations.size() > 3 else 0.0)
	out.append({"id": "thermal_energy_bookkeeping", "ok": worst < 1e-12 and t_err < 1e-9 and debt_err < 1e-9 and is_equal_approx(none.debt_J, calib_W * none.duration_s),
		"actual": {"gross_split_err": worst, "T_required_err": t_err, "debt_err": debt_err, "no_area_burn_debt_J": none.debt_J},
		"note": "gross = net to space + onto the ship; the shown required temperature rejects exactly the input; the debt is the time integral of the deficit (no area over the burn: 16 GW × 7.548 d, cf. 40 row 38)"})
	# 3 Labels: OPEN items never get a number, hypothetical inputs say so, no temperature rise appears.
	var bad := []
	shown = true
	for setting in [[calib_W, 0, T_work, 1.0], [20e9, 1, T_work, 1.0], [5e9, 0, 1400.0, 0.5], [calib_W, 2, T_work, 0.0]]:
		heat_W = setting[0]
		case_i = setting[1] % maxi(cases.size(), 1)
		T_K = setting[2]
		area_frac = setting[3]
		update_now()
		var t := text.text
		if not ("actual drive waste heat OPEN" in t and "DIAGNOSTIC" in t and "not resized" in t):
			bad.append([setting, "disclosure"])
		if not is_equal_approx(heat_W, calib_W) and not "HYPOTHETICAL input" in t:
			bad.append([setting, "hypothetical"])
		if (current().imbalance_W > 0.0) != ("DEFICIT" in t) or ("DEFICIT" in t and not "No temperature rise is shown" in t):
			bad.append([setting, "rise"])
		if "spare" in t and not "NOT a margin" in t:
			bad.append([setting, "margin"])
	out.append({"id": "thermal_labels_honest", "ok": bad.is_empty() and not bool(th.drive_waste_heat.known) and not bool(th.heat_debt.known), "actual": {"bad": bad},
		"note": "drive waste heat and Heat Debt are OPEN in the rig and on screen; a changed input reads HYPOTHETICAL; a spare is never a margin; no temperature rise without a heat capacity"})
	# 4 The explorer changes nothing in the scene.
	for i in ROWS.size():
		row = i
		for d in [1, 1, -1, -1, -1]:
			change(d)
		update_now()
	reset()
	shown = false
	panel.visible = false
	var after = snapshot.call()
	out.append({"id": "thermal_ship_unchanged", "ok": str(before) == str(after), "actual": {"changed": str(before) != str(after)},
		"note": "every row changed both ways: blade transforms, hot-face emission, frame, state and scenario unchanged"})
	return out
