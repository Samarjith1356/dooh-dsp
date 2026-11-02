package logasync

import (
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"
)

func TestBatchShipsValidJSON(t *testing.T) {
	got := make(chan []map[string]any, 4)
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/events/batch" {
			t.Errorf("path %s", r.URL.Path)
		}
		raw, _ := io.ReadAll(r.Body)
		var v []map[string]any
		if err := json.Unmarshal(raw, &v); err != nil {
			t.Errorf("bad json %s: %v", raw, err)
		}
		got <- v
	}))
	defer srv.Close()
	w := New(srv.URL + "/events")
	at := time.Date(2026, 10, 28, 9, 0, 0, 123456789, time.UTC).UnixNano()
	w.Log(Event{EventType: "bid", BidRequestID: "a\"b\n", CampaignID: 5, SpendMicros: 55250, QtyMultiplier: 10, At: at})
	w.Log(Event{EventType: "win", BidRequestID: "c"})
	var all []map[string]any
	for len(all) < 2 {
		select {
		case v := <-got:
			all = append(all, v...)
		case <-time.After(2 * time.Second):
			t.Fatal("no batch")
		}
	}
	if all[0]["bid_request_id"] != "a\"b\n" || all[0]["event_time"] != "2026-10-28T09:00:00.123456789Z" || all[0]["spend_micros"].(float64) != 55250 {
		t.Fatalf("%v", all[0])
	}
	if w.Dropped() != 0 || w.Failed() != 0 {
		t.Fatal("unexpected loss")
	}
}
