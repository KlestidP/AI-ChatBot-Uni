from abc import ABC, abstractmethod
from typing import List, Dict, Optional
from telegram import Update
from telegram.ext import ContextTypes
import logging

from uni_ai_chatbot.utils.utils import handle_error

logger = logging.getLogger(__name__)


class Tool(ABC):
    """Base abstract class for all tools in the chatbot"""

    def __init__(self, name: str, description: str) -> None:
        self.name: str = name
        self.description: str = description

    @abstractmethod
    async def handle(self, update: Update, context: ContextTypes.DEFAULT_TYPE, query: str) -> None:
        """
        Handle the user query with this tool

        Args:
            update: Telegram update object containing message and user info
            context: Telegram context with bot data
            query: The user's text query
        """
        pass

    def get_tool_description(self) -> Dict[str, str]:
        """Get description of this tool for classification purposes"""
        return {
            "name": self.name,
            "description": self.description
        }


class LockerTool(Tool):
    """Tool for handling locker-related queries"""

    def __init__(self) -> None:
        super().__init__(
            name="locker",
            description="Handles queries about locker hours and access in university colleges. "
                        "Use for questions about when lockers can be accessed, their locations, "
                        "or basement access times."
        )

    async def handle(self, update: Update, context: ContextTypes.DEFAULT_TYPE, query: str) -> None:
        """Process a locker-related query"""
        from uni_ai_chatbot.services.locker_service import handle_locker_hours
        await handle_locker_hours(update, context)


class LocationTool(Tool):
    """Tool for handling location and navigation queries"""

    def __init__(self) -> None:
        super().__init__(
            name="location",
            description="Helps users find places on campus and provides navigation assistance. "
                        "Use for questions about where things are located, how to find specific "
                        "facilities like printers, food, or study areas."
        )

    async def handle(self, update: Update, context: ContextTypes.DEFAULT_TYPE, query: str) -> None:
        """Process a location-related query"""
        from uni_ai_chatbot.bot.location_handlers import handle_location_with_ai
        await handle_location_with_ai(update, context, query)


class QATool(Tool):
    """Tool for handling general Q&A about university information"""

    def __init__(self) -> None:
        super().__init__(
            name="qa",
            description="Answers general questions about university policies, procedures, events, and information. "
                        "Use for inquiries about university services, documents, procedures, events, deadlines, "
                        "or any other university-related questions not specific to lockers or navigation."
        )

    async def handle(self, update: Update, context: ContextTypes.DEFAULT_TYPE, query: str) -> None:
        """Process a general question about the university with improved context"""
        qa_chain = context.bot_data["qa_chain"]
        try:
            # Send typing indicator to improve UX
            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

            # Invoke the QA chain
            response = qa_chain.invoke(query)
            result: str = response['result']

            # Enhance response with source information when available
            if 'source_documents' in response and response['source_documents']:
                # Group sources by type for better organization
                source_groups: Dict[str, List[str]] = {
                    'faq': [],
                    'location': [],
                    'locker': []
                }

                for doc in response['source_documents']:
                    if 'type' in doc.metadata:
                        doc_type: str = doc.metadata['type']
                        if doc_type == 'faq' and 'question' in doc.metadata:
                            source_groups['faq'].append(doc.metadata['question'])
                        elif doc_type == 'location' and 'name' in doc.metadata:
                            source_groups['location'].append(doc.metadata['name'])
                        elif doc_type == 'locker' and 'college' in doc.metadata:
                            source_groups['locker'].append(
                                f"{doc.metadata['college']} ({doc.metadata['day']})")

                # Add sourced information if available
                sources_text: List[str] = []
                if source_groups['faq']:
                    unique_faqs: List[str] = list(set(source_groups['faq']))[:3]  # Limit to 3 unique sources
                    sources_text.append("*Relevant FAQs:* " + ", ".join(unique_faqs))

                if source_groups['location']:
                    unique_locations: List[str] = list(set(source_groups['location']))[:3]
                    sources_text.append("*Relevant Locations:* " + ", ".join(unique_locations))

                if source_groups['locker']:
                    unique_lockers: List[str] = list(set(source_groups['locker']))[:3]
                    sources_text.append("*Relevant Locker Info:* " + ", ".join(unique_lockers))

                if sources_text:
                    result += "\n\n" + "\n".join(sources_text)

            await update.message.reply_text(result, parse_mode="Markdown")

        except Exception as e:
            logger.error(f"Error in QA processing: {e}")
            await handle_error(
                update,
                error=e,
                message="I'm having trouble answering that question. Could you rephrase it?"
            )


class FAQTool(Tool):
    """Tool for handling FAQ-related queries"""

    def __init__(self) -> None:
        super().__init__(
            name="faq",
            description="Answers frequently asked questions about university services, documents, "
                        "procedures, and common student needs. Use for questions about enrollment certificates, "
                        "residence permits, laundry, address changes, emergency contacts, driving licenses, "
                        "semester tickets, postal codes, and other common student inquiries."
        )

    async def handle(self, update: Update, context: ContextTypes.DEFAULT_TYPE, query: str) -> None:
        """Process a FAQ-related query"""
        from uni_ai_chatbot.services.faq_service import handle_faq_query
        await handle_faq_query(update, context, query)


class ToolRegistry:
    """Registry for all available tools in the chatbot"""

    def __init__(self) -> None:
        self.tools: List[Tool] = []

    def register_tool(self, tool: Tool) -> None:
        """Register a new tool"""
        self.tools.append(tool)

    def get_tool_by_name(self, name: str) -> Optional[Tool]:
        """Get a tool by its name"""
        for tool in self.tools:
            if tool.name == name:
                return tool
        return None

    def get_all_tools(self) -> List[Tool]:
        """Get all registered tools"""
        return self.tools

    def get_tool_descriptions(self) -> List[Dict[str, str]]:
        """Get descriptions of all tools for the classifier"""
        return [tool.get_tool_description() for tool in self.tools]


class HandbookTool(Tool):
    """Tool for handling handbook and major-related queries"""

    def __init__(self) -> None:
        super().__init__(
            name="handbook",
            description="Provides access to university program handbooks and information about majors. "
                        "Use for questions about degree programs, major requirements, courses, and "
                        "curriculum information."
        )

    async def handle(self, update: Update, context: ContextTypes.DEFAULT_TYPE, query: str) -> None:
        """Process a handbook-related query"""
        from uni_ai_chatbot.services.handbook_service import handle_handbook_query
        await handle_handbook_query(update, context, query)


class ServeryTool(Tool):
    """Tool for handling servery hours queries"""

    def __init__(self) -> None:
        super().__init__(
            name="servery",
            description="Provides information about dining halls and servery hours in university colleges. "
                        "Use for questions about meal times, when to eat, breakfast, lunch, or dinner hours."
        )

    async def handle(self, update: Update, context: ContextTypes.DEFAULT_TYPE, query: str) -> None:
        """Process a servery-related query"""
        from uni_ai_chatbot.services.servery_service import handle_servery_hours
        await handle_servery_hours(update, context, query)

# Register the tool


# Create global tool registry
tool_registry: ToolRegistry = ToolRegistry()

# Register default tools
tool_registry.register_tool(LockerTool())
tool_registry.register_tool(LocationTool())
tool_registry.register_tool(QATool())
tool_registry.register_tool(FAQTool())
tool_registry.register_tool(HandbookTool())
tool_registry.register_tool(ServeryTool())
