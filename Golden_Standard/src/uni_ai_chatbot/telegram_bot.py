import os
import json
import logging
import re
import importlib
from pathlib import Path
from telegram import Update, BotCommand
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from langchain.chains import RetrievalQA
from langchain_community.document_loaders import TextLoader
from langchain_community.vectorstores import FAISS
from langchain_text_splitters import CharacterTextSplitter
from langchain_mistralai import MistralAIEmbeddings
from langchain_mistralai import ChatMistralAI
from uni_ai_chatbot.resources import get_resource
from dotenv import load_dotenv
from uni_ai_chatbot.campus_map_data import campus_map
from uni_ai_chatbot.locker_hours_loader import load_locker_hours
from uni_ai_chatbot.servery_hours_loader import load_servery_hours
from uni_ai_chatbot.handbook_loader import load_handbook_docs
from difflib import get_close_matches

load_dotenv()
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
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
if AI_PROVIDER not in SUPPORTED_PROVIDERS:
    logger.warning(f"Unknown AI provider: {AI_PROVIDER}. Falling back to {DEFAULT_PROVIDER}")
    AI_PROVIDER = DEFAULT_PROVIDER
MISTRAL_API_KEY = os.environ.get("MISTRAL_API_KEY")
if not TELEGRAM_TOKEN:
    raise ValueError("TELEGRAM_TOKEN is not set in environment variables")
if AI_PROVIDER == "mistral" and not MISTRAL_API_KEY:
    raise ValueError("MISTRAL_API_KEY is not set in environment variables")

faq_file_path = Path(__file__).parent / "faq_responses.json"
with open(faq_file_path, encoding="utf-8") as f:
    FAQ_ANSWERS = json.load(f)


def dynamic_import_provider(provider_name):
    """Dynamically import provider modules when needed"""
    if provider_name not in SUPPORTED_PROVIDERS:
        logger.warning(f"Provider {provider_name} not supported")
        return None, None
    provider_info = SUPPORTED_PROVIDERS[provider_name]
    module_name = provider_info["module"]
    try:
        module = importlib.import_module(module_name)
        # Get embeddings class if available
        embeddings_class = None
        if provider_info["embeddings"]:
            embeddings_class = getattr(module, provider_info["embeddings"])
        # Get LLM class
        llm_class = getattr(module, provider_info["llm"])
        return embeddings_class, llm_class
    except (ImportError, AttributeError) as e:
        logger.error(f"Error importing {provider_name} provider: {e}")
        return None, None


def get_embeddings_model(provider=None, api_key=None):
    """Get the appropriate embeddings model based on the provider"""
    # Use system default if no provider specified
    if not provider:
        provider = AI_PROVIDER
        api_key = MISTRAL_API_KEY
    # Special case for Anthropic which doesn't have embeddings
    if provider == "anthropic":
        # Fall back to Mistral embeddings if available
        if MISTRAL_API_KEY:
            return MistralAIEmbeddings(api_key=MISTRAL_API_KEY)
        # Or try OpenAI
        try:
            EmbeddingsClass, _ = dynamic_import_provider("openai")
            if EmbeddingsClass and api_key:
                return EmbeddingsClass(api_key=api_key)
        except Exception as e:
            logger.error(f"Failed to use OpenAI embeddings: {e}")
        raise ValueError("Cannot use Anthropic without embeddings from another provider")
    # For other providers
    EmbeddingsClass, _ = dynamic_import_provider(provider)
    if not EmbeddingsClass:
        raise ValueError(f"No embeddings class found for provider {provider}")
    return EmbeddingsClass(api_key=api_key)


def get_llm_model(provider=None, api_key=None, model=None):
    """Get the appropriate language model based on the provider"""
    # Use system default if no provider specified
    if not provider:
        provider = AI_PROVIDER
        api_key = MISTRAL_API_KEY
    if provider not in SUPPORTED_PROVIDERS:
        raise ValueError(f"Unsupported provider: {provider}")
    # Get the LLM class for this provider
    _, LLMClass = dynamic_import_provider(provider)
    if not LLMClass:
        raise ValueError(f"Failed to import LLM class for {provider}")
    # Get default model for the provider if not specified
    if not model:
        model = SUPPORTED_PROVIDERS[provider]["default_model"]
    # Create the LLM instance with appropriate parameters
    return LLMClass(
        model=model,
        temperature=0,
        api_key=api_key
    )


def initialize_qa_chain(provider=None, api_key=None, model=None):
    """Initialize QA chain with specific provider and API key if provided"""
    docs = TextLoader(get_resource(Path("data.txt"))).load()
    docs += TextLoader(get_resource(Path("map_data.txt"))).load()
    docs += load_handbook_docs()
    splitter = CharacterTextSplitter(chunk_size=200, chunk_overlap=20)
    split_small = splitter.split_documents(docs[:2])  # first two items are small
    full_corpus = split_small + docs[2:]  # append handbook chunks
    try:
        embeddings = get_embeddings_model(provider, api_key)
        vector_store = FAISS.from_documents(full_corpus, embeddings)
        retriever = vector_store.as_retriever(search_kwargs={"k": 6})
        llm = get_llm_model(provider, api_key, model)
        return RetrievalQA.from_chain_type(llm=llm, retriever=retriever)
    except Exception as e:
        logger.error(f"Error initializing QA chain: {e}")
        # If custom provider fails, fall back to default
        if provider != DEFAULT_PROVIDER:
            logger.info(f"Falling back to {DEFAULT_PROVIDER} provider")
            return initialize_qa_chain(DEFAULT_PROVIDER, MISTRAL_API_KEY)
        else:
            # If default provider fails, re-raise the exception
            raise


def resolve_location_name(query):
    names = []
    lookup = {}

    for place in campus_map:
        names.append(place["name"])
        lookup[place["name"].lower()] = place
        for alias in place.get("aliases", []):
            names.append(alias)
            lookup[alias.lower()] = place

    matches = get_close_matches(query.lower(), names, n=1, cutoff=0.6)
    if matches:
        match = matches[0].lower()
        return lookup[match]["name"]
    return None


# determine location info using fuzzy name matching
def get_location_info(query):
    # Build search index using names and aliases
    names = []
    lookup = {}

    for place in campus_map:
        main_name = place["name"]
        names.append(main_name)
        lookup[main_name.lower()] = place

        for alias in place.get("aliases", []):
            names.append(alias)
            lookup[alias.lower()] = place

    # Match user query against names/aliases
    matches = get_close_matches(query.lower(), names, n=1, cutoff=0.6)
    if matches:
        match = matches[0].lower()
        place = lookup[match]
        return f"{place['name']} is in the {place['direction'].lower()} part of campus and is a {place['category'].lower()} facility."

    return "Sorry, I couldn't find that place on the map."


# provide basic directions from Main Gate to the target location
def get_directional_instructions(query):
    names = []
    lookup = {}

    for place in campus_map:
        main_name = place["name"]
        names.append(main_name)
        lookup[main_name.lower()] = place

        for alias in place.get("aliases", []):
            names.append(alias)
            lookup[alias.lower()] = place

    matches = get_close_matches(query.lower(), names, n=1, cutoff=0.6)
    if matches:
        match = matches[0].lower()
        place = lookup[match]
        return f"From the Main Gate, head toward the {place['direction'].lower()} to reach {place['name']}."

    return "Sorry, I couldn't find that place on the map."


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    await update.message.reply_text(
        "Hi! I'm your University Info Bot. Ask me any question about college schedules, fees, or events!"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /help is issued."""
    await update.message.reply_text(
        "Here’s what I can help you with:\n\n"
        "• 📍 `/where [location]` — Find places on campus (e.g., Ocean Lab, C3, IRC).\n\n"
        "• 🧺 *Locker hours* — Ask for locker access times in any college.\n\n"
        "• 🍽 *Servery hours* — Ask for meal times in your college or the coffee bar.\n\n"
        "• ❓ *University FAQs* — Ask about documents, laundry, residence permits, etc.\n\n"
        "• 🗓 *College events* — Get updates on announcements and upcoming activities.\n\n"
        "💬 Just type your question — I’ll understand natural language too!\n\n"
        "🔒 Bot is limited to university-related queries only."
    )


# respond to /where command with location info
async def where_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = ' '.join(context.args)
    if not query:
        await update.message.reply_text(
            "Please provide a location name.\nFor example: /where Ocean Lab"
        )
        return
    response = get_location_info(query)
    await update.message.reply_text(response)


# Add command to change AI provider
async def change_provider_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if not context.args or len(context.args) < 1:
        # Get current provider for this user or system default
        current_provider = context.user_data.get('user_provider', {}).get('name', AI_PROVIDER)
        providers_list = ", ".join(SUPPORTED_PROVIDERS.keys())

        await update.message.reply_text(
            f"Current AI provider: {current_provider}\n\n"
            f"Available providers: {providers_list}\n\n"
            "To change provider, use:\n"
            "/provider [name] [api_key] [model_name]\n\n"
            "Example: /provider openai sk-abc123 gpt-4\n"
            "Model name is optional (default will be used if not provided)"
        )
        return

    provider = context.args[0].lower()

    if provider not in SUPPORTED_PROVIDERS:
        await update.message.reply_text(
            f"Unsupported provider: {provider}\n"
            f"Available providers: {', '.join(SUPPORTED_PROVIDERS.keys())}"
        )
        return

    # Handle API key (required for custom providers)
    api_key = None
    model = None

    if len(context.args) > 1:
        api_key = context.args[1]

        # Handle optional model name if provided
        if len(context.args) > 2:
            model = context.args[2]
    elif provider != DEFAULT_PROVIDER:
        # For non-default providers, API key is required
        await update.message.reply_text(
            f"API key is required for {provider}.\n"
            f"Please use: /provider {provider} YOUR_API_KEY [optional_model_name]"
        )
        return
    else:
        # For default provider, use system API key
        api_key = MISTRAL_API_KEY

    # Initialize user provider settings
    if 'user_provider' not in context.user_data:
        context.user_data['user_provider'] = {}

    # Set provider info in user context
    context.user_data['user_provider']['name'] = provider
    context.user_data['user_provider']['api_key'] = api_key
    if model:
        context.user_data['user_provider']['model'] = model

    # Try to dynamically import the provider's modules
    try:
        EmbeddingsClass, LLMClass = dynamic_import_provider(provider)

        # For Anthropic which doesn't have embeddings, make sure we have access to another embeddings model
        if provider == "anthropic" and not EmbeddingsClass:
            # Try to get Mistral embeddings
            if not MISTRAL_API_KEY:
                await update.message.reply_text(
                    "Anthropic doesn't provide embeddings. You'll need to provide an OpenAI or Mistral API key for embeddings as well:\n"
                    "/provider anthropic YOUR_ANTHROPIC_KEY [model] embeddings EMBEDDINGS_PROVIDER EMBEDDINGS_KEY"
                )
                return

        # Test creating the embeddings and LLM to catch API key issues early
        try:
            # Temporarily add API keys to the user message to indicate we're testing
            await update.message.reply_text(f"Testing connection to {provider}...")

            # Initialize the QA chain with the new provider
            context.user_data['qa_chain'] = initialize_qa_chain(
                provider=provider,
                api_key=api_key,
                model=model
            )

            await update.message.reply_text(
                f"✅ AI provider changed to {provider}" +
                (f" with model {model}" if model else "") +
                "\n\nYour next questions will use this provider."
            )

        except Exception as e:
            logger.error(f"Error initializing provider: {e}")
            # Clean up user provider data due to error
            if 'user_provider' in context.user_data:
                del context.user_data['user_provider']

            await update.message.reply_text(
                f"❌ Error connecting to {provider}. Please check your API key and try again.\n"
                f"Error details: {str(e)}"
            )

    except Exception as e:
        logger.error(f"Error importing provider: {e}")
        await update.message.reply_text(
            f"❌ Failed to set up {provider}. This provider may not be properly installed.\n"
            f"Error: {str(e)}\n\n"
            f"You may need to install: pip install langchain_{provider}"
        )


# handle all text messages (including "how do I get to" questions)
# store temp state for direction questions
user_direction_queries = {}


async def handle_locker_hours(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower()
    locker_data = context.bot_data["locker_hours"]

    aliases = {
        # Krupp
        "krupp": "Krupp College",
        "krupp college": "Krupp College",

        # College III
        "college iii": "College III",
        "college 3": "College III",
        "c3": "College III",

        # Nordmetall
        "nordmetall": "Nordmetall College",
        "nordmetall college": "Nordmetall College",
        "nord": "Nordmetall College",

        # Mercator
        "mercator": "Mercator College",
        "mercator college": "Mercator College",
    }

    canonical = next((real for alias, real in aliases.items() if alias in text), None)
    if not canonical:
        await update.message.reply_text(
            "❓ Please mention the college (Krupp, College III, Nordmetall, or Mercator).")
        return
    matched_college = canonical

    basement = None
    m = re.search(r'\b(?:basement\s*)?([abcdf])\b', text, re.I)
    if m:
        basement = m.group(1).upper()

    day = None
    if "monday" in text:
        day = "monday"
    elif "thursday" in text:
        day = "thursday"

    message = f"🔓 Locker Hours for *{matched_college}*:\n"

    if day:
        if day in locker_data[matched_college]:
            message += f"\n📅 {day.title()}:\n"
            if basement:
                time = locker_data[matched_college][day].get(basement)
                if time:
                    message += f"- Basement {basement}: {time}\n"
                else:
                    message += f"- No info for Basement {basement}.\n"
            else:
                for base, hours in locker_data[matched_college][day].items():
                    message += f"- Basement {base}: {hours}\n"
        else:
            message += "- No info for that day.\n"
    else:
        for d, basements in locker_data[matched_college].items():
            message += f"\n📅 {d.title()}:\n"
            if basement:
                hours = basements.get(basement)
                if hours:
                    message += f"- Basement {basement}: {hours}\n"
            else:
                for base, time in basements.items():
                    message += f"- Basement {base}: {time}\n"

    await update.message.reply_text(message, parse_mode="Markdown")


async def handle_servery_hours(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower()
    data = context.bot_data["servery_hours"]

    colleges = {
        "Alfried Krupp College": ["krupp", "alfried krupp"],
        "College Nordmetall & College 3": ["nordmetall", "college 3", "college iii", "c3", "nord"],
        "Mercator College": ["mercator"],
        "Coffee Bar": ["coffee bar", "bar"]
    }
    college = next((c for c, vs in colleges.items() if any(v in text for v in vs)), None)
    if not college:
        await update.message.reply_text("❓ Which servery? (Krupp, Nordmetall/College 3, Mercator or Coffee Bar)")
        return

    # optional keywords
    meal = next((m for m in ["breakfast", "lunch", "dinner", "servery"] if m in text), None)
    day = next((d for d in ["monday", "friday", "saturday", "sunday", "holiday"] if d in text), None)

    msg = f"🍽 **Servery Hours – {college}**\n"
    periods = data[college]

    for period, meals in periods.items():
        if day and day not in period:
            continue
        msg += f"\n*{period.title()}*\n"
        for m, hrs in meals.items():
            if meal and meal != m:
                continue
            msg += f"• {m.title()}: {hrs}\n"

    await update.message.reply_text(msg, parse_mode="Markdown")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    text = update.message.text.lower()

    # Step 1: if we're waiting for the user's location after asking
    if user_id in user_direction_queries:
        # inside handle_message() where user gives origin:
        origin = resolve_location_name(text)
        target = resolve_location_name(user_direction_queries.pop(user_id))

        if not origin or not target:
            await update.message.reply_text(
                "Sorry, I couldn't understand the location names. Try using different words.")
            return

        ai_input = f"How can I get from {origin} to {target}?"
        await update.message.reply_text("Thinking...")
        # Use user-specific QA chain if available, otherwise use the system one
        qa_chain = context.user_data.get('qa_chain', context.bot_data["qa_chain"])
        response = qa_chain.invoke(ai_input)
        await update.message.reply_text(response['result'])
        return

    # Step 2: if it's a direction question
    if "how do i get to" in text or "how can i get to" in text or "how to reach" in text:
        location_query = text.replace("how do i get to", "").replace("how can i get to", "").replace("how to reach",
                                                                                                     "").strip()
        if location_query:
            user_direction_queries[user_id] = location_query
            await update.message.reply_text("Where are you standing right now?")
        else:
            await update.message.reply_text("Please specify where you want to go.")
        return

    # Check if asking for locker hours
    if "locker" in text and ("open" in text or "hours" in text):
        await handle_locker_hours(update, context)
        return

    if any(k in text for k in ["servery", "mensa", "opening hours"]) and "locker" not in text:
        await handle_servery_hours(update, context)
        return

    # Step 2.5: fuzzy match against FAQ keywords
    question_keywords = list(FAQ_ANSWERS.keys())
    matched = get_close_matches(text.lower(), question_keywords, n=1, cutoff=0.6)

    if matched:
        answer = FAQ_ANSWERS[matched[0]]
        await update.message.reply_text(answer, parse_mode="Markdown")
        return

    # Step 3: fallback to AI QA system
    # Use user-specific QA chain if available, otherwise use the system one
    qa_chain = context.user_data.get('qa_chain', context.bot_data["qa_chain"])
    await update.message.reply_text("Thinking...")
    try:
        response = qa_chain.invoke(text)
        await update.message.reply_text(response['result'])
    except Exception as e:
        logger.error(f"Error processing: {e}")
        await update.message.reply_text("Sorry, I couldn't process your question.")


# set the bot menu button to show available commands
async def set_bot_commands(application):
    await application.bot.set_my_commands([
        BotCommand("start", "Start the bot"),
        BotCommand("help", "Get help using the bot"),
        BotCommand("where", "Find a place on campus"),
        BotCommand("provider", "Change AI provider"),
        BotCommand("providers", "List available AI providers")
    ])


async def list_providers_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Command to list all available providers and their status"""
    user_id = update.effective_user.id

    # Get current provider for this user
    current_provider = context.user_data.get('user_provider', {}).get('name', AI_PROVIDER)
    current_model = context.user_data.get('user_provider', {}).get('model',
                                                                   SUPPORTED_PROVIDERS[current_provider][
                                                                       'default_model'])

    message = "🤖 *Available AI Providers*\n\n"

    for provider_name, provider_info in SUPPORTED_PROVIDERS.items():
        # Check if provider can be imported
        try:
            embeddings_class, llm_class = dynamic_import_provider(provider_name)

            if provider_name == current_provider:
                message += f"✅ *{provider_name}* (current)\n"
                message += f"   Model: {current_model}\n"
            else:
                message += f"• {provider_name}\n"
                message += f"   Default model: {provider_info['default_model']}\n"

            # Add note about embeddings for Anthropic
            if provider_name == "anthropic":
                message += "   Note: Requires another provider for embeddings\n"

        except Exception:
            message += f"• {provider_name} (not installed)\n"

    message += "\nTo change provider:\n/provider [name] [api_key] [optional_model]\n"
    message += "\nExample:\n/provider openai sk-abc123 gpt-4"

    await update.message.reply_text(message, parse_mode="Markdown")


def main() -> None:
    """Initialize and run the bot"""
    try:
        # Build the application
        application = Application.builder().token(TELEGRAM_TOKEN).build()
        # Initialize system-level data
        logger.info("Initializing default QA chain with provider: %s", AI_PROVIDER)
        application.bot_data["qa_chain"] = initialize_qa_chain()
        application.bot_data["locker_hours"] = load_locker_hours()
        application.bot_data["servery_hours"] = load_servery_hours()
        # Register command handlers
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("where", where_command))
        application.add_handler(CommandHandler("provider", change_provider_command))
        application.add_handler(CommandHandler("providers", list_providers_command))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        # Set bot commands
        application.post_init = set_bot_commands
        # Start polling
        logger.info("Starting bot")
        application.run_polling()
    except Exception as e:
        logger.critical("Fatal error starting bot: %s", e)
        raise


if __name__ == "__main__":
    main()
