from __future__ import annotations

from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Advertiser(Base):
    __tablename__ = "advertisers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company: Mapped[str] = mapped_column(String(255))
    brand_guidelines: Mapped[dict] = mapped_column(JSON, default=dict)
    markets: Mapped[list] = mapped_column(JSON, default=list)
    asa_notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    users: Mapped[list["User"]] = relationship(back_populates="advertiser")
    campaigns: Mapped[list["Campaign"]] = relationship(back_populates="advertiser")
    seats: Mapped[list["Seat"]] = relationship(back_populates="advertiser")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    advertiser_id: Mapped[int] = mapped_column(ForeignKey("advertisers.id"))
    email: Mapped[str] = mapped_column(String(255), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), default="")
    name: Mapped[str] = mapped_column(String(255), default="")

    advertiser: Mapped[Advertiser] = relationship(back_populates="users")


class Seat(Base):
    __tablename__ = "seats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    advertiser_id: Mapped[int] = mapped_column(ForeignKey("advertisers.id"))
    seat_id: Mapped[str] = mapped_column(String(64), unique=True)
    advertiser: Mapped[Advertiser] = relationship(back_populates="seats")


class ScreenSpec(Base):
    __tablename__ = "screen_specs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    publisher: Mapped[str] = mapped_column(String(64))
    format_code: Mapped[str] = mapped_column(String(64))
    width: Mapped[int] = mapped_column(Integer)
    height: Mapped[int] = mapped_column(Integer)
    aspect: Mapped[str] = mapped_column(String(16))
    max_bytes: Mapped[int] = mapped_column(Integer)
    codecs: Mapped[list] = mapped_column(JSON)
    max_duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    venue_types: Mapped[list] = mapped_column(JSON)
    country: Mapped[str] = mapped_column(String(8), default="GB")
    __table_args__ = (UniqueConstraint("publisher", "format_code", "country"),)


class Creative(Base):
    __tablename__ = "creatives"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    advertiser_id: Mapped[int] = mapped_column(ForeignKey("advertisers.id"))
    spec_id: Mapped[int | None] = mapped_column(ForeignKey("screen_specs.id"), nullable=True)
    filename: Mapped[str] = mapped_column(String(255))
    asset_uri: Mapped[str] = mapped_column(String(1024), default="")
    mime: Mapped[str] = mapped_column(String(64), default="")
    width: Mapped[int] = mapped_column(Integer, default=0)
    height: Mapped[int] = mapped_column(Integer, default=0)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    validation_status: Mapped[str] = mapped_column(String(32), default="pending")
    validation_errors: Mapped[list] = mapped_column(JSON, default=list)
    ssp_asset_id: Mapped[str] = mapped_column(String(128), default="")


class Geofence(Base):
    __tablename__ = "geofences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    advertiser_id: Mapped[int] = mapped_column(ForeignKey("advertisers.id"))
    name: Mapped[str] = mapped_column(String(128))
    geojson: Mapped[dict] = mapped_column(JSON)
    h3_cells: Mapped[list] = mapped_column(JSON, default=list)
    min_lat: Mapped[float] = mapped_column(Float)
    max_lat: Mapped[float] = mapped_column(Float)
    min_lon: Mapped[float] = mapped_column(Float)
    max_lon: Mapped[float] = mapped_column(Float)
    h3_res: Mapped[int] = mapped_column(Integer, default=8)


class Campaign(Base):
    __tablename__ = "campaigns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    advertiser_id: Mapped[int] = mapped_column(ForeignKey("advertisers.id"))
    name: Mapped[str] = mapped_column(String(255))
    state: Mapped[str] = mapped_column(String(32), default="draft")
    flight_start: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    flight_end: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    daily_cap_micros: Mapped[int] = mapped_column(BigInteger, default=0)
    total_cap_micros: Mapped[int] = mapped_column(BigInteger, default=0)
    currency: Mapped[str] = mapped_column(String(8), default="GBP")
    priority: Mapped[int] = mapped_column(Integer, default=100)
    bid_cpm_micros: Mapped[int] = mapped_column(BigInteger, default=0)
    creative_ids: Mapped[list] = mapped_column(JSON, default=list)
    geofence_ids: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    advertiser: Mapped[Advertiser] = relationship(back_populates="campaigns")
    plans: Mapped[list["CampaignPlan"]] = relationship(back_populates="campaign")


class CampaignPlan(Base):
    __tablename__ = "campaign_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("campaigns.id"))
    dayparts: Mapped[list] = mapped_column(JSON, default=list)
    venue_allowlist: Mapped[list] = mapped_column(JSON, default=list)
    countries: Mapped[list] = mapped_column(JSON, default=list)
    geofence_ids: Mapped[list] = mapped_column(JSON, default=list)
    bid_cpm_micros: Mapped[int] = mapped_column(BigInteger, default=0)
    shade_factor: Mapped[float] = mapped_column(Float, default=0.85)
    goal: Mapped[str] = mapped_column(Text, default="")
    approved: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    campaign: Mapped[Campaign] = relationship(back_populates="plans")


class AgentThread(Base):
    __tablename__ = "agent_threads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    advertiser_id: Mapped[int] = mapped_column(ForeignKey("advertisers.id"))
    campaign_id: Mapped[int | None] = mapped_column(ForeignKey("campaigns.id"), nullable=True)
    messages: Mapped[list] = mapped_column(JSON, default=list)


class AgentMemory(Base):
    __tablename__ = "agent_memories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    advertiser_id: Mapped[int] = mapped_column(ForeignKey("advertisers.id"))
    content: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list | None] = mapped_column(Vector(1536), nullable=True)


class Insight(Base):
    __tablename__ = "insights"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    advertiser_id: Mapped[int] = mapped_column(ForeignKey("advertisers.id"))
    campaign_id: Mapped[int | None] = mapped_column(ForeignKey("campaigns.id"), nullable=True)
    markdown: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
