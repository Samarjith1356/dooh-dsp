package matcher

import (
	"encoding/base64"
	"math/rand"
	"testing"
	"time"

	"github.com/dooh-dsp/bidder/internal/adapter"
	"github.com/dooh-dsp/bidder/internal/budget"
	"github.com/dooh-dsp/bidder/internal/snapshot"
)

var (
	genVenues = []string{"roadside", "roadside.billboard", "transit", "transit.rail", "transit.rail.underground", "transit.bus", "urban.street", "retail.mall", "airport"}
	genSizes  = [][2]int{{1920, 1080}, {1080, 1920}, {1280, 720}, {3840, 1080}}
	genCities = [][2]float64{{51.5074, -0.1278}, {53.3498, -6.2603}, {53.4808, -2.2426}, {52.4862, -1.8904}, {55.9533, -3.1883}, {51.8985, -8.4756}}
)

// genSnapshot builds n synthetic UK/IE campaigns. Deterministic for a seed.
func genSnapshot(n int, seed int64) *snapshot.RulesSnapshot {
	r := rand.New(rand.NewSource(seed))
	s := &snapshot.RulesSnapshot{SnapshotID: 1}
	for i := 0; i < n; i++ {
		city := genCities[r.Intn(len(genCities))]
		span := 0.05 + r.Float64()*0.6
		c := snapshot.Campaign{
			ID: uint32(i + 1), AdvertiserID: uint32(r.Intn(50) + 1), Seat: "seat", Priority: r.Intn(4),
			BidCPMMicros: int64(1_000_000 + r.Intn(9_000_000)),
			Shading:      snapshot.Shading{ShadeFactor: 0.85},
			MinLat:       city[0] - span, MaxLat: city[0] + span,
			MinLon: city[1] - span, MaxLon: city[1] + span,
			Currency: "GBP",
		}
		if r.Intn(4) > 0 {
			c.VenueTypes = []string{genVenues[r.Intn(len(genVenues))]}
		}
		switch r.Intn(3) {
		case 0:
			c.Countries = []string{"GB"}
		case 1:
			c.Countries = []string{"IE"}
		}
		if r.Intn(2) == 0 {
			bits := make([]byte, 21)
			for h := 0; h < 168; h++ {
				if hr := h % 24; hr >= 6 && hr <= 22 && r.Intn(5) > 0 {
					bits[h/8] |= 1 << uint(h%8)
				}
			}
			c.DaypartBits = base64.StdEncoding.EncodeToString(bits)
		}
		for k := 0; k < 1+r.Intn(2); k++ {
			sz := genSizes[r.Intn(len(genSizes))]
			c.Creatives = append(c.Creatives, snapshot.CreativeRef{ID: uint32(i*10 + k), Width: sz[0], Height: sz[1], CDNURL: "http://cdn/x.png"})
		}
		s.Campaigns = append(s.Campaigns, c)
	}
	return s
}

func genImps(n int, seed int64) []adapter.CanonicalImp {
	r := rand.New(rand.NewSource(seed))
	out := make([]adapter.CanonicalImp, n)
	countries := []string{"GB", "IE", "GBR", "IRL", "", "UK"}
	for i := range out {
		city := genCities[r.Intn(len(genCities))]
		sz := genSizes[r.Intn(len(genSizes))]
		imp := adapter.CanonicalImp{
			Lat: city[0] + (r.Float64()-0.5)*1.2, Lon: city[1] + (r.Float64()-0.5)*1.2,
			Country: countries[r.Intn(len(countries))],
			W:       sz[0], H: sz[1], Floor: r.Float64() * 6, Qty: 1 + r.Float64()*20,
		}
		if r.Intn(10) == 0 {
			imp.W, imp.H = 0, 0
		}
		v := genVenues[r.Intn(len(genVenues))]
		imp.VenueTypes = []string{v}
		out[i] = imp
	}
	return out
}

func benchLinear(b *testing.B, n int) {
	snap := genSnapshot(n, 7)
	h := &snapshot.Holder{}
	h.Store(snap)
	bud := budget.New()
	ids := make([]uint32, 0, n)
	for _, c := range snap.Campaigns {
		ids = append(ids, c.ID)
	}
	bud.Ensure(ids, 1<<40)
	imps := genImps(1024, 9)
	now := time.Date(2026, 10, 28, 9, 0, 0, 0, time.UTC)
	b.ReportAllocs()
	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		_ = Match(h.Load(), imps[i&1023], now, bud)
	}
}

func BenchmarkMatchLinear100(b *testing.B)   { benchLinear(b, 100) }
func BenchmarkMatchLinear1000(b *testing.B)  { benchLinear(b, 1000) }
func BenchmarkMatchLinear10000(b *testing.B) { benchLinear(b, 10000) }
