package logasync

import (
	"bytes"
	"encoding/json"
	"net/http"
	"strings"
	"sync/atomic"
	"time"
)

type Event struct {
	EventType     string  `json:"event_type"`
	EventTime     string  `json:"event_time"`
	AdvertiserID  uint32  `json:"advertiser_id"`
	CampaignID    uint32  `json:"campaign_id"`
	SSP           string  `json:"ssp"`
	Country       string  `json:"country"`
	VenueType     string  `json:"venue_type"`
	H3            uint64  `json:"h3"`
	CreativeID    uint32  `json:"creative_id"`
	BidRequestID  string  `json:"bid_request_id"`
	ImpID         string  `json:"imp_id"`
	Currency      string  `json:"currency"`
	PriceCPM      float64 `json:"price_cpm"`
	QtyMultiplier float64 `json:"qty_multiplier"`
	BillableImps  float64 `json:"billable_imps"`
	SpendMicros   int64   `json:"spend_micros"`
	SnapshotID    uint64  `json:"snapshot_id"`
}

type Writer struct {
	ch             chan Event
	ingest         string
	client         *http.Client
	dropped        atomic.Uint64
	droppedBilling atomic.Uint64
}

func New(ingest string) *Writer {
	w := &Writer{
		ch:     make(chan Event, 8192),
		ingest: strings.TrimSpace(ingest),
		client: &http.Client{
			Timeout: 400 * time.Millisecond,
			Transport: &http.Transport{
				MaxIdleConns:        32,
				MaxIdleConnsPerHost: 32,
				IdleConnTimeout:     30 * time.Second,
			},
		},
	}
	go w.loop()
	return w
}

func (w *Writer) Log(e Event) {
	if e.EventTime == "" {
		e.EventTime = time.Now().UTC().Format(time.RFC3339Nano)
	}
	select {
	case w.ch <- e:
	default:
		w.dropped.Add(1)
		if e.EventType == "billing" {
			w.droppedBilling.Add(1)
		}
	}
}

// Dropped returns how many events were dropped because the async queue was full.
func (w *Writer) Dropped() (total, billing uint64) {
	return w.dropped.Load(), w.droppedBilling.Load()
}

func (w *Writer) loop() {
	for e := range w.ch {
		if w.ingest == "" {
			continue
		}
		payload, err := json.Marshal(e)
		if err != nil {
			continue
		}
		req, err := http.NewRequest(http.MethodPost, w.ingest, bytes.NewReader(payload))
		if err != nil {
			continue
		}
		req.Header.Set("Content-Type", "application/json")
		resp, err := w.client.Do(req)
		if err != nil {
			continue
		}
		resp.Body.Close()
	}
}
