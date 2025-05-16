import logging
from typing import Optional, TypedDict
from telegram import Update, Message, User
from telegram.error import TelegramError

logger = logging.getLogger(__name__)


class UserInfo(TypedDict):
    """Type definition for user information"""
    id: int
    username: Optional[str]
    first_name: Optional[str]
    last_name: Optional[str]
    language_code: Optional[str]



async def handle_error(update: Update, error: Optional[Exception] = None,
                       message: Optional[str] = None,
                       thinking_message: Optional[Message] = None) -> None:
    """Enhanced error handler with graceful degradation"""
    if error:
        logger.error(f"Error: {type(error).__name__}: {error}")

    # Clean up thinking message
    if thinking_message:
        try:
            await thinking_message.delete()
        except TelegramError:
            pass  # Ignore if message already deleted

    # Determine appropriate error message
    if isinstance(error, TelegramError):
        error_message = "I'm having trouble with Telegram right now. Please try again in a moment."
    elif "timeout" in str(error).lower() or "timed out" in str(error).lower():
        error_message = "That's taking longer than expected. Could you try a shorter question?"
    else:
        error_message = message or "Sorry, I couldn't process your question. Please try again."

    try:
        await update.message.reply_text(error_message)
    except Exception as follow_up_error:
        logger.error(f"Failed to send error message: {follow_up_error}")


def get_user_info(update: Update) -> UserInfo:
    """
    Extract and return user information from update.

    Args:
        update: Telegram Update object

    Returns:
        Dictionary with user information
    """
    user: User = update.effective_user
    return {
        "id": user.id,
        "username": user.username,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "language_code": user.language_code
    }