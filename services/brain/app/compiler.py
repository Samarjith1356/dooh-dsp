from __future__ import annotations

import base64
import json
import sys
import time
from pathlib import Path

_here = Path(__file__).resolve()
for parent in _here.parents:
    candidate = parent / "packages" / "ruleset" / "python"
    if candidate.is_dir():
        sys.path.insert(0, str(candidate))
        break
else:
    sys.path.insert(0, "/packages/ruleset/python")

from ruleset import CompiledCampaign, CreativeRef, RulesSnapshot, ShadingParams  # noqa: E402

from app.models_view import CampaignView


def encode_dayparts(dayparts: list[dict]) -> str:
    bits = bytearray(21)
    if not dayparts:
        for i in range(168):
            bits[i // 8] |= 1 << (i % 8)
        return base64.b64encode(bytes(bits)).decode("ascii")
    for block in dayparts:
        dow = int(block.get("dow", 0))
        for hour in block.get("hours", []):
            idx = dow * 24 + int(hour)
            if 0 <= idx < 168:
                bits[idx // 8] |= 1 << (idx % 8)
    return base64.b64encode(bytes(bits)).decode("ascii")


def rank_overlaps(campaigns: list[CampaignView]) -> dict[int, int]:
    """Higher priority wins overlapping geo/venue/daypart. Tie-break lower id."""
    order = sorted(campaigns, key=lambda c: (-c.priority, c.id))
    return {c.id: i for i, c in enumerate(order)}


def compile_snapshot(campaigns: list[CampaignView], snapshot_id: int) -> RulesSnapshot:
    ranks = rank_overlaps(campaigns)
    compiled: list[CompiledCampaign] = []
    venue_index: dict[str, list[int]] = {}
    h3_index: dict[str, list[int]] = {}
    deal_index: dict[str, list[int]] = {}

    for view in campaigns:
        shading = ShadingParams(
            min_cpm=max(0.01, view.bid_cpm_micros / 1_000_000 * 0.4),
            max_cpm=view.bid_cpm_micros / 1_000_000,
            shade_factor=view.shade_factor,
            pwin_bin=0.45,
        )
        cc = CompiledCampaign(
            id=view.id,
            advertiser_id=view.advertiser_id,
            seat=view.seat,
            priority=1000 - ranks.get(view.id, 100),
            bid_cpm_micros=view.bid_cpm_micros,
            shading=shading,
            daypart_bits=encode_dayparts(view.dayparts),
            h3_cells=view.h3_cells,
            min_lat=view.min_lat,
            max_lat=view.max_lat,
            min_lon=view.min_lon,
            max_lon=view.max_lon,
            venue_types=view.venue_types,
            creatives=[
                CreativeRef(
                    id=cr.id,
                    width=cr.width,
                    height=cr.height,
                    mime=cr.mime,
                    cdn_url=cr.cdn_url,
                    duration_ms=cr.duration_ms,
                    ssp_asset_id=cr.ssp_asset_id or str(cr.id),
                )
                for cr in view.creatives
            ],
            budget_token=f"budget:{view.id}:remaining_micros",
            currency=view.currency,
            deal_ids=view.deal_ids,
            countries=view.countries,
        )
        compiled.append(cc)
        for v in view.venue_types:
            venue_index.setdefault(v, []).append(view.id)
        for cell in view.h3_cells:
            h3_index.setdefault(str(cell), []).append(view.id)
        for deal in view.deal_ids:
            deal_index.setdefault(deal, []).append(view.id)

    return RulesSnapshot(
        snapshot_id=snapshot_id,
        compiled_at_unix=int(time.time()),
        epoch=snapshot_id,
        campaigns=compiled,
        venue_index=venue_index,
        h3_index=h3_index,
        deal_index=deal_index,
    )


def snapshot_json(snapshot: RulesSnapshot) -> str:
    return json.dumps(snapshot.to_dict())


def consult_memory(
    campaigns: list[CampaignView], chunks: list[dict]
) -> tuple[list[CampaignView], list[str]]:
    """Apply control-plane memory to this compile. Does not touch the Go bidder."""
    notes: list[str] = []
    blocked: set[int] = set()
    for ch in chunks:
        kind = str(ch.get("kind") or "")
        title = str(ch.get("title") or "")
        body = f"{title} {ch.get('body') or ''}".lower()
        payload = ch.get("payload") or {}
        cid = payload.get("campaign_id")
        if kind == "architecture":
            notes.append(f"rule: {title or body[:80]}")
        if kind == "decision" and "cap" in body and "reject" in body:
            notes.append("prior cap-raise rejected — do not expand remaining_micros in this compile")
        if kind == "audit" and "pacing" in body:
            notes.append(f"pacing memory: {title[:120]}")
        if payload.get("block_compile") and cid is not None:
            blocked.add(int(cid))
            notes.append(f"memory blocked campaign {cid}: {title[:120]}")
    kept = [c for c in campaigns if c.id not in blocked]
    if len(kept) != len(campaigns):
        notes.append(f"excluded {len(campaigns) - len(kept)} campaign(s) by memory guardrail")
    # unique, keep order
    seen: set[str] = set()
    uniq: list[str] = []
    for n in notes:
        if n in seen:
            continue
        seen.add(n)
        uniq.append(n)
    return kept, uniq[:12]
