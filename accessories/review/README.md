# Accessory review package (2026-10-24, third slice)

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
| `16_eva_grasp.jpg` | the glove closed on the cartridge crew handle, seen from the thumb / index end (contact-aware display grasp) | same |
| `17_iva_tasks.jpg` | DR-IVA-02 at a deck guide (interface request), DR-IVA-01 perched, DR-IVA-03 at a raceway port | `accessory_scene.py --scenes iva` |
| `18_viewer_DR-EVA-03.jpg`, `19_viewer_handoff.jpg` | the standalone Godot 4.7.2 accessory viewer: grouped class list, action / status table, status card, class facts and gates | `tools/accessory_viewer.py shots` |
| `20_compare_suit.jpg` | suit turnaround before (042ee65 build) and after: boot shells, knee / elbow covers, layered materials, lettering, wear | `eva_preview.py --views turnaround` (before: `--assets` on a 042ee65 build), composed |
| `21_compare_eva_crawlers.jpg` | DR-EVA-01 / 02 / 03 before (042ee65 images) and after the functional identity pass | `drone_preview.py --views review`, composed |
| `22_compare_grasp.jpg` | the glove grasp close-up before and after | `accessory_scene.py --scenes eva`, composed |
| `23_viewer_suit.jpg` | the accessory viewer's suit entry: 15 EVA actions playable, the five inherited unsuited actions LOCKED | `tools/accessory_viewer.py shots` |
| `25_compare_viewer.jpg` | the viewer before (c3cb062) and after its usability pass: suit and DR-EVA-02 entries | `tools/accessory_viewer.py shots`, composed |
| `HANDOFF.md` | owner review and handoff register: visual decisions approvable now, engineering decisions for the canonical Drive sheets, ship-session items | written |
| `review.pdf` | printable review (A4, 12 pages): register, before / after, suit, readbacks, validation, compact PLSS, drone family, HOLD / OPEN list | the review page printed with Chromium; regenerate from `HANDOFF.md` and the images when they change |
| `24_dock_cradles.jpg` | DR-EVA-01 / 02 / 03 docked on their review stands: the PROTOTYPE docking cradles (review fixtures, not ship geometry) | `drone_preview.py --views cradles` |
| `rail_section.svg` | crawler rail cross-section for the ship-session interface request: wheel capture, support web corridor, swept envelope | `presentation/rail_section.py` |

Regenerate with the commands in docs/ACCESSORIES.md ("Run"); the images here are JPEG copies of the review-quality renders. The
comparison sheets 20-22 and 25 are side-by-side composites of those renders with a label bar (no image editing beyond scaling).
