class_name WfPagePanel
extends RefCounted
## Where a training page (a learning station, the Deadship tutorial) sits on any screen. One layout rule for every page, no separate
## mobile pages. Desktop: the right column, as before. Phone or tablet (WfInput.compact): the free band between the page's top row
## (Exit, Full screen, Map, ?) and the lowest controls (the touch buttons and the stick), across the width inside the safe area, with
## smaller type stepped down until the text fits; the scene hides its goal, prompt and map while a page is open (`open_any`), so the
## page covers no touch control and nothing covers the page. Closing the page brings the HUD back on the next frame.

const MARGIN := 8.0
const DESKTOP_FONT := [15, 16]
const COMPACT_FONTS := [[13, 14], [12, 13], [11, 12]]

## The page's place and type for this screen. desktop_w: the text width on a desktop.
static func place(panel: PanelContainer, text: RichTextLabel, sz: Vector2, desktop_w: float) -> void:
	if not panel.visible:
		return
	if not WfInput.compact():
		_font(text, DESKTOP_FONT)
		text.custom_minimum_size.x = desktop_w
		panel.custom_minimum_size = Vector2.ZERO
		panel.reset_size()
		panel.position = Vector2(sz.x - panel.size.x - 18.0, clampf(sz.y - panel.size.y - 18.0, 18.0, 262.0))   # a tall page moves up
		return
	var band := free_band(sz, panel)
	var inner := maxf(band.size.x - 32.0, 120.0)                          # the stylebox's content margins (14 px) and the border
	for f in COMPACT_FONTS:
		_font(text, f)
		text.custom_minimum_size.x = inner
		panel.custom_minimum_size = Vector2(band.size.x, 0.0)
		panel.reset_size()
		if panel.size.y <= band.size.y:
			break
	panel.position = band.position

## The screen band a page may use on a touch-first device: below the top row, above the touch buttons and the stick, inside the safe
## area (CSS env(safe-area-inset-*) from the web shell).
static func free_band(sz: Vector2, skip: Control = null) -> Rect2:
	var t = WfInput.touch
	var safe: Array = t.safe if t != null else [0.0, 0.0, 0.0, 0.0]
	var top := float(safe[1]) + 58.0 + MARGIN                           # wf_touch PAGE_ROW: the page's Exit and Full screen row
	var bottom := sz.y - float(safe[3]) - MARGIN
	if t != null:
		bottom = minf(bottom, sz.y - float(safe[3]) - 2.0 * float(t.STICK_R) - 2.0 * MARGIN)    # the stick's circle at rest
		for r in t.occupied():
			var rr := r as Rect2
			if skip != null and skip.is_visible_in_tree() and rr == skip.get_global_rect():
				continue                                                    # the page itself, when the scene names it as a panel
			if rr.get_center().y < sz.y * 0.3:
				top = maxf(top, rr.end.y + MARGIN)                          # the top row (Exit, Map, ?)
			else:
				bottom = minf(bottom, rr.position.y - MARGIN)               # the touch buttons
	var left := float(safe[0]) + MARGIN
	var right := sz.x - float(safe[2]) - MARGIN
	return Rect2(left, top, maxf(right - left, 120.0), maxf(bottom - top, 80.0))

static func _font(text: RichTextLabel, f: Array) -> void:
	text.add_theme_font_size_override("normal_font_size", int(f[0]))
	text.add_theme_font_size_override("bold_font_size", int(f[1]))
	text.add_theme_font_size_override("italics_font_size", int(f[0]))
