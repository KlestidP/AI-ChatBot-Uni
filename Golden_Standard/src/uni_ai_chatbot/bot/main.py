import logging
from typing import Optional
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler
from telegram import BotCommand

from uni_ai_chatbot.configurations.config import TELEGRAM_TOKEN, MISTRAL_API_KEY, BOT_COMMANDS
from uni_ai_chatbot.bot.commands import start, help_command, where_command, find_command, handbook_command, \
    change_provider_command, list_providers_command
from uni_ai_chatbot.bot.conversation import handle_message
from uni_ai_chatbot.bot.callbacks import handle_location_callback
from uni_ai_chatbot.data.servery_hours_loader import load_servery_hours
from uni_ai_chatbot.services.qa_service_supabase import initialize_qa_chain
from uni_ai_chatbot.data.campus_map_data import load_campus_map
from uni_ai_chatbot.data.locker_hours_loader import load_locker_hours
from uni_ai_chatbot.services.locker_service import parse_locker_hours
from uni_ai_chatbot.services.servery_service import parse_servery_hours
from uni_ai_chatbot.tools.tools_architecture import tool_registry

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

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
        BotCommand(command, description) for command, description in BOT_COMMANDS
    ])


def main() -> None:
    """Main function to initialize and run the bot"""
    # Check and initialize database if needed
    try:
        from uni_ai_chatbot.scripts.init_setup import check_and_initialize_database
        check_and_initialize_database()
    except Exception as e:
        logger.warning(f"Database initialization check failed: {e}. Continuing anyway...")

    """Main function to initialize and run the bot"""
    application: Application = Application.builder().token(TELEGRAM_TOKEN).build()

    # Initialize QA chain components with Supabase vector store
    vector_store, llm, general_qa_chain, location_qa_chain, locker_qa_chain, faq_qa_chain, handbook_qa_chain = initialize_qa_chain()

    # Store LLM instance for tool classifier
    application.bot_data["llm"] = llm

    # Store all QA components in bot_data
    application.bot_data["general_qa_chain"] = general_qa_chain
    application.bot_data["location_qa_chain"] = location_qa_chain
    application.bot_data["locker_qa_chain"] = locker_qa_chain
    application.bot_data["faq_qa_chain"] = faq_qa_chain
    application.bot_data["handbook_qa_chain"] = handbook_qa_chain  # Backward compatibility
    application.bot_data["servery_hours"] = parse_servery_hours(load_servery_hours())
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
    application.add_handler(CommandHandler("handbook", handbook_command))
    application.add_handler(CommandHandler("provider", change_provider_command))
    application.add_handler(CommandHandler("providers", list_providers_command))
    application.add_handler(CallbackQueryHandler(handle_location_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    application.post_init = set_bot_commands

    application.run_polling()


if __name__ == "__main__":
    main()