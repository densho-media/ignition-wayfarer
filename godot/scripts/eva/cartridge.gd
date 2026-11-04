class_name WfCartridge
extends RefCounted
## One RC-1 dock-channel resupply cartridge (EVA-OPS-001, data/eva_ops.toml [cartridge]): a finite N2 vessel on a keel adapter.
## Where it is decides what feeds from it: in the rack (nothing), in arm B (carried by the drone, feeds nothing), free (its own body,
## Newtonian), seated in the suit channel (the suit's dock line: first in the suit's feed order), stowed back in the rack (empty).

enum Where { HELD, FREE, SEATED, STOWED }
var id := ""
var tank: WfN2Tank
var hardware_kg := 1.6
var where := Where.HELD
var node: Node3D                      # visual (and the free body when FREE)
var body: WfEvaBody

func _init(i: String, c: Dictionary) -> void:
	id = i
	hardware_kg = float(c["hardware_kg"])
	tank = WfN2Tank.new(i, "RC-1 cartridge " + i, float(c["n2_kg"]), float(c["usable_kg"]), float(c["regulator_pa"]))

func wet_kg() -> float:
	return hardware_kg + tank.n2_kg
