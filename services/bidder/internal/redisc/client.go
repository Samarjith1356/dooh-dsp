// Package redisc is a minimal RESP2 client for the bidder's background
// pollers (snapshot + budget). It keeps one persistent connection and never
// runs on the bid path.
package redisc

import (
	"bufio"
	"context"
	"errors"
	"fmt"
	"io"
	"net"
	"net/url"
	"strconv"
	"sync"
	"time"
)

var ErrMissing = errors.New("missing")

type Client struct {
	addr string
	mu   sync.Mutex
	conn net.Conn
	rd   *bufio.Reader
	wb   []byte
}

func ParseURL(raw string) *Client {
	u, err := url.Parse(raw)
	if err != nil || u.Host == "" {
		return &Client{addr: "localhost:6379"}
	}
	return &Client{addr: u.Host}
}

// Get returns ErrMissing for a nil reply.
func (c *Client) Get(ctx context.Context, key string) (string, error) {
	vals, found, err := c.do(ctx, "GET", []string{key}, false)
	if err != nil {
		return "", err
	}
	if !found[0] {
		return "", ErrMissing
	}
	return vals[0], nil
}

// MGet fetches all keys in one round trip. found[i] is false for nil replies.
func (c *Client) MGet(ctx context.Context, keys []string) ([]string, []bool, error) {
	if len(keys) == 0 {
		return nil, nil, nil
	}
	return c.do(ctx, "MGET", keys, true)
}

func (c *Client) do(ctx context.Context, cmd string, args []string, array bool) ([]string, []bool, error) {
	c.mu.Lock()
	defer c.mu.Unlock()
	if c.conn == nil {
		d := net.Dialer{}
		conn, err := d.DialContext(ctx, "tcp", c.addr)
		if err != nil {
			return nil, nil, err
		}
		c.conn = conn
		c.rd = bufio.NewReaderSize(conn, 64<<10)
	}
	deadline, ok := ctx.Deadline()
	if !ok {
		deadline = time.Now().Add(500 * time.Millisecond)
	}
	_ = c.conn.SetDeadline(deadline)

	c.wb = appendCommand(c.wb[:0], cmd, args)
	vals, found, err := c.roundTrip(len(args), array)
	if err != nil {
		// Any protocol or I/O error leaves the stream in an unknown state.
		_ = c.conn.Close()
		c.conn, c.rd = nil, nil
		return nil, nil, err
	}
	return vals, found, nil
}

func (c *Client) roundTrip(n int, array bool) ([]string, []bool, error) {
	if _, err := c.conn.Write(c.wb); err != nil {
		return nil, nil, err
	}
	if !array {
		v, ok, err := c.readValue()
		return []string{v}, []bool{ok}, err
	}
	line, err := c.readLine()
	if err != nil {
		return nil, nil, err
	}
	if len(line) == 0 || line[0] != '*' {
		return nil, nil, protoErr(line)
	}
	m, err := strconv.Atoi(string(line[1:]))
	if err != nil || m != n {
		return nil, nil, fmt.Errorf("redis: array len %q, want %d", line, n)
	}
	vals := make([]string, n)
	found := make([]bool, n)
	for i := 0; i < n; i++ {
		if vals[i], found[i], err = c.readValue(); err != nil {
			return nil, nil, err
		}
	}
	return vals, found, nil
}

// readValue reads one bulk/simple/integer reply. Bulk strings are read by
// length, so values containing newlines survive.
func (c *Client) readValue() (string, bool, error) {
	line, err := c.readLine()
	if err != nil {
		return "", false, err
	}
	if len(line) == 0 {
		return "", false, protoErr(line)
	}
	switch line[0] {
	case '$':
		n, err := strconv.Atoi(string(line[1:]))
		if err != nil {
			return "", false, protoErr(line)
		}
		if n < 0 {
			return "", false, nil
		}
		buf := make([]byte, n+2)
		if _, err := io.ReadFull(c.rd, buf); err != nil {
			return "", false, err
		}
		return string(buf[:n]), true, nil
	case '+', ':':
		return string(line[1:]), true, nil
	case '-':
		return "", false, fmt.Errorf("redis: %s", line[1:])
	}
	return "", false, protoErr(line)
}

func (c *Client) readLine() ([]byte, error) {
	line, err := c.rd.ReadSlice('\n')
	if err != nil {
		return nil, err
	}
	if len(line) < 2 || line[len(line)-2] != '\r' {
		return nil, protoErr(line)
	}
	return line[:len(line)-2], nil
}

func appendCommand(dst []byte, cmd string, args []string) []byte {
	dst = append(dst, '*')
	dst = strconv.AppendInt(dst, int64(len(args)+1), 10)
	dst = append(dst, "\r\n"...)
	dst = appendBulk(dst, cmd)
	for _, a := range args {
		dst = appendBulk(dst, a)
	}
	return dst
}

func appendBulk(dst []byte, s string) []byte {
	dst = append(dst, '$')
	dst = strconv.AppendInt(dst, int64(len(s)), 10)
	dst = append(dst, "\r\n"...)
	dst = append(dst, s...)
	return append(dst, "\r\n"...)
}

func protoErr(line []byte) error { return fmt.Errorf("redis: unexpected reply %q", line) }
