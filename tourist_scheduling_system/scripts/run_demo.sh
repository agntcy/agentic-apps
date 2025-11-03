#!/bin/bash
#
# A2A Summit Demo - Distributed Multi-Agent System
#
# Starts the scheduler A2A server and sends requests from tourist/guide agents.
# This demonstrates true A2A protocol communication between independent processes.

set -e

echo "===================================================="
echo "A2A Summit Demo - Multi-Agent Tourist Scheduling"
echo "===================================================="
echo ""

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is required but not found"
    exit 1
fi

# Set up virtual environment
VENV_DIR=".venv"

if [ ! -d "$VENV_DIR" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source "$VENV_DIR/bin/activate"

# Install/update dependencies
echo "📦 Installing dependencies..."
pip install -q --upgrade pip
pip install -q -r requirements.txt

echo ""
echo "1️⃣  Starting Scheduler Agent (A2A Server) on port 10000..."
echo "----------------------------------------------------"

# Start scheduler in background
python scheduler_agent.py --host localhost --port 10000 &
SCHEDULER_PID=$!

# Wait for scheduler to start
echo "⏳ Waiting for scheduler to initialize..."
sleep 3

# Check if scheduler is running
if ! kill -0 $SCHEDULER_PID 2>/dev/null; then
    echo "❌ Scheduler failed to start"
    exit 1
fi

echo "✅ Scheduler running (PID: $SCHEDULER_PID)"
echo ""

echo "2️⃣  Sending Guide Offers..."
echo "----------------------------------------------------"

# Send guide offers
python guide_agent.py --scheduler-url http://localhost:10000 --guide-id g1 &
GUIDE1_PID=$!

python guide_agent.py --scheduler-url http://localhost:10000 --guide-id g2 &
GUIDE2_PID=$!

python guide_agent.py --scheduler-url http://localhost:10000 --guide-id g3 &
GUIDE3_PID=$!

# Wait for guides to finish
wait $GUIDE1_PID $GUIDE2_PID $GUIDE3_PID

echo ""
echo "3️⃣  Sending Tourist Requests..."
echo "----------------------------------------------------"

# Send tourist requests
python tourist_agent.py --scheduler-url http://localhost:10000 --tourist-id t1 &
TOURIST1_PID=$!

python tourist_agent.py --scheduler-url http://localhost:10000 --tourist-id t2 &
TOURIST2_PID=$!

python tourist_agent.py --scheduler-url http://localhost:10000 --tourist-id t3 &
TOURIST3_PID=$!

# Wait for tourists to finish
wait $TOURIST1_PID $TOURIST2_PID $TOURIST3_PID

echo ""
echo "===================================================="
echo "✅ Demo Complete!"
echo "===================================================="
echo ""
echo "Scheduler agent is still running on http://localhost:10000"
echo "You can:"
echo "  - Send more requests using tourist_agent.py or guide_agent.py"
echo "  - Query the agent card: curl http://localhost:10000/.well-known/agent-card.json"
echo "  - Stop the scheduler: kill $SCHEDULER_PID"
echo ""
echo "To stop all processes: kill $SCHEDULER_PID"
echo ""
