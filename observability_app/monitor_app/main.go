// Copyright AGNTCY Contributors (https://github.com/agntcy)
// SPDX-License-Identifier: Apache-2.0

package main

import (
	"context"
	"os"
	"os/signal"
	"syscall"
	"time"

	"go.uber.org/zap"

	"observability_app/internal"

	slim "github.com/agntcy/slim-bindings-go"

	"github.com/agntcy/slim-otel/slimconfig"
)

func main() {
	ctx := context.Background()

	// Configure custom zap logger
	log, err := internal.NewLogger()
	if err != nil {
		panic(err)
	}
	defer func() {
		_ = log.Sync() // Ignore error on cleanup
	}()

	log.Info("Starting Monitor App")

	// Step 1: Initialize and connect to SLIM node
	connID, err := internal.InitAndConnect(slimconfig.ConnectionConfig{
		Address: internal.SlimNodeAddress,
	})
	if err != nil {
		log.Error("failed to connect to SLIM node", zap.Error(err))
		panic(err)
	}

	// Step 2: Create SLIM app
	app, err := internal.CreateApp(internal.MonitorAppName, internal.SharedSecret, connID, slim.DirectionRecv)
	if err != nil {
		log.Error("failed to create SLIM app", zap.Error(err))
		panic(err)
	}
	defer app.Destroy()

	// Step 3: Create a GROUP session (channel)
	channelNameParsed, err := internal.SplitID(internal.ChannelName)
	if err != nil {
		log.Error("failed to parse channel name", zap.Error(err))
		panic(err)
	}

	interval := time.Millisecond * 1000
	maxRetries := uint32(10)
	sessionConfig := slim.SessionConfig{
		SessionType: slim.SessionTypeGroup,
		EnableMls:   false, // Disable MLS for simplicity
		MaxRetries:  &maxRetries,
		Interval:    &interval,
		Metadata:    make(map[string]string),
	}

	session, err := app.CreateSessionAndWait(sessionConfig, channelNameParsed)
	if err != nil {
		log.Error("failed to create session", zap.Error(err))
		panic(err)
	}

	// Step 4: Invite the monitored app to the channel
	monitoredAppNameParsed, err := internal.SplitID(internal.MonitoredAppName)
	if err != nil {
		log.Error("failed to parse monitored app name", zap.Error(err))
		panic(err)
	}

	// Set route for the participant (needed for invitation)
	err = app.SetRoute(monitoredAppNameParsed, connID)
	if err != nil {
		log.Error("failed to set route for monitored app", zap.Error(err))
		panic(err)
	}

	err = session.InviteAndWait(monitoredAppNameParsed)
	if err != nil {
		log.Error("failed to invite monitored app", zap.Error(err))
		panic(err)
	}

	// Step 5: Invite the collector to the channel so it receives metrics for Grafana
	collectorNameParsed, err := internal.SplitID(internal.CollectorName)
	if err != nil {
		log.Error("failed to parse collector name", zap.Error(err))
		panic(err)
	}

	// Set route for the collector
	err = app.SetRoute(collectorNameParsed, connID)
	if err != nil {
		log.Error("failed to set route for collector", zap.Error(err))
		panic(err)
	}

	err = session.InviteAndWait(collectorNameParsed)
	if err != nil {
		log.Error("failed to invite collector", zap.Error(err))
		panic(err)
	}

	// Set up signal handling for graceful shutdown
	sigCh := make(chan os.Signal, 1)
	signal.Notify(sigCh, os.Interrupt, syscall.SIGTERM)

	// Create a context that will be canceled on interrupt
	runCtx, cancel := context.WithCancel(ctx)
	defer cancel()

	// Start goroutine to handle shutdown signal
	go func() {
		<-sigCh
		log.Info("Received interrupt signal, shutting down")
		cancel()
	}()

	log.Info("✅ Telemetry channel created")
	log.Info("🔍 Start to monitor telemetry stream")

	alertFired := false
	specialAgentInvited := false
	samplesOverThreshold := 0
	const samplesRequired = 5
	msgTimeout := time.Second * 5

	// Parse special agent name once
	specialAgentNameParsed, err := internal.SplitID(internal.SpecialAgentAppName)
	if err != nil {
		log.Error("failed to parse special agent name", zap.Error(err))
		panic(err)
	}

	// Step 5 & 6: Receive and parse metrics, check threshold
	for {
		select {
		case <-runCtx.Done():
			log.Info("Shutting down monitor agent")
			return

		default:
			// Receive message from SLIM channel
			msg, err := session.GetMessage(&msgTimeout)
			if err != nil {
				// Timeout is expected while waiting for messages
				continue
			}

			// Check if this is a completion message from special agent
			if string(msg.Payload) == "ANALYSIS_COMPLETE" {
				log.Info("📨 Received completion message from special agent")

				if specialAgentInvited {
					log.Info("🔄 Removing special agent from channel")

					// Remove special agent from the session
					if removeErr := session.RemoveAndWait(specialAgentNameParsed); removeErr != nil {
						log.Error("failed to remove special agent", zap.Error(removeErr))
					}

					// Reset flags so we can handle future alerts
				specialAgentInvited = false
				alertFired = false
				samplesOverThreshold = 0
				log.Info("Monitor reset - ready for next alert")
				}
				continue
			}

			// Parse the OTLP metrics
			latency, _, err := internal.ParseMetrics(msg.Payload)
			if err != nil {
				// Non-metrics message (not completion either), skip
				continue
			}

			// Check if latency exceeds threshold
			if latency > internal.LatencyThreshold {
				if !alertFired {
					samplesOverThreshold++
					log.Warn("⚠️  Latency threshold exceeded",
						zap.Int("current_latency_ms", int(latency)),
						zap.Int("threshold_ms", int(internal.LatencyThreshold)))

					// Fire alert after collecting required samples
					if samplesOverThreshold >= samplesRequired {
						log.Error("🚨 Latency threshold consistently exceeded!")
						alertFired = true

						// Invite the special agent to the channel
						log.Info("📞 Inviting special agent to channel to detect the root cause")

						// Set route for the special agent
						if routeErr := app.SetRoute(specialAgentNameParsed, connID); routeErr != nil {
							log.Error("failed to set route for special agent", zap.Error(routeErr))
							continue
						}

						// Invite the special agent (non-blocking)
						go func() {
							if inviteErr := session.InviteAndWait(specialAgentNameParsed); inviteErr != nil {
								log.Error("failed to invite special agent", zap.Error(inviteErr))
							} else {
								specialAgentInvited = true
							}
						}()
					}
				}
			} else {
				// Reset counter if latency drops below threshold (only if alert hasn't fired yet)
				if samplesOverThreshold > 0 && !alertFired {
					log.Info("Latency returned to normal, resetting counter",
						zap.Int("current_latency_ms", int(latency)),
						zap.Int("previous_samples", samplesOverThreshold))
					samplesOverThreshold = 0
				}
			}
		}
	}
}
