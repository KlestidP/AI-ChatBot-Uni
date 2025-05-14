#!/bin/bash
# reset_bot.sh - Force reset a Telegram bot's connections
# Usage: ./reset_bot.sh YOUR_BOT_TOKEN

# Text formatting
BOLD='\033[1m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

if [ -z "$1" ]; then
    echo -e "${RED}${BOLD}Error:${NC} Please provide your bot token"
    echo "Usage: ./reset_bot.sh YOUR_BOT_TOKEN"
    exit 1
fi

TOKEN="$1"
echo -e "${BOLD}=== Telegram Bot Connection Reset ===${NC}"

# Step 1: Validate token
echo -e "${BLUE}Validating token...${NC}"
TOKEN_CHECK=$(curl -s "https://api.telegram.org/bot$TOKEN/getMe")

if ! echo "$TOKEN_CHECK" | grep -q "\"ok\":true"; then
    echo -e "${RED}Invalid token or cannot connect to Telegram API${NC}"
    echo "$TOKEN_CHECK"
    exit 1
fi

# Step 2: Remove webhook if set
echo -e "${BLUE}Removing any active webhooks...${NC}"
WEBHOOK_RESULT=$(curl -s "https://api.telegram.org/bot$TOKEN/deleteWebhook?drop_pending_updates=true")

if echo "$WEBHOOK_RESULT" | grep -q "\"ok\":true"; then
    echo -e "${GREEN}✓ Webhook removed successfully${NC}"
else
    echo -e "${RED}Failed to remove webhook:${NC}"
    echo "$WEBHOOK_RESULT"
fi

# Step 3: Reset getUpdates
echo -e "${BLUE}Resetting getUpdates connection...${NC}"
UPDATE_RESULT=$(curl -s "https://api.telegram.org/bot$TOKEN/getUpdates?offset=-1")

if echo "$UPDATE_RESULT" | grep -q "\"ok\":true"; then
    echo -e "${GREEN}✓ Update connection reset successfully${NC}"
else
    echo -e "${RED}Error resetting update connection:${NC}"
    echo "$UPDATE_RESULT"
fi

# Step 4: Final verification
echo -e "${BLUE}Verifying connection status...${NC}"
sleep 3 # Give Telegram servers time to process our requests

FINAL_CHECK=$(curl -s "https://api.telegram.org/bot$TOKEN/getUpdates?timeout=1")

if echo "$FINAL_CHECK" | grep -q "Conflict: terminated by other getUpdates"; then
    echo -e "${RED}${BOLD}! Connection conflict still detected${NC}"
    echo "The bot is still running somewhere else. You need to:"
    echo "1. Locate and stop all running instances of your bot"
    echo "2. Wait a few minutes for Telegram's servers to timeout the connection"
    echo "3. Run this reset script again"
else
    echo -e "${GREEN}${BOLD}✓ Connection reset successful!${NC}"
    echo "Your bot token is now free to use with a new instance"
fi

echo -e "${BOLD}=== Reset Complete ===${NC}"
