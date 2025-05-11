from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from telegram import Update
from telegram.ext import ContextTypes
import logging

logger = logging.getLogger(__name__)


class Tool(ABC):
    """Base abstract class for all tools in the chatbot"""
    
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
    
    @abstractmethod
    async def handle(self, update: Update, context: ContextTypes.DEFAULT_TYPE, query: str) -> None:
        """Handle the user query with this tool"""
        pass
    
    def get_tool_description(self) -> Dict[str, str]:
        """Get description of this tool for classification purposes"""
        return {
            "name": self.name,
            "description": self.description
        }


class LockerTool(Tool):
    """Tool for handling locker-related queries"""
    
    def __init__(self):
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
    
    def __init__(self):
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
    
    def __init__(self):
        super().__init__(
            name="qa",
            description="Answers general questions about university policies, procedures, events, and information. "
                       "Use for inquiries about university services, documents, procedures, events, deadlines, "
                       "or any other university-related questions not specific to lockers or navigation."
        )
    
    async def handle(self, update: Update, context: ContextTypes.DEFAULT_TYPE, query: str) -> None:
        """Process a general question about the university"""
        qa_chain = context.bot_data["qa_chain"]
        try:
            response = qa_chain.invoke(query)
            result = response['result']

            # Check if we have source documents
            if 'source_documents' in response and response['source_documents']:
                # Add a "Sources:" section
                sources = set()
                for doc in response['source_documents']:
                    if 'type' in doc.metadata:
                        if doc.metadata['type'] == 'faq' and 'question' in doc.metadata:
                            sources.add(f"FAQ: {doc.metadata['question']}")
                        elif doc.metadata['type'] == 'location' and 'name' in doc.metadata:
                            sources.add(f"Location: {doc.metadata['name']}")

                if sources:
                    result += "\n\n*Sources:*\n- " + "\n- ".join(sources)

            await update.message.reply_text(result, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Error processing: {e}")
            await update.message.reply_text("Sorry, I couldn't process your question.")


class ToolRegistry:
    """Registry for all available tools in the chatbot"""
    
    def __init__(self):
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


# Create global tool registry
tool_registry = ToolRegistry()

# Register default tools
tool_registry.register_tool(LockerTool())
tool_registry.register_tool(LocationTool())
tool_registry.register_tool(QATool())
