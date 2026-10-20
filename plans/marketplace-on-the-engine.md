# The task board as an application on the engine

Plan only, 2026-10-20. Nothing built. This replaces the separate web stack in
`task-marketplace-design.md` §11–12. Identity (Zitadel behind Pomerium), consent and the legal
items in that document still stand.

The idea: the house is one world on the engine and factored-ui draws it. The board is a second
world on the same engine. It chooses a `marketplace` domain, and factored-ui draws it the same way.

## 1. What the engine lacks (read from world-engine kotlin/src on 2026-10-20)

The engine is a pure function: one config in, JSON out. These are the gaps.

| need | today | evidence |
|---|---|---|
| A viewer's write: someone signs up or withdraws | No write path. `WorldFiles` is read-only. `--set` and `--use` change the parsed config in memory and never save it | `Files.kt:9-20`, `WhatIfConfig.kt:28-40` |
| Keeping that write | `contract/change.schema.json` already defines an append-only change log with `actor`, and actions that include `enroll`, `opt_in` and `run_task`. The engine loads it only in a schema test | `jvmTest/LoadSchemaTest.kt:33` |
| Identity | None: no viewer, no auth, no HTTP. The engine only ever sees `actor` as a string | grep of kotlin/src for viewer, auth, session, http and user |
| People from outside the config | `simulate` has no `--people` flag. People must sit inside the config | `CliSimulate.kt:5`, `Crew.kt:91` |
| One world reading another world's output | None. `reads_from` works between domains inside one config. The world schema refuses unknown keys | `CrossDomainReads.kt:13-60`, `world.schema.json:450-480` |
| Assigning a person only to flows they consented to | `bestTeam` picks from every free person | `Crew.kt:129-132` (R2 in the design) |

These would go to the engine as requests, each with a case. None is sent yet.

- **E1. `we commit CONFIG CHANGE.json`.** The engine checks the change against the domain's declared
  change kinds, stamps `id`, `parent` and `touches`, and appends it to the log that the config names
  (`changes: {file}`). `load` and `simulate` fold the log into the state. This is the only write
  path. The host never edits world.json. The schema's `touches` still has tile patterns
  (`col,row`), which Jim retired. The request asks for them to become ids and millimetres.
- **E2. `actor` comes from the host.** The engine does not authenticate anyone. It records the
  `actor` it is given and refuses a change whose actor the domain says may not make it, such as
  withdrawing someone else's sign-up. Identity is the host's job (§3).
- **E3. A world reads another world's output.** For example
  `reads_world: {id: small-house, file, commands: [solve, simulate]}`, pinned by the world file's
  sha256 like `uses`. Without it, a script outside the engine would copy figures, and that breaks
  "computes nothing".
- **E4. The crew matcher restricts each person to their `flows`.** This is R2.

## 2. The domain and the config

**`marketplace` domain**, a kotlin jar in `../domains/kotlin/marketplace`, tested there:
- system `postings`, solution `from-world`: one posting per flow of the world it reads. Each
  posting carries the flow's label, its needs, `*_hours`, the minute range, `waiting.why`, and the
  heaviest piece's `weight_n`, all copied from engine output. Pay is the setting `rate`: `null`,
  reason "Jim has not set pay". So the page reads "rate TBD", and that comes from the config.
- change kinds `enroll` (flow, self-reported skill levels, `hours_per_step`, consent version) and
  `withdraw`. Rule `signup-needs-consent`.
- solver `people-overlay`: it folds the change log into `people` records in the `Crew.kt` shape
  (`skills`, `certifications`, `hours_per_step`, plus `flows` once E4 lands). The id is
  pseudonymous.
- a FLOW that runs the house world's simulate with that overlay, and returns each person's
  assignment rows or their `whyNoTeam` reason. It is shown only after E4.

**`task-board/world.json`** (its own repo, one config): `uses` the marketplace jar; `reads_world`
the small-house world; `changes: {file: signups.log.json}`, which stays out of git; and settings for
the consent version and the age gate. Names and emails stay in the host, keyed by the pseudonymous
actor.

## 3. What factored-ui needs (read from the application-look worktree)

Today `kotlin-application` serves GET `/`, `/spec.json` and the bundle, reads no request header,
and the page's only action, `set_binding`, "never reaches the host" (`PageServer.kt:213-219`,
`RenderContext.kt:166-175`).

- **U1. A host action route.** `POST /action {verb, args}`. The server turns it into
  `we commit <world> <change>` and re-runs `load`. This means a `submit` action in the spec, and
  `card`/`button` nodes whose action names a change kind from the domain. The renderer already has
  `list`, `card`, `button`, `textinput`, `select` and `toggle` (`RenderNode.kt:246-305`).
- **U2. Identity at the host.** Read `X-Pomerium-Jwt-Assertion`, check it against Pomerium's JWKS
  (`aud`, `iss`, `exp`), and pass `sub` as the change's `actor`. On the tailnet, before Pomerium,
  this sits behind the same interface as a dev identity that is clearly marked as temporary.
- **U3. Generic drawing of postings.** A domain's `postings` system is drawn as a list of cards from
  `describe` and solve output, with no per-domain code. This matches how the page draws systems
  today (`PagePlan.kt:18-22`).
- **U4. Invalidating the cache on a commit.** The spec cache is keyed by the world file's mtime and
  size (`PageServer.kt:175`). It also has to key on the change log.

## 4. Order

E1+E2 and U1+U2 are the first slice: a stranger enrolls in `dig-post-holes`, and the change log
holds it. Then E3, so postings come from the house world. Then E4 for matches. The Pomerium route
and the Zitadel client wait for Jim's yes on going public.
