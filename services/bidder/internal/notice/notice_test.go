package notice

import (
	"math"
	"net/url"
	"strings"
	"testing"
)

func sample() (string, Params) {
	return "test-signing-key-at-least-32-bytes!!", Params{
		BidRequestID: "req-1",
		ImpID:        "1",
		AdvertiserID: 7,
		CampaignID:   3,
		CreativeID:   9,
		Multiplier:   5.2,
		BidCPM:       10.0,
		Currency:     "GBP",
	}
}

func TestSignAndVerify(t *testing.T) {
	key, p := sample()
	nurl, burl, lurl := BuildURLs("http://bidder:8081", key, p)
	for _, u := range []string{nurl, burl, lurl} {
		if !strings.Contains(u, "p=${AUCTION_PRICE}") {
			t.Fatalf("missing macro: %s", u)
		}
	}
	raw := strings.Replace(burl, "${AUCTION_PRICE}", "9.5", 1)
	parsed, err := url.Parse(raw)
	if err != nil {
		t.Fatal(err)
	}
	got, price, err := ParseAndVerify(key, parsed.Query())
	if err != nil {
		t.Fatalf("verify: %v", err)
	}
	if price != 9.5 {
		t.Fatalf("price %v", price)
	}
	if got.CampaignID != 3 || got.Multiplier != 5.2 {
		t.Fatalf("params %+v", got)
	}
	// Same signature on all three paths (path is not signed).
	if !strings.Contains(nurl, "&s=") || strings.Split(nurl, "&s=")[1] != strings.Split(burl, "&s=")[1] {
		t.Fatalf("nurl/burl signatures should match")
	}
}

func TestRejectBadSignature(t *testing.T) {
	key, p := sample()
	u := BuildURL("http://bidder:8081", "/burl", key, p)
	raw := strings.Replace(u, "${AUCTION_PRICE}", "9.5", 1)
	parsed, _ := url.Parse(raw)
	q := parsed.Query()
	q.Set("s", "00000000000000000000000000000000")
	if _, _, err := ParseAndVerify(key, q); err != ErrBadSignature {
		t.Fatalf("want ErrBadSignature got %v", err)
	}
}

func TestRejectPriceAboveBid(t *testing.T) {
	key, p := sample()
	u := BuildURL("http://bidder:8081", "/burl", key, p)
	raw := strings.Replace(u, "${AUCTION_PRICE}", "10.01", 1)
	parsed, _ := url.Parse(raw)
	if _, price, err := ParseAndVerify(key, parsed.Query()); err != ErrPriceAboveBid {
		t.Fatalf("want ErrPriceAboveBid got %v price %v", err, price)
	}
}

func TestRejectPriceNaNInfNegativeZero(t *testing.T) {
	key, p := sample()
	u := BuildURL("http://bidder:8081", "/burl", key, p)
	base := strings.Replace(u, "${AUCTION_PRICE}", "PLACEHOLDER", 1)
	cases := []string{
		"NaN",
		"+Inf",
		"-Inf",
		"inf",
		"-1",
		"0",
		"-0",
	}
	for _, rawP := range cases {
		raw := strings.Replace(base, "PLACEHOLDER", rawP, 1)
		parsed, err := url.Parse(raw)
		if err != nil {
			t.Fatalf("parse %q: %v", rawP, err)
		}
		if _, _, err := ParseAndVerify(key, parsed.Query()); err != ErrBadPrice {
			t.Fatalf("price %q: want ErrBadPrice got %v", rawP, err)
		}
	}
	// math.NaN / Inf via strconv already covered; assert helpers too.
	if priceOK(math.NaN()) || priceOK(math.Inf(1)) || priceOK(math.Inf(-1)) || priceOK(0) || priceOK(-0.5) {
		t.Fatal("priceOK should reject NaN/Inf/zero/negative")
	}
	if !priceOK(0.01) {
		t.Fatal("priceOK should accept positive")
	}
}

func TestRejectBadIDs(t *testing.T) {
	key, p := sample()
	u := BuildURL("http://bidder:8081", "/burl", key, p)
	raw := strings.Replace(u, "${AUCTION_PRICE}", "9.5", 1)
	parsed, _ := url.Parse(raw)
	q := parsed.Query()
	q.Set("r", "bad/id")
	if _, _, err := ParseAndVerify(key, q); err != ErrBadID {
		t.Fatalf("want ErrBadID for slash, got %v", err)
	}
	q.Set("r", p.BidRequestID)
	q.Set("i", strings.Repeat("x", 65))
	if _, _, err := ParseAndVerify(key, q); err != ErrBadID {
		t.Fatalf("want ErrBadID for long id, got %v", err)
	}
}

func TestSplitRIFailsVerification(t *testing.T) {
	// Signed as r=ab i=c; presenting as r=a i=bc must fail (query-split attack).
	key := "test-signing-key-at-least-32-bytes!!"
	p := Params{
		BidRequestID: "ab",
		ImpID:        "c",
		AdvertiserID: 1,
		CampaignID:   2,
		CreativeID:   3,
		Multiplier:   1,
		BidCPM:       5,
		Currency:     "GBP",
	}
	u := BuildURL("http://bidder:8081", "/burl", key, p)
	raw := strings.Replace(u, "${AUCTION_PRICE}", "4", 1)
	parsed, _ := url.Parse(raw)
	q := parsed.Query()
	q.Set("r", "a")
	q.Set("i", "bc")
	if _, _, err := ParseAndVerify(key, q); err != ErrBadSignature {
		t.Fatalf("resplit r/i want ErrBadSignature got %v", err)
	}
	// Original split still verifies.
	q.Set("r", "ab")
	q.Set("i", "c")
	if _, _, err := ParseAndVerify(key, q); err != nil {
		t.Fatalf("original: %v", err)
	}
}

func TestValidID(t *testing.T) {
	if !ValidID("req-1._OK") {
		t.Fatal("expected valid")
	}
	for _, s := range []string{"", "a/b", "a&b", "a=b", "a b", strings.Repeat("a", 65)} {
		if ValidID(s) {
			t.Fatalf("%q should be invalid", s)
		}
	}
}

func TestSpendFormulaMultiplier52(t *testing.T) {
	// micros = CPM x multiplier x 1000; 10 * 5.2 * 1000 = 52000
	got := SpendMicros(10.0, 5.2)
	if got != 52000 {
		t.Fatalf("spend %d want 52000", got)
	}
}
