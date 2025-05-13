import re
import logging
from typing import Dict, Any, Optional, List
from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

# Define conversation states
WAITING_FOR_COLLEGE = 1

# College aliases dictionary for reuse
COLLEGE_ALIASES = {
    # Krupp
    "krupp": "Krupp College",
    "krupp college": "Krupp College",

    # College III
    "college iii": "College III",
    "college 3": "College III",
    "c3": "College III",

    # Nordmetall
    "nordmetall": "Nordmetall College",
    "nordmetall college": "Nordmetall College",
    "nord": "Nordmetall College",

    # Mercator
    "mercator": "Mercator College",
    "mercator college": "Mercator College",
}


def parse_locker_hours(data):
    """Parse locker hours data from Supabase into a usable format for the bot"""
    locker_hours = {}

    for record in data:
        college_name = record["colleges"]["name"] if record.get("colleges") else "Unknown"
        day_name = record["days"]["name"].lower() if record.get("days") else "Unknown"
        basement = record["basement"].upper() if record.get("basement") else "Unknown"

        if record.get("time_ranges"):
            time_info = f"{record['time_ranges']['start_time']} - {record['time_ranges']['end_time']}"
        else:
            time_info = "Hours not specified"

        # Initialize nested dictionaries if needed
        if college_name not in locker_hours:
            locker_hours[college_name] = {}
        if day_name not in locker_hours[college_name]:
            locker_hours[college_name][day_name] = {}

        locker_hours[college_name][day_name][basement] = time_info

    return locker_hours


async def handle_locker_hours(update: Update, context: ContextTypes.DEFAULT_TYPE, query: str = None) -> None:
    """Handle queries about locker hours"""
    text = query or update.message.text.lower()
    locker_data = context.bot_data["locker_hours"]

    # Initialize user data dictionary if it doesn't exist
    if 'locker_conversations' not in context.bot_data:
        context.bot_data['locker_conversations'] = {}

    user_id = update.effective_user.id

    # Check if we're in an active locker conversation
    if user_id in context.bot_data['locker_conversations']:
        await _handle_locker_conversation_follow_up(update, context, text, locker_data, user_id)
        return

    # New locker query
    # First try to find college in the query
    matched_college = _find_college_in_text(text)

    if not matched_college:
        # Start a conversation to get the college
        await _start_college_conversation(update, context, text, user_id)
        return

    # Extract day and basement from query
    day, basement = _extract_day_and_basement(text)

    # Create response
    await _respond_with_locker_hours(update, matched_college, day, basement, locker_data)


async def _handle_locker_conversation_follow_up(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,

        text: str,
        locker_data: Dict[str, Any],
        user_id: int
) -> None:
    """
    Handle follow-up response in a locker conversation

    Args:
        update: Telegram update
        context: Bot context
        text: User message text
        locker_data: Locker hours data
        user_id: User ID
    """
    college_response = text.lower()
    matched_college = _find_college_in_text(college_response)

    # If no match in current response, check original query too
    original_query = context.bot_data['locker_conversations'].get(f"{user_id}_query", "")
    if not matched_college:
        matched_college = _find_college_in_text(original_query)

    # Clear conversation state
    del context.bot_data['locker_conversations'][user_id]

    if matched_college:
        # Extract day and basement using both the original and current message
        combined_text = original_query + " " + text
        day, basement = _extract_day_and_basement(combined_text)

        # Create response
        await _respond_with_locker_hours(update, matched_college, day, basement, locker_data)
    else:
        await update.message.reply_text(
            "❓ I couldn't identify that college. Please mention one of: Krupp, College III, Nordmetall, or Mercator.")


def _find_college_in_text(text: str) -> Optional[str]:
    """
    Find college name mentioned in text

    Args:
        text: Text to search in

    Returns:
        College name or None
    """
    # First try exact matches
    for alias, real in COLLEGE_ALIASES.items():
        if alias in text.lower():
            return real

    # Then try partial matches
    for alias, real in COLLEGE_ALIASES.items():
        if any(word in alias for word in text.lower().split()):
            return real

    return None


def _extract_day_and_basement(text: str) -> tuple[Optional[str], Optional[str]]:
    """
    Extract day and basement information from text

    Args:
        text: Text to parse

    Returns:
        Tuple of (day, basement)
    """
    basement = None
    m = re.search(r'\b(?:basement\s*)?([abcdf])\b', text, re.I)
    if m:
        basement = m.group(1).upper()

    day = None
    if "monday" in text.lower():
        day = "monday"
    elif "thursday" in text.lower():
        day = "thursday"

    return day, basement


async def _start_college_conversation(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        text: str,
        user_id: int
) -> None:
    """
    Start a conversation to get college information

    Args:
        update: Telegram update
        context: Bot context
        text: Original query text
        user_id: User ID
    """
    # Set the conversation state and store the original query
    context.bot_data['locker_conversations'][user_id] = WAITING_FOR_COLLEGE
    context.bot_data['locker_conversations'][f"{user_id}_query"] = text

    await update.message.reply_text(
        "❓ Please mention the college (Krupp, College III, Nordmetall, or Mercator).")


async def _respond_with_locker_hours(
        update: Update,
        college: str,
        day: Optional[str],
        basement: Optional[str],
        locker_data: Dict[str, Any]
) -> None:
    """
    Create and send response with locker hours

    Args:
        update: Telegram update
        college: College name
        day: Day name or None for all days
        basement: Basement letter or None for all basements
        locker_data: Locker hours data
    """
    message = f"🔓 Locker Hours for *{college}*:\n"

    if day:
        if day in locker_data[college]:
            message += f"\n📅 {day.title()}:\n"
            if basement:
                time = locker_data[college][day].get(basement)
                if time:
                    message += f"- Basement {basement}: {time}\n"
                else:
                    message += f"- No info for Basement {basement}.\n"
            else:
                for base, hours in locker_data[college][day].items():
                    message += f"- Basement {base}: {hours}\n"
        else:
            message += "- No info for that day.\n"
    else:
        for d, basements in locker_data[college].items():
            message += f"\n📅 {d.title()}:\n"
            if basement:
                hours = basements.get(basement)
                if hours:
                    message += f"- Basement {basement}: {hours}\n"
            else:
                for base, time in basements.items():
                    message += f"- Basement {base}: {time}\n"

    await update.message.reply_text(message, parse_mode="Markdown")