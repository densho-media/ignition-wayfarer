<!-- lab entry -->
| Lab entry | |
| --- | --- |
| Kind | Study |
| Status | ACTIVE (engine used by lab/variants/fdp1) |
| Question | What drive and ship can fly four 0.016 c burns without refuelling, by technology tier? |
| Model base | main 92b83f0 |
| Salvaged from | claude/project-thread-plvziu @ e60ad2b (same files on 8e13aa), 2026-11-06 |
| Open owner questions | Which tier to design to (optimistic, central, pessimistic). |
| Review | project files review/four_burn_2026-11-03/ |

# four-burn-mission: notes

Owner brief 2026-11-03 13:14Z ("Wayfarer Four-Burn Propulsion & Fuel Optimization"). Research only: no canon, `data/`, generator,
tank geometry, Fiji spec or Blender change. Branch `claude/project-thread-plvziu`.

**Function.** Find what drive and ship can do four 0.016 c burns (out, brake, back, brake) without refuelling, physics first.

**Fixed constraints.** 0.016 c per burn (LOCKED); 1.5 g ceiling; D-3He fuel with separate H reaction mass; Fiji lattice = field
amplification and stabilisation only (no heat sink, no stored-energy reduction); energy and momentum conserved; exhaust energy is not
radiator heat.

**Unknowns (kept as tiers, not answers).** D-3He ignition and burn fraction (continuous tau_p, pulsed rhoR), target gain, driver
efficiency and specific mass, nozzle efficiency, armour flux limits, radiator areal mass, tank mass at scale.

**Design freedom used.** Exhaust velocity, power, departure acceleration, core count, pulse rate, tamper mass, radiator type.

**Decisions (Claude, research delegation 2026-10-31).**
- Tiers: optimistic = speculative engineering, central = credible extrapolation, pessimistic = near today's practice.
- Payload 860 t = canon 1,300 t less drive 250, radiators 100 and the legacy tanks 90.
- Propellant reserve 2 % of mission propellant on top of the canon residual and boil-off allowances (PROTOTYPE).
- Tank mass 11.4 kg per m3 of capacity (as-built farm), per species density.
- Continuous core picks its field up to the Fiji limit; core length capped (more cores beyond); a shadow shield per core.
- Pulsed hybrid picks its pulse rate continuously (golden section), tamper mass to hit ve.

**Open for the owner.** Which tier to design to; whether centuries of thrust (central) or a speculative-engineering ship (optimistic,
years) is the story; He-3 inventory scale (thousands of tonnes); see REPORT.md section "Owner decisions".
