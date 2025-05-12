import logging
from difflib import get_close_matches
from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


async def handle_faq_query(update: Update, context: ContextTypes.DEFAULT_TYPE, query: str):
    """
    Handle FAQ queries using proper similarity matching.
    """
    from uni_ai_chatbot.data.resources import load_faq_answers

    try:
        # Load FAQ answers
        faq_answers = load_faq_answers()

        # 1. Direct match attempt
        if query.lower() in faq_answers:
            await update.message.reply_text(faq_answers[query.lower()], parse_mode="Markdown")
            return

        # 2. Normalize query
        normalized_query = query.lower().strip()

        # 3. Fuzzy matching
        question_keywords = list(faq_answers.keys())
        matched = get_close_matches(normalized_query, question_keywords, n=1, cutoff=0.6)

        # 4. Word-by-word matching for longer queries
        if not matched:
            for word in query.split():
                if len(word) > 3:  # Skip very short words
                    word_matches = get_close_matches(word.lower(), question_keywords, n=1, cutoff=0.7)
                    if word_matches:
                        matched = word_matches
                        break

        # Special keyword matching for important topics
        if not matched:
            # Map of important categories and their related keywords
            important_categories = {
                'immatrikulationsbescheinigung': ['immatrikulation', 'enrollment', 'certificate', 'student',
                                                  'confirmation'],
                'laundry': ['laundry', 'washing', 'dryer', 'laundromat', 'wash', 'clothes'],
                'residence permit': ['residence', 'permit', 'visa', 'immigration', 'foreigner', 'ausländerbehörde',
                                     'auslanderbehorde'],
                'address change': ['address', 'change', 'move', 'moving', 'residence', 'registration', 'anmeldung'],
                'emergency contacts': ['emergency', 'help', 'urgent', 'crisis', 'accident', 'police', 'ambulance'],
                'driving license': ['driving', 'driver', 'license', 'licence', 'car', 'conversion', 'führerschein',
                                    'fuhrerschein', 'driving test', 'driving exam', 'driver licence', 'driver licence',
                                    'driving licence'],
                'semester ticket': ['semester', 'ticket', 'transportation', 'train', 'bus', 'travel'],
                'postal code': ['postal', 'code', 'zip', 'plz', 'mail', 'post'],
            }

            for category, keywords in important_categories.items():
                if any(k in normalized_query for k in keywords):
                    # Find any FAQ that mentions these keywords
                    matched = [category]
                    break

        # If we found a match, respond with the answer
        if matched:
            answer = faq_answers[matched[0]]
            await update.message.reply_text(answer, parse_mode="Markdown")
            return

        # 5. If no match found, use the FAQ QA chain for semantic matching
        faq_qa_chain = context.bot_data.get("faq_qa_chain") or context.bot_data.get("qa_chain")

        if faq_qa_chain:
            response = faq_qa_chain.invoke(query)
            await update.message.reply_text(response['result'], parse_mode="Markdown")
        else:
            await update.message.reply_text("I'm sorry, I don't have information about that in my FAQ database.")

    except Exception as e:
        logger.error(f"Error processing FAQ query: {e}")
        await update.message.reply_text("I wasn't able to find an answer for that. Could you try rephrasing your question?")