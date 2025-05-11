from difflib import get_close_matches
from telegram import Update
from telegram.ext import ContextTypes
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from uni_ai_chatbot.bot.location_handlers import show_location_details, handle_location_with_ai, \
    find_location_by_name_or_alias
from uni_ai_chatbot.utils.message_utils import extract_feature_keywords, find_locations_by_feature
from uni_ai_chatbot.services.locker_service import handle_locker_hours
import logging

logger = logging.getLogger(__name__)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle all non-command messages"""
    user_id = update.effective_user.id
    text = update.message.text.lower()
    campus_map = context.bot_data["campus_map"]

    # Check if asking for locker hours
    if "locker" in text and ("open" in text or "hours" in text):
        await handle_locker_hours(update, context)
        return

    # Check if asking about location features like printers, food, study areas
    location_features = ["print", "printer", "food", "eat", "study", "studying",
                         "coffee", "quiet", "library", "ify"]

    is_location_query = False
    for feature in location_features:
        if feature in text:
            is_location_query = True
            break

    is_where_query = any(word in text for word in ["where", "find", "location", "how to get to"])

    # Process location-related queries
    if is_location_query or is_where_query:
        # Extract keywords to find locations with those features
        keywords = extract_feature_keywords(text)

        if keywords:
            # Try to find locations with those features
            locations = find_locations_by_feature(campus_map, keywords)

            if locations:
                if len(locations) == 1:
                    # Only one location found, show it directly
                    location = locations[0]
                    await show_location_details(update, location)
                    return
                else:
                    # Multiple locations found, show a keyboard to select
                    keyboard = []
                    for loc in locations[:8]:  # Limit to 8 options
                        keyboard.append([InlineKeyboardButton(
                            text=loc['name'],
                            callback_data=f"location:{loc['id']}"
                        )])

                    reply_markup = InlineKeyboardMarkup(keyboard)
                    feature_text = " and ".join(keywords)
                    await update.message.reply_text(
                        f"I found {len(locations)} places with {feature_text}. Which one would you like to see?",
                        reply_markup=reply_markup
                    )
                    return

            # If no matches by tags, try to find a specific location by name in the query
            for word in text.split():
                if len(word) > 2:  # Ignore very short words
                    location = find_location_by_name_or_alias(campus_map, word)
                    if location:
                        await show_location_details(update, location)
                        return

        # If we reach here, it's a location query but we couldn't find a match
        # Fall back to AI for this location query
        await handle_location_with_ai(update, context, text)
        return

    # Step 2.5: fuzzy match against FAQ keywords
    from uni_ai_chatbot.data.resources import load_faq_answers
    FAQ_ANSWERS = load_faq_answers()
    question_keywords = list(FAQ_ANSWERS.keys())
    matched = get_close_matches(text.lower(), question_keywords, n=1, cutoff=0.6)

    if matched:
        answer = FAQ_ANSWERS[matched[0]]
        await update.message.reply_text(answer, parse_mode="Markdown")
        return

    # Step 3: fallback to AI QA system for non-location queries
    qa_chain = context.bot_data["qa_chain"]
    await update.message.reply_text("Thinking...")
    try:
        response = qa_chain.invoke(text)
        # Extract the result and source documents
        result = response['result']

        # Check if we have source documents
        if 'source_documents' in response and response['source_documents']:
            # Add a "Sources:" section to show where the information came from
            sources = set()
            for doc in response['source_documents']:
                if 'type' in doc.metadata:
                    if doc.metadata['type'] == 'faq' and 'question' in doc.metadata:
                        sources.add(f"FAQ: {doc.metadata['question']}")
                    elif doc.metadata['type'] == 'location' and 'name' in doc.metadata:
                        sources.add(f"Location: {doc.metadata['name']}")

            if sources:
                result += "\n\n*Sources:*\n- " + "\n- ".join(sources)

        await update.message.reply_text(result, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error processing: {e}")
        await update.message.reply_text("Sorry, I couldn't process your question.")