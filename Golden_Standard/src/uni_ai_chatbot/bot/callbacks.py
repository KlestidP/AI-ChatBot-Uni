from typing import Optional, List, Dict, Any
from telegram import Update, CallbackQuery
from telegram.ext import ContextTypes
from uni_ai_chatbot.bot.location_handlers import show_location_details


async def handle_location_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle callback queries from inline keyboards

    Args:
        update: Telegram Update object
        context: Telegram context
    """
    query: CallbackQuery = update.callback_query
    await query.answer()

    if query.data.startswith("location:"):
        location_id: str = query.data.split(':')[1]
        campus_map: List[Dict[str, Any]] = context.bot_data["campus_map"]

        # Find the location by ID
        location: Optional[Dict[str, Any]] = next((loc for loc in campus_map if loc['id'] == location_id), None)

        if location:
            await show_location_details(update, location, is_callback=True)
        else:
            await query.edit_message_text("Sorry, I couldn't find that location anymore.")