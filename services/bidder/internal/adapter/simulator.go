package adapter

import "github.com/dooh-dsp/bidder/internal/openrtb"

type SimulatorAdapter struct{}

func (SimulatorAdapter) Name() string { return "simulator" }

func (SimulatorAdapter) Auth() AuthConfig {
	return AuthConfig{Mode: "none"}
}

func (SimulatorAdapter) Normalize(req *openrtb.BidRequest) CanonicalImp {
	out := CanonicalImp{Req: req, Qty: 1, Country: req.Device.Geo.Country}
	if req.Dooh != nil {
		out.VenueTypes = req.Dooh.VenueType
		out.DoohID = req.Dooh.ID
	}
	out.Lat = req.Device.Geo.Lat
	out.Lon = req.Device.Geo.Lon
	if len(req.Imp) > 0 {
		out.W, out.H = sizeOf(req.Imp[0])
		out.Floor = req.Imp[0].BidFloor
		out.Qty = qtyOf(req.Imp[0])
	}
	return out
}

func (SimulatorAdapter) MapCreative(dspCreativeID string, sspAssetID string) string {
	if sspAssetID != "" {
		return sspAssetID
	}
	return dspCreativeID
}
