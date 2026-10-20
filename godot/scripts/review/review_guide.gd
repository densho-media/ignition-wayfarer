class_name WfReviewGuide
extends CanvasLayer
## U01: the development review guide over a scene (TODO U; not the final game UI). It shows what to do and what to expect, step by
## step, from a WfReviewSession: a step card with the checklist, the keys that work now as coloured chips (blue available, amber the
## key that moves the step on, grey leave), an "Expect" line, a "Last" line with the result of the last key or the reason it was
## refused, and the engineering detail muted on one line (I expands it, F1 hides the guide). It changes no ship, physics or route state.

static var pending := ""                     # the session the review menu asked for; the opened scene starts it and clears it

const C_NOW := Color("378ADD")
const C_NOW_TEXT := Color("042C53")
const C_NEXT := Color("EF9F27")
const C_NEXT_TEXT := Color("412402")
const C_EXIT := Color("444441")
const C_EXIT_TEXT := Color("D3D1C7")
const C_TITLE := Color("F1EFE8")
const C_BODY := Color("D3D1C7")
const C_MUTED := Color("888780")
const C_EXPECT := Color("9FE1CB")
const C_OK := Color("5DCAA5")
const C_BAD := Color("F09595")
const C_DONE := Color("5DCAA5")
const C_CURRENT := Color("85B7EB")
# Source-status badges (outlined, never filled, so they never read as keys). REAL PHYSICS (a formula fixture) shares DERIVED's colour.
const STATUS_COLORS := {"CANON": Color("97C459"), "DERIVED": Color("5DCAA5"), "REAL PHYSICS": Color("5DCAA5"), "WORKING": Color("85B7EB"),
	"PROTOTYPE": Color("AFA9EC"), "DIAGNOSTIC": Color("ED93B1"), "OPEN": Color("B4B2A9"), "HOLD": Color("F09595"), "STUDY": Color("EF9F27")}

var session: WfReviewSession
var index := 0
var complete := false
var expanded := false
var last_text := ""
var last_ok := true
var events: Array = []                        # [{step, event}] for the headless check

var card := PanelContainer.new()
var crumb := Label.new()
var step_title := Label.new()
var goal := Label.new()
var segments := HBoxContainer.new()
var badges := HFlowContainer.new()
var _labels_shown := ""
var checklist := VBoxContainer.new()
var bar := PanelContainer.new()
var chips := HFlowContainer.new()
var expect := Label.new()
var last := Label.new()
var detail := Label.new()

func _init(s: WfReviewSession) -> void:
	session = s
	layer = 20

func _ready() -> void:
	card.add_theme_stylebox_override("panel", _box(Color(0, 0, 0, 0.62), Color("5F5E5A")))
	card.position = Vector2(20, 20)
	card.custom_minimum_size = Vector2(440, 0)
	add_child(card)
	var col := VBoxContainer.new()
	col.add_theme_constant_override("separation", 6)
	card.add_child(col)
	crumb.add_theme_font_size_override("font_size", 13)
	crumb.add_theme_color_override("font_color", C_MUTED)
	var study := study_label()
	if study != "":
		var sl := Label.new()
		sl.text = study
		sl.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		sl.add_theme_font_size_override("font_size", 13)
		sl.add_theme_color_override("font_color", STATUS_COLORS["STUDY"])
		col.add_child(sl)
	col.add_child(crumb)
	step_title.add_theme_font_size_override("font_size", 22)
	step_title.add_theme_color_override("font_color", C_TITLE)
	col.add_child(step_title)
	goal.add_theme_font_size_override("font_size", 15)
	goal.add_theme_color_override("font_color", C_BODY)
	goal.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	goal.custom_minimum_size = Vector2(410, 0)
	col.add_child(goal)
	badges.add_theme_constant_override("h_separation", 6)
	badges.add_theme_constant_override("v_separation", 4)
	col.add_child(badges)
	segments.add_theme_constant_override("separation", 5)
	col.add_child(segments)
	col.add_child(HSeparator.new())
	checklist.add_theme_constant_override("separation", 2)
	col.add_child(checklist)
	bar.add_theme_stylebox_override("panel", _box(Color(0, 0, 0, 0.66), Color("5F5E5A")))
	add_child(bar)
	bar.set_anchors_and_offsets_preset(Control.PRESET_BOTTOM_WIDE)
	bar.offset_left = 20
	bar.offset_right = -20
	bar.offset_bottom = -20
	bar.grow_vertical = Control.GROW_DIRECTION_BEGIN
	var rows := VBoxContainer.new()
	rows.add_theme_constant_override("separation", 8)
	bar.add_child(rows)
	chips.add_theme_constant_override("h_separation", 8)
	chips.add_theme_constant_override("v_separation", 6)
	rows.add_child(chips)
	for l in [expect, last, detail]:
		l.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		l.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		rows.add_child(l)
	expect.add_theme_font_size_override("font_size", 15)
	expect.add_theme_color_override("font_color", C_EXPECT)
	last.add_theme_font_size_override("font_size", 15)
	detail.add_theme_font_size_override("font_size", 12)
	detail.add_theme_color_override("font_color", C_MUTED)
	_show_step()

static func _box(bg: Color, border: Color, radius := 10, pad := 14) -> StyleBoxFlat:
	var b := StyleBoxFlat.new()
	b.bg_color = bg
	b.border_color = border
	b.set_border_width_all(1)
	b.set_corner_radius_all(radius)
	b.set_content_margin_all(pad)
	return b

func _chip(key: String, what: String, role: String) -> Control:
	return chip(key, what, role)

## A key chip: the input on a filled cap (blue available, amber the key that moves things on, grey leave) and what it does.
## The one chip style of the guide bar, the lesson cards and the control panels (ACI-07).
static func chip(key: String, what: String, role: String) -> Control:
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 6)
	var cap := PanelContainer.new()
	var bg: Color = {"next": C_NEXT, "exit": C_EXIT}.get(role, C_NOW)
	var fg: Color = {"next": C_NEXT_TEXT, "exit": C_EXIT_TEXT}.get(role, C_NOW_TEXT)
	var sb := _box(bg, bg, 6, 0)
	sb.content_margin_left = 10
	sb.content_margin_right = 10
	sb.content_margin_top = 3
	sb.content_margin_bottom = 3
	cap.add_theme_stylebox_override("panel", sb)
	var k := Label.new()
	k.text = key
	k.add_theme_font_size_override("font_size", 16)
	k.add_theme_color_override("font_color", fg)
	cap.add_child(k)
	row.add_child(cap)
	if what == "":
		return row
	var w := Label.new()
	w.text = what
	w.add_theme_font_size_override("font_size", 14)
	w.add_theme_color_override("font_color", C_NEXT if role == "next" else (C_MUTED if role == "exit" else C_BODY))
	row.add_child(w)
	return row

## H03: the label of a STUDY package (`runtime-export --eye-layout r24`), or "" for the canonical package; shown on the menu and every card.
static func study_label() -> String:
	if not FileAccess.file_exists("res://generated/build_identity.json"):   # the export's own checks run before publication writes it
		return ""
	var identity = JSON.parse_string(FileAccess.get_file_as_string("res://generated/build_identity.json"))
	if identity is Dictionary and identity.get("study") is Dictionary:
		return str(identity["study"].get("label", "STUDY package"))
	return ""

static func status_family(status: String) -> String:
	var u := status.to_upper()
	for k in STATUS_COLORS:
		if u.begins_with(k):
			return k
	return "OPEN"

func _badge(status: String, what: String) -> Control:
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 5)
	var cap := PanelContainer.new()
	var c: Color = STATUS_COLORS[status_family(status)]
	var sb := _box(Color(0, 0, 0, 0), c, 4, 0)
	sb.content_margin_left = 6
	sb.content_margin_right = 6
	cap.add_theme_stylebox_override("panel", sb)
	var k := Label.new()
	k.text = status.to_upper()
	k.add_theme_font_size_override("font_size", 11)
	k.add_theme_color_override("font_color", c)
	cap.add_child(k)
	row.add_child(cap)
	var w := Label.new()
	w.text = what
	w.add_theme_font_size_override("font_size", 12)
	w.add_theme_color_override("font_color", C_MUTED)
	row.add_child(w)
	return row

func _show_step() -> void:
	var n := session.steps.size()
	crumb.text = "Review: %s   ·   %s" % [session.title, "complete" if complete else "step %d of %d" % [index + 1, n]]
	if complete:
		step_title.text = "Session complete"
		goal.text = "Every step passed. Tell Claude what looked or felt wrong, if anything. Esc returns to the review menu."
	else:
		step_title.text = session.steps[index].title
		goal.text = session.steps[index].goal
	for c in segments.get_children():
		c.queue_free()
	for i in n:
		var r := ColorRect.new()
		r.custom_minimum_size = Vector2(34, 6)
		r.color = C_DONE if (complete or i < index) else (C_CURRENT if i == index else Color("5F5E5A"))
		segments.add_child(r)
	_refresh_checklist()

func _refresh_checklist() -> void:
	for c in checklist.get_children():
		c.queue_free()
	for i in session.steps.size():
		var l := Label.new()
		var state := "done" if (complete or i < index) else ("now" if i == index else "todo")
		var mark: String = {"done": "✓", "now": "▸", "todo": "○"}[state]
		var extra := session.progress(i) if state == "now" else ""
		l.text = "%s  %s%s" % [mark, session.steps[i].title, ("   " + extra) if extra != "" else ""]
		l.add_theme_font_size_override("font_size", 14)
		l.add_theme_color_override("font_color", {"done": C_DONE, "now": C_CURRENT, "todo": C_MUTED}[state])
		checklist.add_child(l)

func feedback(text: String, ok := true) -> void:
	last_text = text
	last_ok = ok

func _process(dt: float) -> void:
	session.tick(dt)
	if not complete and session.done(index):
		var r := session.result(index)
		feedback(r if r != "" else "Done: " + session.steps[index].title, true)
		events.append({"step": index, "event": "done"})
		index += 1
		complete = index >= session.steps.size()
		_show_step()
	elif not complete and session.progress(index) != "":
		_refresh_checklist_progress()
	var ks: Array = [[WfInput.label("ui.cancel"), "back to the review menu", "exit"]] if complete else session.keys(index)
	if session.details() != "":
		ks = ks + [[WfInput.label("ui.details"), "hide details" if expanded else "details", "exit"]]
	ks = ks + [[WfInput.label("ui.guide"), "hide guide", "exit"]]
	if str(ks) != _keys_shown:                # rebuild the chips only when the available keys change
		_keys_shown = str(ks)
		for c in chips.get_children():
			c.queue_free()
		var lead := Label.new()
		lead.text = "Now you can"
		lead.add_theme_font_size_override("font_size", 13)
		lead.add_theme_color_override("font_color", C_MUTED)
		chips.add_child(lead)
		for k in ks:
			chips.add_child(_chip(k[0], k[1], k[2]))
	expect.text = "" if complete else "Expect:  " + session.steps[index].expect
	expect.visible = not complete
	last.text = ("✓  " if last_ok else "✗  ") + last_text if last_text != "" else ""
	last.add_theme_color_override("font_color", C_OK if last_ok else C_BAD)
	last.visible = last_text != ""
	var lb: Array = [] if complete else session.labels(index)
	if str(lb) != _labels_shown:              # rebuild the badges only when the shown statuses change
		_labels_shown = str(lb)
		for c in badges.get_children():
			c.queue_free()
		for l in lb:
			badges.add_child(_badge(str(l[0]), str(l[1])))
	badges.visible = not lb.is_empty()
	var d := session.details()
	detail.text = d if expanded else d.replace("\n", "  ·  ").left(170) + ("…" if d.length() > 170 else "")
	detail.visible = d != ""

var _progress_shown := ""
var _keys_shown := ""
func _refresh_checklist_progress() -> void:
	var p := session.progress(index)
	if p != _progress_shown:
		_progress_shown = p
		_refresh_checklist()

## Headless checks: send key k (press and release) through the viewport, so the guide's on_key and the scene both see it.
func press(k: Key, shift := false) -> void:
	for down in [true, false]:
		var ev := InputEventKey.new()
		ev.keycode = k
		ev.pressed = down
		ev.shift_pressed = shift
		get_viewport().push_input(ev)

func _input(e: InputEvent) -> void:
	# ACI-07/10: keys, controller and bound mouse buttons; a session sees the default key of the action the input triggers.
	if not WfInput.pressed(e):
		return
	if e.is_action_pressed("ui.guide"):
		card.visible = not card.visible
		bar.visible = card.visible
		get_viewport().set_input_as_handled()
		return
	if e.is_action_pressed("ui.details") and session.details() != "":
		expanded = not expanded
		get_viewport().set_input_as_handled()
		return
	if not complete:
		var k: int = WfInput.canonical_key(e)
		var f := session.on_key(k, index) if k != KEY_NONE else []
		if not f.is_empty():
			feedback(f[0], f[1])
