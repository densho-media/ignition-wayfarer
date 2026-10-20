extends Control
## MECH-003 six-year life-support simulator (Milestone C, references/SIM_INTEGRATION_PLAN_2026-10-17.md). Reads generated/wf_life_support.json
## (src/wayfarer/life_support.py, from data/life_support.toml = the owner's 41_SURVIVAL_RESOURCES study rows) and repeats the module's
## step exactly; check_life_support() proves the repetition against the module's checkpoints before anything else is trusted.
## Owner defaults: five consumers (Seraph eats no human food), 90 % water recovery (41 scenario, not achieved), no O2 recovery and no
## Garden credit (38 S02, 41!B20), the 10 t food category, O2 and makeup-water stores OPEN. Anything the visitor changes is HYPOTHETICAL;
## a Garden or O2-recovery share is an UNCLOSED source (its water, CO2, light power and plant mass are not modelled). Deficits are shown,
## never hidden. Nothing here is canon or writes anything back.

const ROWS := ["CONSUMERS", "WATER", "O2_RECOVERY", "GARDEN", "O2_STORE", "WATER_STORE", "FOOD_EXTRA"]
const PLAY_DAYS_PER_S := 120.0
const C_BG := Color("0E1116")
const C_TEXT := Color("D3D1C7")
const C_MUTED := Color("888780")
const C_CAUTION := Color("EF9F27")
const C_BAD := Color("F09595")
const C_FOOD := Color("97C459")
const C_O2 := Color("85B7EB")
const C_WATER := Color("5DCAA5")
const C_WASTE := Color("B4B2A9")

var data: Dictionary = {}
var rate := {}
var base_store := {}
var duration := 0.0
var p := {}                     # current scenario
var row := 0
var day := 0.0
var playing := false
var series: Array = []          # one snapshot per whole day (+ the end), for the chart and the scrubber
var text := Label.new()
var chart := Control.new()
var font: Font

func _ready() -> void:
	WfInput.context = "life"                      # ACI-10: the guide and the Codex read this scene's actions
	font = ThemeDB.fallback_font
	var bg := ColorRect.new()
	bg.color = C_BG
	bg.set_anchors_preset(Control.PRESET_FULL_RECT)
	add_child(bg)
	var col := VBoxContainer.new()
	col.position = Vector2(24, 18)
	col.add_theme_constant_override("separation", 8)
	add_child(col)
	text.add_theme_font_size_override("font_size", 14)
	text.add_theme_color_override("font_color", C_TEXT)
	text.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	text.custom_minimum_size.x = 1180
	col.add_child(text)
	chart.custom_minimum_size = Vector2(1180, 230)
	chart.draw.connect(_draw_chart)
	col.add_child(chart)
	if not FileAccess.file_exists("res://generated/wf_life_support.json"):
		text.text = "No life-support data: run python3 tools/workflow.py runtime-export"
		return
	data = JSON.parse_string(FileAccess.get_file_as_string("res://generated/wf_life_support.json"))
	for r in data.rates:
		rate[r.id] = float(r.value)
	for s in data.stores:
		base_store[s.id] = float(s.value) if s.known else null
	duration = float(data.duration.value)
	reset()
	var args := OS.get_cmdline_user_args()
	if "--check-life-support" in args:
		check_life_support()
		return
	for a in args:
		if a.begins_with("--capture-life-support="):
			capture(a.trim_prefix("--capture-life-support="))

func reset() -> void:
	p = defaults()
	day = duration
	rebuild()

func defaults() -> Dictionary:
	var pr: Dictionary = data.process
	return {"consumers": int(data.consumers.story), "water_recovery": float(pr.water_recovery.default), "o2_recovery": float(pr.o2_recovery.default),
		"garden_food": float(pr.garden_food.default), "extra": {}}

# ------------------------------------------------------------------------------------------------ the step (life_support.py, line for line)

func start(sc: Dictionary) -> Dictionary:
	var s := base_store.duplicate()
	for k in sc.extra:
		s[k] = float(sc.extra[k]) if s.get(k) == null else float(s[k]) + float(sc.extra[k])
	var z := {"FOOD": 0.0, "O2": 0.0, "WATER_MAKEUP": 0.0}
	return {"day": 0.0, "initial": s.duplicate(), "store": s, "drawn": z.duplicate(), "required": z.duplicate(), "deficit": z.duplicate(), "depleted": {},
		"need": {"FOOD": 0.0, "O2": 0.0, "WATER": 0.0}, "garden_food": 0.0, "o2_recovered": 0.0, "water_recovered": 0.0, "co2_removed": 0.0, "waste": 0.0}

static func _draw_store(st: Dictionary, key: String, amount: float, dt: float) -> void:
	if st.store[key] == null:
		st.required[key] += amount
		return
	var have: float = st.store[key]
	var take := minf(have, amount)
	st.store[key] = have - take
	st.drawn[key] += take
	st.deficit[key] += amount - take
	if amount > take and not st.depleted.has(key):
		st.depleted[key] = st.day + (take / amount) * dt

func step(st: Dictionary, sc: Dictionary, dt: float) -> void:
	var n := float(sc.consumers)
	var food: float = n * rate.FOOD * dt
	var o2: float = n * rate.O2 * dt
	var water: float = n * rate.WATER_TURNOVER * dt
	st.need.FOOD += food
	st.need.O2 += o2
	st.need.WATER += water
	st.garden_food += food * sc.garden_food
	_draw_store(st, "FOOD", food * (1.0 - sc.garden_food), dt)
	st.o2_recovered += o2 * sc.o2_recovery
	_draw_store(st, "O2", o2 * (1.0 - sc.o2_recovery), dt)
	st.water_recovered += water * sc.water_recovery
	_draw_store(st, "WATER_MAKEUP", water * (1.0 - sc.water_recovery), dt)
	st.co2_removed += n * rate.CO2_REMOVED * dt
	st.waste += n * rate.WASTE * dt
	st.day += dt

func run_to(st: Dictionary, sc: Dictionary, to_day: float) -> Dictionary:
	while st.day + 1.0 <= to_day + 1e-12:
		step(st, sc, 1.0)
	if to_day - st.day > 1e-12:
		step(st, sc, to_day - st.day)
	return st

static func ledger_errors(st: Dictionary) -> Dictionary:
	var e := {"FOOD": st.need.FOOD - st.garden_food - st.drawn.FOOD - st.required.FOOD - st.deficit.FOOD,
		"O2": st.need.O2 - st.o2_recovered - st.drawn.O2 - st.required.O2 - st.deficit.O2,
		"WATER": st.need.WATER - st.water_recovered - st.drawn.WATER_MAKEUP - st.required.WATER_MAKEUP - st.deficit.WATER_MAKEUP}
	for k in st.initial:
		if st.initial[k] != null:
			e["store_" + k] = float(st.initial[k]) - float(st.store[k]) - float(st.drawn[k])
	return e

func rebuild() -> void:
	series.clear()
	var st := start(p)
	series.append(st.duplicate(true))
	while st.day < duration - 1e-12:
		run_to(st, p, minf(st.day + 1.0, duration))
		series.append(st.duplicate(true))
	update_now()

func at_day(d: float) -> Dictionary:
	return series[clampi(int(ceil(d - 1e-9)), 0, series.size() - 1)]

# ------------------------------------------------------------------------------------------------ input

func _process(delta: float) -> void:
	if playing:
		day = minf(day + delta * PLAY_DAYS_PER_S, duration)
		playing = day < duration
		update_now()

func _unhandled_input(e: InputEvent) -> void:
	if data.is_empty() or not WfInput.pressed(e, true):
		return
	var k := WfInput.key_of(e, ["life"])                  # ACI-10: life.* actions and ui.cancel
	match k:
		KEY_UP: row = (row + ROWS.size() - 1) % ROWS.size()
		KEY_DOWN: row = (row + 1) % ROWS.size()
		KEY_MINUS, KEY_EQUAL:
			change(1 if k == KEY_EQUAL else -1)
			rebuild()
		KEY_BACKSPACE: reset()
		KEY_COMMA, KEY_PERIOD:
			playing = false
			day = clampf(day + (1.0 if k == KEY_PERIOD else -1.0) * (30.0 if WfInput.shifted(e) else 1.0), 0.0, duration)
		KEY_HOME:
			playing = false
			day = 0.0
		KEY_END:
			playing = false
			day = duration
		KEY_P:
			if day >= duration:
				day = 0.0
			playing = not playing
		KEY_ESCAPE:
			get_tree().change_scene_to_file("res://scenes/review.tscn")
		_: return
	update_now()
	get_viewport().set_input_as_handled()

func change(d: int) -> void:
	var ex: Dictionary = p.extra
	match ROWS[row]:
		"CONSUMERS": p.consumers = int(data.consumers.stress) if p.consumers == int(data.consumers.story) else int(data.consumers.story)
		"WATER": p.water_recovery = clampf(snappedf(p.water_recovery + 0.01 * d, 0.01), 0.0, 1.0)
		"O2_RECOVERY": p.o2_recovery = clampf(snappedf(p.o2_recovery + 0.1 * d, 0.1), 0.0, 0.9)
		"GARDEN": p.garden_food = clampf(snappedf(p.garden_food + 0.05 * d, 0.05), 0.0, 1.0)
		"O2_STORE": _extra(ex, "O2", 500.0 * d)
		"WATER_STORE": _extra(ex, "WATER_MAKEUP", 1000.0 * d)
		"FOOD_EXTRA": _extra(ex, "FOOD", 1000.0 * d)

static func _extra(ex: Dictionary, key: String, d: float) -> void:
	var v := maxf(float(ex.get(key, 0.0)) + d, 0.0)
	if v <= 0.0:
		ex.erase(key)
	else:
		ex[key] = v

# ------------------------------------------------------------------------------------------------ text and chart

static func kg(x: float) -> String:
	return "%s kg" % String.num(x, 1)

func src(id: String) -> String:
	for r in data.rates:
		if r.id == id:
			return "%s %s, %s" % [str(r.value), r.unit, r.source]
	return ""

func store_text(st: Dictionary, key: String) -> String:
	if st.initial[key] == null:
		return "store OPEN — required so far %s" % kg(st.required[key])
	var t := "store %s → left %s" % [kg(st.initial[key]), kg(st.store[key])]
	if st.depleted.has(key) and st.depleted[key] <= day + 1e-9:
		t += "   EMPTY on day %.1f · DEFICIT %s" % [st.depleted[key], kg(st.deficit[key])]
	return t

func update_now() -> void:
	if data.is_empty():
		return
	var st := run_to(start(p), p, day)       # the exact state at the cursor (the series holds whole days only)
	var d := defaults()
	var cur := func(i: int) -> String: return "▸ " if i == row else "   "
	var hyp := func(changed: bool) -> String: return "   HYPOTHETICAL" if changed else ""
	var ex: Dictionary = p.extra
	var lines := ["LIFE SUPPORT · SIX-YEAR STOCK AND FLOW   %s   %s" % [data.meta.notice, WfInput.keys("({life.row_prev} {life.row_next} row · {life.less} {life.more} change · {life.reset} owner defaults · {life.day_prev} {life.day_next} day (shift ×30) · {life.play} play · {life.start} {life.end} · {ui.cancel})")],
		"WHAT  Every kilogram the crew uses comes from a store, a recycler or the Garden — or it is missing.   WHY  Six years is %.1f days: small daily rates become tonnes." % duration,
		"HOW   need = Garden + recovered + drawn from the store + deficit, per resource and day; a store that is OPEN has no number, so its draw is shown as required.",
		"",
		"%sCONSUMERS      %d %s%s" % [cur.call(0), p.consumers, "(41!B7 story crew; Seraph eats no human food)" if p.consumers == d.consumers else "(41!B8 12-person stress test)", hyp.call(p.consumers != d.consumers)],
		"%sWATER RECOVERY %.0f %%  (41 scenarios 90 / 98 %%, NOT achieved, 38 S05)%s" % [cur.call(1), p.water_recovery * 100.0, hyp.call(not (is_equal_approx(p.water_recovery, 0.9) or is_equal_approx(p.water_recovery, 0.98)))],
		"%sO2 RECOVERY    %.0f %%%s" % [cur.call(2), p.o2_recovery * 100.0, "  no credit (38 S02: not a verified loop)" if p.o2_recovery == 0.0 else "   HYPOTHETICAL · UNCLOSED source (its CO2, water and power are not modelled)"],
		"%sGARDEN FOOD    %.0f %%%s" % [cur.call(3), p.garden_food * 100.0, "  no credit (41!B20 = 0 until the crop study closes)" if p.garden_food == 0.0 else "   HYPOTHETICAL · UNCLOSED source (8 m² trays, light power and plant inputs OPEN, 38 S10)"],
		"%sO2 STORE       %s" % [cur.call(4), "OPEN (38 S03 sizing OPEN)" if not ex.has("O2") else "%s   HYPOTHETICAL" % kg(ex.O2)],
		"%sWATER STORE    %s" % [cur.call(5), "OPEN (shield water is not a released potable reserve)" if not ex.has("WATER_MAKEUP") else "%s   HYPOTHETICAL" % kg(ex.WATER_MAKEUP)],
		"%sEXTRA FOOD     %s" % [cur.call(6), "none (food: the 10 t launch category, 41!B21, includes consumables)" if not ex.has("FOOD") else "+%s   HYPOTHETICAL" % kg(ex.FOOD)],
		"",
		"DAY %.1f of %.1f  (year %.2f)" % [day, duration, day / 365.25],
		"FOOD   need %s  =  Garden %s + %s   [%s]" % [kg(st.need.FOOD), kg(st.garden_food), store_text(st, "FOOD"), src("FOOD")],
		"O2     need %s  =  recovered %s + %s   [%s]" % [kg(st.need.O2), kg(st.o2_recovered), store_text(st, "O2"), src("O2")],
		"WATER  loop turnover %s  =  recovered %s + makeup: %s   [%s]" % [kg(st.need.WATER), kg(st.water_recovered), store_text(st, "WATER_MAKEUP"), src("WATER_TURNOVER")],
		"CO2 removed %s   ·   waste %s   [%s · %s]" % [kg(st.co2_removed), kg(st.waste), src("CO2_REMOVED"), src("WASTE")],
		"RESULT STUDY · 41_SURVIVAL_RESOURCES targets, not canon · no power, mass or volume of the machines (41 OPEN rows) · Seraph's needs are not human needs"]
	text.text = "\n".join(lines)
	chart.queue_redraw()

func _draw_chart() -> void:
	if series.is_empty():
		return
	var r := Rect2(Vector2(60, 10), chart.size - Vector2(80, 40))
	chart.draw_rect(Rect2(Vector2.ZERO, chart.size), Color("161A20"))
	var end: Dictionary = series[-1]
	var top := maxf(maxf(end.need.FOOD, 1.0), maxf(end.need.O2, end.need.WATER * (1.0 - p.water_recovery)))
	for f in [0.0, 0.25, 0.5, 0.75, 1.0]:
		var y: float = r.end.y - r.size.y * f
		chart.draw_line(Vector2(r.position.x, y), Vector2(r.end.x, y), Color(C_MUTED, 0.25), 1.0)
		chart.draw_string(font, Vector2(4, y + 4), "%.0f t" % (top * f / 1000.0), HORIZONTAL_ALIGNMENT_LEFT, -1, 12, C_MUTED)
	for yr in range(0, 7):
		var x := r.position.x + r.size.x * (yr * 365.25) / duration
		chart.draw_string(font, Vector2(x - 4, r.end.y + 18), "y%d" % yr, HORIZONTAL_ALIGNMENT_LEFT, -1, 12, C_MUTED)
	# Store-side needs include their deficit: a shortfall is never drawn smaller than it is.
	var lines := [["food store left", func(s): return s.store.FOOD, C_FOOD], ["all deficits", func(s): return s.deficit.FOOD + s.deficit.O2 + s.deficit.WATER_MAKEUP, C_BAD],
		["O2 needed from stores", func(s): return s.drawn.O2 + s.required.O2 + s.deficit.O2, C_O2],
		["makeup water needed", func(s): return s.drawn.WATER_MAKEUP + s.required.WATER_MAKEUP + s.deficit.WATER_MAKEUP, C_WATER],
		["waste", func(s): return s.waste, C_WASTE]]
	for i in lines.size():
		var pts := PackedVector2Array()
		for k in range(0, series.size(), 4):
			var s: Dictionary = series[k]
			pts.append(Vector2(r.position.x + r.size.x * s.day / duration, r.end.y - r.size.y * float(lines[i][1].call(s)) / top))
		chart.draw_polyline(pts, lines[i][2], 2.0)
		chart.draw_string(font, Vector2(r.position.x + 10 + i * 220, r.position.y + 14), lines[i][0], HORIZONTAL_ALIGNMENT_LEFT, -1, 12, lines[i][2])
	var cx := r.position.x + r.size.x * day / duration
	chart.draw_line(Vector2(cx, r.position.y), Vector2(cx, r.end.y), C_CAUTION, 1.0)
	if end.depleted.has("FOOD"):
		var fx: float = r.position.x + r.size.x * end.depleted.FOOD / duration
		chart.draw_string(font, Vector2(fx + 4, r.end.y - 8), "food store empty, day %.0f" % end.depleted.FOOD, HORIZONTAL_ALIGNMENT_LEFT, -1, 12, C_BAD)

# ------------------------------------------------------------------------------------------------ checks and stills

static func _close(a, b) -> bool:
	if a == null or b == null:
		return a == b
	if a is Dictionary:
		return b is Dictionary and a.size() == b.size() and a.keys().all(func(k): return b.has(k) and _close(a[k], b[k]))
	return absf(float(a) - float(b)) <= 1e-6 * maxf(1.0, absf(float(b)))

func check_life_support() -> void:
	var out := []
	# 1 The module's checkpoints, scenario by scenario.
	var bad := []
	for sc in data.scenarios:
		var st := start(sc.params)
		for ref in sc.checkpoints:
			run_to(st, sc.params, float(ref.day))
			for k in ref:
				if not _close(st[k], ref[k]):
					bad.append([sc.id, ref.day, k])
	out.append({"id": "life_support_reproduces_module", "ok": bad.is_empty() and data.scenarios.size() == 4, "actual": {"bad": bad.slice(0, 5)},
		"note": "the GDScript step reproduces life_support.py at days 0, 1, 3, 365.25, 1092, 1093, 2191.5 for the owner, stress and sandbox scenarios"})
	# 2 The owner's 41 results, as the module computed them, are within the owner's values.
	var owner_bad: Array = data.owner_checks.filter(func(c): return not _close(c.computed, c.expected))
	out.append({"id": "life_support_owner_results", "ok": owner_bad.is_empty() and data.owner_checks.size() == 11, "actual": {"bad": owner_bad.map(func(c): return c.id)},
		"note": "41 food 20,052.225 kg (shortfall 10,052.225), 72 h O2 30.24 / CO2 36 / water 149.76 / rations 65.88 kg, waste 10,957.5, makeup 4,558.32 / 911.664 kg"})
	# 3 Every day of every scenario conserves each resource.
	var worst := 0.0
	for sc in data.scenarios:
		var st := start(sc.params)
		while st.day < duration - 1e-12:
			run_to(st, sc.params, minf(st.day + 1.0, duration))
			for v in ledger_errors(st).values():
				worst = maxf(worst, absf(v))
	out.append({"id": "life_support_mass_ledger", "ok": worst < 1e-6, "actual": {"worst_kg": worst},
		"note": "need = Garden + recovered + drawn + required + deficit and store = initial − drawn, every day, every scenario"})
	# 4 Labels: OPEN stays OPEN, a changed input is HYPOTHETICAL, a Garden / O2-recovery share is UNCLOSED, a deficit is shown.
	var lab := []
	var cases := [defaults(), {"consumers": 12, "water_recovery": 0.0, "o2_recovery": 0.0, "garden_food": 0.0, "extra": {}},
		{"consumers": 5, "water_recovery": 0.9, "o2_recovery": 0.5, "garden_food": 0.3, "extra": {"O2": 500.0, "WATER_MAKEUP": 2000.0}}]
	for c in cases:
		p = c
		day = duration
		rebuild()
		var t := text.text
		var st := run_to(start(p), p, day)
		if not ("STUDY" in t and "not canon" in t):
			lab.append([c, "notice"])
		if not c.extra.has("O2") and not "OPEN (38 S03" in t:
			lab.append([c, "o2 open"])
		if (c.garden_food > 0.0 or c.o2_recovery > 0.0) and not "UNCLOSED source" in t:
			lab.append([c, "unclosed"])
		if st.deficit.FOOD > 0.0 and not "DEFICIT" in t:
			lab.append([c, "deficit"])
		if c.consumers != 5 and not "HYPOTHETICAL" in t:
			lab.append([c, "hypothetical"])
	reset()
	out.append({"id": "life_support_labels_honest", "ok": lab.is_empty(), "actual": {"bad": lab},
		"note": "OPEN stores show no number, changed inputs read HYPOTHETICAL, Garden and O2 recovery read UNCLOSED, the food deficit and empty day are shown"})
	var ok: bool = out.all(func(x): return x.ok)
	print("WF_GODOT_LIFE_SUPPORT ", JSON.stringify({"result": "PASS" if ok else "FAIL", "checks": out}))
	get_tree().quit(0 if ok else 1)

func capture(directory: String) -> void:
	DirAccess.make_dir_recursive_absolute(directory)
	var shots := [["owner_defaults", defaults()], ["stress_12", {"consumers": 12, "water_recovery": 0.0, "o2_recovery": 0.0, "garden_food": 0.0, "extra": {}}],
		["sandbox", {"consumers": 5, "water_recovery": 0.98, "o2_recovery": 0.5, "garden_food": 0.3, "extra": {"O2": 500.0, "WATER_MAKEUP": 2000.0}}]]
	for s in shots:
		p = s[1]
		day = 1500.0
		rebuild()
		for n in 3:
			await get_tree().process_frame
		get_viewport().get_texture().get_image().save_png(directory.path_join("life_support_%s.png" % s[0]))
	get_tree().quit()
