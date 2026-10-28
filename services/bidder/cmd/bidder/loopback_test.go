package main

import (
	"bytes"
	"io"
	"net/http"
	"net/http/httptest"
	"sort"
	"strconv"
	"sync"
	"testing"
	"time"
)

var loopbackPayload = []byte(`{"id":"sim-1","imp":[{"id":"1","banner":{"w":1920,"h":1080},"bidfloor":2.0,"qty":{"multiplier":14.2,"sourcetype":1,"vendor":"viooh.com"}}],"dooh":{"id":"jcd-rd-001","name":"London roadside A4 Cromwell","venuetype":["roadside.billboard","roadside"],"venuetypetax":1},"device":{"geo":{"lat":51.5074,"lon":-0.1278,"country":"GB","city":"London"}},"tmax":100,"at":1,"cur":["GBP"],"test":1}`)

// runLoopback drives a real keep-alive HTTP server on loopback with `conc`
// concurrent clients and reports server-side decision percentiles (header)
// plus client round-trip percentiles.
func runLoopback(b *testing.B, h http.Handler, conc int) {
	srv := httptest.NewServer(h)
	defer srv.Close()
	tr := &http.Transport{MaxIdleConns: conc * 2, MaxIdleConnsPerHost: conc * 2}
	client := &http.Client{Transport: tr}
	url := srv.URL + "/openrtb/v2/bid"

	var mu sync.Mutex
	dec := make([]int64, 0, b.N)
	rtt := make([]int64, 0, b.N)
	work := make(chan struct{}, conc)
	var wg sync.WaitGroup
	b.ReportAllocs()
	b.ResetTimer()
	for w := 0; w < conc; w++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			ld := make([]int64, 0, 1024)
			lr := make([]int64, 0, 1024)
			for range work {
				t0 := time.Now()
				resp, err := client.Post(url, "application/json", bytes.NewReader(loopbackPayload))
				if err != nil {
					b.Error(err)
					return
				}
				_, _ = io.Copy(io.Discard, resp.Body)
				resp.Body.Close()
				lr = append(lr, time.Since(t0).Microseconds())
				n, _ := strconv.ParseInt(resp.Header.Get("X-DSP-Decision-Us"), 10, 64)
				ld = append(ld, n)
			}
			mu.Lock()
			dec = append(dec, ld...)
			rtt = append(rtt, lr...)
			mu.Unlock()
		}()
	}
	for i := 0; i < b.N; i++ {
		work <- struct{}{}
	}
	close(work)
	wg.Wait()
	b.StopTimer()
	report(b, "dec", dec)
	report(b, "rtt", rtt)
}

func report(b *testing.B, name string, v []int64) {
	if len(v) == 0 {
		return
	}
	sort.Slice(v, func(i, j int) bool { return v[i] < v[j] })
	q := func(p float64) float64 { return float64(v[int(p*float64(len(v)-1))]) }
	b.ReportMetric(q(0.50), name+"-p50-us")
	b.ReportMetric(q(0.99), name+"-p99-us")
	b.ReportMetric(q(0.999), name+"-p999-us")
	b.ReportMetric(float64(v[len(v)-1]), name+"-max-us")
}
