package matcher

import (
	"strconv"

	"github.com/dooh-dsp/bidder/internal/openrtb"
)

func AppendResponse(dst []byte, resp *openrtb.BidResponse) []byte {
	dst = append(dst, `{"id":`...)
	dst = strconv.AppendQuote(dst, resp.ID)
	if resp.Nbr != 0 || len(resp.SeatBid) == 0 {
		dst = append(dst, `,"nbr":`...)
		dst = strconv.AppendInt(dst, int64(resp.Nbr), 10)
		dst = append(dst, '}')
		return dst
	}
	if resp.Cur != "" {
		dst = append(dst, `,"cur":`...)
		dst = strconv.AppendQuote(dst, resp.Cur)
	}
	sb := resp.SeatBid[0]
	b := sb.Bid[0]
	dst = append(dst, `,"seatbid":[{"seat":`...)
	dst = strconv.AppendQuote(dst, sb.Seat)
	dst = append(dst, `,"bid":[{"id":`...)
	dst = strconv.AppendQuote(dst, b.ID)
	dst = append(dst, `,"impid":`...)
	dst = strconv.AppendQuote(dst, b.ImpID)
	dst = append(dst, `,"price":`...)
	dst = strconv.AppendFloat(dst, b.Price, 'f', 4, 64)
	dst = append(dst, `,"adm":`...)
	dst = strconv.AppendQuote(dst, b.AdM)
	dst = append(dst, `,"nurl":`...)
	dst = strconv.AppendQuote(dst, b.NURL)
	dst = append(dst, `,"burl":`...)
	dst = strconv.AppendQuote(dst, b.BURL)
	dst = append(dst, `,"crid":`...)
	dst = strconv.AppendQuote(dst, b.CrID)
	dst = append(dst, `,"cid":`...)
	dst = strconv.AppendQuote(dst, b.CID)
	dst = append(dst, `,"w":`...)
	dst = strconv.AppendInt(dst, int64(b.W), 10)
	dst = append(dst, `,"h":`...)
	dst = strconv.AppendInt(dst, int64(b.H), 10)
	dst = append(dst, `,"adomain":["dooh.local"]}]}]}`...)
	return dst
}
