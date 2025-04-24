import os
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
from difflib import get_close_matcheso,

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
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CommandHandler("where", where_command))

    application.post_init = set_bot_commands

    application.run_polling()


if __name__ == "__main__":
    main()
