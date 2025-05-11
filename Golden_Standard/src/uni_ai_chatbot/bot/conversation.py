from difflib import get_close_matches
from telegram import Update
from telegram.ext import ContextTypes
import logging

from uni_ai_chatbot.tools.tool_classifier import get_appropriate_tool

logger = logging.getLogger(__name__)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle all non-command messages"""
    user_id = update.effective_user.id
    query = update.message.text

    # Step 1: Try fuzzy matching against FAQ keywords first
    from uni_ai_chatbot.data.resources import load_faq_answers
    FAQ_ANSWERS = load_faq_answers()

    # Improve fuzzy matching by checking individual words and the entire query
    matched = None

    # Check the complete query first with a lower cutoff
    question_keywords = list(FAQ_ANSWERS.keys())
    matched = get_close_matches(query.lower(), question_keywords, n=1, cutoff=0.6)

    # If no match, try individual words with important meaning
    if not matched:
        for word in query.split():
            if len(word) > 3:  # Skip very short words
                word_matches = get_close_matches(word.lower(), question_keywords, n=1, cutoff=0.7)
                if word_matches:
                    matched = word_matches
                    break

    # Direct matching for important keywords that might be missed by fuzzy matching
    if not matched:
        for keyword in question_keywords:
            if any(important in query.lower() for important in ['laundry', 'washing', 'dryer', 'laundromat', 'wash']):
                if any(important in keyword.lower() for important in
                       ['laundry', 'washing', 'dryer', 'laundromat', 'wash']):
                    matched = [keyword]
                    break

    if matched:
        answer = FAQ_ANSWERS[matched[0]]
        await update.message.reply_text(answer, parse_mode="Markdown")
        return

    # Step 2: If no FAQ match, use LLM tool classification to determine the right tool
    logger.info(f"Classifying query: {query}")

    # For longer queries, show a thinking message to improve UX
    if len(query.split()) > 3:
        thinking_message = await update.message.reply_text("Thinking...")
    else:
        thinking_message = None

    # Get the appropriate tool based on LLM classification
    try:
        tool = await get_appropriate_tool(update, context, query)
        logger.info(f"Selected tool: {tool.name}")

        # Delete thinking message if it exists
        if thinking_message:
            await thinking_message.delete()

        # Handle the query with the selected tool
        await tool.handle(update, context, query)

    except Exception as e:
        logger.error(f"Error processing query: {e}")
        if thinking_message:
            await thinking_message.delete()
        await update.message.reply_text("Sorry, I couldn't process your question.")