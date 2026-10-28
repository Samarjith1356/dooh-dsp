FROM golang:1.23-alpine AS build
RUN apk add --no-cache tzdata
WORKDIR /src
COPY services/bidder ./
RUN CGO_ENABLED=0 go build -ldflags="-s -w" -o /bidder ./cmd/bidder

FROM alpine:3.20
RUN apk add --no-cache tzdata
COPY --from=build /bidder /bidder
ENV TZ=Europe/London
EXPOSE 8081
ENTRYPOINT ["/bidder"]
