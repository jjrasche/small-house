# Task board: the house's tasks posted for anyone to sign up

Design only, 2026-10-20. Nothing here is built, and nothing has been posted or sent to anyone.

Jim's ask: "you finding the person who wants to help is your job ... you are creating a 'marketplace' or
something for you to create tasks and people to see, create accounts and sign up for those tasks."
Pairing is up to the solver, not a rule.

Every house figure below is a value the engine returned on 2026-10-20 for world `95cb373`
(`we simulate` and `fields.py`, engine checkout `c3542b1`; `engine.pin` says `5af4c5f`). This document
computes none of them. A claim about law or about how a product behaves carries a source, or is marked
**unverified**.

---

## 1. Where it sits

```
world.json ──we simulate / we solve──▶ postings export ──▶ task board (public list)
                                                              │ sign in (IdP) + consent
                                                              ▼
                                                       board db: accounts, sign-ups
                                                              │ export, pseudonymous ids
                                                              ▼
                              people overlay ──▶ we simulate (crew matcher) ──▶ match shown to each person
```

- The board is an app layer and has its own repo. It is not part of the engine or of small-house, because
  van-world and any later world post tasks the same way.
- It **reads** only engine output: flows, hours, pieces, assignments and piece weights. It **writes** only
  `people` records, in the shape `Crew.kt` reads: `skills`, `certifications`, `hours_per_step`.
- Names, emails and phone numbers stay in the board's database. The engine sees a pseudonymous id. Nothing
  goes into git, and nothing goes into Genesis (Jim's rule: the engine never writes to Genesis's log).
- The engine stays general. What the board needs from it goes in as requests with a case (§10), never as
  edits to the engine.

## 2. What the engine already gives a posting

From `we solve` (`work-at-published-rates`) and `we simulate` on the current world:

| flow | needs (tasks manifest) | hours (solver) | sim minutes run | who the matcher put on it |
|---|---|---|---|---|
| dig-post-holes | none, max_team 1 | post_holes_hours=2.0 | 0–119 | jim |
| set-posts | none, max_team 2 | set_posts_hours=2.0 | 30–134 | jim, sip_lead |
| set-floor-panels | sip-setting 3, max_team 4 | floor_hours=0.9997 | 135–174 | jim (learner), sip_lead |
| set-wall-panels | sip-setting 3, max_team 4 | walls_hours=5.631 | 175–404 | jim (learner), sip_lead |
| set-roof-panels | sip-setting 3, max_team 3 | roof_hours=1.912 | 405–481 | jim (learner), sip_lead |
| cut-openings | none, max_team 2 | cut_openings_hours=6.0 | 482–661 | jim, sip_lead |
| set-windows-and-door | none, max_team 2 | windows_and_door_hours=14.0 | 662–1081 | jim, sip_lead |
| frame-loft | none, max_team 2 | frame_loft_hours=7.200 | 1082–1298 | jim, sip_lead |
| lay-subfloor | none, max_team 2 | lay_subfloor_hours=3.0 | 1299–1388 | jim, sip_lead |
| install-boiler | none, max_team 2 | install_boiler_hours=16.0 | 1389–1868 | jim, sip_lead |

Also returned: `objective_total labour_hours=61.799397`; `final_stocks budget_usd=5512.59`, which is
materials only; `skills_final jim sip-setting=1.578333`; and the gravity load path's `weight_n` for each
piece (for example `roof@0,0,3658 weight_n=3546.57`, `glazing@610,2495,1219 weight_n=924.93`,
`door@610,4819 weight_n=533.79`).

Facts from `Crew.kt` that a posting has to show:
- `bestTeam` tries every team size from 1 to `max_team` and keeps the highest score, so pairing is the
  solver's choice. `teamOf` rejects a team made only of learners. A novice can join a panel task only once
  someone at sip-setting 3 has signed up.
- `whyNoTeam` gives the reason a task waits: `no-free-person`, `no-free-person-holds:<cert>` or
  `no-qualified-person`. The board shows it as written.
- Each assignment row already says who on the team is a mentor and who is a learner.

## 3. Accounts and identity

What exists on vps1 today (read from the box on 2026-10-20):
- **:8102 "Genesis login" is not a user identity system.** Its systemd unit describes it as "the page that
  logs the outside brain in from Jim's phone". It mints a token into deploy's own `claude`, listens on the
  WireGuard address `10.0.0.5:8102`, and the unit currently reports `failed` (the Genesis services were
  stopped on Jim's word). The public cannot reach it, and it holds no accounts. **Rejected.**
- **Zitadel is live at `https://id.jimr.fyi`**, image `zitadel:v4.16.2`. Its OIDC discovery lists the
  scopes `openid profile email` and the grant `authorization_code`. This is the real identity provider that
  was stood up after the 2026-08-07 ruling against Cloudflare-managed logins.
- **Pomerium holds ports 80 and 443** in front of the app containers (common-ground, practice-exchange,
  house-ops and others). I could not read its config (permission denied), so which identity provider it
  uses is **unverified**.
- **Self-hosted Supabase (GoTrue) runs too**: email is on, SMTP goes through `smtp.resend.com`,
  `GOTRUE_DISABLE_SIGNUP=true`, and Google is off. Its allow-list serves Jim's other apps.

| option | how it works | for | against |
|---|---|---|---|
| Google OAuth, direct | the app is a Google OIDC client | most people already have an account | brand verification applies to every app that uses Google APIs ([Google][g-ver]); without verification it is capped at 100 users and shows a warning screen ([Google][g-exempt]); people without Google are shut out |
| Magic link | an emailed one-time link | works for anyone with email; Resend SMTP already exists on the box | deliverability is now our job; mail scanners that open links can use up single-use links (**unverified**) |
| Genesis login (:8102) | — | — | not an identity system (above) |
| **Zitadel (id.jimr.fyi), with Google federated into it and email sign-in** | the board is one OIDC client; Zitadel holds the accounts | one identity provider for every app; Google can create accounts on first login ("Automatic creation", "Account creation allowed", [Zitadel][z-google]); the board never touches a password | self-registration settings have to be set correctly. CVE-2026-29193 let users register even when registration was disabled, in versions 4.0.0 to 4.12.0, fixed in 4.12.1 (**secondary source**); the box runs 4.16.2 |

**Recommendation: Zitadel.** Pomerium authenticates the request and passes identity to the board in
`X-Pomerium-Jwt-Assertion`. The board checks the signature against
`/.well-known/pomerium/jwks.json` and checks `aud`, `iss` and `exp` ([Pomerium][pom-jwt]). The list of
tasks is public. Signing up requires a login.

Later, a person's own agent is a second OIDC client that acts for them with a token scoped to that person.
The board's API is the same one its own page uses, so the agent gets nothing special.

## 4. What a posted task shows

| field | where it comes from today | gap |
|---|---|---|
| What | flow id, plus the pieces it places from `placed_at` (for example 4 posts) | flows have no human label; this is a request to the tasks domain for a label and a description |
| Where | "West Michigan, near Grand Rapids". The address goes only to people with a confirmed sign-up | the site is not in world.json |
| When | the minute range from `we simulate`, relative to the start | there is no start date and no calendar. This is a request (R3) |
| Hours | the `*_hours` figure from `we solve` | the solver returns a point figure, not a range. A range is a request to the tasks domain for low and high rates |
| Skill | the flow's `needs.skills`, plus the note "learners welcome once a lead has signed up" when `teamOf` allows learners | the board should read needs from engine output, not from the domain jar (R4) |
| Team size | `max_team` | — |
| Pay | not modelled | Jim's call (§11). If paid, the cost has to move through `budget_usd` (R5) |
| Physical load | the heaviest piece's `weight_n` from the gravity load path, joined to the task's items | the join is a request (R6). Muscle groups are not banked anywhere |
| What you learn | the skill gains from the crew matcher (`skills_final`; gains per team) | the assignment row does not carry the gains. This is a request (R7) |
| Provenance | the world commit and engine pin the figures came from | — |

## 5. Signing up and consent

- **Signing up is consent to one task**, not to "the build". The record holds: account, flow, the posting
  version (world commit), the skill level the person reports (marked self-reported), any certifications
  (each needs evidence before it counts, because the matcher trusts `certifications` without checking),
  when they are available, the waiver version they accepted, and the time.
- A person can withdraw at any time. Withdrawing deletes the record from the next people export.
- The matcher may assign a person **only to flows they signed up for**. Today `Crew.kt` has no such
  restriction: it puts any free person on any flow they qualify for. This blocks matching and is request
  R2. Until it lands, the board shows sign-ups and does not show matches.
- 18 and over only. The address and the start date are released only to people with a confirmed sign-up.

## 6. How matching runs and is shown

1. The board exports a people overlay: pseudonymous id, self-reported skills, verified certifications,
   `hours_per_step` from availability, and the flows consented to.
2. `we simulate` runs on world.json with that overlay. Until R1 exists, this is a composed copy, the same
   way a what-if is run today.
3. Each person sees their own assignment rows as the simulation returned them: the flow, the minutes, who
   they are paired with and in which role (mentor or learner, both engine fields), and the gain. If they
   were not placed, they see the `whyNoTeam` reason.
4. Jim confirms a match. The board then sends the date and address. A run never commits anyone. The
   simulation proposes, and Jim and the helper agree.

## 7. Safety and liability for helpers in Michigan

This is not legal advice. Before money or strangers are involved, a Michigan attorney and Jim's insurer
need to answer the open items. Which law applies turns on whether helpers are unpaid volunteers or paid,
and on how much control Jim has over the work.

- **The gate: the homeowner permit.** MCL 339.2403(b) exempts "an owner of property, with reference to a
  structure on the property for the owner's own use and occupancy" from the residential builder licence
  ([MCL 339.2403][mcl2403]; text seen only in search results, because the legislature host refused the
  connection on 2026-10-20). Some Michigan homeowner-permit affidavits limit the work to the owner
  personally or to licensed contractors (Madison Heights, Highland Park), and Montcalm County says the
  permit holder carries "liability for any injury which occurs on the job" ([Madison Heights][mh],
  [Montcalm][montcalm]). **Whether Jim's township lets unlicensed helpers work at all is the first legal
  question.** The site, and so the township, is not yet known.
- **Volunteers.** The DOL FLSA Advisor says employees "may not volunteer services to for-profit private
  sector employers" ([DOL elaws][dol-vol]). Jim building his own home is not a for-profit business, and how
  the FLSA treats a homeowner's unpaid helpers is **unverified**. The federal Volunteer Protection Act
  shields only a "volunteer of a nonprofit organization or governmental entity"
  ([42 USC 14503(a)][vpa]). It does not cover Jim's helpers, and it never protected the host.
- **Paid helpers: employee or self-employed.** IRS Pub 926: "The worker is your employee if you can
  control not only what work is done, but how it is done." A self-employed worker "usually provide[s]
  their own tools and offer[s] services to the general public in an independent business." Social Security
  and Medicare apply at "cash wages of $3,000 or more in 2026 to any one household employee"
  ([IRS Pub 926][p926]). Whether building your own house counts as "household work" is **unverified**:
  Pub 926's examples stop at yard workers. A mentored learner on Jim's site, told how to set the panels,
  looks like control of how the work is done.
- **Michigan workers' comp.** The test in MCL 418.161(1)(n): a worker is an employee unless they keep a
  separate business, hold themselves out to the public, and are themselves an employer under the act. This
  comes from search snippets and Court of Appeals opinions applying it ([COA 2015][coa]); the statute text
  was not fetched. Coverage applies to a private employer with 3 or more employees at one time, or 1
  employee for 35+ hours a week for 13 weeks within 52, per michigan.gov FAQ text seen in search results
  (the page returned 403 to fetch) ([LEO FAQ][leo]). **Unverified for households.**
- **1099s.** Secondary sources say the 1099-NEC threshold rose from $600 to $2,000 for payments after
  2025 (OBBBA §70433) ([Sovos][sovos]). That was not confirmed on irs.gov. Whether a personal, non-business
  payer has to file at all is **unverified**.
- **Digging.** The first slice's task digs post holes 4 ft deep. MISS DIG 811 has to be notified at least
  3 business days and no more than 14 calendar days before excavation, under PA 174 of 2013, and the FAQ
  says this applies "no matter how big or small the project" ([MISS DIG FAQ][missdig], [MPSC][mpsc]).
  This is Jim's step before any helper digs.
- **Basics the board enforces whatever the law says:** 18 and over; a written waiver (whether it holds up
  in Michigan is **unverified**); Jim's homeowner's insurer told before anyone works; the heaviest piece's
  weight shown on every posting, and a lift by two or more people for any piece the board flags; required
  PPE listed for each task; nobody runs a power tool without a mentor present; a first-aid kit and an
  address card on site.

## 8. Payments, later

Not in the first slice. Paying people raises the Pub 926 and workers' comp questions above. So the order
is: legal answer, then a pay rate setting in the world (R5) so `we simulate` says whether paid help fits
the $20,000, then a payment processor. No processor has been researched. Any claim about one waits until
it is cited.

## 9. How people find it

**Every outward post needs Jim's first OK.** None has been made.

| channel | what is known |
|---|---|
| Craigslist (grand rapids) | gigs cost "$3-10" in the US. Community posts are not on the fee list, so they are free ([Craigslist][cl]) |
| GR Makers, 401 Hall St SW | an open community lab with a weekly open night (older secondary sources; current hours **unverified**) ([LocalWiki][grm]) |
| Habitat for Humanity of Kent County | a place where people with build skills already volunteer. Whether they allow recruiting for a private build is **unverified**, and likely not |
| Nextdoor | business posts need a claimed business page (secondary source); rules for a neighbour's own request are **unverified** |
| Facebook groups (West Michigan builders, tiny house, SIP) | each group sets its own rules (**unverified**) |

A link to the public list carries a source tag, so the board can count which channel brings people.

## 10. Requests the board will need from the engine and domains (not sent)

- **R1** People from a separate file (`we simulate world.json --people p.json` or an include), so sign-ups
  never land in world.json or git.
- **R2** `people.<id>.flows`: the flows a person consented to. The matcher assigns only within them.
  **This blocks matching.**
- **R3** A start date on the clock, and availability windows for each person.
- **R4** Each flow's needs (skills, certs, `max_team`, effort) in simulate output.
- **R5** (tasks) a pay rate for each person or task that moves `cost_usd` and `budget_usd`.
- **R6** (tasks × structural) the heaviest piece for each task, from the gravity load path's `weight_n`.
- **R7** The skill gains for each person in each assignment row.

## 11. Hosting: three options

| | A. vps1 behind the existing Pomerium, Zitadel and Postgres | B. claude.ai Artifact (db + viewer identity) | C. Managed backend (Supabase Cloud) + static host |
|---|---|---|---|
| Who can sign up | anyone | only signed-in claude.ai users in Jim's org or invited guests (from the Artifact tool's terms in this session) | anyone |
| Added cost | about $0. The box, the domains (`jimr.fyi`), Pomerium, Zitadel and SMTP already exist | $0 beyond Jim's plan | free tier, or the paid tier at the price on [supabase.com/pricing][sb-price] (**not checked**) |
| Runs the engine | yes, the JVM `we` is on the box | no. Postings would be pasted in by hand | no. The exporter still runs on vps1, so there are two places |
| Ways it fails | one box shared with Jim's other apps and Genesis; a bad route exposes them; Postgres backups on this box are **unverified**; several containers run `:latest` images (against the pin rule) | no public reach, which fails the ask | free projects pause after 7 days of low activity ([Supabase][sb-pause]); a second vendor holds helpers' personal data |

## 12. Recommendation and first slice

**Recommendation: A.** One container on vps1. Pomerium routes `tasks.jimr.fyi`: the list is public, and
`/signup` requires a Zitadel login (Google federated, plus email). Postgres holds the board's schema.
B is useful only as Jim's private preview. C splits the system across two places and adds nothing A
lacks.

**First slice: a stranger makes an account and signs up for `dig-post-holes`.** It shows all ten flows,
and sign-up works on any of them. It does not show matches until R2 lands.

Smallest build plan, inside the architecture:
1. `postings export`: run `we solve` and `we simulate` on a named world commit, and write
   `postings.json` (flow, needs, hours figure, minute range, world commit, engine pin). It copies values
   and computes none.
2. The board app: `GET /` and `GET /task/<flow>` render `postings.json`. `POST /signup` verifies the
   Pomerium JWT, upserts the account by the `sub` claim, and stores the sign-up with its consent version.
   `DELETE /signup/<flow>` withdraws.
3. Pomerium route and Zitadel OIDC client, with Google as an external provider and account creation
   allowed. Pin the board image by digest.
4. `people export`: sign-ups become a pseudonymous `people` overlay. Run `we simulate` on a composed
   copy only to prove the overlay is valid. No matches are shown yet.

Acceptance checks:
- `curl -s https://tasks.jimr.fyi/postings.json | jq '.[]|select(.flow=="dig-post-holes").hours'` prints
  `2.0`, the same as `fields.py`'s `post_holes_hours` for the world commit the posting names. Differential:
  on a copy with 6 posts, the export changes and the check fails. A check that read the export back
  against itself could not fail that way.
- `curl -s -o /dev/null -w '%{http_code}' -X POST https://tasks.jimr.fyi/signup` without a session prints
  `302`, with `Location` on `id.jimr.fyi`. With a forged `X-Pomerium-Jwt-Assertion` sent straight to the
  container, it prints `401`.
- A Playwright run creates a fresh Zitadel account, signs up for dig-post-holes, and then
  `select flow from board.signups where account_sub='<sub>'` returns exactly `dig-post-holes`. After
  withdrawing, it returns 0 rows.
- `we simulate` on the composed copy with the exported overlay does not refuse (no `person-invalid` and no
  `people-skill-unknown`), and the test person's id appears in `skills_final`.
- `docker inspect` shows the board image by digest, and Pomerium's other routes return the same status
  codes as before the change.

## 13. Decisions only Jim can make

1. **Money and people: unpaid or paid, and the rate.** $50/hr changes the legal picture (§7), and today
   the engine does not price labour at all.
2. **Before any helper or any outward post:** the site's township (which decides whether unlicensed
   helpers may work under a homeowner permit), his insurer's answer, and his OK on which channel goes
   first.

[g-ver]: https://support.google.com/cloud/answer/13464321
[g-exempt]: https://support.google.com/cloud/answer/13464323
[z-google]: https://zitadel.com/docs/guides/integrate/identity-providers/google
[pom-jwt]: https://www.pomerium.com/docs/capabilities/getting-users-identity
[mcl2403]: https://capitol.legislature.mi.gov/documents/mcl/pdf/MCL-339-2403.pdf
[mh]: https://www.madison-heights.org/DocumentCenter/View/169/Homeowners-Affidavit-to-Obtain-Permit-PDF
[montcalm]: https://www.montcalm.us/DocumentCenter/View/5601
[dol-vol]: https://webapps.dol.gov/elaws/whd/flsa/scope/er16.asp
[vpa]: https://www.law.cornell.edu/uscode/text/42/14503
[p926]: https://www.irs.gov/publications/p926
[coa]: https://www.courts.michigan.gov/siteassets/case-documents/uploads/opinions/final/coa/20150922_c321974_47_321974.opn.pdf
[leo]: https://www.michigan.gov/leo/bureaus-agencies/wdca/frequently-asked-questions/employers/all-employer-faqs
[sovos]: https://sovos.com/regulatory-updates/trr/one-big-beautiful-bill-raises-1099-reporting-thresholds/
[missdig]: https://www.missdig811.org/get-started/i-want-to-dig/faq.html
[mpsc]: https://www.michigan.gov/mpsc/regulatory/damage-prevention
[cl]: https://www.craigslist.org/about/help/posting_fees
[grm]: https://localwiki.org/gr/GRMakers
[sb-price]: https://supabase.com/pricing
[sb-pause]: https://supabase.com/docs/guides/platform/free-project-pausing
