package notice

import (
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"math"
	"net/url"
	"strconv"
	"strings"
)

var (
	ErrBadSignature  = errors.New("bad signature")
	ErrBadPrice      = errors.New("bad price")
	ErrPriceAboveBid = errors.New("price above bid")
)

// Params are the signed notice fields (everything except s and p).
type Params struct {
	BidRequestID string
	ImpID        string
	AdvertiserID uint32
	CampaignID   uint32
	CreativeID   uint32
	Multiplier   float64
	BidCPM       float64
	Currency     string
}

// SpendMicros is the billing formula: round(price_cpm * multiplier * 1000).
func SpendMicros(priceCPM, multiplier float64) int64 {
	return int64(math.Round(priceCPM * multiplier * 1000.0))
}

func formatFloat(v float64) string {
	return strconv.FormatFloat(v, 'f', -1, 64)
}

func appendCanonical(dst []byte, p Params) []byte {
	dst = append(dst, "r="...)
	dst = append(dst, p.BidRequestID...)
	dst = append(dst, "&i="...)
	dst = append(dst, p.ImpID...)
	dst = append(dst, "&a="...)
	dst = strconv.AppendUint(dst, uint64(p.AdvertiserID), 10)
	dst = append(dst, "&c="...)
	dst = strconv.AppendUint(dst, uint64(p.CampaignID), 10)
	dst = append(dst, "&cr="...)
	dst = strconv.AppendUint(dst, uint64(p.CreativeID), 10)
	dst = append(dst, "&q="...)
	dst = strconv.AppendFloat(dst, p.Multiplier, 'f', -1, 64)
	dst = append(dst, "&b="...)
	dst = strconv.AppendFloat(dst, p.BidCPM, 'f', -1, 64)
	dst = append(dst, "&cur="...)
	dst = append(dst, p.Currency...)
	return dst
}

// Sign returns the first 32 hex characters of HMAC-SHA256 over the canonical params.
func Sign(key string, p Params) string {
	mac := hmac.New(sha256.New, []byte(key))
	var buf [192]byte
	payload := appendCanonical(buf[:0], p)
	_, _ = mac.Write(payload)
	sum := hex.EncodeToString(mac.Sum(nil))
	if len(sum) > 32 {
		return sum[:32]
	}
	return sum
}

// BuildURLs builds nurl/burl/lurl with one shared signature (path is not signed).
func BuildURLs(base, key string, p Params) (nurl, burl, lurl string) {
	base = strings.TrimRight(base, "/")
	sig := Sign(key, p)
	q := appendCanonical(make([]byte, 0, 192), p)
	q = append(q, "&s="...)
	q = append(q, sig...)
	q = append(q, "&p=${AUCTION_PRICE}"...)
	qs := string(q)
	return base + "/nurl?" + qs, base + "/burl?" + qs, base + "/lurl?" + qs
}

// BuildURL builds a single notice URL with p=${AUCTION_PRICE}.
func BuildURL(base, path, key string, p Params) string {
	base = strings.TrimRight(base, "/")
	if !strings.HasPrefix(path, "/") {
		path = "/" + path
	}
	n, b, l := BuildURLs(base, key, p)
	switch path {
	case "/nurl":
		return n
	case "/burl":
		return b
	case "/lurl":
		return l
	default:
		return base + path + "?" + string(appendCanonical(nil, p)) + "&s=" + Sign(key, p) + "&p=${AUCTION_PRICE}"
	}
}

// ParseAndVerify checks signature and price. Returns params, clearing price, or an error.
func ParseAndVerify(key string, q url.Values) (Params, float64, error) {
	p := Params{
		BidRequestID: q.Get("r"),
		ImpID:        q.Get("i"),
		Currency:     q.Get("cur"),
	}
	if a, err := strconv.ParseUint(q.Get("a"), 10, 32); err == nil {
		p.AdvertiserID = uint32(a)
	}
	if c, err := strconv.ParseUint(q.Get("c"), 10, 32); err == nil {
		p.CampaignID = uint32(c)
	}
	if cr, err := strconv.ParseUint(q.Get("cr"), 10, 32); err == nil {
		p.CreativeID = uint32(cr)
	}
	if mult, err := strconv.ParseFloat(q.Get("q"), 64); err == nil {
		p.Multiplier = mult
	}
	if bid, err := strconv.ParseFloat(q.Get("b"), 64); err == nil {
		p.BidCPM = bid
	}

	want := Sign(key, p)
	got := q.Get("s")
	if got == "" || !hmac.Equal([]byte(got), []byte(want)) {
		return p, 0, ErrBadSignature
	}

	rawP := q.Get("p")
	if rawP == "" {
		return p, 0, ErrBadPrice
	}
	price, err := strconv.ParseFloat(rawP, 64)
	if err != nil {
		return p, 0, ErrBadPrice
	}
	if price > p.BidCPM {
		return p, price, ErrPriceAboveBid
	}
	return p, price, nil
}
