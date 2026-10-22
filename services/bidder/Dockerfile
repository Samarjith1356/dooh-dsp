FROM golang:1.23-alpine AS build
WORKDIR /src
COPY services/bidder ./
RUN go build -o /bidder ./cmd/bidder

FROM alpine:3.20
COPY --from=build /bidder /bidder
EXPOSE 8081
ENTRYPOINT ["/bidder"]
