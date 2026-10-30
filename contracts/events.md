# Contract: trading events

Version 1.0, 30 Oct 2026. Between Trading (bidder, ssp-simulator, ingest, compiler) and Platform (KPIs, reports, wallet).

## The rule that matters

**Spend is booked only on a `billing` event,** meaning the SSP has told us the ad played. Bids and wins never carry spend.

## Event types

| `event_type` | When | `spend_micros` | `billable_imps` | `price_cpm` |
|---|---|---|---|---|
| `nobid` | We answered no-bid | 0 | 0 | 0 |
| `bid` | We answered with a bid | 0 | 0 | Our bid CPM |
| `win` | The SSP called our `nurl` | 0 | 0 | Clearing CPM |
| `billing` | The SSP called our `burl`, so the ad played | `round(price x multiplier x 1000)` | multiplier | Clearing CPM |
| `loss` | The SSP called our `lurl` (if it sends losses) | 0 | 0 | 0 |
| `notice_rejected` | A notice failed its signature or price check | 0 | 0 | As received |

`spend_micros` uses: CPM in currency units x multiplier / 1000 = cost in currency units, and x 1,000,000 = micros. So micros = CPM x multiplier x 1000.

## Fields on every event

The existing `rtb.events` columns stay. Two are added:

| Field | Type | Meaning |
|---|---|---|
| `imp_id` | String | The impression id from the bid request |
| `currency` | LowCardinality(String) | ISO code of the bid and notice price, e.g. `EUR` |

## Notice URLs we put in each bid

The bidder builds `nurl`, `burl` and `lurl` for every bid. Each URL carries everything needed to book the event without a database lookup:

```
{NOTICE_BASE_URL}/burl?r={bid_request_id}&i={imp_id}&a={advertiser_id}&c={campaign_id}
  &cr={creative_id}&q={multiplier}&b={our_bid_cpm}&cur={currency}&s={signature}&p=${AUCTION_PRICE}
```

- `NOTICE_BASE_URL` comes from the environment and defaults to the bidder's own address.
- `s` is the first 32 hex characters of HMAC-SHA256, keyed with `NOTICE_SIGNING_KEY`, over every parameter except `s` and `p`, in the order shown. The SSP fills in `p`, so it can't be signed.
- A notice is rejected (logged as `notice_rejected`, HTTP 204, nothing booked) if the signature is wrong, `p` is missing or not a number, or `p` is greater than `b`. We never pay more than we bid.
- Notice handling runs off the bid decision path and logs through the async logger.

## Counted once

The same `(event_type, bid_request_id, imp_id)` is counted once. Ingest drops repeats seen in the last 48 hours and counts them in a `duplicates_dropped` metric.

## Budget remaining (compiler pacing)

```
remaining = total_cap
          - billed spend
          - open exposure (wins in the last 60 minutes with no billing yet)
```

A win with no billing after 60 minutes is treated as not played and released. Remaining never goes below zero.

## What consumers count

| Number | From |
|---|---|
| Spend, billable impressions, plays | `billing` events |
| Bids | `bid` events |
| Wins | `win` events |
| Win rate | wins / bids |
| Play rate | billing / wins |

## Simulator behaviour (for realistic tests)

For each bid it receives, the simulator:

1. Wins with probability `SIM_WIN_RATE` (default 0.6), otherwise calls `lurl` if present.
2. On a win, picks a clearing price uniformly between `max(floor, 0.7 x bid)` and the bid, then calls `nurl` with that price.
3. After `SIM_PLAY_DELAY_MS` (default 2000) calls `burl` with the same price, except with probability `SIM_PLAY_DROP_RATE` (default 0.02), when it never calls it. That simulates a screen going offline.
4. Uses the notice URLs exactly as received, replacing only `${AUCTION_PRICE}`.
