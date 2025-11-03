#!/bin/bash

# A2A Summit Demo - Multi-Agent System with Real-time UI
# This script starts all agents in the tourist scheduling system:
# 1. UI Agent (web dashboard + A2A agent)
# 2. Scheduler Agent (A2A agent)
# 3. Main demo (tourist and guide agents with in-memory bus)

set -e

echo "🚀 Starting A2A Summit Demo with Real-time UI Dashboard"
echo "======================================================="

# Function to cleanup background processes on exit
cleanup() {
    echo "🛑 Stopping all agents..."
    kill $(jobs -p) 2>/dev/null || true
    wait
    echo "✅ All agents stopped"
}
trap cleanup EXIT

# Start UI Agent (web dashboard on port 10001, A2A agent on port 10002)
echo "📊 Starting UI Agent..."
python ui_agent.py --host localhost --port 10001 --a2a-port 10002 &
UI_PID=$!

# Wait a moment for UI agent to start
sleep 2

# Start Scheduler Agent (A2A agent on port 10000)
echo "⚙️  Starting Scheduler Agent..."
python scheduler_agent.py --host localhost --port 10000 &
SCHEDULER_PID=$!

# Wait a moment for scheduler to start
sleep 2

# Start main demo (tourist and guide agents with in-memory messaging)
echo "🎯 Starting Tourist & Guide Agents (main demo)..."
python main.py &
MAIN_PID=$!

echo ""
echo "🌟 All agents started successfully!"
echo "📊 Web Dashboard: http://localhost:10001"
echo "🔧 UI Agent A2A:  http://localhost:10002"
echo "🗓️  Scheduler A2A: http://localhost:10000"
echo ""
echo "The dashboard will show real-time updates as the system runs."
echo "Press Ctrl+C to stop all agents."
echo ""

# Wait for all background processes
wait