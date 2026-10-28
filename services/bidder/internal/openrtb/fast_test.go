package openrtb

import "testing"

func TestFastUnmarshalSimulator(t *testing.T) {
	raw := []byte(`{"id":"sim-1","imp":[{"id":"1","banner":{"w":1920,"h":1080},"bidfloor":4.1,"qty":{"multiplier":22.0,"sourcetype":1,"vendor":"viooh.com"}}],"dooh":{"id":"jcd-rd-001","name":"x","venuetype":["roadside.billboard","roadside"],"venuetypetax":1},"device":{"geo":{"lat":51.495,"lon":-0.183,"country":"GB","city":"London"}},"tmax":100,"at":1,"cur":["GBP"],"test":1}`)
	var req BidRequest
	if err := UnmarshalBid(raw, &req); err != nil {
		t.Fatal(err)
	}
	if req.ID != "sim-1" || req.Dooh == nil || req.Dooh.ID != "jcd-rd-001" {
		t.Fatalf("%+v", req)
	}
	if len(req.Dooh.VenueType) != 2 || req.Imp[0].Banner.W != 1920 || req.Imp[0].BidFloor != 4.1 {
		t.Fatalf("imp %+v dooh %+v", req.Imp, req.Dooh)
	}
	if req.Device.Geo.Lat < 51 || req.Device.Geo.Country != "GB" {
		t.Fatalf("geo %+v", req.Device.Geo)
	}
	if !IsDOOH(&req) {
		t.Fatal("expected dooh")
	}
}
