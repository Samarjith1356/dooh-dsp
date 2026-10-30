# Decisions

Claude records design and product calls here. Cursor builds against them, and the reviewer checks against them. If code makes a call that isn't listed here, the reviewer flags it for Sam.

D-001 to D-004 were written down from the code as it stood on 29 Oct 2026. They describe what is built, so Sam should confirm or overturn them.

## Decided

**D-001 · Bid path stays pure** (from code)
The request goes HTTP parse → in-memory match → bid/no-bid → async log. No LLM, Postgres, ClickHouse, S3 or Brain compile on that path.
Why: decision time has to stay under 1ms, and it averages about 41µs today.

**D-002 · Money is integer micros, GBP** (from code)
Caps and spend are stored as integer micros. Billable impressions include `qty.multiplier`.
Why: no float rounding on money. The currency question for Ireland is still open, see O-1.

**D-003 · SSPs plug in behind an adapter** (from code)
`SSP_ADAPTER=simulator` is the default. The VIOOH adapter is a stub, and the matcher doesn't change per SSP.
Why: a live exchange can be swapped in without touching matching.

**D-004 · Control-plane agents run on Grok, off the bid path** (from code)
The runtime agents in `agents/` call the xAI API (`XAI_API_KEY`). They audit and plan, and they never bid.

**D-005 · Build workflow** (29 Oct 2026, Sam)
Claude chat plans and writes task briefs. Cursor builds one task per branch. Claude Code reviews with the `reviewer` subagent before Sam merges. Grok is not in the build loop. The handoff is task files in `tasks/`, and the rules are in `AGENTS.md`.
Why: one owner per decision, so three AI tools don't drift apart.

**D-006 · Dashboard KPIs cover the campaign's full life, with no silent row caps** (29 Oct 2026, Claude)
Totals and the GB/IE split come from the same full-window aggregate. The API returns the first and last event times so the UI can say what period it covers. Query `rtb.events` with GROUP BY for the country split for now, and don't change the materialized view schema in the same task.
Why: the GB/IE figures were computed from the last 500 raw events while the totals came from the hourly view, so the two didn't describe the same thing. At current volumes a GROUP BY on `rtb.events` is cheap. Adding country to the MV is a migration and gets its own task if volume needs it.

**D-007 · This repo is the company's main build** (30 Oct 2026, Sam)
`dooh-dsp` is the main plan. The earlier `Adstreet` repo and its Cloudflare plan are retired.
Why: this is the codebase that runs end to end today.

**D-008 · Ireland first** (30 Oct 2026, Sam)
Launch in Dublin, then the rest of Ireland, Northern Ireland, then the UK. Irish rules (Alcohol Act, ASAI) come first in the compliance engine.

**D-009 · Own DSP, bootstrapped, go-live in about four months** (30 Oct 2026, Sam)
We connect to SSPs directly, with no reseller DSP in between. Build a near-complete prototype in 2–3 months, then simulation and UAT, then go live around four months out. Bootstrapped: no outside funding for now.
Why: the platform is the product, and control over bidding is the moat.

The full company and build plan is in Claude Docs ("DOOH DSP: Company and Build Plan", 30 Oct 2026).

**D-010 · EUR is the base currency** (30 Oct 2026, Claude, following D-008)
Each advertiser and campaign carries a currency, defaulting to EUR. GBP stays possible for NI and UK screens later. Built in task 005.
Why: Irish customers pay in euro, and a per-campaign currency avoids a rewrite when we expand.

**D-011 · Build team: three parallel lanes, one planner, one reviewer** (30 Oct 2026, Claude, at Sam's request)
The builders are Cursor agents in the Trading, Platform and Experience lanes (Agents from Sprint 3). Each owns its own folders and works in its own git worktree from task files. Claude plans and writes contracts, and Claude Code reviews every branch (adding security and QA review when a task asks). Details are in `handbook/06-build-team.md`.
Why: one agent is too slow for the scope, and more than three or four at once collide on shared files and overload review. Contracts between lanes are what make parallel work safe.

**D-012 · Prototype launch scope** (30 Oct 2026, Claude, from the company plan; Sam can overturn)
Businesses and creators first, individuals after media-owner approval. No alcohol, gambling or political ads in the prototype.
Why: these are the highest legal and reputational risks, and the prototype doesn't need them to prove the model.

**D-013 · Priority order follows the go-live critical path** (30 Oct 2026, Claude, at Sam's request to build what is most core and urgent first)
Every backlog item gets a priority:
- **P0**: blocks one of the ten go-live items (`handbook/05-roadmap.md`), or the correctness of money or legal compliance.
- **P1**: needed for the 5 Feb prototype gate, but nothing else waits on it.
- **P2**: can wait until after go-live.

Within P0, work with outside lead time goes first, because the supply side sets the launch date. That means anything an SSP will check when certifying us: spend on billing notices, creative approval per partner, signed notices and latency. Next come accounts and the wallet, which everything customer-facing depends on, then the Irish compliance gate. The rename of `services/brain` to `services/compiler` is P2 and moves out of task 005. It touches every lane, pauses all builders and changes nothing a customer or an SSP sees. Task 005 keeps only the EUR work.
Why: three builders can produce more than one reviewer can check, so the order of work matters more than its speed. Building P0 first means that if time runs short, what's missing is polish, not something go-live needs.

**D-014 · Sam signs off business logic before it is built; only backlog work gets built** (30 Oct 2026, Sam)
Business logic means any rule about money, pricing, fees, refunds, budgets, what an advertiser may do, what is approved or blocked, compliance policy, or what a customer sees as a promise. A task that contains business logic lists those rules in plain words under "Business rules" and carries `sam_signoff: needed`. It only becomes `ready` once Sam has approved the rules (`sam_signoff: approved`, with the date). Builders stop if they find a business rule the task doesn't state. Agents build only tasks from `tasks/BACKLOG.md`. Nothing off-list, no extras, no gold-plating.
Why: Sam is accountable for how the company treats customers and money. AI agents should build fast, but they must not invent policy.

## Open (Sam to answer)

**O-4 · Repo visibility.** This repo is public, including the bidding logic and the compliance rulebook. Proposed: make it private and move it to a company GitHub Organization, with the co-founder added as a collaborator. Until then, commercial details stay out of the repo.

**O-6 · Staging cloud.** Proposed: one EU virtual machine running the Docker stack for staging, at roughly EUR 15-30 a month, with production on a larger provider near the SSP later. Needs Sam to choose a provider and create the account by Sprint 1.
