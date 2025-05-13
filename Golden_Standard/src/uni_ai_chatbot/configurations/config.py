import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Bot configuration
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
MISTRAL_API_KEY = os.environ.get("MISTRAL_API_KEY")

# Database configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

# Feature flags
ENABLE_LLM_CLASSIFICATION = True  # Set to False to use rule-based classification only

# Bot menu commands
BOT_COMMANDS = [
    ("start", "Start the bot"),
    ("help", "Get help using the bot"),
    ("where", "Find a place on campus"),
    ("find", "Find places with specific features")
]

# LLM configuration
LLM_MODEL = "mistral-large-latest"
LLM_TEMPERATURE = 0
LLM_MAX_RETRIES = 2

# Search configuration
MAX_LOCATIONS_TO_DISPLAY = 13  # Maximum number of locations to display in search results
