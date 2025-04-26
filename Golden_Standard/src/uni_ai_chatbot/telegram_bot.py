import os
import json
import logging
from pathlib import Path
from telegram import Update, BotCommand
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from langchain.chains import RetrievalQA
from langchain_community.document_loaders import TextLoader
from langchain_community.vectorstores import FAISS
from langchain_text_splitters import CharacterTextSplitter
from langchain_mistralai import MistralAIEmbeddings
from langchain_mistralai import ChatMistralAI
from uni_ai_chatbot.resources import get_resource
from dotenv import load_dotenv
from uni_ai_chatbot.campus_map_data import campus_map
from uni_ai_chatbot.locker_hours_loader import load_locker_hours
from uni_ai_chatbot.servery_hours_loader import load_servery_hours
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

faq_file_path = Path(__file__).parent / "faq_responses.json"
with open(faq_file_path, encoding="utf-8") as f:
    FAQ_ANSWERS = json.load(f)


def initialize_qa_chain():
    file_path_1 = get_resource(relative_path=Path("data.txt"))
    file_path_2 = get_resource(relative_path=Path("map_data.txt"))  # added map data

    loader = TextLoader(file_path_1)
    loader2 = TextLoader(file_path_2)

    documents = loader.load() + loader2.load()  # combine both
    text_splitter = CharacterTextSplitter(chunk_size=200, chunk_overlap=20)
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


def resolve_location_name(query):
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

# determine location info using fuzzy name matching
def get_location_info(query):
    # Build search index using names and aliases
    names = []
    lookup = {}

    for place in campus_map:
        main_name = place["name"]
        names.append(main_name)
        lookup[main_name.lower()] = place

        for alias in place.get("aliases", []):
            names.append(alias)
            lookup[alias.lower()] = place

    # Match user query against names/aliases
    matches = get_close_matches(query.lower(), names, n=1, cutoff=0.6)
    if matches:
        match = matches[0].lower()
        place = lookup[match]
        return f"{place['name']} is in the {place['direction'].lower()} part of campus and is a {place['category'].lower()} facility."

    return "Sorry, I couldn't find that place on the map."


# provide basic directions from Main Gate to the target location
def get_directional_instructions(query):
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
        return f"From the Main Gate, head toward the {place['direction'].lower()} to reach {place['name']}."

    return "Sorry, I couldn't find that place on the map."


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    await update.message.reply_text(
        "Hi! I'm your University Info Bot. Ask me any question about college schedules, fees, or events!"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /help is issued."""
    await update.message.reply_text(
        "Just ask me any question about college schedules, fees, or events. For example:\n"
        "- When are the college fees due?\n"
        "- Is the library open next month?\n"
        "- When does the semester start?"
    )


# respond to /where command with location info
async def where_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = ' '.join(context.args)
    if not query:
        await update.message.reply_text(
            "Please provide a location name.\nFor example: /where Ocean Lab"
        )
        return
    response = get_location_info(query)
    await update.message.reply_text(response)


# handle all text messages (including "how do I get to" questions)
# store temp state for direction questions
user_direction_queries = {}

async def handle_locker_hours(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower()
    locker_data = context.bot_data["locker_hours"]

    colleges = {
        "Krupp College": ["krupp", "krupp college"],
        "College III": ["college iii", "college 3", "college iii college"],
        "Nordmetall College": ["nordmetall", "nordmetall college"],
        "Mercator College": ["mercator", "mercator college"]
    }

    matched_college = None
    for college, variations in colleges.items():
        for variation in variations:
            if variation in text:
                matched_college = college
                break
        if matched_college:
            break

    if not matched_college:
        await update.message.reply_text("❓ Please mention the college (Krupp, College III, Nordmetall, or Mercator).")
        return

    basement = None
    for b in ["a", "b", "c", "d", "f"]:
        if f"basement {b}" in text or f" {b}" in text:
            basement = b.upper()

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

async def handle_servery_hours(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower()
    data  = context.bot_data["servery_hours"]

    # fuzzy-ish college matching
    colleges = {
        "Alfried Krupp College": ["krupp", "alfried krupp"],
        "College Nordmetall & College 3": ["nordmetall", "college 3", "college iii"],
        "Mercator College": ["mercator"],
        "Coffee Bar": ["coffee bar", "bar"]
    }
    college = next((c for c, vs in colleges.items() if any(v in text for v in vs)), None)
    if not college:
        await update.message.reply_text("❓ Which servery? (Krupp, Nordmetall/College 3, Mercator or Coffee Bar)")
        return

    # optional keywords
    meal  = next((m for m in ["breakfast", "lunch", "dinner", "servery"] if m in text), None)
    day   = next((d for d in ["monday", "friday", "saturday", "sunday", "holiday"] if d in text), None)

    msg = f"🍽 **Servery Hours – {college}**\n"
    periods = data[college]

    for period, meals in periods.items():
        if day and day not in period:
            continue
        msg += f"\n*{period.title()}*\n"
        for m, hrs in meals.items():
            if meal and meal != m:
                continue
            msg += f"• {m.title()}: {hrs}\n"

    await update.message.reply_text(msg, parse_mode="Markdown")




async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    text = update.message.text.lower()

    # Step 1: if we're waiting for the user's location after asking
    if user_id in user_direction_queries:
        # inside handle_message() where user gives origin:
        origin = resolve_location_name(text)
        target = resolve_location_name(user_direction_queries.pop(user_id))

        if not origin or not target:
            await update.message.reply_text(
                "Sorry, I couldn't understand the location names. Try using different words.")
            return

        ai_input = f"How can I get from {origin} to {target}?"
        await update.message.reply_text("Thinking...")
        qa_chain = context.bot_data["qa_chain"]
        response = qa_chain.invoke(ai_input)
        await update.message.reply_text(response['result'])
        return

    # Step 2: if it's a direction question
    if "how do i get to" in text or "how can i get to" in text or "how to reach" in text:
        location_query = text.replace("how do i get to", "").replace("how can i get to", "").replace("how to reach",
                                                                                                     "").strip()
        if location_query:
            user_direction_queries[user_id] = location_query
            await update.message.reply_text("Where are you standing right now?")
        else:
            await update.message.reply_text("Please specify where you want to go.")
        return

    # Check if asking for locker hours
    if "locker" in text and ("open" in text or "hours" in text):
        await handle_locker_hours(update, context)
        return

    if any(k in text for k in ["servery", "mensa", "opening hours"]) and "locker" not in text:
        await handle_servery_hours(update, context)
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
    application.bot_data["qa_chain"] = initialize_qa_chain()
    application.bot_data["locker_hours"] = load_locker_hours()
    application.bot_data["servery_hours"] = load_servery_hours()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CommandHandler("where", where_command))

    application.post_init = set_bot_commands

    application.run_polling()


if __name__ == "__main__":
    main()
