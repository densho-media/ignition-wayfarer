class_name WfEquipment
extends RefCounted
## SYS-001 (Phase 0 proof, `#interior-systems` / `-- --systems`): one piece of real equipment in the walk that operates an engineering
## state. The ring A sector 3 ECLSS bay (the package's binding) houses the ring's CO2-removal unit (WfCabinAir). Ops at the bay isolates
## or restores the unit through the model's own transitions; the bay's status board and the HUD line show the model's readout. This is
## the interaction and display layer only: the numbers, transitions and bands all come from the package (src/wayfarer/cabin_air.py).
## The default Explore Interior start does not create it.
## Phase 1 (DS-1): a small registry of interaction points on real exported nodes: the bay (the model's binding) and any point a scenario
## adds (the sector 2 workbench). Each point is a node, a ring and a reach; what an action there means is the caller's (the scenario's).

const TIMELAPSE := 60.0          # PROTOTYPE display: simulated seconds per real second (shown on the board)
const BAND_COLOURS := {"NOMINAL": Color(0.45, 0.85, 0.55), "ABOVE_TARGET": Color(0.95, 0.80, 0.35), "CONTROL": Color(0.98, 0.55, 0.25),
	"DEGRADED": Color(0.98, 0.40, 0.30), "DANGER": Color(1.0, 0.25, 0.25)}

var air: WfCabinAir = null
var binding := {}
var mesh: MeshInstance3D = null
var board := Label3D.new()
var host: Node = null
var timelapse := TIMELAPSE
var paused := false               # the scenario's pause rule stops the model's clock (walking and the rings keep real time)
var operations := 0
var points := {}                  # id -> {mesh, ring, reach}: "bay" plus the scenario's points
var by_source := {}
var by_name_ref := {}

func _init(by_name: Dictionary, manifest: Dictionary, owner: Node) -> void:
	host = owner
	air = WfCabinAir.load_package()
	if air == null:
		push_warning("SYS-001: wf_cabin_air.json is not in the package; run runtime-export")
		return
	binding = air.doc["binding"]
	by_name_ref = by_name
	for r in manifest.get("nodes", []):
		by_source[str(r.get("source_name", ""))] = str(r.get("node", ""))
	if not add_point("bay", str(binding["node"]), float(binding["reach_m"]), str(binding["ring"])):
		return
	mesh = points["bay"]["mesh"]
	mount_display()
	update()

## DS-O10 (2026-11-14): the bay's status display is a fixed panel mounted on the bay's face at eye level, like a rack's own display, not
## floating text. Its bottom edge is 0.95 m above the deck and it grows upwards to just under the eyes (about 1.43 m; the walk camera's
## eye is 1.47 m); its left edge is the bay's middle. A trainee who stands at the bay and looks level sees it just under and right of the centre
## of the screen: on an upright phone between the HUD's goal box, the Map and ? row and the touch buttons, clear of all of them. Short lines keep it narrow (about 0.5-0.65 m). A dark screen behind the text;
## capitals about 31 mm (DISPLAY_EM). The same size on every device (a real panel does not resize). It rides the ring with the bay.
## Presentation only: a Label3D and a quad, no ship geometry. All lengths in metres, in the bay mesh's frame.
const DISPLAY_EM := 0.044            # PROTOTYPE display: the em height (pixel_size x font_size); capitals about 31 mm
const DISPLAY_TILT_DEG := 0.0        # flush with the face (it is at eye level)
const DISPLAY_BASE := 0.95           # the panel's bottom edge above the deck (PROTOTYPE, chest height)
const DISPLAY_PROUD := 0.03          # in front of the bay face
const DISPLAY_PAD := 0.025
var screen := Node3D.new()
var screen_back := MeshInstance3D.new()

func mount_display() -> void:
	board.font_size = 48
	board.pixel_size = DISPLAY_EM / 48.0
	board.outline_size = 4
	board.outline_modulate = Color(0.0, 0.0, 0.0, 0.85)
	board.billboard = BaseMaterial3D.BILLBOARD_DISABLED
	board.double_sided = false
	board.no_depth_test = false
	board.horizontal_alignment = HORIZONTAL_ALIGNMENT_LEFT
	board.vertical_alignment = VERTICAL_ALIGNMENT_BOTTOM
	var quad := QuadMesh.new()
	screen_back.mesh = quad
	var mat := StandardMaterial3D.new()
	mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	mat.albedo_color = Color(0.025, 0.035, 0.05)
	screen_back.material_override = mat
	screen.add_child(screen_back)
	screen.add_child(board)
	mesh.add_child(screen)                     # rides the ring with the bay
	var box := mesh.get_aabb()
	var up := inward(mesh)
	var ax := 0                                # the face normal: the box's thinnest axis that is not up
	for i in 3:
		if absf(up[i]) < 0.5 and (absf(up[ax]) >= 0.5 or box.size[i] < box.size[ax]):
			ax = i
	var n := Vector3.ZERO
	n[ax] = -signf(box.get_center()[ax])       # towards the sector's centre line (the aisle)
	var right := up.cross(n).normalized()      # the reader looks along -n with up overhead: their right is (-n) x up
	var t := deg_to_rad(DISPLAY_TILT_DEG)
	var z := (n * cos(t) - up * sin(t)).normalized()
	var y := (up * cos(t) + n * sin(t)).normalized()
	var face := box.get_center() + n * (0.5 * absf(box.size[ax]) + DISPLAY_PROUD)
	var deck := minf(box.position.dot(up), box.end.dot(up))               # the bay stands on the deck
	var base := up * (deck + DISPLAY_BASE - box.get_center().dot(up))
	screen.transform = Transform3D(Basis(right, y, z), face + base - right * 0.02)

func inward(m: MeshInstance3D) -> Vector3:
	var box := m.get_aabb()
	var a := above(m, 0.0) - box.get_center()
	return a.normalized() if a.length() > 0.0 else Vector3.UP

## The screen behind the text, sized to it; the panel's bottom-left corner is the screen node's origin.
func fit_display() -> void:
	var b := board.get_aabb()
	board.position = Vector3(DISPLAY_PAD - b.position.x, DISPLAY_PAD - b.position.y, 0.004)
	(screen_back.mesh as QuadMesh).size = Vector2(b.size.x + 2.0 * DISPLAY_PAD, b.size.y + 2.0 * DISPLAY_PAD)
	screen_back.position = Vector3(0.5 * b.size.x + DISPLAY_PAD, 0.5 * b.size.y + DISPLAY_PAD, 0.0)

## Above a ring mesh in spin gravity: towards the ring's spin axis from its centre, past its top, by gap metres, in the mesh's frame.
func above(m: MeshInstance3D, gap: float) -> Vector3:
	var box := m.get_aabb()
	var g := m.global_transform * box.get_center()
	var frames = host.get("frames")
	if frames is Dictionary:
		for id in frames:
			var f: Dictionary = frames[id]
			if id != "STATIONARY" and (f["node"] as Node).is_ancestor_of(m):
				var piv: Node3D = f["node"]
				var c := piv.global_transform.affine_inverse() * g
				var ax: Vector3 = (f["axis"] as Vector3).normalized()
				var inward := -(c - ax * c.dot(ax)).normalized()
				var local_in := (m.global_transform.basis.inverse() * (piv.global_transform.basis * inward)).normalized()
				var half := 0.5 * absf(box.size.dot(local_in.abs()))
				return box.get_center() + local_in * (half + gap)
	return box.get_center() + Vector3(0, box.size.y * 0.5 + gap, 0)

## A named interaction point on an exported node (by its Blender source name). false if the node is not in the package.
func add_point(id: String, node: String, reach: float, ring: String) -> bool:
	var m := WfLearning._mesh(by_name_ref.get(by_source.get(node, node)))
	if m == null:
		push_warning("SYS-001: equipment node %s not in the package" % node)
		return false
	points[id] = {"mesh": m, "ring": ring, "reach": reach, "node": node}
	return true

func ready() -> bool:
	return air != null and mesh != null and air.verified

## A point's centre in the walking body's frame (the same rule as WfLearning.centre: a ring's meshes ride its spinning pivot).
func centre(id := "bay") -> Vector3:
	var m: MeshInstance3D = points[id]["mesh"]
	return to_body(m.global_transform * m.get_aabb().get_center(), m)

## A world point on the ring (for example the board's) in the walking body's frame.
func to_body(g: Vector3, on: Node = null) -> Vector3:
	if on == null:
		on = mesh
	var frames = host.get("frames")
	if frames is Dictionary:
		for id in frames:
			var f: Dictionary = frames[id]
			if id != "STATIONARY" and (f["node"] as Node).is_ancestor_of(on):
				var piv: Node3D = f["node"]
				return piv.get_parent().global_transform * (f["rest"] + piv.global_transform.affine_inverse() * g)
	return g

func in_reach(p: Vector3, zone: String, id := "bay") -> bool:
	if not ready() or not points.has(id):
		return false
	return zone == str(points[id]["ring"]) and p.distance_to(centre(id)) <= float(points[id]["reach"])

## The point in reach ("" none), the bay first.
func point_in_reach(p: Vector3, zone: String) -> String:
	for id in points:
		if in_reach(p, zone, id):
			return id
	return ""

## The operation Ops would request now (the Phase 0 proof: the unit's operating state only).
func next_op() -> String:
	return "isolate" if air.mode == "RUNNING" else "restore"

func op_label() -> String:
	return "isolate CO2 unit" if next_op() == "isolate" else "restore CO2 unit"

## Ops at the bay: ask the model for the operation; the model decides (refusals come back as text).
func operate() -> String:
	return request(next_op())

## Any model operation on the trainee's behalf (the caller checked the trainee is at the right point). "" refusal-free messages.
func request(op: String) -> String:
	var r := air.operate(op)
	operations += 1
	update()
	if r != "":
		return "ECLSS: refused. " + r
	return "ECLSS: " + str({
		"isolate": "CO2-removal unit ISOLATED (powered off and valved out for maintenance). Nothing removes ring A's CO2 now.",
		"restore": "CO2-removal unit RUNNING. Air flows through the bed again." if air.removing() else "CO2-removal unit RUNNING.",
		"take_spare": "spare fan taken from the workbench.",
		"install_spare": "spare fan installed. The unit stays isolated until it is restored."}.get(op, op + " done."))

func step(dt: float) -> void:
	if ready() and not paused:
		air.step(dt * timelapse)

func _hm(h) -> String:
	if h == null:
		return "-"
	var mins := int(round(float(h) * 60.0))
	return "%d h %02d min" % [mins / 60, mins % 60]

## The board's text: only what the model reads out.
func text() -> String:
	if air == null:
		return ""
	if not air.verified:
		return "RING A CO2 MODEL\nREFERENCE CHECK FAILED\n" + str(air.errors[0])
	var r := air.readout()
	var trend := "%+.3f %%/h" % (100.0 * float(r["dxdt_per_h"]))
	var limit := "Limit %.1f %%: %s" % [100.0 * float(air.p["co2_max"]),
		"in " + _hm(r["hours_to_control_limit"]) if r["hours_to_control_limit"] != null else "not approaching"]
	var unit: String = {"OPERATING": "Unit RUNNING", "RUNNING_NOT_REMOVING": "Unit RUNNING · removal 0", "ISOLATED_FAULT": "Unit ISOLATED",
		"ISOLATED_READY": "Unit ISOLATED · ready"}[r["status"]]
	return "RING A CABIN CO2\nSIMULATION x%d%s\n%.3f %%  ·  %.2f kPa\ntrend %s\n%s\n%s\n%s" % [int(timelapse), " (paused)" if paused else "",
		100.0 * float(r["x"]), float(r["pp_kpa"]), trend, unit, str(r["band"]).replace("_", " "), limit]

func update() -> void:
	if mesh == null or air == null:
		return
	board.text = text()
	board.modulate = BAND_COLOURS.get(str(air.readout()["band"]), Color.WHITE) if air.verified else Color(1, 0.3, 0.3)
	fit_display()

## The HUD prompt line while the bay is in reach.
func prompt(key_text: String) -> String:
	var r := air.readout()
	return "%s %s  ·  CO2 %.3f %% (%s)" % [key_text, op_label(), 100.0 * float(r["x"]), air.band_meaning(str(r["band"])) if r["band"] != "NOMINAL" else "within the control band"]

## A goal line for the HUD while this equipment leads the start ("" keeps the walk's own).
func goal_text() -> String:
	return ""

## The browser/headless record (window.wayfarerWalk.systems).
func record() -> Dictionary:
	if air == null:
		return {}
	var r := air.readout()
	return {"verified": air.verified, "mode": air.mode, "fan": air.fan, "spare": air.spare, "status": r["status"],
		"x": snappedf(float(r["x"]), 1e-7), "dxdt_per_h": snappedf(float(r["dxdt_per_h"]), 1e-9), "band": r["band"],
		"t_s": snappedf(air.t_s, 0.01), "operations": operations, "scale": timelapse, "paused": paused, "board": board.text}
