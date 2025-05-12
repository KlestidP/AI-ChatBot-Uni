import re
import logging
from telegram import Update
from telegram.ext import ContextTypes
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from typing import List, Dict, Any, Optional

from uni_ai_chatbot.data.campus_map_data import find_locations_by_feature

from uni_ai_chatbot.data.campus_map_data import extract_feature_keywords

logger = logging.getLogger(__name__)



async def show_location_details(update: Update, location, is_callback=False):
    """Show details and venue for a location"""
    # Create information text
    info_text = f"📍 *{location['name']}*\n"

    if location.get('tags'):
        features = location['tags'].split(',')
        features_text = ", ".join([f.strip() for f in features])
        info_text += f"Features: {features_text}\n"

    if location.get('aliases'):
        aliases = location['aliases'].split(',')
        aliases_text = ", ".join([a.strip() for a in aliases])
        info_text += f"Also known as: {aliases_text}\n"

    # Send message differently depending on if it's a callback or direct message
    if is_callback:
        await update.callback_query.edit_message_text(
            text=info_text,
            parse_mode="Markdown"
        )
        # Send venue as a new message
        await update.effective_chat.send_venue(
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


async def handle_location_with_ai(update: Update, context: ContextTypes.DEFAULT_TYPE, query: str):
    """
    Use AI to understand and respond to location-related queries
    Leverages AI for understanding and matching locations
    """
    campus_map = context.bot_data["campus_map"]
    location_qa_chain = context.bot_data["location_qa_chain"]
    llm = context.bot_data.get("llm")

    try:
        # First, try to use the LLM to match specific locations
        if llm:
            location_names = [loc["name"] for loc in campus_map]
            aliases = []
            for loc in campus_map:
                if loc.get("aliases"):
                    aliases.extend([alias.strip() for alias in loc["aliases"].split(",")])

            all_locations = location_names + aliases

            # Create a classification prompt
            location_prompt = f"""You are a university location assistant. The user query is: "{query}"

The available campus locations are: {', '.join(all_locations)}

Which specific location, if any, is the user asking about? If the query is about a specific location, respond with just that location name. If the query is about a feature (like printers, food, etc.) or is not about a specific location, respond with "feature query".
"""

            try:
                # Ask the LLM to identify the location
                response = llm.invoke(location_prompt)
                matched_location = response.content.strip()

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
        feature_keywords = extract_feature_keywords(query)

        # If explicit features mentioned, show all matching locations
        if feature_keywords:
            locations = find_locations_by_feature(campus_map, feature_keywords)

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
                    feature_text = " and ".join(feature_keywords)
                    await update.message.reply_text(
                        f"I found {len(locations)} places with {feature_text}. Which one would you like to see?",
                        reply_markup=reply_markup
                    )
                    return

        # If we haven't found any matches yet, use the LLM-based QA approach
        ai_query = f"The user wants to know about a location on campus with this query: {query}. Please help find the most relevant locations."
        response = location_qa_chain.invoke(ai_query)
        location_info = response['result']

        # Use LLM to extract location names from the response
        extract_prompt = f"""From the following text about campus locations, extract all specific location names mentioned:

{location_info}

List just the names of locations, one per line, with no additional text.
"""

        location_names = []
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
        matched_locations = []
        for name in location_names:
            for loc in campus_map:
                if name.lower() in loc["name"].lower():
                    if loc not in matched_locations:
                        matched_locations.append(loc)
                    break

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
                f"I couldn't find specific locations matching your query, but here's what I know:\n\n{location_info}"
            )

    except Exception as e:
        logger.error(f"Error processing with AI: {e}")
        await update.message.reply_text("Sorry, I'm having trouble understanding that location request.")