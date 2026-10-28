from __future__ import annotations

from typing import Any

# Layered registry. Commands run from repo root unless noted.
SUITE: list[dict[str, Any]] = [
    {
        "id": "L1-state-machine",
        "layer": "L1 Campaign API",
        "command": "pytest services/campaign-api/tests/test_state_machine.py -q",
        "asserts": "draft↛active; only active compiles",
        "expect": "pass",
    },
    {
        "id": "L1-creative-aspect",
        "layer": "L1 Campaign API",
        "command": "pytest services/campaign-api/tests/test_creative.py -q",
        "asserts": "100x100 / wrong aspect rejected before Brain",
        "expect": "pass",
    },
    {
        "id": "L1-compliance-vectors",
        "layer": "L1 Agent",
        "command": "pytest agents/tests/test_compliance.py -q",
        "asserts": "non-compliant goals never APPROVED",
        "expect": "pass",
    },
    {
        "id": "L2-compiler",
        "layer": "L2 Brain",
        "command": "PYTHONPATH=packages/ruleset/python pytest services/brain/tests/test_compiler.py -q",
        "asserts": "snapshot JSON compiles; inactive campaigns excluded by loader (state==active)",
        "expect": "pass",
    },
    {
        "id": "L2-ruleset-json",
        "layer": "L2 Brain",
        "command": "pytest packages/ruleset/python/test_ruleset.py -q",
        "asserts": "RulesSnapshot round-trip",
        "expect": "pass",
    },
    {
        "id": "L3-matcher",
        "layer": "L3 Bidder",
        "command": "go test ./internal/matcher ./internal/openrtb ./cmd/bidder -count=1",
        "cwd": "services/bidder",
        "asserts": "London roadside bid; venue miss no-bid; site nbr:2; decision <1000µs after warmup",
        "expect": "pass",
        "optional": True,
    },
    {
        "id": "L3-golden-rule",
        "layer": "L3 Bidder",
        "command": "in-process agents.devops.auditor._scan_bidder_isolation",
        "asserts": "no Postgres/ClickHouse/LLM in bidder Go sources",
        "expect": "pass",
    },
    {
        "id": "L4-kpis",
        "layer": "L4 Analytics",
        "command": "pytest agents/tests/test_analytics.py -q",
        "asserts": "qty not double-counted; nobid excluded from spend; remaining 0 is paced-out",
        "expect": "pass",
    },
    {
        "id": "UX-pillars",
        "layer": "L1 Frontend",
        "command": "pytest agents/tests/test_frontend.py -q",
        "asserts": "four console routes; TS5; RBAC not claimed as server auth",
        "expect": "pass",
    },
]

# Illegal transitions that must raise.
ILLEGAL_TRANSITIONS = (
    ("draft", "active"),
    ("draft", "paused"),
    ("completed", "active"),
    ("completed", "draft"),
)

LEGAL_HAPPY_PATH = (
    ("draft", "pending_approval"),
    ("pending_approval", "active"),
    ("active", "paused"),
    ("paused", "active"),
    ("active", "completed"),
)

OPENRTB_VECTORS: list[dict[str, Any]] = [
    {
        "id": "dooh-london-roadside",
        "expect": "bid-or-nbr2-if-paced-out",
        "qps_role": "happy-path 50 QPS simulator",
        "body": {
            "id": "qa-lon-rd",
            "imp": [
                {
                    "id": "1",
                    "banner": {"w": 1920, "h": 1080},
                    "bidfloor": 4.1,
                    "qty": {"multiplier": 22.0, "sourcetype": 1, "vendor": "viooh.com"},
                }
            ],
            "dooh": {"id": "jcd-rd-001", "venuetype": ["roadside.billboard", "roadside"]},
            "device": {"geo": {"lat": 51.495, "lon": -0.183, "country": "GB"}},
            "tmax": 100,
        },
    },
    {
        "id": "dooh-dublin-portrait",
        "expect": "bid-if-portrait-creative-else-nbr2",
        "body": {
            "id": "qa-dub",
            "imp": [{"id": "1", "banner": {"w": 1080, "h": 1920}, "bidfloor": 2.1, "qty": {"multiplier": 9.0}}],
            "dooh": {"id": "jcd-dub-002", "venuetype": ["transit.bus", "transit.rail"]},
            "device": {"geo": {"lat": 53.347, "lon": -6.259, "country": "IE"}},
        },
    },
    {
        "id": "site-not-dooh",
        "expect": "nbr:2",
        "body": {"id": "qa-site", "site": {"id": "web"}, "imp": [{"id": "1"}]},
    },
    {
        "id": "app-not-dooh",
        "expect": "nbr:2",
        "body": {"id": "qa-app", "app": {"id": "ios"}, "imp": [{"id": "1"}]},
    },
    {
        "id": "creative-mismatch-100x100",
        "expect": "nbr:2",
        "body": {
            "id": "qa-tiny",
            "imp": [{"id": "1", "banner": {"w": 100, "h": 100}, "bidfloor": 1}],
            "dooh": {"id": "x", "venuetype": ["roadside"]},
            "device": {"geo": {"lat": 51.5, "lon": -0.1, "country": "GB"}},
        },
    },
    {
        "id": "malformed-json",
        "expect": "http-400",
        "raw": "{not-json",
    },
    {
        "id": "geo-miss-paris",
        "expect": "nbr:2",
        "body": {
            "id": "qa-paris",
            "imp": [{"id": "1", "banner": {"w": 1920, "h": 1080}}],
            "dooh": {"id": "x", "venuetype": ["roadside"]},
            "device": {"geo": {"lat": 48.85, "lon": 2.35, "country": "FR"}},
        },
    },
]

CURL_LIVE = """# Decision SLA is X-DSP-Decision-Us, not curl wall clock.
curl -sD - -o /dev/null -H 'Content-Type: application/json' \\
  --data '{"id":"qa","imp":[{"id":"1","banner":{"w":1920,"h":1080}}],"dooh":{"id":"x","venuetype":["roadside"]},"device":{"geo":{"lat":51.5,"lon":-0.1,"country":"GB"}}}' \\
  http://localhost:8081/openrtb/v2/bid
"""
