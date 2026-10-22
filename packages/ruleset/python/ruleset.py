"""JSON encoding of packages/ruleset/ruleset.proto (no protoc required at runtime)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class CreativeRef:
    id: int
    width: int
    height: int
    mime: str
    cdn_url: str
    duration_ms: int = 0
    ssp_asset_id: str = ""


@dataclass
class ShadingParams:
    min_cpm: float = 0.0
    max_cpm: float = 0.0
    shade_factor: float = 0.85
    pwin_bin: float = 0.5


@dataclass
class CompiledCampaign:
    id: int
    advertiser_id: int
    seat: str
    priority: int
    bid_cpm_micros: int
    shading: ShadingParams
    daypart_bits: str  # base64 of 21 bytes (168 bits)
    h3_cells: list[int]
    min_lat: float
    max_lat: float
    min_lon: float
    max_lon: float
    venue_types: list[str]
    creatives: list[CreativeRef]
    budget_token: str
    currency: str = "GBP"
    deal_ids: list[str] = field(default_factory=list)
    countries: list[str] = field(default_factory=lambda: ["GB", "IE"])


@dataclass
class RulesSnapshot:
    snapshot_id: int
    compiled_at_unix: int
    epoch: int
    campaigns: list[CompiledCampaign]
    venue_index: dict[str, list[int]]
    h3_index: dict[str, list[int]]
    deal_index: dict[str, list[int]]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["campaigns"] = [
            {**asdict(c), "shading": asdict(c.shading), "creatives": [asdict(cr) for cr in c.creatives]}
            for c in self.campaigns
        ]
        return payload

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RulesSnapshot":
        campaigns = []
        for raw in data.get("campaigns", []):
            shading = ShadingParams(**raw.get("shading", {}))
            creatives = [CreativeRef(**cr) for cr in raw.get("creatives", [])]
            campaigns.append(
                CompiledCampaign(
                    id=raw["id"],
                    advertiser_id=raw["advertiser_id"],
                    seat=raw["seat"],
                    priority=raw["priority"],
                    bid_cpm_micros=raw["bid_cpm_micros"],
                    shading=shading,
                    daypart_bits=raw.get("daypart_bits", ""),
                    h3_cells=list(raw.get("h3_cells", [])),
                    min_lat=raw["min_lat"],
                    max_lat=raw["max_lat"],
                    min_lon=raw["min_lon"],
                    max_lon=raw["max_lon"],
                    venue_types=list(raw.get("venue_types", [])),
                    creatives=creatives,
                    budget_token=raw["budget_token"],
                    currency=raw.get("currency", "GBP"),
                    deal_ids=list(raw.get("deal_ids", [])),
                    countries=list(raw.get("countries", ["GB", "IE"])),
                )
            )
        return cls(
            snapshot_id=data["snapshot_id"],
            compiled_at_unix=data["compiled_at_unix"],
            epoch=data["epoch"],
            campaigns=campaigns,
            venue_index={k: list(v) for k, v in data.get("venue_index", {}).items()},
            h3_index={str(k): list(v) for k, v in data.get("h3_index", {}).items()},
            deal_index={k: list(v) for k, v in data.get("deal_index", {}).items()},
        )
