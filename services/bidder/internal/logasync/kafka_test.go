package logasync

import (
	"context"
	"encoding/json"
	"os"
	"strconv"
	"testing"
	"time"

	"github.com/twmb/franz-go/pkg/kgo"
)

// Produces through NewKafka and consumes the records back when
// KAFKA_TEST_BROKERS points at a scratch Redpanda/Kafka.
func TestKafkaSinkRoundTrip(t *testing.T) {
	brokers := os.Getenv("KAFKA_TEST_BROKERS")
	if brokers == "" {
		t.Skip("KAFKA_TEST_BROKERS not set")
	}
	topic := "test.bid_log." + strconv.FormatInt(time.Now().UnixNano(), 10)
	w, err := NewKafka(brokers, topic)
	if err != nil {
		t.Fatal(err)
	}
	for i := 0; i < 1000; i++ {
		w.Log(Event{EventType: "bid", BidRequestID: "r" + strconv.Itoa(i), SpendMicros: 55250})
	}
	cl, err := kgo.NewClient(kgo.SeedBrokers(brokers), kgo.ConsumeTopics(topic), kgo.ConsumeResetOffset(kgo.NewOffset().AtStart()))
	if err != nil {
		t.Fatal(err)
	}
	defer cl.Close()
	ctx, cancel := context.WithTimeout(context.Background(), 20*time.Second)
	defer cancel()
	seen := 0
	for seen < 1000 {
		fs := cl.PollFetches(ctx)
		if ctx.Err() != nil {
			t.Fatalf("got %d/1000 records; failed=%d dropped=%d", seen, w.Failed(), w.Dropped())
		}
		fs.EachRecord(func(r *kgo.Record) {
			var e map[string]any
			if err := json.Unmarshal(r.Value, &e); err != nil || e["event_type"] != "bid" {
				t.Fatalf("bad record %s", r.Value)
			}
			seen++
		})
	}
	if w.Failed() != 0 || w.Dropped() != 0 {
		t.Fatalf("failed=%d dropped=%d", w.Failed(), w.Dropped())
	}
}
