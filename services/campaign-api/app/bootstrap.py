from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models import Advertiser, Campaign, CampaignPlan, Creative, Geofence, ScreenSpec, Seat, User
from app.seed_specs import DUBLIN, LONDON, SCREEN_SPECS


def seed(db: Session) -> None:
    if db.query(ScreenSpec).count() == 0:
        for spec in SCREEN_SPECS:
            db.add(ScreenSpec(**spec))
        db.commit()

    adv = db.query(Advertiser).filter(Advertiser.company == "Demo Brand").one_or_none()
    if adv is None:
        adv = Advertiser(
            company="Demo Brand",
            brand_guidelines={"tone": "premium", "colors": ["#111", "#C4A35A"]},
            markets=["GB", "IE"],
            asa_notes="Follow CAP/ASA. No unsubstantiated superiority claims.",
        )
        db.add(adv)
        db.flush()
        db.add(User(advertiser_id=adv.id, email="demo@dooh.local", name="Demo User"))
        db.add(Seat(advertiser_id=adv.id, seat_id="dooh-demo-seat"))
        db.add(
            Geofence(
                advertiser_id=adv.id,
                name=LONDON["name"],
                geojson=LONDON["geojson"],
                h3_cells=LONDON["h3_cells"],
                min_lat=LONDON["min_lat"],
                max_lat=LONDON["max_lat"],
                min_lon=LONDON["min_lon"],
                max_lon=LONDON["max_lon"],
            )
        )
        db.add(
            Geofence(
                advertiser_id=adv.id,
                name=DUBLIN["name"],
                geojson=DUBLIN["geojson"],
                h3_cells=DUBLIN["h3_cells"],
                min_lat=DUBLIN["min_lat"],
                max_lat=DUBLIN["max_lat"],
                min_lon=DUBLIN["min_lon"],
                max_lon=DUBLIN["max_lon"],
            )
        )
        db.commit()
        db.refresh(adv)
        fences = db.query(Geofence).filter(Geofence.advertiser_id == adv.id).all()
        spec = db.query(ScreenSpec).filter(ScreenSpec.format_code == "ROADSIDE_LANDSCAPE").first()
        cr = Creative(
            advertiser_id=adv.id,
            spec_id=spec.id if spec else None,
            filename="demo-roadside.png",
            asset_uri="https://placehold.co/1920x1080.png",
            mime="image/png",
            width=1920,
            height=1080,
            validation_status="valid",
        )
        db.add(cr)
        db.flush()
        portrait = Creative(
            advertiser_id=adv.id,
            filename="demo-portrait.png",
            asset_uri="https://placehold.co/1080x1920.png",
            mime="image/png",
            width=1080,
            height=1920,
            validation_status="valid",
        )
        db.add(portrait)
        db.flush()
        camp = Campaign(
            advertiser_id=adv.id,
            name="Demo UK/IE commute",
            state="active",
            flight_start=datetime.utcnow(),
            flight_end=datetime.utcnow() + timedelta(weeks=2),
            daily_cap_micros=5_000_000,
            total_cap_micros=50_000_000,
            currency="GBP",
            priority=200,
            bid_cpm_micros=6_500_000,
            creative_ids=[cr.id, portrait.id],
            geofence_ids=[g.id for g in fences],
        )
        db.add(camp)
        db.flush()
        db.add(
            CampaignPlan(
                campaign_id=camp.id,
                dayparts=[],
                venue_allowlist=["roadside", "transit.rail", "transit.bus", "urban.street"],
                countries=["GB", "IE"],
                geofence_ids=[g.id for g in fences],
                bid_cpm_micros=6_500_000,
                shade_factor=0.85,
                goal="Seeded demo: commuters in London and Dublin",
                approved=True,
            )
        )
        db.commit()
