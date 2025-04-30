#!/bin/bash
#
# Enhanced start script for Pokémon battles with comprehensive logging and error handling
#

# Set color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Default settings
DEBUG=0
BATTLE_SCRIPT="enhanced_run_battles.py"
SERVER_DIRECTORY="pokemon-showdown"
MAX_RETRIES=3
TIMEOUT=60
PASS_ARGS=""

# Create timestamp for log files
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
MAIN_LOG="battle_${TIMESTAMP}.log"
SERVER_LOG="server_${TIMESTAMP}.log"
DEBUG_LOG="debug_${TIMESTAMP}.log"

# Create logs directory if it doesn't exist
mkdir -p logs

# Function to print a formatted log message
log() {
    local level=$1
    local message=$2
    local color=$NC
    
    case $level in
        "INFO") color=$GREEN ;;
        "WARN") color=$YELLOW ;;
        "ERROR") color=$RED ;;
        "DEBUG") color=$CYAN ;;
    esac
    
    local timestamp=$(date +"%Y-%m-%d %H:%M:%S")
    echo -e "${color}[${timestamp}] [${level}] ${message}${NC}"
    echo "[${timestamp}] [${level}] ${message}" >> "logs/${MAIN_LOG}"
    
    # Also log to debug log if in debug mode
    if [ $DEBUG -eq 1 ] && [ "$level" == "DEBUG" ]; then
        echo "[${timestamp}] [${level}] ${message}" >> "logs/${DEBUG_LOG}"
    fi
}

# Function to print usage information
usage() {
    echo "Enhanced Pokémon Battle Start Script"
    echo ""
    echo "Usage: $0 [options] [-- battle_args]"
    echo ""
    echo "Options:"
    echo "  --debug              Enable debug mode with verbose logging"
    echo "  --help               Display this help message"
    echo "  --timeout SECONDS    Maximum time to wait for server to start (default: 60)"
    echo "  --retries COUNT      Number of retries if server fails to start (default: 3)"
    echo "  --clean              Clean all logs and server data before starting"
    echo ""
    echo "Arguments after -- will be passed to the battle script."
    echo "Example: $0 --debug -- --agent1 openai --agent2 anthropic --battles 5"
    exit 0
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --debug)
            DEBUG=1
            export DEBUG=1
            log "INFO" "Debug mode enabled"
            shift
            ;;
        --help)
            usage
            shift
            ;;
        --timeout)
            TIMEOUT=$2
            log "INFO" "Timeout set to $TIMEOUT seconds"
            shift 2
            ;;
        --retries)
            MAX_RETRIES=$2
            log "INFO" "Max retries set to $MAX_RETRIES"
            shift 2
            ;;
        --clean)
            log "INFO" "Will clean all logs and server data before starting"
            CLEAN=1
            shift
            ;;
        --)
            shift
            PASS_ARGS="$@"
            break
            ;;
        *)
            log "WARN" "Unknown option: $1"
            shift
            ;;
    esac
done

log "INFO" "Starting enhanced Pokémon battle script"
log "INFO" "Main log: logs/${MAIN_LOG}"
log "INFO" "Server log: logs/${SERVER_LOG}"
if [ $DEBUG -eq 1 ]; then
    log "INFO" "Debug log: logs/${DEBUG_LOG}"
fi

# Validate environment
log "INFO" "Validating environment..."

# Check if Node.js is installed
if ! command -v node &> /dev/null; then
    log "ERROR" "Node.js is required but not found in PATH"
    exit 1
fi

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    log "ERROR" "Python 3 is required but not found in PATH"
    exit 1
fi

# Check if server directory exists
if [ ! -d "$SERVER_DIRECTORY" ]; then
    log "ERROR" "Server directory not found: $SERVER_DIRECTORY"
    log "ERROR" "Please run setup_server.sh first"
    exit 1
fi

# Check if battle script exists
if [ ! -f "$BATTLE_SCRIPT" ]; then
    log "ERROR" "Battle script not found: $BATTLE_SCRIPT"
    exit 1
fi

# Clean up function for graceful termination
cleanup() {
    log "INFO" "Cleaning up resources..."
    
    # Kill any running Pokémon Showdown server
    if pgrep -f "node pokemon-showdown" > /dev/null; then
        log "INFO" "Shutting down Pokémon Showdown server"
        pkill -f "node pokemon-showdown" || true
    fi
    
    # Kill any Python processes we started
    if [ -n "$PYTHON_PID" ]; then
        log "INFO" "Terminating Python process (PID: $PYTHON_PID)"
        kill $PYTHON_PID 2>/dev/null || true
    fi
    
    log "INFO" "Cleanup completed"
}

# Register cleanup function for script termination
trap cleanup EXIT INT TERM

# Function to clean all logs and server data
clean_all() {
    log "INFO" "Cleaning all logs and server data..."
    
    # Kill any running server
    pkill -f "node pokemon-showdown" || true
    
    # Clean server logs
    if [ -d "${SERVER_DIRECTORY}/logs" ]; then
        log "DEBUG" "Removing server logs"
        rm -rf ${SERVER_DIRECTORY}/logs/*
    fi
    
    # Create required log directories
    log "DEBUG" "Creating log directories"
    mkdir -p ${SERVER_DIRECTORY}/logs/repl
    mkdir -p ${SERVER_DIRECTORY}/logs/chat
    mkdir -p ${SERVER_DIRECTORY}/logs/modlog
    mkdir -p ${SERVER_DIRECTORY}/logs/repl/abusemonitor-local-7520
    mkdir -p ${SERVER_DIRECTORY}/logs/repl/abusemonitor-remote-7521
    
    # Set correct permissions
    chmod -R 755 ${SERVER_DIRECTORY}/logs
    
    log "INFO" "Clean completed"
}

# Clean if requested
if [ -n "$CLEAN" ]; then
    clean_all
fi

# Ensure necessary log directories exist
mkdir -p ${SERVER_DIRECTORY}/logs/repl
mkdir -p ${SERVER_DIRECTORY}/logs/chat
mkdir -p ${SERVER_DIRECTORY}/logs/modlog
mkdir -p ${SERVER_DIRECTORY}/logs/repl/abusemonitor-local-7520
mkdir -p ${SERVER_DIRECTORY}/logs/repl/abusemonitor-remote-7521

# Start the Pokémon Showdown server
start_server() {
    log "INFO" "Starting Pokémon Showdown server..."
    
    # Kill any existing servers first
    if pgrep -f "node pokemon-showdown" > /dev/null; then
        log "WARN" "Found existing Pokémon Showdown server. Killing it..."
        pkill -f "node pokemon-showdown" || true
        sleep 2
    fi
    
    # Start the server with output redirection to our log file
    cd ${SERVER_DIRECTORY} && node pokemon-showdown start --no-security > "../logs/${SERVER_LOG}" 2>&1 &
    SERVER_PID=$!
    
    log "DEBUG" "Server started with PID: $SERVER_PID"
    
    # Wait for server to start
    log "INFO" "Waiting for server to initialize (timeout: ${TIMEOUT}s)..."
    for i in $(seq 1 $TIMEOUT); do
        if ! kill -0 $SERVER_PID 2>/dev/null; then
            log "ERROR" "Server process died unexpectedly"
            return 1
        fi
        
        # Check if the server is running by looking for patterns in the log file
        if grep -q "server started" "../logs/${SERVER_LOG}" 2>/dev/null; then
            log "INFO" "Server started successfully"
            cd ..
            return 0
        fi
        
        sleep 1
        if [ $((i % 5)) -eq 0 ]; then
            log "DEBUG" "Still waiting for server to start ($i/${TIMEOUT}s)"
        fi
    done
    
    log "ERROR" "Server failed to start within timeout period"
    cd ..
    return 1
}

# Function to run the battle script
run_battles() {
    log "INFO" "Starting battles with command: python3 $BATTLE_SCRIPT $PASS_ARGS"
    
    if [ $DEBUG -eq 1 ]; then
        log "DEBUG" "Running in debug mode with arguments: $PASS_ARGS"
        python3 $BATTLE_SCRIPT --debug $PASS_ARGS &
    else
        python3 $BATTLE_SCRIPT $PASS_ARGS &
    fi
    
    PYTHON_PID=$!
    log "DEBUG" "Battle script running with PID: $PYTHON_PID"
    
    # Wait for the battle script to complete
    if wait $PYTHON_PID; then
        log "INFO" "Battle script completed successfully"
        return 0
    else
        log "ERROR" "Battle script failed with exit code $?"
        return 1
    fi
}

# Main execution flow
RETRY_COUNT=0
SUCCESS=0

while [ $RETRY_COUNT -lt $MAX_RETRIES ] && [ $SUCCESS -eq 0 ]; do
    if [ $RETRY_COUNT -gt 0 ]; then
        log "WARN" "Retry attempt $RETRY_COUNT of $MAX_RETRIES"
    fi
    
    # Start server
    if start_server; then
        # Run battles
        if run_battles; then
            SUCCESS=1
        else
            log "ERROR" "Battle run failed, retrying..."
            RETRY_COUNT=$((RETRY_COUNT + 1))
            
            # Small delay before retrying
            sleep 2
        fi
    else
        log "ERROR" "Server start failed, retrying..."
        RETRY_COUNT=$((RETRY_COUNT + 1))
        
        # Small delay before retrying
        sleep 5
    fi
done

if [ $SUCCESS -eq 1 ]; then
    log "INFO" "Battles completed successfully"
    exit 0
else
    log "ERROR" "Failed to complete battles after $MAX_RETRIES attempts"
    exit 1
fi