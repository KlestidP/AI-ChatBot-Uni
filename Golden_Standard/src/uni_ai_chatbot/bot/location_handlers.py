import re
import logging
from telegram import Update
from telegram.ext import ContextTypes
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


def find_location_by_name_or_alias(locations: List[Dict[str, Any]], query: str) -> Optional[Dict[str, Any]]:
    """Find a location by its name or alias (case-insensitive)"""
    query = query.lower().strip()

    # First try exact match on name
    for location in locations:
        if location['name'].lower() == query:
            return location

    # Then try exact match on alias
    for location in locations:
        if location.get('aliases'):
            aliases = [alias.strip().lower() for alias in location['aliases'].split(',')]
            if query in aliases:
                return location

    # If no exact match, try partial match on name
    for location in locations:
        if query in location['name'].lower():
            return location

    # Finally try partial match on alias
    for location in locations:
        if location.get('aliases'):
            aliases = [alias.strip().lower() for alias in location['aliases'].split(',')]
            for alias in aliases:
                if query in alias or alias in query:
                    return location

    return None


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
    """Use AI to understand and respond to location-related queries"""
    qa_chain = context.bot_data["qa_chain"]
    campus_map = context.bot_data["campus_map"]

    try:
        # Ask the AI about the location
        ai_query = f"What places on campus match this description: {query}? Please mention specific location names only."
        response = qa_chain.invoke(ai_query)
        response_text = response['result']

        # Extract location names from the AI's response
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
