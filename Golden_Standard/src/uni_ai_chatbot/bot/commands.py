from typing import List, Dict, Any, Optional, Tuple
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Message, User, Chat
from telegram.constants import ParseMode
from telegram.ext import ContextTypes, CallbackContext
from uni_ai_chatbot.data.campus_map_data import find_location_by_name_or_alias, extract_location_name
from uni_ai_chatbot.bot.location_handlers import show_location_details, handle_location_with_ai
from uni_ai_chatbot.data.campus_map_data import extract_feature_keywords, find_locations_by_feature


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Send a message when the command /start is issued.

    Args:
        update: Telegram Update object
        context: Telegram context
    """
    user: User = update.effective_user
    message: Message = update.message

    await message.reply_text(
        f"Hi {user.first_name}! I'm your University Info Bot. Ask me any question about college schedules, fees, or events!"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Send a message when the command /help is issued.

    Args:
        update: Telegram Update object
        context: Telegram context
    """
    message: Message = update.message

    await message.reply_text(
        "Here's what I can help you with:\n\n"
        "• 📍 `/where [location]` — Find places on campus (e.g., Ocean Lab, C3, IRC).\n\n"
        "• 🔍 `/find [feature]` — Find places with specific features (e.g., printer, food, study).\n\n"
        "• 🧺 *Locker hours* — Ask for locker access times in any college.\n\n"
        "• ❓ *University FAQs* — Ask about documents, laundry, residence permits, etc.\n\n"
        "• 🗓 *College events* — Get updates on announcements and upcoming activities.\n\n"
        "💬 Just type your question — I'll understand natural language too!\n\n"
        "🔒 Bot is limited to university-related queries only.",
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
                keyboard.append([InlineKeyboardButton(
                    text=loc['name'],
                    callback_data=f"location:{loc['id']}"
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
