package main

import (
	"context"
	"errors"
	"io"
	"log"
	"net/http"
	"os"
	"runtime/debug"
	"strconv"
	"strings"
	"sync"
	"sync/atomic"
	"time"

	"github.com/dooh-dsp/bidder/internal/adapter"
	"github.com/dooh-dsp/bidder/internal/budget"
	"github.com/dooh-dsp/bidder/internal/lat"
	"github.com/dooh-dsp/bidder/internal/logasync"
	"github.com/dooh-dsp/bidder/internal/matcher"
	"github.com/dooh-dsp/bidder/internal/openrtb"
	"github.com/dooh-dsp/bidder/internal/redisc"
	"github.com/dooh-dsp/bidder/internal/snapshot"
)

const (
	maxBody     = 1 << 20
	keepBodyCap = 64 << 10 // larger buffers are not returned to the pool
)

var (
	bodyPool = sync.Pool{New: func() any { b := make([]byte, 0, 4096); return &b }}
	respPool = sync.Pool{New: func() any { b := make([]byte, 0, 1024); return &b }}
	reqPool  = sync.Pool{New: func() any { return &openrtb.BidRequest{} }}

	errTooLarge = errors.New("body too large")

	// Pre-canonicalised header values shared by every response.
	jsonCT = []string{"application/json"}
)

// bidder is the bid-path state. Everything it reads per request is either
// immutable (the compiled Engine) or atomic (budget counters).
type bidder struct {
	ad         adapter.SspAdapter
	bud        *budget.Cache
	logs       *logasync.Writer
	noticeBase string
	eng        atomic.Pointer[matcher.Engine]
}

func newBidder(ad adapter.SspAdapter, bud *budget.Cache, logs *logasync.Writer, noticeBase string) *bidder {
	return &bidder{ad: ad, bud: bud, logs: logs, noticeBase: strings.TrimRight(noticeBase, "/")}
}

// load compiles a snapshot and swaps it in atomically.
func (b *bidder) load(snap *snapshot.RulesSnapshot) {
	b.eng.Store(matcher.Compile(snap, b.ad, b.bud, b.noticeBase))
}

func main() {
	tuneGC()
	listen := env("BIDDER_LISTEN", ":8081")
	ad := adapter.New(env("SSP_ADAPTER", "simulator"))
	hold := &snapshot.Holder{}
	bud := budget.New()
	logs := logasync.New(env("INGEST_URL", "http://localhost:8090/events"))
	b := newBidder(ad, bud, logs, env("NOTICE_BASE_URL", "http://bidder:8081"))
	rdb := redisc.ParseURL(env("REDIS_URL", "redis://localhost:6379/0"))

	ctx := context.Background()
	go pollSnapshot(ctx, rdb, hold, b)
	go budget.RefreshLoop(ctx, rdb, func() []uint32 {
		s := hold.Load()
		if s == nil {
			return nil
		}
		ids := make([]uint32, 0, len(s.Campaigns))
		for i := range s.Campaigns {
			ids = append(ids, s.Campaigns[i].ID)
		}
		return ids
	}, bud)

	mux := http.NewServeMux()
	mux.HandleFunc("/health", func(w http.ResponseWriter, _ *http.Request) {
		d, c := lat.Decision.Stats(), lat.Compute.Stats()
		u := func(v uint64) string { return strconv.FormatUint(v, 10) }
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(
			`{"ok":true,"adapter":"` + ad.Name() +
				`","bids":` + u(d.Count) +
				`,"avg_decision_us":` + u(d.AvgUs) +
				`,"max_decision_us":` + u(d.MaxUs) +
				`,"last_decision_us":` + u(d.LastUs) +
				`,"window_s":120` +
				`,"p50_decision_us":` + u(d.P50) +
				`,"p99_decision_us":` + u(d.P99) +
				`,"p999_decision_us":` + u(d.P999) +
				`,"window_max_decision_us":` + u(d.WindowMaxUs) +
				`,"p50_compute_us":` + u(c.P50) +
				`,"p99_compute_us":` + u(c.P99) +
				`,"p999_compute_us":` + u(c.P999) +
				`,"window_max_compute_us":` + u(c.WindowMaxUs) +
				`,"log_dropped":` + u(logs.Dropped()) +
				`,"log_failed":` + u(logs.Failed()) + `}`,
		))
	})
	mux.HandleFunc("/openrtb/v2/bid", b.handleBid)
	mux.HandleFunc("/nurl", func(w http.ResponseWriter, r *http.Request) { handleNotice(w, r, "win", logs) })
	mux.HandleFunc("/burl", func(w http.ResponseWriter, r *http.Request) { handleNotice(w, r, "pop", logs) })

	log.Printf("bidder adapter=%s listen=%s (decision budget <1ms)", ad.Name(), listen)
	srv := &http.Server{
		Addr:              listen,
		Handler:           mux,
		ReadHeaderTimeout: 200 * time.Millisecond,
		ReadTimeout:       800 * time.Millisecond,
		WriteTimeout:      800 * time.Millisecond,
		IdleTimeout:       90 * time.Second,
		MaxHeaderBytes:    32 << 10,
	}
	if err := srv.ListenAndServe(); err != nil {
		log.Fatal(err)
	}
}

// tuneGC sets bidder-friendly defaults unless GOGC / GOMEMLIMIT are set.
// The hot path barely allocates, so a high GOGC makes GC cycles rare; the
// soft memory limit keeps the heap bounded if traffic spikes.
func tuneGC() {
	if os.Getenv("GOGC") == "" {
		debug.SetGCPercent(400)
	}
	if os.Getenv("GOMEMLIMIT") == "" {
		debug.SetMemoryLimit(768 << 20)
	}
}

func (b *bidder) handleBid(w http.ResponseWriter, r *http.Request) {
	start := time.Now()
	defer r.Body.Close()

	bufp := bodyPool.Get().(*[]byte)
	body, err := readBody(r, (*bufp)[:0])
	defer func() {
		if cap(body) <= keepBodyCap {
			*bufp = body[:0]
			bodyPool.Put(bufp)
		}
	}()
	if err != nil {
		http.Error(w, "bad request", http.StatusBadRequest)
		return
	}

	computeStart := time.Now()
	req := reqPool.Get().(*openrtb.BidRequest)
	defer reqPool.Put(req)
	if err := openrtb.UnmarshalBid(body, req); err != nil {
		http.Error(w, "invalid json", http.StatusBadRequest)
		return
	}

	outp := respPool.Get().(*[]byte)
	defer respPool.Put(outp)

	if !openrtb.IsDOOH(req) {
		*outp = matcher.AppendNoBid((*outp)[:0], req.ID, 2)
		writeResp(w, *outp, start, computeStart)
		return
	}

	imp := b.ad.Normalize(req)
	eng := b.eng.Load()
	res := eng.Match(imp, matcher.HourIndex(computeStart))
	if res.Campaign != nil {
		eng.Spend(res)
		*outp = eng.AppendBid((*outp)[:0], req.ID, imp.ImpID, res)
	} else {
		*outp = matcher.AppendNoBid((*outp)[:0], req.ID, res.NoBidReason)
	}
	writeResp(w, *outp, start, computeStart)

	evt := logasync.Event{
		EventType:    "nobid",
		SSP:          b.ad.Name(),
		Country:      imp.Country,
		BidRequestID: req.ID,
		At:           computeStart.UnixNano(),
		H3:           snapshot.GridCell(imp.Lat, imp.Lon),
	}
	if len(imp.VenueTypes) > 0 {
		evt.VenueType = imp.VenueTypes[0]
	}
	if eng != nil {
		evt.SnapshotID = eng.Snap.SnapshotID
	}
	if res.Campaign != nil {
		evt.EventType = "bid"
		evt.AdvertiserID = res.Campaign.AdvertiserID
		evt.CampaignID = res.Campaign.ID
		evt.CreativeID = res.Creative.ID
		evt.PriceCPM = res.Price
		evt.QtyMultiplier = res.Qty
		evt.BillableImps = res.Qty
		evt.SpendMicros = res.SpendMicros
	}
	b.logs.Log(evt)
}

// handleNotice logs win (nurl) and proof-of-play (burl) notices. The SSP
// substitutes ${AUCTION_PRICE} with the clearing CPM.
func handleNotice(w http.ResponseWriter, r *http.Request, kind string, logs *logasync.Writer) {
	q := r.URL.Query()
	e := logasync.Event{EventType: kind, BidRequestID: q.Get("id")}
	if p, err := strconv.ParseFloat(q.Get("price"), 64); err == nil {
		e.PriceCPM = p
	}
	logs.Log(e)
	w.WriteHeader(http.StatusNoContent)
}

func writeResp(w http.ResponseWriter, out []byte, start, computeStart time.Time) {
	end := time.Now()
	ns := end.Sub(start).Nanoseconds()
	lat.Decision.Observe(ns)
	lat.Compute.Observe(end.Sub(computeStart).Nanoseconds())
	h := w.Header()
	h["Content-Type"] = jsonCT
	h["X-Dsp-Decision-Us"] = []string{strconv.FormatInt(ns/1000, 10)}
	_, _ = w.Write(out)
}

// readBody reads the request body into buf, reusing its capacity. With a
// Content-Length it is one exact read; otherwise it grows in place.
func readBody(r *http.Request, buf []byte) ([]byte, error) {
	if n := r.ContentLength; n > 0 {
		if n > maxBody {
			return buf, errTooLarge
		}
		if int64(cap(buf)) < n {
			buf = make([]byte, 0, n)
		}
		buf = buf[:n]
		_, err := io.ReadFull(r.Body, buf)
		return buf, err
	}
	for {
		if len(buf) == cap(buf) {
			if len(buf) >= maxBody {
				return buf, errTooLarge
			}
			buf = append(buf, 0)[:len(buf)]
		}
		n, err := r.Body.Read(buf[len(buf):cap(buf)])
		buf = buf[:len(buf)+n]
		if err == io.EOF {
			return buf, nil
		}
		if err != nil {
			return buf, err
		}
	}
}

func pollSnapshot(ctx context.Context, r *redisc.Client, hold *snapshot.Holder, b *bidder) {
	tick := time.NewTicker(500 * time.Millisecond)
	defer tick.Stop()
	var last string
	for {
		select {
		case <-ctx.Done():
			return
		case <-tick.C:
			cctx, cancel := context.WithTimeout(ctx, 200*time.Millisecond)
			sid, err := r.Get(cctx, "rules:current")
			cancel()
			if err != nil || sid == "" || sid == last {
				continue
			}
			cctx, cancel = context.WithTimeout(ctx, 2*time.Second)
			raw, err := r.Get(cctx, "rules:snapshot:"+sid)
			cancel()
			if err != nil || raw == "" {
				continue
			}
			snap, err := snapshot.Parse([]byte(raw))
			if err != nil {
				log.Printf("snapshot parse: %s", err)
				continue
			}
			ids := make([]uint32, 0, len(snap.Campaigns))
			for i := range snap.Campaigns {
				ids = append(ids, snap.Campaigns[i].ID)
			}
			b.bud.Ensure(ids, 50_000_000)
			hold.Store(snap)
			b.load(snap)
			last = sid
			log.Printf("loaded snapshot %s campaigns=%d", sid, len(snap.Campaigns))
		}
	}
}

func env(k, d string) string {
	if v := strings.TrimSpace(os.Getenv(k)); v != "" {
		return v
	}
	return d
}
