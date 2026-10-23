# Wayfarer mobile experience and touch controls (MOB-001)

Plan and decision record for playing Enter Wayfarer (Integrated Demonstrator 01, Godot Web) on phones and tablets without a
keyboard. It covers usability, input, presentation and mobile rendering cost only. No spacecraft geometry, physics, simulation
data or workbook value changes. Dated 2026-10-23, branch `claude/mobile-touch-controls`. The web deployment record is
[wayfarer-web-experience-plan.md](wayfarer-web-experience-plan.md).

## 1. Verified starting point (`main` 80a6cb2)

- **Input.** `WfInput` (`godot/scripts/controls/wf_input.gd`, autoload) is the single action registry: semantic ids, contexts,
  keyboard and gamepad bindings, the analog `strength()` with dead zone and sensitivity, lessons, onboarding preference and the
  profile `user://wayfarer_controls.cfg` (schema 2).
- **Two input paths.** Continuous actions are read every frame through `WfInput.strength()`:
  - `player.move_*` in `boarding.gd` (rail walk) and `body_tour.gd` (deck walk, ladder climb).
  Discrete actions arrive as events in the scenes' own `_unhandled_input`:
  - `body_tour.handle_input`: `e.is_action_pressed("player.grab")`;
  - `demo01.gd`, `boarding.gd`: `WfInput.key_of(e, ctx)` behind `WfInput.pressed(e)`, which accepted only keys, joypad buttons
    and extra mouse buttons;
  - `ship_navigator.gd`: keys and joypad buttons only.
  A synthetic key would not survive rebinding; `Input.action_press()` reaches the `strength()` path but not the event handlers.
- **Looking** is a right-mouse drag read as raw `InputEventMouseMotion` in `body_tour.gd` (yaw/pitch, which also aims a push-off)
  and `boarding.gd` (rail camera look offset). Touch, which Godot emulates as a *left* button, cannot look at all.
- **Web play.** `demo01.tscn` is the web main scene; the keyboard first launch (`open_first_launch`) runs only in the review menu,
  so web visitors get SUGGESTED lesson cards that name keys. The launcher says touch-only devices should use Explore Ship.
- **Phone baseline** (headless Chrome, SwiftShader, `runs/mobile-baseline/`, §8): the 2-D interface is laid out in *device*
  pixels: at DPR 3 the 15 px HUD text is 5 CSS px tall, the desktop side and bottom panels cover a third of the view, the lesson
  card says "hold W", and the 3-D view renders 2532 × 1170 px.

## 2. Research (sources)

| Topic | Finding | Source |
| --- | --- | --- |
| Virtual controls | Movement left, camera right, frequent buttons near the thumb, secondary (menus) at the top; show and hide controls with gameplay; a floating stick is preferred; 44 × 44 pt for frequent controls; respect safe areas; support game controllers | [Apple HIG: Game controls](https://developer.apple.com/design/human-interface-guidelines/game-controls), [Designing for games](https://developer.apple.com/design/human-interface-guidelines/designing-for-games) |
| Touch targets | At least 48 × 48 dp | [Android accessibility](https://developer.android.com/guide/topics/ui/accessibility/apps) |
| Godot 4.7.2 mouse emulation | The emulated mouse event (device `DEVICE_ID_EMULATION` = -1) is sent *before* the touch, for the first finger down only (`core/input/input.cpp`) | Godot source, tag 4.7.2-stable |
| Godot 4.7 Controls | Controls receive ScreenTouch/Drag; BaseButton handles real touch (new in 4.7) | `scene/main/viewport.cpp`, `scene/gui/base_button.cpp` |
| TouchScreenButton | A Node2D (no anchors, containers or safe-area layout), texture-only, one finger per button; with `action` it calls `action_press` and pushes an InputEventAction, and its release clears the action for every device | `scene/2d/physics/touch_screen_button.cpp`, [docs](https://docs.godotengine.org/en/stable/classes/class_touchscreenbutton.html) |
| Godot Web | Touch events are `preventDefault`ed (no browser mouse echo); `touchcancel` arrives as a plain release; drag `relative` is kept per changed-touch slot, not per finger (wrong with two fingers); no safe-area insets; `screen_get_scale` = devicePixelRatio; a canvas blur sends WM_WINDOW_FOCUS_OUT, but no APPLICATION_FOCUS_OUT and no visibility signal | `platform/web/js/libs/library_godot_input.js`, `display_server_web.cpp` |
| 3-D resolution | `Viewport.scaling_3d_scale` with bilinear works in Compatibility since 4.3 | `drivers/gles3/storage/render_scene_buffers_gles3.cpp` |
| JavaScriptBridge | `eval` is on in official web templates and synchronous | `platform/web/detect.py` |
| Browser | `touch-action: none` blocks pinch zoom (an accessibility cost, so game surface only); `screen.orientation.lock()` needs full screen and is unsupported on Safari; element full screen is unavailable on iPhone; `env(safe-area-inset-*)` needs `viewport-fit=cover` | MDN: [touch-action](https://developer.mozilla.org/en-US/docs/Web/CSS/touch-action), [lock()](https://developer.mozilla.org/en-US/docs/Web/API/ScreenOrientation/lock), [requestFullscreen](https://developer.mozilla.org/en-US/docs/Web/API/Element/requestFullscreen), [env()](https://developer.mozilla.org/en-US/docs/Web/CSS/env) |

**Alternatives.**

- **A. Native Godot touch interface: chosen, for gameplay input.**
  - It stays inside `WfInput`, so contexts, interlocks and lessons apply unchanged.
  - The same build can be tested natively.
  - It works the same in a future native mobile export.
- **B. HTML/CSS overlay: rejected for gameplay.**
  - It would need a JavaScript-to-Godot bridge for every action.
  - It would duplicate the context logic outside the registry.
  - It cannot follow the scenes' state without polling.
- **C. Hybrid: adopted for the browser-only concerns.** The HTML shell owns:
  - safe-area insets;
  - full screen and the orientation request;
  - the portrait suggestion;
  - blurring the canvas on `visibilitychange`.

Godot owns all game input.

**Library.** I found no maintained library that fits:
- TouchScreenButton lacks Control layout and its release clears key presses.
- Virtual-joystick add-ons would add a dependency and still need the registry glue.

A small custom layer (`wf_touch.gd`, about 500 lines of GDScript) is the smaller maintenance burden.

## 3. Architecture

```
finger ─ InputEventScreenTouch/Drag ─► WfTouch (_input, by touch index)
           │ claims each finger for ONE control; swallows Godot's emulated mouse of a claimed finger
           ├─ stick  ─► WfInput.set_virtual(move_*, 0..1) ─► WfInput.strength() ─► boarding / body_tour (unchanged physics)
           ├─ look   ─► WfInput.add_look(rad)            ─► take_look() by the look owner (body yaw/pitch, rail look offset)
           ├─ button ─► WfInput.trigger(id) ─► InputEventAction(id) ─► the same _unhandled_input as the bound key
           └─ gui    ─► untouched: Godot's mouse emulation reaches the scene's own controls (map view, card, panels)
scene ── WfInput.touch_provider() ─► {move: "" | "1d" | "2d", look, actions [[id, label, role]], utility, local}
```

- **`trigger(id)`** parses an `InputEventAction` press and release, the event a bound key is matched as (`is_action`). It reaches the
  same handler with the same checks: a grab with no rail in reach stays refused, push needs a grip, and the vestibule interlock
  is untouched. `WfInput.pressed()`, `key_of()` and the navigator's filter now accept `InputEventAction`. Rebinding a key never
  changes a touch button.
- **`set_virtual`** holds only *hold* actions; `strength()` returns the larger of the device and the touch value, so keyboard,
  gamepad and touch can all be used together. Unlike `Input.action_press`, a key release cannot cancel the stick, and the stick
  cannot cancel a key.
- **Look** is a semantic channel: a scene that takes the look each frame owns it (`take_look()`), and the touch layer offers the
  look area only while some scene takes it. The guided EXTERIOR and MODE orbits take none, so they are not overridden. The
  desktop right-drag path is unchanged.
- **Device.** `WfInput.device` gains `touch`. Emulated mouse events (device -1) never switch it back to keyboard. Prompts use
  `TOUCH_LABELS` ("Grab", "stick up") while touch is in use and the keyboard labels otherwise. A key or pad press hands the
  prompts back and hides the touch controls (`touch_controls = auto`).
- **Resets.** These all release every finger, the stick and any look not yet taken:
  - finger up or cancel;
  - a modal panel;
  - WM_WINDOW_FOCUS_OUT;
  - a resize or rotation;
  - a scene change (the provider's `tree_exiting`).
  In addition, the shell blurs the canvas when the page is hidden.
- **Profile.** Schema 3 adds a `[touch]` section with look speed, stick floating/fixed, controls auto/on/off and `intro_done`.
  A schema 2 profile loads with every binding and setting intact and the touch defaults.
- **Compact layout.** Chosen once from the device: coarse pointer and no fine pointer, or `--touch`. The window size alone never
  chooses it, so desktop windows keep the desktop layout. In compact mode:
  - the 2-D interface is scaled by devicePixelRatio, so 1 UI px = 1 CSS px (target sizes physical);
  - the desktop columns are hidden;
  - the chapter text sits top left, the map is hidden until Map is tapped, the card takes the text's place, and lessons sit at
    the top.

## 4. Touch → action mapping (Demonstrator 01)

| Chapter | Stick (left) | Look (right) | Buttons (bottom right) |
| --- | --- | --- | --- |
| EXTERIOR, MODE | — (guided orbit) | — | Pause/Resume · Skip/Next ▸ · MODE: Fault: occupant / Secure occupant (`demo.occupants`) |
| ENTRY | 1-D along the rail (`player.move_forward/back`) | rail look offset | Pause · Skip/Next ▸ |
| MICROGRAVITY | — weightless: no force without a rail | body view (aims Push off) | Grab (no grip) or Push off + Release (gripping) · View · Auto · Next ▸ |
| TRANSFER, DESCENT | 1-D along the line or the rungs | body view | View · Auto · Next ▸ |
| GRAVITY | 2-D walk on the deck | body view | Drop object · View · Auto · Next ▸ |
| ARRIVAL, INSPECT | — | rail look offset | Pause / Hold layer on · Next ▸ |
| Top right (always) | | | Map (`ship.map`) · Systems / Why / Show me / Close (`ship.card`) · Details (display only) · ? Help |

- **Physics redline.**
  - Weightless, the scene offers no stick at all.
  - Even a held stick could add no force: `WfCrewBody.walk_dir` acts only through a floor contact. The check
    `micro_stick_no_force` asserts this.
- **Interaction modes.**
  - Game actions (Grab, Push off, Release, Drop) fire on touch-down, with no tap delay.
  - Navigation buttons fire on release and can be cancelled by sliding off.
- **Help (?).** A modal panel, paused. It shows:
  - what each control does now;
  - look speed, stick floating/fixed, tips on/off, touch controls auto/on/off;
  - replay lessons;
  - the keyboard/controller Codex.
- **Touch welcome.**
  - It appears on the first touch-first launch and replaces the key-capture first launch.
  - It explains the thumbs, says that the stick does nothing when weightless, and offers "Start with tips (recommended)" or
    "Start without tips", which maps to the SUGGESTED / EXPERIENCED preference.
  - Guided / Assisted / Free stay the navigator's modes (unchanged).

## 5. Browser shell (`web/play/shell.html`)

- **Viewport.** `viewport-fit=cover`. `touch-action: none`, `overscroll-behavior: none` and no selection or callout apply on the
  game page only. The launcher and the site keep normal scrolling and zoom.
- **Insets.** `window.wayfarerSafe` holds the `env(safe-area-inset-*)` values from a hidden probe element, and Godot reads them on
  resize.
- **Top-left buttons.** On touch-first devices Exit and Full screen are 44 px targets at the top left, inside the safe area.
  Full screen appears only where element full screen exists, so not on iPhone. After full screen, `screen.orientation.lock`
  ('landscape') is attempted, and a refusal is ignored.
- **Portrait.** A suggestion with "Full screen, landscape" and "Continue upright". The game keeps running and keeps its state
  through rotation (Godot's adaptive canvas). The touch layer releases every finger on resize.
- **Unchanged.**
  - Click to load: neither the welcome page nor the launcher downloads the engine before Start.
  - WebGL context release on `pagehide`.
- **Allowed `?arg=`.** `--touch`, `--no-touch` and `--touch-probe` (checks).

## 6. Desktop compatibility

- **Unchanged on desktop.**
  - The layout and its sizes, since compact mode is never chosen for a fine pointer.
  - The 3-D resolution.
  - Keyboard, mouse and gamepad paths and their checks.
  - The Codex and the first launch in the review menu.
- **Changed for everyone (text only).** The chapter text now prints keys through `WfInput.keys()`. The demonstrator's old
  "A autoplay" therefore now reads the real binding (F2), and rebinding shows there too.
- **Touch on a desktop.** On a touchscreen laptop, touch controls appear when the screen is touched (auto) at desktop scale, and
  disappear with the next key or pad press.

## 7. Implementation sequence (this branch)

1. `wf_input.gd`: `set_virtual`, `trigger`, look channel, `touch` device, emulated-mouse filter, `modal()`, schema 3, touch labels.
2. `wf_touch.gd`: per-finger claims, stick, look, buttons, welcome and help, safe area, density, adaptive 3-D scale, probe.
3. Scene glue: `demo01.gd` (provider, compact text, keys through the registry); `boarding.gd`, `body_tour.gd` (take look,
   compact columns); `ship_navigator.gd` (InputEventAction, compact layout); `control_overlay.gd` (compact lesson card).
4. Shell: insets, full screen and orientation, portrait suggestion, visibility blur, check args. Launcher copy.
5. Checks: `check_touch.gd` (`--check-touch`, runtime-export list); the browser touch journey in `tools/web_check.py`.

## 8. Mobile performance

**Baseline (before, headless Chrome 140 + SwiftShader software WebGL on the cloud container, `runs/mobile-baseline/`).**

| Viewport (CSS, DPR) | Start → running | rAF fps (10 s) | Canvas px |
| --- | --- | --- | --- |
| Desktop 1280 × 800, 1 | 12.8 s | 0.7 | 1280 × 800 |
| Phone landscape 844 × 390, 3 | 7.4 s | 0.4 | 2532 × 1170 |
| Phone portrait 390 × 844, 3 | 6.9 s | 0.7 | 1170 × 2532 |
| Tablet 1180 × 820, 2 | 6.6 s | 0.4 | 2360 × 1640 |

Software rendering on a shared CPU says nothing about a phone's GPU frame rate. It shows the cost scaling with pixels: a 3×
phone renders 2.9 × the desktop's pixels. The download is 62.9 MB uncompressed: the 39.5 MB wasm and a 23.1 MB pack.

**Changes (rendering only).**
- On touch-first devices the 3-D view renders at `RENDER_DENSITY` = 1.25 device px per CSS px. At DPR 3 that is a
  `scaling_3d_scale` of 0.42, bilinear, about 18 % of the pixels. The 2-D interface stays at full resolution.
- An adaptive step keeps the frame rate between 24 and 45 fps, using the 3-D scale only, within 0.35 to the cap. It waits 6 s
  for loading and ignores paused time.
- MSAA, lights, materials, geometry and the simulation are unchanged.

**Budget (initial).** A stable 30 fps on a reference mid-range phone (to be agreed; see §9) at the adaptive scale. It is not
claimed for every device. The after-measurements are in §11.

## 9. Test matrix

| Area | Automated here | Real device |
| --- | --- | --- |
| Registry: virtual holds, trigger, look, device switch, profile v3 | `check_touch.gd` (native headless, real touch events, 30 checks) | — |
| Journey by touch, multi-finger, modal, focus loss, release | `check_touch.gd`; browser journey (Chrome, touch emulation, DPR 3) | **pending** |
| Desktop regression | `--check-demo` 68 checks, `--check-controls`, `--check-controls-body`, `review-demo01`; web_check desktop walk and equivalence | — |
| Android Chrome (phone) | emulated only | **pending**: no device in this environment |
| iOS Safari (iPhone / iPad) | not emulable (WebKit) | **pending** |
| Tablet viewport, portrait ↔ landscape | browser journey (emulated) | **pending** |
| Frame rate, thermal, memory on a phone | not measurable here (software GL) | **pending** |

**Phone test procedure** (owner or tester; about 10 minutes per device).

1. On the phone, open the branch preview (§11) or the site after promotion.
2. Choose Enter Wayfarer, then Start. Note the seconds until the welcome shows.
3. Tap "Start with tips". Rotate the phone and back, and confirm the chapter continues.
4. ENTRY: Pause, then move with the left thumb while dragging the right thumb.
5. MICROGRAVITY: look aft, Push off, then Grab at the next rail.
6. TRANSFER and DESCENT: hold the stick down.
7. GRAVITY: walk, and Drop object while walking. Then open Map, Systems through to Close, and Help.
8. Switch to another app and come back: nothing should move by itself.
9. Exit: you should be back on the launcher.
10. Record the device, the browser version, the fps shown in Help (look speed line) or by the browser's FPS meter, any stuck
    input and any text too small to read.

## 10. Risks and limitations

- **Unverified on real hardware.** Real phones were not available here. iOS Safari (WebKit) is not covered by Chrome emulation.
- **Download size.** 63 MB is heavy on mobile data. The launcher states the size, and the compressed transfer is about 20 MB.
  A smaller engine build (a custom template without unused modules) was not attempted, because nothing has been measured to
  justify it yet.
- **Single-threaded WebGL 2 on a phone.** Old or low-memory phones may fail to start. The shell shows the missing features and
  points to Explore Ship.
- **Glyphs.** The missing ▶ ◆ ○ glyphs in the navigator remain (P05).
- **Landscape lock.** iPhone cannot go full screen or lock landscape. The portrait suggestion and the upright layout cover it.
- **Hybrid devices.** A touchscreen laptop gets desktop-scale touch controls when touched. This is usable but not tuned.

## 11. Results (2026-10-23, branch `claude/mobile-touch-controls`)

**Automated, passing.**

- **`--check-touch`.** 30 checks, native headless Godot 4.7.2, at 844 × 390 UI px. The events are real InputEventScreenTouch
  and ScreenDrag with Godot's mouse emulation. Covered:
  - welcome by tapping, then Pause and Skip;
  - the rail stick with a second finger looking, and release stopping the stick;
  - no emulated mouse reaching the scene;
  - weightless: no stick and no force, look, Push off, Grab refused out of reach;
  - transfer 1-D, deck walk 2-D, Drop by a second finger while walking;
  - Help as a modal (stick released, buttons on screen), then closed;
  - focus loss releasing the stick, a key handing back to the keyboard, the touch labels.
- **Desktop regression on the changed scripts.** All pass:
  - `--check-demo`: 68 checks;
  - `--check-controls`;
  - `--check-controls-body`;
  - `--review=demo01 --check-review`;
  - 146 Python tests.
- **Browser touch journey (`tools/web_check.py`, `run_touch`).** 20 checks in headless Chrome: an emulated phone
  (844 × 390 CSS px, DPR 3, touch), then upright (390 × 844) and tablet (1180 × 820, DPR 2). All 20 passed locally (1234 s
  under SwiftShader) after two fixes it found:
  - Help's Close was below the fold on a 390 px tall screen;
  - devicePixelRatio was not followed on resize.
- **Branch CI.** Run 39915535792 confirmed the browser-versus-native equivalence on the changed scripts: 68 of 68 checks and
  the 5,438-frame recording, identical to native. It also exposed contention: three browsers on the runner timed out a walk
  screenshot. The journey now runs after the equivalence session. Run 39926690587 on `84c43a8` passed: the vehicle
  build (geometry diff empty), the unit tests, all 57 browser checks, the 68-check equivalence and the touch journey. The
  browser check took 31 minutes; splitting it into separate desktop and touch jobs is a follow-up (TODO P05).
- **Review fixes and integration.**
  - The lesson card takes the first free place clear of the systems card, the map, the chapter text, the page buttons and
    the touch controls. On a sideways phone with the systems card and the map both open, it waits until one closes.
  - The full map sits under the page buttons.
  - The chapter text uses short touch wording.
  - `--check-touch` adds both at phone sideways, upright and tablet sizes (32 checks).
  - Merged with `main` `f1e892b` (MOD-003..008). Run 39937720204 on `894e013` passed: geometry diff against
    `baseline_modules_phase2` empty, the native 68 checks and the 5,438-frame recording identical in the browser, and 57 of
    57 browser checks including the touch journey.

**Screenshots** (local, `runs/touch-only/`, `runs/journey/`):
- welcome;
- exterior (guided);
- entry with stick and look;
- microgravity (Push off / Release, one-line lesson);
- systems card;
- gravity walk with Drop;
- Help;
- upright hint and upright layout;
- tablet.

**Performance** (software rendering; behaviour, not phone speed).

| Viewport | Before: canvas px · 3-D px | After: 3-D px (scale) | rAF fps before → after |
| --- | --- | --- | --- |
| Phone 844 × 390, DPR 3 | 2532 × 1170 · 2.96 M | 1063 × 491 · 0.52 M (0.42) | 0.4 → 0.6 |
| Phone 390 × 844, DPR 3 | 1170 × 2532 · 2.96 M | 0.52 M (0.42) | 0.7 → 0.5 |
| Tablet 1180 × 820, DPR 2 | 2360 × 1640 · 3.87 M | 1.51 M (0.625) | 0.4 → 0.3 |
| Desktop 1280 × 800, DPR 1 | unchanged (no touch-first) | 1.02 M (1.0) | 0.7 → 0.6 |

- **Pixels.** The phone renders 18 % of the 3-D pixels it did before.
- **fps.** At under 1 fps the software renderer gives 4 to 7 frames per 10 s, so these fps differences are noise.
- **Adaptive step.** In the browser journey it lowered the scale to its 0.35 floor (at 1 fps), as designed.
- **Start-up.** Start to running took 7 to 21 s locally; the welcome showed 7 to 15 s after navigation.
- **Not measured: real-device frame rate, input latency, memory and thermal behaviour.** They need a phone (§9 procedure).

**Real devices: none tested.** Android Chrome, iOS Safari (iPhone and iPad) and a real tablet are **pending**. iOS full screen
and the landscape lock are unsupported by design; the upright layout covers that case.

## 12. Definition of done

- [x] A separate branch (`claude/mobile-touch-controls`), pushed. `main` and the deployed site are unchanged.
- [x] Touch extends `WfInput`: virtual holds, `trigger()` actions with no synthetic keys, and a semantic look.
- [x] A touch welcome with no keyboard; Help is always available; profile schema 3 migrates schema 2.
- [x] Multitouch claims by finger: stick with look, and stick with a button, both at once. Release, modal, focus loss and resize
      all release. (Web delivers `touchcancel` as a plain release.)
- [x] The controls follow the chapter (guided, weightless, line or ladder, deck, inspect). A weightless stick adds no force.
- [x] Compact HUD on phone and tablet viewports; desktop layout unchanged.
- [x] The whole demonstrator can be completed by touch in the tested environment. Every chapter is reached by Skip or Next; the
      physics chapters are operated by touch.
- [x] Desktop regression checks pass; physics and geometry unchanged (CI geometry diff: 0 changed).
- [x] Performance measured before and after, with its limits stated. Real-phone validation listed as **pending**.
