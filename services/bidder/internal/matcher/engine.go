package matcher

import (
	"math"
	"math/bits"
	"strconv"
	"sync"

	"github.com/dooh-dsp/bidder/internal/adapter"
	"github.com/dooh-dsp/bidder/internal/budget"
	"github.com/dooh-dsp/bidder/internal/snapshot"
)

// Engine is a snapshot compiled for the bid path: inverted bitset indexes
// over campaigns plus pre-rendered response fragments. It is immutable once
// built and swapped atomically, so the hot path takes no locks.
//
// Match ANDs one bitset per targeting dimension (geo cell, venue, country,
// daypart hour, creative size) 64 campaigns per instruction, then runs the
// exact checks only on survivors in campaign order. Results are identical to
// the linear Match (see the differential test), which stays as the oracle.
type Engine struct {
	Snap  *snapshot.RulesSnapshot
	bud   *budget.Cache
	words int
	slots []*budget.Slot

	anyVenue   bitset
	venue      map[string]bitset
	anyCountry bitset
	country    map[string]bitset
	daypart    [168]bitset
	hasCreat   bitset
	size       map[uint64]bitset
	geoWide    bitset
	geo        map[int64]bitset

	frags   []campaignFrags
	scratch sync.Pool // []uint64 of len words, for snapshots over stackWords
}

type bitset []uint64

// Geo grid: 0.25° cells (~28km N-S). Campaign bboxes spanning more cells than
// geoMaxCells go in geoWide and rely on the exact bbox check.
const (
	geoCellsPerDeg = 4
	geoMaxCells    = 4096
	stackWords     = 64 // up to 4096 campaigns matched with no heap scratch
)

func geoKey(lat, lon float64) int64 {
	return int64(math.Floor(lat*geoCellsPerDeg))<<32 | int64(uint32(int32(math.Floor(lon*geoCellsPerDeg))))
}

// Compile builds an Engine. ad maps creative IDs to SSP asset IDs and
// noticeBase prefixes win/billing notice URLs. Runs off the bid path.
func Compile(snap *snapshot.RulesSnapshot, ad adapter.SspAdapter, bud *budget.Cache, noticeBase string) *Engine {
	n := len(snap.Campaigns)
	w := (n + 63) / 64
	e := &Engine{
		Snap: snap, bud: bud, words: w,
		slots:      make([]*budget.Slot, n),
		anyVenue:   make(bitset, w),
		venue:      map[string]bitset{},
		anyCountry: make(bitset, w),
		country:    map[string]bitset{},
		hasCreat:   make(bitset, w),
		size:       map[uint64]bitset{},
		geoWide:    make(bitset, w),
		geo:        map[int64]bitset{},
		frags:      make([]campaignFrags, n),
	}
	e.scratch.New = func() any { s := make([]uint64, w); return &s }
	for h := range e.daypart {
		e.daypart[h] = make(bitset, w)
	}
	set := func(m map[string]bitset, k string, i int) {
		b := m[k]
		if b == nil {
			b = make(bitset, w)
			m[k] = b
		}
		b.set(i)
	}
	for i := range snap.Campaigns {
		c := &snap.Campaigns[i]
		e.slots[i] = bud.Slot(c.ID)

		if len(c.VenueSet) == 0 {
			e.anyVenue.set(i)
		}
		for v := range c.VenueSet {
			set(e.venue, v, i)
		}
		if len(c.CountrySet) == 0 {
			e.anyCountry.set(i)
		}
		for co := range c.CountrySet {
			set(e.country, co, i)
		}
		for h := 0; h < 168; h++ {
			// Missing daypart bytes mean "not allowed" (the linear path
			// would index out of range on a truncated bitmap).
			if len(c.Daypart) == 0 || (h/8 < len(c.Daypart) && c.Daypart[h/8]&(1<<uint(h%8)) != 0) {
				e.daypart[h].set(i)
			}
		}
		if len(c.Creatives) > 0 {
			e.hasCreat.set(i)
		}
		for wh := range c.CreativeByWH {
			b := e.size[wh]
			if b == nil {
				b = make(bitset, w)
				e.size[wh] = b
			}
			b.set(i)
		}
		e.indexGeo(c, i)
		e.frags[i] = renderCampaign(c, ad, noticeBase)
	}
	return e
}

func (e *Engine) indexGeo(c *snapshot.Campaign, i int) {
	if c.MinLat > c.MaxLat || c.MinLon > c.MaxLon {
		return // empty box: never matches
	}
	la0, la1 := math.Floor(c.MinLat*geoCellsPerDeg), math.Floor(c.MaxLat*geoCellsPerDeg)
	lo0, lo1 := math.Floor(c.MinLon*geoCellsPerDeg), math.Floor(c.MaxLon*geoCellsPerDeg)
	if (la1-la0+1)*(lo1-lo0+1) > geoMaxCells {
		e.geoWide.set(i)
		return
	}
	for la := la0; la <= la1; la++ {
		for lo := lo0; lo <= lo1; lo++ {
			k := int64(la)<<32 | int64(uint32(int32(lo)))
			b := e.geo[k]
			if b == nil {
				b = make(bitset, e.words)
				e.geo[k] = b
			}
			b.set(i)
		}
	}
}

func (b bitset) set(i int) { b[i>>6] |= 1 << uint(i&63) }

// Match picks the best eligible campaign for imp at London hour-of-week
// hourIdx (Sunday=0). Same eligibility, scoring and tie-break as Match.
func (e *Engine) Match(imp adapter.CanonicalImp, hourIdx int) Result {
	if e == nil || len(e.Snap.Campaigns) == 0 || !e.bud.Ready() {
		return Result{NoBidReason: 2}
	}
	switch imp.Country {
	case "GBR", "UK":
		imp.Country = "GB"
	case "IRL":
		imp.Country = "IE"
	}

	var sizeB bitset
	if imp.W == 0 && imp.H == 0 {
		sizeB = e.hasCreat
	} else if sizeB = e.size[uint64(imp.W)<<32|uint64(uint32(imp.H))]; sizeB == nil {
		return Result{NoBidReason: 2}
	}
	var countryB bitset
	if imp.Country != "" {
		countryB = e.country[imp.Country] // nil: only "any country" campaigns
	}
	geoB := e.geo[geoKey(imp.Lat, imp.Lon)]
	if hourIdx < 0 || hourIdx >= 168 {
		hourIdx = 0
	}
	dayB := e.daypart[hourIdx]

	// Venue bitsets for each request venue and its dotted prefixes
	// ("transit.rail.underground" also matches "transit.rail" and "transit").
	var venueBuf [16]bitset
	venues := venueBuf[:0]
	for _, v := range imp.VenueTypes {
		if b := e.venue[v]; b != nil {
			venues = append(venues, b)
		}
		for j := 0; j < len(v); j++ {
			if v[j] == '.' {
				if b := e.venue[v[:j]]; b != nil {
					venues = append(venues, b)
				}
			}
		}
	}

	var stack [stackWords]uint64
	var acc []uint64
	if e.words <= stackWords {
		acc = stack[:e.words]
	} else {
		p := e.scratch.Get().(*[]uint64)
		defer e.scratch.Put(p)
		acc = *p
	}
	nonzero := false
	for w := range acc {
		x := e.anyVenue[w]
		for _, vb := range venues {
			x |= vb[w]
		}
		g := e.geoWide[w]
		if geoB != nil {
			g |= geoB[w]
		}
		x &= g & dayB[w] & sizeB[w]
		if imp.Country != "" {
			cm := e.anyCountry[w]
			if countryB != nil {
				cm |= countryB[w]
			}
			x &= cm
		}
		acc[w] = x
		nonzero = nonzero || x != 0
	}
	if !nonzero {
		return Result{NoBidReason: 2}
	}

	wh := uint64(imp.W)<<32 | uint64(uint32(imp.H))
	best, bestCr := -1, (*snapshot.CreativeRef)(nil)
	bestScore := -1.0
	for w, x := range acc {
		for x != 0 {
			i := w<<6 | bits.TrailingZeros64(x)
			x &= x - 1
			c := &e.Snap.Campaigns[i]
			if imp.Lat < c.MinLat || imp.Lat > c.MaxLat || imp.Lon < c.MinLon || imp.Lon > c.MaxLon {
				continue
			}
			if rem := e.slots[i].Load(); rem == budget.Unknown || rem <= 0 {
				continue
			}
			cr := creativeOK(c, wh, imp.W, imp.H)
			if cr == nil {
				continue
			}
			price := c.ShadedCPM
			if price < imp.Floor {
				price = imp.Floor
			}
			if score := price + float64(c.Priority); score > bestScore {
				bestScore, best, bestCr = score, i, cr
			}
		}
	}
	if best < 0 {
		return Result{NoBidReason: 2}
	}
	c := &e.Snap.Campaigns[best]
	qty := imp.Qty
	if qty <= 0 {
		qty = 1
	}
	price := c.ShadedCPM
	if price < imp.Floor {
		price = imp.Floor
	}
	return Result{
		Campaign:    c,
		Creative:    bestCr,
		Price:       price,
		Qty:         qty,
		SpendMicros: int64(price * 1_000_000.0 * qty / 1000.0),
		index:       best,
	}
}

// Spend deducts a bid locally from its campaign's budget counter.
func (e *Engine) Spend(r Result) {
	if r.Campaign != nil {
		budget.Spend(e.slots[r.index], r.SpendMicros)
	}
}

// campaignFrags are the constant pieces of a bid response for one campaign,
// rendered once per snapshot so a bid is a handful of appends.
type campaignFrags struct {
	head      []byte // ,"cur":..,"seatbid":[{"seat":..,"bid":[{"id":"
	idSuffix  []byte // -<cid>","impid":
	creatives map[*snapshot.CreativeRef]*creativeFrags
}

type creativeFrags struct {
	nurl []byte // ,"adm":..,"nurl":"<base>/nurl?id=
	burl []byte // &price=${AUCTION_PRICE}","burl":"<base>/burl?id=
	tail []byte // &price=${AUCTION_PRICE}","crid":..,"cid":..,"w":..,"h":..,"adomain":["dooh.local"]}]}]}
}

func renderCampaign(c *snapshot.Campaign, ad adapter.SspAdapter, base string) campaignFrags {
	cid := strconv.FormatUint(uint64(c.ID), 10)
	var head []byte
	if c.Currency != "" {
		head = append(head, `,"cur":`...)
		head = appendJSONString(head, c.Currency)
	}
	head = append(head, `,"seatbid":[{"seat":`...)
	head = appendJSONString(head, c.Seat)
	head = append(head, `,"bid":[{"id":"`...)
	f := campaignFrags{
		head:      head,
		idSuffix:  []byte(`-` + cid + `","impid":`),
		creatives: make(map[*snapshot.CreativeRef]*creativeFrags, len(c.Creatives)),
	}
	for j := range c.Creatives {
		cr := &c.Creatives[j]
		cf := &creativeFrags{}
		cf.nurl = append(cf.nurl, `,"adm":`...)
		cf.nurl = appendJSONString(cf.nurl, cr.CDNURL)
		cf.nurl = append(cf.nurl, `,"nurl":"`...)
		cf.nurl = appendJSONInner(cf.nurl, base+"/nurl?id=")
		cf.burl = append(cf.burl, `&price=${AUCTION_PRICE}","burl":"`...)
		cf.burl = appendJSONInner(cf.burl, base+"/burl?id=")
		cf.tail = append(cf.tail, `&price=${AUCTION_PRICE}","crid":`...)
		cf.tail = appendJSONString(cf.tail, ad.MapCreative(snapshot.IDString(cr.ID), cr.SSPAssetID))
		cf.tail = append(cf.tail, `,"cid":`...)
		cf.tail = appendJSONString(cf.tail, cid)
		cf.tail = append(cf.tail, `,"w":`...)
		cf.tail = strconv.AppendInt(cf.tail, int64(cr.Width), 10)
		cf.tail = append(cf.tail, `,"h":`...)
		cf.tail = strconv.AppendInt(cf.tail, int64(cr.Height), 10)
		cf.tail = append(cf.tail, `,"adomain":["dooh.local"]}]}]}`...)
		f.creatives[cr] = cf
	}
	return f
}

// AppendBid renders the bid response for r into dst without allocating.
func (e *Engine) AppendBid(dst []byte, reqID, impID string, r Result) []byte {
	f := &e.frags[r.index]
	cf := f.creatives[r.Creative]
	if impID == "" {
		impID = "1"
	}
	dst = append(dst, `{"id":`...)
	dst = appendJSONString(dst, reqID)
	dst = append(dst, f.head...)
	dst = appendJSONInner(dst, reqID)
	dst = append(dst, f.idSuffix...)
	dst = appendJSONString(dst, impID)
	dst = append(dst, `,"price":`...)
	dst = strconv.AppendFloat(dst, r.Price, 'f', 4, 64)
	dst = append(dst, cf.nurl...)
	dst = appendQueryEscaped(dst, reqID)
	dst = append(dst, cf.burl...)
	dst = appendQueryEscaped(dst, reqID)
	dst = append(dst, cf.tail...)
	return dst
}

// AppendNoBid renders {"id":..,"nbr":n}.
func AppendNoBid(dst []byte, reqID string, nbr int) []byte {
	dst = append(dst, `{"id":`...)
	dst = appendJSONString(dst, reqID)
	dst = append(dst, `,"nbr":`...)
	dst = strconv.AppendInt(dst, int64(nbr), 10)
	return append(dst, '}')
}

const hexDigits = "0123456789abcdef"

func appendJSONString(dst []byte, s string) []byte {
	dst = append(dst, '"')
	dst = appendJSONInner(dst, s)
	return append(dst, '"')
}

// appendJSONInner escapes s for the inside of a JSON string literal. Bytes
// >= 0x80 pass through (valid UTF-8 is valid JSON).
func appendJSONInner(dst []byte, s string) []byte {
	start := 0
	for i := 0; i < len(s); i++ {
		c := s[i]
		if c >= 0x20 && c != '"' && c != '\\' {
			continue
		}
		dst = append(dst, s[start:i]...)
		switch c {
		case '"', '\\':
			dst = append(dst, '\\', c)
		case '\n':
			dst = append(dst, '\\', 'n')
		case '\r':
			dst = append(dst, '\\', 'r')
		case '\t':
			dst = append(dst, '\\', 't')
		default:
			dst = append(dst, '\\', 'u', '0', '0', hexDigits[c>>4], hexDigits[c&0xF])
		}
		start = i + 1
	}
	return append(dst, s[start:]...)
}

// appendQueryEscaped percent-encodes s for a URL query value. The output is
// plain ASCII with no characters that need JSON escaping.
func appendQueryEscaped(dst []byte, s string) []byte {
	for i := 0; i < len(s); i++ {
		c := s[i]
		if ('a' <= c && c <= 'z') || ('A' <= c && c <= 'Z') || ('0' <= c && c <= '9') || c == '-' || c == '_' || c == '.' || c == '~' {
			dst = append(dst, c)
			continue
		}
		dst = append(dst, '%', "0123456789ABCDEF"[c>>4], "0123456789ABCDEF"[c&0xF])
	}
	return dst
}
