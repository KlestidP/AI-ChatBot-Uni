import os
import logging
import re
from pathlib import Path
from telegram import Update, BotCommand, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from langchain.chains import RetrievalQA
from langchain_core.documents import Document
from langchain_community.vectorstores import FAISS
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_mistralai import MistralAIEmbeddings
from langchain_mistralai import ChatMistralAI
from uni_ai_chatbot.resources import load_faq_answers
from dotenv import load_dotenv
from uni_ai_chatbot.locker_hours_loader import load_locker_hours
from difflib import get_close_matches
from uni_ai_chatbot.campus_map_data import (
    load_campus_map,
    find_locations_by_tag,
    find_location_by_name_or_alias,
    find_locations_by_feature,
    extract_feature_keywords
)

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
        doc_content = f"Location: {location['name']}\n"

        if location.get('tags'):
            doc_content += f"Features: {location['tags']}\n"

        if location.get('aliases'):
            doc_content += f"Also known as: {location['aliases']}\n"

        doc_content += f"Address: {location.get('address', 'Unknown')}"
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
        "• 🔍 `/find [feature]` — Find places with specific features (e.g., printer, food, study).\n\n"
        "• 🧺 *Locker hours* — Ask for locker access times in any college.\n\n"
        "• 🍽 *Servery hours* — Ask for meal times in your college or the coffee bar.\n\n"
        "• ❓ *University FAQs* — Ask about documents, laundry, residence permits, etc.\n\n"
        "• 🗓 *College events* — Get updates on announcements and upcoming activities.\n\n"
        "💬 Just type your question — I'll understand natural language too!\n\n"
        "🔒 Bot is limited to university-related queries only."
    )


async def where_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Respond to /where command with location info and venue"""
    query = ' '.join(context.args)
    if not query:
        await update.message.reply_text(
            "Please provide a location name.\nFor example: /where Ocean Lab"
        )
        return

    campus_map = context.bot_data["campus_map"]
    location = find_location_by_name_or_alias(campus_map, query)

    if location:
        # Send a text response with information about the location
        info_text = f"📍 *{location['name']}*\n"

        if location.get('tags'):
            features = location['tags'].split(',')
            features_text = ", ".join([f.strip() for f in features])
            info_text += f"Features: {features_text}\n"

        if location.get('aliases'):
            aliases = location['aliases'].split(',')
            aliases_text = ", ".join([a.strip() for a in aliases])
            info_text += f"Also known as: {aliases_text}\n"

        await update.message.reply_text(info_text, parse_mode="Markdown")

        # Then send the venue
        try:
            await update.message.reply_venue(
                latitude=float(location['latitude']),
                longitude=float(location['longitude']),
                title=location['name'],
                address=location.get('address', 'Constructor University, Bremen')
            )
        except Exception as e:
            logger.error(f"Error sending venue: {e}")
            await update.message.reply_text("Sorry, I couldn't display the location on map.")
    else:
        await update.message.reply_text(
            "Sorry, I couldn't find that location. Try asking in a different way or try the /find command."
        )


async def find_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Find locations with specific features"""
    query = ' '.join(context.args)
    if not query:
        await update.message.reply_text(
            "Please specify what you're looking for.\nFor example: /find printer or /find food"
        )
        return

    campus_map = context.bot_data["campus_map"]
    keywords = extract_feature_keywords(query)

    # If no keywords were extracted, use the whole query as a single keyword
    if not keywords:
        keywords = [query.lower()]

    locations = find_locations_by_feature(campus_map, keywords)

    if locations:
        if len(locations) == 1:
            # Only one location found, show it directly
            location = locations[0]
            await show_location_details(update, location)
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
    else:
        # No locations found in the database, fall back to AI
        await update.message.reply_text(
            "I don't have specific information about places with those features. Let me think about it..."
        )
        # Fall back to AI
        await handle_location_with_ai(update, context, query)


async def handle_location_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle callback queries from inline keyboards"""
    query = update.callback_query
    await query.answer()

    if query.data.startswith("location:"):
        location_id = query.data.split(':')[1]
        campus_map = context.bot_data["campus_map"]

        # Find the location by ID
        location = next((loc for loc in campus_map if loc['id'] == location_id), None)

        if location:
            await show_location_details(update, location, is_callback=True)
        else:
            await query.edit_message_text("Sorry, I couldn't find that location anymore.")


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
        await update.message.reply_text(response['result'])
    except Exception as e:
        logger.error(f"Error processing: {e}")
        await update.message.reply_text("Sorry, I couldn't process your question.")


# set the bot menu button to show available commands
async def set_bot_commands(application):
    await application.bot.set_my_commands([
        BotCommand("start", "Start the bot"),
        BotCommand("help", "Get help using the bot"),
        BotCommand("where", "Find a place on campus"),
        BotCommand("find", "Find places with specific features")
    ])


def main() -> None:
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # Initialize QA chain
    application.bot_data["qa_chain"] = initialize_qa_chain()

    # Load data from Supabase
    application.bot_data["campus_map"] = load_campus_map()
    application.bot_data["locker_hours"] = parse_locker_hours(load_locker_hours())

    # Add command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("where", where_command))
    application.add_handler(CommandHandler("find", find_command))
    application.add_handler(CallbackQueryHandler(handle_location_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    application.post_init = set_bot_commands

    application.run_polling()


if __name__ == "__main__":
    main()