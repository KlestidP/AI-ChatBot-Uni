import copy
import logging
from typing import Optional, List, Dict, Any
from telegram import Update, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, User
from telegram.constants import ParseMode
from telegram.ext import ContextTypes
from uni_ai_chatbot.bot.location_handlers import show_location_details, handle_location_with_ai
from uni_ai_chatbot.services.handbook_service import handle_handbook_query

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


async def handle_location_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle callback queries from inline keyboards
    """
    query: CallbackQuery = update.callback_query
    await query.answer()

    # Handle location callbacks
    if query.data.startswith("location:"):
        location_id: str = query.data.split(':')[1]
        campus_map: List[Dict[str, Any]] = context.bot_data["campus_map"]

        # Find the location by ID
        location: Optional[Dict[str, Any]] = next((loc for loc in campus_map if str(loc['id']) == location_id), None)

        if location:
            await show_location_details(update, location, is_callback=True)
        else:
            await query.edit_message_text("Sorry, I couldn't find that location anymore.")

    # Handle handbook callbacks
    elif query.data.startswith("hb:"):
        try:
            # Extract the handbook index
            hb_idx = int(query.data.split(':')[1])
            handbooks = context.bot_data["handbooks"]
            # Ensure the index is valid
            if 0 <= hb_idx < len(handbooks):
                handbook = handbooks[hb_idx]
                if handbook and handbook.get('url'):
                    await query.edit_message_text(f"Fetching the handbook for {handbook['major']}...")
                    await update.effective_chat.send_document(
                        document=handbook['url'],
                        filename=handbook['file_name'],
                        caption=f"Handbook for {handbook['major']}"
                    )
                else:
                    await query.edit_message_text(f"Sorry, I couldn't find that handbook.")
            else:
                await query.edit_message_text("Sorry, I couldn't find that handbook.")
        except Exception as e:
            logger.error(f"Error handling handbook callback: {e}")
            await query.edit_message_text("Sorry, I encountered an error retrieving the handbook.")

    # Handle handbook pagination
    elif query.data == "hb_page:prev" or query.data == "hb_page:next":
        # Change page number
        if query.data == "hb_page:prev":
            context.user_data['handbook_page'] = max(0, context.user_data.get('handbook_page', 0) - 1)
        else:  # next
            handbooks = context.bot_data.get("handbooks", [])
            total_pages = (len(handbooks) + 10 - 1) // 10  # 10 is PAGE_SIZE
            context.user_data['handbook_page'] = min(
                total_pages - 1,
                context.user_data.get('handbook_page', 0) + 1
            )

        # Re-display the handbook menu
        await handle_handbook_query(update, context)

    # Handle onboarding callbacks
    elif query.data.startswith("onboard:") or query.data.startswith("location_example:") or \
            query.data.startswith("dining_example:") or query.data.startswith("locker_example:") or \
            query.data.startswith("handbook_example:") or query.data.startswith("faq_example:"):
        await handle_onboarding_callback(update, context)


async def handle_onboarding_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle onboarding callback queries from inline keyboards
    """
    query: CallbackQuery = update.callback_query
    await query.answer()

    user: User = update.effective_user

    # Get chat ID for sending messages
    chat_id = update.effective_chat.id

    if query.data == "onboard:help":
        # Send help information
        await query.edit_message_text("Loading help information...")

        help_text = (
            "🎓 *Constructor University Bremen Bot* 🎓\n\n"
            "Here's what I can help you with:\n\n"
            "• 📍 `/where [location]` — Find places on campus (e.g., Ocean Lab, C3, IRC).\n\n"
            "• 🔍 `/find [feature]` — Find places with specific features (e.g., printer, food, study).\n\n"
            "• 🧺 *Locker hours* — Ask for locker access times in any college.\n\n"
            "• 🍽 *Servery hours* — Ask for meal times in any college or the coffee bar.\n\n"
            "• 📚 `/handbook [program]` — Get program handbooks or ask about course requirements.\n\n"
            "• ❓ *University FAQs* — Ask about documents, laundry, residence permits, etc.\n\n"
            "• 🤖 `/provider [name] [api_key] [model]` — Change the AI provider for your queries.\n\n"
            "• 📋 `/providers` — List all available AI providers and their status.\n\n"
            "💬 Just type your question naturally — I'll understand and route it to the right service!\n\n"
            "Try questions like:\n"
            "- \"Where can I find a printer?\"\n"
            "- \"What are the locker hours for Krupp College?\"\n"
            "- \"When is lunch served at Nordmetall?\"\n"
            "- \"How do I get my enrollment certificate?\"\n\n"
            "🔒 I'm limited to university-related queries only."
        )

        await context.bot.send_message(
            chat_id=chat_id,
            text=help_text,
            parse_mode=ParseMode.MARKDOWN
        )

    elif query.data == "onboard:back":
        # Return to main menu
        welcome_text = (
            f"👋 *Welcome to Constructor University Bremen Bot, {user.first_name}!*\n\n"
            f"I'm your AI assistant for navigating campus life. You can ask me questions in natural language - "
            f"just type your question as you would ask a person!\n\n"
            f"For example, try asking:\n"
            f"• \"Where can I find a printer?\"\n"
            f"• \"What are the locker hours for Krupp?\"\n"
            f"• \"When is lunch served at Nordmetall?\"\n\n"
            f"Or explore my capabilities using these example buttons:"
        )

        # Create main menu keyboard
        keyboard = [
            [
                InlineKeyboardButton("📍 Campus Locations", callback_data="onboard:locations"),
                InlineKeyboardButton("🍽 Dining Hours", callback_data="onboard:dining"),
            ],
            [
                InlineKeyboardButton("🧺 Locker Access", callback_data="onboard:lockers"),
                InlineKeyboardButton("📚 Program Handbooks", callback_data="onboard:handbooks"),
            ],
            [
                InlineKeyboardButton("❓ University FAQs", callback_data="onboard:faqs"),
                InlineKeyboardButton("🔍 See All Features", callback_data="onboard:help"),
            ]
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            text=welcome_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )

    # Location examples
    elif query.data.startswith("location_example:"):
        example_type = query.data.split(":")[1]

        if example_type == "ocean_lab":
            # Show Ocean Lab location
            await query.edit_message_text("Finding Ocean Lab for you...")

            # Create a new message with Ocean Lab info
            message_text = (
                "📍 *Ocean Lab*\n\n"
                "The Ocean Lab is a dedicated research facility for marine science studies.\n\n"
                "Located on the south side of campus near the Research buildings."
            )

            # Add back button
            keyboard = [[InlineKeyboardButton("« Back to Locations", callback_data="onboard:locations")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await context.bot.send_message(
                chat_id=chat_id,
                text=message_text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN
            )

            # Get location coordinates from database if possible
            campus_map = context.bot_data.get("campus_map", [])
            ocean_lab = next((loc for loc in campus_map if "ocean" in loc["name"].lower()), None)

            if ocean_lab:
                await context.bot.send_venue(
                    chat_id=chat_id,
                    latitude=float(ocean_lab['latitude']),
                    longitude=float(ocean_lab['longitude']),
                    title=ocean_lab['name'],
                    address=ocean_lab.get('address', 'Constructor University, Bremen')
                )

        elif example_type == "printers":
            await query.edit_message_text("Looking for printers on campus...")

            # Create a message about printer locations
            message_text = (
                "🖨️ *Printer Locations on Campus*\n\n"
                "I found several places with printers:\n\n"
                "• Campus Center (IRC)\n"
                "• Research 1\n"
                "• Research 2\n"
                "• Krupp College\n"
                "• Nordmetall College\n"
                "• College III\n\n"
                "Most printers require your campus card for payment."
            )

            # Add back button
            keyboard = [[InlineKeyboardButton("« Back to Locations", callback_data="onboard:locations")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await context.bot.send_message(
                chat_id=chat_id,
                text=message_text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN
            )

        elif example_type == "study":
            await query.edit_message_text("Looking for study spaces on campus...")

            # Create a message about study locations
            message_text = (
                "📚 *Study Spaces on Campus*\n\n"
                "I found several places for studying:\n\n"
                "• Campus Center (IRC) - quiet areas on upper floors\n"
                "• South Hall - comfortable study rooms\n"
                "• East Hall - group study spaces\n"
                "• College common areas - available to all students\n"
                "• Krupp College - study rooms with whiteboards\n\n"
                "Most spaces are open 24/7 with your campus card."
            )

            # Add back button
            keyboard = [[InlineKeyboardButton("« Back to Locations", callback_data="onboard:locations")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await context.bot.send_message(
                chat_id=chat_id,
                text=message_text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN
            )

    # Dining examples
    elif query.data.startswith("dining_example:"):
        example_type = query.data.split(":")[1]

        if example_type == "lunch":
            await query.edit_message_text("Checking lunch times at C3 & Nordmetall College...")

            # Create a lunch times message
            message_text = (
                "🍽 *Lunch Hours at C3 & Nordmetall College*\n\n"
                "📅 All Week:\n"
                "- Lunch: 12:00 PM - 2:00 PM\n\n"
                "Daily specials are posted at the entrance to the servery."
            )

            # Add back button
            keyboard = [[InlineKeyboardButton("« Back to Dining", callback_data="onboard:dining")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await context.bot.send_message(
                chat_id=chat_id,
                text=message_text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN
            )

        elif example_type == "coffee":
            await query.edit_message_text("Checking Coffee Bar hours...")

            # Create a coffee bar hours message
            message_text = (
                "☕ *Coffee Bar Hours*\n\n"
                "📅 Monday - Friday:\n"
                "- Open: 09:30 AM – 05:30 PM\n\n"
                "Located in the Campus Center (IRC). Offers coffee, tea, pastries, and sandwiches."
            )

            # Add back button
            keyboard = [[InlineKeyboardButton("« Back to Dining", callback_data="onboard:dining")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await context.bot.send_message(
                chat_id=chat_id,
                text=message_text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN
            )

            # Add back button
            keyboard = [[InlineKeyboardButton("« Back to Dining", callback_data="onboard:dining")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await context.bot.send_message(
                chat_id=chat_id,
                text=message_text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN
            )

    # Locker examples
    elif query.data.startswith("locker_example:"):
        example_type = query.data.split(":")[1]

        if example_type == "krupp":
            await query.edit_message_text("Checking locker hours at Krupp College...")

            # Create a Krupp locker hours message
            message_text = (
                "🔓 *Locker Hours for Krupp College*\n\n"
                "📅 Monday:\n"
                "- Basement A: 9:00 AM - 10:00 PM\n"
                "- Basement B: 9:00 AM - 10:00 PM\n"
                "- Basement C: 10:00 AM - 9:00 PM\n\n"
                "📅 Thursday:\n"
                "- Basement A: 9:00 AM - 10:00 PM\n"
                "- Basement B: 9:00 AM - 10:00 PM\n"
                "- Basement C: 10:00 AM - 9:00 PM\n\n"
                "Access with your campus card only."
            )

            # Add back button
            keyboard = [[InlineKeyboardButton("« Back to Lockers", callback_data="onboard:lockers")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await context.bot.send_message(
                chat_id=chat_id,
                text=message_text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN
            )

        elif example_type == "c3":
            await query.edit_message_text("Checking locker hours at College III...")

            # Create a C3 locker hours message
            message_text = (
                "🔓 *Locker Hours for College III*\n\n"
                "📅 Monday:\n"
                "- Basement A: 8:00 AM - 10:00 PM\n"
                "- Basement B: 9:00 AM - 10:00 PM\n"
                "- Basement C: 9:00 AM - 9:00 PM\n"
                "- Basement D: 10:00 AM - 8:00 PM\n\n"
                "📅 Thursday:\n"
                "- Basement A: 8:00 AM - 10:00 PM\n"
                "- Basement B: 9:00 AM - 10:00 PM\n"
                "- Basement C: 9:00 AM - 9:00 PM\n"
                "- Basement D: 10:00 AM - 8:00 PM\n\n"
                "Access with your campus card only."
            )

            # Add back button
            keyboard = [[InlineKeyboardButton("« Back to Lockers", callback_data="onboard:lockers")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await context.bot.send_message(
                chat_id=chat_id,
                text=message_text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN
            )

            # Add back button
            keyboard = [[InlineKeyboardButton("« Back to Lockers", callback_data="onboard:lockers")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await context.bot.send_message(
                chat_id=chat_id,
                text=message_text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN
            )

    # Handbook examples
    elif query.data.startswith("handbook_example:"):
        example_type = query.data.split(":")[1]

        if example_type == "cs":
            await query.edit_message_text("Looking for Computer Science handbook...")

            # Create a CS handbook message
            message_text = (
                "📚 *Computer Science Handbook*\n\n"
                "I can provide the Computer Science handbook. The handbook includes:\n\n"
                "• Program overview and learning outcomes\n"
                "• Curriculum structure\n"
                "• Course descriptions\n"
                "• Graduation requirements\n"
                "• Faculty information\n\n"
                "To download the complete handbook, type:\n"
                "`/handbook Computer Science`"
            )

            # Add back button
            keyboard = [[InlineKeyboardButton("« Back to Handbooks", callback_data="onboard:handbooks")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await context.bot.send_message(
                chat_id=chat_id,
                text=message_text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN
            )

        elif example_type == "browse":
            await query.edit_message_text("Loading program handbooks...")

            # Create a browse handbooks message
            message_text = (
                "📚 *Available Program Handbooks*\n\n"
                "You can request handbooks for these programs:\n\n"
                "• Computer Science\n"
                "• Physics and Data Science\n"
                "• Global Economics and Management\n"
                "• Robotics and Intelligent Systems\n"
                "• Biochemistry and Cell Biology\n"
                "• International Business Administration\n"
                "• International Relations: Politics and History\n"
                "• And many more...\n\n"
                "To get a handbook, type:\n"
                "`/handbook [program name]`\n\n"
                "Or use abbreviations like CS, IBA, IRPH, etc."
            )

            # Add back button
            keyboard = [[InlineKeyboardButton("« Back to Handbooks", callback_data="onboard:handbooks")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await context.bot.send_message(
                chat_id=chat_id,
                text=message_text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN
            )

        elif example_type == "requirements":
            await query.edit_message_text("Looking up graduation requirements...")

            # Create a graduation requirements message
            message_text = (
                "📚 *Bachelor's Degree Graduation Requirements*\n\n"
                "For a Bachelor's degree at Constructor University Bremen, students typically need to:\n\n"
                "• Complete 180 ECTS credits over 3 years (6 semesters)\n"
                "• Pass all required core modules for their major\n"
                "• Complete a Bachelor thesis (usually 15 ECTS)\n"
                "• Maintain a minimum GPA (usually 2.0 or higher)\n"
                "• Complete all mandatory internships or practical requirements\n"
                "• Fulfill any language requirements\n\n"
                "*Note:* Requirements vary by program. Please refer to your specific program handbook for detailed "
                "requirements."
            )

            # Add back button
            keyboard = [[InlineKeyboardButton("« Back to Handbooks", callback_data="onboard:handbooks")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await context.bot.send_message(
                chat_id=chat_id,
                text=message_text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN
            )

    # FAQ examples
    elif query.data.startswith("faq_example:"):
        example_type = query.data.split(":")[1]

        if example_type == "documents":
            await query.edit_message_text("Checking enrollment certificate information...")

            # Create an enrollment certificate FAQ message
            message_text = (
                "📄 *How to Get Your Enrollment Certificate*\n\n"
                "You can obtain your enrollment certificate in two ways:\n\n"
                "1. *Online*: Log in to the Campus Portal and navigate to the 'Documents' section. "
                "Select 'Enrollment Certificate' and download the PDF.\n\n"
                "2. *In Person*: Visit the Registrar's Office during office hours "
                "(Monday-Friday, 10:00-16:00) with your student ID.\n\n"
                "Enrollment certificates are available immediately after you complete registration. "
                "The certificate includes your full name, program, and enrollment period."
            )

            # Add back button
            keyboard = [[InlineKeyboardButton("« Back to FAQs", callback_data="onboard:faqs")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await context.bot.send_message(
                chat_id=chat_id,
                text=message_text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN
            )

        elif example_type == "housing":
            await query.edit_message_text("Checking laundry information...")

            # Create a laundry FAQ message
            message_text = (
                "🧺 *Laundry on Campus*\n\n"
                "🧺 Each college block at Constructor University has a dedicated laundry room located in the "
                "basement.\n\n"
                "- 🧼 2 washing machines\n"
                "- 🔁 2 dryers\n"
                "- ⏰ Open 24/7\n\n"
                "💳 Payment is handled via the *Airwallet* app.\n"
                "💰 Prices (as of Spring 2025):\n"
                "  - Washing: **€3.20**\n"
                "  - Drying: **€2.70**\n\n"
                "📱 Download the Airwallet app, create an account, and follow the instructions posted in your dorm’s "
                "laundry area."
            )

            # Add back button
            keyboard = [[InlineKeyboardButton("« Back to FAQs", callback_data="onboard:faqs")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await context.bot.send_message(
                chat_id=chat_id,
                text=message_text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN
            )

        elif example_type == "services":
            await query.edit_message_text("Checking student ID information...")

            # Create a student ID FAQ message
            message_text = (
                "🪪 *Getting Your Student ID Card*\n\n"
                "You can obtain your student ID card from the Campus Card Office:\n\n"
                "• *Location*: Campus Center, Room 247\n\n"
                "• *Hours*: Monday-Friday, 10:00-15:00\n\n"
                "• *Requirements*: Bring your passport or government ID and your admission letter.\n\n"
                "• *Process*: Your photo will be taken on-site, and your card will be issued immediately.\n\n"
                "• *First Card*: Your first student ID is free. Replacement cards cost €20.\n\n"
                "Your student ID card is used for servery payments, library services, building access, "
                "printing, and as proof of enrollment."
            )

            # Add back button
            keyboard = [[InlineKeyboardButton("« Back to FAQs", callback_data="onboard:faqs")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await context.bot.send_message(
                chat_id=chat_id,
                text=message_text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN
            )

    # Category pages
    elif query.data == "onboard:locations":
        text = (
            "*📍 Finding Campus Locations*\n\n"
            "You can ask me about any location on campus:\n"
            "• '/where IRC' - Get info about a specific place\n"
            "• '/find printer' - Find places with specific features\n"
            "• 'Where can I get food?' - Ask naturally\n\n"
            "I'll provide directions and details for all campus locations!"
        )

        # Add examples keyboard
        keyboard = [
            [InlineKeyboardButton("Find Ocean Lab", callback_data="location_example:ocean_lab")],
            [InlineKeyboardButton("Find Printers", callback_data="location_example:printers")],
            [InlineKeyboardButton("Find Study Spaces", callback_data="location_example:study")],
            [InlineKeyboardButton("« Back to Menu", callback_data="onboard:back")]
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            text=text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )

    elif query.data == "onboard:dining":
        text = (
            "*🍽 Checking Dining Hours*\n\n"
            "Find out when meals are served at any college:\n"
            "• 'When is lunch at Krupp?'\n"
            "• 'Coffee Bar hours on weekends?'\n"
            "• 'Servery hours for dinner at Nordmetall'\n\n"
            "I know all breakfast, lunch, dinner, and special meal timings!"
        )

        # Add examples keyboard
        keyboard = [
            [InlineKeyboardButton("Lunch Hours", callback_data="dining_example:lunch")],
            [InlineKeyboardButton("Coffee Bar Hours", callback_data="dining_example:coffee")],
            [InlineKeyboardButton("« Back to Menu", callback_data="onboard:back")]
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            text=text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )

    elif query.data == "onboard:lockers":
        text = (
            "*🧺 Locker Access Hours*\n\n"
            "Check when you can access basement lockers:\n"
            "• 'Locker hours for Krupp College'\n"
            "• 'When can I access my locker in C3?'\n"
            "• 'Nordmetall Basement A access times'\n\n"
            "I can tell you access times for any college and basement!"
        )

        # Add examples keyboard
        keyboard = [
            [InlineKeyboardButton("Krupp Lockers", callback_data="locker_example:krupp")],
            [InlineKeyboardButton("C3 Basement", callback_data="locker_example:c3")],
            [InlineKeyboardButton("« Back to Menu", callback_data="onboard:back")]
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            text=text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )

    elif query.data == "onboard:handbooks":
        text = (
            "*📚 Program Handbooks*\n\n"
            "Access program handbooks and information:\n"
            "• '/handbook Computer Science'\n"
            "• 'What are the requirements for Physics?'\n"
            "• 'Send me the handbook for IBA'\n\n"
            "I can find handbooks for all programs and answer questions about curriculum!"
        )

        # Add examples keyboard
        keyboard = [
            [InlineKeyboardButton("CS Handbook", callback_data="handbook_example:cs")],
            [InlineKeyboardButton("Browse Programs", callback_data="handbook_example:browse")],
            [InlineKeyboardButton("Graduation Requirements", callback_data="handbook_example:requirements")],
            [InlineKeyboardButton("« Back to Menu", callback_data="onboard:back")]
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            text=text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )

    elif query.data == "onboard:faqs":
        text = (
            "*❓ University FAQs*\n\n"
            "Get answers about university life:\n"
            "• 'How do I get my enrollment certificate?'\n"
            "• 'Residence permit application process?'\n"
            "• 'How to do laundry on campus?'\n\n"
            "Ask me any question about university services and procedures!"
        )

        # Add examples keyboard
        keyboard = [
            [InlineKeyboardButton("Documents & Forms", callback_data="faq_example:documents")],
            [InlineKeyboardButton("Housing Questions", callback_data="faq_example:housing")],
            [InlineKeyboardButton("Student Services", callback_data="faq_example:services")],
            [InlineKeyboardButton("« Back to Menu", callback_data="onboard:back")]
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            text=text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
