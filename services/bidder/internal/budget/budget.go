package budget

import (
	"context"
	"math"
	"strconv"
	"strings"
	"sync"
	"sync/atomic"
	"time"
)

// Unknown marks a campaign whose remaining budget could not be read. The
// bidder never bids on it.
const Unknown = math.MinInt64

type RedisClient interface {
	MGet(ctx context.Context, keys []string) ([]string, []bool, error)
}

// Cache holds remaining micros per campaign in one atomic counter each.
// The bid path does a single atomic load (and an atomic add when it bids);
// Redis refreshes store into the same counters, so readers never lock.
type Cache struct {
	mu    sync.Mutex // guards slot creation only
	slots atomic.Pointer[map[uint32]*atomic.Int64]
	ready atomic.Bool
}

func New() *Cache {
	c := &Cache{}
	m := map[uint32]*atomic.Int64{}
	c.slots.Store(&m)
	return c
}

func (c *Cache) Ready() bool { return c.ready.Load() }

// Slot returns the stable counter for a campaign, creating it as Unknown.
func (c *Cache) Slot(id uint32) *atomic.Int64 {
	if s, ok := (*c.slots.Load())[id]; ok {
		return s
	}
	c.mu.Lock()
	defer c.mu.Unlock()
	old := *c.slots.Load()
	if s, ok := old[id]; ok {
		return s
	}
	next := make(map[uint32]*atomic.Int64, len(old)+1)
	for k, v := range old {
		next[k] = v
	}
	s := &atomic.Int64{}
	s.Store(Unknown)
	next[id] = s
	c.slots.Store(&next)
	return s
}

func (c *Cache) Remaining(id uint32) (int64, bool) {
	if !c.ready.Load() {
		return 0, false
	}
	s, ok := (*c.slots.Load())[id]
	if !ok {
		return 0, false
	}
	v := s.Load()
	if v == Unknown {
		return 0, false
	}
	return v, true
}

// Spend deducts a bid's spend locally so the bidder stops before the next
// Redis refresh once a campaign runs dry.
func Spend(s *atomic.Int64, micros int64) {
	if s == nil || micros <= 0 {
		return
	}
	for {
		v := s.Load()
		// A refresh may have marked the slot Unknown since the match;
		// subtracting from MinInt64 would wrap to a huge positive budget.
		if v == Unknown || s.CompareAndSwap(v, v-micros) {
			return
		}
	}
}

// SetAll replaces every known campaign's remaining budget. Campaigns missing
// from m become Unknown (no bid), matching a failed Redis read.
func (c *Cache) SetAll(m map[uint32]int64) {
	for id := range m {
		c.Slot(id)
	}
	for id, s := range *c.slots.Load() {
		if v, ok := m[id]; ok {
			s.Store(v)
		} else {
			s.Store(Unknown)
		}
	}
	c.ready.Store(true)
}

func ParseInt(s string) int64 {
	s = strings.TrimSpace(s)
	n, _ := strconv.ParseInt(s, 10, 64)
	return n
}

// Ensure seeds campaigns that have no value yet with defaultRem.
func (c *Cache) Ensure(ids []uint32, defaultRem int64) {
	for _, id := range ids {
		c.Slot(id).CompareAndSwap(Unknown, defaultRem)
	}
	c.ready.Store(true)
}

// RefreshLoop reads every campaign's remaining budget from Redis in one MGET
// round trip every 250ms. Never called from the bid path.
func RefreshLoop(ctx context.Context, r RedisClient, idsFn func() []uint32, dst *Cache) {
	tick := time.NewTicker(250 * time.Millisecond)
	defer tick.Stop()
	var keys []string
	for {
		select {
		case <-ctx.Done():
			return
		case <-tick.C:
			ids := idsFn()
			if len(ids) == 0 {
				continue
			}
			keys = keys[:0]
			for _, id := range ids {
				keys = append(keys, "budget:"+strconv.FormatUint(uint64(id), 10)+":remaining_micros")
			}
			cctx, cancel := context.WithTimeout(ctx, 100*time.Millisecond)
			vals, found, err := r.MGet(cctx, keys)
			cancel()
			if err != nil {
				continue
			}
			next := make(map[uint32]int64, len(ids))
			for i, id := range ids {
				if found[i] {
					next[id] = ParseInt(vals[i])
				}
			}
			if len(next) > 0 {
				dst.SetAll(next)
			}
		}
	}
}
