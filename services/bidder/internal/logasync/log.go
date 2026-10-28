package logasync

import (
	"bytes"
	"net/http"
	"strconv"
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
	PriceCPM      float64 `json:"price_cpm"`
	QtyMultiplier float64 `json:"qty_multiplier"`
	BillableImps  float64 `json:"billable_imps"`
	SpendMicros   int64   `json:"spend_micros"`
	SnapshotID    uint64  `json:"snapshot_id"`

	// At is the event time in unix nanos. The bid path sets this instead of
	// formatting EventTime; the writer goroutine formats it.
	At int64 `json:"-"`
}

const (
	batchMax   = 512
	flushEvery = 50 * time.Millisecond
)

// Writer ships events to ingest's /events/batch in JSON-array batches from
// one background goroutine. Log never blocks: when the buffer is full the
// event is counted in Dropped and discarded.
type Writer struct {
	ch      chan Event
	url     string
	client  *http.Client
	dropped atomic.Uint64
	failed  atomic.Uint64
}

// New takes the ingest URL. ".../events" is upgraded to ".../events/batch";
// any other URL must accept a JSON array of events.
func New(ingest string) *Writer {
	url := strings.TrimSpace(ingest)
	if strings.HasSuffix(url, "/events") {
		url += "/batch"
	}
	w := &Writer{
		ch:  make(chan Event, 16384),
		url: url,
		client: &http.Client{
			Timeout: 2 * time.Second,
			Transport: &http.Transport{
				MaxIdleConns:        4,
				MaxIdleConnsPerHost: 4,
				IdleConnTimeout:     90 * time.Second,
			},
		},
	}
	go w.loop()
	return w
}

func (w *Writer) Log(e Event) {
	if e.EventTime == "" && e.At == 0 {
		e.At = time.Now().UnixNano()
	}
	select {
	case w.ch <- e:
	default:
		w.dropped.Add(1)
	}
}

// Dropped counts events discarded because the buffer was full.
func (w *Writer) Dropped() uint64 { return w.dropped.Load() }

// Failed counts events lost to failed ingest POSTs.
func (w *Writer) Failed() uint64 { return w.failed.Load() }

func (w *Writer) loop() {
	batch := make([]Event, 0, batchMax)
	buf := make([]byte, 0, 64<<10)
	tick := time.NewTicker(flushEvery)
	defer tick.Stop()
	flush := func() {
		if len(batch) == 0 {
			return
		}
		if w.url != "" {
			buf = AppendBatch(buf[:0], batch)
			w.post(buf, len(batch))
		}
		clear(batch)
		batch = batch[:0]
	}
	for {
		select {
		case e := <-w.ch:
			batch = append(batch, e)
			if len(batch) >= batchMax {
				flush()
			}
		case <-tick.C:
			flush()
		}
	}
}

func (w *Writer) post(body []byte, n int) {
	req, err := http.NewRequest(http.MethodPost, w.url, bytes.NewReader(body))
	if err != nil {
		w.failed.Add(uint64(n))
		return
	}
	req.Header.Set("Content-Type", "application/json")
	resp, err := w.client.Do(req)
	if err != nil {
		w.failed.Add(uint64(n))
		return
	}
	resp.Body.Close()
	if resp.StatusCode >= 300 {
		w.failed.Add(uint64(n))
	}
}

// AppendBatch encodes events as a JSON array.
func AppendBatch(dst []byte, events []Event) []byte {
	dst = append(dst, '[')
	for i := range events {
		if i > 0 {
			dst = append(dst, ',')
		}
		dst = appendEvent(dst, &events[i])
	}
	return append(dst, ']')
}

func appendEvent(dst []byte, e *Event) []byte {
	dst = append(dst, `{"event_type":`...)
	dst = appendStr(dst, e.EventType)
	dst = append(dst, `,"event_time":"`...)
	if e.EventTime != "" {
		dst = appendInner(dst, e.EventTime)
	} else {
		dst = time.Unix(0, e.At).UTC().AppendFormat(dst, time.RFC3339Nano)
	}
	dst = append(dst, `","advertiser_id":`...)
	dst = strconv.AppendUint(dst, uint64(e.AdvertiserID), 10)
	dst = append(dst, `,"campaign_id":`...)
	dst = strconv.AppendUint(dst, uint64(e.CampaignID), 10)
	dst = append(dst, `,"ssp":`...)
	dst = appendStr(dst, e.SSP)
	dst = append(dst, `,"country":`...)
	dst = appendStr(dst, e.Country)
	dst = append(dst, `,"venue_type":`...)
	dst = appendStr(dst, e.VenueType)
	dst = append(dst, `,"h3":`...)
	dst = strconv.AppendUint(dst, e.H3, 10)
	dst = append(dst, `,"creative_id":`...)
	dst = strconv.AppendUint(dst, uint64(e.CreativeID), 10)
	dst = append(dst, `,"bid_request_id":`...)
	dst = appendStr(dst, e.BidRequestID)
	dst = append(dst, `,"price_cpm":`...)
	dst = strconv.AppendFloat(dst, e.PriceCPM, 'g', -1, 64)
	dst = append(dst, `,"qty_multiplier":`...)
	dst = strconv.AppendFloat(dst, e.QtyMultiplier, 'g', -1, 64)
	dst = append(dst, `,"billable_imps":`...)
	dst = strconv.AppendFloat(dst, e.BillableImps, 'g', -1, 64)
	dst = append(dst, `,"spend_micros":`...)
	dst = strconv.AppendInt(dst, e.SpendMicros, 10)
	dst = append(dst, `,"snapshot_id":`...)
	dst = strconv.AppendUint(dst, e.SnapshotID, 10)
	return append(dst, '}')
}

func appendStr(dst []byte, s string) []byte {
	dst = append(dst, '"')
	dst = appendInner(dst, s)
	return append(dst, '"')
}

func appendInner(dst []byte, s string) []byte {
	const hex = "0123456789abcdef"
	start := 0
	for i := 0; i < len(s); i++ {
		c := s[i]
		if c >= 0x20 && c != '"' && c != '\\' {
			continue
		}
		dst = append(dst, s[start:i]...)
		switch c {
		case '"', '\\':
			dst = append(dst, '\\', c)
		case '\n':
			dst = append(dst, '\\', 'n')
		default:
			dst = append(dst, '\\', 'u', '0', '0', hex[c>>4], hex[c&0xF])
		}
		start = i + 1
	}
	return append(dst, s[start:]...)
}
