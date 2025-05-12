from difflib import get_close_matches
from typing import Optional, Dict, Any, List
from telegram import Update, Message, User, Chat
from telegram.ext import ContextTypes
import logging
from uni_ai_chatbot.utils.utils import handle_error
from uni_ai_chatbot.tools.tool_classifier import get_appropriate_tool
from uni_ai_chatbot.tools.tools_architecture import Tool

logger = logging.getLogger(__name__)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle all non-command messages with improved flow control

    Args:
        update: Telegram Update object
        context: Telegram context
    """
    query: str = update.message.text
    user: User = update.effective_user
    chat: Chat = update.effective_chat

    # Show thinking message for longer queries
    thinking_message: Optional[Message] = None
    if len(query.split()) > 3:
        thinking_message = await update.message.reply_text("Thinking...")

    try:
        # Use tool classification to route the query to the right handler
        logger.info(f"Classifying query from user {user.id}: {query}")
        tool: Tool = await get_appropriate_tool(update, context, query)
        logger.info(f"Selected tool: {tool.name}")

        # Handle with the selected tool
        if thinking_message:
            await thinking_message.delete()
        await tool.handle(update, context, query)

    except Exception as e:
        await handle_error(update, error=e, thinking_message=thinking_message)