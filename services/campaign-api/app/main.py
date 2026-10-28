from __future__ import annotations

from io import BytesIO

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from PIL import Image
from sqlalchemy.orm import Session

from pathlib import Path

from app import agent, analytics, bootstrap, bus, creative, ops, storage
from app.config import CREATIVE_DIR, REDIS_URL
from app.db import get_db, init_db
from app.models import Advertiser, Campaign, CampaignPlan, Creative, Geofence, Insight, ScreenSpec, Seat
from app.schemas import (
    AdvertiserIn,
    AdvertiserOut,
    BudgetIn,
    CampaignIn,
    CampaignOut,
    ChatIn,
    DaypartsIn,
    PlanIn,
    StateIn,
)
from app.state_machine import InvalidTransition, transition

app = FastAPI(title="DOOH Campaign API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    Path(CREATIVE_DIR).mkdir(parents=True, exist_ok=True)
    app.mount("/creatives", StaticFiles(directory=CREATIVE_DIR), name="creatives")
    init_db()
    from app.db import SessionLocal

    db = SessionLocal()
    try:
        bootstrap.seed(db)
    finally:
        db.close()


@app.get("/health")
def health() -> dict:
    return {"ok": True}


@app.post("/v1/advertisers", response_model=AdvertiserOut)
def create_advertiser(body: AdvertiserIn, db: Session = Depends(get_db)):
    adv = Advertiser(
        company=body.company,
        brand_guidelines=body.brand_guidelines,
        markets=body.markets,
        asa_notes=body.asa_notes,
    )
    db.add(adv)
    db.flush()
    from app.models import User

    db.add(User(advertiser_id=adv.id, email=str(body.email), name=body.name))
    db.add(Seat(advertiser_id=adv.id, seat_id=f"seat-{adv.id}"))
    db.commit()
    db.refresh(adv)
    return adv


@app.get("/v1/advertisers")
def list_advertisers(db: Session = Depends(get_db)):
    rows = db.query(Advertiser).all()
    return [{"id": a.id, "company": a.company, "markets": a.markets, "asa_notes": a.asa_notes} for a in rows]


@app.get("/v1/screen-specs")
def list_specs(db: Session = Depends(get_db)):
    return agent.get_screen_catalog(db)


@app.get("/v1/geofences")
def list_geofences(advertiser_id: int, db: Session = Depends(get_db)):
    rows = db.query(Geofence).filter(Geofence.advertiser_id == advertiser_id).all()
    return [
        {
            "id": g.id,
            "name": g.name,
            "min_lat": g.min_lat,
            "max_lat": g.max_lat,
            "min_lon": g.min_lon,
            "max_lon": g.max_lon,
            "h3_cells": g.h3_cells,
        }
        for g in rows
    ]


@app.post("/v1/creatives")
async def upload_creative(
    advertiser_id: int = Form(...),
    spec_id: int = Form(...),
    duration_ms: int = Form(0),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    spec_row = db.get(ScreenSpec, spec_id)
    if not spec_row:
        raise HTTPException(404, "unknown screen spec")
    data = await file.read()
    spec = creative.ScreenSpec(
        id=spec_row.id,
        publisher=spec_row.publisher,
        format_code=spec_row.format_code,
        width=spec_row.width,
        height=spec_row.height,
        aspect=spec_row.aspect,
        max_bytes=spec_row.max_bytes,
        codecs=list(spec_row.codecs),
        max_duration_ms=spec_row.max_duration_ms,
        venue_types=list(spec_row.venue_types),
    )
    errors = creative.validate_asset(file.filename or "asset.bin", data, spec, duration_ms)
    w = h = 0
    mime = creative.guess_mime(file.filename or "")
    try:
        img = Image.open(BytesIO(data))
        w, h = img.size
    except Exception:
        pass
    status = "rejected" if errors else "valid"
    uri = ""
    if not errors:
        key = f"{advertiser_id}/{file.filename}"
        uri = storage.put_creative(key, data, mime)
    row = Creative(
        advertiser_id=advertiser_id,
        spec_id=spec_id,
        filename=file.filename or "asset.bin",
        asset_uri=uri,
        mime=mime,
        width=w,
        height=h,
        duration_ms=duration_ms,
        validation_status=status,
        validation_errors=[{"field": e.field, "message": e.message} for e in errors],
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {
        "id": row.id,
        "validation_status": row.validation_status,
        "validation_errors": row.validation_errors,
        "asset_uri": row.asset_uri,
        "width": row.width,
        "height": row.height,
        "mime": row.mime,
    }


@app.get("/v1/creatives")
def list_creatives(advertiser_id: int, db: Session = Depends(get_db)):
    rows = db.query(Creative).filter(Creative.advertiser_id == advertiser_id).all()
    return [
        {
            "id": c.id,
            "filename": c.filename,
            "validation_status": c.validation_status,
            "asset_uri": c.asset_uri,
            "width": c.width,
            "height": c.height,
            "mime": c.mime,
        }
        for c in rows
    ]


@app.post("/v1/campaigns", response_model=CampaignOut)
def create_campaign(body: CampaignIn, db: Session = Depends(get_db)):
    camp = Campaign(**body.model_dump())
    db.add(camp)
    db.commit()
    db.refresh(camp)
    return camp


@app.get("/v1/campaigns")
def list_campaigns(advertiser_id: int | None = None, db: Session = Depends(get_db)):
    q = db.query(Campaign)
    if advertiser_id:
        q = q.filter(Campaign.advertiser_id == advertiser_id)
    return [
        CampaignOut.model_validate(c).model_dump()
        for c in q.order_by(Campaign.id.desc()).all()
    ]


def _remaining_micros(campaign_id: int) -> int | None:
    try:
        import redis

        r = redis.from_url(REDIS_URL, decode_responses=True, socket_timeout=1.0)
        raw = r.get(f"budget:{campaign_id}:remaining_micros")
        return int(raw) if raw is not None else None
    except Exception:  # noqa: BLE001
        return None


@app.get("/v1/campaigns/{campaign_id}", response_model=CampaignOut)
def get_campaign(campaign_id: int, db: Session = Depends(get_db)):
    camp = db.get(Campaign, campaign_id)
    if not camp:
        raise HTTPException(404, "campaign not found")
    body = CampaignOut.model_validate(camp)
    body.remaining_micros = _remaining_micros(camp.id)
    return body


@app.post("/v1/campaigns/{campaign_id}/state", response_model=CampaignOut)
def set_state(campaign_id: int, body: StateIn, db: Session = Depends(get_db)):
    camp = db.get(Campaign, campaign_id)
    if not camp:
        raise HTTPException(404, "campaign not found")
    try:
        camp.state = transition(camp.state, body.state)
    except InvalidTransition as exc:
        raise HTTPException(400, str(exc)) from exc
    if camp.state == "active":
        plan = (
            db.query(CampaignPlan)
            .filter(CampaignPlan.campaign_id == camp.id)
            .order_by(CampaignPlan.id.desc())
            .first()
        )
        if plan:
            plan.approved = True
            if plan.bid_cpm_micros:
                camp.bid_cpm_micros = plan.bid_cpm_micros
            if plan.geofence_ids:
                camp.geofence_ids = plan.geofence_ids
    db.commit()
    if camp.state in {"active", "paused", "completed"}:
        bus.publish("campaign.plan.updated", {"campaign_id": camp.id, "state": camp.state})
        bus.remember_decision(
            f"Campaign {camp.id} → {camp.state}",
            f"state transition campaign_id={camp.id} state={camp.state}",
            {"campaign_id": camp.id, "state": camp.state},
            kind="campaign",
        )
    db.refresh(camp)
    return camp


@app.post("/v1/campaigns/{campaign_id}/plans")
def create_plan(campaign_id: int, body: PlanIn, db: Session = Depends(get_db)):
    camp = db.get(Campaign, campaign_id)
    if not camp:
        raise HTTPException(404, "campaign not found")
    plan = CampaignPlan(campaign_id=campaign_id, **body.model_dump())
    db.add(plan)
    if body.approved and camp.state == "draft":
        camp.state = "pending_approval"
    db.commit()
    db.refresh(plan)
    if plan.approved:
        bus.publish("campaign.plan.updated", {"campaign_id": campaign_id, "plan_id": plan.id})
    return {"id": plan.id, "approved": plan.approved, "goal": plan.goal}


@app.post("/v1/campaigns/{campaign_id}/budget", response_model=CampaignOut)
def set_budget(campaign_id: int, body: BudgetIn, db: Session = Depends(get_db)):
    camp = db.get(Campaign, campaign_id)
    if not camp:
        raise HTTPException(404, "campaign not found")
    camp.total_cap_micros = body.total_cap_micros
    db.commit()
    if body.reset_remaining:
        try:
            import redis

            r = redis.from_url(REDIS_URL, decode_responses=True, socket_timeout=1.5)
            r.set(f"budget:{camp.id}:remaining_micros", str(body.total_cap_micros))
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(502, f"postgres updated but redis remaining failed: {exc}") from exc
    bus.publish("campaign.plan.updated", {"campaign_id": camp.id, "state": camp.state, "budget": True})
    bus.remember_decision(
        f"Budget cap campaign {camp.id}",
        f"total_cap_micros={body.total_cap_micros} reset_remaining={body.reset_remaining}",
        {
            "campaign_id": camp.id,
            "total_cap_micros": body.total_cap_micros,
            "reset_remaining": body.reset_remaining,
        },
    )
    db.refresh(camp)
    return camp


@app.post("/v1/plans/{plan_id}/dayparts")
def set_dayparts(plan_id: int, body: DaypartsIn, db: Session = Depends(get_db)):
    plan = db.get(CampaignPlan, plan_id)
    if not plan:
        raise HTTPException(404, "plan not found")
    plan.dayparts = body.dayparts
    db.commit()
    bus.publish("campaign.plan.updated", {"campaign_id": plan.campaign_id, "plan_id": plan.id})
    return {"id": plan.id, "dayparts": plan.dayparts}


@app.post("/v1/plans/{plan_id}/approve")
def approve_plan(plan_id: int, db: Session = Depends(get_db)):
    try:
        plan = agent.submit_for_approval(db, plan_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    bus.publish("campaign.plan.updated", {"campaign_id": plan.campaign_id, "plan_id": plan.id})
    return {"id": plan.id, "approved": True}


@app.post("/v1/agent/chat")
def chat(body: ChatIn, db: Session = Depends(get_db)):
    result = agent.run_agent(db, body.advertiser_id, body.campaign_id, body.message)
    return result


@app.get("/v1/ops/health")
def fleet():
    return ops.fleet_health()


@app.get("/v1/analytics/hourly")
def hourly(advertiser_id: int, campaign_id: int | None = None):
    return analytics.campaign_hourly(advertiser_id, campaign_id)


@app.get("/v1/analytics/kpis")
def kpis(advertiser_id: int, campaign_id: int | None = None):
    return analytics.kpis(advertiser_id, campaign_id)


@app.get("/v1/analytics/events")
def events(advertiser_id: int, campaign_id: int | None = None, limit: int = 200):
    return analytics.recent_events(advertiser_id, campaign_id, limit)


@app.get("/v1/campaigns/{campaign_id}/plans")
def list_plans(campaign_id: int, db: Session = Depends(get_db)):
    rows = (
        db.query(CampaignPlan)
        .filter(CampaignPlan.campaign_id == campaign_id)
        .order_by(CampaignPlan.id.desc())
        .limit(20)
        .all()
    )
    return [
        {
            "id": p.id,
            "goal": p.goal,
            "approved": p.approved,
            "dayparts": p.dayparts,
            "venue_allowlist": p.venue_allowlist,
            "countries": p.countries,
            "geofence_ids": p.geofence_ids,
            "bid_cpm_micros": p.bid_cpm_micros,
            "shade_factor": p.shade_factor,
            "created_at": p.created_at.isoformat() if p.created_at else None,
        }
        for p in rows
    ]


@app.get("/v1/insights")
def insights(advertiser_id: int, db: Session = Depends(get_db)):
    rows = (
        db.query(Insight)
        .filter(Insight.advertiser_id == advertiser_id)
        .order_by(Insight.id.desc())
        .limit(20)
        .all()
    )
    live = analytics.summarize_performance(advertiser_id)
    return {
        "live": live,
        "stored": [{"id": r.id, "markdown": r.markdown, "created_at": r.created_at.isoformat()} for r in rows],
    }
