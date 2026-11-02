package budget

import (
	"context"
	"errors"
	"os"
	"strconv"
	"sync"
	"testing"

	"github.com/dooh-dsp/bidder/internal/redisc"
)

func TestSpendNeverWrapsUnknown(t *testing.T) {
	c := New()
	s := c.Slot(1)
	Spend(s, 1000)
	if s.Load() != Unknown {
		t.Fatalf("unknown slot changed to %d", s.Load())
	}
	if _, ok := c.Remaining(1); ok {
		t.Fatal("unknown must not be ok")
	}
}

func TestSetAllMarksMissingUnknown(t *testing.T) {
	c := New()
	c.Ensure([]uint32{1, 2}, 500)
	Spend(c.Slot(1), 200)
	if v, ok := c.Remaining(1); !ok || v != 300 {
		t.Fatalf("after spend %d %v", v, ok)
	}
	c.SetAll(map[uint32]int64{1: 900})
	if v, ok := c.Remaining(1); !ok || v != 900 {
		t.Fatalf("refresh %d %v", v, ok)
	}
	if _, ok := c.Remaining(2); ok {
		t.Fatal("campaign missing from refresh must be unknown")
	}
	c.Ensure([]uint32{2}, 50)
	if v, _ := c.Remaining(2); v != 50 {
		t.Fatalf("ensure reseeds unknown, got %d", v)
	}
}

// fakeRedis implements the sync script semantics in memory, shared by
// several caches the way one Redis is shared by several bidders.
type fakeRedis struct {
	mu   sync.Mutex
	vals map[string]int64
	fail bool
}

func (f *fakeRedis) Eval(_ context.Context, _ string, keys, argv []string) ([]string, []bool, error) {
	f.mu.Lock()
	defer f.mu.Unlock()
	if f.fail {
		return nil, nil, errors.New("down")
	}
	out := make([]string, len(keys))
	found := make([]bool, len(keys))
	for i, k := range keys {
		v, ok := f.vals[k]
		if !ok {
			continue
		}
		d, _ := strconv.ParseInt(argv[i], 10, 64)
		v -= d
		f.vals[k] = v
		out[i], found[i] = strconv.FormatInt(v, 10), true
	}
	return out, found, nil
}

func TestSharedBudgetAcrossInstances(t *testing.T) {
	r := &fakeRedis{vals: map[string]int64{Key(1): 1000}}
	a, b := New(), New()
	ctx := context.Background()
	for _, c := range []*Cache{a, b} {
		if err := c.Sync(ctx, r, []uint32{1}); err != nil {
			t.Fatal(err)
		}
	}
	Spend(a.Slot(1), 300)
	Spend(b.Slot(1), 400)
	_ = a.Sync(ctx, r, []uint32{1})
	_ = b.Sync(ctx, r, []uint32{1})
	if r.vals[Key(1)] != 300 {
		t.Fatalf("redis %d, want 300", r.vals[Key(1)])
	}
	_ = a.Sync(ctx, r, []uint32{1})
	if v, _ := a.Remaining(1); v != 300 {
		t.Fatalf("instance a sees %d, want 300 (b's spend included)", v)
	}
}

func TestSyncFailureKeepsSpend(t *testing.T) {
	r := &fakeRedis{vals: map[string]int64{Key(1): 1000}}
	c := New()
	ctx := context.Background()
	_ = c.Sync(ctx, r, []uint32{1})
	Spend(c.Slot(1), 250)
	r.fail = true
	if err := c.Sync(ctx, r, []uint32{1}); err == nil {
		t.Fatal("expected error")
	}
	if v, _ := c.Remaining(1); v != 750 {
		t.Fatalf("local view %d, want 750", v)
	}
	r.fail = false
	_ = c.Sync(ctx, r, []uint32{1})
	if r.vals[Key(1)] != 750 {
		t.Fatalf("spend lost during outage: redis %d", r.vals[Key(1)])
	}
}

func TestSyncMissingKeyIsUnknown(t *testing.T) {
	c := New()
	c.Ensure([]uint32{7}, 500)
	_ = c.Sync(context.Background(), &fakeRedis{vals: map[string]int64{}}, []uint32{7})
	if _, ok := c.Remaining(7); ok {
		t.Fatal("campaign without a Redis budget must not bid")
	}
}

// Runs the real Lua script when REDIS_TEST_ADDR points at a scratch Redis.
func TestSyncScriptOnRedis(t *testing.T) {
	addr := os.Getenv("REDIS_TEST_ADDR")
	if addr == "" {
		t.Skip("REDIS_TEST_ADDR not set")
	}
	r := redisc.ParseURL("redis://" + addr + "/0")
	ctx := context.Background()
	seed := `redis.call('SET', KEYS[1], ARGV[1]) redis.call('DEL', KEYS[2]) return {1, 1}`
	if _, _, err := r.Eval(ctx, seed, []string{Key(901), Key(902)}, []string{"5000"}); err != nil {
		t.Fatal(err)
	}
	var wg sync.WaitGroup
	for n := 0; n < 4; n++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			c := New()
			for i := 0; i < 50; i++ {
				Spend(c.Slot(901), 10)
				if err := c.Sync(ctx, r, []uint32{901, 902}); err != nil {
					t.Error(err)
					return
				}
			}
			if _, ok := c.Remaining(902); ok {
				t.Error("missing key must stay unknown")
			}
		}()
	}
	wg.Wait()
	v, err := r.Get(ctx, Key(901))
	if err != nil || v != "3000" {
		t.Fatalf("redis %q %v, want 3000 (4 instances x 50 x 10 spent)", v, err)
	}
	if _, err := r.Get(ctx, Key(902)); err != redisc.ErrMissing {
		t.Fatalf("script created a key: %v", err)
	}
}
