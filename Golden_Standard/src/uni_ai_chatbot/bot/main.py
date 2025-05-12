import os
import logging
from typing import Optional
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler
from telegram import BotCommand
from dotenv import load_dotenv
from uni_ai_chatbot.bot.commands import start, help_command, where_command, find_command
from uni_ai_chatbot.bot.conversation import handle_message
from uni_ai_chatbot.bot.callbacks import handle_location_callback
from uni_ai_chatbot.services.qa_service_supabase import initialize_qa_chain, get_scoped_qa_chain
from uni_ai_chatbot.data.campus_map_data import load_campus_map
from uni_ai_chatbot.data.locker_hours_loader import load_locker_hours
from uni_ai_chatbot.services.locker_service import parse_locker_hours
from uni_ai_chatbot.tools.tools_architecture import tool_registry

load_dotenv()
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)
TELEGRAM_TOKEN: Optional[str] = os.environ.get("TELEGRAM_TOKEN")
MISTRAL_API_KEY: Optional[str] = os.environ.get("MISTRAL_API_KEY")
if not TELEGRAM_TOKEN:
    raise ValueError("TELEGRAM_TOKEN is not set in environment variables")
if not MISTRAL_API_KEY:
    raise ValueError("MISTRAL_API_KEY is not set in environment variables")


# set the bot menu button to show available commands
async def set_bot_commands(application: Application) -> None:
    """
    Set the bot's command menu

    Args:
        application: Telegram Application instance
    """
    await application.bot.set_my_commands([
        BotCommand("start", "Start the bot"),
        BotCommand("help", "Get help using the bot"),
        BotCommand("where", "Find a place on campus"),
        BotCommand("find", "Find places with specific features")
    ])


def main() -> None:
    """Main function to initialize and run the bot"""
    application: Application = Application.builder().token(TELEGRAM_TOKEN).build()

    # Initialize QA chain components with Supabase vector store
    vector_store, llm, general_qa_chain, location_qa_chain, locker_qa_chain, faq_qa_chain = initialize_qa_chain()

    # Store LLM instance for tool classifier
    application.bot_data["llm"] = llm

    # Store all QA components in bot_data
    application.bot_data["general_qa_chain"] = general_qa_chain
    application.bot_data["location_qa_chain"] = location_qa_chain
    application.bot_data["locker_qa_chain"] = locker_qa_chain
    application.bot_data["faq_qa_chain"] = faq_qa_chain
    application.bot_data["qa_chain"] = general_qa_chain  # Backward compatibility

    # Load data from Supabase
    application.bot_data["campus_map"] = load_campus_map()
    application.bot_data["locker_hours"] = parse_locker_hours(load_locker_hours())

    # Validate that all necessary tools are registered
    logger.info(f"Registered tools: {[tool.name for tool in tool_registry.get_all_tools()]}")

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