# small-house

Jim's pencil sketch of a small house on posts as one world config on the world engine: `world.json` holds five systems (foundation, floor,
walls, roof, glazing), each with the solution chosen for it from the construction domain and the settings the sketch gives, and the sketch's
board feet as a supplied figure. It states no objects, overrides nothing and holds no logic: an 8 by 8 ft floor at 610 mm, 610 mm on four
corner posts buried 4 ft, walls about 12 ft along its edges, a flat 12 by 18 ft roof over them with 2 ft west and north eaves, glass high on
the south and east sides. It is the reference world for the smallest honest syntax (charter:
`~/.claude/brothers/charters/small-house-charter.md`). Vocabulary: system, rule, solution, setting, placement; "group", "pattern", "goal"
and "job" are retired.

- **Domain library:** `../domains` (or `DOMAINS_DIR`), pinned by the sha256 of `construction.domain.json` in `uses`. It owns the types, the
  systems with their rules and the solutions with their placements, all written to the engine's contract. Never edit the domains repo to make
  this world pass; change the world or send the domain a request with a case.
- **Engine:** `../world-engine` (or `WORLD_ENGINE_DIR`); `engine.pin` names the commit whose contract this world targets. The engine reads
  domain files (contract v1, `$defs/domain_file`) but not yet a world config that picks a solution; world-engine sends that shape before
  building the expansion, and `world.json` is written against a draft of it. Never edit the engine.
- **The one command:** `python3 check.py` (standard library only). It writes a scratch world carrying this world's `uses` entries beside copies
  of the domain files and runs `we validate`, so a domain edited since the world pinned it, or one the contract refuses, fails here. One
  `agrees`/`differs` line a pinned domain, the validator's count, `<n> of 2 small house checks agree`, exit 1 on any difference;
  `--plant domain-pin-stale` must exit 1. The expansion checks return when the engine reads the world config.
- **Two named readings**, open until Jim says otherwise, each a `reasons` entry starting `reading:`: 12 ft is wall height, floor top to roof
  underside (not overall above grade); the hatched hangover strip is on the south (not centred, 5 ft each end).
- **Named gaps:** a null setting with its reason for what the sketch does not give (post height above grade and section, each member's
  thickness, glass height and sill); cost and hours wait for tasks.
- **Jim's rulings to hold:** posts are their own system, not the floor's; nothing he reads carries tiles, col/row or a footprint in tiles,
  positions and sizes are millimetres. The request list that led here is `requests/world-engine.md`; its engine defaults 1 to 4 landed.
