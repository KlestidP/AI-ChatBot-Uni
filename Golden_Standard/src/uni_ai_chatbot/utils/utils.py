import logging
from typing import Optional, TypedDict
from telegram import Update, Message, User

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
    """
    Unified error handler for the bot.

    Args:
        update: Telegram Update object
        error: Exception that occurred, if any
        message: Custom error message to show user
        thinking_message: "Thinking..." message to clean up, if any
    """
    if error:
        logger.error(f"Error: {error}")

    if thinking_message:
        try:
            await thinking_message.delete()
        except Exception:
            pass

    error_message: str = message or "Sorry, I couldn't process your question. Please try again."
    await update.message.reply_text(error_message)


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