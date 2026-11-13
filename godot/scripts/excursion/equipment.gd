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
	board.pixel_size = 0.0022
	board.font_size = 32
	board.outline_size = 10
	board.billboard = BaseMaterial3D.BILLBOARD_ENABLED   # faces the viewer, upright in their view (world Y is not up in a spinning ring)
	board.no_depth_test = false
	board.horizontal_alignment = HORIZONTAL_ALIGNMENT_LEFT
	mesh.add_child(board)                      # rides the ring with the bay
	board.position = above(mesh, 0.35)
	update()

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
	var limit := "Control limit %.1f %%: %s" % [100.0 * float(air.p["co2_max"]),
		"in " + _hm(r["hours_to_control_limit"]) + " from now" if r["hours_to_control_limit"] != null else "not approaching"]
	var unit: String = {"OPERATING": "Unit RUNNING", "RUNNING_NOT_REMOVING": "Unit RUNNING · removal 0", "ISOLATED_FAULT": "Unit ISOLATED",
		"ISOLATED_READY": "Unit ISOLATED · ready"}[r["status"]]
	return "RING A CABIN CO2\nSIMULATION x%d%s\n%.3f %%  ·  %.2f kPa\ntrend %s\n%s  ·  %s\n%s" % [int(timelapse), " (paused)" if paused else "",
		100.0 * float(r["x"]), float(r["pp_kpa"]), trend, unit, str(r["band"]).replace("_", " "), limit]

func update() -> void:
	if mesh == null or air == null:
		return
	board.text = text()
	board.modulate = BAND_COLOURS.get(str(air.readout()["band"]), Color.WHITE) if air.verified else Color(1, 0.3, 0.3)

## The HUD prompt line while the bay is in reach.
func prompt(key_text: String) -> String:
	var r := air.readout()
	return "%s %s  ·  CO2 %.3f %% (%s)" % [key_text, op_label(), 100.0 * float(r["x"]), air.band_meaning(str(r["band"])) if r["band"] != "NOMINAL" else "within the control band"]

## The browser/headless record (window.wayfarerWalk.systems).
func record() -> Dictionary:
	if air == null:
		return {}
	var r := air.readout()
	return {"verified": air.verified, "mode": air.mode, "fan": air.fan, "spare": air.spare, "status": r["status"],
		"x": snappedf(float(r["x"]), 1e-7), "dxdt_per_h": snappedf(float(r["dxdt_per_h"]), 1e-9), "band": r["band"],
		"t_s": snappedf(air.t_s, 0.01), "operations": operations, "scale": timelapse, "paused": paused, "board": board.text}
