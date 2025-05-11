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

    # Step 1: Determine the query type (locker, location, or general QA)
    query_type = determine_query_type(text)
    logger.info(f"Determined query type: {query_type}")

    # Step 2: Handle based on query type
    if query_type == "locker":
        await handle_locker_hours(update, context)
        return

    elif query_type == "location":
        # Process location-related queries
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
        # Fall back to AI for this location query, but using the location-specific QA chain
        await handle_location_with_ai_scoped(update, context, text)
        return

    else:  # query_type == "qa"
        # Step 2.5: fuzzy match against FAQ keywords
        from uni_ai_chatbot.data.resources import load_faq_answers
        FAQ_ANSWERS = load_faq_answers()

        # Improve fuzzy matching by checking individual words and the entire query
        matched = None

        # Check the complete query first with a lower cutoff
        question_keywords = list(FAQ_ANSWERS.keys())
        matched = get_close_matches(text.lower(), question_keywords, n=1, cutoff=0.5)

        # If no match, try individual words with important meaning
        if not matched:
            for word in text.split():
                if len(word) > 3:  # Skip very short words
                    word_matches = get_close_matches(word.lower(), question_keywords, n=1, cutoff=0.5)
                    if word_matches:
                        matched = word_matches
                        break

        # Direct matching for important keywords that might be missed by fuzzy matching
        if not matched:
            for keyword in question_keywords:
                if any(important in text.lower() for important in ['laundry', 'washing', 'dryer', 'laundromat', 'wash']):
                    if any(important in keyword.lower() for important in ['laundry', 'washing', 'dryer', 'laundromat', 'wash']):
                        matched = [keyword]
                        break

        if matched:
            answer = FAQ_ANSWERS[matched[0]]
            await update.message.reply_text(answer, parse_mode="Markdown")
            return

        # Step 3: fallback to AI QA system for non-location queries
        qa_chain = context.bot_data["qa_chain"]  # This now uses the qa-specific chain
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


def determine_query_type(text):
    """Determine what type of query the user is asking."""
    text = text.lower()

    # Check if asking for locker hours
    if "locker" in text and ("open" in text or "hours" in text or "time" in text or "access" in text):
        return "locker"

    # Special cases for common queries that should be handled by FAQ
    if any(word in text for word in ["laundry", "washing", "dryer"]):
        return "qa"

    # Location-related keywords
    location_features = ["print", "printer", "food", "eat", "study", "studying",
                         "coffee", "quiet", "library", "ify"]
    location_indicators = ["where", "find", "location", "how to get to", "building", "room", "campus"]

    # Check if it's a location query
    is_location_query = any(feature in text for feature in location_features) or \
                        any(indicator in text for indicator in location_indicators)

    if is_location_query:
        return "location"

    # Default to general QA
    return "qa"


async def handle_location_with_ai_scoped(update: Update, context: ContextTypes.DEFAULT_TYPE, query: str):
    """Use location-specific AI to understand and respond to location-related queries"""
    location_qa_chain = context.bot_data["location_qa_chain"]
    campus_map = context.bot_data["campus_map"]

    try:
        # Ask the AI about the location, using the location-scoped QA chain
        ai_query = f"What places on campus match this description: {query}? Please mention specific location names only."
        response = location_qa_chain.invoke(ai_query)
        response_text = response['result']

        # The rest of the function is the same as handle_location_with_ai
        # Extract location names from the AI's response
        import re
        potential_locations = []
        lines = response_text.split('\n')
        for line in lines:
            if ":" in line:  # Looking for "Location name: description" format
                potential_loc = line.split(':')[0].strip()
                potential_locations.append(potential_loc)
            else:
                # Try to find location names in the text
                words = re.findall(r'\b[A-Z][a-zA-Z\s]+(College|Hall|Lab|Center|Centre)\b', line)
                potential_locations.extend(words)

        # If no locations found in formatted response, try looking for capitalized words that might be locations
        if not potential_locations:
            words = re.findall(r'\b[A-Z][a-zA-Z\s]+(College|Hall|Lab|Center|Centre|Building)\b', response_text)
            potential_locations = words

        # Match potential locations against our database
        matched_locations = []
        for pot_loc in potential_locations:
            location = find_location_by_name_or_alias(campus_map, pot_loc)
            if location and location not in matched_locations:
                matched_locations.append(location)

        if matched_locations:
            # Locations found, show options
            keyboard = []
            for loc in matched_locations[:8]:  # Limit to 8 options
                keyboard.append([InlineKeyboardButton(
                    text=loc['name'],
                    callback_data=f"location:{loc['id']}"
                )])

            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                f"Based on your question, here are some relevant places:",
                reply_markup=reply_markup
            )
        else:
            # No matches, just show the AI's response
            await update.message.reply_text(
                f"I couldn't find specific locations matching '{query}', but here's what I know:\n\n{response_text}"
            )

    except Exception as e:
        logger.error(f"Error processing with AI: {e}")
        await update.message.reply_text("Sorry, I'm having trouble understanding that location request.")
