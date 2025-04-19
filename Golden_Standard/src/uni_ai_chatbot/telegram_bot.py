import os
import logging
from pathlib import Path
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from langchain.chains import RetrievalQA
from langchain_community.document_loaders import TextLoader
from langchain_community.vectorstores import FAISS
from langchain_text_splitters import CharacterTextSplitter
from langchain_mistralai import MistralAIEmbeddings
from langchain_mistralai import ChatMistralAI
from src.uni_ai_chatbot.resources import get_resource
from dotenv import load_dotenv

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
    file_path = get_resource(relative_path=Path("data.txt"))
    loader = TextLoader(file_path)
    documents = loader.load()
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


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle user messages and respond with answers from the QA system."""
    question = update.message.text
    qa_chain = context.bot_data["qa_chain"]
    await update.message.reply_text("Thinking...")
    try:
        response = qa_chain.invoke(question)
        answer = response['result']
        await update.message.reply_text(answer)
    except Exception as e:
        logger.error(f"Error processing question: {e}")
        await update.message.reply_text(
            "Sorry, I couldn't process your question. Please try again later."
        )


def main() -> None:
    """Start the bot."""
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    application.bot_data["qa_chain"] = initialize_qa_chain()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.run_polling()


if __name__ == "__main__":
    main()
