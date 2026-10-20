class_name WfSolarChart
extends RefCounted
## SPACE Stage 2 (S&E 55 SPACE-015/017/019/030; Art Style Objects & Tech row 19): the Solar System chart of the Space Navigator.
## It draws the rig's `space_navigator` references (Sun, eight planets, the Kuiper Belt's main region; NASA fact sheets) around the Sun:
## one guide circle at each mean distance, the perihelion-aphelion band, and each body on ONE schematic layout ray. The ray is not a
## position at any date: no epoch, longitude or ephemeris exists (25!F14:F15 OPEN), so the arrangement is SCHEMATIC and nothing moves
## with the selected mission time. Wayfarer has no marker here (its Sun-relative position is UNKNOWN, SPACE-010).
## Two display modes (SPACE-007, C-012): ANALYTICAL draws distances and sizes to scale (bodies far below a pixel get a fixed glyph,
## labelled so); PRESENTATION compresses distance by a square root and enlarges bodies by a log rule, with the disclosure always on.
## Both transforms are named and invertible and touch only the drawing.

const MODES := ["ANALYTICAL", "PRESENTATION"]
const PAGES := ["WHAT", "WHY", "SHOW ME"]
const GLYPH_PX := 3.0
const PICK_PX := 14.0

var nav                              # WfSpaceNavigator
var reg: Dictionary = {}
var bodies: Array = []
var regions: Array = []
var refs: Dictionary = {}
var mode := "ANALYTICAL"
var zoom := 1                        # index into reg.zooms (OUTER by default: Sun to Neptune)
var selected := "WAYFARER"           # WAYFARER, a body id or a region id
var page := -1                       # card page, -1 closed
var highlight := ""
var glyphs := {}                     # id -> Vector2 drawn this layout (checks, picking)
var box := Rect2()

func _init(n, rig: Dictionary) -> void:
	nav = n
	reg = rig.get("space_navigator", {})
	bodies = reg.get("bodies", [])
	regions = reg.get("regions", [])
	refs = reg.get("references", {})

func ok() -> bool:
	return not bodies.is_empty()

func ids() -> Array:
	var out := ["WAYFARER"]
	for b in bodies:
		out.append(b.id)
	for r in regions:
		out.append(r.id)
	return out

func extent_au() -> float:
	return float(reg.zooms[zoom].extent_au)

# ------------------------------------------------------------------------------------------------------------------- transforms

func origin(r: Rect2) -> Vector2:
	return Vector2(r.position.x + 44.0, r.position.y + r.size.y * 0.58)

func span_px(r: Rect2) -> float:
	return r.size.x - 44.0 - 36.0

## Distance in AU -> px from the Sun, per mode (ANALYTICAL linear, PRESENTATION square root of a / extent).
func radius_px(a_au: float, r: Rect2) -> float:
	if mode == "PRESENTATION":
		return span_px(r) * sqrt(maxf(a_au, 0.0) / extent_au())
	return span_px(r) * a_au / extent_au()

func radius_inverse(px: float, r: Rect2) -> float:
	if mode == "PRESENTATION":
		return extent_au() * pow(px / span_px(r), 2.0)
	return extent_au() * px / span_px(r)

## Body size in px: ANALYTICAL true scale (then a fixed glyph below 1.5 px), PRESENTATION 3 + 2.4 log10(radius / 1000 km).
func size_px(radius_km: float, r: Rect2) -> Dictionary:
	if mode == "PRESENTATION":
		return {"px": 3.0 + 2.4 * log(radius_km / 1000.0) / log(10.0), "glyph": false}
	var px := radius_px(radius_km / float(reg.au_km), r)
	return {"px": maxf(px, GLYPH_PX), "glyph": px < 1.5}

func disclosure() -> String:
	return str(reg.transforms[mode].disclosure)

# ------------------------------------------------------------------------------------------------------------------- layout

func layout(r: Rect2) -> void:
	box = r
	glyphs.clear()
	var o := origin(r)
	for b in bodies:
		var a := float(b.get("a_au", 0.0))
		if a <= extent_au() * 1.02:
			glyphs[b.id] = o + Vector2(radius_px(a, r), 0.0)

func pick(at: Vector2) -> String:
	var best := ""
	var d_best := PICK_PX
	for id in glyphs:
		var d: float = (glyphs[id] as Vector2).distance_to(at)
		if d < d_best:
			best = id
			d_best = d
	if best != "":
		return best
	var a := radius_inverse(at.distance_to(origin(box)), box)
	for g in (regions if nav.on("KUIPER") else []):
		if a >= float(g.inner_au) and a <= float(g.outer_au):
			return g.id
	return ""

func select(id: String) -> void:
	selected = id
	page = -1
	highlight = ""

func cycle(step: int) -> void:
	var all := ids()
	select(all[(all.find(selected) + step + all.size()) % all.size()])

## I on the SOLAR scale: WHAT -> WHY -> SHOW ME -> close. SHOW ME zooms to the object (Wayfarer: back to the journey).
func next_page() -> void:
	page = page + 1 if page < 2 else -1
	highlight = selected if page == 2 else ""
	if page == 2:
		if selected == "WAYFARER":
			nav.scale = "JOURNEY"
			return
		var a := _au_of(selected)
		for i in reg.zooms.size():
			if a <= float(reg.zooms[i].extent_au) * 0.95:
				zoom = i
				break

func _au_of(id: String) -> float:
	for b in bodies:
		if b.id == id:
			return float(b.get("a_au", 0.0))
	for g in regions:
		if g.id == id:
			return float(g.outer_au)
	return 0.0

func _body(id: String) -> Dictionary:
	for b in bodies:
		if b.id == id:
			return b
	for g in regions:
		if g.id == id:
			return g
	return {}

static func _n(x: float, d := 1) -> String:
	return WfSpaceNavigator._num(x, d)

func _ref_line(ref: String) -> String:
	var r: Dictionary = refs.get(ref, {})
	return "Source: %s (updated %s, retrieved %s) · %s" % [r.get("title", ref), r.get("updated", "?"), r.get("retrieved", "?"), r.get("status", "")]

func card_text() -> String:
	if page < 0:
		return ""
	var head := "%s · %s" % [_title(selected), PAGES[page]]
	if selected == "WAYFARER":
		return head + "\n" + ["Position among the planets: UNKNOWN. Released for the ship: only the First Ignition DIAGNOSTIC 1D study, 6.970 AU traveled along local +X from the ignition point, which is not a distance from the Sun.",
			"The owner has not released the ignition epoch, the starting place relative to the Sun, the heading or dated ephemerides (25!F14 COORDINATE_FRAME_VALIDATED and F15 SOLAR_EPHEMERIDES_VALIDATED are OPEN). A dot on this chart would invent a place.",
			"SHOW ME: back to the mission journey, the only released path."][page]
	var b := _body(selected)
	if b.has("inner_au"):
		return head + "\n" + ["%s · regional guide, not an event position\n%s–%s AU from the Sun. %s\n%s" % [b.name, _n(b.inner_au, 0), _n(b.outer_au, 0), b.note, _ref_line(b.ref)],
			"%s\n(DRAFT wording, Tale review)" % b.why,
			"SHOW ME: the Kuiper region zoom, the band highlighted. No Kuiper event is placed. OPEN in 25_ROUTE_VALIDATION: %s." % kuiper_open_text()][page]
	if b.kind == "star":
		return head + "\n" + ["Sun · star · radius %s km\n%s\nThe chart's centre is a drawing choice, not a released coordinate frame." % [_n(b.radius_km, 0), _ref_line(b.ref)],
			"%s\n(DRAFT wording, Tale review)" % b.why, "SHOW ME: the inner planets zoom around it."][page]
	return head + "\n" + ["%s · planet · mean distance %s million km = %.3f AU (DERIVED with the IAU astronomical unit) · perihelion %.3f AU, aphelion %.3f AU · eccentricity %.3f · inclination %.1f° · period %s days · diameter %s km\n%s" % [
			b.name, _n(b.distance_1e6km, 1), b.a_au, b.perihelion_au, b.aphelion_au, b.eccentricity, b.inclination_deg, _n(b.period_days, 1), _n(b.diameter_km, 0), _ref_line(b.ref)],
		"%s\n(DRAFT wording, Tale review)" % b.why,
		"SHOW ME: %s's zoom with its distance band (perihelion to aphelion) highlighted. Its place on the band at any date is not drawn: that needs an epoch." % b.name][page]

## The route's OPEN Kuiper checks (25_ROUTE_VALIDATION rows the importer carries), named on the Kuiper card: nothing is placed until they PASS.
func kuiper_open() -> Array:
	var out := []
	if nav.route.ok():
		for v in nav.route.route.validation:
			if "KUIPER" in str(v.check_id) and v.result != "PASS":
				out.append(v)
	return out

func kuiper_open_text() -> String:
	var parts := kuiper_open().map(func(v): return "%s (row %d)" % [v.check_id, int(v.row)])
	return ", ".join(parts) if not parts.is_empty() else "no Kuiper check in the released route"

func _title(id: String) -> String:
	if id == "WAYFARER":
		return "WAYFARER"
	var b := _body(id)
	return str(b.get("name", id)).to_upper()

# ------------------------------------------------------------------------------------------------------------------- drawing

func draw(c: Control, r: Rect2, fs: int) -> void:
	layout(r)
	var o := origin(r)
	var pal: Dictionary = nav.pal
	var guide := Color(pal["structure"], 0.55)
	# Kuiper band (regional guide) under the orbits.
	for g in (regions if nav.on("KUIPER") else []):
		var r0 := radius_px(float(g.inner_au), r)
		var r1 := radius_px(float(g.outer_au), r)
		var hl: bool = highlight == g.id or selected == g.id
		c.draw_arc(o, (r0 + r1) / 2.0, -PI / 2.0, PI / 2.0, 96, Color(pal["structure_faint"], 0.42 if hl else 0.22), r1 - r0)
		for rr in [r0, r1]:
			_dashed_arc(c, o, rr, Color(pal["quiet"], 0.7))
		var label := "KUIPER BELT (main) %d–%d AU · regional guide, not an event position" % [int(g.inner_au), int(g.outer_au)]
		if o.x + r0 > r.end.x:
			label = "KUIPER BELT (main) %d–%d AU beyond the edge →" % [int(g.inner_au), int(g.outer_au)]
		nav._text(Vector2(r.end.x - 8, r.position.y + 68), label, pal["quiet"], fs - 1, HORIZONTAL_ALIGNMENT_RIGHT)
	var k := 0
	var last_x := -1e9
	var hidden := []
	for b in bodies:
		if not glyphs.has(b.id):
			continue
		var p: Vector2 = glyphs[b.id]
		var sel: bool = selected == b.id
		if b.kind == "planet" and nav.on("ORBITS"):
			var rq := radius_px(float(b.perihelion_au), r)
			var rQ := radius_px(float(b.aphelion_au), r)
			if rQ - rq >= 1.0:
				c.draw_arc(o, (rq + rQ) / 2.0, -PI / 2.0, PI / 2.0, 128, Color(pal["structure"], 0.32 if (sel or highlight == b.id) else 0.14), rQ - rq)
			c.draw_arc(o, p.x - o.x, -PI / 2.0, PI / 2.0, 128, Color(pal["player"], 0.9) if sel else guide, 1.5 if sel else 1.0)
		var sz := size_px(float(b.radius_km), r)
		var col: Color = pal["player"] if sel else (pal["text"] if b.kind == "planet" else pal["caution"].lerp(pal["text"], 0.5))
		if sz.glyph:
			c.draw_arc(p, sz.px, 0, TAU, 16, col, 1.2)
		else:
			c.draw_circle(p, sz.px, col)
		if sel:
			c.draw_arc(p, sz.px + 5.0, 0, TAU, 24, pal["player"], 1.0)
		# Labels alternate above and below; a body crowded within 30 px of the last labelled one is named in one cluster note instead.
		if p.x - last_x < 30.0 and not sel:
			hidden.append(b.name)
			continue
		nav._text(p + Vector2(0, (-10.0 - sz.px) if k % 2 == 0 else (18.0 + sz.px)), b.name, col, fs - 1, HORIZONTAL_ALIGNMENT_CENTER)
		last_x = p.x
		k += 1
	if not hidden.is_empty():
		nav._text(o + Vector2(0, 46), "also here: %s (= to zoom in)" % ", ".join(hidden), pal["quiet"], fs - 1)
	# Persistent disclosures (SPACE-015, Art row 19): amber, top-left, in every mode and zoom.
	nav._text(r.position + Vector2(10, 18), str(reg.schematic_notice), pal["caution"], fs + 1)
	nav._text(r.position + Vector2(10, 34), disclosure(), pal["caution"], fs - 1)
	nav._text(r.position + Vector2(10, 50), "Layout: every body on one ray from the Sun, not where it is on any date · no Wayfarer marker: position UNKNOWN", pal["quiet"], fs - 1)
	nav._text(Vector2(r.end.x - 8, r.position.y + 18), "zoom: %s (%s AU)" % [reg.zooms[zoom].title, _n(extent_au(), 1)], pal["quiet"], fs - 1, HORIZONTAL_ALIGNMENT_RIGHT)
	# A detached length comparison in ANALYTICAL only: a bar, anchored to nothing, never at the Sun.
	if mode == "ANALYTICAL" and nav.on("GRID"):
		var bar_au := 6.970320784 if extent_au() > 10.0 else 1.0
		var w := span_px(r) * bar_au / extent_au()
		var y := r.end.y - 30.0
		var x0 := r.end.x - 24.0 - w
		c.draw_line(Vector2(x0, y), Vector2(x0 + w, y), pal["quiet"], 2.0)
		for xx in [x0, x0 + w]:
			c.draw_line(Vector2(xx, y - 4), Vector2(xx, y + 4), pal["quiet"], 1.0)
		nav._text(Vector2(x0 + w, y - 8), ("length of the First Ignition path, 6.970 AU traveled (a length, not a place)" if bar_au > 1.0 else "1 AU"), pal["quiet"], fs - 1, HORIZONTAL_ALIGNMENT_RIGHT)

func _dashed_arc(c: Control, o: Vector2, radius: float, col: Color) -> void:
	var n := 48
	for i in n:
		if i % 2 == 0:
			var a0 := -PI / 2.0 + PI * i / n
			c.draw_arc(o, radius, a0, a0 + PI / n, 4, col, 1.0)
