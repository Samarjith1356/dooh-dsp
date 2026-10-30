package lat

import "testing"

func TestBucketsCoverValues(t *testing.T) {
	for _, v := range []uint64{0, 1, 7, 8, 9, 15, 16, 17, 1000, 41_000, 999_999, 1 << 40} {
		b := bucketOf(v)
		if ub := upperBound(b); ub < v || (b > 0 && upperBound(b-1) >= v) {
			t.Fatalf("v=%d bucket %d ub %d prev %d", v, b, ub, upperBound(b-1))
		}
	}
}

func TestPercentiles(t *testing.T) {
	var r Recorder
	for i := 0; i < 990; i++ {
		r.Observe(40_000) // 40µs
	}
	for i := 0; i < 10; i++ {
		r.Observe(2_000_000) // 2ms tail
	}
	s := r.Stats()
	if s.P50 < 40 || s.P50 > 45 {
		t.Fatalf("p50 %d", s.P50)
	}
	if s.P999 < 2000 || s.WindowMaxUs != 2000 || s.MaxUs != 2000 {
		t.Fatalf("p999 %d max %d", s.P999, s.WindowMaxUs)
	}
	r.rotate()
	r.rotate()
	if s := r.Stats(); s.WindowN != 0 || s.Count != 1000 {
		t.Fatalf("after rotation %+v", s)
	}
}
