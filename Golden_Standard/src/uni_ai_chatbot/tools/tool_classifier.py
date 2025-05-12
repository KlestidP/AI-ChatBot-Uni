import logging
import json
from typing import Dict, Any, List
from langchain_mistralai import ChatMistralAI
from telegram import Update
from telegram.ext import ContextTypes

from uni_ai_chatbot.tools.tools_architecture import tool_registry
from uni_ai_chatbot.data.campus_map_data import extract_feature_keywords

logger = logging.getLogger(__name__)


class ToolClassifier:
    """
    A class that uses LLM to classify user queries and select appropriate tools
    """

    def __init__(self, llm: ChatMistralAI = None):
        self.llm = llm
        self._tools = tool_registry.get_tool_descriptions()

    async def classify_query(self, query: str) -> str:
        """
        Classify a user query to determine which tool should handle it

        First tries rule-based classification for clear cases,
        then falls back to LLM for ambiguous queries
        """
        query_lower = query.lower()

        # Rule 1: Locker-related queries
        if "locker" in query_lower and any(word in query_lower for word in
                                           ["hours", "time", "access", "open", "basement"]):
            return "locker"

        # Rule 2: FAQ-related queries - check for common FAQ topics
        faq_indicators = [
            "immatrikulation", "enrollment", "certificate",
            "laundry", "washing", "dryer",
            "residence permit", "visa", "ausländerbehörde",
            "address change", "moving", "anmeldung",
            "emergency", "emergency contact",
            "driving license", "driver's license", "führerschein",
            "semester ticket", "transportation",
            "postal code", "zip", "mail"
        ]

        if any(indicator in query_lower for indicator in faq_indicators):
            return "faq"

        # Rule 3: Location-related queries
        location_indicators = ["where", "find", "location", "how to get", "building", "room"]
        feature_keywords = extract_feature_keywords(query_lower)

        if any(indicator in query_lower for indicator in location_indicators) or feature_keywords:
            return "location"

        # For ambiguous cases, use the LLM if available
        if self.llm:
            try:
                classification_prompt = self._build_classification_prompt(query)
                response = self.llm.invoke(classification_prompt)
                tool_name = self._parse_classification_response(response.content)
                logger.info(f"LLM classified query '{query}' as '{tool_name}'")
                return tool_name
            except Exception as e:
                logger.warning(f"LLM classification failed: {e}, falling back to default")

        # Default to general QA for anything else
        return "qa"

    def _build_classification_prompt(self, query: str) -> str:
        """
        Build a prompt for the LLM to classify the query
        """
        tool_descriptions = "\n\n".join([
            f"Tool: {tool['name']}\nDescription: {tool['description']}"
            for tool in self._tools
        ])

        return f"""You are a query classifier for a university chatbot. Your task is to classify the user's query into one of the available tools based on its intent.

Available tools:
{tool_descriptions}

User query: "{query}"

Analyze the query and determine which tool is most appropriate to handle it. Respond with just the tool name and nothing else.
"""

    def _parse_classification_response(self, response: str) -> str:
        """
        Parse the LLM's response to extract the tool name
        """
        # Clean the response text
        response = response.strip().lower()

        # Check if the response contains any of our tool names
        for tool in self._tools:
            tool_name = tool['name'].lower()
            if tool_name in response:
                return tool_name

        # If no match found, default to qa
        return "qa"


async def get_appropriate_tool(update: Update, context: ContextTypes.DEFAULT_TYPE, query: str):
    """
    Determine the appropriate tool to handle a user query

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
    tool_name = await classifier.classify_query(query)

    # Get the appropriate tool from the registry
    tool = tool_registry.get_tool_by_name(tool_name)

    # If no tool found, default to QA
    if not tool:
        tool = tool_registry.get_tool_by_name("qa")

    return tool