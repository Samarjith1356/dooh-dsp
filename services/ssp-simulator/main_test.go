package main

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync/atomic"
	"testing"
	"time"
)

func TestHandleAuctionCallsNotices(t *testing.T) {
	var nurl, burl atomic.Int32
	var prices []string
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch {
		case strings.HasPrefix(r.URL.Path, "/nurl"):
			nurl.Add(1)
			prices = append(prices, r.URL.Query().Get("p"))
		case strings.HasPrefix(r.URL.Path, "/burl"):
			burl.Add(1)
		}
		w.WriteHeader(http.StatusNoContent)
	}))
	defer srv.Close()

	br := bidResponse{
		ID: "x",
		SeatBid: []seatBid{{
			Bid: []bid{{
				Price: 10,
				NURL:  srv.URL + "/nurl?r=1&p=${AUCTION_PRICE}",
				BURL:  srv.URL + "/burl?r=1&p=${AUCTION_PRICE}",
				LURL:  srv.URL + "/lurl?r=1&p=${AUCTION_PRICE}",
			}},
		}},
	}
	raw, _ := json.Marshal(br)
	client := srv.Client()
	handleAuction(client, raw, 2.0, 1.0, 0.0, 5*time.Millisecond)
	deadline := time.Now().Add(2 * time.Second)
	for time.Now().Before(deadline) && (nurl.Load() == 0 || burl.Load() == 0) {
		time.Sleep(5 * time.Millisecond)
	}
	if nurl.Load() != 1 || burl.Load() != 1 {
		t.Fatalf("nurl=%d burl=%d", nurl.Load(), burl.Load())
	}
	if len(prices) != 1 || prices[0] == "" || prices[0] == "${AUCTION_PRICE}" {
		t.Fatalf("clearing price not substituted: %v", prices)
	}
}

func TestHandleAuctionLoss(t *testing.T) {
	var lurl atomic.Int32
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if strings.HasPrefix(r.URL.Path, "/lurl") {
			lurl.Add(1)
		}
		w.WriteHeader(http.StatusNoContent)
	}))
	defer srv.Close()
	br := bidResponse{
		SeatBid: []seatBid{{Bid: []bid{{
			Price: 10,
			LURL:  srv.URL + "/lurl?r=1&p=${AUCTION_PRICE}",
		}}}},
	}
	raw, _ := json.Marshal(br)
	handleAuction(srv.Client(), raw, 2.0, 0.0, 0.0, time.Millisecond)
	deadline := time.Now().Add(time.Second)
	for time.Now().Before(deadline) && lurl.Load() == 0 {
		time.Sleep(5 * time.Millisecond)
	}
	if lurl.Load() != 1 {
		t.Fatalf("lurl=%d", lurl.Load())
	}
}
