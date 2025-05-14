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
    ("find", "Find places with specific features"),
    ("handbook", "Get program handbooks"),
    ("provider", "Change AI provider"),
    ("providers", "List available AI providers")
]

# LLM configuration
LLM_MODEL = "mistral-large-latest"
LLM_TEMPERATURE = 0
LLM_MAX_RETRIES = 2

# Search configuration
MAX_LOCATIONS_TO_DISPLAY = 13  # Maximum number of locations to display in search results

# AI Provider configuration
SUPPORTED_PROVIDERS = {
    "mistral": {
        "module": "langchain_mistralai",
        "embeddings": "MistralAIEmbeddings",
        "llm": "ChatMistralAI",
        "default_model": "mistral-large-latest"
    },
    "openai": {
        "module": "langchain_openai",
        "embeddings": "OpenAIEmbeddings",
        "llm": "ChatOpenAI",
        "default_model": "gpt-4"
    },
    "anthropic": {
        "module": "langchain_anthropic",
        "embeddings": None,
        "llm": "ChatAnthropic",
        "default_model": "claude-3-opus-20240229"
    },
    "gemini": {
        "module": "langchain_google_genai",
        "embeddings": "GoogleGenerativeAIEmbeddings",
        "llm": "ChatGoogleGenerativeAI",
        "default_model": "gemini-1.0-pro"
    }
}
DEFAULT_PROVIDER = "mistral"
AI_PROVIDER = os.environ.get("AI_PROVIDER", DEFAULT_PROVIDER).lower()
