from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, EmailStr, Field


class AdvertiserIn(BaseModel):
    company: str
    brand_guidelines: dict[str, Any] = Field(default_factory=dict)
    markets: list[str] = Field(default_factory=lambda: ["GB", "IE"])
    asa_notes: str = ""
    email: EmailStr
    name: str = ""


class AdvertiserOut(BaseModel):
    id: int
    company: str
    markets: list[str]
    asa_notes: str

    class Config:
        from_attributes = True


class CampaignIn(BaseModel):
    advertiser_id: int
    name: str
    flight_start: datetime | None = None
    flight_end: datetime | None = None
    daily_cap_micros: int = 0
    total_cap_micros: int = 0
    currency: str = "GBP"
    priority: int = 100
    bid_cpm_micros: int = 5_000_000
    creative_ids: list[int] = Field(default_factory=list)
    geofence_ids: list[int] = Field(default_factory=list)


class CampaignOut(BaseModel):
    id: int
    advertiser_id: int
    name: str
    state: str
    currency: str
    daily_cap_micros: int
    total_cap_micros: int
    bid_cpm_micros: int
    creative_ids: list[int]
    geofence_ids: list[int]

    class Config:
        from_attributes = True


class StateIn(BaseModel):
    state: str


class PlanIn(BaseModel):
    dayparts: list[dict[str, Any]] = Field(default_factory=list)
    venue_allowlist: list[str] = Field(default_factory=list)
    countries: list[str] = Field(default_factory=lambda: ["GB", "IE"])
    geofence_ids: list[int] = Field(default_factory=list)
    bid_cpm_micros: int = 0
    shade_factor: float = 0.85
    goal: str = ""
    approved: bool = False


class ChatIn(BaseModel):
    advertiser_id: int
    campaign_id: int | None = None
    message: str
