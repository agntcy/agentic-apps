// Copyright AGNTCY Contributors (https://github.com/agntcy)
// SPDX-License-Identifier: Apache-2.0

package main

import (
	"context"
	"fmt"
	"math"
	"os"
	"os/signal"
	"strings"
	"syscall"
	"time"

	openai "github.com/sashabaranov/go-openai"
	"go.uber.org/zap"

	"observability_app/internal"

	"github.com/agntcy/slim-otel/slimconfig"

	slim "github.com/agntcy/slim-bindings-go"
)

const (
	analysisWindowSec = 10.0
)

type MetricSnapshot struct {
	latency     float64
	connections int64
	timestamp   time.Time
}

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

	// Check for Azure API key and endpoint
	apiKey := os.Getenv("AZURE_API_KEY")
	if apiKey == "" {
		log.Error("AZURE_API_KEY environment variable is required")
		panic("AZURE_API_KEY environment variable is required")
	}

	azureEndpoint := os.Getenv("AZURE_OPENAI_ENDPOINT")
	if azureEndpoint == "" {
		log.Error("AZURE_OPENAI_ENDPOINT environment variable is required")
		panic("AZURE_OPENAI_ENDPOINT environment variable is required")
	}

	// Get deployment name (model name in Azure)
	deploymentName := os.Getenv("AZURE_OPENAI_DEPLOYMENT")
	if deploymentName == "" {
		deploymentName = "gpt-4o" // Default deployment name
	}

	log.Info("🤖 Starting AI-Powered Special Agent (Azure OpenAI)")

	// Initialize Azure OpenAI client
	azureConfig := openai.DefaultAzureConfig(apiKey, azureEndpoint)
	client := openai.NewClientWithConfig(azureConfig)

	// Step 1: Initialize and connect to SLIM node
	connID, err := internal.InitAndConnect(slimconfig.ConnectionConfig{
		Address: internal.SlimNodeAddress,
	})
	if err != nil {
		log.Error("failed to connect to SLIM node", zap.Error(err))
		panic(err)
	}

	// Step 2: Create SLIM app
	app, err := internal.CreateApp(internal.SpecialAgentAppName, internal.SharedSecret, connID, slim.DirectionBidirectional)
	if err != nil {
		log.Error("failed to create SLIM app", zap.Error(err))
		panic(err)
	}
	defer app.Destroy()

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

	// Main loop: wait for invitations, analyze with AI, send completion, repeat
	for {
		select {
		case <-runCtx.Done():
			log.Info("Shutting down special agent")
			return
		default:
			log.Info("⏳ Waiting for incoming telemetry for a new analysis...")

			// Wait for invitation and join session
			session, err := waitForInvitation(runCtx, app, log)
			if err != nil {
				// Context canceled, exit
				return
			}

			log.Info("✅ Joined telemetry channel - starting analysis...")
			log.Info("📊 Collecting metrics...", zap.Float64("duration_sec", analysisWindowSec))

			// Collect metrics for analysis window
			snapshots, err := collectMetrics(runCtx, session, log)
			if err != nil {
				// Context canceled, exit
				return
			}

			// Analyze data with AI
			if len(snapshots) == 0 {
				log.Error("No metrics collected during analysis window")
				// Send completion message anyway
				completionMsg := []byte("ANALYSIS_COMPLETE")
				if _, err = session.Publish(completionMsg, nil, nil); err != nil {
					log.Error("failed to send completion message", zap.Error(err))
				}
				continue
			}

			log.Info("🧠 Analyzing with AI...", zap.Int("samples", len(snapshots)))

			// Analyze with Azure OpenAI
			diagnosis, err := analyzeWithAI(ctx, client, deploymentName, snapshots)
			if err != nil {
				log.Error("AI analysis failed", zap.Error(err))
				log.Info("Falling back to basic analysis")
				printBasicDiagnosis(snapshots)
			} else {
				printAIDiagnosis(diagnosis)
			}

			log.Info("✅ Analysis complete - notify monitor agent")

			// Send completion message
			completionMsg := []byte("ANALYSIS_COMPLETE")
			handler, err := session.Publish(completionMsg, nil, nil)
			if err != nil {
				log.Error("failed to send completion message", zap.Error(err))
			}

			// Wait for message to be sent
			if err := handler.Wait(); err != nil {
				log.Error("failed to wait for message send", zap.Error(err))
			}
		}
	}
}

// waitForInvitation waits for a session invitation and returns the session
// Returns error only if context is canceled
func waitForInvitation(ctx context.Context, app *slim.App, log *zap.Logger) (*slim.Session, error) {
	sessionTimeout := time.Second * 1

	for {
		select {
		case <-ctx.Done():
			log.Info("Shutting down special agent while waiting for invitation")
			return nil, ctx.Err()
		default:
			session, err := app.ListenForSession(&sessionTimeout)
			if err != nil {
				// Timeout is expected while waiting for invitation
				continue
			}
			// Successfully received invitation
			return session, nil
		}
	}
}

// collectMetrics collects metric snapshots for the analysis window
// Returns error only if context is canceled
func collectMetrics(ctx context.Context, session *slim.Session, log *zap.Logger) ([]MetricSnapshot, error) {
	var snapshots []MetricSnapshot
	startTime := time.Now()
	msgTimeout := time.Second * 2

	for {
		select {
		case <-ctx.Done():
			log.Info("Shutting down special agent during analysis")
			return nil, ctx.Err()
		default:
			elapsed := time.Since(startTime).Seconds()
			if elapsed >= analysisWindowSec {
				// Analysis window complete
				return snapshots, nil
			}

			// Receive message from SLIM channel
			msg, err := session.GetMessage(&msgTimeout)
			if err != nil {
				// Timeout is expected while waiting for messages
				continue
			}

			// Parse the OTLP metrics
			latency, connections, err := internal.ParseMetrics(msg.Payload)
			if err != nil {
				log.Warn("failed to parse metrics", zap.Error(err))
				continue
			}

			// Store snapshot
			snapshots = append(snapshots, MetricSnapshot{
				latency:     latency,
				connections: connections,
				timestamp:   time.Now(),
			})
		}
	}
}

// analyzeWithAI sends telemetry data to Azure OpenAI for intelligent root cause analysis
func analyzeWithAI(
	ctx context.Context,
	client *openai.Client,
	deploymentName string,
	snapshots []MetricSnapshot,
) (string, error) {
	// Calculate basic statistics
	var sumLatency, sumConns float64
	var maxLatency float64
	var maxConnections int64
	minLatency := snapshots[0].latency
	minConnections := snapshots[0].connections

	for _, snap := range snapshots {
		sumLatency += snap.latency
		sumConns += float64(snap.connections)

		if snap.latency > maxLatency {
			maxLatency = snap.latency
		}
		if snap.latency < minLatency {
			minLatency = snap.latency
		}
		if snap.connections > maxConnections {
			maxConnections = snap.connections
		}
		if snap.connections < minConnections {
			minConnections = snap.connections
		}
	}

	avgLatency := sumLatency / float64(len(snapshots))
	avgConnections := sumConns / float64(len(snapshots))

	// Build detailed metrics summary
	var metricsDetail strings.Builder
	metricsDetail.WriteString("\nDetailed metrics samples:\n")
	for i, snap := range snapshots {
		metricsDetail.WriteString(fmt.Sprintf("  Sample %d: %.2fms latency, %d connections\n",
			i+1, snap.latency, snap.connections))
	}

	// Create a detailed prompt for the AI
	prompt := fmt.Sprintf(
		`You are an expert Site Reliability Engineer analyzing telemetry data from a production application.

TELEMETRY DATA ANALYSIS:
- Collection Period: %.1f seconds
- Samples Collected: %d
- Sample Rate: ~%.1f samples/second

PROCESSING LATENCY METRICS:
- Average: %.2f ms
- Minimum: %.2f ms
- Maximum: %.2f ms
- Range: %.2f ms
- Standard Deviation: %.2f ms

ACTIVE CONNECTIONS METRICS:
- Average: %.0f connections
- Minimum: %d connections
- Maximum: %d connections
- Range: %d connections

BASELINE ASSUMPTIONS:
- Normal latency: ~50ms
- Normal connections: ~50
- Latency increase: %.1fx from baseline
- Connection increase: %.1fx from baseline

%s

TASK:
Analyze this telemetry data and provide:
1. A clear diagnosis of what's happening
2. The root cause of any performance issues
3. Specific, actionable recommendations to fix the problem
4. Confidence level in your analysis

Be concise but thorough. Focus on actionable insights.`,
		analysisWindowSec,
		len(snapshots),
		float64(len(snapshots))/analysisWindowSec,
		avgLatency,
		minLatency,
		maxLatency,
		maxLatency-minLatency,
		calculateStdDev(snapshots, avgLatency),
		avgConnections,
		minConnections,
		maxConnections,
		maxConnections-minConnections,
		avgLatency/50.0,
		avgConnections/50.0,
		metricsDetail.String(),
	)

	// Use Azure OpenAI to analyze
	resp, err := client.CreateChatCompletion(
		ctx,
		openai.ChatCompletionRequest{
			Model: deploymentName,
			Messages: []openai.ChatCompletionMessage{
				{
					Role: openai.ChatMessageRoleSystem,
					Content: "You are an expert SRE and performance analyst. " +
						"Provide clear, actionable diagnoses based on telemetry data.",
				},
				{
					Role:    openai.ChatMessageRoleUser,
					Content: prompt,
				},
			},
			Temperature: 0.3, // Lower temperature for more focused analysis
			MaxTokens:   1500,
		},
	)
	if err != nil {
		return "", fmt.Errorf("Azure OpenAI API call failed: %w", err)
	}

	if len(resp.Choices) == 0 {
		return "", fmt.Errorf("no response from Azure OpenAI")
	}

	// Extract the text response
	diagnosis := resp.Choices[0].Message.Content

	return diagnosis, nil
}

// calculateStdDev calculates the standard deviation in latency
func calculateStdDev(snapshots []MetricSnapshot, mean float64) float64 {
	var sumSquares float64
	for _, snap := range snapshots {
		diff := snap.latency - mean
		sumSquares += diff * diff
	}
	variance := sumSquares / float64(len(snapshots))
	return math.Sqrt(variance)
}

// printAIDiagnosis displays the AI-generated diagnosis
func printAIDiagnosis(diagnosis string) {
	fmt.Println()
	fmt.Println("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
	fmt.Println("🧠 AI-Powered Root Cause Analysis")
	fmt.Println("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
	fmt.Println()
	fmt.Println(diagnosis)
	fmt.Println()
	fmt.Println("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
	fmt.Println()
}

// printBasicDiagnosis is a fallback when AI analysis fails
func printBasicDiagnosis(snapshots []MetricSnapshot) {
	var sumLatency, sumConns float64
	var maxLatency float64
	var maxConnections int64

	for _, snap := range snapshots {
		sumLatency += snap.latency
		sumConns += float64(snap.connections)
		if snap.latency > maxLatency {
			maxLatency = snap.latency
		}
		if snap.connections > maxConnections {
			maxConnections = snap.connections
		}
	}

	avgLatency := sumLatency / float64(len(snapshots))
	avgConnections := sumConns / float64(len(snapshots))

	fmt.Println()
	fmt.Println("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
	fmt.Println("📊 Basic Telemetry Analysis")
	fmt.Println("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
	fmt.Println()
	fmt.Printf("   Samples: %d\n", len(snapshots))
	fmt.Printf("   Avg Latency: %.2fms (max: %.2fms)\n", avgLatency, maxLatency)
	fmt.Printf("   Avg Connections: %.0f (max: %d)\n", avgConnections, maxConnections)
	fmt.Println()
	fmt.Println("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
	fmt.Println()
}
