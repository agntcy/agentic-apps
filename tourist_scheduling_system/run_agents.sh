#!/bin/bash
#
# A2A Summit Demo - Reorganized Structure Runner
# Runs agents with proper Python path setup
#

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC_DIR="$SCRIPT_DIR/src"

# Add src directory to Python path
export PYTHONPATH="$SRC_DIR:$PYTHONPATH"

echo "🚀 A2A Summit Demo - Reorganized Structure"
echo "📁 Source directory: $SRC_DIR"
echo "🐍 Python path: $PYTHONPATH"
echo ""

# Function to run a command with proper path
run_with_path() {
    echo "▶️  Running: $@"
    PYTHONPATH="$SRC_DIR:$PYTHONPATH" "$@"
}

# Check command line arguments
case "$1" in
    "scheduler")
        echo "🗓️  Starting Scheduler Agent..."
        run_with_path python "$SRC_DIR/agents/scheduler_agent.py" --host localhost --port 10010
        ;;
    "ui")
        echo "🖥️  Starting UI Agent..."
        run_with_path python "$SRC_DIR/agents/ui_agent.py" --host localhost --port 10011 --a2a-port 10012
        ;;
    "guide")
        GUIDE_ID="${2:-guide-demo}"
        echo "🗺️  Starting Guide Agent ($GUIDE_ID)..."
        run_with_path python "$SRC_DIR/agents/guide_agent.py" --scheduler-url http://localhost:10010 --guide-id "$GUIDE_ID"
        ;;
    "tourist")
        TOURIST_ID="${2:-tourist-demo}"
        echo "🧳 Starting Tourist Agent ($TOURIST_ID)..."
        run_with_path python "$SRC_DIR/agents/tourist_agent.py" --scheduler-url http://localhost:10010 --tourist-id "$TOURIST_ID"
        ;;
    "autonomous-guide")
        GUIDE_ID="${2:-guide-ai-demo}"
        echo "🤖 Starting Autonomous Guide Agent ($GUIDE_ID)..."
        source ~/.env-phoenix 2>/dev/null || echo "⚠️  Note: Phoenix environment not available"
        run_with_path python "$SRC_DIR/agents/autonomous_guide_agent.py" --scheduler-url http://localhost:10010 --guide-id "$GUIDE_ID" --duration 5
        ;;
    "autonomous-tourist")
        TOURIST_ID="${2:-tourist-ai-demo}"
        echo "🤖 Starting Autonomous Tourist Agent ($TOURIST_ID)..."
        source ~/.env-phoenix 2>/dev/null || echo "⚠️  Note: Phoenix environment not available"
        run_with_path python "$SRC_DIR/agents/autonomous_tourist_agent.py" --scheduler-url http://localhost:10010 --tourist-id "$TOURIST_ID" --duration 5
        ;;
    "demo")
        echo "🎬 Running Full Demo..."
        echo "1. Starting Scheduler..."
        run_with_path python "$SRC_DIR/agents/scheduler_agent.py" --host localhost --port 10010 &
        SCHEDULER_PID=$!
        sleep 3

        echo "2. Starting UI Agent..."
        run_with_path python "$SRC_DIR/agents/ui_agent.py" --host localhost --port 10011 --a2a-port 10012 &
        UI_PID=$!
        sleep 2

        echo "3. Sending Guide Offers..."
        run_with_path python "$SRC_DIR/agents/guide_agent.py" --scheduler-url http://localhost:10010 --guide-id "florence" &
        run_with_path python "$SRC_DIR/agents/guide_agent.py" --scheduler-url http://localhost:10010 --guide-id "marco" &

        echo "4. Sending Tourist Requests..."
        sleep 1
        run_with_path python "$SRC_DIR/agents/tourist_agent.py" --scheduler-url http://localhost:10010 --tourist-id "alice" &
        run_with_path python "$SRC_DIR/agents/tourist_agent.py" --scheduler-url http://localhost:10010 --tourist-id "bob" &

        echo ""
        echo "✅ Demo running! Check the dashboard at: http://localhost:10011"
        echo "Press Ctrl+C to stop all agents..."

        # Wait for user interruption
        trap "echo ''; echo '🛑 Stopping all agents...'; kill $SCHEDULER_PID $UI_PID 2>/dev/null; exit 0" INT
        wait
        ;;
    "autonomous-demo")
        echo "🤖 Running Autonomous LLM Demo..."
        source ~/.env-phoenix 2>/dev/null || echo "⚠️  Note: Phoenix environment not available"
        run_with_path python "$SCRIPT_DIR/scripts/run_autonomous_demo.py"
        ;;
    *)
        echo "Usage: $0 {scheduler|ui|guide|tourist|autonomous-guide|autonomous-tourist|demo|autonomous-demo} [agent-id]"
        echo ""
        echo "Examples:"
        echo "  $0 scheduler                    # Start scheduler agent"
        echo "  $0 ui                          # Start UI dashboard"
        echo "  $0 guide florence              # Start guide agent with ID 'florence'"
        echo "  $0 tourist alice               # Start tourist agent with ID 'alice'"
        echo "  $0 autonomous-guide ai-marco   # Start LLM-powered guide"
        echo "  $0 demo                        # Run full basic demo"
        echo "  $0 autonomous-demo             # Run LLM-powered demo"
        echo ""
        echo "Dashboard URL: http://localhost:10011"
        exit 1
        ;;
esac