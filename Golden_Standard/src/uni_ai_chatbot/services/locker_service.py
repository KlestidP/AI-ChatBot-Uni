import re
import logging
from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

# Define conversation states
WAITING_FOR_COLLEGE = 1


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

        status = record.get("status", "Unknown")

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
        # We were waiting for a college name
        college_response = text.lower()

        # Match the college response
        matched_college = None
        aliases = {
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

        # Try to match the college from their response
        for alias, real in aliases.items():
            if alias in college_response:
                matched_college = real
                break

        # Check for partial matches if no exact match
        if not matched_college:
            for alias, real in aliases.items():
                if any(word in alias for word in college_response.split()):
                    matched_college = real
                    break

        # Clear the conversation state
        del context.bot_data['locker_conversations'][user_id]

        if matched_college:
            # Extract day and basement from the original query
            original_query = context.bot_data['locker_conversations'].get(f"{user_id}_query", "")

            basement = None
            m = re.search(r'\b(?:basement\s*)?([abcdf])\b', original_query + " " + text, re.I)
            if m:
                basement = m.group(1).upper()

            day = None
            if "monday" in original_query.lower() + " " + text.lower():
                day = "monday"
            elif "thursday" in original_query.lower() + " " + text.lower():
                day = "thursday"

            # Prepare the response
            message = f"🔓 Locker Hours for *{matched_college}*:\n"

            if day:
                if day in locker_data[matched_college]:
                    message += f"\n📅 {day.title()}:\n"
                    if basement:
                        time = locker_data[matched_college][day].get(basement)
                        if time:
                            message += f"- Basement {basement}: {time}\n"
                        else:
                            message += f"- No info for Basement {basement}.\n"
                    else:
                        for base, hours in locker_data[matched_college][day].items():
                            message += f"- Basement {base}: {hours}\n"
                else:
                    message += "- No info for that day.\n"
            else:
                for d, basements in locker_data[matched_college].items():
                    message += f"\n📅 {d.title()}:\n"
                    if basement:
                        hours = basements.get(basement)
                        if hours:
                            message += f"- Basement {basement}: {hours}\n"
                    else:
                        for base, time in basements.items():
                            message += f"- Basement {base}: {time}\n"

            await update.message.reply_text(message, parse_mode="Markdown")
            return
        else:
            await update.message.reply_text(
                "❓ I couldn't identify that college. Please mention one of: Krupp, College III, Nordmetall, or Mercator.")
            return

    # New locker query
    # First try to find college in the query
    aliases = {
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

    matched_college = None
    for alias, real in aliases.items():
        if alias in text:
            matched_college = real
            break

    if not matched_college:
        # Set the conversation state and store the original query
        context.bot_data['locker_conversations'][user_id] = WAITING_FOR_COLLEGE
        context.bot_data['locker_conversations'][f"{user_id}_query"] = text

        await update.message.reply_text(
            "❓ Please mention the college (Krupp, College III, Nordmetall, or Mercator).")
        return

    basement = None
    m = re.search(r'\b(?:basement\s*)?([abcdf])\b', text, re.I)
    if m:
        basement = m.group(1).upper()

    day = None
    if "monday" in text:
        day = "monday"
    elif "thursday" in text:
        day = "thursday"

    message = f"🔓 Locker Hours for *{matched_college}*:\n"

    if day:
        if day in locker_data[matched_college]:
            message += f"\n📅 {day.title()}:\n"
            if basement:
                time = locker_data[matched_college][day].get(basement)
                if time:
                    message += f"- Basement {basement}: {time}\n"
                else:
                    message += f"- No info for Basement {basement}.\n"
            else:
                for base, hours in locker_data[matched_college][day].items():
                    message += f"- Basement {base}: {hours}\n"
        else:
            message += "- No info for that day.\n"
    else:
        for d, basements in locker_data[matched_college].items():
            message += f"\n📅 {d.title()}:\n"
            if basement:
                hours = basements.get(basement)
                if hours:
                    message += f"- Basement {basement}: {hours}\n"
            else:
                for base, time in basements.items():
                    message += f"- Basement {base}: {time}\n"

    await update.message.reply_text(message, parse_mode="Markdown")