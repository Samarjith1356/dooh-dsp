package budget

import (
	"context"
	"strconv"
	"strings"
	"sync"
	"time"
)

type RedisClient interface {
	Get(ctx context.Context, key string) (string, error)
}

type Cache struct {
	mu    sync.RWMutex
	rem   map[uint32]int64
	ready bool
}

func New() *Cache {
	return &Cache{rem: map[uint32]int64{}}
}

func (c *Cache) Remaining(id uint32) (int64, bool) {
	c.mu.RLock()
	defer c.mu.RUnlock()
	if !c.ready {
		return 0, false
	}
	v, ok := c.rem[id]
	return v, ok
}

func (c *Cache) SetAll(m map[uint32]int64) {
	c.mu.Lock()
	c.rem = m
	c.ready = true
	c.mu.Unlock()
}

func ParseInt(s string) int64 {
	s = strings.TrimSpace(s)
	n, _ := strconv.ParseInt(s, 10, 64)
	return n
}

func (c *Cache) Ensure(ids []uint32, defaultRem int64) {
	c.mu.Lock()
	defer c.mu.Unlock()
	if c.rem == nil {
		c.rem = map[uint32]int64{}
	}
	for _, id := range ids {
		if _, ok := c.rem[id]; !ok {
			c.rem[id] = defaultRem
		}
	}
	c.ready = true
}

func RefreshLoop(ctx context.Context, r RedisClient, idsFn func() []uint32, dst *Cache) {
	tick := time.NewTicker(250 * time.Millisecond)
	defer tick.Stop()
	for {
		select {
		case <-ctx.Done():
			return
		case <-tick.C:
			ids := idsFn()
			next := make(map[uint32]int64, len(ids))
			okAny := false
			for _, id := range ids {
				cctx, cancel := context.WithTimeout(ctx, 50*time.Millisecond)
				val, err := r.Get(cctx, "budget:"+strconv.FormatUint(uint64(id), 10)+":remaining_micros")
				cancel()
				if err != nil {
					continue
				}
				next[id] = ParseInt(val)
				okAny = true
			}
			if okAny {
				dst.SetAll(next)
			}
		}
	}
}
