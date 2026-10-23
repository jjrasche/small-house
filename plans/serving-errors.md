# Serving errors: book.jimr.fyi and plum.jimr.fyi

Observed 2026-10-23 16:20 to 17:00 UTC on vps1. Journal window: 2026-10-22 00:00 UTC onward (244 lines across book-app, page-worlds, we-serve).
Pages were loaded headless (Chromium debugging port, one at a time) straight at the units, `http://172.17.0.1:8091` and `http://172.17.0.1:8090`, not through Pomerium: the Pomerium hop and its login were not exercised.

## Errors a visitor hits, ranked

| unit | error | count | first / last | cause | owner | smallest fix |
|---|---|---|---|---|---|---|
| page-worlds | `GET /spec.json` returns 502 "the engine at http://127.0.0.1:8197 did not answer: request timed out" after exactly 60.0 s; the page stays on "Loading the page" with no canvas | 2 of 2 browser loads and 2 of 5 curls (the first three returned 200 at 60.6, 60.6 and 62.3 s) | 16:40 to 16:55 UTC today, reproducible | the world spec is built on every request (no cache on the worlds path) from engine calls, and the build takes about 60 s, the Java client timeout `RUNTIME_TIMEOUT_SECONDS = 60` | world-engine for the slow answer; factored-ui for the missing cache and the timeout | factored-ui `Runtime.kt:8` and `ServedEngine.kt:38`: the timeout applies to every engine call; `WorldsServer.kt:serveWorldSpec` (about line 60) has no memory or disk cache like `PageServer.kt:serveFromMemoryOrDiskOrBuild` (about line 178); give it one keyed on the world's stamp so only the first visit pays |
| we-serve | `GET /worlds` on 127.0.0.1:8197 gives no answer in 10, 15, 20 s and 140 s while page requests are in flight, so every page request that begins with `engine.worlds()` (`WorldsServer.kt` `pageOf`) waits behind it | 4 of 4 tries during the probe | 16:50 to 17:00 UTC | not found. Seen: the JVM is at 1.196 GB resident against `-Xmx1g` and MemoryMax 1.4 GB, and averaged 50 to 58 percent of a core for 70 minutes, and a request that times out client-side keeps running in the engine (the Java client gives up, the server does not cancel). Two other `java` commands from other seats ran at 150 to 205 percent of a core during the probes. A thread dump (`jcmd 262966 Thread.print`) would say whether `/worlds` waits on `listWorlds(roots)` (`CliServe.kt:78`, walks both roots) or on the heap; I did not take one | world-engine | unverified: cache `listWorlds` or exclude `.git-worktrees` from the roots; first take the thread dump |
| browser | `GET /favicon.ico` 404 on both sites, a red console error on every load | every load, both sites, both viewports | always | no favicon route | book-app `web.py:75` (`do_GET`, falls to `send_bundle_file`); factored-ui `PageServer.kt` routes | answer `/favicon.ico` with 204 |
| book-app | `ConnectionResetError: [Errno 104] Connection reset by peer`, a 20-line traceback in the journal, raised in `wfile.write` | 4 (19:05:22, 19:06:33, 19:06:49 on 10-22, 16:07:32 on 10-23) | 2026-10-22 19:05:22 / 2026-10-23 16:07:32 | the client (Pomerium at 172.18.0.12, or a phone dropping the connection) closed a media, timing-asset or bundle download mid-write; `ThreadingHTTPServer` prints the traceback. No visitor effect beyond the aborted download | book-app | `web.py:46`: subclass `ThreadingHTTPServer`, override `handle_error` to ignore `ConnectionResetError` and `BrokenPipeError`; the write sites are `web.py:181`, `209`, `233` |
| page-worlds | `WARNING: sendResponseHeaders: being invoked with a content length for a HEAD request` | 1 (16:36:36, caused by my `curl -I`) | same | `respond` sets a body length on a HEAD request; any HEAD (monitor, link preview) logs it and gets no failure | factored-ui | `PageServer.kt:35`: for HEAD pass -1 (or `-1` when `exchange.requestMethod == "HEAD"`) |
| browser | `Clipboard API is not available in insecure contexts` | each load | always | I loaded over plain http on the bridge address; over https at jimr.fyi it does not occur. Not verified there | none | none |
| browser | `GPU stall due to ReadPixels`, `WEBGL_debug_renderer_info not enabled` | each load of the book page | always | headless Chromium software GL; not a server error | none | none |

No other error appeared: no 5xx from book-app, no failed request apart from the favicon, no console exception.

## Per page

| page | viewport | HTML | wasm | spec | result |
|---|---|---|---|---|---|
| book (:8091) | 390x844 | 0.04 s | 0.19 s and 0.25 s | 0.01 s, 359,703 bytes | loads; the accessibility tree shows the chapter, the audio controls and the text |
| book (:8091) | 1280x800 | 0.03 s | 0.36 s and 0.29 s | 0.01 s | loads, same |
| plum (:8090) | 390x844 | 0.01 s | 0.08 s, 0.23 s | 502 at 60 s (aborted at 100 s watch) | never draws |
| plum (:8090) | 1280x800 | 0.01 s | 0.14 s, 0.21 s | 502 at 60.01 s | never draws |

Book Play: on the default chapter (Weber chapter 1, 18:22) the Play button was clicked at both viewports; ten seconds later the clock read 0:09 of 18:22 each time, and the only errors in that window were the favicon 404 (twice, one before and one after the click). The media route answers 206 on ranged reads for the Weber chapter and the Bible chapters GEN-001 and JHN-003 (about 2 ms). Choosing a different chapter in the picker was not driven in the page (the picker's button names were not read); only the default chapter was played.

## Memory (systemd, read 16:2x to 17:00 UTC)

| unit | MemoryCurrent | MemoryPeak | MemoryMax | swap | note |
|---|---|---|---|---|---|
| book-app | 52.9 MB | 137.8 MB | 300 MB | 0 | the previous run (stopped 15:14:00) peaked at exactly 300.0 MB with 143.3 MB of swap: it reached its cap, no OOM line |
| page-worlds | 136.0 MB | 152.9 MB | 900 MB | 0 | earlier runs peaked at 549 to 597 MB on `-Xmx512m`; no kill |
| we-serve | 1,196 MB | 1,200 MB | 1,400 MB | 0 | 85 percent of its cap with `-Xmx1g`; the 10-23 02:16 run swapped 482 MB |

Host: 7.7 GB, 1.5 GB of 4 GB swap in use, memory pressure (PSI) 0.00. No OOM or kill line in the user journal for the three units and the kernel journal query returned nothing for oom since 10-22 (whether this user can read the kernel journal was not checked). Every `Failed with result 'exit-code'` (status=143) in the journal is a deliberate stop (a `Stopping ...` line precedes each): redeploys, none from crashes.

## Could not read

- Through Pomerium: not tested, so the login hop and the TLS context (the clipboard warning) are unverified.
- A thread dump of we-serve: not taken (no extra JVM on vps1).
- Which engine call inside the page build is the slow one: the page's `Server-Timing` header never arrived because the build failed first.
