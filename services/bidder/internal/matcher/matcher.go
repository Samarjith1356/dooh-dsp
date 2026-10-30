package matcher

import (
	"strconv"
	"time"

	"github.com/dooh-dsp/bidder/internal/adapter"
	"github.com/dooh-dsp/bidder/internal/budget"
	"github.com/dooh-dsp/bidder/internal/openrtb"
	"github.com/dooh-dsp/bidder/internal/snapshot"
)

type Result struct {
	Campaign    *snapshot.Campaign
	Creative    *snapshot.CreativeRef
	Price       float64
	Qty         float64
	SpendMicros int64
	NoBidReason int
}

func Match(snap *snapshot.RulesSnapshot, imp adapter.CanonicalImp, now time.Time, bud *budget.Cache) Result {
	if snap == nil || len(snap.Campaigns) == 0 {
		return Result{NoBidReason: 2}
	}
	switch imp.Country {
	case "GBR", "UK":
		imp.Country = "GB"
	case "IRL":
		imp.Country = "IE"
	}

	var best *snapshot.Campaign
	var bestCr *snapshot.CreativeRef
	bestScore := -1.0
	wh := uint64(imp.W)<<32 | uint64(uint32(imp.H))

	for i := range snap.Campaigns {
		c := &snap.Campaigns[i]
		if imp.Lat < c.MinLat || imp.Lat > c.MaxLat || imp.Lon < c.MinLon || imp.Lon > c.MaxLon {
			continue
		}
		if !venueOK(c, imp.VenueTypes) {
			continue
		}
		if len(c.CountrySet) > 0 && imp.Country != "" {
			if _, ok := c.CountrySet[imp.Country]; !ok {
				continue
			}
		}
		if !snapshot.DaypartAllows(c.Daypart, now) {
			continue
		}
		if rem, ok := bud.Remaining(c.ID); !ok || rem <= 0 {
			continue
		}
		cr := creativeOK(c, wh, imp.W, imp.H)
		if cr == nil {
			continue
		}
		price := c.ShadedCPM
		if price < imp.Floor {
			price = imp.Floor
		}
		score := price + float64(c.Priority)
		if score > bestScore {
			bestScore = score
			best = c
			bestCr = cr
		}
	}
	if best == nil {
		return Result{NoBidReason: 2}
	}
	qty := imp.Qty
	if qty <= 0 {
		qty = 1
	}
	price := best.ShadedCPM
	if price < imp.Floor {
		price = imp.Floor
	}
	return Result{
		Campaign:    best,
		Creative:    bestCr,
		Price:       price,
		Qty:         qty,
		SpendMicros: int64(price * 1_000_000.0 * qty / 1000.0),
	}
}

func venueOK(c *snapshot.Campaign, venues []string) bool {
	if len(c.VenueSet) == 0 {
		return true
	}
	for _, v := range venues {
		if _, ok := c.VenueSet[v]; ok {
			return true
		}
		for i := 0; i < len(v); i++ {
			if v[i] == '.' {
				if _, ok := c.VenueSet[v[:i]]; ok {
					return true
				}
			}
		}
	}
	return false
}

func creativeOK(c *snapshot.Campaign, wh uint64, w, h int) *snapshot.CreativeRef {
	if w == 0 && h == 0 {
		if len(c.Creatives) == 0 {
			return nil
		}
		return &c.Creatives[0]
	}
	if cr, ok := c.CreativeByWH[wh]; ok {
		return cr
	}
	return nil
}

// NoticeURLs carries pre-built signed notice endpoints for a bid.
type NoticeURLs struct {
	NURL string
	BURL string
	LURL string
}

func BuildResponse(req *openrtb.BidRequest, ad adapter.SspAdapter, r Result, notices NoticeURLs) *openrtb.BidResponse {
	if r.Campaign == nil {
		return &openrtb.BidResponse{ID: req.ID, Nbr: r.NoBidReason}
	}
	impID := "1"
	if len(req.Imp) > 0 && req.Imp[0].ID != "" {
		impID = req.Imp[0].ID
	}
	asset := ad.MapCreative(snapshot.IDString(r.Creative.ID), r.Creative.SSPAssetID)
	return &openrtb.BidResponse{
		ID:  req.ID,
		Cur: r.Campaign.Currency,
		SeatBid: []openrtb.SeatBid{{
			Seat: r.Campaign.Seat,
			Bid: []openrtb.Bid{{
				ID:      req.ID + "-" + snapshot.IDString(r.Campaign.ID),
				ImpID:   impID,
				Price:   r.Price,
				AdM:     r.Creative.CDNURL,
				NURL:    notices.NURL,
				BURL:    notices.BURL,
				LURL:    notices.LURL,
				CrID:    asset,
				CID:     strconv.FormatUint(uint64(r.Campaign.ID), 10),
				W:       r.Creative.Width,
				H:       r.Creative.Height,
				Adomain: []string{"dooh.local"},
			}},
		}},
	}
}
