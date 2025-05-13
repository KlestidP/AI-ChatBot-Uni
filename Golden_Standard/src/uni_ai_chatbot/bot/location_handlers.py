import logging
from typing import List, Dict, Any, Optional
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, Message, Chat
from telegram.ext import ContextTypes

from uni_ai_chatbot.data.campus_map_data import find_locations_by_feature, extract_feature_keywords
from uni_ai_chatbot.configurations.config import MAX_LOCATIONS_TO_DISPLAY

logger = logging.getLogger(__name__)


async def show_location_details(update: Update, location: Dict[str, Any], is_callback: bool = False) -> None:
    info_text: str = f"📍 *{location['name']}*\n"

    if location.get('tags'):
        features: List[str] = location['tags'].split(',')
        features_text: str = ", ".join([f.strip() for f in features])
        info_text += f"Features: {features_text}\n"

    if location.get('aliases'):
        aliases: List[str] = location['aliases'].split(',')
        aliases_text: str = ", ".join([a.strip() for a in aliases])
        info_text += f"Also known as: {aliases_text}\n"

    chat: Chat = update.effective_chat

    if is_callback:
        await update.callback_query.edit_message_text(
            text=info_text,
            parse_mode="Markdown"
        )
        await chat.send_venue(
            latitude=float(location['latitude']),
            longitude=float(location['longitude']),
            title=location['name'],
            address=location.get('address', 'Constructor University, Bremen')
        )
    else:
        await update.message.reply_text(
            text=info_text,
            parse_mode="Markdown"
        )
        await update.message.reply_venue(
            latitude=float(location['latitude']),
            longitude=float(location['longitude']),
            title=location['name'],
            address=location.get('address', 'Constructor University, Bremen')
        )


async def handle_location_with_ai(update: Update, context: ContextTypes.DEFAULT_TYPE, query: str) -> None:
    campus_map: List[Dict[str, Any]] = context.bot_data["campus_map"]
    location_qa_chain = context.bot_data["location_qa_chain"]
    llm = context.bot_data.get("llm")

    try:
        if matched_location := await _match_specific_location(llm, campus_map, query):
            await show_location_details(update, matched_location)
            return

        if await _handle_feature_based_query(update, campus_map, query):
            return

        await _respond_with_location_qa(update, location_qa_chain, llm, campus_map, query)

    except Exception as e:
        logger.error(f"Error processing with AI: {e}")
        await update.message.reply_text("Sorry, I'm having trouble understanding that location request.")


async def _match_specific_location(llm, campus_map: List[Dict[str, Any]], query: str) -> Optional[Dict[str, Any]]:
    if not llm:
        return None

    try:
        location_names = [loc["name"] for loc in campus_map]
        aliases = []
        for loc in campus_map:
            if loc.get("aliases"):
                aliases.extend([alias.strip() for alias in loc["aliases"].split(",")])

        all_locations = location_names + aliases

        location_prompt = f"""You are a university location assistant. The user query is: "{query}"

The available campus locations are: {', '.join(all_locations)}

Which specific location, if any, is the user asking about? If the query is about a specific location, respond with just that location name. If the query is about a feature (like printers, food, etc.) or is not about a specific location, respond with "feature query".
"""
        response = llm.invoke(location_prompt)
        matched_location = response.content.strip()

        if matched_location.lower() != "feature query":
            for loc in campus_map:
                if loc["name"].lower() == matched_location.lower():
                    return loc
                if loc.get("aliases") and matched_location.lower() in [alias.strip().lower() for alias in loc["aliases"].split(",")]:
                    return loc
    except Exception as e:
        logger.warning(f"LLM location matching failed: {e}")

    return None


async def _handle_feature_based_query(update: Update, campus_map: List[Dict[str, Any]], query: str) -> bool:
    feature_keywords = extract_feature_keywords(query)

    if not feature_keywords:
        return False

    locations = find_locations_by_feature(campus_map, feature_keywords)

    if not locations:
        return False

    if len(locations) == 1:
        await show_location_details(update, locations[0])
        return True
    else:
        keyboard = [
            [InlineKeyboardButton(text=loc['name'], callback_data=f"location:{loc['id']}")]
            for loc in locations[:MAX_LOCATIONS_TO_DISPLAY]
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)
        feature_text = " and ".join(feature_keywords)
        await update.message.reply_text(
            f"I found {len(locations)} places with {feature_text}. Which one would you like to see?",
            reply_markup=reply_markup
        )
        return True


async def _respond_with_location_qa(update: Update, location_qa_chain, llm, campus_map: List[Dict[str, Any]], query: str) -> None:
    ai_query = f"The user wants to know about a location on campus with this query: {query}. Please help find the most relevant locations."
    response = location_qa_chain.invoke(ai_query)
    location_info = response['result']

    if not await _show_locations_from_ai_response(update, llm, campus_map, location_info):
        await update.message.reply_text(
            f"I couldn't find specific locations matching your query, but here's what I know:\n\n{location_info}"
        )


async def _show_locations_from_ai_response(update: Update, llm, campus_map: List[Dict[str, Any]], location_info: str) -> bool:
    location_names = []

    if llm:
        try:
            extract_prompt = f"""From the following text about campus locations, extract all specific location names mentioned:

{location_info}

List just the names of locations, one per line, with no additional text.
"""
            extract_response = llm.invoke(extract_prompt)
            location_names = [name.strip() for name in extract_response.content.strip().split("\n") if name.strip()]
        except Exception as e:
            logger.warning(f"Failed to extract locations with LLM: {e}")

    if not location_names:
        try:
            import re
            location_names = re.findall(r'\b[A-Z][a-zA-Z\s]+(College|Hall|Lab|Center|Centre|Building)\b', location_info)
        except Exception as e:
            logger.warning(f"Regex location extraction failed: {e}")
            return False

    matched_locations = []
    for name in location_names:
        for loc in campus_map:
            if name.lower() in loc["name"].lower() and loc not in matched_locations:
                matched_locations.append(loc)
                break

    if not matched_locations:
        return False

    keyboard = [
        [InlineKeyboardButton(text=loc['name'], callback_data=f"location:{loc['id']}")]
        for loc in matched_locations[:MAX_LOCATIONS_TO_DISPLAY]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        f"Based on your question, here are some relevant places:",
        reply_markup=reply_markup
    )
    return True