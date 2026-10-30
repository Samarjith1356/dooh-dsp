---
id: 003
title: Book spend when an ad plays, not when we bid
lane: trading
status: ready
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
_Filled in by Cursor._

## Review
_Filled in by Claude Code._
