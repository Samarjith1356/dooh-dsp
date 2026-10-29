// Package budget keeps each campaign's remaining micros in memory for the
// bid path and keeps it in step with one shared counter in Redis, so any
// number of bidder instances draw down the same budget.
//
// Bid path: one atomic load to check, one CAS to spend. Background: every
// SyncEvery, one Lua call pushes each campaign's unsynced spend to Redis
// (DECRBY) and reads back the shared remaining value.
//
// Brain still SETs budget:{id}:remaining_micros every pacing tick from
// ClickHouse spend. Spend that ClickHouse has not ingested yet is briefly
// added back at that moment, so worst-case overspend is the ingest lag's
// worth of spend, not "until the next Brain tick" per instance.
package budget

import (
	"context"
	"log"
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

// SyncEvery is how often local spend is pushed to Redis.
var SyncEvery = 100 * time.Millisecond

// syncScript decrements each existing key by its delta and returns the new
// value, or nil for a missing key. It never creates keys: a campaign Brain
// has not budgeted stays Unknown. One round trip, atomic across instances.
const syncScript = `local out = {}
for i, k in ipairs(KEYS) do
  if redis.call('EXISTS', k) == 1 then
    local d = tonumber(ARGV[i])
    if d ~= 0 then
      out[i] = redis.call('DECRBY', k, d)
    else
      out[i] = tonumber(redis.call('GET', k)) or 0
    end
  else
    out[i] = false
  end
end
return out`

type Scripter interface {
	Eval(ctx context.Context, script string, keys, argv []string) ([]string, []bool, error)
}

// Slot is one campaign's budget state.
type Slot struct {
	rem     atomic.Int64 // remaining micros as the bid path sees it
	pending atomic.Int64 // spent locally, not yet pushed to Redis
}

func (s *Slot) Load() int64 { return s.rem.Load() }

// Store sets the remaining value directly (tests and seeding).
func (s *Slot) Store(v int64) { s.rem.Store(v) }

// Cache maps campaign IDs to stable slots. Readers never lock.
type Cache struct {
	mu    sync.Mutex // guards slot creation only
	slots atomic.Pointer[map[uint32]*Slot]
	ready atomic.Bool
}

func New() *Cache {
	c := &Cache{}
	m := map[uint32]*Slot{}
	c.slots.Store(&m)
	return c
}

func (c *Cache) Ready() bool { return c.ready.Load() }

// Slot returns the stable slot for a campaign, creating it as Unknown.
func (c *Cache) Slot(id uint32) *Slot {
	if s, ok := (*c.slots.Load())[id]; ok {
		return s
	}
	c.mu.Lock()
	defer c.mu.Unlock()
	old := *c.slots.Load()
	if s, ok := old[id]; ok {
		return s
	}
	next := make(map[uint32]*Slot, len(old)+1)
	for k, v := range old {
		next[k] = v
	}
	s := &Slot{}
	s.rem.Store(Unknown)
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
	v := s.rem.Load()
	if v == Unknown {
		return 0, false
	}
	return v, true
}

// Spend records a bid: deducts locally right away so this instance stops
// once the campaign runs dry, and queues the amount for Redis.
func Spend(s *Slot, micros int64) {
	if s == nil || micros <= 0 {
		return
	}
	s.pending.Add(micros)
	for {
		v := s.rem.Load()
		// A sync may have marked the slot Unknown since the match;
		// subtracting from MinInt64 would wrap to a huge positive budget.
		if v == Unknown || s.rem.CompareAndSwap(v, v-micros) {
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
			s.rem.Store(v)
		} else {
			s.rem.Store(Unknown)
		}
	}
	c.ready.Store(true)
}

func ParseInt(s string) int64 {
	s = strings.TrimSpace(s)
	n, err := strconv.ParseInt(s, 10, 64)
	if err != nil {
		f, _ := strconv.ParseFloat(s, 64)
		n = int64(f)
	}
	return n
}

// Ensure seeds campaigns that have no value yet with defaultRem.
func (c *Cache) Ensure(ids []uint32, defaultRem int64) {
	for _, id := range ids {
		c.Slot(id).rem.CompareAndSwap(Unknown, defaultRem)
	}
	c.ready.Store(true)
}

func Key(id uint32) string {
	return "budget:" + strconv.FormatUint(uint64(id), 10) + ":remaining_micros"
}

// Sync pushes unsynced spend for ids to Redis and loads the shared values.
// On error the spend is put back and retried on the next call, so no spend
// is lost while Redis is unreachable.
func (c *Cache) Sync(ctx context.Context, r Scripter, ids []uint32) error {
	if len(ids) == 0 {
		return nil
	}
	keys := make([]string, len(ids))
	argv := make([]string, len(ids))
	slots := make([]*Slot, len(ids))
	deltas := make([]int64, len(ids))
	for i, id := range ids {
		s := c.Slot(id)
		slots[i] = s
		deltas[i] = s.pending.Swap(0)
		keys[i] = Key(id)
		argv[i] = strconv.FormatInt(deltas[i], 10)
	}
	vals, found, err := r.Eval(ctx, syncScript, keys, argv)
	if err != nil {
		for i, s := range slots {
			s.pending.Add(deltas[i])
		}
		return err
	}
	for i, s := range slots {
		if !found[i] {
			s.rem.Store(Unknown)
			continue
		}
		// Bids placed since the swap are in pending and not yet in Redis.
		s.rem.Store(ParseInt(vals[i]) - s.pending.Load())
	}
	c.ready.Store(true)
	return nil
}

// SyncLoop runs Sync every SyncEvery. Never called from the bid path.
func SyncLoop(ctx context.Context, r Scripter, idsFn func() []uint32, dst *Cache) {
	tick := time.NewTicker(SyncEvery)
	defer tick.Stop()
	var lastErr string
	for {
		select {
		case <-ctx.Done():
			return
		case <-tick.C:
			cctx, cancel := context.WithTimeout(ctx, 200*time.Millisecond)
			err := dst.Sync(cctx, r, idsFn())
			cancel()
			if err != nil && err.Error() != lastErr {
				log.Printf("budget sync: %s", err)
			}
			if err != nil {
				lastErr = err.Error()
			} else {
				lastErr = ""
			}
		}
	}
}
