package notice

import (
	"net/url"
	"strings"
	"testing"
)

func sample() (string, Params) {
	return "test-signing-key", Params{
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

func TestSpendFormulaMultiplier52(t *testing.T) {
	// micros = CPM x multiplier x 1000; 10 * 5.2 * 1000 = 52000
	got := SpendMicros(10.0, 5.2)
	if got != 52000 {
		t.Fatalf("spend %d want 52000", got)
	}
}
