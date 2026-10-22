package adapter

import "github.com/dooh-dsp/bidder/internal/openrtb"

type CanonicalImp struct {
	Req          *openrtb.BidRequest
	VenueTypes   []string
	Lat          float64
	Lon          float64
	Country      string
	W            int
	H            int
	Floor        float64
	Qty          float64
	DoohID       string
	SSPAssetHint string
}

type AuthConfig struct {
	Mode     string
	Token    string
	CertFile string
	KeyFile  string
}

type SspAdapter interface {
	Name() string
	Auth() AuthConfig
	Normalize(req *openrtb.BidRequest) CanonicalImp
	MapCreative(dspCreativeID string, sspAssetID string) string
}

func New(name string) SspAdapter {
	switch name {
	case "viooh":
		return VioohAdapter{}
	default:
		return SimulatorAdapter{}
	}
}

func sizeOf(imp openrtb.Imp) (int, int) {
	if imp.Banner != nil {
		return imp.Banner.W, imp.Banner.H
	}
	if imp.Video != nil {
		return imp.Video.W, imp.Video.H
	}
	return 0, 0
}

func qtyOf(imp openrtb.Imp) float64 {
	if imp.Qty != nil && imp.Qty.Multiplier > 0 {
		return imp.Qty.Multiplier
	}
	return 1
}
