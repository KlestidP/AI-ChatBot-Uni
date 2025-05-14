import logging
from typing import Optional, List, Dict, Any
from telegram import Update, CallbackQuery
from telegram.ext import ContextTypes
from uni_ai_chatbot.bot.location_handlers import show_location_details

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


async def handle_location_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle callback queries from inline keyboards
    """
    query: CallbackQuery = update.callback_query
    await query.answer()

    if query.data.startswith("location:"):
        location_id: str = query.data.split(':')[1]
        campus_map: List[Dict[str, Any]] = context.bot_data["campus_map"]

        # Find the location by ID
        location: Optional[Dict[str, Any]] = next((loc for loc in campus_map if str(loc['id']) == location_id), None)

        if location:
            await show_location_details(update, location, is_callback=True)
        else:
            await query.edit_message_text("Sorry, I couldn't find that location anymore.")


    elif query.data.startswith("hb:"):

        try:

            # Extract the handbook index

            hb_idx = int(query.data.split(':')[1])

            handbooks = context.bot_data["handbooks"]

            # Ensure the index is valid

            if 0 <= hb_idx < len(handbooks):

                handbook = handbooks[hb_idx]

                if handbook and handbook.get('url'):

                    await query.edit_message_text(f"Fetching the handbook for {handbook['major']}...")

                    await update.effective_chat.send_document(

                        document=handbook['url'],

                        filename=handbook['file_name'],

                        caption=f"Handbook for {handbook['major']}"

                    )

                else:

                    await query.edit_message_text(f"Sorry, I couldn't find that handbook.")

            else:

                await query.edit_message_text("Sorry, I couldn't find that handbook.")

        except Exception as e:

            logger.error(f"Error handling handbook callback: {e}")

            await query.edit_message_text("Sorry, I encountered an error retrieving the handbook.")
