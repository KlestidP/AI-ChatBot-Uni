import logging
from typing import List, Dict, Any
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, Message, Chat
from telegram.ext import ContextTypes

from uni_ai_chatbot.data.campus_map_data import find_locations_by_feature, extract_feature_keywords

logger = logging.getLogger(__name__)


async def show_location_details(update: Update, location: Dict[str, Any], is_callback: bool = False) -> None:
    """
    Show details and venue for a location

    Args:
        update: Telegram Update object
        location: Dictionary containing location information
        is_callback: Whether this is being called from a callback
    """
    # Create information text
    info_text: str = f"📍 *{location['name']}*\n"

    if location.get('tags'):
        features: List[str] = location['tags'].split(',')
        features_text: str = ", ".join([f.strip() for f in features])
        info_text += f"Features: {features_text}\n"

    if location.get('aliases'):
        aliases: List[str] = location['aliases'].split(',')
        aliases_text: str = ", ".join([a.strip() for a in aliases])
        info_text += f"Also known as: {aliases_text}\n"

    # Send message differently depending on if it's a callback or direct message
    chat: Chat = update.effective_chat

    if is_callback:
        await update.callback_query.edit_message_text(
            text=info_text,
            parse_mode="Markdown"
        )
        # Send venue as a new message
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
        # Send venue
        await update.message.reply_venue(
            latitude=float(location['latitude']),
            longitude=float(location['longitude']),
            title=location['name'],
            address=location.get('address', 'Constructor University, Bremen')
        )


async def handle_location_with_ai(update: Update, context: ContextTypes.DEFAULT_TYPE, query: str) -> None:
    """
    Use AI to understand and respond to location-related queries
    Leverages AI for understanding and matching locations

    Args:
        update: Telegram Update object
        context: Telegram context
        query: The user's message text
    """
    campus_map: List[Dict[str, Any]] = context.bot_data["campus_map"]
    location_qa_chain = context.bot_data["location_qa_chain"]
    llm = context.bot_data.get("llm")

    try:
        # First, try to use the LLM to match specific locations
        if llm:
            location_names: List[str] = [loc["name"] for loc in campus_map]
            aliases: List[str] = []
            for loc in campus_map:
                if loc.get("aliases"):
                    aliases.extend([alias.strip() for alias in loc["aliases"].split(",")])

            all_locations: List[str] = location_names + aliases

            # Create a classification prompt
            location_prompt: str = f"""You are a university location assistant. The user query is: "{query}"

The available campus locations are: {', '.join(all_locations)}

Which specific location, if any, is the user asking about? If the query is about a specific location, respond with just that location name. If the query is about a feature (like printers, food, etc.) or is not about a specific location, respond with "feature query".
"""

            try:
                # Ask the LLM to identify the location
                response = llm.invoke(location_prompt)
                matched_location: str = response.content.strip()

                # If the LLM identified a specific location, find it in our data
                if matched_location.lower() != "feature query":
                    for loc in campus_map:
                        if loc["name"].lower() == matched_location.lower():
                            await show_location_details(update, loc)
                            return
                        if loc.get("aliases") and matched_location.lower() in [alias.strip().lower() for alias in
                                                                               loc["aliases"].split(",")]:
                            await show_location_details(update, loc)
                            return
            except Exception as e:
                logger.warning(f"LLM location matching failed: {e}, falling back to feature search")

        # If it's a feature query or LLM didn't find a match, extract features and find locations
        feature_keywords: List[str] = extract_feature_keywords(query)

        # If explicit features mentioned, show all matching locations
        if feature_keywords:
            locations: List[Dict[str, Any]] = find_locations_by_feature(campus_map, feature_keywords)

            if locations:
                if len(locations) == 1:
                    # Only one location found, show it directly
                    location: Dict[str, Any] = locations[0]
                    await show_location_details(update, location)
                    return
                else:
                    # Multiple locations found, show a keyboard to select
                    keyboard: List[List[InlineKeyboardButton]] = []
                    for loc in locations[:8]:  # Limit to 8 options
                        keyboard.append([InlineKeyboardButton(
                            text=loc['name'],
                            callback_data=f"location:{loc['id']}"
                        )])

                    reply_markup: InlineKeyboardMarkup = InlineKeyboardMarkup(keyboard)
                    feature_text: str = " and ".join(feature_keywords)
                    await update.message.reply_text(
                        f"I found {len(locations)} places with {feature_text}. Which one would you like to see?",
                        reply_markup=reply_markup
                    )
                    return

        # If we haven't found any matches yet, use the LLM-based QA approach
        ai_query: str = f"The user wants to know about a location on campus with this query: {query}. Please help find the most relevant locations."
        response = location_qa_chain.invoke(ai_query)
        location_info: str = response['result']

        # Use LLM to extract location names from the response
        extract_prompt: str = f"""From the following text about campus locations, extract all specific location names mentioned:

{location_info}

List just the names of locations, one per line, with no additional text.
"""

        location_names: List[str] = []
        if llm:
            try:
                extract_response = llm.invoke(extract_prompt)
                location_names = [name.strip() for name in extract_response.content.strip().split("\n") if name.strip()]
            except Exception:
                # Fall back to regex if LLM extraction fails
                import re
                location_names = re.findall(r'\b[A-Z][a-zA-Z\s]+(College|Hall|Lab|Center|Centre|Building)\b',
                                            location_info)

                # Match extracted names to our campus map
            matched_locations: List[Dict[str, Any]] = []
            for name in location_names:
                for loc in campus_map:
                    if name.lower() in loc["name"].lower():
                        if loc not in matched_locations:
                            matched_locations.append(loc)
                        break

            if matched_locations:
                # Locations found, show options
                keyboard: List[List[InlineKeyboardButton]] = []
                for loc in matched_locations[:8]:  # Limit to 8 options
                    keyboard.append([InlineKeyboardButton(
                        text=loc['name'],
                        callback_data=f"location:{loc['id']}"
                    )])

                reply_markup: InlineKeyboardMarkup = InlineKeyboardMarkup(keyboard)
                await update.message.reply_text(
                    f"Based on your question, here are some relevant places:",
                    reply_markup=reply_markup
                )
            else:
                # No matches, just show the AI's response
                await update.message.reply_text(
                    f"I couldn't find specific locations matching your query, but here's what I know:\n\n{location_info}"
                )

    except Exception as e:
        logger.error(f"Error processing with AI: {e}")
        await update.message.reply_text("Sorry, I'm having trouble understanding that location request.")