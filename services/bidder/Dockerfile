# Go 1.26: Green Tea GC by default and container-aware GOMAXPROCS, so the
# bidder sizes itself to its CPU quota instead of being throttled.
FROM golang:1.26-alpine AS build
RUN apk add --no-cache tzdata
WORKDIR /src
COPY services/bidder ./
RUN CGO_ENABLED=0 go build -trimpath -ldflags="-s -w" -o /bidder ./cmd/bidder

FROM alpine:3.20
RUN apk add --no-cache tzdata
COPY --from=build /bidder /bidder
ENV TZ=Europe/London
EXPOSE 8081
ENTRYPOINT ["/bidder"]
