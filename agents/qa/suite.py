from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from agents.compliance.scanner import QA_VECTORS, AuditRequest, audit as compliance_audit
from agents.qa.catalog import ILLEGAL_TRANSITIONS, LEGAL_HAPPY_PATH, OPENRTB_VECTORS, SUITE
from agents.state import snapshot


class CaseResult(BaseModel):
    id: str
    layer: str
    ok: bool
    expected: str
    actual: str
    detail: str = ""


class SuiteReport(BaseModel):
    verdict: str  # GREEN | RED | YELLOW
    passed: int = 0
    failed: int = 0
    cases: list[CaseResult] = Field(default_factory=list)
    layers: dict[str, str] = Field(default_factory=dict)
    openrtb_vectors: list[dict[str, Any]] = Field(default_factory=list)
    live_fleet_ok: bool | None = None
    notes: list[str] = Field(default_factory=list)


def _load_sm():
    import sys
    from pathlib import Path

    api = Path(__file__).resolve().parents[2] / "services" / "campaign-api"
    if str(api) not in sys.path:
        sys.path.insert(0, str(api))
    from app.state_machine import InvalidTransition, compiles, transition  # noqa: WPS433

    return InvalidTransition, compiles, transition


def run_lifecycle() -> list[CaseResult]:
    out: list[CaseResult] = []
    try:
        InvalidTransition, compiles, transition = _load_sm()
    except Exception as exc:  # noqa: BLE001
        return [
            CaseResult(
                id="L1-state-import",
                layer="L1 Campaign API",
                ok=False,
                expected="import state_machine",
                actual=str(exc)[:200],
            )
        ]
    for cur, nxt in LEGAL_HAPPY_PATH:
        got = transition(cur, nxt)
        out.append(
            CaseResult(
                id=f"legal-{cur}-{nxt}",
                layer="L1 Campaign API",
                ok=got == nxt,
                expected=nxt,
                actual=got,
            )
        )
    for cur, nxt in ILLEGAL_TRANSITIONS:
        raised = False
        try:
            transition(cur, nxt)
        except InvalidTransition:
            raised = True
        out.append(
            CaseResult(
                id=f"illegal-{cur}-{nxt}",
                layer="L1 Campaign API",
                ok=raised,
                expected="InvalidTransition",
                actual="raised" if raised else "allowed",
            )
        )
    out.append(
        CaseResult(
            id="compiles-only-active",
            layer="L2 Brain",
            ok=compiles("active") and not compiles("draft") and not compiles("pending_approval"),
            expected="only active",
            actual="ok" if compiles("active") else "broken",
            detail="Brain loader must skip non-active; bidder then nbr:2",
        )
    )
    return out


def run_golden_rule() -> list[CaseResult]:
    from agents.devops.auditor import _scan_bidder_isolation

    ok, findings = _scan_bidder_isolation()
    evidence = "; ".join(f.evidence for f in findings)
    return [
        CaseResult(
            id="L3-golden-rule",
            layer="L3 Bidder",
            ok=ok,
            expected="no CH/PG/LLM on bidder",
            actual="isolated" if ok else evidence,
        )
    ]


def run_compliance() -> list[CaseResult]:
    cases = []
    for vector in QA_VECTORS:
        got = compliance_audit(AuditRequest(**vector["request"]))
        cases.append(
            CaseResult(
                id=f"compliance-{vector['id']}",
                layer="L1 Agent",
                ok=got.verdict == vector["expect"],
                expected=vector["expect"],
                actual=got.verdict,
            )
        )
    return cases


def run_in_process() -> SuiteReport:
    cases: list[CaseResult] = []
    cases.extend(run_lifecycle())
    cases.extend(run_golden_rule())
    cases.extend(run_compliance())
    fleet = snapshot()
    cases.append(
        CaseResult(
            id="fleet-health",
            layer="L0 Infra",
            ok=True,  # informational; live stack may be down during unit runs
            expected="campaign-api/brain/bidder/ingest/redis",
            actual="ok" if fleet.ok else "degraded (ok for offline suite)",
            detail=", ".join(f"{s.name}:{s.ok}" for s in fleet.services),
        )
    )

    failed = [c for c in cases if not c.ok]
    passed = [c for c in cases if c.ok]
    layers: dict[str, str] = {}
    for c in cases:
        bucket = layers.get(c.layer, "GREEN")
        if not c.ok:
            layers[c.layer] = "RED"
        elif bucket != "RED":
            layers[c.layer] = "GREEN"

    verdict = "RED" if failed else "GREEN"
    notes = [
        "Go httptest + matcher benches are listed in catalog (need Go toolchain in CI).",
        "500 QPS is a DevOps chaos playbook, not a pytest default.",
        "Daypart: document Sunday=0 vs agent weekday 0–4 when adding time-based cases.",
        "Live OpenRTB vectors: POST /v1/agents/qa/openrtb",
    ]
    return SuiteReport(
        verdict=verdict,
        passed=len(passed),
        failed=len(failed),
        cases=cases,
        layers=layers,
        openrtb_vectors=OPENRTB_VECTORS,
        live_fleet_ok=fleet.ok,
        notes=notes,
    )
