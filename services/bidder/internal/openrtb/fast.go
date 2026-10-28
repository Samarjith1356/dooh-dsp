package openrtb

import (
	"bytes"
	"encoding/json"
	"strconv"
)

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
	impCount := 0
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
			d, ni, ok := parseDooh(b, i)
			if !ok {
				return false
			}
			req.Dooh = d
			i = ni
		case bytes.Equal(key, []byte("device")):
			ni, ok := parseDevice(b, i, req)
			if !ok {
				return false
			}
			i = ni
		case bytes.Equal(key, []byte("imp")):
			ni, n, ok := parseImpArray(b, i, req)
			if !ok {
				return false
			}
			impCount = n
			i = ni
		default:
			ni, ok := skipValue(b, i)
			if !ok {
				return false
			}
			i = ni
		}
		_ = impCount
	}
	return false
}

func parseDooh(b []byte, i int) (*Dooh, int, bool) {
	i = skipWS(b, i)
	if i >= len(b) || b[i] != '{' {
		return nil, i, false
	}
	i++
	d := &Dooh{}
	for i < len(b) {
		i = skipWS(b, i)
		if i < len(b) && b[i] == '}' {
			return d, i + 1, true
		}
		if i < len(b) && b[i] == ',' {
			i++
			continue
		}
		key, ni, ok := parseString(b, i)
		if !ok {
			return nil, i, false
		}
		i = skipWS(b, ni)
		if i >= len(b) || b[i] != ':' {
			return nil, i, false
		}
		i = skipWS(b, i+1)
		switch {
		case bytes.Equal(key, []byte("id")):
			s, ni, ok := parseString(b, i)
			if !ok {
				return nil, i, false
			}
			d.ID = string(s)
			i = ni
		case bytes.Equal(key, []byte("venuetype")):
			arr, ni, ok := parseStringArray(b, i)
			if !ok {
				return nil, i, false
			}
			d.VenueType = arr
			i = ni
		default:
			ni, ok := skipValue(b, i)
			if !ok {
				return nil, i, false
			}
			i = ni
		}
	}
	return nil, i, false
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
			req.Device.Geo.Country = string(s)
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

func parseImpArray(b []byte, i int, req *BidRequest) (int, int, bool) {
	i = skipWS(b, i)
	if i >= len(b) || b[i] != '[' {
		return i, 0, false
	}
	i++
	n := 0
	for i < len(b) {
		i = skipWS(b, i)
		if i < len(b) && b[i] == ']' {
			return i + 1, n, true
		}
		if i < len(b) && b[i] == ',' {
			i++
			continue
		}
		imp, ni, ok := parseImp(b, i)
		if !ok {
			return i, n, false
		}
		if n == 0 {
			req.Imp = append(req.Imp[:0], imp)
		}
		n++
		i = ni
	}
	return i, n, false
}

func parseImp(b []byte, i int) (Imp, int, bool) {
	i = skipWS(b, i)
	if i >= len(b) || b[i] != '{' {
		return Imp{}, i, false
	}
	i++
	var imp Imp
	for i < len(b) {
		i = skipWS(b, i)
		if i < len(b) && b[i] == '}' {
			return imp, i + 1, true
		}
		if i < len(b) && b[i] == ',' {
			i++
			continue
		}
		key, ni, ok := parseString(b, i)
		if !ok {
			return Imp{}, i, false
		}
		i = skipWS(b, ni)
		if i >= len(b) || b[i] != ':' {
			return Imp{}, i, false
		}
		i = skipWS(b, i+1)
		switch {
		case bytes.Equal(key, []byte("id")):
			s, ni, ok := parseString(b, i)
			if !ok {
				return Imp{}, i, false
			}
			imp.ID = string(s)
			i = ni
		case bytes.Equal(key, []byte("bidfloor")):
			f, ni, ok := parseFloat(b, i)
			if !ok {
				return Imp{}, i, false
			}
			imp.BidFloor = f
			i = ni
		case bytes.Equal(key, []byte("banner")):
			bn, ni, ok := parseWH(b, i)
			if !ok {
				return Imp{}, i, false
			}
			imp.Banner = bn
			i = ni
		case bytes.Equal(key, []byte("video")):
			vd, ni, ok := parseWHVideo(b, i)
			if !ok {
				return Imp{}, i, false
			}
			imp.Video = vd
			i = ni
		case bytes.Equal(key, []byte("qty")):
			q, ni, ok := parseQty(b, i)
			if !ok {
				return Imp{}, i, false
			}
			imp.Qty = q
			i = ni
		default:
			ni, ok := skipValue(b, i)
			if !ok {
				return Imp{}, i, false
			}
			i = ni
		}
	}
	return Imp{}, i, false
}

func parseWH(b []byte, i int) (*Banner, int, bool) {
	w, h, ni, ok := parseWHObj(b, i)
	if !ok {
		return nil, i, false
	}
	return &Banner{W: w, H: h}, ni, true
}

func parseWHVideo(b []byte, i int) (*Video, int, bool) {
	w, h, ni, ok := parseWHObj(b, i)
	if !ok {
		return nil, i, false
	}
	return &Video{W: w, H: h}, ni, true
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

func parseQty(b []byte, i int) (*Qty, int, bool) {
	i = skipWS(b, i)
	if i >= len(b) || b[i] != '{' {
		return nil, i, false
	}
	i++
	q := &Qty{}
	for i < len(b) {
		i = skipWS(b, i)
		if i < len(b) && b[i] == '}' {
			return q, i + 1, true
		}
		if i < len(b) && b[i] == ',' {
			i++
			continue
		}
		key, ni, ok := parseString(b, i)
		if !ok {
			return nil, i, false
		}
		i = skipWS(b, ni)
		if i >= len(b) || b[i] != ':' {
			return nil, i, false
		}
		i = skipWS(b, i+1)
		if bytes.Equal(key, []byte("multiplier")) {
			f, ni, ok := parseFloat(b, i)
			if !ok {
				return nil, i, false
			}
			q.Multiplier = f
			i = ni
			continue
		}
		ni, ok = skipValue(b, i)
		if !ok {
			return nil, i, false
		}
		i = ni
	}
	return nil, i, false
}

func parseStringArray(b []byte, i int) ([]string, int, bool) {
	i = skipWS(b, i)
	if i >= len(b) || b[i] != '[' {
		return nil, i, false
	}
	i++
	var out []string
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
		out = append(out, string(s))
		i = ni
	}
	return nil, i, false
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

func parseStringSlow(b []byte, start, i int) ([]byte, int, bool) {
	var buf []byte
	buf = append(buf, b[start:i]...)
	for i < len(b) {
		c := b[i]
		if c == '\\' {
			if i+1 >= len(b) {
				return nil, i, false
			}
			buf = append(buf, b[i+1])
			i += 2
			continue
		}
		if c == '"' {
			return buf, i + 1, true
		}
		buf = append(buf, c)
		i++
	}
	return nil, i, false
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
		_, ni, ok := parseString(b, i)
		return ni, ok
	case '{':
		return skipDelimited(b, i, '{', '}')
	case '[':
		return skipDelimited(b, i, '[', ']')
	case 't':
		if i+3 < len(b) && bytes.Equal(b[i:i+4], []byte("true")) {
			return i + 4, true
		}
	case 'f':
		if i+4 < len(b) && bytes.Equal(b[i:i+5], []byte("false")) {
			return i + 5, true
		}
	case 'n':
		if i+3 < len(b) && bytes.Equal(b[i:i+4], []byte("null")) {
			return i + 4, true
		}
	default:
		_, ni, ok := parseFloat(b, i)
		return ni, ok
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
