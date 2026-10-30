package adapter

import (
	"os"

	"github.com/dooh-dsp/bidder/internal/openrtb"
)

type VioohAdapter struct{}

func (VioohAdapter) Name() string { return "viooh" }

func (VioohAdapter) Auth() AuthConfig {
	return AuthConfig{
		Mode:     "mtls",
		Token:    os.Getenv("VIOOH_API_TOKEN"),
		CertFile: os.Getenv("VIOOH_TLS_CERT"),
		KeyFile:  os.Getenv("VIOOH_TLS_KEY"),
	}
}

func (a VioohAdapter) Normalize(req *openrtb.BidRequest) CanonicalImp {
	sim := SimulatorAdapter{}.Normalize(req)
	if req.Dooh != nil && len(req.Dooh.Ext) > 0 {
		if v, ok := openrtb.ExtString(req.Dooh.Ext, "screenid"); ok && sim.DoohID == "" {
			sim.DoohID = string(v)
		}
		if v, ok := openrtb.ExtString(req.Dooh.Ext, "venuetype"); ok && len(v) > 0 {
			// Copy: never append into the request's pooled venue slice.
			venues := make([]string, 0, len(sim.VenueTypes)+1)
			sim.VenueTypes = append(append(venues, sim.VenueTypes...), string(v))
		}
	}
	if sim.Country == "UK" {
		sim.Country = "GB"
	}
	return sim
}

func (VioohAdapter) MapCreative(dspCreativeID string, sspAssetID string) string {
	if sspAssetID != "" {
		return sspAssetID
	}
	return "viooh-" + dspCreativeID
}
