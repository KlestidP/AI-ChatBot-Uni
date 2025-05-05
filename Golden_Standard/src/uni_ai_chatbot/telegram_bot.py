import os
import logging
import re
from pathlib import Path
from telegram import Update, BotCommand
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from langchain.chains import RetrievalQA
from langchain_core.documents import Document
from langchain_community.vectorstores import FAISS
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_mistralai import MistralAIEmbeddings
from langchain_mistralai import ChatMistralAI
from uni_ai_chatbot.resources import load_faq_answers
from dotenv import load_dotenv
from uni_ai_chatbot.campus_map_data import load_campus_map
from uni_ai_chatbot.locker_hours_loader import load_locker_hours
from difflib import get_close_matches

load_dotenv()
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
MISTRAL_API_KEY = os.environ.get("MISTRAL_API_KEY")
if not TELEGRAM_TOKEN:
    raise ValueError("TELEGRAM_TOKEN is not set in environment variables")
if not MISTRAL_API_KEY:
    raise ValueError("MISTRAL_API_KEY is not set in environment variables")

FAQ_ANSWERS = load_faq_answers()


def get_resource(relative_path):
    # Helper function to handle resource paths
    base_dir = Path(__file__).parent
    return str(base_dir / relative_path)


def initialize_qa_chain():
    # Create documents directly from database content
    documents = []

    # Add FAQ data as documents
    faq_data = load_faq_answers()
    for question, answer in faq_data.items():
        doc_content = f"Question: {question}\nAnswer: {answer}"
        documents.append(Document(page_content=doc_content))

    # Add campus location data as documents
    campus_data = load_campus_map()
    for location in campus_data:
        location_type = location.get("type", "Unknown")
        area_name = location["campus_areas"]["name"] if location.get("campus_areas") else "Unknown area"
        doc_content = f"Location: {location['name']}\nType: {location_type}\nArea: {area_name}"
        documents.append(Document(page_content=doc_content))

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=200,
        chunk_overlap=20,
        separators=["\\n\\n", "\\n", ".", " ", ""]
    )
    split_docs = text_splitter.split_documents(documents)
    embeddings = MistralAIEmbeddings(api_key=MISTRAL_API_KEY)
    vector_store = FAISS.from_texts([doc.page_content for doc in split_docs], embeddings)
    retriever = vector_store.as_retriever()
    llm = ChatMistralAI(
        model="mistral-large-latest",
        temperature=0,
        max_retries=2,
        api_key=MISTRAL_API_KEY
    )
    return RetrievalQA.from_chain_type(llm=llm, retriever=retriever)


def parse_campus_map_data(data):
    """Parse campus map data from Supabase into a more usable format"""
    campus_map = []
    for location in data:
        location_info = {
            "name": location["name"],
            "type": location["type"],
            "aliases": [],  # Placeholder for aliases
            "direction": "central",  # Default placeholder - would need to be in your actual data
            "category": location["type"],  # Using type as category
        }

        if location.get("campus_areas"):
            location_info["area"] = location["campus_areas"]["name"]

            # Map areas to directions (simplified example)
            area_to_direction = {
                "North Campus": "north",
                "South Campus": "south",
                "East Campus": "east",
                "West Campus": "west",
                "Central Campus": "central"
            }
            location_info["direction"] = area_to_direction.get(location_info["area"], "central")

        campus_map.append(location_info)
    return campus_map


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


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    await update.message.reply_text(
        "Hi! I'm your University Info Bot. Ask me any question about college schedules, fees, or events!"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /help is issued."""
    await update.message.reply_text(
        "Here's what I can help you with:\n\n"
        "• 📍 `/where [location]` — Find places on campus (e.g., Ocean Lab, C3, IRC).\n\n"
        "• 🧺 *Locker hours* — Ask for locker access times in any college.\n\n"
        "• 🍽 *Servery hours* — Ask for meal times in your college or the coffee bar.\n\n"
        "• ❓ *University FAQs* — Ask about documents, laundry, residence permits, etc.\n\n"
        "• 🗓 *College events* — Get updates on announcements and upcoming activities.\n\n"
        "💬 Just type your question — I'll understand natural language too!\n\n"
        "🔒 Bot is limited to university-related queries only."
    )


def resolve_location_name(query, campus_map):
    """Find a location name in the campus map data using fuzzy matching"""
    names = []
    lookup = {}

    for place in campus_map:
        names.append(place["name"])
        lookup[place["name"].lower()] = place
        for alias in place.get("aliases", []):
            names.append(alias)
            lookup[alias.lower()] = place

    matches = get_close_matches(query.lower(), names, n=1, cutoff=0.6)
    if matches:
        match = matches[0].lower()
        return lookup[match]["name"]
    return None


def get_location_info(query, campus_map):
    """Get information about a campus location"""
    names = []
    lookup = {}

    for place in campus_map:
        main_name = place["name"]
        names.append(main_name)
        lookup[main_name.lower()] = place

        for alias in place.get("aliases", []):
            names.append(alias)
            lookup[alias.lower()] = place

    matches = get_close_matches(query.lower(), names, n=1, cutoff=0.6)
    if matches:
        match = matches[0].lower()
        place = lookup[match]
        return f"{place['name']} is in the {place['direction'].lower()} part of campus and is a {place['type'].lower()} facility."

    return "Sorry, I couldn't find that place on the map."



async def where_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Respond to /where command with location info"""
    query = ' '.join(context.args)
    if not query:
        await update.message.reply_text(
            "Please provide a location name.\nFor example: /where Ocean Lab"
        )
        return

    campus_map = context.bot_data["campus_map"]
    response = get_location_info(query, campus_map)
    await update.message.reply_text(response)


async def handle_locker_hours(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle queries about locker hours"""
    text = update.message.text.lower()
    locker_data = context.bot_data["locker_hours"]

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


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle all non-command messages"""
    user_id = update.effective_user.id
    text = update.message.text.lower()
    campus_map = context.bot_data["campus_map"]

    # Check if asking for locker hours
    if "locker" in text and ("open" in text or "hours" in text):
        await handle_locker_hours(update, context)
        return

    # Step 2.5: fuzzy match against FAQ keywords
    question_keywords = list(FAQ_ANSWERS.keys())
    matched = get_close_matches(text.lower(), question_keywords, n=1, cutoff=0.6)

    if matched:
        answer = FAQ_ANSWERS[matched[0]]
        await update.message.reply_text(answer, parse_mode="Markdown")
        return

    # Step 3: fallback to AI QA system
    qa_chain = context.bot_data["qa_chain"]
    await update.message.reply_text("Thinking...")
    try:
        response = qa_chain.invoke(text)
        await update.message.reply_text(response['result'])
    except Exception as e:
        logger.error(f"Error processing: {e}")
        await update.message.reply_text("Sorry, I couldn't process your question.")


# set the bot menu button to show available commands
async def set_bot_commands(application):
    await application.bot.set_my_commands([
        BotCommand("start", "Start the bot"),
        BotCommand("help", "Get help using the bot"),
        BotCommand("where", "Find a place on campus")
    ])


def main() -> None:
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # Initialize QA chain
    application.bot_data["qa_chain"] = initialize_qa_chain()

    # Load data from Supabase and parse into usable formats
    raw_campus_map = load_campus_map()
    application.bot_data["campus_map"] = parse_campus_map_data(raw_campus_map)

    raw_locker_hours = load_locker_hours()
    application.bot_data["locker_hours"] = parse_locker_hours(raw_locker_hours)

    # Add command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("where", where_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    application.post_init = set_bot_commands

    application.run_polling()


if __name__ == "__main__":
    main()