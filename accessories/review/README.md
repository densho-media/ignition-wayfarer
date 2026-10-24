# Accessory review package (2026-10-24)

Curated review images of the WAYFARER accessories (docs/ACCESSORIES.md), committed with the code that renders them. Everything shown is
**PROTOTYPE**: the drone bodies are isolated visual and interaction studies, not integrated (54 DGT-017 HOLD); GU-SIF is a proposed
interface (DGT-012 HOLD); every EVA scene is a training simulation (FLIGHT_EVA HOLD); mass, power, speed, payload, reach, latch strength,
thermal endurance and suit life-support performance are OPEN. Dimensions are stowed sizes from the fit screen or measured readbacks of the
as-built prototype, never ratings.

| File | Shows | Made by |
| --- | --- | --- |
| `01_drone_lineup.jpg` | all seven mobile classes and both fixed arms at one scale, stowed sizes, the suited instructor (1.78 m) as scale | `presentation/drone_preview.py --views review` |
| `02_DR-IVA-01.jpg` … `10_DR-FIX-02.jpg` | each class in its main action, three-quarter view, status note with stowed size and envelope class | same |
| `11_suit_turnaround.jpg` | WAYFARER_EVA_Y155 instructor: front, side, back, three-quarter | `presentation/eva_preview.py --views turnaround` |
| `12_suit_cutaway.jpg` | layers, hard torso, helmet and PLSS internals (display layout, not packaging) | `eva_preview.py --views cutaway` |
| `13_plss_compare.jpg` | baseline two-module PLSS vs. compact study ASSET-10: side profiles, back views with the pack opened, measured readbacks | `eva_preview.py --views plss_compare` |
| `14_eva_handoff.jpg`, `15_eva_handoff_3q.jpg` | DR-EVA-03 presents its tool cartridge; the instructor in a foot restraint, tether A clipped (training fixtures) | `presentation/accessory_scene.py --scenes eva` |
| `16_eva_grasp.jpg` | the glove closed on the cartridge crew handle (contact-aware display grasp) | same |
| `17_iva_tasks.jpg` | DR-IVA-02 at a deck guide (interface request), DR-IVA-01 perched, DR-IVA-03 at a raceway port | `accessory_scene.py --scenes iva` |
| `18_viewer_DR-EVA-03.jpg`, `19_viewer_handoff.jpg` | the standalone Godot 4.7.2 accessory viewer: class list, actions, gate labels | `tools/accessory_viewer.py shots` |
| `rail_section.svg` | crawler rail cross-section for the ship-session interface request: wheel capture, support web corridor, swept envelope | `presentation/rail_section.py` |

Regenerate with the commands in docs/ACCESSORIES.md ("Run"); the images here are JPEG copies of the review-quality renders.
