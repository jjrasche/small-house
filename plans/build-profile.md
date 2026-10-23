# Gamebox build profile (2026-10-23)

Every figure below is what the runner recorded in a run's result.json: `duration_s` is the wall time, and `peak_working_set_mb`
is the peak working set of the whole build tree, sampled during the run, next to `largest_process`. Sources: the 39 runs
already fetched under `~/build-out/`, `gamebox-build status` for 35 more run ids found in notes, and two runs started for
this profile (below). A figure is a range over runs (min / median / max), never one run picked out.

## Wall time and peak per task

| task | runs read | wall time s (min / median / max) | peak MB (min / median / max) | largest process at the peak |
|---|---|---|---|---|
| domain-jars | 16 | 38.5 / 52.2 / 89.9 | 620 / 990 / 1843 | java.exe 364 to 1597 |
| domain-tests | 17 | 100.1 / 218.9 / 308.9 | 1228 / 1811 / 2617 | java.exe 1006 to 1458 |
| engine-cli | 5 | 41 / 72.2 / 76.4 | 994 / 1225 / 1312 | java.exe 941 |
| engine-judge | 1 (20261023T020210-8346) | 207.4 | 1250 | java.exe 1003 |
| engine-mutants | 3 | 85 / 441 / 7201 | 1509 / 1542 / 2640 | java.exe 1045 to 1282 |
| factored-ui-server | 4 | 57.5 / 69.3 / 83.3 | 1138 / 1294 / 1418 | java.exe 881 to 1171 |
| factored-ui-wasm | 7 | 198.6 / 245 / 343.5 | 2222 / 2474 / 4400 | wasm-opt.exe 1358 to 1398 (light runs), java.exe 2583 to 2723 (heavy runs) |
| we-sample | 1 (20261023T020610-0bfd) | 128.3 | 1472 | java.exe 1220 |

- engine-judge and we-sample had no recorded peak before today: the one earlier judge run (20261021T021213-7d5f) was DEFERRED
  at the start and kept none. we-sample's run used the engine's fixture `worlds/sample-knobs.config.json`, 20 runs, seed 1; its
  sample step took 2.8 s, so the figure measures the compile, not a house-sized sample. A house sample's peak is NOT READ.
- engine-mutants: the 7201 s run was `--jobs 2 --full` stopped by the then 120-minute cap; its peak of 2640 MB is the only
  full-run figure, and `--jobs` is now held at 1. A full run at `--jobs 1` is NOT READ.
- In both new runs the peak fell inside the `cli-classes` compile step (peak_at 02:04:02 and 02:08:14 UTC, inside steps
  ending 02:04:06 and 02:08:16), not in judge or sample.

## What sets each peak

Every Gradle step is launched by the runner as
`gradlew.bat --no-daemon --max-workers 4 -Dorg.gradle.jvmargs=-Xmx3g -Pkotlin.compiler.execution.strategy=in-process`.
What follows from that line and from the repos' own files:

1. **Two JVMs per step, always.** All 39 fetched logs print "To honour the JVM settings for this build a single-use Daemon
   process will be forked". Gradle: "If the JVM args of the client process don't match what the build requires, a single-used
   Daemon (disposable JVM) is created", and "If the JAVA_OPTS and GRADLE_OPTS match org.gradle.jvmargs, the Daemon will not be
   used at all since the build happens in the client JVM" (docs.gradle.org/8.14/userguide/gradle_daemon.html). The peak minus the
   largest process is 246 to 257 MB in every jars, engine-cli, judge, sample, server and single-mutant run: that is the client
   JVM and its shells, held for the whole build (domain-tests runs it 289 to 348 MB, the client plus a test JVM).
2. **The compiler lives in the daemon's 3 GB heap.** Kotlin's in-process strategy runs the compiler "inside the build tool's
   process" (kotlinlang.org/docs/compiler-execution-strategy.html), so the daemon's working set is the compile, capped only by
   `-Xmx3g`. The repo settings that would say otherwise are dead under this runner: factored-ui's `gradle.properties`
   `org.gradle.jvmargs=-Xmx3072m` is overridden by the command line's `-D`, and its `kotlin.daemon.jvmargs=-Xmx4096m` names a
   Kotlin daemon the in-process strategy never starts. domains/kotlin and world-engine/kotlin have no `gradle.properties` at all.
3. **factored-ui-wasm's 4.4 GB is two processes stacked.** In the three heavy runs (`:kotlin-compose:compileKotlinWasmJs` executed,
   nothing from cache) the daemon holds 2583 to 2723 MB after the Kotlin compile and link, and binaryen's `wasm-opt.exe`
   (1358 to 1398 MB in the light runs) runs in `compileProductionExecutableKotlinWasmJsOptimize` while the daemon still holds that
   heap: 2723 + about 1400 + the 250 MB client is the 4400 MB recorded. The light runs (kotlin-compose from cache) peak at 2222 to
   2474 MB with wasm-opt as the largest process. webpack ran in 6.3 s and never was the largest process.
4. **world-engine compiles from nothing every run.** The runner adds a fresh `git worktree` for each engine task, so
   `build/` is empty and `compileKotlinJvm` executes every time (executed=3, up_to_date=0 in every engine run, 41 to 118 s), and
   world-engine/kotlin sets no `org.gradle.caching`, so no cache can stand in. domains, by contrast, is checked out and
   `git clean -fdq` (no `-x`, so `build/` survives): its jar runs with 61 to 63 tasks up to date peak at 620 to 1014 MB, against
   1843 MB for the one full compile (65 executed).
5. **domain-tests rebuilds everything on purpose.** The runner passes `--rerun-tasks` (forced_rerun=true in every run), which
   Gradle describes as "similar to running gradle clean test" (command_line_interface.html), so 16 projects' main and test
   sources recompile in the 3 GB daemon each run (98 executed), on top of the test JVM.
6. **Parallelism is not the peak.** No repo sets `org.gradle.parallel` and the runner passes no `--parallel`; Gradle "by default
   ... runs only one task at a time" across projects (performance.html), so `--max-workers 4` does not put four test JVMs or four
   compiles side by side. No build sets `maxParallelForks` or `forkEvery` (Gradle defaults: 1 and 0). What the gamebox's own
   `~/.gradle/gradle.properties` sets is NOT READ (the gate does not expose it).
7. **engine-mutants builds again inside its step.** `CliMutants.kt` `buildModule` runs `gradlew.bat --no-daemon -q
   -Pkotlin.compiler.execution.strategy=in-process cliClasspath` on each mutant's copied module with no `-Dorg.gradle.jvmargs`
   (so Gradle's default "up to 512MB of heap" daemon plus a client), then `java ... worldengine.Cli judge` (line 133) with no
   `-Xmx`, which leaves that JVM at the JVM's default ceiling; `we.cmd` likewise starts its java with no `-Xmx`. Which of these
   holds the mutants peak is NOT READ: result.json keeps only the largest process, not the tree.

## One change per task most likely to cut peak memory

Each is a proposal to try as one change per run on the gamebox, with that run's peak compared to the table above; none was run.
Estimates marked "derived" are arithmetic on the recorded processes, not a measurement.

| task | change | where it lives | expected effect |
|---|---|---|---|
| domain-jars | set the step's `-Dorg.gradle.jvmargs` to `-Xmx1536m` (the full compile's daemon touched 1597 MB under a 3 GB cap; a lower cap makes G1 collect instead of grow) | runner catalog (build-gate.ps1 on the gamebox) | full-compile peak below 1843 MB; risk an OutOfMemoryError, which the run would show |
| domain-tests | replace `--rerun-tasks` with `test --rerun` ("Causes the task to be rerun even if up-to-date ... for a specific task") so only tests re-execute and the compiles stay up to date | runner catalog | peak toward the up-to-date jar runs (620 to 1014 MB) plus the test JVM, from 1811 MB median; whether `--rerun` reaches every project's `test` from one selector is unverified |
| engine-cli | add `org.gradle.caching=true` so `compileKotlinJvm` comes from the local build cache that outlives the fresh worktree | new world-engine/kotlin/gradle.properties | the 994 to 1312 MB compile peak replaced by a cache load on an unchanged engine; the first run per sha still compiles |
| engine-judge | same build-cache change (its peak, 1250 MB, is the cli-classes compile) | world-engine/kotlin/gradle.properties | as engine-cli |
| we-sample | same build-cache change (its peak, 1472 MB, is the cli-classes compile) | world-engine/kotlin/gradle.properties | as engine-cli; a house-sized sample's own peak is unmeasured and may then be the peak |
| engine-mutants | give the mutant judge JVM a heap cap (`-Xmx` in the command at CliMutants.kt line 133) and the mutant rebuild a `-Dorg.gradle.jvmargs` | world-engine kotlin/src/jvmMain/kotlin/worldengine/CliMutants.kt | unverified until a run records which process holds the peak |
| factored-ui-server | run the build in the client JVM: set `GRADLE_OPTS` to the step's jvmargs so no single-use daemon is forked | runner environment for the step | about 250 MB less (derived: peak minus largest process is 247 to 257 MB in its 4 runs) |
| factored-ui-wasm | split the step in two Gradle invocations: `:kotlin-compose-playground:compileProductionExecutableKotlinWasmJs`, then `:kotlin-compose-playground:wasmJsBrowserDistribution`, so the 2.7 GB compile daemon has exited before wasm-opt starts | runner catalog | derived: heavy-run peak from 4400 MB to about the larger of the two halves, near 3000 MB; one extra JVM start (tens of seconds) |

## Top three levers

1. **Split factored-ui-wasm's compile from its binaryen step** (runner catalog, `wasm-bundle` step): the only task over 2.7 GB,
   and the one the gate holds at a 6.22 to 7.22 GB start floor ("measured peak 4.22 GB"), so it is the one most often DEFERRED
   (9 of the 34 status-read runs were factored-ui-wasm DEFERRED).
2. **Stop recompiling unchanged code:** `org.gradle.caching=true` in world-engine/kotlin/gradle.properties (four engine tasks
   compile from nothing every run) and `test --rerun` in place of `--rerun-tasks` for domain-tests (runner catalog).
3. **No single-use daemon:** `GRADLE_OPTS` equal to the step's `-Dorg.gradle.jvmargs` in the runner's environment, about 250 MB
   off every Gradle step of every task.

## Not measured

- A house-sized we-sample and a full engine-mutants run at `--jobs 1`.
- Which process holds the peak beyond the largest one: result.json keeps no per-process tree.
- The gamebox's `~/.gradle/gradle.properties` and `build-gate.ps1` source, which the gate does not expose.
- Whether any change above holds: none was run.

Runs started for this profile, one at a time, both after a dry run said GO: engine-judge 20261023T020210-8346 (PASS) and
we-sample 20261023T020610-0bfd (PASS), both on world-engine master 5d5a58e, unchanged settings.
