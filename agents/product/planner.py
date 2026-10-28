from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

from agents.compliance.scanner import AuditRequest, AuditResult, audit as compliance_audit

Intent = Literal["plan", "performance", "catalog"]

NAMED_FENCES = {
    "london": 1,
    "dublin": 2,
}


class CampaignPlanJSON(BaseModel):
    """Mirrors campaign-api PlanIn — Brain compiler input after approval."""

    goal: str
    countries: list[str] = Field(default_factory=lambda: ["GB", "IE"])
    venue_allowlist: list[str] = Field(default_factory=list)
    dayparts: list[dict[str, Any]] = Field(default_factory=list)
    geofence_ids: list[int] = Field(default_factory=list)
    geofence_hints: list[str] = Field(default_factory=list)
    bid_cpm_micros: int = 6_500_000
    shade_factor: float = 0.85
    currency: str = "GBP"
    flight_start: str = ""
    flight_end: str = ""
    approved: bool = False
    needs_approval: bool = True
    daypart_convention: str = (
        "heuristic commute dow 0-4 = weekdays; Go time.Weekday Sunday=0 — map before compile"
    )


class Orchestration(BaseModel):
    intent: Intent
    reply: str
    plan: CampaignPlanJSON | None = None
    compliance: AuditResult | None = None
    insight: str | None = None
    next_state: str = "draft"
    can_present_approval: bool = False
    parse_notes: list[str] = Field(default_factory=list)


def classify(message: str) -> Intent:
    lower = message.lower().strip()
    if lower.startswith("performance") or "how is" in lower:
        return "performance"
    if lower.startswith("catalog"):
        return "catalog"
    return "plan"


def parse_goal(message: str, geofence_ids: list[int] | None = None) -> tuple[CampaignPlanJSON, list[str]]:
    text = message.lower()
    notes: list[str] = []
    countries: list[str] = []
    if "dublin" in text or "ireland" in text:
        countries.append("IE")
    if "london" in text or "uk" in text or "britain" in text:
        countries.append("GB")
    if not countries:
        countries = ["GB", "IE"]
        notes.append("No market token — defaulted to GB+IE")

    if "commut" in text or "transit" in text or "underground" in text or "rail" in text:
        venues = ["transit.rail", "transit.rail.underground", "transit.bus"]
    elif "road" in text or "billboard" in text:
        venues = ["roadside", "roadside.billboard"]
    else:
        venues = ["roadside", "transit.rail", "urban.street"]
        notes.append("No venue token — defaulted to roadside+transit+street")

    commute = "commut" in text
    hours = list(range(7, 10)) + list(range(17, 20)) if commute else list(range(6, 23))
    days = list(range(0, 5)) if "weekday" in text or commute else list(range(0, 7))
    dayparts = [{"dow": d, "hours": hours} for d in days]

    weeks = 2
    m = re.search(r"(\d+)\s*-?\s*week", text)
    if m:
        weeks = int(m.group(1))

    hints: list[str] = []
    ids: list[int] = []
    if "dublin" in text:
        hints.append("Dublin city center")
        ids.append(NAMED_FENCES["dublin"])
    if "london" in text:
        hints.append("London transport hubs")
        ids.append(NAMED_FENCES["london"])
    if geofence_ids:
        ids = [int(x) for x in geofence_ids]
    elif not ids:
        ids = [NAMED_FENCES["london"], NAMED_FENCES["dublin"]]
        hints = ["London transport hubs", "Dublin city center"]

    start = datetime.now(timezone.utc)
    end = start + timedelta(weeks=weeks)
    return CampaignPlanJSON(
        goal=message,
        countries=countries,
        venue_allowlist=venues,
        dayparts=dayparts,
        geofence_ids=ids,
        geofence_hints=hints,
        flight_start=start.isoformat(),
        flight_end=end.isoformat(),
        approved=False,
        needs_approval=True,
    ), notes


def client_reply(plan: CampaignPlanJSON, compliance: AuditResult) -> str:
    markets = " and ".join(plan.countries)
    venues = ", ".join(plan.venue_allowlist)
    flight = f"{plan.flight_start[:10]} → {plan.flight_end[:10]}"
    cpm = plan.bid_cpm_micros / 1_000_000
    if compliance.verdict == "REJECTED":
        alts = " ".join(compliance.alternatives[:2])
        return (
            "I cannot send this goal for approval as written. "
            f"Compliance verdict REJECTED under {markets}. "
            f"{alts} "
            "Rewrite the brief without absolute, health, political, or guaranteed-return claims, then I will draft again."
        )
    if compliance.verdict == "REQUIRES HUMAN REVIEW":
        return (
            f"I drafted a {markets} DOOH plan ({venues}; {flight}; £{cpm:.2f} CPM, shade {plan.shade_factor}). "
            "Compliance flagged items that need a human reviewer before you can approve. "
            "This is not a live bid rule and will not compile until signed off."
        )
    return (
        f"Drafted a structured DOOH plan for {markets} (not a live bid rule). "
        f"Venues: {venues}. Flight {flight}. "
        f"Proposed £{cpm:.2f} CPM with {plan.shade_factor} shade in GBP micros. "
        "Approve in Agent Studio to move draft → pending_approval, then activate so Brain compiles Redis."
    )


def orchestrate(
    message: str,
    advertiser_id: int = 1,
    campaign_id: int | None = None,
    geofence_ids: list[int] | None = None,
    insight: str | None = None,
) -> Orchestration:
    intent = classify(message)
    if intent == "catalog":
        return Orchestration(
            intent=intent,
            reply=(
                "JCDecaux/VIOOH-shaped specs live in GET /v1/screen-specs "
                "(e.g. ROADSIDE_LANDSCAPE 1920×1080 GB, LU_6SHEET 1080×1920, Dublin landscape/transit). "
                "Upload must match WxH before Brain will compile the creative."
            ),
            next_state="draft",
            can_present_approval=False,
        )
    if intent == "performance":
        body = insight or (
            "I will pull hourly rollups from Analytics. "
            "If you see zero remaining micros, that is pacing (nbr 2), not a platform outage."
        )
        return Orchestration(
            intent=intent,
            reply=body,
            insight=insight,
            next_state="active",
            can_present_approval=False,
        )

    plan, notes = parse_goal(message, geofence_ids)
    compliance = compliance_audit(
        AuditRequest(
            goal=message,
            countries=plan.countries,
            venue_types=plan.venue_allowlist,
            dayparts=plan.dayparts,
        )
    )
    can_approve = compliance.verdict == "APPROVED"
    next_state = "pending_approval" if can_approve else "draft"
    return Orchestration(
        intent="plan",
        reply=client_reply(plan, compliance),
        plan=plan,
        compliance=compliance,
        next_state=next_state,
        can_present_approval=can_approve,
        parse_notes=notes,
    )
