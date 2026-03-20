// Copyright AGNTCY Contributors (https://github.com/agntcy)
// SPDX-License-Identifier: Apache-2.0

package internal

import (
	"fmt"
	"strings"

	slim "github.com/agntcy/slim-bindings-go"
	"github.com/agntcy/slim-otel/slimconfig"
	"go.opentelemetry.io/collector/pdata/pmetric"
	"go.uber.org/zap"
	"go.uber.org/zap/zapcore"
)

// Shared constants across all observability components
const (
	SlimNodeAddress     = "http://127.0.0.1:46357"
	SharedSecret        = "7k9mP2nQ8xL4vR6wT3yU5zH1jN0bG8cF9dS2aE"
	MonitorAppName      = "agntcy/telemetry/monitor_app"
	SpecialAgentAppName = "agntcy/telemetry/special_agent"
	MonitoredAppName    = "agntcy/telemetry/monitored_app_metrics"
	CollectorName       = "agntcy/telemetry/collector"
	ChannelName         = "agntcy/telemetry/channel"
	LatencyThreshold    = 200.0 // milliseconds
)

// NewLogger creates a custom zap logger without caller info and stack traces
func NewLogger() (*zap.Logger, error) {
	config := zap.NewDevelopmentConfig()
	config.EncoderConfig.TimeKey = "time"
	config.EncoderConfig.LevelKey = "level"
	config.EncoderConfig.MessageKey = "msg"
	config.EncoderConfig.CallerKey = ""     // Disable caller info
	config.EncoderConfig.StacktraceKey = "" // Disable stack traces
	config.EncoderConfig.EncodeTime = zapcore.TimeEncoderOfLayout("15:04:05.000")
	config.EncoderConfig.EncodeLevel = zapcore.CapitalColorLevelEncoder

	return config.Build()
}

// InitAndConnect initializes the connection to the SLIM server
func InitAndConnect(
	cfg slimconfig.ConnectionConfig,
) (uint64, error) {

	// Initialize crypto subsystem (idempotent, safe to call multiple times)
	slim.InitializeWithDefaults()

	// Connect to SLIM server (returns connection ID)
	config, err := cfg.ToSlimClientConfig()
	if err != nil {
		return 0, fmt.Errorf("failed to convert connection config: %w", err)
	}
	connID, err := slim.GetGlobalService().Connect(config)
	if err != nil {
		return 0, fmt.Errorf("failed to connect to SLIM server: %w", err)
	}

	return connID, nil
}

// SplitID splits an ID of form organization/namespace/application (or channel).
func SplitID(id string) (*slim.Name, error) {
	parts := strings.Split(id, "/")
	if len(parts) != 3 {
		return nil, fmt.Errorf("IDs must be in the format organization/namespace/app-or-stream, got: %s", id)
	}
	return slim.NewName(parts[0], parts[1], parts[2]), nil
}

// CreateApp creates a SLIM app with shared secret authentication and subscribes it to a connection.
func CreateApp(
	localID string,
	secret string,
	connID uint64,
	direction slim.Direction,
) (*slim.App, error) {
	appName, err := SplitID(localID)
	if err != nil {
		return nil, fmt.Errorf("invalid local ID: %w", err)
	}

	identityProvider := slim.IdentityProviderConfigSharedSecret{
		Data: secret,
		Id:   localID,
	}

	identityVerifier := slim.IdentityVerifierConfigSharedSecret{
		Data: secret,
		Id:   localID,
	}

	// this is an exporter, so should not receive any incoming data
	app, err := slim.GetGlobalService().CreateAppWithDirection(
		appName, identityProvider, identityVerifier, direction)
	if err != nil {
		return nil, fmt.Errorf("create app failed: %w", err)
	}

	if err := app.Subscribe(appName, &connID); err != nil {
		app.Destroy()
		return nil, fmt.Errorf("subscribe failed: %w", err)
	}
	return app, nil
}

// ParseMetrics decodes OTLP metrics and extracts processing_latency_ms and active_connections
func ParseMetrics(payload []byte) (latency float64, connections int64, err error) {
	unmarshaler := &pmetric.ProtoUnmarshaler{}
	metrics, err := unmarshaler.UnmarshalMetrics(payload)
	if err != nil {
		return 0, 0, fmt.Errorf("failed to unmarshal metrics: %w", err)
	}

	// Iterate through resource metrics
	for i := 0; i < metrics.ResourceMetrics().Len(); i++ {
		rm := metrics.ResourceMetrics().At(i)

		// Iterate through scope metrics
		for j := 0; j < rm.ScopeMetrics().Len(); j++ {
			sm := rm.ScopeMetrics().At(j)

			// Iterate through metrics
			for k := 0; k < sm.Metrics().Len(); k++ {
				metric := sm.Metrics().At(k)
				name := metric.Name()

				// Extract the metric values based on type
				if metric.Type() == pmetric.MetricTypeGauge {
					gauge := metric.Gauge()
					if gauge.DataPoints().Len() > 0 {
						dp := gauge.DataPoints().At(0)

						switch name {
						case "processing_latency_ms":
							latency = dp.DoubleValue()
						case "active_connections":
							connections = dp.IntValue()
						}
					}
				}
			}
		}
	}

	return latency, connections, nil
}
