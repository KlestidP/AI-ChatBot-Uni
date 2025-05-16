import logging
from typing import List, Dict, Any, Optional, Tuple
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Message, User, Chat
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from uni_ai_chatbot.configurations.config import MISTRAL_API_KEY, DEFAULT_PROVIDER, SUPPORTED_PROVIDERS, AI_PROVIDER
from uni_ai_chatbot.data.campus_map_data import find_location_by_name_or_alias, extract_location_name
from uni_ai_chatbot.bot.location_handlers import show_location_details, handle_location_with_ai
from uni_ai_chatbot.data.campus_map_data import extract_feature_keywords, find_locations_by_feature

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Enhanced start command with interactive onboarding experience.

    Args:
        update: Telegram Update object
        context: Telegram context
    """
    user: User = update.effective_user
    message: Message = update.message

    # Welcome message with personalized greeting
    welcome_text = (
        f"👋 *Welcome to Constructor University Bremen Bot, {user.first_name}!*\n\n"
        f"I'm your AI assistant for navigating campus life. You can ask me questions in natural language - "
        f"just type your question as you would ask a person!\n\n"
        f"For example, try asking:\n"
        f"• \"Where can I find a printer?\"\n"
        f"• \"What are the locker hours for Krupp?\"\n"
        f"• \"When is lunch served at Nordmetall?\"\n\n"
        f"Or explore my capabilities using these example buttons:"
    )

    # Create keyboard with main categories
    keyboard = [
        [
            InlineKeyboardButton("📍 Campus Locations", callback_data="onboard:locations"),
            InlineKeyboardButton("🍽 Dining Hours", callback_data="onboard:dining"),
        ],
        [
            InlineKeyboardButton("🧺 Locker Access", callback_data="onboard:lockers"),
            InlineKeyboardButton("📚 Program Handbooks", callback_data="onboard:handbooks"),
        ],
        [
            InlineKeyboardButton("❓ University FAQs", callback_data="onboard:faqs"),
            InlineKeyboardButton("🔍 See All Features", callback_data="onboard:help"),
        ]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    await message.reply_text(
        welcome_text,
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /help is issued."""
    message: Message = update.message

    await message.reply_text(
        "🎓 *Constructor University Bremen Bot* 🎓\n\n"
        "Here's what I can help you with:\n\n"
        "• 📍 `/where [location]` — Find places on campus (e.g., Ocean Lab, C3, IRC).\n\n"
        "• 🔍 `/find [feature]` — Find places with specific features (e.g., printer, food, study).\n\n"
        "• 🧺 *Locker hours* — Ask for locker access times in any college.\n\n"
        "• 🍽 *Servery hours* — Ask for meal times in any college or the coffee bar.\n\n"
        "• 📚 `/handbook [program]` — Get program handbooks or ask about course requirements.\n\n"
        "• ❓ *University FAQs* — Ask about documents, laundry, residence permits, etc.\n\n"
        "• 🤖 `/provider [name] [api_key] [model]` — Change the AI provider for your queries.\n\n"
        "• 📋 `/providers` — List all available AI providers and their status.\n\n"
        "💬 Just type your question naturally — I'll understand and route it to the right service!\n\n"
        "Try questions like:\n"
        "- \"Where can I find a printer?\"\n"
        "- \"What are the locker hours for Krupp College?\"\n"
        "- \"When is lunch served at Nordmetall?\"\n"
        "- \"How do I get my enrollment certificate?\"\n\n"
        "🔒 I'm limited to university-related queries only.",
        parse_mode=ParseMode.MARKDOWN
    )

async def where_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Respond to /where command with location info and venue

    Args:
        update: Telegram Update object
        context: Telegram context
    """
    query: str = ' '.join(context.args)
    if not query:
        await update.message.reply_text(
            "Please provide a location name.\nFor example: /where Ocean Lab"
        )
        return

    # Extract location name from query
    cleaned_query: str = extract_location_name(query)

    campus_map: List[Dict[str, Any]] = context.bot_data["campus_map"]
    location: Optional[Dict[str, Any]] = find_location_by_name_or_alias(campus_map, cleaned_query)

    if location:
        await show_location_details(update, location)
    else:
        await update.message.reply_text(
            "Sorry, I couldn't find that location. Try asking in a different way or try the /find command."
        )


async def find_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Find locations with specific features

    Args:
        update: Telegram Update object
        context: Telegram context
    """
    query: str = ' '.join(context.args)
    if not query:
        await update.message.reply_text(
            "Please specify what you're looking for.\nFor example: /find printer or /find food"
        )
        return

    campus_map: List[Dict[str, Any]] = context.bot_data["campus_map"]
    keywords: List[str] = extract_feature_keywords(query)

    # If no keywords were extracted, use the whole query as a single keyword
    if not keywords:
        keywords = [query.lower()]

    locations: List[Dict[str, Any]] = find_locations_by_feature(campus_map, keywords)

    if locations:
        if len(locations) == 1:
            # Only one location found, show it directly
            location: Dict[str, Any] = locations[0]
            await show_location_details(update, location)
        else:
            # Multiple locations found, show a keyboard to select
            keyboard: List[List[InlineKeyboardButton]] = []
            for loc in locations[:13]:  # Limit to 13 options
                logger.debug(f"Location ID type: {type(loc['id'])}, value: {loc['id']}")
                keyboard.append([InlineKeyboardButton(
                    text=loc['name'],
                    callback_data=f"location:{str(loc['id'])}"
                )])

            reply_markup: InlineKeyboardMarkup = InlineKeyboardMarkup(keyboard)
            feature_text: str = " and ".join(keywords)
            await update.message.reply_text(
                f"I found {len(locations)} places with {feature_text}. Which one would you like to see?",
                reply_markup=reply_markup
            )
    else:
        # No locations found in the database, fall back to AI
        await update.message.reply_text(
            "I don't have specific information about places with those features. Let me think about it..."
        )
        # Fall back to AI
        await handle_location_with_ai(update, context, query)


async def handbook_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /handbook command
    """
    query = ' '.join(context.args) if context.args else None

    from uni_ai_chatbot.services.handbook_service import handle_handbook_query
    await handle_handbook_query(update, context, query)


async def change_provider_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Command to change AI provider"""
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
        from uni_ai_chatbot.services.ai_provider_service import dynamic_import_provider
        EmbeddingsClass, LLMClass = dynamic_import_provider(provider)

        # Test creating the embeddings and LLM to catch API key issues early
        try:
            # Temporarily add API keys to the user message to indicate we're testing
            await update.message.reply_text(f"Testing connection to {provider}...")

            # Initialize the QA chain with the new provider
            from uni_ai_chatbot.services.qa_service_supabase import initialize_qa_chain_with_provider
            (vector_store, llm, general_qa_chain, location_qa_chain,
             locker_qa_chain, faq_qa_chain, handbook_qa_chain) = initialize_qa_chain_with_provider(
                provider=provider,
                api_key=api_key,
                model=model
            )

            # Store all chains in user_data
            context.user_data['general_qa_chain'] = general_qa_chain
            context.user_data['location_qa_chain'] = location_qa_chain
            context.user_data['locker_qa_chain'] = locker_qa_chain
            context.user_data['faq_qa_chain'] = faq_qa_chain
            context.user_data['handbook_qa_chain'] = handbook_qa_chain
            context.user_data['llm'] = llm

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


async def list_providers_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Command to list all available providers and their status"""
    from uni_ai_chatbot.services.ai_provider_service import dynamic_import_provider
    from uni_ai_chatbot.configurations.config import SUPPORTED_PROVIDERS, AI_PROVIDER

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