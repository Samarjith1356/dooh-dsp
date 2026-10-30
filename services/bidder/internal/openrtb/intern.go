package openrtb

import (
	"sync"
	"sync/atomic"
)

// String interning for low-cardinality request fields (country, venue types,
// imp IDs, screen IDs). Reads are a lock-free atomic load plus a map lookup;
// m[string(b)] does not allocate. New strings copy-on-write a small shard, so
// the first sighting of a value pays and every later request is free.
const (
	internShards   = 64
	internShardMax = 1024 // ~65k interned strings total
	internMaxLen   = 64
)

type internShard struct {
	mu sync.Mutex
	m  atomic.Pointer[map[string]string]
}

var interned [internShards]internShard

func intern(b []byte) string {
	if len(b) == 0 {
		return ""
	}
	if len(b) > internMaxLen {
		return string(b)
	}
	sh := &interned[fnv1a(b)%internShards]
	if m := sh.m.Load(); m != nil {
		if s, ok := (*m)[string(b)]; ok {
			return s
		}
	}
	s := string(b)
	sh.mu.Lock()
	defer sh.mu.Unlock()
	old := sh.m.Load()
	if old != nil {
		if v, ok := (*old)[s]; ok {
			return v
		}
		if len(*old) >= internShardMax {
			return s
		}
	}
	next := make(map[string]string, 1+lenMap(old))
	if old != nil {
		for k, v := range *old {
			next[k] = v
		}
	}
	next[s] = s
	sh.m.Store(&next)
	return s
}

func lenMap(m *map[string]string) int {
	if m == nil {
		return 0
	}
	return len(*m)
}

func fnv1a(b []byte) uint32 {
	h := uint32(2166136261)
	for _, c := range b {
		h ^= uint32(c)
		h *= 16777619
	}
	return h
}
