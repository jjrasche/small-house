# small-house

Jim's pencil sketch of a small house on posts as one world config on the world engine: `world.json` holds systems (foundation, floor, walls,
roof, glazing, plus weather and finish for the solvers), each with the solution chosen for it from a domain and the settings the sketch gives,
and the sketch's board feet as a supplied figure. It states no objects, overrides nothing and holds no logic: an 8 by 8 ft floor at 610 mm, 610 mm
on four corner posts buried 4 ft, walls about 12 ft along its edges, a flat 12 by 18 ft roof over them with 2 ft west and north eaves, and (Jim,
2026-10-17) one 8 by 8 ft window on the south wall over a 4 ft SIP knee wall. Charter: `~/.claude/brothers/charters/small-house-charter.md`.
Vocabulary: system, rule, solution, setting, placement; "group", "pattern", "goal" and "job" are retired.

- **Domains:** kotlin jars (construction, light, thermal) and `physics.domain.json`, kept in `domains/`, each pinned in `uses` by the sha256 of its
  bytes. They are built in `../domains/kotlin` (one Gradle project each, tests there). Never edit them to make this world pass; change the world
  or send the domain a request with a case. `binds` names which system fills each solver role.
- **Engine:** `../world-engine` (or `WORLD_ENGINE_DIR`); `engine.pin` names the commit whose commands this world needs. Never edit the engine.
- **The one command:** `python3 check.py` (standard library only): the pins match the bytes, `we expand` places 10 objects and 1 window and
  carries 630 board feet, `we solve` answers a daylight factor of 7.365 percent and 332.855 W lost, 1783.153 W gained through the glass.
  `<n> of 9 small house checks agree`, exit 1 on any difference; `--plant domain-pin-stale` must exit 1.
- **Assumed, not Jim's:** weather and finish settings carry reasons beginning "assumed"; the solver applies one sun figure to every side.
- **Two named readings**, open until Jim says otherwise, each a `reasons` entry starting `reading:`: 12 ft is wall height, floor top to roof
  underside (not overall above grade); the hatched hangover strip is on the south (not centred, 5 ft each end).
- **Named gaps:** a null setting with its reason for what the sketch does not give (post height above grade and section, each member's
  thickness); the loft's own heat zone and the SIP wall are not modelled; cost and hours wait for tasks.
- **Jim's rulings to hold:** posts are their own system, not the floor's; nothing he reads carries tiles, col/row or a footprint in tiles,
  positions and sizes are millimetres; light, sound and thermodynamics are their own domains. The request list is `requests/world-engine.md`.
