import logging
from telegram import Update

logger = logging.getLogger(__name__)


async def handle_error(update, error=None, message=None, thinking_message=None):
    """Unified error handler for the bot."""
    if error:
        logger.error(f"Error: {error}")

    if thinking_message:
        try:
            await thinking_message.delete()
        except Exception:
            pass

    error_message = message or "Sorry, I couldn't process your question. Please try again."
    await update.message.reply_text(error_message)


def get_user_info(update):
    """Extract and return user information from update."""
    user = update.effective_user
    return {
        "id": user.id,
        "username": user.username,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "language_code": user.language_code
    }