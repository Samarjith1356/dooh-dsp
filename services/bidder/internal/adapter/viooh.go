package adapter

import (
	"os"

	"github.com/dooh-dsp/bidder/internal/openrtb"
)

// VioohAdapter maps VIOOH/JCDecaux extension fields onto CanonicalImp.
// Live mTLS/HMAC is configured via env; matching stays adapter-agnostic.
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
	if req.Dooh != nil && req.Dooh.Ext != nil {
		if v, ok := req.Dooh.Ext["screenid"].(string); ok && sim.DoohID == "" {
			sim.DoohID = v
		}
		if v, ok := req.Dooh.Ext["venuetype"].(string); ok {
			sim.VenueTypes = append(sim.VenueTypes, v)
		}
	}
	if req.Ext != nil {
		if v, ok := req.Ext["viooh"].(map[string]any); ok {
			if deal, ok := v["deal_id"].(string); ok {
				if sim.Req.Ext == nil {
					sim.Req.Ext = map[string]any{}
				}
				sim.Req.Ext["deal_id"] = deal
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
