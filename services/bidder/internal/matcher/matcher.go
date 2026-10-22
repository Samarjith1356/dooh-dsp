package matcher

import (
	"strconv"
	"strings"
	"time"

	"github.com/dooh-dsp/bidder/internal/adapter"
	"github.com/dooh-dsp/bidder/internal/budget"
	"github.com/dooh-dsp/bidder/internal/openrtb"
	"github.com/dooh-dsp/bidder/internal/snapshot"
)

type Result struct {
	Campaign *snapshot.Campaign
	Creative *snapshot.CreativeRef
	Price    float64
	Qty      float64
	SpendMicros int64
	NoBidReason int
}

func Match(snap *snapshot.RulesSnapshot, imp adapter.CanonicalImp, now time.Time, bud *budget.Cache) Result {
	if snap == nil || len(snap.Campaigns) == 0 {
		return Result{NoBidReason: 2}
	}
	if imp.Country != "" {
		// ISO-3166-1 alpha-3 sometimes used
		if imp.Country == "GBR" {
			imp.Country = "GB"
		}
		if imp.Country == "IRL" {
			imp.Country = "IE"
		}
	}

	var best *snapshot.Campaign
	var bestCr *snapshot.CreativeRef
	bestScore := -1.0

	for i := range snap.Campaigns {
		c := &snap.Campaigns[i]
		if !geoOK(c, imp) {
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
		if rem, ok := bud.Remaining(c.ID); !ok {
			continue
		} else if rem <= 0 {
			continue
		}
		cr := creativeOK(c, imp.W, imp.H)
		if cr == nil {
			continue
		}
		price := shade(c, imp.Floor)
		if price < imp.Floor {
			continue
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
	spend := int64(priceMicros(best, imp.Floor) * qty / 1000.0)
	return Result{
		Campaign:    best,
		Creative:    bestCr,
		Price:       shade(best, imp.Floor),
		Qty:         qty,
		SpendMicros: spend,
	}
}

func geoOK(c *snapshot.Campaign, imp adapter.CanonicalImp) bool {
	if imp.Lat == 0 && imp.Lon == 0 {
		return false
	}
	if imp.Lat < c.MinLat || imp.Lat > c.MaxLat || imp.Lon < c.MinLon || imp.Lon > c.MaxLon {
		return false
	}
	if len(c.H3Set) == 0 {
		return true
	}
	cell := snapshot.GridCell(imp.Lat, imp.Lon)
	if _, ok := c.H3Set[cell]; ok {
		return true
	}
	// Seeded H3 ids are opaque; bbox already passed.
	return true
}

func venueOK(c *snapshot.Campaign, venues []string) bool {
	if len(c.VenueSet) == 0 {
		return true
	}
	for _, v := range venues {
		if _, ok := c.VenueSet[v]; ok {
			return true
		}
		for allowed := range c.VenueSet {
			if strings.HasPrefix(v, allowed) || strings.HasPrefix(allowed, v) {
				return true
			}
		}
	}
	return false
}

func creativeOK(c *snapshot.Campaign, w, h int) *snapshot.CreativeRef {
	for i := range c.Creatives {
		cr := &c.Creatives[i]
		if (w == 0 && h == 0) || (cr.Width == w && cr.Height == h) {
			return cr
		}
	}
	return nil
}

func shade(c *snapshot.Campaign, floor float64) float64 {
	raw := float64(c.BidCPMMicros) / 1_000_000.0
	f := c.Shading.ShadeFactor
	if f <= 0 {
		f = 0.85
	}
	price := raw * f
	if c.Shading.MinCPM > 0 && price < c.Shading.MinCPM {
		price = c.Shading.MinCPM
	}
	if c.Shading.MaxCPM > 0 && price > c.Shading.MaxCPM {
		price = c.Shading.MaxCPM
	}
	if price < floor {
		price = floor
	}
	return price
}

func priceMicros(c *snapshot.Campaign, floor float64) float64 {
	return shade(c, floor) * 1_000_000.0
}

func BuildResponse(req *openrtb.BidRequest, imp adapter.CanonicalImp, ad adapter.SspAdapter, r Result) *openrtb.BidResponse {
	if r.Campaign == nil {
		return &openrtb.BidResponse{ID: req.ID, Nbr: r.NoBidReason}
	}
	impID := "1"
	if len(req.Imp) > 0 {
		impID = req.Imp[0].ID
	}
	asset := ad.MapCreative(snapshot.IDString(r.Creative.ID), r.Creative.SSPAssetID)
	adm := r.Creative.CDNURL
	return &openrtb.BidResponse{
		ID:  req.ID,
		Cur: r.Campaign.Currency,
		SeatBid: []openrtb.SeatBid{{
			Seat: r.Campaign.Seat,
			Bid: []openrtb.Bid{{
				ID:      req.ID + "-" + snapshot.IDString(r.Campaign.ID),
				ImpID:   impID,
				Price:   r.Price,
				AdM:     adm,
				NURL:    "http://bidder:8081/nurl",
				BURL:    "http://bidder:8081/burl",
				CrID:    asset,
				CID:     strconv.FormatUint(uint64(r.Campaign.ID), 10),
				W:       r.Creative.Width,
				H:       r.Creative.Height,
				Adomain: []string{"dooh.local"},
			}},
		}},
	}
}
