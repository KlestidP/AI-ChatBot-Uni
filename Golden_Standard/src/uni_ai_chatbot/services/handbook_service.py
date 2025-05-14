import logging
from typing import List, Dict, Any, Optional, Union
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import re

from uni_ai_chatbot.data.handbook_loader import load_handbooks

logger = logging.getLogger(__name__)


async def handle_handbook_query(update: Update, context: ContextTypes.DEFAULT_TYPE, query: str = None) -> None:
    """
    Handle handbook-related queries
    """
    text = query or update.message.text.lower()

    # Check if this is a content question rather than a request for a specific handbook
    content_question_indicators = ["what", "how", "why", "explain", "tell me about", "describe",
                                   "is there", "are there", "do i need", "requirements", "courses",
                                   "prerequisites", "credits"]

    is_content_question = "?" in text or any(indicator in text.lower() for indicator in content_question_indicators)

    if is_content_question and not text.lower().startswith("/handbook"):
        await handle_handbook_content_question(update, context, text)
        return

    try:
        # Check if we have cached handbooks
        if 'handbooks' not in context.bot_data:
            await update.message.reply_text("Fetching handbook information...")
            context.bot_data['handbooks'] = load_handbooks()

        handbooks = context.bot_data['handbooks']

        # Extract major from query
        major = extract_major_from_query(text)

        if major:
            # Look for handbook matching the major
            matching_handbook = find_handbook_by_major(handbooks, major)

            if matching_handbook and matching_handbook.get('url'):
                await update.message.reply_text(
                    f"Here's the handbook for *{matching_handbook['major']}*:",
                    parse_mode="Markdown"
                )
                await update.message.reply_document(
                    document=matching_handbook['url'],
                    filename=matching_handbook['file_name']
                )
            else:
                # Fall back to AI for more context
                await handle_handbook_with_ai(update, context, major)
        else:
            # Show list of available handbooks with SHORT INDEX NUMBERS as callback data
            keyboard = []
            for idx, handbook in enumerate(handbooks[:10]):  # Limit to 10 options
                keyboard.append([
                    InlineKeyboardButton(
                        text=handbook['major'],
                        callback_data=f"hb:{idx}"  # Use short index ID, not the full major name
                    )
                ])

            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                "Which major's handbook would you like to see?",
                reply_markup=reply_markup
            )

    except Exception as e:
        logger.error(f"Error processing handbook query: {e}")
        await update.message.reply_text(
            "I'm sorry, I couldn't retrieve the handbook information. Please try again later."
        )


def extract_major_from_query(query: str) -> Optional[str]:
    """
    Extract major name from query
    """
    # Common phrases that might indicate a handbook request
    prefixes = [
        "handbook for",
        "handbook of",
        "show me the handbook for",
        "get me the handbook for",
        "can i see the handbook for",
        "find the handbook for"
    ]

    cleaned_query = query.lower()
    for prefix in prefixes:
        if prefix in cleaned_query:
            major = cleaned_query.split(prefix)[1].strip()
            return major

    # Try to find major using regex
    major_match = re.search(r'(?:major|program|degree)(?:\s+in)?\s+([a-z\s]+?)(?:$|\.|\?)', cleaned_query)
    if major_match:
        return major_match.group(1).strip()

    return None


def find_handbook_by_major(handbooks: List[Dict[str, Any]], major: str) -> Optional[Dict[str, Any]]:
    """
    Find a handbook by major name
    """
    major_clean = major.lower().strip()

    # Exact match
    for handbook in handbooks:
        if handbook['major'].lower() == major_clean:
            return handbook

    # Partial match
    for handbook in handbooks:
        if major_clean in handbook['major'].lower() or handbook['major'].lower() in major_clean:
            return handbook

    return None


async def handle_handbook_with_ai(update: Update, context: ContextTypes.DEFAULT_TYPE, major: str) -> None:
    """
    Use AI to provide information about a major when handbook isn't found
    """
    general_qa_chain = context.bot_data.get("general_qa_chain")
    if not general_qa_chain:
        await update.message.reply_text(
            f"I couldn't find a handbook specifically for {major}. Please check with the academic office for information."
        )
        return

    query = f"What information do you have about the {major} program or major at the university?"

    try:
        response = general_qa_chain.invoke(query)
        result = response['result']

        await update.message.reply_text(
            f"I couldn't find a specific handbook for *{major}*, but here's what I know:\n\n{result}",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"AI handling error: {e}")
        await update.message.reply_text(
            f"I couldn't find a handbook for {major}. Please check with the academic office for information."
        )


async def handle_handbook_content_question(update: Update, context: ContextTypes.DEFAULT_TYPE, query: str) -> None:
    """
    Handle questions about handbook content using the handbook QA chain
    """
    try:
        # Get the handbook-specific QA chain
        handbook_qa_chain = context.bot_data.get("handbook_qa_chain")

        if not handbook_qa_chain:
            # Fall back to general QA if handbook chain not available
            logger.warning("Handbook QA chain not found, falling back to general QA")
            handbook_qa_chain = context.bot_data.get("general_qa_chain")

        if not handbook_qa_chain:
            await update.message.reply_text(
                "I'm sorry, I don't have information about handbook content right now.")
            return

        # Show a typing indicator while processing
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

        # Invoke the QA chain
        response = handbook_qa_chain.invoke(query)
        result = response['result']

        # Add source information if available
        if 'source_documents' in response and response['source_documents']:
            sources = set()
            for doc in response['source_documents']:
                if 'major' in doc.metadata:
                    sources.add(doc.metadata['major'])

            if sources:
                result += "\n\n*Sources:* " + ", ".join(sources)

        await update.message.reply_text(result, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Error processing handbook content question: {e}")
        await update.message.reply_text(
            "I'm sorry, I couldn't process your question about handbook content. Please try again later.")