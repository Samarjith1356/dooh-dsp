package logasync

import (
	"encoding/json"
	"net"
	"os"
	"strings"
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
}

type Writer struct {
	ch      chan Event
	brokers []string
}

func New(brokers string) *Writer {
	w := &Writer{
		ch:      make(chan Event, 4096),
		brokers: strings.Split(brokers, ","),
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
	}
}

func (w *Writer) loop() {
	topic := "rtb.bid_log"
	for e := range w.ch {
		payload, _ := json.Marshal(e)
		if err := produce(w.brokers[0], topic, payload); err != nil {
			os.Stderr.WriteString("kafka log skip: " + err.Error() + "\n")
		}
	}
}

func produce(broker, topic string, value []byte) error {
	conn, err := net.DialTimeout("tcp", strings.TrimSpace(broker), 200*time.Millisecond)
	if err != nil {
		return err
	}
	conn.Close()
	_ = topic
	_ = value
	return nil
}
