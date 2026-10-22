CREATE DATABASE IF NOT EXISTS rtb;

CREATE TABLE IF NOT EXISTS rtb.events
(
    event_date Date,
    event_time DateTime64(3),
    event_type LowCardinality(String),
    advertiser_id UInt32,
    campaign_id UInt32,
    ssp LowCardinality(String),
    country LowCardinality(String),
    venue_type LowCardinality(String),
    h3 UInt64,
    creative_id UInt32,
    bid_request_id String,
    price_cpm Float32,
    qty_multiplier Float32,
    billable_imps Float32,
    spend_micros Int64,
    snapshot_id UInt64
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(event_date)
ORDER BY (advertiser_id, campaign_id, event_type, event_time)
TTL event_date + INTERVAL 13 MONTH;

CREATE TABLE IF NOT EXISTS rtb.campaign_hourly
(
    advertiser_id UInt32,
    campaign_id UInt32,
    hour DateTime,
    event_type LowCardinality(String),
    bids AggregateFunction(count),
    imps AggregateFunction(sum, Float32),
    spend_micros AggregateFunction(sum, Int64),
    avg_cpm AggregateFunction(avg, Float32)
)
ENGINE = AggregatingMergeTree
ORDER BY (advertiser_id, campaign_id, event_type, hour);

CREATE MATERIALIZED VIEW IF NOT EXISTS rtb.mv_campaign_hourly
TO rtb.campaign_hourly AS
SELECT
    advertiser_id,
    campaign_id,
    toStartOfHour(event_time) AS hour,
    event_type,
    countState() AS bids,
    sumState(billable_imps) AS imps,
    sumState(spend_micros) AS spend_micros,
    avgState(price_cpm) AS avg_cpm
FROM rtb.events
GROUP BY
    advertiser_id,
    campaign_id,
    hour,
    event_type;

CREATE TABLE IF NOT EXISTS rtb.campaign_dim
(
    campaign_id UInt32,
    advertiser_id UInt32,
    name String,
    updated_at DateTime
)
ENGINE = ReplacingMergeTree(updated_at)
ORDER BY campaign_id;
