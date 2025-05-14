import re
import logging
from typing import Dict, Any, Optional, List, Tuple
from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

# Define conversation states
WAITING_FOR_COLLEGE = 1

# College aliases dictionary for reuse - same as locker service but add Coffee Bar
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

    # Coffee Bar
    "coffee bar": "Coffee Bar",
    "café": "Coffee Bar",
    "cafe": "Coffee Bar",
    "bar": "Coffee Bar"
}

# Meal type aliases
MEAL_ALIASES = {
    # Standard meals
    "breakfast": "breakfast",
    "morning": "breakfast",

    "lunch": "lunch",
    "noon": "lunch",
    "midday": "lunch",

    "dinner": "dinner",
    "evening": "dinner",
    "supper": "dinner",

    # Special offerings
    "pizza": "pizza/pasta",
    "pasta": "pizza/pasta",
    "pizza pasta": "pizza/pasta",

    "burger": "burgers/loaded fries",
    "burgers": "burgers/loaded fries",
    "loaded fries": "burgers/loaded fries",
    "fries": "burgers/loaded fries"
}


def parse_servery_hours(data):
    """Parse servery hours data from Supabase into a usable format for the bot"""
    servery_hours = {}

    for record in data:
        college_name = record["colleges"]["name"] if record.get("colleges") else "Unknown"
        day_name = record["days"]["name"].lower() if record.get("days") else "Unknown"
        meal_type = record["meal_type"].lower() if record.get("meal_type") else "Unknown"

        if record.get("time_ranges"):
            time_info = f"{record['time_ranges']['start_time']} - {record['time_ranges']['end_time']}"
        else:
            time_info = "Hours not specified"

        # Initialize nested dictionaries if needed
        if college_name not in servery_hours:
            servery_hours[college_name] = {}
        if day_name not in servery_hours[college_name]:
            servery_hours[college_name][day_name] = {}

        servery_hours[college_name][day_name][meal_type] = time_info

    return servery_hours


async def handle_servery_hours(update: Update, context: ContextTypes.DEFAULT_TYPE, query: str = None) -> None:
    """Handle queries about servery hours"""
    text = query or update.message.text.lower()
    servery_data = context.bot_data["servery_hours"]

    # Initialize user data dictionary if it doesn't exist
    if 'servery_conversations' not in context.bot_data:
        context.bot_data['servery_conversations'] = {}

    user_id = update.effective_user.id

    # Check if we're in an active servery conversation
    if user_id in context.bot_data['servery_conversations']:
        await _handle_servery_conversation_follow_up(update, context, text, servery_data, user_id)
        return

    # New servery query
    # First try to find college in the query
    matched_college = _find_college_in_text(text)

    if not matched_college:
        # Start a conversation to get the college
        await _start_college_conversation(update, context, text, user_id)
        return

    # Extract day and meal type from query
    day, meal = _extract_day_and_meal(text)

    # Create response
    await _respond_with_servery_hours(update, matched_college, day, meal, servery_data)


async def _handle_servery_conversation_follow_up(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        text: str,
        servery_data: Dict[str, Any],
        user_id: int
) -> None:
    """
    Handle follow-up response in a servery conversation

    Args:
        update: Telegram update
        context: Bot context
        text: User message text
        servery_data: Servery hours data
        user_id: User ID
    """
    college_response = text.lower()
    matched_college = _find_college_in_text(college_response)

    # If no match in current response, check original query too
    original_query = context.bot_data['servery_conversations'].get(f"{user_id}_query", "")
    if not matched_college:
        matched_college = _find_college_in_text(original_query)

    # Clear conversation state
    del context.bot_data['servery_conversations'][user_id]

    if matched_college:
        # Extract day and meal type using both the original and current message
        combined_text = original_query + " " + text
        day, meal = _extract_day_and_meal(combined_text)

        # Create response
        await _respond_with_servery_hours(update, matched_college, day, meal, servery_data)
    else:
        await update.message.reply_text(
            "❓ I couldn't identify that servery. Please mention one of: Krupp, College III, Nordmetall, Mercator")


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


def _extract_day_and_meal(text: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Extract day and meal type information from text
    """
    # Extract meal type
    meal = None
    for alias, real_meal in MEAL_ALIASES.items():
        if alias in text.lower():
            meal = real_meal
            break

    # If no match found for special meals, check for partial matches
    if not meal:
        if "pizza" in text.lower() or "pasta" in text.lower():
            meal = "pizza/pasta"
        elif "burger" in text.lower() or "fries" in text.lower():
            meal = "burgers/loaded fries"

    # Extract day (unchanged)
    day = None
    if "monday" in text.lower():
        day = "monday"
    elif "tuesday" in text.lower():
        day = "tuesday"
    elif "wednesday" in text.lower():
        day = "wednesday"
    elif "thursday" in text.lower():
        day = "thursday"
    elif "friday" in text.lower():
        day = "friday"
    elif "weekend" in text.lower() or "saturday" in text.lower() or "sunday" in text.lower():
        day = "weekend"
    elif "holiday" in text.lower():
        day = "holiday"
    elif "weekday" in text.lower():
        day = "weekday"

    return day, meal


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
    context.bot_data['servery_conversations'][user_id] = WAITING_FOR_COLLEGE
    context.bot_data['servery_conversations'][f"{user_id}_query"] = text

    await update.message.reply_text(
        "❓ Which servery would you like information about? (Krupp, College III, Nordmetall, Mercator, or Coffee Bar)")


async def _respond_with_servery_hours(
        update: Update,
        college: str,
        day: Optional[str],
        meal: Optional[str],
        servery_data: Dict[str, Any]
) -> None:
    """
    Create and send response with servery hours
    """
    message = f"🍽 Servery Hours for *{college}*:\n"

    # Format function to make meal types look nicer
    def format_meal_type(meal_type: str) -> str:
        # Capitalize each word and replace slashes with suitable emoji
        if "/" in meal_type:
            # For special meal types with slashes
            parts = meal_type.split("/")
            formatted = " 🍽 ".join(part.strip().title() for part in parts)
            return formatted
        else:
            # For standard meals
            return meal_type.title()

    if day:
        if day in servery_data[college]:
            message += f"\n📅 {day.title()}:\n"
            if meal:
                time = servery_data[college][day].get(meal)
                if time:
                    message += f"- {format_meal_type(meal)}: {time}\n"
                else:
                    message += f"- No info for {format_meal_type(meal)} on {day}.\n"
            else:
                for meal_type, hours in servery_data[college][day].items():
                    message += f"- {format_meal_type(meal_type)}: {hours}\n"
        else:
            message += "- No info for that day.\n"
    else:
        for d, meals in servery_data[college].items():
            message += f"\n📅 {d.title()}:\n"
            if meal:
                hours = meals.get(meal)
                if hours:
                    message += f"- {format_meal_type(meal)}: {hours}\n"
                else:
                    message += f"- No {format_meal_type(meal)} hours available for {d}.\n"
            else:
                for meal_type, time in meals.items():
                    message += f"- {format_meal_type(meal_type)}: {time}\n"

    await update.message.reply_text(message, parse_mode="Markdown")
