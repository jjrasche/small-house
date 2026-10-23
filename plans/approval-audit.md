# Why the world-engine seat asks for approval so often

Source: session ee60ca69 (world-engine seat), 2026-10-08 to 2026-10-23, 45,416 transcript lines, copied from the gamebox read-only.
Counts are deduplicated: the transcript replays ~16 prompts and ~9 denials after a resume, collapsed by tool-use id and timestamp.
Prompts are tool results carrying `permissionDecision.source = user_temporary` (Jim answered a dialog). Denials carry `toolDenialKind` or a
`Blocked:` / `hook error` result (no dialog; the seat retries).

Finding: the environment is set up wrong in two places, both in the gamebox PreToolUse hook and its settings, and one was already fixed on 2026-10-22.
The hook returns `ask`, and a hook `ask` prompts even under `bypassPermissions` (the session spent 631 mode records in bypass and 461 in auto; the prompts occurred in both).

## Totals

Total prompts (Jim answered a dialog): 107 accepted, plus 1 rejected, 1 closed unanswered, 3 interrupted = 112.
Total denials (hook or tool refusal, seat retries, no Jim): 31.
Turns where the seat stopped and asked Jim for a go: about 33 (25 memory-kill or queue rule, 8 chosen).

| Class | Count | What |
|---|---|---|
| SETUP | 112 prompts | 80 Bash hook asks (heredoc prose matched `env\|set\|printenv`), 21 Edit/Write outside workspace roots, 6 Bash/Read on vps1 with no hook ask, 5 rejected/closed/interrupted of the same kinds |
| SETUP | 31 denials | command shapes the hooks refuse (below) |
| RULE | about 25 stops | memory-kill notice (harness) and the gamebox queue's "judge and full mutants wait for Jim's own go" |
| SEAT | about 8 stops | the seat asked when nothing required it |

## SETUP: prompts

| Class | Count | Cause | Fix |
|---|---|---|---|
| SETUP | 80 | `PreToolUse.js` before 2026-10-22 tested `/\b(env\|set\|printenv)\b/` and `/\b(echo\|printf\|cat)\s+.*>\s*\./` against every `;`/`&`/`\|`-split piece of the command, heredoc bodies included. Any `python - <<'EOF'` with `set(`, `seen=set()` or a `cat > ./x` in prose returned `ask` "Potentially dangerous". | Fixed 2026-10-22 18:57 (hook now calls `environment-dump-guard.js`, which strips data heredocs). Differential: the old patterns reproduce 80 of the 85 Bash prompts; the current hook and guard reproduce 0 of 85. No Bash hook ask appears after 2026-10-22T11:06Z. Nothing more to change; do not add an allow rule (a hook `ask` is not overridden by `allow`). |
| SETUP | 21 | `Edit`/`Write outside workspace roots`. Roots are the session cwd plus `permissions.additionalDirectories`; the gamebox global list is `[]` and world-engine has no `.claude/settings*.json`. A persisted `cd` left cwd at `.git-worktrees/we-build-shorttitle/kotlin/src`, so every edit in a sibling worktree (we-build-verify, we-build-servejoin, we-build-gradlecache) counted as outside. All 21 are on 2026-10-23, after the Bash fix, so this is the live cause. | In the gamebox `~/.claude/settings.json` set `"additionalDirectories": ["C:/Users/falcon-ridge-bmax/workspace"]` (the hook reads the global list). Seat-side: keep Bash cwd at the repo root and pass absolute paths. |
| SETUP | 6 | vps1, auto mode, no hook ask: `cd X && git -C ... diff > /tmp/split.patch && git apply ...`, `git add -A ... && git commit`, `cd ... && rm -rf kotlin/build/sp ...` (matches the `Bash(rm -rf*)` ask rule), `cd /tmp && mkdir ... && cd jarcheck && for ...` (x2), and one `Read /tmp/judge.out`. | Command shape: no `cd` prefix, absolute paths, one command per call; `rm -r <exact dir>` is still a prefix miss, so use `git clean`/`rmdir` on the named path or leave build output. `Read` with `limit`. No allow rule helps a compound. |

## SETUP: denials (31, seat retries)

| Class | Count | Cause | Command shape instead |
|---|---|---|---|
| SETUP | 8 | `sleep N; cat file` blocked | `run_in_background: true`, or Monitor with `until <check>; do sleep 2; done` |
| SETUP | 5 | "writes an executable script" (heredoc `cat > x.py`) | write the file with the Write tool inside the repo worktree, or run `python - <<EOF` without saving |
| SETUP | 4 | Write to the OS temp scratchpad the harness names | the harness text tells the seat to use it and the hook denies it; deliverables go in the worktree, throwaway through a Bash heredoc. The harness text and the hook disagree: that is the setup defect. |
| SETUP | 3 | `subprocess(..., text=True)` | `capture_output=True` then `.stdout.decode("utf-8")` |
| SETUP | 4 | git skill (`raw-stage-or-commit`, `raw-worktree`) 2; search skill (`plain-cat`, `plain-head-tail`) 2 | `git_tool.py stage <path>` / `commit -F`, `git_tool.py worktree add --owner <seat> --topic <slug>`; Read with `limit`/`offset` |
| SETUP | 2 | Bulk Read 88 KB; Agent isolation worktree refused (corrupt `.git`) | Read with `limit`; `git worktree prune` then recreate |
| SETUP | 5 | user-rejected 1, stream-closed 1, interrupted 3 (these are prompts Jim did not accept, counted above) | same fixes as the prompts |

## RULE: stops for a go

| Class | Count | Rule | Would a standing go remove it |
|---|---|---|---|
| RULE | about 22 turns, 9 episodes (10-17, 10-18, 10-21, 10-22 x3, 10-23 x2) | Claude Code's memory-pressure notice: "Do not start it again on your own ... start it again only when asked". It killed the seat's judge/mutant runs 28 times; the seat refuses a go relayed by another seat (correct: an agent message is not consent). The cause is memory on the gamebox (Steam, other seats' java), not the commands. | Yes. One typed in the seat's own session: "go: restart any judge or mutant run the memory notice stopped, one job at a time, when 4.2 GB is free, until I say stop". Removes the stop, not the kills. Cause side: `CLAUDE_CODE_DISABLE_BG_SHELL_PRESSURE_REAP=1` in the environment that starts Claude Code (the notice says a shell `export` has no effect) stops the reaping; the RAM stick is the real fix. |
| RULE | about 3 turns (10-20, 10-23) | gamebox queue/skills: engine-judge and full engine-mutants wait for Jim's own go typed in the session | Yes, same standing go, naming "judge and mutants through the gamebox queue". |

## SEAT: stops with nothing requiring them

| Class | Count | Quote |
|---|---|---|
| SEAT | 3 | 10-11: "should I start with the stale-position rule (item 6)? Say so and I'll write cases first." / "If you don't answer, I leave it and carry on" |
| SEAT | 1 | 10-13: "That's a schema change in both engines, and I'd start it on your go." |
| SEAT | 2 | 10-16/17: "Want me to write it?" / "Do I have your go to write that contract only?" |
| SEAT | 1 | 10-23: "Jim, which do you want? If you type 'go' without choosing, I'll run the mutants one at a time" (it had a default and named it) |
| SEAT | 1 | 10-09: "Do you want me to resume, and if so, is that first step the right place to start?" after Jim's pause |

The 10-09 asks about building `reports` and `views` after "fuck no ... type go in its session" follow Jim's own freeze order and are not counted as SEAT.

## Fixes to apply (proposed only; nothing changed)

1. Gamebox `settings.json`: `permissions.additionalDirectories = ["C:/Users/falcon-ridge-bmax/workspace"]`. Removes the live prompts (21 in one day).
2. Start Claude Code on the gamebox with `CLAUDE_CODE_DISABLE_BG_SHELL_PRESSURE_REAP=1`, or give the seat the standing go above. Removes the largest class of stops.
3. Reconcile the harness scratchpad text with the hook (the seat is told to write where the hook denies).
4. Seat habits: no `sleep N; cat`, no `cd X &&` prefix, absolute paths, Read with `limit`, `git_tool.py` for stage/commit/worktree.
5. Nothing to add to any allow list: the hook `ask` cannot be overridden by `allow`, and compound commands never match a prefix rule.

## Unreadable or not measured

The pre-2026-10-22 PreToolUse.js on the rasche_j workstation (Oct 9-16) was not available; its asks are attributed from the identical gamebox backup (`PreToolUse.js.bak-20261022-envnarrow`) and the recorded reason text. The 6 vps1 prompts have no hook reason, so their cause (classifier or the `rm -rf*` ask rule) is inferred from command shape. Stop counts are turns ending in a request for a go, read from assistant text by pattern; a few status lines that only restate a wait are excluded.
