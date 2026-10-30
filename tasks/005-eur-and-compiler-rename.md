---
id: 005
title: EUR as the base currency, and rename brain to compiler
lane: platform
status: ready
depends_on: ["001", "002", "003", "004"]
extra_review: []
branch: task/005-eur-and-compiler-rename
written: 2026-10-30
---

# 005: EUR as the base currency, and rename `brain` to `compiler`

## Why
We launch in Ireland, so prices, budgets and invoices are in euro (D-010). The service called `brain` only compiles rules. "Central Brain" now means the company's agent orchestrator, so keeping both names will confuse every new agent. Both changes touch many files across lanes, so this task runs alone, after tasks 001-004 are merged, while the other lanes pause.

## Context
- Decisions: D-008 (Ireland first), D-010 (EUR)
- About 50 hard-coded `GBP`/`£` references outside `docs/`: models and seed data in campaign-api, `ruleset.py`, the simulator, bidder tests, `apps/web/lib/utils.ts`, the analytics agent (`spend_gbp`)
- About 20 files reference `brain`: `infra/docker-compose.yml`, `BRAIN_URL` in campaign-api and agents config, `apps/web/lib/api.ts`, agents' state and qa, `README.md`

## Files you may touch
This is the one cross-lane task. Any file is allowed, except `contracts/`, `handbook/`, `docs/DECISIONS.md` and `tasks/`. List any of those that need changes in the Builder report, and the planner will update them.

## Scope
1. Rename `services/brain` to `services/compiler`: the folder, the compose service name, `BRAIN_URL` to `COMPILER_URL`, Dockerfile paths, imports, agent references and the README. Leave the historical docs in `docs/` unchanged.
2. Add a `currency` field (ISO code, default `EUR`) to advertisers and campaigns, and to the compiled snapshot (`packages/ruleset`). Existing demo rows keep `GBP`, and new ones default to `EUR`.
3. Bidder: the bid response `cur` is the campaign's currency. Only bid when that currency is in the request's `cur` list, or the list is empty.
4. Simulator: Irish screens send `cur: ["EUR"]`, UK screens `["GBP"]`.
5. UI and agents: format money with the currency code (`Intl.NumberFormat`). Rename `spend_gbp` to `spend` with a currency field.
6. Update the seed data so the demo advertiser and its Dublin campaigns are EUR.

## Out of scope
- Converting between currencies (not needed while each campaign has one currency)
- Changes to `docs/` history files

## Acceptance criteria
- [ ] `grep -rnE "GBP|£" --exclude-dir=docs --exclude-dir=.git .` finds matches only in tests, fixtures, UK simulator screens and legacy-row handling. List what remains in the Builder report
- [ ] `grep -rn "BRAIN_URL\|services/brain" --exclude-dir=docs --exclude-dir=.git .` finds nothing
- [ ] `docker compose -f infra/docker-compose.yml up -d --build` starts with a `compiler` service, and the console's health strip shows it
- [ ] An Irish campaign bids with `cur: EUR`. A campaign in EUR does not bid on a request whose `cur` is only GBP. Add a matcher test for each
- [ ] CI is green

## Tests
```
All CI jobs, plus a compose smoke run
```

## Open questions
_None yet._

---

## Builder report
_Filled in by Cursor._

## Review
_Filled in by Claude Code._
