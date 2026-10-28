from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from agents.compliance.rulebook import RULES, SCHOOL_HOURS, WEEKDAYS, Rule


class AuditRequest(BaseModel):
    model_config = {"populate_by_name": True}

    copy_text: str = Field(default="", alias="copy")
    goal: str = ""
    filename: str = ""
    mime: str = ""
    countries: list[str] = Field(default_factory=list)
    venue_types: list[str] = Field(default_factory=list)
    dayparts: list[dict[str, Any]] = Field(default_factory=list)
    category: str = ""
    near_schools: bool = False
    publisher: str = ""
    source: str = "task"


class Finding(BaseModel):
    rule_id: str
    citation: str
    severity: str
    evidence: str
    rewrite: str
    markets: list[str]


class AuditResult(BaseModel):
    verdict: str
    findings: list[Finding] = Field(default_factory=list)
    alternatives: list[str] = Field(default_factory=list)
    markets_reviewed: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    qa_vectors_ref: str = "GET /v1/agents/compliance/vectors"


def _blob(req: AuditRequest) -> str:
    parts = [req.copy_text, req.goal, req.filename, req.category, req.mime, " ".join(req.venue_types)]
    return " ".join(p for p in parts if p).lower()


def _markets(req: AuditRequest) -> list[str]:
    raw = [c.upper() for c in req.countries if c]
    mapped = []
    for c in raw:
        if c in {"GBR", "UK", "GB"}:
            mapped.append("GB")
        elif c in {"IRL", "IE"}:
            mapped.append("IE")
        else:
            mapped.append(c)
    if not mapped:
        mapped = ["GB", "IE"]
    return sorted(set(mapped))


def _school_adjacent(req: AuditRequest) -> bool:
    if req.near_schools:
        return True
    for block in req.dayparts:
        hours = {int(h) for h in block.get("hours") or []}
        dow = int(block.get("dow", 0))
        if dow in WEEKDAYS and hours & SCHOOL_HOURS:
            if any(v.startswith("urban") or "transit" in v for v in req.venue_types):
                return True
    return False


def _venue_hit(rule: Rule, venues: list[str]) -> bool:
    if not rule.venues:
        return True
    for v in venues:
        for need in rule.venues:
            if v == need or v.startswith(need + ".") or need.startswith(v + "."):
                return True
    return False


def audit(req: AuditRequest) -> AuditResult:
    blob = _blob(req)
    markets = _markets(req)
    findings: list[Finding] = []
    school = _school_adjacent(req)

    for rule in RULES:
        if not any(m in rule.markets for m in markets):
            continue
        evidence = next((n for n in rule.needles if n in blob), "")
        if not evidence:
            continue
        if rule.venues and not _venue_hit(rule, req.venue_types) and not school:
            if rule.id in {"cap-18-alcohol", "hfss-cap-children"}:
                findings.append(
                    Finding(
                        rule_id=rule.id,
                        citation=rule.citation,
                        severity="review",
                        evidence=evidence,
                        rewrite=rule.rewrite,
                        markets=list(rule.markets),
                    )
                )
                continue
        severity = rule.severity
        if rule.id in {"cap-18-alcohol", "hfss-cap-children"} and school:
            severity = "reject"
        findings.append(
            Finding(
                rule_id=rule.id,
                citation=rule.citation,
                severity=severity,
                evidence=evidence,
                rewrite=rule.rewrite,
                markets=list(rule.markets),
            )
        )

    notes: list[str] = []
    if "GB" in markets:
        notes.append("Reviewed under UK CAP/ASA (non-broadcast) for OOH placement.")
    if "IE" in markets:
        notes.append("Reviewed under ASAI / Irish OOH publisher constraints; GB clearance is not automatic IE clearance.")
    if req.filename.lower().endswith((".mp4", ".mov")):
        notes.append("Video: lexical scan only — run human visual review for implied claims and age appeal.")
    if req.publisher.lower() in {"jcdecaux", "viooh"}:
        notes.append(f"{req.publisher} network policies may be stricter than CAP; keep publisher rejection fingerprints.")

    rejects = [f for f in findings if f.severity == "reject"]
    reviews = [f for f in findings if f.severity == "review"]
    if rejects:
        verdict = "REJECTED"
    elif reviews:
        verdict = "REQUIRES HUMAN REVIEW"
    else:
        verdict = "APPROVED"

    alternatives = []
    for f in findings:
        if f.rewrite and f.rewrite not in alternatives:
            alternatives.append(f.rewrite)
    if verdict != "APPROVED" and not alternatives:
        alternatives.append("Rewrite as a substantiated brand-awareness line with no absolute, health, or political claim.")

    return AuditResult(
        verdict=verdict,
        findings=findings,
        alternatives=alternatives,
        markets_reviewed=markets,
        notes=notes,
    )


QA_VECTORS: list[dict[str, Any]] = [
    {
        "id": "hyperbole-guarantee",
        "expect": "REJECTED",
        "request": {"goal": "We guarantee you will be the best in the world after one week", "countries": ["GB"]},
    },
    {
        "id": "health-cure",
        "expect": "REJECTED",
        "request": {"copy": "Our tonic cures fatigue", "countries": ["IE"]},
    },
    {
        "id": "alcohol-school-hours",
        "expect": "REJECTED",
        "request": {
            "copy": "Ice-cold lager on your commute",
            "countries": ["GB"],
            "venue_types": ["transit.rail.underground"],
            "dayparts": [{"dow": 1, "hours": [8, 9]}],
            "near_schools": True,
        },
    },
    {
        "id": "hfss-review",
        "expect": "REQUIRES HUMAN REVIEW",
        "request": {
            "copy": "New energy drink — grab a can",
            "countries": ["GB"],
            "venue_types": ["roadside.billboard"],
        },
    },
    {
        "id": "political",
        "expect": "REJECTED",
        "request": {"goal": "Vote for progress this election campaign", "countries": ["GB", "IE"]},
    },
    {
        "id": "finance-guaranteed-returns",
        "expect": "REJECTED",
        "request": {"copy": "Guaranteed returns on your crypto guaranteed plan", "countries": ["GB"]},
    },
    {
        "id": "clean-dublin-commute",
        "expect": "APPROVED",
        "request": {
            "goal": "Run a 2-week brand awareness campaign targeting commuters in Dublin",
            "countries": ["IE"],
            "venue_types": ["transit.rail", "transit.bus"],
        },
    },
]


def from_task(objective: str, context: dict[str, Any]) -> AuditRequest:
    return AuditRequest(
        copy_text=str(context.get("copy") or ""),
        goal=str(context.get("goal") or objective),
        filename=str(context.get("filename") or ""),
        mime=str(context.get("mime") or ""),
        countries=list(context.get("countries") or []),
        venue_types=list(context.get("venue_types") or context.get("venue_allowlist") or []),
        dayparts=list(context.get("dayparts") or []),
        category=str(context.get("category") or ""),
        near_schools=bool(context.get("near_schools") or False),
        publisher=str(context.get("publisher") or ""),
        source="task",
    )
