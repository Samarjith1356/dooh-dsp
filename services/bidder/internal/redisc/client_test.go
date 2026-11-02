package redisc

import (
	"bufio"
	"context"
	"net"
	"strings"
	"testing"
	"time"
)

// fakeRedis answers GET/MGET from a map over a single connection.
func fakeRedis(t *testing.T, data map[string]string) string {
	ln, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { ln.Close() })
	go func() {
		for {
			c, err := ln.Accept()
			if err != nil {
				return
			}
			go func(c net.Conn) {
				defer c.Close()
				rd := bufio.NewReader(c)
				for {
					line, err := rd.ReadString('\n')
					if err != nil {
						return
					}
					n := 0
					for _, ch := range strings.TrimSpace(line[1:]) {
						n = n*10 + int(ch-'0')
					}
					args := make([]string, n)
					for i := range args {
						_, _ = rd.ReadString('\n')
						s, _ := rd.ReadString('\n')
						args[i] = strings.TrimSuffix(s, "\r\n")
					}
					bulk := func(k string) string {
						v, ok := data[k]
						if !ok {
							return "$-1\r\n"
						}
						return "$" + itoa(len(v)) + "\r\n" + v + "\r\n"
					}
					switch args[0] {
					case "GET":
						_, _ = c.Write([]byte(bulk(args[1])))
					case "MGET":
						out := "*" + itoa(len(args)-1) + "\r\n"
						for _, k := range args[1:] {
							out += bulk(k)
						}
						_, _ = c.Write([]byte(out))
					}
				}
			}(c)
		}
	}()
	return ln.Addr().String()
}

func itoa(n int) string {
	if n == 0 {
		return "0"
	}
	s := ""
	for ; n > 0; n /= 10 {
		s = string(rune('0'+n%10)) + s
	}
	return s
}

func TestGetAndMGet(t *testing.T) {
	addr := fakeRedis(t, map[string]string{"a": "1", "snap": "{\"x\":\n1}"})
	c := ParseURL("redis://" + addr + "/0")
	ctx, cancel := context.WithTimeout(context.Background(), time.Second)
	defer cancel()
	if v, err := c.Get(ctx, "snap"); err != nil || v != "{\"x\":\n1}" {
		t.Fatalf("get %q %v", v, err)
	}
	if _, err := c.Get(ctx, "nope"); err != ErrMissing {
		t.Fatalf("missing err %v", err)
	}
	vals, found, err := c.MGet(ctx, []string{"a", "nope", "a"})
	if err != nil || !found[0] || found[1] || vals[2] != "1" {
		t.Fatalf("mget %v %v %v", vals, found, err)
	}
}
