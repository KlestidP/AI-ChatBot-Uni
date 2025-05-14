import logging
from typing import Dict, List, Optional
from functools import lru_cache
from langchain_mistralai import ChatMistralAI
from telegram import Update
from telegram.ext import ContextTypes

from uni_ai_chatbot.configurations.config import ENABLE_LLM_CLASSIFICATION

logger = logging.getLogger(__name__)


class ToolClassifier:
    """
    A class that uses LLM to classify user queries and select appropriate tools
    """

    def __init__(self, llm: Optional[ChatMistralAI] = None) -> None:
        self.llm: Optional[ChatMistralAI] = llm
        from uni_ai_chatbot.tools.tools_architecture import tool_registry
        self._tools: List[Dict[str, str]] = tool_registry.get_tool_descriptions()

    async def classify_query(self, query: str, context: ContextTypes.DEFAULT_TYPE, update: Update) -> str:
        """
        Classify a user query to determine which tool should handle it
        Prioritizes LLM classification if available, falls back to basic rules
        Also handles ongoing conversations

        Args:
            query: The user's input text
            context: Telegram context for checking conversation state
            update: Telegram update object for user ID

        Returns:
            The name of the tool that should handle the query
        """
        # Check for active conversations
        user_id = update.effective_user.id

        # Check if we're in an active locker conversation
        if 'locker_conversations' in context.bot_data and user_id in context.bot_data['locker_conversations']:
            return "locker"  # Continue the locker conversation

        # Add this new check for servery conversations
        if 'servery_conversations' in context.bot_data and user_id in context.bot_data['servery_conversations']:
            return "servery"  # Continue the servery conversation

        # Check if we're in an active handbook conversation
        if 'handbook_conversations' in context.bot_data and user_id in context.bot_data['handbook_conversations']:
            return "handbook"

        # Check if we're in an active FAQ conversation
        if 'faq_conversations' in context.bot_data and user_id in context.bot_data['faq_conversations']:
            return "faq"


        # Use the LLM if available and enabled
        if self.llm and ENABLE_LLM_CLASSIFICATION:
            try:
                # Use cached classification to avoid repeated LLM calls
                clean_query = query.strip().lower()
                tool_name = await self._cached_classify(clean_query)
                logger.info(f"LLM classified query '{query}' as '{tool_name}'")
                return tool_name
            except Exception as e:
                logger.warning(f"LLM classification failed: {e}, falling back to basic rules")

        # Fall back to basic rules
        return self._rule_based_classification(query)

    @lru_cache(maxsize=100)
    async def _cached_classify(self, query: str) -> str:
        """
        Cached classification to avoid repeated LLM calls for identical queries

        Args:
            query: The normalized user query

        Returns:
            The classified tool name
        """
        classification_prompt = self._build_classification_prompt(query)
        response = self.llm.invoke(classification_prompt)
        return self._parse_classification_response(response.content)

    def _rule_based_classification(self, query: str) -> str:
        """
        Classify query using simple rule-based approach

        Args:
            query: The user query

        Returns:
            The classified tool name
        """
        query_lower = query.lower()

        # Basic location detection
        location_terms = ["where", "find", "location", "where is", "how do i get to"]
        if any(term in query_lower for term in location_terms):
            return "location"

        # Basic locker detection
        locker_terms = ["locker", "basement", "access"]
        if any(term in query_lower for term in locker_terms):
            return "locker"

        servery_terms = ["servery", "food", "meal", "eat", "dining", "breakfast", "lunch", "dinner", "coffee bar",
                         "menu", "cafeteria"]
        time_terms = ["hours", "time", "open", "when", "schedule"]
        if any(term in query_lower for term in servery_terms) and any(term in query_lower for term in time_terms):
            return "servery"

        # Handbook detection (add this new section)
        handbook_terms = ["handbook", "program", "major", "degree", "curriculum", "syllabus"]
        if any(term in query_lower for term in handbook_terms):
            return "handbook"

        # FAQ detection
        faq_terms = ["how do i", "how to", "what is the", "can i", "when is"]
        if any(query_lower.startswith(term) for term in faq_terms):
            return "faq"

        # Default to general QA
        return "qa"

    def _build_classification_prompt(self, query: str) -> str:
        """Build a prompt for the LLM to classify the query"""
        # Create a detailed prompt with examples for better classification
        tool_descriptions = "\n\n".join([
            f"Tool: {tool['name']}\nDescription: {tool['description']}"
            for tool in self._tools
        ])

        # Add examples to help the model understand common patterns
        examples = """
        Examples:
        1. "Where is the library?" → location
        2. "How do I get my enrollment certificate?" → faq
        3. "When are the locker hours for Krupp College?" → locker
        4. "What's the address of the university?" → qa
        5. "Where can I print documents?" → location
        6. "Tell me about the semester ticket" → faq
        7. "How to change my address in Bremen?" → faq
        8. "What's the student emergency number?" → faq
        9. "Where can I get food on campus?" → location
        10. "When is breakfast served at Krupp College?" → servery
        11. "What are the lunch hours at Mercator?" → servery
        12. "Is the Coffee Bar open on weekends?" → servery
        13. "Servery hours for Nordmetall" → servery
        """

        return f"""You are a query classifier for a university chatbot. Your task is to classify the user's query into one of the available tools based on its intent.

        Available tools:
        {tool_descriptions}

        {examples}

        User query: "{query}"

        Analyze the query and determine which tool is most appropriate to handle it. Respond with just the tool name and nothing else. The available tools are: location, locker, faq, qa, handbook, servery.
        """

    def _parse_classification_response(self, response: str) -> str:
        """Parse the LLM's response to extract the tool name"""
        # Clean the response text
        response = response.strip().lower()

        # Check if the response contains any of our tool names
        valid_tools = ["location", "locker", "faq", "qa", "handbook", "servery"]
        for tool_name in valid_tools:
            if tool_name in response:
                return tool_name

        # If no match found, default to qa
        return "qa"


async def get_appropriate_tool(update: Update, context: ContextTypes.DEFAULT_TYPE, query: str):
    """
    Determine the appropriate tool to handle a user query using AI

    Args:
        update: Telegram Update object
        context: Telegram context
        query: The user's message text

    Returns:
        The appropriate Tool object to handle the query
    """
    # Initialize the classifier if it doesn't exist in bot_data
    if "tool_classifier" not in context.bot_data:
        llm = None
        if "llm" in context.bot_data:
            llm = context.bot_data["llm"]
        context.bot_data["tool_classifier"] = ToolClassifier(llm)

    # Classify the query
    classifier = context.bot_data["tool_classifier"]
    tool_name = await classifier.classify_query(query, context, update)

    # Get the appropriate tool from the registry
    from uni_ai_chatbot.tools.tools_architecture import tool_registry
    tool = tool_registry.get_tool_by_name(tool_name)

    # If no tool found, default to QA
    if not tool:
        tool = tool_registry.get_tool_by_name("qa")

    return tool
