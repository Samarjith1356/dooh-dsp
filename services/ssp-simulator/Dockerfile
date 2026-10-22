FROM golang:1.23-alpine AS build
WORKDIR /src
COPY services/ssp-simulator ./
RUN go build -o /sim .

FROM alpine:3.20
COPY --from=build /sim /sim
ENTRYPOINT ["/sim"]
