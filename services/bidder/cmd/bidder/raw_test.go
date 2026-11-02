package main

import (
	"bufio"
	"bytes"
	"net"
	"net/http"
	"net/http/httptest"
	"strconv"
	"testing"
)

// BenchmarkServerRaw measures server-side cost per bid (net/http + handler)
// using a raw keep-alive TCP client that allocates nothing per request.
func BenchmarkServerRaw(b *testing.B) {
	srv := httptest.NewServer(http.HandlerFunc(testBidder("simulator", 1<<62).handleBid))
	defer srv.Close()
	conn, err := net.Dial("tcp", srv.Listener.Addr().String())
	if err != nil {
		b.Fatal(err)
	}
	defer conn.Close()
	reqBytes := []byte("POST /openrtb/v2/bid HTTP/1.1\r\nHost: x\r\nContent-Type: application/json\r\nContent-Length: " +
		strconv.Itoa(len(testPayload)) + "\r\n\r\n" + string(testPayload))
	rd := bufio.NewReaderSize(conn, 8192)
	body := make([]byte, 4096)
	b.ReportAllocs()
	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		if _, err := conn.Write(reqBytes); err != nil {
			b.Fatal(err)
		}
		n := 0
		for {
			line, err := rd.ReadSlice('\n')
			if err != nil {
				b.Fatal(err)
			}
			if len(line) <= 2 {
				break
			}
			if bytes.HasPrefix(line, []byte("Content-Length: ")) {
				n, _ = strconv.Atoi(string(bytes.TrimSpace(line[16:])))
			}
		}
		if _, err := rd.Read(body[:n]); err != nil {
			b.Fatal(err)
		}
	}
}
