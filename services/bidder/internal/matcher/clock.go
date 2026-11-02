package matcher

import (
	"sync/atomic"
	"time"
)

var london = func() *time.Location {
	loc, err := time.LoadLocation("Europe/London")
	if err != nil {
		return time.UTC
	}
	return loc
}()

type hourWindow struct {
	from, until int64 // unix nanos, [from, until)
	idx         int
}

var hourCache atomic.Pointer[hourWindow]

// HourIndex returns the Europe/London hour-of-week (Sunday=0) for now. The
// timezone conversion runs once per hour; every other call is an atomic load
// and two compares. London offsets are whole hours, so local hour boundaries
// fall on UTC hour boundaries and DST changes are handled exactly.
func HourIndex(now time.Time) int {
	ns := now.UnixNano()
	if w := hourCache.Load(); w != nil && ns >= w.from && ns < w.until {
		return w.idx
	}
	t := now.In(london)
	into := time.Duration(t.Minute())*time.Minute + time.Duration(t.Second())*time.Second + time.Duration(t.Nanosecond())
	w := &hourWindow{from: ns - int64(into), idx: int(t.Weekday())*24 + t.Hour()}
	w.until = w.from + int64(time.Hour)
	hourCache.Store(w)
	return w.idx
}
