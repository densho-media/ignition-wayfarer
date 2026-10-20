class_name WfReviewSession
extends RefCounted
## U01: one guided review session (a development review tool, not game UI). A scene's session subclasses this and answers from
## the scene's real state; the guide (review_guide.gd) polls it every frame and never moves anything itself.
##
## A step is {title, goal, expect}. The guide advances when done(i) turns true for the current step, never on a timer.
## keys(i) lists what the reviewer can press now, as [key, what it does, role]: "next" (the key that moves the step on), "now"
## (available) or "exit". Only keys that work in the current state belong there.

var title := ""
var steps: Array = []
var detail_key := KEY_TAB                     # retired by ACI-10: the guide reads the ui.details action (default Tab)

func done(_i: int) -> bool:
	return false

func keys(_i: int) -> Array:
	return []

## Optional progress text for the current step, shown on its checklist line ("2.1 / 3.0 m").
func progress(_i: int) -> String:
	return ""

## Called before the scene handles a key press; return [text, ok] to show as feedback (ok false: a refusal and its reason), or [].
func on_key(_keycode: int, _i: int) -> Array:
	return []

## Source status of what step i shows, as [[status, what]]: the guide draws each as an outlined badge (CANON, DERIVED, WORKING, PROTOTYPE,
## DIAGNOSTIC, OPEN, HOLD) so the reviewer can tell an owner value from a placeholder or a measurement. Read statuses from the rig.
func labels(_i: int) -> Array:
	return []

## Engineering detail (sources, PROTOTYPE notes, telemetry): one muted line, expanded with I.
func details() -> String:
	return ""

## Result line when step i completes (shown green), or "" for the default "Done: <title>".
func result(_i: int) -> String:
	return ""

func tick(_dt: float) -> void:
	pass
