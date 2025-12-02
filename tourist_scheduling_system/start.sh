#!/usr/bin/env bash
# Enhanced launcher for Multi-Agent Tourist Scheduling System
# Provides argument parsing, sane defaults, optional autonomous mode,
# and graceful cleanup. Pass through extra args to underlying script.

set -euo pipefail
IFS=$'\n\t'

ROOT_DIR=$(cd "$(dirname "$0")" && pwd)
RUNNER_SCRIPT="${ROOT_DIR}/scripts/run_with_ui.sh"

# Defaults
SCHED_PORT=10010
UI_WEB_PORT=10011
UI_A2A_PORT=10012
AUTONOMOUS=true
AUTO_DURATION=20
GUIDE_MIN_INTERVAL=1
GUIDE_MAX_INTERVAL=5
TOURIST_MIN_INTERVAL=1
TOURIST_MAX_INTERVAL=5

GUIDE_IDS=(guide-champs-elisees guide-louvre guide-eiffel-tower guide-notre-dame guide-montmartre)
TOURIST_IDS=(tourist-alice tourist-bob tourist-charlie tourist-diana tourist-ellen tourist-frank)

COLOR_INFO='\033[1;34m'; COLOR_WARN='\033[1;33m'; COLOR_ERR='\033[1;31m'; COLOR_OK='\033[1;32m'; COLOR_RESET='\033[0m'
log() { echo -e "${COLOR_INFO}[start.sh]${COLOR_RESET} $*"; }
warn() { echo -e "${COLOR_WARN}[start.sh] WARN:${COLOR_RESET} $*" >&2; }
err()  { echo -e "${COLOR_ERR}[start.sh] ERROR:${COLOR_RESET} $*" >&2; }
ok()   { echo -e "${COLOR_OK}[start.sh]${COLOR_RESET} $*"; }

usage() {
cat <<EOF
Usage: $0 [options] [-- extra runner args]
        --scheduler-port N             Scheduler port (default: $SCHED_PORT)
        --ui-web-port N                UI web port (default: $UI_WEB_PORT)
        --ui-a2a-port N                UI A2A port (default: $UI_A2A_PORT)
        --autonomous / --no-autonomous Enable or disable autonomous agents (default: $AUTONOMOUS)
        --auto-duration MIN            Autonomous duration minutes (default: $AUTO_DURATION)
        --guide-id ID                  Add guide ID (repeatable)
        --tourist-id ID                Add tourist ID (repeatable)
        --auto-limit-guides N          Limit number of autonomous guide agents (truncate list)
        --auto-limit-tourists N        Limit number of autonomous tourist agents (truncate list)
        --auto-guide-min-interval S    Min seconds between guide offers (default: $GUIDE_MIN_INTERVAL)
        --auto-guide-max-interval S    Max seconds between guide offers (default: $GUIDE_MAX_INTERVAL)
        --auto-tourist-min-interval S  Min seconds between tourist requests (default: $TOURIST_MIN_INTERVAL)
        --auto-tourist-max-interval S  Max seconds between tourist requests (default: $TOURIST_MAX_INTERVAL)
        --help                         Show help
EOF
}

PASS_ARGS=()
AUTO_LIMIT_GUIDES=""
AUTO_LIMIT_TOURISTS=""
while [[ $# -gt 0 ]]; do
        case "$1" in
                --scheduler-port) SCHED_PORT=$2; shift 2;;
                --ui-web-port) UI_WEB_PORT=$2; shift 2;;
                --ui-a2a-port) UI_A2A_PORT=$2; shift 2;;
                --autonomous) AUTONOMOUS=true; shift;;
                --no-autonomous) AUTONOMOUS=false; shift;;
                --auto-duration) AUTO_DURATION=$2; shift 2;;
                --guide-id) GUIDE_IDS+=($2); shift 2;;
                --tourist-id) TOURIST_IDS+=($2); shift 2;;
                --auto-limit-guides) AUTO_LIMIT_GUIDES=$2; shift 2;;
                --auto-limit-tourists) AUTO_LIMIT_TOURISTS=$2; shift 2;;
                --auto-guide-min-interval) GUIDE_MIN_INTERVAL=$2; shift 2;;
                --auto-guide-max-interval) GUIDE_MAX_INTERVAL=$2; shift 2;;
                --auto-tourist-min-interval) TOURIST_MIN_INTERVAL=$2; shift 2;;
                --auto-tourist-max-interval) TOURIST_MAX_INTERVAL=$2; shift 2;;
                --help|-h) usage; exit 0;;
                --) shift; PASS_ARGS=("$@"); break;;
                *) PASS_ARGS+=("$1"); shift;;
        esac
done

for p in $SCHED_PORT $UI_WEB_PORT $UI_A2A_PORT; do
        [[ $p =~ ^[0-9]+$ ]] || { err "Port '$p' must be numeric"; exit 1; }
done

[[ -x "$RUNNER_SCRIPT" ]] || { err "Runner not executable: $RUNNER_SCRIPT"; exit 1; }

log "Scheduler:$SCHED_PORT UI:$UI_WEB_PORT/$UI_A2A_PORT Autonomous:$AUTONOMOUS Duration:${AUTO_DURATION}m"
if [[ -n "$AUTO_LIMIT_GUIDES" ]]; then
        if [[ ! $AUTO_LIMIT_GUIDES =~ ^[0-9]+$ ]]; then err "--auto-limit-guides must be numeric"; exit 1; fi
        if (( AUTO_LIMIT_GUIDES < ${#GUIDE_IDS[@]} )); then
                GUIDE_IDS=("${GUIDE_IDS[@]:0:$AUTO_LIMIT_GUIDES}")
        fi
fi
if [[ -n "$AUTO_LIMIT_TOURISTS" ]]; then
        if [[ ! $AUTO_LIMIT_TOURISTS =~ ^[0-9]+$ ]]; then err "--auto-limit-tourists must be numeric"; exit 1; fi
        if (( AUTO_LIMIT_TOURISTS < ${#TOURIST_IDS[@]} )); then
                TOURIST_IDS=("${TOURIST_IDS[@]:0:$AUTO_LIMIT_TOURISTS}")
        fi
fi

log "Guides (${#GUIDE_IDS[@]}): ${GUIDE_IDS[*]}"
log "Tourists (${#TOURIST_IDS[@]}): ${TOURIST_IDS[*]}"

RUN_ARGS=(--scheduler-port "$SCHED_PORT" --ui-web-port "$UI_WEB_PORT" --ui-a2a-port "$UI_A2A_PORT")
if [[ "$AUTONOMOUS" == true ]]; then
        RUN_ARGS+=(--autonomous --auto-duration "$AUTO_DURATION" --auto-guide-min-interval "$GUIDE_MIN_INTERVAL" --auto-guide-max-interval "$GUIDE_MAX_INTERVAL" --auto-tourist-min-interval "$TOURIST_MIN_INTERVAL" --auto-tourist-max-interval "$TOURIST_MAX_INTERVAL")
        # Pass aggregated lists via plural flags (space-separated). run_with_ui.sh will parse these into arrays.
        # Because IFS is set to newlines globally, ${ARRAY[*]} joins with newlines. Reconstruct space-separated lists explicitly.
        GUIDE_LIST="$(printf '%s ' "${GUIDE_IDS[@]}")"; GUIDE_LIST="${GUIDE_LIST% }"
        TOURIST_LIST="$(printf '%s ' "${TOURIST_IDS[@]}")"; TOURIST_LIST="${TOURIST_LIST% }"
        RUN_ARGS+=(--auto-guide-ids "$GUIDE_LIST" --auto-tourist-ids "$TOURIST_LIST")
fi

cleanup() { warn "Termination received; letting underlying script manage child processes."; }
trap cleanup INT TERM

log "Launching demo..."
"$RUNNER_SCRIPT" "${RUN_ARGS[@]}" ${PASS_ARGS[@]:-}
ok "Launch complete (background processes may continue)."
