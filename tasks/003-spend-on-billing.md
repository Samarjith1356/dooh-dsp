---
id: 003
title: Book spend when an ad plays, not when we bid
lane: trading
status: building
depends_on: []
extra_review: [security]
branch: task/003-spend-on-billing
written: 2026-10-30
---

# 003: Book spend when an ad plays, not when we bid

## Why
Today every bid is booked as spend, so the ~£1,620 on the dashboard is the value of bids sent, not money spent. Budgets drain as fast as we bid. With real money, we pay only for ads that actually play (the SSP's billing notice). Spend, budgets and every report must follow plays.

## Context
- **The spec:** `contracts/events.md`. Implement it exactly
- Background: `handbook/02-dooh-101.md`
- `services/bidder/cmd/bidder/main.go`: `handleBid` logs `bid` events with spend. `handleNotice` logs only the type and request id
- `services/bidder/internal/matcher/matcher.go` (~line 140): `NURL` and `BURL` are fixed strings with no parameters
- `services/bidder/internal/logasync/log.go`: the `Event` struct
- `services/ssp-simulator/main.go`: sends requests, ignores responses, never calls notices
- `services/ingest/app.py`: event intake and the ClickHouse insert
- `infra/clickhouse/init.sql`: the `rtb.events` table
- `services/brain/app/pacing.py`: `spent_micros` sums every event type from the hourly view

## Files you may touch
- Trading lane folders
- `.env.example`: add `NOTICE_BASE_URL` and `NOTICE_SIGNING_KEY` (empty value)
- `infra/docker-compose.yml`: environment variables for the `bidder`, `ssp-simulator` and `ingest` services only

## Scope
1. **Bidder, bid response:** build signed `nurl`, `burl` and `lurl` per the contract. `bid` events carry `spend_micros = 0` and `billable_imps = 0`.
2. **Bidder, notices:** verify the signature and price, then log `win`, `billing` or `loss` with every field from the URL. Spend on `billing` uses the contract formula. Failures log `notice_rejected`. Notice handling must not slow the bid handler.
3. **Simulator:** behave as the contract's "Simulator behaviour" section says, with the three `SIM_*` environment variables.
4. **Ingest:** accept the new event types and fields, and drop repeats of `(event_type, bid_request_id, imp_id)` for 48 hours using Redis. Report `duplicates_dropped` on `/health`.
5. **ClickHouse:** add the `imp_id` and `currency` columns to `init.sql`, plus an idempotent migration (`ADD COLUMN IF NOT EXISTS`) that ingest applies at startup, so existing volumes keep working.
6. **Compiler pacing:** compute remaining per the contract (billed spend plus open exposure), reading `rtb.events`.
7. **Tests:**
   - Go: signing and verification, rejection when `p` > `b`, rejection on a bad signature, the spend formula with multiplier 5.2, and zero spend on `bid`
   - Python: ingest dedupe and the pacing formula, in a new `services/ingest/tests`

## Out of scope
- KPI endpoints and dashboard labels (task 001)
- Switching to EUR (task 005). Keep GBP, but carry the `currency` field everywhere
- VIOOH-specific quirks (Sprint 5)

## Acceptance criteria
- [ ] `go test ./...` passes in `services/bidder` and `services/ssp-simulator`. `pytest` passes in `services/brain` and `services/ingest`
- [ ] Average decision time on `/health` stays within +10µs of before. Report before and after
- [ ] After 10 minutes of the stack running, `SELECT event_type, count(), sum(spend_micros) FROM rtb.events GROUP BY event_type` shows spend only on `billing`, wins around 60% of bids, and billing around 98% of wins. Paste the output
- [ ] A `burl` with a bad signature, and one with `p` greater than `b`, each produce `notice_rejected` and no spend. Show the curl commands and the query
- [ ] Calling the same `burl` twice books it once
- [ ] Budget remaining in Redis falls as billing events arrive, not as bids go out. Show values before and after

## Tests
```
cd services/bidder && go test ./...
cd services/ssp-simulator && go test ./...
cd services/brain && PYTHONPATH=../../packages/ruleset/python pytest
cd services/ingest && pytest
docker compose -f infra/docker-compose.yml up -d --build
```

## Open questions
_None yet._

---

## Builder report

### Files changed
- `services/bidder/internal/notice/notice.go` (+ tests): HMAC notice URL build/verify and billing spend formula
- `services/bidder/cmd/bidder/main.go` (+ tests): signed nurl/burl/lurl on bids; `bid` events with zero spend; verified win/billing/loss/notice_rejected notices
- `services/bidder/internal/matcher/matcher.go`, `marshal.go`: accept notice URLs; emit `lurl`
- `services/bidder/internal/logasync/log.go`, `openrtb/types.go`: `imp_id`, `currency`, `LURL`
- `services/ssp-simulator/main.go` (+ tests): SIM_WIN_RATE / SIM_PLAY_DELAY_MS / SIM_PLAY_DROP_RATE notice behaviour
- `services/ingest/app.py` (+ `tests/`): new fields, Redis 48h dedupe, `duplicates_dropped` on `/health`, startup column migration with retry
- `infra/clickhouse/init.sql`: `imp_id`, `currency` columns
- `services/brain/app/pacing.py` (+ `tests/test_pacing.py`): remaining = cap − billed − open win exposure from `rtb.events`
- `.env.example`, `infra/docker-compose.yml`: NOTICE_* and SIM_* env for bidder / ssp-simulator / ingest
- `services/ingest/requirements.txt`: redis + pytest

### Acceptance criteria
- [x] Go/Python unit tests: `docker run … golang:1.23-alpine go test ./…` passed in bidder and ssp-simulator (Go not on host PATH). `pytest` in ingest: 3 passed. Brain: `tests/test_pacing.py` + `tests/test_compiler.py` 5 passed; full `pytest` still fails pre-existing `test_seed_architecture_idempotent` against local Postgres (memory `_load` prefers empty PG over `_local`) — not introduced here.
- [x] Decision latency: before rebuild avg **44µs**; after (fresh bidder counters) avg **38µs** / last **31µs** (within +10µs).
- [x] 10-minute window query:
  ```
  bid	10897	0
  billing	6503	468671550
  loss	4306	0
  nobid	18197	0
  notice_rejected	3	0
  win	6593	0
  ```
  rates: win_rate≈0.605, play_rate≈0.982, other_spend=0.
- [x] Bad signature / p>b → `notice_rejected`, spend 0:
  ```
  curl 'http://localhost:8081/burl?r=rej-sig&i=1&a=1&c=1&cr=9&q=5.2&b=10&cur=GBP&s=00000000000000000000000000000000&p=9'
  curl 'http://localhost:8081/burl?r=rej-price&i=1&a=1&c=1&cr=9&q=5.2&b=10&cur=GBP&s=1e740daa0db36b85fd75fa7f86f4af29&p=10.01'
  ```
  CH: `notice_rejected rej-sig 0` and `notice_rejected rej-price 0`.
- [x] Duplicate burl (`accept-dup`) booked once: one `billing` row spend=49400; ingest `duplicates_dropped` incremented.
- [x] Budget falls with billing, not bids: Redis `budget:1:remaining_micros` T1=229024259 → T2=127760344 while bids continued; recent `bid` spend_micros sum stayed 0.

### Tests
- `cd services/bidder && go test ./...` — run via `docker run --rm -v … golang:1.23-alpine` because `go` is not installed on this PC PATH. **pass**
- `cd services/ssp-simulator && go test ./...` — same Docker workaround. **pass**
- `cd services/brain && PYTHONPATH=../../packages/ruleset/python pytest` — pacing+compiler pass; full suite blocked by pre-existing memory seed test (see above)
- `cd services/ingest && pytest` — **pass** (3)
- `docker compose -f infra/docker-compose.yml up -d --build` — bidder, ssp-simulator, ingest, brain rebuilt and exercised

### Found along the way
- Existing ClickHouse volumes need the ingest startup migration (or manual `ADD COLUMN`) before inserts with `imp_id`/`currency` succeed; migration now retries.
- `test_seed_architecture_idempotent` is flaky/broken when Postgres is up but architecture recall returns empty.
- Lifetime `/health` avg can be inflated by cold-start outliers after a restart; report steady counters after a short warmup.

### Handbook or contract updates needed
- None for the contract. Handbook could note spend-on-billing is live after this merges.

## Review
_Filled in by Claude Code._
