package adapter

import (
	"encoding/json"
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
		var ext map[string]any
		if json.Unmarshal(req.Dooh.Ext, &ext) == nil {
			if v, ok := ext["screenid"].(string); ok && sim.DoohID == "" {
				sim.DoohID = v
			}
			if v, ok := ext["venuetype"].(string); ok {
				sim.VenueTypes = append(sim.VenueTypes, v)
			}
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
