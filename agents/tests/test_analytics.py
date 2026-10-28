from agents.analytics.engine import avg_cpm_gbp, insight_text, integrity_from_row, kpis_from_hourly, remaining_micros
from agents.analytics.engine import Kpis


def test_cpm_uses_qty_inclusive_imps_once():
    # 14.2 billable imps at £5.525 spend → ~£389k would be wrong if we multiplied qty again
    spend = 5_525_000  # £5.525
    imps = 1000.0
    assert avg_cpm_gbp(spend, imps) == 5.525
    assert avg_cpm_gbp(spend, 0) == 0.0


def test_remaining_and_paced_out():
    assert remaining_micros(50_000_000, 58_000_000) == 0
    assert remaining_micros(50_000_000, 10_000_000) == 40_000_000


def test_kpis_ignore_nobid_spend():
    rows = [
        {"event_type": "bid", "bids": 10, "imps": 100, "spend_micros": 1_000_000, "hour": "a"},
        {"event_type": "nobid", "bids": 50, "imps": 0, "spend_micros": 9_999_999, "hour": "a"},
    ]
    k = kpis_from_hourly(rows, [{"country": "GB", "billable_imps": 80}, {"country": "IE", "billable_imps": 20}])
    assert k.spend_micros == 1_000_000
    assert k.billable_imps == 100
    assert k.gb_imps == 80 and k.ie_imps == 20


def test_integrity_flags_mismatch():
    bad = integrity_from_row(
        {"events_imps": 1000, "hourly_imps": 500, "events_spend": 1_000_000, "hourly_spend": 1_000_000}
    )
    assert bad.ok is False
    good = integrity_from_row(
        {"events_imps": 100, "hourly_imps": 100, "events_spend": 50, "hourly_spend": 50}
    )
    assert good.ok is True


def test_insight_paced_out_is_not_an_outage():
    text = insight_text(Kpis(billable_imps=10, bids=10, hours=1, paced_out=True, spend_gbp=0.01, avg_cpm=1))
    assert "nbr 2" in text or "pacing" in text.lower()
