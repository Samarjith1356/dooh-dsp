package openrtb

import "encoding/json"

type BidRequest struct {
	ID     string          `json:"id"`
	Imp    []Imp           `json:"imp"`
	Site   json.RawMessage `json:"site,omitempty"`
	App    json.RawMessage `json:"app,omitempty"`
	Dooh   *Dooh           `json:"dooh,omitempty"`
	Device Device          `json:"device"`
	TMax   int             `json:"tmax"`
	AT     int             `json:"at"`
	Cur    []string        `json:"cur"`
	WSeat  []string        `json:"wseat"`
	Test   int             `json:"test"`
	Ext    json.RawMessage `json:"ext,omitempty"`
}

type Dooh struct {
	ID           string          `json:"id"`
	Name         string          `json:"name"`
	VenueType    []string        `json:"venuetype"`
	VenueTypeTax int             `json:"venuetypetax"`
	Publisher    json.RawMessage `json:"publisher,omitempty"`
	Ext          json.RawMessage `json:"ext,omitempty"`
}

type Imp struct {
	ID          string          `json:"id"`
	Banner      *Banner         `json:"banner,omitempty"`
	Video       *Video          `json:"video,omitempty"`
	BidFloor    float64         `json:"bidfloor"`
	BidFloorCur string          `json:"bidfloorcur"`
	Qty         *Qty            `json:"qty,omitempty"`
	Ext         json.RawMessage `json:"ext,omitempty"`
}

type Banner struct {
	W int `json:"w"`
	H int `json:"h"`
}

type Video struct {
	W           int `json:"w"`
	H           int `json:"h"`
	MinDuration int `json:"minduration"`
	MaxDuration int `json:"maxduration"`
}

type Qty struct {
	Multiplier float64 `json:"multiplier"`
	SourceType int     `json:"sourcetype"`
	Vendor     string  `json:"vendor"`
}

type Device struct {
	Geo Geo `json:"geo"`
}

type Geo struct {
	Lat     float64 `json:"lat"`
	Lon     float64 `json:"lon"`
	Country string  `json:"country"`
	Region  string  `json:"region"`
	City    string  `json:"city"`
}

type BidResponse struct {
	ID      string    `json:"id"`
	Cur     string    `json:"cur,omitempty"`
	SeatBid []SeatBid `json:"seatbid,omitempty"`
	Nbr     int       `json:"nbr,omitempty"`
}

type SeatBid struct {
	Seat string `json:"seat"`
	Bid  []Bid  `json:"bid"`
}

type Bid struct {
	ID      string   `json:"id"`
	ImpID   string   `json:"impid"`
	Price   float64  `json:"price"`
	AdM     string   `json:"adm,omitempty"`
	NURL    string   `json:"nurl,omitempty"`
	BURL    string   `json:"burl,omitempty"`
	LURL    string   `json:"lurl,omitempty"`
	CrID    string   `json:"crid"`
	CID     string   `json:"cid"`
	W       int      `json:"w,omitempty"`
	H       int      `json:"h,omitempty"`
	Adomain []string `json:"adomain,omitempty"`
}

func IsDOOH(req *BidRequest) bool {
	return req.Dooh != nil && len(req.Site) == 0 && len(req.App) == 0
}
