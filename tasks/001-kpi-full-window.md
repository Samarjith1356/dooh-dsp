---
id: 001
title: KPIs from one full-window query, counted from plays
lane: platform
status: ready
depends_on: ["002"]
extra_review: []
branch: task/001-kpi-full-window
written: 2026-10-29
revised: 2026-10-30
---

# 001: KPIs from one full-window query, counted from plays

## Why
The console, Sam's Desk and the analytics agent show "GB imps 0 · IE imps 4,500" beside a total of about 293k billable impressions. The total comes from the hourly view, while the GB/IE split comes from the last 500 raw events, so the two describe different things. The totals are also silently capped: the hourly query has `LIMIT 168`, which counts rows, not hours. And from task 003 on, spend and impressions come only from `billing` events. The KPIs must follow that rule.

## Context
- **The spec:** `contracts/events.md`, section "What consumers count"
- Decision: D-006 in `docs/DECISIONS.md`
- `services/campaign-api/app/analytics.py`: `kpis()` takes totals from `campaign_hourly()` (`LIMIT 168` rows) and the split from `recent_events(limit=500)`. `_query()` also cuts every result to 500 rows
- `agents/analytics/engine.py`: the same pattern, with `LIMIT 168` in the `hourly` SQL, `sample_sql` limited to 500 rows, and `kpis_from_hourly(rows, sample)`
- UI labels: `apps/web/app/(console)/page.tsx:119`, `apps/web/app/(console)/campaigns/[id]/page.tsx:181`, `apps/web/components/console/sams-desk/AgentArtifactViewer.tsx:45`. Types are in `apps/web/lib/types.ts`
- Schema: `infra/clickhouse/init.sql`. `rtb.events` has `country`; `rtb.campaign_hourly` does not

## Files you may touch
- Platform lane folders
- `agents/analytics/engine.py`, `agents/tests/test_analytics.py`
- The four `apps/web` files listed above

## Scope
1. Compute KPI totals with no row cap: aggregate over all hours for the advertiser or campaign in one query.
2. Take spend, billable impressions and plays from `billing` events, bids from `bid` events and wins from `win` events. Add `wins`, `plays`, `win_rate` and `play_rate` to the response, and keep every existing field name.
3. Compute the GB/IE split with one aggregate over `rtb.events` (`event_type = 'billing'`, the same filters, `GROUP BY country`), normalising `GBR` to `GB` and `IRL` to `IE`. Add `other_imps` for anything else.
4. Add `first_event_at` and `last_event_at` to the response.
5. Make the analytics agent use the same numbers, either by calling `GET /v1/analytics/kpis` or by running identical SQL. Explain which you chose in the Builder report, and remove the 500-row sample.
6. Update the three UI labels: drop "from recent event sample" and show the time window instead.
7. Keep advertiser and campaign ids int-cast in the SQL, or switch to query parameters.

## Out of scope
- Schema changes to the materialized view (D-006)
- `recent_events()` as the "latest events" table. It stays as it is
- Anything in the bidder, simulator or ingest (task 003)

## Acceptance criteria
- [ ] `gb_imps + ie_imps + other_imps` equals `billable_imps` for the same request, within float tolerance
- [ ] No `LIMIT` and no `[:500]` truncation stands between the source tables and the KPI totals
- [ ] The response includes `wins`, `plays`, `win_rate`, `play_rate`, `first_event_at` and `last_event_at`
- [ ] Spend is counted only from `billing` events. A test with mixed event types proves it
- [ ] The analytics agent's KPI numbers match `GET /v1/analytics/kpis` for advertiser 1
- [ ] New tests in `services/campaign-api/tests/test_analytics.py` (mocking `_query`) cover the split summing to the total, GBR/IRL normalisation, billing-only spend, and no truncation with more than 500 hourly rows
- [ ] `agents/tests/test_analytics.py` is updated and passes

## Tests
```
cd services/campaign-api && pytest
python -m pytest agents/tests          # from repo root
cd apps/web && npm run build
```

## Open questions
_None yet._

---

## Builder report
_Filled in by Cursor._

## Review
_Filled in by Claude Code._
