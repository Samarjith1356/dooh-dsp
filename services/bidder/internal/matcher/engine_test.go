package matcher

import (
	"encoding/json"
	"math"
	"strings"
	"testing"
	"time"

	"github.com/dooh-dsp/bidder/internal/adapter"
	"github.com/dooh-dsp/bidder/internal/budget"
	"github.com/dooh-dsp/bidder/internal/snapshot"
)

func compiled(t testing.TB, snap *snapshot.RulesSnapshot, rem int64) (*Engine, *budget.Cache) {
	t.Helper()
	h := &snapshot.Holder{}
	h.Store(snap)
	bud := budget.New()
	ids := make([]uint32, 0, len(snap.Campaigns))
	for _, c := range snap.Campaigns {
		ids = append(ids, c.ID)
	}
	bud.Ensure(ids, rem)
	return Compile(h.Load(), adapter.New("simulator"), bud, "http://bidder:8081"), bud
}

// The indexed engine must choose exactly what the linear oracle chooses.
func TestEngineMatchesLinear(t *testing.T) {
	for _, n := range []int{1, 7, 64, 65, 300, 5000} {
		snap := genSnapshot(n, int64(n))
		eng, bud := compiled(t, snap, 1<<40)
		// Starve a few campaigns so the budget check is exercised.
		for i := 0; i < n; i += 11 {
			bud.Slot(snap.Campaigns[i].ID).Store(0)
		}
		imps := genImps(4000, int64(n)+1)
		for hour := 0; hour < 168; hour += 13 {
			now := time.Date(2026, 10, 25, 0, 0, 0, 0, london).Add(time.Duration(hour) * time.Hour)
			for i, imp := range imps {
				want := Match(eng.Snap, imp, now.In(london), bud)
				got := eng.Match(imp, HourIndex(now))
				if want.Campaign != got.Campaign || want.Creative != got.Creative || want.Price != got.Price || want.SpendMicros != got.SpendMicros {
					t.Fatalf("n=%d hour=%d imp %d %+v: linear %v engine %v", n, hour, i, imp, id(want), id(got))
				}
			}
		}
	}
}

func id(r Result) any {
	if r.Campaign == nil {
		return "nobid"
	}
	return r.Campaign.ID
}

func TestEngineBidJSON(t *testing.T) {
	eng, _ := compiled(t, sampleSnap(), 1_000_000)
	imp := adapter.CanonicalImp{VenueTypes: []string{"roadside.billboard"}, Lat: 51.5074, Lon: -0.1278, Country: "GB", W: 1920, H: 1080, Floor: 2, Qty: 14.2}
	res := eng.Match(imp, 32)
	if res.Campaign == nil {
		t.Fatal("expected bid")
	}
	reqID := "req \"1\"/é&x"
	out := eng.AppendBid(nil, reqID, "1", res)
	var resp struct {
		ID      string `json:"id"`
		Cur     string `json:"cur"`
		SeatBid []struct {
			Seat string `json:"seat"`
			Bid  []struct {
				ID, ImpID, AdM, NURL, BURL, CrID, CID string
				Price                                 float64
				W, H                                  int
				Adomain                               []string
			} `json:"bid"`
		} `json:"seatbid"`
	}
	if err := json.Unmarshal(out, &resp); err != nil {
		t.Fatalf("invalid JSON %s: %v", out, err)
	}
	b := resp.SeatBid[0].Bid[0]
	if resp.ID != reqID || resp.Cur != "GBP" || resp.SeatBid[0].Seat != "seat-1" || b.ID != reqID+"-1" || b.ImpID != "1" {
		t.Fatalf("envelope %s", out)
	}
	if b.CrID != "9" || b.CID != "1" || b.W != 1920 || b.H != 1080 || b.AdM != "http://cdn/a.png" || math.Abs(b.Price-res.Price) > 1e-4 {
		t.Fatalf("bid %s", out)
	}
	wantN := "http://bidder:8081/nurl?id=req%20%221%22%2F%C3%A9%26x&price=${AUCTION_PRICE}"
	if b.NURL != wantN || !strings.HasPrefix(b.BURL, "http://bidder:8081/burl?id=") {
		t.Fatalf("nurl %q burl %q", b.NURL, b.BURL)
	}
}

func TestEngineSpendStopsAtZero(t *testing.T) {
	eng, bud := compiled(t, sampleSnap(), 100_000)
	imp := adapter.CanonicalImp{VenueTypes: []string{"roadside"}, Lat: 51.5, Lon: -0.1, Country: "GB", W: 1920, H: 1080, Floor: 5, Qty: 10}
	bids := 0
	for i := 0; i < 10; i++ {
		res := eng.Match(imp, 32)
		if res.Campaign == nil {
			break
		}
		eng.Spend(res)
		bids++
	}
	// 5.525 CPM * 10 qty = 55,250 micros per bid: the second bid takes the
	// counter below zero and the third is refused.
	if bids != 2 {
		t.Fatalf("bids=%d", bids)
	}
	if rem, _ := bud.Remaining(1); rem > 0 {
		t.Fatalf("remaining %d", rem)
	}
}

func TestEngineNilAndNotReady(t *testing.T) {
	var e *Engine
	if r := e.Match(adapter.CanonicalImp{}, 0); r.Campaign != nil || r.NoBidReason != 2 {
		t.Fatal("nil engine must no-bid")
	}
	h := &snapshot.Holder{}
	h.Store(sampleSnap())
	eng := Compile(h.Load(), adapter.New("simulator"), budget.New(), "")
	imp := adapter.CanonicalImp{VenueTypes: []string{"roadside"}, Lat: 51.5, Lon: -0.1, Country: "GB", W: 1920, H: 1080}
	if r := eng.Match(imp, 32); r.Campaign != nil {
		t.Fatal("budget not ready must no-bid")
	}
}

func TestHourIndexLondon(t *testing.T) {
	cases := []struct {
		t    time.Time
		want int
	}{
		{time.Date(2026, 10, 28, 9, 30, 0, 0, time.UTC), 3*24 + 9},  // Wed, GMT
		{time.Date(2026, 7, 5, 23, 15, 0, 0, time.UTC), 1*24 + 0},   // Sun 23:15 UTC = Mon 00:15 BST
		{time.Date(2026, 10, 25, 0, 59, 59, 0, time.UTC), 0*24 + 1}, // Sun 01:59 BST
		{time.Date(2026, 10, 25, 1, 0, 0, 0, time.UTC), 0*24 + 1},   // Sun 01:00 GMT (repeat hour)
		{time.Date(2026, 10, 25, 2, 0, 0, 0, time.UTC), 0*24 + 2},
	}
	for _, c := range cases {
		if got := HourIndex(c.t); got != c.want {
			t.Fatalf("%v: got %d want %d", c.t, got, c.want)
		}
		// Second call is served from the cache.
		if got := HourIndex(c.t.Add(time.Second)); got != c.want {
			t.Fatalf("%v cached: got %d want %d", c.t, got, c.want)
		}
	}
}

func benchEngine(b *testing.B, n int) {
	snap := genSnapshot(n, 7)
	eng, _ := compiled(b, snap, 1<<40)
	imps := genImps(1024, 9)
	hour := HourIndex(time.Date(2026, 10, 28, 9, 0, 0, 0, time.UTC))
	b.ReportAllocs()
	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		_ = eng.Match(imps[i&1023], hour)
	}
}

func BenchmarkEngine100(b *testing.B)   { benchEngine(b, 100) }
func BenchmarkEngine1000(b *testing.B)  { benchEngine(b, 1000) }
func BenchmarkEngine10000(b *testing.B) { benchEngine(b, 10000) }

func BenchmarkAppendBid(b *testing.B) {
	eng, _ := compiled(b, sampleSnap(), 1<<40)
	imp := adapter.CanonicalImp{VenueTypes: []string{"roadside"}, Lat: 51.5, Lon: -0.1, Country: "GB", W: 1920, H: 1080, Floor: 2, Qty: 10}
	res := eng.Match(imp, 32)
	buf := make([]byte, 0, 1024)
	b.ReportAllocs()
	for i := 0; i < b.N; i++ {
		buf = eng.AppendBid(buf[:0], "sim-123456", "1", res)
	}
}
