# small-house to world-engine: what the world still has to say, and who should say it instead

Branch `minimal-world`, 2026-10-16. The world is one file, `world.json`, 4232 characters compact (4767 as written), down from the
8-part world's 9878 compact. It loads on engine `be770b1` (`we run`), `we validate` says 1 valid, `we judge --embedded` passes its two
cases, and `python3 check.py` agrees 38 of 38 with both plants exiting 1. Every "refused without it" below was observed by removing the one
key from this world and running it (`we run` state step; `we validate` where named).

## What stays, because it is a choice about this house (about 1700 characters)

The grid (12 by 18 tiles of 305 mm, the sketch's grid). The field values the sketch gives: embedment 1219, floor 2438 by 2438, wall height
3658, roof 3658 by 5486, eaves 610, 630 board feet. The two open readings and their reasons (wall height, south hangover). The nine named
gaps with their sketch-specific reasons. The one rule: the roof covers the floor. Where things stand: floor at 2,2; roof at 0,0.

## Engine defaults: the same value in nearly every world

1. **`world_version: 2`, `version: 1`.** Refused without: `world-version-unsupported`, schema `missing 'version'`. Request: absent
   `world_version` reads as the engine's current version; absent `version` is 1. Case (`world_load`): this world with both keys removed
   loads; its state after the seed is byte-identical to the state with them. Saves 28.
   **Landed as a half, engine `c3fd62d`:** `version` defaults to 1 and the world no longer states it (case
   `load-a-world-without-a-revision-number-loads`; a version of 0 still refuses as `world-schema`). `world_version` stays required by
   world-engine's decision: a missing one is how a retired version-1 file is recognised, guarded by `load-world-without-a-version-is-refused`.
   Jim can overrule.
2. **`clock`.** Refused without: schema `missing 'clock'`. Nothing in small-house ticks. Request: a world with no `clock` has no time
   (every `age_s()` null) or the default second/86400; either is better than every world copying one line. Case: this world without `clock`
   loads and gives the same placements and tile counts. Saves 51.
   **Landed, engine `8af6be0`:** an absent clock ticks once a day (second, 86400) and the world no longer states one (case
   `load-a-world-without-a-clock-loads`); a stated clock is still checked whole, so `{"tick_unit": "second"}` alone refuses as
   `world-schema` (`load-a-clock-missing-its-tick-length-is-refused`).
3. **`stocks: [] agents: [] scoring: [] links: []`.** Refused without: `part-missing: stocks is required`. Request: an absent list is
   empty. Case: this world without the four loads; same state. Saves 56.
   **Landed, engine `56b95b2`:** each absent list is empty and the world states none of the four (cases
   `load-a-world-without-empty-lists-loads`, `load-a-directory-world-without-a-stocks-part-key-loads`); a list stated wrongly,
   `"agents": "none"`, still refuses as `world-schema`. Only `stocks` ever had a part file, so only it was ever refused `part-missing`.
4. **`actions`.** Refused without: schema `missing 'actions'`. Request: `place` and `remove` with their parameters are the engine's own
   verbs; a world states `actions` only to add a verb or take one away. Finding on the way: `place` declared with `parameters: []` loads and
   the seed places, so the parameter list is not read on the seed path today. Case: this world without `actions` loads; the seed places; a
   `place` attempt through the log applies and a `dig` attempt is refused. Saves 188.
5. **`grid.shape: "square"`.** Refused without: schema `missing 'shape'`. Request: default square. Case: same tiles without it. Saves 17.
6. **`title`.** Refused without: schema. Request: defaults to the id. Case: loads; the scene reports title `small-house`. Saves 57.
7. **`label` on each type** (6). Refused without: schema `matches none of its allowed shapes`. Request: a type's label defaults to its id.
   Case: a type with no label loads and the scene's type list shows label `post`. Saves 74.
8. **`kind: "design"` on each field** (15). Refused without: schema `missing 'kind'`. Request: default `design`, the one kind that needs
   no source; a sourced kind is stated. Case: a field with no kind loads and `we validate` files it under no sourced-kind fact. Saves 240.
9. **`unit: "mm"` on each field** (15). Not refused by the schema, but the rule then fails `unit_mismatch: '>=' compares mm with
   dimensionless`. Request: a field named `*_mm` is a length in millimetres unless it states a unit, the convention the engine already uses
   for `height_mm`, `footprint_mm`, `tile_mm`. Case: `floor.width_mm` with no `unit` and the rule comparing it to `0 [mm]` loads. Saves 180.
10. **`action: "place"` on each seed entry** (10). Refused without: schema. Request: a seed entry carrying `parameters.type` is a place.
    Case: the seed with no `action` keys loads to the same state. Saves 170.
11. **`id` on each seed entry** (10). Refused without: schema. Request (Jim's lean, 2026-10-16): identity is type plus position; the engine
    derives an id such as `post@2,2` (position, stack level if above 0) when none is given, and a stated id stays valid. Case: the seed with
    no ids loads; the state lists 10 objects; a `remove` at 9,9 removes the one derived `post@9,9`; the derived ids are the same on a second
    load. Saves 141. Caution from the design talk: moving an object changes its identity, so a log that points at it must be re-pointed or
    refused.

Done already by the engine, no request: `stack_level: 0` is the default and the posts no longer state it; `label` on an action is optional
and the `remove` action is gone because this world never removes.

## Domain library: reusable knowledge the world imports at a pinned version

12. **`object_types`: the six types with their fields** (2360 of 4232 characters, 573 of them `null_reason` strings). Today a domain file
    holds rules, equations and tables only (`domain_file` has `additionalProperties: false`), so a domain declaring a type is refused as
    `world-schema`. Request: a `structure` domain declares post, floor, wall, roof and glazing with their fields (embedment, height above
    grade, section, width, depth, thickness, eaves, glass and sill height), each null by default with the domain's reason ("a design choice no
    drawing has made yet"); the world `uses` it and states only the values it chooses and the reasons that are its own, in one place per
    type: `"fields": {"floor": {"width_mm": 2438, "depth_mm": 2438}, "post": {"embedment_mm": 1219, "above_grade_mm": {"null_reason":
    "the sketch's '?'"}}}`. Case: this world with no `object_types`, `uses` the domain and states `fields` as above; `we run` gives the
    same 10 placements, tile counts and null elevations as today; `we validate` 1 valid; `we judge` passes the two cases with their `edits`
    re-pointed at `["fields", "roof", "width_mm"]`. Saves about 1800.
13. **`footprint` on each type** (6). Refused without: schema. Request (the ruling we agreed): a type's size is one field; its tiles derive
    from `width_mm` and `depth_mm` as `footprint_mm` already derives them, ceil(mm / tile_mm). Today the floor says its width twice, 8 tiles
    (2440 mm) and 2438 mm. Case: a floor with `width_mm`/`depth_mm` fields and no footprint covers 8 by 8 tiles and the rule still reads
    2438. Open inside this: the wall's footprint `[8, 1]` asserts a 1-tile thickness that `thickness_mm: null` says is unknown. A derived
    footprint from a null thickness is null, and a null-thick object cannot take a tile. The engine needs a word for "occupies the tile its
    line falls on" before the wall can drop its footprint. Saves 104.
14. **`bears_on` and `bearing` on floor and roof.** Refused without: `floor at 2,2 at stack level 1 has nothing under tile 3,2 at stack
    level 0` (the engine's `nothing-below`). Request (the ruling): bearing is computed from positions, never stated. The engine stops
    requiring something under every tile; what an object rests on is a computed field (`supports`, the distinct objects under any of its
    tiles one level down), and "a floor needs a post under each corner" is a rule from the domain, so a missing corner post is a rule refusal
    naming the corner, not an engine refusal. Case: a floor with no `bears_on` over four corner posts is placed and its `supports` reads the
    four; the same floor over three posts is refused by the domain rule `floor-on-four-corners` at the missing corner. The `corner-post-
    removed` plant in `check.py` then expects that rule's refusal. Saves 69, and the engine loses two construction-shaped keys.
15. **`wall_ns`, a second wall type.** It exists only because `place` has no rotation. Request: a quarter-turn on `place` (`turn: 1`) so
    one wall type stands on any edge, or the pattern in 16. Case: `wall` placed at 2,3 with one turn covers tiles 2,3 to 2,8. Saves 48 and a
    type.
16. **The ten seed entries** (885). Request: patterns, expanded by a world-supplied expansion solver (the model from the design talk). The
    world states `floor at 2,2` and three pattern uses, `posts-at-corners(floor)`, `walls-on-edges(floor)`, `roof-over(walls, west_eave,
    north_eave)`; expansion yields the four posts, four walls and roof at the positions and stack levels the seed states today. Case: the
    world with one seed entry and the three patterns expands to the same 10 objects as today's seed; expanding twice gives the same set; a
    pattern whose parameter changes the count (a fifth post) runs before any that reads the count. Saves about 700.
17. **`height_mm: "post_height"` and the `post_height` equation.** The engine's stacking height is the type's `height_mm`, an integer or an
    equation id, and a null height has no spelling; the equation `self.above_grade_mm` is the shim that makes it null. Request: an object's
    height is its `height_mm` field like any other, one source. Case: a post with `above_grade_mm` null gives the floor a null `z_mm`;
    stated 610, the floor's `z_mm` is 610, with no equation in the world (today's `check_stated_height` proves the same by the shim). Saves
    about 110.
18. **`sketch_board_feet` as a constant equation with `unit: "1"`.** A supplied world-level figure has no slot of its own, so it is spelled
    as an equation. Request: a world-level supplied field (`"fields": {"world": {"board_feet": 630}}`) and `board_foot` as a unit in
    `units.json`, so the dropped `board_foot_volume` constant is the domain's, not the world's. Case: the field reads 630 board_foot in
    `outputs`, converts to 1.48663 cubic metres. Saves about 100.
19. **The `roof-covers-floor` rule.** Stays as Jim's what. Its expression (four clauses over six fields) is domain-shaped: a domain measure
    `overhang_mm(roof, floor)` per side lets the rule read `min(overhang_mm(roof, floor)) >= 0 [mm]`. Low priority. Saves about 150.

## Findings, not requests

- `we run` loads a null default with no `null_reason`; `we validate` refuses it (`property-null-reason`). The loader and the validator
  disagree, so a world can run that cannot validate.
- `part-missing` on a single-file world names a part file that does not exist ("neither world.json nor people.json holds it").

## Sum

Requests 1 to 11 save about 1200 characters and need the engine only. Requests 12 to 18 save about 2900 and need the domain library plus
three engine changes (types in a domain, fields overriding a domain default, bearing as computed). Both together leave a world of about
1500 characters: the choices listed at the top and nothing else.

## Landed: the supplied 630 board feet

Engine `6a284cf` lets a config's supplied figure use a unit its used domain defines. `supplied.board_feet` is back in `world.json` and `we expand`
prints it under `supplied`.

## Open, 2026-10-20: material_source from an expander, and a budget weight

- **A piece's `material_source` from the expander that names its material.** `pieceRow` (`ContactsInput.kt`) sets `material_source` only
  from the system's own solution spec, so every piece of this house, whose material the construction and structural expanders copy from a
  catalog role, reports `material_source: null` though the expander knows the row (`wt.syn_post_6x6`, `lum.nds.fv_spf_no2`). Case: `we geometry
  world.json` on this world; want each piece's `material_source` to be the row the expander gave beside `material`.
- **Score a run by a stock against its target.** `stocks.budget_usd` is now a target with no floor; `optimizing.weights` takes only the names
  fixed at `Crew.kt:23`, so no weight can score the overrun. Case: this world with `stocks.budget_usd` 1000 (check.py's small-target run).
