class_name WfAirflow
extends WfEquipment
## SYS-002 demo (Deadship Phase 2A, `-- --airflow`, #interior-airflow): ring A's air by compartment (WfRingAir) in the walk. The walk's
## own door mechanisms are the connections: a CIRC door's leaf off its seat is an open edge, seated is closed. The model holds no door state
## of its own; each frame it is told what the walk's leaves are doing, so a refused door operation (the doorway occupied) changes nothing.
## The one new interaction is Ops at the sector 3 ECLSS bay: the ring's ventilation fans on or off (the existing Ops binding and touch
## button). The bay's board, the HUD prompt and the ring map show the model's state; all numbers come from the package
## (src/wayfarer/ring_air.py). The default Explore Interior start and DS-1 never create it; DS-1 keeps its one well-mixed volume.

const AIR_TIMELAPSE := 120.0       # PROTOTYPE display: simulated seconds per real second (shown on the board)
const MAX_STEPS_PER_FRAME := 40

var ring: WfRingAir = null
var acc := 0.0
var dt_s := 10.0

func _init(by_name: Dictionary, manifest: Dictionary, owner: Node) -> void:
	super(by_name, manifest, owner)
	timelapse = AIR_TIMELAPSE
	ring = WfRingAir.load_package()
	if ring == null:
		push_warning("SYS-002: wf_ring_air.json is not in the package; run runtime-export")
		return
	dt_s = float(ring.doc["proof"]["dt_s"])
	sync_doors()
	update()

func ready() -> bool:
	return ring != null and ring.verified and mesh != null

## The walk's ring A door leaves -> the model's door edges (the leaf off its seat passes air).
func sync_doors() -> void:
	if ring == null:
		return
	var doors = host.get("circ_doors")
	for e in ring.edges:
		if str(e["kind"]) == "door" and doors.has(e["id"]):
			ring.set_edge(str(e["id"]), float(doors[e["id"]]["value"]) > 0.0)

func step(dt: float) -> void:
	if not ready():
		return
	sync_doors()
	if paused:
		return
	acc += dt * timelapse
	var n := 0
	while acc >= dt_s and n < MAX_STEPS_PER_FRAME:
		ring.step(dt_s)
		acc -= dt_s
		n += 1
	if n == MAX_STEPS_PER_FRAME:
		acc = 0.0                       # a long frame: drop the backlog rather than stall (display time only; the step stays exact)

func next_op() -> String:
	return "vent_off" if ring != null and ring.vent == "ON" else "vent_on"

func op_label() -> String:
	return "ventilation off" if next_op() == "vent_off" else "ventilation on"

func operate() -> String:
	return request(next_op())

func request(op: String) -> String:
	if not ready():
		return "RING A AIR: the model is unavailable."
	operations += 1
	ring.set_vent(op == "vent_on")
	update()
	if ring.vent == "OFF":
		return "VENTILATION OFF: the intermodule fans stop. Only open doors join compartments now; a closed door isolates."
	return "VENTILATION ON: each bulkhead's duct pair exchanges air again, closed doors or not."

## A compartment's short name and value, for the board and the map.
func node_text(q: Dictionary) -> String:
	return "%s %.3f %%%s" % [q["id"], 100.0 * float(q["x"]), "  isolated" if q["isolated"] else ""]

func text() -> String:
	if ring == null:
		return ""
	if not ring.verified:
		return "RING A AIR MODEL\nREFERENCE CHECK FAILED\n" + str(ring.errors[0])
	var r := ring.readout()
	var rows := []
	for q in r["nodes"]:
		rows.append(node_text(q) + (" · unit" if q["id"] == ring.ids[int(ring.p["removal"])] else ""))
	return "RING A AIR BY COMPARTMENT\nSIMULATION x%d · PROTOTYPE exchange\nVentilation %s · doors open %d/9 · %d group%s\n%s" % [int(timelapse),
		r["vent"], open_doors(), r["groups"], "" if r["groups"] == 1 else "s", "\n".join(rows)]

func open_doors() -> int:
	var n := 0
	for e in ring.edges:
		if str(e["kind"]) == "door" and bool(ring.open[e["id"]]):
			n += 1
	return n

func update() -> void:
	if mesh == null or ring == null:
		return
	sync_doors()
	board.text = text()
	board.modulate = Color(0.75, 0.88, 1.0) if ring.verified else Color(1, 0.3, 0.3)

func prompt(key_text: String) -> String:
	return "%s %s  ·  %s" % [key_text, op_label(), "the fans join every compartment through closed doors" if ring.vent == "ON" else "only open doors join compartments"]

func goal_text() -> String:
	if not ready():
		return ""
	var r := ring.readout()
	return "RING A AIR (simulation, PROTOTYPE exchange). The map colours each compartment by its CO2. Ventilation %s, %d group%s. At the sector 3 ECLSS bay %s switches the ventilation; %s opens or closes a door." % [
		r["vent"], r["groups"], "" if r["groups"] == 1 else "s", host.call("key", "exc.ops"), host.call("key", "exc.use")]

func record() -> Dictionary:
	if ring == null:
		return {}
	var r := ring.readout()
	var nodes := {}
	for q in r["nodes"]:
		nodes[q["id"]] = {"x": snappedf(float(q["x"]), 1e-7), "group": q["group"], "isolated": q["isolated"], "removal": q["removal_reaches"]}
	return {"model": "ring_air", "verified": ring.verified, "vent": ring.vent, "groups": r["groups"], "doors_open": open_doors(),
		"nodes": nodes, "t_s": snappedf(ring.t_s, 0.01), "ledger_kg": ring.ledger_error(), "operations": operations, "scale": timelapse,
		"board": board.text}
