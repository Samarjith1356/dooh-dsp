package openrtb

import (
	"encoding/json"
	"testing"
)

func TestEscapesDecoded(t *testing.T) {
	raw := []byte(`{"id":"a\"b\\c\/d\n\té😀","imp":[{"id":"1"}],"dooh":{"id":"x"}}`)
	var req BidRequest
	if err := UnmarshalBid(raw, &req); err != nil {
		t.Fatal(err)
	}
	var want struct{ ID string }
	_ = json.Unmarshal(raw, &want)
	if req.ID != want.ID {
		t.Fatalf("got %q want %q", req.ID, want.ID)
	}
}

func TestDoohExtCapturedAndSecondImpIgnored(t *testing.T) {
	raw := []byte(`{"id":"v","imp":[{"id":"1","banner":{"w":1920,"h":1080},"qty":{"multiplier":3}},{"id":"2","banner":{"w":1,"h":1},"qty":{"multiplier":99}}],"dooh":{"id":"d","venuetype":["roadside"],"ext":{"screenid":"scr-9","venuetype":"transit.rail"}},"device":{"geo":{"lat":1,"lon":2,"country":"GB"}}}`)
	var req BidRequest
	if err := UnmarshalBid(raw, &req); err != nil {
		t.Fatal(err)
	}
	if len(req.Imp) != 1 || req.Imp[0].Banner.W != 1920 || req.Imp[0].Qty.Multiplier != 3 {
		t.Fatalf("imp %+v banner %+v qty %+v", req.Imp, req.Imp[0].Banner, req.Imp[0].Qty)
	}
	v, ok := ExtString(req.Dooh.Ext, "screenid")
	if !ok || string(v) != "scr-9" {
		t.Fatalf("ext %s", req.Dooh.Ext)
	}
	if v, ok := ExtString(req.Dooh.Ext, "venuetype"); !ok || string(v) != "transit.rail" {
		t.Fatal("venuetype ext")
	}
	if _, ok := ExtString(req.Dooh.Ext, "missing"); ok {
		t.Fatal("missing key found")
	}
}

func TestPooledReuseDoesNotLeak(t *testing.T) {
	var req BidRequest
	a := []byte(`{"id":"a","imp":[{"id":"1","banner":{"w":1920,"h":1080},"qty":{"multiplier":5}}],"dooh":{"id":"d","venuetype":["roadside","transit"]}}`)
	b := []byte(`{"id":"b","imp":[{"id":"2"}],"dooh":{"id":"e"}}`)
	if err := UnmarshalBid(a, &req); err != nil {
		t.Fatal(err)
	}
	if err := UnmarshalBid(b, &req); err != nil {
		t.Fatal(err)
	}
	if req.Imp[0].Banner != nil || req.Imp[0].Qty != nil || len(req.Dooh.VenueType) != 0 || req.ID != "b" {
		t.Fatalf("stale state %+v %+v", req.Imp[0], req.Dooh)
	}
}

func TestFastParseAllocs(t *testing.T) {
	raw := []byte(`{"id":"sim-1","imp":[{"id":"1","banner":{"w":1920,"h":1080},"bidfloor":4.1,"qty":{"multiplier":22.0,"sourcetype":1,"vendor":"viooh.com"}}],"dooh":{"id":"jcd-rd-001","name":"x","venuetype":["roadside.billboard","roadside"],"venuetypetax":1},"device":{"geo":{"lat":51.495,"lon":-0.183,"country":"GB","city":"London"}},"tmax":100,"at":1,"cur":["GBP"],"test":1}`)
	var req BidRequest
	_ = UnmarshalBid(raw, &req) // warm the intern table
	n := testing.AllocsPerRun(1000, func() { _ = UnmarshalBid(raw, &req) })
	if n > 1 {
		t.Fatalf("allocs per parse = %v, want <= 1 (request ID)", n)
	}
}

func BenchmarkUnmarshalBid(b *testing.B) {
	raw := []byte(`{"id":"sim-1","imp":[{"id":"1","banner":{"w":1920,"h":1080},"bidfloor":4.1,"qty":{"multiplier":22.0,"sourcetype":1,"vendor":"viooh.com"}}],"dooh":{"id":"jcd-rd-001","name":"x","venuetype":["roadside.billboard","roadside"],"venuetypetax":1},"device":{"geo":{"lat":51.495,"lon":-0.183,"country":"GB","city":"London"}},"tmax":100,"at":1,"cur":["GBP"],"test":1}`)
	var req BidRequest
	b.ReportAllocs()
	b.SetBytes(int64(len(raw)))
	for i := 0; i < b.N; i++ {
		_ = UnmarshalBid(raw, &req)
	}
}
