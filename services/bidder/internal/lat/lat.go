// Package lat records bid-path latency with lock-free log-linear histograms
// (HDR-style: 8 sub-buckets per power of two, so any percentile is reported
// within 12.5%, rounded up). Observe is a few atomic adds and never blocks.
package lat

import (
	"math/bits"
	"sync/atomic"
	"time"
)

const (
	subBits    = 3
	subBuckets = 1 << subBits
	numBuckets = (64-subBits)*subBuckets + subBuckets
	window     = 60 * time.Second
)

type hist struct {
	counts [numBuckets]atomic.Uint64
	n      atomic.Uint64
	sum    atomic.Uint64
	max    atomic.Uint64
}

func bucketOf(v uint64) int {
	if v < subBuckets {
		return int(v)
	}
	e := bits.Len64(v) - 1
	return (e-subBits+1)*subBuckets + int((v>>(uint(e)-subBits))&(subBuckets-1))
}

// upperBound is the largest value that lands in bucket b.
func upperBound(b int) uint64 {
	if b < subBuckets {
		return uint64(b)
	}
	e := b/subBuckets + subBits - 1
	m := uint64(b % subBuckets)
	return ((subBuckets+m+1)<<(uint(e)-subBits) - 1)
}

func (h *hist) observe(v uint64) {
	h.counts[bucketOf(v)].Add(1)
	h.n.Add(1)
	h.sum.Add(v)
	for {
		cur := h.max.Load()
		if v <= cur || h.max.CompareAndSwap(cur, v) {
			return
		}
	}
}

func (h *hist) reset() {
	for i := range h.counts {
		h.counts[i].Store(0)
	}
	h.n.Store(0)
	h.sum.Store(0)
	h.max.Store(0)
}

// Recorder keeps an all-time histogram plus a rolling window made of the
// current and previous 60s slices.
type Recorder struct {
	all     hist
	slices  [2]hist
	cur     atomic.Uint32
	rotated atomic.Int64
	last    atomic.Uint64
}

func (r *Recorder) Observe(ns int64) {
	if ns < 0 {
		ns = 0
	}
	v := uint64(ns)
	r.all.observe(v)
	r.slices[r.cur.Load()&1].observe(v)
	r.last.Store(v)
}

// rotate starts a new window slice; called from a background ticker.
func (r *Recorder) rotate() {
	next := (r.cur.Load() + 1) & 1
	r.slices[next].reset()
	r.cur.Store(next)
	r.rotated.Store(time.Now().UnixNano())
}

// Stats are in microseconds.
type Stats struct {
	Count                uint64
	AvgUs, MaxUs, LastUs uint64
	P50, P90, P99, P999  uint64
	WindowMaxUs, WindowN uint64
}

func (r *Recorder) Stats() Stats {
	s := Stats{Count: r.all.n.Load(), MaxUs: r.all.max.Load() / 1000, LastUs: r.last.Load() / 1000}
	if s.Count > 0 {
		s.AvgUs = r.all.sum.Load() / s.Count / 1000
	}
	var merged [numBuckets]uint64
	var n, max uint64
	for i := range r.slices {
		h := &r.slices[i]
		for b := range merged {
			merged[b] += h.counts[b].Load()
		}
		n += h.n.Load()
		if m := h.max.Load(); m > max {
			max = m
		}
	}
	s.WindowN, s.WindowMaxUs = n, max/1000
	if n == 0 {
		return s
	}
	q := func(p float64) uint64 {
		rank := uint64(p*float64(n-1)) + 1
		var seen uint64
		for b, c := range merged {
			if seen += c; seen >= rank {
				if ub := upperBound(b); ub < max {
					return ub / 1000
				}
				return max / 1000
			}
		}
		return max / 1000
	}
	s.P50, s.P90, s.P99, s.P999 = q(0.50), q(0.90), q(0.99), q(0.999)
	return s
}

var (
	// Decision is the full handler time: body read, parse, match, serialize.
	Decision Recorder
	// Compute excludes the body read: parse, match, serialize only.
	Compute Recorder
)

func init() {
	go func() {
		t := time.NewTicker(window)
		for range t.C {
			Decision.rotate()
			Compute.rotate()
		}
	}()
}

// Observe records a decision time (kept for existing callers).
func Observe(ns int64) { Decision.Observe(ns) }

// Snapshot returns all-time decision count, avg, max and last in µs.
func Snapshot() (count, avgUs, maxUs, lastUs uint64) {
	s := Decision.Stats()
	return s.Count, s.AvgUs, s.MaxUs, s.LastUs
}
