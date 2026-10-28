package main

import (
	"bytes"
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"strconv"
	"testing"

	"github.com/dooh-dsp/bidder/internal/adapter"
	"github.com/dooh-dsp/bidder/internal/budget"
	"github.com/dooh-dsp/bidder/internal/logasync"
	"github.com/dooh-dsp/bidder/internal/snapshot"
)

func testSnap() *snapshot.RulesSnapshot {
	return &snapshot.RulesSnapshot{
		SnapshotID: 3,
		Campaigns: []snapshot.Campaign{{
			ID: 1, AdvertiserID: 1, Seat: "s", Priority: 1,
			BidCPMMicros: 6_500_000,
			Shading:      snapshot.Shading{ShadeFactor: 0.85, MinCPM: 1, MaxCPM: 10},
			MinLat:       51.28, MaxLat: 51.70, MinLon: -0.50, MaxLon: 0.25,
			VenueTypes: []string{"roadside"},
			Countries:  []string{"GB"},
			Creatives:  []snapshot.CreativeRef{{ID: 9, Width: 1920, Height: 1080, CDNURL: "http://cdn/a.png"}},
			Currency:   "GBP",
		}},
	}
}

func testBidder(adapterName string, rem int64) *bidder {
	hold := &snapshot.Holder{}
	hold.Store(testSnap())
	bud := budget.New()
	bud.Ensure([]uint32{1}, rem)
	b := newBidder(adapter.New(adapterName), bud, logasync.New(""), "http://bidder:8081")
	b.load(hold.Load())
	return b
}

var testPayload, _ = json.Marshal(map[string]any{
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

func post(b *bidder, payload []byte) *httptest.ResponseRecorder {
	rec := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodPost, "/openrtb/v2/bid", bytes.NewReader(payload))
	b.handleBid(rec, req)
	return rec
}

func TestBidDecisionUnder1ms(t *testing.T) {
	b := testBidder("simulator", 1<<50)
	var maxUs int64
	for i := 0; i < 200; i++ {
		rec := post(b, testPayload)
		if rec.Code != 200 {
			t.Fatalf("status %d body %s", rec.Code, rec.Body.String())
		}
		if !bytes.Contains(rec.Body.Bytes(), []byte(`"seatbid"`)) {
			t.Fatalf("expected bid, got %s", rec.Body.String())
		}
		n, err := strconv.ParseInt(rec.Header().Get("X-DSP-Decision-Us"), 10, 64)
		if err != nil {
			t.Fatalf("decision header %q", rec.Header().Get("X-DSP-Decision-Us"))
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
	b := testBidder("simulator", 1<<50)
	rec := post(b, []byte(`{"id":"s","site":{"id":"x"},"imp":[{"id":"1"}]}`))
	if rec.Code != 200 || !bytes.Contains(rec.Body.Bytes(), []byte(`"nbr":2`)) {
		t.Fatalf("status %d body %s", rec.Code, rec.Body.String())
	}
}

func TestNoSnapshotIsNoBid(t *testing.T) {
	b := newBidder(adapter.New("simulator"), budget.New(), logasync.New(""), "")
	rec := post(b, testPayload)
	if rec.Code != 200 || rec.Body.String() != `{"id":"lat-1","nbr":2}` {
		t.Fatalf("status %d body %s", rec.Code, rec.Body.String())
	}
}

func TestBadJSONIs400(t *testing.T) {
	b := testBidder("simulator", 1<<50)
	if rec := post(b, []byte(`{"id":`)); rec.Code != 400 {
		t.Fatalf("status %d", rec.Code)
	}
}

func TestChunkedBodyWithoutContentLength(t *testing.T) {
	b := testBidder("simulator", 1<<50)
	rec := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodPost, "/openrtb/v2/bid", io.MultiReader(bytes.NewReader(testPayload[:10]), bytes.NewReader(testPayload[10:])))
	req.ContentLength = -1
	b.handleBid(rec, req)
	if !bytes.Contains(rec.Body.Bytes(), []byte(`"seatbid"`)) {
		t.Fatalf("body %s", rec.Body.String())
	}
}

// VIOOH sends venue type in dooh.ext; the fast parser must keep it.
func TestVioohExtVenueMatches(t *testing.T) {
	b := testBidder("viooh", 1<<50)
	payload := []byte(`{"id":"v1","imp":[{"id":"1","banner":{"w":1920,"h":1080}}],"dooh":{"id":"x","ext":{"screenid":"s1","venuetype":"roadside"}},"device":{"geo":{"lat":51.5,"lon":-0.1,"country":"UK"}}}`)
	rec := post(b, payload)
	if !bytes.Contains(rec.Body.Bytes(), []byte(`"crid":"viooh-9"`)) {
		t.Fatalf("expected VIOOH bid, got %s", rec.Body.String())
	}
}

func TestHandlerAllocs(t *testing.T) {
	b := testBidder("simulator", 1<<62)
	rec := httptest.NewRecorder()
	rd := bytes.NewReader(testPayload)
	req := httptest.NewRequest(http.MethodPost, "/openrtb/v2/bid", rd)
	n := testing.AllocsPerRun(500, func() {
		rd.Reset(testPayload)
		rec.Body.Reset()
		b.handleBid(rec, req)
	})
	// Request ID, decision header value + slice. The recorder's own header
	// snapshot is test-harness overhead.
	if n > 6 {
		t.Fatalf("allocs per bid = %v", n)
	}
}

func BenchmarkHandleBid(b *testing.B) {
	bd := testBidder("simulator", 1<<62)
	rec := httptest.NewRecorder()
	rd := bytes.NewReader(testPayload)
	req := httptest.NewRequest(http.MethodPost, "/openrtb/v2/bid", rd)
	b.ReportAllocs()
	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		rd.Reset(testPayload)
		rec.Body.Reset()
		bd.handleBid(rec, req)
	}
}

func BenchmarkLoopback1(b *testing.B) {
	runLoopback(b, http.HandlerFunc(testBidder("simulator", 1<<62).handleBid), 1)
}

func BenchmarkLoopback32(b *testing.B) {
	runLoopback(b, http.HandlerFunc(testBidder("simulator", 1<<62).handleBid), 32)
}
