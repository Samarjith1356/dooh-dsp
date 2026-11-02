package logasync

import (
	"context"
	"strings"
	"time"

	"github.com/twmb/franz-go/pkg/kgo"
)

// NewKafka ships each event as one JSON record to topic. The client batches
// records per partition (5ms linger), retries, and is idempotent, so events
// survive a slow or restarting ingest: they wait in Redpanda instead of
// being dropped. Brokers are comma-separated host:port.
func NewKafka(brokers, topic string) (*Writer, error) {
	cl, err := kgo.NewClient(
		kgo.SeedBrokers(strings.Split(brokers, ",")...),
		kgo.DefaultProduceTopic(topic),
		kgo.AllowAutoTopicCreation(),
		kgo.ProducerLinger(5*time.Millisecond),
		kgo.MaxBufferedRecords(200_000),
		kgo.RecordDeliveryTimeout(30*time.Second),
		kgo.ProducerBatchMaxBytes(1<<20),
		// Uncompressed: ingest's kafka-python decodes it with no extra
		// codec libraries, and the hop is inside the cluster.
		kgo.ProducerBatchCompression(kgo.NoCompression()),
	)
	if err != nil {
		return nil, err
	}
	w := newWriter()
	done := func(_ *kgo.Record, err error) {
		if err != nil {
			w.failed.Add(1)
		}
	}
	w.ship = func(batch []Event) {
		for i := range batch {
			// The client owns the value until delivery, so each record
			// gets its own buffer.
			rec := &kgo.Record{Value: appendEvent(make([]byte, 0, 384), &batch[i])}
			cl.TryProduce(context.Background(), rec, done)
		}
	}
	go w.loop()
	return w, nil
}
