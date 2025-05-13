#!/bin/bash
# check_token_usage.sh - Check if a Telegram bot token is being used elsewhere
# Usage: ./check_token_usage.sh YOUR_BOT_TOKEN

# Text formatting
BOLD='\033[1m'
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

if [ -z "$1" ]; then
    echo -e "${RED}${BOLD}Error:${NC} Please provide your bot token"
    echo "Usage: ./check_token_usage.sh 8172075901:AAGiMkt7dPbEHg9xAH5F1_G7YHf8HKJWeIM"
    exit 1
fi

TOKEN="$1"
echo -e "${BOLD}=== Telegram Bot Token Usage Check ===${NC}"
echo -e "${BLUE}Starting comprehensive check for token activity...${NC}"
echo

# Step 1: Check basic token validity
echo -e "${BOLD}Step 1: Validating token...${NC}"
TOKEN_CHECK=$(curl -s "https://api.telegram.org/bot$TOKEN/getMe")

# Check if the token is valid
if echo "$TOKEN_CHECK" | grep -q "\"ok\":true"; then
    BOT_USERNAME=$(echo "$TOKEN_CHECK" | grep -o '"username":"[^"]*"' | cut -d'"' -f4)
    BOT_NAME=$(echo "$TOKEN_CHECK" | grep -o '"first_name":"[^"]*"' | cut -d'"' -f4)
    BOT_ID=$(echo "$TOKEN_CHECK" | grep -o '"id":[0-9]*' | cut -d':' -f2)
    
    echo -e "${GREEN}✓ Token is valid${NC}"
    echo -e "   Bot Name: ${BOLD}$BOT_NAME${NC}"
    echo -e "   Username: @$BOT_USERNAME"
    echo -e "   Bot ID: $BOT_ID"
else
    echo -e "${RED}✗ Token is invalid or cannot connect to Telegram API${NC}"
    echo "$TOKEN_CHECK"
    exit 1
fi

echo

# Step 2: Check webhook status
echo -e "${BOLD}Step 2: Checking webhook configuration...${NC}"
WEBHOOK_INFO=$(curl -s "https://api.telegram.org/bot$TOKEN/getWebhookInfo")

# Check if webhook is set
if echo "$WEBHOOK_INFO" | grep -q '"url":""'; then
    echo -e "${GREEN}✓ No webhook is set (bot is using polling mode)${NC}"
else
    WEBHOOK_URL=$(echo "$WEBHOOK_INFO" | grep -o '"url":"[^"]*"' | cut -d'"' -f4)
    echo -e "${YELLOW}! Webhook is set to: ${BOLD}$WEBHOOK_URL${NC}"
    echo -e "  This indicates the bot is running on a server at this URL"
    
    # Get more webhook details
    PENDING_UPDATES=$(echo "$WEBHOOK_INFO" | grep -o '"pending_update_count":[0-9]*' | cut -d':' -f2)
    LAST_ERROR=$(echo "$WEBHOOK_INFO" | grep -o '"last_error_message":"[^"]*"' | cut -d'"' -f4)
    
    if [ "$PENDING_UPDATES" -gt 0 ]; then
        echo -e "${YELLOW}! There are $PENDING_UPDATES pending updates waiting to be processed${NC}"
    else
        echo -e "  No pending updates"
    fi
    
    if [ -n "$LAST_ERROR" ]; then
        echo -e "${RED}! Last webhook error: $LAST_ERROR${NC}"
    fi
fi

echo

# Step 3: Check for recent updates (activity)
echo -e "${BOLD}Step 3: Checking for recent bot activity...${NC}"
echo -e "${BLUE}Attempting to fetch updates (this may take a few seconds)...${NC}"

UPDATE_CHECK=$(curl -s "https://api.telegram.org/bot$TOKEN/getUpdates?limit=1&timeout=3")

if echo "$UPDATE_CHECK" | grep -q "\"ok\":true"; then
    if echo "$UPDATE_CHECK" | grep -q '"result":\[\]'; then
        echo -e "${GREEN}✓ No recent updates detected${NC}"
        echo "  This suggests the bot is either inactive or updates are being processed by another instance"
    else
        # Get the most recent update time
        UPDATE_TIME=$(echo "$UPDATE_CHECK" | grep -o '"date":[0-9]*' | head -1 | cut -d':' -f2)
        CURRENT_TIME=$(date +%s)
        TIME_DIFF=$((CURRENT_TIME - UPDATE_TIME))
        
        # Format time difference
        if [ $TIME_DIFF -lt 60 ]; then
            TIME_AGO="$TIME_DIFF seconds ago"
        elif [ $TIME_DIFF -lt 3600 ]; then
            MINS=$((TIME_DIFF / 60))
            TIME_AGO="$MINS minutes ago"
        elif [ $TIME_DIFF -lt 86400 ]; then
            HOURS=$((TIME_DIFF / 3600))
            TIME_AGO="$HOURS hours ago"
        else
            DAYS=$((TIME_DIFF / 86400))
            TIME_AGO="$DAYS days ago"
        fi
        
        echo -e "${YELLOW}! Recent activity detected: Last update was ${BOLD}$TIME_AGO${NC}"
        echo "  This indicates users are interacting with the bot"
        
        # Check if the update was processed (if we can get it, it wasn't processed)
        echo -e "${YELLOW}! These updates are not being processed by another instance${NC}"
        echo "  If they were being processed, we wouldn't be able to fetch them"
    fi
else
    echo -e "${RED}✗ Error checking for updates:${NC}"
    ERROR_DESC=$(echo "$UPDATE_CHECK" | grep -o '"description":"[^"]*"' | cut -d'"' -f4)
    
    if [[ "$ERROR_DESC" == *"terminated by other getUpdates"* ]]; then
        echo -e "${RED}${BOLD}! ACTIVE BOT DETECTED!${NC} Another instance is currently running"
        echo "  The token is actively being used by a running bot instance"
        echo "  This confirms your bot is running somewhere else"
    else
        echo "  $ERROR_DESC"
    fi
fi

echo

# Step 4: Try to detect connection conflict 
echo -e "${BOLD}Step 4: Testing for connection conflicts...${NC}"
CONFLICT_CHECK=$(curl -s "https://api.telegram.org/bot$TOKEN/getUpdates?timeout=1")

if echo "$CONFLICT_CHECK" | grep -q "Conflict: terminated by other getUpdates"; then
    echo -e "${RED}${BOLD}! ACTIVE BOT CONFIRMED!${NC} Connection conflict detected"
    echo "  This confirms your bot is actively running somewhere else right now"
    echo "  The other instance is holding an active connection to Telegram's servers"
else
    echo -e "${GREEN}✓ No connection conflicts detected${NC}"
    echo "  This suggests your bot is not actively running elsewhere"
fi

echo

# Step 5: Summary and recommendations
echo -e "${BOLD}=== SUMMARY ===${NC}"

if echo "$CONFLICT_CHECK" | grep -q "Conflict: terminated by other getUpdates" || \
   (echo "$WEBHOOK_INFO" | grep -q -v '"url":""' && echo "$WEBHOOK_INFO" | grep -q -v '"url":"http://localhost'); then
    echo -e "${RED}${BOLD}→ Your bot appears to be ACTIVE elsewhere${NC}"
    echo -e "  ${BOLD}Possible locations:${NC}"
    
    if echo "$WEBHOOK_INFO" | grep -q -v '"url":""' && echo "$WEBHOOK_INFO" | grep -q -v '"url":"http://localhost'; then
        WEBHOOK_URL=$(echo "$WEBHOOK_INFO" | grep -o '"url":"[^"]*"' | cut -d'"' -f4)
        echo -e "  - ${BOLD}Webhook server:${NC} $WEBHOOK_URL"
        echo "    Check your web server or hosting provider"
    fi
    
    echo "  - Other development machines or servers you've used"
    echo "  - Cloud platforms (AWS, Azure, GCP, Heroku, etc.)"
    echo "  - Virtual machines or containers"
    
    echo
    echo -e "${BOLD}Recommended actions:${NC}"
    echo "  1. Identify all environments where your bot may be deployed"
    echo "  2. Stop the bot instances on those systems"
    echo "  3. If using a webhook, check the server at the URL mentioned above"
    echo "  4. Reset your bot's connection using: ./reset_bot.sh $TOKEN"
else
    echo -e "${GREEN}${BOLD}→ Your bot does NOT appear to be active elsewhere${NC}"
    echo "  The 'Conflict' error you're seeing may be due to:"
    echo "  - A stale connection that hasn't timed out yet"
    echo "  - A recently stopped instance (Telegram connections can take time to clear)"
    echo
    echo -e "${BOLD}Recommended actions:${NC}"
    echo "  1. Reset your bot's connection: ./reset_bot.sh $TOKEN"
    echo "  2. Wait a few minutes before starting a new instance"
    echo "  3. Use the connection reset code in your main.py to avoid conflicts"
fi

echo
echo -e "${BOLD}=== Check Complete ===${NC}"
