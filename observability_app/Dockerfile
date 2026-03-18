FROM alpine:3.19 AS certs
RUN apk --update add ca-certificates

FROM golang:1.26.1 AS build-stage
WORKDIR /build

COPY ./builder-config.yaml builder-config.yaml

RUN --mount=type=cache,target=/root/.cache/go-build --mount=type=cache,target=/go/pkg/mod GO111MODULE=on go install go.opentelemetry.io/collector/cmd/builder@v0.145.0
RUN --mount=type=cache,target=/root/.cache/go-build builder --config builder-config.yaml --skip-compilation
RUN cd slim-otelcol && go mod download
RUN cd slim-otelcol && go run github.com/agntcy/slim-bindings-go/cmd/slim-bindings-setup
RUN --mount=type=cache,target=/root/.cache/go-build cd slim-otelcol && CGO_ENABLED=1 go build -trimpath -o slim-otelcol -ldflags="-s -w"

FROM debian:stable-slim

ARG USER_UID=10001
USER ${USER_UID}

COPY ./collector-config.yaml /etc/otelcol/collector-config.yaml
COPY --from=certs /etc/ssl/certs/ca-certificates.crt /etc/ssl/certs/ca-certificates.crt
COPY --chmod=755 --from=build-stage /build/slim-otelcol/slim-otelcol /otelcol

ENTRYPOINT ["/otelcol"]
CMD ["--config", "/etc/otelcol/collector-config.yaml"]

EXPOSE 8889

