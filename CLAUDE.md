# small-house

Jim's pencil sketch of a small house on posts as one world on the world engine, kept as part files at the root (world.json, types.json,
equations.json, rules.json, people.json, placements.json, views.json, cases.json): an 8 by 8 ft floor on four posts buried 4 ft, walls about
12 ft, a flat 12 by 18 ft roof, glass high on the south and east. The seed places the four corner posts, the floor on them (`bearing:
corners`), four walls on the floor and the roof over the walls (`bearing: any`).

- **Engine:** the Kotlin line at `../world-engine` (or `WORLD_ENGINE_DIR`); `engine.pin` names the commit, and the check refuses an engine
  that does not contain it. Never edit the engine.
- **The one command:** `python check.py` (standard library only). It prints one `agrees`/`differs` line a check and `<n> of 56 small house
  checks agree`, exit 1 on any difference; `--plant roof-smaller-than-floor` and `--plant corner-post-removed` must exit 1.
- **Two named readings**, open until Jim says otherwise: 12 ft is wall height, floor top to roof underside (not overall above grade); the
  hatched hangover strip is on the south (not centred, 5 ft each end).
- **Named gaps:** a null default with its `null_reason` for what the sketch does not give (post height above grade, glass height and sill,
  each member's section), so the post's whole length and the floor and roof elevations read null; cost and hours wait for tasks.
