import logging
import re
from typing import List, Dict, Any, Optional, Union, Tuple
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from difflib import SequenceMatcher

from uni_ai_chatbot.data.handbook_loader import load_handbooks

logger = logging.getLogger(__name__)

# Define common abbreviations for majors
MAJOR_ABBREVIATIONS = {
    # Science & Math
    "bccb": "Biochemistry and Cell Biology",
    "bcb": "Biochemistry and Cell Biology",
    "bio": "Biochemistry and Cell Biology",
    "biochem": "Biochemistry and Cell Biology",

    "cbt": "Chemistry and Biotechnology",
    "chem": "Chemistry and Biotechnology",
    "biotech": "Chemistry and Biotechnology",

    "essmer": "Earth Sciences and Sustainable Management of Environmental Resources",
    "earth": "Earth Sciences and Sustainable Management of Environmental Resources",
    "ess": "Earth Sciences and Sustainable Management of Environmental Resources",
    "environmental": "Earth Sciences and Sustainable Management of Environmental Resources",

    "mmda": "Mathematics, Modeling and Data Analytics",
    "math": "Mathematics, Modeling and Data Analytics",
    "modeling": "Mathematics, Modeling and Data Analytics",

    "mccb": "Medicinal Chemistry and Chemical Biology",
    "medicinal": "Medicinal Chemistry and Chemical Biology",
    "chemical biology": "Medicinal Chemistry and Chemical Biology",

    "phds": "Physics and Data Science",
    "pds": "Physics and Data Science",
    "physics": "Physics and Data Science",
    "data science": "Physics and Data Science",
    "physics data": "Physics and Data Science",

    # Computer Science & Engineering
    "acs": "Applied Computer Science",
    "applied cs": "Applied Computer Science",

    "cs": "Computer Science",
    "compsci": "Computer Science",

    "ece": "Electrical and Computer Engineering",
    "ee": "Electrical and Computer Engineering",
    "electrical": "Electrical and Computer Engineering",

    "ris": "Robotics and Intelligent Systems",
    "robotics": "Robotics and Intelligent Systems",

    "sdt": "Software, Data and Technology",
    "software": "Software, Data and Technology",

    # Business & Management
    "gem": "Global Economics and Management",
    "eco": "Global Economics and Management",
    "econ": "Global Economics and Management",
    "economics": "Global Economics and Management",

    "iba": "International Business Administration",
    "business": "International Business Administration",

    "iem": "Industrial Engineering and Management",
    "ie": "Industrial Engineering and Management",
    "industrial": "Industrial Engineering and Management",

    # Social Sciences & Humanities
    "irph": "International Relations: Politics and History",
    "ir": "International Relations: Politics and History",
    "politics": "International Relations: Politics and History",
    "international relations": "International Relations: Politics and History",

    "iscp": "Integrated Social and Cognitive Psychology",
    "psych": "Integrated Social and Cognitive Psychology",
    "psychology": "Integrated Social and Cognitive Psychology",

    "mdda": "Management, Decisions and Data Analytics",
    "management": "Management, Decisions and Data Analytics",
    "decisions": "Management, Decisions and Data Analytics"
}


def calculate_similarity(str1: str, str2: str) -> float:
    """
    Calculate the similarity ratio between two strings

    Args:
        str1: First string
        str2: Second string

    Returns:
        Similarity ratio between 0 and 1
    """
    return SequenceMatcher(None, str1.lower(), str2.lower()).ratio()


def extract_major_from_query(query: str) -> Optional[str]:
    """
    Extract major name from query with improved command handling

    Args:
        query: User query

    Returns:
        Extracted major name or None
    """
    logger.info(f"Extracting major from query: '{query}'")

    if not query:
        return None

    # Handle /handbook command format
    if query.lower().startswith("/handbook"):
        # Extract everything after /handbook
        parts = query.split(" ", 1)
        if len(parts) > 1:
            return parts[1].strip()
        else:
            return None  # Just "/handbook" without arguments

    # Common phrases that might indicate a handbook request
    prefixes = [
        "handbook for",
        "handbook of",
        "show me the handbook for",
        "get me the handbook for",
        "can i see the handbook for",
        "find the handbook for"
    ]

    cleaned_query = query.lower()
    for prefix in prefixes:
        if prefix in cleaned_query:
            major = cleaned_query.split(prefix)[1].strip()
            return major

    # Try to find major using regex
    major_match = re.search(r'(?:major|program|degree)(?:\s+in)?\s+([a-z\s]+?)(?:$|\.|\?)', cleaned_query)
    if major_match:
        return major_match.group(1).strip()

    # If query is short and might be a major/abbreviation, return it directly
    if len(cleaned_query.split()) <= 10:  # Increased from 3 to 4 to catch "physics and data science"
        return cleaned_query

    return None


def find_handbook_by_major(handbooks: List[Dict[str, Any]], major: str, similarity_threshold: float = 0.6) -> Optional[
    Dict[str, Any]]:
    """
    Find a handbook by major name with similarity matching

    Args:
        handbooks: List of handbook dictionaries
        major: Major name to search for
        similarity_threshold: Minimum similarity score (0-1) to consider a match

    Returns:
        Matched handbook or None
    """
    if not major:
        return None

    major_clean = major.lower().strip()

    # Check abbreviations first
    if major_clean in MAJOR_ABBREVIATIONS:
        target_major = MAJOR_ABBREVIATIONS[major_clean]
        logger.info(f"Matched abbreviation '{major_clean}' to '{target_major}'")
        for handbook in handbooks:
            if handbook['major'].lower() == target_major.lower():
                return handbook

    # Exact match
    for handbook in handbooks:
        if handbook['major'].lower() == major_clean:
            return handbook

    # Partial match
    for handbook in handbooks:
        if major_clean in handbook['major'].lower() or handbook['major'].lower() in major_clean:
            return handbook

    # Similarity-based matching
    best_match = None
    best_score = 0

    for handbook in handbooks:
        # Calculate similarity with full major name
        score = calculate_similarity(major_clean, handbook['major'].lower())

        # Check if this is the best match so far and meets the threshold
        if score > best_score and score >= similarity_threshold:
            best_score = score
            best_match = handbook

    if best_match:
        logger.info(f"Found similarity match for '{major_clean}': '{best_match['major']}' with score {best_score:.2f}")

    return best_match


async def find_handbook_with_ai(llm, handbooks: List[Dict[str, Any]], query: str) -> Optional[Dict[str, Any]]:
    """
    Use AI to match a query to the appropriate handbook
    """
    try:
        available_majors = [handbook["major"] for handbook in handbooks]
        major_abbrevs = [f"{abbr} ({full})" for abbr, full in MAJOR_ABBREVIATIONS.items()]
        abbrev_info = ", ".join(major_abbrevs[:10]) + "..." if len(major_abbrevs) > 10 else ", ".join(major_abbrevs)

        prompt = f"""You are a university handbook assistant. The user is looking for a handbook for: "{query}"

The available program handbooks are: {", ".join(available_majors)}

Common abbreviations include: {abbrev_info}

Which of these programs best matches the user's query? Consider common abbreviations and alternative phrasings.
Respond with just the exact name of the matching program from the list of available programs. 
If there's no good match, respond with "No match found".
"""

        response = llm.invoke(prompt)
        matched_major = response.content.strip()
        logger.info(f"AI suggestion for '{query}': '{matched_major}'")

        # Check if the AI found a match
        if matched_major.lower() != "no match found":
            # Try to find an exact match first
            for handbook in handbooks:
                if handbook["major"].lower() == matched_major.lower():
                    return handbook

            # If no exact match, try to find a handbook whose name contains the AI's suggestion
            for handbook in handbooks:
                if matched_major.lower() in handbook["major"].lower():
                    return handbook

        # No match found
        return None

    except Exception as e:
        logger.warning(f"Error using AI for handbook matching: {e}")
        return None  # Return None to fall back to showing all handbooks


async def handle_handbook_with_ai(update: Update, context: ContextTypes.DEFAULT_TYPE, major: str) -> None:
    """
    Use AI to provide information about a major when handbook isn't found
    """
    general_qa_chain = context.bot_data.get("general_qa_chain")
    if not general_qa_chain:
        await update.message.reply_text(
            f"I couldn't find a handbook specifically for {major}. Please check with the academic office for information."
        )
        return

    query = f"What information do you have about the {major} program or major at the university?"

    try:
        response = general_qa_chain.invoke(query)
        result = response['result']

        await update.message.reply_text(
            f"I couldn't find a specific handbook for *{major}*, but here's what I know:\n\n{result}",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"AI handling error: {e}")
        await update.message.reply_text(
            f"I couldn't find a handbook for {major}. Please check with the academic office for information."
        )


async def handle_handbook_content_question(update: Update, context: ContextTypes.DEFAULT_TYPE, query: str) -> None:
    """
    Handle questions about handbook content using the handbook QA chain with improved error handling
    """
    try:
        # Show typing indicator while processing
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

        # First, try to identify which handbook(s) the query might be referring to
        llm = context.bot_data.get("llm")
        handbooks = context.bot_data.get("handbooks", [])
        handbook_qa_chain = context.bot_data.get("handbook_qa_chain")

        if not handbook_qa_chain:
            # Fall back to general QA if handbook chain not available
            logger.warning("Handbook QA chain not found, falling back to general QA")
            handbook_qa_chain = context.bot_data.get("general_qa_chain")

        if not handbook_qa_chain:
            await update.message.reply_text(
                "I'm sorry, I don't have information about handbook content right now.")
            return

        # Log the query for debugging
        logger.info(f"Processing handbook content question: {query}")

        # Create a handbook-specific prompt with program context
        program_context = ""
        if llm and handbooks:
            # Try to identify which program the query is about
            for abbr, full_name in MAJOR_ABBREVIATIONS.items():
                if abbr in query.lower() or full_name.lower() in query.lower():
                    program_context = f" (specifically for {full_name})"
                    logger.info(f"Identified program context: {full_name}")
                    break

        # Create an enhanced query that includes context
        enhanced_query = f"{query}{program_context}"

        # Log enhanced query
        logger.info(f"Enhanced query: {enhanced_query}")

        # Add detailed logging and improved error handling here
        try:
            # Invoke the chain
            logger.info(f"Invoking handbook QA chain...")
            response = handbook_qa_chain.invoke(enhanced_query)

            logger.info("Successfully retrieved response from handbook QA chain")

            # Check if we got any response
            if not response or not response.get('result'):
                logger.warning("Empty response from handbook QA chain")
                await update.message.reply_text(
                    "I couldn't find specific information about that in the handbooks. "
                    "Try asking about a specific program or downloading the handbook directly with /handbook [program name]."
                )
                return

            result = response.get('result', '')

            # Log source documents for debugging
            if 'source_documents' in response and response['source_documents']:
                logger.info(f"Found {len(response['source_documents'])} source documents")
                for i, doc in enumerate(response['source_documents'][:3]):  # Log first 3
                    logger.debug(f"Source {i}: {doc.metadata}")
            else:
                logger.warning("No source documents found in response")

            # Add source information if available
            source_info = ""
            if 'source_documents' in response and response['source_documents']:
                sources = set()
                for doc in response['source_documents']:
                    if 'major' in doc.metadata:
                        sources.add(doc.metadata['major'])

                if sources:
                    source_info = "\n\n*Sources:* " + ", ".join(sources) + " handbook(s)"
                    logger.info(f"Added source info from: {sources}")

            # Check if the response seems valid
            if len(result.strip()) < 50 or "I don't know" in result or "I cannot find" in result:
                logger.warning(f"Response seems insufficient: {result[:100]}")
                # Try to provide helpful guidance
                await update.message.reply_text(
                    "I couldn't find detailed information about that specific topic in the handbooks. "
                    "You might want to:\n\n"
                    "• Try rephrasing your question with more specific terms\n"
                    "• Download the relevant handbook with `/handbook [program name]`\n"
                    "• Contact your academic advisor for detailed information"
                )
                return

            # Send the final response with sources
            await update.message.reply_text(result + source_info, parse_mode="Markdown")
            logger.info("Successfully sent handbook response")

        except ValueError as ve:
            logger.error(f"Vector error in handbook retrieval: {ve}", exc_info=True)

            # Provide a helpful fallback response
            await update.message.reply_text(
                "I'm having trouble searching the handbook content right now. "
                "Please try:\n\n"
                "• Downloading the handbook directly: `/handbook [program name]`\n"
                "• Asking a more specific question about the program\n"
                "• Checking the university website for the latest information"
            )

        except Exception as e:
            logger.error(f"Unexpected error in handbook processing: {e}", exc_info=True)

            # Generic error response
            await update.message.reply_text(
                "I encountered an error while searching the handbooks. "
                "Please try again with a different question or download the handbook directly with `/handbook [program name]`."
            )

    except Exception as e:
        logger.error(f"Error in overall handbook content question handling: {e}", exc_info=True)
        await update.message.reply_text(
            "I couldn't process your question about handbook content. Please try again later.")

async def handle_handbook_query(update: Update, context: ContextTypes.DEFAULT_TYPE, query: str = None) -> None:
    """
    Handle handbook-related queries with improved AI matching and content question detection
    Can be called from both initial messages and callback queries
    """
    # For callback queries, message will be None, so we need to handle this case
    is_callback = update.callback_query is not None

    # When called from a callback, there's no message text to process
    # We're just showing the handbook list with a different page
    if is_callback:
        text = ""  # No text to parse
        message_obj = update.callback_query.message  # Use the message that contains the keyboard
    else:
        text = query or update.message.text
        message_obj = update.message

        # Check if this is a content question rather than a request for a specific handbook
        # Use the improved content question detection function
        if is_content_question(text) and not text.lower().startswith("/handbook"):
            await handle_handbook_content_question(update, context, text)
            return

    try:
        # Check if we have cached handbooks
        if 'handbooks' not in context.bot_data:
            await message_obj.reply_text("Fetching handbook information...")
            context.bot_data['handbooks'] = load_handbooks()

        handbooks = context.bot_data['handbooks']

        # Only try to match query if this is not a callback (pagination request)
        if not is_callback:
            # Extract potential major from query
            potential_major = extract_major_from_query(text)
            logger.info(f"Extracted potential major: '{potential_major}' from query: '{text}'")

            # Only try to match if we have some input after "/handbook"
            if potential_major:
                # First try the existing match function with similarity
                matching_handbook = find_handbook_by_major(handbooks, potential_major)

                # If no match, try AI matching
                if not matching_handbook and context.bot_data.get("llm"):
                    llm = context.bot_data.get("llm")
                    matching_handbook = await find_handbook_with_ai(llm, handbooks, potential_major)
                    if matching_handbook:
                        logger.info(f"AI matching result for '{potential_major}': {matching_handbook['major']}")
                    else:
                        logger.info(f"AI matching result for '{potential_major}': None")

                if matching_handbook and matching_handbook.get('url'):
                    await message_obj.reply_text(
                        f"Here's the handbook for *{matching_handbook['major']}*:",
                        parse_mode="Markdown"
                    )
                    await message_obj.reply_document(
                        document=matching_handbook['url'],
                        filename=matching_handbook['file_name']
                    )
                    return  # Exit early - we found a match
                else:
                    # No match found through any method, but we have potential_major
                    await handle_handbook_with_ai(update, context, potential_major)
                    return  # Exit early - handled with AI

        # If we get here, we couldn't find a match or this is a pagination request
        # Show the list of handbooks with pagination
        PAGE_SIZE = 10  # Number of handbooks per page

        # Get current page from user data or default to 0
        current_page = context.user_data.get('handbook_page', 0)
        total_pages = (len(handbooks) + PAGE_SIZE - 1) // PAGE_SIZE  # Ceiling division

        # Calculate start and end indices for current page
        start_idx = current_page * PAGE_SIZE
        end_idx = min(start_idx + PAGE_SIZE, len(handbooks))

        # Create keyboard with handbooks for current page
        keyboard = []
        for idx, handbook in enumerate(handbooks[start_idx:end_idx], start=start_idx):
            keyboard.append([
                InlineKeyboardButton(
                    text=handbook['major'],
                    callback_data=f"hb:{idx}"
                )
            ])

        # Add navigation buttons if needed
        nav_buttons = []
        if current_page > 0:
            nav_buttons.append(
                InlineKeyboardButton("◀️ Previous", callback_data="hb_page:prev")
            )
        if current_page < total_pages - 1:
            nav_buttons.append(
                InlineKeyboardButton("Next ▶️", callback_data="hb_page:next")
            )
        if nav_buttons:
            keyboard.append(nav_buttons)

        reply_markup = InlineKeyboardMarkup(keyboard)
        page_info = f" (Page {current_page + 1}/{total_pages})" if total_pages > 1 else ""

        # Handle displaying results differently for callbacks vs. initial messages
        if is_callback:
            # For callbacks, edit the existing message
            await update.callback_query.edit_message_text(
                f"Which major's handbook would you like to see?{page_info}",
                reply_markup=reply_markup
            )
        else:
            # For initial messages, send a new message
            await message_obj.reply_text(
                f"Which major's handbook would you like to see?{page_info}",
                reply_markup=reply_markup
            )

    except Exception as e:
        logger.error(f"Error processing handbook query: {e}", exc_info=True)
        error_message = "I'm sorry, I couldn't retrieve the handbook information. Please try again later."

        if is_callback:
            await update.callback_query.edit_message_text(error_message)
        else:
            await message_obj.reply_text(error_message)


def is_content_question(text: str) -> bool:
    """
    Determine if query is asking about content within a handbook
    rather than requesting the handbook itself
    """
    # Question indicators
    question_words = ["what", "how", "why", "when", "where", "who", "which", "is", "are", "can", "do", "does"]
    academic_terms = ["course", "credit", "requirement", "prerequisite", "module", "class",
                      "thesis", "grade", "graduation", "degree", "major", "minor", "semester",
                      "program", "study", "curriculum", "elective", "core", "mandatory"]

    # Check for question mark
    has_question_mark = "?" in text

    # Check for question words
    has_question_word = any(text.lower().startswith(word) or f" {word} " in f" {text.lower()} "
                            for word in question_words)

    # Check for academic terms that suggest content questions
    has_academic_term = any(term in text.lower() for term in academic_terms)

    # Check for explicit handbook content phrases
    content_phrases = ["in the handbook", "from the handbook", "handbook say", "according to",
                       "requirement", "tell me about", "find in", "find out", "look up"]
    has_content_phrase = any(phrase in text.lower() for phrase in content_phrases)

    # Check if explicitly requesting the handbook file
    handbook_request_phrases = ["send me", "give me", "download", "get the handbook", "handbook for",
                                "handbook of", "pdf", "file"]
    is_handbook_request = any(phrase in text.lower() for phrase in handbook_request_phrases)

    # Check for program abbreviations that might indicate a content question about a specific program
    text_lower = text.lower()
    has_program_abbr = any(f" {abbr} " in f" {text_lower} " or
                           text_lower.startswith(f"{abbr} ") or
                           text_lower.endswith(f" {abbr}")
                           for abbr in MAJOR_ABBREVIATIONS.keys())

    # Logic to determine if it's a content question
    if is_handbook_request and not has_question_mark and not has_question_word:
        return False  # Explicitly requesting the handbook itself

    # If it has question syntax and (academic terms or content phrases or a program abbreviation), it's likely a content question
    return (has_question_mark or has_question_word) and (has_academic_term or has_content_phrase or has_program_abbr)