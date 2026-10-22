from __future__ import annotations

from sqlalchemy import BigInteger, Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from app.config import DATABASE_URL
from app.models_view import CampaignView, CreativeView


class Base(DeclarativeBase):
    pass


class Advertiser(Base):
    __tablename__ = "advertisers"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)


class Seat(Base):
    __tablename__ = "seats"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    advertiser_id: Mapped[int] = mapped_column(Integer)
    seat_id: Mapped[str] = mapped_column(String(64))


class Creative(Base):
    __tablename__ = "creatives"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    advertiser_id: Mapped[int] = mapped_column(Integer)
    asset_uri: Mapped[str] = mapped_column(String(1024))
    mime: Mapped[str] = mapped_column(String(64))
    width: Mapped[int] = mapped_column(Integer)
    height: Mapped[int] = mapped_column(Integer)
    duration_ms: Mapped[int] = mapped_column(Integer)
    validation_status: Mapped[str] = mapped_column(String(32))
    ssp_asset_id: Mapped[str] = mapped_column(String(128), default="")


class Geofence(Base):
    __tablename__ = "geofences"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    h3_cells: Mapped[list] = mapped_column(JSON)
    min_lat: Mapped[float] = mapped_column(Float)
    max_lat: Mapped[float] = mapped_column(Float)
    min_lon: Mapped[float] = mapped_column(Float)
    max_lon: Mapped[float] = mapped_column(Float)


class Campaign(Base):
    __tablename__ = "campaigns"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    advertiser_id: Mapped[int] = mapped_column(Integer)
    state: Mapped[str] = mapped_column(String(32))
    priority: Mapped[int] = mapped_column(Integer)
    bid_cpm_micros: Mapped[int] = mapped_column(BigInteger)
    currency: Mapped[str] = mapped_column(String(8))
    creative_ids: Mapped[list] = mapped_column(JSON)
    geofence_ids: Mapped[list] = mapped_column(JSON)
    total_cap_micros: Mapped[int] = mapped_column(BigInteger)
    daily_cap_micros: Mapped[int] = mapped_column(BigInteger)


class CampaignPlan(Base):
    __tablename__ = "campaign_plans"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    campaign_id: Mapped[int] = mapped_column(Integer)
    dayparts: Mapped[list] = mapped_column(JSON)
    venue_allowlist: Mapped[list] = mapped_column(JSON)
    countries: Mapped[list] = mapped_column(JSON)
    geofence_ids: Mapped[list] = mapped_column(JSON)
    bid_cpm_micros: Mapped[int] = mapped_column(BigInteger)
    shade_factor: Mapped[float] = mapped_column(Float)
    approved: Mapped[bool] = mapped_column(Boolean)


engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)


def load_active_campaigns(db: Session) -> list[CampaignView]:
    camps = db.query(Campaign).filter(Campaign.state == "active").all()
    out: list[CampaignView] = []
    for camp in camps:
        plan = (
            db.query(CampaignPlan)
            .filter(CampaignPlan.campaign_id == camp.id, CampaignPlan.approved.is_(True))
            .order_by(CampaignPlan.id.desc())
            .first()
        )
        seat = db.query(Seat).filter(Seat.advertiser_id == camp.advertiser_id).first()
        geo_ids = (plan.geofence_ids if plan and plan.geofence_ids else camp.geofence_ids) or []
        fences = db.query(Geofence).filter(Geofence.id.in_(geo_ids)).all() if geo_ids else []
        h3: list[int] = []
        min_lat = min((g.min_lat for g in fences), default=-90)
        max_lat = max((g.max_lat for g in fences), default=90)
        min_lon = min((g.min_lon for g in fences), default=-180)
        max_lon = max((g.max_lon for g in fences), default=180)
        for g in fences:
            h3.extend(int(x) for x in (g.h3_cells or []))
        creatives = []
        for cid in camp.creative_ids or []:
            cr = db.get(Creative, int(cid))
            if cr and cr.validation_status == "valid":
                creatives.append(
                    CreativeView(
                        id=cr.id,
                        width=cr.width,
                        height=cr.height,
                        mime=cr.mime,
                        cdn_url=cr.asset_uri,
                        duration_ms=cr.duration_ms,
                        ssp_asset_id=cr.ssp_asset_id or str(cr.id),
                    )
                )
        if not creatives:
            continue
        out.append(
            CampaignView(
                id=camp.id,
                advertiser_id=camp.advertiser_id,
                seat=seat.seat_id if seat else f"seat-{camp.advertiser_id}",
                priority=camp.priority,
                bid_cpm_micros=(plan.bid_cpm_micros if plan and plan.bid_cpm_micros else camp.bid_cpm_micros),
                shade_factor=plan.shade_factor if plan else 0.85,
                dayparts=plan.dayparts if plan else [],
                h3_cells=h3,
                min_lat=min_lat,
                max_lat=max_lat,
                min_lon=min_lon,
                max_lon=max_lon,
                venue_types=list(plan.venue_allowlist) if plan else ["roadside", "transit.rail"],
                creatives=creatives,
                currency=camp.currency,
                countries=list(plan.countries) if plan else ["GB", "IE"],
                remaining_micros=camp.total_cap_micros or 50_000_000,
            )
        )
    return out
