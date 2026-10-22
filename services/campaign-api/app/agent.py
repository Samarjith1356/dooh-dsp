from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any, TypedDict

from sqlalchemy.orm import Session

from app import analytics
from app.config import LANGGRAPH_MODEL, OPENAI_API_KEY
from app.models import Campaign, CampaignPlan, Geofence, ScreenSpec


class AgentState(TypedDict, total=False):
    message: str
    advertiser_id: int
    campaign_id: int | None
    plan: dict[str, Any]
    reply: str
    needs_approval: bool


def get_screen_catalog(db: Session) -> list[dict[str, Any]]:
    rows = db.query(ScreenSpec).all()
    return [
        {
            "id": r.id,
            "publisher": r.publisher,
            "format_code": r.format_code,
            "width": r.width,
            "height": r.height,
            "aspect": r.aspect,
            "max_bytes": r.max_bytes,
            "venue_types": r.venue_types,
            "country": r.country,
        }
        for r in rows
    ]


def heuristic_plan(message: str, db: Session, advertiser_id: int) -> dict[str, Any]:
    text = message.lower()
    countries = []
    if "dublin" in text or "ireland" in text:
        countries.append("IE")
    if "london" in text or "uk" in text or "britain" in text:
        countries.append("GB")
    if not countries:
        countries = ["GB", "IE"]

    venues = []
    if "commut" in text or "transit" in text or "underground" in text or "rail" in text:
        venues = ["transit.rail", "transit.rail.underground", "transit.bus"]
    elif "road" in text or "billboard" in text:
        venues = ["roadside", "roadside.billboard"]
    else:
        venues = ["roadside", "transit.rail", "urban.street"]

    hours = list(range(7, 10)) + list(range(17, 20)) if "commut" in text else list(range(6, 23))
    days = list(range(0, 5)) if "weekday" in text or "commut" in text else list(range(0, 7))
    dayparts = [{"dow": d, "hours": hours} for d in days]

    weeks = 2
    m = re.search(r"(\d+)\s*-?\s*week", text)
    if m:
        weeks = int(m.group(1))

    fences = db.query(Geofence).filter(Geofence.advertiser_id == advertiser_id).all()
    geo_ids = []
    for g in fences:
        if "dublin" in text and "dublin" in g.name.lower():
            geo_ids.append(g.id)
        if "london" in text and "london" in g.name.lower():
            geo_ids.append(g.id)
    if not geo_ids:
        geo_ids = [g.id for g in fences]

    start = datetime.utcnow()
    end = start + timedelta(weeks=weeks)
    return {
        "goal": message,
        "countries": countries,
        "venue_allowlist": venues,
        "dayparts": dayparts,
        "geofence_ids": geo_ids,
        "bid_cpm_micros": 6_500_000,
        "shade_factor": 0.85,
        "flight_start": start.isoformat(),
        "flight_end": end.isoformat(),
        "approved": False,
    }


def _compliance_notes(message: str) -> list[str]:
    flags = []
    lower = message.lower()
    for banned in ("guarantee", "miracle", "cure", "best in the world"):
        if banned in lower:
            flags.append(f"ASA/CAP risk: avoid absolute claim '{banned}'")
    return flags


def run_agent(db: Session, advertiser_id: int, campaign_id: int | None, message: str) -> dict[str, Any]:
    if message.lower().startswith("performance") or "how is" in message.lower():
        summary = analytics.summarize_performance(advertiser_id, campaign_id)
        return {"reply": summary, "plan": None, "needs_approval": False}

    if message.lower().startswith("catalog"):
        catalog = get_screen_catalog(db)
        return {"reply": f"{len(catalog)} JCDecaux/VIOOH specs available.", "plan": None, "catalog": catalog}

    plan = heuristic_plan(message, db, advertiser_id)
    flags = _compliance_notes(message)

    if OPENAI_API_KEY:
        try:
            plan = _langgraph_plan(message, plan)
        except Exception:
            pass

    if campaign_id:
        camp = db.get(Campaign, campaign_id)
        if camp and camp.advertiser_id == advertiser_id:
            row = CampaignPlan(
                campaign_id=campaign_id,
                dayparts=plan["dayparts"],
                venue_allowlist=plan["venue_allowlist"],
                countries=plan["countries"],
                geofence_ids=plan["geofence_ids"],
                bid_cpm_micros=plan["bid_cpm_micros"],
                shade_factor=plan["shade_factor"],
                goal=plan["goal"],
                approved=False,
            )
            db.add(row)
            if camp.state == "draft":
                camp.state = "pending_approval"
            db.commit()

    reply = (
        "Drafted a structured DOOH plan (not a live bid rule). "
        f"Markets: {', '.join(plan['countries'])}. "
        f"Venues: {', '.join(plan['venue_allowlist'])}. "
        f"Flight {plan['flight_start'][:10]} → {plan['flight_end'][:10]}. "
        "Submit for approval, then Brain compiles the in-memory ruleset."
    )
    if flags:
        reply += " Compliance: " + "; ".join(flags)
    return {"reply": reply, "plan": plan, "needs_approval": True, "compliance_flags": flags}


def _langgraph_plan(message: str, seed: dict[str, Any]) -> dict[str, Any]:
    from langgraph.graph import END, START, StateGraph
    from langchain_openai import ChatOpenAI

    llm = ChatOpenAI(model=LANGGRAPH_MODEL, api_key=OPENAI_API_KEY, temperature=0)

    def intake(state: AgentState) -> AgentState:
        return state

    def compliance(state: AgentState) -> AgentState:
        flags = _compliance_notes(state["message"])
        state["reply"] = "; ".join(flags)
        return state

    def propose(state: AgentState) -> AgentState:
        prompt = (
            "Return only a short confirmation that this DOOH plan is sensible for UK/Ireland. "
            f"User goal: {state['message']}"
        )
        llm.invoke(prompt)
        state["plan"] = seed
        state["needs_approval"] = True
        return state

    graph = StateGraph(AgentState)
    graph.add_node("intake", intake)
    graph.add_node("compliance", compliance)
    graph.add_node("propose", propose)
    graph.add_edge(START, "intake")
    graph.add_edge("intake", "compliance")
    graph.add_edge("compliance", "propose")
    graph.add_edge("propose", END)
    app = graph.compile()
    result = app.invoke({"message": message, "plan": seed})
    return result.get("plan") or seed


def submit_for_approval(db: Session, plan_id: int) -> CampaignPlan:
    plan = db.get(CampaignPlan, plan_id)
    if not plan:
        raise ValueError("plan not found")
    plan.approved = True
    camp = db.get(Campaign, plan.campaign_id)
    if camp:
        camp.bid_cpm_micros = plan.bid_cpm_micros or camp.bid_cpm_micros
        camp.geofence_ids = plan.geofence_ids or camp.geofence_ids
    db.commit()
    db.refresh(plan)
    return plan
