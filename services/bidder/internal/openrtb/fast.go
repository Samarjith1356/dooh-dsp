package openrtb

import (
	"bytes"
	"encoding/json"
	"strconv"
	"unicode/utf16"
	"unicode/utf8"
)

// UnmarshalBid parses an OpenRTB 2.6 bid request. The fast path fills the
// request's own backing storage, so a pooled BidRequest parses with a single
// allocation (the request ID). Dooh.Ext aliases data and is only valid while
// data is alive.
func UnmarshalBid(data []byte, req *BidRequest) error {
	if parseFast(data, req) {
		return nil
	}
	*req = BidRequest{}
	return json.Unmarshal(data, req)
}

func parseFast(b []byte, req *BidRequest) bool {
	*req = BidRequest{}
	i := skipWS(b, 0)
	if i >= len(b) || b[i] != '{' {
		return false
	}
	i++
	for i < len(b) {
		i = skipWS(b, i)
		if i >= len(b) {
			return false
		}
		if b[i] == '}' {
			return req.ID != ""
		}
		if b[i] == ',' {
			i++
			continue
		}
		key, ni, ok := parseString(b, i)
		if !ok {
			return false
		}
		i = skipWS(b, ni)
		if i >= len(b) || b[i] != ':' {
			return false
		}
		i = skipWS(b, i+1)
		if i >= len(b) {
			return false
		}
		switch {
		case bytes.Equal(key, []byte("id")):
			s, ni, ok := parseString(b, i)
			if !ok {
				return false
			}
			req.ID = string(s)
			i = ni
		case bytes.Equal(key, []byte("tmax")):
			n, ni, ok := parseInt(b, i)
			if !ok {
				return false
			}
			req.TMax = n
			i = ni
		case bytes.Equal(key, []byte("site")):
			if b[i] != 'n' {
				req.Site = []byte("1")
			}
			ni, ok := skipValue(b, i)
			if !ok {
				return false
			}
			i = ni
		case bytes.Equal(key, []byte("app")):
			if b[i] != 'n' {
				req.App = []byte("1")
			}
			ni, ok := skipValue(b, i)
			if !ok {
				return false
			}
			i = ni
		case bytes.Equal(key, []byte("dooh")):
			if b[i] == 'n' {
				ni, ok := skipValue(b, i)
				if !ok {
					return false
				}
				i = ni
				continue
			}
			ni, ok := parseDooh(b, i, req)
			if !ok {
				return false
			}
			req.Dooh = &req.doohBuf
			i = ni
		case bytes.Equal(key, []byte("device")):
			ni, ok := parseDevice(b, i, req)
			if !ok {
				return false
			}
			i = ni
		case bytes.Equal(key, []byte("imp")):
			ni, ok := parseImpArray(b, i, req)
			if !ok {
				return false
			}
			i = ni
		default:
			ni, ok := skipValue(b, i)
			if !ok {
				return false
			}
			i = ni
		}
	}
	return false
}

func parseDooh(b []byte, i int, req *BidRequest) (int, bool) {
	i = skipWS(b, i)
	if i >= len(b) || b[i] != '{' {
		return i, false
	}
	i++
	d := &req.doohBuf
	for i < len(b) {
		i = skipWS(b, i)
		if i < len(b) && b[i] == '}' {
			return i + 1, true
		}
		if i < len(b) && b[i] == ',' {
			i++
			continue
		}
		key, ni, ok := parseString(b, i)
		if !ok {
			return i, false
		}
		i = skipWS(b, ni)
		if i >= len(b) || b[i] != ':' {
			return i, false
		}
		i = skipWS(b, i+1)
		switch {
		case bytes.Equal(key, []byte("id")):
			s, ni, ok := parseString(b, i)
			if !ok {
				return i, false
			}
			d.ID = intern(s)
			i = ni
		case bytes.Equal(key, []byte("venuetype")):
			arr, ni, ok := parseStringArray(b, i, req.venueBuf[:0])
			if !ok {
				return i, false
			}
			d.VenueType = arr
			i = ni
		case bytes.Equal(key, []byte("ext")):
			ni, ok := skipValue(b, i)
			if !ok {
				return i, false
			}
			d.Ext = b[i:ni]
			i = ni
		default:
			ni, ok := skipValue(b, i)
			if !ok {
				return i, false
			}
			i = ni
		}
	}
	return i, false
}

func parseDevice(b []byte, i int, req *BidRequest) (int, bool) {
	i = skipWS(b, i)
	if i >= len(b) || b[i] != '{' {
		return i, false
	}
	i++
	for i < len(b) {
		i = skipWS(b, i)
		if i < len(b) && b[i] == '}' {
			return i + 1, true
		}
		if i < len(b) && b[i] == ',' {
			i++
			continue
		}
		key, ni, ok := parseString(b, i)
		if !ok {
			return i, false
		}
		i = skipWS(b, ni)
		if i >= len(b) || b[i] != ':' {
			return i, false
		}
		i = skipWS(b, i+1)
		if bytes.Equal(key, []byte("geo")) {
			ni, ok := parseGeo(b, i, req)
			if !ok {
				return i, false
			}
			i = ni
			continue
		}
		ni, ok = skipValue(b, i)
		if !ok {
			return i, false
		}
		i = ni
	}
	return i, false
}

func parseGeo(b []byte, i int, req *BidRequest) (int, bool) {
	i = skipWS(b, i)
	if i >= len(b) || b[i] != '{' {
		return i, false
	}
	i++
	for i < len(b) {
		i = skipWS(b, i)
		if i < len(b) && b[i] == '}' {
			return i + 1, true
		}
		if i < len(b) && b[i] == ',' {
			i++
			continue
		}
		key, ni, ok := parseString(b, i)
		if !ok {
			return i, false
		}
		i = skipWS(b, ni)
		if i >= len(b) || b[i] != ':' {
			return i, false
		}
		i = skipWS(b, i+1)
		switch {
		case bytes.Equal(key, []byte("lat")):
			f, ni, ok := parseFloat(b, i)
			if !ok {
				return i, false
			}
			req.Device.Geo.Lat = f
			i = ni
		case bytes.Equal(key, []byte("lon")):
			f, ni, ok := parseFloat(b, i)
			if !ok {
				return i, false
			}
			req.Device.Geo.Lon = f
			i = ni
		case bytes.Equal(key, []byte("country")):
			s, ni, ok := parseString(b, i)
			if !ok {
				return i, false
			}
			req.Device.Geo.Country = intern(s)
			i = ni
		default:
			ni, ok := skipValue(b, i)
			if !ok {
				return i, false
			}
			i = ni
		}
	}
	return i, false
}

func parseImpArray(b []byte, i int, req *BidRequest) (int, bool) {
	i = skipWS(b, i)
	if i >= len(b) || b[i] != '[' {
		return i, false
	}
	i++
	n := 0
	for i < len(b) {
		i = skipWS(b, i)
		if i < len(b) && b[i] == ']' {
			return i + 1, true
		}
		if i < len(b) && b[i] == ',' {
			i++
			continue
		}
		if n > 0 {
			// Only the first imp is bid on. Later imps would overwrite the
			// shared Banner/Video/Qty backing storage, so they are skipped.
			ni, ok := skipValue(b, i)
			if !ok {
				return i, false
			}
			i = ni
			n++
			continue
		}
		ni, ok := parseImp(b, i, req)
		if !ok {
			return i, false
		}
		req.Imp = req.impBuf[:1]
		i = ni
		n++
	}
	return i, false
}

func parseImp(b []byte, i int, req *BidRequest) (int, bool) {
	i = skipWS(b, i)
	if i >= len(b) || b[i] != '{' {
		return i, false
	}
	i++
	imp := &req.impBuf[0]
	for i < len(b) {
		i = skipWS(b, i)
		if i < len(b) && b[i] == '}' {
			return i + 1, true
		}
		if i < len(b) && b[i] == ',' {
			i++
			continue
		}
		key, ni, ok := parseString(b, i)
		if !ok {
			return i, false
		}
		i = skipWS(b, ni)
		if i >= len(b) || b[i] != ':' {
			return i, false
		}
		i = skipWS(b, i+1)
		switch {
		case bytes.Equal(key, []byte("id")):
			s, ni, ok := parseString(b, i)
			if !ok {
				return i, false
			}
			imp.ID = intern(s)
			i = ni
		case bytes.Equal(key, []byte("bidfloor")):
			f, ni, ok := parseFloat(b, i)
			if !ok {
				return i, false
			}
			imp.BidFloor = f
			i = ni
		case bytes.Equal(key, []byte("banner")):
			w, h, ni, ok := parseWHObj(b, i)
			if !ok {
				return i, false
			}
			req.bannerBuf = Banner{W: w, H: h}
			imp.Banner = &req.bannerBuf
			i = ni
		case bytes.Equal(key, []byte("video")):
			w, h, ni, ok := parseWHObj(b, i)
			if !ok {
				return i, false
			}
			req.videoBuf = Video{W: w, H: h}
			imp.Video = &req.videoBuf
			i = ni
		case bytes.Equal(key, []byte("qty")):
			ni, ok := parseQty(b, i, &req.qtyBuf)
			if !ok {
				return i, false
			}
			imp.Qty = &req.qtyBuf
			i = ni
		default:
			ni, ok := skipValue(b, i)
			if !ok {
				return i, false
			}
			i = ni
		}
	}
	return i, false
}

func parseWHObj(b []byte, i int) (int, int, int, bool) {
	i = skipWS(b, i)
	if i >= len(b) || b[i] != '{' {
		return 0, 0, i, false
	}
	i++
	var w, h int
	for i < len(b) {
		i = skipWS(b, i)
		if i < len(b) && b[i] == '}' {
			return w, h, i + 1, true
		}
		if i < len(b) && b[i] == ',' {
			i++
			continue
		}
		key, ni, ok := parseString(b, i)
		if !ok {
			return 0, 0, i, false
		}
		i = skipWS(b, ni)
		if i >= len(b) || b[i] != ':' {
			return 0, 0, i, false
		}
		i = skipWS(b, i+1)
		n, ni, ok := parseInt(b, i)
		if !ok {
			ni, ok = skipValue(b, i)
			if !ok {
				return 0, 0, i, false
			}
			i = ni
			continue
		}
		if bytes.Equal(key, []byte("w")) {
			w = n
		} else if bytes.Equal(key, []byte("h")) {
			h = n
		}
		i = ni
	}
	return 0, 0, i, false
}

func parseQty(b []byte, i int, q *Qty) (int, bool) {
	i = skipWS(b, i)
	if i >= len(b) || b[i] != '{' {
		return i, false
	}
	i++
	for i < len(b) {
		i = skipWS(b, i)
		if i < len(b) && b[i] == '}' {
			return i + 1, true
		}
		if i < len(b) && b[i] == ',' {
			i++
			continue
		}
		key, ni, ok := parseString(b, i)
		if !ok {
			return i, false
		}
		i = skipWS(b, ni)
		if i >= len(b) || b[i] != ':' {
			return i, false
		}
		i = skipWS(b, i+1)
		if bytes.Equal(key, []byte("multiplier")) {
			f, ni, ok := parseFloat(b, i)
			if !ok {
				return i, false
			}
			q.Multiplier = f
			i = ni
			continue
		}
		ni, ok = skipValue(b, i)
		if !ok {
			return i, false
		}
		i = ni
	}
	return i, false
}

// parseStringArray appends interned strings to out. Pass a reused backing
// slice to avoid allocating.
func parseStringArray(b []byte, i int, out []string) ([]string, int, bool) {
	i = skipWS(b, i)
	if i >= len(b) || b[i] != '[' {
		return nil, i, false
	}
	i++
	for i < len(b) {
		i = skipWS(b, i)
		if i < len(b) && b[i] == ']' {
			return out, i + 1, true
		}
		if i < len(b) && b[i] == ',' {
			i++
			continue
		}
		s, ni, ok := parseString(b, i)
		if !ok {
			return nil, i, false
		}
		out = append(out, intern(s))
		i = ni
	}
	return nil, i, false
}

// ExtString returns the string value of a top-level key in a JSON object,
// without allocating. Used by adapters reading publisher ext blobs.
func ExtString(obj []byte, key string) ([]byte, bool) {
	i := skipWS(obj, 0)
	if i >= len(obj) || obj[i] != '{' {
		return nil, false
	}
	i++
	for i < len(obj) {
		i = skipWS(obj, i)
		if i >= len(obj) || obj[i] == '}' {
			return nil, false
		}
		if obj[i] == ',' {
			i++
			continue
		}
		k, ni, ok := parseString(obj, i)
		if !ok {
			return nil, false
		}
		i = skipWS(obj, ni)
		if i >= len(obj) || obj[i] != ':' {
			return nil, false
		}
		i = skipWS(obj, i+1)
		if string(k) == key {
			if i < len(obj) && obj[i] == '"' {
				v, _, ok := parseString(obj, i)
				return v, ok
			}
			return nil, false
		}
		ni, ok = skipValue(obj, i)
		if !ok {
			return nil, false
		}
		i = ni
	}
	return nil, false
}

func parseString(b []byte, i int) ([]byte, int, bool) {
	i = skipWS(b, i)
	if i >= len(b) || b[i] != '"' {
		return nil, i, false
	}
	i++
	start := i
	for i < len(b) {
		c := b[i]
		if c == '\\' {
			return parseStringSlow(b, start, i)
		}
		if c == '"' {
			return b[start:i], i + 1, true
		}
		i++
	}
	return nil, i, false
}

// parseStringSlow decodes a JSON string that contains escapes, continuing
// from the first backslash at b[i].
func parseStringSlow(b []byte, start, i int) ([]byte, int, bool) {
	buf := make([]byte, 0, i-start+16)
	buf = append(buf, b[start:i]...)
	for i < len(b) {
		c := b[i]
		switch {
		case c == '"':
			return buf, i + 1, true
		case c == '\\':
			if i+1 >= len(b) {
				return nil, i, false
			}
			switch e := b[i+1]; e {
			case '"', '\\', '/':
				buf = append(buf, e)
			case 'b':
				buf = append(buf, '\b')
			case 'f':
				buf = append(buf, '\f')
			case 'n':
				buf = append(buf, '\n')
			case 'r':
				buf = append(buf, '\r')
			case 't':
				buf = append(buf, '\t')
			case 'u':
				r, n, ok := parseUnicodeEscape(b, i)
				if !ok {
					return nil, i, false
				}
				buf = utf8.AppendRune(buf, r)
				i += n
				continue
			default:
				return nil, i, false
			}
			i += 2
		default:
			buf = append(buf, c)
			i++
		}
	}
	return nil, i, false
}

// parseUnicodeEscape decodes \uXXXX at b[i], joining a following low
// surrogate when present. Returns the rune and bytes consumed.
func parseUnicodeEscape(b []byte, i int) (rune, int, bool) {
	r, ok := hex4(b, i+2)
	if !ok {
		return 0, 0, false
	}
	if utf16.IsSurrogate(r) {
		if i+12 <= len(b) && b[i+6] == '\\' && b[i+7] == 'u' {
			if r2, ok := hex4(b, i+8); ok {
				if dec := utf16.DecodeRune(r, r2); dec != utf8.RuneError {
					return dec, 12, true
				}
			}
		}
		return utf8.RuneError, 6, true
	}
	return r, 6, true
}

func hex4(b []byte, i int) (rune, bool) {
	if i+4 > len(b) {
		return 0, false
	}
	var r rune
	for _, c := range b[i : i+4] {
		switch {
		case c >= '0' && c <= '9':
			c -= '0'
		case c >= 'a' && c <= 'f':
			c = c - 'a' + 10
		case c >= 'A' && c <= 'F':
			c = c - 'A' + 10
		default:
			return 0, false
		}
		r = r<<4 | rune(c)
	}
	return r, true
}

func parseInt(b []byte, i int) (int, int, bool) {
	f, ni, ok := parseFloat(b, i)
	if !ok {
		return 0, i, false
	}
	return int(f), ni, true
}

func parseFloat(b []byte, i int) (float64, int, bool) {
	i = skipWS(b, i)
	start := i
	if i < len(b) && (b[i] == '-' || b[i] == '+') {
		i++
	}
	for i < len(b) && (b[i] == '.' || b[i] == 'e' || b[i] == 'E' || b[i] == '+' || b[i] == '-' || (b[i] >= '0' && b[i] <= '9')) {
		i++
	}
	if i == start {
		return 0, i, false
	}
	f, err := strconv.ParseFloat(string(b[start:i]), 64)
	if err != nil {
		return 0, i, false
	}
	return f, i, true
}

func skipValue(b []byte, i int) (int, bool) {
	i = skipWS(b, i)
	if i >= len(b) {
		return i, false
	}
	switch b[i] {
	case '"':
		return skipString(b, i)
	case '{':
		return skipDelimited(b, i, '{', '}')
	case '[':
		return skipDelimited(b, i, '[', ']')
	case 't':
		if i+4 <= len(b) && bytes.Equal(b[i:i+4], []byte("true")) {
			return i + 4, true
		}
	case 'f':
		if i+5 <= len(b) && bytes.Equal(b[i:i+5], []byte("false")) {
			return i + 5, true
		}
	case 'n':
		if i+4 <= len(b) && bytes.Equal(b[i:i+4], []byte("null")) {
			return i + 4, true
		}
	default:
		_, ni, ok := parseFloat(b, i)
		return ni, ok
	}
	return i, false
}

// skipString skips a JSON string at b[i] without decoding it.
func skipString(b []byte, i int) (int, bool) {
	i++
	for i < len(b) {
		switch b[i] {
		case '\\':
			i += 2
		case '"':
			return i + 1, true
		default:
			i++
		}
	}
	return i, false
}

func skipDelimited(b []byte, i int, open, close byte) (int, bool) {
	if i >= len(b) || b[i] != open {
		return i, false
	}
	depth := 1
	i++
	inStr := false
	esc := false
	for i < len(b) && depth > 0 {
		c := b[i]
		if inStr {
			if esc {
				esc = false
			} else if c == '\\' {
				esc = true
			} else if c == '"' {
				inStr = false
			}
			i++
			continue
		}
		switch c {
		case '"':
			inStr = true
		case open:
			depth++
		case close:
			depth--
		}
		i++
	}
	return i, depth == 0
}

func skipWS(b []byte, i int) int {
	for i < len(b) {
		c := b[i]
		if c != ' ' && c != '\n' && c != '\r' && c != '\t' {
			return i
		}
		i++
	}
	return i
}
