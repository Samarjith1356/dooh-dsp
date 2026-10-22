package redisc

import (
	"bufio"
	"context"
	"fmt"
	"net"
	"net/url"
	"strings"
	"time"
)

type Client struct {
	addr string
}

func ParseURL(raw string) *Client {
	u, err := url.Parse(raw)
	if err != nil || u.Host == "" {
		return &Client{addr: "localhost:6379"}
	}
	return &Client{addr: u.Host}
}

func (c *Client) Get(ctx context.Context, key string) (string, error) {
	d := net.Dialer{}
	conn, err := d.DialContext(ctx, "tcp", c.addr)
	if err != nil {
		return "", err
	}
	defer conn.Close()
	deadline, ok := ctx.Deadline()
	if ok {
		_ = conn.SetDeadline(deadline)
	} else {
		_ = conn.SetDeadline(time.Now().Add(200 * time.Millisecond))
	}
	_, err = fmt.Fprintf(conn, "*2\r\n$3\r\nGET\r\n$%d\r\n%s\r\n", len(key), key)
	if err != nil {
		return "", err
	}
	r := bufio.NewReader(conn)
	line, err := r.ReadString('\n')
	if err != nil {
		return "", err
	}
	line = strings.TrimSpace(line)
	if line == "$-1" || strings.HasPrefix(line, "-") {
		return "", fmt.Errorf("missing")
	}
	if strings.HasPrefix(line, "$") {
		body, err := r.ReadString('\n')
		return strings.TrimSpace(body), err
	}
	if strings.HasPrefix(line, "+") {
		return strings.TrimPrefix(line, "+"), nil
	}
	if strings.HasPrefix(line, ":") {
		return strings.TrimPrefix(line, ":"), nil
	}
	return line, nil
}
