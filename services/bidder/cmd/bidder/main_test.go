package main

import (
	"bytes"
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"strconv"
	"testing"
	"time"

	"github.com/dooh-dsp/bidder/internal/adapter"
	"github.com/dooh-dsp/bidder/internal/budget"
	"github.com/dooh-dsp/bidder/internal/logasync"
	"github.com/dooh-dsp/bidder/internal/snapshot"
)

func TestBidDecisionUnder1ms(t *testing.T) {
	hold := &snapshot.Holder{}
	hold.Store(&snapshot.RulesSnapshot{
		Campaigns: []snapshot.Campaign{{
			ID: 1, AdvertiserID: 1, Seat: "s", Priority: 1,
			BidCPMMicros: 6_500_000,
			Shading:      snapshot.Shading{ShadeFactor: 0.85, MinCPM: 1, MaxCPM: 10},
			MinLat: 51.28, MaxLat: 51.70, MinLon: -0.50, MaxLon: 0.25,
			VenueTypes: []string{"roadside"},
			Countries:  []string{"GB"},
			Creatives:  []snapshot.CreativeRef{{ID: 9, Width: 1920, Height: 1080, CDNURL: "http://cdn/a.png"}},
			Currency:   "GBP",
		}},
	})
	bud := budget.New()
	bud.Ensure([]uint32{1}, 50_000_000)
	logs := logasync.New("")
	ad := adapter.New("simulator")

	payload, _ := json.Marshal(map[string]any{
		"id": "lat-1",
		"imp": []map[string]any{{
			"id": "1", "banner": map[string]int{"w": 1920, "h": 1080},
			"bidfloor": 2.0, "qty": map[string]any{"multiplier": 14.2},
		}},
		"dooh": map[string]any{
			"id": "jcd-rd-001", "venuetype": []string{"roadside.billboard", "roadside"},
		},
		"device": map[string]any{"geo": map[string]any{"lat": 51.5074, "lon": -0.1278, "country": "GB"}},
		"tmax":   100,
	})

	var maxUs int64
	for i := 0; i < 200; i++ {
		rec := httptest.NewRecorder()
		req := httptest.NewRequest(http.MethodPost, "/openrtb/v2/bid", bytes.NewReader(payload))
		handleBid(rec, req, ad, hold, bud, logs, "http://bidder:8081", "test-key")
		if rec.Code != 200 {
			t.Fatalf("status %d body %s", rec.Code, rec.Body.String())
		}
		us := rec.Header().Get("X-DSP-Decision-Us")
		n, err := strconv.ParseInt(us, 10, 64)
		if err != nil {
			t.Fatalf("decision header %q", us)
		}
		if i >= 20 && n > maxUs {
			maxUs = n
		}
		_, _ = io.Copy(io.Discard, rec.Body)
	}
	if maxUs >= 1000 {
		t.Fatalf("decision max %dµs after warmup, want <1000µs", maxUs)
	}
}

func TestSiteIsNoBid(t *testing.T) {
	hold := &snapshot.Holder{}
	bud := budget.New()
	logs := logasync.New("")
	payload := []byte(`{"id":"s","site":{"id":"x"},"imp":[{"id":"1"}]}`)
	rec := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodPost, "/openrtb/v2/bid", bytes.NewReader(payload))
	handleBid(rec, req, adapter.New("simulator"), hold, bud, logs, "http://bidder:8081", "test-key")
	if rec.Code != 200 {
		t.Fatalf("status %d", rec.Code)
	}
	if !bytes.Contains(rec.Body.Bytes(), []byte(`"nbr":2`)) {
		t.Fatalf("body %s", rec.Body.String())
	}
}

func TestNoBidOnUnsafeRequestOrImpID(t *testing.T) {
	hold := &snapshot.Holder{}
	hold.Store(&snapshot.RulesSnapshot{
		Campaigns: []snapshot.Campaign{{
			ID: 1, AdvertiserID: 1, Seat: "s", Priority: 1,
			BidCPMMicros: 6_500_000,
			Shading:      snapshot.Shading{ShadeFactor: 0.85, MinCPM: 1, MaxCPM: 10},
			MinLat: 51.28, MaxLat: 51.70, MinLon: -0.50, MaxLon: 0.25,
			VenueTypes: []string{"roadside"},
			Countries:  []string{"GB"},
			Creatives:  []snapshot.CreativeRef{{ID: 9, Width: 1920, Height: 1080, CDNURL: "http://cdn/a.png"}},
			Currency:   "GBP",
		}},
	})
	bud := budget.New()
	bud.Ensure([]uint32{1}, 50_000_000)
	logs := logasync.New("")
	payload, _ := json.Marshal(map[string]any{
		"id": "bad/id",
		"imp": []map[string]any{{
			"id": "1", "banner": map[string]int{"w": 1920, "h": 1080},
			"bidfloor": 2.0, "qty": map[string]any{"multiplier": 5.2},
		}},
		"dooh": map[string]any{
			"id": "jcd-rd-001", "venuetype": []string{"roadside.billboard", "roadside"},
		},
		"device": map[string]any{"geo": map[string]any{"lat": 51.5074, "lon": -0.1278, "country": "GB"}},
	})
	rec := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodPost, "/openrtb/v2/bid", bytes.NewReader(payload))
	handleBid(rec, req, adapter.New("simulator"), hold, bud, logs, "http://bidder:8081", "test-signing-key-at-least-32-bytes!!")
	if rec.Code != 200 {
		t.Fatalf("status %d", rec.Code)
	}
	if !bytes.Contains(rec.Body.Bytes(), []byte(`"nbr":`)) {
		t.Fatalf("want no-bid for unsafe id, body %s", rec.Body.String())
	}
}

func TestBidEventZeroSpend(t *testing.T) {
	hold := &snapshot.Holder{}
	hold.Store(&snapshot.RulesSnapshot{
		Campaigns: []snapshot.Campaign{{
			ID: 1, AdvertiserID: 1, Seat: "s", Priority: 1,
			BidCPMMicros: 6_500_000,
			Shading:      snapshot.Shading{ShadeFactor: 0.85, MinCPM: 1, MaxCPM: 10},
			MinLat: 51.28, MaxLat: 51.70, MinLon: -0.50, MaxLon: 0.25,
			VenueTypes: []string{"roadside"},
			Countries:  []string{"GB"},
			Creatives:  []snapshot.CreativeRef{{ID: 9, Width: 1920, Height: 1080, CDNURL: "http://cdn/a.png"}},
			Currency:   "GBP",
		}},
	})
	bud := budget.New()
	bud.Ensure([]uint32{1}, 50_000_000)
	var got logasync.Event
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		defer r.Body.Close()
		_ = json.NewDecoder(r.Body).Decode(&got)
		w.WriteHeader(200)
	}))
	defer srv.Close()
	logs := logasync.New(srv.URL)
	payload, _ := json.Marshal(map[string]any{
		"id": "spend-0",
		"imp": []map[string]any{{
			"id": "1", "banner": map[string]int{"w": 1920, "h": 1080},
			"bidfloor": 2.0, "qty": map[string]any{"multiplier": 5.2},
		}},
		"dooh": map[string]any{
			"id": "jcd-rd-001", "venuetype": []string{"roadside.billboard", "roadside"},
		},
		"device": map[string]any{"geo": map[string]any{"lat": 51.5074, "lon": -0.1278, "country": "GB"}},
		"tmax":   100,
	})
	rec := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodPost, "/openrtb/v2/bid", bytes.NewReader(payload))
	handleBid(rec, req, adapter.New("simulator"), hold, bud, logs, "http://bidder:8081", "test-key")
	if rec.Code != 200 {
		t.Fatalf("status %d", rec.Code)
	}
	deadline := time.Now().Add(2 * time.Second)
	for time.Now().Before(deadline) && got.EventType == "" {
		time.Sleep(10 * time.Millisecond)
	}
	if got.EventType != "bid" {
		t.Fatalf("event %+v", got)
	}
	if got.SpendMicros != 0 || got.BillableImps != 0 {
		t.Fatalf("bid must carry zero spend/imps: %+v", got)
	}
	if !bytes.Contains(rec.Body.Bytes(), []byte(`"nurl":`)) || !bytes.Contains(rec.Body.Bytes(), []byte(`"burl":`)) {
		t.Fatalf("missing notice urls: %s", rec.Body.String())
	}
}

func BenchmarkHandleBid(b *testing.B) {
	hold := &snapshot.Holder{}
	hold.Store(&snapshot.RulesSnapshot{
		Campaigns: []snapshot.Campaign{{
			ID: 1, Seat: "s", BidCPMMicros: 6_500_000,
			Shading: snapshot.Shading{ShadeFactor: 0.85, MinCPM: 1, MaxCPM: 10},
			MinLat: 51.28, MaxLat: 51.70, MinLon: -0.50, MaxLon: 0.25,
			VenueTypes: []string{"roadside"},
			Countries:  []string{"GB"},
			Creatives:  []snapshot.CreativeRef{{ID: 9, Width: 1920, Height: 1080, CDNURL: "http://cdn/a.png"}},
			Currency:   "GBP",
		}},
	})
	bud := budget.New()
	bud.Ensure([]uint32{1}, 1_000_000_000)
	logs := logasync.New("")
	ad := adapter.New("simulator")
	payload, _ := json.Marshal(map[string]any{
		"id": "lat-1",
		"imp": []map[string]any{{
			"id": "1", "banner": map[string]int{"w": 1920, "h": 1080},
			"bidfloor": 2.0, "qty": map[string]any{"multiplier": 14.2},
		}},
		"dooh": map[string]any{"id": "jcd-rd-001", "venuetype": []string{"roadside.billboard"}},
		"device": map[string]any{"geo": map[string]any{"lat": 51.5074, "lon": -0.1278, "country": "GB"}},
	})
	b.ReportAllocs()
	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		rec := httptest.NewRecorder()
		req := httptest.NewRequest(http.MethodPost, "/openrtb/v2/bid", bytes.NewReader(payload))
		handleBid(rec, req, ad, hold, bud, logs, "http://bidder:8081", "test-key")
		if rec.Code != 200 {
			b.Fatal(rec.Code)
		}
	}
}
