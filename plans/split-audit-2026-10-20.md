# Split audit, 2026-10-20

Four read-only audits, one per layer: engine at a29552e, domains at main, config world.json on minimal-world, UI on application-look.
Each item names the layer it belongs in.

## Engine (world-engine)
1. `jvmMain/CliCompareHouse.kt:8-19`, `Cli.kt:34`: the `compare-house` command hardcodes a path into Jim's Windows house-world. Move it to that world's check.
2. `SolverInterfaces.kt:15-66`, `Solvers.kt:11-45`: built-in conduction, bracing and span solvers. Move them to the thermal and structural domains.
3. `Checking.kt:32-35`: `TASK_FACT_TYPES` is a fixed list of construction-safety facts. Domains should declare them in the manifest.
4. `Labour.kt:115,159-161,182-193,346`: fixed pay, fatigue, install_hours and bom field names, plus a second labour mechanism alongside `Crew.kt`. Merge the two into one engine mechanism and move the field names to the manifest.
5. `ContractDisplay.kt:66`: the cord-of-wood BTU is an unsourced catalog fact. Lines 56-90 hold a display unit table that should be data.
6. `Scene.kt:12-23,317-388`: water layers (domain content), and zoom steps in feet.
7. `Constants.kt:3,5,96,109`: fixed lists SOURCED_KINDS and VOTE_CLASSES, and usd as a base unit.
8. `Expansion.kt:192-199`: `layOver` takes only west and north offsets (`roofDepth`). It should take a general offset vector.
9. `CliAquaponics.kt:10-14`: hardcoded paths into research.
10. Duplicates: ft/lb conversions (`Differential.kt:47-48` and `ContractDisplay.kt:56-61`), `GOOD_ENDS` (`Overlay.kt` and `Ranking.kt`), `FIGURE_SCALE` (`Crew.kt` and `Sample.kt`), and the optimizing weight names hardcoded at `Crew.kt:23`.
- Missing: sampling of spec figures (in progress); a general load-path mechanic (force split over contacts); the conformance fixture domains ship in jvmMain.
- Views the UI needs from the engine: elevation and section views, geometry with the openings already cut out, a dimension view, a design-summary view, a material kind generic enough to style, and a setting's status (assumed or reading) as a field.

## Domains (domains)
1. `tasks/Tasks.kt:63-78,10,81`: this house's task sequence is hardcoded in Kotlin. Make it data the config selects.
2. `Tasks.kt:12-13`: SIP blank thicknesses are a code map, and the prices sit in the tasks manifest. Move both to the catalog.
3. `ConstructionDomain.kt:20`: two-stacked-4x8, one-8x8 and four-4x4 should be one opening-grid solution that takes rows and columns.
4. `Placements.kt:14,60-68`: roof eaves on west and north only. Take one setting per side.
5. `tasks/manifest.json:259-276`: whole-job hours from tiny-house sources, divided by piece count by `ShareOfSpecHours`. Make them per-unit rates. The flow needs at :396-417 have no source row.
6. Rebuilt geometry: `LoadPathJson.kt:25-48`, `LoadPath.kt:28-40`, `HeaderCheckJson.kt:31-68`, `HeaderLoads.kt:38`, `Windows.kt:7-13,57`, `Integrity.kt:17-47`, `LightJson.kt:34-39`, `HeatNeedJson.kt:43-47`, `HeatNeed.kt:15-19` (the house as one box), and `JoistFraming.kt:3-13` (duplicates construction). These should use the engine's geometry and contacts.
7. Catalog facts read from config settings: `StructuralJson.kt:51` (modulus), `HeatNeedJson.kt:68-72` and `ThermalJson.kt:24` (R, U, SHGC). `LoadPath.kt:56-64` derives SIP density, which the catalog should publish.
8. `construction/steam/SteamTemperature.kt`: an unsourced steam domain living inside construction.
9. House-named text in `construction.domain.json:4,19,23`, `manifest.json:570`, and `mutation/house.config.json`.
10. `structural/manifest.json:239-249`: overlay display hints. These belong in the engine's overlay.
11. `catalog/manifest.json:95`: `size_factor_2x6`.
- The catalog uses evidence labels (published, inferred, visual-read, unpublished) and tasks uses (published, inferred, assumed). These collapse into research's `basis` once the manifest rows index lands.

## Config (world.json)
1. `joists.settings.modulus_mpa` 9653, with a formula written in its reason. Move to the catalog spf-no2 row.
2. `envelope.settings.wall_r`, `roof_r`, `floor_r`, `door_r`: these copy catalog product facts.
3. `walls.thickness_mm`, `floor.thickness_mm` 114, `loft_floor.thickness_mm` 18: stock facts. Set them null, as roof is.
4. `joists.member_width_mm` / `member_depth_mm`: pick a 2x6 stock solution instead.
5. Computed numbers: `floor.elevation_mm` -114, `joists.elevation_mm` 2298, `people.*.hours_per_step` 1/60.
6. `weather.u_value`, `solar_heat_gain_coefficient`, `finish.glass_transmittance`: a window catalog product is missing.
7. Code and site facts: egress minimums, live and dead loads, ground snow, frost line, climate. A site solution keyed by location should carry these.
8. `people_rules.level_max`, `learner_rate`: tasks-domain facts.
9. `heating.fuel_btu_per_unit`, `boiler_efficiency`: catalog facts.
10. Reasons that don't start with "assumed": `joists.reasons.spacing_mm`, `doors.reasons.offset_mm`.
11. Missing values treated as zero: `fields.py:26`, `check.py:173-174`, `check.py:66`.
12. `walls.panel_width_mm` 1219 should name the catalog width.

## UI (factored-ui application-look, kotlin-application)
1. `PageElevations.kt:11-16,50-68,154-166`: works out elevations and sections itself. This needs an engine view.
2. `PageCuts.kt:26-52`: cuts openings out of their hosts itself. Engine geometry should hand them over cut.
3. `PageVolume.kt:5,17-37,52-54,73-86`: falls back to its own stacking, guessed heights, and grade at 0.
4. `PageMaterials.kt:5-15`: a material table keyed by house system names. `Geometry.kt:15,47-51` drops the engine's material fields.
5. `PageBlueprint.kt:183-200`: picks out the walls on a side with a 200 mm band.
6. `PageElevations.kt:92-148`: guesses layer order and which pieces count as alike.
7. `PagePlan.kt:46-67,100-108`, `PageBlueprint.kt:112-123`: the plan is drawn from the expansion, not from `we geometry`.
8. `SheetSummary.kt:62-79`: hardcoded solver names, keys and units.
9. `ExportSheets.kt:56`, `SheetSummary.kt:99`, `PageCards.kt:8`, `Describe.kt:88`: find assumptions by searching the reason text for "assum" or "reading:".
10. `PageBlueprint.kt:77-85`, `DimensionChains.kt:28-41`, `PageElevations.kt:18-33`: work out dimensions themselves.
11. `PageTable.kt:13-19` (domain columns), `Overlay.kt:93-96` (legend stops), invented notes at `PageBlueprint.kt:214` and `SheetLayout.kt:104`, `RenderVolume.kt:251-257` (branches on material words), `RenderScene3d.kt:751-790` (UI physics).
- Clean: ranking, odds, board, build steps, solver cards, kotlin-engine, the playground, and the main factored-ui checkout.
