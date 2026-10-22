package matcher

import (
	"testing"
	"time"

	"github.com/dooh-dsp/bidder/internal/adapter"
	"github.com/dooh-dsp/bidder/internal/budget"
	"github.com/dooh-dsp/bidder/internal/snapshot"
)

func TestMatchLondonRoadside(t *testing.T) {
	snap := &snapshot.RulesSnapshot{
		Campaigns: []snapshot.Campaign{{
			ID:           1,
			AdvertiserID: 1,
			Seat:         "seat-1",
			Priority:     100,
			BidCPMMicros: 6_500_000,
			Shading:      snapshot.Shading{ShadeFactor: 0.85, MinCPM: 1, MaxCPM: 10},
			MinLat:       51.28,
			MaxLat:       51.70,
			MinLon:       -0.50,
			MaxLon:       0.25,
			VenueTypes:   []string{"roadside"},
			Countries:    []string{"GB"},
			Creatives:    []snapshot.CreativeRef{{ID: 9, Width: 1920, Height: 1080, CDNURL: "http://cdn/a.png"}},
			Currency:     "GBP",
		}},
	}
	hold := &snapshot.Holder{}
	hold.Store(snap)
	loaded := hold.Load()
	bud := budget.New()
	bud.Ensure([]uint32{1}, 1_000_000)
	imp := adapter.CanonicalImp{
		VenueTypes: []string{"roadside.billboard"},
		Lat:        51.5074,
		Lon:        -0.1278,
		Country:    "GB",
		W:          1920,
		H:          1080,
		Floor:      2.0,
		Qty:        14.2,
	}
	res := Match(loaded, imp, time.Date(2026, 10, 22, 8, 0, 0, 0, time.UTC), bud)
	if res.Campaign == nil {
		t.Fatal("expected bid")
	}
	if res.Price < 2.0 {
		t.Fatalf("price %v below floor", res.Price)
	}
}

func TestRejectNonMatchingVenue(t *testing.T) {
	snap := &snapshot.RulesSnapshot{
		Campaigns: []snapshot.Campaign{{
			ID:           1,
			BidCPMMicros: 5_000_000,
			MinLat:       51, MaxLat: 52, MinLon: -1, MaxLon: 1,
			VenueTypes: []string{"transit.rail"},
			Creatives:  []snapshot.CreativeRef{{ID: 1, Width: 1920, Height: 1080}},
		}},
	}
	hold := &snapshot.Holder{}
	hold.Store(snap)
	bud := budget.New()
	bud.Ensure([]uint32{1}, 1)
	res := Match(hold.Load(), adapter.CanonicalImp{
		VenueTypes: []string{"retail.mall"},
		Lat: 51.5, Lon: -0.1, W: 1920, H: 1080, Qty: 1,
	}, time.Now(), bud)
	if res.Campaign != nil {
		t.Fatal("expected no-bid")
	}
}
