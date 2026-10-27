# Friction classifier, 2026-10-27

Stage: back-of-envelope. Judge: GROQ_API_KEY is not set in this environment, so no non-Claude judge is reachable; the judge is
`claude -p --model haiku` and every judged result below is SAME-FAMILY (Claude judging Claude's conversations).

## Pre-registration (written before `analyse` ran; counts of Jim messages per seat and day had been looked at, no friction judgment had)

Claim: Jim-directed friction per Jim message rose in the seats on 10-25 to 10-27 against 10-19 to 10-24. It is killed by no seat
(or only small-house) reaching the CHANGED rule below.

Instrument: `python3 plans/tools/jim_friction.py analyse`. Binary questions Q1 wrong/not-asked, Q2 repeats an instruction,
Q3 does not understand, Q4 swearing/exclamation aimed at the assistant or its work, Q5 praise. friction = Q1 or Q2 or Q4;
confusion = Q3. The model outputs booleans only. Judge acceptance: at least 14 of 16 knowns right (6 angry, 7 happy, 3 of Jim's own cases).

Per seat, before = 10-19..10-24, after = 10-25..10-27 (UTC). Cap 400 Jim messages per seat per period, seeded sample (seed 1).
A seat is CHANGED if after/before >= 1.5 and the permutation test (10000 shuffles of period labels over messages, seed 1) gives p < 0.05.

- VERDICT GLOBAL if >= 4 of 6 seats CHANGED
- VERDICT ONE-SESSION if only small-house CHANGED
- VERDICT NONE if no seat CHANGED
- otherwise VERDICT MIXED naming the seats

Added before running, because the data forced it (deviation, logged): Jim's typed text exists almost only in the small-house transcripts
(766 messages in the window; domains 2, world-engine 16, factored-ui 18, research 7, business 0 — the other seats are fed by relay messages
and task notifications). A seat with fewer than 30 Jim messages in either period is THIN: it prints with its numbers, counts as not CHANGED,
and is marked thin. Under this rule GLOBAL cannot be reached from friction alone, so the verdict line is read together with the secondary
measures, which need no Jim message: tool-result error rate per seat (same CHANGED rule: ratio >= 1.5 and permutation p < 0.05,
tool-result level), interrupts per 100 Jim messages, median words of the assistant's final reply to Jim, assistant messages per Jim message,
and the model mix by day.

## Result

Judge validation: 4 wording rounds; final 15 of 16 knowns right (6 of 6 angry found, 6 of 7 happy left alone, 3 of 3 of Jim's own cases).
The miss is the happy line 38716 (a voice-dictated ramble that opens "Yes that's what the f****** anthropic and open AI..."), judged as complaint.
The 14-of-16 acceptance in the rules is met; the acceptance line `knowns agree >=16` is not (15). Wording changed, knowns never changed.
Judge was Claude haiku, so these are SAME-FAMILY; a Groq re-run needs GROQ_API_KEY in the environment (no key file was read).

SEAT small-house before=0.253 after=0.234 ratio=0.93 p=1.0 changed=no
SEAT domains before=0.000 after=0.000 ratio=1.00 p=1.0 changed=no THIN n=1/1
SEAT world-engine before=n/a after=n/a ratio=n/a p=n/a changed=no THIN n=3/0
SEAT factored-ui before=n/a after=n/a ratio=n/a p=n/a changed=no THIN n=2/0
SEAT research before=n/a after=n/a ratio=n/a p=n/a changed=no THIN n=0/0
SEAT business before=n/a after=n/a ratio=n/a p=n/a changed=no THIN n=0/0

VERDICT NONE

Reading it:
- small-house (766 Jim messages in the window, all judged, 383 before and 273 after): friction per message did not rise; it ran 20 to 33 percent
  a day with no step at 10-25 (10-19 .327, 10-20 .292, 10-21 .216, 10-22 .196, 10-23 .203, 10-24 .286, 10-25 .202, 10-26 .240, 10-27 .375 on 24 messages).
  Confusion (Q3) 0.164 before, 0.168 after. The keyword rate (5, 9, 15, 11 percent) measured something else; this measure is flat.
- The other five seats cannot answer the global question from Jim's words: Jim typed 2, 16, 18, 7 and 0 messages there in the window. GLOBAL was
  unreachable by the pre-registered rule, so NONE here means "no seat showed a rise where there is data", not "all seats are fine".
- One session confounds seat and decay: small-house is one session file (ca0bc5ee, 150 MB), so calendar day and session age cannot be separated.
- Secondary, no judge. small-house: interrupts per 100 Jim messages 0.8 before, 0.0 after; tool-result error rate 0.013 before, 0.009 after;
  median words of the assistant's reply to Jim 81 before, 41.5 after (shorter); assistant messages per Jim message 12.7 before, 10.3 after.
  Tool-error rate across seats: domains 0.018 to 0.017, research n/a to 0.006, business 0.033 to 0.018, world-engine and factored-ui have no
  transcript after 10-24 in this directory set; none CHANGED.
- Model mix: small-house ran claude-opus-5-5 on every day from 10-19, not the Sonnet 5.5 default; Sonnet shows only as 14 to 577 messages a day
  (44 percent on 10-25, the largest share). The other seats ran claude-sonnet-5-5 throughout; research shows 12 claude-fable-5 messages on 10-17,
  before the window under test. No model change lines up with 10-25 except the Sonnet share rising in small-house that day.

Thin spots: sample is a single judge family; Q4 is the weakest question (the one wrong known is a Q1 false alarm on a long voice ramble, so the
friction rate may be a little high for dictated messages in every period alike); Jim's image-only messages ("[Image: ...") are excluded as untyped text.
Tool: plans/tools/jim_friction.py (selftest, extract, analyse). Judge cache: /tmp/jim_friction_cache.jsonl (714 rows). Groq spend: none (not used).
