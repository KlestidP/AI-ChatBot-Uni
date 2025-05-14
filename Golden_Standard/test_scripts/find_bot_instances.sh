#!/bin/bash
# find_bot_instances.sh - Locate running instances of your bot
# Usage: ./find_bot_instances.sh [optional: bot name]

# Text formatting
BOLD='\033[1m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

BOT_NAME=$1
if [ -n "$BOT_NAME" ]; then
    echo -e "${BOLD}Searching for bot: ${BLUE}$BOT_NAME${NC}"
else
    echo -e "${BOLD}Searching for all potential bot instances${NC}"
    BOT_NAME="bot|telegram"
fi

echo -e "${BOLD}=== Bot Instance Scanner ===${NC}"
echo -e "${BLUE}This script will attempt to find running instances of your Telegram bot${NC}"
echo

# Function to display section header
section() {
    echo -e "${BOLD}$1${NC}"
    echo -e "${BLUE}${2-Scanning...}${NC}"
}

# Track if we found anything
FOUND_ANY=0

# Step 1: Check for Python processes
section "Step 1: Checking for Python processes"
PYTHON_PROCESSES=$(ps aux | grep -E "python.*($BOT_NAME)" | grep -v grep | grep -v "find_bot_instances" || echo "")

if [ -n "$PYTHON_PROCESSES" ]; then
    echo -e "${YELLOW}${BOLD}! Found potential bot processes:${NC}"
    echo "$PYTHON_PROCESSES"
    FOUND_ANY=1
    
    # Highlight the PIDs
    PIDS=$(echo "$PYTHON_PROCESSES" | awk '{print $2}')
    echo
    echo -e "${BOLD}To stop these processes, run:${NC}"
    for PID in $PIDS; do
        echo "kill -15 $PID   # Graceful stop"
        echo "# or"
        echo "kill -9 $PID    # Force stop"
        echo
    done
else
    echo -e "${GREEN}✓ No matching Python processes found${NC}"
fi

echo

# Step 2: Check for screen/tmux sessions
section "Step 2: Checking for terminal sessions (screen/tmux)"
SCREEN_SESSIONS=""
TMUX_SESSIONS=""

# Check for screen
if command -v screen &> /dev/null; then
    SCREEN_SESSIONS=$(screen -ls | grep -E "($BOT_NAME)" || echo "")
    if [ -n "$SCREEN_SESSIONS" ]; then
        echo -e "${YELLOW}${BOLD}! Found potential screen sessions:${NC}"
        echo "$SCREEN_SESSIONS"
        FOUND_ANY=1
        
        # Extract session names
        SESSION_NAMES=$(echo "$SCREEN_SESSIONS" | grep -o '[0-9]*\.\S*' | cut -d. -f2)
        echo
        echo -e "${BOLD}To stop these sessions:${NC}"
        for NAME in $SESSION_NAMES; do
            echo "screen -r $NAME   # Reconnect to the session"
            echo "# Then press Ctrl+C to stop the bot"
            echo "# Type 'exit' to close the session"
            echo
        done
    else
        echo -e "${GREEN}✓ No matching screen sessions found${NC}"
    fi
else
    echo "screen command not available"
fi

# Check for tmux
if command -v tmux &> /dev/null; then
    TMUX_SESSIONS=$(tmux ls 2>/dev/null | grep -E "($BOT_NAME)" || echo "")
    if [ -n "$TMUX_SESSIONS" ]; then
        echo -e "${YELLOW}${BOLD}! Found potential tmux sessions:${NC}"
        echo "$TMUX_SESSIONS"
        FOUND_ANY=1
        
        # Extract session names
        SESSION_NAMES=$(echo "$TMUX_SESSIONS" | cut -d: -f1)
        echo
        echo -e "${BOLD}To stop these sessions:${NC}"
        for NAME in $SESSION_NAMES; do
            echo "tmux attach -t $NAME   # Reconnect to the session"
            echo "# Then press Ctrl+C to stop the bot"
            echo "# Type 'exit' to close the session"
            echo
        done
    else
        echo -e "${GREEN}✓ No matching tmux sessions found${NC}"
    fi
else
    echo "tmux command not available"
fi

echo

# Step 3: Check for Docker containers
section "Step 3: Checking for Docker containers"
if command -v docker &> /dev/null; then
    DOCKER_CONTAINERS=$(docker ps | grep -E "($BOT_NAME)" || echo "")
    if [ -n "$DOCKER_CONTAINERS" ]; then
        echo -e "${YELLOW}${BOLD}! Found potential Docker containers:${NC}"
        echo "$DOCKER_CONTAINERS"
        FOUND_ANY=1
        
        # Extract container IDs
        CONTAINER_IDS=$(echo "$DOCKER_CONTAINERS" | awk '{print $1}')
        echo
        echo -e "${BOLD}To stop these containers:${NC}"
        for ID in $CONTAINER_IDS; do
            echo "docker stop $ID   # Graceful stop"
            echo "docker rm $ID     # Remove the container"
            echo
        done
    else
        echo -e "${GREEN}✓ No matching Docker containers found${NC}"
    fi
    
    # Also check for stopped containers
    STOPPED_CONTAINERS=$(docker ps -a | grep -E "($BOT_NAME)" | grep -v "Up " || echo "")
    if [ -n "$STOPPED_CONTAINERS" ]; then
        echo -e "${BLUE}Note: Found stopped containers that match the pattern:${NC}"
        echo "$STOPPED_CONTAINERS"
        echo
    fi
else
    echo "Docker command not available"
fi

echo

# Step 4: Check for system services
section "Step 4: Checking for system services"
if command -v systemctl &> /dev/null; then
    SYSTEMD_SERVICES=$(systemctl list-units --type=service | grep -E "($BOT_NAME)" || echo "")
    if [ -n "$SYSTEMD_SERVICES" ]; then
        echo -e "${YELLOW}${BOLD}! Found potential systemd services:${NC}"
        echo "$SYSTEMD_SERVICES"
        FOUND_ANY=1
        
        # Extract service names
        SERVICE_NAMES=$(echo "$SYSTEMD_SERVICES" | awk '{print $1}')
        echo
        echo -e "${BOLD}To stop these services:${NC}"
        for NAME in $SERVICE_NAMES; do
            echo "sudo systemctl stop $NAME   # Stop the service"
            echo "sudo systemctl disable $NAME # Prevent from starting at boot"
            echo
        done
    else
        echo -e "${GREEN}✓ No matching systemd services found${NC}"
    fi
elif command -v service &> /dev/null; then
    SYSV_SERVICES=$(service --status-all 2>&1 | grep -E "($BOT_NAME)" || echo "")
    if [ -n "$SYSV_SERVICES" ]; then
        echo -e "${YELLOW}${BOLD}! Found potential SysV services:${NC}"
        echo "$SYSV_SERVICES"
        FOUND_ANY=1
        
        # Extract service names
        SERVICE_NAMES=$(echo "$SYSV_SERVICES" | awk '{print $4}')
        echo
        echo -e "${BOLD}To stop these services:${NC}"
        for NAME in $SERVICE_NAMES; do
            echo "sudo service $NAME stop   # Stop the service"
            echo
        done
    else
        echo -e "${GREEN}✓ No matching SysV services found${NC}"
    fi
else
    echo "systemctl or service commands not available"
fi

echo

# Step 5: Network connections
section "Step 5: Checking for network connections to Telegram API"
if command -v netstat &> /dev/null || command -v ss &> /dev/null; then
    if command -v netstat &> /dev/null; then
        TELEGRAM_CONNECTIONS=$(netstat -tunapl 2>/dev/null | grep -E "api\.telegram\.org" || echo "")
    else
        TELEGRAM_CONNECTIONS=$(ss -tunapl 2>/dev/null | grep -E "api\.telegram\.org" || echo "")
    fi
    
    if [ -n "$TELEGRAM_CONNECTIONS" ]; then
        echo -e "${YELLOW}${BOLD}! Found active connections to Telegram API:${NC}"
        echo "$TELEGRAM_CONNECTIONS"
        FOUND_ANY=1
        
        # Extract process info if available
        PIDS=$(echo "$TELEGRAM_CONNECTIONS" | grep -o 'pid=[0-9]*' | cut -d= -f2 || echo "")
        
        if [ -n "$PIDS" ]; then
            echo
            echo -e "${BOLD}Associated processes:${NC}"
            for PID in $PIDS; do
                ps -p $PID -o pid,user,command || echo "Process $PID not found"
                echo
            done
            
            echo -e "${BOLD}To stop these processes:${NC}"
            for PID in $PIDS; do
                echo "kill -15 $PID   # Graceful stop"
                echo "# or"
                echo "kill -9 $PID    # Force stop"
                echo
            done
        fi
    else
        echo -e "${GREEN}✓ No active connections to Telegram API found${NC}"
    fi
else
    echo "netstat or ss commands not available"
fi

echo

# Summary
echo -e "${BOLD}=== SUMMARY ===${NC}"
if [ $FOUND_ANY -eq 1 ]; then
    echo -e "${YELLOW}${BOLD}→ Potential bot instances were found on this system${NC}"
    echo "Review the output above and take appropriate action to stop any running instances"
    echo "After stopping all instances, use the reset_bot.sh script to reset your bot's connection with Telegram"
else
    echo -e "${GREEN}${BOLD}→ No obvious bot instances found on this system${NC}"
    echo "If you're still experiencing connection conflicts, your bot may be running on a different system"
    echo "Possible locations to check:"
    echo "  - Cloud hosting services (AWS, Azure, Google Cloud, Heroku, etc.)"
    echo "  - VPS servers"
    echo "  - Other development machines"
    echo "  - Webhook servers (check with ./check_token_usage.sh YOUR_BOT_TOKEN)"
fi

echo
echo -e "${BOLD}=== Scan Complete ===${NC}"
