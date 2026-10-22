package snapshot

import (
	"encoding/base64"
	"encoding/json"
	"strconv"
	"sync/atomic"
	"time"
)

type CreativeRef struct {
	ID         uint32 `json:"id"`
	Width      int    `json:"width"`
	Height     int    `json:"height"`
	Mime       string `json:"mime"`
	CDNURL     string `json:"cdn_url"`
	DurationMS int    `json:"duration_ms"`
	SSPAssetID string `json:"ssp_asset_id"`
}

type Shading struct {
	MinCPM      float64 `json:"min_cpm"`
	MaxCPM      float64 `json:"max_cpm"`
	ShadeFactor float64 `json:"shade_factor"`
	PWinBin     float64 `json:"pwin_bin"`
}

type Campaign struct {
	ID            uint32        `json:"id"`
	AdvertiserID  uint32        `json:"advertiser_id"`
	Seat          string        `json:"seat"`
	Priority      int           `json:"priority"`
	BidCPMMicros  int64         `json:"bid_cpm_micros"`
	Shading       Shading       `json:"shading"`
	DaypartBits   string        `json:"daypart_bits"`
	Daypart       []byte        `json:"-"`
	H3Cells       []uint64      `json:"h3_cells"`
	H3Set         map[uint64]struct{} `json:"-"`
	MinLat        float64       `json:"min_lat"`
	MaxLat        float64       `json:"max_lat"`
	MinLon        float64       `json:"min_lon"`
	MaxLon        float64       `json:"max_lon"`
	VenueTypes    []string      `json:"venue_types"`
	VenueSet      map[string]struct{} `json:"-"`
	Creatives     []CreativeRef `json:"creatives"`
	BudgetToken   string        `json:"budget_token"`
	Currency      string        `json:"currency"`
	DealIDs       []string      `json:"deal_ids"`
	Countries     []string      `json:"countries"`
	CountrySet    map[string]struct{} `json:"-"`
}

type RulesSnapshot struct {
	SnapshotID     uint64              `json:"snapshot_id"`
	CompiledAtUnix int64               `json:"compiled_at_unix"`
	Epoch          uint64              `json:"epoch"`
	Campaigns      []Campaign          `json:"campaigns"`
	VenueIndex     map[string][]uint32 `json:"venue_index"`
	H3Index        map[string][]uint32 `json:"h3_index"`
	DealIndex      map[string][]uint32 `json:"deal_index"`
	ByID           map[uint32]*Campaign `json:"-"`
}

type Holder struct {
	cur atomic.Pointer[RulesSnapshot]
}

func (h *Holder) Store(s *RulesSnapshot) {
	prepare(s)
	h.cur.Store(s)
}

func (h *Holder) Load() *RulesSnapshot {
	return h.cur.Load()
}

func Parse(raw []byte) (*RulesSnapshot, error) {
	var s RulesSnapshot
	if err := json.Unmarshal(raw, &s); err != nil {
		return nil, err
	}
	prepare(&s)
	return &s, nil
}

func prepare(s *RulesSnapshot) {
	s.ByID = make(map[uint32]*Campaign, len(s.Campaigns))
	for i := range s.Campaigns {
		c := &s.Campaigns[i]
		c.Daypart, _ = base64.StdEncoding.DecodeString(c.DaypartBits)
		c.VenueSet = make(map[string]struct{}, len(c.VenueTypes))
		for _, v := range c.VenueTypes {
			c.VenueSet[v] = struct{}{}
		}
		c.H3Set = make(map[uint64]struct{}, len(c.H3Cells))
		for _, cell := range c.H3Cells {
			c.H3Set[cell] = struct{}{}
		}
		c.CountrySet = make(map[string]struct{}, len(c.Countries))
		for _, co := range c.Countries {
			c.CountrySet[co] = struct{}{}
		}
		s.ByID[c.ID] = c
	}
}

func DaypartAllows(bits []byte, t time.Time) bool {
	if len(bits) == 0 {
		return true
	}
	idx := int(t.Weekday())*24 + t.Hour()
	if idx < 0 || idx >= 168 {
		return true
	}
	return bits[idx/8]&(1<<uint(idx%8)) != 0
}

func GridCell(lat, lon float64) uint64 {
	return uint64((lat+90)*100)*100000 + uint64((lon+180)*100)
}

func IDString(id uint32) string { return strconv.FormatUint(uint64(id), 10) }
