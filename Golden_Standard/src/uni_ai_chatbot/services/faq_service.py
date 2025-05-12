import logging
from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


async def handle_faq_query(update: Update, context: ContextTypes.DEFAULT_TYPE, query: str):
    """
    Handle FAQ queries using AI-driven matching instead of hard-coded rules.
    Uses semantic search and LLM to understand and match FAQs.
    """
    try:
        # Get the FAQ QA chain
        faq_qa_chain = context.bot_data.get("faq_qa_chain") or context.bot_data.get("qa_chain")

        if not faq_qa_chain:
            await update.message.reply_text("I'm sorry, I'm not able to answer FAQs at the moment.")
            return

        # First try using the LLM to classify the query
        llm = context.bot_data.get("llm")
        if llm:
            # Get all FAQ questions for better matching
            from uni_ai_chatbot.data.resources import load_faq_answers
            faq_answers = load_faq_answers()

            # Create a classification prompt
            faq_questions = list(faq_answers.keys())
            classification_prompt = f"""You are a university FAQ bot. Below are the FAQ questions you can answer:

{', '.join(faq_questions)}

The user asked: "{query}"

Which of the above FAQ questions is this query most related to? If it's clearly related to one of them, respond with just that FAQ question. If it's not clearly related to any, respond with "none".
"""

            try:
                # Ask the LLM to classify the query
                response = llm.invoke(classification_prompt)
                matched_faq = response.content.strip()

                # If the LLM found a match and it exists in our FAQs
                if matched_faq.lower() != "none" and matched_faq in faq_answers:
                    await update.message.reply_text(faq_answers[matched_faq], parse_mode="Markdown")
                    return
            except Exception as e:
                logger.warning(f"LLM classification failed: {e}, falling back to retrieval")

        # If no direct match or classification failed, use retrieval-based QA
        response = faq_qa_chain.invoke(query)

        await update.message.reply_text(response['result'], parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Error processing FAQ query: {e}")
        await update.message.reply_text(
            "I wasn't able to find an answer for that. Could you try rephrasing your question?")