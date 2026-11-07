class_name WfKeyText
## Key prompts in HUD text as coloured key chips, the convention of the review guide (review_guide.gd): amber for the key that moves
## the step on, blue for the keys that also work now. Scenes write plain text with "[KEY]" tokens (WfInput labels in brackets);
## rich() turns every token into a chip and escapes every other bracket, so a label never parses as a BBCode tag.

const ROLES := {"next": [WfReviewGuide.C_NEXT, WfReviewGuide.C_NEXT_TEXT], "now": [WfReviewGuide.C_NOW, WfReviewGuide.C_NOW_TEXT]}

static var _re: RegEx = null

static func _escape(s: String) -> String:
	return s.replace("[", "\u0001").replace("]", "[rb]").replace("\u0001", "[lb]")

## Plain HUD text -> BBCode with each "[KEY]" token as a chip of the given role ("next" amber, "now" blue).
static func rich(text: String, role := "next") -> String:
	if _re == null:
		_re = RegEx.create_from_string("\\[([^\\[\\]\\n]{1,24})\\]")
	var c: Array = ROLES.get(role, ROLES["next"])
	var out := ""
	var i := 0
	for m in _re.search_all(text):
		out += _escape(text.substr(i, m.get_start() - i))
		# thin spaces outside the chip keep neighbouring chips and brackets apart; the chip text has no outline (dark on colour)
		out += "\u2009[outline_size=0][bgcolor=%s][color=%s] %s [/color][/bgcolor][/outline_size]\u2009" % [c[0].to_html(false),
			c[1].to_html(false), _escape(m.get_string(1))]
		i = m.get_end()
	return out + _escape(text.substr(i))

## A HUD text block that can show key chips: a RichTextLabel that sizes to its text like a Label.
static func label(font_size: int, color := Color.WHITE, wrap := true) -> RichTextLabel:
	var l := RichTextLabel.new()
	l.bbcode_enabled = true
	l.fit_content = true
	l.scroll_active = false
	l.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART if wrap else TextServer.AUTOWRAP_OFF
	l.mouse_filter = Control.MOUSE_FILTER_IGNORE
	l.add_theme_font_size_override("normal_font_size", font_size)
	l.add_theme_color_override("default_color", color)
	l.add_theme_color_override("font_outline_color", Color(0, 0, 0, 0.85))
	l.add_theme_constant_override("outline_size", 4)
	return l
