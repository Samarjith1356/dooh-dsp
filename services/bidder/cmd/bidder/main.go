package main

import (
	"context"
	"io"
	"log"
	"net/http"
	"os"
	"strconv"
	"strings"
	"sync"
	"time"

	"github.com/dooh-dsp/bidder/internal/adapter"
	"github.com/dooh-dsp/bidder/internal/budget"
	"github.com/dooh-dsp/bidder/internal/lat"
	"github.com/dooh-dsp/bidder/internal/logasync"
	"github.com/dooh-dsp/bidder/internal/matcher"
	"github.com/dooh-dsp/bidder/internal/notice"
	"github.com/dooh-dsp/bidder/internal/openrtb"
	"github.com/dooh-dsp/bidder/internal/redisc"
	"github.com/dooh-dsp/bidder/internal/snapshot"
)

var (
	london   *time.Location
	bodyPool = sync.Pool{New: func() any { b := make([]byte, 0, 4096); return &b }}
	respPool = sync.Pool{New: func() any { b := make([]byte, 0, 1024); return &b }}
	reqPool  = sync.Pool{New: func() any { return &openrtb.BidRequest{} }}
)

func init() {
	loc, err := time.LoadLocation("Europe/London")
	if err != nil {
		loc = time.UTC
	}
	london = loc
}

func main() {
	listen := env("BIDDER_LISTEN", ":8081")
	ad := adapter.New(env("SSP_ADAPTER", "simulator"))
	hold := &snapshot.Holder{}
	bud := budget.New()
	ingest := env("INGEST_URL", "http://localhost:8090/events")
	logs := logasync.New(ingest)
	rdb := redisc.ParseURL(env("REDIS_URL", "redis://localhost:6379/0"))
	noticeBase := env("NOTICE_BASE_URL", "http://bidder:8081")
	noticeKey := env("NOTICE_SIGNING_KEY", "")

	ctx := context.Background()
	go pollSnapshot(ctx, rdb, hold, bud)
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
		n, avg, max, last := lat.Snapshot()
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(
			`{"ok":true,"adapter":"` + ad.Name() +
				`","bids":` + strconv.FormatUint(n, 10) +
				`,"avg_decision_us":` + strconv.FormatUint(avg, 10) +
				`,"max_decision_us":` + strconv.FormatUint(max, 10) +
				`,"last_decision_us":` + strconv.FormatUint(last, 10) + `}`,
		))
	})
	mux.HandleFunc("/openrtb/v2/bid", func(w http.ResponseWriter, r *http.Request) {
		handleBid(w, r, ad, hold, bud, logs, noticeBase, noticeKey)
	})
	mux.HandleFunc("/nurl", func(w http.ResponseWriter, r *http.Request) {
		handleNotice(w, r, "win", noticeKey, logs)
	})
	mux.HandleFunc("/burl", func(w http.ResponseWriter, r *http.Request) {
		handleNotice(w, r, "billing", noticeKey, logs)
	})
	mux.HandleFunc("/lurl", func(w http.ResponseWriter, r *http.Request) {
		handleNotice(w, r, "loss", noticeKey, logs)
	})

	log.Printf("bidder adapter=%s listen=%s notice_base=%s (decision budget <1ms)", ad.Name(), listen, noticeBase)
	srv := &http.Server{
		Addr:              listen,
		Handler:           mux,
		ReadHeaderTimeout: 200 * time.Millisecond,
		ReadTimeout:       800 * time.Millisecond,
		WriteTimeout:      800 * time.Millisecond,
		IdleTimeout:       30 * time.Second,
	}
	if err := srv.ListenAndServe(); err != nil {
		log.Fatal(err)
	}
}

func handleBid(w http.ResponseWriter, r *http.Request, ad adapter.SspAdapter, hold *snapshot.Holder, bud *budget.Cache, logs *logasync.Writer, noticeBase, noticeKey string) {
	start := time.Now()
	defer r.Body.Close()

	bufp := bodyPool.Get().(*[]byte)
	buf := (*bufp)[:0]
	body, err := readAll(r.Body, buf)
	if err != nil {
		bodyPool.Put(bufp)
		http.Error(w, "bad request", http.StatusBadRequest)
		return
	}

	req := reqPool.Get().(*openrtb.BidRequest)
	*req = openrtb.BidRequest{}
	err = openrtb.UnmarshalBid(body, req)
	*bufp = body
	bodyPool.Put(bufp)
	if err != nil {
		reqPool.Put(req)
		http.Error(w, "invalid json", http.StatusBadRequest)
		return
	}

	if !openrtb.IsDOOH(req) {
		writeNoBid(w, req.ID, 2, start)
		reqPool.Put(req)
		return
	}

	imp := ad.Normalize(req)
	snap := hold.Load()
	res := matcher.Match(snap, imp, time.Now().In(london), bud)

	var notices matcher.NoticeURLs
	impID := "1"
	if len(req.Imp) > 0 && req.Imp[0].ID != "" {
		impID = req.Imp[0].ID
	}
	if res.Campaign != nil {
		cur := res.Campaign.Currency
		if cur == "" {
			cur = "GBP"
		}
		np := notice.Params{
			BidRequestID: req.ID,
			ImpID:        impID,
			AdvertiserID: res.Campaign.AdvertiserID,
			CampaignID:   res.Campaign.ID,
			CreativeID:   res.Creative.ID,
			Multiplier:   res.Qty,
			BidCPM:       res.Price,
			Currency:     cur,
		}
		nurl, burl, lurl := notice.BuildURLs(noticeBase, noticeKey, np)
		notices = matcher.NoticeURLs{NURL: nurl, BURL: burl, LURL: lurl}
	}
	resp := matcher.BuildResponse(req, ad, res, notices)
	writeResp(w, resp, start)

	evt := logasync.Event{
		EventType:    "nobid",
		SSP:          ad.Name(),
		Country:      imp.Country,
		BidRequestID: req.ID,
		ImpID:        impID,
	}
	if len(imp.VenueTypes) > 0 {
		evt.VenueType = imp.VenueTypes[0]
	}
	if snap != nil {
		evt.SnapshotID = snap.SnapshotID
	}
	evt.H3 = snapshot.GridCell(imp.Lat, imp.Lon)
	if res.Campaign != nil {
		evt.EventType = "bid"
		evt.AdvertiserID = res.Campaign.AdvertiserID
		evt.CampaignID = res.Campaign.ID
		evt.CreativeID = res.Creative.ID
		evt.PriceCPM = res.Price
		evt.QtyMultiplier = res.Qty
		evt.Currency = res.Campaign.Currency
		if evt.Currency == "" {
			evt.Currency = "GBP"
		}
		// Bids never book spend; billing notices do.
		evt.BillableImps = 0
		evt.SpendMicros = 0
	}
	logs.Log(evt)
	reqPool.Put(req)
}

func handleNotice(w http.ResponseWriter, r *http.Request, kind string, noticeKey string, logs *logasync.Writer) {
	q := r.URL.Query()
	params, price, err := notice.ParseAndVerify(noticeKey, q)
	if err != nil {
		priceCPM := price
		if priceCPM == 0 {
			if p, perr := strconv.ParseFloat(q.Get("p"), 64); perr == nil {
				priceCPM = p
			}
		}
		logs.Log(logasync.Event{
			EventType:     "notice_rejected",
			BidRequestID:  params.BidRequestID,
			ImpID:         params.ImpID,
			AdvertiserID:  params.AdvertiserID,
			CampaignID:    params.CampaignID,
			CreativeID:    params.CreativeID,
			QtyMultiplier: params.Multiplier,
			PriceCPM:      priceCPM,
			Currency:      params.Currency,
			SpendMicros:   0,
			BillableImps:  0,
		})
		w.WriteHeader(http.StatusNoContent)
		return
	}

	evt := logasync.Event{
		EventType:     kind,
		BidRequestID:  params.BidRequestID,
		ImpID:         params.ImpID,
		AdvertiserID:  params.AdvertiserID,
		CampaignID:    params.CampaignID,
		CreativeID:    params.CreativeID,
		QtyMultiplier: params.Multiplier,
		Currency:      params.Currency,
		PriceCPM:      price,
		SpendMicros:   0,
		BillableImps:  0,
	}
	if kind == "billing" {
		evt.SpendMicros = notice.SpendMicros(price, params.Multiplier)
		evt.BillableImps = params.Multiplier
	}
	if kind == "loss" {
		evt.PriceCPM = 0
	}
	logs.Log(evt)
	w.WriteHeader(http.StatusNoContent)
}

func writeNoBid(w http.ResponseWriter, id string, nbr int, start time.Time) {
	writeResp(w, &openrtb.BidResponse{ID: id, Nbr: nbr}, start)
}

func writeResp(w http.ResponseWriter, resp *openrtb.BidResponse, start time.Time) {
	ns := time.Since(start).Nanoseconds()
	lat.Observe(ns)
	w.Header().Set("Content-Type", "application/json")
	w.Header().Set("X-DSP-Decision-Us", strconv.FormatInt(ns/1000, 10))
	bufp := respPool.Get().(*[]byte)
	out := matcher.AppendResponse((*bufp)[:0], resp)
	_, _ = w.Write(out)
	*bufp = out
	respPool.Put(bufp)
}

func readAll(r io.Reader, buf []byte) ([]byte, error) {
	const max = 1 << 20
	tmp := make([]byte, 4096)
	for {
		n, err := r.Read(tmp)
		if n > 0 {
			if len(buf)+n > max {
				return nil, io.ErrUnexpectedEOF
			}
			buf = append(buf, tmp[:n]...)
		}
		if err == io.EOF {
			return buf, nil
		}
		if err != nil {
			return nil, err
		}
	}
}

func pollSnapshot(ctx context.Context, r *redisc.Client, hold *snapshot.Holder, bud *budget.Cache) {
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
			cctx, cancel = context.WithTimeout(ctx, 400*time.Millisecond)
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
			hold.Store(snap)
			ids := make([]uint32, 0, len(snap.Campaigns))
			for i := range snap.Campaigns {
				ids = append(ids, snap.Campaigns[i].ID)
			}
			bud.Ensure(ids, 50_000_000)
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
