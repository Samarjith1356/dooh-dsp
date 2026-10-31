---
id: 006
title: Brain memory seeding works without a database, so CI is green
lane: trading
status: ready
depends_on: ["002"]
extra_review: []
sam_signoff: not-needed
branch: task/006-brain-seed-offline
written: 2026-10-31
---

# 006: Brain memory seeding works without a database, so CI is green

## Why
CI (task 002) runs every suite on every pull request, but the `brain` job is red. `seed_architecture()` in `services/brain/memory/store.py` takes the Postgres path whenever `create_engine` succeeds, and `create_engine` succeeds even when no database is reachable because it connects lazily. The count query then fails, the error is swallowed, and every call adds the four architecture rows again (4, then 8). Until this is fixed, nobody can tell a new failure from the old one, and Sam can't turn on "CI must pass before merge".

## Business rules
None.

## Context
- Decisions: D-001 (bid path stays pure; brain is off the bid path), D-013 (this is P0: it blocks green CI)
- Code: `services/brain/memory/store.py` (`_get_engine`, `ensure_schema`, `seed_architecture`, `recall`, `_local`), `services/brain/tests/test_memory.py::test_seed_architecture_idempotent`
- Review notes on task 002 (`tasks/002-ci.md`, Open questions)

## Files you may touch
- `services/brain/memory/**`
- `services/brain/tests/**`

## Scope
1. When Postgres can't actually be reached, memory falls back to the in-process store for the whole call, and `seed_architecture()` checks the fallback store before inserting. Decide "reachable" by a real connection attempt with a short timeout, not by `create_engine` succeeding.
2. When Postgres is reachable, behaviour is unchanged: seed once, skip if architecture rows exist.
3. Keep `reset_for_tests()` working and make the existing test pass with no database and no `DATABASE_URL`.

## Out of scope
- Any change to what the memory stores or how other services call it
- Adding a database service to CI

## Acceptance criteria
- [ ] `cd services/brain && PYTHONPATH=../../packages/ruleset/python pytest` passes with no Postgres running and `DATABASE_URL` unset or pointing at a closed port
- [ ] A new test calls `seed_architecture()` three times with an unreachable `DATABASE_URL` and finds exactly 4 architecture rows
- [ ] The `brain` job in CI is green on the pull request, and every other job stays green
- [ ] No test is skipped, marked xfail or weakened

## Tests
```
cd services/brain && PYTHONPATH=../../packages/ruleset/python pytest
```

## Open questions
_None yet._

---

## Builder report
_Filled in by Cursor._

### Log entries
_One line each: type, area, what happened, lesson._

## Review
_Filled in by Claude Code._
