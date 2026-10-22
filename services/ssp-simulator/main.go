package main

import (
	"bytes"
	"encoding/json"
	"log"
	"math/rand"
	"net/http"
	"os"
	"strconv"
	"time"
)

type qty struct {
	Multiplier float64 `json:"multiplier"`
	SourceType int     `json:"sourcetype"`
	Vendor     string  `json:"vendor"`
}

type banner struct {
	W int `json:"w"`
	H int `json:"h"`
}

type imp struct {
	ID       string  `json:"id"`
	Banner   banner  `json:"banner"`
	BidFloor float64 `json:"bidfloor"`
	Qty      qty     `json:"qty"`
}

type dooh struct {
	ID           string   `json:"id"`
	Name         string   `json:"name"`
	VenueType    []string `json:"venuetype"`
	VenueTypeTax int      `json:"venuetypetax"`
}

type geo struct {
	Lat     float64 `json:"lat"`
	Lon     float64 `json:"lon"`
	Country string  `json:"country"`
	City    string  `json:"city"`
}

type req struct {
	ID     string `json:"id"`
	Imp    []imp  `json:"imp"`
	Dooh   dooh   `json:"dooh"`
	Device struct {
		Geo geo `json:"geo"`
	} `json:"device"`
	TMax int      `json:"tmax"`
	AT   int      `json:"at"`
	Cur  []string `json:"cur"`
	Test int      `json:"test"`
}

type screen struct {
	id      string
	name    string
	venues  []string
	lat     float64
	lon     float64
	country string
	city    string
	w, h    int
	floor   float64
	qty     float64
}

func inventory() []screen {
	return []screen{
		{"jcd-lu-001", "London Underground Oxford Circus", []string{"transit.rail.underground", "transit.rail"}, 51.5154, -0.1419, "GB", "London", 1080, 1920, 3.2, 18.4},
		{"jcd-rd-001", "London roadside A4 Cromwell", []string{"roadside.billboard", "roadside"}, 51.495, -0.183, "GB", "London", 1920, 1080, 4.1, 22.0},
		{"jcd-dub-001", "Dublin O'Connell Street", []string{"roadside", "urban.street"}, 53.3498, -6.2603, "IE", "Dublin", 1920, 1080, 2.8, 11.5},
		{"jcd-dub-002", "Dublin Bus Connects", []string{"transit.bus", "transit.rail"}, 53.347, -6.259, "IE", "Dublin", 1080, 1920, 2.1, 9.0},
	}
}

func main() {
	url := getenv("BIDDER_URL", "http://localhost:8081/openrtb/v2/bid")
	qps, _ := strconv.Atoi(getenv("QPS", "20"))
	if qps <= 0 {
		qps = 20
	}
	inv := inventory()
	client := &http.Client{Timeout: 800 * time.Millisecond}
	ticker := time.NewTicker(time.Second / time.Duration(qps))
	defer ticker.Stop()
	log.Printf("ssp-simulator -> %s at %d qps", url, qps)
	n := 0
	for range ticker.C {
		s := inv[rand.Intn(len(inv))]
		body := req{
			ID: "sim-" + strconv.Itoa(n),
			Imp: []imp{{
				ID:       "1",
				Banner:   banner{W: s.w, H: s.h},
				BidFloor: s.floor,
				Qty:      qty{Multiplier: s.qty, SourceType: 1, Vendor: "viooh.com"},
			}},
			Dooh: dooh{ID: s.id, Name: s.name, VenueType: s.venues, VenueTypeTax: 1},
			TMax: 100,
			AT:   1,
			Cur:  []string{"GBP"},
			Test: 1,
		}
		body.Device.Geo = geo{Lat: s.lat, Lon: s.lon, Country: s.country, City: s.city}
		raw, _ := json.Marshal(body)
		resp, err := client.Post(url, "application/json", bytes.NewReader(raw))
		if err != nil {
			log.Printf("bid error: %s", err)
			continue
		}
		resp.Body.Close()
		n++
		if n%50 == 0 {
			log.Printf("sent %d requests last_status=%d", n, resp.StatusCode)
		}
	}
}

func getenv(k, d string) string {
	if v := os.Getenv(k); v != "" {
		return v
	}
	return d
}
