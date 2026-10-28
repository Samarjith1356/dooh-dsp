package budget

import "testing"

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
