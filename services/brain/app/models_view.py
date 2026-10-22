from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CreativeView:
    id: int
    width: int
    height: int
    mime: str
    cdn_url: str
    duration_ms: int = 0
    ssp_asset_id: str = ""


@dataclass
class CampaignView:
    id: int
    advertiser_id: int
    seat: str
    priority: int
    bid_cpm_micros: int
    shade_factor: float
    dayparts: list[dict]
    h3_cells: list[int]
    min_lat: float
    max_lat: float
    min_lon: float
    max_lon: float
    venue_types: list[str]
    creatives: list[CreativeView]
    currency: str = "GBP"
    deal_ids: list[str] = field(default_factory=list)
    countries: list[str] = field(default_factory=lambda: ["GB", "IE"])
    remaining_micros: int = 0
