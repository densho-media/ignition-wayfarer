class_name WfN2Tank
extends RefCounted
## One nitrogen inventory (EVA-OPS-001): a mass of gas in a vessel. Gas leaves only through draw() (thrusters), never goes below the
## regulator drop-out residual (eva_drone.toml gas.usable_fraction) and enters only through training_reset(), which is counted and
## labelled. There is no transfer between tanks: no line in the canonical suit refills a vessel (the dock line feeds thrusters).

var id := ""
var label := ""
var capacity_kg := 0.0         # full contents at 30 MPa
var residual_kg := 0.0         # left in the vessel when the regulator drops out
var n2_kg := 0.0
var feed_pa := 0.0             # regulated feed pressure: the higher feed wins at a check-valve junction
var used_kg := 0.0             # out through the nozzles since start
var reset_added_kg := 0.0      # put back by training resets (not an in-world event)
var resets := 0

func _init(i: String, lbl: String, full_kg: float, usable_full_kg: float, feed: float) -> void:
	id = i
	label = lbl
	capacity_kg = full_kg
	residual_kg = full_kg - usable_full_kg
	n2_kg = full_kg
	feed_pa = feed

func usable() -> float:
	return maxf(0.0, n2_kg - residual_kg)

func usable_full() -> float:
	return capacity_kg - residual_kg

func fraction() -> float:
	return usable() / usable_full() if usable_full() > 0.0 else 0.0

## Take up to `kg`; returns what was actually taken (less when the vessel runs down). Never negative, never below the residual.
func draw(kg: float) -> float:
	var got := clampf(kg, 0.0, usable())
	n2_kg -= got
	used_kg += got
	return got

## Training only: fill the vessel back to full. Counted, so the ledger shows it is not an in-world resupply.
func training_reset() -> void:
	reset_added_kg += capacity_kg - n2_kg
	n2_kg = capacity_kg
	resets += 1

## Conservation ledger: what is in the vessel plus what has left minus what resets put back equals the first fill.
func ledger_error() -> float:
	return n2_kg + used_kg - reset_added_kg - capacity_kg
