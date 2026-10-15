# small-house

Jim's pencil sketch of a small house on posts as one world on the world engine, kept as part files at the root (world.json, types.json,
equations.json, rules.json, people.json, placements.json, cases.json): an 8 by 8 ft floor on four posts buried 4 ft, walls about 12 ft, a flat
12 by 18 ft roof, glass high on the south and east. The seed places the four posts only.

- **Engine:** the Kotlin line at `../world-engine` (or `WORLD_ENGINE_DIR`); `engine.pin` names the commit, and the check refuses an engine
  that does not contain it. Never edit the engine.
- **The one command:** `python check.py` (standard library only). It prints one `agrees`/`differs` line a check and `<n> of 39 small house
  checks agree`, exit 1 on any difference; `python check.py --plant roof-smaller-than-floor` must exit 1.
- **Two named readings**, open until Jim says otherwise: 12 ft is wall height, floor top to roof underside (not overall above grade); the
  hatched hangover strip is on the south (not centred, 5 ft each end).
- **Named gaps:** a null with its reason for what the sketch does not give (post height above grade, glass sizes, member sections, cost,
  hours); a floor bearing on four corner posts and a roof bearing past its walls; inspection tasks shared with the house world. The check
  asserts the engine still refuses the null field and both bearings, so a line flags when the engine changes.
