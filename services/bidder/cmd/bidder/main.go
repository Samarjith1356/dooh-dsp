package main

import (
	"context"
	"encoding/json"
	"io"
	"log"
	"net/http"
	"os"
	"strings"
	"time"

	"github.com/dooh-dsp/bidder/internal/adapter"
	"github.com/dooh-dsp/bidder/internal/budget"
	"github.com/dooh-dsp/bidder/internal/logasync"
	"github.com/dooh-dsp/bidder/internal/matcher"
	"github.com/dooh-dsp/bidder/internal/openrtb"
	"github.com/dooh-dsp/bidder/internal/redisc"
	"github.com/dooh-dsp/bidder/internal/snapshot"
)

func main() {
	listen := env("BIDDER_LISTEN", ":8081")
	ad := adapter.New(env("SSP_ADAPTER", "simulator"))
	hold := &snapshot.Holder{}
	bud := budget.New()
	logs := logasync.New(env("KAFKA_BROKERS", "localhost:19092"))
	ingest := env("INGEST_URL", "http://localhost:8090/events")
	rdb := redisc.ParseURL(env("REDIS_URL", "redis://localhost:6379/0"))

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
		w.Write([]byte(`{"ok":true,"adapter":"` + ad.Name() + `"}`))
	})
	mux.HandleFunc("/openrtb/v2/bid", func(w http.ResponseWriter, r *http.Request) {
		handleBid(w, r, ad, hold, bud, logs, ingest)
	})
	mux.HandleFunc("/nurl", func(w http.ResponseWriter, r *http.Request) {
		handleNotice(w, r, "win", logs, ingest)
	})
	mux.HandleFunc("/burl", func(w http.ResponseWriter, r *http.Request) {
		handleNotice(w, r, "pop", logs, ingest)
	})

	log.Printf("bidder adapter=%s listen=%s (no postgres, no llm on this path)", ad.Name(), listen)
	if err := http.ListenAndServe(listen, mux); err != nil {
		log.Fatal(err)
	}
}

func handleBid(w http.ResponseWriter, r *http.Request, ad adapter.SspAdapter, hold *snapshot.Holder, bud *budget.Cache, logs *logasync.Writer, ingest string) {
	start := time.Now()
	defer r.Body.Close()
	body, err := io.ReadAll(io.LimitReader(r.Body, 1<<20))
	if err != nil {
		http.Error(w, "bad request", http.StatusBadRequest)
		return
	}
	var req openrtb.BidRequest
	if err := json.Unmarshal(body, &req); err != nil {
		http.Error(w, "invalid json", http.StatusBadRequest)
		return
	}
	if !openrtb.IsDOOH(&req) {
		writeJSON(w, openrtb.BidResponse{ID: req.ID, Nbr: 2})
		return
	}
	if req.TMax > 0 && time.Since(start) > time.Duration(req.TMax)*time.Millisecond {
		writeJSON(w, openrtb.BidResponse{ID: req.ID, Nbr: 2})
		return
	}
	imp := ad.Normalize(&req)
	snap := hold.Load()
	res := matcher.Match(snap, imp, time.Now().In(time.FixedZone("Europe/London", 0)), bud)
	resp := matcher.BuildResponse(&req, imp, ad, res)
	writeJSON(w, resp)

	evt := logasync.Event{
		EventType:    "nobid",
		SSP:          ad.Name(),
		Country:      imp.Country,
		BidRequestID: req.ID,
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
		evt.BillableImps = res.Qty
		evt.SpendMicros = res.SpendMicros
	}
	logs.Log(evt)
	go logs.PostHTTP(ingest, evt)
}

func handleNotice(w http.ResponseWriter, r *http.Request, kind string, logs *logasync.Writer, ingest string) {
	evt := logasync.Event{EventType: kind, BidRequestID: r.URL.Query().Get("id")}
	logs.Log(evt)
	go logs.PostHTTP(ingest, evt)
	w.WriteHeader(http.StatusNoContent)
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

func writeJSON(w http.ResponseWriter, v any) {
	w.Header().Set("Content-Type", "application/json")
	enc := json.NewEncoder(w)
	_ = enc.Encode(v)
}

func env(k, d string) string {
	if v := strings.TrimSpace(os.Getenv(k)); v != "" {
		return v
	}
	return d
}
