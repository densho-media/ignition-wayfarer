class_name WfRingAir
extends RefCounted
## SYS-002 ring A atmospheric connectivity (src/wayfarer/ring_air.py): the runtime copy of the engineering state. Ring A's nine pressure
## compartments hold CO2; open doors and running ventilation (IMV duct pairs with dampers) exchange it; the occupants add it and the unit in
## its compartment removes it. The step is the module's: y(t+dt) = exp(A dt) y(t), the exponential by scaling and squaring of the same
## fixed-order Taylor series in the same order of operations. It must reproduce the packaged checkpoints within the packaged tolerance
## (verify()) before anyone shows its state. Godot computes no parameter and knows nothing of games, scenarios, input or scores; the walk's
## doors are the authority for the door edges (the consumer passes their state in with set_edge). SIMULATION: PROTOTYPE values travel labelled.

var doc := {}
var p := {}
var ids: Array = []
var V: Array = []
var edges: Array = []
var N := 0
var t_s := 0.0
var m: Array = []
var m0 := 0.0
var generated := 0.0
var removed := 0.0
var vent := "ON"
var removal := "ON"
var occupants: Array = []
var open := {}                    # edge id -> bool (doors: the walk's leaf off its seat; IMV: the damper)
var cache := {}                   # dt -> propagator (flat, (N+3)^2), cleared on every change
var history: Array = []           # [t_s, kind, id, value] per change
var verified := false
var errors: Array = []

static func load_package(path := "res://generated/wf_ring_air.json") -> WfRingAir:
	if not FileAccess.file_exists(path):
		return null
	var a := WfRingAir.new()
	a.doc = JSON.parse_string(FileAccess.get_file_as_string(path))
	a.p = a.doc["params"]
	a.ids = a.p["ids"]
	a.V = a.p["V_m3"]
	a.edges = a.p["edges"]
	a.N = a.ids.size()
	a.errors = a.verify()
	a.verified = a.errors.is_empty()
	a.reset()
	return a

func n_mol(i: int) -> float:
	return float(p["P_Pa"]) * float(V[i]) / (float(p["R"]) * float(p["T_K"]))

## The module's start(): every compartment at x0 (< 0: the well-mixed steady state), doors closed, ventilation and dampers open, removing.
func reset(x0 := -1.0) -> void:
	if x0 < 0.0:
		x0 = float(p["well_mixed_x"])
	m = []
	m0 = 0.0
	for i in N:
		m.append(x0 * n_mol(i) * float(p["M_CO2"]))
	m0 = 0.0
	for v in m:
		m0 += v
	t_s = 0.0
	generated = 0.0
	removed = 0.0
	vent = "ON"
	removal = "ON"
	occupants = (p["occupants"] as Array).duplicate()
	open = {}
	for e in edges:
		open[e["id"]] = str(e["kind"]) != "door"
	cache = {}
	history = []

func _changed(kind: String, id: String, v) -> void:
	history.append([t_s, kind, id, v])
	cache = {}

func set_edge(id: String, is_open: bool) -> void:
	if open.has(id) and bool(open[id]) != is_open:
		open[id] = is_open
		_changed("edge", id, is_open)

func set_vent(on: bool) -> void:
	var v := "ON" if on else "OFF"
	if vent != v:
		vent = v
		_changed("vent", "", v)

func set_removal(on: bool) -> void:
	var v := "ON" if on else "OFF"
	if removal != v:
		removal = v
		_changed("removal", "", v)

func set_occupants(o: Array) -> void:
	if o != occupants:
		occupants = o.duplicate()
		_changed("occupants", "", o)

func flow(e: Dictionary) -> float:
	if not bool(open[e["id"]]):
		return 0.0
	if str(e["kind"]) == "imv" and vent != "ON":
		return 0.0
	return float(e["Q_m3_s"])

## The module's rates(): A of dy/dt = A y on y = [m_1..m_N, generated, removed, 1], flat row-major.
func rates() -> PackedFloat64Array:
	var n := N + 3
	var A := PackedFloat64Array()
	A.resize(n * n)
	A.fill(0.0)
	for e in edges:
		var q := flow(e)
		if q > 0.0:
			var i := int(e["i"])
			var j := int(e["j"])
			A[i * n + j] += q / float(V[j])
			A[i * n + i] -= q / float(V[i])
			A[j * n + i] += q / float(V[i])
			A[j * n + j] -= q / float(V[j])
	if removal == "ON":
		var r := int(p["removal"])
		var kr := float(p["k_m3_s"]) / float(V[r])
		A[r * n + r] -= kr
		A[(N + 1) * n + r] += kr
	for i in N:
		var g := float(occupants[i]) * float(p["per_person_kg_s"])
		A[i * n + N + 2] += g
		A[N * n + N + 2] += g
	return A

static func _mul(X: PackedFloat64Array, Y: PackedFloat64Array, n: int) -> PackedFloat64Array:
	var out := PackedFloat64Array()
	out.resize(n * n)
	out.fill(0.0)
	for i in n:
		for k in n:
			var a := X[i * n + k]
			if a != 0.0:
				for j in n:
					out[i * n + j] += a * Y[k * n + j]
	return out

## The module's expm(): scaling and squaring of the fixed-order Taylor series.
func expm(M: PackedFloat64Array, n: int) -> PackedFloat64Array:
	var norm := 0.0
	for j in n:
		var c := 0.0
		for i in n:
			c += absf(M[i * n + j])
		norm = maxf(norm, c)
	var s := 0
	var scale := 1.0
	var lim := float(doc["scale_norm"])
	while norm * scale > lim:
		scale *= 0.5
		s += 1
	var X := PackedFloat64Array()
	X.resize(n * n)
	for k in n * n:
		X[k] = M[k] * scale
	var E := PackedFloat64Array()
	E.resize(n * n)
	E.fill(0.0)
	for i in n:
		E[i * n + i] = 1.0
	var T := E.duplicate()
	for k in range(1, int(doc["taylor_order"]) + 1):
		T = _mul(T, X, n)
		var inv := 1.0 / k
		for q in n * n:
			T[q] *= inv
			E[q] += T[q]
	for i in s:
		E = _mul(E, E, n)
	return E

func propagator(dt: float) -> PackedFloat64Array:
	if not cache.has(dt):
		var A := rates()
		for k in A.size():
			A[k] = A[k] * dt
		cache[dt] = expm(A, N + 3)
	return cache[dt]

## Advance dt seconds exactly (connections, occupants and removal constant over the step).
func step(dt: float) -> void:
	var E := propagator(dt)
	var n := N + 3
	var y: Array = m.duplicate()
	y.append_array([generated, removed, 1.0])
	var out: Array = []
	for i in N + 2:
		var acc := 0.0
		for j in n:
			acc += E[i * n + j] * float(y[j])
		out.append(acc)
	m = out.slice(0, N)
	generated = out[N]
	removed = out[N + 1]
	t_s += dt

func ledger_error() -> float:
	var s := 0.0
	for v in m:
		s += v
	return s - (m0 + generated - removed)

func x(i: int) -> float:
	return float(m[i]) / float(p["M_CO2"]) / n_mol(i)

func index(id: String) -> int:
	return ids.find(id)

## The groups of compartments joined by an open edge now: an Array of member-index Arrays, in node order (the module's components()).
func components() -> Array:
	var root := []
	for i in N:
		root.append(i)
	var find := func(a: int) -> int:
		while root[a] != a:
			root[a] = root[root[a]]
			a = root[a]
		return a
	for e in edges:
		if flow(e) > 0.0:
			var a: int = find.call(int(e["i"]))
			var b: int = find.call(int(e["j"]))
			if a != b:
				root[maxi(a, b)] = mini(a, b)
	var groups := {}
	for i in N:
		var r: int = find.call(i)
		if not groups.has(r):
			groups[r] = []
		groups[r].append(i)
	var out := groups.values()
	out.sort_custom(func(u, v): return u[0] < v[0])
	return out

## Per compartment: fraction, trend, group, isolated, whether removal reaches it (the module's readout()).
func readout() -> Dictionary:
	var A := rates()
	var n := N + 3
	var y: Array = m.duplicate()
	y.append_array([generated, removed, 1.0])
	var groups := components()
	var out := []
	var tot_n := 0.0
	var tot_m := 0.0
	for i in N:
		var g: Array = []
		for gr in groups:
			if i in gr:
				g = gr
		var dm := 0.0
		for j in n:
			dm += A[i * n + j] * float(y[j])
		var nm := n_mol(i)
		out.append({"id": ids[i], "x": x(i), "dxdt_per_h": dm / float(p["M_CO2"]) / nm * 3600.0, "group": groups.find(g),
			"isolated": g.size() == 1, "removal_reaches": removal == "ON" and int(p["removal"]) in g, "occupants": occupants[i]})
		tot_n += nm
		tot_m += float(m[i])
	return {"nodes": out, "x_mean": tot_m / float(p["M_CO2"]) / tot_n, "groups": groups.size(), "vent": vent, "removal": removal, "t_s": t_s}

func _apply(ev: Array) -> void:
	match str(ev[1]):
		"vent":
			set_vent(str(ev[3]) == "ON")
		"removal":
			set_removal(str(ev[3]) == "ON")
		"edge":
			set_edge(str(ev[2]), bool(ev[3]))
		"occupants":
			set_occupants(ev[3])

## Replay the packaged reference run and compare every checkpoint (masses, the ledger's two sums, the number of groups).
func verify() -> Array:
	var errs := []
	var proof: Dictionary = doc["proof"]
	var tol: Dictionary = doc["tolerance"]
	reset()
	var events: Array = (proof["events"] as Array).duplicate(true)
	var dt := float(proof["dt_s"])
	var steps := int(round(float(proof["end_s"]) / dt))
	var every := int(round(float(proof["every_s"]) / dt))
	var cps: Array = proof["checkpoints"]
	var c := 0
	for i in steps + 1:
		while not events.is_empty() and t_s >= float(events[0][0]) - 1e-9:
			_apply(events.pop_front())
		if i % every == 0:
			var want: Dictionary = cps[c]
			var got := m.duplicate()
			got.append_array([generated, removed])
			var exp_: Array = (want["m"] as Array).duplicate()
			exp_.append_array([want["generated"], want["removed"]])
			for k in got.size():
				if absf(float(got[k]) - float(exp_[k])) > float(tol["abs_kg"]) + float(tol["rel"]) * absf(float(exp_[k])):
					errs.append("t %.0f s: value %d is %s, reference %s" % [t_s, k, str(got[k]), str(exp_[k])])
			if components().size() != int(want["groups"]):
				errs.append("t %.0f s: %d groups, reference %d" % [t_s, components().size(), int(want["groups"])])
			c += 1
		if i < steps:
			step(dt)
		if errs.size() > 3:
			break
	if c != cps.size() and errs.is_empty():
		errs.append("compared %d of %d checkpoints" % [c, cps.size()])
	return errs
