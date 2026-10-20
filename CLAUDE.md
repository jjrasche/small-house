# small-house

Jim's pencil sketch of a small house on posts as one world config on the world engine: `world.json` holds systems (foundation, floor, walls,
roof, glazing, plus weather and finish for the solvers), each with the solution chosen for it from a domain and the settings the sketch gives,
and the sketch's board feet as a supplied figure. It states no objects, overrides nothing and holds no logic: an 8 by 8 ft floor at 610 mm, 610 mm
on four corner posts buried 4 ft, walls about 12 ft along its edges, a flat 12 by 18 ft roof over them with 2 ft west and north eaves, and (Jim,
2026-10-17/18) two stacked 4 by 8 ft windows on the south over a 4 ft SIP knee wall and no other glass, a 4 by 8 ft door on the north, and a
sleeping loft floor 8 ft up on 2x6 joists. Charter: `~/.claude/brothers/charters/small-house-charter.md`.
Vocabulary: system, rule, solution, setting, placement; "group", "pattern", "goal" and "job" are retired.

- **Domains:** kotlin jars (construction, light, thermal, structural, catalog, tasks) and `physics.domain.json`, kept in `domains/`, each pinned in `uses`
  by the sha256 of its bytes. The catalog is data only: the SIP panel and SPF No. 2, each figure naming its research row. They are built in `../domains/kotlin` (one Gradle project each, tests there). Never edit them to make this world pass; change the world
  or send the domain a request with a case. `binds` names which system fills each solver role.
- **Engine:** `../world-engine` (or `WORLD_ENGINE_DIR`); `engine.pin` names the commit whose commands this world needs. Never edit the engine.
- **How every simulation question is answered:** change `world.json` (a what-if is an edit of it; git history is the undo; one config file per world, no branch per world), run `python3 fields.py`, and
  report the fields it prints. It computes nothing; each line is a value `we expand`, `we solve`, `we evaluate` or `we simulate` returned. A figure not printed there is not an answer
  about the house; say so and say what config or domain piece would produce it.
- **The one command:** `python3 check.py` (standard library only): the pins match the bytes, `we expand` places the objects and openings, `we
  evaluate` passes the rules, and `we solve` answers the daylight factor, the glass heat balance, the design-day load, the heating season, the joist
  deflection, the gravity load path and the build tasks' hours at published rates, and `we simulate` answers the minute each piece is placed,
  the labour hours, cost, budget left and skills, each figure compared with the value pinned in check.py. `<n> of <m> small house checks agree`, exit 1
  on any difference; `--plant domain-pin-stale` must exit 1.
- **Gravity load path** (`binds`: house parts, panel_pieces, lumber_pieces, occupied_floors, ground, openings): self-weight is volume times the
  catalog density, the occupancy load is the live load on each floor, and a piece's force splits over its contacts by contact area (an
  approximation). A piece the engine cannot measure, or one an unmeasured piece may rest on or be cut from, reports `{unknown: why}`.
- **Headers** (`header`, `roof_loads`, `binds.header_check`): `header-check` loads each opening's header with the roof (dead load plus
  ground snow over the roof's reaction width on that wall) when nothing is above it, and the loft joists landing at its head; it reports
  stress, deflection and utilisation per opening, and the rule `headers-within-capacity` names any over 1. The window-wall options are
  `glazing` solutions (two-stacked-4x8, one-8x8, four-4x4) and the header options catalog `header` solutions; compare them by editing a
  copy of world.json and running fields.py on it (`--use` clears settings). `we rank --system glazing` ranks on first cost and build
  hours, both still gaps.
- **Build run** (`clock`, `stocks`, `people`, `optimizing`, `people_rules`): a step is one working minute; the tasks domain digs the post holes,
  then sets the floor, wall and roof panels, each ready only when what it rests on is placed, half a man-hour of work at the required level
  per run. `stocks.budget_usd` is Jim's $20,000 limit: a task whose cost would breach it waits.
- **Assumed, not Jim's:** weather and finish settings carry reasons beginning "assumed"; the solver applies one sun figure to every side. The
  people (`jim` a beginner at SIP setting, `sip_lead` advanced), `people_rules.learn_rate` and the `optimizing` weights are assumed for Jim to
  overturn; `learner_rate` is inferred from the deck guide's levels.
- **Two named readings**, open until Jim says otherwise, each a `reasons` entry starting `reading:`: 12 ft is wall height, floor top to roof
  underside (not overall above grade); the hatched hangover strip is on the south (not centred, 5 ft each end).
- **Named gaps:** a null setting with its reason for what the sketch does not give (post height above grade and section, roof and loft deck
  thickness); SPF density is not banked, so no joist has a weight; the roof sits at elevation 0, not on the walls, and no
  window or door has a material; the loft's own heat zone is not modelled; tasks with no published hours (set posts, subfloor, openings,
  windows and door, loft, boiler) never run, so hours and cost cover the holes and panels only, and cost is the panel blanks' list price.
- **Jim's rulings to hold:** posts are their own system, not the floor's; nothing he reads carries tiles, col/row or a footprint in tiles,
  positions and sizes are millimetres; light, sound and thermodynamics are their own domains. The request list is `requests/world-engine.md`.
