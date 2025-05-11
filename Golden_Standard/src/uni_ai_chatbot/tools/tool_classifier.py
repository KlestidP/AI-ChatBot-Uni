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

        Args:
            query: The user's message text

        Returns:
            The name of the tool that should handle this query
        """
        if not self.llm:
            # Fallback to rule-based classification if no LLM available
            return self._rule_based_classify(query)

        # Generate a prompt for the LLM to classify the query
        classification_prompt = self._build_classification_prompt(query)

        try:
            # Call the LLM to classify the query
            response = self.llm.invoke(classification_prompt)
            response_text = response.content

            # Parse the response to extract the tool name
            tool_name = self._parse_classification_response(response_text)

            logger.info(f"LLM classified query '{query}' as '{tool_name}'")
            return tool_name

        except Exception as e:
            logger.error(f"Error classifying query with LLM: {e}")
            # Fall back to rule-based classification
            return self._rule_based_classify(query)

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

    def _rule_based_classify(self, query: str) -> str:
        """
        Fallback rule-based classification method similar to the current approach
        """
        query = query.lower()

        # Check if asking for locker hours
        if "locker" in query and any(word in query for word in ["open", "hours", "time", "access"]):
            return "locker"

        # Extract feature keywords
        feature_keywords = extract_feature_keywords(query)

        # Location-related keywords and phrases
        location_features = ["print", "printer", "food", "eat", "study", "studying",
                             "coffee", "quiet", "library", "ify"]
        location_indicators = ["where", "find", "location", "how to get to", "building", "room", "campus",
                               "where can i get", "where can i find", "where is", "how do i get to"]

        # Check if query mentions any location features
        has_feature_keywords = bool(feature_keywords) or any(feature in query for feature in location_features)

        # Check if it's a location query
        is_location_query = has_feature_keywords or any(indicator in query for indicator in location_indicators)

        if is_location_query:
            return "location"

        # Default to general QA
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