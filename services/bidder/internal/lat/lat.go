package lat

import "sync/atomic"

var (
	n      atomic.Uint64
	sumNS  atomic.Uint64
	maxNS  atomic.Uint64
	lastNS atomic.Uint64
)

func Observe(ns int64) {
	if ns < 0 {
		ns = 0
	}
	u := uint64(ns)
	n.Add(1)
	sumNS.Add(u)
	lastNS.Store(u)
	for {
		cur := maxNS.Load()
		if u <= cur || maxNS.CompareAndSwap(cur, u) {
			return
		}
	}
}

func Snapshot() (count, avgUs, maxUs, lastUs uint64) {
	count = n.Load()
	sum := sumNS.Load()
	max := maxNS.Load()
	last := lastNS.Load()
	if count > 0 {
		avgUs = (sum / count) / 1000
	}
	return count, avgUs, max / 1000, last / 1000
}
