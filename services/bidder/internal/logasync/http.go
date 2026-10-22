package logasync

import (
	"bytes"
	"encoding/json"
	"net/http"
	"time"
)

// HTTPFallback posts events to ingest when Kafka client is unavailable.
func (w *Writer) PostHTTP(url string, e Event) {
	b, _ := json.Marshal(e)
	client := &http.Client{Timeout: 200 * time.Millisecond}
	req, err := http.NewRequest(http.MethodPost, url, bytes.NewReader(b))
	if err != nil {
		return
	}
	req.Header.Set("Content-Type", "application/json")
	resp, err := client.Do(req)
	if err != nil {
		return
	}
	resp.Body.Close()
}
